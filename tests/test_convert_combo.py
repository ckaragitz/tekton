"""test_convert_combo.py -- the COMBINATION-INPUT routes (src/rvt/convert).

Fast, self-contained checks of what the convert package adds on top of the
certified stages:

* target resolution (release / schema / levels / content bbox) on our own
  acceptance output;
* the deterministic placement math (intent bbox, disjoint auto-offset,
  whole-intent translation);
* the family-edit vocabulary (captions from the file itself, spec-driven
  unit conversion, honest refusals) and the end-to-end prompt+RFA edit on
  one of OUR generated families;
* the stamps/quarantine classification.

The heavy end-to-end builds (prompt+RVT into a project; IFC merge) run the
full four-registry loader and are gated behind RVT_SKIP_LARGE=1 like the
other end-to-end suites; the recorded proofs live under
experiments/convert_combo/.
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.convert import add_to_project as A          # noqa: E402
from rvt.convert import modify_family as MFAM        # noqa: E402

ACCEPT_RVT = os.path.join(ROOT, "experiments", "frontdoor",
                          "ifc-electrical-room-2500a", "electrical-room-2500a.rvt")
OWN_RFA = os.path.join(ROOT, "experiments", "frontdoor",
                       "ifc-electrical-room-2500a", "families",
                       "dp1_eaton_prl2x_400a_42sp_480y_277.rfa")
IFC_ROOM = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")

# The heavy build-INTO-target tests use the SHARED, REGENERABLE acceptance
# fixture (the same file tests/test_convert.py self-calibrates against):
# sibling streams rebuild it through the CURRENT authoring path, so building
# into it must yield validator-0-errors -- the full-strength gate.  The
# ifc-electrical-room output above predates the fixed loader ordering (its
# own content now carries 2 pre-existing validator errors any build into it
# would inherit); it stays as the target for the READ-ONLY resolution checks
# only.  Expectations below derive from the fixture's actual inventory, never
# a pinned shape.
TARGET_RVT = os.path.join(ROOT, "experiments", "frontdoor",
                          "prompt-electrical-room", "electrical_room_prompt.rvt")

needs_accept = pytest.mark.skipif(not os.path.isfile(ACCEPT_RVT),
                                  reason="frontdoor acceptance output absent")
needs_target = pytest.mark.skipif(not os.path.isfile(TARGET_RVT),
                                  reason="shared acceptance fixture absent "
                                         "(regenerate via the frontdoor)")
needs_own_rfa = pytest.mark.skipif(not os.path.isfile(OWN_RFA),
                                   reason="generated .rfa absent")
skip_large = pytest.mark.skipif(os.environ.get("RVT_SKIP_LARGE") == "1",
                                reason="RVT_SKIP_LARGE=1")


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=100, spaces=42,
                                   voltage="480Y/277", mcb=False,
                                   mounting="surface", panel_name="X")
        return True
    except Exception:                                          # noqa: BLE001
        return False


needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")


# ---------------------------------------------------------------------------
# classification / stamps
# ---------------------------------------------------------------------------

def test_quarantined_input_classification():
    assert A.quarantined_input(os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt"))
    assert A.quarantined_input(os.path.join(ROOT, "vendor", "x", "y.rfa"))
    assert not A.quarantined_input(os.path.join(ROOT, "experiments", "x.rvt"))


# ---------------------------------------------------------------------------
# placement math over a real prompt intent (no build)
# ---------------------------------------------------------------------------

@needs_catalog
def test_bbox_offset_translate_roundtrip():
    from rvt.frontdoor import prompt_intent as PI
    model, parsed = PI.prompt_to_intent("a 100 A lighting panel and a 75 kVA transformer")
    assert model.room is None                      # equipment-only prompt
    mb0 = A.model_bbox_m(model)
    assert mb0 and mb0["x"][0] < mb0["x"][1]

    class T:                                       # minimal TargetInfo stand-in
        bbox_m = {"x": [-4.0, 6.0], "y": [-3.0, 3.0], "z": [0.0, 2.0]}
    dx, dy = A.auto_offset_m(T(), model, margin_m=2.0)
    assert dx == pytest.approx(6.0 - mb0["x"][0] + 2.0, abs=1e-6)

    before = [list(map(float, e.insertion_m)) for e in model.equipment]
    rec = A.translate_model(model, dx, dy, equip_dz_m=1.5)
    assert rec["equipment_translated"] == len(model.equipment)
    for b, e in zip(before, model.equipment):
        assert e.insertion_m[0] == pytest.approx(b[0] + dx, abs=1e-9)
        assert e.insertion_m[1] == pytest.approx(b[1] + dy, abs=1e-9)
        assert e.insertion_m[2] == pytest.approx(b[2] + 1.5, abs=1e-9)
    mb1 = A.model_bbox_m(model)
    assert mb1["x"][0] >= 6.0 + 2.0 - 1e-6         # disjoint east of the target


@needs_catalog
def test_translate_moves_room_walls_too():
    from rvt.frontdoor import prompt_intent as PI
    model, _ = PI.prompt_to_intent(
        "an electrical room 30x20 ft with a 100 A lighting panel")
    assert model.room is not None and model.room.walls
    p0_before = [list(map(float, w.p0_m)) for w in model.room.walls]
    A.translate_model(model, 10.0, -2.0)
    for b, w in zip(p0_before, model.room.walls):
        assert w.p0_m[0] == pytest.approx(b[0] + 10.0, abs=1e-9)
        assert w.p1_m[1] is not None


# ---------------------------------------------------------------------------
# target resolution on our own acceptance output
# ---------------------------------------------------------------------------

@needs_accept
def test_schema_mismatch_fails_red():
    from rvt.frontdoor import standalone as SA
    saved = dict(SA._SCHEMA_STATE)
    try:
        SA._SCHEMA_STATE.clear()
        SA._SCHEMA_STATE.update({"installed": True, "sha256": "f" * 64})
        with pytest.raises(A.ConvertError, match="differs"):
            A.ensure_target_schema(ACCEPT_RVT)
    finally:
        SA._SCHEMA_STATE.clear()
        SA._SCHEMA_STATE.update(saved)


@needs_accept
def test_resolve_target_acceptance_output():
    t = A.resolve_target(ACCEPT_RVT)
    assert t.release == 2026 and t.release_supported
    assert t.schema_sha256 and len(t.schema_sha256) == 64
    assert t.levels and t.n_walls >= 4
    assert t.bbox_m and t.bbox_m["x"][0] < t.bbox_m["x"][1]
    assert not t.quarantined
    j = t.as_json()
    assert j["release"] == 2026 and j["n_walls"] == t.n_walls

    lvl, elev = A.resolve_level(t, None)
    assert isinstance(lvl, int) and lvl > 0
    lvl2, _ = A.resolve_level(t, "1")
    assert isinstance(lvl2, int)
    with pytest.raises(A.ConvertError):
        A.resolve_level(t, "99")
    with pytest.raises(A.ConvertError):
        A.resolve_level(t, "no-such-level-name")


# ---------------------------------------------------------------------------
# the family-edit vocabulary (prompt + RFA)
# ---------------------------------------------------------------------------

@needs_own_rfa
def test_family_inventory_and_parse():
    inv = MFAM.inventory_family(OWN_RFA)
    caps = {p["caption"] for p in inv.params}
    assert {"BusRating", "Voltage", "PanelName", "NumberOfCircuits"} <= caps
    assert inv.type_names and inv.release == 2026
    assert not inv.quarantined

    parsed = MFAM.parse_family_edit(
        "rename the type to X1; set BusRating 225 A; set PanelName DP-9; "
        "set NumberOfCircuits 30", inv)
    ops = {o["op"]: o for o in parsed["ops"]}
    assert ops["rename-type"]["name"] == "X1"
    bus = [o for o in parsed["ops"] if o.get("caption") == "BusRating"][0]
    assert bus["value"] == 225.0 and bus["carrier"] == "m_value"
    pn = [o for o in parsed["ops"] if o.get("caption") == "PanelName"][0]
    assert pn["value"] == "DP-9" and pn["carrier"] == "m_str"
    nc = [o for o in parsed["ops"] if o.get("caption") == "NumberOfCircuits"][0]
    assert nc["value"] == 30 and nc["carrier"] == "m_int"


@needs_own_rfa
def test_family_edit_unit_conversions_and_refusals():
    inv = MFAM.inventory_family(OWN_RFA)
    # volts convert by the verified electrical factor (208 V -> 2238.89...)
    parsed = MFAM.parse_family_edit("set Voltage 208 V", inv)
    v = parsed["ops"][0]["value"]
    assert v == pytest.approx(2238.8933, abs=1e-3)
    # lengths REQUIRE a unit -- never guessed
    with pytest.raises(MFAM.FamilyEditError, match="unit"):
        MFAM.parse_family_edit("set Width 24", inv)
    parsed = MFAM.parse_family_edit("set Width 24 in", inv)
    assert parsed["ops"][0]["value"] == pytest.approx(2.0, abs=1e-9)
    # unknown parameter refuses, naming the real captions
    with pytest.raises(MFAM.FamilyEditError, match="BusRating"):
        MFAM.parse_family_edit("set Nonsense 12", inv)
    # nothing parseable refuses with the grammar
    with pytest.raises(MFAM.FamilyEditError, match="Grammar"):
        MFAM.parse_family_edit("do something nice", inv)


@needs_own_rfa
def test_family_edit_type_scoping():
    inv = MFAM.inventory_family(OWN_RFA)
    tname = inv.type_names[0]
    parsed = MFAM.parse_family_edit(f'set BusRating of type "{tname}" 300', inv)
    op = parsed["ops"][0]
    assert op["type_name"] == tname and op["value"] == 300.0
    with pytest.raises(MFAM.FamilyEditError, match="of type"):
        MFAM.parse_family_edit('set BusRating of type "No Such Type" 300', inv)
    # JSON form carries the scope too
    parsed = MFAM.parse_family_edit(json.dumps(
        [{"op": "set-param", "param": "BusRating", "value": "300",
          "type": tname}]), inv)
    assert parsed["ops"][0]["type_name"] == tname


@needs_own_rfa
def test_family_edit_json_forms():
    inv = MFAM.inventory_family(OWN_RFA)
    parsed = MFAM.parse_family_edit(
        json.dumps([{"op": "set-param", "param": "BusRating", "value": "225"},
                    {"op": "rename-type", "name": "Y2"}]), inv)
    assert parsed["source"] == "inline-json" and len(parsed["ops"]) == 2


@needs_own_rfa
def test_modify_family_end_to_end(tmp_path):
    rec = MFAM.modify_family(
        OWN_RFA, "rename the type to 225A MCB 42ckt T; set BusRating 225; "
                 "set MainsRating 225", str(tmp_path))
    d = rec["deliverables"]
    assert d and next(iter(d.values()))["bytes"] > 0
    g = rec["validation"]["rfa"]
    assert g["family_mode"]["verdict"] == "VALID"
    assert g["family_mode"]["n_errors"] == 0
    assert g["release"]["preserved"] is True
    assert all(r["ok"] for r in g["reread"])
    assert rec["apply"]["structural_ok"] is True
    # PartAtom followed the rename
    pa = rec["apply"].get("partatom") or {}
    assert pa.get("changed") is True


# ---------------------------------------------------------------------------
# heavy end-to-end (gated like the other suites)
# ---------------------------------------------------------------------------

@skip_large
@needs_target
@needs_catalog
def test_add_to_project_end_to_end(tmp_path):
    rec = A.add_to_project("add a 100 A lighting panel to my project",
                           TARGET_RVT, str(tmp_path), stem="t_add")
    assert rec["deliverables"], f"no deliverable: {rec.get('errors')}"
    g = rec["validation"]["combined"]
    assert g["validate"]["verdict"] == "VALID"
    assert g["validate"]["n_errors"] == 0
    assert g["census"]["coherent"] is True
    assert g["release"]["preserved"] is True
    kinds = {c["kind"] for c in rec["created"]}
    assert {"family(.rfa)", "equipment-instance", "loaded-family"} <= kinds
    # the addition landed clear of the target's content bbox
    tb = rec["target"]["bbox_m"]
    inst = [c for c in rec["created"] if c["kind"] == "equipment-instance"][0]
    assert inst["position_ft"][0] * 0.3048 > tb["x"][1]


@skip_large
@needs_target
@needs_catalog
@pytest.mark.skipif(not os.path.isfile(IFC_ROOM), reason="electrical-room IFC absent")
def test_merge_ifc_end_to_end(tmp_path):
    from rvt.convert import merge_ifc as MI
    import shutil
    tgt = str(tmp_path / "target.rvt")
    shutil.copyfile(TARGET_RVT, tgt)
    rec = MI.merge_ifc(IFC_ROOM, tgt, str(tmp_path / "out"), stem="t_merge")
    assert rec["deliverables"], f"no deliverable: {rec.get('errors')}"
    assert rec["created_ids"]
    for g in rec["validation"].values():
        assert g["validate"]["verdict"] == "VALID"
        assert g["release"]["preserved"] is True
    # self-calibrating inventory: whatever the IFC resolves must arrive whole
    # (per placed board one generated family and one loaded family; every
    # resolved wall appended)
    kinds = [c["kind"] for c in rec["created"]]
    n_eq = kinds.count("equipment-instance")
    assert n_eq >= 1
    assert kinds.count("family(.rfa)") == n_eq
    assert kinds.count("loaded-family") == n_eq
    assert kinds.count("wall") == rec["ifc"]["resolved_walls"]
    # disjoint: incoming content strictly east of the target bbox
    off = rec["placement"]["offset"]
    pre = rec["ifc"]["incoming_bbox_pre_offset_m"]
    tb = rec["target"]["bbox_m"]
    assert pre["x"][0] + off["dx_m"] >= tb["x"][1] - 1e-6

"""test_frontdoor.py -- THE MULTI-SURFACE FRONT DOOR (src/rvt/frontdoor,
tools/frontdoor.py) contract.

Fast, self-contained checks of the four things the front door adds:

* the GENESIS BASE REGISTRY: the pinned default resolves and hash-verifies,
  an Autodesk sample base is REFUSED, a pin mismatch is refused;
* the built-in PROMPT FALLBACK: the rules-first parser + the deterministic
  layout resolve the worked prompt into the SAME intent model the IFC
  route yields (tagging-contract dicts, room ring, feeder tree, family
  mapping), with an honest coverage report; and the PRIMARY handoff path
  (scene brief + PROMPT_TO_IFC.md);
* the OPEN-BUG DEGRADE logic (walls + loaded families): --strict = two
  files, default = one file + the PROOF-ONLY stamp, never a silent combo;
* the --rvt EDIT normalisation: text / ops.json / inline JSON -> the job
  runner's ops vocabulary, and the CLI's route validation.

One end-to-end fallback BUILD on the certified genesis base runs when the
base + specimen files are present (skip with RVT_SKIP_LARGE=1); the worked
examples under experiments/frontdoor/ are the recorded end-to-end proofs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor import base as B          # noqa: E402
from rvt.frontdoor import intent as FI       # noqa: E402
from rvt.frontdoor import edit as E          # noqa: E402
from rvt.frontdoor import manifest as MF     # noqa: E402
from rvt.frontdoor import prompt_intent as PP  # noqa: E402
import rvt.frontdoor as FD                   # noqa: E402

PROMPT = ("an electrical room 30x20 ft rated for 2500 A service with a main switchboard, "
          "two 400 A distribution panels and four lighting panels")

GENESIS = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "compose", "G_ABPD.rvt")
SPECIMENS = os.path.join(ROOT, "experiments", "genesis", "R5.rvt")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=400, spaces=42,
                                    voltage="480Y/277", mcb=True, mounting="surface",
                                    panel_name="X")
        return True
    except Exception:
        return False


needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")
needs_genesis = pytest.mark.skipif(
    not (os.path.exists(GENESIS) and os.path.exists(SPECIMENS)),
    reason="genesis base / specimen ancestor absent")


# ===========================================================================
# 1. genesis base registry
# ===========================================================================

def test_pin_record_shape():
    j = B.PIN.as_json()
    assert j["id"] and j["relpath"].endswith(".rvt")
    assert len(j["sha256"]) == 64
    assert "certification" in j and j["specimen_ancestor"]["relpath"].endswith(".rvt")
    assert "genesis" in j["relpath"] and "sample" not in j["relpath"].lower()


@pytest.mark.skipif(not os.path.exists(GENESIS), reason="pinned genesis base absent")
def test_pinned_base_resolves_and_verifies():
    rb = B.resolve_base(None)
    assert rb.pinned and rb.certified and not rb.is_autodesk_sample
    assert rb.sha256.lower() == B.PIN.base_sha256.lower()
    assert os.path.samefile(rb.path, GENESIS)


def test_autodesk_sample_base_is_refused(tmp_path):
    # a fake file named like a sample must be refused even if it exists
    fake = tmp_path / "rmebasicsampleproject.rvt"
    fake.write_bytes(b"x")
    with pytest.raises(B.BaseError):
        B.resolve_base(str(fake))
    assert B.is_autodesk_sample(str(fake))
    assert B.is_autodesk_sample("/firm/x/racbasicsampleproject.rvt")
    assert not B.is_autodesk_sample("/firm/seeds/karagitz-seed.rvt")


def test_missing_explicit_base_is_an_error(tmp_path):
    with pytest.raises(B.BaseError):
        B.resolve_base(str(tmp_path / "does-not-exist.rvt"))


def test_pin_mismatch_is_refused(tmp_path, monkeypatch):
    # a wrong-content file at the pinned repo path must be refused, not
    # silently accepted (monkeypatch the pin's candidate list)
    fake = tmp_path / "G_ABPD.rvt"
    fake.write_bytes(b"not the certified genesis base")
    monkeypatch.setattr(B.PIN.__class__, "candidate_paths",
                        lambda self, plugin_root=None: [str(fake)])
    monkeypatch.delenv("RVT_GENESIS_BASE", raising=False)
    with pytest.raises(B.BaseError) as ei:
        B.resolve_base(None)
    assert "MISMATCH" in str(ei.value)


def test_explicit_non_sample_base_accepted_unpinned(tmp_path):
    firm = tmp_path / "karagitz-seed.rvt"
    firm.write_bytes(b"a firm's own base bytes")
    rb = B.resolve_base(str(firm))
    assert rb.source == "explicit" and not rb.pinned and not rb.certified
    assert rb.warnings and "user's authority" in rb.warnings[0]


# --- --target-version when $RVT_GENESIS_BASE / --base IS our pinned default (#123, #24)
BUNDLED = os.path.join(ROOT, "plugin", "assets", "genesis")
needs_bundled_bases = pytest.mark.skipif(
    not all(os.path.isfile(os.path.join(BUNDLED, n))
            for n in ("G_ABPD.rvt", "G_ABPD_2025.rvt", "G_ABPD_2024.rvt")),
    reason="bundled per-release genesis bases absent")


@needs_bundled_bases
@pytest.mark.parametrize("year,name", [(2025, "G_ABPD_2025.rvt"), (2024, "G_ABPD_2024.rvt")])
def test_default_base_via_env_still_builds_natively_for_a_certified_target(monkeypatch, year, name):
    """The plugin bootstrap / legacy `--env` lines export RVT_GENESIS_BASE =
    the bundled DEFAULT (2026) base.  That is our own file arriving via a
    path, not a user override: a certified target must resolve ITS slot,
    never degrade to a 2026 file + a false 'pending certification' line."""
    monkeypatch.setenv("RVT_GENESIS_BASE", os.path.join(BUNDLED, "G_ABPD.rvt"))
    base, vb, errors = FD._resolve_base_and_version(
        FD.AuthorRequest(prompt="x", target_version=year))
    assert not errors, errors
    assert vb["status"] == "match" and vb["output_release"] == year, vb
    assert base is not None and os.path.basename(base.path) == name and base.certified
    assert os.environ.get("RVT_GENESIS_BASE", "").endswith("G_ABPD.rvt")   # env restored


@needs_bundled_bases
def test_default_base_via_env_with_an_uncertified_target_still_falls_back(monkeypatch):
    monkeypatch.setenv("RVT_GENESIS_BASE", os.path.join(BUNDLED, "G_ABPD.rvt"))
    base, vb, errors = FD._resolve_base_and_version(
        FD.AuthorRequest(prompt="x", target_version=2023))       # known, not certified
    assert vb["status"] == "fallback" and vb["output_release"] == 2026, vb
    assert "your Revit 2023 cannot open it" in vb["line"]
    assert vb["target_support"] == "known-not-certified" and vb["nearest_supported"] == 2024
    assert base is not None and os.path.basename(base.path) == "G_ABPD.rvt"


@needs_bundled_bases
def test_foreign_wrong_release_base_is_still_refused():
    """A --base that is NOT our default pin (here: the 2025 base) combined
    with a different target stays REFUSED -- never a wrong-release build."""
    base, vb, errors = FD._resolve_base_and_version(
        FD.AuthorRequest(prompt="x", target_version=2024,
                         base=os.path.join(BUNDLED, "G_ABPD_2025.rvt")))
    assert base is None and vb["status"] == "refused" and errors


# ===========================================================================
# 2. prompt fallback: parser, layout, intent, coverage
# ===========================================================================

@needs_catalog
def test_worked_prompt_parses_room_and_equipment():
    parsed = PP.parse_prompt(PROMPT)
    r = parsed.room
    assert r is not None and r.walls
    assert abs(r.width_m - 9.144) < 1e-6 and abs(r.depth_m - 6.096) < 1e-6
    assert r.service_rating_a == 2500.0
    assert r.service_voltage == "480Y/277"
    kinds = [it.kind for it in parsed.buildable_items]
    assert kinds.count("switchboard") == 1
    assert kinds.count("distribution_panelboard") == 2
    assert kinds.count("lighting_panelboard") == 4
    dps = [it for it in parsed.items if it.kind == "distribution_panelboard"]
    assert all(it.rating_a == 400.0 for it in dps)
    assert not parsed.coverage.ignored_words
    assert not parsed.unbuilt


@needs_catalog
def test_worked_prompt_intent_model_matches_ifc_route_shape():
    model, parsed = PP.prompt_to_intent(PROMPT)
    # the ONE intent model class
    assert isinstance(model, FI.IntentModel)
    tags = [e.tag for e in model.equipment]
    assert tags == ["MSB", "DP-1", "DP-2", "LP-1", "LP-2", "LP-3", "LP-4"]
    # tagging-contract dicts, same keys the IFC resolver produces
    dp = next(e for e in model.equipment if e.tag == "DP-1")
    for key in ("PanelName", "Voltage", "Phases", "Wires", "BusRating",
                "MainsType", "NumberOfCircuits", "MainsRating", "_voltage"):
        assert key in dp.contract, key
    assert dp.contract["_voltage"]["system"] == "480Y/277"
    assert dp.contract["MainsType"] == "Main breaker"
    # room: closed 4-wall CCW ring centred at the origin
    assert model.room and len(model.room.walls) == 4
    ext = model.room.clear["centerline_extents_m"]
    assert abs(ext["x"][1] - 4.572) < 1e-6 and abs(ext["y"][1] - 3.048) < 1e-6
    # every equipment inside the ring
    assert model.audit["equipment_inside_room_ring"] == "7/7"
    assert model.audit["positions_all_zero"] is False
    # feeder tree: MSB feeds both DPs; LPs ride on the DPs; UTILITY service root
    pairs = {(ed.source, ed.target) for ed in model.feeders}
    assert ("MSB", "DP-1") in pairs and ("MSB", "DP-2") in pairs
    assert ("UTILITY", "MSB") in pairs
    assert any(t.startswith("LP-") for (_s, t) in pairs)
    # family mapping through the SAME resolver: switchboard = house, panels resolved
    st = {p.tag: p.status for p in model.family_plans}
    assert st["MSB"] == "house"
    assert all(st[t] == "resolved" for t in ("DP-1", "DP-2", "LP-1", "LP-2", "LP-3", "LP-4"))
    dp_plan = next(p for p in model.family_plans if p.tag == "DP-1")
    assert dp_plan.constructor.endswith("make_panelboard") and dp_plan.variant == "PRL2X"
    # catalog facts replaced the prompt-default dims
    assert abs(dp.dims_m["w"] - 0.508) < 1e-6


@needs_catalog
def test_intent_json_serialises_like_the_ifc_route(tmp_path):
    from rvt.ifc import intent as I
    model, _ = PP.prompt_to_intent(PROMPT)
    p = tmp_path / "intent.json"
    FI.write_intent_json(model, str(p))
    d = json.loads(p.read_text())
    assert d["specVersion"] == I.INTENT_VERSION
    for k in ("levels", "walls", "equipment", "room", "feederTree", "familyMapping", "audit"):
        assert k in d
    assert len(d["equipment"]) == 7 and len(d["walls"]) == 4


@needs_catalog
def test_coverage_reports_unbuilt_and_defaults():
    prompt = ("electrical room 30 by 20 feet with a 1600A switchboard, "
              "twelve 2x4 LED troffers and no feeders")
    model, parsed = PP.prompt_to_intent(prompt)
    cov = parsed.coverage
    assert any(n["kind"] == "luminaire" for n in cov.not_built)
    assert cov.defaults_applied                      # heights, voltages ... stated
    assert model.feeders == []                       # 'no feeders' honoured
    assert model.other_products and model.other_products[0]["kind"] == "luminaire"


def test_prompt_without_anything_buildable_errors():
    with pytest.raises(PP.PromptError):
        PP.parse_prompt("please make me something nice")
    with pytest.raises(PP.PromptError):
        PP.parse_prompt("")


@needs_catalog
def test_equipment_only_prompt_has_no_room_shell():
    model, parsed = PP.prompt_to_intent("a 150 kVA transformer and a 225 A 208Y/120 "
                                        "receptacle panel")
    assert model.room is None
    kinds = sorted(e.kind for e in model.equipment)
    assert kinds == ["receptacle_panelboard", "transformer"]
    t1 = next(e for e in model.equipment if e.kind == "transformer")
    assert t1.contract.get("RatingkVA") == 150.0
    # the transformer secondary feeds the low-voltage panel
    assert any(ed.source == t1.tag and ed.target == "RP-1" for ed in model.feeders)


@needs_catalog
def test_room_noun_is_never_equipment():
    # 'switchgear room' names a PLACE, not a switchboard
    _model, parsed = PP.prompt_to_intent("switchgear room 40'x25' with two 3000 amp "
                                         "switchboards and no feeders")
    boards = [it for it in parsed.items if it.kind == "switchboard"]
    assert len(boards) == 2 and {b.rating_a for b in boards} == {3000.0}


@needs_catalog
def test_service_voltage_not_polluted_by_branch_panel_voltage():
    _m, parsed = PP.prompt_to_intent("a 45x30 ft electrical room with a 4000 A switchboard "
                                     "and two 208Y/120V receptacle panels")
    assert parsed.room.service_voltage == "480Y/277"


# ===========================================================================
# 3. the PRIMARY prompt path: scene brief + handoff
# ===========================================================================

@needs_catalog
def test_scene_brief_carries_tagging_contract(tmp_path):
    model, parsed = PP.prompt_to_intent(PROMPT)
    brief = PP.scene_brief(PROMPT, parsed=parsed, model=model)
    assert brief["ifcMeta"]["storeys"] and brief["ifcMeta"]["guidSeed"]
    assert brief["room"]["walls"] and len(brief["room"]["walls"]) == 4
    tags = [p["tag"] for p in brief["products"]]
    assert tags == ["MSB", "DP-1", "DP-2", "LP-1", "LP-2", "LP-3", "LP-4"]
    dp = next(p for p in brief["products"] if p["tag"] == "DP-1")
    ui = dp["userData_ifc"]
    assert ui["ifcClass"] == "IFCELECTRICDISTRIBUTIONBOARD"
    props = ui["psets"][0]["props"]
    assert ui["psets"][0]["name"] == "PanelSchedule"
    for k in ("PanelName", "Voltage", "BusRating", "MainsType", "NumberOfCircuits", "FedFrom"):
        assert k in props, k
    assert props["Voltage"]["type"] == "voltage" and props["BusRating"]["type"] == "current"
    assert props["FedFrom"] == "MSB"
    # the handoff package on disk
    hp = PP.write_handoff(PROMPT, str(tmp_path), parsed=parsed, model=model)
    for k in ("scene_brief", "handoff", "instructions"):
        assert os.path.isfile(hp[k])
    md = open(hp["instructions"]).read()
    assert "toIfc(THREE, model" in md and "author --ifc" in md


def test_prompt_to_ifc_doc_ships_with_the_package():
    p = PP.handoff_instructions_path()
    assert os.path.isfile(p)
    txt = open(p).read()
    for needle in ("PanelSchedule", "SwitchboardSchedule", "TransformerSchedule",
                   "userData.ifc", "IFCELECTRICDISTRIBUTIONBOARD"):
        assert needle in txt


# ===========================================================================
# 4. the OPEN-CELL degrade (placed instances of OUR families on OUR composed
#    base -- genesis-audit #48 / issue #16; walls + loaded families PASS)
# ===========================================================================

@needs_catalog
def test_combination_detected_and_degraded():
    """The truth table keys on PLACED INSTANCES on a composed base (#142)."""
    model, _ = PP.prompt_to_intent(PROMPT)          # walls + families + 7 instances
    v = FI.combination_check(model)                 # default: pinned/composed base, E on
    assert v.triggers_open_bug and v.mode == "stamp-proof-only"
    assert v.stamp == FI.OPEN_CELL_STAMP
    assert "generated-family INSTANCES on a composed genesis base" in v.stamp
    assert "genesis-audit.md #48" in v.stamp and "issue #16" in v.stamp
    assert v.places_instances and v.n_instances == 7 and v.composed_base
    assert v.files == ["combined"]
    vs = FI.combination_check(model, strict=True)   # --strict
    assert vs.triggers_open_bug and vs.mode == "split-strict"
    assert vs.stamp is None and vs.files == ["shell", "equipment"]
    assert "walls + the 7 loaded families, NO placement" in vs.reason   # shell = WF_fix shape
    assert "PLACED instances" in vs.reason                              # equipment = the cell
    j = vs.as_json()
    assert j["open_bug"] == FI.OPEN_BUG_ID and j["open_bug_text"]
    assert j["n_instances"] == 7 and j["places_instances"] is True
    # equipment-only (no room, no walls) STILL exercises the open cell
    equip_only, _ = PP.prompt_to_intent("six 225A panelboards")
    ve = FI.combination_check(equip_only)
    assert not ve.has_walls and ve.has_loaded_families
    assert ve.triggers_open_bug and ve.mode == "stamp-proof-only"
    assert ve.stamp == FI.OPEN_CELL_STAMP and ve.n_instances == 6
    ves = FI.combination_check(equip_only, strict=True)
    assert ves.mode == "split-strict" and ves.files == ["shell", "equipment"]


@needs_catalog
def test_no_combination_when_walls_or_families_only():
    """No instance placed on a composed base -> single, no open-cell stamp:
    walls only, walls + LOADED families without placement (--stages FLWV, the
    WF_fix / WF_nofix certified shape), and instances on a NON-composed host."""
    walls_only, _ = PP.prompt_to_intent("an electrical room 9.2m x 6.2m")
    v = FI.combination_check(walls_only)
    assert not v.triggers_open_bug and v.mode == "single" and v.has_walls
    assert v.stamp is None and not v.places_instances
    room, _ = PP.prompt_to_intent(PROMPT)           # walls + loadable families
    v1 = FI.combination_check(room, stages="FLWV")  # loaded, NOT placed
    assert v1.has_walls and v1.has_loaded_families
    assert not v1.triggers_open_bug and v1.mode == "single" and v1.stamp is None
    assert v1.n_instances == 0 and not v1.places_instances
    assert "WITHOUT placement" in v1.reason and "WF_fix" in v1.reason
    v1s = FI.combination_check(room, strict=True, stages="FLWV")   # strict is moot here
    assert v1s.mode == "single" and v1s.files == ["combined"]
    fams_only, _ = PP.prompt_to_intent("a 150 kVA transformer and a 225 A 208Y/120 "
                                          "receptacle panel")
    v2 = FI.combination_check(fams_only, strict=True, stages="FLV")   # load only
    assert not v2.triggers_open_bug and v2.mode == "single" and v2.has_loaded_families
    # instances on a host that is NOT our composed base (pristine host: T1r/T1u/U16 PASS)
    v3 = FI.combination_check(fams_only, composed_base=False)
    assert v3.places_instances and v3.n_instances == 2
    assert not v3.triggers_open_bug and v3.mode == "single" and v3.stamp is None
    assert "NOT the composed genesis base" in v3.reason


@needs_catalog
def test_refused_plans_are_not_counted_as_loadable():
    # 800 A distribution panelboards have no catalog sizing row -> refused
    model, _ = PP.prompt_to_intent("electrical room 40x30 ft with three 800A distribution "
                                    "panelboards")
    st = {p.tag: p.status for p in model.family_plans}
    assert all(v == "refused" for v in st.values())
    assert FI.buildable_family_plans(model) == []
    v = FI.combination_check(model)
    assert not v.triggers_open_bug and not v.has_loaded_families and v.has_walls


@needs_catalog
def test_intent_summary_shape():
    model, _ = PP.prompt_to_intent(PROMPT)
    s = FI.summarize(model)
    assert s["equipment_total"] == 7
    assert s["equipment_by_kind"]["lighting_panelboard"] == 4
    assert s["room"]["walls"] == 4 and s["room"]["ring_ccw"] is True
    assert s["family_plans_by_status"] == {"house": 1, "resolved": 6}


# ===========================================================================
# 5. --rvt edit normalisation
# ===========================================================================

def test_edit_spec_inline_json_and_file(tmp_path):
    spec = E.parse_edit_spec('[{"op": "move", "id": 42, "to": [1, 2, 3]}]')
    assert spec.source == "inline-json" and spec.ops[0]["op"] == "move"
    spec2 = E.parse_edit_spec('{"ops": [{"op": "delete", "id": 7, "cascade": true}]}')
    assert spec2.ops[0]["op"] == "delete"
    p = tmp_path / "ops.json"
    p.write_text(json.dumps({"ops": [{"op": "retype", "id": 5, "symbol": 9}]}))
    spec3 = E.parse_edit_spec(str(p))
    assert spec3.source == "ops-file" and spec3.ops[0]["op"] == "retype"


def test_edit_spec_text_with_ids_needs_no_doc():
    spec = E.parse_edit_spec("delete 1466502 with cascade; move 742670 to 3, 4, 0 ft "
                             "rotation 90 deg; set level 311 elevation to 12 ft; "
                             "retype 1466502 to symbol 619617; move #742670 by 1,0,0 m")
    ops = spec.ops
    assert spec.source == "text" and len(ops) == 5
    assert ops[0] == {"op": "delete", "id": 1466502, "cascade": True}
    assert ops[1]["op"] == "move" and ops[1]["to"] == [3.0, 4.0, 0.0]
    assert ops[1]["rotation_deg"] == 90.0
    assert ops[2] == {"op": "set-level", "id": 311, "elevation_ft": 12.0}
    assert ops[3] == {"op": "retype", "id": 1466502, "symbol": 619617}
    assert ops[4]["delta"] and abs(ops[4]["delta"][0] - 3.28084) < 1e-3   # metres -> feet


def test_edit_spec_garbage_raises():
    with pytest.raises(E.EditParseError):
        E.parse_edit_spec("please tidy the whole model up somehow")
    with pytest.raises(E.EditParseError):
        E.parse_edit_spec("")
    with pytest.raises(E.EditParseError):
        E.parse_edit_spec("[not json")


@pytest.mark.skipif(not os.path.exists(RST), reason="samples/rstbasicsampleproject.rvt missing")
def test_edit_spec_text_resolves_names_against_a_file():
    from rvt.mutate import Document
    doc = Document.from_file(RST)
    ed = E.editables(doc)
    assert ed["levels"], "expected levels in the sample"
    lvl = next(l for l in ed["levels"] if l.get("name"))
    spec = E.parse_edit_spec(f"set level {lvl['name']} elevation to 4.5 m", doc=doc)
    assert spec.ops[0]["op"] == "set-level" and spec.ops[0]["id"] == lvl["id"]
    assert spec.ops[0]["elevation_m"] == 4.5
    with pytest.raises(E.EditParseError):
        E.resolve_ref(doc, "definitely-not-an-element-name-xyz")


# ===========================================================================
# 6. CLI + entrypoint validation
# ===========================================================================

def _cli():
    p = os.path.join(ROOT, "tools", "frontdoor.py")
    spec = importlib.util.spec_from_file_location("frontdoor_cli", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules["frontdoor_cli"] = m
    spec.loader.exec_module(m)
    return m


def test_route_validation():
    with pytest.raises(FD.FrontDoorError):
        FD.AuthorRequest().route()
    with pytest.raises(FD.FrontDoorError):
        FD.AuthorRequest(prompt="x", ifc="y.ifc").route()
    with pytest.raises(FD.FrontDoorError):
        FD.AuthorRequest(rvt="a.rvt").route()          # --rvt needs --edit
    assert FD.AuthorRequest(prompt="x").route() == "prompt"
    assert FD.AuthorRequest(ifc="y.ifc").route() == "ifc"
    assert FD.AuthorRequest(rvt="a.rvt", edit="delete 1").route() == "rvt"


def test_cli_usage_errors_exit_2():
    cli = _cli()
    assert cli.main(["author"]) == cli.EX_USAGE                      # no input
    assert cli.main(["author", "--rvt", "x.rvt"]) == cli.EX_USAGE    # no --edit
    assert cli.main(["author", "--prompt", "a", "--ifc", "b.ifc"]) == cli.EX_USAGE


def test_cli_missing_ifc_file_reports_failure(tmp_path):
    cli = _cli()
    rc = cli.main(["author", "--ifc", str(tmp_path / "nope.ifc"), "--out", str(tmp_path / "o"),
                   "--json"])
    assert rc == cli.EX_INCOMPLETE


@needs_catalog
def test_handoff_only_route_writes_the_package(tmp_path):
    r = FD.author(prompt=PROMPT, out=str(tmp_path / "job"), handoff_only=True)
    assert r.route == "prompt"
    assert r.status.startswith("HANDOFF-ONLY")
    for k in ("scene_brief", "handoff", "instructions"):
        assert k in r.handoff
    assert os.path.isfile(os.path.join(str(tmp_path / "job"), "intent.json"))
    man = json.loads((tmp_path / "job" / "manifest.json").read_text())
    assert man["route"] == "prompt" and man["prompt_coverage"] is not None
    assert man["base"]["pin"]["id"] == B.PIN.base_id
    assert man["intent"]["summary"]["equipment_total"] == 7
    assert (tmp_path / "job" / "MANIFEST.md").exists()


def test_manifest_crud_and_honesty_shape():
    files = {"combined": None}
    created = [
        {"kind": "wall", "tag": "W-N", "elem_id": 1001, "file_role": "W"},
        {"kind": "equipment-instance", "tag": "DP-1", "elem_id": 1002, "file_role": "E"},
        {"kind": "family(.rfa)", "tag": "DP-1", "name": "fam"},
        {"kind": "loaded-family", "tag": "DP-1"},
    ]
    crud = MF.crud_affordances(files, created)
    tags = [r["tag"] for r in crud["elements"]]
    assert tags == ["W-N", "DP-1"]                     # rfa / loaded rows have no elem_id
    dp = next(r for r in crud["elements"] if r["tag"] == "DP-1")
    assert set(dp["modify"]) >= {"move", "retype", "delete"}
    assert "rename / set-mark" in dp["not_available"]
    assert dp["modify"]["delete"]["op"] == {"op": "delete", "id": 1002, "cascade": True}
    cov = MF.coverage_cross_reference(created)
    cells = {(c["category"], c["verb"]) for c in cov["cells_exercised"]}
    assert ("walls", "create") in cells and ("electrical_equipment", "create") in cells
    hon = MF._honesty(None, {"stamp": FI.OPEN_CELL_STAMP})
    assert hon["proof_only_stamps"] == [FI.OPEN_CELL_STAMP]
    assert "NOT claimed" in hon["tiers"]["autodesk_acceptance"]


# ===========================================================================
# 7. end-to-end fallback build on the certified genesis base (slow-ish)
# ===========================================================================

@needs_catalog
@needs_genesis
@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("RVT_SKIP_LARGE") == "1",
                    reason="RVT_SKIP_LARGE=1")
def test_e2e_prompt_fallback_builds_on_genesis_base(tmp_path):
    """The whole chain: prompt -> intent -> families -> LOAD onto the pinned
    genesis base -> walls -> instances -> gates -> manifest, default degrade
    mode (one combined file + the open-cell PROOF-ONLY stamp: 7 instances of
    OUR families placed on the composed base)."""
    out = tmp_path / "e2e"
    r = FD.author(prompt=PROMPT, out=str(out), no_handoff=True)
    assert r.route == "prompt", r.errors
    assert r.ok, (r.status, r.errors)
    man = r.manifest
    build = man["build"]
    v = build["combination_verdict"]
    assert v["mode"] == "stamp-proof-only"
    assert v["stamp"] == FI.OPEN_CELL_STAMP
    assert v["places_instances"] is True and v["composed_base"] is True
    assert "combined" in build["files"]
    combined = build["files"]["combined"]["path"]
    assert os.path.isfile(combined)
    # self-checks all green on the combined file
    g = build["validation"]["combined"]
    assert g["validate"]["verdict"] == "VALID" and g["validate"]["n_errors"] == 0
    assert g["census"].get("coherent") is not False
    assert g["identity"]["status"] == "PASS"
    assert g["self_checks_ok"] is True
    # created: 4 walls + 7 instances (+ 7 rfa + 7 loaded families)
    kinds = [c["kind"] for c in build["elements_created"]]
    assert kinds.count("wall") == 4
    assert kinds.count("equipment-instance") == 7
    assert kinds.count("family(.rfa)") == 7
    # circuits honestly blocked, not faked
    assert build["circuits"].get("blocker")
    # the honesty box carries both PROOF-ONLY tiers
    assert man["honesty"]["proof_only_stamps"]
    # CRUD affordances point at the emitted file
    assert man["crud"]["elements"], "expected editable elements"
    # base recorded as the pinned, certified genesis base
    assert man["base"]["pinned"] is True and man["base"]["certified_genesis_base"] is True
    assert man["base"]["is_autodesk_sample"] is False


@needs_catalog
@needs_genesis
@pytest.mark.slow
@pytest.mark.skipif(os.environ.get("RVT_SKIP_LARGE") == "1",
                    reason="RVT_SKIP_LARGE=1")
def test_e2e_strict_split_and_rvt_edit(tmp_path):
    """--strict emits shell + equipment (each self-checks PASS); the --rvt
    route then edits the equipment file (move + delete) through the
    certified edit pipeline."""
    from rvt.mutate import Document
    out = tmp_path / "strict"
    r = FD.author(prompt=PROMPT, out=str(out), no_handoff=True, strict=True)
    assert r.ok, (r.status, r.errors)
    files = r.manifest["build"]["files"]
    assert set(files) == {"shell", "equipment"}
    for role in ("shell", "equipment"):
        g = r.manifest["build"]["validation"][role]
        assert g["self_checks_ok"] is True, (role, g)
    shell = Document.from_file(files["shell"]["path"])
    equip = Document.from_file(files["equipment"]["path"])
    assert len(shell.ids_of_class("SWall")) == 4 and not shell.ids_of_class("FamilyInstance")
    assert len(equip.ids_of_class("FamilyInstance")) == 7 and not equip.ids_of_class("SWall")
    # --- edit the equipment file: move DP-1, delete LP-4 -------------------
    r2 = FD.author(rvt=files["equipment"]["path"],
                   edit="move DP-1 to 3,1,4.66; delete LP-4 with cascade",
                   out=str(tmp_path / "edit"))
    assert r2.route == "rvt" and r2.ok, (r2.status, r2.errors)
    ops = r2.manifest["edit"]["spec"]["ops"]
    assert [o["op"] for o in ops] == ["move", "delete"]
    assert r2.manifest["edit"]["hard_gates_passed"] is True
    edited = Document.from_file(r2.files["edited"])
    assert len(edited.ids_of_class("FamilyInstance")) == 6

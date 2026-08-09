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


ROOM = "an electrical room 20x15 ft with "


def _tags(prompt):
    parsed = PP.parse_prompt(prompt)
    return parsed, [(it.tag, it.kind) for it in parsed.items]


@pytest.mark.parametrize("clause,expect", [
    ("one 100 A lighting panel LP-1", [("LP-1", "lighting_panelboard")]),
    ("one 100 A lighting panel named LP-1", [("LP-1", "lighting_panelboard")]),
    ("one 100 A lighting panel", [("LP-1", "lighting_panelboard")]),
    ("a 400 A distribution panel DP-1", [("DP-1", "distribution_panelboard")]),
    ("a main switchboard MSB and two lighting panels",
     [("MSB", "switchboard"), ("LP-1", "lighting_panelboard"), ("LP-2", "lighting_panelboard")]),
    ("one 75 kVA transformer T1", [("T1", "transformer")]),
])
def test_naming_the_tag_is_one_item_not_two(clause, expect):
    # #101: 'lighting panel LP-1' is ONE panel tagged LP-1 -- the 'lp' inside
    # the tag must never re-match as a second lighting panel
    parsed, got = _tags(ROOM + clause)
    assert got == expect
    tags = [t for t, _k in got]
    assert len(set(tags)) == len(tags)                       # never two items, one tag
    eq = [u for u in parsed.coverage.understood if u["as"] == "equipment"]
    assert sum(u["count"] for u in eq) == len(expect)
    assert not parsed.coverage.ignored_words                 # the tag was consumed, not ignored


def test_named_tags_are_understood_as_tags_in_coverage():
    parsed, got = _tags(ROOM + "two 100 A lighting panels LP-1 and LP-2")
    assert got == [("LP-1", "lighting_panelboard"), ("LP-2", "lighting_panelboard")]
    assert all(it.rating_a == 100.0 for it in parsed.items)
    cov = parsed.coverage.understood
    eq = [u for u in cov if u["as"] == "equipment"]
    assert len(eq) == 1 and eq[0]["count"] == 2 and eq[0]["tags"] == ["LP-1", "LP-2"]
    tg = [u for u in cov if u["as"] == "equipment tag"]
    assert len(tg) == 1 and tg[0]["tags"] == ["LP-1", "LP-2"] and tg[0]["clause"] == "LP-1 and LP-2"
    # an uncounted plural takes its count from the tags it names
    _p, got = _tags(ROOM + "lighting panels LP-1, LP-2 and LP-3")
    assert [t for t, _k in got] == ["LP-1", "LP-2", "LP-3"]
    # an explicit count WINS over the number of tags named
    _p, got = _tags(ROOM + "three lighting panels LP-1 and LP-2")
    assert [t for t, _k in got] == ["LP-1", "LP-2", "LP-3"]


def test_unnamed_counts_and_references_unchanged():
    # guards: plain counts number exactly as before ...
    _p, got = _tags(PROMPT)
    assert [t for t, _k in got] == ["MSB", "DP-1", "DP-2", "LP-1", "LP-2", "LP-3", "LP-4"]
    _p, got = _tags("an electrical room with 6 panels")
    assert [t for t, _k in got] == [f"PP-{i}" for i in range(1, 7)]
    _p, got = _tags(ROOM + "an MDP and two LPs")             # abbreviations stay NOUNS
    assert got == [("DP-1", "distribution_panelboard"),
                   ("LP-1", "lighting_panelboard"), ("LP-2", "lighting_panelboard")]
    # ... a later REFERENCE to a tag is not another piece of equipment ...
    parsed, got = _tags(ROOM + "one distribution panel and one lighting panel, LP-1 fed from DP-1")
    assert got == [("DP-1", "distribution_panelboard"), ("LP-1", "lighting_panelboard")]
    assert parsed.feeders == [("DP-1", "LP-1")]
    # ... and bare tags alone still stand for one item each, carrying that tag
    _p, got = _tags(ROOM + "LP-1 and LP-2")
    assert got == [("LP-1", "lighting_panelboard"), ("LP-2", "lighting_panelboard")]
    # an explicit tag is never re-issued by auto-numbering (which carries on
    # from the named ordinal: LP-2, then LP-3)
    _p, got = _tags(ROOM + "one lighting panel LP-2 and one more lighting panel")
    assert [t for t, _k in got] == ["LP-2", "LP-3"]


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


# ===========================================================================
# 8. stage P: the JOB's identity in ProjectInfo (issue #148) -- runs on the
#    pinned bases shipped in plugin/assets/genesis (no samples/ needed)
# ===========================================================================

from rvt.frontdoor import project_info as PI                # noqa: E402
from rvt.identity import PRODUCT_AUTHOR_PLACEHOLDER          # noqa: E402

PINNED = {2026: os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt"),
          2025: os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2025.rvt"),
          2024: os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2024.rvt")}
BASE_PLACEHOLDERS = ("rev-revit", "Genesis Base", "GENESIS Base", "Genesis Baseline", "GEN-0000")
needs_pinned = pytest.mark.skipif(not all(os.path.isfile(p) for p in PINNED.values()),
                                  reason="bundled genesis bases missing")


class _FakeIntent:
    project_name = "Riverside Clinic"


def test_project_identity_maps_the_ten_builtin_params(monkeypatch):
    from dataclasses import replace
    from rvt.genesis import house_standard as HS
    ident = PI.identity_from_intent(_FakeIntent(), issue_date="2026-08-09")
    assert ident.project_name == "Riverside Clinic"
    assert ident.project_status == PI.PROJECT_STATUS_PROOF_ONLY == "PROOF-ONLY"
    assert ident.author == PRODUCT_AUTHOR_PLACEHOLDER          # hard rule 6
    # the same ten fields the genesis constructor authors, one BIP each
    assert set(PI.FIELD_PARAMS) == set(HS.PROJECT_INFO) and len(set(PI.FIELD_PARAMS.values())) == 10
    params = replace(ident, project_number="RC-01", client_name="Riverside Health").params()
    assert set(params) == set(PI.FIELD_PARAMS.values())
    assert params[-1006317] == "Riverside Clinic" and params[-1006316] == "RC-01"
    assert params[-1006319] == "Riverside Health" and params[-1006320] == "PROOF-ONLY"
    assert params[-1006321] == "2026-08-09" and params[-1019008] == PRODUCT_AUTHOR_PLACEHOLDER
    assert params[-1019005] == "" and params[-1019007] == ""   # unknown -> blank, never a placeholder
    # the issue date is the build date: SOURCE_DATE_EPOCH pins it, else today (UTC)
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1780000000")      # 2026-05-28T..Z
    assert PI.build_date() == "2026-05-28"
    assert PI.identity_from_intent(_FakeIntent()).issue_date == "2026-05-28"
    monkeypatch.delenv("SOURCE_DATE_EPOCH")
    assert PI.build_date(now=0) == "1970-01-01"
    assert len(PI.build_date()) == 10


@needs_pinned
@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_stage_p_edits_only_projectinfo_and_is_deterministic(tmp_path, release):
    """On each pinned base: the ten strings land on the singleton ProjectInfo,
    that record is the ONLY element whose bytes change (nothing added or
    removed), no base placeholder survives, and two runs are byte-identical."""
    from rvt.mutate import Document
    from rvt import manipulate as M
    from rvt import reduce_law as RL
    from rvt.frontdoor import release_ctx as RC
    base = PINNED[release]
    ident = PI.ProjectIdentity(project_name="Riverside Clinic", issue_date="2026-08-09",
                               project_number="RC-01", client_name="Riverside Health",
                               building_name="Clinic Block A")
    out1, out2 = str(tmp_path / "p1.rvt"), str(tmp_path / "p2.rvt")
    with RC.release_build_context(base):
        rec = PI.stage_project_info(base, out1, ident)
        assert rec["ok"] is True, rec
        assert rec["after"] == ident.as_json() and not rec["mismatch"]
        assert rec["before"]["project_name"] != ident.project_name      # it really changed
        assert rec["commit"]["replaced"] == [[102, rec["elem_id"]]]
        assert rec["commit"]["elemtable_count_before"] == rec["commit"]["elemtable_count_after"]
        # the certified modify shape's structural proof, under the file's own release
        v = M.verify_manipulated(out1, edited_ids=[rec["elem_id"]])
        assert v["stamps_ok"] and v["crc_failures"] == 0 and v["walker_errors"] == 0, v
        assert v["ecc_mismatches"] == 0 and v["unit0_ids_equal_elemtable"] is True, v
        assert v["edited"][str(rec["elem_id"])]["102"] == {"class": "ProjectInfo", "clean": True}
        # the Document record diff: exactly one pre-existing element modified, seq 102
        diff = RL.element_diff(Document.from_file(base), Document.from_file(out1))
        assert not diff.removed and not diff.added, (diff.removed, diff.added)
        assert diff.modified == {rec["elem_id"]: [102]}, diff.modified
        got = PI.read_project_info(Document.from_file(out1))
        assert got["fields"] == ident.as_json()
        assert not [v for v in got["params"].values() for p in BASE_PLACEHOLDERS if p in str(v)]
        # deterministic: same base + same identity -> the same bytes
        assert PI.stage_project_info(base, out2, ident)["ok"] is True
    with open(out1, "rb") as a, open(out2, "rb") as b:
        assert a.read() == b.read()


@pytest.fixture(scope="module")
def identity_job(tmp_path_factory):
    if not os.path.isfile(PINNED[2026]):
        pytest.skip("bundled genesis base missing")
    out = str(tmp_path_factory.mktemp("pi") / "job")
    return FD.author(prompt="an electrical room with 1 panel", out=out, no_handoff=True)


def test_e2e_prompt_output_carries_the_job_identity(identity_job):
    """The product shape: a prompt job's combined .rvt decodes with the
    intent's project name, PROOF-ONLY status, today's issue date and OUR
    author placeholder; the manifest says what was written."""
    from rvt.mutate import Document
    r = identity_job
    assert r.ok, (r.status, r.errors)
    build = r.manifest["build"]
    pi = build["project_info"]
    assert pi["ok"] is True and pi["elem_id"] and not pi["mismatch"], pi
    assert pi["commit"]["replaced"] == [[102, pi["elem_id"]]]
    assert [s["stage"] for s in build["stages"]][0] == "P"
    combined = build["files"]["combined"]["path"]
    got = PI.read_project_info(Document.from_file(combined))
    f = got["fields"]
    assert f["project_name"] == r.manifest["intent"]["summary"]["project"] == "Electrical Room"
    assert f["project_status"] == "PROOF-ONLY" and "PROOF-ONLY" in r.status
    assert f["author"] == PRODUCT_AUTHOR_PLACEHOLDER
    assert f["issue_date"] == pi["identity"]["issue_date"] == PI.build_date()
    assert f == pi["after"]
    assert not [v for v in got["params"].values() for p in BASE_PLACEHOLDERS if p in str(v)]
    assert build["validation"]["combined"]["validate"]["n_errors"] == 0
    with open(r.manifest_paths["md"], encoding="utf-8") as fh:
        assert "project information (ProjectInfo" in fh.read()


def test_e2e_rename_and_set_mark_on_our_own_output(identity_job, tmp_path):
    """Issue #186: the two most natural follow-up edits -- rename the panel,
    set its Mark -- succeed on a prompt-built project whose placed instance
    carries no param rows at all (set_param upserts the AString rows)."""
    from rvt import manipulate as M
    from rvt.mutate import Document
    r = identity_job
    assert r.ok, (r.status, r.errors)
    combined = r.manifest["build"]["files"]["combined"]["path"]
    (panel,) = E.editables(Document.from_file(combined))["instances"]
    ref = panel["name"]
    r2 = FD.author(rvt=combined, edit=f"rename panel {ref} to DPX; set mark of {ref} to M-7",
                   out=str(tmp_path / "edit"))
    assert r2.route == "rvt" and r2.ok, (r2.status, r2.errors)
    assert [o["op"] for o in r2.manifest["edit"]["spec"]["ops"]] == ["rename", "set-mark"]
    assert r2.manifest["edit"]["hard_gates_passed"] is True
    edited = Document.from_file(r2.files["edited"])
    assert E.editables(edited)["instances"] == [dict(panel, name="DPX")]
    rows = edited.value(panel["id"])["m_pParamValueSetAString"]["value"]["m_paramSet"]
    assert rows == [{"m_paramId": M.BIP_RBS_ELEC_PANEL_NAME, "m_value": "DPX"},
                    {"m_paramId": M.BIP_ALL_MODEL_MARK, "m_value": "M-7"}]


# ===========================================================================
# 9. stage D: the intent's levels bound to the base's two building-story
#    datums (issue #147) -- rename + re-elevate (the certified modify shape),
#    storeys beyond them recorded, per-item association in stage E
# ===========================================================================

from rvt.frontdoor import levels as LV                      # noqa: E402

#: the issue #147 DONE prompt: two storeys, a floor-to-floor height, gear on both levels
TWO_STOREY = ("a two storey electrical building 40 by 30 ft, floor to floor 14 ft, with a "
              "main switchboard and four lighting panels on level 2")
THREE_LEVELS = [{"id": "L1", "name": "Level 1", "elevation": 0.0},
                {"id": "L2", "name": "Level 2", "elevation": 4.2672},      # 14 ft
                {"id": "L3", "name": "Level 3", "elevation": 8.5344}]      # 28 ft


@needs_pinned
@pytest.mark.parametrize("release", [2026, 2025, 2024])
def test_stage_d_binds_levels_to_the_story_datums_only(tmp_path, release):
    """On each pinned base: L1/L2 land on the two is_building_story datums
    (renamed, L2 re-elevated 12 -> 14 ft), L3 is NOT created and says why,
    those two Level records are the ONLY bytes that change, and two runs are
    byte-identical."""
    from rvt.mutate import Document
    from rvt import manipulate as M
    from rvt import reduce_law as RL
    from rvt.frontdoor import release_ctx as RC
    base = PINNED[release]
    out1, out2 = str(tmp_path / "d1.rvt"), str(tmp_path / "d2.rvt")
    with RC.release_build_context(base):
        before = {lv["id"]: lv for lv in Document.from_file(base).levels()}
        stories = sorted((lv for lv in before.values() if lv["is_building_story"]),
                         key=lambda lv: lv["elevation_ft"])
        assert len(stories) == 2, stories                    # the premise: two story datums
        rec = LV.stage_levels(base, out1, THREE_LEVELS)
        assert rec["ok"] is True and rec["written"] is True, rec
        l1, l2 = rec["levels"]
        assert (l1["base_id"], l2["base_id"]) == (stories[0]["id"], stories[1]["id"])
        assert (l1["name"], l1["elevation_ft"], l1["move"]) == ("Level 1", 0.0, False)
        assert (l2["name"], l2["elevation_ft"], l2["move"]) == ("Level 2", 14.0, True)
        assert l2["base_elevation_ft"] == 12.0 and l1["rename"] and l2["rename"]
        # the third storey: recorded, bound to the top datum at its OWN z, never created
        assert [nb["id"] for nb in rec["not_built"]] == ["L3"]
        assert "NOT created" in rec["not_built"][0]["reason"]
        # '' = level-less items (WORLD z): the datum nearest 0, NO z offset
        assert rec["level_map"] == {"L1": (l1["base_id"], 0.0), "L2": (l2["base_id"], 14.0),
                                    "L3": (l2["base_id"], 28.0), "": (l1["base_id"], 0.0)}
        assert rec["room_level_id"] == l1["base_id"]                    # no room level given
        assert "room shell on it stands on Level 2's datum (14 ft)" in rec["not_built"][0]["reason"]
        assert LV.resolve(rec["level_map"], "L2") == (l2["base_id"], 14.0)
        assert LV.resolve(rec["level_map"], "L9") == LV.resolve(rec["level_map"], None) \
            == (l1["base_id"], 0.0)
        assert LV.resolve({}, "L2", (7, 1.5)) == (7, 1.5)               # no map: the caller's datum
        assert rec["commit"]["replaced"] == [[102, l1["base_id"]], [102, l2["base_id"]]]
        assert rec["commit"]["elemtable_count_before"] == rec["commit"]["elemtable_count_after"]
        # read back: the two story datums say what the intent says, every other level untouched
        after = {lv["id"]: lv for lv in Document.from_file(out1).levels()}
        assert after[l1["base_id"]]["name"] == "Level 1" and after[l1["base_id"]]["elevation_ft"] == 0.0
        assert after[l2["base_id"]]["name"] == "Level 2" and after[l2["base_id"]]["elevation_ft"] == 14.0
        assert {k: v for k, v in after.items() if k not in (l1["base_id"], l2["base_id"])} == \
               {k: v for k, v in before.items() if k not in (l1["base_id"], l2["base_id"])}
        assert len(after) == len(before)                       # no Level constructor ran
        # the certified modify shape's structural proof, under the file's own release
        v = M.verify_manipulated(out1, edited_ids=rec["edited_ids"])
        assert v["stamps_ok"] and v["crc_failures"] == 0 and v["walker_errors"] == 0, v
        assert v["ecc_mismatches"] == 0 and v["unit0_ids_equal_elemtable"] is True, v
        assert {k: e["102"] for k, e in v["edited"].items()} == {
            str(l1["base_id"]): {"class": "Level", "clean": True},
            str(l2["base_id"]): {"class": "Level", "clean": True}}
        # the Document record diff: exactly the two datums modified (seq 102), nothing else
        diff = RL.element_diff(Document.from_file(base), Document.from_file(out1))
        assert not diff.removed and not diff.added, (diff.removed, diff.added)
        assert diff.modified == {l1["base_id"]: [102], l2["base_id"]: [102]}, diff.modified
        # deterministic
        assert LV.stage_levels(base, out2, THREE_LEVELS)["ok"] is True
    with open(out1, "rb") as a, open(out2, "rb") as b:
        assert a.read() == b.read()


@needs_pinned
def test_stage_d_writes_nothing_when_the_datums_already_match(tmp_path):
    """An intent whose levels already carry the base's names / elevations is a
    no-op: no file, ok, and the map still names the datums."""
    from rvt.mutate import Document
    base = PINNED[2026]
    stories = [lv for lv in Document.from_file(base).levels() if lv["is_building_story"]]
    same = [{"id": f"L{i + 1}", "name": st["name"], "elevation": st["elevation_ft"] / PP.FT_PER_M}
            for i, st in enumerate(stories)]
    rec = LV.stage_levels(base, str(tmp_path / "noop.rvt"), same, room_level="L2")
    assert rec["ok"] is True and rec["written"] is False and not rec["edited_ids"]
    assert not os.path.exists(str(tmp_path / "noop.rvt"))
    assert rec["level_map"] == {"L1": (stories[0]["id"], 0.0), "L2": (stories[1]["id"], 12.0),
                                "": (stories[0]["id"], 0.0)}
    assert rec["room_level_id"] == stories[1]["id"]
    # an intent that asserts NOTHING about levels -- a DEFAULTED level (a prompt /
    # IFC silent about levels) or no level at all -- binds the first storey and
    # keeps the datum's own name -> nothing to write
    dflt = [{"id": "L1", "name": "Level 1", "elevation": 0.0, "default": True}]
    assert PP.parse_prompt("an electrical room 30 by 20 ft").levels == dflt
    for silent in (dflt, [], [dict(dflt[0], elevation=1.0)]):    # a default NEVER renames or moves
        rec = LV.stage_levels(base, str(tmp_path / "dflt.rvt"), silent)
        assert rec["ok"] and not rec["written"], rec
        assert [(b["name"], b["base_id"], b["rename"], b["move"]) for b in rec["levels"]] == \
               [(stories[0]["name"], stories[0]["id"], False, False)]
        assert not rec["not_built"] and rec["room_level_id"] == stories[0]["id"]
    # an intent whose lowest level is BELOW grade (an IFC 'Basement' @ -3 m + 'Level 1'
    # @ 0): bound in elevation order, and level-less items / a level-less room land
    # on the datum that ends up nearest 0 with NO z offset -- never on the basement
    doc = Document.from_file(base)
    bound, nb = LV.bind_levels(doc, [{"id": "L1", "name": "Basement", "elevation": -3.0},
                                     {"id": "L2", "name": "Level 1", "elevation": 0.0}])
    assert [(b["base_id"], b["name"]) for b in bound] == [(stories[0]["id"], "Basement"),
                                                          (stories[1]["id"], "Level 1")]
    lm = LV.level_map(bound, nb)
    assert lm[""] == (stories[1]["id"], 0.0) and LV.resolve(lm, None) == (stories[1]["id"], 0.0)
    assert abs(lm["L1"][1] + 3.0 * PP.FT_PER_M) < 1e-6
    # a single storey above grade: level-less items still get z offset 0 on it
    bound, nb = LV.bind_levels(doc, [{"id": "L1", "name": "Level 1", "elevation": 3.0}])
    assert LV.level_map(bound, nb)[""] == (stories[0]["id"], 0.0)


@pytest.fixture(scope="module")
def two_storey_job(tmp_path_factory):
    if not os.path.isfile(PINNED[2026]):
        pytest.skip("bundled genesis base missing")
    if not _catalog_ok():
        pytest.skip("famgen catalog absent (no equipment to place)")
    out = str(tmp_path_factory.mktemp("lv") / "job")
    return FD.author(prompt=TWO_STOREY, out=out, no_handoff=True)


def test_e2e_two_storey_prompt_places_gear_per_level(two_storey_job):
    """The product shape of issue #147: the DONE prompt's combined .rvt has
    the base's two story datums renamed 'Level 1'/'Level 2' at 0 / 14 ft, the
    four lighting panels on Level 2 (m_assocLevelId + z above ITS datum), the
    switchboard on Level 1, the walls on Level 1, and an honest manifest."""
    from rvt.mutate import Document
    r = two_storey_job
    assert r.ok, (r.status, r.errors)
    m = r.manifest
    assert m["intent"]["summary"]["levels"] == [
        {"id": "L1", "name": "Level 1", "elevation": 0.0},
        {"id": "L2", "name": "Level 2", "elevation": 4.2672}]
    cov = m["prompt_coverage"]
    assert not any("all equipment is placed on Level 1" in w for w in cov["warnings"])
    assert not cov["ignored_words"] and not cov["not_built"]
    build = m["build"]
    assert [s["stage"] for s in build["stages"]][:2] == ["P", "D"]
    lv = build["levels"]
    assert lv["ok"] and lv["written"] and not lv["not_built"]
    l1_id, l2_id = (b["base_id"] for b in lv["levels"])
    doc = Document.from_file(build["files"]["combined"]["path"])
    stories = {x["id"]: (x["name"], x["elevation_ft"]) for x in doc.levels() if x["is_building_story"]}
    assert stories == {l1_id: ("Level 1", 0.0), l2_id: ("Level 2", 14.0)}
    inst = {c["tag"]: c for c in build["elements_created"] if c["kind"] == "equipment-instance"}
    assert set(inst) == {"MSB", "LP-1", "LP-2", "LP-3", "LP-4"}
    for tag, c in inst.items():
        v = doc.value(c["elem_id"])
        z = v["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"][2]
        if tag == "MSB":
            assert (c["level"], c["level_id"], v["m_assocLevelId"]) == ("L1", l1_id, l1_id)
            assert abs(z - c["z_above_level_ft"]) < 1e-3                    # datum @ 0
        else:
            assert (c["level"], c["level_id"], v["m_assocLevelId"]) == ("L2", l2_id, l2_id)
            assert abs(z - (14.0 + c["z_above_level_ft"])) < 1e-3           # datum @ 14 ft
            assert abs(z - (14.0 + PP.DEFAULT_PANEL_MOUNT_CENTER_M * PP.FT_PER_M)) < 1e-9
    walls = [c for c in build["elements_created"] if c["kind"] == "wall"]
    assert len(walls) == 4 and all(doc.value(w["elem_id"])["m_assocLevelId"] == l1_id for w in walls)
    assert build["validation"]["combined"]["validate"]["n_errors"] == 0
    with open(r.manifest_paths["md"], encoding="utf-8") as fh:
        md = fh.read()
    assert "levels (the base's building-story datums, renamed / re-elevated)" in md
    assert "L2 → 'Level 2' @ 14 ft" in md


# ===========================================================================
# 10. the IFC lane under the level contract (issue #147 review): storeys are
#     bound in elevation order, every product takes ITS storey (level-relative
#     z), level-less objects keep world z on the datum nearest 0, and the
#     prompt -> IFC addition writes one storey per level (round trip)
# ===========================================================================

ROOM_IFC = os.path.join(ROOT, "inputs", "ifc", "electrical-room-2500a.ifc")


def _have_numpy() -> bool:
    try:
        import numpy  # noqa: F401
        return True
    except Exception:
        return False


needs_ifc_lane = pytest.mark.skipif(not (os.path.isfile(ROOM_IFC) and _have_numpy()),
                                    reason="worked IFC input or numpy absent")


def _storey_variant(tmp_path, name: str) -> str:
    """The worked room IFC (one storey 'Level 1' @ 0, room + gear contained in
    it, world-baked vertices) with (a) an extra 'Basement' storey @ -3 m or
    (b) its single storey moved to +3 m (placement AND Elevation)."""
    src = open(ROOM_IFC, encoding="utf-8").read()
    sto = "#26=IFCBUILDINGSTOREY('14kxonpfZf0kKWo7G2nBh$',#5,'Level 1',$,$,#25,$,$,.ELEMENT.,0.);"
    agg = "#29=IFCRELAGGREGATES('3tZeI_SmPBi7Tm32cEnPOc',#5,$,$,#24,(#26));"
    plc = "#25=IFCLOCALPLACEMENT(#23,#9);"
    assert sto in src and agg in src and plc in src
    if name == "basement":
        out = src.replace(sto, sto + "\n#900001=IFCCARTESIANPOINT((0.,0.,-3.));\n"
                          "#900002=IFCAXIS2PLACEMENT3D(#900001,$,$);\n"
                          "#900003=IFCLOCALPLACEMENT(#23,#900002);\n"
                          "#900004=IFCBUILDINGSTOREY('1BasementStoreyGuid001',#5,'Basement',$,$,"
                          "#900003,$,$,.ELEMENT.,-3.);")
        out = out.replace(agg, agg.replace("(#26)", "(#26,#900004)"))
    else:  # plus3
        out = src.replace(plc, "#900001=IFCCARTESIANPOINT((0.,0.,3.));\n"
                          "#900002=IFCAXIS2PLACEMENT3D(#900001,$,$);\n"
                          "#25=IFCLOCALPLACEMENT(#23,#900002);")
        out = out.replace(sto, sto.replace(".ELEMENT.,0.", ".ELEMENT.,3."))
    p = tmp_path / f"{name}.ifc"
    p.write_text(out, encoding="utf-8")
    return str(p)


@needs_ifc_lane
def test_ifc_products_take_their_storey_with_level_relative_z(tmp_path):
    """The resolver assigns Equipment.level / RoomShell.level from spatial
    containment and rebases z on that storey; world z is unchanged."""
    base = FI.intent_from_ifc(ROOM_IFC)                       # one storey @ 0: numbers as before
    assert [(lv["id"], lv["name"], lv["elevation"]) for lv in base.levels] == [("L1", "Level 1", 0.0)]
    assert base.room.level == "L1" and {e.level for e in base.equipment} == {"L1"}
    world = {e.tag: round(e.insertion_m[2], 4) for e in base.equipment}
    # (a) a Basement @ -3 m BELOW the room's storey: the room and its gear are on L2
    #     ('Level 1' @ 0), NOT sunk onto the basement; z unchanged (its storey is @ 0)
    m = FI.intent_from_ifc(_storey_variant(tmp_path, "basement"))
    assert [(lv["id"], lv["name"], lv["elevation"]) for lv in m.levels] == [
        ("L1", "Basement", -3.0), ("L2", "Level 1", 0.0)]
    assert m.room.level == "L2" and {e.level for e in m.equipment} == {"L2"}
    assert {e.tag: round(e.insertion_m[2], 4) for e in m.equipment} == world
    assert {round(w.base_m, 4) for w in m.room.walls} == {0.0}
    # (b) the single storey moved to +3 m: world z rides up 3 m, level-relative z does not
    m = FI.intent_from_ifc(_storey_variant(tmp_path, "plus3"))
    assert [(lv["name"], lv["elevation"]) for lv in m.levels] == [("Level 1", 3.0)]
    assert m.room.level == "L1" and {e.level for e in m.equipment} == {"L1"}
    assert {e.tag: round(e.insertion_m[2], 4) for e in m.equipment} == world
    assert {round(w.base_m, 4) for w in m.room.walls} == {0.0}
    msb = m.by_tag("MSB")
    assert round(msb.elevation_m, 4) == round(base.by_tag("MSB").elevation_m, 4)


@needs_ifc_lane
@needs_pinned
def test_stage_d_on_ifc_storeys_never_sinks_or_double_offsets_the_room(tmp_path):
    """Through the level map the build uses: Basement variant -> room datum =
    the story that ends up @ 0, gear z offset = that datum's 0; +3 m variant ->
    gear world z = 3 m + its level-relative z exactly once."""
    from rvt.mutate import Document
    doc = Document.from_file(PINNED[2026])
    s1, s2 = (lv["id"] for lv in LV.story_levels(doc))
    m = FI.intent_from_ifc(_storey_variant(tmp_path, "basement"))
    bound, nb = LV.bind_levels(doc, m.levels)
    lm = LV.level_map(bound, nb)
    assert LV.resolve(lm, m.room.level) == (s2, 0.0)                     # walls base 0 ft
    lvl, z0 = LV.resolve(lm, m.by_tag("MSB").level)
    assert (lvl, round(z0 + m.by_tag("MSB").insertion_m[2] * PP.FT_PER_M, 3)) == (s2, 0.328)
    m = FI.intent_from_ifc(_storey_variant(tmp_path, "plus3"))
    bound, nb = LV.bind_levels(doc, m.levels)
    lm = LV.level_map(bound, nb)
    lvl, z0 = LV.resolve(lm, m.by_tag("MSB").level)
    assert lvl == s1 and abs(z0 - 3.0 * PP.FT_PER_M) < 1e-6
    assert round(z0 + m.by_tag("MSB").insertion_m[2] * PP.FT_PER_M, 3) == 10.171   # 3.1 m, once


@needs_ifc_lane
@needs_catalog
def test_prompt_to_ifc_addition_keeps_every_storey(tmp_path):
    """The version-agnostic IFC of a two-storey prompt carries BOTH storeys and
    each product under its own: re-read through our resolver the LPs are on
    L2 @ 4.2672 m with their level-relative z, the switchboard + shell on L1."""
    from rvt.frontdoor import ifc_out
    model, parsed = PP.prompt_to_intent(TWO_STOREY)
    p = ifc_out.write_intent_ifc(model, str(tmp_path / "two.ifc"))
    text = open(p, encoding="ascii").read()
    assert text.count("IFCBUILDINGSTOREY(") == 2
    assert text.count("IFCRELCONTAINEDINSPATIALSTRUCTURE(") == 2
    m2 = FI.intent_from_ifc(p)
    assert [(lv["id"], lv["name"], lv["elevation"]) for lv in m2.levels] == [
        ("L1", "Level 1", 0.0), ("L2", "Level 2", 4.2672)]
    assert {e.tag: e.level for e in m2.equipment} == {e.tag: e.level for e in model.equipment} == {
        "MSB": "L1", "LP-1": "L2", "LP-2": "L2", "LP-3": "L2", "LP-4": "L2"}
    for e in m2.equipment:
        assert abs(e.insertion_m[2] - model.by_tag(e.tag).insertion_m[2]) < 1e-3, e.tag
    assert m2.room is not None and m2.room.level == "L1" and len(m2.room.walls) == 4


# ===========================================================================
# 11. the convert lane under the same contract (round-2 review): rvt -> ifc
#     writes one storey per BUILDING STORY (never the base's GEN reference
#     datums), gear under its own storey, and ifc -> rvt of that file lands
#     like main (unique level names, no degradations)
# ===========================================================================

def _storey_lines(path: str) -> list:
    return [ln for ln in open(path, encoding="ascii").read().splitlines()
            if "IFCBUILDINGSTOREY(" in ln]


@needs_pinned
def test_rvt_to_ifc_of_the_pinned_base_writes_only_its_story_datum(tmp_path):
    """The 2026 base has 9 Levels (2 building stories, 7 'GEN ...' reference
    datums) and no gear: a level-blind read-back gets ONE storey, never nine."""
    from rvt.convert import rvt_to_ifc as R
    out = str(tmp_path / "base.ifc")
    R.convert_rvt_to_ifc(PINNED[2026], out)
    stos = _storey_lines(out)
    assert len(stos) == 1 and "GEN " not in stos[0], stos


def test_rvt_ifc_rvt_round_trip_keeps_storeys_and_unique_level_names(two_storey_job, tmp_path):
    """convert_rvt_to_ifc(<the built two-storey job>) -> 2 storeys ('Level 1'
    / 'Level 2', none of the base's 7 reference datums), each product under
    ITS storey with level-relative z; that IFC re-read binds back onto the
    pinned base exactly like the prompt did (unique names, main's placement)."""
    from rvt.convert import rvt_to_ifc as R
    from rvt.mutate import Document
    r = two_storey_job
    combined = r.manifest["build"]["files"]["combined"]["path"]
    out = str(tmp_path / "two.ifc")
    R.convert_rvt_to_ifc(combined, out)
    assert [ln.split(",")[2] for ln in _storey_lines(out)] == ["'Level 1'", "'Level 2'"]
    text = open(out, encoding="ascii").read()
    assert text.count("IFCRELCONTAINEDINSPATIALSTRUCTURE(") == 2 and "GEN " not in "".join(_storey_lines(out))
    m = FI.intent_from_ifc(out)
    assert [(lv["name"], lv["elevation"]) for lv in m.levels] == [("Level 1", 0.0), ("Level 2", 4.2672)]
    assert {e.tag: (e.level, round(e.insertion_m[2], 2)) for e in m.equipment} == {
        "MSB": ("L1", 0.1), "LP-1": ("L2", 1.42), "LP-2": ("L2", 1.42),
        "LP-3": ("L2", 1.42), "LP-4": ("L2", 1.42)}
    assert m.room is not None and m.room.level == "L1" and {round(w.base_m, 3) for w in m.room.walls} == {0.0}
    # ifc -> rvt leg: the level map the build uses (no full second build needed)
    doc = Document.from_file(PINNED[2026])
    bound, nb = LV.bind_levels(doc, m.levels)
    assert [(b["base_id"], b["name"], b["elevation_ft"], b.get("rename_skipped")) for b in bound] == [
        (311, "Level 1", 0.0, None), (245423, "Level 2", 14.0, None)] and not nb
    lm = LV.level_map(bound, nb)
    assert LV.resolve(lm, m.room.level) == (311, 0.0)
    lvl, z0 = LV.resolve(lm, m.by_tag("LP-1").level)
    assert (lvl, round(z0 + m.by_tag("LP-1").insertion_m[2] * PP.FT_PER_M, 3)) == (245423, 18.659)


@needs_pinned
def test_a_datum_is_never_renamed_to_a_name_another_level_keeps():
    """Revit level names must be unique: an intent naming a storey like one of
    the base's reference datums keeps the datum's own name and says so."""
    from rvt.mutate import Document
    doc = Document.from_file(PINNED[2026])
    ref = next(lv for lv in doc.levels() if not lv["is_building_story"])      # a 'GEN ...' datum
    bound, _nb = LV.bind_levels(doc, [{"id": "L1", "name": ref["name"], "elevation": 0.0},
                                       {"id": "L2", "name": "Level 2", "elevation": 4.0}])
    assert bound[0]["name"] == bound[0]["base_name"] and not bound[0]["rename"]
    assert "must be unique" in bound[0]["rename_skipped"]
    assert bound[1]["name"] == "Level 2" and "rename_skipped" not in bound[1]
    # swapping the two story names between the two story datums is fine (both are re-bound)
    s = LV.story_levels(doc)
    bound, _nb = LV.bind_levels(doc, [{"id": "L1", "name": s[1]["name"], "elevation": 0.0},
                                       {"id": "L2", "name": s[0]["name"], "elevation": 4.0}])
    assert [b["name"] for b in bound] == [s[1]["name"], s[0]["name"]]
    assert not any("rename_skipped" in b for b in bound)

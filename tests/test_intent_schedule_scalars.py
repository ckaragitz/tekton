"""test_intent_schedule_scalars.py -- a hand-typed board / transformer /
switchboard schedule cell no longer FAILS the ``--ifc`` route (issue #442).

#438 made ``DeviceSchedule.Load`` ('180 VA') coerce or degrade ONE device with
a note.  Its siblings one line over -- ``MainsRating '400 A'``, ``RatingkVA
'75 kVA'``, ``NumberOfCircuits '42 ckt'``, ``ShortCircuitRatingkA '65 kA'``,
``Phases '3 ph'``, ``Sections '4 sections'``, ``MountingHeight '44 in'`` --
still raised ``ValueError`` out of ``resolve_intent`` (classification, the
feeder tree or ``plan_family_for``) and the whole route ended FAILED, rc 3, no
``.rvt``.  Now ONE rule reads every schedule scalar
(``rvt.ifc.intent.parse_schedule_scalar``; ``parse_device_load`` is its Load
preset, wording unchanged): ``normalize_contract`` coerces the tagging
contract's numeric cells or drops an unusable one so it reads as empty, ONE
note per cell riding onto the plan; ``plan_families`` refuses -- records --
an item whose planning raises anyway and plans the rest; a non-finite pset
value never reaches a JSON the front door writes as a bare ``Infinity``.

Sample-free (hand-built records, the famgen catalog, the bundled steplite
reader, the pinned genesis base); no file here is claimed to load in Revit
(rule 4).

Run: .venv/bin/python -m pytest tests/test_intent_schedule_scalars.py -q
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.ifc import intent as I                      # noqa: E402
from rvt.frontdoor import intent as FI               # noqa: E402
from rvt.frontdoor import prompt_intent as PP        # noqa: E402

RT_PROMPT = "an electrical room with a 100 A lighting panel and 4 duplex receptacles at 44 in AFF"
PINNED_2026 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_device_facts("duplex-receptacle")
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=100, spaces=30,
                                    voltage="208Y/120", mcb=True, mounting="surface",
                                    panel_name="X")
        F.resolve_transformer_facts(75.0, vendor="eaton", primary_v=480, secondary_v="208Y/120")
        return True
    except Exception:                                    # noqa: BLE001
        return False


_CATALOG = _catalog_ok()
needs_catalog = pytest.mark.skipif(not _CATALOG, reason="famgen catalog absent")

_CLASS = {"transformer": "IfcTransformer", "receptacle_device": "IfcOutlet"}
_PSET = {"transformer": "TransformerSchedule", "switchboard": "SwitchboardSchedule",
         "receptacle_device": I.DEVICE_PSET}


def _eq(tag: str, kind: str, schedule: dict, *, contract=None, dims=None) -> I.Equipment:
    """A hand-built equipment record whose contract is folded from its
    schedule pset by ``normalize_contract`` -- exactly as both routes do --
    unless an explicit (hand-built) ``contract`` is given."""
    psets = {_PSET.get(kind, "PanelSchedule"): dict(schedule)}
    con = contract if contract is not None else I.normalize_contract(
        psets, name=tag, object_type=None, description=None, tag=tag)
    e = I.Equipment(step_id=0, guid=tag, ifc_class=_CLASS.get(kind, "IfcElectricDistributionBoard"),
                    predefined_type=None, name=tag, tag=tag, description=None, object_type=None,
                    type_name=None, kind=kind, psets=psets, contract=con,
                    placement=I.Placement(np.eye(4)), geometry=I.ProductGeometry(items=[]))
    e.dims_m = dict(dims or {})
    return e


# ---------------------------------------------------------------------------
# 1. ONE rule for every schedule scalar
# ---------------------------------------------------------------------------

def _amps(raw):
    return I.parse_schedule_scalar("PanelSchedule.MainsRating", raw, I.AMPS, fallback="ignored (unit test)")


def test_each_scalar_kind_coerces_the_unit_a_person_types_and_degrades_the_rest_with_one_note():
    # amps: '400 A' / '400A' / '400 amps' / '0.4 kA' -> 400.0 with the text-label note
    for raw, want in (("400 A", 400.0), ("400A", 400.0), ("400 amps", 400.0), (" 400 Amp ", 400.0),
                      ("0.4 kA", 400.0), ("100", 100.0), ("2.5e3 A", 2500.0)):
        v, note = _amps(raw)
        assert v == want, raw
        assert note == (f"PanelSchedule.MainsRating {raw!r} is a text label, not a measure -> "
                        f"read as {want:g} A"), note
    for raw in (400, 400.0, 2500):                                     # a real measure: as is, silently
        assert _amps(raw) == (float(raw), None)
    for raw in (None, "", "  ", 0, 0.0, "0", "0 A"):                   # blank / zero: an empty cell, silently
        assert _amps(raw) == (None, None), raw
    for raw, why in (("abc", "not a number"), ("400 AF", "not a number"), ("400 V", "not a number"),
                     (True, "not a number"), ([400], "not a number"), ("nan", "not a number"),
                     (-100, "negative"), ("-100 A", "negative"),
                     (float("inf"), "not finite"), (float("nan"), "not finite"), ("1e400 A", "not finite"),
                     (25000.0, "above the 20000 A sanity cap for one distribution board")):
        v, note = _amps(raw)
        assert v is None, raw
        assert note.startswith(f"PanelSchedule.MainsRating {raw!r} is not a usable current rating ({why})"), note
        assert note.endswith("-> ignored (unit test)")
    v, note = _amps(10 ** 400)                          # a >308-digit IFCINTEGER: no OverflowError, repr clipped
    assert v is None and "(not finite)" in note and len(note) < 200
    assert note.startswith("PanelSchedule.MainsRating 1" + "0" * 56 + "... is not a usable current rating")
    # kVA / kA: the unit IS the property's ('75 kVA' -> 75, '65 kAIC' -> 65)
    kva = lambda raw: I.parse_schedule_scalar("T.RatingkVA", raw, I.KVA, fallback="x")      # noqa: E731
    assert kva("75 kVA") == (75.0, "T.RatingkVA '75 kVA' is a text label, not a measure -> read as 75 kVA")
    assert kva("75kva")[0] == kva("75")[0] == kva(75)[0] == 75.0
    assert kva("big") == (None, "T.RatingkVA 'big' is not a usable transformer rating (not a number) -> x")
    ka = lambda raw: I.parse_schedule_scalar("S.ShortCircuitRatingkA", raw, I.KA, fallback="x")   # noqa: E731
    assert [ka(r)[0] for r in ("65 kA", "65kA", "65 kAIC", "65", 65.0)] == [65.0] * 5
    assert "above the 300 kA sanity cap" in ka("400 kA")[1]
    # counts: whole numbers with the word a person types after them; returned as int
    ckt = I.CONTRACT_SCALARS["NumberOfCircuits"]
    count = lambda raw: I.parse_schedule_scalar("P.NumberOfCircuits", raw, ckt, fallback="x")   # noqa: E731
    for raw in ("42", "42 ckt", "42 circuits", "42-circuit", "42 spaces", "42 SP", 42, 42.0):
        v, _ = count(raw)
        assert v == 42 and isinstance(v, int), raw
    assert count("42.5")[0] is None and "(not a whole number)" in count("42.5")[1]
    assert count(42.5)[0] is None and "(not a whole number)" in count(42.5)[1]
    assert "(above the 200 sanity cap for one panelboard)" in count("400 ckt")[1]
    phases = lambda raw: I.parse_schedule_scalar("P.Phases", raw, I.CONTRACT_SCALARS["Phases"],   # noqa: E731
                                                 fallback="x")[0]
    assert [phases(r) for r in ("3", "3 ph", "3-phase", "3PH", 3, "1P", "4")] == [3, 3, 3, 3, 3, 1, None]
    assert I.parse_schedule_scalar("S.Sections", "4 sections", I.CONTRACT_SCALARS["Sections"], fallback="x")[0] == 4
    assert I.parse_schedule_scalar("S.Wires", "4W", I.CONTRACT_SCALARS["Wires"], fallback="x")[0] == 4
    # parse_device_load IS the Load preset (its 35 pinned cases: tests/test_intent_device_plan.py)
    assert (I.LOAD_VA.cap, I.LOAD_VA.unit, I.LOAD_VA.factors) == (I.MAX_DEVICE_VA, "VA", {"": 1.0, "k": 1000.0})
    # a space-stuffed junk cell fails in linear time (possessive tails), not by backtracking
    for junk in ("42 ckt" + " " * 20000 + "!", "42" + " " * 20000 + "!", " " * 20000 + "x"):
        assert count(junk)[0] is None and I.parse_mounting_height(junk)[0] is None and _amps(junk)[0] is None


def test_a_mounting_height_coerces_to_inches_or_lets_the_facts_convention_stand_in():
    H = I.parse_mounting_height
    for raw, want in (("44 in", 44.0), ("44in", 44.0), ('44"', 44.0), ("44 inches", 44.0), ("44 in.", 44.0),
                      ("44 in AFF", 44.0), ("44 in a.f.f.", 44.0), ("18 in above finished floor", 18.0),
                      ("3.5 ft", 42.0), ("4'", 48.0), ("1100 mm", 1100 / 25.4), ("110 cm", 1100 / 25.4),
                      ("1.1 m", 1100 / 25.4), ("44", 44.0)):
        v, note = H(raw)
        assert v == pytest.approx(want), raw
        assert note.startswith(f"DeviceSchedule.MountingHeight {raw!r} is a text label") and \
            f"read as {v:g} in" in note, note
    for raw in (44, 44.0, 18, 0, 0.0):                     # a real measure, zero included: as is, silently
        assert H(raw) == (float(raw), None), raw
    assert H(None) == (None, None) and H("  ") == (None, None)
    for raw, why in (("eye level", "not a number"), ("44 kg", "not a number"), (-18, "negative"),
                     (float("nan"), "not finite"), ("4400", "above the 600 in sanity cap"), ("30 m", "above the 600 in")):
        v, note = H(raw)
        assert v is None, raw
        assert note.startswith(f"DeviceSchedule.MountingHeight {raw!r} is not a usable mounting height ({why}")
        assert "the facts' typical mounting height for this device stands in (flagged 'assumed')" in note


# ---------------------------------------------------------------------------
# 2. the contract folds every numeric cell through the rule (both routes)
# ---------------------------------------------------------------------------

def test_normalize_contract_coerces_hand_typed_cells_and_drops_unusable_ones_with_one_note_each():
    typed = {"PanelSchedule": {"PanelName": "DP-1", "Voltage": "480Y/277 V", "Phases": "3 ph", "Wires": "4W",
                               "BusRating": "400A", "MainsRating": "400 A", "MainsType": "Main breaker",
                               "NumberOfCircuits": "42 ckt", "ShortCircuitRatingkA": "65 kA"}}
    con = I.normalize_contract(typed, name="DP-1", object_type=None, description=None, tag="DP-1")
    assert (con["BusRating"], con["MainsRating"], con["NumberOfCircuits"], con["ShortCircuitRatingkA"],
            con["Phases"], con["Wires"]) == (400.0, 400.0, 42, 65.0, 3, 4)
    assert isinstance(con["NumberOfCircuits"], int) and isinstance(con["Phases"], int)
    notes = con["_notes"]
    assert len(notes) == 6 and all(" is a text label, not a measure -> read as " in n for n in notes)
    assert notes[0] == "PanelSchedule.BusRating '400A' is a text label, not a measure -> read as 400 A"
    assert con["_provenance"]["MainsRating"] == "pset:PanelSchedule.MainsRating"
    # an unusable cell is DROPPED so it reads as empty: MainsRating falls back to the bus
    # rating, NumberOfCircuits to the name text -- exactly as if the cell were blank
    junk = {"PanelSchedule": {"PanelName": "LP-2", "Voltage": "208Y/120 V", "BusRating": 100.0,
                              "MainsRating": "n/a", "NumberOfCircuits": "lots", "Phases": 7}}
    con = I.normalize_contract(junk, name="LP-2 30-space lighting panel", object_type=None,
                               description=None, tag="LP-2")
    assert con["MainsRating"] == 100.0 and con["_provenance"]["MainsRating"] == "= BusRating (single-rating device)"
    assert con["NumberOfCircuits"] == 30 and con["_provenance"]["NumberOfCircuits"] == "name-text (NN space)"
    assert con["Phases"] == 3 and con["_provenance"]["Phases"] == "derived from voltage system"
    assert [n.split(" -> ")[0] for n in con["_notes"]] == [
        "PanelSchedule.MainsRating 'n/a' is not a usable current rating (not a number)",
        "PanelSchedule.NumberOfCircuits 'lots' is not a usable circuit count (not a number)",
        "PanelSchedule.Phases 7 is not a usable phase count (above the 3 sanity cap for a phase count)"]
    assert all(n.endswith("reads as an empty cell (fix the schedule cell to book it)") for n in con["_notes"])
    # a figure mined from the NAME clears the same caps as a cell: an absurd '30000 A' in both
    # the pset and the name is dropped twice (two notes), never re-injected by the name text
    absurd = I.normalize_contract({"SwitchboardSchedule": {"BusRating": 30000.0}}, name="MSB 30000 A switchboard",
                                  object_type=None, description=None, tag="MSB")
    assert "BusRating" not in absurd and "MainsRating" not in absurd
    assert [n.split(" is ")[0] for n in absurd["_notes"]] == ["SwitchboardSchedule.BusRating 30000.0",
                                                            "name-text BusRating 30000.0"]
    named = I.normalize_contract({}, name="DP-2 400 A 42-circuit panel", object_type=None, description=None, tag="DP-2")
    assert (named["BusRating"], named["MainsRating"], named["NumberOfCircuits"]) == (400.0, 400.0, 42)
    assert "_notes" not in named
    # review of #457: a TEXT cell that parses to "empty" ('0 A', '-0 kVA', '0 ph', '  ', '0.0') is
    # dropped like an unusable one, silently -- no raw string is ever left in the contract for a
    # consumer (classification, the feeder tree, the room builder) to cast
    empties = {"PanelSchedule": {"Voltage": "208Y/120 V", "BusRating": "0 A", "MainsRating": "  ",
                                 "NumberOfCircuits": "0 ckt", "ShortCircuitRatingkA": "0.0",
                                 "Phases": "0 ph", "Wires": "0W"},
               "TransformerSchedule": {"RatingkVA": "-0 kVA", "Sections": " "}}
    con = I.normalize_contract(empties, name="LP-1", object_type=None, description=None, tag="LP-1")
    assert {k: v for k, v in con.items() if not k.startswith("_")} == {
        "Voltage": "208Y/120 V", "PanelName": "LP-1", "Phases": 3, "Wires": 4}   # phases/wires re-derived
    assert "_notes" not in con and "BusRating" not in con["_provenance"]
    for schedule in (typed, junk, empties):
        c = I.normalize_contract(schedule, name="X 30-space", object_type=None, description=None, tag="X")
        assert not [k for k in I.CONTRACT_SCALARS if isinstance(c.get(k), str)], c
    # '1,200 A' is 1200 with its thousands comma (cell and name text alike), never the '200' after it
    assert _amps("1,200 A") == (1200.0, "PanelSchedule.MainsRating '1,200 A' is a text label, not a measure "
                                        "-> read as 1200 A")
    assert _amps("12,000A")[0] == 12000.0 and _amps("1,200.5")[0] == 1200.5
    assert _amps("1,20 A")[0] is None and _amps("1,2000 A")[0] is None and _amps(",200 A")[0] is None
    for nm, want in (("DP-1 - 1,200 A distribution panel", 1200.0), ("MSB 4000A", 4000.0),
                     ("LP-2 100 A", 100.0), ("X 12,00 A", None), ("T 1.200 A", None)):
        c = I.normalize_contract({}, name=nm, object_type=None, description=None, tag="X")
        assert c.get("BusRating") == want and c.get("MainsRating") == want, nm
    # a blank / zero cell stays put, silently (a switchboard's NumberOfCircuits 0 round-trips as 0)
    zero = I.normalize_contract({"SwitchboardSchedule": {"NumberOfCircuits": 0, "Sections": 4.0}},
                                name="MSB", object_type=None, description=None, tag="MSB")
    assert zero["NumberOfCircuits"] == 0 and zero["Sections"] == 4 and "_notes" not in zero
    # transformer kVA rides through the alias loop and the same rule
    t = I.normalize_contract({"TransformerSchedule": {"RatingkVA": "75 kVA", "Primary": "480 V delta"}},
                             name="T1", object_type=None, description=None, tag="T1")
    assert t["RatingkVA"] == 75.0 and len(t["_notes"]) == 1


def test_the_prompt_routes_numeric_contract_is_untouched_by_the_rule():
    """The prompt route authors numbers; folding them through the rule must
    change no value, no type and add no ``_notes`` (the 6-panel manifest and
    the emitted IFC stay byte-for-byte what they were)."""
    model, _ = PP.prompt_to_intent("an electrical room with a 2500 A switchboard MSB, a 75 kVA transformer "
                                   "T1 fed from MSB, a 400 A distribution panel DP-1 fed from MSB and a "
                                   "100 A lighting panel LP-1 fed from T1")
    for eq in model.equipment:
        con = eq.contract
        assert "_notes" not in con, (eq.tag, con.get("_notes"))
        for props in eq.psets.values():                                # the synthetic schedule psets, as authored
            for k, v in props.items():
                if k in I.CONTRACT_SCALARS:
                    assert con[k] == v and type(con[k]) is type(v), (eq.tag, k, v, con[k])
    assert {p.tag: p.notes for p in model.family_plans if p.kind != "switchboard"} == {
        "T1": [], "DP-1": [], "LP-1": []}


# ---------------------------------------------------------------------------
# 3. plan_family_for: every board branch reads through the rule
# ---------------------------------------------------------------------------

@needs_catalog
def test_board_branches_plan_from_hand_typed_cells_with_one_note_per_cell():
    dp = I.plan_family_for(_eq("DP-1", "distribution_panelboard",
                               {"Voltage": "480Y/277 V", "MainsRating": "400 A", "MainsType": "Main breaker",
                                "NumberOfCircuits": "42 ckt", "ShortCircuitRatingkA": "65 kA"}))
    assert dp.status == "resolved" and dp.constructor.endswith("make_panelboard")
    assert (dp.kwargs["mains_a"], dp.kwargs["spaces"], dp.kwargs["sccr_ka"]) == (400.0, 42, 65.0)
    assert len(dp.notes) == 3 and dp.notes[0] == (
        "PanelSchedule.MainsRating '400 A' is a text label, not a measure -> read as 400 A")
    lp = I.plan_family_for(_eq("LP-1", "lighting_panelboard", {"Voltage": "480Y/277 V", "BusRating": "100 A",
                                                                "MainsType": "Main lugs only"}))
    assert lp.status == "resolved" and lp.kwargs["mains_a"] == 100.0 and lp.variant == "PRL2X"
    assert len(lp.notes) == 1
    t1 = I.plan_family_for(_eq("T1", "transformer", {"RatingkVA": "75 kVA", "Primary": "480 V delta",
                                                    "Secondary": "208Y/120 V"}))
    assert t1.status == "resolved" and t1.kwargs["kva"] == 75.0 and len(t1.notes) == 1
    bad = I.plan_family_for(_eq("T2", "transformer", {"RatingkVA": "big"}))
    assert bad.status == "refused" and bad.kwargs["kva"] == 0.0        # degraded to the branch default ...
    assert bad.refusal.startswith("FactoryError:") and len(bad.notes) == 1   # ... the resolver's refusal stands
    msb = I.plan_family_for(_eq("MSB", "switchboard",
                                {"Voltage": "480Y/277 V", "MainsRating": "2500 A", "Phases": "3 ph",
                                 "Wires": "4W", "ShortCircuitRatingkA": "65 kA", "Sections": "4 sections",
                                 "MainDevice": "2500 A main breaker"}, dims={"w": 2.4, "d": 0.9, "h": 2.3}))
    assert msb.status == "house"
    assert {k: msb.kwargs[k] for k in ("mains_a", "phases", "wires", "sccr_ka", "sections")} == {
        "mains_a": 2500.0, "phases": 3, "wires": 4, "sccr_ka": 65.0, "sections": 4}
    assert len(msb.notes) == 6 and msb.notes[-1].startswith("NO catalog record covers a 2500 A switchboard")
    # a HAND-BUILT contract (no normalize_contract) reads through the same rule inside the branch
    raw = I.plan_family_for(_eq("DP-2", "distribution_panelboard", {}, contract={
        "Voltage": "480Y/277 V", "MainsRating": "400 A", "NumberOfCircuits": "lots", "MainsType": "MCB"}))
    assert raw.status == "resolved" and (raw.kwargs["mains_a"], raw.kwargs["spaces"]) == (400.0, 42)
    assert [n.split(" is ")[0] for n in raw.notes] == ["MainsRating '400 A'", "NumberOfCircuits 'lots'"]
    # the device branch: MountingHeight '44 in' / '1100 mm' coerce, 'eye level' lets the facts stand in
    r1 = I.plan_family_for(_eq("R-1", "receptacle_device", {"Voltage": "120 V", "Load": "180 VA",
                                                            "MountingHeight": "44 in"}))
    assert r1.status == "resolved" and r1.kwargs["mounting_height_in"] == 44.0
    assert r1.facts_summary["mounting_height_in"] == 44.0 and len(r1.notes) == 2
    mm = I.plan_family_for(_eq("R-2", "receptacle_device", {"MountingHeight": "1100 mm"}))
    assert mm.kwargs["mounting_height_in"] == pytest.approx(1100 / 25.4)
    eye = I.plan_family_for(_eq("R-3", "receptacle_device", {"MountingHeight": "eye level"}))
    assert eye.status == "resolved" and eye.kwargs["mounting_height_in"] is None
    assert eye.facts_summary["mounting_height_in"] == 18.0            # the record's typical, 'assumed'
    assert len(eye.notes) == 1 and "'eye level' is not a usable mounting height" in eye.notes[0]


@needs_catalog
def test_plan_families_refuses_the_item_whose_planning_raises_and_plans_the_rest(monkeypatch):
    """The per-item backstop: an unexpected exception out of ONE branch is a
    recorded refusal for THAT item (listed under the build's degradations,
    nothing buildable) -- never propagated; its neighbours still plan."""
    def boom(fp):
        raise RuntimeError("resolver bug (unit test)")
    monkeypatch.setattr(I, "_resolve_xfmr_facts", boom)
    items = [_eq("DP-1", "distribution_panelboard", {"Voltage": "480Y/277 V", "MainsRating": 400.0,
                                                     "MainsType": "Main breaker"}),
             _eq("T1", "transformer", {"RatingkVA": 75.0}, dims={"w": 0.8, "d": 0.6, "h": 1.2}),
             _eq("R-1", "receptacle_device", {"MountingHeight": 18.0})]
    with pytest.raises(RuntimeError):
        I.plan_family_for(items[1])                                  # the branch itself does raise ...
    plans = I.plan_families(items)                                   # ... the table never does
    assert [(p.tag, p.status) for p in plans] == [("DP-1", "resolved"), ("T1", "refused"), ("R-1", "resolved")]
    t1 = plans[1]
    assert t1.refusal == "RuntimeError: resolver bug (unit test)"
    assert (t1.kind, t1.constructor, t1.kwargs) == ("transformer", "", {})
    assert len(t1.notes) == 1 and "NOT built; every other item still is" in t1.notes[0]
    assert t1.as_json()["refusal"] == t1.refusal
    model = I.IntentModel(source_path="unit", schema="unit", project_name="unit", length_scale_m=1.0,
                          levels=[], equipment=items, other_products=[], room=None, clearances=[],
                          feeders=[], conduit_runs=[], family_plans=plans, audit={})
    assert [p.tag for p in FI.buildable_family_plans(model)] == ["DP-1", "R-1"]
    assert FI.summarize(model)["family_plans_by_status"] == {"resolved": 2, "refused": 1}


# ---------------------------------------------------------------------------
# 4. the --ifc route: a retyped MainsRating is delivered, not FAILED
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def our_ifc(tmp_path_factory):
    """OUR IFC of a 100 A lighting panel + 4 receptacles at 44 in AFF."""
    if not _CATALOG:
        pytest.skip("famgen catalog absent")
    from rvt.frontdoor.ifc_out import write_intent_ifc
    model, _ = PP.prompt_to_intent(RT_PROMPT)
    return write_intent_ifc(model, str(tmp_path_factory.mktemp("rt") / "rt.ifc"))


def _retyped(src: str, dst: str, *swaps) -> str:
    """Copy OUR IFC with cells retyped the way a person hand-authors them."""
    text = open(src, encoding="ascii").read()
    for old, new in swaps:
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    with open(dst, "w", encoding="ascii", newline="") as fh:
        fh.write(text)
    return dst


MAINS = ("IFCPROPERTYSINGLEVALUE('MainsRating',$,IFCREAL(100.),$)",
         "IFCPROPERTYSINGLEVALUE('MainsRating',$,IFCLABEL('100 A'),$)")


def test_a_hand_typed_mains_rating_no_longer_fails_the_ifc_route(our_ifc, tmp_path):
    """Before: ``MainsRating IFCLABEL('100 A')`` -> ``ValueError: could not
    convert string to float: '100 A'`` out of plan_families, route FAILED,
    rc 3, no .rvt.  Now: LP-1 resolves at 100 A with ONE note, everything is
    generated, loaded and placed, and the combined file is DELIVERED,
    stamped, validator 0 errors (rule 1; no Revit-load claim -- rule 4)."""
    if not os.path.isfile(PINNED_2026):
        pytest.skip("bundled genesis base missing")
    import rvt.frontdoor as FD
    hand = _retyped(our_ifc, str(tmp_path / "hand.ifc"), MAINS)
    model = FI.intent_from_ifc(hand)                                  # the bare resolver first
    lp = model.plan_for("LP-1")
    assert lp.status == "resolved" and lp.kwargs["mains_a"] == 100.0 and lp.variant == "PRL2X"
    assert lp.notes == ["PanelSchedule.MainsRating '100 A' is a text label, not a measure -> read as 100 A"]
    assert next(e for e in model.equipment if e.tag == "LP-1").contract["MainsRating"] == 100.0
    r = FD.author(ifc=hand, out=str(tmp_path / "job"))               # the product path
    assert r.route == "ifc" and r.ok and r.errors == [], (r.status, r.errors)
    assert "PROOF-ONLY" in r.status
    combined = r.files.get("combined")
    assert combined and os.path.isfile(combined) and os.path.getsize(combined) > 0
    build = r.manifest["build"]
    assert build["errors"] == [] and build["degradations"] == []
    assert build["validation"]["combined"]["validate"]["n_errors"] == 0
    kinds = [c["kind"] for c in build["elements_created"]]
    assert kinds.count("equipment-instance") == 1 and kinds.count("fixture-instance") == 4
    assert r.manifest["intent"]["summary"]["family_plans_by_status"] == {"resolved": 5}
    with open(r.intent_json, encoding="utf-8") as fh:
        on_disk = {p["tag"]: p for p in json.load(fh)["familyMapping"]}
    assert on_disk["LP-1"]["notes"] == lp.notes and on_disk["LP-1"]["kwargs"]["mains_a"] == 100.0
    # review of #457: a TEXT zero ('0 A') reads as an empty cell -- dropped from the contract,
    # never left as a raw string for a consumer to cast; LP-1 rates from its MainsRating, is
    # built and placed, and the file is delivered exactly as above
    zero = _retyped(our_ifc, str(tmp_path / "zero.ifc"),
                    ("IFCPROPERTYSINGLEVALUE('BusRating',$,IFCREAL(100.),$)",
                     "IFCPROPERTYSINGLEVALUE('BusRating',$,IFCLABEL('0 A'),$)"))
    con = next(e for e in FI.intent_from_ifc(zero).equipment if e.tag == "LP-1").contract
    assert con["MainsRating"] == 100.0 and "_notes" not in con
    assert not isinstance(con.get("BusRating"), str)                    # gone, or re-mined from the name text
    assert con["_provenance"].get("BusRating", "name-text").startswith("name-text")
    r = FD.author(ifc=zero, out=str(tmp_path / "job0"))
    assert r.ok and r.errors == [] and os.path.isfile(r.files.get("combined") or ""), (r.status, r.errors)
    build = r.manifest["build"]
    assert build["errors"] == [] and build["degradations"] == []
    assert build["validation"]["combined"]["validate"]["n_errors"] == 0
    assert [c["kind"] for c in build["elements_created"]].count("equipment-instance") == 1   # LP-1 built


def test_every_other_retyped_scalar_resolves_with_one_note_and_no_bare_infinity(our_ifc, tmp_path):
    """Each sibling cell retyped once on OUR IFC: the bare resolver never
    raises, the affected plan carries exactly ONE schedule note, and a
    non-finite cell (``IFCREAL(1.E400)`` reads as inf) is echoed as the text
    'inf' -- ``intent.json`` stays strictly parseable (no ``Infinity``)."""
    cases = [
        ("BusRating", ("IFCPROPERTYSINGLEVALUE('BusRating',$,IFCREAL(100.),$)",
                       "IFCPROPERTYSINGLEVALUE('BusRating',$,IFCLABEL('100A'),$)"), "LP-1", ("mains_a", 100.0)),
        ("NumberOfCircuits", ("IFCPROPERTYSINGLEVALUE('NumberOfCircuits',$,IFCINTEGER(42),$)",
                              "IFCPROPERTYSINGLEVALUE('NumberOfCircuits',$,IFCLABEL('30 ckt'),$)"), "LP-1", ("spaces", 30)),
        ("Phases", ("#69=IFCPROPERTYSINGLEVALUE('Phases',$,IFCINTEGER(3),$)",
                    "#69=IFCPROPERTYSINGLEVALUE('Phases',$,IFCLABEL('3 ph'),$)"), "LP-1", ("mains_a", 100.0)),
        ("Wires", ("#70=IFCPROPERTYSINGLEVALUE('Wires',$,IFCINTEGER(4),$)",
                   "#70=IFCPROPERTYSINGLEVALUE('Wires',$,IFCREAL(1.E400),$)"), "LP-1", ("mains_a", 100.0)),
        ("MountingHeight", ("#94=IFCPROPERTYSINGLEVALUE('MountingHeight',$,IFCREAL(44.),$)",
                            "#94=IFCPROPERTYSINGLEVALUE('MountingHeight',$,IFCLABEL('1100 mm'),$)"), "R-1",
         ("mounting_height_in", pytest.approx(1100 / 25.4))),
        ("Load", ("#93=IFCPROPERTYSINGLEVALUE('Load',$,IFCREAL(180.),$)",
                  "#93=IFCPROPERTYSINGLEVALUE('Load',$,IFCREAL(1.E400),$)"), "R-1", ("va", I.DEFAULT_DEVICE_VA)),
        # review of #457: TEXT zeros / blanks read as empty cells, silently (no note, no raw string)
        ("MainsRating=0", ("IFCPROPERTYSINGLEVALUE('MainsRating',$,IFCREAL(100.),$)",
                           "IFCPROPERTYSINGLEVALUE('MainsRating',$,IFCLABEL('0 A'),$)"), "LP-1", ("mains_a", 100.0)),
        ("Phases=blank", ("#69=IFCPROPERTYSINGLEVALUE('Phases',$,IFCINTEGER(3),$)",
                          "#69=IFCPROPERTYSINGLEVALUE('Phases',$,IFCLABEL('  '),$)"), "LP-1", ("mains_a", 100.0)),
        ("NumberOfCircuits=0", ("IFCPROPERTYSINGLEVALUE('NumberOfCircuits',$,IFCINTEGER(42),$)",
                                "IFCPROPERTYSINGLEVALUE('NumberOfCircuits',$,IFCLABEL('-0 ckt'),$)"), "LP-1", ("spaces", 42)),
    ]
    for key, swap, tag, (kw, want) in cases:
        hand = _retyped(our_ifc, str(tmp_path / f"{key}.ifc"), swap)
        model = I.resolve_intent(hand)                                # never raises
        plan = model.plan_for(tag)
        assert plan.status == "resolved", (key, plan.status, plan.refusal)
        assert plan.kwargs[kw] == want, (key, plan.kwargs)
        sched = [n for n in plan.notes if "Schedule." in n]
        if "=" in key:                                                # an empty cell: silent
            assert sched == [], (key, plan.notes)
        else:
            assert len(sched) == 1 and f"Schedule.{key} " in sched[0], (key, plan.notes)
        for e in model.equipment:                                     # no raw string left to cast, anywhere
            assert not [k for k in I.CONTRACT_SCALARS if isinstance(e.contract.get(k), str)], (key, e.tag)
        assert all(isinstance(f.rating_a, (int, float, type(None))) for f in model.feeders), key
        js = json.dumps(I.intent_to_json(model), allow_nan=False, default=str)   # strict: no Infinity / NaN
        if key in ("Wires", "Load"):
            eq = next(e for e in model.equipment if e.tag == tag)
            pset = "PanelSchedule" if key == "Wires" else I.DEVICE_PSET
            assert eq.psets[pset][key] == "inf" and "'inf' is not a usable" in sched[0]
            assert '"inf"' in js
        assert {p.status for p in model.family_plans} == {"resolved"}, key

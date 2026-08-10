"""test_intent_faulted.py -- a planning FAULT is distinguishable from a fact
REFUSAL (issue #462, follow-up of #442).

``rvt.ifc.intent.plan_families`` carries a per-item backstop: an unexpected
exception out of ``plan_family_for(e)`` never propagates; THAT item is
recorded, not built, and every other item still plans (rule 1).  #442 folded
that record into the policy word ``'refused'`` -- the same status an honest
``FactoryError`` earns when the catalog has no member for a rating -- so
``family_plans_by_status`` could not tell a resolver **bug** from missing
**facts**, and the build's degradation line told the user to "supply the
missing facts" for a traceback in our code.  Now the backstop says
``'faulted'`` (refusal text unchanged), ``summarize()`` counts it apart, and
``frontdoor.build`` words it as a resolver fault to report.  Deliverables are
unchanged: statuses are labels, never refusal logic.

Sample-free (hand-built records, the famgen catalog, OUR bundled example IFCs,
the bundled steplite reader, the pinned genesis base); no file here is claimed
to load in Revit (rule 4).

Run: .venv/bin/python -m pytest tests/test_intent_faulted.py -q
"""
from __future__ import annotations

import os
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.ifc import intent as I                      # noqa: E402
from rvt.frontdoor import intent as FI               # noqa: E402
from rvt.frontdoor import prompt_intent as PP        # noqa: E402
from conftest import pinned_base                     # noqa: E402

OUR_IFCS = [os.path.join(ROOT, "inputs", "ifc", n)
            for n in ("electrical-room-2500a.ifc", "chicago-plenum-downlight.ifc")]
#: the prompt fixtures the front-door suites build from (test_frontdoor.py,
#: test_intent_device_plan.py, test_intent_schedule_scalars.py, the README demo)
PROMPTS = [
    "an electrical room with 6 panels",
    "an electrical room 30x20 ft rated for 2500 A service with a main switchboard, "
    "two 400 A distribution panels and four lighting panels",
    "a two storey electrical building 40 by 30 ft, floor to floor 14 ft, with a "
    "main switchboard and four lighting panels on level 2",
    "electrical room 30x20 ft with a 2000A main switchboard, two 400A "
    "distribution panels and four lighting panels",
    "an electrical room with a 100 A lighting panel and 4 duplex receptacles at 44 in AFF",
    "a room with 4 duplex receptacles",
    "an electrical room with a 400 A distribution panel and a 75 kVA transformer",
]
#: one item resolves, one is an honest FACT refusal (no 5000 kVA member in the
#: dry-type catalog), one is made to FAULT by the test
FAULT_PROMPT = ("an electrical room with a 400 A distribution panel, a 5000 kVA transformer "
                "and 4 duplex receptacles")
FAULT_WORDS = "(a resolver bug; the file is delivered without this item -- please report it)"
FACTS_HINT = "supply the missing facts or choose a covered rating"


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_device_facts("duplex-receptacle")
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=400, spaces=42,
                                   voltage="480Y/277", mcb=True, mounting="surface",
                                   panel_name="X")
        F.resolve_transformer_facts(75.0, vendor="eaton", primary_v=480, secondary_v="208Y/120")
        return True
    except Exception:                                    # noqa: BLE001
        return False


needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")


def _boom(fp):
    raise RuntimeError("resolver bug (unit test)")


# ---------------------------------------------------------------------------
# 1. the table: a fault is 'faulted', a fact refusal stays 'refused'
# ---------------------------------------------------------------------------

@needs_catalog
def test_a_fault_is_faulted_a_fact_refusal_stays_refused_and_the_counts_tell_them_apart(monkeypatch):
    """The device resolver is forced to raise: the receptacles' shared plan is
    'faulted' with the exception as its reason; the 5000 kVA transformer is
    an honest catalog refusal ('refused', the factory's own words); DP-1
    resolves.  Nothing propagates, only DP-1 is buildable, and
    ``family_plans_by_status`` counts the three apart."""
    model, _cov = PP.prompt_to_intent(FAULT_PROMPT)                  # unpatched: the honest picture
    assert FI.summarize(model)["family_plans_by_status"] == {"resolved": 5, "refused": 1}
    devices = [e for e in model.equipment if e.kind == "receptacle_device"]

    monkeypatch.setattr(I, "_resolve_device_facts", _boom)
    with pytest.raises(RuntimeError):
        I.plan_family_for(devices[0])                                # the branch itself does raise ...
    plans = {p.tag: p for p in I.plan_families(model.equipment)}     # ... the table never does
    assert plans["DP-1"].status == "resolved"
    t1 = plans["T1"]
    assert t1.status == "refused" and t1.refusal.startswith("FactoryError: no variant match")
    for e in devices:
        p = plans[e.tag]
        assert p.status == "faulted", (e.tag, p.status)
        assert p.refusal == "RuntimeError: resolver bug (unit test)"      # refusal text unchanged
        assert (p.constructor, p.kwargs) == ("", {})
        assert len(p.notes) == 1 and "a resolver fault, not a fact refusal" in p.notes[0]
    model.family_plans = list(plans.values())
    assert [p.tag for p in FI.buildable_family_plans(model)] == ["DP-1"]   # the gates need no change
    assert FI.summarize(model)["family_plans_by_status"] == {"resolved": 1, "refused": 1, "faulted": 4}


# ---------------------------------------------------------------------------
# 2. the product path: delivered either way; the FAULT is worded as one
# ---------------------------------------------------------------------------

@needs_catalog
def test_the_front_door_delivers_and_words_a_fault_as_a_resolver_bug_not_missing_facts(monkeypatch, tmp_path):
    """Through ``FD.author``: the transformer branch is forced to raise.  The
    job is still delivered (combined .rvt on disk, ok, no errors, DP-1 built
    and placed); ``build.degradations`` carries the planning-FAULT wording
    for T1 -- never the facts hint -- ``MANIFEST.md`` renders it, and the
    summary counts ``{'faulted': 1, ...}``.  The honest 5000 kVA refusal in
    the same job keeps the facts hint."""
    pinned_base(2026)                                                # the certified pin, or a clean skip
    import rvt.frontdoor as FD
    real = I._resolve_xfmr_facts

    def faulty(fp):
        if fp.kwargs.get("kva") == 75.0:
            raise RuntimeError("resolver bug (unit test)")
        real(fp)
    monkeypatch.setattr(I, "_resolve_xfmr_facts", faulty)
    r = FD.author(prompt="an electrical room with a 400 A distribution panel, a 75 kVA transformer "
                         "and a 5000 kVA transformer", out=str(tmp_path / "job"), no_handoff=True)
    assert r.route == "prompt" and r.ok and r.errors == [], (r.status, r.errors)
    combined = r.files.get("combined")
    assert combined and os.path.isfile(combined) and os.path.getsize(combined) > 0
    build = r.manifest["build"]
    assert build["errors"] == []
    assert r.manifest["intent"]["summary"]["family_plans_by_status"] == {
        "resolved": 1, "faulted": 1, "refused": 1}
    plans = {p["tag"]: p for p in r.manifest["intent"]["summary"]["family_plans"]}
    faulted = next(t for t, p in plans.items() if p["status"] == "faulted")
    refused = next(t for t, p in plans.items() if p["status"] == "refused")
    fault_line = next(d for d in build["degradations"] if d.startswith(f"{faulted} ("))
    assert fault_line == (f"{faulted} (transformer): NOT built -- planning FAULT: RuntimeError: "
                          f"resolver bug (unit test) {FAULT_WORDS}")
    assert FACTS_HINT not in fault_line
    refusal_line = next(d for d in build["degradations"] if d.startswith(f"{refused} ("))
    assert "family plan refused: FactoryError" in refusal_line and FACTS_HINT in refusal_line
    assert "FAULT" not in refusal_line
    kinds = [c["kind"] for c in build["elements_created"]]
    assert kinds.count("equipment-instance") == 1 and kinds.count("family(.rfa)") == 1   # DP-1 only
    with open(r.manifest_paths["md"], encoding="utf-8") as fh:
        md = fh.read()
    assert f"- **degradation**: {fault_line}" in md


# ---------------------------------------------------------------------------
# 3. the shard tripwire: nothing WE ship faults
# ---------------------------------------------------------------------------

@needs_catalog
def test_no_plan_is_faulted_on_the_prompt_fixtures_or_our_ifcs(tmp_path):
    """'faulted' means a resolver bug.  Every prompt fixture the front-door
    suites build from, OUR bundled example IFCs, and OUR IFC round trip
    (prompt -> intent -> IFC4 -> intent) plan without one -- so a genuine
    fault stays loud in CI instead of hiding among honest refusals."""
    from rvt.frontdoor.ifc_out import write_intent_ifc
    seen, models = {}, {}
    for prompt in PROMPTS:
        models[prompt], _cov = PP.prompt_to_intent(prompt)
        assert models[prompt].family_plans, prompt
        seen[prompt] = FI.summarize(models[prompt])["family_plans_by_status"]
    for path in OUR_IFCS:
        seen[os.path.basename(path)] = FI.summarize(FI.intent_from_ifc(path))["family_plans_by_status"]
    rt = write_intent_ifc(models[PROMPTS[4]], str(tmp_path / "rt.ifc"))  # LP-1 + 4 receptacles
    seen["round-trip"] = FI.summarize(FI.intent_from_ifc(rt))["family_plans_by_status"]
    assert seen["round-trip"]                                            # it did plan something
    # no fault anywhere -- and the word is reserved for the backstop: no branch says it
    for k, v in seen.items():
        assert set(v) <= {"resolved", "house", "refused", "unmapped"}, (k, v)


def test_the_backstop_needs_no_catalog_to_fault_honestly(monkeypatch):
    """Catalog or not: an item whose planning raises is 'faulted' with
    ``Type: message`` as its refusal, and its neighbour (an unmapped kind,
    which never touches the catalog) still plans."""
    def eq(tag, kind):
        return I.Equipment(step_id=0, guid=tag, ifc_class="IfcFlowTerminal", predefined_type=None,
                           name=tag, tag=tag, description=None, object_type=None, type_name=None,
                           kind=kind, psets={}, contract={}, placement=I.Placement(np.eye(4)),
                           geometry=I.ProductGeometry(items=[]))
    monkeypatch.setattr(I, "_resolve_device_facts", _boom)
    plans = I.plan_families([eq("GB-1", "ground_bus"), eq("R-1", "receptacle_device")])
    assert [(p.tag, p.status) for p in plans] == [("GB-1", "unmapped"), ("R-1", "faulted")]
    assert plans[1].refusal == "RuntimeError: resolver bug (unit test)" and plans[0].refusal
    model = I.IntentModel(source_path="unit", schema="unit", project_name="unit", length_scale_m=1.0,
                          levels=[], equipment=[], other_products=[], room=None, clearances=[],
                          feeders=[], conduit_runs=[], family_plans=plans, audit={})
    assert FI.buildable_family_plans(model) == []
    assert FI.summarize(model)["family_plans_by_status"] == {"unmapped": 1, "faulted": 1}

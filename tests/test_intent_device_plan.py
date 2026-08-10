"""test_intent_device_plan.py -- the resolver's OWN device mapping (issue #397).

``rvt.ifc.intent.plan_family_for`` maps a ``receptacle_device`` itself: the
constructor is OUR ``rvt.famgen.factory.make_device``, the kwargs come from
the equipment's ``DeviceSchedule`` pset (kind / mounting_height_in / voltage /
va), the facts from ``generic/devices-and-mounting`` -- exactly the plan the
front door's ``prompt_intent._plan_device`` used to bolt on through a seam
(#166 / #359).  The seam is gone: the prompt route's plans ARE
``plan_families(equipment)``, ``frontdoor.intent.intent_from_ifc`` is the bare
resolver, and anything that calls ``resolve_intent`` directly (the
``tools/ifc_intent.py intent`` CLI, research probes) sees ``IfcOutlet``
products as ``resolved make_device`` instead of ``unmapped``.

#438: a hand-typed ``Load`` ('180 VA', 'abc') coerces or degrades that ONE
device with a note and the ``--ifc`` route still delivers (rule 1); a 1-pole
device on a wye system books the line-to-neutral leg on both routes.

Sample-free (the famgen catalog + the bundled steplite reader); no file here
is claimed to load in Revit (rule 4).

Run: .venv/bin/python -m pytest tests/test_intent_device_plan.py -q
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys

import numpy as np
import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.ifc import intent as I                      # noqa: E402
from rvt.frontdoor import intent as FI               # noqa: E402
from rvt.frontdoor import prompt_intent as PP        # noqa: E402

DONE_PROMPT = "a room with 4 duplex receptacles on a 20A circuit"
RT_PROMPT = "an electrical room with a 100 A lighting panel and 4 duplex receptacles at 44 in AFF"


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_device_facts("duplex-receptacle")
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=100, spaces=30,
                                    voltage="208Y/120", mcb=True, mounting="surface",
                                    panel_name="X")
        return True
    except Exception:                                    # noqa: BLE001
        return False


needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")


def _device(tag: str, schedule=None, dims=None) -> I.Equipment:
    """A hand-built ``IfcOutlet`` equipment record (no IFC file needed)."""
    e = I.Equipment(step_id=0, guid=tag, ifc_class="IfcOutlet", predefined_type="POWEROUTLET",
                    name=tag, tag=tag, description=None, object_type=None, type_name=None,
                    kind="receptacle_device",
                    psets={I.DEVICE_PSET: dict(schedule)} if schedule is not None else {},
                    contract={}, placement=I.Placement(np.eye(4)),
                    geometry=I.ProductGeometry(items=[]))
    e.dims_m = dict(dims or {})
    return e


# ---------------------------------------------------------------------------
# 1. plan_family_for maps the device itself
# ---------------------------------------------------------------------------

@needs_catalog
def test_plan_family_for_maps_a_receptacle_device_to_make_device_with_schedule_kwargs():
    eq = _device("R-1", {"Voltage": "120 V", "Phases": 1, "Wires": 2, "Load": 180.0,
                         "MountingHeight": 44.0, "DeviceType": "NEMA 5-15R Duplex Receptacle"},
                 dims={"w": 0.07, "d": 0.07, "h": 0.114})
    p = I.plan_family_for(eq)
    assert (p.tag, p.kind, p.constructor) == ("R-1", "receptacle_device",
                                              "rvt.famgen.factory.make_device")
    assert p.status == "resolved" and p.refusal is None
    assert p.kwargs == {"kind": "duplex-receptacle", "mounting_height_in": 44.0,
                        "voltage": "120", "va": 180.0}
    assert (p.catalog, p.variant) == ("generic/devices-and-mounting", "duplex-receptacle-5-15R")
    # facts: the job's height / voltage / load ride as 'given'; the envelope is 'assumed'
    fs = p.facts_summary
    assert (fs["mounting_height_in"], fs["voltage_v"], fs["load_va"]) == (44.0, 120.0, 180.0)
    assert fs["subject"] == "generic/devices-and-mounting duplex-receptacle"
    assert "plate_width_in" in fs["assumed_fields"] and "box_depth_in" in fs["assumed_fields"]
    # the modelled envelope from the generic record: a 2.75 x 4.5 in faceplate on the wall
    # face, a 2.5 in box + the 0.25 in plate into it (metres)
    IN = 0.0254
    assert {k: round(v, 5) for k, v in p.dims_catalog_m.items()} == {
        "w": round(2.75 * IN, 5), "h": round(4.5 * IN, 5), "d": round(2.75 * IN, 5)}
    assert p.dims_modeled_m == {"w": 0.07, "d": 0.07, "h": 0.114}
    # buildable: the room build generates + loads + places it (the open cell, stamped)
    model = I.IntentModel(source_path="unit", schema="unit", project_name="unit", length_scale_m=1.0,
                          levels=[], equipment=[eq], other_products=[], room=None, clearances=[],
                          feeders=[], conduit_runs=[], family_plans=[p], audit={})
    assert FI.buildable_family_plans(model) == [p]


@needs_catalog
def test_a_silent_schedule_books_the_default_row_and_a_wye_voltage_its_line_to_neutral_leg():
    # no schedule at all -> OUR duplex receptacle at 120 V / 180 VA, height from the facts' convention
    bare = I.plan_family_for(_device("R-9"))
    assert bare.status == "resolved"
    assert bare.kwargs == {"kind": I.DEFAULT_DEVICE_KIND, "mounting_height_in": None,
                           "voltage": I.DEFAULT_DEVICE_VOLTAGE, "va": I.DEFAULT_DEVICE_VA}
    assert bare.facts_summary["mounting_height_in"] == 18.0          # the record's typical (assumed)
    # a schedule voltage parses through device_voltage: a plain '277 V' -> '277'
    v277 = I.plan_family_for(_device("R-2", {"Voltage": "277 V", "Load": 0, "MountingHeight": 96}))
    assert v277.kwargs["voltage"] == "277" and v277.kwargs["va"] == I.DEFAULT_DEVICE_VA   # Load 0 -> unit load
    assert v277.kwargs["mounting_height_in"] == 96 and v277.facts_summary["voltage_v"] == 277.0
    assert v277.notes == []                                            # a silent / zero load leaves no note
    # DELIBERATE CHANGE (#438): a wye SYSTEM voltage on a 1-pole receptacle books its
    # line-to-NEUTRAL leg ('208Y/120' -> '120') -- make_device builds ONE 1-pole connector,
    # and a duplex receptacle on a 208Y/120 board sits phase-to-neutral; #397 had inherited
    # the L-L '208' here while the prompt route (_device_voltage) already booked L-N.
    wye = I.plan_family_for(_device("R-3", {"Voltage": "208Y/120", "Load": 360.0, "MountingHeight": 18.0}))
    assert (wye.kwargs["voltage"], wye.kwargs["va"]) == ("120", 360.0)
    assert (wye.facts_summary["voltage_v"], wye.facts_summary["load_va"]) == (120.0, 360.0)
    # ... only a schedule that SAYS 2-pole (Poles / Phases >= 2) takes the line-to-line
    two_pole = I.plan_family_for(_device("R-4", {"Voltage": "208Y/120", "Poles": 2, "Load": 360.0}))
    assert two_pole.kwargs["voltage"] == "208"
    assert I.plan_family_for(_device("R-5", {"Voltage": "208Y/120 V", "Phases": "2"})).kwargs["voltage"] == "208"
    assert I.plan_family_for(_device("R-6", {"Voltage": "208Y/120", "Phases": 1, "Wires": 2})).kwargs["voltage"] == "120"
    # plan_families keeps one plan per item, in order, boards and devices alike
    plans = I.plan_families([_device("R-1", {"MountingHeight": 18.0}), _device("R-2", {"MountingHeight": 44.0})])
    assert [(p.tag, p.status, p.kwargs["mounting_height_in"]) for p in plans] == [
        ("R-1", "resolved", 18.0), ("R-2", "resolved", 44.0)]


def test_the_prompt_route_and_the_plan_book_one_device_voltage():
    """``prompt_intent._device_voltage`` IS ``intent.device_voltage`` (#438):
    the clause voltage a prompted receptacle carries onto its DeviceSchedule
    and the voltage plan_family_for books from that schedule are the same
    figure for every spelling -- L-N of a wye system, a plain number as is,
    the 120 V default row otherwise."""
    for said, want in (("208Y/120", "120"), ("480Y/277 V", "277"), ("277 V", "277"),
                       ("120", "120"), (None, "120"), ("low voltage", "120")):
        item = PP.PromptItem(kind="receptacle_device", tag="R-1", voltage=said)
        assert PP._device_voltage(item) == I.device_voltage(said) == want, said
        assert I.device_voltage(said, poles=1) == want
    assert I.device_voltage("208Y/120", poles=2) == "208" and I.device_voltage("480Y/277", poles="3") == "480"
    assert I.device_voltage("208Y/120", poles="n/a") == "120"           # an unreadable pole count = 1-pole


def test_a_unit_suffixed_load_coerces_and_a_bad_load_degrades_that_one_device_with_a_note():
    """``DeviceSchedule.Load`` as a person types it (#438): '180 VA' / '180VA' /
    '0.18 kVA' coerce to VA (a text label leaves ONE note saying so); 'abc',
    a negative, NaN or an absurd figure fall back to the default unit load with
    ONE note naming the property and the value -- never an exception."""
    D = I.DEFAULT_DEVICE_VA
    for raw, want in (("180 VA", 180.0), ("180VA", 180.0), ("180", 180.0), (" 360 va ", 360.0),
                      ("0.18 kVA", 180.0), ("1.5kva", 1500.0), ("1.5e2 VA", 150.0)):
        va, note = I.parse_device_load(raw)
        assert va == want, raw
        assert note.startswith(f"DeviceSchedule.Load {raw!r} is a text label") and f"read as {want:g} VA" in note
    for raw in (180, 180.0, 360.5):                                    # a real measure: as is, silently
        assert I.parse_device_load(raw) == (float(raw), None)
    for raw in (None, "", "  ", 0, 0.0, "0", "0 VA"):                  # absent / zero: the unit load, silently
        assert I.parse_device_load(raw) == (D, None), raw
    for raw, why in (("abc", "not a number"), ("180 W", "not a number"), ("nan", "not a number"),
                     (True, "not a number"), ([180], "not a number"),
                     (-5, "negative"), ("-5 VA", "negative"),
                     (float("nan"), "not finite"), (float("inf"), "not finite"),
                     (1e12, "sanity cap"), ("1e12", "sanity cap"), ("101 kVA", "sanity cap")):
        va, note = I.parse_device_load(raw)
        assert va == D, raw
        assert note.startswith(f"DeviceSchedule.Load {raw!r} is not a usable apparent load (") and why in note
        assert f"books the default {D:g} VA" in note
    assert I.parse_device_load(I.MAX_DEVICE_VA) == (I.MAX_DEVICE_VA, None)   # the cap itself is a load


@needs_catalog
def test_plan_family_for_never_raises_on_a_bad_load_and_records_one_note():
    ok = I.plan_family_for(_device("R-1", {"Voltage": "120 V", "Load": "180 VA", "MountingHeight": 44.0}))
    assert ok.status == "resolved" and ok.kwargs["va"] == 180.0 and ok.facts_summary["load_va"] == 180.0
    assert len(ok.notes) == 1 and "'180 VA' is a text label" in ok.notes[0]
    kva = I.plan_family_for(_device("R-2", {"Load": "0.36 kVA"}))
    assert kva.kwargs["va"] == 360.0 and kva.facts_summary["load_va"] == 360.0
    for bad in ("abc", -5, float("nan"), 1e12):                        # the issue's four: text, negative, NaN, absurd
        p = I.plan_family_for(_device("R-3", {"Voltage": "120 V", "Load": bad, "MountingHeight": 18.0}))
        assert p.status == "resolved" and p.refusal is None, bad       # degraded, not refused: it is built
        assert p.kwargs["va"] == I.DEFAULT_DEVICE_VA and p.facts_summary["load_va"] == I.DEFAULT_DEVICE_VA
        assert len(p.notes) == 1 and repr(bad) in p.notes[0], p.notes   # ONE note, naming the value
        assert p.as_json()["notes"] == p.notes                          # ... and it rides into intent.json
    # plan_families over a mixed list: every item planned, nothing raised, notes only where earned
    plans = I.plan_families([_device("R-1", {"Load": 180.0}), _device("R-2", {"Load": "abc"}),
                             _device("R-3", {"Load": "180 VA"}), _device("R-4", {})])
    assert [(p.tag, p.status, p.kwargs["va"], len(p.notes)) for p in plans] == [
        ("R-1", "resolved", 180.0, 0), ("R-2", "resolved", 180.0, 1),
        ("R-3", "resolved", 180.0, 1), ("R-4", "resolved", 180.0, 0)]


def test_a_facts_refusal_is_recorded_not_raised(monkeypatch):
    """The twin of ``_resolve_panel_facts``: a resolver refusal marks the plan
    'refused' with the resolver's own words; nothing buildable, nothing raised."""
    from rvt.famgen import factory as F

    def boom(*_a, **_k):
        raise F.FactoryError("no device record on file (unit test)")
    monkeypatch.setattr(F, "resolve_device_facts", boom)
    p = I.plan_family_for(_device("R-1", {"MountingHeight": 18.0}))
    assert p.constructor == "rvt.famgen.factory.make_device"
    assert p.status == "refused" and p.refusal == "FactoryError: no device record on file (unit test)"
    assert p.catalog is None and p.dims_catalog_m == {}
    model = I.IntentModel(source_path="unit", schema="unit", project_name="unit", length_scale_m=1.0,
                          levels=[], equipment=[], other_products=[], room=None, clearances=[],
                          feeders=[], conduit_runs=[], family_plans=[p], audit={})
    assert FI.buildable_family_plans(model) == []


# ---------------------------------------------------------------------------
# 2. the seam is gone: one mapping, owned by the intent layer
# ---------------------------------------------------------------------------

def test_the_front_door_device_seam_is_deleted_not_duplicated():
    for name in ("plan_devices", "_plan_device", "_resolve_device_facts"):
        assert not hasattr(PP, name), f"prompt_intent.{name} should live in rvt.ifc.intent now"
    assert "plan_devices" not in PP.__all__
    assert callable(I._resolve_device_facts) and "plan_family_for" in I.__all__
    # the schedule pset name + the default device row have ONE source (the resolver)
    assert PP.DEVICE_PSET is I.DEVICE_PSET == "DeviceSchedule"
    assert (PP.DEFAULT_DEVICE_KIND, PP.DEFAULT_DEVICE_VOLTAGE, PP.DEFAULT_DEVICE_VA) == (
        I.DEFAULT_DEVICE_KIND, I.DEFAULT_DEVICE_VOLTAGE, I.DEFAULT_DEVICE_VA)


def test_the_room_builder_labels_a_device_without_the_front_doors_prompt_layer():
    """Layering, observed in a fresh interpreter: ``tools/ifc_intent.py``
    labels a placed Electrical Fixture (``_instance_labels`` -> its schedule
    row) with the resolver's ``DEVICE_PSET`` -- it no longer imports
    ``rvt.frontdoor.prompt_intent`` to do it (the last thread of the seam)."""
    probe = (
        "import importlib.util, sys, types\n"
        f"spec = importlib.util.spec_from_file_location('_room', {os.path.join(ROOT, 'tools', 'ifc_intent.py')!r})\n"
        "m = importlib.util.module_from_spec(spec); sys.modules[spec.name] = m; spec.loader.exec_module(m)\n"
        "eq = types.SimpleNamespace(psets={'DeviceSchedule': {'Load': 180.0, 'MountingHeight': 18.0}})\n"
        "lab = m._instance_labels(eq, m.OST_ELECTRICAL_FIXTURES)\n"
        "assert lab == {'created_kind': 'fixture-instance', 'schedule': {'Load': 180.0, 'MountingHeight': 18.0}}, lab\n"
        "assert m._instance_labels(eq, -2001040) == {'created_kind': 'equipment-instance'}\n"
        "print('prompt_layer_loaded=' + str('rvt.frontdoor.prompt_intent' in sys.modules))\n")
    res = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, cwd=ROOT,
                         env={**os.environ, "PYTHONPATH": os.path.join(ROOT, "src")}, timeout=120)
    assert res.returncode == 0, res.stderr[-2000:]
    assert res.stdout.strip().endswith("prompt_layer_loaded=False"), res.stdout


@needs_catalog
def test_the_prompt_routes_device_plans_are_plan_families_verbatim():
    model, _ = PP.prompt_to_intent(DONE_PROMPT)
    assert [e.kind for e in model.equipment] == ["receptacle_device"] * 4
    again = I.plan_families(model.equipment)
    assert [p.as_json() for p in model.family_plans] == [p.as_json() for p in again]
    assert {p.status for p in again} == {"resolved"} and {p.constructor for p in again} == {
        "rvt.famgen.factory.make_device"}
    assert model.audit["family_plans"] == {f"R-{i}": "resolved" for i in range(1, 5)}


# ---------------------------------------------------------------------------
# 3. the bare resolver (and its CLI) map IfcOutlet on the --ifc route
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def our_ifc(tmp_path_factory):
    """OUR IFC of a lighting panel + 4 receptacles at 44 in AFF (IfcOutlet x4)."""
    if not _catalog_ok():
        pytest.skip("famgen catalog absent")
    from rvt.frontdoor.ifc_out import write_intent_ifc
    model, _ = PP.prompt_to_intent(RT_PROMPT)
    return write_intent_ifc(model, str(tmp_path_factory.mktemp("rt") / "rt.ifc"))


def test_resolve_intent_maps_ifcoutlet_devices_without_the_front_door(our_ifc):
    back = I.resolve_intent(our_ifc)                    # the BARE resolver, no front-door wrapper
    assert {e.tag: e.kind for e in back.equipment} == {
        "LP-1": "lighting_panelboard", "R-1": "receptacle_device", "R-2": "receptacle_device",
        "R-3": "receptacle_device", "R-4": "receptacle_device"}
    assert {p.tag: p.status for p in back.family_plans} == {t: "resolved" for t in
                                                            ("LP-1", "R-1", "R-2", "R-3", "R-4")}
    for tag in ("R-1", "R-2", "R-3", "R-4"):
        pl = back.plan_for(tag)
        assert pl.constructor.endswith("make_device") and pl.variant == "duplex-receptacle-5-15R"
        assert pl.kwargs == {"kind": "duplex-receptacle", "mounting_height_in": 44.0,
                             "voltage": "120", "va": 180.0}
    # the front door's --ifc route is the same resolver, plan for plan
    fd = FI.intent_from_ifc(our_ifc)
    assert [p.as_json() for p in fd.family_plans] == [p.as_json() for p in back.family_plans]
    assert FI.summarize(fd)["family_plans_by_status"] == {"resolved": 5}
    # ... and its CLI says so: `tools/ifc_intent.py intent <ifc>` -> 'map R-1 -> resolved make_device'
    from rvt.frontdoor import build as BLD
    R = BLD.load_ifc_room_module()
    buf = io.StringIO()
    out_json = os.path.join(os.path.dirname(our_ifc), "cli.intent.json")
    with contextlib.redirect_stdout(buf):
        rc = R.main(["intent", our_ifc, "-o", out_json])
    out = buf.getvalue()
    assert rc == 0 and os.path.isfile(out_json)
    maps = [ln.split() for ln in out.splitlines() if ln.strip().startswith("map ")]
    assert [(m[1], m[3], m[4]) for m in maps] == [("LP-1", "resolved", "make_panelboard")] + [
        (f"R-{i}", "resolved", "make_device") for i in range(1, 5)]
    assert "unmapped" not in out


# ---------------------------------------------------------------------------
# 4. rule 1 on the --ifc route: one bad schedule cell degrades one device,
#    the project file is still delivered (#438)
# ---------------------------------------------------------------------------

PINNED_2026 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")


def _hand_edited_ifc(src: str, dst: str, *loads: str) -> str:
    """Copy OUR IFC with the first len(loads) ``Load`` cells retyped the way a
    person hand-authors them: ``IFCLABEL('180 VA')`` instead of ``IFCREAL(180.)``."""
    text = open(src, encoding="ascii").read()
    for lab in loads:
        assert "IFCPROPERTYSINGLEVALUE('Load',$,IFCREAL(180.),$)" in text
        text = text.replace("IFCPROPERTYSINGLEVALUE('Load',$,IFCREAL(180.),$)",
                            f"IFCPROPERTYSINGLEVALUE('Load',$,IFCLABEL('{lab}'),$)", 1)
    with open(dst, "w", encoding="ascii", newline="") as fh:
        fh.write(text)
    return dst


def test_a_hand_typed_load_label_no_longer_fails_the_ifc_route(our_ifc, tmp_path):
    """Before #438 ``Load IFCLABEL('180 VA')`` raised ``ValueError: could not
    convert string to float`` out of plan_families and the whole route ended
    FAILED, rc 3, no .rvt.  Now: '180 VA' coerces (one note), 'abc' degrades
    that ONE device to the unit load (one note), every device is still planned,
    generated, loaded and placed, and the combined file is DELIVERED, stamped,
    validator 0 errors (rule 1; no Revit-load claim -- rule 4)."""
    if not os.path.isfile(PINNED_2026):
        pytest.skip("bundled genesis base missing")
    import rvt.frontdoor as FD
    bad = _hand_edited_ifc(our_ifc, str(tmp_path / "hand.ifc"), "180 VA", "abc")
    # the bare resolver first: nothing raises, two notes earned, kwargs unchanged
    model = FI.intent_from_ifc(bad)
    devs = [model.plan_for(f"R-{i}") for i in range(1, 5)]
    assert {p.status for p in devs} == {"resolved"}
    assert [p.kwargs["va"] for p in devs] == [180.0] * 4
    notes = sorted(n for p in devs for n in p.notes)
    assert len(notes) == 2, notes
    assert notes[0].startswith("DeviceSchedule.Load '180 VA' is a text label") and "read as 180 VA" in notes[0]
    assert notes[1].startswith("DeviceSchedule.Load 'abc' is not a usable apparent load (not a number)")
    # the product path: delivered, stamped, 0 validator errors, no degradation, 4 placed devices
    r = FD.author(ifc=bad, out=str(tmp_path / "job"))
    assert r.route == "ifc" and r.ok and r.errors == [], (r.status, r.errors)
    assert "PROOF-ONLY" in r.status
    combined = r.files.get("combined")
    assert combined and os.path.isfile(combined) and os.path.getsize(combined) > 0
    build = r.manifest["build"]
    assert build["errors"] == [] and build["degradations"] == []
    assert build["validation"]["combined"]["validate"]["n_errors"] == 0
    assert [c["kind"] for c in build["elements_created"]].count("fixture-instance") == 4
    assert r.manifest["intent"]["summary"]["family_plans_by_status"] == {"resolved": 5}
    with open(r.intent_json, encoding="utf-8") as fh:
        on_disk = json.load(fh)["familyMapping"]
    assert sorted(n for p in on_disk for n in p["notes"]) == notes       # the two notes ride into intent.json

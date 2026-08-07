"""Tests for rvt.mep.conduit — conduit / cable-tray CRUD (MEP stream: conduit).

Ground truth is the Revit MEP sample (samples/rmebasicsampleproject.rvt):
20 ``RbsConduitCurve`` in 8 ``ConduitRun``s, joined by 13 elbow
``FamilyInstance``s, every curve owning a ``SegmentCenterLine`` and every
elbow a ``ConduitFittingCenterLine``.  The tests prove:

  (a) the DECODED MODEL — level-relative end offsets, the two end connectors,
      the size table (nominal -> inner/outer/bend radius), the elbow frame
      formula (X = unit(C - A_end), Y = unit(B_end - C), Z = X x Y) reproducing
      every real elbow, the shared per-configuration geometry-symbol clone;
  (b) the CREATE planner — a 3-segment path with two elbows is referentially
      closed, its connector graph MUTUAL, trims = bendRadius + extension,
      every record serialises; a straight run; the cable-tray class morph;
  (c) the MODIFY / DELETE planners built on rvt.manipulate.
"""
import math
import os

import pytest

from rvt.mep import conduit as C
from rvt.mutate import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

LEVEL1 = 378117
TYPE_RNC80 = 662478
ELBOW_CLONE = 679082           # the 2" 90-degree elbow geometry-symbol clone
ELBOW_MASTER = 662459          # 'Conduit Elbow: Standard' (the type's m_idDefaultElbow)
XFMR = 624416                  # transformer tapped by conduit 678659 (surface connector)

pytestmark = pytest.mark.skipif(not os.path.exists(SAMPLE), reason="rme sample missing")


@pytest.fixture(scope="module")
def rme():
    return Document.from_file(SAMPLE)


@pytest.fixture()
def doc():
    return Document.from_file(SAMPLE)


def _planned_length(el) -> float:
    """Length of a planned (not yet written) curve element."""
    crv = el.obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
    return crv["m_endParams"][1] - crv["m_endParams"][0]


# ---------------------------------------------------------------------------
# (a) the decoded model
# ---------------------------------------------------------------------------
def test_inventory_finds_all_runs_and_orders_members(rme):
    inv = C.inventory_runs(rme)
    assert inv["totals"]["conduit_runs"] == 8
    assert inv["totals"]["conduits"] == 20
    assert inv["totals"]["cable_trays"] == 0 and not inv["cable_tray_runs"]
    # every conduit is inside a run (no loose conduits in this sample)
    assert inv["loose_conduits"] == []
    run = C.run_report(rme, 679090)
    assert [m["id"] for m in run["members"]] == [687998, 688027, 679071, 688029, 678659]
    assert [m["kind"] for m in run["members"]] == ["curve", "fitting", "curve", "fitting", "curve"]
    assert run["type_id"] == TYPE_RNC80
    assert abs(run["total_length_ft"] - 15.9539) < 0.01


def test_curve_offsets_are_level_relative_and_ends_are_indexed(rme):
    lz = rme._level_elevation(LEVEL1)
    for cid in rme.ids_of_class("RbsConduitCurve"):
        g = C.curve_geometry(rme, cid)
        assert g["level_id"] == LEVEL1
        # m_dOffsetStart/End = endpoint z - level elevation (exact, 20/20)
        assert abs(g["offset_start_ft"] - (g["p0"][2] - lz)) < 1e-6, cid
        assert abs(g["offset_end_ft"] - (g["p1"][2] - lz)) < 1e-6, cid
        idx = sorted(c["index"] for c in g["connectors"])
        assert idx == [0, 1], (cid, idx)
        for c in g["connectors"]:
            assert c["param"] == (0.0 if c["index"] == 0 else 1.0)
        assert g["centerline_id"] and rme.class_of(g["centerline_id"]) == "SegmentCenterLine"
        # the centre-line names its owning conduit
        assert (rme.value(g["centerline_id"]) or {}).get("m_OwnerId") == cid


def test_size_table_row_and_bend_radius(rme):
    row = C.size_row(rme, TYPE_RNC80, 2.0 / 12.0)
    assert abs(row["inner_ft"] * 12 - 1.939) < 1e-6
    assert abs(row["outer_ft"] * 12 - 2.375) < 1e-6
    assert abs(row["bend_radius_ft"] - 0.890625) < 1e-9      # = the corpus elbows' arc radius
    with pytest.raises(LookupError):
        C.size_row(rme, TYPE_RNC80, 7.0 / 12.0)              # no 7" RNC Sch 80


def _near_end(rme, cid, corner):
    g = C.curve_geometry(rme, cid)
    d0 = math.dist(g["p0"], corner)
    d1 = math.dist(g["p1"], corner)
    return (g["p0"], d0) if d0 < d1 else (g["p1"], d1)


def test_elbow_frame_formula_reproduces_every_real_elbow(rme):
    """corner C, X = unit(C - A_end) (leg on connector 1), Y = unit(B_end - C)
    (leg on connector 2), Z = X x Y  reproduce the stored m_3x3 columns; and
    every 2" elbow trims its legs by bendRadius + extension = 1.0573 ft."""
    R = 0.890625
    ext = 2.0 / 12.0
    checked = 0
    for spec in C.elbow_specimens(rme):
        fg = C.fitting_geometry(rme, spec["elbow_id"])
        a = fg["connectors"].get(1) or []
        b = fg["connectors"].get(2) or []
        if not a or not b:
            continue
        aid, bid = a[0]["m_id"], b[0]["m_id"]
        if rme.class_of(aid) != "RbsConduitCurve" or rme.class_of(bid) != "RbsConduitCurve":
            continue
        Cn = fg["corner"]
        a_end, da = _near_end(rme, aid, Cn)
        b_end, db = _near_end(rme, bid, Cn)
        X = C._unit(C._sub(Cn, a_end))
        Y = C._unit(C._sub(b_end, Cn))
        Z = C._cross(X, Y)
        m3 = fg["m3x3"]
        for i in range(3):
            assert abs(m3[i][0] - X[i]) < 1e-9, (spec["elbow_id"], "X")
            assert abs(m3[i][1] - Y[i]) < 1e-9, (spec["elbow_id"], "Y")
            assert abs(m3[i][2] - Z[i]) < 1e-9, (spec["elbow_id"], "Z")
        if spec["master_symbol_id"] == ELBOW_MASTER:
            assert abs(da - (R + ext)) < 1e-6 and abs(db - (R + ext)) < 1e-6
        checked += 1
    assert checked >= 12


def test_all_two_inch_elbows_share_one_geometry_symbol_clone(rme):
    specs = [e for e in C.elbow_specimens(rme) if e["master_symbol_id"] == ELBOW_MASTER]
    assert len(specs) == 12
    assert {e["symbol_clone_id"] for e in specs} == {ELBOW_CLONE}
    hit = C.find_elbow_specimen(rme, ELBOW_MASTER, 2.0 / 12.0)
    assert hit and hit["symbol_clone_id"] == ELBOW_CLONE
    assert C.find_elbow_specimen(rme, ELBOW_MASTER, 4.0 / 12.0) is None   # no 4" elbow drawn


# ---------------------------------------------------------------------------
# (b) create planning
# ---------------------------------------------------------------------------
def test_add_conduit_path_builds_a_closed_mutual_run(doc):
    path = [(-20.0, 30.0, 9.5), (-10.0, 30.0, 9.5), (-10.0, 38.0, 9.5), (0.0, 38.0, 9.5)]
    plan = C.add_conduit_path(doc, path, LEVEL1, TYPE_RNC80, size_ft=2.0 / 12.0)
    assert len(plan.curves) == 3 and len(plan.fittings) == 2 and len(plan.centerlines) == 5
    check = C.verify_plan_graph(doc, plan)
    assert check["ok"], check
    # run lists members in path order: conduit, elbow, conduit, elbow, conduit
    assert plan.run.obj["m_elemIdArr"] == [
        plan.curves[0].elem_id, plan.fittings[0].elem_id, plan.curves[1].elem_id,
        plan.fittings[1].elem_id, plan.curves[2].elem_id]
    # trims: 8-ft first leg becomes 8 - 1.0573; middle leg 8 - 2*1.0573
    trim = 0.890625 + 2.0 / 12.0
    lens = [_planned_length(e) for e in plan.curves]
    assert abs(lens[0] - (10.0 - trim)) < 1e-6
    assert abs(lens[1] - (8.0 - 2 * trim)) < 1e-6
    # elbow frame: X perpendicular Y, symbol == the shared clone, master = type default
    for f in plan.fittings:
        ii = f.obj["m_pInstanceInfo"]["value"]
        assert ii["m_symbolId"] == ELBOW_CLONE and f.obj["m_masterSymbolId"] == ELBOW_MASTER
        m3 = ii["m_Trf"]["m_3x3"]
        X = [m3[0][0], m3[1][0], m3[2][0]]
        Y = [m3[0][1], m3[1][1], m3[2][1]]
        assert abs(C._dot(X, Y)) < 1e-9
        # instOrigin = m_or minus the level elevation (z)
        lz = doc._level_elevation(LEVEL1)
        assert abs(f.obj["m_instOrigin"][2] - (ii["m_Trf"]["m_or"][2] - lz)) < 1e-9
    # centre-lines are owned by their curve / fitting
    for cl in plan.centerlines:
        assert cl.obj["m_OwnerId"] in {c.elem_id for c in plan.curves + plan.fittings}
        assert cl.elemrec.owner_id == cl.obj["m_OwnerId"]
    # everything serialises through rvt.encode
    for e in plan.all():
        assert doc.serialize(e) is not None, (e.elem_id, e.class_name)


def test_add_conduit_run_single_segment(doc):
    plan = C.add_conduit_run(doc, (-30.0, 40.0, 9.5), (-14.0, 40.0, 9.5), LEVEL1,
                             TYPE_RNC80, size_ft=1.0 / 12.0)
    assert plan.run and len(plan.curves) == 1 and len(plan.centerlines) == 1
    assert not plan.fittings
    cv = plan.curves[0]
    assert cv.obj["m_runId"] == plan.run.elem_id
    assert abs(cv.obj["m_dWidthOrDiameter"] * 12 - 1.0) < 1e-9
    dp = cv.obj["m_pDesignPropManager"]["value"]
    assert abs(dp["m_dInnerDiameter"] * 12 - 0.957) < 1e-6      # 1" RNC Sch 80
    assert dp["m_sCalculatedSize"] == "25 mmø"
    assert dp["m_idCenterLine"] == plan.centerlines[0].elem_id
    # open ends: only the self link on each connector
    conns = cv.obj["m_pConnectorManager"]["value"]["m_connPtrArray"]
    for c in conns:
        refs = c["value"]["m_arrRefs"]
        assert refs == [{"m_id": cv.elem_id, "m_nIndex": 1 - c["value"]["m_nIndex"],
                         "m_connType": 1}]
    assert C.verify_plan_graph(doc, plan)["ok"]
    for e in plan.all():
        assert doc.check_references(e) == []


def test_cable_tray_run_is_class_morphed_and_encodes(doc):
    plan = C.add_cable_tray_run(doc, (-30.0, 60.0, 10.5), (-10.0, 60.0, 10.5), LEVEL1,
                                width_ft=1.0, height_ft=4.0 / 12.0)
    tray = plan.curves[0]
    assert tray.class_name == "CableTray" and tray.class_id == C.CLASS_CABLE_TRAY
    assert "m_pDesignPropManager" not in tray.obj
    assert tray.obj["m_oDesignPropManager"]["value"]["m_idCenterLine"] == plan.centerlines[0].elem_id
    assert tray.obj["m_dWidthOrDiameter"] == 1.0 and abs(tray.obj["m_dHeight"] - 4 / 12) < 1e-12
    assert plan.run.class_name == "CableTrayRun" and plan.run.class_id == C.CLASS_CABLE_TRAY_RUN
    assert tray.header["m_categroryId"] == C.OST_CableTray
    steps = tray.obj["m_geomSteps"]["value"]["m_bRepFormGList"]
    assert steps[0]["ptr_class"] == "CableTrayExtrusionGStep"
    for e in plan.all():
        assert doc.serialize(e) is not None
    assert C.verify_plan_graph(doc, plan)["ok"]


# ---------------------------------------------------------------------------
# (c) modify / delete planners
# ---------------------------------------------------------------------------
def test_delete_run_removes_the_whole_closure_and_frees_the_transformer(doc):
    closure = C.run_closure(doc, 679090)
    assert closure == [678659, 679071, 679090, 687998, 688027, 688029,
                       715227, 715228, 715828, 715829, 715846]
    plans = C.delete_run(doc, 679090)
    removed = sorted({i for p in plans for i in p.ids_to_remove})
    assert removed == closure
    referrers = {r["id"] for p in plans for r in p.referrer_edits}
    assert XFMR in referrers      # conduit 678659 tapped the transformer's connector 2001


def test_delete_fitting_neutralises_conduits_and_run(doc):
    plans = C.delete_fitting(doc, 688548)
    assert sorted(plans[0].ids_to_remove) == [688548, 715230]     # elbow + its centre-line
    edited = {r["id"]: r["class"] for r in plans[0].referrer_edits}
    assert edited.get(688538) == "RbsConduitCurve"
    assert edited.get(688547) == "RbsConduitCurve"
    assert edited.get(688539) == "ConduitRun"


def test_resize_extend_retype_plans(doc):
    ps = C.resize_run(doc, 686270, 1.0 / 12.0)
    changed = {c.path: c.after for p in ps for c in p.changes}
    assert abs(changed["m_dWidthOrDiameter"] * 12 - 1.0) < 1e-9
    assert abs(changed["m_pDesignPropManager.value.m_dOuterDiameter"] * 12 - 1.315) < 1e-6
    assert changed["m_pDesignPropManager.value.m_sCalculatedSize"] == "25 mmø"
    # extend: a connected end is refused, an open end works
    with pytest.raises(Exception):
        C.extend_run(doc, 686270, 2.0, end="p0")      # p0 is on the panel's surface connector
    ps2 = C.extend_run(doc, 686514, 3.0, end="p1")      # 686514's top end is open
    lens = {c.path: c.after for p in ps2 for c in p.changes if c.path.endswith("m_endParams")}
    assert abs(lens["m_pCurveDriver.value.m_pCrv.value.m_endParams"][1] - (14.0195 + 3.0)) < 1e-3
    # retype: type id swapped on both conduits and the run
    ps3 = C.retype_run(doc, 688539, 662475)
    types = {(p.elem_id, c.path): c.after for p in ps3 for c in p.changes}
    assert types[(688538, "m_idType")] == 662475
    assert types[(688547, "m_idType")] == 662475
    assert types[(688539, "m_typeId")] == 662475


def test_move_run_translates_curves_fittings_and_centrelines(doc):
    dv = (4.0, 3.0, 0.0)
    plans = C.move_run(doc, 679175, dv)
    touched = {e.elem_id for p in plans for e in p.record_edits}
    # 3 conduits + 2 elbows + 5 centre-lines
    assert touched == {679170, 679171, 679172, 688129, 679174,
                       715217, 715229, 715830, 715831, 715832}
    # the elbow's placement moved by dv
    moved = {(p.elem_id, c.path): (c.before, c.after) for p in plans for c in p.changes}
    b, a = moved[(688129, "m_pInstanceInfo.value.m_Trf.m_or")]
    assert all(abs(a[i] - (b[i] + dv[i])) < 1e-9 for i in range(3))
    # a conduit's GLine origin moved by dv
    b, a = moved[(679172, "m_pCurveDriver.value.m_pCrv.value.m_origin")]
    assert all(abs(a[i] - (b[i] + dv[i])) < 1e-9 for i in range(3))

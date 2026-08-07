"""Electrical devices / fixture instances (MEP stream: devices).

Ground truth = the Revit MEP sample: 416/424 receptacles and 63/63 switches
stand on vertical DummyPlaneRef work planes coincident with a wall face,
410/410 lighting fixtures on horizontal DOWN-facing DummyPlaneRef ceiling
planes, floor/level devices on OnDatumPlaneRef planes bound to a level, and
multi-load circuits (471829 = 4 receptacles, 469428 = 9) close their
connector graph both ways with the panel as base + path node 0.
"""
import math
import os

import pytest

from rvt.mutate import Document
from rvt.mep import devices as D

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

LEVEL1 = 378117
LEVEL2 = 378118
RECEP_STD = 342654
RECEP_GFCI = 342652
SWITCH_1P = 343624
TROFFER = 365612
PANEL_208 = 470440
XFMR_15KVA = 621990
WALL_EAST = 573325
WALL_PARTITION = 573609
PLANE_ELEC_ROOM = 581481
CEILING_PLANE = 442678
ROOM = 573809
SPACE = 379575


@pytest.fixture(scope="module")
def rme():
    if not os.path.exists(SAMPLE):
        pytest.skip("rme sample not present")
    return Document.from_file(SAMPLE)


def _fresh():
    return Document.from_file(SAMPLE)


def _zcol(m3):
    return D._columns_from_rows(m3)[2]


# ---------------------------------------------------------------------------
# the decoded hosting model (corpus facts the module relies on)
# ---------------------------------------------------------------------------
def test_ceiling_lights_stand_on_downfacing_dummy_planes(rme):
    n = shared = 0
    planes = {}
    for i in rme.ids_of_class("FamilyInstance"):
        if rme.category_of(i) != D.OST_LightingFixtures:
            continue
        v = rme.value(i) or {}
        hid = v.get("m_hostId")
        if not (isinstance(hid, int) and hid > 0 and rme.class_of(hid) == "SketchPlane"):
            continue
        sp = rme.value(hid) or {}
        pref = (sp.get("m_oPlaneRef") or {}).get("ptr_class")
        z = _zcol(((sp.get("m_oTrf") or {}).get("value") or {}).get("m_3x3"))
        if abs(z[2]) > 0.5:                       # a horizontal (ceiling) plane
            n += 1
            planes[hid] = planes.get(hid, 0) + 1
            assert pref == "DummyPlaneRef", (i, hid, pref)
            assert z[2] < 0, "ceiling planes face DOWN"
            # the light's own Z column is the plane's -Z (rotated in-plane only)
            ii = ((v.get("m_pInstanceInfo") or {}).get("value")) or {}
            lz = _zcol((ii.get("m_Trf") or {}).get("m_3x3"))
            assert abs(lz[2] + 1.0) < 1e-6, (i, lz)
            assert v.get("m_assocLevelId") == -1 and v.get("m_workPlaneBased") is True
    shared = sum(1 for c in planes.values() if c > 1)
    assert n >= 300 and shared >= 20, (n, shared)


def test_devices_never_reference_a_ceiling_element(rme):
    """No hosting plane in the file references a Ceiling — ceiling hosting
    is by coincidence (a work plane at the ceiling underside)."""
    for spid in rme.ids_of_class("SketchPlane"):
        pref = ((rme.value(spid) or {}).get("m_oPlaneRef") or {})
        if pref.get("ptr_class") == "GeomOnPlaneRef":
            gr = ((pref.get("value") or {}).get("m_geomRef") or {})
            tgt = gr.get("m_elemId")
            if isinstance(tgt, int) and tgt > 0:
                assert rme.class_of(tgt) != "Ceiling"


def test_wall_receptacles_mostly_on_dummy_planes(rme):
    cen = D.device_census(rme)
    r = cen["Electrical Fixtures (receptacles)"]
    assert r.get("wall-plane(dummy)", 0) > 400
    assert r.get("geom-plane->SWall", 0) >= 8
    s = cen["Lighting Devices (switches / sensors)"]
    assert s == {"wall-plane(dummy)": 63}


def test_datum_plane_pattern_exists(rme):
    """OnDatumPlaneRef work planes reference a LEVEL (m_datumPlaneId)."""
    hits = 0
    for spid in rme.ids_of_class("SketchPlane"):
        pref = ((rme.value(spid) or {}).get("m_oPlaneRef") or {})
        if pref.get("ptr_class") == "OnDatumPlaneRef":
            lvl = (pref.get("value") or {}).get("m_datumPlaneId")
            assert rme.class_of(lvl) == "Level", (spid, lvl)
            hits += 1
    assert hits >= 5


def test_multi_load_circuit_model_panel_is_base_and_pathnode0(rme):
    """Every real circuit with path nodes: node 0 = the BASE (panel), the
    base connector is the LAST connector (connType 4)."""
    checked = 0
    for cid in rme.ids_of_class("RbsElectricalSystem"):
        v = rme.value(cid) or {}
        conns = (Document._conn_manager(v) or {}).get("m_connPtrArray") or []
        if len(conns) < 3:
            continue
        last = (conns[-1].get("value") or {}).get("m_arrRefs") or []
        if not (last and last[0].get("m_connType") == 4):
            continue                      # unassigned circuit (no panel)
        base = last[0]["m_id"]
        assert last[0]["m_nIndex"] >= 50000, (cid, last[0])
        node0 = (v.get("m_pathNodes") or [{}])[0]
        if node0.get("m_position") is not None:
            assert node0.get("m_elemId") == base, (cid, node0, base)
        for c in conns[:-1]:
            refs = (c.get("value") or {}).get("m_arrRefs") or []
            assert refs and refs[0]["m_connType"] == 1, (cid, refs)
        checked += 1
    assert checked >= 90, checked


def test_internal_units_match_a_real_20A_120V_circuit(rme):
    v = rme.value(471829) or {}
    assert abs(v["m_dVoltage"] - 120.0 * D.INTERNAL_PER_SI) < 1e-6
    assert abs(v["m_dApparentLoad"] - 720.0 * D.INTERNAL_PER_SI) < 1e-6
    assert v["m_dRating"] == 20.0 and v["m_nPoles"] == 1


# ---------------------------------------------------------------------------
# discovery
# ---------------------------------------------------------------------------
def test_device_symbols_and_space_lookup(rme):
    syms = {r["symbol_id"]: r for r in D.device_symbols(rme)}
    assert syms[RECEP_STD]["placed_instances"] >= 400
    assert syms[RECEP_STD]["category"] == D.OST_ElectricalFixtures
    assert syms[TROFFER]["hosting"] == "ceiling-plane"
    assert syms[SWITCH_1P]["hosting"] == "wall-plane(dummy)"
    assert D.find_device_symbol(rme, "duplex receptacle :: standard") == RECEP_STD
    assert D.space_room_at(rme, (64.0, 110.0, 4.0)) == (SPACE, ROOM)
    assert D.level_at_or_below(rme, 20.51) == LEVEL2
    assert D.level_at_or_below(rme, 1.5) == LEVEL1


# ---------------------------------------------------------------------------
# CREATE — wall devices
# ---------------------------------------------------------------------------
def test_add_wall_devices_share_a_dummy_plane():
    doc = _fresh()
    sp, r = D.add_wall_device(doc, RECEP_STD, wall=WALL_EAST, distance_along_ft=18.0,
                              elevation_ft=1.5, facing_point=(64.0, 110.0), mark="R-1")
    s = D.add_wall_device(doc, SWITCH_1P, wall=WALL_EAST, distance_along_ft=22.0,
                          elevation_ft=3.65, sketchplane=sp, mark="S-1")[0]
    assert doc.check_references(r) == [] and doc.check_references(s) == []
    assert doc.check_references(sp) == []
    pref = (sp.obj.get("m_oPlaneRef") or {})
    assert pref.get("ptr_class") == "DummyPlaneRef"
    ptrf = (sp.obj.get("m_oTrf") or {}).get("value")
    for el, mark, height in ((r, "R-1", 1.5), (s, "S-1", 3.65)):
        o = el.obj
        assert o["m_hostId"] == sp.elem_id and o["m_workPlaneBased"] is True
        assert o["m_assocLevelId"] == -1 and o["m_scheduleOnlyLevelId"] == LEVEL1
        ii = (o.get("m_pInstanceInfo") or {}).get("value") or {}
        assert ii["m_Trf"]["m_3x3"] == ptrf["m_3x3"], "device frame == plane frame"
        z = ii["m_Trf"]["m_or"][2]
        assert abs(z - (doc._level_elevation(LEVEL1) + height)) < 1e-9
        # face: the room-side face of the east wall is x = 68.916 (thickness/2 in)
        assert abs(ii["m_Trf"]["m_or"][0] - 68.9159) < 1e-3
        marks = [p for p in (((o.get("m_pParamValueSetAString") or {}).get("value") or {})
                             .get("m_paramSet") or []) if p.get("m_paramId") == D.BIP_ALL_MODEL_MARK]
        assert marks and marks[0]["m_value"] == mark
        # space / room resolved into the design property manager + parents
        dpm = ((o.get("m_pDesignPropManager") or {}).get("value") or {})
        assert dpm.get("m_idSpace") == SPACE and dpm.get("m_idRoom") == ROOM
        par = (el.header.get("m_parents") or {}).get("value") or {}
        assert {sp.elem_id, SPACE, ROOM, LEVEL1, el.elem_id} <= set(par["m_deletion"])
        assert par["m_nonDetermRegenChildren"] == [SPACE]
        assert par["m_hasNonDetermRegenChildren"] is True
        sing = D._singletons(doc)
        assert sing["units"] in par["m_regenOnly"] and sing["geo"] in par["m_regenOnly"]
        assert sing["mep_tracker"] in par["m_deferredParents"]


def test_add_wall_device_geom_face_reference():
    doc = _fresh()
    sp, r = D.add_wall_device(doc, RECEP_GFCI, wall=WALL_PARTITION,
                              distance_along_ft=3.0, elevation_ft=3.5,
                              facing_point=(64.0, 108.0), plane_ref="geom")
    pref = (sp.obj.get("m_oPlaneRef") or {})
    assert pref.get("ptr_class") == "GeomOnPlaneRef"
    gr = (pref.get("value") or {}).get("m_geomRef") or {}
    assert gr["m_elemId"] == WALL_PARTITION and gr["m_geomTag"] in (5, 6)
    assert doc.check_references(sp) == [] and doc.check_references(r) == []
    assert doc.category_of(RECEP_GFCI) == D.OST_ElectricalFixtures


# ---------------------------------------------------------------------------
# CREATE — ceiling lights
# ---------------------------------------------------------------------------
def test_ceiling_plane_and_two_lights_plus_existing_plane():
    doc = _fresh()
    cp, t1 = D.add_light_fixture(doc, TROFFER, (62.0, 110.0), ceiling_z_ft=20.51)
    t2 = D.add_light_fixture(doc, TROFFER, (66.0, 110.0), ceiling_plane=cp,
                             rotation=math.pi / 2)[0]
    p = D.add_light_fixture(doc, TROFFER, (64.5, 114.0), ceiling_plane=CEILING_PLANE)[0]
    for el in (cp, t1, t2, p):
        assert doc.check_references(el) == []
    # plane: DummyPlaneRef, normal DOWN, at the ceiling z
    trf = (cp.obj.get("m_oTrf") or {}).get("value")
    assert _zcol(trf["m_3x3"]) == (0.0, 0.0, -1.0)
    assert trf["m_or"][2] == 20.51
    pl = (((cp.obj.get("m_oPlaneRef") or {}).get("value") or {}).get("m_pPlane") or {}).get("value")
    assert pl["m_xVec"] == [1.0, 0.0, 0.0] and pl["m_yVec"] == [0.0, -1.0, 0.0]
    par = (cp.header.get("m_parents") or {}).get("value") or {}
    assert par["m_deletion"] == [cp.elem_id]           # ceiling planes depend on nothing
    # fixtures: hosted, schedule to the level at/below the fixture (troffers
    # at z 20.51 -> Level 2; the existing pendant plane at z 11.48 -> Level 1
    # by the module's default rule; pass level_id= to author otherwise)
    for el, host, lvl in ((t1, cp.elem_id, LEVEL2), (t2, cp.elem_id, LEVEL2),
                          (p, CEILING_PLANE, LEVEL1)):
        o = el.obj
        assert o["m_hostId"] == host and o["m_workPlaneBased"] is True
        assert o["m_assocLevelId"] == -1 and o["m_scheduleOnlyLevelId"] == lvl
        ii = (o.get("m_pInstanceInfo") or {}).get("value") or {}
        assert _zcol(ii["m_Trf"]["m_3x3"]) == pytest.approx((0.0, 0.0, -1.0), abs=1e-9)
    # rotation about the down normal turned troffer 2's X axis by 90 deg
    x1 = D._columns_from_rows(t1.obj["m_pInstanceInfo"]["value"]["m_Trf"]["m_3x3"])[0]
    x2 = D._columns_from_rows(t2.obj["m_pInstanceInfo"]["value"]["m_Trf"]["m_3x3"])[0]
    assert abs(sum(a * b for a, b in zip(x1, x2))) < 1e-9          # orthogonal
    # existing pendant plane origin z sets the mounting height
    assert abs(p.obj["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"][2] - 11.4829) < 1e-3


# ---------------------------------------------------------------------------
# CREATE — floor / free devices
# ---------------------------------------------------------------------------
def test_floor_receptacle_on_level_datum_plane_and_free_transformer():
    doc = _fresh()
    fp, fd = D.add_floor_device(doc, RECEP_STD, (64.0, 118.0), LEVEL1)
    xf = D.add_floor_device(doc, XFMR_15KVA, (66.5, 118.5), LEVEL1, hosting_mode="free")[0]
    for el in (fp, fd, xf):
        assert doc.check_references(el) == []
    pref = fp.obj.get("m_oPlaneRef") or {}
    assert pref.get("ptr_class") == "OnDatumPlaneRef"
    assert (pref.get("value") or {}).get("m_datumPlaneId") == LEVEL1
    par = (fp.header.get("m_parents") or {}).get("value") or {}
    assert par["m_deletion"] == sorted({fp.elem_id, LEVEL1})
    z1 = doc._level_elevation(LEVEL1)
    assert fd.obj["m_hostId"] == fp.elem_id and fd.obj["m_workPlaneBased"] is True
    ii = (fd.obj.get("m_pInstanceInfo") or {}).get("value") or {}
    assert abs(ii["m_Trf"]["m_or"][2] - z1) < 1e-9
    assert _zcol(ii["m_Trf"]["m_3x3"]) == pytest.approx((0.0, 0.0, 1.0), abs=1e-9)   # up-facing
    # free-standing pattern
    assert xf.obj["m_hostId"] == -1 and xf.obj["m_workPlaneBased"] is False
    assert xf.obj["m_assocLevelId"] == LEVEL1
    assert xf.obj["m_pInstanceInfo"]["value"]["m_symbolId"] == XFMR_15KVA
    assert xf.obj["m_masterSymbolId"] == XFMR_15KVA


# ---------------------------------------------------------------------------
# CIRCUITS — multiple loads
# ---------------------------------------------------------------------------
def test_multi_load_circuit_graph_closes():
    doc = _fresh()
    panel = D.add_device_on_plane(doc, PANEL_208, PLANE_ELEC_ROOM,
                                  xyz=(59.256, 118.5, 4.3), level_id=LEVEL1, kind="panel")
    loads = []
    sp = None
    for k, dist in enumerate((8.0, 12.0, 16.0, 20.0)):
        made = D.add_wall_device(doc, RECEP_STD, wall=WALL_EAST, distance_along_ft=dist,
                                 elevation_ft=1.5, facing_point=(64.0, 110.0),
                                 sketchplane=sp)
        if sp is None:
            sp, load = made
        else:
            load = made[0]
        loads.append(load)
    circ = D.add_multi_load_circuit(doc, panel, loads, number="3", rating=20.0,
                                    poles=1, voltage_v=120.0,
                                    apparent_load_va_per_load=180.0)
    assert doc.check_references(circ) == []
    v = circ.obj
    conns = (Document._conn_manager(v) or {}).get("m_connPtrArray") or []
    assert len(conns) == 5, "4 load connectors + 1 base"
    idx = [(c.get("value") or {}).get("m_nIndex") for c in conns]
    assert len(idx) == len(set(idx))
    # loads: connType 1 to the load's supply connector; back-link connType 4
    for c, load in zip(conns[:-1], loads):
        cv = c.get("value") or {}
        ref = cv["m_arrRefs"][0]
        assert ref["m_id"] == load.elem_id and ref["m_connType"] == 1
        back = None
        for lc in (Document._conn_manager(load.obj) or {}).get("m_connPtrArray") or []:
            lcv = lc.get("value") or {}
            if lcv.get("m_nIndex") == ref["m_nIndex"]:
                back = lcv.get("m_arrRefs")
        assert {"m_id": circ.elem_id, "m_nIndex": cv["m_nIndex"], "m_connType": 4} in back
    # base = the panel's 50000-series slot; panel back-links; base array = LAST
    base = (conns[-1].get("value") or {})
    pref = base["m_arrRefs"][0]
    assert pref["m_id"] == panel.elem_id and pref["m_connType"] == 4 and pref["m_nIndex"] >= 50000
    assert v["m_baseConnectorIdArray"] == [
        {"m_id": circ.elem_id, "m_nIndex": base["m_nIndex"], "m_connType": 4}]
    assert base["m_nIndex"] == max(idx)
    pback = None
    for pc in (Document._conn_manager(panel.obj) or {}).get("m_connPtrArray") or []:
        pcv = pc.get("value") or {}
        if pcv.get("m_nIndex") == pref["m_nIndex"]:
            pback = pcv.get("m_arrRefs")
    assert pback == [{"m_id": circ.elem_id, "m_nIndex": base["m_nIndex"], "m_connType": 4}]
    # path node 0 = the panel (the corrected real-model rule)
    node0 = (v.get("m_pathNodes") or [{}])[0]
    if node0:
        assert node0["m_elemId"] == panel.elem_id and node0["m_isVirtualNode"] is False
    # internal units + values
    assert abs(v["m_dVoltage"] - 120.0 * D.INTERNAL_PER_SI) < 1e-6
    assert abs(v["m_dApparentLoad"] - 4 * 180.0 * D.INTERNAL_PER_SI) < 1e-6
    assert v["m_dRating"] == 20.0 and v["m_nPoles"] == 1 and v["m_number"] == "3"
    # header parents name the panel + all loads
    par = (circ.header.get("m_parents") or {}).get("value") or {}
    assert {panel.elem_id, circ.elem_id} | {l.elem_id for l in loads} <= set(par["m_deletion"])
    assert set(par["m_appearanceParents"]) == {panel.elem_id} | {l.elem_id for l in loads}


def test_two_circuits_on_one_panel_use_distinct_slots():
    doc = _fresh()
    panel = D.add_device_on_plane(doc, PANEL_208, PLANE_ELEC_ROOM,
                                  xyz=(59.256, 118.5, 4.3), level_id=LEVEL1)
    l1 = D.add_wall_device(doc, RECEP_STD, wall=WALL_EAST, distance_along_ft=8.0,
                           elevation_ft=1.5, facing_point=(64.0, 110.0))[1]
    l2 = D.add_wall_device(doc, RECEP_STD, wall=WALL_EAST, distance_along_ft=12.0,
                           elevation_ft=1.5, facing_point=(64.0, 110.0))[1]
    c1 = D.add_multi_load_circuit(doc, panel, [l1], number="1")
    c2 = D.add_multi_load_circuit(doc, panel, [l2], number="2")
    s1 = c1.obj["m_pConnectorMgr"]["value"]["m_connPtrArray"][-1]["value"]["m_arrRefs"][0]["m_nIndex"]
    s2 = c2.obj["m_pConnectorMgr"]["value"]["m_connPtrArray"][-1]["value"]["m_arrRefs"][0]["m_nIndex"]
    assert s1 != s2 and s1 >= 50000 and s2 >= 50000


def test_multi_load_circuit_requires_new_elements():
    doc = _fresh()
    l = D.add_wall_device(doc, RECEP_STD, wall=WALL_EAST, distance_along_ft=8.0,
                          elevation_ft=1.5, facing_point=(64.0, 110.0))[1]
    with pytest.raises(TypeError):
        D.add_multi_load_circuit(doc, 581483, [l])          # existing panel id


# ---------------------------------------------------------------------------
# EDIT existing devices (planning; the committed proofs are in
# experiments/mep/devices/)
# ---------------------------------------------------------------------------
def test_move_device_along_host_stays_on_face():
    doc = _fresh()
    from rvt import manipulate as M
    before = M.instance_placement(doc, 467523)
    fr = D.plane_frame(doc, before["m_hostId"])
    plan = D.move_device_along_host(doc, 467523, along_ft=2.0, up_ft=0.5)
    after = M.session(doc).value(467523, 102)["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"]
    dv = [after[i] - before["m_or"][i] for i in range(3)]
    assert abs(sum(dv[i] * fr["X"][i] for i in range(3)) - 2.0) < 1e-9
    assert abs(sum(dv[i] * fr["Y"][i] for i in range(3)) - 0.5) < 1e-9
    assert abs(sum(dv[i] * fr["Z"][i] for i in range(3))) < 1e-9      # stays on the face
    assert plan.record_edits


def test_set_mounting_height_and_mark_and_retype():
    doc = _fresh()
    D.set_device_mark(doc, 467473, "R-EDITED")
    D.set_mounting_height(doc, 467473, 4.0)
    D.retype_device(doc, 467480, RECEP_GFCI)
    from rvt import manipulate as M
    work = M.session(doc)
    v = work.value(467473, 102)
    z = v["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"][2]
    assert abs(z - (doc._level_elevation(LEVEL1) + 4.0)) < 1e-9
    marks = [p for p in v["m_pParamValueSetAString"]["value"]["m_paramSet"]
             if p.get("m_paramId") == D.BIP_ALL_MODEL_MARK]
    assert marks[0]["m_value"] == "R-EDITED"
    r = work.value(467480, 102)
    assert r["m_masterSymbolId"] == RECEP_GFCI
    assert r["m_pInstanceInfo"]["value"]["m_symbolId"] == RECEP_GFCI


def test_rehost_device_to_another_face():
    doc = _fresh()
    plans = D.rehost_device(doc, 467456, 453884, uv=(-14.0, 3.5))
    from rvt import manipulate as M
    v = M.session(doc).value(467456, 102)
    assert v["m_hostId"] == 453884
    fr = D.plane_frame(doc, 453884)
    org = v["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"]
    d = [org[i] - fr["or"][i] for i in range(3)]
    assert abs(sum(d[i] * fr["Z"][i] for i in range(3))) < 1e-9        # ON the new plane
    assert v["m_pInstanceInfo"]["value"]["m_Trf"]["m_3x3"] == D._rows_from_columns(fr["X"], fr["Y"], fr["Z"])
    hdr = M.session(doc).value(467456, 101)
    dele = hdr["m_parents"]["value"]["m_deletion"]
    assert 453884 in dele and 467294 not in dele
    assert plans


def test_delete_device_plan_neutralises_circuit_and_wires():
    doc = _fresh()
    plan = D.delete_device(doc, 467291)                # circuited, on shared plane
    assert 467291 in plan.ids_to_remove
    refcls = {r["class"] for r in plan.referrer_edits}
    assert "RbsElectricalSystem" in refcls and "RbsWireCurve" in refcls
    # its circuit and its host plane are NOT deleted
    assert 469428 not in plan.ids_to_remove and 467294 not in plan.ids_to_remove

"""Tests for rvt.mep.electrical_data — wiring, electrical settings, panel data.

Ground truth = the Revit MEP sample (rmebasicsampleproject.rvt): 1,045
RbsWireCurve wires, 187 circuits on 20 panels, 5 voltage definitions, 3
distribution systems, 12 demand factors, 10 load classifications.

The read-model and planning tests run against ``Document.from_file`` (fast,
lazy decode).  The single end-to-end commit test re-emits a 32 MB file
(~60 s) and is skipped when ``RVT_SKIP_LARGE=1``.
"""
import os

import pytest

from rvt.mep import electrical_data as ED
from rvt.mutate import Document

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

# rme facts
WIRE_HOME_RUN = 469465          # home run: free start end, device 467473 at end
WIRE_BRANCH = 469466            # branch 467291 <-> 467473
DEVICE_467473 = 467473
CKT_469513 = 469513             # 'Power Washing Room 25', circuit 3 of PP-1A
PANEL_PP1A = 622027             # hole at slot 2
PANEL_PP2B = 471596             # Autodesk numbering incl. 3-pole 'EP-2' 20,22,24
PANEL_PP3B = 503195             # Autodesk numbering incl. 3-pole 'EP-3' 19,21,23
PANEL_LP2 = 471705              # holes at slots 1, 14, 19
DF_HVAC = 638823
VT_120 = 55359
DS_480_277 = 277810
LC_RECEPT = 690425


def _need(p):
    if not os.path.exists(p):
        pytest.skip(f"sample not available: {p}")


@pytest.fixture(scope="module")
def rme():
    _need(RME)
    return Document.from_file(RME)


# ---------------------------------------------------------------------------
# units
# ---------------------------------------------------------------------------
def test_internal_units():
    assert abs(ED.volts_to_internal(240.0) - 2583.3385000103334) < 1e-6
    assert abs(ED.internal_to_volts(ED.volts_to_internal(277.0)) - 277.0) < 1e-9
    assert abs(ED.va_to_internal(10_000.0) - 107639.10416709722) < 1e-4
    assert ED.internal_to_va(None) is None


# ---------------------------------------------------------------------------
# READ: electrical settings inventory
# ---------------------------------------------------------------------------
def test_voltage_types_and_distribution_systems(rme):
    vts = ED.voltage_types(rme)
    volts = sorted(round(v["volts"]) for v in vts)
    assert volts == [120, 208, 240, 277, 480]
    v120 = next(v for v in vts if v["id"] == VT_120)
    assert (round(v120["min_volts"]), round(v120["max_volts"])) == (110, 130)
    dss = {d["id"]: d for d in ED.distribution_systems(rme)}
    assert len(dss) == 3
    wye = dss[DS_480_277]
    assert wye["name"] == "480/277 Wye"
    assert (wye["vll"], wye["vlg"]) == (480.0, 277.0)
    assert wye["phase"] == "three" and wye["config"] == "wye" and wye["num_wires"] == 4


def test_wire_types_resolve_conductor_names(rme):
    wts = {w["name"]: w for w in ED.wire_types(rme)}
    assert set(wts) >= {"XHHW", "THWN"}
    x = wts["XHHW"]
    # Revit 2026: material / insulation / temperature are CustomElement
    # conductor definitions named via a NamingCell
    assert x["material"] == "Copper"
    assert x["temperature_rating"] == "60"
    assert x["insulation"] in ("XHHW", "THWN")
    dom = ED.wire_type_domains(rme)
    assert {"Copper", "Aluminium"} <= {m["name"] for m in dom["materials"]}


def test_demand_factor_rules(rme):
    dfs = {d["name"]: d for d in ED.demand_factors(rme)}
    assert len(dfs) == 12
    rec = dfs["Receptacles"]                    # NEC 220.44 style range table
    assert rec["rule_type"] == 4
    assert [round(r["factor"], 3) for r in rec["values"]] == [1.0, 0.5]
    assert abs(rec["values"][0]["max"] - 10_000.0) < 1e-3   # 10 kVA threshold
    assert rec["values"][1]["max"] is None                    # unbounded top row
    assert dfs["Motor"]["rule_type"] == 3
    assert abs(dfs["HVAC"]["values"][0]["factor"] - 1.0) < 1e-12


def test_load_classifications_own_param_elements(rme):
    lcs = ED.load_classifications(rme)
    assert len(lcs) == 10
    for lc in lcs:
        # every classification owns six parameter elements pointing back at it
        pids = list(lc["param_elem_ids"].values())
        assert len(pids) == 6 and all(isinstance(p, int) and p > 0 for p in pids)
        for pid in pids:
            v = rme.value(pid) or {}
            assert rme.class_of(pid) == ED.CLS_LOAD_CLASS_PARAM
            assert v.get("m_idLoadClassification") == lc["id"]
        # and its demand factor resolves by name
        assert isinstance(lc["demand_factor"], str)


def test_electrical_setting_singletons(rme):
    s = ED.electrical_settings(rme)
    es = s["electrical_setting"]
    assert es["circuit_name_phases"] == ["A", "B", "C"]
    assert abs(es["circuit_rating"] - 20.0) < 1e-9
    ws = s["wire_settings"]
    assert ws["connector_separator"] == "-"
    assert isinstance(ws["home_run_arrow_leader_style"], int)


# ---------------------------------------------------------------------------
# READ: wires
# ---------------------------------------------------------------------------
def test_wire_count_and_home_run_model(rme):
    ids = rme.ids_of_class(ED.CLS_WIRE)
    assert len(ids) == 1045
    hr = ED.wire_info(rme, WIRE_HOME_RUN)
    assert hr["home_run"] is True
    assert hr["start"] is None                       # free arrow end
    assert hr["end"]["device"] == DEVICE_467473 and hr["end"]["connector"] == 1
    assert hr["circuits"] == [469428, 469434, 469513]  # a 3-circuit home run
    assert hr["wiring"] == "arc"
    br = ED.wire_info(rme, WIRE_BRANCH)
    assert br["home_run"] is False
    assert {br["start"]["device"], br["end"]["device"]} == {467291, DEVICE_467473}


def test_wire_device_links_are_symmetric(rme):
    """Wire end connectors and device connectors reference each other (connType 1)."""
    dev_conns = ED.connectors(rme.value(DEVICE_467473) or {})
    back = dev_conns[1]
    assert (WIRE_HOME_RUN, 1, ED.CONN_LOGICAL) in back      # device -> home run end
    assert (WIRE_BRANCH, 1, ED.CONN_LOGICAL) in back
    # a circuit back-link lives on the same device connector with connType 4
    assert any(ct == ED.CONN_SYSTEM for (_t, _i, ct) in back)


def test_wire_end_flags_match_connection_state(rme):
    """Corpus rule: m_bDynamicUpdateEnds[i] is True iff end i is connected."""
    checked = mismatch = 0
    for wid in rme.ids_of_class(ED.CLS_WIRE)[:400]:
        v = rme.value(wid) or {}
        cc = ED.connectors(v)
        ends = [any(t != wid for (t, _i, _c) in cc.get(i, [])) for i in (0, 1)]
        dyn = list(v.get("m_bDynamicUpdateEnds") or [False, False])
        checked += 1
        if dyn != ends:
            mismatch += 1
    assert checked == 400 and mismatch == 0


def test_no_wire_ever_connects_to_a_panel(rme):
    """Home runs are free-ended: wire connectors target devices, never equipment."""
    for wid in rme.ids_of_class(ED.CLS_WIRE)[:300]:
        for _i, refs in ED.connectors(rme.value(wid) or {}).items():
            for (t, _ti, _ct) in refs:
                if t == wid:
                    continue
                assert rme.category_of(t) != ED.OST_ElectricalEquipment


def test_wires_of_circuit_and_view_inference(rme):
    ws = ED.wires_of_circuit(rme, CKT_469513)
    assert WIRE_HOME_RUN in ws
    view = ED._infer_wire_view(rme, [DEVICE_467473], [CKT_469513])
    assert view == 455447                                # the plan owning them


# ---------------------------------------------------------------------------
# READ: panels + numbering
# ---------------------------------------------------------------------------
def test_panel_info(rme):
    p = ED.panel_info(rme, PANEL_PP1A)
    assert p["name"] == "PP-1A"
    assert p["distribution_system"] == "120/208 Wye"
    assert (p["voltage_ll"], p["voltage_lg"]) == (208.0, 120.0)
    assert abs(p["mains_rating_a"] - 100.0) < 1e-9
    assert p["n_circuits"] == 17
    names = {q["name"] for q in ED.panels(rme)}
    assert {"PP-1A", "PP-2B", "PP-3B", "LP-2"} <= names


def test_circuit_panel_and_loads(rme):
    p = ED.circuit_panel(rme, CKT_469513)
    assert p[0] == PANEL_PP1A and p[1] >= 50000       # a 50000-series slot connector
    loads = ED.circuit_loads(rme, CKT_469513)
    assert len(loads) == 9 and all(c == 1 for (_d, c) in loads)


def test_layout_rule_reproduces_autodesk_numbering(rme):
    """The two-column packing rule reproduces Autodesk's own circuit numbers
    on the untouched panels, including 3-pole spanning circuits."""
    for pid, three_pole in ((PANEL_PP2B, "20,22,24"), (PANEL_PP3B, "19,21,23")):
        rows = ED.panel_circuits(rme, pid)
        laid = ED.layout_circuits(rows)
        for r in laid:
            assert (r["number"] or "") == r["new_number"], (pid, r["id"], r["number"], r["new_number"])
            assert r["start_slot"] == r["new_start_slot"]
        assert any(r["number"] == three_pole for r in rows)
        rep = ED.check_panel_numbering(rme, pid)
        assert rep["consistent"] and rep["compact"] and not rep["overlaps"]


def test_check_panel_numbering_finds_the_hole(rme):
    rep = ED.check_panel_numbering(rme, PANEL_PP1A)
    assert rep["spaces"] == [2]                      # the hole renumber closes
    assert rep["consistent"] and not rep["compact"]
    rep2 = ED.check_panel_numbering(rme, PANEL_LP2)
    assert rep2["spaces"] == [1, 14, 19]


def test_check_panel_numbering_flags_overlap():
    laid = ED.layout_circuits([{"id": 1, "poles": 1}, {"id": 2, "poles": 2},
                               {"id": 3, "poles": 1}])
    assert [r["new_number"] for r in laid] == ["1", "2,4", "3"]
    # a 3-pole always occupies same-parity slots
    laid = ED.layout_circuits([{"id": i, "poles": 1} for i in range(19)]
                              + [{"id": 99, "poles": 3}])
    assert laid[-1]["new_slots"] == [20, 22, 24]     # PP-2B's 'EP-2' exactly


# ---------------------------------------------------------------------------
# CREATE: planning (in memory, no writing)
# ---------------------------------------------------------------------------
@pytest.fixture()
def fresh():
    _need(RME)
    return Document.from_file(RME)


def _decodes_clean(doc, el):
    """Serialize the new element and prove each framed record decodes clean."""
    framed = dict(doc.serialize(el))
    assert set(framed) == {101, 102, 103}
    from rvt.objects import iter_records
    for seq, blob in framed.items():
        recs = list(iter_records(blob, seq))
        assert len(recs) == 1 and recs[0].elem_id == el.elem_id
        r = recs[0]
        if r.body_size >= 2:
            obj = doc.dec.decode_record(r.class_id, r.payload)
            assert obj.clean, (seq, obj.errors[:2] if obj.errors else obj)
    return framed


def test_add_home_run_wire(fresh):
    wp = ED.add_home_run(fresh, CKT_469513)
    assert wp.home_run and wp.view_id == 455447 and wp.circuits == [CKT_469513]
    o = wp.wire.obj
    assert o["m_ownerDBViewId"] == 455447
    assert o["m_bDynamicUpdateEnds"] == [False, True]     # free start, connected end
    assert o["m_eType"] == ED.WIRING_ARC and o["m_bDrawCircularArc"] is True
    cc = ED.connectors(o)
    ext0 = [t for (t, _i, _c) in cc[0] if t != wp.wire.elem_id]
    ext1 = [t for (t, _i, _c) in cc[1] if t != wp.wire.elem_id]
    assert ext0 == [] and len(ext1) == 1                  # arrow end free
    # sibling self-references between the two end connectors
    assert (wp.wire.elem_id, 1, ED.CONN_LOGICAL) in cc[0]
    assert (wp.wire.elem_id, 0, ED.CONN_LOGICAL) in cc[1]
    dpm = ED._v(o.get("m_pDesignPropManager"))
    assert dpm["m_setidCircuits"] == [CKT_469513]
    assert fresh.check_references(wp.wire) == []
    assert len(wp.device_plans) == 1
    _decodes_clean(fresh, wp.wire)


def test_add_branch_wire_backlinks_both_devices(fresh):
    loads = ED.circuit_loads(fresh, CKT_469513)
    a, b = loads[0][0], loads[1][0]
    wp = ED.add_wire(fresh, CKT_469513, a, b, wiring_type="chamfer")
    assert not wp.home_run
    o = wp.wire.obj
    assert o["m_eType"] == ED.WIRING_CHAMFER and o["m_bDrawCircularArc"] is False
    assert o["m_bDynamicUpdateEnds"] == [True, True]
    cc = ED.connectors(o)
    assert (a, 1, ED.CONN_LOGICAL) in cc[0] and (b, 1, ED.CONN_LOGICAL) in cc[1]
    assert sorted(p.elem_id for p in wp.device_plans) == sorted([a, b])
    # the devices' working copies now reference the wire back
    from rvt import manipulate as M
    sess = M.session(fresh)
    for dev, wire_conn in ((a, 0), (b, 1)):
        refs = ED.connectors(sess.value(dev, 102))[1]
        assert (wp.wire.elem_id, wire_conn, ED.CONN_LOGICAL) in refs
    assert fresh.check_references(wp.wire) == []
    _decodes_clean(fresh, wp.wire)


def test_add_wire_rejects_bad_inputs(fresh):
    with pytest.raises(LookupError):
        ED.add_wire(fresh, 123456789, DEVICE_467473)             # not a circuit
    with pytest.raises(ValueError):
        ED.add_wire(fresh, CKT_469513, DEVICE_467473, wiring_type="zigzag")


def test_add_load_classification_closure(fresh):
    els = ED.add_load_classification(fresh, "EV Charging", abbreviation="EV",
                                     demand_factor=1.0, space_load_class=2)
    kinds = [e.kind for e in els]
    assert kinds.count("load_class_param") == 6
    assert kinds.count("demand_factor") == 1 and kinds[0] == "load_classification"
    cls = els[0]
    df = next(e for e in els if e.kind == "demand_factor")
    assert cls.obj["m_name"] == "EV Charging" and cls.obj["m_abbreviation"] == "EV"
    assert cls.obj["m_demandFactorId"] == df.elem_id
    params = [e for e in els if e.kind == "load_class_param"]
    for p in params:
        assert p.obj["m_idLoadClassification"] == cls.elem_id
        pd = ED._v(p.obj.get("m_pParamDef"))
        assert pd["m_paramElemId"] == p.elem_id
        assert pd["m_typeId"]["m_typeId"].endswith(f"{p.elem_id:08x}-1.0.0")
        assert "EV Charging" in (pd.get("m_caption") or "")
        # mutual deletion parents
        pdel = ED._v(p.header["m_parents"])["m_deletion"]
        assert cls.elem_id in pdel and p.elem_id in pdel
    cdel = ED._v(cls.header["m_parents"])["m_deletion"]
    assert df.elem_id in cdel and all(p.elem_id in cdel for p in params)
    # every param field of the classification points at a new param
    assert sorted(cls.obj[k] for k in ED.LOAD_CLASS_PARAM_FIELDS) == \
        sorted(p.elem_id for p in params)
    for e in els:
        assert fresh.check_references(e) == []
        _decodes_clean(fresh, e)


def test_add_distribution_system_with_new_voltages(fresh):
    v347 = ED.add_voltage_type(fresh, "347", 347, 330, 360)
    v600 = ED.add_voltage_type(fresh, "600", 600, 570, 610)
    ds = ED.add_distribution_system(fresh, "600/347 Wye", vll=v600, vlg=v347,
                                    phase="three", config="wye", num_wires=4)
    assert abs(v600.obj["m_dActualVoltage"] - ED.volts_to_internal(600)) < 1e-9
    assert (ds.obj["m_idVll"], ds.obj["m_idVlg"]) == (v600.elem_id, v347.elem_id)
    assert (ds.obj["m_kPhase"], ds.obj["m_kConfig"], ds.obj["m_iNumWires"]) == (1, 1, 4)
    dele = ED._v(ds.header["m_parents"])["m_deletion"]
    assert dele == sorted([v347.elem_id, v600.elem_id, ds.elem_id])
    for e in (v347, v600, ds):
        assert fresh.check_references(e) == []
        _decodes_clean(fresh, e)


# ---------------------------------------------------------------------------
# MODIFY / DELETE planning
# ---------------------------------------------------------------------------
def test_setting_modify_plans(fresh):
    p1 = ED.set_demand_factor(fresh, DF_HVAC, 0.85)
    assert p1.record_edits and abs(p1.changes[0].after - 0.85) < 1e-12
    p2 = ED.set_voltage_type(fresh, VT_120, max_volts=132.0)
    assert abs(p2.changes[0].after - ED.volts_to_internal(132.0)) < 1e-6
    p3 = ED.rename_setting(fresh, 277809, "240/120 Single Phase")
    assert p3.changes[0].path == "m_symbolInfo.value.m_name"
    p4 = ED.set_load_classification(fresh, LC_RECEPT, abbreviation="RCPT")
    assert p4.changes[0].after == "RCPT"
    with pytest.raises(Exception):
        ED.set_demand_factor(fresh, VT_120, 0.5)            # not a demand factor


def test_renumber_circuits_plans_and_idempotency(fresh):
    # PP-2B is already Autodesk-numbered: renumber is a no-op
    assert ED.renumber_circuits(fresh, PANEL_PP2B) == []
    # PP-1A has a hole at slot 2: 16 circuits are re-laid-out
    plans = ED.renumber_circuits(fresh, PANEL_PP1A)
    assert len(plans) == 16
    for pl in plans:
        paths = {c.path for c in pl.changes}
        assert paths == {"m_number", "m_nStartSlot"}
        num = next(c.after for c in pl.changes if c.path == "m_number")
        slot = next(c.after for c in pl.changes if c.path == "m_nStartSlot")
        assert num == str(slot)                              # single-pole circuits


def test_delete_wire_plan(fresh):
    plan = ED.delete_wire(fresh, WIRE_BRANCH)
    assert WIRE_BRANCH in plan.ids_to_remove
    referrers = {r["id"] for r in plan.referrer_edits}
    # both devices' connector back-links (and the neighbouring home run's
    # header list) are neutralised
    assert 467291 in referrers and DEVICE_467473 in referrers
    with pytest.raises(Exception):
        ED.delete_wire(fresh, DEVICE_467473)                    # not a wire


# ---------------------------------------------------------------------------
# end-to-end commit (writes a 32 MB file; ~1 min)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_commit_wire_create_end_to_end(fresh, tmp_path):
    if os.environ.get("RVT_SKIP_LARGE") == "1":
        pytest.skip("RVT_SKIP_LARGE=1")
    loads = ED.circuit_loads(fresh, CKT_469513)
    hr = ED.add_home_run(fresh, CKT_469513)
    br = ED.add_wire(fresh, CKT_469513, loads[0][0], loads[1][0], wiring_type="chamfer")
    plans = hr.device_plans + br.device_plans
    out = str(tmp_path / "wires.rvt")
    rep = ED.commit_electrical(RME, out, fresh, new_elements=[hr.wire, br.wire], plans=plans)
    assert rep.elemtable_count_after == rep.elemtable_count_before + 2
    edited = sorted({p.elem_id for p in plans})
    v = ED.verify_electrical(out, new_ids=[hr.wire.elem_id, br.wire.elem_id],
                             edited_ids=edited)
    assert v["structurally_valid"], v
    d2 = Document.from_file(out)
    hri = ED.wire_info(d2, hr.wire.elem_id)
    assert hri["home_run"] and hri["circuits"] == [CKT_469513]
    bri = ED.wire_info(d2, br.wire.elem_id)
    assert not bri["home_run"] and bri["wiring"] == "chamfer"
    # devices reference the wires back (two-way links)
    back = ED.connectors(d2.value(loads[0][0]))[1]
    assert (hr.wire.elem_id, 1, ED.CONN_LOGICAL) in back
    assert (br.wire.elem_id, 0, ED.CONN_LOGICAL) in back

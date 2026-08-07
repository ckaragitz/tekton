"""Circuit creation: the reference graph must close exactly like real circuits."""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
SAMPLE = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")


def _mgr(v):
    from rvt.mutate import Document
    return Document._conn_manager(v) or {}


@pytest.fixture(scope="module")
def circuited(tmp_path_factory):
    if not os.path.exists(SAMPLE):
        pytest.skip("rme sample not present")
    from rvt.commit import commit_new_elements
    from rvt.mutate import Document
    doc = Document.from_file(SAMPLE)
    lvl = doc.levels()[0]["id"]
    panel = doc.add_family_instance(619617, lvl, position=(50.0, -90.0, 3.5))
    xfmr = doc.add_family_instance(621242, lvl, position=(50.0, -100.0, 0.3))
    circ = doc.add_circuit(panel, xfmr, number="7", description="XFMR feeder")
    recs, plans = [], []
    for el in (panel, xfmr, circ):
        recs.append(dict(doc.serialize(el)))
        plans.append(el.elemrec)
    out = str(tmp_path_factory.mktemp("c") / "circ.rvt")
    commit_new_elements(SAMPLE, out, recs, plans)
    return out, panel, xfmr, circ


def test_circuit_graph_closes(circuited):
    from rvt.mutate import Document
    out, panel, xfmr, circ = circuited
    g = Document.from_file(out)
    v = g.value(circ.elem_id)
    assert g.class_of(circ.elem_id) == "RbsElectricalSystem"
    conns = _mgr(v).get("m_connPtrArray") or []
    assert len(conns) == 2, "single-load circuit = load connector + panel connector"
    load_ref = (conns[0]["value"]["m_arrRefs"] or [None])[0]
    panel_ref = (conns[-1]["value"]["m_arrRefs"] or [None])[0]
    # panel is the BASE at the END on a 50000-series slot; load on its supply conn
    assert panel_ref["m_id"] == panel.elem_id and panel_ref["m_connType"] == 4
    assert panel_ref["m_nIndex"] >= 50000
    assert load_ref["m_id"] == xfmr.elem_id and load_ref["m_connType"] == 1
    assert v["m_baseConnectorIdArray"] == [
        {"m_id": circ.elem_id, "m_nIndex": 1, "m_connType": 4}]

    # back-links present on both member and base
    def refs(eid, idx):
        ev = g.value(eid) or {}
        for c in (Document._conn_manager(ev) or {}).get("m_connPtrArray") or []:
            cv = c.get("value") or {}
            if cv.get("m_nIndex") == idx:
                return cv.get("m_arrRefs")
        return None
    assert refs(xfmr.elem_id, load_ref["m_nIndex"]) == [
        {"m_id": circ.elem_id, "m_nIndex": 0, "m_connType": 4}]
    assert refs(panel.elem_id, panel_ref["m_nIndex"]) == [
        {"m_id": circ.elem_id, "m_nIndex": 1, "m_connType": 4}]


def test_created_equipment_starts_unconnected(circuited):
    """Cloned connectors are scrubbed: no dangling refs to template circuits,
    only the ONE deliberate back-link created by add_circuit."""
    from rvt.mutate import Document
    out, panel, xfmr, circ = circuited
    g = Document.from_file(out)
    for eid, expect_links in ((panel.elem_id, 1), (xfmr.elem_id, 1)):
        v = g.value(eid) or {}
        conns = (Document._conn_manager(v) or {}).get("m_connPtrArray") or []
        refs = [r for c in conns for r in ((c.get("value") or {}).get("m_arrRefs") or [])]
        assert len(refs) == expect_links, f"{eid}: refs={refs}"
        assert all(r["m_id"] == circ.elem_id for r in refs)


def test_panel_slots_are_never_shared():
    """Two circuits on one panel occupy two DISTINCT 50000-series slots."""
    if not os.path.exists(SAMPLE):
        pytest.skip("rme sample not present")
    from rvt.mutate import Document
    doc = Document.from_file(SAMPLE)
    lvl = doc.levels()[0]["id"]
    panel = doc.add_family_instance(619617, lvl, position=(0, 0, 3.5))
    x1 = doc.add_family_instance(621242, lvl, position=(5, 0, 0.3))
    x2 = doc.add_family_instance(621242, lvl, position=(10, 0, 0.3))
    c1 = doc.add_circuit(panel, x1, number="1")
    c2 = doc.add_circuit(panel, x2, number="2")
    s1 = (Document._conn_manager(doc.value(c1.elem_id) if False else c1.obj) or {})
    slot = lambda cel: cel.obj["m_pConnectorMgr"]["value"]["m_connPtrArray"][-1]["value"]["m_arrRefs"][0]["m_nIndex"]
    assert slot(c1) != slot(c2) and slot(c1) >= 50000 and slot(c2) >= 50000

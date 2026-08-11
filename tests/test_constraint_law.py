"""The constraint-graph law (#689), promoted from a desktop failure."""
import pytest
from rvt.famgen import constraint_law as CL


def _tri(eid, cls, obj):
    return (eid, cls, obj)


def _witness(*ids):
    return {"m_witnessRefs": [
        {"m_pWitnessRef": {"ptr_class": "GeomSegInPlaneRef", "pid": -1,
                           "value": {"m_geomRef": {"m_elemId": i}}}}
        for i in ids]}


def _back(*ids):
    return {"m_constrInfo": [{"ptr_class": "ConstraintInfo", "pid": -1,
                              "value": {"m_constrId": i}} for i in ids]}


def test_one_directional_graph_is_an_error():
    # the exact 2026-08-11 shape: the alignment names the curve, the curve
    # denies being constrained.
    f = CL.check_graph([_tri(10, "Alignment", _witness(20)),
                        _tri(20, "CurveElem", {"m_constrInfo": []})])
    assert [x["rule"] for x in f] == ["CG2"]
    assert f[0]["severity"] == CL.ERROR
    assert f[0]["missing"] == [10]


def test_a_coherent_graph_passes():
    assert CL.check_graph([_tri(10, "Alignment", _witness(20)),
                           _tri(20, "CurveElem", _back(10))]) == []


def test_inline_back_edges_are_tolerated_when_reading():
    # reading must never be the thing that breaks
    assert CL.check_graph([_tri(10, "Alignment", _witness(20)),
                           _tri(20, "CurveElem",
                                {"m_constrInfo": [{"m_constrId": 10}]})]) == []


def test_dangling_forward_reference():
    f = CL.check_graph([_tri(10, "Alignment", _witness(99))])
    assert any(x["rule"] == "CG1" for x in f)


def test_dangling_back_edge():
    f = CL.check_graph([_tri(20, "CurveElem", _back(99))])
    assert any(x["rule"] == "CG4" for x in f)


def test_back_edge_naming_a_non_constraint():
    f = CL.check_graph([_tri(10, "CurveElem", {}),
                        _tri(20, "CurveElem", _back(10))])
    assert any(x["rule"] == "CG4" for x in f)


def test_inert_constraint_is_a_warning_not_an_error():
    f = CL.check_graph([_tri(10, "Alignment", {"m_witnessRefs": []})])
    assert [x["rule"] for x in f] == ["CG3"]
    assert f[0]["severity"] == CL.WARNING


def test_a_dimension_constrains_both_its_planes():
    f = CL.check_graph([_tri(10, "LinearDimString", _witness(20, 21)),
                        _tri(20, "RefPlane", _back(10)),
                        _tri(21, "RefPlane", {})])
    assert [x["element"] for x in f] == [21]


def test_summarise_is_quotable():
    assert "coherent" in CL.summarise([])
    f = CL.check_graph([_tri(10, "Alignment", _witness(20)),
                        _tri(20, "CurveElem", {})])
    assert "1 error(s)" in CL.summarise(f)

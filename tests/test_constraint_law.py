"""The constraint-graph law (#689), promoted from a desktop failure.

The back-edge half of it (CG2) was refuted by the #787 corpus census -- 0 / 421
Revit-born files carry an ``m_constrInfo`` back-edge -- and retired in #910;
the tests that pinned it now pin that it is gone (tests/test_constraint_law_910.py
covers the laws that replaced it)."""
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


def test_one_directional_graph_is_not_an_error_any_more():
    # the exact 2026-08-11 shape: the alignment names the curve, the curve's
    # m_constrInfo is [].  That is how EVERY Revit-born family stores it
    # (0 / 421 carry a back-edge, #787), so the refuted CG2 must never fire.
    f = CL.check_graph([_tri(10, "Alignment", _witness(20, 21)),
                        _tri(20, "CurveElem", {"m_constrInfo": []}),
                        _tri(21, "RefPlane", {"m_constrInfo": []})])
    assert f == []
    assert "CG2" in CL.RETIRED_RULES


def test_a_graph_with_back_edges_still_passes():
    # back-edges are not demanded, but one that is present and points at a
    # real constraint is not an error either
    assert CL.check_graph([_tri(10, "Alignment", _witness(20, 21)),
                           _tri(20, "CurveElem", _back(10)),
                           _tri(21, "RefPlane", {})]) == []


def test_inline_back_edges_are_tolerated_when_reading():
    # reading must never be the thing that breaks
    assert CL.check_graph([_tri(10, "Alignment", _witness(20, 21)),
                           _tri(20, "CurveElem",
                                {"m_constrInfo": [{"m_constrId": 10}]}),
                           _tri(21, "RefPlane", {})]) == []


def test_dangling_forward_reference():
    f = CL.check_graph([_tri(10, "Alignment", _witness(99, 20)),
                        _tri(20, "RefPlane", {})])
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


def test_a_dimension_owes_its_planes_no_back_edge():
    # formerly: plane 21 was an error for not listing the dimension.  Born
    # files never list it (#910), so one plane with and one without is fine.
    f = CL.check_graph([_tri(10, "LinearDimString", _witness(20, 21)),
                        _tri(20, "RefPlane", _back(10)),
                        _tri(21, "RefPlane", {})])
    assert f == []


def test_summarise_is_quotable():
    assert "coherent" in CL.summarise([])
    f = CL.check_graph([_tri(10, "Alignment", _witness(20, 99)),
                        _tri(20, "CurveElem", {})])
    assert "1 error(s)" in CL.summarise(f)

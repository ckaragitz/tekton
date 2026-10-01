"""#910 -- the constraint law stops demanding ``m_constrInfo`` back-edges
(0 / 421 Revit-born files carry one, #787 census) and keeps the corpus-attested
shape of the in-plane drive: alignment / labelled-dimension shape (CG5), every
sketch lock registered on its sketch (CG6), and every sketch lock's curve on
its plane (CG7).

Passes on the desktop-verified chains (the #907 trapeze, the #787 one-box
probe pair); FAILS on deliberately broken ones.  Passing is necessary, never
sufficient (hard rule 4).
"""
import os
import sys

import pytest

from rvt.famgen import constraint_law as CL
from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TRAPEZE_PROMPT = "a 2 tier slotted trapeze with threaded rod"
BOX = {"name": "b", "shape": "box", "width_ft": 2, "depth_ft": 1, "height_ft": 1}


# -- synthetic graphs -------------------------------------------------------

def _gref(eid, tag=0):
    return {"m_pWitnessRef": {"ptr_class": "GeomSegInPlaneRef", "pid": -1,
                              "value": {"m_geomRef": {"m_elemId": eid,
                                                      "m_geomTag": tag}}}}


def _lock(*wit, sketch=None):
    o = {"m_witnessRefs": [_gref(e, t) for e, t in wit]}
    if sketch is not None:
        o["m_cellList"] = {"ptr_class": "CellList", "pid": -1, "value": {
            "m_cells": [{"ptr_class": "SketchMembership", "pid": -1,
                         "value": {"m_groupId": sketch}}]}}
    return o


def _plane_x(x):
    """A vertical RefPlane x = ``x`` (drawn in plan, cut vector +Z)."""
    return {"m_freeEnd": [x, -5.0, 0.0], "m_bubbleEnd": [x, 5.0, 0.0],
            "m_cutVec": [0.0, 0.0, 1.0]}


def _line(origin, d, t1):
    return {"m_pCurveDriver": {"ptr_class": "CurveElemDriver", "pid": -1, "value": {
        "m_pCrv": {"ptr_class": "GLine", "pid": 3, "value": {
            "m_origin": list(origin), "m_dirVec": list(d),
            "m_endParams": [0.0, t1]}}}}}


def _arc(center):
    return {"m_pCurveDriver": {"ptr_class": "CurveElemDriver", "pid": -1, "value": {
        "m_pCrv": {"ptr_class": "GArc", "pid": 3, "value": {
            "m_center": list(center), "m_radius": 0.5,
            "m_xVec": [1.0, 0.0, 0.0], "m_yVec": [0.0, 1.0, 0.0],
            "m_endParams": [0.0, 3.14159]}}}}}


def _sketch(dim_ids, deletion):
    return ({"m_dimIds": list(dim_ids)},
            {"m_parents": {"ptr_class": "ElementParents", "pid": -1,
                           "value": {"m_deletion": list(deletion)}}})


def _graph(*, curve=None, tag=0, dim_ids=(10,), deletion=(10, 20, 30),
           plane_x=1.0):
    sk_obj, sk_hdr = _sketch(dim_ids, deletion)
    return [(10, "Alignment", _lock((30, 0), (20, tag), sketch=40)),
            (20, "CurveElem", curve if curve is not None
             else _line((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 2.0)),
            (30, "RefPlane", _plane_x(plane_x)),
            (40, "VarSketch", sk_obj, sk_hdr)]


def _rules(findings):
    return sorted(f["rule"] for f in findings)


def test_a_coherent_lock_without_back_edges_passes():
    assert CL.check_graph(_graph()) == []


def test_cg7_a_line_off_its_plane_is_an_error():
    f = CL.check_graph(_graph(plane_x=1.25))
    assert _rules(f) == ["CG7"]
    assert f[0]["severity"] == CL.ERROR and f[0]["offset_ft"] == pytest.approx(0.25)


def test_cg7_a_line_with_one_end_off_its_plane_is_an_error():
    # a skewed line: origin on x = 1, the far end at x = 1.1
    f = CL.check_graph(_graph(curve=_line((1.0, 0.0, 0.0), (0.05, 1.0, 0.0), 2.0)))
    assert _rules(f) == ["CG7"]


def test_cg7_an_arc_centre_lock_uses_the_centre():
    assert CL.check_graph(_graph(curve=_arc((1.0, 3.0, 0.0)), tag=1)) == []
    assert _rules(CL.check_graph(_graph(curve=_arc((1.5, 3.0, 0.0)), tag=1))) == ["CG7"]


def test_cg7_never_guesses_an_unknown_case():
    # an arc witnessed with geomTag 0 is not a centre lock: not judged
    assert CL.check_graph(_graph(curve=_arc((9.0, 3.0, 0.0)), tag=0)) == []


def test_cg6_a_lock_missing_from_its_sketch_is_an_error():
    f = CL.check_graph(_graph(dim_ids=()))
    assert _rules(f) == ["CG6"]


def test_cg6_dim_ids_must_be_deletion_children_of_the_sketch():
    f = CL.check_graph(_graph(deletion=(20, 30)))
    assert _rules(f) == ["CG6"] and f[0]["missing"] == [10]


def test_cg6_a_lock_on_a_missing_sketch_is_an_error():
    g = [t for t in _graph() if t[0] != 40]
    assert _rules(CL.check_graph(g)) == ["CG6"]


def test_cg5_an_alignment_aligns_exactly_two_references():
    g = _graph()
    g[0] = (10, "Alignment", _lock((30, 0), (20, 0), (30, 0), sketch=40))
    assert "CG5" in _rules(CL.check_graph(g))


def test_cg5_labelled_dimension_shape():
    def dim(n_wit, n_seg, param=50):
        return {"m_witnessRefs": [_gref(30 + i) for i in range(n_wit)],
                "m_ArrSegInfo": [{"m_paramId": param}] * n_seg}
    planes = [(30 + i, "RefPlane", _plane_x(i)) for i in range(3)]
    param = [(50, "FamilyParam", {})]
    ok = [(10, "LinearDimString", dim(2, 1))] + planes + param
    assert CL.check_graph(ok) == []
    assert _rules(CL.check_graph([(10, "LinearDimString", dim(2, 2))]
                                 + planes + param)) == ["CG5"]
    assert _rules(CL.check_graph([(10, "LinearDimString", dim(1, 1))]
                                 + planes + param)) == ["CG5"]
    # labelled with a parameter that is not in the document
    assert _rules(CL.check_graph([(10, "LinearDimString", dim(2, 1, 77))]
                                 + planes)) == ["CG5"]
    # an unlabelled dimension is not held to the labelled shape
    assert CL.check_graph([(10, "LinearDimString", dim(3, 1, -1))] + planes) == []


def test_universe_counts_ids_not_decoded():
    # check_file decodes only constraint classes; an id elsewhere in the
    # file is still "in the document"
    g = [(10, "Alignment", _lock((30, 0), (99, 0)))] + [(30, "RefPlane", _plane_x(0))]
    assert _rules(CL.check_graph(g)) == ["CG1"]
    assert CL.check_graph(g, universe=[99]) == []


# -- the desktop-verified chains --------------------------------------------

@pytest.fixture(scope="module")
def trapeze():
    return F.make_archetype(product="strut_trapeze", prompt=TRAPEZE_PROMPT)


def _box(regen_edge=True):
    prod = F.make_generic_model(parts=[dict(BOX)], drive=True, name="B910")
    DL.apply_born_inplane_law(prod.doc, regen_edge=regen_edge)
    return prod


def test_the_trapeze_carries_no_back_edges_and_passes(trapeze, tmp_path):
    d = trapeze.doc
    assert getattr(d, "born_drive_law", False)
    assert not any(e.obj.get("m_constrInfo") for e in d.elements)
    assert len(DL._sketch_locks(d)) >= 4          # the law has something to judge
    assert CL.check_doc(d) == []
    p = str(tmp_path / "trapeze.rfa")
    trapeze.write(p)
    assert CL.check_file(p) == []


@pytest.mark.parametrize("regen_edge", [True, False])
def test_the_one_box_probe_pair_passes(regen_edge, tmp_path):
    prod = _box(regen_edge)
    assert not any(e.obj.get("m_constrInfo") for e in prod.doc.elements)
    assert len(DL._sketch_locks(prod.doc)) == 4
    assert CL.check_doc(prod.doc) == []
    p = str(tmp_path / "box.rfa")
    prod.write(p)
    assert CL.check_file(p) == []


def _first_lock(doc):
    al = DL._sketch_locks(doc)[0]
    by = {e.elem_id: e for e in doc.elements}
    return al, by[int(al.owner_id)], by


def test_a_lock_moved_off_its_plane_fails(tmp_path):
    prod = _box()
    al, _sk, by = _first_lock(prod.doc)
    cid = next(i for i in DL._witness_ids(al) if by[i].class_name == "CurveElem")
    crv = by[cid].obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
    crv["m_origin"] = [c + 0.25 for c in crv["m_origin"][:2]] + [0.0]
    assert _rules(CL.check_doc(prod.doc)) == ["CG7"]
    p = str(tmp_path / "off.rfa")
    prod.write(p)
    assert _rules(CL.check_file(p)) == ["CG7"]


def test_a_lock_removed_from_its_sketch_fails(tmp_path):
    prod = _box()
    al, sk, _by = _first_lock(prod.doc)
    sk.obj["m_dimIds"] = [i for i in sk.obj["m_dimIds"] if i != al.elem_id]
    assert _rules(CL.check_doc(prod.doc)) == ["CG6"]
    p = str(tmp_path / "unreg.rfa")
    prod.write(p)
    assert _rules(CL.check_file(p)) == ["CG6"]


def test_a_lock_dropped_from_the_sketch_deletion_list_fails(tmp_path):
    prod = _box()
    al, sk, _by = _first_lock(prod.doc)
    par = sk.header["m_parents"]["value"]
    par["m_deletion"] = [i for i in par["m_deletion"] if i != al.elem_id]
    assert _rules(CL.check_doc(prod.doc)) == ["CG6"]
    p = str(tmp_path / "hdr.rfa")
    prod.write(p)
    assert _rules(CL.check_file(p)) == ["CG6"]


# -- the self battery runs this law -----------------------------------------

def _battery():
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    try:
        import self_battery as SB
    finally:
        sys.path.pop(0)
    return SB


def test_self_battery_lists_and_passes_the_verified_chains(tmp_path):
    SB = _battery()
    jobs = SB._catalog()
    for key in ("archetype_strut_trapeze", "drive_one_box_law",
                "drive_one_box_control"):
        assert key in jobs
        row = SB._run_one(key, jobs[key], str(tmp_path), None)
        assert row["steps"]["law"] == "ok", row["steps"]
        assert row["ok"], row["steps"]


def test_self_battery_still_catches_a_broken_chain(tmp_path):
    SB = _battery()

    def broken():
        prod = _box()
        al, _sk, by = _first_lock(prod.doc)
        cid = next(i for i in DL._witness_ids(al) if by[i].class_name == "CurveElem")
        crv = by[cid].obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
        crv["m_origin"] = [c + 0.25 for c in crv["m_origin"][:2]] + [0.0]
        return prod
    row = SB._run_one("broken", broken, str(tmp_path), None)
    assert row["steps"]["law"].startswith("FAIL") and not row["ok"]


@pytest.mark.xfail(strict=True, reason=(
    "#910 finding: param_drive.wire_panelboard_drive puts the front/back side "
    "planes at y = +-depth/2 while the profile spans y = 0..depth, so two "
    "sketch locks sit 0.24 ft off their planes (CG7). A real defect, filed as "
    "a follow-up; strict so the fix flips this test"))
def test_the_panelboard_chain_is_coherent():
    assert CL.check_doc(F.make_panelboard(name="B910").doc) == []

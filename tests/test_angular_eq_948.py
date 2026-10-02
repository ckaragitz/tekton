"""The hex nut's Nut Across Flats drives a REGULAR hexagon (#948).

The #948 census (421 born families, counts only): every labelled hexagon (32, in
7 families) carries the same eleven sketch-member constraints -- five LOCKED
60-degree ``AngularDim``s across consecutive sides, three EQ
``LinearDimString``s about the origin planes, two labelled dimensions of one
instance formula parameter (= across flats / 2), one from the bottom flat to the
centre plane and one from a slant to the ORIGIN POINT (a
``CurveXCurveInPlaneRef``), and a zero-length corner pin drawn in a secret
internal dimension style.  ``rvt.famgen.angular_law`` authors that recipe on the
nested trapeze's hex nut with ONE stated substitution (the corner pin becomes a
second labelled slant).  These tests pin the written shape against the census,
judge every angle / EQ / label with the extended constraint law (CG9 / CG10) on
2026 and 2025, check the refusals leave the document untouched, and keep the
solid trapeze the default.  Nothing here claims Revit regenerates the hexagon:
no desktop verdict exists (hard rule 4).
"""
from __future__ import annotations

import copy
import math
import os
import shutil
import tempfile
from contextlib import ExitStack, nullcontext

import pytest

from rvt.famgen import angular_law as AL
from rvt.famgen import constraint_law as CL
from rvt.famgen import factory as F
from rvt.famgen import skeleton as SK
from rvt.famgen import trapeze_nested as TN
from conftest import context_constants, ladder_constants, streams

# builds enter the write-side release context (2025 targets) and the read-back
# climbs the read-side ladder: conftest's guard watches both (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")

IN = 1.0 / 12.0
AF = 0.5625 * IN
NUT_H = 0.328125 * IN


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the
    native codec singletons; do that once before the guard's first snapshot."""
    d = tempfile.mkdtemp(prefix="t948w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="t948_")
    yield d
    shutil.rmtree(d, True)


def _ctx(release):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return nullcontext()
    return RC.release_build_context(RC._bundled_base_of(release))


def _read(path, classes, unit=0, seq=102):
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    out = {c: {} for c in classes}
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        for c in classes:
            for i in fi.ids_of_class(unit, c):
                out[c][i] = fi.decode(unit, i, seq).value
    return out


def _nut(af=AF):
    return TN.make_hex_nut(1000, across_flats_ft=af, height_ft=NUT_H)


@pytest.fixture(scope="module", params=[2026, 2025])
def written_nut(request):
    """(release, product, path) -- the hex nut child written on its own."""
    d = tempfile.mkdtemp(prefix=f"t948n{request.param}_")
    path = os.path.join(d, "nut.rfa")
    with _ctx(request.param):
        prod = _nut()
        rep = prod.write(path)
    assert rep["ok"], rep.get("validate")
    yield request.param, prod, path
    shutil.rmtree(d, True)


@pytest.fixture(scope="module", params=[2026, 2025])
def nested(request):
    d = tempfile.mkdtemp(prefix=f"t948t{request.param}_")
    path = os.path.join(d, "trapeze.rfa")
    with _ctx(request.param):
        prod = F.make_archetype(product="strut_trapeze", nested_hardware=True)
        rep = prod.write(path)
    yield request.param, prod, rep, path
    shutil.rmtree(d, True)


# ---------------------------------------------------------------------------
# the census shape, role for role (born orientation: flats square to y, CCW,
# H0 = Q0 the bottom-right slant ... H5 = Fb the bottom flat)
# ---------------------------------------------------------------------------

#: per position in the sketch's m_dimIds: (class, m_flags, witness roles,
#: per-witness (constrFlags, oldRefSegEndIdx, id), segments (flags, id1, id2),
#: equality array (number, id1, id2), (lastSeg id1, id2, lastUsed), m_dimData)
#: -- the census table, 32 / 32 hexagons each; position 10 is the stated
#: substitute (born: a zero-length corner pin in a secret style)
_ANG = ((0, 0, 0), (0, 1, 1))
_EQ_SEGS = ((2, 0, 1), (2, 1, 2))
_LAB = ((0, 0, 0), (0, 0, 1))
CENSUS = [
    ("AngularDim", 12, ("Fb", "Q0"), _ANG, ((1, 0, 1),), ((1, 2, -1),), (2, -1, 1), None),
    ("AngularDim", 12, ("Q0", "Q1"), _ANG, ((1, 0, 1),), ((1, 2, -1),), (2, -1, 1), None),
    ("AngularDim", 12, ("Q1", "Ft"), _ANG, ((1, 0, 1),), ((1, 2, -1),), (2, -1, 1), None),
    ("AngularDim", 12, ("Ft", "Sp"), _ANG, ((1, 0, 1),), ((1, 2, -1),), (2, -1, 1), None),
    ("AngularDim", 12, ("Sp", "S"), _ANG, ((1, 0, 1),), ((1, 2, -1),), (2, -1, 1), None),
    ("LinearDimString", 140, ("Ft", "Ppar", "Fb"), ((0, 0, 0), (16, 1, 1), (0, 1, 2)),
     _EQ_SEGS, ((2, 3, -1),), (3, -1, 2), 3),
    ("LinearDimString", 140, ("Fb.0", "Pperp", "Fb.1"), ((0, 0, 0), (16, 0, 1), (0, 0, 2)),
     _EQ_SEGS, ((2, 3, -1),), (3, -1, 2), 0),
    ("LinearDimString", 140, ("Sp.0", "Pperp", "Ft.0"), ((0, 0, 0), (16, 1, 1), (0, 0, 2)),
     _EQ_SEGS, ((2, 3, -1),), (3, -1, 2), 0),
    ("LinearDimString", 12, ("S", "X(Pperp,Ppar)"), _LAB, ((0, 0, 1),), ((1, 2, -1),),
     (2, -1, 1), 3),
    ("LinearDimString", 12, ("Fb", "Ppar"), _LAB, ((0, 0, 1),), ((1, 2, -1),), (2, -1, 1), 3),
    # SUBSTITUTE (stated): the second labelled slant, the exact shape of position 8
    ("LinearDimString", 12, ("Sp", "X(Pperp,Ppar)"), _LAB, ((0, 0, 1),), ((1, 2, -1),),
     (2, -1, 1), 3),
]


def _roles(prod):
    sk = next(e for e in prod.doc.elements if e.class_name == "VarSketch"
              and e.obj.get("m_dimIds"))
    r = AL.hexagon_roles(sk)
    from rvt.famgen import drive_law as DL
    names = {r[k][0]: k for k in AL.ROLES}
    names[DL.origin_centre_plane(prod.doc, "y").elem_id] = "Ppar"
    names[DL.origin_centre_plane(prod.doc, "x").elem_id] = "Pperp"
    return sk, names


def _sig(o, names, sk_obj):
    roles = []
    for w in o["m_witnessRefs"]:
        ptr = w["m_pWitnessRef"]
        g = ptr["value"]["m_geomRef"]
        if ptr["ptr_class"] == "CurveXCurveInPlaneRef":
            ov = ptr["value"]
            assert ov["m_idx"] == 0 and ov["m_orientation"] == 0
            roles.append(f"X({names[g['m_elemId']]},{names[ov['m_otherGeomRef']['m_elemId']]})")
        else:
            n = names[g["m_elemId"]]
            roles.append(n if g["m_subTag"] == -1 else f"{n}.{g['m_subTag']}")
    eqa = o["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"]["m_arr"]
    dd = {x["first"]: x["second"] for x in sk_obj["m_dimData"]}
    return (tuple(roles),
            tuple((w["m_constrFlags"], w["m_oldRefSegEndIdx"], w["m_id"]["m_id"])
                  for w in o["m_witnessRefs"]),
            tuple((s["m_flags"], s["m_id"]["m_id1"], s["m_id"]["m_id2"]) for s in o["m_ArrSegInfo"]),
            tuple((s["m_equalitySegNumber"], s["m_id"]["m_id1"], s["m_id"]["m_id2"]) for s in eqa),
            (o["m_lastDimSegInfoId"]["m_id1"], o["m_lastDimSegInfoId"]["m_id2"],
             o["m_lastUsedId"]["m_id"]),
            dd.get(o["m_id"]))


def test_written_hexagon_matches_the_census_role_for_role(written_nut):
    release, prod, path = written_nut
    sk, names = _roles(prod)
    E = _read(path, ["AngularDim", "LinearDimString", "VarSketch"])
    H = _read(path, ["AngularDim", "LinearDimString", "VarSketch"], seq=101)
    sko = E["VarSketch"][sk.elem_id]
    assert len(sko["m_dimIds"]) == len(CENSUS) == 11
    for pos, (eid, want) in enumerate(zip(sko["m_dimIds"], CENSUS)):
        cls = "AngularDim" if eid in E["AngularDim"] else "LinearDimString"
        o, h = E[cls][eid], H[cls][eid]
        assert (cls, o["m_flags"]) == want[:2], pos
        assert _sig(o, names, sko) == want[2:], pos
        # every hexagon dimension: a sketch member owned by no view, dim
        # version 6, header regen = the sketch's own plane (192 / 192 + 160)
        assert o["m_cellList"]["value"]["m_cells"][0]["value"]["m_groupId"] == sk.elem_id
        assert o["m_ownerDBViewId"] == -1 and h["m_ownerViewId"] == -1
        assert o["m_dimVersion"] == 6
        assert h["m_parents"]["value"]["m_regenOnly"] == [sko["m_sketchPlaneId"]]
        assert h["m_categroryId"] == -2000260
        assert h["m_viewRules"]["m_nVisibleViewFlags"] == (-1 if cls == "AngularDim" else -4225)
        assert all(v["m_oTextFields"] is None for s in o["m_ArrSegInfo"] for v in s["m_values"])
        if cls == "AngularDim":
            seg = o["m_ArrSegInfo"][0]
            assert abs(seg["m_lockedValue"] - math.pi / 3.0) < 1e-12
            assert o["m_pDimArc"]["ptr_class"] == "GArc" and o["m_pDimArc"]["pid"] == 3
            assert not o["m_2ArcAngle"] and o["m_originIsSet"] and o["m_sectorHasBeenSet"]
    # the sketch: regen = Level + both origin planes; deletion holds every dim
    hp = H["VarSketch"][sk.elem_id]["m_parents"]["value"]
    assert {names.get(i) for i in hp["m_regenOnly"]} >= {"Ppar", "Pperp"}
    assert set(sko["m_dimIds"]) <= set(hp["m_deletion"])


def test_three_labels_carry_one_instance_formula_parameter(written_nut):
    _release, prod, path = written_nut
    half = prod.doc.params[TN.NUT_HALF_ACROSS_FLATS]
    E = _read(path, ["LinearDimString", "Family"])
    labels = [o for o in E["LinearDimString"].values()
              if any(s["m_paramId"] == half.elem_id for s in o["m_ArrSegInfo"])]
    assert len(labels) == 3
    assert all(abs(o["m_ArrSegInfo"][0]["m_lockedValue"] - AF / 2.0) < 1e-12 for o in labels)
    rows = [r for f in E["Family"].values()
            for r in (((f.get("m_familyParams") or {}).get("value") or {}).get("m_params") or [])
            if r.get("m_paramId") == half.elem_id]
    assert rows and all(r["m_instance"] for r in rows)
    expr = rows[0]["m_oExpression"]
    assert expr["ptr_class"] == "BinaryOperatorExpression"
    assert expr["value"]["m_binaryOperator"] == 4                      # '/'
    assert (expr["value"]["m_pLeftSubexpression"]["value"]["m_paramId"]
            == prod.doc.params["Nut Across Flats"].elem_id)
    assert abs(rows[0]["m_value"] - AF / 2.0) < 1e-12


def test_sketch_solver_state_is_the_census_form(written_nut):
    """One HV (horizontal, on the top flat) plus six point-point joins in the
    census order; m_angleCoef = the side; m_highResidualTol; the curve bit."""
    _release, prod, path = written_nut
    sk, names = _roles(prod)
    E = _read(path, ["VarSketch", "CurveElem"])
    v = E["VarSketch"][sk.elem_id]
    pid = {r["pid"]: names[r["value"]["m_objId"]] for r in v["m_elemRecs"]}
    got = [(r["ptr_class"], tuple(pid[x["weakref"]] for x in r["value"]["m_constrElems"]),
            tuple(r["value"]["m_constrSubTypes"])) for r in v["m_constrRecs"]]
    PP, HV = "VarSketchPPConstrObj", "VarSketchHorVerConstrObj"
    assert got == [(PP, ("Q1", "Q0"), (1, 2)), (PP, ("Ft", "Q1"), (1, 2)), (HV, ("Ft",), (0,)),
                   (PP, ("Sp", "Ft"), (1, 2)), (PP, ("S", "Sp"), (1, 2)),
                   (PP, ("Fb", "S"), (1, 2)), (PP, ("Fb", "Q0"), (2, 1))]
    assert [r["value"]["m_hor"] for r in v["m_constrRecs"] if r["ptr_class"] == HV] == [True]
    side = AF / math.sqrt(3.0)
    assert all(abs(r["value"]["m_angleCoef"] - side) < 1e-12 for r in v["m_elemRecs"])
    assert v["m_highResidualTol"] is True
    for r in v["m_elemRecs"]:
        crv = E["CurveElem"][r["value"]["m_objId"]]["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
        assert crv["m_GInfo"]["m_flags"] & 0x80000


def test_sketch_members_are_owned_by_their_sketch(written_nut):
    """ElemTable owner of every hexagon dimension = its sketch (born: 26,335 /
    26,335 linear and 66 / 66 angular sketch members in host documents)."""
    from rvt.container import open_rvt
    from rvt.elemtable import inflate_global_stream, parse_elemtable
    from rvt.genesis.skeleton import NO_OWNER
    _release, prod, path = written_nut
    sk, _names = _roles(prod)
    with open_rvt(path) as fh:
        t = parse_elemtable(inflate_global_stream(fh.raw("Global/ElemTable")).payload, "rfa")
    own = {int(r.id): (None if r.owner_id in (NO_OWNER, None) else int(r.owner_id))
           for r in t.records}
    assert {own[i] for i in sk.obj["m_dimIds"]} == {sk.elem_id}


def test_the_law_judges_the_nut_clean_and_validates(written_nut):
    from rvt.versions import detect_release
    release, prod, path = written_nut
    assert int(detect_release(path)) == release
    assert CL.check_file(path) == []
    assert CL.check_doc(prod.doc) == []


@pytest.mark.parametrize("af_in", [0.4375, 0.5625, 1.125])
def test_any_across_flats_writes_a_regular_hexagon(tmp, af_in):
    prod = _nut(af_in * IN)
    assert prod.doc.hexagon_drive is not None
    assert prod.doc.hexagon_drive["across_flats"] == pytest.approx(af_in * IN, abs=1e-12)
    p = os.path.join(tmp, "nut.rfa")
    rep = prod.write(p)
    assert rep["ok"] and rep["validate"]["family_mode"]["n_errors"] == 0
    assert CL.check_file(p) == []


# ---------------------------------------------------------------------------
# CG9 / CG10 actually JUDGE the hexagon: a tampered copy is caught
# ---------------------------------------------------------------------------

def _tuples(prod):
    return [(e.elem_id, e.class_name, copy.deepcopy(e.obj), copy.deepcopy(e.header))
            for e in prod.doc.elements]


def test_a_wrong_angle_lock_is_caught_by_cg9():
    prod = _nut()
    els = _tuples(prod)
    ang = [t for t in els if t[1] == "AngularDim"]
    assert len(ang) == 5 and CL.check_graph(els) == []
    ang[0][2]["m_ArrSegInfo"][0]["m_lockedValue"] = math.radians(45.0)
    assert [f["rule"] for f in CL.check_graph(els)] == ["CG9"]


@pytest.mark.parametrize("which", ["eq", "label", "crossing"])
def test_a_wrong_linear_value_is_caught_by_cg10(which):
    prod = _nut()
    els = _tuples(prod)
    hexd = prod.doc.hexagon_drive
    by = {t[0]: t for t in els}
    if which == "eq":
        seg = by[hexd["eq"][0]][2]["m_ArrSegInfo"][1]
        seg["m_values"][0]["m_value"] = seg["m_lockedValue"] = 2.0 * seg["m_lockedValue"]
    elif which == "label":
        by[hexd["labelled"][1]][2]["m_ArrSegInfo"][0]["m_values"][0]["m_value"] = 1.0
    else:   # the slant label to the plane crossing
        by[hexd["labelled"][0]][2]["m_ArrSegInfo"][0]["m_values"][0]["m_value"] = 1.0
    rules = [f["rule"] for f in CL.check_graph(els)]
    assert rules and set(rules) == {"CG10"}


# ---------------------------------------------------------------------------
# CG9 / CG10 / CG8 on synthetic graphs
# ---------------------------------------------------------------------------

def _line(eid, a, b):
    d = (b[0] - a[0], b[1] - a[1], 0.0)
    return (eid, "CurveElem", {"m_pCurveDriver": {"ptr_class": "CurveDriver", "value": {
        "m_pCrv": {"ptr_class": "GLine", "value": {
            "m_origin": [a[0], a[1], 0.0], "m_dirVec": list(d), "m_endParams": [0.0, 1.0]}}}}})


def _w(eid, sub=-1, cls="GeomSegInPlaneRef", other=None):
    v = {"m_geomRef": {"m_elemId": eid, "m_geomTag": 0, "m_subTag": sub}}
    if other is not None:
        v["m_otherGeomRef"] = {"m_elemId": other, "m_geomTag": 0, "m_subTag": -1}
    return {"m_pWitnessRef": {"ptr_class": cls, "value": v}}


def _seg(value, flags, param=-1):
    return {"m_lockedValue": value, "m_flags": flags, "m_paramId": param,
            "m_values": [{"m_value": value}]}


def _plane(eid, axis):
    """x = 0 plane ('x', normal x) or y = 0 plane ('y', normal y)."""
    if axis == "x":
        return (eid, "RefPlane", {"m_freeEnd": [0.0, -1.0, 0.0], "m_bubbleEnd": [0.0, 1.0, 0.0],
                                  "m_cutVec": [0.0, 0.0, 1.0]})
    return (eid, "RefPlane", {"m_freeEnd": [-1.0, 0.0, 0.0], "m_bubbleEnd": [1.0, 0.0, 0.0],
                              "m_cutVec": [0.0, 0.0, 1.0]})


@pytest.mark.parametrize("deg, rule", [(60.0, None), (120.0, None), (45.0, "CG9")])
def test_cg9_locked_angle(deg, rule):
    els = [_line(1, (0, 0), (1, 0)), _line(2, (1, 0), (1.5, math.sqrt(3) / 2)),
           (9, "AngularDim", {"m_witnessRefs": [_w(1), _w(2)],
                              "m_ArrSegInfo": [_seg(math.radians(deg), 1)]})]
    assert [f["rule"] for f in CL.check_graph(els)] == ([rule] if rule else [])


def test_cg9_judges_an_angular_eq_and_never_guesses():
    """Angular EQ (0 / 387 born -- judged on synthetic graphs only): three lines
    at 0, 30 and 60 degrees are equal angles; 0, 30, 90 are not."""
    def graph(third):
        return [_line(1, (0, 0), (1, 0)),
                _line(2, (0, 0), (math.cos(math.radians(30)), math.sin(math.radians(30)))),
                _line(3, (0, 0), (math.cos(math.radians(third)), math.sin(math.radians(third)))),
                (9, "AngularDim", {"m_witnessRefs": [_w(1), _w(2), _w(3)],
                                   "m_ArrSegInfo": [_seg(0.5, 2), _seg(0.5, 2)]})]
    assert CL.check_graph(graph(60)) == []
    assert [f["rule"] for f in CL.check_graph(graph(90))] == ["CG9"]
    # a plane witness is not a line: not judged
    els = [_plane(1, "x"), _line(2, (0, 0), (1, 1)),
           (9, "AngularDim", {"m_witnessRefs": [_w(1), _w(2)], "m_ArrSegInfo": [_seg(3.0, 1)]})]
    assert CL.check_graph(els) == []


def test_cg5_shapes_an_angular_dimension():
    els = [_line(1, (0, 0), (1, 0)), _line(2, (1, 0), (2, 1)),
           (9, "AngularDim", {"m_witnessRefs": [_w(1), _w(2)],
                              "m_ArrSegInfo": [_seg(0.1, 0), _seg(0.1, 0)]})]
    assert [f["rule"] for f in CL.check_graph(els)] == ["CG5"]


def _lds(witnesses, segs, d):
    return (9, "LinearDimString", {"m_witnessRefs": witnesses, "m_ArrSegInfo": segs,
                                   "m_pDimLine": {"ptr_class": "GLine", "value": {
                                       "m_dirVec": list(d)}}})


@pytest.mark.parametrize("value, rule", [(0.5, None), (0.75, "CG10")])
def test_cg10_label_to_a_plane_crossing(value, rule):
    """A slant 0.5 ft from the origin, labelled to the crossing of the two
    origin planes, measured along its normal (the hexagon's S label)."""
    n = (math.sqrt(3) / 2, 0.5, 0.0)
    t = (-n[1], n[0])                                             # along the line
    a = (-0.5 * n[0] + 0.5 * t[0], -0.5 * n[1] + 0.5 * t[1])      # 0.5 ft from the origin
    b = (a[0] + t[0], a[1] + t[1])
    els = [_plane(1, "x"), _plane(2, "y"), _line(3, a, b),
           _lds([_w(3), _w(1, cls="CurveXCurveInPlaneRef", other=2)], [_seg(value, 0, 77)], n)]
    assert [f["rule"] for f in CL.check_graph(els, universe=[77])] == ([rule] if rule else [])


@pytest.mark.parametrize("x1, rule", [(-1.0, None), (-1.5, "CG10")])
def test_cg10_eq_about_a_plane_with_line_ends(x1, rule):
    els = [_plane(1, "x"), _line(3, (x1, -1.0), (1.0, -1.0)),
           _lds([_w(3, 0), _w(1), _w(3, 1)], [_seg(1.0, 2), _seg(1.0, 2)], (1.0, 0.0, 0.0))]
    rules = [f["rule"] for f in CL.check_graph(els)]
    assert (set(rules) == {rule}) if rule else rules == []


def test_cg10_never_guesses_an_unresolved_or_oblique_witness():
    # a line NOT square to the dimension line, and a missing element
    els = [_plane(1, "x"), _line(3, (0.0, 0.0), (1.0, 1.0)),
           _lds([_w(3), _w(1)], [_seg(5.0, 0, 77)], (1.0, 0.0, 0.0))]
    assert CL.check_graph(els, universe=[77]) == []
    els = [_plane(1, "x"), _lds([_w(55), _w(1)], [_seg(5.0, 1)], (1.0, 0.0, 0.0))]
    assert [f["rule"] for f in CL.check_graph(els, universe=[55])] == []


def test_cg6_registers_a_sketch_member_dimension():
    member = {"ptr_class": "CellList", "value": {"m_cells": [
        {"ptr_class": "SketchMembership", "value": {"m_groupId": 50}}]}}
    els = [_line(1, (0, 0), (1, 0)), _line(2, (1, 0), (2, 1)),
           (50, "VarSketch", {"m_dimIds": []}, {"m_parents": {"value": {"m_deletion": []}}}),
           (9, "AngularDim", {"m_witnessRefs": [_w(1), _w(2)], "m_cellList": member,
                              "m_ArrSegInfo": [_seg(0.1, 0)]})]
    assert [f["rule"] for f in CL.check_graph(els)] == ["CG6"]


# ---------------------------------------------------------------------------
# #949 review: CG8's frame fields are reported when absent; one shared selector
# ---------------------------------------------------------------------------

def _inst_graph(**frame):
    plane = {"m_freeEnd": [0.0, 0.0, 1.0], "m_bubbleEnd": [1.0, 0.0, 1.0],
             "m_cutVec": [0.0, 1.0, 0.0]}

    def wit(eid, tag):
        return {"m_pWitnessRef": {"ptr_class": "GeomSegInPlaneRef", "value": {
            "m_geomRef": {"m_elemId": eid, "m_geomTag": tag}}}}
    lock = {"m_witnessRefs": [wit(10, 0), wit(20, 7)], "m_flags": 14, **frame}
    els = [(10, "RefPlane", plane), (20, "FamilyInstance", {}), (30, "Alignment", lock)]
    inst = {(20, 7): ((0.0, 0.0, 1.0), (0.0, 0.0, 1.0))}
    return CL.check_graph(els, instance_planes=inst)


FULL = {"m_constrDir": [0.0, 0.0, 1.0], "m_refPnts": [[0.5, 0.0, 1.0], [0.5, 0.0, 1.0]],
        "m_oldOrigin": [0.0, 0.0, 1.0]}


def test_cg8_frame_complete_is_silent():
    assert _inst_graph(**FULL) == []


@pytest.mark.parametrize("drop", ["m_constrDir", "m_refPnts", "m_oldOrigin"])
def test_cg8_frame_field_absent_is_reported(drop):
    frame = {k: v for k, v in FULL.items() if k != drop}
    f = _inst_graph(**frame)
    assert [(x["rule"], x["severity"]) for x in f] == [("CG8", CL.WARNING)]
    assert f[0]["missing"] == [drop]


def test_cg8_pick_is_the_one_selection_rule():
    plane = ((0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
    inst = {(20, 7): plane}
    g = [{"m_elemId": 10, "m_geomTag": 0}, {"m_elemId": 20, "m_geomTag": 7}]
    got = CL.cg8_pick(g, {10: plane}.get, inst)
    assert got[0] == 10 and got[2:4] == (20, 7)
    assert CL.cg8_pick(g, {}.get, inst) is None                       # no plane
    assert CL.cg8_pick(g + g[:1], {10: plane}.get, inst) is None       # three witnesses
    assert CL.cg8_pick(g, {10: plane}.get, {}) is None                 # no instance ref


# ---------------------------------------------------------------------------
# refusals: all-or-nothing, and the nut is still delivered
# ---------------------------------------------------------------------------

def _snapshot(doc):
    return [(e.elem_id, e.class_name, copy.deepcopy(e.obj), copy.deepcopy(e.header))
            for e in doc.elements], {k: dict(v) for k, v in doc.types}


def _bare_nut(ring=None, formula="Nut Across Flats / 2", half_value=None):
    doc = SK.new_family_document("generic_model", "n", work_plane_based=False,
                                 start_id=1000, plane_length_ft=1.0)
    part = {"shape": "polygon", "name": "nut", "vertices": ring or TN.hex_ring(AF),
            "height_ft": NUT_H, "center": [0.0, 0.0], "base_z_ft": 0.0}
    fb = F.add_generic_part(doc, part)
    af = doc.add_family_parameter("Nut Across Flats", SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                  is_instance=True, default=AF)
    half = doc.add_family_parameter(TN.NUT_HALF_ACROSS_FLATS, SK.SPEC_LENGTH,
                                    SK.PGROUP_DIMENSIONS, is_instance=True,
                                    formula=formula, default=AF / 2.0)
    doc.add_type("t", {af.elem_id: AF, half.elem_id: AF / 2.0 if half_value is None
                       else half_value})
    sk = next(e for e in fb.elements if e.class_name == "VarSketch")
    return doc, sk


def _rotated_ring():
    """The solid trapeze's orientation: flats square to x -- refused."""
    r = AF / math.sqrt(3.0)
    ring = [[r * math.cos(math.radians(a)), r * math.sin(math.radians(a))]
            for a in (30, 90, 150, 210, 270, 330)]
    return ring + [list(ring[0])]


@pytest.mark.parametrize("case", ["rotated", "formula", "value", "twice", "finalized"])
def test_a_refused_hexagon_drive_leaves_the_document_untouched(case):
    kw = {}
    if case == "rotated":
        kw["ring"] = _rotated_ring()
    elif case == "formula":
        kw["formula"] = "Nut Across Flats / 3"
    elif case == "value":
        kw["half_value"] = AF
    doc, sk = _bare_nut(**kw)
    if case == "twice":
        AL.wire_hexagon_drive(doc, sketch=sk, caption="Nut Across Flats",
                              half_caption=TN.NUT_HALF_ACROSS_FLATS)
    if case == "finalized":
        doc.finalize()
    before = _snapshot(doc)
    with pytest.raises(AL.AngularLawError):
        AL.wire_hexagon_drive(doc, sketch=sk, caption="Nut Across Flats",
                              half_caption=TN.NUT_HALF_ACROSS_FLATS)
    assert _snapshot(doc) == before


def test_a_refused_drive_still_delivers_the_nut(tmp, monkeypatch):
    def boom(doc, **kw):
        raise AL.AngularLawError("probe: refused")
    monkeypatch.setattr(AL, "wire_hexagon_drive", boom)
    prod = _nut()
    assert prod.doc.hexagon_drive is None
    assert any("VALUE ONLY" in n and "probe: refused" in n for n in prod.doc.notes)
    assert not [e for e in prod.doc.elements if e.class_name == "AngularDim"]
    p = os.path.join(tmp, "nut.rfa")
    assert prod.write(p)["ok"] and CL.check_file(p) == []


def test_the_nut_is_deterministic(tmp):
    # same file name (BasicFileInfo carries it), two directories
    a, b = os.path.join(tmp, "a", "nut.rfa"), os.path.join(tmp, "b", "nut.rfa")
    _nut().write(a)
    _nut().write(b)
    assert streams(a) == streams(b)


# ---------------------------------------------------------------------------
# the nested trapeze on 2026 and 2025: the nut's unit judged, the host locks too
# ---------------------------------------------------------------------------

def test_nested_trapeze_nut_unit_is_judged_clean(nested):
    release, prod, rep, path = nested
    from rvt.versions import detect_release
    assert rep["ok"] and rep["nested_hardware"]["ok"], rep.get("nested_hardware")
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    assert int(detect_release(path)) == release
    assert CL.check_file(path) == []
    units = CL.nested_units(path)
    with_ang = []
    for u in units.values():
        assert CL.check_file(path, u) == [], u
        E = _read(path, ["AngularDim"], unit=u)
        if E["AngularDim"]:
            with_ang.append(u)
            assert len(E["AngularDim"]) == 5
            assert all(abs(o["m_ArrSegInfo"][0]["m_lockedValue"] - math.pi / 3.0) < 1e-12
                       and o["m_ArrSegInfo"][0]["m_flags"] == 1 for o in E["AngularDim"].values())
    assert len(with_ang) == 1                   # the one nut family, nested once
    # every instance lock still judged (CG8, three per instance)
    nh = rep["nested_hardware"]
    insts = nh["washer"]["instance_ids"] + nh["nut"]["instance_ids"]
    judged = CL.judged_instance_locks(path)
    assert {(r["instance"], r["tag"]) for r in judged} == {(i, c) for i in insts
                                                           for c in (1, 4, 7)}


def test_nested_notes_say_the_hexagon_drives_without_a_verdict(nested):
    _release, _prod, rep, _path = nested
    notes = " ".join(rep["family"]["notes"])
    assert "drives the hexagon across flats" in notes and "VALUE ONLY" not in notes
    assert "no desktop verdict" in notes


def test_the_default_trapeze_stays_solid():
    """#948 decision (record): no desktop verdict exists for the nested lane's
    locks or the hexagon drive, so the solid trapeze stays the default."""
    prod = F.make_archetype(product="strut_trapeze")
    assert type(prod) is F.FamilyProduct
    assert not [e for e in prod.doc.elements if e.class_name == "AngularDim"]

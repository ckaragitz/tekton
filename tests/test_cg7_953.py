"""#953 -- CG7 corrected to the law Revit-born families follow.

The first reading of CG7 ("a sketch lock's curve lies on its plane") judged
BOTH ends of every locked line and read the plane from its drawn ends.  Over
the host documents of the 421-family born library it fired 139 errors (410
with the nested units): END locks (a ``GLine`` witnessed at geomTag 0,
subTag 0 / 1) were judged on their free end, and planes whose drawn ends are
off their own surface (``m_pSurface``) were read from the drawn ends.  The
corrected law -- an END lock pins THAT end; the plane is its surface -- holds
on every judged born lock (census: ``docs/inbox/param-drive.d/953-cg7.md``).

Synthetic positive / negative cases below; the corpus test skips cleanly when
the git-ignored ``samples/`` library is absent (fresh clone, CI).  Passing is
necessary, never sufficient (hard rule 4).
"""
import glob
import os

import pytest

from rvt.famgen import constraint_law as CL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(os.environ.get("TEKTON_ROOT") or ROOT, "samples", "evolve", "lib")


def _gref(eid, tag=0, sub=-1):
    return {"m_pWitnessRef": {"ptr_class": "GeomSegInPlaneRef", "pid": -1,
                              "value": {"m_geomRef": {"m_elemId": eid,
                                                      "m_geomTag": tag,
                                                      "m_subTag": sub}}}}


def _lock(*wit, sketch=40):
    return {"m_witnessRefs": [_gref(*w) for w in wit],
            "m_cellList": {"ptr_class": "CellList", "pid": -1, "value": {
                "m_cells": [{"ptr_class": "SketchMembership", "pid": -1,
                             "value": {"m_groupId": sketch}}]}}}


def _plane_x(x, surface_x=None):
    """A vertical RefPlane drawn at x = ``x``; with ``surface_x`` it also
    carries its own surface (``m_pSurface``) at x = ``surface_x``."""
    o = {"m_freeEnd": [x, -5.0, 0.0], "m_bubbleEnd": [x, 5.0, 0.0],
         "m_cutVec": [0.0, 0.0, 1.0]}
    if surface_x is not None:
        o["m_pSurface"] = {"ptr_class": "Plane", "pid": 7, "value": {
            "m_origin": [surface_x, 0.0, 0.0], "m_xVec": [0.0, 1.0, 0.0],
            "m_yVec": [0.0, 0.0, 1.0]}}
    return o


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


#: a line along +x from (1, 0) to (3, 0): its START end is at x = 1, its
#: END end at x = 3 (perpendicular to the planes x = c)
ACROSS = _line((1.0, 0.0, 0.0), (1.0, 0.0, 0.0), 2.0)


def _graph(curve, plane, tag=0, sub=-1):
    return [(10, "Alignment", _lock((30, 0, -1), (20, tag, sub))),
            (20, "CurveElem", curve),
            (30, "RefPlane", plane),
            (40, "VarSketch", {"m_dimIds": [10]},
             {"m_parents": {"ptr_class": "ElementParents", "pid": -1,
                            "value": {"m_deletion": [10, 20, 30]}}})]


def _rules(findings):
    return sorted(f["rule"] for f in findings)


# -- END locks pin one end ---------------------------------------------------

@pytest.mark.parametrize("sub,x", [(0, 1.0), (1, 3.0)])
def test_an_end_lock_pins_only_its_own_end(sub, x):
    # the born case the first reading flagged: the OTHER end is 2 ft away
    assert CL.check_graph(_graph(ACROSS, _plane_x(x), sub=sub)) == []


@pytest.mark.parametrize("sub,x", [(0, 3.0), (1, 1.0)])
def test_an_end_lock_whose_own_end_is_off_the_plane_fails(sub, x):
    f = CL.check_graph(_graph(ACROSS, _plane_x(x), sub=sub))
    assert _rules(f) == ["CG7"]
    assert f[0]["severity"] == CL.ERROR and f[0]["offset_ft"] == pytest.approx(2.0)


@pytest.mark.parametrize("sub,x", [(0, 1.25), (1, 2.5)])
def test_an_end_lock_slightly_off_fails(sub, x):
    f = CL.check_graph(_graph(ACROSS, _plane_x(x), sub=sub))
    assert _rules(f) == ["CG7"] and f[0]["offset_ft"] == pytest.approx(0.25 if sub == 0 else 0.5)


def test_a_whole_line_lock_still_pins_both_ends():
    along = _line((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 2.0)
    assert CL.check_graph(_graph(along, _plane_x(1.0), sub=-1)) == []
    # the line crossing the plane: its start is on it, its end 2 ft off
    f = CL.check_graph(_graph(ACROSS, _plane_x(1.0), sub=-1))
    assert _rules(f) == ["CG7"] and f[0]["offset_ft"] == pytest.approx(2.0)


def test_an_unknown_subtag_is_not_judged():
    assert CL.check_graph(_graph(ACROSS, _plane_x(9.0), sub=2)) == []


def test_lock_points_sub_tag_reading():
    assert len(CL.lock_points("CurveElem", ACROSS, 0)) == 2          # historical
    assert len(CL.lock_points("CurveElem", ACROSS, 0, -1)) == 2
    assert CL.lock_points("CurveElem", ACROSS, 0, 0) == [(1.0, 0.0, 0.0)]
    assert CL.lock_points("CurveElem", ACROSS, 0, 1) == [(3.0, 0.0, 0.0)]
    assert CL.lock_points("CurveElem", ACROSS, 0, 5) is None


# -- the plane is its own surface ---------------------------------------------

def test_the_plane_is_read_from_its_surface_not_its_drawn_ends():
    along = _line((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 2.0)
    # drawn ends at x = 4 (stale), surface at x = 1: the born case -- holds
    assert CL.check_graph(_graph(along, _plane_x(4.0, surface_x=1.0))) == []
    # drawn ends at x = 1, surface at x = 4: the curve is 3 ft off the plane
    f = CL.check_graph(_graph(along, _plane_x(1.0, surface_x=4.0)))
    assert _rules(f) == ["CG7"] and f[0]["offset_ft"] == pytest.approx(3.0)


def test_an_arc_centre_lock_uses_the_surface_too():
    assert CL.check_graph(_graph(_arc((1.0, 3.0, 0.0)), _plane_x(6.0, surface_x=1.0),
                                 tag=1)) == []
    f = CL.check_graph(_graph(_arc((1.0, 3.0, 0.0)), _plane_x(1.0, surface_x=1.5), tag=1))
    assert _rules(f) == ["CG7"] and f[0]["offset_ft"] == pytest.approx(0.5)


def test_a_surface_only_plane_is_now_judged():
    # drawn ends collapsed to one point (born surface-only planes): the
    # drawn-end reading could not judge this lock; the surface can
    plane = _plane_x(1.0, surface_x=2.0)
    plane["m_bubbleEnd"] = list(plane["m_freeEnd"])
    along = _line((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), 2.0)
    f = CL.check_graph(_graph(along, plane))
    assert _rules(f) == ["CG7"] and f[0]["offset_ft"] == pytest.approx(1.0)
    plane["m_pSurface"]["value"]["m_origin"] = [1.0, 0.0, 0.0]
    assert CL.check_graph(_graph(along, plane)) == []


def test_cg7_stays_live_rule_not_retired():
    assert "CG7" not in CL.RETIRED_RULES


# -- the born library (development instrument; absent in a fresh clone) ------

def _corpus():
    files = sorted(glob.glob(os.path.join(CORPUS, "**", "*.rfa"), recursive=True))
    if not files:
        pytest.skip("born reference library (samples/, git-ignored) not present")
    return files


@pytest.mark.slow
def test_cg7_is_silent_on_the_born_host_documents():
    if os.environ.get("RVT_SKIP_LARGE"):
        pytest.skip("RVT_SKIP_LARGE set")
    files = _corpus()
    bad = []
    for p in files:
        cg7 = [f for f in CL.check_file(p) if f["rule"] == "CG7"]
        if cg7:
            bad.append((os.path.basename(p), len(cg7)))
    assert bad == [], f"{len(bad)} born host documents with CG7 findings"


def test_a_none_tag_reads_as_its_default():
    """#963 review: a gref tag decoded as None is the default, never a TypeError."""
    from rvt.famgen import constraint_law as CL
    assert CL._tag({"m_subTag": None}, "m_subTag", -1) == -1
    assert CL._tag({}, "m_geomTag", 0) == 0
    assert CL._tag({"m_subTag": 1}, "m_subTag", -1) == 1

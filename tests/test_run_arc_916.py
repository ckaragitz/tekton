"""#916 DONE 3 for horizontal runs: a run's circle is ONE full arc, as born runs draw it.

Census (421-family private reference corpus, a development instrument, counts only;
record ``docs/inbox/param-drive.d/916-run-arc.md``): every one of the 147 born horizontal
runs whose profile is one circle sketches it as ONE ``CurveElem`` whose ``GArc`` has
endParams [0, 0] -- no control joins, header deletion [family, SketchPlane, sketch, self]
-- which the sketch absorbs as two halves (tag 0 [0, pi], tag 1 [pi, 2pi]) with ONE
unbounded ``VarSketchArcObj``; the extrusion's helper loop is ([pi, 2pi], [0, pi]) and its
B-rep the same two-half-cylinder solid the two-half-arc form carries.  A labelled type-9
diameter witnesses that arc with geomTag 0 and a cached [0, pi] arc.

``run_law.add_run_cylinder`` now authors that shape (``geometry.full_arc_cylinder_form``)
and ``diameter_law`` labels the full arc.  The plan-circle forms (``cylinder`` parts, the
rotated-B-rep ``cylinder_x``, the trapeze rods, the downlight) keep their two half arcs
and their bytes.  Every check here reads back from the WRITTEN file on 2026 and 2025.

Nothing here claims a family flexes in Revit (hard rule 4): authored, unverified.
"""
from __future__ import annotations

import hashlib
import math
import os
import shutil
import tempfile
from contextlib import ExitStack

import pytest

from rvt.families import FamilyIndex
from rvt.famgen import constraint_law as CL
from rvt.famgen import factory as F
from rvt.famgen import geometry as G
from rvt.famgen import run_law as RL
from conftest import HAVE_SCHEMA, context_constants, ladder_constants

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFC = os.path.join(ROOT, "inputs", "ifc", "chicago-plenum-downlight.ifc")

# builds enter the write-side release context (2025 targets) and the read-back
# climbs the read-side ladder: conftest's guard watches both (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the native
    codec singletons (by design); do that once before the guard's first snapshot."""
    d = tempfile.mkdtemp(prefix="t916arw_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


TOL = 1e-9
RUN = {"name": "run", "shape": "cylinder_x", "radius_ft": 0.1, "length_ft": 2.0,
       "center": [0.0, 0.0], "base_z_ft": -0.1, "work_plane": "vertical"}


def _run_y(cross=0.3, z=0.4):
    return F.make_generic_model(
        parts=[dict(RUN, shape="cylinder_y", center=[cross, 0.0], base_z_ft=z)],
        name="RY", numeric_params={"Length": ("length", 2.0), "D": ("length", 0.2)},
        runs=[{"caption": "Length", "parts": ["run"]}],
        diameters=[{"caption": "D", "parts": ["run"]}])


BUILDS = {
    "conduit": lambda: F.make_archetype(product="conduit"),
    "conduit_2in": lambda: F.make_archetype(product="conduit", dimensions={"diameter_in": 2.0}),
    "run_y": _run_y,
}


def _write(prod, path):
    if hasattr(prod, "write"):
        return prod.write(path)
    from rvt.frontdoor.standalone import standalone_family_write
    return standalone_family_write(prod, path, provenance=False)


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t916asha_")
    try:
        path = os.path.join(d, "f.rfa")
        res = _write(prod, path)
        assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    finally:
        shutil.rmtree(d, True)


def _in_release(release, build):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return build()
    with RC.release_build_context(RC._bundled_base_of(release)):
        return build()


def _read(path):
    with ExitStack() as st:
        from rvt.global_framing import enter_own_release
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0)
        out = {}
        for eid, r in recs.get(102, {}).items():
            cls = fi.class_name(r.class_id)
            if cls in ("CurveElem", "VarSketch", "ExtrusionElem", "RadialDim", "RefPlane",
                       "Alignment"):
                h = fi.decode(0, eid, 101) if eid in recs.get(101, {}) else None
                out[eid] = (cls, fi.decode(0, eid, 102).value, h.value if h else {})
        return out


def _full(ep) -> bool:
    return abs(float(ep[0])) < TOL and abs(float(ep[1])) < TOL


def _crv(o):
    return o["m_pCurveDriver"]["value"]["m_pCrv"]


# --------------------------------------------------------------------------- in memory

def test_the_run_circle_is_one_full_arc_shaped_as_born():
    prod = F.make_archetype(product="conduit")
    run = next(fb for fb in prod.forms if RL.is_run(fb))
    assert [e.class_name for e in run.elements] == [
        "SketchPlane", "VarSketch", "CurveElem", "ExtrusionElem"]
    sp, sk, ce, ex = run.elements
    arc = _crv(ce.obj)
    assert arc["ptr_class"] == "GArc" and _full(arc["value"]["m_endParams"])
    assert ce.obj["m_pCurveDriver"]["value"]["m_controlJoinsSet"] == []
    assert [c["ptr_class"] for c in ce.obj["m_cellList"]["value"]["m_cells"]] == [
        "SketchMembership", "ArcElemCell"]
    fam = prod.doc.self_family.elem_id
    assert ce.header["m_parents"]["value"]["m_deletion"] == sorted(
        [fam, sp.elem_id, sk.elem_id, ce.elem_id])
    # the rep: one full arc whose bbox is the whole circle (in the YZ plane)
    (node,) = ce.rep["m_subNodes"]
    assert _full(node["value"]["m_endParams"])
    r = arc["value"]["m_radius"]
    lo, hi = ce.rep["m_bBox"]
    assert hi[1] - lo[1] == pytest.approx(2 * r) and hi[2] - lo[2] == pytest.approx(2 * r)
    # the sketch absorbs it as two halves, owned by the ONE CurveElem
    o = sk.obj
    halves = [(a["value"]["m_GInfo"]["m_tag"], a["value"]["m_endParams"])
              for a in o["m_absorbedCurves"]]
    assert halves == [(0, [0.0, math.pi]), (1, [math.pi, 2 * math.pi])]
    assert o["m_elemIdsPairSet"]["value"]["m_data"] == [{"m_elementId": ce.elem_id,
                                                         "m_index": 0}]
    assert o["m_nextIndex"] == 1 and len(o["m_absorbedCurvesData"]) == 2
    (rec,) = o["m_elemRecs"]
    assert rec["ptr_class"] == "VarSketchArcObj" and rec["value"]["m_unbounded"] is True
    assert rec["value"]["m_angleCoef"] == pytest.approx(r)
    ps = [p["value"]["m_val"] for p in rec["value"]["m_params"]]
    assert ps[2:] == pytest.approx([r, 0.0, 2 * math.pi * r])
    hist = o["m_geomSteps"]["value"]["m_nonBRepGList"][0]["value"]["m_curveHistTableSet"]
    assert [(h["m_id"], h["m_curveHist"]["m_keys"][1]) for h in hist] == [(1, -10000), (0, 0)]
    # the extrusion's helper loop: [pi, 2pi] (tag 1) then [0, pi] (tag 0)
    helper = next(c["value"] for c in ex.obj["m_cellList"]["value"]["m_cells"]
                  if c["ptr_class"] == "ExtrusionElemExtrusionHelper")
    (loop,) = helper["m_pCurveLoops"]
    assert [(c["value"]["m_GInfo"]["m_tag"], c["value"]["m_endParams"])
            for c in loop["value"]["m_curves"]] == [(1, [math.pi, 2 * math.pi]),
                                                   (0, [0.0, math.pi])]
    assert run.params["full_arc"] is True


def test_the_diameter_label_is_on_the_full_arc():
    prod = F.make_archetype(product="conduit")
    run = next(fb for fb in prod.forms if RL.is_run(fb))
    ce = next(e for e in run.elements if e.class_name == "CurveElem")
    (rd,) = prod.doc.by_class("RadialDim")
    (w,) = rd.obj["m_witnessRefs"]
    g = w["m_pWitnessRef"]["value"]["m_geomRef"]
    assert (g["m_elemId"], g["m_geomTag"]) == (ce.elem_id, 0)
    assert w["m_pCachedArc"]["value"]["m_endParams"] == [0.0, math.pi]
    assert ce.elem_id in rd.header["m_parents"]["value"]["m_deletion"]
    assert prod.diameters["half_arc"] is False
    note = next(n for n in prod.doc.notes if n.startswith("diameters labelled"))
    assert "half arc" not in note and "NO desktop verdict" in note


# --------------------------------------------------------------------------- written

@pytest.mark.parametrize("release", [2026, 2025])
@pytest.mark.parametrize("key", sorted(BUILDS))
def test_the_written_run_carries_one_full_arc_and_its_label(key, release):
    d = tempfile.mkdtemp(prefix=f"t916a_{release}_")
    try:
        def build():
            prod = BUILDS[key]()
            path = os.path.join(d, "f.rfa")
            res = _write(prod, path)
            assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
            return prod, path
        prod, path = _in_release(release, build)
        E = _read(path)
        run = next(fb for fb in prod.forms if RL.is_run(fb))
        sk_id = next(e.elem_id for e in run.elements if e.class_name == "VarSketch")
        arcs = [eid for eid, (c, o, h) in E.items() if c == "CurveElem"
                and sk_id in (h.get("m_parents") or {}).get("value", {}).get("m_deletion", [])]
        assert len(arcs) == 1
        o = E[arcs[0]][1]
        assert _crv(o)["ptr_class"] == "GArc" and _full(_crv(o)["value"]["m_endParams"])
        assert E[sk_id][1]["m_curveObjIdxMap"] == [{"first": arcs[0], "second": 0}]
        rds = [o for c, o, _h in E.values() if c == "RadialDim"]
        assert len(rds) == 1
        g = rds[0]["m_witnessRefs"][0]["m_pWitnessRef"]["value"]["m_geomRef"]
        assert (g["m_elemId"], g["m_geomTag"]) == (arcs[0], 0)
        assert CL.check_file(path) == []
        assert not [n for n in prod.doc.notes if "not wired" in n]
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- the rest

def _guarded(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a plan-circle constructor reached the full-arc form")
    monkeypatch.setattr(G, "full_arc_cylinder_form", boom)


PLAN_CIRCLES = {
    "cylinder_part": lambda: F.make_generic_model(
        parts=[{"name": "c", "shape": "cylinder", "radius_ft": 0.2, "height_ft": 1.0}],
        name="CP"),
    "rotated_cylinder_x": lambda: F.make_generic_model(parts=[dict(RUN, work_plane=None)],
                                                       name="RR"),
    "trapeze": lambda: F.make_archetype(product="strut_trapeze"),
}


@pytest.mark.parametrize("key", sorted(PLAN_CIRCLES))
def test_the_plan_circles_keep_two_half_arcs_and_their_bytes(key, monkeypatch):
    """Every other circle constructor never reaches the full-arc form (the bytes with
    it disabled equal the bytes without), and still draws two half arcs."""
    free = _sha(PLAN_CIRCLES[key]())
    _guarded(monkeypatch)
    prod = PLAN_CIRCLES[key]()
    assert _sha(prod) == free
    arcs = [_crv(e.obj)["value"]["m_endParams"] for e in prod.doc.by_class("CurveElem")
            if _crv(e.obj)["ptr_class"] == "GArc"]
    assert arcs and not any(_full(a) for a in arcs)
    assert sorted(map(tuple, arcs))[0] == (-math.pi, 0.0)


@pytest.mark.skipif(not (os.path.exists(IFC) and HAVE_SCHEMA),
                    reason="downlight IFC input / class schema absent")
def test_the_downlight_plan_circles_never_reach_the_full_arc(monkeypatch):
    from rvt.ifc import famfrom_ifc as FI
    free = _sha(FI.make_downlight())
    _guarded(monkeypatch)
    assert _sha(FI.make_downlight()) == free


def test_the_end_planes_cover_an_off_centre_run():
    """A run far off the origin across its axis: the end planes' envelope and the
    plane witness trace of each face lock hold the cap face (#950 review)."""
    cross = 8.0
    prod = _run_y(cross=cross, z=0.4)
    assert prod.runs["wired"] == 1 and prod.runs["refused"] == []
    doc = prod.doc
    ex = next(e.elem_id for fb in prod.forms if RL.is_run(fb) for e in fb.elements
              if e.class_name == "ExtrusionElem")
    planes = {p.elem_id: p for p in doc.refplanes}
    n = 0
    for al in doc.by_class("Alignment"):
        ws = al.obj["m_witnessRefs"]
        ids = [w["m_pWitnessRef"]["value"]["m_geomRef"]["m_elemId"] for w in ws]
        if ex not in ids:
            continue
        pw = next(w for w, i in zip(ws, ids) if i in planes)
        fw = next(w for w, i in zip(ws, ids) if i == ex)
        rp = planes[next(i for i in ids if i in planes)]
        ext = rp.obj["m_pSurface"]["value"]
        half = max(abs(c) for c in ext["m_Envelope"]["m_corners"][1])
        face_x = [p[0] for p in fw["m_oldRefSegEnds"]]
        plane_x = [p[0] for p in pw["m_oldRefSegEnds"]]
        # a Y run: the cross axis is world X, the plane's surface x is -X
        assert max(abs(x) for x in face_x) == pytest.approx(cross + 0.1)
        assert half >= cross + 0.1 + 1.0 - 1e-9
        assert min(plane_x) <= min(face_x) and max(plane_x) >= max(face_x)
        n += 1
    assert n == 2
    assert CL.check_doc(doc) == []


def test_the_centred_run_planes_are_unchanged_by_the_reach():
    """The conduit's run is at the origin: the reach adds nothing to its planes."""
    from rvt.famgen import drive_law as DL
    prod = F.make_archetype(product="conduit")
    P = DL._dim_ctx(prod.doc)["P"]
    for rp in prod.doc.refplanes:
        if DL.is_surface_only(rp):
            ext = rp.obj["m_pSurface"]["value"]["m_Envelope"]["m_corners"]
            assert max(abs(c) for c in ext[1]) == pytest.approx(max(P, 5.0 + 1.0))


def test_a_vertical_work_plane_on_a_box_is_said_not_silently_dropped():
    prod = F.make_generic_model(
        parts=[{"name": "b", "shape": "box", "width_ft": 1.0, "depth_ft": 1.0,
                "height_ft": 1.0, "work_plane": "vertical"}], name="BV")
    plain = F.make_generic_model(
        parts=[{"name": "b", "shape": "box", "width_ft": 1.0, "depth_ft": 1.0,
                "height_ft": 1.0}], name="BV")
    assert any("work_plane 'vertical' applies to cylinder_x / cylinder_y" in n
               for n in prod.doc.notes)
    assert not any("work_plane" in n for n in plain.doc.notes)
    assert _sha(prod) == _sha(plain)


def test_a_finalized_document_refuses_with_run_error():
    doc = F.SK.new_family_document("generic_model", "x", work_plane_based=False,
                                   start_id=1000)
    run = F.add_generic_part(doc, dict(RUN))
    doc.finalized = True
    with pytest.raises(RL.RunError, match="finalized"):
        RL.wire_run_length(doc, caption="Length", targets=[run])

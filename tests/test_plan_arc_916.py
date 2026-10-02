"""#916 DONE 3 for PLAN circles: a circle on the Ref. Level is ONE full arc, as born plan
circles are.

Census (421-family private reference corpus, a development instrument, counts only;
record ``docs/inbox/param-drive.d/916-plan-arc.md``): of the 235 born extrusions on a
horizontal sketch plane whose profile is one circle, 235 draw it as ONE ``CurveElem``
whose ``GArc`` has endParams [0, 0]; the sketch absorbs it as two halves (tag 0 [0, pi],
tag 1 [pi, 2pi]) with ONE unbounded ``VarSketchArcObj``, the helper loop is
([pi, 2pi], [0, pi]), and the B-rep the same two-half-cylinder solid -- the run census's
shape (#955), so ``geometry.cylinder`` now draws ``full_arc_cylinder_form`` for every
plan circle: ``cylinder`` parts, the strut trapeze's threaded rods (Rod Diameter), the
downlight's can / trim / lens, the fan-powered box's and fan coil's round parts.  The
rotated-B-rep ``cylinder_x`` / ``cylinder_y`` keeps its two-half authoring circle and its
bytes; ``geometry.PLAN_CIRCLE_FULL_ARC = False`` is the way back.  Every written check
reads back its own file on 2026 and 2025.

Nothing here claims a family loads or flexes in Revit (hard rule 4): the two-half form
has a desktop LOAD verdict (#589); the full plan arc is authored, unverified.
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
    d = tempfile.mkdtemp(prefix="t916pw_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


TOL = 1e-9
CYL = {"name": "c", "shape": "cylinder", "radius_ft": 0.2, "height_ft": 1.0,
       "center": [0.5, -0.25], "base_z_ft": 0.1}


def _cyl_d():
    return F.make_generic_model(parts=[dict(CYL)], name="CPD",
                                numeric_params={"D": ("length", 0.4)},
                                diameters=[{"caption": "D", "parts": ["c"]}])


def _downlight():
    from rvt.ifc import famfrom_ifc as FI
    return FI.make_downlight()


BUILDS = {
    "cylinder_d": _cyl_d,
    "trapeze": lambda: F.make_archetype(product="strut_trapeze"),
}


def _write(prod, path):
    if hasattr(prod, "write"):
        return prod.write(path)
    from rvt.frontdoor.standalone import standalone_family_write
    return standalone_family_write(prod, path, provenance=False)


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t916psha_")
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
            if cls in ("CurveElem", "VarSketch", "RadialDim", "Alignment", "DimensionStyle"):
                h = fi.decode(0, eid, 101) if eid in recs.get(101, {}) else None
                out[eid] = (cls, fi.decode(0, eid, 102).value, h.value if h else {})
        return out


def _full(ep) -> bool:
    return abs(float(ep[0])) < TOL and abs(float(ep[1])) < TOL


def _crv(o):
    return o["m_pCurveDriver"]["value"]["m_pCrv"]


def _plan_circle_bundles(prod):
    return [fb for fb in prod.forms if fb.kind == "cylinder"
            and not fb.params.get("rotated_brep") and not fb.params.get("vertical_sketch")]


# --------------------------------------------------------------------------- in memory

def test_a_plan_cylinder_part_is_one_full_arc_on_the_level():
    prod = F.make_generic_model(parts=[dict(CYL)], name="CP")
    (fb,) = _plan_circle_bundles(prod)
    assert [e.class_name for e in fb.elements] == [
        "SketchPlane", "VarSketch", "CurveElem", "ExtrusionElem"]
    sp, sk, ce, ex = fb.elements
    arc = _crv(ce.obj)
    assert arc["ptr_class"] == "GArc" and _full(arc["value"]["m_endParams"])
    assert arc["value"]["m_center"] == [0.5, -0.25, 0.0]
    assert ce.obj["m_pCurveDriver"]["value"]["m_controlJoinsSet"] == []
    assert [c["ptr_class"] for c in ce.obj["m_cellList"]["value"]["m_cells"]] == [
        "SketchMembership", "ArcElemCell"]
    par = ce.header["m_parents"]["value"]
    assert par["m_deletion"] == sorted([prod.doc.self_family.elem_id, sp.elem_id,
                                        sk.elem_id, ce.elem_id])
    # regenOnly [work plane, extrusion]: the plan circle's work plane is the Level (202 / 235)
    assert par["m_regenOnly"][-1] == ex.elem_id and len(par["m_regenOnly"]) == 2
    # the sketch: two halves of ONE CurveElem, one unbounded solver record (angleCoef = r)
    o = sk.obj
    assert [(a["value"]["m_GInfo"]["m_tag"], a["value"]["m_endParams"])
            for a in o["m_absorbedCurves"]] == [(0, [0.0, math.pi]), (1, [math.pi, 2 * math.pi])]
    assert o["m_curveObjIdxMap"] == [{"first": ce.elem_id, "second": 0}]
    (rec,) = o["m_elemRecs"]
    assert rec["value"]["m_unbounded"] is True
    assert rec["value"]["m_angleCoef"] == pytest.approx(0.2)
    # the extrusion: helper loop [pi, 2pi] then [0, pi]; plan B-rep, extrude UP from base_z
    helper = next(c["value"] for c in ex.obj["m_cellList"]["value"]["m_cells"]
                  if c["ptr_class"] == "ExtrusionElemExtrusionHelper")
    (loop,) = helper["m_pCurveLoops"]
    assert [c["value"]["m_endParams"] for c in loop["value"]["m_curves"]] == [
        [math.pi, 2 * math.pi], [0.0, math.pi]]
    assert ex.refs["params"] == {"start_ft": 0.1, "end_ft": 1.1}
    assert fb.params["full_arc"] is True and "tessellation" in fb.params
    assert any("ONE full-arc CurveElem" in n for n in fb.notes)


def test_the_way_back_draws_two_half_arcs(monkeypatch):
    monkeypatch.setattr(G, "PLAN_CIRCLE_FULL_ARC", False)
    prod = F.make_generic_model(parts=[dict(CYL)], name="CP")
    (fb,) = _plan_circle_bundles(prod)
    arcs = [_crv(e.obj)["value"]["m_endParams"] for e in fb.elements
            if e.class_name == "CurveElem"]
    assert sorted(map(tuple, arcs)) == [(-math.pi, 0.0), (0.0, math.pi)]
    assert "full_arc" not in fb.params


def test_the_trapeze_rods_take_one_full_arc_each_and_one_centre_lock(monkeypatch):
    """Rod Diameter labels one full arc per rod; each rod circle's follow lock is ONE
    centre Alignment (geomTag 1), where the two-half circle needed one per half."""
    def census(prod):
        doc = prod.doc
        arcs = {e.elem_id: e for e in doc.by_class("CurveElem")
                if _crv(e.obj)["ptr_class"] == "GArc"}
        locks = sum(1 for al in doc.by_class("Alignment") for w in al.obj["m_witnessRefs"]
                    if w["m_pWitnessRef"]["value"]["m_geomRef"]["m_elemId"] in arcs
                    and w["m_pWitnessRef"]["value"]["m_geomRef"]["m_geomTag"] == 1)
        dims = [w["m_pWitnessRef"]["value"]["m_geomRef"]
                for d in doc.by_class("RadialDim") for w in d.obj["m_witnessRefs"]]
        return arcs, locks, dims

    full = F.make_archetype(product="strut_trapeze")
    arcs, locks, dims = census(full)
    rods = _plan_circle_bundles(full)
    assert rods and len(arcs) == len(rods)
    assert all(_full(_crv(a.obj)["value"]["m_endParams"]) for a in arcs.values())
    assert len(dims) == len(rods) and {(g["m_elemId"], g["m_geomTag"]) for g in dims} == {
        (i, 0) for i in arcs}
    assert locks == len(rods)
    assert full.diameters["wired"] == 1 and full.diameters["half_arc"] is False
    assert not [n for n in full.doc.notes if "not wired" in n or "half arc" in n]
    monkeypatch.setattr(G, "PLAN_CIRCLE_FULL_ARC", False)
    _arcs, half_locks, half_dims = census(F.make_archetype(product="strut_trapeze"))
    assert len(half_dims) == len(dims) and half_locks == 2 * locks
    assert CL.check_doc(full.doc) == []


# --------------------------------------------------------------------------- written

@pytest.mark.parametrize("release", [2026, 2025])
@pytest.mark.parametrize("key", sorted(BUILDS))
def test_the_written_plan_circles_are_full_arcs_with_their_labels(key, release):
    d = tempfile.mkdtemp(prefix=f"t916p_{release}_")
    try:
        def build():
            prod = BUILDS[key]()
            path = os.path.join(d, "f.rfa")
            res = _write(prod, path)
            assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
            return prod, path
        prod, path = _in_release(release, build)
        E = _read(path)
        circles = _plan_circle_bundles(prod)
        assert circles
        for fb in circles:
            sk_id = next(e.elem_id for e in fb.elements if e.class_name == "VarSketch")
            arcs = [eid for eid, (c, o, h) in E.items() if c == "CurveElem"
                    and sk_id in (h.get("m_parents") or {}).get("value", {}).get("m_deletion", [])]
            assert len(arcs) == 1, (key, fb.params)
            assert _full(_crv(E[arcs[0]][1])["value"]["m_endParams"])
            assert E[sk_id][1]["m_curveObjIdxMap"] == [{"first": arcs[0], "second": 0}]
        full_ids = {eid for eid, (c, o, _h) in E.items() if c == "CurveElem"
                    and _crv(o)["ptr_class"] == "GArc" and _full(_crv(o)["value"]["m_endParams"])}
        rds = [o for c, o, _h in E.values() if c == "RadialDim"]
        assert rds
        for o in rds:
            (w,) = o["m_witnessRefs"]
            g = w["m_pWitnessRef"]["value"]["m_geomRef"]
            assert g["m_elemId"] in full_ids and g["m_geomTag"] == 0
            assert w["m_pCachedArc"]["value"]["m_endParams"] == [0.0, math.pi]
            assert E[o["m_styleSymbolId"]][1]["m_dimensionStyleType"] == 9
        assert CL.check_file(path) == []
        for unit in CL.nested_units(path).values():
            assert CL.check_file(path, unit) == []
        assert not [n for n in prod.doc.notes if "not wired" in n or "half arc" in n]
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- the rest

def _guarded(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a two-half circle constructor reached the full-arc form")
    monkeypatch.setattr(G, "full_arc_cylinder_form", boom)


def test_the_rotated_cylinder_keeps_two_half_arcs_and_its_bytes(monkeypatch):
    run = {"name": "run", "shape": "cylinder_x", "radius_ft": 0.1, "length_ft": 2.0,
           "center": [0.0, 0.0], "base_z_ft": -0.1}
    free = _sha(F.make_generic_model(parts=[dict(run)], name="RR"))
    _guarded(monkeypatch)
    prod = F.make_generic_model(parts=[dict(run)], name="RR")
    assert _sha(prod) == free
    arcs = [_crv(e.obj)["value"]["m_endParams"] for e in prod.doc.by_class("CurveElem")]
    assert sorted(map(tuple, arcs)) == [(-math.pi, 0.0), (0.0, math.pi)]


@pytest.mark.parametrize("product", ["lighting_control_panel", "wireway", "junction box"])
def test_circle_free_products_never_reach_the_full_arc(product, monkeypatch):
    free = _sha(F.make_archetype(product=product))
    _guarded(monkeypatch)
    assert _sha(F.make_archetype(product=product)) == free


@pytest.mark.skipif(not (os.path.exists(IFC) and HAVE_SCHEMA),
                    reason="downlight IFC input / class schema absent")
def test_the_downlight_circles_are_full_arcs_and_its_diameters_on_them():
    prod = _downlight()
    circles = _plan_circle_bundles(prod)
    assert len(circles) >= 2                      # can + trim (+ lens)
    doc = prod.doc
    full = {e.elem_id for e in doc.by_class("CurveElem")
            if _crv(e.obj)["ptr_class"] == "GArc" and _full(_crv(e.obj)["value"]["m_endParams"])}
    assert len(full) == len(circles)
    dims = [w["m_pWitnessRef"]["value"]["m_geomRef"]
            for d in doc.by_class("RadialDim") for w in d.obj["m_witnessRefs"]]
    assert dims and all(g["m_elemId"] in full and g["m_geomTag"] == 0 for g in dims)
    assert CL.check_doc(doc) == []
    # the family's own note says where the diameter sits -- never "a half arc"
    notes = [n for n in doc.notes if n.startswith("diameters labelled")]
    assert notes and all("half arc" not in n and "one full arc" in n for n in notes), notes
    _sha(prod)                                     # writes, validates 0 errors

"""#952 -- the generic sketch writer emits a horizontal/vertical constraint only on
genuinely axis-parallel lines, and constraint_law CG11 flags one that is not.

Census (421-family private reference corpus, a development instrument, counts only;
record ``docs/inbox/param-drive.d/952-sketch-hv.md``), host + nested units: 62,033
``VarSketchHorVerConstrObj`` -- every one on an axis-parallel line, ``m_hor`` = the
line is horizontal (32,046 H / 29,987 V); 0 on the 14,219 slanted lines.  Of the
62,783 axis-parallel lines 750 carry none, all in ``m_highResidualTol`` sketches; in
sketches without it (the shape ``geometry.new_var_sketch`` writes) 21,753 / 21,753
carry one.  ``m_angleCoef`` is 1.0 on 26,561 / 26,561 lines of those sketches, so the
writer keeps 1.0 (the line length appears only in ``m_highResidualTol`` sketches).

The writer used to put an HV on every line, slanted ones included (the polygon prism,
the solid trapeze's hex nuts).  Rectangle-only products are byte-identical to the old
rule (asserted below by re-running the old rule); polygon products drop the slanted
lines' HVs and nothing else.  Nothing here claims Revit accepts either (hard rule 4).
"""
from __future__ import annotations

import copy
import glob
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
CORPUS = os.path.join(os.environ.get("TEKTON_ROOT") or ROOT, "samples", "evolve", "lib")
HV = "VarSketchHorVerConstrObj"

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
    d = tempfile.mkdtemp(prefix="t952w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


S3 = math.sqrt(3.0) / 2.0
HEXAGON = [[1, 0], [0.5, S3], [-0.5, S3], [-1, 0], [-0.5, -S3], [0.5, -S3]]


def _downlight():
    from rvt.ifc import famfrom_ifc as FI
    return FI.make_downlight()


BUILDS = {
    "prism_rect": lambda: F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0,
                                               name="PR"),
    "prism_polygon": lambda: F.make_generic_model(vertices=[[0, 0], [2, 0], [1, 1.5]],
                                                  height_ft=1.0, name="PRP"),
    "prism_hexagon": lambda: F.make_generic_model(vertices=HEXAGON, height_ft=0.5, name="PRH"),
    "panelboard": lambda: F.make_panelboard(),
    "cable_tray": lambda: F.make_archetype(product="cable_tray"),
    "lcp": lambda: F.make_archetype(product="lighting_control_panel"),
    "downlight": _downlight,
    "trapeze_solid": lambda: F.make_archetype(product="strut_trapeze"),
    "trapeze_nested": lambda: F.make_archetype(product="strut_trapeze", nested_hardware=True),
}
POLYGON = ("prism_polygon", "prism_hexagon", "trapeze_solid")


def _old_rule(x1, y1, x2, y2):
    """The writer's rule before #952: every line got an HV, by its dominant axis."""
    return "H" if abs(y2 - y1) <= abs(x2 - x1) else "V"


def _write(prod, path):
    if hasattr(prod, "write"):
        return prod.write(path)
    from rvt.frontdoor.standalone import standalone_family_write
    return standalone_family_write(prod, path, provenance=False)


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t952sha_")
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


def _lines_and_hvs(sk_obj):
    """[(axis, [m_hor of each HV naming it], m_angleCoef)] per solver line."""
    by_pid = {}
    for r in sk_obj.get("m_elemRecs") or []:
        if r.get("ptr_class") == "VarSketchLineSegObj":
            p = [float(q["value"]["m_val"]) for q in r["value"]["m_params"]]
            by_pid[r["pid"]] = [CL.line_axis(*p), [], r["value"]["m_angleCoef"]]
    for c in sk_obj.get("m_constrRecs") or []:
        if c.get("ptr_class") == HV:
            for w in c["value"]["m_constrElems"]:
                by_pid[w["weakref"]][1].append(c["value"]["m_hor"])
    return list(by_pid.values())


def _skip_downlight(key):
    if key == "downlight" and not (os.path.exists(IFC) and HAVE_SCHEMA):
        pytest.skip("downlight IFC input / class schema absent")


# --------------------------------------------------------------------------- the predicate

def test_line_axis_is_exact_up_to_the_tolerance():
    assert CL.line_axis(0, 0, 2, 0) == "H"
    assert CL.line_axis(2, 0, 0, 0) == "H"
    assert CL.line_axis(0, 0, 0, -3) == "V"
    assert CL.line_axis(0, 0, 1, 1) is None
    assert CL.line_axis(0, 0, 1, 1.5) is None
    assert CL.line_axis(1, 1, 1, 1) is None                         # zero length
    # float noise of a computed vertex is axis-parallel; a born slanted line's
    # smallest deviation (6.3e-8 degrees ~ 1.1e-9 rad) is not, on a 1 ft line
    assert CL.line_axis(0.5, S3, -0.5, S3 + 1e-16) == "H"
    assert CL.line_axis(0, 0, 1, math.tan(math.radians(6.3e-8))) is None
    assert CL.HV_AXIS_TOL == 1e-9


# --------------------------------------------------------------------------- the writer

def test_the_writer_puts_hv_only_on_axis_parallel_lines():
    for key in ("prism_rect", "prism_polygon", "prism_hexagon", "trapeze_solid"):
        prod = BUILDS[key]()
        n_lines = n_hv = n_slanted = 0
        for sk in prod.doc.by_class("VarSketch"):
            assert sk.obj["m_highResidualTol"] is False
            for axis, hors, coef in _lines_and_hvs(sk.obj):
                n_lines += 1
                n_hv += len(hors)
                if axis is None:
                    n_slanted += 1
                    assert hors == [], key
                else:
                    assert hors == [axis == "H"], key
                assert coef == 1.0, key                # census: 1.0 without highResidualTol
        assert n_lines and (n_slanted > 0) == (key != "prism_rect"), key
        assert n_hv == n_lines - n_slanted, key
        assert CL.check_doc(prod.doc) == [], key


def test_the_hexagon_keeps_its_two_flats_horizontal():
    sk, = BUILDS["prism_hexagon"]().doc.by_class("VarSketch")
    rows = _lines_and_hvs(sk.obj)
    assert sorted(len(h) for _a, h, _c in rows) == [0, 0, 0, 0, 1, 1]
    assert [h for a, h, _c in rows if h] == [[True], [True]]
    kinds = [c["ptr_class"] for c in sk.obj["m_constrRecs"]]
    assert kinds.count("VarSketchPPConstrObj") == 6 and kinds.count(HV) == 2


@pytest.mark.parametrize("key", sorted(BUILDS))
def test_rectangle_products_are_byte_identical_to_the_old_rule(key, monkeypatch):
    """The fix changes polygon sketches only: every line of a rectangle-only
    product is axis-parallel, so the old rule and the new one emit the same HVs
    (and the nested trapeze's hexagon is re-shaped by angular_law either way)."""
    _skip_downlight(key)
    new = _sha(BUILDS[key]())
    monkeypatch.setattr(CL, "line_axis", _old_rule)
    old = _sha(BUILDS[key]())
    assert (new != old) == (key in POLYGON), key


@pytest.mark.parametrize("release", [2026, 2025])
@pytest.mark.parametrize("key", POLYGON)
def test_written_polygon_products_read_back_lawful(key, release):
    d = tempfile.mkdtemp(prefix=f"t952r_{release}_")
    try:
        path = os.path.join(d, "f.rfa")

        def build():
            prod = BUILDS[key]()
            res = _write(prod, path)
            assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
            return prod
        _in_release(release, build)
        assert CL.check_file(path) == []
        for _g, unit in CL.nested_units(path).items():
            assert CL.check_file(path, unit) == []
        with ExitStack() as st:
            from rvt.global_framing import enter_own_release
            from rvt.objects import ObjectDecoder
            enter_own_release(st, path)
            fi = FamilyIndex(path)
            dec = ObjectDecoder(fi.schema)
            recs = fi.unit_records(0)
            slanted = 0
            for eid in fi.ids_of_class(0, "VarSketch"):
                r = recs[102][eid]
                for axis, hors, _c in _lines_and_hvs(dec.decode_record(r.class_id,
                                                                       r.payload).value):
                    slanted += axis is None
                    assert hors == ([] if axis is None else [axis == "H"])
            assert slanted > 0
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- CG11

def _sketch_tuple(key="prism_polygon"):
    sk, = BUILDS[key]().doc.by_class("VarSketch")
    return sk.elem_id, copy.deepcopy(sk.obj)


def test_cg11_fires_on_an_hv_on_a_slanted_line():
    eid, obj = _sketch_tuple()
    assert CL.check_graph([(eid, "VarSketch", obj)]) == []
    slanted = next(r["pid"] for r in obj["m_elemRecs"]
                   if CL.line_axis(*[q["value"]["m_val"] for q in r["value"]["m_params"]]) is None)
    obj["m_constrRecs"].append({"ptr_class": HV, "pid": 999, "value": {
        "m_params": [], "m_pSketch": {"weakref": 2}, "m_objId": -1,
        "m_constrElems": [{"weakref": slanted}], "m_constrSubTypes": [0],
        "m_priorityLevel": 3, "m_hor": True}})
    f = CL.check_graph([(eid, "VarSketch", obj)])
    assert [x["rule"] for x in f] == ["CG11"] and f[0]["severity"] == CL.ERROR
    assert "slanted" in f[0]["message"]


def test_cg11_fires_on_an_hv_on_the_wrong_axis():
    eid, obj = _sketch_tuple("prism_rect")
    hv = next(c for c in obj["m_constrRecs"] if c["ptr_class"] == HV)
    hv["value"]["m_hor"] = not hv["value"]["m_hor"]
    f = CL.check_graph([(eid, "VarSketch", obj)])
    assert [x["rule"] for x in f] == ["CG11"]


def test_cg11_judges_what_the_old_writer_wrote(monkeypatch):
    """The pre-#952 writer's polygon sketches are exactly what CG11 exists for."""
    monkeypatch.setattr(CL, "line_axis", _old_rule)
    prod = BUILDS["prism_polygon"]()
    monkeypatch.undo()
    f = CL.check_doc(prod.doc)
    assert [x["rule"] for x in f] == ["CG11", "CG11"]


def test_cg11_skips_what_it_cannot_resolve():
    eid, obj = _sketch_tuple()
    obj["m_constrRecs"].append({"ptr_class": HV, "pid": 999, "value": {
        "m_constrElems": [{"weakref": 12345}], "m_hor": True}})       # names no line
    obj["m_elemRecs"].append(None)                                     # a deleted record
    assert CL.check_graph([(eid, "VarSketch", obj)]) == []


# --------------------------------------------------------------------------- the born corpus

def _corpus():
    files = sorted(glob.glob(os.path.join(CORPUS, "**", "*.rfa"), recursive=True))
    if not files:
        pytest.skip("born reference library (samples/, git-ignored) not present")
    return files


def test_cg11_is_silent_on_a_born_sample():
    """Every 20th born family, host and nested units (fast; the full sweep is slow)."""
    files = _corpus()[::20]
    bad = 0
    for p in files:
        units = [0] + sorted(CL.nested_units(p).values())
        for u in units:
            bad += sum(1 for f in CL.check_file(p, u) if f["rule"] == "CG11")
    assert bad == 0


@pytest.mark.slow
def test_cg11_is_silent_on_every_born_document():
    if os.environ.get("RVT_SKIP_LARGE"):
        pytest.skip("RVT_SKIP_LARGE set")
    bad = 0
    for p in _corpus():
        for u in [0] + sorted(CL.nested_units(p).values()):
            bad += sum(1 for f in CL.check_file(p, u) if f["rule"] == "CG11")
    assert bad == 0

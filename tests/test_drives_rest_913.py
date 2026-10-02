"""The rest of the #913 survey: the conduit, the single-prism generic model and the
IFC-measured downlight built with their parts constrained to parameter drives.

Steer #913 ("every generated family's parts constrained to parameter drives"): the
survey in ``docs/inbox/param-drive.d/913-equipment-drives.md`` left four rows unwired.
This module pins three of them (record: ``docs/inbox/param-drive.d/913-drives-rest.md``):

* **conduit** (``make_archetype(product="conduit")``): the run is authored the BORN way
  (``rvt.famgen.run_law``) -- its circle sketched on the origin centre plane square to
  the run and extruded along that plane's normal, sketch / frame / B-rep agreeing --
  so **Length** drives its end faces (face locks to surface-only vertical planes held
  by a labelled plan dimension + EQ about the origin plane) and **Outside Diameter**
  labels its circle (``diameter_law``, in the vertical sketch);
* **single-prism generic model** (``make_generic_model(width_ft=..., ...)``, the
  spec-sheet lane): ``prism_drive="law"`` -- Width / Depth symmetric on the body's
  edges, Height on its cap faces; a polygon gets Height only.  ``"372"`` keeps the old
  first-solid chain byte-identical, ``None`` wires nothing;
* **IFC downlight** (``famfrom_ifc.make_downlight``): Frame Length / Frame Width / Bar
  Hanger Span in plan, Housing / Trim / Lens Diameter on the circles, Housing Height on
  the can with the driver riding its top.  ``drive=None`` is the family as before.

Every one is read back from the WRITTEN file on 2026 and 2025: each sketch lock lies on
its plane, each cap-face lock's face lies on its plane, ``constraint_law.check_file``
is empty, and the family validates 0 errors.  A refused spec leaves the file
byte-identical to the build without it.

Nothing here claims a family flexes in Revit (hard rule 4): a face lock to a vertical
plane, a diameter on a vertical circle and a vertical-plane sketch have NO desktop
verdict -- authored, assembled family unverified.
"""
from __future__ import annotations

import copy
import hashlib
import os
import shutil
import tempfile
from contextlib import ExitStack

import pytest

from rvt.families import FamilyIndex
from rvt.famgen import constraint_law as CL
from rvt.famgen import diameter_law as DM
from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F
from rvt.famgen import run_law as RL
from conftest import HAVE_SCHEMA, context_constants, ladder_constants

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IFC = os.path.join(ROOT, "inputs", "ifc", "chicago-plenum-downlight.ifc")
needs_ifc = pytest.mark.skipif(not (os.path.exists(IFC) and HAVE_SCHEMA),
                               reason="downlight IFC input / class schema absent")

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
    d = tempfile.mkdtemp(prefix="t913rw_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


TOL = 1e-6
RUN = {"name": "run", "shape": "cylinder_x", "radius_ft": 0.1, "length_ft": 2.0,
       "center": [0.0, 0.0], "base_z_ft": -0.1, "work_plane": "vertical"}


def _write(prod, path):
    if hasattr(prod, "write"):
        return prod.write(path)
    from rvt.frontdoor.standalone import standalone_family_write
    return standalone_family_write(prod, path, provenance=False)


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t913rsha_")
    try:
        path = os.path.join(d, "f.rfa")
        res = _write(prod, path)
        assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    finally:
        shutil.rmtree(d, True)


def _refusals(notes):
    return [n for n in notes if "not wired" in n or "NOT wired" in n or "not made" in n]


def _downlight(**kw):
    from rvt.ifc import famfrom_ifc as FI
    return FI.make_downlight(**kw)


# --------------------------------------------------------------------------- the conduit

def test_the_conduit_is_a_run_on_the_vertical_centre_plane():
    prod = F.make_archetype(product="conduit")
    doc = prod.doc
    run = next(fb for fb in prod.forms if RL.is_run(fb))
    sp = next(e for e in run.elements if e.class_name == "SketchPlane")
    sk = next(e for e in run.elements if e.class_name == "VarSketch")
    ex = next(e for e in run.elements if e.class_name == "ExtrusionElem")
    wp = DL.origin_centre_plane(doc, "x")
    # the SketchPlane is hosted on the origin centre plane square to the run
    assert sp.obj["m_oPlaneRef"]["value"]["m_datumPlaneId"] == wp.elem_id
    x, y, n = DM.sketch_frame(sk)
    assert [round(c, 12) for c in n] == [1.0, 0.0, 0.0]
    assert sp.obj["m_oTrf"]["value"]["m_3x3"] == [[x[i], y[i], n[i]] for i in range(3)]
    assert sk.obj["m_serFlags"] == RL.VERTICAL_SKETCH_SER_FLAGS
    assert wp.elem_id in sk.header["m_parents"]["value"]["m_regenOnly"]
    # every arc lies in that plane, its centre marker along the normal
    for ce in (e for e in run.elements if e.class_name == "CurveElem"):
        a = ce.obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
        assert all(abs(sum(a[f][i] * n[i] for i in range(3))) < TOL for f in ("m_xVec", "m_yVec"))
        assert ce.obj["m_oArcCntr"]["value"]["m_dirVec"] == [1.0, 0.0, 0.0]
    # the extrusion runs along the normal, centred on the plane
    L = prod.archetype["dimensions"][1]["value"]
    pv = {int(p["m_paramId"]): float(p["m_value"])
          for p in ex.obj["m_pParamValueSetDouble"]["value"]["m_paramSet"]}
    assert (pv[-1001800], pv[-1001801]) == pytest.approx((-L / 2.0, L / 2.0))
    # and the cached B-rep says so too: every cylinder surface axis is +-X
    zs = []

    def walk(v):
        if isinstance(v, dict):
            for k, w in v.items():
                if k == "m_zVec" and isinstance(w, list):
                    zs.append([round(c, 9) for c in w])
                walk(w)
        elif isinstance(v, list):
            for w in v:
                walk(w)
    walk(ex.rep)
    assert zs and all(abs(abs(z[0]) - 1.0) < TOL and abs(z[1]) < TOL and abs(z[2]) < TOL
                      for z in zs)


def test_the_conduit_length_and_diameter_are_wired():
    prod = F.make_archetype(product="conduit")
    doc = prod.doc
    assert prod.runs["wired"] == 1 and prod.runs["refused"] == [] and prod.runs["locks"] == 2
    assert prod.diameters["wired"] == 1 and prod.diameters["dims"] == 1
    assert prod.diameters["refused"] == []
    rows = doc.types[doc.current_type][1]
    d_in = prod.archetype["dimensions"][0]["value"]
    assert rows[doc.params["Outside Diameter"].elem_id] == pytest.approx(d_in / 12.0)
    assert rows[doc.params["Length"].elem_id] == pytest.approx(10.0)
    assert doc.born_drive_law is True
    assert CL.check_doc(doc) == []
    assert _refusals(doc.notes) == [], doc.notes
    assert any("CONSTRAINTS AUTHORED" in n for n in prod.notes)


def test_the_run_end_faces_follow_the_born_lock_law():
    prod = F.make_archetype(product="conduit")
    doc = prod.doc
    ex = next(e for fb in prod.forms if RL.is_run(fb) for e in fb.elements
              if e.class_name == "ExtrusionElem")
    planes = {p.elem_id: p for p in doc.refplanes}
    locks = {}
    for al in doc.by_class("Alignment"):
        g = [w["m_pWitnessRef"]["value"]["m_geomRef"] for w in al.obj["m_witnessRefs"]]
        tags = {x["m_elemId"]: x["m_geomTag"] for x in g}
        if ex.elem_id in tags:
            locks[tags[ex.elem_id]] = (al, g)
    assert set(locks) == {0, 1}
    end, start = locks[0], locks[1]
    # END (tag 0): plane first, constrained -X; START (tag 1): face first, +X
    assert end[1][0]["m_elemId"] in planes and end[0].obj["m_constrDir"] == [-1.0, 0.0, 0.0]
    assert start[1][0]["m_elemId"] == ex.elem_id and start[0].obj["m_constrDir"] == [1.0, 0.0, 0.0]
    for al, g in (end, start):
        assert al.obj["m_flags"] == 14 and al.obj["m_planeNormal"] == [0.0, 0.0, 1.0]
        assert int(al.obj["m_ownerDBViewId"]) == -1
        rp = planes[next(x["m_elemId"] for x in g if x["m_elemId"] in planes)]
        assert DL.is_surface_only(rp)
    # the two planes are held by a labelled PLAN dimension on Length + the EQ
    ends = sorted(next(x["m_elemId"] for x in g if x["m_elemId"] in planes)
                  for _al, g in (end, start))
    dims = [d for d in doc.by_class("LinearDimString")
            if set(ends) <= {w["m_pWitnessRef"]["value"]["m_geomRef"]["m_elemId"]
                             for w in d.obj["m_witnessRefs"]}]
    labelled = [d for d in dims if d.obj["m_ArrSegInfo"][0]["m_paramId"]
                == doc.params["Length"].elem_id]
    eq = [d for d in dims if d.obj["m_flags"] == 140]
    assert len(labelled) == 1 and len(eq) == 1
    assert labelled[0].obj["m_ownerDBViewId"] == doc.plan_view_id
    # the manager rows: run-axis dimDir, +X coefficients
    m = doc.self_family.obj["m_oFamDimConstrMgr"]["value"]
    sd = [r for r in m["m_dimSegDataMap"] if r["first"]["m_elementId"] == ex.elem_id]
    assert len(sd) == 2 and all(r["second"]["m_dimDir"] == [1.0, 0.0, 0.0]
                                and r["second"]["m_coefArr"] == [-1.0, 1.0] for r in sd)
    assert ex.elem_id in {r["first"]["m_elementId"] for r in m["m_paramExprs"]}


def test_the_run_diameter_is_a_type_9_label_in_the_vertical_sketch():
    prod = F.make_archetype(product="conduit")
    doc = prod.doc
    (rd,) = doc.by_class("RadialDim")
    style = next(e for e in doc.by_class("DimensionStyle")
                 if e.elem_id == rd.obj["m_styleSymbolId"])
    assert style.obj["m_dimensionStyleType"] == DM.DIAMETER_STYLE_TYPE
    assert rd.obj["m_planeNormal"] == [1.0, 0.0, 0.0]
    arc = rd.obj["m_witnessRefs"][0]["m_pCachedArc"]["value"]
    assert (arc["m_xVec"], arc["m_yVec"]) == ([0.0, 1.0, 0.0], [0.0, 0.0, 1.0])
    seg = rd.obj["m_ArrSegInfo"][0]
    assert seg["m_paramId"] == doc.params["Outside Diameter"].elem_id
    assert seg["m_lockedValue"] == pytest.approx(2.0 * arc["m_radius"])
    # the 45-degree reference point lies in the YZ plane on the circle
    pt = rd.obj["m_refPnts"][0]
    assert abs(pt[0]) < TOL and abs((pt[1] ** 2 + pt[2] ** 2) ** 0.5 - arc["m_radius"]) < TOL


def test_a_run_sketch_is_not_a_plan_circle_without_the_flag():
    """``circle_of`` keeps its plan-plane refusal: only a caller that names the
    sketch as a run's vertical sketch gets the vertical lane."""
    doc = F.SK.new_family_document("generic_model", "x", work_plane_based=False, start_id=1000)
    fb = F.add_generic_part(doc, dict(RUN))
    sk = next(e for e in fb.elements if e.class_name == "VarSketch")
    with pytest.raises(DM.DiameterError, match="plan plane"):
        DM.circle_of(doc, sk)
    _arc, centre, r = DM.circle_of(doc, sk, vertical=True)
    assert r == pytest.approx(0.1) and centre == pytest.approx([0.0, 0.0, 0.0])


def test_the_rotated_brep_cylinder_is_unchanged_and_still_refused():
    """A ``cylinder_x`` WITHOUT the work plane is the rotated-B-rep form of #591
    round 4 (the IFC assembly route's shape): no run, and a diameter or a run
    length naming it is refused."""
    part = {k: v for k, v in RUN.items() if k != "work_plane"}
    base = F.make_generic_model(parts=[part], name="R", numeric_params={
        "Length": ("length", 2.0), "D": ("length", 0.2)})
    prod = F.make_generic_model(parts=[part], name="R", numeric_params={
        "Length": ("length", 2.0), "D": ("length", 0.2)},
        runs=[{"caption": "Length", "parts": ["run"]}],
        diameters=[{"caption": "D", "parts": ["run"]}])
    assert not any(RL.is_run(fb) for fb in prod.forms)
    assert prod.runs["wired"] == 0 and prod.diameters["wired"] == 0
    assert _sha(prod) == _sha(base)


# --------------------------------------------------------------------------- run refusals

def _run_model(**kw):
    return F.make_generic_model(parts=[dict(RUN)], name="Run", numeric_params={
        "Length": ("length", 2.0), "Run Diameter": ("length", 0.2),
        "Count": ("number", 2.0)}, **kw)


@pytest.mark.parametrize("bad", [
    {"caption": "Length", "parts": ["nope"]},                 # no such part
    {"caption": "Count", "parts": ["run"]},                   # not a length spec
    {"caption": "Run Diameter", "parts": ["run"]},            # value != run length
    {"caption": "Missing", "parts": ["run"]},                 # no such parameter
    {"caption": "Length", "parts": []},                       # nothing to drive
    {"caption": "Length", "parts": ["run", "run"]},           # listed twice
])
def test_a_refused_run_spec_leaves_the_file_byte_identical(bad):
    good = _run_model(runs=[{"caption": "Length", "parts": ["run"]}])
    control = _run_model()
    prod = _run_model(runs=[bad])
    assert prod.runs["wired"] == 0 and len(prod.runs["refused"]) == 1
    assert any("run length for" in n and "not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(control)
    assert _sha(good) != _sha(control)


def test_an_off_centre_run_refuses_the_symmetric_drive_but_takes_the_plain_one():
    part = dict(RUN, center=[0.5, 0.0])
    mk = lambda **kw: F.make_generic_model(parts=[part], name="Off",          # noqa: E731
                                           numeric_params={"Length": ("length", 2.0)}, **kw)
    sym = mk(runs=[{"caption": "Length", "parts": ["run"], "symmetric": True}])
    assert sym.runs["wired"] == 0 and "not centred" in sym.runs["refused"][0]["why"]
    assert _sha(sym) == _sha(mk())
    plain = mk(runs=[{"caption": "Length", "parts": ["run"], "symmetric": False}])
    assert plain.runs["wired"] == 1 and CL.check_doc(plain.doc) == []


def test_a_refused_run_diameter_leaves_the_file_byte_identical():
    control = _run_model()
    prod = _run_model(diameters=[{"caption": "Length", "parts": ["run"]}])   # 2 ft != 0.2
    assert prod.diameters["wired"] == 0 and _sha(prod) == _sha(control)
    good = _run_model(diameters=[{"caption": "Run Diameter", "parts": ["run"]}])
    assert good.diameters["wired"] == 1 and _sha(good) != _sha(control)


def test_the_direct_run_api_refuses_before_any_mutation():
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("generic_model", "Direct", work_plane_based=False,
                                 start_id=1000)
    run = F.add_generic_part(doc, dict(RUN))
    box = F.add_generic_part(doc, {"name": "b", "shape": "box", "width_ft": 1.0,
                                   "depth_ft": 1.0, "height_ft": 1.0})
    for cap in ("Length", "Short"):
        doc.add_family_parameter(cap, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS)
    doc.add_type("Direct", {doc.params["Length"].elem_id: 2.0,
                            doc.params["Short"].elem_id: 1.0})
    n = len(doc.elements)
    for kw, why in ((dict(caption="Short", targets=[run]), "1.0 ft but"),
                    (dict(caption="Length", targets=[box]), "not a run"),
                    (dict(caption="Length", targets=[]), "no run"),
                    (dict(caption="Length", targets=[run, run]), "listed twice"),
                    (dict(caption="Nope", targets=[run]), "no family parameter")):
        with pytest.raises(RL.RunError, match=why):
            RL.wire_run_length(doc, **kw)
        assert len(doc.elements) == n
    r = RL.wire_run_length(doc, caption="Length", targets=[run])
    assert len(r["locks"]) == 2 and r["symmetric"] and len(doc.elements) > n
    n = len(doc.elements)
    with pytest.raises(RL.RunError, match="already locked"):
        RL.wire_run_length(doc, caption="Length", targets=[run])
    assert len(doc.elements) == n
    doc.finalized = True
    with pytest.raises(RL.RunError, match="finalized"):
        RL.wire_run_length(doc, caption="Length", targets=[run])


def test_a_y_run_carries_the_minus_y_law():
    """A run along Y sits on Center (Front/Back), whose normal is -Y: its END face
    is the LOW-y one, the manager coefficients flip sign (the census mode)."""
    part = dict(RUN, shape="cylinder_y")
    prod = F.make_generic_model(parts=[part], name="RY", numeric_params={
        "Length": ("length", 2.0), "Run Diameter": ("length", 0.2)},
        runs=[{"caption": "Length", "parts": ["run"]}],
        diameters=[{"caption": "Run Diameter", "parts": ["run"]}])
    assert prod.runs["wired"] == 1 and prod.diameters["wired"] == 1
    doc = prod.doc
    ex = next(e for e in doc.by_class("ExtrusionElem"))
    m = doc.self_family.obj["m_oFamDimConstrMgr"]["value"]
    sd = [r for r in m["m_dimSegDataMap"] if r["first"]["m_elementId"] == ex.elem_id]
    assert all(r["second"]["m_coefArr"] == [1.0, -1.0] for r in sd)
    (rd,) = doc.by_class("RadialDim")
    assert [round(c, 12) for c in rd.obj["m_planeNormal"]] == [0.0, -1.0, 0.0]
    assert CL.check_doc(doc) == []


# --------------------------------------------------------------------------- the single prism

def test_the_single_prism_drives_width_depth_and_height():
    prod = F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0, name="P913")
    assert [(d["caption"], len(d["locks"]), d["symmetric"]) for d in prod.drives] == [
        ("Width", 2, True), ("Depth", 2, True)]
    h = prod.heights
    assert (h["wired"], h["refused"], h["face_locks"], h["locked_unlabelled"]) == (1, [], 2, 0)
    assert prod.doc.born_drive_law is True and CL.check_doc(prod.doc) == []
    assert _refusals(prod.doc.notes) == []
    assert any("constraints authored (#913)" in n for n in prod.notes)


@pytest.mark.parametrize("base, held", [(0.5, 1), (-1.0, 1), (-3.0, 0), (0.0, 0)])
def test_a_raised_or_sunk_prism_holds_its_base_to_the_origin(base, held):
    prod = F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0, base_z_ft=base,
                                name="P913B")
    h = prod.heights
    assert h["refused"] == [] and h["face_locks"] == 2 and h["locked_unlabelled"] == held
    assert h["captions"] == ["Height"]


def test_a_polygon_prism_drives_its_height_only():
    prod = F.make_generic_model(vertices=[[0, 0], [2, 0], [1, 1.5]], height_ft=1.0,
                                name="P913P")
    assert prod.drives == [] and prod.heights["wired"] == 1
    assert any("NOT driven on an arbitrary profile" in n for n in prod.doc.notes)
    assert len(DL._sketch_locks(prod.doc)) == 0


def test_the_old_prism_chains_stay_behind_the_flag():
    old = F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0, name="P913O",
                               prism_drive="372")
    assert old.drives == [] and old.heights == {}
    assert not getattr(old.doc, "born_drive_law", False)
    assert (len(old.doc.by_class("Alignment")), len(old.doc.by_class("LinearDimString"))) == (4, 2)
    for kw in ({"width_ft": 2.0, "depth_ft": 1.0}, {"vertices": [[0, 0], [2, 0], [1, 1.5]]}):
        none = F.make_generic_model(height_ft=1.0, name="P913N", prism_drive=None, **kw)
        assert (len(none.doc.by_class("Alignment")),
                len(none.doc.by_class("LinearDimString"))) == (0, 0)
    with pytest.raises(F.FactoryError):
        F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=1.0, prism_drive="flex")


def test_a_refused_prism_spec_equals_the_build_without_it(monkeypatch):
    real = F._wire_equipment_drives

    def edited(edit):
        def wrap(doc, named, d, h, *, what):
            d, h = copy.deepcopy(d), copy.deepcopy(h)
            edit(d, h)
            return real(doc, named, d, h, what=what)
        return wrap

    def build():
        return F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0, name="P913R")

    def bad_width(d, h):
        d[0]["lo"] = -5.0                                # planes off the body's edges
    monkeypatch.setattr(F, "_wire_equipment_drives", edited(bad_width))
    refused = build()
    assert any("drive for 'Width' not wired" in n for n in refused.doc.notes)

    def no_width(d, h):
        del d[0]
    monkeypatch.setattr(F, "_wire_equipment_drives", edited(no_width))
    assert _sha(refused) == _sha(build())

    def bad_height(d, h):
        h[0]["hi"] = 9.0                                 # off the top face
    monkeypatch.setattr(F, "_wire_equipment_drives", edited(bad_height))
    refused = build()

    def no_height(d, h):
        h.clear()
    monkeypatch.setattr(F, "_wire_equipment_drives", edited(no_height))
    assert _sha(refused) == _sha(build())


# --------------------------------------------------------------------------- the IFC downlight

@needs_ifc
def test_the_downlight_drives_what_is_measured():
    prod = _downlight()
    got = {d["caption"]: (len(d["locks"]), d.get("symmetric")) for d in prod.drives}
    # the plate sits off the can axis in x: Frame Length is the plain two-plane law
    assert got == {"Frame Length": (2, None), "Frame Width": (2, True),
                   "Bar Hanger Span": (4, True)}
    h = prod.heights
    assert (h["wired"], h["refused"], h["face_locks"], h["locked_unlabelled"]) == (3, [], 4, 2)
    assert h["captions"] == ["Housing Height"]
    assert prod.diameters["captions"] == ["Housing Diameter", "Trim Diameter", "Lens Diameter"]
    doc = prod.doc
    assert doc.born_drive_law is True and CL.check_doc(doc) == []
    assert _refusals(doc.notes) == [], doc.notes
    assert any("constraints authored (#913)" in n and "Aperture Diameter" in n
               for n in prod.notes)


@needs_ifc
def test_the_envelope_downlight_drives_its_can_and_trim():
    prod = _downlight(detail="envelope")
    assert prod.drives == [] and prod.heights["captions"] == ["Housing Height"]
    assert prod.diameters["captions"] == ["Housing Diameter", "Trim Diameter"]
    assert _refusals(prod.doc.notes) == []


@needs_ifc
def test_the_downlight_without_drives_is_unconstrained():
    prod = _downlight(drive=None)
    doc = prod.doc
    assert prod.drives == [] and prod.heights == {} and prod.diameters == {}
    assert [len(doc.by_class(c)) for c in ("Alignment", "LinearDimString", "RadialDim")] == [0, 0, 0]
    from rvt.ifc import famfrom_ifc as FI
    with pytest.raises(FI.FamFromIfcError):
        _downlight(drive="372")


@needs_ifc
def test_every_downlight_spec_refused_equals_no_drive(monkeypatch):
    from rvt.ifc import famfrom_ifc as FI

    def bad(doc, forms):
        return ([{"caption": "Frame Length", "axis": "x", "lo": -9.0, "hi": 9.0,
                  "parts": {"frame plate": ("lo", "hi")}}],
                [{"caption": "Housing Height", "lo": 0.0, "hi": 9.0,
                  "parts": {"housing can": {"end": "hi"}}}],
                [{"caption": "Housing Diameter", "parts": ["frame plate"]}])
    monkeypatch.setattr(FI, "downlight_drive_specs", bad)
    prod = _downlight()
    assert any("drives (#913) NOT wired" in n for n in prod.notes)
    assert _sha(prod) == _sha(_downlight(drive=None))


# --------------------------------------------------------------------------- written read-back

def _plane(o):
    """(point, unit normal) of a RefPlane record, from its SURFACE (a surface-only
    plane has no drawn ends)."""
    s = o["m_pSurface"]["value"]
    x, y = s["m_xVec"], s["m_yVec"]
    n = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
    m = sum(c * c for c in n) ** 0.5
    return s["m_origin"], tuple(c / m for c in n)


def _read(path):
    with ExitStack() as st:
        from rvt.global_framing import enter_own_release
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0).get(102, {})
        return {eid: (fi.class_name(r.class_id), fi.decode(0, eid, 102).value)
                for eid, r in recs.items()
                if fi.class_name(r.class_id) in ("RefPlane", "Alignment", "CurveElem",
                                                 "ExtrusionElem", "SketchPlane",
                                                 "VarSketch")}


def _locks_on_planes(E):
    """(sketch locks, sketch locks off their plane, face locks, face locks off their
    plane) of a written file: a sketch lock's GLine ends, and a face lock's cap face
    (the extrusion's start / end offset along its SketchPlane's normal), measured
    against the plane it is locked to."""
    sk_n = sk_off = f_n = f_off = 0
    for _eid, (cls, v) in E.items():
        if cls != "Alignment":
            continue
        g = [w["m_pWitnessRef"]["value"]["m_geomRef"] for w in v["m_witnessRefs"]]
        pl = [x for x in g if E.get(x["m_elemId"], ("",))[0] == "RefPlane"]
        cu = [x for x in g if E.get(x["m_elemId"], ("",))[0] == "CurveElem"]
        ex = [x for x in g if E.get(x["m_elemId"], ("",))[0] == "ExtrusionElem"]
        if len(pl) != 1:
            continue
        p0, nrm = _plane(E[pl[0]["m_elemId"]][1])
        if len(cu) == 1:
            crv = E[cu[0]["m_elemId"]][1]["m_pCurveDriver"]["value"]["m_pCrv"]
            assert crv["ptr_class"] == "GLine", crv["ptr_class"]
            c = crv["value"]
            pts = [[c["m_origin"][i] + c["m_dirVec"][i] * t for i in range(3)]
                   for t in c["m_endParams"]]
            sk_n += 1
            sk_off += any(abs(sum((p[i] - p0[i]) * nrm[i] for i in range(3))) > TOL
                          for p in pts)
        elif len(ex) == 1:
            o = E[ex[0]["m_elemId"]][1]
            pv = {int(p["m_paramId"]): float(p["m_value"])
                  for p in o["m_pParamValueSetDouble"]["value"]["m_paramSet"]}
            off = pv[-1001801 if ex[0]["m_geomTag"] == 0 else -1001800]
            helper = next(c["value"] for c in o["m_cellList"]["value"]["m_cells"]
                          if c["ptr_class"] == "ExtrusionElemExtrusionHelper")
            sk = E[helper["m_sketchId"]][1]
            sp = E[sk["m_sketchPlaneId"]][1]
            trf = sp["m_oTrf"]["value"]
            sn = [trf["m_3x3"][i][2] for i in range(3)]            # column 2 = normal
            face = [trf["m_or"][i] + sn[i] * off for i in range(3)]
            f_n += 1
            f_off += abs(sum((face[i] - p0[i]) * nrm[i] for i in range(3))) > TOL
    return sk_n, sk_off, f_n, f_off


def _in_release(release, build):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return build()
    with RC.release_build_context(RC._bundled_base_of(release)):
        return build()


READ_BACK = {
    "conduit": lambda: F.make_archetype(product="conduit"),
    "conduit_2in": lambda: F.make_archetype(product="conduit", dimensions={"diameter_in": 2.0}),
    "run_y": lambda: F.make_generic_model(
        parts=[dict(RUN, shape="cylinder_y", center=[0.3, 0.0], base_z_ft=0.4)],
        name="RY", numeric_params={"Length": ("length", 2.0), "D": ("length", 0.2)},
        runs=[{"caption": "Length", "parts": ["run"]}],
        diameters=[{"caption": "D", "parts": ["run"]}]),
    "prism": lambda: F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0, name="PR"),
    "prism_raised": lambda: F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0,
                                                 base_z_ft=0.5, name="PRR"),
    "prism_polygon": lambda: F.make_generic_model(vertices=[[0, 0], [2, 0], [1, 1.5]],
                                                  height_ft=1.0, name="PRP"),
    "downlight": lambda: _downlight(),
    "downlight_envelope": lambda: _downlight(detail="envelope"),
}


@pytest.mark.parametrize("release", [2026, 2025])
@pytest.mark.parametrize("key", sorted(READ_BACK))
def test_every_written_lock_lies_on_its_plane(key, release):
    if key.startswith("downlight") and not (os.path.exists(IFC) and HAVE_SCHEMA):
        pytest.skip("downlight IFC input / class schema absent")
    d = tempfile.mkdtemp(prefix=f"t913r_{release}_")
    try:
        def build():
            prod = READ_BACK[key]()
            path = os.path.join(d, "f.rfa")
            res = _write(prod, path)
            assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
            return prod, path
        prod, path = _in_release(release, build)
        sk_n, sk_off, f_n, f_off = _locks_on_planes(_read(path))
        assert sk_n == len(DL._sketch_locks(prod.doc))
        assert (sk_off, f_off) == (0, 0), (sk_n, sk_off, f_n, f_off)
        assert f_n == sum(1 for al in prod.doc.by_class("Alignment")
                          if int(al.obj["m_flags"]) == 14
                          and any(w["m_pWitnessRef"]["value"]["m_geomRef"]["m_elemId"]
                                  in {e.elem_id for e in prod.doc.by_class("ExtrusionElem")}
                                  for w in al.obj["m_witnessRefs"]))
        assert f_n > 0
        assert CL.check_file(path) == []
        assert _refusals(prod.doc.notes) == [], prod.doc.notes
    finally:
        shutil.rmtree(d, True)

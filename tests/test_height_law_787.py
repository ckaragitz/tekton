"""The HEIGHT drive (#787 Case B): an extrusion's cap faces locked to horizontal
reference planes held by elevation dimensions, authored the way Revit-born
families store it (rvt.famgen.height_law).

These tests pin the law's fields, the born SURFACE-ONLY form of the user's
horizontal planes, the all-or-nothing refusals (a refused spec leaves the
written file byte-identical to the build without it), and the trapeze's
chain on 2026 and 2025.  Nothing here claims a height flexes: no Case B
element has a desktop verdict (hard rule 4).
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack

import pytest

from rvt.famgen import factory as F
from conftest import context_constants, ladder_constants

# builds enter the write-side release context (2025 targets) and the read-back
# climbs the read-side ladder: conftest's guard watches both (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the
    native codec singletons (standalone.install_schema, by design); do that
    once before the guard's first snapshot, so only a swap a release context
    leaves behind can turn the guard red."""
    d = tempfile.mkdtemp(prefix="t787w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)
from rvt.famgen import height_law as HL

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PARTS = [{"shape": "box", "name": "base", "width_ft": 2.0, "depth_ft": 1.0, "height_ft": 1.0},
         {"shape": "box", "name": "cap", "width_ft": 1.0, "depth_ft": 1.0, "height_ft": 0.5,
          "base_z_ft": 1.0}]
PARAMS = {"Base Height": ("length", 1.0), "Cap Height": ("length", 0.5),
          "Count": ("integer", 2)}
GOOD = [{"caption": "Base Height", "lo": 0.0, "hi": 1.0, "name_hi": "base top",
         "parts": {"base": ("start", "end"), "cap": {"start": "hi"}}},
        {"caption": "Cap Height", "lo": "base top", "hi": 1.5,
         "parts": {"cap": {"end": "hi"}}}]


def _build(heights=None, parts=PARTS):
    return F.make_generic_model(parts=[dict(p) for p in parts], name="Stack",
                                numeric_params=dict(PARAMS), heights=heights)


def _write(prod, d, name="f.rfa"):
    path = os.path.join(d, name)
    prod.write(path)
    return path


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t787sha_")
    try:
        return hashlib.sha256(open(_write(prod, d), "rb").read()).hexdigest()
    finally:
        shutil.rmtree(d, True)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _surface_only(o, h):
    """The born surface-only horizontal plane (height_law docstring)."""
    gs = o["m_geomSteps"]["value"]
    step = gs["m_nonBRepGList"][0]["value"]
    return (o["m_freeEnd"] == [0.0] * 3 and o["m_bubbleEnd"] == [0.0] * 3
            and o["m_cutVec"] == [0.0] * 3
            and o["m_refPointsForNewViews"] == [[0.0] * 3, [0.0] * 3]
            and o["m_genDbViewId"] == -1 and o["m_cellList"] is None
            and step["m_version"] == HL.SURFACE_GSTEP_VERSION
            and step["m_flags"] == HL.SURFACE_GSTEP_FLAGS
            and gs["m_flags"] == HL.SURFACE_GSTEP_LIST_FLAGS
            and gs["m_latestGStepTypeInPrevRegenCycle"] == [0] * 5
            and h["m_abFlags4Bytes"] == HL.SURFACE_HDR_FLAGS
            and sorted(h["m_parents"]["value"]["m_deletion"]) == sorted({o["m_famId"], o["m_id"]})
            and not o["m_definesOrigin"])


# --------------------------------------------------------------------------- the law
def test_two_stacked_parts_get_the_born_chain():
    prod = _build(GOOD)
    doc, rep = prod.doc, prod.heights
    assert rep["wired"] == 2 and not rep["refused"]
    assert (rep["dims"], rep["planes"], rep["face_locks"]) == (2, 3, 4)
    assert doc.born_drive_law
    assert not any(e.obj.get("m_constrInfo") for e in doc.elements)
    st = doc._height_law
    planes = {p.elem_id: p for p in doc.refplanes}
    origin = st["origin"]
    assert origin.obj["m_definesOrigin"] and origin.obj["m_refName"] == 12
    assert origin.obj["m_cutVec"] == [0.0, 1.0, 0.0]
    users = [planes[i] for i in st["planes"] if i != origin.elem_id]
    assert len(users) == 2 and all(_surface_only(p.obj, p.header) for p in users)
    # the origin plane is held to the Level by a flags-14 Alignment
    level = doc.by_class("Level")[0].elem_id
    held = [a for a in doc.by_class("Alignment") if a.obj["m_flags"] == 14
            and {w["m_pWitnessRef"]["value"]["m_geomRef"]["m_elemId"]
                 for w in a.obj["m_witnessRefs"]} == {origin.elem_id, level}]
    assert len(held) == 1
    units = doc.by_class("UnitsElem")[0].elem_id
    front = next(v for v in doc.by_class("DBViewSection") if v.obj["m_viewName"] == "Front")
    for did in st["dims"]:
        dim = next(e for e in doc.elements if e.elem_id == did)
        assert dim.obj["m_flags"] == 12 and dim.obj["m_dimVersion"] == 6
        assert dim.obj["m_ownerDBViewId"] == front.elem_id
        assert dim.header["m_parents"]["value"]["m_regenOnly"] == [units]
        assert dim.obj["m_ArrSegInfo"][0]["m_paramId"] in {
            doc.params["Base Height"].elem_id, doc.params["Cap Height"].elem_id}
    mgr = doc.self_family.obj["m_oFamDimConstrMgr"]["value"]
    keys = lambda nm: {(r["first"]["m_elementId"], r["first"]["m_int64"])  # noqa: E731
                       for r in mgr[nm]}
    prop = {(r["m_elementId"], r["m_int64"]) for r in mgr["m_propagatedDrivers"]}
    for lid in st["locks"]:
        al = next(e for e in doc.elements if e.elem_id == lid)
        assert al.obj["m_flags"] == 14 and al.obj["m_cellList"] is None
        assert al.obj["m_ownerDBViewId"] == -1 and al.header["m_ownerViewId"] == -1
        assert al.obj["m_ArrSegInfo"][0]["m_flags"] == 1
        assert al.header["m_parents"]["value"]["m_regenOnly"] == [units]
        ext, = [g for g in (w["m_pWitnessRef"]["value"]["m_geomRef"]
                            for w in al.obj["m_witnessRefs"])
                if g["m_elemId"] not in planes]
        k = HL.FACE_KEY["end" if ext["m_geomTag"] == 0 else "start"]
        for nm in ("m_paramExprs", "m_drivenDimSegs", "m_dimSegDataMap"):
            assert (ext["m_elemId"], k) in keys(nm), nm
        assert (lid, 0) in prop
        plane = next(g["m_elemId"] for g in (w["m_pWitnessRef"]["value"]["m_geomRef"]
                                            for w in al.obj["m_witnessRefs"])
                     if g["m_elemId"] in planes)
        exe = next(e for e in doc.elements if e.elem_id == ext["m_elemId"])
        assert plane in exe.header["m_parents"]["value"]["m_regenOnly"]
        assert (plane, 0) in keys("m_fixedRefs")


def test_the_written_file_reads_back_clean_and_valid():
    d = tempfile.mkdtemp(prefix="t787rb_")
    try:
        path = _write(_build(GOOD), d)
        rb = _read_back(path)
        assert rb["unclean"] == 0
        assert len(rb["locks"]) == 4
        for face_z, plane_z in rb["locks"]:
            assert abs(face_z - plane_z) < 1e-9
        assert rb["surface_only"] == 2 and rb["origin_drawn"] == 1
        assert _validate(path)
    finally:
        shutil.rmtree(d, True)


# --------------------------------------------------------------------------- refusals
REFUSED = [
    # Base Height is 1.0 ft but these planes are 0.9 apart
    [{"caption": "Base Height", "lo": 0.0, "hi": 0.9, "parts": {}}],
    # the face is not on its plane
    [{"caption": "Base Height", "lo": 0.0, "hi": 1.0, "parts": {"cap": ("start", "end")}}],
    # lo above hi / a NaN plane
    [{"caption": "Base Height", "lo": 1.0, "hi": 0.0, "parts": {"base": ("start", "end")}}],
    [{"caption": "Base Height", "lo": 0.0, "hi": float("nan"), "parts": {}}],
    # no such part / a plane no earlier spec named / not a length parameter
    [{"caption": "Base Height", "lo": 0.0, "hi": 1.0, "parts": {"lid": ("start", "end")}}],
    [{"caption": "Cap Height", "lo": "base top", "hi": 1.5, "parts": {"cap": {"end": "hi"}}}],
    [{"caption": "Count", "lo": 0.0, "hi": 2.0, "parts": {}}],
    [{"caption": "Nope", "lo": 0.0, "hi": 1.0, "parts": {}}],
    # unlabelled and unlocked holds nothing
    [{"caption": None, "lo": 0.0, "hi": 1.0, "parts": {"base": ("start", "end")}}],
    # neither plane positioned: the chain would float
    [{"caption": "Cap Height", "lo": 1.0, "hi": 1.5, "parts": {"cap": ("start", "end")}}],
    # a bad face map
    [{"caption": "Base Height", "lo": 0.0, "hi": 1.0, "parts": {"base": {"top": "hi"}}}],
]


@pytest.mark.parametrize("specs", REFUSED)
def test_a_refused_height_leaves_the_file_byte_identical(specs):
    control = _build(None)
    prod = _build(specs)
    assert prod.heights["wired"] == 0 and len(prod.heights["refused"]) == len(specs)
    assert any("height drive for" in n and "not wired" in n for n in prod.doc.notes)
    assert not getattr(prod.doc, "born_drive_law", False)
    assert _sha(prod) == _sha(control)


def test_a_face_is_never_locked_twice_and_the_refusal_touches_nothing():
    once = _build(GOOD[:1])
    twice = _build(GOOD[:1] + [{"caption": "Base Height", "lo": 0.0, "hi": 1.0,
                                "parts": {"base": {"end": "hi"}}}])
    assert twice.heights["wired"] == 1 and twice.heights["refused"] == ["Base Height"]
    assert _sha(once) == _sha(twice)


def test_a_third_dimension_between_positioned_planes_is_refused():
    # every plane GOOD placed is positioned; one more dimension between two of
    # them would over-constrain the chain
    doc = _build(GOOD).doc
    st = doc._height_law
    planes = {p.elem_id: p for p in doc.refplanes}
    a, b = [planes[i] for i in st["planes"][:2]]
    doc.finalized = False
    try:
        with pytest.raises(ValueError, match="over-constrains"):
            HL.wire_height_drive(doc, caption="Base Height", lo_z=a, hi_z=b)
    finally:
        doc.finalized = True


def test_the_single_prism_path_says_heights_were_not_wired():
    prod = F.make_generic_model(width_ft=1.0, depth_ft=1.0, height_ft=1.0, name="One",
                                heights=GOOD)
    assert prod.heights == {}
    assert any("NOT wired" in n for n in prod.notes)


def test_the_direct_api_refuses_before_any_mutation():
    from rvt.famgen import skeleton as SK
    seen = {}

    def grab(self, *a, **k):            # capture the unfinalized document
        seen.setdefault("doc", self)
        raise RuntimeError("stop")
    orig = SK.FamilyDoc.finalize
    SK.FamilyDoc.finalize = grab
    try:
        with pytest.raises(RuntimeError, match="stop"):
            _build(None)
    finally:
        SK.FamilyDoc.finalize = orig
    doc = seen["doc"]
    before = (len(doc.elements), len(doc.refplanes),
              json.dumps(doc.self_family.obj["m_oFamDimConstrMgr"], sort_keys=True,
                         default=str))
    ext = next(e for e in doc.by_class("ExtrusionElem"))
    for kw in ({"caption": "Base Height", "lo_z": 0.0, "hi_z": 1.0,
                "targets": [(ext, ("start", "end")), (ext, {"end": "hi"})]},
               {"caption": "Base Height", "lo_z": 0.0, "hi_z": 1.0,
                "targets": [(doc.by_class("VarSketch")[0], ("start",))]}):
        with pytest.raises(ValueError):
            HL.wire_height_drive(doc, **kw)
        after = (len(doc.elements), len(doc.refplanes),
                 json.dumps(doc.self_family.obj["m_oFamDimConstrMgr"], sort_keys=True,
                            default=str))
        assert after == before


# --------------------------------------------------------------------------- the trapeze
def _read_back(path):
    """Face z vs plane z of every flags-14 face lock, manager rows per locked
    face, plane forms -- from the WRITTEN file under its own schema."""
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    out = {"unclean": 0, "locks": [], "surface_only": 0, "origin_drawn": 0,
           "rows_ok": 0, "rows_missing": []}
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0)
        cls = {e: fi.class_name(r.class_id) for e, r in recs.get(102, {}).items()}
        V, H = {}, {}
        for e, c in cls.items():
            d = fi.decode(0, e, 102)
            if not (d and d.clean and not d.errors):
                out["unclean"] += 1
                continue
            V[e] = d.value
            if c in ("RefPlane",):
                H[e] = fi.decode(0, e, 101).value
        fam = next(e for e, c in cls.items()
                   if c == "Family" and V[e].get("m_surrogateId") == -1)
        mgr = V[fam]["m_oFamDimConstrMgr"]["value"]
        keys = lambda nm: {(r["first"]["m_elementId"], r["first"]["m_int64"])  # noqa: E731
                           for r in mgr[nm]}
        prop = {(r["m_elementId"], r["m_int64"]) for r in mgr["m_propagatedDrivers"]}

        def pz(e):
            s = V[e]["m_pSurface"]["value"]
            assert _cross(s["m_xVec"], s["m_yVec"])[2] > 0.999
            return float(s["m_origin"][2])
        for e, c in cls.items():
            if c == "RefPlane" and e in V:
                s = V[e]["m_pSurface"]["value"]
                if abs(abs(_cross(s["m_xVec"], s["m_yVec"])[2]) - 1) < 1e-6:
                    if _surface_only(V[e], H[e]):
                        out["surface_only"] += 1
                    elif V[e]["m_definesOrigin"] and V[e]["m_refName"] == 12:
                        out["origin_drawn"] += 1
            if c != "Alignment" or V.get(e, {}).get("m_flags") != 14:
                continue
            gs = [w["m_pWitnessRef"]["value"]["m_geomRef"] for w in V[e]["m_witnessRefs"]]
            ext = [g for g in gs if cls.get(g["m_elemId"]) == "ExtrusionElem"]
            if not ext:
                continue
            (g,), plane = ext, next(x["m_elemId"] for x in gs if cls.get(x["m_elemId"]) == "RefPlane")
            face = "end" if g["m_geomTag"] == 0 else "start"
            pvd = {x["m_paramId"]: x["m_value"] for x in
                   V[g["m_elemId"]]["m_pParamValueSetDouble"]["value"]["m_paramSet"]}
            out["locks"].append((float(pvd[HL.BIP[face]]), pz(plane)))
            k = (g["m_elemId"], HL.FACE_KEY[face])
            if (all(k in keys(nm) for nm in ("m_paramExprs", "m_drivenDimSegs",
                                            "m_dimSegDataMap"))
                    and (e, 0) in prop and (plane, 0) in keys("m_fixedRefs")):
                out["rows_ok"] += 1
            else:
                out["rows_missing"].append(e)
    return out


def _validate(path) -> bool:
    js = path + ".validation.json"
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "rvt_validate.py"),
                           path, "--json", js], capture_output=True, text=True, timeout=600)
    rep = json.load(open(js))
    return proc.returncode == 0 and rep["ok"] and rep["counts"]["error"] == 0


@pytest.mark.parametrize("release", [2026, 2025])
def test_the_trapeze_heights_on_2026_and_2025(release):
    from rvt.frontdoor import release_ctx as RC
    d = tempfile.mkdtemp(prefix=f"t787trap{release}_")
    try:
        if release == RC.native_release():
            prod = F.make_archetype(product="strut_trapeze")
            path = _write(prod, d)
        else:
            with RC.release_build_context(RC._bundled_base_of(release)):
                prod = F.make_archetype(product="strut_trapeze")
                path = _write(prod, d)
        h = prod.heights
        # the prototype's numbers at 2 tiers: every extrusion locked on both faces
        assert (h["dims"], h["planes"], h["face_locks"]) == (17, 18, 116)
        assert h["extrusions_locked"] == h["both_faces"] == len(prod.forms) == 58
        assert h["labelled"] == 13 and h["locked_unlabelled"] == 4 and not h["refused"]
        assert set(h["captions"]) == {"Tier Spacing", "Strut Height", "Strut Thickness",
                                      "Washer Thickness", "Rod Below Bottom Nut",
                                      "Rod Above Top Tier"}
        rb = _read_back(path)
        assert rb["unclean"] == 0
        assert len(rb["locks"]) == 116
        for face_z, plane_z in rb["locks"]:
            assert abs(face_z - plane_z) < 1e-9, (face_z, plane_z)
        assert rb["rows_ok"] == 116 and not rb["rows_missing"]
        assert rb["surface_only"] == 17 and rb["origin_drawn"] == 1
        assert _validate(path)
        # honest: the archetype says the heights have no desktop verdict
        assert any("#787 Case B" in n and "NO desktop verdict" in n for n in prod.notes)
    finally:
        shutil.rmtree(d, True)


def test_the_trapeze_height_specs_match_its_parameter_values():
    from rvt.famgen import archetypes as AR
    vals = dict(AR.resolve("strut_trapeze", {"tiers": 3}).values)
    specs = AR.archetype("strut_trapeze").heights(vals)
    assert sum(1 for s in specs if s["caption"] == "Tier Spacing") == 2
    prod = F.make_archetype(product="strut_trapeze", dimensions={"tiers": 3})
    h = prod.heights
    assert h["wired"] == len(specs) and not h["refused"]
    assert h["extrusions_locked"] == h["both_faces"] == len(prod.forms)

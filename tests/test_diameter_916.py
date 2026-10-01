"""A circle's DIAMETER labelled with a family parameter (#916), the way
Revit-born families store it (rvt.famgen.diameter_law): the same in-sketch
``RadialDim`` as the desktop-verified labelled radius (#904 P5), with a
``DimensionStyle`` of ``m_dimensionStyleType`` 9 and the diameter (2 x the arc
radius) as its value.

These tests read the WRITTEN file back and pin the dimension and its style to
the corpus law, check every refusal leaves the written file byte-identical to
the build without the spec, and run the trapeze's Rod Diameter on 2026 and
2025 through constraint_law and rvt_validate.  Nothing here claims a diameter
flexes: no diameter has a desktop verdict (hard rule 4).
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
from contextlib import ExitStack

import pytest

from rvt.families import FamilyIndex
from rvt.famgen import constraint_law as CL
from rvt.famgen import diameter_law as DM
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
    d = tempfile.mkdtemp(prefix="t916w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = 1.0 / 12.0
R = 0.25 * IN                      # a 1/2 in rod
PARTS = [{"shape": "box", "name": "plate", "width_ft": 1.0, "depth_ft": 0.5,
          "height_ft": 0.1},
         {"shape": "cylinder", "name": "rod", "radius_ft": R, "height_ft": 1.0,
          "center": [0.25, 0.0], "base_z_ft": 0.1},
         {"shape": "cylinder", "name": "pin", "radius_ft": R, "height_ft": 0.5,
          "center": [-0.25, 0.0], "base_z_ft": 0.1}]
PARAMS = {"Rod Diameter": ("length", 2.0 * R), "Pin Diameter": ("length", 2.0 * R),
          "Wrong Diameter": ("length", 3.0 * R), "Count": ("integer", 2)}
GOOD = [{"caption": "Rod Diameter", "parts": ["rod"]}]


def _build(diameters=None):
    return F.make_generic_model(parts=[dict(p) for p in PARTS], name="Rods",
                                numeric_params=dict(PARAMS), diameters=diameters)


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t916sha_")
    try:
        path = os.path.join(d, "f.rfa")
        prod.write(path)
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    finally:
        shutil.rmtree(d, True)


def _read_back(path):
    """The written file's RadialDims, DimensionStyles, arcs, sketches and
    parameter ids -- decoded under the file's own release."""
    want = ("RadialDim", "DimensionStyle", "CurveElem", "VarSketch")
    with ExitStack() as st:
        from rvt.global_framing import enter_own_release
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0)
        E = {}
        for eid, r in recs.get(102, {}).items():
            c = fi.class_name(r.class_id)
            if c in want or c.startswith("ParamElem"):
                h = fi.decode(0, eid, 101) if eid in recs.get(101, {}) else None
                E[eid] = (c, fi.decode(0, eid, 102).value, h.value if h else None)
    return E


def _pid(E, caption):
    for eid, (c, o, _h) in E.items():
        if c.startswith("ParamElem"):
            pd = next((v.get("value") or {} for k, v in o.items()
                       if k.endswith("aramDef") and isinstance(v, dict)), {})
            if caption in (pd.get("m_name"), pd.get("m_caption")):
                return eid
    raise LookupError(caption)


def _diameters(E):
    """Every labelled RadialDim whose style is a diameter style."""
    out = []
    for eid, (c, o, h) in E.items():
        if c != "RadialDim":
            continue
        st = E.get(o["m_styleSymbolId"])
        if st and st[1].get("m_dimensionStyleType") == DM.DIAMETER_STYLE_TYPE:
            out.append((eid, o, h))
    return out


def _check_born_law(E, caption, n):
    """The written diameter dims and their style equal the corpus law."""
    pid = _pid(E, caption)
    dims = [d for d in _diameters(E) if d[1]["m_ArrSegInfo"][0]["m_paramId"] == pid]
    assert len(dims) == n
    styles = {o["m_styleSymbolId"] for _e, o, _h in dims}
    assert len(styles) == 1
    st = E[styles.pop()][1]
    assert st["m_dimensionStyleType"] == 9
    assert st["m_arrowHeadStyleId"] == -1 and st["m_interiorTickMarkStyleId"] == -1
    assert st["m_radiusDiameterPrefixText"] == "ø"
    assert st["m_radiusDiameterSymbolLocation"] == 1 and st["m_radialTickType"] == 8
    sketches = {e: o for e, (c, o, _h) in E.items() if c == "VarSketch"}
    for eid, o, h in dims:
        assert o["m_flags"] == 12 and o["m_dimLockedForLabeling"] is True
        assert o["m_dimVersion"] == 6 and o["m_ownerDBViewId"] == -1
        cells = o["m_cellList"]["value"]["m_cells"]
        assert [c["ptr_class"] for c in cells] == ["SketchMembership"]
        sk = cells[0]["value"]["m_groupId"]
        assert eid in sketches[sk]["m_dimIds"]
        (seg,) = o["m_ArrSegInfo"]
        (w,) = o["m_witnessRefs"]
        assert w["m_pWitnessRef"]["ptr_class"] == "ArcRef"
        g = w["m_pWitnessRef"]["value"]["m_geomRef"]
        assert g["m_geomTag"] == 0 and w["m_id"] == {"m_id": -1}
        arc_c, arc, _ = E[g["m_elemId"]]
        assert arc_c == "CurveElem"
        crv = arc["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
        assert seg["m_flags"] == 0
        # the diameter: 2 x the labelled arc's radius, in both value fields
        assert abs(seg["m_lockedValue"] - 2.0 * crv["m_radius"]) < 1e-9
        assert abs(seg["m_values"][0]["m_value"] - 2.0 * crv["m_radius"]) < 1e-9
        assert [v["m_value"] for v in seg["m_values"][1:]] == [-1.0, -1.0]
        ca = w["m_pCachedArc"]["value"]
        assert abs(ca["m_endParams"][0]) < 1e-12 and abs(ca["m_endParams"][1] - math.pi) < 1e-9
        assert ca["m_GInfo"]["m_flags"] == DM.CACHED_ARC_FLAGS
        par = h["m_parents"]["value"]
        assert set(par["m_deletion"]) == {o["m_famId"], o["m_styleSymbolId"], pid, sk,
                                          g["m_elemId"], eid}
        assert set(par["m_appearanceParents"]) == {o["m_styleSymbolId"], sk, g["m_elemId"]}
        assert len(par["m_regenOnly"]) == 1
        assert h["m_viewRules"]["m_nVisibleViewFlags"] == -1 and h["m_abFlags4Bytes"] == 10
    return dims


def _validate(path) -> bool:
    js = path + ".validation.json"
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "rvt_validate.py"),
                           path, "--json", js], capture_output=True, text=True, timeout=600)
    rep = json.load(open(js))
    return proc.returncode == 0 and rep["ok"] and rep["counts"]["error"] == 0


# -- the generic mechanism ---------------------------------------------------

def test_a_labelled_diameter_reads_back_as_the_born_law(tmp_path):
    prod = _build(GOOD)
    assert prod.diameters["wired"] == 1 and prod.diameters["dims"] == 1
    assert not prod.diameters["refused"]
    # the document's default linear style stays the first DimensionStyle: the
    # SymbolIdMgr key-10 default registration takes the first one (#333)
    first = next(e for e in prod.doc.elements if e.class_name == "DimensionStyle")
    assert first.elem_id == prod.doc.dim_style_id
    assert first.obj["m_dimensionStyleType"] == 0
    p = str(tmp_path / "rods.rfa")
    prod.write(p)
    E = _read_back(p)
    _check_born_law(E, "Rod Diameter", 1)
    assert CL.check_file(p) == []
    assert _validate(p)


def test_two_specs_share_one_diameter_style():
    prod = _build(GOOD + [{"caption": "Pin Diameter", "parts": ["pin"]}])
    assert prod.diameters["wired"] == 2 and prod.diameters["dims"] == 2
    t9 = [e for e in prod.doc.by_class("DimensionStyle")
          if e.obj["m_dimensionStyleType"] == 9]
    assert len(t9) == 1
    # the style's own constellation, without the leader the no-arrow style lacks
    assert not any(e.class_name == "LeaderStyle" and e.elem_id in
                   t9[0].header["m_parents"]["value"]["m_deletion"]
                   for e in prod.doc.elements)


@pytest.mark.parametrize("bad", [
    [{"caption": "Wrong Diameter", "parts": ["rod"]}],        # value != 2 x radius
    [{"caption": "Count", "parts": ["rod"]}],                 # not a length
    [{"caption": "Nope", "parts": ["rod"]}],                  # no such parameter
    [{"caption": "Rod Diameter", "parts": ["plate"]}],        # no circle
    [{"caption": "Rod Diameter", "parts": ["shaft"]}],        # no such part
    [{"caption": "Rod Diameter", "parts": []}],               # nothing to label
    [{"caption": "Rod Diameter", "parts": ["rod", "rod"]}],   # listed twice
    [{"caption": "Rod Diameter", "parts": ["rod", "pin", "plate"]}],  # one bad of three
], ids=["value", "spec", "param", "box", "part", "empty", "twice", "partial"])
def test_a_refused_spec_leaves_the_file_byte_identical(bad):
    prod = _build(bad)
    assert prod.diameters["wired"] == 0 and len(prod.diameters["refused"]) == 1
    assert any("not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(_build())


def test_the_good_spec_does_change_the_file():
    assert _sha(_build(GOOD)) != _sha(_build())


def test_wire_diameter_refusals_leave_the_document_untouched():
    prod = _build()
    # rebuild an UNFINALIZED document through the factory's own hook: a
    # refused call must raise before the first element is added
    calls = {}
    orig = DM.wire_diameter_specs

    def probe(doc, specs, sketch_of):
        n0 = len(doc.elements)
        for caption, names in (("Wrong Diameter", ["rod"]), ("Count", ["rod"]),
                               ("Rod Diameter", ["plate"])):
            with pytest.raises(DM.DiameterError):
                DM.wire_diameter(doc, caption=caption,
                                 sketches=[sketch_of[n] for n in names])
            assert len(doc.elements) == n0
        r = DM.wire_diameter(doc, caption="Rod Diameter", sketches=[sketch_of["rod"]])
        assert r["style_authored"] and len(doc.elements) > n0
        # the same circle is never labelled twice
        n1 = len(doc.elements)
        with pytest.raises(DM.DiameterError):
            DM.wire_diameter(doc, caption="Pin Diameter", sketches=[sketch_of["rod"]])
        assert len(doc.elements) == n1
        calls["ok"] = True
        return {"specs": 0, "wired": 0, "dims": 0, "captions": [], "refused": []}

    DM.wire_diameter_specs = probe
    try:
        _build(GOOD)
    finally:
        DM.wire_diameter_specs = orig
    assert calls.get("ok") and prod.diameters == {}
    with pytest.raises(RuntimeError):
        DM.wire_diameter(prod.doc, caption="Rod Diameter", sketches=[])


def test_a_single_prism_says_its_diameters_are_not_wired():
    prod = F.make_generic_model(width_ft=1.0, depth_ft=1.0, height_ft=1.0,
                                diameters=GOOD)
    assert any("NOT wired" in n for n in prod.notes)


# -- the trapeze ---------------------------------------------------------------

def test_the_trapeze_labels_both_rods_and_says_it_is_unverified():
    prod = F.make_archetype(product="strut_trapeze")
    d = prod.diameters
    assert (d["wired"], d["dims"], d["captions"], d["refused"]) == (1, 2, ["Rod Diameter"], [])
    note = next(n for n in prod.doc.notes if n.startswith("diameters labelled"))
    assert "NO desktop verdict" in note and "half arc" in note
    from rvt.famgen import archetypes as AR
    arch = AR.archetype("strut_trapeze")
    assert "no desktop verdict" in arch.lod_note
    assert any("Rod Diameter" in x and "NO desktop verdict" in x for x in arch.limits)


@pytest.mark.parametrize("release", [2026, 2025])
def test_the_trapeze_rod_diameter_on_2026_and_2025(release):
    from rvt.frontdoor import release_ctx as RC
    d = tempfile.mkdtemp(prefix=f"t916trap{release}_")
    try:
        path = os.path.join(d, "trapeze.rfa")
        if release == RC.native_release():
            prod = F.make_archetype(product="strut_trapeze")
            prod.write(path)
        else:
            with RC.release_build_context(RC._bundled_base_of(release)):
                prod = F.make_archetype(product="strut_trapeze")
                prod.write(path)
        E = _read_back(path)
        dims = _check_born_law(E, "Rod Diameter", 2)
        # one per rod, each on its own sketch
        assert len({o["m_cellList"]["value"]["m_cells"][0]["value"]["m_groupId"]
                    for _e, o, _h in dims}) == 2
        assert CL.check_file(path) == []
        assert _validate(path)
    finally:
        shutil.rmtree(d, True)

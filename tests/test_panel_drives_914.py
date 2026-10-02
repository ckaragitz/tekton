"""Panel drives: every sketch lock lies on its plane (#914).

Two changes are pinned here, both read back from the WRITTEN file:

1. **The panelboard chain** (now `drive="372"`; the default is drive_law, #914 DONE 3,
   `tests/test_panel_drive_law_914.py`).  ``param_drive.wire_panelboard_drive`` used to put its
   side planes at x = +-W/2 and y = +-D/2 about the origin.  The panelboard profile
   spans y = 0..D (surface) or -D..0 (flush), so the two y locks sat 0.24 ft off
   their planes -- constraint law CG7.  Now every plane is placed on the edge it
   locks.  A centred profile gives the same numbers, so the generic box, the
   troffer and the switchboard are byte-identical to before (measured in the
   record, not here).
2. **The lighting control panel.**  Cabinet Width is a symmetric in-plane drive
   with the side walls and the door latch riding it (``drive_law.wire_attach``),
   and the cabinet's heights are #787 Case B cap-face drives.

Every refusal leaves the written file byte-identical to the build without the
refused drive.  Nothing here claims a family flexes in Revit: none of these
assembled families has a desktop verdict (hard rule 4).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from contextlib import ExitStack

import pytest

from rvt.families import FamilyIndex
from rvt.famgen import archetypes as AR
from rvt.famgen import constraint_law as CL
from rvt.famgen import drive_law as DL
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
    d = tempfile.mkdtemp(prefix="t914w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)
from rvt.famgen import param_drive as PD

TOL = 1e-6


def _write(prod, d, name="f.rfa"):
    path = os.path.join(d, name)
    res = prod.write(path)
    assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
    return path


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t914sha_")
    try:
        path = os.path.join(d, "f.rfa")
        prod.write(path)
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    finally:
        shutil.rmtree(d, True)


def _plane(o):
    """(point, unit normal) of a RefPlane record: through m_freeEnd, spanned by
    m_bubbleEnd - m_freeEnd and m_cutVec."""
    f, b, c = o["m_freeEnd"], o["m_bubbleEnd"], o["m_cutVec"]
    u = [b[i] - f[i] for i in range(3)]
    n = (u[1] * c[2] - u[2] * c[1], u[2] * c[0] - u[0] * c[2], u[0] * c[1] - u[1] * c[0])
    m = sum(x * x for x in n) ** 0.5
    return (f, tuple(x / m for x in n)) if m > 1e-12 else None


def _locks_on_planes(path):
    """Every SKETCH lock of the written file: (locks read, locks off their plane).

    A sketch lock is an Alignment between a RefPlane and a CurveElem; the
    curve's ends are read from its GLine (m_origin + m_dirVec * t for t in
    m_endParams) and measured against the plane."""
    with ExitStack() as st:
        from rvt.global_framing import enter_own_release
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0).get(102, {})
        E = {eid: (fi.class_name(r.class_id), fi.decode(0, eid, 102).value)
             for eid, r in recs.items()
             if fi.class_name(r.class_id) in ("RefPlane", "Alignment", "CurveElem")}
    n = off = 0
    for _eid, (cls, v) in E.items():
        if cls != "Alignment":
            continue
        g = [w["m_pWitnessRef"]["value"]["m_geomRef"] for w in v["m_witnessRefs"]]
        pl = [x for x in g if E.get(x["m_elemId"], ("",))[0] == "RefPlane"]
        cu = [x for x in g if E.get(x["m_elemId"], ("",))[0] == "CurveElem"]
        if len(pl) != 1 or len(cu) != 1:
            continue                                   # a face lock, not a sketch lock
        crv = E[cu[0]["m_elemId"]][1]["m_pCurveDriver"]["value"]["m_pCrv"]
        assert crv["ptr_class"] == "GLine", crv["ptr_class"]
        c = crv["value"]
        p0, nrm = _plane(E[pl[0]["m_elemId"]][1])
        ends = [[c["m_origin"][i] + c["m_dirVec"][i] * t for i in range(3)]
                for t in c["m_endParams"]]
        n += 1
        off += any(abs(sum((e[i] - p0[i]) * nrm[i] for i in range(3))) > TOL for e in ends)
    return n, off


def _in_release(release, build):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return build()
    with RC.release_build_context(RC._bundled_base_of(release)):
        return build()


BUILDS = {
    "panelboard": lambda: F.make_panelboard(name="B914"),
    "panelboard_flush": lambda: F.make_panelboard(name="B914F", mounting="flush"),
    "panelboard_types": lambda: F.make_panelboard(name="B914T", types=["225A", "400A"]),
    "panelboard_600A": lambda: F.make_panelboard(name="B914_600", mains_a=600),
    # the panelboard keys above carry drive_law since #914 DONE 3; the old
    # #372 chain stays read back from the written file too
    "panelboard_372": lambda: F.make_panelboard(name="B914_372", drive="372"),
    "panelboard_flush_372": lambda: F.make_panelboard(name="B914F_372", mounting="flush",
                                                      drive="372"),
    "lighting_control_panel": lambda: F.make_archetype(product="lighting_control_panel"),
}


@pytest.mark.parametrize("release", [2026, 2025])
@pytest.mark.parametrize("key", sorted(BUILDS))
def test_every_written_sketch_lock_lies_on_its_plane(key, release):
    d = tempfile.mkdtemp(prefix=f"t914_{release}_")
    try:
        def build():
            prod = BUILDS[key]()
            return prod, _write(prod, d)
        prod, path = _in_release(release, build)
        n, off = _locks_on_planes(path)
        assert n == len(DL._sketch_locks(prod.doc)) and n > 0
        assert off == 0, f"{off} of {n} sketch locks are off their planes"
        assert CL.check_file(path) == []
        if key == "lighting_control_panel":            # the whole chain, on both releases
            assert [len(x["locks"]) for x in prod.drives] == [8]
            assert prod.heights["wired"] == 3 and not prod.heights["refused"]
    finally:
        shutil.rmtree(d, True)


@pytest.mark.parametrize("mounting, y", [("surface", (0.0, 1.0)), ("flush", (-1.0, 0.0))])
def test_the_panelboard_depth_planes_sit_on_the_profile_edges(mounting, y):
    # the OLD #372 chain, now behind drive="372" (#914 DONE 3 moved the default
    # to drive_law: tests/test_panel_drive_law_914.py); its planes stay on edges
    prod = F.make_panelboard(name="B914P", mounting=mounting, drive="372")
    D = prod.doc.types[prod.doc.current_type][1][prod.doc.params["Depth"].elem_id]
    side = [p.obj for p in prod.doc.refplanes if not p.obj.get("m_definesOrigin")]
    ys = sorted(o["m_freeEnd"][1] for o in side
                if abs(o["m_freeEnd"][1] - o["m_bubbleEnd"][1]) < 1e-12)
    assert ys == pytest.approx([y[0] * D, y[1] * D])        # was [-D/2, +D/2]
    assert CL.check_doc(prod.doc) == []


def test_a_centred_profile_keeps_its_planes_at_plus_minus_half():
    """The fix reads the planes off the profile, so a centred box is unchanged.

    RE-PINNED (#913 drives-rest): this pins the #372 chain, which the single
    prism wired by default until #913 and now wires behind prism_drive="372"
    (byte-identical); the default build drives the prism through drive_law /
    height_law instead (tests/test_drives_rest_913.py)."""
    prod = F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0, name="C914",
                                prism_drive="372")
    new = [p for p in prod.doc.refplanes if not p.obj.get("m_definesOrigin")]
    at = sorted((round(p.obj["m_freeEnd"][0], 12) if abs(p.obj["m_freeEnd"][0] - p.obj["m_bubbleEnd"][0]) < 1e-12
                 else round(p.obj["m_freeEnd"][1], 12)) for p in new)
    assert at == [-1.0, -0.5, 0.5, 1.0]
    assert CL.check_doc(prod.doc) == []


def test_a_parameter_that_disagrees_with_the_profile_is_refused_before_any_mutation():
    from rvt.famgen import skeleton as SK
    seen = {}

    def grab(self, *a, **k):
        seen.setdefault("doc", self)
        raise RuntimeError("stop")
    orig = SK.FamilyDoc.finalize
    SK.FamilyDoc.finalize = grab
    try:
        with pytest.raises(RuntimeError, match="stop"):
            F.make_panelboard(name="B914R", drive="372")        # the old chain (#914 DONE 3)
    finally:
        SK.FamilyDoc.finalize = orig
    doc = seen["doc"]
    # strip the wired chain's own record of itself: run the drive again on a
    # document whose Depth row is wrong and check nothing is added
    row = doc.types[doc.current_type][1]
    pid = doc.params["Depth"].elem_id
    row[pid] = float(row[pid]) + 0.5
    before = [e.elem_id for e in doc.elements]
    planes = len(doc.refplanes)
    with pytest.raises(ValueError, match="disagree with the profile"):
        PD.wire_panelboard_drive(doc, x_caption="Width", y_caption="Depth")
    assert [e.elem_id for e in doc.elements] == before and len(doc.refplanes) == planes


# --------------------------------------------------------------------------- the LCP

def test_the_lighting_control_panel_wires_width_and_heights():
    prod = F.make_archetype(product="lighting_control_panel")
    (d,) = prod.drives
    assert (d["caption"], d["axis"], d["symmetric"], len(d["locks"])) == (
        "Cabinet Width", "x", True, 8)
    assert (d["attach"]["parts"], d["attach"]["locks"], d["attach"]["planes"]) == (3, 6, 4)
    h = prod.heights
    assert (h["wired"], h["refused"], h["face_locks"], h["extrusions_locked"],
            h["both_faces"], h["planes"]) == (3, [], 12, 6, 6, 4)
    assert h["captions"] == ["Cabinet Height", "Sheet Thickness"]
    for cap in ("Cabinet Width", "Cabinet Height", "Cabinet Depth", "Sheet Thickness"):
        assert cap in prod.doc.params
    # honest text: authored, the assembled family unverified, heights unverdicted
    assert any("assembled family unverified" in n for n in prod.doc.notes)
    assert any("#787 Case B" in n and "NO desktop verdict" in n for n in prod.doc.notes)
    assert not any("not wired" in n or "not made" in n for n in prod.doc.notes), prod.doc.notes
    assert CL.check_doc(prod.doc) == []


def test_the_clearance_variant_wires_the_same_drives():
    prod = F.make_archetype(product="lighting_control_panel",
                            prompt="a lighting control panel with clearance")
    assert [len(d["locks"]) for d in prod.drives] == [8]
    assert prod.heights["wired"] == 3 and not prod.heights["refused"]


V = AR.archetype("lighting_control_panel").defaults()
PARTS = AR._lighting_control_panel(V)
PARAMS = AR._box_params("Cabinet")(V)
GOOD_D = AR._lcp_drives(V)
GOOD_H = AR._lcp_heights(V)


def _build(drives=None, heights=None):
    return F.make_generic_model(parts=[dict(p) for p in PARTS], name="LCP914",
                                numeric_params=dict(PARAMS), drives=drives, heights=heights,
                                category="electrical_equipment")


def _bad_drive(**kw):
    return [dict(GOOD_D[0], **kw)]


@pytest.mark.parametrize("drives", [
    _bad_drive(parts={"no such part": ("lo", "hi")}),          # a name that matches nothing
    _bad_drive(lo=-1.0, hi=1.0),                               # disagrees with Cabinet Width
    _bad_drive(axis="y"),                                      # edges are not on y planes
    _bad_drive(caption="Height"),                              # Height is 30 in, the planes 20 in
])
def test_a_refused_width_drive_leaves_the_file_byte_identical(drives):
    control = _build(None, GOOD_H)
    prod = _build(drives, GOOD_H)
    assert prod.drives == []
    assert any("not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(control)


def test_a_refused_attach_keeps_the_drive_and_touches_nothing_else():
    control = _build([{k: v for k, v in GOOD_D[0].items() if k != "attach"}], GOOD_H)
    prod = _build(_bad_drive(attach={"lo": ["wall left"], "hi": ["no such part"]}), GOOD_H)
    assert [len(d["locks"]) for d in prod.drives] == [8] and "attach" not in prod.drives[0]
    assert any("not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(control)


@pytest.mark.parametrize("heights", [
    [dict(GOOD_H[0], hi=GOOD_H[0]["hi"] + 0.1)],               # off the cap faces
    [dict(GOOD_H[0], parts={"no such part": {"end": "hi"}})],  # a name that matches nothing
    [dict(GOOD_H[2])],                                         # names a plane no spec authored
])
def test_a_refused_height_leaves_the_file_byte_identical(heights):
    control = _build(GOOD_D, None)
    prod = _build(GOOD_D, heights)
    assert prod.heights["wired"] == 0 and prod.heights["refused"]
    assert _sha(prod) == _sha(control)


def test_a_later_refused_height_keeps_the_earlier_ones():
    control = _build(GOOD_D, GOOD_H)
    prod = _build(GOOD_D, GOOD_H + [dict(GOOD_H[0])])          # the same faces again
    assert prod.heights["wired"] == 3 and prod.heights["refused"] == ["Cabinet Height"]
    assert _sha(prod) == _sha(control)

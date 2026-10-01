"""Locks and parameter association on nested instances (#917, second pass).

A born family locks a nested instance's centre references (Center (Left/Right),
Center (Front/Back)) to its own reference planes and lets its own parameters
drive the nested family's instance parameters.  These tests pin
``rvt.famgen.nest.nest_family(locks=..., associate=...)`` and the constraint
law's instance-lock rule CG8, read back from the written file on 2026 and 2025:
0 validator errors (family mode), an empty constraint-law report, and every
lock judged by CG8.  Nothing here claims Revit honours the locks or the
association: no desktop verdict exists (hard rule 4).
"""
from __future__ import annotations

import hashlib
import math
import os
import shutil
import tempfile
from contextlib import ExitStack, nullcontext

import pytest

from rvt.famgen import constraint_law as CL
from rvt.famgen import factory as F
from rvt.famgen import geometry as G
from rvt.famgen import nest as N
from rvt.famgen import skeleton as SK
from conftest import context_constants, ladder_constants

# builds enter the write-side release context (2025 targets) and the read-back
# climbs the read-side ladder: conftest's guard watches both (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")

IN = 1.0 / 12.0
NUT_SIZE = 0.5 * IN


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the
    native codec singletons; do that once before the guard's first snapshot."""
    d = tempfile.mkdtemp(prefix="t917lw_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="t917l_")
    yield d
    shutil.rmtree(d, True)


def _ctx(release):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return nullcontext()
    return RC.release_build_context(RC._bundled_base_of(release))


def _nut(sid):
    """A nut-sized box carrying one INSTANCE length parameter, ``Nut Size``
    (born hosts associate nested instance parameters only)."""
    doc = SK.new_family_document("generic_model", "Probe Nut", work_plane_based=False,
                                 start_id=sid, plane_length_ft=1.0)
    for d in ("Width", "Depth", "Height"):
        doc.add_family_parameter(d, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS)
    ns = doc.add_family_parameter("Nut Size", SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                  is_instance=True, default=NUT_SIZE)
    w = 0.75 * IN
    doc.add_type("Probe Nut", {doc.params["Width"].elem_id: w, doc.params["Depth"].elem_id: w,
                               doc.params["Height"].elem_id: 0.5 * IN, ns.elem_id: NUT_SIZE})
    F.add_box_form(doc, w, w, 0.5 * IN, base_z_ft=0.0, center=(0.0, 0.0), rep=G.REP_SOLID)
    doc.finalize()
    return F.FamilyProduct("generic_model", doc, F.FactSheet(subject="probe nut"),
                           forms=[], file_stem="probe_nut")


def _planes(host):
    """(rod plane at x = -1, rod plane at x = +1, origin Center (Front/Back))."""
    ps = N.host_reference_planes(host)
    at = {}
    for p in ps:
        n = p["normal"]
        if n and abs(abs(n[0]) - 1.0) < 1e-9 and p["ref_name"] != 1:
            at[round(p["point"][0], 9)] = p["id"]
    fb = [p["id"] for p in ps if p["ref_name"] == 4 and p["defines_origin"]]
    assert len(fb) == 1
    return at[-1.0], at[1.0], fb[0]


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _decode(path, ids):
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        return {i: (fi.decode(0, i, 101).value, fi.decode(0, i, 102).value) for i in ids}


def _resolved(path):
    """CG8's resolved instance references of a written file."""
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    from rvt.objects import ObjectDecoder
    with ExitStack() as st:
        enter_own_release(st, path)
        idx = FamilyIndex(path)
        dec = ObjectDecoder(idx.schema)
        recs = idx.unit_records(0)
        tuples = [(e, "Alignment", dec.decode_record(recs[102][e].class_id,
                                                     recs[102][e].payload).value, None)
                  for e in idx.ids_of_class(0, "Alignment")]
        return CL._instance_planes(idx, recs, tuples)


@pytest.mark.parametrize("release", [2026, 2025])
def test_nested_nuts_lock_to_the_rod_planes_and_follow_rod_diameter(release, tmp):
    host, out = os.path.join(tmp, "trap.rfa"), os.path.join(tmp, "nested.rfa")
    pts = [(-1.0, 0.0, -0.3), (1.0, 0.0, -0.3)]
    with _ctx(release):
        F.make_archetype(product="strut_trapeze").write(host)
        lo, hi, fb = _planes(host)
        res = N.nest_family(host, out, _nut, pts,
                            locks=[(0, "center_lr", lo), (1, "center_lr", hi),
                                   N.Lock(0, "center_fb", fb), N.Lock(1, "center_fb", fb)],
                            associate={"Rod Diameter": "Nut Size"})
    assert res.ok and len(res.instance_ids) == 2 and len(res.lock_ids) == 4
    ver = res.proofs["verify"]
    assert ver["validate"]["n_errors"] == 0 and ver["constraint_law"] == []
    assert ver["registries_coherent"] and ver["locks"] == 4
    assert CL.check_file(out) == []
    # every lock is JUDGED by CG8, not skipped: the four centre references resolve
    i0, i1 = res.instance_ids
    placed = _resolved(out)
    assert set(placed) == {(i0, 1), (i0, 4), (i1, 1), (i1, 4)}
    assert placed[(i0, 1)][0] == (-1.0, 0.0, -0.3)

    E = _decode(out, res.instance_ids + res.lock_ids + [res.nested_family_id])
    want = {(i0, lo, 1), (i1, hi, 1), (i0, fb, 4), (i1, fb, 4)}
    got = set()
    for lid in res.lock_ids:
        h, o = E[lid]
        assert o["m_flags"] == N.LOCK_FLAGS and o["m_dimVersion"] == N.LOCK_DIM_VERSION
        assert o["m_cellList"] is None and o["m_ownerDBViewId"] == -1
        wp, wi = (w["m_pWitnessRef"]["value"]["m_geomRef"] for w in o["m_witnessRefs"])
        assert (wp["m_geomTag"], wp["m_flags"]) == (0, 0)
        assert wi["m_flags"] == N.LOCK_GREF_FLAGS_INSTANCE and wi["m_subTag"] == -1
        assert tuple(w["m_constrFlags"] for w in o["m_witnessRefs"]) == N.LOCK_CONSTR_FLAGS
        got.add((wi["m_elemId"], wp["m_elemId"], wi["m_geomTag"]))
        par = h["m_parents"]["value"]
        assert (h["m_abFlags4Bytes"], h["m_viewRules"]["m_nVisibleViewFlags"]) == (10, -4225)
        assert {wi["m_elemId"], wp["m_elemId"], lid} <= set(par["m_deletion"])
        assert res.symbol_id in par["m_regenOnly"]
        assert {wi["m_elemId"], wp["m_elemId"]} <= set(par["m_appearanceParents"])
    assert got == want
    # the association: one cell before the pattern helper, the host value on the row
    hp = res.associations[0]["host_param"]
    twin = res.associations[0]["nested_twin"]
    selff = E[i0][1]["m_famId"]
    host_row = [r for r in _decode(out, [selff])[selff][1]["m_familyParams"]["value"]["m_params"]
                if r["m_paramId"] == hp]
    assert len(host_row) == 1 and host_row[0]["m_value"] > 0 and host_row[0]["m_value"] != NUT_SIZE
    for iid in res.instance_ids:
        h, o = E[iid]
        cells = o["m_cellList"]["value"]["m_cells"]
        assert [c["ptr_class"] for c in cells] == ["FamilyParametrizedElemParamsCell",
                                                    "FamilyInstancePatternHelper"]
        assert cells[0]["value"]["m_paramDrivenData"] == [
            {"m_famParamId": hp, "m_elemPropId": twin, "m_geomTag": -1, "m_bIsSymbol": False}]
        row = [r for r in o["m_pInstParams"]["value"]["m_params"] if r["m_paramId"] == twin]
        assert len(row) == 1 and row[0]["m_value"] == host_row[0]["m_value"]   # the host's, not the nut's
        assert hp in h["m_parents"]["value"]["m_deletion"]
        assert h["m_parents"]["value"]["m_regenOnly"] == [res.nested_family_id]
    # the nested Family's reference index carries the two centre codes the locks name
    rim = E[res.nested_family_id][1]["m_oFamilyReferenceIdxMgr"]["value"]["m_idxToRefMap"]
    assert {e["second"]["first"] for e in rim} >= {1, 4}


def test_locked_nesting_is_deterministic(tmp):
    from rvt.container import open_rvt
    host = os.path.join(tmp, "h.rfa")
    F.make_archetype(product="strut_trapeze").write(host)
    lo, _hi, fb = _planes(host)
    streams = []
    for i in range(2):
        p = os.path.join(tmp, f"d{i}.rfa")
        N.nest_family(host, p, _nut, [(-1.0, 0.0, 0.0)],
                      locks=[(0, "center_lr", lo), (0, "center_fb", fb)],
                      associate={"Rod Diameter": "Nut Size"})
        with open_rvt(p) as f:
            streams.append({s.name: f.raw(s.name) for s in f.streams()
                            if s.name != "BasicFileInfo"})
    assert streams[0] == streams[1]


@pytest.fixture(scope="module")
def trap_host():
    d = tempfile.mkdtemp(prefix="t917lh_")
    host = os.path.join(d, "trap.rfa")
    F.make_archetype(product="strut_trapeze").write(host)
    yield host, _planes(host)
    shutil.rmtree(d, True)


@pytest.mark.parametrize("case, why", [
    ("off_plane", "off plane"),
    ("crossed", "not parallel"),
    ("reference", "not one of"),
    ("index", "there are 1 points"),
    ("elevation", "no origin plane"),
    ("not_a_plane", "not a RefPlane"),
    ("twice", "locked twice"),
    ("shape", "must be"),
    ("type_param", "type parameter"),
    ("no_host_param", "host has no family parameter"),
    ("no_child_param", "nested family has no parameter"),
    ("kind", "not the same kind"),
])
def test_contradicting_or_unknown_locks_and_associations_are_refused(case, why, trap_host, tmp):
    host, (lo, hi, fb) = trap_host
    before = _sha(host)
    out = os.path.join(tmp, "n.rfa")
    pt = [(-1.0, 0.0, 0.0)]
    kw = {
        "off_plane": dict(points=[(-0.9, 0.0, 0.0)], locks=[(0, "center_lr", lo)]),
        "crossed": dict(locks=[(0, "center_lr", fb)]),
        "reference": dict(locks=[(0, "left", lo)]),
        "index": dict(locks=[(1, "center_lr", hi)]),
        "elevation": dict(locks=[(0, "center_elevation", lo)]),
        "not_a_plane": dict(locks=[(0, "center_lr", 1)]),
        "twice": dict(locks=[(0, "center_lr", lo), (0, "center_lr", lo)]),
        "shape": dict(locks=[(0, "center_lr")]),
        "type_param": dict(associate={"Rod Diameter": "Width"}),
        "no_host_param": dict(associate={"No Such": "Nut Size"}),
        "no_child_param": dict(associate={"Rod Diameter": "No Such"}),
        "kind": dict(associate={"Number of Tiers": "Nut Size"}),
    }[case]
    pts = kw.pop("points", pt)
    with pytest.raises(N.NestError, match=why):
        N.nest_family(host, out, _nut, pts, **kw)
    assert not os.path.exists(out)
    assert _sha(host) == before


def test_host_reference_planes_lists_the_origin_centre_planes(trap_host):
    host, _ = trap_host
    ps = {p["ref_name"]: p for p in N.host_reference_planes(host) if p["defines_origin"]}
    assert ps[1]["normal"] in ([1.0, 0.0, 0.0], [-1.0, 0.0, 0.0])
    assert ps[4]["point"][1] == 0.0


# -- CG8 on its own: synthetic graphs ---------------------------------------

def _rp(eid, x):
    """A RefPlane at x = ``x`` (normal +X), drawn-ends form."""
    return (eid, "RefPlane", {"m_freeEnd": [x, -1.0, 0.0], "m_bubbleEnd": [x, 1.0, 0.0],
                              "m_cutVec": [0.0, 0.0, 1.0]})


def _align(eid, plane, inst, tag=1):
    def w(t, g):
        return {"m_pWitnessRef": {"ptr_class": "GeomSegInPlaneRef", "value": {
            "m_geomRef": {"m_elemId": t, "m_geomTag": g}}}}
    return (eid, "Alignment", {"m_witnessRefs": [w(plane, 0), w(inst, tag)], "m_flags": 14})


@pytest.mark.parametrize("placed, rule", [
    (((2.0, 0.5, 0.0), (1.0, 0.0, 0.0)), None),                 # on the plane
    (((2.0, 0.5, 0.0), (-1.0, 0.0, 0.0)), None),                # flipped normal: still on it
    (((2.1, 0.0, 0.0), (1.0, 0.0, 0.0)), "CG8"),                # 0.1 ft off
    (((2.0, 0.0, 0.0), (0.0, 1.0, 0.0)), "CG8"),                # crossing the plane
])
def test_cg8_judges_a_placed_instance_reference_against_its_plane(placed, rule):
    els = [_rp(10, 2.0), (20, "FamilyInstance", {}), _align(30, 10, 20)]
    f = CL.check_graph(els, instance_planes={(20, 1): placed})
    assert [x["rule"] for x in f] == ([rule] if rule else [])


def test_cg8_never_guesses_an_unresolved_reference():
    els = [_rp(10, 2.0), (20, "FamilyInstance", {}), _align(30, 10, 20, tag=44)]
    assert CL.check_graph(els, instance_planes={(20, 1): ((9.0, 0, 0), (1.0, 0, 0))}) == []
    assert CL.check_graph(els) == []


def test_transform_reads_m_3x3_rows_as_the_world_components():
    """``world_k = m_or_k + m_3x3[k] . v`` -- the reading under which every
    judged born lock holds (the transposed one leaves 249 non-parallel)."""
    trf = {"m_3x3": [[0.0, 0.0, 1.0], [-1.0, 0.0, 0.0], [0.0, -1.0, 0.0]],
           "m_or": [1.0, 2.0, 3.0]}
    p, n = CL.transform_plane(trf, ((0.0, 1.0, 0.0), (1.0, 0.0, 0.0)))
    assert p == (1.0, 2.0, 2.0) and n == (0.0, -1.0, 0.0)


def test_plane_of_any_reads_a_surface_only_plane():
    obj = {"m_freeEnd": [0.0] * 3, "m_bubbleEnd": [0.0] * 3, "m_cutVec": [0.0] * 3,
           "m_pSurface": {"ptr_class": "Plane", "value": {
               "m_origin": [0.0, 0.0, 0.5], "m_xVec": [-1.0, 0.0, 0.0],
               "m_yVec": [0.0, -1.0, 0.0]}}}
    assert CL.plane_of("RefPlane", obj) is None
    assert CL.plane_of_any("RefPlane", obj) == ((0.0, 0.0, 0.5), (0.0, 0.0, 1.0))
    assert math.isclose(CL.plane_of_any("RefPlane", dict(_rp(1, 3.0)[2]))[0][0], 3.0)

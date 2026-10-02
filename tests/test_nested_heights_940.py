"""The nested trapeze's washers and nuts locked by HEIGHT (#940).

The #940 census (421 born families, counts only): a nested part follows a host
height by an ``Alignment`` lock of one of its references to a horizontal host
plane in 1,203 instances -- the dominant mechanism -- and for an unrotated free
instance the lockable horizontal reference is the child's Center (Elevation)
(m_refName 7), carried on its origin elevation plane at z 0 (61 / 61 born child
documents).  These tests pin that, read back from the written file on 2026 and
2025: every nested instance locked three ways, every lock judged by CG8 (now
also checking the lock's own frame), each elevation lock on the height-chain
plane at the part's bottom face, the reference index naming code 7 and never
12, and every refusal delivering the solid trapeze byte for byte.  Nothing
here claims Revit moves a locked nested instance: no desktop verdict exists
(hard rule 4).
"""
from __future__ import annotations

import os
import shutil
import tempfile
from contextlib import ExitStack, nullcontext

import pytest

from rvt.famgen import archetypes as AR
from rvt.famgen import constraint_law as CL
from rvt.famgen import factory as F
from rvt.famgen import nest as N
from rvt.famgen import trapeze_nested as TN
from conftest import context_constants, ladder_constants, streams

# builds enter the write-side release context (2025 targets) and the read-back
# climbs the read-side ladder: conftest's guard watches both (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")

IN = 1.0 / 12.0


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the
    native codec singletons; do that once before the guard's first snapshot."""
    d = tempfile.mkdtemp(prefix="t940w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="t940_")
    yield d
    shutil.rmtree(d, True)


def _ctx(release):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return nullcontext()
    return RC.release_build_context(RC._bundled_base_of(release))


def _read(path, classes):
    """{class: {id: object}} for the host unit's elements of ``classes``."""
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    out = {c: {} for c in classes}
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        for c in classes:
            for i in fi.ids_of_class(0, c):
                out[c][i] = fi.decode(0, i, 102).value
    return out


THREE_TIERS = {"tiers": 3, "tier_spacing_in": 10, "washer_thickness_in": 0.1875}


@pytest.fixture(scope="module", params=[(2026, None), (2025, None), (2026, "three")])
def nested(request):
    """(release, dimensions, product, report, path) per case."""
    release, dkey = request.param
    dims = THREE_TIERS if dkey == "three" else None
    d = tempfile.mkdtemp(prefix=f"t940n{release}_")
    path = os.path.join(d, "trapeze.rfa")
    with _ctx(release):
        prod = F.make_archetype(product="strut_trapeze", nested_hardware=True,
                                dimensions=dims)
        rep = prod.write(path)
    yield release, dims, prod, rep, path
    shutil.rmtree(d, True)


# ---------------------------------------------------------------------------
# the children: a Center (Elevation) reference on the origin elevation plane
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("make", [
    lambda: TN.make_washer(1000, size_ft=1.625 * IN, thickness_ft=0.25 * IN),
    lambda: TN.make_hex_nut(1000, across_flats_ft=0.5625 * IN, height_ft=0.328125 * IN)])
def test_children_carry_center_elevation_on_their_origin_plane(make):
    prod = make()
    hor = []
    for rp in prod.doc.refplanes:
        pl = CL.plane_of_any("RefPlane", rp.obj)
        if pl is not None and abs(abs(pl[1][2]) - 1.0) < 1e-9:
            hor.append((rp.obj.get("m_refName"), bool(rp.obj.get("m_definesOrigin")), pl[0][2]))
    origin = [h for h in hor if h[1]]
    # exactly one horizontal origin plane, at z 0, code 7; no "Not a
    # Reference" (12) origin plane left (born: never in the reference index)
    assert origin == [(7, True, 0.0)]
    assert N._child_centre_plane(prod, 7) is not None
    assert not [h for h in hor if h[0] == 12]
    assert any("Center (Elevation)" in x for x in prod.doc.notes)


def test_origin_elevation_reference_refuses_without_the_plane():
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("generic_model", "x", work_plane_based=False,
                                 start_id=1000, plane_length_ft=1.0)
    with pytest.raises(TN.NestedHardwareError):
        TN.origin_elevation_reference(doc)       # no height drive -> no origin plane


# ---------------------------------------------------------------------------
# the nested trapeze: three locks per instance, every one judged
# ---------------------------------------------------------------------------

def test_every_nested_instance_is_locked_by_height_and_judged(nested):
    release, dims, prod, rep, path = nested
    assert rep["ok"], rep.get("validate")
    nh = rep["nested_hardware"]
    assert nh["ok"], nh
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    from rvt.versions import detect_release
    assert int(detect_release(path)) == release
    tiers = int((dims or {}).get("tiers", 2))
    insts = nh["washer"]["instance_ids"] + nh["nut"]["instance_ids"]
    assert len(insts) == 8 * tiers
    assert len(nh["washer"]["lock_ids"]) == len(nh["nut"]["lock_ids"]) == 12 * tiers
    assert CL.check_file(path) == []
    judged = CL.judged_instance_locks(path)
    got = {(r["instance"], r["tag"]) for r in judged}
    assert got == {(i, c) for i in insts for c in (1, 4, 7)}
    assert len(judged) == len(got)
    elev = [r for r in judged if r["elevation"]]
    assert sorted(r["instance"] for r in elev) == sorted(insts)
    assert all(r["tag"] == 7 for r in elev)
    assert not [r for r in judged if r["tag"] != 7 and r["elevation"]]


def test_elevation_locks_sit_on_the_height_chain_planes(nested):
    """Each elevation lock's plane is the host horizontal plane at the part's
    bottom face -- the plane the solid version locks that face to -- and the
    instance sits there (the solid builder's position, part for part)."""
    _release, dims, prod, rep, path = nested
    nh = rep["nested_hardware"]
    E = _read(path, ["Alignment", "FamilyInstance", "RefPlane"])
    by_inst = {}
    for lid in nh["washer"]["lock_ids"] + nh["nut"]["lock_ids"]:
        o = E["Alignment"][lid]
        wp, wi = (w["m_pWitnessRef"]["value"]["m_geomRef"] for w in o["m_witnessRefs"])
        if wi["m_geomTag"] == 7:
            assert wi["m_elemId"] not in by_inst
            by_inst[wi["m_elemId"]] = wp["m_elemId"]
            # born shape of the 9 Center (Elevation) locks: plane first,
            # constrFlags 4 / 2, flags 14, the instance geomRef flags 1
            assert [w["m_constrFlags"] for w in o["m_witnessRefs"]] == [4, 2]
            assert o["m_flags"] == 14 and wi["m_flags"] == 1
            assert abs(abs(o["m_constrDir"][2]) - 1.0) < 1e-12
    v = dict(AR.resolve("strut_trapeze", dims or {}).values)
    pos = TN.hardware_positions(v)
    want = sorted(round(o[2], 9) for k in pos for o, _s in pos[k])
    zs = []
    for iid, pid in by_inst.items():
        pl = CL.plane_of_any("RefPlane", E["RefPlane"][pid])
        assert abs(abs(pl[1][2]) - 1.0) < 1e-12
        z = E["FamilyInstance"][iid]["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"][2]
        assert abs(pl[0][2] - z) < 1e-9
        assert prod.z_planes[min(prod.z_planes, key=lambda k: abs(k - z))] == pid
        zs.append(round(z, 9))
    assert sorted(zs) == want
    # the solid version's washer / nut bottom faces are at the same heights
    solid = sorted(round(p["base_z_ft"], 9) for p in AR._strut_trapeze(v)
                   if TN.is_hardware(p["name"]))
    assert solid == want


def test_reference_index_and_strong_refs_name_center_elevation(nested):
    """The nested Family's reference index lists code 7 (61 / 61 born) and no
    longer 12 (born: 0 / 1,312); the symbol's strong references carry 7 (every
    born locked code is there: 11 / 11 for 7)."""
    _release, _dims, _prod, rep, path = nested
    nh = rep["nested_hardware"]
    E = _read(path, ["Family", "FamilySymbol"])
    for r in (nh["washer"], nh["nut"]):
        rim = E["Family"][r["nested_family_id"]]["m_oFamilyReferenceIdxMgr"]["value"]["m_idxToRefMap"]
        codes = sorted(e["second"]["first"] for e in rim)
        assert codes == [1, 4, 7]
        sym = [o for o in E["FamilySymbol"].values()
               if o.get("m_familyId") == r["nested_family_id"]]
        assert len(sym) == 1
        assert {g["m_geomTag"] for g in sym[0]["m_strongRefs"]} >= {1, 4, 7}


def test_notes_state_the_lock_and_the_missing_verdict(nested):
    _release, _dims, _prod, rep, _path = nested
    notes = " ".join(rep["family"]["notes"])
    assert "Center (Elevation)" in notes and "LOCKED to the host's height planes" in notes
    assert "unverified" in notes and "hard rule 4" in notes
    assert "do NOT follow" not in notes


# ---------------------------------------------------------------------------
# the plane lookup and the refusals: always the solid trapeze, byte for byte
# ---------------------------------------------------------------------------

def test_height_planes_needs_exactly_one_plane_per_height():
    prod = F.make_archetype(product="strut_trapeze", nested_hardware=True)
    assert isinstance(prod, TN.NestedHardwareProduct)
    zs = sorted(prod.z_planes)
    assert TN.height_planes(prod.doc, zs) == prod.z_planes
    with pytest.raises(TN.NestedHardwareError):
        TN.height_planes(prod.doc, [123.0])      # no plane there


@pytest.mark.parametrize("release", [2026, 2025])
def test_an_elevation_refusal_delivers_the_solid_trapeze(tmp, monkeypatch, release):
    """A child without its Center (Elevation) plane makes nest_family REFUSE the
    elevation lock (nothing to lock); the delivery is the solid trapeze, byte
    for byte (hard rule 1)."""
    monkeypatch.setattr(TN, "origin_elevation_reference", lambda doc: None)
    path = os.path.join(tmp, "n", "t.rfa")
    solid = os.path.join(tmp, "s", "t.rfa")
    with _ctx(release):
        rep = F.make_archetype(product="strut_trapeze", nested_hardware=True).write(path)
        F.make_archetype(product="strut_trapeze").write(solid)
    assert os.path.isfile(path) and rep["ok"]
    assert rep["nested_hardware"]["ok"] is False
    assert "center_elevation" in rep["nested_hardware"]["refused"]
    assert any("NESTED HARDWARE REFUSED" in c for c in rep["caveats"])
    assert streams(path) == streams(solid)


def test_an_ambiguous_height_falls_back_to_the_solid_trapeze(tmp, monkeypatch):
    def boom(doc, zs):
        raise TN.NestedHardwareError("probe: two planes at one height")
    monkeypatch.setattr(TN, "height_planes", boom)
    prod = F.make_archetype(product="strut_trapeze", nested_hardware=True)
    assert type(prod) is F.FamilyProduct
    assert any("probe: two planes at one height" in x for x in prod.notes)
    a, b = os.path.join(tmp, "a", "t.rfa"), os.path.join(tmp, "b", "t.rfa")
    prod.write(a)
    F.make_archetype(product="strut_trapeze").write(b)
    assert streams(a) == streams(b)


# ---------------------------------------------------------------------------
# CG8's frame check (#940): fires on synthetic violations
# ---------------------------------------------------------------------------

def _graph(constr_dir=(0.0, 0.0, -1.0), ref_z=1.0, old_z=1.0):
    plane = {"m_freeEnd": [0.0, 0.0, 1.0], "m_bubbleEnd": [1.0, 0.0, 1.0],
             "m_cutVec": [0.0, 1.0, 0.0]}

    def wit(eid, tag):
        return {"m_pWitnessRef": {"ptr_class": "GeomSegInPlaneRef", "value": {
            "m_geomRef": {"m_elemId": eid, "m_geomTag": tag}}}}
    lock = {"m_witnessRefs": [wit(10, 0), wit(20, 7)], "m_constrDir": list(constr_dir),
            "m_refPnts": [[0.5, 0.0, ref_z], [0.5, 0.0, ref_z]],
            "m_oldOrigin": [0.0, 0.0, old_z], "m_flags": 14}
    els = [(10, "RefPlane", plane), (20, "FamilyInstance", {}), (30, "Alignment", lock)]
    inst = {(20, 7): ((0.0, 0.0, 1.0), (0.0, 0.0, 1.0))}
    return [f for f in CL.check_graph(els, instance_planes=inst) if f["rule"] == "CG8"]


def test_cg8_frame_is_silent_on_a_true_elevation_lock():
    assert _graph() == []
    assert _graph(constr_dir=(0.0, 0.0, 1.0)) == []      # either sense of the normal


@pytest.mark.parametrize("kw", [dict(constr_dir=(1.0, 0.0, 0.0)),
                                dict(ref_z=1.25), dict(old_z=0.5)])
def test_cg8_frame_fires_on_a_lock_drawn_off_its_plane(kw):
    f = _graph(**kw)
    assert f and all(x["severity"] == CL.ERROR for x in f)

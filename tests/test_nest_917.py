"""Nesting one generated family inside another (#917).

A born family nests its hardware (a trapeze nests rods, nuts and washers) and
stores each nested family the way a project stores a loaded one.  These tests
pin the smallest working piece: ``rvt.famgen.nest.nest_family`` embeds a
generated family into a generated host ``.rfa`` and places free, unrotated
instances, on 2026 and 2025, read back from the written file -- 0 validator
errors (family mode) and an empty constraint-law report.  Nothing here claims
Revit opens a family with nested instances: no desktop verdict exists (hard
rule 4).
"""
from __future__ import annotations

import math
import os
import shutil
import tempfile
from contextlib import ExitStack, nullcontext

import pytest

from rvt.famgen import constraint_law as CL
from rvt.famgen import factory as F
from rvt.famgen import nest as N
from conftest import context_constants, ladder_constants

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
    native codec singletons (standalone.install_schema, by design); do that
    once before the guard's first snapshot."""
    d = tempfile.mkdtemp(prefix="t917w_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="t917_")
    yield d
    shutil.rmtree(d, True)


def _ctx(release):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return nullcontext()
    return RC.release_build_context(RC._bundled_base_of(release))


def _washer(sid):
    return F.make_generic_model(width_ft=1.5 * IN, depth_ft=1.5 * IN, height_ft=0.125 * IN,
                                name="Square Washer", start_id=sid)


def _nut(sid):
    r = 0.75 * IN / math.sqrt(3.0)
    ring = [[r * math.cos(math.radians(a)), r * math.sin(math.radians(a))]
            for a in (30, 90, 150, 210, 270, 330)]
    return F.make_generic_model(vertices=ring, height_ft=0.5 * IN, name="Hex Nut",
                                start_id=sid)


def _host(path):
    F.make_generic_model(width_ft=2.0, depth_ft=0.5, height_ft=0.2,
                         name="Nest Host").write(path)


def _read(path):
    """{id: (class, header, object)} of unit 0 + the unit count, under the
    file's own release."""
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0)
        out = {}
        for eid, r in recs.get(102, {}).items():
            c = fi.class_name(r.class_id)
            if c in ("Family", "FamilySymbol", "FamilyInstance", "Level"):
                out[eid] = (c, fi.decode(0, eid, 101).value, fi.decode(0, eid, 102).value)
        return out, len(fi.units)


def _latest(path):
    from rvt.adocument import decode_latest
    from rvt.container import open_rvt
    with open_rvt(path) as f:
        return decode_latest(f.inflate("Global/Latest")).value


@pytest.mark.parametrize("release", [2026, 2025])
def test_a_generated_washer_nests_into_a_generated_trapeze(release, tmp):
    host, out = os.path.join(tmp, "trap.rfa"), os.path.join(tmp, "nested.rfa")
    pts = [(-1.0, 0.0, -0.3), (1.0, 0.0, -0.3)]
    with _ctx(release):
        F.make_archetype(product="strut_trapeze").write(host)
        res = N.nest_family(host, out, _washer, pts)
    assert res.ok and len(res.instance_ids) == 2
    ver = res.proofs["verify"]
    assert ver["validate"]["n_errors"] == 0 and ver["constraint_law"] == []
    assert CL.check_file(out) == []
    from rvt.famload import four_registry_census
    reg = four_registry_census(out)
    assert reg["coherent"], reg          # units - 1 == ContentDocuments == ContentTable == FamilyMgr
    E, units = _read(out)
    assert units == 2
    selff = [k for k, (c, _h, o) in E.items() if c == "Family" and not o.get("m_oFamDoc")]
    level = [k for k, (c, _h, _o) in E.items() if c == "Level"]
    assert len(selff) == 1 and len(level) == 1
    got = []
    for iid in res.instance_ids:
        c, h, o = E[iid]
        ii = o["m_pInstanceInfo"]["value"]
        assert c == "FamilyInstance"
        assert ii["m_symbolId"] == o["m_masterSymbolId"] == res.symbol_id
        assert o["m_famId"] == selff[0] and o["m_assocLevelId"] == level[0]
        assert o["m_hostId"] == -1 and not o["m_workPlaneBased"]
        assert h["m_parents"]["value"]["m_regenOnly"] == [res.nested_family_id]
        got.append(tuple(ii["m_Trf"]["m_or"]))
    assert got == pts
    # the family-host flavour of the loaded layer (born hosts: 10 / 2472)
    assert E[res.nested_family_id][1]["m_abFlags4Bytes"] == N.NESTED_FAMILY_HDR_FLAGS
    assert E[res.symbol_id][1]["m_abFlags4Bytes"] == N.NESTED_SYMBOL_HDR_FLAGS
    assert E[res.nested_family_id][2]["m_oFamDoc"]["value"]["m_contentDocGUID"]


def test_two_families_nest_one_after_the_other(tmp):
    host = os.path.join(tmp, "h.rfa")
    _host(host)
    a = N.nest_family(host, os.path.join(tmp, "a.rfa"), _washer, [(0.5, 0.0, 0.2)])
    b = N.nest_family(a.out_path, os.path.join(tmp, "b.rfa"), _nut,
                      [(0.5, 0.0, 0.21), (-0.5, 0.0, 0.21)])
    assert a.ok and b.ok and b.proofs["verify"]["units"] == 3
    assert min(b.instance_ids) > max(a.instance_ids)
    from rvt.famload import four_registry_census
    assert four_registry_census(b.out_path)["coherent"]
    assert CL.check_file(b.out_path) == []


def test_nested_symbols_stay_out_of_the_element_tracking_data(tmp):
    """Born family hosts never track their nested symbols there (0 / 313)."""
    host, out = os.path.join(tmp, "h.rfa"), os.path.join(tmp, "n.rfa")
    _host(host)
    res = N.nest_family(host, out, _washer, [(0.0, 0.0, 0.0)])
    lv = _latest(out)
    mgr = lv["m_pAppInfoManager"]["value"]["m_appInfoArr"]
    etd = next((x["value"] for x in mgr if x and x.get("ptr_class") == "ElementTrackingData"), None)
    tracked = {i for row in ((etd or {}).get("m_symbols") or []) for i in row.get("m_elemIdSet") or []}
    assert res.symbol_id not in tracked
    fm = next(x["value"] for x in mgr if x and x.get("ptr_class") == "FamilyMgr")
    assert any(res.proofs["load"]["plan"]["content_guid"] in e["m_familyDocGUIDs"]
               for e in fm["m_arrLoadedFamilyInfo"])


def test_the_written_host_keeps_its_own_identity(tmp):
    from rvt import stream_encoders as se
    from rvt.container import open_rvt
    host, out = os.path.join(tmp, "h.rfa"), os.path.join(tmp, "n.rfa")
    _host(host)
    N.nest_family(host, out, _washer, [(0.0, 0.0, 0.0)])
    with open_rvt(host) as f:
        before = se.decode_basic_file_info(f.raw("BasicFileInfo"))
    with open_rvt(out) as f:
        after = se.decode_basic_file_info(f.raw("BasicFileInfo"))
    assert after["username"] == before["username"]
    assert after["unique_document_guid"] == before["unique_document_guid"]
    assert after["last_save_path"] == "n.rfa"
    assert F.provenance_scan(out)["ok"]


def test_nesting_is_deterministic(tmp):
    from rvt.container import open_rvt
    host = os.path.join(tmp, "h.rfa")
    _host(host)
    streams = []
    for i in range(2):
        p = os.path.join(tmp, f"d{i}.rfa")
        N.nest_family(host, p, _washer, [(0.25, 0.0, 0.0)])
        with open_rvt(p) as f:
            streams.append({s.name: f.raw(s.name) for s in f.streams()
                            if s.name != "BasicFileInfo"})      # carries its own file name
    assert streams[0] == streams[1]


@pytest.mark.parametrize("points, why", [
    ([], "empty"),
    ([(0.0, 0.0)], "three finite"),
    ([(0.0, float("nan"), 0.0)], "three finite"),
    ("abc", "list"),
    ([(0, 0, 0)] * (N.MAX_INSTANCES + 1), "cap"),
])
def test_bad_points_are_refused_before_anything_is_written(points, why, tmp):
    host, out = os.path.join(tmp, "h.rfa"), os.path.join(tmp, "n.rfa")
    _host(host)
    with pytest.raises(N.NestError, match=why):
        N.nest_family(host, out, _washer, points)
    assert not os.path.exists(out)


def test_a_host_that_is_not_an_rfa_or_the_output_itself_is_refused(tmp):
    host = os.path.join(tmp, "h.rfa")
    _host(host)
    with pytest.raises(N.NestError, match="existing .rfa"):
        N.nest_family(os.path.join(tmp, "missing.rfa"), os.path.join(tmp, "o.rfa"),
                      _washer, [(0, 0, 0)])
    with pytest.raises(N.NestError, match="overwrite"):
        N.nest_family(host, host, _washer, [(0, 0, 0)])
    with pytest.raises(N.NestError, match=".rfa path"):
        N.nest_family(host, os.path.join(tmp, "o.rvt"), _washer, [(0, 0, 0)])


def test_a_child_whose_ids_collide_with_the_host_is_refused(tmp):
    host, out = os.path.join(tmp, "h.rfa"), os.path.join(tmp, "n.rfa")
    _host(host)
    with pytest.raises(N.NestError, match="start_id"):
        N.nest_family(host, out, _washer(1000), [(0, 0, 0)])
    assert not os.path.exists(out)


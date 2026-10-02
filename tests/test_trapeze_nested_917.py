"""The strut trapeze with NESTED washers and nuts (#917 DONE 5) and the nested
type table's real-types-only form in a family host (#917 DONE 1).

``make_archetype(product="strut_trapeze", nested_hardware=True)`` builds the
trapeze without its washer / nut solids and, when written, nests our own
generated square-washer and hex-nut families into it: per tier and rod a washer
and nut below the channel and on the lips, each instance locked by Center
(Left/Right) to its Rod Inset plane and by Center (Front/Back) to the origin
plane, the host's Washer Size / Washer Thickness / Nut Across Flats associated
to the children's instance parameters.  Pinned here on 2026 and 2025, read back
from the written file: 0 validator errors, an empty constraint law with EVERY
nested lock judged by CG8, coherent registries, the family end record, real
types only in every nested type table, determinism, and the solid trapeze
delivered (with the reason) when nesting fails.  The default stays the solid
trapeze, byte for byte.  Nothing here claims Revit behaviour: no desktop verdict
exists for nested families (hard rule 4).
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

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN = 1.0 / 12.0


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.fixture(scope="module", autouse=True)
def _warm_native_codecs():
    """The first write in a process installs the bundled schema and seeds the
    native codec singletons; do that once before the guard's first snapshot."""
    d = tempfile.mkdtemp(prefix="t917tw_")
    try:
        F.make_archetype(product="wireway").write(os.path.join(d, "w.rfa"))
    finally:
        shutil.rmtree(d, True)


@pytest.fixture
def tmp():
    d = tempfile.mkdtemp(prefix="t917t_")
    yield d
    shutil.rmtree(d, True)


def _ctx(release):
    from rvt.frontdoor import release_ctx as RC
    if release == RC.native_release():
        return nullcontext()
    return RC.release_build_context(RC._bundled_base_of(release))


def _read(path, classes):
    """{class: {id: (header, object)}} for the host unit's elements of ``classes``."""
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    out = {c: {} for c in classes}
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        for c in classes:
            for i in fi.ids_of_class(0, c):
                out[c][i] = (fi.decode(0, i, 101).value, fi.decode(0, i, 102).value)
    return out


def _judged(path):
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


@pytest.fixture(scope="module", params=[2026, 2025])
def nested(request):
    """One nested trapeze per release: (release, product, report, path)."""
    d = tempfile.mkdtemp(prefix=f"t917n{request.param}_")
    path = os.path.join(d, "trapeze.rfa")
    with _ctx(request.param):
        prod = F.make_archetype(product="strut_trapeze", nested_hardware=True)
        rep = prod.write(path)
    yield request.param, prod, rep, path
    shutil.rmtree(d, True)


# ---------------------------------------------------------------------------
# DONE 5: the nested trapeze
# ---------------------------------------------------------------------------

def test_nested_trapeze_writes_valid_and_lawful(nested):
    release, prod, rep, path = nested
    assert rep["ok"], rep.get("validate")
    nh = rep["nested_hardware"]
    assert nh["ok"], nh
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    assert rep["provenance"]["ok"], rep["provenance"]["suspects"]
    from rvt.versions import detect_release
    assert int(detect_release(path)) == release
    w, n = nh["washer"], nh["nut"]
    # 2 tiers x 2 rods x (below + above)
    assert len(w["instance_ids"]) == 8 and len(n["instance_ids"]) == 8
    assert len(w["lock_ids"]) == 16 and len(n["lock_ids"]) == 16
    for r in (w, n):
        v = r["proofs"]["verify"]
        assert v["ok"] and v["registries_coherent"] and v["end_record_is_constant"]
        assert v["constraint_law"] == [] and v["validate"]["n_errors"] == 0
    # the final file: the law is clean and EVERY nested lock is judged by CG8
    assert CL.check_file(path) == []
    judged = _judged(path)
    want = {(i, c) for i in w["instance_ids"] + n["instance_ids"] for c in (1, 4)}
    assert set(judged) == want
    from rvt.famload import four_registry_census
    reg = four_registry_census(path)
    assert reg["coherent"]
    notes = " ".join(rep["family"]["notes"])
    assert "NESTED HARDWARE" in notes and "do NOT follow the host's height drives" in notes
    assert "hard rule 4" in notes


def test_nested_locks_target_the_rod_inset_and_origin_planes(nested):
    _release, prod, rep, path = nested
    nh = rep["nested_hardware"]
    lo, hi = prod.rod_planes
    fb = prod.fb_plane
    E = _read(path, ["Alignment", "FamilyInstance", "RefPlane"])
    planes = E["RefPlane"]
    # the lock targets ARE the Rod Inset follow planes (x = -+ rod spacing / 2)
    # and the origin Center (Front/Back)
    g = AR._trapeze_geometry(prod.hardware_values)
    for pid, x in ((lo, -g["spacing"] / 2.0), (hi, g["spacing"] / 2.0)):
        o = planes[pid][1]
        assert abs(o["m_freeEnd"][0] - x) < 1e-9 and abs(o["m_bubbleEnd"][0] - x) < 1e-9
    assert planes[fb][1]["m_definesOrigin"] and planes[fb][1]["m_refName"] == 4
    inst = {i: E["FamilyInstance"][i][1] for i in
            nh["washer"]["instance_ids"] + nh["nut"]["instance_ids"]}
    seen = set()
    for lid in nh["washer"]["lock_ids"] + nh["nut"]["lock_ids"]:
        o = E["Alignment"][lid][1]
        wp, wi = (w["m_pWitnessRef"]["value"]["m_geomRef"] for w in o["m_witnessRefs"])
        x = inst[wi["m_elemId"]]["m_instOrigin"][0]
        if wi["m_geomTag"] == 1:
            assert wp["m_elemId"] == (lo if x < 0 else hi)
        else:
            assert wi["m_geomTag"] == 4 and wp["m_elemId"] == fb
        seen.add((wi["m_elemId"], wi["m_geomTag"]))
    assert len(seen) == 32


def test_hardware_sits_where_the_solid_version_draws_it():
    """Every nested origin = the solid part's centre at its bottom face."""
    res = AR.resolve("strut_trapeze", {})
    v = dict(res.values)
    solid = {}
    for p in AR._strut_trapeze(v):
        if TN.is_hardware(p["name"]):
            solid.setdefault("washer" if " washer " in p["name"] else "nut", []).append(
                (round(p["center"][0], 9), round(p["center"][1], 9), round(p["base_z_ft"], 9)))
    pos = TN.hardware_positions(v)
    for k in ("washer", "nut"):
        got = [tuple(round(c, 9) for c in o) for o, _s in pos[k]]
        assert sorted(got) == sorted(solid[k])
        for (o, side) in pos[k]:
            assert (side == "lo") == (o[0] < 0)


def test_associations_and_values(nested):
    _release, prod, rep, path = nested
    nh = rep["nested_hardware"]
    w = {a["host"]: a for a in nh["washer"]["associations"]}
    n = {a["host"]: a for a in nh["nut"]["associations"]}
    assert set(w) == {"Washer Size", "Washer Thickness"} and set(n) == {"Nut Across Flats"}
    E = _read(path, ["FamilyInstance"])
    g = AR._trapeze_geometry(prod.hardware_values)
    want = {w["Washer Size"]["nested_twin"]: float(prod.hardware_values["washer_size_in"]) * IN,
            w["Washer Thickness"]["nested_twin"]: g["wt"]}
    for iid in nh["washer"]["instance_ids"]:
        o = E["FamilyInstance"][iid][1]
        cell = o["m_cellList"]["value"]["m_cells"][0]
        assert cell["ptr_class"] == "FamilyParametrizedElemParamsCell"
        assert len(cell["value"]["m_paramDrivenData"]) == 2
        rows = {r["m_paramId"]: r for r in o["m_pInstParams"]["value"]["m_params"]}
        for twin, val in want.items():
            assert abs(rows[twin]["m_value"] - val) < 1e-9
    twin = n["Nut Across Flats"]["nested_twin"]
    for iid in nh["nut"]["instance_ids"]:
        rows = {r["m_paramId"]: r for r in
                E["FamilyInstance"][iid][1]["m_pInstParams"]["value"]["m_params"]}
        assert abs(rows[twin]["m_value"] - g["nut_af"]) < 1e-9


def labels_of(prod, cap):
    pid = prod.doc.params[cap].elem_id
    return sum(1 for e in prod.doc.elements if isinstance(e.obj, dict)
               for seg in (e.obj.get("m_ArrSegInfo") or [])
               if isinstance(seg, dict) and seg.get("m_paramId") == pid)


def test_children_are_our_own_driven_families(tmp):
    """The washer's size and thickness and the nut's height are REAL drives
    (labelled dimensions on locked planes); each child writes VALID with an
    empty constraint law on its own.  The nut's across-flats is a value only."""
    wsh = TN.make_washer(1000, size_ft=1.625 * IN, thickness_ft=0.25 * IN)
    nut = TN.make_hex_nut(1000, across_flats_ft=0.5625 * IN, height_ft=0.328125 * IN)
    for prod, labelled in ((wsh, {"Washer Size", "Washer Thickness"}), (nut, {"Nut Height"})):
        p = os.path.join(tmp, prod.file_stem + ".rfa")
        r = prod.write(p)
        assert r["ok"], r.get("validate")
        assert CL.check_file(p) == []
        assert not [x for x in prod.doc.notes if "not wired" in x]
        # each drive parameter LABELS dimensions (segment m_paramId) and is an
        # INSTANCE parameter (born hosts associate nested instance params only)
        labels = {}
        for e in prod.doc.elements:
            for seg in (e.obj.get("m_ArrSegInfo") or []) if isinstance(e.obj, dict) else []:
                pid = seg.get("m_paramId") if isinstance(seg, dict) else None
                if isinstance(pid, int) and pid > 0:
                    labels[pid] = labels.get(pid, 0) + 1
        fp = prod.doc.self_family.obj["m_familyParams"]["value"]["m_params"]
        for cap in labelled:
            pe = prod.doc.params[cap]
            assert labels.get(pe.elem_id, 0) >= 1, cap
            assert [r for r in fp if r["m_paramId"] == pe.elem_id][0]["m_instance"]
    # Washer Size labels BOTH plan widths (x and y)
    assert labels_of(wsh, "Washer Size") == 2
    # the nut's across-flats: an instance parameter, honestly NOT a drive
    assert "Nut Across Flats" in nut.doc.params and labels_of(nut, "Nut Across Flats") == 0
    assert any("value only" in x for x in nut.doc.notes)


def test_nested_trapeze_is_deterministic(nested, tmp):
    release, _prod, _rep, path = nested
    other = os.path.join(tmp, "trapeze.rfa")
    with _ctx(release):
        F.make_archetype(product="strut_trapeze", nested_hardware=True).write(other)
    assert streams(path) == streams(other)


# ---------------------------------------------------------------------------
# opt-in: the default is unchanged; refusals deliver the solid trapeze
# ---------------------------------------------------------------------------

def test_default_is_the_solid_trapeze_byte_for_byte(tmp):
    a, b = os.path.join(tmp, "a", "t.rfa"), os.path.join(tmp, "b", "t.rfa")
    pa = F.make_archetype(product="strut_trapeze")
    pb = F.make_archetype(product="strut_trapeze", nested_hardware=False)
    assert type(pa) is F.FamilyProduct and type(pb) is F.FamilyProduct
    pa.write(a)
    pb.write(b)
    assert streams(a) == streams(b)
    assert len(pa.forms) == len(AR._strut_trapeze(dict(AR.resolve("strut_trapeze", {}).values)))


def test_stripped_host_keeps_rods_and_planes():
    p = F.make_archetype(product="strut_trapeze", nested_hardware=True)
    assert isinstance(p, TN.NestedHardwareProduct)
    v = dict(AR.resolve("strut_trapeze", {}).values)
    all_parts = AR._strut_trapeze(v)
    kept = [q for q in all_parts if not TN.is_hardware(q["name"])]
    assert len(p.forms) == len(kept) < len(all_parts)
    assert not [x for x in p.doc.notes if "not wired" in x]
    fol = p.drives[0]["follow"]
    assert fol["followers"] == 2 and fol["rigid_pairs"] == 0      # the two rods only
    assert set(fol["planes"]) == set(p.rod_planes)


def test_refused_nesting_delivers_the_solid_trapeze(tmp, monkeypatch):
    def boom(*a, **k):
        raise N.NestError("probe refusal")
    monkeypatch.setattr(N, "nest_family", boom)
    path = os.path.join(tmp, "t.rfa")
    prod = F.make_archetype(product="strut_trapeze", nested_hardware=True)
    rep = prod.write(path)
    assert os.path.isfile(path) and rep["ok"]
    assert rep["nested_hardware"] == {"ok": False, "refused": "NestError: probe refusal"}
    assert any("NESTED HARDWARE REFUSED" in c for c in rep["caveats"])
    # what was delivered IS the solid trapeze
    solid = os.path.join(tmp, "s", "t.rfa")
    F.make_archetype(product="strut_trapeze").write(solid)
    assert streams(path) == streams(solid)
    assert not [f for f in os.listdir(tmp) if f.endswith(".tmp")]


def test_a_crashing_read_back_is_stamped_never_raised(tmp, monkeypatch):
    """#939 review: once both nests succeed the file is at ``path``; a read-back
    that crashes is recorded on the report, not raised past delivery."""
    from rvt.frontdoor import standalone as SA
    path = os.path.join(tmp, "t.rfa")
    real = SA._read_back_checks

    def boom(rep, p, *a, **k):                      # only the final delivery's read-back
        if os.path.abspath(p) == os.path.abspath(path):
            raise KeyError("reader crashed")
        return real(rep, p, *a, **k)
    monkeypatch.setattr(SA, "_read_back_checks", boom)
    rep = F.make_archetype(product="strut_trapeze", nested_hardware=True).write(path)
    assert os.path.isfile(path)
    assert rep["ok"] is False and "KeyError" in rep["read_back_error"]
    assert any("read-back checks crashed" in c for c in rep["caveats"])


def test_nested_hardware_on_another_product_is_a_note(tmp):
    a, b = os.path.join(tmp, "a", "w.rfa"), os.path.join(tmp, "b", "w.rfa")
    pa = F.make_archetype(product="wireway", nested_hardware=True)
    pb = F.make_archetype(product="wireway")
    assert type(pa) is F.FamilyProduct
    assert any("strut trapeze only" in x for x in pa.notes)
    pa.write(a)
    pb.write(b)
    assert streams(a) == streams(b)


# ---------------------------------------------------------------------------
# DONE 1: real types only in a family host's nested type table
# ---------------------------------------------------------------------------

def test_nested_type_tables_carry_real_types_only(nested):
    _release, _prod, rep, path = nested
    nh = rep["nested_hardware"]
    E = _read(path, ["Family"])
    for r in (nh["washer"], nh["nut"]):
        ftt = E["Family"][r["nested_family_id"]][1]["m_pFamilyTypes"]["value"]
        names = [p["name"] for p in ftt["m_pairs"]]
        assert names == [r["family_name"]] and ftt["m_idx"] == 0
        assert all(str(n).strip() for n in names)


def test_nested_type_table_keeps_the_current_type():
    blank = {"name": " ", "params": {}}
    a, b = {"name": "A", "params": {}}, {"name": "B", "params": {}}
    t = N.nested_type_table({"m_pairs": [blank, a, b], "m_idx": 2})
    assert [p["name"] for p in t["m_pairs"]] == ["A", "B"] and t["m_idx"] == 1
    t = N.nested_type_table({"m_pairs": [blank, a], "m_idx": 0})
    assert [p["name"] for p in t["m_pairs"]] == ["A"] and t["m_idx"] == 0
    with pytest.raises(N.NestError):
        N.nested_type_table({"m_pairs": [blank], "m_idx": 0})


def test_project_loader_keeps_its_leading_blank_row(tmp):
    """The project path is untouched: a loaded family in a PROJECT still gets
    the blank ' ' current-values row (its own law, #917 changes only the
    family-host flavour)."""
    from rvt.famgen import loader as L
    base = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
    if not os.path.isfile(base):
        pytest.skip("bundled base absent")
    out = os.path.join(tmp, "p.rvt")
    res = L.load_family_into_project(base, out, place=False)
    assert res.ok
    from rvt.families import FamilyIndex
    from rvt.global_framing import enter_own_release
    with ExitStack() as st:
        enter_own_release(st, out)
        fi = FamilyIndex(out)
        o = fi.decode(0, res.plan.host_family_id, 102).value
    ftt = o["m_pFamilyTypes"]["value"]
    assert ftt["m_pairs"][0]["name"] == " " and ftt["m_idx"] >= 1

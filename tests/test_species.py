"""species stream tests -- the registration forensics, the birthright v3
HOSTSYM lane, and the staged species cells (batch 54).

Three layers, no viewer and no heavy builds:

1. the v3 lane pure contracts (strip / host-family table law / pipeline
   dispatch / the opt-in loader patch) on toy documents;
2. pins on the MEASURED forensic record
   (``experiments/species/cd_forensics.json``);
3. pins on the built probes + staged batch
   (``experiments/species/accounting.json``, ``batch_54.json``) --
   byte-identity, single-variable claims, species census, zero-donor.

Layers 2-3 skip when the evidence has not been generated (fresh clone).
"""
import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

from rvt.famgen import birthright as BR                          # noqa: E402

FORENSICS = os.path.join(ROOT, "experiments", "species",
                         "cd_forensics.json")
ACCT = os.path.join(ROOT, "experiments", "species", "accounting.json")
PROBES = os.path.join(ROOT, "experiments", "species", "probes.json")
BATCH = os.path.join(ROOT, "experiments", "acceptance", "batch_54.json")
BIRTH_SPEC = os.path.join(ROOT, "experiments", "birthright",
                          "template_birth.json")


def _j(path):
    with open(path) as fh:
        return json.load(fh)


def _md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ===========================================================================
# toy documents (test_birthright's duck shape)
# ===========================================================================

class _El:
    def __init__(self, eid, cls, obj=None, header=None, rep=None, owner=-1):
        self.elem_id = eid
        self.class_name = cls
        self.obj = obj if obj is not None else {}
        self.header = header if header is not None else {}
        self.rep = rep
        self.owner_id = owner
        self.kind = ""


class _Doc:
    def __init__(self, els, sf, types, current_type, finalized=True):
        self.elements = els
        self.self_family = sf
        self.types = types
        self.current_type = current_type
        self.finalized = finalized


def _doc_with_baked(pairs, idx, types, current_type, finalized=True):
    sf = _El(100, "Family", obj={
        "m_pFamilyTypes": {"ptr_class": "FamilyTypeTable", "pid": -1,
                           "value": {"m_idx": idx,
                                     "m_pairs": [{"name": n} for n in
                                                 pairs]}}})
    return _Doc([sf], sf, types, current_type, finalized)


# ===========================================================================
# 1. the HOSTSYM lane -- pure contracts
# ===========================================================================

class TestHostSymbolLaw:
    def test_strip_blank_pair(self):
        d = _doc_with_baked([" ", "225A"], 1,
                            [(" ", {"a": 1}), ("225A", {"a": 2})], 1)
        rep = BR.apply_host_symbol_law(d)
        assert rep["applied"] is True
        assert rep["stripped_blank_pairs"] == 1
        assert d.types == [("225A", {"a": 2})]
        assert d.current_type == 0
        # the BAKED unit table is untouched (blank-pair-first kept)
        pairs = [p["name"] for p in d.self_family.obj["m_pFamilyTypes"]
                 ["value"]["m_pairs"]]
        assert pairs == [" ", "225A"]
        assert rep["unit_table_pairs"] == [" ", "225A"]
        assert rep["unit_table_idx"] == 1

    def test_noop_without_blank(self):
        d = _doc_with_baked([" ", "225A"], 1, [("225A", {})], 0)
        rep = BR.apply_host_symbol_law(d)
        assert rep["applied"] is False
        assert d.types == [("225A", {})]

    def test_refuses_unfinalized(self):
        d = _doc_with_baked([" ", "225A"], 1, [(" ", {}), ("225A", {})], 1,
                            finalized=False)
        with pytest.raises(ValueError, match="not finalized"):
            BR.apply_host_symbol_law(d)

    def test_refuses_blank_current(self):
        d = _doc_with_baked([" ", "225A"], 1, [(" ", {}), ("225A", {})], 0)
        with pytest.raises(ValueError, match="blank pair"):
            BR.apply_host_symbol_law(d)

    def test_refuses_unbaked_blank_first(self):
        d = _doc_with_baked(["225A"], 0, [(" ", {}), ("225A", {})], 1)
        with pytest.raises(ValueError, match="blank-pair-first"):
            BR.apply_host_symbol_law(d)

    def test_refuses_baked_idx_on_blank(self):
        d = _doc_with_baked([" ", "225A"], 0, [(" ", {}), ("225A", {})], 1)
        with pytest.raises(ValueError, match="REAL pair"):
            BR.apply_host_symbol_law(d)

    def test_strip_is_subtractive_only(self):
        """Zero-donor invariant: the lane never ADDS a value -- the kept
        names are a subset of what the document already carried."""
        types = [(" ", {"x": 1}), ("A", {"x": 2}), ("B", {"x": 3})]
        d = _doc_with_baked([" ", "A", "B"], 1, list(types), 1)
        before = {n for n, _v in types}
        BR.apply_host_symbol_law(d)
        assert {n for n, _v in d.types} <= before


class TestHostFamilyTableLaw:
    def test_drops_copied_blank_rows(self):
        el = _El(1, "Family", obj={
            "m_pFamilyTypes": {"ptr_class": "FamilyTypeTable", "pid": -1,
                               "value": {"m_idx": 1, "m_pairs": [
                                   {"name": " "}, {"name": " "},
                                   {"name": "225A"}]}}})
        rep = BR.apply_host_family_table_law(el)
        assert rep["applied"] is True
        assert rep["pairs"] == [" ", "225A"]
        assert rep["m_idx"] == 1

    def test_single_blank_row_untouched(self):
        el = _El(1, "Family", obj={
            "m_pFamilyTypes": {"ptr_class": "FamilyTypeTable", "pid": -1,
                               "value": {"m_idx": 0,
                                         "m_pairs": [{"name": " "}]}}})
        rep = BR.apply_host_family_table_law(el)
        assert rep["applied"] is False
        assert rep["pairs"] == [" "]
        assert rep["m_idx"] == 0

    def test_native_shape_untouched(self):
        el = _El(1, "Family", obj={
            "m_pFamilyTypes": {"ptr_class": "FamilyTypeTable", "pid": -1,
                               "value": {"m_idx": 1, "m_pairs": [
                                   {"name": " "}, {"name": "Notch"}]}}})
        rep = BR.apply_host_family_table_law(el)
        assert rep["applied"] is False
        assert rep["pairs"] == [" ", "Notch"]


class TestV3Dispatch:
    def test_v3_lanes_constant(self):
        assert BR._V3_LANES == BR._V2_LANES + ("hostsym",)

    @pytest.mark.skipif(not os.path.isfile(BIRTH_SPEC),
                        reason="mined spec absent")
    def test_enabled_rejects_unknown_version(self):
        # version=4 exists since the identity stream (BORN IDENTITY lane);
        # the unknown-version contract now starts at 5
        with pytest.raises(ValueError, match="unknown version"):
            with BR.enabled(BIRTH_SPEC, version=5):
                pass

    @pytest.mark.skipif(not os.path.isfile(BIRTH_SPEC),
                        reason="mined spec absent")
    def test_enabled_v3_patches_and_restores_loader(self):
        from rvt.famgen import loader as L
        orig = L.author_host_family
        with BR.enabled(BIRTH_SPEC, version=3) as ctx:
            assert L.author_host_family is not orig
            assert ctx["version"] == 3
            assert ctx["hostsym_loader"] == []
        assert L.author_host_family is orig

    @pytest.mark.skipif(not os.path.isfile(BIRTH_SPEC),
                        reason="mined spec absent")
    def test_enabled_v2_default_leaves_loader_alone(self):
        from rvt.famgen import loader as L
        orig = L.author_host_family
        with BR.enabled(BIRTH_SPEC) as ctx:
            assert L.author_host_family is orig
            assert ctx["version"] == 2
        assert L.author_host_family is orig


# ===========================================================================
# 2. the forensic record, pinned
# ===========================================================================

@pytest.mark.skipif(not os.path.isfile(FORENSICS),
                    reason="forensics not run")
class TestForensics:
    @pytest.fixture(scope="class")
    def f(self):
        return _j(FORENSICS)

    def test_cd_framing_exonerated(self, f):
        assert f["cd_stream"]["framing_identical"] is True
        assert f["cd_stream"]["pass"]["entries"] == 1
        assert f["cd_stream"]["fail"]["entries"] == 1
        assert f["cd_stream"]["base"]["entries"] == 0

    def test_inline_adoc_form_identical(self, f):
        """The charter-hypothesized standalone registered-ADocument form
        is FALSIFIED by measurement: the PASS ships the same authored
        embedded form as the FAIL."""
        a = f["inline_adoc"]
        assert a["form_identical_modulo_identity"] is True
        for side in ("pass", "fail"):
            s = a[side]
            assert s["elem_table_populated"] is True
            assert s["identity_equals_unit_guid"] is True
            assert s["m_pHostDocument"] == {"weakref": 1}
            assert s["content_rec_set"] == 0
            assert s["appinfo_populated"] == 0
            assert s["stored_by_revit_build"] == []

    def test_host_symbol_table_is_the_delta(self, f):
        hr = f["host_registration"]
        assert hr["pass"]["blank_named_surrogates"] == 0
        assert hr["fail"]["blank_named_surrogates"] == 1
        assert hr["pass"]["instance_bound_pair_name"].strip()
        assert not hr["fail"]["instance_bound_pair_name"].strip()
        assert hr["pass"]["symbol_pairs"] == ["0610 x 0160mm"]
        assert hr["fail"]["symbol_pairs"] == [" ", "225A MLO 42ckt"]

    def test_native_host_family_law(self, f):
        law = f["host_registration"]["native_host_family_law"]
        assert law["host_family_rows"] > 0
        assert law["rows_with_more_than_one_blank"] == 0
        assert law["rows_with_midx_on_blank_despite_real_pairs"] == 0

    def test_demo_v8_double_blank_leak(self, f):
        leak = f.get("famgen_loader_leak_demo_v8")
        if not leak:
            pytest.skip("DEMO v8 not on disk")
        for t in leak["host_family_type_tables"]:
            assert t["pairs"][:2] == [" ", " "]
            assert t["m_idx"] == 1              # POINTS AT A BLANK ROW

    def test_roster_gap(self, f):
        assert f["unit_internal"]["roster_gap_pass_minus_fail"] == 268

    def test_self_family_form_equal(self, f):
        sf = f["unit_internal"]["self_family"]
        assert sf["obj_key_set_delta"] == []
        assert sf["hdr_key_set_delta"] == []
        assert sf["m_bShared"] == {"pass": True, "fail": True}

    def test_delta_list_rank1_is_hostsym(self, f):
        r1 = f["species_delta_list"][0]
        assert r1["rank"] == 1
        assert "host symbol table" in r1["surface"]
        assert r1["authorable"] is True

    def test_id_policy_exonerated(self, f):
        assert any(d.get("surface") == "id policy"
                   and d.get("rank") == "exonerated"
                   for d in f["species_delta_list"])


# ===========================================================================
# 3. the built probes + the staged batch, pinned
# ===========================================================================

@pytest.mark.skipif(not os.path.isfile(ACCT), reason="probes not built")
class TestBuiltProbes:
    @pytest.fixture(scope="class")
    def a(self):
        return _j(ACCT)

    def test_all_gates_green(self, a):
        for n in ("T1uG", "TB0g", "BX_v3", "DEMO_250v_room_v9"):
            assert a["gates"][n]["gates_ok"] is True, n
        assert a["errors"] == {}

    def test_t1ug_byte_identity(self, a):
        bi = a["built"]["T1uG"]["byte_identity"]
        assert bi["target_file"] == "experiments/unionrec/T1u.rvt"
        assert bi["target_guid"] == "7218d5e4-424d-4914-9904-e7bcc1794fd7"
        assert all(bi["segments_byte_identical"].values())

    def test_t1ug_adoc_matches_t1u(self, a):
        d = a["built"]["T1uG"]["adoc_value_diff_vs_t1u"]
        assert d["all_within_history_identity"] is True

    def test_tb0g_byte_identity_and_deviation(self, a):
        b = a["built"]["TB0g"]
        bi = b["byte_identity"]
        assert bi["target_file"] == "experiments/rftprobe/TB0r.rvt"
        assert bi["target_guid"] == "54c84546-ee5d-4d52-a60e-12b37ecbbbaa"
        assert all(bi["segments_byte_identical"].values())
        assert "438" in b["deviation"]["why"]        # rac watermark reason

    def test_tb0g_embedded_species_unit_table_empty(self, a):
        """A measured species datum: the embedded-born famdoc carries an
        EMPTY unit-side type table (types live host-side); the standalone
        species and ours carry the blank-pair-first table in-unit."""
        u = a["built"]["TB0g"]["species"]["units"][0]
        assert u["unit_type_table"]["pairs"] == []
        t1 = a["built"]["T1uG"]["species"]["units"][0]
        assert t1["unit_type_table"]["pairs"][0] == " "

    def test_bx_v3_single_variable_vs_sc1(self, a):
        b = a["built"]["BX_v3"]
        assert b["birthright"]["version"] == 3
        assert b["birthright"]["hostsym"]["applied"] is True
        assert b["load"]["type_names"] == ["225A MLO 42ckt"]
        sp = b["species"]
        assert sp["species_ok"] is True
        assert sp["host_symbol_pairs"] == ["225A MLO 42ckt"]
        assert sp["blank_named_surrogates"] == 0
        assert sp["instances_bound"][0]["pair_name"] == "225A MLO 42ckt"
        assert sp["four_surface"]["self_contained"] is True
        assert sp["four_surface"]["host_resident_total"] == 0
        # the unit-side blank-pair-first law KEPT
        assert sp["units"][0]["unit_type_table"]["pairs"] == \
            [" ", "225A MLO 42ckt"]
        assert sp["units"][0]["unit_type_table"]["m_idx"] == 1

    def test_bx_v3_same_recipe_as_sc1(self, a):
        """Zero-donor + single-variable: BX_v3 runs SC1's exact spec +
        binds (recorded sha equality) -- only the hostsym lane differs."""
        b = a["built"]["BX_v3"]
        sc_acct = os.path.join(ROOT, "experiments", "selfcontained",
                               "accounting.json")
        if not os.path.isfile(sc_acct):
            pytest.skip("selfcontained accounting absent")
        sc = _j(sc_acct)["built"]["SC1"]
        assert b["birth_spec_sha256"] == sc["birth_spec_sha256"]
        assert b["binds"] == sc["binds"]
        assert all(isinstance(v, int) for v in b["binds"].values())

    def test_demo_v9(self, a):
        v9 = a["built"]["DEMO_250v_room_v9"]
        assert v9["n_families"] == 6
        assert v9["n_instances"] == 6
        loader = v9["hostsym_loader"]
        assert len(loader) == 6
        assert all(x["applied"] and x["dropped_blank_rows"] == 1
                   for x in loader)
        sp = v9["species"]
        assert sp["species_ok"] is True
        for t in sp["host_family_type_tables"]:
            assert t["pairs"] == [" ", "225A MLO 42ckt"]
            assert t["m_idx"] == 1
        assert sp["blank_named_surrogates"] == 0
        assert len(sp["units"]) == 6

    def test_probes_json_manifest(self, a):
        p = _j(PROBES)
        names = [x["probe"] for x in p["probes"]]
        assert names == ["T1uG", "TB0g", "BX_v3", "DEMO_250v_room_v9"]
        for x in p["probes"]:
            assert x["base"] == "experiments/genesis/subst_k4/compose/" \
                                "G_ABPD.rvt"
            assert x["gates_ok"] is True
        assert p["reading_the_matrix"]["reading_order"] == names
        assert len(p["reading_the_matrix"]["pre_committed"]) >= 6


@pytest.mark.skipif(not os.path.isfile(BATCH), reason="batch not staged")
class TestStagedBatch:
    @pytest.fixture(scope="class")
    def m(self):
        return _j(BATCH)

    def test_shape(self, m):
        assert m["batch"] == 54
        assert m["control_count"] == 1
        assert m["reading_order"] == [
            "CTRL_G_ABPD_b54.rvt", "T1uG.rvt", "TB0g.rvt", "BX_v3.rvt",
            "DEMO_250v_room_v9.rvt"]
        kinds = [e["kind"] for e in m["entries"]]
        assert kinds == ["control", "probe", "probe", "probe", "probe"]

    def test_staged_md5s_match_built(self, m):
        a = _j(ACCT)
        by_name = {os.path.basename(e["file"]): e for e in m["entries"]
                   if e["kind"] == "probe"}
        if not any(os.path.isfile(os.path.join(ROOT, e["staged_as"]))
                   for e in m["entries"]):
            pytest.skip("staged binaries are git-ignored and absent (fresh clone)")
        for n in ("T1uG", "TB0g", "BX_v3", "DEMO_250v_room_v9"):
            built = a["built"][n]
            e = by_name[f"{n}.rvt"]
            assert e["md5"] == built["md5"], n
            staged = os.path.join(ROOT, e["staged_as"])
            assert os.path.isfile(staged)
            assert _md5(staged) == built["md5"], n

    def test_control_is_byte_identical_g_abpd(self, m):
        ctrl = m["entries"][0]
        staged = os.path.join(ROOT, ctrl["staged_as"])
        base = os.path.join(ROOT, "experiments", "genesis", "subst_k4",
                            "compose", "G_ABPD.rvt")
        assert _md5(staged) == _md5(base)

    def test_all_bases_certified(self, m):
        for e in m["entries"]:
            if e["kind"] == "probe":
                assert e["base_status"] == "certified", e["file"]

"""rft-probes stream tests -- the birth-state probe ladder.

Pins (1) the corpus census SELECTION LAW (TB0/TB0r are the smallest
famdocs whose native instances are MODEL-form FamilyInstances -- the
annotation-family confound is measured, not assumed), (2) the emitted
probes' shape (one added family + one instance, blob-carrying, ONE
instance record, gates green), (3) the birthright module's contract
(tolerant spec parse, the zero-donor adoption line, the delta engine, the
honest roster refusal), and (4) the staged batch (controls first, one
control per distinct base).

Stream-local only (SUITE-COORDINATION: no full-suite runs from this
stream)::

    .venv/bin/python -m pytest tests/test_rft_probe.py -q
"""
from __future__ import annotations

import glob
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "rftprobe")
ACCT = os.path.join(OUT_DIR, "accounting.json")
PROBES = os.path.join(OUT_DIR, "probes.json")
CENSUS = os.path.join(OUT_DIR, "corpus_census.json")
ACCEPTANCE = os.path.join(ROOT, "experiments", "acceptance")

BUILT_TODAY = ("TB0", "TB0r", "T0", "T2a")


def _load(path):
    with open(path) as fh:
        return json.load(fh)


# ===========================================================================
# the census + selection law
# ===========================================================================

@pytest.mark.skipif(not os.path.isfile(CENSUS),
                    reason="census not run (tools/rft_probe.py census)")
class TestCensus:
    def test_selection_is_smallest_model_instanceable(self):
        c = _load(CENSUS)
        rows = c["rows"]
        model = [r for r in rows
                 if r["native_instances"]["model_form"] > 0
                 and r["seq103_loadable"]]
        model.sort(key=lambda r: r["n_records"])
        assert model[0]["family"] == "M_RPC Female"
        assert model[0]["sample"] == "racadvancedsampleproject"
        assert model[0]["unit"] == 33
        assert model[0]["n_records"] == 381
        rst = [r for r in model if r["sample"] == "rstbasicsampleproject"]
        assert rst[0]["family"] == "M_Pile-Steel Pipe"
        assert rst[0]["unit"] == 41
        assert rst[0]["n_records"] == 414

    def test_annotation_confound_is_measured(self):
        """The absolutely smallest famdocs are annotation families whose
        native instances are NOT model-form -- the reason TB0 is 381
        records and not 199."""
        c = _load(CENSUS)
        rows = sorted(c["rows"], key=lambda r: r["n_records"] or 0)
        smallest = rows[0]
        assert smallest["n_records"] < 381
        assert smallest["native_instances"]["model_form"] == 0
        assert "annotation" in c["annotation_finding"]
        # every famdoc smaller than TB0's has zero model-form instances
        for r in rows:
            if (r["n_records"] or 0) >= 381:
                break
            assert r["native_instances"]["model_form"] == 0, r

    def test_tb0_pins_match_census(self):
        import rft_probe as RP
        c = _load(CENSUS)
        sel = c["selection"]
        assert sel["TB0"]["unit"] == RP.TB0_UNIT
        assert sel["TB0r"]["unit"] == RP.TB0R_UNIT


# ===========================================================================
# the emitted probes
# ===========================================================================

@pytest.mark.skipif(not (os.path.isfile(ACCT) and os.path.isfile(PROBES)),
                    reason="probes not built (tools/rft_probe.py build)")
class TestBuiltProbes:
    def test_all_buildable_rungs_present_and_green(self):
        a = _load(ACCT)
        for n in BUILT_TODAY:
            assert n in a["built"], n
            g = a["gates"][n]
            assert g["gates_ok"], (n, g)
            for k, v in g["checks"].items():
                assert v, (n, k)

    def test_one_family_one_instance_each(self):
        a = _load(ACCT)
        for n in BUILT_TODAY:
            info = a["built"][n]
            assert len(info["instance_ids"]) == 1, n
            assert info["symbol_id"] and info["family_id"], n
            # the unit arrives on the LOAD hop; the instance hop adds none
            assert a["accounting"][n]["census_delta"]["save_units"] == 0, n
            assert a["accounting"][n + ".hop_load"]["census_delta"][
                "save_units"] == 1, n

    def test_blob_law_every_unit_64B_added_nonce_ours(self):
        a = _load(ACCT)
        for n in BUILT_TODAY:
            bp = a["built"][n]["blob_proof"]
            assert bp["all_units_64B"], n
            assert bp["added_nonce_verified"], n
            assert list(bp["blob_len_histogram"]) == ["64"], n
            assert bp["units_added_vs_base"] == 1, n

    def test_probe_files_exist_with_recorded_md5(self):
        import rft_probe as RP
        a = _load(ACCT)
        if not any(os.path.isfile(os.path.join(ROOT, a["built"][n]["file"]))
                   for n in BUILT_TODAY):
            pytest.skip("probe binaries are git-ignored and absent (fresh clone)")
        for n in BUILT_TODAY:
            f = os.path.join(ROOT, a["built"][n]["file"])
            assert os.path.isfile(f), n
            assert RP.md5_of(f) == a["built"][n]["md5"], n

    def test_bases_are_the_charter_bases(self):
        a = _load(ACCT)
        assert a["built"]["TB0"]["base"] == \
            "samples/racadvancedsampleproject.rvt"
        assert a["built"]["TB0r"]["base"] == \
            "samples/rstbasicsampleproject.rvt"
        assert a["built"]["T0"]["base"] == \
            "experiments/genesis/subst_k4/compose/G_ABPD.rvt"
        assert a["built"]["T2a"]["base"] == \
            "experiments/genesis/subst_k4/compose/G_ABPD.rvt"

    def test_t2a_standalone_species_facts(self):
        """T2a pins the standalone-species laws this stream measured: the
        owner map comes from Global/ElemTable, the rebase is the
        schema-typed decode-time remap (the blind int-walk aliases the
        small-id species), and the host symbol name is a REAL type name,
        never the corpus blank pair."""
        a = _load(ACCT)
        t = a["built"]["T2a"]
        assert t["rfa_facts"]["owner_source"] == "Global/ElemTable"
        assert t["rfa_facts"]["n_elements"] == 1992
        assert t["template"]["types_from_template"] is True
        names = [n for n, _v in t["template"]["types_authored"]]
        assert names and all(str(n).strip() for n in names)
        assert t["load"]["type_names"] == names

    def test_probes_json_decision_table(self):
        p = _load(PROBES)
        rungs = {r["rung"]: r for r in p["probes"]}
        for n in BUILT_TODAY:
            assert n in rungs
            assert rungs[n]["n_families"] == 1
            assert rungs[n]["n_instances"] == 1
            assert rungs[n]["gates_ok"] is True
        rd = p["reading_the_matrix"]
        assert "T2 PASS + T1 PASS + T0 FAIL" in rd
        assert "TB0r FAIL" in rd
        assert "CTRL FAIL" in rd


# ===========================================================================
# the staged batch
# ===========================================================================

def _rft_batches():
    out = []
    for p in sorted(glob.glob(os.path.join(ACCEPTANCE, "batch_*.json"))):
        try:
            m = _load(p)
        except Exception:                                     # noqa: BLE001
            continue
        if "rft_probe" in str(m.get("tool", "")):
            out.append(m)
    return out


@pytest.mark.skipif(not _rft_batches(),
                    reason="not staged (tools/rft_probe.py stage)")
class TestStagedBatch:
    def test_controls_first_one_per_distinct_base(self):
        m = _rft_batches()[-1]
        entries = m["entries"]
        kinds = [e["kind"] for e in entries]
        n_ctrl = kinds.count("control")
        assert kinds[:n_ctrl] == ["control"] * n_ctrl
        assert "probe" not in kinds[:n_ctrl]
        probe_bases = {e["base"] for e in entries if e["kind"] == "probe"}
        ctrl_sources = {e.get("control_source") for e in entries
                        if e["kind"] == "control"}
        assert probe_bases <= ctrl_sources

    def test_staged_copies_byte_identical(self):
        import rft_probe as RP
        m = _rft_batches()[-1]
        if not any(os.path.isfile(os.path.join(ROOT, e["staged_as"]))
                   for e in m["entries"]):
            pytest.skip("staged binaries are git-ignored and absent (fresh clone)")
        for e in m["entries"]:
            f = os.path.join(ROOT, e["staged_as"])
            assert os.path.isfile(f), e["staged_as"]
            assert RP.md5_of(f) == e["md5"], e["staged_as"]


# ===========================================================================
# birthright (pure-function contracts; no build artifacts needed)
# ===========================================================================

class TestBirthright:
    def _spec_dict(self, **fam):
        base = {"version": 1,
                "source": {"rft": "samples/rft/X.rft", "sha256": "0" * 64},
                "famdoc": {"n_records": 3, "self_family_id": 100,
                           "category_id": -2001330, "part_type": -1,
                           "class_histogram": {"Family": 1,
                                               "UnitsElem": 1,
                                               "BrowserOrganization": 1},
                           **fam}}
        return base

    def _write(self, tmp_path, data):
        p = tmp_path / "template_birth.json"
        p.write_text(json.dumps(data))
        return str(p)

    def test_spec_parse_nested_and_flat(self, tmp_path):
        from rvt.famgen import birthright as BR
        s = BR.read_birth_spec(self._write(tmp_path, self._spec_dict()))
        assert s.category_id == -2001330
        assert s.class_histogram["BrowserOrganization"] == 1
        flat = {"version": 1,
                "class_histogram": {"Family": 1}, "category_id": 5}
        s2 = BR.read_birth_spec(self._write(tmp_path, flat))
        assert s2.class_histogram == {"Family": 1}
        assert s2.category_id == 5

    def test_spec_requires_histogram(self, tmp_path):
        from rvt.famgen import birthright as BR
        with pytest.raises(ValueError, match="class_histogram"):
            BR.read_birth_spec(self._write(tmp_path, {"version": 1}))

    def test_adoption_line_laws_yes_identity_no(self):
        from rvt.famgen.birthright import adoptable
        assert adoptable("m_partType", -1)
        assert adoptable("m_nextAbsorbedIndex", 3165)
        assert adoptable("m_flag", True)
        assert adoptable("m_ids", [1, 2, 3])
        assert not adoptable("m_guid",
                             "e2fe4920-1111-2222-3333-444455556666")
        assert not adoptable("m_name", "x" * 200)
        assert not adoptable("m_blob", b"\x00" * 64)

    def test_author_equivalent_fresh_guid(self):
        from rvt.famgen.birthright import author_equivalent
        g = "e2fe4920-1111-2222-3333-444455556666"
        out = author_equivalent("m_creationGUID", g)
        assert out != g and len(out) == len(g)

    class _El:
        def __init__(self, eid, cls, obj=None, header=None):
            self.elem_id = eid
            self.class_name = cls
            self.obj = obj or {}
            self.header = header or {}

    class _Doc:
        def __init__(self, els, sf):
            self.elements = els
            self.self_family = sf

    def _doc(self):
        sf = self._El(100, "Family",
                      obj={"m_partType": 0, "m_nextAbsorbedIndex": 1,
                           "m_famDocGUID": "aaaaaaaa-bbbb-cccc-dddd-eeeeffff0000"},
                      header={"m_flags": 0})
        return self._Doc([sf, self._El(101, "UnitsElem")], sf)

    def test_delta_missing_and_field_deltas(self, tmp_path):
        from rvt.famgen import birthright as BR
        spec = BR.read_birth_spec(self._write(
            tmp_path, self._spec_dict(
                self_family_fields={"m_partType": -1,
                                    "m_nextAbsorbedIndex": 1,
                                    "m_notEmitted": 7},
                self_family_header={"m_flags": 4})))
        d = BR.birth_delta(self._doc(), spec)
        assert d["missing_classes"] == {"BrowserOrganization": 1}
        assert d["unauthorable"] == ["BrowserOrganization"]
        keys = {x["key"] for x in d["field_deltas"]}
        assert keys == {"m_partType"}       # equal values + unknown keys skipped
        assert d["header_deltas"][0]["key"] == "m_flags"

    def test_apply_refuses_unauthorable_roster(self, tmp_path):
        from rvt.famgen import birthright as BR
        spec = BR.read_birth_spec(self._write(tmp_path, self._spec_dict()))
        with pytest.raises(ValueError, match="author spec"):
            BR.apply_birthright(self._doc(), spec)

    def test_apply_fields_lane_and_registered_constructor(self, tmp_path):
        from rvt.famgen import birthright as BR
        spec = BR.read_birth_spec(self._write(
            tmp_path, self._spec_dict(
                self_family_fields={"m_partType": -1})))
        doc = self._doc()

        made = {}

        def ctor(d, s, count):
            made["n"] = count
            return [self._El(999, "BrowserOrganization")]

        BR.CONSTRUCTORS["BrowserOrganization"] = ctor
        try:
            rep = BR.apply_birthright(doc, spec)
        finally:
            del BR.CONSTRUCTORS["BrowserOrganization"]
        assert made["n"] == 1
        assert any(e.class_name == "BrowserOrganization"
                   for e in doc.elements)
        assert doc.self_family.obj["m_partType"] == -1
        assert rep["fields_set"] == ["m_partType"]

    def test_fields_lane_never_carries_identity(self, tmp_path):
        from rvt.famgen import birthright as BR
        donor_guid = "e2fe4920-1111-2222-3333-444455556666"
        spec = BR.read_birth_spec(self._write(
            tmp_path, self._spec_dict(
                self_family_fields={"m_famDocGUID": donor_guid})))
        doc = self._doc()
        rep = BR.apply_birthright(doc, spec, lanes=("fields",))
        assert doc.self_family.obj["m_famDocGUID"] != donor_guid
        assert rep["authored_equivalents"]


# ===========================================================================
# the tool's pure helpers
# ===========================================================================

class TestToolHelpers:
    def test_pick_rft_prefers_electrical(self, tmp_path, monkeypatch):
        import rft_probe as RP
        d = tmp_path / "rft"
        d.mkdir()
        (d / "Metric Generic Model.rft").write_bytes(b"x")
        (d / "Metric Electrical Equipment.rft").write_bytes(b"x")
        monkeypatch.setattr(RP, "RFT_DIR", str(d))
        assert "Electrical" in os.path.basename(RP.pick_rft())

    def test_pick_rft_explicit_wins(self, tmp_path, monkeypatch):
        import rft_probe as RP
        d = tmp_path / "rft"
        d.mkdir()
        f = d / "A.rft"
        f.write_bytes(b"x")
        monkeypatch.setattr(RP, "RFT_DIR", str(d))
        assert RP.pick_rft(str(f)) == str(f)

    def test_poll_shape_without_material(self, tmp_path, monkeypatch):
        import rft_probe as RP
        monkeypatch.setattr(RP, "RFT_DIR", str(tmp_path / "none"))
        monkeypatch.setattr(RP, "BIRTH_JSON", str(tmp_path / "nope.json"))
        # hermetic: T2a keys on the vendor .rfa being on disk (git-ignored
        # quarantine dir) -- pin it present so the shape is machine-independent
        rfa = tmp_path / "born.rfa"
        rfa.write_bytes(b"r")
        monkeypatch.setattr(RP, "VENDOR_RFA", str(rfa))
        out = RP.poll()
        assert out["buildable_now"] == ["TB0", "TB0r", "T0", "T2a"]
        assert len(out["waiting_on"]) == 2

    def test_poll_unlocks_rungs_with_material(self, tmp_path, monkeypatch):
        import rft_probe as RP
        d = tmp_path / "rft"
        d.mkdir()
        (d / "X.rft").write_bytes(b"x")
        bj = tmp_path / "template_birth.json"
        bj.write_text(json.dumps({"class_histogram": {"Family": 1}}))
        monkeypatch.setattr(RP, "RFT_DIR", str(d))
        monkeypatch.setattr(RP, "BIRTH_JSON", str(bj))
        rfa = tmp_path / "born.rfa"
        rfa.write_bytes(b"r")
        monkeypatch.setattr(RP, "VENDOR_RFA", str(rfa))
        out = RP.poll()
        assert set(out["buildable_now"]) == {"TB0", "TB0r", "T0", "T2a",
                                             "T2", "T1", "T3"}
        assert out["waiting_on"] == []

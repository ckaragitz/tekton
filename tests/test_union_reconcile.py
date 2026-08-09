"""union-reconcile stream tests -- the U16(PASS)/T1v(FAIL) three-axis split.

Pins (1) the single-variable ladder's shape (each probe varies EXACTLY one
axis vs its comparator: T1u=species, T1r=base-failing-side, U16g=
base-proven-side; all 8 outcomes pre-committed), (2) the byte-identity
evidence (T1r/U16g unit segments machine-verified equal to the shipped
T1v/U16 units; T1u's carried block lands on U16's exact ids with the
session hex pinned), (3) the byte audit's verdict (both machineries
produced structurally identical famdoc mutations; the separable delta is
the inline-ADocument flavour; no T1w warranted), and (4) the staged batch
(controls first, one byte-identical certified control per distinct base).

Stream-local only (SUITE-COORDINATION: no full-suite runs from this
stream)::

    .venv/bin/python -m pytest tests/test_union_reconcile.py -q
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT_DIR = os.path.join(ROOT, "experiments", "unionrec")
ACCT = os.path.join(OUT_DIR, "accounting.json")
PROBES = os.path.join(OUT_DIR, "probes.json")
AUDIT = os.path.join(OUT_DIR, "byte_audit.json")
ACCEPTANCE = os.path.join(ROOT, "experiments", "acceptance")

LADDER = ("T1u", "T1r", "U16g")


def _load(path):
    with open(path) as fh:
        return json.load(fh)


def _ur():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "_test_unionrec", os.path.join(ROOT, "tools", "union_reconcile.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ===========================================================================
# machinery contracts (pure python, no builds)
# ===========================================================================

class TestMachinery:
    def test_pinned_identities_match_the_recorded_builds(self):
        """The pins come from the two sides' own accounting records."""
        ur = _ur()
        u16 = _load(os.path.join(ROOT, "experiments", "famdoc_final",
                                 "accounting.json"))["built"]["U16"]
        t1v = _load(os.path.join(ROOT, "experiments", "birthright",
                                 "accounting.json"))["built"]["T1v"]
        assert ur.U16_DOC_GUID == u16["document_guid"]
        assert ur.T1V_DOC_GUID == t1v["document_guid"]

    def test_session_hex_pinning(self):
        """pin_session_hex rewrites every string occurrence and counts."""
        ur = _ur()
        from rvt.genesis.skeleton import SkelElement
        fresh = "a" * 32
        tgt = ur.U16_SESSION_HEX
        el = SkelElement(1, "ParamElemFamily",
                         {"x": f"revit.local.family:{fresh}00000001-1.0.0"},
                         {"m_pParamDef": {"value": {"m_typeId": {
                             "m_typeId":
                             f"revit.local.family:{fresh}00000001-1.0.0"}}}},
                         None, owner_id=-1)
        n = ur.pin_session_hex([el], fresh, tgt)
        assert n == 2
        assert ur.doc_session_hexes([el]) == {tgt}

    def test_ladder_is_exactly_the_charter(self):
        ur = _ur()
        assert tuple(ur.LADDER) == LADDER
        # every one of the 8 outcomes + the control row is pre-committed
        outcomes = [k for k in ur.DECISION_TABLE if k.startswith("T1u ")]
        assert len(outcomes) == 8
        assert any(k.startswith("CTRL") for k in ur.DECISION_TABLE)

    def test_bases_split(self):
        ur = _ur()
        assert ur.base_of("T1u").endswith("rstbasicsampleproject.rvt")
        assert ur.base_of("T1r").endswith("rstbasicsampleproject.rvt")
        assert ur.base_of("U16g").endswith("G_ABPD.rvt")


# ===========================================================================
# the built evidence
# ===========================================================================

@pytest.mark.skipif(not os.path.isfile(ACCT),
                    reason="probes not built (tools/union_reconcile.py build)")
class TestBuilt:
    def test_all_gates_green(self):
        a = _load(ACCT)
        for name in LADDER:
            g = a["gates"][name]
            assert g["gates_ok"] is True, (name, g)
            assert g["validator_errors"] == 0
            assert g["validator_unexpected"] == 0
            assert g["famdoc_refs_unresolved_anywhere"] == 0
            assert g["blob_added_nonce_verified"] is True
            assert g["blob_units_added"] == 1

    def test_byte_identity_machine_verified(self):
        """T1r == T1v's unit; U16g == U16's unit; segment-for-segment."""
        a = _load(ACCT)
        for name, target in (("T1r", "T1v_load.rvt"), ("U16g", "U16.rvt")):
            bi = a["built"][name]["byte_identity"]
            assert bi["target_file"].endswith(target)
            assert set(bi["segments_byte_identical"]) == {"101", "102", "103"}
            assert all(bi["segments_byte_identical"].values()), (name, bi)

    def test_fresh_unit_guids(self):
        """House law: fresh unit GUID per build -- a reused GUID risks
        viewer-side content dedupe faking a verdict."""
        ur = _ur()
        a = _load(ACCT)
        guids = {n: a["built"][n]["document_guid"] for n in LADDER}
        assert len(set(guids.values())) == 3
        assert ur.U16_DOC_GUID not in guids.values()
        assert ur.T1V_DOC_GUID not in guids.values()

    def test_t1u_carried_block_lands_on_u16s_ids(self):
        """RST wm == G_ABPD wm, so famdoc_final's wm+2000 offset puts
        T1u's carried 35 on U16's exact element ids."""
        a = _load(ACCT)
        u16 = _load(os.path.join(ROOT, "experiments", "famdoc_final",
                                 "accounting.json"))["built"]["U16"]
        t1u_ids = [c["id"] for c in a["built"]["T1u"]["union"]["carried"]]
        assert sorted(t1u_ids) == sorted(
            u16["adoc_swap"]["elem_rows_appended"])

    def test_t1u_session_hex_pinned_to_u16(self):
        ur = _ur()
        a = _load(ACCT)
        pin = a["built"]["T1u"]["union"]["session_hex"]
        assert pin["pinned_to"] == ur.U16_SESSION_HEX
        assert pin["substitutions"] == 14        # the 14 ParamElemFamily ids

    def test_t1u_born_adoc_port(self):
        """The born document object rode in: populated registries, born
        build strings, full elem table, zero unmapped positive ids."""
        a = _load(ACCT)
        sw = a["built"]["T1u"]["adoc_swap"]
        assert sw["appinfo_populated"] == 131
        assert sw["stored_by_revit_build"] == 9
        assert sw["elem_rows_total"] == a["built"]["T1u"]["n_elements"]
        assert sw["typed_remap"]["positive_elementids_not_in_idmap"] == 0
        assert sw["owner_family_id"] == \
            a["built"]["T1u"]["union"]["anchors"]["self_family"]

    def test_u16g_adoc_equals_u16s(self):
        """U16g's swapped inline ADocument == U16's, modulo exactly the 4
        per-build history identity GUIDs."""
        a = _load(ACCT)
        d = a["built"]["U16g"]["adoc_value_diff_vs_u16"]
        assert d["all_within_history_identity"] is True
        assert d["n_diff_paths"] == 4

    def test_single_variable_recipes(self):
        """T1u/T1r instance on rst with T1v's category; U16g on G_ABPD
        with U16's category -- each probe's recipe matches its
        comparator's on everything but the probed axis."""
        a = _load(ACCT)
        t1v = _load(os.path.join(ROOT, "experiments", "birthright",
                                 "accounting.json"))["built"]["T1v"]
        assert a["built"]["T1r"]["instance_category"] == \
            t1v["instance_category"]
        assert a["built"]["T1u"]["instance_category"] == \
            t1v["instance_category"]          # the shell's own category
        assert a["built"]["U16g"]["instance_category"] == -2001330
        for n in LADDER:
            assert a["built"][n]["instance"]["position_ft"] == \
                [16.0, -8.0, 0.0]
            assert a["built"][n]["instance"]["n_dangling"] == 0


# ===========================================================================
# the byte audit
# ===========================================================================

@pytest.mark.skipif(not os.path.isfile(AUDIT),
                    reason="audit not run (tools/union_reconcile.py audit)")
class TestAudit:
    def test_both_machineries_touched_only_the_self_family(self):
        d = _load(AUDIT)
        for key in ("T1v_vs_T2a", "U16_vs_B7"):
            ch = d[key]["records_changed"]
            assert len(ch) == 2, (key, ch)          # 101 + 102 of the sf
            assert len({e for e, _s, _c in ch}) == 1
            assert d[key]["records_only_in_" + key.split("_vs_")[1]] == []

    def test_carried_pairwise_clean(self):
        d = _load(AUDIT)
        cp = d["carried_pairwise"]
        assert cp["n_pairs"] == 35
        assert cp["clean_pairs"] == 35
        assert cp["pairs_with_deltas"] == []

    def test_registration_surfaces_identical(self):
        d = _load(AUDIT)
        sf = d["self_family_registration"]
        assert sf["surface_only_in_T1v"] == []
        assert sf["surface_only_in_U16"] == []
        assert set(sf["T1v_touched_vs_T2a"]) == set(sf["U16_touched_vs_B7"])

    def test_no_small_id_residue(self):
        d = _load(AUDIT)
        assert d["small_id_residue"]["in_T1v_not_in_T2a"] == {}

    def test_verdict_no_t1w(self):
        d = _load(AUDIT)
        v = d["smoking_gun_verdict"]
        assert v["unit_content_smoking_gun"] is False
        assert v["t1w_warranted"] is False


# ===========================================================================
# the staged batch
# ===========================================================================

def _newest_unionrec_batch():
    best = None
    for p in sorted(os.listdir(ACCEPTANCE)):
        m = re.match(r"batch_(\d+)\.json$", p)
        if not m:
            continue
        man = _load(os.path.join(ACCEPTANCE, p))
        if "union_reconcile" in str(man.get("tool", "")):
            best = man
    return best


@pytest.mark.skipif(_newest_unionrec_batch() is None,
                    reason="not staged (tools/union_reconcile.py stage)")
class TestStaged:
    def test_controls_first_one_per_base(self):
        man = _newest_unionrec_batch()
        entries = man["entries"]
        assert entries[0]["control"] and entries[1]["control"]
        sources = {e["control_source"] for e in entries[:2]}
        assert any(s.endswith("rstbasicsampleproject.rvt") for s in sources)
        assert any(s.endswith("G_ABPD.rvt") for s in sources)
        probes = [e for e in entries if not e["control"]]
        assert [os.path.basename(e["file"]) for e in probes] == \
            ["T1u.rvt", "T1r.rvt", "U16g.rvt"]

    def test_probe_bases_certified_or_sample(self):
        man = _newest_unionrec_batch()
        for e in man["entries"]:
            if e["control"]:
                continue
            assert e["base_status"] in ("certified", "sample"), e

    def test_staged_bytes_match(self):
        import hashlib
        man = _newest_unionrec_batch()
        if not any(os.path.isfile(os.path.join(ROOT, e["staged_as"]))
                   for e in man["entries"]):
            pytest.skip("staged binaries are git-ignored and absent (fresh clone)")
        for e in man["entries"]:
            p = os.path.join(ROOT, e["staged_as"])
            assert os.path.isfile(p), e["staged_as"]
            h = hashlib.md5()
            with open(p, "rb") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            assert h.hexdigest() == e["md5"], e["staged_as"]

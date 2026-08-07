"""regcorner stream tests: the H12 / H11 / H11x12 registration-corner
probes (post-verdict-#34, batch 40).

Stream-local file only (SUITE-COORDINATION rule).  Everything here reads
the already-emitted artifacts under experiments/regcorner/probes/ +
experiments/acceptance/ -- no probe is rebuilt.
"""
from __future__ import annotations

import glob
import hashlib
import json
import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

OUT = os.path.join(ROOT, "experiments", "regcorner", "probes")
ACC = os.path.join(ROOT, "experiments", "acceptance")
RST = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")
LADDER = ("H12", "H11", "H11x12")

pytestmark = pytest.mark.skipif(
    not os.path.isfile(os.path.join(OUT, "H12.rvt")),
    reason="regcorner probes not built (tools/regcorner_probe.py build)")


def md5(path):
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def jload(path):
    with open(path) as fh:
        return json.load(fh)


@pytest.fixture(scope="module")
def schema():
    import famdoc_bisect as FDB
    FDB._install_schema()                                  # noqa: SLF001
    return True


@pytest.fixture(scope="module")
def acct():
    return jload(os.path.join(OUT, "accounting.json"))


@pytest.fixture(scope="module")
def probes():
    return jload(os.path.join(OUT, "probes.json"))


@pytest.fixture(scope="module")
def rowdiff():
    return jload(os.path.join(OUT, "row_diff.json"))


# ---------------------------------------------------------------------------
# the measured row diff (the H11 mold's evidence)
# ---------------------------------------------------------------------------

def test_row_diff_native_census(rowdiff):
    cen = rowdiff["native_ct_census"]
    assert cen["rows"] == 52
    assert cen["authors"] == {"Autodesk Revit": 52}
    assert set(cen["episode_count_lens"]) <= {"2", "3", 2, 3}
    assert len(cen["keysets"]) == 1                 # 52/52 uniform keyset
    cd = rowdiff["native_cd_entry"]
    assert cd["appinfo_slots"] == 239 and cd["appinfo_populated"] == 131
    assert cd["adoc_decodes_clean"] is True


def test_row_diff_names_the_three_content_fields(rowdiff):
    """After the parent build, the famload-vs-native leaf diff exists and
    touches ONLY author/history/EpisodeCounts + the identity GUID."""
    diff = rowdiff.get("ct_row_field_diff") or []
    if not diff:
        pytest.skip("measure ran before the parent build (re-run measure)")
    tops = {d["path"].split(".")[1].split("[")[0] for d in diff}
    assert tops <= {"m_author", "m_history", "m_EpisodeCounts", "m_ContentKey"}
    assert all(d["identity_forced"] == (".m_ContentKey." in d["path"] + ".")
               for d in diff)


# ---------------------------------------------------------------------------
# the shared-parent design (one byte-identical H9-recipe parent, three axes)
# ---------------------------------------------------------------------------

def test_all_probes_share_one_parent(acct):
    parents = {acct["built"][n]["shared_parent"] for n in LADDER}
    assert len(parents) == 1
    md5s = {acct["built"][n]["md5"] for n in LADDER}
    assert len(md5s) == 3                           # three distinct probes


def test_edit_streams_are_exactly_the_axes(acct):
    want = {"H12": {"Global/ContentDocuments"},
            "H11": {"Global/Latest"},
            "H11x12": {"Global/ContentDocuments", "Global/Latest"}}
    for name in LADDER:
        ch = acct["accounting"][name]["load_vs_parent"]["streams_changed"]
        assert {c["stream"] for c in ch} == want[name], name
        # the edit hop adds/removes/modifies NO elements
        ed = acct["accounting"][name]["load_vs_parent"]["element_diff"]
        assert ed["removed"] == 0 and ed["survivors_modified"] == 0 \
            and ed["added"] == 0
        assert acct["accounting"][name]["load_vs_parent"]["elemtable"][
            "added_ids"] == []


def test_edit_hop_registry_silent(acct):
    for name in LADDER:
        d = acct["accounting"][name]["load_vs_parent"]["census_delta"]
        assert d["save_units"] == 0
        assert d["contentdocs_entries"] == 0
        assert d["contenttable_records"] == 0
        assert d["familymgr_entries"] == 0


# ---------------------------------------------------------------------------
# axis proofs (stored + live read-back of the emitted bytes)
# ---------------------------------------------------------------------------

def test_axis_proofs_all_ok(acct):
    for name in LADDER:
        prf = acct["built"][name]["axis_proofs"]
        assert prf["ok"], (name, prf["failures"])


def test_axis_independence_matrix(acct):
    """H12: populated adoc + famload row; H11: native row + null adoc;
    H11x12: both edits."""
    for name, (pop, author, ec_len) in {
            "H12": (131, "rvt-writer", 1),
            "H11": (0, "Autodesk Revit", 2),
            "H11x12": (131, "Autodesk Revit", 2)}.items():
        prf = acct["built"][name]["axis_proofs"]
        assert prf["inline_adoc"]["appinfo_populated"] == pop, name
        row = prf["ct_row"]
        assert row["m_author"] == author, name
        assert len(row["m_EpisodeCounts"]) == ec_len, name


def test_h11_row_is_the_native_mold_except_guid(schema, acct, rowdiff):
    """The strongest H11 claim, read live from the emitted bytes: our CT
    row == the donor's native row field-for-field, GUID excepted."""
    import regcorner_probe as RC
    info = acct["built"]["H11"]
    lat, _p = RC._latest_value(os.path.join(ROOT, info["file"]))
    ours = RC._ct_row_for(lat.value, info["document_guid"])
    mold = rowdiff["native_donor_ct_row"]
    assert ours is not None
    for k, v in mold.items():
        if k == "m_ContentKey":
            continue
        assert ours[k] == v, k
    assert str(ours["m_ContentKey"]["m_guidKey"]).lower() \
        == info["document_guid"].lower()
    assert str(ours["m_ContentKey"]["m_guidKey"]).lower() \
        != rowdiff["native_donor_guid"].lower()


def test_h12_swap_report(acct):
    for name in ("H12", "H11x12"):
        rep = acct["built"][name]["edits"]["adoc_swap"]
        assert rep["appinfo_populated"] == 131
        assert rep["appinfo_slots"] == 239
        assert rep["adoc_bytes"] > 30000
        assert rep["owner_family_id"] == rep["owner_family_expected"]
        # fresh history identity, re-keyed from the donor's own
        assert rep["history_identity_fresh"]
        assert len(rep["history_guids_rekeyed_from"]) == 4


def test_h11_retrofit_ledger(acct):
    for name in ("H11", "H11x12"):
        rep = acct["built"][name]["edits"]["ct_retrofit"]
        assert set(rep["fields_replaced"]) == {
            "m_pHostDocument", "m_author", "m_history", "m_EpisodeCounts"}
        assert rep["identity_kept"] == ["m_ContentKey"]
        touched = {d["path"] for d in rep["leaf_deltas"]}
        assert not any(".m_ContentKey" in p for p in touched)
        # the three content fields moved; the host-document weakref did not
        tops = {p.split(".")[1].split("[")[0] for p in touched}
        assert tops <= {"m_author", "m_history", "m_EpisodeCounts"}
        assert "m_author" in tops


def test_instance_v20_shape(acct):
    for name in LADDER:
        prf = acct["built"][name]["axis_proofs"]["instance_shape"]
        assert all(prf.values()), (name, prf)


# ---------------------------------------------------------------------------
# gates
# ---------------------------------------------------------------------------

def test_gates_all_green(acct):
    for name in LADDER:
        for hop in ("load_vs_parent", "probe_vs_load"):
            a = acct["accounting"][name][hop]
            assert a["validator"]["n_errors"] == 0, (name, hop)
            assert not a["validator"]["unexpected_errors"], (name, hop)
            assert a["census"]["coherent"] is True, (name, hop)
            assert a["survivor_law_ok"] is True, (name, hop)
        assert acct["accounting"][name]["probe_vs_load"][
            "identity_gate"]["status"] == "PASS", name


# ---------------------------------------------------------------------------
# probes.json + the staged batch
# ---------------------------------------------------------------------------

def test_probes_json_decision_table(probes):
    order = list(probes["upload_order_max_information_first"])
    assert order in (list(LADDER), list(LADDER) + ["H13"])
    rungs = {p["rung"]: p for p in probes["probes"]}
    assert set(rungs) >= set(LADDER)
    for p in probes["probes"]:
        assert p["base"].endswith("rstbasicsampleproject.rvt")
        assert p["gates"]["axis_proofs_ok"] is True
        assert p["gates"]["validator_errors_probe"] == 0
        assert p["gates"]["validator_errors_load"] == 0
    rd = probes["reading_the_matrix"]
    assert "H12 PASS" in rd and "ALL THREE FAIL" in rd
    ctx = probes["recorded_context"]
    assert ctx["H9"].startswith("FAIL") and ctx["H10"].startswith("PASS") \
        and ctx["V20"].startswith("PASS")


def test_staged_batch_with_byte_identical_control(probes):
    """Find the staged regcorner batch (H12 in its entries); its control is
    a byte-identical rst copy and every staged probe md5-matches."""
    batch = None
    for mp in sorted(glob.glob(os.path.join(ACC, "batch_*.json"))):
        man = jload(mp)
        names = {os.path.basename(e.get("file") or "") for e in man["entries"]}
        if "H12.rvt" in names and "H11x12.rvt" in names:
            batch = man
    if batch is None:
        pytest.skip("regcorner batch not staged yet (tools/regcorner_probe.py stage)")
    ctrl = [e for e in batch["entries"] if e["kind"] == "control"]
    assert len(ctrl) == 1
    cpath = os.path.join(ROOT, ctrl[0]["staged_as"])
    assert os.path.isfile(cpath)
    assert md5(cpath) == md5(RST)
    order = [os.path.basename(e["staged_as"]) for e in batch["entries"]
             if e["kind"] == "probe"]
    assert order == [f"{n}.rvt" for n in LADDER]
    for e in batch["entries"]:
        if e["kind"] == "probe":
            assert md5(os.path.join(ROOT, e["staged_as"])) == e["md5"]
            src = os.path.join(OUT, os.path.basename(e["staged_as"]))
            assert md5(src) == e["md5"]


# ---------------------------------------------------------------------------
# H13: the fifth-surface patch (built only after the surface stream's
# ranking landed; its own staged batch)
# ---------------------------------------------------------------------------

h13_built = os.path.isfile(os.path.join(OUT, "H13.rvt"))


@pytest.mark.skipif(not h13_built, reason="H13 not built (surface ranking)")
def test_h13_axis_proofs_and_gates(acct):
    info = acct["built"]["H13"]
    prf = info["axis_proofs"]
    assert prf["ok"], prf["failures"]
    # H11's axes carried: native row + famload's null adoc + V20 shape
    assert prf["ct_row"]["m_author"] == "Autodesk Revit"
    assert prf["inline_adoc"]["appinfo_populated"] == 0
    assert all(prf["instance_shape"].values())
    # the fifth-surface rows present (4 + 4)
    assert prf["category_tracking"]["cat_rows_present"] == 4
    assert prf["category_tracking"]["gs_rows_present"] == 4
    for hop in ("load_vs_parent", "probe_vs_load"):
        a = acct["accounting"]["H13"][hop]
        assert a["validator"]["n_errors"] == 0, hop
        assert not a["validator"]["unexpected_errors"], hop
        assert a["census"]["coherent"] is True
        assert a["survivor_law_ok"] is True
    ch = acct["accounting"]["H13"]["load_vs_parent"]["streams_changed"]
    assert {c["stream"] for c in ch} == {"Global/Latest"}
    assert info["immediate_parent"].endswith("H13_load.rvt")
    assert info["surface_spec"]["candidate"].startswith(
        "Latest:ADocument.m_pAppInfoManager")


@pytest.mark.skipif(not h13_built, reason="H13 not built (surface ranking)")
def test_h13_staged_batch():
    batch = None
    for mp in sorted(glob.glob(os.path.join(ACC, "batch_*.json"))):
        man = jload(mp)
        names = {os.path.basename(e.get("file") or "") for e in man["entries"]}
        if names == {"H13.rvt", ""} or ("H13.rvt" in names and "H12.rvt" not in names):
            batch = man
    if batch is None:
        pytest.skip("H13 batch not staged yet")
    ctrl = [e for e in batch["entries"] if e["kind"] == "control"]
    assert len(ctrl) == 1
    assert md5(os.path.join(ROOT, ctrl[0]["staged_as"])) == md5(RST)
    pr = [e for e in batch["entries"] if e["kind"] == "probe"]
    assert len(pr) == 1
    assert md5(os.path.join(ROOT, pr[0]["staged_as"])) == pr[0]["md5"]

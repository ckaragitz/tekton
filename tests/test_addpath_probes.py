"""Tests for the genesis-addpath-probes stream (tools/genesis_addpath_probes.py).

The stream's deliverable is a SET of one-change probes for the ADD PATH,
each derived from the KNOWN-FAILING X0 (Autodesk's own pen table pushed
through our add path) or the KNOWN-PASSING K1 by EXACTLY ONE registration
detail.  These tests pin the measurements the probes rest on, the
byte-exactness of the assembler, and the certification of every emitted
file.  They rebuild small pieces in a temp dir; the full 14-file set is
built by the tool itself (~3 min) and lives in experiments/genesis/addpath/.
"""
from __future__ import annotations

import json
import os
import struct
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

K1 = os.path.join(ROOT, "experiments", "genesis", "triage", "K1.rvt")
X0 = os.path.join(ROOT, "experiments", "genesis", "controls", "X0.rvt")
X0K = os.path.join(ROOT, "experiments", "genesis", "controls", "X0k.rvt")
ADDPATH = os.path.join(ROOT, "experiments", "genesis", "addpath")

pytestmark = pytest.mark.skipif(
    not (os.path.exists(K1) and os.path.exists(X0) and os.path.exists(X0K)),
    reason="K1 / X0 / X0k probe inputs not present")

import genesis_addpath_probes as G   # noqa: E402


@pytest.fixture(scope="module")
def mats():
    return G.load_all()


# ---------------------------------------------------------------------------
# 1. the measured delta the whole probe set rests on
# ---------------------------------------------------------------------------

def test_delta_is_exactly_five_streams_and_one_adocument_leaf(mats):
    d = G.enumerate_delta(mats["K1"], mats["X0"], mats["X0k"])
    assert d["streams_differing"] == [
        "BasicFileInfo", "Global/DocumentIncrementTable", "Global/ElemTable",
        "Global/Latest", "Partitions/21"]
    leaves = d["adocument_leaf_differences"]
    assert len(leaves) == 1
    assert leaves[0]["path"].endswith("m_penWidthTableElemId")
    assert leaves[0]["K1"] == 2 and leaves[0]["X0"] == 1_500_000


def test_elemtable_rows_and_watermark(mats):
    d = G.enumerate_delta(mats["K1"], mats["X0"], mats["X0k"])
    et = d["elemtable"]
    r2 = et["K1_row_for_element_2"]
    assert (r2["creation_ep"], r2["modified_ep"], r2["user_modified_ep"]) == (0, 976, 976)
    assert r2["owner_id"] == -1 and r2["original_id"] == 2
    rx = et["X0_row_for_element_1500000"]
    assert (rx["creation_ep"], rx["modified_ep"], rx["user_modified_ep"]) == (1016, 1016, 1016)
    assert rx["owner_id"] == -1 and rx["original_id"] == 1_500_000
    assert et["K1_watermark"] == 1_472_524 and et["X0_watermark"] == 1_500_000
    assert et["K1_max_modified_ep"] == 1016
    assert et["K1_count"] == et["X0_count"] == 6540


def test_record_position_facts(mats):
    d = G.enumerate_delta(mats["K1"], mats["X0"], mats["X0k"])
    ro = d["record_order"]
    assert ro["K1_position_of_id_2"] == 2516
    assert ro["K1_neighbours_of_id_2"][2:5] == [1, 2, 3]      # ..., 1, 2, 3, ...
    assert ro["X0_position_of_id_1500000"] == 6539
    assert ro["X0_records_after_sentinel_exclusive_last_index"] == 6539
    assert ro["three_seqs_identical_order"] is True
    assert d["X0k"]["position_of_id_2"] == 6539
    assert d["X0k"]["global_latest_identical_to_K1"] is True


def test_embedded_units_recompressed_but_inflate_identically(mats):
    d = G.enumerate_delta(mats["K1"], mats["X0"], mats["X0k"])
    c = d["partition_compression"]
    n = c["embedded_unit_blocks"][0]
    assert n > 0 and c["embedded_unit_blocks"] == [n, n]
    assert c["embedded_blocks_with_identical_INFLATED_payload"] == n
    assert c["embedded_blocks_with_identical_COMPRESSED_member"] == 0


def test_owner_and_flags_collapse_onto_x0(mats):
    c = G.measure_collapses(mats["K1"], mats["X0"])
    assert c["P_owner"]["both_INVALID"] is True
    hdr = c["P_flags"]["header_field_differences_K1_id2_vs_X0_id1500000"]
    # the ONLY header difference is the identity rebase of the own deletion entry
    assert len(hdr) == 1
    assert "m_deletion" in hdr[0]["path"]
    assert hdr[0]["K1"] == 2 and hdr[0]["X0"] == 1_500_000


def test_low_id_is_free_and_unreferenced(mats):
    k1 = mats["K1"]
    ids = {int(r[4]) for r in k1.et_model["records"]}
    assert G.LOW_ID not in ids
    import genesis_substitute as GS
    import genesis_assemble as GA
    ted = GS.TypedEditor(decoder=None, maps=GA.load_registry_maps())
    assert G.LOW_ID not in ted.all_referenced_ids(k1.latest_tree, "ADocument")


# ---------------------------------------------------------------------------
# 2. assembler byte-exactness
# ---------------------------------------------------------------------------

def test_partition_true_logical_roundtrips_byte_exact(mats):
    for m in mats.values():
        assert m.roundtrip_ok, m.path


def test_reassembly_from_own_record_lists_is_byte_identical(mats):
    k1 = mats["K1"]
    logical = G.assemble_partition(k1, k1.u0_recs, len(k1.et_model["records"]))
    assert logical == k1.true_logical
    assert G.ecc.frame_stream(logical) == k1.raw[k1.pname]


def test_elemtable_reencode_byte_identical(mats):
    k1 = mats["K1"]
    et = G.et_model_copy(k1.et_model)
    assert G.encode_elemtable_stream(et) == k1.raw[G.ETB]


def test_move_and_move_back_is_identity(mats):
    """Removing element 2 and re-inserting it 'after 1' reproduces K1's lists."""
    k1 = mats["K1"]
    wo, idx = G.recs_remove(k1.u0_recs, 2)
    assert idx == {101: 2516, 102: 2516, 103: 2516}
    framed = G.pen_records_at(2, k1)
    back, placed = G.recs_insert(wo, framed, "after", after_id=1)
    for s in (101, 102, 103):
        assert placed[s] == 2516
        assert [r.data for r in back[s]] == [r.data for r in k1.u0_recs[s]]


def test_rebased_records_match_x0_verbatim(mats):
    """Autodesk's element-2 bytes rebased to 1,500,000 by the byte-exact codec
    are exactly the records X0's add path appended."""
    k1, x0 = mats["K1"], mats["X0"]
    framed = G.pen_records_at(1_500_000, k1)
    for s in (101, 102, 103):
        xr = next(r for r in x0.u0_recs[s] if r.elem_id == 1_500_000)
        assert framed[s] == xr.data, f"seq {s}"
    proof = G._REBASE_PROOF[1_500_000]
    assert proof["all_three_seqs_identical"] is True     # byte-exact at id 2 first


def test_framed_to_rec_parses_ids(mats):
    framed = G.pen_records_at(27, mats["K1"])
    for s in (101, 102, 103):
        rec = G.framed_to_rec(s, framed[s])
        assert rec.elem_id == 27 and rec.seq == s
        assert len(rec.data) == (12 if s == 101 else 16) + rec.size + 4
        # trailing u32 repeats psize
        assert struct.unpack_from("<I", rec.data, len(rec.data) - 4)[0] == rec.size


# ---------------------------------------------------------------------------
# 3. the built probe files (present after a full tool run)
# ---------------------------------------------------------------------------

def _report(name: str) -> dict:
    p = os.path.join(ADDPATH, f"{name}.json")
    if not os.path.exists(p):
        pytest.skip(f"{name}.json not built (run tools/genesis_addpath_probes.py)")
    with open(p) as fh:
        return json.load(fh)


@pytest.mark.parametrize("name", [p.name for p in G.probe_specs()])
def test_every_probe_certified(name):
    r = _report(name)
    assert r["verdict"] == "CERTIFIED", r.get("FAILED_SELF_CHECK")
    assert r["validator"]["errors"] == 0
    assert r["structural"]["ok"] is True
    assert r["verify_written"]["crc_failures"] == 0
    assert r["verify_written"]["ecc_mismatches"] == 0
    assert r["target_records"]["found_clean"] is True
    assert r["changed_set_as_expected"] is True
    st = r["intended_state"]
    assert st["row_ok"] and st["position_ok"] and st["latest_ok"] and st["watermark_ok"]
    assert st["counts_6540_coherent"] and st["three_seq_orders_equal"]
    assert st["elemtable_ids_equal_record_ids"]


@pytest.mark.parametrize("name,expected", [
    ("P_ep_only", ["Global/ElemTable"]),
    ("P_pos_only", ["Partitions/21"]),
    ("P_allnew", ["Global/ElemTable", "Global/Latest", "Partitions/21"]),
    ("P_lowid", ["Global/ElemTable", "Global/Latest", "Partitions/21"]),
    ("P_ident_only", ["BasicFileInfo", "Global/DocumentIncrementTable"]),
    ("P_ep", ["Global/ElemTable"]),
    ("P_order", ["Partitions/21"]),
    ("P_ident", ["BasicFileInfo", "Global/DocumentIncrementTable"]),
    ("P_sameid_ep", ["Global/ElemTable"]),
    ("P_sameid_order", ["Partitions/21"]),
    ("P_sameid_ident", ["BasicFileInfo", "Global/DocumentIncrementTable"]),
    ("P_all", []),
])
def test_one_change_stream_sets(name, expected):
    """Each probe differs from its template in EXACTLY the intended stream(s)."""
    r = _report(name)
    assert sorted(r["changed_vs_template"]) == sorted(expected)


def test_P_all_is_byte_identical_to_K1():
    r = _report("P_all")
    ap = r["anchor_proof"]
    assert ap["ALL_STREAMS_BYTE_IDENTICAL_TO_K1"] is True
    assert all(ap["per_stream"].values())


def test_P_x0_is_semantic_twin_of_X0():
    r = _report("P_x0")
    ap = r["anchor_proof"]
    assert ap["SEMANTICALLY_IDENTICAL"] is True
    for k in ("elemtable_model_equal", "adocument_tree_equal", "unit0_record_order_equal",
              "unit0_record_bytes_equal", "dit_usernames_equal"):
        assert ap[k] is True
    # the ONLY identity difference vs X0 is the last_save_path string
    assert set(ap["identity_field_delta"]) <= {"last_save_path"}
    # raw differences are cosmetic: BasicFileInfo (path) + Partitions (compression/junk)
    differs = {n for n, s in ap["raw_stream_status"].items() if s != "identical"}
    assert differs <= {"BasicFileInfo", "Partitions/21"}


def test_P_sameid_is_semantic_twin_of_X0k():
    r = _report("P_sameid")
    ap = r["anchor_proof"]
    assert ap["SEMANTICALLY_IDENTICAL"] is True
    assert set(ap["identity_field_delta"]) <= {"last_save_path"}


def test_from_k1_singles_keep_everything_else_at_k1():
    """The from-K1 singles differ from K1 in exactly their one dimension."""
    for name, expected in (("P_ep_only", ["Global/ElemTable"]),
                           ("P_pos_only", ["Partitions/21"]),
                           ("P_ident_only", ["BasicFileInfo", "Global/DocumentIncrementTable"])):
        r = _report(name)
        vs = [n for n, s in r["streams_vs"]["K1"].items() if s == "DIFFERS"]
        assert sorted(vs) == sorted(expected), name


def test_target_positions():
    """Position facts: 'end' probes sit before the sentinel, 'orig' after element 1."""
    for name, pos in (("P_pos_only", "end"), ("P_order", "orig"), ("P_allnew", "orig"),
                      ("P_lowid", "orig"), ("P_sameid_order", "orig"), ("P_ep", "end")):
        r = _report(name)
        assert r["intended_state"]["record_position"] == pos, name


def test_lowid_watermark_not_raised_high_id_raised():
    lo = _report("P_lowid")["intended_state"]
    hi = _report("P_allnew")["intended_state"]
    assert lo["watermark"] == 1_472_524                 # low id under the watermark
    assert hi["watermark"] == 1_500_000                 # high id raises it
    assert lo["elemtable_row"]["elem_id"] == 27
    assert (lo["elemtable_row"]["creation_ep"], lo["elemtable_row"]["modified_ep"],
            lo["elemtable_row"]["user_modified_ep"]) == (0, 976, 976)


def test_manifest_consistency():
    p = os.path.join(ADDPATH, "probes.json")
    if not os.path.exists(p):
        pytest.skip("probes.json not built")
    with open(p) as fh:
        m = json.load(fh)
    names = {q["name"] for q in m["probes"]}
    assert names == {q.name for q in G.probe_specs()}
    assert m["upload_plan"]["PRIMARY_batch"] == ["P_ep_only", "P_pos_only", "P_allnew", "P_lowid"]
    assert set(m["upload_plan"]["NO_UPLOAD_anchors"]) == {"P_all", "P_x0", "P_sameid"}
    assert set(m["upload_plan"]["NO_FILE_collapsed"]) == {"P_owner", "P_flags"}
    # every listed probe has a certified verdict
    for q in m["probes"]:
        assert q["verdict"] == "CERTIFIED", q["name"]
    d = m["measured_delta_K1_vs_X0"]
    assert len(d["adocument_leaf_differences"]) == 1
    assert d["partition_compression"]["embedded_blocks_with_identical_COMPRESSED_member"] == 0

"""terminal-diff stream tests: the exhaustive H12-vs-native enumeration is
complete and classified, the measured envelope facts hold on the real bytes,
the E-probes are single-axis and gate-clean, batch 42 is staged with a
byte-identical control, and the desktop-Revit kit is in place."""
import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import terminal_diff as td                                    # noqa: E402
from rvt import ecc                                           # noqa: E402
from rvt.container import open_rvt                            # noqa: E402
from rvt.partitions import StreamWalker                       # noqa: E402

TD_JSON = os.path.join(ROOT, "experiments", "terminal", "terminal_diff.json")
PROBES_JSON = os.path.join(ROOT, "experiments", "terminal", "probes.json")
BATCH = os.path.join(ROOT, "experiments", "acceptance", "batch_42.json")
KIT = os.path.join(ROOT, "experiments", "terminal", "REVIT-CHECK-KIT.md")


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@pytest.fixture(scope="module")
def diff():
    assert os.path.isfile(TD_JSON), "run tools/terminal_diff.py enumerate"
    return json.load(open(TD_JSON))


@pytest.fixture(scope="module")
def probes():
    assert os.path.isfile(PROBES_JSON), "run tools/terminal_diff.py probes"
    return json.load(open(PROBES_JSON))


# ---------------------------------------------------------------------------
# the enumeration: complete, classified, and pinned to the measured bytes
# ---------------------------------------------------------------------------

def test_axis_table_is_complete_and_classified(diff):
    ids = {a["id"] for a in diff["axes"]}
    assert {"P1", "P2", "P3", "P4", "P5", "P6"} <= ids
    assert {f"D{i}" for i in range(1, 9)} <= ids
    assert {f"U{i}" for i in range(1, 9)} <= ids
    assert "N1" in ids
    for a in diff["axes"]:
        assert a["classification"] in ("PARITY", "TESTED-DEAD", "UNTESTED",
                                       "NOT-A-DIFF")
        if a["classification"] == "TESTED-DEAD":
            assert a.get("verdict"), f"{a['id']} lacks a verdict citation"
        if a["classification"] == "UNTESTED":
            assert a.get("probe"), f"{a['id']} lacks a probe or deferral note"
            assert isinstance(a.get("rank"), int)
    assert diff["summary"]["untested_axes"] == [f"U{i}" for i in range(1, 9)]


def test_every_stream_difference_lands_in_an_axis(diff):
    """Completeness: the streams that differ are exactly the ones the axis
    table explains; every byte-equal stream is in P6's list."""
    differing = {n for n, r in diff["streams"]["streams"].items()
                 if not r["byte_equal"]}
    assert differing == {"BasicFileInfo", "Global/ContentDocuments",
                         "Global/DocumentIncrementTable", "Global/ElemTable",
                         "Global/Latest", "Partitions/21"}
    assert diff["streams"]["only_in_native"] == []
    assert diff["streams"]["only_in_target"] == []


def test_partition_envelope_pins(diff):
    pe = diff["partitions"]
    assert pe["new_unit"]["footer_blob_len"] == 0          # U1: the axis
    assert pe["native_footer_blob_lens"] == [64]
    assert pe["aligned_footer_blobs_equal"] is True
    assert pe["aligned_separators_equal"] is True
    ab = pe["aligned_blocks"]
    assert ab["byte_equal"] == 0                            # U3: every block
    assert ab["compression_ending_only"] == 411
    assert [b["aligned_index"] for b in ab["content_diff"]] == [21, 148, 212]
    er = pe["end_record"]
    assert er["native_junk_after_end"] == 0
    assert er["target_junk_after_end"] == 571               # U2: the axis
    assert er["true_len"] == 10


def test_h10_crosscheck_shares_every_untested_axis(diff):
    """The PASSING file carries the same envelope: exoneration is
    uninstanced-only, hence rank-not-exclude."""
    pe10 = diff["partitions_crosscheck_h10"]
    assert pe10["new_unit"]["footer_blob_len"] == 0
    assert pe10["end_record"]["target_junk_after_end"] == 150
    assert pe10["aligned_blocks"]["compression_ending_only"] == 411
    for a in diff["axes"]:
        if a["classification"] == "UNTESTED":
            assert a.get("h10_shares") in (True, 0), \
                f"{a['id']} must record whether H10 shares it"


def test_record_delta_is_exactly_the_known_adds(diff):
    rd = diff["record_delta"]
    assert [x["path"] for x in rd["basic_file_info"]] == [
        "bfi.author", "bfi.client_app_name", "bfi.last_save_path"]
    assert rd["increment_table"]["all_diffs_are_username_blanking"] is True
    assert len(rd["elem_table"]["added_ids"]) == 23
    assert rd["elem_table"]["removed_ids"] == []
    assert 1472964 in rd["elem_table"]["added_ids"]         # the instance
    cd = rd["content_documents"]
    assert cd["entries"] == {"native": 52, "target": 53}
    assert cd["changed_common_entries"] == []
    gl = rd["global_latest"]["keyed"]
    assert gl["contenttable"]["changed_common_rows"] == []
    assert gl["contenttable"]["added_keys"] == 1
    assert gl["familymgr"]["added_surrogates"] == [1472943]
    assert gl["familymgr"]["changed_common_entries"] == []
    assert gl["etd_symbols_row44"]["added_ids"] == [1472961]
    assert gl["etd_symbols_row44"]["removed_ids"] == []


def test_ecc_layer_is_parity(diff):
    for name, rec in diff["streams"]["streams"].items():
        if "ecc" in rec:
            assert rec["ecc"]["native_roundtrip_exact"], name
            assert rec["ecc"]["target_roundtrip_exact"], name


# ---------------------------------------------------------------------------
# the measured member recipes reproduce Autodesk bytes (live re-derivation)
# ---------------------------------------------------------------------------

def test_adsk_member_recipes_reproduce_native_bytes():
    doc = open_rvt(td.RST)
    try:
        # a partition block member (partial+finish recipe)
        logical = ecc.unframe_stream(doc.raw(td.PART))
        w = StreamWalker(logical, inflate=True, keep_data=True)
        for b in (w.blocks[0], w.blocks[350]):
            stored = logical[b.member_offset:b.member_offset + b.member_len]
            assert td.adsk_member_partition(b.data) == stored
            assert td.ours_member(b.data) != stored     # ours differs (tail)
        # a global member (sync + 02 0c 00 recipe)
        for name in ("Global/PartitionTable", "Global/History"):
            la = doc.logical(name)
            m = doc.members(name)[0]
            stored = la[m.offset:m.offset + m.consumed]
            assert td.adsk_member_global(doc.inflate(name, 0)) == stored
    finally:
        doc.close()


def test_native_unit_footer_blobs_are_the_axis():
    doc = open_rvt(td.RST)
    try:
        w = StreamWalker(ecc.unframe_stream(doc.raw(td.PART)),
                         inflate=False, keep_data=False)
    finally:
        doc.close()
    blobs = [u.footer_blob for u in w.units]
    assert all(len(b) == 64 for b in blobs)
    assert len(set(blobs)) == len(blobs)                    # distinct per unit
    doc = open_rvt(td.H12)
    try:
        w12 = StreamWalker(ecc.unframe_stream(doc.raw(td.PART)),
                           inflate=False, keep_data=False)
    finally:
        doc.close()
    assert len(w12.units[-1].footer_blob) == 0              # ours is empty


# ---------------------------------------------------------------------------
# the probes: single-axis, gate-clean, staged
# ---------------------------------------------------------------------------

def test_probes_json_shape_and_gates(probes):
    names = [p["name"] for p in probes["probes"]]
    assert names == td.ORDER == ["E_ALL", "E1", "E1b", "E3", "E6", "E4",
                                 "E5", "E2"]
    if not any(os.path.isfile(os.path.join(ROOT, p["file"]))
               for p in probes["probes"]):
        pytest.skip("probe binaries are git-ignored and absent (fresh clone)")
    for p in probes["probes"]:
        path = os.path.join(ROOT, p["file"])
        assert os.path.isfile(path), p["file"]
        assert md5_of(path) == p["md5"], p["name"]
        assert p["base"] == "samples/rstbasicsampleproject.rvt"
        g = p["gates"]
        assert g["validator_errors"] == 0, p["name"]
        assert g["gate"] == "OK", p["name"]
    assert "reading_the_matrix" in probes
    assert "ALL FAIL (incl. E_ALL)" in probes["reading_the_matrix"]


def test_probe_single_axis_stream_deltas(probes):
    by = {p["name"]: p for p in probes["probes"]}
    assert by["E1"]["gates"]["streams_changed_vs_h12"] == ["Partitions/21"]
    assert by["E1b"]["gates"]["streams_changed_vs_h12"] == ["Partitions/21"]
    assert by["E6"]["gates"]["streams_changed_vs_h12"] == ["Partitions/21"]
    assert by["E4"]["gates"]["streams_changed_vs_h12"] == ["BasicFileInfo"]
    assert by["E5"]["gates"]["streams_changed_vs_h12"] == [
        "Global/DocumentIncrementTable"]
    assert by["E2"]["gates"]["streams_changed_vs_h12"] == []
    assert set(by["E3"]["gates"]["streams_changed_vs_h12"]) == {
        "Partitions/21", "Global/ContentDocuments",
        "Global/DocumentIncrementTable", "Global/ElemTable", "Global/Latest"}


def test_probe_envelope_facts(probes):
    by = {p["name"]: p for p in probes["probes"]}
    assert by["E1"]["gates"]["partitions"]["new_unit_footer_blob_len"] == 64
    assert by["E1b"]["gates"]["partitions"]["new_unit_footer_blob_len"] == 64
    assert by["E6"]["gates"]["partitions"]["junk_after_end"] == 0
    assert by["E_ALL"]["gates"]["partitions"]["junk_after_end"] == 0
    assert by["E_ALL"]["gates"]["partitions"]["new_unit_footer_blob_len"] == 64
    for n in ("E3", "E_ALL"):
        g = by[n]["gates"]["partitions"]
        assert g["of_those_byte_identical_to_native"] == \
            g["aligned_content_identical_blocks"] == 411, n
    for n, p in by.items():
        assert p["gates"]["partitions"]["all_block_contents_equal_h12"], n
        assert p["gates"]["decoded_identity"]["elemtable_equal"], n


def test_e4_and_eall_bfi_byte_equal_native(probes):
    by = {p["name"]: p for p in probes["probes"]}
    for n in ("E4", "E_ALL"):
        assert by[n]["gates"]["decoded_identity"]["bfi_raw_equal_native"], n
    for n in ("E5", "E_ALL"):
        assert by[n]["gates"]["decoded_identity"]["dit_equal_native"], n


def test_e2_and_eall_carry_native_directory_tree():
    for n in ("E2", "E_ALL"):
        path = os.path.join(td.PROBE_DIR, f"{n}.rvt")
        cp = td.parse_cfb(path)
        ca = td.parse_cfb(td.RST)
        tp = [(e["color"], e["left"], e["right"], e["child"])
              for e in cp["entries"] if e]
        ta = [(e["color"], e["left"], e["right"], e["child"])
              for e in ca["entries"] if e]
        assert tp == ta, n
        # and the probe still opens through olefile with the same streams
        doc = open_rvt(path)
        try:
            assert {s.name for s in doc.streams()} == {
                s.name for s in open_rvt(td.H12).streams()}
        finally:
            doc.close()


def test_batch_42_staged_with_byte_identical_control(probes):
    assert os.path.isfile(BATCH), "run tools/terminal_diff.py stage"
    m = json.load(open(BATCH))
    assert m["batch"] == 42
    assert m["control_count"] == 1
    ctrl = m["entries"][0]
    assert ctrl["control"] is True
    assert ctrl["md5"] == "b3235ad2743f19bcfff243654fec35dd"
    staged = [os.path.basename(e["staged_as"]) for e in m["entries"][1:]]
    assert staged == [f"{n}.rvt" for n in td.ORDER]
    by = {p["name"]: p for p in probes["probes"]}
    for e in m["entries"][1:]:
        name = os.path.basename(e["staged_as"])[:-4]
        assert e["md5"] == by[name]["md5"], name
        assert md5_of(os.path.join(ROOT, e["staged_as"])) == e["md5"], name


def test_revit_check_kit_in_place():
    assert os.path.isfile(KIT)
    text = open(KIT).read()
    assert "BXhf_f1i1.rvt" in text and "H12.rvt" in text
    assert "Warnings" in text and "screenshot" in text.lower()
    assert md5_of(os.path.join(td.OUT_DIR, "H12.rvt")) == md5_of(td.H12)
    assert md5_of(os.path.join(td.OUT_DIR, "BXhf_f1i1.rvt")) == md5_of(td.BXHF)

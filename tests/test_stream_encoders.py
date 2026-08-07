"""Round-trip + mutation tests for rvt.stream_encoders / rvt.streams_edit.

Byte-exactness target: for every one of the six corpus samples and every one
of the six small structured streams, decode -> encode reproduces the original
payload/stream byte-for-byte.
"""
from __future__ import annotations

import os
import struct

import pytest

from rvt import stream_encoders as se
from rvt import streams_edit as ed
from rvt.container import depage
from rvt.elemtable import parse_elemtable

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EXTRACTED = os.path.join(ROOT, "extracted")
SAMPLES = [
    "racbasicsampleproject",
    "racadvancedsampleproject",
    "rmebasicsampleproject",
    "rstbasicsampleproject",
    "rstadvancedsampleproject",
    "dach-sample-project",
]
STREAMS = ["ElemTable", "History", "DocumentIncrementTable",
           "PartitionTable", "Contents", "BasicFileInfo"]


def _payload(sample: str, name: str) -> bytes:
    kind = se.CODECS[name][2]
    if kind == "payload":
        p = os.path.join(EXTRACTED, sample, f"Global__{name}.gz", "000.bin")
    elif kind == "contents":
        p = os.path.join(EXTRACTED, sample, "Contents.gz", "000.bin")
    else:
        p = os.path.join(EXTRACTED, sample, f"{name}.bin")
    with open(p, "rb") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# 1. the 6 x 6 byte-exact round-trip matrix
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", STREAMS)
@pytest.mark.parametrize("sample", SAMPLES)
def test_roundtrip_byte_exact(sample, name):
    data = _payload(sample, name)
    dec, enc, _ = se.CODECS[name]
    model = dec(data)
    out = enc(model)
    if out != data:
        n = min(len(out), len(data))
        first = next((i for i in range(n) if out[i] != data[i]), n)
        pytest.fail(f"{sample}/{name}: len {len(out)} vs {len(data)}; "
                    f"first diff @0x{first:x}: got {out[first:first+16].hex(' ')}"
                    f" want {data[first:first+16].hex(' ')}")


@pytest.mark.parametrize("sample", SAMPLES)
def test_basic_file_info_mirror_regenerates(sample):
    model = se.decode_basic_file_info(_payload(sample, "BasicFileInfo"))
    assert se.basic_file_info_mirror_text(model) == model["mirror_text"]


@pytest.mark.parametrize("sample", SAMPLES)
def test_contents_prologue_roundtrip(sample):
    raw = open(os.path.join(EXTRACTED, sample, "Contents.bin"), "rb").read()
    pro = se.decode_contents_prologue(raw)
    assert se.encode_contents_prologue(pro) == raw[:24]


# ---------------------------------------------------------------------------
# 2. the 8-byte Global/* prefix constants (from the logical streams)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("sample", SAMPLES)
@pytest.mark.parametrize("name", ["ElemTable", "History", "DocumentIncrementTable",
                                  "PartitionTable", "Latest", "ContentDocuments"])
def test_global_prefix_constants(sample, name):
    p = os.path.join(EXTRACTED, sample, f"Global__{name}.logical.bin")
    if not os.path.exists(p):
        with open(os.path.join(EXTRACTED, sample, f"Global__{name}.bin"), "rb") as fh:
            logical = depage(fh.read())
    else:
        with open(p, "rb") as fh:
            logical = fh.read()
    assert logical[:8] == se.global_prefix(name)
    assert logical[8:11] == b"\x1f\x8b\x08"       # gzip member follows the prefix


def test_wrap_global_stream_is_inflatable():
    import zlib
    payload = _payload("racbasicsampleproject", "PartitionTable")
    logical = se.wrap_global_stream("PartitionTable", payload, level=3)
    assert logical[:8] == b"\x00" * 8
    d = zlib.decompressobj(16 + zlib.MAX_WBITS)   # strict gzip, CRC checked
    assert d.decompress(logical[8:]) == payload


# ---------------------------------------------------------------------------
# 3. ElemTable mutation
# ---------------------------------------------------------------------------

def test_elemtable_add_element_sorted_and_counted():
    m = se.decode_elemtable(_payload("racbasicsampleproject", "ElemTable"))
    n0 = len(m["records"])
    wm0 = ed.elemtable_watermark(m)
    assert wm0 >= ed.elemtable_max_id(m)
    nid = ed.elemtable_next_element_id(m)
    assert nid == wm0 + 1
    # insert a low id in the middle and the next id at the end
    ed.elemtable_add_element(m, 5000000, creation_ep=848)      # beyond all ids
    ed.elemtable_add_element(m, nid, creation_ep=848)
    assert len(m["records"]) == n0 + 2
    ids = [r[4] for r in m["records"]]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    assert ed.elemtable_watermark(m) == 5000000
    with pytest.raises(ValueError):
        ed.elemtable_add_element(m, nid, creation_ep=848)   # duplicate
    payload = se.encode_elemtable(m)
    t = parse_elemtable(payload)                              # wave-1 decoder agrees
    assert t.count == n0 + 2
    assert t.footer.last_id == 5000000
    assert len(payload) == 6 + 40 * (n0 + 2) + 24
    # round-trip of the mutated table
    assert se.encode_elemtable(se.decode_elemtable(payload)) == payload


# ---------------------------------------------------------------------------
# 4. coordinated save across the tables
# ---------------------------------------------------------------------------

def _load_models(sample: str):
    return {
        "ElemTable": se.decode_elemtable(_payload(sample, "ElemTable")),
        "History": se.decode_history(_payload(sample, "History")),
        "DocumentIncrementTable": se.decode_increment_table(
            _payload(sample, "DocumentIncrementTable")),
        "Contents": se.decode_contents(_payload(sample, "Contents")),
        "BasicFileInfo": se.decode_basic_file_info(_payload(sample, "BasicFileInfo")),
    }


@pytest.mark.parametrize("sample", ["racbasicsampleproject", "rstadvancedsampleproject"])
def test_record_save_keeps_cross_stream_invariants(sample):
    models = _load_models(sample)
    n_elem0 = len(models["ElemTable"]["records"])
    n_ep0 = models["History"]["hdr_count"]
    n_inc0 = len(models["DocumentIncrementTable"]["records"])
    new_ids = [ed.elemtable_next_element_id(models["ElemTable"]) + i for i in range(3)]
    rep = ed.record_save(models, new_element_ids=new_ids, username="testuser",
                         timestamp=1_755_000_000)
    # episode allocation / counts
    assert rep["episode_id"] == n_ep0
    assert rep["history_count"] == n_ep0 + 1
    assert rep["elem_count"] == n_elem0 + 3
    assert rep["increments"] == n_inc0 + 1
    # re-encode every table and re-decode with the wave-1 decoders' models
    et = se.decode_elemtable(se.encode_elemtable(models["ElemTable"]))
    hi = se.decode_history(se.encode_history(models["History"]))
    dit = se.decode_increment_table(se.encode_increment_table(models["DocumentIncrementTable"]))
    con = se.decode_contents(se.encode_contents(models["Contents"]))
    bfi = se.decode_basic_file_info(se.encode_basic_file_info(models["BasicFileInfo"]))
    # invariants (docs §5): history count == max(mod_ep)+1 ; DIT id_pair ; BFI ; Contents
    max_mod = max(r[2] for r in et["records"])
    assert hi["hdr_count"] == len(hi["entries"]) == max_mod + 1
    newest = dit["records"][-1]
    assert tuple(newest["id_pair"]) == (n_ep0, n_ep0 + 1)
    assert newest["sequence"] == n_inc0 + 1 and newest["flag"] == 1
    assert dit["records"] == dit["records2"]                 # both copies equal
    assert all(r["elem_id_repeat"] == 0 for r in dit["records"][:-1])
    assert con["counters"] == newest["counters"][:7] + newest["counters"][8:]
    assert con["counter_g"] == newest["counter_g"]
    assert bfi["unique_document_increments"] == str(n_inc0 + 1)
    assert bfi["central_version_number"] == n_inc0 + 1
    assert bfi["unique_document_guid"] == hi["entries"][0][0] == rep["episode_guid"]
    # new records carry the new episode
    for eid in new_ids:
        rec = next(r for r in et["records"] if r[4] == eid)
        assert rec[1] == rec[2] == n_ep0


def test_save_impact_report_shape():
    r = ed.save_impact(7)
    assert r["n_new_elements"] == 7
    assert "Global/ElemTable" in r["must_change"]
    assert "Formats/Latest" in r["constant"]
    assert any("History count" in s for s in r["cross_check_invariants"])

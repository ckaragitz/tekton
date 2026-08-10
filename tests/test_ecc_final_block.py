"""One page-walk law for every reader/checker of a CRCIO-framed stream (#294 / #236).

A FINAL block of 64,388..64,895 data bytes encodes to exactly ``PAGE_STRIDE``
bytes (pad-count field 1..508).  Readers that walked ``len(raw) //
PAGE_STRIDE`` "full pages" took it for a page: ``ecc.unframe_stream``
returned data + pad, and ``verify_written`` / ``verify_manipulated`` reported
one false ``ecc_mismatches`` -> the front door labelled a healthy edit
``FAILED (structural)`` while the CRCIO-faithful validator said 0 errors.
``ecc.iter_blocks`` is now the one law (see its docstring); ``unframe_stream``,
``framing_mismatches`` (behind all three verify_* gates) and
``reduce.unframe_exact`` are built on it.

Sample-free (CI shard): synthetic streams at every interesting length, plus
end-to-end verify_written / verify_manipulated on variants of the tracked
pinned genesis bases written into ``tmp_path``.

Run: .venv/bin/python -m pytest tests/test_ecc_final_block.py -q
"""
from __future__ import annotations

import dataclasses
import os
import random

import pytest

from rvt import ecc
from rvt import reduce as R
from rvt.container import PAGE_PAYLOAD, PAGE_STRIDE, open_rvt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
BAND = (64388, 64895)            # final-block data lengths that fill a whole stride
IN_BAND = 64500
# lengths whose framed form ends in a stride-sized FINAL block, their
# neighbours, genuine whole pages, and the small classes
LENGTHS = [0, 1, 7, 300, 5081, 5082, 64387, BAND[0], IN_BAND, BAND[1], PAGE_PAYLOAD,
           PAGE_PAYLOAD + 1, PAGE_PAYLOAD + IN_BAND, 2 * PAGE_PAYLOAD,
           3 * PAGE_PAYLOAD - 1, 3 * PAGE_PAYLOAD]


def _rand(n: int, seed: int = 7) -> bytes:
    return random.Random(seed * 1_000_003 + n).randbytes(n)


def _flip(raw: bytes, at: int, bit: int = 0) -> bytes:
    b = bytearray(raw)
    b[at] ^= 1 << bit
    return bytes(b)


# --------------------------------------------------------------------------
# the law itself
# --------------------------------------------------------------------------
def test_band_is_what_the_geometry_says():
    """The premise, computed rather than assumed: exactly the final-block
    data lengths 64,388..64,895 (508 of them) encode to one full stride."""
    m, _poly, period, align = ecc.PARAM_CLASSES[0]
    N = ecc.size_field_bits(period, align)
    band = [t for t in range(BAND[0] - 200, PAGE_PAYLOAD)
            if ecc.select_params(t) == ecc.PARAM_CLASSES[0]
            and ecc.encoded_size(t, m, period, align, N) >= PAGE_STRIDE]
    assert (band[0], band[-1], len(band)) == (BAND[0], BAND[1], 508)
    assert ecc.encoded_size(BAND[0] - 1, m, period, align, N) == 64737
    assert all(ecc.encoded_size(t, m, period, align, N) == PAGE_STRIDE for t in band)
    assert len(ecc.frame_stream(bytes(PAGE_PAYLOAD))) == PAGE_STRIDE      # no tail block


@pytest.mark.parametrize("n", LENGTHS)
def test_iter_blocks_is_frame_streams_inverse(n):
    logical = _rand(n)
    raw = ecc.frame_stream(logical)
    blocks = list(ecc.iter_blocks(raw))
    assert b"".join(b for b, _ in blocks) == raw
    assert [fin for _, fin in blocks] == [False] * (len(blocks) - 1) + [True]
    assert all(len(b) == PAGE_STRIDE for b, fin in blocks if not fin)
    assert 0 < len(blocks[-1][0]) <= PAGE_STRIDE
    # frame_stream emits one block per started page, and one for b""
    assert len(blocks) == max(1, -(-n // PAGE_PAYLOAD))
    assert list(ecc.iter_blocks(b"")) == []


@pytest.mark.parametrize("n", LENGTHS)
def test_unframe_round_trip_and_zero_mismatches(n):
    logical = _rand(n)
    raw = ecc.frame_stream(logical)
    tail = (n - 1) % PAGE_PAYLOAD + 1 if n else 0
    # the bug's exact shape: raw an exact multiple of the stride, last block padded
    assert (len(raw) % PAGE_STRIDE == 0) == (BAND[0] <= tail <= PAGE_PAYLOAD)
    assert ecc.unframe_stream(raw) == logical
    assert ecc.framing_mismatches(raw) == 0
    *_, (last, _fin) = ecc.iter_blocks(raw)
    assert ecc.final_block_data_len(last) == tail


def test_genuinely_corrupted_blocks_still_count():
    raw = ecc.frame_stream(_rand(3 * PAGE_PAYLOAD - 1))                  # page, page, padded final
    assert ecc.framing_mismatches(_flip(raw, PAGE_PAYLOAD + 5)) == 1        # page 0 trailer
    assert ecc.framing_mismatches(_flip(raw, PAGE_STRIDE + 100, 3)) == 1    # page 1 payload
    assert ecc.framing_mismatches(_flip(raw, len(raw) - 1, 7)) == 1         # final block parity
    assert ecc.framing_mismatches(_flip(raw, 2 * PAGE_STRIDE + 10)) == 1    # final block data
    two = _flip(_flip(raw, PAGE_PAYLOAD + 5), len(raw) - 2)
    assert ecc.framing_mismatches(two) == 2
    whole = ecc.frame_stream(_rand(2 * PAGE_PAYLOAD))                    # last block IS a full page
    assert ecc.framing_mismatches(whole) == 0
    assert ecc.framing_mismatches(_flip(whole, len(whole) - 1)) == 1     # its trailer, judged as final
    with pytest.raises(ValueError):
        ecc.unframe_stream(_flip(raw, len(raw) - 1, 7))
    junk = b"<?xml version='1.0'?><entry/>" * 20                          # not framed at all
    assert ecc.framing_mismatches(junk) == 1
    with pytest.raises(ValueError):
        ecc.unframe_stream(junk)


def test_one_deframer_in_the_engine():
    assert R.unframe_exact is ecc.unframe_stream


# --------------------------------------------------------------------------
# end to end: the verify_* gates on real containers (tracked pinned bases)
# --------------------------------------------------------------------------
needs_bases = pytest.mark.skipif(
    not all(os.path.isfile(p) for p in BASES.values()),
    reason="bundled genesis bases missing")


def _variant(src: str, dst: str, stream: str, fn) -> None:
    """Copy ``src`` to ``dst`` with ``stream``'s raw bytes replaced by fn(raw)."""
    from rvt.cfb_writer import write_cfb
    from rvt.roundtrip import read_entries
    entries = [dataclasses.replace(e, data=fn(e.data))
               if (e.entry_type == "stream" and e.path == stream) else e
               for e in read_entries(src)]
    assert any(e.entry_type == "stream" and e.path == stream for e in entries), stream
    write_cfb(dst, entries)


def _pad_into_band(raw: bytes) -> bytes:
    """Re-frame the stream with its logical bytes zero-padded to IN_BAND, so
    the whole stream is ONE stride-sized final block (pad field != 0)."""
    logical = ecc.unframe_stream(raw)
    assert len(logical) < BAND[0], len(logical)
    out = ecc.frame_stream(logical + bytes(IN_BAND - len(logical)))
    assert len(out) == PAGE_STRIDE
    return out


@needs_bases
@pytest.mark.parametrize("release", sorted(BASES))
def test_verify_manipulated_zero_false_mismatches_on_a_stride_sized_final_block(tmp_path, release):
    from rvt.manipulate import verify_manipulated
    base = BASES[release]
    ref = verify_manipulated(base)
    assert ref["ecc_mismatches"] == 0 and ref["crc_failures"] == 0, ref
    out = str(tmp_path / f"et_band_{release}.rvt")
    _variant(base, out, "Global/ElemTable", _pad_into_band)
    with open_rvt(out) as d:
        assert len(d.raw("Global/ElemTable")) == PAGE_STRIDE
    rep = verify_manipulated(out)
    assert rep["ecc_mismatches"] == 0, rep                       # 1 before #294
    for k in ("crc_failures", "walker_errors", "elemtable_count", "header_count",
              "sentinel_last", "stamps_ok"):
        assert rep[k] == ref[k], (k, rep[k], ref[k])


@needs_bases
def test_verify_written_zero_false_mismatches_and_real_ones_still_count(tmp_path):
    from rvt.commit import verify_written
    from rvt.manipulate import verify_manipulated
    base = BASES[2026]                                           # built-in framing: no release ctx needed
    ref = verify_written(base, [])
    assert ref["ecc_mismatches"] == 0, ref
    band = str(tmp_path / "et_band.rvt")
    _variant(base, band, "Global/ElemTable", _pad_into_band)
    rep = verify_written(band, [])
    assert rep["ecc_mismatches"] == 0, rep                       # 1 before #294
    assert rep["elemtable_count"] == ref["elemtable_count"] == rep["header_count"]
    # a genuinely damaged full-page trailer of the partition: exactly one, in both gates
    with open_rvt(base) as d:
        pname = d.partition_streams()[0]
    bad = str(tmp_path / "trailer_flip.rvt")
    _variant(base, bad, pname, lambda raw: _flip(raw, PAGE_PAYLOAD + 7))
    assert verify_written(bad, [])["ecc_mismatches"] == 1
    assert verify_manipulated(bad)["ecc_mismatches"] == 1
    # and a damaged final block is no longer invisible to the gate
    badf = str(tmp_path / "final_flip.rvt")
    _variant(base, badf, pname, lambda raw: _flip(raw, len(raw) - 1, 7))
    assert verify_written(badf, [])["ecc_mismatches"] == 1

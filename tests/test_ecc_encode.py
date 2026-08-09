"""Bit-sliced CRCIO page-ECC encoder == the bit-at-a-time reference (#182).

``rvt.ecc.encode_block`` is the lane-parallel (bit-sliced, stdlib-only)
encoder on the WRITE path (``frame_stream`` / ``page_trailer``); the original
CRCIO transcription is kept as ``rvt.ecc._encode_block_ref``.  These tests
are sample-free (CI shard): seeded-random data across every parameter class,
plus the three pinned composed genesis bases shipped in the plugin as ground
truth (their trailers were written by Revit's own reader-accepted layout and
are viewer-certified).
"""
from __future__ import annotations

import os
import random
import time

import pytest

from rvt import ecc
from rvt.container import PAGE_PAYLOAD, PAGE_STRIDE, open_rvt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASES = [os.path.join(ROOT, "plugin", "assets", "genesis", f)
         for f in ("G_ABPD.rvt", "G_ABPD_2025.rvt", "G_ABPD_2024.rvt")]
NO_ECC = {"BasicFileInfo", "PartAtomXML", "TransmissionData",
          "ProjectInformation", "RevitPreview4.0"}
SIZES = [0, 1, 5, 7, 8, 40, 50, 105, 256, 300, 548, 1000, 1274, 5000,
         5081, 5082, 30000, PAGE_PAYLOAD]


def _rand(n: int, seed: int) -> bytes:
    return random.Random(seed * 1_000_003 + n).randbytes(n)


@pytest.mark.parametrize("params", ecc.PARAM_CLASSES,
                         ids=[f"m{p[0]}_poly{p[1]:#x}" for p in ecc.PARAM_CLASSES])
@pytest.mark.parametrize("n", SIZES)
def test_encode_block_matches_reference_every_class(params, n):
    data = _rand(n, params[0])
    assert ecc.encode_block(data, params) == ecc._encode_block_ref(data, params)


@pytest.mark.parametrize("n", SIZES + [2, 3, 41, 106, 257, 549, 1275, 12345, 64895])
def test_encode_block_matches_reference_selected_class(n):
    params = ecc.select_params(n)
    for seed in range(3):
        data = _rand(n, 100 + seed)
        assert ecc.encode_block(data, params) == ecc._encode_block_ref(data, params)


def test_structured_inputs_match_reference():
    """All-zero, all-ones and single-bit pages (the cases a random sweep
    is least likely to hit) in the full-page class and a small class."""
    for params, n in ((ecc.PARAM_CLASSES[0], PAGE_PAYLOAD), (ecc.select_params(300), 300)):
        for data in (bytes(n), b"\xff" * n, b"\x01" + bytes(n - 1),
                     bytes(n - 1) + b"\x80"):
            assert ecc.encode_block(data, params) == ecc._encode_block_ref(data, params)


def test_encoded_size_and_prefix():
    for n in SIZES:
        params = ecc.select_params(n)
        m, _poly, period, align = params
        N = ecc.size_field_bits(period, align)
        data = _rand(n, 9)
        out = ecc.encode_block(data, params)
        assert len(out) == ecc.encoded_size(n, m, period, align, N)
        assert out[:n] == data
    assert len(ecc.page_trailer(bytes(PAGE_PAYLOAD))) == PAGE_STRIDE - PAGE_PAYLOAD == 353


# NB: a final block of 64,388..64,895 data bytes encodes to exactly
# PAGE_STRIDE bytes (255 lanes, pad field 1..508) and the *reader*
# `unframe_stream` takes it for a full page -- a pre-existing decoder
# ambiguity, independent of the encoder (both encoders agree there); filed
# as its own task from #182.  64,387 is the largest unambiguous tail.
@pytest.mark.parametrize("n", [0, 1, 300, 5000, 64387, PAGE_PAYLOAD,
                               PAGE_PAYLOAD + 1, 2 * PAGE_PAYLOAD + 777])
def test_frame_unframe_round_trip(n):
    logical = _rand(n, 42)
    raw = ecc.frame_stream(logical)
    assert ecc.unframe_stream(raw) == logical
    assert ecc.frame_stream(ecc.unframe_stream(raw)) == raw


@pytest.fixture(scope="module")
def bases():
    missing = [b for b in BASES if not os.path.exists(b)]
    if missing:
        pytest.skip(f"pinned genesis base(s) absent: {missing}")
    return {os.path.basename(b): open_rvt(b) for b in BASES}


def _ecc_streams(doc):
    for s in doc.streams():
        raw = doc.raw(s.name)
        if raw and s.name.split("/")[-1] not in NO_ECC:
            yield s.name, raw


def test_pinned_bases_every_full_page_trailer(bases):
    """Every full page of the three shipped bases: new encoder == reference
    == the trailer bytes actually in the certified file."""
    n_pages = 0
    for fname, doc in bases.items():
        for name, raw in _ecc_streams(doc):
            k = 0
            while (k + 1) * PAGE_STRIDE <= len(raw):
                page = raw[k * PAGE_STRIDE:k * PAGE_STRIDE + PAGE_PAYLOAD]
                want = raw[k * PAGE_STRIDE + PAGE_PAYLOAD:(k + 1) * PAGE_STRIDE]
                got = ecc.page_trailer(page)
                assert got == want, (fname, name, k)
                assert got == ecc._encode_block_ref(page)[PAGE_PAYLOAD:], (fname, name, k)
                n_pages += 1
                k += 1
    assert n_pages >= 15, n_pages


def test_pinned_bases_every_stream_reframes_byte_identical(bases):
    """unframe -> frame reproduces every ECC-framed stream of the shipped
    bases byte-for-byte (full pages AND the size-class-selected final
    block), and the final block equals the reference encoder's."""
    n_streams = 0
    for fname, doc in bases.items():
        for name, raw in _ecc_streams(doc):
            logical = ecc.unframe_stream(raw)
            assert ecc.frame_stream(logical) == raw, (fname, name)
            tail = logical[(len(logical) // PAGE_PAYLOAD) * PAGE_PAYLOAD:]
            if tail or not logical:
                p = ecc.select_params(len(tail))
                assert raw.endswith(ecc._encode_block_ref(tail, p)), (fname, name)
            n_streams += 1
    assert n_streams >= 24, n_streams


def test_bitsliced_encoder_is_much_faster_than_reference():
    """Perf tripwire (generous bound so a busy CI host does not flake): the
    lane-parallel encoder must stay >= 5x faster than the bit loop on a full
    page; measured ~50x (1.7 ms vs 86 ms, py3.11)."""
    page = _rand(PAGE_PAYLOAD, 5)

    def best(fn, reps):
        ts = []
        for _ in range(reps):
            t0 = time.perf_counter()
            fn(page)
            ts.append(time.perf_counter() - t0)
        return min(ts)

    new, old = best(ecc.encode_block, 7), best(ecc._encode_block_ref, 2)
    assert new * 5 <= old, (new, old)

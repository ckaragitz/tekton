"""Bit-sliced CRCIO page-ECC encoder == the bit-at-a-time reference (#182).

``rvt.ecc.encode_block`` is the lane-parallel (bit-sliced, stdlib-only)
encoder on the WRITE path (``frame_stream`` / ``page_trailer``); the original
CRCIO transcription is kept as ``rvt.ecc._encode_block_ref``.  These tests
are sample-free (CI shard): seeded-random data across every parameter class,
plus the three pinned composed genesis bases shipped in the plugin as ground
truth (their trailers are the bytes Autodesk's reader certified).
"""
from __future__ import annotations

import os
import random
import time

import pytest

from rvt import ecc
from rvt.container import PAGE_PAYLOAD, PAGE_STRIDE, open_rvt
from rvt.validate import UNFRAMED_STREAMS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASES = [os.path.join(ROOT, "plugin", "assets", "genesis", f)
         for f in ("G_ABPD.rvt", "G_ABPD_2025.rvt", "G_ABPD_2024.rvt")]
NO_ECC = UNFRAMED_STREAMS | {"PartAtom", "PartAtomXML"}
# every size-class threshold and the byte after it, plus in-class sizes
SIZES = sorted({0, 1, 5, 8, 50, 300, 1000, 5000, 12345, 30000, PAGE_PAYLOAD,
                *ecc._THRESH, *(t + 1 for t in ecc._THRESH)})
FULL = ecc.PARAM_CLASSES[0]


def _rand(n: int, seed: int) -> bytes:
    return random.Random(seed * 1_000_003 + n).randbytes(n)


@pytest.mark.parametrize("params", ecc.PARAM_CLASSES,
                         ids=[f"m{p[0]}_poly{p[1]:#x}" for p in ecc.PARAM_CLASSES])
@pytest.mark.parametrize("n", SIZES)
def test_encode_block_matches_reference_every_class(params, n):
    data = _rand(n, params[0])
    assert ecc.encode_block(data, params) == ecc._encode_block_ref(data, params)


@pytest.mark.parametrize("n", SIZES + [2, 3, PAGE_PAYLOAD - 1])
def test_encode_block_matches_reference_selected_class(n):
    params = ecc.select_params(n)
    for seed in range(1 if n >= 30000 else 3):
        data = _rand(n, 100 + seed)
        assert ecc.encode_block(data, params) == ecc._encode_block_ref(data, params)


@pytest.mark.parametrize("params,n", [(FULL, PAGE_PAYLOAD), (ecc.select_params(300), 300)])
@pytest.mark.parametrize("make", [bytes, lambda n: b"\xff" * n,
                                  lambda n: b"\x01" + bytes(n - 1),
                                  lambda n: bytes(n - 1) + b"\x80"],
                         ids=["zeros", "ones", "first_bit", "last_bit"])
def test_structured_inputs_match_reference(params, n, make):
    data = make(n)
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


# A final block of 64,388..64,895 data bytes encodes to exactly PAGE_STRIDE
# bytes; the reader must still decode it by its pad-count field, never take
# it for a full page (#236 / #294 -- `ecc.iter_blocks` is the shared law;
# tests/test_ecc_final_block.py covers the checkers built on it).
@pytest.mark.parametrize("n", [
    0, 1, 300, 5000, 64387, 64388, PAGE_PAYLOAD - 1, PAGE_PAYLOAD, PAGE_PAYLOAD + 1,
    PAGE_PAYLOAD + 64500, 2 * PAGE_PAYLOAD + 777, 3 * PAGE_PAYLOAD - 1, 3 * PAGE_PAYLOAD,
])
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
            for k in range(len(raw) // PAGE_STRIDE):
                page = raw[k * PAGE_STRIDE:k * PAGE_STRIDE + PAGE_PAYLOAD]
                want = raw[k * PAGE_STRIDE + PAGE_PAYLOAD:(k + 1) * PAGE_STRIDE]
                got = ecc.page_trailer(page)
                assert got == want, (fname, name, k)
                assert got == ecc._encode_block_ref(page)[PAGE_PAYLOAD:], (fname, name, k)
                n_pages += 1
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
    page; measured ~120x (0.7 ms vs 87 ms, py3.11)."""
    page = _rand(PAGE_PAYLOAD, 5)

    def best(fn, reps):
        ts = []
        for _ in range(reps):
            t0 = time.perf_counter()
            fn(page)
            ts.append(time.perf_counter() - t0)
        return min(ts)

    new, old = best(ecc.encode_block, 7), best(ecc._encode_block_ref, 1)
    assert new * 5 <= old, (new, old)

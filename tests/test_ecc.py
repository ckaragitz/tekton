"""Ground-truth tests for the .rvt per-page ECC ("353-byte trailer").

The page trailer is the parity of an I-way bit-interleaved binary cyclic
Hamming code (generator g(x) = h_m(x^I); full page: I=255, m=11,
g(x) = x^2805 + x^510 + 1).  Two independent implementations must reproduce
every real trailer BYTE-EXACTLY:

  * ``rvt.ecc``                    -- production module (ecc-intel: recovered
                                      from Utility.dll ``Foundation/Utility/CRCIO.cpp``)
  * ``experiments/ecc/rs_search``  -- black-box algebraic crack (ecc-rs-search:
                                      big-int GF(2) polynomial encoder + geometry
                                      fitted purely from the ground-truth corpus)

Ground truth = the six ``samples/*.rvt`` files (every full page and every
final partial page of every ECC-framed stream).
"""
from __future__ import annotations

import os
import sys

import pytest

from rvt import ecc
from rvt.container import PAGE_PAYLOAD, PAGE_STRIDE, open_rvt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "samples")
sys.path.insert(0, os.path.join(ROOT, "experiments", "ecc"))
import rs_search as rsc  # noqa: E402  (independent oracle implementation)

FILES = [
    "dach-sample-project", "racadvancedsampleproject", "racbasicsampleproject",
    "rmebasicsampleproject", "rstadvancedsampleproject", "rstbasicsampleproject",
]
NO_ECC = ecc_no = {"BasicFileInfo", "PartAtomXML", "TransmissionData",
                    "ProjectInformation", "RevitPreview4.0"}

pytestmark = pytest.mark.skipif(
    not all(os.path.exists(os.path.join(SAMPLES, f + ".rvt")) for f in FILES),
    reason="sample .rvt corpus not present")


@pytest.fixture(scope="module")
def docs():
    return {f: open_rvt(os.path.join(SAMPLES, f + ".rvt")) for f in FILES}


def _ecc_streams(doc):
    return [s.name for s in doc.streams()
            if s.name.split("/")[-1] not in NO_ECC and doc.raw(s.name)]


# ---------------------------------------------------------------------------
# full pages
# ---------------------------------------------------------------------------

def test_full_page_generator_constant():
    """g(x) = h11(x^255) = x^2805 + x^510 + 1 for full pages."""
    assert rsc.gpoly_lows(255, 11) == (510, 0)
    g = rsc.geometry(PAGE_PAYLOAD)
    assert (g.I, g.m, g.k) == (255, 11, 2036)
    assert (g.zero_bytes, g.zero_bits, g.field_bits, g.t_pad) == (0, 3, 9, 7)
    assert g.raw_bytes == PAGE_STRIDE and g.trailer_bytes == 353


@pytest.mark.parametrize("fname", FILES)
def test_full_page_trailers_byte_exact_both_impls(docs, fname):
    """>=20 full pages per file (all of them for the small files), both
    implementations, byte-exact."""
    doc = docs[fname]
    n = 0
    for name in _ecc_streams(doc):
        raw = doc.raw(name)
        k = 0
        while (k + 1) * PAGE_STRIDE <= len(raw) and n < 60:
            page = raw[k * PAGE_STRIDE:k * PAGE_STRIDE + PAGE_PAYLOAD]
            want = raw[k * PAGE_STRIDE + PAGE_PAYLOAD:(k + 1) * PAGE_STRIDE]
            assert ecc.page_trailer(page) == want, (fname, name, k, "rvt.ecc")
            assert rsc.page_trailer(page) == want, (fname, name, k, "rs_search")
            k += 1
            n += 1
    assert n >= 20 or fname == "dach-sample-project", (fname, n)


def test_formats_latest_all_full_pages_all_files(docs):
    """Formats/Latest is byte-identical in all six files; every one of its
    full pages and its final page reproduce exactly (the brief's test rig)."""
    for fname in FILES:
        raw = docs[fname].raw("Formats/Latest")
        page, trailer = raw[:PAGE_PAYLOAD], raw[PAGE_PAYLOAD:PAGE_STRIDE]
        assert ecc.page_trailer(page) == trailer
        assert rsc.page_trailer(page) == trailer


# ---------------------------------------------------------------------------
# final partial pages
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fname", FILES)
def test_final_pages_byte_exact_both_impls(docs, fname):
    """Every ECC stream's final partial page: recover its geometry + exact
    payload length from the raw bytes (rs_search.resolve_page), then both
    encoders must regenerate the stored tail byte-for-byte."""
    doc = docs[fname]
    n = 0
    for name in _ecc_streams(doc):
        raw = doc.raw(name)
        n_full = len(raw) // PAGE_STRIDE
        tail = raw[n_full * PAGE_STRIDE:]
        if not tail:
            continue
        geo = rsc.resolve_page(tail)
        assert geo is not None, (fname, name, "no consistent ECC geometry")
        payload = tail[:geo.payload]
        assert rsc.encode(payload) == tail, (fname, name, "rs_search")
        assert ecc.encode_block(payload, ecc.select_params(len(payload))) == tail, (fname, name, "rvt.ecc")
        n += 1
    assert n >= 8, (fname, n)


# ---------------------------------------------------------------------------
# whole-stream framing + the two implementations agree everywhere
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fname", ["rstbasicsampleproject", "racbasicsampleproject"])
def test_reframe_whole_streams(docs, fname):
    """exact logical (payload) -> frame -> identical raw stream."""
    doc = docs[fname]
    for name in _ecc_streams(doc):
        raw = doc.raw(name)
        logical = rsc.unframe(raw)            # verifies every page's syndrome
        assert rsc.frame(logical) == raw, (fname, name, "rs_search.frame")
        assert ecc.frame_stream(logical) == raw, (fname, name, "rvt.ecc.frame_stream")


def test_implementations_agree_for_every_payload_length():
    """Same class m and same raw size for every possible page payload length."""
    for L in range(1, PAGE_PAYLOAD + 1):
        p = ecc.select_params(L)
        n = ecc.size_field_bits(p[2], p[3])
        g = rsc.geometry(L)
        assert p[0] == g.m, L
        assert ecc.encoded_size(L, p[0], p[2], p[3], n) == g.raw_bytes, L


def test_random_payloads_encode_identically():
    import random

    rng = random.Random(20260802)
    for _ in range(60):
        L = rng.choice([rng.randint(1, 300), rng.randint(300, 6000),
                        rng.randint(6000, PAGE_PAYLOAD)])
        data = bytes(rng.getrandbits(8) for _ in range(L))
        assert ecc.encode_block(data, ecc.select_params(L)) == rsc.encode(data), L


def test_no_ecc_streams_are_not_codewords(docs):
    """Metadata streams (BasicFileInfo, TransmissionData, ...) carry no ECC."""
    doc = docs["rstbasicsampleproject"]
    for name in ("BasicFileInfo", "TransmissionData", "ProjectInformation"):
        raw = doc.raw(name)
        assert rsc.resolve_page(raw) is None, name

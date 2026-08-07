"""ecc-intel: ground-truth checks for the CRCIO page-trailer encoder.

Reproduces real Revit page trailers byte-exactly from page payloads using
``rvt.ecc`` (the cracked Foundation/Utility/CRCIO.cpp interleaved-CRC code).
See docs/inbox/ecc-intel.md for the algorithm and evidence chain.
"""
import os

import pytest

from rvt import ecc
from rvt.container import PAGE_PAYLOAD, PAGE_STRIDE, open_rvt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLE = os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt")

pytestmark = pytest.mark.skipif(not os.path.exists(SAMPLE),
                                reason="sample .rvt not present")


@pytest.fixture(scope="module")
def doc():
    return open_rvt(SAMPLE)


def test_first_page_trailer_byte_exact(doc):
    raw = doc.raw("Formats/Latest")
    page, trailer = raw[:PAGE_PAYLOAD], raw[PAGE_PAYLOAD:PAGE_STRIDE]
    assert ecc.page_trailer(page) == trailer


@pytest.mark.parametrize("stream", ["Formats/Latest", "Global/Latest",
                                    "Global/ElemTable", "Global/History"])
def test_all_full_page_trailers_byte_exact(doc, stream):
    raw = doc.raw(stream)
    n_full = len(raw) // PAGE_STRIDE
    for k in range(n_full):
        page = raw[k * PAGE_STRIDE:k * PAGE_STRIDE + PAGE_PAYLOAD]
        trailer = raw[k * PAGE_STRIDE + PAGE_PAYLOAD:(k + 1) * PAGE_STRIDE]
        assert ecc.page_trailer(page) == trailer, (stream, k)


def _exact_payload_len(tail: bytes) -> int:
    """Recover the payload length of a final partial page from its index
    field (mirrors CRCIO's read side)."""
    import math

    def sizes_total(p, S):
        m, _poly, period, align = p
        bits = S * 8
        n = bits // period
        if n > 65:
            n -= (n - 65) % align
        if n < 65:
            return (bits // 65, 65)
        return (period, n)

    def cap(p, S):
        m = p[0]
        f, s = sizes_total(p, S)
        b = (f - m) * s
        ib = ecc.size_field_bits(p[2], p[3])
        return ((b - ib) >> 3) if b > ib else 0

    def plen(p, D):
        return ecc.encoded_size(D, p[0], p[2], p[3],
                                ecc.size_field_bits(p[2], p[3]))

    A = []
    for i in range(len(ecc.PARAM_CLASSES) - 1):
        hi, lo = ecc.PARAM_CLASSES[i], ecc.PARAM_CLASSES[i + 1]
        V = math.ceil(hi[0] * lo[2] / lo[0])
        T = ((V * 65 + 7) >> 3) - 1
        A.append(plen(lo, cap(hi, T)))
    L = len(tail)
    p = ecc.PARAM_CLASSES[0]
    for j in range(len(A) - 1, -1, -1):
        if A[j] >= L:
            p = ecc.PARAM_CLASSES[j + 1]
            break
    m = p[0]
    ib = ecc.size_field_bits(p[2], p[3])
    f, N = sizes_total(p, L)
    dab = (f - m) * N
    idx = 0
    for i in range(ib):
        q = dab - ib + i
        idx |= ((tail[q >> 3] >> (q & 7)) & 1) << i
    return ((dab - ib) >> 3) - idx


@pytest.mark.parametrize("stream", ["Global/History", "Global/PartitionTable",
                                    "Contents", "Global/ElemTable"])
def test_whole_stream_reframe_byte_exact(doc, stream):
    """exact-unframe then re-frame reproduces the raw stream exactly."""
    raw = doc.raw(stream)
    n_full = len(raw) // PAGE_STRIDE
    logical = bytearray()
    for k in range(n_full):
        logical += raw[k * PAGE_STRIDE:k * PAGE_STRIDE + PAGE_PAYLOAD]
    tail = raw[n_full * PAGE_STRIDE:]
    if tail:
        logical += tail[:_exact_payload_len(tail)]
    assert ecc.frame_stream(bytes(logical)) == raw

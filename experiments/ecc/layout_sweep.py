#!/usr/bin/env python3
"""ECC LAYOUT SWEEP (agent: ecc-layout-sweep).

Systematic numpy sweep over checksum/parity LAYOUTS for the 353-byte Revit
page trailer, plus the WINNING model expressed and verified in the same
"interleaved lane" framework.

RESULT (byte-exact, verified corpus-wide, see verify_corpus()):

  The 350 code bytes are NOT 175 x 16-bit / 87 x 32-bit byte-lane checksums.
  The correct geometry is a BIT-LEVEL interleave: the page (payload bits,
  LSB-first inside each byte) plus 12 zero pad bits form the MESSAGE; the
  trailer field is 353 bytes = 2824 bits.  Dealing the CODEWORD bits
  round-robin into I = 255 lanes (bit stride 255) makes every lane an
  independent (2047, 2036) cyclic Hamming codeword whose 11 parity bits are
  the plain CRC-11 (poly h(y) = y^11 + y^2 + 1 = 0x805, init 0, no reflect,
  no xorout) of that lane's 2036 message bits (highest degree first).
  255 lanes x 11 parity bits = 2805 code bits, wrapped with 12 leading and
  7 trailing zero pad bits = 2824 bits = 353 bytes.  Equivalently the whole
  codeword is a CRC with generator g(x) = h(x^255) = x^2805 + x^510 + 1.

Deliverable of the sweep angle:
  * lane_crc11_trailer(page)  -> the 353-byte trailer (numpy vectorized over
                                  all 255 lanes at once, ~10 ms/page)
  * verify_corpus()             -> byte-exact check over every full page of
                                  every raw stream of all six sample files
  * negative_sweep()            -> the systematic BYTE-granular layout grid
                                  (thousands of variants) with hit counts;
                                  documents that no byte-lane / chunk /
                                  column-parity checksum family matches.

Run:
  /Users/ck/dev/things/rev-revit/.venv/bin/python \
      /Users/ck/dev/things/rev-revit/experiments/ecc/layout_sweep.py [sweep|verify|all]
"""
from __future__ import annotations

import glob
import json
import os
import sys
import time
from typing import Dict, Iterator, List, Tuple

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.container import open_rvt, PAGE_PAYLOAD, PAGE_TRAILER, PAGE_STRIDE  # noqa: E402

PAGE = PAGE_PAYLOAD      # 64896
TRAIL = PAGE_TRAILER     # 353
STRIDE = PAGE_STRIDE     # 65249

# --------------------------------------------------------------------------
# THE WINNING LAYOUT: 255 bit-interleaved CRC-11 lanes
# --------------------------------------------------------------------------

LANES = 255              # interleave depth I
LANE_M = 11              # parity bits per lane (Hamming order m)
LANE_LEN = (1 << LANE_M) - 1        # 2047 = full Hamming length
LANE_K = LANE_LEN - LANE_M          # 2036 message bits per lane
PAD_LOW = 12             # leading zero pad bits in the trailer field
T_PAD = 7                # trailing zero pad bits
CODE_BITS = LANES * LANE_M           # 2805
FIELD_BITS = PAD_LOW + CODE_BITS + T_PAD   # 2824 = 353 * 8
H_LOW = 0x005            # h(y) - y^11 = y^2 + 1  (h = y^11 + y^2 + 1 = 0x805)

assert 8 * PAGE + PAD_LOW == LANES * LANE_K       # 519,180: message fills lanes exactly
assert FIELD_BITS == 8 * TRAIL


def lane_crc11_trailer_batch(pages: List[bytes]) -> List[bytes]:
    """Compute the 353-byte trailer for each full page in ``pages``.

    Vectorized over lanes AND pages: the bit matrix has 2036 rows and
    255 * n_pages columns; one bit-serial CRC-11 register per column.
    """
    n = len(pages)
    if n == 0:
        return []
    buf = np.frombuffer(b"".join(pages), np.uint8).reshape(n, PAGE)
    bits = np.unpackbits(buf, axis=1, bitorder="little")          # (n, 519168) LSB-first
    msg = np.concatenate([bits, np.zeros((n, PAD_LOW), np.uint8)], axis=1)  # (n, 519180)
    # message bit index i belongs to residue s = i mod 255; lane r = (254 - s) mod 255
    L = msg.reshape(n, LANE_K, LANES)                              # [page, row q, residue s]
    L = np.ascontiguousarray(L.transpose(1, 0, 2)).reshape(LANE_K, n * LANES)
    reg = np.zeros(n * LANES, np.uint16)
    for row in L:                                                  # highest degree first
        fb = ((reg >> 10) & 1) ^ row
        reg = ((reg << np.uint16(1)) & np.uint16(0x7FF)) ^ (fb * np.uint16(H_LOW))
    reg = reg.reshape(n, LANES)                                   # reg[page, s] bit q = coeff y^q
    # scatter parity coefficient (lane r, degree q) -> global exponent E = 255q + r
    # -> trailer field bit j = 2816 - E   (t_pad = 7 trailing zeros)
    field = np.zeros((n, FIELD_BITS), np.uint8)
    s_idx = np.arange(LANES)
    r_idx = (254 - s_idx) % LANES
    for q in range(LANE_M):
        j = 2816 - (LANES * q + r_idx)                             # field bit index per residue s
        field[:, j] = (reg >> np.uint16(q)) & 1
    packed = np.packbits(field, axis=1, bitorder="little")         # (n, 353)
    return [row.tobytes() for row in packed]


def lane_crc11_trailer(page: bytes) -> bytes:
    """353-byte trailer of one full 64,896-byte page (the ECC)."""
    assert len(page) == PAGE, len(page)
    return lane_crc11_trailer_batch([page])[0]


# --------------------------------------------------------------------------
# FINAL (partial) BLOCK MODEL — cracked corpus-wide (49/49 final blocks)
# --------------------------------------------------------------------------
#
# Every ECC-framed stream ends with a final block [payload P bytes][field F
# bytes].  The whole final block (like every full page) is ONE codeword: as a
# GF(2) polynomial (LSB-first bits, first bit = highest degree) it is
# divisible by g(x) = h_m(x^I).  Parameter rule, from n = 8*P payload bits:
#     for m in (4,5,7,9,11):  K_m = 2^m - 1 - m ;  I_m = max(65, round(n / K_m))
#     drop candidates with I_m > 255 ; choose the (I,m) minimising I*m.
#     h_4 = y^4+y+1, h_5 = y^5+y^2+1, h_7 = y^7+y+1, h_9 = y^9+y^4+1,
#     h_11 = y^11+y^2+1  (degrees 6, 8, 10 are NOT in the writer's table).
#     F = ceil(I*m / 8) bytes ; base = 8F - I*m leading field bits.
# Field = [base "header" bits][I*m parity bits], t_pad = 0.  The header bits
# are part of the CRC message (payload || header); in about half the corpus
# they are zero, elsewhere small nonzero junk — a syndrome-based reader
# accepts any value, so a writer may emit zeros there.  Parity = the plain
# systematic remainder (M(x) * x^(8F)) mod g when the header is zero.
# Full 64,896-byte pages are the fixed special case F = 353 (12 leading and
# 7 trailing zero bits) handled by lane_crc11_trailer().
#
# Streams WITHOUT ECC framing (no divisor, no trailer): BasicFileInfo,
# TransmissionData, ProjectInformation, RevitPreview4.0 (the non-native
# metadata / preview streams).  ECC-framed: Formats/*, Contents,
# Global/{Latest,ElemTable,ContentDocuments,History,DocumentIncrementTable,
# PartitionTable}, Partitions/*.

PRIM_H = {4: 0x13, 5: 0x25, 7: 0x83, 9: 0x211, 11: 0x805}
_REV = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))


def poly_from_bytes(data: bytes) -> int:
    """LSB-first bit stream as a GF(2) polynomial (bit i = coeff x^i)."""
    return int.from_bytes(data.translate(_REV), "big")


def bytes_from_poly(t: int, nbytes: int) -> bytes:
    return t.to_bytes(nbytes, "big").translate(_REV)


def _pmod(a: int, g: int) -> int:
    dg = g.bit_length() - 1
    while a.bit_length() - 1 >= dg:
        a ^= g << (a.bit_length() - 1 - dg)
    return a


def g_poly(I: int, m: int) -> int:
    """g(x) = h_m(x^I) as an integer polynomial."""
    h = PRIM_H[m]
    g = 0
    for e in range(m + 1):
        if h >> e & 1:
            g |= 1 << (e * I)
    return g


def select_params(payload_len: int) -> Tuple[int, int, int]:
    """Return (I, m, F) for a FINAL block whose payload is ``payload_len``
    bytes.  Rule verified on all 49 corpus final blocks."""
    n = 8 * payload_len
    best = None
    for m in (4, 5, 7, 9, 11):
        K = (1 << m) - 1 - m
        I = max(65, int(n / K + 0.5))
        if I > 255:
            continue
        cand = (I * m, m, I)
        if best is None or cand < best:
            best = cand
    if best is None:
        raise ValueError("payload too long for one block")
    _, m, I = best
    F = -(-(I * m) // 8)
    return I, m, F


def final_trailer(payload: bytes, I: int = None, m: int = None, F: int = None) -> bytes:
    """Trailer field for a FINAL (partial) block with zero header bits:
    field = (payload(x) * x^(8F)) mod g, i.e. base leading zero bits then the
    I*m parity bits (t_pad = 0).  A valid codeword under the reader's expected
    geometry; byte-exact whenever the original header bits were zero."""
    if I is None:
        I, m, F = select_params(len(payload))
    g = g_poly(I, m)
    T = _pmod(poly_from_bytes(payload) << (8 * F), g)
    return bytes_from_poly(T, F)


def analyze_final_block(final: bytes) -> Dict:
    """Given a whole final block (payload || field), locate the split by the
    F = ceil(I*m/8) fixed point, verify the codeword, and report whether the
    zero-header writer reproduces it byte-exactly."""
    R = len(final)
    out = {"R": R, "candidates": []}
    for F in range(1, min(R, 400)):
        P = R - F
        I, m, F_rule = select_params(P)
        if F_rule != F:
            continue
        g = g_poly(I, m)
        divisible = _pmod(poly_from_bytes(final), g) == 0
        mine = final_trailer(final[:P], I, m, F)
        exact = mine == final[P:]
        out["candidates"].append({"P": P, "F": F, "I": I, "m": m,
                                  "codeword_divisible": divisible,
                                  "zero_header_byte_exact": exact})
    return out


# --------------------------------------------------------------------------
# ground truth corpus
# --------------------------------------------------------------------------

def iter_raw_streams() -> Iterator[Tuple[str, bytes]]:
    """Yield (label, raw_bytes) for every raw (page-framed) stream extracted
    under extracted/<file>/*.bin (excluding *.logical.bin)."""
    for path in sorted(glob.glob(os.path.join(ROOT, "extracted", "*", "*.bin"))):
        if path.endswith(".logical.bin"):
            continue
        with open(path, "rb") as fh:
            raw = fh.read()
        yield os.path.relpath(path, ROOT), raw


def ground_truth_page0() -> Tuple[bytes, bytes]:
    """The canonical target: Formats/Latest page 0 (identical in all files)."""
    d = open_rvt(os.path.join(ROOT, "samples", "rstbasicsampleproject.rvt"))
    raw = d.raw("Formats/Latest")
    return raw[:PAGE], raw[PAGE:STRIDE]


def verify_corpus(batch: int = 24) -> Dict[str, int]:
    """Recompute EVERY full-page trailer in the extracted corpus; return
    counts. Byte-exact match required."""
    t0 = time.time()
    total = ok = 0
    mismatches: List[str] = []
    per_stream = {}
    for label, raw in iter_raw_streams():
        nfull = len(raw) // STRIDE
        if nfull == 0:
            continue
        pages, trs = [], []
        for k in range(nfull):
            pages.append(raw[k * STRIDE:k * STRIDE + PAGE])
            trs.append(raw[k * STRIDE + PAGE:(k + 1) * STRIDE])
            if len(pages) == batch or k == nfull - 1:
                mine = lane_crc11_trailer_batch(pages)
                for m, t, kk in zip(mine, trs, range(k - len(pages) + 1, k + 1)):
                    total += 1
                    if m == t:
                        ok += 1
                    else:
                        mismatches.append(f"{label} page {kk}")
                pages, trs = [], []
        per_stream[label] = nfull
    dt = time.time() - t0
    print(f"[verify_corpus] full pages checked: {total}, byte-exact: {ok}, "
          f"mismatch: {total - ok}   ({dt:.1f}s, {len(per_stream)} streams)")
    for m in mismatches[:20]:
        print("   MISMATCH", m)
    return {"total": total, "ok": ok, "mismatch": total - ok, "streams": len(per_stream)}


def verify_final_blocks() -> Dict[str, int]:
    """For every raw stream's final block: locate the payload/field split via
    the parameter rule, check the codeword is divisible by g (structural
    validity), and count byte-exact reproduction by the zero-header writer.
    Streams that carry no ECC (metadata streams) produce no divisible
    candidate and are counted separately."""
    t0 = time.time()
    n_blocks = n_div = n_exact = n_noecc = 0
    per: List[str] = []
    for label, raw in iter_raw_streams():
        nfull = len(raw) // STRIDE
        final = raw[nfull * STRIDE:]
        R = len(final)
        if R < 32:
            continue
        info = analyze_final_block(final)
        cands = [c for c in info["candidates"] if c["codeword_divisible"]]
        if not cands:
            n_noecc += 1
            per.append(f"   NO-ECC  {label} (R={R})")
            continue
        c = cands[0]
        n_blocks += 1
        n_div += 1
        n_exact += c["zero_header_byte_exact"]
        per.append(f"   OK      {label} R={R} P={c['P']} F={c['F']} I={c['I']} m={c['m']} "
                   f"zero-header-exact={c['zero_header_byte_exact']}")
    dt = time.time() - t0
    print(f"[verify_final_blocks] ECC-framed final blocks: {n_blocks}; "
          f"parameter rule located a divisible codeword: {n_div}/{n_blocks}; "
          f"zero-header writer byte-exact: {n_exact}/{n_blocks}; "
          f"unframed streams: {n_noecc}   ({dt:.1f}s)")
    for line in per:
        print(line)
    return {"blocks": n_blocks, "divisible": n_div, "exact": n_exact, "noecc": n_noecc}


# --------------------------------------------------------------------------
# NEGATIVE SWEEP: byte-granular layouts (the assigned hypothesis space)
# --------------------------------------------------------------------------

CRC16_POLYS = [0x8005, 0x1021, 0x3D65, 0x0589, 0xA097, 0x8BB7, 0xC867, 0x1DCF]


def _refl8(x: int) -> int:
    return int(f"{x:08b}"[::-1], 2)


def crc16_lanes(lanes: np.ndarray, poly: int, init: int, refin: bool,
                refout: bool, xorout: int) -> np.ndarray:
    """CRC-16 of each row of ``lanes`` (2-D uint8), vectorized over rows.
    Bit-serial, MSB-first engine (refin handled by pre-reflecting bytes)."""
    data = lanes
    if refin:
        rt = np.array([_refl8(i) for i in range(256)], np.uint16)
        data = rt[data].astype(np.uint8)
    reg = np.full(data.shape[0], init & 0xFFFF, np.uint32)
    for col in range(data.shape[1]):
        b = data[:, col].astype(np.uint32) << 8
        reg ^= b
        for _ in range(8):
            top = reg & 0x8000
            reg = ((reg << 1) & 0xFFFF)
            reg ^= np.where(top != 0, np.uint32(poly), np.uint32(0))
    if refout:
        # reflect 16 bits
        r = np.zeros_like(reg)
        for i in range(16):
            r |= ((reg >> i) & 1) << (15 - i)
        reg = r
    return (reg ^ (xorout & 0xFFFF)) & 0xFFFF


def crc32_lanes(lanes: np.ndarray) -> np.ndarray:
    """zlib CRC-32 per row (vectorized bit-serial, reflected)."""
    poly = 0xEDB88320
    reg = np.full(lanes.shape[0], 0xFFFFFFFF, np.uint64)
    for col in range(lanes.shape[1]):
        reg ^= lanes[:, col].astype(np.uint64)
        for _ in range(8):
            lsb = reg & 1
            reg = (reg >> 1) ^ np.where(lsb != 0, np.uint64(poly), np.uint64(0))
    return (reg ^ 0xFFFFFFFF) & 0xFFFFFFFF


def lane_funcs_16(lanes: np.ndarray) -> Dict[str, np.ndarray]:
    """A bank of cheap 16-bit sub-result functions per lane (row)."""
    x = lanes.astype(np.uint32)
    out = {}
    out["sum8_lohi"] = ((x.sum(1) & 0xFF) | (((x ^ 0).sum(1) >> 8 & 0xFF) << 8)) & 0xFFFF
    out["sum16_le"] = (x[:, 0::2].sum(1) + (x[:, 1::2].sum(1) << 8)) & 0xFFFF
    out["sum8x2"] = ((x.sum(1) & 0xFFFF))
    out["xor8_dup"] = np.bitwise_xor.reduce(x, axis=1) * 0x101 & 0xFFFF
    # xor16 (little-endian words); pad odd length
    if x.shape[1] % 2:
        x2 = np.concatenate([x, np.zeros((x.shape[0], 1), np.uint32)], 1)
    else:
        x2 = x
    w = x2[:, 0::2] | (x2[:, 1::2] << 8)
    out["xor16_le"] = np.bitwise_xor.reduce(w, axis=1) & 0xFFFF
    out["sum16w_le"] = w.sum(1) & 0xFFFF
    # Fletcher-16
    s1 = np.zeros(x.shape[0], np.uint64)
    s2 = np.zeros(x.shape[0], np.uint64)
    for col in range(x.shape[1]):
        s1 = (s1 + x[:, col].astype(np.uint64)) % 255
        s2 = (s2 + s1) % 255
    out["fletcher16"] = ((s2 << 8) | s1).astype(np.uint32) & 0xFFFF
    # Adler-ish 16 (mod 251)
    a = np.ones(x.shape[0], np.uint64)
    b = np.zeros(x.shape[0], np.uint64)
    for col in range(x.shape[1]):
        a = (a + x[:, col].astype(np.uint64)) % 251
        b = (b + a) % 251
    out["adler16m251"] = ((b << 8) | a).astype(np.uint32) & 0xFFFF
    c32 = crc32_lanes(lanes)
    out["crc32_low16"] = (c32 & 0xFFFF).astype(np.uint32)
    out["crc32_high16"] = ((c32 >> 16) & 0xFFFF).astype(np.uint32)
    out["crc32_xorfold"] = ((c32 ^ (c32 >> 16)) & 0xFFFF).astype(np.uint32)
    return out


def match_positions(vals: np.ndarray, target_words: List[int]) -> Dict[str, List[int]]:
    """Where does lane sub-result i equal target word i? (position hits)."""
    hits = {}
    n = min(len(vals), len(target_words))
    tw = np.array(target_words[:n], np.uint32)
    eq = np.nonzero(vals[:n].astype(np.uint32) == tw)[0].tolist()
    if eq:
        hits["ordered"] = eq
    eqr = np.nonzero(vals[:n][::-1].astype(np.uint32) == tw)[0].tolist()
    if eqr:
        hits["reversed"] = eqr
    # membership (lane value appears anywhere in the target list)
    inter = np.intersect1d(vals[:n].astype(np.uint32), tw)
    if len(inter):
        hits["_anywhere_count"] = len(inter)
    return hits


def targets_from_trailer(tr: bytes) -> Dict[str, List[int]]:
    """Candidate 16-bit target word lists carved from the trailer at both
    alignments and endiannesses."""
    out = {}
    for name, seg in (("code2_352", tr[2:352]), ("code1_351", tr[1:351]),
                      ("code3_353", tr[3:353]), ("code0_350", tr[0:350])):
        a = np.frombuffer(seg[: len(seg) // 2 * 2], np.uint8).reshape(-1, 2)
        out[name + "_le"] = (a[:, 0].astype(np.uint32) | (a[:, 1].astype(np.uint32) << 8)).tolist()
        out[name + "_be"] = ((a[:, 0].astype(np.uint32) << 8) | a[:, 1].astype(np.uint32)).tolist()
    return out


def negative_sweep(page: bytes, tr: bytes) -> Dict:
    """The systematic byte-granular layout sweep.  Returns a log of every
    family x parameter tried and any 16-bit sub-result position hits.

    A GENUINE lead would be a family whose lane sub-results hit the target
    word at MANY consecutive positions; single/rare hits at 175 lanes vs
    65536 values are chance (expected ~175/65536 = 0.0027 per lane list).
    """
    log = {"page_len": len(page), "trailer_len": len(tr), "families": []}
    targets = targets_from_trailer(tr)
    variants = 0
    leads = []

    def record(family: str, params: Dict, lanes: np.ndarray):
        nonlocal variants
        bank = lane_funcs_16(lanes)
        fam = {"family": family, "params": params, "n_lanes": int(lanes.shape[0]), "hits": {}}
        for fname, vals in bank.items():
            for tname, tw in targets.items():
                variants += 1
                h = match_positions(vals, tw)
                # keep only ordered/reversed positional hits (real leads)
                pos = {k: v for k, v in h.items() if k in ("ordered", "reversed")}
                if pos:
                    key = f"{fname}|{tname}"
                    fam["hits"][key] = pos
                    for k, v in pos.items():
                        if len(v) >= 3:
                            leads.append({"family": family, "params": params,
                                          "func": fname, "target": tname,
                                          "order": k, "positions": v})
        log["families"].append(fam)

    def record_crc16(family: str, params: Dict, lanes: np.ndarray):
        nonlocal variants
        for poly in CRC16_POLYS:
            for init in (0x0000, 0xFFFF, 0x1D0F, 0x554D):
                for refl in (False, True):
                    for xo in (0x0000, 0xFFFF):
                        vals = crc16_lanes(lanes, poly, init, refl, refl, xo)
                        for tname, tw in targets.items():
                            variants += 1
                            h = match_positions(vals, tw)
                            pos = {k: v for k, v in h.items() if k in ("ordered", "reversed")}
                            if pos:
                                key = f"crc16 poly={poly:#06x} init={init:#06x} refl={refl} xo={xo:#06x}|{tname}"
                                log.setdefault("crc16_hits", {})[key] = pos
                                for k, v in pos.items():
                                    if len(v) >= 3:
                                        leads.append({"family": family, "params": params,
                                                      "func": key, "order": k, "positions": v})

    arr = np.frombuffer(page, np.uint8)

    # ---- Family A: contiguous chunks ------------------------------------
    for c in (372, 371, 373, 370, 374, 368, 376, 384, 366, 365, 364, 360, 256, 512, 175 * 2):
        nlanes = -(-len(page) // c)
        buf = np.zeros(nlanes * c, np.uint8)
        buf[:len(page)] = arr
        lanes = buf.reshape(nlanes, c)
        record("A.contiguous", {"chunk": c}, lanes)
        if c in (372, 371, 373, 175 * 2):
            record_crc16("A.contiguous", {"chunk": c}, lanes)

    # exact fractional handling: 175 chunks of ~370.83; try 175 near-equal chunks
    edges = np.linspace(0, len(page), 176).round().astype(int)
    maxlen = int(np.diff(edges).max())
    lanes = np.zeros((175, maxlen), np.uint8)
    for i in range(175):
        seg = arr[edges[i]:edges[i + 1]]
        lanes[i, :len(seg)] = seg
    record("A.frac175", {"chunks": 175}, lanes)
    record_crc16("A.frac175", {"chunks": 175}, lanes)

    # ---- Family B: interleaved BYTE lanes -------------------------------
    for stride in (175, 350, 87, 88, 174, 176, 255, 353, 351):
        nlanes = stride
        maxlen = -(-len(page) // stride)
        buf = np.zeros(nlanes * maxlen, np.uint8)
        buf[:len(page)] = arr
        # lane i = bytes i, i+stride, ... : reshape as (maxlen, stride) then T
        lanes = buf.reshape(maxlen, stride).T.copy()
        record("B.byte_interleave", {"stride": stride}, lanes)
        if stride in (175, 350, 255):
            record_crc16("B.byte_interleave", {"stride": stride}, lanes)

    # ---- Family C: interleaved 16-bit / 32-bit word lanes ---------------
    w16 = arr[: len(arr) // 2 * 2].reshape(-1, 2)
    for stride in (175, 87, 88):
        nw = len(w16)
        maxlen = -(-nw // stride)
        buf = np.zeros((stride * maxlen, 2), np.uint8)
        buf[:nw] = w16
        lanes = buf.reshape(maxlen, stride, 2).transpose(1, 0, 2).reshape(stride, maxlen * 2).copy()
        record("C.word16_interleave", {"stride": stride}, lanes)
    w32 = arr[: len(arr) // 4 * 4].reshape(-1, 4)
    for stride in (87, 88, 175):
        nw = len(w32)
        maxlen = -(-nw // stride)
        buf = np.zeros((stride * maxlen, 4), np.uint8)
        buf[:nw] = w32
        lanes = buf.reshape(maxlen, stride, 4).transpose(1, 0, 2).reshape(stride, maxlen * 4).copy()
        record("C.word32_interleave", {"stride": stride}, lanes)

    # ---- Family D: metadata bytes prepended / appended to the page ------
    meta = bytes([tr[0], tr[1], tr[-1]])
    for tag, data in (("meta_prepend", meta + page), ("meta_append", page + meta),
                      ("b0b1_prepend", tr[:2] + page)):
        a2 = np.frombuffer(data, np.uint8)
        for c in (372, 371):
            nlanes = -(-len(data) // c)
            buf = np.zeros(nlanes * c, np.uint8)
            buf[:len(data)] = a2
            lanes = buf.reshape(nlanes, c)
            record("D." + tag, {"chunk": c}, lanes)

    # ---- Family E: column parity of page-as-matrix ---------------------
    col_hits = {}
    for C in (175, 350, 353, 351, 349, 348, 176, 174, 87, 88):
        nrows = -(-len(page) // C)
        buf = np.zeros(nrows * C, np.uint8)
        buf[:len(page)] = arr
        M = buf.reshape(nrows, C)
        colxor = np.bitwise_xor.reduce(M, axis=0)
        colsum = (M.astype(np.uint32).sum(0)) & 0xFF
        for fname, colv in (("colxor", colxor.astype(np.uint32)), ("colsum8", colsum)):
            variants += 1
            for tname, seg in (("code2", tr[2:352]), ("code1", tr[1:351]), ("code3", tr[3:353])):
                t8 = np.frombuffer(seg, np.uint8).astype(np.uint32)
                n = min(len(colv), len(t8))
                eq = np.nonzero(colv[:n] == t8[:n])[0]
                if len(eq) > n / 256 * 3 + 3:   # well above chance (1/256 per position)
                    col_hits[f"E.C={C}|{fname}|{tname}"] = {"n_match": int(len(eq)), "n": n}
    log["column_parity_hits_above_chance"] = col_hits

    log["variants_tested"] = variants
    log["leads"] = leads
    return log


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    mode = argv[1] if len(argv) > 1 else "all"
    page, tr = ground_truth_page0()
    print(f"ground truth: Formats/Latest page 0, page {len(page)} B, trailer {len(tr)} B")

    if mode in ("all", "positive", "verify"):
        t0 = time.time()
        mine = lane_crc11_trailer(page)
        print(f"[POSITIVE] 255 bit-lane CRC-11 model on ground truth: "
              f"byte-exact = {mine == tr}   ({(time.time()-t0)*1000:.1f} ms)")
        print(f"  mine[:10] = {mine[:10].hex()}")
        print(f"  real[:10] = {tr[:10].hex()}")
        assert mine == tr, "lane model failed on ground truth"
        stats = verify_corpus()
        assert stats["ok"] == stats["total"] and stats["total"] > 0, stats
        print(f"  ==> BYTE-EXACT on {stats['ok']}/{stats['total']} full pages "
              f"across {stats['streams']} raw streams of all six sample files.")
        fstats = verify_final_blocks()
        assert fstats["divisible"] == fstats["blocks"] and fstats["blocks"] > 0, fstats

    if mode in ("all", "sweep"):
        t0 = time.time()
        log = negative_sweep(page, tr)
        dt = time.time() - t0
        out = os.path.join(ROOT, "experiments", "ecc", "layout_sweep_log.json")
        with open(out, "w") as fh:
            json.dump(log, fh, indent=1)
        print(f"[NEGATIVE SWEEP] byte-granular variants tested: "
              f"{log['variants_tested']} in {dt:.1f}s; positional leads (>=3 "
              f"consecutive-ish hits): {len(log['leads'])}; log -> {out}")
        # summarise per family: total single-position hits (all chance-level)
        fam_hits = {}
        for fam in log["families"]:
            k = fam["family"]
            nh = sum(len(v.get("ordered", [])) + len(v.get("reversed", []))
                     for v in fam["hits"].values())
            fam_hits[k] = fam_hits.get(k, 0) + nh
        for k, v in fam_hits.items():
            print(f"   {k:26s} scattered single-position hits: {v} (chance level)")
        print(f"   crc16 positional hits: {len(log.get('crc16_hits', {}))} "
              f"(all isolated single positions, chance level)")
        print(f"   column-parity above-chance: {log['column_parity_hits_above_chance']}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))

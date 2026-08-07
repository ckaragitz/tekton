#!/usr/bin/env python3
"""ECC differential / linearity analysis of the .rvt per-page trailer.

Agent: ecc-differential.  Run:
    /Users/ck/dev/things/rev-revit/.venv/bin/python \
        /Users/ck/dev/things/rev-revit/experiments/ecc/differential.py [--fast]

What this establishes (all against the REAL corpus trailers):

  A. Corpus inventory: every (full page, trailer) pair from all six sample
     files; exact-duplicate pages carry identical trailers (keyless);
     NO natural near-duplicate full pages exist (min aligned byte-diff among
     all shingle-candidate pairs is ~64.4 KB of 64,896) -> the classic
     "near-dup differential" attack has no natural material here.

  B. The trailer map F is GF(2)-LINEAR.  We use the bit-interleaved cyclic
     code recovered by the ecc-writer-gate agent (ecc_codec.py, g(x) =
     h11(x^255) = x^2805 + x^510 + 1) and prove it IS the real F by
     reproducing every unique full-page trailer in the corpus byte-exactly
     (3,492/3,492), then run the differential tests the corpus itself
     cannot supply:
       * F(0) = 0  (no affine constant)  =>  F(A^B) = F(A)^F(B)
       * superposition confirmed on real pages: F(A^B) == T_A ^ T_B where
         T_A, T_B are the ORIGINAL Autodesk trailers of real pages A, B.
       * single-bit differentials  ->  the generator "columns".

  C. LOCALITY / support structure ("chunk -> parity map"):
       flipping page bit i changes ONLY trailer bits belonging to lane
       L(i) = (D(i) mod 255) where D(i) is the bit's polynomial degree;
       lane l owns exactly the 11 parity coefficients e = l (mod 255),
       i.e. trailer-field bit positions j = 8*353 - 1 - 7 - e.  The lane's
       delta pattern is y^s mod h11(y) (h11 = y^11 + y^2 + 1) - the column
       of a 2047-bit Hamming code.  At BYTE granularity a page byte spans
       8 consecutive degrees -> 8 lanes -> up to 88 trailer bits spread
       across the WHOLE trailer: local in the interleaved-bit domain,
       globally diffused in the byte/offset domain (this is why no
       contiguous "372-byte chunk -> 2 parity bytes" CRC ever matched).
"""
from __future__ import annotations

import collections
import glob
import hashlib
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ecc_codec  # noqa: E402  (recovered code: g = x^2805 + x^510 + 1)

from rvt.container import open_rvt, PAGE_PAYLOAD, PAGE_TRAILER, PAGE_STRIDE  # noqa: E402

PAGE_BITS = 8 * PAGE_PAYLOAD          # 519,168 message bits
FIELD_BITS = 8 * PAGE_TRAILER         # 2,824 trailer-field bits
I_DEPTH, M_ORD = 255, 11              # interleave depth, Hamming order
NPAR = I_DEPTH * M_ORD                # 2,805 parity bits
PAD_LOW, T_PAD = 12, 7                # zero bits before / after the parity


# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------

def load_corpus(files):
    """Return list of unique (page, trailer, prov-list) over all full pages."""
    uniq = {}
    total = 0
    mismatches = 0
    for f in files:
        d = open_rvt(f)
        for s in d.streams():
            raw = d.raw(s.name)
            nfull = len(raw) // PAGE_STRIDE
            for k in range(nfull):
                page = raw[k * PAGE_STRIDE:k * PAGE_STRIDE + PAGE_PAYLOAD]
                tr = raw[k * PAGE_STRIDE + PAGE_PAYLOAD:(k + 1) * PAGE_STRIDE]
                total += 1
                h = hashlib.sha1(page).digest()
                if h in uniq:
                    if uniq[h][1] != tr:
                        mismatches += 1
                    uniq[h][2].append((os.path.basename(f), s.name, k))
                else:
                    uniq[h] = (page, tr, [(os.path.basename(f), s.name, k)])
    return list(uniq.values()), total, mismatches


def near_dup_search(pages, blk=1024):
    """Aligned-block + shingle candidate search.  Returns the best pairs by
    aligned byte-diff (a near-duplicate pair would have a SMALL diff)."""
    idx = collections.defaultdict(list)
    for i, (p, _t, _pr) in enumerate(pages):
        for b in range(0, PAGE_PAYLOAD, blk):
            idx[(b, p[b:b + blk])].append(i)
    aligned_pairs = collections.Counter()
    for lst in idx.values():
        if 2 <= len(lst) <= 50:
            for a in range(len(lst)):
                for b in range(a + 1, len(lst)):
                    aligned_pairs[(lst[a], lst[b])] += 1
    # 64-byte shingles sampled 1/64 (misaligned shared content)
    sh_idx = collections.defaultdict(set)
    for i, (p, _t, _pr) in enumerate(pages):
        for off in range(0, PAGE_PAYLOAD - 64, 8):
            h = hash(p[off:off + 64])
            if h & 63 == 0:
                sh_idx[h].add(i)
    sh_pairs = collections.Counter()
    for s in sh_idx.values():
        if 2 <= len(s) <= 30:
            lst = sorted(s)
            for a in range(len(lst)):
                for b in range(a + 1, len(lst)):
                    sh_pairs[(lst[a], lst[b])] += 1
    best = []
    for (i, j), n in sh_pairs.most_common(60):
        p1, p2 = pages[i][0], pages[j][0]
        diff = sum(1 for a, b in zip(p1, p2) if a != b)
        best.append((diff, n, i, j))
    best.sort()
    return len(aligned_pairs), len(sh_pairs), best


# ---------------------------------------------------------------------------
# the linear map (bit level)
# ---------------------------------------------------------------------------

def bit_degree(i: int) -> int:
    """Degree of page bit i (LSB-first bit index) in the parity computation
    P(x) = (M(x) * x^(pad_low + 2805)) mod g(x): message bit i contributes
    x^((PAGE_BITS-1-i) + 12 + 2805).  (Codeword degree = this + t_pad(7).)"""
    return (PAGE_BITS - 1 - i) + PAD_LOW + NPAR


def field_bit_of_parity(e: int) -> int:
    """Trailer-field bit position (LSB-first index) of parity coefficient e."""
    return FIELD_BITS - 1 - T_PAD - e


def lane_of_page_bit(i: int) -> int:
    """Interleave lane owning page bit i.  Parity coefficient e belongs to
    lane e mod 255; message bit i to lane bit_degree(i) mod 255."""
    return bit_degree(i) % I_DEPTH


def lane_field_bits(lane: int):
    """The 11 trailer-field bit positions owned by ``lane`` (0..254)."""
    return sorted(field_bit_of_parity(e) for e in range(lane, NPAR, I_DEPTH))


def set_bits(b: bytes):
    return [k * 8 + t for k, v in enumerate(b) for t in range(8) if v >> t & 1]


def xor(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


def h11_mul_pow(s: int) -> int:
    """y^s mod h11(y), h11 = y^11 + y^2 + 1, as an int (bit t = coeff y^t)."""
    r = 1
    for _ in range(s):
        r <<= 1
        if r >> 11:
            r ^= (1 << 11) | 0b101
    return r


F = ecc_codec.full_page_trailer  # candidate F under test


def main() -> int:
    fast = "--fast" in sys.argv
    random.seed(20260802)
    files = sorted(glob.glob(os.path.join(ROOT, "samples", "*.rvt")))
    t0 = time.time()
    print("=" * 78)
    print("PART A - corpus & near-duplicate inventory")
    print("=" * 78)
    pages, total, mism = load_corpus(files)
    print(f"full pages: {total}   unique payloads: {len(pages)}   "
          f"trailer-mismatches among identical payloads: {mism}")
    dups = [(len(pr), pr) for (_p, _t, pr) in pages if len(pr) > 1]
    print(f"payloads occurring >1x (keyless consistency check): {len(dups)}")
    for n, pr in dups:
        print(f"  x{n}: {pr[0][1]} page {pr[0][2]} in {sorted({q[0] for q in pr})}")
    na, ns, best = near_dup_search(pages)
    print(f"aligned-1KB-block candidate pairs: {na} (0 => no page shares any"
          f" aligned 1 KiB block with another)")
    print(f"64B-shingle candidate pairs: {ns}; smallest aligned byte-diffs:")
    for diff, n, i, j in best[:8]:
        print(f"  diff={diff:6d}/64896 sharedShingles={n:3d}  {pages[i][2][0]}  {pages[j][2][0]}")
    print("=> NO natural near-duplicate full pages exist (min diff ~64.4 KB): "
          "the differential must be run through the recovered linear map instead.")

    print()
    print("=" * 78)
    print("PART B - F is GF(2)-linear; recovered map == real F on ALL pages")
    print("=" * 78)
    zero_page = bytes(PAGE_PAYLOAD)
    z = F(zero_page)
    print(f"F(0^64896) all-zero: {z == bytes(PAGE_TRAILER)}  (=> linear, no affine constant)")
    if fast:
        sample = random.sample(pages, min(400, len(pages)))
    else:
        sample = pages
    ok = 0
    bad = []
    t1 = time.time()
    for p, tr, pr in sample:
        if F(p) == tr:
            ok += 1
        else:
            bad.append(pr[0])
    print(f"real full-page trailers reproduced byte-exactly by the linear map: "
          f"{ok}/{len(sample)} ({time.time() - t1:.0f}s)")
    for b in bad[:5]:
        print("  MISMATCH", b)
    assert ok == len(sample) and z == bytes(PAGE_TRAILER)

    # superposition on REAL pages / REAL trailers
    n_sup = 40 if fast else 200
    okp = 0
    for _ in range(n_sup):
        (pa, ta, _), (pb, tb, _) = random.sample(pages, 2)
        if F(xor(pa, pb)) == xor(ta, tb):
            okp += 1
    print(f"superposition F(A^B) == T_A ^ T_B (real trailers T_A,T_B): {okp}/{n_sup}")
    assert okp == n_sup

    print()
    print("=" * 78)
    print("PART C - locality / support: single-bit differentials (generator columns)")
    print("=" * 78)
    print("page bit i (LSB-first) -> parity-poly degree D(i)=(8*64896-1-i)+2817 -> lane D(i) mod 255;")
    print("delta-trailer support must lie entirely in that lane's 11 field bits")
    print(f"{'page byte:bit':>14} {'i':>7} {'lane':>4}  delta-trailer bit positions (LSB-first)   in-lane  pattern==y^s mod h11")
    all_ok = True
    probe_bits = [0, 1, 7, 8, 100, 2039, 2040, 65535, 259583, 259584,
                  PAGE_BITS - 8, PAGE_BITS - 2, PAGE_BITS - 1]
    for i in probe_bits:
        pg = bytearray(PAGE_PAYLOAD)
        pg[i >> 3] = 1 << (i & 7)
        dt = xor(F(bytes(pg)), z)              # z is zero -> column i
        supp = set_bits(dt)
        lane = lane_of_page_bit(i)
        lanebits = lane_field_bits(lane)
        in_lane = all(b in lanebits for b in supp)
        # predicted pattern: lane substream position s of this message bit
        D = bit_degree(i)
        s = (D - lane) // I_DEPTH            # power of y = x^255 in the lane
        pat = h11_mul_pow(s)                  # coefficients over y^0..y^10
        pred = sorted(field_bit_of_parity(lane + 255 * t) for t in range(11) if pat >> t & 1)
        match = pred == supp
        all_ok &= in_lane and match
        print(f"{i>>3:>10d}:{i&7} {i:7d} {lane:4d}  {supp}  {in_lane!s:>5}  {match}")
    assert all_ok
    # byte-level locality summary
    print()
    print("byte-level: a page BYTE covers 8 consecutive degrees -> 8 distinct lanes -> up to")
    print("88 trailer bits spread every 255 field bits, i.e. across the WHOLE trailer.")
    b0 = 12345
    lanes = sorted({lane_of_page_bit(8 * b0 + t) for t in range(8)})
    touched_bytes = sorted({fb >> 3 for l in lanes for fb in lane_field_bits(l)})
    print(f"example page byte {b0}: lanes {lanes} -> trailer BYTES touched: "
          f"{touched_bytes[:6]} ... {touched_bytes[-6:]} ({len(touched_bytes)} bytes, "
          f"span {touched_bytes[0]}..{touched_bytes[-1]} of 0..352)")
    print()
    print("CLASSIFICATION: linear (GF(2)) systematic cyclic code, g(x)=x^2805+x^510+1")
    print("= 255-way BIT-interleaved [2047,2036] Hamming code (t=1 per lane; corrects any")
    print("burst <= 255 bits).  Support is LOCAL in the interleaved-bit domain (page bit ->")
    print("its lane's 11 parity bits) but GLOBALLY DIFFUSED in the byte-offset domain.")
    print(f"done in {time.time() - t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())

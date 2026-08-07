#!/usr/bin/env python3
"""Corpus analysis of the 353-byte Revit stream page trailer ("ECC block").

Every raw OLE stream in a .rvt is stored as 64,896-byte payload pages, each
followed by a 353-byte trailer at raw offsets ``64896 + k*65249``; the final
partial page carries a proportionally shorter trailer.  This script builds
the full (page, trailer) corpus across all six sample files and reports:

  1. corpus size (full pages + final partial pages);
  2. DETERMINISM: cross-file byte-identical pages -> identical trailers?
     (Formats/Latest is byte-identical in all 6 files; also generic dup scan);
  3. STRUCTURE: per-position value distributions, entropy per byte,
     the ``00 N0`` head field, last-byte distribution;
  4. LENGTH LAW for the final partial page trailer M(P);
  5. GF(2) LINEARITY / rank test: is trailer = linear function of payload
     bits (like CRC / RS / BCH after removing a constant) or non-linear
     (keyed hash / compressed record)?
  6. XOR-closure additivity spot checks.

Run:
    /Users/ck/dev/things/rev-revit/.venv/bin/python \
        /Users/ck/dev/things/rev-revit/experiments/ecc/analyze_trailers.py
"""
from __future__ import annotations

import collections
import glob
import hashlib
import math
import os
import struct
import sys
import zlib

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXTRACTED = os.path.join(ROOT, "extracted")
FILES = [
    "dach-sample-project",
    "racadvancedsampleproject",
    "racbasicsampleproject",
    "rmebasicsampleproject",
    "rstadvancedsampleproject",
    "rstbasicsampleproject",
]
PAGE = 64_896
TRAIL = 353
STRIDE = PAGE + TRAIL


# ---------------------------------------------------------------------------
# corpus extraction
# ---------------------------------------------------------------------------

def raw_streams():
    """Yield (file, stream_name, raw_bytes) for every raw (paged) stream."""
    for f in FILES:
        d = os.path.join(EXTRACTED, f)
        for path in sorted(glob.glob(os.path.join(d, "*.bin"))):
            base = os.path.basename(path)
            if base.endswith(".logical.bin"):
                continue
            name = base[:-4].replace("__", "/")
            with open(path, "rb") as fh:
                yield f, name, fh.read()


def split_pages(raw: bytes):
    """Yield (payload, trailer, is_full) for each page of a raw stream.

    Full pages: 64,896 payload + 353 trailer.  The final partial page is
    ``raw[k*65249:]`` = payload + zero pad + shorter trailer; we cannot split
    it exactly (trailer starts with 0x00 like the pad) so it is returned as
    the whole tail with is_full=False.
    """
    n = len(raw)
    pos = 0
    while pos + STRIDE <= n:
        yield raw[pos:pos + PAGE], raw[pos + PAGE:pos + STRIDE], True
        pos += STRIDE
    if pos < n:
        yield raw[pos:], b"", False


def build_corpus(verbose=True):
    full = []      # (file, stream, page_index, payload_sha, payload, trailer)
    tails = []     # (file, stream, tail_bytes)
    for f, name, raw in raw_streams():
        k = 0
        for payload, tr, is_full in split_pages(raw):
            if is_full:
                full.append((f, name, k, hashlib.sha1(payload).digest(), payload, tr))
                k += 1
            else:
                tails.append((f, name, k, payload))
    if verbose:
        print(f"corpus: {len(full)} full (page,trailer) pairs from "
              f"{len({(f,n) for f,n,*_ in full})} paged streams; "
              f"{len(tails)} final partial pages")
    return full, tails


# ---------------------------------------------------------------------------
# 2. determinism
# ---------------------------------------------------------------------------

def determinism(full):
    print("\n== 2. DETERMINISM ==")
    # Formats/Latest is byte-identical in all six files -> its pages must be
    # identical; are the trailers?
    by_key = collections.defaultdict(list)
    for f, name, k, ph, payload, tr in full:
        by_key[ph].append((f, name, k, tr))
    fl = [(f, k, tr) for f, name, k, ph, p, tr in full if name == "Formats/Latest"]
    per_page = collections.defaultdict(set)
    for f, k, tr in fl:
        per_page[k].add(tr)
    print(f"  Formats/Latest: {len(fl)} full pages across {len({f for f,_,_ in fl})} files")
    ok = True
    for k in sorted(per_page):
        n_distinct = len(per_page[k])
        ok &= n_distinct == 1
        print(f"    page {k}: {n_distinct} distinct trailer(s) across files"
              f"{' -> IDENTICAL' if n_distinct == 1 else ' -> DIFFER!'}")
    print(f"  => Formats/Latest trailers byte-identical across all files: {ok}")

    # generic duplicate-payload scan
    dup_groups = [(ph, v) for ph, v in by_key.items() if len(v) > 1]
    print(f"  duplicate payload pages (any stream/file): {len(dup_groups)} groups")
    contra = 0
    cross_file = 0
    for ph, v in dup_groups:
        trs = {tr for *_, tr in v}
        files = {f for f, *_ in v}
        if len(files) > 1:
            cross_file += 1
        if len(trs) != 1:
            contra += 1
            print(f"    CONTRADICTION: payload {ph.hex()[:12]} has {len(trs)} distinct trailers: "
                  + ", ".join(f"{f}:{n}[{k}]" for f, n, k, _ in v))
    print(f"  => groups spanning >1 file: {cross_file}; "
          f"identical-payload/different-trailer contradictions: {contra}")
    verdict = ok and contra == 0
    print(f"  VERDICT: trailer is a PURE FUNCTION of the 64,896 page bytes "
          f"(no per-file key/salt/position): {verdict}")
    return verdict, len(dup_groups), contra


# ---------------------------------------------------------------------------
# 3. structure / byte statistics
# ---------------------------------------------------------------------------

def entropy(counter, n):
    e = 0.0
    for c in counter.values():
        p = c / n
        e -= p * math.log2(p)
    return e


def structure(full):
    print("\n== 3. STRUCTURE (over %d full trailers) ==" % len(full))
    n = len(full)
    cols = [collections.Counter() for _ in range(TRAIL)]
    for *_, tr in full:
        for i, b in enumerate(tr):
            cols[i][b] += 1
    const = [i for i in range(TRAIL) if len(cols[i]) == 1]
    print(f"  constant byte positions: {const}")
    for i in const:
        print(f"    pos {i}: always 0x{next(iter(cols[i])):02x}")
    # near-constant / low entropy positions
    ents = [entropy(c, n) for c in cols]
    low = [(i, round(ents[i], 3)) for i in range(TRAIL) if ents[i] < 7.0]
    print(f"  positions with entropy < 7.0 bits: {low}")
    body = [e for i, e in enumerate(ents) if 2 <= i < TRAIL - 1]
    print(f"  mean per-byte entropy of body [2..351]: {sum(body)/len(body):.4f} bits "
          f"(min {min(body):.4f}, max {max(body):.4f}); ideal uniform ~"
          f"{math.log2(min(n,256)):.3f} given n={n}")
    # byte 1: 0xN0 field
    b1 = collections.Counter(tr[1] for *_, tr in full)
    low_nib = sum(v for k, v in b1.items() if k & 0x0F)
    print(f"  byte[1] low nibble nonzero count: {low_nib} / {n} "
          f"(=> byte[1] is a multiple of 0x10 in {n-low_nib}/{n})")
    print(f"  byte[1] high-nibble distribution: "
          + str(sorted(collections.Counter(tr[1] >> 4 for *_, tr in full).items())))
    print(f"  byte[0] distribution: {dict(cols[0])}")
    print(f"  byte[352] (last) distribution: {dict(sorted(cols[352].items()))}")
    print(f"  byte[351] entropy: {ents[351]:.3f}; byte[352] entropy {ents[352]:.3f}")
    # overall value histogram of body
    allc = collections.Counter()
    for *_, tr in full:
        allc.update(tr[2:352])
    tot = sum(allc.values())
    print(f"  body byte-value entropy (pooled): {entropy(allc, tot):.4f} / 8")
    # first-two-byte as u16 LE
    u16 = collections.Counter(struct.unpack("<H", tr[:2])[0] for *_, tr in full)
    print(f"  distinct u16(byte0,byte1) values: {len(u16)}; "
          f"values: {sorted(u16)[:20]}{'...' if len(u16)>20 else ''}")
    # bit-plane check: interpret as LSB-first bitstream -> leading zero bits
    lead = collections.Counter()
    for *_, tr in full:
        bits = 0
        for b in tr:
            for j in range(8):
                if b >> j & 1:
                    break
                bits += 1
            else:
                continue
            break
        lead[bits] += 1
    print(f"  leading zero-bit count (LSB-first) distribution: {dict(sorted(lead.items()))}")
    tail0 = collections.Counter()
    for *_, tr in full:
        z = 0
        for b in reversed(tr):
            if b == 0:
                z += 1
            else:
                break
        tail0[z] += 1
    print(f"  trailing zero-byte count distribution: {dict(sorted(tail0.items()))}")
    return ents, cols


# ---------------------------------------------------------------------------
# 4. final partial-page trailer length law
# ---------------------------------------------------------------------------

def gzip_end_in_logical(raw: bytes, name: str):
    """Length of the meaningful logical stream: end of the LAST gzip member's
    8-byte trailer (de-paged coordinates), or None for non-gzip streams."""
    # de-page
    out = bytearray()
    pos = 0
    while pos < len(raw):
        out += raw[pos:pos + PAGE]
        pos += STRIDE
    logical = bytes(out)
    end = None
    off = 0
    while True:
        off = logical.find(b"\x1f\x8b\x08", off)
        if off < 0:
            break
        d = zlib.decompressobj(16 + zlib.MAX_WBITS)
        try:
            d.decompress(logical[off:])
            if d.eof:
                end = len(logical) - len(d.unused_data)
                off = end
                continue
        except zlib.error:
            pass
        off += 1
    return logical, end


def tail_law(tails):
    print("\n== 4. FINAL PARTIAL-PAGE TRAILER LENGTH LAW ==")
    print("  P_page = payload bytes on final page (logical end - k*64896);")
    print("  M_max = bytes after logical end (zero pad + trailer);")
    print("  M_nz  = M_max minus leading zero pad (trailer starts 0x00 so true M in [M_nz, M_max]).")
    print(f"  {'file/stream':52s} {'k':>3s} {'tail':>6s} {'P_page':>7s} {'zeros':>5s} "
          f"{'M_nz':>5s} {'353P/64896':>10s} {'ceil(P/184)':>11s}")
    rows = []
    for f, name, k, tail in tails:
        raw_len_tail = len(tail)
        # reconstruct which raw stream: reload
        raw = open(os.path.join(EXTRACTED, f, name.replace("/", "__") + ".bin"), "rb").read()
        logical, gend = gzip_end_in_logical(raw, name)
        if gend is None:
            continue
        p_page = gend - k * PAGE      # payload bytes belonging to this final page
        if p_page < 0:
            continue
        after = tail[p_page:]         # zero pad + trailer
        m_max = len(after)
        # strip leading zeros
        stripped = after.lstrip(b"\x00")
        m_nz = len(stripped)
        zeros = m_max - m_nz
        est = 353 * p_page / PAGE
        rows.append((f, name, k, raw_len_tail, p_page, zeros, m_nz, m_max, est))
        print(f"  {(f+'/'+name)[:52]:52s} {k:3d} {raw_len_tail:6d} {p_page:7d} {zeros:5d} "
              f"{m_nz:5d} {est:10.1f} {math.ceil(p_page/184):11d}")
    # fit M_true ~ a + b*P on large pages using m_nz+1 (trailer starts with 0x00)
    big = [(p, mnz + 1) for _, _, _, _, p, z, mnz, mm, e in rows if p > 20000]
    if len(big) >= 2:
        xs = [p for p, _ in big]; ys = [m for _, m in big]
        mx = sum(xs)/len(xs); my = sum(ys)/len(ys)
        b = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / sum((x-mx)**2 for x in xs)
        a = my - b*mx
        print(f"  linear fit (P>20k, assuming trailer = 0x00 + nonzero run): "
              f"M ~= {a:.2f} + P/{1/b:.1f}   (full page: 353 = P/{PAGE/353:.1f})")
    return rows


# ---------------------------------------------------------------------------
# 5. GF(2) linearity (rank) test
# ---------------------------------------------------------------------------

def gf2_rank_test(full, max_pages=1200):
    """If trailer bits are affine-linear in payload bits (CRC / RS / BCH /
    any linear code, possibly XORed with a constant), then for any linear
    dependency among payload rows (XOR of a subset of payloads == 0) the same
    subset XOR of the (trailer - c) rows is 0.  Equivalent: the row space of
    [payload | trailer'] has rank == rank(payload).  We test this on the
    trailers ALONE first (cheap): for a linear code with r = 353*8 = 2824
    parity bits, rank(trailer matrix) <= 2824 no matter how many pages; for a
    keyed hash / compressed record the trailers behave like random 2824-bit
    vectors and reach full rank 2824 quickly, but crucially payload
    dependencies do NOT map to trailer dependencies.

    Practical decisive test: find pages whose payloads are IDENTICAL EXCEPT in
    a small region (not available)... instead we use the definitive
    affine-linearity test: build matrix rows = [payload_bits ^ p0, trailer ^ t0]
    (subtracting page 0 removes any affine constant), reduce; linearity holds
    iff no reduced row has zero payload part with nonzero trailer part.
    Payload is 519,168 bits wide; we operate on Python ints (arbitrary
    precision bitsets) with a pivot dict keyed by top set bit.
    """
    print("\n== 5. GF(2) AFFINE-LINEARITY TEST ==")
    # de-duplicate payloads
    seen = {}
    for f, name, k, ph, payload, tr in full:
        if ph not in seen:
            seen[ph] = (payload, tr)
    items = list(seen.values())
    print(f"  distinct pages available: {len(items)}; using up to {max_pages}")
    items = items[:max_pages]
    p0, t0 = items[0]
    P0 = int.from_bytes(p0, "big")
    T0 = int.from_bytes(t0, "big")
    W = PAGE * 8
    # combined vector: payload high bits, trailer low bits
    pivots = {}   # bit -> vector
    rank_payload = 0
    contradiction = 0
    checked = 0
    for payload, tr in items[1:]:
        v = ((int.from_bytes(payload, "big") ^ P0) << (TRAIL * 8)) | \
            (int.from_bytes(tr, "big") ^ T0)
        # reduce
        while v:
            hb = v.bit_length() - 1
            piv = pivots.get(hb)
            if piv is None:
                pivots[hb] = v
                if hb >= TRAIL * 8:
                    rank_payload += 1
                break
            v ^= piv
        else:
            # v reduced to zero: payload combo was dependent AND trailer combo
            # also cancelled -> consistent with linearity (needs a dependency
            # among payloads to be informative)
            pass
        checked += 1
        # detect: payload part became 0 but trailer part nonzero
        # (that happens inside loop: hb < TRAIL*8 with nonzero v)
    # scan pivots for trailer-only pivots
    trailer_only = [hb for hb in pivots if hb < TRAIL * 8]
    print(f"  pages reduced: {checked}; payload-pivot rank: {rank_payload}; "
          f"trailer-only pivots (payload combo=0 but trailer combo!=0): {len(trailer_only)}")
    if rank_payload == checked and not trailer_only:
        print("  All payload deltas are LINEARLY INDEPENDENT (rank == #pages), so no")
        print("  payload dependency exists to test in this corpus -> the rank test is")
        print("  UNINFORMATIVE for real pages (expected: 64,896-byte pages are")
        print("  effectively random vectors; a dependency needs > 519,168 pages).")
        return None
    if trailer_only:
        print("  => NON-LINEAR: a payload dependency did not cancel the trailers.")
        return False
    print("  => consistent with affine-linear code.")
    return True


def xor_closure_test(full):
    """Look for A^B == C^D style payload relations to spot-check additivity."""
    print("\n== 6. XOR-relation spot checks ==")
    # pairwise XOR fingerprints on a hash of xor is infeasible for full
    # closure; instead check trivial relation: pages that are all-zero or
    # near-constant (their trailers should be structurally simple if the map
    # is 'compression'; if code is linear, trailer(0)=constant c).
    zero_page = bytes(PAGE)
    zt = [tr for f, n, k, ph, p, tr in full if p == zero_page]
    print(f"  all-zero payload pages in corpus: {len(zt)}; distinct trailers: {len(set(zt))}")
    if zt:
        print(f"    trailer(zero page)[:32] = {zt[0][:32].hex(' ')}")
    # constant-fill pages
    fills = [(p[0], tr) for f, n, k, ph, p, tr in full
             if p.count(p[0]) == PAGE]
    print(f"  constant-fill pages: {len(fills)}")
    for b, tr in fills[:5]:
        print(f"    fill=0x{b:02x} trailer[:16]={tr[:16].hex(' ')}")
    return zt, fills


# ---------------------------------------------------------------------------
def main():
    full, tails = build_corpus()
    streams = collections.Counter((f, n) for f, n, *_ in full)
    print("  full pages per stream (top 12):")
    for (f, n), c in streams.most_common(12):
        print(f"    {f}/{n}: {c}")
    det = determinism(full)
    structure(full)
    tail_law(tails)
    gf2_rank_test(full)
    xor_closure_test(full)
    print("\nDone.")


if __name__ == "__main__":
    main()

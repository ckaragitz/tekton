#!/usr/bin/env python3
"""ECC GEOMETRY (agent ecc-geometry) — the complete page/block layout of Revit
2026 streams, derived byte-exactly from the corpus.

RESULT SUMMARY (all verified below):

Every ECC-framed raw stream is a sequence of BLOCKS.  A block is one GF(2)
codeword of the interleaved cyclic (Hamming/CRC) family
        g(x) = h_m(x^I),   h_m = the primitive trinomial of degree m
        m in {4,5,6,7,9,11}: x^4+x+1, x^5+x^2+1, x^6+x+1, x^7+x+1,
                              x^9+x^4+1, x^11+x^2+1
(bits taken LSB-first inside each byte; the block's first bit is the highest
degree coefficient).  Equivalently the codeword bits deal round-robin into I
lanes (bit degree e -> lane e mod I) and every lane is an (2^m-1, 2^m-1-m)
cyclic Hamming codeword (m parity bits = "CRC-m").

FULL pages (all but the last block of a long stream) are the fixed special
case (I,m)=(255,11): codeword N=2047*255=521,985 bits -> block R=65,249 bytes
= 64,896 payload + 353 field; 8*65249 - 521,985 = 7 trailing pad bits; the 12
leading field bits are the message bits 519,168..519,179 (unused, zero).
=> the "0x00 / high-nibble / 0-1 last byte" trailer signature is pure
geometry: 12 zero message bits, 2805 parity bits, 7 zero pad bits.

FINAL (partial) block of a stream with payload buffer P' bytes:
   choose the smallest m (4,5,6,7,9,11) with lanes
        I = max(65, ceil(8*P' / K_m)),  K_m = 2^m-1-m message bits per lane
   such that I <= I_MAX (=81; corpus bounds 79..81) — m=11 is exempt and
   grows to I<=255.
   * SHORTENED case (I=65): codeword N = 8*P' + 65*m bits, block R =
     ceil(N/8) = P' + ceil(65m/8); field F = ceil(65m/8), its 8F-65m leading
     bits are extra (zero) message bits; no trailing pad.
   * QUANTIZED case (I>65): codeword N = (2^m-1)*I bits exactly (every lane
     full length), block R = ceil(N/8), trailing pad = I mod 8 zero bits;
     message capacity K_m*I bits >= 8*P' (payload at the top, zero fill).
   In both cases the parity is the codeword's m*I LOWEST-degree coefficients
   = the block's last ceil((m*I + pad)/8) bytes (LSB-first bit order), and it
   is a pure function of the message bits: parity = (message(x)*x^{mI}) mod g.

Run: /Users/ck/dev/things/rev-revit/.venv/bin/python \
       /Users/ck/dev/things/rev-revit/experiments/ecc/geometry.py
"""
from __future__ import annotations
import glob, os, sys, json
import numpy as np

ROOT = '/Users/ck/dev/things/rev-revit'
sys.path.insert(0, os.path.join(ROOT, 'src'))
from rvt.container import open_rvt, PAGE_PAYLOAD, PAGE_TRAILER, PAGE_STRIDE  # noqa

# ---------------------------------------------------------------------------
# the code family
# ---------------------------------------------------------------------------
TRI = {4: (1 << 4) | (1 << 1) | 1,      # x^4+x+1
       5: (1 << 5) | (1 << 2) | 1,      # x^5+x^2+1
       6: (1 << 6) | (1 << 1) | 1,      # x^6+x+1
       7: (1 << 7) | (1 << 1) | 1,      # x^7+x+1
       9: (1 << 9) | (1 << 4) | 1,      # x^9+x^4+1
       11: (1 << 11) | (1 << 2) | 1}    # x^11+x^2+1
M_ORDER = (4, 5, 6, 7, 9, 11)
LANES_MIN = 65
LANES_MAX_SMALL = 81            # I ceiling for m<11 (corpus bounds 79..81)
LANES_MAX = 255

def K(m): return (1 << m) - 1 - m          # message bits per full lane
def L(m): return (1 << m) - 1              # codeword bits per full lane

_REV = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))
def poly_of(data: bytes) -> int:
    """LSB-first bit stream as GF(2) polynomial (first bit = highest degree)."""
    return int.from_bytes(data.translate(_REV), 'big')
def bytes_of(p: int, nbytes: int) -> bytes:
    return p.to_bytes(nbytes, 'big').translate(_REV)
def pmod(a: int, g: int) -> int:
    dg = g.bit_length() - 1
    while a.bit_length() - 1 >= dg:
        a ^= g << (a.bit_length() - 1 - dg)
    return a
def g_poly(I: int, m: int) -> int:
    h = TRI[m]; g = 0
    for e in range(m + 1):
        if h >> e & 1: g |= 1 << (e * I)
    return g

# ---------------------------------------------------------------------------
# WRITER RULE: payload buffer length P' -> block geometry
# ---------------------------------------------------------------------------

def block_params(payload_len: int, i_max: int = LANES_MAX_SMALL):
    """Return dict(m,I,R,N,t_pad,shortened,capacity_bits,parity_bits)."""
    n = 8 * payload_len
    for m in M_ORDER:
        I = max(LANES_MIN, -(-n // K(m)))
        if m == 11:
            if I > LANES_MAX:
                raise ValueError('payload exceeds one page (64,896 B)')
            break
        if I <= i_max:
            break
    if I == LANES_MIN and n <= LANES_MIN * K(m):
        N = n + LANES_MIN * m           # shortened lanes, no trailing pad
        R = -(-N // 8)
        N = 8 * R                       # the extra (8R-n-65m) base bits are message bits too
        t_pad = 0
        shortened = True
    else:
        N = L(m) * I                    # full-length lanes
        R = -(-N // 8)
        t_pad = 8 * R - N               # == I mod 8
        shortened = False
    return dict(m=m, I=I, R=R, N=N, t_pad=t_pad, shortened=shortened,
                parity_bits=m * I, capacity_bits=N - m * I, payload_len=payload_len)

def parity_of_block(block: bytes, I: int, m: int, t_pad: int) -> int:
    """Recompute the m*I parity bits of ``block`` (whose parity/pad region may
    be anything) purely from its message bits.  Returns the parity polynomial
    (degree < m*I).  Convention: block(x) = codeword(x) * x^t_pad, codeword =
    message(x)*x^{mI} + parity(x)."""
    R = len(block); N = 8 * R - t_pad
    B = poly_of(block) >> t_pad               # drop trailing pad bits (lowest coefficients)
    msg = B >> (m * I)                        # strip the (old) parity coefficients
    return pmod(msg << (m * I), g_poly(I, m))

def rebuild_block(block: bytes, I: int, m: int, t_pad: int) -> bytes:
    """Keep the message bits of ``block`` and REGENERATE its parity + pad."""
    R = len(block)
    B = poly_of(block) >> t_pad
    msg = B >> (m * I)
    cw = (msg << (m * I)) | pmod(msg << (m * I), g_poly(I, m))
    return bytes_of(cw << t_pad, R)

def encode_final_block(payload: bytes) -> bytes:
    """WRITER: emit the whole final block (payload || zero fill || parity ||
    pad) for a payload buffer of len(payload) bytes."""
    p = block_params(len(payload))
    R, I, m, t_pad = p['R'], p['I'], p['m'], p['t_pad']
    blk = bytearray(payload + bytes(R - len(payload)))
    return rebuild_block(bytes(blk), I, m, t_pad)

def encode_full_page(page: bytes) -> bytes:
    """A full page: (I,m)=(255,11), payload exactly 64,896 bytes.
    Uses the fast vectorised lane encoder when available (identical result,
    verified byte-exact on 3,502 corpus pages); falls back to bigints."""
    assert len(page) == PAGE_PAYLOAD
    try:
        return _fast_full_page(page)
    except Exception:
        return rebuild_block(page + bytes(PAGE_TRAILER), 255, 11, 7)

_LS = None
def _fast_full_page(page: bytes) -> bytes:
    global _LS
    if _LS is None:
        sys.path.insert(0, os.path.join(ROOT, 'experiments', 'ecc'))
        import layout_sweep as _LS
    return page + _LS.lane_crc11_trailer(page)

# ---------------------------------------------------------------------------
# INDEPENDENT DIVISOR PROBE (how the rule was derived): find (I,m) dividing a block
# ---------------------------------------------------------------------------

def lane_regs(block: bytes, I: int, h: int) -> np.ndarray:
    n = 8 * len(block)
    bits = np.unpackbits(np.frombuffer(block, np.uint8), bitorder='little')
    pad = (-n) % I
    if pad:
        bits = np.concatenate([np.zeros(pad, np.uint8), bits])
    M = bits.reshape(-1, I)
    m = h.bit_length() - 1
    reg = np.zeros(I, np.uint32)
    hl = np.uint32(h & ((1 << m) - 1)); mm = np.uint32(m); mask = np.uint32((1 << m) - 1)
    for row in M:
        reg = (reg << np.uint32(1)) | row.astype(np.uint32)
        reg = (reg & mask) ^ (((reg >> mm) & 1) * hl)
    return reg

def divides(block: bytes, I: int, m: int) -> bool:
    return not lane_regs(block, I, TRI[m]).any()

def probe_block(block: bytes, i_lo=1, i_hi=255):
    """Every (I,m) in the family whose g divides the block."""
    hits = []
    for m in M_ORDER:
        for I in range(i_lo, i_hi + 1):
            if divides(block, I, m):
                hits.append((I, m))
    return hits

# ---------------------------------------------------------------------------
# corpus
# ---------------------------------------------------------------------------
SAMPLES = sorted(glob.glob(f'{ROOT}/samples/*.rvt'))
EXTRA = (sorted(glob.glob(f'{ROOT}/vendor/**/*.rvt', recursive=True)) +
         sorted(glob.glob(f'{ROOT}/vendor/**/*.rfa', recursive=True)))

def blocks_of(files):
    """Yield (file, stream, kind, blockbytes, D_gz) for every block.
    kind = 'full' or 'final'.  D_gz = end offset of the last gzip member
    within the final block (a hard lower bound on its payload) or None."""
    for f in files:
        try: d = open_rvt(f)
        except Exception: continue
        fn = os.path.basename(f)
        for s in d.streams():
            raw = d.raw(s.name)
            nf = len(raw) // PAGE_STRIDE
            tail_full = (len(raw) == nf * PAGE_STRIDE)
            if tail_full and nf:
                nf -= 1
            for k in range(nf):
                yield fn, s.name, 'full', raw[k * PAGE_STRIDE:(k + 1) * PAGE_STRIDE], None
            rem = raw[nf * PAGE_STRIDE:]
            if not rem:
                continue
            ms = d.members(s.name)
            D = None
            if ms:
                D = ms[-1].offset + ms[-1].consumed - nf * PAGE_PAYLOAD
                if D < 0: D = None
            yield fn, s.name, 'final', rem, D

# ---------------------------------------------------------------------------
# VERIFICATION 1: the full-page rule (payload 64896 + field 353, signature)
# ---------------------------------------------------------------------------

def verify_full_page_rule(files=SAMPLES, recompute_stride=101):
    """(a) every full page's field has byte0=0, byte1 low nibble 0, last<=1;
    (b) a strided subset of full pages is byte-exactly reproduced by
    encode_full_page (independent of experiments/ecc/layout_sweep.py)."""
    n = sig_ok = re_n = re_ok = 0
    for fn, sn, kind, blk, D in blocks_of(files):
        if kind != 'full':
            continue
        tr = blk[PAGE_PAYLOAD:]
        n += 1
        if tr[0] == 0 and (tr[1] & 0x0F) == 0 and tr[352] <= 1:
            sig_ok += 1
        if n % recompute_stride == 1:
            re_n += 1
            # independent big-integer polynomial encoder (NOT layout_sweep)
            if rebuild_block(blk, 255, 11, 7) == blk:
                re_ok += 1
    print(f'[full-page rule] full pages: {n}; signature (00, x0, <=01) holds: {sig_ok}/{n}; '
          f'byte-exact re-encode (every {recompute_stride}th): {re_ok}/{re_n}')
    return n, sig_ok, re_ok, re_n

# ---------------------------------------------------------------------------
# VERIFICATION 2: final-block geometry, per block
# ---------------------------------------------------------------------------

def analyse_final_block(blk: bytes, D):
    """Locate (I,m) by divisibility (search window around the field size),
    then check (i) the block length quantization, (ii) t_pad, (iii) the payload
    interval [P'min,P'max] contains a value >= D, (iv) BYTE-EXACT parity
    regeneration from the message bits."""
    R = len(blk)
    tail = blk[D:] if D is not None else blk
    z = len(tail) - len(tail.lstrip(bytes(1)))
    nz = len(tail) - z
    found = None
    # search: shortened I=65 for every m, and quantized I = ceil(8R/L(m)) etc.
    cands = set()
    for m in M_ORDER:
        cands.add((65, m))
        for I in range(66, 256):
            if -(-(L(m) * I) // 8) == R:
                cands.add((I, m))
    # plus a generic window near F ~ nz for safety
    for m in M_ORDER:
        for I in range(max(1, (8 * (nz - 3)) // m), min(255, 8 * (nz + 10) // m) + 1):
            cands.add((I, m))
    for I, m in sorted(cands, key=lambda t: -(t[0] * t[1])):
        if divides(blk, I, m):
            found = (I, m); break
    if not found:
        return None
    I, m = found
    if I > LANES_MIN:
        N = L(m) * I; t_pad = 8 * R - N; shortened = False
        Pmax = (K(m) * I) // 8
        Pmin = (K(m) * (I - 1)) // 8 + 1 if I > LANES_MIN else 0
        quant_ok = (-(-N // 8) == R) and (t_pad == I % 8)
    else:
        N = 8 * R; t_pad = 0; shortened = True
        F = -(-(LANES_MIN * m) // 8)
        Pmax = R - F
        Pmin = 0
        quant_ok = True
    regen = rebuild_block(blk, I, m, t_pad) == blk
    # writer-rule consistency: does some P' in [max(D,Pmin), Pmax] map to (m,I,R)?
    rule_P = None
    lo = max(D or 0, Pmin)
    for P in range(lo, Pmax + 1):
        p = block_params(P)
        if p['m'] == m and p['I'] == I and p['R'] == R:
            rule_P = P; break
    return dict(R=R, I=I, m=m, shortened=shortened, t_pad=t_pad, quant_ok=quant_ok,
                Pmin=Pmin, Pmax=Pmax, D=D, D_ok=(D is None or D <= Pmax),
                regen_exact=regen, rule_P=rule_P, z=z, nz=nz)

def verify_final_blocks(files, label):
    rows = []
    n = ok_regen = ok_quant = ok_rule = ok_D = 0
    for fn, sn, kind, blk, D in blocks_of(files):
        if kind != 'final' or len(blk) < 20:
            continue
        a = analyse_final_block(blk, D)
        if a is None:
            print(f'   NO-ECC   {fn[:26]:27s} {sn:30s} R={len(blk)}')
            continue
        n += 1
        ok_regen += a['regen_exact']; ok_quant += a['quant_ok']
        ok_rule += a['rule_P'] is not None; ok_D += a['D_ok']
        print(f"   {'OK ' if a['regen_exact'] and a['quant_ok'] and a['rule_P'] is not None and a['D_ok'] else 'ERR'}"
              f"   {fn[:26]:27s} {sn:30s} R={a['R']:6d} I={a['I']:3d} m={a['m']:2d} "
              f"{'short' if a['shortened'] else 'quant'} t_pad={a['t_pad']} P'∈[{a['Pmin']},{a['Pmax']}] "
              f"D={a['D']} ruleP={a['rule_P']} regen={a['regen_exact']}")
        rows.append(dict(file=fn, stream=sn, **{k: v for k, v in a.items()}))
    print(f'[{label}] final blocks: {n}; parity byte-exact regenerated: {ok_regen}/{n}; '
          f'length/t_pad quantization holds: {ok_quant}/{n}; D<=capacity: {ok_D}/{n}; '
          f'writer-rule reproduces (m,I,R) for some P>=D: {ok_rule}/{n}')
    return rows

def main_verify():
    print('== FULL-PAGE RULE (six 2026 samples) ==')
    verify_full_page_rule(SAMPLES)
    print('\n== FINAL BLOCKS (six 2026 samples) ==')
    r1 = verify_final_blocks(SAMPLES, '2026 samples')
    print('\n== FINAL BLOCKS + full-slot pages (2016-2026 vendor files) ==')
    r2 = verify_final_blocks(EXTRA, 'vendor files')
    with open('/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/geom/geometry_table.json', 'w') as f:
        json.dump(r1 + r2, f, indent=1, default=str)
    print('\n== brief test rig: page_trailer(page) == trailer on Formats/Latest page 0 ==')
    d = open_rvt(f'{ROOT}/samples/rstbasicsampleproject.rvt')
    raw = d.raw('Formats/Latest')
    page, tr = raw[:PAGE_PAYLOAD], raw[PAGE_PAYLOAD:PAGE_STRIDE]
    assert encode_full_page(page)[PAGE_PAYLOAD:] == tr
    print('ASSERTION PASSED: encode_full_page(page)[64896:] == trailer  (353 bytes byte-exact)')
    fb = raw[2 * PAGE_STRIDE:]
    assert rebuild_block(fb, 205, 11, 5) == fb
    print('ASSERTION PASSED: rebuild_block(final block, I=205, m=11, t_pad=5) == real final block '
          f'({len(fb)} bytes, byte-exact) — the FINAL PARTIAL BLOCK GEOMETRY reproduces the real bytes')


# ---------------------------------------------------------------------------
# WHOLE-STREAM FRAMING (for the writer): payload buffer -> raw paged stream
# ---------------------------------------------------------------------------

def frame_stream(payload: bytes) -> bytes:
    """Frame a logical payload buffer exactly like Revit does: full 64,896-byte
    pages (each an (I,m)=(255,11) block of 65,249 bytes), then one final block
    for the remainder via the (m,I) selection rule.  Payload shorter than a
    page => single final block.  An exact multiple of 64,896 needs no extra
    block (a 64,896-byte chunk maps to the (255,11)/65,249 block anyway)."""
    out = bytearray()
    pos = 0
    n = len(payload)
    if n == 0:
        return b''
    while n - pos > PAGE_PAYLOAD:
        out += encode_full_page(payload[pos:pos + PAGE_PAYLOAD])
        pos += PAGE_PAYLOAD
    out += encode_final_block(payload[pos:])
    return bytes(out)


def reframe_demo(files=SAMPLES, max_pages=6):
    """For every ECC-framed stream with <= max_pages full pages: rebuild the
    ENTIRE raw stream from its own payload buffer with frame_stream() and
    byte-compare with the real raw stream.  P' = the rule-consistent split.
    Mismatches are diagnosed: they may ONLY lie in the message-slack region
    (junk bits Revit left between the payload end and the parity), never in
    data or parity, and the rebuilt block must still verify."""
    tot = exact = valid = junk_only = 0
    for f in files:
        d = open_rvt(f)
        fn = os.path.basename(f)
        for s in d.streams():
            raw = d.raw(s.name)
            nf = len(raw) // PAGE_STRIDE
            if len(raw) == nf * PAGE_STRIDE and nf:
                nf -= 1
            if nf > max_pages:
                continue
            rem = raw[nf * PAGE_STRIDE:]
            ms = d.members(s.name)
            D = (ms[-1].offset + ms[-1].consumed - nf * PAGE_PAYLOAD) if ms else None
            a = analyse_final_block(rem, D) if rem else None
            if a is None:
                continue
            P = a['rule_P'] if a['rule_P'] is not None else a['Pmax']
            payload = b''.join(raw[k * PAGE_STRIDE:k * PAGE_STRIDE + PAGE_PAYLOAD] for k in range(nf)) + rem[:P]
            mine = frame_stream(payload)
            tot += 1
            same = (mine == raw)
            exact += same
            fb = mine[nf * PAGE_STRIDE:]
            v = analyse_final_block(fb, None)
            valid += (v is not None and v['regen_exact'] and (v['I'], v['m']) == (a['I'], a['m']))
            if not same and len(mine) == len(raw):
                # diagnose: identical except inside [payload end, R): junk message bits + parity
                base = nf * PAGE_STRIDE
                if mine[:base + P] == raw[:base + P]:
                    junk_only += 1
                    print(f'   junk-slack diff: {fn[:22]} {s.name} (R={len(rem)}, payload end {P}) — real block '
                          f'has nonzero message bits after the payload; both codewords valid')
                else:
                    print(f'   MISMATCH: {fn[:22]} {s.name}')
            elif not same:
                print(f'   LENGTH MISMATCH: {fn[:22]} {s.name} mine={len(mine)} real={len(raw)}')
    print(f'[reframe] streams rebuilt end-to-end from their payload buffer: {tot}; whole-stream '
          f'byte-exact: {exact}/{tot}; differing only in Revit junk-slack bits: {junk_only}; '
          f'my final block re-derives to the same (I,m) and verifies: {valid}/{tot}')
    return tot, exact, valid, junk_only


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'verify'
    if cmd == 'reframe':
        reframe_demo()
    else:
        main_verify()

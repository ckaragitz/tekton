#!/usr/bin/env python3
"""Known-plaintext search over ALGEBRAIC error-correcting codes for the Revit
``.rvt`` per-page trailer (agent ``ecc-rs-search``, wave 2)  --  SOLVED.

VERDICT
-------
The trailer is NOT Reed-Solomon (neither GF(2^8) chunked/interleaved nor a
GF(2^16) single codeword: see ``rs_negative_grid``).  It is the parity of a
**binary cyclic code**: an ``I``-way *bit-interleaved Hamming code*
(equivalently a binary BCH-family code with t=1 per lane / bursts up to I),
generator ``g(x) = h_m(x^I)`` where ``h_m`` is a primitive polynomial of
degree ``m`` over GF(2).  A FULL 64,896-byte page uses ``I=255, m=11``::

    g(x) = x^2805 + x^510 + 1        (2,805 parity bits -> 353-byte trailer)

Bit conventions: the page is ONE bit string read LSB-first inside each byte
(bit 0 of byte 0 first, DEFLATE order); the first bit is the highest-degree
coefficient of the codeword C(x); ``g(x) | C(x)``.

COMPLETE PAGE LAYOUT (bit granularity), for a page carrying ``L`` payload
bytes with parameter class (I, m, k = message bits per lane, w = pad-count
field width)::

    [ payload L bytes ][ Z zero bytes ][ z zero bits ][ w-bit LE field = Z ]
    |<------------------ message  s = I*k bits ------------------------->|
    [ parity  I*m bits, highest degree first ][ t_pad zero bits to byte end ]

    parity(x) = ( M(x) * x^(I*m) ) mod g(x),   R = ceil((s + I*m) / 8) raw bytes

For a FULL page (L = 64,896): (I,m,k) = (255,11,2036), s = 519,180, Z=0,
z=3, w=9  -> the observed 12 leading zero bits (byte0 = 0, byte1's low
nibble = 0), 2,805 parity bits, t_pad = 7  ->  353 bytes; R = 65,249 = the
page stride.  The "16-value nibble" in byte1 and the "0/1 last byte" of
docs/ecc-brief.md are simply the first 4 and last 1 parity bits.

PARAMETER-CLASS SELECTION (from the payload length L):
  * this file's independently-derived EMPIRICAL rule (``geometry_min_parity``,
    fits all 3,502 full + 55 final corpus pages byte-exact):  among the
    classes m, minimise the parity size I*m, where for message bits
    M = 8L + w(m):  I = 65, k = ceil(M/65) if M <= 65*K_m (K_m = 2^m-1-m),
    else k = K_m (full rows) and I = smallest ODD number >= ceil(M/K_m)
    (I <= 255);  w(m) = max(4, m-2);
  * the AUTHORITATIVE rule recovered by the ecc-intel agent from Utility.dll
    (CRCIO.cpp): the same eight classes chosen by fixed data-length
    thresholds (``CLASS_BY_LENGTH``);  identical on every corpus page and used
    by default here (the two differ only in unobserved size windows, e.g.
    L in 106..~113 where min-parity picks m=4/I=79 but the DLL picks m=5).

DELIVERABLES IN THIS MODULE
  * ``geometry(L)``          -- the writer's layout for an L-byte page payload
  * ``encode(payload)``      -- payload -> full raw page bytes (payload+trailer)
  * ``page_trailer(page)``   -- 353-byte trailer of a full page
  * ``fit_tail(tail)``       -- the known-plaintext fitter that cracked it
  * ``rs_negative_grid``     -- the refuted Reed-Solomon hypothesis grid
  * ``prove_corpus()``       -- byte-exact proof over the whole extracted corpus

Run:
    /Users/ck/dev/things/rev-revit/.venv/bin/python \\
        /Users/ck/dev/things/rev-revit/experiments/ecc/rs_search.py [--rs] [--fit] [--sweep]
"""
from __future__ import annotations

import glob
import os
import sys
import zlib
from dataclasses import dataclass
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXTRACTED = os.path.join(ROOT, "extracted")

PAGE = 64896            # payload bytes per full page
TRAIL = 353             # trailer bytes per full page
STRIDE = PAGE + TRAIL   # 65,249

# LSB-first bit stream <-> big-endian integer polynomial
REV = bytes(int(f"{i:08b}"[::-1], 2) for i in range(256))

# Primitive polynomial per class order m (low exponents; leading x^m implied).
# m>=4 confirmed by corpus fits; m=2,3 from Utility.dll (ecc-intel) only.
PRIM_LOW: Dict[int, Tuple[int, ...]] = {
    2: (1, 0),          # x^2 + x + 1
    3: (2, 0),          # x^3 + x^2 + 1   (DLL; reciprocal x^3+x+1 also primitive)
    4: (1, 0),          # x^4 + x + 1
    5: (2, 0),          # x^5 + x^2 + 1
    6: (1, 0),          # x^6 + x + 1
    7: (1, 0),          # x^7 + x + 1
    9: (4, 0),          # x^9 + x^4 + 1
    11: (2, 0),         # x^11 + x^2 + 1
}
# extra degrees, used only by the exhaustive fitter (never selected)
_FITTER_EXTRA: Dict[int, Tuple[int, ...]] = {8: (4, 3, 2, 0), 10: (3, 0), 12: (6, 4, 1, 0)}

# The selectable parameter classes (m -> lane alignment quantum).  align is
# the multiple to which the lane count I is rounded above the 65-lane floor
# (=> I odd for align 2, since I >= 65).  From Utility.dll (ecc-intel); the
# m>=4 rows are independently confirmed by the corpus.
CLASS_ALIGN: Dict[int, int] = {11: 2, 9: 2, 7: 2, 6: 2, 5: 2, 4: 2, 3: 2, 2: 4}

# Data-length thresholds for class selection (payload bytes -> m), from the
# DLL's capacity computation (ecc-intel).  L <= 7 -> m=2, <= 40 -> 3,
# <= 105 -> 4, <= 256 -> 5, <= 548 -> 6, <= 1274 -> 7, <= 5081 -> 9,
# else m = 11.  Corpus-confirmed transitions: 97..104->4, 112..238->5,
# 624..1017->7, 3868->9, >=7097->11.
CLASS_BY_LENGTH: Tuple[Tuple[int, int], ...] = (
    (7, 2), (40, 3), (105, 4), (256, 5), (548, 6), (1274, 7), (5081, 9),
)

MIN_LANES = 65
MAX_LANES = 255

# streams stored WITHOUT any page ECC (small uncompressed metadata)
NO_ECC_STREAMS = frozenset({
    "BasicFileInfo", "PartAtomXML", "TransmissionData",
    "ProjectInformation", "RevitPreview4.0",
})


# --------------------------------------------------------------------------
# GF(2) polynomial arithmetic on big ints  (bit i = coefficient of x^i)
# --------------------------------------------------------------------------

def hamming_K(m: int) -> int:
    """Message bits per lane: 2^m - 1 - m."""
    return (1 << m) - 1 - m


def field_width(m: int) -> int:
    """Width of the little-endian pad-count field.  == max(4, m-2); the DLL
    computes it as the bit-length of the byte-capacity of one alignment unit
    (see ecc-intel), which yields the same values for every class."""
    return max(4, m - 2)


def gpoly_lows(I: int, m: int) -> Tuple[int, ...]:
    """Low-term exponents of g(x) = h_m(x^I) (leading term x^(I*m) implied)."""
    lows = PRIM_LOW.get(m) or _FITTER_EXTRA[m]
    return tuple(e * I for e in lows)


def polymod_sparse(n: int, deg: int, lows: Sequence[int]) -> int:
    """n(x) mod g(x) where g = x^deg + sum(x^e for e in lows), all e < deg.
    Folds the high part down (x^deg == sum(x^e)); fast for sparse g."""
    mask = (1 << deg) - 1
    while n.bit_length() > deg:
        h = n >> deg
        n &= mask
        for e in lows:
            n ^= h << e
    return n


def bits_to_int(data: bytes) -> int:
    """``data`` as a GF(2) polynomial: LSB-first bit stream, first bit =
    highest degree (bit-reverse each byte, then big-endian integer)."""
    return int.from_bytes(data.translate(REV), "big")


def int_to_bytes(value: int, nbytes: int) -> bytes:
    """Inverse of bits_to_int for a polynomial of degree < 8*nbytes."""
    return value.to_bytes(nbytes, "big").translate(REV)


# --------------------------------------------------------------------------
# geometry (the writer's rule)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Geometry:
    payload: int      # L payload bytes
    I: int            # interleave depth (lanes)
    m: int            # Hamming order (parity bits per lane)
    k: int            # message bits per lane (rows), k <= 2^m-1-m
    zero_bytes: int   # Z zero pad bytes after the payload
    zero_bits: int    # z zero pad bits (0..7) before the field
    field_bits: int   # w width of the little-endian pad-count field (value Z)
    t_pad: int        # zero bits filling the final byte after the parity

    @property
    def message_bits(self) -> int:
        return self.I * self.k

    @property
    def parity_bits(self) -> int:
        return self.I * self.m

    @property
    def raw_bytes(self) -> int:
        return (self.message_bits + self.parity_bits + self.t_pad) // 8

    @property
    def trailer_bytes(self) -> int:
        return self.raw_bytes - self.payload


def class_for_length(L: int) -> int:
    """The Hamming order m the writer uses for a page of L payload bytes
    (authoritative DLL threshold rule)."""
    for limit, m in CLASS_BY_LENGTH:
        if L <= limit:
            return m
    return 11


def _lanes_for(M: int, m: int) -> Optional[Tuple[int, int]]:
    """(I, k) for message bits M with class m, or None if it cannot fit."""
    Km = hamming_K(m)
    if M <= MIN_LANES * Km:                 # shortened rows at the 65-lane floor
        return MIN_LANES, -(-M // MIN_LANES)
    align = CLASS_ALIGN[m]
    I = -(-M // Km)                         # full rows: k = Km, widen I
    rem = (I - MIN_LANES) % align
    if rem:
        I += align - rem                     # round up so (I - 65) % align == 0 (=> I odd)
    if I > MAX_LANES:
        return None
    return I, Km


def _geometry_for(L: int, m: int) -> Optional[Geometry]:
    w = field_width(m)
    M = 8 * L + w
    lanes = _lanes_for(M, m)
    if lanes is None:
        return None
    I, k = lanes
    s = I * k
    pad = s - 8 * L - w                      # = 8Z + z zero pad bits
    Z, z = pad >> 3, pad & 7
    t_pad = (-(s + I * m)) % 8
    return Geometry(L, I, m, k, Z, z, w, t_pad)


def geometry(L: int) -> Geometry:
    """The writer's page geometry for an ``L``-byte payload (DLL class rule)."""
    if not 0 < L <= PAGE:
        raise ValueError(f"page payload must be 1..{PAGE} bytes, got {L}")
    g = _geometry_for(L, class_for_length(L))
    if g is None:                             # cannot happen for L <= PAGE
        raise ValueError(f"payload of {L} bytes exceeds one page's ECC capacity")
    return g


def geometry_min_parity(L: int) -> Geometry:
    """This agent's independently-derived selection rule: minimise the parity
    size I*m over the classes m in {4,5,6,7,9,11}.  Byte-exact on the whole
    corpus; may differ from ``geometry`` in unobserved size windows."""
    best = None
    for m in (4, 5, 6, 7, 9, 11):
        g = _geometry_for(L, m)
        if g is not None and (best is None or (g.parity_bits, m) < (best.parity_bits, best.m)):
            best = g
    if best is None:
        raise ValueError(L)
    return best


# --------------------------------------------------------------------------
# encoder / verifier
# --------------------------------------------------------------------------

def codeword(payload: bytes, geo: Geometry) -> int:
    """The page codeword (message || parity) as a polynomial integer of
    degree < message_bits + parity_bits."""
    s, w, Z, L = geo.message_bits, geo.field_bits, geo.zero_bytes, geo.payload
    assert len(payload) == L
    msg = bits_to_int(payload) << (s - 8 * L)      # payload then zero pad
    for j in range(w):                              # field: stream bit s-w+j = bit j of Z
        if (Z >> j) & 1:
            msg |= 1 << (w - 1 - j)                 # stream bit i -> coefficient x^(s-1-i)
    deg = geo.parity_bits
    parity = polymod_sparse(msg << deg, deg, gpoly_lows(geo.I, geo.m))
    return (msg << deg) | parity


def encode(payload: bytes, geo: Optional[Geometry] = None) -> bytes:
    """Raw page bytes (payload || trailer) for ``payload``."""
    geo = geo or geometry(len(payload))
    return int_to_bytes(codeword(payload, geo) << geo.t_pad, geo.raw_bytes)


def trailer(payload: bytes) -> bytes:
    """The bytes the writer appends after ``payload`` (pad, field, parity,
    byte fill).  353 bytes for a full 64,896-byte page."""
    return encode(payload)[len(payload):]


def page_trailer(page: bytes) -> bytes:
    """The 353-byte trailer of a FULL 64,896-byte page."""
    assert len(page) == PAGE, len(page)
    return trailer(page)


def final_trailer(payload: bytes) -> bytes:
    """The trailer of a stream's final partial page."""
    return trailer(payload)


def frame(logical: bytes) -> bytes:
    """Page-frame a whole logical stream (writer): 64,896-byte pages, each
    followed by its trailer; the final page (possibly full) closes it."""
    if not logical:
        raise ValueError("cannot frame an empty stream")
    out = bytearray()
    pos, n = 0, len(logical)
    while n - pos > PAGE:
        out += encode(logical[pos:pos + PAGE])
        pos += PAGE
    out += encode(logical[pos:])
    return bytes(out)


def syndrome_zero(raw_page: bytes, geo: Geometry) -> bool:
    """True iff ``raw_page`` (payload+trailer) is a codeword of geo's code
    with geo's byte fill (does not check the pad-count field)."""
    if len(raw_page) != geo.raw_bytes:
        return False
    val = bits_to_int(raw_page)
    if val & ((1 << geo.t_pad) - 1):
        return False
    return polymod_sparse(val >> geo.t_pad, geo.parity_bits, gpoly_lows(geo.I, geo.m)) == 0


def resolve_page(raw_page: bytes) -> Optional[Geometry]:
    """Recover the geometry (hence the exact payload length) of a raw page
    from its size, its pad-count field and its zero syndrome."""
    nbytes = len(raw_page)
    if nbytes == STRIDE:
        geo = geometry(PAGE)
        return geo if syndrome_zero(raw_page, geo) else None
    val, nb = bits_to_int(raw_page), 8 * nbytes
    for L in range(nbytes - 1, max(0, nbytes - 4700), -1):
        geo = geometry(L)
        if geo.raw_bytes != nbytes:
            continue
        s, w = geo.message_bits, geo.field_bits
        field = 0
        for j in range(w):                          # stream bit p -> integer bit nb-1-p
            field |= ((val >> (nb - 1 - (s - w + j))) & 1) << j
        if field != geo.zero_bytes:
            continue
        if syndrome_zero(raw_page, geo):
            return geo
    return None


def unframe(raw: bytes) -> bytes:
    """The EXACT logical stream of a framed raw stream: strips trailers AND
    the final page's zero pad (via the pad-count field).  Raises on any
    page failing verification."""
    out = bytearray()
    pos, n = 0, len(raw)
    full = geometry(PAGE)
    while n - pos > STRIDE:
        if not syndrome_zero(raw[pos:pos + STRIDE], full):
            raise ValueError(f"full page at raw offset {pos} fails ECC")
        out += raw[pos:pos + PAGE]
        pos += STRIDE
    geo = resolve_page(raw[pos:])
    if geo is None:
        raise ValueError("final page fails ECC")
    out += raw[pos:pos + geo.payload]
    return bytes(out)


# --------------------------------------------------------------------------
# the known-plaintext FITTER (how the geometry was cracked)
# --------------------------------------------------------------------------

def fit_tail(tail: bytes, Irange: Iterable[int] = range(1, 256),
             mrange: Iterable[int] = range(2, 13)) -> List[dict]:
    """Find every (I, m) whose interleaved-Hamming code divides the tail bit
    string once ``t_pad`` trailing zero bits are removed (t_pad within the
    trailing-zero run).  Any hit on a real compressed page is essentially
    certain (chance ~2^-(I*m)).  Records the largest ``s`` (parity start) per
    (I, m); the true ``s`` is the multiple of I inside the returned window."""
    R, full = len(tail), bits_to_int(tail)
    nb = 8 * R
    tz = (full & -full).bit_length() - 1 if full else nb
    hits: List[dict] = []
    for m in mrange:
        if m not in PRIM_LOW and m not in _FITTER_EXTRA:
            continue
        for I in Irange:
            deg = I * m
            if deg + 8 > nb:
                continue
            lows = gpoly_lows(I, m)
            mask = (1 << deg) - 1
            for t in range(0, min(7, tz) + 1):
                s = nb - deg - t
                if s < 8:
                    break
                if full & ((1 << t) - 1):
                    continue
                if polymod_sparse((full >> (deg + t)) << deg, deg, lows) == ((full >> t) & mask):
                    hits.append(dict(I=I, m=m, deg=deg, s_max=s, t_pad=t,
                                     lane_aligned=(len([x for x in range(s - min(7, tz) + t, s + 1) if x % I == 0]) > 0)))
                    break
    return hits


# --------------------------------------------------------------------------
# Reed-Solomon hypothesis families (executable NEGATIVE evidence)
# --------------------------------------------------------------------------

def rs_gf8_encode(page: bytes, nlanes: int, nsym: int, poly: int = 0x11D,
                  fcr: int = 0, interleave: bool = True) -> bytes:
    """Family A: systematic RS over GF(2^8): ``nlanes`` codewords with ``nsym``
    parity bytes each (interleaved: byte i -> lane i mod nlanes; contiguous
    372-byte chunks cannot even form RS(255) codewords)."""
    import reedsolo
    rsc = reedsolo.RSCodec(nsym, nsize=255, prim=poly, fcr=fcr)
    if interleave:
        chunks = [bytes(page[i::nlanes]) for i in range(nlanes)]
    else:
        step = -(-len(page) // nlanes)
        chunks = [bytes(page[i * step:(i + 1) * step]) for i in range(nlanes)]
    out = bytearray()
    for c in chunks:
        if len(c) > 255 - nsym:
            raise ValueError("chunk longer than an RS(255) codeword can hold")
        out += bytes(rsc.encode(bytearray(c))[-nsym:])
    return bytes(out)


def rs_gf16_encode(page: bytes, nsym: int = 175, poly: int = 0x1002B,
                   b: int = 1, word_le: bool = True) -> bytes:
    """Family B: ONE systematic RS codeword over GF(2^16): 32,448 words +
    ``nsym`` parity words (350 bytes).  Pure-python LFSR encoder."""
    F = 1 << 16
    exp, log = [0] * (2 * (F - 1)), [0] * F
    x = 1
    for i in range(F - 1):
        exp[i], log[x] = x, i
        x <<= 1
        if x & F:
            x ^= poly
    for i in range(F - 1, 2 * (F - 1)):
        exp[i] = exp[i - (F - 1)]

    def gmul(a, c):
        return 0 if a == 0 or c == 0 else exp[log[a] + log[c]]

    gen = [1]
    for i in range(nsym):
        root = exp[(b + i) % (F - 1)]
        newg = [0] * (len(gen) + 1)
        for j, coef in enumerate(gen):
            newg[j] ^= coef
            newg[j + 1] ^= gmul(coef, root)
        gen = newg
    if word_le:
        words = [page[i] | (page[i + 1] << 8) for i in range(0, len(page), 2)]
    else:
        words = [(page[i] << 8) | page[i + 1] for i in range(0, len(page), 2)]
    reg = [0] * nsym
    for w_ in words:
        fb = w_ ^ reg[0]
        reg = reg[1:] + [0]
        if fb:
            for j in range(nsym):
                reg[j] ^= gmul(gen[j + 1], fb)
    out = bytearray()
    for r in reg:
        out += bytes((r & 0xFF, r >> 8)) if word_le else bytes((r >> 8, r & 0xFF))
    return bytes(out)


def rs_negative_grid(page: bytes, trailer_: bytes) -> List[dict]:
    """The RS hypothesis grid against one (page, trailer): report any
    candidate whose FIRST TWO parity bytes appear anywhere in the trailer's
    code region.  (None do -- and the byte-exact binary code makes RS moot.)"""
    code = trailer_[1:352]
    hits: List[dict] = []
    for nsym, nlanes in ((2, 175), (1, 350), (5, 70), (7, 50), (10, 35), (14, 25), (25, 14), (35, 10), (50, 7)):
        if -(-len(page) // nlanes) > 255 - nsym:
            hits.append(dict(family="A.gf8", nsym=nsym, lanes=nlanes,
                             result="structurally impossible: lane longer than an RS(255) codeword"))
            continue
        for poly in (0x11D, 0x11B, 0x12B, 0x165):
            for fcr in (0, 1):
                par = rs_gf8_encode(page, nlanes, nsym, poly, fcr, interleave=True)
                for label, cand in (("as-is", par), ("byteswap", par[::-1])):
                    at = code.find(cand[:2])
                    if at >= 0:
                        hits.append(dict(family="A.gf8", nsym=nsym, lanes=nlanes,
                                         poly=hex(poly), fcr=fcr, order=label,
                                         probe=cand[:2].hex(), at=at + 1))
    for poly in (0x1002B, 0x1100B):
        for b in (0, 1):
            for word_le in (True, False):
                par = rs_gf16_encode(page, 175, poly, b, word_le)
                for label, cand in (("as-is", par), ("word-rev", par[::-1])):
                    at = code.find(cand[:2])
                    if at >= 0:
                        hits.append(dict(family="B.gf16", poly=hex(poly), b=b,
                                         word_le=word_le, order=label,
                                         probe=cand[:2].hex(), at=at + 1))
    return hits


# --------------------------------------------------------------------------
# corpus proof / demo
# --------------------------------------------------------------------------

def iter_raw_streams():
    for f in sorted(os.listdir(EXTRACTED)):
        d = os.path.join(EXTRACTED, f)
        if not os.path.isdir(d):
            continue
        for p in sorted(glob.glob(os.path.join(d, "*.bin"))):
            b = os.path.basename(p)[:-4]
            if b.endswith(".logical") or b in NO_ECC_STREAMS:
                continue
            with open(p, "rb") as fh:
                yield f, b.replace("__", "/"), fh.read()


def iter_pages(raw: bytes) -> Iterator[Tuple[int, bytes]]:
    pos, k, n = 0, 0, len(raw)
    while n - pos > STRIDE:
        yield k, raw[pos:pos + STRIDE]
        pos += STRIDE
        k += 1
    if pos < n:
        yield k, raw[pos:]


def prove_corpus(verbose: bool = True) -> Tuple[int, int, int, int]:
    """Recompute every page trailer of every ECC stream in all six extracted
    files.  Returns (full_ok, full_total, final_ok, final_total)."""
    fo = ft = to = tt = 0
    for f, name, raw in iter_raw_streams():
        for k, page in iter_pages(raw):
            if len(page) == STRIDE:
                ft += 1
                fo += page_trailer(page[:PAGE]) == page[PAGE:]
            else:
                tt += 1
                geo = resolve_page(page)
                ok = geo is not None and encode(page[:geo.payload], geo) == page
                to += ok
                if verbose:
                    tag = (f"L={geo.payload} I={geo.I} m={geo.m} k={geo.k} "
                           f"Z={geo.zero_bytes} z={geo.zero_bits} t_pad={geo.t_pad}"
                           if geo else "NO GEOMETRY")
                    print(f"   {'OK ' if ok else 'BAD'} {f[:14]:14s} {name:28s} R={len(page):6d}  {tag}")
    return fo, ft, to, tt


def _demo() -> int:
    argv = sys.argv[1:]
    print("== Revit page ECC: interleaved cyclic Hamming (binary BCH family) ==")
    print("full page: I=255 m=11 g(x)=x^2805+x^510+1, 12 zero bits (=field Z=0),"
          " 2805 parity bits, t_pad=7 -> 353-byte trailer")
    print("\n-- final partial pages (all ECC streams, all 6 files) --")
    fo, ft, to, tt = prove_corpus(verbose=True)
    print(f"\n-- full pages: {fo}/{ft} byte-exact --")
    print(f"-- final pages: {to}/{tt} byte-exact --")
    if "--sweep" in argv:
        diff = [L for L in range(1, PAGE + 1)
                if (geometry(L).I, geometry(L).m) != (geometry_min_parity(L).I, geometry_min_parity(L).m)]
        print(f"\n-- DLL-threshold rule vs min-parity rule differ for {len(diff)} of {PAGE} lengths"
              f" (ranges start: {diff[:1]} ... total windows) --")
    if "--rs" in argv:
        print("\n-- Reed-Solomon hypothesis grid on Formats/Latest page 0 (negative control) --")
        raw = open(os.path.join(EXTRACTED, "rstbasicsampleproject", "Formats__Latest.bin"), "rb").read()
        for h in rs_negative_grid(raw[:PAGE], raw[PAGE:STRIDE]):
            print("   ", h)
    if "--fit" in argv:
        print("\n-- fitter re-run on the small tails (the cracking evidence) --")
        for f, name, raw in iter_raw_streams():
            for k, page in iter_pages(raw):
                if len(page) != STRIDE and len(page) < 1200:
                    hits = fit_tail(page, Irange=range(60, 90), mrange=(4, 5, 6, 7))
                    print(f"   {f[:14]:14s} {name:28s} R={len(page):5d} "
                          + " ".join(f"(I={h['I']},m={h['m']},s<={h['s_max']})" for h in hits))
    print(f"\nRESULT: full {fo}/{ft}  final {to}/{tt}")
    return 0 if (fo == ft > 0 and to == tt > 0) else 1


if __name__ == "__main__":
    sys.exit(_demo())

"""ecc-intel: Revit page-trailer ECC (Foundation\\Utility\\CRCIO.cpp), reproduced.

Reverse-engineered from Utility.dll (Revit 2023.1.9). A "page" is one CRCIO
encoding block: the payload followed by an N-bit pad-count field and the
interleaved CRC parity of `second` bit-lanes (lane i = every bit position
p with p mod second == i), each lane protected by an m-bit reflected CRC.
Parameter class (m, poly, period, align) is chosen by data size; a full
64,896-byte page uses (11, 0x500, 2047, 2) => 255 lanes x 11 parity bits.
"""
from __future__ import annotations

# (m checksum bits, reflected poly, period, align) -- the 8 selectable
# classes (from the DLL's static initializers), largest first.
PARAM_CLASSES = [
    (11, 0x500, 2047, 2), (9, 0x110, 511, 2), (7, 0x60, 127, 2),
    (6, 0x30, 63, 2), (5, 0x14, 31, 2), (4, 0xC, 15, 2), (3, 5, 7, 2),
    (2, 3, 3, 4),
]
# Additional param objects that exist in the DLL (alternate polys):
ALT_PARAMS = [(9,0x108,511,2),(8,0x90,200,2),(7,0x48,127,2),(7,0x44,127,2),
              (7,0x41,127,2),(6,0x21,63,2),(5,0x12,31,2),(4,9,15,2),(3,6,7,2)]


def size_field_bits(period: int, align: int) -> int:
    r9 = max(period * align, 65)
    nb = (r9 + 7) >> 3
    e, c = 0, 1
    while c < nb:
        c <<= 1
        e += 1
    return e


def geometry(nbytes: int, m: int, period: int, align: int, N: int):
    """Return (first=codeword length in bits, second=#lanes) for encoding
    `nbytes` of data (mirrors CRCIO fn 0x872e0 with flag=0)."""
    bits = nbytes * 8
    D = period - m
    rdx = bits + N
    if rdx <= 65 * D:
        second = 65
        first = (rdx + 64) // 65 + m
    else:
        cw = -(-rdx // D)
        rem = (cw - 65) % align
        if rem:
            cw += align - rem
        second, first = cw, period
    return first, second


def encoded_size(nbytes: int, m: int, period: int, align: int, N: int) -> int:
    first, second = geometry(nbytes, m, period, align, N)
    return (first * second + 7) // 8


def _crc_planes(buf: bytes, rounds: int, second: int, poly: int, m: int) -> list:
    """Bit-sliced reflected CRC (init 0) of all ``second`` lanes at once.

    Bit p of ``buf`` (little-endian) is lane ``p % second``'s input at round
    ``p // second``, so one round's inputs are ``second`` contiguous bits.
    The CRC state is ``m`` ints ("planes"; bit i of plane j == bit j of lane
    i's register): a round is a few big-int ops instead of ``second`` scalar
    ones.  Returns the planes after ``rounds`` rounds; bits of ``buf`` past
    ``rounds * second`` are ignored."""
    lane_mask = (1 << second) - 1
    assert (poly >> (m - 1)) & 1              # reflected poly: top tap always set
    low_taps = [j for j in range(m - 1) if (poly >> j) & 1]
    c = [0] * m
    CH = 8                                    # rounds per chunk (x8 = byte-aligned)
    step = CH * second >> 3
    for r in range(0, rounds, CH):
        off = r * second >> 3
        chunk = int.from_bytes(buf[off:off + step], "little")
        for _ in range(min(CH, rounds - r)):
            fb = c[0] ^ (chunk & lane_mask)   # (state ^ in) & 1, every lane
            chunk >>= second
            del c[0]                          # state >>= 1 ...
            c.append(fb)                      # ... ^= top tap where fb set
            for j in low_taps:                # ... ^= the other taps
                c[j] ^= fb
    return c


def encode_block(data: bytes, params=(11, 0x500, 2047, 2)) -> bytes:
    """Return the full encoded block (data + pad + size field + parity).
    Lane-parallel; byte-identical to the bit-at-a-time ``_encode_block_ref``
    (parity plane j lands at bit ``pre + j*second``, i.e. CRCIO's "parity
    bit j of lane i -> bit pre + i + j*second")."""
    m, poly, period, align = params
    N = size_field_bits(period, align)
    first, second = geometry(len(data), m, period, align, N)
    rounds = first - m
    pre = rounds * second                     # bits before the parity area
    pad_bytes = (pre - len(data) * 8 - N) >> 3
    assert 0 <= pad_bytes < (1 << N)
    big = int.from_bytes(data, "little") | (pad_bytes << (pre - N))
    planes = _crc_planes(big.to_bytes((pre + 7) >> 3, "little"),
                         rounds, second, poly, m)
    parity = 0
    for j, plane in enumerate(planes):
        parity |= plane << (j * second)
    big |= parity << pre
    return big.to_bytes((first * second + 7) >> 3, "little")


def _encode_block_ref(data: bytes, params=(11, 0x500, 2047, 2)) -> bytes:
    """Reference bit-at-a-time encoder (the original CRCIO transcription);
    ~90 ms per full page.  Kept only as the oracle for ``encode_block``."""
    m, poly, period, align = params
    N = size_field_bits(period, align)
    bits = len(data) * 8
    first, second = geometry(len(data), m, period, align, N)
    total_bytes = (first * second + 7) // 8
    pre = (first - m) * second               # bits before the parity area
    buf = bytearray(total_bytes)
    buf[:len(data)] = data
    slack = pre - bits - N
    assert slack >= 0
    pad_bytes = slack >> 3
    pos = pre - N                            # N-bit pad-byte-count field
    for k in range(N):
        p = pos + k
        if (pad_bytes >> k) & 1:
            buf[p >> 3] |= 1 << (p & 7)
    # per-lane reflected CRC (init 0, no xorout) over bits 0..pre-1
    crc = [0] * second
    lane = 0
    for p in range(pre):
        bit = (buf[p >> 3] >> (p & 7)) & 1
        c = crc[lane]
        fb = (c ^ bit) & 1
        c >>= 1
        if fb:
            c ^= poly
        crc[lane] = c
        lane += 1
        if lane == second:
            lane = 0
    # parity bit j (LSB first) of lane i -> bit position pre + i + j*second
    for i, c in enumerate(crc):
        for j in range(m):
            if (c >> j) & 1:
                q = pre + i + j * second
                buf[q >> 3] ^= 1 << (q & 7)
    return bytes(buf)


def page_trailer(page: bytes, params=(11, 0x500, 2047, 2)) -> bytes:
    """Trailer bytes appended after `page` (for a full 64,896-byte page this
    is the 353-byte trailer)."""
    out = encode_block(page, params)
    return out[len(page):]


# ---- parameter-class selection (mirrors CRCIO fns 0x86e90 / 0x87220) ----
def _geom_flag1(size: int, m: int, period: int, align: int):
    bits = size * 8
    r14 = bits // period
    if r14 > 65:
        r14 -= (r14 - 65) % align
    if r14 < 65:
        return bits // 65, 65
    return period, r14


def _pre_bits(size: int, p) -> int:
    m, poly, period, align = p
    first, second = _geom_flag1(size, m, period, align)
    return 0 if first < m else (first - m) * second


def _cap(p, size: int) -> int:
    N = size_field_bits(p[2], p[3])
    pre = _pre_bits(size, p)
    return 0 if pre <= N else (pre - N) >> 3


def _thresholds():
    import math
    t = []
    for i in range(len(PARAM_CLASSES) - 1):
        big, small = PARAM_CLASSES[i], PARAM_CLASSES[i + 1]
        x = math.ceil(big[0] * small[2] / small[0])
        buf_bytes = ((x * 65 + 7) >> 3) - 1
        a = _cap(big, buf_bytes)
        b = encoded_size(a, *small[:1], small[2], small[3],
                         size_field_bits(small[2], small[3]))
        c = _cap(small, b)
        t.append(c)
    return t


_THRESH = _thresholds()   # data-length thresholds: [5081, 1274, 548, 256, 105, 40, 7]


def select_params(nbytes: int):
    """The parameter class CRCIO uses for a block of `nbytes` data bytes."""
    for i in range(len(PARAM_CLASSES) - 2, -1, -1):
        if _THRESH[i] >= nbytes:
            return PARAM_CLASSES[i + 1]
    return PARAM_CLASSES[0]


PAGE_PAYLOAD = 64_896
PAGE_STRIDE = 65_249


def frame_stream(logical: bytes) -> bytes:
    """Encode a whole logical stream into its raw page-framed CRCIO form:
    every full 64,896-byte page + 353-byte trailer, then the final partial
    block encoded with the size class selected by its byte count.
    ``iter_blocks`` is the inverse walk every reader/checker must use."""
    out = bytearray()
    pos = 0
    n = len(logical)
    while n - pos >= PAGE_PAYLOAD:
        out += encode_block(logical[pos:pos + PAGE_PAYLOAD])
        pos += PAGE_PAYLOAD
    if pos < n or n == 0:
        tail = logical[pos:]
        out += encode_block(tail, select_params(len(tail)))
    return bytes(out)


def iter_blocks(raw: bytes):
    """The ONE page-walk law for a CRCIO-framed raw stream -- the exact
    inverse of ``frame_stream``'s emission order, shared by every reader and
    checker: yields ``(block, is_final)``.  A PAGE_STRIDE-sized block that is
    FOLLOWED by more bytes is a full page (64,896 data bytes + 353-byte
    trailer); the LAST block (1..PAGE_STRIDE bytes) is always the final block
    and only its pad-count field can tell its data length: a final block of
    64,388..64,895 data bytes selects the full-page class and encodes to
    exactly PAGE_STRIDE bytes (pad field 1..508), indistinguishable by length
    from a genuine full page (pad field 0 -> 64,896 -- the same decode covers
    both).  A naive ``len(raw) // PAGE_STRIDE`` walk takes such a final block
    for a page: ~0.8 % of stream lengths (#236 / #294)."""
    pos, n = 0, len(raw)
    while n - pos > PAGE_STRIDE:
        yield raw[pos:pos + PAGE_STRIDE], False
        pos += PAGE_STRIDE
    if n:
        yield raw[pos:], True


def lane_syndromes(block: bytes, first: int, second: int, poly: int,
                   m: int) -> list:
    """Per-lane CRC syndromes of ONE encoded block, stdlib only.

    Bit p of the codeword belongs to lane ``p % second``, round
    ``p // second``; a valid codeword has every lane's syndrome == 0 and a
    single flipped bit at round r of lane i leaves lane i with the
    signature CRCIO's decoder looks up (validate._signature_table).

    Bit-sliced (the encoder's ``_crc_planes`` run over all ``first`` rounds,
    then transposed plane -> lane): well under 1 ms per full 64,896-byte
    page, stdlib only -- numpy is never a requirement for verification
    (issue #75: the bare plugin surface has no numpy and must still verify,
    not skip or crash)."""
    out = [0] * second
    for j, plane in enumerate(_crc_planes(block, first, second, poly, m)):
        i = 0
        while plane:
            if plane & 1:
                out[i] |= 1 << j
            plane >>= 1
            i += 1
    return out


def _block_data_len(block_len: int, params) -> int:
    """Exact data byte-count of an encoded block of `block_len` bytes
    (reader side: flag=1 geometry + the N-bit pad-count field)."""
    m, poly, period, align = params
    N = size_field_bits(period, align)
    first, second = _geom_flag1(block_len, m, period, align)
    pre = 0 if first < m else (first - m) * second
    return pre, N


def final_block_candidates(tail: bytes) -> list:
    """``[(params, data_len)]`` for every size class whose N-bit pad-count
    field self-consistently decodes this final (partial) block: the data
    length is in range, selects that very class, and re-encodes to exactly
    ``len(tail)`` bytes.  Usually one candidate; the caller disambiguates by
    exact re-encode (``unframe_stream``) or by syndrome check (the
    validator).  Empty list == not a CRCIO block at all."""
    L = len(tail)
    out = []
    for params in PARAM_CLASSES:
        m, poly, period, align = params
        pre, N = _block_data_len(L, params)
        if pre <= N or (pre + 7) // 8 > L:
            continue
        fpos = pre - N                       # pad-count field: N bits, LSB first
        pad = 0
        for k in range(N):
            p = fpos + k
            if (tail[p >> 3] >> (p & 7)) & 1:
                pad |= 1 << k
        data_len = ((pre - N) >> 3) - pad
        if 0 <= data_len <= L and select_params(data_len) == params \
           and encoded_size(data_len, m, period, align, N) == L:
            out.append((params, data_len))
    return out


def final_block_data_len(block: bytes):
    """Exact data byte-count of a FINAL block (``iter_blocks``' last item):
    the size class whose pad-count field decodes it AND reproduces it
    byte-for-byte on re-encode -- a genuine full page included (pad 0 ->
    PAGE_PAYLOAD).  ``None`` == no class does (not CRCIO-framed, or damaged,
    or an Autodesk-born partial block with heap bytes leaked into its pad
    region -- those verify by syndrome in ``rvt.validate``, never here)."""
    for params, data_len in final_block_candidates(block):
        if encode_block(block[:data_len], params) == block:
            return data_len
    return None


def unframe_stream(raw: bytes) -> bytes:
    """Inverse of frame_stream for a CRCIO-framed raw stream (walked by
    ``iter_blocks``): strips every full page's 353-byte trailer and decodes
    the final block's exact data length from its pad-count field.  No error
    correction is attempted; a final block no size class reproduces raises
    ``ValueError`` (e.g. an unframed stream handed in by mistake)."""
    out = bytearray()
    for block, is_final in iter_blocks(raw):
        data_len = final_block_data_len(block) if is_final else PAGE_PAYLOAD
        if data_len is None:
            raise ValueError("final block is not CRCIO-framed (raw stream?)")
        out += block[:data_len]
    return bytes(out)


def framing_mismatches(raw: bytes) -> int:
    """How many CRCIO blocks of a framed raw stream (walked by
    ``iter_blocks``) break ``frame_stream``'s law: a full page whose trailer
    is not ``page_trailer(payload)``, or a final block no size class decodes
    and reproduces.  0 <=> ``frame_stream(unframe_stream(raw)) == raw``.  The
    post-write self-check for streams WE framed (verify_written /
    verify_manipulated / verify_reduced); Autodesk-born partial blocks are
    ``rvt.validate``'s (syndrome) business, not this exact re-encode's."""
    bad = 0
    for block, is_final in iter_blocks(raw):
        bad += ((final_block_data_len(block) is None) if is_final else
                (page_trailer(block[:PAGE_PAYLOAD]) != block[PAGE_PAYLOAD:]))
    return bad


if __name__ == "__main__":   # demo: rstbasic Formats/Latest page 0 + round-trip
    import olefile
    ole = olefile.OleFileIO('samples/racbasicsampleproject.rvt')
    for name in ('Formats/Latest', 'Global/History', 'Contents', 'Global/PartitionTable'):
        raw = ole.openstream(name.split('/')).read()
        logical = unframe_stream(raw)
        print(name, 'raw', len(raw), 'logical', len(logical),
              'blocks not byte-exact:', framing_mismatches(raw),
              'round-trip:', frame_stream(logical) == raw)

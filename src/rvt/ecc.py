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


def _crc_planes(big: int, rounds: int, second: int, poly: int, m: int) -> list:
    """Bit-sliced per-lane reflected CRC (init 0, no xorout), stdlib only.

    ``big`` is the codeword prefix as one little-endian int: bit p belongs to
    lane ``p % second``, round ``p // second`` -- so round r's input bit of
    every lane is the contiguous slice ``big >> (r*second) & lane_mask``.
    The ``m`` CRC state bits are kept as ``m`` Python ints ("planes") whose
    bit i is lane i's state bit; one round is then a handful of big-int
    XORs over ``second`` (<= 2047) bits instead of ``second`` scalar
    updates.  Returns the planes: bit i of ``planes[j]`` == bit j of lane
    i's CRC.  (Same slicing as the verify side's ``lane_syndromes``, #75.)"""
    lane_mask = (1 << second) - 1
    taps = [j for j in range(m) if (poly >> j) & 1]
    c = [0] * m
    CH = 64                                  # rounds sliced off `big` per chunk
    chunk_bits = CH * second
    chunk_mask = (1 << chunk_bits) - 1
    r = 0
    while r < rounds:
        chunk = big & chunk_mask
        big >>= chunk_bits
        for _ in range(min(CH, rounds - r)):
            fb = c[0] ^ (chunk & lane_mask)  # (state ^ in) & 1, all lanes
            chunk >>= second
            c = c[1:] + [0]                  # state >>= 1, all lanes
            for j in taps:                   # state ^= poly where fb set
                c[j] ^= fb
        r += CH
    return c


def encode_block(data: bytes, params=(11, 0x500, 2047, 2)) -> bytes:
    """Return the full encoded block (data + pad + size field + parity).

    Lane-parallel (bit-sliced) encoder, byte-identical to the bit-at-a-time
    reference ``_encode_block_ref`` (kept for the tests): the codeword is
    built as one int -- data bits, zero slack, the N-bit pad-byte-count
    field at bit ``pre - N``, then parity plane j (bit i = parity bit j of
    lane i) at bit ``pre + j*second`` -- which is exactly CRCIO's layout
    "parity bit j of lane i -> bit position pre + i + j*second"."""
    m, poly, period, align = params
    N = size_field_bits(period, align)
    first, second = geometry(len(data), m, period, align, N)
    rounds = first - m
    pre = rounds * second                    # bits before the parity area
    slack = pre - len(data) * 8 - N
    assert slack >= 0
    pad_field = (slack >> 3) & ((1 << N) - 1)
    big = int.from_bytes(data, "little") | (pad_field << (pre - N))
    shift = pre
    for plane in _crc_planes(big, rounds, second, poly, m):
        big |= plane << shift
        shift += second
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
    block encoded with the size class selected by its byte count."""
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


def lane_syndromes(block: bytes, first: int, second: int, poly: int,
                   m: int) -> list:
    """Per-lane CRC syndromes of ONE encoded block, stdlib only.

    Bit p of the codeword belongs to lane ``p % second``, round
    ``p // second``; a valid codeword has every lane's syndrome == 0 and a
    single flipped bit at round r of lane i leaves lane i with the
    signature CRCIO's decoder looks up (validate._signature_table).

    Bit-sliced: the ``m`` CRC state bits are kept as ``m`` Python ints whose
    bit i is lane i's state bit, so one round is a handful of big-int XORs
    over ``second`` (<= 2047) bits instead of ``second`` scalar updates --
    ~2 ms per full 64,896-byte page, i.e. numpy is an optional accelerator
    for this, never a requirement (issue #75: the bare plugin surface has
    no numpy and must still verify, not skip or crash)."""
    nb = first * second
    big = int.from_bytes(block[:(nb + 7) >> 3], "little")
    if nb & 7:
        big &= (1 << nb) - 1
    lane_mask = (1 << second) - 1
    taps = [j for j in range(m) if (poly >> j) & 1]
    c = [0] * m                      # c[j] bit i == bit j of lane i's CRC
    CH = 64                          # rounds sliced off `big` per chunk
    chunk_bits = CH * second
    chunk_mask = (1 << chunk_bits) - 1
    r = 0
    while r < first:
        chunk = big & chunk_mask
        big >>= chunk_bits
        for _ in range(min(CH, first - r)):
            fb = c[0] ^ (chunk & lane_mask)          # (state ^ in) & 1, all lanes
            chunk >>= second
            c = c[1:] + [0]                          # state >>= 1, all lanes
            for j in taps:                           # ^= poly where fb set
                c[j] ^= fb
        r += CH
    out = [0] * second
    for j, plane in enumerate(c):
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


def unframe_stream(raw: bytes) -> bytes:
    """Inverse of frame_stream for a CRCIO-framed raw stream: strips every
    full page's 353-byte trailer and decodes the final block's exact data
    length from its pad-count field. (No error correction is attempted.)"""
    out = bytearray()
    pos, n = 0, len(raw)
    while n - pos >= PAGE_STRIDE:
        out += raw[pos:pos + PAGE_PAYLOAD]
        pos += PAGE_STRIDE
    tail = raw[pos:]
    if tail:
        # the right size class reproduces the block exactly
        for params, data_len in final_block_candidates(tail):
            if encode_block(tail[:data_len], params) == tail:
                out += tail[:data_len]
                break
        else:
            raise ValueError("final block is not CRCIO-framed (raw stream?)")
    return bytes(out)


if __name__ == "__main__":   # demo: rstbasic Formats/Latest page 0 + round-trip
    import olefile
    ole = olefile.OleFileIO('samples/racbasicsampleproject.rvt')
    for name in ('Formats/Latest', 'Global/History', 'Contents', 'Global/PartitionTable'):
        raw = ole.openstream(name.split('/')).read()
        page = raw[:PAGE_PAYLOAD] if len(raw) >= PAGE_STRIDE else None
        if page is not None:
            print(name, 'page0 trailer byte-exact:',
                  page_trailer(page) == raw[PAGE_PAYLOAD:PAGE_STRIDE])
        logical = unframe_stream(raw)
        print(name, 'raw', len(raw), 'logical', len(logical),
              'round-trip:', frame_stream(logical) == raw)

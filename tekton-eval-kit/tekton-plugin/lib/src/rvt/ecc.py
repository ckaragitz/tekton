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


def encode_block(data: bytes, params=(11, 0x500, 2047, 2)) -> bytes:
    """Return the full encoded block (data + pad + size field + parity)."""
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


def _block_data_len(block_len: int, params) -> int:
    """Exact data byte-count of an encoded block of `block_len` bytes
    (reader side: flag=1 geometry + the N-bit pad-count field)."""
    m, poly, period, align = params
    N = size_field_bits(period, align)
    first, second = _geom_flag1(block_len, m, period, align)
    pre = 0 if first < m else (first - m) * second
    return pre, N


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
        # try each size class; the right one reproduces the block exactly
        for params in PARAM_CLASSES:
            pre, N = _block_data_len(len(tail), params)
            if pre <= N or (pre + 7) // 8 > len(tail):
                continue
            # read pad-count field (N bits, LSB-first) at bit pre-N
            fpos = pre - N
            pad = 0
            for k in range(N):
                p = fpos + k
                if (tail[p >> 3] >> (p & 7)) & 1:
                    pad |= 1 << k
            data_len = ((pre - N) >> 3) - pad
            if 0 <= data_len <= len(tail) and select_params(data_len) == params \
               and encode_block(tail[:data_len], params) == tail:
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

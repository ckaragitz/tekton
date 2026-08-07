"""Decoders for ``Global/ContentDocuments`` and ``Global/History``.

Both streams share the common ``Global/*`` envelope:

    [8-byte LE prefix][gzip header (10 B)][raw deflate ...][gzip trailer:
     crc32 + isize][zero padding][opaque footer blob]

* ``Global/History`` inflates to ``ADocument::m_pHistory`` -- the document's
  save/episode history: a header, the list of internal *format version*
  numbers the file has been saved under (upgrade history, ends in 2662 for
  every Revit 2026 file) and a newest-first array of 17-byte episode records
  (16-byte little-endian GUID + one constant tag byte 0x28).  Record 0 is the
  document's own "unique document GUID" from ``BasicFileInfo``.

* ``Global/ContentDocuments`` inflates to ``ADocument::m_oContentTable`` -- an
  ordered map (keys = 16-byte GUIDs, ascending memcmp order) of embedded
  "content document" objects.  Each entry starts with the 12-byte marker
  ``a3 03 ff ff ff ff a2 03 ff ff ff ff`` (two null class-tagged pointers),
  then the 16-byte GUID key, then an ``ADocument``-style serialization whose
  prologue tag sequence is byte-identical to the start of ``Global/Latest``.
  Entries are not length-prefixed reliably; the map is enumerated by scanning
  for the marker and validated by key monotonicity.

Anomaly handled here: in ``racadvancedsampleproject`` and
``dach-sample-project`` the ContentDocuments deflate stream does not decode
end-to-end (the same defect hits ElemTable in dach/rme).  ``inflate_global``
therefore performs *segmented recovery*: decode the primary stream until the
first invalid block, then scan forward for the next strictly-valid dynamic
Huffman block header that decodes cleanly to end-of-stream, and report the
undecodable gap.  Recovered tail segments are decoded with an unknown 32 KiB
history window (back-references into it are flagged as untrusted).

Run:  python -m rvt.content            # all six extracted samples
      python -m rvt.content <extracted-dir-or-Global__*.bin ...>
"""
from __future__ import annotations

import glob
import os
import re
import struct
import sys
import uuid
import zlib
import datetime
from dataclasses import dataclass, field
from typing import Iterable, List, Optional, Tuple

# ----------------------------------------------------------------------------
# The common Global/* envelope
# ----------------------------------------------------------------------------

GZIP_MAGIC = b"\x1f\x8b\x08"
#: End-of-stream signature emitted by Revit's writer just before the gzip
#: trailer: an empty stored block (Z_SYNC_FLUSH) followed by two empty
#: fixed-Huffman blocks, the last one FINAL.
DEFLATE_TAIL_SIG = b"\x00\x00\xff\xff\x02\x0c\x00"


@dataclass
class Segment:
    """One independently-decoded run of deflate blocks inside a stream."""
    index: int
    comp_start: int          # byte offset in the raw stream where decoding starts
    comp_end: int            # byte offset where decoding stopped
    out_len: int             # bytes produced by this segment
    status: str              # 'eof' | 'error' | 'truncated'
    error: Optional[str] = None
    trusted: bool = True     # False = decoded with an unknown 32 KiB history window


@dataclass
class GlobalStream:
    """Everything we can say about a Global/* stream's envelope."""
    name: str
    raw_len: int
    prefix: bytes                    # the 8 bytes before the gzip header
    prefix_lo: int
    prefix_hi: int
    gzip_offset: int                 # offset of 1f 8b 08 (normally 8)
    gzip_flg: int
    payload: bytes                   # best-effort inflated bytes (segments concatenated)
    segments: List[Segment] = field(default_factory=list)
    complete: bool = False           # primary deflate reached its final block
    trailer_crc32: Optional[int] = None
    trailer_isize: Optional[int] = None
    crc_ok: Optional[bool] = None
    isize_ok: Optional[bool] = None
    tail_sig_ok: bool = False        # deflate ends with 00 00 ff ff 02 0c 00
    pad_zeros: int = 0
    footer: bytes = b""              # opaque high-entropy blob at stream end

    @property
    def gap(self) -> Optional[Tuple[int, int]]:
        """(start, end) raw offsets of undecodable compressed bytes, if any."""
        if len(self.segments) >= 2:
            return (self.segments[0].comp_end, self.segments[1].comp_start)
        if self.segments and self.segments[0].status == "error":
            return (self.segments[0].comp_end, self._deflate_data_end)
        return None

    _deflate_data_end: int = 0


# --- strict dynamic-Huffman block-header validator (for resync scanning) ---

_CL_ORDER = (16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15)


class _Bits:
    __slots__ = ("d", "p", "buf", "n")

    def __init__(self, data: bytes, pos: int):
        self.d, self.p, self.buf, self.n = data, pos, 0, 0

    def get(self, k: int) -> int:
        while self.n < k:
            self.buf |= self.d[self.p] << self.n   # IndexError == out of data
            self.p += 1
            self.n += 8
        v = self.buf & ((1 << k) - 1)
        self.buf >>= k
        self.n -= k
        return v


def _canon_table(lengths):
    """dict (bitlen, code) -> symbol for a canonical Huffman code, or None."""
    maxl = max(lengths) if lengths else 0
    if maxl == 0:
        return None
    bl = [0] * (maxl + 1)
    for L in lengths:
        if L:
            bl[L] += 1
    code, nxt = 0, [0] * (maxl + 2)
    for b in range(1, maxl + 1):
        code = (code + bl[b - 1]) << 1
        nxt[b] = code
    t = {}
    for s, L in enumerate(lengths):
        if L:
            t[(L, nxt[L])] = s
            nxt[L] += 1
    return t


def _decode(bits: _Bits, table, maxl):
    code = 0
    for L in range(1, maxl + 1):
        code = (code << 1) | bits.get(1)
        s = table.get((L, code))
        if s is not None:
            return s
    raise ValueError("bad code")


def _strict_dynamic_header_at(data: bytes, byte_off: int) -> bool:
    """True iff a *complete, non-oversubscribed* dynamic block header starts
    exactly at ``byte_off`` (bit 0).  This is the same acceptance test zlib
    applies, so a hit means zlib can decode from here (given a window)."""
    try:
        b = _Bits(data, byte_off)
        b.get(1)                       # BFINAL (either)
        if b.get(2) != 2:              # BTYPE must be dynamic
            return False
        hlit = b.get(5) + 257
        hdist = b.get(5) + 1
        hclen = b.get(4) + 4
        if hlit > 286 or hdist > 30:
            return False
        cl = [0] * 19
        for i in range(hclen):
            cl[_CL_ORDER[i]] = b.get(3)
        if abs(sum(2.0 ** -L for L in cl if L) - 1.0) > 1e-9:
            return False
        ct = _canon_table(cl)
        cmax = max(cl)
        lens: List[int] = []
        while len(lens) < hlit + hdist:
            s = _decode(b, ct, cmax)
            if s < 16:
                lens.append(s)
            elif s == 16:
                if not lens:
                    return False
                lens.extend([lens[-1]] * (b.get(2) + 3))
            elif s == 17:
                lens.extend([0] * (b.get(3) + 3))
            else:
                lens.extend([0] * (b.get(7) + 11))
        if len(lens) != hlit + hdist:
            return False
        ll, dl = lens[:hlit], lens[hlit:]
        if ll[256] == 0:
            return False
        if abs(sum(2.0 ** -L for L in ll if L) - 1.0) > 1e-9:
            return False
        nz = sum(1 for L in dl if L)
        k2 = sum(2.0 ** -L for L in dl if L)
        if not (abs(k2 - 1.0) < 1e-9 or nz == 1):
            return False
        return True
    except (IndexError, ValueError, ZeroDivisionError):
        return False


def _primary_inflate(comp: bytes, chunk: int = 4096):
    """Incrementally raw-inflate ``comp``.

    Returns (output, consumed_bytes, eof, error).  ``consumed_bytes`` is exact
    on eof (len(comp) - unused) and the last-good chunk boundary on error.
    """
    d = zlib.decompressobj(-zlib.MAX_WBITS)
    out = bytearray()
    pos = 0
    n = len(comp)
    while pos < n:
        try:
            out += d.decompress(comp[pos:pos + chunk])
        except zlib.error as e:
            return bytes(out), pos, False, str(e)
        if d.eof:
            return bytes(out), n - len(d.unused_data), True, None
        pos += chunk
    return bytes(out), pos, d.eof, None


def _resync(comp: bytes, start: int, history: bytes, log=None):
    """Scan ``comp[start:]`` for the next byte offset where a strictly-valid
    dynamic block begins AND decodes cleanly to end-of-stream.

    Returns (offset, output, consumed) or None.  The 32 KiB window is primed
    with ``history`` (our best guess: the previously decoded tail); bytes
    reached only through back-references into that window are untrusted.
    """
    zdict = (history[-32768:] if history else b"") or b"\x00" * 32768
    n = len(comp)
    pos = start
    while pos < n - 8:
        if _strict_dynamic_header_at(comp, pos):
            d = zlib.decompressobj(-zlib.MAX_WBITS, zdict=zdict)
            try:
                out = d.decompress(comp[pos:])
            except zlib.error:
                pos += 1
                continue
            if d.eof:
                return pos, out, len(comp) - pos - len(d.unused_data)
        pos += 1
    return None


def inflate_global(raw: bytes, name: str = "?", resync: bool = True) -> GlobalStream:
    """Decode a whole ``Global/*`` stream: prefix, deflate payload
    (segment-recovering), gzip trailer, padding and footer blob."""
    gz = raw.find(GZIP_MAGIC)
    if gz < 0:
        raise ValueError(f"{name}: no gzip header")
    prefix = raw[:gz]
    lo, hi = (struct.unpack_from("<II", prefix + b"\0" * 8)[:2])
    flg = raw[gz + 3]
    comp_start = gz + 10                     # skip the 10-byte gzip header
    comp = raw[comp_start:]

    gs = GlobalStream(name=name, raw_len=len(raw), prefix=prefix, prefix_lo=lo,
                      prefix_hi=hi, gzip_offset=gz, gzip_flg=flg, payload=b"")

    out, consumed, eof, err = _primary_inflate(comp)
    segs = [Segment(0, comp_start, comp_start + consumed, len(out),
                    "eof" if eof else "error", err, True)]
    payload = bytearray(out)

    if not eof and resync:
        # Segment recovery: find a resumable block start after the failure.
        cursor = consumed
        seg_idx = 1
        while cursor < len(comp) and not eof:
            r = _resync(comp, cursor, bytes(payload))
            if r is None:
                break
            off, more, used = r
            segs.append(Segment(seg_idx, comp_start + off, comp_start + off + used,
                                len(more), "eof", None, trusted=False))
            payload += more
            eof = True                      # tail reached final block
            cursor = off + used
            seg_idx += 1

    gs.segments = segs
    gs.complete = segs[-1].status == "eof"
    gs.payload = bytes(payload)

    # Locate the physical end of the deflate data (writer's tail signature)
    tail = raw.rfind(DEFLATE_TAIL_SIG)
    deflate_end = tail + len(DEFLATE_TAIL_SIG) if tail >= 0 else comp_start + consumed
    gs.tail_sig_ok = tail >= 0
    gs._deflate_data_end = deflate_end
    rest = raw[deflate_end:]
    if len(rest) >= 8:
        gs.trailer_crc32, gs.trailer_isize = struct.unpack_from("<II", rest)
        gs.crc_ok = gs.trailer_crc32 == (zlib.crc32(gs.payload) & 0xFFFFFFFF)
        gs.isize_ok = gs.trailer_isize == (len(gs.payload) & 0xFFFFFFFF)
        body = rest[8:]
        z = 0
        while z < len(body) and body[z] == 0:
            z += 1
        gs.pad_zeros = z
        gs.footer = body[z:]
    return gs


# ----------------------------------------------------------------------------
# Global/History  (ADocument::m_pHistory)
# ----------------------------------------------------------------------------

HISTORY_CLASS_TAG = 0x0538   # u16 at offset 0; same tag appears as a null
                             # object-pointer field in every ContentDocuments
                             # entry prologue -> class id of the history object.
HISTORY_RECORD_LEN = 17      # 16-byte GUID + 1 constant byte (0x28)


@dataclass
class HistoryEntry:
    index: int
    guid: uuid.UUID
    tag: int                          # trailing byte, observed constant 0x28
    when: Optional[datetime.datetime] # decoded only for RFC-4122 version-1 GUIDs
    mac: Optional[str]                # node/MAC from a v1 GUID

    @property
    def is_v1(self) -> bool:
        return self.guid.version == 1


@dataclass
class History:
    class_tag: int
    version: int                      # u16 at +2, always 1 in corpus
    hdr_count: int                    # u32 at +0x0e, == len(entries)
    header_guids: List[uuid.UUID]     # 5 slots at +0x16 (slot 3 always zero)
    format_versions: List[int]        # ascending internal format numbers
    entries: List[HistoryEntry]       # newest first, oldest (2001-era v1) last
    trailing: bytes                   # bytes after the entry array (u32 0)

    @property
    def document_guid(self) -> Optional[uuid.UUID]:
        """Entry 0 == BasicFileInfo 'Unique Document GUID'."""
        return self.entries[0].guid if self.entries else None

    @property
    def current_format(self) -> Optional[int]:
        return self.format_versions[-1] if self.format_versions else None


_GREG = datetime.datetime(1582, 10, 15)


def _v1_time(g: uuid.UUID):
    if g.version != 1:
        return None, None
    when = _GREG + datetime.timedelta(microseconds=g.time // 10)
    mac = ":".join(f"{(g.node >> s) & 0xff:02x}" for s in range(40, -8, -8))
    return when, mac


def parse_history(payload: bytes) -> History:
    """Parse an inflated ``Global/History`` payload.

    Layout (all little-endian):
      +0x00 u16 class tag 0x0538          +0x02 u16 version (1)
      +0x04 u16 0  +0x06 u32 0  +0x0a u32 0
      +0x0e u32 entry count (repeated later)   +0x12 u32 0
      +0x16 GUID[5] header slots: g, g, g, ZERO, g   (16 bytes each, bytes_le)
      +0x66 u32 nversions, then nversions * u32 format version (ascending)
      then  u32 nentries, then nentries * 17-byte record: GUID(16, bytes_le)+u8 0x28
      then  u32 0
    """
    if len(payload) < 0x6a:
        raise ValueError("history payload too small")
    class_tag, version = struct.unpack_from("<HH", payload, 0)
    hdr_count = struct.unpack_from("<I", payload, 0x0e)[0]
    header_guids = [uuid.UUID(bytes_le=payload[0x16 + 16 * i:0x26 + 16 * i]) for i in range(5)]
    nver = struct.unpack_from("<I", payload, 0x66)[0]
    off = 0x6a
    versions = list(struct.unpack_from(f"<{nver}I", payload, off))
    off += 4 * nver
    nrec = struct.unpack_from("<I", payload, off)[0]
    off += 4
    entries: List[HistoryEntry] = []
    for i in range(nrec):
        rec = payload[off:off + HISTORY_RECORD_LEN]
        if len(rec) < HISTORY_RECORD_LEN:
            break
        g = uuid.UUID(bytes_le=rec[:16])
        when, mac = _v1_time(g)
        entries.append(HistoryEntry(i, g, rec[16], when, mac))
        off += HISTORY_RECORD_LEN
    return History(class_tag, version, hdr_count, header_guids, versions, entries, payload[off:])


# ----------------------------------------------------------------------------
# Global/ContentDocuments  (ADocument::m_oContentTable)
# ----------------------------------------------------------------------------

#: 12-byte entry marker: two null class-tagged pointers (class 0x03a3 = -1,
#: class 0x03a2 = -1) that open every embedded content-document entry.
CD_ENTRY_MAGIC = bytes.fromhex("a303ffffffff" "a203ffffffff")
# General entry marker: class tag 0x03a3 <u32 pid> then class tag 0x03a2
# <u32 pid>. The skeleton form (both pids == 0xffffffff, i.e. null pointers)
# is CD_ENTRY_MAGIC above, but real entries also carry NON-null lead
# pointers (found by the family-authoring stream: only 32/305 rme entries
# were recovered with the null-only marker; the recessed-light and
# panelboard documents were among the missed). Match the tags with ANY
# 4-byte pointer between them and rely on the ascending-GUID monotonic
# filter + prologue check to reject in-payload false positives.
CD_ENTRY_RE = re.compile(rb"\xa3\x03.{4}\xa2\x03.{4}", re.DOTALL)

#: The ADocument prologue that follows the GUID key + u32 in the "clean"
#: entries.  Byte-identical to Global/Latest's opening tag sequence except
#: for two extra tagged fields (0x05c9, 0x0538=history ptr) and the format
#: version u32 (2660 here vs 2662 in Global/Latest).
CD_PROLOGUE_TAGS = (0x001C, 0x05C9, 0x03A7, 0x01A0, 0x1066, 0x0538, 0x0FF8, 0x0AE9)


@dataclass
class ContentEntry:
    index: int
    offset: int              # offset of the a3 03 ff.. marker in the payload
    length: int              # bytes to next entry (or end of payload)
    key: uuid.UUID           # 16-byte GUID key (stored bytes_le at +12)
    key_bytes: bytes
    u32_1c: int              # u32 immediately after the key (== length-36 for
                             #  "skeleton" entries: their first body block size)
    element_id: Optional[int]  # ElementId (u64) after tag 0x0ae9 (host doc), None if -1
    format_version: Optional[int]  # u32 near +0x6c: 2660 for clean entries
    table_tag: Optional[int]   # u16 at +0x7f (0x0644 for clean entries)
    table_count: Optional[int] # u32 at +0x81 (element records of 40 bytes)
    kind: str                # 'skeleton' | 'extended' | 'anomalous'

    @property
    def key_sort(self) -> bytes:
        return self.key_bytes


@dataclass
class ContentMap:
    entries: List[ContentEntry]
    payload_len: int
    coverage: int            # bytes accounted for by entries (should == payload_len)
    monotonic: bool          # keys strictly ascending (validates the framing)
    prologue_variants: int   # entries whose prologue deviates from the clean form

    def kinds(self):
        from collections import Counter
        return Counter(e.kind for e in self.entries)


def _clean_prologue(p: bytes, h: int) -> bool:
    """Does the entry at ``h`` carry the canonical prologue field values?"""
    try:
        return (struct.unpack_from("<H", p, h + 32)[0] == 0x1C
                and struct.unpack_from("<H", p, h + 38)[0] == 0x05C9
                and struct.unpack_from("<H", p, h + 48)[0] == 0x03A7
                and struct.unpack_from("<H", p, h + 58)[0] == 0x01A0
                and struct.unpack_from("<H", p, h + 64)[0] == 0x1066
                and struct.unpack_from("<H", p, h + 70)[0] == 0x0538
                and struct.unpack_from("<H", p, h + 76)[0] == 0x0FF8
                and struct.unpack_from("<H", p, h + 86)[0] == 0x0AE9)
    except struct.error:
        return False


def scan_content_documents(payload: bytes) -> ContentMap:
    """Enumerate the embedded content-document entries of an inflated
    ``Global/ContentDocuments`` payload (an ordered map keyed by GUID).

    Entry layout (offsets relative to the marker):
      +0x00  a3 03 ff ff ff ff   null ptr, class tag 0x03a3
      +0x06  a2 03 ff ff ff ff   null ptr, class tag 0x03a2
      +0x0c  GUID key (16 bytes, bytes_le, keys ascend in memcmp order)
      +0x1c  u32                 first body block size (== entry_len-36 for
                                 skeleton entries)
      +0x20  document object: 1c 00 <i32 -1> | c9 05 <u32> <i32 -1> |
             a7 03 <u32 1> <i32 -1> | a0 01 <i32 -1> | 66 10 <i32 -1> |
             38 05 <i32 -1> | f8 0f <u32 0> <i32 -1> | e9 0a <u64 ElementId>
             <i64 -1> | u32 1 | u32 format_version(2660) | u32 0,0,0 |
             i32 -1 | 44 06 <u32 count> [count x 40-byte element records] ...
    Entry ends where the next marker begins.
    """
    cands = [m.start() for m in CD_ENTRY_RE.finditer(payload)]
    # The 12-byte marker can also occur inside a payload (false positive).
    # Keys are stored in ascending memcmp order, so drop any candidate whose
    # key does not exceed the previous accepted key unless it carries the
    # canonical prologue (a real entry with a duplicate-looking key never
    # occurs in the corpus).
    ms: List[int] = []
    last_key = b""
    for h in cands:
        kb = payload[h + 12:h + 28]
        if kb <= last_key and not _clean_prologue(payload, h):
            continue
        ms.append(h)
        last_key = kb
    entries: List[ContentEntry] = []
    monotonic = True
    variants = 0
    prev_key = b""
    n = len(payload)
    for i, h in enumerate(ms):
        end = ms[i + 1] if i + 1 < len(ms) else n
        key_bytes = payload[h + 12:h + 28]
        if key_bytes <= prev_key:
            monotonic = False
        prev_key = key_bytes
        key = uuid.UUID(bytes_le=key_bytes)
        u32_1c = struct.unpack_from("<I", payload, h + 28)[0] if h + 32 <= n else 0
        clean = _clean_prologue(payload, h)
        eid = fv = ttag = tcnt = None
        if clean and h + 0x85 <= n:
            e = struct.unpack_from("<q", payload, h + 0x58)[0]
            eid = None if e < 0 else e
            fv = struct.unpack_from("<I", payload, h + 0x6C)[0]
            ttag = struct.unpack_from("<H", payload, h + 0x7F)[0]
            if ttag == 0x0644:
                tcnt = struct.unpack_from("<I", payload, h + 0x81)[0]
            else:                 # a variant body layout (extra fields); the
                ttag = None       # element table sits elsewhere in that case
        else:
            variants += 1
        length = end - h
        if not clean:
            kind = "anomalous"
        elif length == u32_1c + 36:
            kind = "skeleton"
        else:
            kind = "extended"
        entries.append(ContentEntry(i, h, length, key, key_bytes, u32_1c, eid, fv,
                                    ttag, tcnt, kind))
    cov = (n - ms[0]) if ms else 0
    return ContentMap(entries, n, cov, monotonic, variants)


def element_records(payload: bytes, entry: ContentEntry, limit: int = 0):
    """Yield the 40-byte element records of a clean entry's first table.

    Record layout: u64 ElementId, u32 a, u32 b, i32 c, u64 ElementId (repeat),
    i64 previous ElementId (-1 for the first), u32 0.  ``a/b/c`` are small
    integers in the 800..860 range (class/category ordinals [hypothesis]).
    """
    if entry.table_tag != 0x0644 or entry.table_count is None:
        return
    if entry.table_count * 40 > entry.length:      # implausible count
        return
    o = entry.offset + 0x85
    cnt = entry.table_count if not limit else min(limit, entry.table_count)
    for i in range(cnt):
        if o + 40 > len(payload) or o + 40 > entry.offset + entry.length:
            break
        rec = struct.unpack_from("<QIIiQqI", payload, o)
        if rec[0] != rec[4]:                          # self-id repeat is the
            break                                       # record invariant
        yield rec
        o += 40


# ----------------------------------------------------------------------------
# demo / __main__
# ----------------------------------------------------------------------------

SAMPLES = ["racbasicsampleproject", "rstbasicsampleproject", "rmebasicsampleproject",
           "rstadvancedsampleproject", "racadvancedsampleproject", "dach-sample-project"]

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))


def _extracted(sample: str, stream: str) -> Optional[str]:
    p = os.path.join(_ROOT, "extracted", sample, f"Global__{stream}.bin")
    return p if os.path.exists(p) else None


def _report_stream(gs: GlobalStream) -> None:
    print(f"    prefix   : {gs.prefix.hex()} (lo={gs.prefix_lo}, hi={gs.prefix_hi})"
          f"  gzip@{gs.gzip_offset} flg={gs.gzip_flg}")
    print(f"    raw={gs.raw_len:,}  payload={len(gs.payload):,}  complete={gs.complete}"
          f"  tail_sig={gs.tail_sig_ok}")
    for s in gs.segments:
        print(f"      seg{s.index}: comp[{s.comp_start:,}..{s.comp_end:,}) -> {s.out_len:,} B"
              f"  {s.status}{'' if s.trusted else ' (untrusted window)'}"
              f"{'  ' + s.error if s.error else ''}")
    if gs.gap:
        a, b = gs.gap
        print(f"      GAP: undecodable compressed bytes [{a:,}..{b:,}) = {b - a:,} B")
    if gs.trailer_crc32 is not None:
        print(f"    trailer  : crc32={gs.trailer_crc32:08x} ({'OK' if gs.crc_ok else 'stale'})"
              f"  isize={gs.trailer_isize:,} ({'OK' if gs.isize_ok else f'stale, actual {len(gs.payload):,}'})"
              f"  pad0={gs.pad_zeros}  footer={len(gs.footer)} B")


def demo(samples: Iterable[str] = SAMPLES) -> None:
    print("=" * 78)
    print("Global/History  (ADocument::m_pHistory)")
    print("=" * 78)
    for s in samples:
        path = _extracted(s, "History")
        if not path:
            continue
        gs = inflate_global(open(path, "rb").read(), f"{s}:History")
        print(f"\n[{s}]")
        _report_stream(gs)
        h = parse_history(gs.payload)
        v1 = [e for e in h.entries if e.is_v1]
        print(f"    class_tag=0x{h.class_tag:04x} ver={h.version} entries={len(h.entries)}"
              f" (hdr says {h.hdr_count}) format_versions={len(h.format_versions)}"
              f" -> current {h.current_format}")
        print(f"    header GUID slots: {h.header_guids[0]}  [g,g,g,0,g]="
              f"{h.header_guids[0] == h.header_guids[1] == h.header_guids[2] == h.header_guids[4] and h.header_guids[3].int == 0}")
        print(f"    format versions: {h.format_versions[:6]} ... {h.format_versions[-4:]}")
        print(f"    entry[0] (== unique document GUID): {h.document_guid} tag=0x{h.entries[0].tag:02x}")
        if v1:
            old = min(v1, key=lambda e: e.when)
            print(f"    v1 episodes: {len(v1)}; oldest #{old.index}/{len(h.entries) - 1}"
                  f" {old.guid} @ {old.when} mac {old.mac}")
        else:
            print(f"    v1 episodes: 0 (all random v4 GUIDs)")
        print(f"    trailing bytes: {h.trailing.hex()}  tag byte set: "
              f"{sorted({e.tag for e in h.entries})}")

    print()
    print("=" * 78)
    print("Global/ContentDocuments  (ADocument::m_oContentTable)")
    print("=" * 78)
    for s in samples:
        path = _extracted(s, "ContentDocuments")
        if not path:
            continue
        gs = inflate_global(open(path, "rb").read(), f"{s}:ContentDocuments")
        print(f"\n[{s}]")
        _report_stream(gs)
        cm = scan_content_documents(gs.payload)
        kinds = cm.kinds()
        print(f"    entries={len(cm.entries)}  coverage={cm.coverage:,}/{cm.payload_len:,}"
              f"  keys ascending={cm.monotonic}  kinds={dict(kinds)}")
        for e in cm.entries[:3]:
            print(f"      #{e.index:3d} @{e.offset:#9x} len={e.length:9,} key={e.key}"
                  f" u32={e.u32_1c} kind={e.kind} table=({'-' if e.table_tag is None else hex(e.table_tag)},"
                  f"{e.table_count}) fv={e.format_version}")
        big = sorted(cm.entries, key=lambda e: -e.length)[:3]
        print("      largest:")
        for e in big:
            print(f"      #{e.index:3d} @{e.offset:#9x} len={e.length:9,} key={e.key} kind={e.kind}")
        # first entry's element records, first three
        e0 = cm.entries[0] if cm.entries else None
        if e0 and e0.kind == "skeleton":
            recs = list(element_records(gs.payload, e0, 3))
            for r in recs:
                print(f"      rec: elem={r[0]:#x} a={r[1]} b={r[2]} c={r[3]}"
                      f" self={r[4]:#x} prev={r[5]} tail={r[6]}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        demo()
    else:
        for a in args:
            if os.path.isdir(a):
                demo([os.path.basename(a.rstrip("/"))])
            else:
                gs = inflate_global(open(a, "rb").read(), a)
                _report_stream(gs)
                if "History" in a:
                    h = parse_history(gs.payload)
                    print(f"    entries={len(h.entries)} doc_guid={h.document_guid}"
                          f" format={h.current_format}")
                elif "Content" in a:
                    cm = scan_content_documents(gs.payload)
                    print(f"    entries={len(cm.entries)} monotonic={cm.monotonic}")

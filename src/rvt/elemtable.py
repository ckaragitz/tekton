"""Global/ElemTable decoder — Revit's per-document element table.

`Global/ElemTable` is the externalized `ADocument.m_elemTable` member: a
serialized `ElemTable` object (schema class index 0x05c9) holding a sorted
array of fixed-size 40-byte `ElemRec` records — one per live ElementId — plus
an (empty in all samples) array of `GraveyardRec`s, plus a small footer.

Contrary to the original hypothesis, it is NOT an id -> (partition, byte
offset) location index. Per the (de-framed) `Formats/Latest` schema:

    ElemTable   { ElemRec[]      m_elemArr;
                  GraveyardRec[] m_graveyardRecs; }
    ElemRec     { ElementHistory m_history;
                  ElementId      m_id;              # u64, the sort key
                  ElementId      m_OwningElementId; # u64, -1 = none
                  PartitionId    m_partitionId; }   # u32
    ElementHistory { ElementId originalElementId;    # u64
                     EpisodeId creationDate;          # u32 episode index
                     EpisodeId lastModificationDate;  # u32 episode index
                     EpisodeId lastUserModificationDate; } # u32, -1 = never

Episode indices refer to `Global/History` (episode list; its count equals
max(lastModificationDate)+1 in every sample).

STREAM FRAMING (critical, corpus-wide): the raw OLE stream bytes are stored in
pages of 65,249 bytes = 64,896 (0xFD80) payload bytes + a 353-byte per-page
block. Those 353-byte blocks must be stripped before inflating; after that
the gzip trailer (CRC32/ISIZE) validates in every sample. See `deframe()`.
"""
from __future__ import annotations

import os
import struct
import sys
import zlib
from dataclasses import dataclass, field
from typing import Iterator, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXTRACTED = os.path.join(ROOT, 'extracted')

PROJECTS = [
    'racbasicsampleproject',
    'racadvancedsampleproject',
    'rmebasicsampleproject',
    'rstadvancedsampleproject',
    'rstbasicsampleproject',
    'dach-sample-project',
]

# --- stream page framing --------------------------------------------------

PAGE_DATA = 64896      # 0xFD80 payload bytes per page
PAGE_TRAILER = 353     # per-page block that is not payload
PAGE_STRIDE = PAGE_DATA + PAGE_TRAILER  # 65,249

GLOBAL_PREFIX_LEN = 8  # every Global/* stream starts with an 8-byte header
GZIP_HDR_LEN = 10

# schema class indices (Revit 2026 build 20250227_1515) seen in this stream
CLASS_ELEMTABLE = 0x05C9   # ElemTable (root object of the stream)
CLASS_ELEMREC = 0x05C5     # ElemRec  (element type of m_elemArr)
CLASS_GRAVEYARD = 0x05CA   # GraveyardRec (element type of m_graveyardRecs)
CLASS_TAIL = 0x096A        # class tag inside the footer [hypothesis]

INVALID_ID = 0xFFFFFFFFFFFFFFFF  # ElementId::InvalidElementId
NO_EPISODE = 0xFFFFFFFF          # "never" for an EpisodeId field

REC_SIZE = 40
REC_FMT = '<QIIIQQI'   # orig_id, ce, me, ue, id, owner, partition


def deframe(raw: bytes, page_data: int = PAGE_DATA, page_trailer: int = PAGE_TRAILER) -> bytes:
    """Strip the 353-byte per-page blocks from a raw OLE stream.

    Layout (from stream offset 0): repeat { 64,896 payload | 353 block }.
    Streams shorter than 64,896 bytes are returned unchanged.
    """
    out = bytearray()
    pos = 0
    n = len(raw)
    while pos < n:
        out += raw[pos:pos + page_data]
        pos += page_data + page_trailer
    return bytes(out)


@dataclass
class InflatedStream:
    prefix: bytes          # 8-byte Global/* prefix
    payload: bytes         # inflated bytes
    crc32: int             # from the gzip trailer
    isize: int             # from the gzip trailer
    deflate_end: int       # offset (in de-framed stream) where deflate data ends
    slack: bytes           # bytes after the gzip trailer (allocation slack)

    @property
    def crc_ok(self) -> bool:
        return self.crc32 == (zlib.crc32(self.payload) & 0xFFFFFFFF)

    @property
    def isize_ok(self) -> bool:
        return self.isize == (len(self.payload) & 0xFFFFFFFF)


def inflate_global_stream(raw: bytes, prefix_len: int = GLOBAL_PREFIX_LEN) -> InflatedStream:
    """De-frame, then gunzip an 8-byte-prefixed Global/* stream."""
    lin = deframe(raw)
    if lin[prefix_len:prefix_len + 3] != b'\x1f\x8b\x08':
        raise ValueError('no gzip header after prefix; hex=%s' % lin[:24].hex())
    d = zlib.decompressobj(-zlib.MAX_WBITS)
    payload = d.decompress(lin[prefix_len + GZIP_HDR_LEN:])
    payload += d.flush()
    end = len(lin) - len(d.unused_data)
    crc, isz = struct.unpack('<II', lin[end:end + 8])
    return InflatedStream(prefix=lin[:prefix_len], payload=payload, crc32=crc,
                          isize=isz, deflate_end=end, slack=lin[end + 8:])


# --- records ---------------------------------------------------------------

@dataclass
class ElemRec:
    """One 40-byte record = schema class ElemRec (0x05c5).

    Field order in bytes matches the schema field order:
    m_history{originalElementId, creation, lastMod, lastUserMod},
    m_id, m_OwningElementId, m_partitionId.
    """
    index: int
    original_id: int      # +0  u64  m_history.m_originalElementId
    creation_ep: int      # +8  u32  m_history.m_creationDate (EpisodeId)
    modified_ep: int      # +12 u32  m_history.m_lastModificationDate (EpisodeId)
    user_modified_ep: int # +16 u32  m_history.m_lastUserModificationDate (EpisodeId, 0xFFFFFFFF=never)
    id: int               # +20 u64  m_id  (ElementId, the sort key)
    owner_id: int         # +28 u64  m_OwningElementId (ElementId, -1 = none)
    partition_id: int     # +36 u32  m_partitionId.m_id

    @property
    def renumbered(self) -> bool:
        return self.original_id != self.id

    def line(self) -> str:
        own = '-' if self.owner_id == INVALID_ID else f'{self.owner_id}'
        ue = '-' if self.user_modified_ep == NO_EPISODE else str(self.user_modified_ep)
        orig = '=' if self.original_id == self.id else f'{self.original_id}'
        return (f'{self.index:6d}  id={self.id:<9d} orig={orig:<9s} '
                f'create_ep={self.creation_ep:<5d} mod_ep={self.modified_ep:<5d} '
                f'usermod_ep={ue:<5s} owner={own:<9s} part={self.partition_id}')


@dataclass
class ElemTableFooter:
    graveyard_count: int   # u32, expected 0
    marker: int            # u32, observed 0xFFFFFFFF
    tail_class: int        # u16, observed 0x096A (schema class tag) [hypothesis]
    tail_pad: int          # u16, 0
    last_id: int           # u64, highest issued ElementId watermark [hypothesis]
    tail_zero: int         # u32, 0
    raw: bytes = b''


@dataclass
class ElemTable:
    project: str
    class_tag: int                 # u16 at payload offset 0, expected 0x05C9
    count: int                     # u32 at payload offset 2
    records: List[ElemRec] = field(default_factory=list)
    footer: Optional[ElemTableFooter] = None
    stream: Optional[InflatedStream] = None
    payload_len: int = 0

    # --- convenience ---------------------------------------------------
    def ids(self) -> List[int]:
        return [r.id for r in self.records]

    def max_episode(self) -> int:
        return max((r.modified_ep for r in self.records), default=-1)

    def stats(self) -> dict:
        recs = self.records
        n = len(recs)
        if n == 0:
            return {'count': 0}
        ids = self.ids()
        return {
            'count': n,
            'id_min': min(ids), 'id_max': max(ids),
            'sorted_by_id': all(ids[i] < ids[i + 1] for i in range(n - 1)),
            'renumbered': sum(1 for r in recs if r.renumbered),
            'with_owner': sum(1 for r in recs if r.owner_id != INVALID_ID),
            'never_user_modified': sum(1 for r in recs if r.user_modified_ep == NO_EPISODE),
            'max_creation_ep': max(r.creation_ep for r in recs),
            'max_modified_ep': self.max_episode(),
            'partition_ids': sorted({r.partition_id for r in recs}),
            'ep_invariant_ce_le_me': all(r.creation_ep <= r.modified_ep for r in recs),
            'ep_invariant_ue_between': all(
                r.creation_ep <= r.user_modified_ep <= r.modified_ep
                for r in recs if r.user_modified_ep != NO_EPISODE),
            'orig_le_id': all(r.original_id <= r.id for r in recs),
        }


def parse_elemtable(payload: bytes, project: str = '?') -> ElemTable:
    """Parse the inflated ElemTable payload."""
    if len(payload) < 6:
        raise ValueError('payload too short')
    class_tag, count = struct.unpack_from('<HI', payload, 0)
    tbl = ElemTable(project=project, class_tag=class_tag, count=count, payload_len=len(payload))
    off = 6
    need = 6 + count * REC_SIZE
    if len(payload) < need:
        raise ValueError(f'payload {len(payload)} < needed {need} for {count} records')
    unpack = struct.Struct(REC_FMT).unpack_from
    recs = tbl.records
    for i in range(count):
        o, ce, me, ue, eid, own, pid = unpack(payload, off)
        recs.append(ElemRec(i, o, ce, me, ue, eid, own, pid))
        off += REC_SIZE
    tail = payload[off:]
    if len(tail) >= 24:
        gcnt, marker, tcls, tpad, last_id, tz = struct.unpack_from('<IIHHQI', tail, 0)
        tbl.footer = ElemTableFooter(gcnt, marker, tcls, tpad, last_id, tz, tail)
    else:
        tbl.footer = ElemTableFooter(0, 0, 0, 0, 0, 0, tail)
    return tbl


def load_elemtable(project: str = 'racbasicsampleproject') -> ElemTable:
    """Read extracted/<project>/Global__ElemTable.bin and decode it."""
    path = os.path.join(EXTRACTED, project, 'Global__ElemTable.bin')
    with open(path, 'rb') as fh:
        raw = fh.read()
    st = inflate_global_stream(raw)
    tbl = parse_elemtable(st.payload, project)
    tbl.stream = st
    return tbl


# --- cross-checks -----------------------------------------------------------

def partition_header_element_count(project: str) -> Optional[int]:
    """u32 at bytes 14..17 of the Partitions/<N> stream header (matches ElemTable count)."""
    import glob
    cands = sorted(glob.glob(os.path.join(EXTRACTED, project, 'Partitions__*.bin')))
    best = None
    for p in cands:
        with open(p, 'rb') as fh:
            h = fh.read(20)
        if len(h) >= 18:
            v = struct.unpack_from('<I', h, 14)[0]
            best = v if (best is None or v > best) else best
    return best


def history_episode_count(project: str) -> Optional[int]:
    """u32 at offset 14 of the inflated Global/History payload (= episode count)."""
    path = os.path.join(EXTRACTED, project, 'Global__History.bin')
    if not os.path.exists(path):
        return None
    with open(path, 'rb') as fh:
        raw = fh.read()
    try:
        st = inflate_global_stream(raw)
    except Exception:
        return None
    if len(st.payload) < 18:
        return None
    return struct.unpack_from('<I', st.payload, 14)[0]


# --- CLI ---------------------------------------------------------------------

def _report(project: str, nrecs: int = 20) -> None:
    tbl = load_elemtable(project)
    st = tbl.stream
    print('=' * 78)
    print(f'{project}')
    print('-' * 78)
    print(f'stream prefix (8B): {st.prefix.hex()}   inflated payload: {len(st.payload):,} B')
    print(f'gzip trailer: crc32=0x{st.crc32:08x} ({"OK" if st.crc_ok else "MISMATCH"})'
          f'  isize={st.isize:,} ({"OK" if st.isize_ok else "MISMATCH"})'
          f'  slack-after-trailer={len(st.slack)} B')
    print(f'header: class_tag=0x{tbl.class_tag:04x}'
          f' ({"ElemTable" if tbl.class_tag == CLASS_ELEMTABLE else "??"})'
          f'  count={tbl.count:,}  -> 6 + 40*count + 24 = {6 + 40*tbl.count + 24:,} B'
          f' (payload {tbl.payload_len:,} B)')
    f = tbl.footer
    print(f'footer(24B): graveyard_count={f.graveyard_count} marker=0x{f.marker:08x} '
          f'class=0x{f.tail_class:04x} pad={f.tail_pad} last_id={f.last_id} zero={f.tail_zero}')
    print(f'  raw={f.raw.hex(" ")}')
    print(f'first {nrecs} records:')
    for r in tbl.records[:nrecs]:
        print(r.line())
    if tbl.records:
        print('last record:')
        print(tbl.records[-1].line())
    s = tbl.stats()
    print('stats:')
    for k, v in s.items():
        print(f'  {k:24s} {v}')
    phc = partition_header_element_count(project)
    hec = history_episode_count(project)
    print(f'cross-checks: Partitions/<N> header count = {phc} '
          f'({"MATCH" if phc == tbl.count else "differs"});  '
          f'Global/History episode count = {hec} '
          f'(max_modified_ep+1 = {s["max_modified_ep"]+1}, '
          f'{"MATCH" if hec == s["max_modified_ep"]+1 else "differs"})')


def main(argv: List[str]) -> int:
    projects = argv[1:] if len(argv) > 1 else PROJECTS
    for p in projects:
        try:
            _report(p)
        except Exception as e:  # keep going across files
            print(f'{p}: ERROR {type(e).__name__}: {e}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))

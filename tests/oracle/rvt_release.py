"""rvt_release.py -- release-independent access to a .rvt's own schema + framing tags.

Every Revit release ships its own ``Formats/Latest`` (the archive class map).
The wave-1 grammar in ``rvt.schema_a`` turns out to be release-independent
(verified here on Revit 2023 / 2024 / 2026), and the type ids it assigns
(definition order + 0x0c) are EXACTLY the class words that appear on disk:
the Partitions framing tags (SegmentMarker/SegmentCheckback/SignatureMarker/
ContentMarker/ContentKey), the record class words (ElementHeader, GElement,
SerializedDummy...) and the Global/* lead ordinals (ADocument, ElemTable,
DocumentHistory...).  So instead of hard-coding 2026 constants (0x0f28 etc.)
we resolve every framing tag BY CLASS NAME from the file's own schema.

Public API
    class_map(doc)            -> ClassMap  (id<->name, class list, parse stats)
    framing_tags(cmap)        -> FramingTags (block/trailer/footer/container...)
    walk_partition(clean, tags) -> ParsedPartition (blocks per seq, payloads)

Everything is cached under tests/oracle/cache/ keyed by the schema sha256 so
re-runs are cheap.
"""
from __future__ import annotations

import hashlib
import json
import os
import struct
import zlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# --------------------------------------------------------------------------
# schema / class map
# --------------------------------------------------------------------------


@dataclass
class ClassMap:
    sha256: str
    inflated_size: int
    release: str                      # from BasicFileInfo ("2023"/"2024"/"2026") or "?"
    id_to_name: Dict[int, str]
    name_to_id: Dict[str, int]
    n_classes: int
    n_fields: int
    parsed_bytes: int                 # bytes consumed before desync (or full length)
    desync: Optional[str]

    def name(self, cid: int) -> str:
        return self.id_to_name.get(cid, f"cls_0x{cid:04x}")

    def to_json(self) -> dict:
        return {
            "sha256": self.sha256,
            "inflated_size": self.inflated_size,
            "release": self.release,
            "n_classes": self.n_classes,
            "n_fields": self.n_fields,
            "parsed_bytes": self.parsed_bytes,
            "desync": self.desync,
            "id_to_name": {str(k): v for k, v in self.id_to_name.items()},
        }

    @staticmethod
    def from_json(j: dict) -> "ClassMap":
        i2n = {int(k): v for k, v in j["id_to_name"].items()}
        n2i: Dict[str, int] = {}
        for k, v in i2n.items():
            n2i.setdefault(v, k)
        return ClassMap(j["sha256"], j["inflated_size"], j.get("release", "?"),
                        i2n, n2i, j["n_classes"], j["n_fields"],
                        j["parsed_bytes"], j.get("desync"))


def class_map_from_bytes(schema: bytes, release: str = "?") -> ClassMap:
    """Parse an inflated Formats/Latest with the wave-1 grammar (rvt.schema_a)."""
    sha = hashlib.sha256(schema).hexdigest()
    cache = os.path.join(CACHE_DIR, f"schema_{sha[:16]}.json")
    if os.path.exists(cache):
        with open(cache) as f:
            return ClassMap.from_json(json.load(f))
    from rvt import schema_a as S  # imported lazily; heavy-ish

    parser, err = S.parse(schema)
    id_to_name: Dict[int, str] = {}
    name_to_id: Dict[str, int] = {}
    for c in parser.classes:
        id_to_name[c["type_id"]] = c["class_name"]
        name_to_id.setdefault(c["class_name"], c["type_id"])
    nfields = sum(len(c["fields"]) for c in parser.classes)
    cm = ClassMap(sha, len(schema), release, id_to_name, name_to_id,
                  len(parser.classes), nfields,
                  err.offset if err else len(schema),
                  str(err) if err else None)
    with open(cache, "w") as f:
        json.dump(cm.to_json(), f, indent=1)
    return cm


def class_map(doc, release: str = "?") -> ClassMap:
    """ClassMap for an open ``rvt.container.RvtDocument`` (its own schema)."""
    schema = doc.inflate("Formats/Latest", 0)
    return class_map_from_bytes(schema, release)


# --------------------------------------------------------------------------
# framing tags resolved by class name
# --------------------------------------------------------------------------

# 2026 fallbacks (used only if a name is missing from the parsed schema)
_FALLBACK = {
    "SegmentMarker": 0x0F28,      # block header tag / unit terminator
    "SegmentCheckback": 0x0F21,   # block trailer tag
    "SignatureMarker": 0x0F3F,    # unit footer blob tag
    "ContentMarker": 0x03A3,      # stream header class / separator / end record
    "ContentKey": 0x03A2,         # separator inner class
    "ElementHeader": 0x05E5,
    "GElement": 0x089E,
    "SerializedDummy": 0x0F2C,
}


@dataclass
class FramingTags:
    block: int          # SegmentMarker
    trailer: int        # SegmentCheckback
    footer: int         # SignatureMarker
    container: int      # ContentMarker
    inner: int          # ContentKey
    source: Dict[str, str] = field(default_factory=dict)  # name -> schema|fallback

    def dump(self) -> str:
        return (f"block(SegmentMarker)=0x{self.block:x} "
                f"trailer(SegmentCheckback)=0x{self.trailer:x} "
                f"footer(SignatureMarker)=0x{self.footer:x} "
                f"container(ContentMarker)=0x{self.container:x} "
                f"inner(ContentKey)=0x{self.inner:x}")


def framing_tags(cmap: ClassMap) -> FramingTags:
    src: Dict[str, str] = {}

    def get(name: str) -> int:
        if name in cmap.name_to_id:
            src[name] = "schema"
            return cmap.name_to_id[name]
        src[name] = "fallback-2026"
        return _FALLBACK[name]

    return FramingTags(get("SegmentMarker"), get("SegmentCheckback"),
                       get("SignatureMarker"), get("ContentMarker"),
                       get("ContentKey"), src)


# --------------------------------------------------------------------------
# partition stream walker (release-parametric copy of rvt.partitions logic)
# --------------------------------------------------------------------------

PAGE_SIZE = 64896
PAGE_TRAILER = 353
PAGE_STRIDE = PAGE_SIZE + PAGE_TRAILER

_ISIZE_ADJ = {4: 0, 5: 4, 6: -4, 7: 0}


def depage(raw: bytes) -> bytes:
    if len(raw) <= PAGE_SIZE:
        return raw
    out = bytearray()
    pos = 0
    n = len(raw)
    while pos < n:
        out += raw[pos:pos + PAGE_SIZE]
        pos += PAGE_STRIDE
    return bytes(out)


@dataclass
class WBlock:
    index: int
    unit: int
    hdr_offset: int
    flags: int
    n_records: int      # A
    size_hint: int      # B
    body_bytes: int     # C
    seq: int
    member_offset: int
    member_len: int
    trailer_ok: bool
    crc_ok: bool
    isize: int
    intended_len: int
    data: bytes = b""

    def brief(self) -> str:
        return (f"blk{self.index:5d} u{self.unit:3d} flags={self.flags} "
                f"A={self.n_records:5d} B={self.size_hint:7d} C={self.body_bytes:8d} "
                f"seq={self.seq} infl={len(self.data)} crc={self.crc_ok} "
                f"isize_ok={len(self.data) == self.intended_len}")


@dataclass
class WHeader:
    version: int
    zero0: int
    class_ordinal: int
    zero1: int
    elem_table_count: int


@dataclass
class ParsedPartition:
    header: WHeader
    blocks: List[WBlock]
    n_units: int
    end_offset: int
    errors: List[str]

    def segment(self, seq: int) -> bytes:
        return b"".join(b.data for b in self.blocks if b.seq == seq)

    def seqs(self) -> List[int]:
        return sorted({b.seq for b in self.blocks})


def _inflate_member(clean: bytes, start: int, end: int):
    body = clean[start + 10:end - 8]
    stored_crc, stored_isize = struct.unpack_from("<II", clean, end - 8)
    d = zlib.decompressobj(-zlib.MAX_WBITS)
    try:
        out = d.decompress(body) + d.flush()
    except zlib.error:
        return b"", False, stored_isize
    crc_ok = (zlib.crc32(out) & 0xFFFFFFFF) == stored_crc and \
        (len(out) & 0xFFFFFFFF) == stored_isize
    return out, crc_ok, stored_isize


def parse_partition_header(clean: bytes) -> WHeader:
    version, zero0, cls, zero1, cnt = struct.unpack_from("<IIHiI", clean, 0)
    return WHeader(version, zero0, cls, zero1, cnt)


def walk_partition(clean: bytes, tags: FramingTags, keep_data: bool = True) -> ParsedPartition:
    """Walk header / units / blocks / footers of a de-paged Partitions/<N>."""
    hdr = parse_partition_header(clean)
    blocks: List[WBlock] = []
    errors: List[str] = []
    n = len(clean)
    pos = 18
    unit = 0
    terminator = struct.pack("<HIIII", tags.block, 0, 0, 0, 0)
    end_offset = pos
    while pos + 2 <= n:
        (tag,) = struct.unpack_from("<H", clean, pos)
        if tag == tags.block and clean[pos:pos + 18] == terminator:
            # unit footer: SignatureMarker blob + UTF-16 'Data generated...'
            p = pos + 18
            if p + 6 <= n and struct.unpack_from("<H", clean, p)[0] == tags.footer:
                (blen,) = struct.unpack_from("<I", clean, p + 2)
                p += 6 + blen
                if p + 4 <= n:
                    (nchars,) = struct.unpack_from("<I", clean, p)
                    p += 4 + 2 * nchars
            else:
                errors.append(f"footer tag missing at {p}")
                end_offset = pos
                break
            pos = p
            # unit separator (ContentMarker,-1,ContentKey,counter,guid) or end
            if pos + 8 <= n and clean[pos:pos + 6] == struct.pack("<Hi", tags.container, -1) \
                    and struct.unpack_from("<H", clean, pos + 6)[0] == tags.inner:
                pos += 28
                unit += 1
                if pos + 2 <= n and struct.unpack_from("<H", clean, pos)[0] != tags.block:
                    # tolerate junk before next block header
                    nxt = _find_block_header(clean, pos, tags)
                    if nxt < 0:
                        end_offset = pos
                        break
                    errors.append(f"skipped {nxt - pos} bytes after separator at {pos}")
                    pos = nxt
                continue
            end_offset = pos
            break
        if tag != tags.block:
            errors.append(f"unexpected tag 0x{tag:04x} at {pos}")
            end_offset = pos
            break
        _t, flags, A, B, C, seq, z = struct.unpack_from("<HIIIIII", clean, pos)
        if flags not in (4, 5, 6, 7):
            errors.append(f"bad flags {flags} at {pos}")
            end_offset = pos
            break
        member = pos + 26
        trailer_pat = struct.pack("<HI", tags.trailer, B)
        guess = member + B - 8
        if guess + 6 <= n and clean[guess:guess + 6] == trailer_pat:
            end = guess
            trailer_ok = True
        else:
            end = clean.find(trailer_pat, member)
            trailer_ok = False
            if end < 0:
                errors.append(f"no trailer for block at {pos} (B={B})")
                end_offset = pos
                break
        data, crc_ok, isize = _inflate_member(clean, member, end)
        hdr_len = 16 if seq == 101 else 20
        intended = hdr_len * A + C + _ISIZE_ADJ.get(flags, 0)
        blocks.append(WBlock(len(blocks), unit, pos, flags, A, B, C, seq,
                             member, end - member, trailer_ok, crc_ok, isize,
                             intended, data if keep_data else b""))
        pos = end + 6
        end_offset = pos
    return ParsedPartition(hdr, blocks, unit + 1, end_offset, errors)


def _find_block_header(clean: bytes, start: int, tags: FramingTags, limit: int = 65536) -> int:
    pat = struct.pack("<H", tags.block)
    end = min(len(clean), start + limit)
    q = start
    while True:
        q = clean.find(pat, q, end)
        if q < 0:
            return -1
        if q + 29 <= len(clean):
            flags = struct.unpack_from("<I", clean, q + 2)[0]
            if flags in (4, 5, 6, 7) and clean[q + 26:q + 29] == b"\x1f\x8b\x08":
                return q
        q += 1


# --------------------------------------------------------------------------
# record scanning (identical framing across releases; verified by walk %)
# --------------------------------------------------------------------------

@dataclass
class Rec:
    offset: int
    elem_id: int
    stamp: Optional[int]
    body_size: int
    cls: int
    hdr_len: int


def scan_records(seg: bytes, seq: int):
    """Yield Rec over a concatenated seq segment. Stops when implausible."""
    hlen = 16 if seq == 101 else 20
    p = 0
    n = len(seg)
    while p + hlen <= n:
        if seq == 101:
            eid, size, cls = struct.unpack_from("<qII", seg, p)
            stamp = None
        else:
            eid, stamp, size, cls = struct.unpack_from("<qIII", seg, p)
        if not (-1 <= eid < (1 << 40)) or size > (1 << 30):
            return
        yield Rec(p, eid, stamp, size, cls & 0xFFFF, hlen)
        p += hlen + size


if __name__ == "__main__":
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "src"))
    from rvt.container import open_rvt

    paths = sys.argv[1:] or [
        "/Users/ck/dev/things/rev-revit/vendor/magnetar-revit-test-datasets/Revit/Revit_IFC5_Einhoven.rvt",
        "/Users/ck/dev/things/rev-revit/vendor/magnetar-revit-test-datasets/Revit/2024_Core_Interior.rvt",
        "/Users/ck/dev/things/rev-revit/samples/racbasicsampleproject.rvt",
    ]
    for p in paths:
        with open_rvt(p) as doc:
            cm = class_map(doc)
            tg = framing_tags(cm)
            print(f"{os.path.basename(p)}: schema {cm.inflated_size:,} B "
                  f"sha {cm.sha256[:12]} classes={cm.n_classes} fields={cm.n_fields} "
                  f"parsed={cm.parsed_bytes:,}B desync={'yes' if cm.desync else 'no'}")
            print(f"  tags: {tg.dump()}")
            for s in doc.partition_streams():
                clean = depage(doc.raw(s))
                pp = walk_partition(clean, tg)
                crc = sum(1 for b in pp.blocks if b.crc_ok)
                print(f"  {s}: hdr(v={pp.header.version} cls=0x{pp.header.class_ordinal:x} "
                      f"elem_tbl={pp.header.elem_table_count}) blocks={len(pp.blocks)} "
                      f"crc_ok={crc}/{len(pp.blocks)} units={pp.n_units} seqs={pp.seqs()} "
                      f"errors={len(pp.errors)}")

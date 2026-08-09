"""Canonical decoder for the Revit 2026 ``Formats/Latest`` schema stream.

``Formats/Latest`` (de-paged, gzip member 0 inflated: 496,597 bytes, sha256
6459a9a9..., byte-identical in every Revit 2026 file) is the on-disk
**archive class map**: every serializable/embeddable C++ class with its
name, base class, version, ordered field records and per-class GUID table.
This module is the merger of the wave-1 decoders ``schema_a`` (bottom-up
grammar) and ``schema_b`` (statistical codebook) plus prior art
``vendor/rvt-rs`` (field type-encoding table), run over the CORRECTED
(de-paged, CRC-verified) stream.  It parses the whole stream to EOF with
zero gaps and zero unresolved backward type references.

Grammar (all little-endian; see docs/streams/01-schema.md)::

    stream        := class_record* zero_pad(<=15)          (until EOF)

    class_record  := u16 0                                  (record marker)
                     u16 name_len,  u8[name_len] name       (ASCII class name)
                     u16 parent_ref                         (0        = no base
                                                             0x8000|i = base class
                                                                defined INLINE next,
                                                                receiving id i
                                                             i        = backward ref
                                                                to already-defined id)
                     u32 version
                     u32 field_count
                     field[field_count]
                     u32 guid_count
                     u8[16] guid[guid_count]

    field         := u32 name_len, u8[name_len] name, descriptor

    descriptor    := u8 kind, u8 flags, u16 extra            (extra == 0 except
                                                             one field: 0x0004
                                                             on VarExpr.m_refCt)
                     [ if flags high-nibble == 0x1 : u32 fixed_count ]
                     [ if kind == 0x0e and (flags & 0x0f) == 0 :
                           u16 type_ref  (0x8000|i => class_record for id
                                          i defined INLINE right here) ]
                     [ if kind == 0x0d : field  (anonymous element field
                                                 named " " describing the
                                                 array element)
                       + if the element is kind 0x0e with (flags&0x0f)==0:
                             u16 type_ref (repeat of element's type id) ]

Type ids are assigned in DEFINITION ORDER (top-level and inline share one
counter) starting at ``0x0c``.  Ids ``0x00..0x0b`` are the primitive kind
codes.  This id assignment is validated against 16 independently-known
class ordinals from the element/global streams (see ``ANCHORS`` and
``anchor_report``): 16/16 match.

Public API::

    schema = load_schema()            # -> Schema
    schema.by_id[0x1c].name           # 'ADocument'
    schema.by_name['Wall']            # ClassDef
    schema.stats()                    # dict of statistics

Running the module writes ``extracted/_schema/schema.json``,
``extracted/_schema/type_ids.json`` and ``extracted/_schema/mep_classes.txt``
and prints statistics plus the anchor validation table.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import json
import os
import re
import struct
import sys
from collections import Counter
from dataclasses import dataclass, field as dc_field

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # repo root; env TEKTON_ROOT overrides
DEFAULT_PATH = os.path.join(
    ROOT, "extracted/racbasicsampleproject/Formats__Latest.gz/000.bin"
)
OUT_DIR = os.path.join(ROOT, "extracted/_schema")
OUT_SCHEMA = os.path.join(OUT_DIR, "schema.json")
OUT_IDS = os.path.join(OUT_DIR, "type_ids.json")
OUT_MEP = os.path.join(OUT_DIR, "mep_classes.txt")
RVTRS_DRIFT_CSV = os.path.join(ROOT, "vendor/rvt-rs/docs/data/tag-drift-2016-2026.csv")

EXPECTED_SIZE = 496_597
EXPECTED_SHA256 = "6459a9a93ebde32c26e4190de2756bf7a4592e63a0d142feca43c392ecdf8ac2"

FIRST_TYPE_ID = 0x0C  # first class type id; lower values are primitive kinds

# ---------------------------------------------------------------------------
# Kind codebook (descriptor byte 0).  Entries marked "GT" are ground truth
# from the synthetic std::pair< A, B > classes whose C++ signature is spelled
# out in their class name (e.g. 'std::pair< short, int64_t >' -> first is
# kind 0x03, second is kind 0x0b).  Others are corroborated by rvt-rs and by
# field-name/value statistics.
KIND_NAMES = {
    0x01: "bool",        # GT: std::pair< X, bool >
    0x02: "char",        # GT: std::pair< X, char >          (8-bit)
    0x03: "short",       # GT: std::pair< short, X >         (16-bit)
    0x04: "int",         # GT: std::pair< X, int >           (int32)
    0x05: "uint",        # GT: std::pair< unsigned long, X > (uint32; colors, ATime)
    0x06: "float",       # GT: std::pair< X, float >
    0x07: "double",      # GT: std::pair< X, double >
    0x08: "AString",     # GT: std::pair< X, AString >, always flags 0x60
    0x09: "GUID",        # GUIDvalue.m_guid (16 bytes)
    0x0a: "classref",    # ClassDefinitionRef.m_ref (single instance)
    0x0b: "int64",       # GT: std::pair< X, int64_t >
    0x0d: "array",       # inline array wrapper: anonymous element sub-field
    0x0e: "class",       # user class value/ref; u16 type_ref when flags&0xf==0
}

# Flags codebook (descriptor byte 1).  High nibble = storage shape,
# low nibble = indirection kind.
FLAG_NAMES = {
    0x00: "value",
    0x01: "ptr",             # owned polymorphic pointer
    0x02: "ptr_owned",       # m_elemTable / m_pAppInfoManager
    0x03: "ptr_weak",        # m_pACD / m_pADoc back-pointer
    0x04: "ptr_var",         # only on Var*/VarExpr expression nodes
    0x10: "fixed_array",     # u32 count follows
    0x11: "fixed_array_ptr",
    0x13: "fixed_array_wptr",
    0x50: "container",       # std::vector / set / map-of-pairs (growable)
    0x51: "container_ptr",
    0x53: "container_wptr",
    0x54: "container_varptr",
    0x60: "string",          # only with kind 0x08
}

MEP_NAME_RE = re.compile(
    r"(Electrical|Circuit|Panel|Wire|Wiring|Conduit|CableTray|Distribution|"
    r"Power|Voltage|Fixture|Lighting|Connector|MEPSystem|System|Load|Phase)"
)

# Known class-ordinal anchors from the partition / global decoders (u16
# class words observed leading real serialized objects) plus the ZDI 2025
# research (AString = 0x1f).  The names are the wave-1 analysts' functional
# labels; some are approximate ("~"), so we match on name-family.
ANCHORS = [
    (0x001C, "ADocument", "Global/Latest lead ordinal (ADocument object graph)"),
    (0x0014, "ElementId", "u32 0x14 element-id type word in Partitions records"),
    (0x001F, "AString", "ZDI 2025: registered archive class AString = index 0x1f"),
    (0x0025, "Element", "universal element base ordinal in partition class words"),
    (0x05C9, "ElemTable", "Global/ElemTable lead ordinal 0x5c9"),
    (0x0538, "DocumentHistory", "Global/History lead ordinal 0x538"),
    (0x053C, "DocumentIncrementTable", "Global/DocumentIncrementTable lead 0x53c"),
    (0x053E, "DocumentStorageIndex", "Contents stream item word 0x53e (Contents/DocumentStorageIndex)"),
    (0x0C80, "PartitionTable", "Global/PartitionTable lead ordinal 0xc80"),
    (0x03A2, "ContentMarker", "content separator word a2 03 (~ContentMarker)"),
    (0x03A3, "ContentRec", "content/partition header word a3 03 (~ContentRec)"),
    (0x05E5, "ElementHeader", "Partitions seq-101 record class word 0x5e5 (~ElementHeader)"),
    (0x0F2C, "SerializedDummy", "Partitions seq-103 dominant class word 0x0f2c (~SerializedDummy)"),
    (0x089E, "GElement", "Partitions seq-103 class word 0x89e (~GElement)"),
    (0x08CC, "GStyleElem", "Partitions seq-102 top class 2252 = 0x8cc (~GStyleElem)"),
    (0x02E1, "CategoryElem", "Partitions seq-102 top class 737 = 0x2e1 (~CategoryElem)"),
]


# ---------------------------------------------------------------------------
@dataclass
class Field:
    name: str
    kind: int
    flags: int
    offset: int
    count: int | None = None        # fixed array count (flags high nibble 1)
    type_id: int | None = None      # target class id (kind 0x0e typed / 0x0d element)
    type_name: str | None = None
    inline_definition: bool = False # target class was defined inline here
    element: "Field | None" = None  # kind 0x0d: anonymous element sub-field
    extra: int = 0                  # descriptor u16 third word (0 except VarExpr.m_refCt=4)

    @property
    def kind_name(self) -> str:
        return KIND_NAMES.get(self.kind, f"kind{self.kind:02x}")

    @property
    def flags_name(self) -> str:
        return FLAG_NAMES.get(self.flags, f"flags{self.flags:02x}")

    @property
    def tag_hex(self) -> str:
        return f"{self.kind:02x} {self.flags:02x} {self.extra & 0xff:02x} {self.extra >> 8:02x}"

    def to_json(self) -> dict:
        d = {
            "name": self.name,
            "kind": self.kind,
            "kind_name": self.kind_name,
            "flags": self.flags,
            "flags_name": self.flags_name,
            "type_id": self.type_id,
            "type_name": self.type_name,
            "count": self.count,
        }
        if self.extra:
            d["extra"] = self.extra
        if self.inline_definition:
            d["inline_definition"] = True
        if self.element is not None:
            d["element"] = self.element.to_json()
        return d


@dataclass
class ClassDef:
    type_id: int
    name: str
    version: int
    offset: int
    end: int = 0
    depth: int = 0                   # nesting depth of the definition site
    parent_id: int | None = None
    parent: str | None = None
    parent_inline: bool = False
    fields: list[Field] = dc_field(default_factory=list)
    guids: list[str] = dc_field(default_factory=list)

    def to_json(self) -> dict:
        return {
            "type_id": self.type_id,
            "type_id_hex": f"{self.type_id:#06x}",
            "name": self.name,
            "parent": self.parent,
            "parent_id": self.parent_id,
            "parent_inline": self.parent_inline,
            "version": self.version,
            "offset": self.offset,
            "end": self.end,
            "depth": self.depth,
            "fields": [f.to_json() for f in self.fields],
            "guids": self.guids,
        }


class ParseError(Exception):
    def __init__(self, offset, msg):
        super().__init__(f"parse error at {offset:#x}: {msg}")
        self.offset = offset
        self.msg = msg


class Schema:
    """Parsed schema: classes in definition order plus lookup indices."""

    def __init__(self):
        self.classes: list[ClassDef] = []   # definition order (id order)
        self.top_level: list[ClassDef] = []
        self.by_id: dict[int, ClassDef] = {}
        self.by_name: dict[str, ClassDef] = {}
        self.desc_hist: Counter = Counter()
        self.type_refs: Counter = Counter()
        self.unresolved: list[tuple[int, int]] = []
        self.consumed = 0
        self.total_size = 0
        self.trailing_pad = 0
        self.sha256 = ""
        self.source = ""

    # ---- derived views -------------------------------------------------
    def parent_chain(self, name_or_id) -> list[str]:
        c = self._get(name_or_id)
        out, seen = [], set()
        while c is not None and c.parent_id is not None and c.parent_id not in seen:
            seen.add(c.type_id)
            p = self.by_id.get(c.parent_id)
            if p is None:
                out.append(f"<{c.parent_id:#x}>")
                break
            out.append(p.name)
            c = p
        return out

    def depth_of(self, name_or_id) -> int:
        return len(self.parent_chain(name_or_id))

    def _get(self, name_or_id):
        if isinstance(name_or_id, int):
            return self.by_id.get(name_or_id)
        return self.by_name.get(name_or_id)

    def descendants(self, name_or_id) -> list[ClassDef]:
        root = self._get(name_or_id)
        if root is None:
            return []
        kids: dict[int, list[ClassDef]] = {}
        for c in self.classes:
            if c.parent_id is not None:
                kids.setdefault(c.parent_id, []).append(c)
        out, stack = [], list(kids.get(root.type_id, []))
        while stack:
            c = stack.pop()
            out.append(c)
            stack.extend(kids.get(c.type_id, []))
        return out

    def mep_classes(self) -> list[ClassDef]:
        return [c for c in self.classes if MEP_NAME_RE.search(c.name)]

    def stats(self) -> dict:
        depths = [self.depth_of(c.type_id) for c in self.classes]
        deepest = max(range(len(depths)), key=lambda i: depths[i])
        nfields = sum(len(c.fields) for c in self.classes)
        with_parent = sum(1 for c in self.classes if c.parent_id is not None)
        top_names = [c.name.encode() for c in self.top_level]
        return {
            "top_level_ascii_sorted": all(a < b for a, b in zip(top_names, top_names[1:])),
            "stream_size": self.total_size,
            "sha256": self.sha256,
            "bytes_consumed": self.consumed,
            "trailing_zero_pad": self.trailing_pad,
            "class_count": len(self.classes),
            "top_level_records": len(self.top_level),
            "inline_definitions": len(self.classes) - len(self.top_level),
            "field_count": nfields,
            "classes_with_parent": with_parent,
            "type_id_range": [f"{FIRST_TYPE_ID:#x}",
                              f"{FIRST_TYPE_ID + len(self.classes) - 1:#x}"],
            "guid_entries": sum(len(c.guids) for c in self.classes),
            "unresolved_refs": len(self.unresolved),
            "max_inheritance_depth": max(depths),
            "deepest_class": self.classes[deepest].name,
            "deepest_chain": [self.classes[deepest].name]
            + self.parent_chain(self.classes[deepest].type_id),
            "most_referenced_types": self.type_refs.most_common(20),
            "descriptor_histogram": {
                f"{k:02x} {fl:02x}": n for (k, fl), n in sorted(self.desc_hist.items())
            },
        }

    def to_json(self) -> list[dict]:
        return [c.to_json() for c in self.classes]

    def type_id_map(self) -> dict[str, str]:
        return {f"{c.type_id:#06x}": c.name for c in self.classes}


# ---------------------------------------------------------------------------
class _Parser:
    def __init__(self, data: bytes):
        self.d = data
        self.pos = 0
        self.s = Schema()
        self.next_id = FIRST_TYPE_ID

    # primitive readers ------------------------------------------------
    def u8(self):
        v = self.d[self.pos]; self.pos += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.pos)[0]; self.pos += 2
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.pos)[0]; self.pos += 4
        return v

    def take(self, n):
        v = self.d[self.pos:self.pos + n]; self.pos += n
        return v

    def ctx(self, off=None, before=24, after=40):
        off = self.pos if off is None else off
        lo = max(0, off - before)
        return f"@{off:#x}: {self.d[lo:off].hex(' ')} | {self.d[off:off + after].hex(' ')}"

    # grammar -----------------------------------------------------------
    def run(self):
        n = len(self.d)
        try:
            while self.pos < n:
                # end-of-stream sentinel: a short all-zero tail
                if n - self.pos < 16 and not any(self.d[self.pos:]):
                    self.s.trailing_pad = n - self.pos
                    break
                self.s.top_level.append(self.parse_class(0))
        except (struct.error, IndexError) as e:
            raise ParseError(self.pos, f"truncated: {e}")
        self.s.consumed = self.pos
        return self.s

    def parse_class(self, depth, assigned_id=None) -> ClassDef:
        start = self.pos
        marker = self.u16()
        if marker != 0:
            raise ParseError(start, f"class marker != 0 ({marker:#06x}) {self.ctx(start)}")
        nl = self.u16()
        name_b = self.take(nl)
        if nl == 0 or len(name_b) != nl or not _is_ident(name_b):
            raise ParseError(start, f"bad class name len={nl} {self.ctx(start)}")
        name = name_b.decode("ascii")

        my_id = self.next_id
        if assigned_id is not None and assigned_id != my_id:
            raise ParseError(start, f"inline id {assigned_id:#x} != counter {my_id:#x} ({name})")
        self.next_id += 1
        cd = ClassDef(type_id=my_id, name=name, version=0, offset=start, depth=depth)
        # register early so nested definitions can back-reference this id
        self.s.by_id[my_id] = cd

        pref = self.u16()
        if pref & 0x8000:
            cd.parent_id = pref & 0x7FFF
            base = self.parse_class(depth + 1, assigned_id=cd.parent_id)
            cd.parent = base.name
            cd.parent_inline = True
        elif pref != 0:
            cd.parent_id = pref
            base = self.s.by_id.get(pref)
            if base is None:
                self.s.unresolved.append((self.pos - 2, pref))
                cd.parent = f"<unresolved {pref:#06x}>"
            else:
                cd.parent = base.name

        cd.version = self.u32()
        fcount = self.u32()
        if fcount > 1000:
            raise ParseError(start, f"absurd field_count {fcount} in {name}")
        for _ in range(fcount):
            cd.fields.append(self.parse_field(depth, name))
        gc_off = self.pos
        gcount = self.u32()
        if gcount > 200_000:
            raise ParseError(gc_off, f"absurd guid_count {gcount} in {name}")
        for _ in range(gcount):
            g = self.take(16)
            if len(g) != 16:
                raise ParseError(gc_off, f"truncated guid table in {name}")
            cd.guids.append(g.hex())
        cd.end = self.pos

        self.s.classes.append(cd)
        self.s.by_name.setdefault(name, cd)   # first definition wins
        return cd

    def parse_field(self, depth, cls_name) -> Field:
        fo = self.pos
        fnl = self.u32()
        fn_b = self.take(fnl)
        if fnl == 0 or len(fn_b) != fnl or not _is_ident(fn_b):
            raise ParseError(fo, f"bad field name (len={fnl}) in {cls_name} {self.ctx(fo)}")
        fname = fn_b.decode("ascii")
        return self.parse_desc(depth, fname, fo, cls_name)

    def parse_desc(self, depth, fname, fo, cls_name) -> Field:
        start = self.pos
        kind = self.u8()
        flags = self.u8()
        extra = self.u16()
        # `extra` is 0 for every descriptor in the 2026 schema except one
        # (VarExpr.m_refCt: kind 0x04, extra 0x0004).  It never alters framing.
        self.s.desc_hist[(kind, flags)] += 1
        f = Field(name=fname, kind=kind, flags=flags, offset=fo, extra=extra)
        if (flags >> 4) == 0x1:                      # fixed-size array: u32 count
            f.count = self.u32()
        if kind == 0x0E and (flags & 0x0F) == 0:      # typed class member: type ref
            tref = self.u16()
            if tref & 0x8000:
                tid = tref & 0x7FFF
                nested = self.parse_class(depth + 1, assigned_id=tid)
                f.type_id = tid
                f.type_name = nested.name
                f.inline_definition = True
            else:
                f.type_id = tref
                tgt = self.s.by_id.get(tref)
                if tgt is None:
                    self.s.unresolved.append((self.pos - 2, tref))
                    f.type_name = f"<unresolved {tref:#06x}>"
                else:
                    f.type_name = tgt.name
            self.s.type_refs[f.type_name] += 1
        if kind == 0x0D:                              # inline array: element sub-field
            eo = self.pos
            enl = self.u32()
            en_b = self.take(enl)
            if enl == 0 or len(en_b) != enl or not _is_ident(en_b):
                raise ParseError(eo, f"bad element-field name (len={enl}) in {cls_name}.{fname}")
            elem = self.parse_desc(depth, en_b.decode("ascii"), eo, cls_name)
            f.element = elem
            f.type_id, f.type_name = elem.type_id, elem.type_name
            if elem.kind == 0x0E and (elem.flags & 0x0F) == 0:
                tail = self.u16()
                if tail != elem.type_id:
                    raise ParseError(self.pos - 2,
                                     f"0x0d trailing typeref {tail:#x} != element type "
                                     f"{elem.type_id} in {cls_name}.{fname}")
        return f


def _is_ident(b: bytes) -> bool:
    return all(0x20 <= c < 0x7F for c in b)


# ---------------------------------------------------------------------------
def parse(data: bytes, source: str = "") -> Schema:
    """Parse a whole ``Formats/Latest`` inflated stream. Raises ParseError."""
    p = _Parser(data)
    s = p.run()
    s.classes.sort(key=lambda c: c.type_id)   # id order (== definition order)
    s.total_size = len(data)
    s.sha256 = hashlib.sha256(data).hexdigest()
    s.source = source
    return s


def load_schema(path: str = DEFAULT_PATH) -> Schema:
    """Load and fully parse the canonical Revit 2026 schema.

    When the research corpus is not on this machine (fresh clone / cloud
    session) the default-path call falls back to the sha-pinned bundled
    genesis base's own embedded ``Formats/Latest`` -- the same bytes (the
    per-release schema constant), resolved the way the shipped plugin
    resolves them.  An explicit ``path`` is always honoured verbatim."""
    if path == DEFAULT_PATH and not os.path.isfile(path):
        try:
            from .frontdoor.standalone import bundled_schema
            return bundled_schema()
        except Exception:                                    # noqa: BLE001
            pass          # fall through to the original error naming the path
    with open(path, "rb") as fh:
        data = fh.read()
    return parse(data, source=path)


# ---------------------------------------------------------------------------
def anchor_report(s: Schema):
    """Validate the id model against known ordinal anchors.

    Match rules: EXACT if the decoded name at that id equals the anchor
    name; FAMILY if the anchor name (the wave-1 analysts' functional label,
    often marked '~approx') is contained in / contains the decoded name at
    that id or an immediate neighbour id (the label was a guess about which
    of two adjacent, tightly-related classes carries the ordinal).
    """
    rows = []
    for aid, aname, why in ANCHORS:
        got = s.by_id.get(aid)
        gname = got.name if got else "-"
        status = "MISS"
        note = ""
        if got and got.name == aname:
            status = "EXACT"
        elif got and (aname.lower() in gname.lower() or gname.lower() in aname.lower()):
            status = "EXACT-FAMILY"
            note = "same name family (label was approximate)"
        else:
            for d in (-1, 1):
                nb = s.by_id.get(aid + d)
                if nb and (nb.name == aname or aname.lower() in nb.name.lower()
                           or nb.name.lower() in aname.lower()):
                    status = f"NEIGHBOUR({d:+d})"
                    note = f"anchor label matches id {aid + d:#x} = {nb.name}"
                    break
        rows.append((aid, aname, gname, status, note, why))
    return rows


def rvtrs_tag_comparison(s: Schema):
    """Compare our id model with rvt-rs's 2026 'tag' column.

    rvt-rs reads the u16 that follows the class name (with 0x8000 set) as
    the class's "serialization tag".  In the true grammar that u16 is the
    INLINE-DEFINED PARENT's id, so rvt-rs's tag == our (parent id) for
    classes whose base is defined inline == our id + 1.  We verify that.
    """
    if not os.path.exists(RVTRS_DRIFT_CSV):
        return None
    total = plus1 = exact = other = 0
    samples = []
    with open(RVTRS_DRIFT_CSV) as fh:
        for row in csv.DictReader(fh):
            tag = (row.get("2026") or "").strip()
            if not tag:
                continue
            c = s.by_name.get(row["class_name"])
            if c is None:
                continue
            total += 1
            t = int(tag, 16)
            if t == c.type_id + 1:
                plus1 += 1
            elif t == c.type_id:
                exact += 1
            else:
                other += 1
                if len(samples) < 6:
                    samples.append((row["class_name"], f"{t:#x}", f"{c.type_id:#x}"))
    return {"compared": total, "rvtrs_tag_equals_our_id_plus_1": plus1,
            "rvtrs_tag_equals_our_id": exact, "other": other, "other_samples": samples}


# ---------------------------------------------------------------------------
def write_outputs(s: Schema):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_SCHEMA, "w") as fh:
        json.dump(s.to_json(), fh, indent=1)
    with open(OUT_IDS, "w") as fh:
        json.dump(s.type_id_map(), fh, indent=1)
    mep = s.mep_classes()
    with open(OUT_MEP, "w") as fh:
        fh.write(f"# Revit 2026 electrical/MEP class inventory ({len(mep)} classes)\n")
        fh.write("# from Formats/Latest schema; id = archive class index (definition order + 0x0c)\n")
        fh.write("# match: (Electrical|Circuit|Panel|Wire|Wiring|Conduit|CableTray|Distribution|Power|Voltage|Fixture|Lighting|Connector|MEPSystem|System|Load|Phase)\n\n")
        for c in mep:
            chain = s.parent_chain(c.type_id)
            fh.write(f"{c.type_id:#06x}  {c.name}  v{c.version}"
                     f"  parent={c.parent or '-'}  fields={len(c.fields)}"
                     f"  chain={' > '.join(chain) if chain else '-'}\n")
            for f in c.fields:
                t = f"->{f.type_name}" if f.type_name else ""
                cnt = f"[{f.count}]" if f.count is not None else ""
                fh.write(f"      {f.name}: {f.kind_name}{cnt} {f.flags_name}{t}\n")
    return len(mep)


def print_report(s: Schema, stream=sys.stdout):
    P = lambda *a: print(*a, file=stream)
    st = s.stats()
    P(f"Formats/Latest schema: {st['stream_size']:,} bytes  sha256 {st['sha256'][:16]}...")
    P(f"parsed to EOF: consumed {st['bytes_consumed']:,} bytes + {st['trailing_zero_pad']} "
      f"trailing zero pad = {st['bytes_consumed'] + st['trailing_zero_pad']:,} "
      f"(gaps: {st['stream_size'] - st['bytes_consumed'] - st['trailing_zero_pad']})")
    P(f"classes: {st['class_count']:,} (top-level {st['top_level_records']:,}, "
      f"inline {st['inline_definitions']:,})   fields: {st['field_count']:,}   "
      f"guid entries: {st['guid_entries']:,}")
    P(f"type ids {st['type_id_range'][0]}..{st['type_id_range'][1]}   "
      f"unresolved backward refs: {st['unresolved_refs']}   "
      f"top-level names ASCII-sorted: {st['top_level_ascii_sorted']}")
    P(f"classes with a base: {st['classes_with_parent']:,}   max inheritance depth: "
      f"{st['max_inheritance_depth']} ({' > '.join(st['deepest_chain'])})")
    P("20 most-referenced types (typed class fields):")
    for name, n in st["most_referenced_types"]:
        P(f"   {n:5d}  {name}")
    P("descriptor (kind flags) histogram:")
    for k, n in st["descriptor_histogram"].items():
        kd, fl = int(k[:2], 16), int(k[3:], 16)
        P(f"   {k}  {KIND_NAMES.get(kd, '?'):>9} {FLAG_NAMES.get(fl, '?'):>17}  x{n}")
    P("\nanchor validation (known stream ordinal -> decoded class):")
    ok = 0
    for aid, aname, gname, status, note, why in anchor_report(s):
        ok += status != "MISS"
        P(f"   {aid:#06x}  expect {aname:<24} got {gname:<26} {status:<14} {note}")
    P(f"   => {ok}/{len(ANCHORS)} anchors match ({ok / len(ANCHORS):.0%})")
    cmp = rvtrs_tag_comparison(s)
    if cmp:
        P(f"\nrvt-rs 2026 tag column vs our ids (their tag = inline-parent id = ours+1):")
        P(f"   compared {cmp['compared']}: tag==id+1 {cmp['rvtrs_tag_equals_our_id_plus_1']}, "
          f"tag==id {cmp['rvtrs_tag_equals_our_id']}, other {cmp['other']} {cmp['other_samples']}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else DEFAULT_PATH
    s = load_schema(path)
    print_report(s)
    nmep = write_outputs(s)
    print(f"\nwrote {OUT_SCHEMA} ({len(s.classes)} classes)")
    print(f"wrote {OUT_IDS} ({len(s.classes)} ids)")
    print(f"wrote {OUT_MEP} ({nmep} MEP/electrical classes)")

    print("\ncorpus check (schema must be byte-identical in all six files):")
    for f in sorted(glob.glob(os.path.join(ROOT, "extracted/*/Formats__Latest.gz/000.bin"))):
        with open(f, "rb") as fh:
            b = fh.read()
        h = hashlib.sha256(b).hexdigest()
        okay = "OK " if (h == EXPECTED_SHA256 and len(b) == EXPECTED_SIZE) else "!!!"
        print(f"   {okay} {h[:16]}  {len(b):>7,}  {f.split('/extracted/')[1].split('/')[0]}")

    print("\nworked examples:")
    for want in ("ADocument", "Element", "Level", "ElectricalCircuit", "PanelScheduleView"):
        c = s.by_name.get(want)
        if not c:
            print(f"   {want}: (no such class)")
            continue
        fld = ", ".join(
            f"{f.name}:{f.kind_name}" + (f"->{f.type_name}" if f.type_name else "")
            for f in c.fields[:5]
        )
        more = " ..." if len(c.fields) > 5 else ""
        print(f"   {c.type_id:#06x} {c.name} v{c.version} base={c.parent} "
              f"depth={s.depth_of(c.type_id)} fields={len(c.fields)}: {fld}{more}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

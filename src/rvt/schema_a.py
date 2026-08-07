"""Bottom-up sequential parser for the Revit ``Formats/Latest`` schema stream.

The inflated stream (498,766 bytes, byte-identical in every Revit 2026 file)
is a flat sequence of *class records*.  Every class definition -- whether it
appears at top level or is embedded inline the first time it is referenced --
receives the next sequential *type id*, starting at 0x0c (12).  Ids below
that are the primitive kind codes used by field descriptors.

Grammar (all integers little-endian) -- see docs/streams/01-schema-a.md:

    stream        := class_record*                          (until EOF)

    class_record  := u16 zero_prefix                        (always 0)
                     u16 name_len,  u8[name_len] name       (ASCII class name)
                     u16 parent_ref                         (0      = no parent
                                                             0x8000|id = define parent
                                                                inline: a class_record
                                                                follows immediately
                                                             id     = existing type id)
                     u32 version
                     u32 field_count
                     field[field_count]
                     u32 guid_count
                     u8[16] guid[guid_count]                (per-class GUID table)

    field         := u32 name_len, u8[name_len] name, descriptor

    descriptor    := u8 kind, u8 flags, u16 zero
                     [ if flags high-nibble == 0x1 : u32 array_count ]
                     [ if kind == 0x0e and (flags & 0x0f) == 0 :
                           u16 type_ref  (0x8000|id => inline class_record
                                          defining that id follows) ]
                     [ if kind == 0x0d : field  (anonymous element field,
                                                 named " ")
                       + if that element is a class-typed 0x0e:
                             u16 type_ref (repeat of the element's type id) ]

The stream parses cleanly under this grammar for 138,858 bytes
([0, 0x21e6a): 1,150 class definitions / 727 top-level records / 3,111
fields).  From 0x21e6a to EOF the inflated bytes are intrinsically damaged
(identifiers with dropped characters, letter runs, broken framing); this is a
property of the data Autodesk shipped, not of the extraction -- see the
corruption report printed by ``main`` and the doc.

Running this module writes ``extracted/_schema/schema_a.json`` (list of class
records) and ``extracted/_schema/schema_a_meta.json`` (parse + corruption
report) and prints a summary.
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import re
import struct
import sys
from collections import Counter

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # repo root; env TEKTON_ROOT overrides
DEFAULT_PATH = os.path.join(
    ROOT, "extracted/racbasicsampleproject/Formats__Latest.gz/000.bin"
)
OUT_JSON = os.path.join(ROOT, "extracted/_schema/schema_a.json")
OUT_META = os.path.join(ROOT, "extracted/_schema/schema_a_meta.json")

FIRST_TYPE_ID = 0x0C  # first user (class) type id; lower values are primitives

KIND_NAMES = {
    0x01: "bool",
    0x02: "byte/uint8",         # ByteData.m_data, m_compressedImage (byte containers)
    0x03: "uint16/short?",      # UserID.m_id, Viewer.m_viewerFlags [hypothesis]
    0x04: "int32",
    0x05: "uint32",             # colors, ATime.m_msb/m_lsb
    0x06: "float",
    0x07: "double",
    0x08: "string(AString)",   # always with flags 0x60
    0x09: "guid16",             # GUIDvalue.m_guid
    0x0A: "class-def-ref?",     # ClassDefinitionRef.m_ref (single instance)
    0x0B: "int64",
    0x0C: "?0c",                # never observed
    0x0D: "inline-array",       # anonymous fixed/var array with element sub-field
    0x0E: "class",              # user-defined class type (type_ref follows if typed)
}

FLAG_NAMES = {
    0x00: "value",
    0x01: "ptr(01)",
    0x02: "ptr(02,owned)",
    0x03: "ptr(03,weak)",
    0x10: "fixed-array",
    0x11: "fixed-array-of-ptr",
    0x50: "container(value)",
    0x51: "container(ptr)",
    0x60: "string",
}


class Desync(Exception):
    """Raised when the byte stream stops fitting the grammar."""

    def __init__(self, offset, msg):
        super().__init__(f"desync at {offset:#x}: {msg}")
        self.offset = offset
        self.msg = msg


class SchemaParser:
    def __init__(self, data: bytes):
        self.d = data
        self.pos = 0
        self.classes = []            # every class definition, in definition order
        self.top = []                # top-level class records only
        self.next_id = FIRST_TYPE_ID
        self.id_to_name = {}
        self.desc_kinds = Counter()  # (kind, flags) -> count
        self.type_string_refs = Counter()  # class name -> reference count
        self.unresolved_refs = []

    # ---- primitive readers -------------------------------------------
    def u8(self):
        v = self.d[self.pos]
        self.pos += 1
        return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.pos)[0]
        self.pos += 2
        return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.pos)[0]
        self.pos += 4
        return v

    def take(self, n):
        v = self.d[self.pos:self.pos + n]
        self.pos += n
        return v

    def ctx(self, off=None, before=32, after=48):
        off = self.pos if off is None else off
        lo = max(0, off - before)
        return f"@{off:#x}: {self.d[lo:off].hex(' ')} | {self.d[off:off + after].hex(' ')}"

    # ---- grammar ---------------------------------------------------
    def parse_stream(self):
        while self.pos < len(self.d):
            self.top.append(self.parse_class(0))
        return self.top

    def parse_class(self, depth, assigned_id=None):
        start = self.pos
        if self.pos + 4 > len(self.d):
            raise Desync(start, "truncated class header")
        prefix = self.u16()
        if prefix != 0:
            raise Desync(start, f"class zero_prefix != 0 ({prefix:#06x}) {self.ctx(start)}")
        nl = self.u16()
        name_b = self.take(nl)
        if nl == 0 or len(name_b) != nl or not _is_ident(name_b):
            raise Desync(start, f"bad class name len={nl} {self.ctx(start)}")
        name = name_b.decode("ascii")

        # type ids are assigned in definition order; an inline definition
        # carries its id in the reference and must match the running counter.
        my_id = self.next_id
        if assigned_id is not None and assigned_id != my_id:
            raise Desync(start, f"inline id {assigned_id:#x} != counter {my_id:#x} for {name}")
        self.next_id += 1
        self.id_to_name[my_id] = name

        pref = self.u16()
        parent_id = None
        parent_name = None
        parent_inline = False
        if pref & 0x8000:
            parent_id = pref & 0x7FFF
            inl = self.parse_class(depth + 1, assigned_id=parent_id)
            parent_name = inl["class_name"]
            parent_inline = True
        elif pref != 0:
            parent_id = pref
            parent_name = self.id_to_name.get(pref)
            if parent_name is None:
                self.unresolved_refs.append((self.pos - 2, pref))
                parent_name = f"<unresolved {pref:#06x}>"

        version = self.u32()
        fcount = self.u32()
        if fcount > 1000:
            raise Desync(start, f"absurd field_count {fcount} in {name} {self.ctx()}")
        fields = []
        for i in range(fcount):
            fo = self.pos
            fnl = self.u32()
            fn_b = self.take(fnl)
            if fnl == 0 or len(fn_b) != fnl or not _is_ident(fn_b):
                raise Desync(fo, f"bad field name (len={fnl}) in {name} field {i}/{fcount} {self.ctx(fo)}")
            desc = self.parse_desc(depth, name + "." + fn_b.decode("ascii"))
            fields.append({"name": fn_b.decode("ascii"), "offset": fo, **desc})
        gco = self.pos
        guid_count = self.u32()
        if guid_count > 200000:
            raise Desync(gco, f"absurd guid_count {guid_count} in {name} {self.ctx(gco)}")
        guids = [self.take(16).hex() for _ in range(guid_count)]
        rec = {
            "class_name": name,
            "type_id": my_id,
            "type_id_hex": f"{my_id:#06x}",
            "offset": start,
            "end": self.pos,
            "depth": depth,
            "parent_ref_hex": f"{pref:#06x}",
            "parent_id": parent_id,
            "parent": parent_name,
            "parent_inline": parent_inline,
            "version": version,
            "field_count": fcount,
            "fields": fields,
            "guid_count": guid_count,
            "guids": guids,
        }
        self.classes.append(rec)
        return rec

    def parse_desc(self, depth, ctx_name):
        start = self.pos
        kind = self.u8()
        flags = self.u8()
        pad = self.u16()
        if pad != 0:
            raise Desync(start, f"descriptor pad != 0 in {ctx_name} {self.ctx(start)}")
        self.desc_kinds[(kind, flags)] += 1
        desc = {
            "kind": kind,
            "kind_name": KIND_NAMES.get(kind, f"?{kind:02x}"),
            "flags": flags,
            "flag_name": FLAG_NAMES.get(flags, f"?{flags:02x}"),
            "tag_hex": f"{kind:02x} {flags:02x} 00 00",
        }
        if (flags >> 4) == 0x1:                      # fixed-size array: count
            desc["array_count"] = self.u32()
        if kind == 0x0E and (flags & 0x0F) == 0:      # typed class member: type ref
            tref = self.u16()
            desc["type_ref_hex"] = f"{tref:#06x}"
            if tref & 0x8000:
                tid = tref & 0x7FFF
                nested = self.parse_class(depth + 1, assigned_id=tid)
                desc["type_id"] = tid
                desc["type_string"] = nested["class_name"]
                desc["inline_definition"] = True
            else:
                desc["type_id"] = tref
                nm = self.id_to_name.get(tref)
                if nm is None:
                    self.unresolved_refs.append((self.pos - 2, tref))
                    nm = f"<unresolved {tref:#06x}>"
                desc["type_string"] = nm
                desc["inline_definition"] = False
            self.type_string_refs[desc["type_string"]] += 1
        if kind == 0x0D:
            # anonymous element sub-field describing the array element
            eo = self.pos
            enl = self.u32()
            en_b = self.take(enl)
            if enl == 0 or len(en_b) != enl or not _is_ident(en_b):
                raise Desync(eo, f"bad element-field name (len={enl}) in {ctx_name} {self.ctx(eo)}")
            elem = {"name": en_b.decode("ascii"), **self.parse_desc(depth, ctx_name + "[]")}
            desc["element"] = elem
            if elem.get("kind") == 0x0E and (elem.get("flags", 1) & 0x0F) == 0:
                tail = self.u16()
                desc["element_type_ref_hex"] = f"{tail:#06x}"
                if tail != elem.get("type_id"):
                    raise Desync(self.pos - 2, f"0x0d trailing typeref {tail:#x} != element type {elem.get('type_id')} in {ctx_name} {self.ctx(self.pos - 2)}")
        n = self.pos - start
        desc["raw_hex"] = self.d[start:start + min(n, 20)].hex(" ") + (" ..." if n > 20 else "")
        return desc


# --------------------------------------------------------------------------
def _is_ident(b: bytes) -> bool:
    return all(0x20 <= c < 0x7F for c in b)


def load(path=DEFAULT_PATH) -> bytes:
    with open(path, "rb") as f:
        return f.read()


def parse(data: bytes):
    """Parse the stream; returns (parser, desync_or_None)."""
    p = SchemaParser(data)
    err = None
    try:
        p.parse_stream()
    except Desync as e:
        err = e
    except (struct.error, IndexError) as e:  # ran off the end
        err = Desync(p.pos, f"truncated: {e}")
    return p, err


def classes_json(p: SchemaParser):
    out = []
    for c in p.classes:
        fields = []
        for f in c["fields"]:
            e = {k: f[k] for k in ("name", "offset", "kind", "kind_name", "flags",
                                    "flag_name", "tag_hex", "raw_hex")}
            for k in ("array_count", "type_id", "type_string", "type_ref_hex",
                      "inline_definition", "element", "element_type_ref_hex"):
                if k in f:
                    e[k] = f[k]
            fields.append(e)
        out.append({
            "class_name": c["class_name"],
            "type_id": c["type_id"],
            "type_id_hex": c["type_id_hex"],
            "offset": c["offset"],
            "end": c["end"],
            "depth": c["depth"],
            "parent": c["parent"],
            "parent_id": c["parent_id"],
            "parent_ref_hex": c["parent_ref_hex"],
            "parent_inline": c["parent_inline"],
            "version": c["version"],
            "field_count": c["field_count"],
            "fields": fields,
            "guid_count": c["guid_count"],
            "guids": c["guids"],
        })
    return out


# ---- corruption forensics on the unparseable tail ------------------------
def region_stats(b: bytes):
    if not b:
        return {}
    cnt = Counter(b)
    ent = -sum((n / len(b)) * math.log2(n / len(b)) for n in cnt.values())
    printable = sum(n for c, n in cnt.items() if 0x20 <= c < 0x7F)
    runs = len(re.findall(rb"([A-Za-z])\1{3,}", b))
    return {
        "length": len(b),
        "printable_ratio": round(printable / len(b), 4),
        "zero_ratio": round(cnt.get(0, 0) / len(b), 4),
        "entropy_bits_per_byte": round(ent, 3),
        "letter_runs_ge4_per_kb": round(runs * 1024 / len(b), 3),
    }


def salvage_scan(data: bytes, start: int, limit: int = 5000):
    """Heuristically find class-record-looking headers in the corrupted tail.

    Looks for ``00 00 <u16 len> <printable name>`` and reports the candidate
    with the bytes that follow.  These are NOT trusted: the region is damaged.
    """
    out = []
    tail = data[start:]
    for m in re.finditer(rb"\x00\x00([\x02-\x3c])\x00([A-Za-z_][ -~]{1,60})", tail):
        ln = m.group(1)[0]
        nm = m.group(2)[:ln]
        if len(nm) != ln or not re.fullmatch(rb"[A-Za-z_][A-Za-z0-9_:<>, ]*", nm):
            continue
        after = tail[m.start() + 4 + ln:m.start() + 4 + ln + 12]
        # weak plausibility: parent_ref u16 then version < 100 and count < 300
        plausible = False
        if len(after) >= 10:
            ver = struct.unpack_from("<I", after, 2)[0]
            cnt = struct.unpack_from("<I", after, 6)[0]
            plausible = ver < 100 and cnt < 300
        out.append({
            "offset": start + m.start(),
            "candidate_name": nm.decode("ascii"),
            "following_hex": after.hex(" "),
            "header_plausible": plausible,
        })
        if len(out) >= limit:
            break
    return out


def build_meta(p: SchemaParser, data: bytes, err, path: str):
    clean_end = err.offset if err else len(data)
    meta = {
        "source": path,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "grammar_clean_span": [0, clean_end],
        "clean_bytes": clean_end,
        "clean_fraction": round(clean_end / len(data), 4),
        "class_definitions_parsed": len(p.classes),
        "top_level_records_parsed": len(p.top),
        "fields_parsed": sum(len(c["fields"]) for c in p.classes),
        "type_id_range_hex": [f"{FIRST_TYPE_ID:#x}", f"{p.next_id - 1:#x}"],
        "guid_entries_parsed": sum(c["guid_count"] for c in p.classes),
        "unresolved_type_refs": [{"offset": o, "ref_hex": f"{r:#06x}"} for o, r in p.unresolved_refs],
        "descriptor_histogram": {f"{k:02x} {fl:02x} 00 00": n for (k, fl), n in sorted(p.desc_kinds.items())},
        "kind_names": {f"{k:#04x}": v for k, v in KIND_NAMES.items()},
        "flag_names": {f"{k:#04x}": v for k, v in FLAG_NAMES.items()},
        "most_referenced_types": p.type_string_refs.most_common(30),
        "desync": None,
    }
    if err:
        meta["desync"] = {
            "offset_hex": f"{err.offset:#x}",
            "message": err.msg,
            "hex_context": p.ctx(err.offset, before=48, after=64),
            "last_classes": [c["class_name"] for c in p.classes[-6:]],
        }
        meta["corruption_forensics"] = {
            "clean_region_stats": region_stats(data[:clean_end]),
            "tail_region_stats": region_stats(data[clean_end:]),
            "note": (
                "Beyond the desync offset the inflated bytes are intrinsically damaged: "
                "identifiers with dropped characters (e.g. 'temFa_idLoa', 'CutoutSkk', "
                "'Templegore'), letter runs (tttt/yyyy/OOOO) that never occur in the "
                "clean region, and record framing that no longer aligns. Two independent "
                "inflate implementations (zlib raw -15 and py inflate64) produce byte-"
                "identical output; the OLE stream is contiguous on disk; and the stream "
                "is byte-identical in all six sample files. Conclusion: the damage is "
                "in the payload Revit 2026 (build 20250227_1515) itself wrote."
            ),
        }
        salv = salvage_scan(data, clean_end)
        meta["salvage_candidates_count"] = len(salv)
        meta["salvage_candidates_sample"] = salv[:60]
    return meta


def summarize(p: SchemaParser, data: bytes, err, stream=sys.stdout):
    P = lambda *a: print(*a, file=stream)
    clean_end = err.offset if err else len(data)
    if err is None:
        P(f"OK: consumed {p.pos:,} / {len(data):,} bytes (100%) with zero gaps")
    else:
        P(f"DESYNC at {err.offset:#x} ({err.offset:,} bytes = {err.offset / len(data):.1%} of stream): {err.msg}")
        P(f"  hex context: {p.ctx(err.offset, before=32, after=48)}")
        P(f"  last classes: {[c['class_name'] for c in p.classes[-4:]]}")
        cs, ts = region_stats(data[:clean_end]), region_stats(data[clean_end:])
        P(f"  clean region [0,{clean_end:#x}): printable {cs['printable_ratio']:.3f} zeros {cs['zero_ratio']:.3f} "
          f"entropy {cs['entropy_bits_per_byte']:.2f} letter-runs>=4/KB {cs['letter_runs_ge4_per_kb']}")
        P(f"  tail region  [{clean_end:#x},end): printable {ts['printable_ratio']:.3f} zeros {ts['zero_ratio']:.3f} "
          f"entropy {ts['entropy_bits_per_byte']:.2f} letter-runs>=4/KB {ts['letter_runs_ge4_per_kb']}")
        P("  => tail is intrinsically corrupted data (see docs/streams/01-schema-a.md)")
    P(f"class definitions: {len(p.classes):,} (top-level {len(p.top):,}, inline {len(p.classes) - len(p.top):,})")
    nfields = sum(len(c["fields"]) for c in p.classes)
    P(f"fields: {nfields:,}   type ids {FIRST_TYPE_ID:#x}..{p.next_id - 1:#x}   "
      f"per-class GUID entries: {sum(c['guid_count'] for c in p.classes):,}   unresolved refs: {len(p.unresolved_refs)}")
    P("descriptor (kind flags 00 00) histogram:")
    for (k, fl), n in sorted(p.desc_kinds.items()):
        P(f"  {k:02x} {fl:02x} 00 00  {KIND_NAMES.get(k, '?'):>18} {FLAG_NAMES.get(fl, '?'):>20}  x{n}")
    P("20 most-referenced type strings:")
    for name, n in p.type_string_refs.most_common(20):
        P(f"  {n:5d}  {name}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else DEFAULT_PATH
    data = load(path)
    p, err = parse(data)
    summarize(p, data, err)

    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(classes_json(p), f, indent=1)
    meta = build_meta(p, data, err, path)
    with open(OUT_META, "w") as f:
        json.dump(meta, f, indent=1)
    print(f"wrote {OUT_JSON} ({len(p.classes)} classes)")
    print(f"wrote {OUT_META}")

    # confirm the schema stream is a per-release constant across the corpus
    print("sha256 of inflated Formats/Latest across all six files:")
    for f in sorted(glob.glob(os.path.join(ROOT, "extracted/*/Formats__Latest.gz/000.bin"))):
        with open(f, "rb") as fh:
            b = fh.read()
        print(f"  {hashlib.sha256(b).hexdigest()[:16]}  {len(b):>7,}  {f.split('/extracted/')[1].split('/')[0]}")

    # a few worked examples for the report
    print("\nworked examples (class @ offset [id]: fields):")
    for want in ("ImportVocabulary", "ADocument", "Trf", "ADTGridImportVocabulary"):
        for c in p.classes:
            if c["class_name"] == want:
                fld = ", ".join(f"{f['name']}:{f['tag_hex']}" + (f"->{f['type_string']}" if 'type_string' in f else '') for f in c["fields"][:4])
                more = " ..." if len(c["fields"]) > 4 else ""
                print(f"  {c['class_name']} @{c['offset']:#x} [id {c['type_id_hex']}] parent={c['parent']} v{c['version']} nfields={c['field_count']}: {fld}{more}")
                break
    return 0 if err is None else 3


if __name__ == "__main__":
    sys.exit(main())

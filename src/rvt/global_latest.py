"""Framing parser / region mapper for the Revit ``Global/Latest`` stream.

``Global/Latest`` is the serialized ``ADocument`` object graph (the schema for
``ADocument`` lives in ``Formats/Latest``).  This module does *framing*, not a
full decode: it establishes the primitive encodings, walks the leading
structures whose grammar we have cracked, locates the big landmark regions,
and prints a byte-region map.

Established encodings (see docs/streams/03-global-latest.md for evidence):

* ``AString``  : u32 char_count + UTF-16LE code units, no terminator.
* ``ElementId``: signed 64-bit little-endian; ``-1`` (8 x 0xff) = invalid.
* ``GUID``     : 16 raw bytes, Microsoft mixed-endian layout.
* class ref    : u16 index into the ``Formats/Latest`` class table
                 (first user class id = 12, sequential in schema-file order).
* typed pointer: ``i32 -1`` + u16 class index (6 bytes), often followed by a
                 u32 flag/count; ``-1`` = "no ElementId / body follows or is
                 externalized".

Run:  .venv/bin/python -m rvt.global_latest            (racbasic + rstbasic)
      .venv/bin/python src/rvt/global_latest.py --all   (all six samples)
"""
from __future__ import annotations

import json
import os
import re
import struct
import sys
import zlib
from collections import Counter
from dataclasses import dataclass, field
from typing import Optional

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # repo root; env TEKTON_ROOT overrides
EXTRACTED = os.path.join(ROOT, "extracted")
SAMPLES = [
    "racbasicsampleproject",
    "rstbasicsampleproject",
    "racadvancedsampleproject",
    "rstadvancedsampleproject",
    "rmebasicsampleproject",
    "dach-sample-project",
]


# --------------------------------------------------------------------------
# loading / decompression
# --------------------------------------------------------------------------

def load_global_latest(project: str) -> tuple[bytes, dict]:
    """Return (inflated_bytes, info) for a sample project's Global/Latest.

    Prefers the pre-inflated ``Global__Latest.gz/000.bin``; otherwise
    re-inflates ``Global__Latest.bin`` (skip 8-byte prefix + 10-byte gzip
    header, raw inflate with wbits=-15).
    """
    info = {}
    raw_path = os.path.join(EXTRACTED, project, "Global__Latest.bin")
    pre_path = os.path.join(EXTRACTED, project, "Global__Latest.gz", "000.bin")
    raw = open(raw_path, "rb").read() if os.path.exists(raw_path) else None
    if raw is not None:
        info["raw_size"] = len(raw)
        info["prefix8"] = raw[:8].hex()
        info["prefix8_le_u64"] = struct.unpack_from("<Q", raw, 0)[0]
        info["gzip_magic_at_8"] = raw[8:10] == b"\x1f\x8b"
    if os.path.exists(pre_path):
        data = open(pre_path, "rb").read()
        info["source"] = pre_path
        if raw is not None:
            do = zlib.decompressobj(-15)
            do.decompress(raw[18:])
            info["deflate_trailer_len"] = len(do.unused_data)
    else:
        if raw is None:
            raise FileNotFoundError(raw_path)
        do = zlib.decompressobj(-15)
        data = do.decompress(raw[18:])
        info["source"] = raw_path + " (re-inflated)"
        info["deflate_trailer_len"] = len(do.unused_data)
    info["inflated_size"] = len(data)
    return data, info


# --------------------------------------------------------------------------
# class-id -> name table (from Formats/Latest)
# --------------------------------------------------------------------------

_CLASS_TABLE: Optional[dict[int, str]] = None


def class_table() -> dict[int, str]:
    """Best-effort map: schema class index -> name.

    Uses ``extracted/_schema/schema_a.json`` if the schema agent has produced
    it; otherwise falls back to a heuristic scan of ``Formats/Latest``: every
    u16-length-prefixed printable token (class names AND C++ type strings) in
    file order gets the next id starting at 12.  This heuristic is validated by
    the 0x8000-flagged explicit references in the schema (423/458 exact
    matches) but only for the leading ~146 KB of the schema (ids <= ~1450);
    the schema's tail region uses a different encoding, so higher ids resolve
    to None here.  Explicit flagged references override the rank estimate.
    """
    global _CLASS_TABLE
    if _CLASS_TABLE is not None:
        return _CLASS_TABLE
    table: dict[int, str] = {}
    js = os.path.join(EXTRACTED, "_schema", "schema_a.json")
    if os.path.exists(js):
        try:
            j = json.load(open(js))
            # tolerate a few plausible shapes
            classes = j.get("classes", j) if isinstance(j, dict) else j
            if isinstance(classes, dict):
                it = classes.items()
            else:
                it = enumerate(classes)
            for k, v in it:
                if isinstance(v, dict):
                    cid = v.get("type_id", v.get("id", v.get("index", k)))
                    name = v.get("class_name", v.get("name"))
                else:
                    cid, name = k, v
                try:
                    cid = int(cid)
                except (TypeError, ValueError):
                    continue
                if isinstance(name, str) and name:
                    table[cid] = name
        except Exception:
            table = {}
    if len(table) < 100:
        table = _scan_formats_class_table()
    else:
        # supplement ids the schema decode does not cover (schema tail) with
        # the heuristic scan, marked as such
        heur = _scan_formats_class_table()
        for cid, nm in heur.items():
            if cid not in table:
                table[cid] = nm + "(h)"
    _CLASS_TABLE = table
    return table


def _scan_formats_class_table(project: str = "racbasicsampleproject") -> dict[int, str]:
    path = os.path.join(EXTRACTED, project, "Formats__Latest.gz", "000.bin")
    if not os.path.exists(path):
        return {}
    f = open(path, "rb").read()
    order: list[str] = []
    seen = set()
    i = 0
    n = len(f)
    ident_first = re.compile(rb"[A-Za-z_:]")
    while i < n - 3:
        L = f[i] | (f[i + 1] << 8)
        if 2 <= L <= 200 and i + 2 + L <= n:
            s = f[i + 2:i + 2 + L]
            if all(0x20 <= c < 0x7F for c in s) and ident_first.match(s[:1]):
                nm = s.decode("latin1")
                if nm not in seen:
                    seen.add(nm)
                    order.append(nm)
                i += 2 + L
                continue
        i += 1
    table = {12 + r: nm for r, nm in enumerate(order)}
    # explicit flagged refs (u16 idx|0x8000, u16 0, u16 len, name) win
    for i in range(0, n - 8):
        v = f[i] | (f[i + 1] << 8)
        if v & 0x8000 and f[i + 2] == 0 and f[i + 3] == 0:
            L = f[i + 4] | (f[i + 5] << 8)
            if 1 <= L <= 200 and i + 6 + L <= n:
                s = f[i + 6:i + 6 + L]
                if all(0x20 <= c < 0x7F for c in s) and ident_first.match(s[:1]):
                    idx = v & 0x7FFF
                    if idx < 1500:  # tail of schema uses another encoding
                        table[idx] = s.decode("latin1")
    # ids the heuristic cannot resolve: mark None
    return table


# highest class id we trust from the fallback heuristic
TRUSTED_MAX_ID = 1450


def class_name(cid: int) -> str:
    t = class_table()
    nm = t.get(cid)
    if nm is None:
        return f"cls#{cid}(?)"
    trusted = cid <= TRUSTED_MAX_ID or len(t) > 3000
    return f"cls#{cid}={nm}" + ("" if trusted else "(??)")


# --------------------------------------------------------------------------
# primitive readers
# --------------------------------------------------------------------------

class Reader:
    def __init__(self, d: bytes, pos: int = 0):
        self.d = d
        self.p = pos

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v

    def u16(self):
        v = struct.unpack_from("<H", self.d, self.p)[0]; self.p += 2; return v

    def u32(self):
        v = struct.unpack_from("<I", self.d, self.p)[0]; self.p += 4; return v

    def i32(self):
        v = struct.unpack_from("<i", self.d, self.p)[0]; self.p += 4; return v

    def i64(self):
        v = struct.unpack_from("<q", self.d, self.p)[0]; self.p += 8; return v

    def guid(self):
        b = self.d[self.p:self.p + 16]; self.p += 16
        return fmt_guid(b)

    def astring(self):
        n = self.u32()
        b = self.d[self.p:self.p + 2 * n]
        self.p += 2 * n
        return b.decode("utf-16le", errors="replace")

    def peek(self, n=16):
        return self.d[self.p:self.p + n]


def fmt_guid(b: bytes) -> str:
    d1, d2, d3 = struct.unpack_from("<IHH", b, 0)
    tail = b[8:16]
    return f"{d1:08x}-{d2:04x}-{d3:04x}-{tail[0]:02x}{tail[1]:02x}-{tail[2:].hex()}"


def plausible_astring(d: bytes, p: int, maxlen: int = 4000,
                      ascii_only: bool = False) -> Optional[tuple[int, str]]:
    """If a u32-length-prefixed UTF-16LE string starts at p, return (nchars, str)."""
    if p + 4 > len(d):
        return None
    n = struct.unpack_from("<I", d, p)[0]
    if not (1 <= n <= maxlen) or p + 4 + 2 * n > len(d):
        return None
    b = d[p + 4:p + 4 + 2 * n]
    for j in range(0, 2 * n, 2):
        c = b[j] | (b[j + 1] << 8)
        if ascii_only:
            if not (c in (9, 10, 13) or 0x20 <= c < 0x7F):
                return None
        elif not (c in (9, 10, 13) or 0x20 <= c < 0xD800 or 0xE000 <= c < 0xFFFE):
            return None
        if c == 0:
            return None
    try:
        return n, b.decode("utf-16le")
    except Exception:
        return None


# --------------------------------------------------------------------------
# region map
# --------------------------------------------------------------------------

@dataclass
class Region:
    start: int
    end: int
    desc: str
    confidence: str  # HIGH / MED / LOW
    details: list = field(default_factory=list)

    def size(self):
        return self.end - self.start


@dataclass
class Analysis:
    project: str
    info: dict
    regions: list = field(default_factory=list)
    notes: list = field(default_factory=list)

    def add(self, start, end, desc, conf, details=None):
        self.regions.append(Region(start, end, desc, conf, details or []))


# --------------------------------------------------------------------------
# structured region parsers
# --------------------------------------------------------------------------

HEADER_LEN = 0x53  # constant across all six 2026 samples


def parse_header(d: bytes, an: Analysis) -> int:
    """Parse the constant 0x53-byte prologue.  Returns offset after it."""
    r = Reader(d, 0)
    det = []
    root_cls = r.u32()
    det.append(f"0x00 u32 {root_cls} (0x{root_cls:x}) : root class id -> {class_name(root_cls)} [hypothesis: ADocument]")
    det.append(f"0x04 u32 {r.u32()}, 0x08 u16 {r.u16()} : unknown zero words [hypothesis: m_elemTable/m_appInfoArr = external/empty]")
    # typed-pointer tokens
    for label in ("m_oContentTable", None, "m_pAppInfoManager", "m_pStyleSettings",
                  None, "m_pHistory", None, "m_pSteelModelInfo"):
        pos = r.p
        peek = r.peek(6)
        if peek[:4] == b"\xff\xff\xff\xff":
            tag = r.i32(); cls = r.u16()
            det.append(f"0x{pos:02x} ptr (tag {tag}, {class_name(cls)}) : {label} [MED]")
        else:
            v = r.u32()
            det.append(f"0x{pos:02x} u32 {v} : filler/flag [LOW]")
    eid1 = r.i64(); eid2 = r.i64()
    det.append(f"0x34 ElementId64 {eid1} : m_ownerFamilyId [MED]")
    det.append(f"0x3c ElementId64 {eid2} : m_ownerFamilyContainingGroupId [MED]")
    dev = r.u32(); syncv = r.u32()
    det.append(f"0x44 u32 {dev}, 0x48 u32 {syncv} (0x{syncv:x}) : DevBranchInfo{{devBranchId, syncVersion}}?? — 0x{syncv:x} equals ADocument's schema version 2662 [hypothesis]")
    flags = r.d[r.p:r.p + 3]; r.p += 3
    det.append(f"0x4c bytes {flags.hex()} : m_groupFile/m_corruptDocument/m_bIsCoreDocument = 3 bools [MED]")
    upg = r.u32()
    det.append(f"0x4f u32 {upg} : count of m_executedUpgrades (GUIDvalue list) [MED]")
    end = r.p
    conf = "HIGH" if end == HEADER_LEN else "MED"
    an.add(0, end, "ADocument prologue: root class, typed-pointer tokens for externalized "
                   "sub-tables, two invalid ElementId64s, DevBranchInfo, 3 bools, upgrade count. "
                   "Byte-identical across all six samples.", conf, det)
    return end


def parse_stored_by_build(d: bytes, p: int, an: Analysis) -> int:
    r = Reader(d, p)
    n = r.u32()
    det = []
    strs = []
    for _ in range(n):
        s = r.astring()
        strs.append(s)
        det.append(repr(s))
    an.add(p, r.p, f"m_storedByRevitBuild: u32 count {n} + {n} AString (AStringWrapper list) — "
                    f"Revit build history that saved this file.", "HIGH", det)
    return r.p


def parse_exservices(d: bytes, p: int, an: Analysis) -> int:
    """The object serialized right after the build list.

    Layout: ptr-token (i32 -1, u16 cls=0x644), u32 1, u32 count N, then N
    entries: {u32 flag, GUID(16), AString vendor, ElementId64, u32 a, u32 b,
    i32 -1, u32 npairs, npairs*(u32 key,u32 val)}.
    """
    r = Reader(d, p)
    det = []
    if r.peek(4) != b"\xff\xff\xff\xff":
        an.notes.append(f"exservices region not found at 0x{p:x}")
        return p
    tag = r.i32(); cls = r.u16(); one = r.u32(); count = r.u32()
    det.append(f"ptr token (tag {tag}, {class_name(cls)}), u32 {one}, u32 count {count}")
    entries = []
    ok = 0
    for k in range(count):
        start = r.p
        try:
            flag = r.u32()
            g = r.guid()
            vendor = r.astring()
            eid = r.i64()
            a = r.u32(); b = r.u32()
            tag2 = r.i32(); npairs = r.u32()
            if npairs > 64:
                raise ValueError("npairs")
            pairs = [(r.u32(), r.u32()) for _ in range(npairs)]
        except Exception as e:  # noqa: BLE001
            det.append(f"entry {k} at 0x{start:x} failed: {e}")
            break
        entries.append((start, flag, g, vendor, eid, a, b, tag2, pairs))
        ok += 1
    for e in entries[:6]:
        det.append(f"@0x{e[0]:x} flag={e[1]} guid={e[2]} vendor={e[3]!r} eid={e[4]} "
                   f"a=0x{e[5]:x} b=0x{e[6]:x} tag={e[7]} pairs={[(hex(k), v) for k, v in e[8]]}")
    if len(entries) > 6:
        det.append(f"... {len(entries)} entries total; distinct (a,b): "
                   f"{Counter((e[5], e[6]) for e in entries).most_common(4)}; "
                   f"pair keys: {Counter(k for e in entries for k, _ in e[8]).most_common(6)}")
    vendors = Counter(e[3] for e in entries)
    det.append(f"vendors: {vendors.most_common(5)}")
    conf = "HIGH" if ok == count else "MED"
    an.add(p, r.p, f"m_oExServicesUsed-like object: {count} GUID-keyed entries "
                    f"(vendor string 'Autodesk Revit'), sorted by GUID bytes (std::map). "
                    f"Parsed {ok}/{count}.", conf, det)
    return r.p


def parse_indexed_object_map(d: bytes, p: int, an: Analysis) -> int:
    """u32 1, u32 0xf1 (constant across files: NOT the entry count; 0xf1=241 ==
    class id of ``PostedWarning``?? [hypothesis]), then entries: u32 key
    (sequential from 2), u16 classIdx-like (+ variable, mostly-zero body).
    We resync on the next key."""
    start = p
    r = Reader(d, p)
    det = []
    flag = r.u32(); count = r.u32()
    det.append(f"u32 {flag}, u32 {count} (0x{count:x}) — constant across all samples, "
               f"so not the entry count; 0x{count:x} would be {class_name(count)} as a class id")
    key = struct.unpack_from("<I", d, r.p)[0]
    first_key = key
    entries = []
    p = r.p
    limit = min(len(d), start + 0x4000)
    while p < limit:
        k = struct.unpack_from("<I", d, p)[0]
        if k != key:
            break
        # find next key
        nxt = None
        for q in range(p + 4, min(p + 80, len(d) - 4)):
            if struct.unpack_from("<I", d, q)[0] == key + 1:
                nxt = q
                break
        if nxt is None:
            payload = d[p + 4:p + 10]
            entries.append((p, k, payload))
            p += 10
            key += 1
            break
        payload = d[p + 4:nxt]
        entries.append((p, k, payload))
        p = nxt
        key += 1
    classes = Counter()
    for off, k, payload in entries:
        if len(payload) >= 2:
            classes[struct.unpack_from("<H", payload, 0)[0]] += 1
    det.append(f"keys {first_key}..{key - 1} ({len(entries)} entries); payload sizes: "
               f"{dict(Counter(len(e[2]) for e in entries))}")
    for off, k, payload in entries[:8]:
        cid = struct.unpack_from("<H", payload, 0)[0] if len(payload) >= 2 else -1
        det.append(f"@0x{off:x} key {k}: {payload.hex(' ')}  -> lead u16 {class_name(cid)}")
    det.append(f"lead-u16 values are unique per entry (looks like class ids >= 0x400): "
               f"min {min(classes) if classes else '-'} max {max(classes) if classes else '-'}")
    an.add(start, p, f"u32-keyed table (key seq {first_key}..{key - 1}, {len(entries)} entries): "
                    f"each entry = u32 key + u16 (class-id-like) + 0..n zero u32s. "
                    f"[hypothesis: per-class/per-manager registry, e.g. document sub-object table]",
           "MED", det)
    return p


def parse_pointer_run(d: bytes, p: int, an: Analysis) -> int:
    """After the keyed table: a short run of (u16 cls, i32 -1)-style typed
    null pointers, then zero padding.  Purely descriptive."""
    start = p
    toks = []
    # optional leading (u16, i32 -1) pattern
    q = p
    while q + 6 <= len(d):
        cls = struct.unpack_from("<H", d, q)[0]
        tag = struct.unpack_from("<i", d, q + 2)[0]
        if tag != -1 or cls == 0xFFFF:
            break
        toks.append((q, cls))
        q += 6
    # then a final u16 + zero padding
    end = q
    zrun = 0
    while end + zrun < len(d) and d[end + 2 + zrun] == 0 and zrun < 200:
        zrun += 1
    det = [f"@0x{o:x} ({class_name(c)}, -1)" for o, c in toks[:16]]
    det.append(f"then u16 0x{struct.unpack_from('<H', d, end)[0]:x} + {zrun} zero bytes")
    fin = end + 2 + zrun
    an.add(start, fin, f"run of {len(toks)} typed null-pointer tokens (u16 classIdx + i32 -1) "
                       f"followed by zero padding [hypothesis: remaining ADocument pointer "
                       f"members / editing-mode manager refs]", "LOW", det)
    return fin


def parse_noble_secondary(d: bytes, p: int, an: Analysis, region_end: int) -> int:
    """m_oNobleSecondaryData region: 'NobleDocWarnings' object then a stream
    of ColorFillSecondaryData entries.  The first 9 entries carry an explicit
    typed-pointer header ``ff ff ff ff 2a 03 01 00 00 00``; later ones are
    embedded records ``u32 1 + 5 AStrings + ElementId64s``.  We anchor on the
    class-name string, which every entry stores twice."""
    anchor = "NobleDocWarnings".encode("utf-16le")
    i = d.find(anchor, p)
    if i < 0:
        an.notes.append("no NobleDocWarnings anchor found (dach-style file?)")
        return p
    start = i - 8  # u32 1 + u32 len(16)
    det = []
    r = Reader(d, start)
    one = r.u32(); name = r.astring()
    tag = r.i32(); cls = r.u16(); n = r.u32()
    det.append(f"u32 {one}, AString {name!r}, ptr (tag {tag}, {class_name(cls)}), u32 {n}")
    # explicit typed-header objects
    pat = b"\xff\xff\xff\xff\x2a\x03\x01\x00\x00\x00"
    hdr_objs = []
    q = r.p
    while True:
        j = d.find(pat, q, region_end)
        if j < 0:
            break
        hdr_objs.append(j)
        q = j + 10
    # entries by class-name string (each entry has the string twice)
    s = "ColorFillSecondaryData".encode("utf-16le")
    slocs = []
    q = r.p
    while True:
        j = d.find(s, q, region_end)
        if j < 0:
            break
        slocs.append(j - 4)
        q = j + len(s)
    entries = []
    k = 0
    while k + 1 < len(slocs):
        e0 = slocs[k]
        # strings: name, group, name, kind, target
        rr = Reader(d, e0)
        strs = []
        for _ in range(6):
            pa = plausible_astring(d, rr.p, 300)
            if pa is None:
                break
            strs.append(pa[1]); rr.p += 4 + 2 * pa[0]
        eid = None
        for q2 in range(rr.p, min(rr.p + 60, len(d) - 8)):
            v = struct.unpack_from("<q", d, q2)[0]
            if 1000 < v < 20_000_000 and d[q2 + 3:q2 + 8] == b"\x00" * 5:
                eid = v
                break
        entries.append((e0, strs, eid))
        k += 2
    for e in entries[:5]:
        det.append(f"@0x{e[0]:x} strings={e[1]} elementId={e[2]}")
    if len(entries) > 5:
        det.append(f"... {len(entries)} ColorFillSecondaryData entries "
                   f"({len(hdr_objs)} carry an explicit ptr header ff ff ff ff 2a 03 01 00 00 00, "
                   f"the rest are embedded 'u32 1 + strings' records); element ids "
                   f"{[e[2] for e in entries[:4]]} .. {[e[2] for e in entries[-3:]]}")
    endp = (entries[-1][0] + 300) if entries else r.p
    an.add(start, endp, f"m_oNobleSecondaryData head: 'NobleDocWarnings' (ptr class "
                          f"0x{cls:x}) + {len(entries)} ColorFillSecondaryData entries "
                          f"(class 0x32a=810); each carries ElementId64s present in "
                          f"Global/ElemTable.", "MED", det)
    return endp


def find_units_dictionary(d: bytes, p: int, an: Analysis) -> tuple[int, int, int]:
    """The Forge units/spec JSON dictionary: (typeid AString, json AString)
    pairs.  Header just before the first typeid: ..., u64 1, i64 -1, u32 1,
    u32 count(=893 declared in every sample that has the dictionary).
    Returns (dict_start, clean_end, last_typeid_end)."""
    pat = "autodesk.unit.dimension:currency-1.0.0".encode("utf-16le")
    i = d.find(pat, p)
    if i < 0:
        an.notes.append("no units dictionary anchor found (dach-style file: units JSON absent)")
        return p, p, p
    tstart = i - 4
    hdr = tstart - 40
    det = []
    r = Reader(d, hdr)
    det.append(f"pre-header @0x{hdr:x}: u64 0x{r.i64() & (2**64-1):x}, i64 {r.i64()}, "
               f"u64 {r.i64()}, i64 {r.i64()}, u32 {r.u32()}, u32 declared count {r.u32()}")
    q = tstart
    pairs = []
    breaks = []
    clean_end = tstart
    while q < len(d) - 8 and len(pairs) < 5000:
        a = plausible_astring(d, q, 200)
        if a is None or "autodesk." not in a[1]:
            break
        js = q + 4 + 2 * a[0]
        jl = struct.unpack_from("<I", d, js)[0] if js + 4 <= len(d) else 0
        je = js + 4 + 2 * jl
        if not (10 <= jl <= 200000) or je > len(d) or d[js + 4:js + 6] != b"{\x00":
            breaks.append((q, a[1], "not a clean (typeid,json) pair"))
            break
        pairs.append((q, a[1], jl))
        q = je
        if not breaks:
            clean_end = je
        nxt_ok = plausible_astring(d, q, 200)
        if nxt_ok is None or b"autodesk" not in d[q + 4:q + 24]:
            nxt = d.find("autodesk.".encode("utf-16le"), q, q + 20000)
            if nxt < 0:
                break
            if nxt - 4 != q:
                breaks.append((q, a[1], f"{nxt - 4 - q} junk bytes before next typeid"))
            q = nxt - 4
    det.append(f"parsed {len(pairs)} (typeid, json) pairs; first: {pairs[0][1] if pairs else '-'}; "
               f"last: {pairs[-1][1] if pairs else '-'}")
    det.append(f"json length stats (chars): min {min(x[2] for x in pairs) if pairs else 0}, "
               f"max {max(x[2] for x in pairs) if pairs else 0}")
    for b in breaks[:8]:
        det.append(f"irregularity near 0x{b[0]:x} after {b[1]!r}: {b[2]}")
    end = q
    an.add(hdr, clean_end, f"units/spec dictionary (clean part): u32 1 + u32 count 893 + "
                             f"({len(pairs)} typeids found) x (AString typeid, AString json) — "
                             f"Autodesk Forge unit/dimension/symbol schemas embedded verbatim.",
           "MED", det)
    if end > clean_end:
        an.add(clean_end, end, "units/spec dictionary (degraded part): further typeid/json pairs "
                               "separated by runs of shredded JSON fragments (junk bytes between "
                               "entries) — same encoding hypothesis as the blob below.", "LOW",
               [f"{len(breaks)} irregularities; last clean pair ends 0x{clean_end:x}, "
                f"last typeid seen ends 0x{end:x}"])
    return hdr, clean_end, end


def characterise_opaque(d: bytes, p: int, an: Analysis, tail_start: int) -> int:
    """The large stringless middle blob between the units dictionary and the
    trailing named-object region."""
    if tail_start <= p + 16:
        return p
    blob = d[p:tail_start]
    n = len(blob) or 1
    zero = blob.count(0) / n
    ff = blob.count(0xFF) / n
    evens = blob[0::2]; odds = blob[1::2]
    az = sum(1 for c in evens if 0x20 <= c < 0x7F) / max(1, len(evens))
    oz = odds.count(0) / max(1, len(odds))
    nstr = 0
    i = 0
    while i < n - 8:
        a = plausible_astring(blob, i, 300)
        if a:
            nstr += 1; i += 4 + 2 * a[0]
        else:
            i += 64
    det = [f"size {n} bytes ({100.0 * n / len(d):.1f}% of stream); zero-byte fraction {zero:.2f}; "
           f"0xff fraction {ff:.2f}; length-prefixed strings inside: ~{nstr}",
           f"even-byte printable fraction {az:.2f}; odd-byte zero fraction {oz:.2f} "
           f"(0.5/0.9+ would be plain UTF-16 text; observed values = shredded UTF-16)",
           "content: shredded fragments of the same Forge units JSON with alignment slips and "
           "1-byte insertions => [hypothesis] byte-oriented LZ/delta coded continuation of the "
           "units dictionary (the declared count 893 exceeds the ~590-600 clean pairs); NOT "
           "plain AStrings and NOT nested gzip/zlib (no magic, no valid deflate window found)."]
    an.add(p, tail_start, "OPAQUE units-JSON continuation blob (no clean framing; needs a "
                          "dedicated decoder pass)", "LOW", det)
    return tail_start


def find_tail_start(d: bytes, after: int) -> int:
    """Find where clean, non-units length-prefixed strings resume after
    `after`: first plausible AString (not 'autodesk.*') that is followed by
    >= 4 more plausible AStrings within the next 32 KB."""
    n = len(d)
    i = max(after, 0)
    junky = ("autodesk", "typeid", "unit:", "annotation", "{", "value\"", "id\"")
    while i < n - 8:
        a = plausible_astring(d, i, 120, ascii_only=True)
        if a is not None and not any(j in a[1] for j in junky):
            # confirm with follow-up ascii strings within 32 KB
            cnt = 0
            j = i + 4 + 2 * a[0]
            lim = min(n - 8, i + 32768)
            while j < lim and cnt < 5:
                b = plausible_astring(d, j, 120, ascii_only=True)
                if b is not None and not any(x in b[1] for x in junky):
                    cnt += 1
                    j += 4 + 2 * b[0]
                else:
                    j += 1
            if cnt >= 5:
                return i
            i += 4 + 2 * a[0]
            continue
        i += 1
    return n


def strings_census(d: bytes, a: int, b: int, maxn: int = 300, ascii_only: bool = True):
    out = []
    i = a
    while i < b - 8:
        pa = plausible_astring(d, i, maxn, ascii_only=ascii_only)
        if pa is not None:
            out.append((i, pa[1]))
            i += 4 + 2 * pa[0]
        else:
            i += 1
    return out


def characterise_tail(d: bytes, p: int, an: Analysis) -> None:
    """Trailing region: named settings objects, rooms, links, etc."""
    n = len(d)
    strs = strings_census(d, p, n)
    det = [f"{len(strs)} AStrings; sample: " +
           "; ".join(f"0x{o:x}={s!r}" for o, s in strs[:14])]
    if len(strs) > 14:
        det.append("more: " + "; ".join(f"0x{o:x}={s!r}" for o, s in strs[14:40]))
    cnt = Counter(s for _, s in strs)
    det.append(f"most common: {cnt.most_common(8)}")
    an.add(p, n, "tail region: heterogeneous named objects (system families, numbering "
                 "schemas, DB server info, MEP systems, revision settings, LB_* link data, "
                 "room/space names) — not framed yet.", "LOW", det)


def annotate_gap(d: bytes, reg: Region) -> None:
    """Add a strings census to an unparsed gap region."""
    strs = strings_census(d, reg.start, reg.end)
    reg.details.append(f"{len(strs)} clean AStrings in {reg.size()} bytes (mostly binary: "
                       f"ElementId64s, doubles, small ints)")
    if strs:
        cnt = Counter(s for _, s in strs)
        reg.details.append("top strings: " + "; ".join(f"{s!r}x{c}" for s, c in cnt.most_common(10)))
        reg.details.append("first: " + "; ".join(f"0x{o:x}={s!r}" for o, s in strs[:8]))


# --------------------------------------------------------------------------
# heuristic scanners (whole stream)
# --------------------------------------------------------------------------

def scan_typed_pointers(d: bytes, ranges: list, top: int = 30):
    """(i32 -1, u16 X, u32 f in {0,1}) tokens; X = class index candidate.

    Restricting the trailing u32 to a small flag suppresses the noise from
    ElementId64 -1 runs and the opaque blob."""
    cnt: Counter = Counter()
    first: dict[int, int] = {}
    for a, b in ranges:
        i = a
        while True:
            i = d.find(b"\xff\xff\xff\xff", i, b)
            if i < 0 or i + 10 > b:
                break
            cls = struct.unpack_from("<H", d, i + 4)[0]
            flg = struct.unpack_from("<I", d, i + 6)[0]
            if 12 <= cls < 0x2000 and cls & 0xFF != 0xFF and flg in (0, 1):
                cnt[cls] += 1
                first.setdefault(cls, i)
            i += 1
    return [(cls, c, first[cls], class_name(cls)) for cls, c in cnt.most_common(top)]


def scan_u32_smallints(d: bytes, ranges: list, top: int = 30):
    """u32-aligned values in the plausible class-id range, over given ranges."""
    cnt: Counter = Counter()
    pos: dict[int, int] = {}
    for a, b in ranges:
        for i in range(a & ~3, b - 4, 4):
            v = d[i] | (d[i + 1] << 8) | (d[i + 2] << 16) | (d[i + 3] << 24)
            if 0x100 <= v <= 0x1400 and (v & 0xFF) != 0xFF:
                cnt[v] += 1
                pos.setdefault(v, i)
    return [(v, c, pos[v], class_name(v)) for v, c in cnt.most_common(top)]


def scan_u16_after_u32count(d: bytes, ranges: list, top: int = 20):
    """u16 values that immediately follow a small u32 (the 'u32 key + u16
    classIdx' motif of the indexed table)."""
    cnt: Counter = Counter()
    pos: dict[int, int] = {}
    for a, b in ranges:
        for i in range(a & ~1, b - 6, 2):
            v = struct.unpack_from("<H", d, i)[0]
            if 0x100 <= v < 0x1400 and (v & 0xFF) != 0xFF and d[i + 2:i + 4] == b"\x00\x00":
                cnt[v] += 1
                pos.setdefault(v, i)
    return [(v, c, pos[v], class_name(v)) for v, c in cnt.most_common(top)]


def elemtable_ids(project: str) -> set[int]:
    """Cheap harvest of ElementId candidates from Global/ElemTable (u64 values
    at 8-byte alignment scan is unreliable; instead take every u32 that is
    immediately followed by 4 zero bytes and > 1000)."""
    path = os.path.join(EXTRACTED, project, "Global__ElemTable.gz", "000.bin")
    if not os.path.exists(path):
        return set()
    et = open(path, "rb").read()
    ids = set()
    for i in range(0, len(et) - 8):
        if et[i + 4:i + 8] == b"\x00\x00\x00\x00":
            v = et[i] | (et[i + 1] << 8) | (et[i + 2] << 16) | (et[i + 3] << 24)
            if 1000 < v < 50_000_000:
                ids.add(v)
    return ids


def scan_elementid64(d: bytes, valid_ids: set[int], limit_report: int = 20):
    """Find int64 LE values that are known ElemTable ids."""
    hits = []
    i = 0
    n = len(d)
    step = 1
    while i < n - 8:
        if d[i + 3:i + 8] == b"\x00\x00\x00\x00\x00":
            v = d[i] | (d[i + 1] << 8) | (d[i + 2] << 16)
            if v in valid_ids:
                hits.append((i, v))
                i += 8
                continue
        i += step
    return hits


def scan_guids_near_vendor(d: bytes):
    """GUIDs are the 16 bytes preceding a length-prefixed vendor string in
    the exservices map; also generic: 16 high-entropy bytes followed by an
    AString and preceded by u32 1."""
    out = []
    pat = "Autodesk Revit".encode("utf-16le")
    i = 0
    while True:
        i = d.find(pat, i)
        if i < 0:
            break
        g = d[i - 20:i - 4]
        out.append((i - 20, fmt_guid(g)))
        i += 2
    return out


# --------------------------------------------------------------------------
# top-level analysis
# --------------------------------------------------------------------------

def analyse(project: str):
    d, info = load_global_latest(project)
    an = Analysis(project, info)
    p = parse_header(d, an)
    p = parse_stored_by_build(d, p, an)
    p = parse_exservices(d, p, an)
    p = parse_indexed_object_map(d, p, an)
    p = parse_pointer_run(d, p, an)
    # look ahead for the units dictionary so the NOBLE scan is bounded
    upat = "autodesk.unit.dimension:currency-1.0.0".encode("utf-16le")
    ui = d.find(upat, p)
    noble_bound = (ui - 48) if ui > 0 else len(d)
    p_noble_end = parse_noble_secondary(d, p, an, noble_bound)
    dict_start, dict_clean_end, dict_end = find_units_dictionary(d, p_noble_end, an)
    if dict_start > p_noble_end:
        tail_start = find_tail_start(d, dict_end + 0x10000 if dict_end > dict_clean_end else dict_end)
        characterise_opaque(d, max(dict_end, dict_clean_end), an, tail_start)
    else:
        tail_start = find_tail_start(d, p_noble_end)
    characterise_tail(d, tail_start, an)
    # gap regions (unlabelled bytes between parsed regions)
    an.regions.sort(key=lambda r: r.start)
    gaps = []
    cur = 0
    for reg in an.regions:
        if reg.start > cur:
            gaps.append(Region(cur, reg.start, "UNPARSED gap (secondary NOBLE data: color-fill "
                                                "schemes, HVAC/space & electrical naming schemes, "
                                                "browser-organization / view / sheet name records, "
                                                "small XML blobs ...)", "LOW"))
        cur = max(cur, reg.end)
    if cur < len(d):
        gaps.append(Region(cur, len(d), "UNPARSED trailing bytes", "LOW"))
    for g in gaps:
        if g.size() > 0:
            annotate_gap(d, g)
    an.regions.extend(g for g in gaps if g.size() > 0)
    an.regions.sort(key=lambda r: r.start)
    an.framed_ranges = [(r.start, r.end) for r in an.regions
                        if r.confidence in ("HIGH", "MED") or "gap" in r.desc or "tail" in r.desc]
    return an, d


def print_region_map(an: Analysis, d: bytes, verbose: bool = True) -> None:
    print("=" * 100)
    print(f"Global/Latest  ::  {an.project}")
    for k, v in an.info.items():
        print(f"  {k}: {v}")
    print("-" * 100)
    print(f"{'start':>9} {'end':>9} {'size':>9}  conf  description")
    for r in an.regions:
        print(f"0x{r.start:07x} 0x{r.end:07x} {r.size():>9}  {r.confidence:<4}  {r.desc}")
        if verbose:
            for line in r.details:
                print(f"{'':>32}  · {line}")
    for note in an.notes:
        print(f"NOTE: {note}")
    print()


def print_heuristics(project: str, d: bytes, ranges: list) -> None:
    print(f"--- heuristic scans :: {project} (framed regions only, opaque blob excluded) ---")
    print("Top typed-pointer tokens (i32 -1, u16 classIdx, u32 0|1):")
    for cls, c, first, nm in scan_typed_pointers(d, ranges):
        print(f"  0x{cls:04x} x{c:<5} first@0x{first:x}  {nm}")
    print("Top u32-aligned small ints in class-id range 0x100..0x1400 (may be enums/ids, "
          "not necessarily class ordinals):")
    for v, c, pos, nm in scan_u32_smallints(d, ranges)[:20]:
        print(f"  0x{v:04x} x{c:<5} first@0x{pos:x}  {nm}")
    print("Top u16 following a u32 (indexed-table motif):")
    for v, c, pos, nm in scan_u16_after_u32count(d, ranges)[:15]:
        print(f"  0x{v:04x} x{c:<5} first@0x{pos:x}  {nm}")
    ids = elemtable_ids(project)
    if ids:
        hits = scan_elementid64(d, ids)
        c = Counter(v for _, v in hits)
        print(f"ElementId64 values also present in Global/ElemTable: {len(hits)} hits, "
              f"{len(c)} distinct ids; first 8: "
              + ", ".join(f"{v}@0x{o:x}" for o, v in hits[:8]))
    gs = scan_guids_near_vendor(d)
    if gs:
        print(f"GUIDs keyed to 'Autodesk Revit' vendor strings: {len(gs)}; first 3: "
              + ", ".join(g for _, g in gs[:3]))
    print()


def summary_line(project: str) -> str:
    try:
        an, d = analyse(project)
    except FileNotFoundError as e:
        return f"{project}: MISSING ({e})"
    n = len(d)
    parsed = sum(r.size() for r in an.regions if r.confidence in ("HIGH", "MED"))
    return (f"{project:<26} inflated={n:>9}  prefix8={an.info.get('prefix8')}  "
            f"trailer={an.info.get('deflate_trailer_len')}  framed(HIGH+MED)={parsed:>8} "
            f"({100.0 * parsed / n:4.1f}%)  regions={len(an.regions)}")


def main(argv: list[str]) -> int:
    do_all = "--all" in argv
    verbose_all = "-v" in argv
    targets = SAMPLES if do_all else ["racbasicsampleproject", "rstbasicsampleproject"]
    for k, proj in enumerate(targets):
        try:
            an, d = analyse(proj)
        except FileNotFoundError as e:
            print(f"[skip] {proj}: {e}")
            continue
        print_region_map(an, d, verbose=(k == 0 or verbose_all))
        print_heuristics(proj, d, getattr(an, "framed_ranges", [(0, len(d))]))
    print("=" * 100)
    print("Cross-file summary")
    for proj in SAMPLES:
        print(" ", summary_line(proj))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Extensible Storage (ES): the in-model schema catalog + the entity blob codec.

Extensible Storage is Revit's self-describing add-in data: an ENTITY conforms
to a SCHEMA that an add-in (or Revit itself) registers at runtime, and every
schema an entity uses is stored INSIDE the model.  This module is the last
decode gap of the schema-directed object decoder: elements carrying
``ESEntityCell`` cells (``Element.m_cellList -> CellList.m_cells[] ->
ESEntityCell.m_entityMap : container< pair<GUIDvalue schemaGuid, ESEntity> >``)
used to fail at ``ESEntity.m_blob`` with "pointer token pid=-1 to unknown
class 0x2314".  There is no class 0x2314: the two bytes after the pointer id
are the leading bytes of the entity's 16-byte SCHEMA GUID.

Established facts (all byte-verified across the six sample projects; see
docs/writer/extensible-storage.md for the offsets and worked hexdumps):

Schema catalog (WHERE the schemas live)
    ``Global/Latest`` (the serialized ``ADocument`` graph) holds the AppInfo
    object ``ESSchemaStorage`` (archive class 0x56f); its member
    ``m_schemaUsageMap : container< std::pair< GUIDvalue, SchemaUsageInfo > >``
    IS the catalog: for every schema GUID a ``SchemaUsageInfo`` =
    {``m_contentDocsKeys`` container<GUIDvalue>, ``m_schema`` ESSchema,
    ``m_usedInHost`` bool} where ``ESSchema`` (0x56e) = {m_documentation,
    m_fields : container<ESField>, m_schemaName, m_vendorId,
    m_applicationGUID, m_guid, m_readAccessLevel, m_writeAccessLevel} and
    ``ESField`` (0x56d) = {m_documentation, m_fieldName, m_fieldTypeName,
    m_specTypeId ForgeTypeId, m_containerType (0 scalar / 1 array / 2 map),
    m_entryIndex, m_subSchemaGUID}.  These are ORDINARY archive classes, so
    the generic ``ObjectDecoder`` decodes every catalog entry as-is; the only
    work is LOCATING the map (self-validating: an entry's map key GUID must
    equal its decoded ``ESSchema.m_guid``; entries are contiguous; the u32
    before the first entry equals the entry count).  A sibling AppInfo,
    ``EStorageTracking``, holds ``m_trackingItems`` = per schema GUID the set
    of ElementIds carrying an entity of it (the source of :func:`es_report`).

Entity token (WHY class 0x2314 does not exist)
    ``ESEntity.m_blob`` is a pointer field, but the pointed-to object is a
    RUNTIME class defined by an in-model schema, so its token is
    ``i32 pid`` (0 = null: no entity, 4 bytes) followed by the 16-byte SCHEMA
    GUID in place of the usual ``u16`` archive class id.  The failing "class"
    words 0x2314 / 0x2a2b / 0x7959 / 0xb137 / 0xe691 are simply the first two
    little-endian bytes of the schema GUIDs 762a2314-.. / 1b022a2b-.. /
    4c817959-.. / e66bb137-.. / bba2e691-.. .

Entity blob grammar (the body the token points to)
    The body is DEFERRED breadth-first into the same per-record queue as any
    owned pointer body (it appears at its queue position, after the sibling
    cell bodies / connectors queued before it -- never inline).  The body is
    the schema's field VALUES concatenated in ``m_entryIndex`` order with NO
    header, count or GUID: e.g. rme duct fittings (schema
    CoefficientFromTable, one TCHAR field 'ASHRAETableName') carry the
    14-byte body ``u32 5 + "SR3-1"``; rstbasic DataStorage 1382860 (schema
    DaylightingAnalysisInfo: 'AnalysisId' TCHAR entryIndex 0, 'ResultsInvalid'
    int entryIndex 1) carries ``00000000 00000000`` = empty string + int 0.
    Field encodings = the archive primitive codebook: bool/char u8, short
    i16, int i32, int64 i64, float f32, double f64, TCHAR/AString/
    AStringWrapper = u32 count + UTF-16LE, GUIDvalue = 16 raw, ElementId =
    i64, XYZ = 3 f64, UV = 2 f64.  Containers: array (containerType 1) =
    ``u32 count`` + elements; map (containerType 2, field type name
    ``std::pair< K, V >``) = ``u32 count`` + count x (K value, V value).
    A nested ``ESEntity`` value (scalar, array element or map value) is again
    a token ``i32 pid`` [+ 16-byte SUB-schema GUID when pid != 0] whose body
    is deferred to the same queue (dach AnalyticalPanel 4276033: schema
    AnalysisResult = null 'LoadCase' + 'LoadCasesMap' map<ElementId,
    ESEntity> {1476906 -> token of subschema LoadCasesMap 5fb3dbc4-..}, whose
    body only appears after 19 other queued bodies).

Public API::

    cat  = schemas(doc)                       # ESSchemaCatalog (from Global/Latest)
    ent  = decode_entity_blob(blob, cat, guid)   # {'schema_guid', 'fields', ...}
    blob = encode_entity_blob(ent, cat)          # bytes (byte-exact inverse)
    rep  = es_report(doc)                     # schema GUID+name -> element ids
    dec  = ESDecoder(archive_schema, cat)     # record-level decoder (ObjectDecoder+ES)
    enc  = ESEncoder(dec)                     # record-level encoder (symmetric)
    verify_document(doc)                      # corpus proof: byte-exact per record

``python -m rvt.estorage <project|path.rvt> [--report] [--walk] [--roundtrip]``
reads a file under ITS OWN release (a Revit 2025/2024 project is walked with
that release's framing, entered once through ``rvt.native_framing`` -> the
``rvt.global_framing`` note-never-raise ladder; a native file enters nothing
and imports no ladder) and reports an honest
``0 schemas (reason)`` where no schema-usage map can be read.  Exit codes:
0 = reported; 1 = the file could not be loaded (stated on stderr, never a
traceback); 2 = no such file.
"""
from __future__ import annotations

import contextlib
import os
import re
import struct
import sys
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field as dc_field
from typing import Any, Optional

from .encode import ObjectEncoder, Writer, EncodeError, _Pend
from . import objects as O                      # O.iter_records at call time: ids32() rebinds it by name (#548)
from .objects import (ObjectDecoder, Reader, DecodeError, DecodedObject,
                      _Pending, _State, field_key)
from .schema import Schema

ROOT = os.environ.get("TEKTON_ROOT") or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))  # repo root; env TEKTON_ROOT overrides

# Access levels of ESSchema.m_readAccessLevel / m_writeAccessLevel
ACCESS_LEVELS = {1: "Public", 2: "Vendor", 3: "Application"}
CONTAINER_TYPES = {0: "simple", 1: "array", 2: "map"}


class ESSchemaError(Exception):
    """A schema/type is missing or unsupported (an honest, loud failure)."""


# ---------------------------------------------------------------------------
# GUID helpers (same string form as rvt.objects.Reader.guid)
# ---------------------------------------------------------------------------

def guid_str(b: bytes) -> str:
    d1, d2, d3 = struct.unpack_from("<IHH", b, 0)
    t = b[8:16]
    return f"{d1:08x}-{d2:04x}-{d3:04x}-{t[0]:02x}{t[1]:02x}-{t[2:].hex()}"


def guid_bytes(g: str) -> bytes:
    d1, d2, d3, t4, tail = g.split("-")
    return (struct.pack("<IHH", int(d1, 16), int(d2, 16), int(d3, 16))
            + bytes.fromhex(t4) + bytes.fromhex(tail))


NULL_GUID = "00000000-0000-0000-0000-000000000000"


# ---------------------------------------------------------------------------
# Catalog dataclasses
# ---------------------------------------------------------------------------

@dataclass
class ESFieldDef:
    name: str
    type_name: str            # 'TCHAR', 'int', 'double', 'ESEntity', 'std::pair< A, B >' ...
    documentation: str
    spec_type_id: str         # ForgeTypeId (units) e.g. 'autodesk.spec.aec:length-1.0.0'
    container_type: int       # 0 simple, 1 array, 2 map
    entry_index: int          # serialization slot: field values are written in this order
    sub_schema_guid: str      # for ESEntity fields: the entity's own schema

    @property
    def is_null_sub(self) -> bool:
        return self.sub_schema_guid == NULL_GUID

    def to_json(self) -> dict:
        return {
            "name": self.name, "type": self.type_name,
            "container": CONTAINER_TYPES.get(self.container_type, self.container_type),
            "entryIndex": self.entry_index,
            "spec": self.spec_type_id or None,
            "subSchema": None if self.is_null_sub else self.sub_schema_guid,
            "doc": self.documentation or None,
        }


@dataclass
class ESSchemaDef:
    guid: str
    name: str
    vendor_id: str
    application_guid: str
    documentation: str
    read_access: int
    write_access: int
    fields: list[ESFieldDef]              # SERIALIZATION order (entry_index)
    used_in_host: bool = False
    content_docs_keys: list[str] = dc_field(default_factory=list)
    offset: int = -1                       # map-entry offset in Global/Latest (or -1)
    raw: Optional[dict] = None             # the decoded pair<GUIDvalue,SchemaUsageInfo>

    def field(self, name: str) -> Optional[ESFieldDef]:
        for f in self.fields:
            if f.name == name:
                return f
        return None

    def to_json(self) -> dict:
        return {
            "guid": self.guid, "name": self.name, "vendorId": self.vendor_id,
            "applicationGuid": None if self.application_guid == NULL_GUID else self.application_guid,
            "documentation": self.documentation or None,
            "readAccess": ACCESS_LEVELS.get(self.read_access, self.read_access),
            "writeAccess": ACCESS_LEVELS.get(self.write_access, self.write_access),
            "usedInHost": self.used_in_host,
            "contentDocsKeys": self.content_docs_keys,
            "fields": [f.to_json() for f in self.fields],
        }


class ESSchemaCatalog:
    """schema GUID -> ESSchemaDef, in map order, + the EStorageTracking table."""

    def __init__(self):
        self.by_guid: dict[str, ESSchemaDef] = {}
        self.order: list[str] = []
        self.map_offset: int = -1          # u32 count offset in Global/Latest
        self.map_count: int = 0            # declared entry count
        self.tracking: dict[str, list[int]] = {}   # schema guid -> element ids
        self.tracking_offset: int = -1
        self.source: str = ""
        self.note: str = ""                # why the catalog is empty, when it is

    def add(self, s: ESSchemaDef):
        if s.guid not in self.by_guid:
            self.order.append(s.guid)
        self.by_guid[s.guid] = s

    def get(self, guid: str) -> Optional[ESSchemaDef]:
        return self.by_guid.get(guid)

    def __len__(self):
        return len(self.by_guid)

    def __iter__(self):
        for g in self.order:
            yield self.by_guid[g]

    def to_json(self) -> dict:
        return {
            "source": self.source,
            "map_offset": self.map_offset,
            "map_count": self.map_count,
            "schemas": [s.to_json() for s in self],
            "tracking": {g: len(v) for g, v in self.tracking.items()},
        }


def _schema_from_pair(v: dict, offset: int = -1) -> ESSchemaDef:
    """Build an ESSchemaDef from a decoded pair<GUIDvalue, SchemaUsageInfo>."""
    su = v["second"]
    sch = su["m_schema"]
    fields = []
    for f in sch["m_fields"]:
        spec = f.get("m_specTypeId") or {}
        fields.append(ESFieldDef(
            name=f["m_fieldName"] or "",
            type_name=f["m_fieldTypeName"] or "",
            documentation=f.get("m_documentation") or "",
            spec_type_id=(spec.get("m_typeId") or "") if isinstance(spec, dict) else "",
            container_type=int(f.get("m_containerType") or 0),
            entry_index=int(f.get("m_entryIndex") or 0),
            sub_schema_guid=f.get("m_subSchemaGUID") or NULL_GUID,
        ))
    fields.sort(key=lambda fd: fd.entry_index)     # serialization order
    return ESSchemaDef(
        guid=sch["m_guid"],
        name=sch["m_schemaName"] or "",
        vendor_id=sch["m_vendorId"] or "",
        application_guid=sch.get("m_applicationGUID") or NULL_GUID,
        documentation=sch.get("m_documentation") or "",
        read_access=int(sch.get("m_readAccessLevel") or 0),
        write_access=int(sch.get("m_writeAccessLevel") or 0),
        fields=fields,
        used_in_host=bool(su.get("m_usedInHost")),
        content_docs_keys=list(su.get("m_contentDocsKeys") or []),
        offset=offset,
        raw=v,
    )


# ---------------------------------------------------------------------------
# Catalog location inside Global/Latest
# ---------------------------------------------------------------------------

_PAIR_CLASS = "std::pair< GUIDvalue, SchemaUsageInfo >"
_MAX_ENTRY = 400_000        # generous bound on one catalog entry's byte size


def _decode_pair_at(dec: ObjectDecoder, gl: bytes, p: int, pair_id: int):
    """Decode one map entry at ``p``; return (end, value) if self-consistent."""
    if p < 0 or p + 26 > len(gl):
        return None
    o = dec.decode_record(pair_id, gl[p:p + _MAX_ENTRY])
    if o.errors:
        return None
    su = o.value.get("second") or {}
    sch = su.get("m_schema") or {}
    if sch.get("m_guid") != guid_str(gl[p:p + 16]):
        return None
    return p + o.consumed, o.value


def _chain_map(dec: ObjectDecoder, gl: bytes, seeds: list[int], pair_id: int):
    """From validated entry offsets, recover the whole contiguous map.

    Forward: the next entry starts where this one ends.  Backward: the
    previous entry's ``ESSchema.m_guid`` sits 25 bytes before this entry's
    start (m_guid(16) + read u32 + write u32 + usedInHost u8) and that same
    GUID begins the previous entry.  Stop when the u32 preceding the first
    entry equals the number of entries recovered (the container count).
    """
    entries: dict[int, tuple[int, dict]] = {}
    for s in sorted(set(seeds)):
        if s in entries:
            continue
        r = _decode_pair_at(dec, gl, s, pair_id)
        if not r:
            continue
        entries[s] = r
        p = r[0]
        while p not in entries:            # forward chain
            r2 = _decode_pair_at(dec, gl, p, pair_id)
            if not r2:
                break
            entries[p] = r2
            p = r2[0]
    if not entries:
        return -1, 0, {}
    # backward chain from the earliest entry until the count field matches
    while True:
        first = min(entries)
        count = struct.unpack_from("<I", gl, first - 4)[0] if first >= 4 else 0
        n = _run_length(entries, first)
        if count == n:
            return first - 4, count, dict((k, entries[k]) for k in _run(entries, first))
        prev_guid = gl[first - 25:first - 9]
        q = gl.find(prev_guid, max(0, first - _MAX_ENTRY), first - 25)
        placed = False
        while q >= 0:
            r = _decode_pair_at(dec, gl, q, pair_id)
            if r and r[0] == first:
                entries[q] = r
                placed = True
                break
            q = gl.find(prev_guid, q + 1, first - 25)
        if not placed:
            # cannot walk further back; return the run we have (count unverified)
            return first - 4, n, dict((k, entries[k]) for k in _run(entries, first))


def _run(entries: dict, start: int) -> list[int]:
    """Contiguous entry offsets starting at ``start``."""
    out, p = [], start
    while p in entries:
        out.append(p)
        p = entries[p][0]
    return out


def _run_length(entries: dict, start: int) -> int:
    return len(_run(entries, start))


# tail of an ESSchema + SchemaUsageInfo: read u32, write u32, usedInHost u8
_TAIL_RE = re.compile(rb"[\x00-\x04]\x00\x00\x00[\x00-\x04]\x00\x00\x00[\x00\x01]", re.S)


def _tail_scan_seeds(dec: ObjectDecoder, gl: bytes, pair_id: int,
                     max_hits: int = 200_000) -> list[int]:
    """GUID-free anchor: find a catalog entry by its distinctive TAIL.

    An entry ends ``... m_vendorId(AString) m_applicationGUID(16) m_guid(16)
    read(u32) write(u32) usedInHost(u8)`` and BEGINS with the same 16 bytes as
    m_guid.  For each candidate tail we require a plausible vendorId AString
    just before the two GUIDs, then locate the map key (first occurrence of
    the m_guid bytes shortly before) and fully validate by decoding.
    """
    seeds: list[int] = []
    n = 0
    for m in _TAIL_RE.finditer(gl):
        n += 1
        if n > max_hits:
            break
        t = m.start()
        if t < 40:
            continue
        g = gl[t - 16:t]
        if g == bytes(16) or len(set(g)) < 4:
            continue
        # vendorId AString ends at t-32 (before m_applicationGUID + m_guid)
        ok = False
        for vlen in range(0, 48):
            off = t - 32 - 2 * vlen - 4
            if off < 0:
                break
            if struct.unpack_from("<I", gl, off)[0] == vlen:
                ok = True
                break
        if not ok:
            continue
        s = gl.find(g, max(0, t - _MAX_ENTRY), t - 16)
        while s >= 0:
            r = _decode_pair_at(dec, gl, s, pair_id)
            if r and r[0] == t + 9:
                seeds.append(s)
                break
            s = gl.find(g, s + 1, t - 16)
        if seeds:
            break               # one validated entry anchors the whole run
    return seeds


def locate_schema_map(gl: bytes, dec: ObjectDecoder,
                      seed_guids: Optional[list[str]] = None):
    """Locate + decode ``ESSchemaStorage.m_schemaUsageMap`` in Global/Latest.

    Seeds are catalog-entry offsets validated by decoding.  With ``seed_guids``
    (schema GUIDs seen in entity tokens) the map-key occurrences of those
    GUIDs seed the chain; otherwise (or in addition, when that finds nothing)
    a GUID-free structural scan finds one entry.  Returns
    ``(count_offset, count, {entry_offset: (end, value)})`` -- ``(-1, 0, {})``
    when no entry can be located or the archive schema lacks the pair class
    (the older ``m_storedSchemas`` layout, #576; :func:`schemas` then names
    the reason in ``cat.note``).
    """
    pair_cd = dec.schema.by_name.get(_PAIR_CLASS)
    if pair_cd is None:
        return -1, 0, {}
    pair_id = pair_cd.type_id
    seeds: list[int] = []
    for g in seed_guids or []:
        raw = guid_bytes(g) if isinstance(g, str) else bytes(g)
        i = gl.find(raw)
        while i >= 0:
            r = _decode_pair_at(dec, gl, i, pair_id)
            if r:
                seeds.append(i)
                break
            i = gl.find(raw, i + 1)
    if not seeds:
        seeds = _tail_scan_seeds(dec, gl, pair_id)
    if not seeds:
        return -1, 0, {}
    return _chain_map(dec, gl, seeds, pair_id)


# -- EStorageTracking (schema GUID -> element id set) -----------------------

def locate_tracking(gl: bytes, guids: list[str]) -> tuple[int, dict[str, list[int]]]:
    """Locate ``EStorageTracking.m_trackingItems`` and read every item.

    Item = GUIDvalue m_schemaGuid + container<ElementId> m_elemIdSet
    (u32 count + count x i64).  Items are contiguous; the u32 preceding the
    first item equals the item count.  Anchored on any known schema GUID
    occurrence that is followed by a plausible id list.
    """
    def item_at(p: int):
        if p + 20 > len(gl):
            return None
        n = struct.unpack_from("<I", gl, p + 16)[0]
        end = p + 20 + 8 * n
        if n > 5_000_000 or end > len(gl):
            return None
        ids = list(struct.unpack_from(f"<{n}q", gl, p + 20)) if n else []
        if any(i < 0 or i >= (1 << 47) for i in ids):
            return None
        return end, guid_str(gl[p:p + 16]), ids

    starts: dict[int, tuple[int, str, list[int]]] = {}
    for g in guids:
        raw = guid_bytes(g)
        i = gl.find(raw)
        while i >= 0:
            if i not in starts:
                r = item_at(i)
                if r is not None:
                    # forward chain
                    starts[i] = r
                    p = r[0]
                    while p not in starts:
                        r2 = item_at(p)
                        if r2 is None:
                            break
                        # a random GUID could false-positive; the count check
                        # below plus catalog membership filters that
                        starts[p] = r2
                        p = r2[0]
            i = gl.find(raw, i + 1)
    if not starts:
        return -1, {}
    # choose the run whose leading u32 count matches its length and whose
    # guids are all catalogued
    known = set(guids)
    best = (-1, {})
    for s in sorted(starts):
        run, p, table = [], s, {}
        while p in starts and starts[p][1] in known:
            run.append(p)
            table[starts[p][1]] = starts[p][2]
            p = starts[p][0]
        if not run:
            continue
        cnt = struct.unpack_from("<I", gl, s - 4)[0] if s >= 4 else -1
        if cnt == len(run) and len(run) >= len(best[1]):
            best = (s - 4, table)
    if best[0] < 0 and starts:
        # unverified count: still return the longest catalogued run
        for s in sorted(starts):
            run, p, table = [], s, {}
            while p in starts and starts[p][1] in known:
                table[starts[p][1]] = starts[p][2]
                run.append(p)
                p = starts[p][0]
            if len(table) > len(best[1]):
                best = (s - 4, table)
    return best


# ---------------------------------------------------------------------------
# Catalog entry point
# ---------------------------------------------------------------------------

def _global_latest_bytes(source) -> tuple[bytes, str]:
    """Inflated Global/Latest of a source: rvt path, Document, or project name."""
    from .container import open_rvt
    path = None
    if isinstance(source, str) and source.lower().endswith(".rvt"):
        path = source
    elif hasattr(source, "source_path") and getattr(source, "source_path", None):
        path = source.source_path
    if path:
        with open_rvt(path) as f:
            return f.concat("Global/Latest"), path
    # corpus project name (extracted/<project>/Global__Latest.gz/*.bin)
    project = source if isinstance(source, str) else getattr(source, "project", None)
    if project:
        gz_dir = os.path.join(ROOT, "extracted", project, "Global__Latest.gz")
        if os.path.isdir(gz_dir):
            parts = []
            for name in sorted(fn for fn in os.listdir(gz_dir) if fn.endswith(".bin")):
                with open(os.path.join(gz_dir, name), "rb") as fh:
                    parts.append(fh.read())
            if parts:
                return b"".join(parts), gz_dir
        sample = os.path.join(ROOT, "samples", f"{project}.rvt")
        if os.path.exists(sample):
            with open_rvt(sample) as f:
                return f.concat("Global/Latest"), sample
    raise ESSchemaError(f"cannot locate Global/Latest for {source!r}")


def harvest_token_guids(seg: bytes, decoder: ObjectDecoder, limit: Optional[int] = None) -> Counter:
    """Schema GUIDs seen in ``ESEntity.m_blob`` tokens of a seq-102 segment.

    Uses the base decoder's error position (the token) so it works before a
    catalog exists.  Returns a Counter of guid string -> record count.
    """
    out: Counter = Counter()
    n = 0
    for r in O.iter_records(seg, 102):
        if r.elem_id < 0:
            continue
        o = decoder.decode_record(r.class_id, r.payload)
        if o.clean or o.stub or not o.errors:
            continue
        e = o.errors[0]
        if "pid=-1 to unknown class" not in e["error"] and "pid=-" not in e["error"]:
            continue
        off = e["offset"] + 4
        if off + 16 <= len(r.payload):
            out[guid_str(bytes(r.payload[off:off + 16]))] += 1
        n += 1
        if limit and n >= limit:
            break
    return out


def schemas(source, decoder: Optional[ObjectDecoder] = None,
            seed_guids: Optional[list[str]] = None,
            with_tracking: bool = True) -> ESSchemaCatalog:
    """The in-model Extensible-Storage schema catalog of a project.

    ``source`` = a ``rvt.mutate.Document`` (uses ``doc.source_path`` /
    ``doc.project`` + its schema decoder), an ``.rvt`` path, or a corpus
    project name.  ``seed_guids`` (entity-token GUIDs) speed up / harden the
    location; without them a GUID-free structural scan anchors the map.
    """
    base = decoder if decoder is not None else _decoder_for(source)
    gl, src = _global_latest_bytes(source)
    cat = ESSchemaCatalog()
    cat.source = src
    count_off, count, entries = locate_schema_map(gl, base, seed_guids)
    cat.map_offset, cat.map_count = count_off, count
    if not entries:
        cat.note = _no_map_reason(base.schema)
    for k in sorted(entries):
        end, v = entries[k]
        try:
            cat.add(_schema_from_pair(v, k))
        except Exception as e:                       # pragma: no cover
            raise ESSchemaError(f"catalog entry @{k:#x}: {e}")
    if with_tracking and len(cat):
        toff, table = locate_tracking(gl, list(cat.by_guid))
        cat.tracking_offset = toff
        cat.tracking = table
    return cat


def _no_map_reason(schema: Schema) -> str:
    """One sentence on why no schema-usage map was read from a file carrying
    ``schema`` -- the catalog is then honestly empty, never guessed."""
    if _PAIR_CLASS in schema.by_name:
        return "no ESSchemaStorage.m_schemaUsageMap entry could be located in Global/Latest"
    ess = schema.by_name.get("ESSchemaStorage")
    kept = ", ".join(f"{f.name} : {f.type_name}" for f in (ess.fields if ess else ())
                     if f.type_name and "ESSchema" in f.type_name) or "no ESSchema map at all"
    return (f"this file's archive schema has no {_PAIR_CLASS!r} -- its ESSchemaStorage "
            f"keeps {kept}, an older catalog layout this module does not read yet, #576")


def _decoder_for(source) -> ObjectDecoder:
    """Archive-schema decoder for a source (file's own Formats/Latest)."""
    from .container import open_rvt
    from .schema import parse as parse_schema
    if isinstance(source, str) and source.lower().endswith(".rvt"):
        with open_rvt(source) as f:
            return ObjectDecoder(parse_schema(f.inflate("Formats/Latest"), source=source))
    if hasattr(source, "dec"):
        return ObjectDecoder(source.dec.schema)
    return ObjectDecoder()


# ---------------------------------------------------------------------------
# Field type system
# ---------------------------------------------------------------------------

# type name -> ("prim", struct fmt) | (special,)
_TYPE_TABLE = {
    "bool": ("bool",),
    "char": ("prim", "<b"), "signed char": ("prim", "<b"),
    "unsigned char": ("prim", "<B"), "byte": ("prim", "<B"),
    "short": ("prim", "<h"), "unsigned short": ("prim", "<H"),
    "int": ("prim", "<i"), "long": ("prim", "<i"),
    "unsigned int": ("prim", "<I"), "unsigned long": ("prim", "<I"),
    "int64": ("prim", "<q"), "__int64": ("prim", "<q"), "int64_t": ("prim", "<q"),
    "float": ("prim", "<f"), "double": ("prim", "<d"),
    "TCHAR": ("string",), "AString": ("string",), "AStringWrapper": ("string",),
    "GUIDvalue": ("guid",), "GUID": ("guid",), "Guid": ("guid",),
    "ElementId": ("elementid",), "Identifier": ("elementid",),
    "XYZ": ("xyz",), "UV": ("uv",),
    "ESEntity": ("entity",),
}

_PAIR_RE = re.compile(r"^std::pair<\s*(.+)\s*>$")


def _split_top_level(s: str) -> list[str]:
    parts, depth, cur = [], 0, []
    for ch in s:
        if ch == "<":
            depth += 1
        elif ch == ">":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
            continue
        cur.append(ch)
    parts.append("".join(cur).strip())
    return parts


def parse_type(type_name: str) -> tuple:
    """ES field type name -> a type descriptor tuple.

    'int' -> ('prim','<i'); 'TCHAR' -> ('string',); 'ESEntity' ->
    ('entity',); 'std::pair< AString, ESEntity >' -> ('pair', kdesc,
    vdesc).  Raises ESSchemaError on an unknown type (loud, not lossy).
    """
    t = (type_name or "").strip()
    m = _PAIR_RE.match(t)
    if m:
        halves = _split_top_level(m.group(1))
        if len(halves) != 2:
            raise ESSchemaError(f"bad pair type {type_name!r}")
        return ("pair", parse_type(halves[0]), parse_type(halves[1]))
    d = _TYPE_TABLE.get(t)
    if d is None:
        raise ESSchemaError(f"unsupported ES field type {type_name!r}")
    return d


# ---------------------------------------------------------------------------
# Entity value model
# ---------------------------------------------------------------------------
# A decoded entity (top-level or nested):
#   {"schema_guid": g, "schema": name, "pid": -1, "fields": {name: value}}
# A null entity: None.  A weak/back reference (never seen for ES): kept as
# {"backref_pid": n} for symmetry with rvt.objects.
# Field values: primitives, str, [x,y,z], list (array), [[k, v], ...] (map),
# nested entity dict / None.  Char arrays -> {"charbytes": "hex"}.


class _ESPend:
    """A queued nested-entity body: fill ``holder[key]`` when reached."""
    __slots__ = ("guid", "holder", "key", "pid", "path")

    def __init__(self, guid: str, holder, key, pid: int, path: str):
        self.guid = guid
        self.holder = holder
        self.key = key
        self.pid = pid
        self.path = path


class EntityCodec:
    """Encodes/decodes entity bodies against a catalog.

    Nested entities are reported to a caller-supplied queue as ``_ESPend``
    (decode) / ``(guid, entity)`` (encode) so the same code serves the
    standalone contiguous form and the record-level interleaved queue.
    """

    def __init__(self, catalog: ESSchemaCatalog):
        self.cat = catalog

    def schema(self, guid: str) -> ESSchemaDef:
        s = self.cat.get(guid)
        if s is None:
            raise ESSchemaError(f"schema {guid} not in the model's catalog")
        return s

    # -- decode ------------------------------------------------------------
    def read_entity_body(self, rd: Reader, guid: str, esq: deque, path: str) -> dict:
        s = self.schema(guid)
        fields: dict = {}
        for f in s.fields:
            key = f.name
            i = 2
            while key in fields:                      # never seen; be safe
                key = f"{f.name}#{i}"
                i += 1
            fields[key] = self._read_field(rd, f, esq, f"{path}.{f.name}")
        return fields

    def _read_field(self, rd: Reader, f: ESFieldDef, esq: deque, path: str):
        desc = parse_type(f.type_name)
        if f.container_type == 1:                  # array
            n = rd.count32(1, f"array count {f.name}")
            if desc == ("prim", "<b") or desc == ("prim", "<B"):
                return {"charbytes": rd.take(n).hex()}
            return [self._read_value(rd, desc, f, esq, f"{path}[{i}]") for i in range(n)]
        if f.container_type == 2:                  # map
            if desc[0] != "pair":
                raise ESSchemaError(f"map field {f.name} has non-pair type {f.type_name!r}")
            n = rd.count32(1, f"map count {f.name}")
            out = []
            for i in range(n):
                k = self._read_value(rd, desc[1], f, esq, f"{path}[{i}].first")
                v = self._read_value(rd, desc[2], f, esq, f"{path}[{i}].second")
                out.append([k, v])
            return out
        return self._read_value(rd, desc, f, esq, path)

    def _read_value(self, rd: Reader, desc: tuple, f: ESFieldDef, esq: deque, path: str):
        kind = desc[0]
        if kind == "prim":
            return rd._unpack(desc[1], struct.calcsize(desc[1]))
        if kind == "bool":
            return rd.bool()
        if kind == "string":
            return rd.astring()
        if kind == "guid":
            return rd.guid()
        if kind == "elementid":
            return rd.element_id()
        if kind == "xyz":
            return rd.xyz()
        if kind == "uv":
            return rd.uv()
        if kind == "entity":
            return self.read_entity_token(rd, esq, path)
        if kind == "pair":                           # inline pair value (rare)
            return [self._read_value(rd, desc[1], f, esq, path + ".first"),
                    self._read_value(rd, desc[2], f, esq, path + ".second")]
        raise ESSchemaError(f"unhandled type {desc!r} at {path}")

    def read_entity_token(self, rd: Reader, esq: deque, path: str):
        """i32 pid; 0 -> null; else 16-byte schema GUID, body deferred (queued)."""
        pid = rd.i32()
        if pid == 0:
            return None
        guid = rd.guid()
        s = self.cat.get(guid)
        holder = {"schema_guid": guid, "schema": s.name if s else None,
                  "pid": pid, "fields": None}
        esq.append(_ESPend(guid, holder, "fields", pid, path))
        return holder

    # -- encode ------------------------------------------------------------
    def write_entity_body(self, w: Writer, ent: dict, esq: deque, path: str):
        guid = ent.get("schema_guid")
        s = self.schema(guid)
        fields = ent.get("fields") or {}
        used: dict = {}
        for f in s.fields:
            key = f.name
            i = 2
            while key in used:
                key = f"{f.name}#{i}"
                i += 1
            used[key] = True
            if key not in fields:
                raise EncodeError(path, f"entity {s.name}: missing field {key!r}")
            self._write_field(w, f, fields[key], esq, f"{path}.{f.name}")

    def _write_field(self, w: Writer, f: ESFieldDef, v, esq: deque, path: str):
        desc = parse_type(f.type_name)
        if f.container_type == 1:
            if desc in (("prim", "<b"), ("prim", "<B")):
                raw = bytes.fromhex(v["charbytes"]) if isinstance(v, dict) else bytes(v)
                w.u32(len(raw))
                w.raw(raw)
                return
            w.u32(len(v))
            for i, x in enumerate(v):
                self._write_value(w, desc, f, x, esq, f"{path}[{i}]")
            return
        if f.container_type == 2:
            w.u32(len(v))
            for i, kv in enumerate(v):
                self._write_value(w, desc[1], f, kv[0], esq, f"{path}[{i}].first")
                self._write_value(w, desc[2], f, kv[1], esq, f"{path}[{i}].second")
            return
        self._write_value(w, desc, f, v, esq, path)

    def _write_value(self, w: Writer, desc: tuple, f: ESFieldDef, v, esq: deque, path: str):
        kind = desc[0]
        if kind == "prim":
            try:
                w.buf += struct.pack(desc[1], v)
            except struct.error as e:
                raise EncodeError(path, f"{f.name}: {e}")
            return
        if kind == "bool":
            w.bool(v)
            return
        if kind == "string":
            w.astring(v)
            return
        if kind == "guid":
            w.guid(v)
            return
        if kind == "elementid":
            w.element_id(v)
            return
        if kind == "xyz":
            w.xyz(v)
            return
        if kind == "uv":
            w.uv(v)
            return
        if kind == "entity":
            self.write_entity_token(w, v, esq, path)
            return
        if kind == "pair":
            self._write_value(w, desc[1], f, v[0], esq, path + ".first")
            self._write_value(w, desc[2], f, v[1], esq, path + ".second")
            return
        raise ESSchemaError(f"unhandled type {desc!r} at {path}")

    def write_entity_token(self, w: Writer, v, esq: deque, path: str):
        if v is None:
            w.i32(0)
            return
        if isinstance(v, dict) and "backref_pid" in v:
            w.i32(v["backref_pid"])
            return
        if not isinstance(v, dict) or "schema_guid" not in v:
            raise EncodeError(path, f"bad ES entity token {v!r}")
        w.i32(v.get("pid", -1))
        w.guid(v["schema_guid"])
        esq.append((v["schema_guid"], v))


# ---------------------------------------------------------------------------
# Pure-function blob codec (entity + its nested closure, contiguous BFS)
# ---------------------------------------------------------------------------

def decode_entity_blob(blob: bytes, catalog: ESSchemaCatalog, guid: str,
                       schema_name: Optional[str] = None) -> dict:
    """Decode one entity body (given its schema GUID) to a structured dict.

    ``blob`` is the entity's body bytes; when the entity nests further
    entities their bodies must follow contiguously in breadth-first order
    (exactly how an entity closure is laid out when it sits at the end of a
    record's deferred queue).  Returns the entity dict with ``consumed``
    (bytes read, target ``len(blob)``) and ``errors`` (empty when clean).
    """
    codec = EntityCodec(catalog)
    rd = Reader(blob)
    esq: deque = deque()
    s = catalog.get(guid)
    ent = {"schema_guid": guid, "schema": s.name if s else schema_name,
           "pid": -1, "fields": None}
    errors: list = []
    try:
        ent["fields"] = codec.read_entity_body(rd, guid, esq, s.name if s else guid)
        while esq:                                  # nested bodies, BFS
            pend = esq.popleft()
            pend.holder[pend.key] = codec.read_entity_body(rd, pend.guid, esq, pend.path)
    except (DecodeError, ESSchemaError) as e:
        off = e.offset if isinstance(e, DecodeError) else rd.p
        errors.append({"offset": off, "error": str(e)})
    except (struct.error, IndexError) as e:
        errors.append({"offset": rd.p, "error": f"truncated: {e}"})
    ent["consumed"] = rd.p
    ent["total"] = len(blob)
    ent["errors"] = errors
    return ent


def encode_entity_blob(entity: dict, catalog: ESSchemaCatalog) -> bytes:
    """Byte-exact inverse of :func:`decode_entity_blob` (parent body then
    the nested bodies breadth-first)."""
    codec = EntityCodec(catalog)
    w = Writer()
    esq: deque = deque()
    codec.write_entity_body(w, entity, esq, entity.get("schema") or "<entity>")
    while esq:
        g, sub = esq.popleft()
        codec.write_entity_body(w, sub, esq, f"{sub.get('schema') or g}")
    return w.bytes()


# ---------------------------------------------------------------------------
# Record-level integration: ESDecoder / ESEncoder
# ---------------------------------------------------------------------------

class ESDecoder(ObjectDecoder):
    """``ObjectDecoder`` + Extensible-Storage entities.

    Identical to the archive decoder except that decoding the ``ESEntity``
    class reads the ``m_blob`` token as ``i32 pid`` [+ 16-byte schema GUID]
    and queues the entity body into the SAME breadth-first deferred queue,
    where it is decoded against the in-model catalog when reached (nested
    entities recurse through that same queue).  This is the exact behaviour
    the objects.py integration diff installs natively.
    """

    def __init__(self, schema: Optional[Schema] = None,
                 catalog: Optional[ESSchemaCatalog] = None):
        super().__init__(schema)
        self.catalog = catalog if catalog is not None else ESSchemaCatalog()
        self.codec = EntityCodec(self.catalog)
        cd = self.schema.by_name.get("ESEntity")
        self.id_ESEntity = cd.type_id if cd else None

    # -- token: intercept the ESEntity class body ------------------------------
    def _decode_class(self, rd: Reader, class_id: int, queue: deque, state: _State,
                      path: str) -> dict:
        if class_id == self.id_ESEntity and self.id_ESEntity is not None:
            state.path = path + ".m_blob"
            return {"m_blob": self.codec.read_entity_token(rd, queue, path + ".m_blob")}
        return super()._decode_class(rd, class_id, queue, state, path)

    # -- deferred queue: also serve queued entity bodies ----------------------
    def decode_record(self, class_id: int, payload: bytes) -> DecodedObject:
        name = self.class_name(class_id)
        obj = DecodedObject(class_id, name, {}, 0, len(payload))
        rd = Reader(payload)
        state = _State(seen_pids={1, 2})
        queue: deque = deque()
        try:
            if class_id not in self.schema.by_id:
                raise DecodeError(0, f"unknown class id {class_id:#x}")
            obj.value = self._decode_class(rd, class_id, queue, state, name)
            while queue:
                pend = queue.popleft()
                obj.n_deferred += 1
                if isinstance(pend, _ESPend):
                    state.path = pend.path
                    if self.catalog.get(pend.guid) is None:
                        raise DecodeError(rd.p, f"ES entity of unknown schema {pend.guid}")
                    pend.holder[pend.key] = self.codec.read_entity_body(
                        rd, pend.guid, queue, f"{pend.path}~>{self.catalog.get(pend.guid).name}")
                    continue
                cname = self.class_name(pend.class_id)
                sub = self._decode_class(rd, pend.class_id, queue, state,
                                         f"{pend.path}->{cname}")
                pend.holder[pend.key] = sub
        except DecodeError as e:
            obj.errors.append({"field": state.path, "offset": e.offset, "error": e.msg})
        except ESSchemaError as e:
            obj.errors.append({"field": state.path, "offset": rd.p, "error": str(e)})
        except (struct.error, IndexError) as e:
            obj.errors.append({"field": state.path, "offset": rd.p, "error": f"truncated: {e}"})
        obj.consumed = rd.p
        if not obj.errors and obj.consumed < obj.total and obj.total <= 4 \
                and not any(payload[obj.consumed:]):
            obj.stub = True
        return obj


class ESEncoder(ObjectEncoder):
    """``ObjectEncoder`` + Extensible-Storage entities (mirror of ESDecoder)."""

    def __init__(self, decoder: Optional[ESDecoder] = None,
                 schema: Optional[Schema] = None,
                 catalog: Optional[ESSchemaCatalog] = None):
        if decoder is None:
            decoder = ESDecoder(schema, catalog)
        super().__init__(decoder=decoder)
        self.esdec = decoder
        self.codec = decoder.codec

    def _encode_class(self, w: Writer, class_id: int, value: dict, queue: deque, path: str):
        if class_id == self.esdec.id_ESEntity:
            self.codec.write_entity_token(w, (value or {}).get("m_blob"), queue,
                                          path + ".m_blob")
            return
        super()._encode_class(w, class_id, value, queue, path)

    def encode_object(self, class_id: int, value: dict) -> bytes:
        if class_id not in self.schema.by_id:
            raise EncodeError("<root>", f"unknown class id {class_id:#x}")
        w = Writer()
        queue: deque = deque()
        root_name = self.dec.class_name(class_id)
        self._encode_class(w, class_id, value or {}, queue, root_name)
        while queue:
            pend = queue.popleft()
            if isinstance(pend, tuple):                # (guid, entity) ES pending
                g, ent = pend
                self.codec.write_entity_body(w, ent, queue, ent.get("schema") or g)
                continue
            self._encode_class(w, pend.class_id, pend.value or {}, queue,
                               f"{pend.path}->{self.dec.class_name(pend.class_id)}")
        return w.bytes()


def make_es_decoder(doc, catalog: Optional[ESSchemaCatalog] = None) -> ESDecoder:
    """An ESDecoder for a ``rvt.mutate.Document`` (its schema + catalog)."""
    cat = catalog if catalog is not None else schemas(doc)
    return ESDecoder(doc.dec.schema, cat)


# ---------------------------------------------------------------------------
# Reports / corpus proof
# ---------------------------------------------------------------------------

def entities_in(value, out: Optional[list] = None) -> list:
    """All entity dicts (top-level and nested) inside a decoded value tree."""
    if out is None:
        out = []
    if isinstance(value, dict):
        if "schema_guid" in value and "fields" in value:
            out.append(value)
            entities_in(value.get("fields"), out)
        else:
            for x in value.values():
                entities_in(x, out)
    elif isinstance(value, list):
        for x in value:
            entities_in(x, out)
    return out


def es_report(doc, catalog: Optional[ESSchemaCatalog] = None,
              walk: bool = False, decoder: Optional[ESDecoder] = None) -> dict:
    """Which schemas exist and which elements carry entities of each.

    Element ids come from Autodesk's own ``EStorageTracking`` registry (fast,
    authoritative).  With ``walk=True`` every seq-102 record is decoded with
    the ES decoder as well, adding per-schema class breakdowns and the
    host/embedded split (and cross-checking the tracking table).
    """
    cat = catalog if catalog is not None else schemas(doc)
    dec = decoder or ESDecoder(doc.dec.schema, cat)
    rep: dict = {
        "project": getattr(doc, "project", ""),
        "schema_count": len(cat),
        "map_offset": cat.map_offset,
        "tracking_offset": cat.tracking_offset,
        "schemas": [],
    }
    walked: dict = defaultdict(lambda: {"classes": Counter(), "ids": [], "embedded": 0,
                                        "nested": Counter()})
    if walk:
        for r in O.iter_records(doc.seg[102], 102):
            if r.elem_id < 0:
                continue
            o = dec.decode_record(r.class_id, r.payload)
            ents = entities_in(o.value)
            if not ents:
                continue
            host = doc.in_host_document(r.elem_id) if hasattr(doc, "in_host_document") \
                else r.elem_id in getattr(doc, "et_by_id", {})
            top = _top_level_entities(o.value)
            for e in top:
                w = walked[e.get("schema_guid")]
                w["classes"][dec.class_name(r.class_id)] += 1
                if host:
                    w["ids"].append(r.elem_id)
                else:
                    w["embedded"] += 1
            for e in ents:
                if e not in top:
                    walked[e.get("schema_guid")]["nested"]["nested"] += 1
    for s in cat:
        entry = {
            "guid": s.guid, "name": s.name, "vendor": s.vendor_id,
            "usedInHost": s.used_in_host, "fields": len(s.fields),
            "element_ids": cat.tracking.get(s.guid, []),
        }
        if walk:
            w = walked.get(s.guid)
            if w:
                entry["walk"] = {
                    "host_element_ids": sorted(set(w["ids"])),
                    "host_count": len(set(w["ids"])),
                    "embedded_records": w["embedded"],
                    "classes": dict(w["classes"]),
                    "nested_entity_count": w["nested"].get("nested", 0),
                }
        rep["schemas"].append(entry)
    if walk:
        unknown = set(walked) - {s.guid for s in cat}
        if unknown:
            rep["uncatalogued_guids"] = sorted(unknown)
    return rep


def _top_level_entities(value) -> list:
    """Entities held by archive objects (an ``m_blob``), i.e. NOT nested
    inside another entity's ``fields``."""
    out: list = []
    _walk_top(value, out)
    return out


def _walk_top(v, out):
    if isinstance(v, dict):
        if "schema_guid" in v and "fields" in v:      # an entity: stop here
            out.append(v)
            return
        for x in v.values():
            _walk_top(x, out)
    elif isinstance(v, list):
        for x in v:
            _walk_top(x, out)


@dataclass
class VerifyResult:
    project: str
    schemas: int
    records_examined: int = 0
    records_with_entities: int = 0
    entities: int = 0
    decode_clean: int = 0
    roundtrip_exact: int = 0
    decode_failures: list = dc_field(default_factory=list)
    roundtrip_failures: list = dc_field(default_factory=list)
    by_schema: dict = dc_field(default_factory=dict)
    by_class: dict = dc_field(default_factory=dict)
    seconds: float = 0.0

    @property
    def undecodable(self) -> int:
        return self.records_examined - self.decode_clean

    def to_json(self) -> dict:
        return {
            "project": self.project, "schemas": self.schemas,
            "records_examined": self.records_examined,
            "records_with_entities": self.records_with_entities,
            "entities": self.entities,
            "decode_clean": self.decode_clean,
            "undecodable": self.undecodable,
            "roundtrip_exact": self.roundtrip_exact,
            "by_schema": self.by_schema, "by_class": self.by_class,
            "decode_failures": self.decode_failures[:20],
            "roundtrip_failures": self.roundtrip_failures[:20],
            "seconds": round(self.seconds, 1),
        }


def verify_document(doc, catalog: Optional[ESSchemaCatalog] = None,
                    ids: Optional[list[int]] = None,
                    limit: Optional[int] = None,
                    max_failure_samples: int = 12) -> VerifyResult:
    """Corpus proof: every ES-bearing seq-102 record decodes 100 % AND
    re-encodes byte-exact through ESEncoder.

    Records are selected by ``ids``, else = every record whose payload
    contains a catalog schema GUID (a strict superset of the entity-bearing
    records; false positives merely also round-trip cleanly).
    """
    import time
    t0 = time.time()
    cat = catalog if catalog is not None else schemas(doc)
    dec = ESDecoder(doc.dec.schema, cat)
    enc = ESEncoder(dec)
    res = VerifyResult(project=getattr(doc, "project", ""), schemas=len(cat))
    guid_bytes_list = [guid_bytes(g) for g in cat.by_guid]
    id_es = dec.id_ESEntity
    seg = doc.seg[102]
    by_schema: Counter = Counter()
    by_class: Counter = Counter()
    n = 0
    for r in O.iter_records(seg, 102):
        if r.elem_id < 0:
            continue
        if ids is not None:
            if r.elem_id not in ids:
                continue
        else:
            pay = r.payload
            if not any(g in pay for g in guid_bytes_list):
                continue
        n += 1
        res.records_examined += 1
        o = dec.decode_record(r.class_id, r.payload)
        ents = entities_in(o.value)
        cname = dec.class_name(r.class_id)
        if ents:
            res.records_with_entities += 1
            res.entities += len(ents)
            for e in ents:
                by_schema[e.get("schema_guid")] += 1
            by_class[cname] += 1
        if o.errors or (not o.clean and not o.stub):
            if len(res.decode_failures) < max_failure_samples:
                res.decode_failures.append({
                    "elem_id": r.elem_id, "class": cname,
                    "consumed": o.consumed, "total": o.total,
                    "errors": o.errors[:2],
                })
            continue
        res.decode_clean += 1
        rec = enc.encode_record(102, r.elem_id, r.stamp, r.class_id, o.value)
        hlen = 16
        orig = seg[r.seg_offset: r.seg_offset + hlen + r.body_size + 4]
        if rec == orig:
            res.roundtrip_exact += 1
        else:
            if len(res.roundtrip_failures) < max_failure_samples:
                div = _first_divergence(rec, orig)
                res.roundtrip_failures.append({
                    "elem_id": r.elem_id, "class": cname, "diverge_at": div,
                    "orig_len": len(orig), "reenc_len": len(rec),
                    "orig": orig[max(0, div - 8): div + 16].hex(" "),
                    "reenc": rec[max(0, div - 8): div + 16].hex(" "),
                })
        if limit and n >= limit:
            break
    res.by_schema = dict(by_schema)
    res.by_class = dict(by_class)
    res.seconds = time.time() - t0
    return res


def _first_divergence(a: bytes, b: bytes) -> int:
    n = min(len(a), len(b))
    for i in range(n):
        if a[i] != b[i]:
            return i
    return n


def collect_entity_closures(doc, catalog: Optional[ESSchemaCatalog] = None,
                             ids: Optional[list[int]] = None,
                             limit: Optional[int] = None) -> list[dict]:
    """Contiguous entity closures -- the byte strings
    :func:`decode_entity_blob` / :func:`encode_entity_blob` operate on.

    An entity with NO nested entities has a contiguous closure (its body
    span) wherever it sits in the queue.  An entity WITH nested entities has
    a contiguous closure only when its body starts with an otherwise empty
    queue (everything after it, to the record end, is its own descendants).
    Returns [{elem_id, class, schema_guid, schema, offset, blob, nested}].
    """
    cat = catalog if catalog is not None else schemas(doc)
    dec = ESDecoder(doc.dec.schema, cat)
    gbs = [guid_bytes(g) for g in cat.by_guid]
    out: list = []
    seg = doc.seg[102]
    for r in O.iter_records(seg, 102):
        if r.elem_id < 0:
            continue
        if ids is not None and r.elem_id not in ids:
            continue
        if not any(g in r.payload for g in gbs):
            continue
        for start, end, guid, nested in _entity_closures(dec, r):
            out.append({
                "elem_id": r.elem_id, "class": dec.class_name(r.class_id),
                "schema_guid": guid,
                "schema": cat.get(guid).name if cat.get(guid) else None,
                "offset": start, "blob": bytes(r.payload[start:end]),
                "nested": nested,
            })
            if limit and len(out) >= limit:
                return out
    return out


def _entity_closures(dec: ESDecoder, r) -> list[tuple]:
    """(start, end, guid, nested_count) for every top-level entity of the
    record whose closure is contiguous (see :func:`collect_entity_closures`)."""
    name = dec.class_name(r.class_id)
    rd = Reader(r.payload)
    state = _State(seen_pids={1, 2})
    queue: deque = deque()
    spans: list = []
    tail: Optional[tuple] = None      # (start, guid) of an entity whose descendants follow
    top_pendings: set = set()
    try:
        val = dec._decode_class(rd, r.class_id, queue, state, name)
        # every _ESPend queued so far is top-level (archive-held m_blob)
        top_pendings = {id(p) for p in queue if isinstance(p, _ESPend)}
        while queue:
            pend = queue.popleft()
            if isinstance(pend, _ESPend):
                is_top = id(pend) in top_pendings
                start = rd.p
                queue_was_empty = not queue
                before = len(queue)
                pend.holder[pend.key] = dec.codec.read_entity_body(
                    rd, pend.guid, queue, pend.path)
                nested_now = len(queue) - before
                if is_top:
                    if nested_now == 0:
                        spans.append((start, rd.p, pend.guid, 0))
                    elif queue_was_empty and tail is None:
                        tail = (start, pend.guid)
                continue
            # a top-level ES pending queued LATER (e.g. from another cell) is
            # also top-level: refresh the set from the current queue
            sub = dec._decode_class(rd, pend.class_id, queue, state,
                                    f"{pend.path}->{dec.class_name(pend.class_id)}")
            pend.holder[pend.key] = sub
            top_pendings |= {id(p) for p in queue if isinstance(p, _ESPend)}
            tail = None
    except (DecodeError, ESSchemaError, struct.error, IndexError):
        return spans
    if tail is not None and rd.p == len(r.payload):
        start, guid = tail
        spans.append((start, rd.p, guid, 1))
    return spans


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _doc_path(arg: str) -> Optional[str]:
    """The .rvt path ``arg`` names (a path, or a corpus sample by project
    name); None when it names an extracted corpus project instead."""
    if arg.lower().endswith(".rvt") or os.path.sep in arg:
        return arg
    sample = os.path.join(ROOT, "samples", f"{arg}.rvt")
    return sample if os.path.exists(sample) else None


def print_catalog(cat: ESSchemaCatalog, stream=None):
    P = lambda *a: print(*a, file=stream)       # None = sys.stdout at CALL time (a captured/redirected stdout counts)
    if not len(cat) and cat.note:
        P(f"ES schema catalog: 0 schemas ({cat.note})")
        return
    P(f"ES schema catalog: {len(cat)} schemas (map count {cat.map_count} "
      f"@{cat.map_offset:#x} in Global/Latest; tracking @{cat.tracking_offset:#x})")
    for s in cat:
        ids = cat.tracking.get(s.guid)
        used = "used" if s.used_in_host else "unused"
        P(f"  {s.guid}  {s.name!r} vendor={s.vendor_id!r} {used} "
          f"fields={len(s.fields)} read={ACCESS_LEVELS.get(s.read_access, s.read_access)} "
          f"write={ACCESS_LEVELS.get(s.write_access, s.write_access)}"
          + (f" tracked_elements={len(ids)}" if ids else "")
          + (f" contentDocs={len(s.content_docs_keys)}" if s.content_docs_keys else ""))
        for f in s.fields:
            ct = {0: "", 1: "[]", 2: "{}"}.get(f.container_type, f"<c{f.container_type}>")
            sub = "" if f.is_null_sub else f" -> {f.sub_schema_guid}"
            spec = f" ({f.spec_type_id})" if f.spec_type_id else ""
            doc_s = f'  "{f.documentation}"' if f.documentation else ""
            P(f"      [{f.entry_index:2d}] {f.name}: {f.type_name}{ct}{sub}{spec}{doc_s}")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    flags = {a for a in argv if a.startswith("--")}
    args = [a for a in argv if not a.startswith("--")]
    target = args[0] if args else "rmebasicsampleproject"
    path = _doc_path(target)                     # None: an extracted corpus project, loaded as it always was
    if path is not None and not os.path.exists(path):
        print(f"ERROR: no such file: {path}", file=sys.stderr)
        return 2
    from .container import open_rvt
    from .mutate import Document
    from .native_framing import enter_files_release
    with contextlib.ExitStack() as stack:
        try:
            if path is not None:
                # read under the FILE's own release: opened once for the probe, a
                # native file enters nothing (no ladder imported); a foreign one
                # climbs the instrument ladder once -- a note, never a raise
                with open_rvt(path) as f:
                    note = enter_files_release(stack, f, path)
                if note:
                    print(f"warning: {note}", file=sys.stderr)
                doc = Document.from_file(path)
            else:
                doc = Document.load(target)
        except Exception as e:  # noqa: BLE001 -- a file that cannot be opened or loaded IS the verdict, not a crash
            print(f"ERROR: cannot load {target}: {type(e).__name__}: {e}", file=sys.stderr)
            return 1
        return _report(doc, target, flags)


def _report(doc, target: str, flags: set) -> int:
    """Print the catalog and the ``--report`` / ``--walk`` / ``--roundtrip``
    sections for a loaded ``doc``, under whatever release is in force."""
    print(f"loaded {getattr(doc, 'project', target)}: {len(doc.et_by_id)} host elements")
    cat = schemas(doc)
    print_catalog(cat)
    if "--report" in flags or not flags:
        rep = es_report(doc, cat, walk="--walk" in flags)
        print(f"\nES report: {rep['schema_count']} schemas")
        for s in rep["schemas"]:
            ids = s["element_ids"]
            extra = ""
            if "walk" in s:
                w = s["walk"]
                extra = (f" | walk: host {w['host_count']}, embedded {w['embedded_records']}, "
                         f"nested {w['nested_entity_count']}, classes {w['classes']}")
            if ids or "walk" in s:
                P = f"  {s['name']!r} {s['guid']}: tracked elements {len(ids)}"
                if ids:
                    P += f" (first {ids[:5]})"
                print(P + extra)
    if "--roundtrip" in flags:
        res = verify_document(doc, cat)
        j = res.to_json()
        print(f"\nround-trip: examined {j['records_examined']} records, "
              f"{j['records_with_entities']} with entities ({j['entities']} entities), "
              f"clean {j['decode_clean']}, undecodable {j['undecodable']}, "
              f"byte-exact re-encode {j['roundtrip_exact']} in {j['seconds']}s")
        print(f"  by schema: {j['by_schema']}")
        print(f"  by class:  {j['by_class']}")
        for fk in j["decode_failures"]:
            print(f"  DECODE FAIL {fk}")
        for fk in j["roundtrip_failures"]:
            print(f"  ROUNDTRIP FAIL {fk}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

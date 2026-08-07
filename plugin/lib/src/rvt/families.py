"""Family (embedded content-document) reconnaissance for the .rvt writer.

An ``.rvt`` project embeds one **family document** per loaded family as its
own **save unit** inside ``Partitions/<N>`` (unit 0 = the host project; units
1..k = the embedded documents, each opened by a 28-byte separator carrying
the document's GUID + record count).  This module makes those documents
addressable and dumpable:

    idx = FamilyIndex.open("samples/rmebasicsampleproject.rvt")
    for fam in family_documents(idx):        # one row per host Family element
        print(fam["family_id"], fam["family_name"], fam["unit"], fam["n_types"])
    d = dump_family(idx, unit=fam["unit"])  # structured JSON of that unit

Verified linkage (rme, 147/159 host families resolve; the rest are system
families with no embedded document):

* host ``Family`` (seq-102 class ``Family``) carries
  ``m_oFamDoc -> FamilyDocument{ m_contentDocGUID, m_big2SmallMap2 }``.
  ``m_contentDocGUID`` **==** the GUID in a ``Partitions/N`` unit separator
  **==** the key of the corresponding ``Global/ContentDocuments`` entry.
  ``m_big2SmallMap2`` maps HOST element ids (categories, styles, params the
  family uses; the family's own params) -> the EMBEDDED document's element ids.
* the embedded document is a complete little Revit document: its own
  ``Family`` element ("self" family, all-zero ``m_famDocGUID``; every family
  editor element's ``m_famId`` points at it), its own ``Level``
  ("Ref. Level"), CategoryElem/GStyleElem copies, views, sketches
  (``VarSketch`` + ``CurveElem`` profile lines on a ``SketchPlane``),
  ``RefPlane``s, solid forms (``ExtrusionElem`` etc. -- each carrying a real
  ``GElement`` solid in seq 103), family parameters (``ParamElemFamily``),
  the family's types (``FamilySymbol`` + ``FamSymSurrogate``), and MEP
  ``ConnectorElem``s.  Nested families are further units.
* the ``Global/ContentDocuments`` entry for a GUID = that embedded document's
  serialized ``ADocument`` + its inline 40-byte element table
  (``table_count`` == the unit's record count); the ``element_id`` after tag
  0x0ae9 = the embedded document's own self-``Family`` element id.
* an ``.rfa`` on disk is the SAME CFB container + the SAME ``Formats/Latest``
  schema (byte-identical 496,597 bytes) + a ``PartAtom`` stream + a single
  ``Partitions/N`` whose ONE save unit (unit 0) is the family document itself.
  => the existing native writer chain can emit ``.rfa`` files unchanged.

Run ``python -m rvt.families`` to (re)build the inventories under
``experiments/families/``.
"""
from __future__ import annotations

import collections
import json
import os
import struct
import sys
import uuid
from dataclasses import dataclass, field as dc_field
from typing import Any, Iterable, Optional

from .container import open_rvt
from .objects import ObjectDecoder, Record, iter_records
from .partitions import StreamWalker
from .schema import parse as parse_schema

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", ".."))
SAMPLES_DIR = os.path.join(_ROOT, "samples")

#: built-in category ids of interest (host Family.m_categoryId)
OST_LightingFixtures = -2001120
OST_ElectricalEquipment = -2001040
OST_ElectricalFixtures = -2001060

#: family-editor element classes whose decoded objects are dumped in full
DETAIL_CLASSES = (
    "Family", "FamilySymbol", "FamSymSurrogate", "FamilySurrogate",
    "ParamElemFamily", "ExtrusionElem", "SweepElem", "BlendElem",
    "RevolveElem", "SweptBlendElem", "FamilyGeomCombination", "VarSketch",
    "CurveElem", "RefPlane", "SketchPlane", "ConnectorElem", "Level",
    "ImposterLight", "LightSourceElem",
    "ParamElemElectricalLoadClassification", "MaterialElem",
)

#: solid-form classes (family editor "forms")
FORM_CLASSES = ("ExtrusionElem", "SweepElem", "BlendElem", "RevolveElem",
                "SweptBlendElem", "FreeFormElement", "GenericForm")


# ---------------------------------------------------------------------------
# index over one file
# ---------------------------------------------------------------------------

@dataclass
class UnitInfo:
    index: int
    guid: Optional[str]
    counter: Optional[int]
    n_blocks: int
    first_block: int


class FamilyIndex:
    """Walks a project's partition stream(s) once and exposes per-unit
    element records plus the host-document (unit 0) index."""

    def __init__(self, path: str):
        self.path = path
        self.name = os.path.splitext(os.path.basename(path))[0]
        self.units: list[UnitInfo] = []
        self._walkers: list[tuple[str, StreamWalker]] = []
        self._unit_ref: list[tuple[int, int]] = []       # (walker idx, unit idx)
        self._unit_recs: dict[int, dict[int, dict[int, Record]]] = {}
        with open_rvt(path) as f:
            self.schema = parse_schema(f.inflate("Formats/Latest"), source=path)
            for pn in f.partition_streams():
                w = StreamWalker(f.logical(pn), inflate=True, keep_data=True)
                wi = len(self._walkers)
                self._walkers.append((pn, w))
                for u in w.units:
                    gi = len(self.units)
                    g = str(uuid.UUID(bytes_le=u.guid)) if u.guid else None
                    self.units.append(UnitInfo(gi, g, u.counter, u.n_blocks,
                                               u.first_block))
                    self._unit_ref.append((wi, u.index))
        self.dec = ObjectDecoder(self.schema)
        self.unit_by_guid = {u.guid: u.index for u in self.units if u.guid}
        self._decoded: dict[tuple[int, int, int], Any] = {}

    # -- construction --------------------------------------------------
    @classmethod
    def open(cls, path_or_project: str) -> "FamilyIndex":
        p = path_or_project
        if not os.path.exists(p):
            cand = os.path.join(SAMPLES_DIR, f"{p}.rvt")
            if os.path.exists(cand):
                p = cand
        return cls(p)

    # -- unit records ------------------------------------------------------
    def unit_records(self, unit: int) -> dict[int, dict[int, Record]]:
        """{seq: {element_id: Record}} for one save unit (0 = host document)."""
        if unit not in self._unit_recs:
            wi, ui = self._unit_ref[unit]
            _pn, w = self._walkers[wi]
            u = w.units[ui]
            blocks = w.blocks[u.first_block:u.first_block + u.n_blocks]
            segs: dict[int, bytearray] = {}
            for b in blocks:
                segs.setdefault(b.seq, bytearray()).extend(b.data or b"")
            out: dict[int, dict[int, Record]] = {}
            for seq, buf in segs.items():
                out[seq] = {r.elem_id: r for r in iter_records(bytes(buf), seq)
                            if r.elem_id >= 0}
            self._unit_recs[unit] = out
        return self._unit_recs[unit]

    def class_name(self, class_id: int) -> str:
        return self.dec.class_name(class_id)

    def decode(self, unit: int, eid: int, seq: int = 102):
        key = (unit, eid, seq)
        if key not in self._decoded:
            r = self.unit_records(unit).get(seq, {}).get(eid)
            self._decoded[key] = (self.dec.decode_record(r.class_id, r.payload)
                                  if r else None)
        return self._decoded[key]

    def value(self, unit: int, eid: int, seq: int = 102) -> Optional[dict]:
        o = self.decode(unit, eid, seq)
        return o.value if o else None

    def ids_of_class(self, unit: int, name: str) -> list[int]:
        cd = self.schema.by_name.get(name)
        if cd is None:
            return []
        return [i for i, r in self.unit_records(unit).get(102, {}).items()
                if r.class_id == cd.type_id]

    def class_histogram(self, unit: int, seq: int = 102) -> dict[str, int]:
        c = collections.Counter(self.class_name(r.class_id)
                                for r in self.unit_records(unit).get(seq, {}).values())
        return dict(c.most_common())

    def decode_stats(self, unit: int, seq: int = 102) -> dict:
        """Decode every record of a unit's seq; report clean/error counts."""
        recs = self.unit_records(unit).get(seq, {})
        clean = 0
        errors: dict[str, int] = collections.Counter()
        for eid, r in recs.items():
            o = self.dec.decode_record(r.class_id, r.payload)
            if o.clean:
                clean += 1
            else:
                errors[self.class_name(r.class_id)] += 1
        return {"records": len(recs), "clean": clean,
                "error_classes": dict(errors)}


def _index(doc) -> FamilyIndex:
    """Resolve a path / project name / mutate.Document / FamilyIndex."""
    if isinstance(doc, FamilyIndex):
        return doc
    if isinstance(doc, str):
        return FamilyIndex.open(doc)
    src = getattr(doc, "source_path", None) or getattr(doc, "project", None)
    if src:
        return FamilyIndex.open(src)
    raise TypeError(f"cannot build a FamilyIndex from {doc!r}")


# ---------------------------------------------------------------------------
# public API
# ---------------------------------------------------------------------------

def family_documents(doc) -> list[dict]:
    """Enumerate the embedded family documents of a project.

    Returns one dict per HOST ``Family`` element:
      family_id, family_name, category, content_doc_guid, fam_doc_guid,
      unit (partition save-unit index or None), unit_counter,
      n_records (seq-102 records in the unit), n_types (host FamilySymbols
      whose m_familyId == family_id), symbol_ids, in_place, work_plane_based,
      classes_histogram (seq-102 class -> count for the unit),
      geometry (form classes present: ExtrusionElem/SweepElem/...),
      n_connectors, n_family_params, n_ref_planes, n_nested_families,
      big2small_count (host->embedded id map size).
    Families with unit == None are system families (no embedded document).
    """
    idx = _index(doc)
    host = idx.unit_records(0)
    fam_cd = idx.schema.by_name["Family"]
    sym_cd = idx.schema.by_name["FamilySymbol"]
    # host FamilySymbols grouped by family
    syms_by_fam: dict[int, list[dict]] = collections.defaultdict(list)
    for eid, r in host.get(102, {}).items():
        if r.class_id != sym_cd.type_id:
            continue
        v = idx.value(0, eid) or {}
        fid = v.get("m_familyId")
        name = ((v.get("m_symbolInfo") or {}).get("value") or {}).get("m_name")
        syms_by_fam[fid].append({"symbol_id": eid, "name": name})
    out = []
    for eid, r in host.get(102, {}).items():
        if r.class_id != fam_cd.type_id:
            continue
        v = idx.value(0, eid) or {}
        fd = (v.get("m_oFamDoc") or {}).get("value") or {}
        cdguid = fd.get("m_contentDocGUID")
        unit = idx.unit_by_guid.get(cdguid)
        row = {
            "family_id": eid,
            "family_name": v.get("m_name"),
            "category": v.get("m_categoryId"),
            "content_doc_guid": cdguid,
            "fam_doc_guid": v.get("m_famDocGUID"),
            "in_place": v.get("m_inPlace"),
            "work_plane_based": v.get("m_isWorkPlaneBased"),
            "part_type": v.get("m_partType"),
            "big2small_count": len(fd.get("m_big2SmallMap2") or []),
            "unit": unit,
            "n_types": len(syms_by_fam.get(eid, [])),
            "symbols": syms_by_fam.get(eid, []),
        }
        if unit is not None:
            hist = idx.class_histogram(unit)
            u = idx.units[unit]
            row.update({
                "unit_counter": u.counter,
                "n_records": sum(hist.values()),
                "classes_histogram": hist,
                "geometry": {k: n for k, n in hist.items() if k in FORM_CLASSES},
                "n_connectors": hist.get("ConnectorElem", 0),
                "n_family_params": hist.get("ParamElemFamily", 0),
                "n_ref_planes": hist.get("RefPlane", 0),
                "n_types_in_doc": hist.get("FamilySymbol", 0),
                "n_nested_families": max(hist.get("Family", 0) - 1, 0),
            })
        out.append(row)
    out.sort(key=lambda d: (d["unit"] is None, d.get("category") or 0,
                            d["family_id"]))
    return out


def _prune(v, depth=0, max_list=60, max_depth=9):
    """Keep JSON dumps of decoded objects bounded but structurally faithful."""
    if depth > max_depth:
        return "..."
    if isinstance(v, dict):
        return {k: _prune(x, depth + 1, max_list, max_depth) for k, x in v.items()}
    if isinstance(v, list):
        head = [_prune(x, depth + 1, max_list, max_depth) for x in v[:max_list]]
        if len(v) > max_list:
            head.append(f"... {len(v) - max_list} more (total {len(v)})")
        return head
    if isinstance(v, bytes):
        return v.hex()
    return v


def dump_family(doc, unit: int, detail_classes: Iterable[str] = DETAIL_CLASSES,
                max_detail_per_class: int = 6) -> dict:
    """Structured JSON of one save unit (an embedded family document).

    Contains: unit metadata, per-seq record counts + decode stats, the seq-102
    and seq-103 class histograms, the seq-103 rep class per element class,
    the id range, and full decoded objects for the family-editor essentials
    (``DETAIL_CLASSES``), plus the matching seq-101 ElementHeader parents for
    each detailed element.
    """
    idx = _index(doc)
    u = idx.units[unit]
    recs = idx.unit_records(unit)
    r102 = recs.get(102, {})
    r103 = recs.get(103, {})
    r101 = recs.get(101, {})
    hist102 = idx.class_histogram(unit, 102)
    hist103 = idx.class_histogram(unit, 103)
    # which rep class each element class carries in seq 103
    rep_by_class: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for eid, r in r102.items():
        r3 = r103.get(eid)
        if r3 is not None:
            rep_by_class[idx.class_name(r.class_id)][idx.class_name(r3.class_id)] += 1
    detail: dict[str, list] = {}
    want = set(detail_classes)
    per_class_seen: dict[str, int] = collections.Counter()
    for eid, r in sorted(r102.items()):
        cname = idx.class_name(r.class_id)
        if cname not in want or per_class_seen[cname] >= max_detail_per_class:
            continue
        per_class_seen[cname] += 1
        o = idx.decode(unit, eid, 102)
        h = idx.decode(unit, eid, 101)
        rep = r103.get(eid)
        entry = {
            "id": eid,
            "class": cname,
            "psize": r.body_size,
            "clean": bool(o and o.clean),
            "value": _prune(o.value) if o else None,
            "header_parents": _prune((h.value or {}).get("m_parents")) if h else None,
            "rep": None if rep is None else {
                "class": idx.class_name(rep.class_id), "psize": rep.body_size},
        }
        if rep is not None and idx.class_name(rep.class_id) == "GElement" \
                and cname in ("ExtrusionElem", "SweepElem", "BlendElem",
                              "RevolveElem", "SweptBlendElem"):
            g = idx.decode(unit, eid, 103)
            entry["rep_value"] = _prune(g.value, max_list=12, max_depth=7) if g else None
        detail.setdefault(cname, []).append(entry)
    ids = list(r102)
    return {
        "file": idx.name,
        "unit": unit,
        "unit_guid": u.guid,
        "unit_counter": u.counter,
        "n_blocks": u.n_blocks,
        "record_counts": {str(s): len(recs.get(s, {})) for s in (101, 102, 103)},
        "id_range": [min(ids), max(ids)] if ids else None,
        "decode_stats_seq102": idx.decode_stats(unit, 102),
        "decode_stats_seq103": idx.decode_stats(unit, 103),
        "classes_histogram_seq102": hist102,
        "classes_histogram_seq103": hist103,
        "rep_class_by_element_class": {k: dict(v) for k, v in rep_by_class.items()},
        "self_family": self_family_of_unit(idx, unit),
        "detail": detail,
    }


def self_family_of_unit(doc, unit: int) -> Optional[dict]:
    """The embedded document's OWN Family element: the one every other
    element's ``m_famId`` points at (nil ``m_famDocGUID``, no contentDoc).
    Carries the family's category, its family parameters (built-in +
    ``ParamElemFamily`` ids) and its type table (``FamilyTypeTable``)."""
    idx = _index(doc)
    fam_ids = idx.ids_of_class(unit, "Family")
    if not fam_ids:
        return None
    # the self family is the one referenced by other elements' m_famId
    refs = collections.Counter()
    for eid, r in idx.unit_records(unit).get(102, {}).items():
        v = idx.value(unit, eid) or {}
        fid = v.get("m_famId")
        if fid in fam_ids:
            refs[fid] += 1
    sf = refs.most_common(1)[0][0] if refs else fam_ids[0]
    v = idx.value(unit, sf) or {}
    fp = ((v.get("m_familyParams") or {}).get("value") or {}).get("m_params") or []
    ftt = (v.get("m_pFamilyTypes") or {}).get("value") or {}
    types = []
    for pr in ftt.get("m_pairs") or []:
        types.append({"name": pr.get("name"),
                      "n_params": len(((pr.get("params") or {}).get("m_params")) or [])})
    return {
        "id": sf,
        "category": v.get("m_categoryId"),
        "part_type": v.get("m_partType"),
        "work_plane_based": v.get("m_isWorkPlaneBased"),
        "n_nested_families": len(fam_ids) - 1,
        "family_params": [{"paramId": p.get("m_paramId"), "value": p.get("m_value"),
                           "int": p.get("m_int"),
                           "str": (p.get("m_str") or "")[:80]} for p in fp],
        "types": types,
        "big2small_present": bool(((v.get("m_oFamDoc") or {}).get("value") or {})
                                  .get("m_big2SmallMap2")),
    }


def find_family(doc, name_contains: str) -> Optional[dict]:
    """First inventory row whose family_name contains the given text."""
    idx = _index(doc)
    for row in family_documents(idx):
        n = row.get("family_name") or ""
        if name_contains.lower() in n.lower():
            return row
    return None


# ---------------------------------------------------------------------------
# ContentDocuments: locate every embedded document's ADocument by its GUID
# ---------------------------------------------------------------------------

def content_documents_by_guid(doc) -> list[dict]:
    """Locate each embedded family document's ``ADocument`` inside
    ``Global/ContentDocuments`` by searching for the unit-separator GUID.

    Verified on rme (305/305 embedded units): every entry has the form

        u32 X + ``a3 03 ff ff ff ff a2 03 ff ff ff ff`` + GUID(16)
        + u32 adoc_len + [u16 0x001c ADocument + object bytes ...]

    i.e. the two lead pointers ARE null for family entries; consecutive
    entries are spaced ``adoc_len + 36`` bytes apart.  The embedded ADocument
    carries INLINE the sub-objects a standalone document externalises to
    ``Global/ElemTable`` (0x5c9) and ``Global/History`` (0x538); its
    ``0x0ae9`` slot holds the document's own self-``Family`` element id.
    Returns rows {unit, guid, cd_offset (offset of the GUID in the inflated
    CD payload), adoc_offset, adoc_len, adoc_class, self_family_id}.
    """
    import struct as _st
    idx = _index(doc)
    with open_rvt(idx.path) as f:
        try:
            cd = b"".join(f.inflate_all("Global/ContentDocuments"))
        except Exception:                                    # pragma: no cover
            cd = b""
    rows = []
    for u in idx.units:
        if not u.guid:
            continue
        g = uuid.UUID(u.guid).bytes_le
        p = cd.find(g)
        row = {"unit": u.index, "guid": u.guid, "cd_offset": None,
               "adoc_offset": None, "adoc_len": None, "adoc_class": None,
               "self_family_id": None, "null_lead_pointers": None}
        if p >= 0 and p + 20 <= len(cd):
            n = _st.unpack_from("<I", cd, p + 16)[0]
            cls = _st.unpack_from("<H", cd, p + 20)[0]
            row.update({
                "cd_offset": p, "adoc_offset": p + 20, "adoc_len": n,
                "adoc_class": cls,
                "null_lead_pointers": cd[p - 12:p] == bytes.fromhex(
                    "a303ffffffffa203ffffffff"),
            })
            q = cd.find(b"\xe9\x0a", p + 20, p + 20 + 128)   # 0x0ae9 slot
            if q >= 0:
                row["self_family_id"] = _st.unpack_from("<q", cd, q + 2)[0]
        rows.append(row)
    return rows


def content_document_adoc(doc, guid: str) -> Optional[bytes]:
    """The serialized ``ADocument`` bytes of the embedded document with the
    given content-document GUID (== unit separator GUID), or ``None``."""
    idx = _index(doc)
    g = uuid.UUID(guid).bytes_le
    import struct as _st
    with open_rvt(idx.path) as f:
        cd = b"".join(f.inflate_all("Global/ContentDocuments"))
    p = cd.find(g)
    if p < 0:
        return None
    n = _st.unpack_from("<I", cd, p + 16)[0]
    return cd[p + 20:p + 20 + n]


# ---------------------------------------------------------------------------
# family-document (re-)authoring: F1 (full re-encode) and F2 (param edit)
# ---------------------------------------------------------------------------

#: streams stored with NO CRCIO page framing (copied byte-for-byte).
#: ``PartAtom`` (the .rfa Atom-XML manifest) is plain unframed text.
UNFRAMED_STREAMS = ("BasicFileInfo", "ProjectInformation",
                    "TransmissionData", "RevitPreview4.0", "PartAtom")


def unit_segments(doc, unit: int) -> dict[int, bytes]:
    """Per-seq (101/102/103) concatenated block payloads of one save unit,
    in stream order -- the byte strings ``iter_records`` walks."""
    idx = _index(doc)
    wi, ui = idx._unit_ref[unit]
    _pn, w = idx._walkers[wi]
    u = w.units[ui]
    blocks = w.blocks[u.first_block:u.first_block + u.n_blocks]
    segs: dict[int, bytearray] = {}
    for b in sorted(blocks, key=lambda b: b.hdr_offset):
        segs.setdefault(b.seq, bytearray()).extend(b.data or b"")
    return {seq: bytes(buf) for seq, buf in sorted(segs.items())}


def encoder_roundtrip(doc, unit: int, keep_failures: int = 8) -> dict:
    """Decode -> re-encode every record of a unit's three seqs and count
    the records whose re-encoded bytes are IDENTICAL to the original
    (header, stamp, sizes, class id, object, trailer).  100 %-pass here means
    the whole document can be re-serialized by our encoder -- the F1/F2
    precondition."""
    from .encode import ObjectEncoder, roundtrip_segment
    idx = _index(doc)
    enc = ObjectEncoder(idx.schema)
    out = {}
    for seq, seg in unit_segments(idx, unit).items():
        st = roundtrip_segment(seg, seq, enc, only_clean=False)
        out[str(seq)] = {
            "records": st["records"], "tested": st["tested"],
            "pass": st["pass"], "fail": st["fail"],
            "skipped_unclean": st["skipped_unclean"],
            "skipped_bad_trailer": st["skipped_bad_trailer"],
            "failures": st["failures"][:keep_failures],
        }
    out["all_pass"] = all(v["fail"] == 0 and v["skipped_unclean"] == 0
                          for k, v in out.items() if k in ("101", "102", "103"))
    return out


def _reencoded_segments(idx: FamilyIndex, unit: int) -> tuple[dict[int, bytes], dict]:
    """Re-serialize a unit's seqs record-by-record through the encoder."""
    from .encode import ObjectEncoder, reencode_segment
    enc = ObjectEncoder(idx.schema)
    segs = unit_segments(idx, unit)
    out, stats = {}, {}
    for seq, seg in segs.items():
        nb, st = reencode_segment(seg, seq, enc)
        st["identical_to_original"] = (nb == seg)
        st["length_preserved"] = (len(nb) == len(seg))
        out[seq] = nb
        stats[str(seq)] = st
    return out, stats


def set_family_type_param(doc, unit: int, segments: dict[int, bytes], *,
                          param_id: int, new_value: float,
                          type_name: Optional[str] = None,
                          also_current_defaults: bool = False) -> tuple[dict[int, bytes], dict]:
    """F2 primitive: change ONE type-parameter default of the document's
    self-``Family`` and re-encode that record with a recomputed adler32 stamp.

    ``type_name`` selects the ``FamilyTypeTable.m_pairs[]`` entry (None =
    all types); ``also_current_defaults`` also rewrites the matching entry in
    the self-Family's ``m_familyParams`` (the CURRENT type's defaults).
    A double -> double edit keeps the record length, so the modified seq-102
    segment is a same-length splice (block A/B/C counters stay valid).
    Returns (new_segments, edit_report).
    """
    import copy
    from .encode import ObjectEncoder, record_stamp
    idx = _index(doc)
    sf = self_family_of_unit(idx, unit)
    if sf is None:
        raise ValueError("unit has no self-Family")
    sf_id = sf["id"]
    rec = idx.unit_records(unit)[102][sf_id]
    dobj = idx.decode(unit, sf_id, 102)
    if dobj is None or not dobj.clean:
        raise ValueError("self-Family record does not decode cleanly")
    value = copy.deepcopy(dobj.value)
    changed = []
    ftt = ((value.get("m_pFamilyTypes") or {}).get("value") or {})
    for pr in ftt.get("m_pairs") or []:
        if type_name is not None and pr.get("name") != type_name:
            continue
        for p in ((pr.get("params") or {}).get("m_params") or []):
            if p.get("m_paramId") == param_id:
                changed.append({"where": f"type[{pr.get('name')!r}]",
                                "old": p.get("m_value"), "new": new_value})
                p["m_value"] = float(new_value)
    if also_current_defaults:
        fp = ((value.get("m_familyParams") or {}).get("value") or {})
        for p in fp.get("m_params") or []:
            if p.get("m_paramId") == param_id:
                changed.append({"where": "self.m_familyParams",
                                "old": p.get("m_value"), "new": new_value})
                p["m_value"] = float(new_value)
    if not changed:
        raise ValueError(f"param {param_id} / type {type_name!r} not found")
    enc = ObjectEncoder(idx.schema)
    body = enc.encode_object(rec.class_id, value)
    ps = 2 + len(body)
    stamp = record_stamp(rec.class_id, body)
    new_rec = (struct.pack("<qII", sf_id, stamp, ps) + struct.pack("<H", rec.class_id)
               + body + struct.pack("<I", ps))
    seg = segments[102]
    old_rec = seg[rec.seg_offset: rec.seg_offset + 16 + rec.body_size + 4]
    if len(new_rec) != len(old_rec):
        raise ValueError(f"record length changed {len(old_rec)} -> {len(new_rec)}"
                         " (only same-length edits are splice-able)")
    new_seg = (seg[:rec.seg_offset] + new_rec
               + seg[rec.seg_offset + len(old_rec):])
    out = dict(segments)
    out[102] = new_seg
    report = {"self_family_id": sf_id, "class_id": rec.class_id,
              "record_offset": rec.seg_offset, "record_len": len(new_rec),
              "old_stamp": rec.stamp, "new_stamp": stamp,
              "bytes_changed": sum(1 for a, b in zip(old_rec, new_rec) if a != b),
              "changed": changed}
    return out, report


def _rebuild_partition_logical(logical: bytes, walker: StreamWalker,
                               seg_by_seq: dict[int, bytes], level: int = 3) -> bytes:
    """Re-emit a single-unit partition stream: every block payload is taken
    from ``seg_by_seq`` (re-encoded / edited segments) at the same block
    boundaries, re-gzipped by us; all inter-block bytes are copied and the
    stream is truncated cleanly after the end record."""
    from .writer import BLOCK_TRL_LEN, BLOCK_TRL_TAG, gzip_member
    out = bytearray()
    cursor = 0
    cur: dict[int, int] = {seq: 0 for seq in seg_by_seq}
    for b in sorted(walker.blocks, key=lambda b: b.hdr_offset):
        out += logical[cursor:b.member_offset]
        hdr_start = len(out) - (b.member_offset - b.hdr_offset)
        seg = seg_by_seq.get(b.seq)
        if seg is None:
            payload = b.data
        else:
            payload = seg[cur[b.seq]:cur[b.seq] + len(b.data)]
            cur[b.seq] += len(b.data)
        if len(payload) != len(b.data):
            raise ValueError(f"block {b.index}: payload length changed")
        gz = gzip_member(payload, level=level, sync_flush=True)
        nb = 8 + len(gz)
        struct.pack_into("<I", out, hdr_start + 10, nb)      # patch header B
        out += gz + struct.pack("<HI", BLOCK_TRL_TAG, nb)   # trailer mirror
        cursor = b.member_offset + b.member_len + BLOCK_TRL_LEN
    out += logical[cursor:]
    for seq, seg in seg_by_seq.items():
        if cur[seq] != len(seg):
            raise ValueError(f"seq {seq}: segment length mismatch "
                             f"({cur[seq]} spliced of {len(seg)})")
    w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
    if w2.errors:
        raise ValueError(f"rebuilt partition walker errors: {w2.errors[:3]}")
    end = w2.end_offset + len(w2.end_record)
    if 0 < end <= len(out):
        out = out[:end]
    return bytes(out)


def emit_rfa(src: str, out: str, *, edits: Optional[list[dict]] = None,
             level: int = 3) -> dict:
    """FULL-pipeline re-emit of a standalone family (``.rfa``) file.

    Every seq-101/102/103 record of the (single) family document is decoded
    and RE-ENCODED by ``rvt.encode`` (F1), optionally with type-parameter
    edits applied to the self-``Family`` record (F2, ``edits`` =
    [{param_id, value, type_name?, also_current_defaults?}]); the partition
    stream is re-blocked with our gzip, every framed stream is re-gzipped
    (level 3 + sync-flush) and re-framed with REAL CRCIO page ECC, the
    unframed metadata streams (incl. the Atom-XML ``PartAtom``) are copied,
    and the container is rebuilt by our CFB writer.  Returns a report
    including read-back verification (see ``verify_rfa``).
    """
    import dataclasses as _dc
    from . import ecc
    from .cfb_writer import write_cfb
    from .roundtrip import read_entries
    from .writer import gzip_member
    idx = FamilyIndex(src)
    report: dict = {"src": src, "out": out, "streams": [], "edits": []}
    # --- the family document: re-encode (and optionally edit) unit 0
    segs, seg_stats = _reencoded_segments(idx, 0)
    report["reencode"] = seg_stats
    for e in edits or []:
        segs, er = set_family_type_param(
            idx, 0, segs, param_id=e["param_id"], new_value=e["value"],
            type_name=e.get("type_name"),
            also_current_defaults=e.get("also_current_defaults", False))
        report["edits"].append(er)
    entries = read_entries(src)
    new_data: dict[str, bytes] = {}
    with open_rvt(src) as f:
        pstreams = set(f.partition_streams())
        for s in f.streams():
            name = s.name
            if name in UNFRAMED_STREAMS or not f.members(name):
                report["streams"].append({"name": name, "action": "copied",
                                          "size": len(f.raw(name))})
                continue
            if name in pstreams:
                wi = [i for i, (pn, _w) in enumerate(idx._walkers) if pn == name][0]
                _pn, w = idx._walkers[wi]
                logical = _rebuild_partition_logical(f.logical(name), w, segs, level)
                new_data[name] = ecc.frame_stream(logical)
                report["streams"].append({"name": name,
                                          "action": "records re-encoded, re-blocked, real ECC",
                                          "logical": len(logical), "size": len(new_data[name])})
            else:
                logical = f.prefix(name) + gzip_member(f.inflate(name, 0),
                                                       level=level, sync_flush=True)
                new_data[name] = ecc.frame_stream(logical)
                report["streams"].append({"name": name, "action": "re-gzip + real ECC",
                                          "logical": len(logical), "size": len(new_data[name])})
    out_entries = [_dc.replace(e, data=new_data[e.path])
                   if e.entry_type == "stream" and e.path in new_data else e
                   for e in entries]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    write_cfb(out, out_entries)
    report["size"] = os.path.getsize(out)
    report["verify"] = verify_rfa(out, src=src)
    return report


def verify_rfa(path: str, src: Optional[str] = None) -> dict:
    """Read a written .rfa back: every gzip member CRC-verifies, every full
    page's CRCIO trailer re-derives byte-exact, the partition walks with no
    errors, per-seq record counts and every seq-102 record decode clean; if
    ``src`` is given, per-seq element-id sets are compared with the source."""
    from . import ecc
    rep: dict = {"path": path, "gzip_members": 0, "gzip_crc_failures": 0,
                 "ecc_full_pages": 0, "ecc_mismatch": 0}
    with open_rvt(path) as d:
        for s in d.streams():
            for m in d.members(s.name):
                rep["gzip_members"] += 1
                if not m.crc_ok:
                    rep["gzip_crc_failures"] += 1
            raw = d.raw(s.name)
            if s.name in UNFRAMED_STREAMS:
                continue
            for k in range(len(raw) // ecc.PAGE_STRIDE):
                page = raw[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD]
                tr = raw[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE]
                rep["ecc_full_pages"] += 1
                if ecc.page_trailer(page) != tr:
                    rep["ecc_mismatch"] += 1
    idx = FamilyIndex(path)
    _pn, w = idx._walkers[0]
    rep["walker_errors"] = list(w.errors[:5])
    rep["n_units"] = len(idx.units)
    segs = unit_segments(idx, 0)
    rep["record_counts"] = {str(s): sum(1 for _ in iter_records(seg, s))
                            for s, seg in segs.items()}
    st = idx.decode_stats(0, 102)
    rep["decode_seq102"] = st
    if src:
        sidx = FamilyIndex(src)
        s_segs = unit_segments(sidx, 0)
        rep["ids_match_source"] = all(
            [r.elem_id for r in iter_records(segs[s], s)]
            == [r.elem_id for r in iter_records(s_segs[s], s)]
            for s in s_segs)
    rep["ok"] = (rep["gzip_crc_failures"] == 0 and rep["ecc_mismatch"] == 0
                 and not rep["walker_errors"] and st["clean"] == st["records"]
                 and rep.get("ids_match_source", True))
    return rep


# ---------------------------------------------------------------------------
# demo / __main__
# ---------------------------------------------------------------------------

OUT_DIR = os.path.join(_ROOT, "experiments", "families")


def _summary_line(row: dict) -> str:
    g = row.get("geometry") or {}
    gtxt = ",".join(f"{k[:-4] if k.endswith('Elem') else k}x{n}"
                    for k, n in g.items()) or "-"
    return (f"  {row['family_id']:>8}  u{str(row['unit']):>4}  cat {str(row['category']):>9}"
            f"  types {row['n_types']:>2}  conn {row.get('n_connectors', 0):>2}"
            f"  refp {row.get('n_ref_planes', 0):>2}  geom {gtxt:<12}"
            f"  {row['family_name']!r}")


def write_inventory(project: str, out_name: str) -> dict:
    idx = FamilyIndex.open(project)
    rows = family_documents(idx)
    os.makedirs(OUT_DIR, exist_ok=True)
    out = {
        "file": idx.name,
        "n_units": len(idx.units),
        "n_embedded_units": len(idx.units) - 1,
        "n_host_families": len(rows),
        "n_families_resolved_to_unit": sum(1 for r in rows if r["unit"] is not None),
        "families": rows,
    }
    p = os.path.join(OUT_DIR, f"inventory_{out_name}.json")
    with open(p, "w") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(f"{idx.name}: {out['n_embedded_units']} embedded units, "
          f"{out['n_host_families']} host families, "
          f"{out['n_families_resolved_to_unit']} resolved  -> {p}")
    for row in rows:
        if row["unit"] is not None:
            print(_summary_line(row))
    return out


DUMP_TARGETS = (
    # (name fragment, output file)
    ("Plain Recessed Lighting Fixture", "dump_rme_plain_recessed_light.json"),
    ("Panelboard - 208V MLO", "dump_rme_panelboard_208v_mlo.json"),
)

#: the standalone family donor on disk (a 2026 furniture .rfa)
SAMPLE_RFA = os.path.join(_ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
                          "racbasicsamplefamily-2026.rfa")
F1_OUT = os.path.join(OUT_DIR, "F1_rfa_full_reencode.rfa")
F2_OUT = os.path.join(OUT_DIR, "F2_rfa_type_param_edit.rfa")
#: F2 edit: type '0610 x 0160mm' Length (ParamElemFamily 4253, feet):
#: 2.0013 ft (610 mm) -> 3.0 ft (914.4 mm); the CURRENT type is untouched
#: so no cached geometry goes stale.
F2_EDITS = [{"param_id": 4253, "value": 3.0, "type_name": "0610 x 0160mm"}]


def _dump_reports(name: str, obj) -> str:
    p = os.path.join(OUT_DIR, name)
    with open(p, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)
    return p


def run_experiments() -> dict:
    """Encoder round-trip on the three family documents + F1 + F2."""
    os.makedirs(OUT_DIR, exist_ok=True)
    out: dict = {}
    # -- encoder round-trip: the .rfa's document and the two rme donors
    rt = {"rfa:" + os.path.basename(SAMPLE_RFA): encoder_roundtrip(SAMPLE_RFA, 0)}
    idx = FamilyIndex.open("rmebasicsampleproject")
    for frag, _ in DUMP_TARGETS:
        row = find_family(idx, frag)
        if row and row["unit"] is not None:
            rt[f"rme:unit{row['unit']}:{row['family_name']}"] = \
                encoder_roundtrip(idx, row["unit"])
    p = _dump_reports("encoder_roundtrip.json", rt)
    print("encoder round-trip:", {k: (v.get("102", {}).get("pass"),
                                     v.get("102", {}).get("fail"),
                                     v.get("all_pass")) for k, v in rt.items()},
          "->", p)
    out["encoder_roundtrip"] = rt
    # -- CD entries: every embedded document's ADocument located by GUID
    cdrows = content_documents_by_guid(idx)
    n_found = sum(1 for r in cdrows if r["cd_offset"] is not None)
    p = _dump_reports("cd_family_documents_rme.json",
                      {"file": idx.name, "units": len(cdrows), "found": n_found,
                       "all_null_lead_pointers": all(
                           r["null_lead_pointers"] for r in cdrows
                           if r["cd_offset"] is not None),
                       "rows": cdrows})
    print(f"CD entries by GUID: {n_found}/{len(cdrows)} embedded units located -> {p}")
    out["cd_found"] = (n_found, len(cdrows))
    # -- F1: full-pipeline re-emit of the sample .rfa (zero semantic change)
    r1 = emit_rfa(SAMPLE_RFA, F1_OUT)
    p = _dump_reports("F1_report.json", r1)
    print(f"F1 -> {F1_OUT} ({r1['size']:,} B); verify ok={r1['verify']['ok']} -> {p}")
    out["F1"] = r1
    # -- F2: F1 + one type-parameter default changed (stamp recomputed)
    r2 = emit_rfa(SAMPLE_RFA, F2_OUT, edits=F2_EDITS)
    p = _dump_reports("F2_report.json", r2)
    print(f"F2 -> {F2_OUT} ({r2['size']:,} B); verify ok={r2['verify']['ok']}"
          f" edit={r2['edits']} -> {p}")
    out["F2"] = r2
    return out


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    write_inventory("rmebasicsampleproject", "rme")
    write_inventory("racbasicsampleproject", "rac")
    # detailed dumps: the closest thing to the flagship recessed luminaire,
    # plus the electrical panelboard donor
    idx = FamilyIndex.open("rmebasicsampleproject")
    for frag, outname in DUMP_TARGETS:
        row = find_family(idx, frag)
        if not row or row["unit"] is None:
            print(f"no family matching {frag!r}")
            continue
        d = dump_family(idx, row["unit"])
        d["host_family"] = row
        p = os.path.join(OUT_DIR, outname)
        with open(p, "w") as fh:
            json.dump(d, fh, indent=1, default=str)
        print(f"dumped unit {row['unit']} ({row['family_name']}) -> {p}")
        print("  seq102 histogram:", json.dumps(d["classes_histogram_seq102"]))
        print("  decode stats:", d["decode_stats_seq102"])
    if "--no-experiments" not in argv:
        run_experiments()
    return 0


if __name__ == "__main__":
    sys.exit(main())

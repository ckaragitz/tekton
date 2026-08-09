"""rvt.famload -- the EMBEDDED FAMILY-DOCUMENT LOADER (the K4-FAIL branch).

Insert one or more of OUR family documents into a project (.rvt) as proper
EMBEDDED DOCUMENTS -- the exact inverse of ``tools/genesis_triage.py``'s
``remove_documents`` -- reconciling ALL FOUR document registries plus the
host-side family layer:

    FOUR REGISTRIES (a document GUID lives in four places)   [VERIFIED on
    rstbasic: 53 units / 52 ContentDocuments / 52 ContentTable / 50 FamilyMgr
    entries carrying 52 GUIDs; the viewer-FAILED R9b/R10b splices reconciled
    only the first two]

      1. ``Partitions/<N>``   a new SAVE UNIT: 28-byte separator {u16 0x3a3,
         i32 -1, u16 0x3a2, u32 record_count, GUID}, per-seq segments
         (101/102/103, whole records, our gzip, block A/B/C by the corpus
         identity), sentinels, 18-byte terminator + 0x0f3f footer + the
         'Data generated ...' magic  (rvt.famgen.factory.build_family_save_unit
         + splice before the stream end record; every existing unit
         byte-preserved).
      2. ``Global/ContentDocuments``   one entry {separator, GUID, u32
         adoc_len, the embedded ADocument, u32 adoc_len mirror}, GUID-sorted,
         SOLVED grammar (rvt.famgen.factory parse/assemble/insert, byte-exact
         on the corpus).
      3. ``Global/Latest`` ADocument ``m_oContentTable.m_ContentRecSet`` += the
         record {ContentKey.m_guidKey = our GUID, m_author, history{creation /
         modification episodes}, m_EpisodeCounts [(episode, unit records)]}.
      4. ``Global/Latest`` ADocument ``AppInfoManager[FamilyMgr]
         .m_arrLoadedFamilyInfo`` (AppInfo slot 0) += {m_surrogateId = our
         FamilySurrogate, m_familyDocGUIDs [our GUID]}.

    (``Global/PartitionTable`` is the WORKSET table -- class 0xc80, 1 row on
    rstbasic -- NOT a per-document index; loading a family adds NO row there.
    ``ElementTrackingData`` symbol-id sets are appended only when the host
    already tracks the family's category: annotation-head categories are NOT
    tracked on rstbasic.)

    HOST-SIDE ELEMENTS (partition unit 0 + ``Global/ElemTable`` rows), the
    annotation-family flavour decoded from rstbasic's 'M_Level Head - Circle1'
    (host Family 1388845, symbol 1417017, surrogates 1388865 / 1417014, three
    ParamElemFamily twins 1390070/71/73)                       [VERIFIED shapes]

      * ``ParamElemFamily`` TWIN per family user parameter -- the embedded
        parameter object with FOUR rewrites: m_id / m_pParamDef.m_paramElemId
        -> the host id, m_famId -> the host Family, m_typeId ->
        ``revit.local.family:<32hex session guid><%08x host id>-1.0.0``;
        header {category -1, m_familyId = host Family, deletion [Family,
        self], flags 8202}.
      * ``FamilySurrogate`` {m_elemId = host Family, m_name = family name,
        m_categoryId, m_previewElemId -1, m_guid = the constant creator GUID
        e3e052f8-0156-11d5-9301-0000863f27ad, m_bIsAdaptive False}; header
        {deletion [Family, self], view-flags -32640}.
      * host ``Family`` = OUR self-Family TRANSFORMED: m_name = the family
        name (the embedded self-Family's name is empty), m_famDocGUID minted,
        m_surrogateId, m_path '' (ours), m_partType (-1 for annotation),
        ``m_oFamDoc = FamilyDocument{m_contentDocGUID = our GUID,
        m_big2SmallMap2 = [(host twin -> embedded param) ...], m_coreIds}``,
        m_familyIds narrowed to the host twins (each keeping its embedded
        ABSORBED index), ``m_pFamilyTypes`` = ONE leading blank ' ' row (= the
        current values keyed by the twins; an ANNOTATION family's types live
        as FamilySymbols, not in the host type table), one
        DBViewInfoForPreview, FamilyReferenceIdxMgr (origin refs), the empty
        FamDimConstrMgr KEPT (annotation flavour keeps it), doc-only state
        (m_fsdos / m_refs / m_deletableElements) empty.
      * one ``FamilySymbol`` per family type: m_symbolInfo{m_name = type
        name}, m_familyId = host Family, m_partitionSurrogateId = its
        FamSymSurrogate, m_pParams = the type's rows keyed by the TWIN ids,
        m_hasParamDefValue 1, m_active, the FamilySymbolPatternHelper cell, an
        empty move-restriction Matrix, an annotation-plane outline;
        seq-103 rep = SerializedDummy (Revit regenerates the symbol graphics
        from the family document -- the specimen carries a cached GElement
        graphics tree, OURS relies on regeneration [ACCEPTANCE H]).
      * ``FamSymSurrogate`` {m_elemId = the symbol, m_name = type name,
        m_categoryId, m_famSurrogateId = the FamilySurrogate}; header
        {deletion [surrogate, self, symbol], regenOnly [Family],
        view-flags -32640}.

    USAGE REPOINTING (optional third pass): the OUTSIDE references into a
    project's loadable-family layer are USAGE fields on attribute/type
    elements (LevelAttributes / GridAttributes / CalloutTag /
    ViewportAttributes ``.m_familyTagId``, SectionAttributes
    ``.m_sectionHeadFamilyTagId`` / ``.m_sectionTailFamilyTagId``,
    InteriorElevAttributes ``.m_elevationSymbolId``, StructSettingsElem
    ``.m_bcFixedFamilyId``) naming a FamilySymbol id, plus that symbol in the
    referrer's seq-101 ``m_parents.m_deletion`` list [VERIFIED rstbasic
    LevelAttributes 305 -> symbol 1417017 in both].  ``repoint_usage`` sets
    them to OUR symbols through ``rvt.manipulate``'s certified modify path
    (records re-encoded byte-exact, adler32 stamps recomputed).

Write pipeline (``load_family_documents``): survey host -> per family:
build the document ABOVE the host watermark, plan ids / twins, author the
host elements -> roundtrip-gate every authored record -> PASS 1
``rvt.commit.commit_new_elements`` (host elements into save-unit 0 +
ElemTable + identity) -> PASS 2 (splice every embedded save unit, insert
every ContentDocuments entry, register every family in the host ADocument;
CRCIO-reframe the three touched streams) -> PASS 3 (optional usage
repointing) -> verify (four-registry coherence census + our GUIDs / ids
present in all four + validator 0 errors + walker clean + our host elements
decode).

PROVENANCE: every element the load creates is OURS -- our family documents
(constructor-built, no Autodesk family bytes), host records authored
field-by-field from format shapes.  The HOST project is whatever the caller
passes (a sample, a triage rung, or our constructed genesis base).

Public API::

    from rvt import famload as FL
    rep = FL.load_family_document("samples/rstbasicsampleproject.rvt",
                                  builder_or_doc, out_rvt="out.rvt", name="RW Level Head")
    rep = FL.load_family_documents(host, [FamilyLoad(name, builder), ...],
                                   out_rvt, repoints=[UsageRepoint(...)])
    FL.four_registry_census(path)           # the coherence instrument
    FL.verify_loaded_project(path, plans)   # the machine proofs

TERRITORY: new module of the genesis-loader (K4-FAIL branch) stream; imports
(never edits) rvt.famgen.factory / rvt.famgen.skeleton / rvt.genesis /
rvt.commit / rvt.adocument / rvt.manipulate and the format codecs.  Coordinates
with the asset-forge L4/L5 stream's ``rvt.famgen.loader`` (component families,
placed instances, host = the rme sample): the four registries and the host
element shapes below are the ANNOTATION-family flavour genesis needs; the two
loaders share ``rvt.famgen.factory``'s L1/L2/L3 machinery.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import os
import struct
import time
import uuid
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", ".."))

#: our product identity (matches rvt.famgen.factory.PRODUCT_NAME)
PRODUCT_NAME = "rvt-writer"
INVALID = -1

#: FamilySurrogate.m_guid -- the SAME constant on all 159 rme surrogates AND
#: rstbasic's 1388865 [VERIFIED]: a format-level creator id, not content.
SURROGATE_GUID = "e3e052f8-0156-11d5-9301-0000863f27ad"

#: seq-101 header (m_abFlags4Bytes, m_viewRules.m_nVisibleViewFlags) per host
#: class, from the rstbasic level-head family layer [VERIFIED]
HDR_FLAGS = {
    "Family": (10, -32768),
    "FamilySymbol": (2218, -32768),
    "ParamElemFamily": (8202, -32768),
    "ParamElemExternal": (8202, -32768),
    "FamilySurrogate": (10, -32640),
    "FamSymSurrogate": (10, -32640),
}

#: the family-parameter definition classes that get a host TWIN (a shared
#: ``ParamElemExternal`` twins as itself, GUID identity kept verbatim)
PARAM_TWIN_CLASSES = ("ParamElemFamily", "ParamElemExternal")

#: DBViewInfoForPreview of an annotation host Family [VERIFIED rstbasic
#: 1388845: one preview view, viewFamily 107, viewType 6]
ANNOTATION_PREVIEW_VIEW = {
    "m_name": "", "m_horz": [1.0, 0.0, 0.0], "m_origin": [0.0, 0.0, 0.0],
    "m_scale": 1.0, "m_vert": [0.0, 1.0, 0.0],
    "m_viewerTargetPos": [0.0, 0.0, 0.0], "m_viewFamily": 107, "m_viewType": 6,
}

#: The USAGE fields that name a head/tag FamilySymbol, per referrer class
#: [VERIFIED by genesis-triage-a's K3 neutralisation set]
USAGE_FIELDS = {
    "LevelAttributes": ["m_familyTagId"],
    "GridAttributes": ["m_familyTagId"],
    "CalloutTag": ["m_familyTagId"],
    "ViewportAttributes": ["m_familyTagId"],
    "SectionAttributes": ["m_sectionHeadFamilyTagId", "m_sectionTailFamilyTagId"],
    "InteriorElevAttributes": ["m_elevationSymbolId"],
    "StructSettingsElem": ["m_bcFixedFamilyId"],
}


class LoaderError(RuntimeError):
    """A load precondition the host or the family cannot satisfy."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _dc(v: Any) -> Any:
    return copy.deepcopy(v)


def _ptr(cls: str, value: dict, pid: int = -1) -> dict:
    return {"ptr_class": cls, "pid": pid, "value": value}


def _weak(ref: int) -> dict:
    return {"weakref": int(ref)}


def _relp(p: str) -> str:
    try:
        return os.path.relpath(p, _ROOT)
    except ValueError:                      # pragma: no cover
        return p


# ---------------------------------------------------------------------------
# THE FOUR-REGISTRY COHERENCE CENSUS  (the instrument the loader is verified by)
# ---------------------------------------------------------------------------

def four_registry_census(path: str) -> Dict[str, Any]:
    """The four document registries of ``path`` and their coherence.

    Returns {save_units, contentdocs_entries, contentdocs_guids,
    contenttable_records, contenttable_guids, familymgr_entries,
    familymgr_guids, unit_guids, coherent, orphan_units, unregistered ...}.
    COHERENT = ``save_units - 1 == contentdocs_entries ==
    contenttable_records == len(familymgr_guids)`` AND the four GUID sets are
    equal (R9 / K1 / rstbasic are coherent; the viewer-FAILED R9b / R10b and
    the audited G0 were not).  Read-only, and read under the file's OWN
    release (``rvt.global_framing.enter_own_release``): partition framing,
    the ContentDocuments tokens and the ADocument decoder all follow the
    file, so a 2025/2024 project's registries are counted, not mis-parsed
    as 0 (a fallback rung, if taken, is reported as ``release_note``).
    """
    from contextlib import ExitStack
    from .global_framing import enter_own_release
    with ExitStack() as stack:
        note = enter_own_release(stack, path)
        rep = _four_registry_census(path)
        if note:
            rep["release_note"] = note
        return rep


def _four_registry_census(path: str) -> Dict[str, Any]:
    from .container import open_rvt
    from .partitions import StreamWalker
    from . import adocument as A
    from .famgen.factory import parse_content_documents
    rep: Dict[str, Any] = {"path": _relp(path)}
    unit_guids: List[str] = []
    with open_rvt(path) as f:
        pname = f.partition_streams()[0]
        w = StreamWalker(f.logical(pname), inflate=False, keep_data=False)
        rep["save_units"] = len(w.units)
        for u in w.units:
            if u.index != 0 and u.guid:
                unit_guids.append(str(uuid.UUID(bytes_le=u.guid)))
        # ContentDocuments (solved grammar)
        try:
            payload = b"".join(f.inflate_all("Global/ContentDocuments"))
            entries, tail = parse_content_documents(payload)
            rep["contentdocs_entries"] = len(entries)
            rep["contentdocs_guids"] = sorted(g.lower() for g, _a in entries)
            rep["contentdocs_clean_tail"] = (len(tail) == 14)
        except Exception as ex:                                   # pragma: no cover
            rep["contentdocs_entries"] = None
            rep["contentdocs_error"] = repr(ex)
        # ADocument ContentTable + FamilyMgr
        try:
            a = A.decode_latest(f.inflate("Global/Latest"))
            rep["adocument_clean"] = bool(a.clean)
            ct = (a.value.get("m_oContentTable") or {}).get("value") or {}
            recs = ct.get("m_ContentRecSet")
            if isinstance(recs, list):
                rep["contenttable_records"] = len(recs)
                rep["contenttable_guids"] = sorted(
                    str((r.get("m_ContentKey") or {}).get("m_guidKey") or "").lower()
                    for r in recs)
            else:
                rep["contenttable_records"] = None
            mgr = (a.value.get("m_pAppInfoManager") or {}).get("value") or {}
            fm_guids: List[str] = []
            fm_entries = None
            for slot in mgr.get("m_appInfoArr") or []:
                if isinstance(slot, dict) and slot.get("ptr_class") == "FamilyMgr":
                    arr = (slot.get("value") or {}).get("m_arrLoadedFamilyInfo") or []
                    fm_entries = len(arr)
                    for e in arr:
                        fm_guids.extend(str(g).lower() for g in (e.get("m_familyDocGUIDs") or []))
            rep["familymgr_entries"] = fm_entries
            rep["familymgr_guids"] = sorted(fm_guids)
        except Exception as ex:                                   # pragma: no cover
            rep["contenttable_records"] = None
            rep["adocument_error"] = repr(ex)
    rep["unit_guids"] = sorted(g.lower() for g in unit_guids)
    ug = set(rep["unit_guids"])
    cg = set(rep.get("contentdocs_guids") or [])
    tg = set(rep.get("contenttable_guids") or [])
    fg = set(rep.get("familymgr_guids") or [])
    rep["coherent_counts"] = bool(
        rep.get("save_units") is not None
        and rep["save_units"] - 1 == rep.get("contentdocs_entries")
        == rep.get("contenttable_records") == len(fg))
    rep["coherent_guids"] = bool(ug == cg == tg == fg)
    rep["coherent"] = bool(rep["coherent_counts"] and rep["coherent_guids"])
    # diagnostics: which surface disagrees
    rep["units_missing_from_contentdocs"] = sorted(ug - cg)
    rep["units_missing_from_contenttable"] = sorted(ug - tg)
    rep["units_missing_from_familymgr"] = sorted(ug - fg)
    rep["contenttable_dangling"] = sorted(tg - ug)
    rep["familymgr_dangling"] = sorted(fg - ug)
    return rep


# ---------------------------------------------------------------------------
# host survey
# ---------------------------------------------------------------------------

@dataclass
class HostContext:
    """What the loader needs to know about the HOST project."""
    path: str
    doc: Any                                  # rvt.mutate.Document
    watermark: int                            # highest issued id (IdentifierSource.m_last)
    episode: int                              # the load episode (max modified episode)
    partition_name: str
    category_gstyles: Dict[int, int] = dc_field(default_factory=dict)   # category -> GStyleElem id
    fill_pattern_solid: int = INVALID
    line_pattern_solid: int = INVALID
    census_before: Dict[str, Any] = dc_field(default_factory=dict)
    usage_referrers: Dict[str, List[int]] = dc_field(default_factory=dict)  # class -> ids
    notes: List[str] = dc_field(default_factory=list)


def survey_host(host_rvt: str, *, categories: Sequence[int] = ()) -> HostContext:
    """Open the host, resolve the id watermark / load episode / partition
    name, the projection ``GStyleElem`` of each requested category (a loaded
    family binds its category's style row as a CORE id when the host has one),
    the usage-field referrers present, and the four-registry census BEFORE."""
    from .mutate import Document
    from .container import open_rvt
    from .elemtable import parse_elemtable
    doc = Document.from_file(host_rvt)
    with open_rvt(host_rvt) as f:
        parts = f.partition_streams()
        if len(parts) != 1:
            raise LoaderError(f"expected one partition stream, got {parts}")
        pname = parts[0]
        et = parse_elemtable(f.inflate("Global/ElemTable", 0))
    last = int(et.footer.last_id) if et.footer else 0
    wm = max(last, max(doc.et_by_id) if doc.et_by_id else 0)
    episode = max((r.modified_ep for r in et.records), default=0)
    ctx = HostContext(path=host_rvt, doc=doc, watermark=int(wm),
                      episode=int(episode), partition_name=pname)
    # the four registries BEFORE
    ctx.census_before = four_registry_census(host_rvt)
    # category projection GStyles (m_gstyleType 1 = projection) for the
    # requested categories -- a family's core-id binding [V rstbasic level
    # head core ids include GStyle rows of its categories]
    want = {int(c) for c in categories}
    if want:
        for gid in doc.ids_of_class("GStyleElem"):
            v = doc.value(gid) or {}
            cat = v.get("m_categoryId")
            if cat in want and cat not in ctx.category_gstyles:
                ctx.category_gstyles[int(cat)] = int(gid)
            elif cat in want and v.get("m_gstyleType") == 1:
                ctx.category_gstyles[int(cat)] = int(gid)
        for c in sorted(want - set(ctx.category_gstyles)):
            ctx.notes.append(f"host has no GStyleElem for category {c}: "
                             f"that family's m_coreIds omit it")
    # solid patterns (universal host resources)
    fps = sorted(doc.ids_of_class("FillPatternElem"))
    lps = sorted(doc.ids_of_class("LinePatternElem"))
    ctx.fill_pattern_solid = fps[0] if fps else INVALID
    ctx.line_pattern_solid = lps[0] if lps else INVALID
    # usage referrers present in the host
    for cls in USAGE_FIELDS:
        try:
            ids = list(doc.ids_of_class(cls))
        except Exception:                                        # pragma: no cover
            ids = []
        if ids:
            ctx.usage_referrers[cls] = sorted(ids)
    return ctx


# ---------------------------------------------------------------------------
# the load plan (ids + correspondences) of ONE family
# ---------------------------------------------------------------------------

@dataclass
class LoadPlan:
    """Ids and correspondences of one family load."""
    key: str                                   # caller's family key
    guid: str                                  # our content-document GUID (== unit GUID)
    fam_doc_guid: str                          # host Family.m_famDocGUID (minted)
    session_guid_hex: str                      # 32-hex session guid for the twins' typeIds
    family_name: str
    category: int
    part_type: int
    type_names: List[str] = dc_field(default_factory=list)
    host_family_id: int = INVALID
    surrogate_id: int = INVALID
    symbol_ids: List[int] = dc_field(default_factory=list)         # one per type
    symbol_surrogate_ids: List[int] = dc_field(default_factory=list)
    twin_of: Dict[int, int] = dc_field(default_factory=dict)      # embedded param id -> host twin id
    abs_index: Dict[int, int] = dc_field(default_factory=dict)    # embedded elem id -> absorbed index
    core_ids: List[int] = dc_field(default_factory=list)
    doc_id_range: Tuple[int, int] = (0, 0)
    unit_records: int = 0
    episode: int = 0
    notes: List[str] = dc_field(default_factory=list)

    @property
    def symbol_id(self) -> int:
        return self.symbol_ids[0] if self.symbol_ids else INVALID

    @property
    def symbol_surrogate_id(self) -> int:
        return self.symbol_surrogate_ids[0] if self.symbol_surrogate_ids else INVALID

    def host_ids(self) -> List[int]:
        return sorted([x for x in ([self.host_family_id, self.surrogate_id]
                                   + list(self.symbol_ids)
                                   + list(self.symbol_surrogate_ids)
                                   + list(self.twin_of.values())) if x != INVALID])

    def as_json(self) -> dict:
        d = dataclasses.asdict(self)
        d["host_ids"] = self.host_ids()
        return d


@dataclass
class FamilyLoad:
    """One family to load: a NAME/key plus either a prebuilt ``FamilyDoc``
    (ids already ABOVE the host watermark) or a BUILDER
    ``callable(start_id) -> FamilyDoc`` the loader invokes with a free id
    block.  ``core_categories`` = the OST categories whose host GStyle rows
    the family binds as core ids (default: the doc's own category).
    """
    key: str
    builder: Optional[Callable[..., Any]] = None
    doc: Any = None
    core_categories: Optional[Sequence[int]] = None
    notes: List[str] = dc_field(default_factory=list)


def _plan_family(fl: FamilyLoad, doc, host: HostContext, cursor: int) -> Tuple[LoadPlan, int]:
    """Derive the LoadPlan of one finalized FamilyDoc; allocate the host
    element ids above the document's own ids.  Returns (plan, next cursor)."""
    if not doc.finalized:
        doc.finalize()
    sf = doc.self_family
    if sf is None:
        raise LoaderError(f"{fl.key}: family document has no self-Family")
    unit = doc.to_embedded_unit()
    guid = str(unit["content_doc_guid"])
    if doc.document_guid and str(doc.document_guid) != guid:
        raise LoaderError(f"{fl.key}: content GUID mismatch: doc "
                          f"{doc.document_guid} vs unit {guid}")
    ids = [e.elem_id for e in doc.elements]
    lo, hi = min(ids), max(ids)
    if lo <= host.watermark:
        raise LoaderError(f"{fl.key}: family document ids start at {lo} <= host "
                          f"watermark {host.watermark} (build above it)")
    # host symbol pairs for the REAL-named types only: a blank ' ' pair is the
    # family document's own current-values row (born blank-pair-first law,
    # kept inside the unit), never a host FamSymSurrogate/FamilySymbol and
    # never the symbol an instance binds [corpus law: 0/36 native host rows]
    from .famgen.loader import real_type_names
    type_names = real_type_names(doc) or [str(doc.name)]
    plan = LoadPlan(key=fl.key, guid=guid, fam_doc_guid=str(uuid.uuid4()),
                    session_guid_hex=uuid.uuid4().hex,
                    family_name=str(doc.name), category=int(doc.category_id),
                    part_type=int(getattr(doc, "part_type", 0)),
                    type_names=type_names, episode=int(host.episode),
                    doc_id_range=(int(lo), int(hi)),
                    unit_records=int(unit["record_count"]))
    # absorbed indices of OUR document (the self-Family's m_familyIds)
    fids = (((sf.obj.get("m_familyIds") or {}).get("value") or {}).get("m_data") or [])
    plan.abs_index = {int(e["m_elementId"]): int(e["m_index"]) for e in fids}
    # host ids: Family, param twins, FamilySurrogate, then per type a
    # FamSymSurrogate + FamilySymbol -- allocated ABOVE our document's ids so
    # the raised ElemTable watermark covers the embedded ids too (element ids
    # are unique file-wide) [V: rstbasic footer last_id 1,472,524 > every
    # embedded document id].
    nxt = [max(int(host.watermark), int(hi), int(cursor) - 1)]

    def alloc() -> int:
        nxt[0] += 1
        return nxt[0]
    plan.host_family_id = alloc()
    for e in doc.elements:
        if e.class_name in PARAM_TWIN_CLASSES:
            plan.twin_of[e.elem_id] = alloc()
    plan.surrogate_id = alloc()
    for _t in plan.type_names:
        plan.symbol_surrogate_ids.append(alloc())
        plan.symbol_ids.append(alloc())
    # core ids = the host category style rows the family binds (its own
    # category + any extra); a host without them binds nothing [H: the rme
    # panelboard binds its category GStyle + load classification; the level
    # head binds fill patterns / category GStyles / a material].
    cats = list(fl.core_categories) if fl.core_categories else [doc.category_id]
    core = set()
    for c in cats:
        g = host.category_gstyles.get(int(c))
        if g is not None:
            core.add(int(g))
        else:
            plan.notes.append(f"no host GStyleElem for category {c}: core-id binding omitted")
    plan.core_ids = sorted(core)
    return plan, nxt[0] + 1


# ---------------------------------------------------------------------------
# host-side record authoring (L4, the annotation-family flavour)
# ---------------------------------------------------------------------------

def _skel(elem_id: int, class_name: str, header: dict, obj: dict,
          rep: Optional[dict] = None, *, owner_id: int = -1, kind: str = ""):
    from .genesis.skeleton import SkelElement
    return SkelElement(elem_id, class_name, header, obj, rep,
                       owner_id=owner_id, kind=kind)


def _header(class_name: str, *, category: int = -1, family_id: int = -1,
            deletion: Sequence[int] = (), regen_only: Sequence[int] = (),
            appearance: Sequence[int] = (), bbox=None) -> dict:
    from .genesis.skeleton import element_header
    flags, vflags = HDR_FLAGS.get(class_name, (10, -32768))
    return element_header(class_name, category=category, family_id=family_id,
                          deletion=sorted({int(x) for x in deletion if int(x) not in (0,)}),
                          regen_only=sorted({int(x) for x in regen_only}),
                          appearance=sorted({int(x) for x in appearance}),
                          flags=flags, visible_view_flags=vflags, bbox=bbox)


def author_param_twins(doc, plan: LoadPlan) -> List:
    """One host ``ParamElemFamily`` TWIN per family user parameter [VERIFIED
    rstbasic 1390073 vs its embedded counterpart 1393111]: the document's own
    parameter object with m_id / m_pParamDef.m_paramElemId -> the host id,
    m_famId -> the host Family, m_typeId -> the host-local family type id;
    m_designOptionId KEEPS the family-document -4 (the host twin carries -4
    too).  Header {family_id = host Family, deletion [Family, self]}.

    A SHARED parameter (``ParamElemExternal``) twins as its own class with
    the same id / owner rewrites but KEEPS its ``revit.local.shared:<guid>``
    typeId and ``m_externalParamKey`` GUID verbatim -- the identity a
    schedule binds by is never re-minted [UNVERIFIED host-side: the host's
    ``ExternalParamTracking`` registration is the open follow-up].
    """
    out = []
    hf = plan.host_family_id
    for e in doc.elements:
        if e.class_name not in PARAM_TWIN_CLASSES:
            continue
        tid = plan.twin_of[e.elem_id]
        obj = _dc(e.obj)
        obj["m_id"] = tid
        obj["m_famId"] = hf
        pd = ((obj.get("m_pParamDef") or {}).get("value") or {})
        pd["m_paramElemId"] = tid
        if e.class_name == "ParamElemFamily":       # session identity -> host-local
            local_id = (f"revit.local.family:{plan.session_guid_hex}"
                        f"{tid & 0xFFFFFFFF:08x}-1.0.0")
            tt = pd.get("m_typeId")
            if isinstance(tt, dict):
                tt["m_typeId"] = local_id
            else:
                pd["m_typeId"] = {"m_typeId": local_id}
        hdr = _header(e.class_name, category=-1, family_id=hf,
                      deletion=[hf, tid])
        el = _skel(tid, e.class_name, hdr, obj, None, owner_id=hf,
                   kind="param_twin")
        el.notes.append(f"twin of embedded param {e.elem_id} "
                        f"({(pd.get('m_caption') or '')!s})")
        out.append(el)
    return out


def author_family_surrogate(plan: LoadPlan):
    """The ``FamilySurrogate`` [VERIFIED rstbasic 1388865]."""
    from .genesis.types import blank_object
    o = blank_object("FamilySurrogate")
    o.update({
        "m_docAccess": {"m_pDoc": _weak(1)},
        "m_id": plan.surrogate_id,
        "m_assocLevelId": -1, "m_famId": -1, "m_unplacedOwnerId": -1,
        "m_ownerDBViewId": -1, "m_createdPhaseId": -1, "m_demolishedPhaseId": -1,
        "m_designOptionId": -1, "m_locked": False, "m_moribund": False,
        "m_dummy": False,
        "m_pADoc": _weak(1),
        "m_elemId": plan.host_family_id,
        "m_name": plan.family_name,
        "m_categoryId": int(plan.category),
        "m_previewElemId": -1,
        "m_guid": {"m_guid": SURROGATE_GUID},
        "m_bIsAdaptive": False,
    })
    hdr = _header("FamilySurrogate", deletion=[plan.host_family_id, plan.surrogate_id])
    return _skel(plan.surrogate_id, "FamilySurrogate", hdr, o, None,
                 kind="family_surrogate")


def author_famsym_surrogates(plan: LoadPlan) -> List:
    """One ``FamSymSurrogate`` per symbol [VERIFIED rstbasic 1417014]:
    {m_elemId = symbol, m_name = type name, m_categoryId, m_famSurrogateId};
    header deletion [surrogate, self, symbol], regenOnly [Family]."""
    from .genesis.types import blank_object
    out = []
    for tname, sym, ssur in zip(plan.type_names, plan.symbol_ids,
                                plan.symbol_surrogate_ids):
        o = blank_object("FamSymSurrogate")
        o.update({
            "m_docAccess": {"m_pDoc": _weak(1)},
            "m_id": ssur,
            "m_assocLevelId": -1, "m_famId": -1, "m_unplacedOwnerId": -1,
            "m_ownerDBViewId": -1, "m_createdPhaseId": -1, "m_demolishedPhaseId": -1,
            "m_designOptionId": -1, "m_locked": False, "m_moribund": False,
            "m_dummy": False,
            "m_pADoc": _weak(1),
            "m_elemId": sym,
            "m_name": tname,
            "m_categoryId": int(plan.category),
            "m_famSurrogateId": plan.surrogate_id,
        })
        hdr = _header("FamSymSurrogate",
                      deletion=[plan.surrogate_id, ssur, sym],
                      regen_only=[plan.host_family_id])
        out.append(_skel(ssur, "FamSymSurrogate", hdr, o, None,
                         kind="famsym_surrogate"))
    return out


def _remap_param_rows(rows: List[dict], twin_of: Dict[int, int]) -> List[dict]:
    out = []
    for r in rows or []:
        r2 = _dc(r)
        pid = r2.get("m_paramId")
        if isinstance(pid, int) and pid in twin_of:
            r2["m_paramId"] = twin_of[pid]
        eid = r2.get("m_elemId")
        if isinstance(eid, int) and eid in twin_of:
            r2["m_elemId"] = twin_of[eid]
        out.append(r2)
    return out


def _current_type_rows(doc) -> List[dict]:
    """The current type's parameter rows (family-document keyed)."""
    sf = doc.self_family
    ftt = ((sf.obj.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = ftt.get("m_pairs") or []
    idx = doc.current_type if pairs and doc.current_type < len(pairs) else 0
    if pairs:
        return _dc(list((pairs[idx].get("params") or {}).get("m_params") or []))
    fp = ((sf.obj.get("m_familyParams") or {}).get("value") or {})
    return _dc(list(fp.get("m_params") or []))


def _type_rows_by_name(doc) -> Dict[str, List[dict]]:
    sf = doc.self_family
    ftt = ((sf.obj.get("m_pFamilyTypes") or {}).get("value") or {})
    out: Dict[str, List[dict]] = {}
    for pr in ftt.get("m_pairs") or []:
        out[str(pr.get("name"))] = _dc(list((pr.get("params") or {}).get("m_params") or []))
    return out


def _reference_idx_mgr(doc, plan: LoadPlan) -> Optional[dict]:
    """``FamilyReferenceIdxMgr``: origin reference planes' ABSORBED indices
    -> (Is-Reference code, name) [VERIFIED shape rstbasic 1388845: keys 4/5 =
    the origin planes' m_familyIds indices, code 10, name '' for the head
    families]."""
    entries = []
    for e in doc.elements:
        if e.class_name != "RefPlane":
            continue
        v = e.obj or {}
        if not v.get("m_definesOrigin"):
            continue
        ai = plan.abs_index.get(e.elem_id)
        if ai is None:
            continue
        entries.append({"first": int(ai), "second": {"first": 10, "second": ""}})
    if not entries:
        return None
    entries.sort(key=lambda d: d["first"])
    return _ptr("FamilyReferenceIdxMgr", {"m_idxToRefMap": entries})


def author_host_family(doc, plan: LoadPlan) :
    """The HOST ``Family`` = OUR self-Family transformed to the host
    (annotation) flavour [rules VERIFIED on rstbasic 1388845 vs its embedded
    self-Family 1393105; the parameter/type remapping is the same transform
    the asset-forge stream decoded on the rme panelboard host family]."""
    from .famgen.geometry import assign_pids
    sf = doc.self_family
    o = _dc(sf.obj)
    idmap = dict(plan.twin_of)
    idmap[sf.elem_id] = plan.host_family_id
    o["m_id"] = plan.host_family_id
    o["m_famId"] = -1
    o["m_designOptionId"] = -1
    o["m_name"] = plan.family_name
    o["m_famDocGUID"] = plan.fam_doc_guid
    o["m_surrogateId"] = plan.surrogate_id
    o["m_path"] = ""                                     # ours (no authoring path)
    o["m_partType"] = int(plan.part_type)
    for k in ("m_omniClassCode", "m_classificationDescription", "m_seekItemId",
              "m_familyNameKeyText", "m_dumpSymName", "m_structuralCodeName",
              "m_protectionAccessKey"):
        if k in o:
            o[k] = ""
    # -- current parameter values (m_familyParams) keyed by the host twins --
    cur_rows = _remap_param_rows(_current_type_rows(doc), idmap)
    fp = ((o.get("m_familyParams") or {}).get("value") or {})
    if fp is not None and isinstance(fp, dict):
        fp["m_params"] = _dc(cur_rows)
        fp.setdefault("m_geomRefHandles", {"m_offsetGeomMap": []})
    else:                                                          # pragma: no cover
        o["m_familyParams"] = _ptr("FamilyParams", {
            "m_params": _dc(cur_rows), "m_geomRefHandles": {"m_offsetGeomMap": []}})
    # -- host FamilyTypeTable: ONE leading blank ' ' row (= current values);
    #    an annotation family's types live as FamilySymbols [V rstbasic] -----
    ftt = ((o.get("m_pFamilyTypes") or {}).get("value") or {})
    blank_row = {"name": " ", "params": {"m_params": _dc(cur_rows),
                                         "m_geomRefHandles": {"m_offsetGeomMap": []}}}
    if isinstance(ftt, dict) and ftt:
        ftt["m_pairs"] = [blank_row]
        ftt["m_idx"] = 0
    else:
        o["m_pFamilyTypes"] = _ptr("FamilyTypeTable", {"m_idx": 0, "m_pairs": [blank_row]})
    # -- cells: the parameter-order cell(s), param ids -> twins -------------
    cl = ((o.get("m_cellList") or {}).get("value") or {})
    cells = list(cl.get("m_cells") or []) if cl else []
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        if isinstance(cv.get("m_sortedParams"), list):
            new = []
            for x in cv["m_sortedParams"]:
                if isinstance(x, int):
                    new.append(idmap.get(x, x))
                elif isinstance(x, dict):
                    x2 = _dc(x)
                    if isinstance(x2.get("m_paramIds"), list):
                        x2["m_paramIds"] = [idmap.get(y, y) if isinstance(y, int) else y
                                            for y in x2["m_paramIds"]]
                    new.append(x2)
                else:
                    new.append(x)
            cv["m_sortedParams"] = new
    o["m_cellList"] = _ptr("CellList", {"m_cells": cells})
    # -- locked / trivial param ids -> twins ------------------------------------
    lk = o.get("m_lockedParameterIdsForDirectManipulation")
    if isinstance(lk, list):
        o["m_lockedParameterIdsForDirectManipulation"] = sorted(
            {idmap.get(x, x) for x in lk if isinstance(x, int)})
    tp = o.get("m_trivialParamIds")
    if isinstance(tp, list):
        o["m_trivialParamIds"] = [idmap.get(x, x) for x in tp if isinstance(x, int)]
    # -- m_oFamDoc: content GUID + big2small (host twin -> embedded param) --
    big2small = [{"first": int(t), "second": {"m_id64": int(p)}}
                 for p, t in sorted(plan.twin_of.items(), key=lambda kv: kv[1])]
    o["m_oFamDoc"] = _ptr("FamilyDocument", {
        "m_contentDocGUID": plan.guid,
        "m_big2SmallMap2": big2small,
        "m_coreIds": list(plan.core_ids),
    })
    # -- m_familyIds: the host twins with their embedded absorbed indices --
    fids = []
    for p, t in sorted(plan.twin_of.items(), key=lambda kv: kv[1]):
        ai = plan.abs_index.get(p)
        if ai is None:
            continue
        fids.append({"m_elementId": int(t), "m_index": int(ai)})
    o["m_familyIds"] = _ptr("ElementIdIndexPairSet", {"m_data": fids})
    # -- host-only members ------------------------------------------------------
    o["m_dbviewInfos"] = [_ptr("DBViewInfoForPreview", _dc(ANNOTATION_PREVIEW_VIEW))]
    o["m_oFamilyReferenceIdxMgr"] = _reference_idx_mgr(doc, plan)
    o["m_defaultHostThickness"] = -1e30
    o["m_defaultHeightAboveLevel"] = -1e30
    # -- family-document-only state emptied (annotation flavour keeps the
    #    empty FamDimConstrMgr) ------------------------------------------------
    o["m_fsdos"] = []
    o["m_refs"] = []
    o["m_deletableElements"] = []
    o["m_oldCurveElemsWithBadSketchAndSP"] = []
    # -- archive object numbering (owned pointers registered as on the specimen)
    assign_pids(o)
    # -- header: deletion = core ids + twins + surrogate + self (the specimen
    #    also lists its family-scoped host children -- ours has none) --------
    deletion = set(plan.core_ids) | set(plan.twin_of.values())
    deletion |= {plan.host_family_id, plan.surrogate_id}
    hdr = _header("Family", category=-1, deletion=sorted(deletion))
    el = _skel(plan.host_family_id, "Family", hdr, o, None, kind="host_family")
    el.notes.append("host Family = our self-Family transformed (annotation flavour)")
    return el


def author_family_symbols(doc, plan: LoadPlan) -> List:
    """One host ``FamilySymbol`` per family TYPE [VERIFIED shape rstbasic
    1417017 'M_Level Head - Circle']: the type row keyed by the twins, the
    symbol-info name, m_familyId, m_partitionSurrogateId, the pattern-helper
    cell, an empty move-restriction Matrix, an annotation-plane outline;
    the seq-103 rep is a SerializedDummy (the symbol graphics regenerate from
    the family document [ACCEPTANCE H]) and the geometry bookkeeping
    (m_geomSteps / m_pGeomTable / m_refFaces / m_tagNoteData) stays empty."""
    from .genesis.types import blank_object
    out = []
    rows_by_type = _type_rows_by_name(doc)
    cur = _current_type_rows(doc)
    for i, (tname, sym, ssur) in enumerate(zip(plan.type_names, plan.symbol_ids,
                                              plan.symbol_surrogate_ids)):
        rows = rows_by_type.get(tname) or (cur if i == 0 else [])
        rows = _remap_param_rows(rows, plan.twin_of)
        o = blank_object("FamilySymbol")
        o.update({
            "m_pParamValueSetDouble": None, "m_pParamValueSetInt": None,
            "m_pParamValueSetAString": None, "m_pParamValueSetElementId": None,
            "m_geomSteps": None, "m_pGeomTable": None, "m_constrInfo": [],
            "m_cellList": _ptr("CellList", {"m_cells": [
                _ptr("FamilySymbolPatternHelper",
                     {"m_PatternPositionMap": [], "m_substituteFaceMap": []})]}),
            "m_docAccess": {"m_pDoc": _weak(1)},
            "m_id": sym,
            "m_assocLevelId": -1, "m_famId": -1, "m_unplacedOwnerId": -1,
            "m_ownerDBViewId": -1, "m_createdPhaseId": -1, "m_demolishedPhaseId": -1,
            "m_designOptionId": -1, "m_locked": False, "m_moribund": False,
            "m_dummy": False,
            "m_symbolInfo": _ptr("SymbolInfo", {"m_name": tname}),
            "m_renderStyleId": -1, "m_previewElemId": -1,
            "m_pCutLoops": [], "m_cutDirs": [], "m_cutIndices": [],
            "m_pParams": _ptr("FamilyParams", {
                "m_params": rows, "m_geomRefHandles": {"m_offsetGeomMap": []}}),
            "m_controlIcons": [], "m_controlIconTags": [],
            "m_textNoteData": [], "m_tagNoteData": [],
            "m_refs": [], "m_refFaces": [],
            "m_handleMgr": {"m_handleArr": [], "m_handleDimArr": [], "m_handleMap": []},
            "m_pMoveRestrictions": _ptr("Matrix", {
                "m_nRows": 0, "m_ncols": 3, "m_bUseSingleArray": True,
                "m_arr": [], "m_rows": []}),
            "m_closurePlanes": [], "m_gTagDirFlagsPairs": [], "m_nonBRepGeomPtrs": [],
            "m_oArrMembHistTable": None,
            "m_outline": {"m_minmax": [[-0.02, -0.02, 0.0], [0.02, 0.02, 0.0]]},
            "m_origin": [0.0, 0.0, 0.0], "m_rotCenter": [0.0, 0.0, 0.0],
            "m_cutPlaneHeights": [0.0, 0.0],
            "m_familyId": plan.host_family_id,
            "m_masterId": -1, "m_slaveTrackerId": -1,
            "m_partitionSurrogateId": ssur,
            "m_ownerInstanceId": -1, "m_stretchPrototypeId": -1,
            "m_stretchCount": 0, "m_geomTagOfDummyCurveRef": -1,
            "m_idxOfFirstCoreLayerRefFace": -1,
            "m_hasParamDefValue": 1, "m_faceBasedHostNormal": 0,
            "m_mirrored": False, "m_bHostLayersFlippedY": False,
            "m_active": True, "m_preview": False, "m_hasRotCenter": False,
            "m_visibilityIsOld": False, "m_bMayBeStretchable": False,
            "m_bConfirmedStretchable": False, "m_bHasNothingVisible": False,
            "m_bCantBeStretched": False,
            "m_labelParamTagInfo": [], "m_complexCutRefIds": [], "m_complexCutGeoms": [],
            "m_dummyHostGeoms": [], "m_dummyHostCutFaceTags": [],
            "m_dummyHostInsertionFaceTags": [], "m_strongRefs": [],
            "m_setOfInPlaceTotalParentIds": [], "m_notRotatedNodes": [],
            "m_lightSrcParamIds": [], "m_lightSrcGReps": [], "m_lightSrcValues": [],
            "m_arrProfileLoops": [], "m_pretaggingGNodes": [],
            "m_pretaggingTranslations": [], "m_arrConnectorData": [],
            "m_arrFamSymRegenData": [], "m_flippedGeomRefHandlesSet": [],
            "m_subInstData": [], "m_subElemData": [], "m_imposterLightTrfs": [],
            "m_oFamMoveRestrictions": None, "m_geomTag2MaterialId": [],
        })
        deletion = {plan.host_family_id, ssur, sym} | set(plan.twin_of.values())
        hdr = _header("FamilySymbol", category=int(plan.category),
                      deletion=sorted(deletion),
                      bbox=([-0.02, -0.02, 0.0], [0.02, 0.02, 0.0]))
        el = _skel(sym, "FamilySymbol", hdr, o, None, kind="family_symbol")
        el.notes.append("annotation symbol: SerializedDummy rep (graphics regenerate "
                        "from the family document); geometry bookkeeping empty [H]")
        out.append(el)
    return out


def author_host_elements(doc, plan: LoadPlan) -> List:
    """All host-side elements of one loaded family, sorted by id."""
    els: List = []
    els.extend(author_param_twins(doc, plan))
    els.append(author_family_surrogate(plan))
    els.append(author_host_family(doc, plan))
    els.extend(author_family_symbols(doc, plan))
    els.extend(author_famsym_surrogates(plan))
    els.sort(key=lambda e: e.elem_id)
    return els


# ---------------------------------------------------------------------------
# the host ADocument registrations (L5)
# ---------------------------------------------------------------------------

def _appinfo_slot(value: dict, class_name: str) -> Optional[dict]:
    mgr = (value.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") == class_name:
            return x.get("value")
    return None


def register_in_host_adocument(latest_value: dict, plans: Sequence[LoadPlan], *,
                                author: str = PRODUCT_NAME) -> Dict[str, Any]:
    """Edit the decoded host ``ADocument`` value IN PLACE with, per plan,
    the ContentTable record and the FamilyMgr loaded-family entry (the two
    ADocument registries of a loaded document), plus ElementTrackingData
    symbol tracking WHEN the host already tracks that category [VERIFIED
    record / entry shapes on rstbasic + the rme host]."""
    rep: Dict[str, Any] = {"content_table_records": None,
                           "family_mgr_entries": None,
                           "element_tracking": {}}
    # 1. ContentTable
    ct = ((latest_value.get("m_oContentTable") or {}).get("value") or {})
    recs = ct.get("m_ContentRecSet")
    if not isinstance(recs, list):
        raise LoaderError("host ContentTable.m_ContentRecSet is not a list")
    existing = {str((r.get("m_ContentKey") or {}).get("m_guidKey") or "").lower()
                for r in recs}
    for plan in plans:
        if plan.guid.lower() in existing:
            raise LoaderError(f"content GUID {plan.guid} already registered in the host")
        ep = int(plan.episode)
        recs.append({
            "m_pHostDocument": _weak(1),
            "m_ContentKey": {"m_guidKey": plan.guid},
            "m_author": author,
            "m_history": {"m_originalElementId": {"m_id64": -1},
                          "m_creationDate": {"m_id": ep},
                          "m_lastModificationDate": {"m_id": ep},
                          "m_lastUserModificationDate": {"m_id": -1}},
            "m_EpisodeCounts": [{"first": {"m_id": ep},
                                 "second": int(plan.unit_records)}],
        })
    # keep the specimen's order: records sorted by GUID key [V rstbasic /
    # rme ContentTable records are in ascending GUID order like the CD stream]
    recs.sort(key=lambda r: uuid.UUID(
        str((r.get("m_ContentKey") or {}).get("m_guidKey"))).bytes_le)
    rep["content_table_records"] = len(recs)
    # 2. FamilyMgr (AppInfo slot 0)
    fm = _appinfo_slot(latest_value, "FamilyMgr")
    if fm is None:
        raise LoaderError("host ADocument has no FamilyMgr appinfo (slot 0)")
    lfi = fm.setdefault("m_arrLoadedFamilyInfo", [])
    for plan in plans:
        lfi.append({"m_surrogateId": int(plan.surrogate_id),
                    "m_familyDocGUIDs": [plan.guid]})
    lfi.sort(key=lambda e: int(e.get("m_surrogateId", 0)))
    rep["family_mgr_entries"] = len(lfi)
    # 3. ElementTrackingData -- ONLY into an EXISTING category row (rstbasic
    #    does not track annotation-head symbols) [conservative]
    etd = _appinfo_slot(latest_value, "ElementTrackingData")
    if etd is not None:
        arr = etd.get("m_symbols") or []
        for plan in plans:
            row = next((x for x in arr
                        if x.get("m_categoryId") == int(plan.category)), None)
            if row is None:
                rep["element_tracking"][str(plan.category)] = "no host row (skipped)"
                continue
            s = row.setdefault("m_elemIdSet", [])
            for sid in plan.symbol_ids:
                if int(sid) not in s:
                    s.append(int(sid))
            s.sort()
            rep["element_tracking"][str(plan.category)] = len(s)
    else:
        rep["element_tracking"] = "absent (skipped)"
    return rep


# ---------------------------------------------------------------------------
# usage repointing (the third pass): point the host's usage fields at OUR
# symbols through rvt.manipulate's certified modify path
# ---------------------------------------------------------------------------

@dataclass
class UsageRepoint:
    """Point ``referrer_class.field`` (an existing host element's usage
    field) at the FIRST symbol of the loaded family ``family_key``.
    ``referrer_id`` = a specific element (else EVERY element of the class);
    ``old_symbol_id`` (optional) is dropped from the referrer's header
    deletion list; the new symbol is added to it [V rstbasic LevelAttributes
    305 lists its head symbol in m_parents.m_deletion]."""
    referrer_class: str
    field: str
    family_key: str
    referrer_id: Optional[int] = None
    old_symbol_id: Optional[int] = None
    type_index: int = 0
    #: True = only replace fields that currently name SOMETHING (>= 0):
    #: "switch the existing head to ours" (L1b / L2).  False = also set
    #: fields that are -1 ("give the type a head", the L3 case).
    only_if_set: bool = True


def repoint_usage(src_rvt: str, out_rvt: str, repoints: Sequence[UsageRepoint],
                  symbol_of_key: Dict[str, List[int]]) -> Dict[str, Any]:
    """Apply ``repoints`` to ``src_rvt`` -> ``out_rvt``: each referrer's usage
    field := our symbol id, and the symbol id added to (any old symbol dropped
    from) the referrer's seq-101 ``m_parents.m_deletion``.  Records are
    re-encoded byte-exact with recomputed stamps (rvt.manipulate M3 path)."""
    from .mutate import Document
    from . import manipulate as MP
    doc = Document.from_file(src_rvt)
    sess = MP.session(doc)
    sess.plans.clear()
    log: List[dict] = []
    plans: List = []
    for rp in repoints:
        syms = symbol_of_key.get(rp.family_key) or []
        if not syms:
            log.append({"repoint": rp.family_key, "error": "no symbol loaded for key"})
            continue
        sym = syms[min(rp.type_index, len(syms) - 1)]
        targets = ([rp.referrer_id] if rp.referrer_id is not None
                   else list(doc.ids_of_class(rp.referrer_class)))
        for rid in targets:
            entry = {"referrer": rid, "class": rp.referrer_class,
                     "field": rp.field, "symbol": sym}
            try:
                val = sess.value(rid, 102)
                old = val.get(rp.field)
                entry["old_value"] = old
                if rp.field not in val:
                    entry["skipped"] = "field absent"
                    log.append(entry)
                    continue
                if rp.only_if_set and not (isinstance(old, int) and old >= 0):
                    entry["skipped"] = "field unset (-1) and only_if_set"
                    log.append(entry)
                    continue
                val[rp.field] = int(sym)
                pl = MP.ModifyPlan(kind="repoint-usage", elem_id=rid,
                                   class_name=doc.class_of(rid))
                pl.changes.append(MP.FieldChange(102, rp.field, old, int(sym)))
                pl.record_edits.append(sess.replacement(
                    rid, 102, f"usage {rp.field} -> our symbol {sym}"))
                # header deletion list: add our symbol (drop the old one)
                hdr = sess.value(rid, 101)
                par = ((hdr.get("m_parents") or {}).get("value") or {})
                dele = par.get("m_deletion")
                if isinstance(dele, list):
                    newd = [int(x) for x in dele
                            if not (rp.old_symbol_id is not None
                                    and int(x) == int(rp.old_symbol_id))
                            and not (old is not None and isinstance(old, int)
                                     and old >= 0 and int(x) == int(old))]
                    if int(sym) not in newd:
                        newd.append(int(sym))
                    par["m_deletion"] = sorted(newd)
                    pl.changes.append(MP.FieldChange(101, "m_parents.value.m_deletion",
                                                     dele, par["m_deletion"]))
                    pl.record_edits.append(sess.replacement(
                        rid, 101, f"deletion += our symbol {sym}"))
                    entry["deletion_added"] = int(sym)
                plans.append(pl)
                entry["ok"] = True
            except Exception as ex:                     # left as-is, reported
                entry["error"] = f"{type(ex).__name__}: {ex}"
            log.append(entry)
    if not plans:
        return {"edits": log, "written": False}
    MP.commit_plans(src_rvt, out_rvt, plans)
    ver = MP.verify_manipulated(out_rvt, edited_ids=[p.elem_id for p in plans])
    return {"edits": log, "written": True, "plans": len(plans),
            "verify": {k: ver.get(k) for k in ("crc_failures", "ecc_mismatches",
                                                   "walker_errors", "stamps_ok",
                                                   "elemtable_count",
                                                   "isize_identity_mismatches")}}


# ---------------------------------------------------------------------------
# the LOADER: N families into one project, one write (three passes)
# ---------------------------------------------------------------------------

@dataclass
class LoadResult:
    ok: bool
    out_path: Optional[str]
    plans: List[LoadPlan]
    proofs: Dict[str, Any]
    acceptance: List[str]
    stop_reason: str = ""
    seconds: float = 0.0

    def symbols_by_key(self) -> Dict[str, List[int]]:
        return {p.key: list(p.symbol_ids) for p in self.plans}

    def as_json(self) -> dict:
        return {"ok": self.ok, "out_path": (_relp(self.out_path) if self.out_path else None),
                "plans": [p.as_json() for p in self.plans],
                "proofs": self.proofs, "acceptance": self.acceptance,
                "stop_reason": self.stop_reason, "seconds": self.seconds}


def _resolve_docs(families: Sequence[FamilyLoad], host: HostContext) -> List[Tuple[FamilyLoad, Any, LoadPlan]]:
    """Build every family document in its own id block ABOVE the host
    watermark, then plan its host ids above the document's ids."""
    out = []
    cursor = int(host.watermark) + 1
    for fl in families:
        if fl.doc is not None:
            doc = fl.doc
            if not doc.finalized:
                doc.finalize()
        elif fl.builder is not None:
            doc = fl.builder(start_id=cursor)
            if not doc.finalized:
                doc.finalize()
        else:
            raise LoaderError(f"{fl.key}: FamilyLoad needs a doc or a builder")
        plan, cursor = _plan_family(fl, doc, host, cursor)
        # leave a round-number gap before the next family's document block
        cursor = ((cursor + 99) // 100) * 100 + 1
        out.append((fl, doc, plan))
    return out


def _roundtrip_gate(elements) -> Dict[str, Any]:
    from .genesis.skeleton import roundtrip_report
    return roundtrip_report(elements)


def load_family_documents(host_rvt: str, families: Sequence[FamilyLoad],
                          out_rvt: Optional[str], *,
                          repoints: Sequence[UsageRepoint] = (),
                          validate: bool = True,
                          report_path: Optional[str] = None,
                          identity: Optional[dict] = None) -> LoadResult:
    """LOAD every family of ``families`` into a copy of ``host_rvt``,
    writing ``out_rvt`` (a project); apply ``repoints`` after; verify.

    Every family becomes: an embedded save unit + a ContentDocuments entry
    + a ContentTable record + a FamilyMgr entry (the FOUR REGISTRIES,
    coherent by construction), plus its host Family / FamilySymbol(s) /
    surrogates / ParamElemFamily twins in save-unit 0 + ElemTable rows.
    ``out_rvt=None`` = dry run (everything authored + gated, no file).

    Runs under the HOST's own release (``rvt.frontdoor.release_ctx.
    host_release_context`` -- issue #14); a native host enters no context.
    """
    from .frontdoor.release_ctx import host_release_context
    with host_release_context(host_rvt):
        return _load_family_documents(host_rvt, families, out_rvt,
                                      repoints=repoints, validate=validate,
                                      report_path=report_path, identity=identity)


def _load_family_documents(host_rvt: str, families: Sequence[FamilyLoad],
                           out_rvt: Optional[str], *,
                           repoints: Sequence[UsageRepoint], validate: bool,
                           report_path: Optional[str],
                           identity: Optional[dict]) -> LoadResult:
    from .famgen import factory as F
    from .encode import encode_record
    from .commit import commit_new_elements
    from .container import open_rvt
    from .adocument import decode_latest, encode_latest
    from .roundtrip import read_entries
    from .cfb_writer import write_cfb
    from .stream_encoders import wrap_global_stream
    from . import ecc

    t0 = time.time()
    proofs: Dict[str, Any] = {}
    acceptance: List[str] = []
    cats: List[int] = []
    for fl in families:
        if fl.doc is not None:
            cats.append(int(fl.doc.category_id))
        for c in (fl.core_categories or []):
            cats.append(int(c))
    host = survey_host(host_rvt, categories=cats)
    proofs["host"] = {
        "path": _relp(host_rvt), "watermark": host.watermark,
        "episode": host.episode, "partition": host.partition_name,
        "elements": len(host.doc.et_by_id),
        "category_gstyles": {str(k): v for k, v in host.category_gstyles.items()},
        "usage_referrers": host.usage_referrers,
        "registries_before": {k: host.census_before.get(k) for k in (
            "save_units", "contentdocs_entries", "contenttable_records",
            "familymgr_entries", "coherent")},
        "notes": host.notes,
    }
    # ---------------- build the documents + plan the ids ------------------
    triples = _resolve_docs(list(families), host)
    plans = [p for _f, _d, p in triples]
    proofs["plans"] = [p.as_json() for p in plans]
    # ---------------- author the host elements of every family ----------------
    all_els = []
    per_family_elements: Dict[str, List[dict]] = {}
    for fl, doc, plan in triples:
        els = author_host_elements(doc, plan)
        all_els.extend(els)
        per_family_elements[fl.key] = [
            {"elem_id": e.elem_id, "class": e.class_name, "kind": e.kind,
             "owner_id": e.owner_id, "notes": list(e.notes)} for e in els]
    all_els.sort(key=lambda e: e.elem_id)
    proofs["host_elements"] = {"count": len(all_els), "by_family": per_family_elements}
    # roundtrip gate: every authored record encodes + decodes back byte-exact
    gate = _roundtrip_gate(all_els)
    proofs["roundtrip_gate"] = gate
    if gate.get("failed", 1) != 0 or gate.get("roundtrip_ok", 0) != gate.get("records", -1):
        raise LoaderError("a host record failed the encode/decode round trip: "
                          f"{gate.get('failures', [])[:8]}")
    # ---------------- L3: every embedded ADocument + L2: every save unit ------
    units: Dict[str, dict] = {}
    adocs: Dict[str, dict] = {}
    for fl, doc, plan in triples:
        ad = F.author_embedded_adocument(doc, episode=plan.episode,
                                         document_guid=plan.guid)
        unit = F.build_family_save_unit(doc)
        if str(unit["guid"]) != plan.guid:
            raise LoaderError(f"{fl.key}: save unit GUID {unit['guid']} != {plan.guid}")
        if int(unit["record_count"]) != plan.unit_records:
            plan.unit_records = int(unit["record_count"])
        adocs[fl.key] = ad
        units[fl.key] = unit
    proofs["embedded"] = {
        fl.key: {"adocument_self_check": dict(adocs[fl.key]["self_check"]),
                 "save_unit": {"guid": units[fl.key]["guid"],
                               "records": units[fl.key]["record_count"],
                               "bytes": len(units[fl.key]["bytes"]),
                               "segments": units[fl.key]["segments"]}}
        for fl, _d, _p in triples}
    if out_rvt is None:
        return LoadResult(ok=False, out_path=None, plans=plans, proofs=proofs,
                          acceptance=acceptance,
                          stop_reason="dry run (out_rvt=None): no file emitted",
                          seconds=round(time.time() - t0, 1))

    os.makedirs(os.path.dirname(os.path.abspath(out_rvt)) or ".", exist_ok=True)
    tmp1 = out_rvt + ".pass1.tmp"
    tmp2 = out_rvt + ".pass2.tmp"
    for t in (tmp1, tmp2):
        if os.path.exists(t):
            os.remove(t)

    # ---------------- PASS 1: host elements into save unit 0 -----------------
    recs = []
    new_els = []
    for e in all_els:
        ne = e.as_new_element(creation_ep=host.episode)
        recs.append({seq: encode_record(seq, ne.elem_id, None, cid, obj)
                     for seq, cid, obj in ne.records()})
        new_els.append(ne)
    crep = commit_new_elements(host_rvt, tmp1, recs,
                               [ne.elemrec for ne in new_els],
                               creation_ep=host.episode,
                               identity=dict(identity or {"username": ""}))
    proofs["pass1_commit"] = {
        "new_element_ids": list(crep.new_element_ids),
        "elemtable_count_before": crep.elemtable_count_before,
        "elemtable_count_after": crep.elemtable_count_after,
        "watermark_after": crep.watermark_after,
        "per_seq_bytes_added": dict(crep.per_seq_bytes_added),
    }
    max_needed = max(p.doc_id_range[1] for p in plans)
    if int(crep.watermark_after) < max_needed:
        raise LoaderError(f"ElemTable watermark {crep.watermark_after} does not cover "
                          f"the embedded documents' max id {max_needed}")

    # ---------------- PASS 2: units + ContentDocuments + host ADocument -----
    with open_rvt(tmp1) as f2:
        part_logical = f2.logical(host.partition_name)
        cd_payload = b"".join(f2.inflate_all("Global/ContentDocuments"))
        latest_payload = f2.inflate("Global/Latest")
    # splice every unit (each before the end record; sequential)
    splice_reports = {}
    logical = part_logical
    for fl, _doc, plan in triples:
        sp = F.splice_save_unit(logical, units[fl.key]["bytes"])
        w = sp["walker"]
        splice_reports[fl.key] = {
            "units_before": w["units_before"], "units_after": w["units_after"],
            "walker_errors": w["errors"], "our_unit_guid": w["our_unit_guid"],
            "our_unit_records": w["our_unit_records"],
            "id_sets_identical": w["id_sets_identical"]}
        if w["errors"] or w["units_after"] != w["units_before"] + 1:
            raise LoaderError(f"{fl.key}: partition splice failed: {w['errors'][:3]}")
        if str(w["our_unit_guid"]) != plan.guid:
            raise LoaderError(f"{fl.key}: spliced unit GUID {w['our_unit_guid']} != {plan.guid}")
        logical = sp["logical"]
    proofs["pass2_partition_splices"] = splice_reports
    # ContentDocuments: insert every entry (GUID-sorted merge)
    cd_new = cd_payload
    for fl, _doc, plan in triples:
        cd_new = F.insert_content_document(cd_new, plan.guid, adocs[fl.key]["payload"])
    ents_before, tail_before = F.parse_content_documents(cd_payload)
    ents_after, tail_after = F.parse_content_documents(cd_new)
    present = {g for g, _a in ents_after}
    proofs["pass2_content_documents"] = {
        "entries_before": len(ents_before), "entries_after": len(ents_after),
        "ours_all_present": all(p.guid in present for p in plans),
        "end_record_intact": tail_after == (tail_before or F.CD_END_RECORD),
        "delta_bytes": len(cd_new) - len(cd_payload)}
    if not all(p.guid in present for p in plans):
        raise LoaderError("a ContentDocuments entry did not insert")
    # host ADocument registrations
    lat = decode_latest(latest_payload)
    if not lat.clean:
        raise LoaderError("host Global/Latest does not decode clean")
    lv = _dc(lat.value)
    reg = register_in_host_adocument(lv, plans)
    proofs["pass2_adocument_registrations"] = reg
    new_latest = encode_latest(lv, trailer=lat.trailer)
    back = decode_latest(new_latest)
    proofs["pass2_adocument_reencode"] = {"clean": bool(back.clean),
                                          "bytes_before": len(latest_payload),
                                          "bytes_after": len(new_latest)}
    if not back.clean:
        raise LoaderError("edited host ADocument does not re-decode clean")
    # frame + write
    new_streams = {
        host.partition_name: ecc.frame_stream(logical),
        "Global/ContentDocuments": ecc.frame_stream(
            wrap_global_stream("Global/ContentDocuments", cd_new, level=3)),
        "Global/Latest": ecc.frame_stream(
            wrap_global_stream("Global/Latest", new_latest, level=3)),
    }
    entries = read_entries(tmp1)
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    stage_out = tmp2 if repoints else out_rvt
    write_cfb(stage_out, out_entries)
    try:
        os.remove(tmp1)
    except OSError:                                            # pragma: no cover
        pass

    # ---------------- PASS 3: usage repointing (optional) --------------------
    if repoints:
        symmap = {p.key: list(p.symbol_ids) for p in plans}
        rr = repoint_usage(tmp2, out_rvt, list(repoints), symmap)
        proofs["pass3_usage_repoint"] = rr
        if rr.get("written"):
            try:
                os.remove(tmp2)
            except OSError:                                    # pragma: no cover
                pass
        else:
            # nothing was repointed: the loaded (stage) file IS the output
            os.replace(stage_out, out_rvt)
    # ---------------- verify -------------------------------------------------
    ver = verify_loaded_project(out_rvt, plans, expected_units_added=len(plans),
                                 validate=validate,
                                 census_before=host.census_before)
    proofs["verify_written"] = ver
    ok = bool(ver.get("ok"))
    acceptance.extend([
        "H1: an EMBEDDED family ADocument with an all-null 239-slot "
        "AppInfoManager (the specimen carries ~110 populated family-editor "
        "registries) -- the factory's L3 open question, unchanged",
        "H2: an annotation FamilySymbol whose seq-103 rep is a SerializedDummy "
        "and whose geometry bookkeeping (m_geomSteps / m_pGeomTable / "
        "m_refFaces / m_tagNoteData) is EMPTY -- Revit must regenerate the "
        "symbol graphics from the family document",
        "H3: our family documents carry the S0 skeleton (self-Family, Ref. "
        "Level, origin planes, units, one plan view, parameters, one type) "
        "and NO detail geometry / label -- the head SHAPE is absent",
        "H4: host Family.m_coreIds bind only the host's category GStyle rows "
        "(none when the host lacks that category); big2small maps only the "
        "parameter twins (our documents reference no host catalog rows)",
        "H5: the ContentTable record's author is 'rvt-writer'; the load "
        "reuses the host's current episode (no new History row / DIT record)",
        "H6: the host FamilyTypeTable = one blank ' ' row and the type lives "
        "as the FamilySymbol (the annotation flavour); OUR embedded document "
        "carries its single named type too (the specimen embedded head "
        "document's type table is empty)",
    ])
    res = LoadResult(ok=ok, out_path=out_rvt, plans=plans, proofs=proofs,
                     acceptance=acceptance,
                     stop_reason=("" if ok else "verify_loaded_project reported failures"),
                     seconds=round(time.time() - t0, 1))
    if report_path:
        os.makedirs(os.path.dirname(os.path.abspath(report_path)) or ".", exist_ok=True)
        with open(report_path, "w") as fh:
            json.dump(res.as_json(), fh, indent=1, default=str)
    return res


def load_family_document(host_rvt: str, family: Union[FamilyLoad, Any],
                         out_rvt: Optional[str], *, name: Optional[str] = None,
                         repoints: Sequence[UsageRepoint] = (),
                         validate: bool = True,
                         report_path: Optional[str] = None) -> LoadResult:
    """Load ONE family document into ``host_rvt`` -> ``out_rvt``.

    ``family`` = a :class:`FamilyLoad`, a builder ``callable(start_id) ->
    FamilyDoc``, or a prebuilt ``FamilyDoc`` (its ids must already lie
    above the host watermark).  See :func:`load_family_documents`.
    """
    if isinstance(family, FamilyLoad):
        fl = family
    elif callable(family):
        fl = FamilyLoad(key=(name or "family"), builder=family)
    else:
        fl = FamilyLoad(key=(name or getattr(family, "name", "family")), doc=family)
    return load_family_documents(host_rvt, [fl], out_rvt, repoints=repoints,
                                 validate=validate, report_path=report_path)


# ---------------------------------------------------------------------------
# verification of the written project (the machine proofs)
# ---------------------------------------------------------------------------

def verify_loaded_project(path: str, plans: Sequence[LoadPlan], *,
                          expected_units_added: int,
                          validate: bool = True,
                          census_before: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Read the loaded project back and prove: container / ECC / walker
    health, the FOUR REGISTRIES are COHERENT and each family's GUID sits in
    all four, the host ids are in the ElemTable and decode to the expected
    classes, the host Family names our content GUID and our symbol(s), the
    edited ADocument decodes clean, and (optionally) ``rvt.validate`` = 0
    errors."""
    from .container import open_rvt
    from .families import FamilyIndex, family_documents
    from .elemtable import parse_elemtable
    from .partitions import StreamWalker
    from .commit import verify_written
    rep: Dict[str, Any] = {"path": _relp(path)}
    all_ids: List[int] = []
    for p in plans:
        all_ids.extend(p.host_ids())
    vw = verify_written(path, all_ids)
    # every host id must appear in all three seqs of save-unit 0 and decode clean
    found = vw.get("new_ids_found") or {}
    missing: List[str] = []
    unclean: List[str] = []
    for seq in (101, 102, 103):
        per = found.get(seq) or {}
        for i in all_ids:
            e = per.get(i)
            if e is None:
                missing.append(f"seq{seq}:{i}")
            elif e.get("clean") is False:
                unclean.append(f"seq{seq}:{i}")
    rep["container"] = {"crc_failures": vw.get("crc_failures"),
                        "ecc_mismatches": vw.get("ecc_mismatches"),
                        "walker_errors": vw.get("walker_errors"),
                        "stamps_ok": vw.get("stamps_ok"),
                        "host_records_missing": missing,
                        "host_records_unclean": unclean}
    # the four registries
    cen = four_registry_census(path)
    rep["registries"] = {k: cen.get(k) for k in (
        "save_units", "contentdocs_entries", "contenttable_records",
        "familymgr_entries", "coherent", "coherent_counts", "coherent_guids",
        "units_missing_from_contentdocs", "units_missing_from_contenttable",
        "units_missing_from_familymgr", "contenttable_dangling",
        "familymgr_dangling")}
    if census_before:
        rep["registries"]["before"] = {k: census_before.get(k) for k in (
            "save_units", "contentdocs_entries", "contenttable_records",
            "familymgr_entries", "coherent")}
        rep["registries"]["units_added"] = (
            (cen.get("save_units") or 0) - (census_before.get("save_units") or 0))
        rep["registries"]["units_added_ok"] = (
            rep["registries"]["units_added"] == int(expected_units_added))
    ours_in_all_four = all(
        p.guid.lower() in (cen.get("unit_guids") or [])
        and p.guid.lower() in (cen.get("contentdocs_guids") or [])
        and p.guid.lower() in (cen.get("contenttable_guids") or [])
        and p.guid.lower() in (cen.get("familymgr_guids") or [])
        for p in plans)
    rep["registries"]["ours_in_all_four"] = ours_in_all_four
    # ElemTable rows + host element decode
    with open_rvt(path) as f:
        et = parse_elemtable(f.inflate("Global/ElemTable", 0))
    et_ids = {r.id for r in et.records}
    rep["elemtable"] = {"records": len(et.records),
                        "watermark": et.footer.last_id if et.footer else None,
                        "our_host_ids_present": all(i in et_ids for i in all_ids),
                        "watermark_covers_documents": bool(
                            et.footer and et.footer.last_id >= max(
                                p.doc_id_range[1] for p in plans))}
    # decode our host elements + check the linkage fields
    from .mutate import Document
    doc = Document.from_file(path)
    linkage = []
    all_link_ok = True
    for p in plans:
        row = {"key": p.key, "family": p.host_family_id, "checks": {}}
        fam = doc.value(p.host_family_id) or {}
        fdoc = ((fam.get("m_oFamDoc") or {}).get("value") or {})
        row["checks"]["family_content_guid"] = (str(fdoc.get("m_contentDocGUID")) == p.guid)
        row["checks"]["family_name"] = (fam.get("m_name") == p.family_name)
        row["checks"]["family_surrogate"] = (fam.get("m_surrogateId") == p.surrogate_id)
        sur = doc.value(p.surrogate_id) or {}
        row["checks"]["surrogate_points_at_family"] = (sur.get("m_elemId") == p.host_family_id)
        for sym, ssur in zip(p.symbol_ids, p.symbol_surrogate_ids):
            sv = doc.value(sym) or {}
            ok_sym = (sv.get("m_familyId") == p.host_family_id
                      and sv.get("m_partitionSurrogateId") == ssur)
            ssv = doc.value(ssur) or {}
            ok_ss = (ssv.get("m_elemId") == sym and ssv.get("m_famSurrogateId") == p.surrogate_id)
            row["checks"][f"symbol_{sym}"] = ok_sym
            row["checks"][f"symsurrogate_{ssur}"] = ok_ss
        for te, tt in p.twin_of.items():
            tv = doc.value(tt) or {}
            row["checks"][f"twin_{tt}"] = (tv.get("m_famId") == p.host_family_id
                                            and tv.get("m_id") == tt)
        row["ok"] = all(bool(v) for v in row["checks"].values())
        all_link_ok = all_link_ok and row["ok"]
        linkage.append(row)
    rep["host_linkage"] = {"ok": all_link_ok, "families": linkage}
    # family inventory: each of our documents shows up as a loaded family
    fidx = FamilyIndex.open(path)
    inv = family_documents(fidx)
    ours = []
    inv_ok = True
    for p in plans:
        mine = [d for d in inv if d.get("content_doc_guid") == p.guid]
        entry = {"key": p.key, "found": len(mine)}
        if len(mine) == 1:
            m = mine[0]
            entry.update({"family_id": m["family_id"], "family_name": m["family_name"],
                          "category": m["category"], "unit": m["unit"],
                          "n_records": m.get("n_records"), "n_types": m["n_types"],
                          "symbols": m["symbols"], "big2small_count": m["big2small_count"],
                          "n_family_params": m.get("n_family_params")})
            entry["ok"] = (m["family_id"] == p.host_family_id
                           and m["unit"] is not None
                           and {s.get("symbol_id") for s in m["symbols"]} == set(p.symbol_ids))
        else:
            entry["ok"] = False
        inv_ok = inv_ok and entry["ok"]
        ours.append(entry)
    rep["family_inventory"] = {"total_host_families": len(inv), "ours": ours, "ok": inv_ok}
    # validator
    val_ok = True
    if validate:
        try:
            from .validate import validate_file
            vr = validate_file(path)
            errs = list(vr.errors)
            rep["validate"] = {"verdict": "VALID" if vr.ok else "INVALID",
                               "n_errors": len(errs),
                               "n_warnings": len(vr.warnings),
                               "errors": [f"[{f.layer}] {f.where}: {f.message}"
                                          for f in errs[:12]],
                               "warnings": [f"[{f.layer}] {f.where}: {f.message}"
                                            for f in vr.warnings[:12]]}
            val_ok = (len(errs) == 0)
        except Exception as exc:                                   # pragma: no cover
            rep["validate"] = {"error": f"{type(exc).__name__}: {exc}"}
            val_ok = False
    rep["ok"] = bool(
        (rep["container"]["crc_failures"] == 0)
        and (rep["container"]["ecc_mismatches"] == 0)
        and (rep["container"]["walker_errors"] == 0)
        and (rep["container"]["stamps_ok"] is not False)
        and not rep["container"]["host_records_missing"]
        and not rep["container"]["host_records_unclean"]
        and cen.get("coherent") is True
        and ours_in_all_four
        and rep["elemtable"]["our_host_ids_present"]
        and rep["elemtable"]["watermark_covers_documents"]
        and all_link_ok
        and inv_ok
        and val_ok)
    return rep


# ---------------------------------------------------------------------------
# THE L-PROOF LADDER (the loader's viewer probes; the K4-FAIL fix candidates)
# ---------------------------------------------------------------------------

LOADER_OUT = os.path.join(_ROOT, "experiments", "genesis", "loader")
RSTBASIC = os.path.join(_ROOT, "samples", "rstbasicsampleproject.rvt")
K1_PATH = os.path.join(_ROOT, "experiments", "genesis", "triage", "K1.rvt")
G1_PATH = os.path.join(_ROOT, "experiments", "genesis", "G1_candidate.rvt")

#: the built-in ANNOTATION-head categories of our set (== the categories of
#: the Autodesk head families L2 replaces)
HEAD_CATEGORIES = {-2000400, -2006020, -2006040, -2000538, -2006045,
                   -2000515, -2005301}


def _log(msg: str) -> None:
    print(msg, flush=True)


def _probe_report(name: str, res: LoadResult, extra: Dict[str, Any]) -> Dict[str, Any]:
    ver = (res.proofs.get("verify_written") or {})
    reg = ver.get("registries") or {}
    return {
        "probe": name, "out": (res.out_path and _relp(res.out_path)),
        "ok": res.ok, "seconds": res.seconds,
        "families": [{"key": p.key, "guid": p.guid, "host_family": p.host_family_id,
                      "symbols": p.symbol_ids, "twins": len(p.twin_of),
                      "unit_records": p.unit_records,
                      "doc_ids": list(p.doc_id_range)} for p in res.plans],
        "registries_after": {k: reg.get(k) for k in (
            "save_units", "contentdocs_entries", "contenttable_records",
            "familymgr_entries", "coherent", "ours_in_all_four", "units_added")},
        "registries_before": (reg.get("before") if isinstance(reg, dict) else None),
        "elemtable": ver.get("elemtable"),
        "container": ver.get("container"),
        "host_linkage_ok": (ver.get("host_linkage") or {}).get("ok"),
        "family_inventory_ok": (ver.get("family_inventory") or {}).get("ok"),
        "validate": ver.get("validate"),
        "usage_repoint": res.proofs.get("pass3_usage_repoint"),
        "acceptance": res.acceptance,
        **extra,
    }


def _write_json(path: str, obj: Any) -> None:
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=1, default=str)


def build_L1a(out_dir: str = LOADER_OUT) -> Dict[str, Any]:
    """L1a: the working rst basic sample + ONE of our head families (the
    level head) LOADED, no usage repoint.  Proves the loader mechanism in
    isolation on a viewer-PASSING base: the loaded family is present in all
    four registries but referenced by nothing (an unused loaded family)."""
    from .famgen import heads as H
    out = os.path.join(out_dir, "L1a_rstbasic_loaded_levelhead.rvt")
    res = load_family_documents(RSTBASIC, [H.family_load("level_head")], out,
                                report_path=out + ".load.json")
    return _probe_report("L1a", res, {
        "base": _relp(RSTBASIC), "base_verdict": "sample (viewer PASS)",
        "tests": ("Does the reader accept a project into which OUR family "
                  "document was LOADED (four registries coherent, host Family / "
                  "symbol / surrogates / twins ours, embedded document ours), "
                  "the family referenced by nothing?  The pure loader proof."),
        "if_PASS": ("The load mechanism is reader-accepted: an OUR-authored "
                    "embedded family document coexists with the sample's.  L1b / "
                    "L3 read cleanly on top of it."),
        "if_FAIL": ("The loader corrupts a passing file: one of the four "
                    "registries or a host record shape is wrong -- bisect with "
                    "the four-registry census + the acceptance list (H1-H6); "
                    "L3's verdict is moot until this passes."),
    })


def build_L1b(out_dir: str = LOADER_OUT) -> Dict[str, Any]:
    """L1b: rst basic + ALL twelve of our head families loaded AND every
    existing head-usage field switched to OUR symbols (the sample's own
    head families stay loaded, unreferenced).  Answers the CONTENT
    question: are our skeleton head families acceptable as the ACTIVE
    level / grid / section / callout / elevation / view-title / boundary-
    condition heads of a project the reader otherwise opens?"""
    from .famgen import heads as H
    out = os.path.join(out_dir, "L1b_rstbasic_our_heads_active.rvt")
    res = load_family_documents(RSTBASIC, H.all_family_loads(), out,
                                repoints=H.default_repoints(),
                                report_path=out + ".load.json")
    return _probe_report("L1b", res, {
        "base": _relp(RSTBASIC), "base_verdict": "sample (viewer PASS)",
        "tests": ("Our twelve head family DOCUMENTS become the project's "
                  "ACTIVE heads (LevelAttributes / GridAttributes / "
                  "SectionAttributes head+tail / CalloutTag / "
                  "ViewportAttributes / InteriorElevAttributes / "
                  "StructSettingsElem usage fields all name OUR symbols; the "
                  "Autodesk heads remain loaded but unreferenced).  Is an "
                  "annotation-skeleton family (no detail geometry / label) "
                  "an acceptable REFERENCED head?"),
        "if_PASS": ("Our head family documents satisfy the reader as active "
                    "heads: family-document CONTENT (the head shape / label) is "
                    "NOT required by the reader -- L3's remaining variable is "
                    "the constructed base itself."),
        "if_FAIL": ("(with L1a PASSING) the reader requires MORE content in "
                    "a referenced head family document than our skeleton "
                    "carries (detail geometry / label / the annotation view "
                    "constellation) -- the head CONTENT ladder is the next "
                    "stream; L3 cannot pass with these families."),
    })


def build_L3(out_dir: str = LOADER_OUT, *, all_heads: bool = True) -> Dict[str, Any]:
    """L3 / L3b: the constructed genesis base G1_candidate + our head
    families loaded + its level type's usage field pointed at our level
    head.  THE K4-FAIL FIX CANDIDATE: the constructed base gains coherent
    embedded family documents (the machinery K4-FAIL says the reader
    requires).  L3 = all twelve heads; L3b = the level head only."""
    from .famgen import heads as H
    name = "L3" if all_heads else "L3b"
    out = os.path.join(out_dir, f"{name}_G1_candidate_our_heads.rvt")
    loads = H.all_family_loads() if all_heads else [H.family_load("level_head")]
    # G1_candidate's only usage referrer is its LevelAttributes (m_familyTagId
    # = -1): give the level type OUR level head (only_if_set False).
    rps = [UsageRepoint(referrer_class="LevelAttributes", field="m_familyTagId",
                        family_key="level_head", only_if_set=False)]
    res = load_family_documents(G1_PATH, loads, out, repoints=rps,
                                report_path=out + ".load.json")
    return _probe_report(name, res, {
        "base": _relp(G1_PATH), "base_verdict": "constructed genesis base (viewer FAIL: "
                                                 "'Revit-DocumentCorruption')",
        "tests": ("The constructed base G1_candidate (234-element house-standard "
                  "inventory, OUR ADocument, ZERO family documents) + "
                  + ("our twelve" if all_heads else "our level-head")
                  + " head family document(s) loaded through all four registries, "
                  "and its level type's m_familyTagId pointed at our level-head "
                  "symbol.  = the K4-FAIL fix: the base now carries coherent "
                  "embedded family documents."),
        "if_PASS": ("Embedded family documents were the missing skeleton class: "
                    "the genesis base + OUR loaded families opens -- G1 has its "
                    "K4-FAIL fix and the loader is the genesis-2 base's family "
                    "route."),
        "if_FAIL": ("Family documents alone do not fix the constructed base: "
                    "read the card message -- if L1a/L1b PASS, the residual is "
                    "the base's OTHER missing skeleton content (settings "
                    "singletons / catalogs, the K5x/K6 verdicts) or the head "
                    "CONTENT (if L1b failed)."),
    })


def _head_family_layer(st: dict, categories: set, exclude_families: set) -> Tuple[set, dict, list]:
    """The Autodesk head-family layer of ``st``: Family elements whose
    m_categoryId is a head category (minus ``exclude_families``), their
    symbols / surrogates / param twins / family-scoped children (the same
    linking-field fixpoint as genesis_triage.family_layer), plus their
    embedded document GUIDs."""
    from . import families as FAM
    doc, cls_of, host = st["doc"], st["cls_of"], st["host"]
    famdocs = FAM.family_documents(st["src"])
    doc_of_family = {fd["family_id"]: fd for fd in famdocs}
    fam_ids = set()
    names = {}
    for e in host:
        if cls_of.get(e) != "Family" or e in exclude_families:
            continue
        v = doc.value(e) or {}
        if int(v.get("m_categoryId") if isinstance(v.get("m_categoryId"), int) else 0) in categories:
            fam_ids.add(e)
            names[e] = v.get("m_name")
    layer = set(fam_ids)
    et = getattr(doc, "et_by_id", {}) or {}
    changed = True
    while changed:
        changed = False
        for e in host:
            if e in layer or e in exclude_families:
                continue
            v = doc.value(e)
            if not isinstance(v, dict):
                v = {}
            links = [v.get("m_famId"), v.get("m_familyId"), v.get("m_famSurrogateId")]
            c = cls_of.get(e)
            if c in ("FamilySurrogate", "FamSymSurrogate"):
                links.append(v.get("m_elemId"))
            if c == "FamilyInstance":
                links.append(v.get("m_masterSymbolId"))
                ii = ((v.get("m_pInstanceInfo") or {}).get("value")
                      if isinstance(v.get("m_pInstanceInfo"), dict) else None) or {}
                links.append(ii.get("m_symbolId"))
            r = et.get(e)
            if r is not None:
                own = getattr(r, "owner_id", None)
                if own is not None and 0 < own < (1 << 63):
                    links.append(own)
            if any(isinstance(x, int) and x in layer for x in links):
                layer.add(e)
                changed = True
    docs = [{"guid": doc_of_family[f].get("content_doc_guid"),
             "unit": doc_of_family[f].get("unit"), "family": names.get(f)}
            for f in fam_ids if f in doc_of_family]
    return layer, names, docs


def build_L2(out_dir: str = LOADER_OUT) -> Dict[str, Any]:
    """L2: Autodesk's empty-project skeleton K1 with its ANNOTATION-HEAD
    families REPLACED by ours.  Recipe (every intermediate coherent):
    (1) load our twelve into K1 + repoint the head usage fields to OUR
    symbols; (2) the Autodesk head-family layer is now unreferenced by any
    usage field -> neutralise residual referrers, remove their embedded
    documents COHERENTLY (all four registries) and delete the layer
    (genesis_triage / rvt_reduce machinery).  Composes the loader with the
    triage stream's removal tools; reported honestly if a step is missing."""
    from .famgen import heads as H
    rep: Dict[str, Any] = {"probe": "L2", "base": _relp(K1_PATH),
                           "base_verdict": "Autodesk empty-project skeleton (viewer verdict PENDING)"}
    if not os.path.exists(K1_PATH):
        rep["status"] = "SKIPPED: K1.rvt not on disk"
        return rep
    t0 = time.time()
    # step 1: load ours + repoint (Autodesk heads still present)
    tmp_loaded = os.path.join(out_dir, ".L2_step1_loaded.rvt")
    res = load_family_documents(K1_PATH, H.all_family_loads(), tmp_loaded,
                                repoints=H.default_repoints())
    rep["step1_load"] = _probe_report("L2-step1", res, {})
    if not res.ok:
        rep["status"] = "STOPPED: step 1 (load into K1) did not verify"
        return rep
    ours = {p.host_family_id for p in res.plans}
    our_ids = set()
    for p in res.plans:
        our_ids |= set(p.host_ids())
    # step 2: remove the Autodesk head layer from the loaded file
    try:
        import sys as _sys
        tools = os.path.join(_ROOT, "tools")
        if tools not in _sys.path:
            _sys.path.insert(0, tools)
        import rvt_reduce as RR                                    # type: ignore
        import genesis_triage as GT                               # type: ignore
        from .reduce import delete_elements, verify_reduced
    except Exception as ex:                                       # pragma: no cover
        rep["status"] = f"PARTIAL: removal machinery unavailable ({ex!r}); step 1 file kept"
        rep["out"] = _relp(tmp_loaded)
        return rep
    st = RR.build_state_v2(tmp_loaded)
    layer, names, docs = _head_family_layer(st, HEAD_CATEGORIES, exclude_families=ours)
    layer -= our_ids                                              # never touch ours
    rep["autodesk_head_layer"] = {
        "families": names, "elements": len(layer),
        "documents": docs,
        "children_by_class": GT._class_hist(st, layer - set(names)),
    }
    # neutralise residual host referrers of the layer (usage fields already ours)
    tmp_neut = os.path.join(out_dir, ".L2_step2_neutralised.rvt")
    nrep = GT.neutralise_referrers(st, layer, tmp_neut, name="L2")
    rep["neutralise"] = {k: nrep[k] for k in ("referrer_elements_edited",
                                              "edits_by_referrer_class",
                                              "embedded_document_referrers_not_edited",
                                              "verify")}
    # remove their documents coherently, then delete the layer
    guids = {str(d["guid"]).lower() for d in docs if d.get("guid")}
    tmp_docs = os.path.join(out_dir, ".L2_step3_docs_removed.rvt")
    rrep = GT.remove_documents(tmp_neut, tmp_docs, guids,
                               reconcile_contenttable=True, reconcile_familymgr=True)
    rep["remove_documents"] = {k: rrep.get(k) for k in (
        "units_before", "units_after", "cd_entries_before", "cd_entries_after",
        "contenttable_records_before", "contenttable_records_after",
        "familymgr_entries_before", "familymgr_entries_after",
        "familymgr_doc_guids_removed")}
    st2 = RR.build_state_v2(tmp_docs)
    L = {e for e in layer if e in st2["host"]}
    L = RR._protect_history(st2, L)
    delete, kept, ev = RR.maxgc(st2, L)
    out = os.path.join(out_dir, "L2_K1_our_heads.rvt")
    delete_elements(tmp_docs, out, delete)
    for t in (tmp_loaded, tmp_neut, tmp_docs):
        try:
            os.remove(t)
        except OSError:                                           # pragma: no cover
            pass
    rep["layer_gc"] = {"seed": len(L), "deleted": len(delete), "kept_pinned": len(kept),
                       "deleted_by_class": GT._class_hist(st2, delete),
                       "kept_by_class": GT._class_hist(st2, kept)}
    struct_ok = verify_reduced(out, delete)
    val = GT.validate(out)
    cen = four_registry_census(out)
    resid = GT._residual_guid_hits(out, guids)
    rep.update({
        "out": _relp(out), "structural_ok": bool(struct_ok.get("ok")),
        "validator": val,
        "registries": {k: cen.get(k) for k in ("save_units", "contentdocs_entries",
                                                 "contenttable_records", "familymgr_entries",
                                                 "coherent")},
        "residual_guid_bytes": resid,
        "our_families": {p.key: p.host_family_id for p in res.plans},
        "seconds": round(time.time() - t0, 1),
        "tests": ("K1 (Autodesk's own empty-project skeleton, every catalog / "
                  "singleton / view type intact) with its annotation-head "
                  "families (level / grid / section / callout / elevation / "
                  "view-title / boundary-condition heads: the like categories "
                  "of our set) REPLACED by our twelve -- loaded through all "
                  "four registries, every head usage field naming OUR symbols, "
                  "the Autodesk head families + their documents removed "
                  "coherently.  Tags / spot elevations / view references / the "
                  "title block / curtain families STAY."),
        "if_PASS": ("Our head families are acceptable substitutes on the FULL "
                    "Autodesk skeleton: the head-family layer of a genesis base "
                    "can be ours."),
        "if_FAIL": ("(with K1 / K3 / KD1 PASSING and L1b PASSING) a head-family "
                    "REMOVAL side effect broke the file (a family-scoped host "
                    "child / catalog row the removal took) -- bisect against "
                    "L1b (same load, no removal)."),
    })
    rep["ok"] = bool(struct_ok.get("ok") and val.get("ok") and val.get("errors") == 0
                     and cen.get("coherent"))
    rep["status"] = "BUILT" if rep["ok"] else "SELF-CHECK FAILED"
    return rep


def write_probes_manifest(reports: Dict[str, dict], out_dir: str = LOADER_OUT,
                          rfa_report: Optional[dict] = None) -> str:
    """probes.json -- every loader probe, ordered by information value."""
    order = ["L1a", "L1b", "L3", "L3b", "L2"]
    probes = []
    for name in order:
        r = reports.get(name)
        if not r:
            continue
        probes.append({
            "file": r.get("out"),
            "probe": name,
            "self_checks_ok": bool(r.get("ok")),
            "base": r.get("base"), "base_verdict": r.get("base_verdict"),
            "tests": r.get("tests"),
            "if_PASS": r.get("if_PASS"),
            "if_FAIL": r.get("if_FAIL"),
            "families": r.get("families") or r.get("our_families"),
            "registries_after": r.get("registries_after") or r.get("registries"),
            "validate": r.get("validate") or r.get("validator"),
            "report": f"{name}.json",
        })
    rfas = []
    for key, e in ((rfa_report or {}).get("families") or {}).items():
        rfas.append({"file": (e.get("rfa") or {}).get("path"), "key": key,
                     "name": e.get("name"), "category": e.get("category"),
                     "validate_family": (e.get("validate_family") or {}).get("verdict")})
    manifest = {
        "purpose": (
            "THE K4-FAIL BRANCH: if the reader REQUIRES embedded family documents "
            "(K4 FAIL with KD1/K3 PASS), the genesis base needs OUR families "
            "loaded as coherent embedded documents.  These probes exercise the "
            "loader (rvt.famload) that does that: L1a = the mechanism on a "
            "passing base; L1b = our head families as the ACTIVE heads of a "
            "passing sample (the content question); L3/L3b = the K4-FAIL FIX "
            "CANDIDATE (the constructed base G1_candidate + our loaded heads); "
            "L2 = the head-family replacement on Autodesk's full skeleton K1. "
            "The twelve head_*.rfa are the standalone family form of the same "
            "families (family-editor acceptance)."),
        "read_order": ("L1a first (loader mechanism), then L1b (family content), "
                       "then L3/L3b (the genesis fix), then L2 (skeleton "
                       "replacement).  A card message DIFFERENT from "
                       "'Revit-DocumentCorruption' on any file is a spotlight."),
        "reading_the_results": {
            "L1a PASS": "loader mechanism reader-accepted; the four registries + host records are right",
            "L1a FAIL": "loader defect (registry / record shape); everything else moot",
            "L1a PASS & L1b PASS": ("our skeleton head families are acceptable ACTIVE "
                                    "heads -- family-document content is not required"),
            "L1a PASS & L1b FAIL": ("a referenced head needs real content (detail "
                                    "geometry / label / view constellation) -- the "
                                    "head-content ladder is next; L3 cannot pass yet"),
            "L3 PASS": ("embedded family documents were the K4-FAIL fix: the genesis "
                        "base opens with OUR loaded families"),
            "L3 FAIL (L1a/L1b PASS)": ("family documents alone do not fix the base -- "
                                       "the residual is other skeleton content (K5x/K6 "
                                       "verdicts) -- read the card message"),
            "L2 PASS": "our heads substitute on the full Autodesk skeleton (K1)",
            "L2 FAIL (K1 PASS, L1b PASS)": ("the Autodesk head-family REMOVAL took a "
                                            "needed family-scoped row -- bisect vs L1b"),
        },
        "coherence_rule": ("a document GUID lives in FOUR places -- the "
                           "Partitions save-unit separator, the "
                           "Global/ContentDocuments entry, the ADocument "
                           "ContentTable.m_ContentRecSet record and the "
                           "ADocument FamilyMgr.m_arrLoadedFamilyInfo entry "
                           "(AppInfo slot 0).  Every emitted file is COHERENT "
                           "(four_registry_census) and rvt_validate VALID with "
                           "0 errors -- see each L*.json."),
        "probes": probes,
        "standalone_families": rfas,
    }
    path = os.path.join(out_dir, "probes.json")
    _write_json(path, manifest)
    return path


def build_loader_proofs(out_dir: str = LOADER_OUT, *, with_L2: bool = True,
                        with_rfas: bool = True) -> Dict[str, Any]:
    """Build the whole loader ladder: the twelve standalone .rfa, L1a, L1b,
    L3, L3b, (L2), the per-probe JSON reports and probes.json."""
    from .famgen import heads as H
    os.makedirs(out_dir, exist_ok=True)
    reports: Dict[str, Any] = {}
    rfa_rep = None
    if with_rfas:
        _log("[heads] emitting the twelve standalone head .rfa files ...")
        rfa_rep = H.emit_head_rfas(out_dir)
        n_ok = sum(1 for e in rfa_rep["families"].values()
                   if (e.get("validate_family") or {}).get("verdict") == "VALID")
        _log(f"[heads] {len(rfa_rep['families'])} .rfa emitted, {n_ok} family-mode VALID")
    for name, fn in (("L1a", build_L1a), ("L1b", build_L1b),
                     ("L3", lambda d: build_L3(d, all_heads=True)),
                     ("L3b", lambda d: build_L3(d, all_heads=False))):
        _log(f"[{name}] building ...")
        r = fn(out_dir)
        reports[name] = r
        _write_json(os.path.join(out_dir, f"{name}.json"), r)
        reg = r.get("registries_after") or {}
        val = r.get("validate") or {}
        _log(f"[{name}] ok={r.get('ok')} units {reg.get('save_units')} CD "
             f"{reg.get('contentdocs_entries')} CT {reg.get('contenttable_records')} "
             f"FM {reg.get('familymgr_entries')} coherent={reg.get('coherent')} "
             f"validate={val.get('verdict')} errors={val.get('n_errors')} "
             f"({r.get('seconds')}s) -> {r.get('out')}")
    if with_L2:
        _log("[L2] building (K1 head-family replacement) ...")
        try:
            r2 = build_L2(out_dir)
        except Exception as ex:                                   # honest stop
            r2 = {"probe": "L2", "status": f"FAILED TO BUILD: {type(ex).__name__}: {ex}",
                  "ok": False}
        reports["L2"] = r2
        _write_json(os.path.join(out_dir, "L2.json"), r2)
        _log(f"[L2] status={r2.get('status')} ok={r2.get('ok')} "
             f"registries={r2.get('registries')} -> {r2.get('out')}")
    manifest = write_probes_manifest(reports, out_dir, rfa_report=rfa_rep)
    _log(f"[loader] probes manifest: {_relp(manifest)}")
    return {"reports": reports, "manifest": manifest,
            "rfa": (rfa_rep or {}).get("families")}


# ---------------------------------------------------------------------------
# CLI: load our head families into a host / build the L ladder
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m rvt.famload",
                                 description="load OUR annotation-head families into a project")
    ap.add_argument("--host", default=os.path.join(_ROOT, "samples", "rstbasicsampleproject.rvt"))
    ap.add_argument("--out", default=None, help="output .rvt (default: dry run)")
    ap.add_argument("--families", default="level_head",
                    help="comma-separated head keys (rvt.famgen.heads.HEAD_SPECS) or 'all'")
    ap.add_argument("--report", default=None)
    ap.add_argument("--census", default=None, help="just print the four-registry census of a file")
    ap.add_argument("--proofs", action="store_true",
                    help="build the whole L-proof ladder (rfas + L1a/L1b/L3/L3b/L2 + probes.json)")
    ap.add_argument("--no-L2", action="store_true")
    a = ap.parse_args(argv)
    if a.census:
        print(json.dumps(four_registry_census(a.census), indent=1))
        return 0
    if a.proofs:
        build_loader_proofs(with_L2=not a.no_L2)
        return 0
    from .famgen import heads as H
    keys = list(H.HEAD_SPECS) if a.families == "all" else [
        k.strip() for k in a.families.split(",") if k.strip()]
    loads = [H.family_load(k) for k in keys]
    res = load_family_documents(a.host, loads, a.out, report_path=a.report)
    print(json.dumps({"ok": res.ok, "out": res.out_path, "stop": res.stop_reason,
                      "plans": [{"key": p.key, "family": p.host_family_id,
                                 "symbols": p.symbol_ids, "guid": p.guid} for p in res.plans],
                      "verify": (res.proofs.get("verify_written") or {})}, indent=1, default=str))
    return 0 if (res.ok or a.out is None) else 1


if __name__ == "__main__":
    raise SystemExit(main())

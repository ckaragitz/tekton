"""rvt.famgen.loader -- L4/L5 of the asset factory: LOAD a generated family
into a project document (the host-side loader).

This is the second half of ``rvt.famgen.factory``'s loader.  The factory
proved L1 (the ``Global/ContentDocuments`` entry), L2 (the embedded partition
save unit) and L3 (the embedded document's ``ADocument``) and stopped
honestly at L4/L5.  This module authors L4 (the HOST-SIDE elements) and L5
(the host ``ADocument`` registrations) and composes all five into a project
file.

What "loading" a family means in the file, decoded from the rme specimen
(host ``Family`` 454674 = 'M_Lighting and Appliance Panelboard - 208V MLO'
+ its embedded document unit 243, ``docs/writer/asset-factory.md`` sec.6):

    HOST ELEMENTS (partition save-unit 0, ``Global/ElemTable`` rows)
      * one ``ParamElemFamily`` TWIN per top-level family user parameter
        (a SHARED ``ParamElemExternal`` parameter twins as itself, keeping
        its ``revit.local.shared:<guid>`` identity + GUID key verbatim) --
        the embedded parameter object with 4 rewrites (id, owner family,
        the ``revit.local.family:`` type id), ElemRec owner = the host
        Family                                                      [VERIFIED]
      * a ``FamilySurrogate`` {m_elemId=host Family, m_name, category,
        m_guid = e3e052f8-0156-11d5-9301-0000863f27ad}          [V, 159/159]
      * the host ``Family`` = the family's own self-Family object TRANSFORMED
        (id remap P_i->T_i, ``m_oFamDoc{contentDocGUID, big2SmallMap2,
        coreIds}``, ``m_famDocGUID``, host-only ``m_familyIds`` /
        ``m_dbviewInfos`` / ``m_oFamilyReferenceIdxMgr`` /
        ``ConnectorDataCell`` / ``m_surrogateId``)  -- transform derived
        from a field-by-field diff host-vs-embedded             [VERIFIED]
      * one host ``FamilySymbol`` per type (name, parameter row, and the
        SYMBOL GEOMETRY: ``m_geomSteps`` history + ``m_pGeomTable`` + the
        seq-103 ``GElement`` solid the placed instances display) + its
        ``FamSymSurrogate``                                     [V grammar]
      * a placed ``FamilyInstance`` (``GInstance -> symbolId``, connector
        manager for OUR connectors, face-hosted on a SketchPlane) [V shape]
    HOST ADOCUMENT (``Global/Latest``) registrations
      * ``ContentTable.m_ContentRecSet`` += record keyed by our content GUID
      * ``AppInfoManager[FamilyMgr].m_arrLoadedFamilyInfo`` +=
        {surrogateId, [our content GUID]}
      * ``AppInfoManager[ElementTrackingData]`` symbol / instance id sets
    STREAMS
      * ``Global/ContentDocuments`` += entry(our GUID, our embedded ADocument)
      * ``Partitions/<N>`` += our save unit (+ the host elements in unit 0)
      * ``Global/ElemTable`` += rows, watermark raised

Provenance: every element the load creates points at OUR embedded document
(our geometry, our parameters, our GUID).  The host records are format
scaffolding built field-by-field (the genesis / family-skeleton discipline);
the FamilyInstance placement scaffolding follows ``rvt.mutate``'s proven
instance recipe.  No Autodesk family bytes are referenced by our elements.

Acceptance is the Revit / viewer gate: the structural proofs here are the
codec / walker / validator / decoder round trips (all machine-checked); the
symbol geometry bookkeeping and the empty embedded ``AppInfoManager`` are the
open acceptance questions this file carries to that gate (see the report's
``acceptance`` block).

Public API::

    from rvt.famgen import loader as L
    rep = L.load_family_into_project(
        "samples/rmebasicsampleproject.rvt",
        "experiments/families/factory/project_with_generated_panel.rvt",
        product=None,            # None -> the flagship 400 A Eaton panel
        place=True, symbol_solid=True)
    rep["ok"], rep["proofs"], rep["acceptance"]

TERRITORY: new module of the asset-forge stream; imports (never edits) the
foundry modules and the format codecs.
"""
from __future__ import annotations

import collections
import copy
import json
import math
import os
import struct
import uuid
from dataclasses import dataclass, field as dc_field, replace
from typing import Any, Dict, List, Optional, Sequence, Tuple

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "..", ".."))
DEFAULT_HOST = os.path.join(_ROOT, "samples", "rmebasicsampleproject.rvt")

#: our product identity (matches rvt.famgen.factory.PRODUCT_NAME)
PRODUCT_NAME = "rvt-writer"

INVALID = -1
CAT_ELECTRICAL_EQUIPMENT = -2001040

#: FamilySurrogate.m_guid -- the SAME value on all 159 FamilySurrogates of
#: the rme host [VERIFIED 159/159]: a format-level creator identifier, not
#: content.  Every loaded family carries it.
SURROGATE_GUID = "e3e052f8-0156-11d5-9301-0000863f27ad"

#: header flag words copied from the specimen classes [V per class]
HDR_FLAGS = {
    "Family": (26, -32768),
    "FamilySymbol": (2488, -32768),
    "ParamElemFamily": (8218, -32768),
    "ParamElemExternal": (8218, -32768),
    "FamilySurrogate": (26, -32640),
    "FamSymSurrogate": (26, -32640),
    "FamilyInstance": (10, -32768),
}

#: history-table entry type codes of BaseFamilySymbolGStep [V specimen]
HIST_FACE, HIST_EDGE, HIST_NODE, HIST_FORM = 5, 3, 6, 65


class LoaderError(RuntimeError):
    """A load precondition the host or the product cannot satisfy."""


# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------

def _dc(v: Any) -> Any:
    return copy.deepcopy(v)


def _ptr(cls: str, value: dict, pid: int = -1) -> dict:
    return {"ptr_class": cls, "pid": pid, "value": value}


def _weak(ref: int) -> dict:
    return {"weakref": int(ref)}


def _guid_hex32(g: str) -> str:
    return uuid.UUID(g).hex


def _walk_replace_ids(node: Any, idmap: Dict[int, int]) -> None:
    """In-place remap of every integer VALUE found under any key whose name
    marks it as an element id / param id container, using ``idmap``.
    Conservative: rewrites plain int values that appear in ``idmap`` only.
    """
    if isinstance(node, dict):
        for k, v in list(node.items()):
            if isinstance(v, bool):
                continue
            if isinstance(v, int) and v in idmap:
                node[k] = idmap[v]
            else:
                _walk_replace_ids(v, idmap)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, bool):
                continue
            if isinstance(v, int) and v in idmap:
                node[i] = idmap[v]
            else:
                _walk_replace_ids(v, idmap)


def _collect_negative_param_ids(node: Any, out: set) -> None:
    """Every negative ``m_paramId`` (built-in parameter id) under ``node``."""
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "m_paramId" and isinstance(v, int) and not isinstance(v, bool) and v < 0:
                out.add(v)
            else:
                _collect_negative_param_ids(v, out)
    elif isinstance(node, list):
        for v in node:
            _collect_negative_param_ids(v, out)


# ---------------------------------------------------------------------------
# host survey
# ---------------------------------------------------------------------------

@dataclass
class HostContext:
    """Everything the loader needs to know about the HOST project."""
    path: str
    doc: Any                              # rvt.mutate.Document
    fidx: Any                             # rvt.families.FamilyIndex
    watermark: int                        # ElemTable IdentifierSource.m_last / max id
    episode: int                          # the load episode (existing max modified episode)
    partition_name: str
    category: int
    category_gstyle: int = INVALID        # host GStyleElem for the family's category
    load_classifications: Dict[str, int] = dc_field(default_factory=dict)   # name -> host id
    line_pattern_solid: int = INVALID
    fill_pattern_solid: int = INVALID
    template_instance: int = INVALID      # a specimen FamilyInstance of the same category
    template_host: int = INVALID          # its face host (SketchPlane) if any
    levels: List[dict] = dc_field(default_factory=list)
    notes: List[str] = dc_field(default_factory=list)


def survey_host(host_rvt: str = DEFAULT_HOST, *,
                category: Optional[int] = CAT_ELECTRICAL_EQUIPMENT) -> HostContext:
    """Open the host and resolve the resources a family of ``category``
    binds to: the category's projection ``GStyleElem`` (the symbol
    geometry's line style), the named load classifications (a family's
    connector load classification RESOLVES BY NAME to a host one), the id
    watermark, the load episode, and a specimen instance to clone the
    placement scaffolding from.  ``category=None`` = the category-neutral
    survey only (``ctx.category == INVALID``); :func:`bind_category` later.
    """
    from ..mutate import Document
    from ..families import FamilyIndex
    doc = Document.from_file(host_rvt)
    fidx = FamilyIndex.open(host_rvt)
    et = doc.et
    wm = max(int(et.footer.last_id if et.footer else 0),
             max(doc.et_by_id) if doc.et_by_id else 0)
    episode = max((r.modified_ep for r in et.records), default=0)
    parts = []
    from ..container import open_rvt
    with open_rvt(host_rvt) as f:
        parts = f.partition_streams()
    if len(parts) != 1:
        raise LoaderError(f"expected one partition stream, got {parts}")
    ctx = HostContext(path=host_rvt, doc=doc, fidx=fidx, watermark=wm,
                      episode=int(episode), partition_name=parts[0],
                      category=INVALID)
    # named load classifications
    for lid in doc.ids_of_class("ElectricalLoadClassification"):
        v = doc.value(lid) or {}
        nm = v.get("m_name")
        if nm:
            ctx.load_classifications[str(nm)] = lid
    # patterns (universal host resources; ids 3 / 16 on the samples)
    fps = sorted(doc.ids_of_class("FillPatternElem"))
    lps = sorted(doc.ids_of_class("LinePatternElem"))
    ctx.fill_pattern_solid = fps[0] if fps else INVALID
    ctx.line_pattern_solid = lps[0] if lps else INVALID
    ctx.levels = doc.levels()
    return ctx if category is None else bind_category(ctx, category)


def bind_category(ctx: HostContext, category: int) -> HostContext:
    """``ctx`` bound to ``category``: the category's projection
    ``GStyleElem`` and a specimen instance of it (placement scaffolding)
    resolved on the SAME surveyed host -- a new context (``ctx`` untouched;
    ``notes`` are the binding's own) unless ``ctx`` is already bound to
    ``category``.  The batched loader binds one per distinct family category
    (a fixtures family among equipment families must not inherit the
    equipment category on its surrogates / symbol header / tracking rows)."""
    category = int(category)
    if ctx.category == category:
        return ctx
    doc = ctx.doc
    notes: List[str] = []
    # category projection GStyle: the GStyleElem whose object m_categoryId
    # == category and m_gstyleType == 1 (projection)          [V id 124 on rme]
    best = None
    for gid in doc.ids_of_class("GStyleElem"):
        v = doc.value(gid) or {}
        if v.get("m_categoryId") == category:
            if v.get("m_gstyleType") == 1:
                best = gid
                break
            best = best or gid
    if best is None:
        notes.append(f"no host GStyleElem for category {category}: "
                     "symbol geometry falls back to m_categoryId -1")
    # a specimen instance of the category (placement scaffolding)
    tpl, tpl_host = INVALID, INVALID
    for iid in doc.ids_of_class("FamilyInstance"):
        if doc.category_of(iid) == category:
            tpl = iid
            h = (doc.value(iid) or {}).get("m_hostId", INVALID)
            tpl_host = h if isinstance(h, int) else INVALID
            break
    if tpl == INVALID:
        notes.append(f"no host FamilyInstance of category {category}: "
                     "placement scaffolding unavailable (family loads unplaced)")
    return replace(ctx, category=category,
                   category_gstyle=best if best is not None else INVALID,
                   template_instance=tpl, template_host=tpl_host, notes=notes)


#: the built-in (OST_*) category id range: every BuiltInCategory is a
#: negative int at or below -2000000 (-2000011 Walls ... -2007000 Connectors);
#: -1 = INVALID / "could not be read"
BUILTIN_CATEGORY_CEILING = -2000000


def product_category(product, default: int = CAT_ELECTRICAL_EQUIPMENT) -> int:
    """The built-in category a product's own family document declares
    (``FamilyDoc.category_id``) -- what its host surrogates / symbol header /
    ElementTrackingData row must carry.  ``default`` (Electrical Equipment,
    the loader's binding before categories came from the product) for a
    product without a document, without a category, or whose category could
    not be read (``rvt.convert.extract_family.RfaFamilyDoc`` records ``-1``
    then) -- an unknown category never loads UNBOUND."""
    cat = getattr(getattr(product, "doc", None), "category_id", None)
    if isinstance(cat, bool) or not isinstance(cat, int) or cat > BUILTIN_CATEGORY_CEILING:
        return int(default)
    return int(cat)


# ---------------------------------------------------------------------------
# the load plan: ids, twins, absorbed indices
# ---------------------------------------------------------------------------

def real_type_names(doc) -> List[str]:
    """The family's REAL-named types = the ones that become host symbols.

    A blank ' ' pair in ``doc.types`` / the unit-side ``FamilyTypeTable`` is
    the family document's own current-values row (the born blank-pair-first
    law, kept INSIDE the unit); it is never a host ``FamilySymbol`` /
    ``FamSymSurrogate`` and never a second row of the host Family's table
    [corpus law, measured on 36 native host Family rows: zero rows with more
    than the one leading blank, zero whose ``m_idx`` names a blank, zero
    instances bound to a blank-named symbol -- docs/inbox/species.md 1.2]."""
    names = (str(n) for n, _v in (doc.types or []))
    return [n for n in names if n.strip()]


def symbol_type_name(doc, fallback: str) -> str:
    """The host FamilySymbol's type name: the current type when it is
    real-named, else the first real-named type, else ``fallback``."""
    types = doc.types or []
    if 0 <= doc.current_type < len(types):
        cur = str(types[doc.current_type][0])
        if cur.strip():
            return cur
    real = real_type_names(doc)
    return real[0] if real else fallback


@dataclass
class LoadPlan:
    """Ids and correspondences of one family load."""
    guid: str                                  # our content-document GUID (== unit GUID)
    fam_doc_guid: str                          # host Family.m_famDocGUID (minted)
    session_guid_hex: str                      # 32-hex session guid for the twins' typeIds
    family_name: str
    type_name: str                             # the PRIMARY (current) type = what an instance binds
    host_family_id: int = INVALID
    surrogate_id: int = INVALID
    symbol_id: int = INVALID                   # the primary type's symbol pair
    symbol_surrogate_id: int = INVALID
    instance_id: int = INVALID
    # one FamSymSurrogate+FamilySymbol pair per REAL-named type (famload's
    # shape): parallel lists in unit-table order; the primary's entries equal
    # symbol_id / symbol_surrogate_id / type_name above
    type_names: List[str] = dc_field(default_factory=list)
    symbol_ids: List[int] = dc_field(default_factory=list)
    symbol_surrogate_ids: List[int] = dc_field(default_factory=list)
    twin_of: Dict[int, int] = dc_field(default_factory=dict)     # embedded P_i -> host T_i
    abs_index: Dict[int, int] = dc_field(default_factory=dict)   # embedded elem id -> absorbed index
    core_ids: List[int] = dc_field(default_factory=list)
    load_class_host: int = INVALID
    load_class_name: str = ""
    episode: int = 0
    notes: List[str] = dc_field(default_factory=list)


def plan_load(product, host: HostContext, *, place: bool) -> LoadPlan:
    """Allocate ids and derive the correspondences for loading
    ``product``'s document into ``host``."""
    doc = product.doc
    if not doc.finalized:
        doc.finalize()
    sf = doc.self_family
    if sf is None:
        raise LoaderError("product document has no self-Family")
    unit = doc.to_embedded_unit()
    guid = str(unit["content_doc_guid"])
    if doc.document_guid and str(doc.document_guid) != guid:
        raise LoaderError(f"content GUID mismatch: doc {doc.document_guid} vs unit {guid}")
    max_own = max(e.elem_id for e in doc.elements)
    if max_own <= 0:
        raise LoaderError("product elements carry no ids")
    plan = LoadPlan(guid=guid, fam_doc_guid=str(uuid.uuid4()),
                    session_guid_hex=uuid.uuid4().hex,
                    family_name=doc.name or product.name,
                    type_name=symbol_type_name(doc, doc.name or product.name),
                    episode=int(host.episode))
    # absorbed indices of OUR document (the self-Family's m_familyIds)
    fids = (((sf.obj.get("m_familyIds") or {}).get("value") or {})
            .get("m_data") or [])
    plan.abs_index = {int(e["m_elementId"]): int(e["m_index"]) for e in fids}
    # allocate host ids: Family, twins, surrogate, symbol, symbol-surrogate,
    # instance -- monotonic above every id our document uses
    nxt = [max(int(host.watermark), int(max_own))]

    def alloc() -> int:
        nxt[0] += 1
        return nxt[0]
    from .skeleton import PARAM_TWIN_CLASSES
    plan.host_family_id = alloc()
    for e in doc.elements:
        if e.class_name in PARAM_TWIN_CLASSES:
            plan.twin_of[e.elem_id] = alloc()
    plan.surrogate_id = alloc()
    plan.symbol_id = alloc()
    plan.symbol_surrogate_id = alloc()
    # every OTHER real-named type gets its own pair (a host Family table row
    # is always backed by a FamSymSurrogate+FamilySymbol); primary first, so
    # a one-type load allocates exactly what it always did
    plan.type_names = [plan.type_name]
    plan.symbol_ids = [plan.symbol_id]
    plan.symbol_surrogate_ids = [plan.symbol_surrogate_id]
    for tname in real_type_names(doc):
        if tname != plan.type_name:
            plan.type_names.append(tname)
            plan.symbol_ids.append(alloc())
            plan.symbol_surrogate_ids.append(alloc())
    if place:
        plan.instance_id = alloc()
    # load classification: resolve OUR connector's LC by NAME to a host LC
    lc = next((e for e in doc.elements
               if e.class_name == "ElectricalLoadClassification"), None)
    lc_name = str((lc.obj or {}).get("m_name") or "") if lc is not None else ""
    plan.load_class_name = lc_name
    if lc_name and lc_name in host.load_classifications:
        plan.load_class_host = host.load_classifications[lc_name]
    elif "Other" in host.load_classifications:
        plan.load_class_host = host.load_classifications["Other"]
        if lc_name:
            plan.notes.append(f"family load classification {lc_name!r} not in host; "
                              "resolved to host 'Other'")
    # core ids = the host resources our family binds to
    core = set()
    if host.category_gstyle != INVALID:
        core.add(int(host.category_gstyle))
    if plan.load_class_host != INVALID:
        core.add(int(plan.load_class_host))
    plan.core_ids = sorted(core)
    return plan


# ---------------------------------------------------------------------------
# record authoring -- the HOST elements (L4)
# ---------------------------------------------------------------------------

def _skel(elem_id: int, class_name: str, header: dict, obj: dict,
          rep: Optional[dict] = None, *, owner_id: int = -1, kind: str = ""):
    from ..genesis.skeleton import SkelElement
    return SkelElement(elem_id, class_name, header, obj, rep,
                       owner_id=owner_id, kind=kind)


def _header(class_name: str, *, category: int = -1, family_id: int = -1,
            deletion: Sequence[int] = (), regen_only: Sequence[int] = (),
            appearance: Sequence[int] = (), bbox=None) -> dict:
    from ..genesis.skeleton import element_header
    flags, vflags = HDR_FLAGS.get(class_name, (10, -32768))
    return element_header(class_name, category=category, family_id=family_id,
                          deletion=sorted({int(x) for x in deletion if int(x) != 0}),
                          regen_only=sorted({int(x) for x in regen_only}),
                          appearance=sorted({int(x) for x in appearance}),
                          flags=flags, visible_view_flags=vflags, bbox=bbox)


def author_param_twins(product, plan: LoadPlan) -> List:
    """One host TWIN per top-level family user parameter: the family
    document's own parameter object with exactly four rewrites [VERIFIED
    455334 vs 786844 diff] -- ``skeleton.retarget_param_twin``: ``m_id`` /
    ``m_pParamDef.m_paramElemId`` -> the host id, ``m_famId`` -> the host
    Family, a local ``m_typeId`` ->
    ``revit.local.family:<32hex session guid><%08x host id>-1.0.0`` (a SHARED
    ``ParamElemExternal`` twins as itself and KEEPS its
    ``revit.local.shared:<guid>`` identity + GUID key verbatim [UNVERIFIED
    host-side: registering the GUID in the host's ``ExternalParamTracking`` /
    reusing a host definition of the same GUID is the open follow-up -- no
    loads claim]).  Header ``m_familyId`` = the host Family, deletion =
    [host Family, self].  ElemRec owner = the host Family.
    """
    from .skeleton import PARAM_TWIN_CLASSES, retarget_param_twin
    out = []
    hf = plan.host_family_id
    for e in product.doc.elements:
        if e.class_name not in PARAM_TWIN_CLASSES:
            continue
        tid = plan.twin_of[e.elem_id]
        obj = retarget_param_twin(_dc(e.obj), tid, hf, plan.session_guid_hex)
        hdr = _header(e.class_name, category=-1, family_id=hf, deletion=[hf, tid])
        out.append(_skel(tid, e.class_name, hdr, obj, None,
                         owner_id=hf, kind="param_twin"))
    return out


def author_family_surrogate(plan: LoadPlan, category: int):
    """The ``FamilySurrogate`` stand-in for the loaded family
    [V shape 455404]: {m_elemId = host Family, m_name = family name,
    m_categoryId, m_previewElemId = -1 (56/159 surrogates carry -1),
    m_guid = the constant creator GUID}."""
    from ..genesis.types import blank_object
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
        "m_categoryId": int(category),
        "m_previewElemId": -1,
        "m_guid": {"m_guid": SURROGATE_GUID},
        "m_bIsAdaptive": False,
    })
    hdr = _header("FamilySurrogate", deletion=[plan.host_family_id, plan.surrogate_id])
    return _skel(plan.surrogate_id, "FamilySurrogate", hdr, o, None, kind="family_surrogate")


def author_famsym_surrogate(plan: LoadPlan, category: int):
    """The per-symbol ``FamSymSurrogate`` [V shape 455410]: {m_elemId =
    the symbol, m_name = type name, m_categoryId, m_famSurrogateId = the
    FamilySurrogate}."""
    from ..genesis.types import blank_object
    o = blank_object("FamSymSurrogate")
    o.update({
        "m_docAccess": {"m_pDoc": _weak(1)},
        "m_id": plan.symbol_surrogate_id,
        "m_assocLevelId": -1, "m_famId": -1, "m_unplacedOwnerId": -1,
        "m_ownerDBViewId": -1, "m_createdPhaseId": -1, "m_demolishedPhaseId": -1,
        "m_designOptionId": -1, "m_locked": False, "m_moribund": False,
        "m_dummy": False,
        "m_pADoc": _weak(1),
        "m_elemId": plan.symbol_id,
        "m_name": plan.type_name,
        "m_categoryId": int(category),
        "m_famSurrogateId": plan.surrogate_id,
    })
    hdr = _header("FamSymSurrogate",
                  deletion=[plan.surrogate_id, plan.symbol_id, plan.symbol_surrogate_id])
    return _skel(plan.symbol_surrogate_id, "FamSymSurrogate", hdr, o, None,
                 kind="famsym_surrogate")


# -- the host Family (the transform of our self-Family) ----------------------

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


def _connector_facts(product) -> Dict[str, Any]:
    """Pull the electrical facts of OUR connector(s) out of the document:
    index, voltage/poles/apparent-load internal values, the associated
    (parameter-driven) property bindings, and the connector's placement
    (host face) for the symbol's ``m_arrConnectorData``."""
    doc = product.doc
    facts = {"connectors": []}
    for c in doc.elements:
        if c.class_name != "ConnectorElem":
            continue
        v = c.obj or {}
        entry: Dict[str, Any] = {"elem_id": c.elem_id, "index": None,
                                 "voltage": None, "poles": None, "load": None,
                                 "bindings": [], "system_type": None,
                                 "power_factor": None}
        # index
        for key in ("m_index", "m_nIndex", "m_connectorIndex"):
            if isinstance(v.get(key), int):
                entry["index"] = v[key]
                break
        stack = [v]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                if "m_voltage" in n or "m_apparentLoad" in n or "m_poles" in n:
                    entry["voltage"] = n.get("m_voltage", entry["voltage"])
                    entry["poles"] = n.get("m_poles", entry["poles"])
                    entry["load"] = n.get("m_apparentLoad", entry["load"])
                    entry["system_type"] = n.get("m_systemType", entry["system_type"])
                    entry["power_factor"] = n.get("m_powerFactor", entry["power_factor"])
                if "m_paramDrivenData" in n:
                    for b in n.get("m_paramDrivenData") or []:
                        prop = b.get("m_elemPropId")
                        fam = b.get("m_famParamId")
                        if isinstance(prop, int) and isinstance(fam, int):
                            entry["bindings"].append((prop, fam))
                if entry["index"] is None and isinstance(n.get("m_index"), int):
                    entry["index"] = n["m_index"]
                for x in n.values():
                    stack.append(x)
            elif isinstance(n, list):
                stack.extend(n)
        if entry["index"] is None:
            entry["index"] = 1
        facts["connectors"].append(entry)
    return facts


def _connector_data_cells(product, plan: LoadPlan) -> List[dict]:
    """One ``ConnectorDataCell`` per connector — delegates row-building to
    the corpus-lawful cell in :mod:`rvt.famload_fix` (D4: every corpus cell
    carries the canonical 11..21-row m_oRelevantParams table; the electrical
    cells one canonical 15-row order [V 22/22])."""
    from ..famload_fix import electrical_connector_cell
    facts = _connector_facts(product)
    cells = []
    for con in facts["connectors"]:
        bindings = [{"first": int(prop),
                     "second": int(plan.twin_of.get(fam, fam))}
                    for prop, fam in con.get("bindings") or []]
        cells.append(electrical_connector_cell(
            con, bindings=bindings,
            load_class_host=plan.load_class_host))
    return cells


def _preview_view_infos(product) -> List[dict]:
    """``DBViewInfoForPreview`` entries mirroring OUR document's views
    (the specimen carries one per family view: 'Ref. Level' plan +
    ceiling + elevations) [V shape; the required set is an ACCEPTANCE
    question]."""
    out = []
    doc = product.doc
    names = []
    for e in doc.elements:
        if e.class_name in ("DBViewPlan", "DBViewProject"):
            nm = (e.obj or {}).get("m_name") or "Ref. Level"
            names.append(str(nm))
    if not names:
        names = ["Ref. Level"]
    seen = set()
    for nm in names:
        if nm in seen:
            continue
        seen.add(nm)
        out.append(_ptr("DBViewInfoForPreview", {
            "m_name": nm,
            "m_horz": [1.0, 0.0, 0.0],
            "m_origin": [0.0, 0.0, 0.0],
            "m_scale": 0.05,
            "m_vert": [0.0, 1.0, 0.0],
            "m_viewerTargetPos": [0.0, 0.0, 0.0],
            "m_viewFamily": 109,
            "m_viewType": 1,
        }))
    return out


def _reference_idx_mgr(product, plan: LoadPlan) -> Optional[dict]:
    """``FamilyReferenceIdxMgr``: reference INDEX -> (Is-Reference code,
    plane name) for the family's origin planes [V: the map keys are the
    RefPlanes' ABSORBED INDICES -- specimen 25/26/27 = its origin planes'
    m_familyIds indices; the code is the RefPlane m_refName].
    """
    names = {0: "Left", 1: "Center (Left/Right)", 2: "Right", 3: "Front",
             4: "Center (Front/Back)", 5: "Back", 7: "Center (Elevation)"}
    entries = []
    for e in product.doc.elements:
        if e.class_name != "RefPlane":
            continue
        v = e.obj or {}
        if not v.get("m_definesOrigin"):
            continue
        code = v.get("m_refName")
        if not isinstance(code, int):
            continue
        ai = plan.abs_index.get(e.elem_id)
        if ai is None:
            continue
        entries.append({"first": int(ai),
                        "second": {"first": int(code),
                                   "second": v.get("m_name") or names.get(code, "Reference")}})
    if not entries:
        return None
    entries.sort(key=lambda d: d["first"])
    return _ptr("FamilyReferenceIdxMgr", {"m_idxToRefMap": entries})


def author_host_family(product, plan: LoadPlan, host: HostContext):
    """The HOST ``Family`` element = OUR self-Family object transformed to
    the host flavour.  Every rule below comes from the field-by-field diff
    of the specimen host Family (454674) against its own embedded self-Family
    (786439) [VERIFIED transform]:

    * id remap: self id -> host Family id, every family-parameter id P_i ->
      its host twin T_i (``m_familyParams``, the type-table rows, cells);
    * ``m_name`` = the family name (the self-Family carries an empty name);
    * ``m_famDocGUID`` minted; ``m_surrogateId`` = our FamilySurrogate;
    * ``m_oFamDoc`` = ``FamilyDocument{m_contentDocGUID = our GUID,
      m_big2SmallMap2 = [(T_i, P_i)] sorted by host id, m_coreIds}``;
    * ``m_familyIds`` narrowed to the HOST-side twins, each keeping its
      embedded counterpart's absorbed index [V 455334->1106 == 786844->1106];
    * ``m_pFamilyTypes`` gains the leading blank ' ' row (= the current
      values) [V] ahead of the REAL-named types keyed by the twins; a blank
      pair the unit table already carries (born blank-pair-first law) is NOT
      copied -- one leading blank, ``m_idx`` on a real pair [corpus law,
      :func:`real_type_names`];
    * host-only: ``m_dbviewInfos`` (preview views), the ``ConnectorDataCell``
      summarizing our connector, ``m_oFamilyReferenceIdxMgr`` (origin
      references), ``m_defaultHeight*`` = -1e30;
    * family-document-only state dropped: ``m_oFamDimConstrMgr``, ``m_fsdos``,
      ``m_refs``, ``m_deletableElements``.
    """
    sf = product.doc.self_family
    o = _dc(sf.obj)
    idmap = dict(plan.twin_of)
    idmap[sf.elem_id] = plan.host_family_id
    o["m_id"] = plan.host_family_id
    o["m_famId"] = -1
    o["m_designOptionId"] = -1
    o["m_name"] = plan.family_name
    o["m_famDocGUID"] = plan.fam_doc_guid
    o["m_surrogateId"] = plan.surrogate_id
    o["m_path"] = ""                                    # deliberately empty (ours)
    for k in ("m_omniClassCode", "m_classificationDescription", "m_seekItemId",
              "m_familyNameKeyText", "m_dumpSymName"):
        if k in o:
            o[k] = ""
    # -- parameters + type table keyed by the host twins ---------------------
    fp = ((o.get("m_familyParams") or {}).get("value") or {})
    if fp:
        fp["m_params"] = _remap_param_rows(fp.get("m_params") or [], idmap)
    ftt = ((o.get("m_pFamilyTypes") or {}).get("value") or {})
    if ftt:
        pairs = []
        for pr in ftt.get("m_pairs") or []:
            if not str(pr.get("name", "")).strip():
                continue                             # the unit's own blank row: never a host type
            pr2 = _dc(pr)
            params = pr2.get("params") or {}
            if isinstance(params, dict):
                params["m_params"] = _remap_param_rows(params.get("m_params") or [], idmap)
            pairs.append(pr2)
        # leading blank ' ' row = the current values [V: host row 0 name ' ']
        cur_rows = _remap_param_rows(fp.get("m_params") or [], {}) if fp else []
        blank = {"name": " ", "params": {"m_params": cur_rows,
                                         "m_geomRefHandles": {"m_offsetGeomMap": []}}}
        ftt["m_pairs"] = [blank] + pairs
        # current type = the primary (instance-facing) real pair [H]
        names = [str(p.get("name", "")) for p in pairs]
        ftt["m_idx"] = 1 + names.index(plan.type_name) if plan.type_name in names else 0
    # -- cells: connector data cell(s) FIRST, then the parameter order cell -
    cl = ((o.get("m_cellList") or {}).get("value") or {})
    cells = []
    if cl:
        cells = list(cl.get("m_cells") or [])
    # remap param ids inside the FamilyParamsOrderCell
    for c in cells:
        cv = (c.get("value") or {}) if isinstance(c, dict) else {}
        if isinstance(cv.get("m_sortedParams"), list):
            cv["m_sortedParams"] = [idmap.get(x, x) if isinstance(x, int) else x
                                    for x in cv["m_sortedParams"]]
    cdc = _connector_data_cells(product, plan)
    all_cells = cdc + cells
    o["m_cellList"] = _ptr("CellList", {"m_cells": all_cells})
    # -- locked param ids -> twins ---------------------------------------------
    lk = o.get("m_lockedParameterIdsForDirectManipulation")
    if isinstance(lk, list):
        o["m_lockedParameterIdsForDirectManipulation"] = sorted(
            {idmap.get(x, x) for x in lk if isinstance(x, int)})
    tp = o.get("m_trivialParamIds")
    if isinstance(tp, list):
        o["m_trivialParamIds"] = [idmap.get(x, x) for x in tp if isinstance(x, int)]
    # -- m_oFamDoc: content GUID + big2small + core ids ----------------------
    big2small = [{"first": int(t), "second": {"m_id64": int(p)}}
                 for p, t in sorted(plan.twin_of.items(), key=lambda kv: kv[1])]
    o["m_oFamDoc"] = _ptr("FamilyDocument", {
        "m_contentDocGUID": plan.guid,
        "m_big2SmallMap2": big2small,
        "m_coreIds": list(plan.core_ids),
    })
    # -- m_familyIds: the host twins with their embedded absorbed indices ---
    fids = []
    for p, t in sorted(plan.twin_of.items(), key=lambda kv: kv[1]):
        ai = plan.abs_index.get(p)
        if ai is None:
            continue
        fids.append({"m_elementId": int(t), "m_index": int(ai)})
    o["m_familyIds"] = _ptr("ElementIdIndexPairSet", {"m_data": fids})
    # keep m_nextAbsorbedIndex = our document's own value
    # -- host-only members -----------------------------------------------------
    o["m_dbviewInfos"] = _preview_view_infos(product)
    rim = _reference_idx_mgr(product, plan)
    o["m_oFamilyReferenceIdxMgr"] = rim
    o["m_defaultHostThickness"] = -1e30
    o["m_defaultHeightAboveLevel"] = -1e30
    # -- family-document-only state dropped ------------------------------------
    # D3 corpus law: the HOST Family carries a (possibly empty) FamDimConstrMgr
    # in 831/831 specimens — never null (WF_fix-certified form).
    from ..genesis.residue_c import famdim_constr_empty
    o["m_oFamDimConstrMgr"] = famdim_constr_empty()
    o["m_fsdos"] = []
    o["m_refs"] = []
    o["m_deletableElements"] = []
    o["m_oldCurveElemsWithBadSketchAndSP"] = []
    # -- registered-object numbering (m_oFamDoc = pid 3 on the specimen) ------
    from .geometry import assign_pids
    assign_pids(o)
    # -- header: deletion = built-ins used + core ids + big2small host ids +
    #    self + twins + surrogate (specimen shape) -----------------------------
    negs: set = set()
    _collect_negative_param_ids(o, negs)
    deletion = set(negs) | set(plan.core_ids) | set(plan.twin_of.values())
    deletion |= {plan.host_family_id, plan.surrogate_id}
    hdr = _header("Family", category=-1, deletion=sorted(deletion))
    return _skel(plan.host_family_id, "Family", hdr, o, None, kind="host_family")


# -- the host FamilySymbol (type row + the SYMBOL GEOMETRY) ------------------

def _form_bundle(product):
    """The (single) extrusion form of the product: its element + solid rep."""
    for e in product.doc.elements:
        if e.class_name == "ExtrusionElem":
            return e
    return None


def _box_extent(rep: dict) -> Tuple[List[float], List[float]]:
    bb = rep.get("m_bBox") or rep.get("m_tightbBox")
    if not bb:
        raise LoaderError("form rep carries no bbox")
    return [float(x) for x in bb[0]], [float(x) for x in bb[1]]


def _symbol_placement_data(product, plan: LoadPlan) -> Dict[str, Any]:
    """The symbol's non-geometry cargo, independent of the solid: the
    connector data (index + placement frame on the top face), the strong
    reference planes (origin planes by Is-Reference code), the plan-projected
    origin, and the box extents.  Shared by the solid (F4a) and dummy (F4b)
    symbol variants."""
    form = _form_bundle(product)
    if form is not None and form.rep is not None:
        lo, hi = _box_extent(form.rep)
    else:                                              # pragma: no cover
        lo, hi = [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]
    facts = _connector_facts(product)
    top_y = hi[1]
    mid_z = (lo[2] + hi[2]) / 2.0
    cx = (lo[0] + hi[0]) / 2.0
    conn_data = []
    for con in facts["connectors"]:
        conn_data.append({
            "m_trf": {"m_3x3": [[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [0.0, -1.0, 0.0]],
                      "m_or": [float(cx), float(top_y), float(mid_z)]},
            "m_index": int(con.get("index") or 1),
        })
    strong_refs = []
    for e in product.doc.elements:
        if e.class_name != "RefPlane":
            continue
        v = e.obj or {}
        if v.get("m_definesOrigin") and isinstance(v.get("m_refName"), int):
            strong_refs.append({
                "m_intermediateTags": [], "m_oNextRef": None,
                "m_elemId": int(plan.symbol_id), "m_ownerDBViewId": -1,
                "m_foreignElemIdRef": {"m_id64": -1},
                "m_geomTag": int(v["m_refName"]), "m_subTag": -1,
                "m_famMemberIdx": -1, "m_flags": 0, "m_isLazyRef": False,
            })
    origin = [float(cx), float((lo[1] + hi[1]) / 2.0), 0.0]
    return {"connector_data": conn_data, "strong_refs": strong_refs,
            "origin": origin, "bbox": (lo, hi)}


def build_symbol_geometry(product, plan: LoadPlan, host: HostContext,
                          *, absorbed_form_index: int) -> Dict[str, Any]:
    """Author the symbol geometry from OUR extrusion's authored solid
    (rvt.famgen.geometry): the seq-103 ``GElement`` the placed instances
    display + the ``m_geomSteps`` history tables + ``m_pGeomTable`` that map
    every symbol-space id back to (kind, tag, form-by-absorbed-index).

    Grammar [V from FamilySymbol 455409]:
      * one flat symbol id space 0..N: graph-node entries first (history type
        6, no form), then a fresh id for every solid face (type 5:
        [5, faceTag, formAbsIdx]) and edge (type 3: [3, edgeTag, formAbsIdx,
        -1]), and the ``Geometry`` node's own ``m_geometryTag`` (type 65:
        [65, formAbsIdx, -1, -1, -1]);
      * faces / edges carry the symbol id in ``GInfo.m_tag`` (the family
        document's own solid carries geometry TAGS there);
      * ``m_pGeomTable`` = one ``{m_geomGeneratorId: 1}`` per id 0..N
        (33 entries = ids 0..32 on the specimen);
      * the root ``GInfo.m_categoryId`` = the host category GStyle,
        ``m_tag`` = the symbol element id.
    ACCEPTANCE [H]: the id-space semantics are inferred from one specimen.
    """
    form = _form_bundle(product)
    if form is None or form.rep is None:
        raise LoaderError("symbol geometry needs a form with an authored solid rep")
    solid = _dc(form.rep)                              # our GElement (family space)
    lo, hi = _box_extent(solid)
    # -- flat symbol id space ---------------------------------------------------
    face_hist: List[dict] = []
    edge_hist: List[dict] = []
    node_hist: List[dict] = []
    counter = [0]

    def nid() -> int:
        v = counter[0]
        counter[0] += 1
        return v
    # graph nodes: GFilter wrapper + the Geometry node (type-6 entries)
    n_filter = nid()
    n_geom = nid()
    node_hist.append({"m_id": n_filter, "m_faceHist": {"m_keys": [HIST_NODE, 0, -1]}})
    node_hist.append({"m_id": n_geom, "m_faceHist": {"m_keys": [HIST_NODE, 1, -1]}})
    # walk our solid: retag faces / edges with symbol ids, record history
    geom_nodes = [x for x in (solid.get("m_subNodes") or [])
                  if isinstance(x, dict) and x.get("ptr_class") == "Geometry"]
    if not geom_nodes:
        raise LoaderError("form rep carries no Geometry node")
    for gnode in geom_nodes:
        gv = gnode.get("value") or {}
        for f in gv.get("m_pFaces") or []:
            fv = f.get("value") or {}
            gi = fv.get("m_GInfo") or {}
            tag = gi.get("m_tag", -1)
            sid = nid()
            gi["m_tag"] = sid
            gi["m_categoryId"] = -1
            fv["m_GInfo"] = gi
            face_hist.append({"m_id": sid, "m_faceHist": {
                "m_keys": [HIST_FACE, int(tag), int(absorbed_form_index)]}})
        for ed in gv.get("m_pEdges") or []:
            ev = ed.get("value") or {}
            gi = ev.get("m_GInfo") or {}
            tag = gi.get("m_tag", -1)
            sid = nid()
            gi["m_tag"] = sid
            gi["m_categoryId"] = -1
            ev["m_GInfo"] = gi
            edge_hist.append({"m_id": sid, "m_edgeHist": {
                "m_keys": [HIST_EDGE, int(tag), int(absorbed_form_index), -1]}})
        # the Geometry node's own tag (the type-65 'curve' entry)
        gtag = nid()
        gv["m_geometryTag"] = gtag
        curve_entry = {"m_id": gtag, "m_curveHist": {
            "m_keys": [HIST_FORM, int(absorbed_form_index), -1, -1, -1]}}
        ggi = gv.get("m_GInfo") or {}
        ggi["m_categoryId"] = -1
        ggi["m_tag"] = -1
        ggi["m_controlCommand"] = 32768                # solid node [V specimen]
        gv["m_GInfo"] = ggi
    n_ids = counter[0]
    # -- the symbol GElement: wrap our solid in a GFilter under the root -----
    cat_gstyle = host.category_gstyle if host.category_gstyle != INVALID else -1
    root_ginfo = {"m_categoryId": int(cat_gstyle), "m_tag": int(plan.symbol_id),
                  "m_controlCommand": 0, "m_flags": int((solid.get("m_GInfo") or {})
                                                          .get("m_flags", 557060))}
    gfilter = _ptr("GFilter", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": -1, "m_controlCommand": 0,
                    "m_flags": int(root_ginfo["m_flags"])},
        "m_subNodes": [x for x in solid.get("m_subNodes") or []],
        "m_oConditions": [],
        "m_bIsNestedDetailFamily": False,
    })
    sym_rep = {
        "m_GInfo": root_ginfo,
        "m_subNodes": [gfilter],
        "m_bBox": [lo, hi],
        "m_tightbBox": [lo, hi],
        "m_elementId": int(plan.symbol_id),
        "m_gElemType": int(solid.get("m_gElemType", 3)),
        "m_flags": int(solid.get("m_flags", 2)),
    }
    # -- geomSteps: BaseFamilySymbolGStep with the history tables -----------
    step = _ptr("BaseFamilySymbolGStep", {
        "m_faceHistTable": node_hist + face_hist,
        "m_curveHistTableSet": [curve_entry],
        "m_edgeHistTable": edge_hist,
        "m_edgeHistTableReverse": [],
        "m_id": 1,
        "m_version": 4,
        "m_flags": 761725,
        "m_pElem": _weak(2),
        "m_oExtraDatas": None,
    })
    geom_steps = _ptr("GeomStepList", {
        "m_nonBRepGList": [],
        "m_bRepFormGList": [step],
        "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [],
        "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None,
        "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None,
        "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [2, 2, 2, 2, 2],
        "m_idCounter": 2,
        "m_flags": 9,
    })
    geom_table = _ptr("GeomTable", {
        "m_refPntMirrored": False,
        "m_table": [{"m_geomGeneratorId": 1} for _ in range(n_ids)],
        "m_bigTableOwner": None,
        "m_materialMarkers": [],
        "m_faceTypeMarkers": [],
    })
    # -- connector data + strong references + origin (shared with F4b) -----
    plc = _symbol_placement_data(product, plan)
    return {
        "rep": sym_rep,
        "geom_steps": geom_steps,
        "geom_table": geom_table,
        "connector_data": plc["connector_data"],
        "strong_refs": plc["strong_refs"],
        "bbox": (lo, hi),
        "origin": plc["origin"],
        "geometry_tag": counter[0] - 1,
        "n_symbol_ids": n_ids,
        "history": {"faces": len(face_hist), "edges": len(edge_hist),
                    "nodes": len(node_hist), "geom_table": n_ids},
    }


def author_family_symbol(product, plan: LoadPlan, host: HostContext,
                         type_rows: List[dict], *, solid: bool = True):
    """The host ``FamilySymbol`` for ONE type (``plan.type_name`` /
    ``plan.symbol_id``; :func:`_author_load` calls it once per real-named
    type with a per-pair view of the plan).

    Content = OURS: the type name, the parameter row (the same rows as the
    host Family's, keyed by the twins), and the symbol geometry (or, in the
    ``solid=False`` variant, a ``SerializedDummy`` rep and no geometry
    history -- the F4b 'let Revit regenerate the symbol' question).  The
    scalar / flag defaults are the format's ``FamilySymbol`` defaults with
    the electrical-equipment values of the specimen (455409) as reference,
    each set explicitly (genesis discipline).
    """
    from ..genesis.types import blank_object
    from .geometry import assign_pids
    o = blank_object("FamilySymbol")
    # D3 corpus law: every FamilySymbol carries m_pMoveRestrictions (an empty
    # 0x3 Matrix) in 2,710/2,710 specimens — never null (WF_fix-certified).
    from ..genesis.residue_c import move_restrictions_empty
    o["m_pMoveRestrictions"] = move_restrictions_empty()
    geo = None
    form = _form_bundle(product)
    if solid:
        if form is None or form.rep is None:
            raise LoaderError("solid symbol requested but the product form has no authored solid "
                              "(regenerate the product with solid=True)")
        ai = plan.abs_index.get(form.elem_id)
        if ai is None:
            raise LoaderError("extrusion has no absorbed index in the self-Family")
        geo = build_symbol_geometry(product, plan, host, absorbed_form_index=ai)
    o.update({
        "m_pParamValueSetDouble": None, "m_pParamValueSetInt": None,
        "m_pParamValueSetAString": None, "m_pParamValueSetElementId": None,
        "m_constrInfo": [],
        "m_docAccess": {"m_pDoc": _weak(1)},
        "m_id": int(plan.symbol_id),
        "m_assocLevelId": -1, "m_famId": -1, "m_unplacedOwnerId": -1,
        "m_ownerDBViewId": -1, "m_createdPhaseId": -1, "m_demolishedPhaseId": -1,
        "m_designOptionId": -1, "m_locked": False, "m_moribund": False,
        "m_dummy": False,
        "m_symbolInfo": _ptr("SymbolInfo", {"m_name": plan.type_name}),
        "m_renderStyleId": -1, "m_previewElemId": -1,
        "m_pCutLoops": [], "m_cutDirs": [], "m_cutIndices": [],
        "m_pParams": _ptr("FamilyParams", {
            "m_params": _remap_param_rows(type_rows, plan.twin_of),
            "m_geomRefHandles": {"m_offsetGeomMap": []}}),
        "m_controlIcons": [], "m_controlIconTags": [],
        "m_textNoteData": [], "m_tagNoteData": [],
        "m_refs": [], "m_refFaces": [],
        "m_closurePlanes": [],
        "m_gTagDirFlagsPairs": [], "m_nonBRepGeomPtrs": [],
        "m_familyId": int(plan.host_family_id),
        "m_masterId": -1, "m_slaveTrackerId": -1,
        "m_partitionSurrogateId": int(plan.symbol_surrogate_id),
        "m_ownerInstanceId": -1, "m_stretchPrototypeId": -1,
        "m_stretchCount": 0, "m_geomTagOfDummyCurveRef": -1,
        "m_idxOfFirstCoreLayerRefFace": -1, "m_hasParamDefValue": 0,
        "m_faceBasedHostNormal": 0, "m_mirrored": False,
        "m_bHostLayersFlippedY": False, "m_active": True, "m_preview": False,
        "m_hasRotCenter": False, "m_visibilityIsOld": False,
        "m_bMayBeStretchable": False, "m_bConfirmedStretchable": False,
        "m_bHasNothingVisible": False, "m_bCantBeStretched": False,
        "m_labelParamTagInfo": [], "m_complexCutRefIds": [],
        "m_complexCutGeoms": [], "m_dummyHostGeoms": [],
        "m_dummyHostCutFaceTags": [], "m_dummyHostInsertionFaceTags": [],
        "m_strongRefs": [], "m_setOfInPlaceTotalParentIds": [],
        "m_notRotatedNodes": [], "m_lightSrcParamIds": [],
        "m_lightSrcGReps": [], "m_lightSrcValues": [],
        "m_arrProfileLoops": [], "m_pretaggingGNodes": [],
        "m_pretaggingTranslations": [], "m_arrConnectorData": [],
        "m_arrFamSymRegenData": [], "m_flippedGeomRefHandlesSet": [],
        "m_subInstData": [], "m_subElemData": [], "m_imposterLightTrfs": [],
        "m_geomTag2MaterialId": [],
        "m_cellList": _ptr("CellList", {"m_cells": [
            _ptr("FamilySymbolPatternHelper", {
                "m_PatternPositionMap": [], "m_substituteFaceMap": []})]}),
        "m_origin": [0.0, 0.0, 0.0], "m_rotCenter": [0.0, 0.0, 0.0],
        "m_cutPlaneHeights": [0.0, 0.0],
    })
    rep = None
    bbox = None
    if geo is not None:
        o["m_geomSteps"] = geo["geom_steps"]
        o["m_pGeomTable"] = geo["geom_table"]
        o["m_arrConnectorData"] = geo["connector_data"]
        o["m_strongRefs"] = geo["strong_refs"]
        o["m_geomTag2MaterialId"] = [{"first": int(geo["geometry_tag"]), "second": -1}]
        o["m_origin"] = list(geo["origin"])
        o["m_rotCenter"] = list(geo["origin"])
        lo, hi = geo["bbox"]
        o["m_outline"] = {"m_minmax": [lo, hi]}       # inline value class (Outline)
        rep = geo["rep"]
        bbox = (lo, hi)
    else:
        # F4b: no symbol geometry -> Revit must regenerate it from the
        # embedded document.  Connector data / origin / references still ours.
        plc = _symbol_placement_data(product, plan)
        o["m_arrConnectorData"] = plc["connector_data"]
        o["m_strongRefs"] = plc["strong_refs"]
        o["m_origin"] = list(plc["origin"])
        o["m_rotCenter"] = list(plc["origin"])
        lo, hi = plc["bbox"]
        o["m_outline"] = {"m_minmax": [lo, hi]}
        bbox = (lo, hi)
        o["m_geomSteps"] = None
        o["m_pGeomTable"] = None
    assign_pids(o)
    if rep is not None:
        assign_pids(rep)
    # header: the CATEGORY sits on the symbol header, plus the geometry bbox
    negs: set = set()
    _collect_negative_param_ids(o, negs)
    deletion = (set(negs) | {plan.host_family_id, plan.symbol_id,
                             plan.symbol_surrogate_id} | set(plan.twin_of.values()))
    regen = [host.category_gstyle] if host.category_gstyle != INVALID else []
    hdr = _header("FamilySymbol", category=host.category,
                  deletion=sorted(deletion), regen_only=regen, bbox=bbox)
    el = _skel(plan.symbol_id, "FamilySymbol", hdr, o, rep, kind="family_symbol")
    return el, geo


# -- the placed FamilyInstance -----------------------------------------------

def _connector_slot(index: int) -> dict:
    """One connector object of an instance connector manager [V shape:
    the specimen slot], unconnected (empty refs)."""
    return _ptr("Connector", {
        "m_arrRefs": [],
        "m_pElement": _weak(2),
        "m_nIndex": int(index),
        "m_mode": 1,
        "m_modifiers": [
            _ptr("FamilyConnectorPosition", {"m_pConnector": _weak(4)}),
            _ptr("MEPFamilyConnectorCalculationElectrical", {
                "m_pConnector": _weak(4), "m_velocityPressureImpl": 0.0,
                "m_idDownstreamCircuit": -1}),
            _ptr("MEPFamilyConnectorDataElectrical", {
                "m_pConnector": _weak(4),
                "m_delayedWriteParamMap": {"m_paramIdValueMap": []}}),
        ],
    })


def author_family_instance(product, plan: LoadPlan, host: HostContext, *,
                           position: Optional[Sequence[float]] = None,
                           circuit_slots: int = 0):
    """Place one instance of our symbol via ``rvt.mutate``'s proven instance
    recipe (clone the placement SCAFFOLDING of an existing instance of the
    category), pointed at OUR symbol (``symbol == masterSymbol`` -- the
    free/simple pattern; no per-host slave geometry symbol), on the specimen
    instance's face host (a SketchPlane), with the connector manager rebuilt
    for OUR connectors (never the template family's).

    Position: the template instance's origin shifted along the world axis
    least aligned with the host face normal (a few feet along the wall), so
    ours does not overlap the sample's own equipment.
    """
    from ..mutate import CLASS_FAMILY_INSTANCE
    doc = host.doc
    tpl = host.template_instance
    if tpl == INVALID:
        raise LoaderError("no template instance for placement (host has no "
                          "instance of the family's category)")
    tv = doc.value(tpl) or {}
    obj = _dc(tv)
    eid = plan.instance_id
    sym = plan.symbol_id
    obj["m_id"] = eid
    obj["m_famId"] = -1
    obj["m_designOptionId"] = -1
    obj["m_demolishedPhaseId"] = -1
    obj["m_masterSymbolId"] = sym
    obj["m_superInstanceId"] = -1
    obj["m_ownerElemId"] = -1
    obj["m_subInstTable"] = []
    obj["m_refs"] = []
    obj["m_offsetPosArr"] = []
    # placement transform: template's, shifted
    ii_h = obj.get("m_pInstanceInfo") or {}
    ii = ii_h.get("value") if isinstance(ii_h, dict) else None
    if ii is None:
        ii = {}
        obj["m_pInstanceInfo"] = _ptr("InstanceInfo", ii)
    trf = (ii.get("m_Trf") or {})
    m3 = trf.get("m_3x3") or [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    org = trf.get("m_or") or [0.0, 0.0, 0.0]
    if position is None:
        # shift along the world axis least aligned with the face normal
        try:
            n = [float(m3[2][k]) for k in range(3)]        # image of family Z ~ normal
        except Exception:
            n = [0.0, 0.0, 1.0]
        cand = [(abs(n[0]), 0), (abs(n[1]), 1)]           # horizontal world axes
        cand.sort()
        axis = cand[0][1]
        pos = list(org)
        pos[axis] = float(pos[axis]) + 4.0               # 4 ft along the wall
    else:
        pos = [float(position[0]), float(position[1]), float(position[2])]
    ii["m_symbolId"] = sym
    ii["m_GRepId"] = 0
    ii["m_Trf"] = {"m_3x3": m3, "m_or": pos}
    # connector manager rebuilt for OUR connectors (+ per-circuit slots)
    facts = _connector_facts(product)
    slots = [_connector_slot(int(c.get("index") or 1)) for c in facts["connectors"]]
    for k in range(int(circuit_slots)):
        slots.append(_connector_slot(50000 + k))
    # corpus law: every placed instance carries a FamilyInstanceConnectorManager
    # (13,636/13,636 specimens; the base ConnectorManager class appears in none)
    obj["m_pConnectorManager"] = _ptr("FamilyInstanceConnectorManager", {
        "m_setDeletedConnectors": [],
        "m_connPtrArray": slots,
        "m_modifiers": [],
    })
    # instance-level parameter rows: our INSTANCE parameters keyed by twins
    fp = ((product.doc.self_family.obj.get("m_familyParams") or {}).get("value") or {})
    inst_rows = []
    for r in fp.get("m_params") or []:
        if r.get("m_instance"):
            r2 = _dc(r)
            pid = r2.get("m_paramId")
            if isinstance(pid, int) and pid in plan.twin_of:
                r2["m_paramId"] = plan.twin_of[pid]
            inst_rows.append(r2)
    ip = obj.get("m_pInstParams")
    if isinstance(ip, dict) and isinstance(ip.get("value"), dict):
        ip["value"]["m_params"] = inst_rows
    else:
        obj["m_pInstParams"] = _ptr("FamilyParams", {
            "m_params": inst_rows, "m_geomRefHandles": {"m_offsetGeomMap": []}})
    # id remap of any remaining self-references of the template, then the
    # registered-object pid space renumbered from the record root
    from .geometry import assign_pids
    _walk_replace_ids(obj, {int(tv.get("m_id", -999999)): eid})
    assign_pids(obj)
    # seq-103 rep: the formulaic GInstance -> symbol reference
    rep = None
    trep = doc.decode(tpl, 103)
    if trep is not None and trep.clean and trep.value:
        rep = _dc(trep.value)
        _walk_replace_ids(rep, {int(tv.get("m_id", -999999)): eid})
        gi = rep.get("m_GInfo") or {}
        gi["m_tag"] = eid
        rep["m_elementId"] = eid
        for node in rep.get("m_subNodes") or []:
            nv = node.get("value") or {}
            info = ((nv.get("m_instanceInfo") or {}).get("value")) or {}
            if info:
                info["m_symbolId"] = sym
                info["m_Trf"] = {"m_3x3": m3, "m_or": pos}
        rep["m_bBox"] = [[pos[0] - 1.0, pos[1] - 1.0, pos[2]],
                         [pos[0] + 1.0, pos[1] + 1.0, pos[2] + 3.0]]
        rep["m_tightbBox"] = rep["m_bBox"]
        assign_pids(rep)
    # header: category + deletion (our symbol, family, host, self)
    hostid = obj.get("m_hostId", -1)
    deletion = {sym, eid, plan.host_family_id}
    if isinstance(hostid, int) and hostid > 0:
        deletion.add(hostid)
    lvl = obj.get("m_scheduleOnlyLevelId", -1)
    if isinstance(lvl, int) and lvl > 0:
        deletion.add(lvl)
    hdr = _header("FamilyInstance", category=host.category,
                  deletion=sorted(deletion), appearance=[sym],
                  regen_only=[plan.host_family_id],
                  bbox=([pos[0] - 1.0, pos[1] - 1.0, pos[2]],
                        [pos[0] + 1.0, pos[1] + 1.0, pos[2] + 3.0]))
    el = _skel(eid, "FamilyInstance", hdr, obj, rep, kind="family_instance")
    el.notes.append(f"placement scaffolding cloned from host instance {tpl} "
                    f"(class {doc.class_of(tpl)}); symbol == masterSymbol == {sym}; "
                    f"host {hostid}; connector manager rebuilt for our "
                    f"{len(facts['connectors'])} connector(s) + {circuit_slots} circuit slot(s)")
    return el


# ---------------------------------------------------------------------------
# L5 -- the host ADocument (Global/Latest) registrations
# ---------------------------------------------------------------------------

def _appinfo_slot(value: dict, class_name: str) -> Optional[dict]:
    mgr = (value.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") == class_name:
            return x.get("value")
    return None


def register_in_host_adocument(latest_value: dict, plan: LoadPlan, *,
                                category: int, unit_records: int,
                                author: str = PRODUCT_NAME) -> Dict[str, Any]:
    """Edit the decoded host ``ADocument`` value IN PLACE with the three
    loaded-family registrations [VERIFIED locations, the only three the
    specimen family / symbol / GUID appear in the host ADocument]:

    1. ``m_oContentTable.m_ContentRecSet`` += {ContentKey guid = our GUID,
       author, history{episodes}, m_EpisodeCounts [(episode, unit records)]}
    2. ``AppInfoManager[FamilyMgr].m_arrLoadedFamilyInfo`` +=
       {m_surrogateId, m_familyDocGUIDs [our GUID]} (single-GUID entries
       are the norm: 47/159; extra GUIDs are nested embedded documents)
    3. ``AppInfoManager[ElementTrackingData]`` symbol / instance id sets of
       our category += our symbol / instance ids (sorted).
    """
    rep: Dict[str, Any] = {}
    ep = int(plan.episode)
    # 1. ContentTable
    ct = ((latest_value.get("m_oContentTable") or {}).get("value") or {})
    recs = ct.get("m_ContentRecSet")
    if not isinstance(recs, list):
        raise LoaderError("host ContentTable.m_ContentRecSet not a list")
    ours = {
        "m_pHostDocument": _weak(1),
        "m_ContentKey": {"m_guidKey": plan.guid},
        "m_author": author,
        "m_history": {"m_originalElementId": {"m_id64": -1},
                      "m_creationDate": {"m_id": ep},
                      "m_lastModificationDate": {"m_id": ep},
                      "m_lastUserModificationDate": {"m_id": -1}},
        "m_EpisodeCounts": [{"first": {"m_id": ep}, "second": int(unit_records)}],
    }
    recs.append(ours)
    # corpus order: ContentTable records ascend by ContentKey GUID,
    # like the ContentDocuments stream [V 6/6 samples; famload's rule]
    recs.sort(key=lambda r: uuid.UUID(
        str((r.get("m_ContentKey") or {}).get("m_guidKey"))).bytes_le)
    rep["content_table_records"] = len(recs)
    # 2. FamilyMgr
    fm = _appinfo_slot(latest_value, "FamilyMgr")
    if fm is None:
        raise LoaderError("host ADocument has no FamilyMgr appinfo")
    lfi = fm.setdefault("m_arrLoadedFamilyInfo", [])
    lfi.append({"m_surrogateId": int(plan.surrogate_id),
                "m_familyDocGUIDs": [plan.guid]})
    rep["family_mgr_entries"] = len(lfi)
    # 3. ElementTrackingData
    etd = _appinfo_slot(latest_value, "ElementTrackingData")
    if etd is not None:
        for fld, ids in (("m_symbols", list(plan.symbol_ids)),
                         ("m_elems", ([plan.instance_id] if plan.instance_id != INVALID else []))):
            if not ids:
                continue
            arr = etd.setdefault(fld, [])
            row = next((x for x in arr if x.get("m_categoryId") == category), None)
            if row is None:
                row = {"m_categoryId": int(category), "m_elemIdSet": []}
                arr.append(row)
                arr.sort(key=lambda d: d.get("m_categoryId", 0))
            s = row.setdefault("m_elemIdSet", [])
            for i in ids:
                if int(i) not in s:
                    s.append(int(i))
            s.sort()
            rep.setdefault("element_tracking", {})[fld] = len(s)
    else:
        rep["element_tracking"] = "absent (skipped)"
    return rep


# ---------------------------------------------------------------------------
# compose + write
# ---------------------------------------------------------------------------

@dataclass
class LoadResult:
    ok: bool
    out_path: Optional[str]
    plan: Optional[LoadPlan]
    proofs: Dict[str, Any]
    acceptance: List[str]
    elements: List[dict]
    report_path: Optional[str] = None
    stop_reason: str = ""

    def as_json(self) -> dict:
        return {
            "ok": self.ok, "out_path": self.out_path,
            "plan": (self.plan.__dict__ if self.plan else None),
            "proofs": self.proofs, "acceptance": self.acceptance,
            "elements": self.elements, "report_path": self.report_path,
            "stop_reason": self.stop_reason,
        }


def _roundtrip_gate(elements) -> Dict[str, Any]:
    """Every authored record must encode and decode back byte-exact
    (schema-validity + reversibility) before anything is written."""
    from ..genesis.skeleton import roundtrip_report
    return roundtrip_report(elements)


def _type_rows(product, type_name: Optional[str] = None) -> List[dict]:
    """The parameter rows (family-document keyed) of the type named
    ``type_name`` -- by default the current type's."""
    sf = product.doc.self_family
    ftt = ((sf.obj.get("m_pFamilyTypes") or {}).get("value") or {})
    pairs = ftt.get("m_pairs") or []
    if pairs:
        idx = product.doc.current_type if product.doc.current_type < len(pairs) else 0
        if type_name is not None:
            named = [i for i, p in enumerate(pairs) if str(p.get("name", "")) == type_name]
            idx = named[0] if named else idx
        rows = ((pairs[idx].get("params") or {}).get("m_params")) or []
        return _dc(list(rows))
    fp = ((sf.obj.get("m_familyParams") or {}).get("value") or {})
    return _dc(list(fp.get("m_params") or []))


def _symbol_pairs(plan: LoadPlan) -> List[Tuple[str, int, int]]:
    """(type name, symbol id, sym-surrogate id) per real-named type, primary first."""
    return list(zip(plan.type_names, plan.symbol_ids, plan.symbol_surrogate_ids))


def _plan_host_ids(plan: LoadPlan) -> List[int]:
    """Every host id a load allocates (Family, surrogates, symbols, instance
    if placed, the ParamElem twins) -- the one canonical list."""
    ids = [plan.host_family_id, plan.surrogate_id, plan.instance_id]
    ids += plan.symbol_ids + plan.symbol_surrogate_ids
    return [x for x in ids if x != INVALID] + list(plan.twin_of.values())


@dataclass
class _AuthoredLoad:
    """Everything ONE family contributes to a load, authored and gated in
    memory (no host stream touched yet): the plan, the host elements (L4),
    our embedded ADocument (L3) and our save unit (L2)."""
    plan: LoadPlan
    elements: List[Any]                   # SkelElements, id-sorted
    adocument: dict                       # factory.author_embedded_adocument(...)
    unit: dict                            # factory.build_family_save_unit(...)
    proofs: Dict[str, Any]
    elements_json: List[dict]
    category: int = CAT_ELECTRICAL_EQUIPMENT   # the family's category (its tracking row)

    @property
    def max_host_id(self) -> int:
        """The highest id this load allocates == the host watermark after it
        (what a chained next load would survey)."""
        return max(_plan_host_ids(self.plan))

    def result(self, ok: bool, out_path: Optional[str], *,
               verify: Optional[Dict[str, Any]] = None, stop_reason: str = "") -> "LoadResult":
        proofs = dict(self.proofs)
        if verify is not None:
            proofs["verify_written"] = verify
        return LoadResult(ok=ok, out_path=out_path, plan=self.plan, proofs=proofs,
                          acceptance=list(ACCEPTANCE_LEDGER), elements=self.elements_json,
                          stop_reason=stop_reason)


def _author_load(product, host: HostContext, *, place: bool, symbol_solid: bool,
                 circuit_slots: int) -> _AuthoredLoad:
    """Plan + author + gate ONE family against ``host`` (whose ``watermark``
    is the id floor): the shared front half of the single and the batched
    loader.  Raises :class:`LoaderError` on any gate failure."""
    from . import factory as F
    doc = product.doc
    if not doc.finalized:
        doc.finalize()
    plan = plan_load(product, host, place=place)
    proofs: Dict[str, Any] = {}
    proofs["plan"] = {
        "content_guid": plan.guid, "fam_doc_guid": plan.fam_doc_guid,
        "host_watermark": host.watermark,
        "our_doc_ids": [min(e.elem_id for e in doc.elements),
                        max(e.elem_id for e in doc.elements)],
        "host_ids": {"family": plan.host_family_id, "surrogate": plan.surrogate_id,
                     "symbol": plan.symbol_id, "symbol_surrogate": plan.symbol_surrogate_id,
                     "symbols": list(plan.symbol_ids),
                     "symbol_surrogates": list(plan.symbol_surrogate_ids),
                     "instance": plan.instance_id, "twins": len(plan.twin_of)},
        "type_names": list(plan.type_names),
        "resolved": {"category": host.category,
                     "category_gstyle": host.category_gstyle,
                     "load_classification": {"name": plan.load_class_name,
                                             "host_id": plan.load_class_host},
                     "core_ids": plan.core_ids,
                     "template_instance": host.template_instance,
                     "template_host": host.template_host},
        "notes": host.notes + plan.notes,
    }

    # ---------------- author the host elements -----------------------------
    els = []
    els.extend(author_param_twins(product, plan))
    els.append(author_family_surrogate(plan, host.category))
    els.append(author_host_family(product, plan, host))
    # one FamilySymbol + FamSymSurrogate per real-named type (primary first);
    # every symbol carries the ONE authored solid (geometry is not
    # label-driven) and its own type's parameter row
    geo = None
    for tname, sym, ssur in _symbol_pairs(plan):
        sub = replace(plan, type_name=tname, symbol_id=sym, symbol_surrogate_id=ssur)
        hsym, g = author_family_symbol(product, sub, host, _type_rows(product, tname),
                                       solid=symbol_solid)
        geo = geo if geo is not None else g
        els.append(hsym)
        els.append(author_famsym_surrogate(sub, host.category))
    if place:
        els.append(author_family_instance(product, plan, host,
                                          circuit_slots=circuit_slots))
    els.sort(key=lambda e: e.elem_id)

    # roundtrip gate: every record encodes + decodes back byte-exact
    gate = _roundtrip_gate(els)
    proofs["roundtrip_gate"] = gate
    if gate.get("failed", 1) != 0 or gate.get("roundtrip_ok", 0) != gate.get("records", -1):
        raise LoaderError("a host record failed the encode/decode round trip: "
                          f"{gate.get('failures', [])[:6]}")

    # ---------------- L3: our embedded ADocument + L2: our save unit --------
    ad = F.author_embedded_adocument(doc, episode=plan.episode,
                                     document_guid=plan.guid)
    proofs["embedded_adocument"] = dict(ad["self_check"])
    unit = F.build_family_save_unit(doc)
    if str(unit["guid"]) != plan.guid:
        raise LoaderError(f"save unit GUID {unit['guid']} != content GUID {plan.guid}")
    proofs["save_unit"] = {"guid": unit["guid"], "records": unit["record_count"],
                           "bytes": len(unit["bytes"]), "segments": unit["segments"]}
    if geo is not None:
        proofs["symbol_geometry"] = geo["history"]
    elements_json = [{"elem_id": e.elem_id, "class": e.class_name,
                      "kind": e.kind, "owner_id": e.owner_id,
                      "rep": ("GElement" if e.rep is not None else "SerializedDummy"),
                      "notes": list(e.notes)} for e in els]
    return _AuthoredLoad(plan=plan, elements=els, adocument=ad, unit=unit,
                         proofs=proofs, elements_json=elements_json, category=host.category)


def _framed_load_records(loads: Sequence[_AuthoredLoad], encode_record):
    """PASS-1 input for :func:`rvt.commit.commit_new_elements`: every host
    element of every load (ascending id == load order), framed per seq."""
    recs, elemrecs = [], []
    for a in loads:
        for e in a.elements:
            ne = e.as_new_element(creation_ep=a.plan.episode)
            recs.append({seq: encode_record(seq, ne.elem_id, None, cid, obj)
                         for seq, cid, obj in ne.records()})
            elemrecs.append(ne.elemrec)
    return recs, elemrecs


def load_family_into_project(host_rvt: str = DEFAULT_HOST,
                             out_path: Optional[str] = None,
                             product=None, *,
                             place: bool = True,
                             symbol_solid: bool = True,
                             circuit_slots: int = 0,
                             report_path: Optional[str] = None,
                             validate: bool = True) -> LoadResult:
    """LOAD ``product`` (a :class:`rvt.famgen.factory.FamilyProduct`; default
    = the flagship 400 A Eaton panelboard) into a copy of ``host_rvt`` and,
    if ``place``, place one instance.  Writes ``out_path`` (a ``.rvt``) and
    returns a :class:`LoadResult` with the machine proofs.

    Pipeline: survey host -> regenerate the product ABOVE the host id
    watermark -> plan ids/twins -> author the host elements (twins,
    FamilySurrogate, host Family, FamilySymbol(+geometry), FamSymSurrogate,
    FamilyInstance) -> roundtrip-gate every record -> pass 1
    (``rvt.commit.commit_new_elements``: host elements into save-unit 0 +
    ElemTable + identity) -> pass 2 (splice our embedded save unit, insert
    our ContentDocuments entry, write the edited host ADocument) -> verify.

    Runs under the HOST's own release (``rvt.frontdoor.release_ctx.
    host_release_context`` -- issue #14): joins ``build_intent``'s context
    when called inside it, enters its own when called bare.
    """
    from ..frontdoor.release_ctx import host_release_context
    with host_release_context(host_rvt):
        return _load_family_into_project(
            host_rvt, out_path, product, place=place, symbol_solid=symbol_solid,
            circuit_slots=circuit_slots, report_path=report_path,
            validate=validate)


def _load_family_into_project(host_rvt: str, out_path: Optional[str],
                              product, *, place: bool, symbol_solid: bool,
                              circuit_slots: int, report_path: Optional[str],
                              validate: bool) -> LoadResult:
    from . import factory as F
    if product is None:
        host = survey_host(host_rvt)
        product = F.make_panelboard(vendor="eaton", line="pow-r-line",
                                   mains_a=400, spaces=42, voltage="480Y/277",
                                   mcb=True, mounting="surface",
                                   solid=True, start_id=host.watermark + 1)
    else:
        host = survey_host(host_rvt, category=product_category(product))
        _require_ids_above(product, host.watermark)
    authored = _author_load(product, host, place=place, symbol_solid=symbol_solid,
                            circuit_slots=circuit_slots)
    plan, proofs = authored.plan, authored.proofs

    # L5 (host ADocument) + L1 (ContentDocuments), in memory
    new_latest, cd_new, edit_proofs = _edit_host_registries(host_rvt, host, [authored])
    proofs.update(edit_proofs)
    proofs["adocument_registrations"] = edit_proofs["adocument_registrations"][0]

    if out_path is None:
        # dry run: everything authored + gated, no file
        res = authored.result(False, None, stop_reason="dry run (out_path=None): no file emitted")
        res.acceptance = []
        return res

    # PASS 1 (host elements -> unit 0 + ElemTable) + PASS 2 (unit splice,
    # ContentDocuments, Latest) -> ONE container write
    write_proofs = _commit_and_write(host_rvt, out_path, host, [authored], new_latest, cd_new)
    proofs["pass1_commit"] = write_proofs["pass1_commit"]
    proofs["pass2_partition_splice"] = write_proofs["pass2_partition_splice"][0]

    # ---------------- verify the written file --------------------------------
    ver = verify_loaded_project(out_path, plan, validate=validate)
    ok = bool(ver.get("ok"))
    res = authored.result(ok, out_path, verify=ver,
                          stop_reason=("" if ok else "verify_written reported failures"))
    if report_path:
        _write_report(report_path, res.as_json())
        res.report_path = report_path
    return res


#: what only the Revit / viewer gate can answer about a loaded family
ACCEPTANCE_LEDGER = (
    "H1: the family editor / project accepts a family document whose "
    "embedded ADocument carries an all-null AppInfoManager (the L3 open "
    "question, unchanged)",
    "H2: symbol geometry bookkeeping (BaseFamilySymbolGStep history tables + "
    "GeomTable + the seq-103 solid's flat id space) inferred from ONE "
    "specimen -- the symbol_solid=False variant leaves the symbol geometry "
    "to Revit's own regeneration (the F4a/F4b triage of the geometry stream)",
    "H3: the host Family's core-id / big2small completeness for a family "
    "document that carries no category / object-style copies (our doc has "
    "none; the specimen twins 45 style rows)",
    "H4: FamilySurrogate.m_previewElemId = -1 (56/159 host surrogates carry "
    "-1) and the shared creator GUID; the FamilyMgr entry is single-GUID "
    "(47/159 are)",
    "H5: the placed instance uses symbol == masterSymbol on a face host "
    "(the specimen panelboards use a per-host slave geometry symbol); its "
    "connector manager is rebuilt for our connectors",
    "H6: the ContentTable record's author string is ours (rvt-writer), the "
    "load episode reuses the host's current episode (no new History row)",
)


def _write_report(path: str, payload: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w") as fh:
        json.dump(payload, fh, indent=1, default=str)


def _require_ids_above(product, watermark: int) -> None:
    """The caller must have allocated the product's ids above the host
    watermark (the loader plans host ids above the product's own)."""
    lo = min(e.elem_id for e in product.doc.elements)
    if lo <= watermark:
        raise LoaderError(f"product ids start at {lo} <= host watermark "
                          f"{watermark}: rebuild with start_id={watermark + 1}")


# ---------------------------------------------------------------------------
# the BATCHED loader: N families, ONE host pass (issue #124)
# ---------------------------------------------------------------------------

class _FamilyStepError(LoaderError):
    """A step of the shared host write failed FOR ONE FAMILY (``index`` in
    load order) -- so the caller can exclude exactly that family."""

    def __init__(self, index: int, message: str):
        super().__init__(message)
        self.index = index


@dataclass
class BatchLoadResult:
    """N families loaded in one host pass.  ``loads[i]`` is the per-family
    :class:`LoadResult` (same ``plan`` / ``proofs`` / ``elements`` shape as
    the single loader; ``proofs['verify_written']`` = that family's slice of
    the one verification); ``shared`` = the proofs of the single host edit
    (ADocument re-encode, ContentDocuments, pass-1 commit, partition splices,
    the file-level verification ``verify_written``).  When ``ok`` is False,
    ``culprit`` is the index of the family to blame (authoring gate, an
    attributable write step, or the first failing per-family verification)
    or ``None`` when the failure cannot be pinned on one family (host write
    crashed, file-level verification) -- the caller's degrade policy decides
    what to retry."""
    ok: bool                              # file written, verifies, every family ok
    out_path: Optional[str]               # None when no usable file was written
    loads: List[LoadResult]               # attempted families, in order
    shared: Dict[str, Any]
    stop_reason: str = ""                 # first failure (names the family)
    culprit: Optional[int] = None         # index of the family to blame, if known

    @property
    def n_loaded(self) -> int:
        return sum(1 for r in self.loads if r.ok)

    def as_json(self) -> dict:
        return {"ok": self.ok, "out_path": self.out_path, "stop_reason": self.stop_reason,
                "culprit": self.culprit, "shared": self.shared,
                "loads": [r.as_json() for r in self.loads]}


def load_families_into_project(host_rvt: str, out_path: str, products: Sequence[Any], *,
                               symbol_solid: bool = True,
                               report_path: Optional[str] = None,
                               validate: bool = True) -> BatchLoadResult:
    """LOAD ``products`` (N :class:`rvt.famgen.factory.FamilyProduct`, or
    callables ``f(start_id) -> FamilyProduct`` so each family is regenerated
    above the ids the previous one allocated) into a copy of ``host_rvt`` in
    ONE host pass: survey once, author + gate every family in memory, edit
    ``Global/Latest`` / ``Global/ContentDocuments`` once, one
    ``commit_new_elements`` (all host elements into save-unit 0 + ElemTable),
    splice the N save units, write ``out_path`` once, verify once.

    Byte-for-byte the same streams as chaining :func:`load_family_into_project`
    N times (family i+1 onto family i's output) with the same GUIDs -- ids
    ladder identically, units append in load order, ContentDocuments /
    ContentTable stay GUID-sorted, FamilyMgr entries keep load order -- minus
    N-1 container rewrites, N-1 host surveys and N-1 verifications.  Families
    load UNPLACED (placement is the caller's: ``rvt.mutate.add_family_instance``
    onto the returned symbols).

    Honest, single pass: a family whose authoring gates fail stops the batch
    THERE (the id ladder needs every earlier family) and the families before
    it are written; a failure inside the shared host write (registration,
    ContentDocuments, commit, unit splice) writes NO file and is attributed to
    the offending family when the step is per-family (``culprit``); the
    written file is verified once and each family gets its verdict -- ``ok``
    only if the file verifies and every family does.  What to do with a
    partial result (keep the prefix before ``culprit``, shed a family and try
    again) is the CALLER's degrade policy
    (``rvt.frontdoor.build.stage_load_batched``).

    Runs under the HOST's own release like the single loader.
    """
    from ..frontdoor.release_ctx import host_release_context
    with host_release_context(host_rvt):
        return _load_families_into_project(host_rvt, out_path, list(products),
                                           symbol_solid=symbol_solid,
                                           report_path=report_path, validate=validate)


def _load_families_into_project(host_rvt: str, out_path: str, products: List[Any], *,
                                symbol_solid: bool, report_path: Optional[str],
                                validate: bool) -> BatchLoadResult:
    host = survey_host(host_rvt, category=None)
    shared: Dict[str, Any] = {"host_watermark": host.watermark, "n_products": len(products)}
    authored: List[_AuthoredLoad] = []
    auth_failure = ""                    # why the first un-authorable family failed
    cursor = int(host.watermark)
    bound: Dict[int, HostContext] = {}   # one category binding per distinct family category
    for i, item in enumerate(products):
        try:
            product = item(cursor + 1) if callable(item) else item
            _require_ids_above(product, cursor)
            cat = product_category(product)
            if cat not in bound:
                bound[cat] = bind_category(host, cat)
            a = _author_load(product, replace(bound[cat], watermark=cursor),
                             place=False, symbol_solid=symbol_solid, circuit_slots=0)
        except Exception as exc:                                  # noqa: BLE001
            auth_failure = f"family {i + 1}/{len(products)}: {type(exc).__name__}: {exc}"
            break                        # the id ladder needs every earlier family
        authored.append(a)
        cursor = a.max_host_id
    loads: List[LoadResult] = []
    stop_reason = ""
    culprit: Optional[int] = None
    file_ok = False
    written = False
    if authored:
        try:
            new_latest, cd_new, edit_proofs = _edit_host_registries(host_rvt, host, authored)
            shared.update(edit_proofs)
            shared.update(_commit_and_write(host_rvt, out_path, host, authored,
                                            new_latest, cd_new))
            written = True
        except Exception as exc:                                  # noqa: BLE001
            culprit = getattr(exc, "index", None)
            stop_reason = ((f"family {culprit + 1}/{len(products)}: " if culprit is not None
                            else "host write failed: ") + f"{type(exc).__name__}: {exc}")
            shared["write_error"] = stop_reason
            for k, a in enumerate(authored):
                loads.append(a.result(False, None, stop_reason=(
                    stop_reason if k == culprit else "not written: the shared host write failed")))
            for junk in (out_path, out_path + ".pass1.tmp"):
                try:
                    os.remove(junk)
                except OSError:
                    pass
    if written:
        ver = verify_loaded_projects(out_path, [a.plan for a in authored], validate=validate)
        shared["verify_written"] = {k: v for k, v in ver.items() if k != "per_plan"}
        file_ok = bool(ver["file_ok"])
        for k, (a, pv) in enumerate(zip(authored, ver["per_plan"])):
            loads.append(a.result(bool(pv["ok"]), out_path, verify=pv,
                                  stop_reason="" if pv["ok"] else "verify_written reported failures"))
            if not pv["ok"] and culprit is None:
                culprit = k
                stop_reason = f"family {k + 1}/{len(products)}: verify_written reported failures"
        if not file_ok:
            stop_reason = "file-level verification failed: " + "; ".join(ver["file_errors"])[:300]
    if auth_failure:
        loads.append(LoadResult(ok=False, out_path=None, plan=None, proofs={}, acceptance=[],
                                elements=[], stop_reason=auth_failure))
        if culprit is None and (written and file_ok or not authored):
            culprit = len(authored)              # the un-authorable family is the one to blame
        stop_reason = stop_reason or auth_failure
    res = BatchLoadResult(ok=file_ok and not auth_failure and all(r.ok for r in loads),
                          out_path=out_path if written else None,
                          loads=loads, shared=shared, stop_reason=stop_reason, culprit=culprit)
    if report_path:
        _write_report(report_path, res.as_json())
    return res


def _edit_host_registries(host_rvt: str, host: HostContext,
                          authored: Sequence[_AuthoredLoad]) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """L5 + L1 for every family, in memory: decode the host ``Global/Latest``
    once, register each family (ContentTable / FamilyMgr / tracking data),
    re-encode once and prove it re-decodes clean; insert every family's
    ``Global/ContentDocuments`` entry (GUID-sorted).  Returns
    ``(new_latest_payload, new_content_documents_payload, proofs)``."""
    from . import factory as F
    from ..container import open_rvt
    from ..adocument import decode_latest, encode_latest
    with open_rvt(host_rvt) as f:
        latest_payload = f.inflate("Global/Latest")
        cd_payload = b"".join(f.inflate_all("Global/ContentDocuments"))
    lat = decode_latest(latest_payload)
    if not lat.clean:
        raise LoaderError("host Global/Latest does not decode clean")
    lv = _dc(lat.value)
    regs = []
    for i, a in enumerate(authored):
        try:
            regs.append(register_in_host_adocument(lv, a.plan, category=a.category,
                                                   unit_records=int(a.unit["record_count"])))
        except Exception as exc:                                  # noqa: BLE001
            raise _FamilyStepError(i, f"host ADocument registration failed: "
                                      f"{type(exc).__name__}: {exc}") from exc
    new_latest = encode_latest(lv, trailer=lat.trailer)
    back = decode_latest(new_latest)
    if not back.clean:
        raise LoaderError("edited host ADocument does not re-decode clean")
    ents_before, tail = F.parse_content_documents(cd_payload)
    have = {g for g, _a in ents_before}
    for i, a in enumerate(authored):
        if a.plan.guid in have:
            raise _FamilyStepError(i, f"content document {a.plan.guid} already present in the host")
        have.add(a.plan.guid)
    cd_new = F.assemble_content_documents(
        ents_before + [(a.plan.guid, bytes(a.adocument["payload"])) for a in authored],
        tail=tail or F.CD_END_RECORD)
    ents_after, tail_after = F.parse_content_documents(cd_new)
    have = {g for g, _a in ents_after}
    ours_present = all(a.plan.guid in have for a in authored)
    if not ours_present:
        raise LoaderError("our ContentDocuments entry did not insert")
    return new_latest, cd_new, {
        "adocument_registrations": regs,
        "adocument_reencode": {"clean": bool(back.clean),
                               "bytes_before": len(latest_payload),
                               "bytes_after": len(new_latest)},
        "content_documents": {"entries_before": len(ents_before),
                              "entries_after": len(ents_after),
                              "ours_present": ours_present,
                              "end_record_intact": tail_after == tail,
                              "delta_bytes": len(cd_new) - len(cd_payload)}}


def _commit_and_write(host_rvt: str, out_path: str, host: HostContext,
                      authored: Sequence[_AuthoredLoad],
                      new_latest: bytes, cd_new: bytes) -> Dict[str, Any]:
    """The ONE container rewrite: pass 1 = every family's host elements into
    save-unit 0 + ElemTable (``rvt.commit.commit_new_elements``, via a temp
    file); pass 2 = splice every save unit before the partition end record
    (load order), swap in the edited ContentDocuments / Latest, write
    ``out_path``.  Returns the pass-1 / pass-2 proofs."""
    from . import factory as F
    from ..encode import encode_record
    from ..commit import commit_new_elements
    from ..container import open_rvt
    from ..roundtrip import read_entries
    from ..cfb_writer import write_cfb
    from ..stream_encoders import wrap_global_stream
    from .. import ecc
    recs, elemrecs = _framed_load_records(authored, encode_record)
    tmp1 = out_path + ".pass1.tmp"
    crep = commit_new_elements(host_rvt, tmp1, recs, elemrecs,
                               creation_ep=authored[0].plan.episode,
                               identity={"username": ""})
    rep: Dict[str, Any] = {"pass1_commit": {
        "new_element_ids": list(crep.new_element_ids),
        "elemtable_count_before": crep.elemtable_count_before,
        "elemtable_count_after": crep.elemtable_count_after,
        "watermark_after": crep.watermark_after,
        "per_seq_bytes_added": dict(crep.per_seq_bytes_added),
    }, "pass2_partition_splice": []}
    with open_rvt(tmp1) as f2:
        part_logical = f2.logical(host.partition_name)
    for i, a in enumerate(authored):
        try:
            sp = F.splice_save_unit(part_logical, a.unit["bytes"])
        except Exception as exc:                                  # noqa: BLE001
            raise _FamilyStepError(i, f"unit splice failed: {type(exc).__name__}: {exc}") from exc
        w = sp["walker"]
        rep["pass2_partition_splice"].append({
            "units_before": w["units_before"], "units_after": w["units_after"],
            "walker_errors": w["errors"],
            "our_unit_guid": w["our_unit_guid"],
            "our_unit_records": w["our_unit_records"],
            "id_sets_identical": w["id_sets_identical"],
        })
        if (w["errors"] or w["units_after"] != w["units_before"] + 1
                or w["our_unit_guid"] != a.plan.guid):
            raise _FamilyStepError(i, f"partition splice failed: {w['errors'][:3]} "
                                      f"(unit guid {w['our_unit_guid']}, want {a.plan.guid})")
        part_logical = sp["logical"]
    new_streams = {
        host.partition_name: ecc.frame_stream(part_logical),
        "Global/ContentDocuments": ecc.frame_stream(
            wrap_global_stream("Global/ContentDocuments", cd_new, level=3)),
        "Global/Latest": ecc.frame_stream(
            wrap_global_stream("Global/Latest", new_latest, level=3)),
    }
    out_entries = [replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in read_entries(tmp1)]
    write_cfb(out_path, out_entries)
    try:
        os.remove(tmp1)
    except OSError:
        pass
    return rep


# ---------------------------------------------------------------------------
# verification of the written project
# ---------------------------------------------------------------------------

def verify_loaded_projects(path: str, plans: Sequence[LoadPlan], *,
                           validate: bool = True) -> Dict[str, Any]:
    """Read a loaded project back ONCE and prove, for the file: container/ECC
    health (the validator's structure layer is authoritative), the partition
    walker is clean, the host ADocument decodes clean and (optionally)
    ``rvt.validate`` reports 0 errors; and PER PLAN (``per_plan[i]``): our
    unit is present with our GUID, our host ids are in the ElemTable, the
    ADocument carries our three registrations, our family shows up as a host
    Family whose content GUID is ours with our symbol(s), the instance (if
    any) references our symbol, and the provenance of what the load added is
    ours.  ``ok`` = the file checks AND every plan's checks."""
    from ..container import open_rvt
    from ..families import FamilyIndex, family_documents
    from ..elemtable import parse_elemtable
    from ..partitions import StreamWalker
    from ..adocument import decode_latest
    from ..commit import verify_written
    rep: Dict[str, Any] = {"path": path}
    vw = verify_written(path, {i for plan in plans for i in _plan_host_ids(plan)})
    rep["container"] = {"crc_failures": vw.get("crc_failures"),
                        "ecc_mismatches_heuristic": vw.get("ecc_mismatches"),
                        "walker_errors": vw.get("walker_errors"),
                        "new_ids_found": {str(k): v for k, v in (vw.get("new_ids_found") or {}).items()}}
    # the AUTHORITATIVE container gate = the validator's structure layer
    # (real CRCIO ECC verification of every page).  commit.verify_written's
    # trailer recompute can disagree with ecc.frame_stream on the boundary
    # page when a stream length is an exact multiple of the page payload
    # (a false positive of that heuristic, not a file defect).
    try:
        from ..validate import validate_file as _vf
        sr = _vf(path, layers=("structure",))
        rep["structure_layer"] = {"verdict": "VALID" if sr.ok else "INVALID",
                                  "n_errors": len(sr.errors),
                                  "n_warnings": len(sr.warnings),
                                  "pages_checked": sr.stats.get("pages_checked"),
                                  "errors": [f"{f.where}: {f.message}" for f in sr.errors[:8]]}
    except Exception as exc:                           # pragma: no cover
        rep["structure_layer"] = {"verdict": "ERROR", "n_errors": 1,
                                  "errors": [f"{type(exc).__name__}: {exc}"]}
    if (vw.get("ecc_mismatches") or 0) and rep["structure_layer"].get("n_errors") == 0:
        rep["container"]["note"] = (
            "verify_written's trailer heuristic flagged a page but the validator's "
            "ECC layer verifies every page clean: the boundary page of a stream "
            "whose length is an exact multiple of the page payload (heuristic false "
            "positive; the structure layer is authoritative)")
    with open_rvt(path) as f:
        pn = f.partition_streams()[0]
        w = StreamWalker(f.logical(pn), inflate=False, keep_data=False)
        rep["partition"] = {"units": len(w.units), "walker_errors": list(w.errors[:5])}
        unit_of = {str(uuid.UUID(bytes_le=u.guid)): u.index for u in w.units if u.guid}
        et = parse_elemtable(f.inflate("Global/ElemTable", 0))
        et_ids = {r.id for r in et.records}
        rep["elemtable"] = {"records": len(et.records),
                            "watermark": et.footer.last_id if et.footer else None}
        lat = decode_latest(f.inflate("Global/Latest"))
        lv = lat.value
        rep["adocument"] = {"clean": bool(lat.clean)}
    ct = (((lv.get("m_oContentTable") or {}).get("value") or {}).get("m_ContentRecSet") or [])
    ct_guids = {(r.get("m_ContentKey") or {}).get("m_guidKey") for r in ct}
    fm = _appinfo_slot(lv, "FamilyMgr") or {}
    fm_guids = {g for e in (fm.get("m_arrLoadedFamilyInfo") or [])
                for g in (e.get("m_familyDocGUIDs") or [])}
    etd = _appinfo_slot(lv, "ElementTrackingData") or {}
    tracked = {i for r in (etd.get("m_symbols") or []) for i in (r.get("m_elemIdSet") or [])}
    # family inventory: each of our families is loaded, keyed by our GUID
    fidx = FamilyIndex.open(path)
    docs = family_documents(fidx)
    rep["family_documents"] = {"total_host_families": len(docs)}
    per_plan: List[Dict[str, Any]] = []
    for plan in plans:
        pr: Dict[str, Any] = {"content_guid": plan.guid}
        pr["partition"] = {"our_unit_index": unit_of.get(plan.guid)}
        pr["elemtable"] = {"our_host_ids_present": all(i in et_ids for i in _plan_host_ids(plan))}
        pr["adocument"] = {"content_table_record": plan.guid in ct_guids,
                           "family_mgr_entry": plan.guid in fm_guids,
                           # every symbol of the family (one per real type)
                           "symbol_tracked": all(s in tracked for s in plan.symbol_ids)}
        mine = [d for d in docs if d.get("content_doc_guid") == plan.guid]
        pr["family_documents"] = {
            "ours": [{"family_id": d["family_id"], "family_name": d["family_name"],
                      "category": d["category"], "unit": d["unit"],
                      "n_records": d.get("n_records"),
                      "n_types": d["n_types"], "symbols": d["symbols"],
                      "big2small_count": d["big2small_count"],
                      "n_connectors": d.get("n_connectors"),
                      "n_family_params": d.get("n_family_params")} for d in mine]}
        fam_ok = (len(mine) == 1 and mine[0]["family_id"] == plan.host_family_id
                  and mine[0]["unit"] is not None
                  and any(s.get("symbol_id") == plan.symbol_id for s in mine[0]["symbols"]))
        pr["family_documents"]["ok"] = fam_ok
        # instance -> symbol
        inst_ok = True
        if plan.instance_id != INVALID:
            v = fidx.value(0, plan.instance_id) or {}
            ii = ((v.get("m_pInstanceInfo") or {}).get("value") or {})
            inst_ok = (ii.get("m_symbolId") == plan.symbol_id
                       and v.get("m_masterSymbolId") == plan.symbol_id)
            pr["instance"] = {"symbol_id": ii.get("m_symbolId"),
                              "master_symbol_id": v.get("m_masterSymbolId"),
                              "host_id": v.get("m_hostId"), "ok": inst_ok}
        # provenance of what the load added (our unit + our host elements)
        prov = provenance_ours(path, plan, fidx=fidx)
        pr["provenance_ours"] = prov
        pr["ok"] = bool(pr["partition"]["our_unit_index"] is not None
                        and pr["elemtable"]["our_host_ids_present"]
                        and pr["adocument"]["content_table_record"]
                        and pr["adocument"]["family_mgr_entry"]
                        and fam_ok and inst_ok and bool(prov.get("ok")))
        per_plan.append(pr)
    rep["per_plan"] = per_plan
    # validation
    val_ok = True
    if validate:
        try:
            from ..validate import validate_file
            vr = validate_file(path)                    # project mode (host is a .rvt)
            errs = list(vr.errors)
            rep["validate"] = {"verdict": "VALID" if vr.ok else "INVALID",
                               "n_errors": len(errs),
                               "n_warnings": len(vr.warnings),
                               "errors": [f"[{f.layer}] {f.where}: {f.message}"
                                          for f in errs[:12]],
                               "warnings": [f"[{f.layer}] {f.where}: {f.message}"
                                            for f in vr.warnings[:12]]}
            val_ok = (len(errs) == 0)
        except Exception as exc:                       # pragma: no cover
            rep["validate"] = {"error": f"{type(exc).__name__}: {exc}"}
            val_ok = False
    file_errors = []
    if rep["container"]["crc_failures"] != 0:
        file_errors.append("gzip CRC failures")
    if rep["structure_layer"].get("n_errors") != 0:
        file_errors.append("structure layer: " + "; ".join(rep["structure_layer"].get("errors") or []))
    if rep["container"]["walker_errors"] != 0 or rep["partition"]["walker_errors"]:
        file_errors.append("partition walker errors")
    if not rep["adocument"]["clean"]:
        file_errors.append("host ADocument does not decode clean")
    if not val_ok:
        file_errors.append("rvt.validate: " + "; ".join((rep.get("validate") or {}).get("errors")
                                                          or [str((rep.get("validate") or {}).get("error"))]))
    rep["file_errors"] = file_errors
    rep["file_ok"] = not file_errors
    rep["ok"] = bool(rep["file_ok"] and per_plan and all(pr["ok"] for pr in per_plan))
    return rep


def verify_loaded_project(path: str, plan: LoadPlan, *, validate: bool = True) -> Dict[str, Any]:
    """Read the loaded project back and prove: container/ECC health, the
    partition walker is clean and OUR unit is present with our GUID, our
    family shows up as a host Family whose content GUID is ours with our
    symbol(s), the host ADocument decodes clean and carries our three
    registrations, our host ids are in the ElemTable, the instance (if any)
    references our symbol, and (optionally) ``rvt.validate`` reports 0
    errors.  (The one-plan view of :func:`verify_loaded_projects`: the plan's
    slice merged into the file-level report -- the historical shape.)"""
    rep = verify_loaded_projects(path, [plan], validate=validate)
    for k, v in rep.pop("per_plan")[0].items():
        if k in ("ok", "content_guid"):
            continue
        if isinstance(v, dict) and isinstance(rep.get(k), dict):
            rep[k].update(v)
        else:
            rep[k] = v
    del rep["file_ok"], rep["file_errors"]
    return rep


# ---------------------------------------------------------------------------
# targeted provenance: OUR unit + OUR host elements (the host is the sample)
# ---------------------------------------------------------------------------

def provenance_ours(path: str, plan: LoadPlan, *, fidx=None) -> Dict[str, Any]:
    """Provenance of what the LOAD added -- the embedded family document
    (our unit) and the host elements we authored -- never the host project
    (which is the sample by design).  Uses the factory's suspect / Forge
    vocabulary rules: every string of those records is scanned for company
    / author / path leakage; the ``revit.local.family:`` / ``autodesk.spec``
    identifiers are format VOCABULARY (whitelisted, listed).
    """
    from ..families import FamilyIndex
    from .factory import _collect, _suspects, forge_vocabulary
    rep: Dict[str, Any] = {}
    if fidx is None:
        fidx = FamilyIndex.open(path)
    unit = fidx.unit_by_guid.get(plan.guid)
    strings: List[str] = []
    n_el = 0
    if unit is not None:
        recs = fidx.unit_records(unit).get(102, {})
        for eid in sorted(recs):
            d = fidx.decode(unit, eid, 102)
            n_el += 1
            if d is not None:
                _collect(d.value, strings)
    rep["our_unit"] = {"unit": unit, "elements": n_el,
                       "n_distinct_strings": len(set(strings))}
    sus_unit = _suspects(strings)
    hstrings: List[str] = []
    ids = _plan_host_ids(plan)
    for eid in ids:
        d = fidx.decode(0, eid, 102)
        if d is not None:
            _collect(d.value, hstrings)
    sus_host = _suspects(hstrings)
    rep["host_elements"] = {"count": len(ids), "n_distinct_strings": len(set(hstrings))}
    rep["suspects"] = {"our_unit": sus_unit, "host_elements": sus_host}
    rep["forge_vocabulary_ids"] = forge_vocabulary(strings + hstrings)
    rep["sample_strings"] = sorted(set(strings + hstrings))[:30]
    rep["ok"] = (not sus_unit) and (not sus_host)
    return rep


# ---------------------------------------------------------------------------
# CLI-able driver: the load-proof ladder
# ---------------------------------------------------------------------------

FACTORY_OUT = os.path.join(_ROOT, "experiments", "families", "factory")


def build_load_proofs(out_dir: str = FACTORY_OUT, host_rvt: str = DEFAULT_HOST,
                      *, validate: bool = True) -> Dict[str, Any]:
    """The load-proof ladder for the flagship panel (each an independent
    file, ordered by information value / risk):

    * ``project_with_generated_panel.rvt`` -- family loaded + ONE placed
      instance, our symbol geometry authored (F4a).
    * ``project_with_generated_panel_dummy.rvt`` -- same, symbol geometry
      left as SerializedDummy for Revit to regenerate (F4b).
    * ``project_with_loaded_panel.rvt`` -- family loaded, NOT placed
      (the type is in the project; no instance): the load without the
      placement variable.
    """
    from . import factory as F
    os.makedirs(out_dir, exist_ok=True)
    out: Dict[str, Any] = {"host": host_rvt, "files": {}}
    ladder = [
        ("project_with_generated_panel.rvt", dict(place=True, symbol_solid=True)),
        ("project_with_generated_panel_dummy.rvt", dict(place=True, symbol_solid=False)),
        ("project_with_loaded_panel.rvt", dict(place=False, symbol_solid=True)),
    ]
    host_ctx_wm = survey_host(host_rvt).watermark
    for fname, kw in ladder:
        path = os.path.join(out_dir, fname)
        prod = F.make_panelboard(vendor="eaton", line="pow-r-line",
                                mains_a=400, spaces=42, voltage="480Y/277",
                                mcb=True, mounting="surface", solid=True,
                                start_id=host_ctx_wm + 1)
        res = load_family_into_project(host_rvt, path, prod, validate=validate,
                                       report_path=os.path.splitext(path)[0] + ".json",
                                       **kw)
        out["files"][fname] = {
            "ok": res.ok, "path": path, "report": res.report_path,
            "stop_reason": res.stop_reason,
            "verify": (res.proofs.get("verify_written") or {}).get("ok"),
            "validate": ((res.proofs.get("verify_written") or {})
                         .get("validate", {}).get("n_errors")),
            "our_unit_index": ((res.proofs.get("verify_written") or {})
                               .get("partition", {}).get("our_unit_index")),
            "family": ((res.proofs.get("verify_written") or {})
                       .get("family_documents", {}).get("ours")),
        }
    return out


def main(argv=None) -> int:
    argv = list(argv or [])
    res = build_load_proofs(validate=("--no-validate" not in argv))
    print(f"asset-forge LOADER -> {os.path.dirname(next(iter(res['files'].values()))['path'])}")
    ok = True
    for fname, r in res["files"].items():
        print(f"  {fname:40s} ok={r['ok']}  validate_errors={r['validate']}  "
              f"unit={r['our_unit_index']}")
        if r["family"]:
            fam = r["family"][0]
            print(f"      loaded family {fam['family_id']} '{fam['family_name']}' "
                  f"unit={fam['unit']} recs={fam['n_records']} types={fam['n_types']} "
                  f"symbols={[s['symbol_id'] for s in fam['symbols']]}")
        if not r["ok"]:
            print(f"      STOP: {r['stop_reason']}")
        ok = ok and bool(r["ok"])
    return 0 if ok else 1


if __name__ == "__main__":                              # pragma: no cover
    import sys
    sys.exit(main(sys.argv[1:]))

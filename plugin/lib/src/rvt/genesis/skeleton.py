"""rvt.genesis.skeleton -- the DOCUMENT SCAFFOLDING of a valid Revit project.

Everything a project must contain BEYOND element types (which are the
``rvt.genesis.types`` stream's territory): levels, phases, project
information, the view constellations (project view / 3D view / floor
plan), the site & coordinate skeleton, the units registry, and the six
"table" streams (``Global/ElemTable``, ``Global/History``,
``Global/DocumentIncrementTable``, ``Global/PartitionTable``, ``Contents``,
``BasicFileInfo``) for a MINIMAL one-episode document.

Every constructor here builds its object FIELD BY FIELD in Python from
plain parameters -- no ``.rvt`` is opened, no Autodesk payload is cloned.
The field layouts were derived by schema-directed decoding of specimens in
the Revit 2026 sample corpus and are proven byte-exact by re-encoding those
specimens from their parameter values (``tests/test_genesis_skeleton.py``).
Each claim in the accompanying spec (``docs/writer/genesis-skeleton.md``)
is tagged VERIFIED / INFERRED / UNKNOWN.

Shape contract (shared with the types stream and ``rvt.mutate.NewElement``):
a constructor returns one or more :class:`SkelElement` records, each of
which yields the three partition records of an element::

    (101, ElementHeader class, header dict)
    (102, class_id,            object dict)
    (103, GElement | SerializedDummy, rep dict or {})

plus its 40-byte ``ElemRec`` row for ``Global/ElemTable``.  The encoder
(``rvt.encode.ObjectEncoder``) serializes the dicts against the archive
schema exactly as it does for decoded records.

Ids: genesis assigns its own ElementIds through :class:`IdSource` (or any
duck-typed object with ``.next()``).  The ancestral ids of Autodesk's
templates (1 = AllProjectPhases, 230 = DBViewProject, ...) are documented in
``WELL_KNOWN_IDS`` for reference only -- a genesis document is free to
renumber; only the CROSS-REFERENCES (this element points at that one) matter.

Run ``python -m rvt.genesis.skeleton`` for a demonstration that builds a
minimal skeleton (2 levels, 2 phases, project info, project view + one 3D
view + one plan view), encodes every record, decodes it back and reports
the structural round-trip, and prints the six minimal Global stream models.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

# ---------------------------------------------------------------------------
# Constants derived from the corpus (Revit 2026)
# ---------------------------------------------------------------------------

#: Class names used by the skeleton; ids are resolved through the schema.
CLASS_ELEMENT_HEADER = "ElementHeader"      # 0x5e5  (seq 101)
CLASS_SERIALIZED_DUMMY = "SerializedDummy"  # 0xf2c  (seq 103, no geometry)
CLASS_GELEMENT = "GElement"                  # 0x89e  (seq 103, geometry)

#: seq-103 SerializedDummy record stamp = adler32(u16 0x0f2c) (KNOWLEDGE.md)
DUMMY_STAMP = 0x0069003C

#: BuiltInCategory ids (negative ElementIds) seen on skeleton elements
#: [VERIFIED: ElementHeader.m_categroryId of the rstbasic specimens].
BIC_LEVELS = -2000240
BIC_PHASES = -2000112
BIC_PROJECT_INFORMATION = -2003101
BIC_VIEWS = -2000279
BIC_VIEWPORTS = -2000510
BIC_CAMERAS = -2000500          # Viewer3d category
BIC_SECTION_BOX = -2000301       # ModelClipBox category
BIC_SUN_STUDY = -2009609         # SunAndShadowSettings / SunAnnotationElem
BIC_SITE = -2000111              # GeoSite
BIC_GEO_LOCATION = -2000110      # GeoLocation (site position instance)
BIC_PROJECT_BASE_POINT = -2001272
BIC_SHARED_BASE_POINT = -2001271
BIC_SHEETS = -2003100

#: BuiltInParameter ids used by the skeleton objects
#: [VERIFIED: m_paramSet keys in the rstbasic specimens].
BIP_ELEM_TYPE_PARAM = -1012201            # ELEM_FAMILY_AND_TYPE (Level -> -1)
BIP_LEVEL_IS_STRUCTURAL = -1007112        # int 1 on every corpus level [INFERRED name]
BIP_PROJECT_NAME = -1006317
BIP_PROJECT_NUMBER = -1006316
BIP_PROJECT_ADDRESS = -1006318
BIP_CLIENT_NAME = -1006319
BIP_PROJECT_STATUS = -1006320
BIP_PROJECT_ISSUE_DATE = -1006321
BIP_PROJECT_ORG_NAME = -1019005
BIP_PROJECT_ORG_DESCRIPTION = -1019006
BIP_PROJECT_BUILDING_NAME = -1019007
BIP_PROJECT_AUTHOR = -1019008
BIP_VIEW_PHASE_FILTER = -1012103          # view -> phase filter id
BIP_VIEW_PHASE = -1012102                 # view -> phase id
BIP_VIEW_DETAIL_LEVEL = -1011002          # plan view detail level (int)
BIP_VIEW_DISCIPLINE = -1005163            # plan view discipline (int) [INFERRED name]
BIP_VIEWER_BOUND_ACTIVE = -1012202        # Viewer crop param (element id -1)
BIP_LEVEL_ATTR_SYMBOL_END1 = -1008002     # level type: head at end 1 default (0) [INFERRED name]
BIP_LEVEL_ATTR_SYMBOL_END2 = -1008001     # level type: head at end 2 default (1) [INFERRED name]

#: DBViewType.m_systemFamilyIdx values = the SYSTEM VIEW-FAMILY index a view
#: family type belongs to [VERIFIED identical in rst/rac/rme 2026 templates:
#: (idx, sample type name, m_planViewDirection)].  Plan families carry a
#: plan direction (0 down / 1 up for ceiling plans); every other family -1.
VIEW_FAMILY = {
    "3d": 102,                     # '3D View'
    "walkthrough": 103,            # 'Walkthrough'
    "rendering": 104,              # 'Rendering'
    "schedule": 105,               # 'Schedule'
    "cost_report": 106,            # 'Cost Report'
    "sheet": 107,                  # 'Sheet'
    "drafting": 108,               # 'Drafting View' / 'Detail'
    "floor_plan": 109,             # 'Floor Plan'        (dir 0)
    "ceiling_plan": 111,           # 'Ceiling Plan'      (dir 1)
    "section": 112,                # 'Building Section' / 'Wall Section'
    "detail": 113,                 # 'Detail View' (callout)
    "elevation": 114,              # 'Building Elevation'
    "loads_report": 115,
    "pressure_loss_report": 116,
    "legend": 117,
    "panel_schedule": 118,         # 'Panel Schedule Report'
    "graphical_column_schedule": 119,
    "structural_plan": 120,        # 'Structural Plan'   (dir 0)
    "analysis_report": 121,
}
#: plan-direction per plan family (m_planViewDirection); others -1 [VERIFIED]
PLAN_VIEW_DIRECTION = {"floor_plan": 0, "structural_plan": 0, "ceiling_plan": 1}

#: The ancestral element ids present at EPISODE 0 (document birth) in every
#: Autodesk 2026 template -- reference only; genesis renumbers freely.
WELL_KNOWN_IDS = {
    1: "AllProjectPhases",
    2: "PenWidthTableElem",
    230: "DBViewProject (the project's implicit view; viewer 231, viewport 232, drawing 233)",
    311: "Level 'Level 1' (birth level)",
    305: "LevelAttributes (birth level type)",
    375: "PhaseFilterElem 'Show All' (default)",
    19236: "UnitsElem",
    49504: "ProjectInfo",
}

#: ElemRec owner sentinel (no owner)
NO_OWNER = 0xFFFFFFFFFFFFFFFF


# ---------------------------------------------------------------------------
# ids and episodes
# ---------------------------------------------------------------------------

class IdSource:
    """Monotonic ElementId allocator.

    Duck-compatible with ``rvt.genesis.types.IdSource`` (``next_id()``) and
    ``rvt.mutate.Document`` (``next_id()``): the skeleton's constructors
    allocate through :func:`_alloc`, which accepts any of them.  ``start``
    is the first id issued.  Autodesk's own documents allocate settings /
    style elements below ~4,096 and model content above; genesis is free to
    use one contiguous range -- only cross-references matter.
    """

    def __init__(self, start: int = 1):
        self._next = int(start)

    def next(self) -> int:
        v = self._next
        self._next += 1
        return v

    next_id = next     # alias: rvt.genesis.types.IdSource / mutate.Document API

    @property
    def watermark(self) -> int:
        """Highest id issued so far (0 if none) == ElemTable ``last_id``."""
        return self._next - 1

    last_issued = watermark


def _alloc(ids: Any) -> int:
    """Take the next id from any allocator (IdSource / types.IdSource /
    mutate.Document) -- ``.next()`` or ``.next_id()``."""
    if hasattr(ids, "next"):
        return int(ids.next())
    if hasattr(ids, "next_id"):
        return int(ids.next_id())
    raise TypeError("ids must provide next() or next_id()")


_SCHEMA_CACHE: Dict[str, Any] = {}


def class_id(name: str) -> int:
    """u16 archive class id for ``name`` from the canonical 2026 schema
    (``Formats/Latest`` -- a per-release FORMAT constant, not content).
    Cached; ``0`` if the schema is unavailable (constructors themselves
    never need it -- only encoding does)."""
    try:
        dec = _SCHEMA_CACHE.get("dec")
        if dec is None:
            from ..objects import ObjectDecoder
            dec = _SCHEMA_CACHE["dec"] = ObjectDecoder()
        cd = dec.schema.by_name.get(name)
        return cd.type_id if cd else 0
    except Exception:  # pragma: no cover - schema unavailable
        return 0


# ---------------------------------------------------------------------------
# the element record shape
# ---------------------------------------------------------------------------

@dataclass
class SkelElement:
    """One skeleton element = its seq-101/102/103 records + its ElemTable row.

    Field-for-field the same shape as ``rvt.genesis.types.TypeRecord`` and
    ``rvt.mutate.NewElement`` (elem_id, class name/id, header dict, object
    dict, rep dict) so the commit/assembly layer treats types-stream
    records, skeleton records and cloned records uniformly; adapters
    :meth:`as_type_record` / :meth:`as_new_element` bridge to both.
    """
    elem_id: int
    class_name: str                    # concrete seq-102 class ("Level", ...)
    header: dict                       # seq-101 ElementHeader object
    obj: dict                          # seq-102 element object
    rep: Optional[dict] = None         # seq-103 GElement dict; None => SerializedDummy
    owner_id: int = -1                 # ElemRec owner (view-owned satellites)
    kind: str = ""                     # human tag: 'level', 'phase', 'view', ...
    refs: dict = dc_field(default_factory=dict)   # named ids this element points at
    notes: list = dc_field(default_factory=list)

    # -- ids / classes ---------------------------------------------------------
    @property
    def class_id(self) -> int:
        """u16 archive class id (schema lookup; 0 if the schema is absent)."""
        return class_id(self.class_name)

    @property
    def rep_class_name(self) -> str:
        return CLASS_GELEMENT if self.rep is not None else CLASS_SERIALIZED_DUMMY

    @property
    def rep_class_id(self) -> int:
        return class_id(self.rep_class_name)

    @property
    def category_id(self) -> int:
        return int(self.header.get("m_categroryId", -1))

    # -- record shape ---------------------------------------------------------
    def records(self, class_ids: Optional[Callable[[str], int]] = None,
                by_name: bool = False) -> list:
        """The three ``(seq, class, object)`` records this element needs.

        Default: numeric class ids (schema), exactly like
        ``TypeRecord.records()`` / ``NewElement.records()``.  ``by_name``
        returns class NAMES instead (self-describing form for logs/tests);
        ``class_ids`` overrides the resolver (e.g. an encoder's own
        ``class_id_of``).
        """
        if by_name:
            rid = (lambda n: n)
        elif class_ids:
            rid = (lambda n: class_ids(n))
        else:
            rid = class_id
        return [
            (101, rid(CLASS_ELEMENT_HEADER), self.header),
            (102, rid(self.class_name), self.obj),
            (103, rid(self.rep_class_name), self.rep if self.rep is not None else {}),
        ]

    def as_tuple(self):
        """The (class_id, obj_dict, header_dict) contract of the types stream."""
        return (self.class_id, self.obj, self.header)

    def elemrec_row(self, episode: int = 0) -> tuple:
        """The ``Global/ElemTable`` row as ``rvt.stream_encoders`` stores it:
        ``(original_id, creation_ep, modified_ep, user_modified_ep, id,
        owner_id, partition_id)`` -- created and modified in ``episode``.
        """
        owner = self.owner_id if self.owner_id >= 0 else NO_OWNER
        return (self.elem_id, episode, episode, episode, self.elem_id, owner, 0)

    # -- adapters --------------------------------------------------------------
    def as_type_record(self):
        """-> ``rvt.genesis.types.TypeRecord`` (if the types module exists)."""
        from .types import TypeRecord  # type: ignore
        return TypeRecord(self.elem_id, self.kind, self.class_name, self.class_id,
                          self.category_id, self.obj, self.header, self.rep,
                          refs=dict(self.refs, owner_id=self.owner_id),
                          notes=list(self.notes))

    def as_new_element(self, creation_ep: int = 0):
        """-> ``rvt.mutate.NewElement`` (+ ElemRecPlan) for the commit path."""
        from ..mutate import NewElement, ElemRecPlan
        er = ElemRecPlan(elem_id=self.elem_id, original_id=self.elem_id,
                         creation_ep=creation_ep, modified_ep=creation_ep,
                         user_modified_ep=creation_ep,
                         owner_id=self.owner_id)
        return NewElement(self.elem_id, self.kind, self.class_name, self.class_id,
                          self.header, self.obj, self.rep, er, template_id=-1,
                          notes=list(self.notes))

    def roundtrip(self) -> dict:
        """Encode each record then decode it back (schema validity proof)."""
        from ..encode import ObjectEncoder
        dec = _SCHEMA_CACHE.get("dec")
        if dec is None:
            from ..objects import ObjectDecoder
            dec = _SCHEMA_CACHE["dec"] = ObjectDecoder()
        enc = _SCHEMA_CACHE.get("enc")
        if enc is None:
            enc = _SCHEMA_CACHE["enc"] = ObjectEncoder(decoder=dec)
        rep = {}
        for seq, cid, obj in self.records():
            body = enc.encode_object(cid, obj or {})
            got = dec.decode_record(cid, body)
            body2 = enc.encode_object(cid, got.value) if got.clean else b""
            rep[seq] = {"class": dec.class_name(cid), "bytes": len(body),
                        "clean": bool(got.clean), "byte_exact": body == body2,
                        "value_equal": bool(got.clean) and got.value == obj,
                        "errors": got.errors}
        rep["ok"] = all(r["clean"] and r["byte_exact"] for k, r in rep.items()
                        if k != "ok")
        return rep

    def to_json(self) -> dict:
        return {"elem_id": self.elem_id, "class": self.class_name,
                "kind": self.kind, "owner_id": self.owner_id, "refs": self.refs,
                "seq101_ElementHeader": self.header, "seq102_object": self.obj,
                "seq103": ({"class": CLASS_GELEMENT, "value": self.rep}
                           if self.rep is not None else
                           {"class": CLASS_SERIALIZED_DUMMY, "stamp": f"{DUMMY_STAMP:#010x}"}),
                "notes": self.notes}


# ---------------------------------------------------------------------------
# common building blocks (seq-101 header, seq-102 Element base)
# ---------------------------------------------------------------------------

def _ptr(cls: str, value: dict, pid: int = -1) -> dict:
    """An owned-pointer token in the decoder's dict shape."""
    return {"ptr_class": cls, "pid": pid, "value": value}


def _weak(pid: int) -> dict:
    """A weak-pointer token (archive object index; 1 = ADocument, 2 = self)."""
    return {"weakref": pid}


def element_parents(*, deletion: Iterable[int], regen_only: Iterable[int] = (),
                    appearance: Iterable[int] = (),
                    dependency: Iterable[int] = (),
                    nondeterm_children: Iterable[int] = ()) -> dict:
    """The ``ElementParents`` sub-object of a seq-101 header.

    ``deletion`` = elements whose deletion cascades onto this one (always
    includes the element itself); ``regen_only`` / ``appearance`` /
    ``dependency`` = regeneration edges [semantics INFERRED from specimens].
    """
    ndc = sorted(set(int(x) for x in nondeterm_children))
    return _ptr("ElementParents", {
        "m_deletion": sorted(set(int(x) for x in deletion)),
        "m_regenOnly": sorted(set(int(x) for x in regen_only)),
        "m_regenWildcards": [], "m_nonDetermRegenChildren": ndc,
        "m_dependencyParents": sorted(set(int(x) for x in dependency)),
        "m_appearanceParents": sorted(set(int(x) for x in appearance)),
        "m_deferredParents": [], "m_deferredPropagationParents": [],
        "m_computedParametersParents": [],
        "m_hasNonDetermRegenChildren": bool(ndc),
    })


def element_header(class_name: str, *, category: int = -1,
                   deletion: Iterable[int], regen_only: Iterable[int] = (),
                   appearance: Iterable[int] = (), dependency: Iterable[int] = (),
                   nondeterm_children: Iterable[int] = (),
                   flags: int = 10, visible_view_flags: int = -32768,
                   family_id: int = -1, owner_view: int = -1,
                   design_option: int = -1, unplaced_owner: int = -1,
                   misc_id: int = -1, bbox: Optional[Tuple[Sequence[float], Sequence[float]]] = None
                   ) -> dict:
    """A complete seq-101 ``ElementHeader`` object [layout VERIFIED byte-exact].

    ``flags`` = ``m_abFlags4Bytes`` and ``visible_view_flags`` =
    ``m_viewRules.m_nVisibleViewFlags``: per-class constants copied from the
    specimens (their bit semantics are UNKNOWN; both a "birth" value with bit
    0x800 and a "user-created" value 10 exist in the corpus and both open).
    """
    return {
        "m_regenHistory": {"m_historyMap": []},
        "m_categroryId": int(category),          # NB: Revit's own field typo
        "m_familyId": int(family_id),
        "m_ownerViewId": int(owner_view),
        "m_designOptionId": int(design_option),
        "m_unplacedOwnerId": int(unplaced_owner),
        "m_miscId": int(misc_id),
        "m_viewRules": {"m_nVisibleViewFlags": int(visible_view_flags)},
        "m_abFlags4Bytes": int(flags),
        "m_classDef": {"m_ref": {"classref": class_name}},
        "m_pBBox": (_ptr("Outline", {"m_minmax": [list(map(float, bbox[0])),
                                                 list(map(float, bbox[1]))]})
                    if bbox is not None else None),
        "m_parents": element_parents(deletion=deletion, regen_only=regen_only,
                                     appearance=appearance, dependency=dependency,
                                     nondeterm_children=nondeterm_children),
    }


def element_base(elem_id: int, *, cell_list: bool = False,
                 owner_view: int = -1, design_option: int = -1,
                 created_phase: int = -1) -> dict:
    """The 20 fields of the universal ``Element`` base (parent-first order).

    ``cell_list`` -- most settings/type elements carry an empty
    ``CellList{PatternHelper}``; a few (AllProjectPhases, ProjectInfo,
    GeoLocation, ...) carry ``None`` [VERIFIED per class].
    """
    return {
        "m_pParamValueSetDouble": None,
        "m_pParamValueSetInt": None,
        "m_pParamValueSetAString": None,
        "m_pParamValueSetElementId": None,
        "m_geomSteps": None,
        "m_pGeomTable": None,
        "m_constrInfo": [],
        "m_cellList": (_ptr("CellList", {"m_cells": [
            _ptr("PatternHelper", {"m_PatternPositionMap": [],
                                    "m_substituteFaceMap": []})]})
                       if cell_list else None),
        "m_docAccess": {"m_pDoc": _weak(1)},
        "m_id": int(elem_id),
        "m_assocLevelId": -1,
        "m_famId": -1,
        "m_unplacedOwnerId": -1,
        "m_ownerDBViewId": int(owner_view),
        "m_createdPhaseId": int(created_phase),
        "m_demolishedPhaseId": -1,
        "m_designOptionId": int(design_option),
        "m_locked": False,
        "m_moribund": False,
        "m_dummy": False,
    }


def symbol_base(elem_id: int, name: str, **kw) -> dict:
    """``Symbol`` = Element base + SymbolInfo name + render/preview ids
    (type/annotation-type/view-type elements) [VERIFIED]."""
    d = element_base(elem_id, **kw)
    d["m_symbolInfo"] = _ptr("SymbolInfo", {"m_name": str(name)})
    d["m_renderStyleId"] = -1
    d["m_previewElemId"] = -1
    return d


def param_set_int(pairs: Sequence[Tuple[int, int]]) -> dict:
    return _ptr("ParamValueSetInt", {"m_paramSet": [
        {"m_paramId": int(p), "m_value": int(v)} for p, v in pairs]})


def param_set_elemid(pairs: Sequence[Tuple[int, int]]) -> dict:
    return _ptr("ParamValueSetElementId", {"m_paramSet": [
        {"m_paramId": int(p), "m_value": int(v)} for p, v in pairs]})


def param_set_astring(pairs: Sequence[Tuple[int, str]]) -> dict:
    return _ptr("ParamValueSetAString", {"m_paramSet": [
        {"m_paramId": int(p), "m_value": v} for p, v in pairs]})


def param_set_double(pairs: Sequence[Tuple[int, float]]) -> dict:
    return _ptr("ParamValueSetDouble", {"m_paramSet": [
        {"m_paramId": int(p), "m_value": float(v)} for p, v in pairs]})


def plane(origin: Sequence[float], xvec: Sequence[float], yvec: Sequence[float],
          envelope: Sequence[Sequence[float]] = ((1.0, 1.0), (0.0, 0.0)),
          pid: int = -1) -> dict:
    """A ``Plane`` (Surface) object.  ``envelope`` = the 2-corner UV extent
    of the plane's drawn envelope; ``((1,1),(0,0))`` is Revit's EMPTY
    envelope (min > max) used by cutters [VERIFIED]."""
    return {"ptr_class": "Plane", "pid": pid, "value": {
        "m_Envelope": {"m_corners": [list(map(float, envelope[0])),
                                     list(map(float, envelope[1]))]},
        "m_orientFlag": True,
        "m_origin": list(map(float, origin)),
        "m_xVec": list(map(float, xvec)),
        "m_yVec": list(map(float, yvec))}}


EMPTY_ENVELOPE = ((1.0, 1.0), (0.0, 0.0))


# ---------------------------------------------------------------------------
# LEVELS
# ---------------------------------------------------------------------------

def _datum_plane_geom_steps() -> dict:
    """The GeomStepList of a datum (Level): one DatumPlaneGeomStep whose face
    history keys the level plane face [VERIFIED byte-exact on rstbasic 311]."""
    return _ptr("GeomStepList", {
        "m_nonBRepGList": [_ptr("DatumPlaneGeomStep", {
            "m_faceHistTable": [{"m_id": 0, "m_faceHist": {"m_keys": [6, 0, -1]}}],
            "m_curveHistTableSet": [], "m_edgeHistTable": [],
            "m_edgeHistTableReverse": [],
            "m_id": 1, "m_version": 0, "m_flags": 1,
            "m_pElem": _weak(2), "m_oExtraDatas": None})],
        "m_bRepFormGList": [], "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [], "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [1, 1, 1, 1, 1],
        "m_idCounter": 2, "m_flags": 1})


def new_level(elem_id: int, name: str, elevation_ft: float, level_type_id: int, *,
              extent_ft: Tuple[Tuple[float, float], Tuple[float, float]] = (
                  (-50.0, -50.0), (50.0, 50.0)),
              units_id: int = -1, geolocation_id: int = -1,
              datum_length_ft: float = 30.0,
              is_building_story: bool = False,
              flags: int = 10) -> SkelElement:
    """A ``Level`` datum (class 0x9e7) at ``elevation_ft`` (feet, model Z).

    Structure [VERIFIED byte-exact vs rstbasic 311]:  the elevation is the
    Z of the level's inline datum plane (``m_pSurface`` and the identical
    plane inside ``m_pFace``); the datum LINE runs from ``m_freeEnd`` to
    ``m_bubbleEnd`` (``datum_length_ft`` long, drawn at the level elevation
    for a genesis level [INFERRED]).  ``extent_ft`` = the plane envelope
    corners (the datum's model extent).  ``level_type_id`` = the
    ``LevelAttributes`` element; ``units_id``/``geolocation_id`` are the
    regen edges every corpus level carries (UnitsElem, project GeoLocation).
    seq-103 rep = SerializedDummy (levels carry no cached geometry) [VERIFIED].
    """
    z = float(elevation_ft)
    o = element_base(elem_id, cell_list=True)
    o["m_pParamValueSetInt"] = param_set_int([(BIP_LEVEL_IS_STRUCTURAL, 1)])
    o["m_pParamValueSetElementId"] = param_set_elemid([(BIP_ELEM_TYPE_PARAM, -1)])
    o["m_geomSteps"] = _datum_plane_geom_steps()
    o["m_pGeomTable"] = _ptr("GeomTable", {
        "m_refPntMirrored": False, "m_table": [{"m_geomGeneratorId": 1}],
        "m_bigTableOwner": None, "m_materialMarkers": [], "m_faceTypeMarkers": []})
    origin = (0.0, 0.0, z)
    xvec, yvec = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    o["m_text"] = str(name)
    # NB: pointer archive indices: 1 = ADocument, 2 = this element, 3.. in
    # token order (Face token first, then m_pSurface, then Face's deferred
    # m_pSurf) [VERIFIED on the specimen: 3 / 4 / 5].
    o["m_pFace"] = _ptr("Face", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                    "m_flags": 524804},
        "m_pFirstLoop": None, "m_faceRegions": [], "m_pGFilling": None,
        "m_oBackgroundFilling": None, "m_renderStyleId": -1, "m_cutType": 0,
        "m_faceFlags_v9": 0,
        "m_pSurf": plane(origin, xvec, yvec, extent_ft, pid=5)}, pid=3)
    o["m_pSurface"] = plane(origin, xvec, yvec, extent_ft, pid=4)
    o["m_pLeader"] = None
    o["m_freeEnd"] = [0.0, 0.0, z]
    o["m_bubbleEnd"] = [float(datum_length_ft), 0.0, z]
    o["m_cutVec"] = [0.0, 1.0, 0.0]
    o["m_refPointsForNewViews"] = [[0.0, 0.0, z], [float(datum_length_ft), 0.0, z]]
    o["m_sheetTextHeight"] = 0.015624999999999998      # 3/16 in on sheet [VERIFIED value]
    o["m_genDbViewId"] = -1
    o["m_v2Datum"] = False
    o["m_useConstVForDatumLine3dRep"] = True
    o["m_roomComputationElevationOffset"] = 0.0
    o["m_attrId"] = int(level_type_id)
    o["m_isBuildingStory"] = bool(is_building_story)

    regen = [x for x in (units_id, geolocation_id) if x is not None and x >= 0]
    appear = [x for x in (level_type_id, units_id) if x is not None and x >= 0]
    hdr = element_header("Level", category=BIC_LEVELS,
                         deletion=[level_type_id, elem_id],
                         regen_only=regen, appearance=appear,
                         flags=flags, visible_view_flags=-4225)
    return SkelElement(elem_id, "Level", hdr, o, None, kind="level",
                       notes=["seq103=SerializedDummy; elevation = plane origin Z"])


def new_level_type(elem_id: int, name: str = "Level Head", *,
                   line_category_id: int = -1, leader_category_id: int = -1,
                   font_id: int = -1, head_family_symbol_id: int = -1,
                   base_elevation: int = 0,
                   room_computation_height_ft: float = 4.0) -> SkelElement:
    """A ``LevelAttributes`` (level TYPE, class 0x9e8).

    [VERIFIED structure vs rstbasic 305 '8mm Head'].  References (all
    optional here, ``-1``): the level line sub-``CategoryElem`` (object-
    styles registry), a leader ``CategoryElem``, a ``FontElem``, and the
    level-head annotation ``FamilySymbol`` (``m_familyTagId``) -- an
    Autodesk-content family in every sample, deliberately UNSET for genesis
    (``-1`` == parameter 'Symbol: <none>' [UNKNOWN whether -1 renders; a
    level head is cosmetic]).  ``base_elevation``: 0 = Project Base Point,
    1 = Survey Point.
    """
    o = symbol_base(elem_id, name, cell_list=False)
    # level-type params: symbol-at-end-1 default (0=off) / end-2 default
    # (1=on) [VERIFIED values vs rstbasic 305; parameter identity INFERRED]
    o["m_pParamValueSetInt"] = param_set_int([(BIP_LEVEL_ATTR_SYMBOL_END1, 0),
                                              (BIP_LEVEL_ATTR_SYMBOL_END2, 1)])
    o["m_lineAndTextAttr"] = {"m_fontId": int(font_id),
                              "m_categoryId": int(line_category_id),
                              "m_background": 0, "m_bBold": False,
                              "m_bItalic": False, "m_bUnderline": False}
    o["m_roomComputationUserHeight"] = float(room_computation_height_ft)
    o["m_leaderCategoryId"] = int(leader_category_id)
    o["m_familyTagId"] = int(head_family_symbol_id)
    o["m_baseElevation"] = int(base_elevation)
    o["m_bRoomComputationHeightAutomatic"] = False
    dele = [elem_id] + [x for x in (line_category_id, leader_category_id, font_id,
                                    head_family_symbol_id) if x >= 0]
    hdr = element_header("LevelAttributes", category=BIC_LEVELS, deletion=dele,
                         flags=30, visible_view_flags=-32768)
    return SkelElement(elem_id, "LevelAttributes", hdr, o, None, kind="level_type")


# ---------------------------------------------------------------------------
# PHASES
# ---------------------------------------------------------------------------

def new_phase(elem_id: int, name: str, description: str = "", *,
              all_phases_id: int = 1) -> SkelElement:
    """A ``ProjectPhase`` (class 0xd17).  Ordering lives in
    ``AllProjectPhases.m_phaseIds`` (see :func:`new_all_project_phases`).
    [VERIFIED byte-exact vs rstbasic 12589 'Existing']."""
    o = element_base(elem_id, cell_list=True)
    o["m_name"] = str(name)
    o["m_description"] = str(description)
    hdr = element_header("ProjectPhase", category=BIC_PHASES,
                         deletion=[elem_id], regen_only=[all_phases_id],
                         flags=2078, visible_view_flags=-32768)
    return SkelElement(elem_id, "ProjectPhase", hdr, o, None, kind="phase")


def override_graphic_settings(*, detail_level: int = 0, halftone: bool = False,
                              proj_pen: int = 1, cut_pen: int = 3,
                              proj_line_pattern: int = -1, cut_line_pattern: int = -1,
                              proj_pen_color: int = 0, cut_pen_color: int = 0,
                              proj_fill_pattern: int = -1, cut_fill_pattern: int = -1,
                              proj_fill_color: int = 16777216, cut_fill_color: int = 16777216,
                              cut_fill_visible: bool = True,
                              transparency: int = 0) -> dict:
    """An ``OverrideGraphicSettings`` object (used by phasing overrides).

    Pattern / line-pattern ids reference the FillPatternElem /
    LinePatternElem registries (``-1`` = solid/none); colors are 0x00BBGGRR
    ints; 16777216 (0x1000000) = "no color override" [INFERRED].
    """
    def pen(n): return _ptr("GPenNumberOverrider", {"m_penNumber": int(n)})
    def lpat(i): return _ptr("GLinePatternOverrider", {"m_linePatternId": int(i)})
    def scol(c): return _ptr("GStyleColorOverrider", {"m_color": int(c)})
    def fpat(i, fg): return _ptr("GFillPatternOverrider", {"m_fillPatternId": int(i),
                                                            "m_isForeground": bool(fg)})
    def fcol(c, fg): return _ptr("GFillColorOverrider", {"m_color": int(c),
                                                          "m_isForeground": bool(fg)})
    return _ptr("OverrideGraphicSettings", {
        "m_detailLevel": int(detail_level), "m_bHalftone": bool(halftone),
        "m_bProjFillPatternVisible": True,
        "m_bSurfaceBackgroundFillPatternVisible": True,
        "m_bCutFillPatternVisible": bool(cut_fill_visible),
        "m_bCutBackgroundFillPatternVisible": True,
        "m_oProjPenNumber": pen(proj_pen), "m_oCutPenNumber": pen(cut_pen),
        "m_oProjLinePattern": lpat(proj_line_pattern),
        "m_oCutLinePattern": lpat(cut_line_pattern),
        "m_oProjPenColor": scol(proj_pen_color), "m_oCutPenColor": scol(cut_pen_color),
        "m_oProjFillPattern": fpat(proj_fill_pattern, True),
        "m_oSurfaceBackgroundPatternIdOverrider": fpat(-1, False),
        "m_oCutFillPattern": fpat(cut_fill_pattern, True),
        "m_oCutBackgroundPatternIdOverrider": fpat(-1, False),
        "m_oProjFillColor": fcol(proj_fill_color, True),
        "m_oSurfaceBackgroundPatternColorOverrider": fcol(16777216, False),
        "m_oCutFillColor": fcol(cut_fill_color, True),
        "m_oCutBackgroundPatternColorOverrider": fcol(16777216, False),
        "m_oSurfacesTransparency": _ptr("GSurfacesTransparencyOverrider",
                                        {"m_transparency": int(transparency)}),
    })


#: The four phase-status graphic overrides every corpus AllProjectPhases
#: carries (m_elementOnPhaseStatus 2..5 = Existing / Demolished / New /
#: Temporary) with the sample's default pens and NO material/pattern
#: dependencies (genesis leaves material -1 so the phase set does not depend
#: on the material registry) [INFERRED: Revit's default phase graphics].
def default_phasing_overrides(materials: Optional[Sequence[int]] = None,
                              line_patterns: Optional[Sequence[int]] = None,
                              fill_patterns: Optional[Sequence[int]] = None) -> list:
    """The ``m_arrPhasingOverrides`` array of ``AllProjectPhases``.

    Optional registry ids (in phase-status order Existing, Demolished, New,
    Temporary): ``materials`` (Phase - Exist / Phase - Demo / Phase - New /
    Phase - Temporary style materials), ``line_patterns`` (demolished
    'Demolished' dash pattern), ``fill_patterns`` (existing/temporary cut
    patterns).  All default to ``-1`` (no dependency) [UNKNOWN whether Revit
    tolerates -1 materials here; every corpus file references real materials].
    """
    mats = list(materials) if materials else [-1, -1, -1, -1]
    lps = list(line_patterns) if line_patterns else [-1, -1, -1, -1]
    fps = list(fill_patterns) if fill_patterns else [-1, -1, -1, -1]
    specs = [
        # status, proj_pen, cut_pen, cut_fill_visible, pen colors, ..., cut fill color
        (2, 2, 3, True, 8355711, 8355711, mats[0], lps[0], fps[0], 8355711),    # Existing (grey)
        (3, 1, 3, False, 0, 0, mats[1], lps[1], fps[1], 16777216),            # Demolished
        (4, 4, 5, True, 0, 0, mats[2], lps[2], fps[2], 0),                      # New
        (5, 1, 3, True, 8323072, 8323072, mats[3], lps[3], fps[3], 8323072),   # Temporary
    ]
    out = []
    for status, ppen, cpen, cutvis, pcol, ccol, mat, lp, fp, cutfill in specs:
        out.append(_ptr("PhasingOverrides", {
            "m_elementOnPhaseStatus": status,
            "m_oOverrideGraphicSettings": override_graphic_settings(
                proj_pen=ppen, cut_pen=cpen, cut_fill_visible=cutvis,
                proj_pen_color=pcol, cut_pen_color=ccol,
                proj_line_pattern=lp, cut_line_pattern=lp,
                cut_fill_pattern=fp, cut_fill_color=cutfill),
            "m_oGMaterialOverrider": _ptr("GMaterialOverrider",
                                          {"m_materialId": int(mat)}),
        }))
    return out


def new_all_project_phases(elem_id: int, phase_ids: Sequence[int], *,
                           phasing_overrides: Optional[list] = None) -> SkelElement:
    """The singleton ``AllProjectPhases`` (class 0xcc) holding the ordered
    phase list [VERIFIED structure vs rstbasic id 1; ancestral id 1 in every
    template].  ``phasing_overrides`` defaults to
    :func:`default_phasing_overrides` (no material/pattern dependencies)."""
    o = element_base(elem_id, cell_list=False)
    o["m_phaseIds"] = [int(p) for p in phase_ids]
    o["m_arrPhasingOverrides"] = (phasing_overrides if phasing_overrides is not None
                                 else default_phasing_overrides())
    # deletion parents = self + phases + every registry id the overrides use
    refs = set(int(p) for p in phase_ids)
    for po in o["m_arrPhasingOverrides"]:
        v = po.get("value") or {}
        mid = ((v.get("m_oGMaterialOverrider") or {}).get("value") or {}).get("m_materialId", -1)
        if mid is not None and mid >= 0:
            refs.add(mid)
        og = ((v.get("m_oOverrideGraphicSettings") or {}).get("value") or {})
        for k in ("m_oProjLinePattern", "m_oCutLinePattern"):
            lid = ((og.get(k) or {}).get("value") or {}).get("m_linePatternId", -1)
            if isinstance(lid, int) and lid >= 0:
                refs.add(lid)
        for k in ("m_oProjFillPattern", "m_oCutFillPattern"):
            fid = ((og.get(k) or {}).get("value") or {}).get("m_fillPatternId", -1)
            if isinstance(fid, int) and fid >= 0:
                refs.add(fid)
    hdr = element_header("AllProjectPhases", category=-1,
                         deletion=[elem_id] + sorted(refs),
                         flags=8222, visible_view_flags=-32768)
    return SkelElement(elem_id, "AllProjectPhases", hdr, o, None, kind="phase_set")


#: The five product-default phase filters (names + 7-slot presentation
#: vectors) present at episode 0 in every corpus template [VERIFIED 3/3;
#: presentation semantics per slot INFERRED: 0 = by-category, 1 =
#: overridden, 2 = not-displayed for status slots (?,?,New?,Existing?,
#: Demolished?,Temporary?,?)].
DEFAULT_PHASE_FILTERS: List[Tuple[str, bool, List[int]]] = [
    ("Show Previous Phase", False, [0, 0, 2, 0, 0, 0, 0]),
    ("Show Previous + New", False, [0, 0, 2, 0, 1, 0, 0]),
    ("Show Previous + Demo", False, [0, 0, 2, 2, 0, 0, 0]),
    ("Show Demo + New", False, [0, 0, 0, 2, 1, 2, 0]),
    ("Show All", True, [0, 0, 2, 2, 1, 2, 0]),
]


def new_phase_filter(elem_id: int, name: str, presentation: Sequence[int],
                     is_default: bool = False, *,
                     regen_only: Sequence[int] = ()) -> SkelElement:
    """A ``PhaseFilterElem`` (class 0xca7) [VERIFIED byte-exact vs rstbasic
    371..375 objects].  ``regen_only`` = the header regen edges (the corpus
    filters list the AllProjectPhases element and the pattern/material the
    phasing overrides use)."""
    o = element_base(elem_id, cell_list=True)
    o["m_name"] = str(name)
    o["m_bDefault"] = bool(is_default)
    o["m_phaseStatusPresentation"] = [int(x) for x in presentation]
    hdr = element_header("PhaseFilterElem", category=-1, deletion=[elem_id],
                         regen_only=regen_only, flags=2078, visible_view_flags=-32768)
    return SkelElement(elem_id, "PhaseFilterElem", hdr, o, None, kind="phase_filter")


def default_phase_filters(ids: IdSource, all_phases_id: int = -1) -> List[SkelElement]:
    """The five standard phase filters (one flagged default 'Show All')."""
    regen = [all_phases_id] if all_phases_id >= 0 else []
    return [new_phase_filter(_alloc(ids), n, p, d, regen_only=regen)
            for n, d, p in DEFAULT_PHASE_FILTERS]


# ---------------------------------------------------------------------------
# PROJECT INFORMATION
# ---------------------------------------------------------------------------

def new_project_info(elem_id: int, *, project_name: str = "", project_number: str = "",
                     address: str = "", client_name: str = "",
                     project_status: str = "", issue_date: str = "",
                     organization_name: str = "", organization_description: str = "",
                     building_name: str = "", author: str = "") -> SkelElement:
    """The singleton ``ProjectInfo`` (class 0xd13) -- the identity WE set from
    the job spec [VERIFIED byte-exact vs rstbasic 49504].  All ten built-in
    project parameters are AString parameters on the element."""
    o = element_base(elem_id, cell_list=False)
    o["m_pParamValueSetAString"] = param_set_astring([
        (BIP_PROJECT_AUTHOR, author),
        (BIP_PROJECT_BUILDING_NAME, building_name),
        (BIP_PROJECT_ORG_DESCRIPTION, organization_description),
        (BIP_PROJECT_ORG_NAME, organization_name),
        (BIP_PROJECT_ISSUE_DATE, issue_date),
        (BIP_PROJECT_STATUS, project_status),
        (BIP_CLIENT_NAME, client_name),
        (BIP_PROJECT_ADDRESS, address),
        (BIP_PROJECT_NAME, project_name),
        (BIP_PROJECT_NUMBER, project_number),
    ])
    hdr = element_header("ProjectInfo", category=BIC_PROJECT_INFORMATION,
                         deletion=[elem_id], flags=8222, visible_view_flags=-32768)
    return SkelElement(elem_id, "ProjectInfo", hdr, o, None, kind="project_info")


# ---------------------------------------------------------------------------
# UNITS registry (mandatory registry -- Level/every dimension references it)
# ---------------------------------------------------------------------------

#: (spec typeId, unit typeId, symbol typeId or None, accuracy, use_default)
#: A DEFAULT format-options table.  The Forge/Autodesk unit schema
#: identifiers ('autodesk.spec.*', 'autodesk.unit.*') are the openly
#: published measurable-spec ids Revit 2026 keys its unit settings by.  This
#: is a MINIMAL common-length/angle/electrical set; a full table has ~136
#: entries (see docs/writer/genesis-skeleton.md, registry section)
#: [INFERRED: entries a document does not carry fall back to defaults].
DEFAULT_UNIT_FORMATS: List[Tuple[str, str, Optional[str], float]] = [
    ("autodesk.spec.aec:length-2.0.0", "autodesk.unit.unit:feetFractionalInches-1.0.0", None, 0.00520833333333333),
    ("autodesk.spec.aec:area-2.0.0", "autodesk.unit.unit:squareFeet-1.0.1", "autodesk.unit.symbol:sf-1.0.1", 0.01),
    ("autodesk.spec.aec:volume-2.0.0", "autodesk.unit.unit:cubicFeet-1.0.1", "autodesk.unit.symbol:cf-1.0.1", 0.01),
    ("autodesk.spec.aec:angle-2.0.0", "autodesk.unit.unit:degrees-1.0.1", "autodesk.unit.symbol:degreeSymbol-1.0.1", 0.01),
    ("autodesk.spec.aec:number-2.0.0", "autodesk.unit.unit:general-1.0.1", None, 0.000001),
    ("autodesk.spec.aec.electrical:apparentPower-1.0.0", "autodesk.unit.unit:voltAmperes-1.0.1", "autodesk.unit.symbol:vA-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:current-2.0.0", "autodesk.unit.unit:amperes-1.0.1", "autodesk.unit.symbol:ampere-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:potential-2.0.0", "autodesk.unit.unit:volts-1.0.1", "autodesk.unit.symbol:volt-1.0.1", 1.0),
]


def format_options(spec_type_id: str, unit_type_id: str,
                   symbol_type_id: Optional[str], accuracy: float, *,
                   use_default: bool = False, use_grouping: bool = False,
                   rounding_method: int = 0) -> dict:
    """One ``m_formatOptionsMap`` entry: spec typeId -> FormatOptions
    [VERIFIED structure vs rstbasic UnitsElem 19236 (136 entries)]."""
    return {
        "first": {"m_typeId": spec_type_id},
        "second": {
            "m_symbolTypeId": {"m_typeId": symbol_type_id or ""},
            "m_unitTypeId": {"m_typeId": unit_type_id},
            "m_accuracy": float(accuracy),
            "m_roundingMethod": int(rounding_method),
            "m_bSuppressLeadingZeros": False, "m_bSuppressSpaces": False,
            "m_bSuppressTrailingZeros": False,
            "m_bUseDefault": bool(use_default),
            "m_bUseGrouping": bool(use_grouping),
            "m_bUsePlusPrefix": False,
        }}


def new_units_elem(elem_id: int, formats: Optional[Sequence] = None, *,
                   universal_unit_system: int = 1, decimal_symbol: int = 0,
                   digit_grouping_symbol: int = 1,
                   digit_grouping_amount: int = 1) -> SkelElement:
    """The singleton ``UnitsElem`` (class 0x111e): the document's per-spec
    display-unit settings.  ``formats`` = iterable of
    ``(spec, unit, symbol_or_None, accuracy)`` (default: a small imperial
    set); ``universal_unit_system`` 0 = metric, 1 = imperial [INFERRED].
    Every level (and every dimensioned element) lists UnitsElem as a regen
    parent, so it is a mandatory registry singleton [VERIFIED reference]."""
    fmts = list(formats) if formats is not None else DEFAULT_UNIT_FORMATS
    o = element_base(elem_id, cell_list=True)
    o["m_units"] = {
        "m_formatOptionsMap": [format_options(*f[:4]) for f in fmts],
        "m_universalUnitSystem": int(universal_unit_system),
        "m_decimalSymbol": int(decimal_symbol),
        "m_digitGroupingSymbol": int(digit_grouping_symbol),
        "m_digitGroupingAmount": int(digit_grouping_amount),
    }
    hdr = element_header("UnitsElem", category=-1, deletion=[elem_id],
                         flags=8222, visible_view_flags=-32768)
    return SkelElement(elem_id, "UnitsElem", hdr, o, None, kind="registry")


# ---------------------------------------------------------------------------
# SITE / COORDINATES  (optional skeleton pieces every template carries)
# ---------------------------------------------------------------------------

def new_true_north(elem_id: int, angle_rad: float = 0.0, *,
                   site_cut_material_id: int = -1) -> SkelElement:
    """``TrueNorth`` singleton (class 0x1108): rotation from project north
    to true north [VERIFIED vs rstbasic 7850].  ``site_cut_material_id`` =
    the topo cut material (registry ref; -1 = none)."""
    o = element_base(elem_id, cell_list=True)
    o["m_angle"] = float(angle_rad)
    o["m_pocheDepth"] = -9.842519685039369          # -3 m poche depth (product default)
    o["m_siteCutMaterialId"] = int(site_cut_material_id)
    o["m_propertyBearingMethod"] = 1
    o["m_propertyBearingUnits"] = 1
    dele = [elem_id] + ([site_cut_material_id] if site_cut_material_id >= 0 else [])
    hdr = element_header("TrueNorth", category=-1, deletion=dele,
                         flags=2078, visible_view_flags=-32768)
    return SkelElement(elem_id, "TrueNorth", hdr, o, None, kind="site")


def new_base_point(elem_id: int, shared: bool = False,
                   coord_ft: Sequence[float] = (0.0, 0.0, 0.0), *,
                   geolocation_id: int = -1, tracking_id: int = -1) -> SkelElement:
    """A ``BasePoint`` (class 0x23e): ``shared=False`` = the Project Base
    Point (category -2001272), ``shared=True`` = the Survey Point
    (category -2001271).  Both exist in every template [VERIFIED].  Its seq-103
    rep is a real GElement (a GPoint marker) rather than SerializedDummy
    [VERIFIED]; the rep is rebuilt here from ``coord_ft``.
    """
    x, y, z = (float(c) for c in coord_ft)
    o = element_base(elem_id, cell_list=True)
    # a coordinate element carries a curve-history geom step + geom table
    # [VERIFIED vs rstbasic 111429]
    o["m_geomSteps"] = _ptr("GeomStepList", {
        "m_nonBRepGList": [_ptr("CoordinateElemBaseGeomStep", {
            "m_faceHistTable": [],
            "m_curveHistTableSet": [{"m_id": 0, "m_curveHist": {"m_keys": [2, 0, -1, -1, -1]}}],
            "m_edgeHistTable": [], "m_edgeHistTableReverse": [],
            "m_id": 1, "m_version": 0, "m_flags": 761725,
            "m_pElem": _weak(2), "m_oExtraDatas": None})],
        "m_bRepFormGList": [], "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [], "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [1, 1, 1, 1, 1],
        "m_idCounter": 2, "m_flags": 11})
    o["m_pGeomTable"] = _ptr("GeomTable", {
        "m_refPntMirrored": False, "m_table": [{"m_geomGeneratorId": 1}],
        "m_bigTableOwner": None, "m_materialMarkers": [], "m_faceTypeMarkers": []})
    o["m_oGPoint"] = _ptr("GPoint", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                    "m_flags": 524292},
        "m_coord": [x, y, z], "m_size": 6, "m_borderSize": 2,
        "m_pointFlags": 0}, pid=3)
    o["m_transformedPosition"] = [0.0, 0.0, 0.0] if shared else [x, y, -0.0 if z == 0 else z]
    o["m_locationType"] = 0 if shared else 1
    o["m_isClippedToShared"] = True
    regen = [g for g in (geolocation_id, tracking_id) if g >= 0]
    hdr = element_header("BasePoint",
                         category=BIC_SHARED_BASE_POINT if shared else BIC_PROJECT_BASE_POINT,
                         deletion=[elem_id], regen_only=regen,
                         flags=6186, visible_view_flags=-4225,
                         bbox=((x, y, z), (x, y, z)))
    # seq-103: a real GElement (point marker + its bitmap glyph) rather
    # than SerializedDummy [VERIFIED vs rstbasic 111426]; m_GInfo's
    # categoryId 105717 in the corpus is a category-element id (registry) --
    # -1 here.
    rep = {
        "m_GInfo": {"m_categoryId": -1, "m_tag": int(elem_id),
                    "m_controlCommand": 0, "m_flags": 557060},
        "m_subNodes": [
            _ptr("GPoint", {"m_GInfo": {"m_categoryId": -1, "m_tag": 0,
                                         "m_controlCommand": 0, "m_flags": 557828},
                             "m_coord": [x, y, z], "m_size": 1,
                             "m_borderSize": 2, "m_pointFlags": -2147483648}, pid=3),
            _ptr("GBitmap", {"m_GInfo": {"m_categoryId": -1, "m_tag": -1,
                                          "m_controlCommand": 0, "m_flags": 557572},
                              "m_point": [x, y, z], "m_size": [24, 24],
                              "m_bitmapType": 79, "m_alignment": 0}, pid=4),
        ],
        "m_bBox": [[x, y, z], [x, y, z]],
        "m_tightbBox": [[x, y, z], [x, y, z]],
        "m_elementId": int(elem_id),
        "m_gElemType": 2,
        "m_flags": 0,
    }
    return SkelElement(elem_id, "BasePoint", hdr, o, rep, kind="site",
                       notes=["seq103 rep = GElement point marker (bitmapType 79 = base-point glyph)"])


def our_guid(purpose: str, *parts: Any) -> str:
    """A DETERMINISTIC GUID in OUR namespace: uuid5 under
    ``rvt-writer.gen.<purpose>`` over ``parts``.  Same inputs, same GUID (two
    builds of one intent are byte-identical); distinct inputs differ; no
    donor GUID is ever the material (residue_b._stable_guid is the
    'house-standard' instance of the same derivation)."""
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, f"rvt-writer.gen.{purpose}")
    return str(uuid.uuid5(ns, "|".join(str(p) for p in parts)))


def new_geo_site(elem_id: int, name: str = "", *, latitude_rad: float = 0.7397927100428358,
                 longitude_rad: float = -1.2434074657057992, timezone_h: float = -5.0,
                 shared_coord_guid: Optional[str] = None) -> SkelElement:
    """A ``GeoSite`` symbol (class 0x8e1): the site location (lat/long in
    radians, time zone) + weather data [VERIFIED structure vs rstbasic
    21747].  Templates carry two ('Internal', 'Project').  Weather arrays
    hold Revit's stock design-day temperatures (Kelvin) [product defaults].
    ``shared_coord_guid`` defaults to :func:`our_guid` ('geo-site') of the
    site's identity (id, name, lat, lon, tz); an explicit GUID wins."""
    o = symbol_base(elem_id, name, cell_list=False)
    o["m_dLatitude"] = float(latitude_rad)
    o["m_dLongitude"] = float(longitude_rad)
    o["m_dTimeZone"] = float(timezone_h)
    o["m_dElevation"] = 0.0
    o["m_dWinterDryBulbTemperature"] = 259.0
    o["m_ClearnessNumber"] = 1.0
    o["m_ownerSymbolId"] = -1
    o["m_geodeticCoordinatesBasePointType"] = 0
    o["m_sharedCoordGUID"] = shared_coord_guid or our_guid(
        "geo-site", int(elem_id), name, o["m_dLatitude"], o["m_dLongitude"], o["m_dTimeZone"])
    o["m_bUseDST"] = False
    o["m_bUserDefinedWeatherData"] = False
    o["m_bFromClimateServer"] = False
    o["m_bIsLocationDefinedByDefaultCityList"] = False
    o["m_geoCoordinateSystem"] = ""
    o["m_placeName"] = ""
    o["m_weatherStationName"] = ""
    o["m_zipCodeOrPostalCode"] = "00000"
    o["m_dSummerDryBulbTemperature"] = [285.0, 287.0, 292.0, 298.0, 304.0, 306.0,
                                       307.0, 306.0, 303.0, 298.0, 294.0, 289.0]
    o["m_dSummerWetBulbTemperature"] = [284.0, 284.0, 286.0, 290.0, 295.0, 297.0,
                                       299.0, 299.0, 297.0, 293.0, 290.0, 287.0]
    o["m_dMeanDailyTemperature"] = [260.2, 260.777, 260.777, 260.777, 261.33,
                                    261.8, 261.33, 260.777, 261.33, 261.33,
                                    260.777, 260.2]
    hdr = element_header("GeoSite", category=BIC_SITE, deletion=[elem_id],
                         flags=30, visible_view_flags=-32768)
    return SkelElement(elem_id, "GeoSite", hdr, o, None, kind="site")


def new_geo_location(elem_id: int, site_id: int, name: str = "Project", *,
                     origin_ft: Sequence[float] = (0.0, 0.0, 0.0),
                     angle_rad: float = 0.0) -> SkelElement:
    """A ``GeoLocation`` (class 0x8e0) = a placement (Instance) of a
    GeoSite symbol: the named position 'Internal' or 'Project' [VERIFIED
    structure vs rstbasic 21748/111428].  The transform positions the model
    on the site (project position: origin + rotation about Z)."""
    c, s = math.cos(angle_rad), math.sin(angle_rad)
    o = element_base(elem_id, cell_list=False)
    o["m_pGeomTable"] = _ptr("GeomTable", {
        "m_refPntMirrored": False, "m_table": [{"m_geomGeneratorId": -1}],
        "m_bigTableOwner": None, "m_materialMarkers": [], "m_faceTypeMarkers": []})
    o["m_pInstanceInfo"] = _ptr("InstanceInfo", {
        "m_Trf": {"m_3x3": [[c, s, 0.0], [-s, c, 0.0], [0.0, 0.0, 1.0]],
                  "m_or": list(map(float, origin_ft))},
        "m_symbolId": int(site_id), "m_GRepId": 0,
        "m_cda": {"m_pDoc": _weak(1)}})
    o["m_GInstanceId"] = 0
    o["m_name"] = str(name)
    hdr = element_header("GeoLocation", category=BIC_GEO_LOCATION,
                         deletion=[site_id, elem_id], appearance=[site_id],
                         flags=14, visible_view_flags=-32768)
    return SkelElement(elem_id, "GeoLocation", hdr, o, None, kind="site")


# ---------------------------------------------------------------------------
# VIEWS -- the DBView base and the view constellations
# ---------------------------------------------------------------------------

def _grender_settings(print_page_width: int = 6) -> dict:
    """Default GRenderSettings block of a ViewDisplayMgr (Revit's stock
    'SunAndSky-002' environment + 'Generic' quality/exposure assets from
    ``assetlibrary_base.fbx`` -- product render defaults) [VERIFIED value]."""
    def asset(name, atype, props):
        return {"m_sName": name, "m_aChild": None, "m_aConnected": [],
                "m_aAProperties": props, "m_sLibrary": "assetlibrary_base.fbx",
                "m_sScene": "", "m_oImage": None, "m_eAssetType": atype}
    quality = [
        _ptr("APropertyInteger", {"m_sName": "lightAndMaterialAccuracy", "m_aChild": None, "m_aConnected": [], "m_value": 1}),
        _ptr("APropertyInteger", {"m_sName": "renderDuration", "m_aChild": None, "m_aConnected": [], "m_value": 0}),
        _ptr("APropertyFloat", {"m_sName": "renderNoiseLevel", "m_aChild": None, "m_aConnected": [], "m_value": 1.0}),
        _ptr("APropertyFloat", {"m_sName": "renderLevels", "m_aChild": None, "m_aConnected": [], "m_value": 1.0}),
        _ptr("APropertyInteger", {"m_sName": "renderTime", "m_aChild": None, "m_aConnected": [], "m_value": 1}),
    ]
    exposure = [
        _ptr("APropertyDouble1", {"m_sName": "ExposureValue", "m_aChild": None, "m_aConnected": [], "m_value": 14.0}),
    ]
    return _ptr("GRenderSettings", {
        "m_fVisibilityDistance": 0.0, "m_iResolution": 150,
        "m_iPrintPageWidth": int(print_page_width), "m_eQuality": 11,
        "m_eLighting": 21, "m_eBackground": 32, "m_clrBackground": 16761984,
        "m_screenResolution": True,
        "m_oEnvironmentAssets": asset("SunAndSky-002", 8, []),
        "m_customQualityAsset": asset("Generic", 7, quality),
        "m_oExposureAssets": asset("Generic", 9, exposure),
        "m_oLightScheme": None,
        "m_BkIamgeSettings": {"m_ImageFileName": "", "m_OffsetWidth": 0.0,
                              "m_OffsetHeight": 0.0, "m_FitType": 43},
    })


def view_display_mgr(sun_settings_id: int, *, ambient_shadows: bool = False,
                     shadow_intensity: int = 50, sunlight_intensity: int = 80,
                     ground_color: int = 10855845, surfaces: int = 2) -> dict:
    """A view's ``ViewDisplayMgr`` (graphic-display / render settings) with
    Revit's stock values; ``sun_settings_id`` = the view's
    ``SunAndShadowSettings`` element [VERIFIED structure, all 3 view classes]."""
    return _ptr("ViewDisplayMgr", {
        "m_background": {"m_imagePath": "", "m_bkImageOffsets": [0.0, 0.0],
                         "m_bkImageScales": [0.0, 0.0], "m_backgroundColor": 15921906,
                         "m_groundColor": int(ground_color), "m_imageFlags": 0,
                         "m_skyColor": 13685181, "m_type": 256},
        "m_fog": {"m_color": 16777215, "m_density": 100, "m_end": 100,
                  "m_start": 0, "m_enable": False},
        "m_lights": {"m_sunAndShadowSettingsId": int(sun_settings_id),
                     "m_ambientLightIntensity": 0,
                     "m_shadowIntensity": int(shadow_intensity),
                     "m_sunlightIntensity": int(sunlight_intensity)},
        "m_model": {"m_silhouetteEdgesGStyleId": -1, "m_edges": 1,
                    "m_showHiddenLinesVal": 1, "m_surfaces": int(surfaces),
                    "m_transparency": 0, "m_enableSilhouettes": False,
                    "m_smoothEdges": False},
        "m_oRaytraceSettings": _grender_settings(6),
        "m_sketchyLines": {"m_extension": 0, "m_jitter": 0,
                           "m_enableSketchyLines": False},
        "m_oStaticRRTRenderSettings": _grender_settings(6),
        "m_exposure": {"m_burnHighlights": 0.25, "m_crushBlacks": 1.0,
                       "m_gamma": 2.2, "m_exposureDouble": 15.0,
                       "m_physicalScale": 1.0, "m_saturation": 1.0,
                       "m_vignetting": 0.0, "m_whitePoint": 6500.0,
                       "m_RPCAppearance": 0, "m_type": 1},
        "m_waterColorType": 0, "m_hlr": True, "m_lighting": False,
        "m_shadows": {"m_ambientShadows": bool(ambient_shadows),
                      "m_castShadows": False},
    })


#: BuiltInCategories a view excludes from drawing by default via its
#: ``IckyExcludedCategoriesSetPtrWrapper`` draw filter (per view kind)
#: [VERIFIED lists from the rstbasic project view / plan / 3D view; the
#: exact meaning of each id is a category-table lookup].
DRAW_EXCLUDED_CATEGORIES = {
    "project": [-2009667, -2009666, -2001115, -2001113, -2001083, -2001075, -2001035],
    "plan": [-2009667, -2009666, -2009665, -2009664, -2009662, -2009645, -2009007,
             -2008186, -2001115, -2001113, -2001083, -2001075, -2001035],
    "3d": [-2009667, -2009666, -2009645, -2009609, -2009007, -2008186, -2003400,
           -2003200, -2003100, -2002000, -2001360, -2001352, -2001350, -2001340,
           -2001330, -2001320, -2001300, -2001280, -2001270, -2001262, -2001261,
           -2001260, -2001250, -2001240, -2001220, -2001200, -2001180, -2001160,
           -2001140, -2001120, -2001115, -2001113, -2001100, -2001083, -2001075,
           -2001060, -2001040, -2001035, -2001020, -2001010, -2000983, -2000970,
           -2000960, -2000950, -2000901, -2000899, -2000898, -2000897, -2000896],
}


def draw_filters(excluded_categories: Sequence[int],
                 analytical_excluded: bool = False) -> list:
    """A view's ``m_oaDrawFilters``: the six standard draw filters
    [VERIFIED structure]."""
    return [
        _ptr("IckyExcludedCategoriesSetPtrWrapper", {
            "m_annotationsExcluded": False, "m_modelsExcluded": False,
            "m_analyticalModelsExcluded": bool(analytical_excluded),
            "m_importsExcluded": False,
            "m_ccda": {"m_pDoc": _weak(1)},
            "m_categoryIds": [int(c) for c in excluded_categories]}),
        _ptr("PartitionVisibilityDrawFilter", {}),
        _ptr("PhasingDrawFilter", {}),
        _ptr("DesignOptionDrawFilter", {}),
        _ptr("RvtLinkDrawFilter", {}),
        _ptr("HideElementsDrawFilter", {}),
    ]


def dbview_base(elem_id: int, name: str, *, viewer_id: int, drawing_id: int,
                sun_settings_id: int, view_type_id: int = -1,
                phase_id: int = -1, phase_filter_id: int = -1,
                extent_elem_id: int = -1, fixed_sketch_plane_id: int = -1,
                gen_elem_id: int = -1, light_scheme_id: int = -1,
                view_template_id: int = -1,
                origin: Sequence[float] = (0.0, 0.0, 0.0),
                view_dir: Sequence[float] = (0.0, 0.0, 1.0),
                horz_dir: Sequence[float] = (1.0, 0.0, 0.0),
                vert_dir: Sequence[float] = (0.0, 1.0, 0.0),
                scale: float = 0.01, back_clipping: int = -1,
                excluded_categories: Sequence[int] = (),
                analytical_excluded: bool = False,
                int_params: Sequence[Tuple[int, int]] = (),
                invisible_style_id: int = -1, not_silhouette_style_id: int = -1,
                cell_list: bool = True, ambient_shadows: bool = False,
                shadow_intensity: int = 50) -> dict:
    """The shared ``DBView`` base object (class 0x72) all views extend
    [VERIFIED: 461-leaf common structure across DBViewProject / DBView3d /
    DBViewPlan in three templates].

    A view is DEFINED by: its name, its ``m_dbViewTypeId`` (the
    DBViewType = view family type), its orientation frame (``origin``,
    ``view_dir``, ``horz_dir``, ``vert_dir``), ``scale`` (drawing scale as a
    fraction: 0.01 = 1:100 ... plans; 3D views carry an arbitrary value),
    the phase parameters (``phase_id`` / ``phase_filter_id`` as ElementId
    parameters -1012102 / -1012103) and its links to its satellite elements
    (``viewer_id``, ``drawing_id``, ``extent_elem_id``,
    ``fixed_sketch_plane_id``, ``light_scheme_id``, and the
    ``sun_settings_id`` embedded in the ViewDisplayMgr).  Everything else
    below is stock display settings.  ``invisible_style_id`` /
    ``not_silhouette_style_id`` = the two GStyleElem the RetouchTable
    references (object-styles registry; -1 leaves them unbound [UNKNOWN
    tolerance]).
    """
    o = element_base(elem_id, cell_list=cell_list)
    o["m_pParamValueSetInt"] = param_set_int(int_params)
    o["m_pParamValueSetElementId"] = param_set_elemid([
        (BIP_VIEW_PHASE_FILTER, phase_filter_id), (BIP_VIEW_PHASE, phase_id)])
    o["m_pADoc"] = _weak(1)
    o["m_oAdHocOverrides"] = _ptr("AdHocOverrides", {"m_elementMap": [],
                                                     "m_oaSettings": []})
    o["m_dependentViewIds"] = []
    o["m_oDesignOptionViewSettings"] = _ptr("DesignOptionViewSettings",
                                            {"m_mOverridingOptions2": []})
    o["m_oDirectContext3DHandleOverrides"] = _ptr("DirectContext3DHandleOverrides",
                                                  {"m_overridesMap": []})
    o["m_explicitlyHiddenElements"] = []
    o["m_oFilterOverrides"] = _ptr("FilterOverrides", {"m_oaSettings": []})
    o["m_oGraphicOverrides"] = _ptr("GraphicOverrides", {
        "m_structuralLayerCleanupType": 0, "m_bHostLayersOverridden": False,
        "m_gStylesProj": [], "m_gStylesCut": [], "m_fillPatternsProj": [],
        "m_fillPatternsCut": [], "m_fillColorsProj": [], "m_fillColorsCut": [],
        "m_fillHiddenProj": [], "m_fillHiddenCut": [],
        "m_backgroundFillPatternsProj": [], "m_backgroundFillPatternsCut": [],
        "m_backgroundFillColorsProj": [], "m_backgroundFillColorsCut": [],
        "m_backgroundFillHiddenProj": [], "m_backgroundFillHiddenCut": [],
        "m_halftones": [], "m_surfacesTransparency": [], "m_detailLevels": []})
    o["m_oHiddenElementsViewSettings"] = _ptr("HiddenElementsViewSettings", {
        "m_foreignElements": [], "m_hiddenElements": []})
    o["m_oaDrawFilters"] = draw_filters(excluded_categories, analytical_excluded)
    o["m_pColorFillSchemaSetting"] = _ptr("ColorFillSchemaSetting", {
        "m_categoryToSchema": [], "m_bBackground": True})
    o["m_pDetailDrawOrderMgr"] = _ptr("DrawOrderMgr", {
        "m_pADoc": _weak(1), "m_pDBView": _weak(2), "m_aDrawOrder": []})
    o["m_pHideElementsMgr"] = _ptr("HideElementsMgr", {
        "m_hidding2hidden": [], "m_hidden2hidding": []})
    o["m_pRetouchTable"] = _ptr("RetouchTable", {
        "m_lineworkMap4": [], "m_invisibleGStyleId": int(invisible_style_id),
        "m_notSilhouetteGStyleId": int(not_silhouette_style_id),
        "m_bFaceRecsUpgraded": True})
    o["m_pRvtLinkOverrides"] = _ptr("RvtLinkOverrides", {
        "m_invisibleSet": [], "m_halftoneSet": [], "m_underlaySet": [],
        "m_displaySettingsMap": [],
        "m_upgradeForWorksetVisibilityInLinkFiles": False})
    o["m_pViewDisplayMgr"] = view_display_mgr(sun_settings_id,
                                              ambient_shadows=ambient_shadows,
                                              shadow_intensity=shadow_intensity)
    o["m_strCustomScaleName"] = ""
    o["m_nonPropagatedTemplateParamIds"] = []
    o["m_oPointCloudOverrides"] = _ptr("PointCloudOverrides", {
        "m_settingsMap": [], "m_regionSettingsMap": []})
    o["m_viewDescription"] = ""
    o["m_viewName"] = str(name)
    o["m_oWorksetVisibilityViewSettings"] = _ptr("WorksetVisibilityViewSettings", {
        "m_worksetVisibilityPGUIDMap": []})
    o["m_analysisDisplayStyleId"] = -1
    o["m_dbDrawingId"] = int(drawing_id)
    o["m_dbViewTypeId"] = int(view_type_id)
    o["m_defaultTemplateId"] = -1
    o["m_extentElemId"] = int(extent_elem_id)
    o["m_fixedSketchPlaneId"] = int(fixed_sketch_plane_id)
    o["m_genElemId"] = int(gen_elem_id)
    o["m_horzDir"] = list(map(float, horz_dir))
    o["m_lightSchemeId"] = int(light_scheme_id)
    o["m_shopDrawingAssemblyInstanceId"] = -1
    o["m_origin"] = list(map(float, origin))
    o["m_primaryViewId"] = -1
    o["m_scale"] = float(scale)
    o["m_sheetViewportElemId"] = -1
    o["m_vertDir"] = list(map(float, vert_dir))
    o["m_viewDir"] = list(map(float, view_dir))
    o["m_viewPositionId"] = -1
    o["m_viewTemplateId"] = int(view_template_id)
    o["m_viewerId"] = int(viewer_id)
    o["m_backClipping"] = int(back_clipping)
    o["m_modelDisplayMode"] = 0
    o["m_partsVisibility"] = 1
    o["m_forceCustomViewScale"] = False
    o["m_isTemplate"] = False
    o["m_bCustomScaleName"] = False
    o["m_named"] = True
    return o


def new_view_type(elem_id: int, name: str, family: str = "3d", *,
                  poche_material_id: int = -1,
                  default_template_id: int = -1) -> SkelElement:
    """A ``DBViewType`` (view family type, class 0x486): the SYSTEM-FAMILY
    TYPE a view belongs to [VERIFIED vs rstbasic 49559 '3D View' /
    69847 'Structural Plan'].  ``family`` selects ``m_systemFamilyIdx`` from
    :data:`VIEW_FAMILY` (or pass an int).  ``m_planViewDirection`` = 0 for
    plan families, -1 otherwise [VERIFIED]."""
    fam = VIEW_FAMILY.get(family, family) if isinstance(family, str) else int(family)
    o = symbol_base(elem_id, name, cell_list=True)
    o["m_refLabelStr"] = "Sim"
    o["m_sectionAttrId"] = -1
    o["m_calloutAttrId"] = -1
    o["m_elevatnAttrId"] = -1
    o["m_pocheMatId"] = int(poche_material_id)
    o["m_defaultTemplateId"] = int(default_template_id)
    o["m_systemFamilyIdx"] = int(fam)
    o["m_planViewDirection"] = PLAN_VIEW_DIRECTION.get(family, -1) \
        if isinstance(family, str) else -1
    o["m_defaultTemplateIdAssignOnViewCreation"] = True
    dele = [elem_id] + ([poche_material_id] if poche_material_id >= 0 else [])
    hdr = element_header("DBViewType", category=-1, deletion=dele,
                         flags=2074, visible_view_flags=-32768)
    return SkelElement(elem_id, "DBViewType", hdr, o, None, kind="view_type")


def _viewer_bounded_space(orig, basis, offsets, active, is_on) -> dict:
    return {"m_orig": list(map(float, orig)),
            "m_basis": [list(map(float, r)) for r in basis],
            "m_boundOffset": [list(map(float, r)) for r in offsets],
            "m_boundActive": [[bool(a), bool(b)] for a, b in active],
            "m_isOn": bool(is_on)}


def _viewer_gstep(flags: int = 761725) -> dict:
    """GeomStepList of a Viewer (one ViewerGStep) [VERIFIED vs 245445]."""
    return _ptr("GeomStepList", {
        "m_nonBRepGList": [_ptr("ViewerGStep", {
            "m_faceHistTable": [], "m_curveHistTableSet": [],
            "m_edgeHistTable": [], "m_edgeHistTableReverse": [],
            "m_id": 1, "m_version": 0, "m_flags": int(flags),
            "m_pElem": _weak(2), "m_oExtraDatas": None})],
        "m_bRepFormGList": [], "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [], "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [0, 0, 0, 0, 0],
        "m_idCounter": 2, "m_flags": 11})


def _viewer_common(elem_id: int, view_id: int, *, orig, basis, offsets,
                   active, crop_on: bool, target: Sequence[float],
                   axis: Sequence[float], proj_dist: float,
                   with_gstep: bool, cell_list: bool = False) -> dict:
    """The shared ``Viewer`` (class 0x2d4) fields: the view's crop/bound box
    + camera frame [VERIFIED structure vs rstbasic 231 / 245445]."""
    o = element_base(elem_id, cell_list=cell_list, design_option=-4)
    o["m_pParamValueSetElementId"] = param_set_elemid([(BIP_VIEWER_BOUND_ACTIVE, -1)])
    if with_gstep:
        o["m_geomSteps"] = _viewer_gstep()
    o["m_boundedSpace"] = _viewer_bounded_space(orig, basis, offsets, active, crop_on)
    o["m_pAnnotationCropOffsets"] = _ptr("AnnotationCropOffsets", {
        "m_leftRightTopBottomOffsets": [0.08333333333333333] * 4})
    o["m_targetPos"] = list(map(float, target))
    o["m_axisDir"] = list(map(float, axis))
    o["m_projDist"] = float(proj_dist)
    o["m_dbViewId"] = int(view_id)
    o["m_VisibleInDesignOption"] = -1
    o["m_sketchId"] = -1
    o["m_projMethodType"] = 2
    o["m_viewerFlags"] = 7
    o["m_bReflected"] = False
    o["m_intentionallyPlaced"] = True
    o["m_bIsViewerReference"] = False
    o["m_bAnnotationCropActive"] = False
    o["m_oViewLayout"] = _ptr("ViewLayout", {
        "m_arrViewRegions": [{"m_dMin": 0.0, "m_dMax": 1.0, "m_dOffset": 0.0}],
        "m_iDim": 0})
    o["m_nonRectangularCropAreaCurvesLoops"] = []
    return o


def new_viewer(elem_id: int, view_id: int, *,
               orig: Sequence[float] = (0.0, 0.0, 0.0),
               crop_on: bool = False, with_gstep: bool = True,
               regen_only: Sequence[int] = (), appearance: Sequence[int] = (),
               flags: int = 10) -> SkelElement:
    """The ``Viewer`` of a plan / project view: view frame + crop box
    (crop off by default) [VERIFIED structure vs 231 (project view viewer,
    no gstep, no cellList) and 245445 (plan viewer)].  ElemRec owner = view."""
    o = _viewer_common(elem_id, view_id, orig=orig,
                       basis=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [-0.0, -0.0, -1.0]],
                       offsets=[[100.0, -100.0], [100.0, -100.0], [1000.0, 0.1]],
                       active=[[True, True], [True, True], [False, False]],
                       crop_on=crop_on, target=(0.0, 0.0, 0.0),
                       axis=(0.0, 1.0, 0.0), proj_dist=0.1,
                       with_gstep=with_gstep)
    hdr = element_header("Viewer", category=-1, deletion=[view_id, elem_id],
                         regen_only=regen_only, appearance=appearance,
                         flags=flags, visible_view_flags=-129)
    return SkelElement(elem_id, "Viewer", hdr, o, None, owner_id=view_id,
                       kind="view_satellite")


def new_viewer3d(elem_id: int, view_id: int, clip_box_id: int, *,
                 orig: Sequence[float] = (0.0, 0.0, 0.0),
                 basis: Optional[Sequence[Sequence[float]]] = None,
                 target: Sequence[float] = (0.0, 0.0, 0.0),
                 view_type_id: int = -1) -> SkelElement:
    """The ``Viewer3d`` (class 0x117b) of a 3D view: camera bound box +
    perspective frame + the section box link [VERIFIED structure vs rstbasic
    1138900].  Its seq-103 rep in the corpus is a GENERATED camera-symbol
    GElement (the little camera you see in plan); genesis emits
    SerializedDummy [UNKNOWN whether the reader requires the camera rep --
    it is regenerable geometry, and SerializedDummy reps were accepted for
    walls (V22)]."""
    b = basis or [[0.0, -1.0, 0.0], [0.0, 0.0, 1.0], [1.0, 0.0, 0.0]]
    o = _viewer_common(elem_id, view_id, orig=orig, basis=b,
                       offsets=[[0.05, -0.05], [0.03, -0.03], [225.0, 0.225]],
                       active=[[True, True], [True, True], [False, False]],
                       crop_on=True, target=target, axis=(0.0, 0.0, 1.0),
                       proj_dist=0.1, with_gstep=False)
    o["m_geomSteps"] = None    # camera symbol geometry regenerated by Revit
    o["m_WTPath"] = None       # walkthrough path (none)
    o["m_pCutter"] = None      # far-clip cutter (none)
    o["m_savedOrientation"] = None
    o["m_modelClipBoxId"] = int(clip_box_id)
    o["m_lockedOrientation"] = False
    regen = [view_type_id] if view_type_id >= 0 else []
    hdr = element_header("Viewer3d", category=BIC_CAMERAS,
                         deletion=[elem_id, clip_box_id, view_id],
                         regen_only=regen, appearance=regen,
                         flags=16680, visible_view_flags=-129)
    return SkelElement(elem_id, "Viewer3d", hdr, o, None, owner_id=view_id,
                       kind="view_satellite",
                       notes=["seq103 SerializedDummy (corpus rep = generated camera GElement)"])


def new_model_clip_box(elem_id: int, viewer3d_id: int, *, half_extent_ft: float = 100.0,
                       is_on: bool = False) -> SkelElement:
    """The ``ModelClipBox`` (section box, class 0xab9) every Viewer3d owns
    [VERIFIED structure vs rstbasic 1138901]; off by default."""
    h = float(half_extent_ft)
    o = element_base(elem_id, cell_list=False, design_option=-4)
    o["m_boundedSpace"] = _viewer_bounded_space(
        (0.0, 0.0, 0.0), [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
        [[h, -h], [h, -h], [h, -h]], [[True, True]] * 3, is_on)
    o["m_viewer3dId"] = int(viewer3d_id)
    hdr = element_header("ModelClipBox", category=BIC_SECTION_BOX,
                         deletion=[viewer3d_id, elem_id], appearance=[viewer3d_id],
                         flags=10, visible_view_flags=-4225)
    return SkelElement(elem_id, "ModelClipBox", hdr, o, None, owner_id=viewer3d_id,
                       kind="view_satellite")


def new_dbdrawing(elem_id: int, viewport_ids: Sequence[int], owner_view_id: int,
                  flags: int = 8202) -> SkelElement:
    """A view's internal ``DBDrawing`` (class 0x463): the drawing that
    lists the view's own Viewport(s) [VERIFIED structure vs rstbasic 233 /
    245449; present at document birth for the project view].  ElemRec owner
    = the view."""
    o = element_base(elem_id, cell_list=(flags == 2074), design_option=-4)
    o["m_viewports"] = [int(v) for v in viewport_ids]
    o["m_pADoc"] = _weak(1)
    hdr = element_header("DBDrawing", category=-1,
                         deletion=list(viewport_ids) + [elem_id],
                         flags=flags, visible_view_flags=-32768)
    return SkelElement(elem_id, "DBDrawing", hdr, o, None, owner_id=owner_view_id,
                       kind="view_satellite")


def new_viewport(elem_id: int, view_id: int, drawing_id: int, *,
                 viewport_type_id: int = -1, label_origin_z: float = 0.0,
                 flags: int = 10) -> SkelElement:
    """The ``Viewport`` (class 0x88d) a DBDrawing lists for its view
    [VERIFIED structure vs rstbasic 232 (project view) / 1138904 (3D view)].
    ``viewport_type_id`` = ViewportAttributes ('Title w Line') type, -1 =
    none.  ElemRec owner = the DBDrawing."""
    o = element_base(elem_id, cell_list=(flags == 2074), design_option=-4)
    o["m_detailNumber"] = ""
    o["m_labelLength"] = 0.0
    o["m_labelOrigin"] = [0.0, 0.0, float(label_origin_z)]
    o["m_offset"] = [0.0, 0.0, 0.0]
    o["m_scale"] = 0.0
    o["m_stretchFactor"] = 1.0
    o["m_viewPosition"] = [0.0, 0.0, 0.0]
    o["m_attrId"] = int(viewport_type_id)
    o["m_dbDrawingId"] = int(drawing_id)
    o["m_dbViewId"] = int(view_id)
    o["m_viewportOrientation"] = 0
    o["m_viewportPositioning"] = 0
    o["m_viewAnchor"] = 0
    o["m_clipping"] = False
    o["m_oPlaceholderBoxOutline"] = None
    dele = [view_id, elem_id, drawing_id] + ([viewport_type_id] if viewport_type_id >= 0 else [])
    hdr = element_header("Viewport", category=BIC_VIEWPORTS, deletion=dele,
                         dependency=[view_id],
                         flags=flags, visible_view_flags=-129)
    return SkelElement(elem_id, "Viewport", hdr, o, None, owner_id=drawing_id,
                       kind="view_satellite")


def new_extent_elem(elem_id: int, view_id: int, normal: Sequence[float]) -> SkelElement:
    """The ``ExtentElem`` (class 0x672) that owns a view's model-extent
    references (level/grid datum extents in that view) [VERIFIED structure
    vs rstbasic 245444/1470254]."""
    o = element_base(elem_id, cell_list=False, owner_view=view_id)
    o["m_dbViewNorm"] = list(map(float, normal))
    o["m_dbViewId"] = int(view_id)
    o["m_idExtents"] = []
    hdr = element_header("ExtentElem", category=-1, deletion=[view_id, elem_id],
                         owner_view=view_id, flags=10, visible_view_flags=-21474)
    return SkelElement(elem_id, "ExtentElem", hdr, o, None, kind="view_satellite")


def new_sketch_plane(elem_id: int, view_id: int, datum_id: int, elevation_ft: float,
                     regen_level_id: int = -1) -> SkelElement:
    """A plan view's fixed ``SketchPlane`` (class 0xf5d) lying on the plan's
    level datum [VERIFIED structure vs rstbasic 245451: the plane references
    the view via ``m_datumPlaneId`` and sits at the level elevation]."""
    o = element_base(elem_id, cell_list=False, owner_view=view_id)
    o["m_oPlaneRef"] = _ptr("OnDBViewPlaneRef", {
        "m_geomRef": {"m_intermediateTags": [], "m_oNextRef": None,
                      "m_elemId": -1, "m_ownerDBViewId": -1,
                      "m_foreignElemIdRef": {"m_id64": -1},
                      "m_geomTag": -1, "m_subTag": -1, "m_famMemberIdx": -1,
                      "m_flags": 0, "m_isLazyRef": False},
        "m_vecInPlane": [0.0, 0.0, 0.0], "m_rotation": 0.0,
        "m_datumPlaneId": int(datum_id), "m_mirror": False})
    o["m_oTrf"] = _ptr("Trf", {"m_3x3": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0],
                                          [0.0, 0.0, 1.0]],
                                "m_or": [0.0, 0.0, float(elevation_ft)]})
    o["m_userId"] = -1
    o["m_flipZ"] = False
    hdr = element_header("SketchPlane", category=-1, deletion=[datum_id, elem_id],
                         regen_only=[regen_level_id] if regen_level_id >= 0 else [],
                         owner_view=view_id, flags=10, visible_view_flags=-32768)
    return SkelElement(elem_id, "SketchPlane", hdr, o, None, kind="view_satellite")


def new_sun_and_shadow_settings(elem_id: int, view_id: int = -1, *,
                                name: str = "<In-session, Still>",
                                level_id: int = -1, annotation_id: int = -1,
                                azimuth_rad: float = 2.3561944901923426,
                                altitude_rad: float = 0.6108652381980147,
                                owner_regen: Sequence[int] = ()) -> SkelElement:
    """A ``SunAndShadowSettings`` (class 0x1074): the sun position a view's
    ViewDisplayMgr points at [VERIFIED structure vs rstbasic 245446].
    ``view_id`` = the owning view (-1 = the document-wide setting the
    project view uses, cf. ancestral id 54520); ``level_id`` = the ground
    level for shadows (optional, -1 in 63/90 corpus specimens);
    ``annotation_id`` = the sun-path SunAnnotationElem (optional, -1 in
    62/90) [VERIFIED optionality]."""
    o = element_base(elem_id, cell_list=False, owner_view=view_id)
    o["m_sName"] = str(name)
    o["m_outline"] = {"m_minmax": [[1e+30, 1e+30, 1e+30], [-1e+30, -1e+30, -1e+30]]}
    o["m_dAzimuth"] = float(azimuth_rad)
    o["m_dAltitude"] = float(altitude_rad)
    o["m_activeFrame"] = 1.0
    o["m_idLevel"] = int(level_id)
    o["m_idAnnotation"] = int(annotation_id)
    o["m_startDateTime"] = 2108033792
    o["m_endDateTime"] = 2103131034
    o["m_eSunStudyTimeInterval"] = 3
    o["m_type"] = 0
    o["m_sunPathSize"] = 150
    o["m_bGroundPlane"] = level_id >= 0
    o["m_bRelativeToView"] = view_id >= 0
    o["m_sunriseToSunset"] = False
    o["m_updateSunpath"] = True
    o["m_sharedSetting"] = False
    dele = [elem_id] + [x for x in (view_id, level_id, annotation_id) if x >= 0]
    hdr = element_header("SunAndShadowSettings", category=BIC_SUN_STUDY,
                         deletion=dele, regen_only=owner_regen, owner_view=view_id,
                         flags=10, visible_view_flags=-4225)
    return SkelElement(elem_id, "SunAndShadowSettings", hdr, o, None,
                       owner_id=view_id, kind="view_satellite")


def new_light_scheme(elem_id: int, view_id: int) -> SkelElement:
    """The ``LightSchemeElement`` (class 0x9f9) a 3D view owns (empty
    scheme = daylight only) [VERIFIED structure vs rstbasic 1138906]."""
    o = element_base(elem_id, cell_list=False, owner_view=view_id)
    o["m_oScheme"] = _ptr("LightScheme", {"m_lightSchemeEntries": []})
    hdr = element_header("LightSchemeElement", category=-1,
                         deletion=[view_id, elem_id], owner_view=view_id,
                         flags=8202, visible_view_flags=-32768)
    return SkelElement(elem_id, "LightSchemeElement", hdr, o, None, kind="view_satellite")


# --- the three view constellations -------------------------------------------

@dataclass
class ViewSpec:
    """The elements one view expands into (the view + its satellites).

    ``view`` is the DBView* element; ``satellites`` the elements that
    exist only to serve it (viewer, drawing, viewport, extent, sketch plane,
    sun settings, light scheme, clip box).  ``elements()`` yields all of
    them in dependency order (satellites the view references first).
    """
    view: SkelElement
    satellites: List[SkelElement] = dc_field(default_factory=list)

    def elements(self) -> List[SkelElement]:
        return [*self.satellites, self.view]


def new_project_view(ids: IdSource, *, phase_id: int = -1, phase_filter_id: int = -1,
                     sun_settings_id: int = -1,
                     invisible_style_id: int = -1, not_silhouette_style_id: int = -1,
                     name: str = "???") -> ViewSpec:
    """The document's implicit PROJECT VIEW (``DBViewProject``, class 0x47c)
    with its Viewer, DBDrawing and Viewport -- the ONE view constellation
    present at EPISODE 0 (birth) in every corpus template (ancestral ids
    230/231/233/232), i.e. the minimum viewable set a document is born with
    [VERIFIED 3/3 templates].  ``sun_settings_id`` = the document-wide
    SunAndShadowSettings its ViewDisplayMgr references (ancestral 54520);
    pass -1 and it stays unbound [UNKNOWN tolerance] -- prefer
    :func:`new_document_sun_settings`.  Its DBView type is -1, view
    direction is -Y (front), scale 0.01, name '???' [VERIFIED constants]."""
    view_id = _alloc(ids)
    viewer_id = _alloc(ids)
    viewport_id = _alloc(ids)
    drawing_id = _alloc(ids)
    obj = dbview_base(view_id, name, viewer_id=viewer_id, drawing_id=drawing_id,
                      sun_settings_id=sun_settings_id, view_type_id=-1,
                      phase_id=phase_id, phase_filter_id=phase_filter_id,
                      origin=(0.0, 0.0, 0.0), view_dir=(0.0, -1.0, 0.0),
                      horz_dir=(1.0, 0.0, -0.0), vert_dir=(0.0, 0.0, 1.0),
                      scale=0.01, back_clipping=-1,
                      excluded_categories=DRAW_EXCLUDED_CATEGORIES["project"],
                      invisible_style_id=invisible_style_id,
                      not_silhouette_style_id=not_silhouette_style_id,
                      cell_list=True, shadow_intensity=60)
    dele = [view_id, viewer_id, drawing_id] + [x for x in (
        phase_id, phase_filter_id, sun_settings_id, invisible_style_id,
        not_silhouette_style_id) if x >= 0]
    hdr = element_header("DBViewProject", category=-1, deletion=dele,
                         flags=67610, visible_view_flags=-32640)
    view = SkelElement(view_id, "DBViewProject", hdr, obj, None, kind="view",
                       notes=["the birth (episode-0) view; type -1; name '???'"])
    # the project view's viewer: elevation-style frame (Y up), bounds
    # inactive, ortho (m_projMethodType 1) [VERIFIED byte-exact vs rstbasic 231]
    vo = _viewer_common(viewer_id, view_id, orig=(0.0, 0.0, 0.0),
                        basis=[[1.0, 0.0, 0.0], [0.0, 0.0, 1.0], [-0.0, 1.0, -0.0]],
                        offsets=[[100.0, -100.0], [100.0, -100.0], [100.0, -100.0]],
                        active=[[False, False], [False, False], [False, False]],
                        crop_on=True, target=(0.0, 0.0, 0.0),
                        axis=(0.0, 0.0, 1.0), proj_dist=0.1,
                        with_gstep=True, cell_list=True)
    vo["m_geomSteps"]["value"]["m_latestGStepTypeInPrevRegenCycle"] = [0, 0, 0, 0, 0]
    vo["m_pParamValueSetElementId"] = None    # no crop param on the project viewer
    vo["m_projMethodType"] = 1
    vo["m_viewerFlags"] = 0
    vo["m_intentionallyPlaced"] = False
    vhdr = element_header("Viewer", category=-1, deletion=[view_id, viewer_id],
                          flags=2074, visible_view_flags=-129)
    viewer = SkelElement(viewer_id, "Viewer", vhdr, vo, None, owner_id=view_id,
                         kind="view_satellite")
    viewport = new_viewport(viewport_id, view_id, drawing_id,
                            label_origin_z=-0.16404199475065614, flags=2074)
    drawing = new_dbdrawing(drawing_id, [viewport_id], view_id, flags=2074)
    return ViewSpec(view, [viewer, viewport, drawing])


def new_3d_view(ids: IdSource, name: str, view_type_id: int, *,
                phase_id: int = -1, phase_filter_id: int = -1,
                ground_level_id: int = -1,
                eye_ft: Sequence[float] = (-40.0, -40.0, 20.0),
                target_ft: Sequence[float] = (0.0, 0.0, 5.0),
                invisible_style_id: int = -1, not_silhouette_style_id: int = -1,
                scale: float = 5.0) -> ViewSpec:
    """A default (isometric-style) 3D VIEW constellation: ``DBView3d`` +
    ``Viewer3d`` + ``ModelClipBox`` + ``DBDrawing``/``Viewport`` +
    ``ExtentElem`` + ``LightSchemeElement`` + its ``SunAndShadowSettings``
    [VERIFIED constellation membership from rstbasic 1138902's deletion
    parents].

    VIEW DEFINITION (what we author): name, view family type
    (``view_type_id`` = a :func:`new_view_type` with family '3d'), the
    camera frame (derived here from ``eye_ft``/``target_ft``: view_dir
    points from the model TOWARD the eye, horz/vert form the screen frame),
    phase / phase filter parameters, scale (5.0 = the corpus 3D default,
    display '1:5.25').  GENERATED content NOT emitted: the camera-symbol
    GElement of Viewer3d and the DBView's cached graphics -- all
    SerializedDummy [see spec §views]."""
    ex, ey, ez = (float(c) for c in eye_ft)
    tx, ty, tz = (float(c) for c in target_ft)
    dx, dy, dz = ex - tx, ey - ty, ez - tz            # view_dir: model -> eye
    n = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    vdir = (dx / n, dy / n, dz / n)
    # horizontal screen axis = up x view_dir (keeps horizon level)
    hx, hy, hz = (-vdir[1], vdir[0], 0.0)
    hn = math.hypot(hx, hy) or 1.0
    hdir = (hx / hn, hy / hn, 0.0)
    # vertical screen axis = view_dir x horz_dir
    vdirv = (vdir[1] * hdir[2] - vdir[2] * hdir[1],
             vdir[2] * hdir[0] - vdir[0] * hdir[2],
             vdir[0] * hdir[1] - vdir[1] * hdir[0])
    view_id = _alloc(ids)
    viewer_id = _alloc(ids)
    clip_id = _alloc(ids)
    sun_id = _alloc(ids)
    viewport_id = _alloc(ids)
    drawing_id = _alloc(ids)
    light_id = _alloc(ids)
    extent_id = _alloc(ids)
    obj = dbview_base(view_id, name, viewer_id=viewer_id, drawing_id=drawing_id,
                      sun_settings_id=sun_id, view_type_id=view_type_id,
                      phase_id=phase_id, phase_filter_id=phase_filter_id,
                      extent_elem_id=extent_id, light_scheme_id=light_id,
                      origin=eye_ft, view_dir=vdir, horz_dir=hdir, vert_dir=vdirv,
                      scale=scale, back_clipping=-1,
                      excluded_categories=DRAW_EXCLUDED_CATEGORIES["3d"],
                      analytical_excluded=True,
                      invisible_style_id=invisible_style_id,
                      not_silhouette_style_id=not_silhouette_style_id,
                      cell_list=True, shadow_intensity=50)
    obj["m_levelsIdsForDrawingGrids"] = []
    obj["m_projectGridsOnSectionBox"] = False
    dele = [view_id, viewer_id, drawing_id, sun_id, light_id, extent_id] + [
        x for x in (view_type_id, phase_id, phase_filter_id, invisible_style_id,
                    not_silhouette_style_id) if x >= 0]
    hdr = element_header("DBView3d", category=BIC_VIEWS, deletion=dele,
                         regen_only=[clip_id] + ([view_type_id] if view_type_id >= 0 else []),
                         flags=10, visible_view_flags=-32608)
    view = SkelElement(view_id, "DBView3d", hdr, obj, None, kind="view")
    viewer = new_viewer3d(viewer_id, view_id, clip_id, orig=eye_ft,
                          basis=[list(hdir), list(vdirv), list(vdir)],
                          target=target_ft, view_type_id=view_type_id)
    clip = new_model_clip_box(clip_id, viewer_id)
    sun = new_sun_and_shadow_settings(sun_id, view_id, level_id=ground_level_id)
    viewport = new_viewport(viewport_id, view_id, drawing_id, flags=10)
    drawing = new_dbdrawing(drawing_id, [viewport_id], view_id, flags=8202)
    light = new_light_scheme(light_id, view_id)
    extent = new_extent_elem(extent_id, view_id, (-vdir[0], -vdir[1], -vdir[2]))
    return ViewSpec(view, [viewer, clip, sun, viewport, drawing, light, extent])


def new_plan_view(ids: IdSource, name: str, level_id: int, level_elevation_ft: float,
                  view_type_id: int, *, phase_id: int = -1, phase_filter_id: int = -1,
                  level_below_id: int = -1, level_below_elevation_ft: float = 0.0,
                  cut_offset_ft: float = 3.937007874015748,      # 1200 mm
                  top_offset_ft: float = 7.545931758530183,       # 2300 mm
                  invisible_style_id: int = -1, not_silhouette_style_id: int = -1,
                  scale: float = 0.01, detail_level: int = 1, discipline: int = 1
                  ) -> ViewSpec:
    """A FLOOR-PLAN view constellation for ``level_id``: ``DBViewPlan`` +
    ``Viewer`` + fixed ``SketchPlane`` (on the level datum) + ``ExtentElem``
    + ``DBDrawing``/``Viewport`` + its ``SunAndShadowSettings`` [VERIFIED
    membership from rstbasic 245443's deletion parents].

    VIEW DEFINITION: name, ``view_type_id`` (a plan-family DBViewType),
    the ASSOCIATED LEVEL (``m_genElemId`` = the Level element -- this is what
    makes it 'Level 1's plan) [VERIFIED: 245443.m_genElemId == its level],
    the view range (cut plane / top / bottom / view depth = ``PlanViewRange2``
    offsets relative to the level, feet), scale (0.01 = 1:100 [INFERRED
    from 0.01 on every metric-template plan]), phase / phase filter,
    detail level and discipline (int params -1011002 / -1005163).  The plan
    looks DOWN (view_dir +Z is the up axis stored; origin z = the cut plane
    elevation) [VERIFIED values].  GENERATED content (cached plan graphics)
    is NOT emitted."""
    z = float(level_elevation_ft)
    zb = float(level_below_elevation_ft)
    view_id = _alloc(ids)
    viewer_id = _alloc(ids)
    sketch_id = _alloc(ids)
    sun_id = _alloc(ids)
    viewport_id = _alloc(ids)
    drawing_id = _alloc(ids)
    extent_id = _alloc(ids)
    cut_z = z + float(cut_offset_ft)
    obj = dbview_base(view_id, name, viewer_id=viewer_id, drawing_id=drawing_id,
                      sun_settings_id=sun_id, view_type_id=view_type_id,
                      phase_id=phase_id, phase_filter_id=phase_filter_id,
                      extent_elem_id=extent_id, fixed_sketch_plane_id=sketch_id,
                      gen_elem_id=level_id,
                      origin=(0.0, 0.0, cut_z), view_dir=(0.0, 0.0, 1.0),
                      horz_dir=(1.0, 0.0, 0.0), vert_dir=(0.0, 1.0, 0.0),
                      scale=scale, back_clipping=0,
                      excluded_categories=DRAW_EXCLUDED_CATEGORIES["plan"],
                      int_params=[(BIP_VIEW_DETAIL_LEVEL, detail_level),
                                  (BIP_VIEW_DISCIPLINE, discipline)],
                      invisible_style_id=invisible_style_id,
                      not_silhouette_style_id=not_silhouette_style_id,
                      cell_list=True, ambient_shadows=True, shadow_intensity=10)
    # plan-specific view range machinery [VERIFIED structure vs 245443]
    obj["m_geomSteps"] = _ptr("GeomStepList", {
        "m_nonBRepGList": [_ptr("MakeCutterForPlanRegionsGStep", {
            "m_faceHistTable": [], "m_curveHistTableSet": [],
            "m_edgeHistTable": [], "m_edgeHistTableReverse": [],
            "m_id": 1, "m_version": 0, "m_flags": 1,
            "m_pElem": _weak(2), "m_oExtraDatas": None})],
        "m_bRepFormGList": [], "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [], "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [1, 1, 1, 1, 1],
        "m_idCounter": 2, "m_flags": 1})
    below = level_below_id if level_below_id >= 0 else level_id
    depth_z = (zb - 5.905511811023622) if level_below_id >= 0 else (z - 3.937007874015748)
    obj["m_pCutter"] = _ptr("GenericPlaneCutter", {
        "m_pPlane": plane((0.0, 0.0, cut_z + 3.28083989501312), (1.0, 0.0, 0.0),
                          (0.0, -1.0, 0.0), EMPTY_ENVELOPE, pid=3),
        "m_bAssignCutFaceTag": True, "m_bBackPlaneCut": False})
    obj["m_pPlanViewRange"] = _ptr("PlanViewRange", {
        "m_offsets": [0.0, 0.0, 0.0, 0.0, 0.0], "m_levelPos": [0, 0, 0, 0, 0]})
    obj["m_pPlanViewRange2"] = _ptr("PlanViewRange2", {
        "m_viewDepthPlaneOffsets": [float(top_offset_ft), float(cut_offset_ft),
                                    0.0, 0.0, 0.0],
        "m_viewDepthPlaneLevelIds": [int(level_id), int(level_id), int(level_id),
                                     int(below), -1]})
    obj["m_pViewDepthCutter"] = _ptr("GenericPlaneCutter", {
        "m_pPlane": plane((0.0, 0.0, depth_z), (1.0, 0.0, 0.0),
                          (-0.0, 1.0, -0.0), EMPTY_ENVELOPE, pid=4),
        "m_bAssignCutFaceTag": True, "m_bBackPlaneCut": True})
    obj["m_planRegionIds"] = []
    obj["m_bottomClipElev"] = depth_z
    obj["m_columnSymbolElev"] = 1.0
    obj["m_cutPlaneElev"] = cut_z
    obj["m_levelBelowElev"] = depth_z if level_below_id >= 0 else zb
    obj["m_topClipElev"] = z + float(top_offset_ft)
    obj["m_underlayBottom"] = 999999999.9999999
    obj["m_underlayTop"] = -999999999.9999999
    obj["m_idUnderlayLevel"] = -1
    obj["m_idUnderlayTopLevel"] = -1
    obj["m_joinCleanType"] = 0
    obj["m_planViewType"] = 1
    obj["m_underlayOrientation"] = 0
    obj["m_bUseTrueNorth"] = False
    obj["m_underlayIsAbsolute"] = True
    dele = [view_id, viewer_id, sketch_id, sun_id, drawing_id, extent_id, level_id] + [
        x for x in (view_type_id, phase_id, phase_filter_id, level_below_id,
                    invisible_style_id, not_silhouette_style_id) if x >= 0]
    hdr = element_header("DBViewPlan", category=BIC_VIEWS, deletion=dele,
                         appearance=[view_type_id] if view_type_id >= 0 else [],
                         flags=10, visible_view_flags=-32608)
    view = SkelElement(view_id, "DBViewPlan", hdr, obj, None, kind="view")
    viewer = new_viewer(viewer_id, view_id, orig=(0.0, 0.0, z), with_gstep=True,
                        appearance=[view_type_id] if view_type_id >= 0 else [],
                        regen_only=[view_type_id] if view_type_id >= 0 else [],
                        flags=10)
    sketch = new_sketch_plane(sketch_id, view_id, datum_id=view_id,
                              elevation_ft=z, regen_level_id=level_id)
    sun = new_sun_and_shadow_settings(sun_id, view_id, level_id=-1)
    viewport = new_viewport(viewport_id, view_id, drawing_id, flags=10)
    drawing = new_dbdrawing(drawing_id, [viewport_id], view_id, flags=8202)
    extent = new_extent_elem(extent_id, view_id, (0.0, 0.0, -1.0))
    return ViewSpec(view, [viewer, sketch, sun, viewport, drawing, extent])


def new_document_sun_settings(elem_id: int, **kw) -> SkelElement:
    """The document-wide (view-less) ``SunAndShadowSettings`` the project
    view's ViewDisplayMgr references (ancestral id 54520; owner view -1)
    [VERIFIED: DBViewProject.m_pViewDisplayMgr.m_lights.m_sunAndShadowSettingsId
    == 54520 in all three templates]."""
    return new_sun_and_shadow_settings(elem_id, view_id=-1, **kw)


# ---------------------------------------------------------------------------
# THE MINIMAL GLOBAL/* TABLE STREAMS (models for rvt.stream_encoders)
# ---------------------------------------------------------------------------

REVIT_2026_FORMAT_VERSION = 2662      # History upgrade list terminator (Revit 2026)
REVIT_2026_BUILD = "20250227_1515(x64)"


def minimal_history(document_guid: str, episode_guid: str,
                    format_versions: Optional[Sequence[int]] = None) -> Dict[str, Any]:
    """``Global/History`` model for ONE save episode (episode 0).

    Layout [VERIFIED 6/6]: header GUID slots (G, G, G, ZERO, G) = the
    document lineage GUID (constant for the file's life, NOT an episode);
    ``format_versions`` = the ascending format-upgrade list ending at 2662
    (Revit 2026) -- corpus files carry ~185 historic entries because they
    descend from ancient templates; a genesis document was BORN as 2026 so
    it carries just ``[2662]`` [INFERRED]; ``entries`` newest-first =
    [(episode_guid, 0x28)] and entry[0] must equal BasicFileInfo's Unique
    Document GUID [VERIFIED 6/6].
    """
    zero = "00000000-0000-0000-0000-000000000000"
    fv = sorted(set(int(v) for v in (format_versions or [REVIT_2026_FORMAT_VERSION])))
    return {
        "stream": "History",
        "class_tag": 0x0538,
        "version": 1,
        "pad10": "00" * 10,
        "hdr_count": 1,
        "pad_u32": 0,
        "header_guids": [document_guid, document_guid, document_guid, zero, document_guid],
        "format_versions": fv,
        "entries": [(episode_guid, 0x28)],
        "trailing": "00000000",
    }


def minimal_increment_table(username: str, element_record_count: int, *,
                            timestamp: Optional[int] = None,
                            counters: Optional[Sequence[int]] = None,
                            counter_g: int = 1) -> Dict[str, Any]:
    """``Global/DocumentIncrementTable`` model for ONE save (episode 0).

    Invariants [VERIFIED 6/6]: newest ``id_pair`` = (History count - 1,
    History count) = (0, 1); record count = BasicFileInfo increments = 1;
    ``pairs`` = [(-1, element_record_count)] with ``elem_id_repeat`` the
    same on the newest record; ``flag`` 1 = ordinary modifying save; copy 2
    of the table identical to copy 1.  ``counters`` = 10 monotonic per-save
    counters and ``counter_g`` a companion counter [semantics UNKNOWN;
    defaults = a first save with every counter at 1 -- to be confirmed by
    a Revit open test].
    """
    ts = int(timestamp if timestamp is not None else time.time())
    ctr = list(counters) if counters is not None else [1] * 10
    if len(ctr) != 10:
        raise ValueError("DocumentIncrementTable counters must have 10 entries")
    rec = {
        "pairs": [(-1, int(element_record_count))],
        "username": str(username),
        "unknown_zero_1": 0,
        "id_pair": (0, 1),
        "unknown_zero_2": 0,
        "timestamp": ts,
        "sequence": 1,
        "elem_id_repeat": int(element_record_count),
        "counters": [int(c) for c in ctr],
        "counter_g": int(counter_g),
        "flag": 1,
    }
    return {
        "stream": "DocumentIncrementTable",
        "type_tag": 0x053C,
        "records": [rec],
        "records2": [dict(rec)],
        "trailer": "00" * 8,
    }


def minimal_partition_table(workset_guid: str, name: str = "Workset1", *,
                            id_a: int = 0, id_b: int = 0) -> Dict[str, Any]:
    """``Global/PartitionTable`` (the WORKSET table) with ONE user workset.

    [VERIFIED 6/6]: one kind-0 entry named 'Workset1' (localized in dach);
    ``guid`` = the workset-table GUID (== ``Contents.creation_guid``);
    ``id_b`` = the OLDEST DocumentIncrementTable episode id (0 for a
    genesis document); ``id_a`` semantics UNKNOWN (352/254/131 in corpus)
    -- 0 chosen.  Non-worksharing files still carry this table.
    """
    return {
        "stream": "PartitionTable",
        "class_ordinal": 0x0C80,
        "version": 1,
        "entries": [{
            "guid": workset_guid, "zero0": 0,
            "id_a": int(id_a), "id_b": int(id_b),
            "minus_one": -1, "kind": 0, "flag": 0,
            "name": str(name), "tail_words": [1, 1, 0, 1, 0]}],
        "trailing": "",
    }


def minimal_contents(workset_guid: str, counters: Optional[Sequence[int]] = None,
                     counter_g: int = 1, *, build: str = REVIT_2026_BUILD,
                     class_ref: int = 0x1C) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """``Contents`` (DocumentStorageIndex, class 0x53e): returns
    ``(prologue_model, payload_model)``.

    [VERIFIED 6/6]: ``creation_guid`` == the workset-table GUID; the 9
    ``counters`` == the newest DocumentIncrementTable counters with index
    7 REMOVED and ``counter_g`` == its ``counter_g``; ``build`` = the
    Revit build string; ``hdr5`` = (7, 0, 3, -1, 3) [4/6, dach/racbasic
    vary in slots 1-2 -- UNKNOWN meaning]; ``trailing_pairs`` = the two
    class idents (-1, 1420) / (-1, 1426) constant across the corpus
    [INFERRED: A3PartyAImage/A3PartyObject class ids of the preview
    entries; the constant is version-specific].  Prologue ``class_ref`` =
    0x1C (ADocument) [VERIFIED].
    """
    ctr = list(counters) if counters is not None else [1] * 10
    nine = ctr[:7] + ctr[8:] if len(ctr) == 10 else ctr
    prologue = {"unknown_28": 0x1C, "count": 1, "zero": 0, "class_ref": int(class_ref)}
    payload = {
        "stream": "Contents",
        "type_tag": 0x053E,
        "has_username": False, "username": None,
        "zero_a": 0, "zero_b": 0,
        "partition_name": "GLOBAL",
        "zero36": "00" * 36,
        "one": 1,
        "creation_guid": workset_guid,
        "worksharing_marker_u16": 0xFFFF,
        "zero_c": 0, "zero_d": 0,
        "build": str(build),
        "hdr5": [7, 0, 3, -1, 3],
        "one_b": 1, "zero_e": 0,
        "counters": [int(c) for c in nine],
        "counter_g": int(counter_g),
        "trailing_pairs": [(-1, 1420), (-1, 1426)],
        "tail": "00" * 28,
    }
    return prologue, payload


#: The EMPTY ``Global/ContentDocuments`` payload (inflated, before the
#: 8-byte prefix u64 = 1 and gzip framing): u16 0x3a3 (ContentMarker class)
#: + u32 count 0 + u32 0xFFFFFFFF + u32 0 = 14 bytes.  This is exactly the
#: form a 2026 family document with NO nested content carries (82 raw
#: bytes on disk) [VERIFIED: racbasicsamplefamily-2026 .rfa].  Whether a
#: PROJECT may carry zero content documents (no loaded families at all)
#: is UNKNOWN -- the R9b/R10b reductions on disk are the probes.
EMPTY_CONTENT_DOCUMENTS = bytes.fromhex("a30300000000ffffffff00000000")


def minimal_content_documents() -> bytes:
    """Inflated ``Global/ContentDocuments`` payload for a document with no
    embedded content documents (see :data:`EMPTY_CONTENT_DOCUMENTS`)."""
    return EMPTY_CONTENT_DOCUMENTS


def minimal_basic_file_info(document_guid: str, *, out_path: str = "",
                            username: str = "", author: str = "rvt-writer",
                            client_app_name: str = "rvt-writer",
                            format_year: str = "2026",
                            build: str = REVIT_2026_BUILD) -> Dict[str, Any]:
    """``BasicFileInfo`` model with OUR identity (never a template's) --
    the writer's identity policy (``rvt.identity``, TRACKER gate G2).

    [VERIFIED 6/6 invariants]: ``unique_document_guid`` ==
    ``central_episode_guid`` == History entry[0]; ``unique_document_increments``
    (a string) == ``central_version_number`` == DIT record count == 1.
    ``author``/``client_app_name`` default to OUR product placeholder --
    the reader does not gatekeep on them (V31 PASS); the version marker
    (``format`` 2026 + ``build``) stays until counsel decision C1
    [see rvt/identity.py].
    """
    import os as _os
    return {
        "stream": "BasicFileInfo",
        "structure_version": 14,
        "worksharing_state": 0,
        "worksharing_text": "Not enabled",
        "username": str(username),
        "central_model_path": "",
        "format": str(format_year),
        "build": str(build),
        "last_save_path": _os.path.basename(out_path) if out_path else "",
        "open_workset_default": 3,
        "project_spark_file": 0,
        "central_model_identity": "00000000-0000-0000-0000-000000000000",
        "locale": "ENU",
        "all_local_changes_saved_to_central": 0,
        "central_version_number": 1,
        "central_episode_guid": document_guid,
        "unique_document_guid": document_guid,
        "unique_document_increments": "1",
        "model_identity": "00000000-0000-0000-0000-000000000000",
        "is_single_user_cloud_model": False,
        "is_single_user_cloud_model_text": "False",
        "author": str(author),
        "client_app_name": str(client_app_name),
        "mirror_text": "",           # regenerated by the encoder
    }


def minimal_elemtable(elements: Sequence[SkelElement], *, episode: int = 0,
                      watermark: Optional[int] = None) -> Dict[str, Any]:
    """``Global/ElemTable`` model: one 40-byte ElemRec per element (sorted
    by id, all created/modified in ``episode``) + the id-watermark footer
    [VERIFIED layout; footer marker 0xFFFFFFFF, tail class 0x96a]."""
    recs = sorted((e.elemrec_row(episode) for e in elements), key=lambda r: r[4])
    ids = [r[4] for r in recs]
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate element ids in the skeleton")
    last = watermark if watermark is not None else (max(ids) if ids else 0)
    return {
        "stream": "ElemTable",
        "class_tag": 0x05C9,
        "records": recs,
        "graveyard_count": 0,
        "footer": {"marker": 0xFFFFFFFF, "tail_class": 0x096A, "tail_pad": 0,
                   "last_id": int(last), "tail_zero": 0},
    }


def minimal_globals(elements: Sequence[SkelElement], *,
                    document_guid: Optional[str] = None,
                    episode_guid: Optional[str] = None,
                    workset_guid: Optional[str] = None,
                    username: str = "",
                    out_path: str = "",
                    timestamp: Optional[int] = None,
                    counters: Optional[Sequence[int]] = None,
                    counter_g: int = 1) -> Dict[str, Any]:
    """Build the SIX coordinated table-stream models for a minimal document
    containing exactly ``elements`` and ONE save episode (episode 0).

    Returns ``{stream_name: model}`` for ``ElemTable``, ``History``,
    ``DocumentIncrementTable``, ``PartitionTable``, ``Contents`` (payload
    model), ``ContentsPrologue`` and ``BasicFileInfo`` -- ready for
    ``rvt.stream_encoders`` (:func:`encode_minimal_globals`).  The cross-
    stream identity invariants (KNOWLEDGE.md 'Cross-stream save
    invariants') hold by construction: History count 1 == DIT records 1 ==
    BFI increments 1; DIT id_pair (0, 1); BFI GUID == History entry[0];
    Contents counters == DIT counters minus index 7; Contents GUID ==
    workset GUID; ElemTable count == the element count.
    """
    doc_guid = document_guid or str(uuid.uuid4())
    ep_guid = episode_guid or str(uuid.uuid4())
    ws_guid = workset_guid or str(uuid.uuid4())
    et = minimal_elemtable(elements, episode=0)
    n = len(et["records"])
    dit = minimal_increment_table(username, n, timestamp=timestamp,
                                  counters=counters, counter_g=counter_g)
    prologue, contents = minimal_contents(ws_guid, dit["records"][0]["counters"],
                                          dit["records"][0]["counter_g"])
    return {
        "ElemTable": et,
        "History": minimal_history(doc_guid, ep_guid),
        "DocumentIncrementTable": dit,
        "PartitionTable": minimal_partition_table(ws_guid),
        "Contents": contents,
        "ContentsPrologue": prologue,
        "BasicFileInfo": minimal_basic_file_info(ep_guid, out_path=out_path,
                                                 username=username),
        "_ids": {"document_guid": doc_guid, "episode_guid": ep_guid,
                 "workset_guid": ws_guid},
    }


def encode_minimal_globals(models: Dict[str, Any]) -> Dict[str, bytes]:
    """Encode the models with ``rvt.stream_encoders``: returns the INFLATED
    payload bytes per stream (``Contents`` = its 24-byte prologue + gzip is
    a raw-stream concern; here the inflated payload is returned; framing /
    gzip / ECC is the assembler's job)."""
    from .. import stream_encoders as se
    return {
        "ElemTable": se.encode_elemtable(models["ElemTable"]),
        "History": se.encode_history(models["History"]),
        "DocumentIncrementTable": se.encode_increment_table(models["DocumentIncrementTable"]),
        "PartitionTable": se.encode_partition_table(models["PartitionTable"]),
        "Contents": se.encode_contents(models["Contents"]),
        "ContentsPrologue": se.encode_contents_prologue(models["ContentsPrologue"]),
        "BasicFileInfo": se.encode_basic_file_info(models["BasicFileInfo"],
                                                    regenerate_mirror=True),
        "ContentDocuments": minimal_content_documents(),
    }


# ---------------------------------------------------------------------------
# A whole minimal skeleton (the demo composition)
# ---------------------------------------------------------------------------

@dataclass
class Skeleton:
    """A composed minimal document skeleton: its elements + globals."""
    elements: List[SkelElement]
    by_kind: Dict[str, List[SkelElement]]
    globals_models: Dict[str, Any]
    ids: Dict[str, int]

    def element_ids(self) -> List[int]:
        return [e.elem_id for e in self.elements]


def build_minimal_skeleton(*, project_name: str = "GENESIS", project_number: str = "0001",
                           levels_ft: Sequence[Tuple[str, float]] = (
                               ("Level 1", 0.0), ("Level 2", 9.84251968503937)),
                           with_3d_view: bool = True, with_plan_views: bool = True,
                           username: str = "", timestamp: Optional[int] = None,
                           start_id: int = 100) -> Skeleton:
    """Compose the whole minimal skeleton: units registry, level type +
    levels, phases + AllProjectPhases + the five phase filters, project
    info, view types, the project-view constellation, one 3D view and one
    plan per level, plus the six Global table-stream models.

    This is a COMPOSITION HELPER for tests/the assembler -- it does NOT
    encode partition records (the assembler does) and it does NOT emit the
    registries owned by the types stream (categories, styles, patterns,
    materials, fonts) nor ADocument (Global/Latest).
    """
    ids = IdSource(start_id)
    els: List[SkelElement] = []
    by: Dict[str, List[SkelElement]] = {}

    def add(*xs: SkelElement) -> None:
        for x in xs:
            els.append(x)
            by.setdefault(x.kind or x.class_name, []).append(x)

    named: Dict[str, int] = {}
    units = new_units_elem(_alloc(ids))
    named["units"] = units.elem_id
    add(units)
    ltype = new_level_type(_alloc(ids), "Level Head")
    add(ltype)
    level_els: List[SkelElement] = []
    for nm, elev in levels_ft:
        lv = new_level(_alloc(ids), nm, float(elev), ltype.elem_id,
                       units_id=units.elem_id)
        level_els.append(lv)
        add(lv)
    ph_existing = new_phase(_alloc(ids), "Existing")
    ph_new = new_phase(_alloc(ids), "New Construction")
    add(ph_existing, ph_new)
    allph = new_all_project_phases(_alloc(ids), [ph_existing.elem_id, ph_new.elem_id])
    # fix each phase's regenOnly to point at the real AllProjectPhases id
    for p in (ph_existing, ph_new):
        p.header["m_parents"]["value"]["m_regenOnly"] = [allph.elem_id]
    add(allph)
    filters = default_phase_filters(ids)
    add(*filters)
    show_all = next(f for f in filters if f.obj["m_bDefault"]).elem_id
    add(new_project_info(_alloc(ids), project_name=project_name,
                         project_number=project_number))
    doc_sun = new_document_sun_settings(_alloc(ids))
    add(doc_sun)
    proj_view = new_project_view(ids, phase_id=ph_new.elem_id, phase_filter_id=show_all,
                                 sun_settings_id=doc_sun.elem_id)
    add(*proj_view.elements())
    if with_3d_view:
        vt3d = new_view_type(_alloc(ids), "3D View", "3d")
        add(vt3d)
        v3 = new_3d_view(ids, "{3D}", vt3d.elem_id, phase_id=ph_new.elem_id,
                         phase_filter_id=show_all,
                         ground_level_id=level_els[0].elem_id)
        add(*v3.elements())
        named["view3d"] = v3.view.elem_id
    if with_plan_views:
        vtp = new_view_type(_alloc(ids), "Floor Plan", "floor_plan")
        add(vtp)
        for i, lv in enumerate(level_els):
            below = level_els[i - 1] if i > 0 else None
            pv = new_plan_view(ids, level_els[i].obj["m_text"], lv.elem_id,
                               lv.obj["m_pSurface"]["value"]["m_origin"][2],
                               vtp.elem_id, phase_id=ph_new.elem_id,
                               phase_filter_id=show_all,
                               level_below_id=below.elem_id if below else -1,
                               level_below_elevation_ft=(
                                   below.obj["m_pSurface"]["value"]["m_origin"][2]
                                   if below else 0.0))
            add(*pv.elements())
    gm = minimal_globals(els, username=username, timestamp=timestamp)
    return Skeleton(els, by, gm, {"watermark": ids.watermark, **named})


# ---------------------------------------------------------------------------
# demo / __main__
# ---------------------------------------------------------------------------

def roundtrip_report(elements: Sequence[SkelElement]) -> Dict[str, Any]:
    """Encode every record with the schema encoder, decode it back, compare
    (schema-validity + reversibility proof for constructed objects)."""
    ok = fail = 0
    bad: List[str] = []
    total_bytes = 0
    for e in elements:
        rep = e.roundtrip()
        for seq in (101, 102, 103):
            r = rep[seq]
            total_bytes += r["bytes"]
            if r["clean"] and r["byte_exact"] and r["value_equal"]:
                ok += 1
            else:
                fail += 1
                bad.append(f"{e.class_name}#{e.elem_id} seq{seq} ({r['class']}) "
                           f"clean={r['clean']} exact={r['byte_exact']} "
                           f"equal={r['value_equal']} {r['errors'][:1]}")
    return {"records": ok + fail, "roundtrip_ok": ok, "failed": fail,
            "encoded_bytes": total_bytes, "failures": bad}


def main(argv=None):
    sk = build_minimal_skeleton(timestamp=0)
    print(f"GENESIS skeleton: {len(sk.elements)} elements, watermark {sk.ids['watermark']}")
    for k, v in sk.by_kind.items():
        print(f"  {k:16s} {len(v):3d}  ({', '.join(sorted({e.class_name for e in v}))})")
    rep = roundtrip_report(sk.elements)
    print(f"encode->decode round-trip: {rep['roundtrip_ok']}/{rep['records']} records, "
          f"{rep['encoded_bytes']:,} object bytes, failures={rep['failed']}")
    for b in rep["failures"][:10]:
        print("   FAIL", b)
    enc = encode_minimal_globals(sk.globals_models)
    print("Global streams (inflated payload bytes):")
    for k, v in enc.items():
        print(f"  {k:24s} {len(v):6d} B")
    return 0 if rep["failed"] == 0 else 1


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main(sys.argv[1:]))

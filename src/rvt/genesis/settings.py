"""genesis/settings.py -- constructors for the DOCUMENT-SETTINGS SINGLETONS,
the settings CONSTELLATIONS (project browser, keynoting, revisions) and the
SYSTEM VIEW-FAMILY TABLE that a real Revit project carries beyond its
element types -- the "Bug A / K5" candidates our constructed base lacked.

Why this module exists (the reader's own diagnosis, 2026-08-03): every
constructed genesis base (G0, G1_candidate, G1a, G1b) is validator-VALID yet
Autodesk's own reader rejects it with ``Revit-DocumentCorruption: The file is
corrupt`` (the extractor crashes at open time), while sample reductions that
KEEP the document-settings skeleton pass.  The K-ladder (docs/inbox/
genesis-triage-a.md, experiments/genesis/triage/K5*.rvt) bisects WHICH
settings the reader requires; this module PRE-BUILDS our constructors for
every class the ladder can name, so a K5x FAIL never waits on a cold start:

  K5a  the real project pen table ............... :func:`pen_width_table`
  K5b  the project-browser constellation ....... :func:`default_browser_organizations`,
       (BrowserOrganization x N + the system-      :func:`browser_organization`,
       navigator view + the two browser settings) :func:`system_navigator`,
                                                   :func:`reconcile_browser_settings`,
                                                   :func:`construction_set_project`
  K5c  the MEP / structural settings singletons  :func:`struct_settings`,
                                                   :func:`wire_settings` / :func:`wire_sizes`,
                                                   :func:`duct_settings` / :func:`duct_sizes`,
                                                   :func:`pipe_settings` / :func:`pipe_sizes`,
                                                   :func:`conduit_settings`, :func:`cable_tray_settings`
                                                   + the analysis / fabrication set
  K5d  the remaining UniqueElement singletons ... :func:`wall_join_default_setting`,
                                                   :func:`auto_join_tracker`, :func:`keynote_table`,
                                                   :func:`initial_view_settings`, revisions,
                                                   export / worksharing / area settings and
                                                   the 12 EMPTY TRACKERS (:func:`tracker`)
  --   the 19 REAL PROJECT view types .......... :func:`system_view_type_table`

STANDARD (identical to ``rvt.genesis.types`` / ``rvt.genesis.skeleton``): every
constructor takes PLAIN PARAMETERS and builds its object FIELD BY FIELD over a
schema-directed blank (:func:`rvt.genesis.types.blank_object` = the archive
class map ``Formats/Latest``); nothing is cloned from any Autodesk file.  The
field layouts were derived by decoding the six 2026 sample specimens and are
PROVEN by parametric reproduction (feed a specimen's own parameter values in,
require the encoded object to equal the specimen -- ``tests/
test_genesis_settings.py``).  Every DEFAULT value is either OURS (our house
line-weight / drafting / MEP-routing standard, documented per constant), a
published fact (NEC / ISO / SMACNA), a schema sentinel (-1 / [] / null) or a
REQUIRED FORMAT TOKEN the reader keys on (the browser organizations' name
``all``, the keynote table name ``Standard``, the project view's ``???``).
Where the samples carry Autodesk PRODUCT DEFAULTS (their pen widths, keynote
database, energy constructions, rebar abbreviations) OUR value replaces it and
the docstring says so.

Registry knowledge for the ADocument (``Global/Latest``): each singleton is
INDEXED by the document object -- most through the positional
``UniqueElementsTracking.m_elemIds`` table, the rest through a named AppInfo
registry.  :data:`ADOC_REGISTRY` records the surface per class so the S-ladder
composer (``experiments/genesis/singletons/build_ladder.py``) repopulates the
document object over exactly the elements we add.

Territory: this module + ``rvt.genesis.catalog`` (the built-in-category
graphic-style catalog).  It IMPORTS the proven layers (types / skeleton /
encode) and edits none of them.

Demo / self-test::

    python -m rvt.genesis.settings          # build + round-trip every kind
"""
from __future__ import annotations

import collections
import json
import math
import sys
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .types import (
    TypeRecord, IdArg, IdSource, INVALID, NO_DESIGN_OPTION, NULL_GUID,
    LINEPATTERN_SOLID, blank_object, element_defaults, symbol_defaults,
    element_header, class_id, mm, inches, rgb, _record, _alloc, _owned, _ptr,
)
from . import skeleton as sk

# ---------------------------------------------------------------------------
# unit helpers & format constants
# ---------------------------------------------------------------------------

MM_PER_FT = 304.8
IN_PER_FT = 12.0

#: BuiltInParameter ids the project-browser organizations key on
#: (Autodesk's fixed public API enum -- interoperability constants; the
#: parameter *choice* per organization below is OUR browser scheme).
#: [VERIFIED as the folder / sort / filter parameter paths of the 2026
#: samples' BrowserOrganization elements; names per the public API enum.]
BIP_VIEW_FAMILY_AND_TYPE = -1012106     # views folder: 'Family and Type'
BIP_VIEW_NAME = -1005112                # view sort key: view name
BIP_VIEW_PHASE = -1012102               # views folder: phase
BIP_VIEW_DISCIPLINE = -1005163          # views folder: discipline
BIP_VIEWPORT_SHEET_NUMBER = -1005207    # 'Sheet Number' of a view (filter "not on sheets")
BIP_VIEW_ASSOCIATED_LEVEL = -1005113    # views folder: associated level [ASSUMED enum id]
BIP_SHEET_NUMBER = -1007401             # sheets sort / folder: sheet number
BIP_SHEET_NAME = -1007400               # sheets folder: sheet name
BIP_SHEET_ISSUE_DATE = -1006322         # sheets folder: issue date
BIP_SHEET_DRAWN_BY = -1007404           # sheets folder: drawn by

#: BrowserOrganization.m_type codes = which project-browser TREE the
#: organization applies to [VERIFIED 0 = views / 1 = sheets in three
#: samples: the folder / sort parameters are view- vs sheet-parameters; 3 and
#: 4 = the two later browser tabs whose "all" defaults appear at the same
#: (late) episode in every sample: 3 sorts by view name = SCHEDULES
#: [INFERRED], 4 has no sort parameter = the FAMILIES tab [INFERRED]].
BROWSER_ORG_VIEWS = 0
BROWSER_ORG_SHEETS = 1
BROWSER_ORG_SCHEDULES = 3
BROWSER_ORG_TYPE4 = 4
#: BrowserFilter.m_relation codes (0 = equals, 1 = not-equals) [VERIFIED
#: rme 'Simple' (equals) vs 'Advanced' (not-equals) organizations]
FILTER_EQUALS = 0
FILTER_NOT_EQUALS = 1

#: line-weight count of a pen table: Revit exposes exactly 16 pens (a
#: format constant -- the Line Weights dialog's fixed 1..16 rows).
PEN_COUNT = 16

# per-class ElementHeader constants (m_abFlags4Bytes, m_nVisibleViewFlags)
# [VERIFIED across rst/rme/rac 2026: the value the settings elements carry
# in the reader-accepted files; where two "eras" exist (a template-birth
# value with bit 0x800/0x2000 and a plain user-created 10/26/30) we use the
# value the FRESHLY-CREATED specimens carry, as our elements are created in
# the genesis save].
_HDR: Dict[str, Tuple[int, int]] = {
    "PenWidthTableElem": (8222, -32768),
    "BrowserOrganization": (10, -32640),
    "RbsDbViewSystemNavigator": (2074, -32768),
    "StructSettingsElem": (8222, -32768),
    "WallJoinDefaultSetting": (26, -32768),
    "AutoJoinTracker": (26, -32768),
    "KeynoteTable": (67117086, -32768),
    "KeynotingSystem": (8222, -32768),
    "InitialViewSettings": (8202, -32768),
    "ReconcileBrowserSettingsElem": (8206, -32768),
    "ConstructionSetProject": (30, -32768),
    "RbsWireSettingsElem": (8222, -32768),
    "RbsWireSizesElem": (8222, -32768),
    "RbsPipeSettingsElem": (30, -32768),
    "RbsPipeSizesElem": (8222, -32768),
    "RbsDuctSettingsElem": (30, -32768),
    "RbsDuctSizesElem": (8222, -32768),
    "ConduitSettingsElem": (8206, -32768),
    "CableTraySettingsElem": (8206, -32768),
    "AutoCamSettingsElem": (8218, -32768),
    "HalftoneUnderlaySettings": (8206, -32768),
    "MultipleValuesIndicationSettings": (8206, -32768),
    "DaylightSourceIdSet": (8218, -32768),
    "ExternalParamLock": (8218, -32768),
    "AllProjectRevisions": (30, -32768),
    "ProjectRevision": (30, -32736),
    "RevisionNumberingSequence": (8206, -32768),
    "WorksetVisibilitySettingsElem": (8202, -32768),
    "WorksharingViewModeSettings": (8206, -32768),
    "CoordinateSystemDisplayElem": (58, -4225),
    "ActiveGeoLocationTrackingElement": (10, -32768),
    "DefaultDivideSettings": (8206, -32768),
    "ProjectCopySettingsElem": (8206, -32768),
    "CopyWatchProperties": (8202, -32768),
    "Dwg2dExportUserSettingsData": (8218, -32768),
    "STEPExportSettings": (8202, -32768),
    "ModelGraphicsStyle": (8218, -32768),
    "GCSTracker": (26, -32768),
    "AssemblyTracker": (10, -32768),
    "LayoutNodesTracker": (10, -32768),
    "MEPSystemTracker": (10, -32768),
    "MEPComponentTracker": (10, -32768),
    "MEPNetworkTracker": (10, -32768),
    "KeynoteTagsOnSheetsTracker": (14, -32768),
    "RevisionCloudsOnSheetsTracker": (10, -32768),
    "SheetsInSheetCollectionTracker": (10, -32768),
    "AnalyticalToPhysicalRelationManager": (8202, -32768),
    "ReactionsUpToDateElem": (8218, -32768),
    "AreaSettingsElem": (30, -32768),
    "AreaMeasureElem": (8222, -32768),
    "EnergyDataSettings": (14, -32768),
    "ZoneScheme": (8218, -32768),
    "ReinforcementSettings": (8206, -32768),
    "RouteAnalysisSettings": (8206, -32768),
    "MEPHiddenLineSettingsElem": (8206, -32768),
    "FabricationSettings": (8202, -32768),
    "FabricationServiceSettings": (8202, -32768),
    "FabricationSettingsElement": (8202, -32768),
    "CircuitNamingTypeSetting": (8206, -32768),
    "SSEPointVisibilitySettings": (8202, -32768),
    "StructuralConnectionSettings": (8206, -32768),
    "RvtLinkInstanceAppearanceParentElem": (8202, -32768),
    "SketchGridAppearanceParentElem": (8202, -32768),
    "CurtaSystemFaceManager": (10, -4225),
    "PrintSettings": (8206, -32768),
    "ViewSheetSet": (8202, -32768),
    "GraphicsCache": (8202, -32768),
    "MEPNetworkDataElem": (10, -32768),
    "MEPAnalyticalModelSettings": (8202, -32768),
    "DBViewType": (10, -32768),
    "Viewer": (2074, -129),
    "DBDrawing": (2074, -32768),
    "Viewport": (2074, -129),
}
_HDR_DEFAULT = (10, -32768)


def _hdr(class_name: str) -> Tuple[int, int]:
    return _HDR.get(class_name, _HDR_DEFAULT)


def _cell_list_pattern_helper() -> dict:
    """The ``CellList{PatternHelper}`` most template-era settings elements
    carry (an empty pattern-position helper); the freshly-created specimens
    carry ``None`` instead -- both open.  Constructors take ``cell_list``:
    None = null, True = this helper."""
    return _ptr("CellList", {"m_cells": [
        _ptr("PatternHelper", {"m_PatternPositionMap": [],
                                 "m_substituteFaceMap": []})]})


#: seq-101 ``ElementHeader.m_parents.m_regenWildcards`` per settings class =
#: the CLASSES whose creation / change re-runs the singleton (a compiled-in
#: regeneration subscription; identical in every 2026 sample, so a
#: per-class FORMAT CONSTANT, not sample expression) [VERIFIED 3/3
#: rst / rme / rac, specimen order preserved].
REGEN_WILDCARDS: Dict[str, List[str]] = {
    "WallJoinDefaultSetting": ["BasicWallType"],
    "AutoJoinTracker": ["CeilingAndFloor", "FamilyInstance", "Element"],
    "GCSTracker": ["FamilyInstance", "Grid", "ReferencePoint"],
    "KeynoteTagsOnSheetsTracker": ["KeynoteTag"],
    "MEPSystemTracker": ["RbsCurve", "MechanicalEquipmentSet", "FamilyInstance",
                         "RbsSystem", "RbsSystemType"],
    "MEPComponentTracker": ["RbsCurve", "FabricationPart", "LayoutNode",
                            "FamilyInstance"],
    "MEPNetworkTracker": ["FabricationPart", "FamilyInstance", "Element"],
    "RevisionCloudsOnSheetsTracker": ["RevisionCloud"],
    "SheetsInSheetCollectionTracker": ["DBViewDrafting", "SheetCollection"],
    "AssemblyTracker": ["AssemblyInstance", "AssemblyType", "DBView"],
    "LayoutNodesTracker": ["Element"],
    "AllProjectRevisions": ["RevisionNumberingSequence"],
    "ProjectRevision": ["AllProjectRevisions"],
    "AreaSettingsElem": ["DBViewPlan", "DBViewSection"],
}


def _settings_record(class_name: str, kind: str, eid: int, obj: dict, *,
                     category: int = INVALID,
                     deletion_ids: Iterable[int] = (),
                     appearance_ids: Iterable[int] = (),
                     regen_only: Iterable[int] = (),
                     wildcards: Optional[Sequence[str]] = None,
                     rep: Optional[dict] = None,
                     refs: Optional[dict] = None,
                     notes: Optional[list] = None,
                     hdr: Optional[Tuple[int, int]] = None) -> TypeRecord:
    """Wrap a finished object in a TypeRecord with the class's header
    constants (the shared ``_record`` machinery of the types stream) plus the
    class's regeneration subscription (:data:`REGEN_WILDCARDS`) and any
    ``regen_only`` element edges."""
    ab, vis = hdr or _hdr(class_name)
    h = element_header(class_name, category, eid, deletion_ids=deletion_ids,
                       appearance_ids=appearance_ids, ab_flags=ab,
                       visible_flags=vis)
    par = h["m_parents"]["value"]
    wc = list(REGEN_WILDCARDS.get(class_name, []) if wildcards is None else wildcards)
    par["m_regenWildcards"] = [{"m_ref": {"classref": str(c)}} for c in wc]
    par["m_regenOnly"] = sorted({int(x) for x in regen_only if x not in (None, INVALID)})
    return TypeRecord(eid, kind, class_name, class_id(class_name), category,
                      obj, h, rep, refs or {}, notes or [])


def _element(class_name: str, eid: int, *, cell_list: bool = False,
             double_params=None, int_params=None, astring_params=None,
             elemid_params=None) -> dict:
    """A blanked object of ``class_name`` with the universal Element base
    filled (the document-settings elements are ownerless singletons: assoc
    level / family / phases / design option all -1)."""
    obj = blank_object(class_name)
    element_defaults(obj, eid, double_params=double_params, int_params=int_params,
                     astring_params=astring_params, elemid_params=elemid_params)
    obj["m_cellList"] = _cell_list_pattern_helper() if cell_list else None
    return obj


def _generic(class_name: str, kind: str, ids: IdArg, elem_id: Optional[int],
             overlay: Optional[dict] = None, *, cell_list: bool = False,
             category: int = INVALID, deletion_ids: Iterable[int] = (),
             regen_only: Iterable[int] = (),
             wildcards: Optional[Sequence[str]] = None,
             refs: Optional[dict] = None, notes: Optional[list] = None,
             astring_params=None) -> TypeRecord:
    """The DATA-DRIVEN singleton constructor: blank the class, apply the
    universal base, overlay the caller's field values, wrap in a record.
    Used by every small settings singleton and every empty TRACKER (whose
    whole content is empty containers = pure machinery, no free choice)."""
    eid = _alloc(ids, elem_id)
    obj = _element(class_name, eid, cell_list=cell_list,
                   astring_params=astring_params)
    if overlay:
        obj.update(overlay)
    return _settings_record(class_name, kind, eid, obj, category=category,
                            deletion_ids=deletion_ids, regen_only=regen_only,
                            wildcards=wildcards, refs=refs, notes=notes)


# ===========================================================================
# 1. THE PEN TABLE  (PenWidthTableElem -- element id 2 in every sample)
# ===========================================================================
#: OUR line-weight standard (millimetres, plotted width per pen 1..16 at
#: the finest scale breakpoint).  Pens 1..9 = the ISO 128 / DIN 15
#: preferred line-width series (a documented FACT: 0.13, 0.18, 0.25, 0.35,
#: 0.5, 0.7, 1.0, 1.4, 2.0 mm, geometric ratio sqrt(2)); pens 10..16 = OUR
#: coarse extension for poche / graphic emphasis.  Autodesk's default
#: table (0.18 ... 9.0 mm, three repeated 9.0 pens) is NOT reproduced.
PEN_WIDTHS_MM: List[float] = [
    0.13, 0.18, 0.25, 0.35, 0.50, 0.70, 1.00, 1.40, 2.00,      # ISO 128
    2.50, 3.00, 4.00, 5.00, 6.00, 7.00, 8.00,                  # our coarse set
]
#: THE PROJECT PEN TABLE'S SCALE BREAKPOINTS ARE A PER-RELEASE FORMAT
#: CONSTANT, not a design choice: EVERY 2026 sample's project pen table
#: (m_famId -1, id 2) carries exactly these six view-scale denominators
#: (10, 20, 50, 100, 200, 500) regardless of the file's unit system
#: (imperial rme / rac included), and 2,610 of the 3,488 family-scoped
#: tables agree [VERIFIED, six-sample census 2026-08-03; the fixer's
#: field-diff record docs/inbox/genesis-fixer.md].  Our earlier "imperial
#: architectural ladder" (24 ... 768) put a scale (768) NO specimen of the
#: 3,494 corpus pen tables carries into the reader-audited table.  The
#: breakpoints are the Line Weights dialog's fixed model-pen columns
#: (interface constants, like the 16-pen count); the WIDTHS in the columns
#: stay OURS (ISO 128).  Coarser scales -> finer minimum pens (our rule:
#: each coarser breakpoint prepends one hairline and drops the widest).
PEN_SCALE_BREAKPOINTS: List[int] = [10, 20, 50, 100, 200, 500]
#: the finest / coarsest inverted scale a project pen table carries (the
#: observed column set is exactly PEN_SCALE_BREAKPOINTS)
PEN_SCALE_SET = frozenset(PEN_SCALE_BREAKPOINTS)


def pen_series_mm(shift: int = 0, base: Sequence[float] = tuple(PEN_WIDTHS_MM)) -> List[float]:
    """OUR pen vector for the ``shift``-th coarser scale breakpoint: prepend
    ``shift`` hairlines (the finest width) and truncate to 16 -- so coarse
    (small-scale) drawings plot thinner, as any line-weight standard does."""
    b = list(base)
    if len(b) != PEN_COUNT:
        raise ValueError(f"a pen vector has exactly {PEN_COUNT} widths")
    finest = b[0]
    return ([finest] * shift + b)[:PEN_COUNT]


def default_model_pens_mm(scales: Sequence[int] = tuple(PEN_SCALE_BREAKPOINTS),
                          base: Sequence[float] = tuple(PEN_WIDTHS_MM)) -> Dict[int, List[float]]:
    """{scale-denominator: [16 widths mm]} for OUR breakpoints, finest scale
    (smallest denominator) = the full series, each coarser step shifted."""
    return {int(s): pen_series_mm(i, base) for i, s in enumerate(sorted(scales))}


def _pen_info(scale: int, widths_mm: Sequence[float]) -> dict:
    if len(widths_mm) != PEN_COUNT:
        raise ValueError(f"pen vector for scale {scale} must have {PEN_COUNT} widths")
    return {"m_invertedScale": int(scale),
            "m_pens": [float(w) / MM_PER_FT for w in widths_mm]}


def _pen_info_ft(scale: int, widths_ft: Sequence[float]) -> dict:
    """A pen vector given directly in Revit's stored unit (feet) -- the
    exact-value path (Autodesk's stored doubles are NOT all reachable
    through mm / 304.8; see the controls stream's P1)."""
    if len(widths_ft) != PEN_COUNT:
        raise ValueError(f"pen vector for scale {scale} must have {PEN_COUNT} widths")
    return {"m_invertedScale": int(scale), "m_pens": [float(w) for w in widths_ft]}


def pen_width_table(*, ids: IdArg = None, elem_id: int = None,
                    model_pens_mm: Optional[Dict[int, Sequence[float]]] = None,
                    perspective_pens_mm: Optional[Sequence[float]] = None,
                    annotation_pens_mm: Optional[Sequence[float]] = None,
                    model_pens_ft: Optional[Dict[int, Sequence[float]]] = None,
                    perspective_pens_ft: Optional[Sequence[float]] = None,
                    annotation_pens_ft: Optional[Sequence[float]] = None,
                    family_id: int = INVALID) -> TypeRecord:
    """The document's ``PenWidthTableElem`` = the Line Weights table
    (model line weights per view scale + perspective + annotation weights).

    DEFINITION = ``m_pPenWidthTable`` -> ``PenWidthTable`` {
    ``m_modelPenInfo`` = one ``PenInfoForScale{m_invertedScale, m_pens[16]
    (feet)}`` per scale breakpoint (ascending denominator);
    ``m_perspectiveModelPenInfo`` and ``m_draftPenInfo`` = single scale-
    independent 16-pen vectors (``m_invertedScale`` -1)}.  16 pens and the
    six model scale breakpoints (:data:`PEN_SCALE_BREAKPOINTS`) are format
    constants.  ``model_pens_mm`` = {scale-denominator: [16 mm]} (default
    = the format's breakpoints / OUR ISO-128 series); perspective /
    annotation vectors default to our base series.  ``*_pens_ft`` are the
    same vectors given DIRECTLY IN FEET (the stored unit) and take
    precedence -- the exact-value probe path.

    The REAL project pen table has ``m_famId`` -1 (the samples also carry 8
    family-scoped copies owned by the curtain SYSTEM families -- not needed:
    the project table is element id 2 in every 2026 file).  [VERIFIED
    structure byte-exact vs rstbasic id 2 / rme id 2, all six scales.]
    """
    eid = _alloc(ids, elem_id)
    model = model_pens_mm if model_pens_mm is not None else default_model_pens_mm()
    persp = list(perspective_pens_mm) if perspective_pens_mm is not None else pen_series_mm(0)
    draft = list(annotation_pens_mm) if annotation_pens_mm is not None else pen_series_mm(0)
    obj = _element("PenWidthTableElem", eid, cell_list=False)
    obj["m_famId"] = int(family_id)
    if model_pens_ft is not None:
        model_info = [_pen_info_ft(s, w) for s, w in sorted(model_pens_ft.items())]
        model = dict(model_pens_ft)
    else:
        model_info = [_pen_info(s, w) for s, w in sorted(model.items())]
    persp_info = (_pen_info_ft(-1, list(perspective_pens_ft))
                  if perspective_pens_ft is not None else _pen_info(-1, persp))
    draft_info = (_pen_info_ft(-1, list(annotation_pens_ft))
                  if annotation_pens_ft is not None else _pen_info(-1, draft))
    table = {
        "m_modelPenInfo": model_info,
        "m_perspectiveModelPenInfo": persp_info,
        "m_draftPenInfo": draft_info,
    }
    obj["m_pPenWidthTable"] = _ptr("PenWidthTable", table)
    return _settings_record(
        "PenWidthTableElem", "pen-table", eid, obj,
        refs={"scales": sorted(int(s) for s in model)},
        notes=[f"{len(model)} model scale breakpoints, 16 pens each; "
               "perspective + annotation vectors scale-independent (-1); "
               "widths = OUR ISO-128-based line-weight standard (mm/304.8 ft)"])


#: the pen-WIDTH range every corpus pen table stays inside (mm): 0.025
#: (a dach family table) .. 200 (dach's exaggerated poche pens); the six
#: PROJECT tables span 0.053 .. 10.0.  Our ISO-128 series (0.13 .. 8.0)
#: sits well inside both [VERIFIED, six-sample census].
PEN_WIDTH_MM_RANGE = (0.025, 200.0)
PEN_WIDTH_MM_PROJECT_RANGE = (0.05, 10.0)


def lint_pen_width_table(rec: "TypeRecord") -> dict:
    """The fixer's specimen LINT for a project ``PenWidthTableElem``: the
    invariants EVERY reader-accepted 2026 project pen table satisfies --
    the six model scale breakpoints are exactly :data:`PEN_SCALE_SET`
    (ascending), every vector has :data:`PEN_COUNT` monotone widths inside
    the corpus width range, the perspective / annotation vectors are the
    scale-independent (-1) form, ``m_famId`` -1, no CellList, header
    category / family -1.  Returns {'hard': [...], 'ok': bool}."""
    hard: List[dict] = []
    v = rec.obj

    def bad(field, ours, want):
        hard.append({"field": field, "ours": ours, "expected": want})
    if int(v.get("m_famId", 0)) != INVALID:
        bad("m_famId", v.get("m_famId"), INVALID)
    if v.get("m_cellList") is not None:
        bad("m_cellList", "present", None)
    t = ((v.get("m_pPenWidthTable") or {}).get("value") or {})
    if (v.get("m_pPenWidthTable") or {}).get("ptr_class") != "PenWidthTable":
        bad("m_pPenWidthTable.ptr_class",
            (v.get("m_pPenWidthTable") or {}).get("ptr_class"), "PenWidthTable")
    model = t.get("m_modelPenInfo") or []
    scales = [pi.get("m_invertedScale") for pi in model]
    if set(scales) != set(PEN_SCALE_SET):
        bad("m_modelPenInfo[].m_invertedScale (set)", scales, sorted(PEN_SCALE_SET))
    if scales != sorted(scales):
        bad("m_modelPenInfo order", scales, "ascending")
    lo, hi = PEN_WIDTH_MM_RANGE
    for pi in model + [t.get("m_perspectiveModelPenInfo") or {},
                       t.get("m_draftPenInfo") or {}]:
        pens = list(pi.get("m_pens") or [])
        tag = f"pens(scale {pi.get('m_invertedScale')})"
        if len(pens) != PEN_COUNT:
            bad(tag + ".count", len(pens), PEN_COUNT)
            continue
        mm_vals = [round(float(x) * MM_PER_FT, 4) for x in pens]
        if any(not (lo <= w <= hi) for w in mm_vals):
            bad(tag + ".range_mm", mm_vals, [lo, hi])
        if any(a > b + 1e-9 for a, b in zip(mm_vals, mm_vals[1:])):
            bad(tag + ".monotone", mm_vals, "non-decreasing")
    for key in ("m_perspectiveModelPenInfo", "m_draftPenInfo"):
        if (t.get(key) or {}).get("m_invertedScale") != -1:
            bad(key + ".m_invertedScale", (t.get(key) or {}).get("m_invertedScale"), -1)
    hdr = rec.header or {}
    if hdr.get("m_categroryId", INVALID) != INVALID:
        bad("hdr.m_categroryId", hdr.get("m_categroryId"), INVALID)
    if hdr.get("m_familyId", INVALID) != INVALID:
        bad("hdr.m_familyId", hdr.get("m_familyId"), INVALID)
    ab = int(hdr.get("m_abFlags4Bytes") or 0)
    if ab & 0x800:
        bad("hdr.m_abFlags4Bytes(cell-list bit)", hex(ab), "clear (no CellList)")
    if (ab & 0xFF) != 0x1E:
        bad("hdr.m_abFlags4Bytes(low byte)", hex(ab), "0x1E (PenWidthTableElem)")
    return {"hard": hard, "ok": not hard}


# ===========================================================================
# 2. THE PROJECT BROWSER  (BrowserOrganization + trackers)
# ===========================================================================

def _agg_param(param_ids: Union[int, Sequence[int]]) -> dict:
    """``AggregatedParameter{m_paramIdPath}`` = the parameter (path) a
    browser folder / sort / filter keys on: a single BuiltInParameter id or
    a path of parameter element ids."""
    path = [int(param_ids)] if isinstance(param_ids, int) else [int(p) for p in param_ids]
    return {"m_paramIdPath": path}


def _param_storage(value: Any) -> dict:
    """A ``ParamStorage`` value for a browser filter: string / double / int
    / element id, ``m_storageType`` per the schema enum (0 = none/empty,
    1 = int, 2 = double, 3 = string, 4 = element id) [VERIFIED string=3 and
    empty=0 in rme; 1/2/4 INFERRED from the storage-type enum order]."""
    st = {"m_str": {"m_str": ""}, "m_dbl": 0.0, "m_elemId": INVALID,
          "m_int": 0, "m_storageType": 0}
    if value is None or value == "":
        return st
    if isinstance(value, bool):
        st.update(m_int=int(value), m_storageType=1)
    elif isinstance(value, int):
        st.update(m_int=int(value), m_storageType=1)
    elif isinstance(value, float):
        st.update(m_dbl=float(value), m_storageType=2)
    else:
        st.update(m_str={"m_str": str(value)}, m_storageType=3)
    return st


def browser_organization(name: str, *, org_type: int = BROWSER_ORG_VIEWS,
                         folders: Sequence[Union[int, Sequence[int], dict]] = (),
                         sort_by: Union[int, Sequence[int], None] = BIP_VIEW_NAME,
                         ascending: bool = True,
                         filters: Sequence[dict] = (),
                         is_default: bool = False,
                         chars_to_use: int = 0,
                         ids: IdArg = None, elem_id: int = None,
                         cell_list: bool = False) -> TypeRecord:
    """A ``BrowserOrganization`` = one project-browser ORGANIZATION scheme
    (a named grouping + sorting + filter rule set for the views or sheets
    tree; the reader keeps a REQUIRED set of them -- Tier 2 required-class,
    11-12 in every accepted file).

    DEFINITION: ``m_symbolInfo.m_name`` (the scheme name; the built-in
    default of every tree is named ``all`` -- a required token, see
    :func:`default_browser_organizations`), ``m_type`` (which tree:
    :data:`BROWSER_ORG_VIEWS` / ``_SHEETS`` / ``_SCHEDULES`` / ``_TYPE4``),
    ``m_folderDefinitions`` (ordered folder levels, each a parameter path +
    the number of leading characters to group on: 0 = whole value),
    ``m_sortParameter`` (the leaf sort key; path ``[-1]`` = none),
    ``m_bSortOrderAsc``, ``m_filters`` ([{parameter path, ParamStorage
    value, relation 0 = equals / 1 = not-equals}]), ``m_bDefault`` (the
    scheme currently applied to its tree), ``m_category`` -1.

    ``folders`` items: an int / id-path, or {"param": id|path, "chars": n}.
    ``filters`` items: {"param": id|path, "value": v (''=blank), "relation":
    0|1}.  A folder/sort/filter that names a PROJECT parameter element (a
    positive id) makes it a deletion parent -- ours use built-ins only.
    [VERIFIED byte-exact vs rst/rac 24945..26017 + the four 'all' defaults.]
    """
    eid = _alloc(ids, elem_id)
    obj = _element("BrowserOrganization", eid, cell_list=cell_list)
    symbol_defaults(obj, name)
    fdefs, dele = [], []
    for f in folders:
        if isinstance(f, dict):
            path, chars = f.get("param"), int(f.get("chars", 0))
        else:
            path, chars = f, int(chars_to_use)
        ap = _agg_param(path)
        dele += [p for p in ap["m_paramIdPath"] if p > 0]
        fdefs.append({"m_parameter": ap, "m_numCharsToUse": chars})
    obj["m_filters"] = []
    for flt in filters:
        ap = _agg_param(flt["param"])
        dele += [p for p in ap["m_paramIdPath"] if p > 0]
        obj["m_filters"].append({"m_parameter": ap,
                                  "m_value": _param_storage(flt.get("value")),
                                  "m_relation": int(flt.get("relation", FILTER_EQUALS))})
    obj["m_folderDefinitions"] = fdefs
    obj["m_category"] = INVALID
    obj["m_type"] = int(org_type)
    obj["m_bDefault"] = bool(is_default)
    obj["m_bSortOrderAsc"] = bool(ascending)
    obj["m_sortParameter"] = _agg_param(sort_by if sort_by is not None else -1)
    return _settings_record(
        "BrowserOrganization", "browser-organization", eid, obj,
        deletion_ids=sorted(set(dele)),
        refs={"org_type": int(org_type), "default": bool(is_default),
              "folder_params": [f["m_parameter"]["m_paramIdPath"] for f in fdefs]},
        notes=(["default organization of its tree (name 'all' = required token)"]
               if is_default else []))


#: OUR project-browser scheme = the 4 REQUIRED per-tree defaults (name
#: 'all' -- Revit's fixed built-in default, undeletable/unrenameable, i.e.
#: a required token, not our expression) + OUR two house organizations.
#: The house pair deliberately differs from Autodesk's shipped set
#: ('not on sheets' / 'Phase' / 'Discipline' / 'Type/Discipline' /
#: 'Issue Date' / 'Drawn By' / 'Sheet Prefix' -- theirs, not reproduced):
#: OUR views tree groups by discipline THEN phase (a combination they do
#: not ship), OUR sheets tree groups by the sheet-number series prefix
#: (2 leading characters = our sheet-numbering standard's discipline
#: series 'E1'/'M2'/'A3'), sorted by number.
def default_browser_organizations(ids: IdArg, *, with_house_set: bool = True) -> List[TypeRecord]:
    """The project-browser organization SET: one default ('all') per tree
    (views, sheets, schedules, families) + our two house organizations.
    Returns [TypeRecord, ...]; the defaults are the ones the
    ``BrowserOrganizationTracking.m_currentBrOrgTypeToBrOrgMap`` registry
    keys per tree type (see :data:`ADOC_REGISTRY`)."""
    recs = [
        # the four REQUIRED defaults -- name 'all' is Revit's fixed token
        browser_organization("all", org_type=BROWSER_ORG_VIEWS,
                             folders=[BIP_VIEW_FAMILY_AND_TYPE],
                             sort_by=BIP_VIEW_NAME, is_default=True, ids=ids),
        browser_organization("all", org_type=BROWSER_ORG_SHEETS, folders=[],
                             sort_by=BIP_SHEET_NUMBER, is_default=True, ids=ids),
        browser_organization("all", org_type=BROWSER_ORG_SCHEDULES, folders=[],
                             sort_by=BIP_VIEW_NAME, is_default=True, ids=ids),
        browser_organization("all", org_type=BROWSER_ORG_TYPE4, folders=[],
                             sort_by=-1, is_default=True, ids=ids),
    ]
    if with_house_set:
        from .house_standard import gen                      # our name prefix
        recs.append(browser_organization(
            gen("Discipline / Phase"), org_type=BROWSER_ORG_VIEWS,
            folders=[BIP_VIEW_DISCIPLINE, BIP_VIEW_PHASE],
            sort_by=BIP_VIEW_NAME, is_default=False, ids=ids))
        recs.append(browser_organization(
            gen("Sheet Series"), org_type=BROWSER_ORG_SHEETS,
            folders=[{"param": BIP_SHEET_NUMBER, "chars": 2}],
            sort_by=BIP_SHEET_NUMBER, is_default=False, ids=ids))
    return recs


def reconcile_browser_settings(*, ids: IdArg = None, elem_id: int = None,
                               old_orphan_color: int = rgb(200, 0, 120),
                               new_orphan_color: int = rgb(0, 120, 200),
                               sort_mode: int = 0,
                               apply_graphics: bool = True) -> TypeRecord:
    """The document's ``ReconcileBrowserSettingsElem`` (the Reconcile-
    Hosting browser's graphics settings: how orphaned elements read).

    DEFINITION: ``m_oldOrphanedGStyle`` / ``m_newOrphanedGStyle`` = inline
    ``GStyle`` overrides {linePattern -1, material -1, pen -1, m_color
    (COLORREF), isScreenSized false}, ``m_sortMode`` (0 = by original
    category [INFERRED enum]), ``m_bApplyGraphicsSettings``.  OUR colours:
    magenta = "was hosted, now orphaned", cyan-blue = "orphaned in this
    session" (Autodesk's default is green 0x008000 for both -- not
    reproduced).  [VERIFIED structure vs rst 116120.]"""
    eid = _alloc(ids, elem_id)
    obj = _element("ReconcileBrowserSettingsElem", eid)

    def gstyle(color: int) -> dict:
        return {"m_linePatternId": INVALID, "m_materialElemId": INVALID,
                "m_penNumber": -1, "m_color": int(color), "m_isScreenSized": False}
    obj["m_oldOrphanedGStyle"] = gstyle(old_orphan_color)
    obj["m_newOrphanedGStyle"] = gstyle(new_orphan_color)
    obj["m_sortMode"] = int(sort_mode)
    obj["m_bApplyGraphicsSettings"] = bool(apply_graphics)
    return _settings_record("ReconcileBrowserSettingsElem",
                            "reconcile-browser-settings", eid, obj)


#: OUR conceptual-energy construction set: NO energy constructions
#: assigned (a genesis base carries no conceptual energy model; the
#: samples name gbXML/DOE-2 construction codes 'ASHWL-66' / 'ASHIW23' /
#: 'SGFLR' ... keyed into Autodesk's shipped Constructions.xml database --
#: their product data, deliberately NOT reproduced and not referenced).
CONSTRUCTION_SET_SURFACES = (
    "external_wall", "partition", "solid_ground", "roof", "ceiling", "floor",
    "door", "external_window", "internal_window", "roof_light", "underground_wall",
)
_CS_FIELDS = {
    "external_wall": "m_strExternalWall", "partition": "m_strPartition",
    "solid_ground": "m_strSolidGround", "roof": "m_strRoof",
    "ceiling": "m_strCeiling", "floor": "m_strFloor", "door": "m_strDoor",
    "external_window": "m_strExternalWindow",
    "internal_window": "m_strInternalWindow",
    "roof_light": "m_strRoofLight", "underground_wall": "m_strUndergroundWall",
}


def construction_set_project(*, ids: IdArg = None, elem_id: int = None,
                             name: str = "<Building>",
                             constructions: Optional[Dict[str, str]] = None,
                             shading_factor: float = 0.0,
                             cell_list: bool = True) -> TypeRecord:
    """The document's ``ConstructionSetProject`` (the whole-building
    conceptual-energy CONSTRUCTION SET, a Symbol).

    DEFINITION: ``m_symbolInfo.m_name`` = ``<Building>`` (the fixed
    project-level construction-set token, angle brackets = built-in),
    the eleven surface construction ids ``m_str*`` (keys into an energy
    constructions database; OURS default to '' = unassigned),
    ``m_rgbOverrideModel[11]`` (per-surface override flags),
    ``m_dShadingFactor``.  ``constructions`` = {surface-key: construction
    id string} over :data:`CONSTRUCTION_SET_SURFACES`.  Carries a present
    empty ``ParamValueSetAString`` [VERIFIED rst/rac/rme].  [VERIFIED
    structure vs rst 99928.]"""
    eid = _alloc(ids, elem_id)
    obj = _element("ConstructionSetProject", eid, cell_list=cell_list,
                   astring_params={})
    symbol_defaults(obj, name)
    obj["m_rgbOverrideModel"] = [False] * 11
    cons = constructions or {}
    for key, fld in _CS_FIELDS.items():
        obj[fld] = str(cons.get(key, ""))
    obj["m_dShadingFactor"] = float(shading_factor)
    return _settings_record("ConstructionSetProject", "construction-set",
                            eid, obj,
                            refs={"assigned": sorted(k for k, v in cons.items() if v)},
                            notes=(["no energy constructions assigned (a genesis "
                                    "base carries no conceptual energy model)"]
                                   if not any(cons.values()) else []))


# ===========================================================================
# 3. THE SYSTEM NAVIGATOR  (RbsDbViewSystemNavigator + its view frame)
# ===========================================================================

def system_navigator(ids: IdArg, *, phase_id: int = INVALID,
                     phase_filter_id: int = INVALID,
                     sun_settings_id: int = INVALID,
                     invisible_style_id: int = INVALID,
                     not_silhouette_style_id: int = INVALID,
                     viewport_type_id: int = INVALID,
                     excluded_categories: Sequence[int] = (),
                     name: str = "???",
                     shadow_intensity: int = 50,
                     sunlight_intensity: int = 30,
                     all_phases_id: int = INVALID,
                     units_id: int = INVALID,
                     workset_visibility_id: int = INVALID,
                     mep_system_tracker_id: int = INVALID) -> List[TypeRecord]:
    """The MEP SYSTEM BROWSER's implicit view = an ``RbsDbViewSystemNavigator``
    (a plain ``DBView`` subclass -- the class adds ZERO fields of its own)
    plus its view frame: a ``Viewer``, a ``Viewport`` and a ``DBDrawing``
    -- exactly the shape of the document's PROJECT VIEW constellation
    (``rvt.genesis.skeleton.new_project_view``), differing only in class,
    a plan-like orientation (view direction +Z, up +Y), a null integer
    parameter set, and dimmer sun intensities.  Returns
    ``[navigator_view, viewer, viewport, drawing]``; the navigator is the
    id ``DBViewInfo.m_DBViewSystemNavigatorId`` names.

    Name ``???`` = the fixed internal token every corpus file's project /
    navigator view carries (REQUIRED FORMAT TOKEN, not expression).
    ``viewport_type_id`` = a ViewportAttributes type (-1 = none: viewport
    types are annotation-family content).  ``excluded_categories`` = the
    IckyExcludedCategories draw filter (OUR policy: empty = everything
    drawable; the samples exclude ~57 analytical categories).  The view's
    regeneration edges: ``m_regenOnly`` -> {AllProjectPhases, UnitsElem,
    WorksetVisibilitySettingsElem}, ``m_deferredParents`` -> {the
    MEPSystemTracker} (pass their ids; -1 = edge absent) [VERIFIED wiring
    vs rst 69851].  [VERIFIED constellation vs rst 69851..69854 (view,
    viewer 69852, viewport 69853, drawing 69854); DBView leaves vs
    DBViewProject 230.]
    """
    view_id = _alloc(ids)
    viewer_id = _alloc(ids)
    viewport_id = _alloc(ids)
    drawing_id = _alloc(ids)
    # -- the navigator view (DBView base, plan-like frame) ------------------
    obj = sk.dbview_base(
        view_id, name, viewer_id=viewer_id, drawing_id=drawing_id,
        sun_settings_id=sun_settings_id, view_type_id=INVALID,
        phase_id=phase_id, phase_filter_id=phase_filter_id,
        origin=(0.0, 0.0, 0.0), view_dir=(0.0, 0.0, 1.0),
        horz_dir=(1.0, 0.0, 0.0), vert_dir=(0.0, 1.0, 0.0),
        scale=0.01, back_clipping=-1,
        excluded_categories=list(excluded_categories),
        invisible_style_id=invisible_style_id,
        not_silhouette_style_id=not_silhouette_style_id,
        cell_list=True, shadow_intensity=shadow_intensity)
    obj["m_pParamValueSetInt"] = None            # the navigator carries no int set
    vdm = obj["m_pViewDisplayMgr"]["value"]
    vdm["m_lights"]["m_sunlightIntensity"] = int(sunlight_intensity)
    vdm["m_model"]["m_surfaces"] = 1           # navigator: consistent-colour surfaces off
    vdm["m_oStaticRRTRenderSettings"]["value"]["m_iPrintPageWidth"] = 12
    vdm["m_oStaticRRTRenderSettings"]["value"]["m_BkIamgeSettings"]["m_FitType"] = 0
    dele = [view_id, viewer_id, drawing_id] + [x for x in (
        phase_id, phase_filter_id, sun_settings_id, invisible_style_id,
        not_silhouette_style_id) if x is not None and x >= 0]
    regen = [x for x in (all_phases_id, units_id, workset_visibility_id)
             if x not in (None, INVALID)]
    ab, vis = _hdr("RbsDbViewSystemNavigator")
    hdr = sk.element_header("RbsDbViewSystemNavigator", category=-1,
                            deletion=sorted(set(dele)), regen_only=regen,
                            flags=ab, visible_view_flags=vis)
    if mep_system_tracker_id not in (None, INVALID):
        hdr["m_parents"]["value"]["m_deferredParents"] = [int(mep_system_tracker_id)]
    view = TypeRecord(view_id, "system-navigator", "RbsDbViewSystemNavigator",
                      class_id("RbsDbViewSystemNavigator"), INVALID, obj, hdr,
                      None,
                      refs={"viewer": viewer_id, "viewport": viewport_id,
                            "drawing": drawing_id, "phase": phase_id,
                            "phase_filter": phase_filter_id, "sun": sun_settings_id},
                      notes=["MEP system browser view; name '???' = required token; "
                             "DBView + Viewer + Viewport + DBDrawing constellation"])
    # -- its Viewer: elevation-less plan frame, bounds inactive, ortho ------
    vo = sk._viewer_common(viewer_id, view_id, orig=(0.0, 0.0, 0.0),
                           basis=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [-0.0, -0.0, -1.0]],
                           offsets=[[100.0, -100.0], [100.0, -100.0], [1000.0, 0.1]],
                           active=[[False, False], [False, False], [False, False]],
                           crop_on=True, target=(0.0, 0.0, 0.0),
                           axis=(0.0, 1.0, 0.0), proj_dist=0.1,
                           with_gstep=True, cell_list=True)
    vo["m_pParamValueSetElementId"] = None
    vo["m_projMethodType"] = 1
    vo["m_viewerFlags"] = 0
    vo["m_intentionallyPlaced"] = False
    vab, vvis = _hdr("Viewer")
    vhdr = sk.element_header("Viewer", category=-1, deletion=[view_id, viewer_id],
                             flags=vab, visible_view_flags=vvis)
    viewer = TypeRecord(viewer_id, "system-navigator-viewer", "Viewer",
                        class_id("Viewer"), INVALID, vo, vhdr, None,
                        refs={"view": view_id, "owner_id": view_id})
    # -- viewport + drawing (the skeleton's own constructors) ----------------
    vp = sk.new_viewport(viewport_id, view_id, drawing_id,
                         viewport_type_id=viewport_type_id,
                         label_origin_z=0.0, flags=2074)
    dr = sk.new_dbdrawing(drawing_id, [viewport_id], view_id, flags=2074)
    viewport = vp.as_type_record()
    drawing = dr.as_type_record()
    viewport.kind = "system-navigator-viewport"
    drawing.kind = "system-navigator-drawing"
    # the navigator's viewport carries appearance edges to (its type,) the
    # view and the viewer, and regenerates on the viewer [VERIFIED rst 69853]
    vpar = viewport.header["m_parents"]["value"]
    vpar["m_appearanceParents"] = sorted({int(x) for x in (viewport_type_id, view_id, viewer_id)
                                          if x not in (None, INVALID)})
    vpar["m_regenOnly"] = [int(viewer_id)]
    return [view, viewer, viewport, drawing]


# ===========================================================================
# 4. STRUCTURAL / JOIN / KEYNOTE / INITIAL-VIEW singletons  (the named set)
# ===========================================================================
#: OUR structural symbolic settings (imperial house standard).  Cutbacks,
#: brace symbols and analytical tolerances are drafting / analysis
#: CONVENTIONS: symbolic cutback 3/32" from the joined member, brace
#: symbol parallel offset 3/32", column cutback 1/16", analytical-model
#: snap / support tolerances 1'-0", discrepancy 6", boundary-condition
#: symbol spacing 1", load-scaling slopes (our display scaling of load
#: arrows) and the analytical load display range 0..1000 kip.  Autodesk's
#: metric-template values (2.5 mm / 300 mm / 150 mm / 25 mm ...) are not
#: reproduced.  Boundary-condition FAMILY ids are -1 (no loaded families;
#: the K3 rung proved the reader tolerates a null bcFixedFamilyId path).
STRUCTURAL_SETTINGS: Dict[str, Any] = {
    "parallel_brace_offset_in": 3.0 / 32.0,
    "symbolic_cutback_in": 3.0 / 32.0,
    "symbolic_brace_cutback_in": 3.0 / 32.0,
    "column_cutback_in": 1.0 / 16.0,
    "analytical_snap_ft": 1.0,
    "tolerance_support_ft": 1.0,
    "tolerance_discrepancy_ft": 0.5,
    "tolerance_autofix_xy_ft": 1.0,
    "tolerance_autofix_z_ft": 1.0,
    "bc_symbol_spacing_in": 1.0,
    "point_loads_slope": 0.001,          # loads display scaling (ft per unit load) -- ours
    "line_loads_slope": 0.001,
    "area_loads_slope": 0.003,
    "loads_y_intercept": 0.0,
    "min_load_force": 0.0,
    "max_load_force": 1_000_000.0,      # analysis load display cap (internal force units)
    "brace_repr_type": 1,               # brace symbol representation: 1 = line with kicker
    "show_brace_above": True,
    "show_brace_below": True,
}


def struct_settings(*, ids: IdArg = None, elem_id: int = None,
                    settings: Optional[Dict[str, Any]] = None,
                    hidden_level_ids: Sequence[int] = (),
                    brace_above_id: int = INVALID, brace_below_id: int = INVALID,
                    kicker_brace_id: int = INVALID,
                    bc_fixed_family_id: int = INVALID,
                    bc_pinned_family_id: int = INVALID,
                    bc_roller_family_id: int = INVALID,
                    bc_user_family_id: int = INVALID,
                    show_analytical_nodes: bool = False,
                    use_loads_display_scaling: bool = False,
                    boundary_setback_disabled_for_steel: bool = False,
                    auto_support: bool = False, auto_consistency: bool = False,
                    check_support_cycle: bool = True,
                    check_consistency_discrepancy: bool = True,
                    check_consistency_gap: bool = True,
                    check_consistency_beam_slab: bool = True,
                    check_consistency_instability: bool = True,
                    enable_analytical_model_distance: bool = True,
                    differentiate_analytical_ends: bool = True,
                    check_analytical_model_asset: bool = False) -> TypeRecord:
    """The document's ``StructSettingsElem`` (Structural Settings: symbolic
    representation, brace symbols, analytical-model tolerances, boundary
    conditions, load-display scaling).  ``settings`` overrides keys of
    :data:`STRUCTURAL_SETTINGS` (inch / foot / raw values, converted here).
    The four ``bc_*_family_id`` = the boundary-condition symbol FAMILIES
    (loadable content -> -1 in a family-free base; K3 nulled this path in a
    passing file).  [VERIFIED all 40 fields byte-exact vs rst 54663 (its own
    metric values fed back).]"""
    eid = _alloc(ids, elem_id)
    s = dict(STRUCTURAL_SETTINGS)
    if settings:
        s.update(settings)
    obj = _element("StructSettingsElem", eid)
    obj["m_hiddenLevelIds"] = [int(x) for x in hidden_level_ids]
    obj["m_parallelBraceOffset"] = inches(s["parallel_brace_offset_in"])
    obj["m_symbolicCutback"] = inches(s["symbolic_cutback_in"])
    obj["m_symbolicBraceCutback"] = inches(s["symbolic_brace_cutback_in"])
    obj["m_analyticalModelSnapDistance"] = float(s["analytical_snap_ft"])
    obj["m_columnCutback"] = inches(s["column_cutback_in"])
    obj["m_toleranceSupport"] = float(s["tolerance_support_ft"])
    obj["m_toleranceDiscrepancy"] = float(s["tolerance_discrepancy_ft"])
    obj["m_toleranceAutofixXY"] = float(s["tolerance_autofix_xy_ft"])
    obj["m_toleranceAutofixZ"] = float(s["tolerance_autofix_z_ft"])
    obj["m_bcSpacing"] = inches(s["bc_symbol_spacing_in"])
    obj["m_scaledPointLoadsIntensitySlope"] = float(s["point_loads_slope"])
    obj["m_scaledLineLoadsIntensitySlope"] = float(s["line_loads_slope"])
    obj["m_scaledAreaLoadsIntensitySlope"] = float(s["area_loads_slope"])
    obj["m_scaledLoadsIntensityYIntercept"] = float(s["loads_y_intercept"])
    obj["m_minLoadForce"] = float(s["min_load_force"])
    obj["m_maxLoadForce"] = float(s["max_load_force"])
    obj["m_braceAbove"] = int(brace_above_id)
    obj["m_braceBelow"] = int(brace_below_id)
    obj["m_kickerBrace"] = int(kicker_brace_id)
    obj["m_bcFixedFamilyId"] = int(bc_fixed_family_id)
    obj["m_bcPinnedFamilyId"] = int(bc_pinned_family_id)
    obj["m_bcRollerFamilyId"] = int(bc_roller_family_id)
    obj["m_bcUserFamilyId"] = int(bc_user_family_id)
    obj["m_braceReprType"] = int(s["brace_repr_type"])
    obj["m_showAnalyticalNodes"] = bool(show_analytical_nodes)
    obj["m_showBraceAbove"] = bool(s["show_brace_above"])
    obj["m_showBraceBelow"] = bool(s["show_brace_below"])
    obj["m_useLoadsDisplayScaling"] = bool(use_loads_display_scaling)
    obj["m_boundarySetbackDisabledForSteelElements"] = bool(boundary_setback_disabled_for_steel)
    obj["m_autoSupport"] = bool(auto_support)
    obj["m_autoConsistency"] = bool(auto_consistency)
    obj["m_supportCycle"] = bool(check_support_cycle)
    obj["m_consistencyDiscrepancy"] = bool(check_consistency_discrepancy)
    obj["m_consistencyGap"] = bool(check_consistency_gap)
    obj["m_consistencyBeamSlab"] = bool(check_consistency_beam_slab)
    obj["m_consistencyInstability"] = bool(check_consistency_instability)
    obj["m_enableAnalyticalModelDistance"] = bool(enable_analytical_model_distance)
    obj["m_differentiateAnalyticalEnds"] = bool(differentiate_analytical_ends)
    obj["m_checkAnalyticalModelAsset"] = bool(check_analytical_model_asset)
    fam = [i for i in (bc_fixed_family_id, bc_pinned_family_id,
                       bc_roller_family_id, bc_user_family_id, brace_above_id,
                       brace_below_id, kicker_brace_id) if i not in (None, INVALID)]
    return _settings_record("StructSettingsElem", "structural-settings", eid, obj,
                            deletion_ids=fam, refs={"family_ids": fam},
                            notes=(["boundary-condition families -1 (family-free base)"]
                                   if not fam else []))


def wall_join_default_setting(*, ids: IdArg = None, elem_id: int = None,
                              default_records: Sequence[dict] = (),
                              wall_part_flag: int = 0) -> TypeRecord:
    """The document's ``WallJoinDefaultSetting`` (per-join-type default
    cleanup records; empty in every sample = no user defaults).
    DEFINITION: ``m_defaultSettingRecordArr`` ([] = none),
    ``m_wallPartFlag`` 0.  [VERIFIED byte-exact vs rst/rac/rme.]"""
    return _generic("WallJoinDefaultSetting", "wall-join-defaults", ids, elem_id,
                    {"m_defaultSettingRecordArr": [dict(r) for r in default_records],
                     "m_wallPartFlag": int(wall_part_flag)})


def auto_join_tracker(*, ids: IdArg = None, elem_id: int = None,
                      keep_old_overlapping_unjoined: bool = False,
                      excluded_ids: Sequence[int] = ()) -> TypeRecord:
    """The document's ``AutoJoinTracker`` (the wall auto-join bookkeeping
    singleton).  DEFINITION: ``m_map`` [] (join records = regenerable
    session state), ``m_keepOldOverlappingElemsUnjoined`` (the one real
    setting), ``m_excludedIds`` (elements excluded from auto-join).
    [VERIFIED byte-exact vs rst/rac/rme.]"""
    return _generic("AutoJoinTracker", "auto-join-tracker", ids, elem_id,
                    {"m_map": [],
                     "m_keepOldOverlappingElemsUnjoined": bool(keep_old_overlapping_unjoined),
                     "m_excludedIds": [int(x) for x in excluded_ids]},
                    deletion_ids=[int(x) for x in excluded_ids])


def _keynote_entries(entries: Sequence[Union[Tuple[str, str, str], dict]]) -> Tuple[list, list]:
    """Build the ``KeynoteEntryTable`` rows from (key, parent_key, text)
    triples; children lists are derived from the parent keys, orphans =
    keys whose parent is not in the table."""
    rows = []
    for e in entries:
        if isinstance(e, dict):
            key, parent, text = e["key"], e.get("parent", ""), e.get("text", "")
        else:
            key, parent, text = e[0], e[1], e[2]
        rows.append((str(key), str(parent or ""), str(text)))
    keys = {k for k, _p, _t in rows}
    children: Dict[str, List[str]] = {k: [] for k in keys}
    orphans = []
    for k, p, _t in rows:
        if p:
            if p in children:
                children[p].append(k)
            else:
                orphans.append({"m_str": k})
    tree = []
    for k, p, t in rows:
        entry = {"m_childrenKeys": [{"m_str": c} for c in children[k]],
                 "m_key": k, "m_parentKey": p, "m_keynoteText": t}
        tree.append({"m_oEntry": _ptr("KeynoteEntry", entry), "m_key": k})
    # a top-level entry (parent "") is an orphan-list member in Revit's
    # bookkeeping (rst: 16 top-level divisions listed in m_orphans)
    orphans = [{"m_str": k} for k, p, _t in rows if not p] + orphans
    return tree, orphans


def keynote_table(*, ids: IdArg = None, elem_id: int = None,
                  entries: Sequence[Union[Tuple[str, str, str], dict]] = (),
                  name: str = "Standard", built_in: bool = True,
                  keynote_file_path: Optional[str] = None,
                  last_read_succeeded: bool = False,
                  cell_list: bool = False) -> TypeRecord:
    """The document's ``KeynoteTable`` = the keynote definitions table
    (normally loaded from an external keynote text file).

    OURS: an EMPTY table (no keynote file loaded, ``entries`` = []) -- the
    samples embed Autodesk's shipped ``RevitKeynotes_Metric.txt`` (3,840
    CSI MasterFormat rows = their product data + an employee's local path;
    NOT reproduced).  A job may pass its own (key, parent_key, text) rows.
    DEFINITION: ``m_oKeyBasedTreeEntries`` -> ``KeynoteEntryTable``
    {``m_keyBasedTreeEntrySet`` [{KeynoteEntry{childrenKeys, key,
    parentKey, keynoteText}, key}], ``m_orphans`` [top-level keys]},
    ``m_lastReadSucceeded``, ``m_name`` ('Standard' = the built-in table's
    fixed name token), ``m_isBuiltIn``, ``m_hasUserCustomizedKeynote``;
    cell list = ``ExternalFileReferenceCell`` + an
    ``ExternalResourceReferenceCell`` naming the keynote file (empty = no
    file).  [VERIFIED structure vs rst/rac/rme 86291; entry rows shape vs
    the 3,840-row specimen.]"""
    eid = _alloc(ids, elem_id)
    obj = _element("KeynoteTable", eid)
    tree, orphans = _keynote_entries(entries)
    obj["m_oKeyBasedTreeEntries"] = _ptr("KeynoteEntryTable", {
        "m_keyBasedTreeEntrySet": tree, "m_orphans": orphans})
    obj["m_lastReadSucceeded"] = bool(last_read_succeeded)
    obj["m_name"] = str(name)
    obj["m_isBuiltIn"] = bool(built_in)
    obj["m_hasUserCustomizedKeynote"] = False
    refs = []
    if keynote_file_path:
        # our file reference: display path only, keyed by the external-
        # resource "Path"/"PathType" reference-information pairs (interface)
        ref = {"m_serverId": NULL_GUID,
               "m_displayPath": str(keynote_file_path),
               "m_referenceInformation": [
                   {"first": "Path", "second": str(keynote_file_path)},
                   {"first": "PathType", "second": "Absolute"}],
               "m_version": ""}
        refs = [{"first": {"m_value": NULL_GUID}, "second": ref}]
    cells = [_ptr("ExternalFileReferenceCell", {}),
             _ptr("ExternalResourceReferenceCell", {
                 "m_externalResourceReferences": refs,
                 "m_externalResourceReferencesExpanded": ([
                     {"first": {"m_value": NULL_GUID},
                      "second": {"m_refs": [{"first": NULL_GUID, "second": refs[0]["second"]}]}}
                 ] if refs else [])})]
    if cell_list:
        cells.append(_ptr("PatternHelper", {"m_PatternPositionMap": [],
                                             "m_substituteFaceMap": []}))
    obj["m_cellList"] = _ptr("CellList", {"m_cells": cells})
    return _settings_record("KeynoteTable", "keynote-table", eid, obj,
                            refs={"entries": len(tree), "file": keynote_file_path or ""},
                            notes=(["empty keynote table -- no keynote file loaded (ours)"]
                                   if not tree else [f"{len(tree)} keynote entries"]))


def keynoting_system(keynote_table_id: int, *, ids: IdArg = None,
                     elem_id: int = None, number_by_sheet: bool = False,
                     cell_list: bool = False) -> TypeRecord:
    """The document's ``KeynotingSystem``: which keynote table drives the
    keynote tags and the numbering mode (by keynote / by sheet).
    DEFINITION: ``m_keynoteTableId`` -> :func:`keynote_table`,
    ``m_isNumberBySheet``.  [VERIFIED byte-exact vs rst/rac/rme 86315.]"""
    return _generic("KeynotingSystem", "keynoting-system", ids, elem_id,
                    {"m_keynoteTableId": int(keynote_table_id),
                     "m_isNumberBySheet": bool(number_by_sheet)},
                    cell_list=cell_list, deletion_ids=[keynote_table_id],
                    refs={"keynote_table": int(keynote_table_id)})


def initial_view_settings(*, ids: IdArg = None, elem_id: int = None,
                          initial_view_id: int = INVALID) -> TypeRecord:
    """The document's ``InitialViewSettings`` = the Starting View (the
    view opened with the file).  DEFINITION: ``m_initialViewId`` (-1 =
    <Last Viewed>; else a view id, which joins the deletion set).
    [VERIFIED byte-exact vs rst 133303.]"""
    dele = [initial_view_id] if initial_view_id not in (None, INVALID) else []
    return _generic("InitialViewSettings", "initial-view", ids, elem_id,
                    {"m_initialViewId": int(initial_view_id)},
                    deletion_ids=dele, refs={"initial_view": int(initial_view_id)})


# ===========================================================================
# 5. MEP SETTINGS SINGLETONS  (wire / duct / pipe / conduit / cable tray)
# ===========================================================================
#: MEP annotation / routing house standard (imperial).  Text-height-scaled
#: fitting-annotation sizes = OUR 3/32" (2.4 mm) symbol size; rise/drop
#: symbols = the two-line-diagram symbol families' enum codes below;
#: routing offsets = OUR ceiling-space conventions (mains centred 10'-0"
#: above the floor, branches 9'-0", 3'-0" minimum segment, 6'-0" max flex
#: run-out, 1'-6" perimeter inset).  Autodesk's shipped values (9'-0" /
#: 2'-1" / metric round-offs) are not reproduced.
MEP_ANNOTATION_SIZE_IN = 3.0 / 32.0
MEP_MAIN_OFFSET_FT = 10.0
MEP_BRANCH_OFFSET_FT = 9.0
MEP_MIN_LENGTH_FT = 3.0
MEP_FLEX_MAX_FT = 6.0
MEP_PERIMETER_INSET_FT = 1.5
#: connector-description separator ('-' between system and number, e.g.
#: "M1-2") and centreline / flat-on symbols are near-universal MEP
#: shorthand: '=' centreline, 'FOT'/'FOB' flat on top/bottom, 'SU'/'SD'
#: set up/down, 'BU'/'BD' from bottom (industry abbreviations = facts).
MEP_CONNECTOR_SEPARATOR = "-"
#: OUR size-annotation punctuation: imperial trade sizes carry the inch
#: mark suffix; rectangular sizes are separated by 'x'; oval by '/'.
MEP_ROUND_SIZE_SUFFIX = '"'
MEP_SIZE_SEPARATOR = "x"
MEP_OVAL_SEPARATOR = "/"
#: fitting-angle set = the manufactured elbow angles of MEP fittings
#: [FACT: standard factory bends 11.25 / 22.5 / 30 / 45 / 60 / 90 deg];
#: the same set our ElectricalSetting carries (rvt.genesis.house_standard).
MEP_SPECIFIC_ANGLES_DEG: Tuple[float, ...] = (11.25, 22.5, 30.0, 45.0, 60.0, 90.0)
#: OUR pipe slope palette (rise per foot expressed as the schema's
#: dimensionless ratio *12*: value = inches-per-foot; plumbing code slopes
#: 1/8", 1/4", 1/2" per foot are FACTS (IPC 704.1); the rest are ours).
PIPE_SLOPES_IN_PER_FT: Tuple[float, ...] = (0.0, 1.0 / 16, 1.0 / 8, 1.0 / 4,
                                            3.0 / 8, 1.0 / 2, 3.0 / 4, 1.0)
#: standard air properties at 68 F / 20 C, sea level [FACT: density
#: 1.2041 kg/m^3, dynamic viscosity 1.813e-5 Pa.s], expressed in the
#: file's internal units (mass kg, length ft, time s).
_KG_M3_TO_INTERNAL = 0.3048 ** 3            # kg/m^3 -> kg/ft^3
_PA_S_TO_INTERNAL = 0.3048                  # kg/(m.s) -> kg/(ft.s)
STANDARD_AIR_DENSITY_KG_M3 = 1.2041
STANDARD_AIR_VISCOSITY_PA_S = 1.813e-5

#: rise/drop symbol codes (the schema's rise/drop enums; the symbol choice
#: is our diagram convention -- rise = yin-yang / drop = full circle for
#: contour, plain arrow codes for one-line) [enum values INFERRED from
#: the samples' populated codes; ours use small distinct codes].
RISE_DROP_CODES = {"rise": 1, "drop": 3, "one_line_rise": 1,
                   "one_line_drop": 3, "junction_rise": 1, "junction_drop": 3,
                   "bend_rise": 1, "bend_drop": 3}


def _server_info(name: str = "", description: str = "",
                 server_id: str = NULL_GUID) -> dict:
    """An MEP external-calculation-server descriptor (pressure-loss /
    flow-conversion service).  The samples name Autodesk's built-in
    calculation servers ('Colebrook Equation', 'Duct Pressure Drop',
    'Plumbing Fixture Flow') by their registered GUIDs -- interface
    identifiers of Revit's own installed services.  OURS default to NONE
    selected (null GUID, empty strings): the reader recomputes with its
    default server on demand [tolerance UNVERIFIED -- probe row]."""
    return {"m_description": str(description), "m_serverName": str(name),
            "m_serverId": str(server_id)}


def wire_settings(*, ids: IdArg = None, elem_id: int = None,
                  tick_mark_families: Optional[Dict[str, int]] = None,
                  connector_separator: str = MEP_CONNECTOR_SEPARATOR,
                  crossing_gap_mm: float = 2.0,
                  home_run_arrow_style_id: int = INVALID,
                  show_tick_marks: int = 0, tick_mark_style: int = 0,
                  electrical_data_style: int = 0,
                  circuit_description_style: int = 0,
                  home_run_arrow_count_style: int = 0,
                  cell_list: bool = False) -> TypeRecord:
    """The document's ``RbsWireSettingsElem`` (Electrical Settings >
    Wiring: tick-mark symbol families, wire-crossing gap, home-run
    arrowhead, circuit description formatting).

    DEFINITION: ``m_wireTickMarkStyle`` {hot / neutral / ground conductor
    tick-mark FAMILY SYMBOL ids (annotation families -> -1 in a family-
    free base), ``m_bDrawSlantedLine``}, ``m_strElectricalConnector
    Separator``, ``m_dWiringCrossingGap`` (ft), ``m_idWireHomeRunArrow
    LeaderStyle`` (an arrowhead LeaderStyle element; -1 = none),
    ``m_eShowTickMarks`` / ``m_nWireTickMarkStyle`` /
    ``m_nElectricalDataStyle`` / ``m_nCircuitDescriptionStyle`` /
    ``m_eWireHomeRunArrowCountStyle`` (enum codes, 0 = defaults).
    [VERIFIED byte-exact vs rme 293123.]"""
    eid = _alloc(ids, elem_id)
    fam = tick_mark_families or {}
    obj = _element("RbsWireSettingsElem", eid, cell_list=cell_list)
    obj["m_wireTickMarkStyle"] = {
        "m_hotConductorFamSymId": int(fam.get("hot", INVALID)),
        "m_neutralConductorFamSymId": int(fam.get("neutral", INVALID)),
        "m_groundConductorFamSymId": int(fam.get("ground", INVALID)),
        "m_bDrawSlantedLine": bool(fam.get("slanted", False)),
    }
    obj["m_strElectricalConnectorSeparator"] = str(connector_separator)
    obj["m_dWiringCrossingGap"] = mm(crossing_gap_mm)
    obj["m_idWireHomeRunArrowLeaderStyle"] = int(home_run_arrow_style_id)
    obj["m_eShowTickMarks"] = int(show_tick_marks)
    obj["m_nWireTickMarkStyle"] = int(tick_mark_style)
    obj["m_nElectricalDataStyle"] = int(electrical_data_style)
    obj["m_nCircuitDescriptionStyle"] = int(circuit_description_style)
    obj["m_eWireHomeRunArrowCountStyle"] = int(home_run_arrow_count_style)
    dele = [i for i in (home_run_arrow_style_id, fam.get("hot", INVALID),
                        fam.get("neutral", INVALID), fam.get("ground", INVALID))
            if i not in (None, INVALID)]
    return _settings_record("RbsWireSettingsElem", "wire-settings", eid, obj,
                            deletion_ids=dele, refs={"companions": dele},
                            notes=(["tick-mark families / home-run arrowhead -1 "
                                    "(annotation content, family-free base)"]
                                   if not dele else []))


def conduit_settings(*, ids: IdArg = None, elem_id: int = None,
                     connector_separator: str = MEP_CONNECTOR_SEPARATOR,
                     size_prefix: str = "", size_suffix: str = MEP_ROUND_SIZE_SUFFIX,
                     fitting_annotation_size_in: float = MEP_ANNOTATION_SIZE_IN,
                     rise_drop_annotation_size_in: float = MEP_ANNOTATION_SIZE_IN,
                     one_line_drop_type: int = 3, one_line_rise_type: int = 1,
                     contour_drop_type: int = 3, contour_rise_type: int = 1,
                     use_anno_scale_for_1line: bool = True,
                     cell_list: bool = False) -> TypeRecord:
    """The document's ``ConduitSettingsElem`` (Electrical Settings >
    Conduit: connector separator, size prefix/suffix, fitting & rise/drop
    annotation sizes (feet in the file, inches here), the four rise/drop
    symbol codes, annotation-scale flag).  [VERIFIED byte-exact vs rme
    638851 / rst 113174.]"""
    eid = _alloc(ids, elem_id)
    obj = _element("ConduitSettingsElem", eid, cell_list=cell_list)
    obj["m_strConnectorSeparator"] = str(connector_separator)
    obj["m_strSizePrefix"] = str(size_prefix)
    obj["m_strSizeSuffix"] = str(size_suffix)
    obj["m_dFittingAnnotationSize"] = inches(fitting_annotation_size_in)
    obj["m_dRiseDropAnnotationSize"] = inches(rise_drop_annotation_size_in)
    obj["m_e1LineDropType"] = int(one_line_drop_type)
    obj["m_e1LineRiseType"] = int(one_line_rise_type)
    obj["m_eContourDropType"] = int(contour_drop_type)
    obj["m_eContourRiseType"] = int(contour_rise_type)
    obj["m_bUseAnnoScaleFor1LineFittings"] = bool(use_anno_scale_for_1line)
    return _settings_record("ConduitSettingsElem", "conduit-settings", eid, obj)


def cable_tray_settings(*, ids: IdArg = None, elem_id: int = None,
                        connector_separator: str = MEP_CONNECTOR_SEPARATOR,
                        size_separator: str = MEP_SIZE_SEPARATOR,
                        size_suffix: str = MEP_ROUND_SIZE_SUFFIX,
                        fitting_annotation_size_in: float = MEP_ANNOTATION_SIZE_IN,
                        rise_drop_annotation_size_in: float = MEP_ANNOTATION_SIZE_IN,
                        one_line_drop_type: int = 17, one_line_rise_type: int = 17,
                        contour_drop_type: int = 2, contour_rise_type: int = 2,
                        use_anno_scale_for_1line: bool = True,
                        cell_list: bool = False) -> TypeRecord:
    """The document's ``CableTraySettingsElem`` (Electrical Settings >
    Cable Tray): as :func:`conduit_settings` but with a size SEPARATOR
    (rectangular tray "W x H") instead of a prefix.  [VERIFIED byte-exact
    vs rme 638850 / rst 113173.]"""
    eid = _alloc(ids, elem_id)
    obj = _element("CableTraySettingsElem", eid, cell_list=cell_list)
    obj["m_strConnectorSeparator"] = str(connector_separator)
    obj["m_strSizeSeparator"] = str(size_separator)
    obj["m_strSizeSuffix"] = str(size_suffix)
    obj["m_dFittingAnnotationSize"] = inches(fitting_annotation_size_in)
    obj["m_dRiseDropAnnotationSize"] = inches(rise_drop_annotation_size_in)
    obj["m_e1LineDropType"] = int(one_line_drop_type)
    obj["m_e1LineRiseType"] = int(one_line_rise_type)
    obj["m_eContourDropType"] = int(contour_drop_type)
    obj["m_eContourRiseType"] = int(contour_rise_type)
    obj["m_bUseAnnoScaleFor1LineFittings"] = bool(use_anno_scale_for_1line)
    return _settings_record("CableTraySettingsElem", "cable-tray-settings", eid, obj)


#: Piping-system CLASSIFICATION codes that carry a per-classification
#: routing setting (the MEP system classification enum -- interface
#: constants; the 14 codes below are the piping classifications:
#: 7 supply hydronic, 8 return hydronic, 15 sanitary, 16 vent, 17 domestic
#: hot water, 18 domestic cold water, 19 fire protection wet, 20 fire
#: protection dry, 21 fire preaction, 22 fire other, 23 other pipe,
#: 24-26 fitting/global [names INFERRED from the API's
#: MEPSystemClassification enum order]).
PIPE_SYSTEM_CLASSIFICATIONS: Tuple[int, ...] = (7, 8, 15, 16, 17, 18, 19, 20,
                                                 21, 22, 23, 24, 25, 26)
#: Duct-system classification codes carrying a routing setting
#: (0 undefined / 1 supply air / 2 return air / 3 exhaust air / 4 other).
DUCT_SYSTEM_CLASSIFICATIONS: Tuple[int, ...] = (0, 1, 2, 3, 4)
#: duct shape codes for the rise/drop symbol map (1 rectangular / 2 round
#: / 3 oval [INFERRED]) -> OUR rise/drop symbol code per shape.
DUCT_RISE_DROP_BY_SHAPE: Dict[int, int] = {1: 1, 2: 1, 3: 1}


def pipe_settings(*, ids: IdArg = None, elem_id: int = None,
                  size_suffix: str = MEP_ROUND_SIZE_SUFFIX, size_prefix: str = "",
                  connector_separator: str = MEP_CONNECTOR_SEPARATOR,
                  system_routing: Optional[Dict[int, dict]] = None,
                  slopes_in_per_ft: Sequence[float] = tuple(PIPE_SLOPES_IN_PER_FT),
                  specific_angles_deg: Sequence[float] = tuple(MEP_SPECIFIC_ANGLES_DEG),
                  fitting_annotation_size_in: float = MEP_ANNOTATION_SIZE_IN,
                  rise_drop_annotation_size_in: float = MEP_ANNOTATION_SIZE_IN,
                  elbow_increment_deg: float = 1.0,
                  connector_tolerance_deg: float = 10.0,
                  contour_rise_type: int = 1, contour_drop_type: int = 3,
                  one_line_bend_rise_type: int = 1, one_line_bend_drop_type: int = 3,
                  one_line_junction_rise_type: int = 1,
                  one_line_junction_drop_type: int = 3,
                  fitting_angle_usage: int = 0,
                  use_anno_scale_for_1line: bool = True,
                  allow_conversion_per_system: bool = True,
                  closed_loop_hydronic_analysis: bool = False,
                  pressure_loss_server: Optional[dict] = None,
                  flow_conversion_server: Optional[dict] = None,
                  cell_list: bool = False) -> TypeRecord:
    """The document's ``RbsPipeSettingsElem`` (Mechanical Settings >
    Pipe: size punctuation, per-classification routing offsets & pipe
    types, slope palette, fitting angle set, annotation sizes, rise/drop
    symbols, calculation servers).

    ``system_routing`` = {classification-code: {"offset_ft", "min_length_ft",
    "branch_offset_ft", "perimeter_inset_ft", "type_id" (RbsPipeType),
    "branch_type_id"}} over :data:`PIPE_SYSTEM_CLASSIFICATIONS` (defaults =
    OUR routing conventions, pipe types -1 = auto).  Slopes are stored as
    the dimensionless rise ratio scaled by 12 (in/ft).  The two server
    descriptors default to NONE (see :func:`_server_info`).  [VERIFIED
    byte-exact vs rme 293122 (its own values fed back).]"""
    eid = _alloc(ids, elem_id)
    obj = _element("RbsPipeSettingsElem", eid, cell_list=cell_list)
    obj["m_strPipeSizeSuffix"] = str(size_suffix)
    obj["m_strPipeSizePrefix"] = str(size_prefix)
    obj["m_strPipeConnectorSeparator"] = str(connector_separator)
    obj["m_flatOnTop"] = "FOT"
    obj["m_flatOnBottom"] = "FOB"
    obj["m_setUp"] = "SU"
    obj["m_setDown"] = "SD"
    obj["m_centerline"] = "="
    routing = system_routing
    if routing is None:
        routing = {c: {} for c in PIPE_SYSTEM_CLASSIFICATIONS}
    rows, type_ids = [], []
    for code, s in sorted(routing.items()):
        tid = int(s.get("type_id", INVALID))
        btid = int(s.get("branch_type_id", tid))
        rows.append({"first": int(code), "second": {
            "m_dOffset": float(s.get("offset_ft", MEP_MAIN_OFFSET_FT)),
            "m_dMinLength": float(s.get("min_length_ft", MEP_MIN_LENGTH_FT)),
            "m_dBranchOffset": float(s.get("branch_offset_ft", MEP_BRANCH_OFFSET_FT)),
            "m_dPerimeterInsetLength": float(s.get("perimeter_inset_ft", MEP_PERIMETER_INSET_FT)),
            "m_typeId": tid, "m_branchTypeId": btid}})
        type_ids += [t for t in (tid, btid) if t not in (None, INVALID)]
    obj["m_mapSystemTypeToPipeSettings"] = rows
    obj["m_pipeSlopes"] = [float(s) for s in slopes_in_per_ft]
    obj["m_specificAngles"] = [{"first": float(a), "second": True} for a in specific_angles_deg]
    obj["m_dPipeFittingAnnotationSize"] = inches(fitting_annotation_size_in)
    obj["m_dPipeElbowIncrementAngle"] = math.radians(elbow_increment_deg)
    obj["m_dPipeRiseDropAnnoSize"] = inches(rise_drop_annotation_size_in)
    obj["m_dPipeConnectorTolerance"] = math.radians(connector_tolerance_deg)
    obj["m_eDipingContourRiseType"] = int(contour_rise_type)
    obj["m_eDipingContourDropType"] = int(contour_drop_type)
    obj["m_eDiping1LineBendRiseType"] = int(one_line_bend_rise_type)
    obj["m_eDiping1LineBendDropType"] = int(one_line_bend_drop_type)
    obj["m_eDiping1LineJunctionRiseType"] = int(one_line_junction_rise_type)
    obj["m_eDiping1LineJunctionDropType"] = int(one_line_junction_drop_type)
    obj["m_fittingAngleUsage"] = int(fitting_angle_usage)
    obj["m_bPipeUseAnnoScaleFor1LineFittings"] = bool(use_anno_scale_for_1line)
    obj["m_bPipeAllowConversionSettingsPerSystemType"] = bool(allow_conversion_per_system)
    obj["m_enableAnalysisForClosedLoopHydronicPipingNetworks"] = bool(closed_loop_hydronic_analysis)
    obj["m_pressLossCalcServerInfo"] = pressure_loss_server or _server_info()
    obj["m_flowConvertionServerInfo"] = flow_conversion_server or _server_info()
    return _settings_record("RbsPipeSettingsElem", "pipe-settings", eid, obj,
                            deletion_ids=sorted(set(type_ids)),
                            refs={"pipe_types": sorted(set(type_ids)),
                                  "classifications": sorted(int(c) for c in routing)},
                            notes=(["calculation servers not selected (null GUIDs) "
                                    "-- probe row"] if pressure_loss_server is None else []))


def duct_settings(*, ids: IdArg = None, elem_id: int = None,
                  connector_separator: str = MEP_CONNECTOR_SEPARATOR,
                  size_separator: str = MEP_SIZE_SEPARATOR,
                  oval_separator: str = MEP_OVAL_SEPARATOR,
                  round_size_suffix: str = MEP_ROUND_SIZE_SUFFIX,
                  system_routing: Optional[Dict[int, dict]] = None,
                  rise_drop_by_shape: Optional[Dict[int, int]] = None,
                  specific_angles_deg: Sequence[float] = tuple(MEP_SPECIFIC_ANGLES_DEG),
                  air_density_kg_m3: float = STANDARD_AIR_DENSITY_KG_M3,
                  air_viscosity_pa_s: float = STANDARD_AIR_VISCOSITY_PA_S,
                  elbow_increment_deg: float = 1.0,
                  fitting_annotation_size_in: float = MEP_ANNOTATION_SIZE_IN,
                  rise_drop_annotation_size_in: float = MEP_ANNOTATION_SIZE_IN,
                  flex_duct_length_ft: float = MEP_FLEX_MAX_FT,
                  fitting_angle_usage: int = 0,
                  allow_conversion_per_system: bool = True,
                  network_based_calculations: bool = False,
                  use_anno_scale_for_1line: bool = True,
                  pressure_loss_server: Optional[dict] = None,
                  cell_list: bool = False) -> TypeRecord:
    """The document's ``RbsDuctSettingsElem`` (Mechanical Settings > Duct:
    size punctuation per shape, rise/drop symbols per shape, per-
    classification routing offsets & duct types, fitting angle set, standard
    air properties, annotation sizes, flex-duct rule, calculation server).

    ``system_routing`` = {duct-classification: {"main_offset_ft",
    "main_min_length_ft", "branch_offset_ft", "branch_min_length_ft",
    "branch_flex_max_ft", "perimeter_inset_ft", "main_type_id",
    "branch_type_id", "branch_flex_type_id"}} over
    :data:`DUCT_SYSTEM_CLASSIFICATIONS` (defaults = OUR conventions, types -1
    = auto).  Air density / viscosity = standard air facts converted to the
    file's kg-ft-s internal units.  [VERIFIED byte-exact vs rme 293121
    (its own values fed back).]"""
    eid = _alloc(ids, elem_id)
    obj = _element("RbsDuctSettingsElem", eid, cell_list=cell_list)
    obj["m_centerline"] = "="
    obj["m_flatOnBottom"] = "FOB"
    obj["m_flatOnTop"] = "FOT"
    obj["m_strDuctConnectorSeparator"] = str(connector_separator)
    obj["m_strDuctSizeSeparator"] = str(size_separator)
    obj["m_strOvalDuctSizeSeparator"] = str(oval_separator)
    obj["m_strOvalDuctSizeSuffix"] = ""
    obj["m_strRectDuctSizeSuffix"] = ""
    obj["m_strRoundDuctSizePrefix"] = ""
    obj["m_strRoundDuctSizeSuffix"] = str(round_size_suffix)
    rd = rise_drop_by_shape or dict(DUCT_RISE_DROP_BY_SHAPE)
    obj["m_mapDuctRiseDropSettings"] = [{"first": int(k), "second": int(v)}
                                       for k, v in sorted(rd.items())]
    routing = system_routing
    if routing is None:
        routing = {c: {} for c in DUCT_SYSTEM_CLASSIFICATIONS}
    rows, type_ids = [], []
    for code, s in sorted(routing.items()):
        mt = int(s.get("main_type_id", INVALID))
        bt = int(s.get("branch_type_id", mt))
        ft_ = int(s.get("branch_flex_type_id", INVALID))
        rows.append({"first": int(code), "second": {
            "m_dMainOffset": float(s.get("main_offset_ft", MEP_MAIN_OFFSET_FT)),
            "m_dMainMinLength": float(s.get("main_min_length_ft", MEP_MIN_LENGTH_FT)),
            "m_dBranchOffset": float(s.get("branch_offset_ft", MEP_BRANCH_OFFSET_FT)),
            "m_dBranchMinLength": float(s.get("branch_min_length_ft", MEP_MIN_LENGTH_FT)),
            "m_dBranchFlexMaxLength": float(s.get("branch_flex_max_ft", MEP_FLEX_MAX_FT)),
            "m_dPerimeterInsetLength": float(s.get("perimeter_inset_ft", MEP_PERIMETER_INSET_FT)),
            "m_mainTypeId": mt, "m_branchTypeId": bt, "m_branchFlexTypeId": ft_}})
        type_ids += [t for t in (mt, bt, ft_) if t not in (None, INVALID)]
    obj["m_mapDuctSystemTypeToSettings"] = rows
    obj["m_pressLossCalcServerInfo"] = pressure_loss_server or _server_info()
    obj["m_setDown"] = "SD"
    obj["m_setDownFromBottom"] = "BD"
    obj["m_setUp"] = "SU"
    obj["m_setUpFromBottom"] = "BU"
    obj["m_specificAngles"] = [{"first": float(a), "second": True} for a in specific_angles_deg]
    obj["m_airDynamicViscosity"] = float(air_viscosity_pa_s) * _PA_S_TO_INTERNAL
    obj["m_dAirDensity"] = float(air_density_kg_m3) * _KG_M3_TO_INTERNAL
    obj["m_dDuctElbowIncrementAngle"] = math.radians(elbow_increment_deg)
    obj["m_dDuctFittingAnnotationSize"] = inches(fitting_annotation_size_in)
    obj["m_dDuctRiseDropAnnoSize"] = inches(rise_drop_annotation_size_in)
    obj["m_dFlexDuctLength"] = float(flex_duct_length_ft)
    obj["m_fittingAngleUsage"] = int(fitting_angle_usage)
    obj["m_bDuctAllowConversionSettingsPerSystemType"] = bool(allow_conversion_per_system)
    obj["m_enableNetworkBasedCalculations"] = bool(network_based_calculations)
    obj["m_bDuctUseAnnoScaleFor1LineFittings"] = bool(use_anno_scale_for_1line)
    return _settings_record("RbsDuctSettingsElem", "duct-settings", eid, obj,
                            deletion_ids=sorted(set(type_ids)),
                            refs={"duct_types": sorted(set(type_ids)),
                                  "classifications": sorted(int(c) for c in routing)},
                            notes=(["pressure-loss server not selected (null GUID) "
                                    "-- probe row"] if pressure_loss_server is None else []))


# --- the SIZE TABLES --------------------------------------------------------

def _size_data_row(nominal_ft: float, inner_ft: float, outer_ft: float, *,
                   in_size_list: bool = True, used_by_sizing: bool = True) -> dict:
    return {"m_dSize": float(nominal_ft), "m_dInnerDiameter": float(inner_ft),
            "m_dOuterDiameter": float(outer_ft), "m_bInSizeList": bool(in_size_list),
            "m_bUsedBySizing": bool(used_by_sizing)}


#: OUR duct size lists (nominal inches).  Rectangular / oval side sizes
#: follow SMACNA-customary even increments; round diameters follow the
#: standard spiral-duct series [FACTS of the sheet-metal trade; the list
#: extents are our choice].
DUCT_RECT_SIZES_IN: List[float] = ([4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
                                    + [float(x) for x in range(12, 41, 2)]
                                    + [float(x) for x in range(42, 61, 4)]
                                    + [float(x) for x in range(64, 121, 8)])
DUCT_ROUND_SIZES_IN: List[float] = [3, 4, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18,
                                     20, 22, 24, 26, 28, 30, 32, 34, 36, 38,
                                     40, 42, 44, 46, 48, 50, 52, 54, 56, 58, 60]
DUCT_OVAL_SIZES_IN: List[float] = DUCT_RECT_SIZES_IN


def duct_sizes(*, ids: IdArg = None, elem_id: int = None,
               rectangular_in: Sequence[float] = tuple(DUCT_RECT_SIZES_IN),
               oval_in: Sequence[float] = tuple(DUCT_OVAL_SIZES_IN),
               round_in: Sequence[float] = tuple(DUCT_ROUND_SIZES_IN),
               cell_list: bool = False) -> TypeRecord:
    """The document's ``RbsDuctSizesElem`` = the duct size lists per shape.
    DEFINITION: ``m_shapeSizes`` = [{first: shape code (0 rectangular /
    1 oval / 2 round [VERIFIED order vs rme 293120]), second: {m_sizeData
    [{m_dSize (ft), m_dInnerDiameter 12.0, m_dOuterDiameter 12.0 (the
    unused-for-ducts diameter columns carry the constant 12.0),
    in-list / sizing flags}]}}].  Sizes in inches (converted to feet)."""
    eid = _alloc(ids, elem_id)
    obj = _element("RbsDuctSizesElem", eid, cell_list=cell_list)

    def rows(vals):
        return {"m_sizeData": [_size_data_row(inches(v), 12.0, 12.0) for v in vals]}
    obj["m_shapeSizes"] = [
        {"first": 0, "second": rows(rectangular_in)},
        {"first": 1, "second": rows(oval_in)},
        {"first": 2, "second": rows(round_in)},
    ]
    return _settings_record("RbsDuctSizesElem", "duct-sizes", eid, obj,
                            refs={"rect": len(rectangular_in), "oval": len(oval_in),
                                  "round": len(round_in)})


def pipe_sizes(material_map: Dict[int, Dict[int, Dict[int, Sequence]]], *,
               ids: IdArg = None, elem_id: int = None,
               cell_list: bool = False) -> TypeRecord:
    """The document's ``RbsPipeSizesElem`` = pipe size tables keyed by the
    pipe MATERIAL / CONNECTION / SCHEDULE catalog elements:
    ``material_map`` = {RbsPipeMaterialType id: {RbsPipeConnectionType id:
    {RbsPipeScheduleType id: [(nominal_in, inner_in, outer_in), ...]}}}.
    DEFINITION: ``m_materialMapConnections`` -> per material
    ``m_connectionMapSchedules`` -> per connection ``m_scheduleMapSizes`` ->
    per schedule ``m_sizeData`` rows.  The catalog elements are the piping
    catalog's territory (RbsPipeMaterialType / -ConnectionType /
    -ScheduleType constructors); this table just wires their ids.
    [VERIFIED structure vs rme 293159.]"""
    eid = _alloc(ids, elem_id)
    obj = _element("RbsPipeSizesElem", eid, cell_list=cell_list)
    mats, dele = [], []
    for mat_id, conns in sorted(material_map.items()):
        conn_rows = []
        for conn_id, scheds in sorted(conns.items()):
            sched_rows = []
            for sched_id, sizes in sorted(scheds.items()):
                data = []
                for r in sizes:
                    if isinstance(r, dict):
                        data.append(_size_data_row(inches(r["nominal_in"]),
                                                   inches(r.get("inner_in", 0.0)),
                                                   inches(r.get("outer_in", 0.0)),
                                                   in_size_list=r.get("in_size_list", True),
                                                   used_by_sizing=r.get("used_by_sizing", True)))
                    else:
                        nom, idn, od = (list(r) + [0.0, 0.0])[:3]
                        data.append(_size_data_row(inches(nom), inches(idn), inches(od)))
                sched_rows.append({"first": int(sched_id), "second": {"m_sizeData": data}})
                dele.append(int(sched_id))
            conn_rows.append({"first": int(conn_id), "second": {"m_scheduleMapSizes": sched_rows}})
            dele.append(int(conn_id))
        mats.append({"first": int(mat_id), "second": {"m_connectionMapSchedules": conn_rows}})
        dele.append(int(mat_id))
    obj["m_materialMapConnections"] = mats
    return _settings_record("RbsPipeSizesElem", "pipe-sizes", eid, obj,
                            deletion_ids=sorted(set(dele)),
                            refs={"materials": [int(k) for k in material_map]})


# ampacity temperature-correction bands: (Celsius band edges, factor) --
# NEC Table 310.15(B)(1) ambient-temperature correction factors for the
# 30 C-rated columns [FACT], expressed in Kelvin as the file stores them.
NEC_TEMP_CORRECTION_75C: List[Tuple[float, float, float]] = [
    (21.0, 25.0, 1.05), (26.0, 30.0, 1.00), (31.0, 35.0, 0.94),
    (36.0, 40.0, 0.88), (41.0, 45.0, 0.82), (46.0, 50.0, 0.75),
    (51.0, 55.0, 0.67), (56.0, 60.0, 0.58), (61.0, 65.0, 0.47),
    (66.0, 70.0, 0.33),
]
NEC_TEMP_CORRECTION_90C: List[Tuple[float, float, float]] = [
    (21.0, 25.0, 1.04), (26.0, 30.0, 1.00), (31.0, 35.0, 0.96),
    (36.0, 40.0, 0.91), (41.0, 45.0, 0.87), (46.0, 50.0, 0.82),
    (51.0, 55.0, 0.76), (56.0, 60.0, 0.71), (61.0, 65.0, 0.65),
    (66.0, 70.0, 0.58), (71.0, 75.0, 0.50), (76.0, 80.0, 0.41),
]
#: equipment-grounding-conductor sizes by overcurrent rating (amps ->
#: AWG copper) [FACT: NEC Table 250.122].
NEC_GROUND_SIZES_CU: List[Tuple[float, str]] = [
    (15.0, "14"), (20.0, "12"), (60.0, "10"), (100.0, "8"), (200.0, "6"),
    (300.0, "4"), (400.0, "3"), (500.0, "2"), (600.0, "1"), (800.0, "1/0"),
    (1000.0, "2/0"), (1200.0, "3/0"), (1600.0, "4/0"), (2000.0, "250"),
    (2500.0, "350"), (3000.0, "400"), (4000.0, "500"), (5000.0, "700"),
    (6000.0, "800"),
]


def _c_to_k(c: float) -> float:
    return float(c) + 273.15


def wire_sizes(material_tables: Dict[int, dict], *, ids: IdArg = None,
               elem_id: int = None,
               power_factor_tables: Optional[Dict[int, dict]] = None,
               wire_diameters_in: Optional[Dict[str, float]] = None,
               initialized: int = 0,
               cell_list: bool = False) -> TypeRecord:
    """The document's ``RbsWireSizesElem`` = the electrical wiring data
    tables (ampacity per wire material / temperature rating / size, ground-
    conductor sizing, ambient-temperature correction, impedance power-factor
    tables, bare-conductor diameters).

    ``material_tables`` = {RbsWireMaterialType id: {
        "temperature_ratings": {RbsWireTemperatureRatingType id: {
            "sizes": [(size_label, ampacity_A, diameter_in, in_use), ...],
            "insulation_ids": [RbsWireInsulationType ids],
            "correction": [(min_C, max_C, factor), ...]}},
        "ground_sizes": [(rating_A, size_label), ...]}}.
    ``power_factor_tables`` = {material id: {poles: {size_label:
    [(power_factor_pct, impedance_factor), ...]}}} (voltage-drop
    impedance data; {} = none).  ``wire_diameters_in`` = {size_label:
    bare diameter in}.  The KEY elements are the wire catalog's
    RbsWireMaterialType / -TemperatureRatingType / -InsulationType
    symbols (rvt.genesis.types constructors); the DATA is NEC (facts, see
    house_standard.WIRE_AMPACITY_TABLE / this module's NEC_* tables).
    [VERIFIED structure vs rme 293190 / rst 102410.]"""
    eid = _alloc(ids, elem_id)
    obj = _element("RbsWireSizesElem", eid, cell_list=cell_list)
    mats, dele = [], []
    for mat_id, tab in sorted(material_tables.items()):
        temp_rows = []
        for tr_id, tdata in sorted((tab.get("temperature_ratings") or {}).items()):
            sizes = [{"m_strSize": str(sz), "m_dAmpacity": float(amp),
                      "m_dDiameter": inches(dia), "m_bInUse": int(bool(use))}
                     for (sz, amp, dia, *rest) in (
                         [(s[0], s[1], s[2], (s[3] if len(s) > 3 else True))
                          for s in tdata.get("sizes", [])])
                     for use in [rest[0] if rest else True]]
            ins = [int(i) for i in tdata.get("insulation_ids", [])]
            temp_rows.append({"first": int(tr_id), "second": {
                "m_arrWireSizes": sizes, "m_setInsulationIds": ins}})
            dele += [int(tr_id)] + ins
        ground = [{"first": float(a), "second": str(sz)}
                  for a, sz in tab.get("ground_sizes", [])]
        corr = []
        for tr_id, tdata in sorted((tab.get("temperature_ratings") or {}).items()):
            factors = [{"m_dMin": _c_to_k(lo), "m_dMax": _c_to_k(hi),
                        "m_dFactor": float(f)}
                       for lo, hi, f in tdata.get("correction", [])]
            corr.append({"first": int(tr_id),
                         "second": {"m_dMin": 0.0, "m_dMax": 0.0,
                                    "m_arrFactors": factors}})
        mats.append({"first": int(mat_id), "second": {
            "m_mapTemperatureRatings": temp_rows,
            "m_mapGroundSizes": ground,
            "m_mapCorrectionFactors": corr}})
        dele.append(int(mat_id))
    obj["m_mapMaterials"] = mats
    pf_rows = []
    for mat_id, poles in sorted((power_factor_tables or {}).items()):
        pole_rows = []
        for npole, sizes in sorted(poles.items()):
            entries = [{"first": str(sz),
                        "second": {"m_arrEntries": [{"first": float(pf), "second": float(z)}
                                                    for pf, z in rows]}}
                       for sz, rows in sizes.items()]
            pole_rows.append({"first": int(npole), "second": {"m_mapPowerFactors": entries}})
        pf_rows.append({"first": int(mat_id), "second": {"m_mapPoles": pole_rows}})
        dele.append(int(mat_id))
    obj["m_mapPowerFactors"] = pf_rows
    obj["m_mapWireDiameters"] = [{"first": str(k), "second": inches(v)}
                                 for k, v in sorted((wire_diameters_in or {}).items())]
    obj["m_bInitialized"] = int(initialized)
    return _settings_record("RbsWireSizesElem", "wire-sizes", eid, obj,
                            deletion_ids=sorted(set(dele)),
                            refs={"materials": sorted(int(k) for k in material_tables)},
                            notes=["ampacities NEC 310.16, ground sizes NEC 250.122, "
                                   "correction NEC 310.15(B)(1) -- facts"])


def wire_sizes_from_house_table(material_ids: Dict[str, int],
                                temperature_ids: Dict[str, int],
                                insulation_ids: Dict[str, int], *,
                                ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """Build :func:`wire_sizes` from the own-content house standard's NEC
    ampacity data (``house_standard.WIRE_AMPACITY_TABLE`` = Cu/Al x 75/90 C
    columns of NEC Table 310.16 + Chapter 9 Table 8 diameters).
    ``material_ids`` = {"Copper": id, "Aluminum": id}; ``temperature_ids``
    = {"75": id, "90": id}; ``insulation_ids`` = {name: id} (all listed
    against every rating).  The referenced elements are the wire catalog's
    RbsWireMaterialType / RbsWireTemperatureRatingType /
    RbsWireInsulationType symbols."""
    from .house_standard import WIRE_AMPACITY_TABLE
    tables: Dict[int, dict] = {}
    diameters: Dict[str, float] = {}
    corr = {"75": NEC_TEMP_CORRECTION_75C, "90": NEC_TEMP_CORRECTION_90C}
    for mat_name, mid in material_ids.items():
        by_temp = WIRE_AMPACITY_TABLE.get(mat_name) or {}
        trs = {}
        for temp_name, tid in temperature_ids.items():
            rows = by_temp.get(temp_name)
            if not rows:
                continue
            for size, dia_in, _amp in rows:
                diameters.setdefault(size, dia_in)
            trs[tid] = {"sizes": [(size, amp, dia_in, True) for size, dia_in, amp in rows],
                        "insulation_ids": sorted(insulation_ids.values()),
                        "correction": corr.get(temp_name, [])}
        tables[mid] = {"temperature_ratings": trs,
                       "ground_sizes": (list(NEC_GROUND_SIZES_CU)
                                        if mat_name.lower().startswith("cop") else [])}
    return wire_sizes(tables, ids=ids, elem_id=elem_id, wire_diameters_in=diameters)


# ===========================================================================
# 6. THE SMALL SINGLETONS + THE EMPTY TRACKERS  (K5d population)
# ===========================================================================
#: The tracker singletons whose entire body is EMPTY containers / false
#: flags = pure regeneration bookkeeping (NO free choice, NO expression):
#: constructed as blank objects with these exact scalar defaults.  A few
#: carry a fixed regenOnly wiring into the MEP settings pair -- see
#: :func:`mep_tracker_constellation`.  [VERIFIED byte-exact bodies vs
#: rst / rme / rac for every class listed.]
EMPTY_TRACKERS: Dict[str, dict] = {
    "AssemblyTracker": {"m_mapTypeInsts": [], "m_symToFamSymCacheMap": [],
                        "m_mapInstToShopDrawings": []},
    "GCSTracker": {"m_gridsChanged": [], "m_columnsChanged": [],
                   "m_affectedGridIntersections": [], "m_gridIntDB": [],
                   "m_gridIntersections": [], "m_colGridMap": []},
    "KeynoteTagsOnSheetsTracker": {"m_sheetToCloudsMap": [], "m_sheetIdsToUpdate": []},
    "RevisionCloudsOnSheetsTracker": {"m_sheetToCloudsMap": [], "m_sheetIdsToUpdate": []},
    "SheetsInSheetCollectionTracker": {"m_sheetCollectionToSheetsMap": []},
    "LayoutNodesTracker": {"m_isTrackerActive": False, "m_layoutElementsToDelete": []},
    "MEPComponentTracker": {"m_componentsWithSizeChanges": [], "m_componentsReloaded": [],
                            "m_dirtyLayoutNodes": [], "m_movedLayoutNodes": []},
    "MEPNetworkTracker": {"m_isTrackerActive": False, "m_changedElements": [],
                          "m_component2BaseSegmentMap": []},
    "MEPSystemTracker": {"m_systemsChanged": [], "m_systemsChangedDelayed": [],
                         "m_fixturesAdded": [], "m_systemsToCheckForSplit": [],
                         "m_elemsToUpdateCalculate": [], "m_elemsToValidateCenterline": [],
                         "m_layoutManagerSeeds": [], "m_layoutManagerSeedsForFullRegen": [],
                         "m_connectorOperations": [], "m_hasDeletedFixtures": 0,
                         "m_bNeedToUpdateSystemBrowser": False,
                         "m_changedCalculationServices": [], "m_movedSystemMembers": []},
    "MEPNetworkDataElem": {"m_component2BaseSegmentMap": []},
    "AnalyticalToPhysicalRelationManager": {},
    "ReactionsUpToDateElem": {"m_upToDate": True},
    "GraphicsCache": {},
    "ExternalParamLock": {},
    "DaylightSourceIdSet": {"m_daylightIdSet": []},
    "WorksetVisibilitySettingsElem": {"m_invisibleWorksets": []},
    "Dwg2dExportUserSettingsData": {},
    "STEPExportSettings": {},
    "ZoneScheme": {},
    "RvtLinkInstanceAppearanceParentElem": {},
    "SketchGridAppearanceParentElem": {},
    "FabricationServiceSettings": {"m_serviceToFluidMap": []},
    "CurtaSystemFaceManager": {"m_dividedSurfaceId": INVALID, "m_cSystemId": INVALID,
                               "m_cGDrivTag": -1, "m_cuSyFaCoCounter": 0},
    "StructuralConnectionSettings": {"m_includeWarningControls": True},
    "CircuitNamingTypeSetting": {"m_circuitNamingSchemeId": INVALID},
}
#: cell-list form per tracker class (True = CellList{PatternHelper},
#: else null) [VERIFIED majority form of the corpus specimens]
_TRACKER_CELL_LIST = {"ExternalParamLock", "DaylightSourceIdSet", "ZoneScheme"}


def tracker(class_name: str, *, ids: IdArg = None, elem_id: int = None,
            regen_only: Iterable[int] = (), overlay: Optional[dict] = None) -> TypeRecord:
    """One of the EMPTY TRACKER / bookkeeping singletons in
    :data:`EMPTY_TRACKERS` (its whole content = empty containers).
    ``regen_only`` wires the element regeneration edges the MEP tracker
    constellation carries (see :func:`mep_tracker_constellation`);
    ``overlay`` overrides body fields."""
    if class_name not in EMPTY_TRACKERS:
        raise KeyError(f"{class_name} is not an empty-tracker class")
    body = dict(EMPTY_TRACKERS[class_name])
    if overlay:
        body.update(overlay)
    kind = class_name[0].lower() + class_name[1:]
    return _generic(class_name, kind, ids, elem_id, body,
                    cell_list=(class_name in _TRACKER_CELL_LIST),
                    regen_only=regen_only)


def mep_tracker_constellation(ids: IdArg, duct_settings_id: int,
                              pipe_settings_id: int) -> List[TypeRecord]:
    """The five MEP bookkeeping singletons WITH their fixed regeneration
    wiring [VERIFIED identical wiring rst / rme / rac]:
    MEPComponentTracker (leaf); LayoutNodesTracker -> {component};
    MEPSystemTracker -> {duct settings, pipe settings, component, layout};
    MEPNetworkDataElem -> {network tracker}; MEPNetworkTracker -> {duct
    settings, pipe settings, component, network data}."""
    comp = tracker("MEPComponentTracker", ids=ids)
    layout = tracker("LayoutNodesTracker", ids=ids, regen_only=[comp.elem_id])
    system = tracker("MEPSystemTracker", ids=ids,
                     regen_only=[duct_settings_id, pipe_settings_id,
                                 comp.elem_id, layout.elem_id])
    ndata_id = _alloc(ids)
    ntrk = tracker("MEPNetworkTracker", ids=ids,
                   regen_only=[duct_settings_id, pipe_settings_id, comp.elem_id, ndata_id])
    ndata = tracker("MEPNetworkDataElem", elem_id=ndata_id, regen_only=[ntrk.elem_id])
    return [comp, layout, system, ntrk, ndata]


def gcs_tracker(ids: IdArg = None, elem_id: int = None, *,
                units_id: int = INVALID) -> TypeRecord:
    """The graphical-column-schedule tracker; regenerates on the document's
    units (``regen_only`` = [UnitsElem]) [VERIFIED rst/rme/rac -> 19236]."""
    ro = [units_id] if units_id not in (None, INVALID) else []
    return tracker("GCSTracker", ids=ids, elem_id=elem_id, regen_only=ro)


def auto_cam_settings(*, ids: IdArg = None, elem_id: int = None,
                      show_compass: bool = True) -> TypeRecord:
    """``AutoCamSettingsElem`` = the ViewCube / SteeringWheels HOME view
    state: no home set (all zeros, ``m_hasSetHome`` false,
    ``m_homeProjToPageScale`` -1), compass shown.  [VERIFIED byte-exact
    vs rst 102842.]"""
    body = {
        "m_dbDrawingIdHomeIsSet": INVALID, "m_homeBottomFOV": 0.0,
        "m_homeCenterXYZ": [0.0, 0.0, 0.0], "m_homeEyeXYZ": [0.0, 0.0, 0.0],
        "m_homeLeftFOV": 0.0, "m_homeOrthoHeight": 0.0, "m_homeOrthoWidth": 0.0,
        "m_homePivotXYZ": [0.0, 0.0, 0.0], "m_homeProjToPageOriginX": 0.0,
        "m_homeProjToPageOriginY": 0.0, "m_homeProjToPageScale": -1.0,
        "m_homeRightFOV": 0.0, "m_homeTopFOV": 0.0, "m_homeUpXYZ": [0.0, 0.0, 0.0],
        # scene frame: front = +Y (model north), up = +Z [VERIFIED 3/3]
        "m_sceneCenterXYZ": [0.0, 0.0, 0.0], "m_sceneFrontXYZ": [0.0, 1.0, 0.0],
        "m_sceneRadius": 0.0, "m_sceneUpXYZ": [0.0, 0.0, 1.0],
        "m_hasSetHome": False, "m_lockToCurrentSel": False,
        "m_showCompass": bool(show_compass)}
    return _generic("AutoCamSettingsElem", "auto-cam-settings", ids, elem_id, body)


def halftone_underlay_settings(*, ids: IdArg = None, elem_id: int = None,
                               line_pattern_id: int = INVALID, pen: int = -1,
                               brightness_pct: int = 50, apply_halftone: bool = True,
                               cell_list: bool = True) -> TypeRecord:
    """``HalftoneUnderlaySettings`` (Manage > Halftone/Underlay: the
    underlay line pattern / weight override and the halftone brightness).
    OURS: no pattern / weight override (-1), 50 % brightness (a common
    reprographics halftone).  [VERIFIED byte-exact vs rst 105779.]"""
    return _generic("HalftoneUnderlaySettings", "halftone-underlay", ids, elem_id,
                    {"m_linePatternId": int(line_pattern_id), "m_penNumber": int(pen),
                     "m_halftoneBrightness": int(brightness_pct),
                     "m_bApplyHalftone": bool(apply_halftone)},
                    cell_list=cell_list,
                    deletion_ids=[i for i in (line_pattern_id,) if i not in (None, INVALID) and i > 0])


def multiple_values_indication_settings(*, ids: IdArg = None, elem_id: int = None,
                                        custom_text: str = "",
                                        use_custom: bool = False) -> TypeRecord:
    """``MultipleValuesIndicationSettings`` (Properties palette text shown
    when a multi-selection differs: default ``<varies>`` vs a custom
    string).  [VERIFIED byte-exact vs rst 1471489.]"""
    return _generic("MultipleValuesIndicationSettings", "multiple-values-indication",
                    ids, elem_id, {"m_customValue": str(custom_text),
                                   "m_custom": bool(use_custom)})


def workset_visibility_settings(*, ids: IdArg = None, elem_id: int = None,
                                invisible_worksets: Sequence[int] = ()) -> TypeRecord:
    """``WorksetVisibilitySettingsElem`` (default workset visibility: the
    list of worksets hidden by default; none)."""
    return _generic("WorksetVisibilitySettingsElem", "workset-visibility", ids, elem_id,
                    {"m_invisibleWorksets": [int(x) for x in invisible_worksets]})


def _status_colors(pairs: Sequence[Tuple[int, int, bool]]) -> list:
    return [{"first": int(code), "second": {"m_lineColor": int(col), "m_apply": bool(ap)}}
            for code, col, ap in pairs]


#: OUR worksharing-display colours (COLORREF): ownership statuses
#: (0 owned-by-me = green, 1 owned-by-others = amber, 2 not owned = grey)
#: and update statuses (0 up-to-date, 1 modified locally = blue,
#: 2 updated in central = orange, 3 conflict = red).  Autodesk's
#: 0x7100 green triplet is not reproduced.
WORKSHARING_OWNERSHIP_COLORS = [(0, rgb(46, 139, 87), True),
                                (1, rgb(230, 138, 0), True),
                                (2, rgb(150, 150, 150), True)]
WORKSHARING_UPDATE_COLORS = [(0, rgb(46, 139, 87), False),
                             (1, rgb(30, 100, 200), False),
                             (2, rgb(230, 120, 20), False),
                             (3, rgb(200, 30, 30), False)]


def worksharing_view_mode_settings(*, ids: IdArg = None, elem_id: int = None,
                                   project_settings: bool = True,
                                   user: str = "",
                                   removed_users: Sequence[str] = (),
                                   regen_only: Iterable[int] = (),
                                   cell_list: bool = True) -> TypeRecord:
    """``WorksharingViewModeSettings`` (Worksharing Display: the colour
    coding of ownership / update statuses).  A document carries the
    PROJECT-level element (``project_settings`` True, user '') and, once a
    user customises, a per-user copy naming the username whose
    ``regen_only`` points at the project element.  OURS = the project
    element only, our status colours.  [VERIFIED structure vs rst
    130813 / 171476.]"""
    return _generic("WorksharingViewModeSettings", "worksharing-display", ids, elem_id,
                    {"m_ownerOverrides": [],
                     "m_ownershipStatusColors": _status_colors(WORKSHARING_OWNERSHIP_COLORS),
                     "m_removedUserSet": [{"m_str": str(u)} for u in removed_users],
                     "m_updateStatusColors": _status_colors(WORKSHARING_UPDATE_COLORS),
                     "m_user": str(user),
                     "m_worksetAssignmentColors": [],
                     "m_displayUsingUserSettings": False,
                     "m_projectSettings": bool(project_settings)},
                    cell_list=cell_list, regen_only=regen_only)


def coordinate_system_display(*, ids: IdArg = None, elem_id: int = None,
                              category: int = -2000977, size: int = 6,
                              border_size: int = 2) -> TypeRecord:
    """``CoordinateSystemDisplayElem`` = the internal-origin marker (a
    GPoint at the internal origin, category -2000977 'Internal Origin').
    The class has ZERO own schema fields (the marker lives in the seq-102
    body's inherited ``m_oGPoint``); header bbox = a degenerate outline
    at the origin.  [VERIFIED body vs rst 86204: GPoint{GInfo{category
    -1, tag 0, flags 524292}, coord origin, size 6, borderSize 2, flags 0}.
    The specimens ALSO carry regenerable display geometry (a geomSteps
    generator node, a geom table row and a 691-byte GElement rep = the
    origin symbol + flip controls); ours emits the definition only
    (SerializedDummy rep, no gsteps) -- the wall / camera SerializedDummy
    precedents were reader-accepted; [tolerance UNVERIFIED, probe row].]"""
    body = {"m_oGPoint": _ptr("GPoint", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                    "m_flags": 524292},
        "m_coord": [0.0, 0.0, 0.0], "m_size": int(size),
        "m_borderSize": int(border_size), "m_pointFlags": 0})}
    rec = _generic("CoordinateSystemDisplayElem", "internal-origin", ids, elem_id,
                   body, category=category,
                   notes=["origin-marker display geometry (geomSteps + GElement rep) "
                          "omitted: regenerable; SerializedDummy rep [probe]"])
    rec.header["m_pBBox"] = _ptr("Outline", {"m_minmax": [[0.0, 0.0, 0.0],
                                                        [0.0, 0.0, 0.0]]})
    return rec


def active_geo_location_tracking(project_geo_location_id: int, *,
                                 active_geo_location_id: int = INVALID,
                                 ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """``ActiveGeoLocationTrackingElement`` = which ``GeoLocation`` is the
    document's PROJECT position and which is currently ACTIVE (the shared/
    survey position).  Both ids join the deletion set.  [VERIFIED
    byte-exact vs rst 113109 (active = the site location 21748, project =
    the project-position location 111428).]"""
    active = active_geo_location_id if active_geo_location_id not in (None, INVALID) \
        else project_geo_location_id
    return _generic("ActiveGeoLocationTrackingElement", "geo-location-tracking",
                    ids, elem_id,
                    {"m_activeGeoLocationId": int(active),
                     "m_projectGeoLocationId": int(project_geo_location_id)},
                    deletion_ids=sorted({int(active), int(project_geo_location_id)}))


def default_divide_settings(*, ids: IdArg = None, elem_id: int = None,
                            u_spacing_ft: float = 0.0, v_spacing_ft: float = 0.0,
                            path_distance_ft: float = 5.0,
                            layout: int = 2, u_number: int = 10, v_number: int = 10,
                            path_layout: int = 2, path_measurement: int = 0,
                            path_number: int = 6) -> TypeRecord:
    """``DefaultDivideSettings`` (Massing: default divided-surface U/V grid
    and divided-path settings).  OURS = the number-based layout (layout 2)
    10 x 10 divisions, path 6 segments -- a neutral default.  [VERIFIED
    byte-exact vs rst 907053.]"""
    return _generic("DefaultDivideSettings", "default-divide", ids, elem_id,
                    {"m_distance": [float(u_spacing_ft), float(v_spacing_ft)],
                     "m_pathDistance": float(path_distance_ft),
                     "m_layout": [int(layout), int(layout)],
                     "m_number": [int(u_number), int(v_number)],
                     "m_pathLayout": int(path_layout),
                     "m_pathMeasurementType": int(path_measurement),
                     "m_pathNumber": int(path_number)})


#: The COPY/MONITOR MEP-fixture category set (copy-behaviour 1 = allow
#: batch copy, parameter-behaviour 0) = the 16 built-in categories the
#: copy/monitor MEP-fixture tool covers [VERIFIED identical 3/3 samples;
#: ids are BuiltInCategory constants: sprinklers, fire alarm / data /
#: communication / security / nurse-call devices, telephone devices,
#: lighting devices, air terminals, plumbing fixtures, mechanical
#: equipment, lighting fixtures, electrical fixtures / equipment ...].
COPY_MONITOR_CATEGORIES: List[int] = [
    -2008234, -2008232, -2008099, -2008087, -2008085, -2008083, -2008081,
    -2008079, -2008077, -2008075, -2008013, -2001160, -2001140, -2001120,
    -2001060, -2001040,
]


def project_copy_settings(*, ids: IdArg = None, elem_id: int = None,
                          categories: Sequence[int] = tuple(COPY_MONITOR_CATEGORIES),
                          behaviour: Tuple[int, int] = (1, 0)) -> TypeRecord:
    """``ProjectCopySettingsElem`` (Copy/Monitor: per-category copy
    behaviour map).  DEFINITION: ``m_categoryCopyMap`` = [{first:
    BuiltInCategory, second: {first: copy behaviour, second: parameter
    behaviour}}].  [VERIFIED structure vs rst 115987 (16 MEP categories,
    behaviour (1, 0) each).]"""
    return _generic("ProjectCopySettingsElem", "copy-monitor-settings", ids, elem_id,
                    {"m_categoryCopyMap": [
                        {"first": int(c), "second": {"first": int(behaviour[0]),
                                                     "second": int(behaviour[1])}}
                        for c in categories]})


def copy_watch_properties(*, ids: IdArg = None, elem_id: int = None,
                          link_id: int = INVALID,
                          categories: Sequence[int] = tuple(COPY_MONITOR_CATEGORIES),
                          behaviour: Tuple[int, int] = (1, 0)) -> TypeRecord:
    """``CopyWatchProperties`` = the copy/monitor state of a document
    (type-copy map, watched links, category copy map).  OURS = the
    NO-LINK default: empty type/param/copied maps, ``m_linkId`` -1, the
    same category copy map as :func:`project_copy_settings`.  A file WITH
    a Revit link carries the link's watch tables here.  [VERIFIED
    structure vs rst 1250031; empty-link form INFERRED.]"""
    obj_overlay = {
        "m_typeCopyMap": [], "m_paramIdToPageMap": [], "m_copiedElemsMap": [],
        "m_linkId": int(link_id), "m_linkedPhaseMap": [],
        "m_paramCopyTypeMap": [], "m_copyOriginalMap": [],
        "m_categoryCopyMap": [
            {"first": int(c), "second": {"first": int(behaviour[0]),
                                         "second": int(behaviour[1])}}
            for c in categories],
    }
    rec = _generic("CopyWatchProperties", "copy-watch", ids, elem_id, obj_overlay,
                   deletion_ids=[i for i in (link_id,) if i not in (None, INVALID)],
                   notes=["no linked model (empty watch tables)"])
    # present-but-empty parameter sets, as the specimen carries all three
    rec.obj["m_pParamValueSetDouble"] = _owned("ParamValueSetDouble", m_paramSet=[])
    rec.obj["m_pParamValueSetInt"] = _owned("ParamValueSetInt", m_paramSet=[])
    rec.obj["m_pParamValueSetAString"] = _owned("ParamValueSetAString", m_paramSet=[])
    return rec


def model_graphics_styles(ids: IdArg, sun_settings_id: int, *,
                          sun_intensity: int = 80, shadow_intensity: int = 60) -> List[TypeRecord]:
    """The two document ``ModelGraphicsStyle`` presets ``<Shading>``
    (render type 3, lighting on) and ``<Raytracing>`` (render type 5,
    hidden-line on) -- named angle-bracket built-in tokens, each pointing
    at the document sun settings (``m_idShadowsSettings``, deletion
    parent).  Intensities = our display defaults.  [VERIFIED byte-exact
    vs rst 54523 / 54525.]"""
    out = []
    for name, render_type, lighting, hlr in (("<Shading>", 3, True, False),
                                            ("<Raytracing>", 5, False, True)):
        body = {"m_sName": name, "m_idShadowsSettings": int(sun_settings_id),
                "m_nSunIntensity": int(sun_intensity), "m_nAmbientIntensity": 0,
                "m_nShadowIntensity": int(shadow_intensity),
                "m_nTransparencyIntensity": 0, "m_viewDisplayRenderType": render_type,
                "m_bLighting": lighting, "m_bHLR": hlr, "m_bCastShadows": False,
                "m_bUseAmbientLighting": False, "m_bShowEdges": True}
        out.append(_generic("ModelGraphicsStyle", "model-graphics-style", ids, None,
                            body, cell_list=True,
                            deletion_ids=[sun_settings_id] if sun_settings_id >= 0 else [],
                            refs={"sun": int(sun_settings_id)}))
    return out


def area_settings(*, ids: IdArg = None, elem_id: int = None,
                  boundary_location: int = 0,
                  compute_room_volumes: bool = False,
                  room_bounding_types: Optional[Sequence[bool]] = None) -> TypeRecord:
    """``AreaSettingsElem`` (Area and Volume Computations: boundary
    location 0 = at wall finish, room-volume computation off, the 8 room-
    bounding element-type flags = all element types bound rooms except
    slot 0 [VERIFIED identical flag vector 3/3 samples]).  Regenerates
    on plan / section views (wildcards).  [VERIFIED byte-exact vs rst
    85092.]"""
    flags = list(room_bounding_types) if room_bounding_types is not None \
        else [False, True, True, True, True, True, True, True]
    return _generic("AreaSettingsElem", "area-volume-settings", ids, elem_id,
                    {"m_BoundaryLocation": int(boundary_location),
                     "m_computeRoomVolumes": bool(compute_room_volumes),
                     "m_roomBoundingTypes": [bool(x) for x in flags]})


def revision_numbering_sequences(ids: IdArg) -> List[TypeRecord]:
    """The two built-in ``RevisionNumberingSequence`` elements every
    document has: 'Numeric' (start 1, step 1, min 1 digit) and
    'Alphanumeric' (the A..Z series).  Their names are the fixed built-in
    sequence names; the A..Z alphabet and 1..N series are the universal
    revision-lettering conventions [VERIFIED byte-exact vs rst
    1471493 / 1471494].  Category -2006071; both carry the internal
    design-option sentinel -4 (like a type's owned companions)."""
    num = _generic("RevisionNumberingSequence", "revision-sequence-numeric", ids, None,
                   {"m_oRevisionSettings": _ptr("NumericRevisionSettings", {
                       "m_prefixStr": "", "m_suffixStr": "", "m_incrementSize": 1,
                       "m_minimumDigits": 1, "m_startNumber": 1}),
                    "m_sequenceName": "Numeric",
                    "m_designOptionId": -4}, category=-2006071)
    alpha = _generic("RevisionNumberingSequence", "revision-sequence-alphanumeric", ids, None,
                     {"m_oRevisionSettings": _ptr("AlphanumericRevisionSettings", {
                         "m_prefixStr": "", "m_suffixStr": "",
                         "m_sequence": [{"m_str": chr(ord("A") + i)} for i in range(26)]}),
                      "m_sequenceName": "Alphanumeric",
                      "m_designOptionId": -4}, category=-2006071)
    return [num, alpha]


def project_revision(*, ids: IdArg = None, elem_id: int = None,
                     sequence_id: int, sequence_number: int = 1,
                     description: str = "", date: str = "", number: str = "1",
                     issued: bool = False, issued_by: str = "", issued_to: str = "",
                     visibility: int = 1, cell_list: bool = True) -> TypeRecord:
    """A ``ProjectRevision`` (a Sheet Issues/Revisions row): description,
    date, issued-by/to, number, its numbering sequence, cloud+tag
    visibility (1 = cloud and tag).  Wildcard: regenerates on
    AllProjectRevisions.  Category -2006070.  OURS: description / date =
    the job's issue data ('' by default; Autodesk's 'Revision 1' /
    'Date 1' placeholders are not reproduced).  [VERIFIED byte-exact vs
    rst 49030.]"""
    return _generic("ProjectRevision", "project-revision", ids, elem_id,
                    {"m_description": str(description), "m_issuedBy": str(issued_by),
                     "m_issuedTo": str(issued_to), "m_date": str(date),
                     "m_numberStr": str(number),
                     "m_revisionNumberingSequenceId": int(sequence_id),
                     "m_revVisible": int(visibility), "m_sequenceNumber": int(sequence_number),
                     "m_issued": bool(issued)},
                    category=-2006070, cell_list=cell_list,
                    deletion_ids=[sequence_id],
                    refs={"sequence": int(sequence_id)})


def all_project_revisions(revision_ids: Sequence[int], numeric_sequence_id: int,
                          alphanumeric_sequence_id: int, *, ids: IdArg = None,
                          elem_id: int = None, revision_numbering: int = 0,
                          min_cloud_spacing_ft: float = 20.0 / MM_PER_FT * MM_PER_FT / 1.0
                          ) -> TypeRecord:
    """``AllProjectRevisions`` = the revision table singleton: the ordered
    revision ids, the two built-in numbering sequences, numbering mode
    (0 = per project) and the minimum revision-cloud arc spacing.
    Wildcard: regenerates on RevisionNumberingSequence.  [VERIFIED
    byte-exact vs rst 49031 (min spacing 0.0656 ft = 20 mm; ours = 3/4",
    an inch-round cloud arc).]"""
    dele = sorted({*[int(r) for r in revision_ids], int(numeric_sequence_id),
                   int(alphanumeric_sequence_id)})
    return _generic("AllProjectRevisions", "revision-table", ids, elem_id,
                    {"m_revisionIds": [int(r) for r in revision_ids],
                     "m_builtInAlphanumericSequenceId": int(alphanumeric_sequence_id),
                     "m_builtInNumericSequenceId": int(numeric_sequence_id),
                     "m_minSpacingForCloud": float(min_cloud_spacing_ft),
                     "m_revisionNumbering": int(revision_numbering)},
                    deletion_ids=dele,
                    refs={"revisions": [int(r) for r in revision_ids],
                          "sequences": [int(numeric_sequence_id), int(alphanumeric_sequence_id)]})


def revision_constellation(ids: IdArg) -> List[TypeRecord]:
    """The complete revisions machinery a document is born with: the two
    numbering sequences + one initial revision + the AllProjectRevisions
    table (returned in dependency order)."""
    num, alpha = revision_numbering_sequences(ids)
    rev = project_revision(ids=ids, sequence_id=num.elem_id, sequence_number=1,
                           number="1")
    table = all_project_revisions([rev.elem_id], num.elem_id, alpha.elem_id, ids=ids,
                                  min_cloud_spacing_ft=0.75 / 12.0)
    # sequences and revision are OWNED by the table (ElemRec owner) [VERIFIED]
    for r in (num, alpha):
        r.refs["owner_id"] = table.elem_id
    return [num, alpha, rev, table]


def view_sheet_set(name: str, *, ids: IdArg = None, elem_id: int = None,
                   drawing_ids: Sequence[int] = (), timestamp: int = 0,
                   sheet_organization_id: int = INVALID,
                   view_organization_id: int = INVALID,
                   automatic: bool = False) -> TypeRecord:
    """A ``ViewSheetSet`` (a named print set of view/sheet DBDrawings).
    Not count-invariant (0..N per file); provided for jobs that publish a
    print set.  [VERIFIED structure vs rst 503760.]"""
    return _generic("ViewSheetSet", "view-sheet-set", ids, elem_id,
                    {"m_name": str(name),
                     "m_timeStampInSeconds": {"m_msb": 0, "m_lsb": int(timestamp)},
                     "m_orderedViewSheetList": {
                         "m_dbDrawingIds": [int(d) for d in drawing_ids],
                         "m_sheetOrganizationId": int(sheet_organization_id),
                         "m_viewOrganizationId": int(view_organization_id),
                         "m_isAutomatic": bool(automatic)}},
                    deletion_ids=[int(d) for d in drawing_ids])


#: OUR default print setup: US Letter portrait, 1:1 zoom, raster quality
#: 300 dpi -- the values a fresh US-imperial document defaults to; the
#: printer-driver strings are the OS's ('<default tray>' = the driver's
#: default source token, kept as the neutral no-selection value).
def print_settings(name: str = "Default", *, ids: IdArg = None, elem_id: int = None,
                   paper_size: str = "Letter", paper_source: str = "<default tray>",
                   paper_size_index: int = 1,
                   paper_dims_tenths_mm: Tuple[int, int] = (2159, 2794),
                   orientation: int = 1, zoom_pct: int = 100, dpi: int = 300,
                   timestamp: int = 0, cell_list: bool = False) -> TypeRecord:
    """A ``PrintSettings`` (a named print setup; a document carries at
    least the current 'Default' setup).  DEFINITION: name, paper
    (size string / dims in 0.1 mm / source), orientation (1 portrait),
    zoom, colour depth 2 (colour), raster dpi, hidden-line 0 (vector),
    the print-filter flags (our conventions: hide scope boxes / reference
    planes / crop boundaries / unreferenced view tags, print rooms).
    [VERIFIED structure vs rst 19895 (US Letter default).]"""
    return _generic("PrintSettings", "print-settings", ids, elem_id, {
        "m_name": str(name),
        "m_PrintParameters": {
            "m_strPaperSize": str(paper_size), "m_strPaperSource": str(paper_source),
            "m_dOriginOffsetX": 0.0, "m_dOriginOffsetY": 0.0,
            "m_nPaperSizeX": int(paper_dims_tenths_mm[0]),
            "m_nPaperSizeY": int(paper_dims_tenths_mm[1]),
            "m_nPaperSource": 4294967295, "m_nPaperIndex": int(paper_size_index),
            "m_OrientationType": int(orientation), "m_PaperPlacementType": 0,
            "m_MarginType": 0, "m_ZoomType": 0, "m_nZoom": int(zoom_pct),
            "m_ColorDepthType": 2, "m_nUserDPI": int(dpi), "m_HLRType": 0,
            "m_PrintFilters": {"m_bControlsInBlue": False, "m_bHideScopeBoxes": True,
                               "m_bHideRefPlanes": True, "m_bMaskCoincidentLines": False,
                               "m_bHideCropBoundaries": True,
                               "m_bHideViewsNotOnSheet": False,
                               "m_bHalftoneThinLines": False,
                               "m_bHideRoomsAreasAndSpaces": True,
                               "m_bHideFlipControl": False}},
        "m_timeStampInSeconds": {"m_msb": 0, "m_lsb": int(timestamp)}},
        cell_list=cell_list)


def route_analysis_settings(*, ids: IdArg = None, elem_id: int = None,
                            ignored_categories: Sequence[int] = (-2000023,),
                            zone_bottom_offset_ft: float = 8.0 / 12.0,
                            zone_top_offset_ft: float = 80.0 / 12.0,
                            minimum_length_ft: float = 1.0,
                            travel_speed_ft_s: float = 4.4,
                            allow_large_geometry: int = 2,
                            ignore_imports: bool = False) -> TypeRecord:
    """``RouteAnalysisSettings`` (Route Analysis: obstacles ignored --
    doors by default --, the analysis-zone bottom/top offsets, minimum path
    length, travel speed).  Ignored categories join the deletion set as
    negative ids [VERIFIED rst 1470390: OST_Doors -2000023 listed in the
    header's m_deletion].  Values: ours (8" / 6'-8" zone = the walkable
    band above the level; 4.4 ft/s = the 3 mph pedestrian pace)."""
    cats = [int(c) for c in ignored_categories]
    return _generic("RouteAnalysisSettings", "route-analysis", ids, elem_id,
                    {"m_ignoredCategoryIds": cats,
                     "m_analysisZoneBottomOffset": float(zone_bottom_offset_ft),
                     "m_analysisZoneTopOffset": float(zone_top_offset_ft),
                     "m_minimumLength": float(minimum_length_ft),
                     "m_travelSpeed": float(travel_speed_ft_s),
                     "m_allowLargeGeometry": int(allow_large_geometry),
                     "m_enableIgnoredCategoryIds": True,
                     "m_ignoreImports": bool(ignore_imports)},
                    deletion_ids=cats)


def mep_hidden_line_settings(*, ids: IdArg = None, elem_id: int = None,
                             line_style_category: int = -2000042,
                             inside_gap_ft: float = 1.0 / 16 / 12,
                             outside_gap_ft: float = 1.0 / 16 / 12,
                             single_line_gap_ft: float = 1.0 / 16 / 12,
                             draw_hidden_line: bool = True) -> TypeRecord:
    """``MEPHiddenLineSettingsElem`` (Mechanical Settings > Hidden Line:
    the gaps drawn where an MEP element crosses under another, and the
    line style = the built-in <Hidden Lines> category -2000042).  The
    style id joins the deletion set (negative built-in) [VERIFIED rst
    1471446].  Gaps ours (1/16")."""
    return _generic("MEPHiddenLineSettingsElem", "mep-hidden-line", ids, elem_id,
                    {"m_insideGap": float(inside_gap_ft),
                     "m_lineStyleId": int(line_style_category),
                     "m_outsideGap": float(outside_gap_ft),
                     "m_singleLineGap": float(single_line_gap_ft),
                     "m_drawHiddenLine": bool(draw_hidden_line)},
                    deletion_ids=[int(line_style_category)])


def fabrication_settings(*, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """``FabricationSettings`` = the fabrication (ITM) database binding;
    OURS = NO fabrication database bound (empty database descriptor, null
    GUID, version 0, cloud version -1).  [VERIFIED byte-exact vs rst
    1218727.]"""
    return _generic("FabricationSettings", "fabrication-settings", ids, elem_id,
                    {"m_oFabricationDatabase": _ptr("FabricationDatabase", {
                        "m_cachedItemFiles": [], "m_cachedServiceIds": [],
                        "m_cloudId": "", "m_description": "", "m_imagesPool": [],
                        "m_itemsPool": [], "m_mem": [], "m_name": "",
                        "m_profiles": [], "m_version": 0.0, "m_cloudVersion": -1,
                        "m_gUID": NULL_GUID, "m_productVersion": 0,
                        "m_unitSystem": 0, "m_isConnected": False,
                        "m_locked": False})})


def fabrication_settings_element(*, ids: IdArg = None, elem_id: int = None,
                                 round_rotation_angles_deg: Sequence[float] = (45.0, 90.0)
                                 ) -> TypeRecord:
    """``FabricationSettingsElement`` (fabrication round-part rotation angle
    snaps; 45/90 deg = the universal fitting rotations)."""
    return _generic("FabricationSettingsElement", "fabrication-round-rotations",
                    ids, elem_id,
                    {"m_rotationAnglesForRound": [float(a) for a in round_rotation_angles_deg]})


#: structural section end-point visibility per category [VERIFIED
#: identical 3/3 samples: -2001079 hidden, -2000035 / -2000032 shown]
SSE_POINT_VISIBILITY: List[Tuple[int, bool]] = [(-2001079, False), (-2000035, True),
                                                  (-2000032, True)]


def sse_point_visibility_settings(*, ids: IdArg = None, elem_id: int = None,
                                  visibility: Optional[Sequence[Tuple[int, bool]]] = None
                                  ) -> TypeRecord:
    """``SSEPointVisibilitySettings`` (structural steel-element analytical
    point visibility per category).  Keys are BuiltInCategory constants,
    in the compiled-in order [VERIFIED 3/3 samples]."""
    vis = list(visibility) if visibility is not None else list(SSE_POINT_VISIBILITY)
    return _generic("SSEPointVisibilitySettings", "sse-point-visibility", ids, elem_id,
                    {"m_visibiltiyMap": [{"first": int(k), "second": bool(v)}
                                         for k, v in vis]})


def area_measure(name: str, description: str, area_type: int, *,
                 ids: IdArg = None, elem_id: int = None,
                 area_type_ids: Sequence[int] = (),
                 plan_topology_id: int = INVALID,
                 default_space_id: int = INVALID) -> TypeRecord:
    """An ``AreaMeasureElem`` = an AREA SCHEME (name, description, the set
    of ``AreaTypeElem`` area types it uses, its ``AreaSchemePlanTopology``
    and the default space/area type).  ``area_type_ids`` /
    ``plan_topology_id`` are the area-catalog's companion elements
    (AreaTypeElem constructors = a further catalog); -1/[] = not built.
    Category -2003201.  [VERIFIED structure vs rst 9490 'Gross Building' /
    9494 'Rentable'.]  OUR default scheme names: see AREA_SCHEMES."""
    dele = [int(x) for x in area_type_ids] + [x for x in (plan_topology_id, default_space_id)
                                               if x not in (None, INVALID)]
    return _generic("AreaMeasureElem", "area-scheme", ids, elem_id,
                    {"m_areaElemDescription": str(description),
                     "m_areaElemName": str(name),
                     "m_areaTypeElemSet": [int(x) for x in area_type_ids],
                     "m_areaSchemePlanTopologyElemId": int(plan_topology_id),
                     "m_defaultSpaceElemId": int(default_space_id),
                     "m_eAreaType": int(area_type)},
                    category=-2003201, cell_list=True,
                    deletion_ids=sorted(set(dele)))


#: OUR area scheme pair (a document has a gross-area and a rentable-area
#: scheme; the METHOD names are the industry standards' -- BOMA 2017 /
#: IPMS -- our descriptions cite them; Autodesk's descriptions are not
#: reproduced).  (name, description, area type code 0 gross / 1 rentable)
AREA_SCHEMES: List[Tuple[str, str, int]] = [
    ("Gross Floor Area", "Constructed floor area to the outside face of "
                         "the exterior enclosure (IPMS 1)", 0),
    ("Rentable Area", "Rentable floor area per the office measurement "
                      "standard (BOMA 2017 / IPMS 3)", 1),
]


def energy_data_settings(*, ids: IdArg = None, elem_id: int = None,
                         ground_level_id: int = INVALID,
                         project_phase_id: int = INVALID,
                         building_type_id: int = INVALID,
                         construction_set_id: int = INVALID,
                         export_category: int = -2000160,
                         postal_code: str = "", reports_folder: str = "",
                         cell_list: bool = True) -> TypeRecord:
    """``EnergyDataSettings`` (Energy Analysis settings: ground plane
    level, project phase, building type (an ``HVACLoadBuildingTypeElem``
    catalog row -- -1 if the HVAC-load catalog is absent), construction
    set, export category rooms, analysis resolutions).  OUR analysis
    parameters: analytical grid 3 ft, core offset 15 ft, sill 2'-6",
    skylight 3 ft, glazing target 40 % (a code-typical envelope
    assumption), no auto-created energy model.  The four view overrides
    key on built-in categories (-2001001 mass zoning etc.).  [VERIFIED
    structure vs rst 115988.]"""
    dele = [x for x in (ground_level_id, project_phase_id, building_type_id,
                        construction_set_id) if x not in (None, INVALID)]
    body = {
        "m_energyModelViewOverrides": [
            _ptr("EnergyModelOverrides", {"m_oGStyleOverrider": None,
                                           "m_categoryId": int(c)})
            for c in (-2001001, -2008185, -2008186, -2001020)],
        "m_postalCode": str(postal_code), "m_reportsFolder": str(reports_folder),
        "m_analyticalGridCellSize": 3.0,
        "m_buildingTypeId": int(building_type_id),
        "m_constructionSetElementId": int(construction_set_id),
        "m_exportCategory": int(export_category),
        "m_groundPlane": int(ground_level_id),
        "m_horizontalVoidThreshold": 1.0, "m_massZoneCoreOffset": 15.0,
        "m_outsideAirChangesRatePerHour": 0.0, "m_outsideAirPerArea": 0.0,
        "m_outsideAirPerPerson": 0.0, "m_percentageGlazing": 0.4,
        "m_percentageSkylights": 0.0,
        "m_projectPhase": int(project_phase_id),
        "m_shadeDepth": 1.5, "m_sillHeight": 2.5, "m_skylightWidth": 3.0,
        "m_sliverSpaceTolerance": 1.0, "m_spaceResolution": 1.5,
        "m_surfaceResolution": 1.0, "m_verticalVoidThreshold": 6.0,
        "m_analysisType": 2, "m_buildingConstructionClass": 3,
        "m_buildingEnvelopeDeterminationMethod": 0, "m_buildingHVACSystem": 2,
        "m_buildingOperatingSchedule": 0, "m_exportComplexity": 1,
        "m_projectReportType": 2, "m_serviceType": 10, "m_shadingSurfaces": 1,
        "m_state": 0, "m_DmeaEnabled": False, "UseHeatingCredits": False,
        "m_createAnalyticalModel": False, "m_energyModel": False,
        "m_exportDefaults": True, "glazingIsShaded": False,
        "m_includeThermalProperties": False, "m_massZoneDividePerimeter": True,
        "m_useAirChangesPerHour": False, "m_useCurrentViewOnly": False,
        "m_useOutsideAirPerArea": False, "m_useOutsideAirPerPerson": False,
    }
    rec = _generic("EnergyDataSettings", "energy-settings", ids, elem_id, body,
                   deletion_ids=dele,
                   refs={"ground_level": int(ground_level_id),
                         "phase": int(project_phase_id),
                         "building_type": int(building_type_id)},
                   notes=(["building type -1 (HVAC-load catalog absent)"]
                          if building_type_id in (None, INVALID) else []))
    rec.obj["m_cellList"] = _ptr("CellList", {"m_cells": [
        _ptr("ExternalFileReferenceCell", {}),
        _ptr("ExternalResourceReferenceCell", {
            "m_externalResourceReferences": [],
            "m_externalResourceReferencesExpanded": []})]}) if cell_list else None
    return rec


#: OUR structural-rebar drawing abbreviations (the plan/section symbols
#: appended to area / path reinforcement tags): major/minor top and
#: bottom marks, each-way / each-face, and the path-reinforcement
#: shorthand.  The SLOT NAMES (setting strings) and their resource ids
#: are Revit's fixed abbreviation slots -- 10 area-reinforcement slots
#: (type tag 0) + 6 path-reinforcement slots (type tag 1) -- interface
#: constants [VERIFIED identical slots / resource ids / tags 3/3 samples];
#: the VALUES are our shorthand (Autodesk's '(T)' / '(B)' / '(I)' / '(E)'
#: / 'TOP' / 'BOT' set is not reproduced).  (setting, our value,
#: resource id, type tag)
REBAR_ABBREVIATIONS: List[Tuple[str, str, int, int]] = [
    ("Slab Top - Major Direction", "T1", 48785, 0),
    ("Slab Top - Minor Direction", "T2", 48786, 0),
    ("Slab Bottom - Major Direction", "B1", 48760, 0),
    ("Slab Bottom - Minor Direction", "B2", 48761, 0),
    ("Wall Interior - Major Direction", "IF1", 48762, 0),
    ("Wall Interior - Minor Direction", "IF2", 48763, 0),
    ("Wall Exterior - Major Direction", "EF1", 48764, 0),
    ("Wall Exterior - Minor Direction", "EF2", 48765, 0),
    ("Each Way", "E.W.", 46967, 0),
    ("Each Face", "E.F.", 46968, 0),
    ("Slab Top", "T", 48526, 1),
    ("Slab Bottom", "B", 48527, 1),
    ("Wall Interior", "IF", 48528, 1),
    ("Wall Exterior", "EF", 48529, 1),
    ("Alternating", "ALT.", 48530, 1),
    ("Alternating Bar Offset", "OFFS.", 48828, 1),
]
REBAR_ABBREVIATION_NAMES: List[str] = ["Area Reinforcement", "Path Reinforcement"]


def reinforcement_settings(*, ids: IdArg = None, elem_id: int = None,
                           abbreviations: Sequence[Tuple[str, str, int, int]] = tuple(REBAR_ABBREVIATIONS),
                           varying_length_suffix: str = "-", numbering_method: int = 0,
                           presentation_in_section: int = 0,
                           presentation_in_view: int = 0,
                           host_structural_rebar: bool = True,
                           shape_defines_end_treatments: bool = False,
                           shape_defines_hooks: bool = True) -> TypeRecord:
    """``ReinforcementSettings`` (Structural Settings > Reinforcement:
    abbreviations table, varying-length rebar suffix, numbering, shape /
    hook / end-treatment policies).  DEFINITION: ``m_abbreviationItems``
    = [{AbbreviationItem{setting name, value, resource id, type tag}}],
    ``m_abbreviationNames`` = the two group names.  Regenerates on
    UnitsElem (regen_only added by the composer).  [VERIFIED structure vs
    rst 137426.]"""
    items = [_ptr("AbbreviationItem", {
        "m_oSetting": _ptr("AStringWrapper", {"m_str": str(nm)}),
        "m_oValue": _ptr("AStringWrapper", {"m_str": str(val)}),
        "m_resourceId": int(rid), "m_typeTag": int(tag)})
        for nm, val, rid, tag in abbreviations]
    return _generic("ReinforcementSettings", "reinforcement-settings", ids, elem_id,
                    {"m_abbreviationItems": items,
                     "m_abbreviationNames": [_ptr("AStringWrapper", {"m_str": n})
                                             for n in REBAR_ABBREVIATION_NAMES],
                     "m_rebarVaryingLengthNumberSuffix": str(varying_length_suffix),
                     "m_numberingMethod": int(numbering_method),
                     "m_rebarPresentationInSection": int(presentation_in_section),
                     "m_rebarPresentationInView": int(presentation_in_view),
                     "m_hostStructuralRebar": bool(host_structural_rebar),
                     "m_rebarShapeDefinesEndTreatments": bool(shape_defines_end_treatments),
                     "m_rebarShapeDefinesHooks": bool(shape_defines_hooks)})


# ===========================================================================
# 7. THE SYSTEM VIEW-FAMILY TABLE  (the 19 real project DBViewTypes)
# ===========================================================================
#: The 19 PROJECT view families every real document carries a DBViewType for
#: (one per ``DBViewType.m_systemFamilyIdx``; the family INDEX is the
#: interface constant, the type NAME is user text = ours, per
#: ``house_standard.gen``).  Plan families carry a plan direction; the
#: annotation-attribute references (callout / section / elevation head
#: types) are annotation content -> -1 in a family-free base.
#: [VERIFIED: the 19 non-family-scoped DBViewTypes of rstbasic
#: (49552..69847 + 1470382), rme and rac; census = the 19 project view
#: types of docs/writer/skeleton-census.md.]
SYSTEM_VIEW_FAMILIES: List[Tuple[str, str]] = [
    ("3d", "3D"),                                # idx 102
    ("walkthrough", "Walkthrough"),              # idx 103
    ("rendering", "Render"),                     # idx 104
    ("schedule", "Schedule"),                    # idx 105
    ("cost_report", "Cost Report"),              # idx 106
    ("sheet", "Sheet"),                          # idx 107
    ("drafting", "Drafting"),                    # idx 108
    ("floor_plan", "Plan"),                      # idx 109 (dir 0)
    ("ceiling_plan", "RCP"),                     # idx 111 (dir 1)
    ("section", "Section"),                      # idx 112
    ("detail", "Detail Section"),                # idx 113
    ("elevation", "Elevation"),                  # idx 114
    ("loads_report", "Loads Report"),            # idx 115
    ("pressure_loss_report", "Pressure Loss Report"),   # idx 116
    ("legend", "Legend"),                        # idx 117
    ("panel_schedule", "Panel Schedule"),        # idx 118
    ("graphical_column_schedule", "Column Schedule"),   # idx 119
    ("structural_plan", "Framing Plan"),         # idx 120 (dir 0)
    ("analysis_report", "Analysis Report"),      # idx 121
]


def system_view_type_table(ids: IdArg, *, poche_material_id: int = INVALID,
                           families: Optional[Sequence[Tuple[str, str]]] = None,
                           name_prefix: bool = True,
                           skip_families: Sequence[str] = ()) -> List[TypeRecord]:
    """The SYSTEM view-family TYPE TABLE: one ``DBViewType`` per project
    view family in :data:`SYSTEM_VIEW_FAMILIES` (minus ``skip_families``,
    e.g. the three the house standard already builds), built by the
    skeleton stream's proven :func:`rvt.genesis.skeleton.new_view_type`
    (m_systemFamilyIdx per family, plan direction for plan families, ref
    label 'SIM.', head/tag/poche references -1 except the 3D family's
    optional poche material).  Names = ``house_standard.gen(<our label>)``."""
    from .house_standard import gen
    fams = list(families) if families is not None else list(SYSTEM_VIEW_FAMILIES)
    out: List[TypeRecord] = []
    for fam_key, label in fams:
        if fam_key in skip_families:
            continue
        eid = _alloc(ids)
        name = gen(label) if name_prefix else label
        el = sk.new_view_type(eid, name, fam_key,
                              poche_material_id=(poche_material_id if fam_key == "3d"
                                                 else INVALID))
        el.obj["m_refLabelStr"] = "SIM."          # our sheet-reference abbreviation
        rec = el.as_type_record()
        rec.kind = "view-type"
        rec.refs["family"] = fam_key
        rec.refs["system_family_idx"] = el.obj.get("m_systemFamilyIdx")
        out.append(rec)
    return out


# ===========================================================================
# 8. THE ADOCUMENT REGISTRY MAP  (where the document object indexes each)
# ===========================================================================
#: Where the ADocument (``Global/Latest``) indexes each settings class the
#: constructors here produce -- :func:`apply_adoc_registry` (used by the
#: S-ladder composer) applies these when it adds our elements to a base
#: file.  A class may have several surfaces.  Forms:
#:   ("uet",)                 -> ``UniqueElementsTracking.m_elemIds`` at the
#:                                 class's fixed position (position from the
#:                                 derived ``UET_POS_TO_CLASS`` map -- 72
#:                                 compiled-in positions, cross-sample stable)
#:   ("appinfo", "Class.field")-> a scalar element-id member of an AppInfo body
#:   ("set", "Class.field")    -> membership in an AppInfo element-id set
#:   ("browser",)             -> ``BrowserOrganizationTracking`` (id set +
#:                                 the per-tree default map + folder cache)
#:   ("navigator",)           -> ``DBViewInfo`` (navigator id + views index);
#:                                 its DBDrawing -> ``DBDrawingInfo`` index
#:   ("sysfam",)              -> ``AppInfoSystemFamiliesNames`` (one document-
#:                                 local key per element)
#:   ("etd",)                 -> ``ElementTrackingData`` per-category rows
#:   ("none",)                -> not referenced by the ADocument at all
#: [VERIFIED per class against the rstbasic ADocument -- every settings
#: element's referrers enumerated (the four "none" classes are genuinely
#: unindexed).]
ADOC_REGISTRY: Dict[str, List[Tuple[str, ...]]] = {
    "PenWidthTableElem": [("appinfo", "PenWidthTableInfo.m_penWidthTableElemId")],
    "BrowserOrganization": [("browser",), ("sysfam",)],
    "RbsDbViewSystemNavigator": [("navigator",)],
    "KeynoteTable": [("uet",), ("set", "KeynoteTableTracking.m_elemIdSet")],
    "KeynotingSystem": [("set", "KeynotingSystemTracking.m_elemIdSet")],
    "InitialViewSettings": [("uet",)],
    "StructSettingsElem": [("uet",)],
    "WallJoinDefaultSetting": [("uet",)],
    "AutoJoinTracker": [("uet",)],
    "ReconcileBrowserSettingsElem": [("uet",)],
    "ConstructionSetProject": [("sysfam",)],
    "RbsWireSettingsElem": [("uet",)],
    "RbsWireSizesElem": [("uet",)],
    "RbsPipeSettingsElem": [("uet",)],
    "RbsPipeSizesElem": [("uet",)],
    "RbsDuctSettingsElem": [("uet",)],
    "RbsDuctSizesElem": [("uet",)],
    "ConduitSettingsElem": [("uet",)],
    "CableTraySettingsElem": [("uet",)],
    "AutoCamSettingsElem": [("uet",)],
    "HalftoneUnderlaySettings": [("appinfo", "HalftoneUnderlaySettingsAppInfo."
                                            "m_halftoneUnderlaySettingsElementId")],
    "MultipleValuesIndicationSettings": [("uet",)],
    "DaylightSourceIdSet": [("none",)],
    "ExternalParamLock": [("appinfo", "ExternalParamTracking.m_externalParamLockId")],
    "AllProjectRevisions": [("uet",)],
    "ProjectRevision": [("etd",)],
    "RevisionNumberingSequence": [("set", "RevisionNumberingSequenceTracking.m_elemIdSet")],
    "WorksetVisibilitySettingsElem": [("uet",)],
    "WorksharingViewModeSettings": [("appinfo", "WorksharingDisplaySettingsTracking."
                                               "m_sharedDisplaySettingsId")],
    "CoordinateSystemDisplayElem": [("uet",)],
    "ActiveGeoLocationTrackingElement": [("uet",)],
    "DefaultDivideSettings": [("uet",)],
    "ProjectCopySettingsElem": [("uet",)],
    "CopyWatchProperties": [("none",)],
    "Dwg2dExportUserSettingsData": [("uet",)],
    "STEPExportSettings": [("uet",)],
    "ModelGraphicsStyle": [("none",)],
    "AnalyticalToPhysicalRelationManager": [("uet",)],
    "ReactionsUpToDateElem": [("uet",)],
    "AreaSettingsElem": [("uet",)],
    "AreaMeasureElem": [("set", "AreaMeasureTracking.m_elemIdSet")],
    "EnergyDataSettings": [("uet",)],
    "ZoneScheme": [("set", "ZoneSchemeTracking.m_elemIdSet")],
    "ReinforcementSettings": [("uet",)],
    "RouteAnalysisSettings": [("uet",)],
    "MEPHiddenLineSettingsElem": [("uet",)],
    "FabricationSettings": [("uet",)],
    "FabricationServiceSettings": [("uet",)],
    "FabricationSettingsElement": [("uet",)],
    "CircuitNamingTypeSetting": [("uet",)],
    "SSEPointVisibilitySettings": [("uet",)],
    "StructuralConnectionSettings": [("uet",)],
    "RvtLinkInstanceAppearanceParentElem": [("uet",)],
    "SketchGridAppearanceParentElem": [("uet",)],
    "CurtaSystemFaceManager": [("none",)],
    "PrintSettings": [("set", "PrintSettingsTracking.m_elemIdSet")],
    "ViewSheetSet": [("set", "ViewSheetSetTracking.m_elemIdSet")],
    "GraphicsCache": [("uet",)],
    "MEPNetworkDataElem": [("uet",)],
    "MEPSystemTracker": [("uet",)],
    "MEPComponentTracker": [("uet",)],
    "MEPNetworkTracker": [("uet",)],
    "LayoutNodesTracker": [("uet",)],
    "AssemblyTracker": [("uet",)],
    "GCSTracker": [("uet",)],
    "KeynoteTagsOnSheetsTracker": [("uet",)],
    "RevisionCloudsOnSheetsTracker": [("uet",)],
    "SheetsInSheetCollectionTracker": [("uet",)],
    "DBViewType": [("sysfam",)],
    # the wire catalog symbols the wire-sizes table keys on (types stream
    # constructors): ElementTrackingData symbol rows + system-family keys +
    # default types, all supplied by the frozen maps
    "RbsWireMaterialType": [("etd",), ("sysfam",)],
    "RbsWireTemperatureRatingType": [("etd",), ("sysfam",)],
    "RbsWireInsulationType": [("etd",), ("sysfam",)],
    "GStyleElem": [("category-tracking",)],       # the catalog rows (CategoryTracking)
    "CategoryElem": [("category-tracking",)],
}


def _appinfo_body(tree: dict, class_name: str) -> Optional[dict]:
    """The value body of the named AppInfo slot in a decoded ADocument tree."""
    mgr = (tree.get("m_pAppInfoManager") or {}).get("value") or {}
    for x in mgr.get("m_appInfoArr") or []:
        if isinstance(x, dict) and x.get("ptr_class") == class_name:
            return x.get("value")
    return None


def apply_adoc_registry(tree: dict, records: Sequence[TypeRecord], *,
                        maps: Optional[dict] = None,
                        default_browser_orgs: Optional[Dict[int, int]] = None,
                        register_views_index: bool = True) -> dict:
    """POPULATE the decoded ADocument ``tree`` (``rvt.adocument`` value dict,
    edited in place) so it indexes ``records`` -- the settings / catalog
    elements just added to the document -- through each class's registry
    surfaces (:data:`ADOC_REGISTRY`).  ``maps`` = the frozen
    ``G1_registry_maps.json`` semantics (UET_POS_TO_CLASS, ETD category
    maps, SFN_TRACKED_CLASSES); ``default_browser_orgs`` = {org type: the
    default organization id} (derived from the records when omitted).
    Returns a report {surface: count} + a list of skipped items.  Only
    ADDS our ids; existing entries are kept (the base's own inventory).
    """
    maps = maps or {}
    report: Dict[str, Any] = {"applied": collections.Counter(), "skipped": []}
    by_class: Dict[str, List[TypeRecord]] = {}
    for r in records:
        by_class.setdefault(r.class_name, []).append(r)
    pos_to_class = maps.get("UET_POS_TO_CLASS") or {}
    class_to_pos = {v: int(k) for k, v in pos_to_class.items()}
    tracked_sfn = set(maps.get("SFN_TRACKED_CLASSES") or [])
    c2sym = maps.get("CLASS_TO_ETD_SYMBOL_CATEGORIES") or {}
    c2elm = maps.get("CLASS_TO_ETD_ELEM_CATEGORIES") or {}

    def uet_set(cls_name: str, eid: int) -> None:
        body = _appinfo_body(tree, "UniqueElementsTracking")
        pos = class_to_pos.get(cls_name)
        if body is None or pos is None:
            report["skipped"].append(f"uet {cls_name}: "
                                     f"{'no UET body' if body is None else 'no slot in map'}")
            return
        arr = body.get("m_elemIds") or []
        while len(arr) <= pos:
            arr.append(INVALID)
        if arr[pos] in (None, INVALID):
            arr[pos] = int(eid)
            report["applied"]["uet"] += 1
        else:
            report["skipped"].append(f"uet[{pos}] {cls_name}: slot already {arr[pos]}")
        body["m_elemIds"] = arr

    def appinfo_scalar(spec: str, eid: int) -> None:
        cls_name, fld = spec.split(".", 1)
        body = _appinfo_body(tree, cls_name)
        if body is None or fld not in body:
            report["skipped"].append(f"appinfo {spec}: absent in the base document")
            return
        if body[fld] in (None, INVALID):
            body[fld] = int(eid)
            report["applied"]["appinfo"] += 1
        else:
            report["skipped"].append(f"appinfo {spec}: already {body[fld]}")

    def appinfo_set(spec: str, eid: int) -> None:
        cls_name, fld = spec.split(".", 1)
        body = _appinfo_body(tree, cls_name)
        if body is None or fld not in body:
            report["skipped"].append(f"set {spec}: absent in the base document")
            return
        lst = body.get(fld)
        if not isinstance(lst, list):
            report["skipped"].append(f"set {spec}: not a container")
            return
        if int(eid) not in lst:
            lst.append(int(eid))
        report["applied"]["set"] += 1

    # -- per class -------------------------------------------------------------
    for cls_name, recs in by_class.items():
        for surface in ADOC_REGISTRY.get(cls_name, []):
            kind = surface[0]
            if kind == "uet":
                for r in recs:
                    uet_set(cls_name, r.elem_id)
            elif kind == "appinfo":
                for r in recs:
                    appinfo_scalar(surface[1], r.elem_id)
            elif kind == "set":
                for r in recs:
                    appinfo_set(surface[1], r.elem_id)
            elif kind == "none":
                report["applied"]["none"] += len(recs)
    # -- the project-browser tracking body -----------------------------------------
    orgs = by_class.get("BrowserOrganization") or []
    if orgs:
        body = _appinfo_body(tree, "BrowserOrganizationTracking")
        if body is None:
            report["skipped"].append("browser: BrowserOrganizationTracking absent")
        else:
            ids = body.setdefault("m_elemIdSet", [])
            for r in orgs:
                if r.elem_id not in ids:
                    ids.append(int(r.elem_id))
            body["m_idMRU"] = INVALID
            body["m_currentBrOrgFamilies"] = []
            body["m_setExpandedNodes"] = []
            body["m_folderNameToIdMap"] = []          # tree-folder cache: regenerated
            defaults = default_browser_orgs
            if defaults is None:
                defaults = {}
                for r in orgs:
                    if r.refs.get("default"):
                        defaults[int(r.refs.get("org_type", 0))] = int(r.elem_id)
            body["m_currentBrOrgTypeToBrOrgMap"] = [
                {"first": int(t), "second": int(i)} for t, i in sorted(defaults.items())]
            report["applied"]["browser"] += len(orgs)
    # -- the system navigator (DBViewInfo / DBDrawingInfo) --------------------------
    for r in by_class.get("RbsDbViewSystemNavigator") or []:
        dbv = _appinfo_body(tree, "DBViewInfo")
        if dbv is None:
            report["skipped"].append("navigator: DBViewInfo absent")
            break
        dbv["m_DBViewSystemNavigatorId"] = int(r.elem_id)
        idx = dbv.setdefault("m_DBViewsIndex", [])
        if register_views_index and r.elem_id not in idx:
            idx.append(int(r.elem_id))
        dr = r.refs.get("drawing")
        ddi = _appinfo_body(tree, "DBDrawingInfo")
        if isinstance(dr, int) and dr >= 0 and ddi is not None:
            didx = ddi.setdefault("m_DBDrawingsIndex", [])
            if dr not in didx:
                didx.append(int(dr))
        report["applied"]["navigator"] += 1
    # -- ElementTrackingData rows (ProjectRevision, the wire catalog ...) -------
    #    class -> built-in category rows, from the frozen maps (symbols / elems);
    #    the registry's "etd" tag falls back to the record's own category.
    etd = _appinfo_body(tree, "ElementTrackingData")
    if etd is not None:
        def add_to(entries: list, cat_id: int, eid: int) -> None:
            for e in entries:
                if e.get("m_categoryId") == cat_id:
                    if eid not in e["m_elemIdSet"]:
                        e["m_elemIdSet"].append(int(eid))
                    return
            entries.append({"m_categoryId": int(cat_id), "m_elemIdSet": [int(eid)]})
        for cls_name, recs in by_class.items():
            cats_s = list(c2sym.get(cls_name) or [])
            cats_e = list(c2elm.get(cls_name) or [])
            if not cats_s and not cats_e and any(
                    s[0] == "etd" for s in ADOC_REGISTRY.get(cls_name, [])):
                # registry says ETD but the maps have no entry: use the record's
                # own (negative) header category as an element row
                cats_e = [recs[0].category_id] if recs[0].category_id < 0 else []
            for r in recs:
                if isinstance(etd.get("m_symbols"), list) and len(cats_s) == 1:
                    add_to(etd["m_symbols"], int(cats_s[0]), r.elem_id)
                    report["applied"]["etd"] += 1
                elif isinstance(etd.get("m_elems"), list) and len(cats_e) == 1:
                    add_to(etd["m_elems"], int(cats_e[0]), r.elem_id)
                    report["applied"]["etd"] += 1
    # -- default types (SymbolIdMgr.m_defElementTypeMap): single-group type classes --
    sim = _appinfo_body(tree, "SymbolIdMgr")
    c2g = maps.get("CLASS_TO_DEF_GROUPS") or {}
    if sim is not None and isinstance(sim.get("m_defElementTypeMap"), list) and c2g:
        rows = sim["m_defElementTypeMap"]
        have = {int(p["first"]) for p in rows if isinstance(p, dict)}
        for cls_name, recs in sorted(by_class.items()):
            groups = c2g.get(cls_name) or []
            typelike = (cls_name.endswith(("Type", "Attributes", "Attr", "Attrs", "Symbol"))
                        or cls_name in ("Level",))
            if len(groups) == 1 and typelike and int(groups[0]) not in have:
                rows.append({"first": int(groups[0]), "second": int(recs[0].elem_id)})
                have.add(int(groups[0]))
                report["applied"]["def-type"] += 1
    # -- AppInfoSystemFamiliesNames (document-local keys) -----------------------------
    sfn = _appinfo_body(tree, "AppInfoSystemFamiliesNames")
    if sfn is not None:
        rows = sfn.setdefault("m_idMap", [])
        key = int(sfn.get("m_newKey") or (len(rows)))
        for cls_name, recs in by_class.items():
            wants = any(s[0] == "sysfam" for s in ADOC_REGISTRY.get(cls_name, [])) \
                or cls_name in tracked_sfn
            if not wants:
                continue
            for r in recs:
                rows.append({"first": key, "second": {"m_elementIds": [int(r.elem_id)]}})
                key += 1
                report["applied"]["sysfam"] += 1
        sfn["m_newKey"] = key
        sfn["m_bValid"] = True
    # -- the category / graphic-style catalogue rows -------------------------------------
    ctr = _appinfo_body(tree, "CategoryTracking")
    if ctr is not None:
        rows = ctr.setdefault("m_gstyleData", [])
        crows = ctr.setdefault("m_categoryData", [])
        for r in by_class.get("GStyleElem") or []:
            cat_id = r.obj.get("m_categoryId")
            gtype = r.obj.get("m_gstyleType")
            if isinstance(cat_id, int) and isinstance(gtype, int):
                rows.append({"m_categoryId": int(cat_id), "m_gstyleId": int(r.elem_id),
                             "m_gstyleType": int(gtype)})
                report["applied"]["category-tracking"] += 1
        for r in by_class.get("CategoryElem") or []:
            parent = (((r.obj.get("m_pCategory") or {}).get("value") or {})
                      .get("m_parentCategoryId"))
            if isinstance(parent, int):
                crows.append({"m_parentCategoryId": int(parent), "m_categoryId": int(r.elem_id)})
                report["applied"]["category-tracking"] += 1
    report["applied"] = dict(report["applied"])
    return report


# ===========================================================================
# 9. THE STANDARD SETTINGS CONSTELLATION  (what S3 / S5 add to a base)
# ===========================================================================

@dataclass
class SettingsCatalog:
    """Collector for the settings records with the same verification
    surface as ``rvt.genesis.types.GenesisCatalog`` (round-trip / reference
    check / new_elements) so the composer treats them uniformly."""
    records: List[TypeRecord] = dc_field(default_factory=list)
    ids: Any = None

    def next_id(self) -> int:
        return int(_alloc(self.ids))

    def add(self, rec) -> Any:
        if isinstance(rec, (list, tuple)):
            self.records.extend(rec)
        else:
            self.records.append(rec)
        return rec

    def roundtrip(self) -> dict:
        ok, fails = 0, []
        for r in self.records:
            rep = r.roundtrip()
            if rep["ok"]:
                ok += 1
            else:
                fails.append({"elem_id": r.elem_id, "class": r.class_name, "report": rep})
        return {"records": len(self.records), "ok": ok, "failures": fails}

    #: leaf names whose positive integers are NOT ElementIds: enum indexes
    #: (m_systemFamilyIdx = the view-family enum) and string-table resource
    #: indexes (m_resourceId of the rebar-abbreviation slots)
    NOT_ELEMENT_IDS = {"m_systemFamilyIdx", "m_resourceId"}

    def check_references(self, known_ids: Optional[Iterable[int]] = None) -> list:
        from .types import _element_refs
        mine = {r.elem_id for r in self.records}
        known = set(known_ids or ()) | mine
        bad = []
        for r in self.records:
            for path, i in _element_refs(r):
                leaf = path.rsplit(".", 1)[-1].split("[")[0]
                if leaf in self.NOT_ELEMENT_IDS:
                    continue
                if i > 0 and i not in known and i != r.elem_id:
                    bad.append({"elem_id": r.elem_id, "class": r.class_name,
                                "path": path, "target": i})
        return bad

    def new_elements(self, creation_ep: int = 0) -> list:
        return [r.as_new_element(creation_ep)
                for r in sorted(self.records, key=lambda x: x.elem_id)]

    def by_class(self) -> Dict[str, List[int]]:
        out: Dict[str, List[int]] = {}
        for r in self.records:
            out.setdefault(r.class_name, []).append(int(r.elem_id))
        for v in out.values():
            v.sort()
        return out

    def to_json(self) -> dict:
        return {"count": len(self.records),
                "records": [r.to_json() for r in self.records]}


def standard_settings(ids: IdArg, *, tier: str = "all",
                      doc_ids: Optional[Dict[str, int]] = None,
                      poche_material_id: int = INVALID) -> SettingsCatalog:
    """Build OUR complete document-settings constellation as new elements
    (allocated from ``ids``), for a base document whose existing ids are
    given in ``doc_ids`` (keys: 'units', 'document_sun', 'project_view',
    'phase_new', 'phase_filter', 'geo_location', 'level1' ... -- the named
    ids of the house-standard skeleton; missing keys degrade to -1).

    ``tier`` selects the K-branch content:
      'pen'      -> the pen table only (S1 / K5a)
      'browser'  -> + the project-browser constellation (S2 / K5b)
      'named'    -> + StructSettings, wall-join, auto-join, keynotes,
                    initial view (S3 core, the charter's named singletons)
      'mep'      -> + the MEP settings pair set + trackers (K5c)
      'all'      -> + every remaining K5d singleton, revisions, print set,
                    and the 16 remaining SYSTEM view-family types
    Each tier includes the previous ones.
    """
    d = doc_ids or {}
    sun = int(d.get("document_sun", INVALID))
    units = int(d.get("units", INVALID))
    phase = int(d.get("phase_new", INVALID))
    pfilter = int(d.get("phase_filter", INVALID))
    geo = int(d.get("geo_location", INVALID))
    ground = int(d.get("level1", INVALID))
    cat = SettingsCatalog(ids=ids)
    tiers = ["pen", "browser", "named", "mep", "all"]
    want = set(tiers[:tiers.index(tier) + 1]) if tier in tiers else set(tiers)

    # -- S1: the real project pen table -------------------------------------
    cat.add(pen_width_table(ids=ids))
    if want == {"pen"}:
        return cat
    # -- S2: the project-browser constellation ----------------------------
    if "browser" in want:
        cat.add(default_browser_organizations(ids))
        cat.add(reconcile_browser_settings(ids=ids))
        cat.add(construction_set_project(ids=ids))
    # -- S3 core: the named singletons -------------------------------------
    if "named" in want:
        cat.add(struct_settings(ids=ids))
        cat.add(wall_join_default_setting(ids=ids))
        cat.add(auto_join_tracker(ids=ids))
        kt = cat.add(keynote_table(ids=ids))
        cat.add(keynoting_system(kt.elem_id, ids=ids))
        cat.add(initial_view_settings(ids=ids))
    mep_system_id = INVALID
    workset_vis_id = INVALID
    # -- K5c: the MEP settings set --------------------------------------------
    if "mep" in want:
        cat.add(wire_settings(ids=ids))
        # the wiring-data table + the wire catalog symbols it keys on
        # (RbsWireMaterialType / -TemperatureRatingType / -InsulationType,
        # the types stream's constructors; names = the physical / NEC
        # designations, values = the house standard's NEC ampacity data)
        from .types import (new_wire_material_type, new_wire_temperature_rating_type,
                            new_wire_insulation_type)
        from . import house_standard as hs
        mat_ids = {n: cat.add(new_wire_material_type(n, ids=ids)).elem_id
                   for n in hs.CONDUCTOR_MATERIALS}
        temp_ids = {n: cat.add(new_wire_temperature_rating_type(n, ids=ids)).elem_id
                    for n in hs.CONDUCTOR_TEMPERATURE_RATINGS_C}
        ins_ids = {n: cat.add(new_wire_insulation_type(n, ids=ids)).elem_id
                   for n in hs.CONDUCTOR_INSULATIONS}
        cat.add(wire_sizes_from_house_table(mat_ids, temp_ids, ins_ids, ids=ids))
        cat.add(conduit_settings(ids=ids))
        cat.add(cable_tray_settings(ids=ids))
        ps = cat.add(pipe_settings(ids=ids))
        ds = cat.add(duct_settings(ids=ids))
        cat.add(duct_sizes(ids=ids))
        trk = cat.add(mep_tracker_constellation(ids, ds.elem_id, ps.elem_id))
        mep_system_id = next(t.elem_id for t in trk if t.class_name == "MEPSystemTracker")
        cat.add(mep_hidden_line_settings(ids=ids))
        cat.add(tracker("CircuitNamingTypeSetting", ids=ids))
    # -- K5d / the rest ---------------------------------------------------------
    if "all" in want:
        cat.add(gcs_tracker(ids, units_id=units))
        cat.add(tracker("AssemblyTracker", ids=ids))
        cat.add(tracker("KeynoteTagsOnSheetsTracker", ids=ids))
        cat.add(tracker("RevisionCloudsOnSheetsTracker", ids=ids))
        cat.add(tracker("SheetsInSheetCollectionTracker", ids=ids))
        cat.add(tracker("AnalyticalToPhysicalRelationManager", ids=ids))
        cat.add(tracker("ReactionsUpToDateElem", ids=ids))
        cat.add(tracker("GraphicsCache", ids=ids))
        cat.add(tracker("ExternalParamLock", ids=ids))
        cat.add(tracker("DaylightSourceIdSet", ids=ids))
        wv = cat.add(tracker("WorksetVisibilitySettingsElem", ids=ids))
        workset_vis_id = wv.elem_id
        cat.add(tracker("Dwg2dExportUserSettingsData", ids=ids))
        cat.add(tracker("STEPExportSettings", ids=ids))
        cat.add(tracker("ZoneScheme", ids=ids))
        cat.add(tracker("RvtLinkInstanceAppearanceParentElem", ids=ids))
        cat.add(tracker("SketchGridAppearanceParentElem", ids=ids))
        cat.add(tracker("FabricationServiceSettings", ids=ids))
        cat.add(tracker("CurtaSystemFaceManager", ids=ids))
        cat.add(tracker("StructuralConnectionSettings", ids=ids))
        cat.add(auto_cam_settings(ids=ids))
        cat.add(halftone_underlay_settings(ids=ids))
        cat.add(multiple_values_indication_settings(ids=ids))
        cat.add(worksharing_view_mode_settings(ids=ids))
        cat.add(coordinate_system_display(ids=ids))
        if geo not in (None, INVALID):
            cat.add(active_geo_location_tracking(geo, ids=ids))
        cat.add(default_divide_settings(ids=ids))
        cat.add(project_copy_settings(ids=ids))
        cat.add(copy_watch_properties(ids=ids))
        if sun not in (None, INVALID):
            cat.add(model_graphics_styles(ids, sun))
        cat.add(area_settings(ids=ids))
        cat.add(route_analysis_settings(ids=ids))
        cat.add(fabrication_settings(ids=ids))
        cat.add(fabrication_settings_element(ids=ids))
        cat.add(sse_point_visibility_settings(ids=ids))
        cat.add(reinforcement_settings(ids=ids, ))
        cat.add(energy_data_settings(ids=ids, ground_level_id=ground,
                                     project_phase_id=phase))
        cat.add(revision_constellation(ids))
        cat.add(print_settings(ids=ids))
        for nm, desc, code in AREA_SCHEMES:
            from .house_standard import gen
            cat.add(area_measure(gen(nm), desc, code, ids=ids))
        cat.add(system_view_type_table(ids, poche_material_id=poche_material_id,
                                       skip_families=("3d", "floor_plan", "ceiling_plan")))
    # -- S2's system navigator (built last: it names the phase / units /
    #    workset-visibility / MEP-system-tracker elements when present) ---------
    if "browser" in want:
        cat.add(system_navigator(
            ids, phase_id=phase, phase_filter_id=pfilter, sun_settings_id=sun,
            all_phases_id=int(d.get("phase_set", INVALID)), units_id=units,
            workset_visibility_id=workset_vis_id,
            mep_system_tracker_id=mep_system_id))
    return cat


# ===========================================================================
# DEMO / self-test
# ===========================================================================

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    src = IdSource(700_000)
    cat = standard_settings(src, tier="all",
                            doc_ids={"units": 690_001, "document_sun": 690_002,
                                     "phase_new": 690_003, "phase_filter": 690_004,
                                     "geo_location": 690_005, "level1": 690_006})
    rt = cat.roundtrip()
    dangling = cat.check_references(known_ids=[690_001, 690_002, 690_003, 690_004,
                                               690_005, 690_006])
    by_cls = cat.by_class()
    print(f"genesis settings constellation: {rt['records']} records, "
          f"{len(by_cls)} classes; round-trip clean+byte-exact "
          f"{rt['ok']}/{rt['records']}; dangling references {len(dangling)}")
    for k in sorted(by_cls):
        print(f"   {len(by_cls[k]):3d} x {k}")
    for f in rt["failures"][:6]:
        print("   FAIL", f["elem_id"], f["class"],
              {k: (v.get("errors") if isinstance(v, dict) else v)
               for k, v in f["report"].items() if k != "ok"})
    for dg in dangling[:8]:
        print("   DANGLING", dg)
    if "--json" in argv:
        json.dump(cat.to_json(), sys.stdout, indent=1, default=str)
        print()
    return 0 if (rt["ok"] == rt["records"] and not dangling) else 1


if __name__ == "__main__":
    sys.exit(main())

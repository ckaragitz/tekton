"""genesis/residue_b.py -- RESIDUE CONSTRUCTORS, GROUP B (class names M..Z) +
the ZB in-place rung table + the Yn END-GAME queue (genesis-residue-B stream).

WHAT THIS MODULE IS.  After the CERTIFIED substitution ladder Y1..Y9
(docs/writer/substitution-ladder-v3.md, ORCHESTRATOR VERDICTS #17: ALL PASS),
Y9 -- the deepest rung -- carries 1,333 of K4's 3,342 host elements as OUR
constructors' output; the RESIDUE = 2,009 elements in 11 named buckets
(experiments/genesis/subst_k4/Yn.json).  GROUP B owns every residue CLASS
whose name sorts M..Z (29 classes, 997 elements; Group A owns A..L).  This
module holds, per Group-B class:

  * a CENSUS entry (:data:`GROUP_B_CENSUS`) -- element count in Y9/K4 and the
    six samples, which fields are FREE VALUES (ours to state) vs FORMAT-
    CONSTANT MACHINERY (reproduced), and the retiring OPERATION (in-place /
    add / delete-with-content) per THE REDUCTION LAW;
  * a CONSTRUCTOR building OUR object field by field over the schema-directed
    blank (rvt.genesis.types.blank_object) -- OUR values + mined format
    constants; the empty-machinery classes are REPRODUCED and declared
    'nothing of ours to reject';
  * an IN-PLACE RUNG BUILDER (``build_ZB_<bucket>(ctx)`` -> a
    ``genesis_substitute.SubstBuild``) that lands our records on the sample's
    slots of the same class (role correspondence), so the ONE variable of a
    rung is the CONTENT of our objects at Autodesk's own registrations (id /
    ElemTable row / record position / registry slots byte-identical --
    rvt.regadd.substitute_elements, seq-102 only).

THE RUNGS (each = a certified parent + ONE bucket in place; ``ZB_deep`` =
the cumulative file; reproduce with ``.venv/bin/python -m
rvt.genesis.residue_b``, output ``experiments/genesis/subst_k4/residue_b/``):

  ZB1_defs      the parameter-DEFINITIONS layer (791: ParamElemExternal 466,
                ParamBinding 209, ParamElemElectricalLoadClassification 108,
                ParamElemProject 8) -> OUR shared / project / load-class
                parameter definitions at the sample's GUID / id registrations
  ZB2_mepcat    the MEP CATALOG (74: wire material 4 / insulation 26 / temp
                rating 3, pipe schedule 13 / material 5 / connection 8, pipe
                segments 15) -> our conductor / piping catalog
  ZB3_pens      the 8 curtain-family-scoped PenWidthTableElem -> our ISO-128
                pen table, family-scoped
  ZB4_annot     SectionAttributes 10 + ViewportAttributes 1 -> our section
                head/tail types + viewport-title type (companion wiring kept)
  ZB5_palette   the 10 SURPLUS materials -> our extended palette; the 28
                PropertySetElements -> our physical assets (17 structural +
                11 thermal -- both param-id blocks decoded, F6/F7)
  ZB6_filters   the 7 ParameterFilterElements -> our house view filters
  ZB7_machinery SunAnnotationElem 3 / NumberingSchema 3 / SlaveSymbolTracker 1
                (empty / built-in machinery REPRODUCED = nothing of ours to
                reject) + the surplus per-user WorksharingViewModeSettings and
                the 2 surplus PrintSettings (-> ours) + the drafting view's
                Viewer / Viewport companions (skeleton constructors, wiring
                kept)
  ZB8_content   RefPlane 21 -> our reference planes; SketchPlane 30 -> our
                level work planes; RoomElem 1 -> our room identity (the
                placeable-content probe; the endgame retires content by
                DELETION -- docs/writer/genesis-endgame.md)
  ZB_deep       = Y9 + ZB1..ZB8 (the cumulative deep file)
  Z_<bucket>    = Y9 + that bucket ONLY (single-change probes)

Read the record docs/inbox/genesis-residue-B.md and the end-game
docs/writer/genesis-endgame.md (the ordered path Y9 -> Yn = 0
Autodesk-authored elements: which residue element retires by which operation).

TERRITORY: this module, tests/test_residue_b.py,
experiments/genesis/subst_k4/residue_b/* (+ probes.json + reports),
docs/writer/genesis-endgame.md, docs/inbox/genesis-residue-B.md.  Every
dependency (rvt.genesis.types / settings / skeleton / house_standard,
tools/genesis_substitute(_v3), rvt.regadd / regdiff / reduce) is IMPORTED,
never edited.  Python: ``.venv/bin/python`` from the repo root.
"""
from __future__ import annotations

import collections
import copy
import dataclasses
import hashlib
import json
import math
import os
import sys
import time
import uuid
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .types import (
    TypeRecord, IdArg, IdSource, INVALID, NO_DESIGN_OPTION, NULL_GUID,
    LINEPATTERN_SOLID, blank_object, element_defaults, symbol_defaults,
    element_header, class_id, mm, inches, rgb, _record, _alloc, _owned, _ptr,
)
from . import settings as ST
from . import skeleton as sk
from . import types as TY

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
MM_PER_FT = 304.8
IN_PER_FT = 12.0

#: OUR house prefix (rvt.genesis.house_standard.gen) -- every named object we
#: author carries it, so provenance is unambiguous in any inspection.
HOUSE_PREFIX = "GEN"


def gen(name: str) -> str:
    """OUR naming convention: 'GEN <name>' (house_standard.gen)."""
    n = str(name).strip()
    return n if n.startswith(HOUSE_PREFIX + " ") else f"{HOUSE_PREFIX} {n}"


def log(msg: str) -> None:
    print(msg, flush=True)


# ===========================================================================
# 0. THE GROUP-B CLAIM + CENSUS (which residue classes are ours, and what in
#    each is a free value vs format machinery vs registration)
# ===========================================================================
#: The 29 residue classes GROUP B owns (class name sorts M..Z), from
#: experiments/genesis/subst_k4/Yn.json 'residue_still_autodesk.table' -- the
#: buckets straddle the alphabet split, so the claim is PER CLASS.  Value =
#: (Yn residue count in Y9, Yn bucket, this module's rung / disposition).
GROUP_B_CLASSES: Dict[str, Tuple[int, str, str]] = {
    "ParamElemExternal":                  (466, "definitions-removal-candidate", "ZB1_defs"),
    "ParamBinding":                       (209, "definitions-removal-candidate", "ZB1_defs"),
    "ParamElemElectricalLoadClassification": (108, "definitions-removal-candidate", "ZB1_defs"),
    "ParamElemProject":                   (8,   "definitions-removal-candidate", "ZB1_defs"),
    "RbsWireInsulationType":              (26,  "constructor-exists", "ZB2_mepcat"),
    "RbsWireMaterialType":                (4,   "constructor-exists", "ZB2_mepcat"),
    "RbsWireTemperatureRatingType":       (3,   "constructor-exists", "ZB2_mepcat"),
    "RbsPipeScheduleType":                (13,  "constructor-partial", "ZB2_mepcat"),
    "RbsPipeConnectionType":              (8,   "constructor-partial", "ZB2_mepcat"),
    "RbsPipeMaterialType":                (5,   "constructor-partial", "ZB2_mepcat"),
    "PipeSegment":                        (15,  "constructor-partial", "ZB2_mepcat"),
    "PenWidthTableElem":                  (8,   "curtain-systems(no-constructor)", "ZB3_pens"),
    "SectionAttributes":                  (10,  "no-constructor", "ZB4_annot"),
    "ViewportAttributes":                 (1,   "no-constructor", "ZB4_annot"),
    "MaterialElem":                       (10,  "surplus-sample-instances", "ZB5_palette"),
    "PropertySetElement":                 (28,  "no-constructor", "ZB5_palette"),
    "ParameterFilterElement":             (7,   "no-constructor", "ZB6_filters"),
    "SunAnnotationElem":                  (3,   "surplus-sample-instances", "ZB7_machinery"),
    "NumberingSchema":                    (3,   "no-constructor", "ZB7_machinery"),
    "SlaveSymbolTrackerElem":             (1,   "curtain-systems(no-constructor)", "ZB7_machinery"),
    "WorksharingViewModeSettings":        (1,   "surplus-sample-instances", "ZB7_machinery"),
    "PrintSettings":                      (2,   "surplus-sample-instances", "ZB7_machinery"),
    "Viewer":                             (1,   "surplus-sample-instances", "ZB7_machinery"),
    "Viewport":                           (3,   "surplus-sample-instances", "ZB7_machinery"),
    "RefPlane":                           (21,  "content-removal-candidate", "ZB8_content"),
    "SketchPlane":                        (30,  "content-removal-candidate", "ZB8_content"),
    "RoomElem":                           (1,   "content-removal-candidate", "ZB8_content"),
    "RvtLinkSymbol":                      (1,   "external-link-removal-candidate", "ENDGAME:delete"),
    "RvtLinkInstance":                    (1,   "external-link-removal-candidate", "ENDGAME:delete"),
}
#: Yn's 'ours-not-landed' queue is Group A/B agnostic (the ADD path); the two
#: external-link elements are NOT in-place-substitutable (a genesis file
#: carries no linked models) -- their retiring operation is DELETION, designed
#: in docs/writer/genesis-endgame.md, not built by an in-place rung.
GROUP_B_TOTAL = sum(v[0] for v in GROUP_B_CLASSES.values())      # 997


def census_class(doc, class_name: str, *, ids: Optional[Sequence[int]] = None,
                 max_depth_list: int = 4) -> dict:
    """FIELD-VARIATION CENSUS of one class in one document: which flattened
    fields are CONSTANT across every instance (= format machinery, or a
    registration common to all) and which VARY (= per-element free values /
    registrations).  ``doc`` = ``rvt.mutate.Document``; ``ids`` restricts the
    instances (e.g. residue only).  This is the instrument behind
    :data:`GROUP_B_CENSUS` (recorded per class in
    docs/inbox/genesis-residue-B.md, table 'free value vs machinery')."""
    def _flat(v, prefix, out):
        if isinstance(v, dict):
            for k, x in v.items():
                _flat(x, f"{prefix}.{k}" if prefix else k, out)
        elif isinstance(v, list):
            out[prefix + "[len]"] = len(v)
            for i, x in enumerate(v[:max_depth_list]):
                _flat(x, f"{prefix}[{i}]", out)
        else:
            out[prefix] = v
    use = list(ids) if ids is not None else list(doc.ids_of_class(class_name))
    vals: Dict[str, set] = collections.defaultdict(set)
    for e in use:
        d: Dict[str, Any] = {}
        _flat(doc.value(e) or {}, "", d)
        for k, x in d.items():
            vals[k].add(repr(x)[:80])
    constant = {k: next(iter(v)) for k, v in vals.items() if len(v) == 1}
    varying = {k: sorted(v)[:4] for k, v in vals.items() if len(v) > 1}
    return {"class": class_name, "count": len(use),
            "constant_fields": len(constant), "varying_fields": sorted(varying),
            "constant": constant, "varying_examples": varying}


#: THE GROUP-B CENSUS SUMMARY (per class: what our constructor sets vs what
#: it reproduces).  Numbers = Yn residue in Y9; 'files' = instance counts in
#: (Y9, K4, rst, rac, rme, racadv, rstadv, dach) from the cross-corpus census
#: (docs/inbox/genesis-residue-B.md, table T2).  This is the map the
#: constructors below implement.
GROUP_B_CENSUS: Dict[str, dict] = {
    "ParamElemExternal": {
        "residue": 466, "files": (466, 466, 466, 290, 8, 2, 33, 434),
        "free": ["m_pParamDef.m_caption", "m_description", "m_pParamDef.m_groupTypeId",
                 "m_pParamDef.m_specTypeId (kind-compatible)", "m_userVisible/m_hideWhenNoValue"],
        "registration": ["m_externalParamKey.m_guidValue == the ExternalParamTracking.m_keyDataMap "
                         "KEY in Global/Latest (466/466)", "m_typeId = 'revit.local.shared:<guid>-1.0.0'",
                         "m_paramElemId == m_id", "m_bindingIds -> its ParamBinding rows"],
        "machinery": ["ParamDef pointer class per storage kind (Value/String/YesNo/Int/URL/"
                      "MaterialBrowse/FamType/NoOfPoles)", "m_restriction 1 / m_boundless F for "
                      "measurable kinds", "m_userModifiable T"],
        "verdict": "constructible IN PLACE at the sample's GUID registration; retire by DELETION "
                   "(the family-free genesis file carries no sample shared params; 0 value carriers)",
    },
    "ParamBinding": {
        "residue": 209, "files": (209, 209, 209, 2, 12, 8, 4, 219),
        "free": [], "registration": ["ParamBindingTracking.m_itemSet (category -> binding ids)"],
        "machinery": ["{m_paramId, m_categoryId, m_elemOrSymbol} -- the binding IS a registration"],
        "verdict": "PURE MACHINERY: reproduced byte-for-byte = nothing of ours to reject",
    },
    "ParamElemElectricalLoadClassification": {
        "residue": 108, "files": (108, 108, 108, 72, 60, 18, 36, 126),
        "free": ["m_pParamDef.m_caption (the 6 role phrasings per load classification)"],
        "registration": ["m_idLoadClassification -> its ElectricalLoadClassification (Group A)",
                         "m_typeId = 'revit.local.classification:<session-guid><elem-id hex>-2.0.0' "
                         "(suffix == element id, 108/108)", "ElementTrackingData.m_elems id set"],
        "machinery": ["m_eType 0..5 = est-load / est-current / actual-space / demand-factor / "
                      "total-current / total-load", "spec type per role", "18 classes x 6 = 108"],
        "verdict": "constructible IN PLACE (our role captions); Group A owns the 18 classifications",
    },
    "ParamElemProject": {
        "residue": 8, "files": (8, 8, 8, 1, 4, 8, 2, 13),
        "free": ["m_pParamDef.m_caption", "m_description", "m_pParamDef.m_groupTypeId"],
        "registration": ["m_typeId = 'revit.local.project:<session-guid><elem-id hex>-1.0.0' (8/8)",
                         "ProjectParamTracking.m_elemIdSet", "m_bindingIds"],
        "machinery": ["ParamDef pointer class per storage kind"],
        "verdict": "constructible IN PLACE (our project-parameter captions)",
    },
    "RbsWireMaterialType": {"residue": 4, "files": (4, 4, 4, 4, 5, 4, 4, 8),
                            "free": ["m_symbolInfo.m_name"], "machinery": ["CellList{PatternHelper}",
                            "present-empty AString param set"], "verdict": "constructor-exists (types.new_wire_material_type)"},
    "RbsWireInsulationType": {"residue": 26, "files": (26, 26, 26, 26, 2, 26, 26, 26),
                              "free": ["m_symbolInfo.m_name (NEC insulation designation)"],
                              "machinery": ["CellList{PatternHelper}", "empty AString set"],
                              "verdict": "constructor-exists"},
    "RbsWireTemperatureRatingType": {"residue": 3, "files": (3, 3, 3, 3, 1, 3, 3, 3),
                                     "free": ["m_symbolInfo.m_name ('60'/'75'/'90' C)"],
                                     "machinery": ["CellList{PatternHelper}", "empty AString set"],
                                     "verdict": "constructor-exists"},
    "RbsPipeScheduleType": {"residue": 13, "files": (13, 13, 13, 10, 10, 10, 10, 10),
                            "free": ["m_symbolInfo.m_name (ASME/ASTM/AWWA schedule designation)"],
                            "machinery": ["CellList{PatternHelper}", "empty AString set"],
                            "verdict": "new constructor (pipe_schedule_type)"},
    "RbsPipeConnectionType": {"residue": 8, "files": (8, 8, 8, 8, 8, 8, 8, 8),
                              "free": ["m_symbolInfo.m_name (joining method)"],
                              "machinery": ["CellList{PatternHelper}", "empty AString set"],
                              "verdict": "new constructor (pipe_connection_type)"},
    "RbsPipeMaterialType": {"residue": 5, "files": (5, 5, 5, 5, 5, 5, 5, 5),
                            "free": ["m_symbolInfo.m_name", "roughness param -1140204 (mm)"],
                            "machinery": ["CellList{PatternHelper}", "empty AString set"],
                            "verdict": "new constructor (pipe_material_type)"},
    "PipeSegment": {"residue": 15, "files": (15, 15, 15, 12, 13, 12, 12, 12),
                    "free": ["m_name", "m_sizeData rows (ASME B36.10/B36.19, ASTM B88, AWWA -- FACTS, "
                             "our selection)", "m_roughness (published absolute roughness)"],
                    "machinery": ["m_materialId / m_scheduleTypeId wiring (kept per slot)", "m_shape 0",
                                  "m_connectionType 0"],
                    "verdict": "new constructor (pipe_segment)"},
    "PenWidthTableElem": {"residue": 8, "files": (9, 9, 9, 9, 11, 10, 9, 8),
                          "free": ["the 16-pen vectors x 6 scale breakpoints (OUR ISO-128 series)"],
                          "registration": ["m_famId = the owning curtain SYSTEM family (per slot)"],
                          "verdict": "constructor-exists (settings.pen_width_table, family-scoped)"},
    "SectionAttributes": {"residue": 10, "files": (10, 10, 10, 10, 10, 12, 11, 2),
                          "free": ["m_symbolInfo.m_name", "m_sectionTailLength/Width",
                                   "m_styleForBrokenDisplay"],
                          "machinery": ["m_lineAndTextAttr wiring: its own FontElem + line-style "
                                        "CategoryElem (Group-A companions, kept per slot)",
                                        "m_sectionHead/TailFamilyTagId -1 (K3 nulled the family usage)"],
                          "verdict": "new constructor (section_attributes)"},
    "ViewportAttributes": {"residue": 1, "files": (1, 1, 2, 2, 4, 4, 5, 3),
                           "free": ["m_symbolInfo.m_name", "m_showLabel/m_showBox/m_showExtensionLine"],
                           "machinery": ["m_categoryId = its own line sub-category (kept)"],
                           "verdict": "new constructor (viewport_attributes)"},
    "MaterialElem": {"residue": 10, "files": (23, 23, 93, 174, 192, 184, 213, 212),
                     "free": ["everything: name, colour, shininess, class/category strings, patterns"],
                     "machinery": ["m_asset generic descriptor tokens"],
                     "verdict": "constructor-exists (types.new_material) -> our EXTENDED palette (10 more)"},
    "PropertySetElement": {"residue": 28, "files": (28, 28, 56, 53, 20, 28, 20, 67),
                           "free": ["the physical constants (E, G, nu, density, yield, ...) -- published "
                                    "facts of the substance; the asset NAME + source 'GEN'"],
                           "machinery": ["the builtin-param id BLOCKS = the asset schema (structural "
                                         "-1140xxx / thermal -1152xxx / identity -1150xxx)"],
                           "product_data": ["source 'Autodesk' + asset-library GUIDs + Inventor "
                                            "sustainability tokens (dropped in ours)"],
                           "verdict": "new constructors for BOTH shapes: the STRUCTURAL asset (id block "
                                      "decoded EXACTLY via the inline PhysicalParamSet Rosetta twin) and "
                                      "the THERMAL asset (id block decoded by unit matching over all 11 rst "
                                      "thermal assets: k / cp / rho / emissivity ...)"},
    "ParameterFilterElement": {"residue": 7, "files": (7, 7, 7, 2, 21, 2, 4, 83),
                               "free": ["m_name", "m_oCategoryRule.m_categories", "m_oRuleCombination"],
                               "verdict": "new constructor (parameter_filter) -> our house filters"},
    "SunAnnotationElem": {"residue": 3, "files": (3, 3, 31, 22, 72, 24, 25, 298),
                          "free": [], "machinery": ["EMPTY class body (view-owned; the sun-path graphic "
                          "is regenerated)"], "verdict": "reproduced = nothing of ours to reject"},
    "NumberingSchema": {"residue": 3, "files": (3, 3, 3, 3, 3, 3, 3, 3),
                        "free": ["m_priority order (0/1/2 -- Revit's own default order)"],
                        "product_data": ["m_builtIn TRUE: 'Rebar Numbering' / 'Fabric Sheets Numbering' / "
                                         "'Rebar Couplers Numbering' -- Revit's built-in numbering "
                                         "machinery keyed to built-in categories/parameters"],
                        "verdict": "reproduced (built-in machinery) = nothing of ours to reject"},
    "SlaveSymbolTrackerElem": {"residue": 1, "files": (1, 1, 1, 0, 0, 0, 1, 2),
                               "free": [], "machinery": ["empty SharedSlaveSymbolTrackerCell maps; "
                               "m_masterId -> the FabricSheetType it tracks"],
                               "verdict": "reproduced = nothing of ours to reject"},
    "WorksharingViewModeSettings": {"residue": 1, "files": (2, 2, 2, 2, 1, 1, 1, 2),
                                    "free": ["status colours", "m_user (LEAKS the sample username "
                                    "'liqi' -> ours 'rvt-writer')"],
                                    "verdict": "constructor-exists (settings.worksharing_view_mode_settings)"},
    "PrintSettings": {"residue": 2, "files": (3, 3, 3, 2, 1, 1, 1, 10),
                      "free": ["m_name (LEAKS the sample printer 'SYDPRN008'), paper size/dims, "
                               "orientation, dpi, print filters"],
                      "verdict": "constructor-exists (settings.print_settings) -> our A3 / ANSI-D setups"},
    "Viewer": {"residue": 1, "files": (5, 5, 34, 24, 110, 30, 37, 272),
               "free": ["crop-box extents / camera frame (a genesis view is uncropped)"],
               "machinery": ["m_dbViewId -> its view (the drafting view 1457028)"],
               "verdict": "constructor-exists (skeleton.new_viewer) -- the drafting-view constellation"},
    "Viewport": {"residue": 3, "files": (8, 8, 79, 63, 157, 62, 60, 607),
                 "free": ["label origin (empty machinery otherwise)"],
                 "machinery": ["m_attrId / m_dbDrawingId / m_dbViewId wiring (kept per slot)"],
                 "verdict": "constructor-exists (skeleton.new_viewport) -- mostly byte-identical machinery"},
    "RefPlane": {"residue": 21, "files": (21, 21, 21, 56, 12, 13, 4, 462),
                 "free": ["the plane geometry (origin / direction / extent envelope)", "m_text (name)"],
                 "machinery": ["DatumPlaneGeomStep + GeomTable + Face/Plane twin (the Level datum shape)"],
                 "verdict": "new constructor (reference_plane); endgame = DELETE (sample content)"},
    "SketchPlane": {"residue": 30, "files": (32, 32, 209, 123, 487, 174, 94, 1449),
                    "free": ["the work-plane transform (elevation on its level)"],
                    "machinery": ["m_oPlaneRef (OnDBViewPlaneRef / OnLevelPlaneRef) -> its datum"],
                    "verdict": "constructor-exists (skeleton.new_sketch_plane); endgame = DELETE"},
    "RoomElem": {"residue": 1, "files": (1, 1, 31, 14, 165, 116, 0, 90),
                 "free": ["room number / name (AString params -1006901 / -1006900), placement point"],
                 "machinery": ["level / area-scheme / boundary-curve / topology wiring (a placed room's "
                               "companions: LevelRoomPlan + 5 area-boundary CurveElems, Group A classes)"],
                 "verdict": "in-place identity constructor here; endgame = DELETE-WITH-CONTENT "
                            "(the room + LevelRoomPlan + boundary CurveElems + sketch plane, atomically)"},
    "RvtLinkSymbol": {"residue": 1, "files": (1, 1, 1, 0, 0, 0, 1, 1),
                      "product_data": ["a LINKED AUTODESK SAMPLE FILE ('rac_basic_sample_project.rvt') + "
                                       "its Dropbox path -- names an external Autodesk model"],
                      "verdict": "ENDGAME DELETE (no genesis file links a model); NOT in-place-able"},
    "RvtLinkInstance": {"residue": 1, "files": (1, 1, 1, 0, 0, 0, 1, 1),
                        "verdict": "ENDGAME DELETE with its RvtLinkSymbol (delete-with-content)"},
}


# ===========================================================================
# 1. small shared building blocks
# ===========================================================================

def _cell_list_pattern_helper() -> dict:
    """The ``CellList{PatternHelper}`` every corpus MEP catalog symbol
    carries [VERIFIED 26/26 wire insulation, 13/13 pipe schedules, ...]."""
    return _ptr("CellList", {"m_cells": [
        _ptr("PatternHelper", {"m_PatternPositionMap": [], "m_substituteFaceMap": []})]})


def _astring_param_set(pairs: Sequence[Tuple[int, str]] = ()) -> dict:
    """A PRESENT (possibly empty) ``ParamValueSetAString`` -- the MEP
    catalog symbols carry an empty one, the room its number / name."""
    return _ptr("ParamValueSetAString",
                {"m_paramSet": [{"m_paramId": int(k), "m_value": str(v)} for k, v in pairs]})


def _double_param_set(pairs: Sequence[Tuple[float, int]]) -> dict:
    """``ParamValueSetDouble`` -- NB: the DOUBLE set serialises value FIRST
    then the param id [VERIFIED: material -1001205, pipe-material -1140204]."""
    return _ptr("ParamValueSetDouble",
                {"m_paramSet": [{"m_value": float(v), "m_paramId": int(k)} for v, k in pairs]})


def _int_param_set(pairs: Sequence[Tuple[int, int]]) -> dict:
    return _ptr("ParamValueSetInt",
                {"m_paramSet": [{"m_paramId": int(k), "m_value": int(v)} for k, v in pairs]})


def _stable_guid(*parts: str) -> str:
    """A DETERMINISTIC GUID in OUR namespace (uuid5 over 'rvt-writer/GEN'):
    the same inputs always yield the same GUID, so a re-run reproduces the
    file byte-for-byte, and no Autodesk GUID is ever reused."""
    ns = uuid.uuid5(uuid.NAMESPACE_DNS, "rvt-writer.gen.house-standard")
    return str(uuid.uuid5(ns, "|".join(str(p) for p in parts)))


# ===========================================================================
# 2. THE PARAMETER-DEFINITIONS LAYER (ZB1_defs)
#    ParamElemExternal / ParamElemProject / ParamElemElectricalLoadClassification / ParamBinding
# ===========================================================================
#: ParamDef pointer classes = the definition's STORAGE KIND [VERIFIED census
#: of the 466 rstbasic shared parameters: Value 171 / String 145 / YesNo 34 /
#: MaterialBrowse 78 / URL 11 / FamType 15 / NoOfPoles 3 / Int 9].  In-place
#: substitution NEVER changes a slot's storage kind (a text parameter never
#: becomes a length): our library supplies one definition of the same kind.
PARAM_DEF_CLASSES = ("ParamDefValue", "ParamDefString", "ParamDefYesNo", "ParamDefInt",
                     "ParamDefMaterialBrowse", "ParamDefURL", "ParamDefFamType",
                     "ParamDefNoOfPoles")
#: kinds whose ParamDef carries the (m_specTypeId, m_restriction, m_boundless)
#: measurable-value block [VERIFIED: ParamDefValue only]
_VALUE_DEF_CLASSES = {"ParamDefValue"}

#: Autodesk's PUBLIC parameter-group identifiers (the openly published
#: 'autodesk.parameter.group:*' enum -- interoperability constants; the
#: CHOICE of group per parameter below is ours).
GROUP_ELECTRICAL = "autodesk.parameter.group:electrical-1.0.0"
GROUP_ELECTRICAL_LOADS = "autodesk.parameter.group:electricalLoads-1.0.0"
GROUP_ELECTRICAL_CIRCUITING = "autodesk.parameter.group:electricalCircuiting-1.0.0"
GROUP_ELECTRICAL_LIGHTING = "autodesk.parameter.group:electricalLighting-1.0.0"
GROUP_MECHANICAL = "autodesk.parameter.group:mechanical-1.0.0"
GROUP_MECH_AIRFLOW = "autodesk.parameter.group:mechanicalAirflow-1.0.0"
GROUP_PLUMBING = "autodesk.parameter.group:plumbing-1.0.0"
GROUP_IDENTITY = "autodesk.parameter.group:identityData-1.0.0"
GROUP_DIMENSIONS = "autodesk.parameter.group:dimensions-1.0.0"
GROUP_CONSTRAINTS = "autodesk.parameter.group:constraints-1.0.0"
GROUP_CONSTRUCTION = "autodesk.parameter.group:construction-1.0.0"
GROUP_MATERIALS = "autodesk.parameter.group:materials-1.0.0"
GROUP_STRUCTURAL = "autodesk.parameter.group:structural-1.0.0"
GROUP_GENERAL = "autodesk.parameter.group:general-1.0.0"
GROUP_DATA = "autodesk.parameter.group:data-1.0.0"
GROUP_TEXT = "autodesk.parameter.group:text-1.0.0"
GROUP_NONE = ""

#: Autodesk's PUBLIC measurable-spec identifiers ('autodesk.spec.*' -- the
#: openly published unit/spec schema).  A spec choice per OUR parameter.
SPEC_LENGTH = "autodesk.spec.aec:length-1.0.0"
SPEC_AREA = "autodesk.spec.aec:area-1.0.0"
SPEC_VOLUME = "autodesk.spec.aec:volume-1.0.0"
SPEC_ANGLE = "autodesk.spec.aec:angle-1.0.0"
SPEC_NUMBER = "autodesk.spec.aec:number-1.0.0"
SPEC_INTEGER = "autodesk.spec.aec:integer-1.0.0"
SPEC_CURRENCY = "autodesk.spec.measurable:currency-1.0.0"
SPEC_MASS = "autodesk.spec.aec:mass-1.0.0"
SPEC_TIME = "autodesk.spec.aec:time-1.0.0"
SPEC_SPEED = "autodesk.spec.aec:speed-1.0.0"
SPEC_APPARENT_POWER = "autodesk.spec.aec.electrical:apparentPower-1.0.0"
SPEC_CURRENT = "autodesk.spec.aec.electrical:current-1.0.0"
SPEC_POTENTIAL = "autodesk.spec.aec.electrical:potential-1.0.0"
SPEC_WATTAGE = "autodesk.spec.aec.electrical:wattage-1.0.0"
SPEC_ILLUMINANCE = "autodesk.spec.aec.electrical:illuminance-1.0.0"
SPEC_LUMINOUS_FLUX = "autodesk.spec.aec.electrical:luminousFlux-1.0.0"
SPEC_COLOR_TEMPERATURE = "autodesk.spec.aec.electrical:colorTemperature-1.0.0"
SPEC_EFFICACY = "autodesk.spec.aec.electrical:efficacy-1.0.0"
SPEC_DEMAND_FACTOR = "autodesk.spec.aec.electrical:demandFactor-1.0.0"
SPEC_AIRFLOW = "autodesk.spec.aec.hvac:airFlow-1.0.0"
SPEC_PRESSURE = "autodesk.spec.aec.hvac:pressure-1.0.0"
SPEC_TEMPERATURE = "autodesk.spec.aec.hvac:temperature-1.0.0"
SPEC_PIPE_SIZE = "autodesk.spec.aec.piping:pipeSize-1.0.0"
SPEC_FLOW = "autodesk.spec.aec.piping:flow-1.0.0"
SPEC_FORCE = "autodesk.spec.aec.structural:force-1.0.0"
SPEC_MOMENT = "autodesk.spec.aec.structural:moment-1.0.0"

#: The six role phrasings of the load-classification companion parameters
#: (ParamElemElectricalLoadClassification.m_eType 0..5) -- OURS: the reader
#: keys the role on m_eType + m_specTypeId; the caption text is free.
#: [VERIFIED role -> spec on the 108 rstbasic rows: 0 est-load
#: apparentPower / 1 est-current current / 2 actual-space-load apparentPower
#: / 3 demand-factor demandFactor / 4 total-current current / 5 total-load
#: apparentPower]
LOAD_CLASS_PARAM_ROLES: Dict[int, Tuple[str, str, bool]] = {
    # eType: (our caption pattern, spec, readOnly)
    0: ("{cls} Demand Load (est.)", SPEC_APPARENT_POWER, False),
    1: ("{cls} Demand Current (est.)", SPEC_CURRENT, False),
    2: ("{cls} Space Load (actual)", SPEC_APPARENT_POWER, False),
    3: ("{cls} Demand Factor", SPEC_DEMAND_FACTOR, True),
    4: ("{cls} Connected Current", SPEC_CURRENT, False),
    5: ("{cls} Connected Load", SPEC_APPARENT_POWER, False),
}

#: OUR shared-parameter LIBRARY generator input: per storage KIND a list of
#: (caption stem, spec-or-None, group) our house standard defines.  The
#: library is EXTENDED deterministically (numbered zone / phase variants)
#: when a base needs more definitions of a kind than the stems provide, so
#: EVERY sample slot receives a distinct definition of ours (a rung leaves
#: no residue in the layer).  Domain: an ELECTRICAL / MEP institutional
#: practice (our subject matter -- tekton README).
_SHARED_PARAM_STEMS: Dict[str, List[Tuple[str, Optional[str], str]]] = {
    "ParamDefValue": [
        ("Mounting Height AFF", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Clearance - Front", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Clearance - Rear", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Clearance - Left", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Clearance - Right", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Clearance - Top", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Whip Length", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Trapeze Spacing", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Rod Length", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Cut Length", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Enclosure Width", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Enclosure Height", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Enclosure Depth", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Housekeeping Pad Height", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Panel Working Space Depth", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Rise", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Run", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Setout Offset X", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Setout Offset Y", SPEC_LENGTH, GROUP_DIMENSIONS),
        ("Connected Load", SPEC_APPARENT_POWER, GROUP_ELECTRICAL_LOADS),
        ("Demand Load", SPEC_APPARENT_POWER, GROUP_ELECTRICAL_LOADS),
        ("Spare Capacity", SPEC_APPARENT_POWER, GROUP_ELECTRICAL_LOADS),
        ("Full Load Current", SPEC_CURRENT, GROUP_ELECTRICAL),
        ("Starting Current", SPEC_CURRENT, GROUP_ELECTRICAL),
        ("Available Fault Current", SPEC_CURRENT, GROUP_ELECTRICAL),
        ("Nominal Voltage", SPEC_POTENTIAL, GROUP_ELECTRICAL),
        ("Rated Wattage", SPEC_WATTAGE, GROUP_ELECTRICAL),
        ("Design Illuminance", SPEC_ILLUMINANCE, GROUP_ELECTRICAL_LIGHTING),
        ("Lamp Lumens", SPEC_LUMINOUS_FLUX, GROUP_ELECTRICAL_LIGHTING),
        ("Colour Temperature", SPEC_COLOR_TEMPERATURE, GROUP_ELECTRICAL_LIGHTING),
        ("Luminous Efficacy", SPEC_EFFICACY, GROUP_ELECTRICAL_LIGHTING),
        ("Diversity Factor", SPEC_NUMBER, GROUP_ELECTRICAL_LOADS),
        ("Power Factor", SPEC_NUMBER, GROUP_ELECTRICAL),
        ("Circuit Count", SPEC_INTEGER, GROUP_ELECTRICAL_CIRCUITING),
        ("Spare Ways", SPEC_INTEGER, GROUP_ELECTRICAL_CIRCUITING),
        ("Design Airflow", SPEC_AIRFLOW, GROUP_MECH_AIRFLOW),
        ("Static Pressure", SPEC_PRESSURE, GROUP_MECHANICAL),
        ("Design Temperature", SPEC_TEMPERATURE, GROUP_MECHANICAL),
        ("Domestic Water Flow", SPEC_FLOW, GROUP_PLUMBING),
        ("Nominal Pipe Size", SPEC_PIPE_SIZE, GROUP_PLUMBING),
        ("Unit Weight", SPEC_MASS, GROUP_STRUCTURAL),
        ("Seismic Restraint Force", SPEC_FORCE, GROUP_STRUCTURAL),
        ("Anchorage Moment", SPEC_MOMENT, GROUP_STRUCTURAL),
        ("Support Angle", SPEC_ANGLE, GROUP_DIMENSIONS),
        ("Coverage Area", SPEC_AREA, GROUP_DATA),
        ("Excavation Volume", SPEC_VOLUME, GROUP_DATA),
        ("Unit Cost", SPEC_CURRENCY, GROUP_DATA),
        ("Installed Cost", SPEC_CURRENCY, GROUP_DATA),
        ("Lead Time (days)", SPEC_NUMBER, GROUP_DATA),
        ("Maintenance Interval (days)", SPEC_TIME, GROUP_DATA),
        ("Conveyor Speed", SPEC_SPEED, GROUP_MECHANICAL),
        ("Efficiency", SPEC_NUMBER, GROUP_MECHANICAL),
        ("Quantity", SPEC_INTEGER, GROUP_DATA),
    ],
    "ParamDefString": [
        ("Asset Tag", None, GROUP_IDENTITY), ("Equipment Reference", None, GROUP_IDENTITY),
        ("Fed From", None, GROUP_ELECTRICAL_CIRCUITING), ("Panel Reference", None, GROUP_ELECTRICAL_CIRCUITING),
        ("Circuit Reference", None, GROUP_ELECTRICAL_CIRCUITING),
        ("Room Reference", None, GROUP_IDENTITY), ("Zone", None, GROUP_IDENTITY),
        ("Spec Section", None, GROUP_IDENTITY), ("Submittal Number", None, GROUP_IDENTITY),
        ("Submittal Status", None, GROUP_IDENTITY), ("Manufacturer (basis of design)", None, GROUP_IDENTITY),
        ("Model Number", None, GROUP_IDENTITY), ("Serial Number", None, GROUP_IDENTITY),
        ("Installer", None, GROUP_CONSTRUCTION), ("QA Reviewer", None, GROUP_CONSTRUCTION),
        ("Commissioning Status", None, GROUP_CONSTRUCTION), ("Warranty Terms", None, GROUP_DATA),
        ("O&M Manual Reference", None, GROUP_DATA), ("Barcode", None, GROUP_IDENTITY),
        ("Legacy Tag", None, GROUP_IDENTITY), ("Drawing Reference", None, GROUP_IDENTITY),
        ("Detail Reference", None, GROUP_IDENTITY), ("Revision Note", None, GROUP_GENERAL),
        ("Field Note", None, GROUP_GENERAL), ("Coordination Note", None, GROUP_GENERAL),
        ("Owner Comment", None, GROUP_GENERAL), ("Cable Reference", None, GROUP_ELECTRICAL),
        ("Conduit Reference", None, GROUP_ELECTRICAL), ("Circuit Description", None, GROUP_ELECTRICAL_CIRCUITING),
        ("Load Description", None, GROUP_ELECTRICAL_LOADS), ("Service Type", None, GROUP_MECHANICAL),
        ("System Abbreviation", None, GROUP_MECHANICAL), ("Sequence of Operation", None, GROUP_MECHANICAL),
        ("Control Point Name", None, GROUP_ELECTRICAL), ("BAS Address", None, GROUP_ELECTRICAL),
        ("Firestop System", None, GROUP_CONSTRUCTION), ("Access Requirement", None, GROUP_CONSTRUCTION),
        ("Hazard Class", None, GROUP_CONSTRUCTION), ("Seismic Category", None, GROUP_STRUCTURAL),
        ("Ingress Rating", None, GROUP_DATA), ("Finish Code", None, GROUP_MATERIALS),
        ("Colour Code", None, GROUP_MATERIALS), ("Keying Group", None, GROUP_DATA),
        ("Procurement Package", None, GROUP_DATA), ("Cost Code", None, GROUP_DATA),
    ],
    "ParamDefYesNo": [
        ("Emergency Circuit", None, GROUP_ELECTRICAL_CIRCUITING), ("Life Safety Branch", None, GROUP_ELECTRICAL_CIRCUITING),
        ("Critical Branch", None, GROUP_ELECTRICAL_CIRCUITING), ("Generator Backed", None, GROUP_ELECTRICAL),
        ("UPS Backed", None, GROUP_ELECTRICAL), ("Isolated Ground", None, GROUP_ELECTRICAL),
        ("Seismically Restrained", None, GROUP_STRUCTURAL), ("Fire Rated Penetration", None, GROUP_CONSTRUCTION),
        ("Owner Furnished", None, GROUP_CONSTRUCTION), ("Existing to Remain", None, GROUP_CONSTRUCTION),
        ("Salvage for Owner", None, GROUP_CONSTRUCTION), ("Commissioned", None, GROUP_CONSTRUCTION),
        ("Field Verified", None, GROUP_CONSTRUCTION), ("Approved Substitution", None, GROUP_IDENTITY),
        ("Include in Load Schedule", None, GROUP_ELECTRICAL_LOADS), ("Metered", None, GROUP_ELECTRICAL),
        ("Networked", None, GROUP_ELECTRICAL), ("Dimmable", None, GROUP_ELECTRICAL_LIGHTING),
    ],
    "ParamDefInt": [
        ("Number of Poles (schedule)", None, GROUP_ELECTRICAL), ("Number of Phases", None, GROUP_ELECTRICAL),
        ("Frequency (Hz)", None, GROUP_ELECTRICAL), ("Insulation Class", None, GROUP_ELECTRICAL),
        ("Priority Level", None, GROUP_DATA), ("Redundancy Count", None, GROUP_DATA),
    ],
    "ParamDefMaterialBrowse": [
        ("Housing Material", None, GROUP_MATERIALS), ("Finish Material", None, GROUP_MATERIALS),
        ("Bus Material", None, GROUP_MATERIALS), ("Conductor Material", None, GROUP_MATERIALS),
        ("Support Material", None, GROUP_MATERIALS), ("Insulation Material", None, GROUP_MATERIALS),
        ("Gasket Material", None, GROUP_MATERIALS), ("Backing Material", None, GROUP_MATERIALS),
        ("Encasement Material", None, GROUP_MATERIALS), ("Cover Plate Material", None, GROUP_MATERIALS),
    ],
    "ParamDefURL": [
        ("Product Data Sheet URL", None, GROUP_IDENTITY), ("Installation Manual URL", None, GROUP_IDENTITY),
        ("Warranty URL", None, GROUP_DATA), ("BIM Object URL", None, GROUP_DATA),
    ],
    "ParamDefFamType": [
        ("Nested Bracket Type", None, GROUP_CONSTRUCTION), ("Nested Support Type", None, GROUP_CONSTRUCTION),
        ("Tag Type Override", None, GROUP_GENERAL), ("Mounting Kit Type", None, GROUP_CONSTRUCTION),
    ],
    "ParamDefNoOfPoles": [
        ("Breaker Poles", None, GROUP_ELECTRICAL), ("Switch Poles", None, GROUP_ELECTRICAL),
        ("Disconnect Poles", None, GROUP_ELECTRICAL),
    ],
}
#: qualifiers used to extend a kind's stems deterministically to any count
_STEM_QUALIFIERS = ["A", "B", "C", "N", "L1", "L2", "L3", "Zone 1", "Zone 2", "Zone 3",
                    "Phase 1", "Phase 2", "Level 1", "Level 2", "Riser", "Feeder", "Branch"]


def our_shared_parameter_captions(kind: str, count: int) -> List[Tuple[str, Optional[str], str]]:
    """OUR ``count`` distinct (caption, spec, group) triples for a ParamDef
    storage ``kind``: the house stems first, then stem x qualifier extensions
    (deterministic order).  Every caption is GEN-prefixed and unique."""
    stems = list(_SHARED_PARAM_STEMS.get(kind) or [(f"Attribute {kind}", None, GROUP_GENERAL)])
    out: List[Tuple[str, Optional[str], str]] = []
    seen: Set[str] = set()
    i = 0
    # round 0: plain stems; round k>=1: stem + qualifier[k-1]
    rounds = 1 + len(_STEM_QUALIFIERS)
    for k in range(rounds):
        for stem, spec, group in stems:
            cap = stem if k == 0 else f"{stem} - {_STEM_QUALIFIERS[k - 1]}"
            cap = gen(cap)
            if cap in seen:
                continue
            seen.add(cap)
            out.append((cap, spec, group))
            i += 1
            if i >= count:
                return out
    # (never reached in practice: 53 stems x 18 rounds >> 466)
    n = len(out)
    while len(out) < count:                                     # pragma: no cover
        n += 1
        out.append((gen(f"Attribute {kind} {n}"), None, GROUP_GENERAL))
    return out[:count]


def shared_parameter(caption: str, guid: str, *, kind: str = "ParamDefValue",
                     spec: Optional[str] = SPEC_LENGTH, group: str = GROUP_GENERAL,
                     description: str = "", user_visible: bool = True,
                     hide_when_no_value: bool = False, read_only: bool = False,
                     binding_ids: Sequence[int] = (), ids: IdArg = None,
                     elem_id: int = None) -> TypeRecord:
    """A ``ParamElemExternal`` = a SHARED-PARAMETER DEFINITION.

    DEFINITION (our free values): ``caption`` (the parameter's name),
    ``description``, ``group`` (its property-palette group), and for
    measurable kinds the ``spec`` (Autodesk's public 'autodesk.spec.*' id).
    ``kind`` = the ParamDef storage class (:data:`PARAM_DEF_CLASSES`).

    REGISTRATION (machinery, per slot): ``guid`` -- the shared parameter's
    global identity -- is the KEY of ``ExternalParamTracking.m_keyDataMap`` in
    Global/Latest AND is embedded in ``m_pParamDef.m_typeId`` as
    ``'revit.local.shared:<guid without dashes>-1.0.0'`` [VERIFIED 466/466:
    guid == typeId token]; an in-place rung MUST keep the slot's GUID (the
    registry stays byte-identical) -- pass the slot's GUID here.  A NEW
    shared parameter of ours (add path) takes ``_stable_guid('shared', caption)``.
    ``binding_ids`` = its ParamBinding rows (ids preserved in place).
    ``m_paramElemId`` == its own element id (machinery).  [VERIFIED layout
    field-for-field vs rstbasic 21308 / 198377.]
    """
    if kind not in PARAM_DEF_CLASSES:
        raise ValueError(f"unknown ParamDef kind {kind!r}")
    eid = _alloc(ids, elem_id)
    g = str(guid).lower()
    obj = blank_object("ParamElemExternal")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    obj["m_description"] = str(description)
    pd = blank_object(kind)
    pd["m_dynamicGroupName"] = ""
    pd["m_groupTypeId"] = {"m_typeId": str(group or "")}
    pd["m_caption"] = str(caption)
    pd["m_typeId"] = {"m_typeId": f"revit.local.shared:{g.replace('-', '')}-1.0.0"}
    pd["m_paramElemId"] = int(eid)
    pd["m_allowVaryBetweenGroups"] = False
    pd["m_readOnly"] = bool(read_only)
    pd["m_userVisible"] = bool(user_visible)
    if kind in _VALUE_DEF_CLASSES:
        pd["m_specTypeId"] = {"m_typeId": str(spec or SPEC_NUMBER)}
        pd["m_restriction"] = 1
        pd["m_boundless"] = False
    obj["m_pParamDef"] = _ptr(kind, pd)
    obj["m_bindingIds"] = [int(b) for b in binding_ids]
    obj["m_externalParamKey"] = {"m_guidValue": g}
    obj["m_hideWhenNoValue"] = bool(hide_when_no_value)
    obj["m_userModifiable"] = True
    return _record("shared-parameter", "ParamElemExternal", INVALID, eid, obj,
                   deletion_ids=list(binding_ids),
                   refs={"guid": g, "kind": kind, "spec": spec, "group": group,
                         "bindings": list(binding_ids)},
                   notes=["registration: GUID is the ExternalParamTracking key + the "
                          "typeId token (kept per slot in place)"])


def project_parameter(caption: str, type_id_token: str, *, kind: str = "ParamDefString",
                      spec: Optional[str] = None, group: str = GROUP_IDENTITY,
                      description: str = "", user_visible: bool = True,
                      binding_ids: Sequence[int] = (), internal_name: str = "",
                      flags: int = 0, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``ParamElemProject`` = a PROJECT-PARAMETER DEFINITION.

    Our free values: ``caption``, ``description``, ``group``, ``kind``
    (storage class), ``spec`` for value kinds.  REGISTRATION (machinery, per
    slot): ``type_id_token`` -- the whole 'revit.local.project:<session-guid>
    <element-id hex>-1.0.0' token (its 8-hex suffix IS the element id
    [VERIFIED 8/8]) and ``binding_ids``; ``ProjectParamTracking.m_elemIdSet``
    indexes the ids.  For a NEW project parameter of ours (add path) build
    the token as ``project_param_type_id(session_guid, elem_id)``.
    [VERIFIED layout vs rstbasic 26010 / 713618.]"""
    if kind not in PARAM_DEF_CLASSES:
        raise ValueError(f"unknown ParamDef kind {kind!r}")
    eid = _alloc(ids, elem_id)
    obj = blank_object("ParamElemProject")
    element_defaults(obj, eid)
    obj["m_cellList"] = _cell_list_pattern_helper()
    obj["m_description"] = str(description)
    pd = blank_object(kind)
    pd["m_dynamicGroupName"] = ""
    pd["m_groupTypeId"] = {"m_typeId": str(group or "")}
    pd["m_caption"] = str(caption)
    pd["m_typeId"] = {"m_typeId": str(type_id_token)}
    pd["m_paramElemId"] = int(eid)
    pd["m_allowVaryBetweenGroups"] = False
    pd["m_readOnly"] = False
    pd["m_userVisible"] = bool(user_visible)
    if kind in _VALUE_DEF_CLASSES:
        pd["m_specTypeId"] = {"m_typeId": str(spec or SPEC_NUMBER)}
        pd["m_restriction"] = 1
        pd["m_boundless"] = False
    obj["m_pParamDef"] = _ptr(kind, pd)
    obj["m_bindingIds"] = [int(b) for b in binding_ids]
    obj["m_internalName"] = str(internal_name)
    obj["m_nFlags"] = int(flags)
    return _record("project-parameter", "ParamElemProject", INVALID, eid, obj,
                   deletion_ids=list(binding_ids),
                   refs={"kind": kind, "type_id": type_id_token, "bindings": list(binding_ids)},
                   notes=["registration: the typeId token embeds the element id (kept per slot)"])


def project_param_type_id(session_guid: str, elem_id: int, scope: str = "project",
                          version: str = "1.0.0") -> str:
    """The 'revit.local.<scope>:<session-guid><element-id hex>-<version>'
    token a locally-defined parameter carries (add-path helper; in place the
    slot's own token is kept)."""
    return (f"revit.local.{scope}:{str(session_guid).lower().replace('-', '')}"
            f"{int(elem_id) & 0xFFFFFFFF:08x}-{version}")


def load_classification_parameter(load_classification_id: int, e_type: int,
                                  classification_name: str, type_id_token: str, *,
                                  caption: Optional[str] = None,
                                  ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``ParamElemElectricalLoadClassification`` = one of the SIX
    schedule-column parameters Revit registers per load classification
    (m_eType 0..5, :data:`LOAD_CLASS_PARAM_ROLES`).  MACHINERY: the role
    (m_eType), its spec type, ``m_idLoadClassification`` (the Group-A
    ElectricalLoadClassification, id preserved in place), the typeId token
    (embeds the element id), group = electricalLoads, m_bTotal False.  OURS:
    the caption phrasing ('GEN Lighting Connected Load', ...) built from
    ``classification_name``.  [VERIFIED 18 classes x 6 roles = 108 on rst;
    role->spec map verified on all 108.]"""
    if int(e_type) not in LOAD_CLASS_PARAM_ROLES:
        raise ValueError(f"unknown load-classification param role {e_type}")
    pattern, spec, read_only = LOAD_CLASS_PARAM_ROLES[int(e_type)]
    eid = _alloc(ids, elem_id)
    cap = caption if caption is not None else gen(pattern.format(cls=str(classification_name).strip()))
    obj = blank_object("ParamElemElectricalLoadClassification")
    element_defaults(obj, eid)
    obj["m_cellList"] = _cell_list_pattern_helper()
    obj["m_description"] = ""
    pd = blank_object("ParamDefValue")
    pd["m_dynamicGroupName"] = ""
    pd["m_groupTypeId"] = {"m_typeId": GROUP_ELECTRICAL_LOADS}
    pd["m_caption"] = str(cap)
    pd["m_typeId"] = {"m_typeId": str(type_id_token)}
    pd["m_paramElemId"] = int(eid)
    pd["m_allowVaryBetweenGroups"] = False
    pd["m_readOnly"] = bool(read_only)
    pd["m_userVisible"] = True
    pd["m_specTypeId"] = {"m_typeId": spec}
    pd["m_restriction"] = 1
    pd["m_boundless"] = False
    obj["m_pParamDef"] = _ptr("ParamDefValue", pd)
    obj["m_idLoadClassification"] = int(load_classification_id)
    obj["m_eType"] = int(e_type)
    obj["m_bTotal"] = False
    return _record("load-class-parameter", "ParamElemElectricalLoadClassification", INVALID, eid, obj,
                   deletion_ids=[load_classification_id] if load_classification_id not in (None, INVALID) else [],
                   refs={"load_classification": load_classification_id, "role": int(e_type), "spec": spec},
                   notes=["role/spec/typeId/classification wiring = machinery; the caption "
                          "phrasing is ours"])


def param_binding(param_id: int, category_id: int, elem_or_symbol: int = 1, *,
                  ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``ParamBinding`` = the registration of parameter ``param_id`` to
    built-in category ``category_id`` (``elem_or_symbol`` 1 = instance
    binding, 2 = type binding).  The class carries NO free value: it is pure
    machinery {m_paramId, m_categoryId, m_elemOrSymbol}, registered in
    ``ParamBindingTracking.m_itemSet`` by category -- our constructor
    REPRODUCES it (nothing of ours to reject).  [VERIFIED layout vs rstbasic
    198378 / 26011: instance bindings carry a null CellList, the id-26011
    era one a PatternHelper CellList -- both forms open; ours = null.]"""
    eid = _alloc(ids, elem_id)
    obj = blank_object("ParamBinding")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    obj["m_paramId"] = int(param_id)
    obj["m_categoryId"] = int(category_id)
    obj["m_elemOrSymbol"] = int(elem_or_symbol)
    return _record("param-binding", "ParamBinding", INVALID, eid, obj,
                   deletion_ids=[param_id] if param_id not in (None, INVALID) else [],
                   refs={"param": param_id, "category": category_id, "elem_or_symbol": elem_or_symbol},
                   notes=["PURE MACHINERY: a param-to-category registration; reproduced, "
                          "nothing of ours to reject"])


# ===========================================================================
# 3. THE MEP CATALOG (ZB2_mepcat): wire + piping catalogs
# ===========================================================================
#: OUR wire-catalog SELECTION.  The DESIGNATIONS are industry facts (NEC
#: article 310 insulation type letters; conductor materials); the selection
#: and every OBJECT are ours.  (types.new_wire_material_type / insulation /
#: temperature constructors exist -- wrapped here to carry the corpus
#: CellList{PatternHelper} machinery every catalog symbol has [26/26].)
WIRE_MATERIALS: List[str] = ["Copper", "Aluminum", "Copper-Clad Aluminum", "Steel (bond/messenger)"]
WIRE_TEMPERATURE_RATINGS: List[str] = ["60", "75", "90"]      # deg C (NEC Table 310.16 columns)
#: NEC 310.104(A) conductor insulation designations we schedule (26 = the
#: sample's count; the SET is our choice among the code designations)
WIRE_INSULATIONS: List[str] = [
    "THHN", "THWN", "THWN-2", "THW", "THW-2", "THHW", "TW", "XHHW", "XHHW-2",
    "XHH", "RHH", "RHW", "RHW-2", "RH", "USE", "USE-2", "UF", "MI", "MC-cable",
    "AC-cable", "FEP", "FEPB", "SA", "SIS", "TBS", "ZW",
]


def _wire_symbol(class_name: str, kind: str, category: int, name: str, *,
                 ids: IdArg, elem_id: Optional[int]) -> TypeRecord:
    """The pure-name MEP catalog symbol (definition = the name only), with
    the corpus machinery every catalog symbol carries: a PRESENT empty
    AString param set + ``CellList{PatternHelper}`` [VERIFIED 26/26 wire
    insulation, 4/4 wire material, 3/3 temperature rating on rst/rac/rme]."""
    eid = _alloc(ids, elem_id)
    obj = blank_object(class_name)
    element_defaults(obj, eid, astring_params={})
    obj["m_cellList"] = _cell_list_pattern_helper()
    symbol_defaults(obj, name)
    return _record(kind, class_name, category, eid, obj,
                   notes=["catalog symbol: definition = the name; machinery = "
                          "CellList{PatternHelper} + empty AString param set"])


def wire_material_type(name: str, *, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """``RbsWireMaterialType`` (a conductor MATERIAL of the wire catalog)."""
    return _wire_symbol("RbsWireMaterialType", "wire-material", TY.OST_WireMaterial,
                        name, ids=ids, elem_id=elem_id)


def wire_insulation_type(name: str, *, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """``RbsWireInsulationType`` (an NEC insulation designation)."""
    return _wire_symbol("RbsWireInsulationType", "wire-insulation", TY.OST_WireInsulation,
                        name, ids=ids, elem_id=elem_id)


def wire_temperature_rating_type(name: str, *, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """``RbsWireTemperatureRatingType`` (a conductor temperature rating in
    deg C as text -- the NEC ampacity table columns)."""
    return _wire_symbol("RbsWireTemperatureRatingType", "wire-temperature",
                        TY.OST_WireTemperatureRating, name, ids=ids, elem_id=elem_id)


# ---- piping catalog -------------------------------------------------------
#: BuiltInCategory ids of the piping catalog symbols [VERIFIED headers on
#: rst/rme: RbsPipeMaterialType -2008049? -- the segments' category].  The
#: schedule / connection / material symbols carry category -1 in the corpus
#: headers we do NOT replace (seq-101 stays); recorded for the add path.
OST_PipeSegments = -2008159
#: builtin double parameter of a pipe MATERIAL type: its roughness (mm)
#: [VERIFIED all 5 rst pipe materials: -1140204 = the material's absolute
#: roughness, e.g. carbon steel 0.04572 mm]
BIP_PIPE_MATERIAL_ROUGHNESS = -1140204

#: OUR piping catalog: material -> (absolute roughness mm [FACT: published
#: hydraulic roughness -- Moody / Colebrook references: commercial steel
#: 0.045 mm, drawn copper tube 0.0015 mm, PVC/plastic 0.0015 mm, ductile
#: iron 0.26 mm, stainless 0.002 mm], schedules the material is stocked in).
#: NAMES: the material designation is a FACT of the trade; the segment
#: NAMES ('GEN Steel Pipe (ASME B36.10 Sch 40)') are ours.
PIPE_MATERIALS: List[Dict[str, Any]] = [
    {"key": "steel", "name": "Carbon Steel", "roughness_mm": 0.045},
    {"key": "stainless", "name": "Stainless Steel", "roughness_mm": 0.002},
    {"key": "copper", "name": "Copper (drawn tube)", "roughness_mm": 0.0015},
    {"key": "pvc", "name": "PVC (plastic)", "roughness_mm": 0.0015},
    {"key": "ductile", "name": "Ductile Iron", "roughness_mm": 0.26},
]
#: joining methods (RbsPipeConnectionType) -- the standard trade methods
PIPE_CONNECTIONS: List[str] = ["Threaded", "Flanged", "Butt Welded", "Grooved",
                               "Soldered", "Brazed", "Press-Fit", "Bell and Spigot (push-on)"]
#: pipe schedules (RbsPipeScheduleType) -- ASME / ASTM / AWWA designations
PIPE_SCHEDULES: List[str] = ["Schedule 40", "Schedule 80", "Schedule 10S", "Schedule 5S",
                             "Type K", "Type L", "Type M", "SDR 21", "SDR 26", "Schedule 120",
                             "Class 350 (AWWA C151)", "Class 250 (AWWA C151)", "STD"]


def pipe_schedule_type(name: str, *, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """``RbsPipeScheduleType`` -- a pipe SCHEDULE (wall-thickness series)
    of the piping catalog.  Definition = the designation name; machinery =
    the empty AString param set + CellList{PatternHelper} [VERIFIED 13/13]."""
    return _wire_symbol("RbsPipeScheduleType", "pipe-schedule", INVALID,
                        name, ids=ids, elem_id=elem_id)


def pipe_connection_type(name: str, *, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """``RbsPipeConnectionType`` -- a JOINING METHOD of the piping catalog.
    Definition = the name; same machinery as every catalog symbol [8/8]."""
    return _wire_symbol("RbsPipeConnectionType", "pipe-connection", INVALID,
                        name, ids=ids, elem_id=elem_id)


def pipe_material_type(name: str, roughness_mm: float, *, ids: IdArg = None,
                       elem_id: int = None) -> TypeRecord:
    """``RbsPipeMaterialType`` -- a pipe MATERIAL of the piping catalog.
    Definition = the name + its absolute ROUGHNESS carried in a present
    ParamValueSetDouble under builtin -1140204 (millimetres) [VERIFIED all 5
    rst pipe materials: carbon steel 0.04572 / stainless 0.0018 / copper
    0.00254 / plastic 0.00254 / ductile iron 0.25908 -- the DOUBLE set
    serialises value first].  Machinery = CellList{PatternHelper} + empty
    AString set."""
    eid = _alloc(ids, elem_id)
    obj = blank_object("RbsPipeMaterialType")
    element_defaults(obj, eid, astring_params={})
    obj["m_pParamValueSetDouble"] = _double_param_set([(float(roughness_mm), BIP_PIPE_MATERIAL_ROUGHNESS)])
    obj["m_cellList"] = _cell_list_pattern_helper()
    symbol_defaults(obj, name)
    return _record("pipe-material", "RbsPipeMaterialType", INVALID, eid, obj,
                   refs={"roughness_mm": float(roughness_mm)},
                   notes=["roughness (mm) in ParamValueSetDouble[-1140204] -- a published "
                          "hydraulic fact of the material; the name is the trade designation"])


#: OUR pipe SIZE data = published dimensional facts: ASME B36.10M carbon /
#: alloy steel (schedule 40 / 80 / STD), ASME B36.19M stainless (10S / 5S),
#: ASTM B88 copper tube (K / L / M), ASTM D1785 PVC schedule 40/80 IDs,
#: AWWA C151 ductile iron.  (nominal NPS inch, outside diameter inch, wall
#: inch) -> inner = OD - 2 wall; stored in FEET.  The RANGE we stock (1/2..12
#: in) is our choice.  (genesis_substitute._ASME_* holds the same B36.10 /
#: B88 tables for the RbsPipeSizesElem rung -- one source of truth per
#: standard; the ductile / SDR series below are additions.)
_B36_10_SCH40 = [(0.5, 0.840, 0.109), (0.75, 1.050, 0.113), (1.0, 1.315, 0.133),
                 (1.25, 1.660, 0.140), (1.5, 1.900, 0.145), (2.0, 2.375, 0.154),
                 (2.5, 2.875, 0.203), (3.0, 3.500, 0.216), (4.0, 4.500, 0.237),
                 (5.0, 5.563, 0.258), (6.0, 6.625, 0.280), (8.0, 8.625, 0.322),
                 (10.0, 10.750, 0.365), (12.0, 12.750, 0.406)]
_B36_10_SCH80 = [(0.5, 0.840, 0.147), (0.75, 1.050, 0.154), (1.0, 1.315, 0.179),
                 (1.25, 1.660, 0.191), (1.5, 1.900, 0.200), (2.0, 2.375, 0.218),
                 (2.5, 2.875, 0.276), (3.0, 3.500, 0.300), (4.0, 4.500, 0.337),
                 (5.0, 5.563, 0.375), (6.0, 6.625, 0.432), (8.0, 8.625, 0.500),
                 (10.0, 10.750, 0.594), (12.0, 12.750, 0.688)]
_B36_19_10S = [(0.5, 0.840, 0.083), (0.75, 1.050, 0.083), (1.0, 1.315, 0.109),
               (1.25, 1.660, 0.109), (1.5, 1.900, 0.109), (2.0, 2.375, 0.109),
               (2.5, 2.875, 0.120), (3.0, 3.500, 0.120), (4.0, 4.500, 0.120),
               (6.0, 6.625, 0.134), (8.0, 8.625, 0.148), (10.0, 10.750, 0.165),
               (12.0, 12.750, 0.180)]
_B36_19_5S = [(0.5, 0.840, 0.065), (0.75, 1.050, 0.065), (1.0, 1.315, 0.065),
              (1.25, 1.660, 0.065), (1.5, 1.900, 0.065), (2.0, 2.375, 0.065),
              (2.5, 2.875, 0.083), (3.0, 3.500, 0.083), (4.0, 4.500, 0.083),
              (6.0, 6.625, 0.109), (8.0, 8.625, 0.109), (10.0, 10.750, 0.134),
              (12.0, 12.750, 0.156)]
_B88_TYPE_K = [(0.5, 0.625, 0.049), (0.75, 0.875, 0.065), (1.0, 1.125, 0.065),
               (1.25, 1.375, 0.065), (1.5, 1.625, 0.072), (2.0, 2.125, 0.083),
               (2.5, 2.625, 0.095), (3.0, 3.125, 0.109), (4.0, 4.125, 0.134),
               (5.0, 5.125, 0.160), (6.0, 6.125, 0.192), (8.0, 8.125, 0.271)]
_B88_TYPE_L = [(0.5, 0.625, 0.040), (0.75, 0.875, 0.045), (1.0, 1.125, 0.050),
               (1.25, 1.375, 0.055), (1.5, 1.625, 0.060), (2.0, 2.125, 0.070),
               (2.5, 2.625, 0.080), (3.0, 3.125, 0.090), (4.0, 4.125, 0.110),
               (5.0, 5.125, 0.125), (6.0, 6.125, 0.140), (8.0, 8.125, 0.200)]
_B88_TYPE_M = [(0.5, 0.625, 0.028), (0.75, 0.875, 0.032), (1.0, 1.125, 0.035),
               (1.25, 1.375, 0.042), (1.5, 1.625, 0.049), (2.0, 2.125, 0.058),
               (2.5, 2.625, 0.065), (3.0, 3.125, 0.072), (4.0, 4.125, 0.095),
               (5.0, 5.125, 0.109), (6.0, 6.125, 0.122), (8.0, 8.125, 0.170)]
#: ASTM D1785 / D2665 PVC: schedule 40 & 80 share the steel OD series with
#: their own (min) walls [FACT: ASTM D1785 dimension tables]
_PVC_SCH40 = [(0.5, 0.840, 0.109), (0.75, 1.050, 0.113), (1.0, 1.315, 0.133),
              (1.25, 1.660, 0.140), (1.5, 1.900, 0.145), (2.0, 2.375, 0.154),
              (3.0, 3.500, 0.216), (4.0, 4.500, 0.237), (6.0, 6.625, 0.280),
              (8.0, 8.625, 0.322), (10.0, 10.750, 0.365), (12.0, 12.750, 0.406)]
_PVC_SCH80 = [(0.5, 0.840, 0.147), (0.75, 1.050, 0.154), (1.0, 1.315, 0.179),
              (1.25, 1.660, 0.191), (1.5, 1.900, 0.200), (2.0, 2.375, 0.218),
              (3.0, 3.500, 0.300), (4.0, 4.500, 0.337), (6.0, 6.625, 0.432),
              (8.0, 8.625, 0.500), (10.0, 10.750, 0.593), (12.0, 12.750, 0.687)]
#: AWWA C151 ductile iron pressure class 350 (nominal, OD in; wall in)
#: [FACT: AWWA C151/A21.51 dimension table, class 350]
_AWWA_C151_CL350 = [(4.0, 4.80, 0.25), (6.0, 6.90, 0.25), (8.0, 9.05, 0.25),
                    (10.0, 11.10, 0.26), (12.0, 13.20, 0.28), (14.0, 15.30, 0.28),
                    (16.0, 17.40, 0.30), (18.0, 19.50, 0.31), (20.0, 21.60, 0.33),
                    (24.0, 25.80, 0.37)]

PIPE_SIZE_TABLES: Dict[str, list] = {
    "b36.10-sch40": _B36_10_SCH40, "b36.10-sch80": _B36_10_SCH80,
    "b36.19-10s": _B36_19_10S, "b36.19-5s": _B36_19_5S,
    "b88-k": _B88_TYPE_K, "b88-l": _B88_TYPE_L, "b88-m": _B88_TYPE_M,
    "pvc-sch40": _PVC_SCH40, "pvc-sch80": _PVC_SCH80,
    "awwa-c151-cl350": _AWWA_C151_CL350,
}


def pipe_size_rows(table_key: str) -> List[Tuple[float, float, float]]:
    """(nominal, inner, outer) in FEET for a size table."""
    out = []
    for nom, od, wall in PIPE_SIZE_TABLES[table_key]:
        out.append((inches(nom), inches(od - 2.0 * wall), inches(od)))
    return out


def _table_for_schedule(schedule_name: str, material_name: str = "") -> str:
    """Choose OUR dimension table for a (schedule, material) designation --
    the documented rule the segment rung applies to each slot's names."""
    s = str(schedule_name or "").strip().lower()
    m = str(material_name or "").strip().lower()
    if "5s" in s:
        return "b36.19-5s"
    if "10s" in s:
        return "b36.19-10s"
    if "80" in s:
        return "pvc-sch80" if ("plastic" in m or "pvc" in m) else "b36.10-sch80"
    if s in ("k", "type k", "a"):
        return "b88-k"
    if s in ("l", "type l", "b"):
        return "b88-l"
    if s in ("m", "type m", "c", "d"):
        return "b88-m"
    if "copper" in m:
        return "b88-l"
    if any(t in s for t in ("class", "awwa", "22", "30")) or "ductile" in m or "iron" in m:
        return "awwa-c151-cl350"
    if "plastic" in m or "pvc" in m or "sdr" in s:
        return "pvc-sch40"
    return "b36.10-sch40"


def pipe_segment(name: str, material_id: int, schedule_id: int,
                 size_rows_ft: Sequence[Tuple[float, float, float]],
                 roughness_mm: float = 0.045, *, description: str = "",
                 shape: int = 0, connection_type: int = 0,
                 used_by_sizing: bool = True, ids: IdArg = None,
                 elem_id: int = None) -> TypeRecord:
    """A ``PipeSegment`` = one (material, schedule) row of the pipe SIZE
    catalog: its name, the size rows ``[(nominal, inner, outer) ft]``, the
    absolute roughness (mm), and the wiring to its material / schedule
    symbols (``material_id`` = a MaterialElem, ``schedule_id`` = an
    RbsPipeScheduleType -- the slot's own ids in place).  m_shape 0
    (round) / m_connectionType 0 [VERIFIED constant 15/15 rst; the sizes
    are OUR published dimensional data]."""
    eid = _alloc(ids, elem_id)
    obj = blank_object("PipeSegment")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    obj["m_description"] = str(description)
    obj["m_name"] = str(name)
    obj["m_sizeData"] = [{"m_dSize": float(n), "m_dInnerDiameter": float(i),
                          "m_dOuterDiameter": float(o), "m_bInSizeList": True,
                          "m_bUsedBySizing": bool(used_by_sizing)}
                         for (n, i, o) in size_rows_ft]
    obj["m_materialId"] = int(material_id)
    obj["m_roughness"] = float(roughness_mm)
    obj["m_connectionType"] = int(connection_type)
    obj["m_shape"] = int(shape)
    obj["m_scheduleTypeId"] = int(schedule_id)
    dele = [x for x in (material_id, schedule_id) if x not in (None, INVALID)]
    return _record("pipe-segment", "PipeSegment", OST_PipeSegments, eid, obj,
                   deletion_ids=dele,
                   refs={"material": material_id, "schedule": schedule_id,
                         "rows": len(size_rows_ft), "roughness_mm": roughness_mm},
                   notes=["size rows = published ASME/ASTM/AWWA dimensions (our selection); "
                          "material/schedule wiring kept per slot"])


# ===========================================================================
# 4. FAMILY-SCOPED PEN TABLES (ZB3_pens) -- the curtain SYSTEM families' own
# ===========================================================================

def family_pen_width_table(family_id: int, *, ids: IdArg = None,
                           elem_id: int = None) -> TypeRecord:
    """A curtain-SYSTEM-family-scoped ``PenWidthTableElem`` (m_famId = the
    family): OUR ISO-128 pen series (settings.pen_width_table) with the
    family scope kept -- the family is the slot's REGISTRATION (Group A owns
    the 8 Family elements; their pen tables are ours).  [VERIFIED structure
    vs rst 1218557 (m_famId 8482 'Rectangular Mullion'), all six scale
    breakpoints identical to the project table.]"""
    rec = ST.pen_width_table(ids=ids, elem_id=elem_id, family_id=int(family_id))
    rec.kind = "family-pen-table"
    rec.refs = dict(rec.refs, family_id=int(family_id))
    rec.notes.append(f"family-scoped: m_famId = {int(family_id)} (the curtain SYSTEM family, "
                     "kept per slot); our ISO-128 pen widths")
    return rec


# ===========================================================================
# 5. ANNOTATION ATTRIBUTE TYPES (ZB4_annot): SectionAttributes / ViewportAttributes
# ===========================================================================
#: OUR section-mark drafting standard (a house convention, like the pen
#: table): the section tail is a 10 mm long / 2.5 mm wide filled arrow tail;
#: the broken-line display of a jogged section shows the head at both ends
#: (m_styleForBrokenDisplay 0 = 'gap' per Revit's SectionMarkStyle enum
#: [ASSUMED enum name; the corpus value is 0 on 10/10]).
SECTION_TAIL_LENGTH_MM = 10.0
SECTION_TAIL_WIDTH_MM = 2.5
#: our section-type NAMES (10 = the sample's count; head/tail pairing is
#: the naming convention 'Head - Tail')
SECTION_TYPE_NAMES: List[str] = [
    "Section Head - Filled, Tail - Filled", "Section Head - Filled, Tail - None",
    "Section Head - Open, Tail - Open", "Section Head - Open, Tail - Filled",
    "Detail Cut", "Wall Section", "Building Section", "Enlarged Detail Section",
    "Electrical Room Section", "Riser Cut",
]


def section_attributes(name: str, *, font_id: int, category_id: int,
                       tail_length_mm: float = SECTION_TAIL_LENGTH_MM,
                       tail_width_mm: float = SECTION_TAIL_WIDTH_MM,
                       bold: bool = False, italic: bool = False, underline: bool = False,
                       background: int = 0, broken_display_style: int = 0,
                       head_family_tag_id: int = INVALID, tail_family_tag_id: int = INVALID,
                       ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``SectionAttributes`` = a SECTION MARK TYPE (head + tail graphics
    of a section line).  OURS: the name, the tail length/width (mm), the
    text weight flags, the broken-display style.  MACHINERY (per slot, kept):
    ``m_lineAndTextAttr`` wiring to the type's OWN FontElem (``font_id``)
    and its line sub-category (``category_id``) -- Group-A companion
    classes; the head/tail family tag symbols (-1 in the family-free K4
    lineage: K3 nulled family usage).  [VERIFIED layout vs rst 26029; tail
    0.0295 ft x 0.00656 ft on 10/10 = Autodesk's 9 x 2 mm; ours 10 x 2.5.]"""
    eid = _alloc(ids, elem_id)
    obj = blank_object("SectionAttributes")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    symbol_defaults(obj, name)
    obj["m_lineAndTextAttr"] = {"m_fontId": int(font_id), "m_categoryId": int(category_id),
                                "m_background": int(background), "m_bBold": bool(bold),
                                "m_bItalic": bool(italic), "m_bUnderline": bool(underline)}
    obj["m_sectionTailLength"] = mm(tail_length_mm)
    obj["m_sectionTailWidth"] = mm(tail_width_mm)
    obj["m_sectionHeadFamilyTagId"] = int(head_family_tag_id)
    obj["m_sectionTailFamilyTagId"] = int(tail_family_tag_id)
    obj["m_styleForBrokenDisplay"] = int(broken_display_style)
    dele = [x for x in (category_id, font_id, head_family_tag_id, tail_family_tag_id)
            if x not in (None, INVALID)]
    return _record("section-attributes", "SectionAttributes", INVALID, eid, obj,
                   deletion_ids=dele,
                   refs={"font": font_id, "category": category_id,
                         "tail_mm": [tail_length_mm, tail_width_mm]},
                   notes=["font/category companion wiring kept per slot (Group-A classes); "
                          "the head/tail family tags are -1 in a family-free base"])


def viewport_attributes(name: str, *, category_id: int, show_label: int = 1,
                        show_box: bool = False, show_extension_line: bool = True,
                        preserve_title_position: bool = False, family_tag_id: int = INVALID,
                        ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``ViewportAttributes`` = a VIEWPORT TITLE TYPE (the title graphics
    of a viewport on a sheet).  OURS: the name + the title options
    (label / box / extension line / preserve position).  MACHINERY (kept):
    ``category_id`` = its own line sub-category (a Group-A CategoryElem);
    ``family_tag_id`` -1 in the family-free lineage.  [VERIFIED layout vs
    rst 324 'Title w Line'.]"""
    eid = _alloc(ids, elem_id)
    obj = blank_object("ViewportAttributes")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    symbol_defaults(obj, name)
    obj["m_familyTagId"] = int(family_tag_id)
    obj["m_categoryId"] = int(category_id)
    obj["m_showLabel"] = int(show_label)
    obj["m_showBox"] = bool(show_box)
    obj["m_showExtensionLine"] = bool(show_extension_line)
    obj["m_preserveTitlePosition"] = bool(preserve_title_position)
    dele = [x for x in (category_id, family_tag_id) if x not in (None, INVALID)]
    return _record("viewport-attributes", "ViewportAttributes", INVALID, eid, obj,
                   deletion_ids=dele, refs={"category": category_id},
                   notes=["its line sub-category id kept per slot (Group-A CategoryElem)"])


# ===========================================================================
# 6. THE PALETTE COMPANIONS (ZB5_palette): our EXTENDED materials + our
#    physical (structural) ASSET property sets
# ===========================================================================
#: OUR EXTENDED material palette (10 more graphics-only materials for the
#: sample's 10 surplus material slots -- house_standard.MATERIALS covers
#: the first 13; these are the MEP / electrical additions).  Representational
#: colours are our pick; no appearance asset.
EXTENDED_MATERIALS: List[Dict[str, Any]] = [
    {"key": "copper", "name": gen("Copper, Busbar"), "rgb": (184, 115, 51),
     "material_class": "Metal", "category": "Electrical"},
    {"key": "aluminum", "name": gen("Aluminum, Anodized"), "rgb": (192, 195, 200),
     "material_class": "Metal", "category": "Electrical"},
    {"key": "steel_galv", "name": gen("Steel, Galvanized"), "rgb": (160, 165, 168),
     "material_class": "Metal", "category": "Support Systems", "cut_pattern": "solid"},
    {"key": "steel_enamel", "name": gen("Steel, Powder-Coated ANSI 61 Gray"), "rgb": (137, 139, 142),
     "material_class": "Metal", "category": "Enclosures"},
    {"key": "iron_ductile", "name": gen("Iron, Ductile"), "rgb": (78, 80, 82),
     "material_class": "Metal", "category": "Piping"},
    {"key": "stainless", "name": gen("Steel, Stainless 304"), "rgb": (200, 200, 205),
     "material_class": "Metal", "category": "Piping"},
    {"key": "pvc", "name": gen("PVC, Rigid Nonmetallic"), "rgb": (110, 118, 126),
     "material_class": "Plastic", "category": "Raceway"},
    {"key": "fiberglass", "name": gen("Fiberglass Reinforced Polyester"), "rgb": (168, 158, 120),
     "material_class": "Plastic", "category": "Support Systems"},
    {"key": "porcelain", "name": gen("Porcelain, Insulator"), "rgb": (232, 226, 214),
     "material_class": "Ceramic", "category": "Electrical"},
    {"key": "concrete_precast", "name": gen("Concrete, Precast (equipment pad)"), "rgb": (188, 186, 180),
     "material_class": "Concrete", "category": "Foundations", "cut_pattern": "crosshatch"},
]


def extended_material(spec: Dict[str, Any], *, ids: IdArg = None,
                      elem_id: int = None, cut_pattern_id: int = INVALID,
                      surface_pattern_id: int = INVALID) -> TypeRecord:
    """One of OUR extended-palette materials (types.new_material)."""
    return TY.new_material(spec["name"], tuple(spec.get("rgb", (150, 150, 150))),
                           ids=ids, elem_id=elem_id,
                           material_class=spec.get("material_class", "Unassigned"),
                           category=spec.get("category", "Unassigned"),
                           transparency=float(spec.get("transparency", 0.0)),
                           cut_pattern_id=cut_pattern_id,
                           surface_pattern_id=surface_pattern_id)


# ---- structural ASSETS ----------------------------------------------------
#: THE STRUCTURAL-ASSET PARAM-ID SCHEMA -- decoded via the ROSETTA TWIN
#: (material 509467's inline named PhysicalParamSet vs its id-keyed
#: m_oStructuralPropertySetNew: identical values, so id -> quantity is
#: EXACT).  Revit's internal units: stress kg/(ft s^2) = Pa x 0.3048; unit
#: weight = N/m^3 x 3.28084/35.3147; expansion coefficient raw (1/K);
#: Poisson / factors raw.  [VERIFIED: 345 MPa steel -> 105,156,000; 200 GPa
#: -> 6.096e10; 77 kN/m^3 -> 7,153.5.]
BIP_PHY = {
    "young_x": -1140300, "young_y": -1140301, "young_z": -1140302,
    "poisson_x": -1140303, "poisson_y": -1140304, "poisson_z": -1140305,
    "shear_x": -1140306, "shear_y": -1140307, "shear_z": -1140308,
    "unit_weight": -1140309,
    "alpha_x": -1140310, "alpha_y": -1140311, "alpha_z": -1140312,
    "damping_ratio": -1140313, "concrete_compression": -1140314,
    "bending_reinforcement": -1140315, "shear_reinforcement": -1140316,
    "shear_strength_reduction": -1140317, "min_yield_stress": -1140318,
    "min_tensile_strength": -1140319, "reduction_factor": -1140320,
    "resistance_calc_strength": -1140321,
    "compression_parallel": -1140407, "compression_perpendicular": -1140408,
    "shear_parallel": -1140409, "shear_perpendicular": -1140410, "bending": -1140414,
    "material_class_int": -1150464, "behavior_int": -1140322, "lightweight_int": -1140323,
    "asset_name_str": -1150466, "subclass_str": -1150465,
    "grade_str": -1140417, "species_str": -1140416, "description_str": -1150481,
}
#: PropertySetElement.m_propertySetType [VERIFIED: 1 = structural asset
#: (17/28), 2 = thermal asset (11/28)]
PROPSET_STRUCTURAL = 1
PROPSET_THERMAL = 2
#: StructuralAssetClass codes in -1150464 [VERIFIED 3 on the metal /
#: concrete / wood sample assets; 1 = 'Basic'-shaped soil? -- we emit the
#: material class of ours: metal 1 / concrete 2 / wood 3 per the API's
#: StructuralAssetClass ordering is NOT proven; the corpus shows 3 on every
#: sampled asset regardless of class -> ours emits 3 (the observed value)]
PROPSET_ASSET_CLASS_OBSERVED = 3

PA_TO_INTERNAL = 0.3048                       # stress: Pa -> kg/(ft s^2)
NM3_TO_INTERNAL = 3.28084 / 35.3147          # unit weight: N/m^3 -> internal

#: OUR structural asset library = PUBLISHED engineering constants (facts of
#: the substance; e.g. EN 1993 / AISC steel E = 210/200 GPa, ACI 318 concrete
#: 4700 sqrt(f'c), NDS wood species values) -- the NAMES and the selection
#: are ours.  Stresses in MPa, densities in kN/m^3, alpha per K.
STRUCTURAL_ASSETS: List[Dict[str, Any]] = [
    {"key": "steel_345", "name": gen("Steel S345 (Fy 345 MPa)"), "subclass": "Ferrous",
     "E_MPa": 200_000, "nu": 0.30, "unit_weight_kNm3": 77.0, "alpha": 1.2e-5,
     "fy_MPa": 345, "fu_MPa": 470, "reduction": 1.0},
    {"key": "steel_250", "name": gen("Steel S250 (Fy 250 MPa)"), "subclass": "Ferrous",
     "E_MPa": 200_000, "nu": 0.30, "unit_weight_kNm3": 77.0, "alpha": 1.2e-5,
     "fy_MPa": 250, "fu_MPa": 400, "reduction": 1.0},
    {"key": "steel_rebar_500", "name": gen("Reinforcing Steel B500 (Fy 500 MPa)"), "subclass": "Ferrous",
     "E_MPa": 200_000, "nu": 0.30, "unit_weight_kNm3": 77.0, "alpha": 1.2e-5,
     "fy_MPa": 500, "fu_MPa": 545, "reduction": 1.0},
    {"key": "steel_light_gauge", "name": gen("Steel, Light Gauge (Fy 230 MPa)"), "subclass": "Ferrous",
     "E_MPa": 203_000, "nu": 0.30, "unit_weight_kNm3": 77.0, "alpha": 1.2e-5,
     "fy_MPa": 230, "fu_MPa": 310, "reduction": 1.0},
    {"key": "aluminum_6061", "name": gen("Aluminum 6061-T6"), "subclass": "Non Ferrous",
     "E_MPa": 69_000, "nu": 0.33, "unit_weight_kNm3": 26.5, "alpha": 2.36e-5,
     "fy_MPa": 240, "fu_MPa": 290, "reduction": 1.0},
    {"key": "copper", "name": gen("Copper, Hard Drawn"), "subclass": "Non Ferrous",
     "E_MPa": 117_000, "nu": 0.34, "unit_weight_kNm3": 87.9, "alpha": 1.7e-5,
     "fy_MPa": 210, "fu_MPa": 300, "reduction": 1.0},
    {"key": "concrete_25", "name": gen("Concrete C25/30 (f'c 25 MPa)"), "subclass": "Normal Weight",
     "E_MPa": 24_500, "nu": 0.20, "unit_weight_kNm3": 23.6, "alpha": 1.0e-5,
     "fc_MPa": 25, "concrete": True},
    {"key": "concrete_32", "name": gen("Concrete C32/40 (f'c 32 MPa)"), "subclass": "Normal Weight",
     "E_MPa": 27_800, "nu": 0.20, "unit_weight_kNm3": 24.0, "alpha": 1.0e-5,
     "fc_MPa": 32, "concrete": True},
    {"key": "concrete_lw_20", "name": gen("Concrete, Lightweight (f'c 20 MPa)"), "subclass": "Lightweight",
     "E_MPa": 17_400, "nu": 0.20, "unit_weight_kNm3": 18.0, "alpha": 0.9e-5,
     "fc_MPa": 20, "concrete": True, "lightweight": True},
    {"key": "wood_sw", "name": gen("Wood, Softwood (D.Fir-Larch No.2)"), "subclass": "Softwood",
     "E_MPa": 11_000, "nu": 0.29, "unit_weight_kNm3": 5.4, "alpha": 4.9e-6, "wood": True,
     "bending_MPa": 6.2, "comp_par_MPa": 9.3, "comp_perp_MPa": 4.3,
     "shear_par_MPa": 1.2, "shear_perp_MPa": 0.32},
    {"key": "wood_hw", "name": gen("Wood, Hardwood (Oak, structural)"), "subclass": "Hardwood",
     "E_MPa": 12_500, "nu": 0.30, "unit_weight_kNm3": 6.9, "alpha": 5.4e-6, "wood": True,
     "bending_MPa": 8.0, "comp_par_MPa": 10.0, "comp_perp_MPa": 5.5,
     "shear_par_MPa": 1.5, "shear_perp_MPa": 0.4},
    {"key": "glass", "name": gen("Glass, Annealed"), "subclass": "Basic",
     "E_MPa": 70_000, "nu": 0.22, "unit_weight_kNm3": 25.0, "alpha": 9.0e-6},
    {"key": "masonry_cmu", "name": gen("Masonry, CMU (f'm 13.8 MPa)"), "subclass": "Basic",
     "E_MPa": 12_400, "nu": 0.20, "unit_weight_kNm3": 21.0, "alpha": 8.1e-6},
    {"key": "gypsum", "name": gen("Gypsum Board"), "subclass": "Basic",
     "E_MPa": 2_500, "nu": 0.30, "unit_weight_kNm3": 7.5, "alpha": 1.66e-5},
    {"key": "grp", "name": gen("Fiberglass Reinforced Polyester (pultruded)"), "subclass": "Basic",
     "E_MPa": 24_000, "nu": 0.28, "unit_weight_kNm3": 18.6, "alpha": 1.4e-5},
    {"key": "pvc", "name": gen("PVC, Rigid"), "subclass": "Basic",
     "E_MPa": 2_900, "nu": 0.38, "unit_weight_kNm3": 13.9, "alpha": 5.4e-5},
    {"key": "porcelain", "name": gen("Porcelain, Electrical Grade"), "subclass": "Basic",
     "E_MPa": 70_000, "nu": 0.17, "unit_weight_kNm3": 23.5, "alpha": 4.0e-6},
]


def structural_asset(spec: Dict[str, Any], *, property_set_type: int = PROPSET_STRUCTURAL,
                     ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``PropertySetElement`` carrying OUR STRUCTURAL ASSET (the physical
    constants a MaterialElem's m_structuralPropertySetId points at), in the
    LEGACY shape [VERIFIED vs rst 194585 '345 MPa': the -1140300 block +
    the asset-name string -1150466 + ints -1150464 / -1140322; id ->
    quantity decoded EXACTLY through the Rosetta twin (see :data:`BIP_PHY`)].
    Values = PUBLISHED engineering constants of the substance (facts); the
    asset NAME + selection are ours; NO Autodesk asset-library GUID / source
    'Autodesk' / Inventor sustainability token (product data, dropped)."""
    eid = _alloc(ids, elem_id)
    E = float(spec["E_MPa"]) * 1e6 * PA_TO_INTERNAL
    nu = float(spec.get("nu", 0.3))
    G = E / (2.0 * (1.0 + nu))                       # isotropic G = E / 2(1+nu)
    uw = float(spec.get("unit_weight_kNm3", 24.0)) * 1000.0 * NM3_TO_INTERNAL
    alpha = float(spec.get("alpha", 1.2e-5))
    dbl: List[Tuple[float, int]] = [
        (E, BIP_PHY["young_x"]), (E, BIP_PHY["young_y"]), (E, BIP_PHY["young_z"]),
        (nu, BIP_PHY["poisson_x"]), (nu, BIP_PHY["poisson_y"]), (nu, BIP_PHY["poisson_z"]),
        (G, BIP_PHY["shear_x"]), (G, BIP_PHY["shear_y"]), (G, BIP_PHY["shear_z"]),
        (uw, BIP_PHY["unit_weight"]),
        (alpha, BIP_PHY["alpha_x"]), (alpha, BIP_PHY["alpha_y"]), (alpha, BIP_PHY["alpha_z"]),
        (float(spec.get("reduction", 1.0)), BIP_PHY["reduction_factor"]),
    ]
    if "fy_MPa" in spec:
        dbl.append((float(spec["fy_MPa"]) * 1e6 * PA_TO_INTERNAL, BIP_PHY["min_yield_stress"]))
    if "fu_MPa" in spec:
        dbl.append((float(spec["fu_MPa"]) * 1e6 * PA_TO_INTERNAL, BIP_PHY["min_tensile_strength"]))
    if spec.get("concrete"):
        dbl.append((float(spec["fc_MPa"]) * 1e6 * PA_TO_INTERNAL, BIP_PHY["concrete_compression"]))
        dbl.append((1.0, BIP_PHY["shear_strength_reduction"]))
    if spec.get("wood"):
        for key, bip in (("bending_MPa", "bending"), ("comp_par_MPa", "compression_parallel"),
                         ("comp_perp_MPa", "compression_perpendicular"),
                         ("shear_par_MPa", "shear_parallel"), ("shear_perp_MPa", "shear_perpendicular")):
            if key in spec:
                dbl.append((float(spec[key]) * 1e6 * PA_TO_INTERNAL, BIP_PHY[bip]))
    # order by the builtin id descending (the corpus order: -1140320 ... -1140300)
    dbl.sort(key=lambda t: t[1], reverse=True)
    ints = [(PROPSET_ASSET_CLASS_OBSERVED, BIP_PHY["material_class_int"]),
            (1 if spec.get("lightweight") else 0, BIP_PHY["behavior_int"])]
    strs = [(BIP_PHY["asset_name_str"], str(spec["name"])),
            (BIP_PHY["subclass_str"], str(spec.get("subclass", "")))]
    obj = blank_object("PropertySetElement")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    obj["m_oParamSet"] = _ptr("ParamSet", {
        "m_pDoubleParams": _double_param_set(dbl),
        "m_pIntParams": _int_param_set([(v, k) for v, k in ints]),
        "m_pAStringParams": _astring_param_set([(k, v) for k, v in strs]),
        "m_pBoolParams": None, "m_pElementIdParams": None,
    })
    obj["m_propertySetType"] = int(property_set_type)
    return _record("structural-asset", "PropertySetElement", -2000924, eid, obj,
                   refs={"asset": spec.get("key"), "E_MPa": spec.get("E_MPa"),
                          "unit_weight_kNm3": spec.get("unit_weight_kNm3")},
                   notes=["structural asset in the LEGACY id block (-1140300..); values = "
                          "published engineering constants; NO Autodesk asset-library GUID / "
                          "source token (product data dropped)"])



# ---- thermal ASSETS ---------------------------------------------------------
#: THE THERMAL-ASSET PARAM-ID SCHEMA -- decoded by UNIT MATCHING against
#: the eleven rst thermal assets (steel k = 45.000 W/mK, rho = 7,850 kg/m3,
#: cp = 480 J/kgK; copper 401 / 8,920 / 385; aluminum 230 / 2,700 / 897;
#: stainless 16.2 -- textbook values [VERIFIED all 11]).  Internal units:
#: conductivity = W/(m K) x 3.28084; specific heat = J/(kg K) x 10.7639;
#: density = kg/m3 x 0.0283168 (= kg/ft3); emissivity / porosity /
#: reflectivity / permeability raw; electrical resistivity = ohm m x
#: 3.531466e8.
BIP_THM = {
    "conductivity_x": -1152308, "conductivity_y": -1152309, "conductivity_z": -1152310,
    "conductivity": -1152311, "specific_heat": -1152312, "density": -1152313,
    "emissivity": -1152320, "permeability": -1152327, "porosity": -1152328,
    "reflectivity": -1152329, "electrical_resistivity": -1152330,
    "compressible_int": -1152338, "behavior_int": -1152326,
    "material_class_int": -1150464, "structural_behavior_int": -1140322,
    "schema_str": -1152342, "keywords_str": -1152341, "source_str": -1152340,
    "library_guid_str": -1152337, "description_str": -1150481,
    "asset_name_str": -1150466, "subclass_str": -1150465,
}
K_TO_INTERNAL = 3.28084                      # W/(m K) -> internal
CP_TO_INTERNAL = 10.7639104167               # J/(kg K) -> internal
RHO_TO_INTERNAL = 0.0283168466              # kg/m3 -> kg/ft3
RESISTIVITY_TO_INTERNAL = 3.5314666e8       # ohm m -> internal

#: OUR thermal asset library = PUBLISHED thermophysical constants (facts of
#: the substance: e.g. steel k 45 W/mK rho 7850 cp 490; copper 390 / 8940 /
#: 385; concrete 1.7 / 2300 / 880; softwood 0.12 / 500 / 1600; glass 1.0 /
#: 2500 / 840); emissivities are typical published surface values; the
#: NAMES and selection are ours.  ``schema`` = the asset-schema class
#: string (a FORMAT vocabulary token: 'thermal:solid'); source 'GEN'.
THERMAL_ASSETS: List[Dict[str, Any]] = [
    {"key": "steel", "name": gen("Steel, Carbon (thermal)"), "subclass": "Metal",
     "schema": "thermal:solid", "k": 45.0, "cp": 490.0, "rho": 7850.0,
     "emissivity": 0.79, "resistivity": 1.43e-7},
    {"key": "stainless", "name": gen("Steel, Stainless 304 (thermal)"), "subclass": "Metal",
     "schema": "thermal:solid", "k": 16.2, "cp": 500.0, "rho": 8000.0,
     "emissivity": 0.17, "resistivity": 7.2e-7},
    {"key": "copper", "name": gen("Copper (thermal)"), "subclass": "Metal",
     "schema": "thermal:solid", "k": 390.0, "cp": 385.0, "rho": 8940.0,
     "emissivity": 0.05, "resistivity": 1.68e-8},
    {"key": "aluminum", "name": gen("Aluminum (thermal)"), "subclass": "Metal",
     "schema": "thermal:solid", "k": 205.0, "cp": 900.0, "rho": 2700.0,
     "emissivity": 0.09, "resistivity": 2.65e-8},
    {"key": "concrete", "name": gen("Concrete, Normal Weight (thermal)"), "subclass": "Concrete",
     "schema": "thermal:solid", "k": 1.7, "cp": 880.0, "rho": 2300.0,
     "emissivity": 0.94, "resistivity": 100.0},
    {"key": "concrete_lw", "name": gen("Concrete, Lightweight (thermal)"), "subclass": "Concrete",
     "schema": "thermal:solid", "k": 0.5, "cp": 840.0, "rho": 1800.0,
     "emissivity": 0.94, "resistivity": 100.0},
    {"key": "wood_sw", "name": gen("Wood, Softwood (thermal)"), "subclass": "Wood",
     "schema": "thermal:solid", "k": 0.12, "cp": 1600.0, "rho": 500.0,
     "emissivity": 0.90, "resistivity": 1e8},
    {"key": "plywood", "name": gen("Plywood Panel (thermal)"), "subclass": "Wood",
     "schema": "panel:thermal:solid", "k": 0.13, "cp": 1500.0, "rho": 545.0,
     "emissivity": 0.90, "resistivity": 1e8},
    {"key": "glass", "name": gen("Glass, Float (thermal)"), "subclass": "Basic",
     "schema": "thermal:solid", "k": 1.0, "cp": 840.0, "rho": 2500.0,
     "emissivity": 0.92, "resistivity": 1e11},
    {"key": "gypsum", "name": gen("Gypsum Board (thermal)"), "subclass": "Basic",
     "schema": "thermal:solid", "k": 0.25, "cp": 1090.0, "rho": 800.0,
     "emissivity": 0.90, "resistivity": 1e8},
    {"key": "pvc", "name": gen("PVC (thermal)"), "subclass": "Plastic",
     "schema": "thermal:solid", "k": 0.16, "cp": 900.0, "rho": 1400.0,
     "emissivity": 0.92, "resistivity": 1e13},
    {"key": "soil", "name": gen("Soil, Compacted Fill (thermal)"), "subclass": "Basic",
     "schema": "soil:thermal:solid", "k": 0.8, "cp": 1000.0, "rho": 1600.0,
     "emissivity": 0.90, "resistivity": 100.0},
]


def thermal_asset(spec: Dict[str, Any], *, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``PropertySetElement`` carrying OUR THERMAL ASSET (m_propertySetType
    2): conductivity / specific heat / density / emissivity + the neutral
    machinery params, in the id block decoded by unit matching over all 11
    rst thermal assets (:data:`BIP_THM`).  Values = published thermophysical
    constants (facts); NO Autodesk asset-library GUID / source 'Autodesk' /
    Inventor sustainability token (product data dropped; source = ours)."""
    eid = _alloc(ids, elem_id)
    k = float(spec["k"]) * K_TO_INTERNAL
    dbl = [
        (k, BIP_THM["conductivity_x"]), (k, BIP_THM["conductivity_y"]),
        (k, BIP_THM["conductivity_z"]), (k, BIP_THM["conductivity"]),
        (float(spec["cp"]) * CP_TO_INTERNAL, BIP_THM["specific_heat"]),
        (float(spec["rho"]) * RHO_TO_INTERNAL, BIP_THM["density"]),
        (float(spec.get("emissivity", 0.9)), BIP_THM["emissivity"]),
        (float(spec.get("permeability", 0.0)), BIP_THM["permeability"]),
        (float(spec.get("porosity", 0.001)), BIP_THM["porosity"]),
        (float(spec.get("reflectivity", 0.0)), BIP_THM["reflectivity"]),
        (float(spec.get("resistivity", 1e8)) * RESISTIVITY_TO_INTERNAL, BIP_THM["electrical_resistivity"]),
    ]
    dbl.sort(key=lambda t: t[1], reverse=True)   # -1152308 first .. -1152330 last [VERIFIED corpus order]
    ints = [(0 if spec.get("subclass") in ("Wood", "Plastic") else 1, BIP_THM["compressible_int"]),
            (0, BIP_THM["behavior_int"]),
            (PROPSET_ASSET_CLASS_OBSERVED, BIP_THM["material_class_int"]),
            (0, BIP_THM["structural_behavior_int"])]
    strs = [(BIP_THM["schema_str"], str(spec.get("schema", "thermal:solid"))),
            (BIP_THM["keywords_str"], ""),
            (BIP_THM["source_str"], HOUSE_PREFIX),
            (BIP_THM["description_str"], str(spec["name"])),
            (BIP_THM["asset_name_str"], str(spec["name"])),
            (BIP_THM["subclass_str"], str(spec.get("subclass", "")))]
    obj = blank_object("PropertySetElement")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    obj["m_oParamSet"] = _ptr("ParamSet", {
        "m_pDoubleParams": _double_param_set(dbl),
        "m_pIntParams": _int_param_set([(v, k) for v, k in ints]),
        "m_pAStringParams": _astring_param_set([(k, v) for k, v in strs]),
        "m_pBoolParams": None, "m_pElementIdParams": None,
    })
    obj["m_propertySetType"] = PROPSET_THERMAL
    return _record("thermal-asset", "PropertySetElement", -2000924, eid, obj,
                   refs={"asset": spec.get("key"), "k_WmK": spec.get("k"), "rho_kgm3": spec.get("rho")},
                   notes=["thermal asset in the decoded -1152300 block (unit-matched over all 11 "
                          "rst thermal assets); values = published thermophysical constants; "
                          "source '%s', no asset-library GUID" % HOUSE_PREFIX])


def thermal_asset_role(hint: str) -> str:
    """Pick OUR thermal asset for a sample thermal-asset slot by keyword."""
    s = str(hint).lower()
    if "stainless" in s:
        return "stainless"
    if any(t in s for t in ("copper", "bronze", "brass")):
        return "copper"
    if "alum" in s:
        return "aluminum"
    if any(t in s for t in ("steel", "iron", "metal")):
        return "steel"
    if any(t in s for t in ("aerated", "lightweight")):
        return "concrete_lw"
    if any(t in s for t in ("concrete", "precast", "masonry", "cmu")):
        return "concrete"
    if any(t in s for t in ("plywood", "sheathing", "panel")):
        return "plywood"
    if any(t in s for t in ("wood", "softwood", "lumber", "fir", "pine", "oak", "timber")):
        return "wood_sw"
    if "glass" in s:
        return "glass"
    if any(t in s for t in ("gypsum", "plaster")):
        return "gypsum"
    if any(t in s for t in ("plastic", "pvc", "hdpe", "poly", "vinyl")):
        return "pvc"
    if any(t in s for t in ("soil", "earth", "landscape", "sand")):
        return "soil"
    if "roof" in s:
        return "gypsum"
    return "steel"


def structural_asset_role(schema_hint: str, asset_name: str = "") -> str:
    """Pick OUR asset for a sample structural-asset slot from its schema id /
    name keywords (the correspondence rule of the palette rung)."""
    s = f"{schema_hint} {asset_name}".lower()
    if any(t in s for t in ("copper", "c10100", "bronze", "brass")):
        return "copper"
    if any(t in s for t in ("alum", "6061")):
        return "aluminum_6061"
    if "light gauge" in s or "cold" in s:
        return "steel_light_gauge"
    if any(t in s for t in ("rebar", "grade 65", "grade 60", "reinf", "wire fabric")):
        return "steel_rebar_500"
    if any(t in s for t in ("250", "a36")):
        return "steel_250"
    if any(t in s for t in ("steel", "metal", "iron", "cast", "high strength")):
        return "steel_345"
    if any(t in s for t in ("lightweight", "light weight")):
        return "concrete_lw_20"
    if any(t in s for t in ("concrete", "cast-in-place", "precast", "aci")):
        return "concrete_25"
    if any(t in s for t in ("wood", "softwood", "lumber", "fir", "pine", "plywood", "sheathing")):
        return "wood_sw"
    if any(t in s for t in ("hardwood", "oak", "maple")):
        return "wood_hw"
    if "glass" in s or "glaz" in s:
        return "glass"
    if any(t in s for t in ("masonry", "cmu", "block", "brick")):
        return "masonry_cmu"
    if "gypsum" in s or "plaster" in s:
        return "gypsum"
    if any(t in s for t in ("soil", "earth", "landscape")):
        return "masonry_cmu"
    if any(t in s for t in ("plastic", "pvc", "hdpe", "poly")):
        return "pvc"
    if "roof" in s:
        return "gypsum"
    return "steel_345"


# ===========================================================================
# 7. VIEW FILTERS (ZB6_filters): ParameterFilterElement
# ===========================================================================
#: BuiltInCategory ids (Autodesk's fixed public enum -- interoperability
#: constants) our filters key on [ids cross-checked with the house
#: catalog table rvt.genesis.house_standard.HOUSE_CATEGORIES].
OST_ElectricalEquipment = -2001040
OST_ElectricalFixtures = -2001060
OST_LightingFixtures = -2001120
OST_LightingDevices = -2008087
OST_Conduits = -2008132
OST_ConduitFitting = -2008128
OST_CableTray = -2008130
OST_CableTrayFitting = -2008126
OST_Wire = -2008039
OST_DataDevices = -2008083
OST_CommunicationDevices = -2008077
OST_FireAlarmDevices = -2008081
OST_NurseCallDevices = -2008085
OST_SecurityDevices = -2008079
OST_TelephoneDevices = -2008075
OST_MechanicalEquipment = -2001140
OST_DuctCurves = -2008000
OST_PipeCurves = -2008044
OST_Sprinklers = -2008099
OST_Rooms = -2000160
OST_MEPSpaces = -2003600
OST_Walls = -2000011
OST_Floors = -2000032
OST_Doors = -2000023
OST_GenericModel = -2000151

#: OUR house VIEW FILTERS (electrical / MEP coordination): category-scoped
#: filters -- the name + category set are ours; rules empty (a category
#: filter needs none: Revit's own 'Interior' filter carries an empty
#: LogicalAndFilterData / a category rule) [VERIFIED both shapes on rst:
#: 116099 category-only + string rule / the Connected-Node structural set].
HOUSE_VIEW_FILTERS: List[Dict[str, Any]] = [
    {"name": gen("Electrical - Power Devices"),
     "categories": [OST_ElectricalFixtures, OST_ElectricalEquipment]},
    {"name": gen("Electrical - Lighting"),
     "categories": [OST_LightingFixtures, OST_LightingDevices]},
    {"name": gen("Electrical - Distribution Gear"),
     "categories": [OST_ElectricalEquipment]},
    {"name": gen("Electrical - Raceway (conduit + tray)"),
     "categories": [OST_Conduits, OST_ConduitFitting, OST_CableTray, OST_CableTrayFitting]},
    {"name": gen("Systems - Communications & Life Safety"),
     "categories": [OST_DataDevices, OST_CommunicationDevices, OST_FireAlarmDevices,
                    OST_NurseCallDevices, OST_SecurityDevices, OST_TelephoneDevices]},
    {"name": gen("Coordination - Mechanical & Plumbing"),
     "categories": [OST_MechanicalEquipment, OST_DuctCurves, OST_PipeCurves, OST_Sprinklers]},
    {"name": gen("Coordination - Architectural Context"),
     "categories": [OST_Walls, OST_Floors, OST_Doors, OST_Rooms]},
]


def parameter_filter(name: str, categories: Sequence[int], *, inverted: bool = False,
                     ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``ParameterFilterElement`` = a VIEW FILTER: OUR name + the built-in
    category set it applies to + an EMPTY logical-AND rule combination (a
    pure category filter).  m_proxyView -1 (not a selection-based filter).
    [VERIFIED structure vs rst 928364 / 116099; a category filter with no
    parameter rules is a shipped-file form.]"""
    eid = _alloc(ids, elem_id)
    obj = blank_object("ParameterFilterElement")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    obj["m_name"] = str(name)
    obj["m_oCategoryRule"] = _ptr("FilterCategoryRule", {
        "m_categories": [int(c) for c in categories]})
    obj["m_oRuleCombination"] = _ptr("LogicalAndFilterData", {
        "m_inverted": bool(inverted), "m_filters": []})
    obj["m_proxyView"] = INVALID
    return _record("view-filter", "ParameterFilterElement", INVALID, eid, obj,
                   refs={"categories": list(categories)},
                   notes=["category-scoped view filter; rule combination empty (our filters "
                          "select by category)"])


# ===========================================================================
# 8. EMPTY / BUILT-IN MACHINERY REPRODUCERS (ZB7_machinery)
#    SunAnnotationElem / NumberingSchema / SlaveSymbolTrackerElem
# ===========================================================================

def sun_annotation(view_id: int, *, ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``SunAnnotationElem`` = a view's sun-path annotation element.  The
    class body is EMPTY (every own field is the Element base; the sun-path
    graphic is regenerated from the view's SunAndShadowSettings) -- there is
    NOTHING of ours to reject: this constructor REPRODUCES the machinery so
    the residue bucket is honestly emptied ('landed but byte-identical').
    ``view_id`` = the owning view (m_ownerDBViewId, per slot).  [VERIFIED
    3/3 rst: body == Element base with m_ownerDBViewId set; header category
    -2009609, flags 10 / -4225.]"""
    eid = _alloc(ids, elem_id)
    obj = blank_object("SunAnnotationElem")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    obj["m_ownerDBViewId"] = int(view_id)
    return _record("sun-annotation", "SunAnnotationElem", -2009609, eid, obj,
                   refs={"view": view_id},
                   notes=["EMPTY machinery reproduced -- nothing of ours to reject"])


#: The three BUILT-IN numbering schemes every 2026 template carries
#: (rebar / fabric-sheet / rebar-coupler numbering): m_builtIn TRUE, keyed
#: to built-in categories (-2009000 rebar / -2009016 fabric sheets /
#: -2009060 couplers) and built-in NUMBER parameters -- Revit's own
#: numbering machinery, NOT authorship.  Reproduced with the observed
#: priorities; nothing of ours to reject.  [VERIFIED 3/3 identical across
#: rst / rme / rac / adv / dach.]
BUILTIN_NUMBERING_SCHEMES: List[Dict[str, Any]] = [
    {"name": "Rebar Numbering", "priority": 0, "scope_category": -2009000,
     "numbering_param": -1154616, "partition_param": -1154614},
    {"name": "Rebar Couplers Numbering", "priority": 1, "scope_category": -2009060,
     "numbering_param": -1154642, "partition_param": -1154614},
    {"name": "Fabric Sheets Numbering", "priority": 2, "scope_category": -2009016,
     "numbering_param": -1154617, "partition_param": -1154614},
]


def builtin_numbering_schema(spec: Dict[str, Any], *, ids: IdArg = None,
                             elem_id: int = None) -> TypeRecord:
    """A BUILT-IN ``NumberingSchema`` (:data:`BUILTIN_NUMBERING_SCHEMES`):
    Revit's rebar / fabric-sheet / coupler numbering machinery, m_builtIn
    TRUE, scoped to its built-in category and NUMBER parameter -- format
    machinery reproduced verbatim (nothing of ours to reject).  [VERIFIED
    field-for-field vs rst 1218729 / 1218730 / 1457391.]"""
    eid = _alloc(ids, elem_id)
    obj = blank_object("NumberingSchema")
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    obj["m_formatSettings"] = {
        "m_formattedParameters": [{
            "m_parameter": {"m_parameterId": int(spec["numbering_param"]),
                            "m_numberingParameterType": 0},
            "m_prefix": "", "m_sampleValue": "1", "m_separator": "", "m_suffix": ""}],
        "m_firstNumberFormattingOption": 0, "m_minimumNumberOfDigits": 1,
        "m_asCharacters": False, "m_uppercaseCharacters": True}
    obj["m_inInterfaceName"] = str(spec["name"])
    obj["m_matchingParams"] = []
    obj["m_outputParamBindings"] = []
    obj["m_partitioningParams"] = [{"m_parameterId": int(spec["partition_param"]),
                                   "m_numberingParameterType": 0}]
    obj["m_scopeCategories"] = [int(spec["scope_category"])]
    obj["m_useBuiltInMatchingForCategories"] = [{"first": int(spec["scope_category"]),
                                               "second": True}]
    obj["m_numberingParameterId"] = int(spec["numbering_param"])
    obj["m_priority"] = int(spec["priority"])
    obj["m_secondaryDataGUID"] = NULL_GUID
    obj["m_builtIn"] = True
    obj["m_hasRoomRelatedParameters"] = False
    obj["m_enabled"] = True
    obj["m_matchGeometry"] = False
    obj["m_usingNOBLE"] = False
    return _record("builtin-numbering-schema", "NumberingSchema", INVALID, eid, obj,
                   refs={"scope_category": spec["scope_category"], "priority": spec["priority"]},
                   notes=["BUILT-IN machinery reproduced -- nothing of ours to reject"])


def slave_symbol_tracker(master_id: int, *, ids: IdArg = None,
                         elem_id: int = None) -> TypeRecord:
    """A ``SlaveSymbolTrackerElem`` = the (empty) tracker of the shared
    'slave' symbols of a master type (here the FabricSheetType, Group A).
    Every map of its SharedSlaveSymbolTrackerCell is EMPTY = pure machinery;
    reproduced, nothing of ours to reject.  ``master_id`` (m_masterId) is
    the registration (kept per slot).  [VERIFIED vs rst 1454535: the cell
    carries archive pid 3 (first indexed sub-object).]"""
    eid = _alloc(ids, elem_id)
    obj = blank_object("SlaveSymbolTrackerElem")
    element_defaults(obj, eid, design_option=TY.INTERNAL_DESIGN_OPTION)   # -4: document machinery
    cell = blank_object("SharedSlaveSymbolTrackerCell")
    cell.update({"m_deferredDeletedSlaves": [], "m_instanceToSlaveMap": [],
                 "m_newSlaves": [], "m_slaveToInstancesMap": [], "m_newInstances": []})
    obj["m_cellList"] = _ptr("CellList", {"m_cells": [
        _ptr("SharedSlaveSymbolTrackerCell", cell, pid=3)]})
    obj["m_masterId"] = int(master_id)
    return _record("slave-symbol-tracker", "SlaveSymbolTrackerElem", INVALID, eid, obj,
                   refs={"master": master_id},
                   notes=["EMPTY tracker machinery reproduced -- nothing of ours to reject"])


# ---- our second print setups + the per-user worksharing display ----------
#: OUR sheet-size print setups (a document carries the 'Default' setup Y5
#: landed + these).  Paper dims in 0.1 mm; the paper index / source values
#: are the Windows print-dialog machinery ('<default tray>', DMPAPER
#: indices [8 = A3, 3 = Tabloid, 25 = ANSI D per the public DEVMODE enum]).
HOUSE_PRINT_SETUPS: List[Dict[str, Any]] = [
    {"name": gen("A3 Landscape - Full Size"), "paper": "A3", "index": 8,
     "dims": (2970, 4200), "orientation": 1, "zoom": 100},
    {"name": gen("ANSI D Landscape - Full Size"), "paper": "ANSI D (22x34in)", "index": 25,
     "dims": (5588, 8636), "orientation": 1, "zoom": 100},
    {"name": gen("A4 Portrait - Check Print 50%"), "paper": "A4", "index": 9,
     "dims": (2100, 2970), "orientation": 0, "zoom": 50},
]


def house_print_settings(spec: Dict[str, Any], *, ids: IdArg = None,
                         elem_id: int = None) -> TypeRecord:
    """One of OUR print setups (settings.print_settings): name / paper /
    orientation / zoom / dpi / our print-filter conventions.  Retires the
    sample's printer-specific setups (their names leak an Autodesk printer,
    'SYDPRN008')."""
    return ST.print_settings(str(spec["name"]), ids=ids, elem_id=elem_id,
                             paper_size=str(spec["paper"]),
                             paper_size_index=int(spec["index"]),
                             paper_dims_tenths_mm=tuple(spec["dims"]),
                             orientation=int(spec["orientation"]),
                             zoom_pct=int(spec["zoom"]))


def per_user_worksharing_settings(user: str, project_settings_id: int, *,
                                  ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """The per-user ``WorksharingViewModeSettings`` copy (m_projectSettings
    FALSE, m_user = OUR username): its ``regen_only`` edge points at the
    project-level element (the Y5-landed slot).  Retires the sample's
    per-user copy, which leaks an Autodesk username ('liqi')."""
    return ST.worksharing_view_mode_settings(ids=ids, elem_id=elem_id,
                                             project_settings=False, user=str(user),
                                             regen_only=[project_settings_id]
                                             if project_settings_id not in (None, INVALID) else [])


# ---- the drafting view's companions ---------------------------------------
def drafting_viewer(view_id: int, *, ids: IdArg = None, elem_id: int = None):
    """The ``Viewer`` of a drafting view (skeleton.new_viewer): an
    UNCROPPED 2D frame -- our genesis views are uncropped by convention;
    the wiring (m_dbViewId) is the slot's view.  Returns a SkelElement."""
    return sk.new_viewer(_alloc(ids, elem_id), int(view_id), crop_on=False, with_gstep=False)


def drafting_viewport(view_id: int, drawing_id: int, viewport_type_id: int, *,
                      label_origin_z: float = 0.0, ids: IdArg = None,
                      elem_id: int = None):
    """A ``Viewport`` of a view constellation (skeleton.new_viewport): pure
    machinery + wiring (view / drawing / title type) kept per slot."""
    return sk.new_viewport(_alloc(ids, elem_id), int(view_id), int(drawing_id),
                           viewport_type_id=int(viewport_type_id),
                           label_origin_z=float(label_origin_z))


# ===========================================================================
# 9. PLACEABLE DATUM / CONTENT (ZB8_content): RefPlane / SketchPlane / RoomElem
# ===========================================================================
#: BuiltInCategory of reference planes [VERIFIED header m_categroryId
#: -2000530 (OST_CLines) on all 21 rst RefPlanes]
OST_CLines = -2000530
#: BuiltInParameter of a datum's associated-view label param
#: [VERIFIED -1012201 in every RefPlane's ElementId param set, value -1]
BIP_DATUM_ELEM = -1012201

#: OUR reference-plane STANDARD for an electrical / equipment room: named
#: layout planes at the room origin (the setout lines a contractor
#: dimensions from).  Directions are unit vectors in plan; the plane is
#: VERTICAL (its normal lies in plan) and drawn ``length`` long, from the
#: room's floor (0) to ``height`` [our convention: 3.0 m = 9.84 ft draw
#: height, matching the corpus refplanes' vertical extent band].
HOUSE_REFERENCE_PLANES: List[Dict[str, Any]] = [
    {"name": gen("Setout - Origin North-South"), "origin_mm": (0.0, 0.0),
     "direction": (0.0, 1.0), "length_mm": 12000.0},
    {"name": gen("Setout - Origin East-West"), "origin_mm": (0.0, 0.0),
     "direction": (1.0, 0.0), "length_mm": 12000.0},
    {"name": gen("Gear Line - Switchboard Front"), "origin_mm": (0.0, 1500.0),
     "direction": (1.0, 0.0), "length_mm": 9000.0},
    {"name": gen("Gear Line - Panel Row A"), "origin_mm": (0.0, 4200.0),
     "direction": (1.0, 0.0), "length_mm": 9000.0},
    {"name": gen("Gear Line - Panel Row B"), "origin_mm": (0.0, 6000.0),
     "direction": (1.0, 0.0), "length_mm": 9000.0},
    {"name": gen("Equipment CL - Transformer T1"), "origin_mm": (3000.0, 0.0),
     "direction": (0.0, 1.0), "length_mm": 6000.0},
    {"name": gen("Equipment CL - Transformer T2"), "origin_mm": (6000.0, 0.0),
     "direction": (0.0, 1.0), "length_mm": 6000.0},
    {"name": gen("Clearance - Egress Path"), "origin_mm": (-1200.0, 0.0),
     "direction": (0.0, 1.0), "length_mm": 12000.0},
    {"name": gen("Trapeze Support Grid 1"), "origin_mm": (0.0, 2000.0),
     "direction": (1.0, 0.0), "length_mm": 9000.0},
    {"name": gen("Trapeze Support Grid 2"), "origin_mm": (0.0, 3600.0),
     "direction": (1.0, 0.0), "length_mm": 9000.0},
]
REFPLANE_DRAW_HEIGHT_MM = 3000.0


def reference_plane(name: str, origin_ft: Sequence[float], direction: Sequence[float],
                    length_ft: float, *, base_z_ft: float = 0.0,
                    height_ft: float = 3000.0 / MM_PER_FT,
                    ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``RefPlane`` = a REFERENCE PLANE datum: a named VERTICAL plane
    through ``origin_ft`` running along the plan unit vector ``direction``,
    drawn ``length_ft`` long between elevations ``base_z_ft`` and
    ``base_z_ft + height_ft``.

    Layout = the DATUM-PLANE machinery a Level carries (skeleton.new_level:
    DatumPlaneGeomStep geometry, a GeomTable row, the Face + Plane twin
    with archive pointer indices 3 / 4 / 5) but with a VERTICAL plane:
    plane xVec = along the run (mirroring the corpus: the specimen's xVec
    is the plan direction reversed, yVec = +Z, so the plane's normal lies in
    plan), the envelope = the drawn extent in the plane's UV (U along the
    run, V = height), free/bubble ends 0 (project refplanes derive the drawn
    line from the envelope), m_refName 14 (the 'not a named family reference'
    enum value on all 21 rst project refplanes), no subcategory.  [VERIFIED
    field layout + header (category -2000530 CLines, flags 10 / -4225) vs
    rst 273446; the geometry values are ours.]"""
    eid = _alloc(ids, elem_id)
    o = sk.element_base(eid, cell_list=False)
    o["m_pParamValueSetElementId"] = sk.param_set_elemid([(BIP_DATUM_ELEM, -1)])
    gsteps = sk._datum_plane_geom_steps()
    # RefPlane's DatumPlaneGeomStep is the versioned/flagged variant [VERIFIED
    # rst 273446: m_version 1, m_flags 761725, prev-regen types all 0]
    step = gsteps["value"]["m_nonBRepGList"][0]["value"]
    step["m_version"] = 1
    step["m_flags"] = 761725
    gsteps["value"]["m_latestGStepTypeInPrevRegenCycle"] = [0, 0, 0, 0, 0]
    o["m_geomSteps"] = gsteps
    o["m_pGeomTable"] = _ptr("GeomTable", {
        "m_refPntMirrored": False, "m_table": [{"m_geomGeneratorId": 1}],
        "m_bigTableOwner": None, "m_materialMarkers": [], "m_faceTypeMarkers": []})
    o["m_text"] = str(name)
    dx, dy = float(direction[0]), float(direction[1])
    dl = math.hypot(dx, dy) or 1.0
    dx, dy = dx / dl, dy / dl
    ox, oy = float(origin_ft[0]), float(origin_ft[1])
    z0 = float(base_z_ft)
    L, H = float(length_ft), float(height_ft)
    # plane frame: xVec = -run direction (the corpus convention), yVec = +Z;
    # origin = the run's END point (so U spans [-L, 0] like the specimen)
    origin = (ox + dx * L, oy + dy * L, z0)
    xvec, yvec = (-dx, -dy, 0.0), (0.0, 0.0, 1.0)
    envelope = ((-L, 0.0), (0.0, H))
    o["m_pFace"] = _ptr("Face", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                    "m_flags": 524804},
        "m_pFirstLoop": None, "m_faceRegions": [], "m_pGFilling": None,
        "m_oBackgroundFilling": None, "m_renderStyleId": -1, "m_cutType": 0,
        "m_faceFlags_v9": 0,
        "m_pSurf": sk.plane(origin, xvec, yvec, envelope, pid=5)}, pid=3)
    o["m_pSurface"] = sk.plane(origin, xvec, yvec, envelope, pid=4)
    o["m_pLeader"] = None
    o["m_freeEnd"] = [0.0, 0.0, 0.0]
    o["m_bubbleEnd"] = [0.0, 0.0, 0.0]
    o["m_cutVec"] = [0.0, 0.0, 0.0]
    o["m_refPointsForNewViews"] = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    o["m_sheetTextHeight"] = 0.007874015748031494        # 2.4 mm on sheet [rst value]
    o["m_genDbViewId"] = -1
    o["m_v2Datum"] = False
    o["m_useConstVForDatumLine3dRep"] = True
    o["m_refName"] = 14                                    # 'not a family reference' [21/21]
    o["m_definesOrigin"] = False
    o["m_deletionByUserAllowed"] = True
    o["m_definesWallClosure"] = False
    o["m_parentReference"] = None
    o["m_subcategoryId"] = INVALID
    hdr = sk.element_header("RefPlane", category=OST_CLines, deletion=[eid],
                            flags=10, visible_view_flags=-4225)
    rec = TypeRecord(eid, "reference-plane", "RefPlane", class_id("RefPlane"),
                     OST_CLines, o, hdr, None,
                     refs={"origin_ft": list(origin_ft), "direction": [dx, dy],
                           "length_ft": L, "height_ft": H},
                     notes=["datum-plane machinery mirrored from the Level constructor; "
                            "vertical plane, envelope U=[-L,0] V=[0,H]"])
    return rec


def datum_sketch_plane(datum_id: int, elevation_ft: float = 0.0, *,
                       category: int = INVALID, flags: int = 2074,
                       ids: IdArg = None, elem_id: int = None) -> TypeRecord:
    """A ``SketchPlane`` bound to a DATUM (``OnDatumPlaneRef``: the work
    plane sits on level / refplane ``datum_id`` -- the slot's own datum id
    is kept in place; most of K4's residue sketch planes sit on the two
    building levels which are OURS after Y8).  Our transform: identity
    rotation at ``elevation_ft``.  [VERIFIED shape vs rst 3325: identity
    Trf, m_userId -1, flags 2074, deletion [datum, self].]"""
    eid = _alloc(ids, elem_id)
    o = sk.element_base(eid, cell_list=False)
    o["m_oPlaneRef"] = _ptr("OnDatumPlaneRef", {
        "m_geomRef": {"m_intermediateTags": [], "m_oNextRef": None,
                      "m_elemId": -1, "m_ownerDBViewId": -1,
                      "m_foreignElemIdRef": {"m_id64": -1},
                      "m_geomTag": -1, "m_subTag": -1, "m_famMemberIdx": -1,
                      "m_flags": 0, "m_isLazyRef": False},
        "m_vecInPlane": [0.0, 0.0, 0.0], "m_rotation": 0.0,
        "m_datumPlaneId": int(datum_id), "m_mirror": False})
    o["m_oTrf"] = _ptr("Trf", {"m_3x3": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                               "m_or": [0.0, 0.0, float(elevation_ft)]})
    o["m_userId"] = -1
    o["m_flipZ"] = False
    hdr = sk.element_header("SketchPlane", category=category, deletion=[int(datum_id), eid],
                            flags=flags, visible_view_flags=-32768)
    return TypeRecord(eid, "datum-sketch-plane", "SketchPlane", class_id("SketchPlane"),
                      category, o, hdr, None, refs={"datum": datum_id},
                      notes=["work plane on the slot's own datum (kept); identity frame at the "
                             "datum elevation"])


def free_sketch_plane(origin_ft: Sequence[float], normal_axis: str = "y", *,
                      flags: int = 8202, ids: IdArg = None,
                      elem_id: int = None) -> TypeRecord:
    """A FREE ``SketchPlane`` (``DummyPlaneRef``: an inline Plane, no
    datum) at ``origin_ft`` -- OUR vertical work plane through the point,
    facing ``normal_axis`` ('x' or 'y').  [VERIFIED shape vs rst 912817:
    the inline Plane carries the EMPTY envelope ((1,1),(0,0)) and the Trf
    duplicates the plane frame; flags 8202, deletion [self].]"""
    eid = _alloc(ids, elem_id)
    ox, oy, oz = (float(origin_ft[0]), float(origin_ft[1]),
                  float(origin_ft[2]) if len(origin_ft) > 2 else 0.0)
    if str(normal_axis).lower().startswith("x"):
        xvec, yvec = [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]
        trf = [[0.0, 1.0, 0.0], [0.0, 0.0, -1.0], [1.0, 0.0, 0.0]]
    else:
        xvec, yvec = [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]
        trf = [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]]
    o = sk.element_base(eid, cell_list=False)
    plane_v = sk.plane((ox, oy, oz), xvec, yvec, sk.EMPTY_ENVELOPE, pid=3)
    o["m_oPlaneRef"] = _ptr("DummyPlaneRef", {
        "m_geomRef": {"m_intermediateTags": [], "m_oNextRef": None,
                      "m_elemId": -1, "m_ownerDBViewId": -1,
                      "m_foreignElemIdRef": {"m_id64": -1},
                      "m_geomTag": -1, "m_subTag": -1, "m_famMemberIdx": -1,
                      "m_flags": 0, "m_isLazyRef": False},
        "m_pPlane": plane_v})
    o["m_oTrf"] = _ptr("Trf", {"m_3x3": trf, "m_or": [ox, oy, oz]})
    o["m_userId"] = -1
    o["m_flipZ"] = False
    hdr = sk.element_header("SketchPlane", category=INVALID, deletion=[eid],
                            flags=flags, visible_view_flags=-32768)
    return TypeRecord(eid, "free-sketch-plane", "SketchPlane", class_id("SketchPlane"),
                      INVALID, o, hdr, None, refs={"origin_ft": [ox, oy, oz], "normal": normal_axis},
                      notes=["free work plane (inline Plane) at our setout point"])


#: BuiltInParameters carrying a room's / area's identity in its AString
#: param set [VERIFIED -1006901 = number, -1006900 = name on the rst
#: RoomElem / area 1004910; API: ROOM_NUMBER / ROOM_NAME]
BIP_ROOM_NUMBER = -1006901
BIP_ROOM_NAME = -1006900


def room_identity(sample_value: dict, elem_id: int, *, number: str, name: str,
                  point_ft: Optional[Sequence[float]] = None) -> TypeRecord:
    """A ``RoomElem`` whose IDENTITY is ours: the number / name (the AString
    param set) and optionally the placement point -- built over the SLOT's
    own decoded object so its topology WIRING (level, area scheme, area-space
    element, boundary references, placement offsets) stays the file's own.
    This is the honest in-place statement for a placed room in a
    substitution ladder: the placeable CONTENT bucket's real retirement is
    DELETION (docs/writer/genesis-endgame.md) -- a genesis file authors its
    rooms through the add path -- but a room's identity strings are ours to
    set at Autodesk's registration, and this record proves the reader takes
    them.  The HVAC design fields keep their (zero) defaults."""
    obj = copy.deepcopy(sample_value or {})
    obj["m_id"] = int(elem_id)
    obj["m_pParamValueSetAString"] = _astring_param_set([(BIP_ROOM_NUMBER, str(number)),
                                                        (BIP_ROOM_NAME, str(name))])
    if point_ft is not None:
        obj["m_point"] = [float(point_ft[0]), float(point_ft[1])]
    return TypeRecord(int(elem_id), "room-identity", "RoomElem", class_id("RoomElem"),
                      -2000160, obj, TY.element_header("RoomElem", -2000160, int(elem_id)),
                      None, refs={"number": number, "name": name},
                      notes=["identity (number/name) ours; topology wiring = the slot's own; "
                             "the header is not replaced (object-only rung)"])


# ===========================================================================
# 10. IN-PLACE RUNG BUILDERS (build_ZB_<bucket>(ctx, landed) -> SubstBuild)
# ===========================================================================
# ``ctx`` is a ``tools/genesis_substitute.SubstContext`` on the PARENT
# file; ``landed`` = {slot id: rung} already landed by the Y-ladder (and by
# earlier ZB rungs) -- OUR objects sit there, so a builder targets ONLY the
# residue slots of its classes.  Each builder returns the ``SubstBuild``
# contract of the substitution engine: old_ids (the residue slots), records
# (ours, at temporary ids from ``ctx.ids``), corr (slot -> our record) and
# residue (classes deliberately left, with the reason).

def _residue_slots(ctx, class_name: str, landed: Dict[int, Any]) -> List[int]:
    return [int(e) for e in ctx.ids_of(class_name) if int(e) not in landed]


def _sym_name(ctx, eid: int) -> str:
    v = ctx.value(eid) or {}
    si = v.get("m_symbolInfo")
    if isinstance(si, dict):
        n = (si.get("value") or {}).get("m_name")
        if n:
            return str(n)
    for k in ("m_name", "m_viewName", "m_text", "m_sName"):
        x = v.get(k)
        if isinstance(x, str) and x.strip():
            return str(x)
    return ""


def _mat_name(ctx, eid: int) -> str:
    v = ctx.value(eid) or {}
    m = ((v.get("m_pMaterial") or {}).get("value") or {})
    return str(m.get("m_name") or "")


def _norm(s: str) -> str:
    s = str(s or "").strip().lower()
    return {"aluminium": "aluminum"}.get(s, s)


def _zip_by_name_then_order(slots: List[int], names_of: Callable[[int], str],
                            ours: List[Any], our_name_of: Callable[[Any], str],
                            alias: Optional[Dict[str, str]] = None) -> Dict[int, Any]:
    """Pair sample slots with our items: first by normalized NAME (with an
    optional alias map from sample designation -> our designation), then the
    remaining slots with the remaining items IN ORDER.  Returns {slot: item}."""
    alias = alias or {}
    out: Dict[int, Any] = {}
    by_our_name = {_norm(our_name_of(x)): x for x in ours}
    used: Set[int] = set()
    left_slots: List[int] = []
    for s in slots:
        nm = _norm(names_of(s))
        nm = _norm(alias.get(nm, nm))
        item = by_our_name.get(nm)
        if item is not None and id(item) not in used:
            out[s] = item
            used.add(id(item))
        else:
            left_slots.append(s)
    remaining = [x for x in ours if id(x) not in used]
    for s, item in zip(left_slots, remaining):
        out[s] = item
    return out


def _new_ids(ctx):
    """The rung's temporary-id allocator (a band above the parent's
    watermark; the substitution context provides it)."""
    return ctx.ids


# ---- ZB1: the parameter-definitions layer ----------------------------------
#: OUR 8 project parameters (identity / documentation data our practice
#: carries on the project) -- captions + kinds + groups
HOUSE_PROJECT_PARAMETERS: List[Tuple[str, str, str]] = [
    (gen("Design Package"), "ParamDefString", GROUP_IDENTITY),
    (gen("Issue Purpose"), "ParamDefString", GROUP_IDENTITY),
    (gen("Client Reference"), "ParamDefString", GROUP_IDENTITY),
    (gen("Site Zone"), "ParamDefString", GROUP_IDENTITY),
    (gen("Model Author Initials"), "ParamDefString", GROUP_IDENTITY),
    (gen("QA Checked"), "ParamDefYesNo", GROUP_CONSTRUCTION),
    (gen("Issued for Construction"), "ParamDefYesNo", GROUP_CONSTRUCTION),
    (gen("Sheet Discipline Code"), "ParamDefString", GROUP_IDENTITY),
]


def build_ZB1_defs(ctx, landed: Dict[int, Any]):
    """OLD = every residue parameter DEFINITION (ParamElemExternal shared
    params, ParamElemProject project params, the load-classification
    companion params) and their ParamBinding rows.  NEW = OUR definitions at
    the sample's REGISTRATIONS: each shared-parameter slot receives one of
    our house shared parameters of the SAME storage kind at the slot's own
    GUID (the ExternalParamTracking key -- Global/Latest byte-identical),
    each project-parameter slot one of our project parameters at its
    typeId token, each load-classification slot our role caption; the
    bindings are pure machinery reproduced (param -> category
    registrations of the slots our params now occupy).  No value carrier
    exists for any of the 791 definitions in the family-free lineage
    [MEASURED 0 carriers], so the swap is content-only."""
    _gs = _genesis_substitute()
    ids = _new_ids(ctx)
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    residue: Dict[str, str] = {}
    # ---- shared parameters, per storage kind --------------------------------
    ext = _residue_slots(ctx, "ParamElemExternal", landed)
    by_kind: Dict[str, List[int]] = collections.defaultdict(list)
    for e in ext:
        v = ctx.value(e) or {}
        by_kind[str((v.get("m_pParamDef") or {}).get("ptr_class") or "ParamDefValue")].append(e)
    n_ext = 0
    for kind, slots in sorted(by_kind.items()):
        caps = our_shared_parameter_captions(kind, len(slots))
        for slot, (cap, spec, group) in zip(sorted(slots), caps):
            v = ctx.value(slot) or {}
            guid = ((v.get("m_externalParamKey") or {}).get("m_guidValue")) or NULL_GUID
            slot_pd = (v.get("m_pParamDef") or {}).get("value") or {}
            # keep the slot's spec for measurable kinds when ours has none
            if kind in _VALUE_DEF_CLASSES and spec is None:
                spec = (slot_pd.get("m_specTypeId") or {}).get("m_typeId") or SPEC_NUMBER
            rec = shared_parameter(cap, guid, kind=kind, spec=spec, group=group,
                                   description=f"{HOUSE_PREFIX} house shared parameter ({kind[8:]})",
                                   user_visible=bool(slot_pd.get("m_userVisible", True)),
                                   hide_when_no_value=bool(v.get("m_hideWhenNoValue", False)),
                                   binding_ids=[int(b) for b in (v.get("m_bindingIds") or [])],
                                   ids=ids)
            records.append(rec)
            corr[slot] = int(rec.elem_id)
            n_ext += 1
    notes.append(f"shared parameters: {n_ext} slots by kind "
                 f"{ {k: len(s) for k, s in by_kind.items()} } <- OUR house library "
                 "(same kind, slot GUID kept = the registry key)")
    # ---- project parameters -------------------------------------------------
    proj = sorted(_residue_slots(ctx, "ParamElemProject", landed))
    for i, slot in enumerate(proj):
        v = ctx.value(slot) or {}
        pd = (v.get("m_pParamDef") or {}).get("value") or {}
        tok = (pd.get("m_typeId") or {}).get("m_typeId") or ""
        cap, kind, group = HOUSE_PROJECT_PARAMETERS[i % len(HOUSE_PROJECT_PARAMETERS)]
        if i >= len(HOUSE_PROJECT_PARAMETERS):
            cap = f"{cap} - {i // len(HOUSE_PROJECT_PARAMETERS) + 1}"
        rec = project_parameter(cap, tok, kind=kind, group=group,
                                description=f"{HOUSE_PREFIX} house project parameter",
                                user_visible=bool(pd.get("m_userVisible", True)),
                                binding_ids=[int(b) for b in (v.get("m_bindingIds") or [])],
                                flags=int(v.get("m_nFlags", 0) or 0), ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"project parameters: {len(proj)} slots <- ours (slot typeId token kept)")
    # ---- load-classification companion parameters ---------------------------
    lcp = sorted(_residue_slots(ctx, "ParamElemElectricalLoadClassification", landed))
    for slot in lcp:
        v = ctx.value(slot) or {}
        pd = (v.get("m_pParamDef") or {}).get("value") or {}
        tok = (pd.get("m_typeId") or {}).get("m_typeId") or ""
        cls_id = int(v.get("m_idLoadClassification", INVALID) or INVALID)
        cls_name = _sym_name(ctx, cls_id) if cls_id > 0 else "Load"
        # strip a house prefix Group A may already have applied
        cls_name = cls_name[len(HOUSE_PREFIX) + 1:] if cls_name.startswith(HOUSE_PREFIX + " ") else cls_name
        rec = load_classification_parameter(cls_id, int(v.get("m_eType", 0) or 0),
                                            cls_name or "Load", tok, ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"load-classification parameters: {len(lcp)} slots <- our 6 role phrasings "
                 f"(classification name from the current file; ids/typeIds kept)")
    # ---- bindings: pure machinery reproduced ---------------------------------
    binds = sorted(_residue_slots(ctx, "ParamBinding", landed))
    for slot in binds:
        v = ctx.value(slot) or {}
        rec = param_binding(int(v.get("m_paramId", INVALID) or INVALID),
                            int(v.get("m_categoryId", INVALID) or INVALID),
                            int(v.get("m_elemOrSymbol", 1) or 1), ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"parameter bindings: {len(binds)} reproduced (pure machinery: expect "
                 f"byte-identical landed slots)")
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr,
                          notes=notes, residue=residue,
                          info={"shared_by_kind": {k: len(s) for k, s in by_kind.items()},
                                "project": len(proj), "load_class_params": len(lcp),
                                "bindings": len(binds)})


# ---- ZB2: the MEP catalog ---------------------------------------------------
def build_ZB2_mepcat(ctx, landed: Dict[int, Any]):
    """OLD = the wire + piping catalog residue.  NEW = ours: 4 conductor
    materials, 26 insulation designations, 3 temperature ratings, our 13
    pipe schedules, 8 joining methods, 5 pipe materials (with published
    roughness) and 15 pipe segments carrying our ASME/ASTM/AWWA dimension
    rows -- each landed on its role correspondent (name match, else
    order).  The catalog's cross-wiring (segment -> material / schedule,
    the Y4 wire/pipe size tables keyed on these symbol ids) holds by
    construction: every id is preserved in place."""
    _gs = _genesis_substitute()
    ids = _new_ids(ctx)
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    residue: Dict[str, str] = {}
    name = lambda e: _sym_name(ctx, e)

    def land(pairs: Dict[int, Any], make: Callable[[Any, int], Any]) -> int:
        n = 0
        for slot, item in sorted(pairs.items()):
            rec = make(item, slot)
            records.append(rec)
            corr[slot] = int(rec.elem_id)
            n += 1
        return n
    # wire materials / temperature ratings / insulations
    wm = _residue_slots(ctx, "RbsWireMaterialType", landed)
    n = land(_zip_by_name_then_order(wm, name, WIRE_MATERIALS, str,
                                     alias={"aluminium": "aluminum", "steel": "steel (bond/messenger)",
                                            "non-magnetic": "copper-clad aluminum"}),
             lambda nm, slot: wire_material_type(nm, ids=ids))
    wt = _residue_slots(ctx, "RbsWireTemperatureRatingType", landed)
    n += land(_zip_by_name_then_order(wt, name, WIRE_TEMPERATURE_RATINGS, str),
              lambda nm, slot: wire_temperature_rating_type(nm, ids=ids))
    wi = _residue_slots(ctx, "RbsWireInsulationType", landed)
    n += land(_zip_by_name_then_order(wi, name, WIRE_INSULATIONS, str),
              lambda nm, slot: wire_insulation_type(nm, ids=ids))
    notes.append(f"wire catalog: {len(wm)} materials + {len(wt)} ratings + {len(wi)} insulations "
                 f"<- ours (industry designations; objects ours)")
    # pipe schedules / connections / materials
    ps = _residue_slots(ctx, "RbsPipeScheduleType", landed)
    n += land(_zip_by_name_then_order(ps, name, PIPE_SCHEDULES, str,
                                      alias={"k": "type k", "l": "type l", "m": "type m",
                                             "5s": "schedule 5s", "10s": "schedule 10s",
                                             "a": "type k", "b": "type l", "c": "type m", "d": "sdr 26",
                                             "22": "class 350 (awwa c151)", "30": "class 250 (awwa c151)"}),
              lambda nm, slot: pipe_schedule_type(nm, ids=ids))
    pc = _residue_slots(ctx, "RbsPipeConnectionType", landed)
    n += land(_zip_by_name_then_order(pc, name, PIPE_CONNECTIONS, str,
                                      alias={"welded": "butt welded", "socket-type": "press-fit",
                                             "mechanical joint": "grooved",
                                             "bell and spigot": "bell and spigot (push-on)"}),
              lambda nm, slot: pipe_connection_type(nm, ids=ids))
    pm = _residue_slots(ctx, "RbsPipeMaterialType", landed)
    n += land(_zip_by_name_then_order(pm, name, PIPE_MATERIALS, lambda x: x["name"],
                                      alias={"carbon steel": "carbon steel", "stainless steel": "stainless steel",
                                             "copper": "copper (drawn tube)", "plastic": "pvc (plastic)",
                                             "ductile iron": "ductile iron"}),
              lambda spec, slot: pipe_material_type(spec["name"], spec["roughness_mm"], ids=ids))
    notes.append(f"piping catalog: {len(ps)} schedules + {len(pc)} joining methods + {len(pm)} "
                 f"materials <- ours (published roughness)")
    # pipe segments: our dimension rows per the slot's (schedule, material) names
    seg = sorted(_residue_slots(ctx, "PipeSegment", landed))
    rough_by_role = {m["key"]: m["roughness_mm"] for m in PIPE_MATERIALS}
    for slot in seg:
        v = ctx.value(slot) or {}
        sched_id = int(v.get("m_scheduleTypeId", INVALID) or INVALID)
        mat_id = int(v.get("m_materialId", INVALID) or INVALID)
        sched_nm = _sym_name(ctx, sched_id) if sched_id > 0 else ""
        mat_nm = _mat_name(ctx, mat_id) or str(v.get("m_name") or "")
        table = _table_for_schedule(sched_nm, mat_nm)
        rows = pipe_size_rows(table)
        mkey = ("ductile" if "ductile" in mat_nm.lower() or "iron" in mat_nm.lower()
                else "copper" if "copper" in mat_nm.lower()
                else "stainless" if "stainless" in mat_nm.lower()
                else "pvc" if any(t in mat_nm.lower() for t in ("plastic", "pvc"))
                else "steel")
        rough = rough_by_role[mkey]
        our_mat_word = {"steel": "Steel", "stainless": "Stainless", "copper": "Copper",
                        "pvc": "PVC", "ductile": "Ductile Iron"}[mkey]
        std_word = {"b36.10-sch40": "ASME B36.10 Sch 40", "b36.10-sch80": "ASME B36.10 Sch 80",
                    "b36.19-10s": "ASME B36.19 Sch 10S", "b36.19-5s": "ASME B36.19 Sch 5S",
                    "b88-k": "ASTM B88 Type K", "b88-l": "ASTM B88 Type L", "b88-m": "ASTM B88 Type M",
                    "pvc-sch40": "ASTM D1785 Sch 40", "pvc-sch80": "ASTM D1785 Sch 80",
                    "awwa-c151-cl350": "AWWA C151 Class 350"}[table]
        rec = pipe_segment(gen(f"{our_mat_word} Pipe - {std_word}"), mat_id, sched_id, rows,
                           rough, ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
        n += 1
    notes.append(f"pipe segments: {len(seg)} <- our ASME/ASTM/AWWA size rows (table chosen by "
                 f"the slot's schedule/material designation; material/schedule wiring kept)")
    for cls_name in ("RbsPipingSystemType", "RbsFluidType", "RbsPipeType", "RbsFlexPipeType"):
        k = len(ctx.ids_of(cls_name))
        if k:
            residue[cls_name] = f"{k} kept -- Group A / a later catalog rung"
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr,
                          notes=notes, residue=residue, info={"records": n})


# ---- ZB3: the family-scoped pen tables -------------------------------------
def build_ZB3_pens(ctx, landed: Dict[int, Any]):
    """OLD = the curtain-SYSTEM-family-scoped PenWidthTableElems (m_famId
    != -1; the project table is ours since Y1).  NEW = OUR ISO-128 pen
    series per family scope (the family id is the slot's registration and
    is kept)."""
    _gs = _genesis_substitute()
    ids = _new_ids(ctx)
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    fams = []
    for slot in sorted(_residue_slots(ctx, "PenWidthTableElem", landed)):
        v = ctx.value(slot) or {}
        fam = int(v.get("m_famId", INVALID) or INVALID)
        if fam == INVALID:
            continue                                # the project table (ours already)
        rec = family_pen_width_table(fam, ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
        fams.append((slot, fam, _sym_name(ctx, fam)))
    notes.append(f"family-scoped pen tables: {len(fams)} <- our ISO-128 series; family scopes "
                 f"kept: {[(f, nm) for _s, f, nm in fams]}")
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr, notes=notes,
                          info={"family_scopes": fams})


# ---- ZB4: annotation attribute types ---------------------------------------
def build_ZB4_annot(ctx, landed: Dict[int, Any]):
    """OLD = the residue SectionAttributes (section mark types) and the
    ViewportAttributes viewport-title type.  NEW = ours: our section
    head/tail types (our tail dimensions) and our viewport-title type,
    each keeping the slot's companion wiring (its own FontElem / line
    sub-category / family scope) -- the companions are Group-A classes."""
    _gs = _genesis_substitute()
    ids = _new_ids(ctx)
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    sec = sorted(_residue_slots(ctx, "SectionAttributes", landed))
    proj_names = list(SECTION_TYPE_NAMES)
    fam_count = 0
    for i, slot in enumerate(sec):
        v = ctx.value(slot) or {}
        lta = v.get("m_lineAndTextAttr") or {}
        fam = int(v.get("m_famId", INVALID) or INVALID)
        if fam != INVALID:
            fam_count += 1
            nm = gen(f"Section Mark (curtain family {_sym_name(ctx, fam) or fam})")
        else:
            nm = gen(proj_names[i % len(proj_names)])
        rec = section_attributes(nm, font_id=int(lta.get("m_fontId", INVALID) or INVALID),
                                 category_id=int(lta.get("m_categoryId", INVALID) or INVALID),
                                 bold=bool(lta.get("m_bBold", False)),
                                 head_family_tag_id=int(v.get("m_sectionHeadFamilyTagId", INVALID) or INVALID),
                                 tail_family_tag_id=int(v.get("m_sectionTailFamilyTagId", INVALID) or INVALID),
                                 ids=ids)
        if fam != INVALID:
            rec.obj["m_famId"] = fam                 # family-scoped type: keep the scope
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"section mark types: {len(sec)} <- ours (tail {SECTION_TAIL_LENGTH_MM} x "
                 f"{SECTION_TAIL_WIDTH_MM} mm); {fam_count} family-scoped (curtain families) keep "
                 f"m_famId; font/category companions kept per slot")
    vp = sorted(_residue_slots(ctx, "ViewportAttributes", landed))
    for i, slot in enumerate(vp):
        v = ctx.value(slot) or {}
        rec = viewport_attributes(gen("Viewport Title with Line" if i == 0 else f"Viewport Title {i + 1}"),
                                  category_id=int(v.get("m_categoryId", INVALID) or INVALID),
                                  show_label=int(v.get("m_showLabel", 1) or 1),
                                  show_extension_line=bool(v.get("m_showExtensionLine", True)),
                                  ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"viewport title types: {len(vp)} <- ours (line sub-category kept)")
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr, notes=notes,
                          info={"section_types": len(sec), "viewport_types": len(vp)})


# ---- ZB5: palette companions ------------------------------------------------
def build_ZB5_palette(ctx, landed: Dict[int, Any]):
    """OLD = the sample's SURPLUS materials (the palette slots Y7 did not
    fill) + the PropertySetElement asset companions.  NEW = our EXTENDED
    material palette (10 more MEP materials, by material-class role) + our
    STRUCTURAL assets (published constants) on the structural-asset slots
    (m_propertySetType 1).  The THERMAL assets (type 2, 11 slots) are LEFT
    as residue -- their param-id semantics are not decoded (a documented
    constructor gap; the endgame retires them with their materials)."""
    _gs = _genesis_substitute()
    ids = _new_ids(ctx)
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    residue: Dict[str, str] = {}
    # ---- surplus materials <- our extended palette (role by class keyword) --
    mats = sorted(_residue_slots(ctx, "MaterialElem", landed))
    pool = list(EXTENDED_MATERIALS)
    role_key = {"copper": "copper", "alum": "aluminum", "stainless": "stainless",
                "galv": "steel_galv", "light gauge": "steel_galv", "steel": "steel_enamel",
                "metal": "steel_enamel", "iron": "iron_ductile", "concrete": "concrete_precast",
                "porcelain": "porcelain", "pvc": "pvc", "plastic": "pvc", "fiberglass": "fiberglass",
                "wood": "fiberglass", "lumber": "fiberglass"}
    used: Set[str] = set()
    unfilled: List[int] = []
    for slot in mats:
        nm = _mat_name(ctx, slot).lower()
        key = next((k for token, k in role_key.items() if token in nm and k not in used), None)
        spec = next((s for s in pool if s["key"] == key), None) if key else None
        if spec is None:
            unfilled.append(slot)
            continue
        used.add(spec["key"])
        rec = extended_material(spec, ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    leftover = [s for s in pool if s["key"] not in used]
    for slot, spec in zip(unfilled, leftover):
        rec = extended_material(spec, ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    if len(unfilled) > len(leftover):
        residue["MaterialElem"] = (f"{len(unfilled) - len(leftover)} surplus material(s) beyond our "
                                   f"extended palette -- left")
    notes.append(f"surplus materials: {len(mats)} slots <- our extended palette "
                 f"({len(EXTENDED_MATERIALS)} materials, matched by class role first)")
    # ---- property sets: structural assets <- ours; thermal = documented gap --
    props = sorted(_residue_slots(ctx, "PropertySetElement", landed))
    n_struct = n_thermal = 0
    for slot in props:
        v = ctx.value(slot) or {}
        pst = int(v.get("m_propertySetType", 0) or 0)
        # schema hint from the AString params (asset name / schema id) + the
        # referring material's name
        ps = ((v.get("m_oParamSet") or {}).get("value") or {})
        strs = {p.get("m_paramId"): p.get("m_value") for p in
                ((((ps.get("m_pAStringParams") or {}).get("value") or {}).get("m_paramSet")) or [])}
        hint = " ".join(str(strs.get(k) or "") for k in (-1152342, -1150466, -1150481, -1150465))
        for r in ctx.inbound(slot):
            if ctx.cls_of.get(r) == "MaterialElem":
                hint += " " + _mat_name(ctx, r)
        if pst == PROPSET_THERMAL:
            role = thermal_asset_role(hint)
            spec = next(s for s in THERMAL_ASSETS if s["key"] == role)
            rec = thermal_asset(spec, ids=ids)
            n_thermal += 1
        else:
            role = structural_asset_role(hint, "")
            spec = next(s for s in STRUCTURAL_ASSETS if s["key"] == role)
            rec = structural_asset(spec, property_set_type=pst, ids=ids)
            n_struct += 1
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"property sets: {n_struct} STRUCTURAL assets + {n_thermal} THERMAL assets <- ours "
                 f"(published engineering / thermophysical constants; the two decoded id blocks)")
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr, notes=notes,
                          residue=residue, info={"materials": len(mats),
                                                 "structural_assets": n_struct,
                                                 "thermal_left": n_thermal})


# ---- ZB6: view filters --------------------------------------------------------
def build_ZB6_filters(ctx, landed: Dict[int, Any]):
    """OLD = the sample's view filters.  NEW = OUR house electrical / MEP
    coordination filters (category-scoped), one per slot (name role,
    else order).  Nothing references a filter here (no view applies one),
    so the swap is content-only."""
    _gs = _genesis_substitute()
    ids = _new_ids(ctx)
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    slots = sorted(_residue_slots(ctx, "ParameterFilterElement", landed))
    pool = list(HOUSE_VIEW_FILTERS)
    for i, slot in enumerate(slots):
        spec = pool[i % len(pool)]
        nm = spec["name"] if i < len(pool) else f"{spec['name']} - {i // len(pool) + 1}"
        rec = parameter_filter(nm, spec["categories"], ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"view filters: {len(slots)} <- our {len(pool)} house filters (category-scoped)")
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr, notes=notes)


# ---- ZB7: machinery + surplus singletons + the drafting companions --------
def build_ZB7_machinery(ctx, landed: Dict[int, Any]):
    """OLD = SunAnnotationElem 3 / NumberingSchema 3 / SlaveSymbolTracker 1
    (EMPTY / BUILT-IN machinery: reproduced -> 'landed but byte-identical'
    = NOTHING OF OURS TO REJECT, the bucket is honestly emptied) + the
    surplus per-user WorksharingViewModeSettings (retires the leaked username
    'liqi' -> ours) + the surplus PrintSettings (retires 'SYDPRN008' ->
    our A3 / ANSI-D setups) + the drafting view's Viewer / Viewport companions
    (skeleton constructors wired to the same view / drawing / title type)."""
    _gs = _genesis_substitute()
    ids = _new_ids(ctx)
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    residue: Dict[str, str] = {}
    # sun annotations (empty machinery)
    suns = sorted(_residue_slots(ctx, "SunAnnotationElem", landed))
    for slot in suns:
        v = ctx.value(slot) or {}
        rec = sun_annotation(int(v.get("m_ownerDBViewId", INVALID) or INVALID), ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    # numbering schemes (built-in machinery): match by interface name
    nums = _residue_slots(ctx, "NumberingSchema", landed)
    by_name = {str((ctx.value(e) or {}).get("m_inInterfaceName") or "").strip().lower(): e for e in nums}
    for spec in BUILTIN_NUMBERING_SCHEMES:
        slot = by_name.get(spec["name"].lower())
        if slot is None:
            continue
        rec = builtin_numbering_schema(spec, ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    if len(corr) < len(suns) + len(nums):
        for e in nums:
            if e not in corr:
                residue.setdefault("NumberingSchema", "an unrecognised numbering schema left")
    # slave symbol trackers (empty machinery)
    trk = sorted(_residue_slots(ctx, "SlaveSymbolTrackerElem", landed))
    for slot in trk:
        v = ctx.value(slot) or {}
        rec = slave_symbol_tracker(int(v.get("m_masterId", INVALID) or INVALID), ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"empty/built-in machinery reproduced: {len(suns)} sun annotations, "
                 f"{sum(1 for s in nums if s in corr)} numbering schemas, {len(trk)} slave trackers "
                 f"(expect byte-identical landed slots = nothing of ours to reject)")
    # the surplus per-user worksharing display copy -> ours (username leak retired)
    ws_res = sorted(_residue_slots(ctx, "WorksharingViewModeSettings", landed))
    ws_project = next((e for e in ctx.ids_of("WorksharingViewModeSettings") if e in landed), INVALID)
    for slot in ws_res:
        rec = per_user_worksharing_settings("rvt-writer", ws_project, ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    if ws_res:
        notes.append(f"per-user worksharing display: {len(ws_res)} <- ours (user 'rvt-writer'; "
                     f"the sample copy leaked username 'liqi')")
    # surplus print setups -> our sheet-size setups (printer name leak retired)
    prints = sorted(_residue_slots(ctx, "PrintSettings", landed))
    for i, slot in enumerate(prints):
        rec = house_print_settings(HOUSE_PRINT_SETUPS[i % len(HOUSE_PRINT_SETUPS)], ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    if prints:
        notes.append(f"print setups: {len(prints)} <- ours (the sample's names leaked printer 'SYDPRN008')")
    # the drafting view's viewer + viewports (companions of the residue drafting view)
    viewers = sorted(_residue_slots(ctx, "Viewer", landed))
    for slot in viewers:
        v = ctx.value(slot) or {}
        rec = drafting_viewer(int(v.get("m_dbViewId", INVALID) or INVALID), ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    vps = sorted(_residue_slots(ctx, "Viewport", landed))
    for slot in vps:
        v = ctx.value(slot) or {}
        lo = v.get("m_labelOrigin") or [0.0, 0.0, 0.0]
        rec = drafting_viewport(int(v.get("m_dbViewId", INVALID) or INVALID),
                                int(v.get("m_dbDrawingId", INVALID) or INVALID),
                                int(v.get("m_attrId", INVALID) or INVALID),
                                label_origin_z=float(lo[2] if len(lo) > 2 else 0.0), ids=ids)
        # keep the slot's non-zero placement (label / view position) -- ours
        # only asserts the machinery shape
        for k in ("m_labelOrigin", "m_viewPosition", "m_offset", "m_labelLength",
                  "m_scale", "m_stretchFactor", "m_detailNumber"):
            if k in v and k in rec.obj:
                rec.obj[k] = copy.deepcopy(v[k])
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    if viewers or vps:
        notes.append(f"drafting view companions: {len(viewers)} viewer + {len(vps)} viewports "
                     f"<- skeleton constructors (view/drawing/title wiring kept; the drafting "
                     f"VIEW ROOT + its DBDrawing are Group-A classes)")
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr, notes=notes,
                          residue=residue)


# ---- ZB8: placeable datum / content -------------------------------------------
def build_ZB8_content(ctx, landed: Dict[int, Any]):
    """OLD = the sample's placeable datum / content residue: 21 reference
    planes, 30 orphan sketch planes, the placed room.  NEW = OUR content at
    the same registrations: our electrical-room setout reference planes
    (our named layout planes at our positions), our work planes (on the
    slot's own datum / at our setout points), the room's identity strings
    ours.  This is the CONTENT probe -- the endgame retires sample content
    by DELETION (docs/writer/genesis-endgame.md); a genesis file authors
    its own content through the add path."""
    _gs = _genesis_substitute()
    ids = _new_ids(ctx)
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    residue: Dict[str, str] = {}
    # ---- reference planes <- our setout planes -----------------------------
    rps = sorted(_residue_slots(ctx, "RefPlane", landed))
    pool: List[Dict[str, Any]] = list(HOUSE_REFERENCE_PLANES)
    k = 3
    while len(pool) < len(rps):                       # deterministic extra grid lines
        pool.append({"name": gen(f"Trapeze Support Grid {k}"),
                     "origin_mm": (0.0, 3600.0 + (k - 2) * 1600.0),
                     "direction": (1.0, 0.0), "length_mm": 9000.0})
        k += 1
    for slot, spec in zip(rps, pool):
        rec = reference_plane(spec["name"], (mm(spec["origin_mm"][0]), mm(spec["origin_mm"][1])),
                              spec["direction"], mm(spec["length_mm"]), ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"reference planes: {len(rps)} <- our setout / gear-line / support-grid planes")
    # ---- sketch planes -------------------------------------------------------
    sps = sorted(_residue_slots(ctx, "SketchPlane", landed))
    n_datum = n_free = n_view = 0
    free_pts = [(0.0, 1500.0), (0.0, 4200.0), (0.0, 6000.0), (3000.0, 0.0),
                (6000.0, 0.0), (0.0, 2000.0), (0.0, 3600.0), (-1200.0, 0.0)]
    fi = 0
    for slot in sps:
        v = ctx.value(slot) or {}
        pr = v.get("m_oPlaneRef") or {}
        pcls = pr.get("ptr_class")
        pv = pr.get("value") or {}
        owner_view = int(v.get("m_ownerDBViewId", INVALID) or INVALID)
        if pcls in ("OnDatumPlaneRef",) and owner_view == INVALID:
            datum = int(pv.get("m_datumPlaneId", INVALID) or INVALID)
            elev = 0.0
            if ctx.cls_of.get(datum) == "Level":
                surf = (((ctx.value(datum) or {}).get("m_pSurface") or {}).get("value") or {})
                org = surf.get("m_origin") or [0.0, 0.0, 0.0]
                elev = float(org[2]) if len(org) > 2 else 0.0
            rec = datum_sketch_plane(datum, elev, ids=ids)
            n_datum += 1
        elif pcls == "DummyPlaneRef" and owner_view == INVALID:
            x_mm, y_mm = free_pts[fi % len(free_pts)]
            fi += 1
            rec = free_sketch_plane((mm(x_mm), mm(y_mm), 0.0), "y" if fi % 2 else "x", ids=ids)
            n_free += 1
        elif owner_view != INVALID:
            # a view's fixed sketch plane (the residue drafting view's) --
            # rebuilt as a view-plane sketch plane wired to the same view/datum
            datum = int(pv.get("m_datumPlaneId", owner_view) or owner_view)
            se = sk.new_sketch_plane(_alloc(ids, None), owner_view, datum, 0.0)
            rec = se.as_type_record()
            n_view += 1
        else:
            residue.setdefault("SketchPlane", "an unrecognised sketch-plane form left")
            continue
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    notes.append(f"sketch planes: {n_datum} on-datum (slot datum kept) + {n_free} free (our "
                 f"setout points) + {n_view} view-owned <- ours")
    # ---- the placed room's identity ---------------------------------------------
    rooms = sorted(_residue_slots(ctx, "RoomElem", landed))
    for i, slot in enumerate(rooms):
        v = ctx.value(slot) or {}
        rec = room_identity(v, _alloc(ids, None), number=f"E-{101 + i}",
                            name=gen("Main Electrical Room" if i == 0 else f"Electrical Room {i + 1}"))
        records.append(rec)
        corr[slot] = int(rec.elem_id)
    if rooms:
        notes.append(f"rooms: {len(rooms)} identity <- ours (number/name); topology wiring kept; "
                     f"the room's companions (LevelRoomPlan / boundary CurveElems) are Group-A "
                     f"classes -- the endgame deletes the whole room constellation atomically")
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr, notes=notes,
                          residue=residue,
                          info={"refplanes": len(rps), "sketch_datum": n_datum,
                                "sketch_free": n_free, "sketch_view": n_view, "rooms": len(rooms)})


def _genesis_substitute():
    """Lazy import of ``tools/genesis_substitute`` (the SubstBuild /
    SubstContext machinery this stream reuses -- a tool, so it is imported
    on demand rather than at module load)."""
    tools = os.path.join(ROOT, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    src = os.path.join(ROOT, "src")
    if src not in sys.path:
        sys.path.insert(0, src)
    import genesis_substitute as GS                                # noqa: E402
    return GS


# ===========================================================================
# 11. THE ZB RUNG TABLE + DRIVER (the in-place ladder over Group B)
# ===========================================================================
#: The certified PARENT of every ZB rung (single probes) and of ZB1 (the
#: chain start): Y9 -- the deepest Y rung, viewer-CERTIFIED (ORCHESTRATOR
#: VERDICTS #17).  ZBk (k>=2) derive from ZB(k-1); ZB_deep = the last of the
#: chain.  Every rung's CONTROL = a byte-identical copy of Y9.
DEFAULT_PARENT = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "Y9.rvt")
Y_LADDER_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4")
ZB_OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_b")
Y_RUNGS = ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7", "Y8", "Y9"]


@dataclasses.dataclass
class ZBRung:
    name: str
    label: str
    build: Callable                    # (ctx, landed) -> SubstBuild
    parent: str = "BASE"               # 'BASE' (= the certified Y9) or a ZB rung name
    description: str = ""
    tests: str = ""
    if_pass: str = ""
    if_fail: str = ""
    seqs: Tuple[int, ...] = (102,)
    slot_fill: bool = False            # our builders build one record per residue slot


ZB_CHAIN: List[ZBRung] = [
    ZBRung("ZB1_defs", "the parameter-DEFINITIONS layer (791 shared / project / load-class "
                       "params + bindings) -> ours, IN PLACE at the sample's GUID / typeId registrations",
           build_ZB1_defs, parent="BASE",
           description="Every residue parameter definition receives OUR definition of the same "
                       "storage kind at the SAME GUID (the ExternalParamTracking registry key) / "
                       "typeId token / element id; the ParamBinding rows are pure machinery "
                       "reproduced.  0 elements carry values for these definitions in the base.",
           tests="Whether the reader accepts OUR ParamDef objects (captions / specs / groups) at "
                 "Autodesk's own shared / project / load-classification parameter registrations.",
           if_pass="Our parameter-definition constructors are reader-accepted; the layer's true "
                   "retirement (DELETION -- a genesis file carries none of the sample's shared "
                   "parameters) is a removal rung, the registry left dangling (tolerated, R5/R9).",
           if_fail="A ParamDef object of ours is rejected -- bisect by ParamDef kind (Value / "
                   "String / YesNo / ...) with single-kind in-place probes; diff a rejected slot's "
                   "ParamDef vs the sample's field by field."),
    ZBRung("ZB2_mepcat", "the MEP CATALOG (wire materials/insulations/ratings + pipe schedules/"
                         "materials/connections + pipe segments) -> our conductor & piping catalog",
           build_ZB2_mepcat, parent="ZB1_defs",
           description="The wire and piping catalog symbols become OUR objects (industry "
                       "designations, our published roughness + ASME/ASTM/AWWA dimension rows); the "
                       "Y4 size tables and the segment->material/schedule wiring hold by "
                       "construction (ids preserved).",
           tests="Whether the reader accepts our MEP catalog objects + our pipe-segment dimension data.",
           if_pass="Our MEP catalog constructors are reader-accepted.",
           if_fail="A catalog object is rejected -- bisect wire vs pipe symbols vs pipe segments."),
    ZBRung("ZB3_pens", "the 8 curtain-family-scoped pen tables -> our ISO-128 pen series (family "
                       "scope kept)", build_ZB3_pens, parent="ZB2_mepcat",
           description="Each curtain-SYSTEM family's own pen table receives our pen values, keeping "
                       "m_famId (the family = the slot's registration).",
           tests="Whether a family-SCOPED pen table of ours loads (the project one passed at Y1).",
           if_pass="Family-scoped pen tables are ours too.",
           if_fail="Our pen values are rejected in FAMILY scope while Y1 passed -> the family "
                   "scoping (m_famId) is the variable: diff vs the Y1 table."),
    ZBRung("ZB4_annot", "SectionAttributes + ViewportAttributes -> our section-mark / viewport-title "
                        "types", build_ZB4_annot, parent="ZB3_pens",
           description="Our section head/tail types (tail 10 x 2.5 mm) and our viewport-title "
                       "type, keeping each slot's own FontElem / line sub-category companions "
                       "(Group-A classes).",
           tests="Whether the reader accepts our annotation ATTRIBUTE types with the sample's companions.",
           if_pass="Annotation attribute types are constructible ours (the 'no-constructor' bucket "
                   "shrinks by these two classes).",
           if_fail="An attribute type of ours is rejected -- bisect section types vs the viewport type."),
    ZBRung("ZB5_palette", "the 10 SURPLUS materials -> our extended palette; the 28 asset "
                          "PropertySetElements -> our structural + thermal assets",
           build_ZB5_palette, parent="ZB4_annot",
           description="Our extended MEP material palette lands on the sample's surplus material "
                       "slots; our structural assets (published engineering constants, legacy id "
                       "block) and our THERMAL assets (published thermophysical constants, the id "
                       "block decoded by unit matching over all 11 rst assets) land on every "
                       "property-set slot.",
           tests="Whether the reader accepts our extra materials + our structural-asset property sets.",
           if_pass="Our extended palette + structural / thermal assets are reader-accepted; of the "
                   "palette companions only the appearance assets (Group A) remain.",
           if_fail="Bisect materials vs property sets (single-class probes); a structural-asset FAIL "
                   "names the -1140300 id block (diff vs rst 194585)."),
    ZBRung("ZB6_filters", "the 7 view filters -> our house electrical / MEP coordination filters",
           build_ZB6_filters, parent="ZB5_palette",
           description="Our category-scoped house view filters replace the sample's filters in place.",
           tests="Whether the reader accepts our ParameterFilterElement objects.",
           if_pass="View filters are constructible ours.",
           if_fail="Our filter object shape is rejected -- diff vs the sample's category-only "
                   "filter 116099."),
    ZBRung("ZB7_machinery", "empty/built-in machinery reproduced (sun annotations / numbering schemas "
                            "/ slave tracker) + surplus print & worksharing setups + the drafting view's "
                            "viewer/viewports -> ours", build_ZB7_machinery, parent="ZB6_filters",
           description="The empty and built-in machinery classes are REPRODUCED (byte-identical slots "
                       "= nothing of ours to reject); the surplus per-user worksharing display (the "
                       "'liqi' username leak) and print setups ('SYDPRN008' printer leak) become "
                       "ours; the drafting view's companions are rebuilt by the skeleton constructors.",
           tests="Whether our print / worksharing setups and the rebuilt view companions load (the "
                 "reproduced machinery cannot fail).",
           if_pass="The machinery buckets are honestly emptied; the two identity leaks are retired.",
           if_fail="Bisect print setups vs the worksharing copy vs the drafting companions."),
    ZBRung("ZB8_content", "reference planes / sketch planes / the room -> OUR content at the same "
                          "registrations", build_ZB8_content, parent="ZB7_machinery",
           description="The CONTENT probe: our setout reference planes, our work planes (on the "
                       "slot's own datum or at our setout points), our room identity.  The endgame "
                       "retires sample content by DELETION; this rung proves our datum-content "
                       "constructors load at Autodesk's registrations.",
           tests="Whether the reader accepts our reference-plane / sketch-plane geometry objects and "
                 "the room's identity strings.",
           if_pass="Our datum-content constructors load; the content bucket is retired as an "
                   "engineering question (deletion or ours, both certified paths).",
           if_fail="Our refplane/sketch-plane geometry object is rejected -- bisect refplanes vs "
                   "sketch planes vs the room (single-class probes); diff a rejected refplane vs "
                   "rst 273446 field by field."),
]
ZB_BY_NAME = {r.name: r for r in ZB_CHAIN}
#: the single-change probes: each = the certified parent + ONE bucket in place
ZB_SINGLES = [f"Z_{r.name.split('_', 1)[1]}" for r in ZB_CHAIN]        # Z_defs, Z_mepcat, ...


def _tools():
    tools = os.path.join(ROOT, "tools")
    if tools not in sys.path:
        sys.path.insert(0, tools)
    src = os.path.join(ROOT, "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def _v3():
    """tools/genesis_substitute_v3 -- the in-place ladder machinery this
    stream reuses (plan / retarget / byte-delta assertions / parity /
    registration diff / certification / report shape)."""
    _tools()
    import genesis_substitute_v3 as V3                             # noqa: E402
    return V3


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def y_ladder_landed(y_dir: str = Y_LADDER_DIR) -> Dict[int, str]:
    """{slot: rung} landed by the Y-ladder (Y1..Y9 reports): OUR objects
    already sit in these slots -- protected from every ZB rung."""
    out: Dict[int, str] = {}
    for name in Y_RUNGS:
        p = os.path.join(y_dir, f"{name}.json")
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                rep = json.load(fh)
        except Exception:
            continue
        for row in rep.get("landed_slots") or []:
            out[int(row["slot"])] = name
    return out


def zb_landed(out_dir: str, chain: Sequence[str]) -> Dict[int, str]:
    """{slot: rung} landed by earlier ZB rungs of a derivation chain."""
    out: Dict[int, str] = {}
    for name in chain:
        p = os.path.join(out_dir, f"{name}.json")
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                rep = json.load(fh)
        except Exception:
            continue
        for row in rep.get("landed_slots") or []:
            out[int(row["slot"])] = name
    return out


def zb_prior_correspondence(out_dir: str, chain: Sequence[str]) -> Dict[int, int]:
    """{our temporary id: slot} from earlier ZB rungs (farthest first so a
    nearer rung wins on a temporary-id collision)."""
    out: Dict[int, int] = {}
    for name in reversed(list(chain)):
        p = os.path.join(out_dir, f"{name}.json")
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                rep = json.load(fh)
        except Exception:
            continue
        for row in rep.get("landed_slots") or []:
            if row.get("ours_tmp") is not None:
                out[int(row["ours_tmp"])] = int(row["slot"])
    return out


def zb_chain(rung: ZBRung) -> List[str]:
    """Names of the ancestor ZB rungs (nearest first) up to the BASE."""
    chain: List[str] = []
    cur = rung
    seen: Set[str] = set()
    while cur.parent != "BASE" and cur.parent not in seen:
        chain.append(cur.parent)
        seen.add(cur.parent)
        cur = ZB_BY_NAME[cur.parent]
    return chain


def stage_control(parent_path: str, out_dir: str = ZB_OUT_DIR) -> dict:
    """The batch's CERTIFIED positive CONTROL: a byte-identical copy of the
    certified parent (Y9), md5-asserted, uploaded with EVERY ZB batch."""
    import shutil
    V3 = _v3()
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, f"CTRL_{os.path.splitext(os.path.basename(parent_path))[0]}_base.rvt")
    shutil.copyfile(parent_path, dst)
    if _md5(parent_path) != _md5(dst):                              # pragma: no cover
        raise RuntimeError("staged control is not byte-identical to the parent")
    return {"file": _relp(dst), "identical_to": _relp(parent_path), "md5": _md5(dst),
            "certification": V3.certification_of(parent_path)}


def zb_substitute_inplace(rung: ZBRung, parent_path: str, *, out_dir: str = ZB_OUT_DIR,
                          out_name: Optional[str] = None,
                          y_dir: str = Y_LADDER_DIR, base_path: str = DEFAULT_PARENT,
                          control: Optional[dict] = None,
                          extra_landed: Optional[Dict[int, str]] = None) -> dict:
    """Emit ``<out_dir>/<out_name or rung.name>.rvt`` = ``parent_path`` with
    the rung's residue bucket replaced IN PLACE by our constructors' objects,
    and write the certification report ``.json``.  Mirrors
    ``genesis_substitute_v3.substitute_inplace`` (its plan / retarget /
    byte-delta / parity / regdiff / census / verdict machinery is REUSED),
    with the Y-ladder's landed slots + the earlier ZB rungs' slots
    PROTECTED (our objects already sit there)."""
    V3 = _v3()
    GS = V3.GS
    regadd = V3.regadd
    t_all = time.time()
    name = out_name or rung.name
    out = os.path.join(out_dir, f"{name}.rvt")
    os.makedirs(out_dir, exist_ok=True)
    log(f"\n== {name} :: {rung.label}")
    log(f"   parent {_relp(parent_path)} (base {_relp(base_path)})")
    base_cert = V3.certification_of(base_path)
    if base_cert is None:
        raise RuntimeError(f"{_relp(base_path)} is NOT viewer-certified -- a ZB rung may only "
                           "derive from a certified base (the standing-controls discipline)")
    report: Dict[str, Any] = {
        "rung": name, "label": rung.label, "kind": "inplace", "stream": "genesis-residue-B",
        "mechanism": ("rvt.regadd.substitute_elements -- IN-PLACE, seqs "
                      f"{list(rung.seqs)} (object record only), keep_row=True (ElemTable row "
                      "byte-identical), Global/Latest byte-identical; nothing added, nothing "
                      "deleted; one our-record per residue slot"),
        "base": {"file": _relp(base_path), "certification": base_cert},
        "control_to_upload_with_batch": control,
        "parent": _relp(parent_path), "parent_rung": rung.parent, "out": _relp(out),
        "description": rung.description, "tests": rung.tests,
        "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail, "stages": [],
        "group_b_classes": {k: v[0] for k, v in GROUP_B_CLASSES.items() if v[2] == rung.name},
    }
    # ---- 1. context + protection + build ------------------------------------
    t0 = time.time()
    ctx = GS.SubstContext(parent_path, name)
    chain = zb_chain(rung)
    protected: Dict[int, str] = dict(y_ladder_landed(y_dir))
    protected.update(zb_landed(out_dir, chain))
    if extra_landed:
        protected.update(extra_landed)
    sb = rung.build(ctx, protected)
    build_s = round(time.time() - t0, 1)
    old_by_class = collections.Counter(ctx.cls_of.get(int(o), "?") for o in sb.old_ids)
    new_by_class = collections.Counter(r.class_name for r in sb.records)
    log(f"   build: residue slots {len(sb.old_ids)} {dict(old_by_class.most_common(6))}; "
        f"OUR records {len(sb.records)} {dict(new_by_class.most_common(6))}; "
        f"correspondence {len(sb.corr)} (protected earlier-rung slots {len(protected)}) ({build_s}s)")
    report["parent_context"] = {"host_elements": len(ctx.host), "watermark": ctx.watermark,
                                "protected_slots_from_earlier_rungs": len(protected)}
    report["candidates_old_by_class"] = dict(old_by_class.most_common())
    report["our_records_by_class"] = dict(new_by_class.most_common())
    report["build_notes"] = sb.notes
    report["build_info"] = sb.info
    report["residue_named_by_builder"] = sb.residue
    # ---- 2. plan (role correspondence; slot-fill off: one record per slot) --
    plan = V3.plan_inplace(ctx, sb, slot_fill=rung.slot_fill, protected=set(protected))
    match_hist = collections.Counter(p.match for p in plan.pairs)
    landed_by_class = collections.Counter(p.cls for p in plan.pairs)
    log(f"   plan: {len(plan.pairs)} landed {dict(match_hist)}; dropped ours "
        f"{len(plan.dropped)}; residue olds {len(plan.residue)}; class mismatches "
        f"{len(plan.class_mismatch)}")
    report["plan"] = {"landed": len(plan.pairs), "by_match": dict(match_hist),
                      "landed_by_class": dict(landed_by_class.most_common()),
                      "dropped_ours": len(plan.dropped), "residue_olds": len(plan.residue),
                      "class_mismatch": plan.class_mismatch, "notes": plan.notes}
    if not plan.pairs:
        report["FAILED_SELF_CHECK"] = "no landed pairs -- this bucket does not exist in the parent"
        report["verdict"] = "NOT-BUILT"
        V3._write_report(out_dir, name, report)
        log(f"   *** {name}: nothing to substitute")
        return report
    # ---- 3. retarget + self-check ------------------------------------------------
    t0 = time.time()
    prior_map = zb_prior_correspondence(out_dir, chain)
    records_by_id, rt_rep = V3.retarget(ctx, sb, plan, seqs=rung.seqs, prior_tmp_to_slot=prior_map)
    report["retarget"] = {k: (v if not isinstance(v, list) else v[:40]) for k, v in rt_rep.items()}
    report["retarget"]["seconds"] = round(time.time() - t0, 1)
    log(f"   retarget: {rt_rep['records']} records; leaves remapped {rt_rep['leaves_remapped']}; "
        f"neutralised {len(rt_rep['dropped_refs_neutralised'])}; self-check failures "
        f"{len(rt_rep['record_selfcheck_failures'])}")
    if rt_rep["record_selfcheck_failures"]:
        report["FAILED_SELF_CHECK"] = (f"{len(rt_rep['record_selfcheck_failures'])} re-targeted "
                                       "record body/bodies not schema-clean / byte-exact")
        report["verdict"] = "NOT-BUILT"
        report["retarget"]["record_selfcheck_failures"] = rt_rep["record_selfcheck_failures"][:20]
        V3._write_report(out_dir, name, report)
        log(f"   *** {name}: {report['FAILED_SELF_CHECK']} -- NO FILE EMITTED")
        return report
    slots = set(records_by_id)
    live = set(ctx.universe) | slots
    dangle = []
    for slot, by_seq in records_by_id.items():
        for seq, (cid, val) in by_seq.items():
            cname = "ElementHeader" if seq == 101 else ctx.doc.dec.class_name(cid)
            for lf in ctx.ted.leaves(val, cname):
                x = lf.value
                if isinstance(x, int) and x > 0 and x not in live:
                    dangle.append({"slot": slot, "seq": seq, "path": lf.path, "target": x})
    report["new_object_reference_check"] = {"dangling": len(dangle), "examples": dangle[:12]}
    if dangle:
        report["FAILED_SELF_CHECK"] = f"{len(dangle)} unresolved reference(s) in our re-targeted objects"
        report["verdict"] = "NOT-BUILT"
        V3._write_report(out_dir, name, report)
        log(f"   *** {name}: {report['FAILED_SELF_CHECK']} -- NO FILE EMITTED")
        return report
    # ---- 4. the in-place substitution -------------------------------------------
    t0 = time.time()
    srep = regadd.substitute_elements(parent_path, out,
                                      {int(k): {int(s): tuple(v) for s, v in bs.items()}
                                       for k, bs in records_by_id.items()},
                                      seqs=tuple(int(s) for s in rung.seqs),
                                      keep_row=True, verify=True, diff=True)
    emit_s = round(time.time() - t0, 1)
    diff = srep.diff or {}
    pname = (diff.get("streams") and (srep.emit or {}).get("partition")) or "Partitions/?"
    log(f"   emit: {srep.op} verdict {srep.verdict} problems {srep.problems}; streams differing "
        f"{(diff.get('streams') or {}).get('differing')} ({emit_s}s)")
    report["substitute"] = {"op": srep.op, "verdict": srep.verdict, "problems": srep.problems,
                            "seqs_replaced": srep.seqs_replaced,
                            "elemtable_rewritten": (srep.emit or {}).get("elemtable_rewritten"),
                            "latest_rewritten": (srep.emit or {}).get("latest_rewritten"),
                            "streams_replaced": (srep.emit or {}).get("streams_replaced"),
                            "seconds": emit_s}
    # ---- 5. certification --------------------------------------------------------
    t0 = time.time()
    byte_delta = V3._byte_delta_assertions(diff, slots=slots, seqs=rung.seqs, partition_name=pname)
    parity = V3._parity_report(ctx, slots, latest_identical=bool((diff.get("latest") or {}).get("identical")))
    reg_sample = V3._registration_diff_sample(parent_path, out, sorted(slots), limit=6)
    try:
        _tools()
        import genesis_triage as GT                                       # noqa: E402
        cen = GT.census(out)
    except Exception as ex:                                             # pragma: no cover
        cen = {"error": repr(ex)[:300]}
    coherence = {"save_units": cen.get("save_units"), "contentdocs_entries": cen.get("contentdocs_entries"),
                 "contenttable_records": cen.get("contenttable_records"),
                 "adocument_clean": cen.get("adocument_clean"),
                 "coherent": (cen.get("save_units") is not None
                              and cen.get("save_units", 0) - 1 == cen.get("contentdocs_entries")
                              == cen.get("contenttable_records"))}
    report["byte_delta"] = byte_delta
    report["parity"] = parity
    report["registration_diff_sample"] = reg_sample
    report["validator"] = srep.validator
    report["structural"] = srep.structural
    report["census"] = {k: cen.get(k) for k in ("path", "elements", "file_size", "save_units",
                                                   "contentdocs_entries", "contenttable_records",
                                                   "adocument_clean") if k in cen}
    report["coherence"] = coherence
    report["certification_seconds"] = round(time.time() - t0, 1)
    # ---- 6. the record ---------------------------------------------------------------
    recs_by_tmp = {int(r.elem_id): r for r in sb.records}
    report["correspondence"] = [
        {"ours_tmp": p.ours, "slot": p.slot, "class": p.cls, "match": p.match,
         "role_group": p.role_group, "slot_referrers": p.slot_referrers,
         "our_name": (_rec_display_name(recs_by_tmp.get(p.ours)))}
        for p in sorted(plan.pairs, key=lambda x: x.slot)][:400]
    report["landed_slots"] = [{"slot": p.slot, "class": p.cls, "match": p.match, "ours_tmp": p.ours}
                               for p in plan.pairs]
    report["ours_not_landed"] = {"count": len(plan.dropped),
                                 "by_class": dict(collections.Counter(d["class"] for d in plan.dropped).most_common()),
                                 "examples": plan.dropped[:24]}
    report["residue_olds_left_in_place"] = {"count": len(plan.residue),
                                            "by_class": dict(collections.Counter(r["class"] for r in plan.residue).most_common())}
    # ---- 7. verdict --------------------------------------------------------------------
    problems: List[str] = []
    if srep.verdict != "VALID":
        problems += [f"regadd: {p}" for p in (srep.problems or [])]
    val = srep.validator or {}
    if not (val.get("ok") and val.get("errors") == 0):
        problems.append(f"validator errors={val.get('errors')}")
    if not (srep.structural or {}).get("ok"):
        problems.append("structural proof failed")
    if not byte_delta["assertion_holds"]:
        problems += byte_delta["problems"]
    if not parity["latest_byte_identical"]:
        problems.append("Global/Latest not byte-identical (parity unproven)")
    if not coherence["coherent"]:
        problems.append("four-registry document coherence broken")
    regdiff_bad = [r for r in reg_sample if not r.get("registration_identical")
                   and r.get("non_object_differences")]
    if regdiff_bad:
        problems.append(f"{len(regdiff_bad)} sampled slot(s) show a NON-object registration difference")
    if rt_rep["dropped_refs_neutralised"]:
        report.setdefault("warnings", []).append(
            f"{len(rt_rep['dropped_refs_neutralised'])} record body/bodies had references to our "
            f"NOT-LANDED records neutralised (listed in retarget.dropped_refs_neutralised)")
    report["problems"] = problems
    report["verdict"] = "VALID" if not problems else "NOT-CLEAN"
    if problems:
        report["FAILED_SELF_CHECK"] = "; ".join(problems)
    report["bytes"] = os.path.getsize(out) if os.path.exists(out) else None
    report["seconds"] = round(time.time() - t_all, 1)
    V3._write_report(out_dir, name, report)
    log(f"   byte-delta: only-partition {byte_delta['only_partition_differs']}; changed "
        f"{byte_delta['records_changed_count']} of {byte_delta['expected_slots']} slots "
        f"(unchanged {byte_delta['landed_but_unchanged_slots']}); ElemTable identical "
        f"{byte_delta['elemtable_identical']}; ADocument identical {byte_delta['adocument_identical']}")
    log(f"   validator: {'VALID' if val.get('ok') else 'INVALID'} errors={val.get('errors')} "
        f"warnings={val.get('warnings')}; structural ok={(srep.structural or {}).get('ok')}; "
        f"coherence {coherence['save_units']}/{coherence['contentdocs_entries']}/"
        f"{coherence['contenttable_records']}; regdiff sample "
        f"{sum(1 for r in reg_sample if r.get('registration_identical'))}/{len(reg_sample)} identical")
    log(f"   -> {_relp(out)} {report['bytes']:,} B  VERDICT {report['verdict']}"
        f"{('  *** ' + report['FAILED_SELF_CHECK']) if problems else ''} ({report['seconds']}s)")
    for m in (val.get("error_messages") or [])[:4]:
        log(f"      ERROR {m}")
    return report


def _rec_display_name(rec) -> str:
    if rec is None:
        return ""
    o = getattr(rec, "obj", None) or {}
    si = o.get("m_symbolInfo")
    if isinstance(si, dict):
        n = (si.get("value") or {}).get("m_name")
        if n:
            return str(n)
    pd = o.get("m_pParamDef")
    if isinstance(pd, dict):
        n = (pd.get("value") or {}).get("m_caption")
        if n:
            return str(n)
    for k in ("m_name", "m_text", "m_viewName", "m_inInterfaceName"):
        x = o.get(k)
        if isinstance(x, str) and x.strip():
            return x
    h = o.get("m_pMaterial")
    if isinstance(h, dict):
        n = (h.get("value") or {}).get("m_name")
        if n:
            return str(n)
    return ""


# ---------------------------------------------------------------------------
# the ladder driver: the CHAIN (-> ZB_deep) + the SINGLE probes + probes.json
# ---------------------------------------------------------------------------

def build_zb_ladder(out_dir: str = ZB_OUT_DIR, *, parent: str = DEFAULT_PARENT,
                    only: Sequence[str] = (), singles: bool = True,
                    ledger: bool = True) -> dict:
    """Build the ZB CHAIN (ZB1 <- Y9, ZBk <- ZB(k-1); copy the last as
    ZB_deep.rvt) + the SINGLE probes (Z_<bucket> = Y9 + one bucket) + the
    control + probes.json.  Returns {rung: verdict}."""
    V3 = _v3()
    os.makedirs(out_dir, exist_ok=True)
    parent = os.path.abspath(parent)
    if not os.path.exists(parent):
        raise FileNotFoundError(parent)
    cert = V3.certification_of(parent)
    if cert is None:
        raise RuntimeError(f"{_relp(parent)} is not viewer-CERTIFIED; the ZB ladder needs a "
                           f"certified parent (Y9)")
    log(f"[parent] {_relp(parent)} -- CERTIFIED: {cert.get('proves', '')[:120]}")
    control = stage_control(parent, out_dir)
    log(f"[control] staged {control['file']} (md5 {control['md5']}) -- upload with EVERY batch")
    verdicts: Dict[str, str] = {}
    want = set(only)
    t0 = time.time()
    # ---- the cumulative chain -------------------------------------------------
    prev_path = parent
    chain_ok = True
    for rung in ZB_CHAIN:
        if want and rung.name not in want and "chain" not in want:
            # a skipped rung breaks the chain: later rungs derive from the parent
            p = os.path.join(out_dir, f"{rung.name}.rvt")
            prev_path = p if os.path.exists(p) else prev_path
            continue
        if not chain_ok:
            break
        parent_path = parent if rung.parent == "BASE" else os.path.join(out_dir, f"{rung.parent}.rvt")
        if not os.path.exists(parent_path):
            log(f"\n== {rung.name}: parent {_relp(parent_path)} missing -- SKIPPED")
            chain_ok = False
            continue
        try:
            rep = zb_substitute_inplace(rung, parent_path, out_dir=out_dir, base_path=parent,
                                        control=control)
            verdicts[rung.name] = rep.get("verdict", "?")
            if rep.get("verdict") not in ("VALID",):
                chain_ok = False
        except Exception as ex:                                       # a rung that cannot build is a FINDING
            import traceback
            tb = traceback.format_exc()
            log(f"\n== {rung.name}: BUILD ABORTED -- {ex!r}\n{tb}")
            V3._write_report(out_dir, rung.name, {"rung": rung.name, "label": rung.label,
                                                  "verdict": "NOT-BUILT", "abort": repr(ex),
                                                  "traceback": tb})
            bad = os.path.join(out_dir, f"{rung.name}.rvt")
            if os.path.exists(bad):
                os.remove(bad)
            verdicts[rung.name] = "NOT-BUILT"
            chain_ok = False
    # ZB_deep = the deepest built chain file (a named copy, md5-recorded)
    deepest = None
    for rung in reversed(ZB_CHAIN):
        p = os.path.join(out_dir, f"{rung.name}.rvt")
        if os.path.exists(p) and verdicts.get(rung.name, "VALID") == "VALID":
            deepest = rung.name
            break
    if deepest:
        import shutil
        src = os.path.join(out_dir, f"{deepest}.rvt")
        dst = os.path.join(out_dir, "ZB_deep.rvt")
        shutil.copyfile(src, dst)
        with open(os.path.join(out_dir, "ZB_deep.json"), "w") as fh:
            json.dump({"rung": "ZB_deep", "alias_of": deepest,
                       "chain": [r.name for r in ZB_CHAIN[:[r.name for r in ZB_CHAIN].index(deepest) + 1]],
                       "file": _relp(dst), "md5": _md5(dst), "identical_to": _relp(src),
                       "verdict": verdicts.get(deepest, "?")}, fh, indent=1)
        log(f"\n[ZB_deep] = {deepest}.rvt -> {_relp(dst)} (md5 {_md5(dst)})")
        verdicts["ZB_deep"] = verdicts.get(deepest, "?")
    # ---- the single-change probes (each = the certified parent + one bucket) --
    if singles:
        for rung, single_name in zip(ZB_CHAIN, ZB_SINGLES):
            if want and single_name not in want and "singles" not in want:
                continue
            single = dataclasses.replace(rung, name=single_name, parent="BASE",
                                         label=f"{rung.label} [SINGLE-CHANGE PROBE off the parent]")
            try:
                rep = zb_substitute_inplace(single, parent, out_dir=out_dir, out_name=single_name,
                                            base_path=parent, control=control)
                verdicts[single_name] = rep.get("verdict", "?")
            except Exception as ex:
                import traceback
                tb = traceback.format_exc()
                log(f"\n== {single_name}: BUILD ABORTED -- {ex!r}\n{tb}")
                V3._write_report(out_dir, single_name, {"rung": single_name, "verdict": "NOT-BUILT",
                                                         "abort": repr(ex), "traceback": tb})
                bad = os.path.join(out_dir, f"{single_name}.rvt")
                if os.path.exists(bad):
                    os.remove(bad)
                verdicts[single_name] = "NOT-BUILT"
    # ---- the residue re-census of the deepest file (what B leaves) ------------
    if deepest:
        try:
            deep_path = os.path.join(out_dir, "ZB_deep.rvt")
            cen = census_group_b_residue(deep_path, out_dir)
            with open(os.path.join(out_dir, "ZB_deep_census.json"), "w") as fh:
                json.dump(cen, fh, indent=1, default=str)
            log(f"[census] ZB_deep Group-B residue: {cen['group_b_residue_elements']} elements "
                f"in {len(cen['by_class'])} classes -> {os.path.join(_relp(out_dir), 'ZB_deep_census.json')}")
        except Exception as ex:                                        # pragma: no cover
            log(f"[census] skipped: {ex!r}")
    write_zb_probes_manifest(out_dir, parent, control, verdicts)
    log(f"\n=== ZB LADDER SUMMARY ({time.time() - t0:.1f}s) ===")
    for k, v in verdicts.items():
        log(f"  {k:<16} {v}")
    return verdicts


def census_group_b_residue(rvt_path: str, out_dir: str = ZB_OUT_DIR,
                           y_dir: str = Y_LADDER_DIR) -> dict:
    """Re-census of a built file: how many GROUP-B residue elements remain
    (elements of a Group-B class NOT landed by any Y or ZB rung)."""
    from ..mutate import Document
    landed = dict(y_ladder_landed(y_dir))
    landed.update(zb_landed(out_dir, [r.name for r in ZB_CHAIN]))
    doc = Document.from_file(rvt_path)
    residue: Dict[str, int] = collections.Counter()
    landed_here: Dict[str, int] = collections.Counter()
    for e in doc.et_by_id:
        c = doc.class_of(e) or "?"
        if c not in GROUP_B_CLASSES:
            continue
        if int(e) in landed:
            landed_here[c] += 1
        else:
            residue[c] += 1
    return {"file": _relp(rvt_path), "group_b_landed_ours": dict(landed_here),
            "group_b_residue_elements": sum(residue.values()), "by_class": dict(residue)}


def write_zb_probes_manifest(out_dir: str, parent: str, control: dict,
                             verdicts: Dict[str, str]) -> str:
    """probes.json for the ZB batch: ZB_deep FIRST (a PASS proves every
    Group-B constructor at once), then the single-change probes ordered by
    information value, each naming its CERTIFIED base (Y9) + the control."""
    V3 = _v3()
    base_cert = V3.certification_of(parent)
    entries: List[dict] = []
    order = ["ZB_deep"] + ZB_SINGLES + [r.name for r in ZB_CHAIN]
    for i, name in enumerate(order, 1):
        p = os.path.join(out_dir, f"{name}.rvt")
        rp = os.path.join(out_dir, f"{name}.json")
        if not os.path.exists(p):
            continue
        rep = {}
        if os.path.exists(rp):
            try:
                with open(rp) as fh:
                    rep = json.load(fh)
            except Exception:
                rep = {}
        rung = ZB_BY_NAME.get(name)
        if rung is None and name.startswith("Z_"):
            rung = next((r for r in ZB_CHAIN if r.name.endswith(name[2:])), None)
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        plan = rep.get("plan") or {}
        entry = {
            "order": len(entries) + 1, "rung": name,
            "file": os.path.join(_relp(out_dir), f"{name}.rvt"),
            "class_layer_substituted": (rung.label if rung else "the cumulative Group-B residue ladder"),
            "base": {"file": _relp(parent), "certification": base_cert},
            "derived_from": rep.get("parent") or _relp(parent),
            "parent_rung": rep.get("parent_rung", "BASE"),
            "the_ONE_thing_it_tests": (rung.tests if rung else
                                       "EVERY Group-B residue constructor at once (the deepest ZB file)"),
            "if_PASS": (rung.if_pass if rung else
                        "every Group-B constructor loads at Autodesk's registrations; what remains "
                        "of Group B = the documented gaps (thermal assets) + the endgame's "
                        "deletion set (external link, sample content by choice)"),
            "if_FAIL": (rung.if_fail if rung else
                        "read the single-change probes Z_<bucket> in order: the first FAIL whose "
                        "parent PASSED convicts exactly that bucket"),
            "elements_substituted_in_place": {"landed": plan.get("landed"),
                                              "by_class": plan.get("landed_by_class"),
                                              "by_match": plan.get("by_match")},
            "ours_not_landed": (rep.get("ours_not_landed") or {}).get("by_class"),
            "byte_delta": ({k: bd.get(k) for k in ("only_partition_differs", "records_changed_count",
                                                    "expected_slots", "unexpected_changed_ids",
                                                    "records_added_ids", "records_removed_ids",
                                                    "elemtable_identical", "adocument_identical",
                                                    "assertion_holds", "landed_but_unchanged_slots")}
                           if bd else None),
            "registry_parity": (rep.get("parity") or {}).get("parity"),
            "validator": {"ok": v.get("ok"), "errors": v.get("errors"), "warnings": v.get("warnings")},
            "structural_ok": (rep.get("structural") or {}).get("ok"),
            "document_coherence": rep.get("coherence"),
            "verdict": rep.get("verdict") or verdicts.get(name, "not built"),
            "self_check": rep.get("FAILED_SELF_CHECK"),
            "bytes": rep.get("bytes"),
            "control_to_upload_with_batch": control,
            "report": os.path.join(_relp(out_dir), f"{name}.json"),
        }
        if name == "ZB_deep":
            entry["note"] = ("ZB_deep.rvt is a byte-identical copy of the deepest CHAIN rung "
                             "(see ZB_deep.json alias_of); upload ONCE and record the verdict for both")
        entries.append(entry)
    manifest = {
        "stream": "genesis-residue-B (RESIDUE CONSTRUCTORS, GROUP B: the residue classes M..Z + "
                  "the endgame)",
        "situation": ("Y9 (certified, VERDICTS #17) leaves 2,009 residue elements in 11 buckets; "
                      "Group B owns the 29 classes sorting M..Z (997 elements). Each ZB rung "
                      "substitutes one bucket's residue slots IN PLACE with OUR constructors' "
                      "objects; ZB_deep = Y9 + every ZB rung."),
        "the_operation": ("In-place substitution (rvt.regadd.substitute_elements): our object "
                          "record (seq-102) replaces the sample's at the SAME id / ElemTable row / "
                          "record position / registry slots; Global/Latest + Global/ElemTable "
                          "BYTE-IDENTICAL to the parent; nothing added or deleted; the Y-ladder's "
                          "landed slots are protected."),
        "base": {"file": _relp(parent), "certification": base_cert,
                 "lineage": "Y9 = the deepest CERTIFIED in-place rung on K4 (VERDICTS #17: Y1, "
                            "Y_cat, Y9 ALL PASS); K4 = the certified family-free base"},
        "standing_control": control,
        "controls_discipline": ("EVERY batch is uploaded with the certified control (a byte-"
                                "identical copy of Y9). If the CONTROL fails, the batch is VOID and "
                                "nothing about our constructors is read from it. Only with the "
                                "control PASSING are the probe verdicts read."),
        "upload_order_bisection_first": [e["rung"] for e in entries],
        "reading_the_results": {
            "how": ("ZB_deep FIRST: a PASS proves every Group-B constructor loads at Autodesk's "
                    "registrations in ONE verdict. ZB_deep FAIL -> read the singles Z_defs, "
                    "Z_mepcat, Z_pens, Z_annot, Z_palette, Z_filters, Z_machinery, Z_content: "
                    "each is Y9 + ONE bucket, so the first FAIL (control passing) convicts exactly "
                    "that bucket's constructors; the chain rungs ZB1..ZB8 bracket a combination."),
            "Z_machinery FAIL": ("cannot be our content (the reproduced machinery slots are byte-"
                                 "identical) -> read the print / worksharing / drafting-companion "
                                 "sub-groups (the report lists which slots CHANGED)."),
            "ALL PASS": ("Group B's residue is retired as an engineering question: what remains is "
                         "the endgame (docs/writer/genesis-endgame.md): the thermal-asset gap, the "
                         "external-link deletion, and the choice deletion-vs-ours for sample "
                         "content."),
        },
        "verdicts_local_self_checks": verdicts,
        "probes": entries,
        "derivation_chain": [f"{r.name} <- {r.parent}" for r in ZB_CHAIN] +
                            [f"{s} <- BASE(Y9)" for s in ZB_SINGLES],
        "endgame": "docs/writer/genesis-endgame.md",
        "record": "docs/inbox/genesis-residue-B.md",
    }
    p = os.path.join(out_dir, "probes.json")
    os.makedirs(out_dir, exist_ok=True)
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"[probes] wrote {_relp(p)} ({len(entries)} entries)")
    return p


# ===========================================================================
# 12. CLI
# ===========================================================================

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="genesis-residue-B: the ZB in-place ladder over "
                                             "the Group-B residue classes (M..Z)")
    ap.add_argument("--parent", default=DEFAULT_PARENT,
                    help="the CERTIFIED parent (default experiments/genesis/subst_k4/Y9.rvt)")
    ap.add_argument("--out-dir", default=ZB_OUT_DIR)
    ap.add_argument("--only", default="", help="comma list of rungs (ZB1_defs,Z_defs,...) / 'chain' / 'singles'")
    ap.add_argument("--no-singles", action="store_true", help="skip the single-change probes")
    ap.add_argument("--manifest-only", action="store_true", help="only (re)write probes.json")
    ap.add_argument("--census", action="store_true", help="print the Group-B census summary and exit")
    args = ap.parse_args(argv)
    if args.census:
        print(json.dumps({k: {"residue": v.get("residue"), "verdict": v.get("verdict")}
                          for k, v in GROUP_B_CENSUS.items()}, indent=1))
        print(json.dumps({"group_b_total_residue_elements": GROUP_B_TOTAL,
                          "classes": len(GROUP_B_CLASSES)}, indent=1))
        return 0
    out_dir = os.path.abspath(args.out_dir)
    parent = os.path.abspath(args.parent)
    if args.manifest_only:
        V3 = _v3()
        control = stage_control(parent, out_dir)
        write_zb_probes_manifest(out_dir, parent, control, {})
        return 0
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    verdicts = build_zb_ladder(out_dir, parent=parent, only=only,
                               singles=not args.no_singles)
    bad = [k for k, v in verdicts.items() if v != "VALID"]
    return 0 if not bad else 1


if __name__ == "__main__":                                        # pragma: no cover
    sys.exit(main())

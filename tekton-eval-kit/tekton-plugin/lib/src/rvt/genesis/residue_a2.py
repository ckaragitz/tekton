"""genesis/residue_a2.py -- RESIDUE CONSTRUCTORS, GROUP A / ROUND 2: THE
REMAINING UNSUBSTITUTED CLASSES of the first Group-A round's disposition list
(``docs/inbox/genesis-residue-A.md`` § "The other A..L residue classes ...
DISPOSITIONED", ``residue_after_ZA_deep.json`` disposition
"outside both charters") -- the HVAC / energy database web, the electrical
load / demand-factor catalog, the conduit & cable-tray catalogs, the residue
system-family types, the analysis / area / structural settings machinery, the
surplus browser organizations and the drafting-view + sheet constellation --
as OUR constructors + the in-place ZC rungs that substitute them into the
CERTIFIED ZA_deep file.

BASE (viewer-CERTIFIED, VERDICTS #18): ``experiments/genesis/subst_k4/
residue_a/ZA_deep.rvt`` = Y9 + Group A's five class layers in place --
1,806 of the base's 3,342 host elements are OUR constructors' output; the
K4-inherited RESIDUE = 1,536 elements (``residue_after_ZA_deep.json``).  Of
those, 373 lie "outside both charters"; 61 of them are Group B's MEP
wire / pipe catalog (74 elements incl. PipeSegment; ``genesis-residue-B``,
ZB2_mepcat, viewer-PASS batch 17) and the external-link pair (D_links /
the clean-header rung).  THIS module retires the 312 elements the first
Group-A round dispositioned by class and NAMED an owning rung for, plus it
STATES the operation of every element that cannot be substituted in place.

THE OPERATION (identical physics to the Y / ZA / ZB ladders): every rung is
``rvt.regadd.substitute_elements(seqs=(102,), keep_row=True)`` on the
certified parent -- OUR constructor's seq-102 OBJECT replaces the sample's at
the SAME element id, same ElemTable row, same record position, same registry
slots; ``Global/Latest`` + ``Global/ElemTable`` BYTE-IDENTICAL; nothing
added, nothing deleted; the byte-delta-vs-parent assertion (only the landed
slots' object records change) + registry parity + the ``rvt.regdiff`` sample
+ the per-class FIELD-DELTA table (which object fields carry OUR value) are
recorded per rung by the ladder's own certification helpers
(``rvt.genesis.residue_a.emit_rung`` -> ``tools/genesis_substitute_v3.py``).

THE FIVE HONEST CATEGORIES this census sorts every residue class into:
  A. INTERFACE-KEYED SETTINGS -- a per-release ENUM the reader keys on (the
     125 HVAC space types / 33 building types = the public gbXML / ASHRAE
     space- and building-type enumerations; the 8 built-in area types; the
     load-classification signature roles) whose VALUES are the document's
     settings: the enum identity is REPRODUCED from the slot, the values are
     OURS (rvt.genesis.catalog's law: "THE ENUM IS A FORMAT CONSTANT, THE
     VALUES ARE OURS").
  B. NAME-KEYED CATALOG CONTENT -- schedules, demand factors, load
     classifications, load natures / cases, conduit standards, colour
     schemes, browser organizations, fabric types: OUR library at the slots.
  C. PURE MACHINERY -- no free value at all (AreaTypeElem, the empty
     AreaSchemePlanTopologies holders, BuildingOperatingYearSchedule
     wrappers, the sheet's DBDrawing viewport list): REPRODUCED
     byte-identical and DECLARED "nothing of ours to reject" (Group B's
     machinery-reproduction proof method, ``genesis-residue-B.md`` F8).
  D. PRODUCT DATA WE EMPTY -- Autodesk's shipped UniFormat table embedded in
     the AssemblyCodeTable (795 rows + an Autodesk employee's local path,
     byte-identical in all six samples): OUR AssemblyCodeTable is EMPTY (the
     KeynoteTable precedent), which also retires the identity leak.
  E. NOT IN-PLACE-ABLE -- stated with the required operation (§NON_INPLACE):
     the linked-model pair (DELETE; instance side emitted by the deletion
     stream's D_links, the symbol waits on the clean-header rung), the
     DataStorage Extensible-Storage vendor blob (DELETE, undecodable leaf),
     the room-owned AreaSchemePlanTopologies 9744 (leaves with the room).

Territory (this stream): this module, ``tests/test_residue_a2.py``,
``experiments/genesis/subst_k4/residue_a2/*``, ``docs/inbox/genesis-
residue-A2.md``.  Every dependency (``rvt.genesis.{types,settings,
house_standard,residue_a,residue_b}``, ``rvt.regadd`` / ``rvt.regdiff`` /
``rvt.mutate``, and the certification helpers of ``tools/genesis_
substitute_v3.py``) is IMPORTED, never edited.  Python: ``.venv/bin/python``
from the repo root::

    .venv/bin/python -m rvt.genesis.residue_a2                 # census + whole ZC ladder
    .venv/bin/python -m rvt.genesis.residue_a2 --only ZC_elec,ZC_conduit
    .venv/bin/python -m rvt.genesis.residue_a2 --census-only   # residue census only
    .venv/bin/python -m rvt.genesis.residue_a2 --derive-enums  # (re)freeze the HVAC enums
    .venv/bin/python -m rvt.genesis.residue_a2 --demo          # constructors round-trip
"""
from __future__ import annotations

import argparse
import collections
import copy
import dataclasses
import hashlib
import json
import math
import os
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .types import (INVALID, NO_DESIGN_OPTION, VOLT_TO_INTERNAL, blank_object,
                    element_defaults, symbol_defaults, class_id, _owned, _ptr, mm,
                    inches, rgb)
from . import types as TY
from . import house_standard as hs
from . import residue_a as RA

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
LADDER_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4")
#: THE CERTIFIED PARENT of every ZC rung (VERDICTS #18: "*** GROUP-A RESIDUE LOADS ***")
DEFAULT_PARENT = os.path.join(LADDER_DIR, "residue_a", "ZA_deep.rvt")
DEFAULT_PARENT_REPORT = os.path.join(LADDER_DIR, "residue_a", "ZA_deep.json")
#: this stream's territory
RESIDUE_DIR = os.path.join(LADDER_DIR, "residue_a2")
ENUMS_FILE = os.path.join(RESIDUE_DIR, "hvac_type_enums.json")
LEDGER_MD = os.path.join(ROOT, "docs", "inbox", "genesis-residue-A2.md")
#: the standing certified control of the batch (a byte-identical copy of the base)
CTRL_ZA_DEEP = os.path.join(RESIDUE_DIR, "CTRL_ZA_deep_base.rvt")
CORPUS_SAMPLES = ["rstbasicsampleproject", "rstadvancedsampleproject",
                  "racbasicsampleproject", "racadvancedsampleproject",
                  "rmebasicsampleproject", "dach-sample-project"]

PREFIX = hs.PREFIX                                   # 'GEN' -- our house prefix
log = RA.log
gen = hs.gen
field_delta = RA.field_delta
Obj = RA.Obj
RungPlan = RA.RungPlan

# ---------------------------------------------------------------------------
# unit helpers (format facts: Revit internal units)
# ---------------------------------------------------------------------------
#: W -> Revit internal power (kg*ft^2/s^3): the m^2->ft^2 factor
P_INT = float(VOLT_TO_INTERNAL)                      # 10.7639104167097
BTUH_TO_W = 0.29307107


def kelvin_f(deg_f: float) -> float:
    """degrees Fahrenheit -> Kelvin (temperature setpoints are stored in K)."""
    return (float(deg_f) - 32.0) * 5.0 / 9.0 + 273.15


def w_per_ft2(x: float) -> float:
    """W/ft^2 -> internal power density (W * P_INT per ft^2)."""
    return float(x) * P_INT


def watts(x: float) -> float:
    """W -> internal power."""
    return float(x) * P_INT


def btuh(x: float) -> float:
    """Btu/h -> internal power."""
    return watts(float(x) * BTUH_TO_W)


def cfm(x: float) -> float:
    """ft^3/min -> ft^3/s (airflow rates are stored per second)."""
    return float(x) / 60.0


def kva(x: float) -> float:
    """kVA -> internal power (a demand-rule load-range breakpoint)."""
    return float(x) * 1000.0 * P_INT


def _deep(v):
    return copy.deepcopy(v)


# ===========================================================================
# 0. THE CLAIM (what this stream substitutes, what it cannot, what is others')
# ===========================================================================
#: rung -> the residue classes it substitutes IN PLACE (the disposition list)
CLAIMED_CLASSES: Dict[str, List[str]] = {
    "ZC_hvac":    ["HVACLoadScheduleElem", "BuildingOperatingYearSchedule",
                   "HVACLoadBuildingTypeElem", "HVACLoadSpaceTypeElem"],
    "ZC_elec":    ["ElectricalLoadClassification", "ElectricalDemandFactorDefinition"],
    "ZC_conduit": ["ConduitStandardType", "ConduitSizesElem", "CableTraySizesElem"],
    "ZC_systype": ["BasicWallType", "FloorAttributes", "FabricSheetType", "FabricWireType"],
    "ZC_analysis": ["AreaTypeElem", "AreaSchemePlanTopologies", "AreaReportSettingsElem",
                    "AssemblyCodeTable", "ColorFillSchema", "LoadCaseElem", "LoadNatureElem"],
    "ZC_browse":  ["BrowserOrganization", "DBViewDrafting", "DBDrawing"],
}
RUNG_ORDER = ["ZC_hvac", "ZC_elec", "ZC_conduit", "ZC_systype", "ZC_analysis", "ZC_browse"]

#: what CANNOT be substituted in place -> {class or key: (operation, reason)}
NON_INPLACE: Dict[str, Tuple[str, str]] = {
    "RvtLinkSymbol": (
        "DELETE-WITH-CONTENT (clean-header rung first)",
        "a genesis file links NO model: the symbol names an external Autodesk sample file "
        "('rac_basic_sample_project.rvt' + a relative path) -- nothing of ours to express at "
        "the slot.  The deletion stream (docs/inbox/genesis-deletion.md, finding 1) measured it "
        "NOT delete-reachable on ZA_deep: OUR OWN Y2/Y9 view slots' inherited seq-101 headers "
        "list it as a deletion parent, and this stream's ZC_browse sheet-view constructor "
        "REMOVES its remaining seq-102 pin (the drafting/sheet view's RvtLinkOverrides display "
        "map).  Retirement = the clean-header rung (seqs 101+102 on our views) then one maxgc "
        "deletion of {symbol + drafting-view constellation} -- the substitution stream's queue."),
    "RvtLinkInstance": (
        "DELETE-WITH-CONTENT (emitted: deletion stream D_links)",
        "the placed instance of the link; the deletion stream's D_links probe deletes it with "
        "OUR CopyWatchProperties 1250031 (delete-with-content of our own referrer, EDIT-FREE)."),
    "DataStorage": (
        "DELETE (leaf)",
        "an Extensible-Storage container whose ESEntity blob is a VENDOR schema this project's "
        "decoder does not read (the arbiter's one standing warning): there is nothing of ours to "
        "express, and reproducing it would keep an undecoded third-party blob -- a zero-referrer "
        "leaf for the deletion set (endgame step 24)."),
    "AreaSchemePlanTopologies(room)": (
        "DELETE-WITH-CONTENT (with the room constellation)",
        "topology 9744 CONTAINS the placed room's LevelRoomPlan + boundary curves (deletion "
        "stream finding 2: the constellation is held together by 9744 and PINNED by OUR "
        "AreaMeasureElem 9490's kept wiring) -- it leaves with the room, atomically; left "
        "byte-identical here."),
}

#: classes REACHED by other streams (excluded from this round's authoring)
REACHED_ELSEWHERE: Dict[str, str] = {
    "RbsWireInsulationType": "GROUP B ZB2_mepcat (viewer PASS, batch 17) -- our wire catalog",
    "RbsWireMaterialType": "GROUP B ZB2_mepcat",
    "RbsWireTemperatureRatingType": "GROUP B ZB2_mepcat",
    "RbsPipeScheduleType": "GROUP B ZB2_mepcat -- our piping catalog",
    "RbsPipeConnectionType": "GROUP B ZB2_mepcat",
    "RbsPipeMaterialType": "GROUP B ZB2_mepcat",
    "PipeSegment": "GROUP B ZB2_mepcat",
    "CategoryElem": "GROUP A ZA_deep (family-scoped remainder = curtain constellation, D_curtain)",
    "GStyleElem": "GROUP A ZA_deep (family-scoped remainder = curtain constellation)",
    "FontElem": "GROUP A ZA_deep (family-scoped remainder = curtain constellation)",
    "DimensionStyle": "GROUP A ZA_deep (family-scoped remainder)",
    "CalloutTag": "GROUP A ZA_deep (family-scoped remainder)",
    "InteriorElevAttributes": "GROUP A ZA_deep (family-scoped remainder)",
    "DBViewType": "curtain constellation (deletion stream D_curtain)",
    "Family": "curtain constellation (D_curtain)",
    "FamilySurrogate": "curtain constellation (D_curtain)",
    "CurveElem": "room constellation (deletion stream, blocked -> D_room after the wiring fix)",
    "LegendComponent": "type previews (2 curtain-owned in D_curtain; 2 owned by our residue types)",
    "LevelRoomPlan": "room constellation",
    "LinearDimString": "constraint-dimension group (deletion stream D_content)",
    "RoomElem": "GROUP B ZB8_content (identity) / room constellation deletion",
    "MaterialElem": "GROUP B ZB5_palette (surplus materials)",
    "ParamElemExternal": "GROUP B ZB1_defs", "ParamBinding": "GROUP B ZB1_defs",
    "ParamElemElectricalLoadClassification": "GROUP B ZB1_defs (the 6-per-class companions of our "
                                              "ZC_elec classifications -- id-wired both sides)",
    "ParamElemProject": "GROUP B ZB1_defs",
    "PenWidthTableElem": "GROUP B ZB3_pens", "SectionAttributes": "GROUP B ZB4_annot",
    "ViewportAttributes": "GROUP B ZB4_annot", "PropertySetElement": "GROUP B ZB5_palette",
    "ParameterFilterElement": "GROUP B ZB6_filters", "SunAnnotationElem": "GROUP B ZB7_machinery",
    "NumberingSchema": "GROUP B ZB7_machinery", "SlaveSymbolTrackerElem": "GROUP B ZB7_machinery",
    "WorksharingViewModeSettings": "GROUP B ZB7_machinery", "PrintSettings": "GROUP B ZB7_machinery",
    "Viewer": "GROUP B ZB7_machinery (the sheet's viewer 1457029)",
    "Viewport": "GROUP B ZB7_machinery (the sheet's viewports 1457030/1457043/1457044)",
    "RefPlane": "GROUP B ZB8_content", "SketchPlane": "GROUP B ZB8_content",
}

# ---------------------------------------------------------------------------
# format constants (public BuiltInParameter / BuiltInCategory enums --
# interoperability constants, not content)
# ---------------------------------------------------------------------------
#: LoadCaseElem category ids = the built-in load-case CATEGORY per load
#: category (an interface enum; [VERIFIED: DL1/-2005211 LL1/-2005212
#: WIND1/-2005213 SNOW1/-2005214 LR1/-2005215 ACC1/-2005216 TEMP1/-2005217
#: SEIS1/-2005218 in every US-template sample])
OST_LoadCasesDead = -2005211
OST_LoadCasesLive = -2005212
OST_LoadCasesWind = -2005213
OST_LoadCasesSnow = -2005214
OST_LoadCasesRoofLive = -2005215
OST_LoadCasesAccidental = -2005216
OST_LoadCasesTemperature = -2005217
OST_LoadCasesSeismic = -2005218
#: LoadCase / LoadNature name mirror parameters (AString params)
BIP_LOAD_CASE_NAME = -1015250
BIP_LOAD_NATURE_NAME = -1015254
#: colour-fill built-in FILL pattern id (the built-in solid fill token, an
#: interface constant carried by every corpus colour-scheme entry)
FILLPATTERN_SOLID = 3


# ===========================================================================
# 1. CENSUS MACHINERY (the residue of a parent, the frozen enums)
# ===========================================================================

def residue_of_parent(parent_report: str = DEFAULT_PARENT_REPORT) -> Dict[int, str]:
    """{slot: rung} of EVERY element already OURS in the parent -- the whole
    Y-ladder plus the parent's own cumulative report (ZA_deep.json)."""
    return RA.ladder_landed(extra_reports=[parent_report])


def derive_hvac_type_enums(samples: Sequence[str] = tuple(CORPUS_SAMPLES), *,
                           verbose: bool = True) -> dict:
    """Derive the two HVAC type ENUMERATIONS -- {m_eSpaceType: name} (125)
    and {m_eBuildingType: name} (33) -- from the corpus and ASSERT they are
    IDENTICAL in every sample (including the German-language file, whose
    schedule / load-nature names are localized but whose space-type names are
    NOT): they are the reader's fixed space- and building-type list, i.e. the
    PUBLIC gbXML / ASHRAE 90.1 space-type and building-type enumerations
    (interface constants).  ONLY the enum key + its canonical name are read;
    NO settings VALUE (density / setpoint / schedule) is read from any file --
    those are ours (:data:`SPACE_PROFILES`)."""
    from ..mutate import Document
    space: Dict[int, str] = {}
    build: Dict[int, str] = {}
    for i, s in enumerate(samples):
        d = Document.load(s)
        sp = {}
        bt = {}
        for e in d.ids_of_class("HVACLoadSpaceTypeElem"):
            v = d.value(e) or {}
            sp[int(v.get("m_eSpaceType", -1))] = str(v.get("m_name") or "")
        for e in d.ids_of_class("HVACLoadBuildingTypeElem"):
            v = d.value(e) or {}
            bt[int(v.get("m_eBuildingType", -1))] = str(v.get("m_name") or "")
        if i == 0:
            space, build = sp, bt
        else:
            if sp != space or bt != build:
                raise RuntimeError(f"HVAC type enum differs in {s} (not an interface constant?)")
        if verbose:
            log(f"   [enum] {s}: {len(sp)} space types, {len(bt)} building types -- identical")
    if sorted(space) != list(range(len(space))) or sorted(build) != list(range(len(build))):
        raise RuntimeError("HVAC type enum keys are not the dense 0..N-1 range expected")
    return {
        "generator": "rvt.genesis.residue_a2.derive_hvac_type_enums",
        "derived_from": list(samples),
        "note": ("The Revit-2026 HVAC space-type (125) and building-type (33) ENUMERATIONS "
                 "(m_eSpaceType / m_eBuildingType -> canonical name): IDENTICAL in every "
                 "sample incl. the German-language dach file (locale-independent identity) => "
                 "the reader's fixed type LIST = the public gbXML / ASHRAE 90.1 space- and "
                 "building-type enumerations (interface constants). Only keys + canonical names "
                 "are recorded: NO density / setpoint / schedule VALUE is read from any sample "
                 "-- those are OUR settings (residue_a2.SPACE_PROFILES / BUILDING_PROFILES)."),
        "space_types": {str(k): v for k, v in sorted(space.items())},
        "building_types": {str(k): v for k, v in sorted(build.items())},
    }


def load_hvac_type_enums(path: str = ENUMS_FILE, *, derive_if_missing: bool = True) -> dict:
    """Load the frozen HVAC enums (derive + freeze on first use)."""
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    if not derive_if_missing:
        raise FileNotFoundError(path)
    enums = derive_hvac_type_enums()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(enums, fh, indent=1)
    return enums


# ===========================================================================
# 2. OUR DATA -- the HVAC / energy standard
# ===========================================================================
# Every value below is a caller parameter of our own design standard,
# expressed as plain data.  Where a value is an engineering QUANTITY, the
# comment names the public source of the FACT it reflects (published
# code / standard ranges); the SELECTION, the classification of the
# space-type enum into our functional profiles, the naming and the assembled
# set are ours.  NO value is read from any Autodesk file.

#: OUR HVAC DAY-SCHEDULE library: (key, name, 24 hourly fractions).  A day
#: schedule is a 24-value load-fraction profile (hour 0..23); the fractions
#: are our design assumptions for a transit / institutional practice.
def _hours(spec: Dict[int, float]) -> List[float]:
    """{hour: fraction} run-length spec -> 24 fractions (a value applies
    from its hour until the next specified hour; hours are 0..23)."""
    out = [0.0] * 24
    keys = sorted(spec)
    for i, h0 in enumerate(keys):
        h1 = keys[i + 1] if i + 1 < len(keys) else 24
        for h in range(h0, h1):
            out[h] = float(spec[h0])
    return out


DAY_SCHEDULES: List[Dict[str, Any]] = [
    {"key": "off",            "name": gen("Off - 24 Hours"),                   "hours": _hours({0: 0.0})},
    {"key": "on24",           "name": gen("On - 24 Hours"),                    "hours": _hours({0: 1.0})},
    {"key": "half24",         "name": gen("On - 24 Hours (50 Percent)"),       "hours": _hours({0: 0.5})},
    {"key": "occ_office",     "name": gen("Occupancy - Office (8 AM to 6 PM)"),
     "hours": _hours({0: 0.0, 7: 0.1, 8: 0.7, 9: 0.9, 12: 0.5, 13: 0.9, 17: 0.5, 18: 0.1, 20: 0.0})},
    {"key": "occ_classroom",  "name": gen("Occupancy - Classroom (7 AM to 4 PM)"),
     "hours": _hours({0: 0.0, 7: 0.5, 8: 0.95, 12: 0.6, 13: 0.95, 15: 0.4, 16: 0.05, 18: 0.0})},
    {"key": "occ_assembly",   "name": gen("Occupancy - Assembly (Evening Peak)"),
     "hours": _hours({0: 0.0, 9: 0.1, 12: 0.3, 17: 0.5, 19: 1.0, 22: 0.4, 23: 0.0})},
    {"key": "occ_transit24",  "name": gen("Occupancy - Transit Facility (24 Hour, Commute Peaks)"),
     "hours": _hours({0: 0.15, 5: 0.4, 6: 0.9, 9: 0.5, 15: 0.6, 16: 1.0, 19: 0.5, 22: 0.2})},
    {"key": "occ_shop",       "name": gen("Occupancy - Maintenance Shop (Two Shifts 6 AM to 10 PM)"),
     "hours": _hours({0: 0.05, 6: 0.9, 12: 0.6, 13: 0.9, 14: 0.85, 20: 0.6, 22: 0.05})},
    {"key": "occ_warehouse",  "name": gen("Occupancy - Warehouse (7 AM to 5 PM)"),
     "hours": _hours({0: 0.0, 7: 0.8, 12: 0.4, 13: 0.8, 17: 0.0})},
    {"key": "occ_retail",     "name": gen("Occupancy - Retail (9 AM to 9 PM)"),
     "hours": _hours({0: 0.0, 9: 0.2, 11: 0.6, 13: 0.7, 17: 0.8, 20: 0.4, 21: 0.0})},
    {"key": "occ_dining",     "name": gen("Occupancy - Dining (Lunch and Dinner Peaks)"),
     "hours": _hours({0: 0.0, 7: 0.2, 9: 0.05, 11: 0.6, 12: 0.9, 14: 0.2, 17: 0.6, 18: 0.9, 21: 0.4, 22: 0.0})},
    {"key": "occ_health24",   "name": gen("Occupancy - Healthcare (24 Hour, Night Reduced)"),
     "hours": _hours({0: 0.4, 6: 0.6, 8: 1.0, 17: 0.7, 21: 0.4})},
    {"key": "occ_residential", "name": gen("Occupancy - Residential (Night Peak)"),
     "hours": _hours({0: 0.9, 7: 0.5, 9: 0.2, 16: 0.4, 18: 0.7, 22: 0.9})},
    {"key": "occ_recreation", "name": gen("Occupancy - Recreation (6 AM to 10 PM)"),
     "hours": _hours({0: 0.0, 6: 0.4, 8: 0.3, 12: 0.5, 16: 0.7, 17: 1.0, 20: 0.6, 22: 0.0})},
    {"key": "ltg_office",     "name": gen("Lighting - Office (6 AM to 11 PM)"),
     "hours": _hours({0: 0.05, 6: 0.3, 8: 0.9, 12: 0.8, 13: 0.9, 18: 0.5, 20: 0.3, 23: 0.05})},
    {"key": "ltg_transit24",  "name": gen("Lighting - Transit (24 Hour, 30 Percent Night Setback)"),
     "hours": _hours({0: 0.3, 5: 1.0, 22: 0.3})},
    {"key": "ltg_warehouse",  "name": gen("Lighting - Warehouse (6 AM to 6 PM)"),
     "hours": _hours({0: 0.05, 6: 0.9, 18: 0.05})},
    {"key": "ltg_exterior",   "name": gen("Lighting - Exterior (Dusk to Dawn)"),
     "hours": _hours({0: 1.0, 6: 0.0, 18: 1.0})},
    {"key": "ltg_egress",     "name": gen("Lighting - Egress and Emergency (Always On)"),
     "hours": _hours({0: 1.0})},
    {"key": "ltg_corridor",   "name": gen("Lighting - Corridor (24 Hour, Occupancy Setback)"),
     "hours": _hours({0: 0.5, 6: 1.0, 20: 0.5})},
    {"key": "ltg_retail",     "name": gen("Lighting - Retail (7 AM to 10 PM)"),
     "hours": _hours({0: 0.05, 7: 0.9, 22: 0.05})},
    {"key": "plug_office",    "name": gen("Plug Load - Office (Base plus Day Peak)"),
     "hours": _hours({0: 0.2, 7: 0.4, 8: 0.9, 12: 0.8, 13: 0.9, 17: 0.5, 19: 0.3, 22: 0.2})},
    {"key": "plug_it24",      "name": gen("Plug Load - IT and Data (24 Hour Flat)"),
     "hours": _hours({0: 1.0})},
    {"key": "eq_kitchen",     "name": gen("Equipment - Kitchen (Meal Peaks)"),
     "hours": _hours({0: 0.1, 5: 0.4, 6: 0.6, 10: 0.9, 14: 0.4, 16: 0.9, 20: 0.3, 22: 0.1})},
    {"key": "eq_shop",        "name": gen("Equipment - Shop (Two Shifts)"),
     "hours": _hours({0: 0.05, 6: 0.8, 12: 0.5, 13: 0.8, 20: 0.4, 22: 0.05})},
    {"key": "eq_charging",    "name": gen("Equipment - Bus and EV Charging (Overnight)"),
     "hours": _hours({0: 1.0, 5: 0.3, 8: 0.1, 20: 0.6, 22: 1.0})},
    {"key": "hvac_optimum",   "name": gen("HVAC Availability - Optimum Start (5 AM to 7 PM)"),
     "hours": _hours({0: 0.0, 5: 1.0, 19: 0.0})},
]

#: metabolic rate PROFILES (per-person sensible / latent heat gain, Btu/h)
#: [FACT: representative rates of heat gain from occupants, ASHRAE
#: Fundamentals ch.18 tab.1 -- seated quiet 245/105, moderately active
#: office work 250/200, standing / light work walking 250/200, light bench
#: work 275/475, heavy work 580/870, athletics 710/1090]
ACTIVITY: Dict[str, Tuple[float, float]] = {
    "resting":     (240.0, 105.0),
    "seated":      (245.0, 155.0),
    "office":      (250.0, 200.0),
    "standing":    (250.0, 200.0),
    "eating":      (275.0, 275.0),
    "light_bench": (275.0, 475.0),
    "heavy":       (580.0, 870.0),
    "athletic":    (710.0, 1090.0),
    "none":        (0.0, 0.0),
}

#: OUR SPACE-TYPE VALUE PROFILES.  A profile = our design values for a
#: functional space category; each of the 125 space-type slots is mapped
#: to one by :data:`SPACE_TYPE_PROFILE` (OUR classification of the public
#: enum).  Quantities: ft2_per_person (None = unoccupied), lighting /
#: equipment W/ft2, outdoor air cfm/person + cfm/ft2, occupied cooling /
#: heating setpoints degF, activity key, plenum-lighting fraction, RH
#: setpoints, infiltration cfm/ft2, carpet, and the three schedule ROLE keys
#: (occupancy / lighting / power) into :data:`DAY_SCHEDULES`.
#: [FACTS informing the magnitudes: interior lighting power densities in
#: the ASHRAE 90.1-2019 space-by-space range; combined outdoor-air rates of
#: the ASHRAE 62.1-2019 ventilation-rate procedure; occupant heat gains
#: above.  The chosen values and the classification are OURS.]
def _prof(occ, lpd, epd, oa_pp, oa_a, clg, htg, act, occ_s, ltg_s, pwr_s, *,
          plenum_frac=0.10, carpet=False, dehum=0.60, humid=0.0, infil=0.05,
          is_plenum=False):
    return {"ft2_per_person": occ, "lpd": lpd, "epd": epd, "oa_person": oa_pp,
            "oa_area": oa_a, "clg_f": clg, "htg_f": htg, "activity": act,
            "occ_sched": occ_s, "ltg_sched": ltg_s, "pwr_sched": pwr_s,
            "plenum_frac": plenum_frac, "carpet": carpet, "dehum": dehum,
            "humid": humid, "infiltration": infil, "is_plenum": is_plenum}


SPACE_PROFILES: Dict[str, dict] = {
    "storage_active":    _prof(300, 0.40, 0.20, 0.0, 0.12, 78, 62, "standing",
                               "occ_warehouse", "ltg_warehouse", "occ_warehouse"),
    "storage_inactive":  _prof(None, 0.30, 0.10, 0.0, 0.06, 80, 60, "none",
                               "off", "ltg_warehouse", "off"),
    "warehouse_bulky":   _prof(500, 0.35, 0.20, 0.0, 0.06, 80, 60, "heavy",
                               "occ_warehouse", "ltg_warehouse", "occ_warehouse"),
    "transit_terminal":  _prof(33, 0.60, 0.50, 7.5, 0.06, 75, 68, "standing",
                               "occ_transit24", "ltg_transit24", "occ_transit24"),
    "lobby":             _prof(100, 0.85, 0.30, 5.0, 0.06, 75, 70, "standing",
                               "occ_office", "ltg_office", "plug_office"),
    "assembly":          _prof(15, 0.80, 0.30, 5.0, 0.06, 74, 70, "seated",
                               "occ_assembly", "occ_assembly", "occ_assembly"),
    "office_enclosed":   _prof(200, 0.65, 1.00, 5.0, 0.06, 75, 70, "office",
                               "occ_office", "ltg_office", "plug_office", carpet=True),
    "office_open":       _prof(150, 0.60, 1.50, 5.0, 0.06, 75, 70, "office",
                               "occ_office", "ltg_office", "plug_office", carpet=True),
    "conference":        _prof(20, 0.95, 1.00, 5.0, 0.06, 75, 70, "office",
                               "occ_office", "ltg_office", "plug_office", carpet=True),
    "classroom":         _prof(40, 0.85, 1.00, 10.0, 0.12, 75, 70, "office",
                               "occ_classroom", "occ_classroom", "occ_classroom"),
    "laboratory":        _prof(100, 1.20, 8.00, 10.0, 0.18, 74, 70, "light_bench",
                               "occ_office", "ltg_office", "plug_it24"),
    "sales_general":     _prof(67, 1.05, 0.50, 7.5, 0.12, 75, 70, "standing",
                               "occ_retail", "ltg_retail", "occ_retail"),
    "sales_service":     _prof(100, 0.90, 0.50, 7.5, 0.12, 75, 70, "standing",
                               "occ_retail", "ltg_retail", "occ_retail"),
    "library_reading":   _prof(100, 0.90, 0.30, 5.0, 0.12, 75, 70, "seated",
                               "occ_office", "ltg_office", "plug_office", carpet=True),
    "library_stacks":    _prof(100, 1.10, 0.20, 5.0, 0.12, 75, 70, "standing",
                               "occ_office", "ltg_office", "off"),
    "corridor":          _prof(None, 0.50, 0.10, 0.0, 0.06, 76, 68, "none",
                               "off", "ltg_corridor", "off"),
    "stair":             _prof(None, 0.50, 0.00, 0.0, 0.06, 78, 65, "none",
                               "off", "ltg_corridor", "off"),
    "restroom":          _prof(100, 0.65, 0.20, 0.0, 0.06, 76, 70, "standing",
                               "occ_office", "ltg_office", "off"),
    "locker_room":       _prof(40, 0.60, 0.20, 20.0, 0.06, 76, 70, "standing",
                               "occ_recreation", "ltg_office", "off"),
    "gym_court":         _prof(40, 0.85, 0.30, 20.0, 0.06, 74, 68, "athletic",
                               "occ_recreation", "occ_recreation", "occ_recreation"),
    "lounge":            _prof(40, 0.75, 0.50, 5.0, 0.06, 75, 70, "seated",
                               "occ_office", "ltg_office", "plug_office"),
    "dining":            _prof(15, 0.65, 0.50, 7.5, 0.18, 75, 70, "eating",
                               "occ_dining", "occ_dining", "occ_dining"),
    "kitchen":           _prof(100, 1.05, 15.00, 7.5, 0.12, 78, 68, "light_bench",
                               "occ_dining", "occ_dining", "eq_kitchen"),
    "residential_living": _prof(200, 0.50, 0.50, 5.0, 0.06, 75, 70, "seated",
                               "occ_residential", "occ_residential", "occ_residential", carpet=True),
    "residential_sleep": _prof(250, 0.30, 0.30, 5.0, 0.06, 75, 70, "resting",
                               "occ_residential", "occ_residential", "occ_residential", carpet=True),
    "confinement":       _prof(100, 0.75, 0.30, 5.0, 0.06, 78, 68, "resting",
                               "on24", "ltg_corridor", "half24"),
    "healthcare_treat":  _prof(50, 1.10, 2.00, 15.0, 0.18, 74, 70, "standing",
                               "occ_health24", "on24", "occ_health24"),
    "healthcare_patient": _prof(100, 0.70, 1.50, 25.0, 0.12, 74, 70, "resting",
                               "on24", "occ_health24", "half24"),
    "healthcare_support": _prof(100, 0.90, 1.00, 5.0, 0.12, 74, 70, "office",
                               "occ_health24", "ltg_office", "occ_health24"),
    "industrial_high":   _prof(200, 0.90, 5.00, 10.0, 0.18, 78, 65, "heavy",
                               "occ_shop", "occ_shop", "eq_shop"),
    "industrial_low":    _prof(100, 1.05, 3.00, 10.0, 0.18, 78, 65, "light_bench",
                               "occ_shop", "occ_shop", "eq_shop"),
    "workshop":          _prof(100, 1.15, 3.00, 10.0, 0.18, 78, 65, "light_bench",
                               "occ_shop", "occ_shop", "eq_shop"),
    "vehicle_charging":  _prof(300, 0.70, 8.00, 0.0, 0.12, 80, 60, "light_bench",
                               "occ_shop", "ltg_transit24", "eq_charging"),
    "laundry":           _prof(100, 0.60, 8.00, 10.0, 0.12, 78, 68, "light_bench",
                               "occ_office", "ltg_office", "eq_shop"),
    "mech_elec":         _prof(None, 0.45, 0.50, 0.0, 0.00, 85, 55, "none",
                               "off", "ltg_corridor", "on24", infil=0.10),
    "parking":           _prof(None, 0.15, 0.05, 0.0, 0.75, 90, 45, "none",
                               "off", "ltg_transit24", "off", infil=0.50, dehum=0.0),
    "plenum":            _prof(None, 0.00, 0.00, 0.0, 0.00, 78, 62, "none",
                               "off", "off", "off", plenum_frac=0.0, is_plenum=True, dehum=0.0),
}

#: OUR CLASSIFICATION of the 125-value space-type enum into our profiles
#: (m_eSpaceType -> profile key).  The enum is the reader's fixed list (the
#: public gbXML / ASHRAE space-type enumeration, ``hvac_type_enums.json``);
#: this mapping is our engineering judgement.
SPACE_TYPE_PROFILE: Dict[int, str] = {
    0: "storage_active", 1: "storage_active", 2: "transit_terminal", 3: "transit_terminal",
    4: "lobby", 5: "lobby",
    6: "assembly", 7: "assembly", 8: "assembly", 9: "assembly", 10: "assembly",
    11: "assembly", 12: "assembly", 13: "assembly", 14: "assembly", 15: "assembly",
    16: "assembly", 17: "lobby", 18: "office_open", 19: "sales_service", 20: "library_stacks",
    21: "classroom", 22: "classroom", 23: "confinement", 24: "confinement", 25: "conference",
    26: "corridor", 27: "corridor", 28: "corridor", 29: "gym_court", 30: "assembly",
    31: "sales_general", 32: "industrial_low", 33: "dining", 34: "dining", 35: "dining",
    36: "dining", 37: "dining", 38: "dining", 39: "dining", 40: "dining",
    41: "residential_sleep", 42: "library_reading",
    43: "locker_room", 44: "locker_room", 45: "locker_room", 46: "locker_room",
    47: "locker_room", 48: "mech_elec", 49: "lobby", 50: "healthcare_treat", 51: "mech_elec",
    52: "healthcare_treat", 53: "gym_court", 54: "gym_court", 55: "assembly", 56: "assembly",
    57: "storage_active", 58: "sales_general", 59: "industrial_low", 60: "kitchen",
    61: "workshop", 62: "industrial_high", 63: "industrial_low", 64: "assembly",
    65: "healthcare_patient", 66: "storage_active", 67: "healthcare_treat", 68: "conference",
    69: "storage_inactive", 70: "office_enclosed", 71: "laboratory", 72: "laundry",
    73: "laundry", 74: "library_reading", 75: "residential_living", 76: "residential_living",
    77: "residential_living", 78: "lobby", 79: "lobby", 80: "lobby", 81: "lobby", 82: "lobby",
    83: "lobby", 84: "lobby", 85: "lounge", 86: "sales_general", 87: "sales_general",
    88: "warehouse_bulky", 89: "sales_general", 90: "storage_inactive",
    91: "healthcare_support", 92: "office_enclosed", 93: "office_open",
    94: "storage_inactive", 95: "healthcare_treat", 96: "gym_court", 97: "parking",
    98: "parking", 99: "healthcare_patient", 100: "sales_service", 101: "healthcare_support",
    102: "healthcare_support", 103: "gym_court", 104: "plenum", 105: "laboratory",
    106: "lounge", 107: "library_reading", 108: "transit_terminal", 109: "lobby",
    110: "lobby", 111: "healthcare_patient", 112: "workshop", 113: "restroom",
    114: "gym_court", 115: "residential_sleep", 116: "industrial_low", 117: "sales_general",
    118: "library_stacks", 119: "stair", 120: "stair", 121: "sales_general",
    122: "transit_terminal", 123: "workshop", 124: "assembly",
}

#: OUR BUILDING-TYPE VALUE PROFILES (building-area lighting power density
#: W/ft2, equipment power density W/ft2, ft2/person, outdoor air cfm/person
#: + cfm/ft2, occupied cooling / heating setpoints degF, unoccupied cooling
#: setpoint degF, equipment operating window, schedule roles).  [FACTS
#: informing the magnitudes: whole-building lighting power densities in
#: the ASHRAE 90.1-2019 building-area-method range; ventilation as above.]
def _bprof(lpd, epd, occ, oa_pp, oa_a, clg, htg, unocc_clg, start, end,
           occ_s, ltg_s, pwr_s, *, plenum_frac=0.10, carpet=False, dehum=0.60,
           humid=0.0, infil=0.05):
    return {"lpd": lpd, "epd": epd, "ft2_per_person": occ, "oa_person": oa_pp,
            "oa_area": oa_a, "clg_f": clg, "htg_f": htg, "unocc_clg_f": unocc_clg,
            "eq_start": start, "eq_end": end, "occ_sched": occ_s, "ltg_sched": ltg_s,
            "pwr_sched": pwr_s, "plenum_frac": plenum_frac, "carpet": carpet,
            "dehum": dehum, "humid": humid, "infiltration": infil, "activity": "office"}


BUILDING_PROFILES: Dict[str, dict] = {
    "office":        _bprof(0.75, 1.00, 200, 5.0, 0.06, 75, 70, 85, "07:00", "19:00",
                            "occ_office", "ltg_office", "plug_office", carpet=True),
    "school":        _bprof(0.72, 0.80, 60, 10.0, 0.12, 75, 70, 85, "07:00", "17:00",
                            "occ_classroom", "occ_classroom", "occ_classroom"),
    "healthcare":    _bprof(0.96, 1.50, 100, 15.0, 0.12, 74, 70, 82, "00:00", "24:00",
                            "occ_health24", "on24", "occ_health24"),
    "retail":        _bprof(0.90, 0.50, 67, 7.5, 0.12, 75, 70, 85, "08:00", "22:00",
                            "occ_retail", "ltg_retail", "occ_retail"),
    "hospitality":   _bprof(0.75, 0.50, 250, 5.0, 0.06, 75, 70, 82, "00:00", "24:00",
                            "occ_residential", "ltg_corridor", "half24", carpet=True),
    "residential":   _bprof(0.50, 0.50, 250, 5.0, 0.06, 75, 70, 82, "00:00", "24:00",
                            "occ_residential", "occ_residential", "occ_residential", carpet=True),
    "industrial":    _bprof(0.90, 4.00, 150, 10.0, 0.18, 78, 65, 90, "06:00", "22:00",
                            "occ_shop", "occ_shop", "eq_shop"),
    "warehouse":     _bprof(0.45, 0.20, 500, 0.0, 0.06, 80, 60, 90, "06:00", "18:00",
                            "occ_warehouse", "ltg_warehouse", "occ_warehouse"),
    "parking":       _bprof(0.11, 0.05, None, 0.0, 0.75, 90, 45, 95, "00:00", "24:00",
                            "off", "ltg_transit24", "off", infil=0.50, dehum=0.0),
    "assembly":      _bprof(0.80, 0.30, 15, 5.0, 0.06, 74, 70, 82, "08:00", "23:00",
                            "occ_assembly", "occ_assembly", "occ_assembly"),
    "civic":         _bprof(0.79, 0.80, 200, 5.0, 0.06, 75, 70, 85, "07:00", "18:00",
                            "occ_office", "ltg_office", "plug_office"),
    "civic_24h":     _bprof(0.79, 0.80, 200, 5.0, 0.06, 75, 70, 78, "00:00", "24:00",
                            "occ_health24", "ltg_corridor", "half24"),
    "institutional": _bprof(0.80, 0.50, 100, 5.0, 0.12, 75, 70, 82, "08:00", "20:00",
                            "occ_office", "ltg_office", "plug_office"),
    "dining":        _bprof(0.85, 4.00, 15, 7.5, 0.18, 75, 70, 82, "06:00", "24:00",
                            "occ_dining", "occ_dining", "eq_kitchen"),
    "recreation":    _bprof(0.75, 0.30, 40, 20.0, 0.06, 74, 68, 82, "06:00", "22:00",
                            "occ_recreation", "occ_recreation", "occ_recreation"),
    "transit":       _bprof(0.65, 1.50, 33, 7.5, 0.06, 75, 68, 78, "00:00", "24:00",
                            "occ_transit24", "ltg_transit24", "eq_charging"),
    "shop":          _bprof(0.90, 3.00, 100, 10.0, 0.18, 78, 65, 90, "06:00", "22:00",
                            "occ_shop", "occ_shop", "eq_shop"),
}

#: OUR CLASSIFICATION of the 33-value building-type enum into our
#: building profiles (m_eBuildingType -> profile key).
BUILDING_TYPE_PROFILE: Dict[int, str] = {
    0: "shop", 1: "assembly", 2: "civic", 3: "dining", 4: "dining", 5: "dining",
    6: "residential", 7: "recreation", 8: "civic_24h", 9: "recreation", 10: "healthcare",
    11: "hospitality", 12: "institutional", 13: "industrial", 14: "hospitality",
    15: "assembly", 16: "residential", 17: "institutional", 18: "office",
    19: "parking", 20: "civic_24h", 21: "assembly", 22: "civic_24h", 23: "civic",
    24: "assembly", 25: "retail", 26: "school", 27: "residential", 28: "recreation",
    29: "civic", 30: "transit", 31: "warehouse", 32: "shop",
}


# ===========================================================================
# 3. OUR DATA -- the electrical load / demand-factor standard (extends
#    house_standard.LOAD_CLASSIFICATIONS / DEMAND_FACTORS to the base's count)
# ===========================================================================
#: demand-factor RULE codes (verified on the corpus, house_standard F-HS-3)
RULE_CONSTANT, RULE_COUNT, RULE_LOAD = hs.RULE_CONSTANT, hs.RULE_COUNT, hs.RULE_LOAD

#: OUR demand-factor RULE library (key -> spec).  The RULES are NEC facts
#: (the code sections cited); the names, the selection and the assembled set
#: are ours.  Reuses house_standard.DEMAND_FACTORS and extends it.
DEMAND_RULES: Dict[str, dict] = {d["key"]: d for d in hs.DEMAND_FACTORS}
DEMAND_RULES.update({
    "welder_group": {
        "key": "welder_group", "name": gen("Welder Group Demand (NEC 630.12)"),
        "rule": RULE_COUNT,
        "rows": [(0.0, 1.0, 1.0), (1.0, 2.0, 1.0), (2.0, 3.0, 0.85), (3.0, 4.0, 0.70),
                 (4.0, 1e30, 0.60)],
        "source": "NEC 630.12(B): largest welder 100 %, second 100 %, third 85 %, fourth "
                  "70 %, all others 60 % [count-range rows, largest-first ordering]"},
    "lighting_dwelling": {
        "key": "lighting_dwelling", "name": gen("Dwelling Lighting Demand (NEC 220.42)"),
        "rule": RULE_LOAD,
        "rows": [(0.0, kva(3.0), 1.0), (kva(3.0), kva(120.0), 0.35), (kva(120.0), 1e30, 0.25)],
        "source": "NEC Table 220.42 dwelling units: first 3 kVA at 100 %, 3-120 kVA at 35 %, "
                  "remainder at 25 %"},
    "noncoincident": {
        "key": "noncoincident", "name": gen("Non-Coincident HVAC (NEC 220.60)"),
        "rule": RULE_CONSTANT, "rows": [(0.0, 1e30, 1.0)],
        "source": "NEC 220.60: only the larger of the noncoincident heating / cooling loads is "
                  "carried -- applied by our schedule policy; the factor itself is unity"},
    "fire_pump": {
        "key": "fire_pump", "name": gen("Fire Pump (NEC 695, No Demand)"),
        "rule": RULE_CONSTANT, "rows": [(0.0, 1e30, 1.0)],
        "source": "NEC 695: fire-pump supply sized for locked-rotor conditions -- no demand "
                  "reduction ever applied (our policy: unity, sized separately)"},
    "sign_outlet": {
        "key": "sign_outlet", "name": gen("Sign and Outline Lighting (NEC 220.14F)"),
        "rule": RULE_CONSTANT, "rows": [(0.0, 1e30, 1.0)],
        "source": "NEC 220.14(F): 1,200 VA minimum per required sign circuit, no demand factor"},
    "track_lighting": {
        "key": "track_lighting", "name": gen("Track Lighting (NEC 220.46B)"),
        "rule": RULE_CONSTANT, "rows": [(0.0, 1e30, 1.0)],
        "source": "NEC 220.46(B): 150 VA per 600 mm of lighting track -- computed as the "
                  "connected basis, no further demand factor (our policy)"},
    "crane_group": {
        "key": "crane_group", "name": gen("Crane and Hoist Group (NEC 610.14E)"),
        "rule": RULE_COUNT,
        "rows": [(0.0, 1.0, 1.0), (1.0, 2.0, 0.75), (2.0, 3.0, 0.70), (3.0, 4.0, 0.65),
                 (4.0, 1e30, 0.60)],
        "source": "NEC 610.14(E): two motors 75 %, three 70 %, four+ 65 % of their sum "
                  "[count-range approximation of the group factor -- our policy applies the "
                  "group factor manually where exactness matters]"},
    "elevator_group": {
        "key": "elevator_group", "name": gen("Elevator Group (NEC 620.14)"),
        "rule": RULE_COUNT,
        "rows": [(0.0, 1.0, 1.0), (1.0, 2.0, 0.95), (2.0, 3.0, 0.90), (3.0, 4.0, 0.85),
                 (4.0, 5.0, 0.82), (5.0, 1e30, 0.79)],
        "source": "NEC Table 620.14: elevator group demand 1 -> 1.00, 2 -> 0.95, 3 -> 0.90, "
                  "4 -> 0.85, 5 -> 0.82, 6+ -> 0.79 [count-range encoding of the group table]"},
    "existing_recalc": {
        "key": "existing_recalc", "name": gen("Existing Load Determination (NEC 220.87)"),
        "rule": RULE_CONSTANT, "rows": [(0.0, 1e30, 1.25)],
        "source": "NEC 220.87: existing peak demand (metered) times 125 % for load additions"},
})

#: OUR LOAD-CLASSIFICATION library.  ``role`` = the reader's reserved
#: signature slot the entry occupies (motor / other / spare -- exactly one
#: of each per project [VERIFIED 6/6 samples]) or None for a regular class.
#: ``space_class`` = the m_spaceLoadClass enum (1 lighting / 2 power / 0
#: none) [decoded from rme, house_standard F-HS-4].  ``rule`` -> DEMAND_RULES.
LOAD_CLASS_LIBRARY: List[dict] = [
    # reserved roles ----------------------------------------------------------
    {"name": gen("Motor Loads"), "rule": "motor", "space_class": 0, "role": "motor",
     "signature": 1, "abbrev": "MTR"},
    {"name": gen("Miscellaneous Loads"), "rule": "no_diversity", "space_class": 0, "role": "other",
     "signature": 2, "abbrev": "MISC"},
    {"name": gen("Spare Capacity"), "rule": "no_diversity", "space_class": 0, "role": "spare",
     "signature": 3, "abbrev": "SPARE"},
    # regular classifications (ours) ----------------------------------------
    {"name": gen("Lighting - Interior"), "rule": "continuous125", "space_class": 1,
     "role": None, "signature": 0, "abbrev": "LTG"},
    {"name": gen("Lighting - Emergency"), "rule": "continuous125", "space_class": 1,
     "role": None, "signature": 0, "abbrev": "EM"},
    {"name": gen("Lighting - Exterior"), "rule": "continuous125", "space_class": 1,
     "role": None, "signature": 0, "abbrev": "EXT"},
    {"name": gen("Receptacle - General"), "rule": "receptacle", "space_class": 2,
     "role": None, "signature": 0, "abbrev": "RECP"},
    {"name": gen("Receptacle - Dedicated Equipment"), "rule": "no_diversity", "space_class": 2,
     "role": None, "signature": 0, "abbrev": "DED"},
    {"name": gen("Data and IT Equipment"), "rule": "continuous125", "space_class": 2,
     "role": None, "signature": 0, "abbrev": "IT"},
    {"name": gen("HVAC - Cooling"), "rule": "no_diversity", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "CLG"},
    {"name": gen("HVAC - Heating"), "rule": "no_diversity", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "HTG"},
    {"name": gen("HVAC - Fans and Ventilation"), "rule": "continuous125", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "FAN"},
    {"name": gen("Kitchen Equipment"), "rule": "kitchen", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "KIT"},
    {"name": gen("Elevator and Escalator"), "rule": "no_diversity", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "ELEV"},
    {"name": gen("EV Charging"), "rule": "continuous125", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "EV"},
    {"name": gen("Bus Charging Equipment"), "rule": "continuous125", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "BUS"},
    {"name": gen("Shop and Maintenance Equipment"), "rule": "no_diversity", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "SHOP"},
    {"name": gen("Life Safety and Signal"), "rule": "no_diversity", "space_class": 0,
     "role": None, "signature": 0, "abbrev": "LS"},
]
#: extra demand-rule keys for demand-factor slots NO classification references
DEMAND_EXTRAS: List[str] = ["welder_group", "lighting_dwelling", "noncoincident", "fire_pump",
                            "sign_outlet", "track_lighting", "crane_group", "elevator_group",
                            "existing_recalc"]

#: the reader's reserved role -> our library entry (m_signitureType decides)
_ROLE_BY_SIGNATURE = {1: "motor", 2: "other", 3: "spare"}


# ===========================================================================
# 4. OUR DATA -- structural load standard, area report, colour schemes,
#    browser organizations, sheet identity, welded-wire fabric
# ===========================================================================
#: OUR load NATURES: names ours; the parenthesised symbols are the industry
#: standard load-category symbols (ASCE 7 load combinations) -- FACT.
#: category id -> our nature name (the case's category enum decides which
#: nature its nature slot carries, so the case <-> nature web stays sound).
LOAD_NATURE_BY_CATEGORY: Dict[int, str] = {
    OST_LoadCasesDead:        gen("Dead (D)"),
    OST_LoadCasesLive:        gen("Live (L)"),
    OST_LoadCasesWind:        gen("Wind (W)"),
    OST_LoadCasesSnow:        gen("Snow (S)"),
    OST_LoadCasesRoofLive:    gen("Roof Live (Lr)"),
    OST_LoadCasesAccidental:  gen("Accidental (Ax)"),
    OST_LoadCasesTemperature: gen("Thermal (T)"),
    OST_LoadCasesSeismic:     gen("Seismic (E)"),
}
#: OUR load CASES per category (name; number assigned by our order below)
LOAD_CASE_BY_CATEGORY: Dict[int, str] = {
    OST_LoadCasesDead:        gen("D-1 Self Weight and Superimposed Dead"),
    OST_LoadCasesLive:        gen("L-1 Occupancy Live"),
    OST_LoadCasesWind:        gen("W-1 Wind (Primary Direction)"),
    OST_LoadCasesSnow:        gen("S-1 Balanced Snow"),
    OST_LoadCasesRoofLive:    gen("Lr-1 Roof Live"),
    OST_LoadCasesAccidental:  gen("Ax-1 Vehicle Impact"),
    OST_LoadCasesTemperature: gen("T-1 Thermal Range"),
    OST_LoadCasesSeismic:     gen("E-1 Seismic (Primary Direction)"),
}
LOAD_CASE_ORDER = [OST_LoadCasesDead, OST_LoadCasesLive, OST_LoadCasesRoofLive,
                   OST_LoadCasesSnow, OST_LoadCasesWind, OST_LoadCasesSeismic,
                   OST_LoadCasesAccidental, OST_LoadCasesTemperature]

#: OUR area-report drafting settings (the tool's own text / prefixes /
#: sizes -- a document setting; the unit-format machinery is the slot's)
AREA_REPORT_SETTINGS = {
    "name": "default",                       # the settings-set name token
    "prefix_arc_sector": "R",                # our sector prefix
    "prefix_triangle": "T",                  # our triangle prefix
    "font_size_mm": (3.0, 2.0),              # (annotation, tag) heights
}

#: OUR colour-fill palette (muted, print-safe) + the department vocabulary a
#: department scheme carries (our room / space programme vocabulary)
COLOR_FILL_PALETTE: List[int] = [
    rgb(190, 220, 250), rgb(200, 235, 200), rgb(250, 225, 190), rgb(235, 200, 200),
    rgb(220, 210, 245), rgb(245, 240, 200), rgb(210, 235, 235), rgb(240, 215, 235),
    rgb(215, 215, 215), rgb(230, 245, 220),
]
DEPARTMENT_VOCABULARY: List[str] = [
    "Operations", "Vehicle Maintenance", "Administration", "Storage", "Building Services",
    "Vertical Circulation", "Electrical / IT", "Public / Passenger",
]
AREA_RANGES_FT2: List[Tuple[float, float]] = [   # our area-range legend breakpoints (ft2)
    (0.0, 100.0), (100.0, 250.0), (250.0, 500.0), (500.0, 1000.0), (1000.0, 1e30),
]
#: role words for a colour scheme's parameter (BuiltInParameter -> phrase)
_CFS_PARAM_WORD = {
    -1006900: "by Name", -1006907: "by Department", -1006902: "by Area",
    -1012701: "by Area Type", -1013405: "by System", -1140213: "by System",
    -1155116: "by Space Type", -1114300: "by Load Classification",
}
_CFS_CATEGORY_WORD = {
    -2000160: "Rooms", -2003200: "Areas", -2008000: "Ducts", -2008044: "Piping",
    -2003600: "Spaces", -2008107: "Electrical", -2001001: "Zones",
}

#: OUR extra project-browser organizations (5 -- the sample's surplus set,
#: which our house set deliberately does not reproduce: settings.default_
#: browser_organizations).  Built-in parameter ids are interface constants.
BROWSER_ORGANIZATIONS_EXTRA: List[dict] = [
    {"name": gen("Views - Level"), "type": "views",
     "folders": ["BIP_VIEW_ASSOCIATED_LEVEL"], "sort": "BIP_VIEW_NAME"},
    {"name": gen("Views - Family and Type"), "type": "views",
     "folders": ["BIP_VIEW_FAMILY_AND_TYPE", "BIP_VIEW_DISCIPLINE"], "sort": "BIP_VIEW_NAME"},
    {"name": gen("Sheets - Series (1 Character)"), "type": "sheets",
     "folders": [{"param": "BIP_SHEET_NUMBER", "chars": 1}], "sort": "BIP_SHEET_NUMBER"},
    {"name": gen("Sheets - Issue Date"), "type": "sheets",
     "folders": ["BIP_SHEET_ISSUE_DATE"], "sort": "BIP_SHEET_NUMBER"},
    {"name": gen("Sheets - Name"), "type": "sheets",
     "folders": ["BIP_SHEET_NAME"], "sort": "BIP_SHEET_NUMBER"},
]

#: OUR sheet identity block (the drafting/sheet view constellation we ADOPT:
#: DBViewDrafting 1457028 is the K4 lineage's sheet 'S101 - Framing Plans',
#: on whose drawing OUR two plan views are placed).  Deterministic tokens.
SHEET_IDENTITY = {
    "view_name": gen("Overall Plans"),
    "sheet_number": "GEN-101",
    "date": "01/01/26",
    "issue_date": "01/01/26",
    "drawn_by": "GEN",
    "checked_by": "GEN",
    "designed_by": "GEN",
    "approved_by": "GEN",
}

#: OUR welded-wire fabric.  DESIGNATIONS + wire geometry are FACTS of
#: ASTM A1064 (W-number = cross-section in 0.01 in2; W2.9 dia 0.192 in,
#: W4.0 dia 0.226 in); the sheet make-up (length / width / laps /
#: overhangs) is our detailing convention.
FABRIC_WIRE = {"name": gen("W2.9"), "diameter_in": 0.192,
               "bend_diameter_factor": 4.0,          # ACI 318 min inside bend = 4 db (D6 and smaller)
               "source": "ASTM A1064 W2.9 (0.029 in2, 0.192 in dia)"}
FABRIC_SHEET = {
    "name": gen("WWF 6x6-W2.9xW2.9"),
    "spacing_in": 6.0,                                # both ways
    "overall_length_ft": 20.0, "overall_width_ft": 8.0,
    "overhang_in": 3.0,                               # half a spacing at each side/end
    "lap_splice_in": 12.0,                            # >= one spacing + 6 in (our WWR lap policy)
    "mass_kg": 30.5,                                  # 42 lb/100 ft2 * 160 ft2 = 67.2 lb
    "source": "ASTM A1064 6x6-W2.9xW2.9 (42 lb / 100 ft2); sheet 8 ft x 20 ft ours",
}

#: OUR generic system-family types for the two residue slots (layers use
#: OUR palette materials, looked up by name in the parent)
WALL_TYPE = {"name": gen("Wall - Interior Partition 121mm"),
             "layers": [("finish2", 16.0, gen("Gypsum Wall Board")),
                        ("structure", 89.0, gen("Metal Stud Framing")),
                        ("finish2", 16.0, gen("Gypsum Wall Board"))],
             "function": 0}                            # 0 = interior
FLOOR_TYPE = {"name": gen("Floor - Concrete Slab 150mm"),
              "layers": [("structure", 150.0, gen("Concrete, Cast-in-Place"))]}


# ===========================================================================
# 5. CONSTRUCTORS -- the HVAC / energy web
# ===========================================================================

def _cell_pattern_helper():
    """The ``CellList{PatternHelper}`` most settings-class residue slots
    carry (kept from the slot in-place; used by the pure constructors when
    a slot has one)."""
    return _ptr("CellList", {"m_cells": [
        _ptr("PatternHelper", {"m_PatternPositionMap": [], "m_substituteFaceMap": []})]})


#: sentinel: "no slot context" -> the constructor emits the standard cell
#: helper.  When a rung passes the SLOT's own cell list (which may be
#: None), that value is kept VERBATIM -- in place, the slot's cell
#: apparatus is machinery, and a null cell list stays null.
_NO_SLOT = object()


def _cells_of(cells) -> Any:
    """Resolve a ``cells`` argument: the slot's own value verbatim (None
    included), or the standard PatternHelper cell list when no slot."""
    if cells is _NO_SLOT:
        return _cell_pattern_helper()
    return _deep(cells)


def hvac_day_schedule(name: str, fractions: Sequence[float], *, elem_id: int = 0,
                      cells=_NO_SLOT, design_option: int = NO_DESIGN_OPTION) -> Obj:
    """OUR ``HVACLoadScheduleElem`` (a 24-hour load-fraction DAY schedule):
    the name + the 24 hourly fractions are ours (:data:`DAY_SCHEDULES`).
    ``cells`` = the slot's cell apparatus (kept VERBATIM in place; None
    stays None)."""
    if len(fractions) != 24:
        raise ValueError("a day schedule needs exactly 24 hourly fractions")
    obj = blank_object("HVACLoadScheduleElem")
    element_defaults(obj, int(elem_id), design_option=design_option)
    obj["m_cellList"] = _cells_of(cells)
    obj["m_strName"] = str(name)
    obj["m_24HourSchedules"] = [float(x) for x in fractions]
    return Obj("HVACLoadScheduleElem", class_id("HVACLoadScheduleElem"), obj,
               ours=["m_strName", "m_24HourSchedules"],
               notes=[f"our day schedule {name!r} ({sum(1 for x in fractions if x > 0)}/24 h non-zero)"])


def hvac_year_schedule_reproduced(slot: dict) -> Obj:
    """A ``BuildingOperatingYearSchedule`` is PURE MACHINERY: 365 day-slot
    ids wrapping ONE day schedule (uniform in all six samples, 27/27 in the
    base; no name, no free value).  In place, its day-schedule id now points
    at OUR day schedule at that slot -> the object is REPRODUCED
    byte-identical: NOTHING OF OURS TO REJECT (Group B's machinery-
    reproduction proof method)."""
    return Obj("BuildingOperatingYearSchedule", class_id("BuildingOperatingYearSchedule"),
               _deep(slot), ours=[],
               notes=["REPRODUCED machinery: 365 day ids wrapping the (now OUR) day schedule at "
                      f"slot {(slot.get('m_daySchedules') or [None])[0]} -- byte-identical, "
                      "nothing of ours to reject"])


def _hvac_common_values(obj: dict, prof: dict, occ_year: int, ltg_year: int, pwr_year: int):
    """The shared value block of space / building types (OUR profile)."""
    sens, lat = ACTIVITY[prof["activity"]]
    occ = prof["ft2_per_person"]
    obj["m_LightingLoadDensity"] = w_per_ft2(prof["lpd"])
    obj["m_PowerLoadDensity"] = w_per_ft2(prof["epd"])
    obj["m_coolingSetPoint"] = kelvin_f(prof["clg_f"])
    obj["m_dAirChangesPerHour"] = 0.0
    obj["m_dAreaPerPerson"] = float(occ) if occ else 0.0
    obj["m_dEquipmentRadiant"] = 0.35                    # our plug-load radiant fraction assumption
    obj["m_dInfiltration"] = cfm(prof["infiltration"])   # cfm/ft2 -> ft3/s per ft2
    obj["m_dLatentHeatGainPerPerson"] = btuh(lat)
    obj["m_dOutdoorAirPerArea"] = cfm(prof["oa_area"])
    obj["m_dOutdoorAirPerPerson"] = cfm(prof["oa_person"])
    obj["m_dPlenumLighting"] = float(prof["plenum_frac"])
    obj["m_dSensibleHeatGainPerPerson"] = btuh(sens)
    obj["m_dehumidificationSetPoint"] = float(prof["dehum"])
    obj["m_heatingSetPoint"] = kelvin_f(prof["htg_f"])
    obj["m_humidificationSetPoint"] = float(prof["humid"])
    obj["m_idLightingSchedule"] = int(ltg_year)
    obj["m_idOccupancySchedule"] = int(occ_year)
    obj["m_idPowerSchedule"] = int(pwr_year)
    obj["m_eOutdoorAirFlowStandard"] = 0
    obj["m_bCarpeting"] = bool(prof["carpet"])


HVAC_OUR_FIELDS = [
    "m_LightingLoadDensity", "m_PowerLoadDensity", "m_coolingSetPoint", "m_dAreaPerPerson",
    "m_dAirChangesPerHour", "m_dEquipmentRadiant", "m_dInfiltration",
    "m_dLatentHeatGainPerPerson", "m_dOutdoorAirPerArea",
    "m_dOutdoorAirPerPerson", "m_dPlenumLighting", "m_dSensibleHeatGainPerPerson",
    "m_dehumidificationSetPoint", "m_heatingSetPoint", "m_humidificationSetPoint",
    "m_idLightingSchedule", "m_idOccupancySchedule", "m_idPowerSchedule", "m_bCarpeting"]


def hvac_space_type(space_enum: int, canonical_name: str, prof: dict, *,
                    occ_year: int, ltg_year: int, pwr_year: int,
                    elem_id: int = 0, cells=_NO_SLOT, oa_standard: int = 0,
                    design_option: int = NO_DESIGN_OPTION) -> Obj:
    """OUR ``HVACLoadSpaceTypeElem``: the space-type IDENTITY (m_eSpaceType
    + its canonical name = the reader's fixed list / the public space-type
    enumeration) is the slot's INTERFACE; every settings VALUE (densities,
    setpoints, ventilation, heat gains, schedules, plenum / carpet flags) is
    OURS (the profile of :data:`SPACE_TYPE_PROFILE`)."""
    obj = blank_object("HVACLoadSpaceTypeElem")
    element_defaults(obj, int(elem_id), design_option=design_option)
    obj["m_cellList"] = _cells_of(cells)
    _hvac_common_values(obj, prof, occ_year, ltg_year, pwr_year)
    obj["m_name"] = str(canonical_name)
    obj["m_eSpaceType"] = int(space_enum)
    obj["m_isPlenum"] = bool(prof.get("is_plenum", False))
    obj["m_eOutdoorAirFlowStandard"] = int(oa_standard)
    return Obj("HVACLoadSpaceTypeElem", class_id("HVACLoadSpaceTypeElem"), obj,
               ours=HVAC_OUR_FIELDS + ["m_isPlenum"],
               notes=[f"space type #{space_enum} {canonical_name!r} (interface key kept) -> OUR "
                      f"values: LPD {prof['lpd']} W/ft2, EPD {prof['epd']} W/ft2, "
                      f"{prof['ft2_per_person']} ft2/person, OA {prof['oa_person']} cfm/p + "
                      f"{prof['oa_area']} cfm/ft2, {prof['clg_f']}/{prof['htg_f']} degF, "
                      f"schedules {prof['occ_sched']}/{prof['ltg_sched']}/{prof['pwr_sched']}"])


def hvac_building_type(building_enum: int, canonical_name: str, prof: dict, *,
                       occ_year: int, ltg_year: int, pwr_year: int,
                       elem_id: int = 0, cells=_NO_SLOT, oa_standard: int = 0,
                       design_option: int = NO_DESIGN_OPTION) -> Obj:
    """OUR ``HVACLoadBuildingTypeElem``: identity (m_eBuildingType + name) =
    interface; every settings value + the equipment operating window ours."""
    obj = blank_object("HVACLoadBuildingTypeElem")
    element_defaults(obj, int(elem_id), design_option=design_option)
    obj["m_cellList"] = _cells_of(cells)
    _hvac_common_values(obj, prof, occ_year, ltg_year, pwr_year)
    obj["m_name"] = str(canonical_name)
    obj["m_strEquipmentEndTime"] = str(prof["eq_end"])
    obj["m_strEquipmentStartTime"] = str(prof["eq_start"])
    obj["m_dCoolingSetPoint"] = kelvin_f(prof["unocc_clg_f"])
    obj["m_eBuildingType"] = int(building_enum)
    obj["m_eOutdoorAirFlowStandard"] = int(oa_standard)
    return Obj("HVACLoadBuildingTypeElem", class_id("HVACLoadBuildingTypeElem"), obj,
               ours=HVAC_OUR_FIELDS + ["m_strEquipmentStartTime", "m_strEquipmentEndTime",
                                       "m_dCoolingSetPoint"],
               notes=[f"building type #{building_enum} {canonical_name!r} (interface key kept) -> "
                      f"OUR values: LPD {prof['lpd']} W/ft2, EPD {prof['epd']} W/ft2, equipment "
                      f"{prof['eq_start']}-{prof['eq_end']}, {prof['clg_f']}/{prof['htg_f']} degF"])


# ===========================================================================
# 6. CONSTRUCTORS -- the electrical load / demand-factor catalog
# ===========================================================================

def our_demand_factor(rule_key: str, *, elem_id: int, cells=_NO_SLOT,
                      design_option: int = NO_DESIGN_OPTION) -> Obj:
    """OUR ``ElectricalDemandFactorDefinition`` (types.new_demand_factor
    with an NEC-cited rule spec of :data:`DEMAND_RULES`) at a slot: the
    slot's cell apparatus is kept VERBATIM (None stays None)."""
    spec = DEMAND_RULES[rule_key]
    rows = spec["rows"]
    rec = TY.new_demand_factor(spec["name"], rows[0][2], elem_id=int(elem_id),
                               rule=int(spec["rule"]), rows=rows)
    obj = _deep(rec.obj)
    obj["m_cellList"] = _cells_of(cells)
    obj["m_designOptionId"] = int(design_option)
    return Obj("ElectricalDemandFactorDefinition", class_id("ElectricalDemandFactorDefinition"),
               obj, ours=["m_name", "m_ruleType", "m_values", "m_additionalLoad",
                          "m_includeAdditionalLoad"],
               notes=[f"our demand rule {spec['name']!r} ({len(rows)} row(s), rule {spec['rule']}) "
                      f"-- {spec['source']}"])


def our_load_classification(entry: dict, slot: dict) -> Obj:
    """OUR ``ElectricalLoadClassification`` (types.new_load_class + our
    label templates) at an existing slot: the slot's WIRING is kept -- its
    demand-factor id (which our ZC_elec demand rule lands at) and its six
    ParamElemElectricalLoadClassification companion ids (Group B's, id-wired
    both ways) -- and the slot's reserved signature ROLE is kept
    (m_signitureType); the name, abbreviation, labels, rule choice and
    space-load class are ours."""
    v = slot
    pe = {"actual_space": v.get("m_actualSpaceLoadParamElemId", INVALID),
          "demand_factor_param": v.get("m_demandFactorParamElemId", INVALID),
          "est_current": v.get("m_estCurrentParamElemId", INVALID),
          "est_load": v.get("m_estLoadParamElemId", INVALID),
          "total_current": v.get("m_totalCurrentParamElemId", INVALID),
          "total_load": v.get("m_totalLoadParamElemId", INVALID)}
    rec = TY.new_load_class(entry["name"], int(v.get("m_demandFactorId", INVALID)),
                            elem_id=int(v.get("m_id", 0)),
                            space_load_class=int(entry["space_class"]),
                            param_elem_ids=pe)
    obj = _deep(rec.obj)
    for k, tmpl in hs.LOAD_LABEL_TEMPLATES.items():      # our label phrasing
        obj[k] = str(tmpl)
    obj["m_abbreviation"] = str(entry.get("abbrev", ""))
    obj["m_signitureType"] = int(entry.get("signature", v.get("m_signitureType", 0)))
    obj["m_cellList"] = _deep(v.get("m_cellList"))
    obj["m_designOptionId"] = int(v.get("m_designOptionId", NO_DESIGN_OPTION))
    return Obj("ElectricalLoadClassification", class_id("ElectricalLoadClassification"), obj,
               ours=["m_name", "m_abbreviation", "m_spaceLoadClass", "m_signitureType(role)",
                     "the six label templates"],
               notes=[f"our classification {entry['name']!r} (rule {entry['rule']}, space class "
                      f"{entry['space_class']}, role {entry.get('role')}); wiring kept: demand "
                      f"slot {v.get('m_demandFactorId')}, 6 companion param ids"])


def plan_electrical_layer(doc, class_slots: Sequence[int], demand_slots: Sequence[int]
                          ) -> Tuple[Dict[int, Obj], dict]:
    """Plan the WHOLE electrical load-classification / demand-factor layer of
    a parent IN PLACE.

    The parent's id-wiring decides the STRUCTURE (which classification slot
    points at which demand slot; several classifications may share one demand
    slot); OUR library supplies the content.  Assignment (deterministic):
      1. classification slots whose ``m_signitureType`` marks a RESERVED ROLE
         (1 motor / 2 other / 3 spare) receive OUR role entries;
      2. the remaining classification slots are grouped by the demand slot
         they share (largest group first) and receive OUR regular entries so
         that a shared demand slot serves classifications with the SAME rule
         (our entries are bucketed by rule);
      3. every REFERENCED demand slot gets the rule of the classification(s)
         it serves ('no_diversity' if a mixed group could not be avoided --
         reported); every UNREFERENCED demand slot gets one of OUR extra NEC
         demand definitions (:data:`DEMAND_EXTRAS`), then repeats the basic set.
    Returns ({slot: Obj}, report)."""
    plans: Dict[int, Obj] = {}
    rep: Dict[str, Any] = {"roles": {}, "groups": [], "assignment": {}, "demand_rules": {},
                           "mixed_groups": [], "unreferenced_demand": []}
    # --- the demand web of the parent ------------------------------------------
    demand_set = set(int(d) for d in demand_slots)
    by_demand: Dict[int, List[int]] = collections.defaultdict(list)   # demand slot -> class slots
    role_slot: Dict[str, int] = {}
    for c in sorted(int(x) for x in class_slots):
        v = doc.value(c) or {}
        role = _ROLE_BY_SIGNATURE.get(int(v.get("m_signitureType", 0)))
        if role and role not in role_slot:
            role_slot[role] = c
        by_demand[int(v.get("m_demandFactorId", INVALID))].append(c)
    # --- 1. reserved roles ------------------------------------------------------
    assigned: Dict[int, dict] = {}
    lib_roles = {e["role"]: e for e in LOAD_CLASS_LIBRARY if e["role"]}
    for role, c in role_slot.items():
        if role in lib_roles:
            assigned[c] = lib_roles[role]
            rep["roles"][role] = c
    # --- 2. regular slots, grouped by shared demand slot ----------------------
    regular_specs = [e for e in LOAD_CLASS_LIBRARY if not e["role"]]
    groups = sorted(((d, [c for c in cs if c not in assigned]) for d, cs in by_demand.items()),
                    key=lambda t: (-len(t[1]), t[0]))
    buckets: Dict[str, List[dict]] = collections.defaultdict(list)
    for e in regular_specs:
        buckets[e["rule"]].append(e)
    used_specs: Set[str] = set()
    for d, cs in groups:
        cs = [c for c in cs if c not in assigned]
        if not cs:
            continue
        rep["groups"].append({"demand_slot": d, "class_slots": cs, "size": len(cs)})
        # a bucket with at least len(cs) unused entries of one rule serves the group
        pick: Optional[List[dict]] = None
        for rule, entries in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
            avail = [e for e in entries if e["name"] not in used_specs]
            if len(avail) >= len(cs):
                pick = avail[:len(cs)]
                break
        if pick is None:                                   # mixed group (fallback)
            leftover = [e for e in regular_specs if e["name"] not in used_specs]
            pick = leftover[:len(cs)]
            rep["mixed_groups"].append({"demand_slot": d, "class_slots": cs})
        for c, e in zip(cs, pick):
            assigned[c] = e
            used_specs.add(e["name"])
    # any classification slot still unassigned (more slots than our library):
    # extend our library deterministically with numbered spare classes
    extra_i = 0
    for c in sorted(int(x) for x in class_slots):
        if c not in assigned:
            extra_i += 1
            assigned[c] = {"name": gen(f"Load Class {extra_i:02d}"), "rule": "no_diversity",
                           "space_class": 0, "role": None, "signature": 0,
                           "abbrev": f"C{extra_i:02d}"}
    # --- 3. demand rules --------------------------------------------------------
    rule_of_demand: Dict[int, str] = {}
    for d, cs in by_demand.items():
        if d not in demand_set:
            continue
        rules = sorted({assigned[c]["rule"] for c in cs})
        rule_of_demand[d] = rules[0] if len(rules) == 1 else "no_diversity"
        if len(rules) > 1:
            rep["mixed_groups"].append({"demand_slot": d, "rules": rules, "resolved": "no_diversity"})
    extras = list(DEMAND_EXTRAS) + list(DEMAND_RULES)
    xi = 0
    for d in sorted(demand_set):
        if d not in rule_of_demand:
            rule_of_demand[d] = extras[xi % len(extras)]
            rep["unreferenced_demand"].append({"demand_slot": d, "our_rule": rule_of_demand[d]})
            xi += 1
    # --- build ------------------------------------------------------------------
    for c, e in sorted(assigned.items()):
        plans[c] = our_load_classification(e, doc.value(c) or {})
        rep["assignment"][str(c)] = {"our_class": e["name"], "rule": e["rule"],
                                     "role": e.get("role"),
                                     "demand_slot": int((doc.value(c) or {}).get("m_demandFactorId", -1))}
    for d, rule in sorted(rule_of_demand.items()):
        v = doc.value(d) or {}
        plans[d] = our_demand_factor(rule, elem_id=d, cells=v.get("m_cellList"),
                                     design_option=int(v.get("m_designOptionId", NO_DESIGN_OPTION)))
        rep["demand_rules"][str(d)] = {"our_rule": rule, "name": DEMAND_RULES[rule]["name"],
                                       "referenced_by": by_demand.get(d, [])}
    return plans, rep


# ===========================================================================
# 7. CONSTRUCTORS -- conduit / cable-tray catalogs
# ===========================================================================
#: OUR conduit standards (house_standard) + PVC Schedule 80 [FACT: NEMA
#: TC-2 / NEC Ch.9 Table 4 Schedule 80 nominal IDs; RMC ODs (same OD series
#: as Schedule 40 rigid PVC)], so a 5-slot base carries five of ours.
PVC80_STANDARD = {
    "key": "pvc80", "name": gen("PVC Schedule 80"), "source": "NEMA TC-2 / NEC Ch.9 T4",
    "sizes": [(0.5, 0.526, 0.840), (0.75, 0.722, 1.050), (1.0, 0.936, 1.315),
              (1.25, 1.255, 1.660), (1.5, 1.476, 1.900), (2.0, 1.913, 2.375),
              (2.5, 2.290, 2.875), (3.0, 2.864, 3.500), (3.5, 3.326, 4.000),
              (4.0, 3.786, 4.500), (5.0, 4.768, 5.563), (6.0, 5.709, 6.625)],
}
OUR_CONDUIT_STANDARDS: List[dict] = list(hs.CONDUIT_STANDARDS) + [PVC80_STANDARD]


def our_conduit_standard(spec: dict, slot: dict) -> Obj:
    """OUR ``ConduitStandardType`` (a named conduit STANDARD -- the name IS
    the definition; the size table lives in the ConduitSizesElem keyed by
    this slot's id).  types.new_conduit_standard + the slot's cell / empty
    AString-set apparatus."""
    rec = TY.new_conduit_standard(spec["name"], elem_id=int(slot.get("m_id", 0)))
    obj = _deep(rec.obj)
    obj["m_cellList"] = _deep(slot.get("m_cellList"))
    if slot.get("m_pParamValueSetAString") is not None:
        obj["m_pParamValueSetAString"] = _deep(slot.get("m_pParamValueSetAString"))
    obj["m_designOptionId"] = int(slot.get("m_designOptionId", NO_DESIGN_OPTION))
    obj["m_renderStyleId"] = int(slot.get("m_renderStyleId", INVALID))
    obj["m_previewElemId"] = int(slot.get("m_previewElemId", INVALID))
    return Obj("ConduitStandardType", class_id("ConduitStandardType"), obj,
               ours=["m_symbolInfo.value.m_name"],
               notes=[f"our conduit standard {spec['name']!r} ({spec['source']})"])


def our_conduit_sizes(std_slot_by_key: Dict[str, int], slot: dict) -> Obj:
    """OUR ``ConduitSizesElem`` (the document's conduit size table): for
    each of OUR standards (at the standard slots the parent keys the table
    on), the trade-size / inner / outer / bend-radius rows -- published NEC
    Ch.9 Table 4 dimensions + Table 2 bend radii (FACTS; the standard
    SELECTION is ours), via types.conduit_sizes_element."""
    sizes = {}
    for spec in OUR_CONDUIT_STANDARDS:
        sid = std_slot_by_key.get(spec["key"])
        if sid is None:
            continue
        rows = hs.conduit_size_rows(spec) if spec["key"] != "pvc80" else \
            [(t, i, o, hs._BEND_RADIUS_IN.get(t, 6.0 * t)) for t, i, o in spec["sizes"]]
        sizes[int(sid)] = rows
    rec = TY.conduit_sizes_element(sizes, elem_id=int(slot.get("m_id", 0)))
    obj = _deep(rec.obj)
    obj["m_cellList"] = _deep(slot.get("m_cellList"))
    obj["m_designOptionId"] = int(slot.get("m_designOptionId", NO_DESIGN_OPTION))
    return Obj("ConduitSizesElem", class_id("ConduitSizesElem"), obj, ours=["m_sizes"],
               notes=[f"our conduit size table: {len(sizes)} standards x rows "
                      f"{[len(v) for v in sizes.values()]} (NEC Ch.9 Table 4 / Table 2 facts)"])


def our_cable_tray_sizes(slot: dict) -> Obj:
    """OUR ``CableTraySizesElem``: the tray width list = the NEMA VE 1
    standard widths our practice stocks (house_standard.CABLE_TRAY_WIDTHS_IN;
    a FACT of the trade), via types.cable_tray_sizes_element."""
    rec = TY.cable_tray_sizes_element(list(hs.CABLE_TRAY_WIDTHS_IN), elem_id=int(slot.get("m_id", 0)))
    obj = _deep(rec.obj)
    obj["m_cellList"] = _deep(slot.get("m_cellList"))
    obj["m_designOptionId"] = int(slot.get("m_designOptionId", NO_DESIGN_OPTION))
    return Obj("CableTraySizesElem", class_id("CableTraySizesElem"), obj, ours=["m_sizes"],
               notes=[f"our cable-tray widths {list(hs.CABLE_TRAY_WIDTHS_IN)} in (NEMA VE 1)"])


# ===========================================================================
# 8. CONSTRUCTORS -- residue system-family types + welded-wire fabric
# ===========================================================================

def _material_ids_by_name(doc) -> Dict[str, int]:
    """{material name: id} of the parent's MaterialElems (our palette lands
    under its gen() names -- looked up by NAME, never a value read)."""
    out: Dict[str, int] = {}
    for e in doc.ids_of_class("MaterialElem"):
        v = doc.value(e) or {}
        mat = (v.get("m_pMaterial") or {}).get("value") or {}
        nm = str(mat.get("m_name") or "")
        if nm and nm not in out:
            out[nm] = int(e)
    return out


def _layers(spec_layers: Sequence[Tuple[str, float, str]], mats: Dict[str, int]
            ) -> List[Tuple[str, float, int]]:
    return [(fn, float(w), int(mats.get(mname, INVALID))) for fn, w, mname in spec_layers]


def our_wall_type(slot: dict, mats: Dict[str, int]) -> Obj:
    """OUR ``BasicWallType`` (types.new_wall_type) at the residue system-
    family slot: our name + our layer make-up over OUR palette materials;
    the slot's type-preview id / cell apparatus / param sets are kept
    (its LegendComponent preview then displays OUR type)."""
    rec = TY.new_wall_type(WALL_TYPE["name"], _layers(WALL_TYPE["layers"], mats),
                           elem_id=int(slot.get("m_id", 0)),
                           function=int(WALL_TYPE["function"]),
                           preview_id=int(slot.get("m_previewElemId", INVALID)),
                           with_geometry_rep=False)
    obj = _deep(rec.obj)
    for f in ("m_pParamValueSetDouble", "m_pParamValueSetInt", "m_pParamValueSetAString",
              "m_pParamValueSetElementId", "m_cellList", "m_geomSteps"):
        if f in slot:
            obj[f] = _deep(slot[f])
    obj["m_designOptionId"] = int(slot.get("m_designOptionId", NO_DESIGN_OPTION))
    obj["m_renderStyleId"] = int(slot.get("m_renderStyleId", INVALID))
    return Obj("BasicWallType", class_id("BasicWallType"), obj,
               ours=["m_symbolInfo.value.m_name", "m_pCompoundStructure (our layers)", "m_function"],
               notes=[f"our wall type {WALL_TYPE['name']!r}: layers "
                      f"{[(fn, w, m) for fn, w, m in WALL_TYPE['layers']]}; preview "
                      f"{slot.get('m_previewElemId')} kept"])


def our_floor_type(slot: dict, mats: Dict[str, int]) -> Obj:
    """OUR ``FloorAttributes`` (types.new_floor_type) at the residue slot:
    our name + our slab layer over OUR palette material; preview id kept."""
    rec = TY.new_floor_type(FLOOR_TYPE["name"], _layers(FLOOR_TYPE["layers"], mats),
                            elem_id=int(slot.get("m_id", 0)),
                            preview_id=int(slot.get("m_previewElemId", INVALID)))
    obj = _deep(rec.obj)
    for f in ("m_pParamValueSetDouble", "m_pParamValueSetInt", "m_pParamValueSetAString",
              "m_pParamValueSetElementId", "m_cellList", "m_geomSteps"):
        if f in slot:
            obj[f] = _deep(slot[f])
    obj["m_designOptionId"] = int(slot.get("m_designOptionId", NO_DESIGN_OPTION))
    obj["m_renderStyleId"] = int(slot.get("m_renderStyleId", INVALID))
    return Obj("FloorAttributes", class_id("FloorAttributes"), obj,
               ours=["m_symbolInfo.value.m_name", "m_pCompoundStructure (our layers)"],
               notes=[f"our floor type {FLOOR_TYPE['name']!r}: layers "
                      f"{[(fn, w, m) for fn, w, m in FLOOR_TYPE['layers']]}; preview "
                      f"{slot.get('m_previewElemId')} kept"])


def our_fabric_wire_type(slot: dict) -> Obj:
    """OUR ``FabricWireType``: an ASTM A1064 wire designation (name), its
    diameter (FACT of the designation) and the minimum bend diameter (our
    detailing rule: 4 wire diameters, per ACI 318's small-bar minimum)."""
    d_in = float(FABRIC_WIRE["diameter_in"])
    obj = blank_object("FabricWireType")
    element_defaults(obj, int(slot.get("m_id", 0)),
                     design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)))
    obj["m_cellList"] = _deep(slot.get("m_cellList"))
    symbol_defaults(obj, FABRIC_WIRE["name"],
                    preview_id=int(slot.get("m_previewElemId", INVALID)),
                    render_style_id=int(slot.get("m_renderStyleId", INVALID)))
    obj["m_bendDiameter"] = inches(d_in * float(FABRIC_WIRE["bend_diameter_factor"]))
    obj["m_wireDiameter"] = inches(d_in)
    return Obj("FabricWireType", class_id("FabricWireType"), obj,
               ours=["m_symbolInfo.value.m_name", "m_wireDiameter", "m_bendDiameter"],
               notes=[f"our wire {FABRIC_WIRE['name']!r} ({FABRIC_WIRE['source']}), bend "
                      f"diameter {FABRIC_WIRE['bend_diameter_factor']} db"])


def our_fabric_sheet_type(slot: dict, wire_id: int) -> Obj:
    """OUR ``FabricSheetType``: an ASTM A1064 welded-wire fabric designation
    with our sheet make-up (spacing / laps / overhangs / sheet size).  The
    slot's WIRING is kept -- the wire-type slot (now OUR wire), the sheet
    material slot (the palette layer's), the MasterSymbolCell -> its
    SlaveSymbolTracker (Group B's reproduced machinery)."""
    sp = FABRIC_SHEET
    spacing_ft = inches(sp["spacing_in"])
    length_ft, width_ft = float(sp["overall_length_ft"]), float(sp["overall_width_ft"])
    obj = blank_object("FabricSheetType")
    element_defaults(obj, int(slot.get("m_id", 0)),
                     design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)))
    obj["m_cellList"] = _deep(slot.get("m_cellList"))          # MasterSymbolCell -> tracker (kept)
    symbol_defaults(obj, sp["name"], preview_id=int(slot.get("m_previewElemId", INVALID)),
                    render_style_id=int(slot.get("m_renderStyleId", INVALID)))
    obj["m_majorEndOverhang"] = inches(sp["overhang_in"])
    obj["m_majorLapSpliceLength"] = inches(sp["lap_splice_in"])
    obj["m_majorStartOverhang"] = inches(sp["overhang_in"])
    obj["m_minorEndOverhang"] = inches(sp["overhang_in"])
    obj["m_minorLapSpliceLength"] = inches(sp["lap_splice_in"])
    obj["m_minorStartOverhang"] = inches(sp["overhang_in"])
    obj["m_overallLength"] = length_ft
    obj["m_overallWidth"] = width_ft
    obj["m_sheetMaterial"] = int(slot.get("m_sheetMaterial", INVALID))
    obj["m_userEnteredSheetMass"] = float(sp["mass_kg"])
    obj["m_majorLayoutPattern"] = 0
    obj["m_majorNumberOfWires"] = int(round(width_ft / spacing_ft)) + 1
    obj["m_minorLayoutPattern"] = 0
    obj["m_minorNumberOfWires"] = int(round(length_ft / spacing_ft)) + 1
    obj["m_isSheetMassCalculated"] = False
    obj["m_insertionOrigin"] = {"m_3x3": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                                "m_or": [0.0, 0.0, 0.0]}
    obj["m_majorDirectionWireType"] = int(wire_id)
    obj["m_majorSpacing"] = spacing_ft
    obj["m_minorDirectionWireType"] = int(wire_id)
    obj["m_minorSpacing"] = spacing_ft
    return Obj("FabricSheetType", class_id("FabricSheetType"), obj,
               ours=["m_symbolInfo.value.m_name", "spacings", "overhangs", "lap splices",
                     "sheet size", "wire counts", "sheet mass"],
               notes=[f"our fabric {sp['name']!r} ({sp['source']}); wire slot {wire_id}, "
                      f"material slot {slot.get('m_sheetMaterial')} + tracker cell kept"])


# ===========================================================================
# 9. CONSTRUCTORS -- analysis / area / structural settings machinery
# ===========================================================================

def reproduced(class_name: str, slot: dict, why: str) -> Obj:
    """A PURE-MACHINERY slot reproduced byte-identical (empty topology
    holders, area-type enum rows, the sheet's drawing viewport list, year
    schedules): the byte-delta table will show it 'landed but byte-
    identical' = the machine-checked statement that there is NOTHING OF OURS
    TO REJECT (docs/inbox/genesis-residue-B.md finding 8's method)."""
    return Obj(class_name, class_id(class_name), _deep(slot), ours=[],
               notes=[f"REPRODUCED machinery ({why}) -- byte-identical, nothing of ours to reject"])


def our_load_nature(name: str, slot: dict) -> Obj:
    """OUR ``LoadNatureElem`` (a structural load NATURE = a name; the name
    is mirrored into its AString parameter -1015254)."""
    obj = blank_object("LoadNatureElem")
    element_defaults(obj, int(slot.get("m_id", 0)),
                     astring_params={BIP_LOAD_NATURE_NAME: str(name)},
                     design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)))
    obj["m_cellList"] = _cells_of(slot.get("m_cellList")) if slot else _cell_pattern_helper()
    obj["m_name"] = str(name)
    return Obj("LoadNatureElem", class_id("LoadNatureElem"), obj,
               ours=["m_name", "m_pParamValueSetAString(-1015254)"],
               notes=[f"our load nature {name!r}"])


def our_load_case(name: str, number: int, slot: dict) -> Obj:
    """OUR ``LoadCaseElem`` (a load CASE: name, sequence number).  The
    slot's built-in load-case CATEGORY (which load category the case
    belongs to -- an interface enum) and its nature-slot wiring are kept;
    the name (mirrored into AString parameter -1015250) and number ours."""
    obj = blank_object("LoadCaseElem")
    element_defaults(obj, int(slot.get("m_id", 0)), int_params={}, elemid_params={},
                     astring_params={BIP_LOAD_CASE_NAME: str(name)},
                     design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)))
    obj["m_cellList"] = _cells_of(slot.get("m_cellList")) if slot else _cell_pattern_helper()
    obj["m_name"] = str(name)
    obj["m_categoryId"] = int(slot.get("m_categoryId", OST_LoadCasesDead))
    obj["m_natureId"] = int(slot.get("m_natureId", INVALID))
    obj["m_number"] = int(number)
    return Obj("LoadCaseElem", class_id("LoadCaseElem"), obj,
               ours=["m_name", "m_number", "m_pParamValueSetAString(-1015250)"],
               notes=[f"our load case {name!r} #{number}; category {slot.get('m_categoryId')} + "
                      f"nature slot {slot.get('m_natureId')} kept"])


def our_area_report_settings(slot: dict) -> Obj:
    """OUR ``AreaReportSettingsElem`` (the area-report drafting settings)
    as an OVERLAY on the slot: our font names / sizes / prefixes; the unit-
    format machinery and the wiring to its OWN fonts / internal categories
    (already ours: ZA_annot's fonts, Z_subcat's internal rows) are kept."""
    ours = _deep(slot)
    for st in (ours.get("m_allSettings") or []):
        st["m_name"] = str(AREA_REPORT_SETTINGS["name"])
        st["m_prefixArcSector"] = str(AREA_REPORT_SETTINGS["prefix_arc_sector"])
        st["m_prefixTriangle"] = str(AREA_REPORT_SETTINGS["prefix_triangle"])
        st["m_fontAnotName"] = str(hs.TEXT_FONT)
        st["m_fontTagName"] = str(hs.TEXT_FONT)
        st["m_fontSize"] = [mm(AREA_REPORT_SETTINGS["font_size_mm"][0]),
                            mm(AREA_REPORT_SETTINGS["font_size_mm"][1])]
    delta = field_delta(slot, ours)
    return Obj("AreaReportSettingsElem", class_id("AreaReportSettingsElem"), ours,
               ours=["m_allSettings[*].m_prefixArcSector/m_prefixTriangle",
                     "m_allSettings[*].m_fontAnotName/m_fontTagName", "m_allSettings[*].m_fontSize"],
               notes=[f"OVERLAY (unit-format machinery + own font/category wiring = the slot's); "
                      f"our text {AREA_REPORT_SETTINGS}; delta {delta}"])


def our_empty_assembly_code_table(slot: dict) -> Obj:
    """OUR ``AssemblyCodeTable`` = an EMPTY assembly-code table: NO embedded
    classification rows, NO external-file / external-resource references.
    The slot's table EMBEDS 795 UniFormat classification rows (Autodesk's
    shipped ``UniformatClassifications.txt``, byte-identical in all six
    samples) and its cells name an Autodesk employee's local OneDrive path
    -- PRODUCT DATA + an identity leak, neither ours to express.  A genesis
    document's assembly-code table is empty until a project supplies its own
    classification file (the campaign's KeynoteTable precedent: our EMPTY
    keynote table retired the sample's).  Shape = the reader-accepted empty
    keynote-table shape (empty ClassificationEntries + empty reference
    cells)."""
    obj = blank_object("AssemblyCodeTable")
    element_defaults(obj, int(slot.get("m_id", 0)),
                     design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)))
    obj["m_cellList"] = _ptr("CellList", {"m_cells": [
        _ptr("ExternalFileReferenceCell", {}),
        _ptr("ExternalResourceReferenceCell", {"m_externalResourceReferences": [],
                                                "m_externalResourceReferencesExpanded": []})]})
    obj["m_oKeyBasedTreeEntries"] = _ptr("ClassificationEntries",
                                        {"m_keyBasedTreeEntrySet": [], "m_orphans": []})
    obj["m_lastReadSucceeded"] = False
    obj["m_hasUserCustomizedAssemblyCode"] = False
    return Obj("AssemblyCodeTable", class_id("AssemblyCodeTable"), obj,
               ours=["EMPTY table (no classification rows, no external references)"],
               notes=["our EMPTY assembly-code table: retires the embedded 795-row UniFormat product "
                      "table + the Autodesk employee's OneDrive path (identity leak) at the slot"])


def our_color_fill_schema(slot: dict, index: int) -> Obj:
    """OUR ``ColorFillSchema`` at a slot: the scheme's DEFINITION pairing
    (target category, key parameter, area scheme, by-range flag, parameter
    storage type) is the slot's REGISTRATION (kept); the name, title, and
    the entry list (values / captions / colours / fill pattern) are ours.
    Rooms/spaces schemes keyed on a STRING parameter carry our department
    vocabulary; the by-range area scheme carries our area breakpoints; the
    rest ship EMPTY (entries auto-populate from the model, corpus-legal)."""
    ours = _deep(slot)
    cat = int(slot.get("m_categoryId", INVALID))
    pid = int(slot.get("m_paramId", INVALID))
    by_range = bool(slot.get("m_bByRange", False))
    cat_word = _CFS_CATEGORY_WORD.get(cat, "Scheme")
    param_word = _CFS_PARAM_WORD.get(pid, "")
    name = gen(f"{cat_word} {param_word}".strip())
    ours["m_strName"] = name
    ours["m_title"] = f"{name} Legend"
    # entry storage type of this scheme (from the slot's own entries or its flag)
    proto = (slot.get("m_colorFillArr") or [{}])[0]
    st_type = int((proto.get("m_paramStorage") or {}).get("m_storageType", 3))
    entries: List[dict] = []
    if by_range:
        for i, (lo, hi) in enumerate(AREA_RANGES_FT2):
            entries.append(_cfs_entry(caption=f"{int(lo)} - {int(hi) if hi < 1e29 else 'up'}",
                                      dbl=(lo, hi), color=COLOR_FILL_PALETTE[i % len(COLOR_FILL_PALETTE)],
                                      by_range=True, storage_type=2))
    elif pid in (-1006907,) or (cat in (-2000160, -2003600) and st_type == 3 and pid != -1006900):
        for i, dep in enumerate(DEPARTMENT_VOCABULARY):
            entries.append(_cfs_entry(value=dep, color=COLOR_FILL_PALETTE[i % len(COLOR_FILL_PALETTE)],
                                      storage_type=3))
    ours["m_colorFillArr"] = entries
    return Obj("ColorFillSchema", class_id("ColorFillSchema"), ours,
               ours=["m_strName", "m_title", "m_colorFillArr (our entries / colours)"],
               notes=[f"our scheme {name!r} on category {cat} keyed by parameter {pid} "
                      f"(byRange {by_range}); {len(entries)} of our entries "
                      f"({'department vocabulary' if entries and not by_range else 'area ranges' if by_range else 'empty -- auto-populate'})"])


def _cfs_entry(*, value: Any = "", caption: str = "", dbl: Optional[Tuple[float, float]] = None,
               color: int = 0xC8C8C8, by_range: bool = False, storage_type: int = 3) -> dict:
    """One colour-scheme entry (the shape every corpus entry carries)."""
    stg = {"m_str": {"m_str": ""}, "m_dbl": 0.0, "m_elemId": INVALID, "m_int": 0,
           "m_storageType": int(storage_type)}
    if storage_type == 3:
        stg["m_str"] = {"m_str": str(value)}
    elif storage_type == 2 and dbl is not None:
        stg["m_dbl"] = float(dbl[0])
    return {"m_caption": str(caption), "m_paramStorage": stg,
            "m_fillPatternId": FILLPATTERN_SOLID, "m_color": int(color),
            "m_bByRange": bool(by_range), "m_bColorManually": True,
            "m_bDefaultCaption": (not caption), "m_bHidden": False,
            "m_bInUse": True, "m_isPlaceholder": False}


# ===========================================================================
# 10. CONSTRUCTORS -- browser organizations + the sheet-view constellation
# ===========================================================================

def our_browser_organization(spec: dict, slot: dict) -> Obj:
    """OUR ``BrowserOrganization`` (settings.browser_organization) at a
    surplus slot: our scheme name + folder / sort definition over BUILT-IN
    parameters (interface constants); the slot's tree TYPE is kept (a views
    scheme stays a views scheme)."""
    from . import settings as ST
    bip = {n: getattr(ST, n) for n in dir(ST) if n.startswith("BIP_")}
    tree = int(slot.get("m_type", 0))

    def resolve(x):
        if isinstance(x, dict):
            return {"param": bip[x["param"]] if isinstance(x["param"], str) else x["param"],
                    "chars": int(x.get("chars", 0))}
        return bip[x] if isinstance(x, str) else int(x)

    org_type = tree
    folders = [resolve(f) for f in spec["folders"]]
    sort_by = resolve(spec["sort"])
    rec = ST.browser_organization(spec["name"], org_type=org_type, folders=folders,
                                  sort_by=(sort_by["param"] if isinstance(sort_by, dict) else sort_by),
                                  ascending=True, is_default=False,
                                  elem_id=int(slot.get("m_id", 0)),
                                  cell_list=bool(slot.get("m_cellList")))
    obj = _deep(rec.obj)
    if slot.get("m_cellList") is not None:
        obj["m_cellList"] = _deep(slot.get("m_cellList"))
    obj["m_designOptionId"] = int(slot.get("m_designOptionId", NO_DESIGN_OPTION))
    obj["m_renderStyleId"] = int(slot.get("m_renderStyleId", INVALID))
    obj["m_previewElemId"] = int(slot.get("m_previewElemId", INVALID))
    return Obj("BrowserOrganization", class_id("BrowserOrganization"), obj,
               ours=["m_symbolInfo.value.m_name", "m_folderDefinitions", "m_sortParameter",
                     "m_bSortOrderAsc", "m_bDefault"],
               notes=[f"our organization {spec['name']!r} (tree type {tree}, folders "
                      f"{spec['folders']}, sort {spec['sort']})"])


def our_sheet_view(slot: dict) -> Obj:
    """OUR sheet-view (``DBViewDrafting`` 1457028 = the K4 lineage's sheet
    'S101 - Framing Plans', on whose drawing OUR two plan views are placed)
    as an OVERLAY: our sheet identity (name / number / dates / drawn-
    checked-designed-approved tokens) and an EMPTY RvtLinkOverrides map (we
    place NO linked model -- this removes the seq-102 pin the deletion
    stream found on the RvtLinkSymbol).  All view machinery (override
    managers, draw filters, retouch table, wiring to its drawing / viewer /
    viewport / view type / sketch plane) = the slot's."""
    ours = _deep(slot)
    idn = SHEET_IDENTITY
    ours["m_viewName"] = str(idn["view_name"])
    ours["m_sheetNumber"] = str(idn["sheet_number"])
    ours["m_date"] = str(idn["date"])
    ours["m_issueDate"] = str(idn["issue_date"])
    ours["m_drawnBy"] = str(idn["drawn_by"])
    ours["m_checkedBy"] = str(idn["checked_by"])
    ours["m_designedBy"] = str(idn["designed_by"])
    ours["m_approvedBy"] = str(idn["approved_by"])
    lo = (ours.get("m_pRvtLinkOverrides") or {})
    if isinstance(lo, dict) and isinstance(lo.get("value"), dict):
        lo["value"]["m_displaySettingsMap"] = []                 # NO link display settings
        lo["value"]["m_invisibleSet"] = []
        lo["value"]["m_halftoneSet"] = []
        lo["value"]["m_underlaySet"] = []
    return Obj("DBViewDrafting", class_id("DBViewDrafting"), ours,
               ours=["m_viewName", "m_sheetNumber", "m_date", "m_issueDate", "m_drawnBy",
                     "m_checkedBy", "m_designedBy", "m_approvedBy",
                     "m_pRvtLinkOverrides.value.m_displaySettingsMap (EMPTIED)"],
               notes=[f"OUR sheet {idn['sheet_number']} {idn['view_name']!r} (identity tokens ours; "
                      "override managers / draw filters / wiring = the slot's); the RvtLinkSymbol "
                      "display-settings pin is REMOVED (empty link overrides)"])


# ===========================================================================
# 11. THE PARENT + THE RESIDUE PLANS (parent -> {slot: Obj}) per rung
# ===========================================================================

class Parent2:
    """Read-only view of the CERTIFIED parent a ZC rung derives from (default
    ZA_deep): the mutate.Document + the typed reference graph + the FULL
    landed-slot map (Y-ladder + the parent's own cumulative report), so
    'residue' means exactly ``residue_after_ZA_deep.json``'s residue."""

    def __init__(self, path: str = DEFAULT_PARENT, *, report: str = DEFAULT_PARENT_REPORT,
                 with_graph: bool = True):
        base = RA.Parent(path, with_graph=with_graph)
        self._p = base
        self.path = base.path
        self.state = base.state
        self.doc = base.doc
        self.cls_of = base.cls_of
        self.landed = residue_of_parent(report)
        self.residue = RA.residue_by_class(self.doc, self.landed)
        self.seconds = base.seconds

    # emit_rung reads .doc/.path/.value; parity stub reads via _CtxStub(parent)
    def value(self, eid: int) -> dict:
        return self.doc.value(int(eid)) or {}

    def name_of(self, eid: int) -> str:
        return self._p.name_of(eid)

    def referrers(self, eid: int) -> Set[int]:
        return self._p.referrers(eid)

    def residue_of(self, class_name: str) -> List[int]:
        return sorted(self.residue.get(class_name, []))


def plan_hvac(parent: Parent2, enums: Optional[dict] = None) -> RungPlan:
    """ZC_hvac: the HVAC / energy database web -- our day-schedule library at
    the day slots (year schedules = reproduced 365-day wrappers), the space
    types and building types with their interface identity kept and OUR
    values applied (:data:`SPACE_TYPE_PROFILE` / :data:`BUILDING_TYPE_PROFILE`),
    schedule references rewired to OUR schedules by role."""
    doc = parent.doc
    plans: Dict[int, Obj] = {}
    notes: List[str] = []
    info: Dict[str, Any] = {}
    day_slots = parent.residue_of("HVACLoadScheduleElem")
    year_slots = parent.residue_of("BuildingOperatingYearSchedule")
    space_slots = parent.residue_of("HVACLoadSpaceTypeElem")
    build_slots = parent.residue_of("HVACLoadBuildingTypeElem")
    # ---- day schedules: our library over the slots (extend deterministically) --
    lib = list(DAY_SCHEDULES)
    while len(lib) < len(day_slots):
        i = len(lib) - len(DAY_SCHEDULES)
        base = DAY_SCHEDULES[i % len(DAY_SCHEDULES)]
        lib.append({"key": f"{base['key']}_v{i // len(DAY_SCHEDULES) + 2}",
                    "name": f"{base['name']} (Variant {i // len(DAY_SCHEDULES) + 2})",
                    "hours": list(base["hours"])})
    key_at_day: Dict[int, str] = {}
    for slot, spec in zip(day_slots, lib):
        v = parent.value(slot)
        plans[slot] = hvac_day_schedule(spec["name"], spec["hours"], elem_id=slot,
                                        cells=v.get("m_cellList"),
                                        design_option=int(v.get("m_designOptionId", NO_DESIGN_OPTION)))
        key_at_day[slot] = spec["key"]
    # ---- year schedules: reproduced wrappers; role -> year slot map ----------
    year_of_key: Dict[str, int] = {}
    for slot in year_slots:
        v = parent.value(slot)
        plans[slot] = hvac_year_schedule_reproduced(v)
        day = (v.get("m_daySchedules") or [None])[0]
        k = key_at_day.get(int(day)) if day is not None else None
        if k and k not in year_of_key:
            year_of_key[k] = slot

    def year(role_key: str) -> int:
        """Our year schedule carrying the day profile ``role_key`` (fallback:
        any of ours; -1 if the base has no schedules)."""
        if role_key in year_of_key:
            return year_of_key[role_key]
        for fb in ("on24", "occ_office", "off"):
            if fb in year_of_key:
                return year_of_key[fb]
        return next(iter(year_of_key.values()), INVALID)

    # ---- space types ------------------------------------------------------------
    prof_use = collections.Counter()
    for slot in space_slots:
        v = parent.value(slot)
        e = int(v.get("m_eSpaceType", 0))
        pk = SPACE_TYPE_PROFILE.get(e, "office_open")
        prof = SPACE_PROFILES[pk]
        prof_use[pk] += 1
        plans[slot] = hvac_space_type(e, str(v.get("m_name") or ""), prof,
                                      occ_year=year(prof["occ_sched"]),
                                      ltg_year=year(prof["ltg_sched"]),
                                      pwr_year=year(prof["pwr_sched"]),
                                      elem_id=slot, cells=v.get("m_cellList"),
                                      oa_standard=int(v.get("m_eOutdoorAirFlowStandard", 0)),
                                      design_option=int(v.get("m_designOptionId", NO_DESIGN_OPTION)))
    # ---- building types ----------------------------------------------------------
    bprof_use = collections.Counter()
    for slot in build_slots:
        v = parent.value(slot)
        e = int(v.get("m_eBuildingType", 0))
        pk = BUILDING_TYPE_PROFILE.get(e, "office")
        prof = BUILDING_PROFILES[pk]
        bprof_use[pk] += 1
        plans[slot] = hvac_building_type(e, str(v.get("m_name") or ""), prof,
                                         occ_year=year(prof["occ_sched"]),
                                         ltg_year=year(prof["ltg_sched"]),
                                         pwr_year=year(prof["pwr_sched"]),
                                         elem_id=slot, cells=v.get("m_cellList"),
                                         oa_standard=int(v.get("m_eOutdoorAirFlowStandard", 0)),
                                         design_option=int(v.get("m_designOptionId", NO_DESIGN_OPTION)))
    info.update({"day_schedules": len(day_slots), "year_schedules": len(year_slots),
                 "space_types": len(space_slots), "building_types": len(build_slots),
                 "space_profile_use": dict(prof_use.most_common()),
                 "building_profile_use": dict(bprof_use.most_common()),
                 "year_of_key": year_of_key, "day_library_used": [s["key"] for s in lib[:len(day_slots)]]})
    notes += [
        f"day schedules {len(day_slots)} -> OUR schedule library ({len(DAY_SCHEDULES)} named 24-hour "
        f"profiles: {', '.join(s['key'] for s in DAY_SCHEDULES[:8])}, ...); the sample's schedule "
        f"NAMES are free content (the German file localizes them) -> ours",
        f"year schedules {len(year_slots)}: PURE MACHINERY (365 x one day-slot id, uniform 27/27) "
        f"-> REPRODUCED byte-identical, each now wrapping OUR day schedule at its day slot "
        f"(nothing of ours to reject)",
        f"space types {len(space_slots)}: identity = m_eSpaceType + canonical name = the reader's fixed "
        f"space-type LIST (identical in all six samples incl. the German file = the public gbXML / "
        f"ASHRAE space-type ENUMERATION, an interface constant) KEPT; every settings VALUE (LPD / EPD "
        f"/ occupant density / OA rates / setpoints / heat gains / plenum-lighting / carpet + the "
        f"three schedule references) = OUR profile ({len(SPACE_PROFILES)} of our functional "
        f"profiles; classification of the enum = ours; use {dict(prof_use.most_common(6))} ...)",
        f"building types {len(build_slots)}: identity (m_eBuildingType + name = the public building-"
        f"type enum) KEPT; values + equipment operating window + schedules OURS "
        f"({dict(bprof_use.most_common())})",
        "web wiring: space/building types -> OUR year schedules (by role) -> OUR day schedules; "
        "the referrers into the web from OUR settings (EnergyDataSettings -> a building type; the "
        "room -> a space type) keep pointing at valid, now-ours elements (ids preserved)",
    ]
    return RungPlan("ZC_hvac", "the HVAC / energy database web (schedules + space & building types): "
                    "interface enums kept, OUR schedules and OUR settings values, IN PLACE",
                    plans, {}, notes, info=info)


def plan_elec(parent: Parent2) -> RungPlan:
    """ZC_elec: the electrical load-classification / demand-factor catalog ->
    OUR extended load-class library + NEC-cited demand rules, in place
    (the parent's classification <-> demand <-> companion-param wiring by id
    is preserved on both sides)."""
    cls = parent.residue_of("ElectricalLoadClassification")
    dem = parent.residue_of("ElectricalDemandFactorDefinition")
    plans, rep = plan_electrical_layer(parent.doc, cls, dem)
    notes = [
        f"load classifications {len(cls)} -> OUR library (3 reserved roles by the slot's "
        f"m_signitureType: motor 1 / other 2 / spare 3 -- exactly one each per project, 6/6 "
        f"samples -- + {len(cls) - 3} of our regular classes); each keeps its slot's demand-slot "
        f"id and its six ParamElemElectricalLoadClassification companion ids (Group B's ZB1_defs, "
        f"id-wired both sides -- the cleanest cross-group web, endgame section 2 row 6)",
        f"demand factors {len(dem)} -> OUR NEC-cited demand rules: each REFERENCED demand slot gets the "
        f"rule of the classification(s) it serves (rule codes verified on the corpus: 0 constant / 3 "
        f"count ranges / 4 load ranges); {len(rep['unreferenced_demand'])} unreferenced demand slots "
        f"get our extra demand definitions ({', '.join(d['our_rule'] for d in rep['unreferenced_demand'][:6])})",
        f"role slots: {rep['roles']}; shared-demand groups: "
        f"{[(g['demand_slot'], g['size']) for g in rep['groups'] if g['size'] > 1]}; mixed groups "
        f"resolved to no_diversity: {len(rep['mixed_groups'])}",
        "our label templates ('%1!s! - Actual Load', ...) replace Autodesk's phrasing; %1!s! is the "
        "reader's format token (interface)",
    ]
    return RungPlan("ZC_elec", "the electrical load-classification + demand-factor catalog -> OUR "
                    "load classes + NEC-cited demand rules, IN PLACE (id-wired web preserved)",
                    plans, {}, notes, info=rep)


def plan_conduit(parent: Parent2) -> RungPlan:
    """ZC_conduit: the conduit-standard catalog (+ its size table) and the
    cable-tray size list -> OURS (NEC / ANSI / NEMA dimensional facts,
    our selection)."""
    doc = parent.doc
    plans: Dict[int, Obj] = {}
    std_slots = parent.residue_of("ConduitStandardType")
    sizes = parent.residue_of("ConduitSizesElem")
    trays = parent.residue_of("CableTraySizesElem")
    # our standards over the standard slots (in our order); key by our spec key
    std_slot_by_key: Dict[str, int] = {}
    for slot, spec in zip(std_slots, OUR_CONDUIT_STANDARDS):
        plans[slot] = our_conduit_standard(spec, parent.value(slot))
        std_slot_by_key[spec["key"]] = slot
    for slot in sizes:
        plans[slot] = our_conduit_sizes(std_slot_by_key, parent.value(slot))
    for slot in trays:
        plans[slot] = our_cable_tray_sizes(parent.value(slot))
    notes = [
        f"conduit standards {len(std_slots)} -> OURS: "
        f"{[s['name'] for s in OUR_CONDUIT_STANDARDS[:len(std_slots)]]} (the standard names are "
        f"trade designations; the SELECTION is ours)",
        f"conduit size table {len(sizes)}: {len(std_slot_by_key)} standards keyed by the SAME "
        f"standard slots (now ours), each = the trade-size / inner / outer / bend-radius rows of "
        f"NEC Chapter 9 Table 4 (published dimensional FACTS) + Table 2 bend radii",
        f"cable-tray sizes {len(trays)} -> our NEMA VE 1 width list {list(hs.CABLE_TRAY_WIDTHS_IN)} in",
    ]
    return RungPlan("ZC_conduit", "the conduit standards + size table + cable-tray sizes -> OURS "
                    "(NEC / NEMA facts, our selection), IN PLACE", plans, {}, notes,
                    info={"standard_slots": std_slot_by_key})


def plan_systype(parent: Parent2) -> RungPlan:
    """ZC_systype: the residue system-family types -> ours (generic wall /
    floor types over OUR palette materials; ASTM A1064 fabric)."""
    doc = parent.doc
    plans: Dict[int, Obj] = {}
    left: Dict[str, List[int]] = {}
    notes: List[str] = []
    mats = _material_ids_by_name(doc)
    for slot in parent.residue_of("BasicWallType"):
        plans[slot] = our_wall_type(parent.value(slot), mats)
    for slot in parent.residue_of("FloorAttributes"):
        plans[slot] = our_floor_type(parent.value(slot), mats)
    wire_slots = parent.residue_of("FabricWireType")
    for slot in wire_slots:
        plans[slot] = our_fabric_wire_type(parent.value(slot))
    for slot in parent.residue_of("FabricSheetType"):
        v = parent.value(slot)
        wire = int(v.get("m_majorDirectionWireType", INVALID))
        if wire_slots and wire not in wire_slots:
            wire = wire_slots[0]
        plans[slot] = our_fabric_sheet_type(v, wire)
    missing = [n for _f, _w, n in WALL_TYPE["layers"] + FLOOR_TYPE["layers"] if n not in mats]
    notes += [
        f"wall type -> {WALL_TYPE['name']!r}, floor type -> {FLOOR_TYPE['name']!r}: our layer make-up "
        f"over OUR palette materials looked up by name in the parent "
        f"({'ALL FOUND' if not missing else 'MISSING: ' + str(missing)}); each type's LegendComponent "
        f"preview id is KEPT (the preview then displays OUR type -- a type-preview leaves only with its "
        f"type, deletion finding 3)",
        f"fabric: wire -> {FABRIC_WIRE['name']!r} ({FABRIC_WIRE['source']}), sheet -> "
        f"{FABRIC_SHEET['name']!r} ({FABRIC_SHEET['source']}); the sheet's MasterSymbolCell -> "
        f"SlaveSymbolTracker (Group B's reproduced machinery) and its sheet-material slot wiring kept",
    ]
    return RungPlan("ZC_systype", "residue system-family types (wall / floor / welded-wire fabric) "
                    "-> OURS, IN PLACE", plans, left, notes,
                    info={"materials_found": {n: mats.get(n) for _f, _w, n in
                                              WALL_TYPE["layers"] + FLOOR_TYPE["layers"]}})


def plan_analysis(parent: Parent2) -> RungPlan:
    """ZC_analysis: the analysis / area / structural settings machinery ->
    ours or reproduced.  DataStorage + the room's topology are LEFT with
    their stated operations."""
    doc = parent.doc
    plans: Dict[int, Obj] = {}
    left: Dict[str, List[int]] = {}
    notes: List[str] = []
    # ---- AreaTypeElem: pure enum machinery (m_areaSchemeId + m_eSpaceType) ----
    at = parent.residue_of("AreaTypeElem")
    for slot in at:
        plans[slot] = reproduced("AreaTypeElem", parent.value(slot),
                                 "built-in area-type enum row: only its area-scheme wiring (OUR "
                                 "AreaMeasureElems) + the m_eSpaceType enum -- no free value")
    # ---- AreaSchemePlanTopologies: empty holders reproduced; the room's left --
    topo_left = []
    for slot in parent.residue_of("AreaSchemePlanTopologies"):
        v = parent.value(slot)
        content = ((v.get("m_pSet") or {}).get("value") or {}).get("m_set") or []
        if content:
            topo_left.append(slot)                     # the placed room's topology (blocked)
        else:
            plans[slot] = reproduced("AreaSchemePlanTopologies", v,
                                     "empty plan-topology holder (scheme x option) -- machinery")
    if topo_left:
        left["AreaSchemePlanTopologies(room)"] = topo_left
    # ---- AreaReportSettingsElem: our settings overlay -----------------------
    for slot in parent.residue_of("AreaReportSettingsElem"):
        plans[slot] = our_area_report_settings(parent.value(slot))
    # ---- AssemblyCodeTable: OUR EMPTY table --------------------------------
    for slot in parent.residue_of("AssemblyCodeTable"):
        plans[slot] = our_empty_assembly_code_table(parent.value(slot))
    # ---- ColorFillSchema: our schemes ---------------------------------------
    cfs = parent.residue_of("ColorFillSchema")
    for i, slot in enumerate(cfs):
        plans[slot] = our_color_fill_schema(parent.value(slot), i)
    # ---- LoadNature / LoadCase: our structural load standard --------------
    cases = parent.residue_of("LoadCaseElem")
    natures = parent.residue_of("LoadNatureElem")
    nature_set = set(natures)
    nature_named: Dict[int, str] = {}
    for i, c in enumerate(sorted(cases, key=lambda x: (
            LOAD_CASE_ORDER.index(int(parent.value(x).get("m_categoryId", 0)))
            if int(parent.value(x).get("m_categoryId", 0)) in LOAD_CASE_ORDER else 99, x))):
        v = parent.value(c)
        cat = int(v.get("m_categoryId", OST_LoadCasesDead))
        cname = LOAD_CASE_BY_CATEGORY.get(cat, gen(f"Case {i + 1:02d}"))
        plans[c] = our_load_case(cname, i + 1, v)
        nat = int(v.get("m_natureId", INVALID))
        if nat in nature_set and nat not in nature_named:
            nature_named[nat] = LOAD_NATURE_BY_CATEGORY.get(cat, gen(f"Nature {len(nature_named) + 1:02d}"))
    spare_i = 0
    for n in natures:
        v = parent.value(n)
        nm = nature_named.get(n)
        if nm is None:
            spare_i += 1
            nm = gen(f"Nature - Reserved {spare_i:02d}")
        plans[n] = our_load_nature(nm, v)
    # ---- DataStorage: NOT in place (stated) ----------------------------------
    ds = parent.residue_of("DataStorage")
    if ds:
        left["DataStorage(vendor ES blob)"] = ds
    notes += [
        f"AreaTypeElem {len(at)}: PURE MACHINERY (m_areaSchemeId -> OUR area schemes + the built-in "
        f"area-type enum m_eSpaceType, no name / no free value) -> REPRODUCED byte-identical",
        f"AreaSchemePlanTopologies: {sum(1 for s in parent.residue_of('AreaSchemePlanTopologies') if s not in topo_left)} "
        f"EMPTY holders REPRODUCED; {len(topo_left)} (the placed room's, {topo_left}) LEFT byte-identical "
        f"-- it CONTAINS the room's LevelRoomPlan/curves and is pinned by OUR AreaMeasureElem 9490's "
        f"kept wiring (deletion stream finding 2): it leaves with the room constellation",
        f"AreaReportSettingsElem: our text / prefixes / sizes over the slot's unit-format machinery "
        f"(its own fonts + internal categories are already ours from ZA_annot / Z_subcat)",
        "AssemblyCodeTable: OUR EMPTY table -- the slot embeds Autodesk's shipped 795-row UniFormat "
        "classification table (byte-identical in all six samples = PRODUCT DATA) AND an Autodesk "
        "employee's local OneDrive path (an identity leak); both retired at the slot (KeynoteTable "
        "precedent: our empty keynote table)",
        f"ColorFillSchema {len(cfs)}: our schemes -- the (category, key parameter, area scheme, "
        f"by-range) DEFINITION of each slot is its registration (kept); names / titles / entries / "
        f"colours ours (department vocabulary on string-keyed room/space schemes, our area-range "
        f"breakpoints on the by-range scheme, the rest EMPTY = auto-populate, corpus-legal)",
        f"LoadCaseElem {len(cases)} + LoadNatureElem {len(natures)} -> OUR structural load standard: "
        f"cases keep their built-in load-case CATEGORY (an interface enum) + nature-slot wiring, "
        f"names / numbers ours (industry-standard load symbols D/L/Lr/S/W/E/T/Ax); nature NAMES are "
        f"free content (the German file localizes them) -> ours, each nature slot named for the "
        f"category of the case(s) referencing it",
    ]
    if ds:
        notes.append(f"DataStorage {ds}: {NON_INPLACE['DataStorage'][0]} -- {NON_INPLACE['DataStorage'][1]}")
    return RungPlan("ZC_analysis", "analysis / area / structural settings: area-type + topology "
                    "machinery reproduced, our area-report settings, our EMPTY assembly-code table, "
                    "our colour schemes, our load cases / natures, IN PLACE",
                    plans, left, notes)


def plan_browse(parent: Parent2) -> RungPlan:
    """ZC_browse: the surplus browser organizations -> our extra
    organizations; the drafting/sheet-view constellation ADOPTED (OUR sheet
    identity, link overrides emptied) + its drawing reproduced.  The link
    pair is LEFT with its stated operation."""
    plans: Dict[int, Obj] = {}
    left: Dict[str, List[int]] = {}
    notes: List[str] = []
    bo = parent.residue_of("BrowserOrganization")
    lib = list(BROWSER_ORGANIZATIONS_EXTRA)
    # match specs to slots BY TREE TYPE (views slots get views schemes)
    views_specs = [s for s in lib if s["type"] == "views"]
    sheets_specs = [s for s in lib if s["type"] == "sheets"]
    used = 0
    for slot in bo:
        v = parent.value(slot)
        pool = views_specs if int(v.get("m_type", 0)) == 0 else sheets_specs
        if not pool:
            pool = lib
        spec = pool.pop(0) if pool else None
        if spec is None:
            used += 1
            spec = {"name": gen(f"Organization {used:02d}"), "type": "views",
                    "folders": ["BIP_VIEW_FAMILY_AND_TYPE"], "sort": "BIP_VIEW_NAME"}
        plans[slot] = our_browser_organization(spec, v)
    # the sheet view + its drawing
    dv = parent.residue_of("DBViewDrafting")
    dd = parent.residue_of("DBDrawing")
    for slot in dv:
        plans[slot] = our_sheet_view(parent.value(slot))
    for slot in dd:
        plans[slot] = reproduced("DBDrawing", parent.value(slot),
                                 "the sheet's viewport list (its own drafting content + OUR two plan "
                                 "views' viewports) -- pure wiring")
    # the link pair: stated, not touched
    for cls_name in ("RvtLinkSymbol", "RvtLinkInstance"):
        ids = parent.residue_of(cls_name)
        if ids:
            left[f"{cls_name}(external link)"] = ids
            notes.append(f"{cls_name} {ids}: {NON_INPLACE[cls_name][0]} -- {NON_INPLACE[cls_name][1]}")
    notes += [
        f"browser organizations {len(bo)}: the sample's surplus set (Discipline / Type-Discipline / "
        f"Issue Date / Drawn By / Sheet Prefix -- the set our house standard deliberately does NOT "
        f"reproduce) -> {len(lib)} MORE OF OUR organizations "
        f"({[s['name'] for s in BROWSER_ORGANIZATIONS_EXTRA]}) matched to the slots by tree type; "
        f"folder / sort keys are BuiltInParameter interface constants",
        f"the sheet-view constellation ADOPTED (deletion stream finding 9: pinned by OUR plans -> ADOPT): "
        f"DBViewDrafting {dv} = the sheet whose drawing {dd} places OUR two plan views + its own "
        f"drafting content -> OUR sheet {SHEET_IDENTITY['sheet_number']} "
        f"{SHEET_IDENTITY['view_name']!r} (identity tokens ours, view machinery the slot's, "
        f"RvtLinkOverrides display map EMPTIED -- the link symbol's seq-102 pin removed); the drawing "
        f"= REPRODUCED viewport wiring; its viewer 1457029 / viewports / sketch plane are Group B's "
        f"ZB7 companions (already rebuilt at the same ids on Y9)",
    ]
    return RungPlan("ZC_browse", "the surplus browser organizations -> ours + the ADOPTED sheet-view "
                    "constellation (our sheet identity, link overrides emptied), IN PLACE",
                    plans, left, notes)


PLANNERS: Dict[str, Callable[[Parent2], RungPlan]] = {
    "ZC_hvac": plan_hvac, "ZC_elec": plan_elec, "ZC_conduit": plan_conduit,
    "ZC_systype": plan_systype, "ZC_analysis": plan_analysis, "ZC_browse": plan_browse,
}


def merge_plans(plans: Sequence[RungPlan]) -> RungPlan:
    """ZC_deep = every single-group plan applied together (slots are
    disjoint by class; a collision would be a planning defect)."""
    merged: Dict[int, Obj] = {}
    left: Dict[str, List[int]] = {}
    notes: List[str] = []
    info: Dict[str, Any] = {}
    for p in plans:
        for slot, o in p.plans.items():
            if slot in merged:
                raise RuntimeError(f"slot {slot} planned twice ({merged[slot].class_name} / {o.class_name})")
            merged[slot] = o
        for k, v in p.residue_left.items():
            left.setdefault(k, []).extend(v)
        notes.append(f"[{p.name}] {p.notes[0] if p.notes else ''}")
        info[p.name] = {"slots": len(p.plans), "by_class": p.by_class}
    return RungPlan("ZC_deep", "ZA_deep + ALL of this stream's groups (HVAC web, electrical catalog, "
                    "conduit catalogs, system types, analysis machinery, browser + sheet), IN PLACE",
                    merged, left, notes, info=info)


# ===========================================================================
# 12. EMISSION (the residue-A rung emitter, imported) + our reasons
# ===========================================================================
#: reasons for the residue_left keys this stream emits (residue_a.emit_rung
#: looks up NON_INPLACE by key; we patch our own reasons into the report)
LEFT_REASONS: Dict[str, str] = {
    "AreaSchemePlanTopologies": NON_INPLACE["AreaSchemePlanTopologies(room)"][0] + " -- "
                                + NON_INPLACE["AreaSchemePlanTopologies(room)"][1],
    "DataStorage": NON_INPLACE["DataStorage"][0] + " -- " + NON_INPLACE["DataStorage"][1],
    "RvtLinkSymbol": NON_INPLACE["RvtLinkSymbol"][0] + " -- " + NON_INPLACE["RvtLinkSymbol"][1],
    "RvtLinkInstance": NON_INPLACE["RvtLinkInstance"][0] + " -- " + NON_INPLACE["RvtLinkInstance"][1],
}


def emit_rung2(rung: RungPlan, parent: Parent2, out_dir: str = RESIDUE_DIR, *,
               base_certification: Optional[dict] = None,
               control: Optional[dict] = None) -> dict:
    """Emit one ZC rung via the residue-A emitter (validator + structural
    proof + coherence + parity + regdiff sample + byte-delta assertion +
    field-delta table), then patch OUR residue-left reasons and the excluded
    classes into the report."""
    rep = RA.emit_rung(rung, parent, out_dir, base_certification=base_certification,
                       control=control)
    rl = rep.get("residue_left_in_place") or {}
    for k, v in rl.items():
        base_key = k.split("(")[0]
        if base_key in LEFT_REASONS:
            v["reason"] = LEFT_REASONS[base_key]
    rep["reached_by_other_streams_not_reauthored"] = {
        c: r for c, r in REACHED_ELSEWHERE.items()
        if parent.residue.get(c)}
    rep["stream"] = "genesis-residue-A2 (remaining unsubstituted classes, in place, from ZA_deep)"
    RA._write_report(out_dir, rung.name, rep)
    return rep


# ===========================================================================
# 13. THE LADDER DRIVER + probes.json + the residue census
# ===========================================================================

def _v3():
    return RA._v3()


def stage_control(parent_path: str = DEFAULT_PARENT, out_dir: str = RESIDUE_DIR) -> dict:
    """Copy the certified parent byte-for-byte as the batch's CONTROL
    (a control that fails voids the round; upload it with every batch)."""
    import shutil
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, os.path.basename(CTRL_ZA_DEEP))
    shutil.copyfile(parent_path, dst)
    with open(parent_path, "rb") as fh:
        md5 = hashlib.md5(fh.read()).hexdigest()
    return {"file": os.path.relpath(dst, ROOT), "copied_from": os.path.relpath(parent_path, ROOT),
            "md5": md5, "note": "the batch's standing certified control (byte-identical to the "
                                "certified ZA_deep); read FIRST -- a failing control voids the round"}


def write_probes_manifest(reports: Dict[str, dict], parent_path: str = DEFAULT_PARENT,
                          out_dir: str = RESIDUE_DIR, *, base_cert: Optional[dict] = None,
                          control: Optional[dict] = None) -> str:
    """probes.json: ZC_deep FIRST (bisection-first), then the six single-
    group probes, each naming its CERTIFIED base (ZA_deep) + the control,
    the ONE thing it tests, and the reading of each verdict."""
    order = ["ZC_deep"] + RUNG_ORDER
    entries: List[dict] = []
    for i, name in enumerate(order, 1):
        rep = reports.get(name) or {}
        if not rep:
            continue
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        entries.append({
            "order": i, "rung": name, "file": f"{os.path.relpath(out_dir, ROOT)}/{name}.rvt",
            "class_layer_substituted": rep.get("label"),
            "base": {"file": os.path.relpath(parent_path, ROOT), "certification": base_cert},
            "derived_from": os.path.relpath(parent_path, ROOT),
            "passing_sibling": ("ZA_deep (the certified parent) -- PASS-parent + FAIL-here convicts "
                                "exactly THIS group"),
            "the_ONE_thing_it_tests": _rung_tests(name),
            "if_PASS": _rung_if_pass(name), "if_FAIL": _rung_if_fail(name),
            "mechanism": rep.get("mechanism"),
            "elements_substituted_in_place": {"landed": len(rep.get("landed_slots") or []),
                                              "by_class": rep.get("landed_by_class")},
            "residue_left_in_place": {k: v.get("count") for k, v in
                                      (rep.get("residue_left_in_place") or {}).items()},
            "byte_delta": ({k: bd.get(k) for k in ("only_partition_differs", "records_changed_count",
                                                    "expected_slots", "unexpected_changed_ids",
                                                    "records_added_ids", "records_removed_ids",
                                                    "elemtable_identical", "adocument_identical",
                                                    "assertion_holds")} if bd else None),
            "registry_parity": (rep.get("parity") or {}).get("parity"),
            "validator": {"ok": v.get("ok"), "errors": v.get("errors"), "warnings": v.get("warnings")},
            "structural_ok": (rep.get("structural") or {}).get("ok"),
            "document_coherence": rep.get("coherence"),
            "verdict": rep.get("verdict", "not built"),
            "self_check": rep.get("FAILED_SELF_CHECK"),
            "bytes": rep.get("bytes"),
            "control_to_upload_with_batch": control,
            "report": f"{os.path.relpath(out_dir, ROOT)}/{name}.json",
        })
    manifest = {
        "stream": "genesis-residue-A2 (THE REMAINING UNSUBSTITUTED CLASSES -- HVAC / energy web, "
                  "electrical catalog, conduit / tray catalogs, system types, analysis machinery, "
                  "browser + sheet)",
        "situation": (
            "VERDICT #18: ZA_deep (Y9 + Group A's five layers) LOADS -- 1,806/3,342 base elements are "
            "OUR constructors' output, viewer-proven.  The residue disposition list of genesis-residue-A "
            "named the classes the first round did not reach, each with an owning rung; this batch "
            "IS those rungs: each substitutes ONE remaining class group of the CERTIFIED ZA_deep in "
            "place with OUR constructors' objects (or REPRODUCES the pure machinery); ZC_deep is all "
            "of them at once.  What genuinely cannot be substituted in place (the external link, the "
            "vendor DataStorage blob, the room's plan topology) is LISTED with its operation."),
        "the_operation": (
            "In-place substitution (rvt.regadd.substitute_elements, seq 102 only, keep_row): our "
            "constructor's OBJECT replaces the sample's at the SAME element id -- same ElemTable row, "
            "same record position, same registry slots; Global/Latest + Global/ElemTable BYTE-IDENTICAL "
            "to ZA_deep; nothing added, nothing deleted.  Every rung asserts validator 0 errors, the "
            "structural proof, four-registry coherence, registry parity (by construction), a rvt.regdiff "
            "registration-diff sample, the regadd byte-delta table (ONLY the landed slots' object "
            "records change) AND a per-class FIELD-DELTA table naming which object fields carry OUR "
            "value vs the slot's own machinery / wiring / interface identity."),
        "base": {"file": os.path.relpath(parent_path, ROOT), "certification": base_cert,
                 "lineage": ("ZA_deep = the certified Group-A residue rung: Y9 (settings / catalog / "
                             "palette / datum / view constellations) + sub-category layer + "
                             "annotation types & fonts + grids/levels + patterns + appearance assets "
                             "-- viewer PASS (docs/coverage/viewer-certified.json, VERDICTS #18)")},
        "standing_control": control or {"note": "not staged (stage with tools/probe_batch.py)"},
        "controls_discipline": (
            "Upload the batch with the certified CONTROL (a byte-identical copy of ZA_deep: "
            "CTRL_ZA_deep_base.rvt is staged in this directory; tools/probe_batch.py stage adds one "
            "automatically). If the CONTROL fails, the batch is VOID and nothing about our "
            "constructors is read from it."),
        "upload_order_bisection_first": [e["rung"] for e in entries],
        "reading_the_results": {
            "how": ("ZC_deep is the cumulative rung: PASS => every remaining-class constructor of this "
                    "stream (our HVAC schedules / space & building type values over the interface enums, "
                    "our electrical load classes + NEC demand rules, our conduit / tray catalogs, our "
                    "system types + fabric, our analysis settings + empty assembly-code table + colour "
                    "schemes + load standard, our browser organizations + our adopted sheet) loads at "
                    "Autodesk's registrations, and only the LISTED delete-only residue remains "
                    "(link pair, DataStorage, the room's topology + the deletion stream's queues + "
                    "Group B's classes on this base).  ZC_deep FAIL => read the six singles: the "
                    "first FAIL whose parent (ZA_deep) PASSED convicts exactly that group."),
            "ZC_hvac FAIL": ("our HVAC web is rejected: bisect schedules vs types (two further singles) "
                             "-- the space-type values (magnitudes / units / schedule wiring) are the "
                             "prime suspects, the reproduced year schedules cannot fail."),
            "ZC_elec FAIL": ("our load classifications / demand rules are rejected: the field-delta "
                             "names the candidates (label templates, rule rows, role assignment)."),
            "ZC_conduit FAIL": "our conduit standards / size table / tray widths are rejected (a value grammar issue in the size rows).",
            "ZC_systype FAIL": "our wall / floor / fabric types are rejected -- bisect the four slots.",
            "ZC_analysis FAIL": ("one of: the EMPTY assembly-code table shape, our colour-scheme entries, "
                                 "our load cases / natures, the area-report overlay (the reproduced "
                                 "machinery slots cannot fail) -- the field-delta bisects it."),
            "ZC_browse FAIL": ("our browser organizations or the adopted sheet (identity tokens / the "
                               "emptied link overrides) are rejected -- two further singles bisect."),
        },
        "not_in_place_able_with_operation": {k: {"operation": v[0], "reason": v[1]}
                                             for k, v in NON_INPLACE.items()},
        "probes": entries,
        "derivation_chain": ["ZC_deep <- ZA_deep (all groups)"]
                            + [f"{n} <- ZA_deep (single group)" for n in RUNG_ORDER],
    }
    p = os.path.join(out_dir, "probes.json")
    os.makedirs(out_dir, exist_ok=True)
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"\n[probes] wrote {os.path.relpath(p, ROOT)} ({len(entries)} entries)")
    return p


def _rung_tests(name: str) -> str:
    return {
        "ZC_deep": ("Whether the reader accepts ALL of this stream's remaining-class constructors at once "
                    "on the certified ZA_deep: our HVAC schedule library + space / building type values "
                    "over the interface enums, our electrical load classes + NEC demand rules, our "
                    "conduit / cable-tray catalogs, our wall / floor / fabric types, our analysis "
                    "settings (empty assembly-code table, colour schemes, load standard) + reproduced "
                    "machinery, our browser organizations + our adopted sheet."),
        "ZC_hvac": ("Whether the reader accepts OUR HVAC / energy web: 27 day schedules (our library), "
                    "27 reproduced year-schedule wrappers, 125 space types + 33 building types with the "
                    "interface identity kept and every settings value ours."),
        "ZC_elec": ("Whether the reader accepts OUR electrical load classifications (3 reserved roles + 15 "
                    "regular) and OUR NEC-cited demand-factor rules at the sample's id-wired slots."),
        "ZC_conduit": ("Whether the reader accepts OUR conduit standards, our NEC Ch.9 conduit size table "
                       "and our NEMA cable-tray width list."),
        "ZC_systype": ("Whether the reader accepts OUR residue system-family types: a generic interior "
                       "partition, a concrete slab, and an ASTM A1064 fabric wire + sheet."),
        "ZC_analysis": ("Whether the reader accepts the reproduced area machinery, our area-report settings, "
                        "OUR EMPTY assembly-code table, our colour-fill schemes, our load cases / natures."),
        "ZC_browse": ("Whether the reader accepts OUR extra browser organizations and OUR adopted sheet "
                      "(identity tokens ours, link overrides emptied) + its reproduced drawing."),
    }[name]


def _rung_if_pass(name: str) -> str:
    return {
        "ZC_deep": ("EVERY remaining-class constructor loads: the disposition list of genesis-residue-A is "
                    "RETIRED in place; what remains is exactly the listed delete-only residue (link pair, "
                    "DataStorage, the room's topology) + the other streams' queues (curtain / room / dim "
                    "deletions; Group B's classes await the ZAB composition on this base)."),
        "ZC_hvac": ("Our HVAC web is reader-accepted: the space / building type ENUM is confirmed as the "
                    "interface and its VALUES as ours -- the energy layer is authorable."),
        "ZC_elec": "Our electrical load-class + demand-factor catalog is reader-accepted at the id-wired slots.",
        "ZC_conduit": "Our conduit / cable-tray catalogs (NEC / NEMA facts, our selection) are reader-accepted.",
        "ZC_systype": "Our generic system-family types + welded-wire fabric are reader-accepted.",
        "ZC_analysis": ("The reproduced area machinery, our area-report settings, OUR EMPTY assembly-code "
                        "table, our colour schemes and our load standard are reader-accepted (the UniFormat "
                        "product data + the identity leak are retired)."),
        "ZC_browse": ("Our browser organizations + our adopted sheet are reader-accepted; the link symbol's "
                      "seq-102 pin is gone -- the clean-header rung + link deletion is unblocked on the "
                      "view side."),
    }[name]


def _rung_if_fail(name: str) -> str:
    return {
        "ZC_deep": "Read the six singles (all from ZA_deep): the failing single names the rejected group.",
        "ZC_hvac": ("Our HVAC web is rejected: bisect the day-schedule library vs the space / building type "
                    "values (two further single-layer probes); the year-schedule wrappers are byte-identical "
                    "and cannot be the cause."),
        "ZC_elec": ("Our classifications / demand rules are rejected: candidates = the label templates, the "
                    "count / load range rows, the role assignment -- the field-delta table names the fields."),
        "ZC_conduit": "Our conduit / tray catalogs are rejected: the size-row grammar (units / count) is the suspect.",
        "ZC_systype": "Our system types are rejected: bisect wall / floor / fabric (three single-slot probes).",
        "ZC_analysis": ("Bisect: EMPTY assembly-code table shape / colour-scheme entries / load cases + "
                        "natures / area-report overlay -- the reproduced machinery slots cannot be the cause."),
        "ZC_browse": ("Bisect the browser organizations vs the sheet overlay (identity tokens / emptied link "
                      "overrides / the reproduced drawing)."),
    }[name]


def run_ladder(parent_path: str = DEFAULT_PARENT, out_dir: str = RESIDUE_DIR, *,
               only: Sequence[str] = (), skip_deep: bool = False) -> Dict[str, dict]:
    """Build the whole ZC ladder from the CERTIFIED parent (default
    ZA_deep): each single-group rung (each derived DIRECTLY from the parent)
    + ZC_deep (all groups together), then probes.json (bisection-first),
    the staged control and the residue-after census.  Returns {rung:
    report}."""
    V3 = _v3()
    os.makedirs(out_dir, exist_ok=True)
    base_cert = V3.certification_of(parent_path)
    if base_cert is None:
        raise RuntimeError(f"{os.path.relpath(parent_path, ROOT)} is NOT viewer-certified -- a ZC rung "
                           "may only derive from a CERTIFIED file (verdict #15)")
    log(f"[base] {os.path.relpath(parent_path, ROOT)} -- CERTIFIED: {str(base_cert.get('proves'))[:140]}")
    control = stage_control(parent_path, out_dir)
    control["certification"] = base_cert
    log(f"[control] {control['file']} (md5 {control['md5']}) -- upload with EVERY batch")
    t0 = time.time()
    parent = Parent2(parent_path)
    log(f"[parent] {len(parent.doc.et_by_id):,} host elements; ours (Y-ladder + ZA_deep) "
        f"{len(parent.landed):,}; residue classes {len(parent.residue)} ({parent.seconds}s)")
    want = [s.strip() for s in only if s.strip()]
    reports: Dict[str, dict] = {}
    plans: List[RungPlan] = []
    for name in RUNG_ORDER:
        if want and name not in want and "ZC_deep" not in want:
            continue
        t1 = time.time()
        plan = PLANNERS[name](parent)
        log(f"[plan] {name}: {len(plan.plans)} slots {plan.by_class} ({round(time.time() - t1, 1)}s)")
        plans.append(plan)
        if not want or name in want:
            reports[name] = emit_rung2(plan, parent, out_dir, base_certification=base_cert, control=control)
    if not skip_deep and (not want or "ZC_deep" in want):
        deep = merge_plans(plans)
        reports["ZC_deep"] = emit_rung2(deep, parent, out_dir, base_certification=base_cert, control=control)
    write_probes_manifest(reports, parent_path, out_dir, base_cert=base_cert, control=control)
    if "ZC_deep" in reports and (reports["ZC_deep"] or {}).get("verdict") == "VALID":
        zn = residue_after_deep()
        log(f"[Zn] after ZC_deep: {zn['residue_elements']} residue elements in "
            f"{zn['residue_classes']} classes; by disposition {zn['totals_by_disposition']}")
    log("\n=== GROUP-A ROUND-2 (REMAINING CLASSES) LADDER SUMMARY ===")
    for name in ["ZC_deep"] + RUNG_ORDER:
        rep = reports.get(name)
        if not rep:
            continue
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        log(f"  {name:<11} {rep.get('verdict', '?'):<9} validator ok={v.get('ok')} errors={v.get('errors')} "
            f"landed {len(rep.get('landed_slots') or [])} changed {bd.get('records_changed_count', '-')} "
            f"unchanged {bd.get('landed_but_unchanged_slots', '-')} latest-identical "
            f"{bd.get('adocument_identical', '-')}  {rep.get('bytes', 0) or 0:>9,} B")
    log(f"total {time.time() - t0:.1f}s")
    return reports


#: our disposition per residue class of ZC_deep (the honest 'what is left')
def _disposition(cls_name: str, count: int) -> str:
    if cls_name in REACHED_ELSEWHERE:
        return f"other stream: {REACHED_ELSEWHERE[cls_name]}"
    if cls_name in ("RvtLinkSymbol", "RvtLinkInstance", "DataStorage"):
        return f"NOT in-place-able: {NON_INPLACE[cls_name][0]}"
    if cls_name == "AreaSchemePlanTopologies":
        return f"NOT in-place-able: {NON_INPLACE['AreaSchemePlanTopologies(room)'][0]}"
    return "SHOULD BE OURS after ZC_deep (a planning gap if it appears here)"


def residue_after_deep(deep_rvt: str = os.path.join(RESIDUE_DIR, "ZC_deep.rvt"),
                       deep_report: str = os.path.join(RESIDUE_DIR, "ZC_deep.json"),
                       *, save: bool = True) -> dict:
    """The census AFTER ZC_deep: which elements are STILL AUTODESK'S -- the
    Y-ladder + ZA_deep + ZC_deep landed slots vs the file's host elements --
    bucketed by class with our disposition per class.  Written to
    ``<RESIDUE_DIR>/residue_after_ZC_deep.json``."""
    from ..mutate import Document
    landed = RA.ladder_landed(extra_reports=[DEFAULT_PARENT_REPORT, deep_report])
    doc = Document.from_file(deep_rvt)
    counts: collections.Counter = collections.Counter()
    for e in doc.et_by_id:
        if int(e) not in landed:
            counts[doc.class_of(int(e)) or "?"] += 1
    by_class = {c: {"count": n, "disposition": _disposition(c, n)} for c, n in counts.most_common()}
    totals = collections.Counter()
    for c, row in by_class.items():
        totals[row["disposition"].split(":")[0]] += row["count"]
    out = {"subject": os.path.relpath(deep_rvt, ROOT), "elements": len(doc.et_by_id),
           "landed_ours": sum(1 for e in doc.et_by_id if int(e) in landed),
           "residue_elements": sum(counts.values()), "residue_classes": len(counts),
           "residue_by_class": by_class, "totals_by_disposition": dict(totals.most_common()),
           "not_in_place_able": {k: {"operation": v[0], "reason": v[1]} for k, v in NON_INPLACE.items()}}
    if save:
        p = os.path.join(RESIDUE_DIR, "residue_after_ZC_deep.json")
        os.makedirs(RESIDUE_DIR, exist_ok=True)
        with open(p, "w") as fh:
            json.dump(out, fh, indent=1)
        log(f"[census] wrote {os.path.relpath(p, ROOT)}")
    return out


# ===========================================================================
# 14. the census report + demo + CLI
# ===========================================================================

def census_report(parent_path: str = DEFAULT_PARENT, *, save: bool = True) -> dict:
    """The residue census of the parent (this stream's classes) + the
    field-variation census per class -> ``residue_a2/residue_census.json``."""
    from . import residue_b as RB
    parent = Parent2(parent_path)
    doc = parent.doc
    out: Dict[str, Any] = {"parent": os.path.relpath(parent_path, ROOT),
                           "landed_slots": len(parent.landed), "classes": {}}
    mine = sorted({c for cs in CLAIMED_CLASSES.values() for c in cs}
                  | {"RvtLinkSymbol", "RvtLinkInstance", "DataStorage"})
    for cls_name in mine:
        ids = parent.residue_of(cls_name)
        if not ids:
            continue
        cen = RB.census_class(doc, cls_name, ids=ids, max_depth_list=3)
        out["classes"][cls_name] = {
            "residue": len(ids), "ids": ids[:60],
            "rung": next((r for r, cs in CLAIMED_CLASSES.items() if cls_name in cs),
                         (NON_INPLACE.get(cls_name) or ("stated", ""))[0]),
            "constant_fields": cen["constant_fields"],
            "varying_fields": cen["varying_fields"],
        }
    reached = {c: len(parent.residue_of(c)) for c in REACHED_ELSEWHERE if parent.residue_of(c)}
    out["reached_by_other_streams_on_this_base"] = {c: {"count": n, "owner": REACHED_ELSEWHERE[c]}
                                                    for c, n in reached.items()}
    out["totals"] = {"claimed": sum(v["residue"] for c, v in out["classes"].items()
                                     if c not in NON_INPLACE and c not in
                                     ("RvtLinkSymbol", "RvtLinkInstance", "DataStorage")),
                     "not_in_place_able": {c: len(parent.residue_of(c)) for c in
                                           ("RvtLinkSymbol", "RvtLinkInstance", "DataStorage")},
                     "reached_elsewhere": sum(reached.values())}
    if save:
        os.makedirs(RESIDUE_DIR, exist_ok=True)
        p = os.path.join(RESIDUE_DIR, "residue_census.json")
        with open(p, "w") as fh:
            json.dump(out, fh, indent=1, default=str)
        log(f"[census] wrote {os.path.relpath(p, ROOT)}")
    return out


def demo() -> int:
    """Round-trip every PURE constructor (encode -> decode -> re-encode
    byte-exact) with sample arguments."""
    probes = [
        hvac_day_schedule(DAY_SCHEDULES[3]["name"], DAY_SCHEDULES[3]["hours"], elem_id=1),
        hvac_space_type(92, "Office - Enclosed", SPACE_PROFILES["office_enclosed"],
                        occ_year=2, ltg_year=3, pwr_year=4, elem_id=5),
        hvac_building_type(18, "Office", BUILDING_PROFILES["office"],
                           occ_year=2, ltg_year=3, pwr_year=4, elem_id=6),
        our_demand_factor("receptacle", elem_id=7),
        our_demand_factor("welder_group", elem_id=8),
        our_load_classification(LOAD_CLASS_LIBRARY[3],
                                {"m_id": 9, "m_demandFactorId": 7, "m_signitureType": 0}),
        our_load_nature(gen("Dead (D)"), {"m_id": 10}),
        our_load_case(gen("D-1 Self Weight"), 1, {"m_id": 11, "m_categoryId": OST_LoadCasesDead,
                                                    "m_natureId": 10}),
        our_empty_assembly_code_table({"m_id": 12}),
        our_fabric_wire_type({"m_id": 13}),
        our_fabric_sheet_type({"m_id": 14, "m_sheetMaterial": -1, "m_cellList": None}, 13),
        our_conduit_standard(OUR_CONDUIT_STANDARDS[0], {"m_id": 15}),
        our_conduit_sizes({"emt": 15}, {"m_id": 16}),
        our_cable_tray_sizes({"m_id": 17}),
    ]
    fails = 0
    for o in probes:
        rep = RA.check_object(o.class_name, o.value)
        status = "OK  " if rep["ok"] else "FAIL"
        if not rep["ok"]:
            fails += 1
        log(f"  {status} {o.class_name:<34} {rep['bytes']:>6} B  clean={rep['clean']} "
            f"byte_exact={rep['byte_exact']} {rep['errors'] if not rep['ok'] else ''}")
    log(f"\n{len(probes) - fails}/{len(probes)} constructors round-trip byte-exact")
    return 0 if fails == 0 else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--parent", default=DEFAULT_PARENT, help="the CERTIFIED parent (default ZA_deep)")
    ap.add_argument("--out", default=RESIDUE_DIR)
    ap.add_argument("--only", default="", help="comma-separated rung names to build")
    ap.add_argument("--skip-deep", action="store_true")
    ap.add_argument("--census-only", action="store_true")
    ap.add_argument("--derive-enums", action="store_true")
    ap.add_argument("--demo", action="store_true", help="round-trip the pure constructors")
    args = ap.parse_args(argv)
    if args.demo:
        return demo()
    if args.derive_enums:
        enums = derive_hvac_type_enums()
        os.makedirs(RESIDUE_DIR, exist_ok=True)
        with open(ENUMS_FILE, "w") as fh:
            json.dump(enums, fh, indent=1)
        log(f"[enum] wrote {os.path.relpath(ENUMS_FILE, ROOT)}: {len(enums['space_types'])} space "
            f"types, {len(enums['building_types'])} building types")
        return 0
    if args.census_only:
        rep = census_report(args.parent)
        for c, row in rep["classes"].items():
            log(f"  {c:<32} residue {row['residue']:>4}  rung {row['rung']:<12} "
                f"varying {row['varying_fields'][:6]}")
        log(f"  reached elsewhere: {list(rep['reached_by_other_streams_on_this_base'])}")
        return 0
    reports = run_ladder(args.parent, args.out,
                         only=[s for s in args.only.split(",") if s.strip()],
                         skip_deep=args.skip_deep)
    bad = [n for n, r in reports.items() if r.get("verdict") != "VALID"]
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())

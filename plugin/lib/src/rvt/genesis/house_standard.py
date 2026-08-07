"""rvt.genesis.house_standard -- OUR HOUSE STANDARD: the default CONTENT of a
genesis document, authored by us as PLAIN DATA + rationale, driving the proven
constructors of :mod:`rvt.genesis.types` and :mod:`rvt.genesis.skeleton`.

Why this exists (docs/inbox/genesis-audit.md, TRACKER P0 gate G1 sub-gates
G1b / G1c): our constructors WORK, but the values the first genesis
candidate fed them reproduced Autodesk stock settings (ElectricalSetting
46/49 fields identical to the rme sample's; view / base-point / phase
elements structurally 0.8-0.95 similar to sample specimens) and our records
embed Autodesk resource identifiers (``assetlibrary_base.fbx``,
``SunAndSky-002``, ``%1!s!`` MACH label strings, Forge unit typeIds).
This module retires both:

* **G1b OWN VALUES.**  Every value below is one of THREE things and is
  labelled which: a physical / regulatory FACT (cited to a public source --
  facts are not authorship), a public STANDARD (cited), or a value INVENTED
  BY US (our house convention).  Nothing is copied from an Autodesk sample or
  template; where a class leaves no free choice (a survey point IS the model
  origin; a copper conductor IS named "Copper") the record says so instead
  of pretending an authored value exists.

* **G1c RESOURCE IDENTIFIERS.**  :data:`RESOURCE_ID_DISPOSITIONS` inventories
  every Autodesk identifier our constructors would otherwise emit and states
  its disposition: (a) DROP, (b) REPLACE with ours, or (c) REQUIRED FORMAT
  TOKEN (an interface identifier the reader keys on -- argued for counsel).
  Dispositions (a)/(b) that the constructors do not yet parameterise are
  applied here as documented SHIMS over the constructor output (this module
  edits only its own returned dicts, never the constructor modules); the
  exact constructor diffs that make each shim unnecessary are listed in
  :data:`CONSTRUCTOR_DIFFS` for the orchestrator.

Public API::

    cat = build_catalog(start_id=1_500_000)          # everything we author
    cat.roundtrip()          # schema round-trip proof (all records byte-exact)
    cat.dangling()           # self-containment (references only OUR ids)
    cat.identifier_scan()    # Autodesk identifiers remaining in the bytes
    similarity_report(cat)   # max shingle similarity vs ALL SIX samples
    RESOURCE_ID_DISPOSITIONS, CONSTRUCTOR_DIFFS, NO_FREE_CHOICE, FINDINGS

Naming convention: our type/definition names carry the ``GEN`` prefix (the
tekton genesis house prefix) so anything WE authored is greppable in a
delivered document and never collides with template names.

TERRITORY: this module CALLS the public constructors of
:mod:`rvt.genesis.types` / :mod:`rvt.genesis.skeleton`; it does not modify
them (parallel workstreams own those files).

Demo::

    python -m rvt.genesis.house_standard              # build + verify
    python -m rvt.genesis.house_standard --similarity # + six-sample similarity
"""
from __future__ import annotations

import json
import math
import re
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import skeleton as sk
from . import types as ty
from .skeleton import _ptr as _skel_ptr          # pointer-token shape helper

# ---------------------------------------------------------------------------
# 0. HOUSE VOCABULARY
# ---------------------------------------------------------------------------

#: OUR name prefix for every authored type / definition (invented by us).
PREFIX = "GEN"

INVALID = ty.INVALID
BLACK = 0
SOLID_LINE = ty.LINEPATTERN_SOLID     # built-in "solid" line-pattern sentinel
                                       # (-3000010: a format sentinel, no content)


def rgb(r: int, g: int, b: int) -> int:
    """(r,g,b) 0-255 -> Windows COLORREF (r | g<<8 | b<<16)."""
    return ty.rgb(r, g, b)


def gen(name: str) -> str:
    """Prefix an authored name with our house prefix."""
    return f"{PREFIX} {name}"


# ---------------------------------------------------------------------------
# 1. IDENTITY -- who this document says it is (INVENTED BY US)
# ---------------------------------------------------------------------------

#: Project-information element + partatom metadata source of truth.  These
#: are OUR placeholders for a genesis BASE document (a real job replaces them
#: from the job spec).  Author = the writer's product identity placeholder
#: (counsel item C1 decides the final string; see rvt.identity).
PROJECT_INFO: Dict[str, str] = {
    "project_name": "GENESIS Base",
    "project_number": "GEN-0000",
    "address": "",
    "client_name": "tekton genesis",
    "project_status": "Genesis Baseline",
    "issue_date": "2026-08-03",
    "organization_name": "tekton",
    "organization_description": "genesis base document authored by our writer",
    "building_name": "Genesis Base",
    "author": "rvt-writer",
}

# ---------------------------------------------------------------------------
# 2. UNITS registry (project display-unit settings)
# ---------------------------------------------------------------------------
# The KEYS of the format map are Forge measurable-spec typeIds and the unit /
# symbol values are Forge unit typeIds.  These strings are the INTERFACE the
# reader looks units up by (identical in every 2026 file; the ADocument's
# sealed Forge schema corpus enumerates the vocabulary) -- listed as REQUIRED
# FORMAT TOKENS in RESOURCE_ID_DISPOSITIONS (row "forge-typeids").  The CHOICE
# of display unit, symbol and precision per spec is a project setting = ours.
#
# Every typeId string below was VERIFIED PRESENT in the 2026 corpus (sample
# UnitsElem maps for the spec keys; the Forge unit corpus inside Global/Latest
# for the imperial unit/symbol ids).  NOTE: rvt.genesis.skeleton's
# DEFAULT_UNIT_FORMATS keys length/area/volume/angle/number as ``-2.0.0``
# spec ids and uses ``feetFractionalInches`` -- neither appears in the 2026
# corpus (the samples key ``autodesk.spec.aec:length-1.0.0`` etc.); that list
# is superseded here (finding F-HS-1).
#
# accuracy = the display precision in the unit's own value (0.0625 in = 1/16").

#: OUR IMPERIAL house set (US practice: our two disciplines' specs).  Each
#: row: (spec typeId, unit typeId, symbol typeId or None, accuracy).  Choices
#: (unit + precision) are ours; electrical / lighting / structural specs use
#: SI-derived units because those quantities HAVE no imperial alternative
#: in practice (amperes, volts, VA, lux, hertz) -- a physical fact.
UNIT_FORMATS_IMPERIAL: List[Tuple[str, str, Optional[str], float]] = [
    # -- common ------------------------------------------------------------
    ("autodesk.spec.aec:length-1.0.0", "autodesk.unit.unit:feet-1.0.1",
     "autodesk.unit.symbol:feetAndInches-1.0.1", 1.0 / 256.0),      # to 1/256"
    ("autodesk.spec.aec:area-1.0.0", "autodesk.unit.unit:squareFeet-1.0.1",
     "autodesk.unit.symbol:sf-1.0.1", 0.01),
    ("autodesk.spec.aec:volume-1.0.0", "autodesk.unit.unit:cubicFeet-1.0.1",
     "autodesk.unit.symbol:cf-1.0.1", 0.01),
    ("autodesk.spec.aec:angle-1.0.0", "autodesk.unit.unit:degrees-1.0.1",
     "autodesk.unit.symbol:degree-1.0.1", 0.01),
    ("autodesk.spec.aec:slope-1.0.0", "autodesk.unit.unit:slopeDegrees-1.0.0",
     "autodesk.unit.symbol:slopeDegree-1.0.0", 0.01),
    ("autodesk.spec.aec:number-1.0.0", "autodesk.unit.unit:general-1.0.1", None, 1e-06),
    ("autodesk.spec.aec:massDensity-1.0.0",
     "autodesk.unit.unit:poundsMassPerCubicFoot-1.0.1",
     "autodesk.unit.symbol:lbMassPerFtSup3-1.0.1", 0.01),
    ("autodesk.spec.aec:decimalSheetLength-1.0.0", "autodesk.unit.unit:inches-1.0.1",
     "autodesk.unit.symbol:inchDoubleQuote-1.0.1", 1.0 / 32.0),
    ("autodesk.spec.aec:sheetLength-1.0.0", "autodesk.unit.unit:inches-1.0.1",
     "autodesk.unit.symbol:inchDoubleQuote-1.0.1", 1.0 / 32.0),
    # -- electrical (SI: no imperial alternative exists = fact) ----------
    ("autodesk.spec.aec.electrical:current-1.0.0", "autodesk.unit.unit:amperes-1.0.0",
     "autodesk.unit.symbol:ampere-1.0.0", 0.1),
    ("autodesk.spec.aec.electrical:potential-1.0.0", "autodesk.unit.unit:volts-1.0.1",
     "autodesk.unit.symbol:volt-1.0.1", 0.1),
    ("autodesk.spec.aec.electrical:apparentPower-1.0.0",
     "autodesk.unit.unit:voltAmperes-1.0.1", "autodesk.unit.symbol:vA-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:power-1.0.0", "autodesk.unit.unit:watts-1.0.1",
     "autodesk.unit.symbol:watt-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:wattage-1.0.0", "autodesk.unit.unit:watts-1.0.1",
     "autodesk.unit.symbol:watt-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:frequency-1.0.0", "autodesk.unit.unit:hertz-1.0.1",
     "autodesk.unit.symbol:hz-1.0.1", 0.1),
    ("autodesk.spec.aec.electrical:illuminance-1.0.0", "autodesk.unit.unit:footcandles-1.0.1",
     "autodesk.unit.symbol:fc-1.0.1", 0.1),
    ("autodesk.spec.aec.electrical:luminousFlux-1.0.0", "autodesk.unit.unit:lumens-1.0.1",
     "autodesk.unit.symbol:lm-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:wireDiameter-1.0.0", "autodesk.unit.unit:inches-1.0.1",
     "autodesk.unit.symbol:inchDoubleQuote-1.0.1", 0.001),
    ("autodesk.spec.aec.electrical:conduitSize-1.0.0", "autodesk.unit.unit:inches-1.0.1",
     "autodesk.unit.symbol:inchDoubleQuote-1.0.1", 0.125),      # trade sizes are 1/8"-ish
    ("autodesk.spec.aec.electrical:cableTraySize-1.0.0", "autodesk.unit.unit:inches-1.0.1",
     "autodesk.unit.symbol:inchDoubleQuote-1.0.1", 0.5),
    ("autodesk.spec.aec.electrical:demandFactor-1.0.0", "autodesk.unit.unit:percentage-1.0.1",
     "autodesk.unit.symbol:percent-1.0.1", 0.01),
    ("autodesk.spec.aec.electrical:powerDensity-1.0.0",
     "autodesk.unit.unit:wattsPerSquareFoot-1.0.1",
     "autodesk.unit.symbol:wPerFtSup2-1.0.1", 0.01),
    ("autodesk.spec.aec.electrical:temperature-1.0.0", "autodesk.unit.unit:fahrenheit-1.0.1",
     "autodesk.unit.symbol:degreeF-1.0.1", 0.1),
    ("autodesk.spec.aec.electrical:temperatureDifference-1.0.0",
     "autodesk.unit.unit:fahrenheitInterval-1.0.1",
     "autodesk.unit.symbol:deltaDegreeF-1.0.1", 0.1),
]

#: The METRIC alternate (a metric-market job overrides the registry with it).
UNIT_FORMATS_METRIC: List[Tuple[str, str, Optional[str], float]] = [
    ("autodesk.spec.aec:length-1.0.0", "autodesk.unit.unit:millimeters-1.0.1",
     "autodesk.unit.symbol:mm-1.0.1", 1.0),
    ("autodesk.spec.aec:area-1.0.0", "autodesk.unit.unit:squareMeters-1.0.1",
     "autodesk.unit.symbol:mSup2-1.0.1", 0.01),
    ("autodesk.spec.aec:volume-1.0.0", "autodesk.unit.unit:cubicMeters-1.0.1",
     "autodesk.unit.symbol:mSup3-1.0.1", 0.001),
    ("autodesk.spec.aec:angle-1.0.0", "autodesk.unit.unit:degrees-1.0.1",
     "autodesk.unit.symbol:degree-1.0.1", 0.01),
    ("autodesk.spec.aec:slope-1.0.0", "autodesk.unit.unit:slopeDegrees-1.0.0",
     "autodesk.unit.symbol:slopeDegree-1.0.0", 0.01),
    ("autodesk.spec.aec:number-1.0.0", "autodesk.unit.unit:general-1.0.1", None, 1e-06),
    ("autodesk.spec.aec:massDensity-1.0.0",
     "autodesk.unit.unit:kilogramsPerCubicMeter-1.0.1",
     "autodesk.unit.symbol:kgPerMSup3-1.0.1", 0.01),
    ("autodesk.spec.aec.electrical:current-1.0.0", "autodesk.unit.unit:amperes-1.0.0",
     "autodesk.unit.symbol:ampere-1.0.0", 0.1),
    ("autodesk.spec.aec.electrical:potential-1.0.0", "autodesk.unit.unit:volts-1.0.1",
     "autodesk.unit.symbol:volt-1.0.1", 0.1),
    ("autodesk.spec.aec.electrical:apparentPower-1.0.0",
     "autodesk.unit.unit:voltAmperes-1.0.1", "autodesk.unit.symbol:vA-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:power-1.0.0", "autodesk.unit.unit:watts-1.0.1",
     "autodesk.unit.symbol:watt-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:illuminance-1.0.0", "autodesk.unit.unit:lux-1.0.1",
     "autodesk.unit.symbol:lx-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:luminousFlux-1.0.0", "autodesk.unit.unit:lumens-1.0.1",
     "autodesk.unit.symbol:lm-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:wireDiameter-1.0.0", "autodesk.unit.unit:millimeters-1.0.1",
     "autodesk.unit.symbol:mm-1.0.1", 0.01),
    ("autodesk.spec.aec.electrical:conduitSize-1.0.0", "autodesk.unit.unit:millimeters-1.0.1",
     "autodesk.unit.symbol:mm-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:cableTraySize-1.0.0", "autodesk.unit.unit:millimeters-1.0.1",
     "autodesk.unit.symbol:mm-1.0.1", 1.0),
    ("autodesk.spec.aec.electrical:temperature-1.0.0", "autodesk.unit.unit:celsius-1.0.1",
     "autodesk.unit.symbol:degreeC-1.0.1", 0.1),
]

#: unit-system flag for UnitsElem.m_universalUnitSystem (1 = imperial,
#: 0 = metric [INFERRED, skeleton spec]) + decimal / grouping symbols
#: (0 = ".", 1 = ",", grouping amount 3 digits).  Ours: US convention.
UNIT_SYSTEM_FLAGS = {
    "imperial": {"universal_unit_system": 1, "decimal_symbol": 0,
                 "digit_grouping_symbol": 1, "digit_grouping_amount": 3},
    "metric": {"universal_unit_system": 0, "decimal_symbol": 0,
               "digit_grouping_symbol": 1, "digit_grouping_amount": 3},
}

# ---------------------------------------------------------------------------
# 3. SITE & SUN (neutral, non-Autodesk defaults)
# ---------------------------------------------------------------------------
# Autodesk's stock site is its Waltham, MA headquarters (42.387 N,
# -71.242 W, TZ -5, weather station "52939_2004") in EVERY sample -- the
# skeleton's default lat/long inherit exactly that.  OUR base document is
# location-neutral: latitude 0 / longitude 0 ("null island", the WGS-84
# origin -- a coordinate FACT with no proprietary provenance), UTC, no
# weather station, and NEUTRAL climate data = the ISO 2533 International
# Standard Atmosphere sea-level temperature (15 degC = 288.15 K) in every
# design-day slot [FACT: ISO 2533:1975], replacing Revit's stock design-day
# temperature arrays.  A real job overwrites all of this from its address.
SITE: Dict[str, Any] = {
    "site_symbol_name": "",                 # samples leave the GeoSite symbol unnamed
    "internal_location_name": gen("Internal Origin"),
    "project_location_name": gen("Project Position"),
    "latitude_deg": 0.0,
    "longitude_deg": 0.0,
    "timezone_h": 0.0,
    "place_name": "",
    "weather_station": "",
    "postal_code": "",
    "elevation_m": 0.0,
    #: ISO 2533 standard-atmosphere temperature, kelvin (fact)
    "isa_temperature_K": 288.15,
    "clearness_number": 1.0,               # dimensionless nominal (no haze)
}

#: OUR still-sun study default: sun due SOUTH (azimuth 180 deg from north)
#: at 45 deg altitude -- a neutral, hemisphere-agnostic study angle chosen by
#: us (Autodesk's stock is azimuth 135 / altitude 35).  The name is ours.
SUN: Dict[str, Any] = {
    "name": gen("Still Sun - South 45"),
    "azimuth_deg": 180.0,
    "altitude_deg": 45.0,
}

#: True-north rotation of the base document = 0 (project north == true
#: north until a job sets it -- a definitional zero, not content); poche
#: (site section earth-hatch) depth is OUR drafting choice: 6 ft.
TRUE_NORTH_ANGLE_DEG = 0.0
POCHE_DEPTH_FT = 6.0

# ---------------------------------------------------------------------------
# 4. LEVELS (datums)
# ---------------------------------------------------------------------------
# OUR level naming convention: "L<n> - <description>" (invented by us; NOT
# Revit's template "Level 1"/"Level 2").  Default storey height 12'-0"
# (our institutional / mixed-use floor-to-floor default; a job overrides it).
# Levels are DATUM elements -- the ledger reports (does not gate) them.
STOREY_HEIGHT_FT = 12.0
LEVELS: List[Dict[str, Any]] = [
    {"key": "L1", "name": "L1 - Ground Floor", "elevation_ft": 0.0},
    {"key": "L2", "name": "L2 - Second Floor", "elevation_ft": STOREY_HEIGHT_FT},
]
#: our level-head TYPE (its head symbol is deliberately unset: level heads
#: are loadable annotation content -> the G4 content gate, not genesis)
LEVEL_TYPE_NAME = gen("Level Head - Circle")
#: room computation height above the level: 4'-0" (our practice: the
#: horizontal cut at which room boundaries are evaluated)
ROOM_COMPUTATION_HEIGHT_FT = 4.0
#: datum line drawn length in views (a graphic default, ours)
LEVEL_DATUM_LENGTH_FT = 40.0

# ---------------------------------------------------------------------------
# 5. PHASES -- our wording, our filter set (semantics DECODED, ours by design)
# ---------------------------------------------------------------------------
# Revit's templates ship phases "Existing"/"New Construction" and filters
# "Show All", "Show Previous + Demo", ... (product terminology + vectors).
# We author OUR OWN two phases and OUR OWN filter SET.
#
# DECODED this session (was INFERRED-only in the skeleton spec): the 7-slot
# ``m_phaseStatusPresentation`` vector = per phase-STATUS display state with
#   slot 2 = EXISTING, slot 3 = DEMOLISHED, slot 4 = NEW, slot 5 = TEMPORARY
#   value 0 = NOT DISPLAYED, 1 = BY CATEGORY, 2 = OVERRIDDEN
# (proof: rst/rme/rac "Show New" [0,0,0,0,1,0,0] = New by-category only;
# "Show Complete" [0,0,1,0,1,0,0] = Existing+New by category; "Show All"
# [0,0,2,2,1,2,0] = New by-category, Existing/Demolished/Temporary
# overridden).  Slots 0, 1, 6 are 0 in every corpus filter (unused).
# Given the encoding, our filter set is a designed set of combinations:
NOT_DISPLAYED, BY_CATEGORY, OVERRIDDEN = 0, 1, 2


def phase_presentation(*, existing: int = NOT_DISPLAYED,
                       demolished: int = NOT_DISPLAYED,
                       new: int = NOT_DISPLAYED,
                       temporary: int = NOT_DISPLAYED) -> List[int]:
    """Build the 7-slot presentation vector from named phase-status states."""
    return [0, 0, int(existing), int(demolished), int(new), int(temporary), 0]


#: OUR phases (names + descriptions invented by us).
PHASES: List[Dict[str, str]] = [
    {"key": "existing", "name": "Existing Conditions",
     "description": "Elements in place before our scope of work begins"},
    {"key": "new", "name": "New Work",
     "description": "Elements constructed under this scope of work"},
]

#: OUR phase-filter set: (name, is_default, presentation).  Four of the five
#: combinations differ from every shipped Autodesk filter vector; "New
#: Work Only" necessarily coincides with the corpus 'Show New' vector -- the
#: intent "show only new work" has exactly one encoding (documented, not a
#: copy).  All names are ours.
PHASE_FILTERS: List[Tuple[str, bool, List[int]]] = [
    (gen("All Phases"), True,
     phase_presentation(existing=BY_CATEGORY, demolished=BY_CATEGORY,
                        new=BY_CATEGORY, temporary=BY_CATEGORY)),
    (gen("Existing Conditions Only"), False,
     phase_presentation(existing=BY_CATEGORY)),
    (gen("Demolition Plan"), False,
     phase_presentation(existing=BY_CATEGORY, demolished=OVERRIDDEN)),
    (gen("New Work Only"), False,
     phase_presentation(new=BY_CATEGORY)),
    (gen("Construction Set (Existing + New + Temporary)"), False,
     phase_presentation(existing=OVERRIDDEN, new=BY_CATEGORY, temporary=BY_CATEGORY)),
]

#: OUR phase-status graphic overrides (the AllProjectPhases table): how
#: EXISTING / DEMOLISHED / NEW / TEMPORARY elements read when a filter says
#: "overridden".  A firm's own drafting convention (existing = light grey,
#: demolition = grey dashed, new = full black weight, temporary = blue-grey
#: dashed); pen numbers refer to OUR pen weights.  status codes 2..5 =
#: Existing/Demolished/New/Temporary (schema enum).  COLORREF ints.
PHASE_STATUS_GRAPHICS: List[Dict[str, Any]] = [
    {"status": 2, "role": "existing", "proj_pen": 1, "cut_pen": 2,
     "pen_color": rgb(140, 140, 140), "cut_fill_visible": True,
     "cut_fill_color": rgb(200, 200, 200), "line": "solid", "material": "existing"},
    {"status": 3, "role": "demolished", "proj_pen": 1, "cut_pen": 1,
     "pen_color": rgb(110, 110, 110), "cut_fill_visible": False,
     "cut_fill_color": rgb(255, 255, 255), "line": "hidden", "material": "demolition"},
    {"status": 4, "role": "new", "proj_pen": 1, "cut_pen": 4,
     "pen_color": BLACK, "cut_fill_visible": True,
     "cut_fill_color": BLACK, "line": "solid", "material": "new"},
    {"status": 5, "role": "temporary", "proj_pen": 1, "cut_pen": 1,
     "pen_color": rgb(70, 90, 140), "cut_fill_visible": True,
     "cut_fill_color": rgb(200, 205, 220), "line": "hidden", "material": "temporary"},
]

# ---------------------------------------------------------------------------
# 6. DRAFTING PATTERNS (ours: dash rhythms / hatch spacings we chose)
# ---------------------------------------------------------------------------
#: line patterns: name -> segment list [(kind, length_mm)].  Rhythms chosen
#: for legibility at 1/8"=1'-0" (~1:100) plotting.
LINE_PATTERNS: List[Dict[str, Any]] = [
    {"key": "dash", "name": gen("Dash 3mm"),
     "segments": [("dash", 3.0), ("space", 3.0)]},
    {"key": "hidden", "name": gen("Hidden 2mm"),
     "segments": [("dash", 2.0), ("space", 1.5)]},
    {"key": "centre", "name": gen("Centre 8mm"),
     "segments": [("dash", 8.0), ("space", 2.0), ("dash", 2.0), ("space", 2.0)]},
    {"key": "demo", "name": gen("Demolition 4mm"),
     "segments": [("dash", 4.0), ("space", 2.0)]},
]

#: fill patterns: name -> grid list (drafting/symbolic, sheet-scaled).  An
#: empty grid list = SOLID.  Spacings/angles are our drafting standard.
FILL_PATTERNS: List[Dict[str, Any]] = [
    {"key": "solid", "name": gen("Solid Fill"), "grids": []},
    {"key": "crosshatch", "name": gen("Diagonal Crosshatch 3mm"),
     "grids": [{"angle_deg": 45, "spacing_mm": 3.0}, {"angle_deg": 135, "spacing_mm": 3.0}]},
    {"key": "diagonal", "name": gen("Diagonal Up 4mm"),
     "grids": [{"angle_deg": 45, "spacing_mm": 4.0}]},
    {"key": "insulation", "name": gen("Insulation Batting 6mm"),
     "grids": [{"angle_deg": 0, "spacing_mm": 6.0}, {"angle_deg": 90, "spacing_mm": 6.0}]},
    {"key": "sand", "name": gen("Sand Stipple 1.5mm"),
     "grids": [{"angle_deg": 45, "spacing_mm": 1.5, "dashes_mm": [0.4, 2.6]}]},
]

# ---------------------------------------------------------------------------
# 7. MATERIALS (graphics-only; representational colours chosen by us)
# ---------------------------------------------------------------------------
#: name, shaded RGB (a plausible on-screen colour for the substance --
#: appearance is a fact of the material; the exact RGB is our pick),
#: material class / category strings (our library taxonomy), transparency,
#: cut pattern key.  NO appearance/render asset (see resource disposition
#: "material-asset-descriptor": Autodesk's ``Generic`` /
#: ``assetlibrary_base.fbx`` asset binding is DROPPED).
MATERIALS: List[Dict[str, Any]] = [
    {"key": "concrete", "name": gen("Concrete, Cast-in-Place"), "rgb": (200, 198, 192),
     "material_class": "Concrete", "category": "Concrete", "cut_pattern": "crosshatch"},
    {"key": "cmu", "name": gen("Concrete Masonry Units"), "rgb": (172, 168, 158),
     "material_class": "Masonry", "category": "Masonry", "cut_pattern": "diagonal"},
    {"key": "gypsum", "name": gen("Gypsum Wall Board"), "rgb": (246, 246, 240),
     "material_class": "Gypsum Board", "category": "Interior Finish"},
    {"key": "stud", "name": gen("Metal Stud Framing"), "rgb": (168, 168, 178),
     "material_class": "Metal", "category": "Framing"},
    {"key": "steel", "name": gen("Steel, Structural"), "rgb": (150, 152, 160),
     "material_class": "Metal", "category": "Structure", "cut_pattern": "solid"},
    {"key": "insulation", "name": gen("Rigid Insulation"), "rgb": (250, 240, 200),
     "material_class": "Insulation", "category": "Thermal", "cut_pattern": "insulation"},
    {"key": "glass", "name": gen("Glass, Clear"), "rgb": (198, 220, 236),
     "material_class": "Glass", "category": "Glazing", "transparency": 0.7},
    {"key": "wood", "name": gen("Wood, Softwood Lumber"), "rgb": (204, 178, 140),
     "material_class": "Wood", "category": "Framing"},
    {"key": "earth", "name": gen("Earth"), "rgb": (140, 116, 88),
     "material_class": "Earth", "category": "Site", "cut_pattern": "sand"},
    # the four phase-status materials OUR phasing overrides reference
    {"key": "existing", "name": gen("Phase - Existing"), "rgb": (176, 176, 176),
     "material_class": "Phase", "category": "Phasing"},
    {"key": "demolition", "name": gen("Phase - Demolition"), "rgb": (140, 140, 140),
     "material_class": "Phase", "category": "Phasing", "transparency": 0.5},
    {"key": "new", "name": gen("Phase - New"), "rgb": (224, 224, 224),
     "material_class": "Phase", "category": "Phasing"},
    {"key": "temporary", "name": gen("Phase - Temporary"), "rgb": (206, 206, 216),
     "material_class": "Phase", "category": "Phasing", "transparency": 0.5},
]

# ---------------------------------------------------------------------------
# 8. SYSTEM-FAMILY TYPES (our assemblies; layer thicknesses are the real
#    product dimensions -- 5/8" gypsum board, 3-5/8" (92 mm) steel stud,
#    nominal 8" (190 mm actual) CMU: facts of construction products)
# ---------------------------------------------------------------------------
WALL_TYPES: List[Dict[str, Any]] = [
    {"name": gen("Interior - 124mm Gypsum Partition"),
     "layers": [("finish2", 16.0, "gypsum"), ("structure", 92.0, "stud"),
                ("finish1", 16.0, "gypsum")],
     "function": 0, "fill": None,
     "rationale": "5/8 in gypsum board each side of a 3-5/8 in (92 mm) steel stud"},
    {"name": gen("Exterior - 200mm CIP Concrete"),
     "layers": [("structure", 200.0, "concrete")], "function": 1, "fill": "solid",
     "rationale": "single 200 mm cast-in-place concrete structural layer"},
    {"name": gen("Interior - 190mm CMU"),
     "layers": [("structure", 190.0, "cmu")], "function": 0, "fill": "diagonal",
     "rationale": "nominal 8 in concrete block (190 mm actual)"},
]
FLOOR_TYPES: List[Dict[str, Any]] = [
    {"name": gen("Slab on Grade - 150mm Concrete"),
     "layers": [("structure", 150.0, "concrete")],
     "rationale": "150 mm structural concrete slab"},
]
ROOF_TYPES: List[Dict[str, Any]] = [
    {"name": gen("Roof - Concrete Deck 200mm with Insulation"),
     "layers": [("finish1", 60.0, "insulation"), ("structure", 200.0, "concrete")],
     "rationale": "60 mm rigid insulation over 200 mm concrete deck"},
]
CEILING_TYPES: List[Dict[str, Any]] = [
    {"name": gen("Ceiling - 16mm GWB on Furring"),
     "layers": [("finish2", 16.0, "gypsum"), ("structure", 38.0, "stud")],
     "rationale": "5/8 in gypsum on 1-1/2 in (38 mm) furring"},
]
#: preview-sample geometry every wall type carries (a modelling default:
#: the type's preview/cut sample height); OUR value 20'-0" = 6096 mm.
WALL_SAMPLE_HEIGHT_MM = 6096.0

# ---------------------------------------------------------------------------
# 9. ELECTRICAL HOUSE STANDARD (facts + public code data + our conventions)
# ---------------------------------------------------------------------------
# All voltage / demand / conduit / wire VALUES below are published FACTS
# (ANSI / NEMA / NFPA 70 = NEC).  Type NAMES and the SELECTION are ours.

#: OUR voltage definitions.  min/max = ANSI C84.1 Range A service-voltage
#: limits (+-5 % of nominal) [FACT: ANSI C84.1-2020, Table 1 -- Range A
#: service voltage].  (Note: rvt.genesis.types.NOMINAL_VOLTAGE_RANGES holds
#: the ROUNDED Autodesk template values 110/130 etc., not C84.1 -- superseded
#: here, finding F-HS-2; we always pass explicit min/max.)
def _c84_range_a(nominal: float) -> Tuple[float, float]:
    """ANSI C84.1 Range A service voltage = nominal +-5 %."""
    return (round(nominal * 0.95, 1), round(nominal * 1.05, 1))


VOLTAGES: List[Dict[str, Any]] = [
    {"key": 120, "name": gen("120 V"), "nominal": 120.0},
    {"key": 208, "name": gen("208 V"), "nominal": 208.0},
    {"key": 240, "name": gen("240 V"), "nominal": 240.0},
    {"key": 277, "name": gen("277 V"), "nominal": 277.0},
    {"key": 480, "name": gen("480 V"), "nominal": 480.0},
    {"key": 600, "name": gen("600 V"), "nominal": 600.0},
]
for _v in VOLTAGES:
    _v["min"], _v["max"] = _c84_range_a(_v["nominal"])

#: OUR distribution systems = the standard North-American service
#: configurations [FACT: ANSI C84.1 Table 1 nominal system voltages; the
#: naming style "208Y/120" is the ANSI/IEEE designation].  Type names ours.
#: ll / lg = keys into VOLTAGES (line-to-line / line-to-ground; None = none).
DISTRIBUTION_SYSTEMS: List[Dict[str, Any]] = [
    {"name": gen("120/240 V Single-Phase 3W"), "phase": "single", "config": "delta",
     "wires": 3, "ll": 240, "lg": 120},
    {"name": gen("208Y/120 V Three-Phase 4W Wye"), "phase": "three", "config": "wye",
     "wires": 4, "ll": 208, "lg": 120},
    {"name": gen("480Y/277 V Three-Phase 4W Wye"), "phase": "three", "config": "wye",
     "wires": 4, "ll": 480, "lg": 277},
    {"name": gen("480 V Three-Phase 3W Delta"), "phase": "three", "config": "delta",
     "wires": 3, "ll": 480, "lg": None},
    {"name": gen("600 V Three-Phase 3W Delta"), "phase": "three", "config": "delta",
     "wires": 3, "ll": 600, "lg": None},
]

#: Revit stores electrical POWER (VA / W) in internal units = value * the
#: m^2->ft^2 factor (same 10.7639104167 the voltage encoding uses:
#: rme 'Receptacles' threshold 107639.104 == 10,000 VA * 10.7639104167).
VA_TO_INTERNAL = ty.VOLT_TO_INTERNAL

#: Demand-factor RULE TYPE codes as OBSERVED on the corpus (rme): 0 =
#: constant, 3 = COUNT-based ranges ("largest N objects", motor rule), 4 =
#: LOAD ranges in internal power units (receptacle rule).  (types.py's
#: {'load': 2} guess is not what the corpus uses -- finding F-HS-3; we pass
#: raw codes.)
RULE_CONSTANT, RULE_COUNT, RULE_LOAD = 0, 3, 4

#: OUR demand-factor definitions -- the RULES are NEC facts, cited; the
#: names and the assembled set are ours.
DEMAND_FACTORS: List[Dict[str, Any]] = [
    {"key": "continuous125", "name": gen("Continuous Load 125% (NEC 210.19)"),
     "rule": RULE_CONSTANT, "rows": [(0.0, 1e30, 1.25)],
     "source": "NEC 210.19(A)/215.2(A): continuous loads at 125 %"},
    {"key": "receptacle", "name": gen("Receptacle Demand (NEC 220.44)"),
     "rule": RULE_LOAD,
     "rows": [(0.0, 10000.0 * VA_TO_INTERNAL, 1.0),
              (10000.0 * VA_TO_INTERNAL, 1e30, 0.5)],
     "source": "NEC 220.44: first 10 kVA at 100 %, remainder at 50 %"},
    {"key": "motor", "name": gen("Motor Demand (NEC 430.24)"),
     "rule": RULE_COUNT, "rows": [(0.0, 1.0, 1.25), (1.0, 1e30, 1.0)],
     "source": "NEC 430.24: 125 % of the largest motor plus 100 % of the rest"},
    {"key": "kitchen", "name": gen("Commercial Kitchen Demand (NEC 220.56)"),
     "rule": RULE_COUNT,
     "rows": [(0.0, 2.0, 1.0), (2.0, 3.0, 0.9), (3.0, 4.0, 0.8),
              (4.0, 5.0, 0.7), (5.0, 1e30, 0.65)],
     "source": "NEC 220.56 Table: 1-2 units 100 %, 3 units 90 %, 4 units 80 %, "
               "5 units 70 %, 6+ units 65 % [count-range encoding: hypothesis]"},
    {"key": "no_diversity", "name": gen("No Diversity 100%"),
     "rule": RULE_CONSTANT, "rows": [(0.0, 1e30, 1.0)],
     "source": "our policy: no demand diversity applied (base default)"},
]

#: OUR load classifications (the standard load families = electrical
#: practice; our labels + the classification set are ours).  space_class /
#: signature = the schema enums decoded this session from rme (space load
#: class 1 = lighting, 2 = power/receptacle; signature 1 = motor, 2 =
#: other, 3 = spare) -- semantics we must set correctly (interface), see
#: finding F-HS-4 (types.new_load_class hard-codes signature 0).
LOAD_CLASSIFICATIONS: List[Dict[str, Any]] = [
    {"name": gen("Lighting"), "demand": "continuous125", "space_class": 1, "signature": 0},
    {"name": gen("Receptacle"), "demand": "receptacle", "space_class": 2, "signature": 0},
    {"name": gen("Motor"), "demand": "motor", "space_class": 0, "signature": 1},
    {"name": gen("HVAC"), "demand": "no_diversity", "space_class": 0, "signature": 0},
    {"name": gen("Kitchen Equipment"), "demand": "kitchen", "space_class": 0, "signature": 0},
    {"name": gen("Spare"), "demand": "no_diversity", "space_class": 0, "signature": 3},
]

#: OUR panel-schedule label templates for a load classification.  ``%1!s!``
#: is a Windows FormatMessage placeholder the reader substitutes the
#: classification name into -- a REQUIRED FORMAT TOKEN (interface); the
#: surrounding PHRASING is ours (Autodesk's is "Actual %1!s! Load", ...).
LOAD_LABEL_TEMPLATES: Dict[str, str] = {
    "m_actualElectricalLoadLabel": "%1!s! - Actual Load",
    "m_loadSummaryDemandFactorLabel": "%1!s! - Demand Factor",
    "m_panelConnectedCurrentLabel": "%1!s! - Connected Current",
    "m_panelConnectedLabel": "%1!s! - Connected Load",
    "m_panelEstimatedCurrentLabel": "%1!s! - Demand Current",
    "m_panelEstimatedLabel": "%1!s! - Demand Load",
}

#: OUR ElectricalSetting (Electrical Settings > General).  Per field:
#: phase names L1/L2/L3 = our house convention (IEC 60445 line-conductor
#: designation, chosen over the A/B/C of the samples); circuit rating 20 A
#: = FACT (NEC 210.3 standard branch-circuit rating); wiring path offset
#: 8'-0" AFF = our routing convention; specific angles = the manufactured
#: elbow angles of conduit / cable-tray FITTINGS [FACT: standard factory
#: bends 11.25/15/22.5/30/45/60/90 deg]; the boolean policies are our
#: schedule conventions (spares excluded from panel totals; multi-pole
#: circuits merged into one schedule cell).
ELECTRICAL_SETTING: Dict[str, Any] = {
    "phase_labels": ("L1", "L2", "L3"),
    "circuit_rating_A": 20.0,
    "circuit_path_offset_mm": 8.0 * 304.8,          # 8'-0" above the level
    "specific_angles_deg": (11.25, 15.0, 22.5, 30.0, 45.0, 60.0, 90.0),
    "load_calc_method": 0,
    "run_load_calcs_in_spaces": True,
    "include_spares_in_totals": False,
    "merge_multi_pole_circuits": True,
    "space_label": "SPACE",
    "spare_label": "SPARE",
}

#: CONDUIT standards + trade-size tables.  Every dimension is a FACT:
#: nominal internal diameters = NEC Chapter 9 Table 4; outer diameters =
#: the product standards (EMT: ANSI C80.3 / UL 797; IMC: ANSI C80.6 /
#: UL 1242; RMC: ANSI C80.1 / UL 6; PVC-40: NEMA TC-2 / UL 651); minimum
#: bend radii = NEC Chapter 9 Table 2 (one-shot & full-shoe benders, to
#: centerline).  Names ours.  Rows = (trade in, ID in, OD in, bend R in).
_BEND_RADIUS_IN = {0.5: 4.0, 0.75: 4.5, 1.0: 5.75, 1.25: 7.25, 1.5: 8.25,
                   2.0: 9.5, 2.5: 10.5, 3.0: 13.0, 3.5: 15.0, 4.0: 16.0,
                   5.0: 24.0, 6.0: 30.0}
CONDUIT_STANDARDS: List[Dict[str, Any]] = [
    {"key": "emt", "name": gen("EMT"), "source": "ANSI C80.3 / NEC Ch.9 T4",
     "sizes": [(0.5, 0.622, 0.706), (0.75, 0.824, 0.922), (1.0, 1.049, 1.163),
               (1.25, 1.380, 1.510), (1.5, 1.610, 1.740), (2.0, 2.067, 2.197),
               (2.5, 2.731, 2.875), (3.0, 3.356, 3.500), (3.5, 3.834, 4.000),
               (4.0, 4.334, 4.500)]},
    {"key": "imc", "name": gen("IMC"), "source": "ANSI C80.6 / NEC Ch.9 T4",
     "sizes": [(0.5, 0.660, 0.815), (0.75, 0.864, 1.029), (1.0, 1.105, 1.290),
               (1.25, 1.448, 1.638), (1.5, 1.683, 1.883), (2.0, 2.150, 2.360),
               (2.5, 2.557, 2.857), (3.0, 3.176, 3.476), (3.5, 3.671, 3.971),
               (4.0, 4.166, 4.466)]},
    {"key": "rmc", "name": gen("RMC"), "source": "ANSI C80.1 / NEC Ch.9 T4",
     "sizes": [(0.5, 0.632, 0.840), (0.75, 0.836, 1.050), (1.0, 1.063, 1.315),
               (1.25, 1.394, 1.660), (1.5, 1.624, 1.900), (2.0, 2.083, 2.375),
               (2.5, 2.489, 2.875), (3.0, 3.090, 3.500), (3.5, 3.570, 4.000),
               (4.0, 4.050, 4.500), (5.0, 5.073, 5.563), (6.0, 6.093, 6.625)]},
    {"key": "pvc40", "name": gen("PVC Schedule 40"), "source": "NEMA TC-2 / NEC Ch.9 T4",
     "sizes": [(0.5, 0.602, 0.840), (0.75, 0.804, 1.050), (1.0, 1.029, 1.315),
               (1.25, 1.360, 1.660), (1.5, 1.590, 1.900), (2.0, 2.047, 2.375),
               (2.5, 2.445, 2.875), (3.0, 3.042, 3.500), (3.5, 3.521, 4.000),
               (4.0, 3.998, 4.500), (5.0, 5.016, 5.563), (6.0, 6.031, 6.625)]},
]


def conduit_size_rows(std: Dict[str, Any]) -> List[Tuple[float, float, float, float]]:
    """(trade, inner, outer, bend_radius) inch rows for a conduit standard,
    joining the standard's diameters with NEC Chapter 9 Table 2 radii."""
    return [(t, i, o, _BEND_RADIUS_IN[t]) for t, i, o in std["sizes"]]


#: OUR conduit TYPES: per standard, a with-fitting and a plain-run type.
#: Fitting-family symbol ids stay -1 (fitting families = OUR future loadable
#: content, gate G4 -- never sample families).
CONDUIT_TYPES: List[Dict[str, Any]] = [
    {"name": gen("Conduit - EMT with Fittings"), "standard": "emt", "with_fitting": True},
    {"name": gen("Conduit - EMT (no fittings)"), "standard": "emt", "with_fitting": False},
    {"name": gen("Conduit - IMC with Fittings"), "standard": "imc", "with_fitting": True},
    {"name": gen("Conduit - RMC with Fittings"), "standard": "rmc", "with_fitting": True},
    {"name": gen("Conduit - PVC Sch 40 with Fittings"), "standard": "pvc40", "with_fitting": True},
]

#: CABLE TRAY: nominal widths [FACT: NEMA VE 1 standard widths, inches];
#: types ours (ladder / ventilated trough / solid bottom).
CABLE_TRAY_WIDTHS_IN: List[float] = [6.0, 9.0, 12.0, 18.0, 24.0, 30.0, 36.0]
CABLE_TRAY_TYPES: List[Dict[str, Any]] = [
    {"name": gen("Cable Tray - Ladder"), "shape": "ladder"},
    {"name": gen("Cable Tray - Ventilated Trough"), "shape": "ushape"},
    {"name": gen("Cable Tray - Solid Bottom"), "shape": "ushape"},
]

#: CONDUCTOR definition cells.  Names are the physical / code
#: designations themselves (a copper conductor is named 'Copper'; 'THHN'
#: 'THWN-2' 'XHHW-2' are NEC insulation-type designations; '75'/'90' are the
#: degC temperature ratings) -- FACTS with no free naming choice; the class
#: is a name-only cell (see NO_FREE_CHOICE).  Diameters = uninsulated
#: stranded conductor overall diameter [FACT: NEC Chapter 9 Table 8].
CONDUCTOR_MATERIALS: List[str] = ["Copper", "Aluminum"]
CONDUCTOR_TEMPERATURE_RATINGS_C: List[str] = ["75", "90"]
CONDUCTOR_INSULATIONS: List[str] = ["THWN-2", "THHN", "XHHW-2"]
CONDUCTOR_MAX_SIZES: List[Tuple[str, float]] = [("500", 0.813 * 25.4),   # 500 kcmil Cu
                                                 ("750", 0.998 * 25.4)]   # 750 kcmil Al

#: OUR wire types (name -> cell selection + neutral/ground policy).  The
#: raceway-magnetism string 'Non-Magnetic'/'Magnetic' is a two-valued
#: schema field (interface).  Names ours.
WIRE_TYPES: List[Dict[str, Any]] = [
    {"name": gen("Wire - Cu THWN-2 75C"), "material": "Copper", "temperature": "75",
     "insulation": "THWN-2", "max_size": "500", "conduit_type": "Non-Magnetic"},
    {"name": gen("Wire - Cu THHN 90C"), "material": "Copper", "temperature": "90",
     "insulation": "THHN", "max_size": "500", "conduit_type": "Non-Magnetic"},
    {"name": gen("Wire - Al XHHW-2 75C"), "material": "Aluminum", "temperature": "75",
     "insulation": "XHHW-2", "max_size": "750", "conduit_type": "Non-Magnetic"},
]

#: WIRE AMPACITY / SIZE data [FACT: NEC Table 310.16 (75 degC and 90 degC
#: columns) and NEC Chapter 9 Table 8 conductor diameters].  DATA ONLY: no
#: RbsWireSizesElem constructor exists yet (the electrical-catalog stream's
#: queued constructor -- exact target structure recorded in
#: docs/inbox/own-content.md).  size (AWG/kcmil label), diameter inches
#: (Table 8, stranded), ampacity A per (material, degC column).
WIRE_AMPACITY_TABLE: Dict[str, Dict[str, List[Tuple[str, float, float]]]] = {
    "Copper": {
        "75": [("14", 0.073, 20.0), ("12", 0.092, 25.0), ("10", 0.116, 35.0),
               ("8", 0.146, 50.0), ("6", 0.184, 65.0), ("4", 0.232, 85.0),
               ("3", 0.260, 100.0), ("2", 0.292, 115.0), ("1", 0.332, 130.0),
               ("1/0", 0.372, 150.0), ("2/0", 0.418, 175.0), ("3/0", 0.470, 200.0),
               ("4/0", 0.528, 230.0), ("250", 0.575, 255.0), ("300", 0.630, 285.0),
               ("350", 0.681, 310.0), ("400", 0.728, 335.0), ("500", 0.813, 380.0),
               ("600", 0.893, 420.0), ("750", 0.998, 475.0)],
        "90": [("14", 0.073, 25.0), ("12", 0.092, 30.0), ("10", 0.116, 40.0),
               ("8", 0.146, 55.0), ("6", 0.184, 75.0), ("4", 0.232, 95.0),
               ("3", 0.260, 115.0), ("2", 0.292, 130.0), ("1", 0.332, 145.0),
               ("1/0", 0.372, 170.0), ("2/0", 0.418, 195.0), ("3/0", 0.470, 225.0),
               ("4/0", 0.528, 260.0), ("250", 0.575, 290.0), ("300", 0.630, 320.0),
               ("350", 0.681, 350.0), ("400", 0.728, 380.0), ("500", 0.813, 430.0),
               ("600", 0.893, 475.0), ("750", 0.998, 535.0)],
    },
    "Aluminum": {
        "75": [("12", 0.092, 20.0), ("10", 0.116, 30.0), ("8", 0.146, 40.0),
               ("6", 0.184, 50.0), ("4", 0.232, 65.0), ("3", 0.260, 75.0),
               ("2", 0.292, 90.0), ("1", 0.332, 100.0), ("1/0", 0.372, 120.0),
               ("2/0", 0.418, 135.0), ("3/0", 0.470, 155.0), ("4/0", 0.528, 180.0),
               ("250", 0.575, 205.0), ("300", 0.630, 230.0), ("350", 0.681, 250.0),
               ("400", 0.728, 270.0), ("500", 0.813, 310.0), ("600", 0.893, 340.0),
               ("750", 0.998, 385.0)],
        "90": [("12", 0.092, 25.0), ("10", 0.116, 35.0), ("8", 0.146, 45.0),
               ("6", 0.184, 55.0), ("4", 0.232, 75.0), ("3", 0.260, 85.0),
               ("2", 0.292, 100.0), ("1", 0.332, 115.0), ("1/0", 0.372, 135.0),
               ("2/0", 0.418, 150.0), ("3/0", 0.470, 175.0), ("4/0", 0.528, 205.0),
               ("250", 0.575, 230.0), ("300", 0.630, 260.0), ("350", 0.681, 280.0),
               ("400", 0.728, 305.0), ("500", 0.813, 350.0), ("600", 0.893, 385.0),
               ("750", 0.998, 435.0)],
    },
}

# ---------------------------------------------------------------------------
# 10. ANNOTATION STANDARDS (text types)
# ---------------------------------------------------------------------------
#: Text heights are the ISO 3098 lettering series [FACT: ISO 3098-1
#: preferred heights 2.5 / 3.5 / 5 / 7 mm].  'Arial' names an operating-
#: system FONT (a Monotype/Microsoft font-name reference customary in any
#: document that declares typography -- see disposition "font-names").
TEXT_FONT = "Arial"
TEXT_TYPES: List[Dict[str, Any]] = [
    {"name": gen("2.5mm Text"), "size_mm": 2.5, "bold": False},
    {"name": gen("3.5mm Text Bold"), "size_mm": 3.5, "bold": True},
    {"name": gen("5mm Title"), "size_mm": 5.0, "bold": True},
]

# ---------------------------------------------------------------------------
# 11. OBJECT STYLES HOUSE STANDARD (our discipline-coded graphics manual)
# ---------------------------------------------------------------------------
# The object-styles table has one GStyleElem per built-in category and
# role.  WHICH categories exist / which are cuttable = a product fact (the
# BuiltInCategory enum -- an interface constant, cf. rvt.inventory); the pens
# and colours below are OUR discipline-coded documentation standard, NOT
# Autodesk's per-category defaults (their extracted 1,074-row table is
# QUARANTINED at experiments/genesis/reference/ and never read here).
# Line-weight LOGIC (cut heavier than projection) is the universal drafting
# convention; the specific pen numbers and the colour-per-discipline coding
# are invented by us (a CAD-standard, like a firm's layer manual).
#
#: discipline -> (projection pen, cut pen, COLORREF)
HOUSE_SCHEME: Dict[str, Tuple[int, int, int]] = {
    "architectural": (1, 4, BLACK),
    "structural":    (2, 5, rgb(96, 32, 32)),      # oxblood
    "electrical":    (1, 3, rgb(0, 60, 150)),      # navy
    "mechanical":    (1, 3, rgb(0, 110, 70)),      # green
    "piping":        (1, 3, rgb(30, 90, 140)),     # steel blue
    "annotation":    (1, 1, BLACK),
    "site":          (1, 3, rgb(120, 80, 40)),     # brown
    "general":       (1, 3, BLACK),
}

#: (BuiltInCategory OST id, our label, discipline, cuttable)
HOUSE_CATEGORIES: List[Tuple[int, str, str, bool]] = [
    (-2000011, "Walls", "architectural", True),
    (-2000014, "Windows", "architectural", True),
    (-2000023, "Doors", "architectural", True),
    (-2000032, "Floors", "architectural", True),
    (-2000035, "Roofs", "architectural", True),
    (-2000038, "Ceilings", "architectural", True),
    (-2000051, "Lines", "annotation", False),
    (-2000080, "Furniture", "architectural", True),
    (-2000100, "Columns", "architectural", True),
    (-2000120, "Stairs", "architectural", True),
    (-2000126, "Railings", "architectural", True),
    (-2000150, "Generic Annotations", "annotation", False),
    (-2000151, "Generic Models", "architectural", True),
    (-2000160, "Rooms", "annotation", False),
    (-2000220, "Grids", "annotation", False),
    (-2000240, "Levels", "annotation", False),
    (-2000260, "Dimensions", "annotation", False),
    (-2000280, "Title Blocks", "annotation", False),
    (-2000300, "Text Notes", "annotation", False),
    (-2000400, "Section Heads", "annotation", False),
    (-2000480, "Room Tags", "annotation", False),
    (-2000485, "Space Tags", "annotation", False),
    (-2000510, "Viewports", "annotation", False),
    (-2000515, "View Titles", "annotation", False),
    (-2000530, "Reference Planes", "annotation", False),
    (-2000538, "Callout Heads", "annotation", False),
    (-2000573, "Schedules", "annotation", False),
    (-2000600, "Sheets", "annotation", True),
    (-2000700, "Materials", "general", False),
    (-2001000, "Casework", "architectural", True),
    (-2001040, "Electrical Equipment", "electrical", False),
    (-2001060, "Electrical Fixtures", "electrical", False),
    (-2001120, "Lighting Fixtures", "electrical", False),
    (-2001140, "Mechanical Equipment", "mechanical", False),
    (-2001160, "Plumbing Fixtures", "piping", True),
    (-2001260, "Site", "site", True),
    (-2001271, "Survey Point", "site", True),
    (-2001272, "Project Base Point", "site", True),
    (-2001300, "Structural Foundations", "structural", True),
    (-2001320, "Structural Framing", "structural", True),
    (-2001330, "Structural Columns", "structural", True),
    (-2001350, "Specialty Equipment", "architectural", True),
    (-2002000, "Detail Items", "annotation", False),
    (-2003101, "Project Information", "annotation", False),
    (-2003600, "Spaces", "annotation", False),
    (-2005003, "Electrical Equipment Tags", "annotation", False),
    (-2005008, "Lighting Fixture Tags", "annotation", False),
    (-2006020, "Level Heads", "annotation", False),
    (-2006040, "Grid Heads", "annotation", False),
    (-2007000, "Connectors", "electrical", False),
    (-2008000, "Ducts", "mechanical", False),
    (-2008010, "Duct Fittings", "mechanical", False),
    (-2008013, "Air Terminals", "mechanical", False),
    (-2008037, "Electrical Circuits", "electrical", False),
    (-2008039, "Wires", "electrical", False),
    (-2008044, "Pipes", "piping", False),
    (-2008049, "Pipe Fittings", "piping", False),
    (-2008077, "Communication Devices", "electrical", False),
    (-2008079, "Security Devices", "electrical", False),
    (-2008081, "Fire Alarm Devices", "electrical", False),
    (-2008083, "Data Devices", "electrical", False),
    (-2008087, "Lighting Devices", "electrical", False),
    (-2008126, "Cable Tray Fittings", "electrical", False),
    (-2008128, "Conduit Fittings", "electrical", False),
    (-2008130, "Cable Trays", "electrical", False),
    (-2008132, "Conduits", "electrical", False),
]

#: OUR sub-categories = a firm's own line-style vocabulary:
#: (name, parent OST id, categoryType 1 model / 4 line-style, pen, colour,
#:  line-pattern key, discipline)
SUB_CATEGORIES: List[Tuple[str, int, int, int, int, str, str]] = [
    (gen("Fire-Rated Assembly Line"), -2000011, 1, 2, rgb(200, 30, 30), "dash", "architectural"),
    (gen("Above-Ceiling Conduit"), -2008132, 1, 1, rgb(0, 60, 150), "hidden", "electrical"),
    (gen("Demolition (Existing to Remove)"), -2000011, 1, 1, rgb(120, 120, 120), "demo",
     "architectural"),
    (gen("Centre Lines"), -2000051, 4, 1, rgb(30, 30, 120), "centre", "annotation"),
]

# ---------------------------------------------------------------------------
# 12. VIEWS
# ---------------------------------------------------------------------------
#: OUR view family types + the default views a genesis base is born with.
#: '{3D}' is Revit's own default-3D-view name -> ours: 'Working 3D'.  The
#: project view's name stays '???' (a fixed internal token in every corpus
#: file incl. the German ones -- REQUIRED FORMAT TOKEN, see dispositions).
VIEW_TYPES: List[Dict[str, str]] = [
    {"key": "3d", "name": gen("3D View"), "family": "3d"},
    {"key": "floor_plan", "name": gen("Floor Plan"), "family": "floor_plan"},
    {"key": "ceiling_plan", "name": gen("Ceiling Plan"), "family": "ceiling_plan"},
]
VIEW_3D_NAME = gen("Working 3D")
#: OUR default 3D camera: SE isometric looking at the model origin.
VIEW_3D_EYE_FT = (-60.0, -60.0, 40.0)
VIEW_3D_TARGET_FT = (0.0, 0.0, 6.0)
#: OUR plan view range (imperial house standard): cut plane 4'-0" above the
#: level, top clip 8'-0" (a typical ceiling / plenum line), view depth = the
#: level below.  (Revit's metric-template values are 1200 / 2300 mm.)
PLAN_CUT_OFFSET_FT = 4.0
PLAN_TOP_OFFSET_FT = 8.0
#: OUR plan scale: 1/8" = 1'-0" (1:96), the US architectural default; the
#: 3D view uses the corpus's dimensionless 5.0 convention.
PLAN_SCALE = 1.0 / 96.0
VIEW_3D_SCALE = 5.0
#: plan detail level 2 (medium) / discipline 1 (architectural) [enum values
#: INFERRED; ours = medium detail on architectural plans].
PLAN_DETAIL_LEVEL = 2
PLAN_DISCIPLINE = 1
#: OUR view visibility policy for the base document: NO categories excluded
#: by default in any view (everything visible; visibility templates are
#: authored later per job).  The corpus views exclude analytical / scope
#: categories via the sample template's list -- OUR policy is empty lists.
DRAW_EXCLUDED_CATEGORIES: Dict[str, List[int]] = {"project": [], "plan": [], "3d": []}
#: reference (similar-condition) label of a view family type: 'SIM.' is
#: our sheet abbreviation standard (Autodesk's default text is 'Sim').
VIEW_REF_LABEL = "SIM."

# ---------------------------------------------------------------------------
# 13. RESOURCE-IDENTIFIER DISPOSITIONS (G1c) + the shims that apply them
# ---------------------------------------------------------------------------
#: Every Autodesk identifier our constructors emit (found by source grep +
#: a decode/byte scan of a constructed catalog -- see identifier_scan()),
#: with its disposition:
#:   drop      -> emit empty/none (option a)
#:   replace   -> our identifier / wording (option b)
#:   required  -> a REQUIRED FORMAT TOKEN: an interface identifier the
#:                reader keys behaviour on; not expression -- argued for
#:                counsel (option c)
#: 'shim' = the value is applied here over the constructor output because
#: the constructor does not parameterise it yet (see CONSTRUCTOR_DIFFS);
#: 'probe' = reader tolerance unknown -> viewer-test before certifying.
RESOURCE_ID_DISPOSITIONS: List[Dict[str, Any]] = [
    {"id": "material-asset-descriptor",
     "what": "Material.m_asset {m_sName 'Generic', m_sLibrary 'assetlibrary_base.fbx', "
             "m_eAssetType 4} on every MaterialElem",
     "where": "rvt/genesis/types.py::new_material (lines ~995-999)",
     "count": "1 per material (13 in the house catalog)",
     "disposition": "drop",
     "action": "asset binding descriptor blanked (name '', library '', type 0): our "
               "materials are graphics-only (m_appearanceAssetId -1) and shade by m_color; "
               "the descriptor only NAMES Autodesk's shipped render-asset library",
     "shim": True, "probe": True,
     "fallback": "if the reader requires a bound appearance asset descriptor, this becomes a "
                 "'required' interface reference (naming Autodesk's asset library is a reference, "
                 "not a redistribution) -- counsel"},
    {"id": "view-render-assets",
     "what": "ViewDisplayMgr GRenderSettings assets: environment 'SunAndSky-002', quality/exposure "
             "'Generic', all with m_sLibrary 'assetlibrary_base.fbx' (x2 render-settings blocks "
             "per view)",
     "where": "rvt/genesis/skeleton.py::_grender_settings / view_display_mgr / dbview_base",
     "count": "8 asset descriptors per view (project view + 3D view + 2 plans = 32)",
     "disposition": "drop",
     "action": "asset names / library strings blanked; render quality/exposure numeric properties "
               "left at neutral values (they are not identifiers)",
     "shim": True, "probe": True,
     "fallback": "same as the material descriptor: a 'required' reference if the reader "
                 "insists on a named environment"},
    {"id": "load-class-labels",
     "what": "the six panel-schedule label templates ('Actual %1!s! Load', '%1!s! Demand Factor', "
             "...) on every ElectricalLoadClassification -- Revit's UI resource strings",
     "where": "rvt/genesis/types.py::new_load_class (lines ~1533-1538, hard-coded)",
     "count": "6 per classification (36 in the house catalog)",
     "disposition": "replace",
     "action": "our own phrasing (LOAD_LABEL_TEMPLATES) keeping the %1!s! substitution token",
     "shim": True, "probe": False,
     "fallback": ""},
    {"id": "formatmessage-token",
     "what": "the '%1!s!' placeholder itself (Windows FormatMessage argument syntax)",
     "where": "inside the six load-label templates",
     "count": "36",
     "disposition": "required",
     "action": "kept: it is the substitution SYNTAX the reader expands the classification "
               "name into -- an interface token, not phrasing",
     "shim": False, "probe": False, "fallback": ""},
    {"id": "forge-typeids",
     "what": "Forge measurable-spec / unit / symbol typeIds ('autodesk.spec.aec:length-1.0.0', "
             "'autodesk.unit.unit:feet-1.0.1', 'autodesk.unit.symbol:sf-1.0.1', ...) in the "
             "UnitsElem format map",
     "where": "house_standard.UNIT_FORMATS_* (was skeleton.DEFAULT_UNIT_FORMATS)",
     "count": f"{3} strings x ~28 entries",
     "disposition": "required",
     "action": "kept: these are the KEYS the reader looks display units up by (identical in "
               "every 2026 file); the CHOICES (which unit/symbol/precision per spec) are ours. "
               "This is the identifier vocabulary of Autodesk's openly published Forge unit "
               "schema (github.com/Autodesk/forge-... schema packages) -- naming a unit is an "
               "interoperability reference, but the licence status of the identifier set is a "
               "counsel question (audit item D-3(a))",
     "shim": False, "probe": False, "fallback": ""},
    {"id": "site-location-defaults",
     "what": "GeoSite defaults: Autodesk HQ coordinates (42.387 N / -71.242 W, Waltham MA), "
             "weather station '52939_2004', stock design-day temperature arrays",
     "where": "rvt/genesis/skeleton.py::new_geo_site defaults (coordinates were already "
              "parameterised; the weather arrays are hard-coded)",
     "count": "2 sites",
     "disposition": "replace",
     "action": "neutral SITE: lat/long 0/0, UTC, no station, ISO 2533 standard-atmosphere "
               "temperatures in every climate slot",
     "shim": True, "probe": False, "fallback": ""},
    {"id": "sun-defaults",
     "what": "SunAndShadowSettings name '<In-session, Still>' (Revit's transient-setting label; "
             "localized user text in the corpus) and the stock azimuth 135 / altitude 35",
     "where": "rvt/genesis/skeleton.py::new_sun_and_shadow_settings (name parameterised; the "
              "per-view constellations do not pass it through)",
     "count": "4 (document sun + one per view)",
     "disposition": "replace",
     "action": "our SUN default (name + south/45 deg); shim on the view-owned sun elements",
     "shim": True, "probe": False, "fallback": ""},
    {"id": "phase-terminology",
     "what": "phase names 'Existing'/'New Construction' and the five 'Show ...' filter names + "
             "vectors (skeleton.DEFAULT_PHASE_FILTERS)",
     "where": "rvt/genesis/skeleton.py::DEFAULT_PHASE_FILTERS / default_phase_filters (unused "
              "here) -- house_standard drives new_phase / new_phase_filter directly",
     "count": "2 phases + 5 filters",
     "disposition": "replace",
     "action": "PHASES / PHASE_FILTERS: our wording and our filter set built from the decoded "
               "presentation-vector semantics",
     "shim": False, "probe": False, "fallback": ""},
    {"id": "view-terminology",
     "what": "default view naming '{3D}' and view-type reference label 'Sim'",
     "where": "genesis_assemble (view name) / skeleton.new_view_type (m_refLabelStr hard-coded)",
     "count": "1 view + 3 view types",
     "disposition": "replace",
     "action": "'Working 3D'; reference label 'SIM.' (shim on m_refLabelStr)",
     "shim": True, "probe": False, "fallback": ""},
    {"id": "project-view-name-token",
     "what": "DBViewProject.m_viewName '???'",
     "where": "rvt/genesis/skeleton.py::new_project_view default",
     "count": "1",
     "disposition": "required",
     "action": "kept: identical '???' in EVERY corpus file including the German-localized ones -> "
               "a fixed internal token for the project's implicit view, not authored text",
     "shim": False, "probe": False, "fallback": ""},
    {"id": "system-family-name",
     "what": "wall-type family-name parameter 'Basic Wall' (param -1010105)",
     "where": "rvt/genesis/types.py::new_wall_type family_name default",
     "count": "1 per wall type (3)",
     "disposition": "required",
     "action": "kept: 'Basic Wall' vs 'Curtain Wall' vs 'Stacked Wall' names the SYSTEM FAMILY "
               "kernel behaviour the type belongs to -- a required designator (interface). "
               "(Types without the param are also accepted by the reader per the types stream; "
               "if counsel prefers, pass family_name=None.)",
     "shim": False, "probe": False, "fallback": "family_name=None (viewer-probe)"},
    {"id": "builtin-enum-ids",
     "what": "negative BuiltInCategory (OST_*) / BuiltInParameter (BIP_*) ids and the "
             "-3000010 solid-pattern sentinel",
     "where": "throughout types.py / skeleton.py / house_standard tables",
     "count": "hundreds",
     "disposition": "required",
     "action": "kept: the fixed public enum every Revit interoperator (API, IFC exporters, forums) "
               "keys on -- format constants, not content",
     "shim": False, "probe": False, "fallback": ""},
    {"id": "font-names",
     "what": "font name 'Arial' in FontElem",
     "where": "house_standard.TEXT_FONT -> types.new_text_type",
     "count": "1 per text type (3)",
     "disposition": "required",
     "action": "kept: names an operating-system font (Monotype/Microsoft), the customary way any "
               "document declares typography; a THIRD-PARTY (not Autodesk) name reference. Swap "
               "TEXT_FONT for an OFL font (e.g. a metric-compatible open font) if counsel prefers",
     "shim": False, "probe": False, "fallback": ""},
    # ---- identifiers OUTSIDE the constructor package (listed for completeness) ----
    {"id": "partatom-namespace",
     "what": "ProjectInformation partatom XML: namespace 'urn:schemas-autodesk-com:partatom', "
             "taxonomy 'adsk:revit' / 'Autodesk Revit', '<A:product>Revit</A:product>'",
     "where": "tools/genesis_assemble.py::our_project_information_zip (assembler stream)",
     "count": "1 stream", "disposition": "required",
     "action": "kept by the assembler: an XML SCHEMA namespace / product-taxonomy vocabulary the "
               "reader parses -- an interface identifier (like an XML xmlns URI). Counsel item "
               "for the product-name mark (TRACKER G3)",
     "shim": False, "probe": False, "fallback": ""},
    {"id": "revit-build-string",
     "what": "BasicFileInfo / History version marker '2026' + build '20250227_1515(x64)' and "
             "the History format-version list ending 2662",
     "where": "rvt/genesis/skeleton.py::REVIT_2026_BUILD / minimal_basic_file_info / "
              "minimal_history; rvt/identity.py keeps the version marker",
     "count": "1", "disposition": "required",
     "action": "kept: the reader gates OPENING on the format/version marker (identity.py: "
               "'Revit reads it to open the file'); the format-version list is the upgrade "
               "ladder the reader replays. Counsel item C1 covers the authoring string",
     "shim": False, "probe": False, "fallback": ""},
    {"id": "formats-latest-schema",
     "what": "Formats/Latest (Autodesk's per-release archive class map, byte-identical) -- not "
             "emitted by these constructors but the schema every constructor is directed by",
     "where": "container level (assembler carries it from the base document)",
     "count": "1 stream", "disposition": "required",
     "action": "OUT OF THIS STREAM'S TERRITORY -- audit item D-3(b) / counsel C4 (ship "
               "verbatim vs clean-room re-serialization)",
     "shim": False, "probe": False, "fallback": ""},
    {"id": "save-unit-signature-banner",
     "what": "the save-unit terminator record inside Partitions/N: u32-length UTF-16 "
             "'Data generated by Autodesk® Revit®' + the Revit application GUID "
             "34b22600-3ed6-44b3-b4f1-6596f4d52b43 (docs/streams/05-partitions.md, KNOWLEDGE "
             "Partitions section) -- present in EVERY G-file's Partitions/21 including the HS "
             "ladder built this session (offset 15,838 of the HS G0)",
     "where": "partition save-unit framing carried/rewritten by the commit & stream layers "
              "(rvt/commit.py, rvt/stream_encoders.py) -- OUTSIDE the constructor package, "
              "found by the whole-file identifier scan",
     "count": "1 per save unit (1 in G0)",
     "disposition": "counsel + probe",
     "action": "NOT ours to change here. Two candidate readings: (i) a REQUIRED framing "
               "record the reader validates (then it is an interface token like the build "
               "string), or (ii) a free-text authorship banner asserting Autodesk generated the "
               "data -- which we did not, so we must not assert it. Recommend the orchestrator "
               "viewer-probe a G0 whose banner AString is emptied/replaced by ours (u32 length + "
               "our text) to learn whether the reader tolerates it; counsel item alongside C1 "
               "(the authoring string)",
     "shim": False, "probe": True, "fallback": ""},
]

#: Constructor changes (owned by the types / skeleton streams) that would
#: retire each shim above -- EXACT DIFFS for the orchestrator; house_standard
#: applies the same values as shims until they land (see docs/inbox/own-content.md).
CONSTRUCTOR_DIFFS: List[Dict[str, str]] = [
    {"file": "src/rvt/genesis/types.py", "function": "new_material",
     "change": "add asset_name='' / asset_library='' / asset_type=0 keyword parameters "
               "replacing the hard-coded 'Generic' / 'assetlibrary_base.fbx' / 4 overlay",
     "retires_shim": "material-asset-descriptor"},
    {"file": "src/rvt/genesis/types.py", "function": "new_load_class",
     "change": "add labels: dict = None (the six m_*Label fields) and signature_type: int = 0; "
               "default labels stay Revit's, house_standard passes LOAD_LABEL_TEMPLATES",
     "retires_shim": "load-class-labels"},
    {"file": "src/rvt/genesis/types.py", "function": "new_demand_factor",
     "change": "correct the rule-type map (corpus: 3 = count ranges, 4 = load ranges in "
               "internal power units; 'load': 2 is unobserved) or document raw codes",
     "retires_shim": "n/a (finding F-HS-3)"},
    {"file": "src/rvt/genesis/skeleton.py", "function": "_grender_settings / view_display_mgr / "
                                                       "dbview_base / new_project_view / new_3d_view / "
                                                       "new_plan_view",
     "change": "add render_env_name='', asset_library='' (and background/sky/ground colour) "
               "parameters threaded from the three view constellations",
     "retires_shim": "view-render-assets"},
    {"file": "src/rvt/genesis/skeleton.py", "function": "new_project_view / new_3d_view / "
                                                       "new_plan_view",
     "change": "add excluded_categories=None (default: DRAW_EXCLUDED_CATEGORIES[kind]) and pass "
               "sun name/azimuth/altitude through to their SunAndShadowSettings satellites",
     "retires_shim": "view-visibility + sun-defaults"},
    {"file": "src/rvt/genesis/skeleton.py", "function": "new_geo_site",
     "change": "add climate parameters (summer/wet-bulb/mean-daily arrays, winter dry bulb, "
               "clearness) defaulting to the ISO-atmosphere neutral set",
     "retires_shim": "site-location-defaults"},
    {"file": "src/rvt/genesis/skeleton.py", "function": "new_view_type",
     "change": "add ref_label='Sim' parameter (m_refLabelStr)",
     "retires_shim": "view-terminology"},
    {"file": "src/rvt/genesis/skeleton.py", "function": "new_true_north",
     "change": "add poche_depth_ft parameter (hard-coded -3 m product default)",
     "retires_shim": "true-north poche depth"},
    {"file": "src/rvt/genesis/skeleton.py", "constant": "DEFAULT_UNIT_FORMATS",
     "change": "replace with house_standard.UNIT_FORMATS_IMPERIAL: the current spec keys "
               "('...length-2.0.0', 'current-2.0.0') and 'feetFractionalInches' do not occur in "
               "the 2026 corpus (finding F-HS-1)",
     "retires_shim": "n/a"},
    {"file": "src/rvt/genesis/types.py", "constant": "NOMINAL_VOLTAGE_RANGES",
     "change": "the values are Autodesk's rounded template ranges (110-130 for 120 V), not "
               "ANSI C84.1; relabel or replace with the +-5 % Range A rule (finding F-HS-2). "
               "house_standard always passes explicit min/max so behaviour is unaffected",
     "retires_shim": "n/a"},
    {"file": "tools/genesis_assemble.py", "function": "build_our_content",
     "change": "REPLACE the inline catalog/skeleton values with "
               "rvt.genesis.house_standard.build_catalog(start_id) (same OurContent shape: "
               ".elements / .manifest / .ids / .roundtrip / .dangling); the label 'units "
               "registry (136 formats)' must state the emitted count (audit accounting error B6)",
     "retires_shim": "n/a -- INTEGRATION of this module into the G0 ladder"},
]

# ---------------------------------------------------------------------------
# 14. NO-FREE-CHOICE registry (classes whose bytes are format machinery)
# ---------------------------------------------------------------------------
#: Elements whose serialized similarity to a sample specimen may reach the
#: >= 0.85 zone WITHOUT being copied expression, because the class leaves no
#: (or almost no) authorable payload.  key = class name; value = the reason
#: (the record cites each measured case).  A >= 0.85 element whose class is
#: NOT here is a G1b violation (test_house_standard asserts this).
NO_FREE_CHOICE: Dict[str, str] = {
    "BasePoint":
        "the Project Base Point / Survey Point of a genesis document sit at the model origin "
        "(0,0,0) with the fixed point-marker rep; the only 'value' is the coordinate, and a base "
        "document's coordinate IS the origin -- there is no other honest choice",
    "DBViewProject":
        "the birth (episode-0) project view is a container of stock display machinery (461/474 "
        "leaves are display settings every view carries); its name is the required '???' token; "
        "our authorable share (phase params, exclusion policy, render descriptors, colours) is "
        "a few dozen bytes of a ~2 kB object -- retiring the rest needs the view-display "
        "constructor parameters listed in CONSTRUCTOR_DIFFS",
    "Viewer":
        "the project view's Viewer is a crop/camera frame with no user-facing definition (the "
        "corpus itself carries the same frame in every template); nothing but bound offsets to "
        "vary",
    "CustomElement":
        "conductor definition cells are NAME-ONLY cells whose names are physical/code "
        "designations ('Copper', '75', 'THWN-2', '500') -- facts, not authorship; the class "
        "carries nothing else",
    "GStyleElem":
        "an object-style row is ~60 bytes of fixed serialization around ~8 bytes of definition "
        "(category id / pen / colour / pattern); OUR pens and colours change every one of "
        "those definition bytes -- nothing else in the row CAN differ (measured max 0.83)",
    "ModelClipBox":
        "the 3D view's section box is an axis-aligned bound frame owned by the Viewer3d; its "
        "only values are the half-extents (measured max 0.80)",
}

#: Findings surfaced while authoring this standard (for the owning streams).
FINDINGS: Dict[str, str] = {
    "F-HS-1": "skeleton.DEFAULT_UNIT_FORMATS spec/unit typeIds ('...:length-2.0.0', "
              "'feetFractionalInches-1.0.0', 'current-2.0.0') do not occur in the 2026 corpus; "
              "the samples key 'autodesk.spec.aec:length-1.0.0' / 'current-1.0.0' and have no "
              "'feetFractionalInches' unit (feet-and-inches is a SYMBOL: "
              "'autodesk.unit.symbol:feetAndInches-1.0.1'). Superseded by UNIT_FORMATS_IMPERIAL.",
    "F-HS-2": "types.NOMINAL_VOLTAGE_RANGES claims NEC/ANSI provenance but its ranges "
              "(120 V: 110-130, 208: 200-220, 480: 460-490 ...) are exactly Autodesk's rme template "
              "values; ANSI C84.1 Range A service voltage is +-5 % (120 V: 114-126). VOLTAGES here "
              "use C84.1.",
    "F-HS-3": "demand-factor m_ruleType observed on the corpus: 0 = constant, 3 = COUNT ranges "
              "(motor 'largest 1 at 125 %'), 4 = LOAD ranges in internal power units (receptacle "
              "'first 10 kVA' stores 107639.104 = 10,000 * 10.7639); types.new_demand_factor's "
              "{'load': 2} map is not what the samples carry.",
    "F-HS-4": "ElectricalLoadClassification semantic enums decoded from rme: m_spaceLoadClass "
              "1 = lighting, 2 = power/receptacle (else 0); m_signitureType 1 = motor, 2 = other, "
              "3 = spare (else 0). types.new_load_class hard-codes m_signitureType = 0 -> a "
              "Motor / Spare classification cannot be expressed without the signature_type param "
              "(applied here as a shim).",
    "F-HS-5": "phase-filter presentation vector semantics DECODED (was INFERRED): slots "
              "2/3/4/5 = Existing/Demolished/New/Temporary; 0 = not displayed, 1 = by category, "
              "2 = overridden. skeleton's comment guesses the opposite value order.",
    "F-HS-6": "GeoSite/GeoLocation naming: the corpus GeoSite symbol name is EMPTY and the "
              "'Internal'/'Project' strings live on the GeoLocation instances (localized: German "
              "'Intern'/'Projekt', with an English 'Internal' co-existing in the dach file) -> the "
              "location names are free text, not tokens. skeleton's default coordinates are "
              "Autodesk HQ (Waltham MA), the corpus stock site.",
}


# ---------------------------------------------------------------------------
# 15. THE CATALOG object
# ---------------------------------------------------------------------------

#: the six Autodesk 2026 sample projects (the provenance corpus)
SAMPLES: List[str] = [
    "rstbasicsampleproject", "rmebasicsampleproject", "racbasicsampleproject",
    "racadvancedsampleproject", "rstadvancedsampleproject", "dach-sample-project",
]

#: identifier patterns the byte scanner looks for in serialized records
IDENTIFIER_PATTERN = re.compile(
    r"(autodesk|adsk|\.fbx|sunandsky|%1!|forge|revit|generic|assetlibrary|"
    r"52939_2004|<in-session)", re.I)


@dataclass
class HouseCatalog:
    """Everything build_catalog authored, in the shape the assembler consumes.

    records  -- TypeRecord / SkelElement (id-sorted after build)
    elements -- rvt.mutate.NewElement list (id-sorted), the commit shape
    manifest -- per element {id, class, kind, name, params?}
    ids      -- named ids of the skeleton elements (levels, phases, views ...)
    """
    records: List[Any]
    elements: List[Any]
    manifest: List[dict]
    ids: Dict[str, int]
    start_id: int
    last_id: int
    scrub: str = "full"
    unit_system: str = "imperial"

    # -- verification --------------------------------------------------------
    def roundtrip(self) -> dict:
        """Encode every record then decode it back: schema validity +
        byte-exactness proof.  {records, ok, failed, failures[:20]}"""
        ok = fail = 0
        failures: List[str] = []
        for r in self.records:
            rep = r.roundtrip()
            good = rep.get("ok")
            if good is None:                                  # SkelElement shape
                good = all(v.get("clean") and v.get("byte_exact")
                           for k, v in rep.items() if k != "ok")
            if good:
                ok += 1
            else:
                fail += 1
                failures.append(f"{r.class_name}#{r.elem_id}: "
                                f"{ {k: v for k, v in rep.items() if k != 'ok'} }"[:300])
        return {"records": len(self.records), "ok": ok, "failed": fail,
                "failures": failures[:20]}

    def dangling(self) -> List[dict]:
        """Every positive ElementId our records reference must be one of OUR
        ids (self-containment).  Returns the (empty, we assert) dangling list."""
        mine = {r.elem_id for r in self.records}
        # small integers that are ENUM values, not element ids (same
        # exclusion the assembler applies: DBViewType.m_systemFamilyIdx)
        not_ids = {"m_systemFamilyIdx"}
        out: List[dict] = []
        for r in self.records:
            tr = r if hasattr(r, "rep_class_id") and not hasattr(r, "elemrec_row") \
                else r.as_type_record()
            for path, i in ty._element_refs(tr):
                if path.rsplit(".", 1)[-1].split("[")[0] in not_ids:
                    continue
                if i > 0 and i not in mine and i != r.elem_id:
                    out.append({"elem_id": r.elem_id, "class": r.class_name,
                                "path": path, "target": i})
        return out

    def encoded(self) -> List[Tuple[int, str, bytes, str, str]]:
        """[(elem_id, class_name, seq102_body, kind, name)] -- the exact
        payloads the provenance shingle index compares."""
        dec, enc, _s = ty._S()
        by_id = {m["id"]: m for m in self.manifest}
        out = []
        for r in sorted(self.records, key=lambda x: x.elem_id):
            body = enc.encode_object(r.class_id, r.obj or {})
            m = by_id.get(r.elem_id, {})
            out.append((r.elem_id, r.class_name, body, m.get("kind", ""), m.get("name", "")))
        return out

    def identifier_scan(self) -> Dict[str, dict]:
        """Byte-scan every record's THREE serialized payloads for identifier
        strings (UTF-16LE).  {string: {count, classes{...}}} -- what an
        auditor's ``strings`` pass would find in OUR records."""
        dec, enc, _s = ty._S()
        hits: Dict[str, dict] = {}
        for r in self.records:
            for seq, cid, obj in r.records():
                body = enc.encode_object(cid, obj or {})
                for s in _utf16_strings(body):
                    if IDENTIFIER_PATTERN.search(s):
                        h = hits.setdefault(s, {"count": 0, "classes": {}})
                        h["count"] += 1
                        h["classes"][r.class_name] = h["classes"].get(r.class_name, 0) + 1
        return hits

    def counts_by_class(self) -> Dict[str, int]:
        c: Dict[str, int] = {}
        for r in self.records:
            c[r.class_name] = c.get(r.class_name, 0) + 1
        return dict(sorted(c.items()))

    def to_json(self) -> dict:
        return {"count": len(self.records), "start_id": self.start_id,
                "last_id": self.last_id, "scrub": self.scrub,
                "unit_system": self.unit_system, "manifest": self.manifest,
                "ids": self.ids}


def _utf16_strings(b: bytes, minlen: int = 3) -> List[str]:
    out = []
    for m in re.finditer(rb"(?:[\x20-\x7e]\x00){%d,}" % minlen, b):
        try:
            out.append(m.group().decode("utf-16-le"))
        except Exception:
            pass
    return out


def _name_of(rec) -> str:
    """Best-effort human name of a constructed record (manifest column)."""
    obj = getattr(rec, "obj", None) or {}
    if not isinstance(obj, dict):
        return ""
    for path in (("m_text",), ("m_viewName",), ("m_name",),
                 ("m_symbolInfo", "value", "m_name"),
                 ("m_pMaterial", "value", "m_name"),
                 ("m_pLinePattern", "value", "m_name"),
                 ("m_pFillPattern", "value", "m_name"),
                 ("m_pFont", "value", "m_name"),
                 ("m_pCategory", "value", "m_name")):
        cur: Any = obj
        ok = True
        for k in path:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and isinstance(cur, str) and cur:
            return cur
    return ""


# ---------------------------------------------------------------------------
# 16. SHIMS (resource-id dispositions the constructors do not parameterise)
# ---------------------------------------------------------------------------
#: scrub levels for build_catalog(scrub=...):
#:   'none' -- raw constructor output (Autodesk defaults intact; for A/B)
#:   'safe' -- name/label/number overlays that cannot affect the reader
#:            (load labels, signature enums, climate numbers, sun, poche,
#:            reference label)
#:   'full' -- 'safe' + blanking asset descriptors / render environments and
#:            OUR view-visibility policy (reader tolerance = viewer probe)
SCRUB_LEVELS = ("none", "safe", "full")


def _blank_asset_descriptor(a: Optional[dict]) -> None:
    """Blank an inline asset-binding descriptor {m_sName, m_sLibrary, ...}."""
    if not isinstance(a, dict):
        return
    if "m_sName" in a:
        a["m_sName"] = ""
    if "m_sLibrary" in a:
        a["m_sLibrary"] = ""


def _scrub_material(rec) -> None:
    """Disposition 'material-asset-descriptor': drop the Autodesk asset
    binding (name 'Generic', library 'assetlibrary_base.fbx', type 4)."""
    mat = ((rec.obj.get("m_pMaterial") or {}).get("value") or {})
    a = mat.get("m_asset")
    if isinstance(a, dict):
        _blank_asset_descriptor(a)
        if "m_eAssetType" in a:
            a["m_eAssetType"] = 0


def _scrub_view_render(view_rec) -> None:
    """Disposition 'view-render-assets': blank the render environment /
    quality / exposure asset descriptors of a view's ViewDisplayMgr."""
    vdm = (view_rec.obj.get("m_pViewDisplayMgr") or {}).get("value") or {}
    for key in ("m_oRaytraceSettings", "m_oStaticRRTRenderSettings"):
        rs = (vdm.get(key) or {}).get("value") or {}
        for akey in ("m_oEnvironmentAssets", "m_customQualityAsset", "m_oExposureAssets"):
            _blank_asset_descriptor(rs.get(akey))


def _scrub_view_visibility(view_rec, kind: str) -> None:
    """OUR visibility policy: overwrite the sample-template category
    exclusion list of a view's IckyExcludedCategoriesSet draw filter."""
    for df in view_rec.obj.get("m_oaDrawFilters") or []:
        if isinstance(df, dict) and df.get("ptr_class") == "IckyExcludedCategoriesSetPtrWrapper":
            df["value"]["m_categoryIds"] = list(DRAW_EXCLUDED_CATEGORIES[kind])


def _apply_load_class_labels(rec, spec: Dict[str, Any]) -> None:
    """Disposition 'load-class-labels' + finding F-HS-4 (signature enum)."""
    for k, v in LOAD_LABEL_TEMPLATES.items():
        rec.obj[k] = v
    rec.obj["m_signitureType"] = int(spec.get("signature", 0))
    rec.obj["m_spaceLoadClass"] = int(spec.get("space_class", 0))


def _apply_site_climate(site_rec) -> None:
    """Disposition 'site-location-defaults': neutral ISO-atmosphere climate."""
    T = float(SITE["isa_temperature_K"])
    o = site_rec.obj
    o["m_dSummerDryBulbTemperature"] = [T] * 12
    o["m_dSummerWetBulbTemperature"] = [T] * 12
    o["m_dMeanDailyTemperature"] = [T] * 12
    o["m_dWinterDryBulbTemperature"] = T
    o["m_ClearnessNumber"] = float(SITE["clearness_number"])
    o["m_placeName"] = str(SITE["place_name"])
    o["m_weatherStationName"] = str(SITE["weather_station"])
    o["m_zipCodeOrPostalCode"] = str(SITE["postal_code"])
    o["m_dElevation"] = float(SITE["elevation_m"]) / 0.3048


def _apply_view_sun(sun_rec) -> None:
    """Disposition 'sun-defaults' on a view-owned SunAndShadowSettings."""
    sun_rec.obj["m_sName"] = str(SUN["name"])
    sun_rec.obj["m_dAzimuth"] = math.radians(float(SUN["azimuth_deg"]))
    sun_rec.obj["m_dAltitude"] = math.radians(float(SUN["altitude_deg"]))


# ---------------------------------------------------------------------------
# 17. BUILD -- drive the constructors with OUR values
# ---------------------------------------------------------------------------

def build_catalog(start_id: int = 1_500_000, *, scrub: str = "full",
                  unit_system: str = "imperial") -> HouseCatalog:
    """Compose OUR complete genesis content -- element-type catalog + document
    skeleton -- from the tables above, allocating every id from one
    monotonic source starting at ``start_id``.

    Every cross-reference points at OUR OWN elements (materials -> our
    patterns, layers -> our materials, phasing overrides -> our phase
    materials/patterns, levels -> our units + geolocation, views -> our
    phases/filters/view types/levels): the catalog is SELF-CONTAINED
    (:meth:`HouseCatalog.dangling` == []).
    """
    if scrub not in SCRUB_LEVELS:
        raise ValueError(f"scrub must be one of {SCRUB_LEVELS}")
    ids = sk.IdSource(int(start_id))
    records: List[Any] = []
    manifest: List[dict] = []
    named: Dict[str, int] = {}

    def add(rec, kind: str = "", **params) -> Any:
        recs = rec if isinstance(rec, (list, tuple)) else [rec]
        for r in recs:
            records.append(r)
            manifest.append({"id": int(r.elem_id), "class": r.class_name,
                             "kind": kind or getattr(r, "kind", "") or r.class_name,
                             "name": _name_of(r),
                             **({"params": params} if params else {})})
        return rec

    cat = ty.GenesisCatalog(ids=ids)

    # ---- line & fill patterns (our drafting standard) --------------------
    lp: Dict[str, Any] = {}
    for spec in LINE_PATTERNS:
        lp[spec["key"]] = add(cat.line_pattern(spec["name"], spec["segments"]), "line-pattern")
    fp: Dict[str, Any] = {}
    for spec in FILL_PATTERNS:
        fp[spec["key"]] = add(cat.fill_pattern(spec["name"], spec["grids"]), "fill-pattern")

    # ---- materials (graphics-only; our colours) ---------------------------
    mats: Dict[str, Any] = {}
    for spec in MATERIALS:
        cutpat = fp[spec["cut_pattern"]].elem_id if spec.get("cut_pattern") else INVALID
        rec = cat.material(spec["name"], tuple(spec["rgb"]),
                           material_class=spec["material_class"],
                           category=spec["category"],
                           transparency=float(spec.get("transparency", 0.0)),
                           cut_pattern_id=cutpat)
        if scrub == "full":
            _scrub_material(rec)                       # drop Autodesk asset binding
        mats[spec["key"]] = add(rec, "material", rgb=spec["rgb"])

    # ---- system-family types (our assemblies) ------------------------------
    def _layers(spec_layers):
        return [(fn, th, mats[m].elem_id if m else INVALID) for fn, th, m in spec_layers]

    for spec in WALL_TYPES:
        add(cat.wall_type(spec["name"], _layers(spec["layers"]),
                          function=int(spec["function"]),
                          fill_pattern_id=(fp[spec["fill"]].elem_id if spec.get("fill")
                                           else INVALID),
                          sample_height_mm=WALL_SAMPLE_HEIGHT_MM),
            "wall-type", rationale=spec["rationale"])
    for spec in FLOOR_TYPES:
        add(cat.floor_type(spec["name"], _layers(spec["layers"])), "floor-type",
            rationale=spec["rationale"])
    for spec in ROOF_TYPES:
        add(cat.roof_type(spec["name"], _layers(spec["layers"])), "roof-type",
            rationale=spec["rationale"])
    for spec in CEILING_TYPES:
        add(cat.ceiling_type(spec["name"], _layers(spec["layers"])), "ceiling-type",
            rationale=spec["rationale"])

    # ---- electrical definitions -------------------------------------------
    volt: Dict[Any, Any] = {}
    for spec in VOLTAGES:
        volt[spec["key"]] = add(cat.voltage_type(spec["name"], spec["nominal"],
                                                  min_volts=spec["min"], max_volts=spec["max"]),
                                 "voltage-type", nominal=spec["nominal"],
                                 source="ANSI C84.1 Range A")
    for spec in DISTRIBUTION_SYSTEMS:
        add(cat.distribution_system(
            spec["name"], phase=spec["phase"], config=spec["config"], wires=int(spec["wires"]),
            voltage_ll_id=(volt[spec["ll"]].elem_id if spec.get("ll") else INVALID),
            voltage_lg_id=(volt[spec["lg"]].elem_id if spec.get("lg") else INVALID)),
            "distribution-system", source="ANSI C84.1 Table 1")
    dem: Dict[str, Any] = {}
    for spec in DEMAND_FACTORS:
        first_factor = float(spec["rows"][0][2])
        dem[spec["key"]] = add(cat.demand_factor(spec["name"], first_factor,
                                                  rule=int(spec["rule"]),
                                                  rows=list(spec["rows"])),
                                "demand-factor", source=spec["source"])
    for spec in LOAD_CLASSIFICATIONS:
        rec = cat.load_class(spec["name"], dem[spec["demand"]].elem_id,
                             space_load_class=int(spec["space_class"]))
        if scrub != "none":
            _apply_load_class_labels(rec, spec)       # our labels + enums
        add(rec, "load-classification")
    es = ELECTRICAL_SETTING
    add(cat.electrical_setting(
        phase_labels=tuple(es["phase_labels"]),
        circuit_rating=float(es["circuit_rating_A"]),
        circuit_path_offset_mm=float(es["circuit_path_offset_mm"]),
        specific_angles_deg=tuple(es["specific_angles_deg"]),
        load_calc_method=int(es["load_calc_method"]),
        run_load_calcs_in_spaces=bool(es["run_load_calcs_in_spaces"]),
        include_spares_in_totals=bool(es["include_spares_in_totals"]),
        merge_multi_pole_circuits=bool(es["merge_multi_pole_circuits"]),
        space_label=str(es["space_label"]), spare_label=str(es["spare_label"])),
        "electrical-setting")

    # ---- conduit / cable tray / wire ---------------------------------------
    std: Dict[str, Any] = {}
    for spec in CONDUIT_STANDARDS:
        std[spec["key"]] = add(cat.conduit_standard(spec["name"]), "conduit-standard",
                               source=spec["source"])
    add(cat.conduit_sizes({std[s["key"]].elem_id: conduit_size_rows(s)
                           for s in CONDUIT_STANDARDS}),
        "conduit-sizes-table", source="NEC Ch.9 Table 4 / Table 2")
    for spec in CONDUIT_TYPES:
        add(cat.conduit_type(spec["name"], standard_id=std[spec["standard"]].elem_id,
                             with_fitting=bool(spec["with_fitting"])), "conduit-type")
    add(cat.cable_tray_sizes(list(CABLE_TRAY_WIDTHS_IN)), "cable-tray-sizes-table",
        source="NEMA VE 1")
    for spec in CABLE_TRAY_TYPES:
        add(cat.cable_tray_type(spec["name"], shape=spec["shape"]), "cable-tray-type")
    # conductor definition cells (shared by the wire types)
    cmat = {n: add(cat.add(ty.new_conductor_material(n, ids=ids)), "conductor-material")
            for n in CONDUCTOR_MATERIALS}
    ctmp = {n: add(cat.add(ty.new_conductor_temperature_rating(n, ids=ids)),
                   "conductor-temperature-rating") for n in CONDUCTOR_TEMPERATURE_RATINGS_C}
    cins = {n: add(cat.add(ty.new_conductor_insulation(n, ids=ids)), "conductor-insulation")
            for n in CONDUCTOR_INSULATIONS}
    csiz = {n: add(cat.add(ty.new_conductor_size(n, d, ids=ids)), "conductor-size",
                   diameter_mm=d, source="NEC Ch.9 Table 8")
            for n, d in CONDUCTOR_MAX_SIZES}
    for spec in WIRE_TYPES:
        add(cat.wire_type(spec["name"], material_id=cmat[spec["material"]].elem_id,
                          temperature_rating_id=ctmp[spec["temperature"]].elem_id,
                          insulation_id=cins[spec["insulation"]].elem_id,
                          max_size_id=csiz[spec["max_size"]].elem_id,
                          conduit_type=spec["conduit_type"]), "wire-type")

    # ---- annotation standards: text types (4 elements each) --------------
    for spec in TEXT_TYPES:
        add(cat.text_type(spec["name"], font=TEXT_FONT, size_mm=float(spec["size_mm"]),
                          bold=bool(spec.get("bold", False))),
            "text-type", size_mm=spec["size_mm"], source="ISO 3098")

    # ---- OUR OBJECT STYLES house standard -------------------------------
    for cat_id, label, discipline, cuttable in HOUSE_CATEGORIES:
        proj_pen, cut_pen, colour = HOUSE_SCHEME[discipline]
        gs = ty.new_gstyle(cat_id, style_type="projection", pen=proj_pen, color=colour,
                           line_pattern_id=SOLID_LINE, material_id=INVALID, ids=ids)
        cat.add(gs)
        records.append(gs)
        manifest.append({"id": gs.elem_id, "class": gs.class_name, "kind": "object-style",
                         "name": f"{label} / projection",
                         "params": {"category": cat_id, "discipline": discipline,
                                    "pen": proj_pen, "color": colour}})
        if cuttable:
            gc = ty.new_gstyle(cat_id, style_type="cut", pen=cut_pen, color=colour,
                               line_pattern_id=SOLID_LINE, material_id=INVALID, ids=ids)
            cat.add(gc)
            records.append(gc)
            manifest.append({"id": gc.elem_id, "class": gc.class_name, "kind": "object-style",
                             "name": f"{label} / cut",
                             "params": {"category": cat_id, "discipline": discipline,
                                        "pen": cut_pen, "color": colour}})
    # ---- OUR sub-categories (a firm's own line-style vocabulary) -------
    for name, parent_ost, ctype, pen, colour, patkey, discipline in SUB_CATEGORIES:
        cat_id = ids.next()
        gs = ty.new_gstyle(cat_id, style_type="projection", pen=pen, color=colour,
                           line_pattern_id=lp[patkey].elem_id, material_id=INVALID, ids=ids)
        ce = ty.new_category(name, parent_ost, INVALID, category_type=ctype,
                             gstyle_ids=[gs.elem_id], elem_id=cat_id)
        cat.add(ce)
        cat.add(gs)
        for r, kind in ((ce, "sub-category"), (gs, "object-style")):
            records.append(r)
            manifest.append({"id": r.elem_id, "class": r.class_name, "kind": kind,
                             "name": name if r is ce else f"{name} / projection",
                             "params": {"parent": parent_ost, "discipline": discipline}})

    # ================= SKELETON (units / site / levels / phases / views) =====
    fmts = UNIT_FORMATS_IMPERIAL if unit_system == "imperial" else UNIT_FORMATS_METRIC
    uflags = UNIT_SYSTEM_FLAGS[unit_system if unit_system in UNIT_SYSTEM_FLAGS else "imperial"]
    units = add(sk.new_units_elem(ids.next(), fmts, **uflags), "units-registry",
                entries=len(fmts), unit_system=unit_system)
    tn = add(sk.new_true_north(ids.next(), math.radians(TRUE_NORTH_ANGLE_DEG)), "true-north")
    if scrub != "none":
        tn.obj["m_pocheDepth"] = -abs(float(POCHE_DEPTH_FT))       # our poche depth
    lat = math.radians(float(SITE["latitude_deg"]))
    lon = math.radians(float(SITE["longitude_deg"]))
    site_int = sk.new_geo_site(ids.next(), SITE["site_symbol_name"], latitude_rad=lat,
                               longitude_rad=lon, timezone_h=float(SITE["timezone_h"]))
    site_prj = sk.new_geo_site(ids.next(), SITE["site_symbol_name"], latitude_rad=lat,
                               longitude_rad=lon, timezone_h=float(SITE["timezone_h"]))
    if scrub != "none":
        _apply_site_climate(site_int)
        _apply_site_climate(site_prj)
    add(site_int, "geo-site", latitude_deg=SITE["latitude_deg"],
        longitude_deg=SITE["longitude_deg"])
    add(site_prj, "geo-site", latitude_deg=SITE["latitude_deg"],
        longitude_deg=SITE["longitude_deg"])
    loc_int = add(sk.new_geo_location(ids.next(), site_int.elem_id,
                                      SITE["internal_location_name"]), "geo-location")
    loc_prj = add(sk.new_geo_location(ids.next(), site_prj.elem_id,
                                      SITE["project_location_name"]), "geo-location")
    add(sk.new_base_point(ids.next(), shared=False, geolocation_id=loc_prj.elem_id),
        "project-base-point")
    add(sk.new_base_point(ids.next(), shared=True, geolocation_id=loc_prj.elem_id),
        "survey-point")
    ltype = add(sk.new_level_type(ids.next(), LEVEL_TYPE_NAME, font_id=INVALID,
                                  head_family_symbol_id=INVALID,
                                  room_computation_height_ft=ROOM_COMPUTATION_HEIGHT_FT),
                "level-type")
    lvl: Dict[str, Any] = {}
    for spec in LEVELS:
        lvl[spec["key"]] = add(sk.new_level(
            ids.next(), spec["name"], float(spec["elevation_ft"]), ltype.elem_id,
            units_id=units.elem_id, geolocation_id=loc_prj.elem_id,
            datum_length_ft=LEVEL_DATUM_LENGTH_FT, is_building_story=True),
            "level", elevation_ft=spec["elevation_ft"])
    lv1, lv2 = lvl[LEVELS[0]["key"]], lvl[LEVELS[1]["key"]]
    # phases: allocate the phase-set id first so each phase points at it
    allph_id = ids.next()
    phase_recs: Dict[str, Any] = {}
    for spec in PHASES:
        phase_recs[spec["key"]] = add(sk.new_phase(ids.next(), spec["name"],
                                                    spec["description"],
                                                    all_phases_id=allph_id), "phase")
    overrides = phasing_overrides(mats, lp, fp)
    allph = add(sk.new_all_project_phases(allph_id, [p.elem_id for p in phase_recs.values()],
                                          phasing_overrides=overrides), "phase-set")
    filters = []
    for name, is_default, pres in PHASE_FILTERS:
        filters.append(add(sk.new_phase_filter(ids.next(), name, pres, is_default,
                                               regen_only=[allph.elem_id]), "phase-filter"))
    show_all = next(f for f in filters if f.obj.get("m_bDefault")).elem_id
    pinfo = add(sk.new_project_info(
        ids.next(), project_name=PROJECT_INFO["project_name"],
        project_number=PROJECT_INFO["project_number"], address=PROJECT_INFO["address"],
        client_name=PROJECT_INFO["client_name"],
        project_status=PROJECT_INFO["project_status"],
        issue_date=PROJECT_INFO["issue_date"],
        organization_name=PROJECT_INFO["organization_name"],
        organization_description=PROJECT_INFO["organization_description"],
        building_name=PROJECT_INFO["building_name"], author=PROJECT_INFO["author"]),
        "project-info", project_name=PROJECT_INFO["project_name"])
    doc_sun = add(sk.new_document_sun_settings(
        ids.next(), name=str(SUN["name"]),
        azimuth_rad=math.radians(float(SUN["azimuth_deg"])),
        altitude_rad=math.radians(float(SUN["altitude_deg"]))), "document-sun-settings")
    ph_new = phase_recs["new"]
    proj_view = sk.new_project_view(ids, phase_id=ph_new.elem_id, phase_filter_id=show_all,
                                    sun_settings_id=doc_sun.elem_id)
    if scrub == "full":
        _scrub_view_render(proj_view.view)
        _scrub_view_visibility(proj_view.view, "project")
    add(proj_view.elements(), "project-view-constellation")
    vt: Dict[str, Any] = {}
    for spec in VIEW_TYPES:
        vt[spec["key"]] = add(sk.new_view_type(ids.next(), spec["name"], spec["family"]),
                               "view-type", family=spec["family"])
        if scrub != "none":
            vt[spec["key"]].obj["m_refLabelStr"] = VIEW_REF_LABEL
    v3 = sk.new_3d_view(ids, VIEW_3D_NAME, vt["3d"].elem_id, phase_id=ph_new.elem_id,
                        phase_filter_id=show_all, ground_level_id=lv1.elem_id,
                        eye_ft=VIEW_3D_EYE_FT, target_ft=VIEW_3D_TARGET_FT,
                        scale=VIEW_3D_SCALE)
    pv1 = sk.new_plan_view(ids, LEVELS[0]["name"], lv1.elem_id, float(LEVELS[0]["elevation_ft"]),
                           vt["floor_plan"].elem_id, phase_id=ph_new.elem_id,
                           phase_filter_id=show_all, level_below_id=INVALID,
                           level_below_elevation_ft=0.0,
                           cut_offset_ft=PLAN_CUT_OFFSET_FT, top_offset_ft=PLAN_TOP_OFFSET_FT,
                           scale=PLAN_SCALE, detail_level=PLAN_DETAIL_LEVEL,
                           discipline=PLAN_DISCIPLINE)
    pv2 = sk.new_plan_view(ids, LEVELS[1]["name"], lv2.elem_id, float(LEVELS[1]["elevation_ft"]),
                           vt["floor_plan"].elem_id, phase_id=ph_new.elem_id,
                           phase_filter_id=show_all, level_below_id=lv1.elem_id,
                           level_below_elevation_ft=float(LEVELS[0]["elevation_ft"]),
                           cut_offset_ft=PLAN_CUT_OFFSET_FT, top_offset_ft=PLAN_TOP_OFFSET_FT,
                           scale=PLAN_SCALE, detail_level=PLAN_DETAIL_LEVEL,
                           discipline=PLAN_DISCIPLINE)
    for spec_view, kind in ((v3, "3d"), (pv1, "plan"), (pv2, "plan")):
        for el in spec_view.elements():
            if el.class_name == "SunAndShadowSettings" and scrub != "none":
                _apply_view_sun(el)                        # our sun on view suns
            if el is spec_view.view and scrub == "full":
                _scrub_view_render(el)
                _scrub_view_visibility(el, kind)
    add(v3.elements(), "3d-view-constellation")
    add(pv1.elements(), "plan-view-constellation", level=LEVELS[0]["name"])
    add(pv2.elements(), "plan-view-constellation", level=LEVELS[1]["name"])

    # ================= conversion to the commit shape ==========================
    records.sort(key=lambda x: x.elem_id)
    manifest.sort(key=lambda m: m["id"])
    elements = [r.as_new_element(creation_ep=0) for r in records]
    named.update({
        "units": units.elem_id, "level1": lv1.elem_id, "level2": lv2.elem_id,
        "phase_new": ph_new.elem_id, "phase_existing": phase_recs["existing"].elem_id,
        "phase_set": allph.elem_id, "project_view": proj_view.view.elem_id,
        "view_3d": v3.view.elem_id, "project_info": pinfo.elem_id,
        "geo_location": loc_prj.elem_id, "true_north": tn.elem_id,
        "document_sun": doc_sun.elem_id})
    return HouseCatalog(records=records, elements=elements, manifest=manifest,
                        ids=named, start_id=int(start_id), last_id=ids.watermark,
                        scrub=scrub, unit_system=unit_system)


def phasing_overrides(mats: Dict[str, Any], lp: Dict[str, Any], fp: Dict[str, Any]) -> list:
    """OUR ``AllProjectPhases.m_arrPhasingOverrides`` from
    :data:`PHASE_STATUS_GRAPHICS` (pens/colours/patterns/materials all ours)."""
    line_of = {"solid": SOLID_LINE}
    out = []
    for g in PHASE_STATUS_GRAPHICS:
        line = line_of.get(g["line"], lp[g["line"]].elem_id if g["line"] in lp else SOLID_LINE)
        ogs = sk.override_graphic_settings(
            proj_pen=int(g["proj_pen"]), cut_pen=int(g["cut_pen"]),
            cut_fill_visible=bool(g["cut_fill_visible"]),
            proj_pen_color=int(g["pen_color"]), cut_pen_color=int(g["pen_color"]),
            proj_line_pattern=int(line), cut_line_pattern=int(line),
            cut_fill_pattern=(fp["solid"].elem_id if g["cut_fill_visible"] else -1),
            cut_fill_color=int(g["cut_fill_color"]))
        out.append(_skel_ptr("PhasingOverrides", {
            "m_elementOnPhaseStatus": int(g["status"]),
            "m_oOverrideGraphicSettings": ogs,
            "m_oGMaterialOverrider": _skel_ptr("GMaterialOverrider",
                                                {"m_materialId": int(mats[g["material"]].elem_id)}),
        }))
    return out


# ---------------------------------------------------------------------------
# 18. SIMILARITY vs the six samples (the G1b measurement)
# ---------------------------------------------------------------------------

def similarity_report(cat: HouseCatalog, samples: Sequence[str] = tuple(SAMPLES), *,
                      threshold: float = 0.85, verbose: bool = False) -> dict:
    """Max 16-byte-shingle similarity (the provenance ledger's metric) of
    every record against every element of the same class in EACH sample
    document.  Returns per-record maxima + the >= ``threshold`` list, each
    tagged 'no-free-choice' (class registered in :data:`NO_FREE_CHOICE`) or
    'VIOLATION'.  Samples are read from the extracted research corpus
    (``rvt.mutate.Document.load``); missing ones are recorded as skipped.
    """
    from ..mutate import Document
    from ..provenance import _CloneIndex
    recs = cat.encoded()
    best: Dict[int, dict] = {}
    skipped: List[str] = []
    used: List[str] = []
    for s in samples:
        try:
            base = Document.load(s)
        except Exception as e:                       # sample not extracted here
            skipped.append(f"{s} ({type(e).__name__}: {e})")
            continue
        used.append(s)
        ci = _CloneIndex(base)
        for eid, cls, body, kind, name in recs:
            try:
                clone_of, sim = ci.best_match(cls, body)
            except Exception:
                clone_of, sim = None, 0.0
            cur = best.get(eid)
            if cur is None or sim > cur["max_similarity"]:
                best[eid] = {"id": eid, "class": cls, "kind": kind, "name": name,
                             "max_similarity": round(float(sim), 3), "vs_sample": s,
                             "vs_element": clone_of}
        if verbose:
            hi = sum(1 for v in best.values() if v["max_similarity"] >= threshold)
            print(f"  {s:26s} running >= {threshold}: {hi}", flush=True)
    over = []
    for v in best.values():
        if v["max_similarity"] >= threshold:
            reason = NO_FREE_CHOICE.get(v["class"])
            v = dict(v, status=("no-free-choice" if reason else "VIOLATION"),
                     justification=reason or "class not registered as no-free-choice")
            over.append(v)
    over.sort(key=lambda d: -d["max_similarity"])
    by_class: Dict[str, float] = {}
    for v in best.values():
        by_class[v["class"]] = max(by_class.get(v["class"], 0.0), v["max_similarity"])
    return {
        "samples_used": used, "samples_skipped": skipped, "threshold": threshold,
        "records": len(recs),
        "over_threshold": over,
        "violations": [o for o in over if o["status"] == "VIOLATION"],
        "class_max": dict(sorted(by_class.items(), key=lambda kv: -kv[1])),
        "per_record": [best[i] for i in sorted(best)],
    }


# ---------------------------------------------------------------------------
# 19. DEMO / self-test
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    cat = build_catalog()
    rt = cat.roundtrip()
    dangling = cat.dangling()
    counts = cat.counts_by_class()
    print(f"HOUSE STANDARD catalog: {len(cat.records)} elements, "
          f"{len(counts)} classes, ids {cat.start_id}..{cat.last_id} "
          f"(scrub={cat.scrub}, units={cat.unit_system})")
    print(f"  round-trip clean+byte-exact: {rt['ok']}/{rt['records']}  "
          f"dangling references: {len(dangling)}")
    for f in rt["failures"][:5]:
        print("   FAIL", f)
    for k, n in counts.items():
        print(f"   {n:4d} x {k}")
    scan = cat.identifier_scan()
    print(f"  identifier strings remaining in serialized records: {len(scan)}")
    for s, h in sorted(scan.items(), key=lambda kv: -kv[1]["count"]):
        print(f"     {h['count']:4d} x {s!r}  {h['classes']}")
    rc = 0 if (rt["ok"] == rt["records"] and not dangling) else 1
    if "--similarity" in argv:
        print("== similarity vs the six samples (threshold 0.85)")
        rep = similarity_report(cat, verbose=True)
        print(f"  samples used: {rep['samples_used']}  skipped: {rep['samples_skipped']}")
        for o in rep["over_threshold"]:
            print(f"   {o['max_similarity']:.2f} {o['class']:26s} {o['status']:15s} "
                  f"{o['name'][:36]}  (vs {o['vs_sample']} ~{o['vs_element']})")
        print(f"  VIOLATIONS: {len(rep['violations'])}")
        if rep["violations"]:
            rc = 2
    if "--json" in argv:
        json.dump({"catalog": cat.to_json(),
                   "dispositions": RESOURCE_ID_DISPOSITIONS,
                   "constructor_diffs": CONSTRUCTOR_DIFFS,
                   "findings": FINDINGS}, sys.stdout, indent=1, default=str)
        print()
    return rc


if __name__ == "__main__":
    sys.exit(main())

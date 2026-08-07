"""genesis/port2024.py -- the Revit-2024 PORTABILITY LAYER over the 2026
constructors (genesis-2024 campaign, constructor side).

The 2026 constructors (``rvt.genesis.types`` / ``settings`` / ``catalog`` /
``skeleton`` / ``residue_*``) build schema-directed objects against the 2026
archive class map.  This module WRAPS them -- it never edits them (and never
edits ``port2025`` either; where the Revit-2024 layout EQUALS the Revit-2025
layout it DELEGATES to port2025's machinery, recorded per delegation):

    adapt(class_name, obj_2026)  ->  obj_2024
    adapt_record(record_2026)    ->  PortedRecord (2024 class ids, 2024-shaped
                                     seq-101/102/103 bodies)

The transform is port2025's CONFIRMED method re-run for 2024: walk the
TARGET (2024) class chain field by field against the pinned
``rvt.versions.schema_2024`` map, carry every field that exists under the
same name in the 2026 source object (recursively adapting nested
owned/inline class values), synthesise a 2024 schema-blank default for
fields the 2026 object does not have, and apply the CONFIRMED per-class
hooks where a blank default is not the corpus value.  2026-only fields
disappear by construction.  Classes absent from the 2024 map raise
:class:`Missing2024`.

CONFIRMED PORTABILITY VERDICT (``--verify`` re-derives it; frozen copy:
``experiments/genesis2024/miners/portability-2024.json``).  Method =
port2025's section-6 method, re-run: own-field signatures by type NAME,
flattened parent-first chain layout, per-class versions, 2026 pin vs the
2024 pin -- PLUS a three-way annotation against the 2026-vs-2025 table,
because 2024 did NOT evolve monotonically from 2025's deltas.

THE THREE-WAY RESULT over the same 403-class universe (326 harvested + chain
expansion): 347 IDENTICAL / 40 LAYOUT-DELTA / 13 MISSING-2024 /
3 VERSION-ONLY (DataStorage v3->0, ElementHeader v25->24, FamilyInstance
v39->37 -- free: records carry no version).  Deltas that are the SAME as
2025's (22 classes; port2025's hooks apply verbatim): GeomTable,
NumberingSchema, BrowserOrganization, BrowserOrganizationTracking (v6->5,
same three-field split), ModelGraphicsStyle, ViewDisplayMgr,
ReinforcementSettings, RbsWireSettingsElem, RbsWireSizesElem (v8->3, drop
m_bInitialized), RbsWireType, AssemblyCodeTable, KeynoteTable,
StructSettingsElem, DBView + every constructed view subclass
(m_viewPositionId drop), Viewport (v13->10, the SAME v10 as 2025 -- 2025
kept 2024's layout), Section/SectionGraphics.

DELTAS THAT DIFFER FROM 2025's (established independently, never assumed):

* ``GeomStep`` v17->15: ``m_oExtraDatas`` is simply ABSENT in 2024 -- there
  is NO ``m_oExtraData`` twin (2025 renamed; 2024 predates the field).  The
  port2025 rename hook MUST NOT be carried; the field drops by construction.
* ``DBViewDrafting`` v12->11: 2024 additionally lacks ``m_sheetCollectionId``
  (2025 had it) and carries 2024-only ``m_scheduleInstanceIds``
  (ElementId container; corpus value on fresh drafting views = EMPTY,
  8/8 rst specimens -> the schema blank [] IS the corpus value, no hook).
* ``AutoCamSettingsElem`` v6->5 (2025 == 2026): the seven camera vectors are
  RENAMED and RE-TYPED -- 2026 inline ``XYZ`` fields ``m_homeEyeXYZ`` etc.
  are 2024 fixed ``double[3]`` arrays ``m_homeEye`` etc. (value-compatible
  [x,y,z] lists; field order also differs -- the target-chain walk handles
  order).  Hooked for all seven.  OUR constructor's values are byte-exact
  against the 2024 rst specimen 102842 (fresh home state, scene frame
  +Y front / +Z up) -- verified in :func:`selftest`.
* ``RbsDuctSettingsElem`` v15->14 (2025 == 2026): 2026
  ``m_airDynamicViscosity`` (dynamic viscosity, kg/(ft.s)) becomes 2024
  ``m_dAirViscosity`` -- a DIFFERENT QUANTITY: the KINEMATIC viscosity in
  ft^2/s.  CONFIRMED bit-exact in Autodesk's own corpus: 2024 rst
  m_dAirViscosity 0.0001622533748701973 == 2026 rst m_airDynamicViscosity
  5.52543392433963e-06 / m_dAirDensity 0.034054354362490005 (both files
  carry the SAME m_dAirDensity).  Hook computes nu = mu / rho from the
  source object's own fields.
* ``MEPNetworkTracker`` v4->3 (2025 == 2026): 2026
  ``m_component2BaseSegmentMap`` (pairs of NetworkSegmentId) becomes 2024
  ``m_component2BaseElementMap`` (pairs of ElementId).  Our tracker
  constructor and every corpus specimen carry the EMPTY map; the hook
  carries empty verbatim and refuses a non-empty source (no lossless
  NetworkSegmentId->ElementId mapping exists).
* ``RbsDistributionSysType`` v2->1: 2026-only ``m_highLegPhase`` dropped
  (generic walk).
* ``HVACLoadScheduleElem`` v4->3: same two own fields, opposite ORDER
  (walk handles).  ``FamilyBase`` v48->47 additionally drops
  ``m_familyNestingBehavior`` + ``m_tagOrientationBehavior`` vs 2025;
  ``IndependentTag`` v22->21 drops three head-position fields and gains
  ``m_taggedEntitiesCell``; ``Rebar`` v57->54 drops ``m_frozenSegments``
  (2025 was VERSION-ONLY) -- none of these three is constructed (harvest
  name-collisions / regen-wildcard classrefs; recorded with provenance).

MISSING-2024 BEYOND THE CONDUCTOR CATALOG -- five classes 2025 HAS that
2024 lacks, ALL constructed by genesis, so their constructors emit NOTHING
on a 2024 build (:data:`MISSING_2024_CONSTRUCTED`):
``SheetCollection``, ``SheetsInSheetCollectionTracker``,
``MEPNetworkDataElem``, ``STEPExportSettings``,
``BuildingOperatingYearSchedule`` (+ the 8 conductor-catalog classes 2025
also lacks).

MINED 2024 corpus constants: every port2025 mined value RE-DERIVED
INDEPENDENTLY from the quarantined ``samples/2024`` corpus (rst specimens
cited per constant below); all equal their 2025 twins EXCEPT nothing --
the 2024 corpus agrees with 2025 on every re-mined value, and adds the
duct-viscosity arithmetic above.  Catalog / pen / palette miners:
``--mine`` freezes ``builtin_category_enum_2024.json``,
``builtin_style_profile_2024.json``, ``pen_table_2024.json``,
``palette_invariants_2024.json`` under ``experiments/genesis2024/miners/``.

DELEGATIONS TO port2025 (recorded; each verified safe for 2024):

* ``PortabilityError`` base class; ``_AdaptContext``; the dec-parameterised
  blank machinery ``_blank_class25 / _blank_field25 / _blank_scalar25``
  (release-agnostic: every schema lookup goes through the decoder argument
  -- passing the 2024 decoder yields 2024 blanks).
* The pure value hooks ``_hook_sort_param_id`` /
  ``_hook_numbering_min_digits`` / ``_hook_numbering_matching`` /
  ``_browser_tracking_tree`` (no schema binding).
* The numbering hooks ``_hook_numbering_partition_creator`` /
  ``_hook_numbering_type_guid`` build 2025-blank bodies for
  ``ParameterBasedPartitionDescriptionCreator`` / ``NumberingSchemaType``:
  both classes are LAYOUT-IDENTICAL 2024==2025 (verified in ``--verify``
  and tests), and the 2024-mined GUID table equals the 2025 one, so the
  2025 blanks ARE 2024 blanks.  The walk itself is bound to the 2024
  schema here (port2025's walk is hardwired to its 2025 singleton).

Round-trip gate: every adapted object must encode -> decode -> re-encode
BYTE-EXACT under the 2024 schema (:func:`verify_roundtrip_2024`;
tests/test_port2024.py runs it over the constructor battery).  Specimen
gate (byte-level, where the 2026 method verified byte-level):
:func:`verify_specimen_byte_level` proves OUR adapted AutoCamSettingsElem
and MEPNetworkTracker BYTE-EXACT against the 2024 rst specimens (102842 /
1468014), the pen-table layout byte-exact with specimen vectors re-fed,
and specimen re-encode round-trips for every ported constructor class.

Territory: this module, tests/test_port2024.py,
experiments/genesis2024/miners/**, docs/inbox/genesis-2024-port.md.
Python: ALWAYS ``.venv/bin/python`` from the repo root.

CLI::

    .venv/bin/python -m rvt.genesis.port2024 --verify    # portability table
    .venv/bin/python -m rvt.genesis.port2024 --mine      # 2024 corpus miners
    .venv/bin/python -m rvt.genesis.port2024 --selftest  # adapt+roundtrip+specimen
"""
from __future__ import annotations

import ast
import collections
import copy
import dataclasses
import json
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple

from .types import INVALID, NULL_GUID
from .port2025 import (
    PortabilityError,
    _AdaptContext,
    _blank_class25 as _blank_class_for,      # dec-parameterised, release-agnostic
    _blank_field25 as _blank_field_for,
    _blank_scalar25 as _blank_scalar_for,
    _browser_tracking_tree,
    _hook_numbering_matching,
    _hook_numbering_min_digits,
    _hook_numbering_partition_creator,       # 2025 blanks; layout-identical in 2024
    _hook_numbering_type_guid,               # (verified: see module docstring)
    _hook_sort_param_id,
)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
GENESIS_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "experiments", "genesis2024", "miners")
PORTABILITY_JSON = os.path.join(OUT_DIR, "portability-2024.json")
ENUM_2024_JSON = os.path.join(OUT_DIR, "builtin_category_enum_2024.json")
PROFILE_2024_JSON = os.path.join(OUT_DIR, "builtin_style_profile_2024.json")
PEN_2024_JSON = os.path.join(OUT_DIR, "pen_table_2024.json")
PALETTE_2024_JSON = os.path.join(OUT_DIR, "palette_invariants_2024.json")

#: the quarantined 2024 samples (DEV-ONLY field oracles; never shipped)
SAMPLES_2024 = os.path.join(ROOT, "samples", "2024")
RST_2024 = os.path.join(SAMPLES_2024, "rstbasicsampleproject.rvt")

#: portability layers are NOT constructors -- ALL of them are excluded from
#: the harvest (port2025.py, this module, and any sibling stream's
#: port20XX.py, e.g. the 2023 stream's port2023.py which appeared while
#: this stream ran and whose field-map literals are not constructions)
def _is_port_layer(fn: str) -> bool:
    return fn.startswith("port20") and fn.endswith(".py")


class Missing2024(PortabilityError):
    """The class does not exist in the Revit-2024 archive class map."""


#: classes genesis CONSTRUCTS that have NO Revit-2024 twin: the conductor
#: catalog (2026-only, same refusal as 2025) PLUS the five 2025-era classes
#: below.  Their constructors emit nothing on a 2024 build.
MISSING_2024_CONSTRUCTED: Tuple[str, ...] = (
    # 2026-only (also missing in 2025): the conductor catalog
    "CustomElement", "NamingCell", "RbsConductorMaterial",
    "RbsConductorTemperatureRating", "RbsConductorInsulationMaterial",
    "RbsConductorSize",
    # present in 2025, ABSENT in 2024 (this stream's finding):
    "SheetCollection", "SheetsInSheetCollectionTracker", "MEPNetworkDataElem",
    "STEPExportSettings", "BuildingOperatingYearSchedule",
)


# ---------------------------------------------------------------------------
# schema / codec singletons (2026 = the genesis default; 2024 = the pin)
# ---------------------------------------------------------------------------
_STATE: Dict[str, Any] = {}


def _S26():
    """(decoder, encoder, schema) for the canonical 2026 map."""
    if "s26" not in _STATE:
        from .types import _S
        _STATE["s26"] = _S()
    return _STATE["s26"]


def _S24():
    """(decoder, encoder, schema) for the pinned Revit-2024 map."""
    if "s24" not in _STATE:
        from ..encode import ObjectEncoder
        from ..objects import ObjectDecoder
        from ..versions import schema_2024
        dec = ObjectDecoder(schema_2024.load())
        _STATE["s24"] = (dec, ObjectEncoder(decoder=dec), dec.schema)
    return _STATE["s24"]


def class_id_2024(name: str) -> int:
    """u16 Revit-2024 archive class id of ``name`` (raises Missing2024)."""
    _dec, _enc, schema = _S24()
    cd = schema.by_name.get(name)
    if cd is None:
        raise Missing2024(f"class {name!r} is not in the Revit-2024 archive class map")
    return cd.type_id


def exists_2024(name: str) -> bool:
    _dec, _enc, schema = _S24()
    return name in schema.by_name


def blank_object_2024(class_name: str) -> dict:
    """A complete, 2024-encoder-ready object dict for ``class_name`` (the
    2024 twin of ``types.blank_object`` -- port2025's dec-parameterised
    blank machinery walked with the 2024 decoder)."""
    dec, _enc, schema = _S24()
    cd = schema.by_name.get(class_name)
    if cd is None:
        raise Missing2024(f"class {class_name!r} is not in the Revit-2024 archive class map")
    return _blank_class_for(dec, cd.type_id, 0)


# ---------------------------------------------------------------------------
# MINED 2024 corpus constants (field oracles; provenance in each comment).
# Everything below was DECODED from the quarantined samples/2024 corpus --
# independently RE-MINED, never assumed equal to the 2025 constants (they
# all came out equal; the duct-viscosity arithmetic is 2024-new).
# ---------------------------------------------------------------------------
#: RbsWireSettingsElem's three 2024-only doubles (same three fields as the
#: 2025 delta).  Decoded from the 2024 rst sample elem 102129: the 2 % / 3 %
#: max voltage-DROP sizing fractions and 30 degC ambient in kelvin
#: (303.15000000000003 is the EXACT stored double -- equal to 2025's).
WIRE_SETTINGS_2024 = {
    "m_dMaxVoltageBranchSizing": 0.02,
    "m_dMaxVoltageFeederSizing": 0.03,
    "m_dAmbientTemperature": 303.15000000000003,
}

#: GeomTable's two 2024-only leading ints.  Corpus value for fresh/empty
#: tables is (-1, -1): 5,620 of 5,637 GeomTables decoded from the 2024 rst
#: sample carry exactly that (the same 5,620/5,637 ratio the 2025 miner saw).
GEOMTABLE_2024 = {"m_maxSafeTag": -1, "m_lastCheckedKingsUserModificationDate": -1}

#: NumberingSchema 2024: schemaTypeGuid per scope category, decoded from the
#: 2024 rst sample's three built-in numbering schemas (1218729 rebar /
#: 1457391 couplers / 1218730 fabric sheets) -- identical GUIDs to 2025
#: (product identity of Revit's numbering machinery, stable across releases).
NUMBERING_SCHEMA_TYPE_GUIDS_2024 = {
    -2009000: "e0bc59cf-a1aa-48ae-83a2-637780af923d",   # Rebar Numbering
    -2009060: "396c2ee8-a554-4fed-bf44-c2e648dec011",   # Rebar Couplers Numbering
    -2009016: "f90085e5-ffbd-4dea-aadc-837c93df2943",   # Fabric Sheets Numbering
}

#: ViewDisplayMgr.m_useGDI / ModelGraphicsStyle.m_bUseGDI: False in every
#: decoded 2024 specimen (85/85 ViewDisplayMgr nested in the rst views,
#: 2/2 ModelGraphicsStyle).
USE_GDI_2024 = False

#: ReinforcementSettings.m_numberVaryingLengthRebarsIndividually: the 2024
#: sample default is True (rst elem 137426) -- NOT the blank default.
REINF_NUMBER_INDIVIDUALLY_2024 = True

#: RbsWireType.m_strMaxConductorSize: the 2024 sample stores the bare size
#: label ('2000' on rst elem 55171).  OUR wire types resolve their own
#: conductor-size cell's label; this is the fallback.
WIRE_MAX_SIZE_FALLBACK_2024 = "2000"

#: the pen-table format constants, re-mined for 2024 (rst elem 2): the six
#: model scale breakpoints, 16 pens per vector, perspective/annotation
#: vectors scale-independent (-1) -- IDENTICAL to the 2026/2025 constants,
#: so ``settings.pen_width_table`` ports value-unchanged.
PEN_SCALE_BREAKPOINTS_2024 = [10, 20, 50, 100, 200, 500]
PEN_COUNT_2024 = 16


# ---------------------------------------------------------------------------
# the 2024-NEW field-map hooks
# ---------------------------------------------------------------------------
#: AutoCamSettingsElem v6->5: 2024 fixed double[3] field <- 2026 inline XYZ
#: field (the XYZ decodes as [x,y,z]; value-compatible carry under rename).
AUTOCAM_RENAMES_2024 = {
    "m_homeEye": "m_homeEyeXYZ", "m_homeCenter": "m_homeCenterXYZ",
    "m_homeUp": "m_homeUpXYZ", "m_homePivot": "m_homePivotXYZ",
    "m_sceneUp": "m_sceneUpXYZ", "m_sceneFront": "m_sceneFrontXYZ",
    "m_sceneCenter": "m_sceneCenterXYZ",
}


def _autocam_hook(dst: str):
    src_name = AUTOCAM_RENAMES_2024[dst]

    def hook(s: dict, c: _AdaptContext):
        v = s.get(src_name)
        if isinstance(v, (list, tuple)) and len(v) == 3:
            return [float(x) for x in v]
        return [0.0, 0.0, 0.0]
    return hook


def _hook_duct_viscosity(src: dict, ctx: _AdaptContext):
    """2024 ``m_dAirViscosity`` (KINEMATIC, ft^2/s) from the 2026 record's
    own dynamic viscosity and density: nu = mu / rho.  Bit-exact against
    Autodesk's own 2024<->2026 migration of the rst sample (see module
    docstring)."""
    mu = src.get("m_airDynamicViscosity")
    rho = src.get("m_dAirDensity")
    if isinstance(mu, (int, float)) and isinstance(rho, (int, float)) and rho:
        return float(mu) / float(rho)
    ctx.note("RbsDuctSettingsElem.m_dAirViscosity: source lacks usable "
             "m_airDynamicViscosity / m_dAirDensity -> 0.0")
    return 0.0


def _hook_mep_network_map(src: dict, ctx: _AdaptContext):
    """2024 ``m_component2BaseElementMap`` (ElementId pairs) from 2026's
    ``m_component2BaseSegmentMap`` (NetworkSegmentId pairs).  Our tracker
    constructor and every corpus specimen carry the EMPTY map; a non-empty
    source has no lossless representation and is refused."""
    m = src.get("m_component2BaseSegmentMap")
    if m:
        raise PortabilityError(
            "MEPNetworkTracker.m_component2BaseSegmentMap is non-empty: "
            "NetworkSegmentId pairs cannot be expressed as 2024 ElementId "
            "pairs -- construct the tracker empty for a 2024 build")
    return []


def _hook_wire_max_size_2024(src: dict, ctx: _AdaptContext):
    """RbsWireType: id-of-catalog-cell -> the bare size-label string (the
    2024 corpus form, rst 55171).  port2025's hook re-stated against the
    2024-mined fallback."""
    sid = src.get("m_idMaxConductorSize", INVALID)
    if isinstance(sid, int) and sid not in (None, INVALID) and ctx.resolve_name:
        nm = ctx.resolve_name(int(sid))
        if nm:
            ctx.note(f"RbsWireType.m_strMaxConductorSize <- conductor-size cell "
                     f"{sid} name {nm!r}")
            return str(nm)
    ctx.note("RbsWireType.m_strMaxConductorSize <- fallback "
             f"{WIRE_MAX_SIZE_FALLBACK_2024!r} (max-size cell not resolvable)")
    return WIRE_MAX_SIZE_FALLBACK_2024


#: (declaring class, 2024 field) -> value hook(src_2026_obj, ctx).
#: A hook OVERRIDES both carry-over and the blank default.  The same-as-2025
#: block re-states port2025's hooks against the 2024-mined constants (values
#: verified equal); the delegated numbering hooks are port2025's own
#: functions (layout-identical nested classes, identical GUID table).
#: NOTE deliberately ABSENT vs port2025: ("GeomStep", "m_oExtraData") --
#: 2024 has no extra-data field at all; it drops by construction.
HOOKS_2024: Dict[Tuple[str, str], Callable[[dict, _AdaptContext], Any]] = {
    # -- same delta as 2025, 2024-mined values --------------------------------
    ("GeomTable", "m_maxSafeTag"): lambda s, c: GEOMTABLE_2024["m_maxSafeTag"],
    ("GeomTable", "m_lastCheckedKingsUserModificationDate"):
        lambda s, c: GEOMTABLE_2024["m_lastCheckedKingsUserModificationDate"],
    ("RbsWireSettingsElem", "m_dMaxVoltageBranchSizing"):
        lambda s, c: WIRE_SETTINGS_2024["m_dMaxVoltageBranchSizing"],
    ("RbsWireSettingsElem", "m_dMaxVoltageFeederSizing"):
        lambda s, c: WIRE_SETTINGS_2024["m_dMaxVoltageFeederSizing"],
    ("RbsWireSettingsElem", "m_dAmbientTemperature"):
        lambda s, c: WIRE_SETTINGS_2024["m_dAmbientTemperature"],
    ("RbsWireType", "m_strMaxConductorSize"): _hook_wire_max_size_2024,
    ("BrowserOrganization", "m_sortParamId"): _hook_sort_param_id,
    ("ModelGraphicsStyle", "m_bUseGDI"): lambda s, c: USE_GDI_2024,
    ("ViewDisplayMgr", "m_useGDI"): lambda s, c: USE_GDI_2024,
    ("ReinforcementSettings", "m_numberVaryingLengthRebarsIndividually"):
        lambda s, c: REINF_NUMBER_INDIVIDUALLY_2024,
    ("NumberingSchema", "m_oPartitionDescriptionCreator"): _hook_numbering_partition_creator,
    ("NumberingSchema", "m_minimumNumberOfDigits"): _hook_numbering_min_digits,
    ("NumberingSchema", "schemaTypeGuid"): _hook_numbering_type_guid,
    ("NumberingSchema", "m_isMatchingEnabled"): _hook_numbering_matching,
    ("BrowserOrganizationTracking", "m_currentBrOrgViews"):
        lambda s, c: _browser_tracking_tree(s, 0),
    ("BrowserOrganizationTracking", "m_currentBrOrgSheets"):
        lambda s, c: _browser_tracking_tree(s, 1),
    ("BrowserOrganizationTracking", "m_currentBrOrgSchedules"):
        lambda s, c: _browser_tracking_tree(s, 3),
    # -- 2024-new deltas ------------------------------------------------------
    ("RbsDuctSettingsElem", "m_dAirViscosity"): _hook_duct_viscosity,
    ("MEPNetworkTracker", "m_component2BaseElementMap"): _hook_mep_network_map,
}
for _dst in AUTOCAM_RENAMES_2024:
    HOOKS_2024[("AutoCamSettingsElem", _dst)] = _autocam_hook(_dst)


# ---------------------------------------------------------------------------
# the generic schema-pair adapter, bound to the 2024 pin (port2025's walk is
# hardwired to its 2025 singleton, so the walk lives here; the shape is
# port2025's, verbatim method)
# ---------------------------------------------------------------------------
def adapt(class_name: str, obj: dict, *,
          resolve_name: Optional[Callable[[int], Optional[str]]] = None,
          _ctx: Optional[_AdaptContext] = None) -> dict:
    """A Revit-2024 object dict for ``class_name`` from a 2026-built one.

    Walks the 2024 class chain; carries same-name fields (recursively
    adapting nested class values), applies :data:`HOOKS_2024`, blanks the
    rest.  The source is never mutated.  Raises :class:`Missing2024` when
    the class (or a pointed-to class inside it) has no 2024 twin.
    """
    ctx = _ctx or _AdaptContext(resolve_name=resolve_name)
    _dec24, _enc, schema24 = _S24()
    cd = schema24.by_name.get(class_name)
    if cd is None:
        raise Missing2024(f"class {class_name!r} is not in the Revit-2024 archive "
                          "class map")
    return _adapt_class(class_name, cd.type_id, obj or {}, ctx)


def _adapt_class(class_name: str, type_id: int, src: dict, ctx: _AdaptContext) -> dict:
    from ..objects import field_key
    dec24, _enc, _s = _S24()
    out: dict = {}
    for cd in dec24.chain(type_id):
        for f in cd.fields:
            key = field_key(cd, f, out)
            hook = HOOKS_2024.get((cd.name, f.name))
            if hook is not None:
                out[key] = hook(src, ctx)
                continue
            if key in src:
                out[key] = _adapt_field(f, src[key], ctx, f"{class_name}.{key}")
            elif f.name in src:                       # shadow-key fallback
                out[key] = _adapt_field(f, src[f.name], ctx, f"{class_name}.{f.name}")
            else:
                out[key] = _blank_field_for(dec24, f, 0)
    return out


def _adapt_field(f, v: Any, ctx: _AdaptContext, path: str):
    kind, flags = f.kind, f.flags
    shape = flags >> 4
    dec24, _enc, schema24 = _S24()
    if kind == 0x08:                                   # AString (scalar or list)
        if shape in (1, 5):
            return [str(x) for x in (v or [])]
        return "" if v is None else str(v)
    if kind == 0x0D:                                   # inline array wrapper
        if not isinstance(v, list):
            ctx.note(f"{path}: expected list for array field, got "
                     f"{type(v).__name__} -> blank []")
            return _blank_field_for(dec24, f, 0)
        return [_adapt_field(f.element, x, ctx, f"{path}[{i}]")
                for i, x in enumerate(v)]
    if shape == 5:                                     # growable container
        if not isinstance(v, list):
            ctx.note(f"{path}: expected container, got {type(v).__name__} -> []")
            return []
        return [_adapt_scalar(f, kind, flags & 0x0F, x, ctx, f"{path}[{i}]")
                for i, x in enumerate(v)]
    if shape == 1:                                     # fixed array
        vals = v if isinstance(v, list) else []
        n = f.count or 0
        out = [_adapt_scalar(f, kind, flags & 0x0F, x, ctx, f"{path}[{i}]")
               for i, x in enumerate(vals[:n])]
        while len(out) < n:
            out.append(_blank_scalar_for(dec24, f, kind, flags & 0x0F, 0))
        return out
    return _adapt_scalar(f, kind, flags & 0x0F, v, ctx, path)


def _adapt_scalar(f, kind: int, indir: int, v: Any, ctx: _AdaptContext, path: str):
    from ..objects import _PRIM_FMT
    dec24, _enc, schema24 = _S24()
    if kind == 0x01:
        return bool(v)
    if kind in _PRIM_FMT:
        return v if isinstance(v, (int, float)) else (0.0 if kind in (0x06, 0x07) else 0)
    if kind == 0x08:
        return "" if v is None else str(v)
    if kind == 0x09:
        return str(v) if v else NULL_GUID
    if kind == 0x0A:                                   # classref
        name = v.get("classref") if isinstance(v, dict) else v
        if name and name not in schema24.by_name:
            raise Missing2024(f"{path}: classref {name!r} has no 2024 twin")
        return {"classref": name or "Element"}
    if kind == 0x0E:
        if indir == 0:                                 # inline value class
            tid = f.type_id
            if tid in (dec24.id_ElementId, dec24.id_Identifier):
                return int(v) if isinstance(v, (int, float)) else INVALID
            if tid == dec24.id_XYZ:
                return list(v) if isinstance(v, list) else [0.0, 0.0, 0.0]
            if tid == dec24.id_UV:
                return list(v) if isinstance(v, list) else [0.0, 0.0]
            if tid == dec24.id_GUIDvalue:
                return str(v) if v else NULL_GUID
            cname = dec24.class_name(tid)
            if not isinstance(v, dict):
                ctx.note(f"{path}: inline {cname} source is {type(v).__name__} "
                         "-> 2024 blank")
                return _blank_class_for(dec24, schema24.by_name[cname].type_id, 1)
            return _adapt_class(cname, tid, v, ctx)
        if indir == 3:                                 # weak pointer
            if isinstance(v, dict) and "weakref" in v:
                return {"weakref": int(v["weakref"])}
            return {"weakref": int(v or 0)}
        # owned / poly pointer
        if v is None:
            return None
        if isinstance(v, dict) and "backref_pid" in v:
            return dict(v)
        if isinstance(v, dict) and "ptr_class" in v:
            pcls = v["ptr_class"]
            cd = schema24.by_name.get(pcls)
            if cd is None:
                raise Missing2024(f"{path}: pointed-to class {pcls!r} has no 2024 twin")
            body = v.get("value")
            return {"ptr_class": pcls, "pid": v.get("pid", -1),
                    "value": (None if body is None
                              else _adapt_class(pcls, cd.type_id, body, ctx))}
        ctx.note(f"{path}: unrecognised pointer token {type(v).__name__} -> null")
        return None
    raise PortabilityError(f"{path}: unsupported field kind {kind:#x}")


# ---------------------------------------------------------------------------
# record-level adaptation (what a Revit-2024 build path consumes)
# ---------------------------------------------------------------------------
@dataclasses.dataclass
class PortedRecord:
    """A 2026 TypeRecord-shaped record re-expressed for Revit 2024: 2024
    class ids, 2024-shaped seq-101/102/103 bodies."""
    elem_id: int
    kind: str
    class_name: str
    class_id: int                     # 2024 ordinal
    obj: dict                         # seq-102 body (2024 shape)
    header: dict                      # seq-101 body (2024 shape)
    rep: Optional[dict]               # seq-103 GElement body or None (dummy)
    rep_class_id: int                 # 2024 ordinal (GElement / SerializedDummy)
    rep_class_name: str
    refs: dict = dataclasses.field(default_factory=dict)
    notes: List[str] = dataclasses.field(default_factory=list)

    def records(self) -> list:
        return [(101, class_id_2024("ElementHeader"), self.header),
                (102, self.class_id, self.obj),
                (103, self.rep_class_id, self.rep if self.rep is not None else {})]


def adapt_record(rec, *, resolve_name: Optional[Callable[[int], Optional[str]]] = None
                 ) -> PortedRecord:
    """Adapt one 2026 constructor record into a :class:`PortedRecord`.
    Raises :class:`Missing2024` for :data:`MISSING_2024_CONSTRUCTED` classes
    (callers emit nothing for those on a 2024 build)."""
    cname = rec.class_name
    if not exists_2024(cname):
        raise Missing2024(f"{cname} (record {rec.elem_id}) has no Revit-2024 "
                          "twin -- emit nothing on a 2024 build")
    ctx = _AdaptContext(resolve_name=resolve_name)
    obj24 = _adapt_class(cname, _S24()[2].by_name[cname].type_id,
                         copy.deepcopy(rec.obj or {}), ctx)
    hdr24 = adapt("ElementHeader", copy.deepcopy(rec.header or {}),
                  resolve_name=resolve_name, _ctx=ctx)
    rep = getattr(rec, "rep", None)
    if rep is not None:
        rep24 = adapt("GElement", copy.deepcopy(rep), resolve_name=resolve_name,
                      _ctx=ctx)
        rep_cid, rep_cn = class_id_2024("GElement"), "GElement"
    else:
        rep24, rep_cid, rep_cn = None, class_id_2024("SerializedDummy"), "SerializedDummy"
    return PortedRecord(
        elem_id=int(rec.elem_id), kind=str(getattr(rec, "kind", "")),
        class_name=cname, class_id=class_id_2024(cname), obj=obj24,
        header=hdr24, rep=rep24, rep_class_id=rep_cid, rep_class_name=rep_cn,
        refs=dict(getattr(rec, "refs", {}) or {}),
        notes=list(getattr(rec, "notes", []) or []) + ctx.notes)


def verify_roundtrip_2024(class_id: int, obj: dict) -> dict:
    """Encode ``obj`` under the 2024 schema, decode it back, re-encode:
    the port2024 round-trip gate (clean + byte-exact required)."""
    dec, enc, _s = _S24()
    body = enc.encode_object(class_id, obj or {})
    got = dec.decode_record(class_id, body)
    body2 = enc.encode_object(class_id, got.value) if got.clean else b""
    return {"class": dec.class_name(class_id), "bytes": len(body),
            "clean": bool(got.clean), "byte_exact": body == body2,
            "errors": list(got.errors or [])[:3],
            "ok": bool(got.clean) and body == body2}


def verify_ported(pr: PortedRecord) -> dict:
    """Round-trip every seq body of a :class:`PortedRecord` under 2024."""
    rep = {}
    for seq, cid, body in pr.records():
        rep[seq] = verify_roundtrip_2024(cid, body or {})
    rep["ok"] = all(rep[s]["ok"] for s in (101, 102, 103))
    return rep


# ---------------------------------------------------------------------------
# the CONFIRMED portability table (three-way: 2026 vs 2024, annotated vs 2025)
# ---------------------------------------------------------------------------
def harvest_constructed_classes() -> Dict[str, List[str]]:
    """{class name: [where]} harvested from the genesis sources -- port2025's
    harvest rule, with BOTH portability layers excluded (they carry class
    names as field-map keys, not constructors)."""
    _d, _e, s26 = _S26()
    out: Dict[str, Set[str]] = collections.defaultdict(set)
    for fn in sorted(os.listdir(GENESIS_DIR)):
        if not fn.endswith(".py") or _is_port_layer(fn):
            continue
        src = open(os.path.join(GENESIS_DIR, fn)).read()
        tree = ast.parse(src)
        doc_positions: Set[int] = set()
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                doc_positions.add(id(body[0].value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and id(node) not in doc_positions:
                v = node.value
                if v in s26.by_name and v.strip() == v and " " not in v:
                    out[v].add(f"{fn}:{node.lineno}")
    return {k: sorted(v) for k, v in sorted(out.items())}


def _field_sig(f, schema):
    tn = None
    if f.type_id is not None:
        c = schema.by_id.get(f.type_id)
        tn = c.name if c else f.type_name
    el = _field_sig(f.element, schema) if f.element is not None else None
    return (f.name, f.kind, f.flags, f.count, tn, f.extra, el)


def diff_class(name: str) -> dict:
    """One class's CONFIRMED 2026-vs-2024 verdict: IDENTICAL / VERSION-ONLY /
    LAYOUT-DELTA (with exact field deltas) / MISSING-2024."""
    dec26, _e26, s26 = _S26()
    dec24, _e24, s24 = _S24()
    a = s26.by_name.get(name)
    if a is None:
        return {"class": name, "verdict": "NOT-IN-2026"}
    b = s24.by_name.get(name)
    if b is None:
        return {"class": name, "verdict": "MISSING-2024", "version_2026": a.version}
    ca, cb = dec26.chain(a.type_id), dec24.chain(b.type_id)
    flat26 = [(c.name, _field_sig(f, s26)) for c in ca for f in c.fields]
    flat24 = [(c.name, _field_sig(f, s24)) for c in cb for f in c.fields]
    chain26, chain24 = [c.name for c in ca], [c.name for c in cb]
    out: Dict[str, Any] = {"class": name, "version_2026": a.version,
                           "version_2024": b.version, "chain": chain26}
    if flat26 == flat24 and chain26 == chain24:
        out["verdict"] = ("IDENTICAL" if a.version == b.version else "VERSION-ONLY")
        return out
    out["verdict"] = "LAYOUT-DELTA"
    if chain26 != chain24:
        out["chain_2024"] = chain24
    deltas = []
    for c26 in ca:
        c24 = next((c for c in cb if c.name == c26.name), None)
        if c24 is None:
            deltas.append({"base": c26.name, "delta": "base class missing in 2024"})
            continue
        f26 = [_field_sig(f, s26) for f in c26.fields]
        f24 = [_field_sig(f, s24) for f in c24.fields]
        if f26 == f24 and c26.version == c24.version:
            continue
        n26, n24 = {t[0] for t in f26}, {t[0] for t in f24}
        d = {"base": c26.name, "version": f"{c26.version}->{c24.version}",
             "only_2026": [t[0] for t in f26 if t[0] not in n24],
             "only_2024": [t[0] for t in f24 if t[0] not in n26],
             "changed": [t[0] for t in f26
                         if t[0] in n24 and next(u for u in f24 if u[0] == t[0]) != t]}
        shared26 = [t[0] for t in f26 if t[0] in n24]
        shared24 = [t[0] for t in f24 if t[0] in n26]
        if shared26 != shared24:
            d["order_differs"] = True
        deltas.append(d)
    out["deltas"] = deltas
    out["hooked"] = sorted({f for (c, f) in HOOKS_2024
                            if c in chain26 or c == name})
    return out


def _norm_deltas(row: dict, year_label: str) -> tuple:
    """Delta shape normalised for cross-release comparison (only_20XX keyed
    positionally so 2024 and 2025 rows compare)."""
    ds = []
    for d in row.get("deltas", []):
        if "delta" in d:
            ds.append((d["base"], d["delta"].replace(year_label, "X")))
        else:
            ds.append((d["base"], tuple(d.get("only_2026") or []),
                       tuple(d.get(f"only_{year_label}") or []),
                       tuple(d.get("changed") or []),
                       bool(d.get("order_differs"))))
    return tuple(ds)


def vs_2025(name: str, row24: Optional[dict] = None) -> str:
    """How this class's 2024 delta relates to its 2025 delta (the three-way
    annotation): 'same-as-2025' / 'differs-from-2025' / verdict labels."""
    from . import port2025 as P25
    r24 = row24 or diff_class(name)
    r25 = P25.diff_class(name)
    v24, v25 = r24["verdict"], r25["verdict"]
    if v24 == v25 == "LAYOUT-DELTA":
        return ("same-as-2025" if _norm_deltas(r24, "2024") == _norm_deltas(r25, "2025")
                else "differs-from-2025")
    if v24 == v25:
        return f"both-{v24}"
    return f"2025={v25}"


def portability_table(*, write: bool = True) -> dict:
    """The CONFIRMED constructor-portability table 2026 -> 2024, three-way
    annotated against port2025's 2026 -> 2025 table.  Frozen to
    :data:`PORTABILITY_JSON`."""
    dec26, _e, s26 = _S26()
    harvest = harvest_constructed_classes()
    names: Set[str] = set(harvest)
    for n in list(names):
        cd = s26.by_name.get(n)
        if cd:
            names.update(c.name for c in dec26.chain(cd.type_id))
    rows = {}
    for n in sorted(names):
        r = diff_class(n)
        if r["verdict"] in ("LAYOUT-DELTA", "MISSING-2024", "VERSION-ONLY"):
            r["vs_2025"] = vs_2025(n, r)
        rows[n] = r
    counts = collections.Counter(r["verdict"] for r in rows.values())
    table = {
        "generator": "rvt.genesis.port2024.portability_table",
        "method": "port2025's method re-run for 2024: own-field signatures by "
                  "type NAME + flattened parent-first chain + class versions, "
                  "2026 pin vs rvt.versions.schema_2024 pin; every LAYOUT-DELTA "
                  "/ MISSING / VERSION-ONLY row three-way annotated vs the "
                  "2026->2025 table (vs_2025)",
        "universe": {"harvested": len(harvest), "with_chain_expansion": len(names)},
        "counts": dict(counts),
        "non_monotonic_findings": {
            "deltas_that_differ_from_2025": sorted(
                n for n, r in rows.items()
                if r.get("vs_2025") == "differs-from-2025"),
            "delta_only_in_2024": sorted(
                n for n, r in rows.items()
                if r["verdict"] == "LAYOUT-DELTA"
                and (r.get("vs_2025") or "").startswith("2025=")),
            "missing_2024_but_present_2025": sorted(
                n for n, r in rows.items()
                if r["verdict"] == "MISSING-2024"
                and r.get("vs_2025") not in ("both-MISSING-2024",)
                and "MISSING" not in (r.get("vs_2025") or "")),
            "geomstep_note": "2024 has NO extra-data field (2025 renamed "
                             "m_oExtraDatas->m_oExtraData; 2024 predates it) -- "
                             "the port2025 rename hook is deliberately absent",
            "dbviewdrafting_note": "2024 additionally lacks m_sheetCollectionId "
                                   "and gains m_scheduleInstanceIds (corpus "
                                   "blank-[] on fresh views, 8/8 rst)",
            "constructed_missing_2024": list(MISSING_2024_CONSTRUCTED),
        },
        "mined_constants": {
            "WIRE_SETTINGS_2024": WIRE_SETTINGS_2024,
            "GEOMTABLE_2024": GEOMTABLE_2024,
            "NUMBERING_SCHEMA_TYPE_GUIDS_2024": NUMBERING_SCHEMA_TYPE_GUIDS_2024,
            "USE_GDI_2024": USE_GDI_2024,
            "REINF_NUMBER_INDIVIDUALLY_2024": REINF_NUMBER_INDIVIDUALLY_2024,
            "WIRE_MAX_SIZE_FALLBACK_2024": WIRE_MAX_SIZE_FALLBACK_2024,
            "PEN_SCALE_BREAKPOINTS_2024": PEN_SCALE_BREAKPOINTS_2024,
            "PEN_COUNT_2024": PEN_COUNT_2024,
            "DUCT_VISCOSITY_RULE": "m_dAirViscosity = m_airDynamicViscosity / "
                                   "m_dAirDensity (kinematic ft^2/s; bit-exact "
                                   "vs rst 102127 across releases)",
        },
        "classes": rows,
        "harvest_provenance": harvest,
    }
    if write:
        os.makedirs(OUT_DIR, exist_ok=True)
        with open(PORTABILITY_JSON, "w") as fh:
            json.dump(table, fh, indent=1)
    return table


# ---------------------------------------------------------------------------
# 2024 corpus miners (the same derivations as rvt.genesis.catalog /
# port2025, run over the quarantined samples/2024 corpus)
# ---------------------------------------------------------------------------
def _sample_documents_2024(names: Sequence[str] = ("rstbasicsampleproject",
                                                   "rmebasicsampleproject",
                                                   "racbasicsampleproject")):
    from .. import versions
    from ..mutate import Document
    for n in names:
        p = os.path.join(SAMPLES_2024, f"{n}.rvt")
        if not os.path.exists(p):
            continue
        with versions.reading(p):
            yield n, Document.from_file(p)


def derive_builtin_category_enum_2024(verbose: bool = True) -> dict:
    """The Revit-2024 graphic-category ENUM (catalog's derivation over the
    2024 samples): every built-in category id carrying a host object-style
    row + its cuttability, asserted identical across the samples."""
    per: Dict[str, Dict[int, set]] = {}
    for s, doc in _sample_documents_2024():
        rows: Dict[int, set] = collections.defaultdict(set)
        for gid in doc.ids_of_class("GStyleElem", host_only=True):
            v = doc.value(gid) or {}
            if v.get("m_famId", -1) != -1:
                continue
            cid = v.get("m_categoryId")
            if isinstance(cid, int) and cid < 0:
                rows[cid].add(int(v.get("m_gstyleType", 1)))
        per[s] = dict(rows)
        if verbose:
            print(f"   [enum-2024] {s}: {len(rows)} built-in categories, "
                  f"{sum(1 for t in rows.values() if 2 in t)} cuttable")
    base = None
    for s, rows in per.items():
        norm = {k: tuple(sorted(v)) for k, v in rows.items()}
        if base is None:
            base = norm
        elif norm != base:
            diff = set(norm) ^ set(base)
            raise RuntimeError(f"2024 graphic-category enum differs in {s}: "
                               f"{len(diff)} ids differ")
    cats = [{"id": int(cid), "cut": 2 in ts} for cid, ts in sorted((base or {}).items())]
    return {"generator": "rvt.genesis.port2024.derive_builtin_category_enum_2024",
            "derived_from": sorted(per), "release": 2024,
            "count": len(cats), "cuttable": sum(1 for c in cats if c["cut"]),
            "categories": cats}


def derive_builtin_style_profile_2024(verbose: bool = True) -> dict:
    """The per-(category, style-type) STRUCTURAL profile of the 2024
    object-styles table (catalog.derive_builtin_style_profile's rules over
    the 2024 samples).  Structure only."""
    from .catalog import AB_CELLLIST_BIT, BUILTIN_SOLID_PATTERN, _modal
    per: Dict[Tuple[int, int], dict] = collections.defaultdict(lambda: {
        "ab": collections.Counter(), "vis": collections.Counter(),
        "pat_val": collections.Counter(), "pat_kind": collections.Counter(),
        "mat_val": collections.Counter(), "mat_kind": collections.Counter(),
        "scr": collections.Counter(), "pen": collections.Counter(), "files": set()})
    n_rows = 0
    for s, doc in _sample_documents_2024():
        seen = 0
        for gid in doc.ids_of_class("GStyleElem", host_only=True):
            v = doc.value(gid) or {}
            if v.get("m_famId", -1) != -1 or v.get("m_ownerId", -1) != -1:
                continue
            cid = v.get("m_categoryId")
            if not (isinstance(cid, int) and cid < 0):
                continue
            gt = int(v.get("m_gstyleType", 1))
            p = per[(int(cid), gt)]
            p["files"].add(s)
            gs = ((v.get("m_pGStyle") or {}).get("value") or {})
            pat, mat, pen = (gs.get("m_linePatternId"), gs.get("m_materialElemId"),
                             gs.get("m_penNumber"))
            p["pat_kind"]["null" if pat == INVALID else
                          ("builtin" if isinstance(pat, int) and pat < 0 else "elem")] += 1
            if isinstance(pat, int) and pat < 0 and pat != INVALID:
                p["pat_val"][int(pat)] += 1
            p["mat_kind"]["null" if mat == INVALID else
                          ("builtin" if isinstance(mat, int) and mat < 0 else "elem")] += 1
            if isinstance(mat, int) and mat < 0 and mat != INVALID:
                p["mat_val"][int(mat)] += 1
            p["scr"][bool(gs.get("m_isScreenSized"))] += 1
            if isinstance(pen, int):
                p["pen"][int(pen)] += 1
            h = doc.decode(gid, 101)
            if h and getattr(h, "clean", False) and h.value:
                p["ab"][int(h.value.get("m_abFlags4Bytes") or 0)] += 1
                p["vis"][int(((h.value.get("m_viewRules") or {})
                              .get("m_nVisibleViewFlags") or 0))] += 1
            seen += 1
        n_rows += seen
        if verbose:
            print(f"   [profile-2024] {s}: {seen} built-in object-style rows")
    keys = {}
    for (cid, gt), p in sorted(per.items()):
        clean = collections.Counter({a: c for a, c in p["ab"].items()
                                     if not (a & AB_CELLLIST_BIT)})
        ab = _modal(clean)
        if ab is None:
            ab = (_modal(p["ab"]) or 0) & ~AB_CELLLIST_BIT
        vis = _modal(p["vis"])
        kinds = set(p["pat_kind"])
        if kinds == {"null"}:
            pattern = "null"
        elif kinds == {"elem"}:
            pattern = "elem"
        elif "builtin" in kinds:
            if BUILTIN_SOLID_PATTERN in p["pat_val"]:
                pattern = "solid"
            elif kinds == {"builtin"}:
                pattern = f"builtin:{_modal(p['pat_val'])}"
            else:
                pattern = "solid"
        else:
            pattern = "nullwire"
        mkinds = set(p["mat_kind"])
        if mkinds == {"null"}:
            material = "null"
        elif mkinds == {"elem"}:
            material = "elem"
        elif mkinds == {"builtin"}:
            material = f"builtin:{_modal(p['mat_val'])}"
        else:
            material = "nullwire"
        pens = set(p["pen"])
        keys[f"{cid}:{gt}"] = {
            "cat": cid, "type": gt, "files": len(p["files"]),
            "ab": int(ab), "ab_set": sorted(int(x) for x in p["ab"]),
            "vis": int(vis) if vis is not None else -32768,
            "pattern": pattern, "material": material,
            "screen_sized": (set(p["scr"]) == {True}),
            "pen": ("null0" if pens == {0} else
                    ("nullneg1" if pens == {-1} else "ours")),
        }
    return {"generator": "rvt.genesis.port2024.derive_builtin_style_profile_2024",
            "release": 2024, "rows_analysed": n_rows, "count": len(keys),
            "keys": keys}


def derive_pen_table_2024(verbose: bool = True) -> dict:
    """The 2024 project pen-table FORMAT constants, mined from every basic
    sample's project table (m_famId -1): the model scale-breakpoint set,
    pens per vector, perspective/annotation scale sentinels."""
    tables = []
    for s, doc in _sample_documents_2024():
        for gid in doc.ids_of_class("PenWidthTableElem", host_only=True):
            v = doc.value(gid) or {}
            if v.get("m_famId", -1) != -1:
                continue
            t = ((v.get("m_pPenWidthTable") or {}).get("value") or {})
            model = t.get("m_modelPenInfo") or []
            widths = [w for x in model for w in (x.get("m_pens") or [])]
            widths += list((t.get("m_perspectiveModelPenInfo") or {}).get("m_pens") or [])
            widths += list((t.get("m_draftPenInfo") or {}).get("m_pens") or [])
            row = {
                "file": s, "elem_id": int(gid),
                "scales": sorted(int(x.get("m_invertedScale")) for x in model),
                "pens_per_vector": sorted({len(x.get("m_pens") or []) for x in model}),
                "perspective_scale": (t.get("m_perspectiveModelPenInfo") or {}).get("m_invertedScale"),
                "draft_scale": (t.get("m_draftPenInfo") or {}).get("m_invertedScale"),
                "width_ft_range": [min(widths), max(widths)] if widths else None,
            }
            tables.append(row)
            if verbose:
                print(f"   [pen-2024] {s} id {gid}: scales={row['scales']} "
                      f"pens={row['pens_per_vector']} persp={row['perspective_scale']}")
    scale_sets = {tuple(r["scales"]) for r in tables}
    pen_counts = {tuple(r["pens_per_vector"]) for r in tables}
    if scale_sets != {tuple(PEN_SCALE_BREAKPOINTS_2024)}:
        raise RuntimeError(f"2024 pen-table scale keys differ from the pinned "
                           f"constant: {scale_sets}")
    if pen_counts != {(PEN_COUNT_2024,)}:
        raise RuntimeError(f"2024 pen count differs from {PEN_COUNT_2024}: {pen_counts}")
    return {"generator": "rvt.genesis.port2024.derive_pen_table_2024",
            "release": 2024, "project_tables": tables,
            "scale_breakpoints": PEN_SCALE_BREAKPOINTS_2024,
            "pens_per_vector": PEN_COUNT_2024,
            "perspective_draft_scale": -1,
            "matches_2026_constant": True}


def derive_palette_invariants_2024(verbose: bool = True) -> dict:
    """The 2024 PropertySetElement (palette) serialisation invariants --
    residue_b2's corpus laws, re-measured over the 2024 samples: param-id
    ASCENDING order per container, built-in ids NEGATIVE, m_pElementIdParams
    PRESENT-EMPTY, the property-set-type census."""
    asc = collections.Counter()
    eidset = collections.Counter()
    pstype = collections.Counter()
    neg = collections.Counter()
    per_file = {}
    n_sets = 0
    for s, doc in _sample_documents_2024():
        seen = 0
        for e in doc.ids_of_class("PropertySetElement", host_only=True):
            v = doc.value(e) or {}
            pstype[int(v.get("m_propertySetType", -1))] += 1
            ps = ((v.get("m_oParamSet") or {}).get("value") or {})
            for key in ("m_pDoubleParams", "m_pIntParams", "m_pAStringParams"):
                arr = ((((ps.get(key) or {}).get("value") or {}).get("m_paramSet")) or [])
                ids = [x.get("m_paramId") for x in arr]
                asc[ids == sorted(ids)] += 1
                for i in ids:
                    neg[bool(isinstance(i, int) and i < 0)] += 1
            eid = ps.get("m_pElementIdParams")
            present_empty = (isinstance(eid, dict) and eid.get("value") is not None
                             and not (eid["value"].get("m_paramSet") or []))
            eidset["present_empty" if present_empty
                   else ("null" if eid is None else "nonempty")] += 1
            n_sets += 1
            seen += 1
        per_file[s] = seen
        if verbose:
            print(f"   [palette-2024] {s}: {seen} PropertySetElements")
    out = {"generator": "rvt.genesis.port2024.derive_palette_invariants_2024",
           "release": 2024, "property_sets": n_sets, "per_file": per_file,
           "type_census": {str(k): v for k, v in sorted(pstype.items())},
           "param_containers_ascending": {str(k): v for k, v in asc.items()},
           "param_ids_negative": {str(k): v for k, v in neg.items()},
           "element_id_set": dict(eidset),
           "laws_hold": (set(asc) <= {True} and set(neg) <= {True}
                         and set(eidset) <= {"present_empty"})}
    if not out["laws_hold"]:
        raise RuntimeError(f"2024 palette invariants VIOLATED: {out}")
    return out


def load_2024_catalog_constants(*, derive_if_missing: bool = True) -> Tuple[dict, dict]:
    """(enum, profile) for a 2024 catalog rung -- frozen JSON, derived on
    first use."""
    out = []
    for path, derive in ((ENUM_2024_JSON, derive_builtin_category_enum_2024),
                         (PROFILE_2024_JSON, derive_builtin_style_profile_2024)):
        if os.path.exists(path):
            with open(path) as fh:
                out.append(json.load(fh))
            continue
        if not derive_if_missing:
            raise FileNotFoundError(path)
        data = derive()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=1)
        out.append(data)
    return out[0], out[1]


def mine_all(verbose: bool = True) -> dict:
    """Freeze EVERY 2024 miner artifact under experiments/genesis2024/miners."""
    os.makedirs(OUT_DIR, exist_ok=True)
    enum, prof = load_2024_catalog_constants()
    results = {"enum": enum, "profile": prof}
    for path, derive in ((PEN_2024_JSON, derive_pen_table_2024),
                         (PALETTE_2024_JSON, derive_palette_invariants_2024)):
        if os.path.exists(path):
            with open(path) as fh:
                results[os.path.basename(path)] = json.load(fh)
            continue
        data = derive(verbose)
        with open(path, "w") as fh:
            json.dump(data, fh, indent=1)
        results[os.path.basename(path)] = data
    return results


# ---------------------------------------------------------------------------
# specimen validation (byte-level, where the 2026 method verified byte-level)
# ---------------------------------------------------------------------------
def verify_specimen_byte_level(verbose: bool = True) -> dict:
    """The byte-level specimen gate against the 2024 rst sample:

    1. OUR adapted ``auto_cam_settings`` seq-102 body BYTE-EXACT vs specimen
       102842 (the 2026 constructor's own byte-exact claim, re-proven on
       2024 through the rename hooks).
    2. OUR adapted empty ``MEPNetworkTracker`` BYTE-EXACT vs specimen
       1468014 (EMPTY_TRACKERS' byte-exact claim, through the map hook).
    3. OUR ``pen_width_table`` LAYOUT byte-exact vs specimen 2 when the
       specimen's own vectors are re-fed (widths are values, not format).
    4. Specimen re-encode round-trip (decode -> encode byte-exact under the
       2024 codec) for one host specimen of EVERY class the constructor
       battery ports -- the 2024 encode stack is proven on real bodies.
    """
    from .. import versions
    from ..mutate import Document
    if not os.path.exists(RST_2024):
        return {"skipped": "quarantined 2024 samples not present"}
    dec, enc, s24 = _S24()
    with versions.reading(RST_2024):
        doc = Document.from_file(RST_2024)
    from . import settings as st
    rep: Dict[str, Any] = {}

    def compare(name, elem_id, rec):
        r = doc.record(elem_id, 102)
        pr = adapt_record(rec)
        body = enc.encode_object(pr.class_id, pr.obj)
        ok = (r is not None and body == r.payload)
        rep[name] = {"elem_id": elem_id, "byte_exact": ok,
                     "ours": len(body), "specimen": len(r.payload) if r else None}
        if verbose:
            print(f"   [specimen] {name:<24} vs {elem_id}: byte_exact={ok} "
                  f"({len(body)} B)")
        return ok

    ok = True
    # 1. auto-cam: fresh home state is value-identical to the specimen
    ok &= compare("AutoCamSettingsElem", 102842, st.auto_cam_settings(elem_id=102842))
    # 2. the empty MEP network tracker
    ok &= compare("MEPNetworkTracker", 1468014,
                  st.tracker("MEPNetworkTracker", elem_id=1468014))
    # 3. pen table layout with the specimen's own vectors re-fed
    sp = doc.value(2) or {}
    t = ((sp.get("m_pPenWidthTable") or {}).get("value") or {})
    model_ft = {int(x["m_invertedScale"]): list(x["m_pens"])
                for x in (t.get("m_modelPenInfo") or [])}
    persp_ft = list((t.get("m_perspectiveModelPenInfo") or {}).get("m_pens") or [])
    draft_ft = list((t.get("m_draftPenInfo") or {}).get("m_pens") or [])
    ok &= compare("PenWidthTableElem", 2,
                  st.pen_width_table(elem_id=2, model_pens_ft=model_ft,
                                     perspective_pens_ft=persp_ft,
                                     annotation_pens_ft=draft_ft))
    # 4. specimen re-encode round-trip per ported constructor class
    classes = ["BasicWallType", "FloorAttributes", "MaterialElem", "LinePatternElem",
               "FillPatternElem", "RbsWireType", "RbsWireSettingsElem",
               "RbsWireSizesElem", "NumberingSchema", "BrowserOrganization",
               "StructSettingsElem", "KeynoteTable", "ReinforcementSettings",
               "PenWidthTableElem", "AutoCamSettingsElem", "RbsDuctSettingsElem",
               "MEPNetworkTracker", "RbsDistributionSysType", "GStyleElem",
               "PropertySetElement", "DBViewDrafting"]
    rt: Dict[str, Any] = {}
    for cls in classes:
        ids = doc.ids_of_class(cls, host_only=True)
        if not ids:
            rt[cls] = "no-specimen"
            continue
        e = ids[0]
        r = doc.record(e, 102)
        got = dec.decode_record(r.class_id, r.payload)
        rt[cls] = {"elem_id": e, "clean": bool(got.clean),
                   "byte_exact": (bool(got.clean)
                                  and enc.encode_object(r.class_id, got.value) == r.payload)}
        ok &= (rt[cls]["clean"] and rt[cls]["byte_exact"])
        if verbose:
            print(f"   [roundtrip] {cls:<24} specimen {e}: clean={rt[cls]['clean']} "
                  f"byte_exact={rt[cls]['byte_exact']}")
    rep["specimen_roundtrips"] = rt
    rep["ok"] = bool(ok)
    return rep


# ---------------------------------------------------------------------------
# self-test battery: adapt + 2024 round-trip over representative constructors
# ---------------------------------------------------------------------------
def selftest(verbose: bool = True) -> dict:
    """Build a battery of 2026 constructor records, adapt each to 2024, and
    round-trip every body under the 2024 schema; then run the specimen gate."""
    from . import settings as st
    from . import types as T
    from .residue_b import BUILTIN_NUMBERING_SCHEMES, builtin_numbering_schema
    ids = T.IdSource(9_000_000)
    battery: List[Any] = [
        T.new_wall_type("P24 Wall", [("structure", 200, INVALID)], ids=ids),
        T.new_material("P24 Concrete", (120, 120, 120), ids=ids),
        T.new_line_pattern("P24 Dash", [("dash", 3.175), ("space", 1.5875)], ids=ids),
        T.new_fill_pattern("P24 Solid", [], ids=ids),
        T.new_floor_type("P24 Floor", [("structure", 150, INVALID)], ids=ids),
        T.new_wire_type("P24 THWN", ids=ids),
        T.new_distribution_system("P24 480/277", ids=ids),
        builtin_numbering_schema(BUILTIN_NUMBERING_SCHEMES[0], ids=ids),
    ]
    battery += [
        st.pen_width_table(ids=ids),
        st.browser_organization("all", ids=ids),
        st.struct_settings(ids=ids),
        st.keynote_table(ids=ids),
        st.wire_settings(ids=ids),
        st.reinforcement_settings(ids=ids),
        st.auto_cam_settings(ids=ids),
        st.duct_settings(ids=ids),
        st.tracker("MEPNetworkTracker", ids=ids),
    ]
    rows = []
    ok = True
    for rec in battery:
        try:
            pr = adapt_record(rec)
            v = verify_ported(pr)
            rows.append({"class": pr.class_name, "elem_id": pr.elem_id,
                         "ok": v["ok"],
                         "seq102": {k: v[102][k] for k in ("clean", "byte_exact", "bytes")},
                         "notes": pr.notes[:4]})
            ok = ok and v["ok"]
            if verbose:
                s = v[102]
                print(f"   {pr.class_name:<28} seq102 {s['bytes']:>6} B clean={s['clean']} "
                      f"byte_exact={s['byte_exact']} all-ok={v['ok']}")
        except Missing2024 as ex:
            rows.append({"class": rec.class_name, "elem_id": rec.elem_id,
                         "missing_2024": str(ex)})
            if verbose:
                print(f"   {rec.class_name:<28} MISSING-2024 (see "
                      "MISSING_2024_CONSTRUCTED)")
    # the refusal battery: constructors whose classes 2024 lacks must raise
    refusals = []
    for build in (lambda: T.new_conductor_size("12", 2.05, ids=ids),
                  lambda: st.tracker("SheetsInSheetCollectionTracker", ids=ids),
                  lambda: st.tracker("MEPNetworkDataElem", ids=ids),
                  lambda: st.tracker("STEPExportSettings", ids=ids)):
        rec = build()
        try:
            adapt_record(rec)
            refusals.append({"class": rec.class_name, "refused": False})
            ok = False
        except Missing2024:
            refusals.append({"class": rec.class_name, "refused": True})
            if verbose:
                print(f"   {rec.class_name:<28} REFUSED (Missing2024) -- correct")
    spec = verify_specimen_byte_level(verbose=verbose)
    if "skipped" not in spec:
        ok = ok and spec["ok"]
    return {"ok": ok, "records": rows, "refusals": refusals, "specimen": spec}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--verify", action="store_true",
                    help="derive + freeze the CONFIRMED portability table")
    ap.add_argument("--mine", action="store_true",
                    help="derive + freeze the 2024 miners (enum / profile / pen / palette)")
    ap.add_argument("--selftest", action="store_true",
                    help="adapt + 2024 round-trip + specimen battery")
    args = ap.parse_args(argv)
    rc = 0
    if args.verify or not (args.mine or args.selftest):
        t = portability_table(write=True)
        print(f"[portability] {t['universe']} -> {t['counts']}  "
              f"-> {os.path.relpath(PORTABILITY_JSON, ROOT)}")
        print(f"[three-way] deltas differing from 2025: "
              f"{t['non_monotonic_findings']['deltas_that_differ_from_2025']}")
    if args.mine:
        res = mine_all()
        enum, prof = res["enum"], res["profile"]
        print(f"[mine] enum-2024 {enum['count']} categories ({enum['cuttable']} cuttable) "
              f"-> {os.path.relpath(ENUM_2024_JSON, ROOT)}")
        print(f"[mine] profile-2024 {prof['count']} keys over {prof['rows_analysed']} rows "
              f"-> {os.path.relpath(PROFILE_2024_JSON, ROOT)}")
        pen = res[os.path.basename(PEN_2024_JSON)]
        print(f"[mine] pen-2024 scales {pen['scale_breakpoints']} x {pen['pens_per_vector']} "
              f"pens -> {os.path.relpath(PEN_2024_JSON, ROOT)}")
        pal = res[os.path.basename(PALETTE_2024_JSON)]
        print(f"[mine] palette-2024 {pal['property_sets']} sets, laws_hold="
              f"{pal['laws_hold']} -> {os.path.relpath(PALETTE_2024_JSON, ROOT)}")
    if args.selftest:
        rep = selftest()
        print(f"[selftest] ok={rep['ok']} over {len(rep['records'])} records "
              f"+ {len(rep['refusals'])} refusals")
        rc = 0 if rep["ok"] else 1
    return rc


if __name__ == "__main__":
    sys.exit(main())

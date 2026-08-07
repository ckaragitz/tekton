"""genesis/residue_b2.py -- THE PALETTE-BUCKET FIX (genesis-palette-fix stream).

WHAT THIS MODULE IS.  Batch 17 (ORCHESTRATOR VERDICTS #19) named ONE defective
constructor bucket of eight: Group B's PALETTE (``ZB5_palette``).  Z_palette
(= certified Y9 + ONLY the palette bucket in place) FAILS Autodesk's reader
while the seven sibling buckets each PASS; ZB_deep (all eight) translates
PARTIALLY -- the extractor emits a view tree + a sheet then DIES, a subtle
LATE defect.  This module DIAGNOSES the defect and ships the corrected
constructors.  It does NOT edit residue_b.py (the exact upstream diff is in
docs/inbox/genesis-palette-fix.md); it imports residue_b's data + rung
machinery and overrides only what is broken.

THE PALETTE BUCKET = 38 slots in three sub-classes (Y9's residue):
  * 10 SURPLUS ``MaterialElem`` (the palette slots Y7 did not fill)
  * 17 STRUCTURAL ``PropertySetElement`` (m_propertySetType 1) -- in TWO
    real shapes: 13 MODERN (43-47 doubles spanning the legacy -1140xxx PHY
    block AND the unified -1152301..-1152318 block, 10 strings, 4-5 ints)
    and 4 LEGACY (15-26 doubles in the -1140xxx block only: 194585 / 1028776
    / 1177773 / 1352644)
  * 11 THERMAL ``PropertySetElement`` (type 2; 11-12 doubles in -1152308..
    -1152330, 7 strings, 4 ints)

THE DIAGNOSIS (evidence: docs/inbox/genesis-palette-fix.md;
experiments/genesis/subst_k4/palette_fix/pal_census.json):

  D1 [PRIMARY, CERTAIN -- the killer].  ``residue_b._int_param_set`` receives
     (VALUE, ID) tuples through the no-op comprehension
     ``[(v, k) for v, k in ints]`` and writes them into (m_paramId, m_value):
     THE INT PARAM ID AND VALUE ARE SWAPPED in EVERY structural and thermal
     asset (2-4 ints each, all 28 slots).  On disk our objects carry
     ``m_paramId = 3 / 0 / 1`` (small POSITIVE ints) with ``m_value =
     -1150464 / -1140322 / ...`` (the real built-in ids).  Every built-in
     param id in the corpus is NEGATIVE; a positive m_paramId is read as the
     ElementId of a ``ParameterElement`` -- ids 0 / 1 / 3 land on
     document-birth singletons (id 1 = AllProjectPhases), a dangling typed
     reference resolved LATE, when the extractor walks the asset library.
     This is the observed signature (view tree built, then death) and it
     is CONFINED to the two palette constructors: ``_int_param_set`` has
     exactly two call sites (structural_asset, thermal_asset); no passing
     bucket touches it (pipe roughness uses the DOUBLE set -> Z_mepcat PASS;
     the room uses the STRING set -> Z_content PASS).

  D2 [SECONDARY, corpus-universal invariants violated].  (a) Every one of
     the 300 PropertySetElement param sets in the six samples + K4 + Y9 is
     serialised in ASCENDING param-id order (300/300); ours emits
     DESCENDING (``dbl.sort(..., reverse=True)`` -- residue_b's
     '[VERIFIED corpus order]' comment is inverted).  (b) ``m_pElementId
     Params`` is a PRESENT-EMPTY ParamValueSetElementId in all 16 corpus
     shapes (300/300); ours emits None.  (c) ``-1150464`` is the ASSET-CLASS
     ENUM (structural: 1 Basic/soil, 2 Liquid, 3 Metal, 4 Concrete, 5 Wood,
     6/7 Gas; thermal: 3 Solid) -- residue_b stamped 3 on EVERYTHING, so its
     concrete assets shipped as class Metal.

  D3 [EXONERATED].  The MaterialElem sub-class: our ``types.new_material`` is
     the SAME constructor Y7 landed on K4's 13 ACTIVE material slots -- slots
     that ALL carried appearance assets and 8 of which carried
     m_assetMap.m_sharedAssetIdMap links to structural + thermal property
     sets.  Y7 performed the identical referential surgery (appearance ->
     -1, sharedAssetIdMap -> [], param sets -> null) and Y9 -- containing
     those 13 -- is VIEWER-CERTIFIED.  ZB5's 10 surplus slots undergo the same
     operation; the material constructor is proven by 13 prior certified
     instances.  (ZA_deep additionally certifies materials that DO point at
     appearance assets -- ours -- so BOTH linkage states load.)

THE FIX (this module).  The palette PropertySetElements are re-authored by
:func:`property_set_v2`: each corrected object is built OVER THE SLOT'S OWN
DECODED SKELETON (its exact param-id set, ascending order and
present/null container states -- rvt's encoder round-trips every decoded
element record byte-exact, KNOWLEDGE 'encode.py 100% round-trip'), with
every VALUE re-stated: the physical quantities from OUR published-constant
asset library (residue_b.STRUCTURAL_ASSETS / THERMAL_ASSETS; the two id
blocks are decoded EXACTLY -- the legacy -1140xxx block by residue_b's
Rosetta twin, the unified -1152xxx block by within-object value matching
here: see :data:`BIP_UNIFIED`), our identity strings, our provenance (no
Autodesk source token, our own asset-library GUID), the CORRECT asset-class
enum, and the schema-default machinery of the slot's own shape reproduced.
The int params are correctly keyed BY CONSTRUCTION (the parent's own
{m_paramId, m_value} entries are re-valued, never re-paired).  The materials
reuse the certified ``types.new_material`` unchanged.

DELIVERABLES (``experiments/genesis/subst_k4/palette_fix/``, reproduce with
``.venv/bin/python -m rvt.genesis.residue_b2``):

  Z_palette_v2      = certified Y9 + the WHOLE corrected palette bucket in
                      place (10 materials + 17 structural + 11 thermal) -- THE
                      deliverable
  P_pal_mat         = Y9 + ONLY the 10 material substitutions (residue_b's
                      original constructor)          -> predicted PASS (D3)
  P_pal_struct      = Y9 + ONLY the 17 structural assets, residue_b's
                      ORIGINAL (swapped) constructor -> predicted FAIL (D1)
  P_pal_thermal     = Y9 + ONLY the 11 thermal assets, residue_b's ORIGINAL
                      (swapped) constructor          -> predicted FAIL (D1)
  P_pal_struct_v2   = Y9 + ONLY the 17 CORRECTED structural assets -> PASS
  P_pal_thermal_v2  = Y9 + ONLY the 11 CORRECTED thermal assets    -> PASS
  P_pal_swapfix     = Y9 + ZB5's EXACT 38 objects with ONLY the int-param
                      keying corrected (order still descending, ElementId set
                      still null, legacy shape on modern slots, 6-string
                      thermal, source 'GEN' -- every other residue-B choice
                      KEPT) -> if this PASSES, D1 alone was the whole defect
  CTRL_Y9_base.rvt  = the batch's byte-identical certified control

Upload order (probes.json, bisection-first): the control, then Z_palette_v2,
then P_pal_struct / P_pal_thermal / P_pal_mat (the diagnostic bisection,
original constructors), P_pal_swapfix (the swap-alone isolate), then the two
corrected single-class probes.  One round names the class AND tests the
fix.

TERRITORY: this module, tests/test_residue_b2.py,
experiments/genesis/subst_k4/palette_fix/*.rvt + probes.json + reports,
docs/inbox/genesis-palette-fix.md.  residue_b.py / types.py / the tools are
IMPORTED, never edited.  Python: ``.venv/bin/python`` from the repo root.
"""
from __future__ import annotations

import copy
import dataclasses
import json
import os
import sys
import uuid
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .types import (
    TypeRecord, IdArg, element_defaults, _record, _alloc, _param_set,
)
from . import residue_b as RB

ROOT = RB.ROOT
HOUSE_PREFIX = RB.HOUSE_PREFIX          # 'GEN'
gen = RB.gen
log = RB.log

#: the palette bucket's classes (Y9 residue counts): the whole named defect
PALETTE_CLASSES: Dict[str, int] = {"MaterialElem": 10, "PropertySetElement": 28}
PROPSET_STRUCTURAL = RB.PROPSET_STRUCTURAL      # 1
PROPSET_THERMAL = RB.PROPSET_THERMAL            # 2

OUT_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "palette_fix")
ZB5_REPORT = os.path.join(RB.ZB_OUT_DIR, "ZB5_palette.json")


# ===========================================================================
# 0. THE CORRECTED PARAM-SET HELPERS (the D1 / D2 fixes, from-scratch API)
# ===========================================================================
# residue_b built its own three helpers instead of rvt.genesis.types._param_set
# (which is CORRECT) and mis-paired the int one.  These are the corrected
# equivalents: pairs are UNAMBIGUOUS (param_id, value) tuples, the set is
# emitted in ASCENDING param-id order (the corpus law: 300/300 sets), and the
# entries are keyed by CONSTRUCTION.  The re-valuing constructor below does not
# need them (it re-values the slot's own skeleton); they are the reusable,
# tested API a from-scratch genesis asset must use.

def _ascending(pairs: Iterable[Tuple[int, Any]]) -> List[Tuple[int, Any]]:
    """Sort (param_id, value) pairs by param id ASCENDING (most-negative
    first) -- the serialisation order EVERY corpus ParamValueSet exhibits
    [MEASURED pal_census.json: ascending 300/300, zero exceptions]."""
    return sorted(((int(k), v) for k, v in pairs), key=lambda t: t[0])


def double_param_set(pairs: Iterable[Tuple[int, float]]) -> dict:
    """``ParamValueSetDouble`` from (param_id, value) pairs.  Ascending id
    order; the Double set serialises m_value FIRST then m_paramId, which
    ``types._param_set`` reproduces."""
    return _param_set("ParamValueSetDouble",
                      {k: float(v) for k, v in _ascending(pairs)})


def int_param_set(pairs: Iterable[Tuple[int, int]]) -> dict:
    """``ParamValueSetInt`` from (param_id, value) pairs -- CORRECTLY KEYED.

    THE FIX FOR D1: residue_b._int_param_set was fed (VALUE, ID) tuples through
    a no-op comprehension and wrote the value into m_paramId / the id into
    m_value.  Here the pair is (param_id, value) and lands verbatim in
    {"m_paramId": param_id, "m_value": value}; ascending id order.  Every
    built-in param id is NEGATIVE -- a positive m_paramId is an error this
    function asserts against."""
    entries = _ascending(pairs)
    for k, _v in entries:
        if k >= 0:
            raise ValueError(f"built-in param id must be NEGATIVE (got {k}) -- "
                             "positive ids are ParameterElement ElementIds; a "
                             "positive m_paramId is the D1 swap signature")
    return _param_set("ParamValueSetInt", {k: int(v) for k, v in entries})


def astring_param_set(pairs: Iterable[Tuple[int, str]]) -> dict:
    """``ParamValueSetAString`` from (param_id, value) pairs; ascending."""
    return _param_set("ParamValueSetAString",
                      {k: str(v) for k, v in _ascending(pairs)})


def elementid_param_set_empty() -> dict:
    """The PRESENT-EMPTY ``ParamValueSetElementId`` every corpus
    PropertySetElement carries [MEASURED 16/16 shapes, 300/300 instances: n=0,
    present=True] -- the D2(b) fix (residue_b emitted None)."""
    return _param_set("ParamValueSetElementId", {})


def swapped_int_entries(obj: dict) -> List[dict]:
    """Return the int-param entries of a decoded PropertySetElement that show
    THE D1 SWAP SIGNATURE (m_paramId >= 0 with a negative m_value) -- the
    detector the diagnosis and the tests use."""
    out: List[dict] = []
    ps = ((obj.get("m_oParamSet") or {}).get("value") or {})
    arr = ((((ps.get("m_pIntParams") or {}).get("value") or {}).get("m_paramSet")) or [])
    for x in arr:
        k, v = x.get("m_paramId"), x.get("m_value")
        if isinstance(k, int) and isinstance(v, int) and k >= 0 and v < 0:
            out.append(dict(x))
    return out


def unswap_int_params(obj: dict) -> int:
    """IN PLACE: for every int entry with the D1 signature, swap m_paramId
    and m_value back.  Returns the number of entries corrected.  Used by the
    P_pal_swapfix probe (ZB5's exact objects with ONLY the keying fixed)."""
    n = 0
    ps = ((obj.get("m_oParamSet") or {}).get("value") or {})
    arr = ((((ps.get("m_pIntParams") or {}).get("value") or {}).get("m_paramSet")) or [])
    for x in arr:
        k, v = x.get("m_paramId"), x.get("m_value")
        if isinstance(k, int) and isinstance(v, int) and k >= 0 and v < 0:
            x["m_paramId"], x["m_value"] = v, k
            n += 1
    return n


def param_ids_ascending(obj: dict) -> Dict[str, bool]:
    """{container: is-ascending} for the three value containers of a decoded
    PropertySetElement -- the D2(a) order law checker."""
    out: Dict[str, bool] = {}
    ps = ((obj.get("m_oParamSet") or {}).get("value") or {})
    for key in ("m_pDoubleParams", "m_pIntParams", "m_pAStringParams"):
        arr = ((((ps.get(key) or {}).get("value") or {}).get("m_paramSet")) or [])
        ids = [x.get("m_paramId") for x in arr]
        out[key] = (ids == sorted(ids))
    return out


# ===========================================================================
# 1. THE DECODED ASSET SCHEMA (both id blocks; F6/F7 + this stream's block)
# ===========================================================================
#: THE UNIFIED (-1152xxx) STRUCTURAL block, decoded HERE by within-object value
#: matching against the legacy -1140xxx block coexisting in the SAME modern
#: assets (13 instances in Y9: steel / copper / aluminum / concrete / wood /
#: soil) plus physical-unit anchoring [MEASURED, pal_census.json]:
#:   -1152301 / -1152302 = Young's modulus (== -1140300..302, kg/(ft s^2) =
#:               Pa x 0.3048; steel 6.096e10)
#:   -1152303 / -1152304 = Poisson ratio (== -1140303..305)
#:   -1152305             = shear modulus (== -1140306..308)
#:   -1152306 / -1152307 = thermal expansion coefficient (== -1140310..312)
#:   -1152308 .. -1152311 = thermal CONDUCTIVITY x/y/z + scalar (W/mK x
#:               3.28084; steel 174586 = 170.6 = 52 W/mK) -- the modern
#:               structural asset EMBEDS thermal scalars
#:   -1152312             = specific heat (J/kgK x 10.7639; steel 5231 = 486)
#:   -1152313             = DENSITY (kg/m3 x 0.0283168 = kg/ft3; steel 222.85
#:               = 7870 kg/m3, copper 253.15 = 8940, aluminum 76.74 = 2710,
#:               concrete 68.17 = 2407, wood 15.83 = 559 -- textbook-exact)
#:   -1152315 / -1152316 = wood modulus-of-rupture / shear strength (WOOD
#:               shape only, 174580); -1152317 = E again; -1152318 = 3.048
#:               placeholder
#: NB the SAME id -1140309 holds DIFFERENT quantities per shape: in the LEGACY
#: shape it is the material's unit weight (194585 steel = 7153.53 = 77 kN/m3
#: in N-flavour) but in the MODERN shape it is a leftover schema DEFAULT
#: (7.15101 on EVERY Y9 modern asset -- steel, concrete, wood and soil alike
#: = default steel 7850 kg/m3 x g in kN-flavour), the material's real density
#: living at -1152313.  Values must therefore be placed BY THE SLOT'S OWN
#: SHAPE, never by a fixed layout -- which is why property_set_v2 re-values
#: the slot's skeleton instead of authoring a fixed record.
BIP_UNIFIED: Dict[str, int] = {
    "u_young_a": -1152301, "u_young_b": -1152302,
    "u_poisson_a": -1152303, "u_poisson_b": -1152304,
    "u_shear": -1152305,
    "u_alpha_a": -1152306, "u_alpha_b": -1152307,
    "u_conductivity_a": -1152308, "u_conductivity_b": -1152309,
    "u_conductivity_c": -1152310, "u_conductivity_d": -1152311,
    "u_specific_heat": -1152312, "u_density": -1152313,
    "u_wood_rupture": -1152315, "u_wood_shear": -1152316,
    "u_young_c": -1152317, "u_placeholder": -1152318,
}
#: FOUR MORE per-material DUPLICATES living in the -1140xxx range of the
#: modern shape, which residue_b's BIP_PHY does not name [VERIFIED equal to
#: the primary quantity WITHIN every one of the 13 Y9 modern assets, all six
#: materials]: -1140401 == -1140300 (E), -1140412 == -1140303 (nu),
#: -1140413 == -1140306 (G), -1140415 == -1140310 (alpha).  A constructor
#: that states E at -1140300 but leaves -1140401 at the sample's value ships
#: an asset with TWO different Young's moduli and leaks the sample's E --
#: caught by this stream's leak audit; they are FORCED like the primaries.
BIP_LEGACY_DUP: Dict[str, int] = {
    "d_young": -1140401, "d_poisson": -1140412, "d_shear": -1140413, "d_alpha": -1140415,
}
BIP_PHY = RB.BIP_PHY                    # the LEGACY structural block (F6, verified)
BIP_THM = RB.BIP_THM                    # the thermal block (F7, verified)

#: -1150464 = the ASSET-CLASS ENUM [MEASURED: soil 174509 = 1, legacy metals
#: 194585/1028776/1352644 = 3, concrete 1177773 = 4, wood 174580 = 5, water
#: 628406 = 2, air/gas assets 6/7; every THERMAL solid = 3].  D2(c): residue_b
#: emitted 3 for every class -- its concrete assets went out as class Metal.
#: Revit's StructuralAssetClass enum values [VERIFIED: soil 1, plywood
#: (Generic) 2, metals 3, concrete 4, wood 5, plastic 8]
ASSET_CLASS_STRUCTURAL = {"basic": 1, "generic": 2, "metal": 3, "concrete": 4,
                          "wood": 5, "liquid": 6, "gas": 7, "plastic": 8}
ASSET_CLASS_THERMAL_SOLID = 3

# Revit's internal units for the quantities (residue_b F6/F7 + this stream)
PA_TO_INTERNAL = RB.PA_TO_INTERNAL              # stress: Pa -> kg/(ft s^2)  (x 0.3048)
UW_LEGACY_PER_NM3 = RB.NM3_TO_INTERNAL          # legacy unit weight: N/m^3 -> internal
K_TO_INTERNAL = RB.K_TO_INTERNAL                # conductivity W/mK -> internal
CP_TO_INTERNAL = RB.CP_TO_INTERNAL              # specific heat J/kgK -> internal
RHO_TO_INTERNAL = RB.RHO_TO_INTERNAL            # density kg/m3 -> kg/ft3
RESISTIVITY_TO_INTERNAL = RB.RESISTIVITY_TO_INTERNAL

#: OUR asset-library GUID (the -1152337 slot): a DETERMINISTIC GUID in our
#: namespace -- syntactically valid, provably NOT one of Autodesk's shipped
#: library GUIDs (AD121259-... / 05AB8C01-... / 51130EE1-... / ...), and
#: stable across re-runs (the file reproduces byte-for-byte).
HOUSE_ASSET_LIBRARY_GUID = str(uuid.uuid5(
    uuid.uuid5(uuid.NAMESPACE_DNS, "rvt-writer.gen.house-standard"),
    "asset-library/1")).upper()

#: thermophysical companions for the STRUCTURAL specs (the modern structural
#: asset embeds conductivity / specific heat / density: -1152308..-1152313).
#: Values = published constants of the substance (k W/mK, cp J/kgK, rho
#: kg/m3), keyed by residue_b.STRUCTURAL_ASSETS 'key'.
STRUCTURAL_THERMO: Dict[str, Tuple[float, float, float]] = {
    "steel_345": (45.0, 490.0, 7850.0), "steel_250": (45.0, 490.0, 7850.0),
    "steel_rebar_500": (45.0, 490.0, 7850.0), "steel_light_gauge": (45.0, 490.0, 7850.0),
    "aluminum_6061": (167.0, 896.0, 2700.0), "copper": (390.0, 385.0, 8940.0),
    "concrete_25": (1.7, 880.0, 2400.0), "concrete_32": (1.7, 880.0, 2450.0),
    "concrete_lw_20": (0.8, 840.0, 1800.0),
    "wood_sw": (0.12, 1600.0, 550.0), "wood_hw": (0.16, 1600.0, 700.0),
    "glass": (1.0, 840.0, 2500.0), "masonry_cmu": (1.0, 840.0, 2100.0),
    "gypsum": (0.25, 1090.0, 800.0), "grp": (0.3, 1200.0, 1900.0),
    "pvc": (0.16, 900.0, 1400.0), "porcelain": (1.5, 750.0, 2400.0),
}
G_STD = 9.80665     # m/s^2 -- unit weight from density


def _material_class_key(spec: Dict[str, Any]) -> str:
    """OUR structural spec -> the asset-class family (drives the -1150464
    enum and the schema token)."""
    if spec.get("wood"):
        return "wood"
    if spec.get("concrete"):
        return "concrete"
    key = str(spec.get("key", ""))
    sub = str(spec.get("subclass", "")).lower()
    if any(t in key for t in ("steel", "aluminum", "copper", "iron")) or \
            sub in ("ferrous", "non ferrous"):
        return "metal"
    if key in ("pvc", "grp"):
        return "plastic"
    return "basic"          # glass / masonry / gypsum / porcelain


def structural_schema_token(spec: Dict[str, Any]) -> str:
    """The -1152342 asset-schema token for OUR structural asset: the corpus's
    GENERIC vocabulary per class ('structural:metal' / 'structural:concrete'
    / 'structural:wood' / 'structural:basic' -- all present verbatim in the
    six samples), a FORMAT token, not authorship."""
    return {"metal": "structural:metal", "concrete": "structural:concrete",
            "wood": "structural:wood", "basic": "structural:basic",
            "plastic": "Plastic:structural"}[_material_class_key(spec)]


def thermal_schema_token(spec: Dict[str, Any]) -> str:
    """The -1152342 token for OUR thermal asset: the spec's own schema class
    string (e.g. 'thermal:solid', 'panel:thermal:solid') -- FORMAT tokens."""
    return str(spec.get("schema", "thermal:solid"))


# ===========================================================================
# 2. OUR VALUE MAPS (param id -> our value, per asset role)
# ===========================================================================
# Each map returns {param_id: value} for every id whose value is a physical
# quantity / identity string / provenance token our spec STATES.  Every OTHER
# id in a slot's skeleton is CLASS-CORRELATED MACHINERY (the schema defaults
# of the slot's own material class -- wood-species defaults on non-wood
# assets, the -1140309 modern default, the reinforcement / resistance-calc
# constants, the shape flags) and is REPRODUCED from the slot: the role
# correspondence is BY MATERIAL CLASS (a concrete slot receives our
# concrete, a wood slot our wood), so a slot's class-correlated defaults are
# correct for our replacement by construction.  The report proves per kept
# id that it is either lineage-CONSTANT machinery or a class default.

def structural_value_map(spec: Dict[str, Any], *, legacy_shape: bool,
                         skeleton_ids: Set[int]) -> Dict[int, Any]:
    """OUR values for a STRUCTURAL asset (both id blocks), for a slot whose
    param-id skeleton is ``skeleton_ids``.  ``legacy_shape`` = the slot lacks
    the unified -1152xxx block (then -1140309 is the material's unit weight;
    in the modern shape -1140309 is a schema default we leave, the density
    living at -1152313)."""
    E = float(spec["E_MPa"]) * 1e6 * PA_TO_INTERNAL
    nu = float(spec.get("nu", 0.3))
    G = E / (2.0 * (1.0 + nu))
    alpha = float(spec.get("alpha", 1.2e-5))
    kNm3 = float(spec.get("unit_weight_kNm3", 24.0))
    k_th, cp, rho = STRUCTURAL_THERMO.get(spec.get("key"), (1.0, 840.0, 2400.0))
    cls = _material_class_key(spec)
    m: Dict[int, Any] = {}
    # --- the legacy -1140xxx PHY block (F6) ---
    for pid in (BIP_PHY["young_x"], BIP_PHY["young_y"], BIP_PHY["young_z"]):
        m[pid] = E
    for pid in (BIP_PHY["poisson_x"], BIP_PHY["poisson_y"], BIP_PHY["poisson_z"]):
        m[pid] = nu
    for pid in (BIP_PHY["shear_x"], BIP_PHY["shear_y"], BIP_PHY["shear_z"]):
        m[pid] = G
    for pid in (BIP_PHY["alpha_x"], BIP_PHY["alpha_y"], BIP_PHY["alpha_z"]):
        m[pid] = alpha
    if legacy_shape:
        # legacy shape: -1140309 IS the material's unit weight (N-flavour,
        # 77 kN/m3 steel -> 7153.53 [VERIFIED rst 194585])
        m[BIP_PHY["unit_weight"]] = kNm3 * 1000.0 * UW_LEGACY_PER_NM3
    # metals state yield / tensile; other classes keep the slot's class default
    if "fy_MPa" in spec:
        m[BIP_PHY["min_yield_stress"]] = float(spec["fy_MPa"]) * 1e6 * PA_TO_INTERNAL
    if "fu_MPa" in spec:
        m[BIP_PHY["min_tensile_strength"]] = float(spec["fu_MPa"]) * 1e6 * PA_TO_INTERNAL
    if cls == "concrete" and "fc_MPa" in spec:
        m[BIP_PHY["concrete_compression"]] = float(spec["fc_MPa"]) * 1e6 * PA_TO_INTERNAL
    if cls == "wood":
        for key, bip in (("bending_MPa", "bending"), ("comp_par_MPa", "compression_parallel"),
                         ("comp_perp_MPa", "compression_perpendicular"),
                         ("shear_par_MPa", "shear_parallel"),
                         ("shear_perp_MPa", "shear_perpendicular")):
            if key in spec:
                m[BIP_PHY[bip]] = float(spec[key]) * 1e6 * PA_TO_INTERNAL
        m[BIP_PHY["species_str"]] = str(spec.get("subclass", "Softwood"))
        m[BIP_PHY["grade_str"]] = gen("No.2")
    # --- the -1140xxx-range DUPLICATES of the physical quantities (modern
    #     shape; BIP_LEGACY_DUP) -- forced with the primaries so the object
    #     never carries two E / nu / G / alpha values ---
    m[BIP_LEGACY_DUP["d_young"]] = E
    m[BIP_LEGACY_DUP["d_poisson"]] = nu
    m[BIP_LEGACY_DUP["d_shear"]] = G
    m[BIP_LEGACY_DUP["d_alpha"]] = alpha
    # --- the unified -1152xxx block (this stream), present in the modern shape ---
    for pid in (BIP_UNIFIED["u_young_a"], BIP_UNIFIED["u_young_b"], BIP_UNIFIED["u_young_c"]):
        m[pid] = E
    for pid in (BIP_UNIFIED["u_poisson_a"], BIP_UNIFIED["u_poisson_b"]):
        m[pid] = nu
    m[BIP_UNIFIED["u_shear"]] = G
    for pid in (BIP_UNIFIED["u_alpha_a"], BIP_UNIFIED["u_alpha_b"]):
        m[pid] = alpha
    kint = k_th * K_TO_INTERNAL
    for pid in (BIP_UNIFIED["u_conductivity_a"], BIP_UNIFIED["u_conductivity_b"],
                BIP_UNIFIED["u_conductivity_c"], BIP_UNIFIED["u_conductivity_d"]):
        m[pid] = kint
    m[BIP_UNIFIED["u_specific_heat"]] = cp * CP_TO_INTERNAL
    m[BIP_UNIFIED["u_density"]] = rho * RHO_TO_INTERNAL
    if cls == "wood":
        if "bending_MPa" in spec:
            m[BIP_UNIFIED["u_wood_rupture"]] = float(spec["bending_MPa"]) * 1e6 * PA_TO_INTERNAL
        if "shear_par_MPa" in spec:
            m[BIP_UNIFIED["u_wood_shear"]] = float(spec["shear_par_MPa"]) * 1e6 * PA_TO_INTERNAL
    # --- identity strings (ours) + provenance (no Autodesk attribution) ------
    # NB the asset-class ENUM (-1150464) and the schema TOKEN (-1152342) are
    # NOT overridden: the object keeps the slot's own skeleton, so the slot's
    # own class enum + schema-class token still name it correctly; class
    # correspondence between the slot and our spec is ENFORCED by
    # structural_role_v2 (see asset_class_family) -- D2(c) resolved by
    # correspondence, not by stamping.  Class-correlated shape flags
    # (-1152338 / -1152314 / -1152319 / -1140322 / -1140323) are likewise the
    # slot's.
    m[-1150466] = str(spec["name"])                            # asset name
    m[-1150465] = str(spec.get("subclass", ""))                # subclass
    m[-1150481] = f"{spec['name']} -- published engineering constants"
    m[-1152341] = ""                                            # keywords
    m[-1152340] = ""                                            # NO Autodesk source token
    m[-1152339] = ""                                            # NO Inventor sustainability token
    m[-1152337] = HOUSE_ASSET_LIBRARY_GUID                      # OUR library GUID
    # only ids the slot's shape carries are applied by the caller
    return {k: v for k, v in m.items() if k in skeleton_ids}


def thermal_value_map(spec: Dict[str, Any], *, skeleton_ids: Set[int]) -> Dict[int, Any]:
    """OUR values for a THERMAL asset (the -1152308..-1152330 block, F7)."""
    k = float(spec["k"]) * K_TO_INTERNAL
    cp = float(spec["cp"]) * CP_TO_INTERNAL
    rho_kgm3 = float(spec["rho"])
    m: Dict[int, Any] = {
        BIP_THM["conductivity_x"]: k, BIP_THM["conductivity_y"]: k,
        BIP_THM["conductivity_z"]: k, BIP_THM["conductivity"]: k,
        BIP_THM["specific_heat"]: cp,
        BIP_THM["density"]: rho_kgm3 * RHO_TO_INTERNAL,
        BIP_THM["emissivity"]: float(spec.get("emissivity", 0.9)),
        BIP_THM["permeability"]: float(spec.get("permeability", 0.0)),
        BIP_THM["porosity"]: float(spec.get("porosity", 0.001)),
        BIP_THM["reflectivity"]: float(spec.get("reflectivity", 0.0)),
        BIP_THM["electrical_resistivity"]: float(spec.get("resistivity", 1e8)) * RESISTIVITY_TO_INTERNAL,
        # NB the class-correlated ints (-1152338 compressible / -1152326 /
        # -1150464 thermal-material-type / -1140322) and the schema TOKEN
        # (-1152342) stay the slot's own: class correspondence with our spec is
        # enforced by thermal_role_v2, so the slot's flags + token are correct
        # for our same-class replacement.
        -1150466: str(spec["name"]), -1150465: str(spec.get("subclass", "")),
        -1150481: f"{spec['name']} -- published thermophysical constants",
        -1152341: "",
        -1152340: "",                                           # NO Autodesk source token
        -1152339: "", -1152337: HOUSE_ASSET_LIBRARY_GUID,
    }
    # thermal-12 shape (aerated concrete) additionally carries the legacy unit
    # weight -1140309 = the material's unit weight; derive from OUR density in
    # the shape's own flavour (chosen against the slot below by the caller)
    if BIP_PHY["unit_weight"] in skeleton_ids:
        m[BIP_PHY["unit_weight"]] = ("__unit_weight_from_density__", rho_kgm3)
    return {k: v for k, v in m.items() if k in skeleton_ids}


def _unit_weight_flavour(rho_kgm3: float, parent_value: float) -> float:
    """Choose the -1140309 unit-weight FLAVOUR the slot uses (the corpus
    stores this id in an N-flavour ~thousands, or a kN-flavour ~units,
    depending on the shape / template) by the parent's own magnitude:
    unit weight = rho x g, in N/m3 -> internal (N-flavour) or /1000
    (kN-flavour); the candidate closest to the slot's value in log-distance
    wins.  Deterministic; states OUR density in the slot's units."""
    import math
    n_flavour = rho_kgm3 * G_STD * UW_LEGACY_PER_NM3
    kn_flavour = n_flavour / 1000.0
    pv = float(parent_value) if parent_value not in (None, 0) else 0.0
    if pv <= 0:
        return n_flavour
    cands = [n_flavour, kn_flavour]
    return min(cands, key=lambda c: abs(math.log10(max(c, 1e-30)) - math.log10(pv)))


# ===========================================================================
# 3. THE CORRECTED CONSTRUCTOR: re-value the slot's own skeleton
# ===========================================================================

@dataclasses.dataclass
class RevalueTrace:
    """Per-slot provenance ledger: which param ids became OURS, which are
    reproduced machinery, plus the D1/D2 conformance of the emitted object."""
    slot: int
    role: str
    spec_key: str
    shape: str
    ours: List[Tuple[str, int]] = dataclasses.field(default_factory=list)
    kept: List[Tuple[str, int]] = dataclasses.field(default_factory=list)
    swapped_ints_in_output: int = 0
    ascending: Dict[str, bool] = dataclasses.field(default_factory=dict)
    elementid_set_present: bool = False


def _paramset_arrays(obj: dict) -> Dict[str, list]:
    ps = ((obj.get("m_oParamSet") or {}).get("value") or {})
    out = {}
    for key in ("m_pDoubleParams", "m_pIntParams", "m_pAStringParams"):
        sub = ps.get(key)
        out[key] = ((((sub or {}).get("value") or {}).get("m_paramSet")) or []) if sub else []
    return out


def skeleton_ids_of(obj: dict) -> Set[int]:
    """The set of param ids a decoded PropertySetElement's skeleton carries."""
    ids: Set[int] = set()
    for arr in _paramset_arrays(obj).values():
        for x in arr:
            if x.get("m_paramId") is not None:
                ids.add(int(x["m_paramId"]))
    return ids


def is_legacy_shape(skeleton_ids: Set[int]) -> bool:
    """A structural asset is LEGACY-shaped iff its skeleton carries none of
    the unified -1152xxx block (194585 / 1028776 / 1177773 / 1352644)."""
    return not any(pid <= -1152000 for pid in skeleton_ids)


def property_set_v2(parent_obj: dict, spec: Dict[str, Any], *, kind: str,
                    ids: IdArg = None, elem_id: int = None,
                    slot: int = -1, spec_key: str = "") -> Tuple[TypeRecord, RevalueTrace]:
    """OUR corrected PropertySetElement for a residue slot, built OVER THE
    SLOT'S OWN DECODED SKELETON.

    ``parent_obj`` = the slot's decoded seq-102 object (the sample's).  We
    deep-copy it -- keeping the EXACT param-id set, the corpus's ascending
    serialisation order and the present-empty ElementId set / null Bool set
    of its shape (D2(a)/(b) satisfied BY CONSTRUCTION) -- and RE-VALUE every
    param whose quantity our library states (:func:`structural_value_map`
    / :func:`thermal_value_map`; D1 satisfied by construction: entries are
    re-valued in place, never re-paired; D2(c): the correct class enum).
    Params our spec does not state are the slot's class-correlated schema
    machinery, reproduced (see module doc).  ``kind`` = 'structural' or
    'thermal'.  Returns (TypeRecord, provenance trace)."""
    eid = _alloc(ids, elem_id)
    obj = copy.deepcopy(parent_obj)
    # our Element base (the top-level machinery is identical to the sample's
    # for this class -- verified field-for-field -- element_defaults reproduces
    # it; the ParamValueSet pointers on the ELEMENT (not the asset) stay null
    # exactly as every corpus PropertySetElement has them)
    element_defaults(obj, eid)
    obj["m_cellList"] = None
    arrays = _paramset_arrays(obj)
    skel = skeleton_ids_of(obj)
    shape = ("legacy" if kind == "structural" and is_legacy_shape(skel)
             else ("modern" if kind == "structural" else
                   ("thermal-uw" if BIP_PHY["unit_weight"] in skel else "thermal")))
    if kind == "structural":
        vmap = structural_value_map(spec, legacy_shape=(shape == "legacy"), skeleton_ids=skel)
        obj["m_propertySetType"] = int(parent_obj.get("m_propertySetType") or PROPSET_STRUCTURAL)
    else:
        vmap = thermal_value_map(spec, skeleton_ids=skel)
        obj["m_propertySetType"] = PROPSET_THERMAL
    trace = RevalueTrace(slot=int(slot), role=kind, spec_key=str(spec_key or spec.get("key", "")),
                         shape=shape)
    for key, arr in arrays.items():
        for x in arr:
            pid = int(x["m_paramId"])
            if pid in vmap:
                nv = vmap[pid]
                # the deferred unit-weight-from-density marker (thermal-12 shape)
                if isinstance(nv, tuple) and nv and nv[0] == "__unit_weight_from_density__":
                    nv = _unit_weight_flavour(float(nv[1]), x.get("m_value"))
                if key == "m_pDoubleParams":
                    x["m_value"] = float(nv)
                elif key == "m_pIntParams":
                    x["m_value"] = int(nv)
                else:
                    x["m_value"] = str(nv)
                trace.ours.append((key, pid))
            else:
                trace.kept.append((key, pid))
    # conformance ledger (the D1 / D2 laws, checked on the OUTPUT)
    trace.swapped_ints_in_output = len(swapped_int_entries(obj))
    trace.ascending = param_ids_ascending(obj)
    ps = ((obj.get("m_oParamSet") or {}).get("value") or {})
    trace.elementid_set_present = ps.get("m_pElementIdParams") is not None
    rec = _record(f"{kind}-asset-v2", "PropertySetElement", -2000924, eid, obj,
                  refs={"asset": spec.get("key"), "shape": shape, "slot": int(slot)},
                  notes=[f"CORRECTED {kind} asset ({shape} shape): re-valued over the slot's "
                         "own skeleton; int params correctly keyed (D1), corpus ascending "
                         "order + present-empty ElementId set (D2) by construction; values = "
                         "published constants of the substance; source token cleared, house "
                         "library GUID, correct asset-class enum"])
    return rec, trace


# ===========================================================================
# 4. ROLE SELECTION (identical to ZB5's, so the probes bisect ZB5 exactly)
# ===========================================================================
#: residue_b build_ZB5_palette's material role table, verbatim (so P_pal_mat
#: reproduces ZB5's material assignment slot-for-slot)
MATERIAL_ROLE_KEY = {"copper": "copper", "alum": "aluminum", "stainless": "stainless",
                     "galv": "steel_galv", "light gauge": "steel_galv", "steel": "steel_enamel",
                     "metal": "steel_enamel", "iron": "iron_ductile", "concrete": "concrete_precast",
                     "porcelain": "porcelain", "pvc": "pvc", "plastic": "pvc", "fiberglass": "fiberglass",
                     "wood": "fiberglass", "lumber": "fiberglass"}


def propertyset_hint(ctx, slot: int) -> str:
    """The role hint ZB5 uses for a PropertySetElement slot: the asset's own
    schema / name / description / subclass strings + its referring materials'
    names (verbatim from build_ZB5_palette)."""
    v = ctx.value(slot) or {}
    ps = ((v.get("m_oParamSet") or {}).get("value") or {})
    strs = {p.get("m_paramId"): p.get("m_value") for p in
            ((((ps.get("m_pAStringParams") or {}).get("value") or {}).get("m_paramSet")) or [])}
    hint = " ".join(str(strs.get(k) or "") for k in (-1152342, -1150466, -1150481, -1150465))
    for r in ctx.inbound(slot):
        if ctx.cls_of.get(r) == "MaterialElem":
            hint += " " + RB._mat_name(ctx, r)
    return hint


def _asset_strings(obj: dict) -> Dict[int, str]:
    ps = ((obj.get("m_oParamSet") or {}).get("value") or {})
    arr = ((((ps.get("m_pAStringParams") or {}).get("value") or {}).get("m_paramSet")) or [])
    return {int(p.get("m_paramId")): str(p.get("m_value") or "") for p in arr}


def _asset_ints(obj: dict) -> Dict[int, int]:
    ps = ((obj.get("m_oParamSet") or {}).get("value") or {})
    arr = ((((ps.get("m_pIntParams") or {}).get("value") or {}).get("m_paramSet")) or [])
    return {int(p.get("m_paramId")): p.get("m_value") for p in arr}


def asset_class_family(obj: dict, kind: str) -> str:
    """The AUTHORITATIVE material-class family of a sample asset, from ITS OWN
    signals only (never its referrers, whose material names the Y-ladder has
    already replaced): the -1152342 schema TOKEN, the -1150464 asset-class
    ENUM (Revit's StructuralAssetClass: 1 Basic, 2 Generic, 3 Metal,
    4 Concrete, 5 Wood, 6 Liquid, 7 Gas, 8 Plastic [VERIFIED on all 17 Y9
    structural slots]) and its own name / description / subclass strings.
    Structural families: metal / concrete / wood / plastic / basic; thermal:
    metal / concrete / wood / plastic / mineral (the -1150464 thermal value
    3 = 'Solid' does not discriminate, so the token + name decide)."""
    strs = _asset_strings(obj)
    ints = _asset_ints(obj)
    tok = strs.get(-1152342, "").lower()
    own = " ".join(strs.get(k, "") for k in (-1150466, -1150481, -1150465)).lower()
    text = f"{tok} {own}"
    enum = ints.get(-1150464)
    if kind == "structural":
        # 1. the schema token names the family outright when present
        if "concrete" in tok:
            return "concrete"
        if "wood" in tok:
            return "wood"
        if "metal" in tok or "alloy" in tok:
            return "metal"
        if "plastic" in tok:
            return "plastic"
        if "soil" in tok or "basic" in tok:
            return "basic"
        # 2. the StructuralAssetClass enum (legacy assets carry no token)
        if enum in (3,):
            return "metal"
        if enum in (4,):
            return "concrete"
        if enum in (5,):
            return "wood"
        if enum in (8,):
            return "plastic"
        if enum in (1,):
            return "basic"
        # 3. the asset's own strings
        if any(t in text for t in ("concrete", "beton", "f'c", "ksi")):
            return "concrete"
        if any(t in text for t in ("wood", "softwood", "hardwood", "lumber", "plywood", "timber")):
            return "wood"
        if any(t in text for t in ("plastic", "pvc", "hdpe", "polyethylene", "polymer")):
            return "plastic"
        return "metal"
    # thermal: family by token/name (concrete-like / metal / wood / plastic / mineral)
    if any(t in text for t in ("concrete", "aerated", "precast", "beton")):
        return "concrete"
    if any(t in text for t in ("steel", "iron", "copper", "alumin", "stainless", "metal",
                              "brass", "bronze", "polished")):
        return "metal"
    if any(t in text for t in ("wood", "softwood", "hardwood", "plywood", "panel", "timber", "oak")):
        return "wood"
    if any(t in text for t in ("hdpe", "pvc", "polyethylene", "plastic", "polymer")):
        return "plastic"
    return "mineral"        # soil / earth / glass / gypsum / roofing membranes ...


def _spec_by_key(pool: List[Dict[str, Any]], key: str) -> Dict[str, Any]:
    return next(s for s in pool if s["key"] == key)


def structural_role_v2(obj: dict) -> Tuple[str, Dict[str, Any]]:
    """OUR structural spec for a sample structural-asset slot, CONSTRAINED to
    the slot's own class family (:func:`asset_class_family`) so the shape-
    faithful re-valuing never mixes classes; the pick within the family is by
    the asset's OWN name keywords (never referrer names).  Returns (family,
    spec).  Fixes residue_b's structural_asset_role, whose 'cast' token
    matched 'Cast-in-Place' concrete and whose referrer-name hint was
    polluted by Y7's material substitution (5 of 17 slots mis-classed)."""
    fam = asset_class_family(obj, "structural")
    pool = RB.STRUCTURAL_ASSETS
    s = " ".join(_asset_strings(obj).values()).lower()
    if fam == "concrete":
        if any(t in s for t in ("lightweight", "light weight", " lw ", "lw ", "aerated")):
            return fam, _spec_by_key(pool, "concrete_lw_20")
        # unambiguous higher-grade markers only (NB 'f'c=3.5 ksi' contains
        # '5 ksi' as a substring -- grade markers must be explicit)
        if any(t in s for t in ("high strength", "f'c=6", "f'c=8", "6 ksi", "8 ksi",
                                 "40 mpa", "45 mpa", "50 mpa", "c40", "c45", "c50")):
            return fam, _spec_by_key(pool, "concrete_32")
        return fam, _spec_by_key(pool, "concrete_25")
    if fam == "wood":
        if any(t in s for t in ("hardwood", "oak", "maple", "walnut")):
            return fam, _spec_by_key(pool, "wood_hw")
        return fam, _spec_by_key(pool, "wood_sw")
    if fam == "plastic":
        if any(t in s for t in ("fiberglass", "frp", "grp", "reinforced")):
            return fam, _spec_by_key(pool, "grp")
        return fam, _spec_by_key(pool, "pvc")
    if fam == "basic":
        if any(t in s for t in ("glass", "glaz")):
            return fam, _spec_by_key(pool, "glass")
        if any(t in s for t in ("gypsum", "plaster")):
            return fam, _spec_by_key(pool, "gypsum")
        if any(t in s for t in ("porcelain", "ceramic")):
            return fam, _spec_by_key(pool, "porcelain")
        return fam, _spec_by_key(pool, "masonry_cmu")     # soil / earth / masonry / brick
    # metal (the default family): pick within metals
    if any(t in s for t in ("copper", "c10100", "brass", "bronze")):
        return fam, _spec_by_key(pool, "copper")
    if any(t in s for t in ("alumin", "6061", "alloy")):
        return fam, _spec_by_key(pool, "aluminum_6061")
    if any(t in s for t in ("rebar", "grade 60", "grade 65", "reinf", "wire fabric", "fabric")):
        return fam, _spec_by_key(pool, "steel_rebar_500")
    if any(t in s for t in ("light gauge", "cold formed", "cold-formed")):
        return fam, _spec_by_key(pool, "steel_light_gauge")
    if any(t in s for t in ("250", "a36", "36 ksi")):
        return fam, _spec_by_key(pool, "steel_250")
    return fam, _spec_by_key(pool, "steel_345")             # carbon / stainless / iron / high strength


def thermal_role_v2(obj: dict) -> Tuple[str, Dict[str, Any]]:
    """OUR thermal spec for a sample thermal-asset slot, from the asset's OWN
    token / name only (residue_b's hint used the polluted referrer names --
    the HDPE slot picked 'steel' via its 'GEN Steel, Structural' referrer)."""
    fam = asset_class_family(obj, "thermal")
    pool = RB.THERMAL_ASSETS
    s = " ".join(_asset_strings(obj).values()).lower()
    if fam == "concrete":
        if any(t in s for t in ("aerated", "lightweight", "light weight")):
            return fam, _spec_by_key(pool, "concrete_lw")
        return fam, _spec_by_key(pool, "concrete")
    if fam == "wood":
        if any(t in s for t in ("plywood", "panel", "sheathing")):
            return fam, _spec_by_key(pool, "plywood")
        return fam, _spec_by_key(pool, "wood_sw")
    if fam == "plastic":
        return fam, _spec_by_key(pool, "pvc")
    if fam == "metal":
        if "stainless" in s or "polished" in s:
            return fam, _spec_by_key(pool, "stainless")
        if any(t in s for t in ("copper", "brass", "bronze")):
            return fam, _spec_by_key(pool, "copper")
        if "alumin" in s:
            return fam, _spec_by_key(pool, "aluminum")
        return fam, _spec_by_key(pool, "steel")
    # mineral: soil / glass / gypsum / masonry ...
    if any(t in s for t in ("soil", "earth", "landscape", "sand")):
        return fam, _spec_by_key(pool, "soil")
    if "glass" in s or "glaz" in s:
        return fam, _spec_by_key(pool, "glass")
    if any(t in s for t in ("gypsum", "plaster")):
        return fam, _spec_by_key(pool, "gypsum")
    return fam, _spec_by_key(pool, "soil")


def propertyset_pairs_v2(ctx, landed: Dict[int, Any]) -> List[Tuple[int, str, Dict[str, Any], str]]:
    """[(slot, kind, our spec, family)] with CLASS-CONSTRAINED role selection
    (the v2 correspondence).  kind by m_propertySetType: 2 = thermal, else
    structural."""
    out: List[Tuple[int, str, Dict[str, Any], str]] = []
    for slot in sorted(RB._residue_slots(ctx, "PropertySetElement", landed)):
        v = ctx.value(slot) or {}
        pst = int(v.get("m_propertySetType", 0) or 0)
        if pst == PROPSET_THERMAL:
            fam, spec = thermal_role_v2(v)
            out.append((slot, "thermal", spec, fam))
        else:
            fam, spec = structural_role_v2(v)
            out.append((slot, "structural", spec, fam))
    return out


def our_spec_family(spec: Dict[str, Any], kind: str) -> str:
    """The class family OUR spec belongs to (for the correspondence check)."""
    if kind == "structural":
        return _material_class_key(spec)
    sub = str(spec.get("subclass", "")).lower()
    key = str(spec.get("key", "")).lower()
    if "concrete" in key or sub == "concrete":
        return "concrete"
    if sub == "metal" or any(t in key for t in ("steel", "stainless", "copper", "aluminum")):
        return "metal"
    if sub == "wood" or "wood" in key or key == "plywood":
        return "wood"
    if sub == "plastic" or key in ("pvc",):
        return "plastic"
    return "mineral"


def material_pairs(ctx, landed: Dict[int, Any]) -> List[Tuple[int, Dict[str, Any]]]:
    """[(slot, our extended-material spec)] exactly as ZB5 pairs them."""
    mats = sorted(RB._residue_slots(ctx, "MaterialElem", landed))
    pool = list(RB.EXTENDED_MATERIALS)
    used: Set[str] = set()
    out: List[Tuple[int, Dict[str, Any]]] = []
    unfilled: List[int] = []
    for slot in mats:
        nm = RB._mat_name(ctx, slot).lower()
        key = next((k for token, k in MATERIAL_ROLE_KEY.items() if token in nm and k not in used), None)
        spec = next((s for s in pool if s["key"] == key), None) if key else None
        if spec is None:
            unfilled.append(slot)
            continue
        used.add(spec["key"])
        out.append((slot, spec))
    leftover = [s for s in pool if s["key"] not in used]
    for slot, spec in zip(unfilled, leftover):
        out.append((slot, spec))
    return sorted(out, key=lambda t: t[0])


def propertyset_pairs(ctx, landed: Dict[int, Any]) -> List[Tuple[int, str, Dict[str, Any]]]:
    """[(slot, kind, our spec)] exactly as ZB5 pairs them (kind by
    m_propertySetType: 2 = thermal, else structural; spec by role hint)."""
    out: List[Tuple[int, str, Dict[str, Any]]] = []
    for slot in sorted(RB._residue_slots(ctx, "PropertySetElement", landed)):
        v = ctx.value(slot) or {}
        pst = int(v.get("m_propertySetType", 0) or 0)
        hint = propertyset_hint(ctx, slot)
        if pst == PROPSET_THERMAL:
            role = RB.thermal_asset_role(hint)
            spec = next(s for s in RB.THERMAL_ASSETS if s["key"] == role)
            out.append((slot, "thermal", spec))
        else:
            role = RB.structural_asset_role(hint, "")
            spec = next(s for s in RB.STRUCTURAL_ASSETS if s["key"] == role)
            out.append((slot, "structural", spec))
    return out


# ===========================================================================
# 5. THE BUILDERS (the corrected bucket + the bisection sub-class probes)
# ===========================================================================

def _substbuild(ctx, corr: Dict[int, int], records: List[Any], notes: List[str],
                info: Dict[str, Any]):
    _gs = RB._genesis_substitute()
    return _gs.SubstBuild(old_ids=sorted(corr), records=records, corr=corr,
                          notes=notes, residue={}, info=info)


def _materials(ctx, landed, records, corr, notes) -> int:
    ids = RB._new_ids(ctx)
    n = 0
    for slot, spec in material_pairs(ctx, landed):
        rec = RB.extended_material(spec, ids=ids)         # the CERTIFIED Y7 constructor
        records.append(rec)
        corr[slot] = int(rec.elem_id)
        n += 1
    notes.append(f"materials: {n} surplus slots <- our extended palette via types.new_material "
                 f"(the constructor certified x13 by Y7/Y9 -- D3 exonerated)")
    return n


def _propsets_v2(ctx, landed, records, corr, notes, traces: List[dict],
                 want_kind: Optional[str] = None) -> Tuple[int, int]:
    """The CORRECTED property sets, with the class-constrained (v2) role
    correspondence -- each trace records the slot's authoritative family and
    OUR spec's family, which the shape-faithful re-valuing REQUIRES equal."""
    ids = RB._new_ids(ctx)
    n_s = n_t = 0
    for slot, kind, spec, fam in propertyset_pairs_v2(ctx, landed):
        if want_kind and kind != want_kind:
            continue
        rec, tr = property_set_v2(ctx.value(slot) or {}, spec, kind=kind, ids=ids,
                                  slot=slot, spec_key=str(spec.get("key", "")))
        records.append(rec)
        corr[slot] = int(rec.elem_id)
        d = dataclasses.asdict(tr)
        ours_fam = our_spec_family(spec, kind)
        # for the correspondence law only the physical family matters:
        # 'generic' (plywood sheathing, StructuralAssetClass 2) is served by
        # our wood spec; 'basic' / 'mineral' by our masonry / soil specs
        equivalent = {("generic", "wood"), ("basic", "basic"), ("mineral", "mineral")}
        d["slot_family"] = fam
        d["our_family"] = ours_fam
        d["family_match"] = (fam == ours_fam) or ((fam, ours_fam) in equivalent)
        traces.append(d)
        if kind == "thermal":
            n_t += 1
        else:
            n_s += 1
    if not want_kind or want_kind == "structural":
        notes.append(f"property sets: {n_s} STRUCTURAL assets <- CORRECTED (skeleton re-valued, "
                     f"both id blocks, correct enum, house GUID, no source token)")
    if not want_kind or want_kind == "thermal":
        notes.append(f"property sets: {n_t} THERMAL assets <- CORRECTED (same method, F7 block)")
    return n_s, n_t


def _propsets_original(ctx, landed, records, corr, notes, *, want_kind: str) -> int:
    """The residue_b ORIGINAL (defective) property-set constructors for one
    sub-class -- the diagnostic bisection reproducing ZB5's exact objects."""
    ids = RB._new_ids(ctx)
    n = 0
    for slot, kind, spec in propertyset_pairs(ctx, landed):
        if kind != want_kind:
            continue
        if kind == "thermal":
            rec = RB.thermal_asset(spec, ids=ids)
        else:
            v = ctx.value(slot) or {}
            pst = int(v.get("m_propertySetType", 0) or 0)
            rec = RB.structural_asset(spec, property_set_type=(pst or PROPSET_STRUCTURAL), ids=ids)
        records.append(rec)
        corr[slot] = int(rec.elem_id)
        n += 1
    notes.append(f"property sets: {n} {want_kind} assets <- residue_b's ORIGINAL constructor "
                 f"(the D1 int-param swap present) -- DIAGNOSTIC bisection probe")
    return n


def build_pal_v2(ctx, landed: Dict[int, Any]):
    """Z_palette_v2: the WHOLE corrected palette bucket -- 10 materials (the
    certified constructor) + 17 structural + 11 thermal assets (corrected)."""
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    traces: List[dict] = []
    nm = _materials(ctx, landed, records, corr, notes)
    ns, nt = _propsets_v2(ctx, landed, records, corr, notes, traces)
    return _substbuild(ctx, corr, records, notes,
                       {"materials": nm, "structural_v2": ns, "thermal_v2": nt,
                        "revalue_traces": traces})


def build_pal_mat(ctx, landed: Dict[int, Any]):
    """P_pal_mat: ONLY the 10 material substitutions (residue_b's original =
    the certified types.new_material).  Predicted PASS (D3)."""
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    nm = _materials(ctx, landed, records, corr, notes)
    return _substbuild(ctx, corr, records, notes, {"materials": nm})


def build_pal_struct(ctx, landed: Dict[int, Any]):
    """P_pal_struct: ONLY the 17 structural assets, residue_b's ORIGINAL
    (swapped) constructor.  Predicted FAIL (D1) -- names the sub-class."""
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    n = _propsets_original(ctx, landed, records, corr, notes, want_kind="structural")
    return _substbuild(ctx, corr, records, notes, {"structural_original": n})


def build_pal_thermal(ctx, landed: Dict[int, Any]):
    """P_pal_thermal: ONLY the 11 thermal assets, residue_b's ORIGINAL
    (swapped) constructor.  Predicted FAIL (D1) -- names the sub-class."""
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    n = _propsets_original(ctx, landed, records, corr, notes, want_kind="thermal")
    return _substbuild(ctx, corr, records, notes, {"thermal_original": n})


def build_pal_struct_v2(ctx, landed: Dict[int, Any]):
    """P_pal_struct_v2: ONLY the 17 CORRECTED structural assets.  Predicted PASS."""
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    traces: List[dict] = []
    n, _ = _propsets_v2(ctx, landed, records, corr, notes, traces, want_kind="structural")
    return _substbuild(ctx, corr, records, notes, {"structural_v2": n, "revalue_traces": traces})


def build_pal_thermal_v2(ctx, landed: Dict[int, Any]):
    """P_pal_thermal_v2: ONLY the 11 CORRECTED thermal assets.  Predicted PASS."""
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    traces: List[dict] = []
    _, n = _propsets_v2(ctx, landed, records, corr, notes, traces, want_kind="thermal")
    return _substbuild(ctx, corr, records, notes, {"thermal_v2": n, "revalue_traces": traces})


def build_pal_swapfix(ctx, landed: Dict[int, Any]):
    """P_pal_swapfix: ZB5's EXACT 38 objects (materials + residue_b's original
    structural / thermal assets) with ONLY the D1 int-param keying corrected
    -- every OTHER residue-B choice KEPT (descending order, null ElementId set,
    legacy shape on modern slots, 6-string thermal, source 'GEN').  The
    swap-alone ISOLATE: if THIS passes, D1 alone was the whole defect and the
    remaining shape corrections in v2 were belt-and-braces."""
    corr: Dict[int, int] = {}
    records: List[Any] = []
    notes: List[str] = []
    _materials(ctx, landed, records, corr, notes)
    ids = RB._new_ids(ctx)
    fixed = 0
    n = 0
    for slot, kind, spec in propertyset_pairs(ctx, landed):
        if kind == "thermal":
            rec = RB.thermal_asset(spec, ids=ids)
        else:
            v = ctx.value(slot) or {}
            pst = int(v.get("m_propertySetType", 0) or 0)
            rec = RB.structural_asset(spec, property_set_type=(pst or PROPSET_STRUCTURAL), ids=ids)
        fixed += unswap_int_params(rec.obj)                     # ONLY the keying is corrected
        records.append(rec)
        corr[slot] = int(rec.elem_id)
        n += 1
    notes.append(f"property sets: {n} = residue_b's ORIGINAL objects with ONLY the int-param "
                 f"keying corrected ({fixed} entries un-swapped) -- the D1 swap-ALONE isolate")
    return _substbuild(ctx, corr, records, notes,
                       {"materials": 10, "propsets_swapfixed": n, "int_entries_unswapped": fixed})


# ===========================================================================
# 6. THE PROBE TABLE + DRIVER (Y9-based single-change probes; ZBRung engine)
# ===========================================================================
DEFAULT_BASE = RB.DEFAULT_PARENT            # experiments/genesis/subst_k4/Y9.rvt (certified)

PAL_PROBES: List[RB.ZBRung] = [
    RB.ZBRung(
        "Z_palette_v2",
        "the WHOLE corrected palette bucket (10 materials + 17 structural + 11 thermal assets)",
        build_pal_v2, parent="BASE",
        description=("The palette bucket re-authored: the surplus materials via the certified "
                     "types.new_material; every PropertySetElement re-valued over its slot's OWN "
                     "skeleton with OUR published constants -- int params correctly keyed (the "
                     "D1 swap FIXED), corpus ascending param order + present-empty ElementId "
                     "set (D2), the correct asset-class enum, house library GUID, no Autodesk "
                     "source token."),
        tests="Whether the CORRECTED palette bucket loads -- the one defective Group-B bucket fixed.",
        if_pass=("The palette constructor defect is CLOSED: all eight Group-B buckets are ours; "
                 "Y9 + ZA_deep + ZB(7 clean + palette-fixed) compose into the ZAB deep file."),
        if_fail=("Read the singles: P_pal_mat (materials), P_pal_struct / P_pal_thermal "
                 "(original, swapped), P_pal_struct_v2 / P_pal_thermal_v2 (corrected), "
                 "P_pal_swapfix (swap-alone) -- they bisect materials vs structural vs thermal "
                 "and separate the D1 swap from the shape corrections.")),
    RB.ZBRung(
        "P_pal_mat", "ONLY the 10 SURPLUS materials (the certified types.new_material)",
        build_pal_mat, parent="BASE",
        description=("Bisection A: the 10 surplus materials alone <- our extended palette. The "
                     "constructor is the one Y7 landed on 13 slots that ALL carried appearance "
                     "assets + shared-asset links (Y9 certified) -- D3 predicts PASS."),
        tests="Whether the material sub-class of the palette bucket is clean (predicted YES).",
        if_pass="The MaterialElem sub-class is exonerated (as the K4/Y7 control history predicts).",
        if_fail=("Contradicts the Y7/Y9 exoneration: diff a surplus slot's referrers vs an "
                 "active slot's -- the surplus slots' registration context is then the variable.")),
    RB.ZBRung(
        "P_pal_struct", "ONLY the 17 STRUCTURAL assets -- residue_b's ORIGINAL (swapped) constructor",
        build_pal_struct, parent="BASE",
        description=("Bisection B: ZB5's exact structural-asset objects (the D1 int-param swap "
                     "present: m_paramId = 3/0, m_value = -1150464/-1140322) -- predicted FAIL."),
        tests="Whether the structural-asset sub-class carries the defect (predicted YES, D1).",
        if_pass="The structural sub-class is NOT the killer -- read P_pal_thermal.",
        if_fail="The structural assets are convicted; P_pal_struct_v2 proves the fix."),
    RB.ZBRung(
        "P_pal_thermal", "ONLY the 11 THERMAL assets -- residue_b's ORIGINAL (swapped) constructor",
        build_pal_thermal, parent="BASE",
        description=("Bisection C: ZB5's exact thermal-asset objects (the D1 swap present: "
                     "m_paramId = 1/0/3/0, m_value = the built-in ids) -- predicted FAIL."),
        tests="Whether the thermal-asset sub-class carries the defect (predicted YES, D1).",
        if_pass="The thermal sub-class is NOT the killer -- read P_pal_struct.",
        if_fail="The thermal assets are convicted; P_pal_thermal_v2 proves the fix."),
    RB.ZBRung(
        "P_pal_swapfix",
        "ZB5's EXACT 38 objects with ONLY the int-param keying corrected (the swap-ALONE isolate)",
        build_pal_swapfix, parent="BASE",
        description=("ZB5 reproduced object-for-object EXCEPT the D1 int-param swap is undone; the "
                     "descending param order, the null ElementId set, the legacy shape on modern "
                     "slots, the 6-string thermal asset and source 'GEN' are all KEPT."),
        tests=("Whether the int-param swap ALONE was the whole defect (PASS) or the shape "
               "corrections in v2 are also load-bearing (FAIL)."),
        if_pass=("D1 (the swapped int params) is the ENTIRE defect; residue-B's other shape "
                 "deviations (descending order, null ElementId set, legacy-on-modern, dropped "
                 "-1152337, source 'GEN') are all reader-tolerated."),
        if_fail=("D1 is necessary but not sufficient -- one of D2's shape corrections carried by "
                 "Z_palette_v2 (order / ElementId set / shape fidelity) is also load-bearing.")),
    RB.ZBRung(
        "P_pal_struct_v2", "ONLY the 17 CORRECTED structural assets",
        build_pal_struct_v2, parent="BASE",
        description="Bisection B corrected: the structural sub-class re-valued over its slots' skeletons.",
        tests="Whether the corrected structural constructor loads.",
        if_pass="The corrected structural-asset constructor is reader-accepted.",
        if_fail=("A structural-asset shape issue survives the D1 fix -- diff a modern slot "
                 "(174481) and a legacy slot (194585) of P_pal_struct_v2 vs Y9 field by field.")),
    RB.ZBRung(
        "P_pal_thermal_v2", "ONLY the 11 CORRECTED thermal assets",
        build_pal_thermal_v2, parent="BASE",
        description="Bisection C corrected: the thermal sub-class re-valued over its slots' skeletons.",
        tests="Whether the corrected thermal constructor loads.",
        if_pass="The corrected thermal-asset constructor is reader-accepted.",
        if_fail=("A thermal-asset shape issue survives the D1 fix -- diff slot 174516 of "
                 "P_pal_thermal_v2 vs Y9 field by field.")),
]
PAL_BY_NAME = {r.name: r for r in PAL_PROBES}
#: predicted verdicts (the diagnosis's falsifiable claims)
PREDICTED_VERDICTS: Dict[str, str] = {
    "Z_palette_v2": "PASS", "P_pal_mat": "PASS", "P_pal_struct": "FAIL",
    "P_pal_thermal": "FAIL", "P_pal_swapfix": "PASS (if D1 alone was the whole defect)",
    "P_pal_struct_v2": "PASS", "P_pal_thermal_v2": "PASS",
}


def _relp(p: str) -> str:
    return os.path.relpath(p, ROOT)


def build_probes(out_dir: str = OUT_DIR, *, base: str = DEFAULT_BASE,
                 only: Sequence[str] = ()) -> Dict[str, str]:
    """Build the palette-fix probe set: the certified control + every probe
    (each = Y9 + one substitution set, in place) + probes.json.  Returns
    {probe: local verdict}."""
    V3 = RB._v3()
    os.makedirs(out_dir, exist_ok=True)
    base = os.path.abspath(base)
    cert = V3.certification_of(base)
    if cert is None:
        raise RuntimeError(f"{_relp(base)} is not viewer-CERTIFIED; the palette fix needs a "
                           f"certified base (Y9)")
    log(f"[base] {_relp(base)} -- CERTIFIED: {cert.get('proves', '')[:110]}")
    control = RB.stage_control(base, out_dir)
    log(f"[control] staged {control['file']} (md5 {control['md5']}) -- upload with the batch")
    verdicts: Dict[str, str] = {}
    want = set(only)
    for rung in PAL_PROBES:
        if want and rung.name not in want:
            continue
        try:
            rep = RB.zb_substitute_inplace(rung, base, out_dir=out_dir, base_path=base,
                                           control=control)
            verdicts[rung.name] = rep.get("verdict", "?")
        except Exception as ex:                                       # a probe that cannot build is a FINDING
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
    write_probes_manifest(out_dir, base, control, verdicts)
    log("\n=== PALETTE-FIX PROBE SUMMARY ===")
    for k in [r.name for r in PAL_PROBES]:
        if k in verdicts:
            log(f"  {k:<18} {verdicts[k]:<10} predicted {PREDICTED_VERDICTS.get(k, '?')}")
    return verdicts


def write_probes_manifest(out_dir: str, base: str, control: dict,
                          verdicts: Dict[str, str]) -> str:
    """probes.json for the palette-fix batch: bisection-first upload order,
    every entry naming its CERTIFIED base (Y9) + the control + its predicted
    verdict."""
    V3 = RB._v3()
    base_cert = V3.certification_of(base)
    entries: List[dict] = []
    for name in [r.name for r in PAL_PROBES]:
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
        rung = PAL_BY_NAME[name]
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        plan = rep.get("plan") or {}
        entries.append({
            "order": len(entries) + 1, "probe": name,
            "file": os.path.join(_relp(out_dir), f"{name}.rvt"),
            "layer_substituted": rung.label,
            "base": {"file": _relp(base), "certification": base_cert},
            "derived_from": _relp(base),
            "the_ONE_thing_it_tests": rung.tests,
            "predicted_verdict": PREDICTED_VERDICTS.get(name),
            "if_PASS": rung.if_pass, "if_FAIL": rung.if_fail,
            "elements_substituted_in_place": {"landed": plan.get("landed"),
                                              "by_class": plan.get("landed_by_class"),
                                              "by_match": plan.get("by_match")},
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
        })
    manifest = {
        "stream": "genesis-palette-fix (THE ONE NAMED CONSTRUCTOR DEFECT: Group B's PALETTE bucket)",
        "situation": ("Batch 17 (VERDICTS #19): Z_palette (Y9 + ONLY the palette bucket) FAILS "
                      "Autodesk's reader while the six sibling Group-B buckets PASS; ZB_deep (all "
                      "eight) translates PARTIALLY (view tree built, then the extractor dies). "
                      "This batch carries the DIAGNOSIS (docs/inbox/genesis-palette-fix.md) as "
                      "falsifiable probes plus the FIX."),
        "diagnosis": {
            "D1_primary_certain": ("residue_b._int_param_set swaps m_paramId and m_value: our "
                                   "structural/thermal assets carry m_paramId = 3/0/1 (POSITIVE) "
                                   "with m_value = the built-in ids -- positive param ids read as "
                                   "ParameterElement ElementIds (0/1/3 = document-birth "
                                   "singletons); confined to the two palette constructors (no "
                                   "passing bucket uses _int_param_set)."),
            "D2_corpus_invariants": ("(a) every corpus param set is ASCENDING (300/300) -- ours "
                                     "descending; (b) m_pElementIdParams is present-empty in all "
                                     "16 shapes -- ours null; (c) -1150464 is the asset-class "
                                     "enum -- ours 3 everywhere (concrete shipped as Metal)."),
            "D3_exonerated": ("MaterialElem: types.new_material = the constructor Y7 landed on "
                              "K4's 13 active slots (all with appearance assets + 8 with shared-"
                              "asset links); Y9 with those 13 is certified -- the identical "
                              "surgery on the 10 surplus slots is proven."),
        },
        "the_operation": ("In-place substitution (rvt.regadd.substitute_elements): seq-102 only; "
                          "Global/Latest + Global/ElemTable BYTE-IDENTICAL to Y9; the Y-ladder's "
                          "landed slots protected; nothing added or deleted."),
        "base": {"file": _relp(base), "certification": base_cert},
        "standing_control": control,
        "controls_discipline": ("Read the CONTROL first: if it fails the round is VOID. Only with "
                                "the control PASSING are probe verdicts read."),
        "upload_order_bisection_first": [e["probe"] for e in entries],
        "reading_the_results": {
            "Z_palette_v2": ("The deliverable. PASS = the palette defect is closed and the seven "
                             "singles are corroboration; FAIL = read the singles."),
            "P_pal_mat / P_pal_struct / P_pal_thermal": ("The diagnostic BISECTION (materials = "
                                                        "certified constructor; struct/thermal = "
                                                        "ORIGINAL swapped constructors). Predicted "
                                                        "PASS / FAIL / FAIL -- naming the two "
                                                        "PropertySetElement constructors."),
            "P_pal_swapfix": ("The swap-ALONE isolate: PASS = D1 was the entire defect; FAIL = a D2 "
                              "shape correction carried by Z_palette_v2 is also load-bearing."),
            "P_pal_struct_v2 / P_pal_thermal_v2": ("The two corrected constructors alone -- each "
                                                    "PASS proves that constructor independently of "
                                                    "the other and of the materials."),
        },
        "predicted_verdicts": PREDICTED_VERDICTS,
        "verdicts_local_self_checks": verdicts,
        "probes": entries,
        "record": "docs/inbox/genesis-palette-fix.md",
        "residue_b_diff": "docs/inbox/genesis-palette-fix.md ## The residue_b.py diff",
    }
    p = os.path.join(out_dir, "probes.json")
    os.makedirs(out_dir, exist_ok=True)
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"[probes] wrote {_relp(p)} ({len(entries)} entries)")
    return p


# ===========================================================================
# 7. THE DIAGNOSTIC INSTRUMENTS (reproduce the evidence from the record)
# ===========================================================================

def diagnose_zb5(zb5_rvt: str = os.path.join(RB.ZB_OUT_DIR, "ZB5_palette.rvt")) -> dict:
    """Scan the FAILING ZB5_palette.rvt (as emitted) and count the D1 swap
    signature + the D2 order / ElementId-set violations on every landed
    PropertySetElement -- the on-disk proof of the diagnosis."""
    from ..mutate import Document
    doc = Document.from_file(zb5_rvt)
    rows = []
    n_swap = n_desc = n_null_eid = 0
    landed = set()
    try:
        with open(ZB5_REPORT) as fh:
            rep = json.load(fh)
        landed = {int(r["slot"]) for r in rep.get("landed_slots", []) if r.get("class") == "PropertySetElement"}
    except Exception:
        landed = set(doc.ids_of_class("PropertySetElement"))
    for eid in sorted(landed):
        v = doc.value(eid) or {}
        sw = swapped_int_entries(v)
        asc = param_ids_ascending(v)
        ps = ((v.get("m_oParamSet") or {}).get("value") or {})
        eid_set = ps.get("m_pElementIdParams") is not None
        n_swap += len(sw)
        n_desc += 0 if all(asc.values()) else 1
        n_null_eid += 0 if eid_set else 1
        rows.append({"slot": eid, "type": v.get("m_propertySetType"),
                     "swapped_int_entries": sw, "ascending": asc,
                     "elementid_set_present": eid_set})
    return {"file": _relp(zb5_rvt), "landed_propertysets": len(landed),
            "swapped_int_param_entries_total": n_swap,
            "objects_with_a_swapped_int": sum(1 for r in rows if r["swapped_int_entries"]),
            "objects_with_a_descending_container": n_desc,
            "objects_with_null_ElementId_set": n_null_eid, "rows": rows}


# ===========================================================================
# 8. CLI
# ===========================================================================

def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="genesis-palette-fix: the corrected palette bucket + "
                                             "the diagnostic bisection probes off certified Y9")
    ap.add_argument("--base", default=DEFAULT_BASE, help="the CERTIFIED base (default Y9.rvt)")
    ap.add_argument("--out-dir", default=OUT_DIR)
    ap.add_argument("--only", default="", help="comma list of probes to build")
    ap.add_argument("--diagnose", action="store_true", help="print the ZB5 on-disk diagnosis and exit")
    args = ap.parse_args(argv)
    if args.diagnose:
        d = diagnose_zb5()
        print(json.dumps({k: v for k, v in d.items() if k != "rows"}, indent=1))
        for r in d["rows"][:8]:
            print(json.dumps(r, default=str))
        return 0
    only = [s.strip() for s in args.only.split(",") if s.strip()]
    verdicts = build_probes(os.path.abspath(args.out_dir), base=os.path.abspath(args.base), only=only)
    bad = [k for k, v in verdicts.items() if v != "VALID"]
    return 0 if not bad else 1


if __name__ == "__main__":                                        # pragma: no cover
    sys.exit(main())

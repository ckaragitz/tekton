"""genesis/residue_a.py -- RESIDUE CONSTRUCTORS, GROUP A: the datum /
annotation / type-layer buckets of the Yn residue census, as OUR
constructors + the in-place Z-rungs that substitute them into the certified
Y9 file.

THE SITUATION (docs/inbox/genesis-rebase.md + genesis-audit.md verdict #17).
The substitution ladder REBASED on the CERTIFIED family-free base K4 as PURE
IN-PLACE substitution took K4 to Y9 -- the settings layer + the 1,407-row
built-in category/GStyle catalog + palette + datum (levels / phases) + view
constellations are ALL our constructors' output at Autodesk's own ids -- and
Y9, Y1 (pen table) and Y_cat (catalog) all LOAD in Autodesk's reader.  The
census of Y9 (``experiments/genesis/subst_k4/Yn.json``): 1,333 of K4's
3,342 host elements are OURS; the RESIDUE = 2,009 elements in 11 named
buckets is the honest queue to zero Autodesk-authored elements.

GROUP A / GROUP B SPLIT (the coordination contract, recorded in
``docs/inbox/genesis-residue-A.md`` before construction began): the residue
CLASSES whose names sort A..L are Group A's, M..Z are Group B's, inside the
families each charter names.  Group A's families = subcategory (the X6b gap),
annotation-attribute types + fonts, datum content + level surplus, the
pattern surplus, the material companions (appearance assets), plus the
honest census of the curtain-SYSTEM constellation (no in-place rung -- a
coherent-REMOVAL rung's business, stated below).

WHAT THIS MODULE PROVIDES
  1. CENSUS MACHINERY -- :func:`ladder_landed` (which slots the Y-ladder made
     ours), :func:`residue_by_class` (the K4-inherited residue of a file per
     class = Yn's queue), :func:`split_family_scoped` (project vs curtain-
     family-scoped rows), :func:`curtain_constellation` (the exact coherent-
     removal set of the 8 curtain SYSTEM families + everything m_famId-scoped
     to them), :func:`derive_generic_asset_profile` (the Protein GenericSchema
     appearance-asset PROPERTY SKELETON mined once from the corpus and frozen
     -- the property names / types / library GUIDs are format constants; the
     colour / gloss / description are ours).
  2. OUR DATA -- the house SUBCATEGORY VOCABULARY per built-in parent category
     (a firm's own object sub-category / line-style naming), OUR annotation
     standard (grid head / interior-elevation marker / callout head /
     arrowheads / dimension text sizes / font), OUR datum vocabulary (surplus
     level names), OUR grid convention, OUR extra drafting patterns, OUR
     generic appearance colours.  Every value below is either a caller
     parameter, one of these house tables, a documented format constant, or
     a sentinel -- never a value copied from an Autodesk file.
  3. CONSTRUCTORS -- one per claimed class.  Two shapes:
       * PURE constructors (schema blank + our values + mined constants):
         subcategory pairs (via ``types.new_category`` / ``new_gstyle``),
         :func:`font_elem`, :func:`arrowhead_type`, :func:`grid_head_type`,
         :func:`interior_elevation_type`, :func:`callout_head_type`,
         :func:`new_grid` (datum content: a straight grid line, the twin of
         ``skeleton.new_level``), :func:`generic_appearance_asset`, the level
         surplus (``skeleton.new_level``), the extra house patterns
         (``types.new_line_pattern`` / ``new_fill_pattern``).
       * IN-PLACE builders (``inplace_<class>(slot_value, ...)``): OUR
         constructor's object WIRED to the slot's own document ids and
         shaped by the slot's per-row STRUCTURAL PROFILE (the cells /
         design-option / header flag apparatus the catalog fixer v2 proved is
         a compiled-in per-row property) -- returns the seq-102 object that
         replaces the slot's, plus a FIELD DELTA (which fields carry OUR value
         vs the slot's) so every rung report says exactly what is ours.  For
         ``DimensionStyle`` (60+ fields of unit-format machinery) only the
         in-place overlay form exists and the report SAYS SO.
  4. THE Z-LADDER (:func:`run_ladder`, ``python -m rvt.genesis.residue_a``):
     from the CERTIFIED Y9, each claimed bucket as ONE in-place rung derived
     directly from Y9 (single-change probes) + the cumulative ZA_deep:
        Z_subcat  -- the project SUBCATEGORY layer (CategoryElem + its GStyle
                     rows; the X6b GAP the whole program has named)
        Z_annot   -- the project annotation-attribute types (secret internal
                     dimension styles + arrowheads, grid head, interior-
                     elevation marker, callout head) + EVERY project FontElem
        Z_datum   -- the 3 grids -> our grids + the 7 plan-less surplus
                     levels -> our datum vocabulary
        Z_pattern -- the 4 fill + 3 line SURPLUS patterns -> our extra
                     house patterns
        Z_asset   -- the 18 material AppearanceAssetElem companions -> our
                     generic appearance assets
        ZA_deep   -- Y9 + ALL of the above in place (bisection-first upload)
     Every rung = ``rvt.regadd.substitute_elements`` (seq-102 object only,
     keep_row, Global/Latest + Global/ElemTable byte-identical, nothing added
     or deleted) certified exactly like the Y-ladder (validator 0 errors,
     structural proof, four-registry coherence, registry parity, a
     ``rvt.regdiff`` sample, the byte-delta-vs-parent assertion table) via
     ``tools/genesis_substitute_v3.py``'s own certification helpers, plus a
     per-class FIELD-DELTA table (our fields vs the slot's).  probes.json is
     written ZA_deep first (bisection), then the singles.

WHAT CANNOT BE SUBSTITUTED IN PLACE (stated, not silently skipped -- see
:data:`NON_INPLACE` and the record):
  * the 8 curtain-SYSTEM FAMILIES ('Rectangular Mullion', 'System Panel', ...)
    + everything m_famId-scoped to them (72 family-editor DBViewTypes, 40+40
    subcategory rows, 24 fonts, 8+8+8 attribute types, 8 pen tables, 8
    surrogates ...): Autodesk's compiled-in curtain machinery -- nothing of
    ours to express; the honest rung is COHERENT REMOVAL (K4's certified
    family-removal operation), whose exact id set :func:`curtain_constellation`
    computes;
  * placed CONTENT constellations: the room boundary loop (5 CurveElem +
    LevelRoomPlan + the room, an area scheme's plan topology), 4
    LegendComponents (type graphics in a legend, referencing wall / floor /
    curtain types), 1 LinearDimString (a locked EQ CONSTRAINT dimension tying
    three reference planes, category OST_Constraints) -- content removal
    rungs (they leave with the elements they annotate / bound), no
    constructor value.

Territory: this module, ``tests/test_residue_a.py``,
``experiments/genesis/subst_k4/residue_a/*``, ``docs/inbox/genesis-residue-A.md``.
Every dependency (``rvt.genesis.{types,house_standard,catalog,skeleton}``,
``rvt.regadd`` / ``rvt.regdiff`` / ``rvt.mutate``, and the CERTIFICATION
helpers of ``tools/genesis_substitute_v3.py`` / ``tools/genesis_substitute
.py``) is IMPORTED, never edited.  Python: ``.venv/bin/python`` from the
repo root::

    .venv/bin/python -m rvt.genesis.residue_a                 # census + whole Z-ladder
    .venv/bin/python -m rvt.genesis.residue_a --only Z_pattern,Z_datum
    .venv/bin/python -m rvt.genesis.residue_a --census-only   # residue census only
    .venv/bin/python -m rvt.genesis.residue_a --demo          # constructors round-trip
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
import random
import sys
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .types import (TypeRecord, IdArg, IdSource, INVALID, LINEPATTERN_SOLID, NULL_GUID,
                    NO_DESIGN_OPTION, INTERNAL_DESIGN_OPTION, OST_TextNoteLineStyle,
                    blank_object, element_defaults, symbol_defaults, class_id,
                    _owned, _ptr, _record, _alloc, mm, rgb,
                    new_category, new_gstyle, new_line_pattern, new_fill_pattern)
from . import house_standard as hs

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
#: this stream's territory + the certified parent of every Z rung
RESIDUE_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4", "residue_a")
LADDER_DIR = os.path.join(ROOT, "experiments", "genesis", "subst_k4")
DEFAULT_PARENT = os.path.join(LADDER_DIR, "Y9.rvt")               # CERTIFIED (viewer PASS)
CTRL_K4 = os.path.join(LADDER_DIR, "CTRL_K4_base.rvt")             # the batch's standing control
GENERIC_ASSET_PROFILE = os.path.join(RESIDUE_DIR, "generic_asset_profile.json")
INVARIANTS_DIR = os.path.join(RESIDUE_DIR, "invariants")            # mined by this stream
LEDGER_MD = os.path.join(ROOT, "docs", "inbox", "genesis-residue-A.md")

#: the Y-ladder's cumulative chain whose reports name every LANDED slot
LADDER_CHAIN = ["Y1", "Y2", "Y3", "Y4", "Y5", "Y6", "Y7", "Y8", "Y9"]

PREFIX = hs.PREFIX                      # 'GEN' -- our house name prefix
CORPUS_SAMPLES = ["rstbasicsampleproject", "rstadvancedsampleproject",
                  "racbasicsampleproject", "racadvancedsampleproject",
                  "rmebasicsampleproject", "dach-sample-project"]


def gen(name: str) -> str:
    return hs.gen(name)


def log(msg: str) -> None:
    print(msg, flush=True)


# ===========================================================================
# 0. THE CLAIM (the Group A / Group B contract -- data, so tests can pin it)
# ===========================================================================
#: rung -> the residue classes it substitutes IN PLACE (all sort A..L)
CLAIMED_CLASSES: Dict[str, List[str]] = {
    "Z_subcat": ["CategoryElem", "GStyleElem"],
    "Z_annot": ["DimensionStyle", "LeaderStyle", "GridAttributes",
                "InteriorElevAttributes", "CalloutTag", "FontElem"],
    "Z_datum": ["Grid", "Level"],
    "Z_pattern": ["FillPatternElem", "LinePatternElem"],
    "Z_asset": ["AppearanceAssetElem"],
}
#: claimed classes with NO in-place rung + the honest reason (the record's
#: "cannot be substituted in place and WHY" list)
NON_INPLACE: Dict[str, str] = {
    "DBViewType": ("all 72 residue rows are FAMILY-SCOPED (m_famId = a curtain-SYSTEM family): "
                   "the family-editor view types (Floor Plan / Ceiling Plan / Section 1 / Detail "
                   "View / Drafting View / Elevation 1 / 3D View / Schedule / Sheet x 8 families) of "
                   "Autodesk's compiled-in curtain machinery -- nothing of ours to express; the "
                   "honest rung is COHERENT REMOVAL of the curtain constellation "
                   "(curtain_constellation()), i.e. K4's certified family-removal operation"),
    "Family": ("the 8 curtain-SYSTEM families ('Rectangular Mullion', 'Circular Mullion', 'System "
               "Panel', 'Empty System Panel', 'L/V/Trapezoid/Quad Corner Mullion') are Autodesk's "
               "built-in curtain content, not authorable expression -- coherent removal, not "
               "substitution"),
    "FamilySurrogate": ("the 8 surrogates ride with their curtain SYSTEM families (coherent removal)"),
    "CurveElem": ("the 5 residue CurveElems are the ROOM/AREA-SEPARATION boundary loop of the ONE "
                  "placed room (RoomElem 1004910 + LevelRoomPlan 1004909 + AreaSchemePlanTopologies "
                  "9744) -- placed CONTENT: a room-removal rung's business (the boundary leaves "
                  "with the room), no constructor value"),
    "LevelRoomPlan": ("the plan-topology companion of the one placed room (its 5 boundary "
                      "CurveElems + AreaSchemePlanTopologies) -- placed CONTENT, removed with the room"),
    "LegendComponent": ("4 legend graphics displaying TYPES (a wall type, a floor type, two curtain "
                        "surrogates) in a legend view -- placed CONTENT referencing type layers other "
                        "streams own; removed with those / with the legend view"),
    "LinearDimString": ("ONE locked EQ-constraint dimension (category OST_Constraints -2000262, "
                        "typed by the secret internal LinAng dimension style 277) tying three "
                        "project reference planes -- CONSTRAINT CONTENT: it leaves with the "
                        "reference planes it constrains (Group B's ref-plane content rung); a "
                        "constraint's 'value' is the geometry it constrains -- nothing of ours"),
    "AppearanceAssetElem": ("(has a constructor + a rung -- listed here only for the "
                            "family-scoped remainder: none)"),
}
#: the M..Z counterparts left to GROUP B (recorded, not touched)
GROUP_B_CLASSES: List[str] = [
    "MaterialElem", "PenWidthTableElem", "SlaveSymbolTrackerElem", "SectionAttributes",
    "ViewportAttributes", "SketchPlane", "RefPlane", "RoomElem", "SunAnnotationElem", "Viewer",
    "Viewport", "WorksharingViewModeSettings", "PrintSettings", "ParamElemExternal",
    "ParamBinding", "ParamElemElectricalLoadClassification", "ParamElemProject",
    "ParameterFilterElement", "NumberingSchema", "PropertySetElement", "PipeSegment",
]

# ---------------------------------------------------------------------------
# format constants (BuiltInCategory / BuiltInParameter ids -- Autodesk's
# fixed public enums: interoperability constants, not content)
# ---------------------------------------------------------------------------
OST_Doors = -2000023
OST_Windows = -2000014
OST_Furniture = -2000080
OST_GenericModel = -2000151
OST_GenericAnnotation = -2000150
OST_Lines = -2000051
OST_DetailComponents = -2002000
OST_Site = -2001260
OST_Parking = -2001180
OST_Entourage = -2001370
OST_PlumbingFixtures = -2001160
OST_SpecialityEquipment = -2001350
OST_StructuralFraming = -2001320
OST_StructuralColumns = -2001330
OST_StructuralFoundation = -2001300
OST_StructConnections = -2009030            # 'Weld' subcategory's parent [INFERRED band]
OST_Rebar = -2009000                        # rebar band (-2009005 / -2009010 cover rows)
OST_Grids = -2000220                        # Grid element category (verified: grid header)
OST_LevelsInternal = -2000240               # Level category
OST_ElevMarkers = -2000195                  # [INFERRED] interior elevation marker head
OST_Callouts = -2000538                     # callout heads
OST_Constraints = -2000262                  # the LinearDimString's category (locked EQ dim)
#: LeaderStyle (arrowhead) parameters [ids verified 2048/1024 corpus arrowheads]
BIP_ARROW_ANGLE = -1006414                  # arrowhead angle (radians; RANGE 0..pi/2)
BIP_ARROW_SIZE = -1006426                   # tick / arrow size (feet)
BIP_ARROW_WIDTH_PEN = -1006447              # arrow width pen (int, 1 on 961/1024)
#: dimension-style double parameters (the 11-entry set of every LINEAR style;
#: ids verified on all 120 corpus DimensionStyles).  Meanings [INFERRED from the
#: public BuiltInParameter enum + magnitudes]: TEXT_SIZE, text offset from the
#: line, witness-line extension / offset / gap, line extension, width factor.
BIP_TEXT_SIZE = -1006404                    # dimension text height (feet)
BIP_DIM_TEXT_OFFSET = -1006407              # text distance to the dimension line
BIP_DIM_WITNS_EXTENSION = -1006405          # witness line extension beyond the dim line
BIP_DIM_WITNS_OFFSET = -1006401             # witness line gap to the element
BIP_DIM_LINE_EXTENSION = -1006431           # dim line extension past the witness line
BIP_DIM_TICK_SIZE = -1006433                # tick size / centreline symbol size
BIP_TEXT_WIDTH_SCALE = -1006327             # text width factor (1.0)
BIP_DIM_LEADER = -1006465                   # leader-related (0.0 in every corpus style)
BIP_DIM_ALT_A, BIP_DIM_ALT_B, BIP_DIM_ALT_C = -1006311, -1006312, -1006313   # alternate-units zeros
BIP_DIM_LEADER_ARROWHEAD = -1006430         # ElementId param: leader arrowhead (-> LeaderStyle)
#: FontElem colour sentinel: 0x1000000 (one past the 24-bit RGB range) is the
#: format's 'black' token carried by 24 of every 30 corpus fonts -- our text
#: colour choice (black) is encoded with it, like the corpus does.
FONT_COLOR_BLACK = 0x1000000

#: which host classes we treat as annotation TYPES whose owned line-style
#: sub-category / font ride with the type (the constellation)
ANNOTATION_TYPE_CLASSES = {"DimensionStyle", "LeaderStyle", "GridAttributes",
                           "InteriorElevAttributes", "CalloutTag"}


# ===========================================================================
# 1. CENSUS MACHINERY
# ===========================================================================

def ladder_landed(ladder_dir: str = LADDER_DIR,
                  chain: Sequence[str] = tuple(LADDER_CHAIN),
                  extra_reports: Sequence[str] = ()) -> Dict[int, str]:
    """{slot: rung} of every element the (cumulative) Y-ladder LANDED an
    our-object in, read from the rung reports (``<rung>.json`` 'landed_slots').
    ``extra_reports`` = additional report paths (a cumulative Z rung)."""
    out: Dict[int, str] = {}
    paths = [os.path.join(ladder_dir, f"{n}.json") for n in chain] + list(extra_reports)
    for p in paths:
        if not os.path.exists(p):
            continue
        try:
            with open(p) as fh:
                rep = json.load(fh)
        except Exception:
            continue
        for row in rep.get("landed_slots") or []:
            out.setdefault(int(row["slot"]), rep.get("rung") or os.path.basename(p)[:-5])
    return out


def residue_by_class(doc, landed: Dict[int, str],
                     classes: Optional[Iterable[str]] = None) -> Dict[str, List[int]]:
    """The K4-inherited RESIDUE of a ``mutate.Document``: every host element
    whose id is NOT in ``landed``, grouped by class (Yn's own definition).
    ``classes`` restricts the answer (None = all residue classes)."""
    want = set(classes) if classes else None
    out: Dict[str, List[int]] = collections.defaultdict(list)
    for e in doc.et_by_id:
        eid = int(e)
        if eid in landed:
            continue
        cls_name = doc.class_of(eid) or "?"
        if want is not None and cls_name not in want:
            continue
        out[cls_name].append(eid)
    return {k: sorted(v) for k, v in out.items()}


def _fam_id(value: dict) -> int:
    try:
        return int((value or {}).get("m_famId", INVALID))
    except Exception:
        return INVALID


def split_family_scoped(doc, ids: Iterable[int]) -> Tuple[List[int], List[int]]:
    """(project ids, family-scoped ids) by ``m_famId`` (-1 = project)."""
    proj, fam = [], []
    for e in ids:
        (fam if _fam_id(doc.value(int(e))) not in (INVALID, None) else proj).append(int(e))
    return sorted(proj), sorted(fam)


def curtain_constellation(state: dict) -> dict:
    """The EXACT coherent-removal set of the curtain-SYSTEM families of a
    parent file (an ``rvt_reduce.build_state_v2`` state): the ``Family``
    elements + every host element ``m_famId``-scoped to them (their family-
    editor DBViewTypes, family pen tables / attribute types / fonts /
    sub-category rows) + their ``FamilySurrogate``s and slave-symbol trackers
    (found through the typed reference graph).  Returns {family_id: {...}}
    + the flat id set -- the removal queue this stream hands over (NOT an
    in-place substitution: :data:`NON_INPLACE`)."""
    doc = state["doc"]
    cls_of = state["cls_of"]
    refs = state["referrers"]                                    # target -> {referrers}
    graph = state["graph"]                                       # source -> {targets}
    families = [int(e) for e in state["host"] if cls_of.get(int(e)) == "Family"]
    fam_set = set(families)
    per_family: Dict[int, Dict[str, List[int]]] = {
        f: collections.defaultdict(list) for f in families}
    scoped_all: Set[int] = set(families)
    for e in state["host"]:
        eid = int(e)
        fid = _fam_id(doc.value(eid))
        if fid in fam_set:
            per_family[fid][cls_of.get(eid, "?")].append(eid)
            scoped_all.add(eid)
    # surrogates / trackers reference their family but are not m_famId-scoped
    for f in families:
        for r in refs.get(f, set()):
            c = cls_of.get(int(r))
            if c in ("FamilySurrogate", "SlaveSymbolTrackerElem") and int(r) not in scoped_all:
                per_family[f][c].append(int(r))
                scoped_all.add(int(r))
    for e in state["host"]:
        if cls_of.get(int(e)) == "SlaveSymbolTrackerElem" and int(e) not in scoped_all:
            if graph.get(int(e), set()) & fam_set:
                scoped_all.add(int(e))
                for f in graph.get(int(e), set()) & fam_set:
                    per_family[f]["SlaveSymbolTrackerElem"].append(int(e))
    names = {f: str((doc.value(f) or {}).get("m_name") or "") for f in families}
    return {
        "families": [{"id": f, "name": names.get(f, ""),
                      "scoped_by_class": {k: sorted(v) for k, v in sorted(per_family[f].items())},
                      "count": sum(len(v) for v in per_family[f].values()) + 1}
                     for f in families],
        "removal_set": sorted(scoped_all),
        "count": len(scoped_all),
        "by_class": dict(collections.Counter(cls_of.get(int(e), "?") for e in scoped_all)),
        "note": ("coherent-removal candidate (K4's certified family-removal operation on the 8 "
                 "curtain SYSTEM families) -- NOT an in-place substitution; the removal must also "
                 "reconcile the FamilyMgr / ContentTable registries exactly as K4's did"),
    }


# ---------------------------------------------------------------------------
# 1b. the frozen GENERIC appearance-asset property PROFILE (mined once)
# ---------------------------------------------------------------------------

#: property name -> our default when the corpus has NO constant (the FREE
#: properties of the Protein GenericSchema).  Everything else is frozen from
#: the corpus census as a format constant (:func:`derive_generic_asset_profile`).
GENERIC_ASSET_OURS = {
    "UIName": None, "VersionGUID": None, "description": None, "keyword": None,
    "category": None, "thumbnail": None, "swatch": None, "generic_diffuse": None,
    "generic_glossiness": None, "generic_reflectivity_at_0deg": None,
    "generic_reflectivity_at_90deg": None, "generic_transparency": None,
    "generic_bump_amount": None, "generic_is_metal": None, "common_Tint_color": None,
    "AssetLibID": None, "version": None, "revision": None,
}


def derive_generic_asset_profile(samples: Sequence[str] = tuple(CORPUS_SAMPLES), *,
                                 verbose: bool = True) -> dict:
    """Mine the Protein ``GenericSchema`` appearance-asset PROPERTY SKELETON
    over every host ``AppearanceAssetElem`` of the corpus whose asset schema
    is 'GenericSchema' (400 specimens on the six 2026 samples): for each
    property its ordinal position, its ``APropertyXxx`` class and, when EVERY
    specimen agrees, its CONSTANT value (library ids, UI xml paths, the
    'materialappearance' asset type, the ambient-occlusion machinery ...).
    Properties whose value varies (colour, gloss, name, description, ...) are
    recorded WITHOUT a value: they are the free properties OUR constructor
    fills (:data:`GENERIC_ASSET_OURS`).  The property NAME SET + order + types
    are the schema constant (a Protein library interface), like the built-in
    category enum -- enumerating them copies no authored value."""
    from ..mutate import Document
    order: Dict[str, List[int]] = collections.defaultdict(list)
    types: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    values: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    present: collections.Counter = collections.Counter()
    top_level: collections.Counter = collections.Counter()
    n = 0
    for s in samples:
        doc = Document.load(s)
        for e in doc.ids_of_class("AppearanceAssetElem", host_only=True):
            v = doc.value(int(e)) or {}
            a = ((v.get("m_pAppearanceAsset") or {}).get("value") or {})
            asset = a.get("m_Asset") or {}
            if asset.get("m_sName") != "GenericSchema":
                continue
            n += 1
            for k in a:
                top_level[k] += 1
            for k in asset:
                top_level["m_Asset." + k] += 1
            for i, p in enumerate(asset.get("m_aAProperties") or []):
                pv = p.get("value") or {}
                name = pv.get("m_sName")
                if not name:
                    continue
                present[name] += 1
                order[name].append(i)
                types[name][p.get("ptr_class")] += 1
                values[name][json.dumps(pv.get("m_value"), sort_keys=True, default=str)] += 1
        if verbose:
            log(f"   [asset-profile] {s}: cumulative Generic assets {n}")
    props = []
    for name in sorted(present, key=lambda k: (sum(order[k]) / max(1, len(order[k])))):
        cnt = present[name]
        cls_ = types[name].most_common(1)[0][0]
        val, val_n = values[name].most_common(1)[0]
        constant = (val_n == cnt) and (cnt >= n)           # identical in EVERY specimen
        props.append({
            "name": name, "aproperty_class": cls_,
            "present_in": cnt, "of": n,
            "modal_ordinal": collections.Counter(order[name]).most_common(1)[0][0],
            "constant": bool(constant and name not in GENERIC_ASSET_OURS),
            "value": (json.loads(val) if (constant and name not in GENERIC_ASSET_OURS) else None),
            "corpus_top_value": json.loads(val), "corpus_top_share": round(val_n / cnt, 3),
        })
    prof = {
        "generator": "rvt.genesis.residue_a.derive_generic_asset_profile",
        "derived_from": list(samples), "generic_specimens": n,
        "top_level_fields": dict(top_level),
        "note": ("The Protein 'GenericSchema' appearance-asset PROPERTY SKELETON: property "
                 "names / order / APropertyXxx types, and the values that are IDENTICAL in every "
                 "one of the corpus's Generic assets (library GUIDs, UI xml paths, the asset "
                 "type token, the AO / roundcorner machinery). A per-release Protein-library "
                 "constant, like the built-in category enum. The FREE properties (name, colour, "
                 "gloss, tint, description, keyword, category, thumbnail) carry NO value here: "
                 "they are OURS at construction time."),
        "properties": props,
    }
    os.makedirs(RESIDUE_DIR, exist_ok=True)
    with open(GENERIC_ASSET_PROFILE, "w") as fh:
        json.dump(prof, fh, indent=1)
    if verbose:
        log(f"   [asset-profile] wrote {os.path.relpath(GENERIC_ASSET_PROFILE, ROOT)} "
            f"({len(props)} properties over {n} specimens)")
    return prof


def load_generic_asset_profile(path: str = GENERIC_ASSET_PROFILE, *,
                               derive_if_missing: bool = True) -> dict:
    if os.path.exists(path):
        with open(path) as fh:
            return json.load(fh)
    if not derive_if_missing:
        raise FileNotFoundError(path)
    return derive_generic_asset_profile()


# ===========================================================================
# 2. OUR DATA (Group A house standard)
# ===========================================================================
#: OUR SUB-CATEGORY VOCABULARY: a firm's own object sub-category naming per
#: built-in parent category (the layer a project template ships).  Names are
#: OURS (the house prefix + our vocabulary); a parent's list is our set for
#: that category, applied to the parent's sub-category slots IN ORDER; extra
#: sample slots beyond our list get :func:`fallback_subcategory_name`.
#: (label, [entries...]) per built-in parent OST id.
SUBCATEGORY_VOCABULARY: Dict[int, Tuple[str, List[str]]] = {
    OST_Doors: ("Door", ["Swing (Plan)", "Leaf", "Frame", "Hardware", "Threshold",
                         "Glazing", "Opening (Elevation)", "Clearance Zone"]),
    OST_Windows: ("Window", ["Glazing", "Frame / Mullion", "Sill & Trim", "Sash",
                             "Swing (Plan)", "Reveal", "Opening (Elevation)",
                             "Hardware", "Head & Jamb"]),
    OST_Furniture: ("Furn", ["2D Outline", "3D Detail", "Hidden", "Overhead", "Frame",
                             "Upholstery", "Casework Face", "Base", "Leg", "Arm",
                             "Seat", "Back", "Edge Band", "Glass Top", "Hardware",
                             "Cushion", "Clearance Zone", "Stacking Guide", "Task Chair"]),
    OST_GenericModel: ("GM", ["Detail Fine", "Detail Medium", "Detail Coarse", "Hidden",
                              "Overhead", "Centreline", "Frame 2D", "Frame 3D", "Panel 2D",
                              "Panel 3D", "Grille 2D", "Grille 3D", "Hardware 2D",
                              "Hardware 3D", "Nameplate", "Trim", "Symbolic", "Clearance",
                              "Access Zone", "Service Zone", "Coarse Massing"]),
    OST_GenericAnnotation: ("Anno", ["Thin", "Medium", "Wide", "Extra Wide", "North Arrow",
                                     "Shadow", "Screened", "Masking"]),
    OST_Lines: ("Line", ["Fine 0.13", "Thin 0.18", "Medium 0.35", "Wide 0.50", "Extra Wide 0.70",
                         "Hidden", "Centre", "Demolition", "Property Line", "Match Line",
                         "Overhead", "Setback", "Movement Joint", "Fire Rating", "Batting",
                         "Break Line", "Datum Reference", "Wetstamp Zone", "Redline"]),
    OST_DetailComponents: ("Detail", ["Heavy", "Medium", "Light", "Hidden", "Beyond",
                                     "Wide", "Screened"]),
    OST_Site: ("Site", ["Property Boundary", "Landscape", "Paving Joint", "Utilities",
                        "Building Pad", "Grading Contour", "Setback"]),
    OST_Parking: ("Parking", ["Stall Striping", "Accessible Symbol", "Wheel Stop",
                              "Aisle Marking"]),
    OST_Entourage: ("Entourage", ["People", "Vehicles", "Planting", "Furniture Ghost"]),
    OST_PlumbingFixtures: ("Plumb", ["2D Symbol", "3D Detail", "Hidden", "Clearance Zone",
                                     "Host Cut", "Rough-in", "Access Panel"]),
    OST_SpecialityEquipment: ("SpecEq", ["2D Symbol", "3D Detail", "Chassis", "Hidden",
                                         "Clearance Zone", "Service Zone"]),
    OST_StructuralFraming: ("Framing", ["Stick Symbol", "Hidden Faces", "Web / Joist",
                                        "Girder", "Rigid Link", "Location Line", "Moment Symbol",
                                        "Camber", "Cope"]),
    OST_StructuralColumns: ("StructCol", ["Hidden Faces", "Location Line", "Stick Symbol",
                                          "Rigid Link", "Baseplate"]),
    OST_StructuralFoundation: ("Fndn", ["Hidden", "Bearing Zone", "Location Line", "Rebar Zone"]),
    OST_StructConnections: ("Conn", ["Weld", "Bolt Group", "Plate", "Hidden", "Anchor"]),
}
#: OUR labels for parents beyond the vocabulary (fallback naming); anything
#: unlabelled falls back to 'Category <id>' honestly.
PARENT_LABELS: Dict[int, str] = {
    -2000059: "Annotation Line",            # the annotation-type internal line-style layer
    -2000460: "Compass",                    # north / medium / thin ceremony rows [id band]
    -2009028: "Rebar", -2009029: "Rebar", -2009005: "Rebar Cover", -2009010: "Rebar Cover",
    -2000079: "Room Separation", -2001000: "Casework", -2001040: "Elec Equipment",
    -2001060: "Elec Fixture", -2001120: "Light Fixture", -2001140: "Mech Equipment",
    -2000180: "Casework", -2000038: "Ceiling", -2000032: "Floor", -2000035: "Roof",
}
for _cid, _lab, _disc, _cut in hs.HOUSE_CATEGORIES:
    PARENT_LABELS.setdefault(int(_cid), _lab.rstrip("s") if not _lab.endswith("ss") else _lab)


def fallback_subcategory_name(parent_ost: int, index: int) -> str:
    """OUR generic name for the ``index``-th (1-based) sub-category slot of a
    parent our vocabulary does not cover (or beyond its length)."""
    label = SUBCATEGORY_VOCABULARY.get(int(parent_ost), (None, None))[0] \
        or PARENT_LABELS.get(int(parent_ost)) or f"Category {abs(int(parent_ost))}"
    return gen(f"{label} - Subcategory {int(index):02d}")


def our_subcategory_name(parent_ost: int, index: int) -> str:
    """OUR name for the ``index``-th (0-based) sub-category slot under
    ``parent_ost``: our vocabulary entry when we have one, else the honest
    numbered fallback."""
    label, entries = SUBCATEGORY_VOCABULARY.get(int(parent_ost), (None, []))
    if entries and index < len(entries):
        return gen(f"{label} - {entries[index]}")
    return fallback_subcategory_name(parent_ost, index + 1)


#: OUR pens for annotation-owned INTERNAL line-style sub-categories (the empty-
#: name ctype-4 rows an annotation type owns): dimension / leader / grid /
#: elevation / callout linework is fine annotation ink in our standard.
ANNOTATION_INTERNAL_PEN = 1
ANNOTATION_INK = 0                           # pure black annotation ink (our choice)

#: OUR annotation standard for the residue attribute types (values ours; the
#: mm sizes follow our ISO 3098-based text ladder from house_standard.TEXT_TYPES).
ANNOTATION_STANDARD: Dict[str, Any] = {
    "font": hs.TEXT_FONT,                         # 'Arial' -- our house text face
    "font_color": FONT_COLOR_BLACK,               # black (format token)
    "grid_head": {"name": gen("Grid Head - 8mm Circle"), "bubble_end1": True, "bubble_end2": True,
                  "center_segment_style": 0,      # continuous grid line
                  "end_segments_length_mm": 1200.0,   # our gapped-grid end length (unused when continuous)
                  "text_mm": 3.5},
    "interior_elevation": {"name": gen("Elevation Marker - 10mm Circle"), "shape": 1,   # circle
                           "width_mm": 10.0, "arrow_angle_deg": 45.0, "arrow_filled": True,
                           "text_position": 3, "view_name_position": 1, "reference_label_pos": 2,
                           "show_view_name": True, "text_mm": 2.5},
    "callout_head": {"name": gen("Callout Head - 2mm Radius"), "corner_radius_mm": 2.0},
    "arrowhead": {"name": gen("Arrow Filled 20 Degree"), "tick_type": 8, "arrow_filled": 1,
                  "arrow_closed": True, "arrow_centered": False, "angle_deg": 20.0,
                  "size_mm": 3.0},
    "dimension": {"text_mm": 2.5, "text_offset_mm": 1.0, "witness_extension_mm": 2.0,
                  "witness_offset_mm": 2.0, "line_extension_mm": 0.0, "tick_size_mm": 2.5,
                  "width_factor": 1.0, "line_pen": 1, "tick_pen": 3, "text_font": hs.TEXT_FONT,
                  "equality_text": "EQ", "radius_prefix": "R", "diameter_symbol": "∅",
                  "snap_distance_mm": 8.0, "shoulder_length_mm": 3.0,
                  "accuracy_length": 1.0,          # 1 mm accuracy for OUR metric dimensions
                  "accuracy_angle": 0.01},
    "secret_dim_font_mm": 2.5,                    # the internal (temporary) dimension text
    "secret_arrow": {"tick_type": 0, "arrow_filled": 0},   # internal arrowheads keep the plain-arrow shape
}
#: the four SECRET INTERNAL dimension-style roles every 2026 project carries
#: exactly once (verified 6/6 samples: LinAng / Rad / TypePreview / Diameter)
#: + their four internal arrowheads.  Names are 'SecretInternal<Role><token>'
#: -- the token is a random alnum every file re-rolls (a format grammar, not
#: a value), so OURS is our own deterministic token.
SECRET_DIM_ROLES = ["LinAngDimStyle", "RadDimStyle", "TypePreviewDimStyle", "DiameterDimStyle"]
SECRET_ARROW_ROLES = ["LinAngArrowhead", "RadArrowhead", "TypePreviewgArrowhead",
                      "DiameterArrowhead"]


def secret_internal_name(role: str, seed: str = "rvt-writer") -> str:
    """'SecretInternal<role><token>' with OUR deterministic alnum token (the
    corpus tokens are per-file random; the grammar -- prefix + role + [0-9a-z]
    tail -- is the format constant)."""
    h = hashlib.md5(f"{seed}|{role}".encode()).hexdigest()
    tail = "".join(ch for ch in h if ch.isdigit())[:9] or "0"
    letter = h[0] if h[0].isalpha() else "q"
    return f"SecretInternal{role}{tail[:3]}{letter}{tail[3:]}"


#: OUR DATUM VOCABULARY for the surplus (plan-less) levels: name + our
#: elevation (metres).  Elevations are OUR building's datum set; a level
#: that geometry / views still reference keeps the SAMPLE's elevation
#: (moving a referenced datum moves hosted geometry -- reported per level).
LEVEL_VOCABULARY: List[Tuple[str, float]] = [
    ("B1 - Basement", -3.6), ("L0 - Ground Datum", 0.0), ("T.O. Slab", 0.15),
    ("Ceiling - L1", 2.7), ("T.O. Parapet", 8.1), ("Roof Datum", 7.5),
    ("T.O. Footing", -1.2), ("T.O. Steel", 7.2), ("Mezzanine", 3.3),
]
#: OUR GRID CONVENTION: gridline names + module.  OUR primary gridlines
#: are ZERO-PADDED NUMBERS ('01', '02', ...) at OUR structural module (the
#: residue grids are one bay of three parallel lettered lines A/B/C at a
#: 3.0 m spacing: ours = 01/02/03 at our 8.4 m module along the same axis, at
#: OUR grid reference elevation).
GRID_CONVENTION = {"names": [f"{i:02d}" for i in range(1, 41)],
                   "module_m": 8.4, "line_length_m": 42.0, "elevation_m": 0.0,
                   "sheet_text_height_ft": 0.015624999999999998}   # 3/16 in [format value]

#: OUR EXTRA drafting patterns (beyond the palette Y7 landed) for the sample's
#: surplus pattern slots -- our vocabulary continues.
EXTRA_LINE_PATTERNS: List[Dict[str, Any]] = [
    {"key": "dashdot", "name": gen("Dash Dot 6mm"),
     "segments": [("dash", 6.0), ("space", 2.0), ("dot", 0.0), ("space", 2.0)]},
    {"key": "phantom", "name": gen("Phantom 12mm"),
     "segments": [("dash", 12.0), ("space", 2.5), ("dash", 2.5), ("space", 2.5),
                  ("dash", 2.5), ("space", 2.5)]},
    {"key": "border", "name": gen("Border 10mm"),
     "segments": [("dash", 10.0), ("space", 2.0), ("dot", 0.0), ("space", 2.0),
                  ("dot", 0.0), ("space", 2.0)]},
]
EXTRA_FILL_PATTERNS: List[Dict[str, Any]] = [
    {"key": "brick", "name": gen("Brick Coursing 75mm"),
     "grids": [{"angle_deg": 0, "spacing_mm": 7.5}, {"angle_deg": 90, "spacing_mm": 22.5,
                                                     "dashes_mm": [7.5, 22.5]}]},
    {"key": "steel", "name": gen("Steel Section Hatch 1.5mm"),
     "grids": [{"angle_deg": 45, "spacing_mm": 1.5}, {"angle_deg": 45, "spacing_mm": 1.5,
                                                      "offset_mm": 0.75, "dashes_mm": [0.75, 0.75]}]},
    {"key": "gyp", "name": gen("Gypsum Stipple 2mm"),
     "grids": [{"angle_deg": 0, "spacing_mm": 2.0, "dashes_mm": [0.3, 3.7]},
               {"angle_deg": 90, "spacing_mm": 2.0, "dashes_mm": [0.3, 3.7]}]},
    {"key": "vertical", "name": gen("Vertical Lines 4mm"),
     "grids": [{"angle_deg": 90, "spacing_mm": 4.0}]},
]
#: OUR generic appearance palette for the material companions (name, RGB,
#: gloss 0..1, transparency, is_metal): render values chosen by us to match
#: the house material palette (rvt.genesis.house_standard.MATERIALS).
APPEARANCE_PALETTE: List[Dict[str, Any]] = [
    {"key": "concrete", "name": gen("Appearance - Cast Concrete"), "rgb": (200, 198, 192), "gloss": 0.20},
    {"key": "cmu", "name": gen("Appearance - Concrete Masonry"), "rgb": (172, 168, 158), "gloss": 0.15},
    {"key": "gypsum", "name": gen("Appearance - Painted Gypsum"), "rgb": (246, 246, 240), "gloss": 0.35},
    {"key": "steel", "name": gen("Appearance - Structural Steel"), "rgb": (150, 152, 160), "gloss": 0.55,
     "is_metal": True},
    {"key": "aluminium", "name": gen("Appearance - Anodised Aluminium"), "rgb": (196, 200, 208),
     "gloss": 0.70, "is_metal": True},
    {"key": "glass", "name": gen("Appearance - Clear Glazing"), "rgb": (198, 220, 236), "gloss": 0.90,
     "transparency": 0.7},
    {"key": "wood", "name": gen("Appearance - Softwood Lumber"), "rgb": (204, 178, 140), "gloss": 0.25},
    {"key": "insulation", "name": gen("Appearance - Rigid Insulation"), "rgb": (250, 240, 200), "gloss": 0.10},
    {"key": "earth", "name": gen("Appearance - Compacted Earth"), "rgb": (140, 116, 88), "gloss": 0.05},
    {"key": "paint_dark", "name": gen("Appearance - Painted Dark"), "rgb": (60, 62, 66), "gloss": 0.40},
    {"key": "plastic", "name": gen("Appearance - Plastic Laminate"), "rgb": (222, 222, 216), "gloss": 0.45},
    {"key": "fabric", "name": gen("Appearance - Upholstery Fabric"), "rgb": (110, 96, 84), "gloss": 0.05},
    {"key": "carpet", "name": gen("Appearance - Carpet Tile"), "rgb": (128, 128, 134), "gloss": 0.05},
    {"key": "brick", "name": gen("Appearance - Face Brick"), "rgb": (172, 96, 74), "gloss": 0.15},
    {"key": "ceramic", "name": gen("Appearance - Ceramic Tile"), "rgb": (232, 232, 226), "gloss": 0.60},
    {"key": "asphalt", "name": gen("Appearance - Asphalt"), "rgb": (72, 72, 74), "gloss": 0.10},
    {"key": "grass", "name": gen("Appearance - Turf"), "rgb": (98, 140, 74), "gloss": 0.05},
    {"key": "water", "name": gen("Appearance - Water"), "rgb": (120, 156, 186), "gloss": 0.85,
     "transparency": 0.4},
]


# ===========================================================================
# 3. CONSTRUCTORS -- shared helpers
# ===========================================================================

@dataclasses.dataclass
class Obj:
    """One constructed seq-102 object destined for an in-place SLOT:
    (class name / id, value dict) + the FIELD DELTA versus the slot's own
    object (which fields carry OUR value) + notes."""
    class_name: str
    class_id: int
    value: dict
    ours: List[str] = dataclasses.field(default_factory=list)     # dotted paths that are OURS
    notes: List[str] = dataclasses.field(default_factory=list)

    def as_tuple(self) -> Tuple[int, dict]:
        return (int(self.class_id), self.value)


def _deep(v):
    return copy.deepcopy(v)


def _name_of(value: dict) -> str:
    si = (value or {}).get("m_symbolInfo")
    if isinstance(si, dict):
        return str((si.get("value") or {}).get("m_name") or "")
    return ""


def _set_name(value: dict, name: str) -> None:
    value["m_symbolInfo"] = _owned("SymbolInfo", m_name=str(name))


def field_delta(a: Any, b: Any, path: str = "") -> List[str]:
    """Dotted paths whose values differ between two decoded objects (a =
    the slot's, b = ours).  Floats compare by their 8-byte encoding."""
    out: List[str] = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a or k not in b:
                out.append(f"{path}{k}")
                continue
            out += field_delta(a[k], b[k], f"{path}{k}.")
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}#len"]
        for i, (x, y) in enumerate(zip(a, b)):
            out += field_delta(x, y, f"{path}[{i}].")
        return out
    if isinstance(a, float) or isinstance(b, float):
        try:
            import struct as _st
            if _st.pack("<d", float(a)) != _st.pack("<d", float(b)):
                out.append(path.rstrip("."))
        except Exception:
            out.append(path.rstrip("."))
        return out
    if a != b:
        out.append(path.rstrip("."))
    return out


def check_object(class_name: str, value: dict) -> dict:
    """Encode -> decode -> re-encode byte-exact proof of one object (the
    per-record honesty gate every emitted object passes)."""
    from .types import _S
    dec, enc, _schema = _S()
    cid = class_id(class_name)
    body = enc.encode_object(cid, value)
    got = dec.decode_record(cid, body)
    re = enc.encode_object(cid, got.value) if got.clean else b""
    return {"class": class_name, "bytes": len(body), "clean": bool(got.clean),
            "byte_exact": (re == body), "errors": (got.errors or [])[:3],
            "ok": bool(got.clean and re == body)}


# ===========================================================================
# 4. THE SUB-CATEGORY LAYER (Z_subcat): CategoryElem + GStyleElem
# ===========================================================================
#: per-row STRUCTURAL PROFILE fields of a sub-category CategoryElem that are
#: compiled-in / registration properties of the ROW (kept from the slot):
#: the cell apparatus (SecretStyleMembership names its group; PatternHelper /
#: CategoryElemGroupHelper are empty helpers), the design-option token, the
#: category type / flags word, the parent + owner + gstyle wiring, m_famId.
CATEGORY_PROFILE_FIELDS = ("m_cellList", "m_designOptionId", "m_famId", "m_ownerId",
                           "m_gstyleIds")
CATEGORY_CATEGORY_PROFILE = ("m_parentCategoryId", "m_categoryType", "m_flags")
GSTYLE_PROFILE_FIELDS = ("m_cellList", "m_designOptionId", "m_famId", "m_categoryId",
                         "m_ownerId", "m_gstyleType")
GSTYLE_STYLE_PROFILE = ("m_linePatternId", "m_materialElemId", "m_isScreenSized")


def inplace_category(slot: dict, our_name: str) -> Obj:
    """OUR sub-category (CategoryElem) at an existing slot: the PURE
    ``new_category`` constructor, WIRED to the slot's own parent category /
    owner / gstyle ids and shaped by the slot's structural profile (cells,
    design-option, category type / flags -- per-row compiled-in properties, the
    catalog fixer v2's law).  The ONLY free value of a sub-category IS its
    NAME: that is ours (our vocabulary); everything else is registration /
    machinery, kept -- and the field-delta the report prints proves it."""
    cat = ((slot.get("m_pCategory") or {}).get("value") or {})
    rec = new_category(str(our_name), int(cat.get("m_parentCategoryId", -1)),
                       int(slot.get("m_ownerId", INVALID)),
                       category_type=int(cat.get("m_categoryType", 4)),
                       flags=int(cat.get("m_flags", 7)),
                       gstyle_ids=list(slot.get("m_gstyleIds") or []),
                       elem_id=int(slot.get("m_id", 0)),
                       design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)))
    ours = _deep(rec.obj)
    # per-row structural profile from the slot (machinery / registration)
    for f in ("m_cellList",):
        ours[f] = _deep(slot.get(f))
    ours["m_famId"] = int(slot.get("m_famId", INVALID))
    delta = field_delta(slot, ours)
    return Obj("CategoryElem", class_id("CategoryElem"), ours,
               ours=["m_pCategory.value.m_name"],
               notes=[f"our sub-category name {our_name!r}; wiring (parent {cat.get('m_parentCategoryId')}, "
                      f"owner {slot.get('m_ownerId')}, gstyles {slot.get('m_gstyleIds')}) + cells / "
                      f"type / flags = the slot's structural profile; field delta {delta}"])


def inplace_gstyle(slot: dict, *, pen: int, color: int,
                   line_pattern_id: Optional[int] = None) -> Obj:
    """OUR object-style ROW (GStyleElem) at an existing sub-category slot:
    the PURE ``new_gstyle`` constructor with OUR pen weight / colour (and,
    optionally, OUR line-pattern choice), WIRED to the slot's category /
    owner and shaped by the slot's profile (pattern / material wiring when we
    do not choose one, the screen-sized flag, cells, design-option)."""
    gst = ((slot.get("m_pGStyle") or {}).get("value") or {})
    pat = int(line_pattern_id) if line_pattern_id is not None else int(gst.get("m_linePatternId", LINEPATTERN_SOLID))
    rec = new_gstyle(int(slot.get("m_categoryId", INVALID)),
                     style_type=int(slot.get("m_gstyleType", 1)),
                     pen=int(pen), color=int(color), line_pattern_id=pat,
                     material_id=int(gst.get("m_materialElemId", INVALID)),
                     owner_id=int(slot.get("m_ownerId", INVALID)),
                     screen_sized=bool(gst.get("m_isScreenSized", False)),
                     elem_id=int(slot.get("m_id", 0)),
                     design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)))
    ours = _deep(rec.obj)
    ours["m_cellList"] = _deep(slot.get("m_cellList"))
    ours["m_famId"] = int(slot.get("m_famId", INVALID))
    fields = ["m_pGStyle.value.m_penNumber", "m_pGStyle.value.m_color"]
    if line_pattern_id is not None:
        fields.append("m_pGStyle.value.m_linePatternId")
    return Obj("GStyleElem", class_id("GStyleElem"), ours, ours=fields,
               notes=[f"our pen {pen} / colour {color:#08x}"
                      + (f" / our pattern {pat}" if line_pattern_id is not None else
                         " (pattern wiring kept)")
                      + "; category / owner / material wiring + cells + screen-sized = profile"])


def subcategory_scheme(parent_ost: int) -> Tuple[int, int, int]:
    """OUR (projection pen, cut pen, colour) for a sub-category of built-in
    parent ``parent_ost`` = the catalog's discipline scheme (the discipline
    OUR rules assign the parent), so the sub-category layer READS as one
    system with the Y6 object-styles catalog."""
    from . import catalog as CAT
    scheme = CAT.catalog_scheme()
    disc = CAT.classify_category(int(parent_ost)) if int(parent_ost) < 0 else "general"
    return scheme.get(disc, scheme["general"])


def build_subcategory_layer(doc, cat_ids: Sequence[int], gstyle_ids: Sequence[int],
                            *, our_line_patterns: Optional[Dict[str, int]] = None
                            ) -> Tuple[Dict[int, Obj], dict]:
    """Plan the WHOLE project sub-category layer of a file IN PLACE:
    ``cat_ids`` = the residue project CategoryElems, ``gstyle_ids`` = the
    residue project GStyleElems (each keyed on one of those categories).

    Names: per parent category, the slot's sub-categories are ordered by id
    and take OUR vocabulary in listed order (numbered fallback beyond it).
    Rows OWNED by an annotation type (empty-name internal line-style
    categories, ctype 4) keep the empty name (the internal-row shape) and get
    OUR annotation-ink pen / colour; the orphan 'X - element id N'-named
    internal rows (owner removed by the reduction) get our numbered
    'Annotation Line' names.  Graphics: OUR discipline scheme by parent
    category (catalog.classify_category), pens by projection / cut style
    type, black->INK swap exactly as the catalog does; where the slot's line
    pattern is one of OUR landed palette patterns (``our_line_patterns`` by
    key) the row keeps it (it IS ours), where it is a built-in the built-in
    stays (interface constant)."""
    plans: Dict[int, Obj] = {}
    report: Dict[str, Any] = {"categories": 0, "gstyles": 0, "named_by_parent": {},
                              "internal_owned": collections.Counter(),
                              "orphan_internal_named": 0, "fallback_named": 0,
                              "vocabulary_named": 0, "pattern_kept_builtin": 0,
                              "pattern_kept_element": 0}
    cat_by_parent: Dict[int, List[int]] = collections.defaultdict(list)
    cat_value: Dict[int, dict] = {}
    for c in sorted(int(x) for x in cat_ids):
        v = doc.value(c) or {}
        cat_value[c] = v
        cat = ((v.get("m_pCategory") or {}).get("value") or {})
        cat_by_parent[int(cat.get("m_parentCategoryId", 0))].append(c)
    orphan_i = 0
    for parent, cats in sorted(cat_by_parent.items()):
        vocab_i = 0
        for c in cats:
            v = cat_value[c]
            cat = ((v.get("m_pCategory") or {}).get("value") or {})
            owner = int(v.get("m_ownerId", INVALID))
            sample_name = str(cat.get("m_name") or "")
            if owner not in (INVALID, None) and owner > 0:
                # an annotation type's OWN internal line-style category: keep the
                # (empty) internal name -- the shape of an owned internal row
                our_name = ""
                report["internal_owned"][doc.class_of(owner) or "?"] += 1
            elif int(cat.get("m_categoryType", 1)) == 4 and int(parent) == OST_TextNoteLineStyle:
                # ORPHAN internal row ('Elevation - element id N'; its owner was
                # removed by the reduction): our numbered annotation-line name
                orphan_i += 1
                our_name = gen(f"Annotation Line {orphan_i:02d}")
                report["orphan_internal_named"] += 1
            else:
                our_name = our_subcategory_name(parent, vocab_i)
                if SUBCATEGORY_VOCABULARY.get(int(parent), (None, []))[1] and \
                        vocab_i < len(SUBCATEGORY_VOCABULARY[int(parent)][1]):
                    report["vocabulary_named"] += 1
                else:
                    report["fallback_named"] += 1
                vocab_i += 1
            plans[c] = inplace_category(v, our_name)
            report["named_by_parent"].setdefault(str(parent), []).append(our_name)
            report["categories"] += 1
    # ---- the GStyle rows of those categories ---------------------------------
    lp_ids = set((our_line_patterns or {}).values())
    for g in sorted(int(x) for x in gstyle_ids):
        v = doc.value(g) or {}
        cid = int(v.get("m_categoryId", INVALID))
        parent = -1
        owner = INVALID
        if cid in cat_value:
            cat = ((cat_value[cid].get("m_pCategory") or {}).get("value") or {})
            parent = int(cat.get("m_parentCategoryId", -1))
            owner = int(cat_value[cid].get("m_ownerId", INVALID))
        elif cid > 0 and doc.class_of(cid) == "CategoryElem":
            cv = doc.value(cid) or {}
            cat = ((cv.get("m_pCategory") or {}).get("value") or {})
            parent = int(cat.get("m_parentCategoryId", -1))
            owner = int(cv.get("m_ownerId", INVALID))
        gst = ((v.get("m_pGStyle") or {}).get("value") or {})
        gtype = int(v.get("m_gstyleType", 1))
        if owner not in (INVALID, None) and owner > 0:
            # an annotation type's own line style: our annotation ink
            pen, col = ANNOTATION_INTERNAL_PEN, ANNOTATION_INK
        else:
            proj_pen, cut_pen, col = subcategory_scheme(parent)
            pen = cut_pen if gtype == 2 else proj_pen
        cur_pat = int(gst.get("m_linePatternId", LINEPATTERN_SOLID))
        if cur_pat > 0:
            # a document line pattern (the palette layer's business: our landed
            # palette patterns or a residue pattern) -- the wiring is KEPT
            report["pattern_kept_element"] += 1
            if cur_pat in lp_ids:
                report.setdefault("pattern_already_ours", 0)
                report["pattern_already_ours"] = report.get("pattern_already_ours", 0) + 1
        else:
            report["pattern_kept_builtin"] += 1                 # built-in pattern id (interface constant)
        plans[g] = inplace_gstyle(v, pen=pen, color=col, line_pattern_id=None)
        report["gstyles"] += 1
    report["internal_owned"] = dict(report["internal_owned"])
    return plans, report


# ===========================================================================
# 5. FONTS (FontElem) -- always OWNED by an annotation type
# ===========================================================================

def font_elem(owner_id: int, *, name: str = None, size_mm: float = 2.5,
              color: int = FONT_COLOR_BLACK, elem_id: int = 0,
              cells=None) -> Obj:
    """OUR ``FontElem`` (a type's text face): our house font at our paper
    height, black.  ``owner_id`` = the owning annotation type (a font is ALWAYS
    owned -- 5,982/5,982 corpus fonts); ``cells`` = the slot's cell apparatus
    (the fonts of the secret internal dimension styles carry a
    SecretStyleMembership cell naming their group -- kept from the slot).
    m_designOptionId = the internal sentinel -4 (5,982/5,982)."""
    obj = blank_object("FontElem")
    element_defaults(obj, int(elem_id), design_option=INTERNAL_DESIGN_OPTION)
    obj["m_ownerId"] = int(owner_id)
    obj["m_pFont"] = _owned("Font", m_name=str(name or ANNOTATION_STANDARD["font"]),
                             m_size=mm(float(size_mm)), m_color=int(color))
    obj["m_cellList"] = _deep(cells) if cells is not None else None
    return Obj("FontElem", class_id("FontElem"), obj,
               ours=["m_pFont.value.m_name", "m_pFont.value.m_size", "m_pFont.value.m_color"],
               notes=[f"our font {name or ANNOTATION_STANDARD['font']} {size_mm} mm, colour {color:#x}; "
                      f"owner {owner_id} + cells = wiring"])


def inplace_font(slot: dict, *, size_mm: float) -> Obj:
    """OUR font at an existing font slot: our face / height / colour, the
    slot's owner + cells (its type constellation's wiring)."""
    o = font_elem(int(slot.get("m_ownerId", INVALID)), size_mm=size_mm,
                  elem_id=int(slot.get("m_id", 0)), cells=slot.get("m_cellList"))
    o.notes.append(f"replaces font {(slot.get('m_pFont') or {}).get('value', {}).get('m_name')} "
                   f"@ owner {slot.get('m_ownerId')}")
    return o


# ===========================================================================
# 6. ARROWHEADS (LeaderStyle)
# ===========================================================================

def arrowhead_type(name: str, *, category_id: int, tick_type: int = 8,
                   filled: int = 1, closed: bool = True, centered: bool = False,
                   angle_deg: float = 20.0, size_mm: float = 3.0,
                   width_pen: Optional[int] = 1, elem_id: int = 0,
                   design_option: int = NO_DESIGN_OPTION, cells=None) -> Obj:
    """OUR arrowhead type (``LeaderStyle``): tick geometry (type / filled /
    closed / centered), OUR arrow angle + size parameters, our name.
    ``category_id`` = the arrowhead's own internal line-style CategoryElem
    (every arrowhead owns one -- 1,024/1,024); ``cells`` = the slot's cell
    apparatus (the SECRET internal arrowheads carry a SecretStyleMembership
    cell naming their dimension group -- machinery, kept)."""
    obj = blank_object("LeaderStyle")
    element_defaults(obj, int(elem_id), design_option=design_option,
                     double_params={BIP_ARROW_ANGLE: math.radians(float(angle_deg)),
                                    BIP_ARROW_SIZE: mm(float(size_mm))},
                     int_params=({BIP_ARROW_WIDTH_PEN: int(width_pen)}
                                 if width_pen is not None else None))
    symbol_defaults(obj, str(name))
    obj["m_categoryId"] = int(category_id)
    obj["m_tickType"] = int(tick_type)
    obj["m_arrowFilled"] = int(filled)
    obj["m_arrowClosed"] = bool(closed)
    obj["m_arrowCentered"] = bool(centered)
    obj["m_cellList"] = _deep(cells) if cells is not None else None
    return Obj("LeaderStyle", class_id("LeaderStyle"), obj,
               ours=["m_symbolInfo.value.m_name", "m_tickType", "m_arrowFilled", "m_arrowClosed",
                     "m_arrowCentered", f"param {BIP_ARROW_ANGLE} (angle)",
                     f"param {BIP_ARROW_SIZE} (size)", f"param {BIP_ARROW_WIDTH_PEN} (width pen)"],
               notes=[f"our arrowhead {name!r}: tick {tick_type}, filled {filled}, angle {angle_deg} deg, "
                      f"size {size_mm} mm; category {category_id} + cells = wiring"])


def inplace_arrowhead(slot: dict) -> Obj:
    """OUR arrowhead at an existing LeaderStyle slot.  A SECRET internal
    arrowhead (name 'SecretInternal<role>...') keeps its ROLE (our token in
    the name) and the plain internal shape (:data:`ANNOTATION_STANDARD`
    'secret_arrow') at OUR internal size; a real arrowhead type becomes OUR
    house arrowhead (filled 20-degree arrow, 3 mm)."""
    old = _name_of(slot)
    role = next((r for r in SECRET_ARROW_ROLES if old.startswith("SecretInternal" + r)), None)
    if role is None and old.startswith("SecretInternal"):
        role = old[len("SecretInternal"):].rstrip("0123456789") or "Arrowhead"
    if role:                                              # internal machinery arrowhead
        st = ANNOTATION_STANDARD["secret_arrow"]
        return arrowhead_type(secret_internal_name(role), category_id=int(slot.get("m_categoryId", -1)),
                              tick_type=st["tick_type"], filled=st["arrow_filled"], closed=False,
                              centered=False, angle_deg=15.0, size_mm=ANNOTATION_STANDARD["secret_dim_font_mm"],
                              width_pen=(1 if slot.get("m_pParamValueSetInt") else None),
                              elem_id=int(slot.get("m_id", 0)),
                              design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)),
                              cells=slot.get("m_cellList"))
    st = ANNOTATION_STANDARD["arrowhead"]
    return arrowhead_type(st["name"], category_id=int(slot.get("m_categoryId", -1)),
                          tick_type=st["tick_type"], filled=st["arrow_filled"],
                          closed=st["arrow_closed"], centered=st["arrow_centered"],
                          angle_deg=st["angle_deg"], size_mm=st["size_mm"],
                          width_pen=(1 if slot.get("m_pParamValueSetInt") else None),
                          elem_id=int(slot.get("m_id", 0)),
                          design_option=int(slot.get("m_designOptionId", NO_DESIGN_OPTION)),
                          cells=slot.get("m_cellList"))


# ===========================================================================
# 7. GRID HEAD TYPE (GridAttributes)
# ===========================================================================

def grid_head_type(name: str, *, font_id: int, line_category_id: int,
                   leader_category_id: int, center_segment_category_id: int,
                   bubble_end1: bool = True, bubble_end2: bool = True,
                   center_segment_style: int = 0, end_segments_length_mm: float = 1200.0,
                   bubble_loc_in_elev: int = 2, family_tag_id: int = INVALID,
                   elem_id: int = 0, design_option: int = NO_DESIGN_OPTION,
                   cells=None) -> Obj:
    """OUR grid TYPE (``GridAttributes``): bubbles at both ends, a
    continuous grid line, OUR end-segment length + text height (via the
    owned font); ``family_tag_id`` = the grid-HEAD annotation family symbol =
    -1 on the family-free base (K4's certified state: the head symbol is
    loadable annotation content, its usage is nulled -- ENUM [null,
    @FamilySymbol] and the base itself carries -1 and LOADS).  The line /
    leader / center-segment CategoryElems + the FontElem are the type's owned
    constellation (wiring); ``m_bubbleLocInElev`` 2 is the corpus constant."""
    obj = blank_object("GridAttributes")
    element_defaults(obj, int(elem_id), design_option=design_option, int_params={})
    symbol_defaults(obj, str(name))
    obj["m_lineAndTextAttr"] = {"m_fontId": int(font_id), "m_categoryId": int(line_category_id),
                               "m_background": 0, "m_bBold": False, "m_bItalic": False,
                               "m_bUnderline": False}
    obj["m_endSegmentsLength"] = mm(float(end_segments_length_mm))
    obj["m_leaderCategoryId"] = int(leader_category_id)
    obj["m_familyTagId"] = int(family_tag_id)
    obj["m_categoryForCenterSegment"] = int(center_segment_category_id)
    obj["m_centerSegmentStyle"] = int(center_segment_style)
    obj["m_bubbleLocInElev"] = int(bubble_loc_in_elev)
    obj["m_bubbleAtEnd1"] = bool(bubble_end1)
    obj["m_bubbleAtEnd2"] = bool(bubble_end2)
    obj["m_cellList"] = _deep(cells) if cells is not None else None
    return Obj("GridAttributes", class_id("GridAttributes"), obj,
               ours=["m_symbolInfo.value.m_name", "m_endSegmentsLength", "m_centerSegmentStyle",
                     "m_bubbleAtEnd1", "m_bubbleAtEnd2"],
               notes=[f"our grid type {name!r}: bubbles both ends, continuous line, end segments "
                      f"{end_segments_length_mm} mm; font / line / leader / centre-segment "
                      "categories = the type's owned constellation (wiring); familyTagId -1 "
                      "(family-free base, corpus-null-legal)"])


# ===========================================================================
# 8. INTERIOR-ELEVATION MARKER TYPE (InteriorElevAttributes)
# ===========================================================================

def interior_elevation_type(name: str, *, font_id: int, line_category_id: int,
                            shape: int = 1, width_mm: float = 10.0,
                            arrow_angle_deg: float = 45.0, arrow_filled: bool = True,
                            text_pos: int = 3, view_name_pos: int = 1,
                            reference_label_pos: int = 2, show_view_name: bool = True,
                            elevation_symbol_id: int = INVALID,
                            elem_id: int = 0, design_option: int = NO_DESIGN_OPTION,
                            cells=None) -> Obj:
    """OUR interior-elevation MARKER type: circle shape, OUR width / arrow
    angle / filled arrows, text + view-name + reference-label positions.
    ``elevation_symbol_id`` = the marker's annotation family symbol = -1 on
    the family-free base (ENUM [null, @FamilySymbol]).  ``m_orderedSubIndices``
    = [] (LEN_SET [0, 4]: the base's four sub-arrow ordinals are unowned
    ordinals we do not invent; empty is corpus-legal); referenceLabelPos 2
    is the corpus constant (49/49)."""
    obj = blank_object("InteriorElevAttributes")
    element_defaults(obj, int(elem_id), design_option=design_option)
    symbol_defaults(obj, str(name))
    obj["m_lineAndTextAttr"] = {"m_fontId": int(font_id), "m_categoryId": int(line_category_id),
                               "m_background": 0, "m_bBold": False, "m_bItalic": False,
                               "m_bUnderline": False}
    obj["m_width"] = mm(float(width_mm))
    obj["m_ahAngleDouble"] = math.radians(float(arrow_angle_deg))
    obj["m_elevationSymbolId"] = int(elevation_symbol_id)
    obj["m_shape"] = int(shape)
    obj["m_textPos"] = int(text_pos)
    obj["m_viewNamePos"] = int(view_name_pos)
    obj["m_referenceLabelPos"] = int(reference_label_pos)
    obj["m_ahFilled"] = bool(arrow_filled)
    obj["m_showViewName"] = bool(show_view_name)
    obj["m_orderedSubIndices"] = []
    obj["m_cellList"] = _deep(cells) if cells is not None else None
    return Obj("InteriorElevAttributes", class_id("InteriorElevAttributes"), obj,
               ours=["m_symbolInfo.value.m_name", "m_width", "m_ahAngleDouble", "m_shape",
                     "m_textPos", "m_viewNamePos", "m_ahFilled", "m_showViewName",
                     "m_orderedSubIndices"],
               notes=[f"our elevation marker {name!r}: shape {shape}, width {width_mm} mm, arrows "
                      f"{arrow_angle_deg} deg filled; symbol id -1 (family-free); sub-indices [] "
                      "(corpus-legal empty)"])


# ===========================================================================
# 9. CALLOUT HEAD TYPE (CalloutTag)
# ===========================================================================

def callout_head_type(name: str, *, corner_radius_mm: float = 2.0,
                      family_tag_id: int = INVALID, elem_id: int = 0,
                      design_option: int = NO_DESIGN_OPTION, cells=None) -> Obj:
    """OUR callout HEAD type (``CalloutTag``): our corner radius, our name;
    the callout tag family symbol = -1 on the family-free base."""
    obj = blank_object("CalloutTag")
    element_defaults(obj, int(elem_id), design_option=design_option)
    symbol_defaults(obj, str(name))
    obj["m_cornerRadius"] = mm(float(corner_radius_mm))
    obj["m_familyTagId"] = int(family_tag_id)
    obj["m_cellList"] = _deep(cells) if cells is not None else None
    return Obj("CalloutTag", class_id("CalloutTag"), obj,
               ours=["m_symbolInfo.value.m_name", "m_cornerRadius"],
               notes=[f"our callout head {name!r}: corner radius {corner_radius_mm} mm; "
                      "familyTagId -1 (family-free)"])


# ===========================================================================
# 10. DIMENSION STYLES (the SECRET internal ones) -- overlay constructor
# ===========================================================================
#: DimensionStyle fields that are OUR annotation standard (values), by
#: name; everything else in the 60+-field object is the unit-format /
#: parameter-set MACHINERY every 2026 dimension style carries in the same
#: shape (kept from the slot -- SAID SO in every report).
DIMENSION_OUR_FIELDS = [
    "m_symbolInfo.value.m_name",                       # SecretInternal<Role> + our token
    f"paramSet[{BIP_TEXT_SIZE}] (text size)",
    f"paramSet[{BIP_DIM_TEXT_OFFSET}] (text offset)",
    f"paramSet[{BIP_DIM_WITNS_EXTENSION}] (witness extension)",
    f"paramSet[{BIP_DIM_WITNS_OFFSET}] (witness offset)",
    f"paramSet[{BIP_DIM_LINE_EXTENSION}] (line extension)",
    f"paramSet[{BIP_DIM_TICK_SIZE}] (tick size)",
    f"paramSet[{BIP_TEXT_WIDTH_SCALE}] (width factor)",
    "m_equalityText / m_radiusDiameterPrefixText / prefixes",
    "m_oLinFormatOptions.accuracy (our 1 mm) / m_oAngFormatOptions.accuracy",
    "m_dimLineSnapDist", "m_leaderShoulderLength",
]


def inplace_secret_dimension_style(slot: dict) -> Obj:
    """OUR secret internal dimension style at an existing slot.  These four
    styles (LinAng / Rad / TypePreview / Diameter) are Revit's TEMPORARY-
    DIMENSION machinery: every 2026 project carries exactly one of each, its
    name a random-token 'SecretInternal<Role>...' -- but the VALUES differ
    per template (metric / imperial text sizes, accuracies), i.e. they are
    document SETTINGS, so OURS apply: OUR annotation text size / offsets /
    witness gaps / tick size / accuracies + OUR name token, overlaid on the
    format machinery (unit FormatOptions apparatus, equality formatting, the
    param-set ids) which is the same shape in every file (the mined
    constants).  A from-blank constructor of this 60-field class is
    deliberately NOT claimed: the report lists OUR fields
    (:data:`DIMENSION_OUR_FIELDS`) and everything else as machinery."""
    st = ANNOTATION_STANDARD["dimension"]
    ours = _deep(slot)
    old = _name_of(slot)
    role = next((r for r in SECRET_DIM_ROLES if old.startswith("SecretInternal" + r)), None)
    if role is None:
        role = (old[len("SecretInternal"):].rstrip("0123456789") if old.startswith("SecretInternal")
                else "LinAngDimStyle")
    _set_name(ours, secret_internal_name(role))
    # our annotation values in the (existing) double param set
    want = {BIP_TEXT_SIZE: mm(st["text_mm"]), BIP_DIM_TEXT_OFFSET: mm(st["text_offset_mm"]),
            BIP_DIM_WITNS_EXTENSION: mm(st["witness_extension_mm"]),
            BIP_DIM_WITNS_OFFSET: mm(st["witness_offset_mm"]),
            BIP_DIM_LINE_EXTENSION: mm(st["line_extension_mm"]),
            BIP_DIM_TICK_SIZE: mm(st["tick_size_mm"]),
            BIP_TEXT_WIDTH_SCALE: float(st["width_factor"])}
    pset = ((ours.get("m_pParamValueSetDouble") or {}).get("value") or {}).get("m_paramSet")
    changed_params = []
    if isinstance(pset, list):
        for entry in pset:
            pid = int(entry.get("m_paramId", 0))
            if pid in want:
                entry["m_value"] = float(want[pid])
                changed_params.append(pid)
    # our texts (equality tag / radius prefix), our snap + shoulder distances
    if "m_equalityText" in ours:
        ours["m_equalityText"] = str(st["equality_text"])
    if "m_radiusDiameterPrefixText" in ours:
        ours["m_radiusDiameterPrefixText"] = str(st["radius_prefix"])
    if "m_dimLineSnapDist" in ours:
        ours["m_dimLineSnapDist"] = mm(st["snap_distance_mm"])
    if "m_leaderShoulderLength" in ours:
        ours["m_leaderShoulderLength"] = mm(st["shoulder_length_mm"])
    # OUR accuracies where the slot carries an explicit (non-default) accuracy
    for fld, acc in (("m_oLinFormatOptions", st["accuracy_length"]),
                     ("m_oAngFormatOptions", st["accuracy_angle"])):
        fo = ((ours.get(fld) or {}).get("value") or {})
        if fo and not fo.get("m_bUseDefault", True):
            fo["m_accuracy"] = float(acc)
    delta = field_delta(slot, ours)
    return Obj("DimensionStyle", class_id("DimensionStyle"), ours,
               ours=list(DIMENSION_OUR_FIELDS) + [f"changed param ids {sorted(set(changed_params))}"],
               notes=[f"secret internal dimension style role {role}: our name token + our annotation "
                      f"values overlaid on the unit-format / param-set MACHINERY of the slot "
                      f"(overlay constructor -- said so); field delta {delta}"])


# ===========================================================================
# 11. GRIDS (datum content) -- pure constructor, the twin of new_level
# ===========================================================================
#: DatumPlane geometry-step / geom-table apparatus of a GRID [values verified
#: on the corpus grid 195338: geomstep version 1, flags 761725, latest
#: gstep types [0,0,0,0,0], id counter 2, list flags 11; Face GInfo flags
#: 524804 -- the same DatumPlane machinery Level carries with grid values].
_GRID_GSTEP_FLAGS = 761725
_GRID_GLIST_FLAGS = 11
_GRID_FACE_FLAGS = 524804
BIP_ELEM_TYPE_PARAM = -1012201                       # ELEM_FAMILY_AND_TYPE (grid -> -1)


def _weak(pid: int) -> dict:
    return {"weakref": int(pid)}


def _grid_geom_steps() -> dict:
    return _ptr("GeomStepList", {
        "m_nonBRepGList": [_ptr("DatumPlaneGeomStep", {
            "m_faceHistTable": [{"m_id": 0, "m_faceHist": {"m_keys": [6, 0, -1]}}],
            "m_curveHistTableSet": [], "m_edgeHistTable": [], "m_edgeHistTableReverse": [],
            "m_id": 1, "m_version": 1, "m_flags": _GRID_GSTEP_FLAGS,
            "m_pElem": _weak(2), "m_oExtraDatas": None})],
        "m_bRepFormGList": [], "m_bRepAdjustGList": [], "m_bRepCutOutGList": [],
        "m_bRepPostCutOutGList": [], "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [0, 0, 0, 0, 0],
        "m_idCounter": 2, "m_flags": _GRID_GLIST_FLAGS})


def _grid_plane(origin, xvec, yvec, envelope, pid: int) -> dict:
    return {"ptr_class": "Plane", "pid": pid, "value": {
        "m_Envelope": {"m_corners": [[float(envelope[0][0]), float(envelope[0][1])],
                                     [float(envelope[1][0]), float(envelope[1][1])]]},
        "m_orientFlag": True,
        "m_origin": [float(x) for x in origin],
        "m_xVec": [float(x) for x in xvec],
        "m_yVec": [float(x) for x in yvec]}}


def new_grid(name: str, start_ft: Sequence[float], end_ft: Sequence[float], *,
             attr_id: int, elevation_ft: float = 0.0, bottom_ft: float = None,
             top_ft: float = None, elem_id: int = 0,
             design_option: int = NO_DESIGN_OPTION) -> Obj:
    """OUR straight GRID line (``Grid``, seq-103 = SerializedDummy): a
    vertical DATUM PLANE through the segment ``start_ft`` -> ``end_ft``
    (model XY, feet) between elevations ``bottom_ft`` .. ``top_ft`` (the
    plane's UV envelope: U along the line from the plane origin, V = Z).
    Structure = the corpus grid (rstbasic-lineage 195338): the plane origin
    is the MIDPOINT of the line at ``elevation_ft`` (the grid's reference
    Z), xVec = the unit line direction, yVec = +Z; ``m_text`` = the grid
    name; ``m_attrId`` = its ``GridAttributes`` type.  ``m_freeEnd`` /
    ``m_bubbleEnd`` / ``m_refPointsForNewViews`` are the zero-vector 'compute
    on regen' form the corpus grid carries; ``m_sheetTextHeight`` 3/16 in is
    the format value; parameter -1012201 (family+type) = -1 (grids have no
    family type)."""
    x0, y0 = float(start_ft[0]), float(start_ft[1])
    x1, y1 = float(end_ft[0]), float(end_ft[1])
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    if length <= 1e-9:
        raise ValueError("a grid line needs distinct end points")
    ux, uy = dx / length, dy / length
    mid = ((x0 + x1) / 2.0, (y0 + y1) / 2.0, float(elevation_ft))
    z0 = float(bottom_ft) if bottom_ft is not None else float(elevation_ft) - 20.0
    z1 = float(top_ft) if top_ft is not None else float(elevation_ft) + 60.0
    # UV envelope: U along the line (centred), V = elevation range (relative to origin z)
    env = ((-length / 2.0, z0 - mid[2]), (length / 2.0, z1 - mid[2]))
    obj = blank_object("Grid")
    element_defaults(obj, int(elem_id), design_option=design_option,
                     elemid_params={BIP_ELEM_TYPE_PARAM: INVALID})
    obj["m_geomSteps"] = _grid_geom_steps()
    obj["m_pGeomTable"] = _ptr("GeomTable", {
        "m_refPntMirrored": False, "m_table": [{"m_geomGeneratorId": 1}],
        "m_bigTableOwner": None, "m_materialMarkers": [], "m_faceTypeMarkers": []})
    obj["m_text"] = str(name)
    obj["m_pFace"] = _ptr("Face", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                    "m_flags": _GRID_FACE_FLAGS},
        "m_pFirstLoop": None, "m_faceRegions": [], "m_pGFilling": None,
        "m_oBackgroundFilling": None, "m_renderStyleId": -1, "m_cutType": 0,
        "m_faceFlags_v9": 0,
        "m_pSurf": _grid_plane(mid, (ux, uy, 0.0), (0.0, 0.0, 1.0), env, pid=5)}, pid=3)
    obj["m_pSurface"] = _grid_plane(mid, (ux, uy, 0.0), (0.0, 0.0, 1.0), env, pid=4)
    obj["m_pLeader"] = None
    obj["m_freeEnd"] = [0.0, 0.0, 0.0]
    obj["m_bubbleEnd"] = [0.0, 0.0, 0.0]
    obj["m_cutVec"] = [0.0, 0.0, 0.0]
    obj["m_refPointsForNewViews"] = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    obj["m_sheetTextHeight"] = float(GRID_CONVENTION["sheet_text_height_ft"])
    obj["m_genDbViewId"] = -1
    obj["m_v2Datum"] = False
    obj["m_useConstVForDatumLine3dRep"] = True
    obj["m_pGridChainMembershipCell"] = None
    obj["m_attrId"] = int(attr_id)
    obj["m_showCenterMark"] = False
    return Obj("Grid", class_id("Grid"), obj,
               ours=["m_text (name)", "m_pSurface / m_pFace plane (line geometry)",
                     "envelope (extents)"],
               notes=[f"our grid {name!r}: line ({x0:.2f},{y0:.2f}) -> ({x1:.2f},{y1:.2f}) ft, "
                      f"length {length:.2f} ft, elevation {elevation_ft} ft; type {attr_id}"])


def our_grid_bay(count: int, *, attr_id: int, elevation_ft: float,
                 origin_ft: Tuple[float, float] = (0.0, 0.0),
                 axis: str = "x") -> List[Obj]:
    """OUR gridline set for one direction: ``count`` parallel lines at OUR
    module (:data:`GRID_CONVENTION`), named A, B, C ..., each OUR length,
    running along ``axis`` ('x' = lines parallel to X, spaced in Y)."""
    module = mm(GRID_CONVENTION["module_m"] * 1000.0)
    length = mm(GRID_CONVENTION["line_length_m"] * 1000.0)
    out = []
    ox, oy = float(origin_ft[0]), float(origin_ft[1])
    for i in range(int(count)):
        nm_ = GRID_CONVENTION["names"][i] if i < len(GRID_CONVENTION["names"]) else str(i + 1)
        off = i * module
        if axis == "x":
            p0, p1 = (ox, oy - off), (ox + length, oy - off)
        else:
            p0, p1 = (ox + off, oy), (ox + off, oy - length)
        out.append(new_grid(nm_, p0, p1, attr_id=attr_id, elevation_ft=elevation_ft))
    return out


# ===========================================================================
# 12. APPEARANCE ASSETS (AppearanceAssetElem) -- pure constructor
# ===========================================================================

_APROP_CLASS_DEFAULT = {"APropertyString": "", "APropertyBoolean": False,
                        "APropertyInteger": 0, "APropertyDouble1": 0.0,
                        "APropertyDouble2": [0.0, 0.0],
                        "APropertyDouble4": [0.0, 0.0, 0.0, 1.0], "APropertyEnum": 0}


def _aproperty(cls_name: str, name: str, value) -> dict:
    return {"ptr_class": cls_name, "pid": -1,
            "value": {"m_sName": str(name), "m_aChild": None, "m_aConnected": [],
                      "m_value": value}}


def _our_asset_guid(name: str) -> str:
    """OUR deterministic version GUID for an appearance asset (a token, not
    a copied library guid)."""
    h = hashlib.md5(f"rvt-writer-appearance|{name}".encode()).hexdigest().upper()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def generic_appearance_asset(name: str, rgb_255: Tuple[int, int, int], *,
                             glossiness: float = 0.4, transparency: float = 0.0,
                             is_metal: bool = False, reflectivity0: float = 0.5,
                             reflectivity90: float = 0.5, tint: bool = False,
                             description: str = "", keyword: str = "",
                             category: str = "", elem_id: int = 0,
                             profile: Optional[dict] = None) -> Obj:
    """OUR ``AppearanceAssetElem`` on the Protein 'GenericSchema': the
    schema's property SKELETON (names / order / APropertyXxx types + the
    library / UI constants, frozen from the corpus census --
    :func:`derive_generic_asset_profile`) with OUR free values: name, diffuse
    colour (linear 0..1 RGBA), glossiness, reflectivity, transparency, tint,
    description / keyword / category strings, OUR deterministic version
    guid + thumbnail token.  ``m_pThumbnail`` null and ``m_materialPathMap``
    [] as the corpus assets carry.  This is what a MaterialElem's render-
    appearance companion is; our house palette (:data:`APPEARANCE_PALETTE`)
    feeds it."""
    prof = profile or load_generic_asset_profile()
    r, g, b = [max(0, min(255, int(x))) / 255.0 for x in rgb_255]
    color4 = [round(r, 4), round(g, 4), round(b, 4), 1.0]
    ours: Dict[str, Any] = {
        "UIName": str(name), "VersionGUID": _our_asset_guid(str(name)),
        "description": str(description or "our house appearance"), "keyword": str(keyword or "materials:ours"),
        "category": str(category or ":Ours"), "thumbnail": f"Mats\\Ours\\t_{name.replace(' ', '_')}.png",
        "swatch": "Swatch-Sphere2", "generic_diffuse": color4,
        "generic_glossiness": float(glossiness), "generic_reflectivity_at_0deg": float(reflectivity0) if is_metal else 0.0,
        "generic_reflectivity_at_90deg": float(reflectivity90) if is_metal else 0.0,
        "generic_transparency": float(transparency), "generic_bump_amount": 0.0,
        "generic_is_metal": bool(is_metal), "common_Tint_color": color4 if tint else [0.315, 0.315, 0.315, 1.0],
        "AssetLibID": "OURS-0000-0000-0000-000000000000", "version": 4, "revision": 1,
    }
    props = []
    for p in prof.get("properties") or []:
        pname = p["name"]
        cls_ = p["aproperty_class"]
        if p.get("constant"):
            val = p.get("value")
        elif pname in ours:
            val = ours[pname]
        else:
            val = p.get("corpus_top_value", _APROP_CLASS_DEFAULT.get(cls_))
        props.append(_aproperty(cls_, pname, val))
    obj = blank_object("AppearanceAssetElem")
    element_defaults(obj, int(elem_id))
    asset = blank_object("Asset")
    asset["m_sName"] = "GenericSchema"
    asset["m_aChild"] = None
    asset["m_aConnected"] = []
    asset["m_aAProperties"] = props
    asset["m_sLibrary"] = "assetlibrary_base.fbx"          # the Protein base library token [400/400]
    asset["m_sScene"] = ""
    asset["m_oImage"] = None
    asset["m_eAssetType"] = 4                              # materialappearance [400/400]
    ap = blank_object("AppearanceAsset")
    ap["m_transparency"] = float(transparency)
    ap["m_color"] = int(rgb(rgb_255[0], rgb_255[1], rgb_255[2]))
    ap["m_Name"] = "Generic"                               # the schema's display name [Generic-schema assets]
    ap["m_Asset"] = asset
    obj["m_pAppearanceAsset"] = _ptr("AppearanceAsset", ap)
    obj["m_pThumbnail"] = None
    obj["m_materialPathMap"] = []
    return Obj("AppearanceAssetElem", class_id("AppearanceAssetElem"), obj,
               ours=["UIName", "VersionGUID", "description", "keyword", "category", "thumbnail",
                     "generic_diffuse", "generic_glossiness", "generic_reflectivity_*",
                     "generic_transparency", "generic_is_metal", "common_Tint_color",
                     "m_color", "m_transparency"],
               notes=[f"our generic appearance {name!r}: diffuse {color4}, gloss {glossiness}, "
                      f"transparency {transparency}, metal {is_metal}; {len(props)}-property "
                      "GenericSchema skeleton = the frozen corpus profile (format constants)"])


# ===========================================================================
# 13. THE RESIDUE PLANS (parent file -> {slot: Obj}) per rung
# ===========================================================================

@dataclasses.dataclass
class RungPlan:
    name: str
    label: str
    plans: Dict[int, Obj]                       # slot -> our object
    residue_left: Dict[str, List[int]]          # class -> ids deliberately not substituted (+ why in notes)
    notes: List[str]
    info: Dict[str, Any] = dataclasses.field(default_factory=dict)

    @property
    def by_class(self) -> Dict[str, int]:
        return dict(collections.Counter(o.class_name for o in self.plans.values()).most_common())


class Parent:
    """Read-only view of the CERTIFIED parent file a Z rung derives from:
    the mutate.Document + the typed reference graph (rvt_reduce state) + the
    Y-ladder's landed-slot map (so 'residue' means exactly Yn's residue)."""

    def __init__(self, path: str = DEFAULT_PARENT, *, with_graph: bool = True):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        self.path = os.path.abspath(path)
        t0 = time.time()
        if with_graph:
            import rvt_reduce as RR                                   # noqa: E402
            self.state = RR.build_state_v2(self.path)
            self.doc = self.state["doc"]
        else:                                                          # pragma: no cover
            from ..mutate import Document
            self.state = None
            self.doc = Document.from_file(self.path)
        self.cls_of = {int(e): (self.doc.class_of(int(e)) or "?") for e in self.doc.et_by_id}
        self.landed = ladder_landed()
        self.residue = residue_by_class(self.doc, self.landed)
        self.seconds = round(time.time() - t0, 1)

    def value(self, eid: int) -> dict:
        return self.doc.value(int(eid)) or {}

    def name_of(self, eid: int) -> str:
        v = self.value(eid)
        return _name_of(v) or str(v.get("m_text") or v.get("m_name") or "")

    def referrers(self, eid: int) -> Set[int]:
        if not self.state:
            return set()
        return set(self.state["referrers"].get(int(eid), set()))

    def our_pattern_ids(self) -> Dict[str, int]:
        """{our line-pattern key: element id} of OUR palette patterns present
        in the parent (Y7 landed them under their gen() names)."""
        by_name = {p["name"]: p["key"] for p in hs.LINE_PATTERNS}
        out: Dict[str, int] = {}
        for e in self.doc.et_by_id:
            if self.cls_of.get(int(e)) != "LinePatternElem":
                continue
            nm_ = str(((self.value(e).get("m_pLinePattern") or {}).get("value") or {}).get("m_name") or "")
            if nm_ in by_name:
                out[by_name[nm_]] = int(e)
        return out


def plan_subcat(parent: Parent) -> RungPlan:
    """Z_subcat: the project SUB-CATEGORY layer -- every residue project
    CategoryElem + every residue project GStyleElem (the family-scoped rows
    of the curtain constellation stay: :data:`NON_INPLACE`)."""
    doc = parent.doc
    cat_res = parent.residue.get("CategoryElem", [])
    gs_res = parent.residue.get("GStyleElem", [])
    cat_proj, cat_fam = split_family_scoped(doc, cat_res)
    gs_proj, gs_fam = split_family_scoped(doc, gs_res)
    plans, rep = build_subcategory_layer(doc, cat_proj, gs_proj,
                                         our_line_patterns=parent.our_pattern_ids())
    notes = [
        f"CategoryElem residue {len(cat_res)}: project {len(cat_proj)} SUBSTITUTED, family-scoped "
        f"{len(cat_fam)} left (curtain constellation)",
        f"GStyleElem residue {len(gs_res)}: project {len(gs_proj)} SUBSTITUTED, family-scoped "
        f"{len(gs_fam)} left",
        f"naming: {rep['vocabulary_named']} slots got OUR vocabulary entries, "
        f"{rep['fallback_named']} our numbered fallback, {rep['orphan_internal_named']} orphan "
        f"internal rows our 'Annotation Line' numbering, {sum(rep['internal_owned'].values())} "
        f"annotation-owned internal rows keep the (empty) internal shape "
        f"(owners: {rep['internal_owned']})",
        f"graphics: our discipline scheme by parent category (catalog.classify_category); "
        f"annotation-owned rows our annotation ink; pattern wiring kept "
        f"({rep['pattern_kept_builtin']} built-in / {rep['pattern_kept_element']} document patterns)",
    ]
    return RungPlan("Z_subcat", "the project SUB-CATEGORY layer (CategoryElem + GStyle rows) -> OUR vocabulary, IN PLACE",
                    plans, {"CategoryElem(family-scoped)": cat_fam,
                            "GStyleElem(family-scoped)": gs_fam}, notes, info=rep)


def plan_annot(parent: Parent) -> RungPlan:
    """Z_annot: the project annotation-attribute TYPES + every project
    FontElem.  Family-scoped copies (curtain constellation) and the placed
    LinearDimString (constraint content) are left with their reasons."""
    doc = parent.doc
    plans: Dict[int, Obj] = {}
    notes: List[str] = []
    left: Dict[str, List[int]] = {}
    st = ANNOTATION_STANDARD

    def fam_split(cls_name: str):
        return split_family_scoped(doc, parent.residue.get(cls_name, []))

    # --- DimensionStyle: the 4 secret internal styles (project) --------------
    ds_proj, ds_fam = fam_split("DimensionStyle")
    for e in ds_proj:
        plans[e] = inplace_secret_dimension_style(parent.value(e))
    left["DimensionStyle(family-scoped)"] = ds_fam
    notes.append(f"DimensionStyle: {len(ds_proj)} project = the SECRET INTERNAL temporary-dimension "
                 f"styles (roles {[ _name_of(parent.value(e))[:26] for e in ds_proj]}) -> our name "
                 f"tokens + our annotation values on the format machinery (overlay); "
                 f"{len(ds_fam)} family-scoped 'Diameter' styles left (curtain)")
    # --- LeaderStyle: 4 secret internal arrowheads + real arrowheads -----------
    ls_proj, ls_fam = fam_split("LeaderStyle")
    for e in ls_proj:
        plans[e] = inplace_arrowhead(parent.value(e))
    left["LeaderStyle(family-scoped)"] = ls_fam
    notes.append(f"LeaderStyle: {len(ls_proj)} project arrowheads -> ours "
                 f"({sum(1 for e in ls_proj if _name_of(parent.value(e)).startswith('SecretInternal'))} "
                 f"secret internal keep their role token, the rest become {st['arrowhead']['name']!r})")
    # --- GridAttributes ------------------------------------------------------------
    ga_proj, ga_fam = fam_split("GridAttributes")
    for e in ga_proj:
        v = parent.value(e)
        lt = v.get("m_lineAndTextAttr") or {}
        gh = st["grid_head"]
        plans[e] = grid_head_type(gh["name"], font_id=int(lt.get("m_fontId", -1)),
                                  line_category_id=int(lt.get("m_categoryId", -1)),
                                  leader_category_id=int(v.get("m_leaderCategoryId", -1)),
                                  center_segment_category_id=int(v.get("m_categoryForCenterSegment", -1)),
                                  bubble_end1=gh["bubble_end1"], bubble_end2=gh["bubble_end2"],
                                  center_segment_style=gh["center_segment_style"],
                                  end_segments_length_mm=gh["end_segments_length_mm"],
                                  family_tag_id=INVALID, elem_id=e,
                                  design_option=int(v.get("m_designOptionId", NO_DESIGN_OPTION)),
                                  cells=v.get("m_cellList"))
    left["GridAttributes(family-scoped)"] = ga_fam
    # --- InteriorElevAttributes ------------------------------------------------------
    ie_proj, ie_fam = fam_split("InteriorElevAttributes")
    for e in ie_proj:
        v = parent.value(e)
        lt = v.get("m_lineAndTextAttr") or {}
        el = st["interior_elevation"]
        plans[e] = interior_elevation_type(el["name"], font_id=int(lt.get("m_fontId", -1)),
                                           line_category_id=int(lt.get("m_categoryId", -1)),
                                           shape=el["shape"], width_mm=el["width_mm"],
                                           arrow_angle_deg=el["arrow_angle_deg"],
                                           arrow_filled=el["arrow_filled"],
                                           text_pos=el["text_position"],
                                           view_name_pos=el["view_name_position"],
                                           reference_label_pos=el["reference_label_pos"],
                                           show_view_name=el["show_view_name"],
                                           elevation_symbol_id=INVALID, elem_id=e,
                                           design_option=int(v.get("m_designOptionId", NO_DESIGN_OPTION)),
                                           cells=v.get("m_cellList"))
    left["InteriorElevAttributes(family-scoped)"] = ie_fam
    # --- CalloutTag ------------------------------------------------------------------------
    ct_proj, ct_fam = fam_split("CalloutTag")
    for e in ct_proj:
        v = parent.value(e)
        ch = st["callout_head"]
        plans[e] = callout_head_type(ch["name"], corner_radius_mm=ch["corner_radius_mm"],
                                     family_tag_id=INVALID, elem_id=e,
                                     design_option=int(v.get("m_designOptionId", NO_DESIGN_OPTION)),
                                     cells=v.get("m_cellList"))
    left["CalloutTag(family-scoped)"] = ct_fam
    notes.append(f"grid head types {len(ga_proj)} -> {st['grid_head']['name']!r}; interior-elevation "
                 f"markers {len(ie_proj)} -> {st['interior_elevation']['name']!r}; callout heads "
                 f"{len(ct_proj)} -> {st['callout_head']['name']!r} (family symbols -1: family-free "
                 f"base); family-scoped {len(ga_fam) + len(ie_fam) + len(ct_fam)} left (curtain)")
    # --- FontElem: every PROJECT font (each owned by an annotation type) --------
    fo_proj, fo_fam = fam_split("FontElem")
    font_sizes = {"GridAttributes": st["grid_head"]["text_mm"],
                  "InteriorElevAttributes": st["interior_elevation"]["text_mm"],
                  "DimensionStyle": st["secret_dim_font_mm"], "LevelAttributes": 3.5,
                  "SectionAttributes": 2.5, "AreaReportSettingsElem": 2.5}
    owners_by_class = collections.Counter()
    for e in fo_proj:
        v = parent.value(e)
        oc = parent.cls_of.get(int(v.get("m_ownerId", INVALID)), "?")
        owners_by_class[oc] += 1
        plans[e] = inplace_font(v, size_mm=float(font_sizes.get(oc, 2.5)))
    left["FontElem(family-scoped)"] = fo_fam
    notes.append(f"FontElem: {len(fo_proj)} project fonts -> our face '{st['font']}' at our per-owner "
                 f"sizes (owners {dict(owners_by_class)}); the {len(fo_fam)} family-scoped fonts "
                 "(3 per curtain family) left")
    # --- LinearDimString (content): left, with its reason ---------------------
    lds = parent.residue.get("LinearDimString", [])
    if lds:
        left["LinearDimString(content)"] = list(lds)
        notes.append(f"LinearDimString {lds}: {NON_INPLACE['LinearDimString']}")
    return RungPlan("Z_annot", "the project annotation-attribute types (dim styles / arrowheads / grid head / elevation marker / callout head) + ALL project fonts -> OURS, IN PLACE",
                    plans, left, notes,
                    info={"font_owner_classes": dict(owners_by_class),
                          "roles_dim": [_name_of(parent.value(e))[:28] for e in ds_proj],
                          "roles_arrow": [_name_of(parent.value(e))[:30] for e in ls_proj]})


def plan_datum(parent: Parent) -> RungPlan:
    """Z_datum: the residue GRIDS -> our gridline bay (our names + our
    geometry: no referrer beyond the plan's ExtentElem), the 7 plan-less
    surplus LEVELS -> our datum vocabulary (our names always; our elevation
    only where nothing references the level -- a referenced datum keeps the
    sample elevation, since moving it moves the sketch planes / plans hosted
    on it, reported per level).  The placed room / boundary / legend content
    is LEFT (removal candidates: :data:`NON_INPLACE`)."""
    from . import skeleton as SK
    doc = parent.doc
    plans: Dict[int, Obj] = {}
    notes: List[str] = []
    left: Dict[str, List[int]] = {}
    info: Dict[str, Any] = {"levels": [], "grids": []}
    # ---- grids -------------------------------------------------------------------
    grids = parent.residue.get("Grid", [])
    if grids:
        # our bay: same count, along the sample bay's axis / spacing sign, at OUR
        # module + OUR names + OUR elevation
        first = parent.value(grids[0])
        surf = ((first.get("m_pSurface") or {}).get("value") or {})
        origin = surf.get("m_origin") or [0.0, 0.0, 0.0]
        xvec = surf.get("m_xVec") or [1.0, 0.0, 0.0]
        attr_id = int(first.get("m_attrId", -1))
        module_ft = mm(GRID_CONVENTION["module_m"] * 1000.0)
        length_ft = mm(GRID_CONVENTION["line_length_m"] * 1000.0)
        elev_ft = mm(GRID_CONVENTION["elevation_m"] * 1000.0)
        # unit direction of the sample lines (kept: the bay's ORIENTATION is the
        # model's; the module / length / names / elevation are ours)
        ux, uy = float(xvec[0]), float(xvec[1])
        n = math.hypot(ux, uy) or 1.0
        ux, uy = ux / n, uy / n
        px, py = -uy, ux                                           # perpendicular (bay direction)
        for i, e in enumerate(sorted(grids)):
            cx = float(origin[0]) + px * module_ft * i * -1.0     # step the bay opposite to +perp
            cy = float(origin[1]) + py * module_ft * i * -1.0
            p0 = (cx - ux * length_ft / 2.0, cy - uy * length_ft / 2.0)
            p1 = (cx + ux * length_ft / 2.0, cy + uy * length_ft / 2.0)
            nm_ = GRID_CONVENTION["names"][i] if i < len(GRID_CONVENTION["names"]) else str(i + 1)
            o = new_grid(nm_, p0, p1, attr_id=attr_id, elevation_ft=elev_ft, elem_id=e)
            refs = sorted(parent.referrers(e))
            o.notes.append(f"replaces grid {parent.value(e).get('m_text')!r}; referrers "
                           f"{[(r, parent.cls_of.get(r)) for r in refs][:4]}")
            plans[e] = o
            info["grids"].append({"slot": e, "old_name": parent.value(e).get("m_text"), "our_name": nm_,
                                  "referrers": [(r, parent.cls_of.get(r)) for r in refs]})
        notes.append(f"grids {len(grids)} -> our bay {[g['our_name'] for g in info['grids']]} at our "
                     f"{GRID_CONVENTION['module_m']} m module, {GRID_CONVENTION['line_length_m']} m long, "
                     f"our elevation {GRID_CONVENTION['elevation_m']} m; the sample bay's orientation "
                     "+ its GridAttributes type wiring kept (referrers: the plan's ExtentElem only)")
    # ---- surplus levels ------------------------------------------------------------
    levels = parent.residue.get("Level", [])
    # pair OUR datum vocabulary to the surplus levels BY ELEVATION RANK (lowest
    # sample datum -> our lowest name), spreading our vocabulary over the
    # sample's count so the top datum gets a top name
    vocab = sorted(LEVEL_VOCABULARY, key=lambda t: t[1])
    lv_sorted = sorted(levels, key=lambda ee: float(
        (((parent.value(ee).get("m_pSurface") or {}).get("value") or {}).get("m_origin") or [0, 0, 0])[2]))
    span = max(1, len(lv_sorted) - 1)
    for i, e in enumerate(lv_sorted):
        v = parent.value(e)
        refs = sorted(parent.referrers(e))
        ref_classes = collections.Counter(parent.cls_of.get(r) for r in refs)
        keep_elev = bool(refs)                                     # referenced datum: keep the elevation
        surf = ((v.get("m_pSurface") or {}).get("value") or {})
        cur_z = float((surf.get("m_origin") or [0, 0, 0])[2])
        vi = int(round(i * (len(vocab) - 1) / span)) if len(lv_sorted) > 1 else 0
        our_nm, our_elev_m = vocab[vi]
        elev_ft = cur_z if keep_elev else mm(our_elev_m * 1000.0)
        env = ((surf.get("m_Envelope") or {}).get("m_corners") or [[-50, -50], [50, 50]])
        se = SK.new_level(int(e), gen(our_nm) if not our_nm.startswith(PREFIX) else our_nm,
                          elev_ft, int(v.get("m_attrId", -1)),
                          extent_ft=((float(env[0][0]), float(env[0][1])),
                                     (float(env[1][0]), float(env[1][1]))))
        ours = _deep(se.obj)
        # keep the slot's regen wiring + datum-line ends + geom apparatus flavour:
        # our name (+ our elevation when free) is the definitional layer of a
        # LEVEL; everything else is the DatumPlane machinery both share
        for f in ("m_pParamValueSetInt", "m_pParamValueSetElementId", "m_pParamValueSetDouble",
                  "m_pParamValueSetAString", "m_cellList", "m_designOptionId",
                  "m_freeEnd", "m_bubbleEnd", "m_cutVec", "m_refPointsForNewViews",
                  "m_genDbViewId", "m_v2Datum", "m_useConstVForDatumLine3dRep",
                  "m_isBuildingStory", "m_roomComputationElevationOffset",
                  "m_geomSteps", "m_pGeomTable", "m_sheetTextHeight", "m_pLeader"):
            if f in v:
                ours[f] = _deep(v[f])
        if keep_elev:
            for f in ("m_pFace", "m_pSurface"):
                ours[f] = _deep(v[f])
        ours["m_text"] = gen(our_nm)
        o = Obj("Level", class_id("Level"), ours,
                ours=["m_text (name)"] + ([] if keep_elev else ["m_pSurface / m_pFace origin z (elevation)"]),
                notes=[f"replaces level {v.get('m_text')!r} (z {cur_z:.3f} ft): our name "
                       f"{gen(our_nm)!r}" + (f", elevation KEPT (referenced by {dict(ref_classes)})"
                                             if keep_elev else f", our elevation {our_elev_m} m")])
        plans[e] = o
        info["levels"].append({"slot": e, "old_name": v.get("m_text"), "our_name": gen(our_nm),
                               "old_z_ft": cur_z, "our_elevation_applied": not keep_elev,
                               "referrers": dict(ref_classes)})
    if levels:
        free_lv = sum(1 for lv in info["levels"] if lv["our_elevation_applied"])
        notes.append(f"surplus levels {len(levels)} -> our datum vocabulary names; our elevation applied "
                     f"to {free_lv} un-referenced level(s), the rest keep the sample elevation "
                     "(hosted sketch planes / plan clips would move -- honest limit of an in-place probe)")
    # ---- placed content: left with reasons ---------------------------------------------
    for cls_name in ("CurveElem", "LegendComponent", "LevelRoomPlan"):
        ids = parent.residue.get(cls_name, [])
        if ids:
            left[f"{cls_name}(content)"] = list(ids)
            notes.append(f"{cls_name} {len(ids)}: {NON_INPLACE[cls_name]}")
    return RungPlan("Z_datum", "the residue GRIDS -> our gridline bay + the 7 surplus levels -> our datum vocabulary, IN PLACE",
                    plans, left, notes, info=info)


def plan_pattern(parent: Parent) -> RungPlan:
    """Z_pattern: the SURPLUS fill / line patterns (beyond the palette Y7
    landed) -> OUR extra house patterns, in place (their referrers -- the
    materials' cut / surface patterns and gstyle rows -- keep pointing at the
    same ids, which now carry OUR pattern)."""
    plans: Dict[int, Obj] = {}
    notes: List[str] = []
    info: Dict[str, Any] = {"fill": [], "line": []}
    for i, e in enumerate(sorted(parent.residue.get("FillPatternElem", []))):
        spec = EXTRA_FILL_PATTERNS[i % len(EXTRA_FILL_PATTERNS)]
        v = parent.value(e)
        old = ((v.get("m_pFillPattern") or {}).get("value") or {})
        target = "model" if int(old.get("m_fpTarget", 0)) == 1 else "drafting"
        rec = new_fill_pattern(spec["name"], spec["grids"], elem_id=e, target=target)
        plans[e] = Obj("FillPatternElem", class_id("FillPatternElem"), _deep(rec.obj),
                       ours=["m_pFillPattern (name / grids / scale)"],
                       notes=[f"replaces fill pattern {old.get('m_name')!r} ({target}) with "
                              f"{spec['name']!r}"])
        info["fill"].append({"slot": e, "old_name": old.get("m_name"), "our_name": spec["name"],
                             "target": target})
    for i, e in enumerate(sorted(parent.residue.get("LinePatternElem", []))):
        spec = EXTRA_LINE_PATTERNS[i % len(EXTRA_LINE_PATTERNS)]
        v = parent.value(e)
        old = ((v.get("m_pLinePattern") or {}).get("value") or {})
        rec = new_line_pattern(spec["name"], spec["segments"], elem_id=e)
        plans[e] = Obj("LinePatternElem", class_id("LinePatternElem"), _deep(rec.obj),
                       ours=["m_pLinePattern (name / segments)"],
                       notes=[f"replaces line pattern {old.get('m_name')!r} with {spec['name']!r}"])
        info["line"].append({"slot": e, "old_name": old.get("m_name"), "our_name": spec["name"]})
    notes.append(f"surplus patterns: {len(info['fill'])} fill + {len(info['line'])} line -> our extra "
                 f"house patterns {[p['our_name'] for p in info['fill'] + info['line']]}")
    return RungPlan("Z_pattern", "the surplus fill / line patterns -> our extra house patterns, IN PLACE",
                    plans, {}, notes, info=info)


def plan_asset(parent: Parent) -> RungPlan:
    """Z_asset: the material APPEARANCE-ASSET companions -> our generic
    appearance palette, in place (their MaterialElem referrers keep pointing
    at the same ids, which now carry OUR appearance)."""
    prof = load_generic_asset_profile()
    plans: Dict[int, Obj] = {}
    info: Dict[str, Any] = {"assets": []}
    ids = sorted(parent.residue.get("AppearanceAssetElem", []))
    for i, e in enumerate(ids):
        spec = APPEARANCE_PALETTE[i % len(APPEARANCE_PALETTE)]
        v = parent.value(e)
        old_nm = ""
        asset_body = (((v.get("m_pAppearanceAsset") or {}).get("value") or {}).get("m_Asset") or {})
        for p in (asset_body.get("m_aAProperties") or []):
            if (p.get("value") or {}).get("m_sName") == "UIName":
                old_nm = str((p.get("value") or {}).get("m_value") or "")
        o = generic_appearance_asset(spec["name"], spec["rgb"], glossiness=spec.get("gloss", 0.4),
                                     transparency=spec.get("transparency", 0.0),
                                     is_metal=spec.get("is_metal", False), elem_id=e,
                                     description=f"our house appearance ({spec['key']})",
                                     keyword=f"materials:ours,{spec['key']}",
                                     profile=prof)
        refs = sorted(parent.referrers(e))
        o.notes.append(f"replaces appearance {old_nm!r}; material referrers "
                       f"{[(r, parent.cls_of.get(r)) for r in refs][:4]}")
        plans[e] = o
        info["assets"].append({"slot": e, "old_ui_name": old_nm, "our_name": spec["name"],
                               "referrers": [(r, parent.cls_of.get(r)) for r in refs]})
    notes = [f"appearance assets {len(ids)} -> our generic appearance palette (Protein "
             f"GenericSchema, frozen {len(prof.get('properties') or [])}-property skeleton, our "
             "colour / gloss / transparency); MaterialElem companions keep referencing the same ids"]
    return RungPlan("Z_asset", "the material appearance-asset companions -> our generic appearance palette, IN PLACE",
                    plans, {}, notes, info=info)


PLANNERS: Dict[str, Callable[[Parent], RungPlan]] = {
    "Z_subcat": plan_subcat, "Z_annot": plan_annot, "Z_datum": plan_datum,
    "Z_pattern": plan_pattern, "Z_asset": plan_asset,
}
#: ZA_deep = the cumulative rung (all single layers together), built LAST but
#: uploaded FIRST (bisection: a PASS proves every Group-A constructor)
RUNG_ORDER = ["Z_subcat", "Z_annot", "Z_datum", "Z_pattern", "Z_asset"]


# ===========================================================================
# 14. EMISSION + CERTIFICATION (the v3 in-place machinery, imported)
# ===========================================================================

def _v3():
    """The rebased ladder's own certification helpers (tools/genesis_
    substitute_v3.py) -- imported, never edited."""
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    import genesis_substitute_v3 as V3                                 # noqa: E402
    return V3


def selfcheck_plans(plans: Dict[int, Obj]) -> List[dict]:
    """Every constructed object must encode -> decode -> re-encode byte-
    exactly (the honesty gate; a failing object is a NOT-BUILT finding)."""
    fails = []
    for slot, o in plans.items():
        rep = check_object(o.class_name, o.value)
        if not rep["ok"]:
            fails.append({"slot": slot, **rep})
    return fails


def emit_rung(rung: RungPlan, parent: Parent, out_dir: str = RESIDUE_DIR, *,
              base_certification: Optional[dict] = None,
              control: Optional[dict] = None) -> dict:
    """Emit ``<out_dir>/<rung.name>.rvt`` = the CERTIFIED parent with the
    rung's slots substituted IN PLACE (seq-102 object only, keep_row) and
    write ``<rung.name>.json`` = the certification report: validator +
    structural proof + four-registry coherence + registry parity + the
    rvt.regdiff registration sample + the byte-delta-vs-parent assertion
    table (the v3 ladder's own certification, imported) + our per-class
    FIELD-DELTA table + the residue left in place with reasons."""
    from rvt import regadd
    V3 = _v3()
    t_all = time.time()
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, f"{rung.name}.rvt")
    log(f"\n== {rung.name} :: {rung.label}")
    log(f"   parent {os.path.relpath(parent.path, ROOT)}; slots {len(rung.plans)} "
        f"{rung.by_class}")
    report: Dict[str, Any] = {
        "rung": rung.name, "label": rung.label, "kind": "inplace",
        "mechanism": ("rvt.regadd.substitute_elements -- IN-PLACE, seq 102 (object record only), "
                      "keep_row=True (ElemTable row byte-identical), Global/Latest byte-identical; "
                      "nothing added, nothing deleted"),
        "base": {"file": os.path.relpath(parent.path, ROOT), "certification": base_certification},
        "control_to_upload_with_batch": control,
        "parent": os.path.relpath(parent.path, ROOT), "out": os.path.relpath(out, ROOT),
        "landed_by_class": rung.by_class, "notes": rung.notes, "info": rung.info,
        "residue_left_in_place": {k: {"count": len(v), "ids": v[:60],
                                      "reason": NON_INPLACE.get(k.split("(")[0], "family-scoped (curtain constellation)")}
                                  for k, v in rung.residue_left.items()},
    }
    # 1. self-check every object
    fails = selfcheck_plans(rung.plans)
    report["record_selfcheck"] = {"objects": len(rung.plans), "failures": fails}
    if fails:
        report["FAILED_SELF_CHECK"] = f"{len(fails)} constructed object(s) not schema-clean / byte-exact"
        report["verdict"] = "NOT-BUILT"
        _write_report(out_dir, rung.name, report)
        log(f"   *** {rung.name}: {report['FAILED_SELF_CHECK']} -- NO FILE EMITTED")
        for f in fails[:6]:
            log(f"      {f}")
        return report
    if not rung.plans:
        report["FAILED_SELF_CHECK"] = "no slots planned (the class layer does not exist in the parent)"
        report["verdict"] = "NOT-BUILT"
        _write_report(out_dir, rung.name, report)
        log(f"   *** {rung.name}: nothing to substitute")
        return report
    # 2. dangling-reference check: every id our objects reference must exist
    slots = set(rung.plans)
    live = set(int(e) for e in parent.doc.et_by_id)
    ted = None
    try:
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import genesis_substitute as GS                                # noqa: E402
        ted = GS.TypedEditor(decoder=parent.doc.dec, maps=None)
    except Exception:
        ted = None
    dangle = []
    if ted is not None:
        for slot, o in rung.plans.items():
            for lf in ted.leaves(o.value, o.class_name):
                v = lf.value
                if isinstance(v, int) and v > 0 and v not in live and lf.path not in ("m_id",):
                    dangle.append({"slot": slot, "path": lf.path, "target": v})
    report["new_object_reference_check"] = {"dangling": len(dangle), "examples": dangle[:12]}
    # (a dangling reference is REPORTED, not fatal: the certified bases carry
    #  thousands of tolerated danglers -- but ours are listed by construction)
    # 3. the in-place substitution
    t0 = time.time()
    srep = regadd.substitute_elements(
        parent.path, out,
        {int(slot): {102: o.as_tuple()} for slot, o in rung.plans.items()},
        seqs=(102,), keep_row=True, verify=True, diff=True)
    emit_s = round(time.time() - t0, 1)
    diff = srep.diff or {}
    pname = ((srep.emit or {}).get("partition")) or "Partitions/?"
    log(f"   emit: verdict {srep.verdict} problems {srep.problems}; streams differing "
        f"{(diff.get('streams') or {}).get('differing')} ({emit_s}s)")
    report["substitute"] = {
        "op": srep.op, "verdict": srep.verdict, "problems": srep.problems,
        "seqs_replaced": srep.seqs_replaced,
        "elemtable_rows": (srep.emit or {}).get("elemtable_count"),
        "elemtable_rewritten": (srep.emit or {}).get("elemtable_rewritten"),
        "latest_rewritten": (srep.emit or {}).get("latest_rewritten"),
        "seconds": emit_s,
    }
    # 4. certification (the v3 ladder's own helpers)
    byte_delta = V3._byte_delta_assertions(diff, slots=slots, seqs=(102,), partition_name=pname)
    ctx_stub = _CtxStub(parent)
    parity = V3._parity_report(ctx_stub, slots,
                               latest_identical=bool((diff.get("latest") or {}).get("identical")))
    reg_sample = V3._registration_diff_sample(parent.path, out, sorted(slots), limit=6)
    try:
        import genesis_triage as GT                                    # noqa: E402
        cen = GT.census(out)
    except Exception as ex:                                        # pragma: no cover
        cen = {"error": repr(ex)[:300]}
    coherence = {
        "save_units": cen.get("save_units"), "contentdocs_entries": cen.get("contentdocs_entries"),
        "contenttable_records": cen.get("contenttable_records"),
        "adocument_clean": cen.get("adocument_clean"),
        "coherent": (cen.get("save_units") is not None
                     and cen.get("save_units", 0) - 1 == cen.get("contentdocs_entries")
                     == cen.get("contenttable_records")),
    }
    report["byte_delta"] = byte_delta
    report["parity"] = parity
    report["registration_diff_sample"] = reg_sample
    report["validator"] = srep.validator
    report["structural"] = srep.structural
    report["census"] = {k: cen.get(k) for k in ("path", "elements", "file_size", "save_units",
                                                   "contentdocs_entries", "contenttable_records",
                                                   "adocument_clean") if k in cen}
    report["coherence"] = coherence
    # 5. the field-delta table (which fields are OURS, per class)
    delta_by_class: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for slot, o in rung.plans.items():
        old = parent.value(slot)
        for path in field_delta(old, o.value):
            delta_by_class[o.class_name][path] += 1
    report["field_delta_by_class"] = {
        c: {"slots": rung.by_class.get(c),
            "differing_field_paths": dict(cnt.most_common(24)),
            "declared_ours": sorted({f for s, ob in rung.plans.items() if ob.class_name == c
                                     for f in ob.ours})[:40]}
        for c, cnt in delta_by_class.items()}
    report["landed_slots"] = [{"slot": s, "class": o.class_name} for s, o in sorted(rung.plans.items())]
    report["object_notes_sample"] = [{"slot": s, "class": o.class_name, "notes": o.notes}
                                     for s, o in list(sorted(rung.plans.items()))[:20]]
    # 6. verdict
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
    if dangle:
        report.setdefault("warnings", []).append(f"{len(dangle)} reference(s) in our objects point at "
                                                f"ids not present in the parent (listed)")
    report["problems"] = problems
    report["verdict"] = "VALID" if not problems else "NOT-CLEAN"
    if problems:
        report["FAILED_SELF_CHECK"] = "; ".join(problems)
    report["bytes"] = os.path.getsize(out) if os.path.exists(out) else None
    report["seconds"] = round(time.time() - t_all, 1)
    _write_report(out_dir, rung.name, report)
    log(f"   byte-delta: only-partition {byte_delta['only_partition_differs']}; changed "
        f"{byte_delta['records_changed_count']} of {byte_delta['expected_slots']} slots "
        f"(unchanged {byte_delta['landed_but_unchanged_slots']}); ElemTable identical "
        f"{byte_delta['elemtable_identical']}; ADocument identical {byte_delta['adocument_identical']}")
    log(f"   validator: {'VALID' if val.get('ok') else 'INVALID'} errors={val.get('errors')} "
        f"warnings={val.get('warnings')}; structural ok={(srep.structural or {}).get('ok')}; "
        f"coherence {coherence['save_units']}/{coherence['contentdocs_entries']}/"
        f"{coherence['contenttable_records']}; regdiff sample "
        f"{sum(1 for r in reg_sample if r.get('registration_identical'))}/{len(reg_sample)} identical")
    log(f"   field-delta: {json.dumps({c: v['differing_field_paths'] for c, v in report['field_delta_by_class'].items()}, default=str)[:600]}")
    log(f"   -> {os.path.relpath(out, ROOT)} {report['bytes']:,} B  VERDICT {report['verdict']}"
        f"{('  *** ' + report['FAILED_SELF_CHECK']) if problems else ''} ({report['seconds']}s)")
    for m in (val.get("error_messages") or [])[:4]:
        log(f"      ERROR {m}")
    return report


class _CtxStub:
    """The two fields v3's ``_parity_report`` reads (ted_adoc + tree)."""

    def __init__(self, parent: Parent):
        sys.path.insert(0, os.path.join(ROOT, "tools"))
        import genesis_substitute as GS                                # noqa: E402
        import genesis_assemble as GA                                  # noqa: E402
        from rvt import adocument as adoc
        from rvt.container import open_rvt
        with open_rvt(parent.path) as f:
            payload = f.inflate(adoc.STREAM, 0)
        a = adoc.decode_latest(payload)
        self.tree = a.value
        self.maps = GA.load_registry_maps()
        self.ted_adoc = GS.TypedEditor(decoder=None, maps=self.maps)


def _write_report(out_dir: str, name: str, rep: dict) -> None:
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"{name}.json"), "w") as fh:
        json.dump(rep, fh, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o))


# ===========================================================================
# 15. THE LADDER DRIVER + probes.json
# ===========================================================================

def merge_plans(plans: Sequence[RungPlan]) -> RungPlan:
    """ZA_deep = every single-layer plan applied together (slots are
    disjoint by class layer; a collision would be a planning defect)."""
    merged: Dict[int, Obj] = {}
    left: Dict[str, List[int]] = {}
    notes: List[str] = []
    info: Dict[str, Any] = {}
    for p in plans:
        for slot, o in p.plans.items():
            if slot in merged:
                raise RuntimeError(f"slot {slot} planned by two rungs ({merged[slot].class_name} / {o.class_name})")
            merged[slot] = o
        for k, v in p.residue_left.items():
            left.setdefault(k, []).extend(v)
        notes.append(f"[{p.name}] {p.notes[0] if p.notes else ''}")
        info[p.name] = {"slots": len(p.plans), "by_class": p.by_class}
    return RungPlan("ZA_deep", "Y9 + ALL Group-A residue layers (subcategory + annotation types/fonts + datum + patterns + appearance assets), IN PLACE",
                    merged, left, notes, info=info)


def write_probes_manifest(reports: Dict[str, dict], parent_path: str = DEFAULT_PARENT,
                          out_dir: str = RESIDUE_DIR, *, base_cert: Optional[dict] = None,
                          control: Optional[dict] = None, curtain: Optional[dict] = None) -> str:
    """probes.json for this stream's batch: ZA_deep FIRST (bisection), then
    the single-layer probes, each naming its CERTIFIED base (Y9), the
    control to upload with the batch, the ONE thing it tests and the
    interpretation of each verdict.  Ordered by information value."""
    order = ["ZA_deep"] + RUNG_ORDER
    entries: List[dict] = []
    for i, name in enumerate(order, 1):
        rep = reports.get(name) or {}
        if not rep:
            continue
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        entries.append({
            "order": i, "rung": name,
            "file": f"{os.path.relpath(out_dir, ROOT)}/{name}.rvt",
            "class_layer_substituted": rep.get("label"),
            "base": {"file": os.path.relpath(parent_path, ROOT), "certification": base_cert},
            "derived_from": os.path.relpath(parent_path, ROOT),
            "passing_sibling": ("Y9 (the certified deepest rung, this probe's parent) -- PASS-parent "
                                "+ FAIL-here convicts exactly THIS class layer"),
            "the_ONE_thing_it_tests": _rung_tests(name),
            "if_PASS": _rung_if_pass(name), "if_FAIL": _rung_if_fail(name),
            "mechanism": rep.get("mechanism"),
            "elements_substituted_in_place": {"landed": len(rep.get("landed_slots") or []),
                                              "by_class": rep.get("landed_by_class")},
            "residue_left_in_place": {k: v.get("count") for k, v in (rep.get("residue_left_in_place") or {}).items()},
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
        "stream": "genesis-residue-A (RESIDUE CONSTRUCTORS, GROUP A -- datum / annotation / type-layer buckets)",
        "situation": (
            "ORCHESTRATOR VERDICT #17 (2026-08-04): the substitution ladder rebased on the CERTIFIED "
            "family-free base K4 as PURE IN-PLACE substitution took K4 to Y9 -- settings + catalog + "
            "palette + datum + view constellations ALL our constructors' output -- and Y9 / Y1 / Y_cat "
            "ALL LOAD.  The residue census (Yn) lists 2,009 K4 elements still Autodesk's in 11 "
            "buckets.  THIS batch retires Group A's buckets (classes sorting A..L in the datum / "
            "annotation / type-layer families): each rung substitutes ONE residue class layer of "
            "the CERTIFIED Y9 in place with OUR constructors' objects; ZA_deep is all of them at once."),
        "the_operation": (
            "In-place substitution (rvt.regadd.substitute_elements): our constructor's OBJECT record "
            "(seq-102) replaces the sample's at the SAME element id -- same ElemTable row, same record "
            "position, same registry slots; Global/Latest + Global/ElemTable BYTE-IDENTICAL to Y9; "
            "nothing added, nothing deleted.  Every rung asserts validator 0 errors, the structural "
            "proof, four-registry coherence, registry parity (by construction), a rvt.regdiff "
            "registration-diff sample, the regadd byte-delta table (ONLY the landed slots' object "
            "records change) AND a per-class FIELD-DELTA table naming which object fields carry OUR "
            "value vs the slot's own machinery / wiring."),
        "base": {"file": os.path.relpath(parent_path, ROOT), "certification": base_cert,
                 "lineage": ("Y9 = the certified deepest rung of the rebased in-place ladder: K4 (certified "
                             "family-free base) + our settings / catalog / palette / datum / view "
                             "constructors in place -- viewer PASS (docs/coverage/viewer-certified.json)")},
        "standing_control": control or {"note": "not staged (stage with tools/probe_batch.py)"},
        "controls_discipline": (
            "Upload the batch with the certified CONTROL (a byte-identical copy of a certified file: "
            "CTRL_K4_base.rvt is staged next to the Y probes; tools/probe_batch.py stage adds one "
            "automatically). If the CONTROL fails, the batch is VOID and nothing about our "
            "constructors is read from it."),
        "upload_order_bisection_first": [e["rung"] for e in entries],
        "reading_the_results": {
            "how": ("ZA_deep is the cumulative rung: PASS => every Group-A residue constructor "
                    "(subcategory vocabulary, annotation types + fonts, grids + levels, extra "
                    "patterns, appearance assets) loads at Autodesk's registrations, and only the "
                    "listed content / curtain removal queues + Group B remain.  ZA_deep FAIL => "
                    "read the singles: the first FAIL whose parent (Y9) PASSED convicts exactly that "
                    "rung's class layer (named in 'class_layer_substituted'), every registration "
                    "variable already eliminated by construction."),
            "Z_subcat FAIL": "our sub-category NAMES / pens / colours at Autodesk's sub-category registrations are the objection (the X6b layer, isolated).",
            "Z_annot FAIL": "one of our annotation-type constructors (secret dim styles / arrowheads / grid head / elevation marker / callout head / fonts) is rejected -- bisect fonts vs the types (two single-layer probes).",
            "Z_datum FAIL": "our grid line objects (datum-plane geometry) or our level names / elevations are rejected -- bisect grids vs levels.",
            "Z_pattern FAIL": "our extra fill / line pattern objects are rejected (the palette question, extended).",
            "Z_asset FAIL": "our Protein GenericSchema appearance-asset objects are rejected -- the frozen property skeleton or a free value; the counsel item stays open either way.",
        },
        "curtain_constellation_removal_candidate": (
            {"count": curtain.get("count"), "families": [f["name"] for f in curtain.get("families", [])],
             "by_class": curtain.get("by_class"), "note": curtain.get("note")} if curtain else None),
        "probes": entries,
        "derivation_chain": ["ZA_deep <- Y9 (all layers)"] + [f"{n} <- Y9 (single layer)" for n in RUNG_ORDER],
    }
    p = os.path.join(out_dir, "probes.json")
    os.makedirs(out_dir, exist_ok=True)
    with open(p, "w") as fh:
        json.dump(manifest, fh, indent=1, default=str)
    log(f"\n[probes] wrote {os.path.relpath(p, ROOT)} ({len(entries)} entries)")
    return p


def _rung_tests(name: str) -> str:
    return {
        "ZA_deep": ("Whether the reader accepts ALL Group-A residue constructors at once: our sub-category "
                    "vocabulary, our annotation types + every project font, our grids + surplus levels, "
                    "our extra patterns, our appearance assets -- at Autodesk's own registrations, in the "
                    "certified Y9."),
        "Z_subcat": ("Whether the reader accepts OUR project SUB-CATEGORY layer (169 CategoryElems + 246 "
                     "GStyle rows: our names, our pens / colours) at Autodesk's sub-category registrations "
                     "-- the X6b gap, isolated on a certified base."),
        "Z_annot": ("Whether the reader accepts OUR annotation-attribute TYPES (4 secret internal dimension "
                    "styles + 5 arrowheads + grid head + interior-elevation marker + callout head) and OUR "
                    "11 project fonts at Autodesk's registrations."),
        "Z_datum": ("Whether the reader accepts OUR datum CONTENT objects: 3 grid lines (our datum-plane "
                    "geometry constructor) + 7 renamed surplus levels."),
        "Z_pattern": ("Whether the reader accepts OUR extra fill / line pattern objects at the sample's "
                      "surplus pattern registrations."),
        "Z_asset": ("Whether the reader accepts OUR Protein GenericSchema appearance-asset objects (frozen "
                    "property skeleton + our colour / gloss values) at the sample's asset registrations."),
    }[name]


def _rung_if_pass(name: str) -> str:
    return {
        "ZA_deep": ("EVERY Group-A residue constructor loads: the datum / annotation / type-layer buckets "
                    "of Yn are retired; what remains of Group A is the curtain-constellation removal "
                    "queue + the content-removal queue (both listed with exact ids)."),
        "Z_subcat": "Our sub-category vocabulary + graphics are reader-accepted: the X6b gap is closed on a certified base.",
        "Z_annot": "Our annotation-type + font constructors are reader-accepted (family-free annotation heads legal).",
        "Z_datum": "Our grid constructor (datum-plane content) + our level naming are reader-accepted -- grids are the first CONTENT class our constructors own.",
        "Z_pattern": "Our extra pattern objects are reader-accepted (the palette layer extends freely).",
        "Z_asset": "Our appearance-asset constructor (Protein GenericSchema skeleton + our values) is reader-accepted.",
    }[name]


def _rung_if_fail(name: str) -> str:
    return {
        "ZA_deep": "Read the five singles (all from Y9): the failing single names the rejected constructor.",
        "Z_subcat": ("Our sub-category NAMES or pen / colour values are the objection: diff a rejected row vs "
                     "the base's (report field_delta_by_class) -- names are the only new variable "
                     "(structural profile + wiring are the slot's)."),
        "Z_annot": ("One of the annotation-type / font constructors is rejected -- the report's per-class "
                    "field-delta names the candidate fields; bisect fonts vs types next."),
        "Z_datum": ("Our grid datum-plane objects or the renamed / re-elevated levels are rejected -- "
                    "bisect grids vs levels; a grid FAIL points at our new_grid geometry constructor."),
        "Z_pattern": "Our extra pattern objects are rejected -- diff vs Y7's accepted palette patterns.",
        "Z_asset": ("Our appearance-asset objects are rejected -- the frozen skeleton misses a required "
                    "property or a free value's grammar; the asset-descriptor counsel item stays open."),
    }[name]


def run_ladder(parent_path: str = DEFAULT_PARENT, out_dir: str = RESIDUE_DIR, *,
               only: Sequence[str] = (), skip_deep: bool = False) -> Dict[str, dict]:
    """Build the whole Group-A Z-ladder from the CERTIFIED parent (default
    Y9): each single-layer rung (each derived DIRECTLY from the parent) +
    ZA_deep (all layers together), then probes.json (bisection-first) and
    the curtain constellation report.  Returns {rung: report}."""
    V3 = _v3()
    os.makedirs(out_dir, exist_ok=True)
    base_cert = V3.certification_of(parent_path)
    if base_cert is None:
        raise RuntimeError(f"{os.path.relpath(parent_path, ROOT)} is NOT viewer-certified -- a Z rung "
                           "may only derive from a CERTIFIED file (verdict #15)")
    log(f"[base] {os.path.relpath(parent_path, ROOT)} -- CERTIFIED: {str(base_cert.get('proves'))[:140]}")
    control = None
    if os.path.exists(CTRL_K4):
        control = {"file": os.path.relpath(CTRL_K4, ROOT),
                   "note": "the ladder's standing certified control (md5-identical to K4); upload with EVERY batch",
                   "certification": V3.certification_of(os.path.join(ROOT, "experiments", "genesis", "triage", "K4.rvt"))}
        log(f"[control] {control['file']} (the certified K4 copy) -- upload with EVERY batch")
    t0 = time.time()
    parent = Parent(parent_path)
    log(f"[parent] {len(parent.doc.et_by_id):,} host elements; ladder-landed {len(parent.landed):,}; "
        f"residue classes {len(parent.residue)} ({parent.seconds}s)")
    # curtain constellation census (the removal queue this stream hands over)
    curtain = curtain_constellation(parent.state)
    with open(os.path.join(out_dir, "curtain_constellation.json"), "w") as fh:
        json.dump(curtain, fh, indent=1)
    log(f"[curtain] {curtain['count']} elements in the 8 curtain-SYSTEM-family constellation "
        f"(coherent-removal candidate): {curtain['by_class']}")
    want = [s.strip() for s in only if s.strip()]
    reports: Dict[str, dict] = {}
    plans: List[RungPlan] = []
    for name in RUNG_ORDER:
        if want and name not in want and "ZA_deep" not in want:
            continue
        t1 = time.time()
        plan = PLANNERS[name](parent)
        log(f"[plan] {name}: {len(plan.plans)} slots {plan.by_class} ({round(time.time() - t1, 1)}s)")
        plans.append(plan)
        if not want or name in want:
            reports[name] = emit_rung(plan, parent, out_dir, base_certification=base_cert, control=control)
    if not skip_deep and (not want or "ZA_deep" in want):
        deep = merge_plans(plans)
        reports["ZA_deep"] = emit_rung(deep, parent, out_dir, base_certification=base_cert, control=control)
    write_probes_manifest(reports, parent_path, out_dir, base_cert=base_cert, control=control,
                          curtain=curtain)
    if "ZA_deep" in reports and (reports["ZA_deep"] or {}).get("verdict") == "VALID":
        zn = residue_after_deep()
        log(f"[Zn] after ZA_deep: {zn['residue_elements']} residue elements in "
            f"{zn['residue_classes']} classes; by disposition {zn['totals_by_disposition']}")
    log("\n=== GROUP-A RESIDUE LADDER SUMMARY ===")
    for name in ["ZA_deep"] + RUNG_ORDER:
        rep = reports.get(name)
        if not rep:
            continue
        v = rep.get("validator") or {}
        bd = rep.get("byte_delta") or {}
        log(f"  {name:<9} {rep.get('verdict', '?'):<9} validator ok={v.get('ok')} errors={v.get('errors')} "
            f"landed {len(rep.get('landed_slots') or [])} {rep.get('landed_by_class')}  changed "
            f"{bd.get('records_changed_count', '-')}  latest-identical {bd.get('adocument_identical', '-')}  "
            f"{rep.get('bytes', 0) or 0:>9,} B")
    log(f"total {time.time() - t0:.1f}s")
    return reports


def residue_after_deep(deep_rvt: str = os.path.join(RESIDUE_DIR, "ZA_deep.rvt"),
                       deep_report: str = os.path.join(RESIDUE_DIR, "ZA_deep.json"),
                       *, save: bool = True) -> dict:
    """The Zn CENSUS: which elements of the deepest Group-A rung (ZA_deep) are
    STILL AUTODESK'S -- the Y-ladder's landed slots + ZA_deep's landed slots
    vs the file's host elements -- bucketed by class, with our disposition per
    class (Group B's, curtain constellation, content removal, other streams'
    catalog / product / misc buckets).  The honest 'what is left' after this
    stream, written to ``<RESIDUE_DIR>/residue_after_ZA_deep.json``."""
    from ..mutate import Document
    landed = ladder_landed(extra_reports=[deep_report])
    doc = Document.from_file(deep_rvt)
    counts: collections.Counter = collections.Counter()
    for e in doc.et_by_id:
        if int(e) not in landed:
            counts[doc.class_of(int(e)) or "?"] += 1
    claimed = {c for cs in CLAIMED_CLASSES.values() for c in cs}
    disp: Dict[str, str] = {}
    for c in counts:
        if c in GROUP_B_CLASSES:
            disp[c] = "GROUP B (M..Z counterpart / definitions / other families)"
        elif c in NON_INPLACE:
            disp[c] = "Group A NON-INPLACE (curtain constellation / placed content) -- removal queue"
        elif c in claimed:
            disp[c] = "Group A claimed class -- family-scoped remainder (curtain constellation)"
        else:
            disp[c] = "outside both charters (product data / catalog rungs / misc machinery / external link)"
    rep = {
        "subject": os.path.relpath(deep_rvt, ROOT),
        "elements": len(doc.et_by_id),
        "landed_ours": sum(1 for e in doc.et_by_id if int(e) in landed),
        "residue_elements": sum(counts.values()),
        "residue_classes": len(counts),
        "residue_by_class": {c: {"count": n, "disposition": disp[c]}
                             for c, n in counts.most_common()},
        "totals_by_disposition": dict(collections.Counter(
            {d: sum(counts[c] for c in counts if disp[c] == d) for d in set(disp.values())})),
    }
    if save:
        os.makedirs(RESIDUE_DIR, exist_ok=True)
        with open(os.path.join(RESIDUE_DIR, "residue_after_ZA_deep.json"), "w") as fh:
            json.dump(rep, fh, indent=1)
    return rep


# ===========================================================================
# 16. CENSUS REPORT + DEMO
# ===========================================================================

def census_report(parent_path: str = DEFAULT_PARENT, *, save: bool = True) -> dict:
    """The residue census this stream works from: per claimed class the
    residue count, its project / family-scoped split, plus the curtain
    constellation and the content-removal queue.  Written to
    ``<RESIDUE_DIR>/residue_census.json``."""
    parent = Parent(parent_path)
    doc = parent.doc
    rows = {}
    claimed = sorted({c for cs in CLAIMED_CLASSES.values() for c in cs}
                     | set(NON_INPLACE) | {"Family", "FamilySurrogate", "DBViewType"})
    for cls_name in claimed:
        ids = parent.residue.get(cls_name, [])
        proj, fam = split_family_scoped(doc, ids)
        rows[cls_name] = {"residue": len(ids), "project": len(proj), "family_scoped": len(fam),
                          "project_ids": proj[:80], "family_scoped_ids": fam[:80],
                          "rung": next((r for r, cs in CLAIMED_CLASSES.items() if cls_name in cs), None),
                          "non_inplace_reason": NON_INPLACE.get(cls_name)}
    curtain = curtain_constellation(parent.state)
    rep = {"parent": os.path.relpath(parent_path, ROOT), "elements": len(doc.et_by_id),
           "ladder_landed": len(parent.landed), "classes": rows,
           "curtain_constellation": {"count": curtain["count"], "by_class": curtain["by_class"],
                                     "families": [f["name"] for f in curtain["families"]]},
           "group_b_classes": GROUP_B_CLASSES}
    if save:
        os.makedirs(RESIDUE_DIR, exist_ok=True)
        with open(os.path.join(RESIDUE_DIR, "residue_census.json"), "w") as fh:
            json.dump(rep, fh, indent=1)
    return rep


def demo() -> int:
    """Build one of every constructor STANDALONE (schema blanks + our
    values) and prove each round-trips byte-exact."""
    from .types import IdSource as IdS
    ids = IdS(5_000_000)
    objs: List[Obj] = []
    # subcategory pair via the pure constructors, then our in-place shaping
    ce = new_category(gen("Door - Swing (Plan)"), OST_Doors, INVALID, category_type=1, flags=0,
                      gstyle_ids=[5_000_101], elem_id=5_000_100)
    gs = new_gstyle(5_000_100, style_type="projection", pen=1, color=0, elem_id=5_000_101)
    objs.append(Obj("CategoryElem", ce.class_id, ce.obj))
    objs.append(Obj("GStyleElem", gs.class_id, gs.obj))
    objs.append(font_elem(5_000_200, size_mm=2.5, elem_id=5_000_201))
    objs.append(arrowhead_type(gen("Arrow Filled 20 Degree"), category_id=5_000_300, elem_id=5_000_301))
    objs.append(grid_head_type(gen("Grid Head - 8mm Circle"), font_id=5_000_201, line_category_id=5_000_100,
                               leader_category_id=INVALID, center_segment_category_id=INVALID,
                               elem_id=5_000_302))
    objs.append(interior_elevation_type(gen("Elevation Marker - 10mm Circle"), font_id=5_000_201,
                                        line_category_id=5_000_100, elem_id=5_000_303))
    objs.append(callout_head_type(gen("Callout Head - 2mm Radius"), elem_id=5_000_304))
    objs.append(new_grid("A", (0.0, 0.0), (mm(42000.0), 0.0), attr_id=5_000_302, elevation_ft=0.0,
                         elem_id=5_000_305))
    objs.append(generic_appearance_asset(gen("Appearance - Cast Concrete"), (200, 198, 192),
                                         glossiness=0.2, elem_id=5_000_306))
    ok = 0
    for o in objs:
        rep = check_object(o.class_name, o.value)
        ok += 1 if rep["ok"] else 0
        log(f"  {o.class_name:24s} bytes {rep['bytes']:6d} clean {rep['clean']} exact {rep['byte_exact']}"
            + ("" if rep["ok"] else f"  *** {rep['errors']}"))
    log(f"[demo] {ok}/{len(objs)} constructors round-trip byte-exact")
    return 0 if ok == len(objs) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--parent", default=DEFAULT_PARENT, help="the CERTIFIED parent (default Y9)")
    ap.add_argument("--out-dir", default=RESIDUE_DIR, help="output directory")
    ap.add_argument("--only", default="", help="comma list of rungs (Z_subcat,ZA_deep,...)")
    ap.add_argument("--census-only", action="store_true", help="write the residue census + curtain set only")
    ap.add_argument("--demo", action="store_true", help="constructor round-trip demo (no files)")
    ap.add_argument("--derive-asset-profile", action="store_true",
                    help="re-derive + freeze the GenericSchema appearance-asset profile")
    args = ap.parse_args(argv)
    if args.demo:
        return demo()
    if args.derive_asset_profile:
        derive_generic_asset_profile()
        return 0
    if args.census_only:
        rep = census_report(args.parent)
        log(json.dumps({k: {kk: vv for kk, vv in v.items() if not kk.endswith("_ids")}
                        for k, v in rep["classes"].items()}, indent=1))
        log(f"curtain constellation: {rep['curtain_constellation']}")
        return 0
    only = [s for s in args.only.split(",") if s.strip()]
    run_ladder(args.parent, args.out_dir, only=only)
    return 0


if __name__ == "__main__":
    sys.exit(main())

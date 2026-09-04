"""rvt.famgen.skeleton -- the FAMILY-DOCUMENT SKELETON, built from scratch.

A Revit FAMILY document (a standalone ``.rfa``, or an embedded save unit
inside a project) is a complete small Revit document.  Comparing eight real
family documents (a 2026 furniture ``.rfa``, an electrical panelboard, a
dry-type transformer, a lighting fixture with an ``ImposterLight``, a
receptacle, a generic-model plate, a furniture side table, a generic-model
fireplace hood) separates the FAMILY SKELETON -- present in EVERY family
document, whatever its category -- from FAMILY-SPECIFIC CONTENT (the
authored solid forms, profile sketches, nested annotation families and the
family editor's dimension/label ballast).

The skeleton (see docs/writer/family-skeleton.md, tags VERIFIED / INFERRED /
UNKNOWN per claim):

* the SELF-``Family`` element -- the document's own family: category,
  part type, the ``FamilyTypeTable`` (all TYPES of a standalone family live
  INSIDE the document), the family-parameter set (``m_familyParams`` = the
  current type's values), the parameter-ordering cell, the family-editor id
  index (``m_familyIds``) and ~90 behaviour flags/enums;
* the REFERENCE LEVEL: a ``Level`` named "Ref. Level" at elevation 0 plus
  its ``LevelAttributes`` type ("Level 1");
* the ORIGIN REFERENCE PLANES: ``RefPlane`` "Center (Front/Back)"
  (m_refName 4) and "Center (Left/Right)" (m_refName 1), plus any authored
  reference planes (``add_reference_plane``);
* the family PARAMETER machinery: ``ParamElemFamily`` elements (user
  parameters: Length/Width/Depth/...), their ``ParamDefValue`` captions,
  spec type ids and the ``revit.local.family:<guid><elemid>`` identity;
  and SHARED family parameters (``ParamElemExternal``, GUID copied verbatim
  from OUR shared-parameter file, ``revit.local.shared:<guid>`` identity);
* the family's own units registry and the plan-view constellation the
  reference planes are drawn in (reused verbatim from ``rvt.genesis.skeleton``
  -- the same DBViewPlan / Viewer / DBDrawing / Viewport / ExtentElem /
  SketchPlane objects a project view is);
* for MEP: the ``ConnectorElem`` + ``ConnectorElemDomainElectrical``
  (voltage, apparent load per phase, power factor, poles, load
  classification), built from the calc-engine values;
* the two DELIVERY FORMS: a standalone ``.rfa`` (:meth:`FamilyDoc.to_rfa`)
  and the embedded save-unit form (:meth:`FamilyDoc.to_embedded_unit`, the
  spec + bytes the project-side loader inserts).

Every constructor builds its object FIELD BY FIELD from plain parameters --
no ``.rfa`` is opened as a template, no Autodesk payload is cloned.  The
field layouts were derived by schema-directed decoding of the specimens above
and are proven by re-encoding those specimens from their own parameter
values (``tests/test_famgen_skeleton.py``: byte-exact for the skeleton
classes).  Product FACTS (manufacturer dimensions / ratings) enter only as
constructor parameter values -- Feist facts, our expression.

Run ``python -m rvt.famgen.skeleton`` to build S0 (an empty single-type
family document: skeleton only, no geometry), encode it, print the record
round-trip proof and (when the donor container is available) emit
``experiments/families/genesis/S0_empty_family.rfa``.
"""
from __future__ import annotations

import copy
import json
import os
import struct
import time
import uuid
import zlib
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple, Union

# --- reuse the project skeleton's building blocks (same shape contract) -----
from ..genesis import skeleton as _gsk
from ..genesis.skeleton import (            # noqa: F401  (re-exported building blocks)
    SkelElement, IdSource, _alloc, class_id, DUMMY_STAMP,
    element_base, symbol_base, element_header, element_parents,
    param_set_int, param_set_elemid, param_set_astring, param_set_double,
    plane, EMPTY_ENVELOPE, _ptr, _weak, our_guid,
    new_units_elem, DEFAULT_UNIT_FORMATS, format_options,
    minimal_globals, encode_minimal_globals,
    REVIT_2026_FORMAT_VERSION, REVIT_2026_BUILD,
)

_ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                      "..", "..", ".."))

# ---------------------------------------------------------------------------
# Constants (Revit 2026 corpus)
# ---------------------------------------------------------------------------

#: built-in categories (OST_*) a family can belong to / reference [VERIFIED
#: from the specimens' m_categoryId + the shared BIC list]
OST_FURNITURE = -2000080
OST_GENERIC_MODEL = -2000151
OST_LIGHTING_FIXTURES = -2001120
OST_ELECTRICAL_EQUIPMENT = -2001040       # panelboards, transformers, switchboards
OST_ELECTRICAL_FIXTURES = -2001060        # receptacles, switches
OST_LEVELS = -2000240
OST_REFERENCE_PLANES = -2000530           # CLINES / reference planes
OST_CONNECTORS = -2007000                 # ConnectorElem header category
OST_LEVEL_HEADS = -2006020
OST_VIEWS = -2000279

#: family-document elements carry m_designOptionId = -4 in their OBJECT
#: (the header keeps -1) [VERIFIED on every element of every family document
#: examined; a project's elements carry -1].  [INFERRED meaning: the family
#: editor's "main model" option sentinel.]
FAMILY_DESIGN_OPTION = -4

#: RefPlane.m_refName -- the "Is Reference" enumeration [VERIFIED values;
#: the names follow Revit's UI list, INFERRED for the codes not backed by a
#: named specimen plane].
REF_NAME = {
    "left": 0, "center_lr": 1, "right": 2,
    "front": 3, "center_fb": 4, "back": 5,
    "bottom": 6, "center_elevation": 7, "top": 8,
    "not_a_reference": 12, "strong": 13, "weak": 14,
}

#: Family.m_partType codes observed on the specimens [VERIFIED values,
#: INFERRED names = Revit's PartType enum]: 0 normal (furniture / generic /
#: lighting), 5 = duct/pipe fittings ..., 14 = electrical panelboard,
#: 15 = transformer / other electrical equipment [H], 16 = switchboard [H].
PART_TYPE = {
    "normal": 0, "panelboard": 14, "electrical_equipment": 15, "switchboard": 16,
}

#: BuiltInParameters used by the family skeleton [VERIFIED ids on specimens]
BIP_ELEM_TYPE_PARAM = -1012201            # Level/RefPlane element-type param (-> -1)
BIP_LEVEL_ATTR_SYMBOL_END1 = -1008002     # level type: symbol at end 1 (0)
BIP_LEVEL_ATTR_SYMBOL_END2 = -1008001     # level type: symbol at end 2 (1)
#: identity-data TYPE parameters a family type may carry (product data) --
#: the FamilyTypeTable stores them as AString-valued entries [ids VERIFIED in
#: the .rfa's identityData parameter group; names INFERRED from the Revit
#: BIP list].
BIP_TYPE_DESCRIPTION = -1010109           # ALL_MODEL_DESCRIPTION
BIP_TYPE_URL = -1010108                   # ALL_MODEL_URL
BIP_TYPE_TYPE_COMMENTS = -1010105         # ALL_MODEL_TYPE_COMMENTS
BIP_TYPE_MANUFACTURER = -1010104          # ALL_MODEL_MANUFACTURER
BIP_TYPE_MODEL = -1010103                 # ALL_MODEL_MODEL
BIP_TYPE_COST = -1001205                  # ALL_MODEL_COST [H: id verified as a
                                          # locked type param in the specimens;
                                          # the COST name is inferred]

#: parameter GROUP type ids (Forge group vocabulary) [VERIFIED on the .rfa]
PGROUP_DIMENSIONS = "autodesk.parameter.group:dimensions-1.0.0"
PGROUP_CONSTRAINTS = "autodesk.parameter.group:constraints-1.0.0"
PGROUP_MATERIALS = "autodesk.parameter.group:materials-1.0.0"
PGROUP_IDENTITY = "autodesk.parameter.group:identityData-1.0.0"
PGROUP_ELECTRICAL = "autodesk.parameter.group:electrical-1.0.0"
PGROUP_ELECTRICAL_LOADS = "autodesk.parameter.group:electricalLoads-1.0.0"
PGROUP_PHOTOMETRICS = "autodesk.parameter.group:photometrics-1.0.0"

#: parameter SPEC type ids (Forge measurable specs) [VERIFIED for length;
#: the electrical ones are the openly published spec ids the units registry
#: keys on (see rvt.genesis.skeleton.DEFAULT_UNIT_FORMATS)]
SPEC_LENGTH = "autodesk.spec.aec:length-1.0.0"
SPEC_NUMBER = "autodesk.spec.aec:number-1.0.0"
SPEC_TEXT = "autodesk.spec:spec.string-1.0.0"
SPEC_INTEGER = "autodesk.spec:spec.int64-1.0.0"
#: SELECTOR ONLY for a Yes/No family parameter -- like SPEC_TEXT / SPEC_INTEGER
#: it is never written into the file: ``ParamDefYesNo`` carries no
#: ``m_specTypeId`` (schema: no own fields, same shape as ParamDefString).
#: The storage-class law of #333 (Revit-2026-born specimen, desktop round 24)
#: says a non-measurable parameter takes its own ParamDef class and no spec.
SPEC_YESNO = "autodesk.spec:spec.bool-1.0.0"
#: text/integer are NON-measurable specs: their family-parameter definition
#: is a ParamDefString / ParamDefInt (no m_specTypeId), NOT a measurable
#: ParamDefValue -- issue #333 round 24, byte-measured on a Revit-2026-born
#: specimen (a blank Generic Model + one Text + one Integer param).  Authoring
#: them as ParamDefValue with a spec id crashed the Family Types dialog
#: (0xe06d7363 at doModal: the dialog read a measurable def and formatted a
#: string/int value through the units path).
PGROUP_TEXT = "autodesk.parameter.group:text-1.0.0"
_INT32_LOW, _INT32_HIGH = -2147483648, 2147483647
SPEC_VOLTAGE = "autodesk.spec.aec.electrical:potential-1.0.0"
SPEC_APPARENT_POWER = "autodesk.spec.aec.electrical:apparentPower-1.0.0"
SPEC_WATTAGE = "autodesk.spec.aec.electrical:wattage-1.0.0"
SPEC_LUMINOUS_FLUX = "autodesk.spec.aec.electrical:luminousFlux-1.0.0"
SPEC_COLOR_TEMPERATURE = "autodesk.spec.aec.electrical:colorTemperature-1.0.0"

#: unit conversions -- Revit stores internal units; electrical V / VA / W
#: are display / 0.3048**2 (verified: 208 V -> 2238.89, 120 V -> 1291.67,
#: 64 W -> 688.89, 180 VA -> 1937.50)
FT_PER_MM = 1.0 / 304.8
_ELEC_FACTOR = 1.0 / (0.3048 ** 2)


def mm(v: float) -> float:
    """millimetres -> feet (Revit internal length)."""
    return float(v) * FT_PER_MM


def volts(v: float) -> float:
    """volts -> Revit internal electrical-potential units."""
    return float(v) * _ELEC_FACTOR


def voltamps(va: float) -> float:
    """volt-amperes -> Revit internal apparent-power units."""
    return float(va) * _ELEC_FACTOR


def watts(w: float) -> float:
    """watts -> Revit internal power units (same electrical factor)."""
    return float(w) * _ELEC_FACTOR


# ---------------------------------------------------------------------------
# common datum building blocks (Level and RefPlane share the datum layout)
# ---------------------------------------------------------------------------

def _datum_geom_steps(gstep_flags: int = 0) -> dict:
    """The ``GeomStepList`` of a datum (Level / RefPlane): one
    ``DatumPlaneGeomStep`` whose face history keys the datum plane face.
    Levels carry ``m_flags`` 1, reference planes 0 [VERIFIED on both]."""
    return _ptr("GeomStepList", {
        "m_nonBRepGList": [_ptr("DatumPlaneGeomStep", {
            "m_faceHistTable": [{"m_id": 0, "m_faceHist": {"m_keys": [6, 0, -1]}}],
            "m_curveHistTableSet": [], "m_edgeHistTable": [],
            "m_edgeHistTableReverse": [],
            "m_id": 1, "m_version": 0, "m_flags": int(gstep_flags),
            "m_pElem": _weak(2), "m_oExtraDatas": None})],
        "m_bRepFormGList": [], "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [], "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [1, 1, 1, 1, 1],
        "m_idCounter": 2, "m_flags": 1})


def _datum_geom_table() -> dict:
    return _ptr("GeomTable", {
        "m_refPntMirrored": False, "m_table": [{"m_geomGeneratorId": 1}],
        "m_bigTableOwner": None, "m_materialMarkers": [], "m_faceTypeMarkers": []})


def _datum_faces(obj: dict, origin: Sequence[float], xvec: Sequence[float],
                 yvec: Sequence[float], envelope) -> None:
    """The datum's inline face + surface (pointer archive indices: 1 =
    ADocument, 2 = self, 3 = Face, 4 = m_pSurface, 5 = the Face's deferred
    m_pSurf) [VERIFIED on Level 311 and the family specimens]."""
    obj["m_pFace"] = _ptr("Face", {
        "m_GInfo": {"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                    "m_flags": 524804},
        "m_pFirstLoop": None, "m_faceRegions": [], "m_pGFilling": None,
        "m_oBackgroundFilling": None, "m_renderStyleId": -1, "m_cutType": 0,
        "m_faceFlags_v9": 0,
        "m_pSurf": plane(origin, xvec, yvec, envelope, pid=5)}, pid=3)
    obj["m_pSurface"] = plane(origin, xvec, yvec, envelope, pid=4)


# ---------------------------------------------------------------------------
# THE REFERENCE LEVEL
# ---------------------------------------------------------------------------

def new_family_level(elem_id: int, self_family_id: int, level_type_id: int, *,
                     gen_view_id: int = -1, name: str = "Ref. Level",
                     elevation_ft: float = 0.0,
                     extent_ft: Tuple[Tuple[float, float], Tuple[float, float]] = (
                         (-5.0, -8.0), (5.0, 6.0)),
                     datum_length_ft: float = 30.0,
                     origin: Sequence[float] = (0.0, 0.0),
                     xvec: Sequence[float] = (1.0, 0.0, 0.0),
                     yvec: Sequence[float] = (0.0, 1.0, 0.0),
                     sheet_text_height_ft: float = 0.015625,
                     v2_datum: bool = False,
                     flags: int = 2058) -> SkelElement:
    """The family's REFERENCE LEVEL (class ``Level``, category Levels).

    [VERIFIED byte-exact vs the .rfa and rme specimens]  Every family document
    holds exactly one Level named "Ref. Level" at elevation 0; its datum plane
    origin Z = the elevation, the datum line runs +X for ``datum_length_ft``
    (30 ft imperial / 30 m metric templates), ``m_isBuildingStory`` is True,
    the family design-option sentinel is -4 and the object carries an EMPTY
    ``ParamValueSetInt`` (project levels carry LEVEL_IS_STRUCTURAL there).
    ``gen_view_id`` = the plan view the level regenerates (header regenOnly
    / appearance parent); ``level_type_id`` = the doc's ``LevelAttributes``.
    seq-103 rep = ``SerializedDummy``.
    """
    z = float(elevation_ft)
    ox, oy = float(origin[0]), float(origin[1])
    o = element_base(elem_id, cell_list=True, design_option=FAMILY_DESIGN_OPTION)
    o["m_famId"] = int(self_family_id)
    o["m_pParamValueSetInt"] = param_set_int([])
    o["m_pParamValueSetElementId"] = param_set_elemid([(BIP_ELEM_TYPE_PARAM, -1)])
    o["m_geomSteps"] = _datum_geom_steps(0)      # family datums carry flags 0
    o["m_pGeomTable"] = _datum_geom_table()
    o["m_text"] = str(name)
    _datum_faces(o, (ox, oy, z), tuple(xvec), tuple(yvec), extent_ft)
    o["m_pLeader"] = None
    o["m_freeEnd"] = [ox, oy, z]
    o["m_bubbleEnd"] = [ox + float(datum_length_ft), oy, z]
    o["m_cutVec"] = [0.0, 1.0, 0.0]
    o["m_refPointsForNewViews"] = [[ox, oy, z], [ox + float(datum_length_ft), oy, z]]
    o["m_sheetTextHeight"] = float(sheet_text_height_ft)
    o["m_genDbViewId"] = -1
    o["m_v2Datum"] = bool(v2_datum)               # True only on ancient (v2) content
    o["m_useConstVForDatumLine3dRep"] = True
    o["m_roomComputationElevationOffset"] = 0.0
    o["m_attrId"] = int(level_type_id)
    o["m_isBuildingStory"] = True
    regen = [gen_view_id] if gen_view_id is not None and gen_view_id >= 0 else []
    hdr = element_header("Level", category=OST_LEVELS,
                         deletion=[self_family_id, level_type_id, elem_id],
                         regen_only=regen, appearance=[level_type_id] + regen,
                         flags=flags, visible_view_flags=-4225,
                         family_id=self_family_id)
    return SkelElement(elem_id, "Level", hdr, o, None, kind="ref_level",
                       refs={"family": self_family_id, "level_type": level_type_id,
                             "gen_view": gen_view_id},
                       notes=["family Reference Level; seq103=SerializedDummy"])


#: the built-in parameter id every level type lists as a regenOnly parent
#: [VERIFIED on all specimen LevelAttributes headers; -1007109 =
#: LEVEL_ATTR_ROOM_COMPUTATION_AUTOMATIC INFERRED]
BIP_LEVEL_ATTR_REGEN = -1007109


def new_family_level_type(elem_id: int, self_family_id: int, *,
                          name: str = "Level 1",
                          line_category_id: int = -1, line_gstyle_id: int = -1,
                          leader_category_id: int = -1,
                          font_id: int = -1, head_family_symbol_id: int = -1,
                          room_computation_height_ft: float = 0.0,
                          flags: int = 14) -> SkelElement:
    """The doc's level TYPE (``LevelAttributes``, named "Level 1" in every
    family document -- the type of the "Ref. Level" datum).

    [VERIFIED byte-exact vs the .rfa / rme specimens]  References (all
    optional, -1 in a genesis document): the level-line ``CategoryElem`` +
    leader ``CategoryElem`` (the family's object-style copies), a
    ``FontElem`` and the level-head ``FamilySymbol`` (a NESTED annotation
    family in Autodesk's templates -- deliberately unset here).  Family docs
    set ``m_bRoomComputationHeightAutomatic`` True with height 0 (projects:
    False + 4 ft) [VERIFIED difference].
    """
    o = symbol_base(elem_id, name, cell_list=False, design_option=FAMILY_DESIGN_OPTION)
    o["m_famId"] = int(self_family_id)
    o["m_pParamValueSetInt"] = param_set_int([(BIP_LEVEL_ATTR_SYMBOL_END1, 0),
                                              (BIP_LEVEL_ATTR_SYMBOL_END2, 1)])
    o["m_lineAndTextAttr"] = {"m_fontId": int(font_id),
                              "m_categoryId": int(line_category_id),
                              "m_background": 0, "m_bBold": False,
                              "m_bItalic": False, "m_bUnderline": False}
    o["m_roomComputationUserHeight"] = float(room_computation_height_ft)
    o["m_leaderCategoryId"] = int(leader_category_id)
    o["m_familyTagId"] = int(head_family_symbol_id)
    o["m_baseElevation"] = 0
    o["m_bRoomComputationHeightAutomatic"] = True
    dele = [self_family_id, elem_id] + [x for x in (line_category_id, line_gstyle_id,
                                                    leader_category_id, font_id,
                                                    head_family_symbol_id) if x >= 0]
    hdr = element_header("LevelAttributes", category=OST_LEVELS, deletion=dele,
                         regen_only=[BIP_LEVEL_ATTR_REGEN],
                         flags=flags, visible_view_flags=-32768,
                         family_id=self_family_id)
    return SkelElement(elem_id, "LevelAttributes", hdr, o, None, kind="level_type",
                       refs={"family": self_family_id, "line_category": line_category_id,
                             "leader_category": leader_category_id, "font": font_id,
                             "head_symbol": head_family_symbol_id})


# ---------------------------------------------------------------------------
# REFERENCE PLANES
# ---------------------------------------------------------------------------

def new_reference_plane(elem_id: int, self_family_id: int, *,
                        name: str = "", ref_name="not_a_reference",
                        bubble_end: Sequence[float] = (5.0, 0.0, 0.0),
                        free_end: Sequence[float] = (-5.0, 0.0, 0.0),
                        normal: Sequence[float] = (0.0, 1.0, 0.0),
                        gen_view_id: int = -1,
                        extent: Tuple[Tuple[float, float], Tuple[float, float]] = (
                            (-5.0, -2.0), (5.0, 7.0)),
                        origin_z: float = 0.0,
                        defines_origin: bool = False, locked: bool = False,
                        subcategory_id: int = -1,
                        sheet_text_height_ft: float = 0.0078125,
                        ref_points: Optional[Sequence[Sequence[float]]] = None,
                        sketch_member: bool = True,
                        gstep_flags: int = 0, flags: int = 2058) -> SkelElement:
    """A ``RefPlane`` datum in the family document.

    [VERIFIED byte-exact vs the rme panelboard's "Center (Front/Back)" and
    "Center (Left/Right)" planes]  The plane runs from ``free_end`` to
    ``bubble_end`` (the drawn datum line, feet) and its face plane spans
    those two points and the ``normal`` (the plane's Y axis; ``m_cutVec`` is
    the view direction the plane was sketched in).  ``ref_name`` = the "Is
    Reference" role (:data:`REF_NAME` key or int: 4 = Center (Front/Back),
    1 = Center (Left/Right), 12 = Not a Reference, ...).  ``defines_origin``
    = the plane pins the family origin; ``gen_view_id`` = the plan view it
    was drawn in (its deletion parent) -- every specimen plane has one.
    ``extent`` = the plane-face envelope (drawing extent, plane UV).
    seq-103 rep = ``SerializedDummy``.
    """
    rn = REF_NAME[ref_name] if isinstance(ref_name, str) else int(ref_name)
    bx, by, bz = (float(c) for c in bubble_end)
    fx, fy, fz = (float(c) for c in free_end)
    # plane axes: X = unit vector free->bubble, Y = normal ("cut" the plane
    # was drawn towards is orthogonal to both)
    dx, dy, dz = bx - fx, by - fy, bz - fz
    ln = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1.0
    xvec = (dx / ln, dy / ln, dz / ln)
    yvec = tuple(float(c) for c in normal)
    # cut vector = the PLANE NORMAL, normalised (the sketching view
    # direction).  Measured on a Revit-2026-born family (issue #52): every
    # donor RefPlane carries m_cutVec == the plane normal [0,0,1]; the old
    # x-cross-normal form put an in-plane vector here.
    cl = (yvec[0] ** 2 + yvec[1] ** 2 + yvec[2] ** 2) ** 0.5 or 1.0
    cut = [yvec[0] / cl, yvec[1] / cl, yvec[2] / cl]
    origin = ((fx + bx) / 2.0, (fy + by) / 2.0, (fz + bz) / 2.0)
    o = element_base(elem_id, cell_list=False, design_option=FAMILY_DESIGN_OPTION)
    o["m_famId"] = int(self_family_id)
    o["m_locked"] = bool(locked)
    o["m_pParamValueSetElementId"] = param_set_elemid([(BIP_ELEM_TYPE_PARAM, -1)])
    o["m_geomSteps"] = _datum_geom_steps(int(gstep_flags))
    o["m_pGeomTable"] = _datum_geom_table()
    cells = ([_ptr("SketchMembership", {"m_groupId": -1})] if sketch_member else [])
    cells.append(_ptr("PatternHelper", {"m_PatternPositionMap": [],
                                          "m_substituteFaceMap": []}))
    o["m_cellList"] = _ptr("CellList", {"m_cells": cells})
    o["m_text"] = str(name)
    _datum_faces(o, origin, xvec, yvec, extent)
    o["m_pLeader"] = None
    o["m_freeEnd"] = [fx, fy, fz]
    o["m_bubbleEnd"] = [bx, by, bz]
    o["m_cutVec"] = cut
    o["m_refPointsForNewViews"] = ([[float(c) for c in p] for p in ref_points]
                                  if ref_points is not None else
                                  [[fx, fy, fz], [bx, by, bz]])
    o["m_sheetTextHeight"] = float(sheet_text_height_ft)
    o["m_genDbViewId"] = int(gen_view_id)
    o["m_v2Datum"] = False
    o["m_useConstVForDatumLine3dRep"] = True
    o["m_refName"] = int(rn)
    o["m_definesOrigin"] = bool(defines_origin)
    o["m_deletionByUserAllowed"] = True
    o["m_definesWallClosure"] = False
    o["m_parentReference"] = None
    o["m_subcategoryId"] = int(subcategory_id)
    del origin_z  # elevation of a vertical plane is implied by its axes
    dele = [self_family_id, elem_id] + ([gen_view_id] if gen_view_id >= 0 else [])
    if subcategory_id >= 0:
        dele.append(subcategory_id)
    hdr = element_header("RefPlane", category=OST_REFERENCE_PLANES, deletion=dele,
                         flags=flags, visible_view_flags=-4225,
                         family_id=self_family_id)
    return SkelElement(elem_id, "RefPlane", hdr, o, None, kind="ref_plane",
                       refs={"family": self_family_id, "gen_view": gen_view_id,
                             "ref_name": rn, "subcategory": subcategory_id})


def new_required_settings(ids, self_family_id: int) -> List[SkelElement]:
    """The four singleton settings elements desktop Revit REQUIRES of a
    family document (issue #52, desktop rounds 4-5, verified on the owner's
    Revit 2026):

    * ``DefaultDivideSettings`` + ``DrawOrder3dElem`` -- the two "required
      internal settings" Revit's repair dialog names when absent;
    * ``AutoCamSettingsElem`` -- the standing ``Cannot get
      AutoCamSettingsElem from the ADoccument!`` DBG_WARN;
    * ``PenWidthTableElem`` -- OUR ISO-128 pen series (the genesis
      constructor); its absence is the ``PenWidthTableGetter.cpp:62``
      assertion that killed view drawing.

    Shapes = blank schema skeletons + the factory defaults measured on a
    Revit-2026-born family; ``famdoc_adoc`` wires their ids into
    ``UniqueElementsTracking`` [10]/[60]/[85] and
    ``PenWidthTableInfo.m_penWidthTableElemId``.  With candidate E these
    removed the repair prompt and the draw assertion on desktop.
    """
    from ..genesis import residue_b as _RB
    from ..genesis.types import blank_object as _blank

    def _settings(cls: str, eid: int, kind: str, **fields) -> SkelElement:
        o = _blank(cls)
        o.update({"m_id": int(eid), "m_famId": int(self_family_id),
                  "m_docAccess": {"m_pDoc": _weak(1)},
                  "m_assocLevelId": -1, "m_unplacedOwnerId": -1,
                  "m_ownerDBViewId": -1, "m_createdPhaseId": -1,
                  "m_demolishedPhaseId": -1, "m_designOptionId": -1})
        o.update(fields)
        hdr = element_header(cls, category=-1, deletion=[])
        return SkelElement(int(eid), cls, hdr, o, None, kind=kind)

    out = [
        _settings("AutoCamSettingsElem", _alloc(ids), "autocam-settings"),
        _settings("DefaultDivideSettings", _alloc(ids), "divide-settings",
                  m_pathDistance=5.0, m_layout=[2, 2], m_number=[12, 12],
                  m_pathLayout=2),
        _settings("DrawOrder3dElem", _alloc(ids), "draworder3d-settings"),
    ]
    rec = _RB.family_pen_width_table(int(self_family_id), elem_id=_alloc(ids))
    out.append(SkelElement(rec.elem_id, rec.class_name, rec.header, rec.obj,
                           rec.rep, kind="pen-width-table"))
    return out


#: the FAMILY-UNITS LAW (issue #333, desktop round 16): the Family Types
#: dialog formats EVERY parameter value through UnitsElem.m_units --
#: a Revit-born family carries a 136-spec m_formatOptionsMap (measured on
#: the owner's donor; pure unit configuration, spec/unit type ids +
#: accuracies only) where our project-derived table carried 8 entries with
#: MISMATCHED spec versions (-2.0.0 vs the -1.0.0 our param defs declare).
#: The first electrical lookup missed and the dialog threw at doModal.
_FAMILY_UNITS_ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "assets", "family_units.json")


def _apply_family_units_law(units: "SkelElement") -> None:
    with open(_FAMILY_UNITS_ASSET, "r", encoding="utf-8") as fh:
        units.obj["m_units"] = json.load(fh)


def new_classification_tables(ids, self_family_id: int) -> List[SkelElement]:
    """The CLASSIFICATION-TABLE singletons (issue #333, desktop round 27):
    editing a family parameter runs the required-unique-elements check, and
    it names these when absent ("Internal setting 'Keynote Table' is
    required by Revit and has been deleted") -- ``AssemblyCodeTable`` (UET
    slot 64) and ``KeynoteTable`` (UET slot 65), measured on the donor
    (unit-0 ids 2971/2972).  OUR tables are MINIMAL AND EMPTY: the donor's
    carry Autodesk's sample keynote text and an external-file reference to
    an Autodesk install path -- content we never copy (hard rules 2/3);
    the checker requires the registered ELEMENT, not the sample data.
    """
    from ..genesis.types import blank_object as _blank
    fam = int(self_family_id)
    out: List[SkelElement] = []
    for cls, tree_cls, extra in (
            ("AssemblyCodeTable", "ClassificationEntries",
             {"m_hasUserCustomizedAssemblyCode": False}),
            ("KeynoteTable", "KeynoteEntryTable",
             {"m_name": "Standard", "m_isBuiltIn": True,
              "m_hasUserCustomizedKeynote": False})):
        eid = _alloc(ids)
        o = _blank(cls)
        o.update({"m_id": eid, "m_famId": fam,
                  "m_docAccess": {"m_pDoc": _weak(1)},
                  "m_assocLevelId": -1, "m_unplacedOwnerId": -1,
                  "m_ownerDBViewId": -1, "m_createdPhaseId": -1,
                  "m_demolishedPhaseId": -1, "m_designOptionId": -1,
                  "m_cellList": {"ptr_class": "CellList", "pid": -1, "value": {
                      "m_cells": [
                          {"ptr_class": "ExternalFileReferenceCell", "pid": -1,
                           "value": {}},
                          {"ptr_class": "ExternalResourceReferenceCell", "pid": -1,
                           "value": {"m_externalResourceReferences": [],
                                     "m_externalResourceReferencesExpanded": []}}]}},
                  "m_oKeyBasedTreeEntries": {"ptr_class": tree_cls, "pid": -1,
                                             "value": dict(_blank(tree_cls),
                                                           m_keyBasedTreeEntrySet=[])},
                  "m_lastReadSucceeded": True})
        o.update(extra)
        hdr = element_header(cls, category=-1, deletion=[fam, eid],
                             flags=67117070, visible_view_flags=-32768)
        out.append(SkelElement(eid, cls, hdr, o, None, kind="classification-table"))
    return out


def new_browser_organizations(ids, self_family_id: int) -> Tuple[int, int, List[SkelElement]]:
    """The BROWSER-ORGANIZATION pair (issue #381: without them the Project
    Browser lists the family's views FLAT -- no 'Floor Plans' / 'Ceiling
    Plans' / '3D Views' folder headers).  Donor law (elements 907/908 +
    AppInfo slot 75): the views organization ("all", folder by built-in
    parameter -1012106 = the view's family/type, sorted by -1005112) and
    the sheets organization ("all", sorted by -1007401), both default.
    Returns ``(views_org_id, sheets_org_id, elements)``; famdoc_adoc wires
    them into ``BrowserOrganizationTracking`` (slot 75).
    """
    from ..genesis.types import blank_object as _blank
    fam = int(self_family_id)

    def _org(eid: int, **fields) -> SkelElement:
        o = _blank("BrowserOrganization")
        o.update({"m_id": eid, "m_famId": fam,
                  "m_docAccess": {"m_pDoc": _weak(1)},
                  "m_assocLevelId": -1, "m_unplacedOwnerId": -1,
                  "m_ownerDBViewId": -1, "m_createdPhaseId": -1,
                  "m_demolishedPhaseId": -1, "m_designOptionId": -4,
                  "m_symbolInfo": {"ptr_class": "SymbolInfo", "pid": -1,
                                   "value": {"m_name": "all"}},
                  "m_bDefault": True, "m_bSortOrderAsc": True})
        o.update(fields)
        hdr = element_header("BrowserOrganization", category=-1,
                             deletion=[fam, eid], flags=26,
                             visible_view_flags=-32768)
        return SkelElement(eid, "BrowserOrganization", hdr, o, None,
                           kind="browser-organization")

    sheets_id = _alloc(ids)
    views_id = _alloc(ids)
    els = [
        _org(sheets_id, m_type=1,
             m_sortParameter={"m_paramIdPath": [-1007401]}),
        _org(views_id,
             m_folderDefinitions=[{"m_parameter": {"m_paramIdPath": [-1012106]},
                                   "m_numCharsToUse": 0}],
             m_sortParameter={"m_paramIdPath": [-1005112]}),
    ]
    return views_id, sheets_id, els


def _dim_format_options(unit: str = "autodesk.unit.unit:meters-1.0.0", *,
                        symbol: str = "", accuracy: float = 1.0,
                        use_default: bool = True) -> dict:
    return {"m_symbolTypeId": {"m_typeId": symbol},
            "m_unitTypeId": {"m_typeId": unit},
            "m_accuracy": float(accuracy), "m_roundingMethod": 0,
            "m_bSuppressLeadingZeros": False, "m_bSuppressSpaces": False,
            "m_bSuppressTrailingZeros": False, "m_bUseDefault": bool(use_default),
            "m_bUseGrouping": False, "m_bUsePlusPrefix": False}


#: THE RETOUCH STYLES every Revit-born family view names in its
#: ``RetouchTable``: the INVISIBLE-LINES style (category -2000064) and the
#: NOT-SILHOUETTE style (-2000082).  Both are pen 2, colour 8355711, no line
#: pattern [identical in the owner's donor (146 / 1266) and the Autodesk
#: library panelboard (17968 / 83898) -- two independently authored files,
#: same pair, so this is the format's law and not one author's setting].
#: Ours shipped -1 for both, leaving the linework pass with no style to
#: resolve.
RETOUCH_STYLES = ((-2000064, "invisible"), (-2000082, "not_silhouette"))


def new_object_style(ids, self_family_id: int, category_id: int, *,
                     pen: int = 1, color: int = 0,
                     line_pattern: int = -3000010) -> SkelElement:
    """THE OBJECT STYLE of the family's own category -- the graphics style
    every solid's ``Geometry`` node names, and therefore the LINE STYLE
    Revit draws that solid's edges with.

    Our documents used to carry none (``geometry_style_id`` -1, "the S0
    reduction"), which is why a generated family rendered as a flat shaded
    body with no outline at all and vanished entirely in Wireframe [owner:
    "when graphics display is on i can not see the outlining of the
    geometry"]: shaded faces come from the material, but the edges have no
    style to be drawn in.

    Measured on the Autodesk library panelboard's 17866: a ``GStyleElem``
    whose ``m_categoryId`` is the family's BUILT-IN category (not a
    CategoryElem id, the way the dimension-style copies are), gstyleType 1,
    pen 1, colour 0, line pattern -3000010, header role 67110926.
    """
    eid = _alloc(ids)
    o = element_base(eid, cell_list=True)
    o["m_famId"] = int(self_family_id)
    o["m_pGStyle"] = _ptr("GStyle", {
        "m_linePatternId": int(line_pattern), "m_materialElemId": -1,
        "m_penNumber": int(pen), "m_color": int(color),
        "m_isScreenSized": False})
    o["m_categoryId"] = int(category_id)
    o["m_ownerId"] = -1
    o["m_gstyleType"] = 1
    hdr = element_header("GStyleElem", category=-1,
                         deletion=[int(self_family_id), eid],
                         flags=67110926, visible_view_flags=-32768)
    hdr["m_familyId"] = int(self_family_id)
    return SkelElement(eid, "GStyleElem", hdr, o, None, kind="object-style")


def new_dimension_style_constellation(ids, self_family_id: int) -> Tuple[int, List[SkelElement]]:
    """The DIMENSION-STYLE LAW (issue #333, desktop round 15): selecting any
    element in the family editor spawns temporary dimensions, and the lookup
    behind them dies without a registered default linear ``DimensionStyle``
    (journal: ``Where is the DimensionStyle?  LinearDimStringState.cpp:106``
    then the ``LinearDimString.cpp:331`` assert).

    Returns ``(dim_style_id, elements)``: the donor-measured 11-element
    constellation of the default style -- ``LeaderStyle`` ("Diagonal"
    arrowhead) + ``DimensionStyle`` ("Diagonal" linear), each ``CategoryElem``
    they reference (leader / text / tick / centerline; anonymous categories,
    parent -2000059, type 4) carrying ONE ``GStyleElem`` line style, plus the
    text ``FontElem`` (Arial 3/32").  Every scalar was measured on the owner's
    Revit-2026-born donor famdoc (unit-1 ids 2642-2652); nothing is copied --
    all schema-built.  ``famdoc_adoc`` registers the style as the document
    default in ``SymbolIdMgr.m_defElementTypeMap`` (key 10, the donor's
    linear-dimension slot).
    """
    from ..genesis.types import blank_object as _blank
    fam = int(self_family_id)

    def _base(cls: str, eid: int, **fields) -> dict:
        o = _blank(cls)
        o.update({"m_id": int(eid), "m_famId": fam,
                  "m_docAccess": {"m_pDoc": _weak(1)},
                  "m_assocLevelId": -1, "m_unplacedOwnerId": -1,
                  "m_ownerDBViewId": -1, "m_createdPhaseId": -1,
                  "m_demolishedPhaseId": -1, "m_designOptionId": -4})
        o.update(fields)
        return o

    def _el(cls, eid, o, deletion, *, flags, kind):
        hdr = element_header(cls, category=-1, deletion=deletion, flags=flags,
                             visible_view_flags=-32768)
        return SkelElement(int(eid), cls, hdr, o, None, kind=kind)

    def _category_elem(eid: int, owner_id: int, gstyle_id: int) -> SkelElement:
        o = _base("CategoryElem", eid, m_ownerId=int(owner_id),
                  m_pCategory={"ptr_class": "Category", "pid": -1, "value": {
                      "m_name": "", "m_parentCategoryId": -2000059,
                      "m_categoryType": 4, "m_flags": 7}},
                  m_gstyleIds=[int(gstyle_id)])
        return _el("CategoryElem", eid, o, [fam, int(owner_id), eid, int(gstyle_id)],
                   flags=8202, kind="dim-style-category")

    def _gstyle_elem(eid: int, category_id: int, *, pen: int, color: int,
                     line_pattern: int) -> SkelElement:
        o = _base("GStyleElem", eid, m_categoryId=int(category_id), m_gstyleType=1,
                  m_pGStyle={"ptr_class": "GStyle", "pid": -1, "value": {
                      "m_linePatternId": int(line_pattern), "m_materialElemId": -1,
                      "m_penNumber": int(pen), "m_color": int(color),
                      "m_isScreenSized": False}})
        return _el("GStyleElem", eid, o, [fam, int(category_id), eid],
                   flags=8202, kind="dim-style-gstyle")

    leader_id = _alloc(ids); leader_cat = _alloc(ids); leader_g = _alloc(ids)
    dim_id = _alloc(ids); text_cat = _alloc(ids); text_g = _alloc(ids)
    font_id = _alloc(ids); tick_cat = _alloc(ids); tick_g = _alloc(ids)
    center_cat = _alloc(ids); center_g = _alloc(ids)

    lo = _base("LeaderStyle", leader_id, m_categoryId=leader_cat,
               m_tickType=0, m_arrowFilled=0,
               m_symbolInfo={"ptr_class": "SymbolInfo", "pid": -1,
                             "value": {"m_name": "Diagonal"}},
               m_pParamValueSetDouble={"ptr_class": "ParamValueSetDouble", "pid": -1,
                                       "value": {"m_paramSet": [
                                           {"m_value": 0.5235987755982984, "m_paramId": -1006426},
                                           {"m_value": 0.010416666666666666, "m_paramId": -1006424}]}})
    leader = _el("LeaderStyle", leader_id, lo, [fam, leader_id, leader_cat],
                 flags=14, kind="dim-style-leader")

    do = _base("DimensionStyle", dim_id,
               m_designOptionId=-1,
               m_symbolInfo={"ptr_class": "SymbolInfo", "pid": -1,
                             "value": {"m_name": "Diagonal"}},
               m_pParamValueSetDouble={"ptr_class": "ParamValueSetDouble", "pid": -1,
                                       "value": {"m_paramSet": [
                                           {"m_value": 0.010416666666666666, "m_paramId": -1006465},
                                           {"m_value": 0.0078125, "m_paramId": -1006433},
                                           {"m_value": 0.0, "m_paramId": -1006431},
                                           {"m_value": 0.010416666666666666, "m_paramId": -1006407},
                                           {"m_value": 0.005208333333333333, "m_paramId": -1006405},
                                           {"m_value": 0.0078125, "m_paramId": -1006404},
                                           {"m_value": 0.005208333333333333, "m_paramId": -1006401},
                                           {"m_value": 1.0, "m_paramId": -1006327}]}},
               m_pParamValueSetElementId={"ptr_class": "ParamValueSetElementId", "pid": -1,
                                          "value": {"m_paramSet": [
                                              {"m_paramId": -1006430, "m_value": -1}]}},
               m_alternateUnitsPrefix="", m_alternateUnitsSuffix="",
               m_equalityFormattingArr=[{"m_labelType": 3, "m_leadingSpaces": 0,
                                         "m_bLeadingParam": True, "m_prefix": "",
                                         "m_suffix": "",
                                         "m_formatOptions": _dim_format_options()}],
               m_equalityText="EQ", m_radiusDiameterPrefixText="",
               m_prefix="", m_suffix="",
               m_oLinFormatOptions={"ptr_class": "FormatOptions", "pid": -1,
                                    "value": _dim_format_options()},
               m_oLinFormatOptionsAlternate={"ptr_class": "FormatOptions", "pid": -1,
                                             "value": _dim_format_options(
                                                 "autodesk.unit.unit:millimeters-1.0.1",
                                                 use_default=False)},
               m_oAngFormatOptions={"ptr_class": "FormatOptions", "pid": -1,
                                    "value": _dim_format_options()},
               m_oAngFormatOptionsAlternate={"ptr_class": "FormatOptions", "pid": -1,
                                             "value": _dim_format_options(
                                                 "autodesk.unit.unit:degrees-1.0.1",
                                                 symbol="autodesk.unit.symbol:degree-1.0.1",
                                                 accuracy=0.01, use_default=False)},
               m_pLineAndTextAttr={"ptr_class": "LineAndTextAttr", "pid": -1,
                                   "value": {"m_fontId": font_id,
                                             "m_categoryId": text_cat,
                                             "m_background": 0, "m_bBold": False,
                                             "m_bItalic": False, "m_bUnderline": False}},
               m_dimLineSnapDist=0.0, m_leaderShoulderLength=0.0,
               m_tickCategoryId=tick_cat, m_heavyEndCatId=-1,
               m_centerlinePatternCatId=center_cat, m_centerlineTickMarkStyleId=-2,
               m_arrowHeadStyleId=leader_id, m_interiorTickMarkStyleId=leader_id,
               m_leaderTickMarkStyleId=-1, m_witnessLineTickMarkStyleId=-1,
               m_leaderDisplayCondition=1, m_leaderType=1, m_leaderTextLocation=0,
               m_textAlignment=1, m_linearTickType=0, m_radialTickType=8,
               m_dimensionStyleType=0, m_textLoc=0,
               m_radiusDiameterSymbolLocation=0, m_equalityWitnessDisplay=0,
               m_alternateUnits=0, m_interiorTickMarkDisplay=0, m_linearDimType=1,
               m_arcCenterMark=True, m_radiusPrefix=False,
               m_txtBackgroundTransparent=False, m_dimWitnCntrlExtBelow=False,
               m_showOpeningHt=False, m_linearFilledTick=False,
               m_radialFilledTick=False, m_suppressSpaces=False)
    dim = _el("DimensionStyle", dim_id, do,
              [fam, leader_id, dim_id, text_cat, font_id, tick_cat, center_cat],
              flags=14, kind="dim-style")

    fo = _base("FontElem", font_id, m_ownerId=dim_id,
               m_pFont={"ptr_class": "Font", "pid": -1, "value": {
                   "m_name": "Arial", "m_size": 0.0078125, "m_color": 16777216}})
    font = _el("FontElem", font_id, fo, [fam, dim_id, font_id],
               flags=8202, kind="dim-style-font")

    els = [
        leader,
        _category_elem(leader_cat, leader_id, leader_g),
        _gstyle_elem(leader_g, leader_cat, pen=5, color=4294967295, line_pattern=-1),
        dim,
        _category_elem(text_cat, dim_id, text_g),
        _gstyle_elem(text_g, text_cat, pen=1, color=0, line_pattern=-3000010),
        font,
        _category_elem(tick_cat, dim_id, tick_g),
        _gstyle_elem(tick_g, tick_cat, pen=5, color=0, line_pattern=-1),
        _category_elem(center_cat, dim_id, center_g),
        _gstyle_elem(center_g, center_cat, pen=1, color=0, line_pattern=-3000010),
    ]
    return dim_id, els


def new_center_reference_planes(ids, self_family_id: int, *, gen_view_id: int = -1,
                                length_ft: float = 10.0, height_ft: float = 10.0
                                ) -> List[SkelElement]:
    """The two ORIGIN reference planes every family document carries:
    "Center (Front/Back)" (m_refName 4, the XZ plane through the origin,
    line drawn along +X) and "Center (Left/Right)" (m_refName 1, the YZ
    plane, line along +Y).  Both ``m_definesOrigin`` True and locked
    [VERIFIED on every specimen: refName pair (4, 1) with definesOrigin]."""
    L = float(length_ft) / 2.0
    env = ((-L, -2.0), (L, float(height_ft)))
    fb = new_reference_plane(_alloc(ids), self_family_id,
                             name="Center (Front/Back)", ref_name="center_fb",
                             free_end=(-L, 0.0, 0.0), bubble_end=(L, 0.0, 0.0),
                             normal=(0.0, 0.0, 1.0), gen_view_id=gen_view_id,
                             extent=env, defines_origin=True, locked=True)
    lr = new_reference_plane(_alloc(ids), self_family_id,
                             name="Center (Left/Right)", ref_name="center_lr",
                             free_end=(0.0, -L, 0.0), bubble_end=(0.0, L, 0.0),
                             normal=(0.0, 0.0, 1.0), gen_view_id=gen_view_id,
                             extent=env, defines_origin=True, locked=True)
    return [fb, lr]


# ---------------------------------------------------------------------------
# FAMILY PARAMETERS  (ParamElemFamily + the type-table value shape)
# ---------------------------------------------------------------------------

#: the :func:`our_guid` purpose of LOCAL family-parameter identities (the
#: GUID policy of skills/tekton-ifc/references/shared-parameters-mapping.md
#: §1.3): a local ``revit.local.family:`` parameter's 32-hex session part is
#: ``our_guid(LOCAL_PARAM_PURPOSE, family_name, caption)`` = uuid5 under
#: 'rvt-writer.gen.family.parameters' over '<family name>|<caption>' -- the
#: same family + caption always yields the same identity (two builds agree
#: byte for byte) and no Autodesk-minted GUID is ever reused.  SHARED
#: parameters never come from here (:func:`new_shared_parameter`).
LOCAL_PARAM_PURPOSE = "family.parameters"


def local_param_guid(family_name: str, caption: str) -> str:
    """The deterministic session GUID of a LOCAL family parameter."""
    return our_guid(LOCAL_PARAM_PURPOSE, family_name, caption)


def param_type_id(family_guid: str, param_elem_id: int) -> str:
    """The ``m_typeId`` identity of a family parameter:
    ``revit.local.family:<32 hex guid><8 hex elem id>-1.0.0`` [VERIFIED
    format; the guid is a per-creation-session GUID -- OURS is
    :func:`local_param_guid` unless the caller passes one]."""
    g = uuid.UUID(str(family_guid)).hex
    return f"revit.local.family:{g}{int(param_elem_id) & 0xFFFFFFFF:08x}-1.0.0"


def shared_param_type_id(guid: str) -> str:
    """The ``m_typeId`` identity of a SHARED parameter:
    ``revit.local.shared:<32 hex guid>-1.0.0`` -- the GUID token IS the
    shared parameter's GUID [VERIFIED 466/466 project-side,
    ``rvt.genesis.residue_b.shared_parameter``]."""
    return f"revit.local.shared:{uuid.UUID(str(guid)).hex}-1.0.0"


#: the family-parameter definition classes a project-side loader TWINS
PARAM_TWIN_CLASSES = ("ParamElemFamily", "ParamElemExternal")


def retarget_param_twin(obj: dict, twin_id: int, host_family_id: int,
                        session_guid_hex: str) -> dict:
    """The object rewrites of a host-side parameter TWIN (both loaders):
    ``m_id`` / ``m_pParamDef.m_paramElemId`` -> the host id, ``m_famId`` ->
    the host Family [VERIFIED 455334 vs 786844], and the identity re-homed
    by SCHEME: a session-scoped ``revit.local.family:`` identity takes the
    host session GUID + host id; a global ``revit.local.shared:<guid>``
    identity (and its ``m_externalParamKey``) is the shared parameter and is
    kept verbatim.  Mutates and returns ``obj``."""
    obj["m_id"] = int(twin_id)
    obj["m_famId"] = int(host_family_id)
    pd = ((obj.get("m_pParamDef") or {}).get("value") or {})
    pd["m_paramElemId"] = int(twin_id)
    tt = pd.get("m_typeId")
    cur = (tt or {}).get("m_typeId") if isinstance(tt, dict) else None
    if not str(cur or "").startswith("revit.local.shared:"):
        pd["m_typeId"] = {"m_typeId": param_type_id(session_guid_hex, twin_id)}
    return obj


def new_family_parameter(elem_id: int, self_family_id: int, name: str, *,
                         spec_type_id: str = SPEC_LENGTH,
                         group_type_id: str = PGROUP_DIMENSIONS,
                         family_guid: Optional[str] = None,
                         family_name: str = "",
                         is_instance: bool = False, description: str = "",
                         read_only: bool = False, user_visible: bool = True,
                         restriction: int = 1, flags: int = 8218) -> SkelElement:
    """A ``ParamElemFamily`` = one FAMILY PARAMETER (its definition; the
    per-type VALUES live in the self-Family's ``FamilyTypeTable`` /
    ``m_familyParams``, keyed by this element's id as the paramId).

    [VERIFIED byte-exact vs the .rfa's Height / Width / Length parameters]
    ``spec_type_id`` = the measurable spec (:data:`SPEC_LENGTH`, voltage...);
    ``group_type_id`` = the properties-palette group; ``family_guid`` seeds
    the ``revit.local.family`` identity (default: the deterministic
    :func:`local_param_guid` of ``family_name`` + ``name``).
    ``restriction`` 1 [VERIFIED on all specimen params; meaning UNKNOWN].

    STORAGE-CLASS LAW (issue #333 round 24, measured on a Revit-2026-born
    Text + Integer specimen): :data:`SPEC_TEXT` selects a ``ParamDefString``
    and :data:`SPEC_INTEGER` a ``ParamDefInt`` with int32 bounds -- both
    WITHOUT ``m_specTypeId`` / ``m_restriction`` / ``m_boundless``; only
    measurable (double-valued) specs use ``ParamDefValue``.
    """
    fam_guid = family_guid or local_param_guid(family_name, name)
    o = element_base(elem_id, cell_list=False, design_option=FAMILY_DESIGN_OPTION)
    o["m_famId"] = int(self_family_id)
    o["m_description"] = str(description)
    base_def = {
        "m_dynamicGroupName": "",
        "m_groupTypeId": {"m_typeId": str(group_type_id)},
        "m_caption": str(name),
        "m_typeId": {"m_typeId": param_type_id(fam_guid, elem_id)},
        "m_paramElemId": int(elem_id),
        "m_allowVaryBetweenGroups": False,
        "m_readOnly": bool(read_only),
        "m_userVisible": bool(user_visible),
    }
    if spec_type_id == SPEC_YESNO:
        # ParamDefYesNo carries NO own fields (schema) -- the same shape as
        # ParamDefString, and like it no m_specTypeId is written.  Extends the
        # #333 storage-class law to the boolean case (#705).
        o["m_pParamDef"] = _ptr("ParamDefYesNo", base_def)
    elif spec_type_id == SPEC_TEXT:
        o["m_pParamDef"] = _ptr("ParamDefString", base_def)
    elif spec_type_id == SPEC_INTEGER:
        o["m_pParamDef"] = _ptr("ParamDefInt", dict(
            base_def, m_lowBound=_INT32_LOW, m_upBound=_INT32_HIGH))
    else:
        o["m_pParamDef"] = _ptr("ParamDefValue", dict(
            base_def,
            m_specTypeId={"m_typeId": str(spec_type_id)},
            m_restriction=int(restriction),
            m_boundless=False))
    o["m_instanceParam"] = bool(is_instance)
    hdr = element_header("ParamElemFamily", category=-1,
                         deletion=[self_family_id, elem_id],
                         flags=flags, visible_view_flags=-32768,
                         family_id=self_family_id)
    return SkelElement(elem_id, "ParamElemFamily", hdr, o, None, kind="family_param",
                       refs={"family": self_family_id, "caption": name,
                             "spec": spec_type_id, "group": group_type_id})


#: the ParamDef storage class of a shared FAMILY parameter.  ``ParamDefValue``
#: keeps the definition block byte-for-byte the shape our LOCAL family
#: parameters carry (spec id + restriction 1 + boundless F, the certified
#: .rfa lineage), so the shared variant differs from the local one in the
#: element class + GUID identity ONLY.  The project-side census
#: (``residue_b.PARAM_DEF_CLASSES``: text -> ParamDefString, integer ->
#: ParamDefInt ...) is the other candidate; pass ``kind=`` to select it.
SHARED_PARAM_DEFAULT_KIND = "ParamDefValue"


def new_shared_parameter(elem_id: int, self_family_id: int, name: str, guid: str, *,
                         spec_type_id: str = SPEC_LENGTH,
                         group_type_id: str = PGROUP_DIMENSIONS,
                         kind: str = SHARED_PARAM_DEFAULT_KIND,
                         description: str = "", user_visible: bool = True,
                         hide_when_no_value: bool = False,
                         flags: int = 8218) -> SkelElement:
    """A ``ParamElemExternal`` = one SHARED family parameter: the definition
    a project schedule / tag binds BY GUID.

    ``guid`` is the shared parameter's identity, copied VERBATIM from OUR
    shared-parameter file (never regenerated): it lands in
    ``m_externalParamKey.m_guidValue`` AND in the ``m_typeId`` token
    (:func:`shared_param_type_id`).  The object layout is the [VERIFIED
    project-side] ``rvt.genesis.residue_b.shared_parameter`` constructor's,
    overlaid with the two family-document conventions every element of ours
    carries (``m_famId`` = the self-Family, ``m_designOptionId`` -4); the
    header mirrors :func:`new_family_parameter`'s.  Its per-type VALUES are
    keyed by this element id exactly like a local parameter's.  [UNVERIFIED
    family-side: no specimen family of the corpus carries a shared
    parameter -- a certification-batch candidate, not a loads claim.]
    """
    from ..genesis import residue_b as _RB
    rec = _RB.shared_parameter(str(name), str(guid), kind=kind, spec=str(spec_type_id),
                               group=str(group_type_id), description=description,
                               user_visible=user_visible,
                               hide_when_no_value=hide_when_no_value, elem_id=int(elem_id))
    o = rec.obj
    o["m_famId"] = int(self_family_id)
    o["m_designOptionId"] = FAMILY_DESIGN_OPTION
    hdr = element_header("ParamElemExternal", category=-1,
                         deletion=[self_family_id, elem_id],
                         flags=flags, visible_view_flags=-32768,
                         family_id=self_family_id)
    return SkelElement(int(elem_id), "ParamElemExternal", hdr, o, None, kind="shared_param",
                       refs={"family": self_family_id, "caption": name,
                             "spec": spec_type_id, "group": group_type_id,
                             "guid": rec.refs["guid"], "kind": kind})


# -- OUR shared-parameter file (the GUID identities a schedule / tag binds by)

@dataclass
class SharedParamDef:
    """One ``PARAM`` row of a Revit shared-parameter file."""
    guid: str
    name: str
    datatype: str
    group: str = ""
    description: str = ""
    visible: bool = True


#: shared-parameter-file DATATYPE token -> the spec ids (version-less) a
#: family parameter of that caption may carry: a schedule bound to the
#: file's definition would reject a value of any other type
SHARED_DATATYPE_SPECS = {
    "TEXT": ("autodesk.spec:spec.string",),
    "INTEGER": ("autodesk.spec:spec.int64", "autodesk.spec.aec:integer"),
    "NUMBER": ("autodesk.spec.aec:number",),
    "LENGTH": ("autodesk.spec.aec:length",),
    "AREA": ("autodesk.spec.aec:area",),
    "VOLUME": ("autodesk.spec.aec:volume",),
    "ANGLE": ("autodesk.spec.aec:angle",),
    "ELECTRICAL_POTENTIAL": ("autodesk.spec.aec.electrical:potential",),
    "ELECTRICAL_CURRENT": ("autodesk.spec.aec.electrical:current",),
    "ELECTRICAL_APPARENT_POWER": ("autodesk.spec.aec.electrical:apparentPower",),
    "ELECTRICAL_WATTAGE": ("autodesk.spec.aec.electrical:wattage",),
    "ELECTRICAL_LUMINOUS_FLUX": ("autodesk.spec.aec.electrical:luminousFlux",),
    "ELECTRICAL_EFFICACY": ("autodesk.spec.aec.electrical:efficacy",),
    "COLOR_TEMPERATURE": ("autodesk.spec.aec.electrical:colorTemperature",),
    "MASS": ("autodesk.spec.aec.structural:mass",),      # the equipment sets' Operating Weight (#630/#658)
}


def shared_datatype_matches(datatype: str, spec_type_id: str) -> bool:
    """True when a file row's DATATYPE and a family parameter's spec agree."""
    return str(spec_type_id).rsplit("-", 1)[0] in SHARED_DATATYPE_SPECS.get(str(datatype).upper(), ())


def read_shared_parameter_file(path: str) -> Dict[str, SharedParamDef]:
    """Parse a Revit shared-parameter TXT (the documented tab-separated
    grammar: ``#`` comments, ``*KIND<TAB>col...`` header rows naming the
    columns of the ``KIND<TAB>value...`` rows that follow -- META / GROUP /
    PARAM) into ``{name: SharedParamDef}``.  UTF-8 or UTF-16 (Revit writes
    UTF-16 LE with a BOM; ours is UTF-8).  Duplicate names, a malformed GUID
    or a PARAM row before its ``*PARAM`` header -> ``ValueError``."""
    with open(path, "rb") as fh:
        raw = fh.read()
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    headers: Dict[str, List[str]] = {}
    groups: Dict[str, str] = {}
    out: Dict[str, SharedParamDef] = {}
    for ln, line in enumerate(raw.decode(enc).splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kind, *rest = line.split("\t")
        if kind.startswith("*"):
            headers[kind[1:]] = rest
            continue
        cols = headers.get(kind)
        if cols is None:
            raise ValueError(f"{path}:{ln}: {kind} row before its *{kind} header")
        row = dict(zip(cols, rest))                   # short rows: .get(col, "") below
        if kind == "GROUP":
            groups[row.get("ID", "")] = row.get("NAME", "")
        elif kind == "PARAM":
            name = row.get("NAME", "")
            try:
                guid = str(uuid.UUID(row.get("GUID", "")))
            except ValueError:
                raise ValueError(f"{path}:{ln}: PARAM {name!r} has no valid GUID") from None
            if name in out:
                raise ValueError(f"{path}:{ln}: duplicate PARAM name {name!r}")
            out[name] = SharedParamDef(
                guid=guid, name=name, datatype=row.get("DATATYPE", ""),
                group=groups.get(row.get("GROUP", ""), row.get("GROUP", "")),
                description=row.get("DESCRIPTION", ""),
                visible=row.get("VISIBLE", "1").strip() != "0")
    return out


#: ``shared_params=``: a shared-parameter file path, or its parsed rows
SharedParamsArg = Union[None, str, Dict[str, SharedParamDef]]


def shared_param_table(shared_params: SharedParamsArg) -> Dict[str, SharedParamDef]:
    """Normalise ``shared_params=`` (None | path | parsed rows) to rows."""
    if not shared_params:
        return {}
    if isinstance(shared_params, str):
        return read_shared_parameter_file(shared_params)
    return dict(shared_params)


def family_param_value(param_id: int, value: Any = 0.0, *,
                       elem_id: int = -1, is_instance: bool = False,
                       reporting: bool = False) -> dict:
    """One ``FamilyParamValue`` entry -- the shape used BOTH by the
    self-Family's ``m_familyParams`` (current type) and by every
    ``FamilyTypeTable`` type row.

    ``param_id`` = a built-in parameter id (negative) or a ``ParamElemFamily``
    element id (positive user parameter).  ``value`` = float for numeric /
    length / electrical params (internal units), str for text (Description
    / Manufacturer / Model / URL), int for enums / yes-no (stored in
    ``m_int``); an ElementId-valued parameter (e.g. a material) sets
    ``elem_id``.  [VERIFIED shape on the .rfa's 4 types + rme families]
    """
    entry = {"m_str": "", "m_oExpression": None, "m_value": 0.0,
             "m_elemId": int(elem_id), "m_paramId": int(param_id),
             "m_int": 0, "m_instance": bool(is_instance),
             "m_reporting": bool(reporting)}
    if isinstance(value, bool):
        entry["m_int"] = int(value)
    elif isinstance(value, int) and not isinstance(value, float) and elem_id < 0:
        entry["m_int"] = int(value)
    elif isinstance(value, float):
        entry["m_value"] = float(value)
    elif isinstance(value, str):
        entry["m_str"] = str(value)
    elif isinstance(value, dict):                      # explicit entry override
        entry.update(value)
    return entry


def family_params_block(params: Sequence[dict]) -> dict:
    """A ``FamilyParams`` owned object (the value set of ONE type).

    In the standalone ``.rfa`` the self-Family carries
    ``m_geomRefHandles`` inside its type-table rows only [VERIFIED: the
    self-Family's own ``m_familyParams`` = current-type values, no handles]."""
    return _ptr("FamilyParams", {"m_params": [dict(p) for p in params],
                                  "m_geomRefHandles": {"m_offsetGeomMap": []}})


def family_type_row(name: str, params: Sequence[dict]) -> dict:
    """One ``FamilyTypeTable.m_pairs`` row = {name, params (+ geom-ref
    handles)} [VERIFIED shape on the .rfa's 4-type table]."""
    return {"name": str(name),
            "params": {"m_params": [dict(p) for p in params],
                       "m_geomRefHandles": {"m_offsetGeomMap": []}}}


def family_type_table(types: Sequence[Tuple[str, Sequence[dict]]],
                      current_index: int = 0) -> dict:
    """The self-Family's ``FamilyTypeTable`` (owned): every TYPE of a
    standalone family document (``m_idx`` = the current type; -1 = the
    single anonymous type of an embedded document whose types live at the
    host) [VERIFIED both forms]."""
    return _ptr("FamilyTypeTable", {
        "m_idx": int(current_index),
        "m_pairs": [family_type_row(n, ps) for n, ps in types],
    })


def family_params_order_cell(groups: Sequence[Tuple[str, Sequence[int]]]) -> dict:
    """The self-Family's ``FamilyParamsOrderCell`` (the properties-palette
    ordering of parameters by group) [VERIFIED shape on the .rfa: groups =
    (group type id, [param ids])]."""
    return _ptr("FamilyParamsOrderCell", {"m_sortedParams": [
        {"m_groupTypeId": {"m_typeId": str(g)}, "m_paramIds": [int(p) for p in ids]}
        for g, ids in groups]})


# ---------------------------------------------------------------------------
# THE SELF-FAMILY
# ---------------------------------------------------------------------------

#: default behaviour flags of a MODEL family (furniture / equipment /
#: fixture / generic model) [VERIFIED = the shared values of the specimens;
#: per-flag semantics INFERRED from the names].  Callers override any of
#: them through ``new_self_family(..., overrides={...})``.
DEFAULT_FAMILY_FLAGS: Dict[str, Any] = {
    "m_isModel": True, "m_is2d": False, "m_isCrvDriven": False,
    "m_isVertical": False, "m_isParametric": True,
    "m_shouldStayParametric": False, "m_contentProtected": False,
    "m_isAboutToBecomeParametric": True, "m_couldAutojoin": True,
    "m_bIsSavable": True, "m_bHasTypesFromCatalog": False,
    "m_bHasSimpleCuts": False, "m_bHasComplexCuts": False,
    "m_bHasBaseArrays": False, "m_bIsHostBased": False,
    "m_bHasInstances": False, "m_isWorkPlaneBased": False,
    "m_bShared": False, "m_bUsePreCutShape": True,
    "m_bElevationMarkBody": True, "m_bForceProperMirroring": False,
    "m_bStructUseCap": False, "m_curveBased": False,
    "m_bElecKeepAnnotationOrientation": False, "m_isRebarShape": False,
    "m_bStretchingDisallowed": False, "m_bIsNew2010": False,
    "m_bHasLabeledDimensions": False, "m_bCutback": True,
    "m_bAllowCutWithUnattachedVoids": False, "m_canHostRebar": False,
    "m_isSpiralShape": False, "m_enableCuttingInViews": True,
    "m_hasRoomCalculationPoint": False, "m_bIsSelfOrienting": False,
    "m_rotateTagWithComponent": False, "m_keepTextReadable": False,
    "m_rotateTagTextWithComponent": False,
    "m_inPlace": False, "m_isCurtainPanel": False, "m_bFromADPx": False,
    "m_elevationFixed": False, "m_isUserCreated": True,
    "m_setCreated2011FaceBasedFamily": False, "m_bHasAnyDummyRefs": False,
    # enums [VERIFIED shared values]
    "m_eRenderModelType": 0, "m_eSymbolicRepType": 0,
    "m_eStructConnectionApplyTo": 0, "m_eBraceRepType": 1,
    "m_eStructMaterialType": 4, "m_eBeamCutbackForColumn": 1,
    "m_eStructHiddenViewDisplayType": 0, "m_lightSourceDefBits": 0,
    "m_eProfileFamUsage": 0, "m_eProfileFamDefinition": 0,
    "m_eProteinRenderType": 0, "m_roundConnDimType": 1, "m_panelConfig": 1,
    "m_familyNestingBehavior": 0, "m_tagOrientationBehavior": 0,
}

#: Revit's app-version marker written by the 2026 family editor into
#: m_appVersionAtLoad / m_appVersionAtInitialLoad on OLD content (2134 on
#: the 2009-era rme families) or -2 on native 2026 documents [VERIFIED
#: values; -2 = "current" sentinel INFERRED].
APP_VERSION_CURRENT = -2


def new_self_family(elem_id: int, category_id: int, *,
                    name: str = "",
                    path: str = "",
                    element_ids: Sequence[int] = (),
                    element_index: Optional[Sequence[Tuple[int, int]]] = None,
                    types: Optional[Sequence[Tuple[str, Sequence[dict]]]] = None,
                    current_type: int = 0,
                    family_params: Optional[Sequence[dict]] = None,
                    param_groups: Optional[Sequence[Tuple[str, Sequence[int]]]] = None,
                    part_type: int = 0,
                    work_plane_based: bool = False,
                    trivial_param_ids: Sequence[int] = (),
                    locked_param_ids: Sequence[int] = (),
                    deletable_elements: Sequence[int] = (),
                    cat_keys: int = 5,
                    predefined_limit_idx: int = 35,
                    app_version_at_load: int = APP_VERSION_CURRENT,
                    ref_type_ids: Sequence[int] = (),
                    refs: Sequence[int] = (),
                    fsdos: Sequence[dict] = (),
                    dim_constr_mgr: Optional[dict] = None,
                    overrides: Optional[Dict[str, Any]] = None,
                    flags: int = 26) -> SkelElement:
    """The document's OWN ``Family`` element -- the self-Family every other
    element's ``m_famId`` points at.

    [VERIFIED structure on all specimens; byte-exact on the .rfa's self-Family
    when fed the specimen's own lists]  Carries:

    * ``m_categoryId`` -- the family CATEGORY (a built-in OST id);
    * ``m_pFamilyTypes`` -- the ``FamilyTypeTable`` = ALL types (name +
      per-type parameter values) of a standalone family; ``m_idx`` = current;
    * ``m_familyParams`` -- the CURRENT type's parameter values;
    * ``m_cellList`` -- one ``FamilyParamsOrderCell`` (parameter ordering
      by properties-palette group);
    * ``m_familyIds`` -- an ``ElementIdIndexPairSet`` mapping EVERY element
      of the document to a monotonic "absorbed" index (the family editor's
      element index; ``m_nextAbsorbedIndex`` = next free) [VERIFIED: max
      index + 1 == m_nextAbsorbedIndex on the .rfa];
    * ~90 behaviour flags / enums (:data:`DEFAULT_FAMILY_FLAGS`),
      ``m_partType`` (14 panelboard, ...), ``m_isWorkPlaneBased``;
    * an all-zero ``m_famDocGUID`` and null ``m_oFamDoc`` (the SELF family
      has no embedded document -- it IS the document) [VERIFIED].

    ``element_ids`` = every element id of the document (in creation order):
    it seeds ``m_familyIds`` and the header's deletion list (the family
    owns all its elements) -- pass the FINAL list (:class:`FamilyDoc` does
    this in ``finalize``).  ``dim_constr_mgr`` = a ``FamDimConstrMgrImpl``
    dict (parameter <-> dimension constraint expressions; the labelled-
    dimension machinery -- empty for a document without labelled
    dimensions).  seq-103 rep = ``SerializedDummy``.
    """
    from ..genesis.types import blank_object
    o = blank_object("Family")
    # -- Element base ------------------------------------------------------
    for k in ("m_pParamValueSetDouble", "m_pParamValueSetInt",
              "m_pParamValueSetAString", "m_pParamValueSetElementId",
              "m_geomSteps", "m_pGeomTable"):
        o[k] = None
    o["m_constrInfo"] = []
    o["m_docAccess"] = {"m_pDoc": _weak(1)}
    o["m_id"] = int(elem_id)
    for k in ("m_assocLevelId", "m_famId", "m_unplacedOwnerId",
              "m_ownerDBViewId", "m_createdPhaseId", "m_demolishedPhaseId",
              "m_designOptionId"):
        o[k] = -1                       # the self-Family is NOT design-option -4
    o["m_locked"] = o["m_moribund"] = o["m_dummy"] = False
    # parameter-ordering cell (properties palette group order)
    groups = list(param_groups) if param_groups is not None else []
    o["m_cellList"] = (_ptr("CellList", {"m_cells": [family_params_order_cell(groups)]})
                     if groups else _ptr("CellList", {"m_cells": [
                         family_params_order_cell([])]}))
    # -- family core -----------------------------------------------------------
    o["m_familyParams"] = family_params_block(list(family_params or []))
    o["m_trivialParamIds"] = [int(p) for p in trivial_param_ids]
    o["m_name"] = str(name)                 # '' in a standalone .rfa (name = file)
    o["m_path"] = str(path)                 # Autodesk stores the authoring path; OURS ''
    o["m_famCatalogKeys"] = [{"m_str": ""} for _ in range(int(cat_keys))]
    tps = list(types) if types is not None else []
    if tps:
        o["m_pFamilyTypes"] = family_type_table(tps, current_index=current_type)
    else:
        o["m_pFamilyTypes"] = _ptr("FamilyTypeTable", {"m_idx": -1, "m_pairs": []})
    o["m_pADoc"] = _weak(1)
    o["m_oFamDoc"] = None
    o["m_deletableElements"] = [int(x) for x in deletable_elements]
    o["m_oldCurveElemsWithBadSketchAndSP"] = []
    o["m_lockedParameterIdsForDirectManipulation"] = [int(p) for p in locked_param_ids]
    # the family-editor element index: every element -> absorbed index
    eids = [int(e) for e in element_ids]
    if element_index is not None:                 # explicit (id, index) pairs
        pairs = [(int(a), int(b)) for a, b in element_index]
    else:
        pairs = [(e, i) for i, e in enumerate(eids)]
    o["m_familyIds"] = _ptr("ElementIdIndexPairSet", {"m_data": [
        {"m_elementId": e, "m_index": i} for e, i in pairs]})
    o["m_oHostFaceGeomRef"] = None
    o["m_dbviewInfos"] = []
    o["m_fsdos"] = [dict(f) for f in fsdos]
    for k in ("m_dumpSymName", "m_omniClassCode", "m_classificationDescription",
              "m_seekItemId", "m_familyNameKeyText", "m_structuralCodeName",
              "m_protectionAccessKey"):
        o[k] = ""
    o["m_tagCurveAttachmentProportion"] = -1.0
    o["m_categoryId"] = int(category_id)
    o["m_keyExtParamId"] = -1
    o["m_ownerSymbolId"] = -1
    o["m_regeneratingGroupId"] = -1
    o["m_famDocGUID"] = "00000000-0000-0000-0000-000000000000"
    o["m_nextAbsorbedIndex"] = (max((i for _e, i in pairs), default=-1) + 1)
    o["m_predefinedLimitIdx"] = int(predefined_limit_idx)
    o["m_appVersionAtLoad"] = int(app_version_at_load)
    o["m_appVersionAtInitialLoad"] = int(app_version_at_load)
    o.update({k: v for k, v in DEFAULT_FAMILY_FLAGS.items()})
    o["m_partType"] = int(part_type)
    o["m_isWorkPlaneBased"] = bool(work_plane_based)
    # dimension-constraint manager (parameter <-> labelled dimension exprs)
    if dim_constr_mgr is None:
        mgr = blank_object("FamDimConstrMgrImpl")
        mgr["m_pFam"] = _weak(2)                # -> this Family element
        dim_constr_mgr = _ptr("FamDimConstrMgrImpl", mgr)
    o["m_oFamDimConstrMgr"] = dim_constr_mgr
    o["m_refs"] = [dict(r) if isinstance(r, dict) else
                   _ptr("FamilyElemRef", {"m_elemId": int(r)}) for r in refs]
    o["m_refTypeIds"] = [int(r) for r in ref_type_ids]
    o["m_oDefaultStretchLine"] = None
    o["m_outOfFamilyRefs"] = []
    o["m_outOfFamilyHostIds"] = []
    o["m_outOfFamilyHostGrefs"] = []
    o["m_oFamilyReferenceIdxMgr"] = None
    for k in ("m_fixedElevation", "m_defaultColumnHeight", "m_defaultHostThickness",
              "m_defaultHeightAboveLevel", "m_inplaceFamElevation"):
        o[k] = 0.0
    o["m_surrogateId"] = -1
    if overrides:
        o.update(dict(overrides))
    # header: the family owns every element of its document
    hdr = element_header("Family", category=-1, deletion=list(eids) + [elem_id],
                         flags=flags, visible_view_flags=-32768)
    return SkelElement(elem_id, "Family", hdr, o, None, kind="self_family",
                       refs={"category": category_id, "n_elements": len(eids)},
                       notes=["the document's self-Family; owns every element"])


def refresh_self_family_index(fam: SkelElement, element_ids: Sequence[int]) -> None:
    """Re-seed the self-Family's element index / ownership from the final
    element list (called by :meth:`FamilyDoc.finalize`)."""
    eids = [int(e) for e in element_ids]
    fam.obj["m_familyIds"]["value"]["m_data"] = [
        {"m_elementId": e, "m_index": i} for i, e in enumerate(eids)]
    fam.obj["m_nextAbsorbedIndex"] = len(eids)
    par = fam.header["m_parents"]["value"]
    par["m_deletion"] = sorted(set(eids + [fam.elem_id]))


# ---------------------------------------------------------------------------
# ELECTRICAL CONNECTOR  (ConnectorElem + ConnectorElemDomainElectrical)
# ---------------------------------------------------------------------------

#: Revit's ``ElectricalSystemType`` for a power connector's domain
#: (``m_systemType``).  Codes from the public Revit API reference,
#: ``ElectricalSystemType`` enumeration: PowerBalanced = 30, PowerUnBalanced
#: = 31 (PowerCircuit = 6 is a CIRCUIT's type, never a connector's) -- the
#: family editor's "System Type: Power - Balanced / Power - Unbalanced"
#: [VERIFIED 31 on every electrical connector specimen: Revit's own
#: panelboard / lighting / receptacle connectors are Power-Unbalanced;
#: no Power-Balanced (30) specimen decoded yet].  Sources + quotes:
#: docs/writer/family-skeleton.md section 7.
ELECTRICAL_SYSTEM_POWER_BALANCED = 30
ELECTRICAL_SYSTEM_POWER_UNBALANCED = 31
#: ``system_type`` names accepted by :func:`electrical_domain` (or the code)
ELECTRICAL_SYSTEM_TYPES = {
    "power_balanced": ELECTRICAL_SYSTEM_POWER_BALANCED,
    "power_unbalanced": ELECTRICAL_SYSTEM_POWER_UNBALANCED,
}
#: ``PowerFactorStateType`` (``m_powerFactorState``): Lagging = 1 (Leading
#: = 0) [API reference enumeration; VERIFIED 1 on every specimen]
POWER_FACTOR_LAGGING = 1

#: connector ELEMENT-PROPERTY built-ins a family parameter can DRIVE via
#: the connector's ``FamilyParametrizedElemParamsCell`` ("associate family
#: parameter") [VERIFIED ids on the lighting-fixture / receptacle
#: connectors: voltage driven by 'Ballast Voltage' / 'Switch Voltage',
#: apparent load by the wattage BIP / a 'Load' user param; names INFERRED
#: = RBS_ELEC_VOLTAGE / RBS_ELEC_APPARENT_LOAD]
ELEM_PROP_VOLTAGE = -1140002
ELEM_PROP_APPARENT_LOAD = -1140005
#: the family-side wattage / apparent-load built-in parameter a lighting
#: family carries on its self-Family [VERIFIED -1140004 = 64 W internal
#: 688.89 on the recessed fixture; ELECTRICAL_WATTAGE name INFERRED]
BIP_FAMILY_WATTAGE = -1140004


def phase_loads_va(apparent_load_va: Union[float, Sequence[float]],
                   poles: int) -> List[float]:
    """The per-phase apparent loads [phase 1, 2, 3] in VA of a ``poles``-pole
    power connector.

    A NUMBER is the connector's whole (balanced) load and is split equally
    over phases 1..``poles`` -- a balanced load is by definition the same
    load on every pole, and Revit totals a connected load as "Apparent Load
    Phase A + Apparent Load Phase B + Apparent Load Phase C" (help: About
    Load Calculations), so 75 kVA on 3 poles = 25 kVA per phase.  A SEQUENCE
    is an explicit (unbalanced) per-phase list; it may not be longer than
    ``poles`` because "Apparent Load Phase 2 [is] active only when ... Number
    of Poles > 1" and Phase 3 "... > 2" (help: Connector Properties).
    Phases beyond ``poles`` are 0.
    """
    poles = int(poles)
    if poles not in (1, 2, 3):
        raise ValueError(f"poles must be 1, 2 or 3 (Revit 'Number of Poles'), got {poles}")
    if isinstance(apparent_load_va, (int, float)):
        each = float(apparent_load_va) / poles
        loads = [each] * poles
    else:
        loads = [float(v) for v in apparent_load_va]
        if not 1 <= len(loads) <= poles:
            raise ValueError(f"{len(loads)} per-phase loads given for a {poles}-pole "
                             "connector (phase n is only active when poles >= n)")
    return loads + [0.0] * (3 - len(loads))


def electrical_domain(*, voltage_v: float, poles: int = 1,
                      apparent_load_va: Union[float, Sequence[float]] = 0.0,
                      power_factor: float = 1.0,
                      load_classification_id: int = -1,
                      description: str = "",
                      system_type: Union[str, int] = "power_unbalanced",
                      primary: bool = True) -> dict:
    """The ``ConnectorElemDomainElectrical`` owned object of a POWER
    connector, from the calc-engine values (display units in, internal out).

    [VERIFIED unit rule + field values on the panelboard / lighting /
    receptacle connectors -- all three are ``system_type`` 31 =
    Power-Unbalanced, single load on phase 1, ``m_dApparentLoad`` 0.0]
    Load law (public Revit help "Connector Properties" + API reference; URLs
    and quotes in docs/writer/family-skeleton.md section 7):

    * ``power_unbalanced`` (31, the specimens' type, the default): the load
      lives in ``m_dApparentLoadPhase1..poles`` ("Apparent Load Phase 1 ...
      Active only when Balanced Load is False"; Phase 2 needs poles > 1,
      Phase 3 poles > 2) and ``m_dApparentLoad`` -- "Active only when Balanced
      Load is True" -- stays 0.0 exactly as the specimens store it.  A number
      is split equally over the poles (:func:`phase_loads_va`); a sequence is
      the explicit per-phase list.
    * ``power_balanced`` (30): ``m_dApparentLoad`` carries the whole load (the
      one active load field of a balanced connector) and the phase fields are
      written as its equal split so the two agree whichever a reader shows
      [no Power-Balanced specimen decoded: documented semantics, on-disk
      values of the inactive phase fields UNOBSERVED -- the factory keeps to
      31].  A per-phase sequence is refused: unequal phases are unbalanced.

    ``primary`` = ``m_bIsConnectorPrimary``: "A single connector of each
    discipline is allowed to be primary in each family. The family's
    electrical data that displays in a schedule is derived from the primary
    connector" (help) / ``ConnectorElement.IsPrimary`` (API); the DOCUMENT
    keeps it to one (:meth:`FamilyDoc.resolve_primary`).
    ``load_classification_id`` = an ``ElectricalLoadClassification`` element
    (the document's own copy in a standalone family) -- -1 = unclassified.
    """
    sys_code = (ELECTRICAL_SYSTEM_TYPES.get(system_type) if isinstance(system_type, str)
                else int(system_type))
    if sys_code not in ELECTRICAL_SYSTEM_TYPES.values():
        raise ValueError(f"system_type must be one of {sorted(ELECTRICAL_SYSTEM_TYPES)} "
                         f"or their codes, got {system_type!r}")
    balanced = sys_code == ELECTRICAL_SYSTEM_POWER_BALANCED
    if balanced and not isinstance(apparent_load_va, (int, float)):
        raise ValueError("a per-phase load list is an unbalanced load: use "
                         "system_type='power_unbalanced'")
    phases = phase_loads_va(apparent_load_va, poles)
    return {
        "m_pConnElem": _weak(2),
        "m_dVoltage": volts(voltage_v),
        "m_dApparentLoad": voltamps(sum(phases)) if balanced else 0.0,
        "m_dApparentLoadPhase1": voltamps(phases[0]),
        "m_dApparentLoadPhase2": voltamps(phases[1]),
        "m_dApparentLoadPhase3": voltamps(phases[2]),
        "m_dPowerFactor": float(power_factor),
        "m_idLoadClassification": int(load_classification_id),
        "m_nNumberOfPoles": int(poles),
        "m_systemType": sys_code,
        "m_powerFactorState": POWER_FACTOR_LAGGING,
        "m_bIsConnectorPrimary": bool(primary),
        "m_bConnectorUtility": False,
        "m_bSubClassificationMotor": False,
        "m_strConnectorDescription": str(description),
    }


def new_electrical_connector(elem_id: int, self_family_id: int, *,
                             host_element_id: int, host_geom_tag: int,
                             location: Sequence[float] = (0.0, 0.0, 0.0),
                             direction: Sequence[float] = (0.0, 0.0, -1.0),
                             u_axis: Sequence[float] = (-0.0, 1.0, 0.0),
                             offset_uv: Sequence[float] = (0.0, 0.0),
                             angle: float = 0.0,
                             voltage_v: float = 120.0, poles: int = 1,
                             load_class_id: int = -1,
                             apparent_load_va: Union[float, Sequence[float]] = 0.0,
                             power_factor: float = 1.0,
                             description: str = "",
                             system_type: Union[str, int] = "power_unbalanced",
                             primary: bool = True,
                             marker_size_ft: float = 0.4921259842519685,
                             edge_loop_tags: Sequence[int] = (),
                             param_bindings: Sequence[Tuple[int, int]] = (),
                             flip: bool = False,
                             index: int = 1,
                             flags: int = 2058) -> SkelElement:
    """A POWER ``ConnectorElem`` hosted on a planar face.

    [VERIFIED structure vs the panelboard / lighting / receptacle connectors;
    domain values byte-exact when fed the specimen's numbers]  A connector is
    a point + axis frame on a HOST FACE: ``host_element_id``/``host_geom_tag``
    = the face reference (an extrusion face ``m_geomTag``, e.g. 2 = the top
    face of the first extrusion), ``location`` = the connector point on that
    face, ``direction`` = the face normal (flow direction), ``u_axis`` = the
    in-plane U axis; ``marker_size_ft`` = the drawn arrow size (0.492 ft =
    150 mm).  The electrical DOMAIN comes from the calc engine
    (``voltage_v``, ``poles``, ``apparent_load_va``, ``power_factor``,
    ``load_class_id``, ``system_type``, ``primary`` -- laws in
    :func:`electrical_domain`).  ``edge_loop_tags`` = the host face's edge tags
    (``EdgeLoopRef.m_sortedTagArr``) when the face is a real solid face;
    empty for a datum-plane host.  ``param_bindings`` = the "associate
    family parameter" links [(family_param_id_or_bip, elem_prop_bip)] --
    e.g. ``[(voltage_param.elem_id, ELEM_PROP_VOLTAGE),
    (BIP_FAMILY_WATTAGE, ELEM_PROP_APPARENT_LOAD)]`` makes the type's
    voltage / wattage parameters drive the connector [VERIFIED cell + the
    driving user params in the header deletion list].
    seq-103 rep = ``SerializedDummy``.
    """
    px, py, pz = (float(c) for c in location)
    dx, dy, dz = (float(c) for c in direction)
    ux, uy, uz = (float(c) for c in u_axis)
    # V axis = direction x U (right-handed frame on the face)
    vx = dy * uz - dz * uy
    vy = dz * ux - dx * uz
    vz = dx * uy - dy * ux
    s = float(marker_size_ft)
    env = ((0.0, 0.0), (s, s))
    o = element_base(elem_id, cell_list=False, design_option=FAMILY_DESIGN_OPTION)
    cells = []
    if param_bindings:
        cells.append(_ptr("FamilyParametrizedElemParamsCell", {"m_paramDrivenData": [
            {"m_famParamId": int(fp), "m_elemPropId": int(prop),
             "m_geomTag": -1, "m_bIsSymbol": False}
            for fp, prop in param_bindings]}))
    cells.append(_ptr("PatternHelper", {"m_PatternPositionMap": [],
                                          "m_substituteFaceMap": []}))
    o["m_cellList"] = _ptr("CellList", {"m_cells": cells})
    o["m_famId"] = int(self_family_id)
    o["m_pParamValueSetDouble"] = param_set_double([])
    o["m_pParamValueSetInt"] = param_set_int([])
    o["m_pParamValueSetAString"] = param_set_astring([])
    o["m_geomSteps"] = _ptr("GeomStepList", {
        "m_nonBRepGList": [_ptr("ConnectorElemGStep", {
            "m_faceHistTable": [{"m_id": 1, "m_faceHist": {"m_keys": [6, 0, -1]}},
                                {"m_id": 2, "m_faceHist": {"m_keys": [6, 1, -1]}}],
            "m_curveHistTableSet": [], "m_edgeHistTable": [],
            "m_edgeHistTableReverse": [],
            "m_id": 1, "m_version": 0, "m_flags": 237373,
            "m_pElem": _weak(2), "m_oExtraDatas": None})],
        "m_bRepFormGList": [], "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [], "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [1, 1, 1, 1, 1],
        "m_idCounter": 2, "m_flags": 9})
    o["m_pGeomTable"] = _ptr("GeomTable", {
        "m_refPntMirrored": False,
        "m_table": [{"m_geomGeneratorId": -1}, {"m_geomGeneratorId": 1},
                    {"m_geomGeneratorId": 1}],
        "m_bigTableOwner": None, "m_materialMarkers": [], "m_faceTypeMarkers": []})
    o["m_oPlaneRef"] = _ptr("GeomOnPlaneRef", {
        "m_geomRef": {"m_intermediateTags": [], "m_oNextRef": None,
                      "m_elemId": int(host_element_id), "m_ownerDBViewId": -1,
                      "m_foreignElemIdRef": {"m_id64": -1},
                      "m_geomTag": int(host_geom_tag), "m_subTag": -1,
                      "m_famMemberIdx": -1, "m_flags": 0, "m_isLazyRef": False},
        "m_oRawPlaneInLinkCache": None, "m_oFacePointRef": None,
        "m_offset": [float(offset_uv[0]), float(offset_uv[1])],
        "m_angle": float(angle), "m_flip": bool(flip)})
    o["m_oEdgeLoopRef"] = _ptr("EdgeLoopRef", {"m_sortedTagArr":
                                              [int(t) for t in edge_loop_tags]})
    def _face(tag, xv, yv, pid):
        return _ptr("Face", {
            "m_GInfo": {"m_categoryId": -1, "m_tag": int(tag),
                        "m_controlCommand": 0, "m_flags": 524804},
            "m_pFirstLoop": None, "m_faceRegions": [], "m_pGFilling": None,
            "m_oBackgroundFilling": None, "m_renderStyleId": -1, "m_cutType": 0,
            "m_faceFlags_v9": 0,
            "m_pSurf": plane((px, py, pz), xv, yv, env, pid=pid + 2)}, pid=pid)
    o["m_pFaceU"] = _face(1, (dx, dy, dz), (ux, uy, uz), 3)
    o["m_pFaceV"] = _face(2, (ux, uy, uz), (vx, vy, vz), 4)
    o["m_pDomain"] = _ptr("ConnectorElemDomainElectrical", electrical_domain(
        voltage_v=voltage_v, poles=poles, apparent_load_va=apparent_load_va,
        power_factor=power_factor, load_classification_id=load_class_id,
        description=description, system_type=system_type, primary=primary))
    o["m_grepSize"] = float(marker_size_ft)
    o["m_idLinkedElem"] = -1
    o["m_idPrimaryElem"] = int(elem_id)
    o["m_index"] = int(index)
    o["m_reservedTag"] = 0
    dele = [self_family_id, elem_id, host_element_id]
    if load_class_id >= 0:
        dele.append(load_class_id)
    dele += [int(fp) for fp, _p in param_bindings if int(fp) > 0]   # driving user params
    hdr = element_header("ConnectorElem", category=OST_CONNECTORS, deletion=dele,
                         flags=flags, visible_view_flags=-4225,
                         family_id=self_family_id)
    return SkelElement(elem_id, "ConnectorElem", hdr, o, None, kind="connector",
                       refs={"family": self_family_id, "host": host_element_id,
                             "geom_tag": host_geom_tag, "load_class": load_class_id},
                       notes=["power connector; domain from calc-engine values; "
                              "seq103=SerializedDummy"])


# ---------------------------------------------------------------------------
# THE FAMILY DOCUMENT (builder)
# ---------------------------------------------------------------------------

#: identity-data type parameters keyed by our API names
_TYPE_TEXT_PARAMS = {
    "description": BIP_TYPE_DESCRIPTION,
    "url": BIP_TYPE_URL,
    "type_comments": BIP_TYPE_TYPE_COMMENTS,
    "manufacturer": BIP_TYPE_MANUFACTURER,
    "model": BIP_TYPE_MODEL,
}


@dataclass
class FamilyDoc:
    """A family document under construction (skeleton + authored content).

    ``elements`` are :class:`SkelElement`s (the same record shape as the
    project skeleton, ``rvt.genesis.types.TypeRecord`` and
    ``rvt.mutate.NewElement``): each yields its three partition records
    (seq 101/102/103) + an ``ElemTable`` row.  :meth:`finalize` seeds the
    self-Family's element index / ownership from the final list, then
    :meth:`to_rfa` / :meth:`to_embedded_unit` deliver the document.
    """
    category_id: int
    name: str
    host: str = "none"
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    elements: List[SkelElement] = dc_field(default_factory=list)
    ids: Any = None
    family_guid: Optional[str] = None     # None = per-parameter local_param_guid; a GUID = one session GUID for all
    document_guid: str = ""
    shared_params: Dict[str, SharedParamDef] = dc_field(default_factory=dict)   # caption -> OUR file's row
    self_family: Optional[SkelElement] = None
    ref_level: Optional[SkelElement] = None
    level_type: Optional[SkelElement] = None
    refplanes: List[SkelElement] = dc_field(default_factory=list)
    params: Dict[str, SkelElement] = dc_field(default_factory=dict)   # caption -> ParamElemFamily / ParamElemExternal
    types: List[Tuple[str, Dict[Any, Any]]] = dc_field(default_factory=list)
    current_type: int = 0
    connectors: List[SkelElement] = dc_field(default_factory=list)
    load_classes: List[SkelElement] = dc_field(default_factory=list)
    views: List[SkelElement] = dc_field(default_factory=list)
    view_ids: Dict[str, int] = dc_field(default_factory=dict)
    plan_view_id: int = -1
    dim_style_id: int = -1
    object_style_id: int = -1
    retouch_style_ids: Dict[str, int] = dc_field(default_factory=dict)
    part_type: int = 0
    work_plane_based: bool = False
    finalized: bool = False
    notes: List[str] = dc_field(default_factory=list)

    # -- element bookkeeping ------------------------------------------------
    def add(self, *els: SkelElement) -> List[SkelElement]:
        if self.finalized:
            raise RuntimeError("FamilyDoc is finalized; no further elements")
        for e in els:
            self.elements.append(e)
        return list(els)

    def element_ids(self) -> List[int]:
        return [e.elem_id for e in self.elements]

    def by_class(self, class_name: str) -> List[SkelElement]:
        return [e for e in self.elements if e.class_name == class_name]

    # -- authoring API ------------------------------------------------------
    def add_reference_plane(self, name: str, ref_name="not_a_reference", *,
                            free_end: Sequence[float],
                            bubble_end: Sequence[float],
                            normal: Sequence[float] = (0.0, 0.0, 1.0),
                            defines_origin: bool = False, locked: bool = False,
                            subcategory_id: int = -1) -> SkelElement:
        """Add a ``RefPlane`` (see :func:`new_reference_plane`)."""
        rp = new_reference_plane(_alloc(self.ids), self.self_family.elem_id,
                                 name=name, ref_name=ref_name,
                                 free_end=free_end, bubble_end=bubble_end,
                                 normal=normal, gen_view_id=self.plan_view_id,
                                 defines_origin=defines_origin, locked=locked,
                                 subcategory_id=subcategory_id)
        self.refplanes.append(rp)
        self.add(rp)
        return rp

    def add_family_parameter(self, name: str, spec_type_id: str = SPEC_LENGTH,
                             group_type_id: str = PGROUP_DIMENSIONS, *,
                             is_instance: bool = False,
                             formula: Optional[str] = None,
                             default: Any = 0.0) -> SkelElement:
        """Add a user FAMILY PARAMETER and register its default value on
        every type row and the current-type value set: a LOCAL
        ``ParamElemFamily`` -- or, when ``name`` is a row of the document's
        ``shared_params`` (OUR shared-parameter file), the SHARED
        ``ParamElemExternal`` at that row's GUID (:meth:`add_shared_parameter`;
        the row's DATATYPE must agree with ``spec_type_id`` -- a schedule
        bound to the file's definition would reject any other -> ValueError).

        ``spec_type_id`` = the measurable spec (:data:`SPEC_LENGTH`,
        :data:`SPEC_VOLTAGE`, ...); ``group_type_id`` = the palette group;
        ``default`` = the value (internal units) written to every type.
        ``formula`` = the parameter formula text [UNKNOWN encoding: formulas
        live in the ``FamDimConstrMgrImpl`` expression tables which this
        skeleton leaves empty -- carried in ``refs`` for the spec only].
        """
        row = self.shared_params.get(name)
        if row is not None:
            if not shared_datatype_matches(row.datatype, spec_type_id):
                raise ValueError(f"shared parameter {name!r}: OUR file declares DATATYPE "
                                 f"{row.datatype!r} but the family authors it as "
                                 f"{spec_type_id!r} -- fix the file row or the family's "
                                 f"spec, never both GUIDs")
            if is_instance or formula:
                raise ValueError(f"shared parameter {name!r}: instance / formula-driven "
                                 f"shared parameters are not built")
            return self.add_shared_parameter(name, row.guid, spec_type_id, group_type_id,
                                             description=row.description, default=default)
        pe = new_family_parameter(_alloc(self.ids), self.self_family.elem_id, name,
                                  spec_type_id=spec_type_id, group_type_id=group_type_id,
                                  family_guid=self.family_guid, family_name=self.name,
                                  is_instance=is_instance)
        if formula:
            pe.refs["formula"] = str(formula)
            pe.notes.append("formula NOT serialized (dimension-expression tables empty)")
        return self._register_param(name, pe, default)

    def add_shared_parameter(self, name: str, guid: str, spec_type_id: str = SPEC_LENGTH,
                             group_type_id: str = PGROUP_DIMENSIONS, *,
                             kind: str = SHARED_PARAM_DEFAULT_KIND,
                             description: str = "", default: Any = 0.0) -> SkelElement:
        """Add a SHARED family parameter (``ParamElemExternal``, see
        :func:`new_shared_parameter`): ``guid`` = its identity from OUR
        shared-parameter file, verbatim.  Type-table values key on its
        element id exactly like :meth:`add_family_parameter`'s."""
        pe = new_shared_parameter(_alloc(self.ids), self.self_family.elem_id, name, guid,
                                  spec_type_id=spec_type_id, group_type_id=group_type_id,
                                  kind=kind, description=description)
        return self._register_param(name, pe, default)

    def _register_param(self, name: str, pe: SkelElement, default: Any) -> SkelElement:
        self.params[name] = pe
        self.add(pe)
        # value entry on every type + current-type set
        for _n, vals in self.types:
            vals.setdefault(pe.elem_id, default)
        return pe

    def add_type(self, name: str, params: Optional[Dict[Any, Any]] = None) -> Tuple[str, dict]:
        """Add a TYPE row to the self-Family's ``FamilyTypeTable``.

        ``params`` maps parameter keys to values: an int/str key = a
        parameter id (built-in negative id or a ``ParamElemFamily`` element
        id) or a caption of a parameter added via
        :meth:`add_family_parameter`, or one of the identity-data names
        ('description', 'manufacturer', 'model', 'url', 'type_comments').
        Values: float (internal units, use :func:`mm` / :func:`volts` ...),
        str (text), int (enum / yes-no).
        """
        row: Dict[Any, Any] = {}
        for pe in self.params.values():           # every user param gets a value
            row[pe.elem_id] = 0.0
        for k, v in (params or {}).items():
            row[self._param_key(k)] = v
        self.types.append((str(name), row))
        return self.types[-1]

    def set_type_param(self, type_name: str, key: Any, value: Any) -> None:
        for n, vals in self.types:
            if n == type_name:
                vals[self._param_key(key)] = value
                return
        raise KeyError(f"type {type_name!r} not found")

    def _param_key(self, k: Any) -> int:
        if isinstance(k, int):
            return int(k)
        ks = str(k)
        if ks in self.params:
            return self.params[ks].elem_id
        if ks.lower() in _TYPE_TEXT_PARAMS:
            return _TYPE_TEXT_PARAMS[ks.lower()]
        raise KeyError(f"unknown parameter key {k!r} (add it with add_family_parameter "
                       f"or use a parameter id / identity name)")

    def add_load_classification(self, name: str) -> SkelElement:
        """Add the document's own ``ElectricalLoadClassification`` (a
        family document carries private copies of the load classes its
        connectors reference) -- built by ``rvt.genesis.types.new_load_class``
        (our load-class constructor)."""
        from ..genesis import types as _gt
        rec = _gt.new_load_class(name, ids=self.ids)
        # bridge the types-stream TypeRecord to the SkelElement shape
        el = SkelElement(rec.elem_id, rec.class_name, rec.header, rec.obj,
                         rec.rep, kind="load_class", refs=dict(rec.refs),
                         notes=list(rec.notes))
        # family-document elements point their m_famId at the self-Family;
        # a load-classification registry element keeps the ordinary -1
        # design option (the .rfa's own load classes carry -1) [V .rfa]
        el.obj["m_famId"] = self.self_family.elem_id
        el.header["m_familyId"] = self.self_family.elem_id
        self.load_classes.append(el)
        self.add(el)
        return el

    def has_primary_connector(self) -> bool:
        """True once one of the document's connectors is the primary one."""
        return any(c.obj["m_pDomain"]["value"]["m_bIsConnectorPrimary"]
                   for c in self.connectors)

    def resolve_primary(self, primary: Optional[bool] = None) -> bool:
        """The one-primary-connector law ("a single connector of each
        discipline is allowed to be primary in each family",
        :func:`electrical_domain`): ``None`` = primary iff the document has
        no primary connector yet; asking for a second primary raises."""
        have = self.has_primary_connector()
        if primary is None:
            return not have
        if primary and have:
            raise ValueError("the family already has a primary connector (one primary "
                             "connector per discipline per family)")
        return bool(primary)

    def add_electrical_connector(self, *, host_element_id: Optional[int] = None,
                                 host_geom_tag: int = 0,
                                 location: Optional[Sequence[float]] = None,
                                 direction: Sequence[float] = (0.0, 0.0, -1.0),
                                 voltage: float = 120.0, poles: int = 1,
                                 load_class: str = "Power",
                                 apparent_load_va: Union[float, Sequence[float]] = 0.0,
                                 power_factor: float = 1.0,
                                 bind_voltage_param: Optional[str] = None,
                                 bind_load_param: Optional[str] = None,
                                 description: str = "Power Connection",
                                 primary: Optional[bool] = None) -> SkelElement:
        """Add a POWER connector from the calc-engine values.

        ``host_element_id``/``host_geom_tag`` = the face the connector sits
        on (a solid form's face); when omitted the connector is referenced to
        the Reference Level's datum plane (host = the Ref. Level, tag 0)
        [UNKNOWN whether Revit accepts a datum-plane-hosted connector -- a
        real family always hosts it on a solid face; solid forms are the
        geometry stream's job].  ``load_class`` = the name of the doc's own
        load classification (created on first use).  ``bind_voltage_param``
        / ``bind_load_param`` = captions of family parameters to ASSOCIATE
        with the connector's voltage / apparent-load properties (so the type
        values drive the connector -- the panelboard's rated voltage) [the
        VERIFIED FamilyParametrizedElemParamsCell mechanism].  ``primary``:
        :meth:`resolve_primary` (``None`` = only the first connector is).
        """
        primary = self.resolve_primary(primary)
        host = self.ref_level.elem_id if host_element_id is None else int(host_element_id)
        bindings: List[Tuple[int, int]] = []
        if bind_voltage_param:
            bindings.append((self._param_key(bind_voltage_param), ELEM_PROP_VOLTAGE))
        if bind_load_param:
            bindings.append((self._param_key(bind_load_param), ELEM_PROP_APPARENT_LOAD))
        loc = tuple(location) if location is not None else tuple(self.origin)
        # the document's own load classification (created on demand)
        lc = next((l for l in self.load_classes
                   if l.obj.get("m_name") == load_class or
                   (l.obj.get("m_symbolInfo") or {}).get("value", {}).get("m_name") == load_class),
                  None)
        if lc is None:
            lc = self.add_load_classification(load_class)
        con = new_electrical_connector(
            _alloc(self.ids), self.self_family.elem_id,
            host_element_id=host, host_geom_tag=host_geom_tag,
            location=loc, direction=direction,
            voltage_v=voltage, poles=poles, load_class_id=lc.elem_id,
            apparent_load_va=apparent_load_va, power_factor=power_factor,
            description=description, param_bindings=bindings,
            primary=primary, index=len(self.connectors) + 1)
        self.connectors.append(con)
        self.add(con)
        return con

    # -- finalisation --------------------------------------------------------
    def finalize(self) -> "FamilyDoc":
        """Seed the self-Family from the final element / type / parameter
        state (type table, current-type value set, parameter ordering,
        element index, ownership).  Idempotent; called by the delivery
        methods."""
        # CONSTRAINT BACK-EDGES for every constructor (steer #765 battery
        # find): apply_constraint_back_edges existed but only the files the
        # session dressed BY HAND carried it -- every family built through a
        # constructor still shipped the one-directional constraint graph that
        # failed on the owner's desktop (Alignments naming elements whose
        # m_constrInfo stayed []).  finalize() is the one choke point every
        # delivery passes, so the graph is closed here.  Idempotent, and a
        # document with no constraints is untouched.
        try:
            from . import famdim as _famdim
            _famdim.apply_constraint_back_edges(self)
        except Exception:                                          # noqa: BLE001
            pass          # never block delivery on the repair (hard rule 1)
        fam = self.self_family
        # type table + current-type value set
        if not self.types:
            self.add_type(" ")
        pes = list(self.params.values())
        table = []
        for tname, vals in self.types:
            table.append((tname, self._type_param_entries(vals)))
        fam.obj["m_pFamilyTypes"] = family_type_table(table, current_index=self.current_type)
        cur_vals = self._type_param_entries(self.types[self.current_type][1])
        fam.obj["m_familyParams"] = family_params_block(cur_vals)
        # parameter ordering cell: dimensions first, then identity BIPs used
        dim_ids = [pe.elem_id for pe in pes if pe.refs.get("group") == PGROUP_DIMENSIONS]
        other_groups: Dict[str, List[int]] = {}
        for pe in pes:
            g = pe.refs.get("group")
            if g != PGROUP_DIMENSIONS:
                other_groups.setdefault(g or PGROUP_DIMENSIONS, []).append(pe.elem_id)
        used_bips = sorted({int(k) for _n, vals in self.types for k in vals if int(k) < 0})
        groups: List[Tuple[str, List[int]]] = []
        if dim_ids:
            groups.append((PGROUP_DIMENSIONS, dim_ids))
        for g, gi in other_groups.items():
            groups.append((g, gi))
        if used_bips:
            groups.append((PGROUP_IDENTITY, used_bips))
        fam.obj["m_cellList"] = _ptr("CellList", {"m_cells": [
            family_params_order_cell(groups)]})
        # ONE group per group-type id (issue #333, desktop round 18): the
        # Family Types dialog builds its tree keyed by parameter group, so a
        # group-type id may appear only once -- but user identity params plus
        # the built-in identity BIPs above produced TWO identityData groups,
        # which threw at ADialog::doModal.  normalize_order_cell merges the
        # duplicate key in place and re-ranks (dimensions < identity <
        # electrical); it is content-preserving (asserts the id multiset).
        from . import layout_law as _LL
        _LL.normalize_order_cell(self)
        # locked-for-direct-manipulation = the length parameters (Revit locks
        # dimension params it drives geometry with) [INFERRED default]
        fam.obj["m_lockedParameterIdsForDirectManipulation"] = sorted(
            pe.elem_id for pe in pes if pe.refs.get("spec") == SPEC_LENGTH)
        # element index + ownership over EVERY element (self last)
        others = [e.elem_id for e in self.elements if e.elem_id != fam.elem_id]
        refresh_self_family_index(fam, others)
        self._fit_3d_view()
        self.finalized = True
        return self

    #: 3D-view scale of a Revit-born family document (1:24) -- the project
    #: default 5.0 frames a building, not a component [measured on the
    #: owner's donor + the Autodesk library panelboard].
    VIEW3D_SCALE = 0.041666666666666664

    def _fit_3d_view(self) -> None:
        """FRAME THE 3D VIEW ON THE MODEL (owner report: a small family "I do
        not see it at all", with the sun path filling the frame).

        The project skeleton's 3D camera sits at (-40,-40,20) looking at
        (0,0,5) at scale 5.0 -- 46 ft away, aimed ABOVE a component: a 4 in.
        hanger is an invisible speck and the 150-unit sun path dominates
        what is left.  A Revit-born family instead parks the camera a couple
        of feet off its object at 1:24 [measured].

        The view DIRECTION is Revit's own family isometric [donor 463/461:
        viewDir (0.5773502691896258, -0.5773502691896258, 0.577350269189626)
        with the matching horizontal/vertical rows]; the target, the eye
        distance and the scale are fitted to the model's bounding box.  The
        project skeleton's direction looked DOWN at a building from above --
        the reason the earlier "camera fit" round still framed nothing.
        """
        lo = [float("inf")] * 3
        hi = [float("-inf")] * 3
        for e in self.elements:
            rep = getattr(e, "rep", None)
            bb = rep.get("m_bBox") if isinstance(rep, dict) else None
            if not (isinstance(bb, list) and len(bb) == 2):
                continue
            try:
                for k in range(3):
                    lo[k] = min(lo[k], float(bb[0][k]))
                    hi[k] = max(hi[k], float(bb[1][k]))
            except (TypeError, ValueError, IndexError):       # pragma: no cover
                continue
        if not all(x < float("inf") for x in lo):
            return                                   # no geometry: leave as built
        centre = [(lo[k] + hi[k]) / 2.0 for k in range(3)]
        size = max([hi[k] - lo[k] for k in range(3)] + [0.5])
        dist = size * 3.0                            # the whole body in frame
        vd, hd, vt = FAMILY_VIEW3D_FRAME
        for e in self.elements:
            if e.class_name == "DBView3d":
                eye = [centre[k] + vd[k] * dist for k in range(3)]
                e.obj["m_origin"] = eye
                e.obj["m_scale"] = self.VIEW3D_SCALE
                e.obj["m_viewDir"] = list(vd)
                e.obj["m_horzDir"] = list(hd)
                e.obj["m_vertDir"] = list(vt)
                for sat in self.elements:
                    if sat.class_name == "Viewer3d":
                        sat.obj["m_targetPos"] = list(centre)
                        bs = sat.obj.get("m_boundedSpace")
                        if isinstance(bs, dict):
                            bs["m_orig"] = list(eye)
                            # the viewer basis IS the camera frame; a stale
                            # basis with a new eye is the mismatch that made
                            # "View 1" look at empty space
                            bs["m_basis"] = [list(hd), list(vt),
                                             [-vd[0], -vd[1], -vd[2]]]
                for sat in self.elements:
                    if (sat.class_name == "ExtentElem"
                            and sat.obj.get("m_dbViewId") == e.elem_id):
                        sat.obj["m_dbViewNorm"] = [-vd[0], -vd[1], -vd[2]]
                break

    def _type_param_entries(self, vals: Dict[Any, Any]) -> List[dict]:
        out = []
        for k, v in vals.items():
            pid = self._param_key(k)
            out.append(family_param_value(pid, v))
        # deterministic order: user params (ascending id) then built-ins
        out.sort(key=lambda e: (0, e["m_paramId"]) if e["m_paramId"] > 0
                 else (1, -e["m_paramId"]))
        return out

    # -- records / proof --------------------------------------------------------
    def records(self) -> List[Tuple[int, int, int, dict]]:
        """[(elem_id, seq, class_id, object)] for every element."""
        out = []
        for e in self.elements:
            for seq, cid, obj in e.records():
                out.append((e.elem_id, seq, cid, obj))
        return out

    def roundtrip(self) -> Dict[str, Any]:
        """Encode -> decode -> re-encode every record: the schema-validity +
        byte-stability proof of the constructed document (no specimen)."""
        return _gsk.roundtrip_report(self.elements)

    def globals_models(self, *, username: str = "", out_path: str = "",
                       timestamp: Optional[int] = None) -> Dict[str, Any]:
        """The coordinated Global table-stream models for a ONE-EPISODE
        family document (``rvt.genesis.skeleton.minimal_globals`` -- the
        cross-stream invariants hold by construction)."""
        return minimal_globals(self.elements, username=username, out_path=out_path,
                               timestamp=timestamp,
                               document_guid=self.document_guid or None)

    # -- delivery ------------------------------------------------------------------
    def partition_payloads(self) -> Dict[int, bytes]:
        """Per-seq (101/102/103) record byte strings of THE ONE SAVE UNIT
        (unit 0 = this family document), each closed by its sentinel."""
        return build_unit_segments(self.elements)

    def part_atom(self, *, product_name: str = "rvt-writer",
                  updated: Optional[str] = None) -> bytes:
        """OUR ``PartAtom`` stream (plain Atom XML): title = the family
        name, category from OUR category label, our product name; no
        Autodesk taxonomy URLs.  [UNFRAMED stream; UTF-8]"""
        return build_part_atom(self.name, category_label(self.category_id),
                               type_names=[n for n, _v in self.types],
                               product_name=product_name, updated=updated)

    def to_rfa(self, path: str, *, donor: Optional[str] = None,
               product_name: str = "rvt-writer", username: str = "rvt-writer",
               timestamp: Optional[int] = None) -> Dict[str, Any]:
        """Emit a STANDALONE family file at ``path`` (see :func:`emit_family_rfa`)."""
        if not self.finalized:
            self.finalize()
        return emit_family_rfa(self, path, donor=donor, product_name=product_name,
                               username=username, timestamp=timestamp)

    def to_embedded_unit(self) -> Dict[str, Any]:
        """The EMBEDDED SAVE-UNIT form of this document, for insertion into a
        project's ``Partitions/<N>`` + ``Global/ContentDocuments`` +
        ``Global/PartitionTable`` (the project-side loader's contract --
        see :func:`build_embedded_unit`)."""
        if not self.finalized:
            self.finalize()
        return build_embedded_unit(self)


# ---------------------------------------------------------------------------
# category labels (for PartAtom / diagnostics) -- OUR words, not a taxonomy
# ---------------------------------------------------------------------------

_CATEGORY_LABEL = {
    OST_FURNITURE: "Furniture", OST_GENERIC_MODEL: "Generic Models",
    OST_LIGHTING_FIXTURES: "Lighting Fixtures",
    OST_ELECTRICAL_EQUIPMENT: "Electrical Equipment",
    OST_ELECTRICAL_FIXTURES: "Electrical Fixtures",
}


def category_label(category_id: int) -> str:
    return _CATEGORY_LABEL.get(int(category_id), f"Category {category_id}")


# ---------------------------------------------------------------------------
# new_family_document -- the composed skeleton
# ---------------------------------------------------------------------------

def new_family_document(category, name: str, *, host: str = "none",
                        origin: Sequence[float] = (0.0, 0.0, 0.0),
                        start_id: int = 1000, with_views: bool = True,
                        family_guid: Optional[str] = None,
                        document_guid: Optional[str] = None,
                        part_type: Optional[int] = None,
                        work_plane_based: bool = False,
                        datum_length_ft: float = 30.0,
                        plane_length_ft: float = 10.0,
                        shared_params: SharedParamsArg = None) -> FamilyDoc:
    """Build the FAMILY-DOCUMENT SKELETON: the self-Family, the Reference
    Level + its LevelAttributes, the two origin reference planes, the units
    registry and (``with_views``) the plan-view constellation the reference
    planes are drawn in -- everything constructed FROM SCRATCH.

    ``category`` = an OST id (or 'furniture' / 'generic_model' /
    'lighting_fixture' / 'electrical_equipment' / 'electrical_fixture');
    ``host`` = 'none' | 'wall' | 'ceiling' | 'face' (a hosted family carries a
    host placeholder + host-face geometry ref which this skeleton records in
    the spec only -- ``host != 'none'`` is UNKNOWN territory, see the field
    map §host); ``origin`` = the insertion point (model coords, feet) the
    origin planes intersect at; ``family_guid`` = ONE session GUID every local
    parameter identity shares (default: each takes its deterministic
    :func:`local_param_guid`); ``shared_params`` = OUR shared-parameter file
    (path or parsed rows): every ``add_family_parameter`` caption it names is
    authored SHARED at the file's GUID, the rest local (default: all
    local).  Returns an un-finalised :class:`FamilyDoc`
    ready for ``add_type`` / ``add_family_parameter`` /
    ``add_shared_parameter`` / ``add_reference_plane`` /
    ``add_electrical_connector``.
    """
    cat = _resolve_category(category)
    ids = IdSource(start_id)
    doc_guid = document_guid or str(uuid.uuid4())
    ptype = int(part_type) if part_type is not None else (
        PART_TYPE["panelboard"] if cat == OST_ELECTRICAL_EQUIPMENT and "panel" in name.lower()
        else PART_TYPE["normal"])
    doc = FamilyDoc(category_id=cat, name=str(name), host=str(host),
                    origin=tuple(float(c) for c in origin), ids=ids,
                    family_guid=family_guid, document_guid=doc_guid,
                    shared_params=shared_param_table(shared_params),
                    part_type=ptype, work_plane_based=bool(work_plane_based))
    if host not in ("none", None, ""):
        doc.notes.append(f"host={host!r}: hosted-family scaffolding (host placeholder + "
                         f"host-face geometry ref) is NOT built by the skeleton [UNKNOWN]")
    # -- the self-Family (element index / ownership seeded at finalize) --
    fam = new_self_family(_alloc(ids), cat, name="", element_ids=[],
                          part_type=ptype, work_plane_based=work_plane_based)
    doc.self_family = fam
    doc.add(fam)
    # -- units registry (mandatory registry singleton) --------------------
    units = new_units_elem(_alloc(ids))
    units.obj["m_famId"] = fam.elem_id
    units.header["m_familyId"] = fam.elem_id
    units.kind = "registry"
    _apply_family_units_law(units)
    doc.add(units)
    # -- the level type + reference level ------------------------------
    ltype = new_family_level_type(_alloc(ids), fam.elem_id)
    doc.level_type = ltype
    doc.add(ltype)
    lvl_id = _alloc(ids)
    # -- the plan-view constellation the datums are drawn in ------------
    plan_id = -1
    if with_views:
        try:
            plan_id = _add_view_constellation(doc, lvl_id)
        except Exception as e:                       # pragma: no cover
            doc.notes.append(f"view constellation NOT built ({e}); refplanes carry "
                             f"m_genDbViewId -1 [UNKNOWN]")
            plan_id = -1
    doc.plan_view_id = plan_id
    lvl = new_family_level(lvl_id, fam.elem_id, ltype.elem_id, gen_view_id=plan_id,
                           elevation_ft=float(origin[2]),
                           origin=(float(origin[0]), float(origin[1])),
                           datum_length_ft=datum_length_ft)
    doc.ref_level = lvl
    doc.add(lvl)
    # bind the plan view (if any) to the level id it was pre-allocated for
    # (the constellation was built against lvl_id before the Level existed)
    # -- the two ORIGIN reference planes ---------------------------------
    for rp in new_center_reference_planes(ids, fam.elem_id, gen_view_id=plan_id,
                                          length_ft=plane_length_ft):
        doc.refplanes.append(rp)
        doc.add(rp)
    # -- the required settings singletons (issue #52: desktop Revit
    # demands these of every family document) -----------------------------
    for se in new_required_settings(ids, fam.elem_id):
        doc.add(se)
    # -- the default dimension-style constellation (issue #333: temporary
    # dimensions on selection need a registered default linear style) ------
    dim_style_id, dim_els = new_dimension_style_constellation(ids, fam.elem_id)
    for se in dim_els:
        doc.add(se)
    doc.dim_style_id = dim_style_id
    # -- the object style of our own category: the line style every solid's
    # Geometry node names, i.e. what Revit draws its EDGES with -----------
    _obj_style = new_object_style(ids, fam.elem_id, doc.category_id)
    doc.add(_obj_style)
    doc.object_style_id = _obj_style.elem_id
    # -- the two RETOUCH styles every family view's RetouchTable names ----
    for _cat, _role in RETOUCH_STYLES:
        _st = new_object_style(ids, fam.elem_id, _cat, pen=2, color=8355711,
                               line_pattern=-1)
        doc.add(_st)
        doc.retouch_style_ids[_role] = _st.elem_id
    _bind_retouch_styles(doc)
    # -- the classification-table singletons (issue #333 round 27: the
    # edit path's required-unique-elements check names them) ---------------
    for se in new_classification_tables(ids, fam.elem_id):
        doc.add(se)
    # -- the browser organizations (issue #381: folder headers in the
    # Project Browser) -----------------------------------------------------
    _vo, _so, _org_els = new_browser_organizations(ids, fam.elem_id)
    for se in _org_els:
        doc.add(se)
    doc.types = []
    return doc


def _resolve_category(category) -> int:
    if isinstance(category, int):
        return category
    key = str(category).lower().replace(" ", "_")
    table = {"furniture": OST_FURNITURE, "generic_model": OST_GENERIC_MODEL,
             "generic": OST_GENERIC_MODEL,
             "lighting_fixture": OST_LIGHTING_FIXTURES,
             "lighting_fixtures": OST_LIGHTING_FIXTURES,
             "electrical_equipment": OST_ELECTRICAL_EQUIPMENT,
             "panelboard": OST_ELECTRICAL_EQUIPMENT,
             "transformer": OST_ELECTRICAL_EQUIPMENT,
             "switchboard": OST_ELECTRICAL_EQUIPMENT,
             "electrical_fixture": OST_ELECTRICAL_FIXTURES,
             "electrical_fixtures": OST_ELECTRICAL_FIXTURES,
             # -- the wider category set (owner steer: "a panel goes under
             # electrical equipment and a receptacle goes under electrical
             # fixtures" -- nothing real belongs in Generic Models by
             # default).  The five above are DESKTOP-VERIFIED; the ids below
             # are Revit's published BuiltInCategory constants and are
             # [INFERRED] until a family in each opens in the right branch
             # of Revit's category list (issue #516).  An explicit integer
             # OST id always passes straight through.
             **{k: v for k, v in {
                 "mechanical_equipment": -2001140,
                 "plumbing_fixture": -2001160, "plumbing_fixtures": -2001160,
                 "specialty_equipment": -2001350,
                 "casework": -2000079,
                 "pipe_accessory": -2008055, "pipe_accessories": -2008055,
                 "duct_accessory": -2008016, "duct_accessories": -2008016,
                 "cable_tray": -2008130, "cable_trays": -2008130,
                 "conduit": -2008132, "conduits": -2008132,
                 "cable_tray_fitting": -2008131,
                 "conduit_fitting": -2008133,
                 "lighting_device": -2008080, "lighting_devices": -2008080,
                 "fire_alarm_device": -2008013, "fire_alarm_devices": -2008013,
                 "data_device": -2008083, "data_devices": -2008083,
                 "communication_device": -2008012,
                 "security_device": -2008085,
                 "nurse_call_device": -2008084,
                 "telephone_device": -2008086,
                 "structural_framing": -2001320,
                 "structural_column": -2001330,
                 "door": -2000023, "doors": -2000023,
                 "window": -2000014, "windows": -2000014,
             }.items()}}
    if key not in table:
        raise KeyError(f"unknown family category {category!r}")
    return table[key]


def _bind_retouch_styles(doc: "FamilyDoc") -> None:
    """Point every view's ``RetouchTable`` at the document's retouch styles.

    The views are composed before the styles exist, so this runs after both.
    A view whose table carries -1/-1 has no style to resolve for the
    linework pass [owner: geometry visible in Shaded, no outline in any
    mode, nothing at all in Wireframe]."""
    inv = int(doc.retouch_style_ids.get("invisible", -1))
    nsi = int(doc.retouch_style_ids.get("not_silhouette", -1))
    for e in doc.elements:
        if e.class_name not in _VIEW_CLASSES:
            continue
        rt = e.obj.get("m_pRetouchTable")
        body = rt.get("value") if isinstance(rt, dict) else None
        if isinstance(body, dict):
            _put(body, "m_invisibleGStyleId", inv)
            _put(body, "m_notSilhouetteGStyleId", nsi)


def _add_view_constellation(doc: FamilyDoc, level_id: int) -> int:
    """The plan-view constellation of the family document, reused verbatim
    from the project skeleton (a family view IS the same DBViewPlan /
    Viewer / DBDrawing / Viewport / ExtentElem / SketchPlane constellation):
    the implicit project view, a 'Floor Plan' view type and ONE plan view
    ("Ref. Level") bound to the Reference Level -- the view every reference
    plane's ``m_genDbViewId`` names.

    [INFERRED: family templates carry MORE (a ceiling plan, four elevation
    ``DBViewSection``s, a 3D view); this minimal constellation is the S0
    reduction -- whether the family editor demands the rest is UNKNOWN,
    exactly like the project skeleton's view ladder.]
    """
    ids = doc.ids
    fam_id = doc.self_family.elem_id
    proj = _gsk.new_project_view(ids, phase_id=-1, phase_filter_id=-1,
                                 sun_settings_id=-1)
    vt = _gsk.new_view_type(_alloc(ids), "Floor Plan", "floor_plan")
    plan = _gsk.new_plan_view(ids, "Ref. Level", level_id, 0.0, vt.elem_id,
                              phase_id=-1, phase_filter_id=-1)
    # -- the ceiling plan + the 3D view (issue #381, owner steer: generated
    # families carry the family view set).  Donor law: the ceiling plan is a
    # second "Ref. Level" DBViewPlan with m_planViewType 2 (same +Z view
    # dir); the 3D view is "View 1" (donor 463).  Elevations (DBViewSection)
    # are phase 2 -- no constructor yet.
    vt_c = _gsk.new_view_type(_alloc(ids), "Ceiling Plan", "ceiling_plan")
    cplan = _gsk.new_plan_view(ids, "Ref. Level", level_id, 0.0, vt_c.elem_id,
                               phase_id=-1, phase_filter_id=-1)
    cplan.view.obj["m_planViewType"] = 2
    # the four elevations (steer S-2026-08-10-a: a generated family carries a
    # Revit-born family's view set).  ONE shared "Elevation 1" DBViewType,
    # exactly as the donor does [type 1139 for all four].
    vt_e = _gsk.new_view_type(_alloc(ids), "Elevation 1", "elevation")
    elevs = [new_elevation_view(ids, nm, vt_e.elem_id, vd, hd, vt2, cx, cy)
             for nm, vd, hd, vt2, cx, cy in _FAMILY_ELEVATIONS]
    vt_3 = _gsk.new_view_type(_alloc(ids), "3D View", "3d")
    v3d = _gsk.new_3d_view(ids, "View 1", vt_3.elem_id, ground_level_id=level_id)
    els = (list(proj.elements()) + [vt] + list(plan.elements())
           + [vt_c] + list(cplan.elements()) + [vt_e])
    for ev in elevs:
        els += list(ev.elements())
    els += [vt_3] + list(v3d.elements())
    _apply_family_viewer_law(els, proj.view.elem_id)
    for e in els:
        # family-document elements: object design-option sentinel + famId
        if isinstance(e.obj, dict) and "m_designOptionId" in e.obj:
            e.obj["m_designOptionId"] = FAMILY_DESIGN_OPTION
        if isinstance(e.obj, dict) and e.obj.get("m_famId", -1) == -1 and "m_famId" in e.obj:
            e.obj["m_famId"] = fam_id
        if isinstance(e.header, dict) and e.header.get("m_familyId", -1) == -1:
            e.header["m_familyId"] = fam_id
        doc.views.append(e)
        doc.add(e)
    doc.view_ids["project"] = proj.view.elem_id
    doc.view_ids["view_type_plan"] = vt.elem_id
    doc.view_ids["plan"] = plan.view.elem_id
    doc.view_ids["ceiling"] = cplan.view.elem_id
    doc.view_ids["view_type_elevation"] = vt_e.elem_id
    for nm, ev in zip((r[0] for r in _FAMILY_ELEVATIONS), elevs):
        doc.view_ids[f"elev_{nm.lower()}"] = ev.view.elem_id
    doc.view_ids["view3d"] = v3d.view.elem_id
    return plan.view.elem_id


#: THE FOUR FAMILY ELEVATIONS [measured on the donor's DBViewSection
#: 31/35/39/43 + viewers 30/34/38/42 + sketch planes 1885-1888].  Each row
#: is (name, viewDir, horzDir, vertDir, cutter xVec, cutter yVec).  The
#: cutter frames are stored per elevation rather than derived: Revit's own
#: Back/Front frames do not follow the same rule as Left/Right, and a
#: derived guess is exactly the kind of thing that cost four rounds on the
#: view law above.
_FAMILY_ELEVATIONS = (
    ("Back",  (0.0, 1.0, -0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0),
     (-0.0, -0.0, -1.0), (1.0, -0.0, 0.0)),
    ("Front", (0.0, -1.0, 0.0), (1.0, 0.0, -0.0), (0.0, 0.0, 1.0),
     (0.0, 0.0, 1.0), (1.0, 0.0, -0.0)),
    ("Left",  (-1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, 1.0),
     (0.0, 1.0, 0.0), (0.0, -0.0, 1.0)),
    ("Right", (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0),
     (-0.0, -1.0, -0.0), (0.0, 0.0, 1.0)),
)


def new_elevation_view(ids: IdSource, name: str, view_type_id: int,
                       view_dir: Sequence[float], horz_dir: Sequence[float],
                       vert_dir: Sequence[float],
                       cut_xvec: Sequence[float], cut_yvec: Sequence[float]):
    """One of a family document's four elevations: ``DBViewSection`` +
    ``Viewer`` + fixed ``SketchPlane`` + ``DBDrawing``/``Viewport`` +
    ``ExtentElem`` [membership measured on donor 31/30/1885/32/33/435].

    A family elevation is a section view (``m_sectionViewType`` 1) whose
    cut plane passes through the family origin, with no sun settings, no
    light scheme and no crop -- the family-view law's shape, authored here
    rather than stamped on afterwards.
    """
    view_id = _alloc(ids)
    viewer_id = _alloc(ids)
    sketch_id = _alloc(ids)
    viewport_id = _alloc(ids)
    drawing_id = _alloc(ids)
    extent_id = _alloc(ids)
    obj = _gsk.dbview_base(
        view_id, name, viewer_id=viewer_id, drawing_id=drawing_id,
        sun_settings_id=-1, view_type_id=view_type_id,
        extent_elem_id=extent_id, fixed_sketch_plane_id=sketch_id,
        origin=(0.0, 0.0, 0.0), view_dir=view_dir, horz_dir=horz_dir,
        vert_dir=vert_dir, scale=FAMILY_VIEW_SCALE, back_clipping=-1,
        excluded_categories=(), cell_list=False)
    obj["m_geomSteps"] = _ptr("GeomStepList", {
        "m_nonBRepGList": [_ptr("MakeCutterForSectionGStep", {
            "m_faceHistTable": [], "m_curveHistTableSet": [],
            "m_edgeHistTable": [], "m_edgeHistTableReverse": [],
            "m_id": 1, "m_version": 0, "m_flags": 7997,
            "m_pElem": _weak(2), "m_oExtraDatas": None})],
        "m_bRepFormGList": [], "m_bRepAdjustGList": [],
        "m_bRepCutOutGList": [], "m_bRepPostCutOutGList": [],
        "m_bRepTweakGList": [],
        "m_bRepFormSnapshot": None, "m_bRepAdjustSnapshot": None,
        "m_bRepCutOutSnapshot": None, "m_bRepPostCutOutSnapshot": None,
        "m_pElem": _weak(2),
        "m_latestGStepTypeInPrevRegenCycle": [1, 1, 1, 1, 1],
        "m_idCounter": 2, "m_flags": 9})
    obj["m_pCutter"] = _ptr("GenericPlaneCutter", {
        "m_pPlane": plane((0.0, 0.0, 0.0), cut_xvec, cut_yvec,
                          EMPTY_ENVELOPE, pid=3),
        "m_bAssignCutFaceTag": True, "m_bBackPlaneCut": False})
    obj["m_sectionViewType"] = 1
    dele = [view_id, viewer_id, sketch_id, drawing_id, extent_id] + (
        [view_type_id] if view_type_id >= 0 else [])
    hdr = element_header("DBViewSection", category=OST_VIEWS, deletion=dele,
                         appearance=[view_type_id] if view_type_id >= 0 else [],
                         flags=10, visible_view_flags=-32608)
    view = SkelElement(view_id, "DBViewSection", hdr, obj, None, kind="view")
    viewer = _gsk.new_viewer(
        viewer_id, view_id, orig=(0.0, 0.0, 0.0), with_gstep=True,
        appearance=[view_type_id] if view_type_id >= 0 else [],
        regen_only=[view_type_id] if view_type_id >= 0 else [], flags=10)
    vb = viewer.obj.get("m_boundedSpace")
    if isinstance(vb, dict):
        vb["m_basis"] = [list(horz_dir), list(vert_dir),
                         [-view_dir[0], -view_dir[1], -view_dir[2]]]
    sketch = _gsk.new_sketch_plane(sketch_id, view_id, datum_id=view_id,
                                   elevation_ft=0.0)
    trf = sketch.obj.get("m_oTrf")
    if isinstance(trf, dict) and isinstance(trf.get("value"), dict):
        # columns = (horz, vert, viewDir) [donor 1885-1888]
        trf["value"]["m_3x3"] = [[horz_dir[i], vert_dir[i], view_dir[i]]
                                 for i in range(3)]
    viewport = _gsk.new_viewport(viewport_id, view_id, drawing_id, flags=10)
    drawing = _gsk.new_dbdrawing(drawing_id, [viewport_id], view_id, flags=8202)
    extent = _gsk.new_extent_elem(extent_id, view_id, (0.0, 0.0, 0.0))
    return _gsk.ViewSpec(view, [viewer, sketch, viewport, drawing, extent])


_FAMILY_VIEW_EXCL_ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                       "assets",
                                       "family_view_excluded_categories.json")


def _apply_family_view_exclusions(els) -> None:
    """THE FAMILY-VIEW EXCLUSION LAW (owner report: "i cant see this at all
    unless i open a new 3d view").

    A view's draw filters carry an EXCLUDED-CATEGORY set.  The project
    skeleton's 3D set excludes the model categories a coordination view
    hides -- Electrical Equipment (-2001040), Electrical Fixtures
    (-2001060), Lighting Fixtures (-2001120), Mechanical, Plumbing,
    Structural ... which are exactly the categories a generated FAMILY
    lives in, so its own geometry was filtered out of its own views while a
    freshly created {3D} view (no exclusions) showed it fine.

    A Revit-born family excludes ANNOTATION categories only [measured on
    the owner's donor: 42 entries in the 3D view, 41 in the plan, none of
    them a model category a component would use].  That measured set is
    shipped as an asset and applied to every family view.
    """
    with open(_FAMILY_VIEW_EXCL_ASSET, "r", encoding="utf-8") as fh:
        law = json.load(fh)
    for e in els:
        if e.class_name == "DBView3d":
            key = "3d"
        elif e.class_name == "DBViewProject":
            key = "project"
        elif e.class_name == "DBViewSection":
            key = "section"
        elif e.class_name == "DBViewPlan":
            key = "ceiling" if int(e.obj.get("m_planViewType") or 1) == 2 else "plan"
        else:
            continue
        wanted = [int(x) for x in law.get(key) or law.get("plan", [])]
        for df in (e.obj.get("m_oaDrawFilters") or []):
            body = (df.get("value") or {}) if isinstance(df, dict) else {}
            if isinstance(body.get("m_categoryIds"), list):
                body["m_categoryIds"] = list(wanted)
                # a family view excludes CATEGORIES, never a whole class of
                # content [every donor family view: all four flags False].
                for flag in ("m_annotationsExcluded", "m_modelsExcluded",
                             "m_analyticalModelsExcluded", "m_importsExcluded"):
                    _put(body, flag, False)


#: THE FAMILY 3D CAMERA FRAME (viewDir, horzDir, vertDir) -- the isometric
#: Revit itself gives a family's "View 1" [donor 463/461].  The project
#: skeleton's frame looks down on a building from above.
FAMILY_VIEW3D_FRAME = (
    (0.5773502691896258, -0.5773502691896258, 0.577350269189626),
    (0.7071067811865476, 0.7071067811865476, 0.0),
    (-0.40824829046386313, 0.40824829046386313, 0.816496580927726),
)

#: THE FAMILY-VIEW SCALE.  Every view of a Revit-born family document --
#: the implicit project view, the Ref. Level plan, the ceiling plan, the four
#: elevations and "View 1" -- carries 1:24 [measured: donor views 50/23/27/
#: 31/35/39/43/463 all 0.041666666666666664].  The project skeleton's 1:100
#: is a building scale: it renders a 1'-8" panel's dimension text at nine
#: inches tall, which is what buried the model in the owner's screenshots.
FAMILY_VIEW_SCALE = 0.041666666666666664

#: PLAN-VIEW RANGE per ``m_planViewType`` [measured on donor 23 (plan) and 27
#: (ceiling)].  Offsets are relative to the Reference Level; ``None`` in
#: ``pvr2_levels`` means "this view's level id", every other entry is the
#: literal sentinel Revit stores.  The project skeleton instead derives the
#: range from the storey height, which on a family's single level produced a
#: cut plane ABOVE the top clip and a view-depth cutter under the level.
_FAMILY_PLAN_RANGE = {
    1: {"cut": 4.0, "top": 7.5, "bottom": 0.0, "level_below": -999999999.9999999,
        "underlay": 0, "offsets": [4.0, 7.5, 0.0, 0.0, 0.0],
        "level_pos": [0, 0, 0, -1, 0], "pvr2_levels": [None, None, None, -4, -1],
        "cut_yvec": [0.0, -1.0, 0.0]},
    2: {"cut": 7.5, "top": 999999999.9999999, "bottom": 0.0,
        "level_below": 999999999.9999999,
        "underlay": 1, "offsets": [7.5, 0.0, 0.0, 0.0, 0.0],
        "level_pos": [0, 1, 0, 1, 0], "pvr2_levels": [None, -2, None, -2, -1],
        "cut_yvec": [0.0, 1.0, 0.0]},
}

#: ``m_oaDrawFilters`` composition per view class [measured].  A family
#: document has no phases and no design options, so a Revit-born famdoc view
#: carries NEITHER ``PhasingDrawFilter`` NOR ``DesignOptionDrawFilter`` -- it
#: keeps a bare ``None`` in the slot where the project view has them.  Ours
#: shipped both, and both filter on state a famdoc cannot satisfy.
_FAMILY_DRAW_FILTERS = {
    "DBViewProject": ("IckyExcludedCategoriesSetPtrWrapper",
                      "PartitionVisibilityDrawFilter",
                      "RvtLinkDrawFilter", "HideElementsDrawFilter"),
    "DBViewPlan": ("IckyExcludedCategoriesSetPtrWrapper", None,
                   "PartitionVisibilityDrawFilter",
                   "RvtLinkDrawFilter", "HideElementsDrawFilter"),
    "DBViewSection": ("IckyExcludedCategoriesSetPtrWrapper", None,
                      "PartitionVisibilityDrawFilter",
                      "RvtLinkDrawFilter", "HideElementsDrawFilter"),
    "DBView3d": ("IckyExcludedCategoriesSetPtrWrapper",
                 "PartitionVisibilityDrawFilter", None,
                 "RvtLinkDrawFilter", "HideElementsDrawFilter"),
}

#: ``m_pViewDisplayMgr.m_lights`` of a family view: NO sun-and-shadow
#: settings element (owner: "what is up with the sun path???" -- the project
#: skeleton points every view at a SunAndShadowSettings, so Revit draws the
#: 150-unit sun path around a 4-inch component).
_FAMILY_VIEW_LIGHTS = {"m_sunAndShadowSettingsId": -1,
                       "m_ambientLightIntensity": 30,
                       "m_shadowIntensity": 50,
                       "m_sunlightIntensity": 0}

#: The rest of ``m_pViewDisplayMgr`` a family view carries.  Found by
#: ``tools/famdiff.py``, not by eye: every hand-written diff in this campaign
#: put the display manager in its SKIP set because the subtree is long and
#: "obviously stock", and it was wrong in four places the whole time.  Both
#: reference files agree on all four, which is what makes them law -- the
#: same run shows ``m_annotationsExcluded`` DISAGREEING between the two
#: references, so that one is an author's choice and is left alone.
_FAMILY_VIEW_DISPLAY = {
    "m_exposure": {"m_crushBlacks": 0.2, "m_exposureDouble": 14.0},
    "m_shadows": {"m_ambientShadows": False},
}
#: ``m_oStaticRRTRenderSettings.m_BkIamgeSettings.m_FitType`` (Autodesk's
#: spelling, not ours) -- 0 in both references, 43 in ours.
_FAMILY_VIEW_BK_FIT_TYPE = 0

#: ``VIEW_DETAIL_LEVEL`` (-1011002): 1 = Coarse on the plans, 2 = Medium on
#: the 3D view [measured].  Our 3D view shipped an EMPTY int param set, i.e.
#: no detail level at all.
_PARAM_VIEW_DETAIL_LEVEL = -1011002
#: ``m_pParamValueSetInt`` entry the project skeleton adds and a famdoc view
#: does not carry (a project-only display flag).
_PARAM_PROJECT_ONLY_INT = -1005163

_VIEW_CLASSES = ("DBViewProject", "DBViewPlan", "DBView3d", "DBViewSection")


def _put(obj, key, value) -> None:
    """Assign ONLY when the active release's schema defines the field --
    writing a 2026-only field into a 2024/2025 object breaks the ADocument
    round-trip (the regression this rule was written for)."""
    if isinstance(obj, dict) and key in obj:
        obj[key] = value


def _wrap(ptr_class: str, value: dict) -> dict:
    return {"ptr_class": ptr_class, "pid": -1, "value": value}


def _pattern_cell_list() -> Optional[dict]:
    return _wrap("CellList", {"m_cells": [
        _wrap("PatternHelper", {"m_PatternPositionMap": [],
                                "m_substituteFaceMap": []})]})


def _clone_gstep(step: dict, ptr_class: str, sid: int, flags: int) -> dict:
    """A GStep of another class with the same body shape [every GStep carries
    the identical ``m_faceHistTable``/``m_curveHistTableSet``/``m_edgeHist*``/
    ``m_id``/``m_version``/``m_flags``/``m_pElem``/``m_oExtraDatas`` set]."""
    out = copy.deepcopy(step)
    out["ptr_class"] = ptr_class
    body = out.get("value")
    if isinstance(body, dict):
        body["m_id"] = sid
        body["m_flags"] = flags
    return out


def _apply_family_draw_filters(e) -> None:
    """Re-compose ``m_oaDrawFilters`` to the family shape for this class."""
    order = _FAMILY_DRAW_FILTERS.get(e.class_name)
    have = e.obj.get("m_oaDrawFilters")
    if order is None or not isinstance(have, list):
        return
    by_class = {f.get("ptr_class"): f for f in have if isinstance(f, dict)}
    out = []
    for want in order:
        if want is None:
            out.append(None)
        elif want in by_class:
            out.append(by_class[want])
    e.obj["m_oaDrawFilters"] = out


def _plan_level_id(o: dict) -> int:
    """The Reference Level a plan view is bound to: ``m_genElemId`` [the
    field the donor carries the level in], falling back to whatever the
    already-built PlanViewRange2 names."""
    lid = int(o.get("m_genElemId", -1) or -1)
    if lid > 0:
        return lid
    pvr2 = o.get("m_pPlanViewRange2")
    ids = (pvr2 or {}).get("value", {}).get("m_viewDepthPlaneLevelIds") \
        if isinstance(pvr2, dict) else None
    if isinstance(ids, list) and ids and int(ids[0]) > 0:
        return int(ids[0])
    return int(o.get("m_assocLevelId", -1) or -1)


def _apply_family_plan_range(e, level_id: int) -> None:
    """Cut plane / top / bottom / view depth of a family plan view."""
    law = _FAMILY_PLAN_RANGE.get(int(e.obj.get("m_planViewType") or 1))
    if law is None:
        return
    o = e.obj
    _put(o, "m_origin", [0.0, 0.0, 0.0])
    _put(o, "m_backClipping", -1)
    _put(o, "m_cutPlaneElev", law["cut"])
    _put(o, "m_topClipElev", law["top"])
    _put(o, "m_bottomClipElev", law["bottom"])
    _put(o, "m_levelBelowElev", law["level_below"])
    _put(o, "m_columnSymbolElev", 0.0)
    _put(o, "m_underlayOrientation", law["underlay"])
    pvr = o.get("m_pPlanViewRange")
    if isinstance(pvr, dict) and isinstance(pvr.get("value"), dict):
        _put(pvr["value"], "m_offsets", list(law["offsets"]))
        _put(pvr["value"], "m_levelPos", list(law["level_pos"]))
    pvr2 = o.get("m_pPlanViewRange2")
    if isinstance(pvr2, dict) and isinstance(pvr2.get("value"), dict):
        _put(pvr2["value"], "m_viewDepthPlaneOffsets", list(law["offsets"]))
        _put(pvr2["value"], "m_viewDepthPlaneLevelIds",
             [level_id if s is None else s for s in law["pvr2_levels"]])
    cutter = o.get("m_pCutter")
    plane = (cutter or {}).get("value", {}).get("m_pPlane") if isinstance(cutter, dict) else None
    if isinstance(plane, dict) and isinstance(plane.get("value"), dict):
        _put(plane["value"], "m_origin", [0.0, 0.0, law["cut"]])
        _put(plane["value"], "m_yVec", list(law["cut_yvec"]))
    # a family plan view has NO separate view-depth cutter element; the depth
    # plane is expressed by the second GStep instead [donor 23/27].
    _put(o, "m_pViewDepthCutter", None)
    steps = o.get("m_geomSteps")
    body = steps.get("value") if isinstance(steps, dict) else None
    lst = body.get("m_nonBRepGList") if isinstance(body, dict) else None
    if isinstance(lst, list) and len(lst) == 1 and isinstance(lst[0], dict):
        first = lst[0]
        if isinstance(first.get("value"), dict):
            first["value"]["m_flags"] = 317
        lst.append(_clone_gstep(first,
                                "MakeViewDepthCutterForPlanRegionsGStep", 2,
                                40765))
        _put(body, "m_idCounter", 3)
        _put(body, "m_flags", 9)


def _apply_family_viewer_law(els, project_view_id: int) -> None:
    """THE FAMILY-VIEW LAW -- the whole view constellation of a family
    document, measured field by field against the owner's Revit-2026-born
    donor (views 50/23/27/463, viewers 49/22/26/461) rather than patched one
    guess at a time.

    Four rounds of single-field fixes (camera fit, 3D crop box, category
    exclusions, the family draw-order manager) each left the owner's report
    unchanged -- "i dont see the element whats so ever" -- and the control
    (a panelboard, not the new multi-part path) failed the same way, which
    exonerated the geometry and convicted the views.  The full diff then
    showed our views were still *project* views in five ways a family
    document cannot satisfy:

    * ``PhasingDrawFilter`` + ``DesignOptionDrawFilter`` in ``m_oaDrawFilters``
      -- a famdoc has no phases and no design options, so both filters test
      state that is never satisfied and drop the model from the draw pass.
      A Revit-born famdoc view carries neither (a bare ``None`` sits in the
      slot); a freshly created ``{3D}`` view has none either, which is
      exactly why THAT view showed the geometry.
    * ``m_scale`` 1:100 instead of 1:24 -- the giant dimension text.
    * ``m_pViewDisplayMgr.m_lights`` pointing at a SunAndShadowSettings --
      the sun path the owner asked about.
    * ``DrawOrderMgr`` instead of ``DrawOrderMgr3dFamily`` on EVERY view (we
      had only converted the 3D one).
    * a plan view range derived from a storey height: cut plane above the
      top clip, plus a view-depth cutter a famdoc does not carry.

    The Viewer3d additionally shipped a PERSPECTIVE projection
    (``m_projMethodType`` 2, ``m_viewerFlags`` 7); a family's "View 1" is
    orthographic, which is also why the donor parks its eye ~1.7 ft off the
    target and still frames the whole body.

    Kept from the earlier rounds (all still donor-measured): the bound-box
    law below, the annotation-only category exclusions, and the fitted 3D
    camera.
    """
    _apply_family_view_exclusions(els)
    ceiling_view_ids = {e.obj.get("m_id") for e in els
                        if e.class_name == "DBViewPlan"
                        and int(e.obj.get("m_planViewType") or 1) == 2}
    for e in els:
        if e.class_name in _VIEW_CLASSES:
            o = e.obj
            _put(o, "m_scale", FAMILY_VIEW_SCALE)
            _put(o, "m_cellList", None)
            # the phase / phase-filter param pair is project state
            _put(o, "m_pParamValueSetElementId", None)
            _put(o, "m_lightSchemeId", -1)
            dom = o.get("m_pDetailDrawOrderMgr")
            if isinstance(dom, dict) and dom.get("ptr_class") != "DrawOrderMgr3dFamily":
                from ..genesis.types import blank_object as _blank
                try:
                    old = dom.get("value") if isinstance(dom.get("value"), dict) else {}
                    new = _blank("DrawOrderMgr3dFamily")
                    # keep the doc / view back-pointers the project manager
                    # already carried [donor: weakrefs 1 and 2]
                    for ref in ("m_pADoc", "m_pDBView"):
                        if ref in old and ref in new:
                            new[ref] = old[ref]
                    dom["ptr_class"] = "DrawOrderMgr3dFamily"
                    dom["value"] = new
                except Exception:                      # pragma: no cover
                    pass
            vdm = o.get("m_pViewDisplayMgr")
            vdmv = vdm.get("value") if isinstance(vdm, dict) else None
            if isinstance(vdmv, dict):
                lights = vdmv.get("m_lights")
                if isinstance(lights, dict):
                    for k, v in _FAMILY_VIEW_LIGHTS.items():
                        _put(lights, k, v)
                model = vdmv.get("m_model")
                if isinstance(model, dict) and e.class_name != "DBView3d":
                    _put(model, "m_surfaces", 1)
                for grp, wanted in _FAMILY_VIEW_DISPLAY.items():
                    sub = vdmv.get(grp)
                    if isinstance(sub, dict):
                        for k, val in wanted.items():
                            _put(sub, k, val)
                rrt = vdmv.get("m_oStaticRRTRenderSettings")
                rrtv = rrt.get("value") if isinstance(rrt, dict) else None
                bk = rrtv.get("m_BkIamgeSettings") if isinstance(rrtv, dict) else None
                if isinstance(bk, dict):
                    _put(bk, "m_FitType", _FAMILY_VIEW_BK_FIT_TYPE)
            _apply_family_draw_filters(e)
            ints = o.get("m_pParamValueSetInt")
            iv = ints.get("value") if isinstance(ints, dict) else None
            if isinstance(iv, dict) and isinstance(iv.get("m_paramSet"), list):
                iv["m_paramSet"] = [
                    p for p in iv["m_paramSet"]
                    if p.get("m_paramId") != _PARAM_PROJECT_ONLY_INT]
                # the implicit project view carries no detail level at all
                want = ({"DBView3d": 2}.get(e.class_name, 1)
                        if e.class_name != "DBViewProject" else None)
                if want is None:
                    iv["m_paramSet"] = [
                        p for p in iv["m_paramSet"]
                        if p.get("m_paramId") != _PARAM_VIEW_DETAIL_LEVEL]
                else:
                    for p in iv["m_paramSet"]:
                        if p.get("m_paramId") == _PARAM_VIEW_DETAIL_LEVEL:
                            p["m_value"] = want
                            break
                    else:
                        iv["m_paramSet"].append(
                            {"m_paramId": _PARAM_VIEW_DETAIL_LEVEL,
                             "m_value": want})
            if e.class_name == "DBViewPlan":
                if o.get("m_pParamValueSetDouble") is None:
                    _put(o, "m_pParamValueSetDouble",
                         _wrap("ParamValueSetDouble", {"m_paramSet": []}))
                _apply_family_plan_range(e, _plan_level_id(o))
            continue
        if e.class_name == "Viewer3d":
            # THE 3D CROP LAW (owner report: "i see nothing in revit" -- an
            # EMPTY 3D view with a white rectangle in it).  The project
            # skeleton's Viewer3d ships a 0.05 x 0.03 ft crop box with
            # cropping ACTIVE on x and y: about half an inch, so every
            # family's geometry is clipped away and only the crop boundary
            # draws.  A Revit-born family carries +-100 ft with every bound
            # INACTIVE [measured on the donor 461 and the Autodesk library
            # panelboard 1134560].
            o = e.obj
            bs = o.get("m_boundedSpace")
            if isinstance(bs, dict):
                bs["m_boundOffset"] = [[100.0, -100.0], [100.0, -100.0],
                                       [1000.0, 0.1]]
                bs["m_boundActive"] = [[False, False]] * 3
                bs["m_isOn"] = True
            # ORTHOGRAPHIC, exactly like Revit's own family "View 1"
            _put(o, "m_projMethodType", 1)
            _put(o, "m_viewerFlags", 0)
            _put(o, "m_intentionallyPlaced", False)
            _put(o, "m_pParamValueSetElementId", None)
            if o.get("m_cellList") is None:
                _put(o, "m_cellList", _pattern_cell_list())
            if o.get("m_geomSteps") is None:
                _put(o, "m_geomSteps", _viewer3d_geom_steps(els))
            continue
        if e.class_name != "Viewer":
            continue
        o = e.obj
        bs = o.get("m_boundedSpace")
        if isinstance(bs, dict):
            bo = bs.get("m_boundOffset")
            if isinstance(bo, list) and len(bo) >= 3:
                bo[2] = [100.0, 0.0]
            if o.get("m_dbViewId") != project_view_id:
                bs["m_boundActive"] = [[False, False]] * 3
                bs["m_isOn"] = True
        if o.get("m_dbViewId") != project_view_id:
            o["m_projMethodType"] = 1
            o["m_viewerFlags"] = 0
            o["m_intentionallyPlaced"] = False
            # a plan/ceiling viewer spins about +Z, not +Y [donor 22/26]
            _put(o, "m_axisDir", [0.0, 0.0, 1.0])
            if o.get("m_dbViewId") in ceiling_view_ids:
                _put(o, "m_bReflected", True)
        else:
            _put(o, "m_cellList", None)


def _viewer3d_geom_steps(els) -> Optional[dict]:
    """The Viewer3d's own two-step geometry list [donor 461]: a
    ``MakeCutterForViewer3d`` (flags 7997) followed by a ``ViewerGStep``
    (flags 761725).  Built by re-tagging a plan view's GStep, whose body
    shape is identical, so nothing is copied out of a donor file."""
    template = None
    for e in els:
        steps = e.obj.get("m_geomSteps") if isinstance(e.obj, dict) else None
        body = steps.get("value") if isinstance(steps, dict) else None
        lst = body.get("m_nonBRepGList") if isinstance(body, dict) else None
        if isinstance(lst, list) and lst and isinstance(lst[0], dict):
            template = (steps, lst[0])
            break
    if template is None:                                  # pragma: no cover
        return None
    steps, step = template
    out = copy.deepcopy(steps)
    body = out["value"]
    body["m_nonBRepGList"] = [
        _clone_gstep(step, "MakeCutterForViewer3d", 1, 7997),
        _clone_gstep(step, "ViewerGStep", 2, 761725),
    ]
    body["m_idCounter"] = 3
    body["m_flags"] = 9
    _put(body, "m_latestGStepTypeInPrevRegenCycle", [1, 1, 1, 1, 1])
    return out


# ---------------------------------------------------------------------------
# PARTITION-STREAM ASSEMBLY (the save unit of a family document)
# ---------------------------------------------------------------------------

#: Partitions stream header: u64 9 + u16 0x3a3 + i32 0 + u32 elem_table_count
_PART_TAG = 0x3A3
BLOCK_TAG = 0x0F28
TRAILER_TAG = 0x0F21
FOOTER_TAG = 0x0F3F
DATA_GENERATED_STRING = "Data generated by Autodesk® Revit®"


def build_unit_segments(elements: Sequence[SkelElement]) -> Dict[int, bytes]:
    """Encode every element into the three per-seq record byte strings of a
    save unit, each closed by its sentinel (id -1, psize 0; stamp 1 for
    seq 102/103) [VERIFIED framing: identical id sets across the three seqs,
    sentinel last]."""
    from ..encode import ObjectEncoder, record_stamp, encode_record as _er
    from ..objects import ObjectDecoder
    dec = _gsk._SCHEMA_CACHE.get("dec")
    if dec is None:
        dec = _gsk._SCHEMA_CACHE["dec"] = ObjectDecoder()
    enc = _gsk._SCHEMA_CACHE.get("enc")
    if enc is None:
        enc = _gsk._SCHEMA_CACHE["enc"] = ObjectEncoder(decoder=dec)
    segs: Dict[int, bytearray] = {101: bytearray(), 102: bytearray(), 103: bytearray()}
    for e in sorted(elements, key=lambda x: x.elem_id):
        for seq, cid, obj in e.records(class_ids=enc.class_id_of):
            if seq == 101:
                segs[seq] += enc.encode_record(seq, e.elem_id, 0, cid, obj)
            else:
                body = enc.encode_object(cid, obj or {})
                st = record_stamp(cid, body)
                ps = 2 + len(body)
                segs[seq] += (struct.pack("<qII", e.elem_id, st, ps)
                              + struct.pack("<H", cid) + body
                              + struct.pack("<I", ps))
    # sentinels (last record of each seq)
    segs[101] += struct.pack("<qI", -1, 0) + struct.pack("<I", 0)
    for s in (102, 103):
        segs[s] += struct.pack("<qII", -1, 1, 0) + struct.pack("<I", 0)
    return {k: bytes(v) for k, v in segs.items()}


def build_partition_stream(segments: Dict[int, bytes], *, elem_table_count: int,
                           footer_blob: bytes = b"",
                           end_record: Optional[bytes] = None,
                           block_size: int = 128 * 1024,
                           gzip_level: int = 3) -> bytes:
    """Assemble the LOGICAL ``Partitions/<N>`` stream of a single-unit
    document: 18-byte stream header + one run of blocks per seq (whole
    records only, ~128 KiB payloads) + the unit terminator/footer + the end
    record [VERIFIED framing: block header {u16 0x0f28, u32 flags, u32 A
    records, u32 B = 8 + gzip len (mirrored in the 0x0f21 trailer), u32 C
    body bytes, u32 seq, u32 0}; ISIZE == hdr_len(seq)*A + C for whole-record
    (flags 4) blocks; unit terminator = 0x0f28 + 16 zero + 0x0f3f blob +
    'Data generated...' UTF-16; end record 0x3a3 -1 ...].

    ``footer_blob`` = the 64-byte opaque unit blob (empty => a 0-length blob
    as the tiny dach partition carries); ``end_record`` = the opaque stream
    end record (default: the minimal ``a3 03 00 00 00 00 ff ff ff ff 00 00 00
    00`` form).  Both are OPAQUE format bytes [UNKNOWN semantics; V15/V20
    proved the reader accepts foreign / re-blocked content beside them].
    """
    from ..writer import gzip_member
    hdr_len = {101: 16, 102: 20, 103: 20}
    out = bytearray()
    out += struct.pack("<QHiI", 9, _PART_TAG, 0, int(elem_table_count))
    for seq in (101, 102, 103):
        seg = segments.get(seq, b"")
        # split into whole-record blocks of <= block_size payload
        recs = _split_records(seg, seq)
        blocks: List[bytes] = []
        cur = bytearray()
        for rb in recs:
            if cur and len(cur) + len(rb) > block_size:
                blocks.append(bytes(cur))
                cur = bytearray()
            cur += rb
        blocks.append(bytes(cur))
        for pay in blocks:
            n_recs = sum(1 for _ in _iter_record_lengths(pay, seq))
            A = n_recs
            C = len(pay) - hdr_len[seq] * A          # body bytes (whole records)
            gz = gzip_member(pay, level=gzip_level, sync_flush=True)
            B = 8 + len(gz)
            out += struct.pack("<HIIIIII", BLOCK_TAG, 4, A, B, C, seq, 0)
            out += gz
            out += struct.pack("<HI", TRAILER_TAG, B)
    # unit terminator + footer
    out += struct.pack("<H", BLOCK_TAG) + b"\x00" * 16
    out += struct.pack("<HI", FOOTER_TAG, len(footer_blob)) + bytes(footer_blob)
    txt = DATA_GENERATED_STRING.encode("utf-16-le")
    out += struct.pack("<I", len(DATA_GENERATED_STRING)) + txt
    if end_record is None:
        end_record = struct.pack("<HiiI", _PART_TAG, 0, -1, 0)
    out += bytes(end_record)
    return bytes(out)


def _split_records(seg: bytes, seq: int) -> List[bytes]:
    """Split a per-seq segment into whole record byte strings (framing:
    seq 101 {i64 id, u32 psize} + psize + u32 repeat; seq 102/103 {i64 id,
    u32 stamp, u32 psize} + psize + u32 repeat)."""
    hl = 12 if seq == 101 else 16
    out, p, n = [], 0, len(seg)
    while p + hl <= n:
        if seq == 101:
            size = struct.unpack_from("<qI", seg, p)[1]
        else:
            size = struct.unpack_from("<qII", seg, p)[2]
        end = p + hl + size + 4
        out.append(seg[p:end])
        p = end
    if p != n:                                        # pragma: no cover
        raise ValueError(f"seq {seq}: trailing {n - p} bytes are not a whole record")
    return out


def _iter_record_lengths(payload: bytes, seq: int):
    return _split_records(payload, seq)


# ---------------------------------------------------------------------------
# PartAtom (the .rfa's Atom-XML manifest) -- OURS
# ---------------------------------------------------------------------------

PARTATOM_NS = "urn:schemas-autodesk-com:partatom"
ATOM_NS = "http://www.w3.org/2005/Atom"


def _xml_escape(text: str) -> str:
    """Byte-identical to ``xml.sax.saxutils.escape`` (``&`` first) without its
    ``urllib.request``/``http.client``/``ssl`` import chain (#139)."""
    return text.replace("&", "&amp;").replace(">", "&gt;").replace("<", "&lt;")


def build_part_atom(title: str, category_label_txt: str, *,
                    type_names: Sequence[str] = (), product_name: str = "rvt-writer",
                    updated: Optional[str] = None) -> bytes:
    """The ``PartAtom`` stream: plain Atom XML in the partatom namespace
    (title, category, updated stamp, the product/design-file entry and the
    type list).  The XML VOCABULARY is format (interoperability); the VALUES
    are ours -- no Autodesk taxonomy URLs, no OmniClass, no Autodesk product
    label [D content policy].  UNFRAMED stream (like BasicFileInfo).
    """
    _x = _xml_escape
    ts = updated or time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    types_xml = "".join(
        f"<A:type><A:title>{_x(str(n))}</A:title></A:type>" for n in type_names)
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<entry xmlns="{ATOM_NS}" xmlns:A="{PARTATOM_NS}">'
        f'<title>{_x(str(title))}</title>'
        f'<id>{_x(str(title))}</id>'
        f'<updated>{ts}</updated>'
        f'<A:taxonomy><term>{_x(product_name)}:family</term>'
        f'<label>{_x(product_name)} Family</label></A:taxonomy>'
        f'<category><term>{_x(category_label_txt)}</term>'
        f'<label>{_x(category_label_txt)}</label></category>'
        '<link rel="design-2d" type="application/rfa" href=".">'
        '<A:design-file>'
        f'<A:title>{_x(str(title))}.rfa</A:title>'
        f'<A:product>{_x(product_name)}</A:product>'
        f'<A:updated>{ts}</A:updated>'
        '</A:design-file></link>'
        f'<A:features><A:feature><A:title>{_x(str(title))}</A:title>'
        f'{types_xml}</A:feature></A:features>'
        '</entry>')
    return xml.encode("utf-8")


# ---------------------------------------------------------------------------
# .rfa emission
# ---------------------------------------------------------------------------

#: streams stored WITHOUT CRCIO page framing (plain bytes) in a family file
UNFRAMED_STREAMS = ("BasicFileInfo", "TransmissionData", "RevitPreview4.0",
                    "PartAtom")

#: default donor for the FORMAT CONSTANTS a from-scratch family file still
#: needs from a real 2026 family container: the per-release schema
#: (``Formats/Latest`` -- a format constant), the ``Global/Latest``
#: ADocument (NO ADocument encoder exists yet -- the same open gate as the
#: project genesis stream, TRACKER G1a) and the opaque partition footer.
DEFAULT_DONOR = os.path.join(_ROOT, "vendor", "phi-ag-rvt", "examples", "Autodesk",
                             "racbasicsamplefamily-2026.rfa")

def our_transmission_data() -> bytes:
    """OUR ``TransmissionData`` stream: no external references.
    Framing = u32 UTF-16 code-unit count + UTF-16LE XML."""
    xml = ('<?xml version="1.0"?>\n<TransmissionData isTransmitted="false" '
           'userData="" version="5"></TransmissionData>')
    body = xml.encode("utf-16-le")
    return struct.pack("<I", len(body) // 2) + body


def _partition_stream_name(dit_model: Dict[str, Any]) -> str:
    """``Partitions/<N>``: N = document-increment count - 1 [VERIFIED
    relation on the six projects: N = DIT record count - 1]."""
    n = max(len(dit_model.get("records") or []) - 1, 0)
    return f"Partitions/{n}"


def emit_family_rfa(doc: FamilyDoc, path: str, *, donor: Optional[str] = None,
                    product_name: str = "rvt-writer", username: str = "rvt-writer",
                    timestamp: Optional[int] = None) -> Dict[str, Any]:
    """Write ``doc`` as a standalone ``.rfa`` container.

    OURS (built here): the whole ``Partitions/<N>`` save unit (every element
    of the document, our gzip, our block framing), ``Global/ElemTable``,
    ``Global/History``, ``Global/DocumentIncrementTable``,
    ``Global/PartitionTable``, ``Global/ContentDocuments`` (empty --
    a family document embeds no further documents), ``Contents``,
    ``BasicFileInfo`` (OUR identity), ``TransmissionData``, ``PartAtom``,
    all with real CRCIO page ECC and our CFB container.

    NOT ours (carried from ``donor``, the same open gates as the project
    genesis stream): ``Formats/Latest`` (the per-release schema -- a format
    constant, byte-identical in every 2026 file) and ``Global/Latest`` (the
    serialized ``ADocument`` -- no ADocument encoder exists, TRACKER gate
    G1a; the donor's carries dangling references to the donor's own element
    ids exactly as G0's does).  The opaque 64-byte unit footer blob + end
    record are taken from the donor too [UNKNOWN semantics; accepted
    around foreign content by the V15/V20 acceptance runs].  No
    ``RevitPreview4.0`` (optional stream) is written.
    """
    from .. import ecc
    from .. import stream_encoders as se
    from ..cfb_writer import CfbEntry, write_cfb
    from ..container import open_rvt
    from ..partitions import StreamWalker
    from ..writer import gzip_member
    donor = donor or DEFAULT_DONOR
    if not os.path.isfile(donor):
        raise FileNotFoundError(
            "family container source not found -- the default path (v2, "
            "rvt.frontdoor.standalone) builds it from the bundled genesis "
            "base; to use THIS v1 emitter supply donor= (an .rfa of yours). "
            f"(looked for: {donor})")
    if not doc.finalized:
        doc.finalize()
    ts = int(timestamp if timestamp is not None else time.time())
    # -- our streams ---------------------------------------------------------
    segs = doc.partition_payloads()
    gm = doc.globals_models(username=username, out_path=path, timestamp=ts)
    dit = gm["DocumentIncrementTable"]
    part_name = _partition_stream_name(dit)
    et_count = len(gm["ElemTable"]["records"])
    with open_rvt(donor) as f:
        formats_raw = f.raw("Formats/Latest")           # format constant (framed)
        latest_raw = f.raw("Global/Latest")             # ADocument gate (framed, donor)
        # opaque partition footer + end record from the donor's single unit
        w = StreamWalker(f.logical(next(iter(f.partition_streams()))),
                         inflate=False, keep_data=False)
        footer_blob = _donor_footer_blob(w)
        end_record = w.end_record
        prefixes = {n: f.prefix(f"Global/{n}") for n in
                    ("ElemTable", "History", "DocumentIncrementTable",
                     "PartitionTable", "ContentDocuments")}
        con_prologue = f.prefix("Contents")
    logical = build_partition_stream(segs, elem_table_count=et_count,
                                     footer_blob=footer_blob, end_record=end_record)
    enc = encode_minimal_globals(gm)
    streams: Dict[str, bytes] = {}
    streams[part_name] = ecc.frame_stream(logical)
    for n in ("ElemTable", "History", "DocumentIncrementTable", "PartitionTable"):
        streams[f"Global/{n}"] = ecc.frame_stream(
            prefixes[n] + gzip_member(enc[n], level=3, sync_flush=True))
    streams["Global/ContentDocuments"] = ecc.frame_stream(
        prefixes["ContentDocuments"] + gzip_member(enc["ContentDocuments"], level=3,
                                                   sync_flush=True))
    # Contents: OUR prologue (encoder) if it round-trips, else the donor's
    try:
        pro = se.encode_contents_prologue(gm["ContentsPrologue"])
        assert len(pro) == len(con_prologue)
        con_prologue = pro
    except Exception:                                   # pragma: no cover
        pass
    streams["Contents"] = ecc.frame_stream(
        con_prologue + gzip_member(enc["Contents"], level=3, sync_flush=True))
    streams["Formats/Latest"] = formats_raw
    streams["Global/Latest"] = latest_raw
    streams["BasicFileInfo"] = enc["BasicFileInfo"]
    streams["TransmissionData"] = our_transmission_data()
    streams["PartAtom"] = doc.part_atom(product_name=product_name)
    # -- the container --------------------------------------------------------
    entries = [CfbEntry(path="", entry_type="root")]
    for storage in ("Formats", "Global", "Partitions"):
        entries.append(CfbEntry(path=storage, entry_type="storage"))
    order = ["BasicFileInfo", "Contents", "Formats/Latest",
             "Global/ContentDocuments", "Global/DocumentIncrementTable",
             "Global/ElemTable", "Global/History", "Global/Latest",
             "Global/PartitionTable", "PartAtom", part_name, "TransmissionData"]
    for name in order:
        entries.append(CfbEntry(path=name, entry_type="stream", data=streams[name]))
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    write_cfb(path, entries)
    rep: Dict[str, Any] = {
        "path": path, "size": os.path.getsize(path), "donor": donor,
        "elements": len(doc.elements), "elem_table_count": et_count,
        "partition_stream": part_name, "logical_partition_bytes": len(logical),
        "document_guid": gm["_ids"]["document_guid"],
        "streams": {k: len(v) for k, v in streams.items()},
        "ours": ["Partitions save unit", "Global/ElemTable", "Global/History",
                 "Global/DocumentIncrementTable", "Global/PartitionTable",
                 "Global/ContentDocuments", "Contents", "BasicFileInfo",
                 "TransmissionData", "PartAtom"],
        "carried_from_donor": ["Formats/Latest (per-release schema constant)",
                               "Global/Latest (ADocument -- NO encoder; gate G1a)",
                               "unit footer blob + stream end record (opaque)"],
        "notes": list(doc.notes),
    }
    rep["verify"] = verify_family_rfa(path)
    return rep


def _donor_footer_blob(walker) -> bytes:
    """Extract the 64-byte 0x0f3f unit blob from a walked single-unit
    partition stream (opaque format bytes)."""
    raw = walker.raw if hasattr(walker, "raw") else b""
    i = raw.rfind(struct.pack("<H", FOOTER_TAG))
    if i < 0:
        return b""
    n = struct.unpack_from("<I", raw, i + 2)[0]
    if n < 0 or n > 4096:                              # pragma: no cover
        return b""
    return raw[i + 6:i + 6 + n]


# ---------------------------------------------------------------------------
# read-back verification + validation (family mode)
# ---------------------------------------------------------------------------

def verify_family_rfa(path: str) -> Dict[str, Any]:
    """Read the written family file back: gzip members CRC-verify, every
    full page's CRCIO trailer re-derives byte-exact, the single-unit
    partition walks clean, per-seq record counts agree, and every seq-102
    record decodes clean (schema)."""
    from .. import ecc
    from ..container import open_rvt
    from ..families import FamilyIndex, unit_segments
    from ..objects import iter_records
    rep: Dict[str, Any] = {"path": path, "gzip_members": 0, "gzip_crc_failures": 0,
                           "ecc_full_pages": 0, "ecc_mismatch": 0}
    with open_rvt(path) as d:
        rep["streams"] = sorted(s.name for s in d.streams())
        for s in d.streams():
            for m in d.members(s.name):
                rep["gzip_members"] += 1
                if not m.crc_ok:
                    rep["gzip_crc_failures"] += 1
            raw = d.raw(s.name)
            if s.name in UNFRAMED_STREAMS:
                continue
            for k in range(len(raw) // ecc.PAGE_STRIDE):
                page = raw[k * ecc.PAGE_STRIDE:k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD]
                tr = raw[k * ecc.PAGE_STRIDE + ecc.PAGE_PAYLOAD:(k + 1) * ecc.PAGE_STRIDE]
                rep["ecc_full_pages"] += 1
                if ecc.page_trailer(page) != tr:
                    rep["ecc_mismatch"] += 1
    idx = FamilyIndex(path)
    _pn, w = idx._walkers[0]
    rep["walker_errors"] = list(w.errors[:5])
    rep["n_units"] = len(idx.units)
    segs = unit_segments(idx, 0)
    rep["record_counts"] = {str(s): sum(1 for _ in iter_records(seg, s))
                            for s, seg in segs.items()}
    st = idx.decode_stats(0, 102)
    rep["decode_seq102"] = st
    ids = {s: [r.elem_id for r in iter_records(seg, s) if r.elem_id >= 0]
           for s, seg in segs.items()}
    rep["id_sets_identical_across_seqs"] = (ids.get(101) == ids.get(102) == ids.get(103))
    rep["ok"] = (rep["gzip_crc_failures"] == 0 and rep["ecc_mismatch"] == 0
                 and not rep["walker_errors"] and st["clean"] == st["records"]
                 and rep["id_sets_identical_across_seqs"])
    return rep


def validate_family(path: str, *, layers=None) -> Dict[str, Any]:
    """Run ``rvt.validate`` on a FAMILY file in family mode.

    The validator is calibrated on PROJECTS: it requires
    ``ProjectInformation`` (a project stream a family file never carries --
    ``PartAtom`` takes its place) and treats every non-metadata stream as
    CRCIO-framed (``PartAtom`` is plain unframed Atom XML).  Family mode
    applies exactly those two adjustments for the duration of the run
    (``PartAtom`` unframed; ``ProjectInformation`` not required) and
    reports the verdict; everything else -- container, ECC, gzip, walker,
    schema decode, ElemTable/DIT/History/Contents decode, reference
    integrity -- is validated unchanged.  Returns ``{verdict, errors,
    warnings, findings, project_mode: {...}}`` (the raw project-mode result
    is included for comparison).
    """
    from .. import validate as _v
    raw = _v.validate_file(path, layers=layers or _v.ALL_LAYERS)
    # family mode is now a first-class validator parameter (the recorded
    # `rvt_validate --family` request, landed) -- no global mutation
    fam = _v.validate_file(path, layers=layers or _v.ALL_LAYERS, family=True)

    def summarize(rep) -> Dict[str, Any]:
        errs = [f for f in rep.findings if f.severity == _v.SEV_ERROR]
        warns = [f for f in rep.findings if f.severity == _v.SEV_WARNING]
        return {"verdict": ("VALID" if not errs else "INVALID"),
                "n_errors": len(errs),
                "errors": [f"{f.layer} {f.where}: {f.message}" for f in errs],
                "n_warnings": len(warns),
                "warnings": [f"{f.layer} {f.where}: {f.message}" for f in warns],
                "stats": dict(rep.stats)}

    out = {"path": path, "family_mode": summarize(fam),
           "project_mode": summarize(raw)}
    out["ok"] = out["family_mode"]["n_errors"] == 0
    return out


# ---------------------------------------------------------------------------
# EMBEDDED save-unit form (the project-side loader's contract)
# ---------------------------------------------------------------------------

def build_embedded_unit(doc: FamilyDoc) -> Dict[str, Any]:
    """The EMBEDDED form of the family document, for the project-side loader
    (the forge stream's ``load_family``): a project embeds a family as an
    extra SAVE UNIT of ``Partitions/<N>`` + a ``Global/ContentDocuments``
    entry + host-side elements.

    Returns the pieces + the insertion CONTRACT (structure VERIFIED on the
    projects' embedded units; the loader's step list is the spec, not an
    implementation -- that is the forge stream's job):

    ``content_doc_guid``  the document GUID (= the unit separator GUID = the
                          ContentDocuments key = the host Family's
                          ``m_oFamDoc.m_contentDocGUID``);
    ``separator``         the 28-byte unit separator preceding our records
                          (u16 0x3a3, i32 -1, u16 0x3a2, u32 record_count,
                          16-byte GUID) [VERIFIED framing];
    ``segments``          per-seq record byte strings (with sentinels) of the
                          unit -- the loader RE-IDS every element into the
                          host id space (embedded ids are file-wide unique)
                          and re-blocks the stream;
    ``record_count``      elements in the unit (separator counter);
    ``content_documents_entry``  the entry grammar the loader must write
                          into ``Global/ContentDocuments``: u32 lead + 12-byte
                          null lead pointers (a3 03 ff ff ff ff a2 03 ff ff ff
                          ff) + GUID + u32 adoc_len + the document's serialized
                          ADocument (INLINE ElemTable + History) -- the
                          ADocument encoder is the open gate (G1a); the entry
                          is specified, not built;
    ``host_side``         what the host must gain: a ``Family`` element with
                          ``m_oFamDoc{m_contentDocGUID, m_big2SmallMap2}``,
                          one ``FamilySymbol`` per type, ElemRecs, the save
                          bookkeeping (mutation-plan §7).
    """
    if not doc.finalized:
        doc.finalize()
    segs = doc.partition_payloads()
    n = len(doc.elements)
    guid = doc.document_guid or str(uuid.uuid4())
    gbytes = uuid.UUID(guid).bytes_le
    separator = (struct.pack("<Hi", _PART_TAG, -1) + struct.pack("<HI", 0x3A2, n)
                 + gbytes)
    return {
        "content_doc_guid": guid,
        "record_count": n,
        "separator": separator,
        "segments": segs,
        "self_family_id": doc.self_family.elem_id,
        "type_names": [t for t, _v in doc.types],
        "content_documents_entry": {
            "lead": "u32 X (varies)",
            "null_lead_pointers": "a303ffffffffa203ffffffff",
            "guid": guid,
            "adoc": "u32 adoc_len + serialized ADocument (inline ElemTable 0x5c9 + "
                    "History 0x538) -- OPEN GATE: ADocument encoder (G1a)",
            "spacing": "consecutive entries adoc_len + 36 bytes apart",
        },
        "host_side": [
            "host Family element: m_oFamDoc{m_contentDocGUID=guid, "
            "m_big2SmallMap2 host->embedded id map}, m_categoryId, m_familyIds",
            "one host FamilySymbol per type (types are HOST-side in a project)",
            "ElementHeaders + ElemRecs for the host elements; embedded elements "
            "re-idded into the host id space; save bookkeeping (record_save)",
        ],
        "notes": ["the loader implements this contract (forge stream); this "
                  "module supplies the document bytes + the spec"],
    }


# ---------------------------------------------------------------------------
# S0 -- the empty family document (skeleton only, one type, no geometry)
# ---------------------------------------------------------------------------

S0_OUT = os.path.join(_ROOT, "experiments", "families", "genesis",
                      "S0_empty_family.rfa")
S0E_OUT = os.path.join(_ROOT, "experiments", "families", "genesis",
                       "S0_electrical_family.rfa")


def build_s0(*, category="furniture", name: str = "S0 Empty Family",
             with_params: bool = True, timestamp: Optional[int] = 0) -> FamilyDoc:
    """S0 = the family-document SKELETON only: self-Family, Reference Level,
    two origin reference planes, units, the plan-view constellation, three
    length parameters (Length / Width / Height) and ONE type row -- no
    geometry, no connector.  The from-scratch analogue of the project
    stream's minimal skeleton."""
    doc = new_family_document(category, name)
    if with_params:
        L = doc.add_family_parameter("Length", SPEC_LENGTH, PGROUP_DIMENSIONS)
        W = doc.add_family_parameter("Width", SPEC_LENGTH, PGROUP_DIMENSIONS)
        H = doc.add_family_parameter("Height", SPEC_LENGTH, PGROUP_DIMENSIONS)
        doc.add_type("Standard", {L.elem_id: mm(600.0), W.elem_id: mm(300.0),
                                  H.elem_id: mm(150.0),
                                  "description": "Empty parametric family (skeleton only)",
                                  "manufacturer": "rvt-writer", "model": "S0"})
    else:
        doc.add_type("Standard")
    doc.finalize()
    return doc


def build_s0e_electrical(*, name: str = "S0e Panelboard 208Y-120V 225A MLO") -> FamilyDoc:
    """S0e = the electrical variant of the skeleton: an ELECTRICAL EQUIPMENT
    family (panelboard part type) with the panel FACTS as type parameters
    (rated voltage, mains rating, bus rating, enclosure W x H x D -- OUR
    parameters carrying manufacturer FACTS, our expression), the document's
    own load classification and ONE power connector whose voltage /
    apparent load are ASSOCIATED to the type parameters.  Still no
    geometry: the connector is referenced to the Reference Level datum
    (a solid face is the geometry stream's job) [UNKNOWN acceptance --
    the honest gap of every geometry-free MEP family]."""
    doc = new_family_document("electrical_equipment", name,
                              part_type=PART_TYPE["panelboard"],
                              work_plane_based=True)
    V = doc.add_family_parameter("Panel Voltage", SPEC_VOLTAGE, PGROUP_ELECTRICAL)
    A = doc.add_family_parameter("Apparent Load", SPEC_APPARENT_POWER,
                                 PGROUP_ELECTRICAL_LOADS)
    W = doc.add_family_parameter("Width", SPEC_LENGTH, PGROUP_DIMENSIONS)
    H = doc.add_family_parameter("Height", SPEC_LENGTH, PGROUP_DIMENSIONS)
    D = doc.add_family_parameter("Depth", SPEC_LENGTH, PGROUP_DIMENSIONS)
    doc.add_type("225 A MLO", {
        V.elem_id: volts(208.0), A.elem_id: voltamps(0.0),
        W.elem_id: mm(508.0), H.elem_id: mm(1524.0), D.elem_id: mm(146.0),
        "manufacturer": "rvt-writer generic", "model": "PNL-208Y120-225MLO",
        "description": "208Y/120 V, 3-phase 4-wire, 225 A main-lug-only "
                       "panelboard (generated from facts; skeleton only)"})
    doc.add_electrical_connector(voltage=208.0, poles=3, load_class="Power",
                                 apparent_load_va=0.0, power_factor=1.0,
                                 bind_voltage_param="Panel Voltage",
                                 bind_load_param="Apparent Load",
                                 description="Power Connection")
    doc.finalize()
    return doc


def main(argv=None) -> int:
    argv = list(argv or [])
    doc = build_s0()
    print(f"S0 family document: {len(doc.elements)} elements "
          f"(self-Family {doc.self_family.elem_id}, ref level {doc.ref_level.elem_id}, "
          f"{len(doc.refplanes)} ref planes, {len(doc.params)} params, "
          f"{len(doc.types)} type(s))")
    for e in doc.elements:
        print(f"  {e.elem_id:>6}  {e.class_name:20s} {e.kind}")
    rep = doc.roundtrip()
    print(f"encode->decode round-trip: {rep['roundtrip_ok']}/{rep['records']} records, "
          f"{rep['encoded_bytes']:,} object bytes, failures={rep['failed']}")
    for b in rep["failures"][:10]:
        print("   FAIL", b)
    if "--no-rfa" in argv:
        return 0 if rep["failed"] == 0 else 1
    if not os.path.exists(DEFAULT_DONOR):
        print(f"donor container {DEFAULT_DONOR} absent -- skipping .rfa emission")
        return 0 if rep["failed"] == 0 else 1
    ok = rep["failed"] == 0
    for label, d, out in (("S0", doc, S0_OUT), ("S0e", build_s0e_electrical(), S0E_OUT)):
        r = d.to_rfa(out, timestamp=0)
        print(f"{label} -> {out} ({r['size']:,} B); verify ok={r['verify']['ok']}, "
              f"records/seq={r['verify']['record_counts']}, decode={r['verify']['decode_seq102']}")
        ok = ok and r["verify"]["ok"]
        try:
            v = validate_family(out)
            print(f"   validate (family mode): {v['family_mode']['verdict']} "
                  f"errors={v['family_mode']['n_errors']} warnings={v['family_mode']['n_warnings']}")
            for e in v["family_mode"]["errors"]:
                print("      ERROR", e)
            print(f"   validate (project mode, reference only): "
                  f"errors={v['project_mode']['n_errors']} {v['project_mode']['errors']}")
            ok = ok and v["family_mode"]["n_errors"] == 0
            rp = os.path.splitext(out)[0] + "_validate.json"
            with open(rp, "w") as fh:
                json.dump({"emit": {k: v2 for k, v2 in r.items() if k != "verify"},
                           "verify": r["verify"], "validate": v}, fh, indent=1, default=str)
            print("   report ->", rp)
        except Exception as e:                                  # pragma: no cover
            print("   validate failed:", e)
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    import sys
    sys.exit(main(sys.argv[1:]))

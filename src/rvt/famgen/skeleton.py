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
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# --- reuse the project skeleton's building blocks (same shape contract) -----
from ..genesis import skeleton as _gsk
from ..genesis.skeleton import (            # noqa: F401  (re-exported building blocks)
    SkelElement, IdSource, _alloc, class_id, DUMMY_STAMP,
    element_base, symbol_base, element_header, element_parents,
    param_set_int, param_set_elemid, param_set_astring, param_set_double,
    plane, EMPTY_ENVELOPE, _ptr, _weak,
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
    # cut vector = xvec x yvec normalised (the sketching view direction)
    cx = xvec[1] * yvec[2] - xvec[2] * yvec[1]
    cy = xvec[2] * yvec[0] - xvec[0] * yvec[2]
    cz = xvec[0] * yvec[1] - xvec[1] * yvec[0]
    cl = (cx * cx + cy * cy + cz * cz) ** 0.5 or 1.0
    cut = [cx / cl, cy / cl, cz / cl]
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

def param_type_id(family_guid: str, param_elem_id: int) -> str:
    """The ``m_typeId`` identity of a family parameter:
    ``revit.local.family:<32 hex guid><8 hex elem id>-1.0.0`` [VERIFIED
    format; the guid is a per-creation-session GUID -- OURS is a fresh uuid4]."""
    g = uuid.UUID(str(family_guid)).hex
    return f"revit.local.family:{g}{int(param_elem_id) & 0xFFFFFFFF:08x}-1.0.0"


def new_family_parameter(elem_id: int, self_family_id: int, name: str, *,
                         spec_type_id: str = SPEC_LENGTH,
                         group_type_id: str = PGROUP_DIMENSIONS,
                         family_guid: Optional[str] = None,
                         is_instance: bool = False, description: str = "",
                         read_only: bool = False, user_visible: bool = True,
                         restriction: int = 1, flags: int = 8218) -> SkelElement:
    """A ``ParamElemFamily`` = one FAMILY PARAMETER (its definition; the
    per-type VALUES live in the self-Family's ``FamilyTypeTable`` /
    ``m_familyParams``, keyed by this element's id as the paramId).

    [VERIFIED byte-exact vs the .rfa's Height / Width / Length parameters]
    ``spec_type_id`` = the measurable spec (:data:`SPEC_LENGTH`, voltage...);
    ``group_type_id`` = the properties-palette group; ``family_guid`` seeds
    the ``revit.local.family`` identity (default: a fresh uuid4).
    ``restriction`` 1 [VERIFIED on all specimen params; meaning UNKNOWN].
    """
    fam_guid = family_guid or str(uuid.uuid4())
    o = element_base(elem_id, cell_list=False, design_option=FAMILY_DESIGN_OPTION)
    o["m_famId"] = int(self_family_id)
    o["m_description"] = str(description)
    o["m_pParamDef"] = _ptr("ParamDefValue", {
        "m_dynamicGroupName": "",
        "m_groupTypeId": {"m_typeId": str(group_type_id)},
        "m_caption": str(name),
        "m_typeId": {"m_typeId": param_type_id(fam_guid, elem_id)},
        "m_paramElemId": int(elem_id),
        "m_allowVaryBetweenGroups": False,
        "m_readOnly": bool(read_only),
        "m_userVisible": bool(user_visible),
        "m_specTypeId": {"m_typeId": str(spec_type_id)},
        "m_restriction": int(restriction),
        "m_boundless": False,
    })
    o["m_instanceParam"] = bool(is_instance)
    hdr = element_header("ParamElemFamily", category=-1,
                         deletion=[self_family_id, elem_id],
                         flags=flags, visible_view_flags=-32768,
                         family_id=self_family_id)
    return SkelElement(elem_id, "ParamElemFamily", hdr, o, None, kind="family_param",
                       refs={"family": self_family_id, "caption": name,
                             "spec": spec_type_id, "group": group_type_id})


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

#: Revit's ElectricalSystemType for a power connector's domain
#: (m_systemType) [VERIFIED 31 on every electrical connector specimen;
#: 31 = PowerCircuit INFERRED from the API enum]
ELECTRICAL_SYSTEM_POWER = 31

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


def electrical_domain(*, voltage_v: float, poles: int = 1,
                      apparent_load_va: float = 0.0, power_factor: float = 1.0,
                      load_classification_id: int = -1,
                      description: str = "",
                      balanced_load: bool = True) -> dict:
    """The ``ConnectorElemDomainElectrical`` owned object of a POWER
    connector, from the calc-engine values (display units in, internal out).

    [VERIFIED unit rule + field values on the panelboard / lighting /
    receptacle connectors]  ``apparent_load_va`` is booked on phase 1 for a
    single-phase load (as the specimens do); ``load_classification_id`` =
    an ``ElectricalLoadClassification`` element (the document's own copy in a
    standalone family) -- -1 = unclassified.
    """
    load1 = voltamps(apparent_load_va) if balanced_load or poles == 1 else 0.0
    return {
        "m_pConnElem": _weak(2),
        "m_dVoltage": volts(voltage_v),
        "m_dApparentLoad": 0.0,
        "m_dApparentLoadPhase1": float(load1),
        "m_dApparentLoadPhase2": 0.0,
        "m_dApparentLoadPhase3": 0.0,
        "m_dPowerFactor": float(power_factor),
        "m_idLoadClassification": int(load_classification_id),
        "m_nNumberOfPoles": int(poles),
        "m_systemType": ELECTRICAL_SYSTEM_POWER,
        "m_powerFactorState": 1,          # 1 = lagging [INFERRED]
        "m_bIsConnectorPrimary": True,
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
                             apparent_load_va: float = 0.0,
                             power_factor: float = 1.0,
                             description: str = "",
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
    ``load_class_id``).  ``edge_loop_tags`` = the host face's edge tags
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
        description=description))
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
    family_guid: str = ""
    document_guid: str = ""
    self_family: Optional[SkelElement] = None
    ref_level: Optional[SkelElement] = None
    level_type: Optional[SkelElement] = None
    refplanes: List[SkelElement] = dc_field(default_factory=list)
    params: Dict[str, SkelElement] = dc_field(default_factory=dict)   # caption -> ParamElemFamily
    types: List[Tuple[str, Dict[Any, Any]]] = dc_field(default_factory=list)
    current_type: int = 0
    connectors: List[SkelElement] = dc_field(default_factory=list)
    load_classes: List[SkelElement] = dc_field(default_factory=list)
    views: List[SkelElement] = dc_field(default_factory=list)
    view_ids: Dict[str, int] = dc_field(default_factory=dict)
    plan_view_id: int = -1
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
        """Add a user FAMILY PARAMETER (``ParamElemFamily``) and register its
        default value on every type row and the current-type value set.

        ``spec_type_id`` = the measurable spec (:data:`SPEC_LENGTH`,
        :data:`SPEC_VOLTAGE`, ...); ``group_type_id`` = the palette group;
        ``default`` = the value (internal units) written to every type.
        ``formula`` = the parameter formula text [UNKNOWN encoding: formulas
        live in the ``FamDimConstrMgrImpl`` expression tables which this
        skeleton leaves empty -- carried in ``refs`` for the spec only].
        """
        pe = new_family_parameter(_alloc(self.ids), self.self_family.elem_id, name,
                                  spec_type_id=spec_type_id, group_type_id=group_type_id,
                                  family_guid=self.family_guid,
                                  is_instance=is_instance)
        if formula:
            pe.refs["formula"] = str(formula)
            pe.notes.append("formula NOT serialized (dimension-expression tables empty)")
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

    def add_electrical_connector(self, *, host_element_id: Optional[int] = None,
                                 host_geom_tag: int = 0,
                                 location: Optional[Sequence[float]] = None,
                                 direction: Sequence[float] = (0.0, 0.0, -1.0),
                                 voltage: float = 120.0, poles: int = 1,
                                 load_class: str = "Power",
                                 apparent_load_va: float = 0.0,
                                 power_factor: float = 1.0,
                                 bind_voltage_param: Optional[str] = None,
                                 bind_load_param: Optional[str] = None,
                                 description: str = "Power Connection") -> SkelElement:
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
        VERIFIED FamilyParametrizedElemParamsCell mechanism].
        """
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
            index=len(self.connectors) + 1)
        self.connectors.append(con)
        self.add(con)
        return con

    # -- finalisation --------------------------------------------------------
    def finalize(self) -> "FamilyDoc":
        """Seed the self-Family from the final element / type / parameter
        state (type table, current-type value set, parameter ordering,
        element index, ownership).  Idempotent; called by the delivery
        methods."""
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
        # locked-for-direct-manipulation = the length parameters (Revit locks
        # dimension params it drives geometry with) [INFERRED default]
        fam.obj["m_lockedParameterIdsForDirectManipulation"] = sorted(
            pe.elem_id for pe in pes if pe.refs.get("spec") == SPEC_LENGTH)
        # element index + ownership over EVERY element (self last)
        others = [e.elem_id for e in self.elements if e.elem_id != fam.elem_id]
        refresh_self_family_index(fam, others)
        self.finalized = True
        return self

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
                        plane_length_ft: float = 10.0) -> FamilyDoc:
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
    origin planes intersect at.  Returns an un-finalised :class:`FamilyDoc`
    ready for ``add_type`` / ``add_family_parameter`` /
    ``add_reference_plane`` / ``add_electrical_connector``.
    """
    cat = _resolve_category(category)
    ids = IdSource(start_id)
    fam_guid = family_guid or str(uuid.uuid4())
    doc_guid = document_guid or str(uuid.uuid4())
    ptype = int(part_type) if part_type is not None else (
        PART_TYPE["panelboard"] if cat == OST_ELECTRICAL_EQUIPMENT and "panel" in name.lower()
        else PART_TYPE["normal"])
    doc = FamilyDoc(category_id=cat, name=str(name), host=str(host),
                    origin=tuple(float(c) for c in origin), ids=ids,
                    family_guid=fam_guid, document_guid=doc_guid,
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
             "electrical_fixtures": OST_ELECTRICAL_FIXTURES}
    if key not in table:
        raise KeyError(f"unknown family category {category!r}")
    return table[key]


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
    els = list(proj.elements()) + [vt] + list(plan.elements())
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
    return plan.view.elem_id


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


def build_part_atom(title: str, category_label_txt: str, *,
                    type_names: Sequence[str] = (), product_name: str = "rvt-writer",
                    updated: Optional[str] = None) -> bytes:
    """The ``PartAtom`` stream: plain Atom XML in the partatom namespace
    (title, category, updated stamp, the product/design-file entry and the
    type list).  The XML VOCABULARY is format (interoperability); the VALUES
    are ours -- no Autodesk taxonomy URLs, no OmniClass, no Autodesk product
    label [D content policy].  UNFRAMED stream (like BasicFileInfo).
    """
    from xml.sax.saxutils import escape as _x
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

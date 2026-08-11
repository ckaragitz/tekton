"""rvt.genesis.cabletray -- OUR native cable tray TYPE (issue #608).

WHY: `Systems > Electrical > Cable Tray` draws a native ``CableTray`` element
whose type is an ``RbsCableTrayType`` -- a SYSTEM family, which lives in a
project/template, never in a ``.rfa``.  Our certified base already carries the
plumbing (``CableTraySettingsElem`` 1, ``CableTraySizesElem`` 1) but **zero**
types, so the Cable Tray tool has nothing to draw.  This authors one.

WHAT REVIT OWNS: ``CableTrayExtrusionGStep`` -- Revit generates the straight
run's geometry from the type.  Measured across a Revit-born Electrical
template's seven types, only two profile classes exist:

    m_eCableTrayType 1 -> UShapeSweepProfile   (Wire Mesh, Solid Bottom,
                                                Channel, Trough, Single Rail)
    m_eCableTrayType 2 -> LadderSweepProfile   (Ladder)

`m_Profile.value` is EMPTY in every one of them.  So a wire-mesh tray is drawn
as a plain U trough whatever it is called: there is no mesh profile to author,
and LOD-400 mesh geometry on a straight run is not reachable through the
native element.  It IS reachable on the FITTINGS, which are loadable families
(``m_idDefault*`` below) -- see #608.

PROVENANCE: the field set and the two enum values are a LAW mined from a
Revit-born specimen (hard rule 3: mine laws from samples, author our own
equivalents).  Every VALUE here is ours or a plain physical constant; no
donor bytes, and nothing is read from an Autodesk installation (rule 2).

Territory: issue #608 (new module; nothing else in rvt.genesis changes).
"""
from __future__ import annotations

from typing import Optional

from .types import (INVALID, TypeRecord, _ptr, _record, blank_object,
                    element_defaults)

__all__ = ["CABLE_TRAY_CATEGORY", "SHAPE_U", "SHAPE_LADDER", "new_cable_tray_type"]

#: OST_CableTray [MEASURED on the specimen's types]
CABLE_TRAY_CATEGORY = -2008130

#: ``m_eCableTrayType`` [MEASURED across all seven specimen types]
SHAPE_U = 1
SHAPE_LADDER = 2

_PROFILE_FOR = {SHAPE_U: "UShapeSweepProfile", SHAPE_LADDER: "LadderSweepProfile"}

#: every fitting slot an RbsCableTrayType carries.  Each names a LOADABLE
#: family; -1 = none.  A type with no fitting families still draws straight
#: runs -- that is what the specimen's `m_bWithFitting False` variants do.
_FITTING_SLOTS = (
    "m_idDefaultElbow", "m_idDefaultElbowUp", "m_idDefaultElbowDown",
    "m_idDefaultTee", "m_idDefaultTeeUp", "m_idDefaultTeeDown",
    "m_idDefaultCross", "m_idDefaultTransition", "m_idDefaultUnion",
    "m_idDefaultTakeoff", "m_idMechJoint", "m_idDefaultMultiShape",
    "m_idDefaultMultiShapeOvalToRound", "m_idDefaultMultiShapeRectToOval",
)


def new_cable_tray_type(name: str, elem_id: int, *,
                        shape: int = SHAPE_U,
                        with_fitting: bool = False,
                        branch_type_tee: bool = False,
                        max_width_ft: float = 8.0,
                        max_height_ft: float = 8.0,
                        min_bend_multiplier: float = 1.0,
                        roughness: float = 0.0003,
                        rise_drop_type: int = 0,
                        fittings: Optional[dict] = None) -> TypeRecord:
    """One ``RbsCableTrayType`` -- a system-family type the Cable Tray tool
    can draw.

    ``shape`` = :data:`SHAPE_U` or :data:`SHAPE_LADDER`; the profile class
    follows from it.  ``fittings`` = {slot name: family symbol id} for the
    ``m_idDefault*`` slots; anything unnamed stays -1 (no fitting), which is
    the shape a first probe wants because it depends on no loaded families.

    ``roughness`` 0.0003 and the 8 ft max width/height are the specimen's
    values -- plain engineering constants, carried because Revit expects a
    sane range, not because they are anyone's product data.
    """
    if shape not in _PROFILE_FOR:
        raise ValueError(f"cable tray shape must be {SHAPE_U} (U) or "
                         f"{SHAPE_LADDER} (ladder), got {shape!r}")
    o = blank_object("RbsCableTrayType")
    # element_defaults, NOT blank_object alone: it stamps m_id (and the
    # param-set pointers).  A blanked object keeps m_id = -1, and Revit
    # asserts on the mismatch at load -- measured, desktop:
    #   "The id stored in the ElemRec 1472525 does not match the id stored
    #    in the Element -1"  -> Unmarshaller.cpp:364 -> 0xe06d7363, open aborts.
    element_defaults(o, elem_id)
    o["m_Profile"] = _ptr(_PROFILE_FOR[shape], {})
    o["m_eCableTrayType"] = int(shape)
    o["m_eRiseDropType"] = int(rise_drop_type)
    o["m_bWithFitting"] = bool(with_fitting)
    o["m_bBranchTypeTee"] = bool(branch_type_tee)
    o["m_dMaxWidth"] = float(max_width_ft)
    o["m_dMaxHeight"] = float(max_height_ft)
    o["m_dMinBendMultiplier"] = float(min_bend_multiplier)
    o["m_dRoughness"] = float(roughness)
    for slot in _FITTING_SLOTS:
        o[slot] = int((fittings or {}).get(slot, INVALID))
    o["m_previewElemId"] = INVALID
    o["m_renderStyleId"] = INVALID
    o["m_pCompoundStructure"] = None
    o["m_symbolInfo"] = _ptr("SymbolInfo", {"m_name": str(name)})
    return _record("cable_tray_type", "RbsCableTrayType", CABLE_TRAY_CATEGORY,
                   elem_id, o,
                   refs={k: o[k] for k in _FITTING_SLOTS if o[k] != INVALID},
                   notes=[f"shape {shape} -> {_PROFILE_FOR[shape]}; Revit generates the "
                          f"straight-run geometry (CableTrayExtrusionGStep)",
                          "fitting slots: " + (", ".join(
                              k for k in _FITTING_SLOTS if o[k] != INVALID) or "none (-1)")])

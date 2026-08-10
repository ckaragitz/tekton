"""rvt.famgen.param_drive -- the PARAMETRIC-DRIVE LAW (issue #372).

A generated family whose Width/Height parameters actually MOVE the
extrusion needs the donor's drive chain, measured on a Revit-2026-born
family document (scratchpad dumps ``donor_lineardims.json`` /
``donor_dims.json`` / ``donor_varsketch_2432.json``, elements 2427-2441,
cross-checked against a second Revit-born donor .rfa):

* a LABELED ``LinearDimString`` per driven direction: one dimension
  segment with ``m_paramId`` = the family-parameter element id and
  ``m_lockedValue`` = the current value, witnessed by TWO ``RefPlane``
  datums (``GeomSegInPlaneRef`` witnesses, geomTag 0);
* an ``Alignment`` per profile sketch line locking that ``CurveElem``
  to a ``RefPlane`` (same Dimension layout, ``m_paramId`` -1, a
  ``SketchMembership`` cell naming the ``VarSketch``, ``m_constrDir`` =
  the constrained direction);
* the sketch REGISTERS its constraints: ``VarSketch.m_dimIds`` = the
  alignment ids and ``m_dimData`` = ``[(id, 1|0), ...]`` (donor 2432:
  ``[(2438,1),(2439,0),(2440,1),(2441,0)]`` -- horizontal locks carry 1,
  vertical locks 0), and the alignments join the sketch header's
  deletion list (donor sketch 580: dims listed; its CurveElems list NO
  dim ids -- curves' headers stay untouched).

Every constant below is a donor MEASUREMENT (structural shape / flag /
sentinel), never copied content: the 1e30 "unset" sentinels, the witness
gaps 1/192 ft and 1/128 ft, dimension flags 12 (labeled dim) / 30
(alignment), category ids -2000260 / -2000262, GLine rep-token flags
524292, header flags 10 with visible-view flags -4225.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..genesis.types import blank_object
from . import geometry as G
from .skeleton import (
    SkelElement, _alloc, element_base, element_header,
    new_reference_plane, FAMILY_DESIGN_OPTION,
)

Vec = Sequence[float]

# -- donor-measured constants (shapes/flags, not content) -------------------
CAT_DIMENSIONS = -2000260        #: LinearDimString header category [V donor 2427/2428]
CAT_ALIGNMENTS = -2000262        #: Alignment header category [V donor 2438-2441 + 2033]
HDR_FLAGS = 10                   #: m_abFlags4Bytes on both classes [V]
HDR_VISIBLE = -4225              #: m_nVisibleViewFlags on both classes [V]
DIM_FLAGS = 12                   #: labeled LinearDimString m_flags [V]
ALIGN_FLAGS = 30                 #: Alignment m_flags [V]
UNSET = 1e30                     #: witness offset/dir "unset" sentinel [V]
GAP_TO_ELT = 0.005208333333333333   #: 1/192 ft witness gap [V]
GAP_TO_DIM = 0.0078125              #: 1/128 ft witness gap [V]
GLINE_DIM_FLAGS = 524292         #: m_pDimLine GLine GInfo flags [V]
#: annotation layout offsets of the donor's labeled dims (refPnt inset from
#: the witness plane's end; dim line a further step outward) -- cosmetic
#: placement, reused as constants [V donor 2427]
REFPNT_INSET = 0.0720885
DIMLINE_STEP = 0.0073657


def _owning() -> dict:
    return {"m_pOwningDimension": {"weakref": 2}}


def _wrap_owning() -> dict:
    return {"m_OwningDimension": _owning()}


def _seg_value(value: Optional[float]) -> dict:
    """One ``m_values`` entry: the leading entry carries the value + its
    ``DimSegValueTextFields`` (all-empty text), the two trailing entries the
    -1.0 placeholders [V donor: every seg carries exactly 3 entries]."""
    if value is None:
        return {"m_value": -1.0, "m_oTextFields": None,
                "m_pDimSegValueBase": None, **_wrap_owning()}
    return {
        "m_value": float(value),
        "m_oTextFields": {"ptr_class": "DimSegValueTextFields", "pid": -1, "value": {
            "m_above": "", "m_below": "", "m_prefix": "", "m_suffix": "",
            "m_valueOverride": "", "m_pDimSegValueTextFieldsBase": None,
            **_wrap_owning()}},
        "m_pDimSegValueBase": None, **_wrap_owning()}


def _seg_info(*, locked_value: float, origin: Vec, param_id: int,
              flags: int, seg_value: float, equality_seg: int = 0,
              id1: int = 0, id2: int = 1, with_text: bool = True) -> dict:
    return {
        "m_pDimSegInfoBase": None, "m_oOffset2": None,
        "m_lockedValue": float(locked_value),
        "m_origin": [float(c) for c in origin],
        "m_offset": [0.0, 0.0],
        "m_paramId": int(param_id),
        "m_equalitySegNumber": int(equality_seg),
        "m_flags": int(flags),
        "m_id": {"m_id1": int(id1), "m_id2": int(id2)},
        "m_leaderVisibility": 0,
        "m_values": ([_seg_value(seg_value), _seg_value(None), _seg_value(None)]
                     if with_text else
                     [_seg_value(None), _seg_value(None), _seg_value(None)]),
        **_wrap_owning()}


def _equality_arr() -> dict:
    """``m_ArrEqualityFormulaInfo_DimEqSegInfoArr``: one placeholder seg
    (equalitySegNumber 1, id {1,1}, three -1.0 values, no text) [V]."""
    return {"m_arr": [_seg_info(locked_value=0.0, origin=(0.0, 0.0, 0.0),
                                param_id=-1, flags=0, seg_value=0.0,
                                equality_seg=1, id1=1, id2=1, with_text=False)],
            "m_maxSize": 0, "m_isLazy": False}


def _witness(target_id: int, *, ends: Tuple[Vec, Vec], ref_length: float,
             wid: int, end_idx: int, constr_flags: int) -> dict:
    """One ``m_witnessRefs`` entry wrapping a ``GeomSegInPlaneRef`` at
    ``target_id`` (geomTag 0, subTag -1) [V donor shape]."""
    return {
        "m_pWitnessRefInfoBase": None,
        "m_pWitnessRef": {"ptr_class": "GeomSegInPlaneRef", "pid": -1, "value": {
            "m_geomRef": {
                "m_intermediateTags": [], "m_oNextRef": None,
                "m_elemId": int(target_id), "m_ownerDBViewId": -1,
                "m_foreignElemIdRef": {"m_id64": -1},
                "m_geomTag": 0, "m_subTag": -1, "m_famMemberIdx": -1,
                "m_flags": 0, "m_isLazyRef": False},
            "m_sideOfArc": False}},
        "m_refToDimOffset": [UNSET] * 3, "m_refBendOffset": [UNSET] * 3,
        "m_refDir": [UNSET] * 3, "m_refBendDir": [UNSET] * 3,
        "m_oldRefSegEnds": [[float(c) for c in ends[0]],
                            [float(c) for c in ends[1]]],
        "m_gapToElt": GAP_TO_ELT, "m_gapToDim": GAP_TO_DIM,
        "m_refLength": float(ref_length),
        "m_id": {"m_id": int(wid)},
        "m_oldRefSegEndIdx": int(end_idx),
        "m_useDistToDimLn": False, "m_modified": False,
        "m_constrFlags": int(constr_flags),
        "m_flipDirForAngle": False,
        **_owning()}


def _dim_line(origin: Vec, dir_vec: Vec) -> dict:
    """The ``m_pDimLine`` GLine token (unbounded: endParams [0,0]) [V]."""
    gl = blank_object("GLine")
    gl["m_GInfo"] = G.ginfo(category=-1, tag=-1, control_command=0,
                            flags=GLINE_DIM_FLAGS)
    gl["m_endParams"] = [0.0, 0.0]
    gl["m_origin"] = [float(c) for c in origin]
    gl["m_dirVec"] = [float(c) for c in dir_vec]
    return {"ptr_class": "GLine", "pid": -1, "value": gl}


def _identity_trf() -> dict:
    return {"m_3x3": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
            "m_or": [0.0, 0.0, 0.0]}


def _seg_length(ends: Tuple[Vec, Vec]) -> float:
    a, b = ends
    return (sum((float(b[i]) - float(a[i])) ** 2 for i in range(3))) ** 0.5


def _family_id_of(ctx_or_family_id: Any) -> int:
    fid = getattr(ctx_or_family_id, "family_id", ctx_or_family_id)
    return int(fid)


def _dimension_common(obj: dict, elem_id: int, family_id: int, view_id: int,
                      style_id: int) -> None:
    """The Element base + the Dimension fields both classes share [V]."""
    for k, v in element_base(elem_id, cell_list=False,
                             design_option=FAMILY_DESIGN_OPTION).items():
        obj[k] = v
    obj["m_famId"] = int(family_id)
    obj["m_ownerDBViewId"] = int(view_id)
    obj["m_oldRefSegEndPnt"] = []
    obj["m_oldRefSegEnd"] = []
    obj["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"] = _equality_arr()
    obj["m_lastTrf"] = _identity_trf()
    obj["m_planeNormal"] = [0.0, 0.0, 1.0]
    obj["m_styleSymbolId"] = int(style_id)
    obj["m_dimSketchPlaneId"] = -1
    obj["m_lastDimSegInfoId"] = {"m_id1": 1, "m_id2": 1}
    obj["m_dimVersion"] = 1
    obj["m_useEqualityFormula"] = False
    obj["m_showLabelGP"] = False
    obj["m_multiReferenceAnnotationId"] = -1
    obj["m_patternId"] = -1
    obj["m_lastUsedId"] = {"m_id": 1}
    obj["m_fixedDir"] = [0.0, 0.0, 0.0]
    obj["m_dirType"] = 0


# ---------------------------------------------------------------------------
# constructors
# ---------------------------------------------------------------------------

def new_alignment(elem_id: int, ctx_or_family_id: Any, *, sketch_id: int,
                  curve_id: int, refplane_id: int, style_id: int,
                  constr_dir: Vec, origin: Vec,
                  curve_ends: Tuple[Vec, Vec], plane_ends: Tuple[Vec, Vec],
                  view_id: int = -1, sketch_plane_id: int = -1,
                  plane_first: bool = False,
                  dim_line_dir: Optional[Vec] = None,
                  ref_pnts: Optional[Tuple[Vec, Vec]] = None,
                  notes=None) -> SkelElement:
    """An ``Alignment`` locking sketch ``CurveElem`` ``curve_id`` to
    ``RefPlane`` ``refplane_id`` -- donor 2438's exact field shape.

    ``plane_first`` selects the donor's two witness orders: False =
    donor 2438/2439 (curve witness first, constrFlags 8, then the plane,
    constrFlags 1, oldRefSegEndIdx 1); True = donor 2440/2441 (plane
    first, constrFlags 4, then the curve, constrFlags 2, both idx 0).
    ``constr_dir`` = the constrained direction (the boundary's outward
    axis: vertical lines (+-1,0,0), horizontal (0,+-1,0)) [V donor].
    ``curve_ends`` / ``plane_ends`` = the witness segments' endpoints
    (curve endpoints; the plane's drawn datum line).
    """
    family_id = _family_id_of(ctx_or_family_id)
    obj = blank_object("Alignment")
    _dimension_common(obj, elem_id, family_id, view_id, style_id)
    obj["m_cellList"] = {"ptr_class": "CellList", "pid": -1, "value": {
        "m_cells": [{"ptr_class": "SketchMembership", "pid": -1,
                     "value": {"m_groupId": int(sketch_id)}}]}}
    p0 = [float(c) for c in origin]
    if ref_pnts is None:
        ref_pnts = (p0, p0)
    obj["m_refPnts"] = [[float(c) for c in ref_pnts[0]],
                        [float(c) for c in ref_pnts[1]]]
    obj["m_ArrSegInfo"] = [_seg_info(locked_value=0.0, origin=p0, param_id=-1,
                                     flags=1, seg_value=0.0)]
    obj["m_oldOrigin"] = p0
    obj["m_flags"] = ALIGN_FLAGS
    obj["m_dimLockedForLabeling"] = False
    if plane_first:
        obj["m_witnessRefs"] = [
            _witness(refplane_id, ends=plane_ends,
                     ref_length=_seg_length(plane_ends), wid=0, end_idx=0,
                     constr_flags=4),
            _witness(curve_id, ends=curve_ends,
                     ref_length=_seg_length(curve_ends), wid=1, end_idx=0,
                     constr_flags=2)]
    else:
        obj["m_witnessRefs"] = [
            _witness(curve_id, ends=curve_ends,
                     ref_length=_seg_length(curve_ends), wid=0, end_idx=0,
                     constr_flags=8),
            _witness(refplane_id, ends=plane_ends,
                     ref_length=_seg_length(plane_ends), wid=1, end_idx=1,
                     constr_flags=1)]
    cd = [float(c) for c in constr_dir]
    if dim_line_dir is None:
        # the drawn token runs along the plane (perpendicular to constrDir)
        dim_line_dir = [-cd[1], cd[0], 0.0]
    obj["m_pDimLine"] = _dim_line(p0, dim_line_dir)
    obj["m_orientType"] = 0
    obj["m_constrDir"] = cd
    G.assign_pids(obj)                      # GLine -> pid 3 [V donor]
    dele = sorted({family_id, int(style_id), int(view_id), int(refplane_id),
                   int(sketch_id), int(curve_id), int(elem_id)} - {-1})
    appearance = sorted({int(style_id), int(refplane_id), int(sketch_id),
                         int(curve_id)} - {-1})
    hdr = element_header("Alignment", category=CAT_ALIGNMENTS, deletion=dele,
                         regen_only=([int(sketch_plane_id)]
                                     if sketch_plane_id >= 0 else []),
                         appearance=appearance,
                         flags=HDR_FLAGS, visible_view_flags=HDR_VISIBLE,
                         family_id=family_id, owner_view=view_id)
    return SkelElement(elem_id, "Alignment", hdr, obj, None, kind="alignment",
                       owner_id=int(sketch_id),
                       refs={"family": family_id, "sketch": int(sketch_id),
                             "curve": int(curve_id), "refplane": int(refplane_id),
                             "style": int(style_id)},
                       notes=list(notes or []))


def new_labeled_dim(elem_id: int, ctx_or_family_id: Any, *, param_id: int,
                    ref_a_id: int, ref_b_id: int, style_id: int, value: float,
                    ref_a_ends: Tuple[Vec, Vec], ref_b_ends: Tuple[Vec, Vec],
                    ref_pnts: Tuple[Vec, Vec], seg_origin: Vec,
                    dim_line_origin: Vec, dim_line_dir: Vec,
                    old_origin: Optional[Vec] = None,
                    view_id: int = -1, sketch_plane_id: int = -1,
                    seg_flags: int = 1, notes=None) -> SkelElement:
    """A LABELED ``LinearDimString`` driving family parameter ``param_id``
    between ``RefPlane`` witnesses ``ref_a_id`` / ``ref_b_id`` -- donor
    2427's shape: one segment (``m_paramId`` = the parameter element id,
    ``m_lockedValue`` = ``value``), ``m_flags`` 12,
    ``m_dimLockedForLabeling`` True, ``ContinuousLinearDimState``.
    ``seg_flags``: donor Width dim carries 1, its second dim 0."""
    family_id = _family_id_of(ctx_or_family_id)
    obj = blank_object("LinearDimString")
    _dimension_common(obj, elem_id, family_id, view_id, style_id)
    obj["m_cellList"] = None
    obj["m_refPnts"] = [[float(c) for c in ref_pnts[0]],
                        [float(c) for c in ref_pnts[1]]]
    obj["m_ArrSegInfo"] = [_seg_info(locked_value=float(value),
                                     origin=seg_origin, param_id=int(param_id),
                                     flags=int(seg_flags), seg_value=float(value))]
    obj["m_oldOrigin"] = [float(c) for c in (old_origin if old_origin is not None
                                             else dim_line_origin)]
    obj["m_flags"] = DIM_FLAGS
    obj["m_dimLockedForLabeling"] = True
    obj["m_witnessRefs"] = [
        _witness(ref_a_id, ends=ref_a_ends, ref_length=_seg_length(ref_a_ends),
                 wid=0, end_idx=0, constr_flags=0),
        _witness(ref_b_id, ends=ref_b_ends, ref_length=_seg_length(ref_b_ends),
                 wid=1, end_idx=0, constr_flags=0)]
    obj["m_pDimLine"] = _dim_line(dim_line_origin, dim_line_dir)
    obj["m_orientType"] = 1
    obj["m_dontEditRefs"] = False
    obj["m_pTypeState"] = {"ptr_class": "ContinuousLinearDimState", "pid": -1,
                           "value": {"m_pDim": {"weakref": 2}}}
    G.assign_pids(obj)                      # GLine -> pid 3 [V donor]
    dele = sorted({family_id, int(style_id), int(view_id), int(ref_a_id),
                   int(ref_b_id), int(elem_id), int(param_id)} - {-1})
    appearance = sorted({int(style_id), int(ref_a_id), int(ref_b_id)}
                        | ({int(sketch_plane_id)} if sketch_plane_id >= 0
                           else set()))
    hdr = element_header("LinearDimString", category=CAT_DIMENSIONS,
                         deletion=dele,
                         regen_only=([int(sketch_plane_id)]
                                     if sketch_plane_id >= 0 else []),
                         appearance=appearance,
                         flags=HDR_FLAGS, visible_view_flags=HDR_VISIBLE,
                         family_id=family_id, owner_view=view_id)
    return SkelElement(elem_id, "LinearDimString", hdr, obj, None,
                       kind="labeled_dim",
                       owner_id=family_id,
                       refs={"family": family_id, "param": int(param_id),
                             "ref_a": int(ref_a_id), "ref_b": int(ref_b_id),
                             "style": int(style_id)},
                       notes=list(notes or []))


# ---------------------------------------------------------------------------
# the panelboard wiring pass
# ---------------------------------------------------------------------------

def _sketch_lines(sk: SkelElement) -> List[Tuple[int, Tuple[float, float],
                                                 Tuple[float, float]]]:
    """[(curve_id, (x1,y1), (x2,y2))] from the sketch's solver records."""
    out = []
    for rec in sk.obj.get("m_elemRecs") or []:
        v = rec.get("value") or {}
        vals = [float((p.get("value") or {}).get("m_val", 0.0))
                for p in v.get("m_params") or []]
        if len(vals) != 4:
            raise ValueError("param_drive: sketch solver record is not a "
                             "4-param line segment")
        out.append((int(v.get("m_objId", -1)), (vals[0], vals[1]),
                    (vals[2], vals[3])))
    return out


def _classify_rect(lines) -> Dict[str, Tuple[int, Tuple[float, float],
                                             Tuple[float, float]]]:
    """Map the 4 profile lines to top/bottom/left/right by orientation."""
    horiz = [l for l in lines if abs(l[2][1] - l[1][1]) <= abs(l[2][0] - l[1][0])]
    vert = [l for l in lines if l not in horiz]
    if len(horiz) != 2 or len(vert) != 2:
        raise ValueError("param_drive: profile is not an axis-aligned rectangle")
    horiz.sort(key=lambda l: (l[1][1] + l[2][1]) / 2.0)
    vert.sort(key=lambda l: (l[1][0] + l[2][0]) / 2.0)
    return {"bottom": horiz[0], "top": horiz[1],
            "left": vert[0], "right": vert[1]}


def wire_panelboard_drive(doc) -> Dict[str, Any]:
    """Wire the parametric drive chain into a PANELBOARD ``FamilyDoc``
    (call AFTER the box form exists, BEFORE ``finalize``):

    4 side ``RefPlane`` datums at x = +-Width/2 and y = +-Height/2, an
    ``Alignment`` locking each profile ``CurveElem`` to its side plane,
    and two LABELED ``LinearDimString`` dims (Width between left/right,
    Height between bottom/top) at the current type's parameter values.
    The ``VarSketch`` registers the alignments (``m_dimIds`` /
    ``m_dimData`` + its header deletion list -- donor law; CurveElem
    headers stay untouched).  Returns a small summary dict.
    """
    if doc.finalized:
        raise RuntimeError("param_drive: document is finalized")
    sketches = doc.by_class("VarSketch")
    if not sketches:
        raise ValueError("param_drive: no VarSketch in the document")
    sk = sketches[0]
    fam_id = doc.self_family.elem_id
    style_id = int(doc.dim_style_id)
    if style_id < 0:
        raise ValueError("param_drive: document has no dimension style")
    view_id = int(doc.plan_view_id)
    lines = _sketch_lines(sk)
    if len(lines) != 4:
        raise ValueError(f"param_drive: expected a 4-line profile, got {len(lines)}")
    rect = _classify_rect(lines)
    # the two sketch planes: the box form's (regen parent of the alignments)
    # and the plan view's (regen parent of the labeled dims) [V donor]
    geo_sp = next((e for e in doc.by_class("SketchPlane")
                   if int(e.obj.get("m_userId", -1)) == sk.elem_id), None)
    geo_sp_id = geo_sp.elem_id if geo_sp is not None else -1
    view_sp = next((e for e in doc.views if e.class_name == "SketchPlane"), None)
    view_sp_id = view_sp.elem_id if view_sp is not None else geo_sp_id
    # parameters + current values (the current type row, internal feet)
    try:
        w_pe, h_pe = doc.params["Width"], doc.params["Height"]
    except KeyError as e:
        raise ValueError(f"param_drive: missing family parameter {e}") from None
    vals = doc.types[doc.current_type][1] if doc.types else {}
    W = float(vals.get(w_pe.elem_id, 0.0))
    H = float(vals.get(h_pe.elem_id, 0.0))
    if W <= 0.0 or H <= 0.0:
        # fall back to the drawn profile (single source of truth = geometry)
        W = abs(rect["right"][1][0] - rect["left"][1][0])
        H = abs(rect["top"][1][1] - rect["bottom"][1][1])
    # half-length of the drawn datum lines: mimic the center planes'
    P = 5.0
    if doc.refplanes:
        c = doc.refplanes[0]
        P = _seg_length((c.obj["m_freeEnd"], c.obj["m_bubbleEnd"])) / 2.0 or 5.0
    env = ((-P, -2.0), (P, 10.0))

    def _side_plane(name, at, vertical):
        if vertical:
            free, bubble = (at, -P, 0.0), (at, P, 0.0)
        else:
            free, bubble = (-P, at, 0.0), (P, at, 0.0)
        rp = new_reference_plane(_alloc(doc.ids), fam_id, name=name,
                                 ref_name="weak", free_end=free,
                                 bubble_end=bubble, normal=(0.0, 0.0, 1.0),
                                 gen_view_id=view_id, extent=env)
        doc.refplanes.append(rp)
        doc.add(rp)
        return rp

    left = _side_plane("", -W / 2.0, True)
    right = _side_plane("", W / 2.0, True)
    bottom = _side_plane("", -H / 2.0, False)
    top = _side_plane("", H / 2.0, False)

    def _p3(p):
        return (float(p[0]), float(p[1]), 0.0)

    def _plane_ends(rp):
        return (_p3(rp.obj["m_freeEnd"]), _p3(rp.obj["m_bubbleEnd"]))

    # 4 alignments in the donor's creation order [bottom, right, top, left]
    # with the donor's witness-order / constrDir / dimData patterns [V 2438-41]
    plan = [
        ("bottom", bottom, (0.0, -1.0, 0.0), False, 1),
        ("right", right, (1.0, 0.0, 0.0), False, 0),
        ("top", top, (0.0, 1.0, 0.0), True, 1),
        ("left", left, (-1.0, 0.0, 0.0), True, 0),
    ]
    aligns: List[SkelElement] = []
    dim_data: List[Tuple[int, int]] = []
    for side, rp, cdir, plane_first, second in plan:
        cid, a, b = rect[side]
        mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, 0.0)
        al = new_alignment(_alloc(doc.ids), fam_id, sketch_id=sk.elem_id,
                           curve_id=cid, refplane_id=rp.elem_id,
                           style_id=style_id, constr_dir=cdir, origin=mid,
                           curve_ends=(_p3(a), _p3(b)), plane_ends=_plane_ends(rp),
                           view_id=view_id, sketch_plane_id=geo_sp_id,
                           plane_first=plane_first,
                           ref_pnts=((mid, mid) if not plane_first
                                     else (_p3(a), _p3(b))))
        aligns.append(al)
        dim_data.append((al.elem_id, second))
        doc.add(al)
    # register on the sketch: m_dimIds / m_dimData + the header deletion
    sk.obj["m_dimIds"] = [a.elem_id for a in aligns]
    sk.obj["m_dimData"] = [{"first": i, "second": s} for i, s in dim_data]
    par = sk.header["m_parents"]["value"]
    par["m_deletion"] = sorted(set(par["m_deletion"])
                               | {a.elem_id for a in aligns})

    # 2 labeled dims: Width between left/right, Height between bottom/top
    y_ref = -(P - REFPNT_INSET)
    y_line = y_ref - DIMLINE_STEP
    width_dim = new_labeled_dim(
        _alloc(doc.ids), fam_id, param_id=w_pe.elem_id,
        ref_a_id=left.elem_id, ref_b_id=right.elem_id, style_id=style_id,
        value=W, ref_a_ends=_plane_ends(left), ref_b_ends=_plane_ends(right),
        ref_pnts=((-W / 2.0, y_ref, 0.0), (W / 2.0, y_ref, 0.0)),
        seg_origin=(0.0, y_line, 0.0), dim_line_origin=(0.0, y_line, 0.0),
        dim_line_dir=(1.0, 0.0, 0.0), view_id=view_id,
        sketch_plane_id=view_sp_id, seg_flags=1)
    doc.add(width_dim)
    x_ref = -(P - REFPNT_INSET)
    x_line = x_ref + DIMLINE_STEP
    height_dim = new_labeled_dim(
        _alloc(doc.ids), fam_id, param_id=h_pe.elem_id,
        ref_a_id=bottom.elem_id, ref_b_id=top.elem_id, style_id=style_id,
        value=H, ref_a_ends=_plane_ends(bottom), ref_b_ends=_plane_ends(top),
        ref_pnts=((x_ref, -H / 2.0, 0.0), (x_ref, H / 2.0, 0.0)),
        seg_origin=(x_line, 0.0, 0.0), dim_line_origin=(x_line, 0.0, 0.0),
        dim_line_dir=(0.0, 1.0, 0.0), view_id=view_id,
        sketch_plane_id=view_sp_id, seg_flags=0)
    doc.add(height_dim)
    doc.notes.append(
        "parametric drive wired (issue #372): 4 side RefPlanes, 4 Alignments "
        "(sketch lines locked to the planes, registered in VarSketch.m_dimIds/"
        "m_dimData), labeled Width/Height LinearDimStrings at the current "
        "type values -- donor-shaped (2427/2438 law)")
    return {"side_planes": [left.elem_id, right.elem_id, bottom.elem_id,
                            top.elem_id],
            "alignments": [a.elem_id for a in aligns],
            "dims": {"Width": width_dim.elem_id, "Height": height_dim.elem_id},
            "values_ft": {"Width": W, "Height": H}}

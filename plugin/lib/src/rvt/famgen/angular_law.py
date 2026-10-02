"""rvt.famgen.angular_law -- LOCKED ANGULAR DIMENSIONS, and the Revit-born recipe
that keeps a regular hexagon regular while one parameter resizes it across flats
(issue #948; the follow-up to the #940 hexagon census).

THE CENSUS (the owner's 421-family reference library, #836 / #865 -- read only as
a development instrument, quarantined, never copied; counts and field facts only):

* **387 ``AngularDim``s** in 62 files (74 in host documents, 313 in nested ones).
  Every one has exactly TWO witnesses and ONE segment (387 / 387) -- there is no
  multi-reference angular EQ anywhere in the library.  ``m_dimVersion`` 6
  (387 / 387); ``m_flags`` 12 (377) or 13 (10); 357 are sketch members
  (``SketchMembership``), owned by no view (object and header owner view -1,
  357 / 357), listed in their sketch's ``m_dimIds`` (357 / 357) and never in its
  ``m_dimData`` (0 / 357); header category -2000260, flags 10, visible-view
  flags -1 (379) / -4225 (8).  Segments: 203 LOCKED (``m_flags`` 1), 184 free
  (0); 163 labelled.  Locked values: 60 deg 160, 90 deg 21, 45 deg 17, 10 deg 3,
  3 deg 2.  Witnesses: ``GeomSegInPlaneRef`` 387 / 387; two sketch curves 246,
  curve + reference plane 90.  The arc token is a ``GArc`` (pid 3, GInfo flags
  524292, endParams [0, 0]) 387 / 387.
* **The hexagon recipe** -- every labelled hexagon (32, in 23 files; 7 distinct
  families, #940) carries the SAME eleven constraints, all sketch members of the
  hexagon's own sketch, all owned by no view (32 / 32 each).  With the hexagon's
  flats square to y, its lines CCW and named H0..H5 from the bottom-right slant
  (H2 = top flat Ft, H3 = S', H4 = S, H5 = bottom flat Fb):

  - five LOCKED 60-degree ``AngularDim``s across consecutive sides
    (Fb, H0) (H0, H1) (H1, Ft) (Ft, S') (S', S) -- the sixth angle (S, Fb)
    follows by closure.  (The #940 record called these "EQ"; they are locks:
    one segment, ``m_flags`` 1, value pi / 3, 160 / 160.)
  - three EQ ``LinearDimString``s (flags 140, segments flags 2):
    Ft | Ppar | Fb (the flats symmetric about the centre plane parallel to them),
    Fb.start | Pperp | Fb.end and S'.start | Pperp | Ft.start (each flat's
    vertices symmetric about the perpendicular centre plane), the plane witness
    ``m_constrFlags`` 16;
  - two LABELLED ``LinearDimString``s of ONE instance formula parameter (value =
    across flats / 2): Fb to Ppar, and S to the ORIGIN POINT (a
    ``CurveXCurveInPlaneRef``: Pperp crossed with Ppar), measured along S's
    normal;
  - one zero-length dimension pinning the S / S' corner on Ppar, drawn in a
    SECRET internal dimension style (category -2000261, ``m_flags`` 28) whose
    style element brings its own category / font / leader elements.
  - The sketch: ``m_highResidualTol`` True (112 / 112 sketches with an angular
    dimension), one horizontal ``VarSketchHorVerConstrObj`` on Ft only plus the
    six point-point joins (32 / 32), ``m_angleCoef`` = the line's length on
    angular-witnessed lines (348 / 358), every curve's GInfo bit 0x80000
    (192 / 192), and ``m_regenOnly`` = [Level, Ppar, Pperp] (32 / 32).
  - Every sketch-member dimension is owned (``ElemTable``) by its sketch:
    26,335 / 26,335 linear, 66 / 66 angular, 2,666 / 2,666 alignments in host
    documents.

WHAT THIS MODULE AUTHORS.  :func:`wire_hexagon_drive` writes that recipe on a
hexagonal sketch of OUR OWN generated family, with ONE stated substitution: the
secret-style corner pin is replaced by a second labelled dimension of the same
parameter, from S' to the origin point (the exact shape of the S one).  Both
fix the one remaining degree of freedom (with S and S' each at across-flats / 2
from the centre at fixed angles, their corner lies on Ppar); the substitution
avoids authoring a secret dimension style constellation the census only saw
inside Autodesk-born files.  So the hexagon carries 11 constraints, 10 of them
the born shape field for field.

Every check runs before the first mutation (all-or-nothing, as
``drive_law.wire_linear_drive``).  Nothing here claims Revit flexes the
hexagon: that is a desktop verdict (hard rule 4), and none exists.
"""
from __future__ import annotations

import collections
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..genesis.types import blank_object

#: AngularDim / LinearDimString header category (Dimensions) [census 387 / 387]
CAT_DIMENSIONS = -2000260
#: m_flags of an AngularDim (377 / 387) and of a labelled sketch dimension
DIM_FLAGS = 12
#: m_flags of an EQ LinearDimString [census 96 / 96 hexagon EQs]
EQ_DIM_FLAGS = 140
#: segment flags: bit 0 = locked, bit 1 = equality [census]
SEG_LOCKED = 1
SEG_EQ = 2
#: the EQ dimension's plane witness constraint flags [census 96 / 96]
EQ_PLANE_CONSTR_FLAGS = 16
#: header visible-view flags: sketch-member angular (379 / 387), linear (192 / 192)
VIS_ANGULAR = -1
VIS_LINEAR = -4225
#: m_dimVersion on born dimensions
BORN_DIM_VERSION = 6
#: VarSketch.m_dimData "second" per hexagon role [census 32 / 32 each]
DIM_DATA = {"eq_flats": 3, "eq_bottom_ends": 0, "eq_top_ends": 0, "label": 3}


class AngularLawError(ValueError):
    """The hexagon drive cannot be wired (the document is left untouched)."""


# ---------------------------------------------------------------------------
# small geometry
# ---------------------------------------------------------------------------

def _p3(p) -> Tuple[float, float, float]:
    return (float(p[0]), float(p[1]), 0.0)


def _unit(v) -> Tuple[float, float]:
    ln = math.hypot(v[0], v[1])
    return (v[0] / ln, v[1] / ln)


def _close(p, q, tol: float = 1e-9) -> bool:
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


#: the hexagon roles in the census order (H0 .. H5)
ROLES = ("Q0", "Q1", "Ft", "Sp", "S", "Fb")


def hexagon_roles(sk) -> Dict[str, Any]:
    """The roles of a hexagonal sketch's six lines, or :class:`AngularLawError`.

    The sketch must be the census shape: a REGULAR hexagon centred on the sketch
    origin, two flats square to y (vertices at 0, 60, ..., 300 degrees), its
    lines chained end-to-start counter-clockwise.  Returns ``{role: (curve id,
    start, end)}`` plus ``"a"`` (across flats / 2) and ``"R"`` (the side = the
    centre-to-corner radius)."""
    from . import param_drive as PD
    try:
        lines = PD._sketch_lines(sk)
    except ValueError as exc:
        raise AngularLawError(f"angular_law: {exc}") from None
    if len(lines) != 6:
        raise AngularLawError(f"angular_law: sketch {sk.elem_id} has {len(lines)} lines, "
                              "not a hexagon's six")
    for i, (_c, _a, b) in enumerate(lines):
        if not _close(b, lines[(i + 1) % 6][1]):
            raise AngularLawError(f"angular_law: sketch {sk.elem_id}'s lines are not "
                                  "chained end to start")
    area = sum(a[0] * b[1] - b[0] * a[1] for _c, a, b in lines)
    if area <= 0.0:
        raise AngularLawError(f"angular_law: sketch {sk.elem_id} runs clockwise")
    R = math.dist(lines[0][1], lines[0][2])
    if not (math.isfinite(R) and R > 1e-6):
        raise AngularLawError("angular_law: degenerate hexagon")
    want = [(R * math.cos(math.radians(k * 60)), R * math.sin(math.radians(k * 60)))
            for k in range(6)]
    starts = [a for _c, a, _b in lines]
    if not all(any(_close(s, w, 1e-9 * max(1.0, R) + 1e-12) for s in starts) for w in want):
        raise AngularLawError(f"angular_law: sketch {sk.elem_id} is not a regular hexagon "
                              "centred on the origin with its flats square to y")
    a = R * math.sqrt(3.0) / 2.0
    fb = [i for i, (_c, p, q) in enumerate(lines)
          if abs(p[1] + a) <= 1e-9 and abs(q[1] + a) <= 1e-9]
    if len(fb) != 1:
        raise AngularLawError("angular_law: no single bottom flat")
    k = fb[0]
    out: Dict[str, Any] = {}
    for j, role in enumerate(ROLES):
        out[role] = lines[(k + 1 + j) % 6]
    out["a"], out["R"] = a, R
    return out


# ---------------------------------------------------------------------------
# witnesses
# ---------------------------------------------------------------------------

def _w_line(cid: int, ends, wid: int, end_idx: int, constr_flags: int = 0,
            sub_tag: int = -1) -> dict:
    from . import param_drive as PD
    e = (_p3(ends[0]), _p3(ends[1]))
    w = PD._witness(cid, ends=e, ref_length=PD._seg_length(e), wid=wid,
                    end_idx=end_idx, constr_flags=constr_flags)
    w["m_pWitnessRef"]["value"]["m_geomRef"]["m_subTag"] = int(sub_tag)
    return w


def _w_vertex(cid: int, pt, sub_tag: int, wid: int, end_idx: int) -> dict:
    return _w_line(cid, (pt, pt), wid, end_idx, sub_tag=sub_tag)


def _w_cross(plane_id: int, other_id: int, wid: int) -> dict:
    """The intersection of two reference planes (the origin point here): a
    ``CurveXCurveInPlaneRef`` whose ``m_geomRef`` is the first plane and
    ``m_otherGeomRef`` the second; ``m_idx`` / ``m_orientation`` 0 [32 / 32]."""
    w = _w_line(plane_id, ((0.0, 0.0), (0.0, 0.0)), wid, 0)
    gref = dict(w["m_pWitnessRef"]["value"]["m_geomRef"])
    other = dict(gref)
    other["m_intermediateTags"] = []
    other["m_foreignElemIdRef"] = {"m_id64": -1}
    other["m_elemId"] = int(other_id)
    w["m_pWitnessRef"] = {"ptr_class": "CurveXCurveInPlaneRef", "pid": -1, "value": {
        "m_geomRef": gref, "m_sideOfArc": False, "m_otherGeomRef": other,
        "m_idx": 0, "m_orientation": 0}}
    return w


def _no_text(segs: List[dict]) -> None:
    for s in segs:
        for v in s.get("m_values") or []:
            v["m_oTextFields"] = None


def _eq_arr(eqn: int, id1: int) -> dict:
    from . import param_drive as PD
    arr = PD._equality_arr()
    s = arr["m_arr"][0]
    s["m_equalitySegNumber"] = int(eqn)
    s["m_id"] = {"m_id1": int(id1), "m_id2": -1}
    return arr


def _sketch_member(sk_id: int) -> dict:
    return {"ptr_class": "CellList", "pid": -1, "value": {
        "m_cells": [{"ptr_class": "SketchMembership", "pid": -1,
                     "value": {"m_groupId": int(sk_id)}}]}}


def _targets(obj: dict) -> List[int]:
    out = []
    for w in obj["m_witnessRefs"]:
        v = w["m_pWitnessRef"]["value"]
        for g in (v.get("m_geomRef"), v.get("m_otherGeomRef")):
            if isinstance(g, dict) and int(g["m_elemId"]) not in out:
                out.append(int(g["m_elemId"]))
    return out


def _header(cls: str, obj: dict, eid: int, *, fam: int, style: int, sk: int,
            skp: int, param: Optional[int], vis: int) -> dict:
    from .skeleton import element_header
    tg = _targets(obj)
    dele = sorted({fam, style, sk, eid, *tg} | ({param} if param is not None else set()))
    app = sorted({style, sk, *tg})
    return element_header(cls, category=CAT_DIMENSIONS, deletion=dele,
                          regen_only=[skp], appearance=app, flags=10,
                          visible_view_flags=vis, family_id=fam, owner_view=-1)


# ---------------------------------------------------------------------------
# constructors
# ---------------------------------------------------------------------------

def new_angular_lock(eid: int, *, fam: int, style: int, sk_id: int, skp: int,
                     line_a, line_b, radius: float):
    """A LOCKED ``AngularDim`` between sketch lines ``line_a`` and ``line_b``
    (each ``(curve id, start, end)``, ``line_a`` ending where ``line_b``
    starts) -- the census shape: witnesses A (its ends in order, endIdx 0) and B
    (its ends reversed, endIdx 1); one segment, ``m_flags`` 1, value = the
    angle between A's way back from the vertex and B's way back, ``m_refPnts``
    on those two rays at ``radius``, the text on their bisector."""
    from . import param_drive as PD
    from . import geometry as G
    from .skeleton import SkelElement
    ca, a0, a1 = line_a
    cb, b0, b1 = line_b
    if not _close(a1, b0):
        raise AngularLawError("angular_law: the two lines do not meet end to start")
    V = a1
    u = _unit((a0[0] - V[0], a0[1] - V[1]))
    w = _unit((V[0] - b1[0], V[1] - b1[1]))
    ang = math.acos(max(-1.0, min(1.0, u[0] * w[0] + u[1] * w[1])))
    bis = _unit((u[0] + w[0], u[1] + w[1]))
    r = float(radius)
    org = (V[0] + r * bis[0], V[1] + r * bis[1], 0.0)
    obj = blank_object("AngularDim")
    keys = set(obj)
    PD._dimension_common(obj, eid, fam, -1, style)
    for k in [k for k in obj if k not in keys]:
        del obj[k]                     # the LinearDimString-only fields
    obj["m_cellList"] = _sketch_member(sk_id)
    obj["m_refPnts"] = [[V[0] + r * u[0], V[1] + r * u[1], 0.0],
                        [V[0] + r * w[0], V[1] + r * w[1], 0.0]]
    seg = PD._seg_info(locked_value=ang, origin=org, param_id=-1, flags=SEG_LOCKED,
                       seg_value=ang, id1=0, id2=1)
    obj["m_ArrSegInfo"] = [seg]
    _no_text(obj["m_ArrSegInfo"])
    obj["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"] = _eq_arr(1, 2)
    obj["m_oldOrigin"] = list(org)
    obj["m_lastDimSegInfoId"] = {"m_id1": 2, "m_id2": -1}
    obj["m_dimVersion"] = BORN_DIM_VERSION
    obj["m_flags"] = DIM_FLAGS
    obj["m_dimLockedForLabeling"] = False
    obj["m_witnessRefs"] = [_w_line(ca, (a0, a1), 0, 0), _w_line(cb, (b1, b0), 1, 1)]
    obj["m_lastUsedId"] = {"m_id": 1}
    arc = blank_object("GArc")
    arc["m_GInfo"] = G.ginfo(category=-1, tag=-1, control_command=0,
                             flags=PD.GLINE_DIM_FLAGS)
    arc["m_endParams"] = [0.0, 0.0]
    arc["m_xVec"] = [1.0, 0.0, 0.0]
    arc["m_yVec"] = [0.0, 1.0, 0.0]
    arc["m_radius"] = r
    arc["m_center"] = list(_p3(V))
    arc["m_bFilled"] = False
    obj["m_pDimArc"] = {"ptr_class": "GArc", "pid": -1, "value": arc}
    obj["m_origin"] = list(org)
    obj["m_2ArcAngle"] = False
    obj["m_originIsSet"] = True
    obj["m_sectorHasBeenSet"] = True
    obj["m_parallelNonTangentRefs"] = False
    obj["m_use360ArcDimFor0"] = False
    obj["m_enableZeroLength"] = False
    G.assign_pids(obj)                 # GArc -> pid 3 [387 / 387]
    hdr = _header("AngularDim", obj, eid, fam=fam, style=style, sk=sk_id, skp=skp,
                  param=None, vis=VIS_ANGULAR)
    return SkelElement(eid, "AngularDim", hdr, obj, None, kind="angular_lock",
                       owner_id=int(sk_id),
                       refs={"family": fam, "sketch": int(sk_id),
                             "curves": [int(ca), int(cb)], "style": style})


def new_sketch_dim(eid: int, *, fam: int, style: int, sk_id: int, skp: int,
                   witnesses: List[dict], ref_pnts: Sequence, values: Sequence[float],
                   seg_origins: Sequence, line_origin, line_dir,
                   param_id: Optional[int] = None):
    """A sketch-member ``LinearDimString`` over ``witnesses`` -- LABELLED with
    ``param_id`` (one segment, flags 0, ``m_flags`` 12) or, with three
    witnesses, an EQ dimension (two segments flags 2, ``m_flags`` 140), the
    census shapes of the hexagon recipe."""
    from . import param_drive as PD
    from . import geometry as G
    from .skeleton import SkelElement
    n = len(witnesses)
    eq = param_id is None
    if (eq and n != 3) or (not eq and n != 2) or len(values) != n - 1:
        raise AngularLawError("angular_law: a sketch dimension is a 2-witness label or "
                              "a 3-witness EQ")
    obj = PD.new_labeled_dim(
        eid, fam, param_id=(-1 if eq else int(param_id)), ref_a_id=0, ref_b_id=0,
        style_id=style, value=float(values[0]), ref_a_ends=((0, 0, 0), (0, 0, 0)),
        ref_b_ends=((0, 0, 0), (0, 0, 0)), ref_pnts=(ref_pnts[0], ref_pnts[-1]),
        seg_origin=seg_origins[0], dim_line_origin=line_origin,
        dim_line_dir=line_dir, view_id=-1, sketch_plane_id=skp, seg_flags=0).obj
    obj["m_cellList"] = _sketch_member(sk_id)
    obj["m_witnessRefs"] = list(witnesses)
    obj["m_refPnts"] = [list(_p3(p)) for p in ref_pnts]
    segs = []
    for i, (v, o) in enumerate(zip(values, seg_origins)):
        segs.append(PD._seg_info(locked_value=float(v), origin=_p3(o),
                                 param_id=(-1 if eq else int(param_id)),
                                 flags=(SEG_EQ if eq else 0), seg_value=float(v),
                                 id1=i, id2=i + 1))
    _no_text(segs)
    obj["m_ArrSegInfo"] = segs
    obj["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"] = _eq_arr(n - 1, n)
    obj["m_lastDimSegInfoId"] = {"m_id1": n, "m_id2": -1}
    obj["m_lastUsedId"] = {"m_id": n - 1}
    obj["m_flags"] = EQ_DIM_FLAGS if eq else DIM_FLAGS
    obj["m_dimLockedForLabeling"] = not eq
    obj["m_dimVersion"] = BORN_DIM_VERSION
    G.assign_pids(obj)
    hdr = _header("LinearDimString", obj, eid, fam=fam, style=style, sk=sk_id, skp=skp,
                  param=(None if eq else int(param_id)), vis=VIS_LINEAR)
    return SkelElement(eid, "LinearDimString", hdr, obj, None,
                       kind=("sketch_eq_dim" if eq else "sketch_labeled_dim"),
                       owner_id=int(sk_id),
                       refs={"family": fam, "sketch": int(sk_id), "style": style,
                             **({} if eq else {"param": int(param_id)})})


# ---------------------------------------------------------------------------
# the sketch's own solver state
# ---------------------------------------------------------------------------

def _renumber(obj: dict) -> None:
    """``geometry.assign_pids`` on ``obj``, keeping every weak reference
    pointing at the SAME owned object it named before."""
    from . import geometry as G
    before: Dict[int, int] = {}

    def collect(v, table):
        if isinstance(v, dict):
            if "ptr_class" in v and isinstance(v.get("pid"), int) and v["pid"] >= 3:
                table[v["pid"]] = id(v)
            for x in v.values():
                collect(x, table)
        elif isinstance(v, list):
            for x in v:
                collect(x, table)
    collect(obj, before)
    G.assign_pids(obj)
    after: Dict[int, int] = {}
    collect(obj, after)
    by_obj = {o: p for p, o in after.items()}

    def fix(v):
        if isinstance(v, dict):
            if set(v) == {"weakref"} and v["weakref"] in before:
                v["weakref"] = by_obj[before[v["weakref"]]]
                return
            for x in v.values():
                fix(x)
        elif isinstance(v, list):
            for x in v:
                fix(x)
    fix(obj)


def _born_solver_state(sk, roles: Dict[str, Any]) -> Dict[str, int]:
    """The hexagon sketch's solver records in the census form: the
    horizontal/vertical constraint on the top flat ONLY (the generic sketch
    writer emits one on every axis-parallel line since #952 -- here the
    bottom flat's is dropped too, as born hexagons carry one), ``m_angleCoef``
    = each line's length, and
    ``m_highResidualTol`` True."""
    recs = sk.obj.get("m_elemRecs") or []
    pid_line = {r["pid"]: int(r["value"]["m_objId"]) for r in recs}
    ft = roles["Ft"][0]
    kept, dropped, ft_hv = [], 0, 0
    for r in sk.obj.get("m_constrRecs") or []:
        if r.get("ptr_class") == "VarSketchHorVerConstrObj":
            el = [pid_line.get(x.get("weakref")) for x in r["value"]["m_constrElems"]]
            if el == [ft] and not ft_hv:
                r["value"]["m_hor"] = True
                ft_hv += 1
                kept.append(r)
            else:
                dropped += 1
            continue
        kept.append(r)
    if not ft_hv:
        ft_pid = next(p for p, c in pid_line.items() if c == ft)
        at = next((i for i, r in enumerate(kept) if r.get("ptr_class") == "VarSketchPPConstrObj"
                   and pid_line.get(r["value"]["m_constrElems"][0]["weakref"]) == ft), len(kept) - 1)
        kept.insert(at + 1, {"ptr_class": "VarSketchHorVerConstrObj", "pid": -1, "value": {
            "m_params": [], "m_pSketch": {"weakref": 2}, "m_objId": -1,
            "m_constrElems": [{"weakref": ft_pid}], "m_constrSubTypes": [0],
            "m_priorityLevel": 3, "m_hor": True}})
    # census order (32 / 32): per line in solver order, its join to the line
    # before it, then its join closing the loop, then -- on Ft -- the HV
    order = [int(r["value"]["m_objId"]) for r in recs]
    pos = {p: order.index(c) for p, c in pid_line.items()}

    def key(r):
        el = [pos.get(x.get("weakref"), 99) for x in r["value"]["m_constrElems"]]
        if r.get("ptr_class") == "VarSketchHorVerConstrObj":
            return (el[0], 2, 0)
        return (el[0], 0 if len(el) > 1 and el[1] == el[0] - 1 else 1, el[-1])
    kept.sort(key=key)
    sk.obj["m_constrRecs"] = kept
    for r in recs:
        p = [float(q["value"]["m_val"]) for q in r["value"]["m_params"]]
        r["value"]["m_angleCoef"] = math.hypot(p[2] - p[0], p[3] - p[1])
    sk.obj["m_highResidualTol"] = True
    _renumber(sk.obj)
    return {"hv_dropped": dropped}


# ---------------------------------------------------------------------------
# the hexagon drive
# ---------------------------------------------------------------------------

def _locked_curves(doc) -> set:
    out = set()
    for cls in ("Alignment", "LinearDimString", "AngularDim"):
        for el in doc.by_class(cls):
            out.update(_targets(el.obj))
    return out


def wire_hexagon_drive(doc, *, sketch, caption: str, half_caption: str) -> Dict[str, Any]:
    """Make ``caption`` (across flats) drive the regular hexagon of ``sketch``.

    ``half_caption`` = the parameter the dimensions carry: a LENGTH parameter
    whose formula is ``<caption> / 2`` (born: one instance formula parameter,
    32 / 32), its value on every type = half the hexagon's across flats.  Writes
    the census recipe (module docstring) -- 5 locked 60-degree angles, 3 EQs, 3
    labels (the corner pin substituted, stated) -- and the sketch's solver
    state.  Call BEFORE ``finalize``.  All-or-nothing: every check first."""
    from .drive_law import drivable_spec, origin_centre_plane
    from .skeleton import _alloc
    if doc.finalized:
        raise AngularLawError("angular_law: document is finalized")
    if not any(e is sketch for e in doc.elements) or sketch.class_name != "VarSketch":
        raise AngularLawError("angular_law: the sketch is not a VarSketch of this document")
    for c in (caption, half_caption):
        if c not in doc.params:
            raise AngularLawError(f"angular_law: no parameter {c!r}")
        if not drivable_spec(doc.params[c]):
            raise AngularLawError(f"angular_law: {c} is not a length parameter")
    half = doc.params[half_caption]
    formula = " ".join(str(half.refs.get("formula") or "").split())
    if formula != f"{' '.join(caption.split())} / 2":
        raise AngularLawError(f"angular_law: {half_caption}'s formula is {formula!r}, "
                              f"not '{caption} / 2'")
    roles = hexagon_roles(sketch)
    a, R = roles["a"], roles["R"]
    full, hp = doc.params[caption].elem_id, half.elem_id
    for name, vals in doc.types or []:
        af, hv = vals.get(full), vals.get(hp)
        if isinstance(af, (int, float)) and abs(float(af) - 2.0 * a) > 1e-9:
            raise AngularLawError(f"angular_law: type {name!r} has {caption} "
                                  f"{float(af):g} ft, the hexagon {2.0 * a:g} ft")
        if isinstance(hv, (int, float)) and abs(float(hv) - a) > 1e-9:
            raise AngularLawError(f"angular_law: type {name!r} has {half_caption} "
                                  f"{float(hv):g} ft, not {a:g} ft")
    ids = {roles[r][0] for r in ROLES}
    by_id = {e.elem_id: e for e in doc.elements}
    if not all(i in by_id and by_id[i].class_name == "CurveElem" for i in ids):
        raise AngularLawError("angular_law: a hexagon line is not a CurveElem of the document")
    if ids & _locked_curves(doc):
        raise AngularLawError("angular_law: the hexagon is already constrained")
    if sketch.obj.get("m_dimIds"):
        raise AngularLawError("angular_law: the sketch already registers dimensions")
    try:
        ppar = origin_centre_plane(doc, "y")   # y = 0: parallel to the flats
        pperp = origin_centre_plane(doc, "x")  # x = 0
    except ValueError as exc:                  # a refusal, so callers' fallback runs
        raise AngularLawError(f"angular_law: {exc}") from exc
    skp = int(sketch.obj.get("m_sketchPlaneId", -1))
    if skp not in by_id or by_id[skp].class_name != "SketchPlane":
        raise AngularLawError("angular_law: the sketch has no sketch plane")
    pids = {p: r["pid"] for p, r in ((r["value"]["m_objId"], r)
                                     for r in sketch.obj.get("m_elemRecs") or [])}
    if set(pids) != ids:
        raise AngularLawError("angular_law: the sketch's solver records are not its six lines")
    kinds = collections.Counter(r.get("ptr_class") for r in sketch.obj.get("m_constrRecs") or [])
    if (set(kinds) - {"VarSketchPPConstrObj", "VarSketchHorVerConstrObj"}
            or kinds.get("VarSketchPPConstrObj") != 6):
        raise AngularLawError("angular_law: the sketch's solver constraints are not six "
                              "point-point joins plus horizontal/vertical locks")

    # -- mutations start here
    fam, style = doc.self_family.elem_id, int(doc.dim_style_id)
    sk_id = sketch.elem_id
    P = max(abs(float(c)) for p in (ppar, pperp)
            for e in ("m_freeEnd", "m_bubbleEnd") for c in p.obj[e][:2]) or 1.0
    m = 3.0 * R                                # annotation offset (cosmetic)
    c = R / 2.0
    L = {r: roles[r] for r in ROLES}
    V = {k: (R * math.cos(math.radians(k)), R * math.sin(math.radians(k)))
         for k in (0, 60, 120, 180, 240, 300)}
    made: List[Any] = []
    kw = dict(fam=fam, style=style, sk_id=sk_id, skp=skp)

    # five locked 60-degree angles, census order
    for ra, rb in (("Fb", "Q0"), ("Q0", "Q1"), ("Q1", "Ft"), ("Ft", "Sp"), ("Sp", "S")):
        made.append(new_angular_lock(_alloc(doc.ids), line_a=L[ra], line_b=L[rb],
                                     radius=R + m, **kw))
    ft, fb, s, sp = L["Ft"], L["Fb"], L["S"], L["Sp"]
    # EQ: Ft | Ppar | Fb (along y); every witness listed along Ft (-x)
    X = R + m
    made.append(new_sketch_dim(
        _alloc(doc.ids), witnesses=[
            _w_line(ft[0], (ft[1], ft[2]), 0, 0),
            _w_line(ppar.elem_id, ((P, 0.0), (-P, 0.0)), 1, 1, EQ_PLANE_CONSTR_FLAGS),
            _w_line(fb[0], (fb[2], fb[1]), 2, 1)],
        ref_pnts=[ft[1], (X, 0.0), fb[2]], values=[a, a],
        seg_origins=[(X, a / 2.0), (X, -a / 2.0)], line_origin=(X, 0.0, 0.0),
        line_dir=(0.0, -1.0, 0.0), **kw))
    # EQ: Fb.start | Pperp | Fb.end (along x)
    Y = -(a + m)
    made.append(new_sketch_dim(
        _alloc(doc.ids), witnesses=[
            _w_vertex(fb[0], fb[1], 0, 0, 0),
            _w_line(pperp.elem_id, ((0.0, -P), (0.0, P)), 1, 0, EQ_PLANE_CONSTR_FLAGS),
            _w_vertex(fb[0], fb[2], 1, 2, 0)],
        ref_pnts=[fb[1], (0.0, Y), fb[2]], values=[c, c],
        seg_origins=[(-c / 2.0, Y), (c / 2.0, Y)], line_origin=(0.0, Y, 0.0),
        line_dir=(1.0, 0.0, 0.0), **kw))
    # EQ: S'.start | Pperp | Ft.start (the top flat's two vertices, along x)
    Y = a + m
    made.append(new_sketch_dim(
        _alloc(doc.ids), witnesses=[
            _w_vertex(sp[0], sp[1], 0, 0, 0),
            _w_line(pperp.elem_id, ((0.0, P), (0.0, -P)), 1, 1, EQ_PLANE_CONSTR_FLAGS),
            _w_vertex(ft[0], ft[1], 0, 2, 0)],
        ref_pnts=[sp[1], (0.0, Y), ft[1]], values=[c, c],
        seg_origins=[(-c / 2.0, Y), (c / 2.0, Y)], line_origin=(0.0, Y, 0.0),
        line_dir=(1.0, 0.0, 0.0), **kw))

    def _slant_label(line):
        d = _unit((line[2][0] - line[1][0], line[2][1] - line[1][1]))
        n = (-d[1], d[0])                     # the inward normal of a CCW side
        q = (line[1][0] - m * d[0], line[1][1] - m * d[1])
        s0 = n[0] * line[1][0] + n[1] * line[1][1]      # = -a
        qn = n[0] * q[0] + n[1] * q[1]
        mid = s0 / 2.0
        so = (q[0] + n[0] * (mid - qn), q[1] + n[1] * (mid - qn))
        return new_sketch_dim(
            _alloc(doc.ids), witnesses=[
                _w_line(line[0], (line[1], line[2]), 0, 0),
                _w_cross(pperp.elem_id, ppar.elem_id, 1)],
            ref_pnts=[line[1], (0.0, 0.0)], values=[a], seg_origins=[so],
            line_origin=(q[0], q[1], 0.0), line_dir=(n[0], n[1], 0.0),
            param_id=hp, **kw)
    # LABEL: S to the origin point, along S's normal
    made.append(_slant_label(s))
    # LABEL: Fb to Ppar (along y)
    X = -(R + m)
    made.append(new_sketch_dim(
        _alloc(doc.ids), witnesses=[
            _w_line(fb[0], (fb[1], fb[2]), 0, 0),
            _w_line(ppar.elem_id, ((-P, 0.0), (P, 0.0)), 1, 0)],
        ref_pnts=[fb[1], (X, 0.0)], values=[a], seg_origins=[(X, -a / 2.0)],
        line_origin=(X, 0.0, 0.0), line_dir=(0.0, 1.0, 0.0), param_id=hp, **kw))
    # LABEL: S' to the origin point -- the stated substitute for the born
    # secret-style corner pin (module docstring)
    made.append(_slant_label(sp))
    for el in made:
        doc.add(el)

    # the sketch registers them; dimData for the linear ones (census order)
    sketch.obj["m_dimIds"] = [el.elem_id for el in made]
    sketch.obj["m_dimData"] = [
        {"first": made[5].elem_id, "second": DIM_DATA["eq_flats"]},
        {"first": made[6].elem_id, "second": DIM_DATA["eq_bottom_ends"]},
        {"first": made[7].elem_id, "second": DIM_DATA["eq_top_ends"]},
        {"first": made[8].elem_id, "second": DIM_DATA["label"]},
        {"first": made[9].elem_id, "second": DIM_DATA["label"]},
        {"first": made[10].elem_id, "second": DIM_DATA["label"]}]
    par = sketch.header["m_parents"]["value"]
    par["m_deletion"] = sorted(set(par["m_deletion"]) | {el.elem_id for el in made})
    par["m_regenOnly"] = sorted(set(par.get("m_regenOnly") or []) | {ppar.elem_id, pperp.elem_id})
    solver = _born_solver_state(sketch, roles)
    # every hexagon curve carries the born sketch-curve bit (192 / 192)
    from .drive_law import CURVE_BORN_BIT
    for cid in ids:
        crv = by_id[cid].obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
        gi = crv.get("m_GInfo")
        if isinstance(gi, dict):
            gi["m_flags"] = int(gi.get("m_flags", 0)) | CURVE_BORN_BIT
    return {"caption": caption, "half_caption": half_caption, "sketch": sk_id,
            "angular": [el.elem_id for el in made[:5]],
            "eq": [el.elem_id for el in made[5:8]],
            "labelled": [el.elem_id for el in made[8:]],
            "planes": [ppar.elem_id, pperp.elem_id], "across_flats": 2.0 * a,
            "substituted": "corner pin -> S' label", **solver}

"""rvt.famgen.drive_law -- the IN-PLANE parametric drive as Revit-born families
store it (issue #787 DONE 1, the in-plane half of #372).

WHY.  ``param_drive.wire_panelboard_drive`` authors the chain a donor showed
(side reference planes, an ``Alignment`` per sketch line, labelled
``LinearDimString``\\s), and ``skeleton.finalize`` adds ``m_constrInfo``
back-edges.  On the owner's Revit nothing flexes (#372, again on the trapeze
of #899 / steer #901).  A field-by-field census of a 421-family Revit-born
corpus (the owner's private reference library, #836 / #865 -- quarantined,
never copied) found the chain differs from EVERY born specimen in these
places (corpus counts; the specimens themselves are not named here):

1. ``VarSketch`` header ``m_parents.m_regenOnly`` lists the host Level AND
   every reference plane its lines are locked to (13,939 / 14,556 sketch
   constraints); ours lists the Level only -- so moving a plane never
   regenerates the sketch.                                     [REGEN EDGE]
2. ``m_constrInfo`` is ``[]`` on every element of every born file (0 / 421
   files carry one); ours writes back-edges (``famdim``), a refuted law.
3. A sketch-lock ``Alignment`` is owned by NO view (object and header owner
   view -1, 2,666 / 2,666); ours names the plan view.
4. ``ExtrusionElem.m_sideRefPlaneCurveBased`` is True (2,161 / 2,161); ours
   False.
5. ``m_dimVersion`` is 6 (or 0) on born dimensions, never 1; ours 1.
6. A sketch ``CurveElem``'s curve ``GInfo.m_flags`` carries bit 0x80000
   (24,209 / 24,213); ours does not.
7. A labelled dimension's segment ``m_flags`` is 0 (2,334 vs 272) and its
   header ``m_regenOnly`` is ``[UnitsElem]``.

This module rewrites a finalized document's in-plane chain to that law.
``regen_edge=False`` leaves item 1 out and nothing else -- the CONTROL of the
single-variable probe pair (#787 DONE 4).  Nothing here claims a family
flexes: that is a desktop verdict (hard rule 4).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional


#: the curve GInfo bit set on 24,209 / 24,213 born sketch curves [census]
CURVE_BORN_BIT = 0x80000
#: m_dimVersion on born dimensions (36k records; 0 on the other 4k) [census]
BORN_DIM_VERSION = 6


#: the parameter specs a LABELLED dimension may carry in Revit-born families:
#: census of the 421-family reference corpus (#913) -- length 2,504, conduit
#: size 92, cable-tray size 19, pipe size 8; nothing else is ever labelled
DRIVABLE_SPECS = ("autodesk.spec.aec:length",
                  "autodesk.spec.aec.electrical:conduitSize",
                  "autodesk.spec.aec.electrical:cableTraySize",
                  "autodesk.spec.aec.piping:pipeSize")


def drivable_spec(pe) -> str:
    """The parameter's spec id when a labelled dimension may carry it, else ''."""
    pdef = next((v.get("value") or {} for k, v in pe.obj.items()
                 if k.endswith("aramDef") and isinstance(v, dict)), {})
    spec = (pdef.get("m_specTypeId") or {}).get("m_typeId") or ""
    return spec if spec.rsplit("-", 1)[0] in DRIVABLE_SPECS else ""


def _parents(el) -> Dict[str, Any]:
    return el.header["m_parents"]["value"]


def _sketch_locks(doc) -> List[Any]:
    """Alignments carrying a SketchMembership cell: the in-plane locks."""
    out = []
    for el in doc.by_class("Alignment"):
        cells = (((el.obj.get("m_cellList") or {}).get("value") or {})
                 .get("m_cells") or [])
        if any(c.get("ptr_class") == "SketchMembership" for c in cells):
            out.append(el)
    return out


def _witness_ids(el) -> List[int]:
    ids = []
    for w in el.obj.get("m_witnessRefs") or []:
        g = (((w.get("m_pWitnessRef") or {}).get("value") or {})
             .get("m_geomRef") or {})
        if "m_elemId" in g:
            ids.append(int(g["m_elemId"]))
    return ids


def apply_born_inplane_law(doc, *, regen_edge: bool = True) -> Dict[str, Any]:
    """Rewrite ``doc``'s in-plane drive chain to the born law; returns a
    report of exactly what changed (so a probe pair can show it differs in
    one thing).  Safe on a document with no chain (changes nothing)."""
    rep: Dict[str, Any] = {"regen_edge": bool(regen_edge), "sketches": {},
                           "locks": [], "labelled": [], "constr_info_cleared": 0,
                           "extrusions": [], "curves": []}
    locks = _sketch_locks(doc)
    by_id = {e.elem_id: e for e in doc.elements}
    refplanes = {e.elem_id for e in doc.by_class("RefPlane")}
    units = [e.elem_id for e in doc.by_class("UnitsElem")]

    # 3 + 5: sketch locks owned by no view, born dim version
    for al in locks:
        view = int(al.obj.get("m_ownerDBViewId", -1))
        al.obj["m_ownerDBViewId"] = -1
        al.header["m_ownerViewId"] = -1
        par = _parents(al)
        if view >= 0:
            par["m_deletion"] = [i for i in par["m_deletion"] if i != view]
        al.obj["m_dimVersion"] = BORN_DIM_VERSION
        rep["locks"].append(al.elem_id)

    # 7 + 5: labelled dimensions
    for dim in doc.by_class("LinearDimString"):
        segs = dim.obj.get("m_ArrSegInfo") or []
        if not any(int(s.get("m_paramId", -1)) >= 0 for s in segs):
            continue
        for s in segs:
            s["m_flags"] = 0
        dim.obj["m_dimVersion"] = BORN_DIM_VERSION
        if units:
            _parents(dim)["m_regenOnly"] = [units[0]]
        rep["labelled"].append(dim.elem_id)

    # 1: the regen edge -- each sketch regenerates from the planes it is locked to
    for sk in doc.by_class("VarSketch"):
        mine = [a for a in locks if int(a.owner_id) == sk.elem_id
                or sk.elem_id in (_parents(a).get("m_deletion") or [])]
        planes = sorted({i for a in mine for i in _witness_ids(a) if i in refplanes})
        if not planes:
            continue
        par = _parents(sk)
        before = list(par.get("m_regenOnly") or [])
        if regen_edge:
            par["m_regenOnly"] = before + [p for p in planes if p not in before]
        rep["sketches"][sk.elem_id] = {"regen_before": before,
                                       "regen_after": list(par["m_regenOnly"]),
                                       "planes": planes}
        # 6: the sketch's own curves carry the born bit
        for a in mine:
            for cid in _witness_ids(a):
                ce = by_id.get(cid)
                if ce is None or ce.class_name != "CurveElem":
                    continue
                crv = (((ce.obj.get("m_pCurveDriver") or {}).get("value") or {})
                       .get("m_pCrv") or {}).get("value") or {}
                gi = crv.get("m_GInfo")
                if isinstance(gi, dict) and not int(gi.get("m_flags", 0)) & CURVE_BORN_BIT:
                    gi["m_flags"] = int(gi.get("m_flags", 0)) | CURVE_BORN_BIT
                    rep["curves"].append(cid)

    # 4: every born extrusion is side-ref-plane curve based (2,161 / 2,161)
    for ex in doc.by_class("ExtrusionElem"):
        if ex.obj.get("m_sideRefPlaneCurveBased") is False:
            ex.obj["m_sideRefPlaneCurveBased"] = True
            rep["extrusions"].append(ex.elem_id)

    # 2: no back-edges anywhere (0 / 421 born files carry one)
    for el in doc.elements:
        if el.obj.get("m_constrInfo"):
            el.obj["m_constrInfo"] = []
            rep["constr_info_cleared"] += 1
    # the Lock column follows the segment lock bits just cleared (#915)
    from .skeleton import sync_locked_params
    sync_locked_params(doc)
    # (runs AFTER finalize sealed the content-derived document GUID (#168):
    # harmless because this rewrite is a pure function of the document, so two
    # identical builds still produce identical bytes)
    doc.notes.append(
        "in-plane drive rewritten to the Revit-born law (#787): "
        + ("WITH" if regen_edge else "WITHOUT (control)")
        + f" the sketch regen edge; {len(rep['locks'])} sketch locks view-less, "
        f"{len(rep['labelled'])} labelled dims, {rep['constr_info_cleared']} "
        "back-edges cleared -- desktop verdicts are per lane (#787 one box, "
        "#904 trapeze Strut Length); any other lane is unverified (hard rule 4)")
    return rep


# ---------------------------------------------------------------------------
# ONE parameter driving the edges of SEVERAL parts (#904)
# ---------------------------------------------------------------------------

#: per (axis, side): (constrained direction, plane-first witness order,
#: VarSketch m_dimData second) -- the donor-measured panel patterns of
#: param_drive.wire_panelboard_drive, side by side
_SIDE_LAW = {
    ("x", "lo"): ((-1.0, 0.0, 0.0), True, 0),
    ("x", "hi"): ((1.0, 0.0, 0.0), False, 0),
    ("y", "lo"): ((0.0, -1.0, 0.0), False, 1),
    ("y", "hi"): ((0.0, 1.0, 0.0), True, 1),
}


def wire_linear_drive(doc, *, caption: str, axis: str, lo: float, hi: float,
                      targets, lo_plane=None, hi_plane=None) -> Dict[str, Any]:
    """Make family parameter ``caption`` drive the distance between two new
    reference planes at ``lo`` / ``hi`` (feet, along ``axis`` 'x' or 'y'), and
    lock the matching edge of every target part's rectangular sketch to them.

    ``targets`` = ``[(VarSketch element, ("lo",) | ("hi",) | ("lo", "hi"))]``:
    a part whose ends both follow the parameter (a full-length web) lists both
    sides; the end segment of a slotted back lists only its outer side.

    ``lo_plane`` / ``hi_plane``: an EXISTING reference plane (in practice the
    origin centre plane, :func:`origin_centre_plane`) standing in for that end.
    No new plane is made there: the labelled dimension witnesses it and that
    side's edges are locked to it, so that end is ANCHORED and only the other
    one moves -- a one-sided drive (a panelboard's back on the wall plane,
    #914).  The plane must lie square to ``axis`` exactly at ``lo`` / ``hi``.
    UNVERIFIED: the one-box verdict (#787) had two new, unanchored planes; a
    drive anchored on an origin plane has no desktop verdict (hard rule 4).

    Call BEFORE ``finalize``; run :func:`apply_born_inplane_law` after it.  The
    chain is the desktop-verified one-box law (#787 verdict) applied per part;
    a multi-part family is its own lane and needs its own verdict (hard rule 4).
    """
    from . import param_drive as PD
    from .skeleton import _alloc, new_reference_plane
    if axis not in ("x", "y"):
        raise ValueError(f"drive_law: axis must be 'x' or 'y', not {axis!r}")
    if doc.finalized:
        raise RuntimeError("drive_law: document is finalized")
    pe = doc.params[caption]
    targets = list(targets)            # a generator would be spent by the checks
    # EVERY check before the first mutation: a refused drive must leave the
    # document exactly as it was, not half a chain (#907 review round 2)
    lo, hi = float(lo), float(hi)
    if not (math.isfinite(lo) and math.isfinite(hi) and lo < hi):
        raise ValueError(f"drive_law: planes must be finite with lo < hi (got {lo!r}, {hi!r})")
    if not drivable_spec(pe):
        raise ValueError(f"drive_law: {caption} is not a length or size parameter")
    if not targets:
        raise ValueError("drive_law: no target parts")
    value = hi - lo
    rows = doc.types[doc.current_type][1] if doc.types else {}
    current = rows.get(pe.elem_id)
    if isinstance(current, (int, float)) and abs(float(current) - value) > 1e-6:
        raise ValueError(f"drive_law: {caption} is {float(current):g} ft but its planes "
                         f"are {value:g} ft apart")
    k = 0 if axis == "x" else 1
    given = {"lo": lo_plane, "hi": hi_plane}
    if lo_plane is not None and lo_plane is hi_plane:
        raise ValueError("drive_law: one plane cannot be both ends")
    for end, rp in given.items():
        if rp is None:
            continue
        if rp.elem_id not in {p.elem_id for p in doc.refplanes}:
            raise ValueError(f"drive_law: the {end} plane is not in this document")
        f, b = rp.obj["m_freeEnd"], rp.obj["m_bubbleEnd"]
        want = lo if end == "lo" else hi
        if abs(float(f[k]) - want) > 1e-9 or abs(float(b[k]) - want) > 1e-9:
            raise ValueError(f"drive_law: the {end} plane is not the {'xy'[k]} = "
                             f"{want:g} ft plane")
    rects = [PD._classify_rect(PD._sketch_lines(sk)) for sk, _sides in targets]
    side_key = {("x", "lo"): "left", ("x", "hi"): "right",
                ("y", "lo"): "bottom", ("y", "hi"): "top"}
    at = {"lo": lo, "hi": hi}
    # a curve already locked to a plane (an earlier drive, or the first-solid
    # chain of drive=True) must not be locked again: two locks on one edge tie
    # two parameters together for ever and Revit cannot flex either (#907
    # review round 4)
    locked = {cid for al in _sketch_locks(doc) for cid in _witness_ids(al)}
    claimed: set = set()
    for (sk, sides), rect in zip(targets, rects):
        bad = [x for x in sides if (axis, x) not in _SIDE_LAW]
        if bad or not sides or len(set(sides)) != len(sides):
            raise ValueError(f"drive_law: unknown, empty or repeated side(s) {list(sides)}")
        for side in sides:
            cid = rect[side_key[(axis, side)]][0]
            if cid in locked or cid in claimed:
                raise ValueError(f"drive_law: sketch {sk.elem_id}'s {side} edge is already "
                                 "locked by another drive")
            claimed.add(cid)
        for side in sides:
            # the edge must LIE ON its plane: both ends at the plane's coordinate
            # (refuses a rotated quad, crossed planes and an off-plane edge)
            _cid, a, b = rect[side_key[(axis, side)]]
            if abs(a[k] - at[side]) > 1e-6 or abs(b[k] - at[side]) > 1e-6:
                raise ValueError(
                    f"drive_law: sketch {sk.elem_id}'s {side} edge is not on the "
                    f"{'xy'[k]} = {at[side]:g} ft plane")
    fam_id = doc.self_family.elem_id
    style_id = int(doc.dim_style_id)
    view_id = int(doc.plan_view_id)
    P = 5.0
    if doc.refplanes:
        c = doc.refplanes[0]
        P = PD._seg_length((c.obj["m_freeEnd"], c.obj["m_bubbleEnd"])) / 2.0 or 5.0
    P = max(P, abs(lo) + 1.0, abs(hi) + 1.0)
    env = ((-P, -2.0), (P, 10.0))

    def _plane(at):
        if axis == "x":
            free, bubble = (at, -P, 0.0), (at, P, 0.0)
        else:
            free, bubble = (-P, at, 0.0), (P, at, 0.0)
        rp = new_reference_plane(_alloc(doc.ids), fam_id, name="", ref_name="weak",
                                 free_end=free, bubble_end=bubble,
                                 normal=(0.0, 0.0, 1.0), gen_view_id=view_id,
                                 extent=env)
        doc.refplanes.append(rp)
        doc.add(rp)
        return rp

    planes = {"lo": lo_plane if lo_plane is not None else _plane(lo),
              "hi": hi_plane if hi_plane is not None else _plane(hi)}

    def _p3(p):
        return (float(p[0]), float(p[1]), 0.0)

    def _plane_ends(rp):
        return (_p3(rp.obj["m_freeEnd"]), _p3(rp.obj["m_bubbleEnd"]))

    locks: List[int] = []
    for (sk, sides), rect in zip(targets, rects):
        geo_sp = next((e for e in doc.by_class("SketchPlane")
                       if int(e.obj.get("m_userId", -1)) == sk.elem_id), None)
        geo_sp_id = geo_sp.elem_id if geo_sp is not None else -1
        dim_ids = list(sk.obj.get("m_dimIds") or [])
        dim_data = list(sk.obj.get("m_dimData") or [])
        new_ids = []
        for side in sides:
            cdir, plane_first, second = _SIDE_LAW[(axis, side)]
            cid, a, b = rect[side_key[(axis, side)]]
            rp = planes[side]
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, 0.0)
            al = PD.new_alignment(
                _alloc(doc.ids), fam_id, sketch_id=sk.elem_id, curve_id=cid,
                refplane_id=rp.elem_id, style_id=style_id, constr_dir=cdir,
                origin=mid, curve_ends=(_p3(a), _p3(b)), plane_ends=_plane_ends(rp),
                view_id=view_id, sketch_plane_id=geo_sp_id, plane_first=plane_first,
                ref_pnts=((mid, mid) if not plane_first else (_p3(a), _p3(b))))
            doc.add(al)
            dim_ids.append(al.elem_id)
            dim_data.append({"first": al.elem_id, "second": second})
            new_ids.append(al.elem_id)
        sk.obj["m_dimIds"] = dim_ids
        sk.obj["m_dimData"] = dim_data
        par = sk.header["m_parents"]["value"]
        par["m_deletion"] = sorted(set(par["m_deletion"]) | set(new_ids))
        locks.extend(new_ids)

    units = [e.elem_id for e in doc.by_class("UnitsElem")]
    view_sp = next((e for e in doc.views if e.class_name == "SketchPlane"), None)
    regen_sp = view_sp.elem_id if view_sp is not None else -1
    ref = -(P - PD.REFPNT_INSET)
    if axis == "x":
        line = ref - PD.DIMLINE_STEP
        dim = PD.new_labeled_dim(
            _alloc(doc.ids), fam_id, param_id=pe.elem_id,
            ref_a_id=planes["lo"].elem_id, ref_b_id=planes["hi"].elem_id,
            style_id=style_id, value=value, ref_a_ends=_plane_ends(planes["lo"]),
            ref_b_ends=_plane_ends(planes["hi"]),
            ref_pnts=((lo, ref, 0.0), (hi, ref, 0.0)),
            seg_origin=((lo + hi) / 2.0, line, 0.0),
            dim_line_origin=((lo + hi) / 2.0, line, 0.0),
            dim_line_dir=(1.0, 0.0, 0.0), view_id=view_id,
            sketch_plane_id=regen_sp, seg_flags=0)
    else:
        line = ref + PD.DIMLINE_STEP
        dim = PD.new_labeled_dim(
            _alloc(doc.ids), fam_id, param_id=pe.elem_id,
            ref_a_id=planes["lo"].elem_id, ref_b_id=planes["hi"].elem_id,
            style_id=style_id, value=value, ref_a_ends=_plane_ends(planes["lo"]),
            ref_b_ends=_plane_ends(planes["hi"]),
            ref_pnts=((ref, lo, 0.0), (ref, hi, 0.0)),
            seg_origin=(line, (lo + hi) / 2.0, 0.0),
            dim_line_origin=(line, (lo + hi) / 2.0, 0.0),
            dim_line_dir=(0.0, 1.0, 0.0), view_id=view_id,
            sketch_plane_id=regen_sp, seg_flags=0)
    if not units:
        doc.notes.append("drive_law: no UnitsElem -- the labelled dimension keeps the "
                         "view sketch plane as its regen parent")
    doc.add(dim)
    out = {"caption": caption, "axis": axis, "planes": [planes["lo"].elem_id,
                                                        planes["hi"].elem_id],
           "locks": locks, "dim": dim.elem_id, "targets": len(targets)}
    anchored = [e for e in ("lo", "hi") if given[e] is not None]
    if anchored:
        out["anchored"] = anchored
    return out


# ---------------------------------------------------------------------------
# PARTS THAT FOLLOW A MOVING PLANE (#904, #908) -- the "Follow" probe ladder's
# mechanisms, each desktop-verified on the owner's Revit (all 9 rungs worked,
# #904 2026-10-01), ported from the ladder builder field for field:
#   * symmetric ends: EQ(lo | origin centre plane | hi)        [ladder base]
#   * a labelled offset plane: R = lo + <param>                [P1, P3, P4]
#   * EQ about a plane + a LOCKED unlabelled width             [P3 + P2]
#   * a circle's arc centres aligned to a plane                [P4]
# ---------------------------------------------------------------------------

def _p3(p) -> tuple:
    return (float(p[0]), float(p[1]), 0.0)


def _plane_ends(rp) -> tuple:
    return (_p3(rp.obj["m_freeEnd"]), _p3(rp.obj["m_bubbleEnd"]))


def _dim_ctx(doc) -> Dict[str, Any]:
    from . import param_drive as PD
    P = 5.0
    if doc.refplanes:
        c = doc.refplanes[0]
        P = PD._seg_length((c.obj["m_freeEnd"], c.obj["m_bubbleEnd"])) / 2.0 or 5.0
    view_sp = next((e for e in doc.views if e.class_name == "SketchPlane"), None)
    return {"fam": doc.self_family.elem_id, "style": int(doc.dim_style_id),
            "view": int(doc.plan_view_id), "P": P,
            "view_sp": view_sp.elem_id if view_sp is not None else -1}


def plane_at(rp, axis: str) -> float:
    return float(rp.obj["m_freeEnd"][0 if axis == "x" else 1])


def add_plane(doc, axis: str, at: float):
    """A weak reference plane at x = ``at`` ('x') or y = ``at`` ('y')."""
    from .skeleton import _alloc, new_reference_plane
    c = _dim_ctx(doc)
    P = max(c["P"], abs(at) + 1.0)
    free, bubble = (((at, -P, 0.0), (at, P, 0.0)) if axis == "x"
                    else ((-P, at, 0.0), (P, at, 0.0)))
    rp = new_reference_plane(_alloc(doc.ids), c["fam"], name="", ref_name="weak",
                             free_end=free, bubble_end=bubble, normal=(0.0, 0.0, 1.0),
                             gen_view_id=c["view"], extent=((-P, -2.0), (P, 10.0)))
    doc.refplanes.append(rp)
    doc.add(rp)
    return rp


def dim3d(doc, a, b, axis: str, *, caption: Optional[str] = None,
          locked: bool = False, line_step: int = 1):
    """A plan-view ``LinearDimString`` between reference planes ``a`` and ``b``:
    LABELLED with ``caption`` (segment ``m_paramId``, flags 0) [P1/P3/P4], or
    UNLABELLED and, with ``locked``, holding its distance (segment flags bit 0)
    [P2; P2c without the bit did not hold]."""
    from . import param_drive as PD
    from . import geometry as G
    from .skeleton import _alloc
    c = _dim_ctx(doc)
    xa, xb = plane_at(a, axis), plane_at(b, axis)
    ref = -(c["P"] - PD.REFPNT_INSET)
    step = PD.DIMLINE_STEP * (1 + 2 * line_step)
    if axis == "x":
        line = ref - step
        kw = dict(ref_pnts=((xa, ref, 0.0), (xb, ref, 0.0)),
                  seg_origin=((xa + xb) / 2.0, line, 0.0),
                  dim_line_origin=((xa + xb) / 2.0, line, 0.0), dim_line_dir=(1.0, 0.0, 0.0))
    else:
        line = ref + step
        kw = dict(ref_pnts=((ref, xa, 0.0), (ref, xb, 0.0)),
                  seg_origin=(line, (xa + xb) / 2.0, 0.0),
                  dim_line_origin=(line, (xa + xb) / 2.0, 0.0), dim_line_dir=(0.0, 1.0, 0.0))
    pid = doc.params[caption].elem_id if caption else -1
    dim = PD.new_labeled_dim(_alloc(doc.ids), c["fam"], param_id=pid, ref_a_id=a.elem_id,
                             ref_b_id=b.elem_id, style_id=c["style"], value=abs(xb - xa),
                             ref_a_ends=_plane_ends(a), ref_b_ends=_plane_ends(b),
                             view_id=c["view"], sketch_plane_id=c["view_sp"],
                             seg_flags=0, **kw)
    seg = dim.obj["m_ArrSegInfo"][0]
    if not caption:
        dim.obj["m_dimLockedForLabeling"] = False
        seg["m_paramId"] = -1
        seg["m_flags"] = 1 if locked else 0
    for v in seg["m_values"]:
        v["m_oTextFields"] = None
    dim.obj["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"]["m_arr"] = []
    dim.obj["m_dimVersion"] = BORN_DIM_VERSION
    G.assign_pids(dim.obj)
    doc.add(dim)
    return dim


def eq3d(doc, a, mid, b, axis: str):
    """A plan-view EQUALITY dimension a | mid | b: flags 140, two segments with
    flags 2 and equal locked values, three plane witnesses [ladder base, P3]."""
    import copy
    from . import param_drive as PD
    from . import geometry as G
    xa, xm, xb = plane_at(a, axis), plane_at(mid, axis), plane_at(b, axis)
    dim = dim3d(doc, a, b, axis, caption=None, locked=False, line_step=2)
    o = dim.obj
    w0, w1 = o["m_witnessRefs"]
    wm = copy.deepcopy(w0)
    wm["m_pWitnessRef"]["value"]["m_geomRef"]["m_elemId"] = mid.elem_id
    ends = _plane_ends(mid)
    wm["m_oldRefSegEnds"] = [list(ends[0]), list(ends[1])]
    wm["m_refLength"] = PD._seg_length(ends)
    w0["m_id"] = {"m_id": 0}
    wm["m_id"] = {"m_id": 1}
    w1["m_id"] = {"m_id": 2}
    for w in (w0, wm, w1):
        w["m_oldRefSegEndIdx"] = 1
        w["m_constrFlags"] = 0
    o["m_witnessRefs"] = [w0, wm, w1]
    r0, r1 = o["m_refPnts"]
    rm = list(r0)
    rm[0 if axis == "x" else 1] = xm
    o["m_refPnts"] = [r0, rm, r1]
    s0 = o["m_ArrSegInfo"][0]
    s1 = copy.deepcopy(s0)
    for s, lo_, hi_, ids in ((s0, xa, xm, (0, 1)), (s1, xm, xb, (1, 2))):
        s["m_lockedValue"] = abs(hi_ - lo_)
        s["m_values"][0]["m_value"] = abs(hi_ - lo_)
        s["m_flags"] = 2
        s["m_paramId"] = -1
        s["m_id"] = {"m_id1": ids[0], "m_id2": ids[1]}
        org = list(s["m_origin"])
        org[0 if axis == "x" else 1] = (lo_ + hi_) / 2.0
        s["m_origin"] = org
    o["m_ArrSegInfo"] = [s0, s1]
    o["m_flags"] = 140
    o["m_dimLockedForLabeling"] = False
    o["m_lastDimSegInfoId"] = {"m_id1": -1, "m_id2": -1}
    o["m_lastUsedId"] = {"m_id": 2}
    par = dim.header["m_parents"]["value"]
    par["m_deletion"] = sorted(set(par["m_deletion"]) | {mid.elem_id})
    par["m_appearanceParents"] = sorted(set(par["m_appearanceParents"]) | {mid.elem_id})
    G.assign_pids(o)
    return dim


def _geo_sp(doc, sk) -> int:
    sp = next((e for e in doc.by_class("SketchPlane")
               if int(e.obj.get("m_userId", -1)) == sk.elem_id), None)
    return sp.elem_id if sp is not None else -1


def _register(sk, el, second: Optional[int]) -> None:
    sk.obj["m_dimIds"] = list(sk.obj.get("m_dimIds") or []) + [el.elem_id]
    if second is not None:
        sk.obj["m_dimData"] = list(sk.obj.get("m_dimData") or []) + [
            {"first": el.elem_id, "second": int(second)}]
    par = sk.header["m_parents"]["value"]
    par["m_deletion"] = sorted(set(par["m_deletion"]) | {el.elem_id})


def _arcs_of(doc, sk) -> List[Any]:
    """The arc CurveElems of sketch ``sk`` (a circle is two half-arcs here)."""
    out = []
    for ce in doc.by_class("CurveElem"):
        if sk.elem_id not in (ce.header["m_parents"]["value"].get("m_deletion") or []):
            continue
        cr = ce.obj["m_pCurveDriver"]["value"]["m_pCrv"]
        if cr.get("ptr_class") == "GArc":
            out.append(ce)
    return out


def align_arc_centre(doc, arc_ce, sk, plane, axis: str):
    """Lock an arc's CENTRE (witness geomTag 1) to ``plane`` [P4]."""
    from . import param_drive as PD
    from . import geometry as G
    from .skeleton import _alloc
    c = _dim_ctx(doc)
    cr = arc_ce.obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
    cc = (float(cr["m_center"][0]), float(cr["m_center"][1]), 0.0)
    if axis == "x":
        cdir, ppt = (1.0, 0.0, 0.0), (plane_at(plane, "x"), cc[1] + 1.0, 0.0)
    else:
        cdir, ppt = (0.0, 1.0, 0.0), (cc[0] + 1.0, plane_at(plane, "y"), 0.0)
    al = PD.new_alignment(_alloc(doc.ids), c["fam"], sketch_id=sk.elem_id,
                          curve_id=arc_ce.elem_id, refplane_id=plane.elem_id,
                          style_id=c["style"], constr_dir=cdir, origin=cc,
                          curve_ends=(cc, cc), plane_ends=_plane_ends(plane),
                          view_id=c["view"], sketch_plane_id=_geo_sp(doc, sk),
                          plane_first=True, ref_pnts=(ppt, cc))
    wp, wa = al.obj["m_witnessRefs"]
    wa["m_pWitnessRef"]["value"]["m_geomRef"]["m_geomTag"] = 1
    wa["m_refLength"] = 0.0
    wp["m_id"] = {"m_id": 1}
    wa["m_id"] = {"m_id": 0}
    seg = al.obj["m_ArrSegInfo"][0]
    seg["m_id"] = {"m_id1": 0, "m_id2": -1}
    for v in seg["m_values"]:
        v["m_oTextFields"] = None
    al.obj["m_lastDimSegInfoId"] = {"m_id1": 0, "m_id2": -1}
    al.obj["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"]["m_arr"] = []
    G.assign_pids(al.obj)
    doc.add(al)
    _register(sk, al, 0 if axis == "x" else 1)
    return al


def _lines_on(sk, axis: str, at: float) -> List[tuple]:
    """Sketch lines lying ON the plane ``axis`` = ``at`` (both ends on it)."""
    from . import param_drive as PD
    k = 0 if axis == "x" else 1
    return [(cid, a, b) for cid, a, b in PD._sketch_lines(sk)
            if abs(a[k] - at) <= 1e-6 and abs(b[k] - at) <= 1e-6]


def lock_line(doc, sk, line, plane, axis: str, side: str):
    """Align one sketch line to a plane, with the verified per-side law."""
    from . import param_drive as PD
    from .skeleton import _alloc
    c = _dim_ctx(doc)
    cdir, plane_first, second = _SIDE_LAW[(axis, side)]
    cid, a, b = line
    mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, 0.0)
    al = PD.new_alignment(_alloc(doc.ids), c["fam"], sketch_id=sk.elem_id, curve_id=cid,
                          refplane_id=plane.elem_id, style_id=c["style"], constr_dir=cdir,
                          origin=mid, curve_ends=(_p3(a), _p3(b)), plane_ends=_plane_ends(plane),
                          view_id=c["view"], sketch_plane_id=_geo_sp(doc, sk),
                          plane_first=plane_first,
                          ref_pnts=((mid, mid) if not plane_first else (_p3(a), _p3(b))))
    doc.add(al)
    _register(sk, al, second)
    return al


def origin_centre_plane(doc, axis: str):
    """The document's origin-defining centre plane normal to ``axis``."""
    k = 0 if axis == "x" else 1
    for p in doc.refplanes:
        if (p.obj.get("m_definesOrigin") and abs(p.obj["m_freeEnd"][k]) < 1e-9
                and abs(p.obj["m_bubbleEnd"][k]) < 1e-9):
            return p
    raise ValueError(f"drive_law: no origin centre plane normal to {axis}")


def wire_follow(doc, *, base: Dict[str, Any], caption: str, offset: float,
                followers: List[Dict[str, Any]], axis: str = "x") -> Dict[str, Any]:
    """Parts that FOLLOW a linear drive's two end planes (``base`` = the report
    of :func:`wire_linear_drive`): a plane R_lo = lo + ``caption`` (labelled),
    mirrored to R_hi by EQ(R_lo | origin centre | R_hi), and per follower on a
    side: ``{"side", "sketch", "kind": "circle"}`` (its arc centres aligned to
    R) or ``{"side", "sketch", "kind": "rigid", "half": h}`` (its lines on
    R - h / R + h locked to two planes held EQ about R by a LOCKED width).

    Every check runs before the first mutation, as in wire_linear_drive."""
    if doc.finalized:
        raise RuntimeError("drive_law: document is finalized")
    planes = {p.elem_id: p for p in doc.refplanes}
    lo_p, hi_p = planes[base["planes"][0]], planes[base["planes"][1]]
    lo, hi = plane_at(lo_p, axis), plane_at(hi_p, axis)
    pe = doc.params[caption]
    if not drivable_spec(pe):
        raise ValueError(f"drive_law: {caption} is not a length or size parameter")
    rows = doc.types[doc.current_type][1] if doc.types else {}
    cur = rows.get(pe.elem_id)
    offset = float(offset)
    if not (math.isfinite(offset) and 0.0 < offset < (hi - lo) / 2.0):
        raise ValueError(f"drive_law: offset {offset!r} does not fit inside the planes")
    if isinstance(cur, (int, float)) and abs(float(cur) - offset) > 1e-6:
        raise ValueError(f"drive_law: {caption} is {float(cur):g} ft, not {offset:g}")
    centre = origin_centre_plane(doc, axis)
    if abs((lo + hi) / 2.0 - plane_at(centre, axis)) > 1e-6:
        # R_hi mirrors R_lo through the centre: only true when the ends do
        raise ValueError("drive_law: the drive's planes are not centred on the origin plane")
    at = {"lo": lo + offset, "hi": hi - offset}
    plan: List[tuple] = []
    for f in followers:
        sk, side, kind = f["sketch"], f["side"], f["kind"]
        if side not in at:
            raise ValueError(f"drive_law: follower side {side!r}")
        if kind == "circle":
            arcs = _arcs_of(doc, sk)
            if not arcs or any(abs(float(a.obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
                                         ["m_center"][0 if axis == "x" else 1]) - at[side]) > 1e-6
                               for a in arcs):
                raise ValueError(f"drive_law: sketch {sk.elem_id}'s circle is not centred on "
                                 f"its follow plane")
            plan.append(("circle", sk, side, arcs))
        elif kind == "rigid":
            from . import param_drive as PD
            h = float(f["half"])
            lines_lo = _lines_on(sk, axis, at[side] - h)
            lines_hi = _lines_on(sk, axis, at[side] + h)
            if not (h > 0 and lines_lo and lines_hi):
                raise ValueError(f"drive_law: sketch {sk.elem_id} has no edges at "
                                 f"{at[side]:g} +- {h:g} ft")
            # the WHOLE part must be the slab between those edges: every vertex
            # within [R - h, R + h] and every edge square to the axis on one of
            # them -- an L-shape locked by two edges would deform (#912 review)
            k = 0 if axis == "x" else 1
            on = {ln[0] for ln in lines_lo + lines_hi}
            for cid, a, b in PD._sketch_lines(sk):
                if (a[k] < at[side] - h - 1e-6 or a[k] > at[side] + h + 1e-6
                        or b[k] < at[side] - h - 1e-6 or b[k] > at[side] + h + 1e-6):
                    raise ValueError(f"drive_law: sketch {sk.elem_id} reaches past "
                                     f"{at[side]:g} +- {h:g} ft")
                if abs(a[k] - b[k]) <= 1e-6 and cid not in on:
                    raise ValueError(f"drive_law: sketch {sk.elem_id} has an edge square to "
                                     f"{axis} inside the slab")
            plan.append(("rigid", sk, side, (h, lines_lo, lines_hi)))
        else:
            raise ValueError(f"drive_law: follower kind {kind!r}")
    locked = {cid for al in _sketch_locks(doc) for cid in _witness_ids(al)}
    claimed: set = set()
    for kind, sk, side, data in plan:
        cids = ([a.elem_id for a in data] if kind == "circle"
                else [ln[0] for ln in data[1] + data[2]])
        # never locked before, and never twice within this follow (a part
        # listed twice, #912 review)
        if any(c in locked or c in claimed for c in cids):
            raise ValueError(f"drive_law: sketch {sk.elem_id} is already locked")
        claimed.update(cids)

    # -- mutations start here
    R = {"lo": add_plane(doc, axis, at["lo"]), "hi": add_plane(doc, axis, at["hi"])}
    dim3d(doc, lo_p, R["lo"], axis, caption=caption)
    eq3d(doc, R["lo"], centre, R["hi"], axis)
    rigid_planes: Dict[tuple, tuple] = {}
    locks = 0
    for kind, sk, side, data in plan:
        if kind == "circle":
            for arc in data:
                align_arc_centre(doc, arc, sk, R[side], axis)
                locks += 1
            continue
        h, lines_lo, lines_hi = data
        key = (side, round(h, 9))
        if key not in rigid_planes:
            a = add_plane(doc, axis, at[side] - h)
            b = add_plane(doc, axis, at[side] + h)
            eq3d(doc, a, R[side], b, axis)
            dim3d(doc, a, b, axis, locked=True, line_step=3)
            rigid_planes[key] = (a, b)
        a, b = rigid_planes[key]
        for ln in lines_lo:
            lock_line(doc, sk, ln, a, axis, "lo")
            locks += 1
        for ln in lines_hi:
            lock_line(doc, sk, ln, b, axis, "hi")
            locks += 1
    return {"caption": caption, "axis": axis, "planes": [R["lo"].elem_id, R["hi"].elem_id],
            "followers": len(plan), "locks": locks, "rigid_pairs": len(rigid_planes)}


def wire_symmetric(doc, base: Dict[str, Any], axis: str = "x"):
    """EQ(lo | origin centre | hi): the drive's ends move symmetrically [ladder
    base, present on every rung that passed]."""
    planes = {p.elem_id: p for p in doc.refplanes}
    centre = origin_centre_plane(doc, axis)
    lo_p, hi_p = planes[base["planes"][0]], planes[base["planes"][1]]
    if abs((plane_at(lo_p, axis) + plane_at(hi_p, axis)) / 2.0
           - plane_at(centre, axis)) > 1e-6:
        # an EQ about a plane that is not midway cannot hold (#912 review)
        raise ValueError("drive_law: the drive's planes are not centred on the origin plane")
    return eq3d(doc, lo_p, centre, hi_p, axis)


def wire_attach(doc, *, items, axis: str) -> Dict[str, Any]:
    """Part edges that RIDE moving planes at their current offsets.

    ``items`` = ``[(VarSketch, lo_plane, hi_plane), ...]``: the sketch's edge
    on the low side of ``axis`` rides ``lo_plane`` and its high-side edge rides
    ``hi_plane`` (either may be ``None`` = that edge stays).  Each edge gets a
    plane at its offset from the plane it rides, held by a LOCKED unlabelled
    dimension from it (offset 0 = that plane itself), and is locked to it --
    the P2 rung's chain (lo -> A locked, A -> B locked), desktop-verified (#904
    "Follow" ladder).  Same plane on both sides = the part rides rigidly (a
    tray rail's web on the width plane); different planes = it stretches with
    the drive (a box wall between front and back).

    All-or-nothing: every item is checked before the first mutation."""
    from . import param_drive as PD
    if doc.finalized:
        raise RuntimeError("drive_law: document is finalized")
    if axis not in ("x", "y"):
        raise ValueError(f"drive_law: attach axis must be 'x' or 'y', not {axis!r}")
    k = 0 if axis == "x" else 1
    locked = {cid for al in _sketch_locks(doc) for cid in _witness_ids(al)}
    claimed: set = set()
    plan = []
    for sk, lo_p, hi_p in items:
        rect = PD._classify_rect(PD._sketch_lines(sk))
        lo_l, hi_l = ((rect["left"], rect["right"]) if axis == "x"
                      else (rect["bottom"], rect["top"]))
        for side, ln, rides in (("lo", lo_l, lo_p), ("hi", hi_l, hi_p)):
            if rides is None:
                continue
            cid, a, b = ln
            if abs(a[k] - b[k]) > 1e-6:
                raise ValueError(f"drive_law: sketch {sk.elem_id} edge is not square to {axis}")
            if cid in locked or cid in claimed:
                raise ValueError(f"drive_law: sketch {sk.elem_id}'s {side} edge is already locked")
            claimed.add(cid)
            plan.append((rides, sk, side, ln, round(a[k] - plane_at(rides, axis), 9)))
    if not plan:
        raise ValueError("drive_law: nothing to attach")
    # -- mutations start here
    made: Dict[tuple, Any] = {}
    n_planes = 0
    keys = sorted({(p[0].elem_id, p[4]): p[0] for p in plan}.items(),
                  key=lambda kv: (kv[0][0], abs(kv[0][1])))
    for i, ((pid, off), plane) in enumerate(keys):
        if off == 0.0:
            made[(pid, off)] = plane
            continue
        made[(pid, off)] = add_plane(doc, axis, plane_at(plane, axis) + off)
        dim3d(doc, plane, made[(pid, off)], axis, locked=True, line_step=4 + i % 3)
        n_planes += 1
    for plane, sk, side, ln, off in plan:
        lock_line(doc, sk, ln, made[(plane.elem_id, off)], axis, side)
    return {"axis": axis, "parts": len({id(p[1]) for p in plan}), "planes": n_planes,
            "locks": len(plan)}

"""rvt.famgen.run_law -- a HORIZONTAL ROUND RUN (a conduit, a pipe stub, a rod
lying down) authored the way Revit-born families build one, with its LENGTH
driven by a family parameter (#913 plan step "the rest").

WHY.  ``factory.add_generic_part`` authors ``cylinder_x`` / ``cylinder_y`` as a
VERTICAL extrusion on the Ref. Level whose cached B-rep alone is rotated onto
the run axis (#591 round 4).  Revit draws the B-rep, so the run displays lying
down, but the sketch still describes a standing cylinder: nothing can drive its
length (that is the extrusion's own start / end, along Z) or label its
diameter (the circle lies in plan), and a regeneration may rebuild it upright
-- the trade #591's own record left "to measure".

THE BORN WAY, read off the 421-family Revit-born reference corpus (the owner's
private library, #836 / #865 -- quarantined, read as a development instrument
only, never copied; counts only, no specimen named):

* **How a round run is built.**  Of every solid form with one circle for a
  profile whose axis is horizontal, 151 are an ``ExtrusionElem`` whose circle
  is sketched ON A VERTICAL PLANE and extruded along that plane's normal
  (147 circles + 4 rings); 8 are sweeps; no revolve has a circle profile.
  The work plane is the origin centre plane square to the run on 74 / 147
  (``m_definesOrigin``; the "Center (Left/Right)" plane for a run along X),
  and the start offset is negative -- the run centred on it -- on 79 / 151.
  Its ``SketchPlane`` carries the plane's own frame as ``m_oTrf.m_3x3``
  (columns = the sketch's x, y and normal), the ``VarSketch.m_pPlane`` that
  frame in world coordinates, ``m_serFlags`` 2 (145 / 160; plan sketches 1),
  header ``m_regenOnly`` [Level, the work plane, ...]; each arc is world
  coordinates on that plane (181 / 193), its centre marker along the normal
  (170 / 193) and its header ``m_regenOnly`` [extrusion, work plane]
  (102 / 193).  The born circle is ONE full ``GArc`` on 147 / 151; this
  engine draws two half arcs (``geometry``) and keeps them -- see GAPS.
* **How its length is driven.**  An END-FACE LOCK: an ``Alignment`` flags 14,
  no cell, owned by no view, one segment (flags 1, locked value 0), header
  ``m_regenOnly`` [UnitsElem] (94 / 94), whose ``m_planeNormal`` is the PLAN
  normal +Z (87 / 94) and whose other witness is a SURFACE-ONLY vertical
  reference plane (no drawn ends, no generating view, header flags 10: 77 /
  77 non-origin planes; the 17 drawn ones are origin planes).  END face
  (geomTag 0): constrained direction -normal (50 / 55), START face
  (geomTag 1): +normal (26 / 28); the plane is the FIRST witness exactly when
  that direction points down its world axis (+X runs: END plane first 31 /
  45, START face first 12 / 17; -Y runs: END face first 9 / 10, START plane
  first 10 / 11 -- height_law's -Z / +Z rule).  Those planes are held by
  PLAN-VIEW dimensions: a labelled one (flags 12, normal +Z, 2 witnesses --
  105) and the EQ about the origin plane (flags 140, 3 witnesses, segments
  flags 2 -- 35).  FamDimConstrMgr rows per locked face as on a Case B height
  (#787): ``m_paramExprs`` 1.0 x the built-in end/start offset (msg 580),
  driven-dim entries (plane +s, SketchPlane -s, lock -s) with s the sign of
  the normal along its axis (47 / 61 on +X runs, 19 / 21 on -Y), ``m_dimSegDataMap`` with
  ``m_dimDir`` the run axis and coefficients (-s, +s), ``m_fixedRefs`` for the
  plane (refFlip 2) and the SketchPlane (refFlip 2 on +normal, 1 on -normal).
* **How its diameter is driven**: a labelled ``RadialDim`` on the circle, in
  the vertical sketch -- ``rvt.famgen.diameter_law`` (type-9 style, 24 of the
  151 born runs; its ``m_planeNormal`` runs along the sketch normal: + on 14 of
  27 labelled diameters, - on 13; this lane writes +, with no dimension
  sketch plane, as 7 of them do).

WHAT HAS A DESKTOP VERDICT AND WHAT DOES NOT (hard rule 4).  A rotated cached
B-rep displays (#514 probe A, #591 round 4).  The in-plane drive and the
"Follow" ladder flex (#787, #904).  NOTHING here has a verdict of its own: a
form sketched on a vertical plane whose sketch, frame and B-rep agree (rounds
1-3 of #591 moved only the datum and kept the B-rep vertical), a face lock to
a vertical plane held by plan dimensions, and a diameter on a vertical circle
are each AUTHORED, the assembled family UNVERIFIED.  Every check in
:func:`wire_run_length` runs before its first mutation.

GAPS, stated rather than hidden: the circle is this engine's two half arcs,
not the born single full arc (147 / 151), so the diameter sits on the [0, pi]
half (``diameter_law``'s own gap); the run's circle centre is not locked to
the origin planes (born runs lock it on 10 / 151 only); the sketch solver
records keep the circle in the sketch's own 2D frame, unverified on a
vertical plane.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import geometry as G
from . import height_law as HL
from .skeleton import _alloc, new_reference_plane

EPS = 1e-6
#: VarSketch.m_serFlags of a sketch on a vertical plane (145 / 160 born runs)
VERTICAL_SKETCH_SER_FLAGS = 2
#: "Is Reference" of a run's end plane: weak (14) -- the born runs' 21 + 10 vs
#: 15 + 3 not-a-reference (12) on X runs; height_law's SURFACE_REF_NAME
END_PLANE_REF_NAME = HL.SURFACE_REF_NAME


class RunError(ValueError):
    """A run length drive was refused; the document is unchanged."""


# --------------------------------------------------------------------------- frames
def _cross(a, b) -> Tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def work_plane(doc, axis: str):
    """The origin centre plane SQUARE to a run along ``axis`` -- the born
    work plane of a centred run (74 / 147): normal X for a run along X."""
    from .drive_law import origin_centre_plane
    return origin_centre_plane(doc, axis)


def plane_frame(rp) -> Tuple[List[float], List[float], List[float], List[float]]:
    """``(origin, x, y, normal)`` of a reference plane's surface."""
    s = rp.obj["m_pSurface"]["value"]
    x = [float(c) for c in s["m_xVec"]]
    y = [float(c) for c in s["m_yVec"]]
    return [float(c) for c in s["m_origin"]], x, y, list(_cross(x, y))


def _k(axis: str) -> int:
    if axis not in ("x", "y"):
        raise RunError(f"run_law: a run lies along 'x' or 'y', not {axis!r}")
    return 0 if axis == "x" else 1


def _box_world(R, box) -> List[List[float]]:
    """World axis-aligned box of a local box under the rotation ``R``."""
    from .orient import _apply
    pts = [_apply(R, (x, y, z)) for x in (box[0][0], box[1][0])
           for y in (box[0][1], box[1][1]) for z in (box[0][2], box[1][2])]
    return [[G._clean(min(p[i] for p in pts)) for i in range(3)],
            [G._clean(max(p[i] for p in pts)) for i in range(3)]]


def _fix_root_bbox(rep, R) -> None:
    if isinstance(rep, dict):
        for key in ("m_bBox", "m_tightbBox"):
            if isinstance(rep.get(key), list) and len(rep[key]) == 2:
                rep[key] = _box_world(R, rep[key])


# --------------------------------------------------------------------------- the form
def add_run_cylinder(doc, *, axis: str, radius_ft: float, length_ft: float,
                     center: Sequence[float] = (0.0, 0.0), base_z_ft: float = 0.0,
                     rep: str = G.REP_SOLID) -> G.FormBundle:
    """A TRUE horizontal cylinder the born way: its circle sketched on the
    origin centre plane square to ``axis`` and extruded along that plane's
    normal.  ``center`` = the plan centre (x, y) of the run, ``base_z_ft`` its
    underside (the axis is at ``base_z_ft + radius_ft``) -- the ``cylinder_x``
    / ``cylinder_y`` part contract.

    Built as the engine's verified upright cylinder cluster in the work
    plane's LOCAL frame (sketch x, sketch y, normal), then every element and
    cached B-rep placed into world by that frame's rotation
    (:func:`rvt.famgen.orient.rotate_record`, the #514 path) and the
    SketchPlane re-hosted on the work plane.  Authored, unverified (module
    docstring)."""
    from .orient import rotate_record
    if doc.finalized:
        raise RunError("run_law: document is finalized")
    k = _k(axis)
    r, L = float(radius_ft), float(length_ft)
    if not (r > 0 and L > 0 and math.isfinite(r) and math.isfinite(L)):
        raise RunError("run_law: a run needs a positive radius and length")
    wp = work_plane(doc, axis)
    o, xv, yv, n = plane_frame(wp)
    if abs(abs(n[k]) - 1.0) > EPS:
        raise RunError(f"run_law: the work plane is not square to {axis}")
    s = 1.0 if n[k] > 0 else -1.0
    centre = [float(center[0]), float(center[1]), float(base_z_ft) + r]
    rel = [centre[i] - o[i] for i in range(3)]
    u = sum(rel[i] * xv[i] for i in range(3))
    v = sum(rel[i] * yv[i] for i in range(3))
    a0, a1 = centre[k] - L / 2.0, centre[k] + L / 2.0
    w0, w1 = sorted((s * (a0 - o[k]), s * (a1 - o[k])))
    R = [[xv[i], yv[i], n[i]] for i in range(3)]         # columns: x, y, normal
    from .factory import geometry_context
    ctx = geometry_context(doc)
    fb = G.cylinder(r, w1 - w0, ctx, doc.ids, base_z_ft=w0, center=(u, v), rep=rep)
    sp = next(e for e in fb.elements if e.class_name == "SketchPlane")
    sk = next(e for e in fb.elements if e.class_name == "VarSketch")
    ex = next(e for e in fb.elements if e.class_name == "ExtrusionElem")
    arcs = [e for e in fb.elements if e.class_name == "CurveElem"]
    local_box = [[u - r, v - r, w0], [u + r, v + r, w1]]
    for el in fb.elements:
        rotate_record(el.obj, R)
        if el.rep is not None:
            rotate_record(el.rep, R)
            _fix_root_bbox(el.rep, R)
    # the SketchPlane rides the work plane: its datum, its frame (m_3x3 = R
    # by the rotation above; origin the plane's own)
    ref = sp.obj["m_oPlaneRef"]["value"]
    ref["m_datumPlaneId"] = wp.elem_id
    sp.obj["m_oTrf"]["value"]["m_or"] = list(o)
    spar = sp.header["m_parents"]["value"]
    spar["m_deletion"] = [wp.elem_id if i == ctx.level_id else i for i in spar["m_deletion"]]
    sp.refs["level"] = wp.elem_id
    sk.obj["m_serFlags"] = VERTICAL_SKETCH_SER_FLAGS
    kpar = sk.header["m_parents"]["value"]
    kpar["m_regenOnly"] = sorted(set(kpar.get("m_regenOnly") or []) | {wp.elem_id})
    for a in arcs:
        apar = a.header["m_parents"]["value"]
        apar["m_regenOnly"] = [wp.elem_id if i == ctx.level_id else i
                               for i in apar.get("m_regenOnly") or []]
    bb = ex.header.get("m_pBBox")
    if isinstance(bb, dict) and isinstance(bb.get("value"), dict):
        bb["value"]["m_minmax"] = _box_world(R, local_box)
    doc.add(*fb.elements)
    fb.params.update({"run_axis": axis, "radius_ft": r, "length_ft": L,
                      "work_plane": wp.elem_id, "normal_sign": s,
                      "run_start": a0, "run_end": a1, "vertical_sketch": True,
                      "centre_cross": centre[1 - k]})
    fb.notes.append(
        f"horizontal run along {axis}: circle sketched on the origin centre plane "
        f"{wp.elem_id} (vertical) and extruded along its normal -- the born way "
        "(151 born round runs); sketch, frame and B-rep agree; authored, no "
        "desktop verdict")
    return fb


def is_run(fb) -> bool:
    return bool((getattr(fb, "params", None) or {}).get("vertical_sketch"))


# --------------------------------------------------------------------------- the length
def _run_of(doc, t):
    """``(ExtrusionElem, SketchPlane, axis, sign, start_at, end_at)`` of a run
    bundle; refuses anything else."""
    params = getattr(t, "params", None) or {}
    if not params.get("vertical_sketch"):
        raise RunError("run_law: target is not a run authored by add_run_cylinder")
    ex = HL.extrusion_of(t)
    sk = HL._sketch_of(doc, ex)
    spid = int(sk.obj["m_sketchPlaneId"])
    sp = next(e for e in doc.by_class("SketchPlane") if e.elem_id == spid)
    axis = params["run_axis"]
    k = _k(axis)
    wp_id = int(sp.obj["m_oPlaneRef"]["value"]["m_datumPlaneId"])
    wp = next((p for p in doc.refplanes if p.elem_id == wp_id), None)
    if wp is None:
        raise RunError("run_law: the run's work plane is not in this document")
    o, _x, _y, n = plane_frame(wp)
    if abs(abs(n[k]) - 1.0) > EPS:
        raise RunError(f"run_law: the run's work plane is not square to {axis}")
    s = 1.0 if n[k] > 0 else -1.0
    pv = HL._pvd(ex)
    # world coordinate along the axis of each cap face: end (tag 0) / start (1)
    at = {"end": o[k] + s * pv[HL.BIP["end"]], "start": o[k] + s * pv[HL.BIP["start"]]}
    return ex, sp, axis, s, at


def _end_plane(doc, axis: str, at: float):
    """A SURFACE-ONLY vertical reference plane square to ``axis`` at ``at``
    (the born end plane of a run): surface x along the other plan axis (+Y
    for an X run, -X for a Y run -- the born modes), y up."""
    from . import drive_law as DL
    c = DL._dim_ctx(doc)
    P = max(c["P"], abs(at) + 1.0)
    if axis == "x":
        free, bubble = (at, -P, 0.0), (at, P, 0.0)
    else:
        free, bubble = (P, at, 0.0), (-P, at, 0.0)
    rp = new_reference_plane(_alloc(doc.ids), c["fam"], name="", ref_name=END_PLANE_REF_NAME,
                             free_end=free, bubble_end=bubble, normal=(0.0, 0.0, 1.0),
                             gen_view_id=-1, extent=((-P, -P), (P, P)), sketch_member=False,
                             flags=HL.SURFACE_HDR_FLAGS)
    HL._surface_only(rp)
    doc.refplanes.append(rp)
    doc.add(rp)
    return rp


def _trace(axis: str, at: float, lo: float, hi: float) -> Tuple[List[float], List[float]]:
    """A plan segment ON the plane ``axis`` = ``at`` from ``lo`` to ``hi``
    along the other plan axis."""
    if axis == "x":
        return [at, lo, 0.0], [at, hi, 0.0]
    return [lo, at, 0.0], [hi, at, 0.0]


def _face_lock(doc, ext, face: str, plane, *, axis: str, sign: float, at: float,
               span: Tuple[float, float]):
    """Alignment flags 14 locking a run's cap face to its vertical end plane
    (the born run law, module docstring): END plane first / START face first
    when the constrained direction points down the world axis, the other order
    when it points up it; constrained direction -normal on END, +normal on
    START; plane normal +Z (the plan)."""
    from . import drive_law as DL
    P = DL._dim_ctx(doc)["P"]
    k = _k(axis)
    tag = HL.FACE_TAG[face]
    nd = [0.0, 0.0, 0.0]
    nd[k] = sign * (-1.0 if face == "end" else 1.0)
    plane_first = nd[k] < 0
    y0, y1 = span
    ym = (y0 + y1) / 2.0
    pl = _trace(axis, at, -P, P)
    fc = _trace(axis, at, y0, y1)
    if plane_first:
        w0 = (plane.elem_id, 0, (pl[0], pl[1]), 0, 0)
        w1 = (ext.elem_id, tag, (fc[0], fc[1]), 0, 0)
        ref = _trace(axis, at, -P - 0.7, y0)
        org = _trace(axis, at, -P, -P)[0]
        ld = [0.0, 0.0, 0.0]
        ld[1 - k] = 1.0
    else:
        w0 = (ext.elem_id, tag, (fc[1], fc[0]), 0, 0)
        w1 = (plane.elem_id, 0, (pl[1], pl[0]), 1, 0)
        mid = _trace(axis, at, ym, ym)
        ref = (mid[0], mid[1])
        org = _trace(axis, at, y1, y1)[0]
        ld = [0.0, 0.0, 0.0]
        ld[1 - k] = -1.0
    al = HL._alignment14(doc, w0, w1, constr_dir=nd, ref_pnts=ref, origin=org,
                         line_dir=ld, seg_origin=_trace(axis, at, ym, ym)[0],
                         plane_normal=(0.0, 0.0, 1.0),
                         deletion=[ext.elem_id, plane.elem_id],
                         appearance=[ext.elem_id, plane.elem_id])
    return al


def _add_rows(doc, ext, sp, face: str, plane, al, *, axis: str, sign: float) -> None:
    """FamDimConstrMgr rows for one locked run face (module docstring)."""
    m = HL._mgr(doc)
    k = HL.FACE_KEY[face]
    s = float(sign)
    dim_dir = [0.0, 0.0, 0.0]
    dim_dir[_k(axis)] = 1.0
    m["m_paramExprs"].append({"first": HL._key(ext.elem_id, k), "second": {
        "m_entries": [{"m_coef": 1.0, "m_paramId": HL.BIP[face]}],
        "m_elemId": ext.elem_id, "m_msgId": HL.MSG_EXTRUSION}})
    entries = sorted([(plane.elem_id, s, 0), (sp.elem_id, -s, -1), (al.elem_id, -s, 0)])
    m["m_drivenDimSegs"].append({"first": HL._key(ext.elem_id, k), "second": {
        "m_oDimValueExpr": {"ptr_class": "DimValueExpr", "pid": -1, "value": {
            "m_entries": [{"m_coeff": c_, "m_dimId": e, "m_seg": sg, "m_mayBeDriven": False}
                          for e, c_, sg in entries], "m_offset": 0.0}}}})
    for f2 in ("end", "start"):
        k2 = HL.FACE_KEY[f2]
        if not HL._has(m["m_dimSegDataMap"], ext.elem_id, k2):
            m["m_dimSegDataMap"].append({"first": HL._key(ext.elem_id, k2), "second": {
                "m_dimDir": list(dim_dir), "m_groupId": -1,
                "m_grefArr": [HL._gref(sp.elem_id, -1), HL._gref(ext.elem_id, HL.FACE_TAG[f2])],
                "m_coefArr": [-s, s]}})
    for e, i, tag, flip in ((plane.elem_id, 0, 0, 2), (sp.elem_id, -1, -1, 2 if s > 0 else 1)):
        if not HL._has(m["m_fixedRefs"], e, i):
            m["m_fixedRefs"].append({"first": HL._key(e, i), "second": {
                "m_gref": HL._gref(e, tag), "m_dimDir": list(dim_dir), "m_groupId": -1,
                "m_refFlip": flip}})
    m["m_propagatedDrivers"].append(HL._key(al.elem_id, 0))
    srt = lambda r: (r["first"]["m_elementId"], r["first"]["m_int64"])  # noqa: E731
    for nm in ("m_paramExprs", "m_drivenDimSegs", "m_dimSegDataMap", "m_fixedRefs"):
        m[nm].sort(key=srt)
    m["m_propagatedDrivers"].sort(key=lambda r: (r["m_elementId"], r["m_int64"]))
    par = ext.header["m_parents"]["value"]
    par["m_regenOnly"] = sorted(set(par.get("m_regenOnly") or []) | {plane.elem_id})


def wire_run_length(doc, *, caption: str, targets: Sequence[Any],
                    symmetric: bool = True) -> Dict[str, Any]:
    """Make family length parameter ``caption`` drive the LENGTH of every run
    in ``targets`` (FormBundles from :func:`add_run_cylinder`, all lying along
    one axis with the same two cap positions): two surface-only end planes at
    the caps, held by a labelled PLAN dimension (and, ``symmetric``, an EQ
    about the origin centre plane), each run's END / START face locked to
    them.

    All-or-nothing: every check runs before the first mutation -- the document
    is not finalized, the parameter exists, is a drivable length/size spec
    and its value equals the run length, every target is a run on one axis
    with the same caps, no cap face is locked already, and (``symmetric``)
    the caps are centred on the origin plane.  Call BEFORE ``finalize``.
    Authored, UNVERIFIED (module docstring)."""
    from . import drive_law as DL
    if doc.finalized:
        raise RuntimeError("run_law: document is finalized")
    pe = doc.params.get(caption)
    if pe is None:
        raise RunError(f"run_law: no family parameter {caption!r}")
    if not DL.drivable_spec(pe):
        raise RunError(f"run_law: {caption} is not a length or size parameter")
    targets = list(targets)
    if not targets:
        raise RunError("run_law: no run to drive")
    if len({id(t) for t in targets}) != len(targets):
        raise RunError("run_law: a run is listed twice")
    runs = [(t, *_run_of(doc, t)) for t in targets]
    axes = {r[3] for r in runs}
    if len(axes) != 1:
        raise RunError("run_law: the runs do not lie along one axis")
    axis = axes.pop()
    k = _k(axis)
    lo = min(runs[0][5].values())
    hi = max(runs[0][5].values())
    for r in runs[1:]:
        if abs(min(r[5].values()) - lo) > EPS or abs(max(r[5].values()) - hi) > EPS:
            raise RunError("run_law: the runs do not share their two cap positions")
    if not hi - lo > EPS:
        raise RunError("run_law: a run has no length")
    rows = doc.types[doc.current_type][1] if doc.types else {}
    cur = rows.get(pe.elem_id)
    if not isinstance(cur, (int, float)) or abs(float(cur) - (hi - lo)) > EPS:
        raise RunError(f"run_law: {caption} is {cur!r} ft but the run is {hi - lo:g} ft long")
    centre = None
    if symmetric:
        centre = DL.origin_centre_plane(doc, axis)
        if abs((lo + hi) / 2.0 - DL.plane_at(centre, axis)) > EPS:
            raise RunError("run_law: the run is not centred on the origin plane")
    locked = HL._existing_face_locks(doc)
    for _t, ex, _sp, _a, _s, _at in runs:
        for f in ("end", "start"):
            if (ex.elem_id, HL.FACE_TAG[f]) in locked:
                raise RunError(f"run_law: extrusion {ex.elem_id}'s {f} face is already locked")
    HL._mgr(doc)
    spans = []
    for _t, ex, sp, _a, _s, _at in runs:
        r = float(_t.params["radius_ft"])
        cy = float(_t.params.get("centre_cross", 0.0))
        spans.append((cy - r, cy + r))
    # -- mutations start here
    planes = {"lo": _end_plane(doc, axis, lo), "hi": _end_plane(doc, axis, hi)}
    dim = DL.dim3d(doc, planes["lo"], planes["hi"], axis, caption=caption)
    eq = DL.eq3d(doc, planes["lo"], centre, planes["hi"], axis) if symmetric else None
    locks: List[int] = []
    for (t, ex, sp, _a, s, at), span in zip(runs, spans):
        for f in ("end", "start"):
            side = "lo" if abs(at[f] - lo) <= EPS else "hi"
            al = _face_lock(doc, ex, f, planes[side], axis=axis, sign=s, at=at[f], span=span)
            _add_rows(doc, ex, sp, f, planes[side], al, axis=axis, sign=s)
            locks.append(al.elem_id)
    return {"caption": caption, "axis": axis, "planes": [planes["lo"].elem_id,
                                                         planes["hi"].elem_id],
            "dim": dim.elem_id, "eq": eq.elem_id if eq is not None else None,
            "locks": locks, "runs": len(runs), "symmetric": bool(symmetric)}


def wire_run_specs(doc, specs: Sequence[Dict[str, Any]],
                   run_of: Dict[str, Optional[Any]]) -> Dict[str, Any]:
    """Wire ``[{"caption", "parts": [run part name, ...], "symmetric": bool}]``;
    each spec all-or-nothing, a refused one is reported (never raised) so
    delivery is never blocked (hard rule 1).  ``run_of`` maps a part name to
    its FormBundle (``None`` when the name is not unique)."""
    rep: Dict[str, Any] = {"specs": len(specs), "wired": 0, "locks": 0, "captions": [],
                           "refused": []}
    for spec in specs:
        cap = spec.get("caption") if isinstance(spec, dict) else None
        try:
            names = list(spec["parts"])
            bad = [n for n in names if run_of.get(n) is None]
            if bad or not names:
                raise RunError(f"part name(s) missing, not unique or not a run: {bad[:4]}")
            r = wire_run_length(doc, caption=spec["caption"],
                                targets=[run_of[n] for n in names],
                                symmetric=bool(spec.get("symmetric", True)))
        except Exception as e:                       # noqa: BLE001 -- never block delivery
            rep["refused"].append({"caption": cap, "why": f"{type(e).__name__}: {str(e)[:120]}"})
            continue
        rep["wired"] += 1
        rep["locks"] += len(r["locks"])
        rep["captions"].append(r["caption"])
    return rep

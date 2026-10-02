"""rvt.famgen.diameter_law -- a circle's DIAMETER labelled with a family
parameter, the way Revit-born families store it (issue #916).

WHY.  The "Follow" ladder's P5 rung (#904) put a LABELLED RADIUS on a circle
(an in-sketch ``RadialDim`` labelled "Rod Radius") and the owner's desktop
Revit flexed it.  Products are sized by DIAMETER (a 3/8 in rod, a 3/4 in
conduit), so a radius parameter beside a "Rod Diameter" that drives nothing is
the wrong shape.  A census of the 421-family Revit-born reference corpus (the
owner's private library, #836 / #865 -- quarantined, read as a development
instrument only, never copied; counts only here) found:

1. A diameter is the SAME class, ``RadialDim``.  What makes it a diameter is
   its STYLE: ``m_styleSymbolId`` names a ``DimensionStyle`` with
   ``m_dimensionStyleType`` 9 (67 / 67 labelled diameters; every labelled
   radius uses type 2 or 0).  Its segment carries the diameter, 2 x the arc
   radius (67 / 67), in ``m_lockedValue`` and ``m_values[0]``.
2. Every born family document carries exactly two type-9 styles of its own
   (421 / 421); the labelled diameters use the one WITHOUT an arrowhead
   (``m_arrowHeadStyleId`` -1) 67 / 67.  Against the document's default
   linear style it differs only in ``m_dimensionStyleType`` 9,
   ``m_radiusDiameterPrefixText`` U+00F8, ``m_radiusDiameterSymbolLocation``
   1, ``m_arrowHeadStyleId`` / ``m_interiorTickMarkStyleId`` -1,
   ``m_radialTickType`` 8, its symbol name and its own text / tick /
   centreline categories + font (header deletion [family, self, 3
   categories, font]; flags 14).
3. The dimension itself is the labelled-radius recipe field for field
   (in-sketch ``SketchMembership``, flags 12, ``m_dimLockedForLabeling``
   True, view -1, ``m_dimVersion`` 6, one segment flags 0, one witness
   {id -1, cached GArc [0, pi] GInfo flags 17301508, ``ArcRef`` geomTag 0},
   header deletion [family, style, parameter, sketch, arc, self], regenOnly
   [the sketch's plane], appearance [style, sketch, arc]; 56 / 67).
4. The labelled arc is a FULL circle (one ``GArc``, endParams [0, 0]) on
   66 / 67, a partial arc once, a HALF arc never.  The alternative -- a
   labelled radius driven by a ``Radius = Diameter / 2`` formula -- appears
   on 31 labelled radii whose source parameter is named as a diameter: the
   direct type-9 label (67) is the majority shape and is the one authored
   here.

THE LABELLED ARC.  This engine draws a plan circle (``geometry.cylinder``)
and a run circle (``run_law``) as ONE full arc, as born circles are (#916;
235 / 235 born single-circle plan extrusions, 147 / 147 runs), so the
dimension goes on that full arc, witness geomTag 0 with a cached [0, pi] arc.
A circle still made of two half arcs (the rotated-B-rep authoring circle,
which this module refuses, #929) would be labelled on its [0, pi] half -- the
arc the verified P5 radius labelled, but a diameter on a half arc is
unattested in the corpus (0 / 67) and is reported as ``half_arc``.  The
type-9 style is authored here from this engine's own default-style
constellation (no donor bytes), and no diameter has a desktop verdict: the
verified P5 radius sat on a half arc, so its verdict does not carry over to a
full arc either -- nothing here claims a diameter flexes (hard rule 4).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence

#: DimensionStyle.m_dimensionStyleType of a diameter style (67 / 67 born
#: labelled diameters) [census #916]
DIAMETER_STYLE_TYPE = 9
#: the diameter symbol a type-9 style prefixes (421 / 421 born styles)
DIAMETER_PREFIX = "ø"
#: GInfo flags of the witness's cached arc (every born radial witness)
CACHED_ARC_FLAGS = 17301508
#: m_dimVersion on born dimensions
BORN_DIM_VERSION = 6
#: header m_nVisibleViewFlags of an IN-SKETCH RadialDim: -1 on 4,308 / 4,308
#: born (every labelled diameter included); -4225 only on the 5 view-owned
#: ones.  The verified P5 radius carried -4225 (the linear-dim constant).
SKETCH_RADIAL_VISIBLE = -1


class DiameterError(ValueError):
    """A diameter label was refused; the document is unchanged."""


def _crv(ce) -> Dict[str, Any]:
    return ce.obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]


def _is_full(ep) -> bool:
    return abs(float(ep[0])) < 1e-12 and abs(float(ep[1])) < 1e-12


def _span(ep) -> float:
    return 2.0 * math.pi if _is_full(ep) else float(ep[1]) - float(ep[0])


def diameter_style(doc):
    """The document's own type-9 (diameter, no arrowhead) DimensionStyle, or
    None when it has none yet."""
    for e in doc.by_class("DimensionStyle"):
        if (int(e.obj.get("m_dimensionStyleType", -1)) == DIAMETER_STYLE_TYPE
                and int(e.obj.get("m_arrowHeadStyleId", 0)) == -1):
            return e
    return None


def author_diameter_style(doc):
    """Author the diameter style from this engine's own default-style
    constellation (``skeleton.new_dimension_style_constellation``): the
    DimensionStyle with its text / tick / centreline categories, their line
    styles and its font -- the leader style dropped, as the born no-arrow
    diameter style references none -- with the born type-9 fields.  Every
    value is ours; nothing is copied from a specimen."""
    from .skeleton import new_dimension_style_constellation
    fam = doc.self_family.elem_id
    style_id, els = new_dimension_style_constellation(doc.ids, fam)
    leader = next(e for e in els if e.class_name == "LeaderStyle")
    leader_cat = int(leader.obj["m_categoryId"])
    leader_g = {g for e in els if e.elem_id == leader_cat
                for g in (e.obj.get("m_gstyleIds") or [])}
    drop = {leader.elem_id, leader_cat} | leader_g
    style = next(e for e in els if e.elem_id == style_id)
    o = style.obj
    o["m_dimensionStyleType"] = DIAMETER_STYLE_TYPE
    o["m_radiusDiameterPrefixText"] = DIAMETER_PREFIX
    o["m_radiusDiameterSymbolLocation"] = 1
    o["m_arrowHeadStyleId"] = -1
    o["m_interiorTickMarkStyleId"] = -1
    o["m_radialTickType"] = 8
    o["m_symbolInfo"]["value"]["m_name"] = "Diameter"
    par = style.header["m_parents"]["value"]
    par["m_deletion"] = [i for i in par["m_deletion"] if i not in drop]
    for e in els:
        if e.elem_id not in drop:
            doc.add(e)
    return style


def _sketch_of(doc, arc_ce):
    dele = set(arc_ce.header["m_parents"]["value"].get("m_deletion") or [])
    return next((s for s in doc.by_class("VarSketch") if s.elem_id in dele), None)


def _geo_sp(doc, sk) -> int:
    sp = next((e for e in doc.by_class("SketchPlane")
               if int(e.obj.get("m_userId", -1)) == sk.elem_id), None)
    return sp.elem_id if sp is not None else -1


def sketch_frame(sk):
    """``(x, y, normal)`` of a sketch's own plane (``VarSketch.m_pPlane``)."""
    pl = ((sk.obj.get("m_pPlane") or {}).get("value") or {})
    x = [float(c) for c in pl.get("m_xVec", (1.0, 0.0, 0.0))]
    y = [float(c) for c in pl.get("m_yVec", (0.0, 1.0, 0.0))]
    n = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]]
    return x, y, n


def _in_plan(sk) -> bool:
    _x, _y, n = sketch_frame(sk)
    return abs(n[0]) < 1e-9 and abs(n[1]) < 1e-9


def circle_of(doc, sk, *, vertical: bool = False):
    """``(label arc, centre, radius)`` of sketch ``sk``'s ONE circle -- one
    full ``GArc``, or arcs about one centre at one radius covering the full
    turn -- else raise :class:`DiameterError`.

    The circle must lie in the PLAN plane; ``vertical=True`` also admits a
    circle in its own sketch's VERTICAL plane (a run authored the born way,
    ``rvt.famgen.run_law``: sketch, frame and B-rep agree).  A plan-sketched
    circle whose B-rep alone is rotated is never admitted (#929)."""
    from .drive_law import _arcs_of
    arcs = _arcs_of(doc, sk)
    if not arcs:
        raise DiameterError(f"sketch {sk.elem_id} has no circle")
    plan = _in_plan(sk)
    if not plan and not vertical:
        raise DiameterError(f"sketch {sk.elem_id}'s circle is not in the plan plane")
    _fx, _fy, n = sketch_frame(sk)
    c0, r0 = _crv(arcs[0])["m_center"], float(_crv(arcs[0])["m_radius"])
    for a in arcs:
        cr = _crv(a)
        if (any(abs(float(cr["m_center"][i]) - float(c0[i])) > 1e-9 for i in range(3))
                or abs(float(cr["m_radius"]) - r0) > 1e-9):
            raise DiameterError(f"sketch {sk.elem_id}'s arcs are not one circle")
        if plan:
            # the plan plane: the dimension's plane normal is +Z
            if abs(float(cr["m_xVec"][2])) > 1e-9 or abs(float(cr["m_yVec"][2])) > 1e-9:
                raise DiameterError(f"sketch {sk.elem_id}'s circle is not in the plan plane")
        elif any(abs(sum(float(cr[f][i]) * n[i] for i in range(3))) > 1e-9
                 for f in ("m_xVec", "m_yVec")):
            # a vertical sketch: the arc must lie in THAT sketch's plane
            raise DiameterError(f"sketch {sk.elem_id}'s circle is not in its sketch plane")
    if abs(sum(_span(_crv(a)["m_endParams"]) for a in arcs) - 2.0 * math.pi) > 1e-6:
        raise DiameterError(f"sketch {sk.elem_id}'s arcs do not close a circle")
    if not (r0 > 0 and math.isfinite(r0)):
        raise DiameterError(f"sketch {sk.elem_id}'s circle has no radius")
    full = [a for a in arcs if _is_full(_crv(a)["m_endParams"])]
    first = [a for a in arcs if abs(float(_crv(a)["m_endParams"][0])) < 1e-12
             and abs(float(_crv(a)["m_endParams"][1]) - math.pi) < 1e-9]
    label = (full or first or [None])[0]
    if label is None:
        raise DiameterError(f"sketch {sk.elem_id}'s circle has no [0, pi] half arc")
    if plan:
        return label, [float(c0[0]), float(c0[1]), 0.0], r0
    return label, [float(c0[0]), float(c0[1]), float(c0[2])], r0


def _labelled_arcs(doc) -> set:
    out = set()
    for d in doc.by_class("RadialDim"):
        for w in d.obj.get("m_witnessRefs") or []:
            g = (((w.get("m_pWitnessRef") or {}).get("value") or {}).get("m_geomRef") or {})
            if "m_elemId" in g:
                out.add(int(g["m_elemId"]))
    return out


def _radial_dim(doc, sk, arc_ce, centre, radius, value, pid, style_id):
    """One labelled in-sketch RadialDim on ``arc_ce`` (the P5 recipe, with the
    diameter's value and style)."""
    from . import geometry as G
    from . import param_drive as PD
    from .skeleton import SkelElement, _alloc, element_header
    from ..genesis.types import blank_object
    fam = doc.self_family.elem_id
    obj = blank_object("RadialDim")
    eid = _alloc(doc.ids)
    for k, v in PD.element_base(eid, cell_list=False,
                                design_option=PD.FAMILY_DESIGN_OPTION).items():
        obj[k] = v
    obj["m_famId"] = fam
    obj["m_ownerDBViewId"] = -1
    obj["m_cellList"] = {"ptr_class": "CellList", "pid": -1, "value": {"m_cells": [
        {"ptr_class": "SketchMembership", "pid": -1, "value": {"m_groupId": sk.elem_id}}]}}
    s45 = 0.7071067811865476
    fx, fy, fn = sketch_frame(sk)
    if _in_plan(sk):
        pt = [centre[0] + radius * s45, centre[1] + radius * s45, 0.0]
        fx, fy, fn = [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]
    else:
        # a run's vertical sketch (run_law): the same 45-degree point, the
        # sketch's own frame and normal (born: m_planeNormal = the sketch
        # normal on a run's labelled diameter)
        pt = [centre[i] + radius * s45 * (fx[i] + fy[i]) for i in range(3)]
    obj["m_refPnts"] = [pt]
    obj["m_oldRefSegEndPnt"] = []
    obj["m_oldRefSegEnd"] = []
    seg = PD._seg_info(locked_value=value, origin=(centre[0], centre[1], centre[2]),
                       param_id=pid, flags=0, seg_value=value, id1=0, id2=-1)
    for v in seg["m_values"]:
        v["m_oTextFields"] = None
    obj["m_ArrSegInfo"] = [seg]
    obj["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"] = {"m_arr": [], "m_maxSize": 0,
                                                       "m_isLazy": False}
    obj["m_lastTrf"] = PD._identity_trf()
    obj["m_planeNormal"] = list(fn)
    obj["m_oldOrigin"] = list(pt)
    obj["m_styleSymbolId"] = int(style_id)
    obj["m_dimSketchPlaneId"] = -1
    obj["m_lastDimSegInfoId"] = {"m_id1": 0, "m_id2": -1}
    obj["m_dimVersion"] = BORN_DIM_VERSION
    obj["m_flags"] = 12
    obj["m_dimLockedForLabeling"] = True
    obj["m_useEqualityFormula"] = False
    obj["m_showLabelGP"] = False
    obj["m_pWitnessRefs"] = []
    garc = blank_object("GArc")
    garc["m_GInfo"] = G.ginfo(category=-1, tag=-1, control_command=0, flags=CACHED_ARC_FLAGS)
    garc.update({"m_endParams": [0.0, math.pi], "m_xVec": list(fx),
                 "m_yVec": list(fy), "m_radius": float(radius),
                 "m_center": list(centre), "m_bFilled": False})
    obj["m_witnessRefs"] = [{
        "m_id": {"m_id": -1}, "m_pWitnessRefInfoBase": None,
        "m_pCachedArc": {"ptr_class": "GArc", "pid": -1, "value": garc},
        "m_pWitnessRef": {"ptr_class": "ArcRef", "pid": -1, "value": {"m_geomRef": {
            "m_intermediateTags": [], "m_oNextRef": None, "m_elemId": arc_ce.elem_id,
            "m_ownerDBViewId": -1, "m_foreignElemIdRef": {"m_id64": -1}, "m_geomTag": 0,
            "m_subTag": -1, "m_famMemberIdx": -1, "m_flags": 0, "m_isLazyRef": False}}},
        "m_pOwningDimension": {"weakref": 2}}]
    obj["m_origin"] = list(pt)
    obj["m_center"] = list(centre)
    obj["m_centerOffset"] = [0.0, 0.0, 0.0]
    obj["m_distance"] = 0.0
    obj["m_hasRegenerated"] = True
    G.assign_pids(obj)
    dele = sorted({fam, int(style_id), int(pid), sk.elem_id, arc_ce.elem_id, eid})
    hdr = element_header("RadialDim", category=PD.CAT_DIMENSIONS, deletion=dele,
                         regen_only=[_geo_sp(doc, sk)],
                         appearance=sorted({int(style_id), sk.elem_id, arc_ce.elem_id}),
                         flags=PD.HDR_FLAGS, visible_view_flags=SKETCH_RADIAL_VISIBLE,
                         family_id=fam, owner_view=-1)
    el = SkelElement(eid, "RadialDim", hdr, obj, None, kind="diameter_dim",
                     owner_id=sk.elem_id, refs={"sketch": sk.elem_id, "param": int(pid)},
                     notes=["labelled diameter (#916): authored, no desktop verdict"])
    doc.add(el)
    sk.obj["m_dimIds"] = list(sk.obj.get("m_dimIds") or []) + [eid]
    par = sk.header["m_parents"]["value"]
    par["m_deletion"] = sorted(set(par["m_deletion"]) | {eid})
    return el


def wire_diameter(doc, *, caption: str, sketches: Sequence[Any],
                  vertical: Sequence[Any] = ()) -> Dict[str, Any]:
    """Label the ONE circle of every sketch in ``sketches`` with family
    parameter ``caption`` as its DIAMETER (the born type-9 ``RadialDim``).

    All-or-nothing: every check runs before the first mutation -- the
    document is not finalized, the parameter exists and is a drivable spec
    (length / conduit / cable-tray / pipe size), every sketch holds exactly
    one plan circle no RadialDim labels yet, no sketch is listed twice, and
    the parameter's current value equals 2 x every circle's radius.  The
    document's diameter style is authored on first use and reused after.
    ``vertical`` lists the sketches that are a RUN's vertical sketch
    (``rvt.famgen.run_law``): their circle lies in that sketch's own plane
    and the dimension takes its frame and normal (authored, no verdict).

    Call BEFORE ``finalize``.  Authored, unverified: no diameter has a
    desktop verdict (hard rule 4)."""
    from .drive_law import _arcs_of, drivable_spec
    if doc.finalized:
        raise RuntimeError("diameter_law: document is finalized")
    pe = doc.params.get(caption)
    if pe is None:
        raise DiameterError(f"diameter_law: no family parameter {caption!r}")
    if not drivable_spec(pe):
        raise DiameterError(f"diameter_law: {caption} is not a length or size parameter")
    sketches = list(sketches)
    if not sketches:
        raise DiameterError("diameter_law: no circle to label")
    if len({s.elem_id for s in sketches}) != len(sketches):
        raise DiameterError("diameter_law: a sketch is listed twice")
    rows = doc.types[doc.current_type][1] if doc.types else {}
    current = rows.get(pe.elem_id)
    labelled = _labelled_arcs(doc)
    plan: List[tuple] = []
    for sk in sketches:
        arc, centre, r = circle_of(doc, sk, vertical=any(sk is v for v in vertical))
        if any(a.elem_id in labelled for a in _arcs_of(doc, sk)):
            raise DiameterError(f"diameter_law: sketch {sk.elem_id}'s circle is already "
                                "dimensioned")
        if not isinstance(current, (int, float)) or abs(float(current) - 2.0 * r) > 1e-6:
            raise DiameterError(
                f"diameter_law: {caption} is {current!r} ft but sketch {sk.elem_id}'s "
                f"circle is {2.0 * r:g} ft across")
        plan.append((sk, arc, centre, r))
    # -- mutations start here
    style = diameter_style(doc)
    authored = style is None
    if style is None:
        style = author_diameter_style(doc)
    dims = [_radial_dim(doc, sk, arc, centre, r, 2.0 * r, pe.elem_id, style.elem_id).elem_id
            for sk, arc, centre, r in plan]
    return {"caption": caption, "dims": dims, "circles": len(plan),
            "style": style.elem_id, "style_authored": authored,
            "half_arc": [not _is_full(_crv(arc)["m_endParams"]) for _sk, arc, _c, _r in plan]}


def wire_diameter_specs(doc, specs: Sequence[Dict[str, Any]],
                        sketch_of: Dict[str, Optional[Any]],
                        rotated: Optional[set] = None,
                        runs: Optional[set] = None) -> Dict[str, Any]:
    """Wire ``[{"caption", "parts": [part name, ...]}]``; each spec is
    all-or-nothing, a refused one is reported (never raised) so delivery is
    never blocked (hard rule 1).  ``rotated`` names parts whose B-rep is
    rotated (cylinder_x / cylinder_y): their sketch is the vertical AUTHORING
    circle, not the drawn geometry, so a spec naming one is refused (#929).
    ``runs`` names parts authored the born way (``run_law``): a circle on a
    vertical sketch whose frame and B-rep agree, labelled in that plane."""
    rep: Dict[str, Any] = {"specs": len(specs), "wired": 0, "dims": 0,
                           "captions": [], "refused": []}
    for spec in specs:
        cap = spec.get("caption") if isinstance(spec, dict) else None
        try:
            names = list(spec["parts"])
            bad = [n for n in names if sketch_of.get(n) is None]
            if bad or not names:
                raise DiameterError(f"part name(s) missing or not unique: {bad[:4]}")
            off = [n for n in names if n in (rotated or ())]
            if off:
                raise DiameterError(
                    f"{off[:4]}: a horizontal (rotated B-rep) cylinder -- no in-plane "
                    "mechanism is probed off the plan plane")
            r = wire_diameter(doc, caption=spec["caption"],
                              sketches=[sketch_of[n] for n in names],
                              vertical=[sketch_of[n] for n in names if n in (runs or ())])
        except Exception as e:                       # noqa: BLE001 -- never block delivery
            rep["refused"].append({"caption": cap, "why": f"{type(e).__name__}: {str(e)[:120]}"})
            continue
        rep["wired"] += 1
        rep["dims"] += len(r["dims"])
        rep["captions"].append(r["caption"])
        rep["half_arc"] = rep.get("half_arc", False) or any(r["half_arc"])
    return rep

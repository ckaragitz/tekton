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

from typing import Any, Dict, List

#: the curve GInfo bit set on 24,209 / 24,213 born sketch curves [census]
CURVE_BORN_BIT = 0x80000
#: m_dimVersion on born dimensions (36k records; 0 on the other 4k) [census]
BORN_DIM_VERSION = 6


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
    doc.notes.append(
        "in-plane drive rewritten to the Revit-born law (#787): "
        + ("WITH" if regen_edge else "WITHOUT (control)")
        + f" the sketch regen edge; {len(rep['locks'])} sketch locks view-less, "
        f"{len(rep['labelled'])} labelled dims, {rep['constr_info_cleared']} "
        "back-edges cleared -- NOT desktop-verified (hard rule 4)")
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
                      targets) -> Dict[str, Any]:
    """Make family parameter ``caption`` drive the distance between two new
    reference planes at ``lo`` / ``hi`` (feet, along ``axis`` 'x' or 'y'), and
    lock the matching edge of every target part's rectangular sketch to them.

    ``targets`` = ``[(VarSketch element, ("lo",) | ("hi",) | ("lo", "hi"))]``:
    a part whose ends both follow the parameter (a full-length web) lists both
    sides; the end segment of a slotted back lists only its outer side.

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

    planes = {"lo": _plane(lo), "hi": _plane(hi)}

    def _p3(p):
        return (float(p[0]), float(p[1]), 0.0)

    def _plane_ends(rp):
        return (_p3(rp.obj["m_freeEnd"]), _p3(rp.obj["m_bubbleEnd"]))

    side_key = {("x", "lo"): "left", ("x", "hi"): "right",
                ("y", "lo"): "bottom", ("y", "hi"): "top"}
    locks: List[int] = []
    for sk, sides in targets:
        rect = PD._classify_rect(PD._sketch_lines(sk))
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

    value = abs(hi - lo)
    # the labelled dimension must agree with the parameter it carries: a
    # mismatch would draw one size and report another (#907 review)
    rows = doc.types[doc.current_type][1] if doc.types else {}
    current = rows.get(pe.elem_id)
    if isinstance(current, (int, float)) and abs(float(current) - value) > 1e-6:
        raise ValueError(f"drive_law: {caption} is {float(current):g} ft but its planes "
                         f"are {value:g} ft apart")
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
    return {"caption": caption, "axis": axis, "planes": [planes["lo"].elem_id,
                                                         planes["hi"].elem_id],
            "locks": locks, "dim": dim.elem_id, "targets": len(targets)}

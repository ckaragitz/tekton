"""rvt.famgen.height_law -- a family parameter drives an EXTRUSION'S HEIGHT the
way Revit-born families store it (issue #787 Case B, plan step 3 of #913).

WHY.  ``drive_law`` authors the IN-PLANE drive (a sketch edge locked to a
vertical reference plane), which the owner's desktop verified (#787, #904).
A parameter that moves an extrusion's top or bottom is a different chain: the
cap FACE of the solid is locked to a HORIZONTAL reference plane, and that plane
is held by a dimension drawn in an elevation.  The law below was read off a
Revit-born corpus (the owner's private reference library, #836 / #865 --
quarantined, never copied; field facts and counts only, no specimen named):

* **Horizontal reference plane** (a user's): SURFACE-ONLY -- ``m_freeEnd``,
  ``m_bubbleEnd``, ``m_cutVec`` and ``m_refPointsForNewViews`` all zero,
  ``m_genDbViewId`` -1, no cell list, header ``m_abFlags4Bytes`` 10 and
  deletion parents ``[Family, self]``; its datum geom step is version 1 /
  flags 761725 in a step list with flags 11 and
  ``m_latestGStepTypeInPrevRegenCycle`` all 0; the geom table's
  ``m_maxSafeTag`` and ``m_lastCheckedKingsUserModificationDate`` are -1
  (fields of the pre-2026 schemas only; the release port writes -1).
  (A census of 823 surface-only horizontal planes in 160 born files: geom
  step 817 / 823, no cells 789, header flags 10 on 800; a horizontal plane
  with drawn ends is, but for 12, the template's origin plane.)
* **Origin elevation plane**: the template's own horizontal plane at z 0
  (``m_refName`` 12, ``m_definesOrigin``, drawn in an elevation, ``m_cutVec``
  (0, 1, 0)), held to the Level by an ``Alignment`` flags 14.  Our documents
  have none; :func:`wire_height_drive` adds it, in that born drawn form, the
  first time a chain starts at z 0.
* **Labelled height**: a ``LinearDimString`` flags 12 owned by an ELEVATION
  view, ``m_planeNormal`` = that view's direction, witnesses [hi plane, lo
  plane], dimension version 6, header ``m_regenOnly`` ``[UnitsElem]``; in no
  manager table.  One parameter may label several dimensions.  An unlabelled
  dimension that must hold its distance carries segment flags bit 0.
* **Face lock**: an ``Alignment`` flags 14, no cell, owner view -1 (object
  and header), one segment (flags 1, locked value 0), header ``m_regenOnly``
  ``[UnitsElem]``.  END face (geomTag 0): witnesses [plane g0, extrusion g0],
  constrained direction -Z.  START face (geomTag 1): [extrusion g1, plane],
  +Z.
* **Extrusion header** ``m_regenOnly`` gains every plane its faces are locked
  to (888 / 888 locked faces).
* **FamDimConstrMgr rows** per locked face (key extrusion / -1 end, -2
  start): ``m_paramExprs`` [1.0 x the built-in end/start offset], msg 580;
  ``m_drivenDimSegs`` (+1 plane seg 0, -1 SketchPlane seg -1, -1 lock seg
  0); ``m_dimSegDataMap`` rows for both faces; ``m_fixedRefs`` for the plane
  and the SketchPlane, refFlip 2; ``m_propagatedDrivers`` the lock.

NOTHING here claims a height flexes: no Case B element has a desktop verdict
(hard rule 4).  Every check in :func:`wire_height_drive` runs before its first
mutation, so a refused drive leaves the document exactly as it was.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import geometry as G
from . import param_drive as PD
from . import skeleton as SK
from .skeleton import SPEC_LENGTH, _alloc, element_header, new_reference_plane

#: m_dimVersion on born dimensions [census, as drive_law]
BORN_DIM_VERSION = 6
FACE_TAG = {"end": 0, "start": 1}
FACE_KEY = {"end": -1, "start": -2}
BIP = {"end": G.BIP_EXTRUSION_END, "start": G.BIP_EXTRUSION_START}
#: m_msgId of every born extrusion ParamExpr row (1,175 / 1,175)
MSG_EXTRUSION = 580
EPS = 1e-6

#: the born SURFACE-ONLY horizontal plane [census, 823 planes / 160 files]
SURFACE_GSTEP_VERSION = 1
SURFACE_GSTEP_FLAGS = 761725
SURFACE_GSTEP_LIST_FLAGS = 11
SURFACE_HDR_FLAGS = 10
SURFACE_REF_NAME = 14          # "weak" (14: 289 + 110 + ...; 12: the rest)


# --------------------------------------------------------------------------- context
def _state(doc) -> Dict[str, Any]:
    st = getattr(doc, "_height_law", None)
    if st is None:
        st = {"positioned": set(), "origin": None, "locked": set(), "dims": [],
              "locks": [], "planes": [], "line": 0}
        doc._height_law = st
    return st


def report(doc) -> Dict[str, Any]:
    """Counts of what the height law authored on ``doc`` (empty when none)."""
    st = getattr(doc, "_height_law", None)
    if not st:
        return {}
    exts = {e for e, _t in st["locked"]}
    return {"dims": len(st["dims"]), "planes": len(st["planes"]),
            "face_locks": len(st["locks"]), "extrusions_locked": len(exts),
            "both_faces": sum(1 for e in exts
                              if (e, 0) in st["locked"] and (e, 1) in st["locked"]),
            "origin_plane": st["origin"].elem_id if st["origin"] is not None else None}


def _ctx(doc) -> Dict[str, Any]:
    views = {e.obj.get("m_viewName"): e for e in doc.by_class("DBViewSection")}
    front = views.get("Front")
    units = [e.elem_id for e in doc.by_class("UnitsElem")]
    levels = doc.by_class("Level")
    return {"fam": doc.self_family.elem_id, "style": int(doc.dim_style_id),
            "front": front, "units": units[0] if units else -1,
            "level": levels[0] if levels else None,
            "view_dir": [float(c) for c in
                         (front.obj.get("m_viewDir") if front else (0, -1, 0))]}


def _p(v) -> List[float]:
    return [float(c) for c in v]


def extrusion_of(t):
    """The ExtrusionElem of a target: the element itself or a FormBundle's one."""
    if hasattr(t, "elements"):             # FormBundle
        ex = [e for e in t.elements if e.class_name == "ExtrusionElem"]
        if len(ex) != 1:
            raise ValueError("height_law: form bundle without exactly one extrusion")
        return ex[0]
    if getattr(t, "class_name", None) != "ExtrusionElem":
        raise ValueError(f"height_law: target is not an ExtrusionElem ({t!r:.60})")
    return t


def _pvd(ext) -> Dict[int, float]:
    return {int(x["m_paramId"]): float(x["m_value"])
            for x in ext.obj["m_pParamValueSetDouble"]["value"]["m_paramSet"]}


def _sketch_of(doc, ext):
    cells = ext.obj["m_cellList"]["value"]["m_cells"]
    sid = next(c["value"]["m_sketchId"] for c in cells
               if c["ptr_class"] == "ExtrusionElemExtrusionHelper")
    return next(e for e in doc.by_class("VarSketch") if e.elem_id == sid)


def _sp_of(doc, ext):
    """The extrusion's SketchPlane; refuses anything but a Level-hosted,
    identity-transform (horizontal, z = level = 0) sketch plane."""
    sk = _sketch_of(doc, ext)
    spid = int(sk.obj["m_sketchPlaneId"])
    sp = next(e for e in doc.by_class("SketchPlane") if e.elem_id == spid)
    ref = sp.obj["m_oPlaneRef"]["value"]
    lvl = _ctx(doc)["level"]
    trf = sp.obj["m_oTrf"]["value"]
    if lvl is None or int(ref["m_datumPlaneId"]) != lvl.elem_id:
        raise ValueError(f"height_law: extrusion {ext.elem_id}'s sketch is not on the Level")
    if trf["m_3x3"] != [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]] or \
            any(abs(float(c)) > EPS for c in trf["m_or"]):
        raise ValueError(f"height_law: extrusion {ext.elem_id}'s sketch plane is transformed")
    return sp


def face_z(doc, ext, face: str) -> float:
    """z (ft) of an extrusion's ``start`` / ``end`` cap face."""
    _sp_of(doc, ext)
    return _pvd(ext)[BIP[face]]


def _x_extent(doc, ext) -> Tuple[float, float]:
    """x range of the extrusion's profile (its face as the Front view sees it)."""
    sk = _sketch_of(doc, ext)
    xs: List[float] = []
    for ce in doc.by_class("CurveElem"):
        if sk.elem_id not in (ce.header["m_parents"]["value"].get("m_deletion") or []):
            continue
        cr = ce.obj["m_pCurveDriver"]["value"]["m_pCrv"]
        v = cr["value"]
        if cr["ptr_class"] == "GLine":
            o, d = v["m_origin"], v["m_dirVec"]
            for t in v["m_endParams"]:
                xs.append(float(o[0]) + float(d[0]) * float(t))
        elif cr["ptr_class"] == "GArc":
            r = float(v.get("m_radius", 0.0))
            xs += [float(v["m_center"][0]) - r, float(v["m_center"][0]) + r]
    if not xs:
        raise ValueError(f"height_law: no profile curves for extrusion {ext.elem_id}")
    return min(xs), max(xs)


def plane_z(rp) -> float:
    """z (ft) of a horizontal, +Z-facing reference plane; refuses any other."""
    s = rp.obj["m_pSurface"]["value"]
    x, y = s["m_xVec"], s["m_yVec"]
    n = (x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0])
    if abs(abs(n[2]) - 1.0) > EPS:
        raise ValueError(f"height_law: plane {rp.elem_id} is not horizontal")
    if n[2] < 0:
        raise ValueError(f"height_law: plane {rp.elem_id} faces -Z "
                         "(the coefficient law assumes +Z)")
    return float(s["m_origin"][2])


def _P(doc) -> float:
    P = 5.0
    for rp in doc.refplanes:
        P = max(P, PD._seg_length((rp.obj["m_freeEnd"], rp.obj["m_bubbleEnd"])) / 2.0)
    return P


def _zline(rp, P) -> Tuple[List[float], List[float]]:
    z = plane_z(rp)
    return ([-P, 0.0, z], [P, 0.0, z])


def _existing_face_locks(doc) -> set:
    out = set()
    for al in doc.by_class("Alignment"):
        for w in al.obj.get("m_witnessRefs") or []:
            g = w["m_pWitnessRef"]["value"]["m_geomRef"]
            out.add((int(g["m_elemId"]), int(g["m_geomTag"])))
    return out


# --------------------------------------------------------------------------- planes
def _surface_only(rp) -> None:
    """Rewrite a freshly built horizontal plane to the born SURFACE-ONLY form
    (module docstring): no drawn ends, no generating view, no cells."""
    o = rp.obj
    o["m_freeEnd"] = [0.0, 0.0, 0.0]
    o["m_bubbleEnd"] = [0.0, 0.0, 0.0]
    o["m_cutVec"] = [0.0, 0.0, 0.0]
    o["m_refPointsForNewViews"] = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
    o["m_genDbViewId"] = -1
    o["m_cellList"] = None
    gs = o["m_geomSteps"]["value"]
    step = gs["m_nonBRepGList"][0]["value"]
    step["m_version"] = SURFACE_GSTEP_VERSION
    step["m_flags"] = SURFACE_GSTEP_FLAGS
    gs["m_flags"] = SURFACE_GSTEP_LIST_FLAGS
    gs["m_latestGStepTypeInPrevRegenCycle"] = [0, 0, 0, 0, 0]
    # GeomTable m_maxSafeTag / m_lastCheckedKingsUserModificationDate are -1 in
    # born files.  The 2026 schema has no such fields and the 2025/2024 port
    # writes -1 for them when the object lacks them (release_ctx), so they are
    # NOT set here: two keys the native schema does not carry made the
    # in-memory roundtrip unequal (byte-exact, value-unequal) on every surface
    # plane (#914 DONE 3; the written bytes are identical either way)
    hdr = rp.header
    hdr["m_abFlags4Bytes"] = SURFACE_HDR_FLAGS
    par = hdr["m_parents"]["value"]
    par["m_deletion"] = sorted({int(rp.obj["m_famId"]), rp.elem_id})
    rp.refs["gen_view"] = -1


def _new_zplane(doc, z: float, *, origin: bool = False):
    c = _ctx(doc)
    P = _P(doc)
    if origin:
        # the template's origin elevation plane, in its born DRAWN form
        rp = new_reference_plane(
            _alloc(doc.ids), c["fam"], name="", ref_name="not_a_reference",
            free_end=(-P, 0.0, z), bubble_end=(P, 0.0, z), normal=(0.0, 1.0, 0.0),
            gen_view_id=c["front"].elem_id, extent=((-P, -P), (P, P)),
            defines_origin=True, sketch_member=True)
    else:
        # a user plane: x axis -X, y axis -Y (normal +Z, the census mode),
        # origin (0, 0, z); then the surface-only fields
        rp = new_reference_plane(
            _alloc(doc.ids), c["fam"], name="", ref_name=SURFACE_REF_NAME,
            free_end=(P, 0.0, z), bubble_end=(-P, 0.0, z), normal=(0.0, -1.0, 0.0),
            gen_view_id=-1, extent=((-P, -P), (P, P)), sketch_member=False,
            flags=SURFACE_HDR_FLAGS)
        _surface_only(rp)
    doc.refplanes.append(rp)
    doc.add(rp)
    _state(doc)["planes"].append(rp.elem_id)
    return rp


def _hdr(cls, *, cat, deletion, regen, appearance, fam):
    return element_header(cls, category=cat, deletion=sorted(set(deletion) - {-1}),
                          regen_only=list(regen), appearance=sorted(set(appearance) - {-1}),
                          flags=PD.HDR_FLAGS, visible_view_flags=PD.HDR_VISIBLE,
                          family_id=fam, owner_view=-1)


def _born_eq_arr() -> dict:
    a = PD._equality_arr()
    a["m_arr"][0]["m_id"] = {"m_id1": 2, "m_id2": -1}
    return a


def _alignment14(doc, w0, w1, *, constr_dir, ref_pnts, origin, line_dir, seg_origin,
                 plane_normal, deletion, appearance):
    """A 3D Alignment, flags 14, no cell, owned by no view.
    w = (elem_id, geomTag, (end_a, end_b), oldRefSegEndIdx, constrFlags)."""
    from ..genesis.types import blank_object
    c = _ctx(doc)
    eid = _alloc(doc.ids)
    o = blank_object("Alignment")
    PD._dimension_common(o, eid, c["fam"], -1, c["style"])
    o["m_cellList"] = None
    o["m_refPnts"] = [_p(ref_pnts[0]), _p(ref_pnts[1])]
    seg = PD._seg_info(locked_value=0.0, origin=seg_origin, param_id=-1, flags=1,
                       seg_value=0.0)
    for v in seg["m_values"]:
        v["m_oTextFields"] = None
    o["m_ArrSegInfo"] = [seg]
    o["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"] = _born_eq_arr()
    o["m_lastDimSegInfoId"] = {"m_id1": 2, "m_id2": -1}
    o["m_oldOrigin"] = _p(origin)
    o["m_flags"] = 14
    o["m_dimLockedForLabeling"] = False
    o["m_dimVersion"] = BORN_DIM_VERSION
    o["m_planeNormal"] = _p(plane_normal)
    ws = []
    for k, (tid, tag, ends, idx, cf) in enumerate((w0, w1)):
        w = PD._witness(tid, ends=(ends[0], ends[1]), ref_length=PD._seg_length(ends),
                        wid=k, end_idx=idx, constr_flags=cf)
        w["m_pWitnessRef"]["value"]["m_geomRef"]["m_geomTag"] = int(tag)
        ws.append(w)
    o["m_witnessRefs"] = ws
    o["m_pDimLine"] = PD._dim_line(origin, line_dir)
    o["m_orientType"] = 0
    o["m_constrDir"] = _p(constr_dir)
    G.assign_pids(o)
    hdr = _hdr("Alignment", cat=PD.CAT_ALIGNMENTS,
               deletion=list(deletion) + [c["fam"], c["style"], eid],
               regen=[c["units"]] if c["units"] >= 0 else [],
               appearance=list(appearance) + [c["style"], c["units"]], fam=c["fam"])
    el = SK.SkelElement(eid, "Alignment", hdr, o, None, kind="alignment",
                        owner_id=c["fam"], refs={"family": c["fam"]})
    doc.add(el)
    return el


def _find_origin(doc):
    for rp in doc.refplanes:
        try:
            if rp.obj.get("m_definesOrigin") and abs(plane_z(rp)) < EPS:
                return rp
        except ValueError:
            continue
    return None


def _ensure_origin(doc):
    """The template's origin elevation plane + its lock to the Level."""
    st = _state(doc)
    if st["origin"] is not None:
        return st["origin"]
    rp = _find_origin(doc)
    if rp is not None:
        st["origin"] = rp
        st["positioned"].add(rp.elem_id)
        return rp
    c = _ctx(doc)
    P = _P(doc)
    rp = _new_zplane(doc, 0.0, origin=True)
    lv = c["level"]
    _alignment14(doc,
                 (rp.elem_id, 0, ([P, 0.0, 0.0], [-P, 0.0, 0.0]), 0, 8),
                 (lv.elem_id, 0, ([P, 0.0, 0.0], [-P, 0.0, 0.0]), 0, 1),
                 constr_dir=(0.0, 0.0, -1.0),
                 ref_pnts=((P + 0.7, 0.0, 0.0), (P + 0.7, 0.0, 0.0)),
                 origin=(P, 0.0, 0.0), line_dir=(-1.0, 0.0, 0.0),
                 seg_origin=(0.2, 0.0, 0.0), plane_normal=c["view_dir"],
                 deletion=[rp.elem_id, lv.elem_id], appearance=[rp.elem_id, lv.elem_id])
    st["origin"] = rp
    st["positioned"].add(rp.elem_id)
    return rp


def _zdim(doc, hi, lo, *, param_id: int, locked: bool):
    """Elevation LinearDimString between horizontal planes hi / lo."""
    c = _ctx(doc)
    st = _state(doc)
    P = _P(doc)
    zh, zl = plane_z(hi), plane_z(lo)
    st["line"] += 1
    xr = -(P - PD.REFPNT_INSET)
    xd = xr + 0.177 + 0.25 * st["line"]          # staggered dimension lines
    mid = (zh + zl) / 2.0
    dim = PD.new_labeled_dim(
        _alloc(doc.ids), c["fam"], param_id=param_id, ref_a_id=hi.elem_id,
        ref_b_id=lo.elem_id, style_id=c["style"], value=abs(zh - zl),
        ref_a_ends=_zline(hi, P), ref_b_ends=_zline(lo, P),
        ref_pnts=((xr, 0.0, zh), (xr, 0.0, zl)), seg_origin=(xd, 0.0, mid),
        dim_line_origin=(xd, 0.0, mid), dim_line_dir=(0.0, 0.0, -1.0 if zh > zl else 1.0),
        view_id=c["front"].elem_id, sketch_plane_id=-1, seg_flags=0)
    o = dim.obj
    o["m_planeNormal"] = list(c["view_dir"])
    o["m_dimVersion"] = BORN_DIM_VERSION
    o["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"] = _born_eq_arr()
    o["m_lastDimSegInfoId"] = {"m_id1": 2, "m_id2": -1}
    seg = o["m_ArrSegInfo"][0]
    for v in seg["m_values"]:
        v["m_oTextFields"] = None
    if param_id < 0:
        o["m_dimLockedForLabeling"] = False
        seg["m_paramId"] = -1
        seg["m_flags"] = 1 if locked else 0
    G.assign_pids(o)
    par = dim.header["m_parents"]["value"]
    if c["units"] >= 0:
        par["m_regenOnly"] = [c["units"]]
        par["m_appearanceParents"] = sorted(set(par["m_appearanceParents"]) | {c["units"]})
    doc.add(dim)
    st["dims"].append(dim.elem_id)
    return dim


def _face_lock(doc, ext, face: str, plane):
    """Alignment flags 14 locking an extrusion cap face to a horizontal plane."""
    c = _ctx(doc)
    P = _P(doc)
    z = plane_z(plane)
    x0, x1 = _x_extent(doc, ext)
    xm = (x0 + x1) / 2.0
    pl = _zline(plane, P)
    tag = FACE_TAG[face]
    if face == "end":       # plane first, constrDir -Z
        w0 = (plane.elem_id, 0, (pl[0], pl[1]), 0, 0)
        w1 = (ext.elem_id, tag, ([x0, 0.0, z], [x1, 0.0, z]), 0, 0)
        cd, rp_, org, ld = ((0.0, 0.0, -1.0), ((-P - 0.7, 0.0, z), (x0, 0.0, z)),
                            (-P, 0.0, z), (1.0, 0.0, 0.0))
    else:                   # face first, plane second (idx 1), constrDir +Z
        w0 = (ext.elem_id, tag, ([x1, 0.0, z], [x0, 0.0, z]), 0, 0)
        w1 = (plane.elem_id, 0, (pl[1], pl[0]), 1, 0)
        cd, rp_, org, ld = ((0.0, 0.0, 1.0), ((xm, 0.0, z), (xm, 0.0, z)),
                            (x1, 0.0, z), (-1.0, 0.0, 0.0))
    al = _alignment14(doc, w0, w1, constr_dir=cd, ref_pnts=rp_, origin=org, line_dir=ld,
                      seg_origin=(xm, 0.0, z), plane_normal=c["view_dir"],
                      deletion=[ext.elem_id, plane.elem_id],
                      appearance=[ext.elem_id, plane.elem_id])
    _state(doc)["locks"].append(al.elem_id)
    return al


# --------------------------------------------------------------------------- manager rows
def _mgr(doc) -> Dict[str, Any]:
    m = doc.self_family.obj.get("m_oFamDimConstrMgr")
    if not m or not isinstance(m.get("value"), dict):
        raise ValueError("height_law: family has no FamDimConstrMgrImpl")
    v = m["value"]
    for nm in ("m_paramExprs", "m_drivenDimSegs", "m_dimSegDataMap", "m_fixedRefs",
               "m_propagatedDrivers"):
        if not isinstance(v.get(nm), list):
            raise ValueError(f"height_law: FamDimConstrMgr has no {nm} table")
    return v


def _key(e, i) -> Dict[str, int]:
    return {"m_elementId": int(e), "m_int64": int(i)}


def _gref(e, tag) -> Dict[str, Any]:
    return {"m_intermediateTags": [], "m_oNextRef": None, "m_elemId": int(e),
            "m_ownerDBViewId": -1, "m_foreignElemIdRef": {"m_id64": -1},
            "m_geomTag": int(tag), "m_subTag": -1, "m_famMemberIdx": -1,
            "m_flags": 0, "m_isLazyRef": False}


def _has(rows, e, i) -> bool:
    return any(r["first"]["m_elementId"] == e and r["first"]["m_int64"] == i for r in rows)


def _add_rows(doc, ext, face: str, plane, al) -> None:
    m = _mgr(doc)
    sp = _sp_of(doc, ext)
    k = FACE_KEY[face]
    m["m_paramExprs"].append({"first": _key(ext.elem_id, k), "second": {
        "m_entries": [{"m_coef": 1.0, "m_paramId": BIP[face]}],
        "m_elemId": ext.elem_id, "m_msgId": MSG_EXTRUSION}})
    entries = sorted([(plane.elem_id, 1.0, 0), (sp.elem_id, -1.0, -1), (al.elem_id, -1.0, 0)])
    m["m_drivenDimSegs"].append({"first": _key(ext.elem_id, k), "second": {"m_oDimValueExpr": {
        "ptr_class": "DimValueExpr", "pid": -1, "value": {
            "m_entries": [{"m_coeff": c_, "m_dimId": e, "m_seg": s, "m_mayBeDriven": False}
                          for e, c_, s in entries], "m_offset": 0.0}}}})
    for f2 in ("end", "start"):
        k2 = FACE_KEY[f2]
        if not _has(m["m_dimSegDataMap"], ext.elem_id, k2):
            m["m_dimSegDataMap"].append({"first": _key(ext.elem_id, k2), "second": {
                "m_dimDir": [0.0, 0.0, 1.0], "m_groupId": -1,
                "m_grefArr": [_gref(sp.elem_id, -1), _gref(ext.elem_id, FACE_TAG[f2])],
                "m_coefArr": [-1.0, 1.0]}})
    for e, i, tag in ((plane.elem_id, 0, 0), (sp.elem_id, -1, -1)):
        if not _has(m["m_fixedRefs"], e, i):
            m["m_fixedRefs"].append({"first": _key(e, i), "second": {
                "m_gref": _gref(e, tag), "m_dimDir": [0.0, 0.0, 1.0], "m_groupId": -1,
                "m_refFlip": 2}})
    m["m_propagatedDrivers"].append(_key(al.elem_id, 0))
    sk = lambda r: (r["first"]["m_elementId"], r["first"]["m_int64"])  # noqa: E731
    for nm in ("m_paramExprs", "m_drivenDimSegs", "m_dimSegDataMap", "m_fixedRefs"):
        m[nm].sort(key=sk)
    m["m_propagatedDrivers"].sort(key=lambda r: (r["m_elementId"], r["m_int64"]))
    # the extrusion regenerates from the planes its faces are locked to
    par = ext.header["m_parents"]["value"]
    par["m_regenOnly"] = sorted(set(par.get("m_regenOnly") or []) | {plane.elem_id})


# --------------------------------------------------------------------------- the drive
def _resolve_plane(doc, v, label):
    """-> (plane element | None, z, is_origin)."""
    if hasattr(v, "elem_id"):
        if v.elem_id not in {p.elem_id for p in doc.refplanes}:
            raise ValueError(f"height_law: {label} plane {v.elem_id} is not in this document")
        return v, plane_z(v), False
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        raise ValueError(f"height_law: {label} must be a z (ft) or a plane, not {v!r}")
    z = float(v)
    if not math.isfinite(z):
        raise ValueError(f"height_law: {label} is not finite")
    if abs(z) < EPS:
        st = _state(doc)
        return (st["origin"] if st["origin"] is not None else _find_origin(doc)), 0.0, True
    return None, z, False


def _faces_map(faces) -> Dict[str, str]:
    if isinstance(faces, dict):
        fmap = {str(f): str(s) for f, s in faces.items()}
    elif isinstance(faces, (list, tuple)):
        if len(set(faces)) != len(faces):
            raise ValueError(f"height_law: repeated face in {faces!r}")
        fmap = {str(f): ("lo" if f == "start" else "hi") for f in faces}
    else:
        raise ValueError(f"height_law: bad faces {faces!r}")
    if not fmap or any(f not in FACE_TAG or s not in ("lo", "hi") for f, s in fmap.items()):
        raise ValueError(f"height_law: bad faces {faces!r}")
    return fmap


def wire_height_drive(doc, *, caption: Optional[str], lo_z, hi_z,
                      targets: Sequence = (), locked: bool = False) -> Dict[str, Any]:
    """Make family parameter ``caption`` drive the height between two
    horizontal reference planes and lock the chosen cap faces of each target
    extrusion to them.

    ``lo_z`` / ``hi_z``: a float z (ft) for a NEW plane (0.0 = the origin
    elevation plane, added on first use) or an existing plane element (a
    chain).  Exactly one of the two must already be positioned (the origin, or
    a plane an earlier height drive placed): two would over-constrain, none
    would float.  ``targets`` = ``[(ExtrusionElem | FormBundle, faces)]`` where
    ``faces`` is ``("start", "end")`` (start -> lo, end -> hi) or
    ``{"start": "lo"|"hi", "end": "lo"|"hi"}``.  ``caption=None`` with
    ``locked=True`` authors a LOCKED unlabelled dimension instead.

    Call BEFORE ``finalize``.  Every check runs before the first mutation;
    a refusal raises and leaves the document unchanged."""
    if doc.finalized:
        raise RuntimeError("height_law: document is finalized")
    c = _ctx(doc)
    st = _state(doc)
    if c["front"] is None or c["level"] is None:
        raise ValueError("height_law: document has no Front elevation or no Level")
    targets = list(targets)
    pid = -1
    if caption is None:
        if not locked:
            raise ValueError("height_law: an unlabelled height dim must be locked "
                             "(else nothing holds it)")
    else:
        if caption not in doc.params:
            raise ValueError(f"height_law: no parameter {caption!r}")
        pe = doc.params[caption]
        pdef = next((v.get("value") or {} for k, v in pe.obj.items()
                     if k.endswith("aramDef") and isinstance(v, dict)), {})
        if ((pdef.get("m_specTypeId") or {}).get("m_typeId") or "") != SPEC_LENGTH:
            raise ValueError(f"height_law: {caption} is not a length parameter")
        pid = pe.elem_id
    lo_p, lo, lo_origin = _resolve_plane(doc, lo_z, "lo")
    hi_p, hi, hi_origin = _resolve_plane(doc, hi_z, "hi")
    if not lo < hi - EPS:
        raise ValueError(f"height_law: planes need lo < hi (got {lo:g}, {hi:g})")
    if caption is not None:
        rows = doc.types[doc.current_type][1] if doc.types else {}
        cur = rows.get(pid)
        if isinstance(cur, (int, float)) and abs(float(cur) - (hi - lo)) > EPS:
            raise ValueError(f"height_law: {caption} is {float(cur):g} ft but its planes are "
                             f"{hi - lo:g} ft apart")
    pos = st["positioned"]
    lo_fixed = lo_origin or (lo_p is not None and lo_p.elem_id in pos)
    hi_fixed = hi_origin or (hi_p is not None and hi_p.elem_id in pos)
    if lo_fixed and hi_fixed:
        raise ValueError("height_law: both planes are already positioned -- a third "
                         "dimension over-constrains")
    if not lo_fixed and not hi_fixed:
        raise ValueError("height_law: neither plane is positioned -- the chain would float")
    locked_now = _existing_face_locks(doc)
    plan: List[Tuple[Any, str, str]] = []
    seen: set = set()
    for t, faces in targets:
        ext = extrusion_of(t)
        fmap = _faces_map(faces)
        _sp_of(doc, ext)
        _x_extent(doc, ext)
        for f, s in fmap.items():
            fz = face_z(doc, ext, f)
            want = lo if s == "lo" else hi
            if abs(fz - want) > EPS:
                raise ValueError(f"height_law: extrusion {ext.elem_id}'s {f} face is at "
                                 f"{fz:g} ft, not on the {s} plane at {want:g} ft")
            key = (ext.elem_id, FACE_TAG[f])
            if key in locked_now or key in st["locked"] or key in seen:
                raise ValueError(f"height_law: extrusion {ext.elem_id}'s {f} face is "
                                 "already locked")
            seen.add(key)
            plan.append((ext, f, s))
    _mgr(doc)
    # ---- mutations start here
    if lo_origin or hi_origin:
        o = _ensure_origin(doc)
        lo_p = o if lo_origin else lo_p
        hi_p = o if hi_origin else hi_p
    if lo_p is None:
        lo_p = _new_zplane(doc, lo)
    if hi_p is None:
        hi_p = _new_zplane(doc, hi)
    pos.update({lo_p.elem_id, hi_p.elem_id})
    dim = _zdim(doc, hi_p, lo_p, param_id=pid, locked=locked)
    locks = []
    for ext, f, s in plan:
        pl = lo_p if s == "lo" else hi_p
        al = _face_lock(doc, ext, f, pl)
        _add_rows(doc, ext, f, pl, al)
        st["locked"].add((ext.elem_id, FACE_TAG[f]))
        locks.append(al.elem_id)
    return {"caption": caption, "lo": lo_p, "hi": hi_p, "dim": dim.elem_id,
            "locks": locks, "targets": len({p[0].elem_id for p in plan})}


def wire_height_specs(doc, specs: Sequence[Dict[str, Any]],
                      ext_of: Dict[str, Any]) -> Dict[str, Any]:
    """Wire a list of declarative height specs (an archetype's ``heights``),
    each all-or-nothing; a refused spec is noted on ``doc.notes`` and never
    raises (hard rule 1).

    A spec: ``{"caption": str | None, "locked": bool, "lo": z | name,
    "hi": z | name, "name_lo": str, "name_hi": str, "parts": {part name:
    faces}}`` -- ``lo`` / ``hi`` name a plane an EARLIER spec named, or give a
    z (ft; 0.0 = the origin elevation plane).  ``ext_of`` maps part name ->
    its ExtrusionElem (``None`` for a name that is not unique)."""
    named: Dict[str, Any] = {}
    done: List[Dict[str, Any]] = []
    refused: List[str] = []
    for spec in specs:
        cap = spec.get("caption") if isinstance(spec, dict) else None
        try:
            ends = {}
            for side in ("lo", "hi"):
                v = spec[side]
                if isinstance(v, str):
                    if v not in named:
                        raise ValueError(f"plane {v!r} was not authored by an earlier spec")
                    v = named[v]
                ends[side] = v
            targets = []
            for n, faces in (spec.get("parts") or {}).items():
                ex = ext_of.get(n)
                if ex is None:
                    raise ValueError(f"part {n!r} is missing or its name is not unique")
                targets.append((ex, faces))
            r = wire_height_drive(doc, caption=cap, lo_z=ends["lo"], hi_z=ends["hi"],
                                  targets=targets, locked=bool(spec.get("locked")))
        except Exception as e:                       # noqa: BLE001 -- never block delivery
            label = cap if cap else "a locked height"
            refused.append(str(label))
            doc.notes.append(f"height drive for {label!r} not wired "
                             f"({type(e).__name__}: {str(e)[:110]})")
            continue
        for side in ("lo", "hi"):
            nm = spec.get(f"name_{side}")
            if nm:
                named[str(nm)] = r[side]
        done.append(r)
    out = dict(report(doc))
    out.update({"specs": len(specs), "wired": len(done), "refused": refused,
                "labelled": sum(1 for d in done if d["caption"]),
                "locked_unlabelled": sum(1 for d in done if not d["caption"]),
                "captions": sorted({d["caption"] for d in done if d["caption"]})})
    return out

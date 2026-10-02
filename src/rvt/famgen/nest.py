"""rvt.famgen.nest -- NEST one generated family inside another generated
family document and place N instances of it (issue #917).

Born families nest their hardware: a trapeze nests its rods, nuts and
washers as real family instances rather than drawing them as solids.  The
census of the owner's reference library (development instrument only, counts
in ``docs/inbox/param-drive.d/917-nested.md``) found that a nested family is
stored inside an ``.rfa`` EXACTLY the way a family loaded into a project is:
an extra save unit in the one partition, a ``Global/ContentDocuments`` entry,
a ``ContentTable`` record, a ``FamilyMgr`` entry, and the host-side
``Family`` / ``FamilySurrogate`` / ``FamilySymbol`` / ``FamSymSurrogate`` /
``ParamElemFamily`` twin layer.  So the load half is the project loader
(:mod:`rvt.famgen.loader`, L1-L5) pointed at a FAMILY document as host; what
this module adds is the family-host flavour of that layer and the placed
instances, which the project loader cannot author in a family (it clones a
template instance of the category and a generated family has none).

What a placed nested instance is, decoded from 3,687 free-placed nested
instances (host -1, on the family's Level, not work-plane based) of 313 born
families -- every constant below carries its count:

* ``FamilyInstance``: ``m_famId`` = the HOST's own self-Family, object design
  option -4, ``m_assocLevelId`` = the Level, ``m_hostId`` -1,
  ``m_workPlaneBased`` False, ``m_elevation`` 0 for an unrotated instance
  (1,143 of 1,251 unrotated) -- the height lives in the transform;
  ``InstanceInfo{m_Trf, m_symbolId, m_GRepId 0}``, ``m_masterSymbolId`` = the
  symbol, ``m_instOrigin`` = the transform origin (3,443), ``m_RefDir`` /
  ``m_zAxis`` = transform rows 0 / 2; ``ParamValueSetInt`` with Visible
  (-1006205) = 1 (the 610-instance shape; 3,074 also carry -1140129 = 2,
  meaning unknown, NOT emitted); ``GeomTable`` with one empty generator row
  (3,687); ``CellList{FamilyInstancePatternHelper}`` last (3,687);
  ``FamInstDesignPropertyManager`` (3,685); ``m_famElemVisibility`` 57406
  (3,662); ``m_roomBounding`` True, ``m_bVertical`` True (3,490);
  ``m_pInstParams`` = one row per INSTANCE parameter of the nested family,
  keyed by its host twin (3,658), flags instance/reporting False (3,684).
* its header: category = the nested symbol's (3,687), family = the host
  self-Family (3,687), flags 2856 / view flags -4225 (3,685), regenOnly =
  [nested Family] (3,446), appearance = {host self-Family, symbol, Level},
  deletion = {host self-Family, Level, symbol, itself, its instance-param
  twins}, bounding box == the rep's (3,687).
* its seq-103 rep: ``GElement{m_GInfo{category = the host's GStyleElem of
  the nested category (3,687), tag = itself, flags 557060}, one GInstance
  with the same InstanceInfo (3,639; transform equal 3,687), gElemType 3}``.
* family-host flavour of the loaded layer: nested ``Family`` header flags 10
  (3,685), nested ``FamilySymbol`` header flags 2472 (3,306); the nested
  symbols are NOT tracked in the host ``ElementTrackingData`` (0 of 313
  files), so the project loader's tracking row is not written here.

LOCKS (#917 second pass, ``locks=``): an instance's centre reference locked
to a host ``RefPlane`` is one ``Alignment``, decoded from the 912 born locks
of a free-placed nested instance's Center (Left/Right) / (Front/Back) /
(Elevation) reference to a host RefPlane (546 / 355 / 11; every constant
below holds on all 912 unless a count says otherwise):

* the instance witness is a ``GeomSegInPlaneRef`` whose ``m_geomRef`` names
  the INSTANCE (``m_elemId``) at ``m_geomTag`` = the child document's
  Is-Reference code (``RefPlane.m_refName``: 1 Center (Left/Right), 4 Center
  (Front/Back), 7 Center (Elevation)) with ``m_subTag`` -1,
  ``m_famMemberIdx`` -1, ``m_ownerDBViewId`` -1 and ``m_flags`` 1 (the plane
  witness: geomTag 0, flags 0).  The child carries exactly one origin plane
  with that code in 1,340 / 1,340 Center (Left/Right) locks of the whole
  corpus; where a child carries two Center (Front/Back) codes the
  origin-defining one is meant (1,153 / 1,165).  Placed by the instance
  transform it lies on the host plane in every one (constraint_law CG8:
  2,393 judged born locks, 0 findings);
* the ``Alignment``: ``m_flags`` 14, ``m_dimVersion`` 6, no cell list, owned
  by no view, ``m_lastTrf`` identity, the only pointer ``m_pDimLine`` (GLine,
  endParams [0, 0]); ``m_constrDir`` parallel to the host plane's normal,
  ``m_planeNormal`` perpendicular to it, both ``m_refPnts`` / ``m_oldOrigin``
  / both witnesses' old segment ends on the plane, ``m_pDimLine`` origin =
  ``m_oldOrigin``; one segment (flags 1, three values, the two trailing -1),
  an empty equality array; the plane-first witness order (constrFlags 4 then
  2, end index 0 / 0: 387 + 222 + 11 of 912; the rest put the instance
  first, mostly with constrFlags 8 / 1);
* its header: category Alignments, flags 10 / view flags -4225, owner view
  -1, family = the host self-Family; deletion = {itself, the DimensionStyle,
  the self-Family, the instance, the plane}; regenOnly = {the nested symbol,
  the Level, the UnitsElem}; appearance = {DimensionStyle, instance, plane,
  UnitsElem}; neither the instance's nor the plane's header lists the lock.

PARAMETER ASSOCIATION (``associate=``): host parameter -> nested parameter
is a ``FamilyParametrizedElemParamsCell`` on the INSTANCE, just before its
``FamilyInstancePatternHelper`` (3,432 of 4,606 cell lists are exactly
those two), one ``m_paramDrivenData`` entry per pair ``{m_famParamId = the
host parameter, m_elemPropId = the nested parameter's host twin, m_geomTag
-1, m_bIsSymbol False}`` (25,002 / 25,002).  Every twin target in the
corpus is an INSTANCE parameter of the nested family (8,349 / 8,349; a
type parameter is never a target here), the instance's ``m_pInstParams`` row
for it carries the host parameter's current value (3,880 / 3,880 numbers,
4,467 / 4,467 Yes/No), and the host parameter is a deletion parent of the
instance (24,992 / 25,002).

Not authored here (gaps recorded in the record): named-reference locks (a
geomTag beyond the Is-Reference codes, 2,000+ in the corpus, mapping
unresolved), work-plane-based / rotated / hosted placement, shared nesting,
association to a nested TYPE parameter (30 born nested symbols carry the
cell; not censused far enough to author), and the nested type table's blank
leading row the project loader writes (born nested families carry real
types only).

Honesty: everything here is format structure + our own two documents; no
reference-family value enters the output.  Validator green and an empty
constraint-law report are facts about the file; whether Revit opens a family
with nested instances is unverified until a desktop verdict exists (hard
rule 4) -- nothing calls this nesting "working".
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from . import loader as L

#: header flag words of a born family host's nested layer / instances [V counts above]
NESTED_FAMILY_HDR_FLAGS = 10
NESTED_SYMBOL_HDR_FLAGS = 2472
INSTANCE_HDR_FLAGS = 2856
INSTANCE_VIEW_FLAGS = -4225
#: FamilyInstance.m_famElemVisibility.m_flags (3,662 / 3,687)
INSTANCE_VISIBILITY_FLAGS = 57406
#: GElement / GInstance m_GInfo.m_flags (every free nested instance rep)
GINFO_FLAGS = 557060
#: the instance object's design option in a family document
FAMILY_DESIGN_OPTION = -4
#: built-in "Visible" integer parameter
BIP_VISIBLE = -1006205
#: a family is small: refuse runaway placement lists before touching anything
MAX_INSTANCES = 512

#: lock reference name -> the child's Is-Reference code (RefPlane.m_refName)
#: = the instance witness's geomTag [V module docstring]
CENTRE_REFERENCE = {"center_lr": 1, "center_fb": 4, "center_elevation": 7}
#: the instance lock's Alignment / header constants [V 912 / 912]
LOCK_FLAGS = 14
LOCK_DIM_VERSION = 6
LOCK_HDR_FLAGS = 10
LOCK_VIEW_FLAGS = -4225
#: m_geomRef.m_flags of the INSTANCE witness (the plane witness carries 0)
LOCK_GREF_FLAGS_INSTANCE = 1
#: plane-first witness order: constrFlags of the plane, then the instance
LOCK_CONSTR_FLAGS = (4, 2)
#: FamilyParametrizedElemParamsCell entry geomTag (25,002 / 25,002)
ASSOC_GEOM_TAG = -1

ProductArg = Union[Any, Callable[[int], Any]]


class NestError(RuntimeError):
    """A nesting precondition or post-write check failed; no output is left."""


@dataclass
class NestResult:
    ok: bool
    out_path: Optional[str]
    family_name: str = ""
    nested_family_id: int = -1
    symbol_id: int = -1
    instance_ids: List[int] = dc_field(default_factory=list)
    proofs: Dict[str, Any] = dc_field(default_factory=dict)
    notes: List[str] = dc_field(default_factory=list)
    lock_ids: List[int] = dc_field(default_factory=list)
    associations: List[Dict[str, Any]] = dc_field(default_factory=list)

    def as_json(self) -> dict:
        return {"ok": self.ok, "out_path": self.out_path,
                "family_name": self.family_name,
                "nested_family_id": self.nested_family_id,
                "symbol_id": self.symbol_id, "instance_ids": list(self.instance_ids),
                "lock_ids": list(self.lock_ids),
                "associations": [dict(a) for a in self.associations],
                "proofs": self.proofs, "notes": list(self.notes)}


@dataclass(frozen=True)
class Lock:
    """Lock placed instance ``instance`` (an index into ``points``) by its
    centre reference ``reference`` (a :data:`CENTRE_REFERENCE` key) to the
    host ``RefPlane`` whose element id is ``plane``."""
    instance: int
    reference: str
    plane: int


@dataclass
class _Assoc:
    host_param: int
    twin: int
    host_row: dict
    host_caption: str
    child_caption: str


@dataclass
class _LockPlan:
    instance: int
    code: int
    plane: int
    plane_obj: dict
    host_plane: Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    child_ends: Tuple[List[float], List[float]]


# ---------------------------------------------------------------------------
# preconditions (all checked before anything is written)
# ---------------------------------------------------------------------------

def _points(points: Sequence[Sequence[float]]) -> List[Tuple[float, float, float]]:
    if points is None or isinstance(points, (str, bytes)):
        raise NestError("points must be a list of (x, y, z) feet")
    pts = []
    for i, p in enumerate(points):
        try:
            xyz = tuple(float(c) for c in p)
        except (TypeError, ValueError) as exc:
            raise NestError(f"point {i} is not numeric: {p!r}") from exc
        if len(xyz) != 3 or not all(math.isfinite(c) for c in xyz):
            raise NestError(f"point {i} must be three finite numbers (feet), got {p!r}")
        pts.append(xyz)
    if not pts:
        raise NestError("nothing to place: points is empty")
    if len(pts) > MAX_INSTANCES:
        raise NestError(f"{len(pts)} instances exceeds the {MAX_INSTANCES} cap")
    return pts


def _host_frame(host: "L.HostContext") -> Dict[str, int]:
    """The host family document's own self-Family and its one Level."""
    doc = host.doc
    selfs = [f for f in doc.ids_of_class("Family")
             if (doc.value(f) or {}).get("m_surrogateId") == -1
             and not (doc.value(f) or {}).get("m_oFamDoc")]
    if len(selfs) != 1:
        raise NestError(f"host is not a family document: {len(selfs)} self-Family "
                        "elements (want exactly 1)")
    levels = doc.ids_of_class("Level")
    if len(levels) != 1:
        raise NestError(f"host family carries {len(levels)} Levels; nesting places "
                        "on the family's one reference level")
    return {"self_family": int(selfs[0]), "level": int(levels[0])}


# ---------------------------------------------------------------------------
# authoring
# ---------------------------------------------------------------------------

def _ptr(cls: str, value: dict, pid: int = -1) -> dict:
    return {"ptr_class": cls, "pid": pid, "value": value}


def _identity3() -> List[List[float]]:
    return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]


def _instance_info(symbol_id: int, origin: Sequence[float]) -> dict:
    return {"m_Trf": {"m_3x3": _identity3(), "m_or": [float(c) for c in origin]},
            "m_symbolId": int(symbol_id), "m_GRepId": 0,
            "m_cda": {"m_pDoc": {"weakref": 1}}}


def _symbol_extent(authored) -> Tuple[List[float], List[float]]:
    """The nested symbol's own bounding box (its local frame), from the
    authored symbol geometry; a unit box when the symbol has no solid."""
    for e in authored.elements:
        if e.class_name == "FamilySymbol" and e.elem_id == authored.plan.symbol_id:
            bb = (e.rep or {}).get("m_bBox") if isinstance(e.rep, dict) else None
            if bb and len(bb) == 2:
                return [float(c) for c in bb[0]], [float(c) for c in bb[1]]
    return [-0.5, -0.5, 0.0], [0.5, 0.5, 1.0]


def _instance_param_rows(product, plan, values: Optional[Dict[int, dict]] = None
                         ) -> List[dict]:
    """One row per INSTANCE parameter of the nested family, keyed by its host
    twin, current value kept, instance/reporting flags False [V 3,658/3,684];
    an ASSOCIATED twin (``values``: twin id -> the host parameter's row)
    carries the host parameter's current value instead [V 3,880 / 3,880
    numbers, 4,467 / 4,467 Yes/No]."""
    fp = ((product.doc.self_family.obj.get("m_familyParams") or {}).get("value") or {})
    rows = []
    for r in fp.get("m_params") or []:
        if not r.get("m_instance"):
            continue
        pid = r.get("m_paramId")
        if not (isinstance(pid, int) and pid in plan.twin_of):
            continue
        r2 = L._dc(r)
        r2["m_paramId"] = int(plan.twin_of[pid])
        r2["m_instance"] = False
        r2["m_reporting"] = False
        src = (values or {}).get(r2["m_paramId"])
        if src is not None:
            for k in ("m_value", "m_int", "m_str", "m_elemId"):
                if k in src:
                    r2[k] = L._dc(src[k])
            r2["m_oExpression"] = None
        rows.append(r2)
    return rows


def author_nested_instance(eid: int, origin: Sequence[float], *, product, plan,
                           frame: Dict[str, int], category: int, gstyle: int,
                           extent: Tuple[List[float], List[float]],
                           associations: Sequence[_Assoc] = ()):
    """One free-placed nested ``FamilyInstance`` (+ its GElement rep) at
    ``origin`` (feet, family coordinates, unrotated); ``associations`` = the
    host parameters driving its instance parameters (module docstring)."""
    from ..genesis.types import blank_object
    from ..genesis.skeleton import element_header
    from .geometry import assign_pids
    sym = int(plan.symbol_id)
    lvl, selff = frame["level"], frame["self_family"]
    org = [float(c) for c in origin]
    lo = [org[k] + extent[0][k] for k in range(3)]
    hi = [org[k] + extent[1][k] for k in range(3)]

    cells = []
    if associations:
        cells.append(_ptr("FamilyParametrizedElemParamsCell", {"m_paramDrivenData": [
            {"m_famParamId": int(a.host_param), "m_elemPropId": int(a.twin),
             "m_geomTag": ASSOC_GEOM_TAG, "m_bIsSymbol": False} for a in associations]}))
    cells.append(_ptr("FamilyInstancePatternHelper", {"m_PatternPositionMap": [],
                                                      "m_substituteFaceMap": []}))
    values = {int(a.twin): a.host_row for a in associations}
    obj = blank_object("FamilyInstance")
    obj.update({
        "m_pParamValueSetInt": _ptr("ParamValueSetInt", {
            "m_paramSet": [{"m_paramId": BIP_VISIBLE, "m_value": 1}]}),
        "m_cellList": _ptr("CellList", {"m_cells": cells}),
        "m_docAccess": {"m_pDoc": {"weakref": 1}},
        "m_id": int(eid), "m_assocLevelId": lvl, "m_famId": selff,
        "m_unplacedOwnerId": -1, "m_ownerDBViewId": -1, "m_createdPhaseId": -1,
        "m_demolishedPhaseId": -1, "m_designOptionId": FAMILY_DESIGN_OPTION,
        "m_pInstanceInfo": _ptr("InstanceInfo", _instance_info(sym, org)),
        "m_GInstanceId": 0, "m_elevation": 0.0, "m_hostParam": 0.0, "m_hostId": -1,
        "m_pInstParams": _ptr("FamilyParams", {
            "m_params": _instance_param_rows(product, plan, values),
            "m_geomRefHandles": {"m_offsetGeomMap": []}}),
        "m_instOrigin": list(org), "m_RefDir": [1.0, 0.0, 0.0], "m_zAxis": [0.0, 0.0, 1.0],
        "m_masterSymbolId": sym, "m_ownerElemId": -1, "m_assocSketchPlaneId": -1,
        "m_analyticalTopPlaneId": -1, "m_analyticalBottomPlaneId": -1,
        "m_superInstanceId": -1, "m_scheduleOnlyLevelId": -1,
        "m_famElemVisibility": {"m_flags": INSTANCE_VISIBILITY_FLAGS},
        "m_roomBounding": True, "m_bVertical": True, "m_workPlaneBased": False,
    })
    gt = blank_object("GeomTable")
    gt["m_table"] = [{"m_geomGeneratorId": -1}]
    for k in ("m_maxSafeTag", "m_lastCheckedKingsUserModificationDate"):
        if k in gt:                       # release-dependent fields
            gt[k] = -1
    obj["m_pGeomTable"] = _ptr("GeomTable", gt)
    dpm = blank_object("FamInstDesignPropertyManager")
    obj["m_pDesignPropManager"] = _ptr("FamInstDesignPropertyManager", dpm)
    assign_pids(obj)

    gi = blank_object("GInstance")
    gi.update({"m_GInfo": {"m_categoryId": -1, "m_tag": 0, "m_controlCommand": 0,
                           "m_flags": GINFO_FLAGS},
               "m_instanceInfo": _ptr("InstanceInfo", _instance_info(sym, org)),
               "m_oEmbeddedSymbolGRep": None, "m_tagId": -1,
               "m_forbiddenTarget": {"m_targets": 0}})
    rep = blank_object("GElement")
    rep.update({"m_GInfo": {"m_categoryId": int(gstyle), "m_tag": int(eid),
                            "m_controlCommand": 0, "m_flags": GINFO_FLAGS},
                "m_subNodes": [_ptr("GInstance", gi)],
                "m_bBox": [list(lo), list(hi)], "m_tightbBox": [list(lo), list(hi)],
                "m_elementId": int(eid), "m_gElemType": 3, "m_flags": 0})
    assign_pids(rep)

    ip_ids = [r["m_paramId"] for r in obj["m_pInstParams"]["value"]["m_params"]]
    hdr = element_header("FamilyInstance", category=int(category), family_id=selff,
                         deletion=sorted({selff, lvl, sym, int(eid), *ip_ids,
                                          *(int(a.host_param) for a in associations)}),
                         regen_only=[int(plan.host_family_id)],
                         appearance=sorted({selff, sym, lvl}),
                         flags=INSTANCE_HDR_FLAGS, visible_view_flags=INSTANCE_VIEW_FLAGS,
                         bbox=(lo, hi))
    el = L._skel(int(eid), "FamilyInstance", hdr, obj, rep, kind="nested_instance")
    el.notes.append(f"nested instance of symbol {sym} at {org} on Level {lvl} "
                    f"(free placement, unrotated, {len(associations)} associated "
                    "parameter(s))")
    return el


# ---------------------------------------------------------------------------
# locks + parameter association: planned (and refused) before anything is written
# ---------------------------------------------------------------------------

def _locks(locks) -> List[Lock]:
    out = []
    for i, lk in enumerate(locks or ()):
        if isinstance(lk, Lock):
            out.append(lk)
            continue
        try:
            a, b, c = lk
            out.append(Lock(int(a), str(b), int(c)))
        except (TypeError, ValueError) as exc:
            raise NestError(f"lock {i} must be (instance index, reference, host plane id), "
                            f"got {lk!r}") from exc
    return out


def _child_centre_plane(product, code: int):
    """The child's ONE origin-defining RefPlane with Is-Reference ``code``
    [V 1,340 / 1,340 Center (Left/Right) locks]; None when it has none."""
    hits = [rp for rp in product.doc.refplanes
            if rp.obj.get("m_refName") == code and rp.obj.get("m_definesOrigin")]
    return hits[0] if len(hits) == 1 else None


def _plan_locks(locks: Sequence[Lock], pts, product, host) -> List[_LockPlan]:
    """Validate every lock and work out its geometry; a lock that would
    contradict the geometry it locks (constraint_law CG8) is refused."""
    from . import constraint_law as CL
    out: List[_LockPlan] = []
    seen = set()
    for lk in locks:
        if not (0 <= lk.instance < len(pts)):
            raise NestError(f"lock names instance {lk.instance}; there are {len(pts)} points")
        code = CENTRE_REFERENCE.get(lk.reference)
        if code is None:
            raise NestError(f"lock reference {lk.reference!r} is not one of "
                            f"{sorted(CENTRE_REFERENCE)}")
        if (lk.instance, code) in seen:
            raise NestError(f"instance {lk.instance}'s {lk.reference} is locked twice")
        seen.add((lk.instance, code))
        crp = _child_centre_plane(product, code)
        if crp is None:
            raise NestError(f"the nested family carries no origin plane with Is-Reference "
                            f"{lk.reference} ({code}); nothing to lock")
        if host.doc.class_of(int(lk.plane)) != "RefPlane":
            raise NestError(f"lock target {lk.plane} is not a RefPlane of the host")
        hobj = host.doc.value(int(lk.plane)) or {}
        hpl = CL.plane_of_any("RefPlane", hobj)
        cpl = CL.plane_of_any("RefPlane", crp.obj)
        if hpl is None or cpl is None:
            raise NestError(f"plane {lk.plane} or the child's {lk.reference} plane is degenerate")
        org = pts[lk.instance]
        trf = {"m_3x3": _identity3(), "m_or": list(org)}
        placed = CL.transform_plane(trf, cpl)
        n = hpl[1]
        if placed is None or abs(abs(CL._dot(placed[1], n)) - 1.0) > CL.PARALLEL_TOL:
            raise NestError(f"instance {lk.instance}'s {lk.reference} is not parallel to "
                            f"plane {lk.plane}: the lock would contradict the geometry")
        off = abs(CL._dot(CL._sub(placed[0], hpl[0]), n))
        if off > CL.ON_PLANE_TOL:
            raise NestError(f"instance {lk.instance}'s {lk.reference} is {off:.6g} ft off "
                            f"plane {lk.plane}: place the instance on the plane first "
                            "(the lock would contradict the geometry)")
        ends = tuple([float(crp.obj[k][i]) + float(org[i]) for i in range(3)]
                     for k in ("m_freeEnd", "m_bubbleEnd"))
        if max(abs(a - b) for a, b in zip(*ends)) < 1e-9:
            raise NestError(f"the child's {lk.reference} plane has no drawn extent")
        out.append(_LockPlan(lk.instance, code, int(lk.plane), hobj, hpl, ends))
    return out


def _caption(v: Optional[dict]) -> str:
    return str((((v or {}).get("m_pParamDef") or {}).get("value") or {}).get("m_caption") or "")


def _def_kind(v: Optional[dict]) -> Tuple[Any, Any]:
    d = (v or {}).get("m_pParamDef") or {}
    spec = (d.get("value") or {}).get("m_specTypeId")
    return d.get("ptr_class"), (spec.get("m_typeId") if isinstance(spec, dict) else spec)


def _plan_associations(associate, product, plan, host, frame) -> List[_Assoc]:
    """``associate`` = ``{host parameter caption: nested parameter caption}``.
    The nested parameter must be an INSTANCE parameter [V 8,349 / 8,349] of
    the same definition class and spec as the host's."""
    if not associate:
        return []
    if not isinstance(associate, dict):
        raise NestError("associate must be {host parameter: nested parameter}")
    doc = host.doc
    sf = doc.value(frame["self_family"]) or {}
    rows = {r.get("m_paramId"): r for r in
            (((sf.get("m_familyParams") or {}).get("value") or {}).get("m_params") or [])}
    host_by_cap: Dict[str, int] = {}
    for pid in rows:
        if isinstance(pid, int) and pid > 0:
            host_by_cap.setdefault(_caption(doc.value(pid)), pid)
    child_rows = {r.get("m_paramId"): r for r in
                  (((product.doc.self_family.obj.get("m_familyParams") or {}).get("value")
                    or {}).get("m_params") or [])}
    out: List[_Assoc] = []
    seen = set()
    for hcap, ccap in associate.items():
        hid = host_by_cap.get(str(hcap))
        if hid is None:
            raise NestError(f"the host has no family parameter {hcap!r}")
        pe = product.doc.params.get(str(ccap))
        if pe is None:
            raise NestError(f"the nested family has no parameter {ccap!r}")
        if not (child_rows.get(pe.elem_id) or {}).get("m_instance"):
            raise NestError(f"nested parameter {ccap!r} is a type parameter; born hosts "
                            "associate nested INSTANCE parameters only (8,349 / 8,349)")
        twin = plan.twin_of.get(pe.elem_id)
        if twin is None:
            raise NestError(f"nested parameter {ccap!r} has no host twin")
        if twin in seen:
            raise NestError(f"nested parameter {ccap!r} is associated twice")
        seen.add(twin)
        if _def_kind(doc.value(hid)) != _def_kind(pe.obj):
            raise NestError(f"host {hcap!r} {_def_kind(doc.value(hid))} and nested {ccap!r} "
                            f"{_def_kind(pe.obj)} are not the same kind of parameter")
        out.append(_Assoc(int(hid), int(twin), L._dc(rows[hid]), str(hcap), str(ccap)))
    return out


def _host_lock_context(host, frame) -> Dict[str, int]:
    """The DimensionStyle the host's own alignments use and its UnitsElem."""
    doc = host.doc
    styles: Dict[int, int] = {}
    for a in doc.ids_of_class("Alignment"):
        st = (doc.value(a) or {}).get("m_styleSymbolId")
        if isinstance(st, int) and st > 0:
            styles[st] = styles.get(st, 0) + 1
    units = doc.ids_of_class("UnitsElem")
    if not styles or len(units) != 1:
        raise NestError("the host has no alignment DimensionStyle or not exactly one "
                        "UnitsElem; locks need both")
    style = sorted(styles.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
    return {"style": int(style), "units": int(units[0])}


def _unit(v) -> List[float]:
    ln = math.sqrt(sum(float(c) * float(c) for c in v)) or 1.0
    return [float(c) / ln for c in v]


def author_instance_lock(eid: int, lp: _LockPlan, *, instance_id: int, symbol_id: int,
                         frame: Dict[str, int], ctx: Dict[str, int]):
    """One born-shape instance lock (module docstring): the host plane first
    (constrFlags 4), the instance's centre reference second (constrFlags 2,
    geomTag = the Is-Reference code, geomRef flags 1)."""
    from ..genesis.types import blank_object
    from ..genesis.skeleton import element_header
    from . import param_drive as PD
    from . import geometry as G
    selff, lvl = frame["self_family"], frame["level"]
    style, units = ctx["style"], ctx["units"]
    n = [float(c) for c in lp.host_plane[1]]
    e0, e1 = lp.child_ends
    mid = [(a + b) / 2.0 for a, b in zip(e0, e1)]
    fe, be = lp.plane_obj.get("m_freeEnd"), lp.plane_obj.get("m_bubbleEnd")
    plane_ends = ((list(map(float, fe)), list(map(float, be)))
                  if fe and be and max(abs(float(a) - float(b)) for a, b in zip(fe, be)) > 1e-9
                  else (list(e0), list(e1)))
    o = blank_object("Alignment")
    PD._dimension_common(o, eid, selff, -1, style)
    o["m_cellList"] = None
    o["m_refPnts"] = [list(mid), list(mid)]
    seg = PD._seg_info(locked_value=0.0, origin=mid, param_id=-1, flags=1,
                       seg_value=0.0, id1=0, id2=-1)
    for v in seg["m_values"]:
        v["m_oTextFields"] = None
    o["m_ArrSegInfo"] = [seg]
    o["m_ArrEqualityFormulaInfo_DimEqSegInfoArr"] = {"m_arr": [], "m_maxSize": 0,
                                                     "m_isLazy": False}
    o["m_lastDimSegInfoId"] = {"m_id1": 0, "m_id2": -1}
    o["m_lastUsedId"] = {"m_id": 1}
    o["m_oldOrigin"] = list(e0)
    o["m_flags"] = LOCK_FLAGS
    o["m_dimLockedForLabeling"] = False
    o["m_dimVersion"] = LOCK_DIM_VERSION
    o["m_planeNormal"] = [0.0, 0.0, 1.0] if abs(n[2]) < 0.5 else [0.0, -1.0, 0.0]
    wp = PD._witness(lp.plane, ends=plane_ends, ref_length=PD._seg_length(plane_ends),
                     wid=0, end_idx=0, constr_flags=LOCK_CONSTR_FLAGS[0])
    wi = PD._witness(instance_id, ends=(e0, e1), ref_length=PD._seg_length((e0, e1)),
                     wid=1, end_idx=0, constr_flags=LOCK_CONSTR_FLAGS[1])
    g = wi["m_pWitnessRef"]["value"]["m_geomRef"]
    g["m_geomTag"] = int(lp.code)
    g["m_flags"] = LOCK_GREF_FLAGS_INSTANCE
    o["m_witnessRefs"] = [wp, wi]
    o["m_pDimLine"] = PD._dim_line(e0, _unit([b - a for a, b in zip(e0, e1)]))
    o["m_orientType"] = 0
    o["m_constrDir"] = list(n)
    G.assign_pids(o)
    hdr = element_header("Alignment", category=PD.CAT_ALIGNMENTS, family_id=selff,
                         deletion=sorted({int(eid), style, selff, int(instance_id), lp.plane}),
                         regen_only=sorted({int(symbol_id), lvl, units}),
                         appearance=sorted({style, int(instance_id), lp.plane, units}),
                         flags=LOCK_HDR_FLAGS, visible_view_flags=LOCK_VIEW_FLAGS,
                         owner_view=-1)
    el = L._skel(int(eid), "Alignment", hdr, o, None, kind="nested_instance_lock")
    el.notes.append(f"instance {instance_id} reference {lp.code} locked to plane {lp.plane}")
    return el


def host_reference_planes(host_rfa: str) -> List[Dict[str, Any]]:
    """Every RefPlane of a family document's own unit, with its plane:
    ``{id, name, ref_name, defines_origin, point, normal}`` -- what a caller
    picks a lock target from."""
    from contextlib import ExitStack
    from ..global_framing import enter_own_release
    from ..families import FamilyIndex
    from . import constraint_law as CL
    out = []
    with ExitStack() as st:
        enter_own_release(st, host_rfa)
        fi = FamilyIndex(host_rfa)
        for eid in sorted(fi.ids_of_class(0, "RefPlane")):
            o = fi.decode(0, eid, 102)
            v = (o.value or {}) if o is not None else {}
            pl = CL.plane_of_any("RefPlane", v)
            out.append({"id": int(eid), "name": str(v.get("m_text") or ""),
                        "ref_name": v.get("m_refName"),
                        "defines_origin": bool(v.get("m_definesOrigin")),
                        "point": list(pl[0]) if pl else None,
                        "normal": list(pl[1]) if pl else None})
    return out


def _family_host_flavour(authored) -> None:
    """Born family hosts carry the nested Family / FamilySymbol headers with
    flags 10 / 2472 where the project loader writes 26 / 2488."""
    for e in authored.elements:
        if e.class_name == "Family" and e.elem_id == authored.plan.host_family_id:
            e.header["m_abFlags4Bytes"] = NESTED_FAMILY_HDR_FLAGS
        elif e.class_name == "FamilySymbol" and e.elem_id in authored.plan.symbol_ids:
            e.header["m_abFlags4Bytes"] = NESTED_SYMBOL_HDR_FLAGS


def _edit_family_host_registries(host_rfa: str, authored) -> Tuple[bytes, bytes, Dict[str, Any]]:
    """ContentTable record + FamilyMgr entry + ContentDocuments entry (the
    project loader's L5/L1), WITHOUT the ElementTrackingData symbol row: born
    family hosts never track their nested symbols there (0 / 313)."""
    from . import factory as F
    from ..container import open_rvt
    from ..adocument import decode_latest, encode_latest
    with open_rvt(host_rfa) as f:
        latest_payload = f.inflate("Global/Latest")
        cd_payload = b"".join(f.inflate_all("Global/ContentDocuments"))
    lat = decode_latest(latest_payload)
    if not lat.clean:
        raise NestError("host Global/Latest does not decode clean")
    lv = L._dc(lat.value)
    plan = authored.plan
    saved = (list(plan.symbol_ids), plan.instance_id)
    try:
        # register without any tracking ids (the helper skips empty id lists)
        plan.symbol_ids, plan.instance_id = [], L.INVALID
        reg = L.register_in_host_adocument(lv, plan, category=authored.category,
                                           unit_records=int(authored.unit["record_count"]))
    finally:
        plan.symbol_ids, plan.instance_id = saved
    new_latest = encode_latest(lv, trailer=lat.trailer)
    if not decode_latest(new_latest).clean:
        raise NestError("edited host ADocument does not re-decode clean")
    ents, tail = F.parse_content_documents(cd_payload)
    if any(g == plan.guid for g, _a in ents):
        raise NestError(f"content document {plan.guid} is already nested in the host")
    cd_new = F.assemble_content_documents(
        ents + [(plan.guid, bytes(authored.adocument["payload"]))],
        tail=tail or F.CD_END_RECORD)
    after, _t = F.parse_content_documents(cd_new)
    if plan.guid not in {g for g, _a in after}:
        raise NestError("our ContentDocuments entry did not insert")
    return new_latest, cd_new, {"registrations": reg,
                                "content_documents": {"before": len(ents), "after": len(after)}}


# ---------------------------------------------------------------------------
# verification of the written host
# ---------------------------------------------------------------------------

def verify_nested(path: str, *, nested_family_id: int, symbol_id: int,
                  instance_ids: Sequence[int], guid: str,
                  validate: bool = True, lock_ids: Sequence[int] = (),
                  associations: Sequence[Tuple[int, int]] = ()) -> Dict[str, Any]:
    """Read the written host back under its own release and prove: the
    nested Family / symbol / every instance decode clean and point at each
    other, the content document + FamilyMgr entry are present, the four
    document registries agree (every born family in the census does: 421 /
    421), the family-mode validator reports 0 errors and the constraint law
    has no findings."""
    from contextlib import ExitStack
    from ..global_framing import enter_own_release
    from ..families import FamilyIndex
    from ..container import open_rvt
    from ..adocument import decode_latest
    from . import constraint_law as CL
    rep: Dict[str, Any] = {"problems": []}
    bad = rep["problems"]
    with ExitStack() as st:
        enter_own_release(st, path)
        fi = FamilyIndex(path)
        recs = fi.unit_records(0).get(102, {})

        def val(eid: int) -> dict:
            if eid not in recs:
                bad.append(f"element {eid} missing")
                return {}
            o = fi.decode(0, eid, 102)
            if o is None or not o.clean:
                bad.append(f"element {eid} does not decode clean")
                return {}
            return o.value or {}
        fam = val(nested_family_id)
        fd = ((fam.get("m_oFamDoc") or {}).get("value") or {})
        if fd.get("m_contentDocGUID") != guid:
            bad.append("nested Family does not carry our content GUID")
        sym = val(symbol_id)
        if sym.get("m_familyId") != nested_family_id:
            bad.append("nested symbol does not point at the nested Family")
        for iid in instance_ids:
            o = val(iid)
            ii = ((o.get("m_pInstanceInfo") or {}).get("value") or {})
            if ii.get("m_symbolId") != symbol_id or o.get("m_masterSymbolId") != symbol_id:
                bad.append(f"instance {iid} does not point at symbol {symbol_id}")
            r = fi.decode(0, iid, 103)
            if r is None or not r.clean:
                bad.append(f"instance {iid} rep does not decode clean")
            if associations:
                cells = ((o.get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
                got = [(d.get("m_famParamId"), d.get("m_elemPropId"))
                       for c in cells if c.get("ptr_class") == "FamilyParametrizedElemParamsCell"
                       for d in ((c.get("value") or {}).get("m_paramDrivenData") or [])]
                if got != [tuple(a) for a in associations]:
                    bad.append(f"instance {iid} does not carry its parameter associations")
        for lid in lock_ids:
            a = val(lid)
            ws = [((w.get("m_pWitnessRef") or {}).get("value") or {}).get("m_geomRef") or {}
                  for w in a.get("m_witnessRefs") or []]
            if not any(g.get("m_elemId") in set(instance_ids) for g in ws):
                bad.append(f"lock {lid} does not witness a nested instance")
        rep["locks"] = len(lock_ids)
        rep["units"] = len(fi.units)
        with open_rvt(path) as f:
            lat = decode_latest(f.inflate("Global/Latest"))
        mgr = ((lat.value.get("m_pAppInfoManager") or {}).get("value") or {}).get("m_appInfoArr") or []
        fm = next((x.get("value") for x in mgr if isinstance(x, dict)
                   and x.get("ptr_class") == "FamilyMgr"), {}) or {}
        if not any(guid in (e.get("m_familyDocGUIDs") or []) for e in fm.get("m_arrLoadedFamilyInfo") or []):
            bad.append("FamilyMgr has no entry for the nested document")
        from . import factory as F
        with open_rvt(path) as f:
            cd = b"".join(f.inflate_all("Global/ContentDocuments"))
        ents, _tail = F.parse_content_documents(cd)
        rep["content_documents"] = len(ents)
        if guid not in {str(g) for g, _a in ents}:
            bad.append("Global/ContentDocuments has no entry for the nested document")
    from ..famload import four_registry_census
    reg = four_registry_census(path)
    rep["registries_coherent"] = bool(reg.get("coherent"))
    if not reg.get("coherent"):
        bad.append("the four document registries disagree (save units / ContentDocuments / "
                   "ContentTable / FamilyMgr)")
    findings = CL.check_file(path)
    rep["constraint_law"] = findings
    if findings:
        bad.append(f"constraint law: {len(findings)} finding(s)")
    if validate:
        from ..validate import validate_file
        vr = validate_file(path, family=True)
        errs = [f"[{f.layer}] {f.where}: {f.message}" for f in vr.errors]
        rep["validate"] = {"verdict": "VALID" if not errs else "INVALID",
                           "n_errors": len(errs), "n_warnings": len(vr.warnings),
                           "errors": errs[:20]}
        if errs:
            bad.append(f"rvt_validate (family mode): {len(errs)} error(s)")
    rep["ok"] = not bad
    return rep


# ---------------------------------------------------------------------------
# the public entry point
# ---------------------------------------------------------------------------

def nest_family(host_rfa: str, out_rfa: str, child: ProductArg,
                points: Sequence[Sequence[float]], *,
                validate: bool = True, locks: Sequence[Any] = (),
                associate: Optional[Dict[str, str]] = None) -> NestResult:
    """Embed ``child`` (a :class:`rvt.famgen.factory.FamilyProduct`, or a
    callable ``f(start_id) -> FamilyProduct`` so its ids land above the
    host's) into the generated family ``host_rfa`` and place one unrotated,
    free instance at every point (feet, family coordinates), writing
    ``out_rfa``.

    All or nothing: every precondition is checked and every record is
    authored and round-trip-gated before the one write; the written file is
    then read back (:func:`verify_nested`) and, if any check fails, removed
    and :class:`NestError` raised.  ``child`` must have been built under the
    host's release (build both inside the same ``release_build_context``).

    ``locks`` = :class:`Lock` (or ``(instance index, reference, host RefPlane
    id)``) entries: each locks that instance's centre reference to the plane
    -- refused unless the placed reference already lies on the plane.
    ``associate`` = ``{host parameter caption: nested INSTANCE parameter
    caption}``: every placed instance's nested parameter follows the host's.
    """
    if not str(host_rfa).lower().endswith(".rfa") or not os.path.isfile(host_rfa):
        raise NestError(f"host must be an existing .rfa: {host_rfa!r}")
    if not str(out_rfa).lower().endswith(".rfa"):
        raise NestError(f"output must be an .rfa path: {out_rfa!r}")
    if os.path.abspath(out_rfa) == os.path.abspath(host_rfa):
        raise NestError("refusing to overwrite the host in place")
    pts = _points(points)
    lks = _locks(locks)
    from ..frontdoor.release_ctx import host_release_context
    with host_release_context(host_rfa):
        try:
            return _nest(host_rfa, out_rfa, child, pts, validate=validate, locks=lks,
                         associate=associate)
        except NestError:
            raise
        except Exception as exc:                               # noqa: BLE001
            # one refusal type for every failure (#936 review).  Nothing to
            # remove: the write and the read-back each discard their own
            # output, and every step before the write touches no file (a
            # pre-existing out_rfa is left as it was)
            raise NestError(f"nesting failed: {type(exc).__name__}: {exc}") from exc


def _nest(host_rfa: str, out_rfa: str, child: ProductArg,
          pts: List[Tuple[float, float, float]], *, validate: bool,
          locks: Sequence[Lock] = (), associate: Optional[Dict[str, str]] = None
          ) -> NestResult:
    host = L.survey_host(host_rfa, category=None)
    frame = _host_frame(host)
    prebuilt = not callable(child)
    product = child(int(host.watermark) + 1) if callable(child) else child
    if not hasattr(product, "doc"):
        raise NestError(f"child must be a FamilyProduct or a callable returning one, "
                        f"not {type(product).__name__}")
    try:
        L._require_ids_above(product, host.watermark)
    except L.LoaderError as exc:
        raise NestError(str(exc)) from exc
    if product.doc.connectors:
        raise NestError("nesting a family with connectors is not supported in this pass")
    cat = L.product_category(product)
    host = L.bind_category(host, cat)
    if host.category_gstyle == L.INVALID:
        raise NestError(f"host family has no GStyleElem for the nested category {cat}: "
                        "a nested family of a category the host does not carry is not "
                        "supported in this pass")
    try:
        authored = L._author_load(product, host, place=False, symbol_solid=True,
                                  circuit_slots=0)
    except L.LoaderError as exc:
        raise NestError(f"loading the nested document failed: {exc}") from exc
    _family_host_flavour(authored)
    plan = authored.plan
    # Revit requires family names in one document to be unique (#936 review)
    taken = {str((host.doc.value(fid) or {}).get("m_name") or "")
             for fid in host.doc.ids_of_class("Family")}
    if plan.family_name in taken:
        raise NestError(f"the host already holds a family named {plan.family_name!r}; "
                        "family names in one document must be unique")
    lock_plan = _plan_locks(locks, pts, product, host)
    lock_ctx = _host_lock_context(host, frame) if lock_plan else {}
    assoc = _plan_associations(associate, product, plan, host, frame)
    extent = _symbol_extent(authored)
    first = authored.max_host_id + 1
    inst = [author_nested_instance(first + i, p, product=product, plan=plan, frame=frame,
                                   category=cat, gstyle=host.category_gstyle, extent=extent,
                                   associations=assoc)
            for i, p in enumerate(pts)]
    nxt = first + len(inst)
    lock_els = [author_instance_lock(nxt + k, lp, instance_id=inst[lp.instance].elem_id,
                                     symbol_id=plan.symbol_id, frame=frame, ctx=lock_ctx)
                for k, lp in enumerate(lock_plan)]
    inst = inst + lock_els
    gate = L._roundtrip_gate(authored.elements + inst)
    if gate.get("failed", 1) != 0 or gate.get("roundtrip_ok", 0) != gate.get("records", -1):
        raise NestError(f"a record failed the encode/decode round trip: {gate.get('failures', [])[:6]}")
    authored.elements = sorted(authored.elements + inst, key=lambda e: e.elem_id)
    new_latest, cd_new, reg = _edit_family_host_registries(host_rfa, authored)

    out_dir = os.path.dirname(os.path.abspath(out_rfa))
    os.makedirs(out_dir, exist_ok=True)
    try:
        wr = L._commit_and_write(host_rfa, out_rfa, host, [authored], new_latest, cd_new,
                                 identity=_host_identity(host_rfa))
    except Exception as exc:                                   # noqa: BLE001
        _discard(out_rfa)
        raise NestError(f"writing the host failed: {type(exc).__name__}: {exc}") from exc
    lock_ids = [e.elem_id for e in lock_els]
    ids = [e.elem_id for e in inst if e.elem_id not in set(lock_ids)]
    try:
        ver = verify_nested(out_rfa, nested_family_id=plan.host_family_id,
                            symbol_id=plan.symbol_id, instance_ids=ids, guid=plan.guid,
                            validate=validate, lock_ids=lock_ids,
                            associations=[(a.host_param, a.twin) for a in assoc])
    except Exception as exc:                                   # noqa: BLE001
        _discard(out_rfa)                  # a reader that crashes never leaves output
        raise NestError(f"verifying the written host failed: "
                        f"{type(exc).__name__}: {exc}") from exc
    if not ver["ok"]:
        _discard(out_rfa)
        raise NestError(f"written host failed verification: {ver['problems'][:6]}")
    return NestResult(
        ok=True, out_path=out_rfa, family_name=plan.family_name,
        nested_family_id=plan.host_family_id, symbol_id=plan.symbol_id,
        instance_ids=ids, lock_ids=lock_ids,
        associations=[{"host_param": a.host_param, "nested_twin": a.twin,
                       "host": a.host_caption, "nested": a.child_caption} for a in assoc],
        proofs={"roundtrip_gate": {k: gate.get(k) for k in ("records", "roundtrip_ok", "failed")},
                "registries": reg, "write": wr, "verify": ver,
                "load": {k: authored.proofs.get(k) for k in ("plan", "save_unit")}},
        notes=list(host.notes) + [
            f"nested instances are free-placed and unrotated; {len(lock_ids)} centre-"
            f"reference lock(s) to host planes, {len(assoc)} host parameter(s) "
            "associated to the nested family's",
            "validator green and an empty constraint-law report are facts about "
            "the file; no desktop-Revit verdict exists for nested families "
            "(hard rule 4)"] + ([
            "the child was passed prebuilt, so its build release was not checked "
            "against the host's; pass a callable to build it under the host's "
            "release"] if prebuilt else []))


def _host_identity(host_rfa: str) -> Dict[str, Any]:
    """The host's own BasicFileInfo username (ours, ``rvt-writer``, on a
    generated family) -- the nested write keeps it rather than blanking it."""
    from ..container import open_rvt
    from ..identity import BFI_STREAM
    from .. import stream_encoders as se
    with open_rvt(host_rfa) as f:
        if not f.has(BFI_STREAM):
            return {"username": ""}
        m = se.decode_basic_file_info(f.raw(BFI_STREAM))
    return {"username": str(m.get("username") or "")}


def _discard(path: str) -> None:
    for p in (path, path + ".pass1.tmp"):
        try:
            os.remove(p)
        except OSError:
            pass

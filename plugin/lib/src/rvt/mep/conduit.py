"""conduit.py — CONDUIT + CABLE TRAY (linear MEP curves) CRUD (MEP stream: conduit).

The contractor's bread and butter: straight conduit RUNS, their ELBOW
fittings, cable-tray runs, and their TYPES.  Every rule below was decoded
from the Revit-MEP sample (``samples/rmebasicsampleproject.rvt``: 20
``RbsConduitCurve`` in 8 ``ConduitRun``s joined by 13 elbows) — see
``docs/writer/mep-conduit.md`` for the byte-level evidence.

THE MODEL (verified on the corpus):

* A conduit is an ``RbsConduitCurve`` (class ``0x0d63``) — an MEP curve
  driven by an ``RbsCurveDriver{GLine}`` location line (feet, world
  coordinates), a nominal ``m_dWidthOrDiameter``, per-end elevations
  ``m_dOffsetStart/End = endpoint.z − level.z``, and TWO end
  ``Connector``s (``m_nIndex`` 0 = start / 1 = end,
  ``SegmentConnectorPosition.m_paramOnCurve`` 0.0 / 1.0).  Every conduit
  belongs to a ``ConduitRun`` (``m_runId``) and OWNS a
  ``SegmentCenterLine`` companion element
  (``ConduitDomainDesignPropertyManager.m_idCenterLine``, ElemTable owner
  = the conduit) carrying the segment's ``GLine``.
* An elbow is a plain ``FamilyInstance`` (category
  ``OST_ConduitFitting`` −2008128) of the run type's
  ``m_idDefaultElbow`` family symbol.  Fittings are FLEXIBLE families: the
  instance points at a per-CONFIGURATION anonymous ``FamilySymbol`` clone
  (2"×2" 90° → symbol 679082, shared by ALL twelve such elbows) while
  ``m_masterSymbolId`` is the real type (662459 ``Conduit Elbow: Standard``).
  So a new elbow of an existing configuration REUSES the clone (the same
  proven pattern as door cut-clones).  Its frame is EXACTLY derivable from
  its two conduits (frame error < 1e-13 on all 13 corpus fittings):
  corner ``C`` = the two axes' intersection, ``X = unit(C − A_end)``,
  ``Y = unit(B_end − C)``, ``Z = X×Y`` (``m_3x3`` columns X,Y,Z);
  ``m_or = C``; ``m_instOrigin = C − (0,0,level.z)``; connector 1 ↔ leg A,
  connector 2 ↔ leg B; both legs are trimmed back from the corner by
  ``bendRadius + straightExtension`` (2": 0.890625 + 0.166667 = 1.0573 ft).
  The elbow owns a ``ConduitFittingCenterLine`` whose curves are
  ``GLine(legA) + GArc(R, 90°) + GLine(legB)``.
* The connector graph is MUTUAL and typed by the TARGET connector's kind
  (Revit ``ConnectorType``): curve/fitting ends are ``End`` (connType 1),
  equipment surface connectors are ``Surface`` (16), circuits ``Logical``
  (4).  A curve end also carries a link to its own opposite end
  ``{self, other_index, 1}``.
* A run (``ConduitRun``, class ``0x0368``, category −2008149, rep =
  ``SerializedDummy``) is the ordered path list
  ``m_elemIdArr = [conduit, elbow, conduit, ...]``, ``m_typeId = the run's
  conduit type``, ElemTable owner = its first conduit.
* Cable trays (``CableTray`` 0x02b6, category −2008130) share the whole
  ``RbsCurve`` chain with conduits — the leaf differs by three fields
  (``m_calculatedSize``, ``m_oDesignPropManager``, ``m_rungSpace``).  NO
  cable-tray specimen exists in any corpus file, so trays are SYNTHESISED
  by class-morphing a conduit specimen (schema-directed, structurally exact,
  but acceptance-unproven: labelled EXPERIMENTAL).

Public API (all take a :class:`rvt.mutate.Document` — ``Document.from_file``
for a user project):

    READ      inventory_runs(doc), conduit_types(doc), cable_tray_types(doc),
              conduit_standards(doc), size_row(doc, type_id, nominal_ft),
              elbow_specimens(doc), run_report(doc, run_id)
    CREATE    add_conduit_run(doc, p0_ft, p1_ft, level_id, type_or_size)
              add_conduit_path(doc, points_ft, level_id, type_id, size)  # elbows
              add_cable_tray_run(doc, p0_ft, p1_ft, level_id, tray_type, w, h)
              commit_created(src_rvt, out_path, plan)     # write the .rvt
    MODIFY    resize_run(doc, id, nominal_ft), move_run(doc, id, dxyz_ft),
              extend_run(doc, conduit_id, delta_ft, end="p1"),
              retype_run(doc, id, new_type_id), set_run_elevation(...)
    DELETE    delete_run(doc, run_id), delete_conduit(doc, id),
              delete_fitting(doc, id)      # -> plans for manipulate.commit_plans

The MODIFY / DELETE verbs return :mod:`rvt.manipulate` plans (write with
``manipulate.commit_plans`` / verify with ``verify_manipulated``); the
CREATE verbs return a :class:`ConduitPlan` of :class:`rvt.mutate.NewElement`
objects (write with :func:`commit_created`, prove with
``rvt.commit.verify_written``).

``python -m rvt.mep.conduit [project.rvt]`` prints the run inventory.
"""
from __future__ import annotations

import copy
import dataclasses
import math
import struct
import sys
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from ..mutate import (CLASS_ELEMENT_HEADER, CLASS_SERIALIZED_DUMMY,
                      Document, ElemRecPlan, NewElement)

# ---------------------------------------------------------------------------
# schema classes (Revit 2026, verified against Formats/Latest)
# ---------------------------------------------------------------------------
CLASS_RBS_CONDUIT_CURVE = 0x0D63          # RbsConduitCurve
CLASS_CABLE_TRAY = 0x02B6                 # CableTray
CLASS_CONDUIT_RUN = 0x0368                # ConduitRun
CLASS_CABLE_TRAY_RUN = 0x02C2             # CableTrayRun
CLASS_SEGMENT_CENTERLINE = 0x0F20         # SegmentCenterLine
CLASS_CONDUIT_FITTING_CENTERLINE = 0x0366  # ConduitFittingCenterLine
CLASS_FITTING_CENTERLINE = 0x0367         # FittingCenterLine (cable-tray fittings)
CLASS_FAMILY_INSTANCE = 0x07C5            # FamilyInstance (elbows are these)
CLASS_RBS_CONDUIT_TYPE = 0x0D64           # RbsConduitType
CLASS_RBS_CABLE_TRAY_TYPE = 0x0D5A        # RbsCableTrayType
CLASS_CONDUIT_STANDARD_TYPE = 0x0370      # ConduitStandardType
CLASS_GELEMENT = 0x089E

# ---------------------------------------------------------------------------
# built-in categories (negative ElementIds), all conduit ones VERIFIED in the
# corpus; the cable-tray run / centre-line ones are inferred (see docs §7).
# ---------------------------------------------------------------------------
OST_Conduit = -2008132                    # RbsConduitCurve      [V]
OST_ConduitFitting = -2008128             # elbow FamilyInstance [V]
OST_ConduitRun = -2008149                 # ConduitRun           [V]
OST_ConduitCenterLine = -2008139          # SegmentCenterLine    [V]
OST_ConduitFittingCenterLine = -2008141   # ConduitFittingCenterLine [V]
OST_CableTray = -2008130                  # CableTray / RbsCableTrayType [V]
OST_CableTrayFitting = -2008126           # tray fittings        [V]
OST_CableTrayRun = -2008147               # CableTrayRun         [H]
OST_CableTrayCenterLine = -2008137        # tray SegmentCenterLine [H]

#: Revit ConnectorType wire codes seen in m_arrRefs[].m_connType
CONN_END = 1        # curve / fitting end connectors
CONN_LOGICAL = 4    # circuits
CONN_SURFACE = 16   # equipment surface connectors (panel / xfmr taps)

#: BuiltInParameter ids used on curves
BIP_ALL_MODEL_MARK = -1001203
BIP_ALL_MODEL_INSTANCE_COMMENTS = -1010106

INVALID_ID = -1
_FT_TO_MM = 304.8


# ===========================================================================
# small vector helpers (all geometry is in feet, world coordinates)
# ===========================================================================
def _v(a) -> List[float]:
    return [float(a[0]), float(a[1]), float(a[2]) if len(a) > 2 else 0.0]


def _sub(a, b):
    return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]


def _add(a, b):
    return [a[0] + b[0], a[1] + b[1], a[2] + b[2]]


def _mul(a, s):
    return [a[0] * s, a[1] * s, a[2] * s]


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def _norm(a) -> float:
    return math.sqrt(_dot(a, a))


def _unit(a) -> List[float]:
    n = _norm(a)
    if n < 1e-12:
        raise ValueError("zero-length vector")
    return [a[0] / n, a[1] / n, a[2] / n]


def _perp_normal(d: Sequence[float]) -> List[float]:
    """A unit vector perpendicular to direction ``d`` — the curve's
    ``m_vNormal`` convention: world +Z for non-vertical runs (17/20 corpus
    conduits), a horizontal perpendicular for vertical runs."""
    d = _unit(d)
    if abs(d[2]) < 0.98:
        # project +Z onto the plane perpendicular to d
        z = [0.0, 0.0, 1.0]
        n = _sub(z, _mul(d, _dot(z, d)))
        return _unit(n)
    return [0.0, -1.0, 0.0]        # vertical run: any horizontal perpendicular


def _bbox(points: Iterable[Sequence[float]], inflate: float = 0.0):
    pts = [list(p) for p in points]
    lo = [min(p[i] for p in pts) - inflate for i in range(3)]
    hi = [max(p[i] for p in pts) + inflate for i in range(3)]
    return [lo, hi]


def _dig(v: Any, *keys):
    """Walk value dicts through owned-pointer wrappers ({'value': {...}})."""
    cur = v
    for k in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(k)
        if isinstance(cur, dict) and "value" in cur and (
                "ptr_class" in cur or "pid" in cur):
            cur = cur.get("value")
    return cur


# ===========================================================================
# READ — catalog + inventory
# ===========================================================================
def _symbol_name(doc: Document, eid: int) -> Optional[str]:
    v = doc.value(eid) or {}
    si = _dig(v, "m_symbolInfo") or {}
    return si.get("m_name") if isinstance(si, dict) else None


def conduit_types(doc: Document) -> List[dict]:
    """Host-document ``RbsConduitType``s: id, name, standard, default elbow,
    with/without-fittings flavour."""
    out = []
    for tid in doc.ids_of_class("RbsConduitType"):
        v = doc.value(tid) or {}
        out.append({
            "type_id": tid, "name": _symbol_name(doc, tid),
            "standard_id": v.get("m_idStandardType"),
            "with_fitting": bool(v.get("m_bWithFitting")),
            "default_elbow_symbol": v.get("m_idDefaultElbow"),
            "default_tee_symbol": v.get("m_idDefaultTee"),
            "default_union_symbol": v.get("m_idDefaultUnion"),
        })
    out.sort(key=lambda r: r["type_id"])
    return out


def cable_tray_types(doc: Document) -> List[dict]:
    """Host-document ``RbsCableTrayType``s: id, name, shape enum, defaults."""
    out = []
    for tid in doc.ids_of_class("RbsCableTrayType"):
        v = doc.value(tid) or {}
        out.append({
            "type_id": tid, "name": _symbol_name(doc, tid),
            "cable_tray_type_enum": v.get("m_eCableTrayType"),
            "with_fitting": bool(v.get("m_bWithFitting")),
            "default_elbow_symbol": v.get("m_idDefaultElbow"),
            "min_bend_multiplier": v.get("m_dMinBendMultiplier"),
        })
    out.sort(key=lambda r: r["type_id"])
    return out


def conduit_standards(doc: Document) -> Dict[int, dict]:
    """The project's conduit STANDARDS with their SIZE TABLES.

    Decoded from ``ConduitSizesElem.m_sizes`` (a container of
    ``pair<ElementId(ConduitStandardType), ConduitSizeSet>``): every row gives
    nominal size, inner/outer diameter and MINIMUM BEND RADIUS (feet).  The
    elbow fittings' radius comes straight from this table (2" RNC Sch 80:
    0.890625 ft = the corpus elbows' ``GArc.m_radius``).
    Returns {standard_id: {name, sizes: [{nominal_ft, inner_ft, outer_ft,
    bend_radius_ft}, ...]}}.
    """
    out: Dict[int, dict] = {}
    ses = doc.ids_of_class("ConduitSizesElem")
    if not ses:
        return out
    v = doc.value(ses[0]) or {}
    for pair in v.get("m_sizes") or []:
        std = pair.get("first")
        rows = []
        for s in (pair.get("second") or {}).get("m_sizeData") or []:
            rows.append({
                "nominal_ft": float(s.get("m_dSize") or 0.0),
                "inner_ft": float(s.get("m_dInnerDiameter") or 0.0),
                "outer_ft": float(s.get("m_dOuterDiameter") or 0.0),
                "bend_radius_ft": float(s.get("m_dBendRadius") or 0.0),
            })
        out[std] = {"name": _symbol_name(doc, std) if doc.exists(std) else None,
                    "sizes": rows}
    return out


def size_row(doc: Document, conduit_type_id: int, nominal_ft: float,
             tol_in: float = 0.01) -> dict:
    """The size-table row of ``conduit_type_id``'s standard whose NOMINAL size
    is ``nominal_ft`` (raises if the standard does not list that size)."""
    t = doc.value(conduit_type_id) or {}
    std = t.get("m_idStandardType")
    table = conduit_standards(doc).get(std)
    if not table:
        raise LookupError(f"conduit type {conduit_type_id}: no size table for standard {std}")
    for row in table["sizes"]:
        if abs(row["nominal_ft"] - float(nominal_ft)) * 12.0 <= tol_in:
            return dict(row, standard_id=std)
    have = ", ".join(f"{r['nominal_ft'] * 12:.2f}in" for r in table["sizes"])
    raise LookupError(f"conduit type {conduit_type_id} (standard {std}) has no "
                      f"{float(nominal_ft) * 12:.3f}in size; available: {have}")


def _mm_label(feet: float) -> str:
    """The metric size label the corpus uses ('51 mmø' for 2")."""
    return f"{int(round(feet * _FT_TO_MM))} mmø"


def curve_geometry(doc: Document, eid: int) -> Optional[dict]:
    """Decoded geometry of a conduit / cable-tray curve: end points (ft), unit
    direction, length, nominal size, level, run, type, centre-line and the
    two end connectors with their references."""
    v = doc.value(eid)
    if not isinstance(v, dict):
        return None
    crv = _dig(v, "m_pCurveDriver", "m_pCrv")
    if not isinstance(crv, dict):
        return None
    org = crv.get("m_origin") or [0.0, 0.0, 0.0]
    d = crv.get("m_dirVec") or [1.0, 0.0, 0.0]
    ep = crv.get("m_endParams") or [0.0, 0.0]
    p0 = [org[i] + d[i] * ep[0] for i in range(3)]
    p1 = [org[i] + d[i] * ep[1] for i in range(3)]
    length = float(ep[1] - ep[0])
    conns = []
    mgr = _dig(v, "m_pConnectorManager") or {}
    for c in (mgr.get("m_connPtrArray") or []):
        cv = c.get("value") if isinstance(c, dict) else None
        if not isinstance(cv, dict):
            continue
        pos = None
        for m in cv.get("m_modifiers") or []:
            if isinstance(m, dict) and m.get("ptr_class") == "SegmentConnectorPosition":
                pos = (m.get("value") or {}).get("m_paramOnCurve")
        conns.append({"index": cv.get("m_nIndex"), "param": pos,
                      "refs": [r for r in (cv.get("m_arrRefs") or [])
                               if isinstance(r, dict)]})
    dp = _dig(v, "m_pDesignPropManager") or {}
    odp = _dig(v, "m_oDesignPropManager") or {}
    return {
        "id": eid, "class": doc.class_of(eid),
        "p0": p0, "p1": p1, "dir": [float(x) for x in d], "length_ft": length,
        "diameter_or_width_ft": float(v.get("m_dWidthOrDiameter") or 0.0),
        "height_ft": float(v.get("m_dHeight") or 0.0),
        "level_id": v.get("m_assocLevelId"), "type_id": v.get("m_idType"),
        "run_id": v.get("m_runId"),
        "offset_start_ft": v.get("m_dOffsetStart"),
        "offset_end_ft": v.get("m_dOffsetEnd"),
        "centerline_id": (dp.get("m_idCenterLine") if dp else None)
                          or (odp.get("m_idCenterLine") if odp else None),
        "size_label": (dp.get("m_sCalculatedSize") if dp else None)
                       or v.get("m_calculatedSize"),
        "connectors": conns,
    }


def _instance_frame(v: dict) -> dict:
    ii = _dig(v, "m_pInstanceInfo") or {}
    trf = ii.get("m_Trf") or {}
    return {"or": trf.get("m_or"), "m3x3": trf.get("m_3x3"),
            "symbol_id": ii.get("m_symbolId"),
            "master_id": v.get("m_masterSymbolId")}


def fitting_geometry(doc: Document, eid: int) -> Optional[dict]:
    """Decoded geometry of a conduit/tray fitting instance: corner (m_or),
    frame (columns X/Y/Z), symbol clone, master, connector references and
    its fitting centre-line id."""
    v = doc.value(eid)
    if not isinstance(v, dict) or doc.class_of(eid) != "FamilyInstance":
        return None
    fr = _instance_frame(v)
    conns = {}
    mgr = _dig(v, "m_pConnectorManager") or {}
    for c in (mgr.get("m_connPtrArray") or []):
        cv = c.get("value") if isinstance(c, dict) else None
        if isinstance(cv, dict):
            conns[cv.get("m_nIndex")] = [r for r in (cv.get("m_arrRefs") or [])
                                          if isinstance(r, dict)]
    dp = _dig(v, "m_pDesignPropManager") or {}
    return {"id": eid, "corner": fr["or"], "m3x3": fr["m3x3"],
            "symbol_clone_id": fr["symbol_id"], "master_symbol_id": fr["master_id"],
            "level_id": v.get("m_assocLevelId"), "connectors": conns,
            "centerline_id": dp.get("m_idCenterLine") if dp else None,
            "size_label": dp.get("m_sCalculatedSize") if dp else None,
            "category": doc.category_of(eid)}


def inventory_runs(doc: Document) -> dict:
    """Every conduit / cable-tray RUN and every loose curve in the host
    document, with size, length and level — the schedule a contractor reads.

    Returns {"conduit_runs": [...], "cable_tray_runs": [...],
    "loose_conduits": [...], "loose_cable_trays": [...], "totals": {...}}.
    Run members are reported in path order with each conduit's length and
    each fitting's connections; ``open_ends`` lists connectors that are not
    connected to anything (the ends a contractor extends).
    """
    def run_rows(run_cls: str, curve_cls: str) -> Tuple[List[dict], set]:
        rows, in_runs = [], set()
        for rid in doc.ids_of_class(run_cls):
            rv = doc.value(rid) or {}
            members = []
            total = 0.0
            n_curve = n_fit = 0
            for mid in rv.get("m_elemIdArr") or []:
                cls = doc.class_of(mid)
                if cls == curve_cls:
                    g = curve_geometry(doc, mid)
                    n_curve += 1
                    in_runs.add(mid)
                    total += g["length_ft"] if g else 0.0
                    members.append({"id": mid, "kind": "curve", "class": cls,
                                    "length_ft": g["length_ft"] if g else None,
                                    "size_ft": g["diameter_or_width_ft"] if g else None,
                                    "p0": g["p0"] if g else None,
                                    "p1": g["p1"] if g else None})
                elif cls == "FamilyInstance":
                    n_fit += 1
                    fg = fitting_geometry(doc, mid)
                    members.append({"id": mid, "kind": "fitting", "class": cls,
                                    "corner": fg["corner"] if fg else None,
                                    "master_symbol_id": fg["master_symbol_id"] if fg else None})
                else:
                    members.append({"id": mid, "kind": "other", "class": cls})
            open_ends = []
            for m in members:
                if m["kind"] != "curve":
                    continue
                g = curve_geometry(doc, m["id"]) or {}
                for c in g.get("connectors") or []:
                    external = [r for r in c["refs"] if r.get("m_id") != m["id"]]
                    if not external:
                        open_ends.append({"conduit": m["id"], "connector": c["index"]})
            rows.append({"run_id": rid, "class": run_cls,
                         "type_id": rv.get("m_typeId"),
                         "type_name": _symbol_name(doc, rv.get("m_typeId"))
                         if rv.get("m_typeId") not in (None, INVALID_ID) else None,
                         "n_curves": n_curve, "n_fittings": n_fit,
                         "total_length_ft": round(total, 4),
                         "members": members, "open_ends": open_ends})
        return rows, in_runs

    cr, in_c = run_rows("ConduitRun", "RbsConduitCurve")
    tr, in_t = run_rows("CableTrayRun", "CableTray")
    loose_c = [curve_geometry(doc, e) for e in doc.ids_of_class("RbsConduitCurve") if e not in in_c]
    loose_t = [curve_geometry(doc, e) for e in doc.ids_of_class("CableTray") if e not in in_t]
    return {
        "conduit_runs": cr, "cable_tray_runs": tr,
        "loose_conduits": [g for g in loose_c if g],
        "loose_cable_trays": [g for g in loose_t if g],
        "totals": {
            "conduit_runs": len(cr), "cable_tray_runs": len(tr),
            "conduits": len(doc.ids_of_class("RbsConduitCurve")),
            "cable_trays": len(doc.ids_of_class("CableTray")),
            "conduit_total_length_ft": round(sum(r["total_length_ft"] for r in cr), 4),
            "cable_tray_total_length_ft": round(sum(r["total_length_ft"] for r in tr), 4),
        },
    }


def run_report(doc: Document, run_id: int) -> dict:
    """One run in detail (members in path order, connector graph)."""
    inv = inventory_runs(doc)
    for r in inv["conduit_runs"] + inv["cable_tray_runs"]:
        if r["run_id"] == run_id:
            return r
    raise LookupError(f"run {run_id} not found (runs: "
                      f"{[r['run_id'] for r in inv['conduit_runs'] + inv['cable_tray_runs']]})")


def elbow_specimens(doc: Document) -> List[dict]:
    """Every conduit ELBOW instance usable as a clone donor, keyed by its
    configuration (master symbol, nominal size, bend angle).

    A new elbow can only be minted for a configuration that already has a
    compiled geometry-symbol clone in the file (the flexible fitting family's
    per-configuration symbol is regenerator-made and cannot be authored
    offline).  The size is read from the connected conduits' diameter, the
    angle from the two leg axes.
    """
    out = []
    seen = set()
    for fid in doc.ids_of_class("FamilyInstance"):
        if doc.category_of(fid) != OST_ConduitFitting:
            continue
        fg = fitting_geometry(doc, fid)
        if not fg or not fg["m3x3"]:
            continue
        neighbours = []
        for idx in (1, 2):
            refs = fg["connectors"].get(idx) or []
            if refs:
                neighbours.append(refs[0].get("m_id"))
        sizes, dirs = [], []
        for nb in neighbours:
            g = curve_geometry(doc, nb) if nb is not None else None
            if g:
                sizes.append(g["diameter_or_width_ft"])
                # travel direction along the leg (either sign is fine for angle)
                dirs.append(_unit(g["dir"]))
        if len(neighbours) != 2 or len(sizes) != 2:
            continue
        cosang = abs(_dot(dirs[0], dirs[1]))
        angle = math.acos(max(-1.0, min(1.0, cosang)))       # 90deg -> pi/2 (perpendicular legs)
        cfg = (fg["master_symbol_id"], round(sizes[0] * 12, 3), round(angle, 3))
        out.append({"elbow_id": fid, "master_symbol_id": fg["master_symbol_id"],
                    "symbol_clone_id": fg["symbol_clone_id"],
                    "nominal_ft": sizes[0], "angle_rad": angle,
                    "centerline_id": fg["centerline_id"],
                    "config": cfg, "shared_clone": cfg in seen})
        seen.add(cfg)
    return out


def find_elbow_specimen(doc: Document, master_symbol_id: int, nominal_ft: float,
                        angle_rad: float = math.pi / 2, size_tol_in: float = 0.05,
                        ang_tol: float = 0.02) -> Optional[dict]:
    """The clone-donor elbow for (master symbol, size, angle), or None."""
    for e in elbow_specimens(doc):
        if e["master_symbol_id"] != master_symbol_id:
            continue
        if abs(e["nominal_ft"] - nominal_ft) * 12.0 > size_tol_in:
            continue
        if abs(e["angle_rad"] - angle_rad) > ang_tol:
            continue
        return e
    return None


# ===========================================================================
# CREATE — plan data
# ===========================================================================
@dataclass
class ConduitPlan:
    """The NewElements one create call produced (all appended to the
    Document's ``new_elements``).  ``all()`` is what the writer commits."""
    kind: str                                   # 'conduit' | 'cable_tray'
    run: Optional[NewElement] = None
    curves: List[NewElement] = dc_field(default_factory=list)
    fittings: List[NewElement] = dc_field(default_factory=list)
    centerlines: List[NewElement] = dc_field(default_factory=list)
    notes: List[str] = dc_field(default_factory=list)

    def all(self) -> List[NewElement]:
        out = []
        if self.run is not None:
            out.append(self.run)
        out.extend(self.curves)
        out.extend(self.fittings)
        out.extend(self.centerlines)
        return out

    def to_json(self) -> dict:
        return {"kind": self.kind,
                "run": self.run.elem_id if self.run else None,
                "curves": [c.elem_id for c in self.curves],
                "fittings": [f.elem_id for f in self.fittings],
                "centerlines": [c.elem_id for c in self.centerlines],
                "notes": self.notes}


# ===========================================================================
# CREATE — specimen (clone donor) discovery
# ===========================================================================
def _donor_conduit(doc: Document, type_id: Optional[int]) -> int:
    """A real RbsConduitCurve to clone; prefer the same type, and a curve with
    exactly two well-formed connectors."""
    best = None
    for cid in doc.ids_of_class("RbsConduitCurve"):
        g = curve_geometry(doc, cid)
        if not g or len(g["connectors"]) != 2:
            continue
        if best is None:
            best = cid
        if type_id is not None and g["type_id"] == type_id:
            return cid
    if best is None:
        raise LookupError(f"{doc.project}: no RbsConduitCurve specimen to clone "
                          "(conduit / cable-tray creation needs one real conduit "
                          "in the template)")
    return best


def _donor_run(doc: Document, run_cls: str = "ConduitRun") -> Optional[int]:
    ids = doc.ids_of_class(run_cls)
    if ids:
        # simplest = fewest members
        return min(ids, key=lambda r: len((doc.value(r) or {}).get("m_elemIdArr") or []))
    # a ConduitRun donor works for a CableTrayRun (identical layout)
    if run_cls != "ConduitRun":
        return _donor_run(doc, "ConduitRun")
    return None


def _donor_centerline(doc: Document, cls: str = "SegmentCenterLine",
                      owner_class: str = "RbsConduitCurve") -> Optional[int]:
    """A centre-line element to clone, preferring one owned by ``owner_class``."""
    ids = doc.ids_of_class(cls)
    if not ids:
        return None
    for eid in ids:
        v = doc.value(eid) or {}
        own = v.get("m_OwnerId")
        if own is not None and own > 0 and doc.class_of(own) == owner_class:
            return eid
    return ids[0]


def _level_z(doc: Document, level_id: int) -> float:
    return float(doc._level_elevation(level_id))


def _phase_of(doc: Document, donor_val: dict, phase_id: Optional[int]) -> int:
    if phase_id is not None:
        return phase_id
    return donor_val.get("m_createdPhaseId", INVALID_ID)


# ===========================================================================
# CREATE — element builders
# ===========================================================================
def _set_astring_param(obj: dict, param_id: int, value: str) -> None:
    """Set an AString element parameter on a run element being built; a
    donor whose holder is null gets it authored, never the value dropped."""
    from ..manipulate import upsert_param_row
    upsert_param_row(obj, param_id, value, holder="m_pParamValueSetAString")


def _connector_dicts(mgr: dict) -> List[dict]:
    """The Connector value dicts of a connector manager, ordered by nIndex."""
    out = []
    for c in mgr.get("m_connPtrArray") or []:
        cv = c.get("value") if isinstance(c, dict) else None
        if isinstance(cv, dict):
            out.append(cv)
    out.sort(key=lambda cv: (cv.get("m_nIndex") if cv.get("m_nIndex") is not None else 0))
    return out


def _set_curve_connectors(obj: dict, eid: int,
                         end_refs: Dict[int, List[dict]],
                         self_pair: bool = True) -> None:
    """Rewrite the two end connectors of a curve object for a NEW element.

    ``end_refs[i]`` = the external references of end ``i`` (0 = start,
    1 = end), each ``{m_id, m_nIndex, m_connType}``.  Mirrors the corpus:
    each end also carries the self link ``{self, other_end, END}`` first
    (15/20 corpus conduits; open ends keep just the self link).
    """
    mgr = _dig(obj, "m_pConnectorManager") or {}
    mgr["m_setDeletedConnectors"] = []
    for cv in _connector_dicts(mgr):
        idx = cv.get("m_nIndex")
        if idx not in (0, 1):
            continue
        refs = []
        if self_pair:
            refs.append({"m_id": eid, "m_nIndex": 1 - idx, "m_connType": CONN_END})
        refs.extend(copy.deepcopy(end_refs.get(idx) or []))
        cv["m_arrRefs"] = refs
        # per-connector calculation state = a fresh, unassigned end
        for m in cv.get("m_modifiers") or []:
            mv = m.get("value") if isinstance(m, dict) else None
            if not isinstance(mv, dict):
                continue
            if m.get("ptr_class") == "SegmentConnectorPosition":
                mv["m_paramOnCurve"] = 0.0 if idx == 0 else 1.0
            elif m.get("ptr_class") == "SegmentConnectorCalculation":
                mv.update({"m_dActualFlow": 0.0, "m_dDemand": 0.0, "m_dFlow": 0.0,
                           "m_idSystem": INVALID_ID, "m_eDirection": 0,
                           "m_eSystemType": 0, "m_nSection": 0})


def _header_parents(header: dict) -> dict:
    parents = ((header.get("m_parents") or {}).get("value")) or {}
    if isinstance(header.get("m_parents"), dict):
        header["m_parents"]["value"] = parents
    return parents


def _make_curve(doc: Document, *, kind: str, eid: int, donor_id: int,
                p0: Sequence[float], p1: Sequence[float], level_id: int,
                type_id: int, size_ft: float, height_ft: Optional[float],
                run_id: int, centerline_id: int, phase_id: Optional[int],
                inner_ft: Optional[float], outer_ft: Optional[float],
                end_refs: Dict[int, List[dict]], neighbours: Iterable[int],
                size_label: Optional[str], rung_space_ft: float = 0.75) -> NewElement:
    """Build a conduit (kind='conduit') or cable-tray (kind='cable_tray')
    curve element by cloning ``donor_id`` (always a real RbsConduitCurve)."""
    p0, p1 = _v(p0), _v(p1)
    axis = _sub(p1, p0)
    length = _norm(axis)
    if length <= 1e-6:
        raise ValueError("curve p0 == p1")
    d = _unit(axis)
    lz = _level_z(doc, level_id)
    tval = doc.value(donor_id)
    obj = copy.deepcopy(tval)
    obj["m_id"] = eid
    obj["m_assocLevelId"] = level_id
    obj["m_famId"] = INVALID_ID
    obj["m_designOptionId"] = INVALID_ID
    obj["m_demolishedPhaseId"] = INVALID_ID
    obj["m_createdPhaseId"] = _phase_of(doc, tval, phase_id)
    obj["m_roomBounding"] = tval.get("m_roomBounding", True)
    # -- location line -------------------------------------------------------
    drv = _dig(obj, "m_pCurveDriver") or {}
    crv = _dig(drv, "m_pCrv") or {}
    crv["m_origin"] = list(p0)
    crv["m_dirVec"] = list(d)
    crv["m_endParams"] = [0.0, length]
    drv["m_sideJoins"] = []
    drv["m_controlJoinsSet"] = []
    drv["m_midParams"] = []
    drv["m_flip"] = False
    drv["m_sideAlignments"] = []
    drv["m_oControlData"] = None
    # -- size / offsets --------------------------------------------------------
    obj["m_dWidthOrDiameter"] = float(size_ft)
    obj["m_dHeight"] = float(height_ft if height_ft is not None else size_ft)
    obj["m_vNormal"] = _perp_normal(d)
    obj["m_dOffsetStart"] = p0[2] - lz
    obj["m_dOffsetEnd"] = p1[2] - lz
    obj["m_idType"] = type_id
    obj["m_idSystemCategory"] = INVALID_ID
    obj["m_idSegment"] = INVALID_ID
    obj["m_eHorOffset"] = 0
    obj["m_eVertOffset"] = 0
    obj["m_iEndReference"] = 0
    obj["m_bFittingLessPathState"] = False
    obj["m_bPlaceHolderEccentricOffsetState"] = False
    obj["m_lineAndArcRunId"] = INVALID_ID
    obj["m_runId"] = run_id
    # -- connectors --------------------------------------------------------------
    _set_curve_connectors(obj, eid, end_refs)
    # -- domain design-property manager / leaf fields --------------------------
    class_id, class_name, category = CLASS_RBS_CONDUIT_CURVE, "RbsConduitCurve", OST_Conduit
    if kind == "conduit":
        dp = _dig(obj, "m_pDesignPropManager")
        if not isinstance(dp, dict):
            obj["m_pDesignPropManager"] = {"ptr_class": "ConduitDomainDesignPropertyManager",
                                          "pid": -1, "value": {}}
            dp = obj["m_pDesignPropManager"]["value"]
        dp["m_idCenterLine"] = centerline_id
        if inner_ft is not None:
            dp["m_dInnerDiameter"] = float(inner_ft)
        if outer_ft is not None:
            dp["m_dOuterDiameter"] = float(outer_ft)
        dp["m_sCalculatedSize"] = size_label or _mm_label(size_ft)
    else:
        # CABLE TRAY leaf: swap the conduit's leaf fields for CableTray's
        # three own fields (schema 0x02b6) and its extrusion GStep class.
        class_id, class_name, category = CLASS_CABLE_TRAY, "CableTray", OST_CableTray
        obj.pop("m_pDesignPropManager", None)
        obj["m_calculatedSize"] = size_label or (
            f"{int(round(size_ft * _FT_TO_MM))} mmx{int(round((height_ft or size_ft) * _FT_TO_MM))} mm")
        obj["m_oDesignPropManager"] = {
            "ptr_class": "CableTrayDomainDesignPropertyManager", "pid": -1,
            "value": {"m_idCenterLine": centerline_id}}
        obj["m_rungSpace"] = float(rung_space_ft)
        obj["m_vNormal"] = [0.0, 0.0, 1.0]           # tray bottom faces down; up = +Z
        gs = _dig(obj, "m_geomSteps") or {}
        for lst in ("m_bRepFormGList", "m_nonBRepGList"):
            for step in gs.get(lst) or []:
                if isinstance(step, dict) and step.get("ptr_class") == "ConduitExtrusionGStep":
                    step["ptr_class"] = "CableTrayExtrusionGStep"
    # blank the Mark so Revit numbers it (avoids a duplicate-mark warning)
    _set_astring_param(obj, BIP_ALL_MODEL_MARK, "")

    # -- seq 101 header --------------------------------------------------------
    header = copy.deepcopy(doc.value(donor_id, 101)) or {}
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = category
    if kind != "conduit":
        header["m_classDef"] = {"m_ref": {"classref": "CableTray"}}
        # cable-tray regen parents: swap the conduit's global regen elements
        # for the cable-tray equivalents when the template has them
        parents = _header_parents(header)
        parents["m_regenOnly"] = _tray_regen_parents(doc, parents.get("m_regenOnly") or [])
    parents = _header_parents(header)
    phase = obj.get("m_createdPhaseId", INVALID_ID)
    deletion = {level_id, type_id, eid, run_id, centerline_id}
    deletion.update(int(n) for n in neighbours)
    if phase not in (None, INVALID_ID):
        deletion.add(phase)
    gstyle = _gstyle_for_category(doc, category)
    appearance = {level_id, type_id}
    if gstyle:
        appearance.add(gstyle)
    parents.update({
        "m_deletion": sorted(x for x in deletion if x not in (None, INVALID_ID)),
        "m_appearanceParents": sorted(appearance),
        "m_regenWildcards": [], "m_nonDetermRegenChildren": [],
        "m_dependencyParents": [], "m_deferredPropagationParents": [],
        "m_computedParametersParents": [],
    })
    half = 0.5 * (outer_ft if outer_ft else max(size_ft, height_ft or size_ft))
    bb = _bbox([p0, p1], inflate=half)
    header["m_pBBox"] = {"ptr_class": "Outline", "pid": -1, "value": {"m_minmax": bb}}
    el = NewElement(eid, kind, class_name, class_id, header, obj, None,
                    _elemrec(doc, eid), donor_id,
                    notes=[f"{class_name} cloned from {donor_id}: p0={_r3(p0)} p1={_r3(p1)} "
                           f"L={length:.4f}ft size={size_ft * 12:.3f}in run={run_id} "
                           f"centerline={centerline_id}",
                           "seq103 = SerializedDummy (Revit regenerates the extrusion "
                           "solid from the RbsCurveGStep/…ExtrusionGStep recipe)"])
    return el


def _r3(p):
    return [round(float(x), 3) for x in p]


def _gstyle_for_category(doc: Document, ost: int) -> Optional[int]:
    """The document GStyleElem (object style) whose m_categoryId is the
    built-in category ``ost`` (conduit reps' GInfo / appearance parents)."""
    cache = getattr(doc, "_mep_gstyle_cache", None)
    if cache is None:
        cache = {}
        for gid in doc.ids_of_class("GStyleElem"):
            v = doc.value(gid) or {}
            cid = v.get("m_categoryId")
            if isinstance(cid, int) and cid < 0 and cid not in cache:
                cache[cid] = gid
        doc._mep_gstyle_cache = cache
    return cache.get(ost)


def _tray_regen_parents(doc: Document, conduit_regen: List[int]) -> List[int]:
    """Swap conduit-domain regen parents (GStyle, ConduitSizesElem,
    ConduitSettingsElem) for their cable-tray equivalents."""
    out = []
    tray_style = _gstyle_for_category(doc, OST_CableTray)
    sizes = doc.ids_of_class("CableTraySizesElem")
    settings = doc.ids_of_class("CableTraySettingsElem")
    for pid in conduit_regen:
        cls = doc.class_of(pid) if pid > 0 else None
        if cls == "GStyleElem":
            out.append(tray_style if tray_style else pid)
        elif cls == "ConduitSizesElem":
            out.append(sizes[0] if sizes else pid)
        elif cls == "ConduitSettingsElem":
            out.append(settings[0] if settings else pid)
        else:
            out.append(pid)
    return sorted(set(out))


def _make_centerline(doc: Document, *, eid: int, donor_id: int, owner_id: int,
                     curves: List[dict], category: int, bbox: list,
                     level_id: int, phase_id: Optional[int],
                     class_name: str = "SegmentCenterLine",
                     class_id: int = CLASS_SEGMENT_CENTERLINE) -> NewElement:
    """A companion centre-line element (owned by its curve / fitting)."""
    tval = doc.value(donor_id)
    obj = copy.deepcopy(tval)
    obj["m_id"] = eid
    obj["m_OwnerId"] = owner_id
    obj["m_createdPhaseId"] = _phase_of(doc, tval, phase_id)
    obj["m_CenterCurves"] = curves
    header = copy.deepcopy(doc.value(donor_id, 101)) or {}
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = category
    header["m_classDef"] = {"m_ref": {"classref": class_name}}
    parents = _header_parents(header)
    phase = obj.get("m_createdPhaseId", INVALID_ID)
    deletion = {owner_id, eid}
    if phase not in (None, INVALID_ID):
        deletion.add(phase)
    parents.update({
        "m_deletion": sorted(deletion), "m_regenOnly": [level_id],
        "m_regenWildcards": [], "m_nonDetermRegenChildren": [],
        "m_dependencyParents": [], "m_appearanceParents": [],
        "m_deferredParents": [], "m_deferredPropagationParents": [],
        "m_computedParametersParents": [],
        "m_hasNonDetermRegenChildren": False,
    })
    header["m_pBBox"] = {"ptr_class": "Outline", "pid": -1, "value": {"m_minmax": bbox}}
    # seq-103 rep: the tiny cached GElement = a GFilter with the two bbox
    # corners as GPoints (333 bytes on every corpus centre-line)
    rep = None
    trep = doc.decode(donor_id, 103)
    if trep is not None and trep.class_id == CLASS_GELEMENT and trep.clean:
        rep = copy.deepcopy(trep.value)
        gi = rep.get("m_GInfo") or {}
        gi["m_tag"] = eid
        rep["m_elementId"] = eid
        rep["m_bBox"] = copy.deepcopy(bbox)
        rep["m_tightbBox"] = copy.deepcopy(bbox)
        pts = [bbox[1], bbox[0]]           # max corner first, then min corner
        k = 0
        for sn in rep.get("m_subNodes") or []:
            for p in ((sn.get("value") or {}).get("m_subNodes") or []):
                pv = p.get("value") or {}
                if p.get("ptr_class") == "GPoint" and k < 2:
                    pv["m_coord"] = list(pts[k])
                    k += 1
    return NewElement(eid, "centerline", class_name, class_id, header, obj, rep,
                      _elemrec(doc, eid, owner_id=owner_id), donor_id,
                      notes=[f"{class_name} owned by {owner_id} "
                             f"(m_OwnerId + ElemTable owner), cloned from {donor_id}"])


def _make_run(doc: Document, *, eid: int, donor_id: int, type_id: int,
              members: List[int], owner_id: int, category: int,
              class_name: str, class_id: int, level_id: int,
              phase_id: Optional[int]) -> NewElement:
    tval = doc.value(donor_id)
    obj = copy.deepcopy(tval)
    obj["m_id"] = eid
    obj["m_typeId"] = type_id
    obj["m_elemIdArr"] = list(members)
    obj["m_createdPhaseId"] = _phase_of(doc, tval, phase_id)
    header = copy.deepcopy(doc.value(donor_id, 101)) or {}
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = category
    header["m_classDef"] = {"m_ref": {"classref": class_name}}
    header["m_pBBox"] = None
    parents = _header_parents(header)
    phase = obj.get("m_createdPhaseId", INVALID_ID)
    deletion = {eid, type_id}
    deletion.update(members)
    if phase not in (None, INVALID_ID):
        deletion.add(phase)
    parents.update({
        "m_deletion": sorted(deletion), "m_regenOnly": [],
        "m_regenWildcards": [], "m_nonDetermRegenChildren": [],
        "m_dependencyParents": [], "m_appearanceParents": [],
        "m_deferredParents": [], "m_deferredPropagationParents": [],
        "m_computedParametersParents": [],
        "m_hasNonDetermRegenChildren": True,
    })
    return NewElement(eid, "run", class_name, class_id, header, obj, None,
                      _elemrec(doc, eid, owner_id=owner_id), donor_id,
                      notes=[f"{class_name} {eid}: members {members}, owned by {owner_id}; "
                             "seq103 = SerializedDummy (runs carry no geometry)"])


def _elemrec(doc: Document, eid: int, owner_id: int = INVALID_ID) -> ElemRecPlan:
    return ElemRecPlan(elem_id=eid, original_id=eid,
                       creation_ep=doc.new_episode, modified_ep=doc.new_episode,
                       user_modified_ep=doc.new_episode, owner_id=owner_id)


# ===========================================================================
# CREATE — public API
# ===========================================================================
def _resolve_type_and_size(doc: Document, conduit_type_or_size,
                           size_ft: Optional[float]) -> Tuple[int, float, dict]:
    """(type_id, nominal_ft, size_row).  ``conduit_type_or_size`` may be a
    type id (then ``size_ft`` gives the nominal size, default = the donor's)
    or a plain nominal size in feet (then the most-used type is chosen)."""
    types = {t["type_id"]: t for t in conduit_types(doc)}
    if not types:
        raise LookupError(f"{doc.project}: no RbsConduitType in template")
    if isinstance(conduit_type_or_size, (int,)) and not isinstance(conduit_type_or_size, bool) \
            and conduit_type_or_size in types:
        tid = conduit_type_or_size
    else:
        size_ft = float(conduit_type_or_size) if size_ft is None else size_ft
        # the type most conduits already use (else the first type)
        usage: Dict[int, int] = {}
        for cid in doc.ids_of_class("RbsConduitCurve"):
            t = (doc.value(cid) or {}).get("m_idType")
            usage[t] = usage.get(t, 0) + 1
        tid = max(usage, key=usage.get) if usage else min(types)
    if size_ft is None:
        # default: the size the type is already used at, else its smallest
        for cid in doc.ids_of_class("RbsConduitCurve"):
            v = doc.value(cid) or {}
            if v.get("m_idType") == tid:
                size_ft = float(v.get("m_dWidthOrDiameter"))
                break
        if size_ft is None:
            std = conduit_standards(doc).get((doc.value(tid) or {}).get("m_idStandardType"))
            size_ft = std["sizes"][0]["nominal_ft"] if std and std["sizes"] else 2.0 / 12.0
    row = size_row(doc, tid, size_ft)
    return tid, float(size_ft), row


def add_conduit_run(doc: Document, p0_ft, p1_ft, level_id: int,
                    conduit_type_or_size, size_ft: Optional[float] = None,
                    phase_id: Optional[int] = None,
                    end_refs: Optional[Dict[int, List[dict]]] = None,
                    donor_id: Optional[int] = None) -> ConduitPlan:
    """CREATE one straight conduit RUN between two points (feet).

    Emits the three-element cluster a real run has: the ``RbsConduitCurve``
    (level-based; location line p0->p1; nominal size from the type's
    standard size table -> inner/outer diameters), its owned
    ``SegmentCenterLine``, and the ``ConduitRun`` (owned by the conduit)
    listing it.  Both ends are OPEN (unconnected) unless ``end_refs`` gives
    ``{0: [{m_id, m_nIndex, m_connType}], 1: [...]}`` (elements planned in
    the SAME commit; existing equipment cannot be back-linked here).
    ``conduit_type_or_size``: an ``RbsConduitType`` id (+ optional
    ``size_ft`` nominal) or just a nominal size in feet.
    """
    for lid, what in ((level_id, "level_id"),):
        if not doc.exists(lid):
            raise LookupError(f"{what} {lid} not in template {doc.project}")
    tid, nominal, row = _resolve_type_and_size(doc, conduit_type_or_size, size_ft)
    donor = donor_id if donor_id is not None else _donor_conduit(doc, tid)
    dscl = curve_geometry(doc, donor)["centerline_id"] or _donor_centerline(doc)
    drun = _donor_run(doc, "ConduitRun")
    if dscl is None or drun is None:
        raise LookupError(f"{doc.project}: missing centre-line/run specimen "
                          f"(scl={dscl}, run={drun})")
    run_id = doc.next_id()
    cid = doc.next_id()
    scl_id = doc.next_id()
    plan = ConduitPlan(kind="conduit")
    curve = _make_curve(
        doc, kind="conduit", eid=cid, donor_id=donor, p0=p0_ft, p1=p1_ft,
        level_id=level_id, type_id=tid, size_ft=nominal, height_ft=None,
        run_id=run_id, centerline_id=scl_id, phase_id=phase_id,
        inner_ft=row["inner_ft"], outer_ft=row["outer_ft"],
        end_refs=end_refs or {}, neighbours=_neighbour_ids(end_refs or {}),
        size_label=_mm_label(nominal))
    plan.curves.append(curve)
    p0, p1 = _v(p0_ft), _v(p1_ft)
    bb = _bbox([p0, p1], inflate=row["outer_ft"] / 2.0)
    scl = _make_centerline(
        doc, eid=scl_id, donor_id=dscl, owner_id=cid,
        curves=[_gline(p0, p1)], category=OST_ConduitCenterLine, bbox=bb,
        level_id=level_id, phase_id=phase_id)
    plan.centerlines.append(scl)
    run = _make_run(doc, eid=run_id, donor_id=drun, type_id=tid, members=[cid],
                    owner_id=cid, category=OST_ConduitRun,
                    class_name="ConduitRun", class_id=CLASS_CONDUIT_RUN,
                    level_id=level_id, phase_id=phase_id)
    plan.run = run
    plan.notes.append(f"straight conduit run {run_id}: conduit {cid} "
                      f"({nominal * 12:.3f}in, type {tid}) + centreline {scl_id}, "
                      f"L={_norm(_sub(p1, p0)):.4f} ft, both ends open")
    _register(doc, plan)
    return plan


def _neighbour_ids(end_refs: Dict[int, List[dict]]) -> List[int]:
    out = []
    for refs in (end_refs or {}).values():
        for r in refs or []:
            if isinstance(r, dict) and isinstance(r.get("m_id"), int):
                out.append(r["m_id"])
    return out


def _gline(p0, p1) -> dict:
    """A GLine value dict from p0 to p1 (endParams [0, length])."""
    p0, p1 = _v(p0), _v(p1)
    d = _sub(p1, p0)
    L = _norm(d)
    return {"ptr_class": "GLine", "pid": -1,
            "value": {"m_GInfo": {"m_categoryId": -1, "m_tag": -1,
                                  "m_controlCommand": 0, "m_flags": 17301504},
                      "m_endParams": [0.0, L],
                      "m_origin": list(p0), "m_dirVec": _unit(d)}}


def _garc(center, xvec, yvec, radius, t0=0.0, t1=math.pi / 2) -> dict:
    return {"ptr_class": "GArc", "pid": -1,
            "value": {"m_GInfo": {"m_categoryId": -1, "m_tag": -1,
                                  "m_controlCommand": 0, "m_flags": 17301504},
                      "m_endParams": [float(t0), float(t1)],
                      "m_xVec": list(xvec), "m_yVec": list(yvec),
                      "m_radius": float(radius), "m_center": list(center),
                      "m_bFilled": False}}


def add_conduit_path(doc: Document, points_ft: Sequence[Sequence[float]],
                     level_id: int, conduit_type_or_size,
                     size_ft: Optional[float] = None,
                     with_elbows: bool = True,
                     phase_id: Optional[int] = None,
                     donor_id: Optional[int] = None,
                     require_elbows: bool = False) -> ConduitPlan:
    """CREATE a multi-segment conduit RUN through ``points_ft`` (a polyline,
    consecutive segments meeting at 90°), with ELBOW fittings at the corners.

    Corners are jointed only when consecutive segments are perpendicular
    (±2°) AND the template holds an elbow specimen of the same (default-elbow
    family, nominal size, 90°) configuration; the elbow's per-configuration
    geometry symbol clone is REUSED (m_symbolId = clone, m_masterSymbolId =
    the type's m_idDefaultElbow).  Both legs are trimmed back from the corner
    by ``bendRadius + straightExtension`` exactly as the corpus fittings are.
    If a corner cannot be jointed (``with_elbows=False``, no specimen, or a
    non-90° angle) the segments simply meet as open ends within the same run
    (``require_elbows=True`` raises instead).  Returns the ConduitPlan
    (run + N curves + M elbows + N+M centre-lines).
    """
    pts = [_v(p) for p in points_ft]
    if len(pts) < 2:
        raise ValueError("path needs >= 2 points")
    if len(pts) == 2:
        return add_conduit_run(doc, pts[0], pts[1], level_id, conduit_type_or_size,
                               size_ft=size_ft, phase_id=phase_id, donor_id=donor_id)
    if not doc.exists(level_id):
        raise LookupError(f"level_id {level_id} not in template {doc.project}")
    tid, nominal, row = _resolve_type_and_size(doc, conduit_type_or_size, size_ft)
    tval = doc.value(tid) or {}
    donor = donor_id if donor_id is not None else _donor_conduit(doc, tid)
    dscl = curve_geometry(doc, donor)["centerline_id"] or _donor_centerline(doc)
    drun = _donor_run(doc, "ConduitRun")
    lz = _level_z(doc, level_id)

    # elbow specimen for this type/size (clone donor)
    master = tval.get("m_idDefaultElbow")
    spec = None
    if with_elbows and master not in (None, INVALID_ID):
        spec = find_elbow_specimen(doc, master, nominal)
    plan = ConduitPlan(kind="conduit")
    if spec is None:
        msg = (f"no elbow specimen for conduit type {tid} default-elbow master "
               f"{master} at {nominal * 12:.3f}in in {doc.project}: corners left as "
               f"OPEN butt joints (segments still share the run)")
        if require_elbows:
            raise LookupError(msg)
        plan.notes.append(msg)

    # elbow trim = bend radius (size table) + straight extension (= nominal)
    R = float(row["bend_radius_ft"])
    ext = float(nominal)
    trim = R + ext if spec is not None else 0.0

    # ids: run, then per segment a conduit + scl, per corner an elbow + cfcl
    run_id = doc.next_id()
    nseg = len(pts) - 1
    seg_ids = [(doc.next_id(), doc.next_id()) for _ in range(nseg)]      # (conduit, scl)
    corner_ids = [(doc.next_id(), doc.next_id()) for _ in range(nseg - 1)]  # (elbow, cfcl)

    # decide which corners get an elbow (perpendicular legs, room to trim)
    joint = []
    for k in range(1, len(pts) - 1):
        a, b = _unit(_sub(pts[k], pts[k - 1])), _unit(_sub(pts[k + 1], pts[k]))
        la, lb = _norm(_sub(pts[k], pts[k - 1])), _norm(_sub(pts[k + 1], pts[k]))
        perp = abs(_dot(a, b)) < 0.035
        room = la > 2 * trim + 0.05 and lb > 2 * trim + 0.05
        use = bool(spec) and perp and room
        if bool(spec) and not perp:
            plan.notes.append(f"corner {k}: legs not perpendicular "
                              f"({math.degrees(math.acos(max(-1, min(1, abs(_dot(a, b)))))):.1f}° "
                              f"off 90) — left as an open butt joint")
        if bool(spec) and perp and not room:
            plan.notes.append(f"corner {k}: leg too short for the {trim:.3f} ft trim — open joint")
        joint.append(use)

    # trimmed segment endpoints
    seg_pts = []
    for k in range(nseg):
        s, e = list(pts[k]), list(pts[k + 1])
        d = _unit(_sub(e, s))
        if k > 0 and joint[k - 1]:
            s = _add(s, _mul(d, trim))
        if k < nseg - 1 and joint[k]:
            e = _sub(e, _mul(d, trim))
        seg_pts.append((s, e))

    # end references: conduit ends <-> elbow connectors (mutual)
    seg_refs: List[Dict[int, List[dict]]] = [{0: [], 1: []} for _ in range(nseg)]
    for k in range(1, nseg):
        if not joint[k - 1]:
            continue
        elbow_id, _ = corner_ids[k - 1]
        # elbow connector 1 <-> the NEXT segment's start (end 0);
        # elbow connector 2 <-> the PREVIOUS segment's end (end 1)
        seg_refs[k][0].append({"m_id": elbow_id, "m_nIndex": 1, "m_connType": CONN_END})
        seg_refs[k - 1][1].append({"m_id": elbow_id, "m_nIndex": 2, "m_connType": CONN_END})

    # build curves + centre-lines
    members: List[int] = []
    for k in range(nseg):
        cid, scl_id = seg_ids[k]
        p0, p1 = seg_pts[k]
        neigh = []
        if k > 0 and joint[k - 1]:
            neigh.append(corner_ids[k - 1][0])
        if k < nseg - 1 and joint[k]:
            neigh.append(corner_ids[k][0])
        curve = _make_curve(
            doc, kind="conduit", eid=cid, donor_id=donor, p0=p0, p1=p1,
            level_id=level_id, type_id=tid, size_ft=nominal, height_ft=None,
            run_id=run_id, centerline_id=scl_id, phase_id=phase_id,
            inner_ft=row["inner_ft"], outer_ft=row["outer_ft"],
            end_refs=seg_refs[k], neighbours=neigh, size_label=_mm_label(nominal))
        plan.curves.append(curve)
        bb = _bbox([p0, p1], inflate=row["outer_ft"] / 2.0)
        plan.centerlines.append(_make_centerline(
            doc, eid=scl_id, donor_id=dscl, owner_id=cid, curves=[_gline(p0, p1)],
            category=OST_ConduitCenterLine, bbox=bb, level_id=level_id,
            phase_id=phase_id))
    # build elbows + fitting centre-lines
    dcfcl = spec.get("centerline_id") if spec else None
    for k in range(1, nseg):
        if not joint[k - 1]:
            continue
        elbow_id, cfcl_id = corner_ids[k - 1]
        prev_id, next_id = seg_ids[k - 1][0], seg_ids[k][0]
        corner = pts[k]
        a_end = seg_pts[k][0]        # NEXT segment's start point (leg A, connector 1)
        b_end = seg_pts[k - 1][1]    # PREVIOUS segment's end point (leg B, connector 2)
        elbow, cfcl = _make_elbow(
            doc, spec=spec, eid=elbow_id, cfcl_id=cfcl_id, corner=corner,
            a_id=next_id, a_end=a_end, a_conn=0, b_id=prev_id, b_end=b_end, b_conn=1,
            level_id=level_id, radius=R, ext=ext, outer_ft=row["outer_ft"],
            phase_id=phase_id, cfcl_donor=dcfcl or _donor_centerline(doc, "ConduitFittingCenterLine",
                                                                        "FamilyInstance"))
        plan.fittings.append(elbow)
        plan.centerlines.append(cfcl)
    # path order: conduit, elbow, conduit, elbow, conduit ...
    for k in range(nseg):
        members.append(seg_ids[k][0])
        if k < nseg - 1 and joint[k]:
            members.append(corner_ids[k][0])
    run = _make_run(doc, eid=run_id, donor_id=drun, type_id=tid, members=members,
                    owner_id=seg_ids[0][0], category=OST_ConduitRun,
                    class_name="ConduitRun", class_id=CLASS_CONDUIT_RUN,
                    level_id=level_id, phase_id=phase_id)
    plan.run = run
    plan.notes.append(
        f"conduit path run {run_id}: {nseg} segment(s), {sum(1 for j in joint if j)} "
        f"elbow(s) ({'specimen ' + str(spec['elbow_id']) + ' clone ' + str(spec['symbol_clone_id']) if spec else 'no elbow specimen'}), "
        f"trim {trim:.4f} ft (R {R:.4f} + ext {ext:.4f}), type {tid} @ {nominal * 12:.3f}in, "
        f"level z {lz:.4f}")
    _register(doc, plan)
    return plan


def _make_elbow(doc: Document, *, spec: dict, eid: int, cfcl_id: int, corner,
                a_id: int, a_end, a_conn: int, b_id: int, b_end, b_conn: int,
                level_id: int, radius: float, ext: float, outer_ft: float,
                phase_id: Optional[int], cfcl_donor: Optional[int]) -> Tuple[NewElement, NewElement]:
    """Clone the specimen elbow onto the corner defined by legs A (connector 1)
    and B (connector 2).  Frame: X = unit(C − A_end), Y = unit(B_end − C),
    Z = X×Y — reproduces every corpus elbow's stored m_3x3 to 1e-13."""
    donor = spec["elbow_id"]
    clone = spec["symbol_clone_id"]
    master = spec["master_symbol_id"]
    C = _v(corner)
    X = _unit(_sub(C, _v(a_end)))
    Y = _unit(_sub(_v(b_end), C))
    Z = _cross(X, Y)
    if _norm(Z) < 1e-6:
        raise ValueError("elbow legs are colinear")
    Z = _unit(Z)
    lz = _level_z(doc, level_id)
    tval = doc.value(donor)
    obj = copy.deepcopy(tval)
    obj["m_id"] = eid
    obj["m_assocLevelId"] = level_id
    obj["m_famId"] = INVALID_ID
    obj["m_designOptionId"] = INVALID_ID
    obj["m_demolishedPhaseId"] = INVALID_ID
    obj["m_createdPhaseId"] = _phase_of(doc, tval, phase_id)
    obj["m_hostId"] = INVALID_ID
    obj["m_workPlaneBased"] = False
    obj["m_elevation"] = 0.0
    obj["m_hostParam"] = 0.0
    obj["m_extraHostIds"] = []
    obj["m_explicitHostIds"] = []
    obj["m_refs"] = []
    obj["m_offsetPosArr"] = []
    obj["m_subInstTable"] = []
    obj["m_superInstanceId"] = INVALID_ID
    obj["m_ownerElemId"] = INVALID_ID
    obj["m_instOrigin"] = [C[0], C[1], C[2] - lz]     # level-local mirror of m_or
    obj["m_RefDir"] = list(X)
    obj["m_zAxis"] = list(Z)
    obj["m_masterSymbolId"] = master
    m3 = [[X[0], Y[0], Z[0]], [X[1], Y[1], Z[1]], [X[2], Y[2], Z[2]]]
    ii = _dig(obj, "m_pInstanceInfo") or {}
    ii["m_symbolId"] = clone
    ii["m_GRepId"] = 0
    ii["m_Trf"] = {"m_3x3": copy.deepcopy(m3), "m_or": list(C)}
    # connectors: 1 <-> leg A neighbour, 2 <-> leg B neighbour
    mgr = _dig(obj, "m_pConnectorManager") or {}
    mgr["m_setDeletedConnectors"] = []
    for cv in _connector_dicts(mgr):
        idx = cv.get("m_nIndex")
        if idx == 1:
            cv["m_arrRefs"] = [{"m_id": a_id, "m_nIndex": a_conn, "m_connType": CONN_END}]
        elif idx == 2:
            cv["m_arrRefs"] = [{"m_id": b_id, "m_nIndex": b_conn, "m_connType": CONN_END}]
        else:
            cv["m_arrRefs"] = []
    dp = _dig(obj, "m_pDesignPropManager")
    if isinstance(dp, dict):
        dp["m_idCenterLine"] = cfcl_id
        dp["m_lineAndArcRunId"] = INVALID_ID
        dp["m_idSpace"] = INVALID_ID
        dp["m_idRoom"] = INVALID_ID
    _set_astring_param(obj, BIP_ALL_MODEL_MARK, "")

    # geometry of the fitting centre-line: legA straight + 90° arc + legB straight
    a_end, b_end = _v(a_end), _v(b_end)
    arc_start = _sub(C, _mul(X, radius))          # on leg A
    arc_end = _add(C, _mul(Y, radius))            # on leg B
    center = _add(arc_start, _mul(Y, radius))     # = C - X*R + Y*R
    # the arc sweeps from the leg-A tangent to the leg-B tangent; only
    # perpendicular corners are jointed, so the sweep is a quarter turn
    sweep = math.pi / 2
    curves = [
        {"ptr_class": "GLine", "pid": -1,
         "value": {"m_GInfo": {"m_categoryId": -1, "m_tag": -1,
                                "m_controlCommand": 0, "m_flags": 17301504},
                    "m_endParams": [-float(_norm(_sub(arc_start, a_end))), -0.0],
                    "m_origin": list(arc_start), "m_dirVec": list(X)}},
        _garc(center, _mul(Y, -1.0), list(X), radius, 0.0, sweep),
        {"ptr_class": "GLine", "pid": -1,
         "value": {"m_GInfo": {"m_categoryId": -1, "m_tag": -1,
                                "m_controlCommand": 0, "m_flags": 17301504},
                    "m_endParams": [-float(_norm(_sub(b_end, arc_end))), -0.0],
                    "m_origin": list(b_end), "m_dirVec": list(Y)}},
    ]
    bb = _bbox([a_end, b_end, C], inflate=outer_ft / 2.0)

    # seq-101 header
    header = copy.deepcopy(doc.value(donor, 101)) or {}
    header["m_regenHistory"] = {"m_historyMap": []}
    header["m_categroryId"] = OST_ConduitFitting
    header["m_pBBox"] = {"ptr_class": "Outline", "pid": -1, "value": {"m_minmax": bb}}
    parents = _header_parents(header)
    # keep the donor's global parents (family, params, styles, symbol, clone);
    # replace the donor's own identity / neighbours / centre-line
    ddp = _dig(tval, "m_pDesignPropManager") or {}
    donor_locals = {donor, ddp.get("m_idCenterLine")}
    for cv in _connector_dicts(_dig(tval, "m_pConnectorManager") or {}):
        for r in cv.get("m_arrRefs") or []:
            donor_locals.add(r.get("m_id"))
    keep = [x for x in (parents.get("m_deletion") or []) if x not in donor_locals]
    phase = obj.get("m_createdPhaseId", INVALID_ID)
    deletion = set(keep) | {eid, cfcl_id, a_id, b_id, level_id, master, clone}
    if phase not in (None, INVALID_ID):
        deletion.add(phase)
    parents.update({
        "m_deletion": sorted(x for x in deletion if x not in (None, INVALID_ID)),
        "m_regenWildcards": [], "m_nonDetermRegenChildren": [],
        "m_dependencyParents": [], "m_deferredPropagationParents": [],
        "m_computedParametersParents": [],
    })
    app = set(parents.get("m_appearanceParents") or [])
    app.discard(donor)
    app |= {level_id, master, clone}
    parents["m_appearanceParents"] = sorted(x for x in app if x not in (None, INVALID_ID))

    # seq-103: clone the donor's small GElement (GInstance -> shared symbol
    # clone) and rewrite the transform, tag, boxes
    rep = None
    trep = doc.decode(donor, 103)
    if trep is not None and trep.class_id == CLASS_GELEMENT and trep.clean:
        rep = copy.deepcopy(trep.value)
        gi = rep.get("m_GInfo") or {}
        gi["m_tag"] = eid
        rep["m_elementId"] = eid
        for node in rep.get("m_subNodes") or []:
            nv = node.get("value") or {}
            info = ((nv.get("m_instanceInfo") or {}).get("value")) or {}
            if info:
                info["m_symbolId"] = clone
                info["m_Trf"] = {"m_3x3": copy.deepcopy(m3), "m_or": list(C)}
        rep["m_bBox"] = copy.deepcopy(bb)
        rep["m_tightbBox"] = copy.deepcopy(bb)
    elbow = NewElement(eid, "conduit_elbow", "FamilyInstance", CLASS_FAMILY_INSTANCE,
                       header, obj, rep, _elemrec(doc, eid), donor,
                       notes=[f"90° elbow at corner {_r3(C)}: clone of {donor} reusing "
                              f"geometry-symbol {clone} (master {master}); connector "
                              f"1 -> conduit {a_id} end {a_conn}, connector 2 -> "
                              f"conduit {b_id} end {b_conn}; frame X={_r3(X)} "
                              f"Y={_r3(Y)} Z={_r3(Z)}",
                              "seq103 = donor GElement (GInstance) re-framed onto the corner"])
    # the fitting centre-line
    cfcl_don = cfcl_donor
    cfcl = _make_centerline(
        doc, eid=cfcl_id, donor_id=cfcl_don, owner_id=eid, curves=curves,
        category=OST_ConduitFittingCenterLine, bbox=bb, level_id=level_id,
        phase_id=phase_id, class_name="ConduitFittingCenterLine",
        class_id=CLASS_CONDUIT_FITTING_CENTERLINE)
    return elbow, cfcl


def add_cable_tray_run(doc: Document, p0_ft, p1_ft, level_id: int,
                       tray_type_id: Optional[int] = None,
                       width_ft: float = 1.0, height_ft: float = 4.0 / 12.0,
                       rung_space_ft: float = 0.75,
                       phase_id: Optional[int] = None,
                       donor_id: Optional[int] = None) -> ConduitPlan:
    """CREATE one straight CABLE TRAY run (EXPERIMENTAL — synthesised).

    No cable-tray specimen exists in any 2026 sample, so the ``CableTray``
    (class 0x02b6) object is CLASS-MORPHED from a conduit specimen: identical
    ``RbsCurve`` chain, with CableTray's three own fields
    (``m_calculatedSize`` / ``m_oDesignPropManager`` /
    ``m_rungSpace``), a ``CableTrayExtrusionGStep`` in place of the conduit
    one, rectangular ``m_dWidthOrDiameter`` = width / ``m_dHeight`` =
    height, an ``RbsCableTrayType``, a ``CableTrayRun`` and a
    ``SegmentCenterLine``.  Structurally exact against the schema; Autodesk
    acceptance UNPROVEN (see docs §7).  No fittings (a tray elbow needs a
    compiled geometry clone that only Revit's regenerator can make).
    """
    if not doc.exists(level_id):
        raise LookupError(f"level_id {level_id} not in template {doc.project}")
    ttypes = cable_tray_types(doc)
    if not ttypes:
        raise LookupError(f"{doc.project}: no RbsCableTrayType in template")
    if tray_type_id is None:
        tray_type_id = ttypes[0]["type_id"]
    if tray_type_id not in {t["type_id"] for t in ttypes}:
        raise LookupError(f"cable tray type {tray_type_id} not in {[t['type_id'] for t in ttypes]}")
    donor = donor_id if donor_id is not None else _donor_conduit(doc, None)
    dscl = curve_geometry(doc, donor)["centerline_id"] or _donor_centerline(doc)
    drun = _donor_run(doc, "CableTrayRun")
    if dscl is None or drun is None:
        raise LookupError(f"{doc.project}: missing centre-line/run specimen for cable tray")
    run_id = doc.next_id()
    cid = doc.next_id()
    scl_id = doc.next_id()
    plan = ConduitPlan(kind="cable_tray")
    label = f"{int(round(width_ft * _FT_TO_MM))} mmx{int(round(height_ft * _FT_TO_MM))} mm"
    curve = _make_curve(
        doc, kind="cable_tray", eid=cid, donor_id=donor, p0=p0_ft, p1=p1_ft,
        level_id=level_id, type_id=tray_type_id, size_ft=width_ft, height_ft=height_ft,
        run_id=run_id, centerline_id=scl_id, phase_id=phase_id,
        inner_ft=None, outer_ft=None, end_refs={}, neighbours=[],
        size_label=label, rung_space_ft=rung_space_ft)
    plan.curves.append(curve)
    p0, p1 = _v(p0_ft), _v(p1_ft)
    bb = _bbox([p0, p1], inflate=max(width_ft, height_ft) / 2.0)
    scl = _make_centerline(
        doc, eid=scl_id, donor_id=dscl, owner_id=cid, curves=[_gline(p0, p1)],
        category=OST_CableTrayCenterLine, bbox=bb, level_id=level_id,
        phase_id=phase_id)
    plan.centerlines.append(scl)
    run = _make_run(doc, eid=run_id, donor_id=drun, type_id=tray_type_id, members=[cid],
                    owner_id=cid, category=OST_CableTrayRun,
                    class_name="CableTrayRun", class_id=CLASS_CABLE_TRAY_RUN,
                    level_id=level_id, phase_id=phase_id)
    plan.run = run
    plan.notes.append(
        f"EXPERIMENTAL cable-tray run {run_id}: tray {cid} ({width_ft * 12:.1f}in x "
        f"{height_ft * 12:.1f}in, type {tray_type_id}) morphed from conduit specimen "
        f"{donor}; SegmentCenterLine {scl_id}; category ids CableTrayRun={OST_CableTrayRun}"
        f"/CenterLine={OST_CableTrayCenterLine} are INFERRED (no specimen in corpus)")
    _register(doc, plan)
    return plan


def _register(doc: Document, plan: ConduitPlan) -> None:
    for el in plan.all():
        if el not in doc.new_elements:
            doc.new_elements.append(el)


# ===========================================================================
# CREATE — commit (like rvt.commit.commit_new_elements but keeps ElemTable owners)
# ===========================================================================
def commit_created(src_rvt: str, out_path: str, doc: Document,
                   plans: Sequence[ConduitPlan], *, verify: bool = False) -> dict:
    """Write the created conduit/cable-tray elements of ``plans`` to ``out_path``.

    Same splice as ``rvt.commit.commit_new_elements`` (records inserted into
    save-unit 0 before each sentinel, ElemRecs appended id-sorted, header
    count bumped, real CRCIO ECC, CFB rewrite, own BasicFileInfo) — but the
    ElemTable rows keep each element's true OWNER (a curve owns its
    centre-line and its run), which the generic commit path drops.
    Returns a report dict; ``verify=True`` appends ``rvt.commit
    .verify_written`` results.
    """
    from ..cfb_writer import write_cfb
    from ..container import open_rvt
    from .. import ecc
    from ..partitions import StreamWalker
    from ..roundtrip import read_entries
    from ..stream_encoders import decode_elemtable, encode_elemtable, global_prefix
    from ..streams_edit import elemtable_add_element
    from ..writer import BLOCK_TRL_TAG, gzip_member

    elements: List[NewElement] = []
    for p in plans:
        elements.extend(p.all())
    if not elements:
        raise ValueError("nothing to commit")
    records = [dict(doc.serialize(e)) for e in elements]
    if any(r is None for r in records):
        raise RuntimeError("rvt.encode not available")

    _ISIZE_ADJ = {4: 0, 5: 4, 6: -4, 7: 0}
    PART_HDR_COUNT_OFF = 14

    def _hdr_len(seq: int) -> int:
        # framing header of one record (its physical size in the segment)
        return 12 if seq == 101 else 16

    def _c_hdr_len(seq: int) -> int:
        # the block-counter identity ISIZE == hdr_len(seq)*A + C + adj counts
        # the WAVE-1 record header (i64 id [+u32 stamp] + u32 psize + u32
        # class_word) = 16 (seq 101) / 20 (seq 102/103); C = body bytes AFTER
        # the class word.  (rvt.commit uses 12/16 here and so leaves C too
        # large by 4*A on the touched blocks — the validator's counter warning.)
        return 16 if seq == 101 else 20

    entries = read_entries(src_rvt)
    new_streams: Dict[str, bytes] = {}
    with open_rvt(src_rvt) as f:
        parts = f.partition_streams()
        if len(parts) != 1:
            raise NotImplementedError(f"expected one partition stream, got {parts}")
        pname = parts[0]
        # -- ElemTable (rows with owners) ------------------------------------
        model = decode_elemtable(f.inflate("Global/ElemTable"))
        count_before = len(model["records"])
        creation_ep = max(r[2] for r in model["records"])
        for e in elements:
            plan = e.elemrec
            own = plan.owner_id if plan.owner_id is not None and plan.owner_id >= 0 \
                else 0xFFFFFFFFFFFFFFFF
            elemtable_add_element(model, e.elem_id, creation_ep=creation_ep,
                                  modified_ep=creation_ep, user_modified_ep=creation_ep,
                                  original_id=e.elem_id, owner_id=own, partition_id=0)
        count_after = len(model["records"])
        watermark_after = model["footer"]["last_id"]
        et_new = encode_elemtable(model)
        et_logical = global_prefix("Global/ElemTable") + gzip_member(et_new, level=3)
        new_streams["Global/ElemTable"] = ecc.frame_stream(et_logical)
        # -- Partitions/<N>: append records before each unit-0 sentinel -------
        logical = f.logical(pname)
        w = StreamWalker(logical, inflate=True, keep_data=True)
        if w.errors:
            raise RuntimeError(f"walker errors on source: {w.errors[:3]}")
        blocks = sorted(w.blocks, key=lambda b: b.hdr_offset)
        u0_last: Dict[int, object] = {}
        for b in blocks:
            if b.unit == 0:
                u0_last[b.seq] = b
        overrides: Dict[int, Tuple[bytes, int]] = {}
        added_bytes: Dict[int, int] = {}
        for seq in (101, 102, 103):
            b = u0_last[seq]
            payload = b.data
            sl = _hdr_len(seq) + 4
            ins = len(payload) - sl
            if seq == 101:
                eidv, ps = struct.unpack_from("<qI", payload, ins)
            else:
                eidv, _st, ps = struct.unpack_from("<qII", payload, ins)
            if not (eidv == -1 and ps == 0):
                raise ValueError(f"seq {seq}: last unit-0 block does not end with a sentinel")
            extra = b"".join(recs[seq] for recs in records if seq in recs)
            overrides[b.index] = (payload[:ins] + extra + payload[ins:], len(records))
            added_bytes[seq] = len(extra)
        out = bytearray()
        cursor = 0
        for b in blocks:
            payload = b.data
            add_recs = 0
            if b.index in overrides:
                payload, add_recs = overrides[b.index]
            out += logical[cursor:b.member_offset]
            hdr = len(out) - (b.member_offset - b.hdr_offset)
            gz = gzip_member(payload, level=3, sync_flush=True)
            nb = 8 + len(gz)
            struct.pack_into("<I", out, hdr + 10, nb)
            if add_recs:
                a_new = b.n_records + add_recs
                adj = _ISIZE_ADJ.get(b.flags, 0)
                c_new = len(payload) - _c_hdr_len(b.seq) * a_new - adj
                struct.pack_into("<I", out, hdr + 6, a_new)
                struct.pack_into("<I", out, hdr + 14, c_new)
            out += gz
            out += struct.pack("<HI", BLOCK_TRL_TAG, nb)
            cursor = b.member_offset + b.member_len + 6
        out += logical[cursor:]
        struct.pack_into("<I", out, PART_HDR_COUNT_OFF, count_after)
        w2 = StreamWalker(bytes(out), inflate=False, keep_data=False)
        if w2.errors:
            raise RuntimeError(f"walker errors after splice: {w2.errors[:3]}")
        part_logical = bytes(out[:w2.end_offset + len(w2.end_record)])
        new_streams[pname] = ecc.frame_stream(part_logical)
    # -- identity (the writer owns BasicFileInfo) --------------------------------
    # This is a MINIMAL commit (no new History episode is recorded), so the
    # document GUID that pairs with History[0] must stay coherent: scrub the
    # provenance strings but KEEP the existing document GUID (a fresh GUID
    # belongs to a full record_save() that also prepends the History episode).
    try:
        from ..identity import own_basic_file_info
        from ..stream_encoders import decode_basic_file_info
        bfi = next((e for e in entries
                    if e.entry_type == "stream" and e.path == "BasicFileInfo"), None)
        if bfi is not None:
            cur = decode_basic_file_info(bfi.data).get("unique_document_guid")
            new_streams["BasicFileInfo"] = own_basic_file_info(
                bfi.data, out_path=out_path, document_guid=cur)
    except Exception as exc:                       # pragma: no cover
        import warnings
        warnings.warn(f"identity scrub skipped: {exc}")
    out_entries = [dataclasses.replace(e, data=new_streams[e.path])
                   if (e.entry_type == "stream" and e.path in new_streams) else e
                   for e in entries]
    write_cfb(out_path, out_entries)
    report = {"partition": pname, "new_element_ids": [e.elem_id for e in elements],
              "elemtable_count_before": count_before,
              "elemtable_count_after": count_after,
              "watermark_after": watermark_after,
              "per_seq_bytes_added": added_bytes, "out_path": out_path}
    if verify:
        from ..commit import verify_written
        report["verify_written"] = verify_written(out_path, [e.elem_id for e in elements])
    return report


# ===========================================================================
# integrity check of a planned run (before writing)
# ===========================================================================
def verify_plan_graph(doc: Document, plan: ConduitPlan) -> dict:
    """Prove the planned run's connector graph is MUTUAL and referentially
    closed: every conduit end's fitting reference is reciprocated by that
    fitting's connector, run membership is consistent, centre-lines point at
    their owners, and ``Document.check_references`` finds no dangling id."""
    by_id = {e.elem_id: e for e in plan.all()}
    issues: List[str] = []
    dangling = {}
    for e in plan.all():
        bad = doc.check_references(e)
        if bad:
            dangling[e.elem_id] = bad
    # connector reciprocity
    def refs_of(el: NewElement) -> Dict[int, List[dict]]:
        out: Dict[int, List[dict]] = {}
        mgr = _dig(el.obj, "m_pConnectorManager") or {}
        for cv in _connector_dicts(mgr):
            out[cv.get("m_nIndex")] = [r for r in (cv.get("m_arrRefs") or [])
                                        if isinstance(r, dict)]
        return out
    graph = {e.elem_id: refs_of(e) for e in plan.all()
             if e.class_name in ("RbsConduitCurve", "CableTray", "FamilyInstance")}
    for eid, conns in graph.items():
        for idx, refs in conns.items():
            for r in refs:
                tgt, tidx = r.get("m_id"), r.get("m_nIndex")
                if tgt == eid:
                    continue                      # self opposite-end link
                if tgt not in graph:
                    if tgt in by_id or (isinstance(tgt, int) and tgt > 0 and doc.exists(tgt)):
                        continue                  # external / other planned element
                    issues.append(f"{eid}.conn{idx} -> unknown {tgt}")
                    continue
                back = graph[tgt].get(tidx) or []
                if not any(x.get("m_id") == eid and x.get("m_nIndex") == idx for x in back):
                    issues.append(f"{eid}.conn{idx} -> {tgt}.conn{tidx} not reciprocated")
    # run membership / ownership
    if plan.run is not None:
        members = plan.run.obj.get("m_elemIdArr") or []
        for m in members:
            el = by_id.get(m)
            if el is None:
                issues.append(f"run member {m} is not part of the plan")
            elif el.class_name in ("RbsConduitCurve", "CableTray") \
                    and el.obj.get("m_runId") != plan.run.elem_id:
                issues.append(f"curve {m} m_runId {el.obj.get('m_runId')} != run {plan.run.elem_id}")
    for cl in plan.centerlines:
        own = cl.obj.get("m_OwnerId")
        if own not in by_id:
            issues.append(f"centre-line {cl.elem_id} owner {own} not in plan")
    return {"dangling_references": dangling, "graph_issues": issues,
            "ok": not dangling and not issues}


# ===========================================================================
# MODIFY (existing elements) — plans for rvt.manipulate.commit_plans
# ===========================================================================
def _M():
    from .. import manipulate as _m
    return _m


def _members_of(doc: Document, run_or_curve_id: int) -> Tuple[Optional[int], List[int]]:
    """(run_id, ordered member ids) for a run id or any member of a run."""
    cls = doc.class_of(run_or_curve_id)
    if cls in ("ConduitRun", "CableTrayRun"):
        rid = run_or_curve_id
    else:
        v = doc.value(run_or_curve_id) or {}
        rid = v.get("m_runId", INVALID_ID)
        if rid in (None, INVALID_ID):
            return None, [run_or_curve_id]
    rv = doc.value(rid) or {}
    return rid, list(rv.get("m_elemIdArr") or [])


def resize_run(doc: Document, run_or_curve_id: int, new_nominal_ft: float, *,
               height_ft: Optional[float] = None) -> list:
    """CHANGE SIZE of every curve in the run (or of one loose curve).

    Rewrites ``m_dWidthOrDiameter`` (+ ``m_dHeight``) and the design-property
    manager's inner/outer diameter + calculated-size label from the type's
    size table.  Fittings in the run keep their compiled clone (Revit
    re-solves them on regeneration; a size the fitting family cannot flex to
    raises a warning in Revit — semantic caveat).  Returns ModifyPlans.
    """
    M = _M()
    rid, members = _members_of(doc, run_or_curve_id)
    plans = []
    for mid in members:
        cls = doc.class_of(mid)
        if cls not in ("RbsConduitCurve", "CableTray"):
            continue
        v = doc.value(mid) or {}
        changes: Dict[str, Any] = {"m_dWidthOrDiameter": float(new_nominal_ft)}
        if cls == "RbsConduitCurve":
            changes["m_dHeight"] = float(new_nominal_ft)
            try:
                row = size_row(doc, v.get("m_idType"), new_nominal_ft)
                changes["m_pDesignPropManager.value.m_dInnerDiameter"] = row["inner_ft"]
                changes["m_pDesignPropManager.value.m_dOuterDiameter"] = row["outer_ft"]
            except LookupError:
                pass
            changes["m_pDesignPropManager.value.m_sCalculatedSize"] = _mm_label(new_nominal_ft)
        else:
            changes["m_dHeight"] = float(height_ft if height_ft is not None
                                         else v.get("m_dHeight") or new_nominal_ft)
            changes["m_calculatedSize"] = (
                f"{int(round(new_nominal_ft * _FT_TO_MM))} mmx"
                f"{int(round((height_ft or v.get('m_dHeight') or new_nominal_ft) * _FT_TO_MM))} mm")
        plans.append(M.modify_element(doc, mid, changes, kind="resize",
                                      reason=f"resize {mid} -> {new_nominal_ft * 12:.3f}in"))
        # header bbox: re-inflate around the axis by the new outer radius
        g = curve_geometry(doc, mid)
        if g:
            outer = changes.get("m_pDesignPropManager.value.m_dOuterDiameter") or new_nominal_ft
            bb = _bbox([g["p0"], g["p1"]], inflate=float(outer) / 2.0)
            plans.append(M.modify_element(doc, mid, {"m_pBBox.value.m_minmax": bb},
                                          seq=101, kind="resize", reason="resize: header bbox"))
    return plans


def move_run(doc: Document, run_or_curve_id: int, delta_ft: Sequence[float]) -> list:
    """RIGIDLY TRANSLATE a whole run (all curves, their fittings and every
    companion centre-line) by ``delta_ft``.  Curve: GLine origin, both
    level offsets (if dz), header bbox; centre-line: curves + rep + bbox;
    fitting: ``rvt.manipulate.move_instance`` (Trf.or, instOrigin, rep,
    bbox).  Returns the ModifyPlans."""
    M = _M()
    dv = _v(delta_ft)
    rid, members = _members_of(doc, run_or_curve_id)
    plans = []
    cl_ids = []
    for mid in members:
        cls = doc.class_of(mid)
        if cls in ("RbsConduitCurve", "CableTray"):
            v = doc.value(mid) or {}
            crv = _dig(v, "m_pCurveDriver", "m_pCrv") or {}
            org = list(crv.get("m_origin") or [0.0, 0.0, 0.0])
            changes = {"m_pCurveDriver.value.m_pCrv.value.m_origin": _add(org, dv)}
            if abs(dv[2]) > 0:
                changes["m_dOffsetStart"] = float(v.get("m_dOffsetStart") or 0.0) + dv[2]
                changes["m_dOffsetEnd"] = float(v.get("m_dOffsetEnd") or 0.0) + dv[2]
            plans.append(M.modify_element(doc, mid, changes, kind="move",
                                          reason=f"move run {rid or mid} by {dv}"))
            plans.append(_move_header_bbox(doc, mid, dv, M))
            g = curve_geometry(doc, mid)
            if g and g.get("centerline_id") and g["centerline_id"] > 0:
                cl_ids.append(g["centerline_id"])
        elif cls == "FamilyInstance":
            plans.append(M.move_instance(doc, mid, dv, None, delta=True, include_owned=False))
            fg = fitting_geometry(doc, mid)
            if fg and fg.get("centerline_id") and fg["centerline_id"] > 0:
                cl_ids.append(fg["centerline_id"])
    for cl in cl_ids:
        plans.extend(_move_centerline(doc, cl, dv, M))
    return [p for p in plans if p is not None]


def set_run_elevation(doc: Document, run_or_curve_id: int, delta_z_ft: float) -> list:
    """Raise/lower a run by ``delta_z_ft`` (a MOVE with dz only)."""
    return move_run(doc, run_or_curve_id, [0.0, 0.0, float(delta_z_ft)])


def _move_header_bbox(doc: Document, eid: int, dv, M):
    h = doc.value(eid, 101) or {}
    mm = _dig(h, "m_pBBox") or {}
    box = mm.get("m_minmax") if isinstance(mm, dict) else None
    if not isinstance(box, list):
        return None
    nb = [[box[0][i] + dv[i] for i in range(3)], [box[1][i] + dv[i] for i in range(3)]]
    return M.modify_element(doc, eid, {"m_pBBox.value.m_minmax": nb}, seq=101,
                            kind="move", reason="move: header bbox")


def _shift_curve(cv: dict, dv) -> None:
    """Translate a GLine/GArc value dict in place."""
    val = cv.get("value") if isinstance(cv, dict) else None
    if not isinstance(val, dict):
        return
    if "m_origin" in val and isinstance(val["m_origin"], list):
        val["m_origin"] = _add(val["m_origin"], dv)
    if "m_center" in val and isinstance(val["m_center"], list):
        val["m_center"] = _add(val["m_center"], dv)


def _move_centerline(doc: Document, cl_id: int, dv, M) -> list:
    """Translate a centre-line element's curves, cached rep GPoints and boxes."""
    plans = []
    v = doc.value(cl_id) or {}
    curves = copy.deepcopy(v.get("m_CenterCurves") or [])
    for c in curves:
        _shift_curve(c, dv)
    if curves:
        plans.append(M.modify_element(doc, cl_id, {"m_CenterCurves": curves},
                                      kind="move", reason="move: centre-line curves"))
    plans.append(_move_header_bbox(doc, cl_id, dv, M))
    # rep: two GPoints + boxes (only when it decodes cleanly)
    r = doc.decode(cl_id, 103)
    if r is not None and r.class_id == CLASS_GELEMENT and r.clean:
        sess = M.session(doc)
        rep = sess.value(cl_id, 103)
        for k in ("m_bBox", "m_tightbBox"):
            box = rep.get(k)
            if isinstance(box, list) and len(box) == 2:
                rep[k] = [[box[0][i] + dv[i] for i in range(3)],
                          [box[1][i] + dv[i] for i in range(3)]]
        for sn in rep.get("m_subNodes") or []:
            for p in ((sn.get("value") or {}).get("m_subNodes") or []):
                pv = p.get("value") or {}
                if p.get("ptr_class") == "GPoint" and isinstance(pv.get("m_coord"), list):
                    pv["m_coord"] = _add(pv["m_coord"], dv)
        pl = M.ModifyPlan(kind="move", elem_id=cl_id, class_name=doc.class_of(cl_id, 103))
        pl.record_edits.append(sess.replacement(cl_id, 103, "move: centre-line rep"))
        M.session(doc).plans.append(pl)
        plans.append(pl)
    return [p for p in plans if p is not None]


def extend_run(doc: Document, curve_id: int, delta_ft: float, *,
               end: str = "p1") -> list:
    """LENGTHEN (or shorten, negative delta) a curve at one END along its
    axis.  Only an OPEN end may move (a jointed end would break the fitting
    geometry, so it is refused).  Rewrites the GLine params, the moved end's
    level offset, the header bbox and the owned centre-line."""
    M = _M()
    if end not in ("p0", "p1"):
        raise ValueError("end must be 'p0' or 'p1'")
    g = curve_geometry(doc, curve_id)
    if g is None:
        raise M.ManipulationError(f"{curve_id} is not a conduit/cable-tray curve")
    idx = 0 if end == "p0" else 1
    for c in g["connectors"]:
        if c["index"] == idx:
            external = [r for r in c["refs"] if r.get("m_id") != curve_id]
            if external:
                raise M.ManipulationError(
                    f"curve {curve_id} end {end} is connected to "
                    f"{[r.get('m_id') for r in external]} — only an open end may be "
                    f"extended (extend the run through the fitting instead)")
    v = doc.value(curve_id) or {}
    lz = _level_z(doc, v.get("m_assocLevelId")) if v.get("m_assocLevelId") not in (
        None, INVALID_ID) else 0.0
    d = _unit(g["dir"])
    p0, p1 = list(g["p0"]), list(g["p1"])
    if end == "p1":
        p1 = _add(p1, _mul(d, float(delta_ft)))
    else:
        p0 = _sub(p0, _mul(d, float(delta_ft)))
    newlen = _norm(_sub(p1, p0))
    if newlen <= 1e-6:
        raise ValueError("extend would collapse the curve to zero length")
    changes = {
        "m_pCurveDriver.value.m_pCrv.value.m_origin": p0,
        "m_pCurveDriver.value.m_pCrv.value.m_dirVec": _unit(_sub(p1, p0)),
        "m_pCurveDriver.value.m_pCrv.value.m_endParams": [0.0, newlen],
        "m_dOffsetStart": p0[2] - lz, "m_dOffsetEnd": p1[2] - lz,
    }
    plans = [M.modify_element(doc, curve_id, changes, kind="extend",
                              reason=f"extend {curve_id} {end} by {delta_ft} ft")]
    dp = _dig(v, "m_pDesignPropManager")
    outer = dp.get("m_dOuterDiameter") if isinstance(dp, dict) else None
    half = float(outer if outer else (v.get("m_dWidthOrDiameter") or 0.0)) / 2.0
    bb = _bbox([p0, p1], inflate=half)
    plans.append(M.modify_element(doc, curve_id, {"m_pBBox.value.m_minmax": bb}, seq=101,
                                  kind="extend", reason="extend: header bbox"))
    cl = g.get("centerline_id")
    if cl and cl > 0 and doc.exists(cl):
        plans.append(M.modify_element(doc, cl, {"m_CenterCurves": [_gline(p0, p1)]},
                                      kind="extend", reason="extend: centre-line"))
        plans.append(M.modify_element(doc, cl, {"m_pBBox.value.m_minmax": bb}, seq=101,
                                      kind="extend", reason="extend: centre-line bbox"))
        # rep GPoints -> new bbox corners
        r = doc.decode(cl, 103)
        if r is not None and r.class_id == CLASS_GELEMENT and r.clean:
            sess = M.session(doc)
            rep = sess.value(cl, 103)
            rep["m_bBox"] = copy.deepcopy(bb)
            rep["m_tightbBox"] = copy.deepcopy(bb)
            pts = [bb[1], bb[0]]
            k = 0
            for sn in rep.get("m_subNodes") or []:
                for p in ((sn.get("value") or {}).get("m_subNodes") or []):
                    pv = p.get("value") or {}
                    if p.get("ptr_class") == "GPoint" and k < 2:
                        pv["m_coord"] = list(pts[k])
                        k += 1
            pl = M.ModifyPlan(kind="extend", elem_id=cl, class_name=doc.class_of(cl, 103))
            pl.record_edits.append(sess.replacement(cl, 103, "extend: centre-line rep"))
            M.session(doc).plans.append(pl)
            plans.append(pl)
    return plans


def retype_run(doc: Document, run_or_curve_id: int, new_type_id: int) -> list:
    """CHANGE the conduit / cable-tray TYPE of every curve in the run and of
    the run element itself (``m_idType``, ``ConduitRun.m_typeId``, the
    header dependency lists old-type -> new-type).  The new type must be the
    same domain (RbsConduitType for conduits, RbsCableTrayType for trays)."""
    M = _M()
    if not doc.exists(new_type_id):
        raise M.ManipulationError(f"type {new_type_id} not in {doc.project}")
    new_cls = doc.class_of(new_type_id)
    rid, members = _members_of(doc, run_or_curve_id)
    plans = []
    for mid in members:
        cls = doc.class_of(mid)
        want = {"RbsConduitCurve": "RbsConduitType", "CableTray": "RbsCableTrayType"}.get(cls)
        if want is None:
            continue
        if new_cls != want:
            raise M.ManipulationError(f"{mid} ({cls}) needs a {want}, got {new_cls}")
        v = doc.value(mid) or {}
        old = v.get("m_idType")
        changes: Dict[str, Any] = {"m_idType": new_type_id}
        if cls == "RbsConduitCurve":
            try:
                row = size_row(doc, new_type_id, float(v.get("m_dWidthOrDiameter")))
                changes["m_pDesignPropManager.value.m_dInnerDiameter"] = row["inner_ft"]
                changes["m_pDesignPropManager.value.m_dOuterDiameter"] = row["outer_ft"]
            except LookupError:
                pass
        plans.append(M.modify_element(doc, mid, changes, kind="retype",
                                      reason=f"retype {mid}: {old} -> {new_type_id}"))
        # header: swap the type id in the dependency lists
        h = copy.deepcopy(doc.value(mid, 101)) or {}
        par = _dig(h, "m_parents") or {}
        touched = False
        for lst in ("m_deletion", "m_appearanceParents"):
            ids = par.get(lst)
            if isinstance(ids, list) and old in ids:
                par[lst] = sorted({(new_type_id if x == old else x) for x in ids})
                touched = True
        if touched:
            plans.append(M.modify_element(doc, mid, {"m_parents.value": par}, seq=101,
                                          kind="retype", reason="retype: header parents"))
    if rid not in (None, INVALID_ID):
        rv = doc.value(rid) or {}
        old = rv.get("m_typeId")
        plans.append(M.modify_element(doc, rid, {"m_typeId": new_type_id}, kind="retype",
                                      reason=f"run {rid} type {old} -> {new_type_id}"))
        h = copy.deepcopy(doc.value(rid, 101)) or {}
        par = _dig(h, "m_parents") or {}
        ids = par.get("m_deletion")
        if isinstance(ids, list) and old in ids:
            par["m_deletion"] = sorted({(new_type_id if x == old else x) for x in ids})
            plans.append(M.modify_element(doc, rid, {"m_parents.value": par}, seq=101,
                                          kind="retype", reason="retype: run header parents"))
    return plans


# ===========================================================================
# DELETE (existing elements) — plans for rvt.manipulate.commit_plans
# ===========================================================================
def run_closure(doc: Document, run_id: int) -> List[int]:
    """Every element a run delete must remove: the run, all its members
    (curves + fittings) and each member's owned companions (centre-lines,
    the run itself is owned by its first curve)."""
    M = _M()
    rid, members = _members_of(doc, run_id)
    ids = set()
    if rid not in (None, INVALID_ID):
        ids.add(rid)
    ids.update(members)
    # owned children (SegmentCenterLine / ConduitFittingCenterLine via
    # ElemTable ownership) + the centre-line ids named by the objects
    ids.update(M.owned_children(doc, list(ids)))
    for mid in list(members):
        g = curve_geometry(doc, mid) or fitting_geometry(doc, mid) or {}
        cl = g.get("centerline_id") if isinstance(g, dict) else None
        if cl and cl > 0 and doc.in_host_document(cl):
            ids.add(cl)
    return sorted(i for i in ids if isinstance(i, int) and i > 0
                  and doc.in_host_document(i))


def delete_run(doc: Document, run_id: int) -> list:
    """DELETE a whole conduit / cable-tray RUN: the run, its curves, its
    fittings and every companion centre-line, neutralising every remaining
    reference (equipment surface connectors that pointed at a deleted curve,
    neighbouring runs, the MEP system tracker).  Returns DeletePlans (one
    per element, referrer edits merged by ``commit_plans``); pass them to
    ``rvt.manipulate.commit_plans``."""
    M = _M()
    closure = run_closure(doc, run_id)
    if not closure:
        raise M.ManipulationError(f"{run_id}: nothing to delete")
    plans = []
    done = set()
    for eid in closure:
        if eid in done:
            continue
        try:
            pl = M.delete_element(doc, eid, cascade=True)
        except M.DependentsError:                       # pragma: no cover
            pl = M.delete_element(doc, eid, cascade=True)
        plans.append(pl)
        done.update(pl.ids_to_remove)
    return plans


def delete_conduit(doc: Document, curve_id: int) -> list:
    """DELETE one curve + its owned centre-line (and its run when the curve
    OWNS the run); the run's member list, its fittings' connector references
    and any equipment connector are neutralised.  For removing a whole run
    prefer :func:`delete_run`."""
    M = _M()
    return [M.delete_element(doc, curve_id, cascade=True)]


def delete_fitting(doc: Document, fitting_id: int) -> list:
    """DELETE one fitting (elbow): the FamilyInstance + its owned fitting
    centre-line; the two conduits' connector references and the run's
    member list are neutralised (leaving two open ends in one run)."""
    M = _M()
    return [M.delete_element(doc, fitting_id, cascade=True)]


# ===========================================================================
# read-back helpers (semantic verification of a written file)
# ===========================================================================
def readback_run(path_or_doc, run_id: int) -> dict:
    """Re-open a written file (or use a Document) and prove a run's graph:
    member order, per-curve length/size/level, connector reciprocity,
    centre-line ownership.  Used by the proof harness and tests."""
    doc = path_or_doc if isinstance(path_or_doc, Document) else Document.from_file(path_or_doc)
    rv = doc.value(run_id)
    if not isinstance(rv, dict):
        return {"run": run_id, "exists": False}
    out = {"run": run_id, "exists": True, "class": doc.class_of(run_id),
           "type_id": rv.get("m_typeId"), "members": [], "issues": []}
    members = list(rv.get("m_elemIdArr") or [])
    graph: Dict[int, Dict[int, List[dict]]] = {}
    for mid in members:
        cls = doc.class_of(mid)
        row = {"id": mid, "class": cls}
        if cls in ("RbsConduitCurve", "CableTray"):
            g = curve_geometry(doc, mid) or {}
            row.update({"length_ft": g.get("length_ft"),
                        "size_ft": g.get("diameter_or_width_ft"),
                        "run_id": g.get("run_id"),
                        "centerline_id": g.get("centerline_id"),
                        "p0": g.get("p0"), "p1": g.get("p1")})
            graph[mid] = {c["index"]: c["refs"] for c in g.get("connectors") or []}
            if g.get("run_id") != run_id:
                out["issues"].append(f"curve {mid} m_runId {g.get('run_id')} != {run_id}")
            cl = g.get("centerline_id")
            if cl and cl > 0:
                clv = doc.value(cl) or {}
                if clv.get("m_OwnerId") != mid:
                    out["issues"].append(f"centre-line {cl} owner "
                                         f"{clv.get('m_OwnerId')} != {mid}")
        elif cls == "FamilyInstance":
            fg = fitting_geometry(doc, mid) or {}
            row.update({"corner": fg.get("corner"), "clone": fg.get("symbol_clone_id"),
                        "master": fg.get("master_symbol_id"),
                        "centerline_id": fg.get("centerline_id")})
            graph[mid] = fg.get("connectors") or {}
        out["members"].append(row)
    # reciprocity
    for eid, conns in graph.items():
        for idx, refs in (conns or {}).items():
            for r in refs or []:
                tgt, tidx = r.get("m_id"), r.get("m_nIndex")
                if tgt == eid or tgt not in graph:
                    continue
                back = graph[tgt].get(tidx) or []
                if not any(x.get("m_id") == eid and x.get("m_nIndex") == idx for x in back):
                    out["issues"].append(f"{eid}.conn{idx} -> {tgt}.conn{tidx} not mutual")
    out["ok"] = not out["issues"]
    return out


# ===========================================================================
# CLI
# ===========================================================================
def main(argv=None):
    import json
    argv = list(sys.argv[1:] if argv is None else argv)
    path = argv[0] if argv else "samples/rmebasicsampleproject.rvt"
    doc = Document.from_file(path) if path.endswith(".rvt") else Document.load(path)
    inv = inventory_runs(doc)
    print(f"# {doc.project}: {inv['totals']}")
    for r in inv["conduit_runs"] + inv["cable_tray_runs"]:
        print(f"\n{r['class']} {r['run_id']}  type {r['type_id']} "
              f"({r['type_name']})  {r['n_curves']} curve(s) {r['n_fittings']} "
              f"fitting(s)  L={r['total_length_ft']:.2f} ft  open ends {len(r['open_ends'])}")
        for m in r["members"]:
            if m["kind"] == "curve":
                print(f"    {m['id']} {m['class']:16s} L={m['length_ft']:.3f} "
                      f"size {m['size_ft'] * 12:.2f}in  {_r3(m['p0'])} -> {_r3(m['p1'])}")
            else:
                print(f"    {m['id']} {m['class']:16s} ({m['kind']})"
                      + (f" corner {_r3(m['corner'])}" if m.get("corner") else ""))
    print("\n# conduit types:", json.dumps(conduit_types(doc), indent=1))
    print("# cable tray types:", json.dumps(cable_tray_types(doc), indent=1))
    print("# elbow specimen configurations:",
          json.dumps([{k: e[k] for k in ("elbow_id", "master_symbol_id",
                                           "symbol_clone_id", "nominal_ft", "angle_rad")}
                      for e in elbow_specimens(doc) if not e["shared_clone"]], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""rvt.famgen.famdim -- THE DRIVER TABLES: registering a labelled dimension as
the thing a family parameter actually DRIVES.

WHY THIS MODULE EXISTS.  ``param_drive`` (#372) authors everything a flexing
family appears to need: four side reference planes, alignments binding the
solid's sketch to them, and a LABELLED ``LinearDimString`` whose segment carries
``m_paramId`` = the family parameter.  It validates 0 errors.  On the owner's
Revit 2026 it **"did not work what so ever"** -- the family opened, the
parameter was there, changing it moved nothing.

The reason is not a donor and not the dimension.  It is that the table which
says *this parameter drives that dimension segment* is EMPTY.  Every family this
engine writes carries::

    mgr = blank_object("FamDimConstrMgrImpl")      # skeleton.py, new_self_family
    o["m_oFamDimConstrMgr"] = _ptr(...)            # every table []

and ``genesis/residue_c`` even names it "the corpus-lawful EMPTY
``Family.m_oFamDimConstrMgr``".  ``skeleton``'s own note says the quiet part --
*"formulas live in the FamDimConstrMgrImpl expression tables which this skeleton
leaves empty"* -- written about formulas, but it is the flex as well.

THE MODEL, READ OFF THE SCHEMA (no donor, no guess about STRUCTURE)::

    FamDimConstrMgrImpl
      m_paramExprs      pair<ElementIdIntPair, ParamExpr>
      m_drivenDimSegs   pair<ElementIdIntPair, DimValueExprOwner>   <- the flex
      m_fixedRefs       pair<ElementIdIntPair, GrefAndDir>
      m_dimSegDataMap   map -> DimSegData
      ...

    ParamExpr          m_entries:[ParamExprEntry], m_elemId, m_msgId
    ParamExprEntry     m_coef, m_paramId
    DimValueExprOwner  m_oDimValueExpr
    DimValueExpr       m_entries:[DimValueExprEntry], m_offset
    DimValueExprEntry  m_coeff, m_dimId, m_seg, m_mayBeDriven
    ElementIdIntPair   m_elementId, m_int64

It is a linear-expression system: a value is a sum of ``coefficient x term``
plus an offset.  A 1:1 drive is one entry at coefficient 1.0 and offset 0.

WHICH TABLE IS THE DRIVE -- SETTLED BY READING THE SCHEMA.  The first cut of
this module enumerated table combinations, because the field NAMES look
ambiguous.  Their TYPES are not, and every file carries its own class schema,
so this needed no specimen and no donor:

* ``m_paramExprs`` maps a (dimension, segment) key to a ``ParamExpr`` -- a
  linear expression IN PARAMETERS, owned by the element ``m_elemId`` names.
  "this segment's value = 1.0 x Width".  **This is the parameter drive.**
* ``m_drivenDimSegs`` maps a segment to an expression in OTHER DIMENSION
  SEGMENTS (``m_dimId``, ``m_seg``).  That is dimension-to-dimension equality,
  not parameter drive -- so the first cut's opening rung was aimed at the
  wrong table, and its ``m_paramExprs`` rung keyed the table BY THE PARAMETER,
  which had the relation backwards.  Both are corrected.
* ``m_dimSegDataMap`` maps the same key to ``DimSegData`` -- the ``GeomRef``s
  the segment spans and their coefficients.  An expression without it gives
  the solver a number but nothing to move.

WHAT REMAINS A LADDER.  The reasoning above fixes WHICH tables and HOW they are
keyed.  It does not prove Revit's solver is satisfied by the minimum, so the
rungs now vary only how much is declared -- P1 (binding alone), P2 (+ the
geometry span), P3 (+ an anchor), P4 (+ registration in the driven table) --
against the P0 control that must NOT flex.  **Nothing here claims a family
flexes.**  Until a desktop verdict says a rung works, this module is opt-in and
every surface stays silent about editability (hard rule 4).

Territory: famgen (new module; builds the manager dict, edits no writer path).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = ["RUNGS", "DEFAULT_RUNG", "labelled_dims", "driver_tables",
           "apply_to_doc", "describe_rung"]


# ---------------------------------------------------------------------------
# the ladder: each rung adds exactly ONE of the four unknowns
# ---------------------------------------------------------------------------

#: rung -> (what it adds over the previous rung, what a PASS would prove)
#: WHICH TABLE IS THE DRIVE -- settled by READING THE SCHEMA, not by guessing.
#:
#: The first version of this ladder enumerated table combinations because the
#: field names alone looked ambiguous.  They are not, once the TYPES are read
#: (every file carries its own class schema, so this needs no specimen):
#:
#:   m_paramExprs    pair<ElementIdIntPair, ParamExpr>
#:                   ParamExpr{ m_entries:[ParamExprEntry{m_coef, m_paramId}],
#:                              m_elemId, m_msgId }
#:       -> a linear expression IN PARAMETERS, belonging to the element named
#:          by m_elemId.  "this segment's value = 1.0 x Width".  THIS IS THE
#:          PARAMETER DRIVE.
#:
#:   m_drivenDimSegs pair<ElementIdIntPair, DimValueExprOwner>
#:                   DimValueExpr{ m_entries:[DimValueExprEntry{m_coeff,
#:                                 m_dimId, m_seg, m_mayBeDriven}], m_offset }
#:       -> a linear expression IN OTHER DIMENSION SEGMENTS.  That is
#:          dimension-to-dimension equality (Revit's EQ constraints, one dim
#:          following another).  It is NOT how a parameter drives geometry.
#:
#:   m_dimSegDataMap pair<ElementIdIntPair, DimSegData>
#:                   DimSegData{ m_dimDir, m_groupId, m_grefArr:[GeomRef],
#:                               m_coefArr:[double] }
#:       -> WHICH GEOMETRY the segment spans, and with what signs.  An
#:          expression with no segment data tells the solver a number but not
#:          what to move.
#:
#: So the earlier D1 ("m_drivenDimSegs alone") was aimed at the wrong table,
#: and the earlier D2 keyed m_paramExprs BY THE PARAMETER -- backwards: the
#: key is the thing whose value is computed (the dim segment), the parameter
#: appears inside the expression.  Both are corrected here.
#:
#: The remaining ladder is small, and each rung is a real hypothesis rather
#: than an arm of an enumeration.
RUNGS: Dict[str, Tuple[str, str]] = {
    "P0": ("nothing -- the manager stays EMPTY, exactly as every family this "
           "engine has ever written",
           "the CONTROL. It must NOT flex. If P0 flexes, the whole premise is "
           "wrong and the failure was somewhere else entirely."),
    "P1": ("m_paramExprs only: each labelled segment keyed to a ParamExpr of "
           "one entry, coefficient 1.0 on its parameter, m_elemId = the "
           "dimension",
           "the solver-side parameter binding is the whole missing piece, and "
           "the segment's geometry is already known from the dimension's own "
           "witnesses"),
    "P2": ("P1 + m_dimSegDataMap: the same key mapped to the two witness "
           "GeomRefs with coefficients -1 / +1 along the dimension direction",
           "the solver ALSO needs the segment's geometry span declared in the "
           "manager, not only on the dimension"),
    "P3": ("P2 + m_fixedRefs: one side pinned, so the pair is not "
           "under-constrained and the solver knows which end moves",
           "the solver needs an anchor; without one a symmetric pair has no "
           "unique solution"),
    "P4": ("P3 + m_drivenDimSegs as a self-referential mirror, m_mayBeDriven "
           "True",
           "the segment must ALSO appear in the driven table to be considered "
           "at all -- i.e. that table is a registry, not only a dim-to-dim "
           "relation. Last rung because the schema says it is the wrong axis."),
}

#: The one unknown that is NOT in the ladder, because it cannot be authored
#: blind: ``Element.m_constrInfo`` is kind 14 / flags 81 -- an ARRAY whose
#: element type the schema does not name, and every element this engine writes
#: carries ``[]``.  Setting it to a scalar is refused by the encoder (that is
#: how this was found).  Revit's default ``.rft`` templates do NOT settle it:
#: all 108 carry ``m_constrInfo == []`` on every dimension, because a template
#: has no user geometry and so has recorded no constraints.
UNKNOWN_NEEDS_SPECIMEN = ("Element.m_constrInfo (array element type unnamed in "
                          "the schema; every element we author carries [], and "
                          "so does every default .rft template)",)

#: What ``apply_to_doc`` uses when a caller does not name a rung.
#:
#: P2 -- the reasoned candidate: the parameter binding plus the geometry span,
#: which is the smallest set that tells the solver both WHAT the value is and
#: WHAT MOVES.  This is a derivation from the schema, NOT a verdict: no rung
#: has been confirmed in Revit, and nothing may claim a family flexes until
#: one has (hard rule 4).  ``P0`` remains the control every probe pairs with.
DEFAULT_RUNG = "P2"

#: The rung ordering a probe batch should walk, most-likely first.
LADDER = ("P2", "P1", "P3", "P4", "P0")


def describe_rung(rung: str) -> Dict[str, str]:
    adds, proves = RUNGS[rung]
    return {"rung": rung, "adds": adds, "a PASS proves": proves}


# ---------------------------------------------------------------------------
# reading the document
# ---------------------------------------------------------------------------

def labelled_dims(doc: Any) -> List[Dict[str, Any]]:
    """Every LABELLED dimension in ``doc``: the ones whose segment carries a
    real ``m_paramId``.  Returns one row per (dimension, segment).

    An unlabelled dimension (``m_paramId`` -1) is a witness line, not a driver,
    and is deliberately not returned.
    """
    out: List[Dict[str, Any]] = []
    for el in getattr(doc, "elements", []):
        if el.class_name != "LinearDimString":
            continue
        for seg_i, seg in enumerate(el.obj.get("m_ArrSegInfo") or []):
            pid = int(seg.get("m_paramId", -1))
            if pid <= 0:
                continue
            out.append({"dim_id": int(el.elem_id), "seg": seg_i, "param_id": pid,
                        "value": float(seg.get("m_lockedValue") or 0.0),
                        "witness_refs": _witness_geom_refs(el),
                        "direction": _dim_direction(el),
                        "element": el})
    return out


def _witness_geom_refs(el: Any) -> List[Dict[str, Any]]:
    """The ``GeomRef``s a dimension measures between, in witness order.

    ``m_witnessRefs[i].m_pWitnessRef`` is a ``GeomSegInPlaneRef`` pointer whose
    ``m_geomRef`` names the referenced element (the side reference plane).
    A linear segment has exactly two; anything else is not authorable as a
    two-ended span and the caller skips it rather than inventing one.
    """
    refs: List[Dict[str, Any]] = []
    for w in el.obj.get("m_witnessRefs") or []:
        ptr = (w or {}).get("m_pWitnessRef") or {}
        val = ptr.get("value") if isinstance(ptr, dict) else None
        gref = (val or {}).get("m_geomRef") if isinstance(val, dict) else None
        if isinstance(gref, dict):
            refs.append(gref)
    return refs


def _dim_direction(el: Any) -> Tuple[float, float, float]:
    """The dimension's measuring direction, from its own dim line.

    ``m_pDimLine`` is a ``GLine`` carrying ``m_dirVec``.  Falls back to
    ``m_fixedDir`` and finally to +X -- both recorded rather than silently
    assumed, because a wrong direction puts the segment's sign the wrong way
    round.
    """
    line = el.obj.get("m_pDimLine") or {}
    val = line.get("value") if isinstance(line, dict) else None
    d = (val or {}).get("m_dirVec") if isinstance(val, dict) else None
    if not d:
        d = el.obj.get("m_fixedDir")
    if d and any(abs(float(c)) > 1e-12 for c in d):
        return (float(d[0]), float(d[1]), float(d[2]) if len(d) > 2 else 0.0)
    return (1.0, 0.0, 0.0)


def _geom_ref(gref: Dict[str, Any]) -> Dict[str, Any]:
    """A ``GeomRef`` copy for the manager's own tables.

    The witness carries the reference we want; copying it keeps the manager
    and the dimension naming the SAME geometry, which is the whole point of
    the segment-data table.
    """
    return {
        "m_intermediateTags": list(gref.get("m_intermediateTags") or []),
        "m_oNextRef": None,
        "m_elemId": int(gref.get("m_elemId", -1)),
        "m_ownerDBViewId": int(gref.get("m_ownerDBViewId", -1)),
        "m_foreignElemIdRef": dict(gref.get("m_foreignElemIdRef") or {"m_id64": -1}),
        "m_geomTag": int(gref.get("m_geomTag", 0)),
        "m_subTag": int(gref.get("m_subTag", -1)),
        "m_famMemberIdx": int(gref.get("m_famMemberIdx", -1)),
        "m_flags": int(gref.get("m_flags", 0)),
        "m_isLazyRef": bool(gref.get("m_isLazyRef", False)),
    }


def _pair(elem_id: int, i: int) -> Dict[str, Any]:
    return {"m_elementId": int(elem_id), "m_int64": int(i)}


def _dim_value_expr(dim_id: int, seg: int, *, coeff: float = 1.0,
                    offset: float = 0.0, may_be_driven: bool = True) -> Dict[str, Any]:
    # m_oDimValueExpr is a POINTER field (kind 14), not an inline struct -- the
    # encoder refuses a bare dict here, which is how this was caught
    return {"m_oDimValueExpr": {"ptr_class": "DimValueExpr", "pid": -1, "value": {
        "m_entries": [{"m_coeff": float(coeff), "m_dimId": int(dim_id),
                       "m_seg": int(seg), "m_mayBeDriven": bool(may_be_driven)}],
        "m_offset": float(offset)}}}


def _param_expr(param_id: int, *, elem_id: int,
                coef: float = 1.0) -> Dict[str, Any]:
    """One ParamExpr: the value = ``coef`` x the parameter.

    ``m_elemId`` is the element the expression BELONGS TO -- the dimension
    whose segment is being computed -- not the parameter.  The parameter
    appears only inside ``m_entries``.  (The first cut of this module set
    m_elemId to the parameter and keyed the table by it, which had the
    relation backwards.)
    """
    return {"m_entries": [{"m_coef": float(coef), "m_paramId": int(param_id)}],
            "m_elemId": int(elem_id), "m_msgId": 0}


def _gref_and_dir(ref_elem_id: int, direction: Sequence[float]) -> Dict[str, Any]:
    return {"m_gref": {"m_intermediateTags": [], "m_oNextRef": None,
                       "m_elemId": int(ref_elem_id), "m_ownerDBViewId": -1,
                       "m_foreignElemIdRef": {"m_id64": 0}, "m_geomTag": 0,
                       "m_subTag": 0, "m_famMemberIdx": 0, "m_flags": 0,
                       "m_isLazyRef": False},
            "m_dimDir": [float(x) for x in direction],
            "m_groupId": -1, "m_refFlip": 0}


# ---------------------------------------------------------------------------
# building the tables
# ---------------------------------------------------------------------------

def driver_tables(doc: Any, *, rung: str = DEFAULT_RUNG,
                  fixed_refs: Optional[Sequence[Tuple[int, Sequence[float]]]] = None
                  ) -> Dict[str, Any]:
    """The ``FamDimConstrMgrImpl`` body for ``doc`` at ladder rung ``rung``.

    ``fixed_refs`` = ``[(reference plane element id, direction), ...]`` for the
    P3 rung; when omitted P3 pins nothing and degrades to P2 (reported).
    """
    if rung not in RUNGS:
        raise ValueError(f"unknown rung {rung!r}; the ladder is {', '.join(RUNGS)}")
    from ..genesis.types import blank_object
    mgr = blank_object("FamDimConstrMgrImpl")
    dims = labelled_dims(doc)
    if rung == "P0" or not dims:
        return mgr

    # P1 -- THE PARAMETER DRIVE.  Key = the segment whose value is computed
    # ((dimension id, segment index)); value = an expression IN PARAMETERS
    # owned by that dimension.  Note the key is NOT the parameter: ParamExpr
    # is an expression *in* parameters, and m_elemId names whose value it is.
    mgr["m_paramExprs"] = [
        {"first": _pair(d["dim_id"], d["seg"]),
         "second": _param_expr(d["param_id"], elem_id=d["dim_id"])}
        for d in dims]
    if rung == "P1":
        return mgr

    # P2 -- WHAT THE SEGMENT SPANS.  The two witness references the dimension
    # measures between, with coefficients -1 / +1 so the segment's value is
    # (high side - low side) along the dimension direction.
    seg_data = []
    for d in dims:
        refs = list(d.get("witness_refs") or ())
        if len(refs) != 2:
            continue          # only a two-witness linear segment is authorable
        seg_data.append({
            "first": _pair(d["dim_id"], d["seg"]),
            "second": {
                "m_dimDir": [float(x) for x in d.get("direction") or (1.0, 0.0, 0.0)],
                "m_groupId": -1,
                "m_grefArr": [_geom_ref(r) for r in refs],
                "m_coefArr": [-1.0, 1.0],
            }})
    mgr["m_dimSegDataMap"] = seg_data
    if rung == "P2":
        return mgr

    # P3 -- pin one side so the pair is not under-constrained
    if fixed_refs:
        mgr["m_fixedRefs"] = [
            {"first": _pair(ref_id, 0), "second": _gref_and_dir(ref_id, direction)}
            for ref_id, direction in fixed_refs]
    if rung == "P3":
        return mgr

    # P4 -- ALSO register the segment in the driven table (self-referential:
    # the segment's value expressed as 1.0 x itself).  The schema says this
    # table relates dimensions to OTHER dimensions, so this rung tests only
    # whether it doubles as a registry of "segments the solver may drive".
    mgr["m_drivenDimSegs"] = [
        {"first": _pair(d["dim_id"], d["seg"]),
         "second": _dim_value_expr(d["dim_id"], d["seg"])}
        for d in dims]
    return mgr


def apply_to_doc(doc: Any, *, rung: str = DEFAULT_RUNG,
                 fixed_refs: Optional[Sequence[Tuple[int, Sequence[float]]]] = None
                 ) -> Dict[str, Any]:
    """Write the driver tables onto ``doc``'s self-Family and return a report.

    Call AFTER the labelled dimensions exist and BEFORE ``finalize`` (finalize
    rewrites other parts of the self-Family, not this one, but ordering keeps
    the intent obvious).  Never raises for a document with no labelled
    dimensions -- it simply reports that there was nothing to drive.
    """
    dims = labelled_dims(doc)
    mgr = driver_tables(doc, rung=rung, fixed_refs=fixed_refs)
    fam = doc.self_family
    fam.obj["m_oFamDimConstrMgr"] = {"ptr_class": "FamDimConstrMgrImpl",
                                     "pid": -1, "value": mgr}
    rep = {
        "rung": rung, **describe_rung(rung),
        "labelled_dims": [{k: v for k, v in d.items() if k != "element"} for d in dims],
        "driven_segs": len(mgr.get("m_drivenDimSegs") or []),
        "param_exprs": len(mgr.get("m_paramExprs") or []),
        "fixed_refs": len(mgr.get("m_fixedRefs") or []),
        "claim": ("NONE. The tables are authored; whether Revit SOLVES them is "
                  "what the desktop round decides. No surface may say this "
                  "family flexes until a rung has a verdict (hard rule 4)."),
    }
    if rung in ("P3", "P4") and not fixed_refs:
        rep["degraded"] = (f"{rung} asked for pinned references but none were "
                           f"given: this build is P2 plus whatever {rung} adds "
                           f"beyond the pin")
    doc.notes.append(f"param-drive probe rung {rung}: {rep['driven_segs']} driven "
                     f"segment(s), {rep['param_exprs']} param expr(s), "
                     f"{rep['fixed_refs']} fixed ref(s) -- NOT verified to flex")
    return rep

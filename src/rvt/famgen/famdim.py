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

WHAT IS STILL UNKNOWN, AND WHY THIS SHIPS AS A LADDER.  The STRUCTURE above is
schema fact.  The VALUES are not, and four of them decide whether Revit
actually solves:

1. which side of ``m_drivenDimSegs`` is the driver -- is the key the driven
   segment and the expression the parameter, or the reverse;
2. whether ``m_paramExprs`` must carry the mirror entry as well;
3. whether ``m_fixedRefs`` must pin the opposite reference so the solver has
   something to hold still (an unpinned pair is under-constrained);
4. whether the ``LinearDimString``'s own ``m_constrInfo`` must stop being 0.

Each is one variable, so each is one rung of a probe ladder with a control --
the method that named the Load Family crash (#589) and the rotated cylinder
(#591 R1-R4).  **Nothing here claims a family flexes.**  Until a desktop verdict
says a rung works, this module is opt-in and every surface stays silent about
editability (hard rule 4).

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
RUNGS: Dict[str, Tuple[str, str]] = {
    "D0": ("nothing -- the manager stays EMPTY, exactly as every family this "
           "engine has ever written",
           "the CONTROL. It must NOT flex. If D0 flexes, the whole premise is "
           "wrong and the failure was somewhere else entirely."),
    "D1": ("m_drivenDimSegs: the labelled dimension's segment 0 registered as "
           "driven, one DimValueExprEntry at coefficient 1.0, offset 0, "
           "m_mayBeDriven=True",
           "the driver table alone is the missing piece"),
    "D2": ("D1 + m_paramExprs: the mirror entry, parameter -> its own "
           "expression at coefficient 1.0",
           "the solver needs the relation registered from BOTH sides"),
    "D3": ("D2 + m_fixedRefs: the opposite reference plane pinned, so the pair "
           "is not under-constrained",
           "the solver needs something held still to solve against"),
    "D4": ("D3 with m_mayBeDriven FALSE on the DimValueExprEntry -- the one "
           "boolean in the expression whose meaning is not obvious from its name",
           "the flag's polarity: whether it marks a segment the solver MAY "
           "drive, or one it may NOT"),
}

#: A FIFTH unknown that is NOT in the ladder, because it is not authorable
#: blind: ``Element.m_constrInfo`` is declared kind 14 / flags 81 -- an ARRAY of
#: something the schema does not name a type for, and every element this engine
#: writes carries ``[]``.  Setting it to a scalar is refused by the encoder
#: (that is how this was found).  Its element shape has to be READ off a family
#: that has one -- a Revit family TEMPLATE (.rft) is the obvious specimen, and
#: the owner has offered to supply the default set.  Until then D0-D4 vary only
#: what can be authored honestly.
UNKNOWN_NEEDS_SPECIMEN = ("Element.m_constrInfo (array element type unnamed in "
                          "the schema; every element we author carries [])",)

#: what `apply_to_doc` uses when a caller does not name a rung.  D0 = today's
#: behaviour, because no rung has a desktop verdict yet.
DEFAULT_RUNG = "D0"


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
                        "element": el})
    return out


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


def _param_expr(param_id: int, *, coef: float = 1.0) -> Dict[str, Any]:
    return {"m_entries": [{"m_coef": float(coef), "m_paramId": int(param_id)}],
            "m_elemId": int(param_id), "m_msgId": 0}


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
    D3 rung; when omitted D3 pins nothing and degrades to D2 (reported).
    """
    if rung not in RUNGS:
        raise ValueError(f"unknown rung {rung!r}; the ladder is {', '.join(RUNGS)}")
    from ..genesis.types import blank_object
    mgr = blank_object("FamDimConstrMgrImpl")
    dims = labelled_dims(doc)
    if rung == "D0" or not dims:
        return mgr

    # D1: every labelled segment is a DRIVEN segment, 1:1
    mgr["m_drivenDimSegs"] = [
        {"first": _pair(d["dim_id"], d["seg"]),
         "second": _dim_value_expr(d["dim_id"], d["seg"])}
        for d in dims]
    if rung == "D1":
        return mgr

    # D2: the mirror -- the parameter's own expression
    mgr["m_paramExprs"] = [
        {"first": _pair(d["param_id"], 0), "second": _param_expr(d["param_id"])}
        for d in dims]
    if rung == "D2":
        return mgr

    # D3: pin the opposite reference so the pair is not under-constrained
    if fixed_refs:
        mgr["m_fixedRefs"] = [
            {"first": _pair(ref_id, 0), "second": _gref_and_dir(ref_id, direction)}
            for ref_id, direction in fixed_refs]
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
    if rung == "D4":
        # flip the one boolean whose polarity the name does not settle
        for row in mgr.get("m_drivenDimSegs") or []:
            expr = row["second"]["m_oDimValueExpr"]["value"]
            for entry in expr["m_entries"]:
                entry["m_mayBeDriven"] = False
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
    if rung == "D3" and not fixed_refs:
        rep["degraded"] = ("D3 asked for pinned references but none were given: "
                           "this build is D2 plus nothing")
    doc.notes.append(f"param-drive probe rung {rung}: {rep['driven_segs']} driven "
                     f"segment(s), {rep['param_exprs']} param expr(s), "
                     f"{rep['fixed_refs']} fixed ref(s) -- NOT verified to flex")
    return rep

"""rvt.famgen.constraint_law -- THE CONSTRAINT-GRAPH LAW: internal
contradictions in a family's constraint graph that a validator can catch
WITHOUT Revit.

HISTORY, AND THE LAW THAT WAS WRONG.  On 2026-08-11 the owner clicked the
extrusion in a generated panelboard and Revit failed (#689).  The file
validated 0 errors.  Inspecting it showed that ``Alignment``s and labelled
``LinearDimString``s named the elements they constrain while every one of those
elements carried ``m_constrInfo == []``.  We read that as a one-directional
graph and promoted it to rule CG2 ("every constrained element lists its
constraints in ``m_constrInfo``").

The #787 census of a 421-family Revit-born corpus REFUTED it: ``m_constrInfo``
is ``[]`` on every element of every born file (0 / 421 files carry a single
back-edge), and CG2 reported 38 and 20 errors on two born specimens.  The
owner's desktop then verified a parameter driving geometry in families
written WITHOUT back-edges (#787 one box, #904 trapeze Strut Length).  So CG2
is RETIRED (#910): an empty ``m_constrInfo`` is the born law, never an error,
and this module never demands a back-edge.  The rule id stays reserved so no
later rule reuses it with a different meaning.

WHAT STAYS -- the corpus-attested shape of the in-plane drive (#787 census):

* **CG1**  every element a constraint's witnesses name exists.
* **CG3**  (warning) a constraint with no witnesses constrains nothing.
* **CG4**  a back-edge, WHERE one is present, names a constraint that exists
  and is one (a dangling pointer is a contradiction whatever the law says).
* **CG5**  shape: an ``Alignment`` (sketch lock, m_flags 30; face lock,
  m_flags 14) aligns exactly TWO references; a labelled ``LinearDimString``
  (``m_ArrSegInfo[i].m_paramId`` >= 0) witnesses at least two references with
  one segment per gap, and (when the whole document is in hand) its parameter
  exists.
* **CG6**  registration: a sketch lock (an ``Alignment`` carrying
  ``SketchMembership{VarSketch}``) is listed in its sketch's ``m_dimIds``, and
  every id in a sketch's ``m_dimIds`` is in that sketch's header
  ``m_parents.m_deletion`` (deleting the sketch deletes its locks).
* **CG7**  a sketch lock's curve LIES ON the plane it is locked to: a ``GLine``
  witnessed with geomTag 0 has both ends (``m_origin + m_dirVec * t`` for each
  ``t`` of ``m_endParams``) on the plane; a ``GArc`` witnessed with geomTag 1
  (its centre) has ``m_center`` on it.  The plane of a ``RefPlane`` is the one
  through ``m_freeEnd`` spanned by ``m_bubbleEnd - m_freeEnd`` and
  ``m_cutVec``.  A lock whose geometry is not one of these two cases is not
  judged (never guessed).

WHAT IT IS NOT.  A file that passes this law is not thereby correct in Revit
(hard rule 4).  It catches contradictions, never omissions we have not
thought of, and says nothing about whether Revit's solver accepts a
consistent graph.

Territory: famgen.  Reads documents and written .rfa files; edits nothing.
Deliberately NOT inside ``validate.py`` (a hot shared file) -- written to be
promoted there once it has earned it.
"""
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

#: Classes that CONSTRAIN other elements (their witnesses name the
#: constrained elements).
CONSTRAINING_CLASSES = ("Alignment", "LinearDimString")

#: CG2 (the m_constrInfo back-edge law) is retired: 0 / 421 Revit-born files
#: carry a back-edge (#787 census, #910).  Kept as a constant so the id is
#: never reused and callers can assert it is gone.
RETIRED_RULES = ("CG2",)

#: Severity names, matching the validator's own vocabulary.
ERROR = "error"
WARNING = "warning"

#: on-plane tolerance, feet (well under 1/1000 inch; locks are authored exact)
ON_PLANE_TOL = 1e-5

#: classes check_file decodes -- everything the rules above read
FILE_CLASSES = ("Alignment", "LinearDimString", "CurveElem", "RefPlane",
                "ExtrusionElem", "GenericForm", "VarSketch")


def _val(p: Any) -> Dict[str, Any]:
    """The value behind a pointer-wrapped dict, or the dict itself."""
    if isinstance(p, dict):
        if "ptr_class" in p:
            v = p.get("value")
            return v if isinstance(v, dict) else {}
        return p
    return {}


def _witness_grefs(obj: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Every witness's ``m_geomRef`` (in witness order, duplicates kept)."""
    out: List[Dict[str, Any]] = []
    for w in obj.get("m_witnessRefs") or []:
        gref = _val((w or {}).get("m_pWitnessRef")).get("m_geomRef")
        out.append(gref if isinstance(gref, dict) else {})
    return out


def _witness_targets(obj: Dict[str, Any]) -> List[int]:
    """Element ids a constraint's witness references name (distinct)."""
    out: List[int] = []
    for gref in _witness_grefs(obj):
        eid = int(gref.get("m_elemId", -1))
        if eid > 0 and eid not in out:
            out.append(eid)
    return out


def _constr_ids(obj: Dict[str, Any]) -> List[int]:
    """Constraint ids an element's ``m_constrInfo`` lists.  Tolerates both the
    pointer-wrapped form and a bare inline dict, because reading must not be
    the thing that breaks."""
    out: List[int] = []
    for entry in obj.get("m_constrInfo") or []:
        if not isinstance(entry, dict):
            continue
        cid = int(_val(entry).get("m_constrId", -1))
        if cid > 0:
            out.append(cid)
    return out


def _sketch_of_lock(obj: Dict[str, Any]) -> Optional[int]:
    """The VarSketch a sketch lock is a member of, or None (not a sketch lock)."""
    cells = _val(obj.get("m_cellList")).get("m_cells") or []
    for c in cells:
        if isinstance(c, dict) and c.get("ptr_class") == "SketchMembership":
            return int(_val(c).get("m_groupId", -1))
    return None


def _deletion(header: Optional[Dict[str, Any]]) -> Optional[List[int]]:
    if not isinstance(header, dict):
        return None
    par = _val(header.get("m_parents"))
    dele = par.get("m_deletion")
    return [int(i) for i in dele] if isinstance(dele, list) else None


# -- geometry ---------------------------------------------------------------

def _vec(v: Any) -> Optional[Tuple[float, float, float]]:
    try:
        x = tuple(float(c) for c in v)
    except (TypeError, ValueError):
        return None
    return x if len(x) == 3 and all(math.isfinite(c) for c in x) else None


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def plane_of(cls: str, obj: Dict[str, Any]
             ) -> Optional[Tuple[Tuple[float, float, float],
                                 Tuple[float, float, float]]]:
    """``(point, unit normal)`` of a ``RefPlane``, or None when it is not one
    or its data is degenerate."""
    if cls != "RefPlane":
        return None
    f, b, cut = (_vec(obj.get(k)) for k in ("m_freeEnd", "m_bubbleEnd", "m_cutVec"))
    if f is None or b is None or cut is None:
        return None
    n = _cross(_sub(b, f), cut)
    ln = math.sqrt(_dot(n, n))
    if ln < 1e-12:
        return None
    return f, (n[0] / ln, n[1] / ln, n[2] / ln)


def lock_points(cls: str, obj: Dict[str, Any], geom_tag: int
                ) -> Optional[List[Tuple[float, float, float]]]:
    """The points a sketch lock pins to its plane for a witness of
    ``geom_tag`` on element ``obj``, or None when the case is not one this law
    knows (GLine geomTag 0 = both ends; GArc geomTag 1 = the centre)."""
    if cls != "CurveElem":
        return None
    crv_p = _val(obj.get("m_pCurveDriver")).get("m_pCrv")
    if not isinstance(crv_p, dict):
        return None
    kind, crv = crv_p.get("ptr_class"), _val(crv_p)
    if kind == "GLine" and geom_tag == 0:
        o, d = _vec(crv.get("m_origin")), _vec(crv.get("m_dirVec"))
        ts = crv.get("m_endParams") or []
        if o is None or d is None or len(ts) != 2:
            return None
        return [(o[0] + d[0] * float(t), o[1] + d[1] * float(t),
                 o[2] + d[2] * float(t)) for t in ts]
    if kind == "GArc" and geom_tag == 1:
        c = _vec(crv.get("m_center"))
        return [c] if c is not None else None
    return None


# -- the law ----------------------------------------------------------------

def _norm(elements: Iterable[Sequence[Any]]
          ) -> Dict[int, Tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]]:
    """Accept ``(id, class, obj)`` or ``(id, class, obj, header)``."""
    out: Dict[int, Tuple[str, Dict[str, Any], Optional[Dict[str, Any]]]] = {}
    for t in elements:
        eid, cls, obj = t[0], t[1], t[2]
        hdr = t[3] if len(t) > 3 else None
        out[int(eid)] = (cls, obj or {}, hdr)
    return out


def check_graph(elements: Iterable[Sequence[Any]], *,
                universe: Optional[Iterable[int]] = None
                ) -> List[Dict[str, Any]]:
    """The law over ``(elem_id, class_name, obj[, header])`` tuples.

    An id is "in the document" when it is one of the tuples or in
    ``universe`` (``check_file`` decodes only the constraint-relevant classes
    and passes every element id of the file here).

    Never demands an ``m_constrInfo`` back-edge (CG2 retired, #910).
    Returns findings; empty means the graph is coherent.
    """
    by_id = _norm(elements)
    known = set(by_id) | {int(i) for i in (universe or ())}
    findings: List[Dict[str, Any]] = []

    def add(sev, rule, eid, cls, msg, **extra):
        findings.append({"severity": sev, "rule": rule, "element": eid,
                         "class": cls, "message": msg, **extra})

    for eid, (cls, obj, _hdr) in sorted(by_id.items()):
        if cls not in CONSTRAINING_CLASSES:
            continue
        grefs = _witness_grefs(obj)
        targets = _witness_targets(obj)
        if not grefs:
            add(WARNING, "CG3", eid, cls,
                f"{cls} {eid} constrains nothing: it has no witness "
                f"references, so it is inert")
        for t in targets:
            if t not in known:
                add(ERROR, "CG1", eid, cls,
                    f"{cls} {eid} references element {t}, which is not in "
                    f"the document")
        # CG5 -- shape
        if cls == "Alignment" and grefs and len(grefs) != 2:
            add(ERROR, "CG5", eid, cls,
                f"Alignment {eid} has {len(grefs)} witness reference(s); an "
                f"alignment aligns exactly two references")
        if cls == "LinearDimString":
            segs = obj.get("m_ArrSegInfo") or []
            params = _param_ids(obj)
            if params:
                if len(grefs) < 2 or len(segs) != len(grefs) - 1:
                    add(ERROR, "CG5", eid, cls,
                        f"labelled LinearDimString {eid} has {len(grefs)} "
                        f"witness(es) and {len(segs)} segment(s); a labelled "
                        f"dimension measures between at least two references, "
                        f"one segment per gap")
                for p in params:
                    if p not in known:
                        add(ERROR, "CG5", eid, cls,
                            f"LinearDimString {eid} is labelled with "
                            f"parameter {p}, which is not in the document")
        if cls != "Alignment":
            continue
        sk_id = _sketch_of_lock(obj)
        if sk_id is None:
            continue
        # CG6 -- registration on the sketch
        sk = by_id.get(sk_id)
        if sk is None:
            if sk_id not in known:
                add(ERROR, "CG6", eid, cls,
                    f"sketch lock {eid} is a member of sketch {sk_id}, which "
                    f"is not in the document")
        else:
            dim_ids = [int(i) for i in (sk[1].get("m_dimIds") or [])]
            if eid not in dim_ids:
                add(ERROR, "CG6", eid, cls,
                    f"sketch lock {eid} names sketch {sk_id} but is not in "
                    f"its m_dimIds: the sketch does not own the lock")
        # CG7 -- the locked curve lies on the locked plane
        planes = []
        points = []
        for g in grefs:
            t = int(g.get("m_elemId", -1))
            tgt = by_id.get(t)
            if tgt is None:
                continue
            pl = plane_of(tgt[0], tgt[1])
            if pl is not None:
                planes.append((t, pl))
                continue
            pts = lock_points(tgt[0], tgt[1], int(g.get("m_geomTag", 0)))
            if pts is not None:
                points.append((t, pts))
        if len(planes) == 1 and len(points) == 1:
            (pid, (p0, n)), (cid, pts) = planes[0], points[0]
            off = max(abs(_dot(_sub(p, p0), n)) for p in pts)
            if off > ON_PLANE_TOL:
                add(ERROR, "CG7", eid, cls,
                    f"sketch lock {eid} locks curve {cid} to plane {pid}, but "
                    f"the curve is {off:.6g} ft off that plane: the lock "
                    f"contradicts the geometry it locks",
                    offset_ft=off)

    # CG6 -- every id a sketch registers is a deletion child of the sketch
    for eid, (cls, obj, hdr) in sorted(by_id.items()):
        if cls != "VarSketch":
            continue
        dele = _deletion(hdr)
        if dele is None:
            continue
        missing = [int(i) for i in (obj.get("m_dimIds") or [])
                   if int(i) not in dele]
        if missing:
            add(ERROR, "CG6", eid, cls,
                f"VarSketch {eid} lists {missing} in m_dimIds but not in its "
                f"header m_deletion: deleting the sketch would orphan them",
                missing=missing)

    # CG4 -- a back-edge, where one exists, must point at a real constraint
    # (back-edges are never REQUIRED: 0 / 421 born files carry one)
    for eid, (cls, obj, _hdr) in sorted(by_id.items()):
        for cid in _constr_ids(obj):
            if cid not in known:
                add(ERROR, "CG4", eid, cls,
                    f"{cls} {eid} lists constraint {cid}, which is not in "
                    f"the document")
            elif by_id[cid][0] not in CONSTRAINING_CLASSES:
                add(ERROR, "CG4", eid, cls,
                    f"{cls} {eid} lists {cid} as a constraint, but {cid} is a "
                    f"{by_id[cid][0]}, which does not constrain anything")
    return findings


def _param_ids(obj: Dict[str, Any]) -> List[int]:
    return [int(s.get("m_paramId", -1)) for s in obj.get("m_ArrSegInfo") or []
            if isinstance(s, dict) and int(s.get("m_paramId", -1)) >= 0]


def check_doc(doc: Any) -> List[Dict[str, Any]]:
    """The law over an in-memory ``FamilyDoc`` -- the cheapest place to catch
    it, before a single byte is written."""
    return check_graph(((e.elem_id, e.class_name, e.obj,
                         getattr(e, "header", None))
                        for e in getattr(doc, "elements", [])))


def check_file(path: str) -> List[Dict[str, Any]]:
    """The law over a WRITTEN ``.rfa`` / ``.rft``.

    Decoding the file rather than trusting the builder is the point: it is the
    same instrument a user's file can be run through.
    """
    from ..families import FamilyIndex
    from ..objects import ObjectDecoder

    idx = FamilyIndex(path)
    dec = ObjectDecoder(idx.schema)
    recs = idx.unit_records(0)
    tuples: List[Tuple[int, str, Dict[str, Any], Optional[Dict[str, Any]]]] = []
    for cls in FILE_CLASSES:
        for eid in idx.ids_of_class(0, cls):
            r = recs.get(102, {}).get(eid)
            if r is None:
                continue
            o = dec.decode_record(r.class_id, r.payload)
            if o is None:
                continue
            hdr = None
            if cls == "VarSketch":
                h = recs.get(101, {}).get(eid)
                ho = dec.decode_record(h.class_id, h.payload) if h is not None else None
                hdr = (ho.value or {}) if ho is not None else None
            tuples.append((int(eid), cls, o.value or {}, hdr))
    return check_graph(tuples, universe=recs.get(102, {}).keys())


def summarise(findings: List[Dict[str, Any]]) -> str:
    """One line per finding, worst first -- quotable in a delivery."""
    if not findings:
        return "constraint graph: coherent (no findings)"
    errs = [f for f in findings if f["severity"] == ERROR]
    warns = [f for f in findings if f["severity"] != ERROR]
    lines = [f"constraint graph: {len(errs)} error(s), {len(warns)} warning(s)"]
    for f in errs + warns:
        lines.append(f"  [{f['rule']}] {f['message']}")
    return "\n".join(lines)

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

* **CG8**  an INSTANCE lock (#917) holds: an ``Alignment`` locking a nested
  ``FamilyInstance``'s centre reference (witness geomTag 0-8 = the child
  document's Is-Reference code, resolved to the child's ``RefPlane`` with that
  ``m_refName``, the origin-defining one where two share it) to a host
  ``RefPlane`` has that child plane, placed by the instance transform, LIE ON
  the host plane: parallel, and its point within ``ON_PLANE_TOL``.  Born
  evidence (421-family corpus, centre-reference locks to a RefPlane): 1,297 /
  1,297 Center (Left/Right), 1,084 / 1,084 Center (Front/Back) and 11 / 11
  Center (Elevation) hold, with a plane read from its ``m_pSurface`` and the
  transform applied as ``world_k = m_or_k + m_3x3[k] . v`` (the other reading
  of ``m_3x3`` leaves 249 of them non-parallel).  Named references (other
  geomTags) and references the child cannot resolve are not judged.

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

#: CG8: the instance-witness geomTags that name a child's Is-Reference code
#: (RefPlane.m_refName: 0 Left .. 8 Top; 1 / 4 / 7 = the three centres)
INSTANCE_REF_TAGS = tuple(range(9))

#: CG8: parallel tolerance on unit normals (|n1 . n2| within this of 1)
PARALLEL_TOL = 1e-6


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


def plane_of_any(cls: str, obj: Dict[str, Any]
                 ) -> Optional[Tuple[Tuple[float, float, float],
                                     Tuple[float, float, float]]]:
    """``(point, unit normal)`` of a ``RefPlane`` from its ``m_pSurface``
    (origin, x axis, y axis) -- the plane's own geometry, present on
    surface-only planes whose drawn ends are zero (born families, our
    horizontal planes) -- else from its drawn ends (:func:`plane_of`).  Used
    by CG8 only; CG7 keeps :func:`plane_of`."""
    if cls != "RefPlane":
        return None
    srf = _val(obj.get("m_pSurface"))
    o, x, y = (_vec(srf.get(k)) for k in ("m_origin", "m_xVec", "m_yVec"))
    if o is not None and x is not None and y is not None:
        n = _cross(x, y)
        ln = math.sqrt(_dot(n, n))
        if ln >= 1e-12:
            return o, (n[0] / ln, n[1] / ln, n[2] / ln)
    return plane_of(cls, obj)


def transform_plane(trf: Dict[str, Any], plane) -> Optional[Tuple[Tuple[float, float, float],
                                                                  Tuple[float, float, float]]]:
    """A child-document plane placed by an ``InstanceInfo.m_Trf``:
    ``world_k = m_or_k + m_3x3[k] . v`` (the reading the born corpus holds,
    CG8 in the module docstring)."""
    m, o = trf.get("m_3x3") if isinstance(trf, dict) else None, _vec((trf or {}).get("m_or"))
    if not (isinstance(m, list) and len(m) == 3 and o is not None):
        return None
    rows = [_vec(r) for r in m]
    if any(r is None for r in rows):
        return None
    p, n = plane
    wp = tuple(o[k] + _dot(rows[k], p) for k in range(3))
    wn = tuple(_dot(rows[k], n) for k in range(3))
    ln = math.sqrt(_dot(wn, wn))
    if ln < 1e-12:
        return None
    return wp, (wn[0] / ln, wn[1] / ln, wn[2] / ln)


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
                universe: Optional[Iterable[int]] = None,
                instance_planes: Optional[Dict[Tuple[int, int], Any]] = None
                ) -> List[Dict[str, Any]]:
    """The law over ``(elem_id, class_name, obj[, header])`` tuples.

    An id is "in the document" when it is one of the tuples or in
    ``universe`` (``check_file`` decodes only the constraint-relevant classes
    and passes every element id of the file here).

    ``instance_planes`` = ``{(instance id, geomTag): (point, normal)}``, the
    child reference each instance witness names, already placed in host
    coordinates (``check_file`` resolves them from the nested documents); a
    witness missing from it is not judged by CG8.

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
        # CG8 -- an instance lock's placed child reference lies on its plane
        if instance_planes and len(grefs) == 2:
            _cg8(eid, cls, grefs, by_id, instance_planes, add)
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
            elif cid not in by_id:
                # in the file but of a class this law does not decode (a
                # Level, another dimension class): it exists, so it is not a
                # dangling pointer, and its class cannot be judged here --
                # reading must not be the thing that breaks (#927 review)
                continue
            elif by_id[cid][0] not in CONSTRAINING_CLASSES:
                add(ERROR, "CG4", eid, cls,
                    f"{cls} {eid} lists {cid} as a constraint, but {cid} is a "
                    f"{by_id[cid][0]}, which does not constrain anything")
    return findings


def _cg8(eid, cls, grefs, by_id, instance_planes, add) -> None:
    planes, refs = [], []
    for g in grefs:
        t, tag = int(g.get("m_elemId", -1)), int(g.get("m_geomTag", 0))
        if (t, tag) in instance_planes:
            refs.append((t, tag, instance_planes[(t, tag)]))
            continue
        tgt = by_id.get(t)
        pl = plane_of_any(tgt[0], tgt[1]) if tgt is not None else None
        if pl is not None:
            planes.append((t, pl))
    if len(planes) != 1 or len(refs) != 1:
        return
    (pid, (p0, n)), (iid, tag, (q, m)) = planes[0], refs[0]
    if abs(abs(_dot(n, m)) - 1.0) > PARALLEL_TOL:
        add(ERROR, "CG8", eid, cls,
            f"instance lock {eid} locks reference {tag} of instance {iid} to "
            f"plane {pid}, but the placed reference is not parallel to that "
            f"plane: the lock contradicts the geometry it locks")
        return
    off = abs(_dot(_sub(q, p0), n))
    if off > ON_PLANE_TOL:
        add(ERROR, "CG8", eid, cls,
            f"instance lock {eid} locks reference {tag} of instance {iid} to "
            f"plane {pid}, but the placed reference is {off:.6g} ft off that "
            f"plane: the lock contradicts the geometry it locks",
            offset_ft=off)


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
    same instrument a user's file can be run through.  Read under the file's
    OWN release (a 2025 file's framing is not 2026's), as every instrument is.
    """
    from contextlib import ExitStack
    from ..global_framing import enter_own_release

    with ExitStack() as st:
        enter_own_release(st, path)
        return _check_file(path)


def _check_file(path: str) -> List[Dict[str, Any]]:
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
    inst = _instance_planes(idx, recs, tuples)
    return check_graph(tuples, universe=recs.get(102, {}).keys(),
                       instance_planes=inst)


def _instance_planes(idx: Any, recs: Dict[int, Dict[int, Any]],
                     tuples: Sequence[Tuple[int, str, Dict[str, Any], Any]]
                     ) -> Dict[Tuple[int, int], Any]:
    """CG8's input: every ``(instance, geomTag)`` an Alignment witnesses, with
    the tag an Is-Reference code, resolved through instance -> symbol ->
    nested Family -> its content document's ``RefPlane`` with that
    ``m_refName`` (the origin-defining one when two share it) and placed by
    the instance transform.  Anything that does not resolve is left out --
    never guessed."""
    r102 = recs.get(102, {})
    wanted = set()
    for _eid, cls, obj, _h in tuples:
        if cls != "Alignment":
            continue
        for g in _witness_grefs(obj):
            t, tag = int(g.get("m_elemId", -1)), int(g.get("m_geomTag", -1))
            r = r102.get(t)
            if (r is not None and tag in INSTANCE_REF_TAGS
                    and idx.class_name(r.class_id) == "FamilyInstance"):
                wanted.add((t, tag))
    out: Dict[Tuple[int, int], Any] = {}
    if not wanted:
        return out

    def val(unit: int, eid: int) -> Dict[str, Any]:
        o = idx.decode(unit, eid, 102)
        return (o.value or {}) if o is not None and isinstance(o.value, dict) else {}
    child_cache: Dict[str, List[Dict[str, Any]]] = {}
    for iid, tag in sorted(wanted):
        ii = _val(val(0, iid).get("m_pInstanceInfo"))
        sym = ii.get("m_symbolId")
        if not isinstance(sym, int) or sym not in r102:
            continue
        fam = val(0, sym).get("m_familyId")
        if not isinstance(fam, int) or fam not in r102:
            continue
        guid = _val(val(0, fam).get("m_oFamDoc")).get("m_contentDocGUID")
        unit = getattr(idx, "unit_by_guid", {}).get(guid)
        if unit is None:
            continue
        if guid not in child_cache:
            ur = idx.unit_records(unit).get(102, {})
            child_cache[guid] = [val(unit, e) for e, r in sorted(ur.items())
                                 if idx.class_name(r.class_id) == "RefPlane"]
        cands = [p for p in child_cache[guid] if p.get("m_refName") == tag]
        if len(cands) > 1:
            cands = [p for p in cands if p.get("m_definesOrigin")]
        if len(cands) != 1:
            continue
        pl = plane_of_any("RefPlane", cands[0])
        placed = transform_plane(ii.get("m_Trf"), pl) if pl is not None else None
        if placed is not None:
            out[(iid, tag)] = placed
    return out


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

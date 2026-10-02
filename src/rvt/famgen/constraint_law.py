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
  exists.  (#956) In a NESTED family's document "exists" has one more born
  form: a SHARED parameter (``ParamElemExternal``) is stored once, in the
  host document (unit 0), and the nested document names it by that id -- so a
  nested unit's label may be a ``ParamElemExternal`` of the host document,
  provided the ``Family`` its dimension's ``m_famId`` names lists it in
  ``m_familyParams`` (the nested family declares it).  The first reading
  (the parameter must be in the dimension's own unit) fired 236 errors on
  nested units of the 421 born families (0 on host documents): every one a
  labelled ``LinearDimString`` whose parameter is a host-held shared
  parameter, which the nested family's own ``Family`` lists -- 0 of 4,425
  nested units carries a ``ParamElemExternal`` of its own, and element ids
  never repeat across units.  Census in
  ``docs/inbox/param-drive.d/956-cg5.md``.
* **CG6**  registration: a sketch lock (an ``Alignment`` carrying
  ``SketchMembership{VarSketch}``) is listed in its sketch's ``m_dimIds``, and
  every id in a sketch's ``m_dimIds`` is in that sketch's header
  ``m_parents.m_deletion`` (deleting the sketch deletes its locks).
* **CG7**  a sketch lock's curve LIES ON the plane it is locked to: a ``GLine``
  witnessed whole (geomTag 0, subTag -1) has both ends (``m_origin + m_dirVec
  * t`` for each ``t`` of ``m_endParams``) on the plane; a ``GLine`` END
  witnessed (geomTag 0, subTag 0 / 1) has THAT end on it -- the other end is
  free; a ``GArc`` witnessed with geomTag 1 (its centre) has ``m_center`` on
  it.  The plane of a ``RefPlane`` is its own surface (``m_pSurface``:
  origin, x axis, y axis -- :func:`plane_of_any`); only a plane with no
  surface falls back to the one through ``m_freeEnd`` spanned by
  ``m_bubbleEnd - m_freeEnd`` and ``m_cutVec``.  A lock whose geometry is not
  one of these cases is not judged (never guessed).  (#953) The first
  reading -- both ends for every line witness, the plane from its drawn ends
  -- fired 139 errors on the host documents of the 421 born families (410
  over host + nested units): 109 host (338 all) were END locks judged on
  their free end (6 host / 22 all of them also locked to a plane whose drawn
  ends are off its surface), and 30 host (72 all) were whole-line or arc-
  centre locks to such a plane.  Corrected -- and now also judging the
  surface-only planes the drawn-end reading skipped -- it holds on all
  15,867 judged born sketch locks (2,313 host; 0 CG7 findings; census in
  ``docs/inbox/param-drive.d/953-cg7.md``).

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
  (#940) The judged lock's own frame agrees with its plane too: its
  ``m_constrDir`` is parallel to the host plane's normal, and both
  ``m_refPnts`` and its ``m_oldOrigin`` lie on the host plane -- each held by
  2,393 / 2,393 judged born locks (of them 467 ELEVATION locks, to a
  horizontal host plane: tags 1 / 4 on rotated instances 119 / 338, Bottom 1,
  Center (Elevation) 9).  :func:`judged_instance_locks` lists what CG8
  judged in a written file, elevation locks marked.  (#948) A judged lock
  that does not CARRY one of the three frame fields gets a WARNING: born
  locks carry all three, and so does every lock our writers emit.

(#948) ANGULAR AND SKETCH DIMENSIONS -- ``AngularDim`` is a constraining class
(387 born, every one 2 witnesses / 1 segment; the hexagon recipe of
:mod:`rvt.famgen.angular_law`):

* **CG5** also covers an ``AngularDim``: at least two witnesses and one segment
  per gap.  **CG6** covers every SKETCH-MEMBER constraint, not only sketch
  locks: an ``AngularDim`` / ``LinearDimString`` carrying
  ``SketchMembership{VarSketch}`` is in that sketch's ``m_dimIds``.
* **CG9**  an ``AngularDim`` over sketch lines (``GLine`` witnesses, geomTag
  0, subTag -1) holds: each LOCKED segment's value is the angle between its
  two lines (either of the two supplementary angles), and the segments of an
  EQ angular dimension (segment flags bit 2) measure equal angles.  (The born
  library has no angular EQ -- 0 / 387 have more than two witnesses -- so the
  EQ half is judged on synthetic graphs only.)
* **CG10** a ``LinearDimString`` whose witnesses all resolve -- a reference
  plane square to the dimension line, a sketch line square to it (subTag -1),
  a line END (subTag 0 / 1), or the crossing of two planes
  (``CurveXCurveInPlaneRef``) -- stores, on every LOCKED, LABELLED or EQ
  segment, the distance its two witnesses are apart along the dimension
  line, and an EQ dimension's segments are equal.  A witness that does not
  resolve, or does not sit square to the dimension line, leaves the dimension
  unjudged (never guessed).

(#952) SKETCH SOLVER RECORDS:

* **CG11**  a ``VarSketchHorVerConstrObj`` holds: the sketch line it names
  (a ``VarSketchLineSegObj`` in the same sketch's ``m_elemRecs``, read from
  its own solver parameters x1, y1, x2, y2) is horizontal when ``m_hor`` is
  True and vertical when it is False (:func:`line_axis`).  An HV on a slanted
  line -- or on the other axis -- contradicts the geometry it constrains.
  Born evidence (421-family corpus, host + nested units): 62,033 HV
  constraints, every one on an axis-parallel line with ``m_hor`` = horizontal
  (0 on the 14,219 slanted lines; the nearest-to-axis slanted line is
  6.3e-8 degrees off, far outside the tolerance).  An HV naming anything
  other than a line, or a line without four parameters, is not judged.

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
CONSTRAINING_CLASSES = ("Alignment", "LinearDimString", "AngularDim")

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
FILE_CLASSES = ("Alignment", "LinearDimString", "AngularDim", "CurveElem", "RefPlane",
                "ExtrusionElem", "GenericForm", "VarSketch", "Family")

#: CG5 (#956): the parameter class a nested document may name from its host
#: (shared parameters are stored once, in unit 0)
HOST_SHARED_PARAM_CLASS = "ParamElemExternal"

#: CG9: angle tolerance, radians (locks are authored exact)
ANGLE_TOL = 1e-6
#: CG10: segment flag bits -- 1 locked, 2 EQ
SEG_LOCKED, SEG_EQ = 1, 2

#: CG8: the instance-witness geomTags that name a child's Is-Reference code
#: (RefPlane.m_refName: 0 Left .. 8 Top; 1 / 4 / 7 = the three centres)
INSTANCE_REF_TAGS = tuple(range(9))

#: CG8: parallel tolerance on unit normals (|n1 . n2| within this of 1)
PARALLEL_TOL = 1e-6

#: CG11: a sketch line is axis-parallel when its off-axis extent is within
#: this fraction of max(1 ft, its length) (the writer uses the same test)
HV_AXIS_TOL = 1e-9


def line_axis(x1: float, y1: float, x2: float, y2: float) -> Optional[str]:
    """``"H"`` for a horizontal sketch line, ``"V"`` for a vertical one, None
    for a slanted (or zero-length) one -- the one predicate CG11 judges by and
    the sketch writer emits ``VarSketchHorVerConstrObj`` by (#952)."""
    dx, dy = float(x2) - float(x1), float(y2) - float(y1)
    length = math.hypot(dx, dy)
    if length == 0.0:
        return None
    tol = HV_AXIS_TOL * max(1.0, length)
    if abs(dy) <= tol:
        return "H"
    if abs(dx) <= tol:
        return "V"
    return None


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
    """Element ids a constraint's witness references name (distinct) -- a
    plane-crossing witness (``CurveXCurveInPlaneRef``) names two."""
    out: List[int] = []
    for w in obj.get("m_witnessRefs") or []:
        ref = _val((w or {}).get("m_pWitnessRef"))
        for key in ("m_geomRef", "m_otherGeomRef"):
            gref = ref.get(key)
            if not isinstance(gref, dict):
                continue
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


def _tag(g: Dict[str, Any], key: str, default: int) -> int:
    """A gref's integer tag; ``default`` when absent OR decoded as None (#963 review)."""
    v = g.get(key)
    return default if v is None else int(v)


def plane_of_any(cls: str, obj: Dict[str, Any]
                 ) -> Optional[Tuple[Tuple[float, float, float],
                                     Tuple[float, float, float]]]:
    """``(point, unit normal)`` of a ``RefPlane`` from its ``m_pSurface``
    (origin, x axis, y axis) -- the plane's own geometry, present on
    surface-only planes whose drawn ends are zero (born families, our
    horizontal planes) -- else from its drawn ends (:func:`plane_of`).  Used
    by CG7 (#953), CG8 and CG10."""
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


def lock_points(cls: str, obj: Dict[str, Any], geom_tag: int,
                sub_tag: Optional[int] = None
                ) -> Optional[List[Tuple[float, float, float]]]:
    """The points a sketch lock pins to its plane for a witness of
    ``geom_tag`` on element ``obj``, or None when the case is not one this law
    knows (GLine geomTag 0 = both ends; GArc geomTag 1 = the centre).

    ``sub_tag`` (#953): None keeps the historical answer (both ends of a
    line, as CG9 / CG10 read it); -1 = the whole line (both ends); 0 / 1 =
    that END only; any other value is not a case this law knows (None)."""
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
        ends = [(o[0] + d[0] * float(t), o[1] + d[1] * float(t),
                 o[2] + d[2] * float(t)) for t in ts]
        if sub_tag is None or sub_tag == -1:
            return ends
        if sub_tag in (0, 1):
            return [ends[sub_tag]]
        return None
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
                instance_planes: Optional[Dict[Tuple[int, int], Any]] = None,
                host_shared_params: Optional[Iterable[int]] = None
                ) -> List[Dict[str, Any]]:
    """The law over ``(elem_id, class_name, obj[, header])`` tuples.

    An id is "in the document" when it is one of the tuples or in
    ``universe`` (``check_file`` decodes only the constraint-relevant classes
    and passes every element id of the file here).

    ``instance_planes`` = ``{(instance id, geomTag): (point, normal)}``, the
    child reference each instance witness names, already placed in host
    coordinates (``check_file`` resolves them from the nested documents); a
    witness missing from it is not judged by CG8.

    ``host_shared_params`` (#956) = ids of the shared parameters
    (``ParamElemExternal``) the HOST document holds, passed when the graph is
    a nested family's document: a label naming one of them is a parameter of
    this document when the ``Family`` the dimension's ``m_famId`` names lists
    it in ``m_familyParams``.

    Never demands an ``m_constrInfo`` back-edge (CG2 retired, #910).
    Returns findings; empty means the graph is coherent.
    """
    by_id = _norm(elements)
    known = set(by_id) | {int(i) for i in (universe or ())}
    host_shared = {int(i) for i in (host_shared_params or ())}
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
        if cls == "AngularDim" and grefs:
            segs = obj.get("m_ArrSegInfo") or []
            if len(grefs) < 2 or len(segs) != len(grefs) - 1:
                add(ERROR, "CG5", eid, cls,
                    f"AngularDim {eid} has {len(grefs)} witness(es) and "
                    f"{len(segs)} segment(s); an angular dimension measures "
                    f"between at least two references, one segment per gap")
        if cls in ("LinearDimString", "AngularDim"):
            segs = obj.get("m_ArrSegInfo") or []
            params = _param_ids(obj)
            if params and cls == "LinearDimString":
                if len(grefs) < 2 or len(segs) != len(grefs) - 1:
                    add(ERROR, "CG5", eid, cls,
                        f"labelled LinearDimString {eid} has {len(grefs)} "
                        f"witness(es) and {len(segs)} segment(s); a labelled "
                        f"dimension measures between at least two references, "
                        f"one segment per gap")
            for p in params:
                if p in known:
                    continue
                if p in host_shared:
                    fam = _family_params(by_id, obj.get("m_famId"))
                    if fam is not None and p in fam:
                        continue
                    add(ERROR, "CG5", eid, cls,
                        f"{cls} {eid} is labelled with shared parameter {p} of "
                        f"the host document, but its family "
                        f"{obj.get('m_famId')} does not list it in "
                        f"m_familyParams: the nested family does not declare it")
                    continue
                add(ERROR, "CG5", eid, cls,
                    f"{cls} {eid} is labelled with "
                    f"parameter {p}, which is not in the document")
        # CG6 -- registration on the sketch (every sketch-member constraint)
        sk_id = _sketch_of_lock(obj)
        if sk_id is not None:
            what = "sketch lock" if cls == "Alignment" else f"sketch {cls}"
            sk = by_id.get(sk_id)
            if sk is None:
                if sk_id not in known:
                    add(ERROR, "CG6", eid, cls,
                        f"{what} {eid} is a member of sketch {sk_id}, which "
                        f"is not in the document")
            else:
                dim_ids = [int(i) for i in (sk[1].get("m_dimIds") or [])]
                if eid not in dim_ids:
                    add(ERROR, "CG6", eid, cls,
                        f"{what} {eid} names sketch {sk_id} but is not in "
                        f"its m_dimIds: the sketch does not own it")
        if cls == "AngularDim":
            _cg9(eid, cls, obj, by_id, add)
            continue
        if cls == "LinearDimString":
            _cg10(eid, cls, obj, by_id, add)
            continue
        # CG8 -- an instance lock's placed child reference lies on its plane
        if instance_planes and len(grefs) == 2:
            _cg8(eid, cls, grefs, by_id, instance_planes, add)
        if sk_id is None:
            continue
        # CG7 -- the locked curve lies on the locked plane
        planes = []
        points = []
        for g in grefs:
            t = int(g.get("m_elemId", -1))
            tgt = by_id.get(t)
            if tgt is None:
                continue
            pl = plane_of_any(tgt[0], tgt[1])
            if pl is not None:
                planes.append((t, pl))
                continue
            pts = lock_points(tgt[0], tgt[1], _tag(g, "m_geomTag", 0),
                              _tag(g, "m_subTag", -1))
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
        _cg11(eid, cls, obj, add)
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


def _cg11(eid, cls, obj, add) -> None:
    """CG11 -- every HorVer constraint of a sketch's solver sits on a line
    along its own axis (#952)."""
    lines: Dict[int, List[float]] = {}
    for r in obj.get("m_elemRecs") or []:
        if not isinstance(r, dict) or r.get("ptr_class") != "VarSketchLineSegObj":
            continue
        try:
            prm = [float(_val(q)["m_val"]) for q in _val(r).get("m_params") or []]
        except (KeyError, TypeError, ValueError):
            continue
        if len(prm) == 4 and r.get("pid") is not None:
            lines[int(r["pid"])] = prm
    for c in obj.get("m_constrRecs") or []:
        if not isinstance(c, dict) or c.get("ptr_class") != "VarSketchHorVerConstrObj":
            continue
        cv = _val(c)
        hor = bool(cv.get("m_hor"))
        for w in cv.get("m_constrElems") or []:
            prm = lines.get(_tag(w or {}, "weakref", -1))   # None-safe (#964 review)
            if prm is None:
                continue
            axis = line_axis(*prm)
            if axis != ("H" if hor else "V"):
                what = "slanted" if axis is None else ("horizontal" if axis == "H" else "vertical")
                add(ERROR, "CG11", eid, cls,
                    f"VarSketch {eid} constrains a {what} line "
                    f"({prm[0]:.6g}, {prm[1]:.6g}) -> ({prm[2]:.6g}, {prm[3]:.6g}) "
                    f"to be {'horizontal' if hor else 'vertical'}: the "
                    f"horizontal/vertical constraint contradicts the geometry it "
                    f"constrains", line=prm, hor=hor)


def cg8_pick(grefs, plane_at, instance_planes):
    """The ONE selection rule CG8 judges by (shared with
    :func:`judged_instance_locks`, #949 review): a two-witness lock with exactly
    one witness an instance reference in ``instance_planes`` and exactly one a
    plane (``plane_at(elem id)`` -> ``(point, normal)`` or None).  Returns
    ``(plane id, plane, instance id, tag, placed reference)`` or None (not
    judged)."""
    if len(grefs) != 2:
        return None
    planes, refs = [], []
    for g in grefs:
        t, tag = int(g.get("m_elemId", -1)), int(g.get("m_geomTag", 0))
        if (t, tag) in instance_planes:
            refs.append((t, tag, instance_planes[(t, tag)]))
            continue
        pl = plane_at(t)
        if pl is not None:
            planes.append((t, pl))
    if len(planes) != 1 or len(refs) != 1:
        return None
    (pid, pl), (iid, tag, placed) = planes[0], refs[0]
    return pid, pl, iid, tag, placed


def _cg8(eid, cls, grefs, by_id, instance_planes, add) -> None:
    def plane_at(t):
        tgt = by_id.get(t)
        return plane_of_any(tgt[0], tgt[1]) if tgt is not None else None
    pick = cg8_pick(grefs, plane_at, instance_planes)
    if pick is None:
        return
    pid, (p0, n), iid, tag, (q, m) = pick
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
    _cg8_frame(eid, cls, by_id[eid][1] if eid in by_id else {}, pid, p0, n, add)


#: the three frame fields every judged born lock carries (2,393 / 2,393)
CG8_FRAME_FIELDS = ("m_constrDir", "m_refPnts", "m_oldOrigin")


def _cg8_frame(eid, cls, obj, pid, p0, n, add) -> None:
    """#940: the lock's own frame agrees with the plane it locks to
    (2,393 / 2,393 judged born locks each): ``m_constrDir`` parallel to the
    plane normal; ``m_refPnts`` and ``m_oldOrigin`` on the plane.  A frame
    field the lock does not carry (absent, empty or unreadable) is REPORTED as
    a warning (#949 review) -- never silently skipped, never guessed."""
    cd = _vec(obj.get("m_constrDir"))
    refs = [_vec(q) for q in (obj.get("m_refPnts") or [])]
    old = _vec(obj.get("m_oldOrigin"))
    missing = [f for f, ok in zip(CG8_FRAME_FIELDS,
                                  (cd is not None, bool(refs) and None not in refs,
                                   old is not None)) if not ok]
    if missing:
        add(WARNING, "CG8", eid, cls,
            f"instance lock {eid} does not carry {', '.join(missing)}: that part "
            f"of its frame is not judged against plane {pid} (every judged born "
            f"lock carries all three)", missing=missing)
    if cd is not None and abs(abs(_dot(cd, n)) - 1.0) > PARALLEL_TOL:
        add(ERROR, "CG8", eid, cls,
            f"instance lock {eid}'s constrained direction {cd} is not the normal "
            f"of plane {pid}: the lock would pull the instance along the plane")
    pts = [("m_refPnts", q) for q in refs] + [("m_oldOrigin", old)]
    for name, q in pts:
        if q is None:
            continue
        off = abs(_dot(_sub(q, p0), n))
        if off > ON_PLANE_TOL:
            add(ERROR, "CG8", eid, cls,
                f"instance lock {eid}'s {name} point is {off:.6g} ft off plane "
                f"{pid}: the lock is drawn somewhere it does not lock",
                offset_ft=off)


# -- CG9 / CG10: angular and linear dimensions against their geometry (#948) --

def _seg_flags(seg: Dict[str, Any]) -> int:
    try:
        return int(seg.get("m_flags", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _seg_value(seg: Dict[str, Any], locked: bool) -> Optional[float]:
    """A segment's stored value: its locked value for a lock, else the first
    ``m_values`` entry (the current value), else the locked value."""
    lv = seg.get("m_lockedValue")
    if locked and isinstance(lv, (int, float)):
        return float(lv)
    vals = seg.get("m_values") or []
    v = vals[0].get("m_value") if vals and isinstance(vals[0], dict) else None
    if isinstance(v, (int, float)) and v >= 0.0:
        return float(v)
    return float(lv) if isinstance(lv, (int, float)) else None


def _whole_line(by_id, g: Dict[str, Any]):
    """``(start, unit direction)`` of a witness naming a whole sketch GLine
    (geomTag 0, subTag -1), else None."""
    if int(g.get("m_geomTag", 0)) != 0 or int(g.get("m_subTag", -1)) != -1:
        return None
    tgt = by_id.get(int(g.get("m_elemId", -1)))
    pts = lock_points(tgt[0], tgt[1], 0) if tgt is not None else None
    if not pts or len(pts) != 2:
        return None
    d = _sub(pts[1], pts[0])
    ln = math.sqrt(_dot(d, d))
    if ln < 1e-12:
        return None
    return pts[0], (d[0] / ln, d[1] / ln, d[2] / ln)


def _cg9(eid, cls, obj, by_id, add) -> None:
    grefs = _witness_grefs(obj)
    segs = [s for s in obj.get("m_ArrSegInfo") or [] if isinstance(s, dict)]
    lines = [_whole_line(by_id, g) for g in grefs]
    if len(grefs) < 2 or None in lines or len(segs) != len(grefs) - 1:
        return                                   # not judged (never guessed)
    angles = []
    for i, seg in enumerate(segs):
        (_p, d), (_q, e) = lines[i], lines[i + 1]
        th = math.acos(max(-1.0, min(1.0, _dot(d, e))))
        angles.append(min(th, math.pi - th))
        if _seg_flags(seg) & SEG_LOCKED:
            v = _seg_value(seg, True)
            if v is not None and min(abs(v - th), abs(v - (math.pi - th))) > ANGLE_TOL:
                add(ERROR, "CG9", eid, cls,
                    f"angular dimension {eid} locks segment {i} at "
                    f"{math.degrees(v):.6g} deg, but its lines meet at "
                    f"{math.degrees(th):.6g} deg: the lock contradicts the sketch",
                    value=v, measured=th)
    eq = [angles[i] for i, s in enumerate(segs) if _seg_flags(s) & SEG_EQ]
    if len(eq) >= 2 and max(eq) - min(eq) > ANGLE_TOL:
        add(ERROR, "CG9", eid, cls,
            f"angular EQ dimension {eid} spans unequal angles "
            f"({', '.join(f'{math.degrees(a):.6g}' for a in eq)} deg)")
    # (the arc's centre is NOT judged: 19 of 36 judged born host-document
    # angular dimensions draw it away from where their lines cross)


def _crossing(p1, p2):
    """``(point, unit direction)`` of the line where planes ``p1`` and ``p2``
    cross, or None when they are parallel."""
    (a, n), (b, m) = p1, p2
    u = _cross(n, m)
    det = _dot(u, u)
    if det < 1e-18:
        return None
    # X = ((n.a) (m x u) + (m.b) (u x n)) / |u|^2 lies on both planes
    da, db = _dot(n, a), _dot(m, b)
    mu, un = _cross(m, u), _cross(u, n)
    x = tuple((da * mu[k] + db * un[k]) / det for k in range(3))
    ln = math.sqrt(det)
    return x, (u[0] / ln, u[1] / ln, u[2] / ln)


def _witness_coord(by_id, w: Dict[str, Any], d) -> Optional[float]:
    """Where a witness sits along the unit dimension direction ``d``, or None
    when it does not resolve or is not square to ``d``."""
    ptr = (w or {}).get("m_pWitnessRef")
    ref = _val(ptr)
    g = ref.get("m_geomRef") if isinstance(ref.get("m_geomRef"), dict) else {}

    def plane(gr):
        tgt = by_id.get(int((gr or {}).get("m_elemId", -1)))
        return plane_of_any(tgt[0], tgt[1]) if tgt is not None else None
    if isinstance(ptr, dict) and ptr.get("ptr_class") == "CurveXCurveInPlaneRef":
        p1, p2 = plane(g), plane(ref.get("m_otherGeomRef"))
        cr = _crossing(p1, p2) if p1 is not None and p2 is not None else None
        if cr is None or abs(_dot(cr[1], d)) > 1e-9:
            return None
        return _dot(cr[0], d)
    pl = plane(g)
    if pl is not None:
        if abs(abs(_dot(pl[1], d)) - 1.0) > PARALLEL_TOL:
            return None
        return _dot(pl[0], d)
    tgt = by_id.get(int(g.get("m_elemId", -1)))
    if tgt is None or int(g.get("m_geomTag", 0)) != 0:
        return None
    sub = int(g.get("m_subTag", -1))
    pts = lock_points(tgt[0], tgt[1], 0)
    if not pts or len(pts) != 2:
        return None
    if sub in (0, 1):
        return _dot(pts[sub], d)
    if sub != -1:
        return None
    ln = _sub(pts[1], pts[0])
    if abs(_dot(ln, d)) > 1e-9 * max(1.0, math.sqrt(_dot(ln, ln))):
        return None
    return _dot(pts[0], d)


def _cg10(eid, cls, obj, by_id, add) -> None:
    segs = [s for s in obj.get("m_ArrSegInfo") or [] if isinstance(s, dict)]
    ws = obj.get("m_witnessRefs") or []
    judged = [i for i, s in enumerate(segs)
              if _seg_flags(s) & (SEG_LOCKED | SEG_EQ) or int(s.get("m_paramId", -1)) >= 0]
    if not judged or len(ws) != len(segs) + 1:
        return
    d = _vec(_val(obj.get("m_pDimLine")).get("m_dirVec"))
    if d is None or _dot(d, d) < 1e-24:
        return
    ln = math.sqrt(_dot(d, d))
    d = (d[0] / ln, d[1] / ln, d[2] / ln)
    xs = [_witness_coord(by_id, w, d) for w in ws]
    if None in xs:
        return                                   # not judged (never guessed)
    meas = [abs(xs[i + 1] - xs[i]) for i in range(len(segs))]
    for i in judged:
        v = _seg_value(segs[i], bool(_seg_flags(segs[i]) & SEG_LOCKED))
        if v is not None and abs(v - meas[i]) > ON_PLANE_TOL:
            add(ERROR, "CG10", eid, cls,
                f"dimension {eid} stores {v:.6g} ft on segment {i}, but its "
                f"witnesses are {meas[i]:.6g} ft apart: the dimension "
                f"contradicts the geometry it measures",
                value=v, measured=meas[i])
    eq = [meas[i] for i, s in enumerate(segs) if _seg_flags(s) & SEG_EQ]
    if len(eq) >= 2 and max(eq) - min(eq) > ON_PLANE_TOL:
        add(ERROR, "CG10", eid, cls,
            f"EQ dimension {eid} spans unequal gaps "
            f"({', '.join(f'{x:.6g}' for x in eq)} ft)")


def _family_params(by_id, fam_id) -> Optional[List[int]]:
    """The parameter ids a ``Family`` element lists in ``m_familyParams``, or
    None when ``fam_id`` is not a decoded ``Family`` (#956)."""
    try:
        tgt = by_id.get(int(fam_id))
    except (TypeError, ValueError):
        return None
    if tgt is None or tgt[0] != "Family":
        return None
    out = []
    for q in _val(tgt[1].get("m_familyParams")).get("m_params") or []:
        if isinstance(q, dict):
            try:
                out.append(int(q.get("m_paramId", -1)))
            except (TypeError, ValueError):
                continue
    return out


def _param_ids(obj: Dict[str, Any]) -> List[int]:
    return [int(s.get("m_paramId", -1)) for s in obj.get("m_ArrSegInfo") or []
            if isinstance(s, dict) and int(s.get("m_paramId", -1)) >= 0]


def check_doc(doc: Any) -> List[Dict[str, Any]]:
    """The law over an in-memory ``FamilyDoc`` -- the cheapest place to catch
    it, before a single byte is written."""
    return check_graph(((e.elem_id, e.class_name, e.obj,
                         getattr(e, "header", None))
                        for e in getattr(doc, "elements", [])))


def check_file(path: str, unit: int = 0) -> List[Dict[str, Any]]:
    """The law over a WRITTEN ``.rfa`` / ``.rft``.

    Decoding the file rather than trusting the builder is the point: it is the
    same instrument a user's file can be run through.  Read under the file's
    OWN release (a 2025 file's framing is not 2026's), as every instrument is.

    ``unit`` = the document unit judged: 0 = the family itself (the default);
    a nested family's content document is its own unit (:func:`nested_units`),
    judged without CG8 (instance locks live in the host), and with the host's
    shared parameters as label targets its family declares (CG5, #956).
    """
    from contextlib import ExitStack
    from ..global_framing import enter_own_release

    with ExitStack() as st:
        enter_own_release(st, path)
        return _check_file(path, unit)


def nested_units(path: str) -> Dict[str, int]:
    """``{content-document GUID: unit}`` of every nested family document a
    WRITTEN file carries (unit 0, the family itself, excluded)."""
    from contextlib import ExitStack
    from ..families import FamilyIndex
    from ..global_framing import enter_own_release

    with ExitStack() as st:
        enter_own_release(st, path)
        idx = FamilyIndex(path)
        return {g: u for g, u in idx.unit_by_guid.items() if u != 0}


def _check_file(path: str, unit: int = 0) -> List[Dict[str, Any]]:
    from ..families import FamilyIndex
    from ..objects import ObjectDecoder

    idx = FamilyIndex(path)
    dec = ObjectDecoder(idx.schema)
    recs = idx.unit_records(unit)
    tuples: List[Tuple[int, str, Dict[str, Any], Optional[Dict[str, Any]]]] = []
    for cls in FILE_CLASSES:
        for eid in idx.ids_of_class(unit, cls):
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
    inst = _instance_planes(idx, recs, tuples) if unit == 0 else {}
    shared = (idx.ids_of_class(0, HOST_SHARED_PARAM_CLASS) if unit != 0 else ())
    return check_graph(tuples, universe=recs.get(102, {}).keys(),
                       instance_planes=inst, host_shared_params=shared)


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


def judged_instance_locks(path: str) -> List[Dict[str, Any]]:
    """What CG8 judges in a WRITTEN file: one row per instance lock whose
    child reference resolved -- ``{lock, instance, tag, plane, elevation}``,
    ``elevation`` True when the host plane is horizontal (the lock holds the
    instance's HEIGHT, #940).  A lock missing here was not judged."""
    from contextlib import ExitStack
    from ..families import FamilyIndex
    from ..global_framing import enter_own_release
    from ..objects import ObjectDecoder

    with ExitStack() as st:
        enter_own_release(st, path)
        idx = FamilyIndex(path)
        dec = ObjectDecoder(idx.schema)
        recs = idx.unit_records(0)
        tuples, planes = [], {}
        for cls in ("Alignment", "RefPlane"):
            for eid in idx.ids_of_class(0, cls):
                r = recs.get(102, {}).get(eid)
                o = dec.decode_record(r.class_id, r.payload) if r is not None else None
                if o is None:
                    continue
                if cls == "Alignment":
                    tuples.append((int(eid), cls, o.value or {}, None))
                else:
                    planes[int(eid)] = plane_of_any(cls, o.value or {})
        inst = _instance_planes(idx, recs, tuples)
    out: List[Dict[str, Any]] = []
    for eid, _cls, obj, _h in tuples:
        # the SAME selection CG8 judges by (#949 review), never a re-derivation
        pick = cg8_pick(_witness_grefs(obj), planes.get, inst)
        if pick is None:
            continue
        pid, (_p0, n), iid, tag, _placed = pick
        out.append({"lock": eid, "instance": iid, "tag": tag, "plane": pid,
                    "elevation": abs(abs(n[2]) - 1.0) <= PARALLEL_TOL})
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

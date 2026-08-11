"""rvt.famgen.constraint_law -- THE CONSTRAINT-GRAPH LAW, promoted from a
desktop failure (#689).

WHY THIS EXISTS.  On 2026-08-11 the owner clicked the extrusion in a generated
panelboard and Revit failed.  The file validated 0 errors, so no instrument we
had said anything was wrong.  Inspecting it showed the constraint graph was
authored in ONE DIRECTION ONLY: four ``Alignment``s and two ``LinearDimString``s
named the elements they constrain, and every one of those elements carried
``m_constrInfo == []`` -- denying it was constrained by anything.

That is an INTERNAL INCONSISTENCY, and internal inconsistency is exactly what a
validator can catch WITHOUT Revit.  This module is that check.  The point is
the pattern, not the one bug: every desktop failure whose cause turns out to be
a self-contradiction in the file becomes a law here, and then it can never
reach a user again.  It is the same move the corpus laws D1-D5 and the 0x0f3f
footer made.

WHAT IT IS NOT.  A file that passes this law is not thereby correct in Revit
(hard rule 4).  This catches contradictions, not omissions we have not thought
of, and it can say nothing about whether Revit's solver LIKES a consistent
graph.  It only guarantees we never ship this particular species of broken
again.

Territory: famgen (new module).  Reads documents and written .rfa files; edits
nothing.  Deliberately NOT inside ``validate.py`` (a hot shared file) -- it is
written to be promoted there once it has earned it.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Classes that CONSTRAIN other elements.  Each owes a back-edge to every
#: element its witnesses name.
CONSTRAINING_CLASSES = ("Alignment", "LinearDimString")

#: Severity names, matching the validator's own vocabulary.
ERROR = "error"
WARNING = "warning"


def _witness_targets(obj: Dict[str, Any]) -> List[int]:
    """Element ids a constraint's witness references name."""
    out: List[int] = []
    for w in obj.get("m_witnessRefs") or []:
        ptr = (w or {}).get("m_pWitnessRef") or {}
        val = ptr.get("value") if isinstance(ptr, dict) else None
        gref = (val or {}).get("m_geomRef") if isinstance(val, dict) else None
        if isinstance(gref, dict):
            eid = int(gref.get("m_elemId", -1))
            if eid > 0 and eid not in out:
                out.append(eid)
    return out


def _constr_ids(obj: Dict[str, Any]) -> List[int]:
    """Constraint ids an element's ``m_constrInfo`` lists.  Tolerates both the
    correct pointer-wrapped form and a bare inline dict, because reading must
    not be the thing that breaks."""
    out: List[int] = []
    for entry in obj.get("m_constrInfo") or []:
        if not isinstance(entry, dict):
            continue
        v = entry.get("value") if "ptr_class" in entry else entry
        cid = int((v or {}).get("m_constrId", -1))
        if cid > 0:
            out.append(cid)
    return out


def check_graph(elements: Iterable[Tuple[int, str, Dict[str, Any]]]
                ) -> List[Dict[str, Any]]:
    """The law, over ``(elem_id, class_name, obj)`` triples.

    Two directions, both required:

    * **forward**  every element a constraint's witnesses name must exist.
    * **backward** every element a constraint names must list that constraint
      in ``m_constrInfo``.  THIS is the one that was silently violated by every
      family this engine has written.

    Returns findings; empty means the graph is coherent.
    """
    by_id: Dict[int, Tuple[str, Dict[str, Any]]] = {
        int(eid): (cls, obj) for eid, cls, obj in elements}
    findings: List[Dict[str, Any]] = []
    constrains: Dict[int, List[int]] = {}      # element -> constraints naming it

    for eid, (cls, obj) in sorted(by_id.items()):
        if cls not in CONSTRAINING_CLASSES:
            continue
        targets = _witness_targets(obj)
        if not targets:
            findings.append({
                "severity": WARNING, "rule": "CG3", "element": eid,
                "class": cls,
                "message": f"{cls} {eid} constrains nothing: it has no witness "
                           f"references, so it is inert"})
        for t in targets:
            constrains.setdefault(t, []).append(eid)
            if t not in by_id:
                findings.append({
                    "severity": ERROR, "rule": "CG1", "element": eid,
                    "class": cls,
                    "message": f"{cls} {eid} references element {t}, which is "
                               f"not in the document"})

    for target, constraint_ids in sorted(constrains.items()):
        if target not in by_id:
            continue
        cls, obj = by_id[target]
        listed = set(_constr_ids(obj))
        missing = [c for c in constraint_ids if c not in listed]
        if missing:
            findings.append({
                "severity": ERROR, "rule": "CG2", "element": target,
                "class": cls, "missing": missing,
                "message": (
                    f"{cls} {target} is constrained by {missing} but its "
                    f"m_constrInfo does not list them: the constraint graph is "
                    f"authored in one direction only. Revit resolves an "
                    f"element's constraint set when the element is selected, "
                    f"and an empty set on a constrained element is a "
                    f"contradiction (desktop failure 2026-08-11, #689)")})

    # a back-edge naming a constraint that is not one
    for eid, (cls, obj) in sorted(by_id.items()):
        for cid in _constr_ids(obj):
            if cid not in by_id:
                findings.append({
                    "severity": ERROR, "rule": "CG4", "element": eid,
                    "class": cls,
                    "message": f"{cls} {eid} lists constraint {cid}, which is "
                               f"not in the document"})
            elif by_id[cid][0] not in CONSTRAINING_CLASSES:
                findings.append({
                    "severity": ERROR, "rule": "CG4", "element": eid,
                    "class": cls,
                    "message": f"{cls} {eid} lists {cid} as a constraint, but "
                               f"{cid} is a {by_id[cid][0]}, which does not "
                               f"constrain anything"})
    return findings


def check_doc(doc: Any) -> List[Dict[str, Any]]:
    """The law over an in-memory ``FamilyDoc`` -- the cheapest place to catch
    it, before a single byte is written."""
    return check_graph((e.elem_id, e.class_name, e.obj)
                       for e in getattr(doc, "elements", []))


def check_file(path: str) -> List[Dict[str, Any]]:
    """The law over a WRITTEN ``.rfa`` / ``.rft``.

    Decoding the file rather than trusting the builder is the point: it is the
    same instrument a user's file can be run through, and it would have caught
    the panel that failed on the owner's desktop.
    """
    from ..families import FamilyIndex
    from ..objects import ObjectDecoder

    idx = FamilyIndex(path)
    dec = ObjectDecoder(idx.schema)
    recs = idx.unit_records(0)
    triples: List[Tuple[int, str, Dict[str, Any]]] = []
    for cls in set(CONSTRAINING_CLASSES) | {"CurveElem", "RefPlane",
                                            "ExtrusionElem", "GenericForm",
                                            "VarSketch"}:
        for eid in idx.ids_of_class(0, cls):
            r = recs.get(102, {}).get(eid)
            if r is None:
                continue
            o = dec.decode_record(r.class_id, r.payload)
            if o is not None:
                triples.append((int(eid), cls, o.value or {}))
    return check_graph(triples)


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

"""rvt.famgen.conformance -- THE CORPUS ORACLE: what Autodesk's own family
documents ALWAYS do, and where ours diverge.

WHY.  Every bug found on 2026-08-11 cost a round-trip through the owner's
desktop: build, send, click, fail, diagnose.  That does not scale and it is
not a good use of a person.  But most of those bugs were not subtle -- they
were our files doing something no Autodesk-born family document ever does
(``m_constrInfo == []`` on a constrained element being the sharpest example).

That class of bug is findable WITHOUT Revit, by asking a corpus of born files
what they invariably do and checking our output against it.  With Revit's 108
default templates in quarantine we have such a corpus, and it has been used
for exactly one question (category ids) when it can answer hundreds.

WHAT AN INVARIANT IS HERE.  For each (class, field) seen in the corpus:

  ALWAYS_EMPTY      every born specimen has it empty/absent  -> ours should too
  ALWAYS_PRESENT    every born specimen has it non-empty     -> ours must not
                                                                leave it empty
  CONSTANT          every born specimen carries one value    -> ours should
                                                                match it

A divergence is a QUESTION, not a verdict: templates are one species of family
document, and a field a template never fills may be one a real family fills
legitimately.  So findings are ranked, never auto-fixed, and the report says
how many specimens back each one.  The value is that it turns "click it and
see" into a list of specific, pre-answered suspicions.

WHAT IT CANNOT DO (hard rule 4).  Conformance to a corpus is not acceptance by
Revit.  This narrows where to look; it never certifies.

PROVENANCE / RULE 3.  Reads quarantined templates, emits only STATISTICS about
field shapes -- never their content.  A constant value is carried only when it
is a scalar law (an int/bool/empty-string), never geometry, never a string
that could be authored content.
"""
from __future__ import annotations

import glob
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

#: Kinds of scalar a CONSTANT invariant may carry.  Anything else (a float,
#: a long string, a nested structure) is a shape we count but never quote --
#: that keeps this a law-mining instrument, not a content copier.
_QUOTABLE = (bool, int)

#: Classes worth checking: the ones famgen actually authors.  Restricting the
#: sweep keeps the report about OUR output rather than about Revit at large.
DEFAULT_CLASSES = (
    "Family", "ParamElemFamily", "RefPlane", "CurveElem", "VarSketch",
    "SketchPlane", "ExtrusionElem", "LinearDimString", "Alignment",
    "FamilySymbol", "GStyleElem", "DBView",
)


def _emptyish(v: Any) -> bool:
    return v is None or v == [] or v == {} or v == ""


def _shape(v: Any) -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return f"bool:{v}"
    if isinstance(v, int):
        return f"int:{v}"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "str:empty" if v == "" else "str"
    if isinstance(v, list):
        return "list:empty" if not v else "list"
    if isinstance(v, dict):
        return "dict:empty" if not v else "dict"
    return type(v).__name__


class Oracle:
    """Field-shape statistics per class, accumulated over born specimens."""

    def __init__(self) -> None:
        # class -> field -> shape -> count
        self.stats: Dict[str, Dict[str, Dict[str, int]]] = {}
        self.specimens: Dict[str, int] = {}      # class -> elements seen
        self.files = 0

    def observe(self, class_name: str, obj: Dict[str, Any]) -> None:
        cls = self.stats.setdefault(class_name, {})
        self.specimens[class_name] = self.specimens.get(class_name, 0) + 1
        for field, value in (obj or {}).items():
            cls.setdefault(field, {})
            s = _shape(value)
            cls[field][s] = cls[field].get(s, 0) + 1

    # -- the derived invariants ------------------------------------------
    def invariants(self, *, min_specimens: int = 5) -> Dict[str, Dict[str, Dict[str, Any]]]:
        out: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for cls, fields in self.stats.items():
            n = self.specimens.get(cls, 0)
            if n < min_specimens:
                continue
            per: Dict[str, Dict[str, Any]] = {}
            for field, shapes in fields.items():
                seen = sum(shapes.values())
                if seen < n:                 # field absent on some specimens
                    continue
                empties = sum(c for s, c in shapes.items()
                              if s in ("none", "list:empty", "dict:empty",
                                       "str:empty"))
                if empties == seen:
                    per[field] = {"invariant": "ALWAYS_EMPTY", "specimens": seen}
                elif empties == 0:
                    rec: Dict[str, Any] = {"invariant": "ALWAYS_PRESENT",
                                           "specimens": seen}
                    if len(shapes) == 1:
                        only = next(iter(shapes))
                        if only.startswith(("int:", "bool:")):
                            rec["invariant"] = "CONSTANT"
                            rec["value"] = only
                    per[field] = rec
            if per:
                out[cls] = per
        return out


def mine(directory: str, *, classes: Iterable[str] = DEFAULT_CLASSES,
         limit: Optional[int] = None) -> Oracle:
    """Accumulate field-shape statistics over every ``.rft`` in ``directory``."""
    from ..families import FamilyIndex
    from ..objects import ObjectDecoder

    oracle = Oracle()
    wanted = set(classes)
    paths = sorted(glob.glob(os.path.join(directory, "*.rft")))
    if limit:
        paths = paths[:limit]
    for path in paths:
        try:
            idx = FamilyIndex(path)
            dec = ObjectDecoder(idx.schema)
            recs = idx.unit_records(0)
        except Exception:                                         # noqa: BLE001
            continue
        oracle.files += 1
        for cls in wanted:
            try:
                ids = idx.ids_of_class(0, cls)
            except Exception:                                     # noqa: BLE001
                continue
            for eid in ids:
                r = recs.get(102, {}).get(eid)
                if r is None:
                    continue
                try:
                    o = dec.decode_record(r.class_id, r.payload)
                except Exception:                                 # noqa: BLE001
                    continue
                if o is not None:
                    oracle.observe(cls, o.value or {})
    return oracle


def check_doc(doc: Any, invariants: Dict[str, Dict[str, Dict[str, Any]]],
              *, min_specimens: int = 5) -> List[Dict[str, Any]]:
    """Where ``doc`` diverges from what born family documents always do.

    Findings are ranked by how many specimens back the invariant -- an
    invariant seen on 400 born elements is a much sharper question than one
    seen on 6.
    """
    findings: List[Dict[str, Any]] = []
    for el in getattr(doc, "elements", []):
        rules = invariants.get(el.class_name)
        if not rules:
            continue
        for field, rule in rules.items():
            if rule["specimens"] < min_specimens:
                continue
            if field not in el.obj:
                continue
            ours = el.obj.get(field)
            kind = rule["invariant"]
            if kind == "ALWAYS_PRESENT" and _emptyish(ours):
                findings.append({
                    "severity": "question", "class": el.class_name,
                    "element": el.elem_id, "field": field,
                    "specimens": rule["specimens"],
                    "message": (f"{el.class_name}.{field} is empty in our "
                                f"file, but non-empty on all "
                                f"{rule['specimens']} born specimens")})
            elif kind == "ALWAYS_EMPTY" and not _emptyish(ours):
                findings.append({
                    "severity": "note", "class": el.class_name,
                    "element": el.elem_id, "field": field,
                    "specimens": rule["specimens"],
                    "message": (f"{el.class_name}.{field} is filled in our "
                                f"file, but empty on all "
                                f"{rule['specimens']} born specimens")})
            elif kind == "CONSTANT":
                want = rule.get("value", "")
                if _shape(ours) != want:
                    findings.append({
                        "severity": "question", "class": el.class_name,
                        "element": el.elem_id, "field": field,
                        "specimens": rule["specimens"],
                        "message": (f"{el.class_name}.{field} is {_shape(ours)} "
                                    f"in our file; all {rule['specimens']} born "
                                    f"specimens carry {want}")})
    findings.sort(key=lambda f: -f["specimens"])
    return findings


def summarise(findings: List[Dict[str, Any]], *, top: int = 20) -> str:
    if not findings:
        return "corpus conformance: no divergences"
    # collapse per (class, field) -- one line per law, not per element
    seen: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for f in findings:
        key = (f["class"], f["field"])
        row = seen.setdefault(key, {**f, "count": 0})
        row["count"] += 1
    rows = sorted(seen.values(), key=lambda r: (-r["specimens"], -r["count"]))
    lines = [f"corpus conformance: {len(rows)} divergent field(s) "
             f"over {len(findings)} element(s)"]
    for r in rows[:top]:
        lines.append(f"  [{r['specimens']:>4} specimens x{r['count']:>3} ours] "
                     f"{r['message']}")
    return "\n".join(lines)

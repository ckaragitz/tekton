"""rvt.famgen.conformance -- THE CORPUS ORACLE: what Autodesk's own family
documents ALWAYS do, and where ours diverge.

WHY.  Every bug found on 2026-08-11 cost a round-trip through the owner's
desktop: build, send, click, fail, diagnose.  That does not scale and it is
not a good use of a person.  But most of those bugs were not subtle -- they
were our files doing something no Autodesk-born family document ever does
(``m_constrInfo == []`` on a constrained element being the sharpest example).

That class of bug is findable WITHOUT Revit, by asking a corpus of born files
what they invariably do and checking our output against it.  A born family
document is a ``.rft`` template OR a Revit-born ``.rfa`` family: either corpus
(Revit's default templates, the quarantined reference families) is mined the
same way, each file read inside its OWN release (#796).

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

READ EVERY FILE IN ITS OWN RELEASE, AND SAY WHAT FAILED (#796).  The first
cut opened each template under the session's native framing and swallowed
the error: on a corpus of 2025 families it mined 0 files and reported nothing
-- an instrument defect, not an engine one.  :func:`iter_objects` enters the
file's own release (``global_framing.enter_own_release``) and :func:`mine`
counts every file it could not decode (:attr:`Oracle.failed`); its
:meth:`Oracle.summary` states ``0/N`` when that is what happened.

PROVENANCE / RULE 3.  Reads quarantined born files, emits only STATISTICS about
field shapes -- never their content.  File paths stay in memory
(:attr:`Oracle.failures`) and are never serialized.  A constant value is
carried only when it is a scalar law (an int/bool/empty-string), never
geometry, never a string that could be authored content.
"""
from __future__ import annotations

import collections
import glob
import os
from contextlib import ExitStack
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


def _shape(v: Any, field: str = "") -> str:
    if v is None:
        return "none"
    if isinstance(v, bool):
        return f"bool:{v}"
    if isinstance(v, int):
        # An ID is never a LAW: born templates number their elements from 17,
        # ours from 1000, and "every template's m_famId is 17" is a fact about
        # template id allocation, not about the format (steer #765 battery
        # round 3 -- every artefact failed on it).  Id-shaped fields count for
        # presence only.
        if field.endswith(("Id", "Ids", "Idx")):
            return "int"
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

    #: the counters :meth:`to_json` carries (never a path)
    _COUNTERS = ("files", "attempted", "failed", "fallbacks", "undecoded_records",
                 "partial_records", "missing_records")

    def __init__(self) -> None:
        # class -> field -> shape -> count
        self.stats: Dict[str, Dict[str, Dict[str, int]]] = {}
        self.specimens: Dict[str, int] = {}      # class -> elements seen
        self.files = 0                           # files DECODED and observed
        self.attempted = 0                       # files mine() tried
        self.failed = 0                          # files that did not decode
        self.fallbacks = 0                       # decoded via a fallback rung
        self.undecoded_records = 0               # records that did not decode
        self.partial_records = 0                 # decoded only partly (not ``clean``)
        self.missing_records = 0                 # class ids with no seq-102 record
        #: the classes :func:`mine` was asked for (``classes_without_specimens``)
        self.requested: Tuple[str, ...] = ()
        self.failure_types: Dict[str, int] = collections.Counter()
        self.releases: Dict[str, int] = collections.Counter()
        #: ``[(path, "Type: message")]`` -- IN MEMORY ONLY, never serialized
        #: (a corpus path names third-party content, rule 3 / rule 6)
        self.failures: List[Tuple[str, str]] = []

    def classes_without_specimens(self) -> List[str]:
        """Requested classes the corpus never showed (their rules cannot exist)."""
        return [c for c in self.requested if not self.specimens.get(c)]

    def summary(self) -> str:
        """One line that never hides a silent zero."""
        inv = self.invariants()
        n_inv = sum(len(v) for v in inv.values())
        line = (f"mined {self.files}/{self.attempted} family files "
                f"({self.failed} failed")
        if self.failure_types:
            line += " -- " + ", ".join(f"{k} x{v}"
                                       for k, v in sorted(self.failure_types.items()))
        line += (f"; {self.fallbacks} via a fallback rung; "
                 f"{self.undecoded_records} undecoded, {self.partial_records} partly "
                 f"decoded (both left out), {self.missing_records} missing records); "
                 f"{len(self.specimens)} classes seen, "
                 f"{len(inv)} with invariants, {n_inv} invariants")
        empty = self.classes_without_specimens()
        if empty:
            line += f"; 0 specimens of {', '.join(empty)}"
        if self.attempted and not self.files:
            line = "NOTHING MINED: " + line
        return line

    def to_json(self) -> Dict[str, Any]:
        """Statistics + counters, never a path (the cache form)."""
        return {"stats": self.stats, "specimens": dict(self.specimens),
                "counters": {k: getattr(self, k) for k in self._COUNTERS},
                "failure_types": dict(self.failure_types),
                "releases": dict(self.releases), "requested": list(self.requested)}

    @classmethod
    def from_json(cls, d: Dict[str, Any]) -> "Oracle":
        o = cls()
        o.stats = {c: {f: dict(sh) for f, sh in fs.items()}
                   for c, fs in (d.get("stats") or {}).items()}
        o.specimens = dict(d.get("specimens") or {})
        for k, v in (d.get("counters") or {}).items():
            if k in cls._COUNTERS:
                setattr(o, k, int(v))
        o.failure_types = collections.Counter(d.get("failure_types") or {})
        o.releases = collections.Counter(d.get("releases") or {})
        o.requested = tuple(d.get("requested") or ())
        return o

    def observe(self, class_name: str, obj: Dict[str, Any]) -> None:
        cls = self.stats.setdefault(class_name, {})
        self.specimens[class_name] = self.specimens.get(class_name, 0) + 1
        for field, value in (obj or {}).items():
            cls.setdefault(field, {})
            s = _shape(value, field)
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


def iter_objects(path: str, classes: Iterable[str] = DEFAULT_CLASSES
                 ) -> Tuple[Optional[str], List[Tuple[int, str, Dict[str, Any]]],
                            Dict[str, int]]:
    """Decode every element of ``classes`` in ``path``'s family document
    (unit 0, seq 102), read inside the file's OWN release.

    Returns ``(release_note, [(element id, class, decoded fields)], counters)``:
    ``release_note`` is None when the file's own schema resolved its release,
    else the sentence naming the fallback rung
    (``global_framing.enter_own_release``); ``counters`` counts what did NOT
    decode instead of skipping it silently: ``undecoded_records`` (the decoder
    raised), ``partial_records`` (it returned an object that is not ``clean``
    -- errors, or bytes left unconsumed: such a record is LEFT OUT, because a
    field its partial decode lacks would read as "absent" on the corpus side
    and go unchecked on ours) and ``missing_records``.  A file that cannot be
    opened at all raises -- the caller counts it."""
    from ..families import FamilyIndex
    from ..global_framing import enter_own_release
    from ..objects import ObjectDecoder

    counters = {"undecoded_records": 0, "partial_records": 0, "missing_records": 0}
    out: List[Tuple[int, str, Dict[str, Any]]] = []
    with ExitStack() as st:
        note = enter_own_release(st, path)
        idx = FamilyIndex(path)
        dec = ObjectDecoder(idx.schema)
        recs = idx.unit_records(0).get(102, {})
        for cls in dict.fromkeys(classes):          # stable order, no repeats
            for eid in idx.ids_of_class(0, cls):
                r = recs.get(eid)
                if r is None:
                    counters["missing_records"] += 1
                    continue
                try:
                    o = dec.decode_record(r.class_id, r.payload)
                except Exception:                                 # noqa: BLE001
                    counters["undecoded_records"] += 1
                    continue
                if o is None:
                    continue
                if not o.clean:
                    counters["partial_records"] += 1
                    continue
                out.append((eid, cls, o.value or {}))
    return note, out, counters


def corpus_paths(directory: str, *, patterns: Iterable[str] = ("*.rfa", "*.rft"),
                 limit: Optional[int] = None) -> List[str]:
    """The born family documents :func:`mine` reads: every match of
    ``patterns`` in ``directory`` (not recursive), de-duplicated, sorted."""
    paths = sorted({p for pat in patterns
                    for p in glob.glob(os.path.join(directory, pat))
                    if os.path.isfile(p)})
    return paths[:limit] if limit else paths


def mine(directory: str, *, classes: Iterable[str] = DEFAULT_CLASSES,
         limit: Optional[int] = None,
         patterns: Iterable[str] = ("*.rfa", "*.rft")) -> Oracle:
    """Accumulate field-shape statistics over every born family document
    (``.rfa`` families and ``.rft`` templates) in ``directory``.

    Each file is read inside its OWN release (#796: read under the session's
    framing, a 2025 corpus mined 0 files and said nothing).  A file that does
    not decode is COUNTED (``Oracle.failed``, ``Oracle.failure_types``), never
    silently dropped; :meth:`Oracle.summary` states the ratio."""
    from .. import versions as V

    oracle = Oracle()
    classes = tuple(dict.fromkeys(classes))
    oracle.requested = classes
    for path in corpus_paths(directory, patterns=patterns, limit=limit):
        oracle.attempted += 1
        try:
            note, objs, counters = iter_objects(path, classes)
        except Exception as e:                                    # noqa: BLE001
            oracle.failed += 1
            oracle.failure_types[type(e).__name__] += 1
            oracle.failures.append((path, f"{type(e).__name__}: {e}"[:240]))
            continue
        oracle.files += 1
        oracle.fallbacks += note is not None
        oracle.undecoded_records += counters["undecoded_records"]
        oracle.partial_records += counters["partial_records"]
        oracle.missing_records += counters["missing_records"]
        try:
            year = V.detect_release(path)
        except Exception:                                         # noqa: BLE001
            year = None
        oracle.releases[str(year)] += 1
        for _eid, cls, obj in objs:
            oracle.observe(cls, obj)
    return oracle


class _Element:
    """The three attributes :func:`check_doc` reads, for a decoded record."""
    __slots__ = ("elem_id", "class_name", "obj")

    def __init__(self, elem_id: int, class_name: str, obj: Dict[str, Any]) -> None:
        self.elem_id, self.class_name, self.obj = elem_id, class_name, obj


class _Decoded:
    def __init__(self, elements: List[_Element]) -> None:
        self.elements = elements


def check_file(path: str, invariants: Dict[str, Dict[str, Dict[str, Any]]], *,
               min_specimens: int = 5, stats: Optional[Dict[str, Any]] = None,
               classes: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
    """:func:`check_doc` over a WRITTEN family file, decoded inside its own
    release -- the bytes that ship, not the builder's in-memory document (a
    2025 / 2024 port layer adds fields the in-memory document never had).

    ``stats`` (optional dict) receives ``elements`` (decoded elements of the
    checked classes), ``rules_evaluated`` (rule x element checks that ran),
    ``undecoded_records`` / ``partial_records`` (records of the checked
    classes left unchecked) and ``release_note``: an instrument that evaluated
    0 rules, or skipped records, is not a clean pass, and the caller can say
    so."""
    wanted = tuple(classes) if classes is not None else tuple(invariants)
    note, objs, counters = iter_objects(path, wanted)
    doc = _Decoded([_Element(eid, cls, obj) for eid, cls, obj in objs])
    found = check_doc(doc, invariants, min_specimens=min_specimens, stats=stats)
    if stats is not None:
        stats["undecoded_records"] = counters["undecoded_records"]
        stats["partial_records"] = counters["partial_records"]
        stats["release_note"] = note
    return found


def check_doc(doc: Any, invariants: Dict[str, Dict[str, Dict[str, Any]]],
              *, min_specimens: int = 5,
              stats: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Where ``doc`` diverges from what born family documents always do.

    Findings are ranked by how many specimens back the invariant -- an
    invariant seen on 400 born elements is a much sharper question than one
    seen on 6.  ``stats`` (optional dict) receives ``elements`` and
    ``rules_evaluated`` so an inert check (0 rules ran) is visible.
    """
    findings: List[Dict[str, Any]] = []
    n_el = n_rules = 0
    for el in getattr(doc, "elements", []):
        rules = invariants.get(el.class_name)
        if not rules:
            continue
        n_el += 1
        for field, rule in rules.items():
            if rule["specimens"] < min_specimens:
                continue
            if field not in el.obj:
                continue
            n_rules += 1
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
                if _shape(ours, field) != want:
                    findings.append({
                        "severity": "question", "class": el.class_name,
                        "element": el.elem_id, "field": field,
                        "specimens": rule["specimens"],
                        "message": (f"{el.class_name}.{field} is {_shape(ours)} "
                                    f"in our file; all {rule['specimens']} born "
                                    f"specimens carry {want}")})
    findings.sort(key=lambda f: -f["specimens"])
    if stats is not None:
        stats["elements"] = n_el
        stats["rules_evaluated"] = n_rules
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

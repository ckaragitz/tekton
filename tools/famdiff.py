"""famdiff -- THE GENERAL LAW-FINDER: diff two Revit documents field by
field, in decoded object space, and rank what differs.

WHY THIS EXISTS.  Every format law this project has found -- the family-view
law, the object style, the retouch styles, the Plan/RCP visibility bit --
was found the same way: decode a file where the behaviour works, decode one
where it does not, and compare.  Four times in one afternoon that comparison
was hand-written as throwaway Python, explored, and thrown away.  The
knowledge was never missing; the INSTRUMENT was.  We carry every class and
every field of the format already (each file ships its own schema in
``Formats/Latest``), so the comparison is computable -- this is it.

WHAT IT COMPUTES

* pairs elements between the two documents by CLASS and ROLE, never by id
  (ids are per-file and pairing on them is meaningless);
* diffs each pair recursively, into the seq-103 geometry rep too;
* classifies every leaf difference so the noise disappears on its own:
  - ``id`` -- both sides hold an element id that EXISTS in their own file
    (our 1075 vs their 17866 is not a finding, it is renumbering),
  - ``float`` -- equal within 1e-9 (3.999999999999994 vs 4.0),
  - ``real`` -- everything left, which is the actual report;
* RANKS real differences by how many pairs of that class show them.  A
  difference present in EVERY pair is a candidate law.  One present in a
  minority tracks topology or one author's choice -- which is exactly the
  distinction that saved this project from "fixing" an edge-flag bit that
  two of three reference extrusions turned out to share with ours.

USAGE

    python tools/famdiff.py REFERENCE.rfa OURS.rfa
    python tools/famdiff.py a.rfa b.rfa --class DBViewPlan --class Viewer
    python tools/famdiff.py a.rfa b.rfa --rep --class ExtrusionElem
    python tools/famdiff.py a.rfa b.rfa --json out/famdiff.json --all

Read-only: it never writes to the inputs.
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

FLOAT_EPS = 1e-9

#: fields whose value is an element id BY DEFINITION -- comparing them across
#: two files is always renumbering noise.  The id-existence test below catches
#: most of these on its own; this list catches the ones pointing at elements
#: the other file does not have.
ID_FIELD_HINTS = ("id", "Id", "ID")


def _is_id_like(name: str) -> bool:
    return name.endswith("Id") or name.endswith("Ids") or name in ("m_id",)


class Doc:
    """One decoded document, indexed by class."""

    def __init__(self, path: str):
        from rvt.families import FamilyIndex
        self.path = path
        self.name = os.path.basename(path)
        self.fi = FamilyIndex(path)
        self.ids = set()
        self.by_class = collections.defaultdict(list)
        for eid, r in self.fi.unit_records(0).get(102, {}).items():
            self.ids.add(int(eid))
            self.by_class[self.fi.class_name(r.class_id)].append(int(eid))
        for lst in self.by_class.values():
            lst.sort()

    def value(self, eid: int, seq: int = 102):
        return self.fi.value(0, eid, seq)

    def rep(self, eid: int):
        r = self.fi.decode(0, eid, 103)
        return r.value if r is not None else None

    def role(self, eid: int) -> str:
        """A stable, id-free identity for an element, so the same view or
        the same form pairs up across two independently authored files."""
        v = self.value(eid) or {}
        name = v.get("m_viewName")
        if isinstance(name, str) and name:
            return name
        plan = v.get("m_planViewType")
        if plan is not None:
            return f"planViewType={plan}"
        cat = v.get("m_categoryId")
        if isinstance(cat, int) and cat < 0:
            return f"category={cat}"
        sym = ((v.get("m_symbolInfo") or {}).get("value") or {}).get("m_name")
        if isinstance(sym, str) and sym:
            return sym
        return ""


def classify(a, b, key: str, doc_a: Doc, doc_b: Doc) -> str:
    """'same' | 'float' | 'id' | 'real' for one leaf pair."""
    if a == b:
        return "same"
    if isinstance(a, bool) or isinstance(b, bool):
        return "real"
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        if isinstance(a, float) or isinstance(b, float):
            if a == b or (math.isfinite(a) and math.isfinite(b)
                          and abs(a - b) <= FLOAT_EPS * max(1.0, abs(a), abs(b))):
                return "float"
        ia, ib = int(a), int(b)
        # a live element id on BOTH sides, or an id-shaped field pointing at
        # something only one file has: renumbering, not a finding
        if ia in doc_a.ids and ib in doc_b.ids:
            return "id"
        if _is_id_like(key) and (ia in doc_a.ids or ib in doc_b.ids):
            return "id"
    return "real"


def walk(a, b, doc_a: Doc, doc_b: Doc, path: str = "", out=None, depth: int = 0):
    """Recursive field diff; appends (path, kind, a, b) for every leaf."""
    if out is None:
        out = []
    if depth > 14:
        return out
    if isinstance(a, dict) and isinstance(b, dict):
        pa, pb = a.get("ptr_class"), b.get("ptr_class")
        if pa != pb:
            out.append((path + "/ptr_class", "real", pa, pb))
        for k in sorted(set(a) | set(b)):
            if k == "pid":                      # per-file object numbering
                continue
            walk(a.get(k), b.get(k), doc_a, doc_b, f"{path}/{k}", out, depth + 1)
        return out
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append((path + "[len]", "real", len(a), len(b)))
        for i in range(min(len(a), len(b))):
            walk(a[i], b[i], doc_a, doc_b, f"{path}[{i}]", out, depth + 1)
        return out
    if type(a) is not type(b) and not (
            isinstance(a, (int, float)) and isinstance(b, (int, float))):
        out.append((path, "real", a, b))
        return out
    key = path.rsplit("/", 1)[-1].split("[")[0]
    kind = classify(a, b, key, doc_a, doc_b)
    if kind != "same":
        out.append((path, kind, a, b))
    return out


def pair_elements(doc_a: Doc, doc_b: Doc, cls: str):
    """[(eid_a, eid_b, role)] for one class, paired by role then by order."""
    ea, eb = list(doc_a.by_class.get(cls, [])), list(doc_b.by_class.get(cls, []))
    ra = collections.defaultdict(list)
    rb = collections.defaultdict(list)
    for e in ea:
        ra[doc_a.role(e)].append(e)
    for e in eb:
        rb[doc_b.role(e)].append(e)
    pairs, used_a, used_b = [], set(), set()
    for role in sorted(set(ra) & set(rb)):
        if not role:
            continue
        for x, y in zip(ra[role], rb[role]):
            pairs.append((x, y, role))
            used_a.add(x)
            used_b.add(y)
    rest_a = [e for e in ea if e not in used_a]
    rest_b = [e for e in eb if e not in used_b]
    for x, y in zip(rest_a, rest_b):
        pairs.append((x, y, ""))
    return pairs, len(ea), len(eb)


def diff_class(doc_a: Doc, doc_b: Doc, cls: str, with_rep: bool):
    pairs, na, nb = pair_elements(doc_a, doc_b, cls)
    findings = collections.defaultdict(list)      # path -> [(role, a, b)]
    for x, y, role in pairs:
        leaves = walk(doc_a.value(x), doc_b.value(y), doc_a, doc_b)
        if with_rep:
            leaves += walk(doc_a.rep(x), doc_b.rep(y), doc_a, doc_b, path="~rep")
        for path, kind, va, vb in leaves:
            if kind == "real":
                findings[path].append((role or f"{x}/{y}", va, vb))
    return {
        "class": cls,
        "count_a": na, "count_b": nb, "paired": len(pairs),
        "findings": [
            {"path": p,
             "pairs_affected": len(v), "pairs_total": len(pairs),
             "universal": len(v) == len(pairs) and len(pairs) > 0,
             "examples": [{"role": r, "a": _short(a), "b": _short(b)}
                          for r, a, b in v[:3]]}
            for p, v in sorted(findings.items(),
                               key=lambda kv: (-len(kv[1]), kv[0]))],
    }


def _short(v, limit: int = 120):
    s = v if isinstance(v, (int, float, bool, type(None))) else json.dumps(
        v, default=str)
    s = str(s)
    return s if len(s) <= limit else s[:limit] + "…"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Diff two Revit documents in decoded object space and "
                    "rank what differs (id renumbering and float noise are "
                    "classified away).")
    ap.add_argument("reference", help="the file where the behaviour WORKS")
    ap.add_argument("ours", help="the file where it does not")
    ap.add_argument("--class", dest="classes", action="append", default=[],
                    help="restrict to this class (repeatable); default = "
                         "every class both files carry")
    ap.add_argument("--rep", action="store_true",
                    help="also diff the seq-103 geometry rep (the B-rep)")
    ap.add_argument("--all", action="store_true",
                    help="report non-universal differences too (default: "
                         "only those present in EVERY paired element, i.e. "
                         "candidate laws)")
    ap.add_argument("--json", dest="json_out", help="write the full report")
    a = ap.parse_args(argv)

    doc_a, doc_b = Doc(a.reference), Doc(a.ours)
    classes = a.classes or sorted(set(doc_a.by_class) & set(doc_b.by_class))
    report = {"reference": doc_a.name, "ours": doc_b.name, "classes": []}
    for cls in classes:
        r = diff_class(doc_a, doc_b, cls, a.rep)
        if r["findings"]:
            report["classes"].append(r)

    print(f"=== famdiff  reference={doc_a.name}  ours={doc_b.name}")
    only_a = sorted(set(doc_a.by_class) - set(doc_b.by_class))
    only_b = sorted(set(doc_b.by_class) - set(doc_a.by_class))
    if only_a:
        print(f"  classes only in the REFERENCE: {', '.join(only_a)}")
    if only_b:
        print(f"  classes only in OURS          : {', '.join(only_b)}")
    shown = 0
    for r in report["classes"]:
        rows = [f for f in r["findings"] if a.all or f["universal"]]
        if not rows:
            continue
        print(f"\n-- {r['class']}  ({r['count_a']} vs {r['count_b']}, "
              f"{r['paired']} paired)")
        for f in rows:
            mark = "LAW " if f["universal"] else "    "
            print(f"  {mark}{f['path']}  [{f['pairs_affected']}/"
                  f"{f['pairs_total']} pairs]")
            ex = f["examples"][0]
            print(f"        ref: {ex['a']}")
            print(f"        our: {ex['b']}")
            shown += 1
    if not shown:
        print("\n  no differences of that kind -- the two agree on every "
              "paired element (after id and float classification)")
    else:
        print(f"\n  {shown} difference(s); LAW = present in every paired "
              f"element of its class, i.e. a candidate format law rather "
              f"than one author's choice or a topology artefact")
    if a.json_out:
        os.makedirs(os.path.dirname(os.path.abspath(a.json_out)), exist_ok=True)
        with open(a.json_out, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=1)
        print(f"  json -> {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

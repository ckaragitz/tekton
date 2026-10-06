"""profile_map_from_rfa -- PROPOSE a profile map from a user's own families (#876).

A library family's size parameters label its dimensions: its shared width labels a
dimension measured along x, its depth one along y, its height one along z.  This
tool reads which axis each SHARED length parameter labels across the user's
families (every ``LinearDimString`` segment whose ``m_paramId`` is that parameter,
measured along ``m_pDimLine.m_dirVec`` in the family's own coordinates) and proposes
the map ``make_family --profile-map`` takes: library parameter GUID -> the generated
family's parameter of the same role.

Our generated equipment is built Width along x, Depth along y, Height along z
(``rvt.famgen.geometry.box``); ``--targets`` names other roles for a family built
otherwise.  A parameter is proposed only when it is a LENGTH, labels an
axis-aligned dimension in at least ``--min-families`` families of the category, and
labels the SAME axis in at least ``--min-share`` of them, and only the axis's
PRIMARY parameter -- the one labelling it in the most families (a section's width
inside one family sizes a part, not the family); everything else is listed with the
reason, never guessed.  Run it per ``--category``: families of different categories
size along different conventions.  The proposal is a starting point the user reviews:
it is written only where they say -- never into this repository (rule 6: the repo is
public; the library's names and GUIDs are the user's) -- and this module holds no
library content of any kind.

USAGE
    python tools/profile_map_from_rfa.py MY_LIBRARY/ --category -2001040 -o my_map.json
    python tools/make_family.py transformer --kva 45 --param-profile my_profile.json \\
        --profile-map my_map.json -o out/x.rfa
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import sys
from contextlib import ExitStack
from typing import Any, Dict, Iterable, List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (os.path.join(_ROOT, "src"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

#: our generated equipment's roles: the axis a dimension is measured along -> the
#: parameter that sizes the family along it (``geometry.box``: width x, depth y, height z)
DEFAULT_TARGETS = {"x": "Width", "y": "Depth", "z": "Height"}
#: a dimension line within this of an axis is measured along that axis
_ALIGNED = 0.999


def axis_of(direction: Any) -> Optional[str]:
    """'x' / 'y' / 'z' for a dimension line along that axis (either sense), None
    for an oblique or unreadable one."""
    try:
        comps = [abs(float(c)) for c in direction][:3]
    except (TypeError, ValueError):
        return None
    if len(comps) != 3:
        return None
    best = max(range(3), key=lambda i: comps[i])
    return "xyz"[best] if comps[best] >= _ALIGNED else None


def read_labels(fi) -> Dict[int, collections.Counter]:
    """{parameter element id: Counter(axis)} for every dimension segment one opened
    family document labels with a parameter (``fi`` = a ``FamilyIndex``)."""
    out: Dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for eid, rec in fi.unit_records(0).get(102, {}).items():
        if fi.class_name(rec.class_id) != "LinearDimString":
            continue
        v = fi.value(0, eid) or {}
        line = ((v.get("m_pDimLine") or {}).get("value") or {})
        axis = axis_of(line.get("m_dirVec"))
        for seg in v.get("m_ArrSegInfo") or []:
            pid = seg.get("m_paramId") if isinstance(seg, dict) else None
            if isinstance(pid, int) and pid > 0:
                out[pid][axis or "oblique"] += 1
    return out


def read_family(path: str) -> Dict[str, Any]:
    """One ``.rfa``, read inside its OWN release: its category and, per SHARED
    parameter (by GUID), its name, spec and the axes its labelled dimensions run along."""
    from rvt import global_framing as GF
    from rvt.families import FamilyIndex
    import shared_params_from_rfa as SP
    with ExitStack() as stack:
        GF.enter_own_release(stack, path)
        fi = FamilyIndex(path)
        index = SP.read_index(fi)
        labels = read_labels(fi)
        guid_of: Dict[int, str] = {}
        for eid, rec in fi.unit_records(0).get(102, {}).items():
            if fi.class_name(rec.class_id) == "ParamElemExternal":
                key = ((fi.value(0, eid) or {}).get("m_externalParamKey") or {}).get("m_guidValue")
                if key:
                    guid_of[int(eid)] = str(key).lower()
    params = {p["guid"]: {"name": p["name"], "spec": p["spec"] or "", "axes": {}}
              for p in index["params"]}
    for pid, axes in labels.items():
        g = guid_of.get(pid)
        if g in params:
            params[g]["axes"] = dict(axes)
    return {"category": index["category"], "params": params}


def propose(families: Iterable[Dict[str, Any]], *, category: Optional[int] = None,
            targets: Optional[Dict[str, str]] = None, min_share: float = 0.8,
            min_families: int = 2) -> Tuple[Dict[str, str], List[Dict[str, Any]]]:
    """(map, report) from :func:`read_family` results.  Each family votes ONCE per
    parameter, for the axis most of that parameter's labelled segments run along in
    it; a parameter is proposed for the target of the winning axis when it is a
    length, at least ``min_families`` families vote, the winner holds at least
    ``min_share`` of the votes, and it is the axis's PRIMARY parameter -- the one
    labelling that axis in the most families (one parameter per axis; a tie is not
    guessed).  ``report`` lists every labelling parameter with the outcome and its
    reason."""
    targets = dict(DEFAULT_TARGETS if targets is None else targets)
    votes: Dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    meta: Dict[str, Dict[str, str]] = {}
    for fam in families:
        if category is not None and fam.get("category") != category:
            continue
        for guid, p in fam["params"].items():
            axes = collections.Counter(p.get("axes") or {})
            if not axes:
                continue
            meta.setdefault(guid, {"name": p["name"], "spec": p["spec"]})
            ranked = axes.most_common(2)
            # a family whose labels run equally along two axes votes for neither:
            # never guessed by insertion order
            votes[guid]["mixed" if len(ranked) > 1 and ranked[0][1] == ranked[1][1]
                        else ranked[0][0]] += 1
    mapping: Dict[str, str] = {}
    report: List[Dict[str, Any]] = []
    for guid in sorted(votes, key=lambda g: (meta[g]["name"], g)):
        v = votes[guid]
        n = sum(v.values())
        ranked = v.most_common(2)
        axis, top = ranked[0]
        if len(ranked) > 1 and ranked[1][1] == top:
            axis = "mixed"                      # families split evenly: never guessed
        row = {"guid": guid, "name": meta[guid]["name"], "families": n, "axes": dict(v),
               "axis": axis, "share": round(top / n, 3)}
        spec = meta[guid]["spec"]
        if ":length" not in spec:
            row["why"] = f"not a length ({spec.split(':')[-1] or 'no spec'})"
        elif axis == "oblique":
            row["why"] = "its dimensions are not along an axis"
        elif axis == "mixed":
            row["why"] = ("its families label it along two axes equally"
                          + (f" ({dict(v)})" if len(v) > 1 and "mixed" not in v else ""))
        elif n < min_families:
            row["why"] = f"labels a dimension in {n} family(ies), fewer than {min_families}"
        elif top / n < min_share:
            row["why"] = f"its families disagree on the axis ({dict(v)})"
        elif axis not in targets:
            row["why"] = f"no target parameter named for the {axis} axis"
        else:
            row["candidate"] = True
        report.append(row)
    # ONE parameter per axis: the one that labels it in the most families is the
    # family's size; a parameter labelling a part along the same axis in fewer (a
    # section's width inside one family) is not -- and a tie is not guessed
    by_axis: Dict[str, List[Dict[str, Any]]] = collections.defaultdict(list)
    for row in report:
        if row.pop("candidate", False):
            by_axis[row["axis"]].append(row)
    for axis, rows in by_axis.items():
        # ranked by the families labelling it along THIS axis (its votes), not by
        # every family it labels
        rows.sort(key=lambda r: -r["axes"][axis])
        top = rows[0]["axes"][axis]
        tied = [r for r in rows if r["axes"][axis] == top]
        for r in rows:
            if len(tied) > 1 and r["axes"][axis] == top:
                r["why"] = (f"{len(tied)} parameters label the {axis} axis in {top} families "
                            f"each: not guessed which is the family's size")
            elif r is rows[0]:
                mapping[r["guid"]] = targets[axis]
                r["target"] = targets[axis]
            else:
                r["why"] = (f"{rows[0]['name']!r} labels the {axis} axis in more families "
                            f"({top} vs {r['axes'][axis]}): this one sizes a part, not the family")
    return mapping, report


def _targets(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for part in text.split(","):
        axis, sep, name = part.partition("=")
        axis = axis.strip().lower()
        if not sep or axis not in ("x", "y", "z") or not name.strip():
            raise argparse.ArgumentTypeError(f"--targets wants x=NAME,y=NAME,z=NAME, not {text!r}")
        out[axis] = name.strip()
    return out


def rfa_files(args: Iterable[str]) -> Tuple[List[str], List[str]]:
    """(.rfa paths, errors): a directory means every .rfa in it; a path given twice
    is read once."""
    out: List[str] = []
    errors: List[str] = []
    seen = set()
    for a in args:
        found = (sorted(os.path.join(a, n) for n in os.listdir(a) if n.lower().endswith(".rfa"))
                 if os.path.isdir(a) else [a])
        if os.path.isdir(a) and not found:
            errors.append(f"{a}: no .rfa file in this directory")
        for p in found:
            key = os.path.normcase(os.path.realpath(p))
            if key not in seen:
                seen.add(key)
                out.append(p)
    return out, errors


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("inputs", nargs="+", help=".rfa files or directories of them")
    ap.add_argument("-o", "--output", required=True, metavar="MAP.json",
                    help="where to write the proposed map (YOUR path, never this repository)")
    ap.add_argument("--category", type=int, default=None,
                    help="only families of this category id (e.g. -2001040 electrical equipment)")
    ap.add_argument("--targets", type=_targets, default=None, metavar="x=Width,y=Depth,z=Height",
                    help="the generated family's parameter for each axis (default as shown)")
    ap.add_argument("--min-share", type=float, default=0.8,
                    help="share of the families that must agree on the axis (0.8)")
    ap.add_argument("--min-families", type=int, default=2,
                    help="families a parameter must label a dimension in (2)")
    ap.add_argument("--json", action="store_true", help="print the report as JSON")
    ns = ap.parse_args(argv)
    if not 0 < ns.min_share <= 1:
        ap.error("--min-share must be in (0, 1]")
    paths, errors = rfa_files(ns.inputs)
    fams = []
    for p in paths:
        try:
            fams.append(read_family(p))
        except Exception as exc:                                   # noqa: BLE001
            errors.append(f"{os.path.basename(p)}: {type(exc).__name__}: {exc}")
    mapping, report = propose(fams, category=ns.category, targets=ns.targets,
                              min_share=ns.min_share, min_families=ns.min_families)
    with open(ns.output, "w", encoding="utf-8") as fh:
        json.dump(mapping, fh, indent=1, sort_keys=True)
    summary = {"files": len(paths), "read": len(fams), "errors": errors,
               "labelling_parameters": len(report), "proposed": len(mapping), "map": ns.output,
               "report": report}
    if ns.json:
        print(json.dumps(summary, indent=1))
    else:
        print(f"{len(fams)} of {len(paths)} families read; {len(report)} shared parameters label "
              f"dimensions; {len(mapping)} proposed -> {ns.output}")
        for row in report:
            print(f"  {row['name']!r}: " + (f"-> {row['target']} ({row['axis']}, {row['families']} "
                                            f"families)" if "target" in row else row["why"]))
        for e in errors:
            print(f"  error: {e}")
    return 0 if fams else 1


if __name__ == "__main__":
    sys.exit(main())

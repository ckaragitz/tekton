#!/usr/bin/env python3
"""report.py -- render the human delivery report (Markdown) from a
validate_ifc.py JSON report. This is what the skill hands back to the user:
it frames the result in the two-tier language and states plainly what will
and won't be editable once the IFC is linked into Revit.

Usage:
    python report.py <validation.json> [-o report.md] [--compare harden.json]
                     [--after validate-after.json]

`--compare` adds the before/after section from harden_ifc.py's report, and
the report then describes the HARDENED file (the one delivered): its headline,
element table, remaining fixes, psets and phantoms come from the hardened
file's own validate_ifc.py report -- `--after`, or, when that is not given,
the `validate-after.json` beside harden.json that both documented paths write
(taken only when it is the report of the file harden.json produced: same
path, score and size).  When no such report exists the report stays on the
input, its first line says so and a warning goes to stderr (issue #760).
Without `--compare` the report describes <validation.json> (`--after` alone
describes that file, with no before/after table).  Exit code 0 on success,
2 on IO/usage error.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

TIER1 = "Tier 1"
TIER2 = "Tier 2"
#: the hardened file's validation report, as ifc_flow.py and the documented four-call path name it
AFTER_REPORT = "validate-after.json"


def load(path):
    with open(path) as fh:
        rep = json.load(fh)
    if not isinstance(rep, dict):
        raise ValueError(f"{path}: not a JSON object")
    return rep


def fmt_pct(x):
    try:
        return f"{100*float(x):.0f}%"
    except Exception:
        return str(x)


def render(rep: dict, compare: dict | None = None, *, source: str | None = None,
           note: str | None = None) -> str:
    """Markdown describing ``rep`` (a validate_ifc.py report).  ``source`` is
    the input's file name when ``rep`` is the hardened file's report; ``note``
    replaces the title's parenthesis when ``rep`` is not the hardened file."""
    sc = rep["score"]
    st = sc["stats"]
    ta, ph, sp, ps = rep["types"], rep["phantoms"], rep["spatial"], rep["psets"]
    schema = rep["schema"]
    fname = os.path.basename(rep["file"])
    title = f"# Revit-readiness report: `{fname}`"
    if source is not None:
        title += f" (hardened from `{source}`)"
    elif note is not None:
        title += f" ({note})"
    L = [title, ""]
    L.append(f"**Score: {sc['score']}/100** — **{sc['tier']}**")
    L.append("")
    L.append(f"- IFC schema `{schema.get('schema')}` — "
             + ("valid (0 schema errors)" if schema.get("n_errors") == 0
                else f"**{schema.get('n_errors')} schema error(s) — must be fixed first**"))
    L.append(f"- {st['products']} model elements; {st['tessellated']} triangle-mesh ({fmt_pct(st['tessellated_fraction'])} tessellated), "
             f"{st['identity_placements']} without a real insertion point")
    L.append(f"- {sp['storey_count']} level(s), {sp['space_count']} room/space(s), "
             f"{ta['type_objects']} type object(s), {ph['count']} phantom annotation solid(s)")
    L.append(f"- File size {rep['file_size']:,} bytes")
    L.append("")

    # ---- what this means in Revit
    L.append("## What happens when you Link this IFC into Revit")
    L.append("")
    L.append("Revit's IFC importer turns every IFC element into a **DirectShape** in the mapped "
             "category (see the table below): visible, taggable, schedulable, filterable, with your "
             "IFC property sets available as parameters. It never creates parametric families or "
             "MEP connectors from IFC — that is a Revit limitation, not something the file can fix. "
             "So the honest ceiling for any IFC is **" + TIER1 + "**; **" + TIER2 + "** needs the Revit API.")
    L.append("")
    L.append("| Tier | What it means | How you get it |")
    L.append("|---|---|---|")
    L.append("| **" + TIER1 + "** | Clean solid geometry in the right category, at the right place, "
             "movable/rotatable, one shared type per catalogue item, schedule data on the element. "
             "Still a DirectShape (no grips, no circuits). | A good IFC — this file, once its score is high. |")
    L.append("| **" + TIER2 + "** | Real Revit families (hosted, connectable), circuits, panel schedules that live-update. "
             "| Only via the Revit API — an APS Design Automation add-in placing families from the same spec. "
             "The panelboard shared-parameters file maps the psets 1:1. |")
    L.append("")

    if compare is not None:
        b, a = compare["before"], compare["after"]
        L.append("## Before / after hardening")
        L.append("")
        L.append("| metric | before | after |")
        L.append("|---|---:|---:|")
        for k in ("score", "tier", "elements", "type_objects", "duplicate_type_objects",
                  "untyped_elements", "tessellated_elements", "extruded_solids",
                  "identity_placements", "spaces", "size_bytes"):
            if k in b or k in a:
                L.append(f"| {k} | {b.get(k)} | {a.get(k)} |")
        L.append("")
        acts = compare.get("actions", {})
        if acts:
            L.append("Actions taken: " + ", ".join(f"{k.replace('_', ' ')}: {v}" for k, v in acts.items() if v))
            L.append("")

    # ---- editability table
    L.append("## Element-by-element: what will and won't be editable in Revit")
    L.append("")
    L.append("| Element | IFC class | Revit category | Geometry | In Revit you CAN | You CANNOT |")
    L.append("|---|---|---|---|---|---|")
    for r in rep["products"]:
        g = r["geometry"]
        kinds = set(g["kinds"])
        if "tessellated" in kinds:
            geom = "triangle mesh"
            can = "see, tag, schedule, filter by category, read parameters"
            cant = "move/rotate about a real insertion point, edit dimensions, connect circuits"
        elif any(k.startswith("mapped") for k in kinds) or "swept" in kinds:
            geom = "clean solid"
            can = "see, tag, schedule, filter, read parameters, move & rotate about its insertion point"
            cant = "stretch parametrically, use type/instance grips, connect circuits"
        else:
            geom = ", ".join(sorted(kinds)) or "-"
            can = "see, tag, schedule"
            cant = "edit parametrically"
        nm = str(r["name"] or "").replace("|", "\\|")
        L.append(f"| {nm} | {r['class']} | {r['revit_category']} | {geom} | {can} | {cant} |")
    L.append("")

    # ---- fixes
    L.append("## Top fixes to raise the tier")
    L.append("")
    if sc["top_fixes"]:
        for i, fx in enumerate(sc["top_fixes"], 1):
            L.append(f"{i}. **{fx['component']}** — {fx['fix']}")
    else:
        L.append("None — this file is already Tier 1. Link it into Revit (Insert ▸ Link IFC).")
    L.append("")

    # ---- data / parameters
    L.append("## Schedule data and parameters")
    L.append("")
    if ps["pset_names"]:
        L.append("Property sets found: " + ", ".join(f"`{n}`" for n in ps["pset_names"]) + ".")
        L.append("")
        L.append("These arrive in Revit as IFC parameters on the DirectShapes. To make them proper "
                 "**shared parameters** you can schedule and tag, bind the project's "
                 "`panelboard-shared-parameters.txt` (Manage ▸ Shared Parameters) — property names "
                 "match parameter names 1:1 (PanelName, Voltage, Phases, Wires, BusRating, MainsType, "
                 "MainsRating, ShortCircuitRatingkA, Mounting, NumberOfCircuits, NeutralRating).")
    if ps["typing_smells"]:
        L.append("")
        L.append(f"Note: {len(ps['typing_smells'])} electrical value(s) are stored as text "
                 "(e.g. `Voltage` as a label). They still import, but as text — export them as "
                 "IfcElectricVoltage/Current/Power measures for unit-aware parameters.")
    if ps["inconsistent"]:
        L.append("")
        L.append("Inconsistent property sets (same name, different shape across elements): "
                 + ", ".join(f"`{x['pset']}` on {x['class']}" for x in ps["inconsistent"]) + ".")
    L.append("")

    if ph["count"]:
        L.append("## Phantom solids")
        L.append("")
        for x in ph["findings"]:
            L.append(f"- {x['class']} `{x['name']}` ({x['confidence']} confidence): " + "; ".join(x["reasons"]))
        L.append("")
        L.append("These are drawing annotations (clearance zones, door swings) exported as building "
                 "solids; in Revit they show up as translucent blobs in every view. `harden_ifc.py` removes "
                 "them (or `--keep-clearance-as-space` turns box clearances into Spaces).")
        L.append("")

    L.append("## How to load it into Revit")
    L.append("")
    L.append("1. Revit ▸ **Insert ▸ Link IFC** (not File ▸ Open) and pick the hardened file.")
    L.append("2. Levels come from the IFC storeys; elements land in the categories listed above.")
    L.append("3. For real electrical families and circuits (" + TIER2 + "), run the APS automation "
             "path from the same building spec — the IFC stays as the coordination reference.")
    L.append("")
    L.append(f"_Generated by tekton-ifc {rep.get('engine_version')} from `{source or fname}`"
             + (f", delivered as `{fname}`" if source is not None else "") + "._")
    return "\n".join(L)


def is_report(d) -> bool:
    """A validate_ifc.py report: a JSON object with its file name and score block."""
    return isinstance(d, dict) and isinstance(d.get("score"), dict) and bool(d.get("file"))


def _same_file(a, b) -> bool:
    return bool(a and b) and os.path.abspath(str(a)) == os.path.abspath(str(b))


def same_numbers(rep: dict, compare: dict) -> bool:
    """``rep`` measures the file harden.json says it produced: the size and
    score harden.json recorded for it (path-agnostic: a kept or renamed copy
    of the hardened file still qualifies, an earlier run's or the input's
    report does not)."""
    produced = compare["after"]
    return (rep.get("file_size") == produced.get("size_bytes")
            and rep["score"].get("score") == produced.get("score"))


def produced_by(rep: dict, compare: dict) -> bool:
    """``rep`` is the report of the file harden.json says it produced, at
    that path -- what a positional or a discovered sibling must satisfy."""
    return _same_file(rep.get("file"), compare.get("output")) and same_numbers(rep, compare)


def find_subject(rep: dict, compare: dict, compare_path: str):
    """With ``--compare`` and no ``--after``: the hardened file's report to
    describe -- the positional itself when it is that report, else the
    AFTER_REPORT beside harden.json when it is.  Returns ``(report, None)``
    or ``(None, why)``."""
    if produced_by(rep, compare):
        return rep, None
    sibling = os.path.join(os.path.dirname(os.path.abspath(compare_path)), AFTER_REPORT)
    if not os.path.isfile(sibling):
        return None, f"no {AFTER_REPORT} beside {os.path.basename(compare_path)}"
    try:
        after = load(sibling)
        if not is_report(after):
            raise ValueError("not a validate_ifc.py report")
    except Exception as e:
        return None, f"{sibling} unreadable: {e}"
    if not produced_by(after, compare):
        return None, (f"{sibling} is not the report of {compare['output']}" if compare.get("output")
                      else f"{os.path.basename(compare_path)} records no output file")
    return after, None


def _render(subject: dict, cmp: dict | None, rep: dict) -> str:
    """render() for the chosen subject: named as hardened from harden.json's
    input when it is the hardened file, with the degraded title otherwise."""
    if subject is rep and cmp is not None and not produced_by(rep, cmp):
        note = ("the input, before hardening" if _same_file(rep.get("file"), cmp.get("input"))
                else "not the file harden.json produced; its report was not found")
        return render(rep, cmp, note=note)
    if cmp is None:
        return render(subject, note=None if subject is rep else f"the hardened file; from `{os.path.basename(str(rep['file']))}`")
    source = os.path.basename(str(cmp["input"])) if cmp.get("input") else None
    return render(subject, cmp, source=source,
                  note=None if source else "the hardened file; harden.json names no input")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("validation_json", help="JSON produced by validate_ifc.py --json")
    ap.add_argument("-o", "--output", help="write markdown here (default: stdout)")
    ap.add_argument("--compare", help="harden_ifc.py --report JSON: adds the before/after section and "
                    "makes the hardened file the subject of the report")
    ap.add_argument("--after", help=f"validate_ifc.py --json report OF THE HARDENED FILE (default with "
                    f"--compare: the {AFTER_REPORT} beside it, when it is that file's report)")
    args = ap.parse_args(argv)
    try:
        rep = load(args.validation_json)
        cmp = load(args.compare) if args.compare else None
        after = load(args.after) if args.after else None
        for label, d in ((args.validation_json, rep), (args.after, after)):
            if d is not None and not is_report(d):
                raise ValueError(f"{label}: not a validate_ifc.py report")
        if cmp is not None and not (isinstance(cmp.get("before"), dict) and isinstance(cmp.get("after"), dict)):
            raise ValueError(f"{args.compare}: not a harden_ifc.py --report file")
        if after is not None and cmp is not None and not same_numbers(after, cmp):
            raise ValueError(f"--after {args.after} is not the report of the file {os.path.basename(args.compare)} "
                             f"produced (its size or score differ from harden.json's `after`)")
        if after is not None and cmp is None and _same_file(after["file"], rep["file"]):
            raise ValueError(f"--after {args.after} is the report of {args.validation_json}'s own file ({rep['file']})")
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    subject, discovered = rep, False
    if after is not None:                       # the operator's assertion (the bench renames its artifacts)
        subject = after
    elif cmp is not None:
        subject, why = find_subject(rep, cmp, args.compare)
        if subject is None:
            print(f"warning: no report of the hardened file ({why}); the report describes "
                  f"{os.path.basename(str(rep['file']))} -- re-validate the hardened file to {AFTER_REPORT} "
                  f"beside {os.path.basename(args.compare)}, or pass --after", file=sys.stderr)
            subject = rep
        discovered = subject is not rep
    named = ", ".join(x for x in (args.validation_json, args.compare, args.after) if x)
    try:
        md = _render(subject, cmp, rep)
    except Exception as e:
        if not discovered:
            print(f"error: could not render the report from {named}: {e!r}", file=sys.stderr)
            return 2
        print(f"warning: the {AFTER_REPORT} beside {os.path.basename(args.compare)} is incomplete ({e!r}); "
              f"the report describes {os.path.basename(str(rep['file']))}", file=sys.stderr)
        try:
            md = _render(rep, cmp, rep)
        except Exception as e2:
            print(f"error: could not render the report from {named}: {e2!r}", file=sys.stderr)
            return 2
    try:
        if args.output:
            with open(args.output, "w") as fh:
                fh.write(md + "\n")
            print(f"report -> {args.output}")
        else:
            print(md)
    except OSError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())

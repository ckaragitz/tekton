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


def render(rep: dict, compare: dict | None = None, *, source: str | None = None) -> str:
    """Markdown describing ``rep`` (a validate_ifc.py report).  ``source`` is
    the input's file name when ``rep`` is the hardened file's report."""
    sc = rep["score"]
    st = sc["stats"]
    ta, ph, sp, ps = rep["types"], rep["phantoms"], rep["spatial"], rep["psets"]
    schema = rep["schema"]
    fname = os.path.basename(rep["file"])
    title = f"# Revit-readiness report: `{fname}`"
    if source is not None:
        title += f" (hardened from `{source}`)"
    elif compare is not None:
        title += " (the input, before hardening)"
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


def sibling_after(compare: str, compare_json: dict):
    """The AFTER_REPORT beside ``--compare`` when it is the report of the file
    harden.json says it produced -- same path, score and size, so a stale one
    left by an earlier run to the same path is not taken.  Returns
    ``(report, None)`` or ``(None, why)``."""
    sibling = os.path.join(os.path.dirname(os.path.abspath(compare)), AFTER_REPORT)
    if not os.path.isfile(sibling):
        return None, f"no {AFTER_REPORT} beside {os.path.basename(compare)}"
    try:
        after = load(sibling)
        if not isinstance(after.get("score"), dict):
            raise ValueError("not a validate_ifc.py report")
    except Exception as e:
        return None, f"{sibling} unreadable: {e}"
    produced = compare_json.get("after") if isinstance(compare_json.get("after"), dict) else {}
    if not (_same_file(after.get("file"), compare_json.get("output"))
            and after.get("file_size") == produced.get("size_bytes")
            and after["score"].get("score") == produced.get("score")):
        return None, f"{sibling} is not the report of {compare_json.get('output')}"
    return after, None


def _same_file(a, b) -> bool:
    return bool(a and b) and os.path.abspath(str(a)) == os.path.abspath(str(b))


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
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if after is not None and not isinstance(after.get("score"), dict):
        print(f"error: --after {args.after} is not a validate_ifc.py report", file=sys.stderr)
        return 2
    if after is not None and _same_file(after.get("file"), rep.get("file")):
        print(f"error: --after {args.after} is the report of the input itself ({rep.get('file')})", file=sys.stderr)
        return 2
    if after is None and cmp is not None:
        after, why = sibling_after(args.compare, cmp)
        if after is None:
            print(f"warning: no report of the hardened file ({why}); the report describes the input "
                  f"-- pass --after {AFTER_REPORT}", file=sys.stderr)
    md = (render(after, cmp, source=os.path.basename(rep["file"])) if after is not None
          else render(rep, cmp))
    if args.output:
        with open(args.output, "w") as fh:
            fh.write(md + "\n")
        print(f"report -> {args.output}")
    else:
        print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())

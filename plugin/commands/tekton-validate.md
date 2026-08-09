---
description: Validate a Revit deliverable — score/tier an .ifc (validate_ifc.py) or run the layered validator on a .rvt/.rfa (rvt_validate.py, 0 errors = the shipping gate) — and give a PASS/FAIL verdict with the file's Revit release
argument-hint: [path/to/file.ifc|.rvt|.rfa] [--json out.json]
allowed-tools: Bash Read Write Glob
---

Validate the file given in the arguments and return an honest PASS/FAIL
verdict with the numbers the tool prints. Detect the file type by extension.
`<plugin>` below is this plugin's root (the folder containing `.claude-plugin/`).

Input: `$ARGUMENTS`
(If no path was given, ask the user which `.ifc`, `.rvt` or `.rfa` to validate and stop.)

**If it is an `.ifc`** — use the `tekton-ifc` engine:
1. First run per sandbox: `pip install -r skills/tekton-ifc/scripts/requirements.txt`
   (the optional IFC extras; `/tekton-doctor --install` does the same once).
   If that fails, report the environment blocker and stop (never fake a score).
2. `python skills/tekton-ifc/scripts/validate_ifc.py <file.ifc> --json out/validate.json`
   (exit 0 = analysed, 2 = not IFC).
3. Report: `schema : IFC4 errors=N warnings=M` (**N>0 = FAIL, the file is
   broken**), `score : x/100`, `tier` (INVALID / Tier 0 / Tier 1 partial /
   Tier 1 — never Tier 2), the audit component scores (geometry, placements,
   types, instancing, phantoms, spatial, psets, units), the ranked top
   fixes, and the element inventory. State what each defect means in
   Revit (100% tessellation ⇒ frozen DirectShape blobs; identity placements
   ⇒ insertion points lost at the origin).

**If it is a `.rvt` or `.rfa`** — use the `tekton-inspect` gate (no install
step: the engine is bundled and reading is version-agnostic):
1. ONE call — readiness check + validator + one JSON:
   `python <plugin>/skills/tekton-inspect/scripts/_bootstrap.py go rvt_validate.py <file.rvt> --json out/report.json`
   (`go.ready` false → relay `go.preflight_line` verbatim and stop;
   `go.exit_code` 0 = ZERO errors, non-zero = errors listed; the verdict
   lines ride in `go.stdout`, the full report in the `--json` file).
2. Report the three layers — STRUCTURE (container, per-page ECC, gzip CRC,
   block walker, sentinels, record stamps), CONSISTENCY (ElemTable /
   history / id-set closure), SEMANTIC (every record decodes, reference
   integrity) — as `VALID (no errors); warnings=N` plus each warning, or
   the errors by layer and what each means (a single ECC mismatch means
   Autodesk's reader will reject the file). State the file's Revit release
   from `go.inputs[].revit_release`: "this is a Revit N file — it opens in
   N and newer, never older."
3. Add the reminder: the validator proves *our* invariants; **final
   acceptance for a `.rvt` is opening it in the Autodesk Viewer / the
   user's Revit** — ask them to confirm. A file that OPENS is not yet a
   file that RENDERS: offer tekton-inspect's render check
   (`render_inspect.py`) if created geometry must be visible.

Finish with a one-line verdict: `PASS` (with the key numbers) or `FAIL`
(with the blocking count), plus the JSON path.

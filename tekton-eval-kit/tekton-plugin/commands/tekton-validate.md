---
description: Validate a Revit deliverable — score/tier an .ifc (validate_ifc.py) or run the four self-checks on a .rvt (rvt_selfcheck.py) — and give a PASS/FAIL verdict
argument-hint: [path/to/file.ifc|.rvt] [--json out.json]
allowed-tools: Bash Read Write Glob
---

Validate the file given in the arguments and return an honest PASS/FAIL
verdict with the numbers the tool prints. Detect the file type by extension.

Input: `$ARGUMENTS`
(If no path was given, ask the user which `.ifc` or `.rvt` to validate and stop.)

**If it is an `.ifc`** — use the `tekton-ifc` engine:
1. First run per sandbox: `pip install -r skills/tekton-ifc/scripts/requirements.txt`.
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

**If it is a `.rvt`** — use the `tekton-native` engine:
1. First run per machine: from the plugin root `pip install ./lib`
   (or rely on the scripts' automatic fallback to `lib/src`). If the engine
   can't import, report the blocker and stop.
2. `python skills/tekton-native/scripts/rvt_selfcheck.py <file.rvt> --json out/selfcheck.json`
   (exit 0 = PASS, 1 = FAIL, 2 = not a readable .rvt).
3. Report the four counts and the verdict:
   gzip members verified / CRC failures; full ECC pages checked /
   mismatches; partition blocks / walker errors; seq-102 stamps valid /
   total → `VERDICT: PASS|FAIL`. Any non-zero failure count = FAIL, and a
   single ECC mismatch means Autodesk's reader will reject the file.
4. Add the reminder: self-checks prove our own invariants; **final
   acceptance for a `.rvt` is opening it in the Autodesk Viewer / the
   user's Revit** — ask them to confirm.

Finish with a one-line verdict: `PASS` (with the key numbers) or `FAIL`
(with the blocking count), plus the JSON path.

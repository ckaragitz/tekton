---
description: One-time tekton environment check/setup (off the hot path) — verify engine, genesis base, family-donor status and optional IFC extras; never touches Autodesk installs
argument-hint: [--install]
allowed-tools: Bash Read
---

Run the tekton doctor — the ONE-TIME environment check that keeps every
skill's hot path fast (the skills themselves need only their <2 s
preflight line; nothing here is required per-session).

Input: `$ARGUMENTS`

1. Run it from any tekton skill's scripts dir (all four are equivalent;
   `<plugin>` is the plugin root, the folder containing `.claude-plugin/`):

   ```bash
   python <plugin>/skills/tekton-author/scripts/_bootstrap.py doctor $ARGUMENTS
   ```

   Exit 0 = ready; 3 = something is wrong (the report names the one thing).

2. Relay the report as printed: plugin root, python, engine source,
   facts store, genesis base verification (+ its Revit release — the
   version any NEW file will target), family-donor status, specimen
   status, output dir, and the optional IFC extras (`ifcopenshell`,
   `numpy` — needed only for the `--ifc` input route).

3. If the user passed `--install`, the doctor pip-installs ONLY the
   missing optional IFC extras into the current interpreter — the single
   sanctioned install, run once, never on the job path. Without
   `--install` nothing is installed; the report just says what to run
   later if the IFC route is wanted.

4. `family container: bundled (genesis base)` is the normal state — the
   family build needs NO donor file and no user file. Only a non-2026
   target release needs one file from the user (their Revit version plus
   one `.rfa`/`.rvt` of their own; set `$RVT_FAMILY_DONOR` or pass the
   file to the job command). NEVER read, probe, list, or request access
   to any Autodesk installation directory (the Windows program /
   program-data Autodesk trees, /Applications/Autodesk, Autodesk
   family-template folders) — a donor comes only from the plugin's
   bundled assets or a file the user supplies.

Finish with the doctor's final readiness line verbatim
(`tekton: READY | …` or `tekton: NOT READY | …`).

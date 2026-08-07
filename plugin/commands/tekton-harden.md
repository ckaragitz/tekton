---
description: Harden an IFC so it links into Revit as clean, correctly-placed Tier-1 elements — validate, harden, re-validate, report the score/tier before→after
argument-hint: [path/to/input.ifc] [--keep-clearance-as-space]
allowed-tools: Bash Read Write Glob
---

Harden the IFC file given in the arguments and make it as Revit-editable as
IFC can be. Follow the `tekton-ifc` skill's Workflow B (validate → harden
→ re-validate → report). Do the steps in order and paste the real numbers
each script prints — never invent a value.

Input: `$ARGUMENTS`
(If no path was given, ask the user for the `.ifc` to harden and stop.)

1. **Locate the engine** — the plugin's `skills/tekton-ifc/` folder.
   First run in this sandbox only: `pip install -r skills/tekton-ifc/scripts/requirements.txt`
   (ifcopenshell + numpy). If that fails (no egress / no wheel), tell the
   user it is an environment blocker and stop — do not fake a result.

2. **Baseline validate:**
   `python skills/tekton-ifc/scripts/validate_ifc.py <input.ifc> --json out/validate-before.json`
   Report the `schema … errors=N`, `score`, `tier`, and the top fixes.

3. **Harden:**
   `python skills/tekton-ifc/scripts/harden_ifc.py <input.ifc> -o out/hardened.ifc --report out/harden.json`
   Add `--keep-clearance-as-space` if the arguments include it (keeps NEC
   110.26 working-clearance volumes as `IfcSpace` instead of removing them).

4. **Re-validate the output:**
   `python skills/tekton-ifc/scripts/validate_ifc.py out/hardened.ifc --json out/validate-after.json`
   It MUST show `errors=0`. If it does not, do not present the file as
   deliverable — show the errors and stop.

5. **Report** in this exact shape:
   - Score & tier: `before → after` (e.g. `31.4/100 Tier 0 → 89.0/100 Tier 1 (partial)`).
   - Actions applied (from `out/harden.json`): types merged/created,
     extrusions recovered, placements recovered, phantoms removed.
   - Element inventory with each element's predicted Revit category.
   - **Warnings remaining and source-only defects** (baked rotations,
     non-box triangle soup, wrong scale) that hardening cannot fix — say
     these need a re-export from the model, not more hardening.
   - The Tier statement: this is **Tier 1** (correctly-categorized,
     correctly-placed elements carrying schedule data as parameters). It is
     never Tier 2 — no MEP connectors, circuits or Revit-native panel
     schedules come from IFC.
   - Deliverables: `out/hardened.ifc`, `out/validate-after.json`,
     `out/harden.json`, and the Revit-side note: Link IFC (don't Open),
     Auto – Origin to Origin, then bind the panelboard shared parameters
     (see `skills/tekton-ifc/references/shared-parameters-mapping.md`).

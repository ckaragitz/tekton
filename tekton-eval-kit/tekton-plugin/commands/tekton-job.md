---
description: Run a whole BIM/Revit job end to end — intake → author/harden IFC (or edit a .rvt) → independent QA gate → one delivery report with an honest Tier-1/Tier-2 statement
argument-hint: [job description, e.g. "Area E electrical room from the attached spec"]
allowed-tools: Bash Read Write Edit Glob Grep Agent
---

Run this as a full job, orchestrated by the **bim-job-orchestrator** agent.
Delegate the work to the specialist agents this plugin ships and hand the
user ONE delivery report. Do not model geometry or edit binaries in this
turn yourself.

Job: `$ARGUMENTS`

Dispatch the `bim-job-orchestrator` agent with the job above and these
standing instructions:

1. **Intake first.** Confirm the deliverable (IFC to link into Revit is the
   default and always works; native `.rvt` only for editing an *existing*
   `.rvt` — new-element creation in `.rvt` is not yet available). Confirm
   the input (Claude Design `.ifc`, building spec JSON, description, or an
   existing `.rvt`), the user's Revit version if any `.rvt` is involved,
   and the schedule facts the psets need (panel names, voltage/phases/wires,
   bus rating, mains, SCCR, mounting, circuits, fed-from, room). State the
   Tier-1 / Tier-2 reality to the user before any work.

2. **Author / source.** From a spec or description, generate with
   `python skills/tekton-ifc/scripts/generate_ifc.py --spec <spec.json> -o out/model.ifc --validate`;
   from an attached `.ifc`, go straight to hardening; for Design authoring,
   follow tekton-ifc Workflow A. Bundled starting points live in the
   plugin's `examples/` folder (Chicago plenum electrical room; Eaton
   panelboard).

3. **Harden.** Dispatch `ifc-hardening-agent` (validate → harden →
   re-validate to `errors=0`; report score/tier before→after and any
   source-only defects).

4. **QA gate.** Dispatch `qa-validation-agent` on EVERY output artifact —
   `validate_ifc.py` for `.ifc`, `rvt_selfcheck.py` for `.rvt`. A builder
   never grades its own work; nothing that failed a gate ships. If a
   `.rvt` edit is in scope, dispatch `tekton-author-agent` for it and QA its
   output.

5. **Deliver** `job/<slug>/DELIVERY.md` + the files: what each element
   becomes in Revit (category/name/type/storey), the exact Tier statement
   (Tier 1 delivered; Tier 2 = connectors/circuits/native panel schedules
   needs the Revit API and is provided as a **handoff package** if asked),
   the Revit-side checklist (Link IFC, Origin-to-Origin, bind shared
   parameters, verify categories), the version note (IFC any version;
   `.rvt` cannot open in an older Revit), and only script-printed numbers.
   List open questions and log any failures.

If the sandbox blocks a tool (ifcopenshell won't install, engine won't
import, no egress), report the blocker in the delivery — never fabricate a
validation result or silently skip the QA gate.

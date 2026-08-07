---
name: tekton-edit
description: Edit an existing Revit .rvt file when the user asks to change, move, rename, retype, re-level, set a parameter or mark on, or delete elements (with cascade), or asks 'what depends on this element'. Runs scripts/rvt_edit.py (info, deps, modify, set-mark, rename-panel, set-level, move, retype, delete [--cascade]) and returns a new file plus a change report. Deletion follows the reduction law: an element leaves together with its content, referrers are never neutralised. Command reference and safety notes are in the skill body.

---

# tekton-edit — change what is already inside a `.rvt`

Opens a real Revit project, edits existing elements in place, re-emits a
file that still validates, and reports exactly what changed. `<plugin>`
below means this plugin's root (the folder containing `.claude-plugin/`);
this file is `<plugin>/skills/tekton-edit/SKILL.md`. Editing an existing
file is version-agnostic by design: the output keeps its INPUT's Revit
version (we never up- or down-grade), so ask the user's Revit version only
to confirm the input file itself is one they can open.

## THE DELIVERABLE RULE (non-negotiable)

When the user asks for an edited `.rvt` and the edit can be made, **make
it, write the new file, and hand it to the user — always.** Gate verdicts
and PROOF-ONLY stamps are **labels** in the report, **never refusal
logic**: deliver first, then state caveats plainly. The only acceptable
non-delivery is an edit that is genuinely impossible (e.g. the element does
not exist, or a non-cascade delete has dependents), reported as ONE clear
line naming the single blocker — with the dependents list when that is the
blocker, so the user decides. Never substitute another format for the
requested file.

## Step 1 — readiness (ONE command, <2 s)

```bash
python <plugin>/skills/tekton-edit/scripts/_bootstrap.py
```

`tekton: READY | …` → proceed. `NOT READY` → relay the line verbatim (it
names the one thing wrong). No pip install, no venv, no `eval`, no task
lists, no exploratory shell. Never read, probe, or list any Autodesk
installation directory for any reason.

## Step 2 — the edit (ONE command; its output IS your report)

Every command runs through the same launcher; every write goes to a NEW
`-o` path (the input is never overwritten):

```bash
# what's inside (ids + names every other command needs) — run this first
python <plugin>/skills/tekton-edit/scripts/_bootstrap.py run rvt_edit.py their.rvt info

# the proven single edits
python <plugin>/skills/tekton-edit/scripts/_bootstrap.py run rvt_edit.py \
    their.rvt rename-panel --id 742670 --name "HG4" -o out/renamed.rvt
#   … set-mark --id N --mark "P-14" | set-level --id N --elevation-ft 12.0
#   … move --id N --to 10 4 0 --rotation-deg 90   (units: FEET; metres x 3.28084)
#   … retype --id N --symbol M                    (target symbol must be loaded; see info)
#   … deps --id N                                  (dependents report before a delete)
#   … delete --id N [--cascade]

# several edits in ONE consistent commit, set-param, or add-instance/add-circuit:
python <plugin>/skills/tekton-edit/scripts/_bootstrap.py run rvt_job.py \
    edit their.rvt --ops out/ops.json -o out/edited.rvt
# ops.json: {"ops":[{"op":"rename","id":581483,"name":"HG4"},
#   {"op":"set-param","id":581483,"param_id":1234,"value":"480Y/277 V"},
#   {"op":"move","id":624416,"to":[10,4,0],"rotation_deg":90},
#   {"op":"delete","id":430715,"cascade":false},
#   {"op":"add-instance","name":"T2","symbol":621242,"position_ft":[12,4,0]},
#   {"op":"add-circuit","panel":"P-1","load":"T2","number":"1"}]}
# any unplannable op ABORTS the whole run (a partial edit is worse than none);
# the runner writes out/edited.rvt.manifest.json with the gates + honest status.

# the mandatory gate on every written file (exit 0 = ZERO errors):
python <plugin>/skills/tekton-edit/scripts/_bootstrap.py run rvt_validate.py out/edited.rvt
```

Confirm ids with the user (from `info`) before writing. Relay the command's
printed report / manifest as the deliverable summary — the self-check
counts (`crc_failures`, `ecc_mismatches`, `walker_errors`, `stamps_ok`)
must be zero/true, and the validator must report 0 errors before the file
is handed over as valid; if a gate fails, hand over the report and say
which gate stopped it in one line.

## Delete and THE REDUCTION LAW

- Without `--cascade`, deleting an element with hard dependents fails
  loudly and prints them — show the user that list; they decide.
- With `--cascade`, the hard-dependency closure goes WITH the target
  (bounded; a runaway closure is refused as a modelling error).
- A referrer of removed content is either deleted WITH it or left
  byte-identical — never "neutralised" into a state no Autodesk-saved file
  exhibits (that defect crashed Autodesk's reader while every offline check
  read clean).
- Do NOT use deletion to carve a project down into a "template"/"base" —
  that is the reduction toolchain's job, not this skill's; say so and route
  to the orchestrator.

## Reporting rules

1. Two tiers, in order: "self-checks and validator PASS (0 errors)" first;
   "accepted by Autodesk" only after the user opens the file and confirms.
2. Known non-blocking warnings (say them, don't hide them): undecodable
   Extensible-Storage entity blobs; the reader-tolerated block-counter
   warning on creation blocks. Elements carrying ES blobs are deletable but
   not yet modifiable — the tool says so and never corrupts.
3. Quote what is CERTIFIED vs VALIDATES vs UNPROVEN for the touched
   category from `skills/tekton-author/references/CRUD-COVERAGE.md`; never
   round a cell up.
4. Touch only elements the user named; never grow a value by padding to
   fake a change.

## Reference

| Path (under `skills/tekton-edit/`) | What |
|---|---|
| `scripts/_bootstrap.py` | readiness line · `run <script> …` launcher · `doctor` |
| `scripts/rvt_edit.py` | info · deps · delete [--cascade] · rename-panel · set-mark · set-level · move · retype |
| `scripts/rvt_job.py` | the ops/batch door (`edit in.rvt --ops ops.json -o out.rvt`) with gates + manifest |
| `scripts/rvt_validate.py` | the mandatory 3-layer validation gate |
| `skills/tekton-author/references/CRUD-COVERAGE.md` | the honest per-category CRUD matrix — quote it |

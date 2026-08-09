---
name: tekton-edit
description: Edit an existing Revit .rvt file when the user asks to change, move, rename, retype, re-level, set a parameter or mark on, or delete elements (with cascade), or asks 'what depends on this element'. ONE call (scripts/_bootstrap.py go edit FILE info, deps, set-mark, rename-panel, set-level, move, retype, delete [--cascade]) returns the new file, its detected Revit release, the change report and both gate verdicts as one JSON. Deletion follows the reduction law: an element leaves together with its content, referrers are never neutralised. Command reference and safety notes are in the skill body.

---

# tekton-edit — change what is already inside a `.rvt`

Opens a real Revit project, edits existing elements in place, re-emits a
file that still validates, and reports exactly what changed. `<plugin>`
below means this plugin's root (the folder containing `.claude-plugin/`);
this file is `<plugin>/skills/tekton-edit/SKILL.md`.

## Step 0 — the Revit release is DETECTED, not asked (state it every time)

An edit keeps its INPUT's release — we never up- or down-grade — so there
is no year to choose: every `go` call below auto-detects the release of
each `.rvt`/`.rfa` you pass (`go.inputs[].revit_release` + `opens_in`;
`go edit` also states `result.release.line`). Say it with the delivery:
**"your file is Revit N; the edited file stays Revit N and opens in N and
newer, never older."** Only if the user mentions an OLDER Revit than N is
there a problem — say plainly it cannot open either file, and offer the
create route at their year (**tekton-author**, `--target-version`). All
three doors below edit Revit 2026, 2025 and 2024 project files under their
own release; any other release stops with one clear line — relay it.

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

## Step 1 — the edit: ONE `go` call per job (readiness + edit + gates + one JSON)

Every command runs through the same launcher — no pip install, no venv,
no `eval`, no separate preflight or validate call, no exploratory shell;
never read, probe, or list any Autodesk installation directory for any
reason. `go` prints ONE JSON: `go.ready` / `go.preflight_line` (relay
verbatim if NOT READY — it names the one thing wrong), `go.inputs` (the
detected release), `go.exit_code`, and the job's report as `result`.
Every write goes to a NEW `-o` path (the input is never overwritten):

```bash
B="<plugin>/skills/tekton-edit/scripts/_bootstrap.py"
# ids + names every id-based edit needs (result.levels / .symbols / .wall_types ...) — when the user has not given ids
python "$B" go edit their.rvt info

# ONE call = the edit + structural self-check + the mandatory validator, one JSON (units: FEET; metres x 3.28084)
python "$B" go edit their.rvt set-level --id 1351691 --elevation-ft 12.0 -o out/edited.rvt
#   … rename-panel --id N --name "HG4" | set-mark --id N --mark "P-14"
#   … move --id N --to 10 4 0 --rotation-deg 90 | retype --id N --symbol M   (symbol must be loaded; see info)
#   … deps --id N   (dependents report, writes nothing) | delete --id N [--cascade]

# edits by NAME in one sentence (the front door; result.release + result.files, gates already run):
python "$B" go author --rvt their.rvt --edit "delete DP-1 with cascade; move LP-2 to 3,4" --out out/job1

# several ops in ONE consistent commit, set-param, add-instance/add-circuit (gates + manifest already run):
python "$B" go rvt_job.py edit their.rvt --ops out/ops.json -o out/edited.rvt
# ops.json: {"ops":[{"op":"rename","id":581483,"name":"HG4"},
#   {"op":"set-param","id":581483,"param_id":1234,"value":"480Y/277 V"},
#   {"op":"move","id":624416,"to":[10,4,0],"rotation_deg":90}, {"op":"delete","id":430715,"cascade":false},
#   {"op":"add-instance","name":"T2","symbol":621242,"position_ft":[12,4,0]},
#   {"op":"add-circuit","panel":"P-1","load":"T2","number":"1"}]}
# any unplannable op ABORTS the whole run (a partial edit is worse than none); manifest = out/edited.rvt.manifest.json
```

`go edit`'s `result`: `ok`, `output.path`/`.bytes` (the deliverable),
`release.line` ("Revit N in, Revit N out …"), `report` (what changed:
`replaced` / `removed_ids`), `gates.line` + `gates.structural`
(`crc_failures`, `ecc_mismatches`, `walker_errors` must be 0, `stamps_ok`
true) + `gates.validation` (`status`, `errors` must be 0, `warnings`,
`top_findings`, full report at `output.validation_json`); an impossible
edit is `ok:false` + ONE `error` line (+ `dependents`). Exit 0 = written
and both gates PASS. Confirm ids with the user (from `info`) before
writing; relay `release.line`, `gates.line` and the report as the delivery
summary; if a gate fails, still hand over the file and say which gate
stopped it in one line. (Fallback only, for a file written some other way:
`python "$B" go rvt_validate.py FILE.rvt` is the same mandatory gate alone.)

## Delete and THE REDUCTION LAW

- Without `--cascade`, deleting an element with hard dependents fails
  loudly and lists them (`result.dependents`) — show the user; they decide.
- With `--cascade`, the hard-dependency closure goes WITH the target
  (bounded; a runaway closure is refused as a modelling error).
- A referrer of removed content is either deleted WITH it or left
  byte-identical — never "neutralised" into a state no Autodesk-saved file
  exhibits (that defect crashed Autodesk's reader while every offline check
  read clean).
- Do NOT use deletion to carve a project down into a "template"/"base" —
  that is the reduction toolchain's job, not this skill's; say so.

## Reporting rules

1. The release line first (`result.release.line` / `go.inputs`), then two
   tiers, in order: "self-checks and validator PASS (0 errors)"
   (`gates.line`); "accepted by Autodesk" only after the user opens the
   file and confirms (`result.status_note` says exactly this).
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
| `scripts/_bootstrap.py` | `go edit …` / `go author …` / `go SCRIPT.py …` one-call dispatch (readiness + job + gates + JSON incl. detected release) · `run SCRIPT …` (bare text) · `doctor` |
| `scripts/rvt_edit.py` | info · deps · delete [--cascade] · rename-panel · set-mark · set-level · move · retype (`--json` adds both gates; what `go edit` runs) |
| `scripts/rvt_job.py` | the ops/batch door (`edit in.rvt --ops ops.json -o out.rvt`) with gates + manifest |
| `scripts/rvt_validate.py` | the mandatory 3-layer validation gate, standalone |
| `skills/tekton-author/references/CRUD-COVERAGE.md` | the honest per-category CRUD matrix — quote it |

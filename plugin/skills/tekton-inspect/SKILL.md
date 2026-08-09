---
name: tekton-inspect
description: Inspect, validate or audit a Revit .rvt/.rfa file when the user asks whether a file is valid, what is in it, why it fails to open, whether created elements will render (load-vs-render), for a panel schedule, or for a seed/content audit. Runs scripts/rvt_validate.py, the render inspector (python -m rvt.render.inspect), scripts/seed_audit.py and scripts/panel_schedule.py, then explains the results in plain language. How to read validator layers, LOADED-vs-RENDERED verdicts and the audit report is in the skill body.

---

# tekton-inspect — validate, look inside, audit readiness, and QA

tekton's QA surface: every tool here READS and REPORTS; nothing writes a
model. `<plugin>` below means this plugin's root (the folder containing
`.claude-plugin/`); this file is `<plugin>/skills/tekton-inspect/SKILL.md`.
Reading any `.rvt` is version-agnostic by design (the file carries its own
schema and we decode against it); the file's Revit release is auto-detected
and worth stating with every verdict ("this is a Revit N file — it opens in
N and newer, never older"): use `go` instead of `run` below and it rides in
the ONE JSON as `go.inputs[].revit_release`. The habit this skill teaches:
**a file that OPENS is not a file that RENDERS — check both, report both.**

## Step 1 — readiness (ONE command, <2 s)

```bash
python <plugin>/skills/tekton-inspect/scripts/_bootstrap.py
```

`tekton: READY | …` → proceed. `NOT READY` → relay the line verbatim. No
pip install, no venv, no `eval`, no task lists, no exploratory shell. Never
read, probe, or list any Autodesk installation directory. A check that did
not run is reported as "not checked" with the error — never as a pass.

## Step 2 — the check (ONE command per question; its output IS your report)

```bash
# "Is this .rvt sound / will it open?"  → the shipping gate (exit 0 = ZERO errors)
python <plugin>/skills/tekton-inspect/scripts/_bootstrap.py run rvt_validate.py \
    their.rvt --json out/report.json

# "It opened but looks empty / a wall doesn't show"  → LOAD vs RENDER, per element
python <plugin>/skills/tekton-inspect/scripts/_bootstrap.py run render_inspect.py \
    their.rvt [--class SWall | --id 493612] [--json out/geom.json]

# "Is our seed/template ready for this job? What's missing?"  → gaps with FIX lines
python <plugin>/skills/tekton-inspect/scripts/_bootstrap.py run seed_audit.py \
    their-seed.rvt --job examples/room-spec.json [--json out/audit.json]

# "Panel schedules / are these panels overloaded?"  → printable schedules + load calcs
python <plugin>/skills/tekton-inspect/scripts/_bootstrap.py run panel_schedule.py \
    --spec examples/electrical-job.json --out out/schedules/
```

## How to read each verdict

**Validator** (`rvt_validate.py`) — three layers: STRUCTURE (container,
per-page ECC, gzip CRC, block walker, sentinels, record stamps),
CONSISTENCY (ElemTable/History/increment bookkeeping, id-set closure),
SEMANTIC (every record decodes; reference integrity; connector-graph
closure). Report `VALID (no errors); warnings=N` plus each warning. Known
non-blocking warnings: undecodable Extensible-Storage entity blobs; the
reader-tolerated block-counter warning on creation blocks. **Any ERROR =
the file does not ship** — say which layer and what it means. ~0.3 s for a
600 KB base, ~12 s for a 32 MB project.

**Render inspector** — the failure it catches: the viewer opens the file
but shows nothing where an element carries no baked geometry. Read the
`kind` column: `brep`/`mesh` draw; `instance-ref` draws if its symbol
carries a solid (resolved for you); `curves-only` is 2D; `dummy` loads but
does NOT draw — normal for levels/grids/annotation, the bug for a 3D model
element. Current truth to relay when asked about our generated rooms: the
equipment renders; created walls load but may not draw yet (wall B-rep
authoring is in certification). Run this before promising a picture.

**Seed audit** — inventories a firm's template (levels, wall types,
families by category with placed instances, title blocks, phases), then per
job item reports the best match or MISSING **with a plain-English FIX**;
verdict `SEED READY` / `SEED USABLE WITH GAPS` / `SEED NOT READY` (exit 2).
The FIX lines are the most useful deliverable — hand them over verbatim.
Expected on our bundled genesis base: `SEED NOT READY` for a
clone-from-seed job — correct, not a defect (the base is family-free BY
DESIGN; tekton loads its own generated families onto it).

**Panel schedules** — writes per-panel HTML/CSV, a print-ready
`schedules.html`, and `summary.json`; console prints connected + demand
kVA, demand amps vs bus rating, phase imbalance, transformer loading, and
warnings. These are DESIGN AIDS for the licensed engineer to review — say
so with every schedule, and surface every warning line verbatim.

## Reporting rules (non-negotiable)

1. Never report a pass you did not run.
2. Two tiers, in order: our validator's verdict first; "accepted by
   Autodesk" only after the user opens the file and confirms.
3. LOAD ≠ RENDER — run the render inspector before promising a picture.
4. Quote counts and exact warnings, not adjectives like "clean".
5. A gap list is an asset — deliver FIX lines verbatim.

## Reference

| Path (under `skills/tekton-inspect/`) | What |
|---|---|
| `scripts/_bootstrap.py` | readiness line · `run <script> …` launcher · `doctor` |
| `scripts/rvt_validate.py` | the 3-layer validity gate (0 errors required to ship) |
| `scripts/render_inspect.py` | LOAD-vs-RENDER inspector (wraps `python -m rvt.render.inspect`) |
| `scripts/seed_audit.py` (+ `scripts/spec_to_rvt.py`) | seed/template readiness vs a job spec, with FIX lines |
| `scripts/panel_schedule.py` | NEC-style schedules + load calcs from an electrical job spec |
| `examples/electrical-job.json` · `examples/room-spec.json` | worked inputs (the bus-storage electrical room) |
| `skills/tekton-author/references/GENESIS-BASE.md` · `…/CRUD-COVERAGE.md` | why the base audits family-free · the capability matrix |

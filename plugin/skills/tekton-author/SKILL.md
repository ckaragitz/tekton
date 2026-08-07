---
name: tekton-author
description: Create a new Revit project or family file from scratch when the user asks to build, generate, author or 'make me' a Revit (.rvt/.rfa) file, a room, an electrical room, walls, a panelboard, switchboard, transformer, lighting layout, or a family — from a plain-English prompt, an IFC file, or an existing .rvt to extend. Runs the tekton front door (scripts/frontdoor.py author --prompt | --ifc | --rvt) onto the certified genesis base and returns the .rvt plus a manifest stating what was created and any PROOF-ONLY stamps. Also handles 'turn this IFC into Revit' and 'give me the Three.js/IFC handoff for a prompt'. Full input formats, examples and caveats are in the skill body and references/.

---

# tekton-author — one front door, three inputs, one honest manifest

tekton authors Revit `.rvt`/`.rfa` files as OUR OWN content on OUR certified
genesis base — pure Python, no Revit install. `<plugin>` below means this
plugin's root: the folder containing `.claude-plugin/`, `skills/`, `lib/`,
`assets/` (this file is `<plugin>/skills/tekton-author/SKILL.md`). Every
command runs from anywhere; outputs land under `--out` (use the user's
working directory).

## THE DELIVERABLE RULE (non-negotiable)

When the user asks for a `.rvt` or `.rfa` and one can be built, **build it,
write it to disk, and hand it to the user — always.** PROOF-ONLY stamps and
gate verdicts are **labels** that ride in the manifest, **never refusal
logic**: deliver the file first, then state the stamps and caveats plainly.
The ONLY acceptable non-delivery is a build that is genuinely impossible,
reported as ONE clear line naming the single missing input (the command
already prints it). Never silently substitute IFC for a requested `.rvt` —
offer IFC as an addition, not a replacement. Never lecture before
delivering.

## Step 0 — ask the Revit version FIRST, then pass it to the tool

First question on every creation request: **"What Revit version will open
this?"** Revit cannot open a file saved by a newer release. Pass the answer
straight through as `--target-version {2026,2025,2024}` — the tool owns the
version guard; never decide (or stay silent) on its behalf.

Honest status per target:

- **2026 — certified today.** The bundled genesis base is Revit **2026**
  (preflight prints the release); outputs open in Revit 2026.
- **2025 — in certification, not yet deliverable as `.rvt`.** The
  Revit-2025 genesis base (the B2025 lineage: the same certified pipeline
  re-run on Revit-2025 format data) is being produced now. Until it
  certifies, `--target-version 2025` still DELIVERS the 2026 build — plus
  ONE clear line in the result (*"target 2025 requested: the 2025 base is
  pending certification; this file targets 2026 — your Revit 2025 cannot
  open it; the IFC alongside is version-agnostic"*) and a version-agnostic
  **IFC of the same intent** written beside the build (any modern Revit
  links/imports IFC). Relay the line verbatim, hand over BOTH files, and
  never present the 2026 `.rvt` as openable in Revit 2025.
- **2024 — guarded target, base not yet in certification.** The 2024 slot
  (the B2024 lineage) is registered but its genesis campaign has not
  produced a base yet — it is queued behind 2025 (the certified pipeline
  transfers across releases). Same honest degrade as 2025:
  `--target-version 2024` DELIVERS the 2026 build plus the same clear line
  with 2024 substituted (*"target 2024 requested: the 2024 base is pending
  certification; this file targets 2026 — your Revit 2024 cannot open it;
  the IFC alongside is version-agnostic"*) and the IFC addition. Relay it
  verbatim; never present the 2026 `.rvt` as openable in Revit 2024.
- **Older releases (pre-2024)** — same honest degrade: deliver what can be
  built today and the IFC addition; a version-N `.rvt` needs a version-N
  certified base (no slot exists yet before 2024, so the tool refuses the
  flag value and you state the degrade yourself).

When the user's release certifies, the exact same command resolves its base
automatically — nothing to relearn. If the user never states a version, the
output targets 2026 and the manifest says so.

## Step 1 — readiness (ONE command, <2 s)

```bash
python <plugin>/skills/tekton-author/scripts/_bootstrap.py
```

One line comes back:
`tekton: READY | python … | engine bundled | genesis verified (Revit 2026) | family-donor <status> | out-dir OK | 0.1s`

- `READY` → go straight to step 2. No pip install, no venv, no `eval`, no
  task lists, no exploring the filesystem.
- `NOT READY` → relay the line verbatim; it names the one thing wrong.
- `family-donor missing` is FINE: the family container is built from the
  bundled genesis base — no donor file, no user file needed
  (`$RVT_FAMILY_DONOR` stays as an expert override, e.g. a non-2026 target
  release). Never read, probe, list, or request access to any Autodesk
  installation directory (the Windows program/program-data Autodesk trees,
  /Applications/Autodesk, any Autodesk family-template folder). A donor
  comes ONLY from the plugin's bundled assets or a file the user supplies.

## Step 2 — the job (ONE command; its `--json` IS your report)

Exactly one input per call — a prompt, an IFC, or an existing `.rvt`:

```bash
python <plugin>/skills/tekton-author/scripts/_bootstrap.py run frontdoor.py \
    author --prompt "an electrical room 30x20 ft rated for 2500 A service with a main \
    switchboard, two 400 A distribution panels and four lighting panels" --out out/job1 --json

python <plugin>/skills/tekton-author/scripts/_bootstrap.py run frontdoor.py \
    author --ifc <their-file>.ifc --out out/job2 --json

python <plugin>/skills/tekton-author/scripts/_bootstrap.py run frontdoor.py \
    author --rvt their.rvt --edit "delete DP-1 with cascade; move LP-2 to 3,4" --out out/job3 --json
```

The `--json` result is the deliverable summary — relay it, do not
re-investigate: `status` (verbatim), `files` (hand these over), `manifest`
(read `honesty.proof_only_stamps`, `build.degradations`, the validator
summary), `errors` (each names its single missing input). Exit 0 = route
completed (PROOF-ONLY is still 0); 2 = usage; 3 = build incomplete (the
JSON says exactly what stopped and what was still written); 4 = self-checks
failed (deliver the file WITH the failed-self-check report and say plainly
it failed our own validator).

Useful flags (see `--help`): `--target-version {2026,2025,2024}` (the
user's answer from step 0 — the tool checks it and degrades honestly, see
above),
`--base FILE.rvt` (author on the firm's own base; an Autodesk sample is
refused; combined with a target it must BE that release), `--specimens
FILE.rvt`, `--strict` (two coordinated files instead of one stamped
combined file — see caveat 3), `--handoff-only` (prompt route: emit only
the AI-surface handoff package), `--stages FLWECV` (subset the build).

## How to report a result (in this order)

1. Hand over every file in `files` (plus the handoff package on the prompt
   route). The files are the user's regardless of stamps.
2. `status` verbatim. `DELIVERABLE (all gates passed; genesis base)` is the
   only string meaning shippable to third parties; `PROOF-ONLY …` means the
   user has the file with named caveats; `FAILED (…)` names the stage and
   the one missing input. If the manifest carries `target_version.line`
   (a 2025 or 2024 target while that release's base certifies), relay that
   line verbatim with the files — the `.rvt` AND the IFC addition are both
   the user's.
3. The stamps (`honesty.proof_only_stamps`) and `build.degradations`,
   plainly, AFTER the file is handed over — labels, not reasons to
   withhold.
4. Counts: families generated, elements created, circuits planned, and (on
   the prompt route) the intent's `coverage` block — what was understood,
   defaulted, or recognised-but-not-built. Share `intent.json` so the user
   can correct ambiguity there.
5. Two acceptance tiers, always separate: "our validator PASS (0 errors)"
   vs "accepted by Autodesk" — the latter only after the user opens the
   file in the Autodesk Viewer / Revit and confirms.

## The three routes in one breath

- **`--prompt`** parses deterministically (no API key): rooms with
  dimensions and service rating; switchboards / distribution / lighting /
  receptacle panelboards / transformers by count, rating, voltage, mains
  style, spaces; feeders. Anything recognised but not buildable
  (luminaires, generators, ATS, MCC …) is listed under `not_built`, never
  silently dropped. It ALSO always writes the AI-surface handoff
  (`scene-brief.json`, `HANDOFF.md`, `PROMPT_TO_IFC.md`) — offer it as an
  addition: a surface builds the three.js scene, exports IFC4, and the file
  re-enters via `--ifc` (`references/PROMPT-TO-IFC.md`).
- **`--ifc`** resolves placements, dims, mounting, the feeder tree, and
  maps every board onto OUR constructors by the tagging-contract Pset join
  key (`references/TAGGING-CONTRACT.md`, `references/CATALOG-FACTS.md`).
  Worked inputs ship in `examples/`.
- **`--rvt --edit`** is the standalone-proven edit route (surgical detail:
  the **tekton-edit** skill).

## Honest caveats (state with the delivery, never instead of it)

1. **Build inputs.** All build inputs ship in the plugin: the family
   container and the wall/instance templates come from the bundled genesis
   base — no donor file, no specimen ancestor, no user file needed. A user
   file is only ever needed for a target release whose base has not
   certified yet — today that means anything before 2026, with 2025 in
   certification and 2024 registered behind it (step 0) — where
   `$RVT_FAMILY_DONOR` / `--specimens` / `--base` remain as expert
   overrides.
2. **PROOF-ONLY provenance stamp.** The bundled genesis base is
   viewer-certified as OURS but its lineage discloses Autodesk-derived
   residue (`references/GENESIS-BASE.md`), so the provenance gate stamps
   outputs PROOF-ONLY for third-party deliverability. The user still gets
   the file; a firm's own base via `--base` changes the verdict.
3. **The open walls+families bug.** Created walls AND loaded families in
   ONE file currently trip Autodesk's audit; each alone passes. The default
   delivers the combined file stamped `PROOF-ONLY: walls+families
   combination unverified`; `--strict` delivers TWO coordinated proven
   files (shell + equipment) — offer both, user picks.
4. **LOAD is not RENDER.** Loaded symbols/instances carry real solids;
   created walls load but may not draw yet. Run **tekton-inspect**'s render
   check before promising a picture.
5. **CRUD coverage per category** is measured, not assumed — quote the row
   from `references/CRUD-COVERAGE.md` for whatever category is requested.

## Reference

| Path (under `skills/tekton-author/`) | What |
|---|---|
| `scripts/_bootstrap.py` | readiness line · `run <script> …` launcher · `doctor` |
| `scripts/frontdoor.py` | THE front door (`author` with `--prompt` / `--ifc` / `--rvt --edit`) |
| `scripts/ifc_intent.py` | IFC → intent resolver (also reused by the build) |
| `scripts/rvt_validate.py` | the 3-layer validation gate (0 errors required) |
| `scripts/rvt_job.py` | the gated job runner the `--rvt` route delegates to |
| `references/TAGGING-CONTRACT.md` · `references/CATALOG-FACTS.md` | Pset join key · manufacturer facts store |
| `references/PROMPT-TO-IFC.md` · `references/GENESIS-BASE.md` · `references/CRUD-COVERAGE.md` | prompt→IFC flow · the base + stamps · the capability matrix |
| `examples/electrical-room-2500a.ifc` · `examples/chicago-plenum-downlight.ifc` | worked IFC inputs (our own authoring) |
| sibling skills | **tekton-edit** (change an existing file) · **tekton-inspect** (validate/QA) · **tekton-ifc** (IFC authoring/hardening) |

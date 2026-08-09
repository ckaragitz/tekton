# tekton — the plugin that lets Claude run your Revit work

Give this to Claude and it can do the fiddly parts of a Revit job for you:
**create a Revit project or family** (`.rvt` / `.rfa`) from a plain-English
description, an IFC, or a spec — an electrical room with its switchboard,
distribution and lighting panels and transformers, walls, families — with
**no Revit install and no Autodesk seat anywhere in the loop**; **edit an
existing `.rvt`** (move, retype, re-level, set values, delete with cascade);
**inspect and validate** any Revit file before you send it; and turn what
you build in **Claude Design** into an IFC that **links into Revit** with
everything in the right category carrying your panel-schedule data, or
**fix** an IFC that came in as frozen blobs at the origin. You describe the
job in plain English; the plugin has the engine, the certified bases, the
rules and the examples so Claude doesn't have to guess.

You do **not** need to be a developer, and nothing needs installing on the
job path — the engine is bundled and runs on the system Python. You do need
Revit (or the free Autodesk Viewer) on the receiving end to open the results:
Revit is the last-mile deliverable format, and Autodesk's own reader is the
final judge of every file.

---

## What's in the box

| Piece | What it does for you |
|---|---|
| **Skill `tekton-author`** | **Create** a new `.rvt` / `.rfa` from a prompt, an IFC, or an existing `.rvt` to extend. Asks the recipient's **Revit year first** (2026 / 2025 / 2024 build natively on that year's certified base; older years get an honest fallback plus an IFC), then runs the front door in **one call** (`go author …`) and hands back the file with its honest per-release status, PROOF-ONLY stamps and manifest. |
| **Skill `tekton-edit`** | **Change** what is already inside a `.rvt`: info, dependencies, modify, set a mark, rename a panel, set level, move, retype, delete (with cascade). The file keeps its own Revit release; you get a new file plus a change report. |
| **Skill `tekton-inspect`** | **QA**: is this file valid (the layered validator, 0 errors = our shipping gate), what is in it, which Revit release is it, why won't it open, will created elements actually **render** (LOAD vs RENDER), panel schedules, seed audits. |
| **Skill `tekton-native`** | The engine-level skill for people who want to work on `.rvt` bytes directly: streams, class schema, records, proven text edits, whole-file rewrite, the four low-level self-checks. |
| **Skill `tekton-ifc`** | Everything IFC: author Revit-ready models in Claude Design, validate an `.ifc`, harden it (recover real positions and clean solids), map property sets onto Revit shared parameters, and the Revit-side checklist. |
| **Commands** `/tekton-job`, `/tekton-validate`, `/tekton-harden`, `/tekton-doctor` | One-liners: run a whole job end to end (year asked first, one build call, independent QA, one delivery report); check any `.rvt`/`.rfa`/`.ifc`; harden an IFC; the one-time environment check (off the hot path). |
| **Agents** (job orchestrator, `.rvt` author, IFC hardening, QA) | Behind `/tekton-job`: a project-manager agent hands the build to the author agent, IFC work to the hardening agent, and every artifact to a separate QA agent — no builder grades its own work. |
| **Assets** (`assets/genesis/`) | The three composed genesis bases — Revit **2026, 2025 and 2024** — each certified by Autodesk's reader; every new project is authored on one of them as our own content. |
| **Examples** (`examples/`, `skills/tekton-author/examples/`) | Two finished real IFC jobs to copy (the Chicago plenum electrical room and the Eaton Pow-R-Line panelboard, with delivery reports) and the worked create inputs (`electrical-room-2500a.ifc`, `room-spec.json`). |
| **Engine** (`lib/`) | The `rvt` reader/writer (pure Python) that every skill drives through its zero-install bootstrap. Developers who want it on their own interpreter: see `lib/README.md`. |

### The honest truth, today (read this once so you're never surprised)

- **Creation works and is delivered** on the certified 2026 / 2025 / 2024
  bases: rooms, walls, switchboards, distribution / lighting / receptacle
  panelboards, transformers, families. Every output passes our validator
  (0 errors) before it is handed over — but *our validator PASS* and
  *accepted by Autodesk* are two different statements: a file is accepted
  only when your Revit / the Autodesk Viewer opens it. Claude states both.
- **PROOF-ONLY, in one sentence:** the bases are certified as ours, but their
  lineage still discloses Autodesk-derived residue and our identity /
  legal-review gates are still open, so every output is *stamped* `PROOF-ONLY` for
  third-party deliverability — you still get the file, always; the stamp is a
  label after delivery, never a refusal.
- **Target version is asked first.** Revit cannot open a file saved by a
  newer Revit, so Claude asks which year will open the file before building.
  Unsure or mixed installs → 2024 (every supported Revit opens it). Older
  than 2024: not supported for creation — you get a default-release file, one
  clear line saying your Revit cannot open it, and an IFC beside it that any
  Revit 2019+ links. An IFC is always an *addition*, never swapped in for the
  `.rvt` you asked for.
- **LOAD is not RENDER.** Placed equipment carries real solids; created walls
  load and validate but may not draw in a 3D view yet. `tekton-inspect`'s
  render check tells you which, per element, before anyone promises a picture.
- **The one open cell:** created walls **and** our generated, placed families
  in ONE file currently trip Autodesk's audit, while each alone passes. The
  default is one combined file stamped `PROOF-ONLY: walls+families
  combination unverified`; `--strict` gives two coordinated files (shell +
  equipment). It is the project's top engineering priority (tracked as issue
  #16 in the repo); Claude says so with every affected delivery.
- **Circuits and Revit-native panel schedules** are planned in the manifest,
  not promised as working Revit circuits. From IFC they never come at all:
  **Tier 1** (what an IFC gives you) = every element in the right Revit
  category, at the right position and true size, with your schedule data as
  parameters — movable, taggable, schedulable, but DirectShape geometry with
  no connectors; **Tier 2** (connectors, circuits, native panel schedules)
  needs native families, which is exactly why the `.rvt` route exists.

---

## Install (three ways — all verified against the Claude Code plugin docs)

**1. Try it right now, straight from the zip** (Claude Code v2.1.128+):

```bash
claude --plugin-dir ./tekton-plugin.zip
```

**2. Or from the unzipped folder** (also the way to develop it):

```bash
claude --plugin-dir ./tekton
```
Edit anything, then run `/reload-plugins` inside the session to pick up changes.

**3. Install it permanently** — the folder doubles as a one-plugin marketplace:

```text
/plugin marketplace add ./tekton
/plugin install tekton@tekton
/reload-plugins
```

Check the plugin's health any time: `claude plugin validate ./tekton` (should
print `✔ Validation passed`). Skills are namespaced, e.g. `/tekton:tekton-job`.
There is **no install step for the engine**: every skill's bootstrap (e.g.
`skills/tekton-author/scripts/_bootstrap.py`) finds the bundled `lib/` and the
certified bases by itself and answers `tekton: READY | …` in well under a
second. Run
`/tekton-doctor` once if you want the full environment report;
`/tekton-doctor --install` adds only the *optional* IFC extras
(`numpy` for the `--ifc` input route if your Python lacks it; `ifcopenshell`
for IFC authoring/validation).

## Install — Cowork

Cowork runs the same skills. Add the plugin's **skills folder** to your
Cowork skills: copy the whole `plugin/skills/` directory (all five skills
plus `_shared/`, the zero-install bootstrap) into Cowork's skills location,
keeping each skill in its own folder with its `SKILL.md` at the top. Copy
`plugin/lib/` and `plugin/assets/` alongside so the bootstrap finds the
engine and the certified bases (it looks for them next to the skills). The
`.mcpb`/connector route is not needed — these skills run their own scripts
in Cowork's built-in code sandbox.

Creating from a prompt, editing and validating `.rvt`/`.rfa` files need **no
pip install at all** on any Python 3.11+. The IFC *input* route (`go author
--ifc`, product facts → family) never needs `ifcopenshell` — the engine
reads IFC through the bundled pure-python steplite fallback
(`lib/src/rvt/ifc/steplite.py`) — but its placement/geometry resolution does
need `numpy`: if the sandbox's Python lacks it, the call stops in under a
second with ONE clear line saying so, and `/tekton-doctor --install` adds it
once (tracked to remove: repo issue #127). IFC *authoring / validation /
hardening* (the `tekton-ifc` scripts) wants the optional extras
(`ifcopenshell` + `numpy`): the same `--install`, or let the `tekton-ifc`
skill run `pip install -r skills/tekton-ifc/scripts/requirements.txt` in the
sandbox (ifcopenshell ships a ready-made Linux wheel, so no compiler is needed).

## Install — claude.ai chat

claude.ai loads one skill at a time by upload. Zip a skill folder and add
it under **Settings → Capabilities → Skills** (or attach it in the chat where
your plan supports skills):

- To create or edit Revit files: zip `plugin/skills/tekton-author/` (or
  `tekton-edit/`, `tekton-inspect/`) **together with `plugin/skills/_shared/`,
  `plugin/lib/` and `plugin/assets/`** (the bootstrap, the engine, the
  certified bases) → upload.
- For IFC work: zip `plugin/skills/tekton-ifc/` → upload.

Then just attach your file to the chat and describe the job — e.g. *"make me
a Revit 2025 electrical room with a 1200 A switchboard and four lighting
panels"*, or attach the `.ifc` you exported from Claude Design and say
*"turn this into a .rvt for Revit 2024"* or *"validate and harden this for
Revit."* The skill runs its scripts in the chat's built-in code sandbox.

## Using it with Claude Design

Claude Design is where you can **build the model visually**; it usually does
not run the Python scripts. The `tekton-ifc` skill tells Claude exactly how
to author in Design so the export is Revit-friendly (metres, real object
positions, un-baked shapes, one tagged group per real-world part, clearances
as data not solid boxes) and installs the canonical exporter
(`skills/tekton-ifc/assets/ifc-export.js`) as `./ifc-export.js` in your
Design project. Workflow:

1. In a Design chat with the skill loaded, ask Claude to build or upgrade
   your 3D page "for Revit". It follows the tagging contract and installs
   the exporter. (The `tekton-author` prompt route writes the same brief for
   you: `HANDOFF.md` + `scene-brief.json` next to the `.rvt`.)
2. Click **IFC** in the stage toolbar → `<name>.ifc` downloads.
3. Attach that `.ifc` in Claude Code / Cowork / claude.ai and say either
   *"turn this into a .rvt for Revit 2025"* (`tekton-author`, `go author
   --ifc`) or *"harden this for Revit"* (`/tekton-harden` → `hardened.ifc` +
   a delivery report) — or both.
4. In Revit: open the `.rvt`; or for the IFC **Insert → Link IFC** → the file
   → "Auto – Origin to Origin", then bind the shared parameters as the report
   explains.

---

## 5-minute quickstart — an electrical room `.rvt`, from nothing

Prove the whole chain works from a bare unzip with the system Python. From
the `plugin` folder (or the unzipped bundle root):

```bash
python3 skills/tekton-author/scripts/_bootstrap.py go author \
    --prompt "an electrical room with 6 panels" --target-version 2025 --out out/j1 --json
```

One call, one JSON on stdout. On a fresh cloud VM this returns in ~17 s with
`go.ready: true` (`tekton: READY | python 3.11 | engine bundled | genesis
verified …`), `result.files.combined = out/j1/prompt_room.rvt` plus a
`families/` folder of generated `.rfa`, `result.release` = *requested 2025 →
output 2025, "Revit 2025 and newer -- never an older Revit",
`target_support: certified-base`, `this_file: validated-not-certified (our
gate: VALID 0 errors / 0 warnings; Autodesk acceptance only when the
recipient's Revit / the Autodesk Viewer opens it)`*, and `result.status =
PROOF-ONLY (self-checks PASS; …)` with the stamps `PROOF-ONLY: walls+families
combination unverified` and `PROOF-ONLY, NOT-DELIVERABLE`. That is the honest
shape of every creation delivery: the file first, the version story, the
status line verbatim, the stamps after. Change the prompt (ratings, counts,
room size, `--target-version 2024`) and re-run: same command, new file.

The IFC chain is just as short — the bundled Eaton panelboard:

```bash
python3 skills/tekton-ifc/scripts/generate_ifc.py \
    --spec examples/eaton-panelboard/panel-spec.json \
    -o out/eaton-panelboard.ifc --validate
```

prints `score : 98.8/100`, `tier : Tier 1`, `schema : IFC4 errors=0`, and one
`IfcElectricDistributionBoard` named `PANEL-A` (Eaton-style, 480Y/277 V,
400 A bus, 42 spaces) with the full panel schedule as typed properties;
**Insert → Link IFC** puts it in *Electrical Equipment* with its data. (This
one needs the optional IFC extras — `/tekton-doctor --install` once.)

Or skip the terminal entirely — just tell Claude:

> /tekton-job Make me a Revit 2025 electrical room, 30 by 20 ft, 2500 A
> service, one main switchboard, two 400 A distribution panels and four
> lighting panels, and give me the delivery report.

## Everyday phrasing that works

- *"Make me an electrical room .rvt with a 1200 A switchboard and six panels
  — we're on Revit 2024."* → `tekton-author`, one `go author --prompt …
  --target-version 2024` call, file + honest status.
- *"Here's the IFC from Claude Design — turn it into a Revit 2025 project and
  tell me what each thing became."* → `go author --ifc … --target-version
  2025` (+ `/tekton-harden` if you also want the IFC linked).
- *"Move LP-2 to the north wall and delete DP-1 and everything fed from it in
  this .rvt."* → `tekton-edit` / `go author --rvt their.rvt --edit "…"`; the
  file keeps its release.
- *"Check this file before I send it."* / *"Will the walls actually show?"* →
  `/tekton-validate <file>` and `tekton-inspect`'s render check.
- *"Run the whole Area E electrical room job from this spec."* →
  `/tekton-job …` with the orchestrator + QA agents.

## Two rules Claude will keep repeating (they matter)

1. **A `.rvt` opens in its own Revit year and newer — never older; IFC has no
   version limit.** So Claude asks for the recipient's Revit year (Help →
   About) *before* building any `.rvt`/`.rfa`, builds natively for 2026,
   2025 or 2024, and for anything older hands you the file, one clear line,
   and an IFC beside it. Existing files keep the release they came in with.
2. **Deliver first, caveat after.** Every route hands over the file it was
   asked for; validator verdicts, PROOF-ONLY stamps and the open-cell caveat
   are stated plainly *with* the delivery, never instead of it — and "our
   validator passed" is never dressed up as "Autodesk accepted it". (For
   IFC: **Link IFC, don't "Open IFC"** — Insert → Link IFC keeps your panel
   data as parameters; File → Open IFC drops most of it.)

## Where things are

```
plugin/
├── .claude-plugin/plugin.json   (+ marketplace.json)  ← what makes it a plugin
├── skills/tekton-author/    ← create: SKILL.md + references + scripts (+ worked example inputs)
├── skills/tekton-edit/      ← edit an existing .rvt
├── skills/tekton-inspect/   ← validate / look inside / LOAD-vs-RENDER / audits
├── skills/tekton-native/    ← engine-level .rvt work (streams, records, self-checks)
├── skills/tekton-ifc/       ← the IFC workflow (SKILL.md + references + scripts + exporter asset)
├── skills/_shared/          ← the zero-install bootstrap every skill's _bootstrap.py loads
├── agents/                  ← job orchestrator, .rvt author, IFC hardening, QA
├── commands/                ← /tekton-job, /tekton-validate, /tekton-harden, /tekton-doctor
├── assets/genesis/          ← the certified composed bases: G_ABPD (2026), G_ABPD_2025, G_ABPD_2024
├── assets/schema_cache/     ← per-release class-schema caches (fast cold start)
├── lib/                     ← the "rvt" engine (found by the bootstrap; no install)
├── examples/                ← the two finished real IFC jobs
├── docs/                    ← honest-status table + fill-in job templates (companion docs)
└── scripts/validate_plugin.py   ← self-check of this plugin's own packaging and wording
```

If something doesn't work, ask Claude to run `python plugin/scripts/validate_plugin.py`
— it checks that every file the plugin refers to is present and well-formed,
and that none of these pages has drifted back to a stale capability claim.

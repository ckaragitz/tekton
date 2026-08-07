# tekton — the plugin that lets Claude run your Revit work

Give this to Claude and it can do the fiddly parts of a Revit job for
you: turn what you build in **Claude Design** into a file that **links into
Revit** with everything in the right category, in the right place, carrying
your panel-schedule data; **fix** an IFC that came in as frozen blobs at the
origin; **check** any deliverable before you send it; and **read or edit an
actual `.rvt`** file. You describe the job in plain English; the plugin has
the tools, the rules and the examples so Claude doesn't have to guess.

You do **not** need to be a developer. You do need Revit (your work
Autodesk account) to open the results.

---

## What's in the box

| Piece | What it does for you |
|---|---|
| **Skill `tekton-ifc`** | Everything IFC: author Revit-ready models in Claude Design, validate an `.ifc`, harden it (recover real positions and clean solids), and the Revit-side checklist. The path that works today for every job. |
| **Skill `tekton-native`** | Everything about real `.rvt` files: inspect what's inside, make a proven text/value edit, and run the safety checks. (Creating brand-new equipment inside a `.rvt` is still in progress — the skill will tell you honestly.) |
| **Commands** `/tekton-job`, `/tekton-harden`, `/tekton-validate` | One-line ways to run a whole job, harden a file, or check a file. |
| **Agents** (job orchestrator, IFC hardening, `.rvt` author, QA) | Behind `/tekton-job`: a project-manager agent hands the work to specialists and a separate QA agent checks the result — no builder grades its own work. |
| **Examples** (`examples/`) | Two finished real jobs to copy: the DDOT Coolidge Area E electrical room and the Eaton Pow-R-Line panelboard, with their delivery reports. |
| **Engine** (`lib/`) | The `.rvt` reader/writer (a Python package called `rvt`) that the `tekton-native` skill drives. Installs with one command. |

The two levels of "editable in Revit" — read this once so you're never
surprised: **Tier 1** (what an IFC gives you, and what this plugin delivers
today) means every panelboard, transformer and hanger lands in the **right
Revit category, at the right position, at true size, with your schedule
data as parameters** you can tag and schedule. It comes in as *DirectShape*
geometry — movable, sectionable, sheet-able — but with **no electrical
connectors, no circuits, no Revit-native Panel Schedule view**. **Tier 2**
(real families with working connectors and circuits) needs the Revit API and
is the next milestone; for now Claude gives you a "Tier-2 handoff package" so
whoever has Revit finishes the wiring in minutes.

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
print `✔ Validation passed`). Skills are namespaced, e.g.
`/tekton:tekton-job`; the engine installs with `pip install ./lib` (the
`tekton-native` skill runs this for you on first use).

## Install — Cowork

Cowork runs the same skills. Add the plugin's **skills folder** to your
Cowork skills: copy the whole `plugin/skills/` directory (both `tekton-ifc`
and `tekton-native`) into Cowork's skills location, keeping each skill in its
own folder with its `SKILL.md` at the top. Copy `plugin/lib/` alongside so
the `.rvt` scripts can find the engine (they look for it at `../lib/src`
next to the skills, or you can `pip install ./lib` in the Cowork sandbox).
The `.mcpb`/connector route is not needed — these skills run their own
scripts in Cowork's built-in code sandbox.

The first thing to say in a Cowork chat: *"Load the tekton-ifc skill and
install its requirements."* Cowork runs `pip install -r
skills/tekton-ifc/scripts/requirements.txt` in its Linux sandbox
(ifcopenshell ships a ready-made Linux wheel, so no compiler is needed).

## Install — claude.ai chat

claude.ai loads one skill at a time by upload. Zip a skill folder and add
it under **Settings → Capabilities → Skills** (or attach it in the chat where
your plan supports skills):

- For IFC work (nearly all jobs): zip `plugin/skills/tekton-ifc/` → upload.
- For reading/editing a `.rvt`: zip `plugin/skills/tekton-native/` **together
  with `plugin/lib/`** (the scripts need the engine) → upload.

Then just attach your file to the chat and describe the job — e.g. attach
the `.ifc` you exported from Claude Design and say *"validate and harden
this for Revit."* The skill runs its scripts in the chat's built-in code
sandbox.

## Using it with Claude Design

Claude Design is where you **build the model**; it usually does not run the
Python scripts. The `tekton-ifc` skill tells Claude exactly how to author
in Design so the export is Revit-friendly (metres, real object positions,
un-baked shapes, one tagged group per real-world part, clearances as data
not solid boxes) and installs the canonical exporter
(`skills/tekton-ifc/assets/ifc-export.js`) as `./ifc-export.js` in your
Design project. Workflow:

1. In a Design chat with the skill loaded, ask Claude to build or upgrade
   your 3D page "for Revit". It follows the tagging contract and installs
   the exporter.
2. Click **IFC** in the stage toolbar → `<name>.ifc` downloads.
3. Attach that `.ifc` in Claude Code / Cowork / claude.ai and run
   `/tekton-harden` (or just say "harden this for Revit"). You get back
   `hardened.ifc` + a delivery report.
4. In Revit: **Insert → Link IFC** → the file → "Auto – Origin to Origin";
   then bind the shared parameters as the report explains.

---

## 5-minute quickstart — the Eaton panelboard

Prove the whole chain works using the bundled example. In Claude Code
(plugin installed, engines installed as above), from the `plugin` folder:

```bash
mkdir -p out
python skills/tekton-ifc/scripts/generate_ifc.py \
    --spec examples/eaton-panelboard/panel-spec.json \
    -o out/eaton-panelboard.ifc --validate
```

You'll see the validator print `score : 98.8/100`, `tier : Tier 1`,
`schema : IFC4 errors=0`, and one `IfcElectricDistributionBoard` named
`PANEL-A` of type `Eaton Pow-R-Line 4 (style) - 400A MB - 42 space` — an
Eaton-style panelboard, 480Y/277 V, 400 A bus, 42 spaces, W 0.508 × H 1.372
× D 0.190 m, with the full panel schedule as typed properties. Open
`out/eaton-panelboard.ifc` in Revit with **Insert → Link IFC** and the panel
appears in *Electrical Equipment* at the origin with its data. Now edit
`examples/eaton-panelboard/panel-spec.json` (change the voltage, the name,
the number of circuits) and re-run: same command, new file, same clean
result — that is the "repeatable, parameterized" workflow.

Or skip the terminal entirely — just tell Claude:

> /tekton-job Build the Eaton Pow-R-Line panelboard from the example spec,
> validate it, and give me the delivery report.

## Everyday phrasing that works

- *"Here's the IFC from Claude Design — get it ready for Revit and tell me
  what each thing will become."* → validate + harden + delivery report.
- *"Check this file before I send it."* → `/tekton-validate <file>`.
- *"What's in this .rvt? List the levels and the panelboards."* → the
  `tekton-native` inspect path.
- *"Run the whole Area E electrical room job from this spec."* →
  `/tekton-job …` with the orchestrator + QA agents.

## Two rules Claude will keep repeating (they matter)

1. **IFC works in any Revit; a `.rvt` does not.** Revit can't open a `.rvt`
   saved by a *newer* Revit. IFC has no version limit. So the default
   deliverable is IFC, and if you ever want a `.rvt` Claude will first ask
   for your exact Revit version (Help → About).
2. **Link IFC, don't "Open IFC".** Insert → Link IFC keeps all your panel
   data as parameters; File → Open IFC is Autodesk's legacy path and drops
   most of it.

## Where things are

```
plugin/
├── .claude-plugin/plugin.json   (+ marketplace.json)  ← what makes it a plugin
├── skills/tekton-ifc/    ← the IFC workflow (SKILL.md + references + scripts + exporter asset)
├── skills/tekton-native/      ← the native .rvt workflow (SKILL.md + scripts)
├── agents/                 ← job orchestrator, IFC hardening, .rvt author, QA
├── commands/               ← /tekton-job, /tekton-harden, /tekton-validate
├── lib/                    ← the "rvt" engine  (pip install ./lib)
├── examples/               ← the two finished real jobs
├── docs/                   ← honest-status table + fill-in job templates (companion docs)
└── scripts/validate_plugin.py   ← self-check of this plugin's own packaging
```

If something doesn't work, ask Claude to run `python plugin/scripts/validate_plugin.py`
— it checks that every file the plugin refers to is present and well-formed.

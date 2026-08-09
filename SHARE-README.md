# tekton — private evaluation build (name provisional)

You're receiving this for a private evaluation. Please don't redistribute.
The feedback we want most: open one generated or edited file in your own
Autodesk® Revit® and tell us exactly what Revit says — the dialog text,
warnings, what is editable and what is not — together with your Revit year.

## What it is

A Claude plugin (skills + commands + a bundled pure-Python engine) that
**creates, edits, inspects, validates and converts** native Revit files
(`.rvt` / `.rfa`) and IFC — with no Revit install and no Autodesk seat
anywhere in the loop. You drive it in plain English from Claude Code,
Cowork or claude.ai; Claude Design is where you can model visually and hand
the IFC over. Revit stays your system of record for final QA; tekton does
the work up to that door and always hands you the file it was asked for.

## Install and use

Everything — install on each surface, the 5-minute quickstart, everyday
phrasing, the honest status — is in the **`README.md` inside the zip**
(`plugin/README.md` in the source tree). The one-liners:

    claude --plugin-dir ./tekton-plugin.zip          # try it straight from the zip (Claude Code)
    /plugin marketplace add ./tekton                 # or, unzipped: install permanently
    /plugin install tekton@tekton

Nothing else needs installing on the job path: the engine and the certified
project bases are bundled and run on the system Python 3.11+. Only IFC
*authoring/validation* wants optional extras (`/tekton-doctor --install`).

## What works today

- **Create** a Revit project from a prompt, an IFC (e.g. exported from Claude
  Design) or a spec — an electrical room with switchboard, distribution and
  lighting panels, transformers, walls — natively for **Revit 2026, 2025 or
  2024**. Claude asks your Revit year *first*: a `.rvt` opens in its own year
  and newer, never older. Older than 2024 → you still get the file, one clear
  line saying your Revit cannot open it, and an IFC beside it.
- **Generate equipment families** (`.rfa`) from catalog facts (panelboards,
  transformers, luminaires), load them, place them — into our bases or into
  a project **you** upload.
- **Edit an existing `.rvt`** you upload: move, retype, re-level, rename /
  re-mark / set values, delete with its dependents; the file keeps its own
  release and you get a change report.
- **Inspect and validate** any `.rvt` / `.rfa` / `.ifc` before you send it,
  including "will these elements actually render" (LOAD vs RENDER).
- **IFC**: author Revit-ready IFC from Claude Design, validate, harden
  (recover positions, clean solids), convert `.rvt` → IFC, and the
  Revit-side Link-IFC checklist.
- The exact input → output table, with evidence and caveats per cell, ships
  in the plugin docs; ask Claude "what can tekton route today".

## Honest status — read once, so nothing surprises you

- **Every file this build produces is stamped `PROOF-ONLY` in its manifest.**
  You always get the file; the stamp is a label, not a refusal. It stays
  until three gates clear: legal review of the format posture and naming
  (in progress), our own identity block in every file, and our own content
  catalogue.
- **"Our validator passed" is not "Autodesk accepted it".** Every output
  passes our validator with 0 errors before hand-over; only your Revit (or
  the free Autodesk Viewer) opening it is acceptance, and Claude states both
  separately. The composed project bases for 2026 / 2025 / 2024, walls,
  edits, family generation and family loading are accepted by Autodesk's
  reader today.
- **The one known open case:** *instances* of our own generated equipment
  families placed on our own new-project bases can trip Revit's audit on
  open — while the same families merely loaded, or placed into a project you
  supplied, open fine. Every equipment-room prompt produces that shape, so
  Claude says so on each affected delivery and can hand you shell + equipment
  as two coordinated files instead (`--strict`). If you hit it, the exact
  Revit dialog text is the single most useful thing you can send us.
- Circuits and native panel schedules are planned in the manifest, not yet
  authored as working Revit circuits.

Autodesk and Revit are registered trademarks of Autodesk, Inc.; "for use with
Autodesk® Revit®" describes compatibility, not affiliation.

# Installing the tekton plugin (optional — Track B)

You do **not** need this to test the files in `TEST-KIT/` — that's the main ask
(Track A: just open them in Revit). The plugin is Track B: it lets you *talk* to
tekton through Claude.

## What you need
- **Claude Code** (Anthropic's command-line assistant) — install from
  https://claude.com/product/claude-code (needs a Claude account; Pro plan works).
- **Python 3.10+** on your machine (`python3 --version` in a terminal to check).
- The `tekton-plugin/` folder from this kit (it's already unpacked — no unzipping).

## Load it
1. Copy the `tekton-plugin/` folder somewhere, e.g. your Desktop.
2. Open a terminal and start Claude Code with the plugin loaded:
   ```
   claude --plugin-dir ~/Desktop/tekton-plugin
   ```
3. First run only: Claude may ask to set up the Python environment for the
   plugin's tools — say yes.

That's it. Now just type requests in plain English (see the prompt list in
the email). The plugin's skills — **tekton-author**, **tekton-edit**,
**tekton-inspect** — kick in automatically based on what you ask.

## What works on your machine (honest boundary)

- **Everything runs standalone now** — including the part that used to need
  our lab: **creating a brand-new native `.rvt` from a plain-English prompt
  or an IFC works entirely on your machine.** Every build input ships inside
  the plugin (our own certified project base — no Autodesk content, no
  donor file, no internet). Also standalone: inspecting/validating any
  `.rvt` (including the test-kit files), describing what's in a file,
  listing panels and their properties, panel-schedule tables, and editing an
  existing file (move / rename / delete elements). The old "specimen
  ancestor not found" stop is gone.
- **The one honest caveat is the Revit VERSION.** Files tekton creates today
  are **Revit 2026 format**; Revit can open files from its own release or
  older, never newer — so **Revit 2025 or older cannot open a freshly
  created `.rvt` yet**. The Revit-2025-native path is in certification now.
  Meanwhile, if you tell the tool you run 2025 (it asks, or say
  "target Revit 2025"), it still builds, says so in one clear line, and
  writes an **IFC of the same design** beside the `.rvt` — any Revit can
  link/import that IFC today. Outputs remain PROOF-ONLY (research, not for
  a real job) until legal review completes.

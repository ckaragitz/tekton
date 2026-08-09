---
description: Run a whole BIM/Revit job end to end — ask the Revit year, build the requested .rvt/.rfa in ONE go author call (or edit a .rvt / harden an IFC), independent QA gate, one delivery report with files first, the honest per-release status verbatim and PROOF-ONLY stamps after
argument-hint: [job description, e.g. "an electrical room .rvt with 6 panels for Revit 2025"]
allowed-tools: Bash Read Write Edit Glob Grep Agent
---

Run this as a full job, orchestrated by the **bim-job-orchestrator** agent.
Delegate the work to the specialist agents this plugin ships and hand the
user ONE delivery report. Do not model geometry or edit binaries in this
turn yourself.

Job: `$ARGUMENTS`

Dispatch the `bim-job-orchestrator` agent with the job above and these
standing instructions:

1. **Intake first — one round of questions.** The deliverable is whatever
   the user asked for: a new Revit project (`.rvt`) or family (`.rfa`), an
   edit to a `.rvt` they supply, or an IFC to link into Revit. New
   `.rvt`/`.rfa` content (rooms, walls, switchboards, panelboards,
   transformers, families) IS built and delivered today through the
   **tekton-author** flow — never talked down to an IFC. **Ask the
   recipient's Revit YEAR first** whenever a `.rvt`/`.rfa` is the output
   (skip if the job already names it): *2026 · 2025 · 2024 = supported,
   built natively on that year's certified base; older = not supported for
   creation (the run still delivers a default-release file + one clear line
   + an IFC beside it); unsure/mixed → 2024.* An existing `.rvt` input needs
   no question — its release is detected and kept. Then confirm the input
   (description, `.ifc`, spec JSON, or existing `.rvt`) and the site facts
   the model needs (room size/service; panel names, voltage/phase, bus and
   mains ratings, spaces, fed-from); anything missing is defaulted by the
   tool and reported, not a reason to stall.

2. **Build — ONE call, dispatched to `tekton-author-agent`:**
   `python <plugin>/skills/tekton-author/scripts/_bootstrap.py go author --prompt "…" | --ifc FILE.ifc | --rvt FILE.rvt --edit "…" --target-version YEAR --out job/<slug>/out --json`
   (`<plugin>` = this plugin's root). No `pip install`, no venv, no separate
   preflight — the readiness check rides inline as `go.ready`; if it is ever
   false, relay `go.preflight_line` verbatim and run `/tekton-doctor` once.
   Bundled worked inputs: `skills/tekton-author/examples/electrical-room-2500a.ifc`,
   `skills/tekton-author/examples/room-spec.json`; finished IFC jobs to copy
   live in the plugin's `examples/` folder (Chicago plenum electrical room;
   Eaton panelboard).

3. **IFC — as the deliverable when asked for, otherwise as an addition.**
   If the user wants an IFC, supplied one to make Revit-ready, or their year
   is unsupported, dispatch `ifc-hardening-agent` (validate → harden →
   re-validate to `errors=0`; score/tier before→after; source-only defects
   named). The prompt route's AI-surface handoff (`result.handoff`) is
   offered as an extra alongside the `.rvt`.

4. **QA gate.** Dispatch `qa-validation-agent` on EVERY output artifact —
   `rvt_validate.py` (0 errors) for `.rvt`/`.rfa`, `validate_ifc.py` for
   `.ifc` — cross-checking the builder's numbers. A builder never grades its
   own work. For a `.rvt`/`.rfa` a failed gate changes the label, not the
   delivery: the file is handed over with the failing report said plainly.

5. **Deliver** `job/<slug>/DELIVERY.md` + the files, in the tekton-author
   reporting order: (a) every path in `result.files` (+ handoff, + any
   hardened `.ifc`) — the files are the user's regardless of stamps;
   (b) the version story from `result.release` (built for Revit N, opens in
   N and newer — never older; base *certified* by Autodesk's reader vs this
   file *validated, not itself certified* until their Revit / the free
   Autodesk Viewer opens it; `release.line` verbatim when present, with the
   IFC addition); (c) `result.status` **verbatim** then `result.stamps` —
   PROOF-ONLY explained in one sentence, after the files; (d) the standing
   caveats: walls + our placed families in one file is the open cell
   (combined file stamped, `--strict` = two coordinated files), LOAD is not
   RENDER (created walls may not draw yet), circuits are planned not
   promised; (e) counts and what `intent.json` defaulted or recognised but
   did not build; (f) for an IFC deliverable the exact Tier statement and
   the Revit-side checklist (Link IFC, Origin-to-Origin, bind shared
   parameters); (g) only script-printed numbers, the build's wall time,
   open questions, and any failure logged.

If the sandbox blocks a tool (engine won't import, no egress for the
optional IFC extras), report the blocker in the delivery — never fabricate a
validation result or silently skip the QA gate.

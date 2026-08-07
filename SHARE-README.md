# tekton — private evaluation build (name provisional)

You're receiving this for a private evaluation. Please don't redistribute.
Feedback wanted — especially: open one generated/edited file in real
Revit and tell us exactly what Revit says (warnings, errors, editability).

## What it is
An AI-driven layer that READS, CREATES, EDITS and VALIDATES native Revit
files (.rvt / .rfa) without a Revit install or seat — you drive it from
Claude (Design / Cowork / Code / chat). Revit stays your system of truth
for final QA; this automates the work up to that door.

## Install
    claude --plugin-dir ./tekton-plugin.zip        # try it in one command
or unzip and:  /plugin marketplace add ./tekton  ->  /plugin install tekton@tekton

## What works today (on YOUR files)
- Upload a project -> inspect, validate, audit, and EDIT it: delete (with
  dependents), rename/re-mark/re-parameter, move, retype, add elements.
- Panel schedules + load calcs (NEC-style), phase balancing, breaker sizing.
- IFC authoring / hardening / validation (Claude Design bridge).
- Generate equipment families (e.g. an Eaton panelboard) from catalog facts.
- CREATE new content into a base file YOU provide (--template-rvt yours.rvt);
  no template ships with this build — supply your own project/standards.

## Honest status
Every file this build generates is stamped PROOF-ONLY in its manifest.
Two gates remain before outputs are contractual deliverables: (1) legal
review in progress, (2) an in-house base document ("genesis") in progress.
Everything else here is real and self-verifying. Your Revit open is the
last-mile check we most want to hear about.

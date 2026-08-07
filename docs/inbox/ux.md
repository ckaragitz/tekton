# Stream UX — fast deterministic bootstrap + lean skill flow (problem B)

Date: 2026-08-04. Territory: `plugin/skills/_shared/**`, the four
`plugin/skills/tekton-*/SKILL.md` BODIES, `plugin/skills/*/scripts/_bootstrap.py`,
`plugin/commands/tekton-doctor.md`, `tests/test_bootstrap.py`, this record.

## What shipped

1. **`plugin/skills/_shared/tekton_env.py`** — the ONE shared bootstrap.
   - `plugin_root()`: walks UP from `os.path.abspath(__file__)` to the first
     dir containing `.claude-plugin/`. Never searches/globs/lists the
     filesystem. Proven from a copied mount-like path with spaces+parens.
   - `ensure_engine()`: inserts `<root>/lib/src` into `sys.path` (bundled
     engine WINS over any stale pip install), vendored-olefile fallback
     (`skills/_shared/_vendor`), sets `RVT_PLUGIN_ROOT` / `RVT_GENESIS_BASE`
     (setdefault, so user overrides win) and `PYTHONPATH` for children.
     NO pip, NO venv on the hot path.
   - `preflight()`: ONE call → `{python, engine (+facts_store), genesis_base
     (present + sha256 vs the shipped pin + revit_release), family_donor,
     specimen, out_dir, extras{numpy,ifcopenshell}, seconds, line}`. One
     readiness line, prefix `tekton: READY|NOT READY | …`. Measured 0.015 s
     internal / 0.09 s wall (budget was < 2 s).
   - `run_script()`: `_bootstrap.py run frontdoor.py author … --json` — runs
     the sibling skill script in the SAME interpreter with the engine ready
     (runpy, exact CLI semantics). This is the one-command job form.
   - `doctor()`: the OFF-hot-path one-time check; `--install` pip-installs
     ONLY the missing optional extras (numpy / ifcopenshell) on explicit
     request. Never touches Autodesk installs.
2. **Four `scripts/_bootstrap.py` shims** (author/edit/inspect/native,
   identical): locate `skills/_shared/tekton_env.py` by walking up from
   their own file, delegate; keep legacy names (`ensure_rvt`, `--env`
   export lines) so nothing existing breaks.
3. **Four SKILL.md bodies rewritten** (frontmatter untouched — verified
   byte-identical against the pre-change `rev-revit.zip` archive for
   author/edit/inspect; native reproduced exactly, and the built zip's
   frontmatter passes the no-angle-brackets + ≤1024-char scan for all 5
   skills incl. tekton-ifc). New shape per body: THE DELIVERABLE RULE up
   top; version question FIRST on creation; ONE readiness command; ONE job
   command whose `--json`/printed report IS the summary to relay;
   family-donor-missing → ask the user for ONE thing (their Revit version +
   one `.rfa`/`.rvt`); no task lists; no exploratory shell; honest caveats
   stated WITH the delivery, never instead of it.
4. **`plugin/commands/tekton-doctor.md`** + the scripts entry
   (`_bootstrap.py doctor [--install]`).
5. **`tests/test_bootstrap.py`** — 8 tests, all green: copied-mountlike-path
   resolution; engine import under `python -I -S` (zero site-packages =
   zero pip, vendored olefile); readiness-line format for all four skills;
   the `run` launcher executing the front door's prompt route from the copy;
   family-donor bundled/user-supplied/missing sources; legacy `--env`; and
   the HARD-RULE guard (no path-literal Autodesk install dirs anywhere in
   plugin/).

## Timings (cold, system python 3.9.6, no venv, 3 runs each)

| Path | seconds |
|---|---|
| NEW preflight alone (`_bootstrap.py`) | 0.09 / 0.09 / 0.10 wall (0.015 internal) |
| NEW preflight + `run frontdoor.py author --prompt … --json` | 0.55 / 0.43 / 0.43 |
| OLD mechanical fallback (`eval $(_bootstrap --env)` + direct script) | 0.28 / 0.38 / 0.32 |

The field problem was never the mechanical exec time — it was the COMMAND
COUNT and the network: ~17 setup commands (filesystem hunting for the
plugin, task boards, `pip install -e ./lib` + PyPI fetches of
olefile/numpy/ifcopenshell, per session). New flow: **2 commands, ~0.5 s,
zero network, zero installs.** Two facts that make the pip route strictly
worse than the bundle: `plugin/lib` declares `requires-python >= 3.11`
(pip refuses on the macOS system 3.9 this was measured on — the bundled
source RUNS there), and this sandbox has no PyPI egress at all (the field
Cowork session burned time on exactly that). `pip install -e ./lib` is
gone from every skill body; the only sanctioned install is
`doctor --install` for the optional IFC extras.

## HARD-RULE sweep (Autodesk installation paths) — findings

Grep of the whole plugin for `ProgramData|Program Files|/Applications/
Autodesk|Family Templates|RVT 20xx` found 3 files; disposition:

- **REMOVED** (2 literal install paths, edited at the sync SOURCE
  `skills/tekton-ifc/references/mep-class-map.md`, synced into the plugin):
  - `` `C:\ProgramData\Autodesk\RVT <year>\importIFCClassMapping.txt` `` →
    now "Revit ships its own default `importIFCClassMapping.txt`, reachable
    through that same dialog — the USER loads it in Revit; we never read
    the Revit install".
  - `` `C:\ProgramData\Autodesk\RVT <year>\exportlayers-ifc-IAI.txt` `` →
    now "Revit's own `exportlayers-ifc-IAI.txt` mapping file".
- **False positives, left alone**: `plugin/lib/src/rvt/famgen/skeleton.py:1428`
  ("family templates carry MORE…" — format knowledge in a docstring, not a
  path; src/rvt is off-territory anyway); `tekton-ifc/references/
  revit-versions.md` "RVT 2015+" (a viewer *format-support* note, not a path).
- A probe scan (`listdir|glob|walk|exists…` near "autodesk") over every
  plugin `.py` found nothing. `tests/test_bootstrap.py::
  test_no_autodesk_install_paths_in_plugin` now enforces the rule
  permanently (path-literal patterns, so prose that NAMES the prohibition
  stays legal).
- Family-donor / specimen status in preflight comes ONLY from
  `$RVT_FAMILY_DONOR` / `$RVT_SPECIMEN_ANCESTOR` (user-supplied file) or
  the bundled `assets/family/` / `assets/genesis/*.specimen.rvt` dirs.

## Withholding / refusal language removed from the skill bodies (the list)

From **tekton-author/SKILL.md**:
1. "Say the last row out loud on every job. Nothing in this skill lets you
   call a file a deliverable; the manifest's status gate decides, and today
   its honest answer is PROOF-ONLY." (lecture-first framing that field
   sessions read as do-not-hand-over)
2. §1 status-box row "Every output's deliverability … outputs are internal
   proofs, not third-party deliverables — the manifest says so and so do
   you" (same; stamps are now defined as LABELS delivered WITH the file)
3. "Show the user the intent … and the coverage block BEFORE promising
   anything" (pre-delivery gate → now relayed WITH the delivery)
4. "the honest, always-available deliverable of the prompt path here is
   (a): the handoff" (substituted the handoff/IFC for a requested .rvt)
5. "if it is older than 2026, the version-agnostic deliverable is the IFC
   route (tekton-ifc)" (IFC as replacement → version asked FIRST, IFC
   offered as an ADDITION)
6. "Don't: call any output a deliverable, 'clean', or 'ready' while the
   manifest says PROOF-ONLY" (kept as label-honesty, reframed so a stamp is
   never a reason to withhold the file)

From **tekton-native/SKILL.md**:
7. The file's accidental FULL DUPLICATION (frontmatter + body repeated,
   three overlapping section sets) — deduplicated.
8. "We cannot yet reliably drop a brand-new family instance into a .rvt …
   the guaranteed route is IFC via the tekton-ifc skill."
9. Routing row "Author a new model from a description … → Use tekton-ifc
   (IFC) — the shipped, working path" (steered .rvt requests to IFC;
   creation now routes to the tekton-author front door)
10. "Don't claim element creation works or promise a family instance /
    circuit / a .rvt from an IFC — those are §6 IN-PROGRESS / not started."
    (outdated AND refusal-shaped)
11. "This is exactly why IFC (tekton-ifc) is the version-agnostic default"
    (replacement steering)
12. "Present it as a preview/plan, not a deliverable." (creation section)

From **tekton-edit / tekton-inspect**: no withholding logic existed; removed
only the per-session setup ceremony (§0 pip/eval blocks) and replaced
"if setup fails, say so and stop" with the NOT-READY one-line relay.

Every body now carries THE DELIVERABLE RULE verbatim-intent: built file
ALWAYS written and handed over; PROOF-ONLY stamps are labels stated AFTER
the handover; the only non-delivery is a genuinely impossible build reported
as ONE line naming the single missing input; IFC only ever as an addition.

## Verification pasted (DONE gates)

- `python tools/sync_plugin.py` → "synced … deny-audit clean; assets
  verified (genesis base == frontdoor pin) / ✔ Validation passed /
  rebuilt tekton-plugin.zip (2634 KB)".
- `claude plugin validate plugin/` → "✔ Validation passed" (exit 0).
- Raw-byte zip scan of every SKILL.md frontmatter in tekton-plugin.zip:
  ```
  skills/tekton-author/SKILL.md: '<'x0 '>'x0 description=696 bytes -> OK
  skills/tekton-edit/SKILL.md: '<'x0 '>'x0 description=529 bytes -> OK
  skills/tekton-ifc/SKILL.md: '<'x0 '>'x0 description=984 bytes -> OK
  skills/tekton-inspect/SKILL.md: '<'x0 '>'x0 description=518 bytes -> OK
  skills/tekton-native/SKILL.md: '<'x0 '>'x0 description=875 bytes -> OK
  ZIP FRONTMATTER CONSTRAINT CHECK: PASS
  ```
- `tests/test_bootstrap.py`: 8 passed.
- Full suite: see BRANCH STATE (run at close).

## Proposed patches OUTSIDE my territory (for the orchestrator)

1. **`tools/*.py` (synced into every skill's `scripts/`)** — the skill-side
   copies cannot find the bundled engine (their `ROOT/lib/src` guess
   resolves under `skills/<skill>/`), which is WHY the launcher form exists.
   Adding this after each script's existing `sys.path` inserts makes the
   task-mandated direct form (`python scripts/frontdoor.py author … --json`)
   work pipless too (exact patch, e.g. tools/frontdoor.py after line 57):
   ```python
   try:                                  # plugin-skill layout: scripts/_bootstrap.py
       if HERE not in sys.path:
           sys.path.insert(0, HERE)
       from _bootstrap import ensure_rvt as _ensure_rvt
       _ensure_rvt()                     # bundled engine + RVT_* env, no pip
   except ImportError:
       pass                              # repo / lib-tools layout: inserts above suffice
   ```
   Same 6 lines for rvt_job.py, rvt_edit.py, rvt_validate.py, ifc_intent.py,
   seed_audit.py, panel_schedule.py, spec_to_rvt.py (their HERE names vary).
2. **`tests/test_engine.py:30`** — pre-existing collection error, rename
   fallout: `SCRIPTS = os.path.join(ROOT, "skills", "revit-bridge",
   "scripts")` → `os.path.join(ROOT, "skills", "tekton-ifc", "scripts")`
   (`ModuleNotFoundError: bridge_lib` breaks bare `pytest tests`; run with
   `--continue-on-collection-errors` until fixed).
3. **`src/rvt/ifc/intent.py:74`** — `import numpy as np` at module top makes
   numpy a hard dep of the whole front door (even the no-IFC prompt route).
   Make it lazy (import inside the functions that use it, or a
   try/except with a clear one-line error) so `author --prompt` runs on a
   numpy-less python. Until then preflight reports `extras.numpy` and
   doctor installs it on request; Cowork sandboxes ship numpy.
4. **root `skills/tekton-ifc/SKILL.md`** (sync-mirrored, ifc steward's file):
   §2 route row "User wants real families, connectors, circuits, or a .rvt
   file → … do NOT promise `.rvt`" and §3 rule 8 "Deliver IFC." predate the
   native front door and contradict THE DELIVERABLE RULE — reword to route
   `.rvt` requests to **tekton-author** (ask the Revit version first) and
   keep IFC as the version-agnostic ADDITION.
5. **`plugin/commands/tekton-job.md` / `tekton-validate.md` /
   `tekton-harden.md` and `plugin/README.md`** still open with per-session
   `pip install` instructions — point them at
   `skills/<skill>/scripts/_bootstrap.py` (readiness) and `/tekton-doctor`
   (one-time extras) instead.
6. **Conventions for streams A/C** (adopted by preflight today):
   a bundled constructed family donor lands in `<plugin>/assets/family/`
   (any `.rfa`/`.rvt` there reports `family-donor bundled`); a bundled
   specimen lands as `<plugin>/assets/genesis/<name>.specimen.rvt`;
   user-supplied equivalents via `$RVT_FAMILY_DONOR` /
   `$RVT_SPECIMEN_ANCESTOR`. A 2025-release genesis base + donor slots
   straight into the same preflight line (`genesis verified (Revit 2025)`).

## BRANCH STATE

- No git repo in this working copy; all changes are on the shared tree at
  `/Users/ck/dev/things/tekton`. Files touched (mine): `plugin/skills/
  _shared/tekton_env.py` (new), `plugin/skills/{tekton-author,tekton-edit,
  tekton-inspect,tekton-native}/scripts/_bootstrap.py` (rewritten),
  `plugin/skills/{tekton-author,tekton-edit,tekton-inspect,tekton-native}/
  SKILL.md` (bodies only), `plugin/commands/tekton-doctor.md` (new),
  `tests/test_bootstrap.py` (new), `skills/tekton-ifc/references/
  mep-class-map.md` (2 lines, HARD-RULE removal at the sync source),
  `docs/inbox/ux.md` (this record). Plus `tools/sync_plugin.py` RUN
  (not edited): plugin mirrors + `tekton-plugin.zip` rebuilt.
- DONE gates: preflight 0.09 s wall (<2 s) ✓; one-command skills ✓; doctor
  command ✓; sync green + `claude plugin validate` ✔ ✓; zip frontmatter
  constraint check PASS (pasted above) ✓.
- Full suite at close: `pytest tests -q --continue-on-collection-errors`
  was LAUNCHED and was still executing after ~35 min when this record
  closed (the large-file ECC/roundtrip tests dominate); the run continues
  in background task `bqj6x21g0` (output:
  `/private/tmp/claude-502/-Users-ck-dev-things/91c616fc-3cee-49e7-be61-74bc4edd8fdb/tasks/bqj6x21g0.output`)
  — read that file for the final count; NO count is claimed here that was
  not observed. Verified before close: `tests/test_bootstrap.py` 8/8 green
  (three separate runs); bare `pytest tests` aborts collection on the
  PRE-EXISTING `tests/test_engine.py` rename fallout (patch 2 above), so
  use `--continue-on-collection-errors` until it lands.
- Open for the orchestrator: apply patches 1–5; confirm stream A adopts the
  donor/specimen conventions (6).

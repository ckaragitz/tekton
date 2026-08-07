# tekton — working guide for coding sessions

You are in **tekton**: a pure-Python interoperability engine that reads,
creates, edits, validates, and converts Autodesk Revit `.rvt` / `.rfa`
containers **without a Revit install, an Autodesk seat, or APS**. Revit is
the last-mile *deliverable* format — a licensed engineer opens our output
for QA. Read this file fully before touching anything; then read
`KNOWLEDGE.md` (institutional memory) and `TRACKER.md` (the work queue).

---

## 1. Hard rules (non-negotiable — they exist because breaking each one cost days)

1. **The deliverable rule.** Status gates (`PROOF-ONLY`, honesty stamps,
   open-bug labels) are **labels, never refusal logic**. Every route always
   *delivers* the built `.rvt`/`.rfa`, stamped, with caveats *after*
   delivery. Never withhold output; never silently swap an IFC for a
   requested `.rvt`.
2. **Never read any Autodesk installation directory** — `ProgramData/Autodesk`,
   `Program Files/Autodesk`, `RVT 20xx/Family Templates`, `/Applications/Autodesk`.
   A runtime tripwire enforces this on the front door. The product's whole
   point is *not needing* Revit.
3. **Zero donor bytes in anything shipped.** We *mine* laws from Autodesk
   files (samples, templates) and *author our own* equivalents; we never
   copy their content into product output. Sample-derived material lives
   only in quarantined, git-ignored dirs (`samples/`, `vendor/`,
   `extracted/`) and dev-only probes under `experiments/` (stamped
   `PROOF-ONLY`). `tools/sync_plugin.py`'s deny-audit blocks it from the
   plugin bundle.
4. **Autodesk's reader is the arbiter, not our validator.** "Validator green"
   is *not* acceptance. A file is *certified* only when
   `viewer.autodesk.com` (or desktop Revit) loads it, and the verdict is
   recorded in `docs/coverage/viewer-certified.json`. Every viewer round
   goes through `tools/probe_batch.py`: **a certified base + a
   byte-identical control per batch**; a base must itself be certified
   *before* you build on it; a failed control voids the round.
5. **The reduction law** (`src/rvt/reduce_law.py`): when removing content, a
   referrer of removed content is deleted *with* it or left
   *byte-identical* — never "neutralised". `assert_edit_free` gates every
   reduction.
6. **Keep this repo private.** It carries counsel-review material (see
   `docs/product/COUNSEL-BRIEF.md`: author strings C1, the per-release
   schema/ESSchema corpora C4, footer token C5). Nothing here goes to a
   public remote.

## 2. Setup and the commands you'll actually use

```bash
python3.11 -m venv .venv && .venv/bin/pip install -e .   # package name: rvt (src/rvt)
.venv/bin/python -m pytest tests/test_frontdoor.py -q     # ALWAYS run python from repo root via .venv
```

- **Tests:** the full suite is ~1,700 tests and takes ~25 min; **do not run
  it casually or concurrently** (see `docs/inbox/SUITE-COORDINATION.md` —
  one canonical run at a time; contributors run their *stream-local* test
  files). `RVT_SKIP_LARGE=1` skips sample-size cases. Some tests
  self-skip when `samples/` is absent — that's expected in a fresh clone.
- **The front door** (one entrypoint, three inputs — exactly one of
  `--prompt` / `--ifc` / `--rvt --edit`):
  ```bash
  .venv/bin/python tools/frontdoor.py author --prompt "an electrical room with 6 panels" --out out/demo --json
  .venv/bin/python tools/frontdoor.py author --ifc room.ifc --target-version 2025 --out out/r25
  .venv/bin/python tools/frontdoor.py author --rvt project.rvt --edit "move DP-1 to 3,1,4.66" --out out/e
  ```
- **The permutation router** (any of {prompt, ifc, rvt, rfa, spec} in → {rvt, rfa, ifc} out):
  `.venv/bin/python tools/route.py matrix` (the honest capability table) /
  `route explain ...` / `route run ...`. Cells are declared in
  `src/rvt/frontdoor/matrix.py`; `verify_evidence()` fails the suite if a
  "works" claim loses its evidence.
- **Plugin build:** `.venv/bin/python tools/sync_plugin.py` mirrors
  `src/` + skills into `plugin/`, runs validation + the deny-audit, and
  rebuilds `tekton-plugin.zip` at the repo root (git-ignored; regenerate,
  don't commit). `--check` = report drift only, exit 1 on any. **Run it
  after every change under `src/` or `skills/`** — the plugin ships source
  copies.
- **Viewer rounds:** `tools/probe_batch.py` (stage/check batches; the
  orchestrating human/session uploads), `tools/serve_acceptance.py`
  (serves `experiments/acceptance/` on 127.0.0.1:8765 for browser upload).

## 3. Map

- `src/rvt/` — the engine. Container/codec layers (CFB → framed gzip →
  records), `schema*` (every file carries its own class schema in
  `Formats/Latest`; decode against *it*), `validate.py` (layered validator,
  corpus-law rules E1–E3), `versions/` (release detection from
  `BasicFileInfo`, by-name framing ordinals, `records32` for the 2023
  32-bit-id era, `KNOWN_RELEASES`), `genesis/` (base composition +
  per-release port layers), `frontdoor/` (`build`, `standalone`,
  `release_ctx`, `router`, `matrix`, `prompt_intent`, `ifc_out`),
  `famgen/` (family generation: `factory`, `loader`, `famdoc_adoc`,
  `birthright`), `famload.py` (four-registry family loading),
  `mutate`/`manipulate` (create/edit/delete), `ifc/` (`intent` resolver,
  `steplite` — stdlib-only IFC reader, no ifcopenshell needed), `convert/`
  (rvt→ifc, extract/edit family, add_to_project, merge_ifc), `reduce_law.py`.
- `tools/` — CLIs and campaign drivers (`frontdoor.py`, `route.py`,
  `sync_plugin.py`, `probe_batch.py`, `genesis_*.py` per release,
  forensic instruments like `terminal_diff.py`, `fifth_surface.py`).
- `plugin/` — the distributable: `skills/` (`tekton-author`, `tekton-edit`,
  `tekton-inspect`, `tekton-ifc`, `tekton-native`, `_shared/tekton_env.py`
  = zero-pip bootstrap + one-call `go` dispatch), `commands/`, `agents/`,
  `assets/genesis/` (the certified composed bases G_ABPD /_2025 /_2024),
  `assets/schema_cache/`, `lib/` (mirrored source). Edit **sources**
  (`src/`, `skills/`), never `plugin/lib` directly — sync overwrites it.
- `docs/inbox/` — one record per workstream (see §4). `docs/product/` —
  user-facing truth (`PERMUTATION-MATRIX.md`, `HONEST-STATUS`,
  `SURFACE-PLAYBOOK.md`, `MCP-PATH.md`, `COUNSEL-BRIEF.md`).
  `docs/writer/` — format facts per release. `docs/coverage/viewer-certified.json`
  — the certification ledger. `docs/inbox/genesis-audit.md` — the running
  verdict log (`## ORCHESTRATOR VERDICTS #N`).
- Git-ignored on purpose: `samples/ vendor/ extracted/` (third-party),
  `experiments/**/*.rvt|rfa` (5+ GB of probes), caches, zips.

## 4. How work is done here (process)

- **Orchestrator + parallel streams.** Substantial work is chartered as
  streams with a *territory* (files it may touch), a checkable *DONE*, and
  a *record*. **Only the orchestrator edits `TRACKER.md`**; streams propose
  follow-ups in their final report or a `docs/inbox/<slug>.md`.
- **Every stream writes `docs/inbox/<stream>.md`**: what was built, the
  evidence (numbers, not adjectives), findings, open questions, and a
  closing **`BRANCH STATE`** block (files written, gates, what's staged vs
  shipped). Durable lessons go to `docs/inbox/learned-<slug>.md`; the
  orchestrator merges them into `KNOWLEDGE.md`.
- **No cross-voice writes**: never write into another stream's record in
  its voice; additions elsewhere go under a header naming *your* stream.
- **Territory discipline**: put new code in new modules; deliver edits to
  shared/hot files (`tools/frontdoor.py`, `plugin/skills/*/SKILL.md`,
  `src/rvt/frontdoor/base.py`, `src/rvt/versions/`) as patches in your
  record unless you own them this round. Mutating tools that write shared
  experiment dirs take a pid lockfile.
- **Evidence discipline**: single-variable experiments with matched
  pass/fail pairs; controls in every batch; an instrument bug voids the
  readings taken with it (re-run, don't reinterpret); "faster" needs a
  measured before/after from a bare environment.
- **Commits**: plain descriptive messages about what the change does.
  Regenerate rather than commit build artifacts. Never commit anything from
  the ignored third-party dirs, and never a presenter cheat sheet
  (`ANSWER_KEY.md`, `DEMO_RUNBOOK.md`, `demo-talk-track.md`).

## 5. Where things stand (read `KNOWLEDGE.md` for the full arc)

Certified by Autodesk's reader: composed genesis bases for **2026/2025/2024**
(2023 base certified, compose pending); native creation of projects +
walls (render) + edits incl. foreign files; family **generation** (`.rfa`);
loading any Revit-born `.rfa` and extract→place onto our bases; our
generated equipment placed **into existing/pristine projects**
(`add_to_project`). Two format laws found and fixed forever: the mandatory
64-byte `0x0f3f` unit footer blob, and the D1–D5 corpus laws.
**The one open cell:** *our generated* families + placed instances on
*our composed* bases fail Autodesk's audit while byte-equivalent-by-every-
instrument variants pass — 26 single-variable rounds are logged in
`docs/inbox/genesis-audit.md` (#31–#48); the next signal is desktop Revit's
own error dialog (`experiments/terminal/REVIT-CHECK-KIT.md`). Don't
re-suspect an exonerated axis without new evidence — check the ledger first.

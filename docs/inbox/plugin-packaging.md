# inbox — plugin-packaging (tekton skills + genesis-base asset + sync guards)

Stream: **plugin-packaging** (2026-08-04). Charter: ship tekton's
capabilities as SKILLS with bundled scripts inside `plugin/`, wire the
front door into the flagship skill, mirror the new engine modules, add the
certified genesis base as a plugin ASSET, keep `--check` / plugin-validate
green, and rebuild the zip. Territory kept: `plugin/skills/tekton-*/**`,
`plugin/assets/**`, `tools/sync_plugin.py`, `tests/test_plugin_sync.py`
(extended), this file. Also touched, by explicit instruction / packaging
necessity (called out below): `plugin/.claude-plugin/plugin.json` +
`marketplace.json` prose (say tekton; name left `rev-revit`), and the
sync-owned copies under `plugin/lib/tools/`, `plugin/skills/rvt-native/
scripts/rvt_job.py`, `plugin/marketplace.json` (derived by the sync). No
existing `src/rvt/*.py` or existing tool edited except `tools/sync_plugin.py`.

## Result in one screen

* **Three skills shipped and validating.** `plugin/skills/tekton-author/`
  (THE FLAGSHIP: the three input paths through `scripts/frontdoor.py`),
  `tekton-edit/` (manipulate an existing `.rvt` — the rvt_edit verbs + the
  ops door + the reduction-law note), `tekton-inspect/` (validate /
  LOAD-vs-RENDER / seed audit / panel schedules). tekton-author carries the
  five references (`TAGGING-CONTRACT.md`, `CATALOG-FACTS.md`,
  `PROMPT-TO-IFC.md`, `GENESIS-BASE.md`, plus `CRUD-COVERAGE.md` = the
  honest 28×6 table from `docs/coverage/matrix.json`) and the two IFC worked
  inputs. The old `rvt-native` skill is untouched and functional;
  tekton-author supersedes it in the docs.
* **`claude plugin validate plugin/` → ✔ Validation passed**;
  `plugin/scripts/validate_plugin.py` → **PASS (22 assertions)** — every
  backticked plugin-relative path in the new markdown resolves;
  `tests/test_plugin_sync.py` → **7 passed** (2 pre-existing + 5 new
  packaging guards); `rev-revit.zip` rebuilt (3.8 MB; exactly one `.rvt`
  inside = the genesis base asset). Full suite: see BRANCH STATE.
* **The certified genesis base is a plugin ASSET.**
  `plugin/assets/genesis/G_ABPD.rvt` (+ `G_ABPD.compose.json` = the
  composer's `G_ABPD.manifest.json` under the brief's name, and a
  provenance `README.md`). The sync copies it opt-in by exact path (exempt
  from the BINARY_EXT filter), DENY-audits its path, verifies it
  byte-identical to the source, and **cross-checks its sha256 against the
  front door's pin** (`src/rvt/frontdoor/assets/genesis_base.json`) — the
  plugin can never ship a base the front door would refuse. Verified: from
  the plugin, `frontdoor author` with `RVT_GENESIS_BASE` (emitted by the
  skills' `_bootstrap.py --env`) resolves it as
  `certified_genesis_base: true, pinned: true, is_autodesk_sample: false`.
* **sync_plugin.py grew four guards**: OPTIONAL sources (a script another
  stream is still building — `frontdoor.py` — is copied when present and
  skipped WITHOUT drift, so `--check` stayed green before, during and after
  its landing); the whole-tree DENY audit (asserts zero quarantined /
  reference files anywhere under `plugin/`, not just at copy time); asset
  verification (byte-equality + the frontdoor pin); and a derived
  `plugin/marketplace.json` convenience copy (fixes the plugin's own
  validator's pre-existing failure — identical to
  `.claude-plugin/marketplace.json` by construction). The zip keeps
  excluding example/proof `.rvt`s and re-adds `assets/` explicitly.

## What the three routes actually do FROM THE PLUGIN (measured, not assumed)

Every claim below was run with the plugin's own bundled engine
(`PYTHONPATH=<plugin>/lib/src` + `RVT_PLUGIN_ROOT` + `RVT_GENESIS_BASE`,
i.e. `eval "$(python skills/tekton-author/scripts/_bootstrap.py --env)"`),
against copies of the scripts sitting in the skills' `scripts/` dirs:

| route | plugin-standalone | evidence |
|---|---|---|
| `author --prompt … --handoff-only` | **WORKS** — intent.json + scene-brief.json + HANDOFF.md + PROMPT_TO_IFC.md + manifest, 0.2 s | status `HANDOFF-ONLY (...)` |
| `author --prompt …` (with fallback build) | intent + handoff written; the BUILD stops honestly at the specimen ancestor | status `FAILED (build crashed: BaseError: specimen ancestor R5 not found … (pass --specimens <path>))` |
| `author --ifc examples/electrical-room-2500a.ifc` | intent resolved (12 equipment / 4 walls / 8 feeders, family plan by the Pset join key); the BUILD stops at the same two research inputs | same FAILED status; `families built: 0` (donor absent) |
| `author --rvt <file> --edit '{"ops":[{"op":"set-level",...}]}'` | **WORKS end to end** — edited `.rvt` + validation JSON + job manifest, hard gates PASSED, output re-validates VALID 0 errors, L2 elevation 12→13 ft confirmed | status `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)` |
| `ifc_intent.py intent`, `rvt_validate.py`, `render_inspect.py`, `rvt_edit.py info/deps`, `seed_audit.py`, `panel_schedule.py`, the famgen catalog | **WORK standalone** | outputs recorded in the skill SOPs |

And the same IFC route in the RESEARCH environment (repo root, where the
research inputs exist) completes end to end in 15.6 s: 8 generated
families all `ok` (Eaton PRL2X ×5, PRL1X ×1, V48M28T4916, house 2500 A
switchboard), combined `.rvt` 663 KB **VALID 0 errors**, circuits planned +
named-blocked, degradations listed, status **PROOF-ONLY** with the two
stamps (`walls+families combination unverified`; `NOT-DELIVERABLE`, G1:
3,062 Autodesk-derived elements). The skill's worked example A is that run.

## THREE PACKAGING FINDINGS the orchestrator should act on (exact, with fixes)

### 1. A plain `pip install ./lib` DROPS the engine's data files (real defect)

The bundled engine's `pyproject.toml` uses `packages.find where=["src"]`
with NO package-data, so a non-editable install omits every non-`.py`
file: the **manufacturer facts store** (`rvt/famgen/facts/**/*.json`,
`LICENSE_NOTES.md`) and the **front-door pin + handoff docs**
(`rvt/frontdoor/assets/genesis_base.json`, `rvt/frontdoor/PROMPT_TO_IFC.md`).
Reproduced: fresh venv, `uv pip install --no-deps plugin/lib` →
`python -m rvt.famgen.catalog list` → `CatalogError: facts directory
missing: …/site-packages/rvt/famgen/facts`. The **editable** install
(`pip install -e ./lib`) and the `PYTHONPATH=lib/src` fallback both keep
them, so every tekton skill's Setup now prescribes `pip install -e ./lib`
(+ the `eval $(_bootstrap.py --env)` fallback) and says why.
**Fix (2 lines, plugin/lib/pyproject.toml — the packager's file, not
mine; not applied):**

```toml
[tool.setuptools.package-data]
rvt = ["famgen/facts/**/*.json", "famgen/facts/**/*.md",
       "frontdoor/assets/*.json", "frontdoor/*.md"]
```

### 2. rvt.frontdoor locates its reused build code by `<repo_root>/tools/` (plugin shim added)

`rvt.frontdoor.build.load_ifc_room_module()` opens `os.path.join(repo_root(),
"tools", "ifc_intent.py")` and `edit.load_job_module()` tries
`<repo_root>/tools/rvt_job.py` (then `<RVT_PLUGIN_ROOT>/skills/rvt-native/
scripts/rvt_job.py`). `repo_root()` = three levels up from the package when
`<cand>/src/rvt` exists — which in the plugin's bundled-source layout is
`plugin/lib` — so it looked for `plugin/lib/tools/ifc_intent.py` and failed
(`status FAILED (tools/ifc_intent.py not found at …/plugin/lib/tools/…)`).
**Shim (mine, in sync_plugin.py):** the front-door engine scripts are ALSO
mirrored to `plugin/lib/tools/` (`LIB_TOOLS_SHIM` — frontdoor, ifc_intent,
rvt_job, probe_batch, spec_to_rvt, ifc_to_spec, seed_audit, panel_schedule,
genesis_compose, rvt_validate, rvt_edit; byte-identical, test-asserted), and
`rvt_job.py` was ALSO added to `skills/rvt-native/scripts/` (their documented
`RVT_PLUGIN_ROOT` lookup path). With the shim the build gets past module
loading. **Requested fix in `src/rvt/frontdoor/{build,edit}.py` (frontdoor
stream): resolve those two modules FIRST beside the running script**
(`os.path.dirname(os.path.abspath(sys.argv[0]))` — the plugin colocates
`ifc_intent.py`, `rvt_job.py`, `probe_batch.py` and their siblings NEXT TO
`frontdoor.py` in `skills/tekton-author/scripts/`), then `$RVT_TOOLS_DIR`,
then `<repo_root>/tools/`. Then the `lib/tools/` shim and the
`RVT_PLUGIN_ROOT` requirement both go away — delete `LIB_TOOLS_SHIM` from
`tools/sync_plugin.py` at that point.

### 3. The families→placement BUILD is not yet plugin-standalone: two unbundleable research inputs

Even with the shim, `author --ifc/--prompt` cannot COMPLETE from the plugin
alone, for two content reasons packaging cannot fix (and correctly did not
paper over — the manifest names both):

* **The family-file FORMAT DONOR.** `rvt.famgen.skeleton.emit_family_rfa`
  carries `Formats/Latest` + the family `Global/Latest` (ADocument) from a
  real 2026 family container: `DEFAULT_DONOR = vendor/phi-ag-rvt/examples/
  Autodesk/racbasicsamplefamily-2026.rfa` = **Autodesk's sample family**.
  It is exactly the class of third-party content the DENY list keeps out of
  the plugin, so it is NOT bundled and the F stage from the plugin builds 0
  families (`FileNotFoundError: …/plugin/lib/vendor/phi-ag-rvt/…rfa`). This
  is TRACKER G4b / the family-genesis residual (a family-document ADocument
  encoder = our own donor), plus a counsel question if any donor is ever
  shipped. Until then family EMISSION is a research-environment step.
* **The SPECIMEN ANCESTOR** (`--specimens`, default `experiments/genesis/
  R5.rvt`). The family-free genesis base carries no wall / instance
  specimen to clone; the front door cuts scaffolding from the certified
  ancestor R5 (same lineage). R5 is a sample-lineage reduction (mostly
  Autodesk-authored content), so bundling it is a provenance / counsel
  decision, not a packaging one — NOT bundled; the build says `BaseError:
  specimen ancestor R5 not found … (pass --specimens <path>)`. The
  milestone that removes the need is a template-free wall / instance
  constructor.

  **Decision requested from the orchestrator:** (a) leave both unbundled
  (today's honest state, documented in `references/GENESIS-BASE.md` §3-4
  and the flagship SKILL §9), or (b) bless shipping R5.rvt (~6 MB) and/or a
  donor family as second assets — I did NOT, absent a ruling. The genesis
  base ITSELF is shipped and resolves certified.

### Also worth knowing

* **Genesis-base asset location vs the front door's default candidates.**
  `GenesisPin.candidate_paths()` looks for a plugin-bundled base at
  `<plugin_root>/lib/genesis/G_ABPD.rvt`; the packaging brief (and the
  plugin's assets convention) put it at `plugin/assets/genesis/G_ABPD.rvt`.
  Bridged today via `RVT_GENESIS_BASE` (hash-verified → certified, exported
  by `_bootstrap.py --env`). **One-line request (frontdoor stream):** add
  `os.path.join(pr, "assets", "genesis", basename)` to `candidate_paths()`
  so the pinned default resolves with only `RVT_PLUGIN_ROOT` (or nothing,
  once script-adjacent lookup lands).
* **Skill-name overlap needing a ruling.** The frontdoor stream authored
  `src/rvt/frontdoor/SKILL.frontdoor.md` (frontmatter `name: frontdoor`)
  "for the packager to promote into `plugin/skills/frontdoor/SKILL.md`".
  This charter names the flagship `tekton-author` — the skill that INVOKES
  `scripts/frontdoor.py`. Shipping BOTH would give the model two skills
  with near-identical triggers ("create a Revit file from a prompt / IFC /
  edit"). I therefore promoted the front door INTO `tekton-author` (the
  real `author --prompt|--ifc|--rvt` CLI, its status box, and their two
  additive items — the fallback prompt GRAMMAR and the note that our
  instances carry no instance parameter rows so rename/set-mark apply to
  NATIVE instances), and left their fragment mirrored inside the engine
  (`plugin/lib/src/rvt/frontdoor/SKILL.frontdoor.md`, referenced from the
  flagship §3) rather than promoted as a fourth skill. **Ruling requested:**
  one flagship (today) or an additional standalone `frontdoor` skill.
* **Parallel-landing race (expected).** The frontdoor stream was landing
  files under `src/rvt/frontdoor/**` throughout this session; each new file
  shows as `--check` drift under `lib/src/rvt/frontdoor/**` until the next
  `python tools/sync_plugin.py`. If the drift test goes red with only that
  path family listed, re-run the sync — it is not a defect.
* **`G_ABPD.compose.json`** = the composer's `G_ABPD.manifest.json` (no
  file literally named `.compose.json` exists in the repo; the brief's name
  is the shipped name, the mapping is documented in `plugin/assets/
  genesis/README.md`). Its own `verdict: NOT-CLEAN` field is rung-byte-
  fidelity bookkeeping at the 19 deleted-by-design slots — NOT a load
  verdict (the load verdict = viewer PASS, verdict #24, in the ledger). The
  README says so, so no reader mistakes it.
* **Pre-existing:** `plugin/scripts/validate_plugin.py` failed before my
  work on `plugin/marketplace.json convenience copy missing`; the sync now
  derives that file, so its validator is green again (22 assertions).
* **Tools scripts run byte-identical from the skill dirs** — no forking:
  their `sys.path.insert(HERE/../src)` lines are dead in the plugin layout
  and the installed / PYTHONPATH engine is what resolves. Kept it that way
  (a `_bootstrap.py` per skill + one `render_inspect.py` launcher are the
  only skill-native scripts).

## Files delivered

```
plugin/skills/tekton-author/SKILL.md                       (flagship; frontmatter triggers on any create/build/generate/author request)
plugin/skills/tekton-author/references/{TAGGING-CONTRACT,CATALOG-FACTS,PROMPT-TO-IFC,GENESIS-BASE,CRUD-COVERAGE}.md
plugin/skills/tekton-author/scripts/  frontdoor.py + rvt_job/ifc_intent/spec_to_rvt/ifc_to_spec/seed_audit/panel_schedule/genesis_compose/probe_batch/rvt_validate.py (synced) + _bootstrap.py
plugin/skills/tekton-author/examples/  electrical-room-2500a.ifc, chicago-plenum-downlight.ifc, room-spec.json, electrical-job.json
plugin/skills/tekton-edit/SKILL.md    + scripts/{rvt_edit,rvt_validate,rvt_job}.py (synced) + _bootstrap.py
plugin/skills/tekton-inspect/SKILL.md + scripts/{rvt_validate,seed_audit,spec_to_rvt,panel_schedule}.py (synced) + render_inspect.py + _bootstrap.py + examples/{room-spec,electrical-job}.json
plugin/assets/genesis/{G_ABPD.rvt, G_ABPD.compose.json, README.md}
plugin/lib/tools/*.py                                     (the front-door engine shim, see finding 2)
plugin/.claude-plugin/{plugin.json,marketplace.json}      (prose -> tekton; name stays rev-revit) + plugin/marketplace.json (derived)
tools/sync_plugin.py                                       (tekton maps, optional sources, assets + pin check, deny audit, shim, zip)
tests/test_plugin_sync.py                                  (7 tests: +tekton skill contents, +byte-identical scripts, +asset pinned, +deny, +manifest tekton)
rev-revit.zip                                              (rebuilt, 3.8 MB, one .rvt = the asset)
docs/inbox/plugin-packaging.md                             (this record)
```

## Requests for the orchestrator

1. **Merge the two-line `package-data` fix** into `plugin/lib/pyproject.toml`
   (finding 1) — until then the skills correctly steer users to the
   editable install, but a copy-install silently degrades the catalog.
2. **Ask the frontdoor stream for the script-adjacent module lookup**
   (finding 2) and the `assets/genesis/` candidate path (`Also worth
   knowing`); then delete `LIB_TOOLS_SHIM` and the `RVT_PLUGIN_ROOT` /
   `RVT_GENESIS_BASE` bridging from the skills.
3. **Rule on the two research inputs** (finding 3): keep the family donor
   and specimen ancestor out of the plugin (today's state) or bless
   assets for them; both flagship-SKILL sections are written to today's
   state and cheap to flip.
4. **KNOWLEDGE.md lines to merge:** (i) *the plugin's engine must be
   installed EDITABLE (or via PYTHONPATH) — a copy install drops
   `rvt/famgen/facts/**` and the frontdoor pin/docs (no package-data);*
   (ii) *rvt.frontdoor resolves its reused build code at
   `<repo_root>/tools/` where `repo_root()` = `plugin/lib` in the bundled
   layout — the packager mirrors those scripts to `plugin/lib/tools/`
   until the loader looks beside the running script;* (iii) *the
   plugin's certified genesis base ships at `plugin/assets/genesis/
   G_ABPD.rvt`, sha256-pinned to `rvt.frontdoor`'s pin by the sync — the
   ONLY `.rvt` in the plugin; the front door asserts it certified via
   `RVT_GENESIS_BASE`.*

## BRANCH STATE

* **DONE**: three tekton skills (author / edit / inspect) with bundled
  scripts, references, examples and honest status boxes; `tools/
  sync_plugin.py` extended (tekton maps, OPTIONAL sources, ASSET copy +
  frontdoor-pin cross-check, whole-tree DENY audit, `lib/tools` shim,
  marketplace convenience copy, zip re-includes `assets/`); the certified
  genesis base + composer manifest shipped as `plugin/assets/genesis/`
  (sha256 84173b89… == the frontdoor pin, DENY-clean); plugin manifests'
  prose say tekton (name still `rev-revit`); `tests/test_plugin_sync.py`
  extended to 7; both plugin validators PASS; zip rebuilt; all three
  front-door routes exercised FROM the plugin with measured outcomes
  (prompt-handoff WORKS, `--rvt --edit` WORKS end to end, IFC/prompt build
  named-blocked on the two research inputs) and the IFC route proven
  complete in the research environment.
* **BLOCKED, NAMED (not packaging-fixable):** the families→placement build
  standalone in the plugin — the family FORMAT DONOR (G4b / family ADocument
  encoder) and the SPECIMEN ANCESTOR (template-free constructors), both
  requiring an orchestrator/counsel ruling to bundle instead. Recorded in
  the flagship SKILL §9 and `references/GENESIS-BASE.md` §3-4 so users are
  told, not surprised.
* **REQUESTED UPSTREAM (owned by other streams):** `plugin/lib/pyproject.toml`
  package-data (packager); script-adjacent module lookup + `assets/genesis/`
  candidate path in `rvt.frontdoor` (frontdoor stream); then the shim and
  the env bridging can be removed.
* **Full suite** (`.venv/bin/python -m pytest tests/ -q`): launched in the
  background and STILL RUNNING when this stream was told to report (the
  suite is large — genesis / render / famgen). No source module or existing
  test was edited by this stream (only `tools/sync_plugin.py` +
  `tests/test_plugin_sync.py`), so a regression here would have to come
  from the sync itself; the plugin-scoped gates are green:
  `tests/test_plugin_sync.py` **7 passed**, `claude plugin validate` ✔,
  `plugin/scripts/validate_plugin.py` **PASS (22 assertions)**, plus the
  regression run of the untouched rvt-native scripts (inspect/selfcheck
  PASS). Orchestrator: read the finished pytest run's tail for the count.

# perf-surfaces / #113 -- the tekton-ifc skill flow has a measured baseline (`ifc-harden`)

Stream: PERF-SURFACES (index: `docs/inbox/perf-surfaces.md`). Issue #113 (Refs #110, steer #108).
Branch `cam/113-ifc-skill-bench` from `main@00b2105`.

## Why

`tools/surface_bench.py` benched every Python-engine skill flow (preflight, `go author`,
`go edit`, validate) and nothing for `tekton-ifc` -- the Claude Design / Cowork sandbox
skill whose engine is four plain CLIs (`validate_ifc.py`, `harden_ifc.py`, `report.py`,
`generate_ifc.py`) run as `python scripts/<tool>.py` in a code-execution sandbox: no `rvt`,
no `_bootstrap.py`, no `go`. Steer #108 makes plugin latency a product requirement; without a
number this flow was an adjective.

## What was built

* **`ifc-harden`**, a tenth canonical job (last in `JOB_ORDER`, its own session): the skill's
  documented flow on a foreign IFC (`SKILL.md` 5.2-5.4) on the plugin's own sample
  `skills/tekton-author/examples/electrical-room-2500a.ifc` (a `three-d-stage` IFC4 export,
  687 KB, already in the zip -- no new fixture): `validate_ifc.py` (score/tier before) ->
  `harden_ifc.py -o --report` -> `validate_ifc.py` on the hardened file (must reopen clean) ->
  `report.py validate.json --compare harden.json` -- FOUR shell calls, wall time + call count
  like every other row. On `codeexec` the hardened file / both JSON reports are re-staged per
  call (the "re-upload").
* **Verdicts.** The tools import `ifcopenshell` + `numpy` (`scripts/requirements.txt`); the
  session's readiness step is `pip install -r scripts/requirements.txt` -- a network call
  this harness never makes -- so an interpreter without the wheels fails the FIRST call at
  import and the row is **BLOCKED** carrying `{route: ifc-skill, needs: [<the modules the
  ModuleNotFoundError named, in requirements order>], fix}`, no further call made (the
  `go author --ifc` pattern, #553). `harden_ifc.py` exit 1 (the rewritten file has schema
  errors), a missing output, or a validate report without a score -> **FAIL** with the call's
  own words. `report.py` is stdlib-only and runs anywhere, but needs the JSON the blocked call
  never wrote, so a blocked row is one call.
* **The row's breakdown** has the same shape the author jobs use -- `stages` rows (one per call:
  validate / harden / re-validate / report) -- plus what hardening did (`score_before/after`,
  the tier names, `schema_errors_after`, `boxes_converted`, `products_before/after`,
  `globalids_preserved`) and a composed `summary` line (the `gates.line` precedent), so the
  existing `_fmt_breakdown` / notes branch renders it: no job-specific formatter, no new
  shape-sniff in `markdown_table`.
* **Gate:** `tests/test_surface_perf.py` -- `IFC_SKILL_CEILING = 20.0`, its own module fixture
  (`ifc_skill_report`, cowork surface, plugin tree, the bare interpreter) and
  `test_ifc_skill_flow_hardens_or_states_its_prerequisite`: PASS (wheels present: 4 calls, the
  hardened file reopens with 0 schema errors, the sample's score rises, under the ceiling) or
  BLOCKED (wheels absent: 1 call, the missing prerequisite named, under `PREFLIGHT_CEILING`),
  never FAIL, never SKIPPED; which branch is required is asked of the bare interpreter under
  the bench env (`_bare_has`, `find_spec` in a subprocess -- nothing heavy imported into pytest).
  The flow is a different session, so it is NOT added to `SESSION_CALL_BUDGET` (5 stays 5).
* **Unit module** `tests/test_ifc_skill_bench_113.py` (11 tests, shard drop-in
  `tests/ci_shard.d/113-ifc-skill-bench.txt`): a fake surface plants the files each call would
  write; pins the BLOCKED/FAIL/PASS classification, the four argv shapes and their chaining,
  the breakdown + notes line, `_missing_prerequisite` (dotted module names, declared order,
  foreign modules ignored), and that `IFC_SKILL_NEEDS` equals the package names in
  `skills/tekton-ifc/scripts/requirements.txt` (the one source of truth; a wheel added there
  cannot silently turn BLOCKED into FAIL).

## Evidence (this cloud VM, 2026-08-27; plugin tree; `IFC_EXAMPLE_REL` sample)

| surface | bare interpreter | verdict | calls | wall | per call |
|---|---|---|---|---|---|
| cowork | `/usr/bin/python3` 3.11 (no numpy) | BLOCKED (needs numpy) | 1 | 0.05 s | -- |
| codeexec | same | BLOCKED (needs numpy) | 1 | 0.05 s (+0.1 s extract) | -- |
| local | repo venv 3.11 + ifcopenshell 0.8.5 + numpy 2.4.6 | PASS | 4 | 5.7 s | validate 1.6 · harden 2.5 · re-validate 1.6 · report 0.0 |
| cowork | venv python as the bare interpreter (x3) | PASS | 4 | **5.4 / 5.6 / 5.7 s** | validate 1.4-1.5 · harden 2.6-2.7 · re-validate 1.3-1.6 · report 0.04 |
| codeexec | venv python as the bare interpreter | PASS | 4 | 5.9 s + 0.5 s extract | validate 1.7 · harden 2.8 · re-validate 1.3 · report 0.04 |

Every PASS row: score **35.7 -> 77.0** (Tier 0 (v1-like) -> Tier 1 (partial)), 124 boxes ->
extrusions, products 14 -> 13 (one phantom removed), GlobalIds 13/13 kept, schema errors after 0.

* **No engine dependency, stated as the issue asked:** none of the four tools imports `rvt`
  (`grep -n "^import \|^from " skills/tekton-ifc/scripts/*.py`); `bridge_lib` imports
  `numpy`, `ifcopenshell`, `ifcopenshell.util.element/placement`, `ifcopenshell.validate`;
  `report.py` imports only `argparse/json/os/sys`. The bare surfaces need no lighter env variant:
  the existing `bare_env` (cleared PATH/HOME/proxies) is exactly the sandbox model, and the
  scripts run from the staged plugin dir directly.
* **Where the time goes:** `import bridge_lib` alone is 0.47-0.73 s on the venv python
  (`-X importtime` cumulative 646 ms: `ifcopenshell` 376 ms, its SWIG wrapper 118 ms,
  `ifcopenshell.validate`/`util`, numpy 58 ms); the flow pays it three times (validate, harden,
  re-validate). So ~1.5-2 s of the ~5.6 s is import; the rest is parse + analysis of a 687 KB
  IFC (validate ~0.9 s net, harden ~2 s net). The scripts README's "all four tools run in well
  under a second" does not hold on this VM for this sample (it was measured on the 11-element
  design sample); the number now lives in the gate comment instead.
* `python3 tools/dev/shard_list.py --print` resolves the drop-in; `tools/sync_plugin.py --check`
  in sync (`surface_bench.py` is not mirrored into the plugin); `plugin/scripts/validate_plugin.py`
  PASS; `tools/dev/check_portable_paths.py` ok (3152).
* Tests: `tests/test_surface_perf.py tests/test_surface_bench_reason.py
  tests/test_ifc_skill_bench_113.py tests/test_records_layout.py` -> **53 passed** (the perf test
  took its BLOCKED branch on this host's numpy-less system python); the PASS branch's assertions
  were run by hand against a venv-python cowork report (PASS, 4 calls, 5.7 s, 35.7 -> 77.0,
  0 errors after) and hold. Final three-surface run with the venv python as the bare interpreter:
  cowork 5.9 s, codeexec 5.8 s + 0.3 s extract, local 5.4 s.
* `/simplify` (four reviewers -- reuse, simplification, efficiency, altitude) before the commit:
  the reporting layer moved to the harness's existing `stages` + `summary` shape (a job-specific
  formatter, a positional step-name zip and a third notes-branch shape-sniff removed); one
  `_read_json` helper now serves `stage_breakdown`, `_ifc_score` and the actions read; each
  output path bound once; `_missing_prerequisite` takes the job's declared `needs`; the tier
  gloss is stripped at read time; the unit module uses `conftest.load_tool` and the sibling
  module's `_inv`; the perf module shares one `_cowork_report` and caches `_bare_python()`.
  Declined: folding `ifc-harden` into `bench_report` (a different session -- the budget test
  would need an exclusion) and reading `needs` from `requirements.txt` at job time (the
  cross-check test catches the drift without a dist->module alias map).

## Findings / follow-ups (not done here)

* **A one-call dispatch for the ifc skill would save ~2 of its ~5.6 s** (three imports of
  ifcopenshell + numpy, plus three model round-trips): a `scripts/go_ifc.py` running validate ->
  harden -> re-validate -> report in one process with one JSON out, the #111 move for this skill.
  Filed as #754.
* **`SKILL.md` 5.4 documents `report.py out/hardened.ifc --before in.ifc`; the CLI is
  `report.py validation.json [--compare harden.json] -o report.md`** (the file's own line 280
  says to trust `--help`). Noted on #112, which restructures that hot file.
* The bench table's "shell calls" column shows the last non-skipped surface's count (4) even
  when the other surfaces were BLOCKED after 1 call -- pre-existing for every BLOCKED row
  (`author-ifc`, `go-author-ifc`), left as is.

### BRANCH STATE (#113)

* Files: `tools/surface_bench.py` (constants `IFC_SKILL_SCRIPTS_REL/NEEDS/FIX`, `JOB_ORDER`
  + `JOBS` entry, `_read_json` (also used by `stage_breakdown`), `_missing_prerequisite`,
  `_ifc_score`, `_ifc_summary`, `job_ifc_harden`, the `summary` tail in `_fmt_breakdown`,
  `import re`, docstring row); `tests/test_surface_perf.py` (`IFC_SKILL_CEILING`, `_cowork_report`,
  `ifc_skill_report`, `_bare_has`, cached `_bare_python`, the new test, docstring); new
  `tests/test_ifc_skill_bench_113.py`;
  new `tests/ci_shard.d/113-ifc-skill-bench.txt`; this fragment + one index line in
  `docs/inbox/perf-surfaces.md`. No hot file, no `src/`, no `plugin/**`, no skill wording.
* Shipped: nothing beyond the PR. Bench artifacts under `out/verify/v113/` are session-local
  (git-ignored); their numbers are transcribed above.
* Open: the one-call ifc dispatch (#754); the `SKILL.md` 5.4 wording (noted on #112).

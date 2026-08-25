# 751 — a skipped validator is SAID: `self-checks SKIPPED`, one word on every route

Fragment of `docs/inbox/perf-go-report.md` (issue #751, follow-up of #185 / PR #748). One PR.

## Why

Surfaced by #748's independent review: `tools/frontdoor.py author --prompt … --no-validate --json`
printed `status: "PROOF-ONLY (self-checks PASS; …)"` next to `report.validation = {verdict: NOT-RUN,
self_checks_ok: false}` — `_rollup_status` only tested its self-check clause when `build.validation`
was non-empty, and a `--no-validate` (or `--stages` without V) run emits files and gates nothing. The
status line is what a skill relays verbatim (hard rule 1); "PASS" for a check that never ran is the
one thing it must not say. Second, the same situation read `NOT-RUN` on the create routes and `SKIPPED`
on the edit route (the job runner's gate word).

## What was built

* `rvt.frontdoor.build.BuildResult.validation_skipped` — the *reason* the V stage gated nothing
  (`"--no-validate"` or `"stage V not in --stages <S>"`), set by the V-stage `elif res.deepest:` branch
  when files were emitted; the same branch now appends the `validation SKIPPED (<reason>): this is NOT
  a shippable run` degradation for both reasons (before: only `--no-validate` degraded, a `--stages`
  subset without V was silent). `GATED_ROLES = ("combined", "equipment", "shell")` is the one tuple
  `BuildResult.deepest` and the V loop iterate. Set after every file write; read only by the manifest.
* `manifest.build_manifest` copies the reason to `manifest["build"]["validation_skipped"]` (null on a
  gated run). `_rollup_status` says `self-checks SKIPPED: <reason>` whenever no gate judged the files
  (after the DELIVERABLE branch, which needs the status gate the V stage produces), default reason
  `validator did not run`; a gated run keeps today's exact strings.
* `report.validation.verdict` — ONE word on every route through `_unrun_summary(n_files)`: `SKIPPED`
  over the emitted files the validator would have judged (`build.files`, exactly the gated roles), `NOT-RUN`
  when nothing was emitted; counts zero either way. `_build_validation_summary(validation, *, emitted)`
  and `_edit_validation_summary` both funnel into it.
* `tools/rvt_job.py` says it at the source: a job whose validation gate is `SKIPPED` gets the status
  `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED; validation SKIPPED: --no-validate)` (the gate still
  counts toward `hard_gates_passed` — skipped is not failed), so `rvt_edit.py` users, the job's own
  `.manifest.json`, `_print_summary` and the front door's edit route all carry one string; a validated job
  keeps `tests/test_edit_status.py`'s pinned string byte for byte.
* `target_status._this_file` — the honesty tier `release.this_file` that `tekton-author` relays in
  step 2 reads `self-checks-skipped (no validator verdict for this file -- NOT a shippable run; …)`
  instead of `validated-not-certified` when `report.validation.verdict` is SKIPPED.
* `MANIFEST.md`: `- **self-checks SKIPPED** (<reason>): no validator / registry / identity verdict for
  <roles> -- NOT a shippable run` where the per-file self-check lines would have been.
* Tests: `tests/test_skipped_selfchecks_751.py` (+ `tests/ci_shard.d/751-skipped-selfchecks.txt`), 9 cases:
  status wording (skipped with either reason, the reason-less default, the gated / failed / no-output strings
  unchanged), both summaries' vocabulary, and end to end on the bundled base with the one-panel prompt:
  the `--no-validate` build beside its validated twin (status, marker, `report`, degradation, MANIFEST.md,
  `this_file`), a `--stages FLWEC` build, and a `--no-validate` edit (rvt_job's wording, `this_file`).
  `tests/test_go_report_185.py`'s edit-vocabulary case tightened: a SKIPPED gate's synthetic counts are no
  longer echoed (zeros). A FAILED intake → `NOT-RUN` stays pinned by the #185 module.
* `/simplify` (4 reviewers) applied: reason-only marker (files counted from `build.files`, no second
  source), one `_unrun_summary`, `checks` computed after the DELIVERABLE return, one degradation template
  for both skip reasons, `GATED_ROLES` shared with `deepest`, the edit-route status fixed in the job
  runner instead of a suffix in `edit_manifest`, the `this_file` tier, and the test trims (one-panel
  prompt, no cases duplicating the #185 module).

## Evidence (2026-08-25, Python 3.11.15, fresh cloud clone)

`tools/frontdoor.py author … --json` (status / `report.validation` as printed; validator re-run on each
emitted `.rvt` with `tools/rvt_validate.py`: `ok: true`, 0 errors, 1 known ES DataStorage warning):

| job | status | `report.validation` |
|---|---|---|
| `--prompt "an electrical room with 6 panels" --no-validate` | `PROOF-ONLY (self-checks SKIPPED: --no-validate; see honesty.proof_only_stamps + status_gate)` | `{SKIPPED, 0, 0, self_checks_ok false, files 1}` |
| same prompt, validated | `PROOF-ONLY (self-checks PASS; see …)` (unchanged) | `{VALID, 0, 1, true, 1}` |
| `--prompt "create an eaton panel for me with 6 switches" --stages FLWEC` | `PROOF-ONLY (self-checks SKIPPED: stage V not in --stages FLWEC; see …)` | `{SKIPPED, 0, 0, false, 1}` |
| `--rvt <6-panel> --edit "move PP-1 to 3,1,0" --no-validate` | `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED; validation SKIPPED: --no-validate)` (rvt_job's own `.manifest.json` says the same) | `{SKIPPED, 0, 0, false, 1}` |
| same edit, validated | `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)` (unchanged) | `{VALID, 0, 1, true, 1}` |
| `--rvt … --edit "teleport the moon"` (FAILED, rc 3) | `FAILED (edit not understood: …)` | `{NOT-RUN, 0, 0, false, 0}` |
| `--ifc tests/conftest.py` (FAILED, rc 3) | `FAILED (IFC intent failed: …)` | `{NOT-RUN, 0, 0, false, 0}` |

`manifest.json["build"]["validation_skipped"]`: `"--no-validate"` / `"stage V not in --stages FLWEC"` /
`null` on the validated run. `release.this_file`: `self-checks-skipped (…)` on the three skipped runs,
`validated-not-certified (…)` on the two validated ones, `not-built` on the FAILED intake. Result sizes
2,104–2,226 B (prompt), 1,320–1,322 B (edit): the #185 4 KB budget is untouched.

Bare surface — fresh unzip of `tekton-plugin.zip`, `/usr/bin/python3`, `env -i`, proxies at a dead port,
`go author --prompt "create an eaton panel for me with 6 switches" [--no-validate] --json`: rc 0,
`go.ready` true both ways; `--no-validate` → status `…(self-checks SKIPPED: --no-validate; …)`,
`report.validation` `{SKIPPED, files 1}`, result 2,894 B, wall 1.67 s; validated → `…(self-checks
PASS; …)`, `{VALID, 0, 1, true, 1}`, 2,833 B, 1.60 s; `go author --rvt … --edit … --no-validate` →
rc 0, status `…(hard gates PASSED; validation SKIPPED: --no-validate)`, `{SKIPPED, files 1}`.

Delivered bytes: the marker is written after every file write and read only by the manifest, so no
`.rvt`/`.rfa` byte depends on it. (Run-to-run sha256 of the same prompt already differs on an unchanged
tree — #168's non-determinism — so sha equality is not a usable instrument here; the argument is structural.)

Gates (after `/simplify`): `tests/test_skipped_selfchecks_751.py` 9 passed in 4.2 s (the first draft's
negative control against `origin/main`'s sources failed at the first status test); `test_go_report_185.py
test_skipped_selfchecks_751.py test_edit_status.py test_status_gate.py test_frontdoor_209.py test_go_edit.py
test_frontdoor_json_strict.py test_frontdoor_manifest_pin.py test_records_layout.py
test_target_version_first.py test_input_release.py` → 197 passed / 1 skipped; `test_frontdoor.py
test_router.py test_surface_bench_reason.py test_plugin_sync.py test_bootstrap.py test_coldstart.py
test_go_target_version.py` → 290 passed / 17 skipped (`RVT_SKIP_LARGE=1`); the rvt_job-driving
`test_job.py test_edit_own_release.py test_manipulate.py test_history_head_guid.py` → 35 passed / 9 skipped;
`tools/sync_plugin.py` rebuilt + `--check` in sync; `validate_plugin.py` PASS; portable paths ok;
`route.py matrix` evidence self-audit clean; every emitted `.rvt` above re-validated `ok: true`.

## Findings

1. The job runner's definition stands: a SKIPPED validation still counts toward `hard_gates_passed`
   (skipped ≠ failed, `tools/rvt_job.py` ~730), so `ok` stays true and the exit code 0 for a
   `--no-validate` job; only the *words* changed — the status now names the skip wherever it is printed.
2. `--stages` without V now degrades like `--no-validate` does (one template); a stages-subset run
   therefore reaches the router's caveats (`_absorb_build_degradations`) too, which it silently did not before.
3. #749 (SKILL.md wording) can now tell skills to key on `report.validation.verdict` ∈ {VALID, INVALID,
   SKIPPED, NOT-RUN} + `self_checks_ok`, and on `release.this_file` starting with `self-checks-skipped`.

## BRANCH STATE

* branch `cam/751-skipped-selfchecks` from `main` @ `d5b2ede`; files: `src/rvt/frontdoor/build.py`
  (`GATED_ROLES`, `validation_skipped`, V-stage `elif`), `src/rvt/frontdoor/manifest.py` (`_rollup_status`,
  `_skipped_reason`, `_unrun_summary`, both summaries, MANIFEST.md line, the `build.validation_skipped`
  key), `src/rvt/frontdoor/target_status.py` (`_this_file` skipped tier), `tools/rvt_job.py` (status
  wording), their `plugin/lib/` mirrors (sync), `tests/test_skipped_selfchecks_751.py`,
  `tests/ci_shard.d/751-skipped-selfchecks.txt`, one tightened case in `tests/test_go_report_185.py`,
  this fragment + one index line in `docs/inbox/perf-go-report.md`.
* shipped in the PR: all of the above. Staged for a human: nothing (no viewer claim; no delivered bytes change).
* not touched: `tools/frontdoor.py`, `plugin/skills/*/SKILL.md`, `src/rvt/frontdoor/base.py`, `src/rvt/versions/`.

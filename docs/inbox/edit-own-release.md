# EDIT-OWN-RELEASE — the edit entry points open, edit and re-emit a Revit 2025/2024 project under its own release (issue #70)

Stream: `edit-own-release` (engineer session on #70, started by the tech-lead
session; the issue calls the record `edit-route-release-aware.md` — named per
the lead's brief, same content). Territory: `tools/rvt_edit.py`,
`tools/rvt_job.py` (edit mode only), `src/rvt/frontdoor/matrix.py` (the
`prompt+rvt → rvt` cell's caveats/evidence), `docs/product/PERMUTATION-MATRIX.md`
(that row), `tests/test_edit_own_release.py` + `tests/ci_shard.txt`, this
record. Builds on PR #91 (issue #14: `release_ctx.host_release_context` /
`enter_host_release`, and `_route_rvt` entering it) — nothing reinvented, no
hot file touched (`tools/frontdoor.py`, `src/rvt/versions/`, `base.py`,
`SKILL.md` all unchanged).

## 0. The defect, reproduced (fresh cloud clone, tracked bases, before any change)

On `origin/main` @ 33622e3 (before #91), all three user-facing edit surfaces
were release-blind on the bundled certified 2025 / 2024 bases:

| surface | `G_ABPD.rvt` (2026) | `G_ABPD_2025.rvt` | `G_ABPD_2024.rvt` |
|---|---|---|---|
| `tools/frontdoor.py author --rvt <base> --edit "…" --json` | ok (0.5 s to a clean "no element named" on the empty base; edit runs) | exit 3, `cannot open/plan …: ValueError: unexpected Partitions header: v=9 cls=0x391` | exit 3, same with `cls=0x37b` |
| `tools/rvt_edit.py <base> info` / `set-level --id 1351691 --elevation-ft 5 -o …` | ok | `ValueError: unexpected Partitions header: v=9 cls=0x391` | same, `0x37b` |
| `tools/rvt_job.py edit <base> --ops ops.json -o …` | ok | traceback, same `ValueError` | same, `0x37b` |

With #91 merged in locally the **front-door route** already passes on all
three (it enters `enter_host_release(stack, rvt_path)`; the job runner it
delegates to then runs inside that context): exit 0, `structural` PASS with
`1351691/102: {Level, clean: True}`, `validation` PASS, output release ==
input release, ~3.5 s each. The two **direct CLIs** — which is what the
`tekton-edit` / `tekton-native` skills document and ship
(`skills/tekton-edit/scripts/rvt_edit.py`, `…/rvt_job.py`) — still died
exactly as above, because nothing on their path enters the input's release.

## 1. What was built

* `tools/rvt_edit.py`: `main()` enters `enter_host_release(stack, FILE)` once,
  around every verb (`info`, `deps`, `delete`, `rename-panel`, `set-mark`,
  `set-level`, `move`, `retype`), then runs the unchanged body (`_run`). A
  native (2026) file enters no context (byte-identical output, §2); a 2025 /
  2024 file is opened, planned, re-emitted (`commit_plans` with the release's
  `BLOCK_TAG`/`TRAILER_TAG`) and structurally verified under its own release;
  a release we cannot author into returns the refusal sentence, printed as a
  `[rvt_edit] warning:` line, and the verb then fails honestly downstream
  (nothing is guessed).
* `tools/rvt_job.py`: `cmd_edit()` enters the same context keyed on the input
  file before planning and keeps it through commit → identity scrub →
  `verify_manipulated` → `run_gates` (validation, provenance); the body moved
  verbatim to `_cmd_edit()`. Re-entrant by construction: called from the front
  door's `--rvt --edit` route it *joins* the route's context (same release)
  instead of stacking. The job manifest's `base` block now records
  `release` (the input's detected year) and, only when the context could not
  be entered, `release_note` (the refusal sentence).
* `src/rvt/frontdoor/matrix.py` / `docs/product/PERMUTATION-MATRIX.md`: the
  `prompt+rvt → rvt` cell states the per-release truth — the edit runs under
  the input's own release and the output keeps it; 2026 / 2025 / 2024 open,
  edit, re-emit and validate 0 errors through all three surfaces; the viewer
  certifications cited on that row are 2026-era files, so 2025/2024 edit
  outputs are **validated, not viewer-certified**; 2023 and older are named
  and refused. New evidence citation `test:tests/test_edit_own_release.py`
  (self-audit passes; the 30 pre-existing "certified file missing on disk"
  audit lines in a fresh clone are the git-ignored `experiments/` files,
  unchanged by this stream).
* `tests/test_edit_own_release.py` (11 tests, ~28 s, in `tests/ci_shard.txt`),
  all on the three tracked bases, all sample-free:
  1. front door `author(rvt=<base>, edit="set level 1351691 elevation to 5 ft")`
     × {2026, 2025, 2024}: `ok`, job `structural` PASS with the Level's 102
     record clean, `validation` PASS, `base.release == year`;
  2. `rvt_edit.py set-level` × {2026, 2025, 2024} as its CLI `main()`:
     rc 0, `walker_errors 0 / crc_failures 0`;
  3. `rvt_edit.py info` + `deps` × {2025, 2024}: the file's own inventory
     (the basement level present), `deps` names the Level;
  4. `rvt_job.py edit` called directly × {2025, 2024}: rc 0, structural +
     validation PASS, `base.release == year`, no `release_note`;
  5. one process, 2025 → 2024 → 2026 edits back to back.
  Every output is then judged **bare** (no context around the judge):
  `detect_release(out) == year`, `active_release() is None`,
  `validate_file(out)` 0 errors; and an autouse fixture asserts the native
  framing table, `manipulate.BLOCK_TAG/TRAILER_TAG` and `active_release()`
  are back after every test (the DONE's "no leak into a following 2026 job").
  Sanity: with the two tool changes stashed, the CLI tests fail (3/3 of the
  2025 CLI cases) with the original `ValueError`; with them, 11/11 pass.

## 2. Evidence (numbers; this cloud VM, Python 3.11, main+#91+this branch)

* **Real CLIs, repo checkout** (`set level 1351691 elevation to 5 ft`):

  | surface | 2026 | 2025 | 2024 |
  |---|---|---|---|
  | `frontdoor.py author --rvt … --edit … --json` | rc 0, 3.1 s, gates structural/validation/identity PASS, out release 2026 | rc 0, 3.7 s, PASS, **2025** | rc 0, 3.6 s, PASS, **2024** |
  | `rvt_edit.py … set-level … -o` | rc 0, 1.5 s, walker/crc/ecc 0, `rvt_validate` 0 errors (1 known DataStorage warning) | rc 0, 1.8 s, 0 errors / 0 warnings, **2025** | rc 0, 1.7 s, 0/0, **2024** |
  | `rvt_job.py edit … --ops … -o` | rc 0, 2.4 s, hard gates PASSED, `base.release 2026` | rc 0, 2.8 s, PASSED, **2025** | rc 0, 2.6 s, PASSED, **2024** |
  | `rvt_edit.py … info` / `deps --id 1351691` | ok | ok (six levels; Level deps) | ok |

* **2026 byte-unchanged:** `rvt_edit.py set-level` on `G_ABPD.rvt` before vs
  after this change: md5 `7ba3ff19…` == `7ba3ff19…`; `rvt_job.py edit`:
  `9439f932…` == `9439f932…` (a native file enters no context).
* **Bare unzip, system `python3` 3.11, `TEKTON_ROOT` unset, a copy of the
  2025 base as "the user's file"** (steer #108 wall times):
  `skills/tekton-author/scripts/_bootstrap.py go author --rvt user2025.rvt
  --edit "set level 1351691 elevation to 5 ft" --json` → `READY`, `ok true`,
  route `rvt`, hard gates PASSED, **2.9 s** (preflight 0.06 s + job 2.75 s);
  `skills/tekton-edit/scripts/_bootstrap.py run rvt_edit.py user2025.rvt info`
  → rc 0, 0.3 s; `… run rvt_edit.py … set-level … -o` → rc 0, 1.3 s,
  walker/crc/ecc 0; `… run rvt_job.py edit … --ops …` → rc 0, 2.3 s, hard
  gates PASSED; `… run rvt_validate.py` on all three outputs → `VALID (no
  errors)` (the 1 warning is the pre-existing "ECC page verification SKIPPED:
  numpy not installed" note of a bare system Python — identical on the
  untouched base); `detect_release` = 2025 on all three.
* **Honesty probes:** `--rvt G_ABPD_2025.rvt --edit … --target-version 2026`
  → delivered, manifest `target_version.status = match-older` (input 2025,
  output 2025, "Revit 2026 opens older files"); `rvt_edit.py /nonexistent.rvt
  info` → one argparse line, rc 2. `tools/provenance.py <2025 edit output>
  --baseline all --streams` completes; in this fresh clone `samples/` is absent
  so it reads "no baseline supplied (provenance unattributable)" exactly as for
  the certified base itself (#91 §2), identity ours = True (`rvt-writer`);
  `tools/rvt_analyze.py` → release 2025, schema sha `c964f9aa…` (the 2025 pin).
* **Tests:** `tests/test_edit_own_release.py` 11 passed (28 s). Adjacent:
  `test_plugin_sync test_bootstrap test_coldstart test_surface_perf
  test_frontdoor test_verify_manipulated_release test_job test_manipulate
  test_router` → 107 passed / 23 skipped / 0 failed (35 s). **CI shard exactly
  as CI runs it** (`RVT_SKIP_LARGE=1 … $(grep -vE '^\s*(#|$)' tests/ci_shard.txt)`):
  **197 passed / 31 skipped in 110 s** (was 186 / 30 in 90 s at #91's head).
* **Plugin:** `tools/sync_plugin.py` → 8 files synced (the two tools into
  `plugin/lib/tools/` + the `tekton-edit` / `tekton-native` / `tekton-author`
  script copies, `matrix.py` mirror), deny-audit clean, zip rebuilt;
  `--check` clean; `plugin/scripts/validate_plugin.py` PASS (23 assertions);
  `tools/dev/check_portable_paths.py` ok (2677 paths).

## 3. Findings / follow-ups (filed as issues, not done here)

* `plugin/skills/tekton-native/scripts/rvt_edit_text.py` (hand-authored in the
  plugin tree, not a `tools/` mirror) frames blocks with the module-level
  `writer.BLOCK_TRL_TAG` and walks partitions bare — the same release-blind
  shape this issue fixed for `rvt_edit.py`; it is outside this territory
  (plugin skill script with no `tools/` source). Filed as #116
  (`Refs #70`).
* Viewer certification of a 2025 / 2024 *edit* output is not claimed here (the
  issue says so); the matrix row now states "validated, not viewer-certified"
  for those releases. A `needs-viewer` batch (certified `G_ABPD_2025` control +
  one `set-level` probe) is the natural follow-up once #14's batch 56 has a
  verdict — filed as #117 (`needs-viewer`, `Refs #70`).

## SUITE RESULT

Per `docs/inbox/SUITE-COORDINATION.md`: no full-suite run. Stream-local +
adjacent + the CI shard only (§2). Expected full-suite delta: +11 tests; no
native-release behaviour change (2026 outputs byte-identical before/after).

## BRANCH STATE

* Branch `cam/70-edit-own-release` from `origin/main`; developed and gated
  locally on top of PR #91's branch merged with `main` (dependency declared on
  #70 before starting; never pushed stacked). Pushed and PR opened with
  `Closes #70` only after #91 landed on `main` and this branch was rebased.
* Files: `tools/rvt_edit.py`, `tools/rvt_job.py`, `src/rvt/frontdoor/matrix.py`,
  `docs/product/PERMUTATION-MATRIX.md`, `tests/test_edit_own_release.py`,
  `tests/ci_shard.txt`, `docs/inbox/edit-own-release.md`, plus the
  `tools/sync_plugin.py` mirrors (`plugin/lib/tools/rvt_{edit,job}.py`,
  `plugin/skills/tekton-{edit,native}/scripts/rvt_edit.py`,
  `plugin/skills/tekton-{author,edit,native}/scripts/rvt_job.py`,
  `plugin/lib/src/rvt/frontdoor/matrix.py`).
* DONE check against #70: front door `--rvt <2025|2024 base> --edit "set level
  1351691 elevation to 5 ft"` exits 0, `structural` PASS (`102: Level clean`),
  `validation` PASS, output declares the input's release, 2026 unchanged ✓;
  `rvt_edit.py <2025 base> set-level … -o` writes a file `rvt_validate.py`
  reports 0 errors on ✓ (2024 too); fresh-clone tests for both in
  `tests/ci_shard.txt` ✓; `route matrix` / `PERMUTATION-MATRIX.md` state the
  per-release truth ✓; module constants restored after each run (autouse
  fixture + mixed-release test) ✓. Beyond the letter: `rvt_job.py edit`
  direct and the read verbs, and the bare-unzip skill launchers, on 2025.
* Nothing staged for the viewer; no certification claim; every output ships
  PROOF-ONLY-stamped as before.

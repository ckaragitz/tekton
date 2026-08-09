# edit-one-call — the tekton-edit skill flow is ONE `go edit` call (issue #111)

Stream: `eng111` (engineer session under the tech-lead session; branch
`cam/111-edit-one-call`). Refs #111, #110 (latency epic), #108 /
S-2026-08-09-g (skill-path latency is first-class; a latency item is only
done with a measured before/after from a bare surface). Follows PR #173
(`go author …` = one call whose JSON carries the release/status block).

## 1. What was built

1. **`_bootstrap.py go edit IN.rvt VERB [ARGS] [-o OUT.rvt]`** — a new,
   additive verb branch in the shared dispatcher
   (`plugin/skills/_shared/tekton_env.py`, `_GO_VERBS` +
   `_resolve_go_target`): inline readiness, then `rvt_edit.py … --json`,
   then ONE combined JSON on stdout. The `author` path is untouched
   (same script, same `--json` append, same fallback to the home skill's
   canonical copy — `go edit` from tekton-author resolves
   `skills/tekton-edit/scripts/rvt_edit.py` from the plugin root, never by
   searching).
2. **`tools/rvt_edit.py --json`** (position-free flag; text mode is
   byte-for-byte the old behaviour): one JSON object carrying everything the
   skill reports — `ok`, `command`, `id`, `input.path`, `output.path/bytes/
   validation_json`, `report` (the `ManipCommitReport`: `replaced`,
   `removed_ids`, ElemTable counts …), `release` (`input`, `output`,
   `opens_in`, `line` = "Revit N in, Revit N out; opens in Revit N and newer,
   never older" — both detected from each file's own `BasicFileInfo`),
   `gates.structural` (= `rvt_job.structural_gate_from_manipulated` on
   `verify_manipulated(out, deleted_ids, edited_ids)`), `gates.validation`
   (= `rvt_job.validation_gate`, the mandatory 3-layer validator, 0 errors
   required, full report written beside the file), `gates.line`,
   `gates.hard_gates_passed`, `status_note` (validator PASS is necessary,
   not sufficient), `seconds`. The gate verdict functions are **reused from
   `rvt_job.py`** via the engine's existing cached loader
   (`rvt.frontdoor.edit.load_job_module()`, which resolves in both the repo
   and the plugin layout — no second loader), and `release.opens_in` comes
   from `rvt.frontdoor.target_status.opens_in` (no third copy of that
   honesty string), so `go edit` and the ops door state the very same
   manifest facts. `go` now also stamps `go.verb` (`author` / `edit` / the
   sibling script's name) — the explicit feature marker the bench keys its
   SKIPPED-on-old-builds decision on instead of an exit-code heuristic. An impossible edit (unknown id,
   wrong class, a delete with dependents and no `--cascade`) is `ok:false` +
   ONE `error` line (+ `dependents`), exit 1, no traceback. `info` / `deps`
   ride the same flag (result = the inventory / report + `ok`, `command`,
   `input`, `release`). Write verbs now `makedirs` the `-o` parent (see §3
   finding 2).
3. **`plugin/skills/tekton-edit/SKILL.md`** — Step 1 rewritten to the
   one-call form (`go edit` primary; `go author --rvt … --edit …` by name;
   `go rvt_job.py edit … --ops` for batches; the standalone
   `go rvt_validate.py` demoted to "fallback only, for a file written some
   other way"); the `result` fields the session relays are named; Step 0's
   stale "id-based commands open 2026 files only" corrected (all three
   doors edit 2026/2025/2024 under their own release since #70 —
   `tests/test_edit_own_release.py`, and re-verified here on the bundled
   2025/2024 bases). Frontmatter still exactly `{name, description}`,
   description 599 chars, no angle brackets.
4. **`tools/surface_bench.py`** — new canonical job `go-edit` (ONE call on
   the bundled `G_ABPD_2025.rvt`, Level 1351691, so it needs no earlier
   step; SKIPPED, not failed, on pre-#111 builds; its table note prints the
   in-process split: job / edit+gates / validator seconds + the gates line).
   `edit-roundtrip` (the 3-call pre-#111 flow) stays as the fallback path
   and the before-number.
5. **Tests** — `tests/test_go_edit.py` (NEW, in `tests/ci_shard.txt`;
   `python -I -S` from a plugin copy at a path with spaces, sample-free):
   the one call carries the whole report on 2025 and 2026 (written file,
   N in / N out, both gates PASS with 0 errors, change report = exactly the
   one Level record), an impossible edit is one clear line with exit 1 and
   no traceback, `go edit IN info` is the same dispatch, and `go edit` works
   from a skill that does not colocate `rvt_edit.py`.
   `tests/test_surface_perf.py`: the fixture drives `go-edit` instead of
   `edit-roundtrip`; `test_bare_go_edit_is_one_call_and_bounded` asserts 1
   call (< the legacy 3) with the validator PASS *inside* the call;
   `SESSION_CALL_BUDGET` 5 → **3** (preflight 1 + author 1 + edit 1).

## 2. Evidence — before / after from a BARE surface

Host: this cloud VM, `/usr/bin/python3` = 3.11.15 **without numpy**, plugin
= the freshly built `tekton-plugin.zip` unzipped to a temp path, `env -i`
(cleared env, dead proxies). Input for the by-hand flow: the bundled
`assets/genesis/G_ABPD_2025.rvt`; edit: `set-level --id 1351691
--elevation-ft 5`. "Before" = the flow `tekton-edit/SKILL.md` documented on
`main @ 5a40b22` (`go rvt_edit.py IN info` → `go rvt_edit.py IN set-level …
-o out/edited.rvt` → `go rvt_validate.py out/edited.rvt`); "after" = `go
edit IN set-level … -o out/edited.rvt`. Three runs each, fresh work dir per
run (run 1 pays the `.pyc` compile of a fresh unzip).

| by hand, bare unzip + system python3 | shell calls | wall (3 runs) | `result` in the JSON |
|---|---|---|---|
| before (documented 3-call flow) | **3** | 1.33 s / 1.49 s / 1.38 s | `null` for the edit AND the gate — both reports were prose in `go.stdout` (the truncated-at-4000-chars change report, then `structural verify: {…}`, then `written: …`; the validator's text verdict) |
| after (`go edit`) | **1** | 1.19 s\* / 0.90 s / 0.89 s | one object: `ok`, `output`, `release.line`, `report`, `gates.{structural,validation,line}` (+ `go.verb: "edit"`) |

\* first process on a fresh unzip (bytecode compile); runs 2–3 are the
steady state. The edited output is **byte-identical** before vs after
(`cmp` clean, 598,016 bytes; validates 0 errors / 0 warnings under its own
release, Revit 2025 in → 2025 out).

`tools/surface_bench.py --zip tekton-plugin.zip` (the harness of record;
`edit-roundtrip` edits the authored 2026 prompt room, `go-edit` the bundled
2025 base — same verb, same gate):

| surface | job | shell calls | seconds |
|---|---|---|---|
| cowork (before, `out/bench_before.json`) | edit-roundtrip | 3 | 1.37 |
| cowork (after, `out/bench_after.json`) | edit-roundtrip | 3 | 1.2 |
| cowork (after) | **go-edit** | **1** | **1.0** (job 0.87 s = edit+gates 0.75 s, of which validator 0.4 s) |
| codeexec — stateless, fresh extract EVERY call (after) | edit-roundtrip | 3 | 1.8 (+0.5 s extract) |
| codeexec (after) | **go-edit** | **1** | **1.2 (+0.2 s extract)** |
| cowork | preflight / author-prompt (unchanged paths, noise check) | 1 / 1 | 0.09→0.1 / 2.92→2.9 |

So per edit: **3 model round-trips → 1** on every surface; process wall
about −20…30 % on the persistent surface and −40 % on the stateless one
(two fewer interpreter cold starts + two fewer re-extracts), before
counting the two saved model turns, which dominate on a real surface. The canonical
preflight+author+edit session budget in `tests/test_surface_perf.py` drops
from 5 calls to 3.

`SKILL.md` token weight: 7,700 → 7,735 bytes (+35 B, +0.45 %; description
575 → 599 chars) — the one-call form plus the named `result` fields cost one
line net after trimming; recorded because #112 tracks it.

Gates run this session: `tests/test_go_edit.py` 5 passed (2.9 s);
`tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py
tests/test_plugin_sync.py tests/test_go_edit.py tests/test_edit_own_release.py
tests/test_plugin_validate.py` → 48 passed, 4 skipped (the 4 =
`test_surface_perf.py`, which self-skips without a numpy-capable bare
`python3` on this VM); the same `test_surface_perf.py` re-run with a
numpy-capable `python3` first on `PATH` → 4 passed (go-edit 1 call, PASS,
validator PASS inside the call, session total 3 calls);
`tools/sync_plugin.py --check` clean (deny-audit clean, assets verified);
`plugin/scripts/validate_plugin.py` PASS (24 assertions);
`tools/dev/check_portable_paths.py` ok (2710 paths).

## 3. Findings

1. **Before #111 the edit's machine-readable result was `null`.** `go
   rvt_edit.py … set-level …` printed the change report truncated at 4,000
   chars (not always valid JSON), then two prose lines, so `go` could not
   parse it and the skill had to read prose out of `go.stdout`; same for the
   separate `go rvt_validate.py` gate. The one-call form fixes the shape,
   not just the count.
2. **`rvt_edit.py -o out/edited.rvt` into a directory that did not exist
   died with `FileNotFoundError`** (surfaced through `go.exception`) — the
   exact path the SKILL.md examples use, so a real session's first edit was
   a guaranteed *fourth* round-trip. Write verbs now create the parent.
3. Step 0 of the skill still claimed the id-based tools open 2026 files
   only; #70 made them own-release months of commits ago. Corrected — an
   honest-status line that under-claims still misroutes the session (it
   would have bounced every 2025/2024 id edit to the by-name door).
4. Loading `rvt_job.py` for its two gate functions costs ~6 ms warm (~11 ms
   compiling after a fresh unzip) and buys identical gate semantics/shape
   with the ops door and the front-door manifest; cheaper than a second
   copy of the PASS criteria drifting.
5. (Simplify pass, efficiency lens) Inside the one call, ~68 % of the time
   is the output file being page-walked **twice** — `verify_manipulated`
   (~260 ms) and then `validate_file`'s L1 layer (~415 ms) repeat the same
   CRC/ECC/ISIZE walk. Pre-existing (the ops door does the same), not
   introduced here, but now the only lever left on this path: sharing one
   inflated-stream walk between the two gates is worth ~150–250 ms per
   edit. Filed as a follow-up under #110 rather than widened here (it
   touches `src/rvt/validate.py` / `manipulate.py`, outside this territory).
6. (Simplify pass, altitude lens — decided, recorded so nobody re-litigates
   it blind) The light door's `--json` deliberately does **not** delegate to
   `rvt_job.py edit`'s pipeline: that pipeline also scrubs `BasicFileInfo`
   identity and ledgers provenance, i.e. it writes *different bytes*; a
   `--json` flag must not change the output (before/after here is
   byte-identical by design), and #111 names `rvt_edit.py` + the validator
   as the scope. The two doors keep their documented roles (single proven
   verb by id vs. one consistent multi-op commit with identity + status);
   whether the light door should also assert our identity block is a G2
   question for #19, not a latency one.

## 4. Open questions / follow-ups (filed as issues where task-shaped)

* `go edit` covers the id-based single-verb door. The ops door
  (`rvt_job.py edit --ops`) already runs its gates in-process but prints a
  prose summary + writes the manifest to disk; under `go` its `result` is
  therefore also `null` today. A `--json` for `rvt_job.py edit` (result =
  the manifest) would make the batch door one clean call too — follow-up
  candidate under #110 (search-before-file: none open at write time).
* `tests/test_surface_perf.py` only runs where a bare `python3` with numpy
  exists; it is not in the CI shard. `tests/test_go_edit.py` (numpy-free,
  in the shard) now guards the one-call contract in CI; the perf ceilings
  themselves still want the `windows-latest`/numpy runner from O2.

## BRANCH STATE

* Branch `cam/111-edit-one-call` from `main @ 5a40b22`; PR closes #111.
* Files written: `plugin/skills/_shared/tekton_env.py` (+`_GO_VERBS`, the
  `edit` branch in `_resolve_go_target`, docstrings/usage),
  `tools/rvt_edit.py` (+`--json` one-object mode with both gates via the
  sibling `rvt_job.py`, `_edit`, `_gates`, `_release_block`, `-o` parent
  mkdir; text mode unchanged), `plugin/skills/tekton-edit/SKILL.md` (Step 1
  one-call form, Step 0 honesty fix, reference table),
  `tools/surface_bench.py` (+job `go-edit`, `GO_EDIT_BASE_REL`,
  `GO_EDIT_LEVEL_ID`, its table note), `tests/test_surface_perf.py`
  (go-edit, budget 5→3), `tests/test_go_edit.py` (NEW), `tests/ci_shard.txt`
  (+`tests/test_go_edit.py`), this record. Generated mirrors re-synced by
  `tools/sync_plugin.py`: `plugin/lib/tools/rvt_edit.py`,
  `plugin/skills/tekton-edit/scripts/rvt_edit.py`,
  `plugin/skills/tekton-native/scripts/rvt_edit.py`.
* Not touched: `tools/frontdoor.py`, `src/rvt/frontdoor/base.py`,
  `src/rvt/versions/` (hot files), the `go author` path.
* Shipped vs staged: everything above ships with the PR; nothing staged for
  the viewer (no format bytes changed — the edited output is byte-identical
  to the pre-#111 tool's).
* Bench artefacts (not committed): `out/bench_before.json`,
  `out/bench_after.json`, `out/bench_after_codeexec.json`,
  `out/flow_before_{1,2,3}.json`, `out/flow_after_{1,2,3}.json`.

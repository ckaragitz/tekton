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

---

## eng #267 — 2026-08-10 — the ops/batch door is ONE JSON too (`go rvt_job.py edit … --ops`)

Stream: `eng267` (engineer session under the tech-lead session; branch
`cam/267-go-ops-json`). Closes #267; Refs #111 (§4 above named this
follow-up), #110, #108 / S-2026-08-09-g. Follow-ups filed: #390 (the
hot-file `SKILL.md` wording, patch below), #391 (a `go-ops` bench job).

### 1. What was built

1. **`tools/rvt_job.py --json`** (position-free, stripped before argparse
   exactly like `rvt_edit.py --json`; text mode byte-for-byte unchanged —
   diffed): stdout is exactly ONE JSON object = **the manifest this run
   wrote** (the full `<out>.manifest.json` after the gates, or the stub
   manifest of an aborted run) + `exit_code`. Every progress line
   (`[rvt_job] planning …`, the op log, `validating …`, the text summary)
   streams into **`<out>.log`**, line-buffered, named in `output.log` of
   the JSON *and* of the manifest file — the front door's `build.log`
   shape (#312/#188), so stderr stays **0 B** on a clean run and a skill
   session's Bash result is the one object and nothing else. An unwritable
   log path degrades to an in-memory sink (logging never costs a
   delivery). The two usage-level failures that used to die before any
   manifest existed (input `.rvt` missing → exit 1; `ops.json` empty/not a
   list → exit 2) now write — in `--json` mode only — the same stub
   manifest every other abort writes (`status` = `FAILED (exit N) before
   anything was written; the reason is the one line on stderr`,
   `output.written:false`), so "stdout == the manifest on disk +
   `exit_code`" holds on every path. Implementation is at `main()` level
   (`_dispatch`, `_open_job_log`, a two-key `_RUN` state that
   `write_manifest` / `_write_stub_manifest` fill via `_record_manifest`)
   — **no gate, plan or commit code changed**; `create` / `from-ifc`
   inherit the flag for free (same `run_gates` / stub writers), untested
   beyond argparse because the skills route creation through the front door.
2. **`plugin/skills/_shared/tekton_env.py`**: `_GO_JSON_SCRIPTS =
   {"rvt_job.py"}` — `go rvt_job.py …` appends `--json` (as `go author` /
   `go edit` already do for their tools), so the example `tekton-edit/SKILL.md`
   has printed since #111 (`go rvt_job.py edit their.rvt --ops out/ops.json
   -o out/edited.rvt`) now yields `result` = the manifest with no wording
   change; `go`'s docstring names the shape. Nothing else in the dispatcher
   moved (`go edit`, `go author`, `go rvt_edit.py …` untouched).
3. **`tests/test_go_edit.py`** (+2, already in the CI shard; bare `-I -S`
   plugin copy at a path with spaces, sample-free):
   `test_go_ops_door_result_is_the_manifest` — ONE call on the bundled
   2025 base returns `result.status` PROOF-ONLY…(hard gates PASSED),
   `gates.validation.errors == 0`, structural/identity PASS,
   `base_provenance.base_kind == pinned-composed-genesis`,
   `output.path` exists with the stated bytes, `edit.edited_ids ==
   [1351691]`, `go.stdout` absent, **stderr == ""**, and `result` minus
   `exit_code` **equals the manifest file on disk** while `output.log`
   holds the progress lines; `test_go_ops_door_unplannable_op_is_one_json_stub`
   — an unknown id aborts the whole run, exit 2, `result` is the stub
   (`status` "FAILED (planning: … 999999999 …)", `output.written:false`),
   nothing written.

### 2. Evidence — before / after from a BARE surface

Host: this cloud VM, `/usr/bin/python3` 3.11.15 **without numpy**; plugin
= `tekton-plugin.zip` built by `tools/sync_plugin.py` from `origin/main @
e5b7864` ("before") and from this branch ("after"), each unzipped to a
temp path with spaces; `env -i` (HOME + `/usr/bin:/bin` only, dead
proxies); fresh work dir per run (run 1 pays the `.pyc` compile). Flow:
`skills/tekton-edit/scripts/_bootstrap.py go rvt_job.py edit
<unzip>/assets/genesis/G_ABPD_2025.rvt --ops ops.json -o out/edited.rvt`,
`ops.json = {"ops":[{"op":"set-level","id":1351691,"elevation_ft":5}]}`.

| bare unzip + system python3, `go rvt_job.py edit --ops` | exit | wall (3 runs; median) | stdout | stderr | `result` | `go.stdout` |
|---|---|---|---|---|---|---|
| before (`main`) | 0 | 1.14 / 0.87 / 0.85 s; **0.87 s** | 2,316 B | 0 B | **`null`** | 1,606 B of prose (op log, `[rvt_job] …` progress, the text summary) |
| after (this branch, final head) | 0 | 1.13 / 0.83 / 0.84 s; **0.84 s** | 11,098 B | **0 B** | **the manifest**: 14 keys, `status` "PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)", `gates.validation.errors` 0, `output.path/bytes/sha256/log`, `edit.*`, `exit_code` 0 | absent |

The edited `.rvt` is **byte-identical** before vs after (`cmp` clean,
598,016 bytes; validates 0 errors / 0 warnings under its own release, 2025
in → 2025 out) — only the reporting changed. Wall time is unchanged within
noise (the JSON dump replaces the prose print; the log file is ~1.5 KB).

**Calls per ops-door flow: 2 → 1.** Before, the facts a skill must relay
(status, the four gate verdicts, error counts, the written path) were only
machine-readable in `out/edited.rvt.manifest.json`, i.e. a second Bash
round-trip (`cat` = 9,588 B more) or prose-scraping `go.stdout`; after,
they are `result` in the same call. Byte ledger for a session that wants
the facts: before 2,316 B + 9,588 B over **2** calls = 11,904 B; after
11,098 B in **1** call (−1 model round-trip, −806 B, no prose parsing). A
session that previously ignored the manifest now receives ~8.8 KB more in
that one call — see open question 1.

`tools/surface_bench.py --zip before.zip|after.zip` (the harness of
record; it has **no ops-door job** — #391 — so this is the no-regression /
noise reading across every existing job, 3 runs each, medians):

| surface | job | calls | before s | after s | status |
|---|---|---|---|---|---|
| cowork | preflight | 1 | 0.07 | 0.07 | PASS / PASS |
| cowork | author-prompt | 1 | 2.36 | 2.39 | PASS / PASS |
| cowork | go-author-prompt | 1 | 1.88 | 2.00 | PASS / PASS |
| cowork | go-author-6panels | 1 | 3.83 | 3.83 | PASS / PASS |
| cowork | author-ifc | 1 | 5.52 | 5.54 | PASS / PASS |
| cowork | edit-roundtrip | 3 | 1.08 | 1.11 | PASS / PASS |
| cowork | go-edit | 1 | 0.78 | 0.78 | PASS / PASS |
| cowork | validate | 1 | 0.55 | 0.55 | PASS / PASS |
| cowork | **session** | 10 | 15.98 | 16.46 | — |
| codeexec (fresh extract every call) | preflight | 1 | 0.07 | 0.07 | PASS / PASS |
| codeexec | author-prompt | 1 | 2.42 | 2.36 | PASS / PASS |
| codeexec | go-author-prompt | 1 | 2.35 | 2.38 | PASS / PASS |
| codeexec | go-author-6panels | 1 | 4.17 | 4.33 | PASS / PASS |
| codeexec | author-ifc | 1 | 5.90 | 6.07 | PASS / PASS |
| codeexec | edit-roundtrip | 3 | 1.52 | 1.63 | PASS / PASS |
| codeexec | go-edit | 1 | 0.95 | 1.02 | PASS / PASS |
| codeexec | validate | 1 | 0.80 | 0.76 | PASS / PASS |
| codeexec | **session** | 10 | 18.25 | 18.58 | — |

(`--python-bare` = the venv interpreter, numpy present, as both real
sandboxes ship numpy. With the host's numpy-less `/usr/bin/python3` every
job reads the same before/after too — session 11.20 s → 11.17 s — except
`author-ifc`, which FAILs identically on both builds: the IFC route needs
numpy for placement, and the bench prints its reason as `author --ifc
failed: }`, the pretty-JSON-tail bug already filed as #287.) No job moved
outside ±0.1 s noise; none of them executes `rvt_job.py`.

Gates run this session: `tests/test_go_edit.py` **7 passed** (3.6 s);
`tests/test_edit_own_release.py tests/test_plugin_sync.py
tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py
tests/test_plugin_validate.py` → **45 passed, 5 skipped** (the 5 =
`test_surface_perf.py`, self-skipping without a numpy-capable bare
`python3`); the same `test_surface_perf.py` with the venv first on `PATH`
→ **5 passed**; `tools/sync_plugin.py` then `--check` clean (deny-audit
clean, identity scan == allowlist, assets verified);
`plugin/scripts/validate_plugin.py` PASS (25 assertions);
`tools/dev/check_portable_paths.py` ok (2861 paths). Text mode of
`rvt_job.py edit` diffed byte-identical against `main`'s output (paths
normalised); the four `--json` failure shapes (unknown op, unknown id,
missing input, empty ops) exercised by hand — one object each, exit 2/2/1/2.

### 3. Findings

1. **Progress belongs in a log file, not on stderr, in `--json` mode.**
   #267's DONE said "progress lines go to stderr"; `go` passes the job's
   stderr straight through to the skill session, so that would have put
   ~1.5 KB of `[rvt_job] …` lines (already duplicated in `result.edit.log`
   and the gate blocks) into every Bash result. `go author --json` is
   silent on stderr today; the front door solved the same problem with
   `<out_dir>/build.log` named in the manifest (#312). The ops door now
   does the same (`<out>.log`, `output.log`), and the shard test pins
   `stderr == ""`. Deviation from the issue's letter, recorded here on
   purpose.
2. Under `go`, a *planning* failure still prints the engine traceback on
   stderr (`traceback.print_exc()` in `_cmd_edit`, pre-existing text-mode
   behaviour, unchanged by design: "no gate semantics change"); the one
   JSON's `status` carries the one-line reason, so a skill never needs the
   traceback. Quieting it in `--json` mode is a two-line follow-up if the
   reviewer wants it; left alone to keep this diff to output plumbing.
3. `result` == the manifest file, key for key (+ `exit_code`) — asserted
   by the test — so there is exactly one shape to document for the ops
   door whether a session reads stdout or, later, the file.
4. (Simplify pass) Applied: `_RUN` is reset at the top of every `main()`
   (tests call `job.main([...])` in-process, so a `--json` run followed by
   a text run in one interpreter would otherwise have stamped a stale
   `output.log`); the pre-manifest failure object goes through
   `_write_stub_manifest` instead of a third hand-built shape (finding 3's
   invariant now has no exception); a comment that restated the module
   docstring dropped. Skipped, on purpose: folding `_GO_JSON_SCRIPTS` and
   `_GO_VERBS` into one script-keyed `--json` set (it would also flip `go
   rvt_edit.py …` / `go frontdoor.py …` spellings to `--json` — a
   behaviour change outside #267); a shared stdlib-only log-sink helper for
   `build.log` / `route.log` / `<out>.log` — that is #373's scope
   (frontdoor territory), noted there as a fourth call site.

### 4. Open questions / follow-ups

1. **Token weight of the one object (S-2026-08-09-g).** 11.1 KB ≈ 2.8 k
   tokens per ops-door call; 3.2 KB of it is `gates.base_provenance.g1`
   (the ≤16-entry `blocking` list) and 0.7 KB the PROOF-ONLY `reason`
   sentence that already summarises it; `edit.plans` is 0.6 KB per op. A
   stdout-only projection (keep the file complete; drop `g1.blocking` /
   `edit.plans` / `stats` from what `--json` prints) would roughly halve
   it but breaks finding 3's "result IS the manifest" invariant — a
   product call, not made here. Candidate under #112/#110 if the tech
   lead wants it; not filed (search-before-file: nothing open; the value
   is arguable).
2. #390 — `plugin/skills/tekton-edit/SKILL.md` (hot file, outside this
   engineer session's territory) should stop pointing at the manifest
   *file* and name the ops door's `result` fields. Patch (≤ 6 lines,
   +~120 B):
   ```diff
   -# several ops in ONE consistent commit, set-param, add-instance/add-circuit (gates + manifest already run):
   +# several ops in ONE consistent commit, set-param, add-instance/add-circuit — result IS the manifest (gates already run):
    python "$B" go rvt_job.py edit their.rvt --ops out/ops.json -o out/edited.rvt
    …
   -# any unplannable op ABORTS the whole run (a partial edit is worse than none); manifest = out/edited.rvt.manifest.json
   +# any unplannable op ABORTS the whole run (a partial edit is worse than none): result.status "FAILED (…)", output.written false
    …
    edit is `ok:false` + ONE `error` line (+ `dependents`). Exit 0 = written
   -and both gates PASS. Confirm ids with the user (from `info`) before
   +and both gates PASS. The ops door's `result` is its manifest: relay
   +`status`, `gates.validation.errors` (must be 0) + `structural`/`identity`
   +status, `output.path`; `gates.base_provenance.reason` is the PROOF-ONLY
   +sentence; never re-read the manifest file or `output.log`. Confirm ids with the user (from `info`) before
   ```
3. #391 — `tools/surface_bench.py` job `go-ops` (outside this territory)
   so the ops door has a standing reading on cowork/codeexec and in
   #221's product-smoke; the by-hand table above is its first datum.

### BRANCH STATE (eng #267)

* Branch `cam/267-go-ops-json` from `origin/main @ e5b7864`; PR closes #267.
* Files written: `tools/rvt_job.py` (module docstring OUTPUT MODES;
  `_RUN`, `_record_manifest`, `_dispatch`, `_open_job_log`, `main`'s
  `--json` branch incl. the pre-manifest stub; `import io`), `plugin/skills/_shared/tekton_env.py`
  (`_GO_JSON_SCRIPTS`, the `--json` append for `go rvt_job.py …`,
  docstrings), `tests/test_go_edit.py` (+2 tests), this section.
  Generated mirrors re-synced by `tools/sync_plugin.py`:
  `plugin/lib/tools/rvt_job.py`, `plugin/skills/{tekton-author,tekton-edit,tekton-native}/scripts/rvt_job.py`.
* Not touched: `tools/frontdoor.py`, `plugin/skills/*/SKILL.md` (#390),
  `tools/surface_bench.py` (#391), `tools/rvt_edit.py`, `src/rvt/**`,
  `tests/ci_shard.txt` (the test file was already in the shard).
* Shipped vs staged: everything above ships with the PR; nothing staged for
  the viewer (no format bytes changed — the edited output is byte-identical
  to `main`'s).
* Bench artefacts (not committed): `out/bench267/{before,after,np_before,np_after}_{1,2,3}.{json,md,log}`,
  scratch `flow_{before,after}_{1,2,3}.json`.

---

## eng #266 — 2026-08-10 — one page walk, two gates (`walk_file` shared by `verify_manipulated` + `validate_file`)

Stream: `eng266` (engineer session under the tech-lead session; branch
`cam/266-shared-gate-walk` from `main @ 6d5b82b`). Closes #266; Refs #111
(§3 finding 5 above is where this came from), #110, #108 / S-2026-08-09-g.
Follow-ups filed: **#427** (the validator's *semantic* layer is where the
edit-gate time actually is), **#428** (`release_ctx` calls
`schema.stats()["sha256"]` 4× per edit call).

### 1. What was built

1. **`rvt.validate.WalkedFile` + `walk_file(path)`** — the written container
   read ONCE: raw streams, the ECC pass (syndrome verify + auto-repair → the
   logical bytes Revit's reader sees, its findings kept per stream), gzip
   members with their CRC32/ISIZE verdicts *and payloads* (so a first
   member is never inflated twice), the `Partitions/<N>` block walkers and
   per-(unit, seq) segments; every fact computed on first use and cached.
   Its read surface is `RvtDocument`'s vocabulary (`raw` / `logical` /
   `members` → `container.Member` / `inflate` / `concat` /
   `partition_streams`) plus the walk, so `_primary_partition(doc)` and
   `versions.schema_of(doc)` take it as-is (no second open of the file for
   the schema). Two **views** of the same bytes, `view(repair=…,
   unframed=…)` converts and shares everything already read and verified:
   `repair=True` (the validator's — ECC-repaired logical) and `repair=False`
   (the writer self-check's — bytes exactly as stored, `container.depage`);
   asked for the as-stored view, a repaired walk returns *itself* when its
   ECC pass repaired no payload bit anywhere (every file we just wrote; the
   new `_EccStreamResult.repaired_blocks` counter says so), else a sibling
   over the same raw + ECC caches. Reading, ECC and the gzip scan are
   release-independent, so `walk_file()` enters no context; walkers are
   built on first use under the release the consumer has in force (both
   gates enter the file's own). `close()` drops every cached byte — a
   spent walk pins several times the file's size. `_gzip_members` now *is*
   `container._inflate_at` in a loop (one scan law, one `Member` type).
2. **`Validator` always draws from a `WalkedFile`**: the one handed in
   (`validate_file(path, …, walked=…)` — new *keyword-only, optional*
   parameter; positional signature unchanged) or one it builds lazily over
   its own open container exactly as before (per-stream, so `--layers
   consistency` still ECC-verifies only the streams it touches). ECC
   findings are replayed into the report the first time any layer touches a
   stream (`_logical()`), in the same order as before; `_payload()` /
   `_walkers()` lost their private lazy-ECC copies. One code path ⇒ the
   report is byte-identical with or without a shared walk (§2).
3. **`rvt.manipulate.verify_manipulated(path, …, walked=None)`** consumes a
   walk instead of an `RvtDocument` (`walked.view(repair=False)` when handed
   one, else `walk_file(path, repair=False)` inside its own release context
   — standalone cost ≈ before, no ECC syndrome pass added): partition CRC
   from the shared block walker (every block inflated once — it used to
   inflate the primary partition twice itself: `members()` magic-scan +
   `StreamWalker`), other framed streams from the shared member scan,
   unframed streams not scanned (they never carry gzip; the validator never
   scanned them either), `framing_mismatches` still on the RAW bytes of the
   two re-emitted streams (the exact re-encode law of #395 — reused, no
   page walk re-derived), own schema via `schema_of(walked)` (memoized parse,
   no re-open), ElemTable/header/sentinels/stamps/edited/deleted checks
   unchanged. Because the as-stored view of a repaired walk is a sibling,
   not the repaired object, a CRCIO-auto-repairable flip in a file we just
   wrote still FAILs the self-check while the validator (the calibrated
   arbiter) keeps rating it a WARNING. `_primary_partition(doc, …)` is
   unchanged but duck-typed: an `RvtDocument` or a `WalkedFile`.
4. **Wiring (`run_gates` only):** `tools/rvt_job.py` `_cmd_edit` →
   `walked = walk_file(out)` → `verify_manipulated(…, walked=walked)` →
   `run_gates(…, walked=walked)` → `validation_gate(…, walked=walked)` →
   `validate_file(…, walked=walked)`, then `walked.close()` (identity and
   provenance gates run after it; nothing below needs the bytes);
   `tools/rvt_edit.py::_gates` the same for the `--json` door. `create` / `from-ifc` (whose structural gate is
   `commit.verify_written`, outside this territory) pass no walk and behave
   exactly as before. Nothing else in `rvt_job.py` touched (#396 `--json`,
   #407 descent, #418 flip: rebased on, untouched).
5. **`tests/test_gates_shared_walk.py`** (NEW, 8 tests, fresh-clone safe:
   bundled bases + `tmp_path`; in the shard via
   `tests/ci_shard.d/266-shared-gate-walk.txt`): on the three pinned bases,
   on a front-door-style set-level edit of the 2025 base, on a **hard**-
   damaged copy (64 payload bytes destroyed in the partition's first block)
   and on a **soft**-damaged copy (ONE payload bit flipped — inside Revit's
   auto-repair envelope, so the shared walk carries REPAIRED bytes), the
   `verify_manipulated` dict, `structural_gate_from_manipulated`, the full
   validator `Report.to_json()` (minus timings) and `validation_gate` (minus
   `elapsed_s`/`report_json`) are **identical shared vs. two independent
   walks**; the damaged copies FAIL (hard: both gates; soft: structural
   FAIL `crc_failures ≥ 1`, validation PASS + the auto-repairable WARNING);
   a spy on `WalkedFile.__init__` proves neither gate walks the file again
   when handed the shared walk (and each still does standalone); and on the
   soft-damaged copy the self-check's `view(repair=False)` is a sibling that
   shares the very `raw`/`ecc` objects (nothing re-read or re-verified)
   while its logical bytes differ from the repaired ones — on a clean file
   it is the same object.

### 2. Evidence

**Verdicts unchanged — gate dicts, `main @ 6d5b82b` code vs this branch
(shared walk), same interpreter, same files** (`out/gatedump/*.json`: the
`verify_manipulated` dict + structural gate + the *whole* validator report,
every finding and stat + validation gate; `diff` of `json.tool --sort-keys`):

| file | main vs branch(shared) | branch independent vs shared | structural / validation (errors, warnings) |
|---|---|---|---|
| `G_ABPD.rvt` (2026) | **0 diff lines** | identical | PASS / PASS (0, 1) |
| `G_ABPD_2025.rvt` | **0 diff lines** | identical | PASS / PASS (0, 0) |
| `G_ABPD_2024.rvt` | **0 diff lines** | identical | PASS / PASS (0, 0) |
| set-level edit of the 2025 base (written by *main's* `rvt_edit.py`) | **0 diff lines** | identical | PASS / PASS (0, 0) |
| hard-damaged copy of that edit | 2 lines: `crc_failures` 0 → **1** (see below); every validator finding identical | identical | FAIL / FAIL (3, 1) — as on main |
| soft-damaged copy (1 payload bit) | 2 lines: `crc_failures` 0 → **1**; validator identical | identical | FAIL / PASS (0, 1) — as on main |

The one field that moved is a blind spot closing, not a verdict change:
main's `crc_failures` came from `container.members()`, whose magic-scan
*silently skips* a gzip member whose deflate body no longer inflates
(`_inflate_at` → None → not counted), so a destroyed block read **0**; the
block walker (and the validator: "1/15 block gzip member(s) fail
CRC32/ISIZE", an ERROR it always raised) count it. Both damaged copies were
and are structural **FAIL** through `ecc_mismatches = 1` +
`isize_identity_mismatches = 1`; now `crc_failures` says so too and agrees
with the validator's own count. `rvt_validate` on every output above: 0
errors (the damaged copies excepted, by construction).

**Latency — measured, and honestly: within noise on the bundled bases (`go
edit` ≈ −40 ms, ~5 %; the ops door unchanged).** Host:
this cloud VM (4 vCPU), `/usr/bin/python3` 3.11.15 without numpy (the
venv, numpy 2.4, reads the same ±5 %), plugin = `tekton-plugin.zip` built by
`tools/sync_plugin.py` from `main` ("before") and this branch ("after"),
each unzipped to a temp path with spaces, `env -i` + dead proxies.

*In-process, both gates on the set-level edit output of the 2025 base
(598,016 B), medians of 15 iterations after one warm-up, two repeats:*

| code | mode | both gates | = walk + verify_manipulated + validate_file |
|---|---|---|---|
| main | independent (the only mode) | 474–482 ms | 0 + 60–61 + 411 |
| branch | independent (public API, no walk passed) | 450–466 ms | 0 + 55–63 + 398–408 |
| branch | **shared** (`walk_file` once, both gates handed it) | 451–459 ms | 18 + 48–49 + 382–386 |

(An earlier cut of this branch that entered the release inside `walk_file`
and built walkers eagerly read `walk 29–31`, total 456–484 — the simplify
pass below removed that third `enter_own_release` and the schema re-open.)

*Bare unzip, whole `go` call, alternating before/after, 10 steady-state runs
each (first run of each tree discarded — it compiles `.pyc`), final head:*

| job (system python3, bare unzip) | before: wall median (min) · in-call | after: wall median (min) · in-call |
|---|---|---|
| `go edit <2025 base> set-level --id 1351691 --elevation-ft 5 -o out/edited.rvt` | 0.975 s (0.910) · `seconds` 0.661 | **0.921 s** (0.896) · 0.623 |
| `go rvt_job.py edit <2025 base> --ops ops.json -o out/edited.rvt` | 1.145 s (1.098) · `elapsed_s` 0.8 | 1.144 s (1.101) · 0.8 |

(runs, s — `go edit` before 0.99 0.98 0.97 0.95 0.93 0.96 0.99 0.98 0.98 0.91,
after 0.98 0.95 0.91 0.92 0.90 0.91 1.01 0.92 0.95 0.92; ops door before
1.15 1.12 1.17 1.12 1.19 1.11 1.18 1.15 1.10 1.14, after 1.14 1.12 1.11 1.14
1.10 1.15 1.15 1.15 1.11 1.16.)

*`tools/surface_bench.py --zip before|after --surfaces cowork,codeexec
--jobs go-edit,validate,go-author-prompt --python-bare python3`, 3 runs each
alternating, medians:* §2b below.

#### 2b. `tools/surface_bench.py` (the harness of record) — 6 runs per tree, before/after alternating, `--python-bare python3` (taken on the pre-simplify cut; the final head only got cheaper, §2 table)

| surface | job | calls | before: median (min) s · in-call job · edit+gates · validator | after: median (min) s · in-call job · edit+gates · validator | status |
|---|---|---|---|---|---|
| cowork | go-edit | 1 | 1.18 (0.98) · 1.00 · 0.68 · 0.45 | 1.25 (0.99) · 1.06 · 0.70 · 0.45 | PASS / PASS |
| codeexec (fresh extract every call) | go-edit | 1 | 1.44 (1.29) · 1.21 · 0.73 · 0.50 | 1.39 (1.25) · 1.17 · 0.73 · 0.45 | PASS / PASS |
| cowork | go-author-prompt (untouched path; noise reading) | 1 | 3.32 (2.82) · 3.14 | 3.52 (2.72) · 3.28 | PASS / PASS |
| codeexec | go-author-prompt | 1 | 3.41 (3.09) · 3.21 | 3.48 (3.12) · 3.27 | PASS / PASS |
| both | validate | 1 | SKIPPED (its input is a `samples/` file, absent in a cloud clone) | SKIPPED | — |

Individual runs spread 0.98–3.06 s (`go-edit`, cowork) and 2.7–4.5 s
(`go-author-prompt`) on this VM regardless of tree — the first job of a
fresh workroot also compiles `.pyc` (runs 1–3 ran `go-edit` first, runs 4–6
`go-author-prompt` first). Medians move both ways by less than that spread
and the minima agree within 0.05 s: **no job changed**. The in-call
`validator` field of `go-edit` (rounded to 0.1 s by `rvt_edit.py`) reads
0.5 → 0.4 on some runs only because the ~30 ms of L1 work now happens in
`walk_file` before the validator's stopwatch starts, not because the call got
that much faster (§2 in-process table). Raw JSON: `out/bench_{before,after}_{1..6}.json`
(not committed).

Why the premise was off (finding 5 above estimated 150–250 ms): the
validator's ~0.4 s inside `go edit` is **not** its L1 walk. Measured split of
`validate_file` on these files: L1 `structure` (ECC syndromes of every page +
gzip/CRC + block walker + record walk) ≈ 40 ms, L2 ≈ 26 ms, **L3 `semantic`
≈ 360–390 ms** (decoding all 3,328 seq-102 records against the file's own
schema for reference/connector/typing integrity). And `verify_manipulated`
never ran the ECC *syndrome* pass at all (only the exact re-encode of two
streams, ~10 ms), so "the CRC/ECC/ISIZE walk twice" was really "olefile read
+ inflate twice" ≈ 10–15 ms on a 600 KB container — which is what sharing
removes, inside the run-to-run noise (±20 ms in-process, ±60 ms wall). The
~260 ms once attributed to `verify_manipulated` was its *cold* first call
paying the one-per-process schema parse (`schema.parse`, memoized by digest —
in a real job `Document.from_file` has already paid it). cProfile of one whole
`rvt_edit.py … --json` call, cumulative: `validate_file` 1.34 s of 2.2 s
under the profiler, of which `_layer_semantic` 1.17 s (`objects.decode_record`
0.99 s: `_decode_class` / `_decode_field` / `_decode_scalar` / `_unpack`);
`verify_manipulated` 0.117 s; `enter_host_release` 0.48 s (schema parse
0.29 s once + `schema.stats()` 4 × ~6 ms → #428). **The lever the epic wants
is the semantic decode → #427** (task-shaped, with these numbers).

What the shared walk still buys, unmeasured here because the clone has no
large projects: `verify_manipulated` used to inflate the primary partition
**twice** on its own (magic-scan + walker) and the validator a third time;
now it is once per job when shared (twice standalone → once + the
validator's). On the 600 KB bases that is ~8 ms of zlib; it scales linearly
with partition size (a 30–100 MB user project: hundreds of MB of inflate
avoided per edit). Stated as reasoning, not evidence.

Gates run this session (all with `RVT_SKIP_LARGE=1`, `.venv/bin/python -m
pytest … -q -rs`), final head: `tests/test_gates_shared_walk.py` **8
passed**; `tests/test_go_edit.py tests/test_edit_own_release.py
tests/test_verify_manipulated_release.py tests/test_validate_release.py
tests/test_ecc_final_block.py tests/test_validate_footer_blob.py
tests/test_bare_family_validate.py tests/test_gates_shared_walk.py
tests/test_manipulate.py tests/test_records32.py tests/test_job.py` → **179
passed, 9 skipped (samples absent), 1 xfailed**; `tests/test_plugin_sync.py
tests/test_bootstrap.py tests/test_coldstart.py tests/test_surface_perf.py`
→ 28 passed, 5 skipped; the whole merged CI shard (`python3
tools/dev/shard_list.py --print`, 68 files, on the pre-simplify cut) → 1468
passed, 133 skipped, 3 xfailed, 2 failed = `test_plugin_sync` drift before
the sync — re-run on the final head: see the PR body; `tools/sync_plugin.py`
→ `--check` clean (deny-audit clean, identity scan == allowlist);
`plugin/scripts/validate_plugin.py` PASS; `tools/dev/check_portable_paths.py`
ok (2886 paths).

`/simplify` (four review lenses) → applied: `WalkedFile` speaks
`RvtDocument`'s vocabulary and `_gzip_members` reuses `container._inflate_at`
+ `Member`; the whole-object repair fallback became `view()` (siblings share
raw + ECC, nothing re-read); `walk_file` no longer enters the release or
builds walkers eagerly (−1 `enter_own_release`, walk 30 → 18 ms);
`schema_of(walked)` instead of re-opening the file (−1 open, −2 schema
inflates); member payloads kept so `payload()`/`inflate()` never re-inflate;
`Validator.unit_segments` derived instead of mirrored, passthroughs and
type-checker asserts dropped, `WalkedFile.fallback` and the unused `family=`
parameters removed; `close()` + `run_gates` closing the spent walk so it
does not pin ~5× the file through the identity/provenance gates. Skipped
(noted, not argued): moving ECC findings onto `_EccStreamResult` (would
widen into the ECC classifier for little), letting `run_gates` own the walk
for `verify_written` too (`commit.py`, outside this territory — §4).

`/verify` (the repo's verify skill — edits + validator + plugin surfaces),
final head: `rvt_edit.py <base> set-level … --json` on all three bases →
`ok=True`, structural PASS, validation PASS (0 errors; 2026: 1 warning, the
base's own), "Revit N in, Revit N out", 0.59–0.65 s; `rvt_job.py edit
<2025 base> --ops {set-level, set-mark} --json` → `PROOF-ONLY,
NOT-DELIVERABLE (hard gates PASSED)`, structural/validation/identity PASS,
stderr 0 B, exit 0; a `delete` and a `set-mark` on our own edit output →
both gates PASS; `rvt_validate.py` on the four outputs + the 2025 base → `OK
errors=0` ×5, exit 0; on a 64 KB truncation → `FAIL errors=11` with a text
report and no traceback, exit 1; on a non-CFB file → `FAIL errors=1`, exit 1;
on the hard/soft damaged copies → FAIL 3 errors / OK 0 errors 1 warning;
bare unzip of the rebuilt `tekton-plugin.zip` + `/usr/bin/python3`, `env
-i`: `go edit …` rc 0 ×3 (structural PASS | validation PASS), `go rvt_job.py
edit … --ops` rc 0 ×3 (hard gates PASSED, validator 0 errors).

### 3. Findings

1. The double page-walk was real but cheap; the validator's semantic layer is
   ~80 % of the edit gates (§2) — #427 carries the numbers and candidate cuts.
2. `verify_manipulated`'s old `crc_failures` (container magic-scan) could not
   see a gzip member whose deflate body was destroyed — it skipped it and
   reported 0 (§2 damaged rows). The verdict was still FAIL through the
   ECC/ISIZE checks, so nothing shipped wrongly, but the field under-reported;
   it now matches the validator's block-CRC count.
3. `release_ctx` computes full schema statistics 4× per edit call to read a
   digest it already has as an attribute (~25 ms) — #428.
4. Single `surface_bench` runs differ by ±0.1 s run-to-run on this VM (the
   first job of a fresh workroot also pays `.pyc` compilation): a latency
   claim from one before/after pair is not evidence; alternate and take
   medians (done here; worth a line in the bench's docstring — not this
   territory).

### 4. Open questions

* `commit.verify_written` (the `create` / `from-ifc` structural gate) has the
  same shape as `verify_manipulated` and could take the same `walked=`; left
  alone (outside this territory, and §2 says it would not be measurable on
  the bundled bases either). Worth doing only together with #427, when the
  validator's share drops enough for the walk to matter.

## BRANCH STATE

* Branch `cam/266-shared-gate-walk` from `main @ 6d5b82b`; PR closes #266.
* Files written: `src/rvt/validate.py` (+`WalkedFile`, `walk_file`,
  `_EccStreamResult.repaired_blocks`; `_gzip_members` over
  `container._inflate_at`/`Member`; `Validator` draws from a walk;
  `validate_file(..., *, walked=None)`), `src/rvt/manipulate.py`
  (`verify_manipulated(..., walked=None)` over a walk; `_primary_partition`
  duck-typed), `tools/rvt_job.py` (`run_gates` / `validation_gate` `walked=`
  wiring + close, and the two lines in `_cmd_edit` that produce and pass
  it), `tools/rvt_edit.py` (`_gates`),
  `tests/test_gates_shared_walk.py` (NEW), `tests/ci_shard.d/266-shared-gate-walk.txt`
  (NEW), this record section. Generated mirrors re-synced by
  `tools/sync_plugin.py`: `plugin/lib/src/rvt/{validate,manipulate}.py`,
  `plugin/lib/tools/{rvt_job,rvt_edit}.py`,
  `plugin/skills/tekton-{author,edit,native}/scripts/rvt_job.py`,
  `plugin/skills/tekton-{edit,native}/scripts/rvt_edit.py`.
* Not touched: any hot file; `src/rvt/ecc.py` (its #395 law reused as is);
  `commit.py`; the NO-GO files of this wave.
* Shipped vs staged: everything above ships with the PR; nothing staged for
  the viewer — no written byte changes (the edit outputs are byte-identical
  to `main`'s; only how the gates *read* them changed).
* Bench artefacts (not committed): `out/gatedump/*.{json,rvt}`,
  `out/bench_{before,after}_{1,2,3}.json`, `out/tekton-plugin.{before,after}.zip`,
  `out/shard_after.log`.

## eng #430 — 2026-08-10 — the self-check counts a lost gzip body on EVERY framed stream (`WalkedFile.crc_failures`, by framing)

Stream: `eng430` (engineer session under the tech-lead session; branch
`cam/430-verify-nonprimary-streams` from `main @ 855f764`). Closes #430; Refs
#266 / #429 (whose independent review found the gap). No written byte changes —
only how the structural gate *reads* a file.

### 1. What was built

1. **`rvt.validate.WalkedFile.crc_failures(name) -> int`** — the validator's L1
   gzip law *as a count*, per stream, enumerated by the stream's FRAMING: a
   `Partitions/<N>` by its block headers (`walker(name)`: an uninflatable body
   is a block with `crc_ok=False`); a stream the inventory law frames around
   ONE gzip body — `_GZIP_BODIED = frozenset(REQUIRED_STREAMS) - UNFRAMED_STREAMS`
   = `Contents`, `Formats/Latest`, every `Global/*`, derived from the existing
   constants, no new inventory — whose member scan finds nothing has lost its
   body → **1**; any other stream: its members that fail CRC32/ISIZE (so a
   family's plain-XML `PartAtom`, which the validator only exempts in family
   mode, still reads 0 — the verify dict of an `.rfa` edit is unchanged); an
   unframed stream → 0. Why a method on the walk and not a loop in
   `manipulate.py`: it is a byte-level fact both gates need, next to the
   constants it derives from ("one code path").
2. **`rvt.manipulate.verify_manipulated`**: `crc_failures = Σ walked.crc_failures(n)`
   over every stream (was: block walker on the PRIMARY partition only + a
   magic scan of everything else, which skips a body that will not inflate and
   read 0 for it — the blind spot #429 closed for the primary partition and its
   review found still open on `Global/Latest`, `Contents`, a second partition);
   `walker_errors = Σ len(walker(p).errors)` over **every** partition (was: the
   primary's only — enumerating a twin partition by framing and dropping the
   framing errors found while doing so would be half a law; the validator makes
   both L1 errors); the ElemTable is taken through `walked.payload()` (the
   validator's stricter question: first magic, CRC32/ISIZE-verified, else
   `None`) and a lost / CRC-bad ElemTable is **not parsed**: `elemtable_count`,
   `elemtable_ids_sorted`, `unit0_ids_equal_elemtable` stay `None`,
   `deleted_in_elemtable` `[]`, `header_count` still read → the gate FAILs on
   `crc_failures ≥ 1` *and* `elemtable_count != header_count` — a verdict where
   `main` raised (`ValueError: no gzip members` on a smash; `ValueError:
   ElemTable footer is 26 bytes / graveyard 45 …` on a one-bit flip, i.e.
   `decode_elemtable` parsing the raw-deflate garbage `_inflate_at`'s fallback
   hands back with `crc_ok=False`). Docstring rewritten to say so. Nothing else
   in the function moved; the dict's keys, order and values on a healthy file
   are identical (§2).
3. **Docstring precision (`WalkedFile`, `view()`, `logical()`)** — the class
   keeps the two-view contract; `view()` now says byte-exactly what `logical()`
   is in each case: a sibling `repair=False` view → `container.depage(raw)` (the
   stored payload **plus** the final partial block's pad + short trailer, which
   `depage` leaves as trailing junk); the `repair=False` view of a repairing
   walk that repaired nothing → `self`, whose `logical()` is the ECC pass's
   output = the same stored payload, unaltered, every block's trailer cut, that
   junk included = `depage(raw)` minus its trailing junk, **not** `depage(raw)`
   itself. Measured on `G_ABPD_2025.rvt`: `depage` − ECC output = 37…627 bytes
   per framed stream, always a strict prefix match (`Contents` 42, `Formats/Latest`
   627, `Global/ElemTable` 582, `Global/Latest` 374, `Partitions/20` 597 …); the
   junk sits past the last member / the end record, so no scan, walker or
   verdict differs — which §2's identity also proves.
4. **`tools/rvt_edit.py::_gates`** calls `walked.close()` right after the
   validation gate, as `rvt_job.run_gates` does (the `--json` door no longer
   pins several times the file's size through the JSON assembly).
5. **Tests** (`tests/test_gates_shared_walk.py`, already in the shard via
   `tests/ci_shard.d/266-shared-gate-walk.txt`; 8 → **12**):
   `test_lost_body_off_the_primary_partition_fails_the_self_check[Contents |
   Global/ElemTable | Global/Latest]` — 64 bytes destroyed inside the one gzip
   body → `crc_failures ≥ 1`, structural **FAIL**, validation FAIL with an
   error at that stream, shared == independent (all four dicts), and for the
   ElemTable the counts are `None` (a verdict, not a raise);
   `test_non_primary_partition_is_walked_by_framing` — the edit output with its
   partition duplicated as `Partitions/<N+1>`: verbatim twin → both gates PASS,
   `crc_failures`/`walker_errors` 0, sharing invisible; twin with its first
   block destroyed → `crc_failures ≥ 1`, structural FAIL, primary/ElemTable/edit
   checks still clean, validator error `"… CRC32/ISIZE"` at the twin. All four
   are red against `main`'s engine (checked: `PYTHONPATH=<main>/src pytest -k
   "lost_body or non_primary"` → 4 failed) and green on the head. A shared
   `_smash64()` replaced three copies of the 64×`0xff` write.

### 2. Evidence

**The smash probe, before/after** (`scratchpad/probe/probe.py`: fixtures
written ONCE — the three pinned bases copied, a `set-level` edit of the 2025
base written by `main`'s code, damaged copies of that edit — then judged by
`main @ 855f764` (`git worktree`) and by this head; per file the
`verify_manipulated` dict + `structural_gate_from_manipulated` + the whole
validator report (−timings) + `validation_gate` (−elapsed/report_json) as
`json.tool --sort-keys`, `diff | grep -c '^[<>]'`):

| file | main: structural (crc/ecc/walk, et/hdr) · validation | head | diff lines main→head |
|---|---|---|---|
| `G_ABPD.rvt` / `_2025` / `_2024` | PASS (0/0/0) · PASS (0 err; 2026: 1 warn) | identical | **0 / 0 / 0** |
| set-level edit of the 2025 base | PASS (0/0/0, 3316/3316) · PASS (0, 0) | identical | **0** |
| verbatim second partition added | PASS (0/0/0) · PASS (0, 0) | identical | **0** |
| primary partition, 64 B destroyed (#429's case) | FAIL (1/1/0) · FAIL (3, 1) | identical | **0** |
| `Global/Latest`, 1 bit flipped (raw-deflate fallback inflates it, `crc_ok=False`) | FAIL (1/0/0) · PASS (0, 1 auto-repairable) | identical | **0** |
| **`Global/Latest`, 64 B destroyed** (the review's probe) | **PASS (0/0/0)** · FAIL (2, 0) | **FAIL (1/0/0)** · FAIL (2, 0) | 6 = `crc_failures` 0→1 (dict + gate report) + `status` PASS→FAIL |
| `Contents`, 64 B destroyed | PASS (0/0/0) · FAIL (3, 0) | FAIL (1/0/0) · FAIL (3, 0) | 6 (same three lines) |
| second partition, first block destroyed | PASS (0/0/0) · FAIL (3, 1) | FAIL (1/0/0) · FAIL (3, 1) | 6 (same three lines) |
| `Global/ElemTable`, 64 B destroyed | **raises** `ValueError: 'Global/ElemTable': no gzip members` · FAIL (3, 0) | FAIL (1/1/0, et **None**/3316) · FAIL (3, 0) | verdict instead of a traceback |
| `Global/ElemTable`, 1 bit flipped | **raises** `ValueError: ElemTable footer is 26 bytes / graveyard 45 …` · PASS (0, 1) | FAIL (1/1/0, et None/3316) · PASS (0, 1) | verdict instead of a traceback |

Every validator finding is identical main vs head on every row (the validator
was not touched); on the head shared == independent on every row (the tests pin
it). `verify_manipulated` on the tracked Revit-born family
`tekton-eval-kit/TEST-KIT/08_eaton_panelboard_family.rfa` (carries `PartAtom`):
`crc 0 / ecc 0 / walk 0 / et 41/41 / stamps ok / fallbacks []` on main **and**
head — the `.rfa` dict is unchanged too.

**Latency — unchanged, as expected (no extra inflate anywhere).** Bare unzip of
`tekton-plugin.zip` built from `main` ("before") and from this branch
("after") into paths with a space, `env -i PATH=/usr/bin:/bin` + dead proxies,
`/usr/bin/python3` 3.11, `go edit assets/genesis/G_ABPD_2025.rvt set-level --id
1351691 --elevation-ft 5 -o out/edited.rvt --json`, alternating: every run rc 0,
`ready: true`, `tekton: READY …`, structural PASS | validation PASS (0 errors),
stderr 0 B. Wall (s), 6 steady-state runs each after the `.pyc`-compiling first
run: before 0.512 0.518 0.526 0.528 0.559 (median **0.526**, in-call `seconds`
0.446–0.485) · after 0.511 0.528 0.529 0.532 0.570 (median **0.529**, in-call
0.442–0.498); an earlier batch of 4+4 read 0.515–0.530 both sides. Within
run-to-run noise; re-taken on the final head: see BRANCH STATE. Efficiency
review of the diff: cost-neutral on the one-partition bases (the partition loop
is the cached primary walker), a small saving on multi-partition files in the
shared path (a twin partition is now inflated once by the walker both gates
share instead of walker + a separate magic-scan inflate).

**Gates** (`RVT_SKIP_LARGE=1 … -q -rs -p no:cacheprovider`):
`tests/test_gates_shared_walk.py` **12 passed**; neighbours
`test_go_edit test_edit_own_release test_verify_manipulated_release
test_validate_release test_ecc_final_block test_validate_footer_blob
test_bare_family_validate test_manipulate test_records32 test_job
test_modify_family_carrier test_plugin_sync test_bootstrap test_coldstart
test_surface_perf` + the above → **223 passed, 14 skipped (samples absent), 1
xfailed**; `tools/sync_plugin.py` run → `--check`: *plugin in sync with source
(deny-audit clean, identity scan == allowlist, assets verified)*;
`plugin/scripts/validate_plugin.py` PASS (25 assertions);
`tools/dev/check_portable_paths.py` ok (2906 paths); whole merged CI shard: see
BRANCH STATE.

`/simplify` (reuse / simplification / efficiency / altitude lenses) → applied:
the name-prefix helper first written in `manipulate.py` became
`WalkedFile.crc_failures` over `REQUIRED_STREAMS − UNFRAMED_STREAMS` (reuse +
altitude); the ElemTable guard uses the existing `WalkedFile.payload()` instead
of re-deriving "first member CRC-ok"; the `pw = w if name == pname else …`
branch and a try/except that counted a twin partition's unparseable framing as
`walker_errors += 1` while the primary's raises were dropped for ONE policy
(any partition whose stream header does not parse raises, exactly as before on
the primary — see §4); the always-true `u0_102_ids is not None` guard went; the
depage/junk account is stated once (`view()`), class and `logical()` point at
it; `_smash64` in the tests. Skipped: nothing.

### 3. Findings

1. Off the primary partition, `main`'s self-check could not see a destroyed
   gzip body at all (`Global/Latest`, `Contents`, a second partition: structural
   PASS, `crc_failures 0`, while the validator FAILed) and turned a destroyed or
   bit-flipped `Global/ElemTable` into a traceback instead of a verdict. Nothing
   shipped unlabelled — both gates run on every edit and the validation gate
   caught each case — but a structural-only reader (`--no-provenance`, the
   `structural_verify` block `convert.modify_family` records) was told PASS.
2. A one-bit flip and a 64-byte smash in a `Global/*` body behave differently
   under the magic scan: the flip usually still raw-inflates (→ a member with
   `crc_ok=False`, counted even on `main`), the smash does not inflate at all (→
   no member → invisible to a scan). Only enumeration by framing sees both.

### 4. Open questions / follow-ups

* A partition whose 44-byte stream header does not parse (`parse_stream_header`
  → `ValueError`) still makes `verify_manipulated` **raise** rather than return
  a FAIL verdict — for the primary (as always) and, now uniformly, for a twin;
  likewise `_primary_partition()` inflates the ElemTable to choose among several
  partitions, so a lost ElemTable on a *multi*-partition file raises there before
  the verdict logic runs. Making those verdicts too means leaving every
  block-dependent field `None` the way the ElemTable fields now are; and the
  deeper cut the altitude review named — `walk_file` inferring the family shape
  (`PartAtom` present → unframed) so both gates apply literally one inventory
  law with no `_GZIP_BODIED` distinction — touches the validator's family mode.
  Both filed together as one task-shaped follow-up: **#458** (Refs #430).

### BRANCH STATE (eng #430)

* Branch `cam/430-verify-nonprimary-streams` from `main @ 855f764`; PR closes #430.
* Files written: `src/rvt/validate.py` (`_GZIP_BODIED`, `WalkedFile.crc_failures`;
  docstrings of `WalkedFile` / `view()` / `logical()` — nothing else in the
  module touched, #429/#447's plan path intact), `src/rvt/manipulate.py`
  (`verify_manipulated` only), `tools/rvt_edit.py` (one line),
  `tests/test_gates_shared_walk.py` (+4 tests, `_with_second_partition`,
  `_smash64`), this record section. Generated mirrors re-synced by
  `tools/sync_plugin.py`: `plugin/lib/src/rvt/{validate,manipulate}.py`,
  `plugin/lib/tools/rvt_edit.py`, `plugin/skills/tekton-{edit,native}/scripts/rvt_edit.py`.
* Not touched: `src/rvt/versions/**` (records32's verify is #394's), `tools/rvt_job.py`
  (eng #440's), any hot file, the validator's layers.
* Shipped vs staged: everything ships with the PR; nothing for the viewer (no
  written byte changes).
* Gates on the final head: whole merged CI shard (`python3 tools/dev/shard_list.py
  --print`, `RVT_SKIP_LARGE=1 … -q -p no:cacheprovider`) → **1560 passed, 134 skipped,
  3 xfailed in 329 s**; `tests/test_gates_shared_walk.py` 12 passed; neighbours 223
  passed / 14 skipped / 1 xfailed; sync `--check` clean, `validate_plugin` PASS,
  portable paths ok. `/verify` on the final head: `rvt_edit.py <base> set-level …
  --json` on all three bases → rc 0, stderr 0 B, `ok=True`, structural PASS |
  validation PASS (0 errors), "Revit N in, Revit N out"; `rvt_validate.py` on the
  three outputs → VALID 0 errors; `rvt_job.py edit <2025 base> --ops {set-level,
  set-mark} --json` → `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`, structural
  PASS / validation PASS, stderr 0 B; the edit door on the twin-partition-damaged
  INPUT → file written (827,392 B) and labelled `structural FAIL (crc_failures=1 …)
  | validation FAIL (3 errors)`, rc 1, stderr 0 B (delivered, labelled — main said
  structural PASS there); truncated / non-CFB files → INVALID 11 / 1 error(s), no
  traceback. Bare unzip of the final `tekton-plugin.zip` vs main's, `env -i
  /usr/bin/python3`, `go edit … set-level --json`, alternating 4+4: every run rc 0,
  READY, both gates PASS; wall before 0.537 0.599 0.529 s (first, `.pyc`-compiling
  run 0.923) vs after 0.512 0.552 0.527 s (first 0.844) — unchanged.
* Probe artefacts (scratchpad, not committed): `probe/probe.py`, `probe/fx/*.rvt`,
  `probe/{main,head}/*.json`, `bench.sh`, `before.zip` / `after.zip`.

---

## eng #458 — 2026-08-10 — an unparseable partition header is a FAIL *verdict* of the self-check (never a raise); the walk reads the family shape off the file

Stream: `eng458` (engineer session under the tech-lead session; branch
`cam/458-partition-header-verdict` from `main @ 2767197`). Closes #458; Refs
#430 / #460 (whose `/simplify` altitude review and independent review named both
gaps). No written byte changes — only how the structural gate *reads* a file.

### 1. What was built

1. **`rvt.manipulate.verify_manipulated` never raises on a partition whose
   stream header does not parse.** Every partition is asked
   `walked.framing_error(p)` first; one whose 18-byte header fails
   `parse_stream_header` (or whose framing raises anything else while walking)
   is **ONE walker error** (`walker_errors += 1`, exactly what the validator
   makes of it: one L1 error) and its reason is recorded under a key present
   only when earned — `rep["framing_errors"] = {<partition>: "partition
   header/framing: <exc>"}`, worded byte-for-byte as the validator's finding on
   the same partition (the tests pin `framing_errors[p] in errors_at(report, p)`).
   Uniform for the primary and a twin. The block-dependent facts —
   `isize_identity_mismatches`, `sentinel_last`, `stamps_ok` (and
   `unit0_ids_equal_elemtable`, as before) — now *start* `None` (= not checked,
   never PASS) and are filled in by the ONE branch that walks the primary's
   blocks; when the **primary**'s header does not parse that branch does not run,
   so they stay `None` by construction (no compute-then-overwrite), `edited` stays
   `{}`, and `structural_gate_from_manipulated` fails on `walker_errors ≥ 1` *and*
   `bool(stamps_ok)`; `header_count` is still the u32 at offset 14 (`_header_count`,
   `None` under 18 bytes), `crc_failures` / `ecc_mismatches` / the ElemTable facts
   are read as before. When it is a **twin**, the primary's facts are all intact
   (edited record clean, sentinels, stamps, counts) and only
   `walker_errors`/`framing_errors` speak. On every healthy file the dict's keys,
   order and values are identical to `main`'s (§2).
2. **A lost `Global/ElemTable` on a multi-partition file is a verdict too.**
   `_primary_partition()` inflated the ElemTable to choose among several
   partitions and raised `ValueError: no gzip members` before #430's verdict
   logic ran. It now reads every partition's declared count through one
   `_header_count(doc, pn) -> Optional[int]` (shared with `verify_manipulated`;
   `None` for a stream under 18 bytes) and treats the ElemTable count as an
   optional input (any failure to read it → no match), so the existing tie-break
   — the partition declaring the most elements — decides and `verify_manipulated`
   reaches its `payload() is None → counts None → FAIL` path; on healthy files
   the choice is the same first-match / first-max as before (`commit_plans` uses
   it too: identical outputs, §2). (`_primary_partition` is named in the issue's
   Territory but not in the engineer brief's "verify_manipulated ONLY" — flagged
   to the tech lead.) `ecc_mismatches` skips an *absent* `Global/ElemTable`
   instead of a `KeyError` (its loss is already the counts-`None` FAIL).
3. **`rvt.validate.WalkedFile` reads the family shape off the file** (the #460
   review note / issue DONE 3, the part inside `WalkedFile`):
   `unframed_streams_of(names) = UNFRAMED_STREAMS | {"PartAtom"} ∩ names` is the
   default `unframed` set of a `WalkedFile` / `walk_file()` built without an
   explicit one (the validator still passes its mode's set explicitly, so every
   validator report is byte-identical in both modes). With the shape known,
   `crc_failures()` applies the validator's L1 law *literally* — an unframed
   stream → 0; a partition → its blocks with `crc_ok=False` (an unparseable
   framing enumerates none → 0, the failure is `framing_error`'s); **any other
   framed stream with no gzip member has lost its body → 1** — and the private
   `_GZIP_BODIED = REQUIRED_STREAMS − UNFRAMED_STREAMS` list is **retired**. The
   one divergence the #460 review named (a memberless framed stream outside
   `REQUIRED_STREAMS`: self-check 0, validator ERROR) is gone: both gates now
   FAIL it (`test_memberless_framed_stream_fails_both_gates_alike`), while a
   family's `PartAtom` still reads 0 because it is *unframed by the file's own
   shape*, not by an exemption list. New accessor `WalkedFile.framing_error(pname)
   -> Optional[str]` (the cached walker exception, worded as the L1 finding).
4. **Tests** — new file `tests/test_partition_header_verdict.py` (**11**), in the
   shard via `tests/ci_shard.d/458-partition-header-verdict.txt`: primary header
   zeroed (first 16 bytes) → dict, `walker_errors 1`, `framing_errors == {primary: …}`,
   block facts `None`, structural FAIL, validator FAIL with the identical message,
   shared == independent; twin header zeroed → FAIL, `framing_errors == {twin: …}`,
   primary facts intact, edit clean; both zeroed → `walker_errors 2`; lost
   ElemTable on a two-partition file → verdict (counts `None`, FAIL), no
   `framing_errors`; identity: the three pinned bases, the edit and a verbatim
   twin copy → PASS and `list(v) == VERIFY_KEYS` (no always-present key added);
   `unframed_streams_of` / `walk_file(...).unframed` on a base and with an
   explicit set; the tracked Revit-born `.rfa` → `PartAtom` unframed, `crc 0`,
   `ecc(PartAtom) is None`, shared == independent, family-mode validator OK; a
   memberless framed `Global/Orphan` → self-check `crc_failures 1` / FAIL exactly
   where the validator errors. Against `main`'s engine (test file copied into a
   `main @ 2767197` worktree, import of the new helper shimmed): **7 failed, 4
   passed** — the 4 identity tests pass on both trees, the 7 behaviour tests are
   red on main and green here. `tests/test_gates_shared_walk.py` (eng #470's this
   wave) untouched and still 12 passed.

### 2. Evidence

**The header-zero probe, before/after** (`scratchpad/probe/`: fixtures written
ONCE by `main @ 2767197`'s engine in a `git worktree` — the three pinned bases
copied, a `set-level` edit of the 2025 base, a verbatim twin copy, #460's smash
set, and the new cases; then judged by main and by this head in separate
interpreters: `verify_manipulated` dict + `structural_gate_from_manipulated` +
the whole validator report (−timings) + `validation_gate` (−elapsed/report_json),
independent AND shared walk, `json.tool --sort-keys`, `diff | grep -c '^[<>]'`):

| fixture | main: structural (crc/ecc/walk, et/hdr) · validation | head | diff lines |
|---|---|---|---|
| `G_ABPD` / `_2025` / `_2024` | PASS (0/0/0) · PASS | identical | **0 / 0 / 0** |
| set-level edit of the 2025 base; verbatim twin added | PASS · PASS | identical | **0 / 0** |
| #460's smash set: primary 64 B, `Global/Latest`, `Contents`, `Global/ElemTable`, twin first block | FAIL · FAIL (et `None`/3316 for the ElemTable) | identical | **0 / 0 / 0 / 0 / 0** |
| **primary header zeroed** | **raises** `ValueError: unexpected Partitions header: v=0 cls=0x0` · FAIL (4 err) | **FAIL** (0/1/**1**, 3316/0; block facts `None`; `framing_errors={Partitions/20: …}`) · FAIL (4 err, report identical) | verdict instead of a traceback |
| **twin header zeroed** | **raises** (same) · FAIL (2 err) | **FAIL** (0/0/**1**, 3316/3316; primary facts intact, edit clean; `framing_errors={Partitions/21: …}`) · FAIL (2, identical) | ” |
| both headers zeroed | raises · FAIL (8) | FAIL (0/1/**2**) · FAIL (8, identical) | ” |
| **lost ElemTable on the twin (two-partition) file** | **raises** `ValueError: 'Global/ElemTable': no gzip members` · FAIL (3) | FAIL (1/1/0, et **None**/3316) · FAIL (3, identical) | ” |

Every validator report and validation gate is byte-identical main vs head on
every row and view (the validator's code path is untouched: it passes its own
`unframed` set); shared == independent on every row on the head. Tracked
eval-kit files (`08_eaton_panelboard_family.rfa` with `PartAtom`, projects
02/04/06): `verify_manipulated` (independent + shared) and the validator report
in project AND family mode, plus the door's actual pairing on the `.rfa`
(`walk_file` → verify → project-mode `validate_file(walked=…)`) → **0 diff lines**
main vs head; the `.rfa` reads `crc 0 / ecc 0 / walk 0 / et 41/41` on both.

**The door's gate stage** (`tools/rvt_edit.py::_gates` verbatim: `walk_file` →
`verify_manipulated` → `structural_gate` → `validation_gate` → the `line`) on a
door-written `set-level` edit of the 2025 base whose twin / primary header was
zeroed *after* writing — the writer-regression case the self-check exists to
label: main → `RAISED ValueError` both times (no line, no validation gate, no
manifest past that point); head → `structural FAIL (crc_failures=0,
ecc_mismatches=0, walker_errors=1, stamps_ok=True) | validation FAIL (2 errors)`
for the twin and `structural FAIL (… ecc_mismatches=1, walker_errors=1,
stamps_ok=None) | validation FAIL (4 errors)` for the primary, `framing_errors`
naming the partition with the validator's exact message. Through `rvt_job.py
edit … --json` a header-zeroed **input** never reaches the gates on either tree:
`mutate.Document.from_file` walks every partition at load and the door answers
rc 1, ONE stderr line `[rvt_job] FAILED (edit: ValueError: unexpected Partitions
header …)`, ONE JSON (`status FAILED (edit: …)`), no traceback, nothing written —
graceful already, input-side, outside this territory (see §4).

**Where the reason lands in the one JSON.** `structural.report.walker_errors`
carries the count and `validation.top_findings` the identical text; the text
under `structural` itself needs `"framing_errors"` in `rvt_job.structural_gate_from_manipulated`'s
keep-list — `tools/rvt_job.py` is outside this territory this wave, patch in §4.

**Latency — unchanged (no extra inflate: `framing_error` is the cached walker).**
Bare unzip of `tekton-plugin.zip` built from `main @ 2767197` ("before") and from
this head ("after") into paths with a space, `env -i PATH=/usr/bin:/bin` + dead
proxies, `/usr/bin/python3` 3.11.15, `go edit assets/genesis/G_ABPD_2025.rvt
set-level --id 1351691 --elevation-ft 5 -o out/edited.rvt --json`, alternating
5+5 after a `.pyc`-compiling first pair (1.19 / 1.12 s): every run rc 0,
`ready: true`, `tekton: READY …`, structural PASS | validation PASS (0 errors),
stderr 0 B; wall before 0.652 0.891 0.623 0.652 0.663 s (median **0.652**, in-call
0.535–0.794) · after 0.644 0.622 0.809 0.629 0.643 s (median **0.643**, in-call
0.539–0.721). Within run-to-run noise.

**Gates** (`RVT_SKIP_LARGE=1 … -q -rs -p no:cacheprovider`):
`tests/test_partition_header_verdict.py` **11 passed** (5 s); neighbours
`test_gates_shared_walk test_manipulate test_verify_manipulated_release
test_edit_own_release test_validate_release test_ecc_final_block
test_validate_footer_blob test_bare_family_validate test_records32 test_job
test_go_edit test_modify_family_carrier test_manipulate_import_context` →
**198 passed, 9 skipped (samples absent), 1 xfailed, 1 failed** — the failure is
`test_manipulate.py::test_job_set_param_op_lands_an_elementid_row_via_holder`
(`from test_job import _load_job`, removed by #471), red on `main @ 2767197`
itself and already filed as **#476**; not this stream's file. `tools/sync_plugin.py`
run → `--check`: *plugin in sync with source (deny-audit clean, identity scan ==
allowlist, assets verified)*; `plugin/scripts/validate_plugin.py` PASS (25
assertions); `tools/dev/check_portable_paths.py` ok; whole merged CI shard: see
BRANCH STATE. Drives: `rvt_edit.py <base> set-level … --json` on all three bases
→ rc 0, stderr 0 B, `ok=True`, structural PASS | validation PASS (0 errors),
"Revit N in, Revit N out"; `rvt_validate.py` on the three outputs → OK 0 errors;
`rvt_job.py edit <2025 base> --ops {set-level} --json` → rc 0, stderr 0 B,
`PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`, structural PASS / validation
PASS, 598,016 B written.

### 3. Findings

1. The verify-side raise is unreachable from the edit doors with a damaged
   *input* (the loader walks every partition first), so in production it could
   only fire on a **writer regression** — precisely the case the self-check is
   for, and precisely when a traceback instead of a labelled file costs the most
   (the validation gate, provenance and the manifest never run). Direct callers
   (`convert.modify_family`'s `structural_verify`, `famload`, the genesis tools,
   tests) met it on any foreign file with an odd header.
2. Reading the family shape off the inventory makes the two gates' inventory law
   one sentence with no exemption list, and costs nothing on projects (the
   inferred set *is* `UNFRAMED_STREAMS` there, so `view()` still returns `self`
   for the validator's project mode; on an `.rfa` the family-mode validator now
   shares the walk object outright, the project-mode one takes a sibling view as
   before-in-reverse).

### 4. Open questions / follow-ups

* **Patch offered, outside territory (`tools/rvt_job.py`, 1 line):** add
  `"framing_errors"` to the keep-tuple in `structural_gate_from_manipulated` so the
  manifest's `structural.report` carries the reason text next to the count (today
  the text is in `validation.top_findings` and in the verify dict):
  ```
  -        "unit0_ids_equal_elemtable")}
  +        "unit0_ids_equal_elemtable", "framing_errors")}
  ```
  (`v.get()` → `None` on healthy files, so manifests of healthy jobs gain one
  `null` field; if byte-identity of healthy manifests matters more, keep it
  conditional: `if v.get("framing_errors"): keep["framing_errors"] = …`.) → in **#486**.
* **Issue DONE 3, the validator half (design call, split as the issue allows):**
  `Validator.__init__` could default `family` from the file
  (`"PartAtom" in names`, i.e. `unframed_streams_of`) with the explicit flag still
  honoured, and `_layer_structure` could word its partition finding through
  `walked.framing_error(pname)` (same string by construction; today the two agree
  by convention, and differ for a partition under 18 bytes: validator "partition
  stream too short" vs `framing_error`'s `struct.error` text). Both touch the
  validator proper, which the engineer brief kept out of this wave's territory
  ("WalkedFile walker ONLY"); filed together with the `rvt_job.py` line above as
  **#486** (Refs #458).
* The efficiency review measured the one latent cost of the inferred shape: a
  project-mode `validate_file(walked=walk_file(x.rfa))` now takes a sibling view
  (~12 ms on a 598 KB file; no caller does this today — the doors walk `.rvt`
  outputs, `modify_family` passes no walk), while the family-mode pairing gains
  `self`. #486's first bullet removes the mismatch at its source.
* The edit doors refuse a header-damaged **input** at load with one FAILED line
  (graceful, rc 1, one JSON); whether such an input should instead be edited
  around is a product question nobody has asked — not filed.
* `/simplify` (reuse / simplification / efficiency / altitude, four reviewers) →
  applied: block facts start `None` and one `if pname not in framing:` branch fills
  them (was: loop over empty segments then overwrite); one loop builds
  `framing_errors` and `walker_errors` together over a hoisted `parts`; `_header_count`
  shared by `_primary_partition` and `verify_manipulated` (was: guarded at one read
  site, unguarded at its twin); the ElemTable count in `_primary_partition` is an
  optional input (`except Exception`, was a two-type list that missed `KeyError`);
  redundant `frozenset()` dropped; `unframed_streams_of` docstring cut to two lines;
  the test's unused `job` fixture parameter dropped and the smash offset named.
  Skipped, with reason: an always-present `"framing_errors": {}` key (would break the
  0-diff identity on healthy files the brief asks for — the key stays conditional,
  like `elemtable_count_expected`); `Validator` adopting `unframed_streams_of` /
  `framing_error` (territory → #486); lifting the test helpers shared with
  `test_gates_shared_walk.py` into `conftest.py` (both files are eng #470's this wave).

### BRANCH STATE (eng #458)

* Branch `cam/458-partition-header-verdict` from `main @ 2767197`; PR #482 closes #458;
  follow-up filed: #486 (validator adopts `unframed_streams_of` / `framing_error`,
  `rvt_job` keep-tuple gains `framing_errors`).
* Files written: `src/rvt/manipulate.py` (`_header_count` new, `_primary_partition`,
  `verify_manipulated` — nothing else in the module; #455/#469's `_emit_block` and
  every plan/commit path untouched), `src/rvt/validate.py` (`unframed_streams_of`
  new, `WalkedFile.__init__` default, `WalkedFile.framing_error` new,
  `WalkedFile.crc_failures`, `_GZIP_BODIED` removed, one import line — the
  `Validator` class, #429/#447's plan path, #466's ref_sink hoist untouched),
  `tests/test_partition_header_verdict.py` (new, 11 tests),
  `tests/ci_shard.d/458-partition-header-verdict.txt` (new), this record section.
  Generated mirrors re-synced by `tools/sync_plugin.py`:
  `plugin/lib/src/rvt/{manipulate,validate}.py`.
* Not touched: `src/rvt/versions/**`, `tools/rvt_job.py`, `tools/rvt_edit.py`,
  `tests/conftest.py`, `tests/test_gates_shared_walk.py`, any hot file.
* Shipped vs staged: everything ships with the PR; nothing for the viewer (no
  written byte changes — `commit_plans` outputs byte-identical: the three
  `rvt_edit.py set-level` outputs validate 0 errors exactly as on main).
* Gates on the final head (post-`/simplify`): `tests/test_partition_header_verdict.py`
  + `tests/test_gates_shared_walk.py` → **23 passed** (15 s); neighbours + plugin
  tests (`test_manipulate test_verify_manipulated_release test_edit_own_release
  test_go_edit test_job test_modify_family_carrier test_manipulate_import_context
  test_bootstrap test_coldstart test_surface_perf test_plugin_sync`) → 84 passed,
  14 skipped, 1 failed = #476 (pre-existing on main); whole merged CI shard
  (`python3 tools/dev/shard_list.py --print`, `RVT_SKIP_LARGE=1 … -q -p
  no:cacheprovider`, taken on the pre-simplify head whose behaviour the identity
  probe shows unchanged by the pass) → **1628 passed, 139 skipped, 3 xfailed, 1
  failed (#476) in 421 s**; sync `--check` clean, `validate_plugin` PASS (25),
  portable paths ok (2913). Identity probe re-run on the final head: 0 diff lines
  on every healthy / #460 fixture and on the eval-kit files, shared == independent
  everywhere. `/verify` on the final head: `rvt_edit.py <base> set-level … --json`
  on all three bases → rc 0, stderr 0 B, `ok=True`, structural PASS | validation
  PASS (0 errors), "Revit N in, Revit N out"; `rvt_validate.py` on the three
  outputs → OK errors=0; `frontdoor.py author --rvt <2025 base> --edit "set level
  1351691 elevation to 5 ft" --json` → rc 0, stderr 0 B, `PROOF-ONLY,
  NOT-DELIVERABLE (hard gates PASSED)`, job manifest structural PASS (walker_errors
  0) / validation PASS (0), output validates 0 errors (an off-grammar phrasing →
  rc 3, one clean `edit not understood` error, no traceback); validator row: three
  bases OK 0/0/0 errors, 64 KiB truncation → FAIL 11 errors, non-CFB → FAIL 1
  error, the header-zeroed / lost-ElemTable fixtures → FAIL 4 / 2 / 3 errors — no
  traceback anywhere; `verify_manipulated` on those fixtures → dicts with
  `walker_errors` 1 / 1 / 2 and `framing_errors` naming the partition(s), counts
  `None` for the lost ElemTable. Bare unzip of the final `tekton-plugin.zip` vs
  main's, `env -i /usr/bin/python3` 3.11.15, `go edit … set-level --json`,
  alternating 4+4: every run rc 0, READY, both gates PASS, stderr 0 B; wall before
  0.656 0.698 0.636 0.616 s vs after 0.651 0.644 0.661 s (+ the fresh unzip's
  `.pyc`-compiling first run 1.030 s) — unchanged.
* Probe artefacts (scratchpad, not committed): `probe/{make_fx,judge,rfa,rfa2}.py`,
  `probe/fx/*.rvt` (written by main's engine), `probe/{main,head}/*.json`,
  `door/gate_stage.py`, `bench.sh`, `before.zip` / `after.zip`.

## eng #486 — 2026-08-10 — the validator words its framing finding through the walk and takes its family shape from the file; the manifest's structural block carries `framing_errors`

Stream: `eng486` (engineer session under the tech-lead session; branch
`cam/486-validator-file-shape` from `main @ 4cc81dd`, i.e. after #495's
`_jsonsafe` writer lines in `tools/rvt_job.py`). Closes #486; Refs #458 (whose
§4 offered both halves as patches), #430, #266. No written byte changes and no
verdict changes: one wording now comes from one place, one set from one law,
and one dict key travels one block further.

### 1. What was built

1. **`Validator._layer_structure` words the partition-framing finding through
   `WalkedFile.framing_error(pname)`** — `why = walked.framing_error(pname);
   if why: rep.error(L_STRUCTURE, pname, why); continue`, then
   `walked.walker(pname)` (cached, cannot raise once `framing_error` said
   `None`). The inline `f"partition header/framing: {e}"` is gone, so the
   validator's L1 error and the self-check's `framing_errors[p]` are one string
   by construction (#458 had them equal by convention). The `< 18 bytes →
   "partition stream too short"` pre-check stays first, so a stub partition
   keeps its old wording (folding it into `framing_error` would have changed the
   self-check's text for that case — `WalkedFile` is #458's, not this
   territory; pinned as-is by `test_validator_words_the_framing_finding_through_the_walk`).
2. **`Validator` takes its family-mode unframed set from the file.**
   `__init__` no longer spells `UNFRAMED_STREAMS | {"PartAtom"}`; `_open` sets
   `self.unframed_streams = unframed_streams_of(names) if family else
   UNFRAMED_STREAMS` once the inventory is known (from the given walk's `names`,
   else the freshly opened container's), and only then takes the caller's walk
   as `walked.view(repair=True, unframed=…)`. In family mode that set *is* the
   walk's default shape, so a shared `walk_file()` object is used outright on an
   `.rfa` **and** on a project (`--family` on a `.rvt`: 1 sibling view on main →
   0); project mode keeps `UNFRAMED_STREAMS` — the explicit flag / `--project` is
   honoured exactly, `PartAtom` judged framed on purpose — so every report in
   either mode is byte-identical (§2) and the one remaining sibling view is the
   deliberate one: project mode on an `.rfa` (§3, → #502).
3. **`tools/rvt_job.py::structural_gate_from_manipulated` keeps
   `framing_errors`** — conditionally (`if v.get("framing_errors"):
   keep["framing_errors"] = …`), matching the verify dict's present-only-when-
   earned key, so a healthy job's manifest gains no `null` field (0-line diff)
   and a damaged one's `gates.structural.report` names the partition and the
   reason next to `walker_errors`, in the ONE `--json` document and the
   identical manifest on disk. Nothing else in the file touched (#495's writer
   lines, the printed == on-disk contract intact — the new door test re-asserts it).
4. **Tests** — `tests/test_partition_header_verdict.py` 11 → **15**: the three
   header-zeroed cases also assert `structural["report"]["framing_errors"] ==
   v["framing_errors"]`; the identity cases assert `list(structural["report"]) ==
   STRUCTURAL_REPORT_KEYS` (no key added on the bases, the edit, the verbatim
   twin); new `test_validator_words_the_framing_finding_through_the_walk`
   (L1 error at the zeroed primary `== walked.framing_error(p)`, a 10-byte twin
   → `"partition stream too short"` while `framing_error` has the struct text);
   new `test_job_json_structural_block_names_partition_and_reason` — drives
   `rvt_job.main(["edit", <2025 base>, "--ops", {set-level}, "-o", …, "--json",
   "--no-provenance"])` in-process with `scrub_identity` wrapped to zero the
   primary's header right after the door wrote the file (the writer-regression
   case): rc `EX_STRUCT` (3), ONE JSON on stdout == the manifest on disk (+
   `exit_code`), `gates.structural` FAIL / `walker_errors 1` /
   `framing_errors == {Partitions/20: "partition header/framing: unexpected
   Partitions header: v=0 cls=0x0"}`, `gates.validation` FAIL with the same
   words at the same `where`, output file delivered, `hard_gates_passed false`;
   new `test_job_json_healthy_structural_block_gains_no_key` (rc 0, PASS, report
   keys == the fixed list); new `test_validator_takes_the_family_shape_from_the_file`
   (family mode: `val.walked is <the given walk>` on the `.rfa` and on a base,
   set == `unframed_streams_of(names)`; explicit project mode on the `.rfa`: a
   view sharing `_raw`, set == `UNFRAMED_STREAMS`, the pinned `PartAtom` +
   `ProjectInformation` errors still reported). Against `main @ 4cc81dd`'s
   engine (file copied into a worktree): **5 failed / 10 passed** — the three
   `framing_errors`-in-report assertions, the door test and the shape test are
   red on main, green here; the wording test passes on both (identity pin).

### 2. Evidence

**Identity probe, exactly as #458's** (`scratchpad/probe/`: fixtures written
ONCE by `main @ 4cc81dd`'s engine — the three pinned bases copied, a `set-level`
edit of the 2025 base, a verbatim twin, #460's smash set (primary 64 B,
`Global/Latest`, `Contents`, `Global/ElemTable`), #458's header cases (primary /
twin / both zeroed, lost ElemTable on the twin file), a memberless `Global/Orphan`,
a 10-byte twin, a 64 KiB truncation, and the tracked eval-kit `.rfa`; judged by
main (worktree) and by this head in separate `-I` interpreters: `verify_manipulated`
dict + `structural_gate_from_manipulated` + the validator report (−timings) +
`validation_gate` (−elapsed/report_json), independent AND shared walk, **plus the
CLI `tools/rvt_validate.py --json` report** (and `--family` / `--project` on the
`.rfa`); `json.tool --sort-keys | diff | grep -c '^[<>]'`):

| fixture | verdicts (main == head) | diff lines main→head |
|---|---|---|
| `G_ABPD` / `_2025` / `_2024`, the edit, the verbatim twin | structural PASS · validation PASS | **0 / 0 / 0 / 0 / 0** |
| primary smash, `Global/Latest`, `Contents`, `Global/ElemTable`, lost ElemTable on twin file, `Global/Orphan`, 64 KiB truncation | FAIL (Contents: structural PASS · validation FAIL, as before) | **0** each |
| `.rfa` — verify (indep + shared), validator project + family in-process, CLI default/`--family`/`--project` | PASS · family OK / project 3 errors | **0** |
| **primary header zeroed** | FAIL · FAIL (4 errors, report identical) | **6** = `structural.report.framing_errors {Partitions/20: …}` ×(independent, shared) — the intended one |
| **twin header zeroed** / **both zeroed** | FAIL · FAIL (2 / 8 errors, identical) | **6 / 8** = the same key (1 / 2 partitions) ×2 views |
| **10-byte twin** | FAIL · FAIL (validator: `partition stream too short`, identical) | **6** = `framing_errors {Partitions/21: "partition header/framing: unpack_from requires …"}` ×2 |

Every validator report — in-process and CLI, both modes — and every verify dict
is byte-identical main vs head on every fixture; the ONLY diff lines anywhere are
the `framing_errors` entries inside `structural.report` of the four framing-damaged
files. Sibling views built by a `validate_file(…, walked=walk_file(x))` (spy on
`WalkedFile.__init__(_shared=…)`), main → head: `.rfa` family mode 0 → 0, `.rfa`
project mode 1 → 1 (by request, §3), base project mode 0 → 0, base family mode
**1 → 0**.

**Through the door** — `test_job_json_structural_block_names_partition_and_reason`
above is the `rvt_job.py edit <copy damaged after a door-written edit> … --json`
drive: ONE JSON, `gates.structural.report = {…, "walker_errors": 1,
"framing_errors": {"Partitions/20": "partition header/framing: unexpected
Partitions header: v=0 cls=0x0"}}`, `gates.validation.top_findings` carrying the
same sentence, status `FAILED (structural, validation)`, the `.rvt` written and
named. A partition-less container still raises inside `_primary_partition`
(`max()` of an empty list) — not in #486's DONE → filed **#501**.

**Latency** (S-2026-08-09-g) and **gates**: see BRANCH STATE (measured on the
final head).

### 3. Findings

1. The default is the last duplicated fact. `validate_file(x.rfa)` with no flag
   is project mode by definition today, and that verdict (3 mode-mismatch errors)
   is a *pinned contract in famgen territory*: `famgen.skeleton.validate_family`
   computes its `project_mode` block with a bare `validate_file(path)`, and
   `test_famgen_skeleton.py:619` (`n_errors == 3`), `test_bare_family_validate.py`
   (`"PartAtom" in wheres`, `project_mode INVALID`) pin it. Both designs the
   issue sketched — the set unconditionally from the file (project mode on an
   `.rfa` → 1 error) or `family=None` inferred (→ 0 errors) — move that contract
   and need the famgen call to say `family=False`; `src/rvt/famgen/**` was NO-GO
   this wave, so #486 lands the part that changes no verdict anywhere and the
   default goes to **#502** with the exact call sites named.
2. Once `framing_error` is the validator's wording, the `try/except` around
   `walked.walker()` in `_layer_structure` is dead by construction (the walker is
   cached — the same object or the same exception every call); `_walkers()` in the
   consistency layer keeps its own `partition walker: …` wording for the L2
   re-walk of a file whose every partition failed L1 (visible in the zeroed
   primary's report on main and head alike) — a second sentence for a second
   layer, left alone (byte identity; outside `_layer_structure`).

### 4. Open questions / follow-ups

* **#501** — `verify_manipulated` on a partition-less file: FAIL verdict, not
  `ValueError: max() arg is an empty sequence` (`_primary_partition`).
* **#502** — `family=None` default inferred from the file; `validate_family`'s raw
  comparison and the three pins say `family=False`; removes the last sibling view.
* Not filed (no caller, no ask): folding the `< 18 bytes` pre-check into
  `WalkedFile.framing_error` so the stub-partition case reads the same sentence in
  both gates (would change the self-check's text for that case only); and the L2
  `_walkers()` re-walk keeping its own `partition walker: …` sentence when every
  partition failed L1 (a second layer's second sentence, byte identity this round).
* `/simplify` (reuse / simplification / efficiency / altitude, four reviewers) →
  applied: `Validator.unframed_streams` dropped as shadow state — `_open` computes
  the mode's shape once as a local and the given walk / the lazily built
  `WalkedFile` carries it (`self.walked.unframed` is the one reader; the family arm
  passes `None` = the file's own shape), one `if/else` instead of two; `w =
  self.part_walkers[pname] = walked.walker(pname)`; `if "framing_errors" in v:`
  states the presence contract literally; tests: `monkeypatch.setattr` instead of
  hand-rolled restore, the dead third return value dropped, `_opened_validator`
  named for what it returns, one `_assert_healthy_shape` helper for the four
  identity pins, structure-only validations pass `layers=("structure",)` (−0.4 s).
  Skipped, with reason: hoisting the "stdout JSON == manifest on disk" check into
  `tests/conftest.py` for `test_frontdoor_json_strict` / `test_stagelog` to share
  (both files are other engineers' this wave — eng #488 / NO-GO list); dropping the
  healthy `--json` door test (~1 s; it is DONE 3's stated evidence).

### BRANCH STATE (eng #486)

* Branch `cam/486-validator-file-shape` from `main @ 4cc81dd`; PR closes #486;
  follow-ups filed: **#501** (partition-less file → verdict), **#502** (`family=None`
  inferred default; famgen's raw comparison says `family=False`).
* Files written: `src/rvt/validate.py` (`Validator.__init__`, `_open`,
  `_layer_structure`'s partition loop + its gzip loop's one read of
  `walked.unframed` — nothing else: `WalkedFile`, #429/#447's plan path,
  `crc_failures`, #466's ref_sink hoist, `validate_file`, the CLI untouched),
  `tools/rvt_job.py` (`structural_gate_from_manipulated`'s keep lines only; #495's
  writer lines untouched), `tests/test_partition_header_verdict.py` (11 → 15 tests;
  already in the shard via `tests/ci_shard.d/458-partition-header-verdict.txt`, no
  new drop-in needed), this record section. Generated mirrors re-synced by
  `tools/sync_plugin.py`: `plugin/lib/src/rvt/validate.py`, `plugin/lib/tools/rvt_job.py`,
  `plugin/skills/{tekton-author,tekton-edit,tekton-native}/scripts/rvt_job.py`.
* Not touched: `src/rvt/versions/**`, `src/rvt/manipulate.py`, `src/rvt/famgen/**`,
  `tools/frontdoor.py`, `tools/rvt_edit.py`, `tests/conftest.py`, any hot file, any
  NO-GO file of this wave.
* Shipped vs staged: everything ships with the PR; nothing for the viewer (no
  written byte changes — the three `rvt_edit.py set-level` outputs and the
  `rvt_job` / front-door edit outputs validate 0 errors exactly as on main).
* Gates on the final head (post-`/simplify`): `tests/test_partition_header_verdict.py`
  **15 passed** (4.6 s; against `main @ 4cc81dd`'s engine 5 failed / 10 passed);
  neighbours + plugin tests (`test_gates_shared_walk test_manipulate
  test_verify_manipulated_release test_edit_own_release test_validate_release
  test_ecc_final_block test_validate_footer_blob test_bare_family_validate
  test_records32 test_job test_go_edit test_modify_family_carrier
  test_manipulate_import_context test_famgen_skeleton test_rvt_analyze
  test_plugin_sync test_bootstrap test_coldstart test_surface_perf`) → **262 passed,
  23 skipped, 1 xfailed, 0 failed** (43 s); whole merged CI shard (`python3
  tools/dev/shard_list.py --print`, `RVT_SKIP_LARGE=1 … -q -p no:cacheprovider`) →
  **1738 passed, 139 skipped, 3 xfailed, 0 failed in 325 s** on the pre-simplify head
  and **1738 passed, 139 skipped, 3 xfailed, 0 failed in 319 s** again on the final head; `tools/sync_plugin.py` run → `--check`: *plugin in
  sync with source (deny-audit clean, identity scan == allowlist, assets verified)*;
  `plugin/scripts/validate_plugin.py` PASS; `tools/dev/check_portable_paths.py` ok
  (2925). Identity probe re-run on the final head: 0 diff lines on every healthy /
  smash / `.rfa` fixture and view, the four framing-damaged fixtures differing ONLY by
  `structural.report.framing_errors`. `/verify` on the final head: validator row —
  three bases `OK errors=0` (rc 0), 64 KiB truncation FAIL 11, header-zeroed primary
  / twin / 10-byte twin FAIL 4 / 2 / 2, partition-less FAIL 1, non-CFB FAIL 1 (rc 1
  each, no traceback anywhere), the eval-kit `.rfa` OK 0 (auto family) / FAIL 3
  (`--project`, the pinned raw comparison); `rvt_edit.py <base> set-level --id
  1351691 --elevation-ft 5 --json` on all three bases → `ok=True`, structural PASS
  (walker_errors=0) | validation PASS (0 errors), "Revit N in, Revit N out", stderr
  0 B; `rvt_job.py edit <2025 base> --ops {set-level} --json` → rc 0, stderr 0 B, ONE
  JSON == manifest on disk, `PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)`,
  structural PASS (no `framing_errors` key) / validation PASS 0, 598,016 B, output
  validates 0 errors; `frontdoor.py author --rvt <2025 base> --edit "set level
  1351691 elevation to 5 ft" --json` → rc 0, stderr 0 B, same status, job manifest
  structural PASS / validation PASS 0, output validates 0 errors. **Latency**
  (S-2026-08-09-g): bare unzip of `tekton-plugin.zip` built from `main @ 4cc81dd`
  ("before", 5,363,094 B) and from the final head ("after") into paths with a space,
  `env -i PATH=/usr/bin:/bin` + dead proxies, `/usr/bin/python3` 3.11.15, `go edit
  assets/genesis/G_ABPD_2025.rvt set-level --id 1351691 --elevation-ft 5 -o
  out/edited.rvt --json`, alternating 5+5 after a `.pyc`-compiling first pair (0.841
  / 0.868 s): every run rc 0, `go.ready true`, `tekton: READY …`, structural PASS |
  validation PASS (0 errors), stderr 0 B, structural report keys unchanged; wall
  before 0.514 0.508 0.510 0.505 0.512 s (median **0.510**) · after 0.507 0.507 0.508
  0.516 0.507 s (median **0.507**) — unchanged. The ops door from the same bare unzip
  (`go rvt_job.py edit … --ops ops.json --no-provenance --json`) → `go.ready true`,
  exit 0, structural PASS / validation PASS, stderr 0 B.
* Probe artefacts (scratchpad, not committed): `probe/{make_fx,judge}.py`,
  `probe/fx/*` (17 fixtures written by main's engine), `probe/{main,head}/*.json`,
  `probe/nopart.rvt`, `bench.sh`, `before.zip` / `after.zip`, `shard.log` / `shard2.log`.

## eng #501 — 2026-08-10 — a file with NO `Partitions/<N>` stream is a FAIL verdict of the self-check (0 walker errors, the absence named where and as the validator names it), never `max()` of an empty sequence

Stream: `eng501` (engineer session under the tech-lead session; branch
`cam/501-partitionless-verdict` from `main @ cd2d5a2`, i.e. after #508 landed
eng #486's validator/`rvt_job` halves). Closes #501; Refs #486, #458, #430. No
written byte changes and no verdict changes on any file that has a partition:
the one input shape that still raised before any verdict logic ran now gets the
verdict every other damaged shape gets.

### 1. What was built

1. **`verify_manipulated` judges a partition-less file without asking
   `_primary_partition`.** `parts = walked.partition_streams()` comes first; with
   partitions the primary is chosen exactly as before, without any the primary's
   *name* is the validator's placeholder `where` and the absence goes into the
   same conditional dict #458 introduced: `framing_errors == {"Partitions/<N>":
   "no Partitions/<N> stream"}` — the `where` and the message of the validator's
   L1 finding on such a file (`Validator._layer_structure`:
   `rep.error(L_STRUCTURE, "Partitions/<N>", "no Partitions/<N> stream")`), held
   as two module constants `NO_PARTITION_WHERE` / `NO_PARTITION_WHY` next to
   `_primary_partition`. Nothing is walked, so `walker_errors` stays **0** (the
   count keeps meaning "errors met while walking a partition"; the DONE asked for
   0); `header_count` is not read (there is no stream header) and stays `None`
   with every block-dependent fact (`isize_identity_mismatches`, `sentinel_last`,
   `stamps_ok`, `unit0_ids_equal_elemtable`); `edited {}`; CRC / ECC / ElemTable
   facts are computed as on any file (the ElemTable still parses: `elemtable_count`
   is an int, so `elemtable_count != header_count`; and `stamps_ok None` fails the
   gate even when the ElemTable is lost too and both counts are `None`). The
   ECC check's `for name in (pname, "Global/ElemTable"): if name in walked.names`
   and the block branch's `if pname not in framing` needed no touch — the
   placeholder is in `framing` and not in `names`. **Decision (DONE 2): the reason
   rides the existing conditional `framing_errors` key**, not a new key and not
   only the `None`s — because that key is the one `tools/rvt_job.py::
   structural_gate_from_manipulated` already forwards into the manifest's
   `gates.structural.report` (#486), so the ONE `--json` document names the reason
   with no change outside this territory, and because keying it at the validator's
   own `where` keeps #486's door property true for this shape too
   (`structural.report.framing_errors[w]` ∈ `validation.top_findings` at `w`). The
   two strings agree with `validate.py:979` by convention, pinned by the tests
   (making it one string by construction is a two-line `validate.py` touch —
   outside territory, §4).
2. **`_primary_partition` raises `ManipulationError("no Partitions/<N> stream")`
   on an empty partition list** instead of `ValueError: max() arg is an empty
   sequence` — the writers (`commit_plans`, `mep.electrical_data`, `records32`)
   still refuse a source with no host partition (there is nothing to edit), now in
   the module's own exception type with the validator's words; unreachable from
   the doors (the loader refuses first) and from `verify_manipulated` (never
   called partition-less). Two lines; the dach two-partition logic untouched.
3. **Tests** — `tests/test_partition_header_verdict.py` 15 → **18** (`_rewrite`
   gains `drop=`): `test_partitionless_file_is_a_fail_verdict` (the set-level edit
   rewritten without its partition entry: `_primary_partition` on it raises the
   named `ManipulationError`; `_judged` — independent AND shared walk, equal — no
   exception, structural FAIL, `walker_errors 0`, `framing_errors ==
   {NO_PARTITION_WHERE: NO_PARTITION_WHY}`, `header_count None`, the four block
   facts `None`, `edited {}`, crc/ecc 0, `list(v)[:14] == VERIFY_KEYS` (no
   always-present key), the validator FAILs with exactly `[NO_PARTITION_WHY]` at
   `NO_PARTITION_WHERE`, the structural report carries the same dict);
   `test_partitionless_file_without_elemtable_still_fails` (partition AND
   `Global/ElemTable` dropped: both counts `None` and equal, verdict still FAIL);
   `test_job_json_partitionless_output_is_delivered_and_labelled` — `rvt_job.main
   (["edit", <2025 base>, "--ops", {set-level}, "-o", …, "--json",
   "--no-provenance"])` in-process with `scrub_identity` wrapped to drop the
   partition right after the door wrote the file: rc `EX_STRUCT` (3), ONE JSON ==
   the manifest on disk (+ `exit_code`), `gates.structural` FAIL / `walker_errors
   0` / `framing_errors == {…}` / `header_count None`, `gates.validation` FAIL with
   `"no Partitions/<N> stream"` at `"Partitions/<N>"`, the `.rvt` delivered and
   named, `hard_gates_passed false`. Against `main @ cd2d5a2`'s engine (test file
   copied into a worktree, the two constants inlined): **3 failed / 15 passed** —
   the two verdict tests die in `_primary_partition` (`ValueError: max() arg is an
   empty sequence`, `manipulate.py:1497`), the door test gets rc 1 instead of 3.

### 2. Evidence

**Identity probe, exactly as #486's** (`scratchpad/probe/`: 17 fixtures written
ONCE by `main @ cd2d5a2`'s engine — the three pinned bases copied, a `set-level`
edit of the 2025 base, a verbatim twin, the smash set (primary 64 B @4096,
`Global/Latest`, `Contents`, `Global/ElemTable`), header-zeroed primary / twin /
both, lost ElemTable on the twin file, a memberless `Global/Orphan`, a 10-byte
twin, a 64 KiB truncation, the tracked eval-kit `.rfa` — plus the NEW 18th, the
edit rewritten without its `Partitions/20` entry; judged by main (worktree) and by
this head in separate `-I` interpreters: `verify_manipulated` dict +
`structural_gate_from_manipulated` + the validator report (−timings), independent
AND shared walk (+ family mode on the `.rfa`); `json.tool --sort-keys | diff |
grep -c '^[<>]'`):

| fixture | verdicts (main == head) | diff lines main→head |
|---|---|---|
| `G_ABPD` / `_2025` / `_2024`, the edit, the verbatim twin | structural PASS · validator OK | **0** each |
| primary smash / `Global/Latest` / `Contents` / `Global/ElemTable` / lost ElemTable on twin file / `Global/Orphan` / 64 KiB truncation | FAIL · FAIL 6 / 2 / (PASS · FAIL 1) / 3 / 3 / 1 / 11 | **0** each |
| header-zeroed primary / twin / both, 10-byte twin | FAIL · FAIL 4 / 2 / 8 / 2, `framing_errors` naming the partition(s) | **0** each |
| `.rfa` (verify indep + shared, validator project + family) | PASS · project FAIL 3 / family OK | **0** |
| **NEW: partition-less edit** | main: **`ValueError: max() arg is an empty sequence`** (verify, both views) · validator FAIL 1; head: structural **FAIL** · validator FAIL 1 (report byte-identical to main's) | 127 = the traceback replaced by the verdict dict ×2 views + the structural gate |

Head's dict on the new fixture (independent == shared): `crc_failures 0,
ecc_mismatches 0, walker_errors 0, isize_identity_mismatches None, elemtable_count
3316, header_count None, sentinel_last None, stamps_ok None, deleted_* empty,
edited {}, elemtable_ids_sorted True, unit0_ids_equal_elemtable None, fallbacks [],
framing_errors {"Partitions/<N>": "no Partitions/<N> stream"}` → gate FAIL; the
validator's only error: `structure  Partitions/<N>  no Partitions/<N> stream`.

**Through the doors.** `tools/rvt_edit.py::_gates` verbatim (`walk_file` →
`verify_manipulated` → structural gate → `validation_gate` → the line) on the
partition-less fixture: main → `RAISED ValueError max() arg is an empty sequence`;
head → `structural FAIL (crc_failures=0, ecc_mismatches=0, walker_errors=0,
stamps_ok=None) | validation FAIL (1 errors, 0 warnings)`, `hard_gates_passed
False`, `framing_errors` as above. `rvt_job.py edit <2025 base> --ops {set-level}
-o … --json --no-provenance` with the written file losing its partition right
after the write (`scrub_identity` wrapped, `probe/door.py`): main → rc **1**,
stderr `[rvt_job] FAILED (edit: ValueError: max() arg is an empty sequence)`, ONE
JSON with `status "FAILED (edit: …)"`, no `gates`, `hard_gates_passed null`, no
`.validation.json` (the 368,640 B file was on disk but the manifest is the 422 B
stub); head → rc **3** (`EX_STRUCT`), stderr 1 line (`RC 3` from the probe itself
— the door wrote nothing there), ONE JSON == manifest (5,046 B): `status "FAILED
(structural, validation)"`, `gates.structural.report` as above,
`gates.validation` FAIL 1 with the same sentence at the same where, `output
{path, bytes 368640, sha256, log}` — delivered and labelled, no traceback on
either tree.

**Latency** (S-2026-08-09-g) and **gates**: see BRANCH STATE (measured on the
final head).

### 3. Findings

1. The placeholder-in-`framing` shape costs one `if parts:` at two sites and
   nothing else: every later read of the primary in `verify_manipulated` was
   already guarded by `name in walked.names` or `pname not in framing` since #458,
   which is why the 17-fixture identity holds with no special-casing downstream.
2. `walker_errors 0` with a `framing_errors` entry is new (#458's entries each
   count one walker error). It is deliberate — nothing was walked — and harmless
   to the gate (`stamps_ok None` and `header_count None` each fail it alone); the
   docstring now says so. A consumer that wants "how many partitions are unusable"
   should read `len(framing_errors)`, not `walker_errors`.

### 4. Open questions / follow-ups

* Not filed (no caller, no ask; would touch `src/rvt/validate.py`, outside this
  territory): let `Validator._layer_structure` take its `"Partitions/<N>"` /
  `"no Partitions/<N> stream"` literals from `rvt.manipulate.NO_PARTITION_*` (or
  both from one place in `validate.py`) so the two gates share the sentence by
  construction, as #486 did for `framing_error`. Today: equal by convention,
  pinned by `test_partitionless_file_is_a_fail_verdict` and the door test.
* The edit doors still refuse a partition-less **input** at load with one FAILED
  line (rc 1, one JSON, nothing written) — graceful, input-side, unchanged, same
  as #458 noted for header-damaged inputs.

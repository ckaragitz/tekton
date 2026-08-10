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

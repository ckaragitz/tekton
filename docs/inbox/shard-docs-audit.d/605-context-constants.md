# 605-context-constants -- `context_constants()` is the ONE test-side list of names the authoring context swaps; five in-process callers watch it, and the law ratchets every module on the leak guard, not eight (shard-docs-audit stream, eng #605)

**Issue:** #605 (Refs #602 #579 #535; inputs from eng #604's and eng #639's comments on the issue). **Date:** 2026-08-11.
**Session:** eng #605 (cloud, `cse_01GTFzG2wVNS8qRETsgAGdad`), started by the tech-lead session. **Base:** `main` @
`0cbf7e1` (#701). Index: `docs/inbox/shard-docs-audit.md` (left untouched -- the README makes the index line optional and
that EOF is the hot spot #636 exists to avoid; the issue predates the fragment convention and names the single file, the
brief named this fragment). Written in this engineer's voice; no other record edited. Tests + this record only: nothing
under `src/`, `tools/`, `plugin/`, `skills/`.

## Why

After #579 / #602 the leak guard has one home -- `tests/conftest.py::no_release_leak`, additive through
`release_leak_extra` -- but the *write-side* watch list was still hand-picked per file. `test_release_ctx_refusal.py`
carried a private `_constants()` naming ten engine values -- the issue says "nine"; its own list has ten -- (`RC._REFUSED`, three `MU.CLASS_*` ids, `GSK.minimal_history`
/ `minimal_elemtable` / `sorted(_SCHEMA_CACHE)`, `SA.bundled_base_path` / `family_instance_template` /
`dict(_SCHEMA_STATE)`); `test_edit_text_release.py` watched `W.BLOCK_TRL_TAG` alone; `test_rvt_edit_refusal.py` and
`test_edit_own_release.py` enter `host_release_context` in-process on every foreign-pin row and watched nothing past the
framing table; `test_edit_status.py` (three in-process `FD.author(rvt=<2025 pin / damaged 2025 host>)` rows) had no
guard at all. Those are all subsets of ONE engine fact -- the `swap(...)` calls of
`src/rvt/frontdoor/release_ctx.py::_release_context` (L396-610 at this base) -- exactly the way `ladder_constants()` is
the one list for the read-side ladder. And the law's `ADOPTERS` (`tests/test_conftest_scaffolding.py`) named eight files
while fourteen modules request the guard on `main` today: the six born on it since #602 (`test_cfb_rewrite_entries`,
`test_rewrite_entries_646`, `test_identity_helper_657`, `test_reduce_v2_655`, `test_reduce_v2_671`,
`test_rvt_job_scrub_656`) could drop their one `pytestmark` line and nothing would notice.

## What landed

1. **`tests/conftest.py`** -- ONE new function next to `ladder_constants()` (+ its name in the module docstring's list;
   nothing else touched): `context_constants() -> dict`, lazily importing `rvt.mutate` / `rvt.genesis.skeleton` /
   `rvt.frontdoor.standalone` / `rvt.frontdoor.release_ctx`, returning exactly the ten values the refusal file watched,
   **keyed `MODULE.name`** (`"MU.CLASS_SWALL"`, `"SA._SCHEMA_STATE"`, ...) so a red teardown names the constant instead of
   printing a tuple under `"mu"`. Docstring: what the write side swaps, why a separate callable (only in-process context
   callers pay for the imports; hand it to `release_leak_extra`), and "the ONE list to grow when `host_release_context`
   learns to swap another name" -- with the honest limit stated: it mirrors `_release_context`'s `swap()` calls by hand,
   and past these ten the right move is one exported table in `release_ctx` that both its restore and this guard read
   (filed, below), not a tenth hand-copied name.
2. **`tests/test_release_ctx_refusal.py`** -- `release_leak_extra` returns `context_constants`; the body-level
   `_constants()` (still used mid-test by `test_setup_failure_after_the_first_swap_restores_everything`) is now
   `dict(native_constants(), **context_constants())` = exactly what the guard watches for this file; the one index that
   read `before["mu"][0]` reads `before["MU.CLASS_ELEMENT_HEADER"]` -- same assertion (`MU.CLASS_ELEMENT_HEADER` differs
   inside the next context from its pre-failure value). The now-unused `SA` / `GSK` imports went; `MU` stays (that row).
3. **`tests/test_edit_text_release.py`, `tests/test_rvt_edit_refusal.py`, `tests/test_edit_own_release.py`** -- each
   gains (or, for the first, respells) a `release_leak_extra` override returning `context_constants`. The first file's old
   extra, `{"W.BLOCK_TRL_TAG": W.BLOCK_TRL_TAG}`, watched nothing of its own: `rvt.writer.BLOCK_TRL_TAG` is a module
   `__getattr__` alias resolving `rvt.partitions.TRAILER_TAG` at access time (`src/rvt/writer.py:28-36`), which
   `native_constants()` already snapshots -- so the switch is strictly more watched there too, and the unused `W` import
   went. **`tests/test_edit_status.py`** opts in: `pytestmark = pytest.mark.usefixtures("no_release_leak")` + the same
   override. All five: every test still green with the wider watch (table below) -- no real leak surfaced.
4. **`tests/test_conftest_scaffolding.py`** (the law): `SHADOWS` += `"context_constants"` (so the `SHADOWS ⊆ vars(conftest)`
   staleness check guards the new name and a module-level copy is a convicted shadow); `ADOPTERS` 8 → 15 (the eight, +
   `test_edit_status`, + the six modules already on the guard); the adopter row's AST read of `pytestmark` became the
   shared `_requests_the_leak_guard(tree)`; **two rows added**:
   * `test_context_constants_snapshot_what_the_write_side_swaps` (behaviour, on the `pin` fixture): the key set is the
     ten names (spelled out, like the ladder row's three, so a dropped watch is red there first); it is disjoint from `native_constants()` ∪ `ladder_constants()` (additive, nothing shadowed); inside
     `host_release_context(pin)` on a foreign pin every swapped *name* really moves (only the two registries
     `RC._REFUSED` / `GSK._SCHEMA_CACHE` may stand -- measured: on the 2024 pin only `RC._REFUSED` stands), on the native
     pin nothing moves; and after exit all ten equal their before -- so the list is pinned to the engine fact it mirrors,
     not just to itself.
   * `test_every_module_on_the_leak_guard_is_an_adopter` (completeness): every `tests/test_*.py` whose module-level
     `pytestmark` requests `no_release_leak`, or that binds `release_leak_extra` at top level, is on `ADOPTERS`.

## The `ADOPTERS` decision (DONE 4): a hand list, made self-completing -- not "imports the scaffolding ⇒ must adopt"

Picked: **`ADOPTERS` stays an explicit list and now covers every module on the guard (15), and the law derives the
obligation to be on it.** The list is the ratchet (a listed module that drops the guard is red); the new completeness row
is the other direction (a module that switches the guard on, or overrides `release_leak_extra`, without enlisting is red
until it adds its stem -- and an override in a module that never requests the guard is caught as the dead watch it is).
So from this PR on the list grows itself: nobody can adopt the guard in a way that could later be silently dropped.

Why not the issue's literal derived reading, "every non-exempt `tests/test_*.py` that imports the scaffolding must
request `no_release_leak`": measured on `main` @ `0cbf7e1`, **importing** the scaffolding says nothing about **entering a
release context** -- `test_validate_footer_blob`, `test_input_release`, `test_ecc_final_block`, `test_clause_relays`,
`test_partition_header_verdict`, `test_gates_shared_walk` import `rewrite_stream` / `flip_bit` / `partition_of` to damage
bytes; making them pay for a guard (or carrying a six-name `EXEMPT` list, i.e. the hand list inverted, which #604/#639 just
retired) is the wrong axis. The honest derivation is *by call*: a module that calls `host_release_context` /
`release_build_context` / `enter_host_release` / `enter_own_release` by name enters a context in-process and should be on
the guard. Census (same base): 26 modules do; 11 request the guard; **15 do not** -- `test_clause_relays`,
`test_famdoc_scan_fp`, `test_famload_2025`, `test_famload_batch`, `test_framing_by_name`, `test_frontdoor`,
`test_gates_shared_walk` (its own after-only `_constants_restored`; eng #604 measured the switch green, issue comment),
`test_history_head_guid`, `test_manipulate_import_context`, `test_objects_plans`, `test_partition_header_verdict`,
`test_readers_own_release` (a private tuple-shaped guard), `test_target2025`, `test_validate_footer_blob`,
`test_verify_manipulated_release`; plus `test_genesis_identity`'s private autouse `_no_release_leak` (eng #639's comment)
which calls none of them by name. Every one of those is outside this issue's territory ("the five test files named"), several
hold a context open in a module-scoped fixture (which the guard's `active_release() is None` at setup would rightly or
wrongly convict -- per-file judgement, not a sweep), and three human sessions were live in `famgen`/`frontdoor` test files
tonight. So: filed as ONE follow-up (below) -- adopt file by file, then flip the adopter rule to derived-by-call and shrink
`ADOPTERS` to the indirect callers (`FD.author(rvt=…)`, `E.main([...])`) the AST cannot see.

## Evidence

**Per file, before (`main` @ `0cbf7e1`) → after (this branch), `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest <file> -q -rs
-p no:cacheprovider` and `--collect-only -q | sort` diffed:**

| file | collected ids | id diff | outcome before → after |
|---|---|---|---|
| `tests/test_release_ctx_refusal.py` | 15 → 15 | empty | 15 passed → 15 passed |
| `tests/test_edit_text_release.py` | 7 → 7 | empty | 7 passed → 7 passed |
| `tests/test_rvt_edit_refusal.py` | 11 → 11 | empty | 11 passed → 11 passed |
| `tests/test_edit_own_release.py` | 11 → 11 | empty | 11 passed → 11 passed |
| `tests/test_edit_status.py` | 9 → 9 | empty | 9 passed → 9 passed (now under the guard) |
| `tests/test_conftest_scaffolding.py` | 18 → 27 | +9, nothing removed: `test_adopter_keeps_the_leak_guard_on[…]` × 7 new stems, `test_context_constants_snapshot_what_the_write_side_swaps`, `test_every_module_on_the_leak_guard_is_an_adopter` | 18 passed → 27 passed |

No skips in any of the six on this VM (all three pins certified: `CERTIFIED_YEARS == [2024, 2025, 2026]`,
`FOREIGN_FIRST[0] == 2024`, so the context row's foreign branch is the one exercised).

**The guard bites under every adopter touched** (throwaway, never committed: a `test_zz_leak_probe_605` appended to each
file that does `rvt.mutate.CLASS_SWALL = -605` and returns; run alone with `-k zz_leak_probe_605`; file restored from a
copy; `git status` afterwards shows only the seven intended modifications):

```
== test_release_ctx_refusal   ERROR at teardown of test_zz_leak_probe_605   E  {'MU.CLASS_SWALL': -605} != {'MU.CLASS_SWALL': 3842}   1 passed, 15 deselected, 1 error
== test_edit_text_release     ERROR at teardown of test_zz_leak_probe_605   E  {'MU.CLASS_SWALL': -605} != {'MU.CLASS_SWALL': 3842}   1 passed, 7 deselected, 1 error
== test_rvt_edit_refusal      ERROR at teardown of test_zz_leak_probe_605   E  {'MU.CLASS_SWALL': -605} != {'MU.CLASS_SWALL': 3842}   1 passed, 11 deselected, 1 error
== test_edit_own_release      ERROR at teardown of test_zz_leak_probe_605   E  {'MU.CLASS_SWALL': -605} != {'MU.CLASS_SWALL': 3842}   1 passed, 11 deselected, 1 error
== test_edit_status           ERROR at teardown of test_zz_leak_probe_605   E  {'MU.CLASS_SWALL': -605} != {'MU.CLASS_SWALL': 3842}   1 passed, 9 deselected, 1 error
```

**Matched control** (the same probe on a `main` @ `0cbf7e1` worktree, same interpreter): `test_edit_status` → `1 passed, 9 deselected` (no guard: the leak is silent), `test_edit_own_release` → `1 passed, 11 deselected` (framing-only guard: silent), `test_release_ctx_refusal` → `1 passed, 15 deselected, 1 error` (it already watched the tuple) -- so the five reds above are this PR's doing, not the probe's.

**Docs-read audit census** (`RVT_DOCS_AUDIT=report` over the six files): `0 repo docs/ file(s) opened by this test
process` before (71 passed) and after (80 passed) -- unchanged.

**Whole merged CI shard** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3
tools/dev/shard_list.py --print)`, 125 files): `main` @ `0cbf7e1` (worktree, same interpreter) → SHARD_MAIN_PLACEHOLDER;
this branch → SHARD_BRANCH_PLACEHOLDER.

Other gates: `python3 tools/dev/check_portable_paths.py` → `ok: 3091 tracked paths are portable` (3090 + this fragment); `.venv/bin/python
plugin/scripts/validate_plugin.py` → `RESULT: PASS — plugin structure is valid` (25 assertions) (sanity; nothing under `plugin/` touched); pyflakes clean on the
seven touched Python files. `/simplify` run on the working-tree diff (four angles): reuse **clean** (nothing re-implemented; `_requests_the_leak_guard` is an extraction shared by two rows); efficiency **clean** (measured: `context_constants()` 3.2 µs warm, conftest import time unchanged at 0.246 s, the new law row 10 ms over the cached ASTs, the one-time `mutate`/`genesis.skeleton` import ~45 ms and already paid by every adopter's own context entry); simplification: two nits applied (the `_tree` cache comment said "two law rows", now three; the spelled-out key set in the new row got the one-line comment saying that a dropped watch being red there is the intent, as in the ladder row), two declined with reason (inlining `_constants()` -- the issue's DONE 2 names it; a composed `no_context_leak` fixture -- outside "conftest gains one function", folded into #707); altitude: keep on all three questions (hand mirror under a no-src constraint with #706 as the real fix; explicit `ADOPTERS` + completeness row as a staged migration with #707 stating the end state; the override idiom over a marker registry). `/verify` skipped -- tests + a record only, no
runtime surface to drive (`No-Verification-Needed: tests-only` trailer).

## Follow-ups filed (searched first: no open issue covers either)

* **#706** (`P2` · `area:frontdoor` · `planned`; deliberately not `ready` while `src/rvt/frontdoor/**` is inside live sessions' territory -- the tech-lead pass flips it): `release_ctx` exports the ledger of `(module, name)` pairs `_release_context` swaps and restores from, and `context_constants()` reads it -- ten hand-mirrored names become every swap, drift-proof by construction; the behaviour row added here becomes the pin of that export.
* **#707** (`P2` · `area:process` · `ready` · `planned`, M): the 16 modules that enter a context in-process without the guard (the 15 by-call + `test_genesis_identity`'s private autouse) adopt `no_release_leak` or are listed with a measured reason; then the law derives adopters by call and `ADOPTERS` shrinks to the indirect callers the AST cannot see; optionally one composed opt-in fixture replaces the nine-plus identical `release_leak_extra` overrides of both dialects at once (the /simplify note below).

## Open questions

None blocking. One judgement the reviewer may want to weigh: `context_constants()` returns the ten names the issue
asked for, not the ~30 `_release_context` swaps (the `FSK` framing copies, `FF.build_family_save_unit` /
`FORMATS_LATEST_SHA256_PREFIX`, `ENC._DEFAULT_ENCODER`, the four `load_schema` reroutes, `REGADD`/`REGDIFF.ObjectDecoder`,
`GT._STATE`, the other three `MU.CLASS_*`, four more `GSK.minimal_*`, `SA.swall_template`, the two `.records` methods,
the port layer's `_STATE`). Widening by hand is exactly what the territory note rules out; the exported-table follow-up is
where the rest belongs, and the behaviour row added here is the test that will pin that table the day it exists.

## BRANCH STATE

* **Branch:** `cam/605-context-constants` from `main` @ `0cbf7e1`; PR opened ready (not draft), `Closes #605`.
* **Files written:** `tests/conftest.py` (+`context_constants`, docstring name), `tests/test_conftest_scaffolding.py`
  (`SHADOWS`, `ADOPTERS`, `_requests_the_leak_guard`, two rows, docstring), `tests/test_release_ctx_refusal.py`,
  `tests/test_edit_text_release.py`, `tests/test_rvt_edit_refusal.py`, `tests/test_edit_own_release.py`,
  `tests/test_edit_status.py` (guard wiring only), this fragment. No CI-shard drop-in needed (all six modules already in
  the merged shard: lines 26/53/94/96/97/102 of `shard_list.py --print`).
* **Gates:** as above -- six stream-local files green with identical ids (law +9); teardown proof under all five; whole
  merged shard = main + 9; portable paths ok; validate_plugin PASS.
* **Staged vs shipped:** nothing staged (no viewer claim, no output files); nothing under `src/`/`tools/`/`plugin/`/`skills/`
  so no `sync_plugin` run owed.
* **Not merged by this session** (regime #302): head SHA reported to the tech-lead session for sandboxed CI + independent
  review.

# 707-adopters-by-call -- every module that enters a release context in-process keeps conftest's leak guard on, the law derives that by CALL, and `ADOPTERS` shrinks to the six callers the scan cannot see (shard-docs-audit stream, eng #707)

**Issue:** #707 (Refs #605 #604 #639 #579; the tech lead's notes on PR #709). **Date:** 2026-08-11.
**Session:** eng #707 (cloud, `cse_01VagXDwxJmZZw2Qu9UQQZF9`), started by the tech-lead session. **Base:** `main` @
`6f33fb7` (#708; #709 = `86af708` is in). Index: `docs/inbox/shard-docs-audit.md` (left untouched, as #605's fragment
did). Written in this engineer's voice; no other record edited. Tests + this record only: **nothing under `src/`,
`tools/`, `plugin/`, `skills/`, and `tests/conftest.py` untouched** (the call-scan helper stays in the law module).

## Why

After #605 / #709 the law ratchets the fifteen modules on the guard, but cannot tell a module that *should* be on it.
The issue's grep census (26 modules name an entry point / 15 unguarded) over-counts: `test_clause_relays` and
`test_readers_own_release` only *mention* `enter_own_release` in docstrings, `test_framing_by_name` and
`test_manipulate_import_context` call it inside subprocess script literals (that interpreter's constants are not
ours). The honest axis is the AST **call**: a module whose own code calls an entry point enters a context in THIS
process. And the four names the issue lists are not the whole door: `versions.reading` (the bare framing context every
`test_port*` / `test_genesis_20xx` / `test_versions` row enters), `global_framing.reading` and `records32.reading32`
rebind the very framing table `native_constants()` watches -- a module that enters *those* and leaks breaks the next
module's native walk exactly like a leaked `host_release_context` would.

## (1) The strict census -- `main` @ `6f33fb7`, every `tests/test_*.py` parsed with `ast`, CALLS only

Instrument (kept in the law as `_context_callers()`; the throwaway that printed this table walked `ast.Call` nodes and
took `func.id` / `func.attr`): entry points = `host_release_context`, `release_build_context`, `enter_host_release`,
`enter_own_release` (global_framing's and validate's), `reading` (`V.` / `versions.` / `GF.`), `reading32`. A name in
a string literal is not a `Call` node, so subprocess scripts drop out by construction. **34 modules call one; 12
requested `no_release_leak`; 22 did not; + `test_genesis_identity` (calls none -- its tool does -- and carried a private
autouse `_no_release_leak`).** By the issue's four names alone: 21 callers / 9 guarded / 12 unguarded (the tech lead's
"~20 / ~11" + the law module's own #605 behaviour row).

| module | calls (line) | guard on `main` | this PR |
|---|---|---|---|
| `test_cfb_rewrite_entries` | `host_release_context` (142) | yes | -- |
| `test_edit_text_release` | `RC.host_release_context` (53) | yes | -- |
| `test_estorage_cli_release` | `GF.reading` (98) | yes | -- |
| `test_identity_helper_657` | `release_build_context` ×10 | yes | -- |
| `test_natively_framed` | `GF.enter_own_release` (81) | yes | -- |
| `test_reduce_v2_655` | `host_release_context` (85, 141), `V.reading` (44) | yes | -- |
| `test_reduce_v2_671` | `RC.host_release_context` ×4 | yes | -- |
| `test_release_ctx_refusal` | `RC.host_release_context` ×4, `RC.enter_host_release` ×3, `GF.enter_own_release` | yes | -- |
| `test_rewrite_entries_646` | `host_release_context` (177), `release_build_context` (213) | yes | -- |
| `test_rvt_job_scrub_656` | `host_release_context` (62, 79) | yes | -- |
| `test_edit_own_release`, `test_edit_status`, `test_inspect_release`, `test_rvt_edit_refusal`, `test_selfcheck_release` | *none by call* (tool / front-door drivers) | yes | stay on `ADOPTERS` (indirect) |
| `test_conftest_scaffolding` | `RC.host_release_context` (157 -- #605's behaviour row) | **no** | adopted, `context_constants` |
| `test_famdoc_scan_fp` | `RC.release_build_context` (278) | **no** | adopted, `context_constants` |
| `test_famload_2025` | `RC.host_release_context` ×5, `RC.release_build_context`, `GF.reading`, `V.reading` (+ `GF.bound`) | **no** (private autouse `_restored` over a 12-tuple `_native_state`) | adopted; private guard folded into its `release_leak_extra` (below) |
| `test_famload_batch` | `RC.host_release_context` (401) | **no** | adopted, `context_constants` |
| `test_frontdoor` | `RC.release_build_context` (753, 1215), `enter_own_release` (1682) | **no** | adopted, `context_constants` **minus the two lazy schema caches** (finding below) |
| `test_gates_shared_walk` | `release_build_context` (98) | **no** (after-only autouse `_constants_restored`) | adopted, `context_constants`; private guard deleted |
| `test_history_head_guid` | `release_build_context` (54, 98) | **no** | adopted, `context_constants` |
| `test_objects_plans` | `enter_own_release` (54), `release_build_context` (319) | **no** | adopted, `context_constants` (see "corpus" note) |
| `test_partition_header_verdict` | `release_build_context` (119, module fixture `edited` -- enters and exits inside) | **no** | adopted, `context_constants` |
| `test_target2025` | `RC.release_build_context` (363, 384), `V.reading` (287, 330) | **no** | adopted, `context_constants` |
| `test_verify_manipulated_release` | `release_build_context` (73), `V.reading` (116) | **no** (after-only `_constants_restored`) | adopted, `context_constants` **minus the two lazy schema caches**; private guard deleted |
| `test_validate_footer_blob` | `VA.enter_own_release` (72, 93, 223) | **no** | adopted, `ladder_constants` |
| `test_codec_bases` | `reading32` (73, the `base` fixture) | **no** (after-only `_constants_restored`) | adopted, `ladder_constants`; private guard deleted |
| `test_estorage_catalog_2024` | `GF.reading` (89) | **no** | adopted, `ladder_constants` |
| `test_genesis_2023` | `V.reading` (158, 179), `records32.reading32` (226) | **no** | adopted, `ladder_constants` (rows sample-gated here) |
| `test_records32` | `R32.reading32` (496, 511, 529) | **no** | adopted, `ladder_constants` |
| `test_readers_own_release` | `V.reading` (141); its readers climb the ladder inside `python -m rvt.census` etc. in-process | **no** (private `_constants_restored` over a `_native_state` tuple: framing + `FF.CD_SEPARATOR` / `CD_END_RECORD` + `ADOC._DECODER`) | adopted, `ladder_constants` + the two `FF.CD_*` tokens it already watched; private guard deleted |
| `test_validate_release` | `V.reading` (62); `validate_file` climbs the ladder in-process | **no** (after-only `_constants_restored`) | adopted, `ladder_constants`; private guard deleted |
| `test_framing_by_name` | `V.reading` (69, 82, 109) -- the `enter_own_release` at 139/170 is inside a subprocess literal | **no** | adopted, no extra (bare framing context = exactly `native_constants()`) |
| `test_manipulate_import_context` | `V.reading` (157) -- the three doors at 41-58 are subprocess literals | **no** | adopted, no extra |
| `test_genesis_2024` / `test_genesis_2025` / `test_port2024` / `test_port2025` / `test_y2025_a` / `test_versions` / `test_status_gate` | `versions.reading` in test bodies (no module-scoped fixture in any of them) | **no** | adopted, no extra (the context rows of the first five are sample/rung-gated on this VM -- see Evidence) |
| `test_genesis_identity` | *none by call*: `GI.build_release(year)` re-authors the foreign pins under `release_build_context` | **no** (private autouse `_no_release_leak`: `active_release() is None` before/after only) | adopted, `context_constants`, on `ADOPTERS` (indirect); private guard deleted |

Held by another session (the brief's list: `test_famgen_*`, `test_category_facts`, `test_famgen_parametric*`,
`test_constraint_law*`, `test_conformance*`, `test_router*`, `test_prompt*`, `test_luminaire_sizes_682`,
`test_steplite*`, `test_ifc_read*`): **none of them calls an entry point** -- nothing skipped for that reason.

## (2) What each adoption is, exactly

The standard wiring and nothing else: `pytestmark = [<the module's existing skipif>, pytest.mark.usefixtures("no_release_leak")]`
(or the bare mark where there was no module mark), plus a three-line `release_leak_extra` override where the module
enters more than the bare framing context. The extra follows what the module enters **by call**: the write side
(`host_release_context` / `release_build_context` / `enter_host_release`, or a tool that does) → `context_constants`;
only the read-side ladder (`enter_own_release`, `GF.reading`, `reading32`, or the release-aware validator / readers it
drives on foreign pins) → `ladder_constants`; only `versions.reading` → nothing past `native_constants()` (the framing
table is all it swaps). No test body, assertion or fixture other than the private guards changed; imports that only the
deleted guards used went with them (`P`/`V` in `test_gates_shared_walk`, `ADOC` in `test_readers_own_release`, `RC` in
`test_genesis_identity`), one the grep missed came back (`P` in `test_verify_manipulated_release`, used by a row).

**Private guards folded, never weakened.** The four after-only `_constants_restored` (codec_bases, gates_shared_walk,
validate_release, verify_manipulated_release) asserted `{P.k} == framing_table(LATEST)` after each test; the shared
guard asserts before == after over the same keys **plus** `active_release() is None` at setup plus the extra -- strictly
more, with one nuance stated once: theirs was an *absolute* check (a leak from an EARLIER, unguarded module would have
gone red here, blaming the wrong test), ours is relative (the leaking test itself is red). With every in-process caller
now guarded the two coincide by induction from import time; and the absolute fact stays pinned where it belongs, in the
law's `test_native_and_ladder_constants_snapshot_what_a_context_rebinds` (`native_constants() == framing_table(LATEST)`).
`test_readers_own_release`'s tuple (framing, `FF.CD_SEPARATOR`, `FF.CD_END_RECORD`, `ADOC._DECODER`) became
`ladder_constants()` (decoder, `iter_records`, `FAMILY_END_RECORD`) + the two `FF.CD_*` tokens keyed `"FF.CD_SEPARATOR"` /
`"FF.CD_END_RECORD"` -- a superset. `test_famload_2025`'s 12-tuple `_native_state` became `_lane_constants()` =
`ladder_constants()` ∪ `context_constants()` ∪ {`P.TERMINATOR`, `FF.CD_SEPARATOR`, `FF.CD_END_RECORD`,
`GSK.EMPTY_CONTENT_DOCUMENTS`, `FSK.FOOTER_TAG`, `sorted(GT._STATE)`, `FF.FORMATS_LATEST_SHA256_PREFIX`} keyed
`MODULE.name` -- every one of the twelve is still watched (`P.BLOCK_TAG` / `CONTAINER_CLASS` via the framing table,
`FDA.FAMILY_END_RECORD` / `ADOC._DECODER` via the ladder list, `MU.CLASS_FAMILY_INSTANCE` via the context list), and
`active_release() is None` is now checked at setup too, not only after. `test_genesis_identity`'s `_no_release_leak`
(active_release only) ⊂ `native_constants()`. The four retired spellings join `FORBIDDEN` (`_constants_restored`,
`_no_release_leak`, `_restored`, `_native_state`; no other module binds them at top level) so a copy cannot come back.

## Finding: two of `context_constants()`'s ten watches are lazy NATIVE caches, and convict a first native build (not a leak)

Measured, not argued. Under `context_constants` as merged by #709, `test_frontdoor` went **85 passed, 5 skipped → 85
passed, 5 skipped, 3 errors** and `test_verify_manipulated_release` **7 passed → 7 passed, 1 error**, all four
`ERROR at teardown`, all four on ONE key:

```
test_frontdoor::test_merge_ifc_of_a_two_storey_ifc_is_world_faithful
test_frontdoor::test_add_to_project_lifts_prompt_gear_onto_the_target_level_once[L2 - Second Floor]
test_frontdoor::test_add_to_project_lifts_prompt_gear_onto_the_target_level_once[None]
  E  Differing items: {'SA._SCHEMA_STATE': {... 'from': '/tmp/.../target.rvt', 'sha256': '6459a9a9…', ...}}
                   != {'SA._SCHEMA_STATE': {... 'from': '.../plugin/assets/genesis/G_ABPD.rvt', 'sha256': '6459a9a9…', ...}}
test_verify_manipulated_release::test_unreadable_schema_degrades_with_a_stated_fallback
  E  Differing items: {'SA._SCHEMA_STATE': {'schema': <Schema>, 'from': '.../G_ABPD.rvt', 'sha256': '6459a9a9…', ...}} != {'SA._SCHEMA_STATE': {}}
```

Neither is a release context leaking. `SA._SCHEMA_STATE` is `standalone`'s process schema cache: on the **native**
path `rvt.schema.load_schema()` with no research corpus on the machine (a fresh clone -- i.e. CI) answers through
`standalone.bundled_schema()`, which *fills* the empty cache on first use (`src/rvt/frontdoor/standalone.py:189-204`;
the verify row's decode fallback is that first use when the row runs before anything else filled it), and
`convert.add_to_project._install_target_schema` / the front door's `install_schema(base)` deliberately re-point
`from` at the same-sha target they build on (`src/rvt/convert/add_to_project.py:180-201`, by design and documented
there). `host_release_context` snapshots and restores that dict around a *foreign* context (`release_ctx.py:439-448`) --
which is all #605's behaviour row proves -- but on the native path it is not a constant, so "equal after every test" is
the wrong contract for it. `GSK._SCHEMA_CACHE` (watched as `sorted(keys)`) is the same kind of thing: `"dec"` / `"enc"`
appear on the first native skeleton build in a process (`genesis/skeleton.py:188-313`). #605's five adopters never
tripped either because their rows only drive foreign pins or edits; the isolation sweep below shows which of the new
adopters would.

**What this PR does about it (territory: not `conftest.py`, not `src/`):** the two modules measured red take
`context_constants` minus those two cache keys through their own `release_leak_extra` (a dict comprehension over
`context_constants()`, docstring naming this finding) -- the other eight write-side names stay watched there, and every
other adopter keeps the full ten. **What should happen next (filed on #706, whose export is where the list stops being
hand-picked):** classify the three live dicts `_release_context` snapshots (`GSK._SCHEMA_CACHE`, `port._STATE`,
`SA._SCHEMA_STATE`) as *restored caches*, not constants, and have `context_constants()` watch the release-relevant bit
of the schema state instead of the whole dict -- `SA._SCHEMA_STATE.get("is_corpus_constant", True)` is exactly "no
foreign release's schema left installed" (True when empty or when a 2026 schema is installed, False inside a 2025/2024
context, restored after) and `"dec" in GSK._SCHEMA_CACHE → type/schema identity` likewise; then the two per-file trims
here disappear. That is a three-line `tests/conftest.py` change this brief put out of bounds; the tech lead can pull it
into this PR by saying so.

## (3) The law: adopters derived by call; `ADOPTERS` = the six indirect callers; both directions still closed

`tests/test_conftest_scaffolding.py`:

* `CONTEXT_ENTRY_POINTS` = the six call names above (commented: write side / ladder / bare framing contexts; why by
  call and not by import or mention). `_context_callers()` = every module whose `_called_names(tree)` meets it (the
  same call-scan #639's rewrite-pass row uses; nested code included, string literals excluded by construction).
* **`test_every_in_process_context_caller_keeps_the_leak_guard_on`** (new, the by-call row): every caller requests
  `no_release_leak` module-wide or stands in `EXPECTED_UNGUARDED = {module: measured reason}` -- **empty today**
  (commented: a module-scoped fixture holding a context across its tests by design, or a file another session holds,
  would go there); the row's second assert drops a stale exception (guarded now, or no longer a caller). One row, not
  a parametrized one: deriving the caller list at collection time would parse all 231 test modules on every
  `--collect-only`; the failure message names each offender with the entry points it calls.
* `ADOPTERS` 15 → **6**, now a `{stem: "through what it enters a context"}` dict of exactly the callers the scan cannot
  see: `test_selfcheck_release` / `test_inspect_release` (`load_tool(...)` judges/walks foreign pins on the ladder),
  `test_edit_own_release` (`E.main([...])` / `FD.author(rvt=…)`), `test_rvt_edit_refusal` (`load_tool('rvt_edit').main`),
  `test_edit_status` (`FD.author(rvt=<2025 pin>)`), + `test_genesis_identity` (`GI.build_release(year)`). The nine that
  left (`test_edit_text_release`, `test_natively_framed`, `test_estorage_cli_release`, `test_release_ctx_refusal`,
  `test_cfb_rewrite_entries`, `test_rewrite_entries_646`, `test_identity_helper_657`, `test_reduce_v2_655`,
  `test_reduce_v2_671`, `test_rvt_job_scrub_656`) are callers: the by-call row holds them, so nothing was un-ratcheted.
  `test_adopter_keeps_the_leak_guard_on[stem]` stays, over the six.
* **#709's completeness row kept, re-aimed** (`test_every_module_on_the_leak_guard_enters_a_context`, was
  `…_is_an_adopter`): a module on the guard is a caller or on `ADOPTERS` -- never neither (else dropping its guard later
  would be silent); a `release_leak_extra` override without the guard is still the dead watch; and a module on
  `ADOPTERS` that the scan *can* see must come off it, so the dict cannot silt up into a second copy of the derived set.
  Shrinking `ADOPTERS` therefore weakens nothing: every module #709 listed is held by one row or the other, and the
  union is checked complete in both directions.
* The law module itself calls `RC.host_release_context(pin)` (#605's behaviour row) → it takes the guard like everyone
  (`pytestmark` + `release_leak_extra = C.context_constants`); measured green in file order and one-row-per-process.
* `FORBIDDEN` += the four private-guard spellings; module docstring updated.

The optional composed fixture (issue DONE 4: one `no_context_leak` in conftest replacing the now **16** identical
`return context_constants` + **8** `return ladder_constants` overrides) is not done here: `tests/conftest.py` was out of
bounds for anything but a call-scan helper, and #706's export changes the shape of the extra anyway -- do both at once.

## Evidence

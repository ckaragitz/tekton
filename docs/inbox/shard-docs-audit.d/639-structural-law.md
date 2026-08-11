# 639-structural-law -- the AST law forbids the container-rewrite PASS by shape; the last two private passes adopt conftest; `EXEMPT` is retired (shard-docs-audit stream, eng #639)

**Issue:** #639 (Refs #617 #604 #579; #640 / PR #648 for `rvt.roundtrip.rewrite_entries`). **Date:** 2026-08-11.
**Session:** eng #639 (cloud, `49c1513a`), started by the tech-lead session. **Base:** `main` @ `006121f` (PR #648 merged
first, as briefed: `conftest.rewrite_streams` is already the one-line caller of `rvt.roundtrip.rewrite_entries`).
Index: `docs/inbox/shard-docs-audit.md` (left untouched -- the README makes the index line optional, and that EOF is the
hot spot #636 exists to avoid). Written in this engineer's voice; no other record edited.

## Why

After #617 the law in `tests/test_conftest_scaffolding.py` was a **lexical** ratchet: `FORBIDDEN` listed every spelling
three hoists had retired. #617's altitude pass named its three weaknesses (issue body): (a) it could not see the
primitive -- `test_validate_footer_blob.strip_footer_blob` and `test_input_release._base_declaring` still hand-rolled
`read_entries → dataclasses.replace → write_cfb` and the law was, by its own rule, silent; (b) generic words
(`_partition`, `_rewrite`, `_variant`) forbidden tree-wide would one day convict an unrelated test for a word choice;
(c) `EXEMPT = set()` had been permanently empty since #604 and its self-check iterated nothing.

## What landed

1. **`tests/test_conftest_scaffolding.py` -- the structural row.** `REWRITE_PASS = {"read_entries", "write_cfb"}`;
   `_called_names(tree)` = every name a module *calls* anywhere (`ast.walk`, `ast.Call` whose `func` is a `Name` or an
   `Attribute` -- `f(…)` and `mod.f(…)` alike, nested code included); `test_no_module_hand_rolls_the_container_rewrite_pass`
   convicts every `tests/test_*.py` with `REWRITE_PASS <= _called_names(tree)` and names it, with the way out in the
   message (conftest's `rewrite_stream(s)` = `rvt.roundtrip.rewrite_entries`; a genuine builder-plus-census module splits
   the two or is allow-listed there with its reason). Decisions, each forced by a file in the tree today:
   * **Per module, not per function.** The retired footer_blob pass was a generator (`_entries`, the read side) consumed
     by `strip_footer_blob` (the write side): a per-function rule would have been born missing one of the two passes it
     exists to catch.
   * **Calls, not references.** `tests/test_famload_batch.py` rebinds `CW.write_cfb` in a counting seam (`real =
     CW.write_cfb`, `monkeypatch.setattr(CW, "write_cfb", counting)`) next to a `read_entries` census; a rule keyed on
     any `Name`/`Attribute` reference would false-positive there. The price -- a call through an alias (`w = write_cfb;
     w(…)`) is unseen -- is stated in the docstring: a ratchet against the habit, not against intent (the same stance
     `_top_level_names` takes on nested definitions).
   * **`olefile.OleFileIO` is deliberately not a source.** Turning an `OleFileIO` back into `CfbEntry`s is
     re-implementing `read_entries` (~25 lines: CLSIDs, state bits, FILETIMEs), which nobody writes by accident; counting
     it would make `tests/test_roundtrip.py` -- the CFB writer's own contract test, which builds containers from literal
     entries and re-reads them with *strict* olefile -- a permanent allow-list exception, and would tax every future
     writer test that verifies with an independent reader (exactly what #636's per-surface modules will produce).
   * **So no allow-list exists.** Classification of every `write_cfb` / `read_entries` site under `tests/` (below):
     after the two adoptions no module holds both, so the issue's anticipated "allow-list of builders" would have been
     born empty -- the very shape (c) retires. The assertion message says where one goes the day a real one appears.
2. **`FORBIDDEN` re-based on what the words mean.** `SHADOWS` = the 15 conftest own-release scaffolding names
   (`FOREIGN_FIRST`, `FOREIGN`, `native_constants`, `ladder_constants`, `no_release_leak`, `rewrite_streams`,
   `rewrite_stream`, `partition_of`, `twin_partition_entry`, `zero_partition_header`, `zero_schema_bytes`, `smash64`,
   `flip_bit`, `truncated_copy`, `cfb_header_zeroed_copy` -- the last four were not forbidden before; no module binds
   them, checked) and the name-law test now also asserts `SHADOWS <= vars(conftest)`, so the list cannot outlive a
   rename (mutation M3c below). `FORBIDDEN = SHADOWS |` the retired per-file spellings that actually existed and that
   the shape rule cannot see: the `NATIVE_LAST` axis and #579's private copies (`_native_constants`, `_no_leak`,
   `_rewrite_stream`, `_partition_of`), and #617's bytes-damage / extra-entry recipe names (`_zero16`, `_smash64`,
   `_flip_bit`, `_twin_entry` -- a bytes recipe or a `CfbEntry` builder writes no container, so `REWRITE_PASS` is blind
   to a regrown copy of those). **Dropped:** `_rewrite`, `_variant`, `_with_second_partition` (each *was* the pass, or
   the pass plus an extra entry -- caught by shape under any name now: mutation M2a uses none of these words and is red)
   and `_partition` (a generic word for a one-liner over `open_rvt(...).partition_streams()`; forbidding the word
   protected nothing). `release_leak_extra` is intentionally not a shadow: conftest documents it as the fixture a file
   overrides. Not done, and why: deriving `_`-twins of every shadow. A lexical list is honestly a ledger of spellings that
   existed (`_no_leak` was the historical twin of `no_release_leak`, not `_no_release_leak`); guessing more adds no
   generality, and the one file it would newly convict -- `tests/test_genesis_identity.py:39-43`, a private autouse
   `_no_release_leak` checking `active_release()` only -- is a guard-wiring adoption in #605's territory, noted there
   (issue comment) rather than fixed out of territory here.
3. **`EXEMPT` and `test_the_exempt_list_only_names_files_that_exist_and_still_need_it` deleted.** No escape hatch kept:
   the structural row needs none today (item 1), and the only new list (`SHADOWS`) has its staleness check folded into
   the name-law test whose meaning it guards. Law ids: 17 → 17 (`…exempt_list…` out, `…hand_rolls…` in; diff below).
4. **The two adoptions (helper adoption only: ids, axes, skip conditions, outcomes unchanged; outputs byte-identical).**
   * `tests/test_input_release.py::_base_declaring` → `rewrite_stream(BASE_2026, path, "BasicFileInfo", redate)` with
     `redate(raw) = encode_basic_file_info(dict(decode_basic_file_info(raw), format=str(year)))`; `dataclasses` and the
     local `read_entries` import go; `write_cfb` stays for `_cfb`, the literal synthetic-container **builder** (the
     sanctioned non-pass shape -- the module is green under the new row with no exception).
   * `tests/test_validate_footer_blob.py::strip_footer_blob` → `rewrite_stream(src, dst, stream, cut)` where `cut(raw)`
     unframes, walks, cuts the one footer blob and re-frames -- a real `bytes → bytes` damage -- run inside
     `VA.enter_own_release(stack, src)` because it reads `P.FOOTER_TAG` / `P.TERMINATOR`, module constants the release
     context rebinds (the first reshaping computed the patch after the walking generator had closed and promptly failed
     on the 2024 pin with tag `0x0e8f` ≠ native `0x0f3f` -- the byte harness caught it before anything was committed;
     kept here as the reason the `with` is load-bearing). `(stream,) = open_rvt(src).partition_streams()` keeps the
     retired loop's "exactly one Partitions stream" assertion. `census` now walks `open_rvt(path).partition_streams()` /
     `.raw(s)` through a shared `_walk(raw)` instead of filtering `read_entries` -- so the module imports neither
     `read_entries` nor `write_cfb` any more (`git grep read_entries -- tests/ | grep -v conftest`: 11 → 7 lines).
   * `tests/conftest.py`: **not touched** (default territory). Two conftest-side niceties surfaced by /simplify are left
     as open questions below rather than done out of territory.

## Evidence

**Byte identity, asserted BEFORE the private loops were deleted and again on the final tree** (`git show
006121f:tests/<file>.py` loaded beside the working copy; sha256, 16-hex prefixes; the two "built" rows use the module's
own prompt build, whose GUIDs differ run to run, so only old-vs-new *within* a run is meaningful):

| case | main `006121f` (private loop) | branch (conftest.rewrite_stream) | equal |
|---|---|---|---|
| strip_footer_blob(pin 2024, u0, new_len=0) | `b0175dc825e0fe8a` | `b0175dc825e0fe8a` | EQUAL |
| strip_footer_blob(pin 2024, u0, new_len=16) | `1075c69a0ba917e1` | `1075c69a0ba917e1` | EQUAL |
| strip_footer_blob(pin 2025, u0, new_len=0) | `517f703139122aaa` | `517f703139122aaa` | EQUAL |
| strip_footer_blob(pin 2025, u0, new_len=16) | `69cdb71db5794d99` | `69cdb71db5794d99` | EQUAL |
| strip_footer_blob(pin 2026, u0, new_len=0) | `ad296387a1b8b4f0` | `ad296387a1b8b4f0` | EQUAL |
| strip_footer_blob(pin 2026, u0, new_len=16) | `e939264e678aa39a` | `e939264e678aa39a` | EQUAL |
| _base_declaring(pin 2024 → Format: 2020) | `dd1980a66f76a7be` | `dd1980a66f76a7be` | EQUAL |
| _base_declaring(pin 2024 → Format: 2027) | `62bcc9f0fc0e9dec` | `62bcc9f0fc0e9dec` | EQUAL |
| _base_declaring(pin 2025 → Format: 2020) | `7eae39cbe50044b0` | `7eae39cbe50044b0` | EQUAL |
| _base_declaring(pin 2025 → Format: 2027) | `69803aa8189cc3a9` | `69803aa8189cc3a9` | EQUAL |
| _base_declaring(pin 2026 → Format: 2020) | `311d9fa5dbfc253c` | `311d9fa5dbfc253c` | EQUAL |
| _base_declaring(pin 2026 → Format: 2027) | `492800d3d4a4351f` | `492800d3d4a4351f` | EQUAL |
| strip_footer_blob(built load_only, u1, new_len=0) | (run-local) | (same) | EQUAL |
| strip_footer_blob(built combined, u1, new_len=0) | (run-local) | (same) | EQUAL |

**14/14 EQUAL** on the first adoption, on the intermediate shape, and on the final /simplify shape (three harness runs).

**Mutation proofs (all reverted; law file otherwise final):**
* M1 -- the retired private loop appended back onto an adopter (`tests/test_input_release.py`, a `_regrown()` doing
  `write_cfb(path, [dataclasses.replace(e, …) … for e in read_entries(BASE_2026)])`) → **red, naming it**:
  `AssertionError: ['test_input_release'] pair read_entries() with write_cfb() -- the hand-rolled 'read the entries,
  replace some, write the container' pass …`; reverted → `1 passed`.
* M2a -- a NEW module `tests/test_zz_planted_639.py` hand-rolling the pass under innocent names (`emit()`, `kept`,
  `R.read_entries(PIN)` as an attribute call, `entry.__class__(**…)` instead of `dataclasses.replace`, no forbidden WORD
  anywhere) → **red**: `['test_zz_planted_639'] pair read_entries() with write_cfb() …`; its output sha256 `ced6d20226e08c64`.
* M2b -- the same file routed through `conftest.rewrite_stream(PIN, dst, "BasicFileInfo", blank_bfi)` → **green**
  (`1 passed`), output sha256 `ced6d20226e08c64` -- **the same bytes**. File removed; law `17 passed`.
* M3a -- kept spellings planted at top level of `tests/test_records_layout.py` (`def _smash64`, `def
  twin_partition_entry`) → red: `{'test_records_layout': ['_smash64', 'twin_partition_entry']} -- import the own-release
  scaffolding from conftest instead (#579)`. M3b -- the dropped generic words planted (`def _variant`, `_partition = 1`)
  → green (the intended change of meaning, and the only one). M3c -- `"renamed_helper_x"` added to `SHADOWS` → red:
  `['renamed_helper_x'] are no conftest names any more: drop them from SHADOWS`. All reverted.
* Before adoption, the new row on the untouched tree convicted **exactly** `['test_input_release',
  'test_validate_footer_blob']` -- the two files the issue names, nothing else.

**`git grep -n "write_cfb" -- tests/` classified (before → after):** `test_famload_batch.py` ×4 (docstrings + the
counting seam: attribute rebinding, no call -- reader-only module, green) unchanged; `test_input_release.py` 3 → 2
(import + `_cfb` builder; the `_base_declaring` call gone); `test_roundtrip.py` ×10 (the writer's contract test:
literal builders, no `read_entries` -- green) unchanged; `test_validate_footer_blob.py` 2 → 0;
`test_conftest_scaffolding.py` 0 → 5 (the law's own prose and constant). **`git grep -n "read_entries" -- tests/ |
grep -v conftest`:** 11 → 7 lines (`test_cfb_rewrite_entries` ×2, `test_famload_batch` ×3, `test_genesis_identity` ×2
remain -- all reader-only).

**Gates** (`RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_conftest_scaffolding.py tests/test_validate_footer_blob.py
tests/test_input_release.py tests/test_partition_header_verdict.py tests/test_ecc_final_block.py
tests/test_gates_shared_walk.py tests/test_records_layout.py -q -rs`): main `006121f` **129 passed** (no skips) → branch
**129 passed** (−1 exempt self-check, +1 structural row). `--collect-only -q` ids of the two adopters: **38 = 38,
identical**; law ids 17 → 17 with exactly the one swap. Whole merged shard (`$(python3 tools/dev/shard_list.py --print)`,
107 files, sequential, `-p no:cacheprovider`): see BRANCH STATE for the exact-head figures next to main's.
`python3 tools/dev/check_portable_paths.py` → ok. `RVT_DOCS_AUDIT=report` census: this change opens no `docs/` file
(the law reads `tests/` sources only; the fragment is read by no test -- `test_records_layout` judges names).

**/simplify (4 angles) -- taken:** `functools.cache` on `_tree` (the second full-tree row would otherwise re-parse ~190
modules, ≈0.5 s per shard run); `_called_names` spelled plainly with the calls-not-references reason in its docstring;
the assertion message names the escape for a genuine builder+census module; the `FORBIDDEN` comment says what the set
*is* (the dropped-word changelog lives here instead); plain set literal for `REWRITE_PASS`; footer_blob reshaped to a
real `cut(raw)` damage under the file's release + `open_rvt` census (drops a `lambda _raw: reframed` adapter, an
`ExitStack` threaded through a generator, a dead tuple slot, and the module's `read_entries` import; one container read
per strip instead of two). **Skipped, with reason:** widening `conftest.rewrite_stream(s)`' docstring to advertise the
`bytes` arm `rewrite_entries` already accepts, and a conftest-side `OWN_RELEASE_SCAFFOLDING` tuple the law could import
instead of listing `SHADOWS` -- both are `tests/conftest.py` edits outside this issue's default territory (open
questions below); a `redate_bfi` recipe for the two look-alike BFI re-daters (`test_input_release`, `test_clause_relays`)
-- two copies do not make a helper.

## Open questions / follow-up candidates (not filed as issues: each is a two-line conftest nicety, better folded into the next conftest-territory issue, e.g. #605)

* `tests/conftest.py::rewrite_streams` docstring could say "`damage`: bytes, a callable over the raw bytes, or None --
  as `rewrite_entries`"; today a caller holding ready-made bytes writes `lambda raw: those` to stay inside the documented
  contract (nobody needs to after this PR).
* `tests/conftest.py` could declare `OWN_RELEASE_SCAFFOLDING = (…)` next to the definitions and the law import it as
  `SHADOWS`, making "add a recipe" and "forbid its shadow" one edit in one file; the `SHADOWS <= vars(conftest)` assert
  is the cheap guard meanwhile.
* #605 now carries the `test_genesis_identity` private leak guard (comment posted from this session).

BRANCH STATE (cam/639-structural-law): `tests/test_conftest_scaffolding.py` (structural row + `_called_names`,
`REWRITE_PASS` / `SHADOWS` / re-based `FORBIDDEN`, `EXEMPT` + its self-check deleted, `_tree` cached, docstring bullet),
`tests/test_input_release.py` and `tests/test_validate_footer_blob.py` (helper adoption only), this fragment (new dir
`docs/inbox/shard-docs-audit.d/`, index untouched). Nothing under `src/`, `tools/`, `plugin/`, `skills/`, `tests/conftest.py`;
no shard drop-in needed (all three test files already in the merged shard: `579-scaffolding.txt`, `ci_shard.txt`);
nothing staged for the viewer; no certification claim; no hot file. Whole merged shard (107 files, sequential): branch tree
before the /simplify reshaping **2218 passed, 134 skipped, 3 xfailed, 3 warnings** in 436 s; on the exact code head
(`8d37b73` content = PR head, the later commits are this fragment only) **2218 passed, 134 skipped, 3 xfailed, 3 warnings**
in 426 s; `main` `006121f` in a worktree, same interpreter, run side by side: **2218 passed, 134 skipped, 3 xfailed,
3 warnings** in 432 s -- equal, as expected (one law row swapped, nothing added or removed).

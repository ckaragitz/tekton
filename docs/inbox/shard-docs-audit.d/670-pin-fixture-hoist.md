# 670-pin-fixture-hoist -- the pinned-base `pin` fixture and the `streams(path)` container census live ONCE in `tests/conftest.py`; four private copies retired and convicted by the scaffolding law (shard-docs-audit stream, eng #670)

**Issue:** #670 (filed by eng #657's /simplify reuse pass; Refs #657, #646, #451, #579). **Date:** 2026-08-11.
**Session:** eng #670 (cloud, `cse_01C82apjgTbhcgWYnzvAZPBv`), started by the tech-lead session. **Base:** `main` @
`345493c` (#669) for every measurement below; #673 (`reduce_v2`, its own new test module + drop-in, disjoint from every file
here) was announced as landing first -- see BRANCH STATE for the rebase note. Index: `docs/inbox/shard-docs-audit.md` (left
untouched -- the README makes the index line optional). Written in this engineer's voice; no other record edited.

## Why

`tests/test_identity_helper_657.py` was the FOURTH module to open with the same nine lines: a module-scoped `pin` fixture
(`C.pinned_base(C.FOREIGN_FIRST[0])`, or `pytest.skip("no certified pinned base")` when nothing is certified) and a
`_streams(path) -> {stream path: raw bytes}` census over `rvt.roundtrip.read_entries` -- after
`tests/test_cfb_rewrite_entries.py` (#640), `tests/test_rewrite_entries_646.py` (#646) and the law module
`tests/test_conftest_scaffolding.py` itself (#579/#617). #646's record had already named the home ("`tests/conftest.py`,
which this issue's territory excludes by name"). Same move as #451 / #579 / #604: hoist once, adopt, and teach the law the
retired spelling so a fifth copy is red on arrival.

## The four copies, side by side (main @ `345493c`) -- and what the hoisted pair therefore is

| module | `pin` | `_streams` |
|---|---|---|
| `test_cfb_rewrite_entries.py:25-34` | `@pytest.fixture(scope="module")`; skip `"no certified pinned base"` if `not C.CERTIFIED_YEARS`; `return C.pinned_base(C.FOREIGN_FIRST[0])` | `read_entries(os.fspath(path))`, streams only, docstring "in directory order" |
| `test_rewrite_entries_646.py:29-37` | identical | identical body, no docstring |
| `test_identity_helper_657.py:36-50` | identical | identical body, no docstring |
| `test_conftest_scaffolding.py:147-157` | identical | `read_entries(path)` (no `fspath` -- only ever handed `str`), local import |

So, honestly read: the four `pin` fixtures are byte-identical -- **not** parametrized over the three pins and entering **no**
release context (each test that decodes framing enters `host_release_context(pin)` / `release_build_context(pin)` itself;
the per-year rows in `test_identity_helper_657` parametrize over `C.CERTIFIED_YEARS` and call `C.pinned_base(year)`
directly, untouched here). The brief floated "parametrized over the three pinned bases … entering `host_release_context`
for foreign pins exactly as the copies do": the copies do neither, and parametrizing would triple every adopter's ids
(DONE 2 forbids an id diff), so the hoisted fixture is exactly the copy. The one `_streams` variance (`os.fspath`) resolves
to the superset: the conftest reader takes `str` or `PathLike`.

## What landed

1. **`tests/conftest.py`** (scaffolding section only; +21 lines, nothing else touched but the module docstring's name list):
   * `pin` -- `@pytest.fixture(scope="module")`, the first of `FOREIGN_FIRST` via `pinned_base` (a foreign pin when one is
     certified -- today 2024 -- so a by-value native assumption shows; the native pin otherwise), `pytest.skip("no certified
     pinned base")` when `CERTIFIED_YEARS` is empty; docstring says the fixture enters no context and why. A conftest
     fixture needs no import: the adopters simply stopped defining their own.
   * `streams(path) -> dict` -- `{e.path: e.data for e in read_entries(os.fspath(path)) if e.entry_type == "stream"}`,
     placed with the fixture just above `rewrite_streams`, whose before/after census it is.
2. **The four adopters** -- private `pin` + `_streams` deleted; every `_streams(` call respelled `C.streams(` (all four
   already `import conftest as C`); imports that only the copy used dropped (`read_entries` in `test_cfb_rewrite_entries`,
   `os` + `read_entries` in `test_identity_helper_657`). No assertion changed meaning; no test added or removed in the three
   plain adopters.
3. **`tests/test_conftest_scaffolding.py`** (the law): `SHADOWS` += `{"pin", "streams"}` (so a module-level `pin` fixture or
   `streams` helper is a convicted shadow, and the `SHADOWS ⊆ vars(conftest)` staleness check now guards both names);
   `FORBIDDEN` += `{"_streams"}` (the retired private spelling the shadow set cannot see); the structural
   `read_entries`+`write_cfb` row, `ADOPTERS`, and every other row keep their meaning verbatim. **One** behavioural row added,
   `test_pin_is_the_first_foreign_first_pin_and_streams_is_its_every_stream_raw`: `pin == C.pinned_base(C.FOREIGN_FIRST[0])`
   (what the copies resolved -- the fixture's meaning pinned, so a drift to another axis is red here first), and
   `C.streams(pin)` == `{s.name: doc.raw(s.name)}` over `rvt.container.open_rvt` (an independent reader as oracle: every
   stream, no storage, raw = still paged). The PathLike spelling is exercised by the adopters themselves
   (`C.streams(tmp_path / "v8.rvt")` etc.). That row is the only collect-id delta in the PR.
4. Nothing under `src/`, `tools/`, `plugin/`, `skills/`; no `tests/ci_shard.d` drop-in (all five files are already in the
   merged shard); no hot file.

## Evidence

Per adopter, `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest <file> -q -rs` and `--collect-only -q | sort`, main @ `345493c`
→ branch:

| module | ids before → after | `collect` diff | outcome before → after |
|---|---|---|---|
| `tests/test_cfb_rewrite_entries.py` | 10 → 10 | empty | 10 passed → 10 passed |
| `tests/test_rewrite_entries_646.py` | 16 → 16 | empty | 15 passed, 1 skipped (`:160` root/read-only gate) → 15 passed, 1 skipped (same gate, now `:149`) |
| `tests/test_identity_helper_657.py` | 17 → 17 | empty | 17 passed → 17 passed |
| `tests/test_conftest_scaffolding.py` | 17 → 18 | `+ …::test_pin_is_the_first_foreign_first_pin_and_streams_is_its_every_stream_raw` only | 17 passed → 18 passed |

Mutation proofs (each planted, run `-k private_copy`, reverted; law green again 18/18 after):

* top-level `def _streams(path)` appended to `tests/test_rewrite_entries_646.py` → **red**:
  `AssertionError: {'test_rewrite_entries_646': ['_streams']} -- import the own-release scaffolding from conftest instead (#579)`;
* a private `@pytest.fixture(scope="module") def pin()` appended to `tests/test_identity_helper_657.py` → **red**:
  `AssertionError: {'test_identity_helper_657': ['pin']} -- …`;
* `conftest.streams` renamed away → **red**: `AssertionError: ['streams'] are no conftest names any more: drop them from SHADOWS`.

`git grep -n "def _streams\|def pin(" -- tests/ | grep -v conftest`: 4 + 4 hits before → **0** after (the one remaining hit
is `tests/conftest.py:301 def pin()`). `python3 tools/dev/check_portable_paths.py` ok (3051 paths);
`.venv/bin/python plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/sync_plugin.py --check` in sync (sanity --
nothing under `src/` moved). Whole merged shard: see BRANCH STATE.

## Findings / not done, on purpose

* **A fifth, nested copy stays -- and the census has an engine-shaped home:** `tests/test_famload_batch.py:218` defines
  `def streams(p)` *inside* a test function (same dict comprehension); `tools/genesis_deletion.py:935-936` and
  `tools/genesis_addpath_probes.py:227` / `:1194` carry it too. All outside this issue's territory (tests-only, the four
  named modules); the nested one is invisible to the law by design (`_top_level_names` reads `tree.body` only) and not
  matched by the issue's grep gate. /simplify's altitude reviewer judged the right depth to be `rvt.roundtrip.read_streams`
  beside `read_entries` / `catalog` (the #640 move, after which conftest's helper becomes a re-export) → filed **#677**.
* `pin` is deliberately not the parametrized "every certified pin" axis: that axis already exists as
  `@pytest.mark.parametrize("year", C.CERTIFIED_YEARS / C.FOREIGN_FIRST)` + `C.pinned_base(year)` wherever a row needs all
  three, and the container-level rows these four modules run need one pin, preferably foreign. The `SHADOWS` comment now
  says a module wanting another pin axis takes another fixture name (a private `pin` with `params=` is still a copy).

## /simplify (RAN, four reviewers on the working-tree diff)

Fixed: the new law row's third full-container read (`C.streams(Path(pin)) == got`) and the `pathlib` import it alone
justified dropped -- PathLike is what the adopters already pass; `doc.streams()` walked once, not twice; the `pin` docstring
cut from five lines to three (contract, not history); three trailing comments realigned to their neighbours' column; the
`SHADOWS` clause above. Skipped, with reason: "`pin == C.pinned_base(C.FOREIGN_FIRST[0])` is a tautology" -- it restates the
fixture body on purpose, as the law's pin of the fixture's meaning (kept); the nested/tools copies -- out of territory
(→ #677). Reuse: no pre-existing engine or conftest helper returned `{path: raw}` in one call; efficiency: fixture scope
unchanged (module), no import-time work added to conftest (lazy `read_entries` import), the law row costs two ~0.6 MB reads.

## Follow-ups (searched first; task-shaped, Refs #670)

- **#677** -- `rvt.roundtrip.read_streams(path)`; conftest re-exports it; the two `tools/genesis_*` sites and
  `tests/test_famload_batch.py:218` adopt it.

BRANCH STATE (cam/670-pin-fixture-hoist): `tests/conftest.py` (+`pin` fixture, +`streams`; docstring name list),
`tests/test_cfb_rewrite_entries.py` / `tests/test_rewrite_entries_646.py` / `tests/test_identity_helper_657.py` (copies
deleted, `C.streams(...)`, dead imports dropped -- adoption only), `tests/test_conftest_scaffolding.py` (copies deleted,
`SHADOWS` +2, `FORBIDDEN` +1, one behavioural row, docstring), this fragment (new). Not touched: `src/**`, `tools/**`,
`plugin/**`, `skills/**`, `tests/ci_shard*`, the collaborator's `tests/test_prompt*` / `test_router*` / `test_famgen_*`,
`tests/test_reduce_v2_655.py` (#673's, carries no copy), any hot file, the stream index. Gates: the table above; mutation
proofs above; whole merged shard `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest -q -p no:cacheprovider $(python3
tools/dev/shard_list.py --print)` on the branch: **SHARD_RESULT_PLACEHOLDER**; `/simplify` RAN on the diff (result on the PR);
`/verify` NOT RUN -- tests-only diff with no runtime surface to drive (`No-Verification-Needed: tests-only` trailer).
Nothing staged for the viewer; no certification claim; nothing generated committed.

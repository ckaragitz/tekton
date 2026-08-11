# 638-fragment-seams -- the record-layout law is felt at merge time (process-friction stream, eng #638)

**Issue:** #638 (Refs #636, #522, #328). **Date:** 2026-08-11. **Session:** eng #638 (cloud, `cse_01MJeDexW92FTUXqLCNjb2zA`).
Index: `docs/inbox/process-friction.md`.

## Why

#636 shipped the fragment convention with its law as a pure function `violations(names)` inside
`tests/test_records_layout.py` -- felt at CI time only. `tools/dev/ci_fresh.sh` re-judges the *post-merge name set* solely
through `tools/dev/check_portable_paths.check(paths)` (#522's seam), so "PR deletes index `docs/inbox/old.md`" (green
against the main of its run) + "main docs-only-adds `docs/inbox/old.d/1-x.md`" (tolerated drift) could each be green and
meet red on `main`. Two process docs still named only the single-file record, and `techlead.py recent_records()`
returned the alphabetically first 30 inbox paths, hiding every recent fragment.

## What landed

1. **The law moved into the names gate.** `tools/dev/check_portable_paths.py` gains `INBOX`, `FRAGMENT` and
   `layout_violations(names) -> [(breach line, names involved)]` (same two rules as #636, now also naming the files
   involved so the merge gate's `changed=` list can name them); `check(paths)` appends its findings as
   `("record layout (docs/inbox/README.md): <line>", [repo-relative names])` after the portability laws. No sibling
   module: `session_ci.sh` runs the file with `python3 -I` and `ci_fresh.sh` loads it by path, so a
   `tools/dev/records_layout.py` import would not resolve -- that decided "inside the checker" over "a tiny module".
   `tests/test_records_layout.py` keeps its rows (now via `conftest.load_tool("dev/check_portable_paths")`, no local
   definition) and gains `test_check_feels_the_law_over_repo_relative_names_and_only_under_docs_inbox`.
2. **`tools/dev/ci_fresh.sh` untouched** (`git diff --stat -- tools/dev/ci_fresh.sh` empty; `bash -n` ok). Its existing
   post-merge re-run now refuses the shape by itself; pinned by one new row in `tests/test_ci_fresh.py`,
   `test_an_index_the_pr_deletes_while_main_adds_a_fragment_beside_it_is_stale` (rig: PR 9 deletes `docs/inbox/old.md`,
   main adds `docs/inbox/old.d/1-x.md` -> exit 4 `STALE … changed=docs/inbox/old.d/1-x.md (tools/dev/check_portable_paths.py
   rejects the post-merge name set: record layout (docs/inbox/README.md): old.d/ has no index old.md beside it)`; control:
   PR 7, which keeps `old.md`, stays `FRESH(docs-only drift)` under the very same drift). The rig's `pr()` helper gained a
   `delete=()` passthrough to `conftest.git_commit` for it. Red before / green after: with `HEAD`'s checker the row fails
   (`(0, 'FRESH(do…') != (4, 'STALE …')`), with this branch's it passes.
3. **Docs, one clause each** (all three stay true for the single-file form and now name the fragment form):
   * `.github/prompts/worker.md` step 3: "write/extend the stream record `docs/inbox/<stream>.md` ending in a `BRANCH STATE`
     block" -> "write/extend the stream record — your own fragment `docs/inbox/<stream>.d/<issue>-<slug>.md` when the stream
     already has a record, else `docs/inbox/<stream>.md` (`docs/inbox/README.md`) — ending in a `BRANCH STATE` block";
   * `docs/process/AUTONOMY.md` §3 artefact table, first cell of the record row: `` `docs/inbox/<stream>.md` `` ->
     `` `docs/inbox/<stream>.md`, or that index + one `docs/inbox/<stream>.d/<issue>-<slug>.md` fragment per PR (`docs/inbox/README.md`) ``
     -- AUTONOMY.md is a `SHARD_READS` file (needles pinned by `tests/test_techlead.py`), so the edit is that one cell only;
   * `.github/prompts/techlead.md` source 3: "in recent `docs/inbox/*.md` records" -> "in recent `docs/inbox/*.md` records and
     `docs/inbox/*.d/*.md` fragments (`techlead.py brief` lists the recently touched ones)".
4. **`recent_records(days=14, cap=30)`** keeps `git log -- docs/inbox` order (most recently touched first), dedups with
   `dict.fromkeys`, caps after; return shape unchanged (list of repo-relative paths). Pinned by
   `tests/test_techlead.py::test_recent_records_lists_the_most_recently_touched_first_deduped_and_capped` on a throwaway repo
   (literal fictional record names on purpose: `tests/test_ci_fresh.py`'s docs-reads scanner reads a *computed*
   `docs/inbox/` name in `test_techlead.py` -- a real reader of AUTONOMY.md -- as a read of the whole directory).

## Evidence

* `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_records_layout.py tests/test_portable_paths.py tests/test_ci_fresh.py
  tests/test_techlead.py tests/test_coord.py tests/test_docs_read_audit.py tests/test_shard_list.py -q -rs`:
  before **107 passed, 3 skipped** (gawk / busybox absent, docs-audit self-test) -> after **110 passed, 3 skipped** (+1 row per file
  named above).
* `python3 tools/dev/check_portable_paths.py` on the tree: `ok: 3020 tracked paths are portable` (also under `python3 -I`).
  On a temp `git worktree` with `docs/inbox/orphan.d/638-x.md` + `docs/inbox/process-friction.d/notes.md` staged: exit 1,
  `record layout (docs/inbox/README.md): orphan.d/ has no index orphan.md beside it` and `… process-friction.d/notes.md is not
  named <issue>-<slug>.md`; with `process-friction.md` removed instead: exit 1, `process-friction.d/ has no index …`.
* `bash -n tools/dev/ci_fresh.sh` ok (file unchanged); `python3 tools/dev/techlead.py hello` prints the offline banner;
  `.venv/bin/python plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/sync_plugin.py --check` in sync
  (`tools/dev/` is not mirrored).
* Whole merged shard: not run here (process tooling + tests; the tech lead's sandbox runs it).

## Findings / open questions

* The checker's CLI header still says `NON-PORTABLE PATHS:` above a record-layout line; left as is because
  `tests/test_portable_paths.py` pins the CLI output byte for byte and each line names its law. Rename it in a later
  portable-paths PR if it grates.
* `docs/inbox/README.md` still says the law is "pinned by `tests/test_records_layout.py`" -- true (that test pins it; the
  function merely lives in the checker now); outside this territory, not edited.

## BRANCH STATE

* Branch `cam/638-fragment-seams` from `origin/main` @ 1376709 (#643); PR opened ready, `Closes #638`.
* Files: `tools/dev/check_portable_paths.py`, `tools/dev/techlead.py` (`recent_records` only), `tests/test_records_layout.py`,
  `tests/test_ci_fresh.py` (one row + the rig's `delete=` passthrough), `tests/test_techlead.py` (one row + `git_commit` import),
  `tests/test_portable_paths.py` (module docstring clause only), `.github/prompts/worker.md`, `.github/prompts/techlead.md`,
  `docs/process/AUTONOMY.md` (one clause each), `docs/inbox/process-friction.md` (one index line), this fragment.
  Not touched: `tools/dev/ci_fresh.sh`, `CLAUDE.md`, workflows, engine, `tests/conftest.py`, hot files.
* Gates: above. `/simplify` run on the code; `/verify` skipped with a `No-Verification-Needed:` trailer (process tooling +
  tests, no product runtime surface).
* Nothing staged for the viewer; no certification claim.

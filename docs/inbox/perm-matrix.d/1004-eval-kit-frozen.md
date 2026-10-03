# #1004: the eval-kit snapshot says it is frozen

Refs #1004, #998, #1002.

## Decision: freeze, not refresh
`tekton-eval-kit/` is the bundle evaluators were sent on 2026-08-11 (commit `6f33fb7`). Refreshing it would rewrite history, and it would also change the `TEST-KIT/` files that `tests/test_family_anatomy_837.py` and `tests/test_partition_header_verdict.py` read as fixtures. So it stays byte-for-byte, and a new `tekton-eval-kit/FROZEN.md` says what it is:
- its date and source commit;
- that current behaviour is in `plugin/`;
- the known-stale claims inside it: the pre-#48 open cell and its dead stamp, with the correct statement and the PRs that fixed them.

## Guard
`tests/test_open_cell_996.py::test_the_frozen_eval_kit_says_it_is_frozen` checks that the snapshot still naming the dead stamp ⇔ `FROZEN.md` exists. It also checks that the note names `OPEN_CELL_STAMP`, its date, and `plugin/`. A refresh that drops the stamp must drop the note, and should then put the kit into `SCANNED`. Measured both ways: with the note, 89 passed; with the note moved away, the test fails.

## BRANCH STATE
- Files: `tekton-eval-kit/FROZEN.md` (new), `tests/test_open_cell_996.py` (one test), this fragment.
- Gates: `test_open_cell_996` 89 passed; `sync_plugin.py --check` in sync; `check_portable_paths` ok.
- Staged: nothing.

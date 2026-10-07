# 1034 — CI never tests, and the merge gate never accepts, an older PR head

Stream **ci-fresh-merge-tree** (tech-lead session, 2026-10-07). Closes #1034.

## The incident

On #1031, four consecutive `tools/dev/session_ci.sh 1031` runs (~20 minutes each) tested `refs/pr/1031` as it was first fetched, `1499a8b`. In that time the PR moved on four times (`dc04eca` → `80f20fe` → `5495eda` → `ee314e2`).

`tools/dev/ci_fresh.sh 1031`, called without a head, compared only `main`, so it said FRESH. The JSON did record the stale `head`, which is how it was caught. Nothing was merged on it, but the CI time was lost.

## What changed

- **`tools/dev/pr_head.sh <pr>` (new).**
  - Reads origin's `refs/pull/<pr>/head` with `git ls-remote` (no objects).
  - Re-fetches `refs/pr/<pr>` when it differs, and prints the head the ref now holds.
  - An origin that cannot be read is a **refusal** (exit 2), never a run on a ref that may be stale.
  - An origin with no PR refs (not GitHub, a test rig) leaves a local ref in use as is, and says so.
- **`session_ci.sh`** calls it before it reads `HEAD`. A failure there is a new setup-failure JSON, named in the header. `SESSION_CI_OFFLINE=1` keeps the old behaviour and logs it.
- **`ci_fresh.sh <pr>`** without a `<head-sha>` reads the PR's head from origin itself. So a verdict for an earlier push is now `WRONG-HEAD` (exit 5) instead of FRESH. It already refused that when given the head; now the bare call does too. An unreadable origin is "cannot judge" (exit 2), as the `main` fetch already was.

## Evidence

- `tests/test_ci_head_1034.py`: **6 passed**, on the same throwaway-repo rig as `tests/test_ci_fresh.py`:
  - a behind ref is refreshed;
  - a current ref is left alone and prints nothing on stderr;
  - with no PR refs the local ref is used and stderr says so, and with no ref at all it refuses;
  - an unreadable origin refuses;
  - `ci_fresh.sh` alone says FRESH for the PR's head and `WRONG-HEAD` after a later push;
  - `session_ci.sh` calls the helper before reading `HEAD`.
- `tests/test_ci_fresh.py`, `tests/test_techlead.py`, `tests/test_session_ci_budget_918.py`, together with the new file: **77 passed, 2 skipped**. The setup-failure pin is now 7, and "current head" is a named reason.
- `check_portable_paths`: ok. `tools/sync_plugin.py --check`: clean (no plugin file is involved).

## BRANCH STATE

- Files:
  - `tools/dev/pr_head.sh` (new), `tools/dev/session_ci.sh`, `tools/dev/ci_fresh.sh`;
  - `tests/test_ci_head_1034.py` (new) with the drop-in `tests/ci_shard.d/1034-ci-head.txt`, as `test_ci_fresh.py` is;
  - `tests/test_ci_fresh.py` (the pin);
  - this record.
- Shipped on merge; nothing is staged.

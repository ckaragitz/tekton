# sync-plugin-zip-stdlib — issue #37

## What was built

`tools/sync_plugin.py::rebuild_zip()` no longer shells out to the Unix `zip`
binary. It builds `tekton-plugin.zip` with the stdlib `zipfile`, from an
explicit, sorted member list (`zip_members()`).

## Evidence

Before, on Windows — the run dies *after* `plugin/` has already been rewritten:

```
FileNotFoundError: [WinError 2] The system cannot find the file specified
sync exit=1
```

After:

```
synced 0 file(s) into plugin/
  deny-audit clean; assets verified (genesis base == frontdoor pin)
rebuilt tekton-plugin.zip (4941 KB)
sync exit=0
```

Archive audit (282 entries):

| property | result |
|---|---|
| two consecutive builds | **byte-identical** (sha256 `7378acdd0407…`) |
| plugin contents at archive root | `.claude-plugin/plugin.json` present |
| `__pycache__` / `node_modules` / `.DS_Store` entries | 0 / 0 / 0 |
| `.rvt` entries | exactly the 3 certified genesis bases under `assets/` |
| sorted / duplicates | sorted, none |

Tests:

- `tests/test_plugin_zip.py` (new) — **4 passed**.
- `tests/test_plugin_sync.py` — 7 passed; `tools/sync_plugin.py --check` exit 0.
- `tests/test_bootstrap.py` + `tests/test_coldstart.py` — 5 failed / 14 passed,
  which is **exactly** the Windows baseline on unmodified `main` (1 bootstrap +
  4 coldstart, all the cp1252 signature of #29). No regression from this change;
  those tests cannot go green on Windows until #29 lands.

## Findings

- The old two-pass shell-out had a subtlety worth preserving deliberately rather
  than by accident: pass 1 excluded `*.rvt` everywhere, then pass 2 re-added
  `assets/` recursively, so `.rvt` shipped *only* under `assets/`. `zip` merged
  the passes by replacing entries; `zipfile` would have written duplicates. The
  single-pass rule is now stated directly — exclude `.rvt` unless the archive
  name starts with `assets/` — and a test asserts both halves.
- Entries are stamped with a fixed `date_time` (the zip format's 1980 minimum)
  and sorted, so the artifact no longer churns on every run. It is git-ignored,
  but a stable hash makes "did the bundle actually change?" answerable.
- File modes are carried from `os.stat`. On Windows those are synthetic, so a
  Windows-built and a Unix-built zip will agree on *entries* but not
  byte-for-byte. That is fine for how the bundle is consumed — CLAUDE.md §3b
  invokes bundled scripts as `python <script>.py`, never relying on the
  executable bit — but it is the reason this record claims determinism
  per-platform rather than across platforms.

## Open questions

- `tests/test_plugin_zip.py` should join `tests/ci_shard.txt` once both this and
  #2 have merged. Not done here: the shard file does not exist on this branch,
  and editing it from two branches at once is exactly the stacking mess the
  hot-file rule exists to prevent.
- `validate()` still shells out to the `claude` CLI, but it already guards with
  `shutil.which` and skips cleanly when absent, so it is not a portability bug.

## BRANCH STATE

- Branch: `ckaragitz12/37-sync-plugin-zip-stdlib`, **stacked on
  `ckaragitz12/27-gitattributes-eol`** (PR #38). It needs #27's `schema_cache`
  determinism fix, or a full sync on Windows still reports drift before it ever
  reaches the zip step. **Retarget to `main` after #38 merges.**
- Files written:
  - `tools/sync_plugin.py` (`rebuild_zip`, new `zip_members`, `import zipfile`)
  - `tests/test_plugin_zip.py` (new)
  - `docs/inbox/sync-plugin-zip-stdlib.md` (this record)
- Gates: full `python tools/sync_plugin.py` exit 0 on Windows;
  `--check` exit 0; `test_plugin_zip.py` 4 passed; `test_plugin_sync.py` 7 passed;
  bootstrap/coldstart at the unchanged #29 baseline.
- Staged vs shipped: shipped. No viewer certification claim.

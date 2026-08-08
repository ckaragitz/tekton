# text-encoding-utf8 — issue #29 (stage 1)

## What was built

`rvt.frontdoor.manifest.write_manifest()` now writes `manifest.json` and
`MANIFEST.md` with `encoding="utf-8", newline="\n"`.

That is the whole of stage 1. Stages 2 and 3 (the `tools/dev/check_text_encoding.py`
guard, and the sweep of the remaining call sites) are **not** in this branch.

## Evidence

Every one of the five Windows-only test failures traced to a single call site,
`src/rvt/frontdoor/manifest.py:370`:

```
UnicodeEncodeError: 'charmap' codec can't encode character '→'
  in position 1645/1733/1921/1922/1964
  File ".../lib/src/rvt/frontdoor/manifest.py", line 370, in write_manifest
```

Before → after on Windows (CPython 3.12.10):

| test file | before | after |
|---|---|---|
| `tests/test_frontdoor.py` | 1 failed, 26 passed, 4 skipped | **27 passed, 4 skipped** |
| `tests/test_bootstrap.py` | 1 failed, 7 passed | **8 passed** |
| `tests/test_coldstart.py` | 4 failed, 7 passed | **11 passed** |

Shard-equivalent run on Windows — `test_frontdoor`, `test_versions`,
`test_steplite`, `test_plugin_sync`, `test_plugin_zip`, `test_bootstrap`,
`test_coldstart`:

```
76 passed, 30 skipped in 8.02s
```

Zero failures. Gates: `tools/sync_plugin.py --check` exit 0;
`tools/dev/check_portable_paths.py` → `ok: 2612 tracked paths are portable`.

Direct check of the written artifacts: `MANIFEST.md` decodes as UTF-8 and
contains no CR bytes; `manifest.json` likewise.

## Findings

- **Five failures, one line.** The AST scan in the issue counts 222 unqualified
  text *writes*, which reads like a large sweep — but the entire observed
  Windows breakage came through one function, because `write_manifest` is on the
  delivery path every route ends at. Worth remembering before anyone budgets the
  full sweep as urgent: the remaining 221 are latent, this one was live.
- **This was a hard-rule violation, not just a test failure.** CLAUDE.md §1 rule
  1 says every route always *delivers* the built file. On Windows the manifest
  write raised inside the delivery step, so the job aborted and the user got a
  traceback instead of their `.rvt`. The status stamp is meant to be a label,
  never refusal logic — an encoding crash turned it into refusal by accident.
- `newline="\n"` was added alongside the encoding for the same reason it was
  needed in `schema_cache` (#27): these are artifacts a user may diff or a test
  may compare, and text mode silently rewrites them per platform.

## Open questions

- Stage 2 (`tools/dev/check_text_encoding.py`, in the shape of
  `check_portable_paths.py`) and stage 3 (sweep the remaining sites) are still
  open on #29. The guard cannot be wired into CI until the sweep is done, since
  it would fail on all 415 current sites.
- With this branch, `windows-latest` becomes a viable CI job — the shard is green
  on Windows for the first time. That is the follow-up recorded in
  `docs/inbox/ci-v1.md`, and it is what would stop this class of bug recurring.

## BRANCH STATE

- Branch: `ckaragitz12/29-utf8-text-io`, **stacked on
  `ckaragitz12/37-sync-plugin-zip-stdlib`** (PR #39), which is itself stacked on
  `ckaragitz12/27-gitattributes-eol` (PR #38). The stack exists because
  verifying this on Windows requires a working `tools/sync_plugin.py` to refresh
  the `plugin/lib/` mirror the cold-start tests execute. **Retarget to `main`
  once #38 and #39 have merged.**
- Files written:
  - `src/rvt/frontdoor/manifest.py` (one call site, two opens)
  - `plugin/lib/src/rvt/frontdoor/manifest.py` (generated mirror, via `tools/sync_plugin.py`)
  - `docs/inbox/text-encoding-utf8.md` (this record)
- Gates: shard-equivalent 76 passed / 30 skipped / 0 failed on Windows;
  `sync_plugin.py --check` exit 0; portable-paths ok.
  `plugin/scripts/validate_plugin.py` still exits 1 on this branch — that is
  #26, fixed on PR #28, not in this stack.
- Staged vs shipped: shipped. No viewer certification claim.

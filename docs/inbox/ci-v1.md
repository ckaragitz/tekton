# ci-v1 — issue #2

## What was built

`.github/workflows/ci.yml`: on `pull_request` and pushes to `main`, two jobs
(`py3.11`, `py3.12`) on `ubuntu-latest`, each running, in order:

1. `tools/dev/check_portable_paths.py`
2. `tools/sync_plugin.py --check` (plugin drift guard)
3. `plugin/scripts/validate_plugin.py` (plugin structure)
4. the fast shard listed in `tests/ci_shard.txt`

`concurrency` cancels superseded runs per ref; `timeout-minutes: 20` caps a hung
job; `permissions: contents: read` — CI needs no write scope. `RVT_SKIP_LARGE=1`
is set job-wide.

The shard lives in `tests/ci_shard.txt` rather than inline in the YAML so it can
be edited without touching workflow syntax, and so the exclusion reasons live
next to the list.

## Evidence

Run: https://github.com/ckaragitz/tekton/actions/runs/31228936716 — **success**,
both jobs.

| step | py3.11 | py3.12 |
|---|---|---|
| Install package and test deps | 9s | 9s |
| Portable paths | 0s | 0s |
| Plugin drift guard | 0s | 0s |
| Plugin structure | 0s | 0s |
| Fast test shard | 10s | 11s |
| **job total** | **27s** | **29s** |

Step output:

```
ok: 2612 tracked paths are portable
  assertions passed: 23
  RESULT: PASS — plugin structure is valid
75 passed, 30 skipped in 10.51s      (py3.12; py3.11: 9.29s)
```

29s against the issue's <10 min target, so there is a lot of headroom to extend
the shard later.

Final shard (7 files): `test_frontdoor.py`, `test_versions.py`,
`test_steplite.py`, `test_plugin_sync.py`, `test_plugin_validate.py`,
`test_bootstrap.py`, `test_coldstart.py`.

## Findings

- **`tests/test_router.py` was pruned from the issue's starting list.** It is
  not green in a fresh clone, for two independent reasons:
  `test_e2e_prompt_to_rfa` reads `extracted/racbasicsampleproject/Formats__Latest.gz/000.bin`,
  which lives in a git-ignored owner-machine corpus, and the `spec -> ifc` cases
  need `ifcopenshell`, an optional dependency the CI install deliberately does
  not carry. `test_evidence_self_audit_is_clean` also failed locally
  ("stale/false evidence citations") and was not diagnosed — it is not a
  line-endings or platform artifact, so it is worth its own look.
- **The 30 skips are load-bearing, not noise.** They are the `samples/`-gated
  cases self-skipping exactly as CLAUDE.md §2 describes. CI asserts the
  no-corpus path stays green; it does not and cannot assert the corpus path.
- **CI green here is evidence for two Windows-only bug reports.** The drift
  guard passed in 0s on Linux while the same command fails on a Windows clone,
  which is the direct confirmation of #27 (no `.gitattributes`, `autocrlf=true`
  gives CRLF, byte-compare against LF-generated content can never match).
  Likewise `test_frontdoor.py`, `test_bootstrap.py` and `test_coldstart.py` are
  all in the shard and all pass on Linux, while the same three fail on Windows
  with `UnicodeEncodeError: charmap` — confirming #29 is a platform bug, not a
  logic bug.
- Consequence worth stating plainly: **this CI cannot catch #27 or #29.** It is
  Linux-only, and both bugs are invisible there. A Windows job would catch them
  but would be red until those issues land, so it is deliberately deferred —
  see Open questions.

## Open questions

- Add a `windows-latest` job once #27 and #29 are fixed. That is the only way
  the Windows contributor path stays green, and it is currently untested by CI.
- `pip` is uncached, costing ~9s per job. Not worth a lockfile yet at a 29s
  total; revisit if the shard grows.
- Re-add `tests/test_router.py` when the two blockers above are addressed
  (either by installing `ifcopenshell` in CI and deselecting the corpus case, or
  by making that case self-skip when `extracted/` is absent, which is how the
  rest of the suite already behaves).

## BRANCH STATE

- Branch: `ckaragitz12/2-ci-v1`, **stacked on `ckaragitz12/26-validate-plugin-nonskill-dirs`** (PR #28).
  CI cannot be green without that fix — `plugin/scripts/validate_plugin.py`
  exits 1 on any clean checkout of `main` today. **Retarget this PR to `main`
  after #28 merges.**
- Files written:
  - `.github/workflows/ci.yml` (new)
  - `tests/ci_shard.txt` (new)
  - `CLAUDE.md` — §4 CI bullet only (hot file; 3 lines → 7, naming the real jobs)
  - `docs/inbox/ci-v1.md` (this record)
- Gates: run 31228936716 green on py3.11 and py3.12; 75 passed / 30 skipped.
- Staged vs shipped: shipped. No viewer certification claim.

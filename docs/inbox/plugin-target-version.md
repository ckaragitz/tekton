# plugin-target-version — bare `go author --target-version N` builds on the bundled Revit-N base (#92)

Stream: eng #92 (engineer session under the tech-lead session; branch
`cam/92-plugin-target-version`). Territory: `plugin/skills/_shared/tekton_env.py`
(hand-authored source), `plugin/skills/tekton-author/references/GENESIS-BASE.md`,
`tests/`. No hot file touched.

## 1. What was wrong (reproduced first, bare unzip + system python3)

Surface: `tekton-plugin.zip` built by `tools/sync_plugin.py` from `main@33622e3`,
unzipped into an empty temp dir, run with the VM's `/usr/local/bin/python3`
(3.11.15, **no `olefile`, no `numpy`** — a genuinely bare interpreter), every
`RVT_*` / `PYTHONPATH` / `TEKTON_ROOT` variable unset:

```
python3 skills/tekton-author/scripts/_bootstrap.py go author \
    --prompt "an electrical room with 6 panels" --target-version 2025 --out out/j25 --json
```

| | before the fix |
|---|---|
| `go.ready` / exit | READY / 0 (20.6 s wall) |
| `manifest.target_version` | `requested 2025, status **fallback**, output_release **2026**` |
| `manifest.base` | `source **env**, G_ABPD.rvt` (the 2026 default) |
| `manifest.target_version.base_status` | `2025: certified true, id G_ABPD_2025` (bundled, sha-pinned — and ignored) |
| `rvt.versions.detect_release(out/j25/prompt_room.rvt)` | **2026** |

Root cause, exactly as the issue states: `ensure_engine()` in
`plugin/skills/_shared/tekton_env.py` did
`os.environ.setdefault("RVT_GENESIS_BASE", <plugin>/assets/genesis/G_ABPD.rvt)`.
`rvt.frontdoor.base.resolve_base(target_release=2025)` honours that variable
as the *user's* override **before** the per-release registry slot, sees a
2026 file, `require_release` raises, and `_resolve_base_and_version` — which
recognises the file as byte-identical to our pinned default — degrades
honestly to the 2026 base + fallback line + IFC addition. The deliverable
rule held (file delivered, honestly labelled), but a Revit-2025 field tester
got a file their Revit cannot open although the certified 2025 base was in
the zip. Only the `go`/`run` dispatch showed it: `author_standalone` driven
with a hand-made `PYTHONPATH` (build-2025's bare proof, `test_frontdoor_standalone`)
never set the variable.

The export was a bridge from before `GenesisPin.candidate_paths()` learned to
find `<RVT_PLUGIN_ROOT>/assets/genesis/<name>` and the package-relative
plugin root by itself (docs/inbox/plugin-packaging.md "Bridged today via
RVT_GENESIS_BASE"). It has been redundant since, and became harmful the day
per-release slots landed.

## 2. What changed

`plugin/skills/_shared/tekton_env.py` (source of truth; the four
`_bootstrap.py` shims are untouched and stay byte-identical):

- `ensure_engine()` no longer exports `RVT_GENESIS_BASE` at all. It still
  exports `RVT_PLUGIN_ROOT` + `PYTHONPATH`, from which the engine resolves
  `assets/genesis/G_ABPD.rvt` / `G_ABPD_2025.rvt` / `G_ABPD_2024.rvt`, each
  sha256-verified against `lib/src/rvt/frontdoor/assets/genesis_base.json`.
- New `_drop_bundled_base_env(root)` / `_is_bundled_default_base()`: an
  *inherited* `RVT_GENESIS_BASE` that IS our pinned default base — the
  bundled file itself (`samefile`) or a byte-identical copy (size == pin
  bytes, then sha256 == pin; e.g. a previous install dir a stale shell
  export still points at) — is removed from the process environment before
  the engine runs. That value is what older bootstraps and the legacy
  `--env` lines exported, carries no user intent, and would re-introduce the
  bug; the identity test is the same one the engine uses
  (`_resolve_base_and_version`'s sha compare). Any other value (a firm's own
  base, or another file inside the bundle) is a real override and is left
  strictly alone; the engine keeps honouring it first and release-checks it
  against `--target-version`. Hot-path cost: zero filesystem calls when the
  variable is unset (preflight still 0.045 s bare); two stats + at most one
  581 KB sha256 when it is set.
- `_legacy_env_lines()` (`_bootstrap.py --env`) prints `PYTHONPATH` and
  `RVT_PLUGIN_ROOT` only.
- `plugin/skills/tekton-author/references/GENESIS-BASE.md` §4 no longer tells
  a skill session to export `RVT_GENESIS_BASE=<plugin>/assets/genesis/G_ABPD.rvt`;
  it documents the per-release bundled resolution instead.

Engine (`src/rvt/**`), `tools/`, SKILL.md files: unchanged →
`tools/sync_plugin.py --check` clean with zero files to sync.

## 3. Evidence (after the fix; same bare surface, fresh unzip of the rebuilt zip)

`go author --prompt "an electrical room with 6 panels" [--target-version Y] --out out/jY --json`,
system `python3`, no `RVT_*` in the environment:

| run | wall | `target_version` | `base.source` / file | `detect_release(output)` | in-job validate (release-aware) | `tools/rvt_validate.py` on `main` |
|---|---|---|---|---|---|---|
| `--target-version 2025` (cold, 1st process after unzip) | **22.15 s** | match / 2025 | pinned-bundled / `G_ABPD_2025.rvt` | **2025** | VALID, 0 errors, 1 warning | 1 error = `FOUR-REGISTRY INCOHERENCE 6/0/0/0` ¹ |
| `--target-version 2024` (cold) | 21.59 s | match / 2024 | pinned-bundled / `G_ABPD_2024.rvt` | **2024** | VALID, 0 errors, 1 warning | 1 error, same ¹ |
| `--target-version 2025` (warm, 2nd run) | **21.76 s** | match / 2025 | pinned-bundled / `G_ABPD_2025.rvt` | 2025 | VALID, 0 errors | — |
| no `--target-version` | 20.65 s | unspecified / 2026 | pinned-bundled / `G_ABPD.rvt` | 2026 (unchanged) | VALID, 0 errors, 2 warnings | VALID (no errors), 1 warning |
| `--target-version 2026` | 19.90 s | match / 2026 | pinned-bundled / `G_ABPD.rvt` | 2026 (unchanged) | VALID, 0 errors, 2 warnings | VALID (no errors), 1 warning |

¹ Pre-existing and not caused here: `main`'s standalone validator false-fires
the four-registry law on every non-2026 file with loaded content (it reads
the Global stream with 2026 tokens). PR #91 (issue #14) carries the
release-aware fix; verified in this session by running **#91's**
`tools/rvt_validate.py` (worktree at `origin/cam/14-famload-2025-lane@8137be1`)
on the very same three files → `VALID (no errors); warnings=0` for j2025 and
j2024, `VALID (no errors); warnings=1` for the default. So under the
validator that understands their release, all outputs are 0 errors; on
today's `main` the 2025/2024 ones show exactly the one known false positive.

**Latency (steer #108).** Cold vs warm is flat (22.2 s vs 21.8 s): there is
no cross-process warm cache on this path; preflight is 0.04 s, the rest is
the job. Wall time scales with the number of families the prompt implies —
the 6-panel prompt runs 6 sequential load stages (`_stages/stage_L1..L6`,
~2.5 s each) + walls; the 1-panel prompt the regression test uses builds in
~6 s on the same interpreter. Per-release cost is identical (2024/2025/2026
within 2 s of each other). Filed as an observation for the latency stream,
not acted on here.

## 4. Regression test (in the CI shard)

`tests/test_go_target_version.py` — bare-surface style (plugin trees copied to
a temp dir, `python -I -S`, all `RVT_*` scrubbed), sample-free, 9 tests / ~13 s:

- `go author --handoff-only --target-version {2025,2024,2026}` → `status
  match`, `output_release == year`, `base.source` starts with `pinned` (never
  `env`), base file is `G_ABPD[_year].rvt` inside the copy, certified.
- no `--target-version` → `unspecified` / 2026 / `G_ABPD.rvt` (default unchanged).
- inherited stale `RVT_GENESIS_BASE` = the bundled `G_ABPD.rvt`, and = a
  byte-identical copy in another dir, + `--target-version 2025` → still
  native 2025 (the default-base pointer is dropped).
- a user's own base outside the plugin via `RVT_GENESIS_BASE` +
  `--target-version 2025` → `base.source == "env"`, honoured.
- full bare build for 2025 and 2024 → combined `.rvt` exists, in-job
  validation has no non-numpy error, and `rvt.versions.detect_release` on
  the file == the target year.

Shown red first: with the pre-fix `tekton_env.py` stashed back in, the
resolution tests fail (`base.source == "env"`, `status fallback`); with the
fix all pass. `tests/test_bootstrap.py::test_legacy_env_exports_still_printed`
now asserts `--env` no longer prints the variable.

`/simplify` pass (4 review agents) applied before commit: identity test
broadened from inode-only to the engine's byte identity (covers upgraders),
docstrings trimmed to the file's density, a test duplicating the
`test_bootstrap.py` `--env` assertion dropped, release read back in-process
instead of a second subprocess. Skipped with reason: hoisting the
bare-plugin test harness (`_copy_plugin`/`_run`, now in three test files)
into a shared fixture — pre-existing pattern, out of this diff's scope, filed
as a chore; dropping the 2024 full build from the shard to save ~6 s — kept,
it is the issue's DONE ("same for 2024") and the only bare `go` 2024 build in CI.

## 5. Gates run

- `tools/sync_plugin.py` → synced 0 files, deny-audit clean, validation
  passed, zip rebuilt (4975 KB); `--check` clean.
- `plugin/scripts/validate_plugin.py` → PASS (23 assertions).
- `tools/dev/check_portable_paths.py` → ok (2665 tracked paths + the new test file name is portable).
- `tests/test_plugin_sync.py tests/test_bootstrap.py tests/test_coldstart.py
  tests/test_go_target_version.py tests/test_surface_perf.py tests/test_frontdoor.py`
  → **62 passed / 8 skipped** (25 s).
- CI shard exactly as CI runs it (`RVT_SKIP_LARGE=1 pytest $(grep -vE '^\s*(#|$)' tests/ci_shard.txt) -q`)
  → **180 passed / 23 skipped in 65 s** (the new file adds ~13 s).
- `/verify` (plugin surface): final zip re-unzipped bare, system `python3`:
  preflight `READY … 0.045s`; `go author … --target-version 2025` → match /
  2025 / `G_ABPD_2025.rvt`, `detect_release` 2025 (22.9 s); with a stale
  `RVT_GENESIS_BASE=<unzip>/assets/genesis/G_ABPD.rvt` in the environment and
  `--target-version 2024` → match / 2024 / `G_ABPD_2024.rvt`, `detect_release`
  2024 (21.8 s). `tools/surface_bench.py --zip tekton-plugin.zip`: session
  totals cowork 17.0 s / 8 calls, codeexec 15.2 s / 8 calls, local 45.7 s;
  `go-author-prompt` 5.9 / 5.7 / 5.4 s, preflight 0.1 s everywhere; the only
  non-PASS is `author-ifc` on the two bare surfaces = the documented honest
  degrade "numpy is required here (IFC placement) … doctor --install" because
  this VM's `/usr/bin/python3` ships without numpy — unrelated to this change.
- Full suite NOT run (SUITE-COORDINATION).

## 6. Findings / follow-ups (filed as issues, not fixed here)

- Engine-side belt and braces, **not** in the hot file: the existing special
  case in `src/rvt/frontdoor/__init__.py::_resolve_base_and_version`
  (≈lines 232-253) already sha-identifies "the env/--base file is our own
  pinned default arriving via a path" — and then chooses the 2026 *fallback*.
  With a certified slot for the target it should instead re-resolve ignoring
  that non-override (`resolve_base(None, target_release=target)`) and build
  natively; only a genuinely pending target falls back. The plugin no longer
  creates the situation, but a user who kept the old `--env` lines in a shell
  profile and drives `tools/frontdoor.py` directly still would. Filed with
  `Refs #92` (the altitude reviewer's point: fix the branch that exists two
  frames up rather than add a third identity rule to `base.py`).
- Latency observation above (per-family sequential load stages dominate
  prompt-only wall time; no warm-start benefit across processes) — filed for
  the latency stream with the measured numbers, `Refs #92`.
- Chore: the bare-plugin test harness (`BARE_PY`, `_copy_plugin`,
  `plugin_copy`/`workdir`, `_bootstrap`, `_run`) now lives verbatim in
  `test_bootstrap.py`, `test_coldstart.py` and `test_go_target_version.py`;
  hoist into one shared module/fixture. Filed `Refs #92`.

## BRANCH STATE

- Branch: `cam/92-plugin-target-version` from `main@33622e3`.
- Files written: `plugin/skills/_shared/tekton_env.py`,
  `plugin/skills/tekton-author/references/GENESIS-BASE.md`,
  `tests/test_go_target_version.py` (new), `tests/test_bootstrap.py`,
  `tests/ci_shard.txt`, `docs/inbox/plugin-target-version.md` (this record).
- Gates: §5, all green. Nothing staged for the viewer (no certification claim;
  the bases used are the already-certified bundled G_ABPD_2025 / _2024).
- Shipped vs staged: shipped = the bootstrap change (takes effect in the next
  `tekton-plugin.zip` build; the zip is git-ignored and regenerated by
  `tools/sync_plugin.py`).
- Overlap: PR #91 also appends to `tests/ci_shard.txt`; trivial rebase either way.

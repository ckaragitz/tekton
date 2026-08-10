# inbox — release-ctx-perf (`release_ctx` stops calling `Schema.stats()` on the hot path, issue #428)

## eng #428 — 2026-08-10

Stream: `eng428` (engineer session under the tech-lead session; branch
`cam/428-release-ctx-stats` from `main @ f05db8b`). Closes #428; Refs #266
(whose cProfile found it), #110, #108 / S-2026-08-09-g (latency is only
"done" with a measured before/after from a bare surface).
Territory: `src/rvt/frontdoor/release_ctx.py` only (+ its byte-identical
mirror `plugin/lib/src/rvt/frontdoor/release_ctx.py` written by
`tools/sync_plugin.py`), this record. No hot file, no test file, no shard
change.

### 1. What was built

`src/rvt/frontdoor/release_ctx.py` read the parsed schema's digest as
`schema.stats()["sha256"]` in four places — `_codec_triple_from_base` (the
release-pin check every context entry runs), the standalone
`SA._SCHEMA_STATE` seed (twice: `stats()["sha256"]` and
`stats().get("bytes", 0)`), and the yielded `info["schema_sha256"]`.
`Schema.stats()` is the analyzer's whole-class-tree statistics pass
(inheritance depth of all 4,600 classes, field counts, descriptor
histogram, `most_common(20)` of type refs …) and merely *echoes*
`self.sha256` / `self.total_size`, which `schema.parse_uncached` and the
`schema_cache` loader both set on every `Schema` they hand out. The four
reads are now the plain attributes:

| line | before | after |
|---|---|---|
| `_codec_triple_from_base` | `got = schema.stats()["sha256"]` | `got = schema.sha256` |
| `_SCHEMA_STATE["sha256"]` | `schema.stats()["sha256"]` | `schema.sha256` |
| `_SCHEMA_STATE["bytes"]` | `schema.stats().get("bytes", 0)` | `schema.total_size` |
| `info["schema_sha256"]` | `schema.stats()["sha256"]` | `schema.sha256` |

`git grep -n "stats()" src/rvt/frontdoor` → nothing (was 4 hits, all in
`release_ctx.py`).

One deliberate internal difference, invisible in every product output: the
`stats()` dict never had a `"bytes"` key (its size field is `"stream_size"`),
so inside a 2025/2024 context `SA._SCHEMA_STATE["bytes"]` used to read **0**;
it now carries the real inflated `Formats/Latest` length — exactly what
`standalone.bundled_schema()` records on the native path (`len(blob)` ==
`Schema.total_size`). The only readers of that key are `install_schema()`'s
report field `schema_bytes` (printed by `standalone.py`'s `__main__` only;
`add_to_project.ensure_target_schema` keeps just the sha) and its cache-file
size check, which the context's `"installed": True` early-return never
reaches. The manifests / `go` JSON below confirm nothing surfaced.

### 2. Evidence

Host: this cloud VM (4 vCPU), `python3` 3.11.15 (system, no numpy) and the
uv-built `.venv` (3.11, numpy) — both read the same. "before" = `main @
f05db8b`, "after" = this branch; plugin trees = `tekton-plugin.zip` built by
`tools/sync_plugin.py` from each, unzipped to a temp path with a space in
it, run with `env -i` + dead proxies.

**Behaviour identical.** The 2025 set-level edit (`GEN B1 - Basement`, id
1351691, → 5 ft) of the bundled `G_ABPD_2025.rvt`, three doors, before vs
after:

| door | output `.rvt` | JSON / manifest diff (`json.tool --sort-keys`, tree paths normalised) |
|---|---|---|
| bare unzip `go edit … set-level --id 1351691 --elevation-ft 5` | `cmp`: byte-identical (598,016 B) | only `go.job_seconds` 0.76→0.757, `preflight_seconds` 0.041→0.042 (+ the same number inside `preflight_line`), `go.seconds` 0.846→0.844, `result.seconds` 0.454→0.464 |
| bare unzip `go rvt_job.py edit … --ops '{"ops":[{"op":"set-level","id":1351691,"elevation_ft":5}]}'` | byte-identical | `go_job.json`: `job_seconds`, `preflight_seconds`(+line), `seconds`, `generated_at`; **`edited.rvt.manifest.json`: one line, `generated_at`** |
| repo `.venv/bin/python tools/rvt_edit.py … set-level … --json` | byte-identical | `seconds` 0.462→0.434 only |
| both `edited.rvt.validation.json` | — | only the `timings` block (`consistency`/`semantic`/`structure`/`total`, ±0.005 s) |

(Those were the first run of each tree, i.e. cold `.pyc`; the timing fields
there are not the measurement — §"Latency" is.) `rvt_validate` on every
output: 0 errors, 0 warnings (the gate inside each call).

**Latency — in-process (the DONE's primary number).**
`enter_host_release(<bundled G_ABPD_2025.rvt>)` = enter + exit of
`host_release_context`, one warm-up call (pays the once-per-process schema
materialisation), then 15 timed iterations, three repeats per interpreter
(`bench_ctx.py`, scratch, not committed):

| interpreter | before: median enter (min–max), 3 repeats | after | Δ median |
|---|---|---|---|
| `.venv` python 3.11 | 17.6 / 16.1 / 17.4 ms (15.9–20.2) | 1.87 / 2.02 / 1.86 ms (1.6–2.8) | **≈ −15 ms** |
| system `python3` 3.11.15 (+ vendored olefile) | 18.2 / 21.6 / 17.4 ms (16.3–23.4) | 2.03 / 1.82 / 1.88 ms (1.6–2.5) | **≈ −16 ms** |
| warm-up (first, cold) call, same runs | 145–160 ms (one 311 outlier) | 130–132 ms | ≈ −15…−25 ms |

`Schema.stats()` alone on that schema (4,600 classes), median of 20: **3.7–3.8
ms** on this VM (the issue's VM read ~6 ms un-profiled) — so 4 × 3.7 ≈ 15 ms
is the whole warm entry cost that disappeared; what is left (~1.9 ms) is
`detect_release` + the bundled-base resolve + the swaps. The issue's "≈ −25
ms" expectation was 4 × its own 6 ms reading; same mechanism, slower host.

**Latency — bare unzip, whole `go edit` call, system python3, alternating
before/after, 11 runs per tree per repeat, first of each discarded** (`wall.sh`,
scratch; wall = `date +%s.%N` around the process; `go.seconds` = the
bootstrap's own in-process total; `result.seconds` = `rvt_edit.py`'s
stopwatch, which starts *after* `enter_host_release` and therefore cannot
see this change — it is the control column):

| repeat | tree | wall median (min) | `go.seconds` median (min) | `result.seconds` median (min) |
|---|---|---|---|---|
| 1 | before | 0.646 s (0.626) | 0.575 (0.555) | 0.429 (0.411) |
| 1 | after | **0.633 s** (0.610) | **0.556** (0.541) | 0.427 (0.416) |
| 2 | before | 0.652 s (0.618) | 0.579 (0.551) | 0.433 (0.414) |
| 2 | after | **0.635 s** (0.620) | **0.562** (0.550) | 0.429 (0.420) |

Runs (wall, s) — r1 before 0.64 0.63 0.72 0.72 0.65 0.69 0.64 0.63 0.65 0.64,
after 0.63 0.62 0.85 0.68 0.62 0.61 0.62 0.64 0.64 0.64; r2 before 0.65 0.66
0.67 0.64 0.65 0.62 0.69 0.63 0.63 0.68, after 0.65 0.65 0.67 0.63 0.63 0.62
0.67 0.64 0.64 0.63. Honest reading: wall and `go.seconds` medians and minima
all move by −13…−19 ms in both repeats, the control column does not move,
and that matches the in-process −15 ms — but single runs spread 0.61–0.85 s,
so any one before/after pair can read either way; the in-process table is
the evidence, the wall table is consistent with it rather than proof on its
own. ≈ 2–3 % of a `go edit` on the 600 KB base; the same 4 × `stats()` came
off every `author`/`edit`/load lane that enters a 2025/2024 context
(`release_build_context` shares `_codec_triple_from_base` and the state seed).

**Gates** (final head, `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest … -q -rs
-p no:cacheprovider`): see BRANCH STATE.

### 3. Findings / follow-ups

* `Schema.stats()` keeps its analyzer/CLI callers (`schema.py` `main`,
  `versions/__init__.py` describe, `parity.py`, `tools/*` reports) where a
  statistics pass is the point; no other `src/rvt/frontdoor` or edit-lane
  caller used it for a scalar. Two *load-once-per-release* siblings still
  do (`versions/_release_schema.py:83 verify_schema`, `genesis/port2023.py:312`)
  — hot-file / another campaign's territory, once per process, ~4 ms each:
  noted, not filed (below the bar for an issue on this evidence).
* Not done, out of territory: the remaining ~1.9 ms of a warm entry is
  `_bundled_base_of` → `resolve_base` (~0.9 ms, honours env at call time, so
  not memoised) + `V.detect_release` / the donor `BasicFileInfo` read (the
  container opened twice when donor == path, ~0.25 ms) — both needed, both
  sub-ms.
* **Pre-existing red test on `main`, reported where it belongs:**
  `tests/test_target2024.py::test_cli_flag_parses_2024` still expects
  argparse to reject `--target-version 2023`, but `tools/frontdoor.py` on
  `main @ f05db8b` already accepts any year (the CLI half of #172) →
  `DID NOT RAISE SystemExit`, with or without this change (verified by
  stashing it). Not in the CI shard, so invisible until #136 adds the file.
  Commented on #172 (its DONE is "never an argparse error"; the assertion
  flips there). Not touched here — outside `release_ctx.py`.

### BRANCH STATE

* Branch `cam/428-release-ctx-stats` from `main @ f05db8b`; PR: see the PR
  that closes #428.
* Files written: `src/rvt/frontdoor/release_ctx.py` (4 reads swapped, −4/+4
  lines), `plugin/lib/src/rvt/frontdoor/release_ctx.py` (sync mirror,
  byte-identical), `docs/inbox/release-ctx-perf.md` (this record, new).
  Nothing staged for the viewer; nothing shipped beyond the plugin mirror;
  no `.rvt`/`.rfa` committed (bench outputs live in the session scratch dir).
* Gates: stream-local `tests/test_edit_own_release.py tests/test_go_edit.py
  tests/test_target2025.py tests/test_target2024.py
  tests/test_router_load_release.py tests/test_router_release.py
  tests/test_verify_manipulated_release.py tests/test_validate_release.py
  tests/test_input_release.py tests/test_readers_own_release.py
  tests/test_gates_shared_walk.py tests/test_famload_2025.py
  tests/test_famdoc_scan_fp.py tests/test_famload_batch.py
  tests/test_genesis_identity.py` → **192 passed, 13 skipped (pinned/composed
  base or R5 ancestor absent — fresh clone), 1 failed =
  `test_target2024.py::test_cli_flag_parses_2024`, pre-existing on `main`
  and unrelated (§3; fails identically with this change stashed)**;
  bare-surface `tests/test_plugin_sync.py tests/test_bootstrap.py
  tests/test_coldstart.py tests/test_surface_perf.py` → **28 passed, 5
  skipped** (surface_perf: no bare python3 with numpy on this host); whole
  merged CI shard (`python3 tools/dev/shard_list.py --print`, 71 files) →
  **1494 passed, 134 skipped, 3 xfailed, 0 failed in 302 s**;
  `tools/sync_plugin.py` run → `--check`: plugin in sync with source
  (deny-audit clean, identity scan == allowlist, assets verified);
  `plugin/scripts/validate_plugin.py` → 25 assertions, RESULT: PASS;
  `tools/dev/check_portable_paths.py` → ok: 2897 tracked paths portable.
* `/simplify` ran (reuse / simplification / efficiency / altitude lenses):
  clean — the only edit it produced was dropping a stray blank line; the
  altitude lens confirmed every `Schema` producer (`parse_uncached`, the
  `schema_cache` loader; `versions`/`global_framing.schema_of` route through
  them) sets `.sha256`/`.total_size`, and that memoising `stats()` inside the
  shared, process-memoized `Schema` would be the wrong level. `/verify` ran:
  drove the three edit doors above (bare-unzip `go edit`, `go rvt_job.py
  edit --ops`, repo `rvt_edit.py --json`) on the after tree — READY, exit 0,
  both gates PASS, outputs byte-identical to main's — and the **build** lane
  through the same context (`tools/frontdoor.py author --prompt "an
  electrical room with 6 panels" --target-version 2025 --json` → `ok: true`,
  `release.resolution: match`, output 2025 on the pinned-bundled
  `G_ABPD_2025.rvt`, 6 `.rfa` generated + placed, `prompt_room.rvt` and a
  sampled `.rfa` validate VALID 0 errors / 0 warnings, stamped PROOF-ONLY and
  delivered, 5.5 s).

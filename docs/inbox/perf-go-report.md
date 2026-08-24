# perf-go-report — the ONE `--json` result carries a `report` block (issue #185)

Stream: plugin/skill-path latency, epic #110 / steer #108 (S-2026-08-09-g: tool round-trips and
token weight per skill flow are product performance). One PR; single-file record.

## Why

`tekton-author`'s "Step 2 — report" needs, after the hand-over: the PROOF-ONLY stamps, every
degradation, the validator summary, and (when asked) the counts. #24 had already put `release` +
`stamps` into `AuthorResult.as_json()`; the degradations, the validator summary and the counts still
lived only in `manifest.json` / `MANIFEST.md`, i.e. a **second tool call** reading 9–225 KB on every
job. Hard rule 1 is untouched: stamps and degradations stay *labels* on delivered files; the block
only relays them in the same JSON that already names the files.

## What was built

* `rvt.frontdoor.manifest.report_block(degradations=, validation=, counts=)` → `{degradations,
  validation{verdict, errors, warnings, self_checks_ok, files}, counts{families, walls,
  equipment_instances, wiring_devices, loaded_families, elements_created, circuits, edited, deleted}}`.
  Each manifest builder assembles it from what it natively holds and stores it as
  **`manifest["report"]`** (so `manifest.json` carries the same block and nothing sniffs manifest
  shapes): `build_manifest` rolls `build.validation[role].validate` up over every emitted file (any
  non-VALID verdict wins; errors/warnings summed) and tallies `elements_created` + `circuits_built`;
  `edit_manifest` says the job runner's validation gate (PASS/FAIL/SKIPPED) in the same words and
  counts the edited/deleted/created id lists. Degradations ride by ONE budget rule (`_budgeted`: order
  kept, duplicates dropped, each whole up to 500 chars by `rvt._clause.clip` — the longest real one is
  401 — and the list capped at `REPORT_DEGRADATIONS_CAP = 10` with a "+N more, see MANIFEST.md" tail).
  `report_block()` with no arguments is the empty-but-present block (same keys, zero counts, verdict
  `NOT-RUN`).
* `AuthorResult.as_json()` relays `manifest["report"]` (or the empty block) as `result.report`, and
  `stamps` is now present (`[]`) even on a result with no manifest; `release` unchanged. The stamps
  and the target-version line keep their #24 homes (`result.stamps`, `result.release.line`) and are
  **not** repeated inside `report` — see "DONE amended" below.
* `created_counts(rows)` — ONE tally of `build.elements_created` by kind; `MANIFEST.md`'s "created:"
  line counts through it (output unchanged); `_rollup_status` and the report share `_self_checks_ok`.
* No change to `tools/frontdoor.py` (hot; it prints `as_json()`), `tools/route.py` or the plugin
  bootstrap: `frontdoor --json`, `route run --json` (via the author result) and `go author|edit`
  (`result.report`) all carry the block as is.
* `tests/test_go_report_185.py` (+ `tests/ci_shard.d/185-go-report.txt`): assembly rules, both
  validation roll-ups, the MANIFEST.md line through the shared tally, `as_json` without a manifest,
  and end to end on the bundled base: the 6-panel flagship (keys, numbers equal to the manifest's,
  `manifest.json["report"] == result.report`, whole result ≤ 4,096 B **in the CLI's `indent=1` form
  with the handoff on**), an edit of that output, and a FAILED IFC intake.

**DONE amended (tech-lead call, stated on the issue):** #185 was written before #24 landed
`result.stamps` / `result.release.line`. Repeating both inside `report` measured +179 B on the
default job and +510 B (12 % of the 4 KB budget) on the 2019-fallback job, for zero information; so
DONE (1)'s key list becomes `report ⊇ {counts, degradations, validation}` with stamps and the line
read from their existing keys (both present on every route; `stamps` now also on manifest-less
results). DONE (2)–(4) unchanged and met.

## Evidence (2026-08-24, Python 3.11.15, fresh cloud clone: no `samples/`, no specimens)

### (a) repo, `tools/frontdoor.py author … --json` — stdout as printed (`indent=1`)

| job | stdout before | stdout after | `report` (compact) | `manifest.json` | `MANIFEST.md` |
|---|---|---|---|---|---|
| `--prompt "an electrical room with 6 panels"` | 1,899 B | 2,255 B | 294 B | 151,481 B | 11,117 B |
| `--prompt "create an eaton panel for me with 6 switches"` | 1,899 B | 2,254 B | 293 B | 45,208 B | 8,731 B |
| `--ifc plugin/skills/tekton-author/examples/electrical-room-2500a.ifc` | — | 3,455 B | 1,871 B (5 degradations, 259–401 chars, all whole) | 226,516 B | 14,313 B |
| `--rvt <6-panel output> --edit "move PP-1 to 3,1,0"` | — | 1,453 B | 293 B (`edited: 1`, VALID 0 err / 1 warn) | 11,219 B | 4,262 B |
| `--prompt … --target-version 2019` (fallback line, 304 chars, said once in `release.line`) | — | 2,529 B | 294 B | 153,411 B | 11,827 B |
| `--rvt … --edit "teleport the moon"` (FAILED, rc 3) | — | 1,641 B | 296 B (all keys, `NOT-RUN`, zero counts) | 7,089 B | 2,020 B |
| `--ifc tests/conftest.py` (FAILED, rc 3) | — | 1,099 B | 296 B (same) | 5,584 B | 2,237 B |

Every run: `report` keys == `['counts', 'degradations', 'validation']`,
`manifest.json["report"] == result.report`; successful builds `validation = {verdict: VALID, errors: 0,
warnings: 1 (the known ES DataStorage decoder gap), self_checks_ok: true, files: 1}`. `MANIFEST.md` of
the 6-panel job before vs after: identical except the out-dir spelling and the `generated_at` stamp.
`manifest.json` grows by the block (≈ +0.3 KB, < 1 %).

### (b) bare surface — fresh unzip of `tekton-plugin.zip`, `/usr/bin/python3` (no numpy), `env -i`, proxies → dead port

`skills/tekton-author/scripts/_bootstrap.py go author --prompt P --out out/j1 --json` (ONE JSON on stdout):

| prompt | zip | rc / `go.ready` | wall (1 run) | stdout | `result` (compact) | `result.report` | manifest json / md |
|---|---|---|---|---|---|---|---|
| eaton panel, 6 switches | main `1cee4c4` | 0 / True | 2.98 s | 3,085 B | 2,608 B | absent | 48,212 / 9,436 B |
| eaton panel, 6 switches | this branch | 0 / True | 3.02 s | 3,460 B | 2,903 B | 293 B | — |
| electrical room, 6 panels | main `1cee4c4` | 0 / True | 6.14 s | 3,084 B | 2,608 B | absent | 159,383 / 11,822 B |
| electrical room, 6 panels | this branch | 0 / True | 5.66 s | 3,461 B | 2,904 B | 294 B | — |

DONE (1) literally: `… go author --prompt 'create an eaton panel for me with 6 switches' --json | python3 -c
'…["result"]["report"]; print(sorted(r))'` → `['counts', 'degradations', 'validation']` (`result.stamps`: 2).
DONE (2): `result` 2,904 B ≤ 4,096 on the bare surface; the test pins the in-process CLI form (≈ 2.3–3.0 KB).
Wall time unchanged within single-run noise (the block is a dict walk over the in-memory manifest).

**The saving, per job:** the follow-up read for degradations / validator summary / counts was
`MANIFEST.md` (9–14 KB ≈ 2.5–3.5 k tokens) or `manifest.json` (45–225 KB ≈ 12–60 k tokens) plus one
tool round-trip; it is now +0.3–0.4 KB (≈ 100 tokens) inside the JSON the surface already holds.

### (c) gates run

* `tests/test_go_report_185.py`: 12 passed (≈ 6 s). Negative control of the first draft against
  `origin/main`'s sources failed at the first test (report API absent) — the module tests the change.
* neighbours (after the final shape): see the PR body for the exact counts of
  `tests/test_frontdoor.py test_frontdoor_json_strict.py test_frontdoor_manifest_pin.py test_frontdoor_209.py
  test_go_edit.py test_status_gate.py test_records_layout.py` and
  `tests/test_target_version_first.py test_coldstart.py test_go_target_version.py test_plugin_sync.py test_bootstrap.py`.
* `tools/sync_plugin.py` (zip rebuilt, deny-audit clean, identity scan == allowlist) → `--check` in sync;
  `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py` ok.
* `/simplify` pass (reuse / simplification / efficiency / altitude reviewers) applied: block born in the
  builders instead of sniffed from the finished dict, no duplicated stamps/line, one budget rule for
  degradations, shared `_self_checks_ok`, MANIFEST.md tally fully migrated, tests measure the shipped form.

## Findings

1. **Router relay is the next notch (follow-up filed).** `route run --json` re-summarises author
   results in `router._absorb_author_result` / `_absorb_build_degradations` (own cap-10 rule, reads
   `build.degradations` only — so the `rvt-read + rvt-edit` cell's `edit.degradations` never reach
   `route run --json` today). Now that every manifest carries `report`, the router can read it
   shape-blind and share `REPORT_DEGRADATIONS_CAP`; RouteResult aggregates several author results per
   cell, so it needs its own small design — not in this S-sized PR.
2. ~1.3 KB of the bare result's 2.9 KB is absolute paths said several times (`out_dir`, `files`,
   `manifest.{json,md,build.log}`, `handoff.*`, `intent_json`). A very deep user directory can push the
   envelope past 4 KB on its own; relative-to-`out_dir` spellings would halve it but change a contract
   three skills read — noted for #110, not done here.
3. `tekton-author/SKILL.md` "Step 2 — report" item 4 still says counts come from `result.manifest.md`;
   pointing it (and `tekton-edit`'s report step) at `result.report` is a hot-file wording change,
   explicitly outside #185 — follow-up filed (Refs #185, #110).
4. The IFC example's five plan-note degradations (259–401 chars) share one boilerplate tail; if
   degradations grow a structured form (kind + subject + reason) the block should carry that instead of
   prose — its own stream, not needed for today's DONE.

## BRANCH STATE

* branch `cam/185-go-report` from `main` @ `1cee4c4`; files: `src/rvt/frontdoor/manifest.py`
  (`report_block`, `created_counts`, `_budgeted`, `_build_validation_summary`, `_edit_validation_summary`,
  `_self_checks_ok`; `build_manifest` / `edit_manifest` store `m["report"]`; md renderer uses the
  tally), `src/rvt/frontdoor/__init__.py` (`as_json`: `stamps` unconditional, `report` relayed), their
  `plugin/lib/` mirrors (sync), `tests/test_go_report_185.py`, `tests/ci_shard.d/185-go-report.txt`,
  this record.
* shipped in the PR: all of the above. Staged for a human: nothing (no viewer claim; no `.rvt`/`.rfa`
  byte changes — `report` is JSON about files; the validator says what it said).
* not touched: `tools/frontdoor.py`, `plugin/skills/*/SKILL.md`, `src/rvt/frontdoor/base.py`,
  `src/rvt/frontdoor/router.py`.

# perf-bench-reason — a non-PASS bench job's `reason` quotes the job's own verdict (#287)

Stream: eng #287 (engineer session started by the tech-lead session), 2026-08-10.
Refs #110 (latency epic — `tools/surface_bench.py` is the instrument every latency change is judged
by), #183 (where the `author --ifc failed: }` line was first noticed), #127 (the numpy question itself),
#221 (what PASS/FAIL *means* — untouched here).

## What was built

- `tools/surface_bench.py`: `_tail(inv)` → `_why(inv)`. Order of preference for the ≤ 200-char
  reason: the parsed `--json` result's own verdict — front door `errors[0]` → `error` → `status` →
  `gates.line`; `go` envelope: the same keys on `result`, then `go.exception`, then the preflight line
  when `go.ready` is false and the job never ran; plain preflight JSON: its `line` — then the last
  non-empty **stderr** line, then the last **stdout** line that is not bare JSON punctuation
  (`{}[],`), then `exit N`. The JSON is re-read from `inv.stdout`, so every call site is the uniform
  `_why(inv)`. Multi-line messages are collapsed to one line (the markdown table's "Non-PASS
  detail" is one bullet per job). `go edit not ok` drops its hand-rolled
  `error or gates.line or _tail` chain because `_why` now does exactly that.
- `tests/test_surface_bench_reason.py` (9 tests, 0.07 s, no plugin build, no bare interpreter) +
  drop-in `tests/ci_shard.d/287-bench-fail-reason.txt`. DONE 2 verbatim (pretty-printed
  `{"ok": false, "status": "FAILED (X)", "errors": ["X: detail"]}`, exit 3 → reason contains
  `X: detail`, never `}`), the `go` envelope shapes (edit door error / gates line, front door inside,
  preflight NOT READY), the three fallbacks, and the 200-char one-line cap.
- Nothing under `src/`, `plugin/`, `skills/`; `surface_bench.py` is not mirrored into the plugin
  (`sync_plugin.py --check`: in sync).

## Evidence (this cloud VM, system `/usr/bin/python3` 3.11.15 **without numpy**, `--zip tekton-plugin.zip --surfaces cowork,codeexec`, all 8 jobs)

Before (`out/bench-before.json`, main@b169376):

```
Non-PASS detail:
- cowork / author-ifc: FAIL -- author --ifc failed: }
- codeexec / author-ifc: FAIL -- author --ifc failed: }
```
`jobs[author-ifc] = {"status": "FAIL", "reason": "author --ifc failed: }", invocations[0].exit == 3, stderr_tail == ""}`

After (`out/bench-after.json`, this branch):

```
Non-PASS detail:
- cowork / author-ifc: FAIL -- author --ifc failed: IFC intent failed: ImportError: numpy is required here (IFC placement / geometry resolution) but is not installed: No module named 'numpy'. One-time fix: python -m pip install numpy (or run the skill'
- codeexec / author-ifc: FAIL -- author --ifc failed: IFC intent failed: ImportError: numpy is required here (IFC placement / geometry resolution) but is not installed: No module named 'numpy'. One-time fix: python -m pip install numpy (or run the skill'
```
`jobs[author-ifc].reason` = the job's own `errors[0]`, quoted part exactly 200 chars (as before: prefix +
capped tail). A field-by-field diff of both reports minus `seconds` / `extract_seconds` /
`invocations[*].seconds` / `breakdown`: **the two `author-ifc` reasons are the only difference** — all
16 job statuses identical (14 PASS, 2 FAIL), same labels, same exit codes, same shell-call counts
(10 per surface). PASS/FAIL semantics unchanged.

## Gates run

- `RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_surface_bench_reason.py tests/test_surface_perf.py -q -rs` → 9 passed, 5 skipped (the perf gate self-skips: no bare python3 with numpy on this host — pre-existing, #127).
- `.venv/bin/python -m pytest tests/test_shard_list.py -q` → 23 passed (drop-in accepted; merged shard lists the new file).
- `.venv/bin/python tools/sync_plugin.py` then `--check` → in sync, deny-audit clean; `plugin/scripts/validate_plugin.py` → PASS (25 assertions); `python3 tools/dev/check_portable_paths.py` → ok.
- Full suite not run (SUITE-COORDINATION).

## Not done here (left in the queue)

- #391 (`go-ops` bench job) — a new canonical job with its own budget assertion and 3-run medians; not
  inside `_why` + its call sites, so it stays its own issue.

## BRANCH STATE

- Branch `cam/287-bench-fail-reason` from main@b169376.
- Files: `tools/surface_bench.py` (M), `tests/test_surface_bench_reason.py` (A),
  `tests/ci_shard.d/287-bench-fail-reason.txt` (A), `docs/inbox/perf-bench-reason.md` (A, this record).
- Staged vs shipped: nothing staged for the viewer (pure reporting fix in a dev tool); `out/bench-*.json`
  are local evidence, not committed.

# ORCHESTRATOR COORDINATION — genesis-2023 territory split (2026-08-04 ~23:20)

Binding for both 2023 streams; the reduce stream's claim is GRANTED.

- **genesis-2023-reduce OWNS**: src/rvt/versions/records32.py (the 32-bit
  record layer), src/rvt/versions/schema_2023.py, the KNOWN_RELEASES[2023]
  entry in src/rvt/versions/__init__.py, tools/genesis_2023.py,
  experiments/genesis2023/** (except miners/), tests/test_genesis_2023.py,
  docs/writer/format-2023.md, docs/inbox/genesis-2023-reduce.md.
- **genesis-2023-port OWNS**: src/rvt/genesis/port2023.py,
  tests/test_port2023.py, experiments/genesis2023/miners/**,
  docs/inbox/genesis-2023-port.md. Do NOT write any src/rvt/versions/ file —
  IMPORT the reduce stream's records32/schema_2023 layers when they land
  (poll for them); until then, work read-only against the samples using
  the reduce stream's published format facts below.
- samples/2023/SOURCES.md stays as written (content verified by reduce).

## The 2023 format delta (reduce's finding — build against THIS)
2023 element ids are 32-BIT (Identifier v1 m_id:i32; 2024+ = v2 i64).
Record framing headers 8/12 bytes (not 12/16); in-body ElementId = 4 bytes;
ElemTable rows 28 bytes, different field order; footer 19 bytes. Schema
grammar unchanged (parses to EOF; 4,418 classes, sha bce7907b...). Framing
ordinals resolve by name (BLOCK_TAG 0x0E4E ...). Read parity achieved:
rst 99.978 / rac 100 / rme 99.172 — same residual ES-blob gaps as 2024-2026.

## UPDATE (~23:30) — racing ladder runs resolved (BINDING)
Two concurrent ladder processes were writing experiments/genesis2023/reduce/
(whole-file writes => torn-file risk). Resolution, effective now:
- **port stream**: let your `ladder --stages R5` process FINISH (it carries
  the honest latest_dangling metric via the scan_stream_ids32 rebind), then
  launch NO further rung runs — experiments/genesis2023/reduce/ is reduce
  territory per this doc. Your parity/read-stack work is acknowledged DONE
  (all six samples VALID; table at experiments/genesis2023/parity_2023.md).
  Return to port2023.py + miners/ only.
- **reduce stream**: owns R6..R9, K3, K4, formats, stage from here.
- context_2023 now includes the RR.scan_stream_ids -> scan_stream_ids32
  rebind (the i64 scan silently zeroes latest_dangling on 2023 streams) —
  both streams must run inside context_2023 for ANY 2023 evidence metric.
- **reduce, for K3/K4 + staging**: reduction law as everywhere
  (assert_edit_free per rung, four-registry census); when staging the viewer
  batch, the untouched 2023 sample is the control AND the does-the-viewer-
  read-2023 probe — a control FAIL means 2023 certification moves to
  desktop-Revit verification (a finding, not a failure).

## FINAL WARNING to genesis-2023-port (~23:40, ORCHESTRATOR, BINDING)
Port ran a SECOND concurrent R6-R9 ladder despite the grant above. This is
the last instruction: **port makes NO further executions of
tools/genesis_2023.py (ladder / k3k4 / stage) under any flag.** The reduce
stream runs them exclusively. Port consumes the rung REPORTS
(experiments/genesis2023/reduce/*.json) READ-ONLY. Port's remaining
territory is EXACTLY: src/rvt/genesis/port2023.py, tests/test_port2023.py,
experiments/genesis2023/miners/**, docs/inbox/genesis-2023-port.md.
Reduce will re-verify every rung from disk in one process after k3k4 and
regenerate any torn file ALONE — port must not "help".

## PACKAGING CONFIRMATION (integrator, relayed ~00:00)
Your shippables are IN the plugin zip and verified: records32.py (30,665 B
incl. the verifier fixes), schema_2023.py, the versions/__init__ 2023 hooks.
ZERO sample binaries in the zip (no samples/ entries, no 2023 .rvt/.rfa —
the exclusion held). sync --check clean; 68/68 post-sync tests.

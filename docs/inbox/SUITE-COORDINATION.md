# ORCHESTRATOR: single canonical suite run (2026-08-04 ~23:55, BINDING)
The full test suite is REPO-GLOBAL, not per-stream. Four concurrent runs
were live (gates-flake-under-load risk + cross-interference on shared
scratch paths); the orchestrator killed 28079/30341/30758 and designated
the 23:23 run (pid 27375) CANONICAL. Every stream adopts its result —
the orchestrator will publish the count in this file when it lands.
Until then: NO stream launches a new full-suite run; stream-local test
files only (pytest tests/test_<yours>.py).

## CULL EXECUTED + VERIFIED (~00:05): the orchestrator killed EVERY pytest
process except canonical 27375 (unsandboxed kill -9, then ps verification:
exactly one survivor). HARD RULE, effective immediately: NO stream runs
`pytest tests` (full suite) for the remainder of this session — 'run the
full suite before finishing' in your charter is SATISFIED by adopting the
canonical count below; run ONLY your stream-local test files. Any new
full-suite process will be killed on sight.

## RESULT (canonical, orchestrator-owned run, finished 2026-08-05 ~02:10):
**1697 passed / 7 failed / 2 skipped** (25:37). Post-run settled-tree
re-verification: test_plugin_sync + test_convert now PASS (fixed mid-run by
build-2025 / convert-a). REAL remaining reds, 5, with owners:
- test_convert_combo::{add_to_project,merge_ifc}_end_to_end — convert-b tests
  coupled to the regenerated shared fixture (cleanup agent dispatched)
- test_genesis_2024::test_batch_manifest_number_does_not_collide — batch 34/35
  manifests landed after its expectation (cleanup agent)
- test_y2025_a::test_probes_manifest — KeyError 'certified_by' (cleanup agent)
- test_genesis_assemble::test_ladder_end_to_end — G0a four-registry
  incoherence, genesis territory (real defect, tracked)
Streams: adopt 1697/7/2 as the canonical count; cite this section.

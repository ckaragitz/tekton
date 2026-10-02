# Review nits from #967 (IFC pset drives) and #970 (perf gate)

Stream: param-drive (+ test-health). Refs #714 #965. Optional findings both reviews
left for "the next PR that touches these files", carried here in one small PR.

## What changed
- **A label the IFC states with conflicting values on one product stays a value.**
  `pset_params.collect()` used to drop the second value into `skipped` only, and the
  first drove the part. It now records `conflicting_values` on the label's source,
  and `pset_drive.plan()` reports the label as value-only ("the IFC states it with
  conflicting values …"). When the conflict spans several products, the owner count
  decides first ("attached to N products"). An equal repeat on one product is still
  one owner and still drives.
- **A pset linked by several `IfcRelDefinesByProperties` keeps every owner.** The
  schema forbids it (`DefinesOccurrence` is SET[0:1]); an exporter may not. The owner
  maps used to be overwritten per relation, so the last relation's product was
  driven alone. They now extend.
- **Docs:** the `pset_drive` module docstring states the unnamed-owner, contradicting-
  axis-word and conflicting-value refusals. The #714 record header names the shipped
  base. The perf-gate test comment table and the self-test docstring describe the
  three-times injection and its measured 33.6–37.4. The #965 record's earlier
  self-test bullet points to its amendment.

*Review of #972 (2026-10-02), 🛑 then fixed:* the multi-relation extension did not
dedupe, so one product linked by two relations counted as two owners and a correctly
driven parameter (BodyWidth on tank_shell) became value-only -- a regression against
main. Owners are now added once per IFC entity id. And float noise between repeats
(1574.8 vs 1574.80000001) was a "conflict"; `_same_value` now treats values equal to
1e-9 relative as one statement. Two more tests pin both (they fail at the first head).

## Evidence
- `tests/test_review_nits_967_970.py`: 5 tests. Against the unfixed modules, the two
  fix tests fail; the equal-repeat guard passes on both; the two #972-review tests
  fail against the PR's first head.
- The #714 fixture's 7 drives are unchanged (`test_pset_drive_714`, 32 passed).

## BRANCH STATE
- Files: `src/rvt/ifc/pset_params.py`, `src/rvt/ifc/pset_drive.py` (+ `plugin/lib`
  mirrors), `tests/test_surface_perf.py` (comments only),
  `tests/test_review_nits_967_970.py` (new), `tests/ci_shard.d/967-970-review-nits.txt`
  (new), `docs/inbox/param-drive.d/714-pset-drive.md` (header),
  `docs/inbox/test-health.d/965-perf-gate.md` (one bullet), this fragment.
- Gates: listed in the PR. Nothing staged; no Revit claim (hard rule 4).

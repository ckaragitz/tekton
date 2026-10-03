# #988: the ledger's stage_L8_lp4 entry says what verdict #25 left standing

Stream: perm-matrix. Issue #988 (follow-up to #984 / PR #989). Hot-file PR: one ledger entry.

## What changed
`docs/coverage/viewer-certified.json`, entry `experiments/ifc_room/stage_L8_lp4.rvt`, `proves`:
- **Was:** "family LOAD + instance PLACEMENT on the genesis base translate (PASS) — loader +
  creation path proven on the genesis lineage; …"
- **Now:** "family LOAD on the genesis base translates (PASS) — the 8 generated families loaded
  via the loader on the genesis lineage; NO instance was placed (all 8 stage load records
  instance_id -1) — verdicts #24/#25: placement on the genesis lineage unproven (#24), and
  this PASS an empty-design short-circuit (8 families + 0 walls + 0 instances, #25); …"
  (attribution made precise after the #991 review: #24 first called placement unproven; #25
  called this PASS an empty-design short-circuit).

No other entry changed; no file added or removed from the ledger. The PASS itself stands (the
viewer translated the file); only what it proves is narrowed to what verdict #25
(`docs/inbox/genesis-audit.md`, "ORCHESTRATOR VERDICTS #24" and "#25") left standing.
The #984 record's line saying the ledger "still reads 'family LOAD + instance PLACEMENT'" is
superseded by this fragment (fragments are never rewritten). The matrix
caveat (`matrix.STAGE_L8_EARLIER_FORM`, #989) already says the file has no placed instance, so
the two now agree.

## BRANCH STATE
- Files: `docs/coverage/viewer-certified.json` (one `proves` string), this fragment.
- Gates: listed in the PR. Nothing staged; no new viewer claim (hard rule 4).

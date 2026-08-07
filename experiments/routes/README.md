# experiments/routes — the permutation router's demonstrated routes

Produced by `tools/route.py` (the permutation router over
`src/rvt/frontdoor/{matrix,router}.py`; perm-matrix stream, 2026-08-04).
Each directory is one end-to-end delivery: the output file(s), every
intermediate artifact, and the route manifest (`route.json` + `ROUTE.md`
— cell, stages+timings, stamps, caveats after delivery, evidence cited).

| dir | route | what it proves | time |
|---|---|---|---|
| `demo1-prompt-to-rfa` | prompt → rfa | panel prompt → 2 generated `.rfa` (validator VALID family-mode, provenance ok) | 3.0 s |
| `demo2-spec-to-ifc` | spec → ifc | room-spec JSON → deterministic IFC4 (657 entities, 13 equipment) | 0.3 s |
| `demo3-prompt-via-ifc-rvt` | **chain** prompt → ifc → rvt | the handoff round trip in-process: prompt intent → our IFC → re-resolved by our own resolver → `.rvt` on the certified genesis base (open-bug stamp riding) | 23.0 s |
| `demo4-rfa-loaded-rvt` | **combination** rfa → loaded rvt | famspec `{"kind": "downlight"}` → our `.rfa` → the same document four-registry-LOADED into the loader-certified host; project validator 0 errors | 35.5 s |
| `demo5-prompt-rvt-edit` | **combination** prompt+rvt → rvt | edit sentence (move + cascade delete) through the certified edit pipeline on demo3's output; hard gates PASSED | 1.8 s |

Every output here is PROOF-ONLY, NOT-DELIVERABLE (TRACKER gates G2/G3);
none of these files carries a viewer-acceptance claim of its own — the
evidence lines in each `ROUTE.md` cite the certified ledger entries the
underlying stages rest on. Full table:
`docs/product/PERMUTATION-MATRIX.md`; live: `tools/route.py matrix`.

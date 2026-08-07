# Deliverable manifest — route `rvt`

**Status:** PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)
**Tool:** tekton frontdoor (rvt.frontdoor) v1.0.0 · 2026-08-05T04:18:47Z

## Input
- **rvt**: `/Users/ck/dev/things/tekton/experiments/routes/demo3-prompt-via-ifc-rvt/prompt_intent.rvt`
- **edit**: `move DP-1 to 3,1,4.66; delete LP-4 with cascade`
- **ops**: `[{"op": "move", "id": 1472947, "to": [3.0, 1.0, 4.66]}, {"op": "delete", "id": 1472952, "cascade": true}]`

## Edit
- delegated to: tools/rvt_job.py edit (rvt.manipulate ONE commit + rvt.mutate adds + structural / validation / identity / provenance gates)
- understood: `{"clause": "move DP-1 to 3,1,4.66", "op": {"op": "move", "id": 1472947, "to": [3.0, 1.0, 4.66]}}`
- understood: `{"clause": "delete LP-4 with cascade", "op": {"op": "delete", "id": 1472952, "cascade": true}}`
- job status: PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED) (hard gates passed: True)
  - gate `structural`: PASS
  - gate `validation`: PASS (errors 0, warnings 1)
  - gate `identity`: PASS
  - gate `base_provenance`: PROOF-ONLY, NOT-DELIVERABLE
- output: `experiments/routes/demo5-prompt-rvt-edit/prompt_intent.edited.rvt` (655360 bytes, sha256 `2e98d49f157e0ae2…`)
- edited [1472947] · deleted [1472952] · created []

## CRUD (the result stays editable)
- inspect: `python tools/rvt_edit.py experiments/routes/demo5-prompt-rvt-edit/prompt_intent.edited.rvt info`
- next edit: `python tools/frontdoor.py author --rvt experiments/routes/demo5-prompt-rvt-edit/prompt_intent.edited.rvt --edit "<sentence | ops.json | inline JSON>" --out <dir>`

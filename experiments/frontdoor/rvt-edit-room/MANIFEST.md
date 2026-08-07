# Deliverable manifest — route `rvt`

**Status:** PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)
**Tool:** tekton frontdoor (rvt.frontdoor) v1.0.0 · 2026-08-04T17:50:46Z

## Input
- **rvt**: `/Users/ck/dev/things/rev-revit/experiments/frontdoor/prompt-electrical-room/electrical_room_prompt.rvt`
- **edit**: `move DP-1 to 3,1,4.66; delete LP-4 with cascade; set level L1 - Ground Floor elevation to 0.5 ft`
- **ops**: `[{"op": "move", "id": 1472947, "to": [3.0, 1.0, 4.66]}, {"op": "delete", "id": 1472952, "cascade": true}, {"op": "set-level", "id": 311, "elevation_ft": 0.5}]`

## Edit
- delegated to: tools/rvt_job.py edit (rvt.manipulate ONE commit + rvt.mutate adds + structural / validation / identity / provenance gates)
- understood: `{"clause": "move DP-1 to 3,1,4.66", "op": {"op": "move", "id": 1472947, "to": [3.0, 1.0, 4.66]}}`
- understood: `{"clause": "delete LP-4 with cascade", "op": {"op": "delete", "id": 1472952, "cascade": true}}`
- understood: `{"clause": "set level L1 - Ground Floor elevation to 0.5 ft", "op": {"op": "set-level", "id": 311, "elevation_ft": 0.5}}`
- job status: PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED) (hard gates passed: True)
  - gate `structural`: PASS
  - gate `validation`: PASS (errors 0, warnings 1)
  - gate `identity`: PASS
  - gate `base_provenance`: PROOF-ONLY, NOT-DELIVERABLE
- output: `experiments/frontdoor/rvt-edit-room/electrical_room_prompt.edited.rvt` (655360 bytes, sha256 `4ae05a8a63c8046a…`)
- edited [1472947, 311] · deleted [1472952] · created []

## CRUD (the result stays editable)
- inspect: `python tools/rvt_edit.py experiments/frontdoor/rvt-edit-room/electrical_room_prompt.edited.rvt info`
- next edit: `python tools/frontdoor.py author --rvt experiments/frontdoor/rvt-edit-room/electrical_room_prompt.edited.rvt --edit "<sentence | ops.json | inline JSON>" --out <dir>`

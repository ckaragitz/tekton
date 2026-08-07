# prompt+rfa->rfa (rvt.convert.modify_family) -- deliverable manifest

## The deliverable(s)
* **rfa**: `experiments/convert_combo/C1_modify_own/dp1_eaton_prl2x_400a_42sp_480y_277.edited.rfa` (270,336 bytes, sha256 a21d0035061ef2bf...)

## Stamps (labels, not refusals)
* PROOF-ONLY, NOT-DELIVERABLE (P0: identity/counsel gates G2-G3 open; every tekton output is an internal proof)

## Edits applied
* {"op": "rename-type", "type_index": 0, "old": "400A MCB 42ckt", "name": "225A MCB 42ckt"}
* {"op": "set-param", "param_id": 1025, "caption": "BusRating", "carrier": "m_value", "value": 225.0, "raw": "225 A"}
* {"op": "set-param", "param_id": 1027, "caption": "MainsRating", "carrier": "m_value", "value": 225.0, "raw": "225"}
* {"op": "set-param", "param_id": 1021, "caption": "PanelName", "carrier": "m_str", "value": "DP-7", "raw": "DP-7"}

## Gates (self-checks)
* family-mode validator: VALID (0 errors, 0 warnings)
* release: 2026 (preserved=True)
* re-read rename-type: want='225A MCB 42ckt' got='225A MCB 42ckt' ok=True
* re-read set-param: want=225.0 got=225.0 ok=True
* re-read set-param: want=225.0 got=225.0 ok=True
* re-read set-param: want='DP-7' got='DP-7' ok=True


# prompt+rvt->rvt (rvt.convert.add_to_project) -- deliverable manifest

## The deliverable(s)
* **combined**: `experiments/convert_combo/A1_add_own/A1_lp_into_own.rvt` (675,840 bytes, sha256 f3eb3f5111815af6...)

## Stamps (labels, not refusals)
* PROOF-ONLY, NOT-DELIVERABLE (P0: identity/counsel gates G2-G3 open; every tekton output is an internal proof)

## Target
* file: `experiments/frontdoor/ifc-electrical-room-2500a/electrical-room-2500a.rvt` (Revit 2026, 4 walls, 8 instances, 8 family documents)
* release preserved: every output verified YES -- the output is a splice of the input, no version conversion
* placement level: id 311 at 0.0 ft ((nearest elevation 0))

## Placement
* rule: free floor space east of the target's content bbox (+1.0 m margin, y-centred)
* offset: {"dx_m": 5.6, "dy_m": 0.0, "equip_dz_m": 0.0, "equipment_translated": 1, "walls_translated": 0, "note": "clearance boxes / conduit runs (informational layers) are NOT translated; positions in the manifest are post-offset"}
* hosting: free-standing (certified shape); wall panels stand upright at panel height; FACE-HOSTING on the target's walls (H1 recipe) is the fidelity follow-up

## Created
* family(.rfa): tag=LP-1, name=Lighting Panelboard LP-1 480Y/277 100A MLO 42sp
* equipment-instance: tag=LP-1, elem_id=1473067
* loaded-family: tag=LP-1, symbol_id=1473065, family_id=1473049

## Gates (self-checks; viewer acceptance is a separate tier)
* combined: validator VALID (0 errors, 1 warnings); four-registry coherent=True; release 2026 (preserved=True)
* identity: the output keeps the TARGET's own identity block (BasicFileInfo / history): this route EDITS the user's file, it does not re-author its identity; the P0 provenance gate does not apply a genesis-base ledger to a user-supplied target

## Caveats / degradations (honest, in delivery order)
* note: the target already carries native walls; loading OUR families into it is the certified L1a shape (foreign host load), not the created-walls+loaded-families open-bug combination


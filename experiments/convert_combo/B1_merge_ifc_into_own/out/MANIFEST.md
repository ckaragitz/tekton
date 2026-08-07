# ifc+rvt->rvt merge (rvt.convert.merge_ifc) -- deliverable manifest

## The deliverable(s)
* **combined**: `experiments/convert_combo/B1_merge_ifc_into_own/out/B1_room_merged.rvt` (753,664 bytes, sha256 41e479668f150d75...)

## Stamps (labels, not refusals)
* PROOF-ONLY, NOT-DELIVERABLE (P0: identity/counsel gates G2-G3 open; every tekton output is an internal proof)
* PROOF-ONLY: walls+families combination unverified

## Target
* file: `experiments/convert_combo/B1_merge_ifc_into_own/target_copy.rvt` (Revit 2026, 4 walls, 8 instances, 8 family documents)
* release preserved: every output verified YES -- the output is a splice of the input, no version conversion
* placement level: id 311 at 0.0 ft ((nearest elevation 0))

## Placement
* rule: auto-disjoint: incoming content east of the target's bbox (+3.0 m margin, y-centred)
* offset: {"dx_m": 12.309, "dy_m": -1.115, "equip_dz_m": 0.0, "equipment_translated": 12, "walls_translated": 4, "note": "clearance boxes / conduit runs (informational layers) are NOT translated; positions in the manifest are post-offset"}
* hosting: free-standing placement at the intent's frames (certified shape); face-hosting follow-up

## Created
* family(.rfa): tag=T1, name=Dry Type Transformer T1 150kVA 480-208Y/120
* family(.rfa): tag=MSB, name=Switchboard MSB 2500A 480Y/277
* family(.rfa): tag=DP-1, name=Distribution Panelboard DP-1 480Y/277 400A MB 42sp
* family(.rfa): tag=LP-1, name=Lighting Panelboard LP-1 480Y/277 100A MLO 30sp
* family(.rfa): tag=LP-2, name=Lighting Panelboard LP-2 480Y/277 100A MLO 30sp
* family(.rfa): tag=DP-2, name=Distribution Panelboard DP-2 480Y/277 400A MB 42sp
* family(.rfa): tag=LP-3, name=Lighting Panelboard LP-3 480Y/277 100A MLO 30sp
* family(.rfa): tag=LP-4, name=Receptacle Panelboard LP-4 208Y/120 225A MB 42sp
* wall: tag=W-N, elem_id=1473479
* wall: tag=W-W, elem_id=1473480
* wall: tag=W-E, elem_id=1473481
* wall: tag=W-S, elem_id=1473482
* equipment-instance: tag=T1, elem_id=1473483
* equipment-instance: tag=MSB, elem_id=1473484
* equipment-instance: tag=DP-1, elem_id=1473485
* equipment-instance: tag=LP-1, elem_id=1473486
* equipment-instance: tag=LP-2, elem_id=1473487
* equipment-instance: tag=DP-2, elem_id=1473488
* equipment-instance: tag=LP-3, elem_id=1473489
* equipment-instance: tag=LP-4, elem_id=1473490
* loaded-family: tag=MSB, symbol_id=1473069, family_id=1473051
* loaded-family: tag=DP-1, symbol_id=1473128, family_id=1473112
* loaded-family: tag=DP-2, symbol_id=1473187, family_id=1473171
* loaded-family: tag=LP-1, symbol_id=1473246, family_id=1473230
* loaded-family: tag=LP-2, symbol_id=1473305, family_id=1473289
* loaded-family: tag=LP-3, symbol_id=1473364, family_id=1473348
* loaded-family: tag=T1, symbol_id=1473418, family_id=1473405
* loaded-family: tag=LP-4, symbol_id=1473477, family_id=1473461

## Gates (self-checks; viewer acceptance is a separate tier)
* combined: validator VALID (0 errors, 1 warnings); four-registry coherent=True; release 2026 (preserved=True)
* identity: the output keeps the TARGET's own identity block (BasicFileInfo / history): this route EDITS the user's file, it does not re-author its identity; the P0 provenance gate does not apply a genesis-base ledger to a user-supplied target

## Caveats / degradations (honest, in delivery order)
* TMGB (ground_bus): NOT built -- family plan unmapped: no house generator for a ground bus bar (a small generic-model family is the follow-up; the TMGB is a detail component, not equipment) -- recorded only
* CONDUIT (conduit_run): NOT built -- family plan unmapped: conduit RUNS are rvt.mep.conduit territory (add_conduit_path over the recorded polyline); needs conduit types in the base -- recorded as run geometry, omitted from v1
* SERVICE (service_entrance): NOT built -- family plan unmapped: utility service entrance: external source -- recorded as the SERVICE edge of the feeder tree
* HANGERS (support): NOT built -- family plan unmapped: trapeze hangers / clevis supports = detailing (supports stream); recorded, omitted from the project file


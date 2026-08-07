# ifc+rvt->rvt merge (rvt.convert.merge_ifc) -- deliverable manifest

## The deliverable(s)
* **combined**: `experiments/convert_combo/B2_merge_rst_devonly/B2_room_into_rst.rvt` (6,766,592 bytes, sha256 b85a7785a037497d...)

## Stamps (labels, not refusals)
* PROOF-ONLY, NOT-DELIVERABLE (P0: identity/counsel gates G2-G3 open; every tekton output is an internal proof)
* QUARANTINED TARGET (dev-only proof): the target file is an Autodesk sample standing in for a user upload; this output exists to PROVE the route and is never shipped or redistributed
* PROOF-ONLY: walls+families combination unverified

## Target
* file: `samples/rstbasicsampleproject.rvt` (Revit 2026, 9 walls, 497 instances, 41 family documents)
* release preserved: every output verified YES -- the output is a splice of the input, no version conversion
* placement level: id 311 at 0.0 ft ((nearest elevation 0))

## Placement
* rule: auto-disjoint: incoming content east of the target's bbox (+3.0 m margin, y-centred)
* offset: {"dx_m": 32.773, "dy_m": -5.945, "equip_dz_m": 0.0, "equipment_translated": 12, "walls_translated": 4, "note": "clearance boxes / conduit runs (informational layers) are NOT translated; positions in the manifest are post-offset"}
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
* wall: tag=W-N, elem_id=1472996
* wall: tag=W-W, elem_id=1472997
* wall: tag=W-E, elem_id=1472998
* wall: tag=W-S, elem_id=1472999
* equipment-instance: tag=T1, elem_id=1473000
* equipment-instance: tag=MSB, elem_id=1473001
* equipment-instance: tag=DP-1, elem_id=1473002
* equipment-instance: tag=LP-1, elem_id=1473003
* equipment-instance: tag=LP-2, elem_id=1473004
* equipment-instance: tag=DP-2, elem_id=1473005
* equipment-instance: tag=LP-3, elem_id=1473006
* equipment-instance: tag=LP-4, elem_id=1473007
* loaded-family: tag=MSB, symbol_id=1472586, family_id=1472568
* loaded-family: tag=DP-1, symbol_id=1472645, family_id=1472629
* loaded-family: tag=DP-2, symbol_id=1472704, family_id=1472688
* loaded-family: tag=LP-1, symbol_id=1472763, family_id=1472747
* loaded-family: tag=LP-2, symbol_id=1472822, family_id=1472806
* loaded-family: tag=LP-3, symbol_id=1472881, family_id=1472865
* loaded-family: tag=T1, symbol_id=1472935, family_id=1472922
* loaded-family: tag=LP-4, symbol_id=1472994, family_id=1472978

## Gates (self-checks; viewer acceptance is a separate tier)
* combined: validator VALID (0 errors, 1 warnings); four-registry coherent=True; release 2026 (preserved=True)
* identity: the output keeps the TARGET's own identity block (BasicFileInfo / history): this route EDITS the user's file, it does not re-author its identity; the P0 provenance gate does not apply a genesis-base ledger to a user-supplied target

## Caveats / degradations (honest, in delivery order)
* TMGB (ground_bus): NOT built -- family plan unmapped: no house generator for a ground bus bar (a small generic-model family is the follow-up; the TMGB is a detail component, not equipment) -- recorded only
* CONDUIT (conduit_run): NOT built -- family plan unmapped: conduit RUNS are rvt.mep.conduit territory (add_conduit_path over the recorded polyline); needs conduit types in the base -- recorded as run geometry, omitted from v1
* SERVICE (service_entrance): NOT built -- family plan unmapped: utility service entrance: external source -- recorded as the SERVICE edge of the feeder tree
* HANGERS (support): NOT built -- family plan unmapped: trapeze hangers / clevis supports = detailing (supports stream); recorded, omitted from the project file


# prompt+rvt->rvt (rvt.convert.add_to_project) -- deliverable manifest

## The deliverable(s)
* **combined**: `experiments/convert_combo/A2_add_rme_devonly/A2_add_into_rme.rvt` (32,686,080 bytes, sha256 8d09aeddce1e4094...)

## Stamps (labels, not refusals)
* PROOF-ONLY, NOT-DELIVERABLE (P0: identity/counsel gates G2-G3 open; every tekton output is an internal proof)
* QUARANTINED TARGET (dev-only proof): the target file is an Autodesk sample standing in for a user upload; this output exists to PROVE the route and is never shipped or redistributed

## Target
* file: `samples/rmebasicsampleproject.rvt` (Revit 2026, 166 walls, 5629 instances, 147 family documents)
* release preserved: every output verified YES -- the output is a splice of the input, no version conversion
* placement level: id 378117 at 0.30896239133315895 ft ((nearest elevation 0))

## Placement
* rule: free floor space east of the target's content bbox (+1.0 m margin, y-centred)
* offset: {"dx_m": 54.097, "dy_m": 19.935, "equip_dz_m": 0.094, "equipment_translated": 2, "walls_translated": 0, "note": "clearance boxes / conduit runs (informational layers) are NOT translated; positions in the manifest are post-offset"}
* hosting: free-standing (certified shape); wall panels stand upright at panel height; FACE-HOSTING on the target's walls (H1 recipe) is the fidelity follow-up

## Created
* family(.rfa): tag=LP-1, name=Lighting Panelboard LP-1 480Y/277 100A MLO 42sp
* family(.rfa): tag=T1, name=Dry Type Transformer T1 75kVA 480-208Y/120
* equipment-instance: tag=LP-1, elem_id=888127
* equipment-instance: tag=T1, elem_id=888128
* loaded-family: tag=LP-1, symbol_id=888071, family_id=888055
* loaded-family: tag=T1, symbol_id=888125, family_id=888112

## Gates (self-checks; viewer acceptance is a separate tier)
* combined: validator VALID (0 errors, 1 warnings); four-registry coherent=True; release 2026 (preserved=True)
* identity: the output keeps the TARGET's own identity block (BasicFileInfo / history): this route EDITS the user's file, it does not re-author its identity; the P0 provenance gate does not apply a genesis-base ledger to a user-supplied target

## Caveats / degradations (honest, in delivery order)
* note: the target already carries native walls; loading OUR families into it is the certified L1a shape (foreign host load), not the created-walls+loaded-families open-bug combination


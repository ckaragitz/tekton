# route: rfa -> rvt

* ok: **True** -- OK (family loaded four-registry; project validates 0 errors)
* matrix cell: status **works**, route `famspec_load`, stages: facts->rfa -> rfa-load
* delivered:
  * `rfa` -> `experiments/routes/demo4-rfa-loaded-rvt/Chicago-Plenum_Recessed_Downlight_6in.rfa` (Revit 2026)
  * `loaded_rvt` -> `experiments/routes/demo4-rfa-loaded-rvt/Chicago-Plenum_Recessed_Downlight_6in_loaded.rvt` (Revit 2026)
  * `load_report` -> `experiments/routes/demo4-rfa-loaded-rvt/Chicago-Plenum_Recessed_Downlight_6in_load-report.json`
* caveats (after delivery, per the deliverable rule):
  * INPUT CONTRACT: a famspec JSON ({'kind': 'downlight', ...}) -- the family is REBUILT by its constructor and loaded through the certified four-registry loader; a bare foreign .rfa path is REFUSED with this row (no .rfa-from-disk reload exists yet)
  * kind='downlight' is the certified load archetype; catalog kinds (panelboard/transformer/luminaire) load through the room pipeline (prompt/ifc -> rvt), not this cell yet
  * default host = the loader-certified rst sample host; pass rvt to load into your own project (see the rfa+rvt cell)
  * every output is PROOF-ONLY, NOT-DELIVERABLE until TRACKER gates G2/G3 clear (docs/product/content-strategy.md); the manifest says so explicitly
  * no host .rvt supplied: loaded into the loader-certified rst host (the exact host of the viewer-certified L1a / L_downlight_loaded proofs)
* evidence cited by the matrix: certified:experiments/families/ifc/L_downlight_loaded.rvt; certified:experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt; test:tests/test_ifc_family.py; test:tests/test_famload.py
* seconds: 35.5

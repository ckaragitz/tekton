# route: prompt -> rfa

* ok: **True** -- OK (2 family .rfa generated; refusals honest)
* matrix cell: status **works**, route `prompt_to_rfa`, stages: prompt->intent -> intent->rfa
* delivered:
  * `intent` -> `experiments/routes/demo1-prompt-to-rfa/intent.json`
  * `families_dir` -> `experiments/routes/demo1-prompt-to-rfa/families`
  * `rfa:DP-7` -> `experiments/routes/demo1-prompt-to-rfa/families/dp7_eaton_prl2x_400a_42sp_480y_277.rfa` (Revit 2026)
  * `rfa:PP-1` -> `experiments/routes/demo1-prompt-to-rfa/families/pp1_eaton_prl2x_400a_42sp_480y_277.rfa` (Revit 2026)
* caveats (after delivery, per the deliverable rule):
  * family generation covers the catalog-backed kinds (panelboard / transformer / luminaire / the honest house switchboard); anything without facts is REFUSED by name, never invented
  * every output is PROOF-ONLY, NOT-DELIVERABLE until TRACKER gates G2/G3 clear (docs/product/content-strategy.md); the manifest says so explicitly
* evidence cited by the matrix: worked:experiments/frontdoor/prompt-electrical-room/families; test:tests/test_famgen_factory.py; test:tests/test_frontdoor.py
* seconds: 3.0

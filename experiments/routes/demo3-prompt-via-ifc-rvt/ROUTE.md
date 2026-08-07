# route: prompt -> rvt

* ok: **True** -- PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)
* matrix cell: status **works**, route `prompt_to_rvt`, stages: prompt->intent -> prompt->handoff -> intent->rvt
* delivered:
  * `intent` -> `experiments/routes/demo3-prompt-via-ifc-rvt/intent.json`
  * `ifc` -> `experiments/routes/demo3-prompt-via-ifc-rvt/prompt_intent.ifc`
  * `prompt_coverage` -> `experiments/routes/demo3-prompt-via-ifc-rvt/prompt-coverage.json`
  * `intent_from_prompt` -> `experiments/routes/demo3-prompt-via-ifc-rvt/intent-from-prompt.json`
  * `families_dir` -> `experiments/routes/demo3-prompt-via-ifc-rvt/families`
  * `combined` -> `experiments/routes/demo3-prompt-via-ifc-rvt/prompt_intent.rvt` (Revit 2026)
* stamps: PROOF-ONLY: walls+families combination unverified; PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)
* caveats (after delivery, per the deliverable rule):
  * walls + loaded families in ONE file is the OPEN BUG (r2): the combined file is STAMPED 'PROOF-ONLY: walls+families combination unverified'; --strict emits two coordinated certified-shape files instead
  * feeder CIRCUITS are a NAMED BLOCKER on the genesis base: the resolved circuit plan rides in the manifest, never faked
  * every output is PROOF-ONLY, NOT-DELIVERABLE until TRACKER gates G2/G3 clear (docs/product/content-strategy.md); the manifest says so explicitly
  * chain: the prompt's intent was emitted as IFC and re-entered through the ifc route (the handoff round trip, run in-process)
* evidence cited by the matrix: worked:experiments/frontdoor/prompt-electrical-room/manifest.json; test:tests/test_frontdoor.py; certified:experiments/ifc_room/electrical_room_2500a_walls_only.rvt; certified:experiments/ifc_room/stage_L8_lp4.rvt
* seconds: 69.0

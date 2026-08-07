# route: prompt+rvt -> rvt

* ok: **True** -- PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)
* matrix cell: status **works**, route `rvt_edit`, stages: rvt-read -> rvt-edit
* delivered:
  * `edited` -> `experiments/routes/demo5-prompt-rvt-edit/prompt_intent.edited.rvt` (Revit 2026)
* stamps: PROOF-ONLY, NOT-DELIVERABLE (hard gates PASSED)
* caveats (after delivery, per the deliverable rule):
  * the prompt is the EDIT (an edit sentence, ops.json path, or inline JSON); certified including on a FOREIGN file (M2_rac)
  * a prompt that is NOT edit-shaped but IS authoring-shaped falls back to building the new content with your .rvt as the BASE -- that branch is PARTIAL: the certified stage code + gates run, but no viewer certification exists on arbitrary bases
* evidence cited by the matrix: certified:experiments/manipulate/M3_modify.rvt; certified:experiments/manipulate/M4_move_retype.rvt; certified:experiments/manipulate/M2_delete_cascade.rvt; certified:experiments/manipulate/M2_delete_cascade_rac.rvt; worked:experiments/frontdoor/rvt-edit-room/manifest.json; test:tests/test_manipulate.py; test:tests/test_frontdoor.py
* seconds: 1.8

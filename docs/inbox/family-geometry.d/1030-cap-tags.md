# 1030 — an extrusion's cap tags follow its own Start / End

Stream **family-geometry** (tech-lead session, 2026-10-07). Closes #1030.

## The defect

Every box solid we generate had its two cap **face tags** the wrong way round for the parameters its own extrusion declares.

**How it happened.** The box B-rep (`geometry.solid_box_brep`) was proven against born *extrude-down* specimens. There, Start is the top cap (tag 1) and End is the bottom (tag 0). Later, the form writer reordered the extrusion's own parameters by elevation, so Start became the bottom and End the top, so that Revit's palette would show a positive depth. Its comment said "the B-rep is unaffected". The B-rep kept tag 1 on the top. In a born extrusion, the cap tags follow the parameters:
- tag 0 is the cap at the **End** offset;
- tag 1 is the cap at the **Start** offset.

So our top cap carried the Start's tag while the element called the top its End.

**Consequences found in our own files** (no Revit needed):
- **Height locks.** `height_law`, built from a born census, locks "end" (geomTag 0) to the higher plane and "start" (tag 1) to the lower one. Across the panelboard, the 45 kVA transformer and every archetype, **175 of 179** cap-face locks witnessed the cached cap on the *other* plane. The 4 that did not were already correct for other reasons.
- **Connectors.** A connector on a box top (`box_face('top')`) named tag 1, the Start cap.
- **Cylinders.** The true cylinder solid (`solid_cylinder_brep`), built from a born extrude-up specimen, already put tag 0 on its top, so `box_face`'s convention disagreed with it. No connector was affected: connectors are refused on any host that is not a 4-curve prism (`add_connector`, `add_conduit_connector`). The polygon cylinders a connector can sit on go through `new_extrusion` like every box.

## The born law (private corpus, counts only)

Read in `samples/reference-families/` (git-ignored), every second or third file, with the sketch plane's own normal:
- **Cap tags.** Tag 0 is the cap at the End offset and tag 1 the cap at the Start offset, in both directions. This held in 673 extrusions. 16 went the other way, not yet explained, and 56 had cap offsets that matched neither parameter.
- **Rails and side frames.** The `[1,i,0]` rails and every side face's frame sit on the cap at the *higher* offset along the sketch normal, with the side's x-axis pointing down. So the solid is always traced from the top: 369 of 369 checked.
- **The proof** (the solid only: the ExtrusionGStep face history, tag 1 = the Start cap, is unchanged and was not compared with born specimens). Born horizontal 4-line boxes with a clean history were rebuilt from their own dimensions with `solid_box_brep` and compared tree by tree (`compare_object_trees`). The result for every face and edge tag:

| specimens | current writer | fixed writer |
|---|---|---|
| End above Start (118) | 0 equal | **117 equal** |
| Start above End (40) | 35 equal | 35 equal (unchanged path) |

The remaining whole-tree differences are not tags. They are a root-flag variant and painted faces (`GFilling`), both outside this issue.

## What changed

- **`geometry.solid_box_brep(…, end_on_top=False)`.** With `end_on_top=True`, the top cap carries tag 0 and the bottom tag 1. Everything else is untouched: rails, frames, edges, loops, pids and face order.
  - `new_extrusion` passes it, because its parameters put End on top.
  - The wall path (`render/brep.py`) and the extrude-down specimen path keep the default.
- **`reproduce_specimen_solid`** now rebuilds a born specimen of either direction: traced from the higher offset, with `end_on_top` from the specimen's own parameters.
- **`factory.box_face`.** `'top'` is tag 0, the End cap, with rails `[3, 6, 10, 14]`. `'bottom'` is tag 1 with rails `[4, 7, 11, 15]`. The ambiguous `'start'` / `'end'` aliases are gone; nothing used them.
- **`famgen/cap_law.py` (new).** `lock_face_findings(doc)` checks, for every `Alignment` witness on an extrusion cap, that the witnessed cached face lies on the witness's own plane. This is the instrument that measured 175 / 179 → 179 / 179.
- **Matrix evidence (#981 / #984).** The downlight and stage_L8 generator outputs changed, so the guard procedure was followed:
  - `DOWNLIGHT_EARLIER_FORM` and `STAGE_L8_EARLIER_FORM` name the change;
  - so do the doc rows in `docs/product/PERMUTATION-MATRIX.md` and `plugin/docs/HONEST-STATUS.md`;
  - the new fingerprints are recorded as `reviewed`.

  `certified` is unchanged (None for both).
- **Tests whose assertions named the old tag.** The connectors on a panelboard, transformer and fan-coil disconnect top now assert tag 0: `test_famgen_factory.py`, `test_fan_coil_893.py`, `test_transformer_detail_879.py`.

## Evidence

- `tests/test_cap_tags_1030.py` + `test_conftest_scaffolding.py`: **34 passed**. The cap law (`test_every_height_lock_witnesses_the_cap_on_its_plane`) fails on main: the instrument reads 175 / 179 locks there.
- `test_matrix_evidence_981.py`, `test_matrix_evidence_984.py`, `test_doc_caveats_990.py`, `test_plugin_sync.py`, `test_cap_tags_1030.py`, `test_famgen_factory.py`, `test_fan_coil_893.py`, `test_transformer_detail_879.py` and `test_conftest_scaffolding.py`: **237 passed, 6 skipped**.
- A wide local sweep, before the test updates above: 7,100 passed, 10 failed. The 10 were exactly the old-tag assertions, the two evidence guards and plugin drift; each is addressed above.
- **Built and written:** the panelboard, the 45 kVA transformer and the strut trapeze, for 2026 and 2025. All six are family-mode **VALID, 0 errors**, with provenance ok.
- `tools/sync_plugin.py --check`: clean.

## Not claimed

No Revit claim (hard rule 4).
- This makes our files say what born files say about caps, and makes our own height locks name the face their plane holds.
- Whether Revit's flexing of a Height parameter changes because of it is a desktop question. It is a candidate cause for behaviour like #908's ("it changes the lengths but the rest of the element…"), not a finding.
- The single-variable desktop probe is a height-driven box flexed, before vs after. It goes in the next verdict batch, not as a separate ask (S-2026-09-04-a).

## BRANCH STATE

- Files:
  - `src/rvt/famgen/geometry.py` (`solid_box_brep(end_on_top=)`, `new_extrusion`, `reproduce_specimen_solid`);
  - `src/rvt/famgen/factory.py` (`box_face` only);
  - `src/rvt/famgen/cap_law.py` (new);
  - `src/rvt/frontdoor/matrix.py`;
  - all four with their plugin mirrors;
  - `docs/product/PERMUTATION-MATRIX.md`, `plugin/docs/HONEST-STATUS.md`, `docs/writer/family-geometry.md` (§3, the box section, now says born boxes extrude both ways and what `end_on_top` changes);
  - tests: `tests/test_cap_tags_1030.py` with the drop-in `tests/ci_shard.d/1030-cap-tags.txt`, and `tests/test_{famgen_factory,fan_coil_893,transformer_detail_879}.py`;
  - this record.
- Shipped on merge. The desktop probe is not staged yet.

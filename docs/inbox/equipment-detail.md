# equipment-detail — generated equipment looks like the product, opens in 3D, carries its clearances

Stream **equipment-detail** (tech-lead session, 2026-09-30). Issues:
- #879 (steer: "this looks absolutely nothing like a transformer");
- #878 (steer: opens in a high-detail, shaded 3D view);
- #882 (steer: clearance zones on every equipment family, toggleable);
- #884 (steer and desktop verdict: transparent purple zones; the toggles are not reliably working).

Territory: `src/rvt/famgen/equipment_detail.py` (new), `src/rvt/famgen/equipment_clearance.py` (new), `src/rvt/famgen/factory.py` (`make_transformer`, `make_panelboard`), `src/rvt/famgen/skeleton.py` (the 3D view's detail level), `src/rvt/famgen/famdoc_adoc.py` (the open-window state), `tools/make_family.py` (the envelope line), tests plus drop-ins, this record, and the `plugin/lib` mirrors.

## What was built

1. **A transformer built from its parts** (`equipment_detail.transformer_parts`). A ventilated dry-type transformer inside the catalog W × D × H envelope:
   - two base skids;
   - the enclosure, with a recessed ventilation slot under the lid, louver slats in it and side cheeks framing it;
   - an overhanging top cover (the drip lid);
   - low and high side louver banks;
   - a bolted front access panel with bolt heads, and a nameplate.
   
   Every detail dimension is a nominal proportion of the envelope (the archetype), never a manufacturer drawing. The dummy variant stays the one envelope box. The connectors sit on the cover's top face at the catalog height.
2. **The family opens in its 3D view, at Fine detail.**
   - Revit restores the windows listed in `DBDrawingInfo.m_openWindowStates`, one `WindowState` per view keyed by its `m_dbDrawingId`. This was measured on the owner's library transformer, which opens on its plan.
   - Our writer emptied the archetype's list, so a generated family opened on the Ref. Level plan. It now records one window: the 3D "View 1".
     - Projection extents are zero, so no zoom is saved and Revit fits the view, as the library specimens store it.
     - The screen rectangle is our neutral window size.
   - The 3D view carries `VIEW_DETAIL_LEVEL` 3 (Fine). Plans stay Coarse. The library's own 3D views carry 2 or 3.
   - The display style is unchanged: the owner's screenshot of our 3D view already showed shaded faces.
3. **Clearance zones on every equipment family** (`equipment_clearance`):
   - **Front zone:** the NEC 110.26(A) working space from #819's table.
     - Transformer: from its −y face, on the floor.
     - Panelboard: from its door face (+y), reaching the floor below a nominal cabinet top of 78 in, the #829 constant, stated in the file.
   - **Top zone:** the 110.26(E)(1) dedicated space for the kinds that rule names (panelboard: 6 ft). Otherwise a nominal 12 in ventilation zone, stated as nominal: a transformer's value is its nameplate marking (NEC 450.9).
   - **Toggles:** Yes/No parameters in the library's structure (measured privately, counts only):
     - a master *Show Clearances* (per instance);
     - *Show Front Clearance* and *Show Top Clearance* (per type);
     - each zone shown by `and(master, own)`, a Yes/No formula.
   - **The binding:** a `FamilyParametrizedElemParamsCell` `{param, −1006205}` between the extrusion helper and the pattern helper, with the driving parameter in the header's deletion parents. This is the layout of the 764 solids bound this way in the owner's library.
   - **The look** (#884): a graphics-only `MaterialElem` "Clearance Zone" (magenta 0xFF00FF, 50 % transparent, no appearance asset, the shape of Revit's own analytical-surface materials) on both zones. It is registered in `MaterialTracking`, and the equipment's own solids stay unpainted. The library's zone material is the same magenta at 33 %.

## Evidence

- **Tests:**
  - `tests/test_transformer_detail_879.py`: 8 passed.
  - `tests/test_equipment_clearance_882.py`: 8 passed.
  - Famgen suites (factory, skeleton, determinism, instance rows, router, LCP clearance, formula) plus plugin sync: 379 passed / 22 skipped.
  - Existing tests that pinned the old shape (one solid; W/H/D the only local parameters; the forms' max height) now name the parts and zones explicitly.
- **Written 45 kVA transformer:**
  - 38 parts plus 2 zones;
  - family-mode VALID with 0 errors, provenance ok;
  - load and place into a front-door host validates at 0 errors.
- **Panelboard:** VALID with 0 errors.
- **Delivered to the owner:** 2026 and 2025 copies, both VALID, plus a 2026 project with the transformer placed. They were built with the owner's private eVolve profile and values (#881). The owner's reaction to the parts: "Now that is how a transformer should look!"

## Desktop verdicts and open questions

- **Toggles (hard rule 4):** the owner reported the toggles "aren't necessarily working" (#884, on the first delivery).
  - Field by field, the binding matches the library's.
  - Open: whether the check was in the Family Editor, where Revit keeps showing hidden solids, or in a project. A project file was delivered for that check.
  - If still failing, stage single-variable probes: direct versus formula-driven, and type versus instance.
  - Until a verdict, nothing calls the toggles working.
- **`m_famElemVisibility`:** our solids carry 57399. Library solids never set bit 0 (57406 is typical), and an earlier session read bit 0 as Plan/RCP from one screenshot. Not changed here; it is a candidate variable for the #884 probe batch.
- **#887 session CI (507e1db): 3 failed / 4525 passed.** Each was fixed and re-run green:
  - `test_conftest_scaffolding`: the open-in-3D test reads a file inside its own release without conftest's leak guard. It now takes `no_release_leak` with `ladder_constants`.
  - `test_family_anatomy_837` (two tests): they pinned the panelboard's shape at 1 form and 21 parameters. It is now 3 forms (the cabinet and its two zones) and 26 parameters (with the 5 toggles), named in the assertions.
- **Follow-up to #887's review nits:**
  - The `make_family` geometry line reports the equipment's own envelope, now from each part's centre and extent (the report's form entries carry `role`, `center`, `source`); the zones print on their own `clearance` lines. It used to fold the zones into "the size" (a 43 in transformer read 78 in) and ignored the parts' positions.
  - The transformer's working space starts in front of its frontmost part, the cover overhang (`FRONT_PROUD_FT`, 0.5 in), not inside the proud plates.
  - The zone material's header flags (67108878) are the value measured on the owner's library clearance material (private, one number). The project-side constant (67108894) is a different writer's; both are candidate variables for the #884 probe batch.
  - The panelboard's working space reaches 1.5 ft below the family origin: the floor below the nominal 78 in cabinet top. In a project, place the cabinet at its mounting height, or the zone reaches below the level.
- **Still missing** versus the library transformer: entry zones, 3D ID and part-number text, the tracking symbol, a leg-height parameter, the body material (#885). The zones have no subcategory yet (#883).

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`, from main `6f56772`.
- Written: `src/rvt/famgen/equipment_detail.py`, `src/rvt/famgen/equipment_clearance.py`, `src/rvt/famgen/factory.py`, `src/rvt/famgen/skeleton.py`, `src/rvt/famgen/famdoc_adoc.py`, `tools/make_family.py`, `tests/test_transformer_detail_879.py`, `tests/test_equipment_clearance_882.py`, `tests/test_famgen_factory.py`, two `tests/ci_shard.d/` drop-ins, this record, and the `plugin/lib` + `plugin/skills` mirrors.
- Shipped: parts, open-in-3D, clearance zones.
- Staged: nothing.
- No certification claim.

## Fragments

Later PRs of this stream each write their own fragment under `docs/inbox/equipment-detail.d/`:
- `892-panelboard-parts.md`
- `893-fan-coil.md`

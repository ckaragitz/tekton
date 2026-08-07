# genesis-reduction — workstream record (DEEPEN THE REDUCTION, 2026-08-03)

Charter: continue the R0..R4s reduction ladder toward the irreducible core
of a Revit 2026 project, ONE surgical class of removals per stage, every
emitted file passing `tools/rvt_validate.py` with ZERO errors, and report the
deepest clean stage + the exact class of removal that first breaks
validation. Territory touched ONLY: `tools/rvt_reduce.py` (extended with the
"ladder v2" section), `tests/test_reduce.py` (extended), `experiments/genesis/*`
(new R5..R10 files + reports), this record. No `src/rvt/*` edits, no
orchestrator files, no browser use.

## Result in one screen

**Every stage of the new ladder is validator-clean.** The removal classes
requested (annotation, views, unused types, options/phases/links, families +
their embedded documents) plus a bonus parameter-definition sweep are ALL
achievable dangling-free; the arbiter is never violated by construction.
What each stage's residue documents is not "what breaks the validator" but
"what CANNOT be deleted without editing a surviving element" — the true
irreducible core, attributed per class below (§4). Deepest clean stage:
**R10b** — 3,022 host elements, 14 embedded family documents,
**1,437,696 bytes**, validator VALID (0 errors), structural gate clean.

| stage | rule (cumulative) | deleted | kept | size (B) | validator | Latest-dangling |
|---|---|---:|---:|---:|:--:|---:|
| src | rstbasicsampleproject.rvt | — | 13,936 | 6,672,384 | VALID | — |
| R5 | annotation (tags/dims/text/spot elev/filled regions/legend comps/detail+model lines) + schedule views | 5,279 | 8,657 | 5,976,064 | **0 errors** | 100 |
| R6 | + every view except `{3D}` and `Level 1` (+ sheets/viewports/companions/view-owned content) | 5,597 | 8,339 | 5,922,816 | **0 errors** | 260 |
| R7 | + unused/unplaced types (all Symbol descendants except view families/geo/browser org; materials, patterns, appearance assets, property sets) via reachability GC | 6,848 | 7,088 | 5,517,312 | **0 errors** | 1,370 |
| R8 | + design options, phases beyond the used one, links/imports, plan topologies (worksets: none — non-workshared) | 6,866 | 7,070 | 5,517,312 | **0 errors** | 1,384 |
| R9 | + families entirely: host Family/FamilySymbol/surrogates/params + ALL placed model content that only exists as family content, + ownership children | 10,227 | 3,709 | 3,313,664 | **0 errors** | 3,114 |
| **R9b** | R9 + the embedded family DOCUMENTS themselves: 38 of 52 save units spliced out of `Partitions/21` + 38 `Global/ContentDocuments` entries removed | (units 53→15) | 3,709 | **1,495,040** | **0 errors** | — |
| R10 (bonus) | + parameter/classification DEFINITION tables (466 shared-param defs, project params, bindings, load classifications, property sets) — GC sweep | 10,914 | 3,022 | 3,252,224 | **0 errors** | 3,801 |
| **R10b** | R10 + embedded documents (as R9b) | (units 53→15) | **3,022** | **1,437,696** | **0 errors** | — |
| R5s..R10s | same seeds, but ALSO pinning every id the i64 scan finds in `Global/Latest`/`ContentDocuments` (the R0/R4s-proven Latest-safe rule) | 5,141..5,282 | 8,795..8,654 | ~6.0 MB | 0 errors | **0** |
| R6naive | boundary probe: delete the WHOLE R6 seed (ignore pins) | 6,500 | 7,436 | 5,705,728 | **1 error** | 419 |
| R9naive | boundary probe: delete the WHOLE R9 seed (ignore pins) | 11,050 | 2,886 | 2,949,120 | **1 error** | 3,577 |

Arbiter run pasted (`.venv/bin/python tools/rvt_validate.py --quiet …`):

```
OK   R0_identity.rvt  errors=0 warnings=1     OK  R8.rvt  errors=0
OK   R5.rvt   errors=0 warnings=1              OK  R8s.rvt errors=0
OK   R5s.rvt  errors=0 warnings=1              OK  R9.rvt  errors=0
OK   R6.rvt   errors=0 warnings=1              OK  R9s.rvt errors=0
OK   R6s.rvt  errors=0 warnings=1              OK  R10.rvt errors=0
OK   R7.rvt   errors=0 warnings=1              OK  R10s.rvt errors=0
OK   R7s.rvt  errors=0 warnings=1              OK  R9b.rvt errors=0
FAIL R6naive.rvt errors=1 (494 dangling)       OK  R10b.rvt errors=0
FAIL R9naive.rvt errors=1 (877 dangling)
```
(the one warning everywhere = the known DataStorage/RebarShape extensible-
storage decode gap, present in the untouched source too.)

## 1. Why a new ladder — the prior R1..R4 FAIL the arbiter

Discovered on entry: the prior closure stages do NOT pass the current
validator (its semantic layer post-dates them): R1 29 / R2 290 / R3 1,051 /
R4 1,871 dangling ElementId references (fields `m_ownerId`, `m_famId`,
`m_linePatternId`, `m_materialElemId`, `m_fillPatternElemId` …). Two root
causes, both fixed by construction in ladder v2:

1. **"Delete the referrers" (closure) is the wrong semantics.** Many
   ElementId fields are OWNERSHIP or CONSTRAINT links whose direction the
   closure inverts: a `FamilySurrogate` references the `LegendComponent` it
   depicts (deleting one legend component cascaded through
   Family→FamilySurrogate to **285 instances**); a locked `Alignment` /
   sketch-constraint `LinearDimString` is referenced BY the wall's/floor's
   `VarSketch` (deleting "annotation" ate the structural model); rebar
   references its presentation views; a 3D view lists element ids in its
   crop/visibility state. Traced causal chains are in the tool's history
   (`Alignment → SWall`, `LinearDimString → VarSketch → floor/joists`,
   `ModelClipBox → DBView3d → Rebar`).
2. Protected infrastructure survivors (KEEP_ALWAYS `CategoryElem` etc.)
   were left holding dangling ids.

## 2. The ladder-v2 rules (implemented in `tools/rvt_reduce.py`, section "LADDER v2")

* **Reference graph = the arbiter's own model.** `build_state_v2` runs
  `rvt.validate._RefDecoder` (schema-typed ElementId capture) over EVERY
  record of EVERY save unit — seq 102 (the validator's gated set) plus
  seq 101/103 — 32,011 ids, 144,269 typed edges on rstbasic. A deletion set
  consistent with this graph cannot produce a validator reference error.
* **Deletion = maximal garbage collection (`maxgc`).** For cumulative seed S:
  keep K = {s ∈ S referenced from outside S} closed FORWARD inside S (a
  kept element pins everything it references); delete = S − K. Dangling-free
  by construction, never cascades outside the seed, handles cycles inside
  the seed, and every survivor of a seeded class is attributable to the
  outside class pinning it (`pin_evidence` in each R<n>.json = the
  irreducible-core evidence).
* **Ownership/companion fixpoint** grows the seed: children referencing an
  already-seeded element (sub-categories `CategoryElem`, their `GStyleElem`,
  `FontElem`, `ParamElemFamily`; view companions `DBDrawing`/`Viewer`/
  `Viewport`/`SunAndShadowSettings`/`ExtentElem`/`ModelClipBox`; sketches
  `VarSketch`/`SketchPlane`; derived caches `HubsTracker`/`GCSTracker`/
  `RegenSplitterElem`/`PostedWarningElem`/`AllPlanTopologies`;
  `InitialViewSettings`) and **view-owned content** (element whose
  `m_ownerDBViewId` is a seeded view — Revit's own "delete view deletes its
  detail lines/components/tags"). `owner_view` is captured schema-driven
  from the field path, not guessed.
* History invariant protected (max-`modified_ep` element never seeded);
  the two keeper views are `{3D}` (1454508) and `Level 1` (1064656).
* **Primary variants R5..R10 ignore `Global/Latest`/`ContentDocuments`**
  (the validator does not gate on them; whether the READER tolerates
  dangling ids inside the serialized ADocument is the open question this
  ladder is built to answer — Latest-dangling grows 100 → 3,801 down the
  ladder). **R5s..R10s** additionally pin every scanned id (Latest-safe, the
  rule R0/R4s proved in the Autodesk viewer) — they plateau at ~8,7xx kept:
  **the Global/Latest wall** is again visible as the difference between the
  two columns.

## 3. R9b — embedded family document removal WORKS

`remove_units()` splices whole save units out of the `Partitions/<N>`
logical stream (unit k = 28-byte separator + blocks + footer; the ranges
tile the stream — `_unit_ranges`, proven by a tiling test) and removes the
matching `Global/ContentDocuments` entries (each entry is self-framed:
12-byte marker + GUID + u32 size + body + u32 size-repeat; entries tile the
payload from offset 0, verified 52/52 on rstbasic — the map carries NO
in-stream count/prologue, so entry removal is a clean splice; the LAST
entry's trailing 14-byte terminator is preserved). Unit selection: host
Family deleted AND no survivor references any id inside the unit AND no
kept parent document names it as a nested family (`m_oFamDoc.m_contentDocGUID`
inside another unit — 11 of rstbasic's 52 units are nested profile/tail
docs, resolved by fixpoint). Both streams are CRCIO-re-framed; Latest,
History, DIT, BasicFileInfo, ElemTable untouched. **38 of 52 documents
removed, partition logical 2,686,068 → 1,377,526 B, CD payload
1,365,825 → 557,592 B, container 3.31 MB → 1.50 MB, validator VALID.**
Risk stated plainly: `Global/Latest` (ADocument) may hold its own content-
document GUID list/count; nothing but the Autodesk viewer can arbitrate
R9b/R10b — this stage is the largest single reduction and the highest-risk
one; test it AFTER R9.

## 4. The irreducible core — what the ladder cannot delete, and why (evidence)

Deep census: `experiments/genesis/deep_census.json` (R10 survivors) and
`R9_census.json`; per-stage `pin_evidence` in every R<n>.json.

| survivor group @ R10 | count | pinned by (evidence) | what deleting it needs |
|---|---:|---|---|
| Object styles + categories (`GStyleElem` 1,533, `CategoryElem` 284, patterns 16, `MaterialElem` 23, `AppearanceAssetElem` 18) | ~1,880 | the category system is self-referential (category ↔ its GStyles) and never seeded — it is FORMAT infrastructure, not content | genesis writer regenerates the catalog; not a reduction target |
| **21 host Families + 14 embedded documents**: 8 curtain-wall system families (mullions / system panels), 12 view-annotation heads (Section Head/Tail ×4, Level Head, Grid Head, Callout Head, Elevation Mark Body+Pointer, View Title, Boundary Condition), title block `A1 metric`, structural default `M_HSS Square-Column` | 21 | `Family ← DBViewType x72`, `CalloutTag ← DBViewType x54`, Section/InteriorElev/Viewport ATTRIBUTES ← DBViewType, `FamilySymbol ← StructSettingsElem / CopyWatchProperties`, `PenWidthTableElem` — i.e. the 91 view TYPES and settings singletons carry default head/tag/title-block families | edit `DBViewType` (default section/callout/level/grid head attrs), `StructSettingsElem`, `PenWidthTable`; or delete the view types — deleting them was ruled out (base keeps view families) |
| 91 `DBViewType` + annotation TYPES they default to (`TextNoteAttributes` 25, `TagNoteAttributes` 20, `LeaderStyle` 19, `DimensionStyle` 12, Section/Callout/InteriorElev/Viewport attrs ~30, `FontElem` 96) | ~300 | kept by design (view families); their default-attribute references are the pin above | ADocument-free edit path exists (they are ordinary elements) — a future MODIFY stage |
| MEP / electrical / structural SETTINGS catalogs (`HVACLoadSpaceTypeElem` 125, load classifications 108, `HVACLoadBuildingTypeElem` 33, `BuildingOperatingYearSchedule` 27, `RbsWire*Type` ~35, `PipeSegment`/`RbsPipe*Type` ~40, load natures/cases 16 …) | ~450 | referenced by their settings singletons (`RbsWireSizesElem`, `PipeSettings`, `LoadCase…`) and each other — Autodesk DEFAULT catalog data | the genesis encoder must regenerate these tables (they are deterministic per Revit release, like the category catalog) — flagged as the SECOND catalog to own beside categories/styles |
| document singletons & datums (9 Levels + attrs, ProjectInfo, phases 2 + AllProjectPhases + 1 PhaseFilterElem, BasePoint 2, geo, ~120 UniqueElement/settings singletons, keeper views + companions, `DBViewProject`) | ~350 | the skeleton every project carries; **the second `ProjectPhase` ('Existing') is pinned by `AllProjectPhases`, which every kept view references → R8 cannot delete phases beyond one WITHOUT an `AllProjectPhases.m_phases` edit** (a MODIFY, out of delete-only scope); `RvtLinkSymbol` is pinned by both kept views' link-visibility settings → same | ADocument/element edit, not deletion |
| residue: 3 Grids + `GCSTracker`, 32 `SketchPlane`/21 `RefPlane` (family work planes), 6 `AreaSchemePlanTopologies`, `Level 2` plan + `Framing Plans` drafting sheet (pinned by the kept `Level 1` plan's viewport placement), 5 `CurveElem`/`LegendComponent` | ~90 | `pin_evidence.top_pinning_pairs` in R10.json | choose a keeper plan NOT placed on a sheet; grids are datums (kept like levels) |

**The class of removal that first breaks validation** — measured by the
`--naive` probes, which delete a stage's ENTIRE seed ignoring pins:
* **Views (R6naive → 494 dangling):** `RebarVisibilityCell.m_detailViewIds`
  (rebar per-view visibility states), `m_elementId`/`m_sketchId`/
  `m_directionId` (model elements pointing at view-owned sketches),
  `m_outOfFamilyRefs`, `m_previewElemId`. ⇒ views are pinned by the placed
  MODEL, not by document tables: they only become deletable together with
  the model (which is why R6's clean cut is small and R9's is huge).
* **Families/model (R9naive → 877 dangling):** `m_setInsulationIds`
  (`RbsWireSizesElem` MEP settings), `m_fillPatternElemId`,
  `m_famId`/`first` (**DBViewType → tag/head families**), `m_calloutAttrId`,
  the kept plan's own `m_dbDrawingId`/`m_extentElemId`/`m_sheetViewportElemId`
  (its companions were seeded — the ownership rule keeps them). ⇒ the family
  floor is set by view-type default families + settings catalogs.
* **No class breaks the arbiter when deleted with `maxgc`** — the boundary is
  entirely "requires editing a survivor", never "the file becomes
  structurally invalid". The validator/writer stack is therefore NOT the
  limit; the two limits are (a) ADocument/`AllProjectPhases`/`DBViewType`
  EDITS and (b) the reader's tolerance of `Global/Latest` dangling.

## 5. Files the orchestrator should viewer-test (in THIS order)

All in `experiments/genesis/`; each is validator-VALID + structurally clean.
Test primary variants first — each is one attributable class beyond the
previous; the first failure names the reader rule (§4 says the arbiter
predicts NO failure other than Latest-dangling):

1. `R5.rvt` (annotation strip; Latest-dangling 100) — cheapest probe of
   "does the reader tolerate dangling ids in Global/Latest at all?"
2. `R6.rvt` (views → {3D} + Level 1; 260), 3. `R7.rvt` (types; 1,370),
4. `R8.rvt` (options/phases/links; 1,384), 5. **`R9.rvt`** (families gone,
   model gone; 3,114), 6. `R10.rvt` (params; 3,801),
7. **`R9b.rvt` then `R10b.rvt`** — embedded-document removal (units 53→15;
   1.44 MB): the deepest files and the ADocument-content-table risk.
If R5 FAILS in the viewer, the whole primary ladder is blocked by Latest —
fall back to `R5s..R10s` (Latest-safe, all viewer-rule-compliant, but they
plateau at ~8.7k elements: that plateau IS the "encode ADocument" mandate,
now measured as ~5,700 elements' worth of otherwise-deletable content).

## 6. Deliverables

| item | path | state |
|---|---|---|
| ladder v2 engine (validator-exact graph, `maxgc`, ownership/owner-view fixpoint, stages R5..R10, naive probes) | `tools/rvt_reduce.py` (§ "LADDER v2") | done |
| embedded-document removal (`_unit_ranges`, `remove_units`, `run_stage_r9b` incl. nested-family closure) | `tools/rvt_reduce.py` | done, validator-clean |
| 15 new files: R5..R10 + s + b variants, R6/R9 naive probes, each with a JSON report | `experiments/genesis/` | on disk, arbiter-verified |
| ladder summary + deep census | `experiments/genesis/summary_v2.{md,json}`, `deep_census.json`, `R9_census.json` | done |
| tests (maxgc semantics/cycles/pins, ownership+owner-view rules, unit-range tiling, identity unit splice validity, R5 end-to-end validator-clean) | `tests/test_reduce.py` (+7) | pass |

Reproduce: `.venv/bin/python tools/rvt_reduce.py --ladder v2 --naive R6,R9`
(≈3 min, all stages) or `--ladder v2 --stage R9` (R9+R9b).

## 7. Gotchas found (for KNOWLEDGE.md merge)

1. **Ownership vs usage references.** ElementId fields point in "wrong"
   directions for cascade deletion: surrogate→legend component, sketch→its
   constraint dimensions/locked alignments, sun settings→sun annotation,
   3D view→section box AND view→per-element visibility lists, tracker
   singletons→everything they track. NEVER cascade by deleting referrers;
   GC (delete only the unreferenced) is the safe operator, with an
   ownership-children fixpoint to release parent+child groups together.
2. **The seq-101 ElementHeader `m_parents.m_deletion[]` array** looks like
   Revit's own delete-dependency list but is NOT usable as one directionally
   (a CategoryElem lists its own GStyles; a FontElem lists its family AND
   owner AND itself). Ignore it; the GC needs no dependency semantics.
3. **`ContentDocuments` is a self-framing tiled array with no count** (each
   entry ends in a u32 repeat of its body size; last entry + 14-byte map
   terminator) — entry removal is a plain splice; the count/GUID list, if
   any, lives in `Global/Latest`.
4. **Save-unit ranges tile the partition logical stream**
   (separator+blocks+footer), unit GUIDs are `bytes_le` in the separator;
   11/52 rstbasic units are NESTED family documents referenced only by a
   `Family.m_oFamDoc.m_contentDocGUID` inside another unit — unit GC must
   follow parent→nested edges or it strands them.
5. **`InitialViewSettings`** (the "starting view" singleton) pins its view →
   that view's sheet → every view placed on it → those views' per-element
   states → the placed model. One settings element was the difference
   between 5,404 and 3,709 survivors.
6. The prior R1..R4 closure files FAIL the current arbiter (29/290/1051/1871
   dangling) — do not treat R1..R4 as valid probes; use R5..R10.

## 8. Open questions (need the viewer / next session)

* Does the reader tolerate dangling ElementIds inside `Global/Latest`? (R5
  answers cheaply; R5s..R10s are the fallback.)
* Does the reader accept a project whose embedded content documents were
  removed while `Global/Latest`'s ADocument still names them? (R9b/R10b.)
* Reader minimum-view rule: R6+ keep `{3D}` + `Level 1` (+ `DBViewProject`);
  is one enough? is `DBViewProject` mandatory?
* Are the ~450 MEP/electrical/structural settings-catalog elements and the
  1,533-style/284-category catalog viewer-mandatory or just editor comfort?
  (an R11 "settings catalogs" sweep is one line to add if the viewer says go).

## Proposed next tasks (orchestrator decides)

1. Viewer-test the §5 list; record the deepest pass in `docs/acceptance-log.md`.
2. MODIFY-stage stream: `AllProjectPhases.m_phases` (drop 'Existing'),
   `DBViewType`/section/callout/level/grid head attrs (release the 12
   annotation-head families), `InitialViewSettings` re-point — via
   `rvt.manipulate`; these are the only edits between R10b and a
   family-free skeleton.
3. `Global/Latest` (ADocument) encoder — still THE critical path if R5
   fails, and needed to clean the growing Latest-dangling counts regardless.
4. Regenerate-not-copy catalogs: category/GStyle table AND the MEP/
   structural settings catalogs (§4) — both are deterministic per release.
5. Merge `MODEL_CLASSES`/`V2_*` taxonomies into `KNOWLEDGE.md` (verified
   census of what "family content" and "view-owned content" mean).

## Diffs requested outside my territory
None required — ladder v2 uses only public APIs (`rvt.reduce.delete_elements`,
`rvt.validate._RefDecoder`/`validate_file`, `rvt.families`, `rvt.content`,
`rvt.partitions`, `rvt.ecc`, `rvt.cfb_writer`). Hygiene suggestion (owner
of `src/rvt/validate.py`): export `_RefDecoder` publicly (it is now the
canonical schema-typed reference extractor two tools depend on).

BRANCH STATE: no VCS in repo (plain directory); all work is uncommitted
files: tools/rvt_reduce.py (ladder v2 section appended; v1 untouched),
tests/test_reduce.py (+7 tests), docs/inbox/genesis-reduction.md (this),
experiments/genesis/{R5..R10}{,s}.rvt+.json, R9b/R10b.rvt+.json,
R6naive/R9naive.rvt+.json, summary_v2.{md,json}, deep_census.json,
R9_census.json. Full suite at handoff: **449 passed, 1 failed** — the
failure is `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source`
(the plugin bundle is out of sync with a concurrent stream's new
`src/rvt/genesis/*` — needs `python tools/sync_plugin.py`, not my
territory); an order-flaky `test_mep_views_spaces` failure seen once in an
earlier `-x` run passes in isolation. All 12 tests in `tests/test_reduce.py`
(7 new) pass. READY.

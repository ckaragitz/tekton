# genesis-lint — THE CONSTRUCTED-OBJECT LINTER (workstream record, 2026-08-03)

Charter (orchestrator verdicts #9): every file whose element records are
cloned / verbatim reproductions of real Autodesk objects LOADS in Autodesk's
own reader; EVERY file carrying our from-scratch CONSTRUCTED objects (the
genesis settings singletons, our built-in style catalog rows, house-standard
content — built field-by-field over schema blanks with OUR values) FAILS
with "Revit-DocumentCorruption: The file is corrupt", while our validator
calls all of them VALID.  This stream builds the instrument that finds how
our constructed objects differ from EVERY accepted specimen of their class,
SYSTEMATICALLY, so we stop discovering constraints one viewer-hour at a time.

Territory touched ONLY (as chartered): `src/rvt/objlint.py` (new),
`tests/test_objlint.py` (new, 18 pass), `experiments/genesis/lint/**`
(the mined invariant corpus `invariants/<class>.json` × 130 + `_index.json`
+ `objlint_run.json`), `docs/writer/objlint-report.md` (the ranked report
= the deliverable), this record.  NO constructor, tool, test or other doc was
edited; every dependency (`rvt.objects`, `rvt.schema`, `rvt.mutate.Document`,
`rvt.elemtable`, the extracted corpus) is READ-ONLY imported.  This stream
does NOT fix constructors — it hands the fix stream the ranked list.  No
viewer / browser use.

## Result in one screen

* **The invariant corpus** — `experiments/genesis/lint/invariants/` : for
  **121 classes** (every class `rvt.genesis.{settings,catalog,types,
  skeleton,house_standard}` emit + 3 control classes), **59,770 host-document
  specimens** decoded from the six 2026 samples (seq-102 object + seq-101
  `ElementHeader` + `Global/ElemTable` row + seq-103 rep class per
  specimen), **15,823 mined per-field rules** over 130 class/cohort corpora.
  Reproduce: `.venv/bin/python -m rvt.objlint --mine-only` (≈ 24 s).
* **The linter** — `rvt.objlint.lint_object(class, obj, header, ...) ->
  findings [{severity, field_path, rule, ours, specimens_say, support, ...}]`,
  flagging every violation of a mined invariant (never-null, always-null,
  identical constant, container length, enum / vocabulary, range,
  owned-sub-object present, ElemTable ownership / owned-children, ElemTable
  VINTAGE, seq-103 rep class).
* **The run** — `docs/writer/objlint-report.md`: OUR objects in the three
  viewer-REJECTED files (X5.rvt, X9.rvt, S5.rvt; 3,241 elements) linted and
  CALIBRATED against the constructed / created objects the viewer already
  ACCEPTED (T_conduit_types.rvt = our from-scratch conduit / wire types,
  certified PASS; V21/V23/V29 created FamilyInstance / SWall / circuits,
  certified PASS): **398 load-bearing findings** (147 CRITICAL / 151 HIGH),
  every core rule type's control false-positive rate ≤ 2 % (STR_VOCAB
  7.2 %) — i.e. the accepted controls satisfy essentially every rule the
  rejected objects break.  **The top of that report is the fix stream's
  bug list.**
* Full run (mine + lint + report): `.venv/bin/python -m rvt.objlint` (≈ 34 s).
* **The fresh loop** — `.venv/bin/python -m rvt.objlint --fresh`: builds
  the CURRENT constructors' output standalone (house catalog + the whole
  settings constellation + the built-in catalog, 1,741 records) and lints
  it against the cached corpus in ≈ 8 s, tagging rules the last file run
  proved tolerated — the fix stream's change-a-constructor / watch-the-
  finding-vanish iteration loop (no file build, no ladder).

## What the linter found (the finding FAMILIES = the fix stream's work queue)

Ranked by the report's own scoring (support × coverage × calibration); the
family table in report §2 carries counts and top exemplars; §4 the flat
ranked evidence with our violating element ids.  Everything below was
VERIFIED on raw specimens this session (§Findings-with-evidence).

1. **NULLED references that specimens ALWAYS populate** (115 rules) — the
   biggest family and the most concrete:
   * every `ElectricalLoadClassification` is BORN WITH SIX
     `ParamElemElectricalLoadClassification` companion elements
     (`m_actualSpaceLoad / demandFactor / estCurrent / estLoad /
     totalCurrent / totalLoad ParamElemId` -> a param element, 70/70) and
     names all six + its demand-factor definition in its header deletion
     list (length always 8); ours nulls all six, deletion list 2;
   * every `BasicWallType` (103/103) / roof / floor / ceiling type references
     a `LegendComponent` preview element (`m_previewElemId`); ours -1
     [WEAKENED by cross-class analogy: our PASSING `RbsConduitType` /
     `RbsCableTrayType` in T_conduit_types.rvt ALSO carry
     `m_previewElemId = -1` while their specimens never do — the linter
     calibrates that rule away for the MEP types, PROVING preview-null is
     tolerated there; wall types remain unproven, hence still listed];
   * every project view (`DBViewPlan` 303/303, `DBView3d` 142/142,
     `DBViewProject` 6/6, and the navigator) carries a `RetouchTable` whose
     `m_invisibleGStyleId` / `m_notSilhouetteGStyleId` reference a
     `GStyleElem` (identical class 100 %); ours nulls both;
   * every `MaterialElem` (1,068/1,068) carries a NON-NULL asset descriptor
     (`Material.m_asset.m_sName`, `m_sLibrary` = `assetlibrary_base.fbx`,
     `m_eAssetType` = 4 in every specimen); our house materials null it
     (the deliberate render-asset scrub — see counsel note below);
   * `LevelAttributes`: `m_leaderCategoryId`, `m_lineAndTextAttr.
     m_categoryId` (-> a `CategoryElem`) and `m_lineAndTextAttr.m_fontId`
     (-> a `FontElem`) never null (13/13); ours all null.
2. **ElemTable OWNERSHIP web** (22 rules) — the ADD-PATH surface no prior
   audit walked (the registry-parity audit reads the ADocument; this reads
   `ElemRec.m_OwningElementId`):
   * `TextNoteAttributes` OWNS exactly two rows in **2,026/2,026**
     specimens: a `CategoryElem` + a `FontElem` (`ETR.owned` = {@CategoryElem,
     @FontElem}); every `FontElem` (5,982/5,982) is OWNED (by its annotation-
     attributes type); every sub-category `CategoryElem` OWNS its `GStyleElem`
     (8,225/8,227) and is itself owned by an attributes type (7,542/8,227,
     leader/dimension/text/tag styles);  ours: text types own nothing, fonts
     un-owned;
   * every `Viewer` (507/507), `Viewport` (1,028/1,028, owner class always
     `@DBDrawing`) and `DBDrawing` (831/831) is OWNED by its view /
     drawing; every `RbsDbViewSystemNavigator` OWNS {`Viewer`, `DBDrawing`}
     (6/6) — and OUR violations LOCALIZE to the **X2 system-navigator
     constellation** (ids 1600008..1600011 in X5 / 1600096..1600099 in S5):
     its Viewer / Viewport / DBDrawing are un-owned and the navigator owns
     nothing, whereas the SKELETON's plan / 3D view companions carry the
     correct owners (they do not appear in the violation list) — a
     localized, actionable defect INSIDE the failing X5 file;
   * `RevisionNumberingSequence` always owned by `@AllProjectRevisions`
     (12/12) and `AllProjectRevisions` owns exactly its 2 sequences (6/6);
     ours (X5 revision constellation, ids 1900044/45/47) un-owned / owns 0;
   * `LevelAttributes` owns a `CategoryElem` + `FontElem` (13/13); ours
     owns nothing.
3. **ElemTable VINTAGE** (22 rules) — the document-birth singletons: in
   ALL 6/6 files the project pen table, `AllProjectPhases`, `DBViewProject`
   are `creation_ep == 0` AND id band `<5k`; `ProjectInfo` `<50k`,
   `UnitsElem` / `TrueNorth` / `DaylightSourceIdSet` / `ExternalParamLock` /
   `AllProjectRevisions` ∈ {`<5k`,`<50k`}, `KeynoteTable` /
   `KeynotingSystem` / `ConstructionSetProject` / the MEP settings ∈
   {`<5k`,`<500k`}; EVERY genesis element lives at id ≥ 1,500,000 in a late
   creation episode.  CRUCIALLY this does NOT hold for user-content classes —
   `GStyleElem`-builtin, `CategoryElem`, `MaterialElem`, `Level`,
   `RbsConduitType`, `FamilyInstance` specimens span every band and are
   almost never episode 0 — which is EXACTLY the divide between what PASSES
   (our conduit types, created instances = user content, no vintage rule) and
   what FAILS (the birth-vintage settings / skeleton classes).  A cheap,
   decisive probe (below).
4. **ElementHeader shape** (23 rules): every `SunAndShadowSettings` header
   names the project `BasePoint` as its ONE `m_appearanceParents` entry AND
   its ONE `m_regenOnly` entry (773/773, verified: rst 54520 -> BasePoint
   111429); ours: both lists empty.  `BasePoint`'s own header: `m_regenOnly`
   length always 2, `m_hasNonDetermRegenChildren` True (12/12); ours 1 /
   False.  `LevelAttributes` `m_regenOnly` length always 2 (13/13); ours 0.
   `UnitsElem` `HDR.m_abFlags4Bytes` ∈ {2074, 8218} (6/6); ours 8222.
5. **MISSING owned sub-objects** (4 rules, all `Viewer3d`, 135/135): every
   `Viewer3d` carries a header `m_pBBox` `Outline`, a `m_geomSteps`
   `GeomStepList`, and its seq-103 rep is a **`GElement` in 100 % of
   specimens** (ours `SerializedDummy`); ours null / dummy.
6. **Container length / cardinality** (33 rules): `DBViewPlan`
   `GeomStepList.m_nonBRepGList` length always 2 (ours 1); `KeynoteTable`'s
   `ExternalResourceReferenceCell` inner arrays length always 1 (ours 0 —
   the empty keynote table carries an empty resource-reference cell where
   every real table names its external file); `UnitsElem.m_units.
   m_formatOptionsMap` length always **136** (6/6; ours 24 = our reduced
   spec set); `DBView3d` owned children ∈ {1, 4, 11, 32} (ours 3).
7. **Our VALUE vs a universal specimen constant** (140 rules; the
   product-default question the audit named, now enumerated field by field):
   `RbsPipeSettingsElem` `m_dMinLength` = 2.08333 ft (25") in ALL 84 rows of
   6 files (ours 3), `RbsDuctSettingsElem` `m_dBranchMinLength` /
   `m_dMainMinLength` = 2.08333 (ours 3), `StructSettingsElem` snap distance
   0.984252 ft (300 mm) / load-intensity slopes / brace offset (ours OUR
   values), `ReconcileBrowserSettingsElem` orphan colours 32768 (ours ours),
   `WorksharingViewModeSettings` status colours, `Viewer` `m_projMethodType`
   = 1 / `m_boundedSpace.m_isOn` True / `m_intentionallyPlaced` False
   (507/507; ours 2 / False / True), `UnitsElem.m_units.
   m_digitGroupingAmount` = 1 (ours 3), `TrueNorth.m_pocheDepth` =
   -9.84252 (ours -6), `Level` bubble-end / free-end / ref-point vectors
   (ours differ), `ConstructionSetProject`'s eleven construction-code
   strings never null (`ASHIF5`, `MDOOR`, `con-c23`... — ours unassigned =
   null; the audit's counsel item, now measured as a NEVER_NULL AString).
   These are DIFFERENCES; whether any is load-bearing only a probe answers —
   the family exists to make the counsel / default-value decision a LIST.
8. **A real data bug in OUR wire table** (RANGE, X4 `RbsWireSizesElem`): one
   correction-factor row has `m_dMin` 349.15 K > every specimen's max
   (344.15) AND `m_dMax` 298.15 K < every specimen's min (299.15) — an
   INVERTED min/max row in `wire_sizes_from_house_table`'s NEC correction
   factors.  Fix in the settings stream (see §Diffs).

**What the linter EXONERATES (equally load-bearing for the ladder read):**
* **Our 1,407-row GStyle catalog (X6a): ZERO findings.**  Built-in-cohort
  specimens (17,068) match ours on every mineable dimension — body, header
  flags (their `abFlags` set spans 12+ values incl. ours), ElemTable rows
  (un-owned, any id band, any episode).  R2's / X6a's rejection is NOT row
  shape, NOT registration (the parity audit already proved that), NOT
  ownership, NOT vintage.  What remains for R2 is either the substitution's
  wider context or — **note the caveat: R2s / R1s (the addback mechanics
  controls) were never viewer-uploaded**, so R1/R2's failures are not
  cleanly attributable to our content; only the K/X ladder verdicts are.
* Our pen table (X1) is shape-conformant EXCEPT (a) VINTAGE and (b) the
  scale-denominator set: X1.rvt AS BUILT carries our imperial ladder
  `m_invertedScale` ∈ {24..768} vs specimens' {10,20,50,100,200,500}
  (metric, 36/6).  Note the CURRENT `settings.pen_width_table()` default
  already emits the metric ladder — a fresh constructor object lints 100 %
  clean standalone (verified) — so an X1 REBUILT today differs from every
  specimen ONLY in vintage, the cleanest single-variable probe on the whole
  ladder.
* `BrowserOrganization`, `WallJoinDefaultSetting`, `AutoJoinTracker`,
  `InitialViewSettings`, `FillPatternElem`, `LinePatternElem`,
  `PhaseFilterElem`, `CategoryElem`(sub) rows: 0–1 minor findings each —
  those constructors already emit specimen-shaped objects.

## Findings with evidence (verified this session on raw specimens)

| finding | verified on |
|---|---|
| SunAndShadowSettings header appearanceParents = regenOnly = [BasePoint] | rst 54520 / 55153 -> BasePoint 111429 |
| ElectricalLoadClassification born with 6 ParamElemElectricalLoadClassification (in deletion list, len 8) | rst 113160: params 127547..127552 |
| Viewer3d: seq-103 GElement, m_geomSteps = GeomStepList | rst 1138900 |
| BasicWallType.m_previewElemId -> LegendComponent | rst 397 -> 1441831; 54538 -> 907390 |
| FontElem owned (5982/5982); TextNoteAttributes owns {CategoryElem, FontElem} (2026/2026); CategoryElem owns its GStyle (8225/8227) | invariants `owned_children` / `ETR.owner_class` |
| Viewport owner always @DBDrawing (1028); Viewer / DBDrawing always owned (507 / 831); navigator owns {Viewer, DBDrawing} (6/6) | invariants; violators = X2 navigator ids 1600008..1600011 |
| birth-vintage singletons: pen table / AllProjectPhases / DBViewProject `creation_ep==0` AND id `<5k` in 6/6 | invariants `ETR.created_at_birth` / `ETR.id_band` |
| GStyle built-in rows: NO vintage / ownership / shape rule violated by ours | X6a's 1,407 rows: 0 findings |

## Method (why the numbers are trustworthy)

* **Schema-parallel flattening** — the same walk `rvt.objects` decodes with,
  so every dict key is visited with its TRUE archive type: an int under an
  ElementId-typed field is an id (tokenized: -1 = null, other negatives =
  the literal built-in constant, positive = `@Class` resolved IN ITS OWN
  FILE), an int under `m_geomSteps` is a counter.  Growable containers
  collapse to `path[]` + `path.#len`, owned pointers add `path.#ptr` = the
  concrete class and are walked into (`->Class`), fixed arrays keep indices.
* **Presence-aware invariants** — each rule carries `present` = distinct
  specimens the path occurred in; specimen-level constants require
  universality, sub-object / element paths generalise only over the
  specimens that carry them, and a path our object legitimately lacks
  (under a null polymorphic pointer) is judged by the pointer slot's own
  rule, never by absence.  (This gating removed ~1,700 sparse-geometry
  false positives from the created-FamilyInstance controls.)
* **Cohorts** split populations that differ by rule: project vs
  family-scoped pen tables / view types (`m_famId`), built-in vs
  sub-category `GStyleElem` / `CategoryElem` (`m_ownerId` / parent),
  project vs family-owned `SketchPlane`.
* **Calibration is measured, not assumed**: 44,000+ rule checks against
  the PASS controls' elements; per rule TYPE the violated fraction is the
  false-positive rate (ALWAYS_NULL / ENUM / PTR_* 0.0 %, CONST_LEN 0.19 %,
  IDENTICAL 0.14 %, NEVER_NULL 0.11 %, RANGE 0.42 %, LEN_SET 1.7 %,
  STR_VOCAB 7.2 %); a (class, path, rule) a passing control of the same class
  violates is marked NOT load-bearing (14 such groups, all conduit-size /
  cable-tray table-length texture and FamilyInstance geometry).
* **The controls prove the from-scratch PATH is fine**: our conduit /
  wire / cable-tray types (same `blank_object` construction, same
  `commit_new_elements` add path, high ids, late episode) PASSED and lint
  clean.  The reader's objection is CLASS-SPECIFIC shape / vintage /
  ownership — which is what the families localise.

## Recommended probes (orchestrator queue, ranked by information value)

Each differs from a KNOWN-PASSING file by ONE change (the brief's
attribution rule); the fix stream builds them, this stream names them.

| # | probe | changes ONE thing vs | PASS means | FAIL means |
|--:|---|---|---|---|
| 1 | **X1 (already built)** — K1 + OUR pen table only | K1 (PASS) | our pen table's VINTAGE (id 1.5M, late episode) + scale set are tolerated; X5's killer is X2..X5 | vintage or the scale enum is a hard constraint -> probe 2 |
| 2 | **X1-lowid** — our pen table transplanted at a FREE LOW id (< 5k) with creation episode 0 | X1 | vintage is THE add-path constraint for birth-vintage classes (apply to every singleton) | rules vintage out |
| 3 | **X2-owned** — X2 with the navigator's Viewer / Viewport / DBDrawing OWNED by the navigator (ElemRec `m_OwningElementId`) per the 507/1028/831 rule | X2 | the ownership web is a load-time audit | (with X1 verdict) narrows to X3..X5 |
| 4 | **skel-sun-hdr** — the skeleton's `SunAndShadowSettings` headers wired with `appearanceParents = regenOnly = [BasePoint]` (773/773) | any passing base + one sun element | header edge required | header edge not the killer |
| 5 | **text-triad** — a `TextNoteAttributes` created OWNING its `CategoryElem` + `FontElem` (2026/2026), `LevelAttributes` likewise (13/13) | X9 / G1 | the annotation-type ownership triad is required | not required |
| 6 | **mat-asset** — our materials WITH a non-null asset descriptor (name / type 4; library string is the counsel token) | X7 | asset descriptor NEVER_NULL is enforced | nullable |
| 7 | **elc-params** — `ElectricalLoadClassification` born with its 6 `ParamElemElectricalLoadClassification` companions + deletion list | G1 / S5 | companions required | not required |
| 8 | **viewer3d-full** — `Viewer3d` with header `Outline`, `GeomStepList`, seq-103 `GElement` (135/135) | X9 / G1 | required | tolerated |

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/genesis/settings.py`** (singletons stream) — (a) FIX the
  inverted `dMin`/`dMax` correction-factor row in
  `wire_sizes_from_house_table` (RbsWireSizesElem; the linter's RANGE
  finding: dMin 349.15 > dMax 298.15); (b) `system_navigator`: emit the
  navigator's Viewer / Viewport / DBDrawing with ElemRec OWNER = the
  navigator / drawing (the skeleton's `new_project_view` already does this
  for project views — reuse it) and register them as the navigator's owned
  children; (c) `revision_constellation`: `RevisionNumberingSequence`
  ElemRec owner = the `AllProjectRevisions` element; (d) consider the
  vintage rule for EVERY singleton this module emits (id band / episode).
* **`src/rvt/genesis/skeleton.py`** — `new_sun_and_shadow_settings` /
  `new_document_sun_settings`: header `appearanceParents = regenOnly =
  [base point id]` (773/773); `new_viewer3d`: emit the seq-103 `GElement`
  rep, the `GeomStepList` and the header `Outline` (135/135); `BasePoint`
  header `regenOnly` length 2 + `m_hasNonDetermRegenChildren` True (12/12);
  every view constructor: populate `RetouchTable.m_invisibleGStyleId` /
  `m_notSilhouetteGStyleId` -> the invisible-lines / silhouette `GStyleElem`
  rows (needs those two catalog rows to exist and be named);
  `new_units_elem`: `abFlags` ∈ {2074, 8218} and the 136-entry
  `m_formatOptionsMap` question (ours 24).
* **`src/rvt/genesis/types.py`** — `new_load_class`: create the 6
  `ParamElemElectricalLoadClassification` companions and name them in the
  deletion list (70/70); wall / roof / floor / ceiling types: a
  `LegendComponent` preview element (`m_previewElemId`, 103/103);
  `new_text_type` / any annotation-attributes constructor: OWN a
  `CategoryElem` + `FontElem` in the ElemTable (2026/2026) — i.e. the
  types stream needs an ownership-aware `TypeRecord.refs['owner_id']`
  convention the commit path honours; `new_material`: the asset-descriptor
  decision (name / type non-null; the library string is a counsel item).
* **`src/rvt/genesis/house_standard.py`** — `_scrub_material` /
  `_scrub_view_render` produce the NEVER_NULL asset-descriptor and
  render-asset findings by design; if the probes prove them required, the
  scrub must SUBSTITUTE (our names / our environment) rather than NULL.
* **`src/rvt/validate.py`** (validation stream) — add `rvt.objlint` as a
  fourth layer: `lint_object` every element the file CREATED against the
  cached invariant corpus, escalating CRITICAL / HIGH un-calibrated
  findings to warnings; the corpus loads in < 1 s and needs no samples at
  lint time.  This is the missing bridge between "validator-clean" and
  "reader-clean" the whole G-line has lacked.
* **`tools/genesis_substitute.py` / `genesis_addback.py`** — assert the
  ownership + vintage rules in the parity table (they read only the
  ADocument today); and record that **R1s / R2s were never uploaded** —
  the addback mechanics are unproven, so R1/R2 verdicts are ambiguous.
* **KNOWLEDGE.md owner** — merge §"New format findings".
* **`tools/sync_plugin.py`** — this stream adds ONE `src/` module
  (`src/rvt/objlint.py`) to the plugin-drift list; left for the
  orchestrator's sync run (the pre-existing `test_plugin_sync` failure).

## New format findings (evidence — merge into KNOWLEDGE.md)

1. **The ElemTable ownership web of annotation types** [V, 6/6 files]:
   `TextNoteAttributes` owns exactly {`CategoryElem`, `FontElem`}
   (2,026/2,026); every `FontElem` row is owned (5,982/5,982) by an
   annotation-attributes type; every sub-category `CategoryElem` owns its
   `GStyleElem` (8,225/8,227) and is itself owned by an attributes type
   (7,542/8,227); `LevelAttributes` owns {`CategoryElem`, `FontElem`}
   (13/13).  Ownership = `ElemRec.m_OwningElementId`, invisible to every
   ADocument-registry audit.
2. **The view-constellation ownership** [V]: `Viewer` (507/507) and
   `DBDrawing` (831/831) are owned by their view; `Viewport` owner is
   ALWAYS a `DBDrawing` (1,028/1,028); a `Viewer3d` is owned by its
   `DBView3d` and owns its `ModelClipBox` (135/135); the system navigator
   owns {`Viewer`, `DBDrawing`} (6/6); a `DBViewPlan` owns
   {SunAndShadowSettings, DBDrawing, Viewer, SketchGrid} (majority) — the
   view is un-owned itself (299/303).
3. **Birth-vintage of document singletons** [V, 6/6]: project pen table,
   `AllProjectPhases`, `DBViewProject` = creation episode 0 + id `<5k`;
   `ProjectInfo` `<50k`; units / true-north / trackers ∈ {`<5k`,`<50k`};
   keynote / construction-set / MEP settings ∈ {`<5k`,`<500k`}.  User-
   content classes (built-in `GStyleElem` rows included!) span every band
   and are not birth-episode — vintage is a SINGLETON property, not a
   catalog property.
4. **`SunAndShadowSettings` header** [V]: `m_appearanceParents` =
   `m_regenOnly` = [the project `BasePoint`] in 773/773 specimens.
5. **`ElectricalLoadClassification` companions** [V]: born with 6
   `ParamElemElectricalLoadClassification` param elements (the six load
   parameters) referenced by `m_*ParamElemId` and listed with the
   demand-factor definition in the header deletion set (length 8, 70/70).
6. **`Viewer3d` is a GElement carrier** [V]: seq-103 `GElement` in
   135/135, plus `GeomStepList` and a header `Outline` — unlike every
   settings singleton (SerializedDummy).
7. **`RetouchTable` GStyle references** [V]: every project view's
   `m_pRetouchTable` names `m_invisibleGStyleId` / `m_notSilhouetteGStyleId`
   -> `GStyleElem` (100 %) — two more required style rows for the catalog.
8. **`MaterialElem.m_asset` is never null** [V, 1,068/1,068]:
   `m_eAssetType` = 4, `m_sLibrary` = `assetlibrary_base.fbx`, `m_sName`
   set — the Autodesk asset-library token is universal (counsel C-class:
   an interface identifier we currently null).
9. **`BasicWallType` / host types carry a `LegendComponent` preview**
   (`m_previewElemId`, 103/103 + roof / floor / ceiling).
10. **Method finding**: presence-gated invariant mining + same-class
    passing-control calibration yields per-rule-type false-positive rates
    ≤ 2 % on this corpus — the accepted constructed / created objects
    satisfy essentially every rule the rejected ones break, so the ranked
    list is genuinely discriminating, not generic noise.

## Counsel-adjacent notes (no action taken)

* The universal `assetlibrary_base.fbx` / `Generic` / `SunAndSky-002`
  asset descriptors (materials + every view's `GRenderSettings`) are
  Autodesk resource IDENTIFIERS that specimens NEVER null; our scrub nulls
  them.  If probes 6 / (a view variant) FAIL-then-PASS, these become
  required interface tokens for the counsel list (like `<Solid fill>`),
  not values we can leave blank.
* `ConstructionSetProject`'s eleven construction-code strings
  (`ASHIF5`...) are NEVER_NULL in 5/5 specimens; ours unassigned = null.

## Verification

* `.venv/bin/python -m pytest tests/test_objlint.py -q` → **18 passed**
  (flattener on real specimens, tokenizers / null semantics, id bands,
  family classification, cohorts, synthetic invariant derivation incl. the
  presence gates, real-specimen self-lint clean + injected-violation
  detection, `@?` unresolvable-target handling, JSON round trip incl.
  set-valued rules, calibration marking + rank demotion, source specs,
  ladder-rung bands, the fresh-constructor loop).
* Full suite this session: see BRANCH STATE.
* Arbiter comparison, this session: every FAILING file linted is
  `rvt_validate` VALID with 0 errors (X5, X9, S5) — the 398 findings are
  ALL outside the validator's rule set, by construction.

## Reproduction (repo root, .venv python)

```
python -m rvt.objlint                       # mine (six samples) + lint 9 sources + report  (~34 s)
python -m rvt.objlint --mine-only           # refresh experiments/genesis/lint/invariants/    (~24 s)
python -m rvt.objlint --no-mine             # lint + report from the cached corpus          (~10 s)
python -m rvt.objlint --fresh               # lint the CURRENT constructors standalone      (~8 s)
python -m rvt.objlint --classes GStyleElem,PenWidthTableElem
python -m rvt.objlint --enumerate          # run the constructors, print the classes they emit
python -m pytest tests/test_objlint.py -q   # 18 passed
```

Outputs: `docs/writer/objlint-report.md` (the ranked report),
`experiments/genesis/lint/objlint_run.json` (machine-readable bug list +
per-source counts + rule-type false-positive rates),
`experiments/genesis/lint/invariants/*.json` (the corpus, one per
class/cohort, + `_index.json`).

## Open questions (need the viewer / a decision)

* The eight probes above, IN ORDER — probes 1–3 discriminate the X5
  failure (X1's own verdict has never been read; it is the single most
  informative pending viewer round on the ladder).
* Whether the 140 product-default-value differences (family 7) are ever
  reader-audited (the linter's honest position: they are differences with
  N/N support; nothing measured says any is fatal).  The families exist so
  the fix stream / counsel can rule per FAMILY, not per byte.
* Whether `UnitsElem.m_units.m_formatOptionsMap` must carry all 136
  registered spec formats (ours 24) — a K5-style completeness question at
  field granularity.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files: `src/rvt/objlint.py`,
`tests/test_objlint.py` (18 pass), `docs/writer/objlint-report.md`,
`docs/inbox/genesis-lint.md` (this file), and under
`experiments/genesis/lint/`: `invariants/*.json` (130 corpora + `_index.json`,
12 MB) and `objlint_run.json`.  DONE per charter: the invariant corpus +
the ranked violation report over all our constructed objects (X5 / X9 / S5
= the failing set) calibrated by the passing controls (T_conduit + V-file
created elements).  Full suite this session (`.venv/bin/python -m pytest
tests/ -q --ignore=tests/oracle`): **790 passed, 3 failed** (848 s).  This
stream's 18 tests are among the 790.  The 3 failures are the pre-existing,
other-stream ones every recent record lists, none touching this stream's
files: `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` (the
plugin-bundle drift — this stream adds ONE `src/` module, `objlint.py`, to
that list; fix = the orchestrator's `tools/sync_plugin.py` run) and
`tests/test_provenance.py::{test_G0_resource_refs_are_counted,
test_G0_identity_dit_usernames_still_leak}` (the STALE assertions pinning the
pre-genesis-2 G0 defects; their owner's diff is in docs/inbox/genesis-2.md).
STOPPED AT READY — the ranked report + this record are the hand-off to the
fix stream; the eight probes are the orchestrator's queue.

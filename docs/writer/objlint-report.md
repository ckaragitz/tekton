# THE CONSTRUCTED-OBJECT LINT REPORT (`rvt.objlint`)

Generated 2026-08-03 23:57:36 by `src/rvt/objlint.py`.  Every finding is a violation, by one of OUR from-scratch CONSTRUCTED objects, of a per-field invariant MINED from the real specimens of that class across the six 2026 sample projects (`experiments/genesis/lint/invariants/<class>.json`).  **The top of this report is the BUG LIST for the fix stream** — ranked by (a) how many specimens support the rule (N/N over several files = a HARD constraint) and (b) how often our objects violate it, and CALIBRATED against the constructed / created objects the Autodesk viewer already ACCEPTED (T_conduit_types = our from-scratch conduit / wire types PASS; the V-file created FamilyInstance / SWall / circuits PASS): a rule those controls also violate is provably NOT load-bearing and is marked so and demoted.  The validator (`tools/rvt_validate.py`) reports every file here VALID with 0 errors — none of these findings is a validator rule; they are the reader's implicit shape contract, mined.

## 1. What was linted

| source | file | our elements | classes | verdict | role |
|---|---|--:|--:|---|---|
| **X5** | `experiments/genesis/subst/X5.rvt` | 80 | 71 | FAIL | BUG HUNT |
| **X9** | `experiments/genesis/subst/X9.rvt` | 1507 | 31 | FAIL | BUG HUNT |
| **S5** | `experiments/genesis/singletons/S5.rvt` | 1654 | 116 | FAIL | BUG HUNT |
| **T_conduit** | `experiments/genesis/types/T_conduit_types.rvt` | 16 | 10 | PASS | calibration control |
| **V21** | `experiments/acceptance/V21_batch_four_columns.rvt` | 4 | 1 | PASS | calibration control |
| **V23** | `experiments/acceptance/V23_electrical_room.rvt` | 12 | 2 | PASS | calibration control |
| **V29** | `experiments/acceptance/V29_room_with_circuits.rvt` | 16 | 3 | PASS | calibration control |
| **T_settings** | `experiments/genesis/types/T_settings.rvt` | 23 | 9 | UNTESTED | informational |
| **T_walltype** | `experiments/genesis/types/T_walltype.rvt` | 12 | 7 | UNTESTED | informational |

* **X5** (FAIL): substitution ladder X1..X5 (pen table, browser orgs + navigator, struct/wall-join/keynote/initial-view, MEP settings+sizes, 51 singletons/trackers) on K1 -- viewer FAILED (Revit-DocumentCorruption) — classes: BrowserOrganization×6, ModelGraphicsStyle×2, RevisionNumberingSequence×2, ViewSheetSet×2, AreaMeasureElem×2, PenWidthTableElem×1, ReconcileBrowserSettingsElem×1, ConstructionSetProject×1, RbsDbViewSystemNavigator×1, Viewer×1, Viewport×1, DBDrawing×1, StructSettingsElem×1, WallJoinDefaultSetting×1
* **X9** (FAIL): substitution ladder rungs X6a..X9 (our 1,407-row GStyle catalog, patterns/materials, units/sites/base points/project info, the view/level/phase skeleton) -- viewer FAILED (parent X5 already failed) — classes: GStyleElem×1410, DBViewType×19, MaterialElem×13, FillPatternElem×5, PhaseFilterElem×5, LinePatternElem×4, SunAndShadowSettings×4, Viewport×4, DBDrawing×4, TextNoteAttributes×3, FontElem×3, CategoryElem×3, Viewer×3, ExtentElem×3
* **S5** (FAIL): the census-complete candidate: G1_candidate base (skeleton + house content, ids 1.5M) + every settings singleton + the complete catalog (ids 1.6M) -- viewer FAILED — classes: GStyleElem×1414, DBViewType×19, MaterialElem×13, CustomElement×9, CategoryElem×7, RbsVoltageType×6, ElectricalLoadClassification×6, BrowserOrganization×6, FillPatternElem×5, RbsDistributionSysType×5, ElectricalDemandFactorDefinition×5, RbsConduitType×5, PhaseFilterElem×5, Viewport×5
* **T_conduit** (PASS): OUR from-scratch RbsConduitType / ConduitStandardType / ConduitSizes / CableTray / RbsWire* / CustomElement types injected into rme -- viewer PASSED = the from-scratch constructor path is accepted for these — classes: CustomElement×4, ConduitStandardType×2, RbsConduitType×2, RbsCableTrayType×2, ConduitSizesElem×1, CableTraySizesElem×1, RbsWireType×1, RbsWireMaterialType×1, RbsWireInsulationType×1, RbsWireTemperatureRatingType×1
* **V21** (PASS): four created FamilyInstance columns (clone-path) -- viewer PASSED — classes: FamilyInstance×4
* **V23** (PASS): created SWall x3 + FamilyInstance x9 (electrical room) -- viewer PASSED — classes: FamilyInstance×9, SWall×3
* **V29** (PASS): created SWall / FamilyInstance / RbsElectricalSystem circuits -- viewer PASSED — classes: FamilyInstance×9, SWall×4, RbsElectricalSystem×3
* **T_settings** (UNTESTED): OUR GStyle/Category/Voltage/DistributionSys/LoadClass/Font/Text/LinePattern types injected into rme -- no viewer verdict recorded — classes: RbsVoltageType×4, ElectricalDemandFactorDefinition×3, ElectricalLoadClassification×3, CategoryElem×3, GStyleElem×3, RbsDistributionSysType×2, TextNoteAttributes×2, FontElem×2, LinePatternElem×1
* **T_walltype** (UNTESTED): OUR wall/floor/roof/ceiling types + materials + patterns injected into rme -- no viewer verdict recorded — classes: MaterialElem×4, FillPatternElem×2, BasicWallType×2, LinePatternElem×1, FloorAttributes×1, RoofAttributes×1, CompoundCeilingType×1

Invariant corpus: **121 classes**, 59,770 host specimens mined from the six samples (seq-102 object + seq-101 header + ElemTable row + seq-103 rep class per specimen), 15,823 rules over 130 class/cohort corpora.  Reproduce: `.venv/bin/python -m rvt.objlint`.

## 2. Executive summary — the finding FAMILIES

Every load-bearing finding (violated by our REJECTED objects, not by any PASSING control of the same class) falls into a family.  The families are the constructor work items; the flat ranked list in §4 is the evidence per field.  `rules` = distinct (class, path, rule) rules violated; `elements` = how many of our objects break at least one rule of the family; `top exemplar` = the highest-ranked instance.  **X5-scoped** = present among X1..X5's classes (X5 = the FIRST rung the viewer rejected, so those are the prime suspects for that verdict).

| family | rules | violating elements | X5-scoped | top exemplar (class · path · ours → specimens) |
|---|--:|--:|:--:|---|
| **ElemTable OWNERSHIP web (owner / owned children)** | 22 | ≥26 | yes | FontElem · `ETR.owner_class` · null → never null (5982/5982 specimens) |
| **ElemTable VINTAGE (id band / creation episode)** | 22 | ≥43 | yes | AllProjectPhases · `ETR.created_at_birth` · False → identical value True in ALL 6/6 specimens |
| **NULLED reference specimens ALWAYS populate** | 115 | ≥46 | yes | MaterialElem · `m_pMaterial->Material.m_asset.m_sLibrary` · null → never null (1068/1068 specimens) |
| **MISSING owned sub-object (pointer we leave null)** | 4 | ≥4 | yes | Viewer3d · `HDR.m_pBBox.#ptr` · null (no owned sub-object) → owned sub-object ALWAYS present (135/135 specimens) |
| **ElementHeader shape (parents lists / flags)** | 23 | ≥41 | yes | SunAndShadowSettings · `HDR.m_parents->ElementParents.m_appearanceParents.#len` · 0 → length always 1 (773/773 specimens) |
| **container length / cardinality** | 33 | ≥30 | yes | DBViewPlan · `m_geomSteps->GeomStepList.m_nonBRepGList.#len` · 1 → length always 2 (303/303 specimens) |
| **seq-103 representation class** | 2 | ≥4 | yes | Viewer3d · `REP.seq103_class` · SerializedDummy → identical value GElement in ALL 135/135 specimens |
| **our VALUE differs from a universal specimen constant** | 140 | ≥78 | yes | MaterialElem · `m_pMaterial->Material.m_asset.m_eAssetType` · 0 → identical value 4 in ALL 1068/1068 specimens |
| **our value outside the observed range** | 16 | ≥24 | yes | GeoSite · `m_dMeanDailyTemperature[]` · 288.15  [12 leaves] → range [260.2 .. 271.039] over 144 elements over 12/12 specimens |
| **string / name vocabulary** | 21 | ≥31 | yes | DBViewType · `m_refLabelStr` · SIM. → value always in {Rand, Sim, null} (124/124 specimens) |

**Ladder-rung attribution** (which substitution rung / candidate layer each violation belongs to; the K1-derived ladder failed FIRST at X5, so X1..X5 rows are the ones a single verdict can convict; X6a..X9 were only ever tested on the failing parent):

| rung / layer | classes touched | distinct rules violated | strongest finding |
|---|---|--:|---|
| S5 base (G1_candidate) | DBViewProject, DBViewPlan, DBView3d, ElectricalLoadClassification, AllProjectPhases, ElectricalSetting … | 224 | MaterialElem · `m_pMaterial->Material.m_asset.m_sLibrary` · NEVER_NULL |
| S5 singletons+catalog | RbsPipeSettingsElem, ConstructionSetProject, RbsDuctSettingsElem, RbsWireSizesElem, RbsDbViewSystemNavigator, StructSettingsElem … | 171 | DBDrawing · `ETR.owner_class` · NEVER_NULL |
| T_settings | ElectricalLoadClassification, TextNoteAttributes, FontElem, ElectricalDemandFactorDefinition, RbsVoltageType | 21 | ElectricalLoadClassification · `m_actualSpaceLoadParamElemId` · NEVER_NULL |
| T_walltype | CompoundCeilingType, BasicWallType, FloorAttributes, RoofAttributes | 11 | BasicWallType · `m_previewElemId` · NEVER_NULL |
| X1  pen table | PenWidthTableElem | 3 | PenWidthTableElem · `ETR.created_at_birth` · IDENTICAL |
| X2  browser/navigator | ConstructionSetProject, RbsDbViewSystemNavigator, Viewport, DBDrawing, Viewer, ReconcileBrowserSettingsElem … | 43 | DBDrawing · `ETR.owner_class` · NEVER_NULL |
| X3  named singletons | StructSettingsElem, KeynoteTable, KeynotingSystem | 15 | StructSettingsElem · `m_analyticalModelSnapDistance` · IDENTICAL |
| X4  MEP settings/sizes | RbsPipeSettingsElem, RbsDuctSettingsElem, RbsWireSizesElem, ConduitSettingsElem, CableTraySettingsElem, RbsDuctSizesElem … | 62 | RbsPipeSettingsElem · `m_mapSystemTypeToPipeSettings[].second.m_dMinLength` · IDENTICAL |
| X5  remaining singletons | CoordinateSystemDisplayElem, CopyWatchProperties, AllProjectRevisions, RevisionNumberingSequence, EnergyDataSettings, ProjectRevision … | 36 | RevisionNumberingSequence · `ETR.owner_class` · NEVER_NULL |
| X7  patterns/materials | MaterialElem | 4 | MaterialElem · `m_pMaterial->Material.m_asset.m_sLibrary` · NEVER_NULL |
| X8  units/site/info | GeoSite, UnitsElem, BasePoint, TrueNorth, ProjectInfo, GeoLocation | 18 | GeoSite · `m_weatherStationName` · NEVER_NULL |
| X9  view/level skeleton | DBViewProject, DBViewPlan, DBView3d, AllProjectPhases, LevelAttributes, Level … | 150 | FontElem · `ETR.owner_class` · NEVER_NULL |

## 3. Calibration — rule types the ACCEPTED controls violate

Our from-scratch conduit / wire / cable-tray types (T_conduit_types.rvt) and the created FamilyInstance / SWall / circuit elements (V21/V23/V29) all LOADED in the Autodesk viewer.  Every rule of a class those controls violate is by definition not required by the reader.  Per RULE TYPE, the fraction of rules the controls violate is the type's false-positive rate; noisy types are demoted in the ranking and their findings should be read as texture, not defects.

| rule type | rules checked on PASS controls | violated | false-positive rate | reading |
|---|--:|--:|--:|---|
| STR_VOCAB | 97 | 7 | 7.2% | mostly reliable |
| LEN_SET | 1587 | 27 | 1.7% | trustworthy |
| RANGE | 11982 | 50 | 0.4% | trustworthy |
| CONST_LEN | 3218 | 6 | 0.2% | trustworthy |
| IDENTICAL | 10280 | 14 | 0.1% | trustworthy |
| NEVER_NULL | 3539 | 4 | 0.1% | trustworthy |
| ALWAYS_NULL | 402 | 0 | 0.0% | trustworthy |
| ENUM | 7380 | 0 | 0.0% | trustworthy |
| PTR_ABSENT | 229 | 0 | 0.0% | trustworthy |
| PTR_CLASS_SET | 965 | 0 | 0.0% | trustworthy |
| PTR_PRESENT | 1470 | 0 | 0.0% | trustworthy |

Rules a PASSING control of the SAME class also violates are provably not load-bearing (marked and demoted).  Per control class, how many rules the accepted objects violate, by rule type:

| control class | rules violated by the PASSING control(s) | by rule type | control sources |
|---|--:|---|---|
| SWall | 6 | RANGE×5, IDENTICAL×1 | V23, V29 |
| ConduitSizesElem | 4 | CONST_LEN×2, RANGE×1, LEN_SET×1 | T_conduit |
| RbsConduitType | 4 | NEVER_NULL×1, IDENTICAL×1, LEN_SET×1, STR_VOCAB×1 | T_conduit |
| RbsCableTrayType | 4 | NEVER_NULL×1, IDENTICAL×1, LEN_SET×1, STR_VOCAB×1 | T_conduit |
| FamilyInstance | 2 | LEN_SET×1, RANGE×1 | V21, V23, V29 |
| RbsElectricalSystem | 2 | CONST_LEN×1, IDENTICAL×1 | V29 |
| ConduitStandardType | 1 | STR_VOCAB×1 | T_conduit |
| CableTraySizesElem | 1 | CONST_LEN×1 | T_conduit |
| RbsWireMaterialType | 1 | STR_VOCAB×1 | T_conduit |

Calibrated rules that OUR FAILING objects violate too (same shape in an accepted file — these are texture, not the defect):

| class | path | rule | fail violations | control sources |
|---|---|---|--:|---|
| CableTraySizesElem | `m_sizes.m_sizeData.#len` | CONST_LEN | 1 | T_conduit |
| ConduitSizesElem | `HDR.m_parents->ElementParents.m_deletion.#len` | CONST_LEN | 1 | T_conduit |
| ConduitSizesElem | `m_sizes.#len` | CONST_LEN | 1 | T_conduit |
| ConduitSizesElem | `m_sizes[].second.m_sizeData[].m_dBendRadius` | RANGE | 1 | T_conduit |
| ConduitStandardType | `m_symbolInfo->SymbolInfo.m_name` | STR_VOCAB | 4 | T_conduit |
| RbsCableTrayType | `HDR.m_parents->ElementParents.m_deletion.#len` | LEN_SET | 3 | T_conduit |
| RbsCableTrayType | `m_previewElemId` | NEVER_NULL | 3 | T_conduit |
| RbsCableTrayType | `m_previewElemId` | IDENTICAL | 3 | T_conduit |
| RbsCableTrayType | `m_symbolInfo->SymbolInfo.m_name` | STR_VOCAB | 3 | T_conduit |
| RbsConduitType | `HDR.m_parents->ElementParents.m_deletion.#len` | LEN_SET | 5 | T_conduit |
| RbsConduitType | `m_previewElemId` | NEVER_NULL | 5 | T_conduit |
| RbsConduitType | `m_previewElemId` | IDENTICAL | 5 | T_conduit |
| RbsConduitType | `m_symbolInfo->SymbolInfo.m_name` | STR_VOCAB | 5 | T_conduit |
| RbsWireMaterialType | `m_symbolInfo->SymbolInfo.m_name` | STR_VOCAB | 1 | T_conduit |

## 4. THE BUG LIST — ranked violations by our REJECTED constructed objects

Read `support` as: this many of the class's real specimens satisfy the rule (N/N = every specimen we have, across `files` sample projects).  Read `violations` as: this many of OUR objects (in the FAILING files X5 / X9 / S5) break it, and which ladder rung they belong to (X5 = the FIRST failing rung, so its rows and X1..X4's are the prime suspects; S5 = the failing census-complete candidate).  `ours` is what our constructor emitted; `specimens say` is the mined invariant.  Header (`HDR.`), ElemTable (`ETR.`) and seq-103 (`REP.`) paths are the record-envelope shape; the rest are seq-102 object fields (`->Class` = through an owned pointer, `[]` = a container's elements, `#len` = its length, `#ptr` = which class an owned pointer slot holds, `@Class` = the class an ElementId points at).

| # | sev | class (cohort) | field path | rule | ours | specimens say | support | violations (rung: n) | score |
|--:|---|---|---|---|---|---|---|---|--:|
| 1 | CRITICAL | MaterialElem | `m_pMaterial->Material.m_asset.m_sLibrary` | NEVER_NULL | null | never null (1068/1068 specimens) | 1068/1068 · 6f | 26 (X7  patterns/materials: 13; S5 base (G1_candidate): 13) | 0.910 |
| 2 | CRITICAL | MaterialElem | `m_pMaterial->Material.m_asset.m_sName` | NEVER_NULL | null | never null (1068/1068 specimens) | 1068/1068 · 6f | 26 (X7  patterns/materials: 13; S5 base (G1_candidate): 13) | 0.910 |
| 3 | CRITICAL | MaterialElem | `m_pMaterial->Material.m_asset.m_eAssetType` | IDENTICAL | 0 | identical value 4 in ALL 1068/1068 specimens | 1068/1068 · 6f | 26 (X7  patterns/materials: 13; S5 base (G1_candidate): 13) | 0.819 |
| 4 | CRITICAL | MaterialElem | `m_pMaterial->Material.m_asset.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 1068/1068 specimens | 1068/1068 · 6f | 26 (X7  patterns/materials: 13; S5 base (G1_candidate): 13) | 0.819 |
| 5 | CRITICAL | ElectricalLoadClassification | `m_actualSpaceLoadParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.762 |
| 6 | CRITICAL | ElectricalLoadClassification | `m_demandFactorParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.762 |
| 7 | CRITICAL | ElectricalLoadClassification | `m_estCurrentParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.762 |
| 8 | CRITICAL | ElectricalLoadClassification | `m_estLoadParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.762 |
| 9 | CRITICAL | ElectricalLoadClassification | `m_totalCurrentParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.762 |
| 10 | CRITICAL | ElectricalLoadClassification | `m_totalLoadParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.762 |
| 11 | CRITICAL | FontElem | `ETR.owner_class` | NEVER_NULL | null | never null (5982/5982 specimens) | 5982/5982 · 6f | 6 (X9  view/level skeleton: 3; S5 base (G1_candidate): 3; T_settings: 2) | 0.762 |
| 12 | CRITICAL | DBViewPlan | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 13 | CRITICAL | DBViewPlan | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 14 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 15 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 16 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 17 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 18 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 19 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 20 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 21 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 22 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 23 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 24 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 25 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.725 |
| 26 | CRITICAL | SunAndShadowSettings | `HDR.m_parents->ElementParents.m_appearanceParents.#len` | CONST_LEN | 0 | length always 1 (773/773 specimens) | 773/773 · 6f | 8 (X9  view/level skeleton: 4; S5 base (G1_candidate): 4) | 0.710 |
| 27 | CRITICAL | SunAndShadowSettings | `HDR.m_parents->ElementParents.m_regenOnly.#len` | CONST_LEN | 0 | length always 1 (773/773 specimens) | 773/773 · 6f | 8 (X9  view/level skeleton: 4; S5 base (G1_candidate): 4) | 0.710 |
| 28 | CRITICAL | BasicWallType | `m_previewElemId` | NEVER_NULL | null | never null (103/103 specimens) | 103/103 · 6f | 3 (S5 base (G1_candidate): 3; T_walltype: 2) | 0.701 |
| 29 | CRITICAL | ElectricalLoadClassification | `m_actualSpaceLoadParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.686 |
| 30 | CRITICAL | ElectricalLoadClassification | `m_demandFactorParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.686 |
| 31 | CRITICAL | ElectricalLoadClassification | `m_estCurrentParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.686 |
| 32 | CRITICAL | ElectricalLoadClassification | `m_estLoadParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.686 |
| 33 | CRITICAL | ElectricalLoadClassification | `m_totalCurrentParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.686 |
| 34 | CRITICAL | ElectricalLoadClassification | `m_totalLoadParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.686 |
| 35 | CRITICAL | FontElem | `ETR.has_owner` | IDENTICAL | False | identical value True in ALL 5982/5982 specimens | 5982/5982 · 6f | 6 (X9  view/level skeleton: 3; S5 base (G1_candidate): 3; T_settings: 2) | 0.686 |
| 36 | CRITICAL | ElectricalLoadClassification | `HDR.m_parents->ElementParents.m_deletion.#len` | CONST_LEN | 2 | length always 8 (70/70 specimens) | 70/70 · 6f | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 0.685 |
| 37 | CRITICAL | TextNoteAttributes | `ETR.owned.#len` | CONST_LEN | 0 | length always 2 (2026/2026 specimens) | 2026/2026 · 6f | 6 (X9  view/level skeleton: 3; S5 base (G1_candidate): 3; T_settings: 2) | 0.685 |
| 38 | CRITICAL | Viewer3d | `HDR.m_pBBox.#ptr` | PTR_PRESENT | null (no owned sub-object) | owned sub-object ALWAYS present (135/135 specimens) | 135/135 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.670 |
| 39 | CRITICAL | Viewer3d | `m_geomSteps.#ptr` | PTR_PRESENT | null (no owned sub-object) | owned sub-object ALWAYS present (135/135 specimens) | 135/135 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.670 |
| 40 | CRITICAL | DBDrawing | `ETR.owner_class` | NEVER_NULL | null | never null (831/831 specimens) | 831/831 · 6f | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 0.669 |
| 41 | CRITICAL | DBView3d | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 42 | CRITICAL | DBView3d | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 43 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 44 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 45 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 46 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 47 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 48 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 49 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 50 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 51 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 52 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 53 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 54 | CRITICAL | DBView3d | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 · 6f | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 0.669 |
| 55 | CRITICAL | Viewer | `ETR.owner_class` | NEVER_NULL | null | never null (507/507 specimens) | 507/507 · 6f | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 0.669 |
| 56 | CRITICAL | Viewport | `ETR.owner_class` | NEVER_NULL | null | never null (1028/1028 specimens) | 1028/1028 · 6f | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 0.669 |
| 57 | CRITICAL | DBViewPlan | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 303/303 specimens | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.653 |
| 58 | CRITICAL | DBViewPlan | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 303/303 specimens | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.653 |
| 59 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 303/303 specimens | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.653 |
| 60 | CRITICAL | DBViewPlan | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | IDENTICAL | null | identical value Generic in ALL 303/303 specimens | 303/303 · 6f | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 0.653 |
| … | | (338 more findings in the JSON) | | | | | | | |

## 5. Per-class findings (all rejected-object violations, by class)

### MaterialElem  — 4 finding(s); 1068 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_pMaterial->Material.m_asset.m_sLibrary` | NEVER_NULL | null | never null (1068/1068 specimens) | 1068/1068 | 26 (X7  patterns/materials: 13; S5 base (G1_candidate): 13) | 2100009, 2100010, 2100011, 2100012 |
| CRITICAL | `m_pMaterial->Material.m_asset.m_sName` | NEVER_NULL | null | never null (1068/1068 specimens) | 1068/1068 | 26 (X7  patterns/materials: 13; S5 base (G1_candidate): 13) | 2100009, 2100010, 2100011, 2100012 |
| CRITICAL | `m_pMaterial->Material.m_asset.m_eAssetType` | IDENTICAL | 0 | identical value 4 in ALL 1068/1068 specimens | 1068/1068 | 26 (X7  patterns/materials: 13; S5 base (G1_candidate): 13) | 2100009, 2100010, 2100011, 2100012 |
| CRITICAL | `m_pMaterial->Material.m_asset.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 1068/1068 specimens | 1068/1068 | 26 (X7  patterns/materials: 13; S5 base (G1_candidate): 13) | 2100009, 2100010, 2100011, 2100012 |

### ElectricalLoadClassification  — 19 finding(s); 70 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_actualSpaceLoadParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_demandFactorParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_estCurrentParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_estLoadParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_totalCurrentParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_totalLoadParamElemId` | NEVER_NULL | null | never null (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_actualSpaceLoadParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_demandFactorParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_estCurrentParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_estLoadParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_totalCurrentParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `m_totalLoadParamElemId` | IDENTICAL | null | identical value @ParamElemElectricalLoadClassification in ALL 70/70 specimens | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| CRITICAL | `HDR.m_parents->ElementParents.m_deletion.#len` | CONST_LEN | 2 | length always 8 (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6; T_settings: 3) | 1500044, 1500045, 1500046, 1500047 |
| MEDIUM | `m_actualElectricalLoadLabel` | STR_VOCAB | %1!s! - Actual Load | value always in {Actual %1!s! Load, Tatsächliche %1!s!-Last, 实际 %1!s! 负荷} (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6) | 1500044, 1500045, 1500046, 1500047 |
| MEDIUM | `m_loadSummaryDemandFactorLabel` | STR_VOCAB | %1!s! - Demand Factor | value always in {%1!s! - Gleichzeitigkeit, %1!s! Demand Factor, %1!s! Gleichzeitigkeit, %1!s! 需求系数} (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6) | 1500044, 1500045, 1500046, 1500047 |
| MEDIUM | `m_panelConnectedCurrentLabel` | STR_VOCAB | %1!s! - Connected Current | value always in {%1!s! - angeschlossen aktuell, %1!s! Connected Current, %1!s! angeschlossen aktuell, %1!s! 连接电流} (70... | 70/70 | 6 (S5 base (G1_candidate): 6) | 1500044, 1500045, 1500046, 1500047 |
| MEDIUM | `m_panelConnectedLabel` | STR_VOCAB | %1!s! - Connected Load | value always in {%1!s! - Verbunden, %1!s! Connected Apparent Power, %1!s! angeschlossen, %1!s! 已连接} (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6) | 1500044, 1500045, 1500046, 1500047 |
| MEDIUM | `m_panelEstimatedCurrentLabel` | STR_VOCAB | %1!s! - Demand Current | value always in {%1!s! - geschätzte Bedarfslast aktuell, %1!s! Estimated Demand Current, %1!s! 估计需用电流} (70/70 specimens) | 70/70 | 6 (S5 base (G1_candidate): 6) | 1500044, 1500045, 1500046, 1500047 |
| MEDIUM | `m_panelEstimatedLabel` | STR_VOCAB | %1!s! - Demand Load | value always in {%1!s! - Geschätzter Bedarf, %1!s! - geschätzter Bedarf, %1!s! Demand Apparent Power, %1!s! 估计需求} (70... | 70/70 | 6 (S5 base (G1_candidate): 6) | 1500044, 1500045, 1500046, 1500047 |

### FontElem  — 2 finding(s); 5982 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `ETR.owner_class` | NEVER_NULL | null | never null (5982/5982 specimens) | 5982/5982 | 6 (X9  view/level skeleton: 3; S5 base (G1_candidate): 3; T_settings: 2) | 2300078, 2300082, 2300086, 1500078 |
| CRITICAL | `ETR.has_owner` | IDENTICAL | False | identical value True in ALL 5982/5982 specimens | 5982/5982 | 6 (X9  view/level skeleton: 3; S5 base (G1_candidate): 3; T_settings: 2) | 2300078, 2300082, 2300086, 1500078 |

### DBViewPlan  — 34 finding(s); 303 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (303/303 specimens) | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | IDENTICAL | null | identical value Generic in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | IDENTICAL | null | identical value SunAndSky-002 in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sName` | IDENTICAL | null | identical value Generic in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sName` | IDENTICAL | null | identical value Generic in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 303/303 specimens | 303/303 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300220, 2300227, 1500220, 1500227 |
| … | (9 more) | | | | | | |

### SunAndShadowSettings  — 2 finding(s); 773 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `HDR.m_parents->ElementParents.m_appearanceParents.#len` | CONST_LEN | 0 | length always 1 (773/773 specimens) | 773/773 | 8 (X9  view/level skeleton: 4; S5 base (G1_candidate): 4) | 2300204, 2300215, 2300223, 2300230 |
| CRITICAL | `HDR.m_parents->ElementParents.m_regenOnly.#len` | CONST_LEN | 0 | length always 1 (773/773 specimens) | 773/773 | 8 (X9  view/level skeleton: 4; S5 base (G1_candidate): 4) | 2300204, 2300215, 2300223, 2300230 |

### BasicWallType  — 3 finding(s); 103 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_previewElemId` | NEVER_NULL | null | never null (103/103 specimens) | 103/103 | 3 (S5 base (G1_candidate): 3; T_walltype: 2) | 1500022, 1500023, 1500024, 888021 |
| CRITICAL | `m_previewElemId` | IDENTICAL | null | identical value @LegendComponent in ALL 103/103 specimens | 103/103 | 3 (S5 base (G1_candidate): 3; T_walltype: 2) | 1500022, 1500023, 1500024, 888021 |
| HIGH | `m_pCompoundStructure->CompoundStructure.m_oVertRegStructure->VerticalRegionsStructure.m_cutOffHeight` | ENUM | 20 | value always in {10, 16.4042, 19.685, 9.02231} (103/103 specimens) | 103/103 | 3 (S5 base (G1_candidate): 3; T_walltype: 2) | 1500022, 1500023, 1500024, 888021 |

### TextNoteAttributes  — 3 finding(s); 2026 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `ETR.owned.#len` | CONST_LEN | 0 | length always 2 (2026/2026 specimens) | 2026/2026 | 6 (X9  view/level skeleton: 3; S5 base (G1_candidate): 3; T_settings: 2) | 2300077, 2300081, 2300085, 1500077 |
| HIGH | `ETR.owned[]` | OWNED_CHILD | owns nothing | every specimen owns a @CategoryElem row in the ElemTable (2026/2026 specimens) | 2026/2026 | 12 (X9  view/level skeleton: 6; S5 base (G1_candidate): 6; T_settings: 4) | 2300077, 2300077, 2300081, 2300081 |
| HIGH | `m_leaderOffsetSheet` | ENUM | 0.00666667 | value always in {0, 0.00164042, 0.00328084, 0.00656168, 0.00666667} (2026/2026 specimens) | 2026/2026 | 6 (X9  view/level skeleton: 3; S5 base (G1_candidate): 3; T_settings: 2) | 2300077, 2300081, 2300085, 1500077 |

### Viewer3d  — 5 finding(s); 135 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `HDR.m_pBBox.#ptr` | PTR_PRESENT | null (no owned sub-object) | owned sub-object ALWAYS present (135/135 specimens) | 135/135 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300213, 1500213 |
| CRITICAL | `m_geomSteps.#ptr` | PTR_PRESENT | null (no owned sub-object) | owned sub-object ALWAYS present (135/135 specimens) | 135/135 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300213, 1500213 |
| CRITICAL | `HDR.m_pBBox.#ptr` | IDENTICAL | null | identical value Outline in ALL 135/135 specimens | 135/135 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300213, 1500213 |
| CRITICAL | `REP.seq103_class` | IDENTICAL | SerializedDummy | identical value GElement in ALL 135/135 specimens | 135/135 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300213, 1500213 |
| CRITICAL | `m_geomSteps.#ptr` | IDENTICAL | null | identical value GeomStepList in ALL 135/135 specimens | 135/135 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300213, 1500213 |

### DBDrawing  — 3 finding(s); 831 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `ETR.owner_class` | NEVER_NULL | null | never null (831/831 specimens) | 831/831 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600011, 1600099 |
| CRITICAL | `ETR.has_owner` | IDENTICAL | False | identical value True in ALL 831/831 specimens | 831/831 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600011, 1600099 |
| LOW | `ETR.owned.#len` | RANGE | 0 | range [1 .. 14] over 831/831 specimens | 831/831 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600011, 1600099 |

### DBView3d  — 32 finding(s); 142 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (142/142 specimens) | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | IDENTICAL | null | identical value Generic in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | IDENTICAL | null | identical value SunAndSky-002 in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sName` | IDENTICAL | null | identical value Generic in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sName` | IDENTICAL | null | identical value Generic in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 142/142 specimens | 142/142 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300212, 1500212 |
| … | (7 more) | | | | | | |

### Viewer  — 5 finding(s); 507 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `ETR.owner_class` | NEVER_NULL | null | never null (507/507 specimens) | 507/507 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600009, 1600097 |
| CRITICAL | `m_boundedSpace.m_isOn` | IDENTICAL | False | identical value True in ALL 507/507 specimens | 507/507 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300221, 2300228, 1500221, 1500228 |
| CRITICAL | `m_intentionallyPlaced` | IDENTICAL | True | identical value False in ALL 507/507 specimens | 507/507 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300221, 2300228, 1500221, 1500228 |
| CRITICAL | `m_projMethodType` | IDENTICAL | 2 | identical value 1 in ALL 507/507 specimens | 507/507 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300221, 2300228, 1500221, 1500228 |
| CRITICAL | `ETR.has_owner` | IDENTICAL | False | identical value True in ALL 507/507 specimens | 507/507 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600009, 1600097 |

### Viewport  — 4 finding(s); 1028 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `ETR.owner_class` | NEVER_NULL | null | never null (1028/1028 specimens) | 1028/1028 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600010, 1600098 |
| CRITICAL | `ETR.has_owner` | IDENTICAL | False | identical value True in ALL 1028/1028 specimens | 1028/1028 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600010, 1600098 |
| CRITICAL | `ETR.owner_class` | IDENTICAL | null | identical value @DBDrawing in ALL 1028/1028 specimens | 1028/1028 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600010, 1600098 |
| HIGH | `HDR.m_parents->ElementParents.m_appearanceParents.#len` | LEN_SET | 2 | length always in [0, 3] (1028/1028 specimens) | 1028/1028 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600010, 1600098 |

### GeoSite  — 7 finding(s); 12 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_weatherStationName` | NEVER_NULL | null | never null (12/12 specimens) | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200186, 2200187, 1500186, 1500187 |
| CRITICAL | `m_zipCodeOrPostalCode` | NEVER_NULL | null | never null (12/12 specimens) | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200186, 2200187, 1500186, 1500187 |
| HIGH | `m_zipCodeOrPostalCode` | IDENTICAL | null | identical value 00000 in ALL 12/12 specimens | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200186, 2200187, 1500186, 1500187 |
| HIGH | `m_dTimeZone` | ENUM | 0 | value always in {-5, 1} (12/12 specimens) | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200186, 2200187, 1500186, 1500187 |
| LOW | `m_dMeanDailyTemperature[]` | RANGE | 288.15  [12 leaves] | range [260.2 .. 271.039] over 144 elements over 12/12 specimens | 12/12 sp (144 obs) | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200186, 2200187, 1500186, 1500187 |
| LOW | `m_dLatitude` | RANGE | 0 | range [0.736756 .. 0.840079] over 12/12 specimens | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200186, 2200187, 1500186, 1500187 |
| LOW | `m_dWinterDryBulbTemperature` | RANGE | 288.15 | range [256.594 .. 261.872] over 12/12 specimens | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200186, 2200187, 1500186, 1500187 |

### RevisionNumberingSequence  — 3 finding(s); 12 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `ETR.owner_class` | NEVER_NULL | null | never null (12/12 specimens) | 12/12 | 4 (X5  remaining singletons: 2; S5 singletons+catalog: 2) | 1900044, 1900045, 1600073, 1600074 |
| HIGH | `ETR.has_owner` | IDENTICAL | False | identical value True in ALL 12/12 specimens | 12/12 | 4 (X5  remaining singletons: 2; S5 singletons+catalog: 2) | 1900044, 1900045, 1600073, 1600074 |
| HIGH | `ETR.owner_class` | IDENTICAL | null | identical value @AllProjectRevisions in ALL 12/12 specimens | 12/12 | 4 (X5  remaining singletons: 2; S5 singletons+catalog: 2) | 1900044, 1900045, 1600073, 1600074 |

### FloorAttributes  — 2 finding(s); 87 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_previewElemId` | NEVER_NULL | null | never null (87/87 specimens) | 87/87 | 1 (S5 base (G1_candidate): 1; T_walltype: 1) | 1500025, 888023 |
| CRITICAL | `m_previewElemId` | IDENTICAL | null | identical value @LegendComponent in ALL 87/87 specimens | 87/87 | 1 (S5 base (G1_candidate): 1; T_walltype: 1) | 1500025, 888023 |

### RoofAttributes  — 4 finding(s); 28 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_previewElemId` | NEVER_NULL | null | never null (28/28 specimens) | 28/28 | 1 (S5 base (G1_candidate): 1; T_walltype: 1) | 1500026, 888024 |
| CRITICAL | `m_previewElemId` | IDENTICAL | null | identical value @LegendComponent in ALL 28/28 specimens | 28/28 | 1 (S5 base (G1_candidate): 1; T_walltype: 1) | 1500026, 888024 |
| HIGH | `m_pCompoundStructure->CompoundStructure.m_numShellLayersExt` | ENUM | 1 | value always in {0, 2, 4} (28/28 specimens) | 28/28 | 1 (S5 base (G1_candidate): 1) | 1500026 |
| HIGH | `m_pCompoundStructure->CompoundStructure.m_structuralMaterialLayerIndex` | ENUM | 1 | value always in {-1, 0, 2, 3, 5, 6} (28/28 specimens) | 28/28 | 1 (S5 base (G1_candidate): 1) | 1500026 |

### Level  — 6 finding(s); 131 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_refPointsForNewViews[0][2]` | IDENTICAL | 12 | identical value 0 in ALL 131/131 specimens | 131/131 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300194, 1500194 |
| CRITICAL | `m_refPointsForNewViews[1][2]` | IDENTICAL | 12 | identical value 0 in ALL 131/131 specimens | 131/131 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300194, 1500194 |
| HIGH | `m_bubbleEnd[0]` | ENUM | 40 | value always in {0, 30} (131/131 specimens) | 131/131 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300193, 2300194, 1500193, 1500194 |
| HIGH | `m_refPointsForNewViews[1][0]` | ENUM | 40 | value always in {0, 30} (131/131 specimens) | 131/131 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300193, 2300194, 1500193, 1500194 |
| HIGH | `m_bubbleEnd[2]` | ENUM | 12 | value always in {0, 13.1234} (131/131 specimens) | 131/131 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300194, 1500194 |
| HIGH | `m_freeEnd[2]` | ENUM | 12 | value always in {0, 13.1234} (131/131 specimens) | 131/131 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300194, 1500194 |

### RbsPipeSettingsElem  — 23 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_mapSystemTypeToPipeSettings[].second.m_dMinLength` | IDENTICAL | 3  [14 leaves] | identical value 2.08333 in ALL 84 elements over 6/6 specimens | 6/6 sp (84 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| CRITICAL | `m_flowConvertionServerInfo.m_description` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| CRITICAL | `m_flowConvertionServerInfo.m_serverId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| CRITICAL | `m_flowConvertionServerInfo.m_serverName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| CRITICAL | `m_pressLossCalcServerInfo.m_description` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| CRITICAL | `m_pressLossCalcServerInfo.m_serverId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| CRITICAL | `m_pressLossCalcServerInfo.m_serverName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_eDiping1LineBendDropType` | IDENTICAL | 3 | identical value 13 in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_eDiping1LineJunctionDropType` | IDENTICAL | 3 | identical value 15 in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_eDipingContourDropType` | IDENTICAL | 3 | identical value 11 in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_flowConvertionServerInfo.m_serverId` | IDENTICAL | null | identical value 56121d7d-e1d7-42a3-bed8-f4d1d32058c8 in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_pressLossCalcServerInfo.m_description` | IDENTICAL | null | identical value Computes Friction Factor using Colebrook Equation. in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_pressLossCalcServerInfo.m_serverId` | IDENTICAL | null | identical value 0875f550-6141-4e34-a6b7-547cf9cfda01 in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_pressLossCalcServerInfo.m_serverName` | IDENTICAL | null | identical value Colebrook Equation in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_strPipeSizeSuffix` | IDENTICAL | " | identical value ø in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_pipeSlopes.#len` | CONST_LEN | 8 | length always 12 (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_mapSystemTypeToPipeSettings[].second.m_dOffset` | ENUM | 10  [14 leaves] | value always in {0, 8.99934, 9, 9.02231} (84 elements over 6/6 specimens) | 6/6 sp (84 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| HIGH | `m_mapSystemTypeToPipeSettings[].second.m_dPerimeterInsetLength` | ENUM | 1.5  [14 leaves] | value always in {0.738189, 0.75} (84 elements over 6/6 specimens) | 6/6 sp (84 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| MEDIUM | `m_dPipeConnectorTolerance` | ENUM | 0.174533 | value always in {0.0872665, 0.174533} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| MEDIUM | `m_dPipeRiseDropAnnoSize` | ENUM | 0.0078125 | value always in {0.00984252, 0.0104167} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| LOW | `m_flowConvertionServerInfo.m_description` | STR_VOCAB | null | value always in {Calculation of flow using the Plumbing Fixture Flow method., Durchflussberechnung über Durchfluss na... | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| LOW | `m_flowConvertionServerInfo.m_serverName` | STR_VOCAB | null | value always in {Durchfluss in Sanitärinstallation, Plumbing Fixture Flow} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |
| LOW | `m_dPipeFittingAnnotationSize` | RANGE | 0.0078125 | range [0.00984252 .. 0.0104987] over 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800002, 1600026 |

### AreaMeasureElem  — 7 finding(s); 14 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_areaSchemePlanTopologyElemId` | NEVER_NULL | null | never null (14/14 specimens) | 14/14 | 2 (S5 singletons+catalog: 2) | 1600078, 1600079 |
| CRITICAL | `m_defaultSpaceElemId` | NEVER_NULL | null | never null (14/14 specimens) | 14/14 | 2 (S5 singletons+catalog: 2) | 1600078, 1600079 |
| CRITICAL | `m_areaSchemePlanTopologyElemId` | IDENTICAL | null | identical value @AreaSchemePlanTopologies in ALL 14/14 specimens | 14/14 | 2 (S5 singletons+catalog: 2) | 1600078, 1600079 |
| CRITICAL | `m_defaultSpaceElemId` | IDENTICAL | null | identical value @AreaTypeElem in ALL 14/14 specimens | 14/14 | 2 (S5 singletons+catalog: 2) | 1600078, 1600079 |
| HIGH | `ETR.id_band` | ENUM | <5M | value always in {<50k, <5k} (14/14 specimens) | 14/14 | 4 (X5  remaining singletons: 2; S5 singletons+catalog: 2) | 1900051, 1900052, 1600078, 1600079 |
| MEDIUM | `HDR.m_parents->ElementParents.m_deletion.#len` | LEN_SET | 1 | length always in [4, 8] (14/14 specimens) | 14/14 | 2 (S5 singletons+catalog: 2) | 1600078, 1600079 |
| MEDIUM | `m_areaTypeElemSet.#len` | LEN_SET | 0 | length always in [2, 6] (14/14 specimens) | 14/14 | 2 (S5 singletons+catalog: 2) | 1600078, 1600079 |

### RbsDuctSettingsElem  — 16 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_mapDuctSystemTypeToSettings[].second.m_dBranchMinLength` | IDENTICAL | 3  [5 leaves] | identical value 2.08333 in ALL 28 elements over 6/6 specimens | 6/6 sp (28 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| CRITICAL | `m_mapDuctSystemTypeToSettings[].second.m_dMainMinLength` | IDENTICAL | 3  [5 leaves] | identical value 2.08333 in ALL 28 elements over 6/6 specimens | 6/6 sp (28 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| CRITICAL | `m_pressLossCalcServerInfo.m_description` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| CRITICAL | `m_pressLossCalcServerInfo.m_serverId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| CRITICAL | `m_pressLossCalcServerInfo.m_serverName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| HIGH | `m_pressLossCalcServerInfo.m_serverId` | IDENTICAL | null | identical value 042a10e0-8d24-46a4-9596-d192b3125d0c in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| HIGH | `m_strRoundDuctSizeSuffix` | IDENTICAL | " | identical value ø in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| HIGH | `m_mapDuctSystemTypeToSettings[].second.m_dMainOffset` | ENUM | 10  [5 leaves] | value always in {10.0066, 8.99934, 9, 9.02231} (28 elements over 6/6 specimens) | 6/6 sp (28 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| HIGH | `m_mapDuctSystemTypeToSettings[].second.m_dPerimeterInsetLength` | ENUM | 1.5  [5 leaves] | value always in {0.75, 3.28084, 4} (28 elements over 6/6 specimens) | 6/6 sp (28 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| HIGH | `m_mapDuctRiseDropSettings[].second` | ENUM | 1  [3 leaves] | value always in {2, 4, 8} (18 elements over 6/6 specimens) | 6/6 sp (18 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| MEDIUM | `m_airDynamicViscosity` | ENUM | 5.52602e-06 | value always in {5.50119e-06, 5.52543e-06} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| MEDIUM | `m_dAirDensity` | ENUM | 0.0340963 | value always in {0.0340538, 0.0340544} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| MEDIUM | `m_dDuctFittingAnnotationSize` | ENUM | 0.0078125 | value always in {0.00984252, 0.0104167} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| LOW | `m_pressLossCalcServerInfo.m_description` | STR_VOCAB | null | value always in {Berechnung des Druckverlusts in Luftkanälen nach Darcy, Calculation of duct pressure drop using Darc... | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| LOW | `m_pressLossCalcServerInfo.m_serverName` | STR_VOCAB | null | value always in {Druckverlust in Luftkanal, Duct Pressure Drop} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |
| LOW | `m_dDuctRiseDropAnnoSize` | RANGE | 0.0078125 | range [0.00984252 .. 0.0104987] over 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800004, 1600027 |

### LevelAttributes  — 11 finding(s); 13 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_leaderCategoryId` | NEVER_NULL | null | never null (13/13 specimens) | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| CRITICAL | `m_lineAndTextAttr.m_categoryId` | NEVER_NULL | null | never null (13/13 specimens) | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| CRITICAL | `m_lineAndTextAttr.m_fontId` | NEVER_NULL | null | never null (13/13 specimens) | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| HIGH | `m_leaderCategoryId` | IDENTICAL | null | identical value @CategoryElem in ALL 13/13 specimens | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| HIGH | `m_lineAndTextAttr.m_categoryId` | IDENTICAL | null | identical value @CategoryElem in ALL 13/13 specimens | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| HIGH | `m_lineAndTextAttr.m_fontId` | IDENTICAL | null | identical value @FontElem in ALL 13/13 specimens | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| HIGH | `HDR.m_parents->ElementParents.m_regenOnly.#len` | CONST_LEN | 0 | length always 2 (13/13 specimens) | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| HIGH | `ETR.owned[]` | OWNED_CHILD | owns nothing | every specimen owns a @CategoryElem row in the ElemTable (13/13 specimens) | 13/13 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300192, 2300192, 1500192, 1500192 |
| HIGH | `m_roomComputationUserHeight` | ENUM | 4 | value always in {0, 3.93701} (13/13 specimens) | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| MEDIUM | `ETR.owned.#len` | LEN_SET | 0 | length always in [3, 4] (13/13 specimens) | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |
| MEDIUM | `HDR.m_parents->ElementParents.m_deletion.#len` | LEN_SET | 1 | length always in [5, 6] (13/13 specimens) | 13/13 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300192, 1500192 |

### CompoundCeilingType  — 4 finding(s); 18 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_previewElemId` | NEVER_NULL | null | never null (18/18 specimens) | 18/18 | 1 (S5 base (G1_candidate): 1; T_walltype: 1) | 1500027, 888025 |
| CRITICAL | `m_previewElemId` | IDENTICAL | null | identical value @LegendComponent in ALL 18/18 specimens | 18/18 | 1 (S5 base (G1_candidate): 1; T_walltype: 1) | 1500027, 888025 |
| MEDIUM | `m_pCompoundStructure->CompoundStructure.m_structuralMaterialLayerIndex` | ENUM | 1 | value always in {-1, 0} (12/18 specimens) | 12/18 | 1 (S5 base (G1_candidate): 1; T_walltype: 1) | 1500027, 888025 |
| LOW | `m_pCompoundStructure->CompoundStructure.m_numShellLayersExt` | RANGE | 1 | range [0 .. 0] over 12/18 specimens | 12/18 | 1 (S5 base (G1_candidate): 1; T_walltype: 1) | 1500027, 888025 |

### BasePoint  — 3 finding(s); 12 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `HDR.m_parents->ElementParents.m_hasNonDetermRegenChildren` | IDENTICAL | False | identical value True in ALL 12/12 specimens | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200190, 2200191, 1500190, 1500191 |
| HIGH | `HDR.m_parents->ElementParents.m_regenOnly.#len` | CONST_LEN | 1 | length always 2 (12/12 specimens) | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200190, 2200191, 1500190, 1500191 |
| MEDIUM | `HDR.m_parents->ElementParents.m_nonDetermRegenChildren.#len` | LEN_SET | 0 | length always in [1, 2] (12/12 specimens) | 12/12 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200190, 2200191, 1500190, 1500191 |

### ProjectRevision  — 2 finding(s); 7 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_date` | NEVER_NULL | null | never null (7/7 specimens) | 7/7 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900046, 1600075 |
| CRITICAL | `m_description` | NEVER_NULL | null | never null (7/7 specimens) | 7/7 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900046, 1600075 |

### CoordinateSystemDisplayElem  — 6 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_geomSteps.#ptr` | PTR_PRESENT | null (no owned sub-object) | owned sub-object ALWAYS present (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900036, 1600059 |
| CRITICAL | `m_pGeomTable.#ptr` | PTR_PRESENT | null (no owned sub-object) | owned sub-object ALWAYS present (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900036, 1600059 |
| HIGH | `REP.seq103_class` | IDENTICAL | SerializedDummy | identical value GElement in ALL 6/6 specimens | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900036, 1600059 |
| HIGH | `m_geomSteps.#ptr` | IDENTICAL | null | identical value GeomStepList in ALL 6/6 specimens | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900036, 1600059 |
| HIGH | `m_pGeomTable.#ptr` | IDENTICAL | null | identical value GeomTable in ALL 6/6 specimens | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900036, 1600059 |
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<500k, <5k} (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900036, 1600059 |

### DBViewProject  — 35 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_customQualityAsset.m_sName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_oStaticRRTRenderSettings->GRenderSettings.m_oExposureAssets.m_sName` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `ETR.created_at_birth` | IDENTICAL | False | identical value True in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `ETR.id_band` | IDENTICAL | <5M | identical value <5k in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pViewDisplayMgr->ViewDisplayMgr.m_model.m_surfaces` | IDENTICAL | 2 | identical value 1 in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_customQualityAsset.m_sName` | IDENTICAL | null | identical value Generic in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oEnvironmentAssets.m_sName` | IDENTICAL | null | identical value SunAndSky-002 in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sLibrary` | IDENTICAL | null | identical value assetlibrary_base.fbx in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| HIGH | `m_pViewDisplayMgr->ViewDisplayMgr.m_oRaytraceSettings->GRenderSettings.m_oExposureAssets.m_sName` | IDENTICAL | null | identical value Generic in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300205, 1500205 |
| … | (10 more) | | | | | | |

### EnergyDataSettings  — 6 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_reportsFolder` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900040, 1600072 |
| CRITICAL | `m_buildingTypeId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 1 (S5 singletons+catalog: 1) | 1600072 |
| HIGH | `m_reportsFolder` | IDENTICAL | null | identical value .\<ProjectName>_Reports in ALL 6/6 specimens | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900040, 1600072 |
| HIGH | `m_cellList->CellList.m_cells[]->ExternalResourceReferenceCell.m_externalResourceReferencesExpanded.#len` | CONST_LEN | 0 | length always 1 (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900040, 1600072 |
| HIGH | `m_buildingTypeId` | IDENTICAL | null | identical value @HVACLoadBuildingTypeElem in ALL 6/6 specimens | 6/6 | 1 (S5 singletons+catalog: 1) | 1600072 |
| HIGH | `HDR.m_parents->ElementParents.m_deletion.#len` | CONST_LEN | 3 | length always 4 (6/6 specimens) | 6/6 | 1 (S5 singletons+catalog: 1) | 1600072 |

### RbsDbViewSystemNavigator  — 11 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600008, 1600096 |
| CRITICAL | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600008, 1600096 |
| CRITICAL | `m_pViewDisplayMgr->ViewDisplayMgr.m_lights.m_sunAndShadowSettingsId` | NEVER_NULL | null | never null (6/6 specimens) | 6/6 | 1 (X2  browser/navigator: 1) | 1600008 |
| HIGH | `m_pRetouchTable->RetouchTable.m_invisibleGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 6/6 specimens | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600008, 1600096 |
| HIGH | `m_pRetouchTable->RetouchTable.m_notSilhouetteGStyleId` | IDENTICAL | null | identical value @GStyleElem in ALL 6/6 specimens | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600008, 1600096 |
| HIGH | `ETR.owned.#len` | CONST_LEN | 0 | length always 2 (6/6 specimens) | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600008, 1600096 |
| HIGH | `m_pViewDisplayMgr->ViewDisplayMgr.m_lights.m_sunAndShadowSettingsId` | IDENTICAL | null | identical value @SunAndShadowSettings in ALL 6/6 specimens | 6/6 | 1 (X2  browser/navigator: 1) | 1600008 |
| HIGH | `ETR.owned[]` | OWNED_CHILD | owns nothing | every specimen owns a @DBDrawing row in the ElemTable (6/6 specimens) | 6/6 | 4 (X2  browser/navigator: 2; S5 singletons+catalog: 2) | 1600008, 1600008, 1600096, 1600096 |
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<500k, <5k} (6/6 specimens) | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600008, 1600096 |
| LOW | `HDR.m_parents->ElementParents.m_deletion.#len` | RANGE | 3 | range [7 .. 9] over 6/6 specimens | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600008, 1600096 |
| LOW | `m_oaDrawFilters[]->IckyExcludedCategoriesSetPtrWrapper.m_categoryIds.#len` | RANGE | 0 | range [57 .. 69] over 6/6 specimens | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600008, 1600096 |

### ConstructionSetProject  — 20 finding(s); 5 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_strCeiling` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strDoor` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strExternalWall` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strExternalWindow` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strFloor` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strInternalWindow` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strPartition` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strRoof` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strRoofLight` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strSolidGround` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strUndergroundWall` | NEVER_NULL | null | never null (5/5 specimens) | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `ETR.id_band` | IDENTICAL | <5M | identical value <500k in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strCeiling` | IDENTICAL | null | identical value ASHIF5 in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strDoor` | IDENTICAL | null | identical value MDOOR in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strFloor` | IDENTICAL | null | identical value con-c23 in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strInternalWindow` | IDENTICAL | null | identical value SGLI in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strPartition` | IDENTICAL | null | identical value ASHIW23 in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strRoofLight` | IDENTICAL | null | identical value DGL-R-IR in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strSolidGround` | IDENTICAL | null | identical value SGFLR in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |
| HIGH | `m_strUndergroundWall` | IDENTICAL | null | identical value ASHWL-11 in ALL 5/5 specimens | 5/5 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600007, 1600008 |

### AllProjectPhases  — 14 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `ETR.created_at_birth` | IDENTICAL | False | identical value True in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| HIGH | `ETR.id_band` | IDENTICAL | <5M | identical value <5k in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| HIGH | `m_arrPhasingOverrides[0]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oProjPenNumber->GPenNumberOverrider.m_penNumber` | IDENTICAL | 1 | identical value 2 in ALL 6/6 specimens | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[0]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oCutPenColor->GStyleColorOverrider.m_color` | ENUM | 9211020 | value always in {0, 8355711} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[0]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oProjPenColor->GStyleColorOverrider.m_color` | ENUM | 9211020 | value always in {0, 8355711} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[1]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oCutPenColor->GStyleColorOverrider.m_color` | ENUM | 7237230 | value always in {0, 32896} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[1]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oCutPenNumber->GPenNumberOverrider.m_penNumber` | ENUM | 1 | value always in {2, 3} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[1]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oProjPenColor->GStyleColorOverrider.m_color` | ENUM | 7237230 | value always in {0, 32896} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[2]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oCutPenNumber->GPenNumberOverrider.m_penNumber` | ENUM | 4 | value always in {2, 5} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[2]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oProjPenNumber->GPenNumberOverrider.m_penNumber` | ENUM | 1 | value always in {2, 4} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[3]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oCutFillColor->GFillColorOverrider.m_color` | ENUM | 14470600 | value always in {12615680, 8323072} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[3]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oCutPenColor->GStyleColorOverrider.m_color` | ENUM | 9198150 | value always in {16711680, 8323072} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[3]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oCutPenNumber->GPenNumberOverrider.m_penNumber` | ENUM | 1 | value always in {2, 3} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |
| MEDIUM | `m_arrPhasingOverrides[3]->PhasingOverrides.m_oOverrideGraphicSettings->OverrideGraphicSettings.m_oProjPenColor->GStyleColorOverrider.m_color` | ENUM | 9198150 | value always in {16711680, 8323072} (6/6 specimens) | 6/6 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300195, 1500195 |

### AllProjectRevisions  — 4 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_minSpacingForCloud` | IDENTICAL | 0.0625 | identical value 0.0656168 in ALL 6/6 specimens | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900047, 1600076 |
| HIGH | `ETR.owned.#len` | CONST_LEN | 0 | length always 2 (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900047, 1600076 |
| HIGH | `ETR.owned[]` | OWNED_CHILD | owns nothing | every specimen owns a @RevisionNumberingSequence row in the ElemTable (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900047, 1600076 |
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<50k, <5k} (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900047, 1600076 |

### CableTraySettingsElem  — 4 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_bUseAnnoScaleFor1LineFittings` | IDENTICAL | True | identical value False in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800007, 1600025 |
| MEDIUM | `m_dFittingAnnotationSize` | ENUM | 0.0078125 | value always in {0.0102526, 0.0104987} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800007, 1600025 |
| LOW | `m_strSizeSuffix` | STR_VOCAB | " | value always in {null, ø} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800007, 1600025 |
| LOW | `m_dRiseDropAnnotationSize` | RANGE | 0.0078125 | range [0.0102526 .. 0.0104331] over 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800007, 1600025 |

### ConduitSettingsElem  — 6 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_bUseAnnoScaleFor1LineFittings` | IDENTICAL | True | identical value False in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800006, 1600024 |
| HIGH | `m_e1LineDropType` | IDENTICAL | 3 | identical value 10 in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800006, 1600024 |
| HIGH | `m_eContourDropType` | IDENTICAL | 3 | identical value 10 in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800006, 1600024 |
| HIGH | `m_strSizeSuffix` | IDENTICAL | " | identical value ø in ALL 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800006, 1600024 |
| MEDIUM | `m_dFittingAnnotationSize` | ENUM | 0.0078125 | value always in {0.0102526, 0.0104987} (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800006, 1600024 |
| LOW | `m_dRiseDropAnnotationSize` | RANGE | 0.0078125 | range [0.0102526 .. 0.0104331] over 6/6 specimens | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800006, 1600024 |

### ElectricalSetting  — 12 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_circuitPathOffset` | IDENTICAL | 9.02231 | identical value 9.02231 in ALL 6/6 specimens | 6/6 | 2 (X5  remaining singletons: 1; S5 base (G1_candidate): 1) | 1900037, 1500050 |
| HIGH | `m_circuitNamePhaseA` | IDENTICAL | L1 | identical value A in ALL 6/6 specimens | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| HIGH | `m_circuitNamePhaseB` | IDENTICAL | L2 | identical value B in ALL 6/6 specimens | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| HIGH | `m_circuitNamePhaseC` | IDENTICAL | L3 | identical value C in ALL 6/6 specimens | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| HIGH | `m_isIncludeSparesInPanelTotals` | IDENTICAL | False | identical value True in ALL 6/6 specimens | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| HIGH | `m_mergeMultiPoledCircuitsIntoSingleCell` | IDENTICAL | True | identical value False in ALL 6/6 specimens | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| HIGH | `m_specificAngles.#len` | CONST_LEN | 7 | length always 6 (6/6 specimens) | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| HIGH | `m_specificAngles[].first` | ENUM | 15 | value always in {11.25, 22.5, 30, 45, 60, 90} (36 elements over 6/6 specimens) | 6/6 sp (36 obs) | 1 (S5 base (G1_candidate): 1) | 1500050 |
| LOW | `m_oldSpaceLabel` | STR_VOCAB | SPACE | value always in {Leerfeld, Space} (6/6 specimens) | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| LOW | `m_oldSpareLabel` | STR_VOCAB | SPARE | value always in {Reserve, Spare} (6/6 specimens) | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| LOW | `m_spaceLabel` | STR_VOCAB | SPACE | value always in {Leerfeld, Space} (6/6 specimens) | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |
| LOW | `m_spareLabel` | STR_VOCAB | SPARE | value always in {Reserve, Spare} (6/6 specimens) | 6/6 | 1 (S5 base (G1_candidate): 1) | 1500050 |

### PenWidthTableElem  — 3 finding(s); 56 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `ETR.created_at_birth` | IDENTICAL | False | identical value True in ALL 6/6 specimens | 6/6 | 2 (X1  pen table: 1; S5 singletons+catalog: 1) | 1500000, 1600000 |
| HIGH | `ETR.id_band` | IDENTICAL | <5M | identical value <5k in ALL 6/6 specimens | 6/6 | 2 (X1  pen table: 1; S5 singletons+catalog: 1) | 1500000, 1600000 |
| HIGH | `m_pPenWidthTable->PenWidthTable.m_modelPenInfo[].m_invertedScale` | ENUM | 24, 48, 96, 192, 384, 768  [6 leaves] | value always in {10, 100, 20, 200, 50, 500} (36 elements over 6/6 specimens) | 6/6 sp (36 obs) | 2 (X1  pen table: 1; S5 singletons+catalog: 1) | 1500000, 1600000 |

### ReconcileBrowserSettingsElem  — 2 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_newOrphanedGStyle.m_color` | IDENTICAL | 13137920 | identical value 32768 in ALL 6/6 specimens | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600006, 1600007 |
| HIGH | `m_oldOrphanedGStyle.m_color` | IDENTICAL | 7864520 | identical value 32768 in ALL 6/6 specimens | 6/6 | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600006, 1600007 |

### ReinforcementSettings  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_rebarVaryingLengthNumberSuffix` | IDENTICAL | - | identical value 1 in ALL 6/6 specimens | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900035, 1600071 |

### StructSettingsElem  — 9 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_analyticalModelSnapDistance` | IDENTICAL | 1 | identical value 0.984252 in ALL 6/6 specimens | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |
| HIGH | `m_maxLoadForce` | IDENTICAL | 1e+06 | identical value 164042 in ALL 6/6 specimens | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |
| HIGH | `m_parallelBraceOffset` | IDENTICAL | 0.0078125 | identical value 0.0082021 in ALL 6/6 specimens | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |
| HIGH | `m_scaledAreaLoadsIntensitySlope` | IDENTICAL | 0.003 | identical value 0.00322917 in ALL 6/6 specimens | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |
| HIGH | `m_scaledLineLoadsIntensitySlope` | IDENTICAL | 0.001 | identical value 0.000984252 in ALL 6/6 specimens | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |
| HIGH | `m_scaledPointLoadsIntensitySlope` | IDENTICAL | 0.001 | identical value 0.0003 in ALL 6/6 specimens | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |
| MEDIUM | `m_columnCutback` | ENUM | 0.00520833 | value always in {0.00164042, 0.00492126} (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |
| MEDIUM | `m_symbolicBraceCutback` | ENUM | 0.0078125 | value always in {0.00164042, 0.0082021} (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |
| MEDIUM | `m_symbolicCutback` | ENUM | 0.0078125 | value always in {0.00164042, 0.0082021} (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700000, 1600009 |

### TrueNorth  — 2 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_pocheDepth` | IDENTICAL | -6 | identical value -9.84252 in ALL 6/6 specimens | 6/6 | 2 (X8  units/site/info: 1; S5 base (G1_candidate): 1) | 2200185, 1500185 |
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<50k, <5k} (6/6 specimens) | 6/6 | 2 (X8  units/site/info: 1; S5 base (G1_candidate): 1) | 2200185, 1500185 |

### UnitsElem  — 4 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_units.m_digitGroupingAmount` | IDENTICAL | 3 | identical value 1 in ALL 6/6 specimens | 6/6 | 2 (X8  units/site/info: 1; S5 base (G1_candidate): 1) | 2200184, 1500184 |
| HIGH | `m_units.m_formatOptionsMap.#len` | CONST_LEN | 24 | length always 136 (6/6 specimens) | 6/6 | 2 (X8  units/site/info: 1; S5 base (G1_candidate): 1) | 2200184, 1500184 |
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<50k, <5k} (6/6 specimens) | 6/6 | 2 (X8  units/site/info: 1; S5 base (G1_candidate): 1) | 2200184, 1500184 |
| MEDIUM | `HDR.m_abFlags4Bytes` | ENUM | 8222 | value always in {2074, 8218} (6/6 specimens) | 6/6 | 2 (X8  units/site/info: 1; S5 base (G1_candidate): 1) | 2200184, 1500184 |

### KeynoteTable  — 5 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_cellList->CellList.m_cells[]->ExternalResourceReferenceCell.m_externalResourceReferences.#len` | CONST_LEN | 0 | length always 1 (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700003, 1600012 |
| HIGH | `m_cellList->CellList.m_cells[]->ExternalResourceReferenceCell.m_externalResourceReferencesExpanded.#len` | CONST_LEN | 0 | length always 1 (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700003, 1600012 |
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<500k, <5k} (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700003, 1600012 |
| MEDIUM | `m_oKeyBasedTreeEntries->KeynoteEntryTable.m_keyBasedTreeEntrySet.#len` | LEN_SET | 0 | length always in [3840, 6591] (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700003, 1600012 |
| MEDIUM | `m_oKeyBasedTreeEntries->KeynoteEntryTable.m_orphans.#len` | LEN_SET | 0 | length always in [16, 45] (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700003, 1600012 |

### RbsWireSizesElem  — 11 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_mapPowerFactors.#len` | CONST_LEN | 0 | length always 2 (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| HIGH | `m_mapWireDiameters.#len` | CONST_LEN | 20 | length always 34 (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| HIGH | `m_mapMaterials[].second.m_mapCorrectionFactors[].second.m_arrFactors.#len` | LEN_SET | 10, 12  [4 leaves] | length always in [7, 9, 10] (31 elements over 6/6 specimens) | 6/6 sp (31 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| HIGH | `m_mapMaterials[].second.m_mapTemperatureRatings[].second.m_arrWireSizes.#len` | LEN_SET | 20, 19  [4 leaves] | length always in [27, 28] (31 elements over 6/6 specimens) | 6/6 sp (31 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| HIGH | `m_mapMaterials[].second.m_mapTemperatureRatings[].second.m_setInsulationIds.#len` | LEN_SET | 3  [4 leaves] | length always in [2, 15, 18, 20, 22, 24, 26] (31 elements over 6/6 specimens) | 6/6 sp (31 obs) | 1 (S5 singletons+catalog: 1) | 1600023 |
| MEDIUM | `m_mapMaterials[].second.m_mapCorrectionFactors.#len` | LEN_SET | 2  [2 leaves] | length always in [1, 3] (11 elements over 6/6 specimens) | 6/6 sp (11 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| MEDIUM | `m_mapMaterials[].second.m_mapGroundSizes.#len` | LEN_SET | 19, 0  [2 leaves] | length always in [17, 19] (11 elements over 6/6 specimens) | 6/6 sp (11 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| MEDIUM | `m_mapMaterials[].second.m_mapTemperatureRatings.#len` | LEN_SET | 2  [2 leaves] | length always in [1, 3] (11 elements over 6/6 specimens) | 6/6 sp (11 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| MEDIUM | `HDR.m_parents->ElementParents.m_deletion.#len` | LEN_SET | 31 | length always in [7, 34] (6/6 specimens) | 6/6 | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| LOW | `m_mapMaterials[].second.m_mapCorrectionFactors[].second.m_arrFactors[].m_dMax` | RANGE | 298.15  [4 leaves] | range [299.15 .. 354.15] over 267 elements over 6/6 specimens | 6/6 sp (267 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |
| LOW | `m_mapMaterials[].second.m_mapCorrectionFactors[].second.m_arrFactors[].m_dMin` | RANGE | 349.15  [2 leaves] | range [294.15 .. 344.15] over 267 elements over 6/6 specimens | 6/6 sp (267 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800001, 1600023 |

### ProjectInfo  — 1 finding(s); 5 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `ETR.id_band` | IDENTICAL | <5M | identical value <50k in ALL 5/5 specimens | 5/5 | 2 (X8  units/site/info: 1; S5 base (G1_candidate): 1) | 2200203, 1500203 |

### ActiveGeoLocationTrackingElement  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `HDR.m_parents->ElementParents.m_deletion.#len` | CONST_LEN | 2 | length always 3 (6/6 specimens) | 6/6 | 1 (S5 singletons+catalog: 1) | 1600060 |

### ElectricalDemandFactorDefinition  — 3 finding(s); 60 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_values[].m_maxRange` | ENUM | 107639 | value always in {1, 1.29167e+06, 107639, 1e+30, 32291.7, 53819.6} (69 elements over 60/60 specimens) | 60/60 sp (69 obs) | 2 (S5 base (G1_candidate): 2; T_settings: 1) | 1500040, 1500042, 888049 |
| HIGH | `m_values[].m_minRange` | ENUM | 107639 | value always in {0, 1, 1.29167e+06, 107639, 32291.7, 53819.6} (69 elements over 60/60 specimens) | 60/60 sp (69 obs) | 2 (S5 base (G1_candidate): 2; T_settings: 1) | 1500040, 1500042, 888049 |
| HIGH | `m_values.#len` | LEN_SET | 5 | length always in [1, 2, 3] (60/60 specimens) | 60/60 | 1 (S5 base (G1_candidate): 1) | 1500042 |

### ExtentElem  — 1 finding(s); 610 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_dbViewNorm[2]` | ENUM | -0.371946 | value always in {-0.30636, -0.798636, -1, -6.9519e-17, 0, 1, 1.69618e-15} (610/610 specimens) | 610/610 | 2 (X9  view/level skeleton: 1; S5 base (G1_candidate): 1) | 2300219, 1500219 |

### WorksharingViewModeSettings  — 2 finding(s); 9 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_updateStatusColors[].second.m_lineColor` | ENUM | 5737262, 13132830, 1341670, 1973960  [4 leaves] | value always in {16711680, 221, 28928} (36 elements over 9/9 specimens) | 9/9 sp (36 obs) | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900041, 1600058 |
| HIGH | `m_ownershipStatusColors[].second.m_lineColor` | ENUM | 5737262, 35558, 9868950  [3 leaves] | value always in {14069600, 221, 28928} (27 elements over 9/9 specimens) | 9/9 sp (27 obs) | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900041, 1600058 |

### RbsVoltageType  — 4 finding(s); 10 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `ETR.id_band` | ENUM | <5M | value always in {<500k, <50k, <5k} (10/10 specimens) | 10/10 | 6 (S5 base (G1_candidate): 6; T_settings: 4) | 1500028, 1500029, 1500030, 1500031 |
| LOW | `m_dMaxVoltage` | RANGE | 5425.01 | range [0 .. 5274.32] over 10/10 specimens | 10/10 | 2 (S5 base (G1_candidate): 2) | 1500032, 1500033 |
| LOW | `m_dActualVoltage` | RANGE | 6458.35 | range [0 .. 5166.68] over 10/10 specimens | 10/10 | 1 (S5 base (G1_candidate): 1) | 1500033 |
| LOW | `m_dMinVoltage` | RANGE | 6135.43 | range [0 .. 4951.4] over 10/10 specimens | 10/10 | 1 (S5 base (G1_candidate): 1) | 1500033 |

### CopyWatchProperties  — 8 finding(s); 3 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_linkId` | NEVER_NULL | null | never null (3/3 specimens) | 3/3 | 1 (S5 singletons+catalog: 1) | 1600063 |
| HIGH | `m_pParamValueSetAString->ParamValueSetAString.m_paramSet.#len` | CONST_LEN | 0 | length always 4 (3/3 specimens) | 3/3 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900038, 1600063 |
| HIGH | `m_pParamValueSetDouble->ParamValueSetDouble.m_paramSet.#len` | CONST_LEN | 0 | length always 4 (3/3 specimens) | 3/3 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900038, 1600063 |
| HIGH | `m_linkId` | IDENTICAL | null | identical value @RvtLinkInstance in ALL 3/3 specimens | 3/3 | 1 (S5 singletons+catalog: 1) | 1600063 |
| LOW | `HDR.m_parents->ElementParents.m_deletion.#len` | RANGE | 2 | range [9 .. 34] over 3/3 specimens | 3/3 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900038, 1600063 |
| LOW | `m_pParamValueSetInt->ParamValueSetInt.m_paramSet.#len` | RANGE | 0 | range [7 .. 8] over 3/3 specimens | 3/3 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900038, 1600063 |
| LOW | `m_paramIdToPageMap.#len` | RANGE | 0 | range [12 .. 13] over 3/3 specimens | 3/3 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900038, 1600063 |
| LOW | `m_typeCopyMap.#len` | RANGE | 0 | range [39 .. 365] over 3/3 specimens | 3/3 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900038, 1600063 |

### ModelGraphicsStyle  — 1 finding(s); 10 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<500k, <50k} (10/10 specimens) | 10/10 | 4 (X5  remaining singletons: 2; S5 singletons+catalog: 2) | 1900042, 1900043, 1600064, 1600065 |

### AreaSettingsElem  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<500k, <5k} (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900030, 1600066 |

### DaylightSourceIdSet  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<50k, <5k} (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900015, 1600045 |

### ExternalParamLock  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<50k, <5k} (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900014, 1600044 |

### KeynotingSystem  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<500k, <5k} (6/6 specimens) | 6/6 | 2 (X3  named singletons: 1; S5 singletons+catalog: 1) | 1700004, 1600013 |

### ReactionsUpToDateElem  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `ETR.id_band` | ENUM | <5M | value always in {<500k, <5k} (6/6 specimens) | 6/6 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900012, 1600042 |

### RbsPipeSizesElem  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_materialMapConnections[].second.m_connectionMapSchedules[].second.m_scheduleMapSizes[].second.m_sizeData.#len` | LEN_SET | 14, 12  [28 leaves] | length always in [5, 9, 14, 15, 17, 18, 20] (168 elements over 6/6 specimens) | 6/6 sp (168 obs) | 1 (X4  MEP settings/sizes: 1) | 1800003 |

### RbsDuctSizesElem  — 2 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `m_shapeSizes[].second.m_sizeData.#len` | LEN_SET | 35, 33  [3 leaves] | length always in [58, 67, 74] (18 elements over 6/6 specimens) | 6/6 sp (18 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800005, 1600028 |
| LOW | `m_shapeSizes[].second.m_sizeData[].m_dSize` | RANGE | 8, 8.66667, 9.33333, 10  [8 leaves] | range [0.246063 .. 7.87402] over 1194 elements over 6/6 specimens | 6/6 sp (1194 obs) | 2 (X4  MEP settings/sizes: 1; S5 singletons+catalog: 1) | 1800005, 1600028 |

### DBViewType  — 1 finding(s); 493 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `m_refLabelStr` | STR_VOCAB | SIM. | value always in {Rand, Sim, null} (124/124 specimens) | 124/124 | 38 (X9  view/level skeleton: 19; S5 singletons+catalog: 16; S5 base (G1_candidate): 3) | 2300209, 2300210, 2300211, 2300234 |

### BrowserOrganization  — 1 finding(s); 68 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `m_folderDefinitions[].m_numCharsToUse` | ENUM | 2 | value always in {0, 1} (83 elements over 49/68 specimens) | 49/68 sp (83 obs) | 2 (X2  browser/navigator: 1; S5 singletons+catalog: 1) | 1600005, 1600006 |

### RbsDistributionSysType  — 1 finding(s); 8 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `HDR.m_parents->ElementParents.m_deletion.#len` | LEN_SET | 2 | length always in [1, 3] (8/8 specimens) | 8/8 | 2 (S5 base (G1_candidate): 2) | 1500037, 1500038 |

### GeoLocation  — 1 finding(s); 13 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `m_name` | STR_VOCAB | GEN Internal Origin | value always in {Intern, Internal, Project, Projekt} (13/13 specimens) | 13/13 | 4 (X8  units/site/info: 2; S5 base (G1_candidate): 2) | 2200188, 2200189, 1500188, 1500189 |

### ProjectPhase  — 1 finding(s); 13 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `m_description` | STR_VOCAB | Elements in place before our scope of work begins | value always in {Erstellung eines Gebäudes als Neubau oder Grundlage für Umbauarbeiten in Phase 2, null} (13/13 speci... | 13/13 | 4 (X9  view/level skeleton: 2; S5 base (G1_candidate): 2) | 2300196, 2300197, 1500196, 1500197 |

### PrintSettings  — 1 finding(s); 18 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| LOW | `m_timeStampInSeconds.m_lsb` | RANGE | 0 | range [1163521104 .. 1541410861] over 18/18 specimens | 18/18 | 2 (X5  remaining singletons: 1; S5 singletons+catalog: 1) | 1900048, 1600077 |

### GCSTracker  — 3 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| LOW | `HDR.m_parents->ElementParents.m_deletion.#len` | RANGE | 1 | range [79 .. 730] over 6/6 specimens | 6/6 | 1 (S5 singletons+catalog: 1) | 1600036 |
| LOW | `m_colGridMap.#len` | RANGE | 0 | range [64 .. 702] over 6/6 specimens | 6/6 | 1 (S5 singletons+catalog: 1) | 1600036 |
| LOW | `m_gridIntersections.#len` | RANGE | 0 | range [6 .. 124] over 6/6 specimens | 6/6 | 1 (S5 singletons+catalog: 1) | 1600036 |

### ViewSheetSet  — 1 finding(s); 7 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| LOW | `m_timeStampInSeconds.m_lsb` | RANGE | 0 | range [1343618402 .. 1510578231] over 7/7 specimens | 7/7 | 2 (X5  remaining singletons: 2) | 1900049, 1900050 |

### RbsConduitType  — 4 finding(s); 20 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_previewElemId` | NEVER_NULL | null | never null (20/20 specimens) | 20/20 | 5 (S5 base (G1_candidate): 5; T_conduit: 2) | 1500056, 1500057, 1500058, 1500059 |
| CRITICAL | `m_previewElemId` | IDENTICAL | null | identical value @LegendComponent in ALL 20/20 specimens | 20/20 | 5 (S5 base (G1_candidate): 5; T_conduit: 2) | 1500056, 1500057, 1500058, 1500059 |
| MEDIUM | `HDR.m_parents->ElementParents.m_deletion.#len` | LEN_SET | 2 | length always in [3, 4, 8] (20/20 specimens) | 20/20 | 5 (S5 base (G1_candidate): 5; T_conduit: 2) | 1500056, 1500057, 1500058, 1500059 |
| MEDIUM | `m_symbolInfo->SymbolInfo.m_name` | STR_VOCAB | GEN Conduit - EMT with Fittings | value always in {Conduit, Electrical Metallic Tubing (EMT), Leerrohr, Rigid Metal Conduit (RMC), Rigid Nonmetallic Co... | 20/20 | 5 (S5 base (G1_candidate): 5; T_conduit: 2) | 1500056, 1500057, 1500058, 1500059 |

### RbsCableTrayType  — 4 finding(s); 21 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| CRITICAL | `m_previewElemId` | NEVER_NULL | null | never null (21/21 specimens) | 21/21 | 3 (S5 base (G1_candidate): 3; T_conduit: 2) | 1500062, 1500063, 1500064, 888032 |
| CRITICAL | `m_previewElemId` | IDENTICAL | null | identical value @LegendComponent in ALL 21/21 specimens | 21/21 | 3 (S5 base (G1_candidate): 3; T_conduit: 2) | 1500062, 1500063, 1500064, 888032 |
| MEDIUM | `HDR.m_parents->ElementParents.m_deletion.#len` | LEN_SET | 1 | length always in [2, 7, 9] (21/21 specimens) | 21/21 | 3 (S5 base (G1_candidate): 3; T_conduit: 2) | 1500062, 1500063, 1500064, 888032 |
| MEDIUM | `m_symbolInfo->SymbolInfo.m_name` | STR_VOCAB | GEN Cable Tray - Ladder | value always in {Channel Cable Tray, Kanal-Kabeltrasse, Ladder Cable Tray, Single Rail Cable Tray, Solid Bottom Cable... | 21/21 | 3 (S5 base (G1_candidate): 3; T_conduit: 2) | 1500062, 1500063, 1500064, 888032 |

### CableTraySizesElem  — 1 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `m_sizes.m_sizeData.#len` | CONST_LEN | 7 | length always 16 (6/6 specimens) | 6/6 | 1 (S5 base (G1_candidate): 1; T_conduit: 1) | 1500061, 888031 |

### ConduitSizesElem  — 3 finding(s); 6 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| HIGH | `HDR.m_parents->ElementParents.m_deletion.#len` | CONST_LEN | 5 | length always 6 (6/6 specimens) | 6/6 | 1 (S5 base (G1_candidate): 1; T_conduit: 1) | 1500055, 888028 |
| HIGH | `m_sizes.#len` | CONST_LEN | 4 | length always 5 (6/6 specimens) | 6/6 | 1 (S5 base (G1_candidate): 1; T_conduit: 1) | 1500055, 888028 |
| LOW | `m_sizes[].second.m_sizeData[].m_dBendRadius` | RANGE | 0.333333  [4 leaves] | range [0.36275 .. 2.77608] over 330 elements over 6/6 specimens | 6/6 sp (330 obs) | 1 (S5 base (G1_candidate): 1; T_conduit: 1) | 1500055, 888028 |

### ConduitStandardType  — 1 finding(s); 32 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `m_symbolInfo->SymbolInfo.m_name` | STR_VOCAB | GEN EMT | value always in {, EMT,, EMT, IMC, RMC, RNC, RNC Schedule40, RNC Schedule80, rmc} (32/32 specimens) | 32/32 | 4 (S5 base (G1_candidate): 4; T_conduit: 2) | 1500051, 1500052, 1500053, 1500054 |

### RbsWireMaterialType  — 1 finding(s); 29 specimens mined

| sev | field path | rule | ours | specimens say | support | violations (rung: n) | our element ids |
|---|---|---|---|---|---|---|---|
| MEDIUM | `m_symbolInfo->SymbolInfo.m_name` | STR_VOCAB | Aluminum | value always in {Aluminium, Copper, Kupfer, Nichtmagnetisch, Non-Magnetic, Stahl, Steel} (29/29 specimens) | 29/29 | 1 (S5 singletons+catalog: 1; T_conduit: 1) | 1600017, 888039 |

## 6. Untested sources (no viewer verdict) — violations unique to them

None — every rule the untested T_settings / T_walltype objects violate is ALSO violated by the rejected X/S set (their findings are counted in §4 / §5), i.e. the untested files add no new suspects; their verdicts would only confirm.

## 7. Method + how to read a finding

* **Mining.** For each class our constructors emit, EVERY host-document specimen (id in `Global/ElemTable`) of the six samples is decoded (seq-102 body, seq-101 `ElementHeader`, ElemTable row, seq-103 rep class) and flattened schema-parallel into typed leaves.  Growable containers collapse to `path[]` + `path.#len`; owned pointers add `path.#ptr` (the concrete class) and are walked into; ElementId leaves are TOKENIZED — -1 = null, other negatives = the literal built-in id constant, positive = `@Class` of the target in ITS OWN file — so `always references a UnitsElem` and `never dangling` are minable, and cross-file id values are comparable.  Cohorts split populations that differ by rule (project vs family-scoped pen tables / view types; built-in vs sub-category style rows).
* **Rules.** NEVER_NULL / PTR_PRESENT (a field or owned sub-object present-and-non-null in N/N), IDENTICAL (one value in all N — a format constant), CONST_LEN / LEN_SET (container length), ENUM / PTR_CLASS_SET / STR_VOCAB (a small saturated value set), RANGE, ALWAYS_NULL / PTR_ABSENT, OWNED_CHILD (an ElemTable-owned child class every specimen owns), on the body, the header (`HDR.`), the ElemTable row (`ETR.`) and the seq-103 rep (`REP.`).
* **Calibration.** The same lint runs over the constructed / created objects the viewer ACCEPTED.  A (class, path, rule) they violate is not required by the reader (marked, demoted); a rule TYPE they violate often is a noisy signal (the false-positive table).  Our conduit / wire types passing tells us the from-scratch construction PATH itself is fine — the reader's objection is class-specific SHAPE / VALUE, which is what this list localises.
* **Reading the list.** A CRITICAL / HIGH row on a class we ship in the failing files, supported by N/N specimens across ≥3 sample projects, not calibrated away, is a concrete shape difference between our object and every accepted one — the fix is to make the constructor emit what the specimens carry (or, where the value is Autodesk expression, to record it for counsel).  Element ids and names in `ours` locate the exact record.

## 8. Reproduction

```
.venv/bin/python -m rvt.objlint                    # mine (six samples) + lint + this report
.venv/bin/python -m rvt.objlint --no-mine          # reuse experiments/genesis/lint/invariants/
.venv/bin/python -m rvt.objlint --classes GStyleElem,PenWidthTableElem
.venv/bin/python -m pytest tests/test_objlint.py -q
```


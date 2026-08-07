# GENESIS TYPES — system-family types & document standards from our own expression

Field-by-field DEFINITION MAPS for the type / standard elements a Revit
project carries *below* the loadable-family layer: wall / floor / roof /
ceiling types (compound structures), conduit / cable-tray / wire types, the
electrical settings elements (voltage & distribution-system definitions, load
classifications, demand factors, the ElectricalSetting singleton), object
styles (CategoryElem + GStyleElem), line & fill patterns, a material, and text
types.  These are the expression that survives even a family-free reduction and
the constructor module `src/rvt/genesis/types.py` builds every one of them
from PLAIN PARAMETERS (mm, inches, volts, RGB, names) with **no cloned Autodesk
payload**.

Every claim is verified against Revit 2026 sample projects (rme = MEP, rst =
structural, rac = architectural).  A field is labelled:

* **DEF** — the type's DEFINITION: a caller parameter.
* **REF** — a reference to another element the caller supplies (or -1).
* **MACH** — format machinery, identical on every instance; reproduced at
  its verified constant (the value in parentheses).
* Confidence: **[exact]** = the constructor reproduces a real Autodesk
  specimen from its plain parameters with ZERO field diffs (object *and*
  seq-101 header) — asserted in `tests/test_genesis_types.py`;
  **[verified]** = observed on ≥ 2 specimens; **[hypothesis]** = unexercised.

Shared by every element (the `Element` base, all **MACH** unless noted):
`m_pParamValueSet{Double,Int,AString,ElementId}` (null or a small
built-in-parameter set — see per class), `m_geomSteps` (null; wall types
carry the regen node §1), `m_pGeomTable` (null; patterns/text types carry an
empty `GeomTable`), `m_constrInfo` [] , `m_cellList` (null or the
analytical/definition cells), `m_docAccess.m_pDoc` weakref 1 (the document),
`m_id` (**DEF** the element id), all `m_*Id` levels/phases/owner/design-option
= -1, `m_locked/m_moribund/m_dummy` false.  `Symbol` adds `m_symbolInfo`
(**DEF** `SymbolInfo{m_name}` = the type name), `m_renderStyleId` -1,
`m_previewElemId` -1 (Revit-authored types point at a `LegendComponent`
type-preview element; -1 is what the settings types carry — mandatory-ness of
a preview for host types is [open]).

The seq-101 `ElementHeader`: `m_categroryId` = the class's built-in category
(table §9), `m_familyId` -1, `m_classDef.m_ref` = classref(class name),
`m_pBBox` null, `m_parents.m_deletion` = self + every referenced/owned id
(materials, standards, fittings, param elements, owned font/category/style),
all other parent lists empty.  `m_abFlags4Bytes` / `m_viewRules` per class
(§9).  The seq-103 representation is `SerializedDummy` (psize 2, stamp
0x0069003C) for **every** type except `BasicWallType`, which carries an EMPTY
`GElement` geometry cache (m_gElemType 3, one empty `Geometry` sub-node,
±1e30 boxes) — reproduced exactly.

---

## 1. `BasicWallType` (0x025b, chain Element < Symbol < HostObjAttr < WallType) — `new_wall_type`

Constructor: `new_wall_type(name, layers=[(function, thickness_mm, material_id),
...], family_name, function, sample_height_mm, cut_off_height_mm,
fill_pattern_id, wrap_at_inserts, wrap_at_ends, default_height_constraint)`.
**[exact]** vs rme 54538 'Exterior - Block on Mtl. Stud' (7 layers, two
0-width membranes), 563417 'MW 17.5' and 563414 'STB 20.0' (single layer) —
the only diffs are the sample's German shared parameter (content, deliberately
not cloned) and the ancient pre-Revit-4.0 `m_segRefFaceKeysPre40` list.

| field | role | value |
|---|---|---|
| m_symbolInfo.value.m_name | **DEF** | type name |
| m_pParamValueSetDouble | MACH | present, empty paramSet |
| m_pParamValueSetAString | **DEF** | `{-1010105: family_name}` = the system-family grouping name ("Basic Wall" / "Stahlbeton"); null when family_name=None (US-template style) |
| m_pParamValueSetInt / ElementId | MACH | null (samples carry firm-specific shared params here — never cloned) |
| m_geomSteps | MACH | `GeomStepList{ m_bRepFormGList=[VertCompoundStructureGStep{ m_id 1, m_version 0, m_flags 13, m_pElem weakref 2, m_minimumWallHeight 0 }], m_pElem weakref 2, m_latestGStepTypeInPrevRegenCycle [2,2,2,2,2], m_idCounter 2, m_flags 9 }` — identical on all 10 rme wall types |
| m_cellList | MACH | 4 cells: AnalyticalPropertiesCell{absorptance 0.1, roughness 1}, PatternHelper{}, TaperableWallTypeAngleParametersCell{0,0}, TaperableWallTypeWidthAtParametersCell{0} |
| m_pCompoundStructure | **DEF** | see §1.1 |
| m_panel / m_intMullions / m_bordMullions | MACH | -1, [-1,-1], [[-1,-1],[-1,-1]] (curtain-panel fields, unused by basic walls) |
| m_autoJoinCond / m_structHiddenViewDisplayType | MACH | 0 / 0 |
| m_defHeightConstraint | **DEF** | 1 (unconnected height; the US template uses 3) |
| m_function | **DEF** | 0 interior / 1 exterior / 2 foundation / 3 retaining / 4 soffit / 5 core-shaft |
| m_fixed / m_allowAutoEmbed | MACH | false / false |
| m_oULineSpec / m_oVLineSpec | MACH | null / null |

### 1.1 `CompoundStructure` — the wall's real definition **[exact]**

`m_layers[]` (exterior → interior), each:
`m_layerWidth` (**DEF** feet = mm/304.8), `m_materialId` (**REF** MaterialElem
or -1), `m_profileId` -1, `m_layerFunction` (**DEF** 1 structure / 2 substrate
/ 3 thermal-air-insulation / 4 finish1 exterior / 5 finish2 interior / 100
membrane), `m_layerPriority` (= function; membrane = 999), `m_embeddingType`
-1, `m_layerId` (index), `m_layerCapFlag` true.

Derived (all **DEF**-driven, computed by the constructor):
`m_numShellLayersExt/Int` = layers before/after the contiguous run of
structure layers (the CORE); `m_structuralMaterialLayerIndex` = first
structure layer; `m_variableLayerIdx` -1; `m_coarseScaleFillPatternElemId`
(**REF** FillPatternElem or -1); `m_coarseScaleFillColor` 0; `m_endCap` /
`m_openingWrapping` (**DEF** wrap-at-ends / wrap-at-inserts codes);
`m_segRefFaceKeysPre40` [] (legacy, only ancient templates carry it).

`m_oVertRegStructure` = `VerticalRegionsStructure` — the layer LAYOUT the
witness lines and dimensions attach to (walls only; floors/roofs/ceilings
have null).  Rule reproduced byte-for-byte on 3 wall types:

* one **region** per NON-ZERO-width layer (0-width membrane layers get no
  region); `m_regionToLayerMap` maps region → layer index;
* **boundary segments** (`m_orientation` 0) at the cumulative widths, origin
  0.0 at the exterior face, ids `0..B-1` exterior→interior; outer faces carry
  `m_regionId [region,-1]`, internal boundaries `[outer,inner]`;
* per region two **face segments** (`m_orientation` 1) at coordinate 0.0 and
  `m_sampleHeight` (**DEF** feet, default 6096 mm = the 20-ft preview sample),
  ids `B+2r` (bottom) / `B+2r+1` (top), `m_regionId [region,-1]`;
* region `r` spans segments `[left_boundary, bottom_face, right_boundary,
  top_face]`; segment array order = bottom faces, top faces, boundaries;
* `m_cutOffHeight` (**DEF**, default = sample height), `m_tol` 1e-9,
  `m_bPreviewDimsAreValid` false, `m_wallSweeps` / `m_reveals` [] (**DEF**
  hooks for later sweep/reveal authoring), `m_extendableRegionIds*` [].

`m_segRefFaceKeys[]` — the stable reference-face identities of the core
boundaries (what dimensions/alignment lock onto): core exterior boundary →
key0 **29**; core interior boundary → key0 **30**; boundaries inside the
exterior shell → key0 **31** with a running key1 counter (0,1,… exterior→
interior); inside the core → key0 **32** (counter); inside the interior shell
→ key0 **33** (counter) [hypothesis — no sample has 2 interior finish
layers].  Outermost faces carry no key unless they coincide with a core
boundary (single-layer wall: 29 on the exterior face, 30 on the interior).

## 2. Flat host types — `new_floor_type`, `new_roof_type`, `new_ceiling_type`

`FloorAttributes` (0x0841), `RoofAttributes` (0x0eb5), `CompoundCeilingType`
(0x02f6): the same `CompoundStructure` **without** the vertical-region grid
(`m_oVertRegStructure` null, `m_segRefFaceKeys` []), `m_endCap` 3, shell
counts / structural index computed as for walls.  **[exact]** vs rme 335
'Generic - 400mm' roof and 563403 compound ceiling; floor 563400 differs only
by the sample's shared parameter.

| class | extra DEF fields | machinery |
|---|---|---|
| FloorAttributes | `m_footingType` 0 (architectural) / 2 (foundation slab) | Int set `{-1001006: 0}` (FLOOR structural-usage default), cellList = [AnalyticalPropertiesCell], `m_structHiddenViewDisplayType` 0 |
| RoofAttributes | — | Double + Int sets present-empty, cellList = [AnalyticalPropertiesCell] |
| CompoundCeilingType | `m_CeilingGridPattern` (0 none), `m_isThick` true, `m_system` "" | Double set `{-1002203: 1.0, -1002202: 1.0}` (ceiling-grid spacing multipliers), cellList = [AnalyticalPropertiesCell] |

## 3. `MaterialElem` (0x0aa3) — `new_material`

A **graphics-only** material (no owned appearance/render asset — a
system-family type only needs the shaded colour).  Object header category
OST_Materials (-2000700).

| field | role | value |
|---|---|---|
| m_pMaterial.value.m_name | **DEF** | material name |
| m_color | **DEF** | u32 COLORREF `r | g<<8 | b<<16` (rme 'Analytical Panels' = 10077691 = rgb 251,197,153) |
| m_transparency / m_smoothness / m_shininess | **DEF** | 0..1 / 0..1 (0.5) / int (64) |
| m_sMaterialClass / m_sCategory / m_keywords | **DEF** | class + category strings ("Concrete") |
| m_surfacePatternId / m_cutPatternId | **REF** | FillPatternElem ids or -1; background pattern ids -1, pattern colours 0 |
| m_appearanceAssetId / m_structuralPropertySetId | REF | -1 (no owned assets) |
| m_asset | MACH | binding descriptor every material carries: `m_sName "Generic"`, `m_sLibrary "assetlibrary_base.fbx"`, `m_eAssetType 4`, containers empty |
| m_assetMap / m_pThumbnail / m_materialPathMap | MACH | empty / null / [] |

## 4. Line patterns (0x0a02) & fill patterns (0x07fe) — `new_line_pattern`, `new_fill_pattern`

**[exact]** vs rme 'Dash' (11), 'Dot' (18), 'Diagonal crosshatch' (6473).
Header category -1 (document-standard, not categorised).

* `LinePatternElem`: `m_pLinePattern` → `LinePattern{ m_name` (**DEF**)`,
  m_segs[]` (**DEF** `{m_data` feet`, m_type` 0 dash / 1 space / 2 dot (data
  0)`}`)`, m_pixelPattern 0 }`, `m_ownerId` -1.  Dash lengths are drafting
  facts ('Dash' = 3.175 mm on / 3.175 mm off).
* `FillPatternElem`: `m_pFillPattern` → `FillPattern{ m_gridsArr[]` (**DEF**
  `FillGrid{ m_angle` rad`, m_origin` uv-ft`, m_deltas [shift, spacing]` ft`,
  m_segs[]` dash lengths ft`}` — zero grids = SOLID fill`), m_name, m_scale
  1.0, m_windowSize` ft`, m_fpOrientation 0, m_fpTarget` 0 drafting / 1
  model`}`; `m_pGeomTable` = empty `GeomTable`; `m_ownerId` -1.

## 5. Electrical definitions

### 5.1 `RbsVoltageType` (0x0dd6) — `new_voltage_type` **[exact]**
`m_symbolInfo.m_name` (**DEF** e.g. "240"), `m_dActualVoltage` /
`m_dMinVoltage` / `m_dMaxVoltage` (**DEF**, internal units = volts ×
10.7639104167 — the metric watt's m² converted to ft²; 240 V stored as
2583.3385, 208 V as 2238.89).  Defaults min/max = the published service range
of the nominal (120→110/130, 208→200/220, 240→220/250, 277→260/280,
480→460/490 …), else ±5 %.  All four param sets null.  Header cat -2008040.

### 5.2 `RbsDistributionSysType` (0x0d70) — `new_distribution_system` **[exact]**
`m_symbolInfo.m_name` (**DEF**), `m_idVll` / `m_idVlg` (**REF** the L-L and
L-G RbsVoltageType ids), `m_kPhase` (0 single / 1 three), `m_kConfig`
(1 wye / 0 delta-or-single), `m_iNumWires` (3 / 4), `m_highLegPhase` -1.
AString set present-empty.  Header cat -2008041.

### 5.3 `ElectricalDemandFactorDefinition` (0x059c) — `new_demand_factor` **[exact]**
`m_name` (**DEF**), `m_ruleType` (0 constant / 1 quantity / 2 load / 3
percentage ranges), `m_values[]` = `{m_factor, m_minRange, m_maxRange}`
(constant = one row 0…1e30), `m_additionalLoad` 0.0,
`m_includeAdditionalLoad` false.  Header cat -2008142.

### 5.4 `ElectricalLoadClassification` (0x05a4) — `new_load_class` **[exact]**
`m_name` (**DEF**), `m_demandFactorId` (**REF** §5.3), `m_spaceLoadClass`
(**DEF** 0/2), `m_signitureType` 0, `m_abbreviation` "", and six Revit
**label templates** (MACH, identical on all 10 rme classifications):
`m_actualElectricalLoadLabel "Actual %1!s! Load"`,
`m_loadSummaryDemandFactorLabel "%1!s! Demand Factor"`,
`m_panelConnectedCurrentLabel "%1!s! Connected Current"`,
`m_panelConnectedLabel "%1!s! Connected Apparent Power"`,
`m_panelEstimatedCurrentLabel "%1!s! Estimated Demand Current"`,
`m_panelEstimatedLabel "%1!s! Demand Apparent Power"`.  The six
`m_*ParamElemId` (**REF**) point at the `ParamElemElectricalLoadClassification`
schedule-column parameters Revit auto-creates per classification — a
parameter-elements concern; the constructor takes them via `param_elem_ids`
or leaves them -1 [documented gap].  Header cat -2008143.

### 5.5 `ElectricalSetting` (0x05ae, document SINGLETON) — `electrical_setting` **[exact]**
`m_pADocument` weakref 1; **DEF**: `m_circuitNamePhaseA/B/C` ("A","B","C"),
`m_spaceLabel/m_spareLabel` (+ old_*), `m_specificAngles[]` = `{degrees,
enabled}` (11.25, 22.5, 30, 45, 60, 90), `m_angleIncrement` 1° (rad),
`m_circuitPathOffset` (2750 mm = 9.02 ft), `m_circuitRating` 20 A,
`m_circuitLoadCalculationMethod`, `m_isIncludeSparesInPanelTotals`,
`m_isRunCalculationsForLoadsInSpaces`,
`m_mergeMultiPoledCircuitsIntoSingleCell`; MACH: `m_capitalizationForLoadNames`
0, `m_circuitSequenceValue` 0, `m_fittingAngleUsage` 0.

## 6. Conduit: `ConduitStandardType` (0x0370) + `ConduitSizesElem` (0x036d) + `RbsConduitType` (0x0d64)

A conduit definition is THREE elements — **[exact]** on all three
(rme 638840 'EMT', 638845 the sizes singleton, 662478 'RNC Sch 80'):

* `new_conduit_standard(name)` — the standard is only its name (EMT / IMC /
  RMC / RNC Schedule 40 / 80).  AString set present-empty; header cat
  -2008144, no preview.
* `conduit_sizes_element({standard_id: [(nominal_in, inner_in, outer_in,
  bend_radius_in), …]})` — the document SINGLETON `m_sizes[]` = per standard
  id a `{m_sizeData[]}` of `{m_dSize, m_dInnerDiameter, m_dOuterDiameter,
  m_dBendRadius` (feet)`, m_bInSizeList, m_bUsedBySizing}`.  The values are
  published ANSI trade dimensions (EMT ½" = 0.622/0.706 in) — facts, not
  authored content.  Header deletion lists the standards.
* `new_conduit_type(name, standard_id, with_fitting, fittings, roughness_ft,
  max_size_in)` — `m_idStandardType` (**REF**), `m_bWithFitting` (**DEF**
  the with/without-fitting family of types), the `m_idDefault*` fitting
  symbols (**REF** loadable fitting-family symbols; -1 until such families
  are OUR content — the sample's own "Conduit" types are with -1), `m_dMaxWidth
  / m_dMaxHeight` (8 ft), `m_dRoughness` 0.0003, `m_Profile` =
  `AbsSysCircSweepProfile{}` (circular routing profile, MACH),
  `m_bBranchTypeTee` true, `m_eRiseDropType` 0, `m_pCompoundStructure` null.
  Header cat -2008132.

## 7. Cable tray: `CableTraySizesElem` (0x02c7) + `RbsCableTrayType` (0x0d5a) **[exact]**

* `cable_tray_sizes_element([width_in, …])` — SINGLETON: `m_sizes` =
  `{m_sizeData[]}` of `{m_dSize (ft), diameters 0, m_bInSizeList,
  m_bUsedBySizing}`.
* `new_cable_tray_type(name, shape, with_fitting, fittings,
  min_bend_multiplier)` — as the conduit type plus `m_eCableTrayType`
  (**DEF** 2 = ladder, 1 = channel/solid-bottom/wire-mesh/trough),
  `m_dMinBendMultiplier` (1.0), `m_Profile` = `LadderSweepProfile{}` /
  `UShapeSweepProfile{}` by shape; fitting symbols include ElbowUp/ElbowDown.
  Header cat -2008130.

## 8. Wire: conductor cells + `RbsWireType` (0x0ded) + the three symbol types **[exact]**

Two parallel catalogs coexist in the format (both reproduced):

1. **Conductor definition cells** = `CustomElement` (0x0442, header cat
   -1) whose `m_cellList` = `CellList{ <cell>, NamingCell{m_name} }` with
   `<cell>` ∈ `RbsConductorMaterial{}` ('Copper'),
   `RbsConductorTemperatureRating{}` ('60'/'75'/'90'),
   `RbsConductorInsulationMaterial{}` ('THWN'/'XHHW'),
   `RbsConductorSize{m_diameter` (ft)`}` (e.g. '2000' kcmil) —
   `new_conductor_*`.
2. **`RbsWireType`** — `new_wire_type(name, material_id,
   temperature_rating_id, insulation_id, max_size_id, …)`: the four ids
   (**REF**) point at the cells above; **DEF**: `m_strConduitType`
   ("Non-Magnetic" / "Magnetic" — selects the impedance table),
   `m_dNeutralMultiplier` 1.0, `m_eNeutralMode` 0,
   `m_bNeutralIncludedInBalancedLoad` true, `m_bShareNeutral` /
   `m_bShareGround` true.  Header cat -2008039, deletion = the 4 cells.
3. **Symbol types** the wire-SIZES table keys on: `RbsWireMaterialType`
   (0x0e00-ish, cat -2008111), `RbsWireInsulationType` (-2008112),
   `RbsWireTemperatureRatingType` (-2008113) — definition = the name only
   (`new_wire_*_type`).  The sizes/ampacity/correction-factor table itself
   (`RbsWireSizesElem`, cat -1, ab 8222) is an NEC-derived data table
   (ampacities in A, diameters in ft, Kelvin correction bands, per-material
   power factors) — mapped here, its authoring is a data-table task and not
   yet a constructor [documented gap].

`GenesisCatalog.wire_type_full(name, material, temperature, insulation,
max_size)` emits the 4 cells + the wired type in one call.

## 9. Object styles & sub-categories — `default_object_styles`, `new_category`, `new_gstyle`

The document's **Object Styles table** = one `GStyleElem` (0x08cc) per
built-in category and style role (`m_gstyleType` 1 projection / 2 cut) whose
`m_categoryId` is the NEGATIVE built-in OST id and `m_ownerId` -1; created FIRST
in every project (ids 30, 31, … in rme; OST_Walls projection = id 30 pen 1,
cut = id 31 pen 3).  `m_pGStyle` = `GStyle{ m_linePatternId` (-3000010 =
built-in SOLID, -1 none, or a LinePatternElem id)`, m_materialElemId,
m_penNumber` (line weight 1-16)`, m_color` (COLORREF, 0 black)`,
m_isScreenSized }`.  **[exact]** vs rme ids 30/31.

The per-category default pens/colours/patterns are a **Revit product
constant**: `data/object_styles.json` (1,074 built-in categories × up to two
roles) was extracted from the MEP sample and cross-checked against the
unrelated structural sample — **1,239 of 1,407 (category, role) entries are
byte-identical in both files** (`confirmed: true`); the remaining 168 are the
MEP template's own values (`confirmed: false`).  `default_object_styles(ids,
categories=…, confirmed_only=…)` regenerates the table (positive line-pattern
and material ids are file-local so only names / -1 are portable).  Object-
style rows carry header `m_abFlags4Bytes` 67108894.

A **sub-category** = `CategoryElem` (0x02e1, header cat -1) with
`m_pCategory` = `Category{ m_name` (**DEF**, "" for a type's private line
style)`, m_parentCategoryId` (**REF** the parent built-in OST id)`,
m_categoryType` (1 model / 2 annotation / 4 internal-line-style)`, m_flags
7 }`, `m_ownerId` (**REF** owning type/family or -1), `m_gstyleIds[]` (**REF**
its GStyleElem rows) + one or more `GStyleElem` whose `m_categoryId` is the
positive CategoryElem id (header flags 8202).  Owned categories list their
owner in `m_deletion`.

Built-in category ids the constructors' headers use (`m_categroryId`):

| class | OST id | abFlags4Bytes / visibleFlags |
|---|---|---|
| BasicWallType | -2000011 Walls | 2364 / -32640 |
| FloorAttributes / RoofAttributes / CompoundCeilingType | -2000032 / -2000035 / -2000038 | 30 / -32640 |
| RbsConduitType / RbsCableTrayType | -2008132 / -2008130 | 14 / -32640 |
| ConduitStandardType | -2008144 | 14 / -32768 |
| RbsWireType | -2008039 | 30 / -32640 |
| RbsWireMaterial/Insulation/TemperatureRating Type | -2008111 / -2008112 / -2008113 | 14, 30, 30 / -32768 |
| RbsVoltageType / RbsDistributionSysType | -2008040 / -2008041 | 30 / -32768 |
| ElectricalLoadClassification / DemandFactorDefinition | -2008143 / -2008142 | 67108878 / 67117070 |
| MaterialElem | -2000700 | 67108894 / -32736 |
| Line/FillPatternElem, DimensionStyle | -1 | 67117086, 30 |
| TextNoteAttributes / FontElem / CategoryElem / GStyleElem(sub) | -1 | 14 / 8202 / 8202 / 8202 |
| CustomElement (conductor cells) | -1 | 8206 / -4225 |
| Conduit/CableTray SizesElem, ElectricalSetting | -1 | 8206 / -32768 |

## 10. Text types — `new_text_type` → 4 wired elements **[exact]**

Reproduced field-for-field against rme text type '1/8" Arial' (618030) and
its three companions:

1. `TextNoteAttributes` (0x10df, chain … LineAndTextAttrSymbol <
   TextElementAttributes): `m_symbolInfo.m_name` (**DEF**), Double set
   `{-1006327: width_factor 1.0, -1006326: tab size (ft)}`, ElementId set
   `{-1006315: leader arrowhead LeaderStyle id or -1}`, `m_pGeomTable` empty
   `GeomTable`, `m_lineAndTextAttr` = `{m_fontId` (**REF** 2)`, m_categoryId`
   (**REF** 3)`, m_background 0, m_bBold/m_bItalic/m_bUnderline` (**DEF**)`}`,
   `m_leaderOffsetSheet` (2.032 mm = 0.08"), `m_textBoxVisibility` (**DEF**
   border).  Header deletion = self + font + category + style + arrowhead.
2. `FontElem` (0x084c): `m_ownerId` = the type; `m_pFont` = `Font{ m_name`
   (**DEF** e.g. "Arial")`, m_size` (**DEF** feet = paper text height, 1/8"
   = 0.0104)`, m_color }`.  Object `m_designOptionId` -4 (internal), header
   deletion lists the owner.
3. `CategoryElem` "" (parent OST -2000059 = the text-note line-style
   category, type 4, owner = the type, `m_gstyleIds` = [4]).
4. `GStyleElem` of that category (projection, pen 1, black, solid) = the
   leader/box line style.

## 11. Dimension styles (`DimensionStyle` 0x00be) — mapped, not yet a constructor

`DimensionStyle` (chain Element < Symbol < DimensionStyle, ~1.1 KB objects)
is fully DECODABLE and its definition is mapped: unit `FormatOptions` value
objects (`m_symbolTypeId`/`m_unitTypeId` as Forge type-id strings such as
"autodesk.unit.unit:millimeters-1.0.1", accuracy, rounding, suppression
flags), an equality-format array, `m_pLineAndTextAttr` (font + its own line
sub-category, exactly the text-type pattern §10), tick/centerline/arrowhead
**category and style ids each dim style owns** (`m_tickCategoryId`,
`m_centerlinePatternCatId`, `m_arrowHeadStyleId`), and ~25 scalar
appearance fields (leader type, text alignment, tick types,
`m_dimensionStyleType` 0 linear / 9 diameter …).  Its constructor is deferred
because each style requires ~4 companion category/gstyle elements plus the
unit-format enums; the schema round-trip of a blanked `DimensionStyle` is
asserted, so the codec side is ready.

## 12. Verification & reproduction record

* `python -m rvt.genesis.types` — builds the demo catalog (52 records / 23
  classes: everything above) and reports encode→decode CLEAN + BYTE-EXACT
  for all 52 with ZERO dangling references.
* `tests/test_genesis_types.py` (46 tests): 30 schema-skeleton round-trips,
  the constructor round-trips, the compound-structure grid/shell/key rules
  against the block-wall specimen, unit factors, the no-corpus-read guard, and
  the PARAMETRIC REPRODUCTION suite (voltage/distribution, conductor cells +
  wire, conduit type/standard/sizes, cable tray, electrical setting, block
  wall + roof + ceiling, patterns, the 4-element text type, the OST_Walls
  object-style rows) — Autodesk's own types re-created from plain parameters
  with zero object/header field diffs.
* `experiments/genesis/types/make_type_proofs.py` — injection proof: three
  batches (`T_walltype.rvt`, `T_conduit_types.rvt`, `T_settings.rvt`, 51
  new type records total) committed into the MEP sample via the proven commit
  path; read-back shows CRC/ECC/walker/stamp/sentinel/count all clean and
  every new object decodes clean; `tools/rvt_validate.py` reports **OK,
  0 errors** on all three (2 warnings = pre-existing: the commit path's
  block A/C counter hygiene + the sample's own Extensible-Storage records).

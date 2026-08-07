# genesis-settings — the DOCUMENT-SETTINGS SINGLETONS, the settings constellations and the built-in style CATALOG (constructor field maps)

Stream: **genesis-singletons** (the K5/K6-FAIL branch).  Modules:
`src/rvt/genesis/settings.py` (constructors + the ADocument registry map),
`src/rvt/genesis/catalog.py` (the built-in-category graphic-style catalog).
Companion record: `docs/inbox/genesis-singletons.md`.  Tests:
`tests/test_genesis_settings.py` (45).  Every constructor follows the
`rvt.genesis.types` / `rvt.genesis.skeleton` standard: PLAIN PARAMETERS,
field-by-field over a schema-directed blank (`types.blank_object`), NO
cloned payload, and a **parametric reproduction proof** against a corpus
specimen (feed the specimen's own values in → object equal; the exact
proofs are the `test_reproduce_*` tests).  Tags below: **[V]** verified
byte-exact on ≥ 1 specimen (usually 3), **[I]** inferred, **[U]** unknown /
reader-tolerance probe.

---

## 1. Why these classes (the reader's diagnosis)

Every constructed genesis base (G0 / G1_candidate / G1a / G1b) is validator-
VALID but Autodesk's own reader rejects it (`Revit-DocumentCorruption`; the
extractor crashes), while sample reductions that KEEP the settings skeleton
PASS.  The census of the required set (`docs/writer/required-set.md`) lists
**62 count-invariant singleton classes present in EVERY reader-accepted file
and absent from G1** (the same gap genesis-2 called "67 empty
UniqueElementsTracking slots").  The K-ladder (`experiments/genesis/triage/
K5*.rvt`, K6) bisects WHICH the reader requires; this stream PRE-BUILDS the
constructors and the add-back files (S1..S5) so a K5x / K6 FAIL is answered
by an existing file.  Constructed here: **69 settings classes + the 19 SYSTEM
view types + the 1,407-row built-in style table.**

## 2. The universal singleton shape [V]

Every document-settings element is a bare `Element` (20 base fields) with:
all six param-set pointers null (a few carry a present-EMPTY AString /
ElementId set — noted per class), `m_docAccess.m_pDoc` = weak → 1, every
scoping id −1 (assoc level, family, phases, design option; the two revision
sequences carry the internal design-option sentinel **−4**), `m_cellList`
either null or the standard `CellList{PatternHelper}` (both forms occur in
the corpus for most classes; the constructors take `cell_list=`), seq-103
`SerializedDummy`, and an **ElemRec owner = NO_OWNER** (owner-less;
exceptions: the navigator's viewer/viewport/drawing are owned by the view,
the two revision sequences by AllProjectRevisions).  Header
(`ElementHeader`): category −1 (a few carry a real built-in category:
ProjectRevision −2006070, RevisionNumberingSequence −2006071,
AreaMeasureElem −2003201, CoordinateSystemDisplayElem −2000977), the
per-class `(m_abFlags4Bytes, m_nVisibleViewFlags)` constants of
`settings._HDR` **[V, the freshly-created specimens' values]**,
`m_deletion` = self + every element the object references.

### 2.1 The REGENERATION WIRING is a per-class constant [V, 3/3 samples]

Two header fields carry class-level dependency wiring, IDENTICAL in every
sample and therefore a format fact, not sample expression:

* `m_regenWildcards` — the CLASSES whose change re-runs the singleton
  (`settings.REGEN_WILDCARDS`): AutoJoinTracker ⇐ {CeilingAndFloor,
  FamilyInstance, Element}; WallJoinDefaultSetting ⇐ {BasicWallType};
  GCSTracker ⇐ {FamilyInstance, Grid, ReferencePoint}; MEPSystemTracker ⇐
  {RbsCurve, MechanicalEquipmentSet, FamilyInstance, RbsSystem,
  RbsSystemType}; MEPComponentTracker ⇐ {RbsCurve, FabricationPart,
  LayoutNode, FamilyInstance}; MEPNetworkTracker ⇐ {FabricationPart,
  FamilyInstance, Element}; RevisionCloudsOnSheetsTracker ⇐ {RevisionCloud};
  SheetsInSheetCollectionTracker ⇐ {DBViewDrafting, SheetCollection};
  AssemblyTracker ⇐ {AssemblyInstance, AssemblyType, DBView};
  LayoutNodesTracker ⇐ {Element}; KeynoteTagsOnSheetsTracker ⇐ {KeynoteTag};
  AllProjectRevisions ⇐ {RevisionNumberingSequence}; ProjectRevision ⇐
  {AllProjectRevisions}; AreaSettingsElem ⇐ {DBViewPlan, DBViewSection}.
* `m_regenOnly` — element edges: the MEP tracker constellation
  (`mep_tracker_constellation`): MEPSystemTracker → {RbsDuctSettingsElem,
  RbsPipeSettingsElem, MEPComponentTracker, LayoutNodesTracker};
  MEPNetworkTracker → {duct settings, pipe settings, MEPComponentTracker,
  MEPNetworkDataElem}; LayoutNodesTracker → {MEPComponentTracker};
  MEPNetworkDataElem → {MEPNetworkTracker}; GCSTracker → {UnitsElem};
  RbsDbViewSystemNavigator → {AllProjectPhases, UnitsElem,
  WorksetVisibilitySettingsElem} (+ deferred parent = MEPSystemTracker);
  ReinforcementSettings → {UnitsElem}; a phase-foldering BrowserOrganization
  → {the ProjectPhases}; a user WorksharingViewModeSettings → {the project
  one}.

## 3. Constructor catalogue (field maps)

Values in every constructor are one of: a **format constant** (enum code,
built-in id, required token), a **published fact** (NEC / ISO / SMACNA
data), a **schema sentinel** (−1, [], null), or **OURS** (our house standard,
each documented at its constant).  The docstring of each function is the
authoritative field map; below is the summary per group.

### 3.1 The pen table — `pen_width_table` (`PenWidthTableElem`) [V byte-exact vs rst 2 / rme 2]

`m_pPenWidthTable` → `PenWidthTable` { `m_modelPenInfo` = one
`PenInfoForScale{m_invertedScale (scale denominator), m_pens[16] (feet)}`
per scale breakpoint; `m_perspectiveModelPenInfo` and `m_draftPenInfo` =
single scale-independent vectors (`m_invertedScale` −1) }.  16 pens = format
constant.  **OURS:** widths = the ISO 128 / DIN 15 preferred line series
(0.13 … 2.0 mm, a fact) + our coarse extension to pen 16; breakpoints = our
imperial scale ladder (24/48/96/192/384/768) with the "coarser scale ⇒ shift
finer" rule (`pen_series_mm`).  Autodesk's table (0.18 … 9.0 mm ×3) is not
reproduced (test asserts the vectors differ).  The REAL project table has
`m_famId` −1 (element id 2 in every sample); the samples' 8 family-scoped
copies belong to the curtain SYSTEM families and are not needed.
Registry: `PenWidthTableInfo.m_penWidthTableElemId`.

### 3.2 The project browser — `browser_organization` + `default_browser_organizations` [V byte-exact vs 8 specimens across rst / rac / rme]

`BrowserOrganization` = Symbol + { `m_type` (tree: 0 views / 1 sheets /
3 schedules [I] / 4 the fourth tab [I]), `m_folderDefinitions[]`
{`AggregatedParameter{m_paramIdPath[]}`, `m_numCharsToUse`},
`m_sortParameter` (path [−1] = none), `m_bSortOrderAsc`, `m_filters[]`
{parameter path, `ParamStorage` value (storage type 3 = string, 0 =
empty), relation 0 = / 1 ≠}, `m_bDefault`, `m_category` −1 }.  Parameter
paths key on BuiltInParameter ids (interface: −1012106 family-and-type,
−1005112 view name, −1007401 sheet number, −1012102 phase, −1005163
discipline, −1005207 viewport sheet number, −1006322 issue date, −1007404
drawn by, −1007400 sheet name); a PROJECT-parameter path (positive id) joins
the deletion set [V rme 709497].  **The four `all` defaults** (one per tree,
name `all` = Revit's fixed built-in token, `m_bDefault` true) are required
shape; **our two house schemes** (views: Discipline / Phase; sheets: 2-char
sheet-series prefix) replace Autodesk's shipped seven ('not on sheets' /
'Phase' / 'Discipline' / …).  Registry: `BrowserOrganizationTracking`
(`m_elemIdSet`, `m_currentBrOrgTypeToBrOrgMap` = tree→default,
`m_folderNameToIdMap` / `m_setExpandedNodes` = regenerated caches,
emptied) + `AppInfoSystemFamiliesNames` (a document-local key each).

### 3.3 The system navigator — `system_navigator` (`RbsDbViewSystemNavigator` + Viewer + Viewport + DBDrawing) [V vs rst 69851..69854]

The MEP System Browser's implicit view.  The class adds ZERO fields to
`DBView`; the constellation is exactly the PROJECT VIEW's (skeleton
`new_project_view`): the view (name `???` = required token, scale 0.01,
plan-like frame view +Z / up +Y, `m_pParamValueSetInt` null, dimmer sun
30/50, own display defaults: surfaces 1, static-RRT page width 12) + a
`Viewer` (elevation-less plan frame, bounds inactive, ortho, gstep) + a
`Viewport` (appearance edges → its type / the view / the viewer, regen →
viewer) + a `DBDrawing`.  Built by re-using `skeleton.dbview_base` /
`_viewer_common` / `new_viewport` / `new_dbdrawing`.  Registry:
`DBViewInfo.m_DBViewSystemNavigatorId` + `m_DBViewsIndex`;
`DBDrawingInfo.m_DBDrawingsIndex`.  [U]: whether the reader needs the
navigator's draw-filter category exclusions (ours: OUR empty policy).

### 3.4 The named singletons

| class | constructor | definition (field → value class) | proof |
|---|---|---|---|
| `StructSettingsElem` | `struct_settings` | 40 fields: symbolic cutbacks / brace offset / column cutback (OUR 3/32", 1/16"), analytical snap & support tolerances (OUR 1'-0"), load-display slopes, force range, brace symbol enum, four boundary-condition FAMILY ids (−1: family-free base; K3 nulled this path in a passing file), 14 policy booleans | V byte-exact rst 54663 |
| `WallJoinDefaultSetting` | `wall_join_default_setting` | `m_defaultSettingRecordArr` [] + `m_wallPartFlag` 0 (empty in every sample) | V rst/rac/rme |
| `AutoJoinTracker` | `auto_join_tracker` | `m_map` [], `m_keepOldOverlappingElemsUnjoined` (the one setting), `m_excludedIds` | V |
| `KeynoteTable` | `keynote_table` | `m_oKeyBasedTreeEntries` → `KeynoteEntryTable{m_keyBasedTreeEntrySet [{KeynoteEntry{childrenKeys, key, parentKey, text}, key}], m_orphans}`, `m_lastReadSucceeded`, `m_name` ('Standard' = built-in token), `m_isBuiltIn`, cells = `ExternalFileReferenceCell` + `ExternalResourceReferenceCell` (the keynote file reference). **OURS: EMPTY table** (no keynote file — the samples embed Autodesk's 3,840-row `RevitKeynotes_Metric.txt` + an employee's local path; the constructor accepts a job's own rows) | V structure vs rst/rac/rme; the 3,840-row tree reproduces exactly |
| `KeynotingSystem` | `keynoting_system` | `m_keynoteTableId` → the table, `m_isNumberBySheet` | V |
| `InitialViewSettings` | `initial_view_settings` | `m_initialViewId` (−1 = last viewed) | V |
| `ReconcileBrowserSettingsElem` | `reconcile_browser_settings` | two inline `GStyle` orphan overrides (OUR magenta / cyan-blue; theirs green), sort mode, apply flag | V |
| `ConstructionSetProject` | `construction_set_project` | Symbol `<Building>` (token), 11 surface construction ids (OURS: unassigned '' — theirs key into the shipped `Constructions.xml` energy database), 11 override flags, shading factor; a present-EMPTY AString param set | V rst 99928 |

### 3.5 The MEP settings set (K5c)

| class | constructor | definition | proof |
|---|---|---|---|
| `RbsWireSettingsElem` | `wire_settings` | tick-mark FAMILY symbols (−1), connector separator, crossing gap, home-run arrowhead LeaderStyle (−1), 5 style enums | V byte-exact rme 293123 |
| `ConduitSettingsElem` / `CableTraySettingsElem` | `conduit_settings` / `cable_tray_settings` | separator / size prefix|separator / suffix (OUR inch mark), fitting & rise-drop annotation sizes (OUR 3/32"), 4 rise/drop symbol enums, anno-scale flag | V byte-exact rme 638851/638850 |
| `RbsPipeSettingsElem` | `pipe_settings` | size punctuation, 5 rise/set-up tokens ('FOT'/'FOB'/'SU'/'SD'/'=' — universal MEP shorthand), per-CLASSIFICATION routing map (14 piping classifications 7,8,15..26 → offsets / pipe types), slope palette (in/ft; IPC code slopes = facts), specific-angle set, annotation sizes, elbow increment, connector tolerance, 6 diagram enums, 3 flags, 2 calculation-server descriptors (OURS: none selected — theirs name Autodesk's registered servers by GUID) [U] | V byte-exact rme 293122 |
| `RbsDuctSettingsElem` | `duct_settings` | as pipes + per-shape size punctuation, the rise/drop-by-shape map, per-classification routing (0..4), standard-air density / viscosity (physical facts in kg·ft·s internal units), flex length, network-calc flag | V byte-exact rme 293121 |
| `RbsDuctSizesElem` | `duct_sizes` | `m_shapeSizes` [shape 0 rect / 1 oval / 2 round → `m_sizeData` rows {size ft, 12.0, 12.0, in-list, sizing}]; OUR SMACNA-customary size lists | V rme 293120 |
| `RbsPipeSizesElem` | `pipe_sizes` | material → connection → schedule → sizes (keyed by the piping-catalog elements; the pipe catalog is that stream's territory) | V rme 293159 |
| `RbsWireSizesElem` | `wire_sizes` (+ `wire_sizes_from_house_table`) | `m_mapMaterials` [RbsWireMaterialType id → {temperature ratings [rating id → {28 wire sizes {size, ampacity, diameter ft, in-use}, insulation-id set}], ground-size map [rating A → size], correction-factor bands (Kelvin) per rating}], `m_mapPowerFactors` (impedance data per material / poles / size), `m_mapWireDiameters`, `m_bInitialized`; DATA = NEC 310.16 / 310.15(B)(1) / 250.122 / Ch.9 T8 facts (`house_standard.WIRE_AMPACITY_TABLE`, `settings.NEC_*`) | V byte-exact rme 293190 |

The wire-sizes table keys on the wire catalog's `RbsWireMaterialType` /
`RbsWireTemperatureRatingType` / `RbsWireInsulationType` symbols (constructors
in `rvt.genesis.types`); `wire_sizes_from_house_table` builds the table from
the house standard's NEC data given those ids.

### 3.6 The small singletons + the twelve EMPTY TRACKERS (K5d)

`EMPTY_TRACKERS` (27 classes) = singletons whose ENTIRE body is empty
containers / false flags = regeneration bookkeeping with **no free choice**
(constructed via `tracker(class)`): AssemblyTracker, GCSTracker (regen →
UnitsElem), KeynoteTagsOnSheetsTracker, RevisionCloudsOnSheetsTracker,
SheetsInSheetCollectionTracker, LayoutNodesTracker, MEPComponentTracker,
MEPNetworkTracker, MEPSystemTracker, MEPNetworkDataElem,
AnalyticalToPhysicalRelationManager, ReactionsUpToDateElem, GraphicsCache,
ExternalParamLock, DaylightSourceIdSet, WorksetVisibilitySettingsElem,
Dwg2dExportUserSettingsData, STEPExportSettings, ZoneScheme,
RvtLinkInstanceAppearanceParentElem, SketchGridAppearanceParentElem,
FabricationServiceSettings, CurtaSystemFaceManager,
StructuralConnectionSettings, CircuitNamingTypeSetting — each **[V
byte-exact body vs rst/rac/rme]**.  Plus the small parameterised ones:
`auto_cam_settings` (ViewCube home unset, scene front +Y / up +Z),
`halftone_underlay_settings` (50 % halftone), `multiple_values_indication_
settings`, `coordinate_system_display` (internal-origin GPoint marker; the
regenerable origin-symbol display geometry is omitted → SerializedDummy
[U probe]), `active_geo_location_tracking` (project + active GeoLocation),
`default_divide_settings`, `project_copy_settings` /
`copy_watch_properties` (the 16-category MEP copy/monitor set = interface;
OURS = no linked model), `model_graphics_styles` (`<Shading>` /
`<Raytracing>` token pair → the document sun), `area_settings` (room-
bounding flags), `route_analysis_settings` (doors ignored; OUR 8"/6'-8"
zone, 4.4 ft/s pace), `mep_hidden_line_settings` (`<Hidden Lines>` −2000042,
OUR 1/16" gaps), `fabrication_settings` (no ITM database), `fabrication_
settings_element` (45/90° rotations), `sse_point_visibility_settings`,
`reinforcement_settings` (16 fixed abbreviation SLOTS — 10 area (tag 0) + 6
path (tag 1), slot names + resource ids = interface [V 3/3]; the abbreviation
VALUES are ours: T1/T2/B1/B2/IF/EF/…, not Autodesk's '(T)'/'(B)'/'TOP'/…),
`energy_data_settings` (OUR analysis parameters; building type −1 = the
HVAC-load catalog absent), `revision_constellation` (Numeric + Alphanumeric
built-in sequences [tokens], one revision, the AllProjectRevisions table —
OUR blank description/date, not the 'Revision 1'/'Date 1' placeholders),
`print_settings` (OUR US-Letter default), `view_sheet_set`,
`worksharing_view_mode_settings` (OUR status colours), `area_measure` (OUR
two schemes citing IPMS / BOMA methods).

### 3.7 The SYSTEM view-family table — `system_view_type_table` (19 `DBViewType`) [V vs rst 49552 / 1470382]

One `DBViewType` per project view family = per `m_systemFamilyIdx` (the
19 indices 102..121 sans 110: 3D, walkthrough, rendering, schedule, cost
report, sheet, drafting, floor plan (dir 0), ceiling plan (dir 1), section,
detail, elevation, loads report, pressure-loss report, legend, panel
schedule, graphical column schedule, structural plan (dir 0), analysis
report) — built by the skeleton's proven `new_view_type` with head / tag /
callout attribute references −1 (annotation content) and OUR names
(`house_standard.gen`, e.g. 'GEN Plan', 'GEN RCP', 'GEN Framing Plan'), ref
label 'SIM.'.  The house standard already builds the 3D / floor-plan /
ceiling-plan trio; the table adds the other 16 (`skip_families`).  The 72
family-scoped DBViewTypes of the samples belong to the curtain SYSTEM
families' family-editor documents (m_famId scoping) and are NOT project
view types.

## 4. The built-in style CATALOG (`rvt.genesis.catalog`) — the K6 branch [V]

**The enum is a format constant, the values are ours.**  Every reader-
accepted 2026 project carries object-style GStyleElem rows for the SAME set
of built-in category ids: **1,074 categories, each with exactly one
projection row, 333 also with a cut row — identical to the id in rst / rme
/ rac** (`derive_builtin_category_enum`; frozen in
`experiments/genesis/singletons/builtin_category_enum.json`, ids + cut flag
ONLY, no value read).  This is Revit 2026's registered graphic-category enum
(the public `BuiltInCategory` allocation extended with the built-in
sub-categories, ~10 id bands −2000xxx…−2010xxx), an interface constant we
may enumerate.  `builtin_style_catalog(ids, exclude_categories=<the base's
own>)` emits one `types.new_gstyle` object-style row per enum entry (+ cut
where cuttable), coloured / weighted by **OUR discipline scheme**
(`catalog_scheme()` = `house_standard.HOUSE_SCHEME` with the neutral
disciplines' pure black replaced by OUR INK 0x181818) applied by **OUR
classification RULE** (`classify_category`: the house standard's explicit
categories; else the MEP sub-range piping / electrical / mechanical; else
the id BAND → discipline).  Guard test: **0 of 1,407 generated rows are
value-identical (pen, colour, pattern, screen-sized) to the quarantined
Autodesk table** (the assayer's own diff, run as a test).  Registry:
`CategoryTracking.m_gstyleData` (one row per style).

## 5. The ADocument registry map + `apply_adoc_registry` [V per class]

`settings.ADOC_REGISTRY` records the surface(s) each class is indexed by
(enumerated against rstbasic's ADocument — no class left unaccounted):

| surface | classes |
|---|---|
| `UniqueElementsTracking.m_elemIds[pos]` (72 compiled-in positions, `G1_registry_maps.json:UET_POS_TO_CLASS`) | 48 singleton classes (StructSettings, wall/auto-join, wire/duct/pipe settings & sizes, initial view, the trackers, area/energy/reinforcement/route/fabrication/…, AllProjectRevisions, GraphicsCache, ActiveGeoLocationTracking, CoordinateSystemDisplay …) |
| named AppInfo scalar | PenWidthTableElem → `PenWidthTableInfo`; RbsDbViewSystemNavigator → `DBViewInfo` (+ views index; its DBDrawing → `DBDrawingInfo`); HalftoneUnderlaySettings → `HalftoneUnderlaySettingsAppInfo`; ExternalParamLock → `ExternalParamTracking`; WorksharingViewModeSettings → `WorksharingDisplaySettingsTracking.m_sharedDisplaySettingsId` |
| named AppInfo id-set (`m_elemIdSet`) | KeynoteTable → `KeynoteTableTracking` (+ its UET slot); KeynotingSystem → `KeynotingSystemTracking`; RevisionNumberingSequence → `RevisionNumberingSequenceTracking`; AreaMeasureElem → `AreaMeasureTracking`; ZoneScheme → `ZoneSchemeTracking`; PrintSettings → `PrintSettingsTracking`; ViewSheetSet → `ViewSheetSetTracking` |
| `BrowserOrganizationTracking` | BrowserOrganization (id set + tree→default map + regenerated caches emptied) |
| `AppInfoSystemFamiliesNames` (document-local keys) | BrowserOrganization, ConstructionSetProject, DBViewType (+ any class in the maps' `SFN_TRACKED_CLASSES`) |
| `ElementTrackingData` (per-category rows) | ProjectRevision (its category) |
| `CategoryTracking.m_gstyleData / m_categoryData` | the catalog's GStyleElem / CategoryElem rows |
| NOT referenced | DaylightSourceIdSet, CopyWatchProperties, ModelGraphicsStyle, CurtaSystemFaceManager |

`apply_adoc_registry(tree, records, maps=G1_registry_maps.json)` edits a
decoded `rvt.adocument` value tree in place, only ADDING our ids (existing
entries kept), and returns per-surface counts + a skip list; the composer
proves the edited tree re-encodes/decodes identically and that the ADocument
references no id absent from the file (0 dangling).

## 6. The ownership boundary (what these constructors do NOT emit)

* the settings CATALOGS the census's "all four PASS" branch would need
  (HVACLoadSpaceTypeElem ×125 / HVACLoadBuildingTypeElem ×33 /
  BuildingOperatingYearSchedule / HVACLoadScheduleElem = Autodesk's shipped
  HVAC energy database; RbsPipeSchedule/Material/Connection type catalogs;
  ParamElemElectricalLoadClassification ×108) — flagged in the record as the
  next constructor queue if K3/K4/K5/K6 all PASS;
* the annotation-attribute types the view types reference (callout /
  section / elevation heads, DimensionStyle, LeaderStyle) — annotation
  content (the family layer, K3/K4's question);
* the AssemblyCodeTable / a LOADED keynote database — Autodesk product data
  (our KeynoteTable is empty; a job may pass its own rows).

## 7. Reproduction

```
.venv/bin/python -m rvt.genesis.settings           # constellation: 100 records, roundtrip + refs
.venv/bin/python -m rvt.genesis.catalog [--derive] # enum + 1,407-row catalog roundtrip
.venv/bin/python -m pytest tests/test_genesis_settings.py -q     # 45 tests
.venv/bin/python experiments/genesis/singletons/build_ladder.py  # S1..S5 + probes.json
```

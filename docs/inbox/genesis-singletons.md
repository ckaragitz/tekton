# genesis-singletons — the K5/K6-FAIL branch: settings-singleton + catalog CONSTRUCTORS and the pre-built S-ladder (workstream record, 2026-08-03)

Charter: IF the Autodesk reader requires the document-settings singletons /
the style catalog our constructed base omits (a K5x / K6 FAIL on the
triage ladder), genesis needs OUR constructors for them — so build the
constructors NOW, field-by-field with reconstruction proofs, for the
census's ranked suspects (PenWidthTableElem — the census's #1 suspect —,
the BrowserOrganization set + system navigator, StructSettingsElem,
WallJoinDefaultSetting, AutoJoinTracker, KeynoteTable, InitialViewSettings,
the Rbs*Settings + Rbs*Sizes singletons, the UniqueElement settings
singletons, the 19-family SYSTEM view-type table, and the COMPLETE
category/GStyle catalog), and PRE-BUILD the add-back ladder S1..S5 on the
failing base so no verdict waits on a cold start.

Territory touched ONLY (as chartered): `src/rvt/genesis/settings.py` (new),
`src/rvt/genesis/catalog.py` (new), `tests/test_genesis_settings.py` (new,
45 tests), `experiments/genesis/singletons/` (S1..S5.rvt + reports +
`probes.json` + `builtin_category_enum.json` + the composer
`build_ladder.py`), `docs/writer/genesis-settings.md` (new, the field-map
document), this record.  NO existing `src/rvt/*.py`, `src/rvt/genesis/
{types,skeleton,house_standard}.py`, tool or test edited — the proven
layers are IMPORTED (types blank/element/symbol/record machinery, skeleton
DBView + viewer + viewport + drawing constructors, house-standard
vocabulary, encode/commit/adocument/validate).  No browser / viewer use;
the S files are LEFT ON DISK for the orchestrator's certification.

## Result in one screen

* **`src/rvt/genesis/settings.py`** — constructors for **69 document-
  settings classes** (every count-invariant Tier-1 singleton of
  `docs/writer/required-set.md` that is a settings object, the K5a/b/c/d
  populations) + the **19-family SYSTEM view-type table** + the ADocument
  registry map / population engine (`ADOC_REGISTRY`, `apply_adoc_registry`).
  The standard constellation (`standard_settings`, 100 records / 73
  classes) round-trips **clean AND byte-exact 100/100 with 0 dangling
  references**; every constructor is PROVEN by parametric reproduction of
  its Autodesk specimens (feed the specimen's own values → object equal),
  header + body, across rst / rme / rac (`tests/test_genesis_settings.py`,
  the `test_reproduce_*` tier).
* **`src/rvt/genesis/catalog.py`** — the built-in-category graphic-style
  ENUM derived and frozen (**1,074 categories, 333 cuttable, IDENTICAL in
  rst / rme / rac** = a per-release format constant) and the COMPLETE
  object-styles table generator: **1,407 GStyleElem rows** (1,074
  projection + 333 cut) coloured / weighted by OUR discipline scheme, round-
  trip 1,407/1,407, and **0 rows value-identical to the quarantined Autodesk
  table** (the assayer's diff, run as a test).
* **The S-LADDER, built and certified** (`experiments/genesis/singletons/`):
  five add-back candidates on G1_candidate, EVERY ONE **validator VALID
  0 errors / 0 warnings, ADocument dangling ids 0, registries repopulated,
  every new record decoded clean** (`build_ladder.py`, per-rung
  `S*_report.json`).  `probes.json` documents what each PASS/FAIL names.

## The S-LADDER (add-back rungs on the failing base)

Each rung = `experiments/genesis/G1_candidate.rvt` + OUR content, committed
through the proven path (`commit_new_elements` → the canonical unit-0
re-blocker), then the ADocument (`Global/Latest`) registries repopulated
over the new ids via the byte-exact codec, then certified (validator +
ADocument self-decode + dangling-id scan).  Every rung is built directly
from the BASE (independent files; content cumulative).

| rung | adds (our ids ≥ 1,600,000) | +elements | tests the ONE thing | bytes |
|---|---|--:|---|--:|
| **S1** | `PenWidthTableElem` (our line-weight table) | 1 | K5a: the reader requires the project pen table | 331,776 |
| **S2** | S1 + 6 `BrowserOrganization` (4 per-tree `all` defaults + 2 house schemes) + the system-navigator constellation (`RbsDbViewSystemNavigator` + Viewer + Viewport + DBDrawing) + `ReconcileBrowserSettingsElem` + `ConstructionSetProject` | 13 | K5b: the project-browser / system-navigator constellation | 335,872 |
| **S3** | S2 + `StructSettingsElem`, `WallJoinDefaultSetting`, `AutoJoinTracker`, `KeynoteTable` (empty) + `KeynotingSystem`, `InitialViewSettings` | 19 | the charter's named singletons | 335,872 |
| **S4** | S3 + the COMPLETE built-in style catalog (1,320 rows for the 1,008 categories the base does not style) | 1,339 | K6: the reader requires the full object-styles table | 380,928 |
| **S5** | S3 + EVERY other constructed singleton (MEP wire/duct/pipe/conduit/cable-tray settings, duct sizes, the MEP tracker constellation, all UniqueElement singletons & trackers, revisions, print, worksharing / export / area / energy, model graphics styles, the wire catalog symbols + wire-sizes table, the 16 remaining system view types) + the S4 catalog = **the census-complete candidate** | 1,420 (76 classes) | everything the K-ladder can name at once | 385,024 |

Registry population per rung (from the reports): S5 = 49 UET slots
filled + `PenWidthTableInfo` + `HalftoneUnderlaySettingsAppInfo` +
`ExternalParamTracking` + `WorksharingDisplaySettingsTracking` scalars, 8
named id-sets, 6 browser orgs + the tree→default map, the navigator in
`DBViewInfo` (+ views index) and `DBDrawingInfo`, 8 ETD rows (the wire
catalog symbols + the revision), 3 default types, 30 system-family keys,
1,320 `CategoryTracking` rows — G1's 5 populated `UniqueElementsTracking`
slots become 54.

### Reading the verdicts (also in `probes.json:reading_the_results`)
* **K5a FAIL** → upload **S1**.  **K5b FAIL** → **S2**.  **K6 FAIL** → **S4**.
  **K5c FAIL** (MEP settings) → **S5** (they live only there).  **K5d FAIL**
  → **S3** then **S5**.
* **K5 and K6 both FAIL / unclear** → upload **S5** first (census-complete);
  if it PASSES, bisect downward with S3 / S1 / S2 / S4.  Upload order by
  information value: **S5, S1, S4, S2, S3.**
* **S5 FAILS** → the required class is NOT a settings singleton nor the
  style catalog: the family layer (K4) or the settings CATALOGS this stream
  did not build (below).

## New format findings (evidence — merge into KNOWLEDGE.md)

1. **The settings singletons' regeneration WIRING is a per-class format
   constant** [V, identical rst / rme / rac]: `ElementHeader.m_parents.
   m_regenWildcards` names the CLASSES whose change re-runs each tracker
   (AutoJoinTracker ⇐ {CeilingAndFloor, FamilyInstance, Element};
   WallJoinDefaultSetting ⇐ {BasicWallType}; GCSTracker ⇐ {FamilyInstance,
   Grid, ReferencePoint}; MEPSystemTracker ⇐ {RbsCurve,
   MechanicalEquipmentSet, FamilyInstance, RbsSystem, RbsSystemType}; …
   full table `settings.REGEN_WILDCARDS`), and `m_regenOnly` carries a fixed
   element-edge constellation among the MEP trackers (system tracker →
   duct settings + pipe settings + component tracker + layout tracker;
   network tracker → the same + network data; layout → component;
   network data → network tracker; GCS tracker → UnitsElem; the system
   navigator → AllProjectPhases + UnitsElem + WorksetVisibilitySettings,
   deferred → MEPSystemTracker).  A settings constructor that omits these
   emits a header no sample carries.
2. **Every settings singleton's ADocument registry surface, enumerated**
   [V]: 48 classes → `UniqueElementsTracking` positional slots; named
   AppInfos for the rest — `PenWidthTableInfo.m_penWidthTableElemId`,
   `DBViewInfo.m_DBViewSystemNavigatorId`, `HalftoneUnderlaySettingsAppInfo`,
   `ExternalParamTracking.m_externalParamLockId`,
   `WorksharingDisplaySettingsTracking.m_sharedDisplaySettingsId`, the
   `m_elemIdSet` trackers (KeynoteTable, KeynotingSystem,
   RevisionNumberingSequence, AreaMeasure, ZoneScheme, PrintSettings,
   ViewSheetSet), `BrowserOrganizationTracking` (+ its tree→default map),
   `AppInfoSystemFamiliesNames` (BrowserOrganization / ConstructionSetProject
   / DBViewType), `ElementTrackingData` (ProjectRevision), and **four
   genuinely UNREFERENCED classes** (DaylightSourceIdSet,
   CopyWatchProperties, ModelGraphicsStyle, CurtaSystemFaceManager).
   `settings.ADOC_REGISTRY` is the table; `apply_adoc_registry` applies it.
3. **The graphic-category ENUM: 1,074 built-in categories carry object-
   style rows in EVERY 2026 file, 333 of them cuttable, identical to the id
   across samples** [V] — the object-styles table's KEY set is a registered
   per-release constant (like the BuiltInCategory enum), extending the
   public API enum with the built-in sub-categories across ~10 id bands.
   Frozen (ids + cut flag only) in `builtin_category_enum.json`.
4. **The 19 project view families = one `DBViewType` per
   `m_systemFamilyIdx` 102..121 (sans 110)** [V]; the samples' 72 other
   DBViewTypes are curtain-SYSTEM-family editor types (m_famId-scoped),
   not project view types (corroborates genesis-triage-a finding 1).
5. **The MEP System Browser is a full view constellation** [V]:
   `RbsDbViewSystemNavigator` adds ZERO fields to `DBView` and is born with
   its own Viewer + Viewport + DBDrawing (same shape as the project view),
   named `???`, registered in `DBViewInfo.m_DBViewSystemNavigatorId`.
6. **A KeynoteTable's 3,840 entries = Autodesk's shipped
   `RevitKeynotes_Metric.txt`** (CSI MasterFormat divisions + an employee's
   local file path in its `ExternalResourceReferenceCell`) in EVERY sample
   incl. the structural ones — product data, like the Forge corpus and the
   AssemblyCodeTable (UniFormat).  OUR base carries an EMPTY table (the
   constructor accepts a job's rows).  **Counsel item** if a job wants to
   ship keynote content: the database rows are Autodesk's.
7. **Product-default VALUES ride in the samples' settings singletons**: the
   pen table's 0.18…9.0 mm series, StructSettings' metric-template
   tolerances, the rebar abbreviations '(T)'/'(B)'/'TOP', the reconcile-
   hosting greens, the '<Building>' energy construction ids
   ('ASHWL-66'…, keyed into `Constructions.xml`), the worksharing status
   colours — all replaced by OUR documented values (per-constant provenance
   in `settings.py`).  The FIXED TOKENS the constructors DO reproduce
   (browser `all`, keynote `Standard`, `<Building>`, `<Shading>` /
   `<Raytracing>`, `???`, the Numeric / Alphanumeric sequence names + the
   A..Z alphabet, the 16 rebar-abbreviation SLOT names + resource ids, the
   copy/monitor MEP category set) are enumerated in §"Counsel list" below.

## The NO-FREE-CHOICE population (why the provenance ledger reads ~1,500 "clones")

`tools/provenance.py --baseline all` on **S5** reads: created 131 /
modified 6 / **cloned 1,509** (byte-shingle similarity ≥ 0.50) — versus
G1's 135 clones.  Every added clone is a **NO-FREE-CHOICE machinery record**
whose byte payload is required tokens + sentinels with ≤ 2 free values:

| population | count | why the bytes cannot differ | our free values |
|---|--:|---|---|
| built-in `GStyleElem` catalog rows | 1,320 (of the 1,404 GStyle "clones"; the rest are the house standard's own 84) | a row is {category id (format constant), style type, pen, colour, pattern −3000010/−1, material −1, owner −1} — ~30 bytes, 2 free | pen + colour: OUR scheme, **0/1,407 value-identical** to Autodesk's table (test) |
| the 27 EMPTY TRACKERS + tiny singletons (ExternalParamLock 0.67, RvtLink/SketchGrid appearance parents 0.6, ReconcileBrowserSettings 0.5 …) | ~30 | body = empty containers / fixed flags; byte-identical is the ONLY possible value | none (ReconcileBrowserSettings: our two colours) |
| the four browser `all` defaults (0.86–0.88) | 4 | name `all` = the fixed built-in default; one folder/sort choice per tree | our 2 house schemes are separate records |
| `ConstructionSetProject` `<Building>` (0.83) | 1 | the token + 11 empty construction strings + 11 false flags | (ours = unassigned; theirs name their database) |
| `KeynoteTable` empty `Standard` (0.64) | 1 | the built-in table's fixed name/flags + an empty tree | entries [] (ours: empty) |
| `RevisionNumberingSequence` ×2 (0.83 / 0.94) | 2 | the built-in Numeric / Alphanumeric sequences: name tokens + the A..Z alphabet | none possible |
| `ModelGraphicsStyle` `<Shading>` / `<Raytracing>` (0.62 / 0.71) | 2 | token pair + a few display ints | our intensities |
| view frames (Viewer / Viewport / DBDrawing / DBViewProject / SketchPlane / ClipBox / ExtentElem) | ~20 | the house standard's known frame machinery (already in its NO_FREE_CHOICE list) | — |

Everything genuinely authored reads **created**: the pen table (0.42 max
similarity), the system navigator's own values, StructSettings (0.32),
KeynotingSystem, ProjectRevision (0.46), AllProjectRevisions (0.40), the 19
view types (~0.30), duct sizes, area schemes, the MEP settings set …  The
catalog trade-off is inherent: **if K6 FAILS, the reader REQUIRES the full
table, and a full table is 1,407 no-free-choice rows** — the counsel item is
the CLASS, decided once, not row by row (values provably ours: 0 identical).

## Counsel list (this stream's additions)

* **The complete object-styles table** (S4/S5): 1,407 rows over Autodesk's
  registered graphic-category ENUM (ids = format constants) with OUR values
  (0 value-identical rows). Class ruling: is a complete style table over
  their category enum shippable? (Only load-bearing if K6 FAILS.)
* **Required-token vocabulary reproduced verbatim** (interface, no free
  choice): browser default name `all`; keynote table `Standard` / built-in
  flag; `<Building>`; `<Shading>` / `<Raytracing>`; the project & navigator
  view name `???`; revision sequence names `Numeric` / `Alphanumeric` + the
  A..Z alphabet; the 16 rebar-abbreviation slot NAMES + resource ids (our
  VALUES); the 16-category copy/monitor MEP set; the MEP shorthand tokens
  ('FOT'/'FOB'/'SU'/'SD'/'BU'/'BD'/'='); the standard-air physical constants.
* **Interface identifiers we chose NOT to reproduce** (probe rows instead):
  the MEP calculation-server GUIDs (Colebrook / Duct Pressure Drop /
  Plumbing Fixture Flow — Autodesk's registered service ids; ours =
  none-selected, null GUID) and the energy `Constructions.xml` codes (ours
  unassigned).  If the reader requires a selected server, the fix is a
  one-line default change (`_server_info`) and becomes a token item.
* **Autodesk product DATA deliberately NOT reproduced**: the keynote
  database (3,840 rows), the assembly-code (UniFormat) table, the HVAC
  space/building-type & schedule catalogs, the pen/tolerance/abbreviation
  VALUES.  A job that wants keynote content passes its OWN rows.

## Reader-tolerance PROBE ROWS (unknowns the viewer decides)

1. `CoordinateSystemDisplayElem` — ours omits the regenerable internal-
   origin display geometry (geomSteps generator + the 691-byte GElement
   symbol rep) and emits SerializedDummy (the wall / camera precedents were
   accepted).  If a rung with it fails and one without passes, add the
   generator node.
2. MEP calculation servers unselected (null GUID) in Rbs*SettingsElem.
3. Navigator draw-filter category exclusions empty (OUR visibility policy
   vs the samples' ~57 analytical exclusions).
4. Empty keynote table (no external file); the `KeynotingSystem` still
   points at it.
5. `EnergyDataSettings.m_buildingTypeId` −1 (the HVAC building-type catalog
   is absent) — the census's untested "all four PASS" branch.

## If K3, K4, K5 and K6 ALL PASS — the next constructor queue (not built here)

The census's remaining count-invariant / required-class populations that
NO K rung isolates (all present in every rung): `HVACLoadSpaceTypeElem`
×125, `HVACLoadBuildingTypeElem` ×33, `BuildingOperatingYearSchedule` /
`HVACLoadScheduleElem` ×25–27 (Autodesk's energy database — product data;
a constructor needs OUR space-type set or a counsel ruling), the piping
catalog (`RbsPipeScheduleType` ×10–13, `RbsPipeMaterialType` ×5,
`RbsPipeConnectionType` ×8, `PipeSegment`) which `RbsPipeSizesElem` keys on
(constructor exists, catalog does not), `ParamElemElectricalLoadClassification`
×108, `LoadCaseElem` / `LoadNatureElem` ×8, `AreaTypeElem` ×8 +
`AreaSchemePlanTopologies` (our `area_measure` records reference them as
−1), `ColorFillSchema` ×9–10, `NumberingSchema` ×3, and the annotation
attribute types (DimensionStyle ×12, LeaderStyle ×19, TagNoteAttributes /
FilledRegionAttributes / CalloutTag / SectionAttributes /
InteriorElevAttributes / ViewportAttributes / GridAttributes /
LevelAttributes ×1) — the annotation set is the family/annotation-content
layer (K2/K3's territory).  Rank for the next stream: (1) the HVAC / energy
catalogs (count-invariant, largest), (2) the piping catalog + PipeSegment,
(3) the load-classification parameter elements, (4) area types + plan
topologies, (5) colour-fill / numbering schemas.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`tools/genesis_assemble.py` (genesis-2)** — consume this module: the
  own-content build (`build_our_content` → `hs.build_catalog`) could take
  `settings.standard_settings(ids, tier=..., doc_ids=cat.ids)` +
  `catalog.builtin_style_catalog(ids, exclude_categories=<house set>)` as
  a second content source, and its `_populate_registries` could delegate the
  settings surfaces to `settings.apply_adoc_registry` (the map covers 62
  more classes than the assembler's five singleton slots).  Then a G1
  candidate is BORN census-complete instead of patched.
* **`src/rvt/genesis/house_standard.py` (own-content)** — three data
  hand-offs already consumed here: `WIRE_AMPACITY_TABLE` (now feeds
  `wire_sizes_from_house_table`), `ELECTRICAL_SETTING` (the specific-angle
  set reused as `MEP_SPECIFIC_ANGLES_DEG`), `HOUSE_SCHEME` / `gen` (the
  catalog + naming).  Proposed additions to the house standard: OUR
  keynote seed rows (if we ever ship keynotes), OUR area-scheme pair,
  OUR browser-scheme pair — currently constants inside `settings.py`
  (`AREA_SCHEMES`, `default_browser_organizations`); moving them keeps ALL
  house choices in one module.
* **`src/rvt/genesis/skeleton.py` (skeleton)** — `new_viewport` /
  `_viewer_common` are re-used for the navigator; the viewport's appearance
  / regen header edges (→ its type, view, viewer / regen → viewer) are
  patched here (VERIFIED on rst 69853); suggest folding into
  `new_viewport(appearance=..., regen_only=...)` for the plan-view viewports
  too.  Also `element_header` could accept `wildcards=` (the settings
  stream's `REGEN_WILDCARDS` mechanism) so tracker-style edges are
  first-class.
* **`src/rvt/validate.py` (validation)** — a per-class regen-wildcard /
  regenOnly conformance check (finding 1) and the singleton-registry
  coherence check (each present singleton's id sits in its registry
  surface, finding 2) would have flagged the constructed bases' 67 empty
  slots as a diagnostic warning instead of leaving it to the census.
* **`docs/writer/skeleton-census.md` / KNOWLEDGE.md owner** — merge
  findings 1–5; correct the census's "settings-catalog" row for
  `HVACLoadSpaceTypeElem` etc. as NOT tested by any current K rung.
* **`tools/sync_plugin.py`** — this stream adds two `src/rvt/genesis/`
  modules (`settings.py`, `catalog.py`) to the plugin bundle drift list;
  left for the orchestrator's post-integration sync run (the pre-existing
  cross-stream `test_plugin_sync` failure, +2 files).

## Full-suite result at handoff

`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle` → **704
passed, 3 failed** of 707 (this session; ~12 min).  This stream's tests:
`tests/test_genesis_settings.py` **45 passed** (structural round-trip /
no-dangling / no-corpus-read guards; parametric reproduction of ~40
specimens across rst / rme / rac; the enum + catalog + 0-identical-rows
guard; `apply_adoc_registry` over the real candidate ADocument; the
S-ladder deliverables' validate-0-errors + manifest checks).  The 3
failures are the pre-existing, other-stream ones every recent record lists,
none touching this stream's files: (1)
`tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` — the
plugin-bundle drift (this stream's two new `src/rvt/genesis/` modules join
the drift list; fix = the orchestrator's `python tools/sync_plugin.py`
run, outside this territory); (2)+(3)
`tests/test_provenance.py::{test_G0_resource_refs_are_counted,
test_G0_identity_dit_usernames_still_leak}` — the STALE assertions pinning
the pre-genesis-2 G0 defects (their owner's diff is in
docs/inbox/genesis-2.md).

## Reproduction (repo root, .venv python)

```
python -m rvt.genesis.settings                 # 92-record constellation: roundtrip clean+byte-exact, 0 dangling
python -m rvt.genesis.catalog                  # enum (1074/333) + 1,407-row catalog roundtrip
python experiments/genesis/singletons/build_ladder.py           # S1..S5 + probes.json (~2 s)
python experiments/genesis/singletons/build_ladder.py --only S1 --base experiments/genesis/G1a.rvt   # any base
python tools/rvt_validate.py --quiet experiments/genesis/singletons/S*.rvt  # OK errors=0 warnings=0 (5/5)
python -m pytest tests/test_genesis_settings.py -q               # 45 passed
```

Validator summary (pasted from `tools/rvt_validate.py --quiet`, this session):

```
OK   experiments/genesis/singletons/S1.rvt  errors=0 warnings=0
OK   experiments/genesis/singletons/S2.rvt  errors=0 warnings=0
OK   experiments/genesis/singletons/S3.rvt  errors=0 warnings=0
OK   experiments/genesis/singletons/S4.rvt  errors=0 warnings=0
OK   experiments/genesis/singletons/S5.rvt  errors=0 warnings=0
S5 verbose: records 4941, elements_decoded 1646, decode_failures 0,
            refs_checked 19812; ADocument dangling ids 0 (composer scan)
```

## Files for the orchestrator to viewer-test (LEFT ON DISK, no viewer used)

`experiments/genesis/singletons/probes.json` is the manifest (file → the
one thing it tests, its known FAILING sibling G1_candidate + the K-rung it
answers, what PASS / FAIL means), ordered by information value: **S5, S1,
S4, S2, S3**.  Every file: our whole partition + Globals path (the accepted
V15–V29 machinery), validator VALID 0/0, ADocument coherent (0 dangling),
identity ours (`rvt-writer`), same base GUID lineage as G1_candidate.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files: `src/rvt/genesis/
settings.py` (69 settings-class constructors + system view-type table +
`ADOC_REGISTRY` / `apply_adoc_registry`), `src/rvt/genesis/catalog.py`
(built-in category enum + complete style catalog), `tests/
test_genesis_settings.py` (45 pass), `docs/writer/genesis-settings.md`,
`docs/inbox/genesis-singletons.md` (this file), and under
`experiments/genesis/singletons/`: `build_ladder.py`, `S1..S5.rvt` +
`S*_report.json`, `probes.json`, `builtin_category_enum.json`.  Every
emitted `.rvt` = validator VALID (0 errors / 0 warnings), ADocument
0-dangling, registries repopulated, new records decode-clean.  STOPPED AT
READY — S1..S5 await the orchestrator's viewer gate; the K5x / K6 verdicts
select which rung answers.

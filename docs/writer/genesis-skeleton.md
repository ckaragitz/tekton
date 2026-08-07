# GENESIS SKELETON — the non-type scaffolding of a valid Revit project

Stream: **skeleton** (2026-08-03). Companion code: `src/rvt/genesis/skeleton.py`
(constructors + minimal Global streams), tests
`tests/test_genesis_skeleton.py`, record `docs/inbox/skeleton.md`.
Sibling streams: `genesis-types` (system-family types / registries),
the reduction ladder (`docs/writer/genesis.md`, `experiments/genesis/`),
and the ADocument (`Global/Latest`) work still outstanding.

This document specifies what a Revit 2026 project must contain **beyond
element types**: the levels, phases, project information, the view
constellations, the site/coordinate skeleton, the units registry, and the
six table streams for a MINIMAL one-episode document — as we understand
them today, with every claim tagged:

- **VERIFIED** — proven by byte-exact reconstruction of a corpus specimen,
  or an invariant checked across the six corpus files, or a Revit reader
  (Autodesk viewer) result;
- **INFERRED** — consistent with all evidence but not directly proven;
- **UNKNOWN** — settled only by a Revit-open test (ranked list in §11).

Evidence base: the six Revit 2026 samples (chiefly
`rstbasicsampleproject`), the schema-directed decoder
(`rvt.objects`), the byte-exact encoder (`rvt.encode`), the six small-stream
codecs (`rvt.stream_encoders`), the 2026 `.rfa`, and the reduction ladders
(`experiments/genesis/`, R4s = deepest viewer PASS on record).

---

## 0. The headline finding: every skeleton object is constructible from scratch

For every class in this document a **constructor** in `skeleton.py` builds
the complete object *field by field from plain parameters* (no `.rvt`
opened, nothing cloned). Feeding a constructor the specimen's own parameter
values reproduces the **original record bytes** of the corresponding
`rstbasicsampleproject` element, adler32 stamp included:

| object | class id | specimen | bytes | byte-exact |
|---|---|---|---:|:--:|
| ProjectPhase 'Existing' / 'New Construction' | 0x0d17 | 12589 / 86961 | 169 / 185 | ✓ / ✓ |
| AllProjectPhases (+ header) | 0x00cc | 1 | 1,029 / 215 | ✓ / ✓ |
| PhaseFilterElem × 5 | 0x0ca7 | 371–375 | 198–222 | 5/5 ✓ |
| ProjectInfo (+ header) | 0x0d13 | 49504 | 387 / 135 | ✓ / ✓ |
| DBViewType '3D View' / 'Structural Plan' | 0x0486 | 49559 / 69847 | 244 / 260 | ✓ / ✓ |
| Level 'Level 1' (obj / header / rep) | 0x09e7 | 311 | 794 / 175 / 22 | ✓ / ✓ / ✓ |
| LevelAttributes '8mm Head' | 0x09e8 | 305 | 249 | ✓ |
| Viewer of the project view (+ header) | 0x02d4 | 231 | 579 / 143 | ✓ / ✓ |
| DBDrawing of the project view | 0x0463 | 233 | 161 | ✓ |
| Viewport of the project view (+ header) | 0x088d | 232 | 286 / 159 | ✓ / ✓ |
| ExtentElem (+ header) | 0x0672 | 245444 | 161 / 143 | ✓ / ✓ |
| SunAndShadowSettings | 0x1074 | 245446 | 280 | ✓ |
| SketchPlane (plan's fixed plane, + header) | 0x0f5d | 245451 | 332 / 151 | ✓ / ✓ |
| LightSchemeElement | 0x09f9 | 1138906 | 135 | ✓ |
| ModelClipBox (section box) | 0x0ab9 | 1138901 | 284 | ✓ |
| TrueNorth (+ header) | 0x1108 | 7850 | 177 / 143 | ✓ / ✓ |
| GeoSite (+ GeoLocation header) | 0x08e1 | 21747 / 111428 | 577 / 151 | ✓ / ✓ |
| BasePoint (survey point) | 0x023e | 111429 | 396 | ✓ |
| UnitsElem (136 format entries) | 0x111e | 19236 | 35,993 | ✓ |

40 records byte-exact in the harness; the encode→decode round trip of the
whole composed minimal skeleton (42 elements, 126 records, 29 KB of object
bytes) is clean **[VERIFIED, `test_genesis_skeleton.py`]**. The remaining
per-object differences against the sample are exclusively *sample-specific
edges* the minimal document legitimately omits (a linked-file override map,
project-browser regen edges, the phase filters' pattern/material regen
edges) — enumerated in §11.

This retires the biggest fear of the genesis plan for the skeleton layer:
**the document scaffolding is not opaque Autodesk expression that must be
copied — it is a fixed, fully mapped structure we can author.**

---

## 1. What a document contains at BIRTH (episode 0) — VERIFIED 3/3

Every corpus project descends from one ancient Autodesk ancestor document
(same element ids for the same infrastructure across the structural,
architectural and MEP templates: 1, 2, 230–233, 305, 311, 371–375, 397,
19236, 49504, …; the History birth episode GUID `e3e052f9-0156-11d5-…` is a
year-2001 GUID). The elements whose `ElemRec.creation_ep == 0` therefore
show what the format machinery inserted when that document was created:

| birth content (creation_ep 0) | rst | rac | rme | class(es) |
|---|--:|--:|--:|---|
| object styles | 188 | 191 | 191 | GStyleElem |
| fill patterns / line patterns | 22 / 13 | 22 / 13 | 22 / 13 | FillPatternElem / LinePatternElem |
| categories (extra project categories) | 15 | 18 | 18 | CategoryElem |
| materials / fonts | 13 / 6 | 13 / 7 | 18 / 8 | MaterialElem / FontElem |
| phase filters (the standard five) | 5 | 5 | 5 | PhaseFilterElem |
| the phase set singleton (**id 1**) | 1 | 1 | 1 | AllProjectPhases |
| pen table (**id 2**) | 1 | 1 | 1 | PenWidthTableElem |
| **the project view** (**ids 230/231/232/233**) | 1+1+1+1 | 1+2+?+2 | 1+1+?+1 | DBViewProject + Viewer + Viewport + DBDrawing |
| level + level type (**311 / 305**) | 1+1 | 1+1 | 0+1 | Level / LevelAttributes |
| annotation type defaults | ~10 | ~12 | ~11 | LeaderStyle, DimensionStyle, TextNoteAttributes, TagNoteAttributes, ViewportAttributes, ColorFillSymbol, … |
| a curtain-wall / basic wall type | 1 | 1 | 1 | BasicWallType (id **397**) |

Reading of this table:

- The **minimum viewable set at birth is the PROJECT VIEW constellation**
  (`DBViewProject` 230 + `Viewer` 231 + `Viewport` 232 + `DBDrawing` 233),
  present in all three lineages with `m_dbViewTypeId = -1` and name `'???'`
  **[VERIFIED 3/3]**. It is not a browsable user view; it is the document's
  root view object. NO floor plan and NO 3D view exist at birth.
- `ProjectInfo` (49504, ep 279), `UnitsElem` (19236, ep 144), the site
  elements (ep 452/167) and the phases (ep 95/378) were created by *later*
  saves/upgrades of the ancestor — a document evolves. **A genesis document
  we author creates all of them in its single episode 0** [INFERRED: a
  2026 'no template' project carries them from the start].
- The birth census is a *lower bound* of a modern minimal document, not an
  exact recipe: it lacks the site/units/project-info elements only because
  the 2001-era format did.

---

## 2. LEVELS

### 2.1 The `Level` element (class 0x9e7, category −2000240 OST_Levels) — VERIFIED byte-exact

A level is a **datum**: an infinite horizontal plane at an elevation, drawn
as a finite line with a bubble. Its record set is
`{seq101 ElementHeader, seq102 Level, seq103 SerializedDummy}` — a level
carries NO cached geometry (the rep is the 2-byte SerializedDummy)
**[VERIFIED]**. Definition fields (parameters of `new_level`):

| field | meaning | genesis value | evidence |
|---|---|---|---|
| `m_text` | level name | parameter | 311 'Level 1' |
| `m_pSurface` → `Plane.m_origin[2]` | **the elevation** (feet) | parameter | Level 2 z = 9.8425 ft = 3.0 m; racbasic Level 2 = 3.0 m (KNOWLEDGE) |
| `m_pSurface` → `Plane.m_Envelope.m_corners` | the datum plane's model extent (2 UV corners) | parameter `extent_ft` | 311: (−51.7,−87.4)–(66.5,94.2) |
| `m_pFace` (Face → its own `m_pSurf` Plane) | the same datum plane wrapped in a Face (two identical Plane objects, archive pids 4/5, Face pid 3) | derived | 311 byte-exact |
| `m_freeEnd` / `m_bubbleEnd` | 3D datum-line endpoints; genesis: (0,0,z) → (`datum_length_ft`,0,z) | parameter | 311: (0,0,0)→(30,0,0) |
| `m_refPointsForNewViews` | the two points new views use to draw the datum | = the endpoints | 311 |
| `m_cutVec` | line direction normal (0,1,0) | fixed | 311/245423 |
| `m_attrId` | the **LevelAttributes** (level type) id | parameter | 311 → 305 |
| `m_isBuildingStory` | building-story flag | parameter (False) | 311 False |
| `m_sheetTextHeight` | 0.015625 ft (3/16") text height | fixed | 311 |
| `m_v2Datum` / `m_useConstVForDatumLine3dRep` | False / True | fixed | 311 |
| `m_pParamValueSetInt` {−1007112: 1} | 'structural' int parameter every corpus level carries | fixed | 311, 694, 245423 |
| `m_pParamValueSetElementId` {−1012201: −1} | ELEM_TYPE param (levels have no family) | fixed | 311 |
| `m_geomSteps` | one `DatumPlaneGeomStep` (face-history keys [6,0,−1], m_flags 1) | fixed | 311 |
| `m_pGeomTable` | GeomTable{one entry, geomGeneratorId 1} | fixed | 311 |
| header `m_deletion` | [level type, self]; `m_regenOnly` [UnitsElem, project GeoLocation]; `m_appearanceParents` [level type, UnitsElem] | derived from params | 311 |

Optional field: `m_pLeader` (a `Leader` when the user has dragged the
head into an elbow) — `null` in the canonical form; level 694 shows the
leader variant **[VERIFIED]**. Levels placed inside a family (owned by
`m_unplacedOwnerId`) exist in racbasic and are excluded from the datum set.

**Minimum:** at least one level in every project [VERIFIED: R4/R9/R10 keep
all 9; a 'no template' Revit project has one]. Whether ZERO levels is
readable is untested and pointless (nothing to host content). The ADocument
also keeps a level table (see §9) — an ADocument coupling.

### 2.2 `LevelAttributes` (level type, class 0x9e8) — VERIFIED byte-exact

A `Symbol` (name via `SymbolInfo`) + line/text style: `m_lineAndTextAttr`
{fontId, categoryId (the level-line sub-category), background 0, bold/
italic/underline}, `m_leaderCategoryId`, `m_familyTagId` (the level-head
annotation **FamilySymbol** — Autodesk content in every sample; genesis
sets **−1** = head symbol "<none>" **[UNKNOWN acceptance — cosmetic]**),
`m_baseElevation` (0 project base / 1 survey), room-computation height,
and int params −1008002 = 0 / −1008001 = 1 [names INFERRED: head-symbol at
end 1/2 defaults]. Header flags 30, category −2000240.

### 2.3 What is NOT part of a level

No separate DatumPlane element (the plane is inline; class DatumPlane has
0 instances), no ExtentElem of its own (view-side ExtentElems hold datum
extents), no generated geometry. The plan view associated with a level is
a separate DBViewPlan whose `m_genElemId` points back at the level (§4.4).

---

## 3. PHASES

### 3.1 The minimum set — VERIFIED structure, INFERRED minimum

| element | class | minimum count | notes |
|---|---|--:|---|
| `AllProjectPhases` (**ancestral id 1**, birth episode) | 0x00cc | 1 | holds `m_phaseIds` = the ORDERED phase list (sequence = list order) and `m_arrPhasingOverrides` (4 status graphic overrides) |
| `ProjectPhase` | 0x0d17 | 1 (samples: 'Existing' + 'New Construction') | `m_name`, `m_description`; category −2000112 (OST_Phases); regen edge → AllProjectPhases |
| `PhaseFilterElem` × 5 (birth episode) | 0x0ca7 | ≥1 (default 'Show All') | `m_name`, `m_bDefault`, 7-slot `m_phaseStatusPresentation` |

- **Phase order lives in `AllProjectPhases.m_phaseIds`, not in the phases**
  [VERIFIED: rstbasic [12589 Existing, 86961 New Construction]; the phases
  carry no sequence field].
- **Phasing overrides** (`m_arrPhasingOverrides`): four `PhasingOverrides`
  entries keyed by `m_elementOnPhaseStatus` **2/3/4/5** = Existing /
  Demolished / New / Temporary **[VERIFIED byte-exact]**, each an
  `OverrideGraphicSettings` (pen numbers, pen colors, cut fill pattern/
  color, line pattern) + `GMaterialOverrider.m_materialId` (the four
  'Phase - Exist/Demo/New/Temporary' materials). These are the ONLY
  dependencies of the phase set on the registries (materials, one line
  pattern, two fill patterns). Genesis default = the standard pens/colors
  with **material/pattern ids −1** [UNKNOWN whether −1 materials are
  accepted; every corpus file references real materials — the types stream
  supplies them, see §8].
- **Phase filters**: the standard five and their presentation vectors
  [VERIFIED 3/3 identical]:

  | name | default | presentation (7 ints) |
  |---|:--:|---|
  | Show Previous Phase | | 0 0 2 0 0 0 0 |
  | Show Previous + New | | 0 0 2 0 1 0 0 |
  | Show Previous + Demo | | 0 0 2 2 0 0 0 |
  | Show Demo + New | | 0 0 0 2 1 2 0 |
  | Show All | ✓ | 0 0 2 2 1 2 0 |

  Slot semantics (which slot = New / Existing / Demolished / Temporary,
  value = by-category / overridden / not-displayed) are INFERRED. The
  names are Revit product-default terminology present in every document.
- Views bind to phases through two ElementId **parameters** on the view:
  `−1012102` (VIEW_PHASE) and `−1012103` (VIEW_PHASE_FILTER) [VERIFIED].

---

## 4. VIEWS

### 4.1 The three view classes that matter and their constellations — VERIFIED membership

A "view" is never one element. From the deletion parents of the specimens
(the element ids a view's header lists as its own deletion cascade):

| constellation | view class | satellites (each its own element) | evidence |
|---|---|---|---|
| **project view** (mandatory, birth) | `DBViewProject` 0x47c | `Viewer` (0x2d4) + `DBDrawing` (0x463, `m_viewports=[vp]`) + `Viewport` (0x88d) | ids 230/231/233/232, ep 0, 3/3 templates |
| **3D view** | `DBView3d` 0x465 | `Viewer3d` (0x117b) + `ModelClipBox` (0xab9, its section box) + `DBDrawing` + `Viewport` + `ExtentElem` (0x672) + `LightSchemeElement` (0x9f9) + `SunAndShadowSettings` (0x1074) | 1138902's constellation 1138900–1138906 + 1470254 |
| **floor plan** | `DBViewPlan` 0x478 | `Viewer` + fixed `SketchPlane` (0xf5d) + `DBDrawing` + `Viewport` + `ExtentElem` + `SunAndShadowSettings` | 245443's constellation 245444–245451 |

ElemRec ownership: Viewer/Viewer3d/Sun/DBDrawing rows carry
`owner_id = the view`; ModelClipBox `owner_id = Viewer3d`; Viewport
`owner_id = DBDrawing`; ExtentElem/SketchPlane/LightScheme own themselves
but store the view in `m_ownerDBViewId`/`m_ownerViewId` **[VERIFIED from
the ElemTable rows]**.

Also referenced by every view (edges, not satellites): its `DBViewType`
(§4.5), a phase + phase filter (parameters), two `GStyleElem` of the
object-styles registry (`RetouchTable.m_invisibleGStyleId` /
`m_notSilhouetteGStyleId`, ancestral ids 201/55150), and in the samples an
`RvtLinkSymbol` (the linked-file override map — sample-specific).

### 4.2 The shared `DBView` base (class 0x72) — VERIFIED (461 common leaves)

Diffing DBViewProject / DBView3d / DBViewPlan across three templates: **461
of 474 leaf values are identical** — the base is a product-default constant.
The 38 leaves that differ are exactly the VIEW DEFINITION:

| definition field | meaning | project view | 3D view | plan |
|---|---|---|---|---|
| `m_viewName` | name | `'???'` | user | user (= level name) |
| `m_dbViewTypeId` | the DBViewType (view family type) | **−1** | 3D-family type | plan-family type |
| `m_viewerId` / `m_dbDrawingId` | the satellites | 231 / 233 | own | own |
| `m_extentElemId` | ExtentElem | −1 | own | own |
| `m_fixedSketchPlaneId` | the plan's work plane | −1 | −1 | own SketchPlane |
| `m_genElemId` | **the generating element = the Level for a plan** | −1 | −1 | the Level id |
| `m_origin` | eye point (3D) / plan origin at cut-plane z | (0,0,0) | eye | (0,0,cutZ) |
| `m_viewDir` / `m_horzDir` / `m_vertDir` | camera frame (viewDir points model→eye) | (0,−1,0) front / X / Z | camera | (0,0,1) up / X / Y |
| `m_scale` | drawing scale as a fraction (0.01 = 1:100) [INFERRED unit] | 0.01 | 5.25… (arbitrary in 3D) | 0.01 |
| `m_backClipping` | | −1 | −1 | 0 |
| `m_lightSchemeId` | LightSchemeElement | −1 | own | −1 |
| `m_viewTemplateId` | applied view template | −1 | −1 (sample: a plan template) | −1 |
| `m_pParamValueSetElementId` | phase filter (−1012103) / phase (−1012102) | ids | ids | ids |
| `m_pParamValueSetInt` | plan only: detail level (−1011002) / discipline (−1005163) | [] | [] | 3 / 2 |
| `m_pViewDisplayMgr.m_lights.m_sunAndShadowSettingsId` | the view's sun element | **54520** (document sun) | own | own |
| `m_oaDrawFilters[0].m_categoryIds` | default-hidden categories (per view kind) | 6–7 ids | ~48 ids (analytical/annotation) | 13 ids |

Everything else — AdHocOverrides, FilterOverrides, GraphicOverrides,
HiddenElements, ColorFillSchemeSetting, DrawOrderMgr, HideElementsMgr,
RetouchTable, RvtLinkOverrides (empty maps), PointCloudOverrides,
WorksetVisibilityViewSettings, the **ViewDisplayMgr** (background/fog/
lights/model/render/exposure blocks with the stock 'SunAndSky-002'
environment + 'Generic' quality/exposure assets from
`assetlibrary_base.fbx`) — are stock display settings, identical
everywhere **[VERIFIED constants; product defaults, not authored content]**.

### 4.3 VIEW DEFINITION vs GENERATED CONTENT — the separation

- **Definition (we author):** the table above + the satellites' small
  parameter sets (Viewer bound box / crop, plan view range, sun position).
- **Generated (we do NOT emit):** the `Viewer3d` seq-103 rep in the corpus
  is a real `GElement` — the *camera symbol* geometry (a GFilter/GGroup
  tree of GLines drawn in plan) **[VERIFIED it is drawn geometry]**;
  genesis emits `SerializedDummy` for it. Every DBView*/DBDrawing/Viewport/
  Extent/Sketch/Sun seq-103 rep is already `SerializedDummy` in the corpus
  **[VERIFIED]** — views cache no graphics in the file; the drawn view
  content is regenerated from the model. The only true GElement reps in
  the skeleton are Viewer3d's camera symbol (dropped) and the BasePoints'
  point markers (emitted, §6).

### 4.4 The floor-plan machinery (DBViewPlan-specific) — VERIFIED structure

`m_genElemId` = the Level ⇒ "Level 1's plan". View range = `PlanViewRange`
(5 offsets/levelPos, zeros) + `PlanViewRange2` {`m_viewDepthPlaneOffsets`
[top, cut, bottom, view-depth, 0], `m_viewDepthPlaneLevelIds` [level,
level, level, level-below, −1]} + the mirrored scalars
`m_cutPlaneElev` / `m_topClipElev` / `m_bottomClipElev` /
`m_levelBelowElev` + two `GenericPlaneCutter` planes (cut plane at
cut-elev + 3.28 ft, view-depth plane, empty envelope ((1,1),(0,0)), archive
pids 3/4) + a `MakeCutterForPlanRegionsGStep` geom step + the fixed
SketchPlane on the level datum at the level elevation (`m_datumPlaneId`
= the view). Sample values: cut 1200 mm, top 2300 mm, view depth at the
level below −1200 mm/−1800 mm (metric templates).

### 4.5 `DBViewType` = the view FAMILY TYPE — VERIFIED byte-exact

A `Symbol` with `m_systemFamilyIdx` selecting the built-in view family
**[VERIFIED identical 3/3 templates]**:

| idx | family | plan dir | | idx | family |
|--:|---|--:|---|--:|---|
| 102 | 3D View | −1 | | 112 | Building/Wall Section |
| 103 | Walkthrough | −1 | | 113 | Detail (callout) |
| 104 | Rendering | −1 | | 114 | Building Elevation |
| 105 | Schedule | −1 | | 115 | Loads Report |
| 106 | Cost Report | −1 | | 116 | Pressure Loss Report |
| 107 | Sheet | −1 | | 117 | Legend |
| 108 | Drafting View / Detail | −1 | | 118 | Panel Schedule (Report) |
| **109** | **Floor Plan** | **0** | | 119 | Graphical Column Schedule |
| 111 | Ceiling Plan | 1 | | **120** | **Structural Plan (0)** |
| | | | | 121 | Analysis Report |

Other fields: `m_refLabelStr` 'Sim', `m_pocheMatId` (poche material,
registry), `m_defaultTemplateId`, `m_planViewDirection` (0 down / 1 up /
−1), `m_defaultTemplateIdAssignOnViewCreation` True. **These are the
system-family TYPES of views** (P0 gate class) — regenerable from this
table; the templates carry ~91 (one or more per family plus discipline
variants).

### 4.6 Can a project have ZERO views? — UNKNOWN (ranked #1)

Evidence in tension:

- The project view (`DBViewProject`) is present at birth in every lineage
  and the v2 reduction ladder deliberately never deletes it (it is treated
  as document infrastructure) **[VERIFIED presence]**.
- No reduction that removed ALL views has been viewer-tested: the v1 R2
  stage (zero views incl. the project view survived) and the v2 R6+ stages
  (which keep the `{3D}` view and the 'Level 1' plan by design) await the
  Autodesk viewer; the deepest PASS on record is **R4s** (798 deletions, all
  views intact) [`experiments/genesis/provenance/`].
- The Autodesk *Viewer* itself needs at least one view to render (a file
  with no 3D/plan may 'translate' yet show nothing) — a viewer PASS is not
  the same as 'Revit opens it'.

Working position [INFERRED]: **project view = mandatory; user views (plan /
3D) = optional for validity but required for the Viewer proof to be
meaningful.** The genesis composer therefore always emits the project view
+ one 3D view + one plan per level.

---

## 5. PROJECT INFORMATION and the "project" identity — VERIFIED byte-exact

`ProjectInfo` (class 0xd13, category −2003101 OST_ProjectInformation) is a
bare element with ONE `ParamValueSetAString` holding the ten built-in
project parameters — the fields **we set from the job spec**:

| BuiltInParameter | id | rstbasic value |
|---|--:|---|
| PROJECT_NAME | −1006317 | 'Sample House' |
| PROJECT_NUMBER | −1006316 | '001-00' |
| PROJECT_ADDRESS | −1006318 | 'Enter address here' |
| CLIENT_NAME | −1006319 | 'Autodesk' |
| PROJECT_STATUS | −1006320 | 'Project Status' |
| PROJECT_ISSUE_DATE | −1006321 | 'Issue Date' |
| ORGANIZATION_NAME / _DESCRIPTION | −1019005 / −1019006 | '' |
| BUILDING_NAME / AUTHOR | −1019007 / −1019008 | '' |

(Parameter names INFERRED from Revit's public BuiltInParameter enum; the
ids and value slots are VERIFIED.) The file-level identity (who authored
it) is a separate stream — `BasicFileInfo`, §7 — governed by the writer's
identity policy (`rvt.identity`, gate G2).

**There is no `ProjectPosition` element.** The "project position" is a
`GeoLocation` (§6) — an *instance* of a `GeoSite` symbol; the API's
ProjectPosition/ProjectLocation are views onto GeoLocation/BasePoint.

---

## 6. SITE & COORDINATES — VERIFIED structure (constructors provided)

| element | class | role | notes |
|---|---|---|---|
| `BasePoint` ×2 | 0x23e | Project Base Point (cat −2001272, `m_locationType 1`) + Survey Point (cat −2001271, `locationType 0`) | seq-103 rep = a real **GElement** point marker (GPoint + 24×24 GBitmap glyph type 79) — emitted; `m_isClippedToShared` |
| `GeoSite` ×2 | 0x8e1 | site symbol: latitude/longitude (radians), time zone, weather design-day arrays (K), `m_sharedCoordGUID` | 'Internal' + 'Project' pair in every template; weather = stock climate defaults |
| `GeoLocation` ×2 | 0x8e0 | Instance of a GeoSite: `InstanceInfo{Trf}` = the model's position/rotation on the site | 'Internal' / 'Project' named positions |
| `TrueNorth` | 0x1108 | `m_angle` (rad) project→true north; `m_siteCutMaterialId` (registry) | poche depth −3 m |
| `ActiveGeoLocationTrackingElement`, `CoordinateSystemDisplayElem` | 0x89 / 0x3d0 | singleton trackers | not constructed (referenced by BasePoint regen edges); [INFERRED droppable — R4 keeps them, untested without] |

---

## 7. THE MINIMAL `Global/*` TABLE STREAMS (one save = episode 0) — models VERIFIED byte-exact by codec round-trip; content INFERRED

`minimal_globals(elements)` builds the six coordinated models; the
cross-stream save invariants of KNOWLEDGE.md hold **by construction**:

| stream | minimal content | evidence |
|---|---|---|
| **`Global/ElemTable`** (class 0x5c9, prefix u64 0) | u32 N + N × 40-B ElemRec sorted by id, all `creation_ep = modified_ep = user_modified_ep = 0`; owner_id = the owning view for satellites else 0xFF…F; footer {marker 0xFFFFFFFF, class 0x96a, watermark = max id} | layout VERIFIED (codec) |
| **`Global/History`** (0x538, prefix 1) | header GUID slots (D,D,D,0,D) — D = a document-lineage GUID, NOT an episode [VERIFIED 6/6 ≠ any entry]; `format_versions` = **[2662]** (a document born as 2026 has no upgrade lineage) [INFERRED — corpus lists ~185 versions inherited from the 2001 ancestor]; `entries` newest-first = [(E0, 0x28)]; hdr_count 1 | E0 == BFI GUID VERIFIED 6/6 |
| **`Global/DocumentIncrementTable`** (0x53c, prefix 1) | ONE record: pairs [(−1, N_elements)], `elem_id_repeat` = N, `id_pair (0, 1)`, sequence 1, username, timestamp, flag 1, 10 `counters` + `counter_g`; table copy 2 identical | id_pair == (count−1, count) VERIFIED 6/6; **counter semantics UNKNOWN** (all-1 chosen) |
| **`Global/PartitionTable`** (workset table, 0xc80, prefix 0) | ONE kind-0 entry 'Workset1', `guid` = the workset-table GUID W (== Contents.creation_guid), `id_b` = oldest DIT episode = **0**, `id_a` = 0 [UNKNOWN semantics: 352/254/131 in corpus] | 6/6 (non-worksharing files still carry it) |
| **`Contents`** (0x53e, 24-B prologue + gzip, not paged) | `creation_guid` = W; 9 counters = DIT counters minus index 7; `counter_g` = DIT G; build string; hdr5 (7,0,3,−1,3); trailing pairs (−1,1420)/(−1,1426) [INFERRED: A3PartyAImage/A3PartyObject class ids] | counters/G/GUID relations VERIFIED 6/6 |
| **`BasicFileInfo`** (raw) | structure v14, worksharing 0, format '2026' + build '20250227_1515(x64)' (version marker kept, counsel C1), OUR author/client strings, fresh document GUID = E0, increments '1', central_version_number 1, locale ENU, mirror text regenerated | invariants VERIFIED 6/6; author strings proven non-gating (V31 PASS) |
| **`Global/ContentDocuments`** (prefix 1) | empty form = 14 bytes `a3 03 00 00 00 00 ff ff ff ff 00 00 00 00` (u16 0x3a3 + u32 0 + u32 0xFFFFFFFF + u32 0) | VERIFIED in the 2026 `.rfa` (82 raw bytes); zero content documents in a PROJECT UNKNOWN (R9b/R10b probe it) |
| `Formats/Latest` | the per-release schema constant (496,597 B) | format constant, copied |
| `Global/Latest` (ADocument) | **not in this stream's territory** — the serialized document object holding the level table, phase table, default type ids, view lists and the element-id arrays that made deep reduction hard | genesis.md §4.4 |
| `Partitions/<N>` (unit 0) | the three record streams of exactly these elements + the 44-B header + end record; N = increment − 1 = **0** [INFERRED: a one-save document's partition is `Partitions/0`] | header count == ElemTable count |

Worked example (the demo's 42-element skeleton): ElemTable 1,710 B (6 +
42×40 + 24), History 135 B, DIT 204 B, PartitionTable 87 B, Contents
240 B, ContentsPrologue 24 B, BasicFileInfo 1,845 B, ContentDocuments 14 B
— all encode → decode → encode stable [VERIFIED, tests].

---

## 8. GLOBAL REGISTRIES — mandatory vs droppable (host document counts, rstbasic)

| registry | class | count | mandatory? | owner |
|---|---|--:|---|---|
| categories / object styles | CategoryElem / GStyleElem | 616 / 2183 | **mandatory** — the category system is product-defined; ~15 CategoryElem + ~190 GStyleElem exist even at birth; every header names a category and views/retouch tables name styles | types stream |
| line patterns / fill patterns | LinePatternElem / FillPatternElem | 150 / 116 | **mandatory core** (13 + 22 at birth); phasing overrides + object styles reference them | types stream |
| materials + appearance assets | MaterialElem / AppearanceAssetElem | 93 / 131 | **mandatory core** (13–18 materials at birth: the four Phase materials + default/poche); AllProjectPhases and DBViewType (poche) reference materials | types stream |
| fonts | FontElem | ~180 | **mandatory core** (6–8 at birth); text/dimension/level types reference a font | types stream |
| pen table | PenWidthTableElem (**id 2**) | 1 | **mandatory** (birth) | types stream |
| units | UnitsElem | 1 | **mandatory** — every level lists it as a regen parent; 136 spec→FormatOptions entries keyed by open Forge unit ids | **this stream** (`new_units_elem`, byte-exact) |
| view family types | DBViewType | 91 | **mandatory subset** — one per view family used (v2 ladder keeps all 91 as infrastructure) | this stream (`new_view_type`, §4.5) |
| phase set + filters | AllProjectPhases / PhaseFilterElem | 1 / 5–7 | **mandatory** (birth) | this stream (§3) |
| annotation type defaults | TextNoteAttributes, DimensionStyle, LeaderStyle, TagNoteAttributes, ViewportAttributes, LevelAttributes, GridAttributes, … | 1–60 each | **mandatory core** at birth (one default each) — ADocument holds 'default type' ids | types stream |
| system-family types | BasicWallType (id 397 at birth), Floor/Roof/Ceiling/MEP curve types | 1+ | at least the birth wall type exists; ADocument default type ids | types stream |
| project browser organisation | BrowserOrganization | 11 | INFERRED droppable-to-defaults (the project view's regen edges point at 2 of them; a 'no template' project has the two default organisations) | UNKNOWN |
| worksharing / workset visibility | WorksharingViewModeSettings ×2, WorksetVisibilitySettingsElem | 3 | INFERRED mandatory (R4 keeps them; view retouch/regen edges) | UNKNOWN |
| design options | DesignOptionSet / DesignOption | 1 / 3 | INFERRED droppable (a new project has none; R4 kept them only because KEEP_ALWAYS pinned them) | UNKNOWN |
| revisions | AllProjectRevisions / ProjectRevision | 1 / 1 | INFERRED mandatory singleton pair (one initial revision) | UNKNOWN |
| keynotes / load classifications / property sets / parameter defs | KeynoteTable, ParamElemExternal (466), ParamBinding (209), PropertySetElement, HVAC/electrical settings singletons (~120 'UniqueElement' trackers) | many | **droppable to empty tables** — R10 GC-swept parameter definitions to those still referenced; the settings SINGLETONS (ElectricalSetting, StructSettingsElem, Rbs*SettingsElem, AutoJoinTracker, HubsTracker, …) are INFERRED mandatory (ADocument references them) | mixed / UNKNOWN |
| sun (document-wide) | SunAndShadowSettings (id 54520) | 1 | **mandatory** — the project view's ViewDisplayMgr points at it | this stream (`new_document_sun_settings`) |
| print / export settings | PrintSetup, PrintSettings, Dwg/STEP export settings | few | INFERRED droppable | UNKNOWN |

The rule of thumb (INFERRED, consistent with the birth census and the
ladders): **a registry is mandatory iff something surviving references its
elements or ADocument holds a default id into it.** The genesis composer
must therefore be given (by the types stream) at minimum: the category
table + styles, the four phase materials + one line and two fill
patterns (or accept −1), one font, the pen table, and one wall type.

---

## 9. Couplings to `Global/Latest` (ADocument) — for the assembler

The skeleton elements are ALSO indexed by the serialized ADocument
(genesis.md §4.4, E3): its ~19 members hold the phase table, the level
table, view-related tables, the default-type ids per category and (in
model files) element-id arrays (e.g. rstbasic's 490-id analytical set).
Consequences for the assembler:

1. Every ADocument-referenced skeleton id (levels, phases, filters,
   DBViewTypes, the project view, styles/categories) must exist —
   otherwise the ids dangle inside `Global/Latest` (the R1/v2 probes).
2. `m_docAccess.m_pDoc` (weakref 1) in every element and `m_pADoc`
   (weakref 1) in views/drawings both point at archive object **1 = the
   ADocument**; pid **2** = the element itself; owned sub-objects
   registered by the reader continue from 3 in token order (Face 3, Plane
   4, deferred Plane 5 in a Level; GPoint 3 / GBitmap 4 in a BasePoint
   rep; the two cutter Planes 3/4 in a plan) **[VERIFIED: reproduced
   byte-exact by construction]**. The skeleton constructors emit exactly
   these pids.

---

## 10. The constructor catalog (`rvt.genesis.skeleton`)

Shape contract (shared with the types stream's `TypeRecord` and
`mutate.NewElement`): each constructor returns `SkelElement`
{`elem_id`, `class_name`, `class_id` (schema lookup), `category_id`,
`obj` (seq-102 dict), `header` (seq-101 dict), `rep` (seq-103 dict or
None ⇒ SerializedDummy), `owner_id`, `refs`, `notes`} with `.records()`
→ `[(101, cid, header), (102, cid, obj), (103, cid, rep)]`,
`.elemrec_row(episode)`, `.as_type_record()`, `.as_new_element()`,
`.roundtrip()`. View constellations return a `ViewSpec` {view,
satellites}. Ids come from `IdSource` (`.next()`/`.next_id()`) or explicit.

| constructor | emits |
|---|---|
| `new_level(id, name, elevation_ft, level_type_id, …)` | Level |
| `new_level_type(id, name, …)` | LevelAttributes |
| `new_phase(id, name)`, `new_all_project_phases(id, phase_ids)`, `default_phasing_overrides(...)` | ProjectPhase, AllProjectPhases |
| `new_phase_filter(...)`, `default_phase_filters(ids)`, `DEFAULT_PHASE_FILTERS` | PhaseFilterElem ×5 |
| `new_project_info(id, project_name=…, project_number=…, address=…, …)` | ProjectInfo |
| `new_view_type(id, name, family)` (`VIEW_FAMILY` table) | DBViewType |
| `new_project_view(ids, phase_id=, phase_filter_id=, sun_settings_id=, …)` | DBViewProject + Viewer + DBDrawing + Viewport |
| `new_3d_view(ids, name, view_type_id, eye_ft=, target_ft=, …)` | DBView3d + Viewer3d + ModelClipBox + Sun + Viewport + DBDrawing + LightScheme + ExtentElem |
| `new_plan_view(ids, name, level_id, level_elevation_ft, view_type_id, …)` | DBViewPlan + Viewer + SketchPlane + Sun + Viewport + DBDrawing + ExtentElem |
| `new_viewer / new_viewer3d / new_model_clip_box / new_dbdrawing / new_viewport / new_extent_elem / new_sketch_plane / new_sun_and_shadow_settings / new_light_scheme / new_document_sun_settings` | the satellites individually |
| `new_units_elem(id, formats)`, `format_options(...)`, `DEFAULT_UNIT_FORMATS` | UnitsElem |
| `new_true_north / new_base_point / new_geo_site / new_geo_location` | site skeleton |
| `minimal_globals(elements, …)` + `encode_minimal_globals(models)`; `minimal_history / minimal_increment_table / minimal_partition_table / minimal_contents / minimal_basic_file_info / minimal_elemtable / minimal_content_documents` | the six table streams (+ empty ContentDocuments) |
| `build_minimal_skeleton(...)` | the whole composed demo skeleton (units, level type, 2 levels, 2 phases + set + 5 filters, project info, document sun, project view, one 3D view, one plan per level) |
| `roundtrip_report(elements)` | schema-validity + reversibility proof |

`python -m rvt.genesis.skeleton` builds the 42-element skeleton, reports
126/126 records round-tripping, and prints the six stream sizes.

---

## 11. RANKED UNKNOWNS — what only a Revit-open test can settle

1. **Zero user views** — is a project with ONLY the project view (no plan,
   no 3D) opened by Revit? Probe: a v2-style reduction that deletes every
   DBView3d/DBViewPlan/section/sheet but keeps DBViewProject 230 (v1 R2
   deleted 230 too — retest with 230 pinned). Cheap; decides §4.6.
2. **DocumentIncrementTable counters / counter_g semantics** — a genesis
   file writes ten 1s and G = 1 with sequence 1 / id_pair (0,1). If Revit
   rejects it, the fallback is to mimic a template's magnitudes. Probe: a
   V-track file whose DIT counters are rewritten to all-1 (everything else
   original). Cheapest test on the list.
3. **`AllProjectPhases` with material/pattern ids −1** in its phasing
   overrides (every corpus file references the four Phase materials). If
   rejected, the types stream must always ship the four phase materials.
   Probe: edit a template's AllProjectPhases materials to −1.
4. **Viewer3d camera rep as SerializedDummy** — the corpus rep is a
   generated camera-symbol GElement. Probe: replace one Viewer3d rep with
   SerializedDummy in a template (analogous to the accepted V22 wall).
5. **The History format-version list = [2662] only** (vs the inherited
   ~185-entry lineage). Probe: truncate a template's History versions to
   [2662].
6. **PartitionTable `id_a`/`id_b` and Contents `hdr5` slot 2** (10 vs 3)
   semantics; `Contents.trailing_pairs` (1420/1426) as class ids of the
   preview entries. Probe: zero them in a template.
7. **Level type with `m_familyTagId = −1`** (no level-head symbol) and
   levels whose `regenOnly` omits the UnitsElem/GeoLocation edges. Low
   risk (cosmetic head; regen edges are advisory in the accepted V-track
   commits, cf. genesis E2 'C counter advisory').
8. **A project with zero `Global/ContentDocuments` entries** (the 14-byte
   empty form proven only for a family document) — R9b/R10b are the
   probes already on disk.
9. **The `Partitions/<N>` name for a one-save document** (N = 0) and
   whether the reader minds a single save unit with no embedded units.
10. **Element ids below 4,096 vs one contiguous genesis range** — the
    corpus keeps infrastructure below 4,096 and content above 1M; whether
    any reader logic keys off the id magnitude is UNKNOWN (assumed not).
11. **Header flag bits** (`m_abFlags4Bytes` 0x800 'birth' bit vs 10, and
    `m_nVisibleViewFlags`) — both variants translate in the corpus; exact
    semantics UNKNOWN, values copied per class.
12. **Whether `WorksharingViewModeSettings`, `AllProjectRevisions`,
    `KeynoteTable`, `BrowserOrganization` and the ~120 settings singletons
    are truly droppable** — decided only by an ADocument-consistent genesis
    file (blocked on the ADocument encoder), not by reduction of a sample.

Sample-specific edges the minimal constructors legitimately omit (for the
record, all header/parents only): DBViewProject's linked-file
`RvtLinkOverrides.m_displaySettingsMap` entry and its browser-organisation
/ energy-settings `m_regenOnly` edges; the phase filters' regen edges to
the phase set / a pattern / a material; the level type's regen edge to
parameter −1007109 and tracker 113109; BasePoint's non-deterministic regen
children (its GeoLocation pair).

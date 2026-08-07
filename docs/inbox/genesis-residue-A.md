# genesis-residue-A — RESIDUE CONSTRUCTORS, GROUP A (the datum / annotation / type-layer buckets) — workstream record

Charter: take the Yn residue census of the certified Y9 (2,009 K4-inherited
elements in 11 named buckets, `experiments/genesis/subst_k4/Yn.json`) and,
for the buckets of the datum / annotation / text / dimension / arrowhead /
fill-line-pattern / material / definition / curtain / subcategory family,
(1) census each claimed class over the six samples + K4, (2) author OUR
constructor in `src/rvt/genesis/residue_a.py`, (3) emit an IN-PLACE rung
from Y9 per bucket (the `tools/genesis_substitute_v3.py` mechanism:
`rvt.regadd.substitute_elements`, seq-102 object only, validator 0 errors +
registry parity + byte-delta-vs-Y9 assertion) plus the cumulative ZA_deep.

**Territory touched ONLY:** `src/rvt/genesis/residue_a.py` (new),
`tests/test_residue_a.py` (new, 28 pass), `experiments/genesis/subst_k4/
residue_a/*` (6 `.rvt` + reports + `probes.json` + censuses + the frozen
appearance-asset profile + this stream's mined invariants), this record.
No existing `src/rvt/*.py`, tool, test or `.rvt` was edited; the v3
ladder's certification helpers, `rvt.regadd` / `rvt.regdiff` / `rvt.mutate`
/ `rvt.objlint` / `rvt.genesis.*`, `genesis_substitute` / `genesis_triage`
are IMPORTED.  No browser / viewer use: the six files + `probes.json` are
left for the orchestrator's queue.

## CLAIMED BUCKETS / CLASSES (first commit — the Group A / Group B split)

**Split rule: Group A takes the residue CLASSES whose names sort A..L, Group
B takes M..Z**, inside the families each charter names.  This section was
committed BEFORE construction began (it is pinned by
`tests/test_residue_a.py::test_claimed_classes_sort_A_to_L` /
`test_group_b_classes_sort_M_to_Z`).

| rung | Yn bucket(s) | classes claimed (all A..L) | residue elems | in-place slots |
|---|---|---|--:|--:|
| `Z_subcat`  | gap-X6b, gap-X6b+family-scoped | `CategoryElem`, `GStyleElem` (project rows) | 209 + 286 | 169 + 246 |
| `Z_annot`   | no-constructor (annotation types + fonts) | `DimensionStyle`, `LeaderStyle`, `GridAttributes`, `InteriorElevAttributes`, `CalloutTag`, `FontElem` (project) + `LinearDimString` (content, left) | 12 + 5 + 1 + 9 + 9 + 35 + 1 | 4 + 5 + 1 + 1 + 1 + 11 |
| `Z_datum`   | content-removal-candidate, surplus | `Grid`, `Level` (7 plan-less surplus) + `CurveElem` / `LegendComponent` / `LevelRoomPlan` (content, left) | 3 + 7 (+ 10 content) | 3 + 7 |
| `Z_pattern` | surplus-sample-instances | `FillPatternElem`, `LinePatternElem` (beyond our palette) | 4 + 3 | 7 |
| `Z_asset`   | material-companions | `AppearanceAssetElem` | 18 | 18 |
| (census + honest statement, no in-place rung) | curtain-systems(no-constructor) | `DBViewType` (72, all family-scoped), `Family` (8), `FamilySurrogate` (8) + every m_famId-scoped copy of the classes above (128) | 88 (+128) | — |
| `ZA_deep`   | (cumulative) | Y9 + Z_subcat + Z_annot + Z_datum + Z_pattern + Z_asset | — | 473 |

**Left to GROUP B (M..Z counterparts, per their committed claim
`docs/inbox/genesis-residue-B.md` — per CLASS, 29 classes / 997 elements):**
`MaterialElem` (surplus 10), `PenWidthTableElem` (8 family-scoped),
`SlaveSymbolTrackerElem` (1), `SectionAttributes` (10), `ViewportAttributes`
(1), `SketchPlane` (30), `RefPlane` (21), `RoomElem` (1) + the whole ROOM
CONTENT constellation (the 5 boundary `CurveElem`s + `LevelRoomPlan` 1004909
+ `AreaSchemePlanTopologies` 9744 belong to `RoomElem` 1004910 — hand it to B
whole, see §Findings 9), the surplus companions `SunAnnotationElem` /
`Viewer` / `Viewport` / `WorksharingViewModeSettings` / `PrintSettings`, the
whole DEFINITIONS bucket (`ParamElemExternal` 466, `ParamBinding` 209,
`ParamElemElectricalLoadClassification` 108, `ParamElemProject` 8),
`ParameterFilterElement`, `NumberingSchema`, `PropertySetElement`, the piping
catalog M..Z classes, and the external-link pair (`RvtLinkSymbol` /
`RvtLinkInstance`).  The two claims are DISJOINT and jointly cover all 73
residue classes (verified against Y9).

**The other A..L residue classes (ours by the split rule but outside this
round's named families) — DISPOSITIONED, not silently orphaned; 373 elements
after ZA_deep, `residue_after_ZA_deep.json`:**

| class(es) | elems | honest disposition | owning rung |
|---|--:|---|---|
| `HVACLoadSpaceTypeElem` / `HVACLoadBuildingTypeElem` / `HVACLoadScheduleElem` / `BuildingOperatingYearSchedule` | 212 | Autodesk's shipped HVAC / energy space-type DATABASE (product data): counsel-or-removal, not authorable | product-data rung (singletons stream's rank-1 queue) or removal |
| `ElectricalDemandFactorDefinition` / `ElectricalLoadClassification` | 39 | the electrical load / demand-factor CATALOG — our types-stream constructors EXIST (T_conduit_types certified) | catalog rung (types stream) |
| `ConduitStandardType` / `ConduitSizesElem` / `CableTraySizesElem` | 7 | MEP catalogs, constructors exist (Y4 landed the settings side) | catalog rung (types stream) |
| `BasicWallType` (1) / `FloorAttributes` (1) / `FabricSheetType` (1) / `FabricWireType` (1) | 4 | residue system-family TYPES: our wall / floor type constructors exist (`types.new_wall_type` / `new_floor_type`); rebar fabric types have none | system-types rung (types stream) |
| `AreaReportSettingsElem` (1) / `AreaSchemePlanTopologies` (6) / `AreaTypeElem` (8) / `AssemblyCodeTable` (1) / `ColorFillSchema` (10) / `LoadCaseElem` (8) / `LoadNatureElem` (8) / `DataStorage` (1) | 43 | misc analysis / area-scheme / structural-analysis / UniFormat / extensible-storage machinery — no our-constructor yet (small definitional constructors for load cases / area types are feasible; the UniFormat table and the ES entity blob are counsel / removal) | analysis-settings rung (a Z_analysis follow-up of this stream) or removal |
| `BrowserOrganization` (5) / `DBDrawing` (1) / `DBViewDrafting` (1) | 7 | surplus browser schemes + the one drafting view and its drawing: companions of layers earlier rungs own (Y2 / Y9) — surplus-removal | rebase stream / removal |

## Result in one screen

**All five Group-A residue rungs + the cumulative ZA_deep are BUILT and
VALID from the certified Y9, by pure in-place substitution of OUR
constructors' objects: 6 files, every one validator-VALID (0 errors),
structurally proven, four-registry coherent, `Global/Latest` + `Global/
ElemTable` BYTE-IDENTICAL to Y9, no element added or removed, registry
parity 100 % by construction (asserted), rvt.regdiff registration sample
identical (6/6 per rung), byte-delta assertion holding (ONLY the landed
slots' seq-102 object records change), zero dangling references in our
objects, and a per-class FIELD-DELTA table naming exactly which object
fields carry OUR value.**  Reproduce (~11 s):
`.venv/bin/python -m rvt.genesis.residue_a`.

Base: `experiments/genesis/subst_k4/Y9.rvt` — CERTIFIED (viewer PASS,
`docs/coverage/viewer-certified.json`: "THE DEEPEST RUNG LOADS").  Control:
`experiments/genesis/subst_k4/CTRL_K4_base.rvt` (md5-identical to the
certified K4; upload with EVERY batch).  Independent arbiter (this session):
`tools/rvt_validate.py --quiet residue_a/*.rvt Y9.rvt CTRL_K4_base.rvt` → 8 ×
`OK errors=0 warnings=1` (the warning = the pre-existing Extensible-Storage
gap on 1 DataStorage element, untouched).

| # | rung | class layer substituted IN PLACE | slots | changed | unchanged | left (reason) | verdict |
|--:|---|---|--:|--:|--:|--:|---|
| 1 | **ZA_deep** | all Group-A layers together (bisection-first) | 473 | 431 | 42 | 139 | VALID |
| 2 | **Z_subcat** | the project SUB-CATEGORY layer (169 CategoryElem + 246 GStyle rows) → our vocabulary + our discipline pens / colours | 415 | 374 | 41 | 80 (curtain-scoped) | VALID |
| 3 | **Z_annot** | 4 secret internal dim styles + 5 arrowheads + grid head + elevation marker + callout head + 11 project fonts → ours | 23 | 22 | 1 | 49 (curtain-scoped + 1 constraint dim) | VALID |
| 4 | **Z_datum** | 3 grids → our '01'/'02'/'03' bay + 7 surplus levels → our datum vocabulary | 10 | 10 | 0 | 10 (room / legend content) | VALID |
| 5 | **Z_pattern** | 4 fill + 3 line surplus patterns → our extra house patterns | 7 | 7 | 0 | 0 | VALID |
| 6 | **Z_asset** | 18 material appearance assets → our generic appearance palette | 18 | 18 | 0 | 0 | VALID |

Upload order (`probes.json:upload_order_bisection_first`): **ZA_deep, then
Z_subcat, Z_annot, Z_datum, Z_pattern, Z_asset**, with `CTRL_K4_base.rvt` in
EVERY batch (a failing control voids the round).  ZA_deep PASS retires every
Group-A residue class this stream can retire; a ZA_deep FAIL is read through
the five singles (each derives DIRECTLY from Y9, so the first single FAIL
convicts exactly its class layer).

The residue after ZA_deep (`residue_after_ZA_deep.json`): 1,536 elements =
936 Group B's + 373 unclaimed by either charter + 128 family-scoped
remainders of Group A's classes (curtain constellation) + 99 Group-A
non-in-place (88 curtain + 11 placed content) — every one dispositioned.

## THE method, and why the probes are clean

Every rung is `rvt.regadd.substitute_elements(seqs=(102,), keep_row=True)`
on the certified Y9: our constructor's seq-102 OBJECT replaces Autodesk's
at the SAME element id — same ElemTable row (episodes / owner / vintage
byte-identical), same record position, same registry slots; both global
registry streams byte-identical; nothing added, nothing deleted.  The ONE
variable of a rung is the CONTENT of our objects at Autodesk's own
registrations — the K1-night registration variables are eliminated by
construction, exactly as in the certified Y-ladder.

New in this stream: every rung report carries a **FIELD-DELTA TABLE**
(`field_delta_by_class`): for every landed slot, the dotted paths whose value
differs between Autodesk's object and ours.  It is the sharpest possible
statement of what a probe tests, and it CERTIFIES the constructors' honesty:

* `CategoryElem` (169 slots): differing fields = `{m_pCategory.value.m_name}`
  ONLY (137 rows; the 32 annotation-owned internal rows are byte-identical —
  an internal row's only free value is its name and internal rows are
  nameless: nothing of ours to reject there, said so).
* `GStyleElem` (246 slots): `{m_pGStyle.value.m_color 235, m_pGStyle.value.
  m_penNumber 125}` ONLY.
* `DimensionStyle` (4): the name token + 5 double-param values + snap /
  shoulder distances (+ radius prefix on the diameter style) — everything
  else is the unit-format machinery (overlay constructor, said so).
* `LeaderStyle` (5): name + the two arrowhead params (+ order) + tick shape.
* `GridAttributes` / `InteriorElevAttributes` / `CalloutTag`: name +
  their definitional dimensions only (bubble ends, end length; marker width
  / arrow angle / sub-indices; corner radius).
* `FontElem` (11): size (10) + colour (2) — the face is already Arial = our
  house face; one font (1468019) is byte-identical (its owner's values
  coincide with ours) — landed, unchanged, listed.
* `Grid` (3): the datum-plane geometry + `m_text`; `Level` (7): `m_text`
  (+ the plane geometry of the ONE un-referenced level that took our
  elevation); patterns: name + grids / segments (+ the constructor's known
  cell / geomtable shape deltas the certified palette layer already
  carries); assets: our GenericSchema property tree + our colour.

## Census evidence (the six samples + K4 lineage; `residue_census.json`, this stream's `invariants/`)

* **Sub-categories.** Yn's 209 CategoryElem / 286 GStyleElem residue = 169
  PROJECT CategoryElems (137 named model / annotation sub-categories of
  built-in parents — door / window / furniture / generic-model / detail /
  site / structural / entourage / drafting-Lines sub-categories left by
  removed loadable families and the template — + 32 annotation-TYPE-OWNED
  nameless internal line-style rows, ctype 4, parent OST_TextNoteLineStyle
  -2000059, owners DimensionStyle 12 / SectionAttributes 4 / GridAttributes
  3 / LeaderStyle 5 / InteriorElevAttributes 1 / LevelAttributes 2 (our own
  landed level type) / ViewportAttributes 1 / AreaReportSettingsElem 6) + 246
  project GStyle rows (each keyed on one of those categories; 209 projection
  + 77 cut... 246 project / 40 curtain-scoped), and 40 + 40 curtain-family-
  scoped rows (m_famId = a curtain SYSTEM family).  Per-row STRUCTURAL
  PROFILE (design-option token -4/-1, ctype / flags word 519 vs 7 vs 0, the
  cell apparatus: `SecretStyleMembership` names the owning secret style,
  `PatternHelper` / `CategoryElemGroupHelper` are empty helpers, header flag
  words 67117070 / 8202 / 2074) is a compiled-in per-row property (the catalog
  fixer v2's law) — our constructor takes it from the slot; the field-delta
  proves nothing but the name / pen / colour changed.  Sample values: pens
  {1:222, 5:16, 2:12, 3:11, ...}, colours mostly 0, patterns 279 built-in / 7
  document, materials none — our discipline scheme (catalog.
  classify_category(parent)) is a genuinely different value table.
* **Annotation types are Revit's SECRET INTERNAL machinery + a handful of
  real heads.**  The 12 residue DimensionStyles = 4 PROJECT
  `SecretInternal{LinAng,Rad,TypePreview,Diameter}DimStyle<random-token>`
  (Revit's temporary / preview dimension styles) + 8 curtain-family-scoped
  'Diameter' styles.  Verified 6/6 samples: every 2026 project carries
  EXACTLY these four secret roles once (and the four `SecretInternal…
  Arrowhead` LeaderStyles once); the name tail is a per-file random alnum
  token (grammar constant, value ours); the VALUES differ per template (5
  distinct object hashes across the six samples per role — text sizes /
  accuracies), i.e. they are document SETTINGS → OURS apply.  The residue
  LeaderStyles = the 4 secret arrowheads + 1 real ('MEP - Arrow Filled 15
  Degree' → our 'GEN Arrow Filled 20 Degree', tickType 8).  The other
  project heads: GridAttributes 341 '6.5mm Bubble', InteriorElevAttributes
  357 '12mm Circle', CalloutTag 49508 'Callout Head w 3mm Corner Radius' —
  each with `m_familyTagId` / `m_elevationSymbolId` ALREADY -1 in the K4
  lineage (K3 nulled family usage) and the lineage LOADS ⇒ family-free
  annotation heads are reader-legal; our constructors emit -1 too.  Corpus
  invariants (mined this session, `invariants/`): GridAttributes owns
  {CategoryElem, FontElem} 11/11, `m_bubbleLocInElev` = 2 constant,
  end-segment length ∈ {25 mm, 1800 m}; InteriorElevAttributes
  `m_orderedSubIndices` ∈ {0, 4} entries (empty legal), referenceLabelPos 2
  constant; CalloutTag owns nothing, corner radius ∈ {0, 3 mm, 1/8"}.
* **Fonts.** EVERY FontElem is OWNED (5,982/5,982 corpus fonts,
  `ETR.has_owner` true): the 35 residue fonts = 11 project (owners: the 4
  secret dim styles, the grid type, the elevation marker, our landed level
  type 305 'GEN Level Head - Circle', 2 SectionAttributes, 1
  AreaReportSettingsElem × 2) + 24 curtain-family-scoped.  Corpus font
  colour ENUM = {0, 16711422, 16777215, **16777216**, 255, ...}: 0x1000000 is
  the format's black token (24/30 modal) — our black is encoded with it.
* **Datum content.** The 3 grids (A/B/C, one bay, 3.0 m module, type 341,
  each referenced only by the plan's ExtentElem 1064657) are DatumPlane
  content — the Level twin: same GeomStepList / Face / Plane machinery
  (geomstep flags 761725 / list flags 11 / face flags 524804 vs Level's
  1 / 1) — a `new_grid` constructor now exists (there was NONE: Yn's "the
  skeleton has grids / refplanes" was aspirational — corrected below).  The 7
  surplus levels ('Ceiling', 'Top of Parapet', 'Roof Level', 'Foundation',
  'Level Lower', 'Ref Beam system', 'FOUNDATION-2700') all use OUR landed
  level type 305; 6 of 7 are referenced (SketchPlanes hosted on them, 2 by
  the document suns, 1 by our plan's view range) → they keep the SAMPLE
  elevation and take our datum names (rank-paired: lowest sample datum → our
  lowest name); 'Ceiling' (0 referrers) also takes our elevation.
* **Placed CONTENT (no constructor value, routed):** the 5 CurveElems are
  the ROOM / AREA-SEPARATION boundary loop of the one placed room (RoomElem
  1004910 → Group B) with its LevelRoomPlan 1004909 + AreaSchemePlanTopologies
  9744, on sketch plane 245433 — one coherent room-content constellation
  (removal rung).  The 4 LegendComponents display TYPES (BasicWallType
  600634, FloorAttributes 1201129, curtain surrogates 12610 / 12614) in a
  legend.  The ONE LinearDimString 763420 = a locked EQ CONSTRAINT dimension
  (category OST_Constraints -2000262, style = the secret internal LinAng
  style 277) tying 3 project reference planes (699327 / 699381 / 763366 —
  Group B's) — constraint content: it leaves with the planes.
* **Patterns / assets.** Surplus patterns: fills 442 / 448 / 449 / 6473,
  lines 16 'Dash dot' / 942 'Aligning Line' / 6553 'Center' → our extra
  house patterns (Y7's constructors).  AppearanceAssetElem: the 18 assets are
  MaterialElem render companions (23 material referrers); the Protein
  'GenericSchema' property skeleton (57–59 properties: names / order /
  APropertyXxx types / library GUIDs / UI xml paths / the AO + roundcorner
  machinery, 'materialappearance' asset type, `assetlibrary_base.fbx`
  library, `m_eAssetType` 4) is IDENTICAL over 400 corpus Generic assets ⇒
  a per-release library constant (like the category enum), frozen once in
  `generic_asset_profile.json`; the FREE properties (UIName, generic_diffuse,
  gloss, reflectivity, transparency, tint, description / keyword /
  category, version guid, thumbnail) carry NO frozen value — ours.  (The
  9 non-Generic-schema residue assets (Metal / Hardwood / PlasticVinyl) all
  become OUR Generic-schema assets — the field-delta lists `m_Asset.m_sName`
  for 9.)
* **The curtain constellation = the exact coherent-removal set**
  (`curtain_constellation.json`): the 8 curtain-SYSTEM families
  ('Rectangular / Circular / L / V / Trapezoid / Quad Corner Mullion',
  'System Panel', 'Empty System Panel', category -1, `m_isCurtainPanel` /
  mullion flags) + everything m_famId-scoped to them: 72 family-editor
  DBViewTypes (Floor Plan / Ceiling Plan / Section 1 / Detail View /
  Drafting View / Elevation 1 / 3D View / Schedule / Sheet × 8), 40
  CategoryElems + 40 GStyle rows, 24 fonts, 8 SectionAttributes, 8
  InteriorElevAttributes ('Elevation 1'), 8 CalloutTags ('Callout Tag 1'),
  8 'Diameter' DimensionStyles, 8 family PenWidthTables, 8 FamilySurrogates
  — **232 elements**.  Pure Autodesk compiled-in curtain machinery: nothing
  of ours to express; the honest rung is COHERENT REMOVAL (K4's own certified
  family-removal operation, with FamilyMgr / ContentTable reconciliation) —
  the id set is the removal queue this stream hands over.

## The constructors (`src/rvt/genesis/residue_a.py`)

| constructor | our values (plain data) | mined constants / wiring | shape |
|---|---|---|---|
| `inplace_category(slot, name)` | our SUB-CATEGORY VOCABULARY per parent (Doors / Windows / Furniture / GM / Lines / Detail / Site / Structural / …) + numbered fallback + our 'Annotation Line NN' for orphan internal rows | parent / owner / gstyle wiring, ctype / flags, design-option token, cell apparatus (per-row profile) | pure `new_category` + profile |
| `inplace_gstyle(slot, pen, color)` | our discipline scheme by parent category (catalog.classify_category → pen / colour); annotation-owned rows our annotation ink | category / owner / pattern / material wiring, screen-sized flag, cells, design option | pure `new_gstyle` + profile |
| `font_elem(owner, name, size, color)` | our face (house TEXT_FONT), our paper height per owner class, black (format token 0x1000000) | owner + cells (a font is ALWAYS owned) | pure |
| `arrowhead_type(...)` / `inplace_arrowhead` | our arrowhead (filled 20°, 3 mm; params -1006414 angle / -1006426 size); secret roles keep their role + OUR token | its own internal line CategoryElem + cells | pure |
| `grid_head_type(...)` | 'GEN Grid Head - 8mm Circle': bubbles both ends, continuous, our end-segment length | font + line / leader / centre-segment categories (owned constellation), familyTagId -1, bubbleLocInElev 2 | pure |
| `interior_elevation_type(...)` | 'GEN Elevation Marker - 10mm Circle': circle shape, 10 mm, 45° filled arrows, positions | font + line category, symbol id -1, sub-indices [] (corpus-legal), refLabelPos 2 | pure |
| `callout_head_type(...)` | 'GEN Callout Head - 2mm Radius' | familyTagId -1 | pure |
| `inplace_secret_dimension_style(slot)` | our name token + our annotation values (text 2.5 mm, offsets, witness gaps, tick 2.5 mm, EQ text, R prefix, snap / shoulder, 1 mm / 0.01° accuracies) | the 60-field unit-FormatOptions / param-set machinery of the slot | OVERLAY (said so: `DIMENSION_OUR_FIELDS`) |
| `new_grid(name, p0, p1, ...)` / `our_grid_bay` | our zero-padded numeric names ('01'…), our 8.4 m module / 42 m length / reference elevation | the DatumPlane apparatus (geomstep 761725 / face 524804 / geomtable, family+type param -1) + the GridAttributes type wiring; orientation from the model | pure (product constructor) |
| level surplus (`skeleton.new_level`) | our datum vocabulary names (+ our elevation where un-referenced) | the DatumPlane apparatus + regen params + our landed level type 305 | reuse |
| extra patterns (`types.new_line_pattern` / `new_fill_pattern`) | 'GEN Dash Dot 6mm' / 'Phantom' / 'Border'; 'Brick Coursing 75mm' / 'Steel Section Hatch' / 'Gypsum Stipple' / 'Vertical Lines' | (the certified Y7 palette constructors) | reuse |
| `generic_appearance_asset(name, rgb, gloss, ...)` | our appearance palette (18 entries: concrete / CMU / gypsum / steel / aluminium / glass / wood / …) — colour, gloss, transparency, metalness, texts, our version guid / thumbnail token | the frozen 57–59-property GenericSchema skeleton (`generic_asset_profile.json`), library / UI constants, `m_eAssetType` 4 | pure (product constructor) |

Every constructor's object encodes → decodes → re-encodes BYTE-EXACT
(`--demo`: 9/9; the tests; the per-rung self-check gate).

## New findings (evidence [V] — merge into KNOWLEDGE.md)

1. **The X6b sub-category gap is a NAMES + GRAPHICS layer only** [V, Z_subcat
   field-delta]: with the per-row structural profile taken from the slot, our
   `new_category` / `new_gstyle` output differs from Autodesk's 415 project
   sub-category rows in EXACTLY {category name} / {pen, colour}.  The
   sub-category question is therefore purely a value question (our vocabulary
   + our pens / colours at their registrations) — cleanly probed by Z_subcat.
2. **A 2026 project always carries exactly four SECRET INTERNAL dimension
   styles (LinAng / Rad / TypePreview / Diameter) and four secret
   arrowheads** [V, 6/6 samples], named `SecretInternal<Role><random alnum
   token>` (the token is per-file random — a grammar, not a value) with
   per-template VALUES (5 distinct object hashes per role across the six
   samples): they are document SETTINGS in machinery clothing → our values
   apply, keyed by role; the K4 lineage's residue annotation-type layer IS
   mostly this machinery + one real arrowhead + three real heads.  The
   locked-constraint dimensions (LinearDimString, OST_Constraints) are typed
   BY the secret LinAng style — that is what the machinery is for.
3. **Every FontElem is owned by a type (5,982/5,982) and 0x1000000 is the
   format's black token** [V]: fonts ride with their type constellations
   (secret dim styles, grid / elevation / section / level types, area-report
   settings); our black uses the 24-bit-plus-one token like 24 of 30 corpus
   fonts.
4. **Family-free annotation heads are legal** [V, K4 lineage LOADS]:
   GridAttributes `m_familyTagId`, InteriorElevAttributes
   `m_elevationSymbolId`, CalloutTag `m_familyTagId` are all -1 in the
   certified K3/K4/Y9 lineage (corpus ENUM [null, @FamilySymbol]); our head
   constructors keep -1 — an annotation head is content, not required.
5. **Grid = DatumPlane content (Level's twin); `residue_a.new_grid` is the
   first CONTENT constructor built to the certified in-place discipline** [V
   structure]: same GeomStepList / Face / Plane apparatus as Level (flag
   words 761725 / 11 / 524804 vs Level's 1 / 1), origin = line midpoint at
   the grid's reference elevation, xVec = line direction, yVec = +Z, UV
   envelope = (half-length, elevation range); zero-vector free / bubble ends
   ('compute on regen'); the type is `GridAttributes` via `m_attrId`.  This
   is the constructor the spec → model pipeline needs for grids.  (Yn's
   'the skeleton has grids / refplanes' was FALSE: no such constructor
   existed — corrected.)
6. **The Protein GenericSchema appearance-asset property skeleton is a
   per-release constant** [V, 400/400 corpus Generic assets]: 57–59
   properties, identical names / order / APropertyXxx types; the library id /
   UI xml paths / asset-type token / AO + roundcorner defaults are identical
   in every specimen; only UIName / diffuse / gloss / reflectivity /
   transparency / tint / description / keyword / category / version guid /
   thumbnail vary (ours).  A Generic asset never carries owned children or a
   thumbnail record (`m_pThumbnail` null, `m_materialPathMap` []).  Any
   material's render companion can therefore be OURS on the Generic schema.
7. **Curtain-SYSTEM families are a fixed 8-family constellation of 232
   host elements in the K4 lineage** [V]: 28 typed referrers per family (9
   family-editor view types + 5 sub-category + 5 style rows + 3 fonts + 1
   surrogate + 1 section head + …) — a coherent-removal unit, not a
   substitution target.
8. **Referenced datums must keep their elevation in an in-place probe** [V
   analysis]: 6 of the 7 surplus levels are referenced by their hosted
   SketchPlanes (whose planes carry absolute geometry), 2 by the document
   suns, 1 by our plan's view range — moving them would desync content the
   reader does not re-solve; our datum NAMES are the free value there, our
   ELEVATIONS only on un-referenced datums ('Ceiling' → 'GEN Mezzanine' at
   our 3.3 m).  The same rule will govern reference planes (Group B).
9. **The room content is ONE constellation across both groups' classes**
   [V]: RoomElem 1004910 (B's) + LevelRoomPlan 1004909 (A's) + 5
   room-separation CurveElems (A's, sketch plane 245433) +
   AreaSchemePlanTopologies 9744 — the A..L / M..Z split cuts it; it must be
   removed WHOLE (Group B's room-content rung; A's classes ride along).
10. **`Global/Latest` + `Global/ElemTable` stay byte-identical for a 473-slot
    substitution** [V, ZA_deep]: registry parity is a property of the
    in-place method at this scale too (13 classes, geometry-bearing content
    included), and unit-0 re-blocking re-flows only the seq-102 run.

## Diffs / hooks proposed for files OUTSIDE this territory (NOT applied)

* **`experiments/genesis/subst_k4/Yn.json` (genesis-rebase)** — the
  content-removal-candidate reason "or our datum constructors (skeleton has
  grids / refplanes)" is inaccurate: NO grid / ref-plane constructor existed
  before `residue_a.new_grid`; word it "datum constructors: grids
  (residue_a.new_grid), levels (skeleton.new_level); ref planes = none yet".
* **`tools/genesis_substitute_v3.py`** — its certification helpers
  (`_byte_delta_assertions`, `_parity_report`, `_registration_diff_sample`,
  `certification_of`, `stage_control`) are the de-facto certification API of
  the in-place ladder (this stream imports the underscore names); promote them
  to a shared module (e.g. `rvt/inplace.py` or a public section of the tool)
  so residue streams stop importing private symbols.
* **`src/rvt/genesis/house_standard.py`** — the sub-category vocabulary,
  datum (level) vocabulary, grid convention, extra patterns and appearance
  palette introduced here (`residue_a.SUBCATEGORY_VOCABULARY`,
  `LEVEL_VOCABULARY`, `GRID_CONVENTION`, `EXTRA_*_PATTERNS`,
  `APPEARANCE_PALETTE`) belong in the house standard next to `TEXT_TYPES` /
  `MATERIALS`; kept in `residue_a` only to respect territory.  Also record
  the font black token (0x1000000): `types.new_text_type` writes 0xFFFFFF for
  "no colour" — the corpus modal font colour token is 0x1000000, not white.
* **`src/rvt/genesis/skeleton.py`** — no grid constructor; adopt
  `residue_a.new_grid` (and a `new_grid_type` = `residue_a.grid_head_type`)
  so `build_minimal_skeleton` can be born WITH a grid bay.
* **`src/rvt/regadd.py` / `rvt.regdiff`** — a public `field_delta(a, b)`
  (this stream's) is the natural companion of `stream_diff_report` for
  object-level evidence; and `SubstituteReport` could carry the substituted
  slots' before / after decoded values so every in-place stream gets the
  field-delta table for free.
* **`docs/coverage/viewer-certified.json` (orchestrator)** — add the six
  Z files + control as they read out; every report names its base (Y9) +
  certification + control.
* **KNOWLEDGE.md owner** — merge findings 1–10; strike the "skeleton has
  grids" phrasing wherever it appears.
* **Group B (`genesis-residue-B`, if that is its slug)** — take the room
  constellation WHOLE (RoomElem + LevelRoomPlan + the 5 boundary CurveElems +
  AreaSchemePlanTopologies 9744) and the 3 reference planes + LinearDimString
  763420 constraint as ONE ref-plane content rung; the split rule cut both
  constellations.  `SlaveSymbolTrackerElem` (1) rides with the curtain
  removal.
* **`tools/sync_plugin.py`** — this stream adds one `src/` module
  (`rvt/genesis/residue_a.py`); run the sync so the plugin's bundled source
  copies stay in step (the pre-existing plugin-drift test will otherwise
  flag it).

## Open questions (need the viewer / a decision)

* The six verdicts, in upload order (`residue_a/probes.json`).  Every
  branch of the interpretation is pre-stated per probe (`if_PASS` /
  `if_FAIL`).  ZA_deep PASS retires Group A's residue except the two
  stated removal queues; a single-rung FAIL names the constructor.
* Z_subcat is the first probe of OUR SUB-CATEGORY NAMES at Autodesk's
  registrations (169 name tokens + 246 pen / colour values) — the field-delta
  says nothing else changed, so a FAIL is a name / value grammar finding
  (e.g. an internal ctype-4 row that must stay nameless: the 19 orphan
  'X - element id N' rows we renamed 'GEN Annotation Line NN' are the first
  suspects — a Z_subcat-b with the orphan names left EMPTY is the bisect).
* Whether the reader tolerates our SecretInternal name TOKENS (the grammar
  is right; the token is ours) — Z_annot answers it; if it fails, keeping
  the slot's own token (a required token, added to the token list) is the
  one-line retreat.
* Whether an EMPTY `m_orderedSubIndices` on the elevation marker and our
  25-mm-vs-1800-m end-segment choice on a CONTINUOUS grid type matter —
  both are corpus-legal but minority forms; Z_annot / Z_datum answer them.
* The curtain-constellation removal (232 ids) and the two content removals
  (room loop, legend + constraint dims) are the recorded next rungs — a
  removal engine's job (rvt.reduce + the four-registry reconciliation), on
  the ZA_deep base once it certifies.
* The three container-layer counsel items (identity, the Forge corpus, the
  schema) are untouched by design: an in-place ladder leaves the ADocument
  and every container stream Autodesk's byte for byte.

## Verification

* `.venv/bin/python -m rvt.genesis.residue_a` → 6 × VALID (11 s); every
  report carries the structural proof, the byte-delta assertion table, the
  parity table, the registration-diff sample, the four-registry census and
  the field-delta table.
* `.venv/bin/python tools/rvt_validate.py --quiet experiments/genesis/subst_k4/residue_a/*.rvt
  experiments/genesis/subst_k4/Y9.rvt experiments/genesis/subst_k4/CTRL_K4_base.rvt`
  → 8 × `OK errors=0 warnings=1` (independent arbiter, this session).
* `.venv/bin/python -m rvt.genesis.residue_a --demo` → 9/9 constructors
  round-trip byte-exact.
* `.venv/bin/python -m pytest tests/test_residue_a.py -q` → **28 passed**
  (2.6 s): the claim contract (A..L / M..Z), every constructor's
  round-trip + our-value assertions, the in-place field-delta discipline
  (CategoryElem name-only, GStyle pen/colour-only), the grid geometry, the
  frozen asset profile + constructor, the plans against Y9 (sizes = Yn's
  residue, family-scoped left, secret roles, family-free heads, referenced
  levels keep elevation), an end-to-end Z_pattern emission (VALID, only the
  partition differs, registries identical, no dangling refs), the built
  reports and the bisection-first manifest.
* Read-back of ZA_deep.rvt: 'GEN Door - Swing (Plan)' at CategoryElem
  1951; door style row 2029 = pen 1 / 0x181818 (our INK); dim style 277 =
  'SecretInternalLinAngDimStyle714q616180'; arrowhead 1471069 = 'GEN Arrow
  Filled 20 Degree' (tick 8); grid 195338 = '01' at our elevation 0.0; level
  694 = 'GEN Mezzanine'; fill 442 = 'GEN Brick Coursing 75mm'; asset 171886
  = 'GEN Appearance - Cast Concrete', diffuse (0.784, 0.777, 0.753); font
  344 = Arial 3.5 mm, black token.
* Full suite: see BRANCH STATE.

## BRANCH STATE

No VCS (plain directory).  NEW files, this stream's territory only:
`src/rvt/genesis/residue_a.py` (constructors + census + the Z-ladder
driver), `tests/test_residue_a.py` (28 pass), `docs/inbox/
genesis-residue-A.md` (this record), and under `experiments/genesis/
subst_k4/residue_a/`: `ZA_deep.rvt`, `Z_subcat.rvt`, `Z_annot.rvt`,
`Z_datum.rvt`, `Z_pattern.rvt`, `Z_asset.rvt` + one `.json` certification
report each, `probes.json` (bisection-first manifest, base Y9, control
CTRL_K4_base), `curtain_constellation.json` (the 232-id coherent-removal
set), `residue_census.json` (the claimed-class census), `residue_after_
ZA_deep.json` (the Zn census: 1,536 residue elements dispositioned),
`generic_asset_profile.json` (the frozen 57–59-property Protein
GenericSchema skeleton, 400 specimens) and `invariants/` (this stream's
mined specimen invariants for the 14 previously-unmined residue classes).
NO existing `src/` module, tool, test or `.rvt` edited; no browser /
viewer use.  Every emitted `.rvt` = validator VALID (0 errors), structural
proof clean, four-registry coherent, `Global/Latest` + `Global/ElemTable`
byte-identical to Y9, registry parity 100 % (asserted), byte-delta
assertion holding, zero dangling references in our objects, per-class
field-delta recorded.
Full suite this session (`.venv/bin/python -m pytest tests/ -q
--ignore=tests/oracle`, 16:04): **996 passed, 3 failed** of 999 — this
stream's 28 tests are among the 996.  The 3 failures: (a) `tests/
test_plugin_sync.py::test_plugin_is_in_sync_with_source` — RESOLVED after
the run: this stream (and the concurrent residue-B stream, plus a `reduce_
law.py` touch by another stream) added `src/rvt` modules, so the plugin
bundle drifted; the project's sanctioned regeneration `python tools/
sync_plugin.py` was run (the standing project rule: sync after every
framework change) — it re-mirrored `src/rvt` into `plugin/lib/` and rebuilt
`rev-revit.zip` (GENERATED artifacts, no hand edits), after which
`tests/test_plugin_sync.py` → 2 passed; (b)+(c) `tests/test_provenance.py
::test_G0_resource_refs_are_counted` and `::test_G0_identity_dit_usernames_
still_leak` — the pre-existing, other-stream STALE assertions every recent
record lists (they pin the pre-genesis-2 G0's defects; owner: the provenance
stream); neither touches this stream's files.  Net after the sync: 998 pass /
2 known-stale.  A provenance ledger v2 of ZA_deep is filed
(`ZA_deep_provenance.json`: Global/Latest 99.95 % identical to the rstbasic
baseline — the container layer is untouched by design; identity remains the
provenance / counsel streams' item).  STOPPED AT READY — the six probes (+
control) await the orchestrator's viewer batch; the curtain-constellation
removal and the two content removals are the recorded next work; Group B
holds the M..Z classes and the two constellations the split rule cut.

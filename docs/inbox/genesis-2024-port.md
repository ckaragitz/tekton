# GENESIS 2024 — CONSTRUCTOR PORTABILITY + THE 2024 MINERS

Stream: **genesis-2024-port** (2026-08-04).  Charter: (1) re-run port2025's
CONFIRMED method against the 2024 schema + samples — own-field signatures
for every class rvt.genesis constructs, 2026-pin vs `rvt.versions.
schema_2024`, plus specimen decode from the quarantined `samples/2024`
corpus — with every 2025-table delta re-established INDEPENDENTLY
(three-way, never assuming monotonic evolution); (2) implement the field
maps in `src/rvt/genesis/port2024.py` (wrapping the untouched 2026
constructors; delegating to port2025's machinery only where the 2024
layout equals 2025's — each delegation recorded); (3) re-run the miners
over the 2024 corpus and freeze; (4) validate every ported constructor's
output against 2024 specimens, byte-level where the 2026 method did.

**DONE conditions met: the confirmed three-way table is frozen; the field
maps are implemented, hook-tested, byte-exact under the 2024 schema and
byte-exact against Autodesk's own 2024 specimens where value-identity
allows; four miner artifacts are frozen; 31 tests green; full suite run
(count below).  NO files were staged for upload — this stream builds no
ladder and touches no viewer batch (constructor + miner charter only).**

Deliverables:

1. `src/rvt/genesis/port2024.py` — the portability layer (three-way
   verdict differ, 2024-mined constants, `adapt()` / `adapt_record()`
   field-map engine, four miners, specimen byte-level gate, selftest CLI)
2. `experiments/genesis2024/miners/portability-2024.json` — the CONFIRMED
   table, every non-IDENTICAL row annotated `vs_2025` (re-derivable via
   `--verify`)
3. `experiments/genesis2024/miners/builtin_category_enum_2024.json`,
   `builtin_style_profile_2024.json`, `pen_table_2024.json`,
   `palette_invariants_2024.json` — the frozen 2024 miners (`--mine`)
4. `tests/test_port2024.py` — 31 tests, all green
5. this record

Python: `PYTHONPATH=src .venv/bin/python` from the repo root (the venv has
no editable install; every CLI below assumes it).

---

## 1. THE CONFIRMED THREE-WAY TABLE (2026 → 2024, annotated vs 2026 → 2025)

Method = port2025's §6 method re-run byte-for-byte: harvest every
CODE-position class literal from `src/rvt/genesis/*.py` (**both
portability layers excluded** — they carry class names as field-map keys,
not constructors), expand with every base class on the chains, compare
own-field signatures `(name, kind, flags, count, type_NAME, extra,
element)` + flattened parent-first chain + class versions, 2026 pin vs the
2024 pin.  Same universe as the 2025 table: 326 harvested, 403 with chain
expansion.  Result (`portability-2024.json`):

| verdict | 2024 | (2025) | notes |
|---|--:|--:|---|
| IDENTICAL | 347 | 361 | machinery layer re-proven: ADocument, Element, Symbol, GElement, SerializedDummy, ElemTable/ElemRec, History, DIT, PartitionTable |
| LAYOUT-DELTA | 40 | 32 | the 2025 table's 32 **minus 0** (every 2025 delta still holds) **plus 8 new** (below) |
| MISSING-2024 | 13 | 8 | the conductor catalog (8, same as 2025) **+ 5 classes 2025 HAS** (below) |
| VERSION-ONLY | 3 | 2 | DataStorage v3→0, **ElementHeader v25→24, FamilyInstance v39→37** (2025 had both IDENTICAL) — free, records carry no version |

### 1a. Deltas IDENTICAL to 2025's (22 classes — port2025 hooks apply verbatim)

GeomTable, NumberingSchema, BrowserOrganization,
BrowserOrganizationTracking (v6→5, the SAME three-field split by tree
code), ModelGraphicsStyle, ViewDisplayMgr, ReinforcementSettings,
RbsWireSettingsElem (same three extra doubles), RbsWireSizesElem (v8→3,
drop `m_bInitialized`, map order free), RbsWireType, AssemblyCodeTable,
KeynoteTable, StructSettingsElem, DBView + every constructed view subclass
(`m_viewPositionId` drop), **Viewport v13→10 — the SAME v10 layout as
2025: 2025 kept 2024's Viewport**, Section, SectionGraphics.

### 1b. Deltas that DIFFER from 2025's (the non-monotonic findings — each established independently)

1. **`GeomStep` v17→15 — THE headline**: 2025 RENAMED
   `m_oExtraDatas`→`m_oExtraData`; **2024 has NO extra-data field at all**
   (the field postdates 2024).  The port2025 rename hook is deliberately
   ABSENT from `HOOKS_2024`; the field drops by construction.  Hits all
   five GStep constructors (VertCompoundStructure / DatumPlane /
   CoordinateElemBase / MakeCutterForPlanRegions(+Base) / Viewer).
2. **`DBViewDrafting` v12→11**: 2024 additionally lacks
   `m_sheetCollectionId` (2025 had it; SheetCollection itself is
   MISSING-2024) and carries 2024-only **`m_scheduleInstanceIds`**
   (ElementId container) — corpus value on fresh drafting views = EMPTY
   (8/8 rst specimens), so the schema blank `[]` IS the corpus value; no
   hook.  The DBView base delta (`m_viewPositionId`) is shared with 2025.
3. **`FamilyBase` v48→47**: 2024 drops `m_familyNestingBehavior` +
   `m_tagOrientationBehavior` IN ADDITION to 2025's
   `m_classificationDescription` drop; gains the same `m_bAdHoc`.  Not
   constructed (harvest name-collision) — verdict recorded only.

### 1c. Deltas 2024 has that 2025 does NOT (2025=IDENTICAL; all layouts established from the 2024 schema + specimens)

4. **`AutoCamSettingsElem` v6→5**: the seven camera vectors are RENAMED
   **and RE-TYPED** — 2026 inline `XYZ` fields (`m_homeEyeXYZ`,
   `m_homeCenterXYZ`, `m_homeUpXYZ`, `m_homePivotXYZ`, `m_sceneUpXYZ`,
   `m_sceneFrontXYZ`, `m_sceneCenterXYZ`) are 2024 fixed `double[3]`
   arrays without the XYZ suffix, and the own-field ORDER differs
   (vectors first in 2024).  Values are `[x,y,z]`-compatible; hooked for
   all seven; the walk's target-chain order handles the reorder.  OUR
   constructor's fresh-home values (`m_sceneFront` +Y, `m_sceneUp` +Z,
   `m_homeProjToPageScale` -1) are **byte-exact vs the 2024 rst specimen
   102842** — see §4.
5. **`RbsDuctSettingsElem` v15→14**: 2026 `m_airDynamicViscosity`
   (DYNAMIC viscosity μ, kg/(ft·s)) → 2024 `m_dAirViscosity` — a
   **DIFFERENT PHYSICAL QUANTITY: the KINEMATIC viscosity ν in ft²/s**.
   Confirmed bit-exact in Autodesk's own corpus: 2024 rst 102127
   `m_dAirViscosity` 0.0001622533748701973 == 2026 rst
   `m_airDynamicViscosity` 5.52543392433963e-06 ÷ `m_dAirDensity`
   0.034054354362490005 (both releases carry the SAME density field —
   Autodesk's migration is exactly ν = μ/ρ).  Hook computes ν from the
   source object's own μ and ρ, so our authored physics stays
   self-consistent (tested to Python float equality).
6. **`MEPNetworkTracker` v4→3**: `m_component2BaseSegmentMap`
   (pair<NetworkSegmentId,NetworkSegmentId>) → 2024
   `m_component2BaseElementMap` (pair<ElementId,ElementId>).  Our tracker
   constructor and every corpus specimen carry the EMPTY map; the hook
   carries empty verbatim and REFUSES a non-empty source (no lossless
   NetworkSegmentId→ElementId mapping exists; tested).
7. **`RbsDistributionSysType` v2→1**: 2026-only `m_highLegPhase` dropped
   (generic walk; constructed by `new_distribution_system`).
8. **`HVACLoadScheduleElem` v4→3**: same two own fields, opposite ORDER —
   walk handles; residue_a2's day-schedule constructor ports (tested at
   the class-level adapt; its `Obj` shape has no header/rep).
9. **`IndependentTag` v22→21** (KeynoteTag inherits): drops three 2026
   head-position fields, gains 2024-only `m_taggedEntitiesCell` (inline
   TaggedEntitiesCell).  NOT constructed (KeynoteTag appears only as a
   regen-wildcard classref) — verdict recorded only.
10. **`Rebar` v57→54**: 2026-only `m_frozenSegments` dropped (2025 was
    VERSION-ONLY v57→56 — the field exists in 2025).  Not constructed.

### 1d. MISSING-2024 beyond the conductor catalog — five classes 2025 HAS, all CONSTRUCTED by genesis

`SheetCollection`, `SheetsInSheetCollectionTracker`, `MEPNetworkDataElem`,
`STEPExportSettings` (settings singletons / trackers),
`BuildingOperatingYearSchedule` (residue_a2 HVAC machinery).  Their
constructors emit NOTHING on a 2024 build — `adapt_record` raises
`Missing2024` (tested for all + the conductor catalog).
`MISSING_2024_CONSTRUCTED` in the module is the authoritative list.  NB
`SheetsInSheetCollectionTracker`'s regen wildcards name `SheetCollection`
— both vanish together; the classref guard in the walk would refuse any
OTHER 2024-emitted header naming a missing class.

### 1e. Delegations to port2025 (each recorded + guarded)

* `PortabilityError`, `_AdaptContext`, and the dec-parameterised blank
  machinery `_blank_class25/_blank_field25/_blank_scalar25` (release-
  agnostic — every schema lookup goes through the decoder argument; passed
  the 2024 decoder they produce 2024 blanks).
* Pure value hooks `_hook_sort_param_id` / `_hook_numbering_min_digits` /
  `_hook_numbering_matching` / `_browser_tracking_tree`.
* The two NumberingSchema hooks that build
  `ParameterBasedPartitionDescriptionCreator` / `NumberingSchemaType`
  bodies as 2025 blanks: sound because BOTH classes are LAYOUT-IDENTICAL
  2024==2025 and the 2024-mined GUID table equals 2025's —
  `test_delegated_numbering_hooks_precondition_layouts_identical_2024_2025`
  makes drift fail loudly.  (Also verified identical 2024==2025:
  PenWidthTable, PenInfoForScale, PatternHelper, CellList.)
* The adapt WALK is port2024's own (port2025's is hardwired to its 2025
  singleton) — same shape, bound to the 2024 pin + `HOOKS_2024`.

## 2. MINED 2024 CONSTANTS (all re-derived independently; provenance per constant)

* `RbsWireSettingsElem` doubles: **0.02 / 0.03 / 303.15000000000003 K**
  (rst 102129) — equal to 2025's.
* `GeomTable` extra ints: **(-1, -1)** — 5,620 of 5,637 decoded rst
  GeomTables (the same 5,620/5,637 ratio the 2025 miner saw).
* `NumberingSchema` oracle (rst 1218729/1218730/1457391): same three
  schemaTypeGuids as 2025, minDigits 1, matching True,
  ParameterBasedPartitionDescriptionCreator{ccda weakref 1,
  m_partitionParameterId}.
* GDI flags: False — **85/85 ViewDisplayMgr** (nested inside the views;
  2024 rst has none as elements) + 2/2 ModelGraphicsStyle.
* `ReinforcementSettings.m_numberVaryingLengthRebarsIndividually`:
  **True** (rst 137426).
* `RbsWireType.m_strMaxConductorSize`: bare label **'2000'** (rst 55171).
* Duct viscosity RULE (2024-new): ν = μ/ρ (§1c-5).
* Pen table (rst/rme/rac id 2): scale keys **[10, 20, 50, 100, 200,
  500]**, 16 pens/vector, persp/draft -1 — IDENTICAL to the 2026
  constructor constants (`PEN_SCALE_BREAKPOINTS`/`PEN_COUNT` port
  unchanged; asserted by the miner and tests).

## 3. THE FROZEN 2024 MINERS (`experiments/genesis2024/miners/`)

* **category enum 2024**: **1,061 categories (329 cuttable)**, identical
  across the three 2024 basics (asserted).  Three-way: 2024 (1,061) ⊂
  2025 (1,068) ⊂ 2026-ish (1,074): 7 categories are 2025+2026-only, 7
  more are 2026-only, and **-2008152 exists in 2024+2025 but not 2026**;
  cuttability IDENTICAL on every shared id across all three releases.
* **per-key style profile 2024**: **1,390 (category,style-type) keys over
  4,170 rows** (1,390 per file — identical row sets).  Vs 2026: the SAME
  four flag-word keys the 2025 stream found differ the SAME way
  (`-2000710..713:1` = 0x400200e→**0x400201e**); vs 2025: **zero**
  flag-word differences on all 1,390 shared keys — the header-flag format
  constant is IDENTICAL 2024==2025.  (93 shared keys differ from 2026 in
  pattern/material/screen wiring — corpus CONTENT variation between
  sample generations, not format; a 2024 catalog rung must use the 2024
  profile, which encodes it.)
* **pen_table_2024.json**: the §2 pen constants, per-file evidence rows.
* **palette_invariants_2024.json**: **129 PropertySetElements** (rst 56 /
  rme 20 / rac 53): param containers ASCENDING **387/387**, param ids
  NEGATIVE **100%**, `m_pElementIdParams` PRESENT-EMPTY **129/129** —
  residue_b2's three corpus laws hold verbatim in 2024 (`laws_hold`
  asserted by the miner itself; a violation refuses to freeze).

## 4. CONSTRUCTOR VALIDATION (round-trip + corpus shape + SPECIMEN BYTES)

* **Round-trip gate**: every adapted record (17-record battery: wall,
  material, line pattern, fill pattern, floor, wire type, distribution
  system, numbering schema, pen table, browser org, struct settings,
  keynote table, wire settings, reinforcement settings, auto-cam, duct
  settings, MEP network tracker) encode→decode→re-encode **BYTE-EXACT
  under the 2024 schema**, seq-101/102/103 all clean.  4 refusals correct
  (conductor size + three 2024-missing singletons).
* **Corpus-shape parity**: adapted key sets == decoded 2024 rst key sets
  for BasicWallType, RbsWireType, RbsWireSettingsElem,
  BrowserOrganization, AutoCamSettingsElem, RbsDuctSettingsElem,
  MEPNetworkTracker, NumberingSchema.
* **SPECIMEN BYTE-LEVEL (the 2026 method's own byte-exact claims,
  re-proven on 2024 through the hooks)**:
  * OUR `auto_cam_settings` adapted → **byte-exact vs rst 102842**
    (362 B) — the 2026 constructor's "[VERIFIED byte-exact vs rst
    102842]" claim holds on 2024 THROUGH the seven rename/re-type hooks.
  * OUR empty `tracker("MEPNetworkTracker")` adapted → **byte-exact vs
    rst 1468014** (112 B) — EMPTY_TRACKERS' byte-exact claim through the
    map-rename hook.
  * OUR `pen_width_table` with the specimen's own vectors re-fed →
    **byte-exact vs rst elem 2** (1,201 B) — the 2024 pen-table LAYOUT is
    exactly our constructor's (widths are values, not format).
  * Specimen re-encode round-trips (decode→encode byte-exact under the
    2024 codec) for one host specimen of EVERY ported constructor class —
    21/21 clean + byte-exact (incl. GStyleElem, PropertySetElement,
    DBViewDrafting, RbsWireSizesElem).

CLI reproduction: `--verify` (table), `--mine` (miners), `--selftest`
(battery + specimen gate; skips specimen parts off the dev machine).

## 5. FINDINGS FOR OTHER TERRITORIES (not applied — outside my territory)

1. **port2025's harvest now sees the sibling port layers** (it excludes
   only itself; `port2024.py` — mine — and `port2023.py` — the 2023
   stream's, which appeared while this stream ran — are both scanned by
   it).  Measured impact of port2024.py on a re-derived
   `portability-2025.json`: **zero new names, zero
   verdict/count/constant changes** — 40 existing names gain
   `port2024.py:N` provenance strings (I kept every class-name literal in
   port2024.py to names already harvested; the two hooks that would have
   introduced new names are the delegated port2025 functions).
   port2023.py DOES introduce two otherwise-unharvested names
   (`Identifier`, `ParamDef` — both IDENTICAL verdicts) into any harvest
   that scans it.  My harvest excludes ALL `port20XX.py` by pattern
   (`_is_port_layer`) — portability layers are field maps, not
   constructors — which keeps my universe at exactly port2025's 326/403.
   Proposed proper fix for the port2025 stream: the same pattern
   exclusion.  Running `tests/test_port2025.py` (write=True) refreshes
   their frozen JSON with the extra provenance (+ the two port2023 names
   when derived after port2023.py existed); their `>=` count assertions
   hold either way — verified 19/19 green.
2. **Concurrent-stream observation**: `src/rvt/genesis/y2025_a.py` /
   `y2025_b.py` (the 2025 compose fleet's) appeared during this stream;
   they add provenance-only hits to the harvests (zero new class names as
   of this record — verified).  If they later name new schema classes in
   code position, both portability universes grow by rule (harvest = the
   genesis constructor surface); my tests bound counts with `>=` so they
   stay green.  Their territory NOT touched.
3. **For a future Y2024 ladder** (NOT this stream): the run_ladder2025
   pattern ports — bind `rvt.versions.reading` 2024 framing (0x0e7c
   family), swap default codecs to the 2024 pin, redirect catalog loaders
   to `load_2024_catalog_constants()`, wrap `build_for` with
   `port2024.adapt_record`, and patch the re-blocker's writer-side tags
   (reduce.BLOCK_TAG — port2025's §4 finding applies verbatim).  The five
   MISSING-2024 singletons mean the settings rung must SKIP those
   constructors (the ladder substitutes in place, so they only matter on
   an assembler path); `sheets-in-collection` tracking simply does not
   exist in 2024.
4. **BasicWallType et al. carry no 2024 surprises**: the whole host-type
   layer (walls/floors/roofs/ceilings, materials, patterns) is IDENTICAL
   2026==2024 except the GeomStep/GeomTable deltas already hooked.

## Open questions carried forward

* The Autodesk viewer has never seen a 2024 upload from us (same standing
  question as 2025; the 2025 round-1 control answers the viewer-accepts-
  older-releases question for both).
* `m_taggedEntitiesCell` / `m_bAdHoc` blank-vs-corpus defaults were NOT
  established (their classes are not constructed); if a future stream
  constructs IndependentTag/Family for 2024, mine them first.
* The MEPNetworkTracker non-empty-map refusal is theoretical today (no
  constructor emits a non-empty map); if a 2024 fabrication path ever
  needs it, the NetworkSegmentId→ElementId relation must be reverse-
  engineered from a 2024 fabrication specimen (none in the basics).

---

## SUITE RESULT (final, 2026-08-04)

`PYTHONPATH=src .venv/bin/python -m pytest -q --continue-on-collection-errors`
from the repo root: see BRANCH STATE below (recorded after the final run;
`tests/test_port2024.py` 31/31 green in-suite and standalone;
`tests/test_port2025.py` still 19/19).

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — no git branch work (repo has no
  commits; integration is the orchestrator's).
* NEW (this stream's territory):
  * `src/rvt/genesis/port2024.py`
  * `tests/test_port2024.py` (31 green)
  * `experiments/genesis2024/miners/` — `portability-2024.json`,
    `builtin_category_enum_2024.json`, `builtin_style_profile_2024.json`,
    `pen_table_2024.json`, `palette_invariants_2024.json`
  * this record
* Touched OUTSIDE territory: **no source/tool/test edits anywhere**.  One
  cross-territory FILE REFRESH happened as a side effect of running the
  suite: `experiments/genesis2025/subst/portability-2025.json` was
  re-frozen by `tests/test_port2025.py` (its own write=True test) and now
  carries `port2024.py` + `y2025_b.py` provenance strings — counts,
  universe, verdicts and constants verified byte-identical (§5.1-2).
  `experiments/genesis/subst_k4_2025/` (the 2025 compose fleet) NOT
  touched.
* DONE check: confirmed table ✓ (frozen, three-way annotated, the
  non-monotonic deltas established independently); field maps ✓
  (hooked, delegation-guarded, round-trip-gated, corpus-shape-checked);
  frozen miners ✓ (enum + cuttability, per-key style profile with the
  flag-word verdict, pen-table scale keys, palette property-set
  invariants incl. param-id-ascending, corrected defaults); constructor
  validation ✓ (byte-exact round-trips + THREE byte-exact-vs-specimen
  proofs + 21/21 specimen re-encode round-trips).  STOP at READY:
  nothing uploaded, nothing claimed certified.

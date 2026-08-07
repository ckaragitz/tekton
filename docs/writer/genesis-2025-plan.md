# GENESIS 2025 — the Revit-2025 lineage plan (MULTI-VERSION PHASE A deliverable)

Stream: **versions** (MULTI-VERSION PHASE A, 2026-08-04).  Status: **PLAN —
not yet run** (phase A delivers read parity + the version model + this plan;
the campaign itself is phase B).  Companion record: `docs/inbox/versions.md`
(read-parity table, acquisition, the version model).  Machine-readable diff
behind every table here: the differ described in §6 (re-runnable; its JSON
lives with the phase-A artifacts).

## 0. Why: the real end user runs Revit 2025

Revit CANNOT open a file saved by a newer release.  Our certified genesis
base (`experiments/genesis/subst_k4/compose/G_ABPD.rvt`, pinned in
`rvt.frontdoor.base`) is **Revit 2026** — unusable to the Revit-2025 user.
Reading/editing is version-agnostic by design (schema-directed against the
file's own `Formats/Latest`; proven at parity for 2024/2025 by phase A), but
**creating** a version-N file needs version-N format data:

1. the version-N `Formats/Latest` class schema            — HAVE (pinned,
   `rvt.versions.schema_2025`, sha256 `c964f9aa…`, 484,585 B, 4,600 classes,
   byte-identical across all six 2025 samples + the 2025 sample .rfa);
2. the version-N unit/spec/parameter-group corpus inside `Global/Latest`
   (+ the `ESSchemaStorage` unit-schema data)             — HARVESTABLE from
   `samples/2025/` (step G25-0 measures it; counsel C4 applies per release);
3. a version-N **certified genesis base**                 — DOES NOT EXIST;
   producing it is this campaign.

Until step G25-5 flips `KNOWN_RELEASES[2025].creation_certified`,
`rvt.versions.require_creation_release(2025)` refuses — a 2025 request
must never be silently answered with a 2026 file.

## 1. What phase A already established (the ground the plan stands on)

* **Read parity** (`rvt.versions.parity`, 2026-08-04): all six 2025 samples
  and all six 2024 samples read VALID — 100 % gzip CRC, 0 StreamWalker
  errors, schema parse OK, seq-102 decode 99.18–100 % clean (identical
  per-discipline percentages to the 2026 baseline; the only failures are the
  same Extensible-Storage blob gaps 2026 has).
* **No schema-parser deltas.**  The `Formats/Latest` grammar is unchanged
  2024→2026; `rvt.schema.parse` reads all three releases to EOF unmodified
  (`schema_2025.PARSER_DELTAS == ()`, asserted by tests/test_versions.py).
* **Ordinals drift, names do not.**  Every partition-framing "constant" is a
  class ordinal (SegmentMarker 0x0f28→0x0ed9, PartitionTable 0x0c80→0x0c40,
  …) resolved BY NAME from the file's schema via
  `rvt.versions.ordinals_from_schema` / activated by `rvt.versions.reading`.
* **The machinery layer is IDENTICAL 2026→2025** (field-for-field, version-
  for-version): ADocument, ElemTable/ElemRec/GraveyardRec, DocumentHistory,
  DocumentIncrementTable, DocumentStorageIndexImpl, PartitionTable,
  ESSchemaStorage, Element, Symbol, ElementHeader, GElement, SerializedDummy,
  and all six framing classes.  The ADocument codec, the four-registry law,
  the re-blocker, ECC/page framing and the record encoders port to 2025
  with NO field-map work — only ordinals differ.

## 2. The certified 2026 lineage this plan mechanizes

The pipeline that reached GENESIS (verdict #24) — every step has a tool and
a certification artifact, all re-run on the 2025 sample instead:

    rstbasicsampleproject.rvt        (the release's rst basic sample)
      └─ reduction ladder            tools/rvt_reduce.py + rvt.reduce_v2
           R5 … R9                   (deepest viewer-PASSED reduction)
      └─ family-free triage          tools/genesis_triage.py
           K3 (family USAGE nulled) → K4 (family layer removed,
           four-registry coherent)   = THE CERTIFIED BASE
      └─ in-place substitution       tools/genesis_substitute_v3.py
           Y-rungs (settings / catalog / palette / datum / views / residue),
           each rung = replace one slot's payload with OUR constructor's
           output, registries byte-identical, + per-batch certified control
      └─ compose                     tools/genesis_compose.py
           G_ABPD.rvt                (all layers ours; anchor byte-exact)
      └─ certification               user-run Autodesk viewer uploads,
                                     ledgered in docs/coverage/viewer-certified.json

Discipline rules carried over verbatim (learned the hard way — K1):
**certify the base itself before building on it**, and **≥ 1 certified
positive control per upload round** (`tools/genesis_controls.py`).

## 3. The campaign, step by step

**G25-0  Harvest + measure the 2025 format-data corpora.**
Inputs: `samples/2025/rstbasicsampleproject.rvt` (primary; smallest).
Measure the `Global/Latest` product-runtime corpus (unit/spec/parameter-group
JSON) and the `ESSchemaStorage` payloads against their 2026 counterparts
(`tools/latest_map.py`, `rvt.estorage`) — expected per-release constants,
byte-identical within the release (verify across all six 2025 samples the way
the schema constant was verified).  Output: the 2025 corpus pins (sizes +
sha256s) appended to `docs/inbox/versions.md`.  Everything below runs inside
`rvt.versions.reading(<2025 file>)`.

**G25-1  Reduction ladder on the 2025 rst sample → R-rungs-2025.**
Re-run the R-ladder (`tools/rvt_reduce.py`, the `rvt.reduce_law` gates).
Expected to port cleanly: reduction only deletes + re-blocks, and the
re-blocker + ADocument codec are release-identical (§1).  New per-release
inputs: none.  Upload round 1: R5-2025 (+ CTRL = the untouched 2025 sample,
which the viewer must PASS — also proves the viewer accepts 2025 uploads).

**G25-2  Family-free triage → K4-2025.**
`tools/genesis_triage.py` K-rungs; the four-registry law is
release-identical.  Upload round 2: K4-2025 + control.  K4-2025 is then THE
certified 2025 base for everything after — nothing builds on an uncertified
rung.

**G25-3  Retarget the constructors at the 2025 schema.**
The one genuine engineering delta of the campaign (§4): give
`rvt.genesis.types._S()` a schema/decoder parameter (or a
`rvt.versions`-driven context) so `blank_object` walks the **2025** class
map and `class_id()` returns **2025** ordinals, then apply the §5 field-map
table (23 classes; 185 need nothing).  Round-trip gate: every constructor
output must encode→decode byte-exact under the 2025 schema
(tests/test_genesis_types.py parameterized over the release).

**G25-4  Substitution ladder → Y-rungs-2025 → compose.**
`tools/genesis_substitute_v3.py` on K4-2025 with the retargeted
constructors; same rung order as subst_k4 (settings → catalog → palette →
datum → views → residue); registry parity asserted per rung; upload rounds
with controls; then `tools/genesis_compose.py` → `G_ABPD_2025.rvt`.

**G25-5  Certify + register + flip the guard.**
Viewer-PASS `G_ABPD_2025.rvt` (3D + sheet, not empty) → ledger it in
`docs/coverage/viewer-certified.json` → add it to the `rvt.frontdoor.base`
registry with a sha256 pin (+ bundle in the plugin next to the 2026 base) →
set `KNOWN_RELEASES[2025].creation_certified = True`, `genesis_base = <path>`
— which is what makes `require_creation_release(2025)` start saying yes.
Identity: BasicFileInfo must say `Format: 2025` with OUR authoring string
(G2/C1 interaction — same counsel question as 2026, asked once, applied per
release).

**G25-6  2024 repeat.**  Same ladder on `samples/2024/`; the extra 2024
field maps are in §5b (four more classes + two version-only stamps).

Explicitly OUT of scope here: the famgen/.rfa path for 2025 (needs a 2025
specimen ancestor + the 2025 family corpus — problem (A)'s research-machine
dependency, tracked separately) and the walls+families combination bug (r2),
which is release-independent and stays with its own stream.

## 4. The retarget mechanism (why this is small)

`rvt.genesis` never hard-codes layouts: `blank_object(name)` walks the
archive class map at runtime and constructors overlay fields BY NAME;
`rvt.encode` serializes schema-directed the same way.  `ObjectDecoder`
already accepts an injected `Schema`.  So retargeting = handing the 2025
schema to one singleton (`_S()` in `src/rvt/genesis/types.py`, today
`ObjectDecoder()` default = the 2026 map) — after which every constructor
whose overlay fields exist unchanged in 2025 ports automatically, ordinals
included.  Proposed patch (NOT applied in phase A — genesis is outside the
versions stream's territory):

```python
# genesis/types.py — sketch
_STATE = {}
def _S(schema=None):
    key = id(schema) if schema is not None else "default"
    if key not in _STATE:
        dec = ObjectDecoder(schema)          # schema=None -> 2026 map, today's behavior
        _STATE[key] = (dec, ObjectEncoder(decoder=dec), dec.schema)
    return _STATE[key]
```

plus threading an optional `schema=` through `blank_object` / `class_id` (or
a module-level `use_schema()` context mirroring `rvt.versions.reading`).

## 5. Constructor portability table (2026 → 2025)

Method: §6.  Universe = **208 classes** `rvt.genesis` constructs
(harvested from every `blank_object` / `_owned` / `_ptr` / helper literal +
the ParamDef kind sets across `src/rvt/genesis/*.py`).

**Verdict: 185 / 208 (89 %) port AS-IS** — identical own fields, identical
flattened base-chain layout, identical class versions; only the class
ordinal differs, which the retarget resolves by name.  **6 are 2026-only
classes** (the conductor catalog — its 2025 representation differs by
design, see 5a.1).  **17 have field-layout deltas** needing the maps below.

The 185 include (grouped by constructor family): all ParamDef kinds +
ParamElem{External,Project,ElectricalLoadClassification} + ParamBinding +
ParamValueSet*; the host types (BasicWallType, FloorAttributes,
RoofAttributes, CompoundCeilingType, CompoundStructure,
VerticalRegionsStructure, TaperableWallType*Cell); materials & appearance
(Material(Elem), AppearanceAsset(Elem), Asset, AProperty*); patterns & text
(Line/FillPattern(Elem), FillGrid, Font(Elem), TextNoteAttributes,
LeaderStyle); MEP catalogs (RbsVoltageType, RbsDistributionSysType,
Conduit*/CableTray*/Pipe* types+sizes+settings, RbsWire{Material,Insulation,
TemperatureRating}Type, ElectricalSetting, Demand/LoadClassification);
categories & styles (Category(Elem), GStyle(Elem), all G*Overrider,
GraphicOverrides, OverrideGraphicSettings); datum & views (Grid(Attributes),
Level via machinery, Section/InteriorElev/Viewport/Callout attributes,
ViewSheetSet, ViewLayout, PlanViewRange(2), InitialViewSettings, LightScheme,
GRenderSettings, all DrawFilters/Mgr/view-settings singletons); geometry rep
(GElement, Geometry, GeomStepList, GPoint, Face, Outline, Trf, GBitmap);
project singletons (revisions, keynoting entries/system, energy, fabrication,
HVAC loads, structural loads, area/route/copy settings, PenWidthTable(Elem),
RetouchTable, DrawOrderMgr, browser/worksharing/SSE view settings,
AutoJoinTracker, ElementParents, InstanceInfo, SymbolInfo,
SlaveSymbolTracker*).  ElementHeader (seq-101) and the Element/Symbol bases:
identical.

### 5a. The 23 that need work for 2025

#### 5a.1  MISSING in 2025 — the conductor catalog is a 2026 invention (6 classes)

`CustomElement`, `NamingCell`, `RbsConductorMaterial`,
`RbsConductorTemperatureRating`, `RbsConductorInsulationMaterial`,
`RbsConductorSize` do not exist in the 2025 (or 2024) schema.  2026 models
the wire catalog as CustomElement cells referenced by id; 2025 models the
same facts as strings/ids on the wire type itself.  Disposition:

* `new_conductor_material` / `new_conductor_temperature_rating` /
  `new_conductor_insulation` / `new_conductor_size` (all built on
  `_custom_cell_element`): **2026-only — emit nothing on a 2025 build.**
* `new_wire_type`: on 2025 write `m_strMaxConductorSize` (AString, e.g.
  `"1000 kcmil"`) instead of 2026's `m_idMaxConductorSize` (ElementId into
  the catalog); note the field sits FIRST in the 2025 field order (handled
  automatically by schema-directed encode).  `m_idMaterial` /
  `m_idTempratureRating` / `m_idInsulation` keep pointing at the (identical)
  RbsWire*Type symbols.  RbsWireType class version 5→2.

#### 5a.2  LAYOUT-DELTA in 2025 — field maps (17 classes)

| class (constructor family) | 2025 delta vs 2026 | disposition for the 2025 build |
|---|---|---|
| GeomStep — base of VertCompoundStructureGStep, DatumPlaneGeomStep, CoordinateElemBaseGeomStep, MakeCutterForPlanRegionsGStep, ViewerGStep (v17→16) | `m_oExtraDatas` (2026) is `m_oExtraData` (2025) — rename + container→single | constructors leave it defaulted → blank_object against the 2025 map already emits the right shape; no overlay touches it (verify with the round-trip gate) |
| GeomTable (palette/geometry) | 2025 has 2 EXTRA leading fields: `m_maxSafeTag` (int), `m_lastCheckedKingsUserModificationDate` (int) | default 0 is the corpus value for fresh tables — confirm against the 2025 sample's decoded GeomTables, then keep defaults |
| RbsWireType (wire) v5→2 | see 5a.1 | string max-conductor-size |
| RbsWireSettingsElem (settings) v13→12 | 2025 has 3 EXTRA doubles: `m_dMaxVoltageBranchSizing`, `m_dMaxVoltageFeederSizing`, `m_dAmbientTemperature` | REAL electrical values required, not type defaults — DECODED from the 2025 rme sample (elem 293123): `0.02` / `0.03` (the 2 %/3 % max voltage-DROP sizing fractions) and `303.15` K (30 °C ambient); mirror these; the sizing model moved into the conductor catalog in 2026 |
| RbsWireSizesElem (wire sizes) v8→3 | 2026-only `m_bInitialized`; map order `materials, wirediameters, powerfactors` (2025) vs `materials, powerfactors, wirediameters` (2026) | drop the flag; order is schema-directed (free) |
| NumberingSchema (residue) v8→5 | near-total rework: 13 2026-only fields (m_formatSettings, m_matchingParams, …) vs 4 2025-only (m_oPartitionDescriptionCreator, m_minimumNumberOfDigits, schemaTypeGuid, m_isMatchingEnabled) | rewrite the constructor body per-release; copy the 2025 sample's own default numbering schemas as the field oracle (they are product defaults, not sample expression — same classification as the 2026 ones we mirror today) |
| BrowserOrganization (views) v6→5 | 2026 `m_sortParameter` (AggregatedParameter) ↔ 2025 `m_sortParamId` (ElementId) | 2025 branch writes the ElementId form (−1 / builtin param id) |
| ModelGraphicsStyle (views) v7→6 | 2025 EXTRA `m_bUseGDI` (bool) | default False (corpus value — confirm) |
| ViewDisplayMgr (views) v35→34 | 2025 EXTRA trailing `m_useGDI` (bool) | default False (confirm) |
| AssemblyCodeTable (residue) | 2026-only `m_hasUserCustomizedAssemblyCode` | drop (2025 own fields = []) |
| KeynoteTable (residue) v11=11 | 2026-only `m_hasUserCustomizedKeynote` | drop |
| StructSettingsElem (settings) v25=25 | 2026-only `m_boundarySetbackDisabledForSteelElements` (mid-list) | drop; rest unchanged |
| ReinforcementSettings (settings) v4→3 | 2026 `m_numberingMethod` (int) ↔ 2025 `m_numberVaryingLengthRebarsIndividually` (bool, different position) | 2025 branch writes the bool (sample default) |

(The GeomStep row covers 5 of the 17; the table lists each family once.)

### 5b. 2024 addendum (beyond the 2025 maps)

Everything in 5a plus: `AutoCamSettingsElem` (home/scene eye-center-up
fields are `m_homeEye`/… in 2024 vs `m_homeEyeXYZ`/… in 2026 — rename,
same XYZ payload); `HVACLoadScheduleElem` (field reorder only — free under
schema-directed encode); `RbsDuctSettingsElem` (`m_dAirViscosity` ↔ 2026
`m_airDynamicViscosity`); `RbsDistributionSysType` (2026-only
`m_highLegPhase` — drop).  Version-only stamps (layout identical, class
`version` differs — carried automatically because the version comes from
the target schema): ElementHeader v25→24, FamilyInstance v39→37.
`ESSchemaStorage` and `FamilySymbol` have real 2024 layout deltas — both
outside the genesis constructor set (read-side handles them; the .rfa path
is out of scope).

Global context: 4,690 (2026) / 4,600 (2025) / 4,492 (2024) classes; 106
classes exist in 2026 but not 2025 (the conductor catalog, numbering-format
machinery, analytical-automation, rebar-crank…), 16 exist in 2025 but not
2026 (DesignOptionConfiguration*, ParamDefAttachment/HorzAlign/VertAlign/
Uniformat, RebarRegenData…) — none of the 16 is needed by any genesis
constructor.

## 6. Reproducing the diff (the method is part of the deliverable)

1. Parse each release's schema from its quarantined sample
   (`rvt.versions.schema_of`; pins in `rvt.versions.schema_2025/_2024`).
2. Harvest the constructed-class set from `src/rvt/genesis/*.py` by regex
   over `blank_object("…")`, `_owned("…")`, `_ptr("…")`, the typed helper
   calls, and `PARAM_DEF_CLASSES`.
3. Per class, compare 2026 vs target: own-field signatures
   `(name, kind, flags, count, type_NAME, extra)` — type NAMES, never
   numeric ids, because ordinals drift — plus the flattened parent-first
   base-chain layout (what `blank_object` actually walks) and the per-class
   `version` stamps.
4. Classify IDENTICAL / VERSION-ONLY / LAYOUT-DELTA / MISSING.

Rerun trigger: any new `blank_object` literal in genesis, or a new target
release.  Fold the differ into `rvt.versions` (e.g. `rvt.versions.diff`)
when phase B starts — proposed, not built, in phase A.

## 7. Risks / open questions

* **Viewer accepts 2025 uploads?**  Round 1's control (the untouched 2025
  sample) answers this before anything is built on it.
* **Value-level (not layout-level) drift**: fields whose layout is identical
  but whose corpus default changed between releases (e.g. new built-in
  categories in registries).  The substitution ladder's registry-parity
  gates catch this per rung; the field oracle is always the 2025 sample's
  own decoded records.
* **Unit/spec corpus size** (G25-0): if the 2025 corpus differs materially
  from 2026's 1,333,338 B blob, the counsel C4 brief should name both.
* **ECC/page framing**: already proven release-identical by the parity run
  (every page of every 2024/2025 sample verifies), so NOT a risk.
* **Tool assumptions**: the reduction/substitution tools import
  `rvt.partitions` constants at module level in places; running them under
  `rvt.versions.reading` handles the live lookups, but each tool's first
  2025 run should be watched for a baked `0x0f28`-era literal (the known
  ones were centralized into `rvt.partitions` and are covered).

## 8. DONE definition for the campaign (phase B)

`G_ABPD_2025.rvt` viewer-certified and ledgered; pinned in
`rvt.frontdoor.base` and bundled in the plugin; `require_creation_release
(2025)` passes; `tools/frontdoor.py author --target-release 2025` (flag to
be added at G25-5) produces a 2025-stamped file that the Revit-2025 user
opens in his own Revit.

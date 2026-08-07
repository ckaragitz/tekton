# GENESIS STATUS v2 — the first G1 CANDIDATE (our own ADocument) and the honest gate reading

Stream: **genesis-2 assembler** (2026-08-03), continuing the **genesis-assembler**
stream (v1 of this document, superseded).  Deliverables:
`experiments/genesis/{G1a, G1_candidate, G1b, G1_candidate_safe}.rvt` (the G1
set) built on a re-assembled `G0.rvt` / `G0_safe.rvt` (the element ladder,
now carrying the own-content **house standard**), by `tools/genesis_assemble.py`
v2.  Certification: `G1_validate.json`, `G1_provenance.json` (+`.txt`),
`G1_gate.json`, per-variant `G1*_authoring/_provenance/_validate.json`,
`G1_registry_maps.json`, `G1_pipeline.json`.  Companion record:
`docs/inbox/genesis-2.md`.

The P0 gate this serves (TRACKER **G1 GENESIS BASELINE**): *nothing ships until
the base document contains NO Autodesk-authored expression*, measured by
`tools/provenance.py --baseline all --streams` (the v2 instrument, all four
layers).

---

## 0. The one-paragraph verdict

**`G1_candidate.rvt` (331,776 B) is a validator-VALID Revit 2026 project whose
element inventory (234 elements, the own-content house standard) AND whose
document object (`Global/Latest`, the serialized `ADocument`) are constructed
by us.**  The last Autodesk stream G0 carried verbatim — the rst sample's
1.59 MB ADocument, which enumerated 6,405 dangling sample element ids, the
sample's room / sheet / assembly names, the users `liqi`/`macalis`, 52 records
of content documents G0 does not have, and the sample's 2018→2026 save lineage
— is replaced by a document object built from the decoded graph: every
element-id registry purged of dangling ids (10,175 references → 0, verified
independently by a byte-level scan) and refilled to index **exactly our
inventory** (214 of our 234 ids appear in the object — the byte scan's count;
the other 20 are Viewer / Viewport / ExtentElem / ModelClipBox / LightScheme /
FontElem / GeoSite / ProjectPhase, classes no sample's ADocument references
either), every sample name cache / user map / link-reconcile dataset emptied,
the loaded-content registry made coherent with the empty ContentDocuments,
the "saved by" list reduced to the Revit-2026 product build constant, our
identity in BasicFileInfo AND in every DocumentIncrementTable episode (the
V32 username scrub, now inside the assembler).  **The v2 gate verdict is still
FAIL — honestly**: what remains is (i) 135 elements whose serialized bytes are
Revit *product-default machinery* our constructors necessarily reproduce
(90 of them the house object-style rows — the classification question the
own-content stream measured), (ii) 1.35 MB of `Global/Latest` byte-identical to
the samples — of which **1,333,338 B (99.0 %) is the Autodesk unit / spec /
parameter-group JSON corpus, product runtime data present identically in all
six samples and NOT regenerable from any public repository** (counsel item,
same class as `Formats/Latest`), the other ~13 KB shared format machinery, and
(iii) the inherited save-history lineage streams (advisory).  Not one byte of it
is *sample-project expression*; every blocking item is now a named
counsel / classification question, and the instrument correctly refuses to
certify until they are ruled on.  Whether the READER opens the candidate is
unmeasured — the four-file viewer queue in §7 answers it, one hypothesis per
file.

---

## 1. What genesis-2 built

### 1.1 The ADocument construction (the codec already existed — `rvt.adocument`)

`Global/Latest` = `u64 5 | u16 0x1c | ADocument object graph | u32 0`,
decoded and re-encoded byte-exactly on all six samples by the adoc-grammar
stream's codec.  Genesis-2 CONSTRUCTS a new value tree from G0's decoded graph
(`tools/genesis_assemble.py` §GENESIS-2) in four policy layers:

1. **Schema-typed dangling-id purge.**  A walk over every object body *in
   parallel with the archive class map* finds every value whose serialized
   type is `ElementId` / `Identifier` (14,652 leaves in G0's ADocument;
   10,175 of them reference deleted sample elements — the audit's "6,175" is
   the distinct count of these; a field-name heuristic misses e.g.
   `DBDrawingInfo.m_DBDrawingsIndex` and the `int64` id keys of
   `BasedOnTracker`, both caught here).  Registry entries keyed by / valuing a
   dangling id are dropped whole; positional and cross-sample-verified parallel
   arrays are nulled in place (positions carry meaning); scalar members are
   set invalid.  The fixed 241-slot AppInfo registry and every archive-indexed
   object (the graph's 180 weak-reference targets) are never touched.  Result:
   **zero dangling ElementId leaves; an independent i64 byte-window scan of
   the emitted payload against the union of every sample's element ids finds
   2 windows, both proven coincidences** (a `0x25` class id followed by zero
   padding; a timestamp fragment).
2. **Coherence.**  `ContentTable.m_ContentRecSet` (52 loaded-content records
   → 0) matches G0's empty `Global/ContentDocuments`; the project-browser
   expanded-node session state (sample view ids as plain integers) is emptied.
3. **Repopulation** (candidate / purity modes) — the registries are refilled
   to index EXACTLY our inventory, driven by registry SEMANTICS DERIVED from
   the five non-workshared samples and frozen in `G1_registry_maps.json`:
   the 72-position singleton table (position → class, **72/72 identical
   across samples** = compiled-in), the ElementTypeGroup enum (group → class,
   stable), the ElementTrackingData category → class maps (stable), the
   custom-element data-type GUIDs (from the MEP sample: exactly the four
   conductor-cell types our catalog has), and the parallel-container groups
   (equal-length in every sample).  These are format facts — no id, name or
   value is copied, only *which class a slot / group / category / GUID stands
   for*.  (`AppInfoSystemFamiliesNames` keys agree only 30/161 across samples
   = document-local allocations → the assembler allocates fresh keys 0..14 for
   our 15 system families instead of reusing any.)
4. **Authorship / caches.**  `NewItemNumber` (the sample's 'FOUNDATION-2700',
   'L1 wall frame hall 5' numbering memory), the worksharing per-user map
   ('liqi'), the temporary-view-properties user map ('macalis'), the NOBLE
   colour-fill / analysis caches (the room names), the `LB_Associations`
   link-reconcile dataset (102 sample element ids *as text*), the last-used
   parameter-value sets ('Concrete 10 MPa', '250 MPa'), the based-on tracking
   maps, the runtime ES schema table, the keynote DB-server descriptor — all
   emptied in the candidate.  `m_storedByRevitBuild` (the SAMPLE's 7-entry
   2018→2026 save lineage) becomes the single product constant every 2026 file
   carries as its last entry (candidate) or OUR authored string (purity probe).
   The Forge corpus is carried-and-flagged (candidate) or emptied (purity).

Every authored tree is re-encoded, re-decoded and asserted equal to what we
authored before a byte is written; every file must (and does) validate 0/0.

### 1.2 The rest of the pipeline v2

* **D1 (own-content) LANDED:** `build_our_content` = the own-content HOUSE
  STANDARD (`rvt.genesis.house_standard.build_catalog`, 234 elements, own values,
  Autodesk resource-identifier dispositions applied — `scrub="full"`; a
  `scrub="safe"` twin is built for bisection).  The manifest now states the
  emitted unit-format count (audit accounting error B6 retired) and
  `PROJECT_META` reads from the house standard.
* **Identity:** the own-save re-signs EVERY DocumentIncrementTable episode
  with our username (V32 mechanism) — the ledger's identity layer now passes on
  every file (it was the one identity violation in the audit's G0 run).
* **The registry maps** are re-derivable (`tools/genesis_assemble.py --only
  maps`, ~3 s) and shipped as data (`G1_registry_maps.json`).
* **Certification per file:** validator + the full ledger v2 (`--baseline
  all --streams --strings --identity`) + the byte scans + a string census;
  roll-ups `G1_validate.json` / `G1_provenance.json` / `G1_gate.json`.

---

## 2. The G1 file set (all `tools/rvt_validate.py` VALID, 0 errors, 0 warnings)

Validator (identical for every G1 file): `verdict: VALID (no errors);
warnings=0 info=2; layers=structure,consistency,semantic; streams 12;
pages_checked 12; gzip_members 8; partition_blocks 3; records 705;
elements_decoded 234; decode_failures 0; refs_checked 2940`.

```
OK   experiments/genesis/G0.rvt                errors=0 warnings=0
OK   experiments/genesis/G0_safe.rvt           errors=0 warnings=0
OK   experiments/genesis/G1a.rvt               errors=0 warnings=0
OK   experiments/genesis/G1_candidate.rvt      errors=0 warnings=0
OK   experiments/genesis/G1b.rvt               errors=0 warnings=0
OK   experiments/genesis/G1_candidate_safe.rvt errors=0 warnings=0
```

| file | authoring mode | Latest payload (before → after) | purge | byte scan (sample-id windows after) | our ids indexed | size |
|---|---|--:|---|--:|--:|--:|
| `G1a.rvt` | **max-safety** — coherence only: purge + ContentTable emptied + browser session state; NO repopulation, NO string edits; corpus + build lineage carried | 1,586,246 → 1,410,436 | 10,175 dangling: 8,892 entries dropped, 138 positional nulls, 22 scalars | 15 windows / 13 distinct — all coincidence-class round values (0x??00…); 0 typed leaves | 0 (by design) | 335,872 |
| **`G1_candidate.rvt`** | **candidate** — purge + registries repopulated over OUR inventory + caches emptied + product build constant; corpus CARRIED + FLAGGED | 1,586,246 → 1,360,923 | same purge | **2 windows** (both proven coincidences) | **214** (byte scan; of 234 — the rest are never-indexed classes) | 331,776 |
| `G1b.rvt` | **max-purity** — candidate + Forge corpora emptied + add-in / updater / service descriptors emptied + OUR "saved by" string | 1,586,246 → **26,102** | same purge | 2 windows | 214 | 258,048 |
| `G1_candidate_safe.rvt` | candidate ADocument over `G0_safe.rvt` (content `scrub="safe"`: asset descriptors / view-visibility policies at constructor defaults) | 1,586,246 → 1,360,923 | same | 2 windows | 214 | 331,776 |

Every ADocument re-decodes to exactly the authored tree (`self_decode_ok=True`);
G0's own-save and every G1 file assert `author/username = rvt-writer`, our
document GUID (= History entry 0), and the identity layer reports **no
violations**.

---

## 3. The v2 gate reading, per file (`G1_gate.json`, ledger `--baseline all --streams`)

| file | elements (union over 6 samples) | Global/Latest identical bytes | resource refs | identity | gate |
|---|---|--:|--:|:--:|---|
| G0 (baseline, house standard) | 135 cloned / 99 created | **1,586,254 / 1,586,254 (100 %, class `identical`)** | 7,457 | ok | FAIL |
| G1a | 135 / 99 | 1,386,156 / 1,410,444 (98.3 %, `modified-lineage`) | 7,405 | ok | FAIL |
| **G1_candidate** | 135 / 99 | **1,346,347 / 1,360,931 (98.9 %, `modified-lineage`)** | 7,400 | ok | **FAIL** |
| G1b | 135 / 99 | **11,776** / 26,110 (45.1 %, `modified-lineage`) | **107** | ok | FAIL |
| G1_candidate_safe | 140 / 94 | 1,346,347 / 1,360,931 | 7,445 | ok | FAIL |

**What each blocking population IS** (the candidate):

* **The 1,346,347 identical Latest bytes** = the Forge unit / spec /
  parameter-group JSON corpus (**1,333,338 B, byte-identical in ALL SIX
  samples** — the serialized image of Revit's installed *Unit Schemas*, product
  runtime data; docs/writer/latest-regions.md §2 — determination (c) "regenerate
  from a public open-source repo" is FALSE, and no viewer verdict yet exists on
  stubbing / blanking it) + ~13 KB of shared format machinery (the 241-slot
  registry frame, product-default settings values, enum-keyed shells,
  updater / propagation-filter registries).  **G1b is the proof**: with the
  corpora emptied the same instrument finds 11,776 identical bytes = the
  machinery alone.  Neither part is sample-project expression; the corpus is the
  counsel item beside `Formats/Latest` (C4-class), the machinery is the byte-level
  analogue of the element layer's classification question below.
* **The 135 cloned elements** = the machinery-class residual the own-content
  stream measured and registered as NO-FREE-CHOICE: 90 `GStyleElem` house
  object-style rows + 3 `CategoryElem`, 4 `Viewport` / 4 `DBDrawing` / 3
  `Viewer` frames, the 9 conductor `CustomElement` name-cells, 4
  `ConduitStandardType`, 3 `FontElem`, 3 `RbsCableTrayType`, 2
  `TextNoteAttributes`, 2 `BasePoint`, 2 `SketchPlane`, and one each of
  `DBViewProject`, `LightSchemeElement`, `AllProjectPhases`, `UnitsElem`,
  `ExtentElem`, `ModelClipBox`.  Of the 99 read-`created` elements, 69 have
  max-similarity < 0.40 everywhere and 17 < 0.25 (the genuinely authored
  payload).  This is the counsel / ledger-owner CLASSIFICATION decision — the
  assembler will not tune bytes to slip under a heuristic.
* **The 7,400 resource refs** = 7,363 Forge `autodesk.unit/spec/…` typeIds
  (7,292 in the corpus + our UnitsElem's REQUIRED lookup keys — house-standard
  disposition table), 36 `%1!s!` label-template TOKENS (our phrasing, Revit's
  substitution syntax — required), 1 corpus schema marker.  With the corpus
  emptied (G1b) the count is 107: the required tokens only.
* **Advisories (never blocking):** `Global/History` 95.7 % identical,
  `Global/PartitionTable` 100 %, `BasicFileInfo` 13.1 %, `Contents`
  prefix-shared — the inherited save-history lineage (§6, item 3).
* **Counsel item C4 (never counted):** `Formats/Latest` 496,597 B, Autodesk's
  serialized class model, byte-identical to all six samples.

**Verdict, stated plainly:** the v2 gate does not pass on any G1 file, and it
cannot pass on THIS instrument until (a) counsel rules on the Forge corpus and
the machinery-class question, or (b) engineering removes them (the corpus is
removable — G1b; the machinery classes are not, they are what a Revit document
IS).  What genesis-2 retired is everything that was *sample-project*
authorship: the sample's document object, its naming, its element registries,
its content records, its usernames — the byte-weighted picture in §4.

---

## 4. Byte-weighted provenance — then and now

Ledger v2, union of all six samples (`% of inflated stream bytes byte-identical
to a baseline`):

| file | all streams | excluding `Formats/Latest` (C4) | of which: Latest identical | ours |
|---|--:|--:|--:|--:|
| G0 (v1 assembler, audited) | 94.91 % | 93.44 % | 1,586,254 (100 %) | 4.94 % |
| G0 (v2, house standard) | 94.01 % | 92.29 % | 1,586,254 (100 %) | 5.87 % |
| G1a | 92.31 % | 89.87 % | 1,386,156 (98.3 %) | 6.38 % |
| **G1_candidate** | **92.61 %** | **90.18 %** | **1,346,347 (98.9 %)** | **6.53 %** |
| G1b | 78.01 % | **16.61 %** | 11,776 (45.1 %) | 19.46 % / 73.81 % ex-schema |

Reading the candidate honestly: of its 2,009,280 inflated bytes, 496,597 are
`Formats/Latest` (C4) and 1,333,338 are the Forge unit-schema corpus — the two
Autodesk PRODUCT corpora every 2026 file carries.  **Excluding both, the
identical-to-baseline share is 30,809 B = 17.2 % of the remaining 179,345 B, and
every one of those bytes is a lineage-fingerprint advisory (`Global/History`
17,408 + `Global/PartitionTable` 95 + `BasicFileInfo` 256 + `Contents`) or
shared ADocument machinery (~13,000)** — zero identical bytes in the element
records, the ElemTable, the content registry, the identity or metadata
streams.  G1b (both corpora + descriptors emptied) shows the floor the current
lineage-carrying design reaches: 16.61 % identical excluding the schema =
essentially the save-history lineage streams.  Retiring those needs the
minted single-episode lineage (§6 item 3) — deliberately NOT done in genesis-2
(it is the one change that couples History / DIT / the `Partitions/21` stream
name, and every reader-accepted file to date carried the inherited lineage).

---

## 5. What OUR document object contains — and what it lacks

### 5.1 Registries repopulated over our inventory (candidate; `G1_candidate_authoring.json`)

| registry (AppInfo) | populated with | rule |
|---|---|---|
| `CategoryTracking.m_gstyleData` / `.m_categoryData` | our **94 graphic-style rows** (the house standard) + **7 sub-category rows** | rows from our own GStyleElem (`m_categoryId`, id, `m_gstyleType`) / CategoryElem (`m_pCategory.m_parentCategoryId`, id) |
| `MaterialTracking` / `FillPatternTracking` / `LinePatternTracking` `.m_elemIdSet` | 13 materials / 5 fill patterns / 4 line patterns | per-class id sets |
| `DatumTracking.m_elemIdSet` | our 2 levels | datums |
| `PhaseFilterTracking.m_elemIdSet` | our 5 phase filters | |
| `UniqueElementsTracking.m_elemIds` (POSITIONAL) | `[2]=ProjectInfo`, `[59]=ElectricalSetting`, `[66]=CableTraySizesElem`, `[67]=ConduitSizesElem`, `[74]=AllProjectPhases`; every other slot `-1` | position → class table, 72/72 stable across samples |
| `UnitsTracking.m_unitsElemId` / `SiteMgr.m_trueNorthId` | our UnitsElem / TrueNorth | |
| `DBViewInfo` | project view id; index of our **4 views**; **4 sun-settings**; 0 templates; no system-navigator view | the view index |
| `DBViewTypesForNewLevel` | our 2 plan view types | |
| `DBDrawingInfo.m_DBDrawingsIndex` | our 4 drawings | |
| `LevelPlanViewTracking` | 2 levels → 2 plan views (`DBViewPlan.m_genElemId` = its level) | |
| `SketchPlaneInfo.m_curSPRecs` | our 2 plan-view sketch planes (`m_ownerDBViewId`) | |
| `ElementTrackingData.m_symbols` / `.m_elems` | our types filed under their built-in category (Walls / Roofs / Ceilings / Foundations / Conduits / Cable Trays / Wires / Distribution systems / Conduit standards; load classifications / demand factors / geolocations / base points / levels) | category → class map, stable across samples |
| `SymbolIdMgr.m_defElementTypeMap` | **11 defaults**: BasicWallType→2, RoofAttributes→3, CompoundCeilingType→6, LevelAttributes→9, Level→15, RbsWireType→102, RbsVoltageType→103, RbsDistributionSysType→104, RbsCableTrayType→122, RbsConduitType→123, ConduitStandardType→124 | ElementTypeGroup enum, single-group type classes only (FloorAttributes 4/5, TextNoteAttributes 12/139, DBViewType ×21 groups skipped as ambiguous; GStyleElem 41 / MaterialElem 42 not type defaults) |
| `SymbolIdMgr.m_defCatSymIds` (category → default family symbol, parallel arrays) | all `-1` (we place no families) | positional-null |
| `CustomElementTracking.m_dataTypeToElementIdsMap` | 4 data types → our 9 conductor cells (Material / TemperatureRating / InsulationMaterial / Size GUIDs) | GUID map derived from the MEP sample; matched by first-cell class |
| `AppInfoSystemFamiliesNames.m_idMap` | 15 system families (fresh document-local keys 0..14) over our types | key set NOT reusable across documents (30/161 agree) |
| `m_storedByRevitBuild` | `["Revit 2026 2026 (2026.000) : 20250227_1515(x64)"]` — the last entry of EVERY 2026 file (product constant, like BasicFileInfo's build field) | counsel C1 (G1b carries our own string instead) |
| `ContentTable.m_ContentRecSet` | `[]` (matches the empty ContentDocuments) | coherence, every mode |
| `ESSchemaStorage` | Forge corpora **carried + flagged** (candidate) / **emptied** (G1b); `m_schemaUsageMap` `[]` (the 2 inherited entries were the sample's add-in schemas; racbasic proves 0 is a valid state) | §3 |

Everything the purge left with no counterpart of ours is empty (numbering
memory, worksharing / temporary-view user maps, based-on tracking, external
shared-parameter map, warnings, room / structural / MEP-space trackers, plan
topologies, MEP per-level layout offsets, open-window states, ADocWarnings…)
— the state a document that never had those elements is in.

### 5.2 What the candidate LACKS — the concrete backlog for the constructor streams

The registries expose it exactly (`missing_singletons` in the authoring
report): the sample's `UniqueElementsTracking` had **72 populated singleton
slots; our skeleton fills 5**.  The other 67 name the document-settings
elements every Revit project carries and our skeleton does not yet construct —
e.g. `AreaSettingsElem`, `WallJoinDefaultSetting`, `AutoJoinTracker`,
`GCSTracker`, `StructSettingsElem`, `ReinforcementSettings`,
`RbsPipe/Duct/Wire/CableTray/Conduit SettingsElem` + `*SizesElem`,
`MEPSystemTracker`, `AllProjectRevisions`, `KeynoteTable`,
`AssemblyCodeTable`, `InitialViewSettings`, `HubsTracker`,
`AnalyticalToPhysicalRelationManager`, `RouteAnalysisSettings`,
`MEPHiddenLineSettingsElem`, `ReconcileBrowserSettingsElem`, ten
`ConceptualSurfaceType`s (full list in `G1_candidate_authoring.json`).
G0 also lacks the `PenWidthTableElem` (element id 2 in EVERY sample),
`BrowserOrganization` elements and a system-navigator view.  **If the id
purge is not what blocked G0, this omission is the next suspect** — and it is
the systemtypes / skeleton streams' queue, not the assembler's (no
constructors exist yet).

---

## 6. The residual list — every item classified (nothing hidden)

1. **The Forge unit / spec / parameter-group corpus** (candidate: 1,333,338
   B carried inside `ESSchemaStorage`) — Autodesk product runtime data,
   identical in every 2026 file, present in the customer's own Revit install;
   NOT regenerable clean-room from a public repository (landmarks §2.4).
   *Counsel item, C4-class* (options: emit the identical product-constant
   bytes / source from the customer's licensed install at generation time /
   ship empty if the reader tolerates it → **G1b answers the last question**).
2. **`Formats/Latest`** — Autodesk's serialized class model, 496,597 B,
   byte-identical to every 2026 file. *Counsel C4* (unchanged from G0).
3. **The inherited save-history LINEAGE** — `Global/History` (1,018 episodes:
   the sample document's 1,017 + our genesis episode 0), `DocumentIncrement
   Table` (23 records, structure inherited, **all usernames now ours**),
   `Global/PartitionTable` (workset GUID) / `Contents` creation GUID, and the
   partition stream NAME `Partitions/21` (21 = the sample's increment counter −
   1).  *Advisory fingerprints* (chain of custody), not expression.  Retiring
   them = minting a single-episode lineage (`skeleton.minimal_history/
   _increment_table/_partition_table/_contents` exist), which couples the four
   streams AND the partition stream name (`Partitions/0`?) — the one lineage
   coupling no reader-accepted file has exercised; deliberately deferred as the
   next dedicated probe rather than folded into the ADocument question.
4. **135 machinery-class element clones** (§3) — the counsel / ledger-owner
   classification decision on Revit product-default machinery (object-style
   rows, view frames, name-only cells).  Population: `G1_candidate_provenance.json`.
5. **Required-token identifiers in OUR records** (own-content disposition
   table): Forge unit typeIds in our UnitsElem, the `%1!s!` substitution
   token, `'Basic Wall'`, BuiltIn enums, the font name `Arial`, the partatom
   XML namespace, the version marker / build string, and the save-unit banner
   `'Data generated by Autodesk® Revit®'` inside `Partitions/21` (own-content
   §5 — probe requested).  *Counsel list*, argued as interface tokens.
6. **Two coincidental id-shaped byte windows** in the candidate's Latest
   (`0x250000` = a class-id `0x25` + zero padding; a timestamp fragment) —
   documented so a future audit does not mistake them for references.

---

## 7. Files for the orchestrator to VIEWER-TEST — ordered by what each proves

None has a viewer verdict; every one is validator-VALID and re-decodes 100 %.
Test after the reader-tolerance controls the latest-probes stream queued
(P0_control / G0_A0 = "our Latest re-serialization is accepted").

| # | file | proves if it PASSES | if it FAILS |
|--:|---|---|---|
| 1 | `experiments/genesis/G1a.rvt` | **the central hypothesis:** a document object with ZERO dangling ids opens where G0 (6,405 dangling) failed → the id purge is the fix and the rest is authorship. Only mandatory coherence changes were made (purge + empty content registry + browser session state) — the smallest step from the accepted shape. | the constructed-skeleton omission (§5.2, the 67 missing settings singletons / no PenWidthTable) or the re-serialization itself is the blocker → run G0_A0 (pure re-encode control) to split those two |
| 2 | **`experiments/genesis/G1_candidate.rvt`** | **OUR document object is accepted:** registries indexing exactly our inventory, no sample names / caches / content records, product build constant — THE genesis-2 base of record | with G1a PASSING: one of the repopulated registries has the wrong shape (bisect via the `--modes` of the tool: build candidate-minus-one-registry variants) |
| 3 | `experiments/genesis/G1b.rvt` | the Forge unit-schema corpus is NOT load-bearing → item 1 above collapses (ship empty), the C4-class corpus question is moot, the last 1.33 MB of Autodesk bytes leaves the genesis base | with the candidate PASSING: the corpus IS load-bearing → keep carrying it (product data) or source it from the customer's install; the counsel item stands |
| 4 | `experiments/genesis/G1_candidate_safe.rvt` | (only if #2 FAILS) the content-layer blanking (asset descriptors / view visibility policy — own-content dispositions) is what the reader rejects, not the ADocument work | with #2 also failing: the fault is above the content layer |

For the record: `G0.rvt` was rebuilt this session (house-standard content,
username-scrubbed lineage) — the audited G0 verdict (PROCESSING FAILED) refers
to the v1 file; the new G0 differs in content values and identity only, and
still carries the verbatim ADocument, so its viewer verdict (if re-tested) is
expected to be the same FAIL.  `G0_safe.rvt` is the `scrub="safe"` content
twin.

---

## 8. Reproduction

```
.venv/bin/python tools/genesis_assemble.py                  # everything (~45 s): G0 ladder + G0_safe + the G1 set + reports
.venv/bin/python tools/genesis_assemble.py --only g1        # the G1 set from the existing G0.rvt / G0_safe.rvt (~30 s)
.venv/bin/python tools/genesis_assemble.py --only g1 --no-ledger   # same, without the ledger v2 (~2 s)
.venv/bin/python tools/genesis_assemble.py --only maps      # re-derive G1_registry_maps.json from the samples (~3 s)
.venv/bin/python tools/genesis_assemble.py --only content   # build + verify OUR content only
.venv/bin/python tools/rvt_validate.py experiments/genesis/G1_candidate.rvt
.venv/bin/python tools/provenance.py experiments/genesis/G1_candidate.rvt --baseline all --streams
.venv/bin/python -m pytest tests/test_genesis_assemble.py tests/test_genesis2_adocument.py -q   # 20 tests
```

Determinism: fixed timestamp (2026-08-03T12:00:00Z), fixed id start; the only
non-deterministic values per build are the fresh document / episode GUIDs.

---

## Appendix A — the G0 element ladder (rebuilt, house-standard content)

| rung | operation | bytes | validator | ledger (single baseline rst) |
|---|---|--:|---|---|
| R10b (base) | deepest v2 reduction of rstbasic | 1,437,696 | VALID | — |
| G0a | + our 234 elements | 1,454,080 | VALID (1 warn = base's known ES gap) | sample 3,022 · cloned 132 · created 102 · 14 family docs |
| G0b | − maximal-GC Autodesk lineage | 983,040 | VALID | sample 165 · docs 14 |
| G0c | − all embedded family documents | 495,616 | VALID | sample 165 · docs 0 |
| G0d | − the unpinned residue | 385,024 | VALID | sample 0 · cloned 126 · created 108 |
| G0 | + own-save (our episode / GUID / identity / EVERY episode username ours) | 380,928 | VALID | sample 0 · cloned 126 · created 108 |

The v1 status document (this file's previous version) — the G0 gap analysis,
the strategy rationale (top-down hollow shell), the D1/D2 diffs and the E5
retraction of the "R4s viewer PASS" claim — remains valid history; its §4.2
"the ADocument is the one stream no encoder exists for" is retired by this
session.

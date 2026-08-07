# `Global/Latest` = the serialized `ADocument` object graph — DECODED (grammar + field map)

Stream: **adoc-grammar** (2026-08-03). Module: `src/rvt/adocument.py`
(`python -m rvt.adocument [--json] [--proofs] [--fields]`). Tests:
`tests/test_adocument.py` (14). Record: `docs/inbox/adoc-grammar.md`.
Supersedes the wave-1 framing pass `docs/streams/03-global-latest.md`
(its region map / "compressed continuation" hypothesis are RETIRED, see §6).

## 0. Result

The hypothesis was correct in its strongest form. `Global/Latest` is the
8-byte per-stream prefix `u64 5` + **one object graph serialized by the very
same schema-directed codec as the element records**, rooted at class
`ADocument` (0x1c). Nothing in the stream is compressed, externalized to a
landmark region, or written by a container class the decoder lacked.

```
logical Global/Latest (inflated)  =
    u64   5                                   (per-stream prefix, rvt.stream_encoders.global_prefix)
    u16   0x001c                              class id ADocument      \ identical framing to an
    ...   ADocument object                        > element record payload
              parent-first fields                                        / {u16 class_id, object}
              breadth-first DEFERRED pointer bodies (one FIFO queue for
              the whole document: ContentTable, AppInfoManager,
              StyleSettings, SteelModelInfo, NOBLE_SecondaryDataStorage,
              ExServicesUsed, then their owned objects, ... 500-1,500 bodies)
    u32   0                                   constant trailer (all six; §6)
```

`rvt.objects.ObjectDecoder` decodes it with exactly **two hooks**
(`ADocumentDecoder`, a subclass — `objects.py` untouched):

1. **archive-object-index (pid) seed = {1}**, not `{1, 2}`: the document
   itself is archive object #1 (every `m_pHostDocument`/`m_pDoc`/`m_pADoc`
   weak reference in the graph is `u32 1`), so the FIRST indexed sub-object
   gets pid 2 (`FamilyMgr`) — whereas in an element record the root
   *element* is pid 2 and the document the implicit pid 1. With the element
   seed the pid-2 token reads as a back-reference and the decode derails at
   `AppInfoManager.m_appInfoArr[0]`.
2. **lifted container cap** (`ADocReader`, 64 M vs 2 M):
   `SteelModelInfo.m_steelModelLatest` is a `char[]` steel-model blob of
   2,085,221 bytes in dach.

| sample | payload | consumed | coverage | errors | deferred bodies | trailer | decode→encode |
|---|--:|--:|--:|--:|--:|---|---|
| racbasic | 1,500,644 | 1,500,640 | 100.0000 % | 0 | 565 | `00000000` | **byte-exact** |
| rstbasic | 1,586,246 | 1,586,242 | 100.0000 % | 0 | 773 | `00000000` | **byte-exact** |
| racadv | 1,645,873 | 1,645,869 | 100.0000 % | 0 | 541 | `00000000` | **byte-exact** |
| rstadv | 1,704,781 | 1,704,777 | 100.0000 % | 0 | 613 | `00000000` | **byte-exact** |
| rme | 4,655,284 | 4,655,280 | 100.0000 % | 0 | 719 | `00000000` | **byte-exact** |
| dach | 4,762,933 | 4,762,929 | 100.0000 % | 0 | 1,482 | `00000000` | **byte-exact** |
| **G0.rvt** | 1,586,246 | 1,586,242 | 100.0000 % | 0 | 773 | `00000000` | **byte-exact** (= rstbasic) |

"consumed" excludes only the trailing `u32 0`. `encode_latest(decode_latest(p)) == p`
byte-for-byte on all seven, using the existing `rvt.encode.ObjectEncoder`
unchanged — **the ADocument encoder already exists**; what the encoder
stream owns is AUTHORING our own value tree (§8). Decode time 0.05 s (rac)
– 1.2 s (dach). `Formats/Latest` remains the schema source; no other stream
is read.

## 1. The primitive/token codebook (unchanged from KNOWLEDGE)

AString `u32 count + UTF-16LE`; ElementId `i64` (−1 invalid); GUID 16 raw
(mixed-endian); class ref `u16` schema type id; owned/poly pointer
`i32 pid [+ u16 class]` (0 null, −1 anonymous, >0 new archive index, seen
pid = back-reference), body deferred breadth-first; weak pointer `u32`
archive index; containers `u32 count + elements`; value classes inline
(ElementId/XYZ/UV/GUIDvalue flattened). Positive pids are assigned
**sequentially 2, 3, 4, … in encounter order** (rstbasic: 180 indexed
objects, pids 2..181 exactly; weak refs target 1 ×251, 152 ×10, 173 ×3 —
weak references to specific AppInfo objects by archive index).

## 2. Field map — the 19 top-level `ADocument` members (schema order)

`FIELD_MAP` in the module is the data form (annotated per file by
`ADocument.field_holdings()`). Byte shares are of the whole stream; the
"deferred bodies" hang off owned pointers and land later in the FIFO queue.

| # | field | serialized as | holds (measured) | body location |
|--:|---|---|---|---|
| 1 | `m_elemTable` | `i32 0` (null ptr) | element table | **Global/ElemTable** |
| 2 | `m_appInfoArr` | `u32 0` (empty container) | nothing — app-infos hang off #5 | — |
| 3 | `m_oContentTable` | `(−1, ContentTable)` + body | `ContentTable{m_pHostDocument weak 1, m_ContentRecSet[]}` = GUID-keyed registry of loaded family/content docs: `ContentKey` GUID, author `"Autodesk Revit"`, creation/mod/user-mod episode ids, per-episode load counts (52 rst / 163 rac / 305 rme / 1,243 dach entries; 0.3–2.6 % of the stream) — this is the wave-1 "GUID-keyed map object" | documents' BYTES in **Global/ContentDocuments** |
| 4 | `m_pHostDocument` | `u32 1` (weak → self) | the document = archive object 1 | — |
| 5 | `m_pAppInfoManager` | `(−1, AppInfoManager)` + body | `{m_pADoc weak 1, m_appInfoArr[241]}` = the **fixed 241-slot AppInfo registry** (§3) — 93–98 % of rst/rac streams (1.5 MB), 34.8 % of rme, 45.6 % of dach | inline |
| 6 | `m_pStyleSettings` | `(−1, StyleSettings)` + body | 9 owned pointers to the style TABLE objects (`CategoryTable`, `MaterialTableNew`, `PenWidthTableGetter`, `LinePatternTable`, `FontTableNew`, `FillPatternTable`, `TilePatternTable`, `AppearanceAssetTable`, `StructuralPropertySetTable`) whose bodies here are ~empty stubs (90 B total); the style *elements* live in Partitions/<N> — the wave-1 "typed null-pointer run" | inline |
| 7 | `m_pHistory` | `i32 0` | save history | **Global/History** |
| 8 | `m_pSteelModelInfo` | `(−1, SteelModelInfo)` + body | Advance-Steel bridge: ext-model GUID, STC/latest hash strings, and the whole steel model as `char[]` (2,085,221 B in dach ≈ 44 % of that stream; empty in the other five) | inline (blob) |
| 9 | `m_pPartitionTable` | `i32 0` | workset table | **Global/PartitionTable** |
| 10 | `m_oNobleSecondaryData` | `(−1, NOBLE_SecondaryDataStorage)` + body | NOBLE analysis cache: `m_appInfoData` (`"NobleDocWarnings"` → `NobleDocWarnings` posted-warning list), `m_data` = `SecondaryDataId → {…}` entries (`ColorFillSecondaryData` — colour-fill results **carrying the room/area name strings**; rme adds `MEPNetworkSecondaryData` (521 KB), `HvacSystem`/`PipingSystem*SecondaryData`), `m_primary2SecondaryDataIdMap` (3,769 entries in rme = 2.26 MB), invalidation queues; 0.6–8 % of most streams, **64.5 % (3.0 MB) of rme** | inline |
| 11 | `m_ownerFamilyId` | `i64` | −1 (project) | — |
| 12 | `m_ownerFamilyContainingGroupId` | `i64` | −1 | — |
| 13 | `m_devBranchInfo` | `i32 1, i32 2662` | DevBranchInfo{branch 1, syncVersion **2662**} = ADocument's schema version (the wave-1 `01 00 00 00 66 0a` at 0x44) | — |
| 14–16 | `m_groupFile`, `m_corruptDocument`, `m_bIsCoreDocument` | 3 × `u8` | false, false, false | — |
| 17 | `m_executedUpgrades` | `u32 0` | empty GUID list | — |
| 18 | `m_storedByRevitBuild` | `u32 n + AStrings` | "saved by" build history, oldest first (7–12 strings, 2018 → `Revit 2026 ... 20250227_1515(x64)`) | — |
| 19 | `m_oExServicesUsed` | `(−1, ExServicesUsed)` + body | `m_arrServiceInfo` = external-service usage records — **empty in all six** (the wave-1 "GUID-keyed map (class 0x644, 163 entries)" was really field #3's ContentTable; 0x644's body is 4 bytes) | inline |

Wave-1 prologue mapping confirmed/corrected token-by-token: 0x1c is the
`u16` class id (not a `u32` type tag); `m_elemTable` is a NULL pointer
(4 zero bytes); `m_appInfoArr` a zero count; the five `(−1, cls)` tokens are
in exact schema order `ContentTable(0x3a7)`, `AppInfoManager(0x1a0)`,
`StyleSettings(0x1066)`, `SteelModelInfo(0xff8)`, `NOBLE_SecondaryDataStorage
(0xae9)`; the two nulls between them are `m_pHistory` and `m_pPartitionTable`.
The wave-1 "11 tokens vs 10 fields" puzzle was the extra `u32 1` = the weak
`m_pHostDocument`.

## 3. The AppInfo registry (`AppInfoManager.m_appInfoArr`)

A **fixed 241-slot container of owned pointers** (`u32 241` = the wave-1
constant `0xf1`, identical in every file). Slot index = compiled-in
registration order; the wave-1 "u32-keyed table, keys 2..181, u16 value" was
this container: each non-null slot serializes `i32 pid, u16 class` (the
sequential "keys" are the archive pids; the "u16 values" are class ids) and
each null slot serializes `i32 0` (the wave-1 "0..7 zero u32s" between
entries = runs of null slots). `APPINFO_SLOTS` in the module is the canonical
table (majority class per slot):

* **227 / 241 slots hold the identical class in all six files**; the 14
  differing slots (`APPINFO_OPTIONAL_SLOTS` = 23, 66, 83, 106, 110, 111, 141,
  165, 177, 181, 183, 191, 201, 217) are present-or-null, never a different
  class (lazily created edit-mode managers / caches: `WallJoinEditMgr`,
  `PasteEditModeMgr`, `XRayContext`, `FamSymGlobalComputedSymbolCache` …).
* **168 slots are populated in every file** (the mandatory-looking set),
  **59 are never used** in the corpus, 172–180 populated per file.
* Slot 0 = `FamilyMgr` (loaded-family surrogate ids), 1 `SketchEditMgr`,
  2 `SymbolIdMgr` (default symbol per category — `CategoryToIdMap`),
  3 `DBViewInfo`, 5 `SketchPlaneInfo`, 17 `NewItemNumber` (**last-used
  sheet/assembly numbering names — 'FOUNDATION-2700', 'L1 wall frame hall
  5' live here**), 26 `ADocWarnings`, 28 `CategoryTracking`, 32
  `ElementTrackingData`, 42 `RoomTracking`, 87 `AbsLayoutAppInfo`
  (`m_strWireSizeTableFilePath = "WireSizes.xml"`, MEP layout offsets), 154
  `WorksharingDisplaySettingsTracking` (per-user map — the sample user
  'liqi'), **158 `ESSchemaStorage`** (§4), 168 `NumberingAppInfo`, 197
  `AppInfoElementsAssociations` … (full table in the module / JSON dumps).

Where the byte weight is (rstbasic): `ESSchemaStorage` 1,333,818 B (84.1 %),
`CategoryTracking` 53,528, `AppInfoElementsAssociations` 33,526,
`NumberingAppInfo` 29,071, `SymbolIdMgr` 19,146, `ElementTrackingData`
12,948, `ExternalParamTracking` 11,204, `SketchPlaneInfo` 6,985 …

## 4. The Forge / ES schema corpus (`ESSchemaStorage`, slot 158)

```
ESSchemaStorage v3
  m_storedForgeSchemas      container< std::pair<AString,AString> >   893 pairs, 796,204 B
  m_schemaUsageMap          container< std::pair<GUIDvalue,SchemaUsageInfo> >
  m_storedParameterSchemas  container< std::pair<AString,AString> >   422 pairs, 537,134 B
  m_dirty                   uint
```

* `m_storedForgeSchemas` = Autodesk **Forge unit corpus** as plain
  `(typeid, json)` UTF-16LE strings (`autodesk.unit.symbol` 433, `.unit` 350,
  `.quantity` 76, `.factor.prefix` 20, `.dimension` 7, `.factor` 7; declared
  893 = the wave-1 `u32 893`). `m_storedParameterSchemas` = the **spec /
  parameter-group corpus** (`autodesk.spec.aec.structural` 92, `.revit.group`
  75, `.spec.aec.hvac` 64, `.parameter.group` 50, `.spec.aec.electrical` 45,
  `.piping` 33 …). **Both corpora are byte-identical in all six files**
  (a Revit-2026 shipped constant, like `Formats/Latest`) — the audit's
  "78.5 % Forge JSON" region, decoded to the byte. **There is no
  compression**: the wave-1 "0xff-flagged length prefixes / LZ literal
  runs / compressed continuation" were mis-framed AString boundaries; the
  216 non-ASCII characters are genuine unit symbols (baht ฿, °, µ).
* `m_schemaUsageMap` = the **runtime Extensible-Storage schema table**:
  `GUID → SchemaUsageInfo{m_contentDocsKeys, m_schema = full ESSchema
  (name, vendor, documentation, m_fields[ESField{fieldName, fieldTypeName,
  ForgeTypeId spec, containerType, entryIndex, subSchemaGUID}], access
  levels, applicationGUID)}` — 0 (rac), 2 (rst/rme), **175 in dach**. This is
  the schema source the object-decoder's remaining `ESEntity.m_blob`
  failures need (cross-stream note filed).

## 5. Where the sample's own content sits (the audit's exhibits, located)

| audit exhibit | field path |
|---|---|
| 6,175 (measured: **6,342 distinct / 9,738 total**) element-id references, ALL dangling in G0 | 99.7 % under `m_pAppInfoManager` — the per-category / per-kind ELEMENT REGISTRIES: `CategoryTracking.m_gstyleData/m_categoryData` (2,799 distinct), `ElementTrackingData.m_elems/m_symbols[].m_elemIdSet` (1,246), `StructuralElemSetTracking.m_elemIdSet` (490), `ExternalParamTracking.m_keyDataMap` (467), `NumberingAppInfo` (365), `AppInfoSystemFamiliesNames.m_idMap` (364), `ParamBindingTracking` (209), `BasedOnTracker` (159), `LinePattern`/`AppearanceAsset`/`FillPattern`/`MaterialTracking.m_elemIdSet` (150/131/116/93), `SketchPlaneInfo` (79), `UniqueElementsTracking` (72), `CustomElementTracking` (61), `FamilyMgr.m_arrLoadedFamilyInfo[].m_surrogateId` (50), `DatumTracking` (46), `RoomTracking.m_roomIds/…` (31), `SymbolIdMgr` (12) … + `ContentTable` (14) + NOBLE colour fills (45) |
| room names ('Hall', 'Kitchen & Dining', 'Master Bedroom' …) | `m_oNobleSecondaryData → NOBLE_SecondaryDataStorage.m_data[].second.m_oData → ColorFillSecondaryData.m_colorFillResults[].m_paramStorage.m_str` (colour-fill result CACHES) |
| sheet 'FOUNDATION-2700', assembly 'L1 wall frame hall 5' | `AppInfoManager.m_appInfoArr[17] → NewItemNumber.m_items[].m_lastItemName` (last-used numbering names) |
| Autodesk employee/sample user 'liqi' | `WorksharingDisplaySettingsTracking.m_userToSettingsMap[].first` |
| 'WireSizes.xml', 'Number of Circuits' | `AbsLayoutAppInfo.m_strWireSizeTableFilePath` etc. |
| the Forge unit/spec/parameter JSON corpus (1.33 MB) | `ESSchemaStorage.m_storedForgeSchemas` + `.m_storedParameterSchemas` — a shipped constant, identical in all six (§4) |
| 52–1,243 `"Autodesk Revit"` vendor strings | `ContentTable.m_ContentRecSet[].m_author` (loaded-content registry; **G0 still lists 52 content records although G0's Global/ContentDocuments is the empty form** — an inconsistency the assembler inherited from the template's ADocument) |

## 6. Regions not covered by the structured decode — NONE

Every byte except the trailing constant is consumed by named schema fields.

| region | what it is | status |
|---|---|---|
| trailing 4 bytes `00 00 00 00` (all six + G0) | `u32 0` after the object graph | UNKNOWN semantics, constant. `[hypothesis]` a trailing element/graveyard count or the guid-count of a virtual trailer field; the encoder appends it verbatim. Cheap viewer test: it is preserved by construction. |
| `SteelModelInfo.m_steelModelLatest` (dach, 2,085,221 B) | `char[]` container | structurally decoded; contents = an OPAQUE embedded Advance-Steel model blob (not Revit's format). Empty in non-steel files; author as `[]`. |
| `StructuralConnectionStyleInfo.m_(detailed)PreviewImagePng` (dach, 30 KB) | `char[]` | PNG images (magic `89 50 4e 47`). |

Nothing else is opaque: strings, ids, doubles, GUIDs and enums with schema
names throughout. The three "unknowns" above are semantic labels on
already-decoded fields, not undecoded bytes.

## 7. Retired wave-1 claims (`docs/streams/03-global-latest.md`)

* "middle 30–60 % = a **compressed** units dictionary (LZ, 0xff-flagged
  literals), decoder not written" → FALSE; it is `ESSchemaStorage`'s plain
  AString pairs, decoded to the byte (§4). Nothing in the stream is
  compressed below the outer gzip. (The `Formats/Latest` "corrupted tail"
  the note linked to this is unrelated and was itself the page-framing
  artefact.)
* "GUID-keyed map = external-service / add-in registry (class 0x644,
  m_oExServicesUsed)" → it is `ContentTable.m_ContentRecSet` (loaded family
  content, field #3); `ExServicesUsed` is field #19 and is empty everywhere.
* "u32-keyed typed-object table, u32 0xf1 = PostedWarning?, keys = a
  registration index" → the 241-slot AppInfo container; the "keys" are
  archive pids, `0xf1` = 241 = its count (§3).
* "typed null-pointer run of ADocument fields" → `StyleSettings`' nine
  table pointers (field #6's deferred body).
* "dach has no units dictionary" → dach carries the identical Forge corpus
  plus 175 ES schemas and a 2 MB steel-model blob.
* Prologue `1c 00 00 00` "u32 type id" → `u16 0x1c` class id + the first
  field's null-pointer word; the framing is byte-identical to an element
  record payload.

## 8. Consequences for the writer (feeds the encoder stream / G1a)

1. **G1a "ADocument encoder — no encoder exists; the biggest engineering
   block" is technically CLOSED.** `encode_latest(value)` +
   `write_with_latest(src, out, payload)` produce accepted-shape streams;
   an ADocument we build from scratch (all pointers null, empty
   containers, our own build string) already encodes and round-trips
   (`test_minimal_authored_document_roundtrip`, 137 bytes). What remains is
   CONTENT authorship + acceptance testing, not a codec.
2. Our own document object = `FIELD_MAP` with: externalized members
   null/empty (they already are); `m_storedByRevitBuild` = our string;
   `ContentTable` empty; NOBLE empty; `AppInfoManager` with the 168
   mandatory slots holding EMPTY registries (all their `m_elemIdSet`s /
   maps `[]` or referencing only OUR ids), `ESSchemaStorage` per the counsel
   answer (empty vs. regenerated from Autodesk's published Forge package),
   `SteelModelInfo`/`ExServicesUsed` empty.
3. The acceptance UNKNOWN is what Revit tolerates as empty — resolved by
   the proof ladder below, one hypothesis per rung.

## 9. Viewer-certification queue (files left on disk, ordered by what each proves)

All built on `experiments/genesis/G0.rvt` (whose ADocument is
byte-identical to the rst sample's), all `tools/rvt_validate.py` **VALID,
0 errors, 0 warnings**; each rung re-decodes to exactly the tree we
authored (`self_decode_ok=True`). Rebuild with
`python -m rvt.adocument --proofs`.

| file | proves | if it FAILS |
|---|---|---|
| `experiments/genesis/latest/G0_A0.rvt` | control — Global/Latest **re-serialized + recompressed by us**, payload byte-identical (isolates our Latest writer path; near-certain PASS given V15) | our Latest re-framing is wrong (contradicts V15) |
| `.../G0_A1.rvt` | **an AUTHORED ADocument** (different bytes AND length): `m_storedByRevitBuild` = one string of ours → Revit accepts a document object we serialized with modified content — the G1a gate proof | the reader validates the build-string history / lengths elsewhere |
| `.../G0_A2.rvt` | A1 + **Forge JSON corpora emptied** (`ESSchemaStorage` 893+422 pairs → 0; stream 1.59 MB → 252 KB, drops the audit's exhibit-A 1.33 MB) → whether Revit REQUIRES the shipped unit/parameter schema corpus (counsel question §D-3(a) becomes moot on a PASS) | corpus is load-bearing → regenerate it from Autodesk's published Forge schema package instead of embedding the sample's copy |
| `.../G0_A3.rvt` | A2 + **sample naming scrubbed** (`NewItemNumber.m_items`, worksharing per-user map, NOBLE colour-fill caches with the room names → empty) → no sample project strings remain in Latest | the numbering/NOBLE caches are validated on load → author minimal defaults instead of emptying |
| `.../G0_A4.rvt` | A3 + **`ContentTable.m_ContentRecSet` emptied** (the 52 `"Autodesk Revit"` content records G0 inherits despite having no content documents) → the content registry can be authored empty for a family-free document | the registry must mirror ElemTable family symbols → reconcile with the genesis assembler |

Not yet built (needs the encoder stream's per-class rules): **A5 — the
tracking-registry purge** (drop the 6,342 dangling ids from the ~60 registry
AppInfos so every referenced ElementId exists in G0's 205-row ElemTable;
generic rule: every container element whose flattened `ElementId` value
type is 0x14 and whose id ∉ ElemTable is removed / the map entry dropped),
and **A6 — the minimal document** (all 168 mandatory slots present but
empty vs. all-null AppInfoManager).

## 10. Confidence

Grammar / framing / codec / field map: **[verified]** — byte-exact
decode→encode on all six samples + G0, and every claim above is a named
schema field, not a heuristic. Slot table: **[verified]** across six
(constancy 227/241). Semantics of the trailing `u32 0`, of the 175 ES schema
usage GUID keys, of `m_dirty`, and which AppInfo registries Revit
re-derives on load vs. requires: **[hypothesis / open]** — resolved by the
A-ladder viewer results, not by more decoding.

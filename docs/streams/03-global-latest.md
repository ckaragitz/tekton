# `Global/Latest` — the serialized `ADocument` graph (framing pass)

Agent: `global-latest` · Tool: `src/rvt/global_latest.py` (run with the venv
python; default runs racbasic + rstbasic, `--all` runs the six samples) ·
Companion: `docs/streams/01-schema-a.md` (class ids / `ADocument` field list).

This is a **framing** pass: it fixes the primitive encodings, walks the head
of the stream structure-by-structure, pins the big landmark regions, and
prints a byte-region map. It is not a full object-graph decode.

## 0. Summary of what is now known

- `Global/Latest` = OLE stream = **8-byte prefix `05 00 00 00 00 00 00 00`**
  (u64 LE `5`, identical in all six samples — meaning still open) + gzip
  member (10-byte header, raw deflate, corrupt trailer) + a short un-decoded
  post-deflate tail (106–797 bytes, per file). Inflated size 1.5–4.8 MB.
  `[verified]`
- The inflated payload is the `ADocument` object written field-by-field
  (schema: `Formats/Latest`, class `ADocument`, type id 0x1c, version 2662),
  followed by the objects it owns. The **first 0x53 bytes are byte-identical
  in all six files** and contain typed-pointer tokens whose class ids resolve
  to `ContentTable` (935) and `AppInfoManager` (416). `[verified]`
- Primitive encodings established (evidence in §2): **AString = u32 char
  count + UTF-16LE**, **ElementId = int64 LE (invalid = -1)**, **GUID = 16
  raw bytes**, **class reference = u16 schema type id**, **typed pointer =
  `i32 -1 | u16 classId`**, bool = 1 byte. `[verified]`
- Cracked head structures, in order: constant prologue → `m_storedByRevitBuild`
  build-history strings → a GUID-keyed map object (163…1243 entries, vendor
  "Autodesk Revit") → a `u32`-keyed table of small typed objects → typed
  null-pointer run → `m_oNobleSecondaryData` (NobleDocWarnings +
  ColorFillSecondaryData entries carrying real ElementIds). `[HIGH/MED]`
- The **middle 30–60 % of every non-DACH file is the Autodesk Forge
  units/spec schema dictionary as JSON**: ~590–640 clean `(typeid, json)`
  AString pairs followed by an ~0.5–1 MB **compressed continuation** (a
  16-bit/byte LZ-style text compression — decoder not yet written; this is
  the same phenomenon as the "corrupted tail" of `Formats/Latest`, see
  inbox note). `[MED]` for the region, `[hypothesis]` for the codec.
- ElementIds found in this stream cross-check against `Global/ElemTable`
  (7,092 int64 hits / 5,065 distinct ids in racbasic; e.g. 99859 at
  Latest+0x46e7 ↔ ElemTable+0xce6e). `[verified]`

## 1. Container facts (all six samples)

| file | inflated | 8-byte prefix | deflate trailer bytes | build strings | GUID-map entries | u32-keyed table keys | CFSD entries | clean units pairs | opaque blob (bytes) | tail start |
|---|---:|---|---:|---:|---:|---|---:|---:|---:|---|
| racbasic | 1,506,910 | `05 00 00 00 00 00 00 00` | 632 | 8 | 163 | 2..173 | 86 | 589 | 853,525 | 0x16935a |
| rstbasic | 1,593,249 | `05 …` | 771 | 7 | 52 | 2..181 | 119 | 522 | 961,141 | 0x1782ae |
| racadv | 1,652,438 | `05 …` | 797 | 7 | 121 | 2..174 | 371 | 636 | 882,072 | 0x18c672 |
| rstadv | 1,712,189 | `05 …` | 410 | 9 | 180 | 2..174 | 35 | 618 | 1,029,351 | 0x19e773 |
| rme | 4,668,833 | `05 …` | 106 | 8 | 305 | 2..174 | 5,230 | 0 (all compressed) | 525,030 | 0x2e592a |
| dach | 4,786,974 | `05 …` | 425 | 12 | 1,243 | 2..178 | (no NobleDocWarnings anchor) | none | none | 0x25c4af |

Decompression: skip the 8-byte prefix and the 10-byte gzip header, raw
inflate (`zlib.decompressobj(-15)`); the deflate stream reaches EOF cleanly
and the remaining 106–797 raw bytes are not consumed (not a gzip trailer;
un-decoded — TRACKER A10).

## 2. Primitive encodings (with evidence)

| primitive | encoding | example (racbasic) | confidence |
|---|---|---|---|
| AString | `u32` char count + UTF-16LE units, no NUL | `0e 00 00 00 41 00 75 00 74 00 6f 00 …` = "Autodesk Revit" @0x3df; build strings @0x57 | HIGH |
| ElementId | signed 64-bit LE; invalid = `ff ff ff ff ff ff ff ff` | `13 86 01 00 00 00 00 00` = 99859 @0x46e7; the same u64 is the key of the 40-byte record @ElemTable+0xce6e; consecutive objects carry 99859, 99860, 99861, 99864 | HIGH |
| GUID | 16 raw bytes, MS mixed-endian layout | `00 26 b2 34 d6 3e b3 44 b4 f1 65 96 f4 d5 2b 43` @0x3cf = {34b22600-3ed6-44b3-b4f1-6596f4d52b43}; the 163 GUIDs of the map are sorted by raw byte value (std::map) | HIGH |
| class ref | `u16` = schema type id (`Formats/Latest`, ids from 0x0c, sequential over class definitions incl. inline ones) | `2a 03` = 0x32a = 810 = `ColorFillSecondaryData` in every color-fill object header; `a7 03`=935=`ContentTable`, `a0 01`=416=`AppInfoManager` in the prologue | HIGH |
| typed pointer | `i32 -1` + `u16 classId`, usually followed by `u32` 0/1 (present/count flag) | `ff ff ff ff 2a 03 01 00 00 00` @0x4703 (object of class 810 follows inline); `ff ff ff ff a7 03` @0x0a | MED |
| bool | 1 byte | `00 00 00` @0x4c (three flags) | MED |
| double | IEEE-754 LE (seen in tail records, not framed here) | — | LOW |

Class-id resolution uses `extracted/_schema/schema_a.json` (ids ≤ 0x489)
plus a heuristic scan of the schema token order for higher ids; ids that
fall in the schema's un-decoded tail (≳1450) print as `cls#NNNN(?)`.

## 3. Region map — racbasicsampleproject (1,506,910 bytes)

| start | end | size | region | conf |
|---|---|---:|---|---|
| 0x00000 | 0x00053 | 83 | constant `ADocument` prologue (§4.1) | HIGH |
| 0x00053 | 0x003bd | 874 | `m_storedByRevitBuild`: u32 8 + 8 AStrings (build history) | HIGH |
| 0x003bd | 0x04077 | 15,546 | GUID-keyed map object (class 0x644): 163 entries {u32 1, GUID, "Autodesk Revit", ElementId64 -1, u32 803, u32 833, i32 -1, u32 n, n×(u32,u32)} (§4.3) | HIGH |
| 0x04077 | 0x0459f | 1,320 | `u32 1, u32 0xf1`, then `u32`-keyed table, keys 2..173, entry = key + u16 class-id-like + 0..7 zero u32s (§4.4) | MED |
| 0x0459f | 0x045fd | 94 | 8 typed null-pointer tokens (`u16 cls, i32 -1`) + u16 0x1031 + 44 zero bytes (§4.5) | LOW |
| 0x045fd | 0x09777 | 20,858 | `m_oNobleSecondaryData`: `NobleDocWarnings` object + 86 `ColorFillSecondaryData` entries with real ElementId64s (§4.6) | MED |
| 0x09777 | 0x2218f | 100,888 | unparsed secondary-data continuation: browser-organization/view/sheet name records ("Elevation 1", "A001", "3D Views", "Floor Plans"), space/HVAC naming schemes ("Space Name"×7, "Space Number"×7), electrical settings ("WireSizes.xml", "Number of Circuits"), user "liqi"; mostly binary (ElementId64s, ints, doubles) | LOW |
| 0x2218f | 0x98c99 | 486,154 | Forge units/spec dictionary, clean part: pre-header + u32 1 + u32 893 + 589 × (typeid AString, json AString) (§4.7) | MED |
| 0x98c99 | 0x98d45 | 172 | dictionary transition (first compressed fragment) | LOW |
| 0x98d45 | 0x16935a | 853,525 | **opaque compressed continuation of the units dictionary (56.6 % of the stream)** (§4.8) | LOW |
| 0x16935a | 0x16fe5e | 27,396 | tail: heterogeneous document-level named objects (§4.9) | LOW |

The same sequence of regions holds for rstbasic / racadv / rstadv / rme (see
§1 for their offsets); dach has the prologue, build list, GUID map and
keyed table but no units dictionary and no `NobleDocWarnings` anchor.

## 4. Region-by-region

### 4.1 Constant prologue 0x00–0x52 (byte-identical in all six files)

```
000000: 1c 00 00 00 00 00 00 00 00 00 ff ff ff ff a7 03  ................
000010: 01 00 00 00 ff ff ff ff a0 01 ff ff ff ff 66 10  ..............f.
000020: 00 00 00 00 ff ff ff ff f8 0f 00 00 00 00 ff ff  ................
000030: ff ff e9 0a ff ff ff ff ff ff ff ff ff ff ff ff  ................
000040: ff ff ff ff 01 00 00 00 66 0a 00 00 00 00 00 00  ........f.......
000050: 00 00 00                                         (0x53: u32 count 8 …)
```

| off | bytes | reading | candidate `ADocument` field (schema order) | conf |
|---|---|---|---|---|
| 0x00 | `1c 00 00 00` | u32 28 = type id of `ADocument` | root object class tag | MED |
| 0x04 | `00 00 00 00 00 00` | u32 0, u16 0 | `m_elemTable` / `m_appInfoArr` written as null/empty here (their data is externalized to `Global/ElemTable` / absent) | LOW |
| 0x0a | `ff ff ff ff a7 03` | ptr (−1, 935 = `ContentTable`) | `m_oContentTable` (body externalized to `Global/ContentDocuments`) | MED |
| 0x10 | `01 00 00 00` | u32 1 | flag following the pointer (present/refcount?) or `m_pHostDocument` weak ptr | LOW |
| 0x14 | `ff ff ff ff a0 01` | ptr (−1, 416 = `AppInfoManager`) | `m_pAppInfoManager` | MED |
| 0x1a | `ff ff ff ff 66 10` | ptr (−1, 0x1066 = 4198, schema tail) | `m_pStyleSettings` | LOW |
| 0x20 | `00 00 00 00` | u32 0 | flag | LOW |
| 0x24 | `ff ff ff ff f8 0f` | ptr (−1, 0xff8 = 4088) | `m_pHistory` (externalized to `Global/History`) | LOW |
| 0x2a | `00 00 00 00` | u32 0 | flag | LOW |
| 0x2e | `ff ff ff ff e9 0a` | ptr (−1, 0xae9 = 2793) | `m_pSteelModelInfo` / `m_pPartitionTable` (→ `Global/PartitionTable`) | LOW |
| 0x34 | `ff ff ff ff ff ff ff ff` | ElementId64 −1 | `m_ownerFamilyId` (invalid: project, not family) | MED |
| 0x3c | `ff ff ff ff ff ff ff ff` | ElementId64 −1 | `m_ownerFamilyContainingGroupId` | MED |
| 0x44 | `01 00 00 00 66 0a 00 00` | u32 1, u32 2662 (0xa66) | `m_devBranchInfo` = DevBranchInfo{m_devBranchId=1, m_syncVersion=2662} — 2662 is exactly `ADocument`'s schema version | MED |
| 0x4c | `00 00 00` | 3 × bool false | `m_groupFile`, `m_corruptDocument`, `m_bIsCoreDocument` | MED |
| 0x4f | `00 00 00 00` | u32 0 | count of `m_executedUpgrades` (list of `GUIDvalue`) — empty | MED |
| 0x53 | `08 00 00 00 …` | u32 count of build strings | `m_storedByRevitBuild` (list of `AStringWrapper`) | HIGH |

The schema declares 19 `ADocument` fields (order: m_elemTable, m_appInfoArr,
m_oContentTable, m_pHostDocument, m_pAppInfoManager, m_pStyleSettings,
m_pHistory, m_pSteelModelInfo, m_pPartitionTable, m_oNobleSecondaryData,
m_ownerFamilyId, m_ownerFamilyContainingGroupId, m_devBranchInfo,
m_groupFile, m_corruptDocument, m_bIsCoreDocument, m_executedUpgrades,
m_storedByRevitBuild, m_oExServicesUsed). The prologue token count (11
tokens before the two ElementIds) is one more than the 10 pointer/container
fields, so the exact token↔field alignment above 0x34 is `[hypothesis]`;
the tail of the prologue (0x34–0x52) matching m_ownerFamilyId …
m_executedUpgrades in schema order is strong. Pointer members whose bodies
live in their own OLE streams appear to serialize here as a bare typed token
with no inline body.

### 4.2 `m_storedByRevitBuild` (0x53–0x3bd in racbasic)

`u32 count` then `count` AStrings — the Revit builds that ever saved the
file, oldest first ("Revit 2018 - Preview Pre-Release 2018 (2018.000) :
20170117_1515(x64)" … "Revit 2026 2026 (2026.000) : 20250227_1515(x64)").
Counts: 8/7/7/9/8/12. This is a plain container-of-AStringWrapper; each
element is just the AString (the wrapper contributes no bytes). `HIGH`

### 4.3 GUID-keyed map object (racbasic 0x3bd–0x4077)

Header: `ff ff ff ff | 44 06 | 01 00 00 00 | a3 00 00 00` = typed pointer
(−1, class 0x644 = 1604, in the un-decoded schema tail), u32 1, u32 count
(163). Position (right after m_storedByRevitBuild) matches the last
`ADocument` field `m_oExServicesUsed` (owning pointer `0e 02`).

Entry grammar (163/163 parse in racbasic; 52…1243 in the other files):

```
entry := u32 1
         u8[16]  guid                      # sorted ascending by raw bytes → std::map<GUID,…>
         AString vendor                    # always "Autodesk Revit"
         i64  -1                           # ElementId64 invalid
         u32  a                            # 803 (0x323) in 157/163 entries, 826 (0x33a) in 6
         u32  b                            # 833 (0x341) in all
         i32  -1
         u32  n
         n × (u32 key, u32 value)          # keys seen: 833 (all), 844 (all), 842 (49), 846 (10), 837 (8)
```
Hex, entry 2 @0x427: `01 00 00 00 | 00 61 bc 96 3d 9a 7f 44 9a 6b ce 19 62 25
41 45 | 0e 00 00 00 "Autodesk Revit" | ff×8 | 23 03 00 00 | 41 03 00 00 |
ff ff ff ff | 02 00 00 00 | 41 03 00 00 e0 00 00 00 | 4c 03 00 00 01 00 00 00`.
`[hypothesis]` external-service / add-in / updater registry (GUID = service
or app id, vendor = "Autodesk Revit"); the u32 constants 803/833/842/844/846
coincide with schema type ids in the same range but the resolved names
(ColorFillData, std::pair<GeomRef,double>, ComponentRepeater…) make no sense,
so they are more likely per-service enum/version ints. `HIGH` for the
framing, `LOW` for the semantics.

### 4.4 `u32`-keyed typed-object table (racbasic 0x4077–0x459f)

`01 00 00 00 f1 00 00 00` (u32 1, u32 0xf1 — **the same 241 in every file**,
so it is not an entry count; 0xf1 = type id of `PostedWarning`?
`[hypothesis]`), then entries:

```
entry := u32 key                  # sequential 2..173 (racbasic), 2..181 (rstbasic), 2..178 (dach)
         u16 v                    # class-id-like: unique per entry, 0x1a..0x11e9;
                                  #   resolvable ones name document-level manager classes:
                                  #   0x475 DBViewInfo, 0x464 DBDrawingInfo, 0x1ad AppearanceInfo,
                                  #   0x1a ADocWarnings(!), 0xad AlignSides, 0xcd AllProjectPhasesInfo
         u32 zero × k             # k = 0..7 — the (mostly default/empty) serialized body of that object
```
Payload sizes in racbasic: 2 B ×130, 6 B ×26, 10 B ×10, 14 B ×3, 18 B ×2, 30 B
×1. `[hypothesis]` this is the document's registry of singleton
manager/table objects keyed by a registration index, each value being a
polymorphic object (u16 class + inline body, usually all-default). `MED`
for framing, `LOW` for semantics.

### 4.5 Typed null-pointer run (racbasic 0x459f–0x45fd)

Eight `(u16 classId, i32 −1)` tokens then `31 10` and 44 zero bytes:
742 `CategoryTable`, 2729, 3232, 2563, 2127, 2052, 4328, 426
`AppearanceAssetTable`. Reads like the null/deferred owning pointers of the
last table object (or of `ADocument` itself). `LOW`

### 4.6 `m_oNobleSecondaryData` head (racbasic 0x45fd–0x9777)

```
01 00 00 00 | 10 00 00 00 "NobleDocWarnings" | ff ff ff ff fd 0a | 09 00 00 00   ...
```
= u32 1, AString "NobleDocWarnings", typed token (−1, 0xafd), u32 9. Then 86
`ColorFillSecondaryData` entries; the first 9 (matching the u32 9) carry an
explicit typed header `ff ff ff ff 2a 03 01 00 00 00` (class 810), the rest
are embedded records `01 00 00 00` + strings. Entry body:

```
AString "ColorFillSecondaryData"        # class/schema name
AString "Color Fills"                   # group
AString "ColorFillSecondaryData"
AString "Color Fill"                    # kind
AString "<view/category> : <scheme>"    # e.g. "Rooms : Name", "Areas : Rentable Area", "Ducts : Duct Color Fill"
u8[10]  zeros
i64     elementId                       # 99859, 99860, 99861, 99864, … — present in Global/ElemTable
u8[~20] zeros / small ints              # (NOBLE_PrimaryDataId {ElementId, appInfoType, dataType, docId, …})
[ i64 elementId2, u32 14, u32 1, … ]    # embedded-record variant only
```
Hex @0x4623: `73 00 | ff ff ff ff fd 0a 09 00 00 00 | 16 00 00 00 43 00 6f 00
… | … "Rooms : Name" | 00×10 | 13 86 01 00 00 00 00 00 | 00×20 …`.
`ColorFillSecondaryData` in the schema derives from
`NOBLE_SecondaryDataEntityBase` (811) and holds `m_collectedPrimaryDataIds`
(list of `NOBLE_PrimaryDataId` {m_elementId, m_appInfoType, m_dataType,
m_docId, m_secondaryId}), which fits the ElementId64 + small-int tail. `MED`

### 4.7 Units/spec dictionary — clean part (racbasic 0x2218f–0x98c99)

Pre-header @0x2218f: `83 3e 0c 00 00 00 00 00 | ff×8 | 01 00 00 00 00 00 00
00 | ff×8 | 01 00 00 00 | 7d 03 00 00` = u64 0xc3e83 (802,435 — ElementId64
of the units-schema element?), i64 −1, u64 1, i64 −1, u32 1, **u32 893
(declared entry count; identical in every file that has the dictionary)**.
Then `(AString typeid, AString json)` pairs — verbatim Autodesk Forge
schema documents:

```
26 00 00 00 "autodesk.unit.dimension:currency-1.0.0"
ca 00 00 00 "{\n   \"annotation\": { \"description\": \"A non-SI base quantity …\"},\n
             \"typeid\": \"autodesk.unit.dimension:currency-1.0.0\",\n
             \"inherits\": [ \"autodesk.unit:dimension-1.0.0\" ]\n}\n"
```
racbasic: 589 clean pairs (json 161–1180 chars) covering dimensions,
symbols and the first units, then the encoding switches (§4.8). rme stores
**zero** clean pairs — the whole dictionary is compressed from the first
entry. `MED`

### 4.8 The opaque middle blob = compressed continuation of the units dictionary (racbasic 0x98d45–0x16935a, 853,525 B)

Evidence that it is the *same* JSON, compressed, not corruption:

- rme's first entry: length prefix `26 ff ff ff` (= 0xffffff26, low byte
  0x26 = 38 = strlen of the typeid; high bytes 0xff = "compressed" flag),
  then the typeid and json remain almost readable except that certain
  UTF-16 code units have their high byte set to **0xff**: `20 ff` (space),
  `22 ff` (quote), `69 ff` ('i') — flagged literals whose low byte is still
  the plain ASCII char. Masking the high byte reconstructs the exact JSON of
  racbasic's plain entry byte-for-byte for the same typeid. `[verified on
  the currency/electricCurrent/length entries]`
- Deeper into the blob (racbasic 0xa0000, 0x120000) literal runs of the JSON
  appear at **both even and odd byte offsets**, with substrings dropped
  ("annotnn\"1", "MincCentimeter…seterseter") — the signature of a
  **byte-oriented LZ scheme with back-references** (matches copied text,
  literals stored verbatim). No gzip/zlib magic; not a nested deflate stream
  (scanned every offset near the transition; the outer deflate is intact —
  it reaches clean EOF with the same output from two inflaters).
- The blob is bounded exactly by the dictionary on both sides in every file:
  it starts at the first non-plain entry (racbasic entry 589; a few later
  typeids still surface uncompressed at 0x99530, 0x99c66, 0x9a86d, 0x9df5f)
  and ends where clean document strings resume (tail, §4.9).
- The declared count 893 vs 589 (racbasic) / 522 (rstbasic) / 636 (racadv)
  clean pairs ⇒ the missing ~250–370 unit definitions live in the blob.

So ~57 % of racbasic's `Global/Latest` (and 30–60 % of the others) is the
Forge unit-schema JSON dictionary, mostly compressed. Decoding it is a
self-contained future task ("units codec"); it is the same encoding that
makes the tail of `Formats/Latest` look "intrinsically corrupted" (schema-a
§7) — inbox note filed. `MED` for the identification, decoder `TODO`.

### 4.9 Tail (racbasic 0x16935a–EOF, 27 KB; up to 2.3 MB in dach)

Starts (0x16929c) with fixed-width vectors — `u32 12, 12×u8 1, 12×u8 0, u32
12, 12×u8 1, u32 12, 12×(i64 −1)` — then a stream of small document-level
named objects: system family names ("Stairs System"), numbering schemas
("Rebar Numbering", "Fabric Sheets Numbering", "Rebar Couplers Numbering"),
DB server info ("http://www.autodesk.com", "Revit Default DB Server",
"ADSK"), MEP system defaults ("RbsSystem"×6, "RbsPipeCurve"), (view class,
"RevisionSettings") pairs, `LB_Associations`/`LB_MetaData`/`LB_Version`/
`LB_References` (linked-model bookkeeping), and finally room names ("Bath",
"Bedroom", "Kitchen & Dining", …) with doubles. Not framed further. `LOW`

## 5. Anchors and cross-stream links

| anchor | location in Global/Latest | link |
|---|---|---|
| `ADocument` type id 28 + version 2662 | 0x00 (`1c`), 0x48 (`66 0a`) | `Formats/Latest` class `ADocument` (u16 parent 0, u32 version 0xa66, 19 fields) |
| build-string list | 0x53 | schema field `m_storedByRevitBuild : container of AStringWrapper` |
| ElementId64 values | e.g. 99859 @0x46e7, 99860 @0x47e3, 99864 @0x48d3 | 40-byte records in `Global/ElemTable` @0xce6e/0xce96/0xcebe (each id occurs exactly twice per record) |
| GUIDs | 163 raw GUIDs keyed to "Autodesk Revit" | not the `BasicFileInfo` document GUID (e6a03f8e-…); those never occur in this stream (searched binary LE/BE and UTF-16 text) |
| class ids | u16 tokens after `i32 −1` | schema type ids: 935 ContentTable, 416 AppInfoManager, 810 ColorFillSecondaryData, 742 CategoryTable, 426 AppearanceAssetTable, 237 AnalyticalAutomationEditModeMgr |
| units dictionary | 0x221b7… | independent copy of Autodesk's public Forge unit schemas (`autodesk.unit.*` typeids) |

## 6. Most frequent small values that could be class ordinals (racbasic, framed regions only — the compressed blob excluded)

Typed-pointer tokens `(i32 −1, u16 X, u32 0|1)` — best class-id signal:

| X | count | first @ | schema name |
|---|---:|---|---|
| 0x032a | 9 | 0x4703 | ColorFillSecondaryData (explicit object headers) |
| 0x0137 | 17 | 0x16e5b0 | AnalyticalMemberMoveAlongMultiDirControl (tail; possibly a false positive on `37 01`) |
| 0x04ba | 6 | 0x16fd9e | 1210 (schema tail) |
| 0x03a7 | 1 | 0x0a | ContentTable |
| 0x01a0 | 1 | 0x14 | AppInfoManager |
| 0x1066 | 1 | 0x1a | 4198 (schema tail; StyleSettings by field order) |
| 0x0ff8 | 1 | 0x24 | 4088 (History by field order) |
| 0x0ae9 | 1 | 0x2e | 2793 |
| 0x0644 | 1 | 0x3bd | 1604 (ExServicesUsed container class) |
| 0x00ed / 0x02e6 / 0x0aa9 / 0x0ca0 / 0x0a03 / 0x084f / 0x0804 / 0x10e8 / 0x01aa | 1 each | 0x4599–0x45c9 | 237 AnalyticalAutomationEditModeMgr, 742 CategoryTable, …, 426 AppearanceAssetTable |

`u16` after a `u32` (the indexed-table motif) and 4-byte-aligned small
`u32`s are dominated by round values (0x100 ×555, 0x200 ×132, 0xa00, 0xb00,
0xe00, 0xc00, 0x1200 …) which are almost certainly enums/flags rather than
class ordinals; genuine class-id-looking `u32`s among the top-30: 0x29f
`NOBLE_DocumentId` (×12, first @0x21900), 0x1b7 `ArcWall` (×15), 0x2a9
`CGDriverNbrCornerMullionData` (×32, @0x21918), 0x681-region GStep names.
Full tables: run the tool (heuristic scan section).

## 7. Reproduce

```bash
/Users/ck/dev/things/rev-revit/.venv/bin/python /Users/ck/dev/things/rev-revit/src/rvt/global_latest.py        # racbasic + rstbasic
/Users/ck/dev/things/rev-revit/.venv/bin/python /Users/ck/dev/things/rev-revit/src/rvt/global_latest.py --all  # all six, + cross-file summary
```
The tool re-inflates from `Global__Latest.bin` if the pre-inflated
`Global__Latest.gz/000.bin` is missing, records the 8-byte prefix and the
deflate trailer length, prints the region map with per-region details, then
the heuristic frequency scans and the ElementId64-vs-ElemTable cross-check.

## 8. Unknowns

1. Meaning of the raw 8-byte stream prefix (`05` in all six) and the
   106–797-byte post-deflate tail of the raw stream.
2. Exact token↔field mapping in the prologue above 0x34 (which of the five
   `(−1, cls)` tokens is m_pStyleSettings vs m_pHistory vs m_pSteelModelInfo
   vs m_pPartitionTable; what the interleaved u32 0/1 words are).
3. Semantics of the GUID-keyed map (external services vs add-in/updater
   registry) and its per-entry u32s 803/826/833/842/844/846 and (key, value)
   pairs.
4. Semantics of the `u32 0xf1` constant and of the keys 2..17x in the typed
   table (§4.4); which class each un-resolvable u16 (≥ 0x600) denotes —
   needs schema decode of `Formats/Latest` beyond 0x21e61.
5. The units-dictionary compression codec (flagged length prefixes with
   0xff high bytes, 0xffXX flagged literals, byte-shifted back-reference
   runs) — the single biggest remaining volume of the stream. Same codec is
   suspected in the `Formats/Latest` tail; solving one solves both.
6. The 100–150 KB "secondary data" gap between the color-fill entries and the
   units dictionary (browser organization, view/sheet naming, MEP naming
   schemas, wire sizes XML) — object framing not attempted.
7. The tail region (§4.9): the leading 12-wide vectors, `LB_*` link tables,
   room/level name records with doubles.
8. Where element geometry lives: **not here** — nothing in `Global/Latest`
   looks like per-element geometry; it holds document-level tables, spec
   dictionaries and settings. Element data is in `Global/ElemTable` +
   `Partitions/<N>`.

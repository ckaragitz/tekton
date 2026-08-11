# Extensible Storage — the in-model schema catalog and the entity blob codec

Stream: `estorage` (wave: writer). Module: `src/rvt/estorage.py`.
Tests: `tests/test_estorage.py` (14; the dach corpus test is `slow`).
Record: `docs/inbox/estorage.md` (with the `objects.py` / `encode.py`
integration DIFF). Companions: `docs/writer/manipulation.md` (the layer
this unblocks — its robustness table's only recurring failure was this),
`docs/streams/10-objects.md` (the object decoder), KNOWLEDGE.md.
Confidence tags: **[V]** verified byte-exact on the corpus, **[H]**
hypothesis, **[D]** design decision.

## 0 · TL;DR

Extensible Storage (ES) is Revit's self-describing add-in data: an
**entity** conforms to a **schema** that Revit or an add-in registers at
runtime, and every schema an entity uses is **stored inside the model**.
The schema-directed object decoder decoded 100 % of records EXCEPT the
elements carrying ES entity blobs (`ESEntityCell.m_entityMap[*].second
.m_blob` failing with `pointer token pid=-1 to unknown class 0x2314` — rme
1,171 host elements, dach 1,741, rstbasic 7). Those elements were
un-modifiable. This stream closes that gap completely:

* **There is no class 0x2314.** The `ESEntity.m_blob` pointer token is
  `i32 pid` followed by the entity's **16-byte schema GUID** in place of the
  usual `u16` archive class id; `0x2314`, `0x2a2b`, `0x7959`, `0xb137` … are
  the first two little-endian bytes of the schema GUIDs (`762a2314-…`,
  `1b022a2b-…`, `4c817959-…`, `e66bb137-…`). ES entity classes are runtime
  types keyed by GUID, not `Formats/Latest` classes. **[V]**
* **The schemas live in `Global/Latest`**, in the `ESSchemaStorage` AppInfo's
  `m_schemaUsageMap` — an ordinary archive container of
  `std::pair< GUIDvalue, SchemaUsageInfo >` that the *existing* generic
  decoder decodes as-is once located (§2). rme has 2 schemas, rstbasic 2,
  dach 175; the three rac/rst-advanced files register none. **[V]**
* **The blob grammar**: the entity body is deferred breadth-first into the
  record's owned-pointer queue and is the schema's field values concatenated
  in `m_entryIndex` order — no header, no count, no GUID — each value in the
  standard archive primitive codebook; a nested `ESEntity` is again a
  `pid + subschema-GUID` token whose body is deferred to the same queue (§4).
  **[V]**
* **Result**: `rvt.estorage` locates + decodes the catalog, decodes every
  entity blob to a structured value and re-encodes it **byte-exact**;
  `ESDecoder` / `ESEncoder` (drop-in `ObjectDecoder` / `ObjectEncoder`
  subclasses, and the equivalent native diff) take the corpus to **0
  undecodable ES elements**: whole records re-encode byte-identical —
  rme 1,171/1,171, rstbasic 7/7, dach 1,743/1,743 (6,085 entities), and the
  1,171 previously-refused rme fittings pass the manipulate byte-exact edit
  precondition (§6, §7). **[V]**

```
cat  = rvt.estorage.schemas(doc)                        # ESSchemaCatalog
ent  = rvt.estorage.decode_entity_blob(blob, cat, guid)  # structured dict
blob = rvt.estorage.encode_entity_blob(ent, cat)         # byte-exact inverse
rep  = rvt.estorage.es_report(doc)                      # schema -> element ids
dec  = rvt.estorage.ESDecoder(schema, cat)              # record-level decoder
enc  = rvt.estorage.ESEncoder(dec)                      # record-level encoder
res  = rvt.estorage.verify_document(doc)                # corpus byte-exact proof
```

## 1 · The failure, diagnosed

Path (every non-clean object in the corpus, `docs/writer/manipulation.md`
§6): `Element.m_cellList → CellList.m_cells[i] → ESEntityCell (0x56b)
.m_entityMap : container< std::pair< GUIDvalue, ESEntity > >`. The pair's
`first` is the schema GUID; `ESEntity` (0x56a) has a single field
`m_blob : ptr` (kind 0x0e, flags 0x01, no static type id — a polymorphic
owned pointer). rme `FamilyInstance` 392203, payload +0x4a1..0x4c9
(`ESEntityCell` body):

```
04a1  01 00 00 00                                   m_entityMap count 1
04a5  14 23 2a 76 1c 1d 87 40 a5 8f ba b9 02 f5 7b e5   pair.first  = schema GUID 762a2314-1d1c-4087-a58f-bab902f57be5
04b5  ff ff ff ff                                   ESEntity.m_blob token: i32 pid = -1 (anonymous)
04b9  14 23 2a 76 1c 1d 87 40 a5 8f ba b9 02 f5 7b e5   ... followed by the SAME 16-byte GUID (NOT a u16 class)
04c9  01                                            (next queued body: AnalyticalSpaceBoundingCell.m_isSpaceBounding)
```

The old decoder read `u16` after the pid, saw `0x2314` (= bytes `14 23`),
found no such archive class (schema ids run `0x0c..0x125d`) and gave up.
The 16 bytes are the schema GUID again: an ES entity's "class" is its
schema, identified by GUID. Per-file "class" words map 1:1 to schema GUIDs:
rme `0x2314`/`0x2a2b` (762a**2314**, 1b02**2a2b**), rstbasic `0x7959`
(4c81**7959**), dach `0xb137`/`0xe691`/`0x1548`/… (e66b**b137**,
bba2**e691**, a116**1548**, …). **[V]** (`ESBlob` 0x569 — zero archive
fields — is the C++ static type of the blob; it is never on the wire.)

Where is the body? **Not** after the token. Owned-pointer bodies are
deferred into the record's breadth-first queue and this token is no
exception. Queue order at the token of FamilyInstance 392203, logged from
the real decoder: `[AnalyticalSpaceBoundingCell, MEPAnalyticalModelCell,
FamilyInstancePatternHelper, MEPCalculationServerInfo, Connector(pid 4),
Connector(pid 5), MEPFamilyInstanceConnectionBehaviorModifier]`; the blob
body is appended behind them, so it starts at +0x757 — after the two
connector bodies — and is 14 bytes: `05 00 00 00 "SR3-1"` (§4.1). The
"Version 5.0.0 of the ASHRAE duct fitting database…" strings right after
the token belong to the `MEPCalculationServerInfo` body, not the entity —
misreading them as an inline "self-describing entity" is the trap. **[V]**

## 2 · The in-model schema catalog

### 2.1 Location and layout **[V]**

`Global/Latest` = the serialized `ADocument`; `ADocument.m_pAppInfoManager
→ AppInfoManager.m_appInfoArr` holds the AppInfo objects, among them
`ESSchemaStorage` (0x56f, base `AppInfo` 0x1b) with, in field order:

| field | type | content |
|---|---|---|
| `m_storedForgeSchemas` | `container< pair<AString,AString> >` | Forge unit/spec schema JSON (`autodesk.unit.unit:feet-1.0.1` → `{"typeid":…}`) |
| **`m_schemaUsageMap`** | `container< pair<GUIDvalue, SchemaUsageInfo> >` | **THE ES CATALOG** — one entry per schema |
| `m_storedParameterSchemas` | `container< pair<AString,AString> >` | Forge parameter-group schema JSON (`autodesk.parameter.group:adskModelProperties-1.0.0`, 100 in every file) |
| `m_dirty` | uint | — |

Catalog entry = `pair< GUIDvalue first = schema GUID, SchemaUsageInfo
second >`, all ordinary archive classes (so `rvt.objects.ObjectDecoder`
decodes them unchanged):

| class (id) | fields (schema order) |
|---|---|
| `SchemaUsageInfo` 0x571 | `m_contentDocsKeys : container<GUIDvalue>` (content documents — embedded families — that use the schema), `m_schema : ESSchema`, `m_usedInHost : bool` |
| `ESSchema` 0x56e | `m_documentation : AString`, `m_fields : container<ESField>`, `m_schemaName : AString`, `m_vendorId : AString`, `m_applicationGUID : GUIDvalue`, `m_guid : GUIDvalue`, `m_readAccessLevel : int`, `m_writeAccessLevel : int` (1 Public / 2 Vendor / 3 Application) |
| `ESField` 0x56d | `m_documentation : AString`, `m_fieldName : AString`, `m_fieldTypeName : AString`, `m_specTypeId : ForgeTypeId` (units, e.g. `autodesk.spec.aec:length-1.0.0`), `m_containerType : int` (0 simple / 1 array / 2 map), `m_entryIndex : int` (**serialization slot**), `m_subSchemaGUID : GUIDvalue` (schema of an `ESEntity` field) |

Note the catalog's `m_fields` list is in field-**name** order; the entity
serialization order is `m_entryIndex` (§4).

Worked example — rme entry 1 at `Global/Latest` +0x327614 (container count
2 at +0x327610), decoded byte-for-byte:

```
0x327610  02 00 00 00                       m_schemaUsageMap count = 2
0x327614  14 23 2a 76 ... 02 f5 7b e5      pair.first = 762a2314-1d1c-4087-a58f-bab902f57be5
0x327624  00 00 00 00                       SchemaUsageInfo.m_contentDocsKeys count 0
0x327628  08 00 00 00 "Version1"          ESSchema.m_documentation = "Version1"
0x32763c  01 00 00 00                       m_fields count 1
0x327640  00 00 00 00                       ESField.m_documentation = ""
0x327644  0f 00 00 00 "ASHRAETableName"   m_fieldName
0x327666  05 00 00 00 "TCHAR"             m_fieldTypeName  (string)
0x327674  00 00 00 00                       m_specTypeId.m_typeId = ""
0x327678  00 00 00 00                       m_containerType = 0 (simple)
0x32767c  00 00 00 00                       m_entryIndex = 0
0x327680  00*16                             m_subSchemaGUID = null
0x327690  14 00 00 00 "CoefficientFromTable"  ESSchema.m_schemaName
0x3276bc  04 00 00 00 "ADSK"              m_vendorId
0x3276c8  00*16                             m_applicationGUID = null
0x3276d8  14 23 2a 76 ... 02 f5 7b e5      m_guid = the SAME GUID as pair.first
0x3276e8  01 00 00 00                       m_readAccessLevel = 1 (Public)
0x3276ec  01 00 00 00                       m_writeAccessLevel = 1
0x3276f0  01                                SchemaUsageInfo.m_usedInHost = true
0x3276f1  2b 2a 02 1b 22 57 87 47 ...       entry 2 begins (1b022a2b-5722-4787-…, PipeFittingKFactorTableName)
0x3277e6  a6 01 00 00 ...                   next: m_storedParameterSchemas (422 pairs)
```

Entries are contiguous (entry 1 ends at 0x3276f1 exactly where entry 2's
GUID begins) and the u32 before entry 1 equals the entry count. **[V]**

### 2.1b The Revit ≤ 2024 layout: `m_storedSchemas` (#576) **[V on the bundled 2024 base]**

A Revit 2024 file's own `Formats/Latest` has **no `SchemaUsageInfo` class**.
Its `ESSchemaStorage` (0x537 in `G_ABPD_2024.rvt`) is, in field order,
`m_storedForgeSchemas : pair<AString,AString>`, `m_storedParameterSchemas :
pair<AString,AString>`, **`m_storedSchemas : container< std::pair< GUIDvalue,
ESSchema > >`** (0x538), `m_dirty` — the catalog value IS the `ESSchema`
(0x536, the same eight members as 2026's 0x56e; `ESField` 0x535 likewise),
without the `m_contentDocsKeys` / `m_usedInHost` wrapper. So an entry is
`key GUID(16) + ESSchema` and ends `… m_guid(16) read u32 write u32` — an
**8-byte** tail after `m_guid` where the 2025+ entry has 9 (`+ usedInHost
u8`). Everything else in §2.1/§2.2 holds: ordinary archive classes decoded by
the generic decoder against the file's own schema, key GUID == decoded
`m_guid`, entries contiguous, u32 count in front. `rvt.estorage.catalog_layout
(schema)` reads which member the file's own `ESSchemaStorage` declares and the
locator chains with that layout's tail length; `ESSchemaDef.used_in_host` is
`None` and `content_docs_keys` `[]` for this layout (not recorded — reported
absent, never invented; the CLI prints `usage-unrecorded`). The 2025 base
already has the 2026 layout (`ESSchemaStorage` 0x554 `m_schemaUsageMap`,
`SchemaUsageInfo` 0x556) — and *also* defines an unused `std::pair< GUIDvalue,
ESSchema >` (0x1187), which is why the layout is read off `ESSchemaStorage`'s
members, not off which pair class merely exists. Whether Revit ≤ 2023 files
share the 2024 layout is unmeasured (no 2023 base in the bundle).

Worked example — `G_ABPD_2024.rvt` entry 1 at `Global/Latest` +0xfe67d
(count 2 at +0xfe679; entry 2, `DaylightingAnalysisInfo`, at +0xfe72f..0xfe83d):

```
0x0fe679  02 00 00 00                       m_storedSchemas count = 2
0x0fe67d  59 79 81 4c 28 00 83 4a b3 e7 cd 1e 83 2a 45 9a   pair.first = 4c817959-0028-4a83-b3e7-cd1e832a459a
0x0fe68d  00 00 00 00                       ESSchema.m_documentation = ""   (no SchemaUsageInfo.m_contentDocsKeys before it)
0x0fe691  01 00 00 00                       m_fields count 1
0x0fe695  00 00 00 00                       ESField.m_documentation = ""
0x0fe699  08 00 00 00 "Identity"          m_fieldName
0x0fe6ad  05 00 00 00 "TCHAR"             m_fieldTypeName
0x0fe6bb  00 00 00 00                       m_specTypeId.m_typeId = ""
0x0fe6bf  00 00 00 00  00 00 00 00          m_containerType = 0, m_entryIndex = 0
0x0fe6c7  00*16                             m_subSchemaGUID = null
0x0fe6d7  14 00 00 00 "AREXContentGenerator"  ESSchema.m_schemaName
0x0fe703  00 00 00 00                       m_vendorId = ""
0x0fe707  00*16                             m_applicationGUID = null
0x0fe717  59 79 81 4c ... 2a 45 9a          m_guid = the SAME GUID as pair.first
0x0fe727  01 00 00 00  01 00 00 00          m_readAccessLevel = 1, m_writeAccessLevel = 1
0x0fe72f  ee 88 95 5d c7 e6 96 4c ...       entry 2 begins IMMEDIATELY (no usedInHost byte)
```

Two locator consequences, both handled: (a) the u32 in front of an *inner*
entry is the previous entry's `m_writeAccessLevel` (1..3), so "leading u32 ==
entries recovered so far" is not a stopping rule for the backward chain — the
chain stops only when no previous entry decodes ending exactly at the current
first entry; (b) an entry key followed by `m_documentation = ""` reads as a
plausible *tracking* item with 0 ids, and the u32 before entry 2's key (entry
1's write level, 1) would even "verify" it as a 1-item table — `locate_tracking`
therefore skips candidates inside the catalog map's own byte span. The 2024
base's real `EStorageTracking.m_trackingItems` is 7 items, count at +0xff92e:
five leading items keyed by structured, uncatalogued GUIDs, then the two
catalogued items — until #595 it came back only through the unverified-count
fallback (offset reported 0xff9a2 = the catalogued run's start − 4, the five
dropped); §2.1c is how it is located and verified now, byte for byte.

### 2.1c The tracking table led by uncatalogued items — `G_ABPD_2024.rvt` (#595) **[V on the bundled 2024 base]**

`EStorageTracking` (0x539 in this file; base `AppInfo` 0x1b = one weak
`m_pADoc`) has the same single member in every release read here,
`m_trackingItems : container<EStorageTrackingItem>` with `EStorageTrackingItem`
(0x53a) = `m_schemaGuid : GUIDvalue` + `m_elemIdSet : container<ElementId>`
— so an item is `GUID(16) + u32 n + n × i64`, exactly the 2025/2026 shape.
The whole object in `Global/Latest`, +0xff92a..0xffa06 (220 bytes):

```
0x0ff92a  01 00 00 00                                   AppInfo.m_pADoc = weak ref 1 (the ADocument)
0x0ff92e  07 00 00 00                                   m_trackingItems count = 7        <- tracking_offset
0x0ff932  01 00 00 30 79 6e 0c 43 ad f9 63 4f 71 6c 5f 5d  00 00 00 00                            item 1  30000001-6e79-430c-adf9-634f716c5f5d  0 ids
0x0ff946  01 00 00 30 e6 62 6d 41 a3 4a bb 30 64 35 0b 62  01 00 00 00  60 c1 00 00 00 00 00 00   item 2  30000001-62e6-416d-a34a-bb3064350b62  {49504}
0x0ff962  02 00 00 20 79 6e 0c 43 ad f9 63 4f 71 6c 5f 5d  00 00 00 00                            item 3  20000002-6e79-430c-adf9-634f716c5f5d  0 ids
0x0ff976  02 00 00 20 e6 62 6d 41 a3 4a bb 30 64 35 0b 62  01 00 00 00  60 c1 00 00 00 00 00 00   item 4  20000002-62e6-416d-a34a-bb3064350b62  {49504}
0x0ff992  05 00 00 10 1a db fc 45 9e ed 81 02 62 79 2b 5b  00 00 00 00                            item 5  10000005-db1a-45fc-9eed-810262792b5b  0 ids
0x0ff9a6  59 79 81 4c 28 00 83 4a b3 e7 cd 1e 83 2a 45 9a  06 00 00 00  84 f0 14 00 … 68 05 15 00 …  item 6  4c817959-…  AREXContentGenerator {1372292, 1372482, 1375817, 1376990, 1377250, 1377640}
0x0ff9ea  ee 88 95 5d c7 e6 96 4c 87 dc df 2a 5f be 66 13  01 00 00 00  cc 19 15 00 00 00 00 00   item 7  5d9588ee-…  DaylightingAnalysisInfo {1382860}
0x0ffa06  (next AppInfo)                                items 6–7 are byte-identical to the 2025/2026 bases' whole 2-item table
```

**Locating it.** Anchors are still catalogued-GUID occurrences that read as
an item (item 6 here); the table is chained forward through items of any
GUID and, since #595, walked *backward* through items of any GUID: the item
with `k` ids that ends where the first known item starts begins at
`q = first − 20 − 8k` and is self-checking — the u32 at `q+16` must equal
`k`, the `k` words must be plausible ElementIds, the 16 bytes at `q` must not
be low-entropy filler. That admits false tilings: from item 5 (@0xff992) both
`k=1` → item 4 @0xff976 (real) and `k=0` → a 20-byte pseudo-item @0xff97e made
of item 4's own tail (`a3 4a … 0b 62 | 01 00 00 00 | 60 c1 00 00`, "count" =
the high dword of id 49504 = 0) pass, and the same happens again from item 3
(@0xff94e). So the walk is breadth-first with backtracking and a table is
accepted only when the u32 in front of its first item equals the items it
then holds (every walked-back item + at least every forward item up to the
last catalogued one; forward items beyond the count are cut). On this base:
level 1 = {0xff992}, level 2 = {0xff97e ✗ (u32 in front 0x416d62e6, no
predecessor), 0xff976}, level 3 = {0xff962}, level 4 = {0xff94e ✗, 0xff946},
level 5 = {0xff932}: u32 in front = **7** = 5 walked back + 2 forward →
verified, `tracking_offset = 0xff92e`, `tracking_count = 7`; seven candidate
states in all, `locate_tracking` 0.72 → 0.75 ms best-of-9 (a walk state is just
an item offset — an item has one end, so an offset reaches the anchor by
exactly one chain — and the accepted table is re-read front to back once).
Two count-verified tilings on one level resolve to the one starting earlier;
that settles exactly the tail-carved pseudo-item family (a real item
out-spans its own tail) and claims no more: any other wrong tiling, on that
level or an earlier one, needs the u32 in front of it to equal its exact item
count — the single 2⁻³² coincidence the pre-#595 count check already
accepted. The catalog map's own span stays excluded (`skip`) *permanently*,
not as a stopgap: entry 2's key + its empty `m_documentation`, fronted by
entry 1's write level 1, would now count-verify as a confident 1-item table
whenever the real table did not. Nothing verified → the old fallback, now
*labelled*: `tracking @0x… (count unverified)`, `tracking_count` 0, catalogued
run only; a file whose own `EStorageTrackingItem` is not `{m_schemaGuid :
GUIDvalue, m_elemIdSet : ElementId}` (`tracking_layout_known`) is not walked
at all and the header says `tracking not read (<why>)`. Cross-check: the
generic `ObjectDecoder` reading class
0x539 at `tracking_offset − 4` against the file's own `Formats/Latest`
decodes `{m_pADoc: weak 1, m_trackingItems: [the same 7 (guid, ids)]}` with
no error and ends at 0xffa06, where the byte walk ends (2025/2026: the same
2 items, object 0x137e06..0x137e6e / 0x16bfad..0x16c015) — `tests/test_estorage_catalog_2024.py`.

**What the five are, as far as the bytes say.** They are ordinary
`EStorageTrackingItem`s of the file's own class — nothing but their GUIDs
distinguishes them from items 6–7 — whose schema GUIDs have **no entry in
`m_storedSchemas`** (count 2, §2.1b), so name, vendor and fields are unknown
and the module says exactly that (`uncatalogued schema GUIDs tracked by
EStorageTracking (no catalog entry; name and fields unknown)`), listing GUID
+ ids once, in the catalog section; `ESSchemaCatalog.tracking_uncatalogued`,
`to_json()["tracking_uncatalogued"]` / `["tracking_count"]` and `es_report()
["tracking_uncatalogued"]` / `["tracking_count"]` carry them unconditionally
(empty / 2 on the 2025/2026 bases — a JSON consumer can always tell verified
from unverified), `tracking` stays catalogued-only.
Each GUID occurs exactly **once** in the whole container (this table) — in no
partition, no other Global stream, not as UTF-16/ASCII text, and nowhere in
the 2025/2026 bases, whose tables are items 6–7 alone. The GUIDs are
structured, not random: three "families" `xxxxxxxx-6e79-430c-adf9-634f716c5f5d`,
`xxxxxxxx-62e6-416d-a34a-bb3064350b62`, `xxxxxxxx-db1a-45fc-9eed-810262792b5b`
whose last 12 bytes keep valid version-4 / RFC-variant bits (`430c`/`adf9`,
`416d`/`a34a`, `45fc`/`9eed`) while `Data1` is overwritten with a small
tagged counter (`0x30000001`, `0x20000002`, `0x10000005`) — i.e. derived
from three random base GUIDs by stamping the first dword. The two items that
track anything both track element **49504 = the `ProjectInfo` element**
(seq-102 class `ProjectInfo`, category −2003101), which carries **no**
`m_cellList` / `ESEntityCell` at all in this base — the registry remembers a
schema→element association whose entity is not (or no longer) serialized on
the element. That is consistent with Revit-internal (not add-in) schemas of
the 2024 era registered against Project Information and gone by the 2025
upgrade of the same seed, but *which* Revit feature owns them is not in the
bytes: no catalog entry, no string, no entity body. Whether Autodesk's own
2024 samples carry the same five is unmeasured here (no `samples/` in a
cloud clone) — one `python -m rvt.estorage <2024 sample> --report` on the
owner's machine answers it.

### 2.2 Locating the map without decoding `ADocument` **[D]**

The full `ADocument` graph is not decoded by the generic decoder (it fails
inside `AppInfoManager.m_appInfoArr`, an out-of-scope token style), so the
map is located structurally and every candidate is **self-validating**: an
offset `p` is a catalog entry iff decoding `pair<GUIDvalue,SchemaUsageInfo>`
at `p` succeeds AND the decoded `ESSchema.m_guid` equals the 16 bytes at
`p` (the map key). `locate_schema_map` then chains: forward (next entry
starts where this one ends) and backward (the previous entry's `m_guid`
sits 25 bytes before this entry's start — `m_guid(16) + read u32 + write u32
+ usedInHost u8`; 24 on the ≤ 2024 layout, §2.1b — and that same GUID begins
the previous entry, placed only if it decodes ending exactly here), stopping
when no previous entry can be placed; the u32 then preceding the first entry
is the container count. dach: 175 entries, `count 175 @0x391d2b` matched. Seeds:

* **GUID-seeded** (any file with entities): the schema GUIDs read straight
  out of the entity tokens (a base-decoder failure at the token, or the ES
  decoder) — a handful of `bytes.find` calls.
* **GUID-free** (`_tail_scan_seeds`): a regex over the distinctive entry
  TAIL (`read u32 ∈ 0..4, write u32 ∈ 0..4, usedInHost u8 ∈ 0..1`; without
  the last byte on the ≤ 2024 layout) plus a
  cheap check that a plausible `m_vendorId` AString ends 32 bytes before the
  tail's `m_guid`, then the same map-key/decode validation; one validated
  entry anchors the whole run. Verified to find the rme (0x327610) and
  rstbasic (0xe9264) maps with no seeds; the three rac/rst-advanced files
  contain no entry (their maps are empty — no schema/type-name strings occur
  anywhere in their `Global/Latest`). **[V]**

### 2.3 `EStorageTracking` — Autodesk's schema → element-ids registry **[V]**

A sibling AppInfo, `EStorageTracking` (0x572), holds `m_trackingItems :
container<EStorageTrackingItem{ m_schemaGuid : GUIDvalue, m_elemIdSet :
container<ElementId> }>` — for each top-level schema, the ids of the host
elements carrying an entity of it. rme at +0x3ab9f7: count 2 →
`{762a2314-…, count 657, ids 392203, 393086, 393092, …}`, `{1b022a2b-…,
count 514, …}` — exactly the 657 + 514 = 1,171 failing FamilyInstances.
`locate_tracking` finds it (items contiguous; the u32 before the first
item = item count; anchored on a catalogued GUID, chained forward and
walked backward through items of *any* GUID and verified by that count —
§2.1c; items whose GUID is not in the catalog are reported as
`tracking_uncatalogued`, never dropped) and it drives
`es_report`. It tracks TOP-LEVEL entities of the host document only:
nested subschema entities (`Values`, `LoadCasesMap`,
`MeasurementDescription`, …) and embedded-document entities are not in it
(dach: 34 tracked schemas / 3,252 ids vs 175 catalogued schemas). **[V]**

### 2.4 The catalogs of the corpus **[V]**

| file | schemas | map (count) @ | tracking @ | notes |
|---|---:|---|---|---|
| rmebasic | 2 | 0x327610 (2) | 0x3ab9f7 | `CoefficientFromTable` ×2 (ADSK; duct `ASHRAETableName`, pipe `PipeFittingKFactorTableName`; TCHAR) |
| rstbasic | 2 | 0xe9264 (2) | 0x16d7d5 | `AREXContentGenerator` (`Identity` TCHAR), `DaylightingAnalysisInfo` (ADSK; `AnalysisId` TCHAR + `ResultsInvalid` int) |
| dach | 175 | 0x391d2b (175) | 0x42b3af | 173 used in host; vendors ADSK 146, HSB_ 8, SOFI 7, RPCA 5, none 9 (steel connections `flatbracing1` / `columnbeamseatt` / `railinganchor` / `singleeb*`) |
| racbasic / racadv / rstadv | 0 | — | — | `ESSchemaStorage` present (100 Forge parameter schemas) but `m_schemaUsageMap` empty |
| bundled `G_ABPD.rvt` (2026) / `G_ABPD_2025.rvt` | 2 | 0xe7a40 / 0xe690f (2) | 0x16bfb1 / 0x137e0a | the rstbasic pair (`AREXContentGenerator` 6 ids, `DaylightingAnalysisInfo` 1 id); `m_schemaUsageMap` layout |
| bundled `G_ABPD_2024.rvt` | 2 | 0xfe679 (2) | 0xff92e (7 items: 5 uncatalogued Revit-internal GUIDs, then the same pair, same ids — §2.1c) | **`m_storedSchemas` layout** (§2.1b) |

## 3 · The entity token **[V]**

Wherever an `ESEntity` value is serialized — the archive class's `m_blob`
(top level), or an `ESEntity`-typed ES field (nested, §4.3):

| bytes | field | meaning |
|---|---|---|
| `i32` | pid | `0` = **null entity, nothing follows (4 bytes total)**; `-1` = anonymous (the normal case); `>0` never observed (would be an indexed pid) |
| `u8[16]` | schema GUID | present when pid ≠ 0; the entity's schema (catalogued in `m_schemaUsageMap`); replaces the archive `u16` class id |

The body is appended to the record's ONE breadth-first deferred queue at
the token's position, exactly like any owned-pointer body. **[V]**

## 4 · The entity blob (body) grammar

### 4.1 Flat entities **[V]**

Body = the schema's field values, one after another, in ascending
`ESField.m_entryIndex`, **no header** (no length, count, version or GUID
— the schema is the only thing that gives the body a structure, which is
why it was undecodable without the catalog). Two ground truths where the
body is provably delimited:

* rstbasic `DataStorage` 1382860, schema `DaylightingAnalysisInfo`
  (`AnalysisId` TCHAR idx 0, `ResultsInvalid` int idx 1): body =
  `00 00 00 00 | 00 00 00 00` = empty AString + int 0 = 8 bytes ending
  **exactly** at the record end (payload 167, body at +0x9f).
* rstbasic `RebarShape` 1377250, schema `AREXContentGenerator`
  (`Identity` TCHAR): body = `40 00 00 00` + 64-char UTF-16 base64
  identity = 132 bytes ending exactly at the record end (+0x84a → 0x8ce).
* rme `FamilyInstance` 392203 (§1): body at +0x757 = `05 00 00 00
  "SR3-1"`, immediately followed by the queued `MEPAnalyticalFittingData`
  body whose own `m_ESFieldName / m_ESFieldValue` =
  `"ASHRAETableName" / "SR3-1"` — Revit's analytical-model cache of the
  same value, an independent confirmation.

Field-order proof (`entryIndex`, not the catalog's name order): dach
`SOFiSTiK_Schema_RebarDetail` (`RebarElement` TCHAR idx 0, `Insertionpoint`
XYZ idx 1; the catalog lists them alphabetically the other way round).
FamilyInstance 1165945 body: `00 00 00 00` (empty string) then the XYZ
`(12002.65, 5105.16, 0.0)` (plausible mm coordinates); reading in name
order would yield a denormal and a NaN. **[V]**

### 4.2 Value encodings and containers **[V]**

`m_fieldTypeName` → the standard archive primitive codebook (same bytes as
`rvt.objects` / `rvt.encode`):

| type name | encoding | corpus evidence |
|---|---|---|
| `int` | i32 | `ResultsInvalid` 0; `Insight360ModelId` 38837; `ValuesMode` |
| `double` | f64 | `Values.ValuesArray` (structural results), `MEPAnalyticalSegment`-adjacent bodies |
| `bool` | u8 (0/1) | `InternalSchema_Data_Version_5.IsZipped` = 1 |
| `char` | i8 (byte) | array form = raw bytes (`SOFiSTiK_Analysis_*.EntityData` binary) |
| `short` / `float` / `int64` | i16 / f32 / i64 | supported by the codebook; not seen in the six samples |
| `TCHAR`, `AString`, `AStringWrapper` | u32 char count + UTF-16LE (0xFFFFFFFF = null) | `ASHRAETableName` "SR3-1"; `AStringWrapper` array elements are plain AStrings (`SOFiSTiK_Schema_Rebar_V6.DetailElements`) |
| `GUIDvalue` | 16 raw bytes | `ResultsPackage.PackageGuid`; `DataStorageUniqueId.Id` |
| `ElementId` | i64 (−1 invalid) | `LevelResults.LevelId`; map keys 1476906 (dach) |
| `XYZ` / `UV` | 3 × f64 / 2 × f64 | `SOFiSTiK_Schema_RebarDetail.Insertionpoint` (unit spec length; raw doubles) |
| `ESEntity` | token (§3), body deferred | `LARData.AnalysisInfo`, `AnalysisResult.LoadCase` |
| `std::pair< K, V >` | K value then V value | map entries (below); K,V any of the above incl. `ESEntity` |

Containers (`m_containerType`): **0 simple** = the value; **1 array** =
`u32 count` + count × element (a `char` array = `u32 count` + raw bytes);
**2 map** = the type name is `std::pair< K, V >`, encoded `u32 count` +
count × (K, V). Observed pair types: `<AString,AString>`,
`<int,ElementId>`, `<ElementId,ESEntity>`, `<AString,ESEntity>`,
`<AString,ElementId>`, `<AString,UV>`, `<AString,XYZ>`, `<AString,bool>`,
`<AString,char>`, `<AString,double>`, `<AString,GUIDvalue>`,
`<AString,int>`. dach type census over 175 schemas: `int`×164, `ESEntity`
×138, `double[]`×130, `TCHAR`×47, `AStringWrapper[]`×33, `int[]`×16,
`XYZ`×12, `bool`×8, `GUIDvalue`×7, pair maps ×24, `ElementId`(±[])×10,
`char[]`×2.

### 4.3 Nested entities are deferred, not inline **[V]**

An `ESEntity`-typed field (scalar, array element, or map value) is a token
(§3); a non-null token appends its body to the SAME record queue, so a
sub-entity body is generally NOT adjacent to its parent — other queued
bodies come first. dach `AnalyticalPanel` 4276033, top entity schema
`AnalysisResult` (`LoadCase` ESEntity idx 0 → subschema `LoadCasesMap`
5fb3dbc4-…, `LoadCasesMap` map<ElementId,ESEntity> idx 1), body at +0x733:

```
0733  00 00 00 00                        LoadCase = pid 0 -> NULL entity (4 bytes)
0737  01 00 00 00                        LoadCasesMap count 1
073b  2a 89 16 00 00 00 00 00            key ElementId 1476906
0743  ff ff ff ff c4 db b3 5f 3d ed 3a 4d ac 2a 18 71 5c ef 9a 7f
                                         value token: pid -1 + SUBschema 5fb3dbc4-ed3d-4d3a-…
0757  01 00 00 00 24 00 00 00 "FBABFC2C-90BA-4A52-AB46-737CF2AD53AA"
      ff ff ff ff 62 0b 1a 89 …           <- NOT the sub-entity body: this is the element's
                                            SECOND top-level entity (map<AString,ESEntity>,
                                            SOFiSTiK dictionary) then 19 more archive bodies;
                                            the LoadCasesMap sub-entity body arrives later.
```

So a record's queue interleaves archive bodies, top-level entity bodies and
their descendants; the codec must live inside the decoder's queue. The one
element with a multi-level nesting proof, dach `ProjectInfo` 802 (7
top-level entities): its `LARData` body is `01 00 00 00 | token(19b97d17-…
AnalysisInfo) | 00 00 00 00 (AnalysisInfoPending null) | 00 00 00 00 (LARData
map count 0) | 00 00 00 00 (LevelResults map count 0)` = 36 bytes, and the
`Insight360` entity body follows immediately (`Insight360ModelName` = the
project name); the `AnalysisInfo` sub-entity body (whose `Environments` /
`JobInfo` arrays hold 2 + 98 further entities) is decoded only after the
six sibling entity bodies. The whole 370,860-byte record decodes to
`consumed == total` and re-encodes byte-identical. **[V]**

### 4.4 Which archive objects hold entities **[V]**

Any occurrence of the archive class `ESEntity` (0x56a): in practice the
`ESEntityCell.m_entityMap` map on the element (the sub-cell also carries
`AnalyticalSpaceBoundingCell` / `MEPAnalyticalModelCell` / pattern-helper
siblings) and inside `pair< ElementId | AString | int | …, ESEntity >`
containers. The decoder hooks the CLASS, so every occurrence is handled.
Element classes seen carrying entities: `FamilyInstance` (rme 1,171; dach
1,284), `RebarShape` 6, `DataStorage` (18), dach `Rebar` 122, `Floor` 21,
`SWall` 4, `DPart` 14, `AssemblyInstance` 11, `RebarSystem` 30,
`AnalyticalPanel` 40, `AnalyticalMember` 81, `FamilySymbol` 5,
`StructuralConnectionHandler` 17, `DBView3d` 21, `Fabric{Sheet,Area}` 29,
`RebarContainer` 3, `Family` 19, `CurveElem` 24, `ProjectInfo` 1.

## 5 · The module (`rvt.estorage`)

| API | purpose |
|---|---|
| `schemas(source)` → `ESSchemaCatalog` | locate + decode the catalog (source = `Document`, `.rvt` path or corpus project); `.by_guid`, iteration in map order, `.tracking` / `.tracking_uncatalogued` / `.tracking_offset` / `.tracking_count` (§2.3, §2.1c; count 0 = unverified fallback), `.to_json()` |
| `ESSchemaDef` / `ESFieldDef` | guid, name, vendorId, applicationGuid, documentation, read/write access, `used_in_host`, `content_docs_keys`, `fields` **in serialization (`entryIndex`) order** |
| `decode_entity_blob(blob, cat, guid)` | pure decode of an entity body (+ its nested bodies contiguous, breadth-first — the layout an entity closure has when nothing but its descendants follow); returns `{schema_guid, schema, pid, fields, consumed, total, errors}` |
| `encode_entity_blob(entity, cat)` | byte-exact inverse |
| `ESDecoder(archive_schema, cat)` | `ObjectDecoder` + ES: intercepts the `ESEntity` class (token → queued body), serves queued entity bodies from the same breadth-first queue; nested tokens recurse through it |
| `ESEncoder(decoder)` | the transpose (`ObjectEncoder` + ES); reproduces the queue order 1:1 |
| `es_report(doc, walk=False)` | schemas + tracked element ids; `walk=True` adds per-schema class breakdown / host-embedded split from a full seq-102 decode |
| `verify_document(doc)` | the corpus proof: every ES-bearing record decodes clean AND re-encodes byte-identical (§6) |
| `collect_entity_closures(doc)` | the contiguous entity closures the pure blob codec operates on |
| CLI | `python -m rvt.estorage <project\|path> [--report [--walk]] [--roundtrip]` |

Decoded entity representation (JSON-able, encode-symmetric) **[D]**:
`{"schema_guid": g, "schema": name, "pid": -1, "fields": {field: value}}`,
a null entity = `None`; scalars as Python numbers/str, `XYZ` = `[x,y,z]`,
arrays = lists, maps = `[[key, value], …]` (order + duplicate keys kept),
`char[]` = `{"charbytes": "<hex>"}`, nested entities recursive. In a whole
record the `ESEntity` object reads `{"m_blob": <entity or None>}`, so the
manipulate JSON-path editing addresses `….m_entityMap[i].second.m_blob
.fields.<Name>`. AString lone surrogates are preserved (`surrogatepass`),
doubles round-trip bit-exact — the same guarantees as `rvt.encode`.

## 6 · Corpus results **[V]**

`verify_document`: every seq-102 record whose payload contains a catalog
GUID is decoded with `ESDecoder` and re-encoded with `ESEncoder`; the
re-emitted **record bytes** must equal the original (this subsumes
blob-level exactness). `collect_entity_closures` + `decode_entity_blob` /
`encode_entity_blob` prove the pure blob codec on every contiguous
closure (flat entities anywhere, plus entities whose descendants form the
queue tail).

| file | ES records | entities (incl. nested) | decode clean | byte-exact re-encode | contiguous closures (blob-level exact) |
|---|---:|---:|---:|---:|---:|
| rmebasicsampleproject | 1,171 | 1,171 | 1,171 | **1,171 / 1,171** | 1,171 / 1,171 |
| rstbasicsampleproject | 7 | 7 | 7 | **7 / 7** | 7 / 7 |
| dach-sample-project | 1,743 | 6,085 | 1,743 | **1,743 / 1,743** | 3,480 / 3,480 (31 nested-descendant tails) |
| racbasic / racadv / rstadv | 0 | — | — | — | — |

**Undecodable ES elements: 0 on every file.** With the native diff
applied, the whole rstbasic seq-102 stream re-encodes 32,011/32,011
(previously 32,004 clean + 7 ES failures), and the corpus-wide seq-102
clean rate becomes 100.000 % (the ES blobs were the only failures). The one
remaining non-clean record corpus-wide is unrelated: dach `ImageHolder`
2181956 (`m_compressedImage` container-count sanity cap — a decoder
container limit, not ES).

## 7 · Integration (`objects.py` / `encode.py` / `mutate.py`)

`ESDecoder` / `ESEncoder` are behaviour-identical previews of the native
integration; the DIFF is in `docs/inbox/estorage.md` and was validated by
applying it to a copy of the package: `ObjectDecoder(schema, es_catalog=cat)`
intercepts the `ESEntity` class in `_decode_class` (reads the §3 token,
queues an `_ESPend`), the `decode_record` loop serves `_ESPend` bodies via
`rvt.estorage.EntityCodec`; `ObjectEncoder` mirrors both (`_encode_class`
writes the token, the `encode_object` loop writes queued entity bodies);
`Document.from_file` / `Document.load` attach the catalog. Consequences:

* `manipulate.EditSession` needs **no change** — its `doc.dec` /
  `ObjectEncoder(decoder=doc.dec)` pick up the catalog, `_orig_bytes_check`
  passes for the ES elements, and an ES field is editable by JSON path
  (`m_cellList.value.m_cells[0].value.m_entityMap[0].second.m_blob.fields
  .ASHRAETableName = "SR3-2"` re-frames rme fitting 392203; the untouched
  analytical cache still reads "SR3-1" — a derived cache, like a renamed
  panel's circuit descriptions).
* Without a catalog the decoder now fails **loudly and truthfully** at the
  entity body ("ES entity blob: schema … not in the in-model catalog"), never
  again with the bogus "unknown class 0x2314".
* Creating a NEW schema/entity (authoring) is not needed for round-trip and
  is out of scope: it would additionally require appending the entry to
  `m_schemaUsageMap` and `EStorageTracking` inside `Global/Latest`
  (`ADocument` re-serialization).

## 8 · Confidence / unknowns

| claim | status |
|---|---|
| token = `i32 pid` + 16-byte schema GUID; `0x2314` is no class | **V** (all 6 files; per-file "class" words = schema GUID prefixes) |
| catalog = `ESSchemaStorage.m_schemaUsageMap` in `Global/Latest`, decodable with the archive schema; entries contiguous; count field matches | **V** (rme 2, rstbasic 2, dach 175 — all decoded to the byte; §2.1 hexdump) |
| body deferred into the record queue (never inline); nested entities likewise | **V** (queue-position proofs, §1 and §4.3) |
| body = field values in `entryIndex` order, no header | **V** (record-end delimited bodies; whole-record byte-exact re-encode of 2,921 records) |
| type table (§4.2) | **V** for every type in the corpus; `short`/`float`/`int64`/`unsigned*` are codebook extrapolations **[H]** (no sample) |
| `EStorageTracking` = top-level schema → host element ids | **V** (rme 657/514 == the failing records) |
| the tracking table can hold GUIDs the catalog does not (2024 base: 5 of 7), verified by count + the file's own class decode | **V** (§2.1c); *which* Revit feature owns those five GUIDs is **unknown** (U7) |
| entity-free files have an empty map (not an unfound one) | **V** (no schema/type strings anywhere in their `Global/Latest`; GUID-free scan proven on rme/rstbasic) |
| a null entity (pid 0) is 4 bytes with no GUID | **V** (`AnalysisResult.LoadCase`, `LARData.AnalysisInfoPending`) |

**Unknowns / open items.** U1 `pid > 0` (indexed) entity tokens and
weak/back-references to entities: never observed; the codec accepts a
positive pid like −1 and would flag a bare backref — behaviour unverified.
U2 `bool` values other than 0/1 and non-canonical NaN doubles would break
byte-exactness (none in the corpus; `verify_document` would catch one). U3
Access-level enum names beyond 1/2 (only Public/Vendor observed). U4
Whether Revit's ES also stores entities on `Global/*` objects outside the
partitions (e.g. a `DataStorage`-like AppInfo) — none referenced by the
tracking table beyond partition elements; the ADocument's own
`m_pAppInfoManager` graph was not decoded here. U5 Authoring a NEW schema
(map + tracking append, §7) — not implemented, not required for edit
fidelity. U6 The GUID-free locator's regex is bounded (`max_hits`); a
pathological file could need the seeded path. U7 The five structured,
uncatalogued schema GUIDs the 2024 base's tracking table leads with (§2.1c:
two of them → the `ProjectInfo` element, which carries no entity; absent by
2025): Revit-internal by every sign, owner feature unnamed in the bytes;
whether Autodesk's 2024 samples carry them too is unmeasured.

## 9 · Reproduction

```
.venv/bin/python -m rvt.estorage rmebasicsampleproject --report --roundtrip
.venv/bin/python -m rvt.estorage samples/dach-sample-project.rvt --roundtrip
.venv/bin/python -m rvt.estorage rstbasicsampleproject --report --walk
.venv/bin/python -m pytest tests/test_estorage.py -q            # 14 (1 slow ~40 s)
RVT_SKIP_LARGE=1 .venv/bin/python -m pytest tests/test_estorage.py -q -m "not slow"
```

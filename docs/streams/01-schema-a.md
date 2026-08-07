# `Formats/Latest` — the serialized class dictionary (schema A)

Agent: `schema-a` · Source of truth: `src/rvt/schema_a.py` ·
Output: `extracted/_schema/schema_a.json` + `schema_a_meta.json`

## Summary

- `Formats/Latest` inflates to a **498,766-byte** blob, **byte-identical in all
  six sample files** (inflated sha256 prefix `36c6ea9711ced9ee`, raw-stream
  sha256 prefix `8f551c2218c6e015`). It is a per-build constant (Revit 2026,
  build 20250227_1515), not per-project data. `[verified]`
- It is a flat sequence of **class records** (Autodesk's C++ serialization
  RTTI): class name → optional parent class → version → ordered field list
  with type descriptors → per-class GUID table. Every class definition, top
  level or inline, is assigned the **next sequential type id starting at
  0x0c**; later references use that u16 id. `[verified: 877 backward
  references, 0 unresolved]`
- The grammar below consumes **[0x00000, 0x21e61) = 138,849 bytes with zero
  gaps** and yields **1,150 class definitions** (727 top-level + 423 inline),
  **3,111 fields**, type ids 0x0c..0x489.
- **From 0x21e61 to EOF (359,917 bytes, 72%) the inflated bytes are
  intrinsically corrupted** — identifiers with dropped characters, letter
  runs, mis-aligned framing. This is a property of the payload Revit wrote
  (identical in all six files, two independent inflaters agree, contiguous
  CFB sectors), not an extraction artifact. See §7. `[verified]`

## 1. Container / how to obtain the bytes

| Item | Value | Evidence |
|---|---|---|
| OLE stream | `Formats/Latest`, 182,953 bytes, contiguous 45×4096-byte sectors starting sector 9 (racbasic) | `olefile` FAT walk |
| Encoding | gzip header (10 bytes) + raw deflate; trailer absent/corrupt → skip 10 bytes, `zlib.decompressobj(-15)` | `tools/scan_gzip.py`; deflate reaches clean EOF after 182,241 bytes |
| Inflated size | 498,766 bytes | zlib raw-inflate **and** py `inflate64` produce byte-identical output |
| After deflate | 712 trailing bytes: `16 22 85 26 d5 93 07 00`, 412 zeros, ~280 high-entropy bytes (not a gzip trailer; not CRC32/Adler32 of any prefix) | see §8 unknowns |
| Cross-file identity | inflated sha256 `36c6ea97…` in all six | `schema_a.py` prints this |

## 2. Record grammar (all integers little-endian)

```
stream        := class_record*                       (until EOF)

class_record  := u16 zero_prefix           (always 0x0000)
                 u16 name_len
                 u8[name_len] name          (ASCII, e.g. "ADocument", "std::pair< ElementId, int >")
                 u16 parent_ref             0x0000       → no parent
                                            0x8000 | id  → parent is DEFINED INLINE: a full
                                                           class_record follows immediately; it
                                                           receives type id `id` (== running counter)
                                            id           → reference to an already-defined class
                 u32 version                (class serialization version; ADocument = 2662)
                 u32 field_count
                 field[field_count]
                 u32 guid_count             (usually 0)
                 u8[16] guid[guid_count]    (per-class static GUID table)

field         := u32 name_len
                 u8[name_len] name          (member name, e.g. "m_pACD", "first", "second")
                 descriptor

descriptor    := u8 kind, u8 flags, u16 zero       (the 4-byte "tag", e.g. 0e 03 00 00)
                 [ if flags high nibble == 0x1 : u32 array_count ]
                 [ if kind == 0x0e and (flags & 0x0f) == 0 :
                       u16 type_ref     (0x8000|id → inline class_record defining
                                         that type follows right here; else a
                                         reference to an existing type id) ]
                 [ if kind == 0x0d : field  (anonymous element sub-field; its
                                             name is a single space " ")
                     + if that element is a class-typed 0x0e :
                           u16 type_ref (repeats the element's type id) ]
```

### 2.1 Type-id assignment `[verified]`

Every class **definition** (top-level or inline, in the exact order the
definitions begin in the stream) receives the next id from a counter starting
at **0x0c**. A definition site is written as a u16 reference with bit 0x8000
set and the low 15 bits equal to the id being assigned; the class record that
immediately follows *is* that definition. Plain u16 references always point
**backwards** to an already-assigned id (877 of 877 resolve; e.g. `14 00` →
`ElementId`, defined at 0x137 as id 0x14). Ids 0x00–0x0b never occur as class
ids — they are the primitive kind codes below. Sequence check:
A3PartyAImage=0x0c, A3PartyObject=0x0d, A3PartySECImage=0x0e,
A3PartySECJpeg=0x0f, ACDPtrWrapper=0x10, ADTGridImportVocabulary=0x11,
ImportVocabulary=0x12, std::pair< ElementId, int >=0x13, ElementId=0x14,
Identifier=0x15, …, AppInfo=0x1b (referenced later as `1b 00` by
APIAppInfo's parent field), Element=0x25 (referenced by dozens of classes as
`25 00`).

### 2.2 Descriptor tag semantics

The 4-byte tag = `kind flags 00 00`.

**kind** (byte 0) — full histogram over the clean region:

| kind | meaning | example fields | count |
|---|---|---|---|
| 0x01 | bool | `ADocument.m_bIsCoreDocument`, `Element.m_locked` | 373 |
| 0x02 | byte/uint8 `[hypothesis]` | `ByteData.m_data`, `ARasterImage.m_compressedImage` (byte containers) | 8 |
| 0x03 | uint16 `[hypothesis]` | `UserID.m_id`, `Viewer.m_viewerFlags` | 4 |
| 0x04 | int32 | `std::pair< ElementId, int >.second`, `ImportVocabulary.m_paramtersType` | 580 |
| 0x05 | uint32 | `ATime.m_msb/m_lsb`, `AnalysisDisplayColorEntry.m_color` | 22 |
| 0x06 | float | `APropertyFloat.m_value`, `APropertyFloat3.m_value` (x3 array) | 4 |
| 0x07 | double | `APropertyDouble*.m_value`, `Trf.m_or` (x3), `ADTGridTextLocation.m_location` (x3) | 445 |
| 0x08 | AString | `AStringWrapper.m_str`, `ADTGridTextLocation.m_text`; flags always 0x60 | 156 |
| 0x09 | GUID (16 bytes) | `GUIDvalue.m_guid` (the only instance) | 1 |
| 0x0a | class-definition ref `[hypothesis]` | `ClassDefinitionRef.m_ref` (only instance) | 1 |
| 0x0b | int64 | `Identifier.m_id64`, `ATFRevitObjectId.m_hashNative` | 14 |
| 0x0c | (never observed — 0x0c is the first user type id) | — | 0 |
| 0x0d | inline array/vector whose element is described by an anonymous sub-field | `Trf.m_3x3` = 3× (anon " " = double[3]); `Dimension.m_refPnts` = container of double[3] | 19 |
| 0x0e | user class type | `ElementId.m_id` → Identifier, `ADocument.m_elemTable` (ptr) | 1,507 |

**flags** (byte 1) — high nibble = shape, low nibble = ownership:

| flags | meaning | payload after tag | count |
|---|---|---|---|
| 0x00 | value / embedded | typed 0x0e → u16 type_ref | 1,151 |
| 0x01 | pointer (variant 1; polymorphic, untyped) | none | 212 |
| 0x02 | pointer (variant 2, "owned" — every ADocument top-level member) | none | 56 |
| 0x03 | pointer (variant 3, back/weak — `ACDPtrWrapper.m_pACD`, `ControlledDocAccess.m_pDoc`, `DimSegOwnedByDimension.m_pOwningDimension`) | none | 38 |
| 0x10 | fixed-size array | u32 count (+ u16 type_ref if 0x0e) | 168 |
| 0x11 | fixed-size array of pointers | u32 count | 5 |
| 0x50 | variable container (list/map/set), by value; maps use a `std::pair< K, V >` element class | typed 0x0e → u16 type_ref | 428 |
| 0x51 | variable container of pointers (`ADocument.m_appInfoArr`, `Element.m_constrInfo`) | none | 74 |
| 0x60 | string (only ever with kind 0x08) | none | 156 |

Rule: a u16 type_ref follows only when `kind == 0x0e` and the low nibble of
flags is 0 (value/typed). Pointer flavours (01/02/03/51) never carry a static
type — the target class is discovered at runtime. The 20 most-referenced type
strings (clean region): ElementId 615, XYZ 54, Trf 21, GUIDvalue 16,
std::pair< ElementId, int > 10, AStringWrapper 10, std::pair< ElementId,
ElementId > 9, ForgeTypeId 8, GeomRef 7, EndInfo 6, std::pair< int, int > 6,
EpisodeId 6, RepeaterCoordinates 6, FormatOptions 5, std::pair< int,
ElementId > 5, std::pair< ElementId, RbsOffsetSetWrapper > 4, ForeignElemRef
4, NumberingParameter 4, std::pair< ElementId, ElectricalPerPhaseData > 4,
ParamStorage 4.

### 2.3 C++ type strings and nesting

Container element types are **real classes named by their C++ template
string** — `std::pair< ElementId, int >`, `std::pair< ForgeTypeId,
FormatOptions >`, `std::pair< AString, RecentSymbolList >` — defined inline
at first use with two fields literally named `first` and `second`, whose
descriptors nest arbitrarily (a `first` of type `ElementId` triggers the
inline definition of `ElementId`, whose `m_id` triggers `Identifier`).
Max observed nesting depth is 6. There is no separate string table: the
template spelling *is* the class name (note Autodesk's spacing:
`std::pair< A, B >`).

### 2.4 Inheritance `[verified]`

`parent_ref` encodes single inheritance: 698 of 1,150 classes have a parent
(180 define the parent inline at first use, 518 reference an existing id).
Most-derived-from bases: Element 89, GeomStep 63, Cell 54, AppInfo 32,
Symbol 27, PostedWarning 24, AProperty 18, DBView 14. Example: `APIAppInfo`
record body starts `1b 00 0d 00 00 00 …` → parent id 0x1b = AppInfo,
version 13. Note the reader must know a parent was declared to decode: e.g.
"ATFProvenanceCell" (17 chars) is immediately followed by parent ref `45 00`
(= ATFProvenanceBaseCell, id 0x45 = ASCII 'E' — the on-disk bytes
misleadingly read "ATFProvenanceCellE").

### 2.5 Per-class GUID table

After the fields comes `u32 guid_count` then `guid_count` 16-byte GUIDs. It is
0 for 1,124 classes; non-zero for 26, e.g. ADocument 1509, AUnits 13,
WitnessRefInfo 3, Element 2, AppInfoManager 2, HostObjAttr 1. Verified by
exact-fit: ADocument's 1,509 × 16 bytes end at 0x649b, immediately followed by
the next record `00 00 0a 00 "APIAppInfo"`. `[hypothesis]` these are static
class-level GUID lists (format/upgrade identities; cf. ADocument.m_executedUpgrades
of type GUIDvalue). ADocument entry[1] is the all-zero GUID.

## 3. ADocument ↔ top-level streams (keystone mapping) `[verified]`

`ADocument` @0x3b8, id 0x1c, **version 2662**, 19 fields, no parent:

| # | tag | field | type |
|---|---|---|---|
| 1 | `0e 02` | m_elemTable | owned ptr → `Global/ElemTable` |
| 2 | `0e 51` | m_appInfoArr | container of AppInfo ptrs |
| 3 | `0e 02` | m_oContentTable | owned ptr → `Global/ContentDocuments` |
| 4 | `0e 03` | m_pHostDocument | weak ptr |
| 5 | `0e 02` | m_pAppInfoManager | owned ptr |
| 6 | `0e 02` | m_pStyleSettings | owned ptr |
| 7 | `0e 02` | m_pHistory | owned ptr → `Global/History` |
| 8 | `0e 02` | m_pSteelModelInfo | owned ptr |
| 9 | `0e 02` | m_pPartitionTable | owned ptr → `Global/PartitionTable` |
| 10 | `0e 01` | m_oNobleSecondaryData | ptr |
| 11 | `0e 00`→0x14 | m_ownerFamilyId | ElementId |
| 12 | `0e 00`→0x14 | m_ownerFamilyContainingGroupId | ElementId |
| 13 | `0e 00`→0x801d | m_devBranchInfo | DevBranchInfo (inline def: m_devBranchId int32, m_syncVersion int32) |
| 14–16 | `01 00` | m_groupFile, m_corruptDocument, m_bIsCoreDocument | bool |
| 17 | `0e 50`→0x801e | m_executedUpgrades | container of GUIDvalue (kind 0x09) |
| 18 | `0e 50`→0x801f | m_storedByRevitBuild | container of AStringWrapper |
| 19 | `0e 02` | m_oExServicesUsed | owned ptr |
| — | `e5 05 00 00` | guid table | 1,509 GUIDs (24,144 bytes, 0x64b–0x649b) |

## 4. Worked examples (hex-annotated)

### 4.1 `ACDPtrWrapper` — smallest complete record (0x7f–0xab)

```
0x07f  00 00                      zero_prefix
0x081  0d 00                      name_len = 13
0x083  "ACDPtrWrapper"
0x090  00 00                      parent_ref = none
0x092  01 00 00 00                version = 1
0x096  01 00 00 00                field_count = 1
0x09a  06 00 00 00                field name_len = 6
0x09e  "m_pACD"
0x0a4  0e 03 00 00                descriptor: kind 0x0e (class), flags 0x03 (weak ptr) → no type_ref
0x0a8  00 00 00 00                guid_count = 0            (record ends 0x0ac)
```
ACDPtrWrapper is the 5th definition → type id 0x10.

### 4.2 `ADTGridImportVocabulary` — inline parent + nested container element classes (0xac–0x35c)

```
0x0ac  00 00 | 17 00 "ADTGridImportVocabulary"                      (id 0x11)
0x0c5  12 80                    parent_ref = DEFINE inline, id 0x12
0x0c7    00 00 | 10 00 "ImportVocabulary"                            ← inline parent record begins
0x0d9    00 00                  ImportVocabulary parent = none
0x0db    02 00 00 00            version 2
0x0df    05 00 00 00            field_count 5
0x0e3    0e 00 00 00 "m_mapIntValues"
0x0f5    0e 50 00 00            kind class, flags 0x50 container(value)
0x0f9    13 80                  type_ref = DEFINE inline id 0x13
0x0fb      00 00 | 1b 00 "std::pair< ElementId, int >"               ← id 0x13
0x11a      00 00 | 00 00 00 00 | 02 00 00 00      parent none, v0, 2 fields
0x124      05 00 00 00 "first"  0e 00 00 00  14 80                     value of type: DEFINE id 0x14
0x134        00 00 | 09 00 "ElementId" | 00 00 | 01 00 00 00 | 01 00 00 00     ← id 0x14, v1, 1 field
0x14d        04 00 00 00 "m_id"  0e 00 00 00  15 80                    value of type: DEFINE id 0x15
0x15c          00 00 | 0a 00 "Identifier" | 00 00 | 02 00 00 00 | 01 00 00 00  ← id 0x15, v2, 1 field
0x173          06 00 00 00 "m_id64"  0b 00 00 00                     int64
0x181          00 00 00 00      Identifier guid_count 0   → Identifier done
0x185        00 00 00 00        ElementId guid_count 0    → ElementId done (first is done)
0x189      06 00 00 00 "second"  04 00 00 00                          int32
0x197      00 00 00 00          pair guid_count 0          → std::pair< ElementId, int > done
0x19b    0e 00 00 00 "m_mapDblValues" 0e 50 00 00 16 80 … std::pair< ElementId, double >
                                (first = 0e 00 00 00 14 00 → REFERENCE to ElementId, no redefinition;
                                 second = 07 00 00 00 double)
0x1ff    "m_mapStrValues"  → 17 80 std::pair< ElementId, AString >  (second = 08 60 00 00)
0x265    "m_mapIdsValues"  → 18 80 std::pair< ElementId, ElementId > (both 0e 00 00 00 14 00)
0x2cf    0f 00 00 00 "m_paramtersType" 04 00 00 00                       int32
0x2e4    00 00 00 00            ImportVocabulary guid_count 0  → parent done
0x2e8  01 00 00 00              ADTGridImportVocabulary version 1
0x2ec  01 00 00 00              field_count 1
0x2f0  11 00 00 00 "m_arrTextLocation"
0x305  0e 50 00 00  19 80         container of ADTGridTextLocation (DEFINE id 0x19)
0x30f    00 00 | 13 00 "ADTGridTextLocation" | 00 00 | 01 00 00 00 | 02 00 00 00
0x330    0a 00 00 00 "m_location" 07 10 00 00 03 00 00 00    double, fixed array, count 3
0x346    06 00 00 00 "m_text"     08 60 00 00                AString
0x354    00 00 00 00            ADTGridTextLocation guid_count 0
0x358  00 00 00 00              ADTGridImportVocabulary guid_count 0   (record ends 0x35c)
```
This one example demonstrates: inline parent definition, container types
whose element is a template-named `std::pair<>` class with `first`/`second`,
three levels of nested inline definition, back-references by u16 id, the
kind-0x07/flag-0x10 fixed array (`double[3]`), and the string kind.

### 4.3 `ADocument` — large version, mixed field kinds, GUID trailer (0x3b8–0x649b)

```
0x3b8  00 00 | 09 00 "ADocument"                (id 0x1c)
0x3c5  00 00                    parent none
0x3c7  66 0a 00 00              version = 0x0a66 = 2662
0x3cb  13 00 00 00              field_count = 19
0x3cf  0b 00 00 00 "m_elemTable"       0e 02 00 00     owned ptr (no static type)
0x3e2  0c 00 00 00 "m_appInfoArr"      0e 51 00 00     container of ptrs
0x3f6  0f 00 00 00 "m_oContentTable"   0e 02 00 00
0x40d  0f 00 00 00 "m_pHostDocument"   0e 03 00 00     weak ptr
 …
0x4b6  0f 00 00 00 "m_ownerFamilyId"   0e 00 00 00 14 00   value, type_ref 0x14 = ElementId
0x4f7  0f 00 00 00 "m_devBranchInfo"   0e 00 00 00 1d 80   → inline DevBranchInfo (id 0x1d)
 …
0x62e  11 00 00 00 "m_oExServicesUsed" 0e 02 00 00     owned ptr
0x647  e5 05 00 00              guid_count = 1509
0x64b  3f f7 91 9e ae 38 83 4c ad 86 16 9d 1d b1 7b 86    guid[0]
0x65b  00 × 16                                            guid[1] (all-zero GUID)
 …     1,509 × 16 = 24,144 bytes
0x649b (record ends; next record: 00 00 0a 00 "APIAppInfo" 1b 00 …  parent = AppInfo 0x1b)
```

### 4.4 `Trf` — kind 0x0d inline array (0x713d–0x7180)

```
0x713d 00 00 | 03 00 "Trf" | 00 00 | 01 00 00 00 | 02 00 00 00       (id 0x4f, v1, 2 fields)
0x714e 05 00 00 00 "m_3x3"
0x7157 0d 10 00 00              kind 0x0d (inline array), flags 0x10 (fixed) →
0x715b 03 00 00 00                array_count = 3   (3 rows)
0x715f 01 00 00 00 20               anonymous element sub-field: name_len 1, name " "
0x7164 07 10 00 00 03 00 00 00      element descriptor: double, fixed array, count 3
                                (element is a primitive → no trailing type_ref)  ⇒ double[3][3]
0x716c 04 00 00 00 "m_or"  07 10 00 00 03 00 00 00                 double[3]
0x717c 00 00 00 00              guid_count 0
```
When a 0x0d's element sub-field is itself class-typed (e.g.
`AnalyticalModelFamilyInstance.m_projection` = 2 × array-of-2-ElementId), a
trailing u16 repeating the element's type id follows the element descriptor
(`… 0e 10 00 00 02 00 00 00 14 00 | 14 00`).

## 5. Statistics (clean region 0x00000–0x21e60)

| Metric | Value |
|---|---|
| Class definitions | 1,150 (727 top-level, 423 inline; nesting depth ≤ 6) |
| Fields | 3,111 (max 48 per class, mean 2.7) |
| Type ids assigned | 0x0c … 0x489 (0x48a was in progress at the desync) |
| Version distribution | v1: 469, v0: 318, v2: 144, v3: 56 … max 2662 (ADocument) |
| Classes with parent | 698 (61%) — inheritance IS encoded |
| Type references | 243 inline definitions + 877 backward u16 refs, 0 unresolved |
| Per-class GUID tables | 26 classes, 1,555 GUIDs total |
| Descriptor pad u16 | 0 in 100% of 4,300 descriptors |

## 6. How to reuse this

`.venv/bin/python src/rvt/schema_a.py` re-runs the parse, prints the summary,
histogram, desync report and cross-file hash check, and rewrites
`extracted/_schema/schema_a.json` (list of class records: `class_name`,
`type_id`, `offset`, `parent`/`parent_id`/`parent_inline`, `version`,
`fields[{name, tag_hex, kind, flags, kind_name, flag_name, type_string,
type_id, array_count, element…}]`, `guids`) and `schema_a_meta.json`
(parse metadata + corruption forensics + salvage candidates). To resolve any
u16 type id: index into definition order (`type_id`); ids < 0x0c are the
primitive kinds in §2.2.

## 7. The corruption boundary — why the parser cannot reach EOF

The grammar consumes the stream perfectly up to **0x21e61** (the start of
field 4 of `DDGraphSerializable`, id 0x48a, whose header validly declares 5
fields; fields 1–3 `m_accMatrix` (bool container), `m_depthFirstFields`,
`m_targetNames` (both containers of AStringWrapper 0x1f) parse cleanly and
end at 0x21e61). From 0x21e61 on the bytes are **damaged data**, not a new
encoding:

```
021e5b: 0e 50 00 00 1f 00                       ← last good descriptor (m_targetNames)
021e61: 0a 00 00 00 6d 5f 6e 43 6c 00 13 00 6d 61   field name len 10 → "m_nCl\0\x13\0ma"  ✗
021e6f: 0e 01 00 00 19 00 00 6d 00 00 12 00 00 00 6d 5f 70 56 69 65 77 66  "m_pViewf"
021e85: 00 00 02 00 00 00 0f 00 "temFa_idLoa" 0d 00 00 00 "m_t\x1etemFa_idt_beamEnd" 04 00 00 00 …
        "m_headeargiry" 0e 01 00 72 e0 83 00 00 0d 00 "Wal" 00…  "CutoutSkk" … "closedCueaPlan" … "Templegore"
tail:   "…cz\0t_\0sDBWithDatu_t\x1d\0Peoies\0coneeoiettttt…Wid\0ekF\0ls\0NshErt, ntI…std::pair< ntI, ntI >, XYZ…"
```

Evidence that this is intrinsic to the payload and not an artifact of our
extraction or decompression:

1. **Structural statistics diverge sharply.** Clean region [0,0x21e61): 0
   letter-runs ≥ 4, printable ratio 0.549, entropy 5.68 b/B. Tail
   [0x21e61,EOF): 11.3 letter-runs ≥ 4 per KB (`tttt`, `yyyyyyy`,
   `OOOOOOOOOOOO`, `rrrrrr`), printable 0.753, entropy 5.21. Class names in
   the clean region contain no repeated-letter runs at all.
2. **Identifiers are damaged, not encoded**: real names appear with
   characters missing/inserted ("SystemFamily…"→"temFa_", "CutoutSketch"→
   "CutoutSkk", "TemplateCategory"→"Templegore"), yet grammar residue
   (u32 name lengths, `0e 50 00 00`, `04 00 00 00`, inline type refs
   `e0 83 00 00`, `std::pair< …, XYZ`) is interleaved — the same record
   grammar continues underneath the damage. Some islands are intact
   ("ContinuousRailJoinInfo", "CoverType", "DBView3dEnergyAnalysis" at
   0x22800/0x2379c/0x2514c — three copies of one definition, itself a sign
   of damage).
3. **Two independent inflaters agree**: zlib raw inflate (wbits −15) and the
   independent `inflate64` C implementation produce byte-identical 498,766-byte
   output; the deflate stream ends at a clean end-of-stream marker after
   182,241 bytes (a randomly-corrupted bitstream cannot decode ~117 KB
   further without an invalid code). A control test confirmed the two
   decoders diverge on genuine Deflate64 input, so the stream is plain
   deflate and its output is what Autodesk fed the compressor.
4. **The OLE stream is contiguous** on disk (single FAT run, sectors 9–53,
   matches `olefile` extraction byte-for-byte) and is **byte-identical in all
   six sample files** → this exact payload is what Revit 2026 emits.
5. The damaged output is **not** an LZ literal stream of our own decoder's
   history: mangled fragments ("temFa_id", "closedCueaPlan") do not exist in
   the preceding 32 KB window, and long zero runs / u32 framing survive as
   literals, which an LZ stage would have compressed away.

Compressed-side location: the first damaged output byte is produced while
consuming raw stream offset ≈ 0xfd82 (≈ 64.9 KB into the 182,953-byte
stream). `[hypothesis]` The build's embedded schema resource is itself
damaged from that point (a defective generation step upstream of the
per-file gzip); Revit does not need to re-read its own build's schema, so the
defect can ship unnoticed. Practical impact: **classes defined after
DDGraphSerializable (an estimated ~3,000+ more, including Wall/Level/View
element classes hinted by tail fragments) are NOT recoverable from this
release's `Formats/Latest`**; their names/fields must come from other
evidence (the `Global/*` object graphs themselves, or another Revit
release's schema stream if intact).

`schema_a.py` stops there deliberately, prints the offset + hex context +
statistics above, and additionally emits 298 heuristically-salvaged (mostly
mangled) class-name candidates from the tail in `schema_a_meta.json` for
whatever forensic value they hold.

## 8. Unknowns

- Semantics of pointer flavours 0x01 vs 0x02 vs 0x03 (owned/weak inferred
  from usage only). `[hypothesis]`
- Exact primitive widths of kinds 0x02, 0x03, 0x05, 0x0a; kind 0x0c never seen.
- Meaning of the class `u32 version` (per-class serialization version is the
  best fit: ADocument 2662, Element 21, AUnits 49) and of the per-class GUID
  tables (26 classes; ADocument's 1,509 include one all-zero entry).
- The 712-byte post-deflate trailer (`16 22 85 26 d5 93 07 00`, 412 zeros,
  ~280 random-looking bytes) — not CRC32/Adler32 of the inflated data or any
  prefix; not a gzip trailer. Out of slice (see `docs/inbox/schema-a.md`).
- Root cause and true extent of the tail corruption; whether other Revit
  releases carry an intact schema. The keystone mapping needed by this
  project (ADocument → `Global/*` streams; Element base layout with
  m_id/m_famId/…; ElementId → Identifier.m_id64) all lies in the **clean**
  region and is fully decoded.

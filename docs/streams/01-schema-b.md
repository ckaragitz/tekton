# `Formats/Latest` — schema stream decode (method B: structural / statistical)

Agent `schema-b`. Independent cross-validation decode of the per-release schema
blob. **Method:** no knowledge of the format was assumed. The grammar was
derived from (1) length-prefixed identifier harvesting, (2) record-boundary
alignment (records must tile the byte stream with zero gaps), and (3) gap
statistics between consecutive field names, which reveal the byte length of
every field-descriptor tag. Scalar type codes were then calibrated
*statistically* using the synthetic template classes the schema defines for
itself (`std::pair< ElementId, int >` names the C++ type of its own `second`
field), and confirmed against field-naming conventions (`m_pX` / `m_bX`).

Code: `src/rvt/schema_b.py` → emits `extracted/_schema/schema_b.json`.
Subject: `extracted/racbasicsampleproject/Formats__Latest.gz/000.bin`
(498,766 bytes inflated; sha256 `36c6ea9711ced9ee…`; **byte-identical in all
six samples**).

---

## 1. Headline

| Fact | Value | Confidence |
|---|---|---|
| Stream is a flat sequence of class records, top-level classes in **alphabetical order** (A3Party… → DDGraphSerializable) | first-letter histogram A:303, B:78, C:315, D:31 among top-level | verified |
| Faithfully-decodable prefix | bytes `0x00000–0x21DFA` (138,746 B, **27.8 %**) = **1,150 class records** (727 top-level + 423 inline), 3,111 fields; plus the header/first three fields of record 1,151 (`DDGraphSerializable`) up to `~0x21E64` | verified |
| Records tile the faithful prefix with **zero gap bytes**; every top-level record starts where the previous one ends | tiling check: sum of record spans = 138,746 = prefix length | verified |
| Class references are **ordinals**, not byte offsets; ordinals start at **12** and increase by 1 in *definition order*; a reference with bit 15 set (`0x8000\|N`) means "class N is defined inline right here" | **423/423** flagged references equal 12 + definition-index (independent internal consistency proof) | verified |
| Remaining **72.2 %** (`0x21DFA–EOF`, 360,020 B) is **scrambled at the source** — see §7. Class records for names alphabetically after `DDG…` are **not recoverable** from this stream. | density profile + LZ token forensics + recompression + cross-version comparison | verified (phenomenon); cause = hypothesis |

## 2. Record grammar

All integers little-endian.

```
stream   := record*                                   (top-level classes)
record   := u16  marker = 0x0000
            u16  nameLen ; name[nameLen]                (ASCII, C++ class name;
                                                        template instantiations
                                                        spelled out, e.g.
                                                        "std::pair< ElementId, int >")
            u16  baseRef                                (0 = no base class;
                                                        else ordinal, and if bit15
                                                        set the base class record
                                                        follows inline right here)
            [record]                                    only when baseRef & 0x8000
            u32  version                                (small per-class serial;
                                                        histogram 1:469, 0:318, 2:144)
            u32  fieldCount ; field[fieldCount]
            u32  nGuid ; guid[nGuid]                    (16-byte GUIDs; 0 for 1,124
                                                        of 1,150 records)
field    := u32 nameLen ; name[nameLen] ; typedesc
typedesc := u8 kind, u8 mod, u16 pad(=0), then payload by (kind,mod) — §3
```

### 2.1 Worked example — the first four records (`0x00000–0x0007E`)

```
000000: 00 00                                  marker
000002: 0d 00 "A3PartyAImage"                nameLen 13, name             (ordinal 12)
000011: 0d 80                                  baseRef = 0x800D → base class
                                               ordinal 13 defined INLINE:
000013:   00 00 | 0d 00 "A3PartyObject"        nested record marker+name  (ordinal 13)
000024:   00 00                                its baseRef = none
000026:   00 00 00 00 | 00 00 00 00            version 0, fieldCount 0
00002e:   00 00 00 00                          nGuid 0            (nested record ends)
000032: 00 00 00 00 | 00 00 00 00            back in A3PartyAImage: version 0, fieldCount 0
00003a: 00 00 00 00                            nGuid 0            (ends 0x3E)
00003e: 00 00 | 0f 00 "A3PartySECImage"      next record (ordinal 14)
000051: 0d 00                                  baseRef = 13 (already defined,
                                               NO 0x8000 flag) = A3PartyObject
000053: 00 00 00 00 | 00 00 00 00 | 00 00 00 00     version, fieldCount, nGuid
00005f: 00 00 | 0e 00 "A3PartySECJpeg" ...   (ordinal 15) baseRef 13, ends 0x7E
```

The three A3Party image classes all derive from ordinal 13 (`A3PartyObject`);
the first spells the base out inline (flagged), the later two reference it by
bare ordinal `0d 00`. This is the entire inheritance mechanism.

### 2.2 Worked example — a class with fields (`ACDPtrWrapper`, `0x7F–0xAB`)

```
00007f: 00 00 | 0d 00 "ACDPtrWrapper"        record start (ordinal 16)
000090: 00 00                                  baseRef none
000092: 01 00 00 00                            version 1
000096: 01 00 00 00                            fieldCount 1
00009a: 06 00 00 00 "m_pACD"                   field: u32 nameLen 6, name
0000a4: 0e 03 00 00                            typedesc: kind 0e (class), mod 03
                                               (pointer, no static class) — 4 B
0000a8: 00 00 00 00                            nGuid 0
0000ac: 00 00 | 17 00 "ADTGridImportVocabulary" ...   next record
```

### 2.3 Worked example — nested/inline definitions and containers

`ADTGridImportVocabulary` (ordinal 17) derives inline from
`ImportVocabulary` (ordinal 18, `12 80`), whose first field
`m_mapIntValues` has descriptor `0e 50 00 00 13 80` = container of class
ordinal 19 flagged inline → the synthetic pair class is defined right there:

```
0000f9: 0e 50 00 00                            kind class, mod container
0000fd: 13 80                                  element = ordinal 19, defined inline:
0000ff:   00 00 | 1b 00 "std::pair< ElementId, int >"          (ordinal 19)
00011e:   00 00 | 00 00 00 00 | 02 00 00 00   base none, version 0, 2 fields
000128:   05 00 00 00 "first" 0e 00 00 00 14 80   field first = class ord 20,
                                                    inline: ElementId (ord 20)
000137:     00 00 | 09 00 "ElementId" 00 00 | 01 00 00 00 | 01 00 00 00
                                                  ElementId v1, 1 field:
00014e:     04 00 00 00 "m_id" 0e 00 00 00 15 80    m_id = class ord 21,
                                                     inline: Identifier
00015c:       00 00 | 0a 00 "Identifier" 00 00 | 02 00 00 00 | 01 00 00 00
000174:       06 00 00 00 "m_id64" 0b 00 00 00       m_id64 : Int64 (kind 0b)
000182:       00 00 00 00                            Identifier nGuid 0
000186:     00 00 00 00                              ElementId nGuid 0
00018a:   06 00 00 00 "second" 04 00 00 00        second : int (kind 04)
000198:   00 00 00 00                              pair nGuid 0
00019c: 0e 00 00 00 "m_mapDblValues" ...          ImportVocabulary continues
```

`ElementId` is therefore ordinal 20 = **`0x14`**; every later `ElementId`
field in the schema is the 6-byte descriptor `0e 00 00 00 14 00` (735
`0e00` fields; ElementId is the most-referenced class, 611 refs).

## 3. Field descriptor / type-tag codebook

The descriptor is `u8 kind, u8 mod, u16 0`, then a payload determined by
`(kind, mod)`. Descriptor **byte lengths were established by gap statistics**
(distance from the end of one field name to the start of the next field's
`u32 nameLen`, across ~3,000 consecutive field pairs): scalar tags are 4 B
(gap 4), class-by-value 6 B (gap 6), fixed arrays add a `u32 count`, and any
larger gap is exactly a class-end trailer (`u32 nGuid=0`) or an inline
record — i.e. the model accounts for every gap byte.

### 3.1 Kind (low byte)

| kind | meaning | evidence | conf |
|---|---|---|---|
| `01` | `bool` | `std::pair< X, bool >.second` (2/2); `m_bIsCoreDocument`, `m_bLock…` (all `m_bX` names) | verified |
| `02` | 16-bit int / enum | `Dimension.m_flags`, `m_constrFlags`, `m_typeOfChange` (enum) | hypothesis |
| `03` | 32-bit long / enum | `UserID.m_id`, `m_nAtomType`, `m_viewerFlags` | hypothesis |
| `04` | `int` (also `unsigned int`) | pair GT: `int`→`0400` **26/26**, `unsigned int`→`0400` 1/1 | verified |
| `05` | `unsigned long` (Win32 = 32-bit) | pair GT: `unsigned long`→`0500` 1/1; `ATime.m_msb/m_lsb`, `m_color` | high |
| `06` | `float` | `APropertyFloat.m_value`, `APropertyFloat3.m_value` = `06 10 …count 3` | high |
| `07` | `double` | pair GT: `double`→`0700` **5/5**; `APropertyDouble1..3`, `m_location` `07 10 count 3` | verified |
| `08` | `AString` (always with mod `60`) | pair GT: `AString`→`0860` **12/12**; `AStringWrapper.m_str` | verified |
| `09` | GUID | `GUIDvalue.m_guid` (16-byte value) | high |
| `0a` | class-definition ref | `ClassDefinitionRef.m_ref` (1 occurrence) | hypothesis |
| `0b` | `Int64` | `Identifier.m_id64`, `Int64Wrapper`/`UInt64Wrapper`, `m_hashNative` | high |
| `0d` | *wrapped* type — carries a nested `typedesc` (see below) | `Trf.m_3x3` = `0d10 count3 … [07 10 count 3]` = double[3][3] | high |
| `0e` | **user class** — a `u16` class-ordinal reference follows | 1,150 records; refs resolve to defined classes | verified |

Kinds `00`, `0c` never occur; `0d`/`0e` never occur bare. `[hypothesis]`
kinds `00–0b` are exactly the ordinals `0..11` reserved below the first user
class (ordinal base 12) — i.e. built-in kinds and class ordinals share one
number space.

### 3.2 Modifier (high byte) and payload

| tag_hex | count | kind / mod | payload after the 4-byte head | examples |
|---|---:|---|---|---|
| `0e00` | 735 | class / by value | `u16 ref` (+ inline record if `ref&0x8000`) | `pair<>.first`, `ElementId.m_id` |
| `0400` | 534 | int / value | — | `pair<>.second`, `m_devBranchId` |
| `0e50` | 361 | class / container (vector/set/map) | `u16 ref` (+inline) | `m_mapIntValues` (elem = pair), `m_arrTextLocation` |
| `0100` | 354 | bool / value | — | `m_groupFile`, `m_corruptDocument` |
| `0700` | 311 | double / value | — | `APropertyDistance.m_value` |
| `0e01` | 212 | class / pointer, polymorphic (no static ref) | — | `m_oNobleSecondaryData`, `Element.m_pParamValueSet*` |
| `0860` | 156 | AString / str | — | `m_text`, `m_str` |
| `0710` | 108 | double / fixed array | `u32 count` | `m_location` (3), `APropertyDouble2` (2) |
| `0e51` | 74 | class / container of pointers | — | `m_appInfoArr`, `m_constrInfo` |
| `0e02` | 56 | class / pointer (owned) | — | `m_elemTable`, `m_pAppInfoManager` |
| `0e03` | 38 | class / pointer (back/weak) | — | `m_pACD`, `m_pADoc`, `m_pHostDocument` |
| `0450` | 26 | int / container | — | `m_rgColWidths` |
| `0410` | 20 | int / fixed array | `u32 count` | `Int64Wrapper.m_value` |
| `0500` | 20 | unsigned long / value | — | `ATime.m_msb`, `m_color` |
| `0e10` | 20 | class / fixed array | `u32 count`, `u16 ref` (+inline) | `DimSegInfo.m_values` (3 × ord 0xB4) |
| `0b00` | 14 | Int64 / value | — | `m_id64`, `m_hashNative` |
| `0d10` | 13 | wrapped / fixed array | `u32 count`, `u32 k(=1)`, `u8 0x20`, nested typedesc, then `u16 ref` again if the nested element is class-typed | `Trf.m_3x3` = 3 × double[3]; `m_projection` = 2 × ElementId[2] |
| `0750` | 12 | double / container | — | `m_setOffset` |
| `0110` | 10 | bool / fixed array | `u32 count` | `m_bLock` (3) |
| `0150` | 7 | bool / container | — | `m_useRanges` |
| `0d50` | 6 | wrapped / container | `u32 k`, `u8 0x20`, nested typedesc (+`u16 ref`) | `Dimension.m_refPnts` = container< double[3] > |
| `0e11` | 5 | class / fixed array of pointers | `u32 count` | `m_arrPhasingOverrides` (4) |
| `0250` | 4 | 16-bit / container | — | `ByteData.m_data`, `m_compressedImage` |
| `0200` | 4 | 16-bit / value | — | `Dimension.m_flags` |
| `0300` | 4 | long / value | — | `UserID.m_id` |
| `0600`,`0610` | 3 | float / value / array | (`u32 count`) | `APropertyFloat.m_value` |
| `0900`,`0550`,`0510`,`0a00` | 1 each | as kind table | | `m_guid`, `m_cells`, `m_fontColor`, `m_ref` |

The container kind (vector vs set vs map) is **not** encoded in the tag: a
map field is a container whose element class is a synthetic
`std::pair< K, V >`; sets/vectors are distinguished only by naming
(`m_map*`, `m_set*`, `m_arr*`, `m_vec*`) `[hypothesis]`.

### 3.3 Statistical corroboration (independent of the pair<> ground truth)

* Field names starting `m_p[A-Z]` carry a pointer tag (`0e01/02/03/51/11`)
  in **129/129** cases; `m_o[A-Z]` in **161/162**.
* Field names `m_b[A-Z]` carry `0100` (bool); `m_id`/`m_*Id` carry
  `0e00`→`ElementId` (53) or `0400` (17); `m_str*` carry `0860` (29/38).
* The pair<> ground truth is internally consistent with **zero conflicts**
  (`int`→`0400` in 26/26, `AString`→`0860` in 12/12, `ElementId`→`0e00` in
  34/34, `bool`→`0100` 2/2, `double`→`0700` 5/5).

## 4. Class inventory (faithful prefix)

* **1,150 classes** decoded: 727 top-level (alphabetical), 423 defined inline
  as the target of a flagged reference (base classes and field element types
  — including **77 synthetic `std::pair< … >`** instantiations and wrapper
  classes such as `AStringWrapper`, `ElementIdSetWrapperClass`).
* Ordinals **12 … 1,161** (`0x00C … 0x489`). `A3PartyAImage`=12,
  `A3PartyObject`=13, `ElementId`=20 (`0x14`), `Identifier`=21,
  `AppInfo`=27, `ADocument`=28, `GUIDvalue`=30, `AStringWrapper`=31.
* Coverage by name: `A3PartyAImage` (0x0) … `DC3DGraphicsSettings`
  (0x21DB1, last complete record) then `DDGraphSerializable` (0x21DFA,
  header + 3 of 5 fields intact). Everything alphabetically after `DDG…`
  lies in the degraded region.
* Most common rendered field types: `int` 534, `ElementId` 468, `bool` 354,
  `double` 311, untyped pointer `T*` 306, `AString` 156,
  `container< ElementId >` 129, `double[3]` 85, `container< T* >` 74,
  `XYZ` 45.
* Most referenced classes: `ElementId` 611, `XYZ` 54, `Trf` 21,
  `GUIDvalue` 16, `std::pair< ElementId, int >` 10.

### 4.1 `ADocument` (ordinal 28, offset `0x3B8`, version **2662**, 19 fields, 1,509 trailer GUIDs)

| field | tag | type | note |
|---|---|---|---|
| `m_elemTable` | `0e02` | owned ptr | ↔ stream `Global/ElemTable` |
| `m_appInfoArr` | `0e51` | container of ptrs | |
| `m_oContentTable` | `0e02` | owned ptr | ↔ `Global/ContentDocuments` |
| `m_pHostDocument` | `0e03` | back ptr | |
| `m_pAppInfoManager`, `m_pStyleSettings`, `m_pHistory`, `m_pSteelModelInfo`, `m_pPartitionTable` | `0e02` | owned ptrs | ↔ `Global/History`, `Global/PartitionTable` |
| `m_oNobleSecondaryData` | `0e01` | polymorphic obj | |
| `m_ownerFamilyId`, `m_ownerFamilyContainingGroupId` | `0e00` | `ElementId` | |
| `m_devBranchInfo` | `0e00` | `DevBranchInfo` (inline, ord 29) | |
| `m_groupFile`, `m_corruptDocument`, `m_bIsCoreDocument` | `0100` | bool | |
| `m_executedUpgrades` | `0e50` | container< `GUIDvalue` > | |
| `m_storedByRevitBuild` | `0e50` | container< `AStringWrapper` > | |
| `m_oExServicesUsed` | `0e02` | owned ptr | |

## 5. Reference / inheritance model

* **Inheritance**: single base per class via `u16 baseRef` (698 edges; 452
  root classes among the 1,150). Depth histogram: 0→452, 1→268, 2→273,
  3→117, 4→30, 5→9, 6→1. Most-derived-from bases: `Element` 89, `GeomStep`
  63, `Cell` 54, `AppInfo` 32, `Symbol` 27, `PostedWarning` 24.
  Evidence that references are **ordinals, not byte offsets**: `ElementId`
  is defined at byte `0x137` but referenced as `0x0014` (its ordinal 20)
  in 611 places; `AStringWrapper` defined at `0x603`, referenced as `0x001F`.
* **Definition-on-first-use**: the first mention of a class (as a base or as
  a field element type) carries `0x8000|ordinal` and its full record body
  follows immediately; every later mention is the bare ordinal. Hence the
  file order is: alphabetical top-level classes, each dragging in the closure
  of not-yet-defined dependencies. Verified by re-deriving each flagged
  ordinal as `12 + definition_index` — **423/423 match**.
* **Field references** (`0e00/0e50/0e10`) resolve the same way (`ref_class`
  in the JSON). Pointer kinds (`0e01/02/03/51/11`) carry **no** static class
  — the pointee is polymorphic at runtime.
* **Trailer GUIDs**: 26 classes carry a `nGuid > 0` list (1,555 GUIDs total,
  **all distinct**): `ADocument` 1,509; `AUnits` 13; `WitnessRefInfo` 3;
  `Element`, `Dimension`, `AppInfoManager`, `ParamElem`, `TableView`,
  `DBViewSchedule`, `ConnectorElem` 2 each; 17 classes with 1
  (`FormatOptions`, `HostObjAttr`, `DBView`, `GeomRef`, …). `[hypothesis]`
  per-class GUID identity / upgrade or extensible-storage ids; ADocument's
  1,509 may enumerate all GUID-tagged serializable classes. Sample
  (ADocument #1): `9e91f73f-38ae-4c83-ad86-169d1db17b86`; (Element):
  `dd085cde-53ef-4c37-8527-168cfbe42a1f`, `10618e58-79c7-48c0-84e9-720cb519117a`.

## 6. Agreement / self-verification metrics (computed without any other decode)

| metric | result |
|---|---|
| Byte tiling of faithful prefix by top-level records | **100 %** (138,746 / 138,746, zero gap bytes) |
| Flagged-reference ordinal cross-check (`0x8000\|N` ≟ 12+index) | **423 / 423** |
| A-CamelCase / type-string u16 identifiers in prefix accounted for by a parsed record | **1,148 / 1,148** (0 unaccounted) |
| pair<> ground-truth self-consistency | 80 / 80 samples, 0 conflicts |
| `m_pX`→pointer-tag correlation | 129 / 129 |
| Six-sample stream identity | 6 / 6 identical sha256 |
| Descriptor `pad` u16 ≡ 0 across all 3,111 fields | 3,111 / 3,111 |

## 7. The degraded tail (72.2 % of the stream) — evidence and diagnosis

Observation: after `~0x21E64` the plaintext stops being a record stream and
becomes a soup of real identifier *fragments* (`m_headeargiry`,
`closedCueaPlan`, `CamInstWithDatuomE`) with byte runs (`MMMMMMM`,
`eeeeeee`) and verbatim duplicates. Quantified:

* Well-formed `u32 nameLen`+`m_…` field density per 8 KiB window drops from
  165–236 (prefix) to 13, 7, 9, 14, 6, 1, 0, … and never recovers to the end
  of the stream.
* The 38-byte record header of `DBView3dEnergyAnalysis` (true copy at
  `0x20A7E` in the prefix) recurs verbatim **≥ 30 times** between `0x22804`
  and `0x4F967`, each embedded in unrelated garbage; `CoverType` similarly ×12.
  A real class dictionary defines each class once — these are copy artefacts.
* A token-level deflate decode (`inflate_tokens.py`, our own implementation,
  output verified byte-identical to zlib) shows the compressed stream at
  that point is composed of many **short matches (len 3–13) at scattered
  distances** stitching fragments from all over the earlier window — the
  fingerprint of an LZ77 *encoder* whose match search operated on a stale /
  desynchronised window while emitting unverified matches.
* The gzip member's stored CRC/ISIZE **do not match** the inflated output
  (the known "corrupt trailer" of every Revit gzip stream) — consistent with
  a home-grown deflate writer rather than stock zlib.
* Re-compressing our inflated output with zlib level 3 reproduces the
  **first 41,152 compressed bytes exactly**, so the plaintext we obtain is
  bit-for-bit what the encoder intended for its early phase; divergence is
  encoder-version noise. The stream inflates to EOF with **no zlib error**
  and 712 trailing bytes — the bitstream is syntactically valid deflate.
* The **identical phenomenon** exists in the `Formats/Latest` of Revit
  family samples **2016 through 2026** (`vendor/phi-ag-rvt/examples`): dense
  field text for the first ~160–170 KB inflated, then collapse. A decade-old
  writer defect, not damage to our samples.
* Removing 1–32 bytes at any offset near the divergence, and re-decoding with
  distances offset by +32 KiB, both fail to restore structure — the
  corruption is not a simple insertion or a wrapped-window artefact.

**Conclusion `[hypothesis, strongly evidenced]`:** Revit's writer serialises
the schema correctly but compresses it with a defective LZ encoder whose
window/hash state desynchronises once the input passes ~139 KB, so the
emitted deflate stream *faithfully encodes garbage* for the remainder. Since
Revit carries the schema internally and never needs to read this stream to
open a same-version file, the defect went unnoticed. **The class records for
names alphabetically after `DDGraphSerializable` are unrecoverable from
`Formats/Latest`** in any file of this build; they must come from another
source (a different release's stream, live introspection, or reconstruction
from element data).

## 8. Unknowns

1. Recovery of the degraded 72 % — needs an alternate source; not decodable here.
2. Exact C++ types for kinds `02` (16-bit?/enum), `03` (long/enum32), `0a`
   (`ClassDefinitionRef.m_ref`); `04` conflates `int`/`unsigned int`.
3. Semantics of the three pointer flavours `mod 01/02/03` and of container
   flavours `50/51`; whether `mod 40/52/61/62` exist (unseen in the prefix).
4. Meaning of the per-record `u32 version` and of the `u32 k(=1)` and
   `u8 0x20` bytes inside `0d10/0d50` wrappers.
5. Semantics of trailer GUID lists (per-class 1–3, `AUnits` 13, `ADocument`
   1,509) and why exactly these 26 classes carry them.
6. Whether ordinals `0..11` are the built-in kinds `00..0b` (numerically
   consistent, unproven).
7. Whether the total top-level class count relates to ADocument's 1,509
   GUIDs (prefix has 727 top-level classes in 27.8 % of bytes).

## Reproduce

```
.venv/bin/python src/rvt/schema_b.py            # prints summary, writes JSON
.venv/bin/python src/rvt/schema_b.py <stream>   # any inflated Formats/Latest
```

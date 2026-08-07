# Stream: `Formats/Latest` — the Revit 2026 archive class map (CANONICAL)

Status: **SOLVED (wave 2).** The whole stream parses to EOF with zero
unparsed gaps and zero unresolved type references. This document supersedes
`01-schema-a.md` and `01-schema-b.md` (kept as history); the wave-1
"corruption at 0x21e61" was the page-framing artefact, not damage.

- Decoder: `src/rvt/schema.py` (`load_schema() -> Schema`).
- Outputs: `extracted/_schema/schema.json` (4,690 class records),
  `extracted/_schema/type_ids.json` (id → name),
  `extracted/_schema/mep_classes.txt` (407 electrical/MEP classes).
- Subject bytes: `extracted/<file>/Formats__Latest.gz/000.bin` — the
  de-paged, gzip-member-0 inflate of the OLE stream `Formats/Latest`.
  **496,597 bytes, sha256 `6459a9a93ebde32c…f8ac2`, byte-identical in all
  six 2026 files** (verified by the decoder on every run). It is a
  per-release constant: decode once per Revit build.

## What it is

The self-describing serialization schema Revit's `Utility!ArchiveClassMaps`
registers: every archive-serializable and every embeddable C++ class, in
one flat sequence of class records. Each record carries the class name,
optional base class, a version integer, an ordered list of field
descriptors (member name + type encoding) and a per-class GUID table.
The **archive class index** (the `u16 class word` that leads serialized
objects everywhere else in the file — `Global/*` leads, `Partitions/*`
record class words, ZDI's "u16 class index read by the deserializer") is
simply the class's **definition-order position + 0x0c**. 4,690 classes
in 2026 (ZDI counted 4,611 for 2025).

## Grammar

All integers little-endian.

```
stream        := class_record* zero_pad          (8 zero bytes at EOF)

class_record  := u16 0                             record marker
                 u16 name_len,  u8[name_len] name  ASCII class name
                 u16 parent_ref                    0        = no base
                                                   0x8000|i = base class
                                                              defined INLINE
                                                              next, gets id i
                                                   i        = backward ref to
                                                              defined id i
                 u32 version                       class serialization version
                 u32 field_count
                 field[field_count]
                 u32 guid_count
                 u8[16] guid[guid_count]           class GUID history table

field         := u32 name_len, u8[name_len] name, descriptor

descriptor    := u8 kind, u8 flags, u16 extra
                 [ if flags high-nibble == 0x1 : u32 fixed_count ]
                 [ if kind == 0x0e and (flags & 0x0f) == 0 :
                       u16 type_ref                0x8000|i => class_record
                                                   for id i INLINE right here ]
                 [ if kind == 0x0d :               inline array wrapper:
                       field                       anonymous element field
                                                   (its name is a single
                                                   space " ")
                       + if that element is kind 0x0e with (flags&0x0f)==0 :
                           u16 type_ref            repeat of the element's id ]
```

Type ids are assigned by ONE running counter, in DEFINITION ORDER (top-
level records and inline definitions share it), starting at **0x0c**.
Values `0x00–0x0b` are the primitive kind codes and never denote classes.
An inline definition (`0x8000|i` in a `parent_ref` or `type_ref`) carries
its own id `i`; across all 1,086 inline definitions `i` equals the running
counter every time (parser hard-asserts this) — the proof that the number
is the *defined* class's ordinal, not a property of the referencing class.

`extra` (descriptor bytes 2–3) is zero for **12,638 of 12,639**
descriptors (12,558 named fields + 81 anonymous array-element
descriptors); the single exception is `VarExpr.m_refCt` = kind `0x04`
(int), extra `0x0004` (offset `0x72d3d`) — a runtime reference count on
the family-editor expression node; `[hypothesis]` the extra word marks it
transient/non-owning. It never changes framing.

The top-level records are stored in **strict ASCII byte order of class
name** (0 descents across 3,604 records) — the map is Autodesk's sorted
class registry — so a class's id is its rank in the sorted registry plus
the number of inline definitions that precede it.

### Worked examples

Stream head (offset `0x0`) — `A3PartyAImage` whose base `A3PartyObject`
is defined inline and therefore receives id `0x0d`:

```
00000000: 0000 0d00 4133 5061 7274 7941 496d 6167   ....A3PartyAImag
00000010: 650d 80|00 000d 0041 3350 6172 7479 4f62  e......A3PartyOb
                ^^^^ parent_ref 0x800d = INLINE base, id 0x0d
                     -> nested record: marker 0000, len 000d, "A3PartyObject",
                        parent 0000, version 0, fields 0, guids 0
00000020: 6a65 6374 0000 0000 0000 0000 0000 0000   ...(A3PartyObject:
00000030: 0000 0000 0000 0000 0000 0000 0000 0000    parent0 v0 fc0 gc0)
                                                     then A3PartyAImage's
                                                     own v0 fc0 gc0
00000040: 0f00 4133 5061 7274 7953 4543 496d 6167   A3PartySECImage (id 0x0e)
00000050: 650d 00|.. parent_ref 0x000d = backward ref to A3PartyObject
```
=> `A3PartyAImage`=0x0c, `A3PartyObject`=0x0d, `A3PartySECImage`=0x0e.

The synthetic `std::pair< ElementId, int >` at `0xff` shows an inline
`type_ref` chain defining `ElementId` (0x14) → `Identifier` (0x15):

```
000000ff: 0000 1b00 "std::pair< ElementId, int >" 0000  v0  fc=2
0000012a: 05000000 "first"  0e 00 0000 | 1480  = kind class(value),
          type_ref 0x8014 = INLINE define ElementId as id 0x14:
0000013b: 0000 0900 "ElementId" 0000 v1 fc=1
0000014f:   04000000 "m_id" 0e 00 0000 | 1580 = INLINE Identifier id 0x15
              ... Identifier v2 fc=1 "m_id64" 0b 00 0000 (int64) gc=0
            ElementId gc=0
0000018b: 06000000 "second" 04 00 0000 (int)   pair gc=0
```
=> `ElementId` = **0x14**, matching the u32 `0x14` element-id type word
seen throughout `Partitions/*`.

The last record and EOF (offset `0x793a0`):

```
000793a0: 0009 0074 6573 7463 6c61 7373 0000 0100  ...testclass....
000793b0: 0000 0100 0000 0900 0000 6d5f 7465 7374  v1 fc1 "m_testMap"
000793c0: 4d61 700e 5000 00fc 11|00 0000 0000 0000  0e 50 = container of
000793d0: 0000 0000 00                            class, type_ref 0x11fc
```
`testclass` (id 0x125d, a debug fixture Autodesk left registered) is the
final class; `fc 11` = backward type_ref `0x11fc` =
`std::pair< ElementId, LevelMapData >` (already defined ⇒ no 0x8000
flag); guid_count 0 ends at `0x793cd`; the remaining **8 zero bytes**
are the end-of-registry sentinel/pad. Consumed 496,589 + 8 = 496,597. ∎

## Kind codebook (descriptor byte 0)

Ground truth (GT) comes from the 394 synthetic `std::pair< A, B >`
classes whose C++ signature is spelled out in their name (e.g.
`std::pair< short, int64_t >` → `first`=0x03, `second`=0x0b), tabulated
over the entire stream.

| kind | meaning | width | evidence |
|-----:|---------|-------|----------|
| 0x01 | `bool` | 1 | GT: `pair<X,bool>` ×25 |
| 0x02 | `char` (byte) | 1 | GT: `pair<X,char>` ×21 (contradicts rvt-rs's "u16") |
| 0x03 | `short` | 2 | GT: `pair<short,X>` ×21 (contradicts rvt-rs's "deprecated i32") |
| 0x04 | `int` (int32) | 4 | GT: `pair<X,int>` ×95 |
| 0x05 | `unsigned` (uint32) | 4 | GT: `pair<unsigned long,X>`; `ATime.m_msb/m_lsb`, colours |
| 0x06 | `float` | 4 | GT: `pair<X,float>` ×8; `APropertyFloat*.m_value` |
| 0x07 | `double` | 8 | GT: `pair<X,double>` ×16 |
| 0x08 | `AString` (UTF-16 string) | var | GT: `pair<X,AString>` ×39; always flags 0x60 |
| 0x09 | `GUID` (16 bytes) | 16 | `GUIDvalue.m_guid` (sole instance) |
| 0x0a | class-definition ref | — | `ClassDefinitionRef.m_ref` (sole instance) |
| 0x0b | `int64` | 8 | GT: `pair<X,int64_t>` ×21; `Identifier.m_id64` |
| 0x0d | inline array wrapper | var | anonymous element sub-field follows (81×) |
| 0x0e | user class (by id) | var | 5,708 fields; typed forms carry a `u16 type_ref` |

Flags (descriptor byte 1): high nibble = storage shape
(`0` scalar/single, `1` fixed array (+u32 count), `5` growable container,
`6` string), low nibble = indirection (`0` value — carries a `type_ref`
when kind 0x0e, `1` polymorphic ptr, `2` owned ptr, `3` weak/back ptr,
`4` var-node ptr, only on `VarExpr`/`VarFunction`). Observed pairs and
counts (full-stream histogram):

```
01 00 x1550  01 10 x33  01 50 x17       bool
02 00 x38    02 50 x31                  char
03 00 x27    03 10 x3                   short
04 00 x2047  04 10 x76  04 50 x116      int
05 00 x76    05 10 x5   05 50 x1        uint
06 00 x15    06 10 x10                  float
07 00 x1581  07 10 x416 07 50 x61       double
08 60 x702                              AString
09 00 x1     0a 00 x1    0b 00 x38  0b 50 x1
0d 10 x32    0d 50 x49                  inline array
0e 00 x2937  0e 01 x720 0e 02 x117 0e 03 x108 0e 04 x1
0e 10 x65    0e 11 x9   0e 13 x3   0e 50 x1339 0e 51 x409 0e 53 x1 0e 54 x3
```

Only value-shaped class fields (`0e 00`, `0e 10`, `0e 50`, and the
element of a `0d`) carry a static `type_ref`; pointer flavours are
polymorphic (their target class index is written per-object at runtime,
per ZDI's deserializer description).

## Id model and anchor validation (acceptance test)

Model: **id = definition order + 0x0c, no drift.** Validated against 16
class ordinals independently observed leading real serialized objects in
the element/global streams (wave-1 partitions/global/content agents) plus
the ZDI datum `AString = 0x1f`:

| anchor id | expected (source) | decoded class at id | verdict |
|----------:|-------------------|---------------------|---------|
| 0x001c | ADocument — `Global/Latest` lead ordinal | `ADocument` | EXACT |
| 0x0014 | ElementId — u32 type word in partition records | `ElementId` | EXACT |
| 0x001f | AString — ZDI 2025 registered class index | `AStringWrapper` | EXACT (AString's serializable wrapper class) |
| 0x0025 | Element — universal base ordinal | `Element` | EXACT |
| 0x05c9 | ElemTable — `Global/ElemTable` lead | `ElemTable` | EXACT |
| 0x0538 | DocumentHistory — `Global/History` lead | `DocumentHistory` | EXACT |
| 0x053c | DocumentIncrementTable lead | `DocumentIncrementTable` | EXACT |
| 0x053e | Contents item word (~DocumentStorageIndex) | `DocumentStorageIndexImpl` (0x53d = `DocumentStorageIndex`) | EXACT family — the on-disk object is the Impl subclass |
| 0x0c80 | PartitionTable (workset table) lead | `PartitionTable` | EXACT |
| 0x03a2 | ~ContentMarker (separator word `a2 03`) | `ContentKey` (0x3a3 = `ContentMarker`) | family, +1 — the guessed label named the sibling; `ContentKey` (counter + GUID) fits the observed 28-byte separator payload |
| 0x03a3 | ~ContentRec (Partitions header word `a3 03`) | `ContentMarker` (0x3a4 = `ContentRec`) | family, +1 — the wave-1 label picked the neighbouring name; the ordinals are right, the guessed names were one slot off |
| 0x05e5 | ~ElementHeader — seq-101 record class word | `ElementHeader` | EXACT |
| 0x0f2c | ~SerializedDummy — seq-103 dominant word | `SerializedDummy` | EXACT |
| 0x089e | ~GElement — seq-103 class word | `GElement` | EXACT |
| 0x08cc | ~GStyleElem — seq-102 top class 2252 | `GStyleElem` | EXACT |
| 0x02e1 | ~CategoryElem — seq-102 top class 737 | `CategoryElem` | EXACT |

**16/16 (100%)**: 12 exact names, 2 exact-family (the anchor's functional
label vs. the concrete/wrapper class name), 2 where the wave-1 analyst
attached the neighbouring class's name to a correctly-observed ordinal.
No ±1 drift is needed anywhere: the model is exact `definition-order +
0x0c`. This closes the wave-1 open question "definition-order + 0x0c,
allowing the observed ±1 drift" — the "drift" was label guesswork, not
the id model.

Corroboration from prior art: rvt-rs's `tag-drift-2016-2026.csv` reads the
u16 after the class name (0x8000 flag set) as the class's "serialization
tag". In the true grammar that word is the **inline-defined base class's
id**, so rvt-rs's tag must equal our id **+1** for every class whose base
is defined inline. Result: **60/60 classes present in both = ours+1**
(0 exceptions). rvt-rs's "tagless" classes are simply those whose base was
already defined (a backward ref has no 0x8000 flag); its ~400-class /
64 KB cap and "post-64KB is binary noise" belief are the paging artefact.

## Statistics (2026, all six files identical)

- **4,690 classes**: 3,604 top-level records + 1,086 inline definitions;
  ids `0x000c–0x125d`. **12,558 fields.** 1,677 per-class GUID entries in
  100 classes (`ADocument` alone holds 1,509 — its format-episode
  history; `AUnits` 13).
- 3,127 classes name a base (66%). Inheritance depth histogram (steps to
  root): 0:1,563 · 1:1,120 · 2:1,289 · 3:494 · 4:152 · 5:47 · 6:23 · 7:2.
  Deepest: `RbsDuctInsulation > RbsInsulation > RbsInsulationLiningBase >
  RbsReference > RbsMultiCurve > RbsCurve > HostObj > Element`.
- Most-subclassed bases: `Element` 383 direct / **895 total descendants**,
  `GeomStep` 215, `ParamDefCombo` 185, `Cell` 170, `AppInfo` 110,
  `Symbol` 95, `PostedWarning` 80, `ElemSetTracking` 53.
- Field kind mix: class-ref 5,708 · int 2,228 · double 2,003 · bool 1,599
  · AString 702 · uint 82 · inline-array 81 · char 69 · int64 39 ·
  short 27 · float 18 · GUID 1 · classref 1.
- Top referenced types (typed class fields): `ElementId` 2,100,
  `XYZ` 218, `GUIDvalue` 94, `Trf` 82, `GeomRef` 43,
  `RoomBoundingItem` 39, `ForeignElemRef` 30, `std::pair< int, int >` 28,
  `AStringWrapper` 25, `std::pair< ElementId, ElementId >` 24,
  `ConnectorId` 19, `ForgeTypeId` 18, `UV` 18, `Pick` 18, `Outline` 15.
- Largest classes: `FamSymRegenArgs` 108 fields, `FamilyBase` 89,
  `FamilySymbol` 61, `EnergyAnalysisSpaceData` 60, `RoomElem` 52,
  `DBView` 48. Highest versions: `ADocument` **2662** (== the Revit 2026
  format episode number ending `Global/History`), `ModifiedGroupData` 201,
  `DBView` 99, `ScheduleSchema` 76. `Element` v21, 20 fields.

## Electrical / MEP class inventory (Track focus)

`extracted/_schema/mep_classes.txt` lists all **407** classes whose
name matches `(Electrical|Circuit|Panel|Wire|Wiring|Conduit|CableTray|
Distribution|Power|Voltage|Fixture|Lighting|Connector|MEPSystem|System|
Load|Phase)` with id, base chain and full field list. Keyword hit counts:
Connector 95 · System 83 · Load 75 · Wire 32 · Electrical 30 · Conduit 24
· Panel 22 · Circuit 20 · CableTray 15 · Phase 14 · Distribution 10 ·
Fixture 10 · MEPSystem 10 · Power 9 · Voltage 3 · Wiring 1 · Lighting 1
(note `Load` also matches unrelated `*Loaded*` family classes; consumers
should filter by base chain, e.g. descendants of `Element`).

Key classes for the electrical bridge (id · base chain · notable fields):

- `0x0596 ElectricalCircuit` (Element): `m_pConnectorMgr`,
  `m_strDescription`, `m_strWireSize`, `m_dRating`, `m_dLength`,
  `m_dVoltageDrop`, `m_idWireType`, `m_idPanel` (ElementId), `m_type`,
  `m_loadClassification`, `m_nPoles`, `m_nStartSlot`.
- `0x05a4 ElectricalLoadClassification` (Element, 17 fields),
  `0x05ae ElectricalSetting` (Element, 19), `0x05ad ElectricalLoadZoneType`,
  `0x059c ElectricalDemandFactorDefinition`, `0x0595
  ElectricalAnalyticalLoadSet`, `0x00f6 ElectricalPerPhaseData` (16 fields,
  embedded), `0x05ac LoadClassificationPerPhaseData`.
- Connectivity: `0x0376 Connector`, `0x0377 ConnectorId`,
  `0x037c ConnectorDomain` + `0x037e ConnectorDomainElectrical` /
  `0x037d …CableTrayConduit` / `0x037f …Hvac` / `0x0380 …Piping`,
  `0x0381 ConnectorElem` (Element), `0x0597 ElectricalCircuitConnector`,
  `0x0598 ElectricalCircuitConnectorManager`.
- Distribution/routing: `0x02b6 CableTray` and `ConduitRun`/`CableTrayRun`
  under `CableTrayConduitRunBase > Element` (host chain
  `RbsCableTrayConduitBase > LineAndArcRunMember > RbsSingleCurve >
  RbsCurve > HostObj > Element`), `0x036a ConduitSize(Set)`,
  `0x02c3 CableTraySettingsElem`, `0x0369 ConduitSettingsElem`,
  `0x0de1 WireSizeItem`, `0x11c7 WireInfo` (ConductorInfo).
- Schedules: `0x0b48 PanelScheduleView` (TableView > DBView > Element),
  `0x0b41 PanelScheduleData` (23 fields), `0x0b45 PanelScheduleTemplate`,
  `0x0b42 PanelScheduleSheetInstance`; circuits: `0x030d
  CircuitNamingScheme`, `0x030f CircuitNamingTypeSetting`, `0x0309
  CircuitGroupAppInfo`.

Panelboards / distribution equipment themselves are `FamilyInstance`/
`FamilySymbol` (`RbsFamilyInstance…` design-property managers such as
`0x059f ElectricalFamInstDesignPropertyManager`), not dedicated classes —
consistent with Revit's family-based MEP equipment model.

## How to use

```python
from rvt.schema import load_schema
s = load_schema()                      # parses to EOF, 0 gaps, 0 unresolved
c = s.by_name["ElectricalCircuit"]     # ClassDef: type_id, version, fields...
s.by_id[0x1c].name                     # 'ADocument'
s.parent_chain("PanelScheduleView")    # ['TableView','DBView','Element']
[f.name for f in c.fields], s.stats()
```
`python -m rvt.schema` re-parses, prints the report + anchor table, and
rewrites `extracted/_schema/{schema.json,type_ids.json,mep_classes.txt}`.
JSON class record: `{type_id, name, parent, parent_id, version, fields:
[{name, kind, kind_name, flags, flags_name, type_id, type_name, count,
[extra], [element], [inline_definition]}], guids:[...]}`.

## Unknowns

- `VarExpr.m_refCt` descriptor `extra=0x0004` (unique in the stream) —
  `[hypothesis]` a transient/skip marker; semantic unconfirmed.
- Flag low-nibble `0x4` (`0e 04`, `0e 54`, 4 fields, all on
  `VarExpr`/`VarFunction`) — a fourth pointer flavour; exact ownership
  semantics unconfirmed.
- Kind `0x0a` (`ClassDefinitionRef.m_ref`) wire encoding at object level
  unobserved (schema-only).
- The 8 trailing zero bytes — read as sentinel/pad `[hypothesis]`; harmless
  either way (a class marker of 0 with name length 0 cannot start a valid
  record).
- Per-class `version` semantics beyond "matches per-object version words"
  is untested against object payloads (element-decode agents' job).

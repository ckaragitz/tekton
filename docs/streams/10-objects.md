# 10 — Element objects: schema-directed decoding of `Partitions/*` records

Status: **element objects DECODE (wave 3).** Every field of every serialized
element in the three partition record streams is walked using the canonical
class map (`Formats/Latest`, `docs/streams/01-schema.md`) — no guessing,
no heuristic string scans. Real values fall out: level elevations, wall
location lines, view / type / category names, GUIDs, ElementIds that
resolve into `Global/ElemTable`, panel-schedule and circuit data.

- Decoder: `src/rvt/objects.py` (`ObjectDecoder`, `Reader`, `iter_records`,
  driver `python -m rvt.objects [project] [seq] [--samples] [--json]
  [--experiments]`).
- Tests: `tests/test_objects.py` (10 tests; framing, id-mapping, decode
  rate, level elevations, wall lengths, ElemTable id intersection).
- Sample dump: `extracted/_objects/racbasic_sample.json` (100 decoded
  instances, racbasic, all clean).

Confidence per section: **[V]** verified byte-exact by the decoder over
whole record streams (a full-record decode consumes 100 % of the record's
bytes with zero errors), **[H]** hypothesis / semantic reading.

## 1. Results (corpus decode rates)

`clean` = the record's object decoded with **every byte consumed** (`consumed
== psize-2`) and **no error**. One `ObjectDecoder`, unchanged, over all five
sub-100 MB samples (dach-sample-project not run this wave — see Unknowns):

| project | seq | records | classes | clean full-record decodes | byte coverage |
|---------|-----|--------:|--------:|--------------------------:|--------------:|
| racbasicsampleproject | 101 | 85,814 | 1 | 85,814 (100.00 %) | 100.0 % |
| racbasicsampleproject | 102 | 85,814 | 306 | **85,814 (100.00 %)** | 100.0 % |
| racbasicsampleproject | 103 | 85,814 | 2 | 85,814 (100.00 %) | 100.0 % |
| rstbasicsampleproject | 102 | 32,011 | 311 | 32,004 (99.98 %) | 100.0 % |
| rmebasicsampleproject | 102 | 142,174 | 306 | 141,003 (99.18 %) | 98.4 % |
| racadvancedsampleproject | 102 | 59,453 | 312 | 59,453 (100.00 %) | 100.0 % |
| rstadvancedsampleproject | 102 | 64,966 | 300 | 64,966 (100.00 %) | 100.0 % |
| all five, seq 101 / 103 | — | — | 1 / 2 | 100.00 % each | 100.0 % |

Seq 102 overall: **383,240 / 384,418 = 99.69 %**. The *only* failures in
the whole corpus are Extensible-Storage entity blobs (blocker B1, §9):
1,171 `FamilyInstance` in rme, 6 `RebarShape` + 1 `DataStorage` in
rstbasic. Everything else — 300–312 distinct classes per file — decodes to
the byte.

Per-class table, racbasic seq 102, top 40 by count (all 100 % clean, mean
bytes consumed == mean psize):

```
  class name                              records   clean  rate   bytes/record
0x08cc GStyleElem                           13157   13157  100.0    162.4
0x02e1 CategoryElem                         11653   11653  100.0    157.1
0x03ba CurveElem                             7674    7674  100.0    625.0
0x0a0c LinearDimString                       6459    6459  100.0   1337.2
0x084c FontElem                              5269    5269  100.0    148.6
0x0486 DBViewType                            3125    3125  100.0    208.8
0x0927 SketchGrid                            2673    2673  100.0    111.6
0x0f5d SketchPlane                           2621    2621  100.0    319.1
0x09e3 LeaderStyle                           1953    1953  100.0    253.7
0x0e75 RefPlane                              1787    1787  100.0    754.4
0x00be DimensionStyle                        1779    1779  100.0   1129.8
0x00ae Alignment                             1756    1756  100.0   1327.1
0x1143 VarSketch                             1472    1472  100.0   3519.4
0x0c50 ParamElemFamily                       1374    1374  100.0    381.0
0x088d Viewport                              1039    1039  100.0    245.1
0x0463 DBDrawing                             1019    1019  100.0    120.2
0x0ddd RbsWireInsulationType                  884     884  100.0    142.4
0x02d4 Viewer                                 866     866  100.0    550.0
0x0a1e LoadNatureElem                         856     856  100.0    153.0
0x0a18 LoadCaseElem                           856     856  100.0    177.2
0x10df TextNoteAttributes                     673     673  100.0    240.3
0x0672 ExtentElem                             627     627  100.0    319.8
0x0f19 SectionAttributes                      597     597  100.0    213.1
0x10aa TagNoteAttributes                      521     521  100.0    212.2
0x080a FilledRegionAttributes                 502     502  100.0    210.8
0x07c5 FamilyInstance                         495     495  100.0    844.7
0x00bd SpotElevationStyle                     495     495  100.0   1432.2
0x07af Family                                 475     475  100.0   4648.3
0x0690 ExtrusionElem                          437     437  100.0   2008.2
0x07e6 FamilySymbol                           390     390  100.0   7542.2
0x0d36 RadialDim                              367     367  100.0    943.0
0x100f StructConnectionType                   345     345  100.0    179.4
0x07ac FamSymSurrogate                        343     343  100.0    161.5
0x028c BrowserOrganization                    337     337  100.0    180.6
0x0482 DBViewSection                          317     317  100.0   2763.0
0x07e3 FamilySurrogate                        312     312  100.0    192.8
0x02da CalloutTag                             306     306  100.0    173.1
0x09ab InteriorElevAttributes                 306     306  100.0    221.9
0x0c9f PenWidthTableElem                      306     306  100.0   1201.1
0x0ea9 RevealAttr                             298     298  100.0    168.4
```

Selected further racbasic classes (all 100 %): `Level` ×109 (760 B),
`SWall` ×64 (9,688 B), `Grid` ×14, `BasicWallType` ×11, `DBViewPlan` ×173
(3,041 B), `DBView3d` ×141, `DBViewSection` ×317, `DBViewSchedule` ×9
(13,586 B), `PanelScheduleTemplate` ×5 (104,369 B), `ElectricalSetting` ×1,
`ElectricalLoadClassification` ×12, `RbsElectricalSystem` ×1. Reproduce:
`python -m rvt.objects racbasicsampleproject 102`.

## 2. Record framing — corrected and unified [V]

The wave-1 header `{i64 id, u32 stamp, u32 size, u32 class_word}` is right
about the bytes but wrong about the split: the `u32 class_word` is really a
**`u16 class_id`** (the object's leading class ordinal) followed by the
**first `u16` of the object**, and the last 4 bytes of the "body" are a
**repeat of the size**. One layout describes all three seqs and every record
kind, including the seq-103 `SerializedDummy` placeholders and the id `-1`
save-unit sentinels:

| offset | size | field | meaning / evidence |
|-------:|-----:|-------|--------------------|
| 0 | 8 | `i64 id` | ElementId of the record (`-1` = save-unit sentinel). Decoded objects carry the same id in `Element.m_id`. |
| 8 | 4 | `u32 stamp` | **seq 102/103 only** (absent in seq 101). 85,799 distinct values among racbasic's 85,814 records `[H]` per-object stamp/hash, not an episode counter. |
| 8 or 12 | 4 | `u32 psize` | payload size = 2 (class id) + object bytes. 0 for sentinels. |
| … | 2 | `u16 class_id` | schema type_id, **identity** (§3). |
| … | psize−2 | object | serialized fields (§5). Empty for `SerializedDummy` (psize = 2). |
| … | 4 | `u32 psize` (repeat) | trailer; **equal to `psize` for all 85,978 racbasic records in each of seq 101 and seq 102** (85,814 elements + 164 sentinels, whose trailer is 0) (`tests/test_objects.py::test_record_framing_trailer`). |

Total record length = 16 (seq 101) or 20 (seq 102/103) + psize.

Worked example — a whole 176-byte `GStyleElem` record, racbasic seq-102
segment offset `0xbe150`, decoded field-by-field:

```
0000: 08 96 02 00 00 00 00 00   id      = 0x29608 = 169480
0008: 00 54 f8 79               stamp   = 0x79f85400
000c: 9c 00 00 00               psize   = 0x9c = 156   (=> total 20+156 = 176)
0010: cc 08                     class_id = 0x08cc GStyleElem
0012: 00 00 00 00               Element.m_pParamValueSetDouble   ptr pid=0 -> null
0016: 00 00 00 00               Element.m_pParamValueSetInt      null
001a: 00 00 00 00               Element.m_pParamValueSetAString  null
001e: 00 00 00 00               Element.m_pParamValueSetElementId null
0022: 00 00 00 00               Element.m_geomSteps               null
0026: 00 00 00 00               Element.m_pGeomTable              null
002a: 00 00 00 00               Element.m_constrInfo   (container) count = 0
002e: 00 00 00 00               Element.m_cellList                null
0032: 01 00 00 00               Element.m_docAccess.m_pDoc  weakref pid=1 (the document)
0036: 08 96 02 00 00 00 00 00   Element.m_id           = 169480   (== record id)
003e: ff ff ff ff ff ff ff ff   m_assocLevelId         = -1
0046: d0 95 02 00 00 00 00 00   m_famId                = 0x295d0 = 169424
004e: ff*8 ×4                   m_unplacedOwnerId, m_ownerDBViewId,
                                m_createdPhaseId, m_demolishedPhaseId = -1
006e: fc ff ff ff ff ff ff ff   m_designOptionId       = -4
0076: 00 00 00                  m_locked/m_moribund/m_dummy = False
0079: ff ff ff ff  c8 08        GStyleElem.m_pGStyle = ptr pid=-1 (anonymous)
                                + u16 class 0x08c8 GStyle; body DEFERRED
007f: 06 96 02 00 00 00 00 00   m_categoryId = 0x29606 = 169478
0087: ff*8                      m_ownerId    = -1
008f: 01 00 00 00               m_gstyleType = 1
        ---- deferred pointed-to object (breadth-first, after own fields) ----
0093: ff*8                      GStyle.m_linePatternId  = -1
009b: ff*8                      GStyle.m_materialElemId = -1
00a3: 07 00 00 00               GStyle.m_penNumber      = 7
00a7: ff ff ff ff               GStyle.m_color (uint)   = 0xffffffff
00ab: 00                        GStyle.m_isScreenSized  = False
00ac: 9c 00 00 00               psize repeat = 156  -> record ends at 0xb0
```

The three seqs are **one record per element, keyed by the same id**:
racbasic has exactly 85,814 records in each of seq 101, 102 and 103, the
three id sets are **identical**, and no id repeats within a seq. So an
element = the join of its three records: **seq 101 = `ElementHeader`
(0x5e5)** — regen history, category/family/owner-view/design-option ids,
`ElementParents` dependency lists and, notably, `m_classDef` (a
`ClassDefinitionRef` = u16 class index → the element's class name);
**seq 102 = the polymorphic element object itself; seq 103 = its geometry
rep** (`GElement` 0x89e — 11,863 in racbasic — or an empty
`SerializedDummy` 0x0f2c placeholder, psize = 2, when the element has no
cached representation). All 8,401 `Global/ElemTable` ids are a subset of
the partition record ids [V].

## 3. `class_word` → schema type_id: **identity** [V]

The record's `u16 class_id` **is** the archive class index `id = definition
order + 0x0c` from `01-schema.md` — no offset, no drift. Proof: decode the
same 4,000 racbasic seq-102 records with the id shifted by `k`; only
`k = 0` makes them decode cleanly:

| k (candidate id = class_id + k) | clean full-record decodes | mean byte coverage |
|---:|---:|---:|
| −2 | 1 / 4000 (0.03 %) | 14.3 % |
| −1 | 15 / 4000 (0.38 %) | 15.6 % |
| **0** | **4000 / 4000 (100.00 %)** | **100.0 %** |
| +1 | 118 / 4000 (2.95 %) | 18.7 % |
| +2 | 1 / 4000 (0.03 %) | 14.8 % |

(rstbasic: k=0 4000/4000, k=±1 65/0.) This independently re-proves the
schema id model and the 16/16 anchor table (`ElementHeader` 0x5e5 in seq
101, `GElement` 0x89e / `SerializedDummy` 0x0f2c in seq 103, `GStyleElem`
0x8cc etc. in seq 102). `objects.offset_experiment()` reproduces it.

## 4. Field order — parents first [V]

An object's fields are its **root base class's fields, then each subclass
down to the concrete class**, each in schema order (`ObjectDecoder.chain()`).
Same 4,000 records: parent-first 4000/4000 clean; self-first
(concrete class first) 96/4000 (2.40 %). E.g. every element starts with
`Element`'s 20 fields (`m_pParamValueSetDouble …`), a `Level` continues
with `DatumPlane`'s (`m_text`, `m_pFace`, `m_pSurface` …) and ends with
`Level`'s own three.

## 5. Serialization codebook [V]

Per schema field descriptor (`kind`, `flags` = shape≪4 | indirection):

| construct | encoding | note |
|-----------|----------|------|
| `bool`/`char` (01/02) | u8 | |
| `short` (03) | i16 | |
| `int`/`uint` (04/05) | i32 / u32 | |
| `float`/`double` (06/07) | f32 / f64 LE | Trf/XYZ/UV/Outline are just fixed double arrays via the schema |
| `int64` (0b) | i64 | |
| `AString` (08, flags 0x60) | u32 char-count + UTF-16LE, no NUL | count `0xFFFFFFFF` = null (strings-map §6.2) |
| `GUID` (09) | 16 raw bytes | rendered `d1-d2-d3-d4-…` (LE d1..d3), e.g. `FamilySurrogate.m_guid = e3e052f8-0156-11d5-9301-0000863f27ad` |
| class-def ref (0a) | u16 class index | `ClassDefinitionRef.m_ref` in `ElementHeader.m_classDef` → the element's class name |
| `ElementId` value (`0e 00 →0x14`) | i64 LE, −1 invalid | flattened; = `Identifier.m_id64` |
| inline value class (`0e 00/10/50`) | the class's field list inline (recursively parent-first) | e.g. `SymbolInfo`, `Trf`, `ApparentPowerPerPhaseData` |
| fixed array (flags ≪4 = 1) | schema `u32 count` elements, no length on the wire | XYZ = `double[3]`, m_3x3 = `double[3][3]` |
| container (flags ≪4 = 5) | `u32 count` + elements | capped at 2·10⁶ / remaining-bytes sanity |
| inline-array wrapper (0d) | repeats its anonymous element descriptor | 81 fields |
| owned/poly pointer (`0e 01/02/04`) | **`i32 pid`**; `pid==0` → null (4 bytes). Otherwise + **`u16 class`** and the pointed object's body is **deferred**: appended to a per-record FIFO and serialized only after the current object's field list finishes (breadth-first). | see below |
| weak pointer (`0e 03`) | **`u32 pid`** = archive object index only; 0 null, 1 document, 2 the record's root object | `m_pElem = weakref(2)`, `m_pDoc = weakref(1)` |

Pointer `pid` semantics: `-1` = anonymous, unshared target (the common
case); `pid > 0` assigns the target an archive **object index** so weak
pointers / later pointers can refer to it (1 = the document, 2 = the
record's root, 3… allocated in encounter order); a `pid > 0` already seen is
a **back-reference** (no class word, no body). The deferred/BFS layout is
what makes 100 %-coverage possible: in the GStyleElem example the `GStyle`
body follows *all* of GStyleElem's own fields even though `m_pGStyle` is
declared before `m_categoryId`. Deferred-object count per record
(racbasic, first 20k): 1×7,066 records, 3×3,714, 0×1,700, 2×1,239, 4×855,
6×821, 9×660 — deep trees are normal (`FamilySymbol` ≈ 100+ objects).

## 6. Targets — where the model lives

| element | class (id) | key decoded members |
|---|---|---|
| **Level** | `Level` 0x09e7 < `DatumPlane` < `Element` | `m_text` (name); `m_pSurface` → `Plane` (pid 4/5) whose `m_origin[2]` is the **elevation in feet**; `m_bubbleEnd/m_freeEnd` datum extents; `m_isBuildingStory`; `m_attrId` (its `LevelAttributes` type) |
| **Wall** | `SWall` 0x0f02 < `VWall` 0x01b8 < `HostObj` < `Element` | `m_pCurveDriver` → `VWallDriver.m_pCrv` → `GLine{m_origin, m_dirVec, m_endParams}` (location line, **length = endParams[1]−endParams[0], feet**); `m_upToLevelId` / `Element.m_assocLevelId` (top/base levels = real Level ids); `m_WallAttributesId` (wall type); `m_hostObjMiscData.m_oCGDrivers` (curtain grid/panel ids); wall joins in `m_controlJoinsSet` (`m_elemId` of joined walls) |
| **Grid** | `Grid` 0x090e < `DatumPlane` | `m_text` (bubble label, e.g. `'1'`); plane origin/xVec = the grid line |
| **View** | `DBViewPlan` 0x0478 / `DBViewSection` 0x0482 / `DBView3d` 0x0465 … < `DBView` 0x0072 | `m_viewName` (`'Level 1'`, `'Longitudinal Section'`, `'Solar Analysis'`), `m_scale`, `m_origin/m_viewDir/m_horzDir/m_vertDir`, `m_dbViewTypeId`, `m_viewTemplateId`, `m_isTemplate` |
| **Category** | `CategoryElem` 0x02e1 → `m_pCategory` → `Category` (value class) | user sub-categories carry `m_name` (`'Chassis'`, `'Table Top'`, `'Fabric'`) + `m_parentCategoryId` = a **negative BuiltInCategory id** (`-2000080`, `-2001350`); built-in categories store an empty `m_name` (name comes from Revit's resource table) |
| **Type / symbol names** | `DBViewType`, `LeaderStyle`, `FamilySymbol`, `Family`, `RbsVoltageType` … | `SymbolInfo.m_name` (`'Floor Plan'`, `'Ceiling Plan'`, `'240'`), `Family.m_famDocGUID`/`m_contentDocGUID` |
| **Electrical** | see §8 | circuits, panels, connectors, voltage/distribution types, settings |

Decoded racbasic levels (elem_id · `m_text` · elevation ft): `311 'Level 1'
0.0`, `694 'Ceiling' 8.8583` (2.7 m), `245423 'Level 2' 9.8425` (3.0 m),
`196629 'Roof Line' 19.6850` (6.0 m), `511122 'Foundation' −2.6247`
(−0.8 m), `515270 'Level 1 Living Rm.' −1.8045` (−0.55 m); plus 100+
`'Ref. Level'`/`'Ground floor'` levels owned by nested families
(`m_unplacedOwnerId` set). Wall location lines: `GLine m_endParams
[0.0, 9.84252]` = 3.000 m segments; `m_upToLevelId 196629` (Roof Line),
`m_assocLevelId 311` (Level 1) — level references are real element ids.

Units are Revit internal: length **feet**, angle radians, voltage
**kg·ft²·s⁻³·A⁻¹ = V ÷ 0.3048² ≈ V × 10.7639** (verified: `RbsVoltageType
'240'`: actual 2583.34 → 240.0 V, max 2690.98 → 250 V; circuit
`m_dVoltage 2238.89` → 208 V; `ConnectorElemDomainElectrical.m_dVoltage
1291.67` → 120 V), power `m_apparentPowerPhaseA 60062.6` etc. in
kg·ft²·s⁻³ (VA ÷ 0.3048²).

## 7. Sample instances

`extracted/_objects/racbasic_sample.json` holds **100** fully-decoded racbasic
instances (top-15 classes × 3, plus Level, SWall, Grid, BasicWallType,
FamilySymbol/Instance, DBViewPlan/3d, the electrical classes present in
racbasic, `ProjectInfo`; long containers capped at 40 entries). Nested dict
per instance = the object tree (`{"ptr_class": …, "pid": …, "value": …}` for
pointers, `{"weakref": pid}`, `{"backref_pid": pid}`, ElementIds as ints,
GUIDs as strings). Curated excerpts (`python -m rvt.objects racbasicsampleproject
102 --samples` prints the top-15 × 3 dump; full trees in the JSON):

**Level 311 ('Level 1'):**
```
m_id: 311   m_designOptionId: -1   m_text: 'Level 1'
m_pFace: -> Face (pid 3) m_GInfo: {m_categoryId:-1, m_tag:0, m_flags:524804}
   m_pSurf: -> Plane (pid 5)  m_origin [-1.6e-15, 0, 0]  m_xVec [1,~0,-0]  m_yVec [0,1,-0]
   m_Envelope.m_corners [[-51.6606,-66.1963],[84.3691,86.6831]]
m_pSurface: -> Plane (pid 4) (same plane)   m_bubbleEnd [30,0,0]  m_cutVec [0,1,0]
m_sheetTextHeight 0.015625  m_v2Datum False  m_roomComputationElevationOffset 0
m_attrId 305  m_isBuildingStory True
```
**Level 245423 ('Level 2'):** `m_pSurface->Plane.m_origin[2] = 9.84251968503937` ft.

**SWall 423099** (12,516-byte object, 48 deferred sub-objects): parameter
sets (`ParamValueSetDouble.m_paramSet[i] = {m_paramId: -1001109 (a
BuiltInParameter), m_value: -0.984252}`), geometry steps
(`WallRefPlanesGStep`, `BaseWallGStep`, `JoinEndGStep`,
`VerticalExtensionOfLayersGStep`, `SweepGStep`, all `m_pElem: weakref(2)`),
`VWallDriver{m_pCrv: GLine{m_origin [33.01,9.35,0], m_dirVec [1,0,0],
m_endParams [0.0, 9.84252]}, m_controlJoinsSet (joined wall ids 418079,
423099), m_flip False, m_joinStrength 3}`, curtain data
`WallCGDriver.m_pCurtainGrid.CurtainGrid{m_uLineIds [423106], m_vLineIds
[424757], m_panelIds [423100,424758,423107,424759]}`, `m_upToLevelId
196629`.

**CategoryElem 1647** → `m_pCategory: Category{m_name 'Overhead Lines',
m_parentCategoryId -2000080, m_categoryType 1}`; `m_gstyleIds […]`
(GStyleElem ids). 116 of racbasic's 11,653 category cells carry a name
(user sub-categories); the rest are built-ins.

**DBViewSection 247014** `m_viewName 'Longitudinal Section'`, **DBView3d
959071** `'Solar Analysis'`, **DBViewPlan 312** `'Level 1'`.

**GElement (seq 103)** decodes as the geometry graph: `m_GInfo{m_categoryId
137306, m_tag 147064, m_flags 557060}`, `m_subNodes: [-> GFilter (pid 3)
… ]` with nested `GNode` trees.

## 8. rmebasic — electrical / MEP classes

rmebasic seq 102: 142,174 records, 306 classes, 99.18 % clean; **every MEP /
electrical class decodes 100 %** — the sole shortfall is 1,171
`FamilyInstance`s that carry Extensible-Storage entities (§9 B1). Present and
decoding (records): `FamilyInstance` 4,501/5,672, `FamilySymbol` 1,148,
`RbsWireCurve` 1,045, `RbsWireInsulationType` 1,076, `RbsDuctCurve` 724,
`RbsPipeCurve` 491, `ConnectorElem` 228, `SysPanelFamSym` 220,
**`RbsElectricalSystem` 187 (circuits)**, `RbsWireMaterialType` 177,
`RbsWireTemperatureRatingType` 132, `RbsFlexDuctCurve` 113,
`ZoneElement` 53, `PanelScheduleView` 24, `RbsConduitCurve` 20,
`RbsWireSizesElem` 19, `ElectricalDemandFactorDefinition` 12,
`ElectricalLoadClassification` 10, `RbsConduitType` 10, `ConduitRun` 8,
`RbsCableTrayType` 7, `PanelScheduleTemplate` 6, `RbsVoltageType` 5,
`RbsDistributionSysType` 3, `RbsCableType` 2, `ElectricalSetting` 1,
`CircuitNamingTypeSetting` 1, `RbsWireType` 2, `RbsWireSettingsElem` 1,
`ConduitSizesElem` 1, `CableTraySizesElem` 1, `CableTraySettingsElem` 1.
Note: this Revit build serializes circuits as **`RbsElectricalSystem`
(0x0d87)** and equipment/fixtures as `FamilyInstance` + `FamilySymbol` with
an `ElectricalFamInstDesignPropertyManager`; `ElectricalCircuit` (0x0596)
does not occur as a record class in this file.

Decoded field exposure (real values from rme):

- `RbsElectricalSystem` 623656 (a circuit): `m_number '1'`,
  `m_strDescription 'PP-1B'`, `m_strLoadClassifications 'Receptacles'`,
  `m_dRating 20`, `m_dVoltage 2238.89` (208 V), `m_dApparentLoad 232500`,
  `m_dTrueLoad 232500`, `m_dVoltageDrop 11.2`, `m_dLength 4.06456`,
  `m_dFrame 400`, `m_cableType 887996`, per-phase
  `ApparentPowerPerPhaseData{m_apparentPowerPhaseA/B/C 60062.6/93000.2/
  79437.7, m_truePowerPhase… same, currents 0}`, `m_pathNodes` (circuit path
  polyline with `m_elemId` + `m_position` XYZ), `m_baseConnectorIdArray
  [{m_id 623656, m_nIndex 1, m_connType 4}]`, `m_pConnectorMgr →
  RbsSystemConnectorManager{m_connPtrArray[Connector{m_arrRefs[{m_id
  622027, m_nIndex 1, …}], m_mode 4}] …}`.
- `ConnectorElem` 766662: `m_pDomain → ConnectorElemDomainElectrical
  {m_dVoltage 1291.67 (120 V), m_dPowerFactor 1, m_nNumberOfPoles 1,
  m_idLoadClassification 638828, m_systemType 31, m_powerFactorState 1,
  m_bIsConnectorPrimary True}`, host geometry `m_oPlaneRef.m_geomRef
  {m_elemId 766636, m_geomTag 2}`, faces/planes.
- `ElectricalSetting` 639116: `m_circuitNamePhaseA/B/C 'A'/'B'/'C'`,
  `m_spaceLabel 'Space'`, `m_spareLabel 'Spare'`, `m_circuitRating 20`,
  `m_specificAngles [(11.25,True),(22.5,True),(30,True),(45,True),
  (60,True),(90,True)]`, `m_circuitPathOffset 9.02231`.
- `RbsVoltageType` 277806: `SymbolInfo.m_name '240'`, actual/max/min
  2583.34/2690.98/2368.06 (240/250/220 V). `RbsDistributionSysType`
  277809: `'120/240 Single'`, `m_idVll 277806`, `m_idVlg 55359`,
  `m_kPhase 0`, `m_iNumWires 3`.
- `FamilyInstance` 471580 (an electrical fixture): placement
  `InstanceInfo{m_Trf.m_3x3 rows [[0,0,1],[1,0,0],[0,1,0]], m_or
  [64.43,108.53,17.78] ft, m_symbolId 470440}`, `m_hostId 471504`,
  `m_pDesignPropManager → ElectricalFamInstDesignPropertyManager{m_idSpace
  535894, m_idRoom 576019, m_oLoadClassificationsData …}`, instance
  `FamilyParams` (BuiltInParameter ids −1140xxx with numeric/string values).
- `PanelScheduleView` 709371: full `DBView` state (draw filters incl.
  `IckyExcludedCategoriesSetPtrWrapper.m_categoryIds` of 66 built-in ids,
  retouch/graphic override tables, `m_pRvtLinkOverrides`), 153,800-byte
  object decoded clean.
- Wires/conduits are curve-driven like walls: `RbsCurveConnectorManager`
  with two `Connector`s (`m_arrRefs` → the connected element ids, e.g.
  wire 469465 ↔ 467473), `SegmentConnector{Position,DataModifier,
  Calculation}` modifiers, `RbsCurveDriver.m_pCrv → GLine`.

`ClassDefinitionRef` in seq-101 `ElementHeader.m_classDef` names each
element's class, so an MEP element inventory needs only seq 101.

## 9. Blockers / next-iteration work queue (ranked)

Only **B1** is a decode failure; the rest are semantic or coverage gaps.

**B1. Extensible-Storage entity blobs (`ESEntity.m_blob`) — the only
failures corpus-wide.** Path
`Element.m_cellList → CellList.m_cells[] → ESEntityCell.m_entityMap :
container of pair<GUIDvalue schemaGuid, ESEntity>`. `ESEntity.m_blob` is
declared `ptr` but is NOT an archive object: the token is `i32 pid = -1`
followed by the **16-byte schema GUID again** and then the entity's field
data serialized per that Extensible-Storage schema (defined at runtime by
Revit/add-ins), so there is no `u16` archive class after the pid. Evidence,
rstbasic `RebarShape` 1377250, payload +0x80e:
```
… 01 00 00 00 00 00 01 00 00 00 [59 79 81 4c 28 00 83 4a b3 e7 cd 1e 83 2a 45 9a]   pair.first schema GUID
| ff ff ff ff  [59 79 81 4c 28 00 83 4a b3 e7 cd 1e 83 2a 45 9a]                       pid=-1 + same GUID
  00 00 00 00 00 00 f0 bf …                                                          entity data (double -1.0 …)
```
rme `FamilyInstance` 392203, +0x4b5: `ff ff ff ff 14 23 2a 76 1c 1d 87 40 a5
8f ba b9 02 f5 7b e5 | 01 ff ff ff ff 2d 0a 02 00 00 00 …` (schema GUID
`762a2314-1d1c-4087-a58f-bab902f57be5`, 1,171 instances share it).
Resolution path (verified): both schema GUIDs occur in the same file's
`Global/Latest` (rme `+0x327614`, rstbasic `+0xe931f`) inside the
**`ADocument` Extensible-Storage schema table** (`ESSchemaStorage` 0x56f
`m_storedForgeSchemas : container<pair<AString,AString>>` — schema name +
JSON with Forge units like `autodesk.unit.unit:feet-1.0.1`, field names
`ASHRAETableName`, `AnalysisId`, schemas `AREXContentGenerator`, …). Next:
decode `ADocument` (0x1c) in `Global/Latest` with this same decoder, build
the schema-GUID → ESSchema field list map, and give `ESEntity` a custom
reader. Impact: 1,171 rme + 7 rstbasic records (0.3 % of the corpus).

**B2. `Global/Latest` / `ADocument` not yet fed through this decoder.**
`ADocument` (0x1c) is a schema class like any other; the wave-1
`global_latest.py` heuristics predate the schema. Feeding the whole
`Global/*` object streams to `ObjectDecoder` should now be direct and
unlocks B1's schema table, `ContentDocuments`, `History`.

**B3. dach-sample-project (128 MB partition) not decoded** — no data, only
runtime; the workshared file may exercise classes/paths not in the five
samples. `RVT_SEG_CACHE` caches the concatenated segment for repeats.

**B4. Cross-record weak references unresolved.** `weakref(pid)` resolves
inside one record (1 = document, 2 = root, 3… local). Whether an archive
pid can reference an object serialized in a *different* record (a
document-global object table) is unverified; all observed weak refs so
far resolve locally or to 1/2.

**B5. Parameter semantics.** `ParamValueSet{Double,Int,AString,ElementId}
.m_paramSet[i].m_paramId` are negative **BuiltInParameter** enum values
(`-1001109`, `-1012201`, `-1140142` …) and positive shared/family parameter
element ids; naming them needs a BuiltInParameter enum table (not in
`Formats/Latest`; derive from RevitAPI or an id→name resource) and
`ParamElemFamily`/`ParamElemExternal` records (which DO decode: `m_caption
'Width'`, ForgeTypeId `'autodesk.spec.aec:length-1.0.0'`).

**B6. Units layer.** All values are Revit internal units (ft, ft², ft³,
rad, kg·ft²·s⁻³·A⁻¹ volts, …); a conversion table keyed by field / spec
(ForgeTypeId strings are already decoded, e.g. `autodesk.unit.unit:
millimeters-1.0.1`) is needed before values are user-facing.

**B7. Geometry semantics (seq 103 `GElement`).** The `GRep`/`GNode` tree
(`GFilter`, faces, edge loops, `m_subNodes`) decodes to 100 % of bytes but
its geometric meaning (solid faces/loops vs. the wall's `GLine`, curtain
panels, `ExtrusionElem` profiles) is unvalidated — validate against the IFC
oracle (`vendor/magnetar-revit-test-datasets`) / element extents.

**B8. `stamp` (u32) unexplained** — 85,799 distinct values in 85,814
racbasic records; `[H]` a per-object stamp/checksum; not needed for
reading.

**B9. `char`(0x02)/`short`(0x03)/flag `0e 04` var-node pointer edge cases**
— all decode clean in-corpus, but coverage of these rare kinds is thin
(char ×69 fields, short ×27, `0e 04` ×4 on `VarExpr`); watch on new files.

**B10. Element → type → family joins are id-based, not built.** e.g. wall
→ `m_WallAttributesId` (11 `BasicWallType`s: compound structure layers),
level → `m_attrId` (`LevelAttributes`), instance → `m_symbolId` →
`FamilySymbol` → `Family`. All the ids decode; a small `ElementIndex`
(id → (seq101 header, seq102 object, seq103 grep)) API is the next
readability step.

Corrected en route (was blocking): `partitions.partition_stream_paths()`
globs `Partitions__*.bin` and therefore also picked up the de-paged
`Partitions__N.logical.bin` extraction artefact, appending a garbled
duplicate of the segment head (phantom duplicate `KeynoteTable` records and
bogus `AString length` failures at file-specific offsets). `objects.
load_segment()` now skips `.logical.bin`; the shared helper still has the
bug — see `docs/inbox/object-decoder.md`.

## 10. Cross-checks

- **ElementIds ↔ `Global/ElemTable`:** all 8,401 ElemTable ids ⊂ the
  85,814 partition record ids; `Element.m_id == record id` for every
  decoded object; decoded reference ids intersect the table (2,886 of
  37,168 collected id-typed values in a 1-in-7 record sweep; test asserts
  ≥ 200 — most references point at elements the ElemTable does not index).
  Levels/walls/views/categories reference each other by real ids
  (`SWall.m_upToLevelId 196629 = 'Roof Line'`; `DBViewPlan 245424
  'Level 2'` has `m_genElemId 245423` = the `'Level 2'` Level element, and
  its `m_levelBelowElev 9.8425` equals that level's decoded elevation).
- **Strings ↔ `08-strings-map.md`:** the map's Level names (`Level 2`,
  `Level 1 Living Rm.`, `Datum Level 1`), view names (`Ground floor`,
  `Living Rm.`, `Solar Analysis`), type names (`Wall - Timber Clad`),
  keynote/asset strings are exactly the `m_text` / `m_viewName` /
  `SymbolInfo.m_name` AStrings the decoder now yields with their owning
  field known — the map's `[hypothesis]` "level elevation double follows
  the Level name" is *not* how it is stored: the name is `DatumPlane.m_text`
  and the elevation is the `Plane.m_origin` of the deferred surface object
  ~200 bytes later.
- **Schema anchors:** the record class ids seen (0x9e7 Level, 0xf02 SWall,
  0x25b BasicWallType, 0x478 DBViewPlan, 0x2e1 CategoryElem, 0x5e5
  ElementHeader in seq 101, 0x89e GElement / 0x0f2c SerializedDummy in
  seq 103) all decode under identity — a 300+-anchor extension of the
  16-anchor id proof.

## 11. Unknowns

- ES entity blob field encoding beyond `pid=-1 + schema GUID` (B1).
- `u32 stamp` semantics (B8); id `-1` sentinel's `stamp = 1` in seq 102.
- Meaning of `SerializedDummy`'s empty object (psize 2): `[H]` "element has
  no cached geometry rep in this partition".
- Semantics of `pid > 2` numbering across sub-objects vs. Revit's runtime
  object identity; whether pids are stable across saves.
- `GNode.m_subNodes` filter/marker classes' geometric role (B7).
- Whether any element class serializes fields NOT in `Formats/Latest`
  (custom `serialize()` overrides): only `ESEntity` found so far; the
  100 % byte coverage bounds any others to zero in these five files.

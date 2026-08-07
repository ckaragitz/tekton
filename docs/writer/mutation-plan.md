# Mutation plan — the writer's algorithm for creating native Revit elements

Agent: `mutation-planner` (wave: writer). Companion artefacts:
`docs/writer/specimens/*.json` (annotated real elements),
`docs/writer/template-catalog.md` (instantiable ids per seed),
`src/rvt/mutate.py` (working planner + prototype), `tests/test_mutate.py`.
Confidence tags: **[V]** verified byte-exact on the corpus, **[H]**
hypothesis (needs Revit acceptance), **[D]** design decision.

## 0 · TL;DR

Adding an element to a Revit 2026 project is **not** a new save unit and
**not** a new `Partitions/<N>` stream. It is:

1. mint an ElementId above the file-wide watermark and append a 40-byte
   `ElemRec` to `Global/ElemTable`;
2. insert **three records** — `ElementHeader` (seq 101), the element
   object (seq 102), a geometry rep (seq 103) — into **save unit 0** of the
   existing `Partitions/<N>` (unit 0 IS the host document; its ids are
   exactly the ElemTable ids), re-blocking unit 0 and copying every
   embedded-family unit verbatim;
3. record the save: one new `DocumentIncrement`, one new `History` episode,
   the matching GUID in `BasicFileInfo`;
4. re-page with per-page ECC (the other fleet) and re-write the CFB
   (already solved).

Two decoder facts this agent SOLVED make the record layer fully
computable: the seq-102/103 `u32 stamp` = **`adler32(u16 class_id + object
bytes)`** [V, 287,441 records, 0 exceptions], and the save-unit /
sentinel structure (§3). Element records are minted by **cloning real
specimens** from the same template and patching a small, enumerated field
set (§5).

## 1 · The physical model of "one save" (what changes on disk)

`Partitions/<N>` is **N = the current major increment − 1** [V]: racbasic
16 increments → `Partitions/15`; rme 15 → `/14`; racadv 14 → `/13`;
rstbasic 22 → `/21`; dach 86 → `/84` (+ a vestigial empty `/85`). The
"first u32 = max(N)+1" of `Global/DocumentIncrementTable` is simply the
element count of `m_increments`. **Adding elements does not create a new
partition stream** — the whole `Partitions/N` logical stream is re-written
on every save (Revit rewrites; it does not append), keeping N. (A new
partition stream only appears when a save creates a new increment version
listing a new partition number in `m_incrementVersions` — never needed by
the writer.)

Inside `Partitions/N`, blocks group into **save units** [V] but the units
are **documents, not saves** (correcting wave 1):

| unit | contents | evidence |
|---|---|---|
| **unit 0** | the **host (project) document**: every project element, all three seqs | racbasic unit-0 seq-102 records = **8,401 = exactly the `Global/ElemTable` id set**; rme 28,132 = ElemTable; racadv 17,231 = ElemTable (set equality, `test_unit0_is_the_host_element_table`) |
| units 1…k | one per **embedded content/family document**, preceded by a separator carrying its GUID; separator `u32 counter` = that document's record count | racbasic units 1–163: unit 1's GUID `34b22600-3ed6-44b3-b4f1-6596f4d52b43` = ContentDocuments entry-0 key; 60/163 unit GUIDs = the 60 recovered ContentDocuments keys; counter 225 = entry-0's 225-record element table; unit 0 + Σ counters = 85,814 = every record |

ElementIds are unique across the whole file — host and embedded documents
share one id space (rme: 142,174 records, 0 duplicate ids) [V].

**Consequence [D]: to add host elements, insert their records into unit 0
and copy units 1…k byte-for-byte** (their gzip blocks, footers and
separators need no re-encoding — only their absolute logical offsets
shift, and nothing outside the stream references those offsets).

### 1.1 What a save touches — the diff (`Document.diff()`)

| stream | change | detail |
|---|---|---|
| `Global/ElemTable` | +1 `ElemRec` per element (sorted by `m_id`), `count`++, footer `IdentifierSource.m_last` = new max issued id | §2 |
| `Partitions/<N>` | 3 records per element inserted into unit 0 (seq 101/102/103); unit-0 blocks re-emitted; stream header `elem_table_count` = new ElemTable count; units 1…k copied | §3, §4 |
| `Global/DocumentIncrementTable` | one `DocumentIncrement` appended to BOTH `m_increments` and `m_localIncrements` | §7 |
| `Global/History` | one 17-byte episode (fresh v4 GUID + `0x28`) prepended as entry 0; counts++ | §7 |
| `BasicFileInfo` | "Unique Document GUID" / "central model episode GUID" strings = the new episode GUID | §7 |
| `Global/Latest` | none required for elements (optionally append `ADocument.m_storedByRevitBuild` string) | §7 |
| `Formats/Latest`, `Contents`, `Global/PartitionTable`, `Global/ContentDocuments`, `TransmissionData`, preview | copy | schema/index/workset/family payloads are element-independent |
| every stream re-written | re-gzip (zlib level 3 + sync flush), re-page 64,896 + 353-byte ECC (`rvt.ecc.page_trailer(page)` — other fleet), CFB re-write | KNOWLEDGE, `writer.py`, `cfb_writer.py` |

**Minimal-change alternative [D, ranked second]:** touch only `ElemTable`
+ `Partitions/N` and reuse the LAST episode index for the new elements'
`ElementHistory` (no new increment/episode/GUID). Fewer moving parts, but
`m_incrementVersions[0].m_totalElements` (§7) would no longer equal the
partition record count. Because that field visibly tracks the record count
in every sample, the faithful new-save recipe above is the primary path;
the minimal variant is acceptance test T4.

## 2 · Ids and the ElemTable row

**Allocation [V]:** the `Global/ElemTable` footer is
`ElemTable.m_pSource -> IdentifierSource{ m_last : Identifier }` = the
highest ElementId ever issued (racbasic `m_last` 1,098,947 while max live
id 1,098,851 — 96 ids were issued then deleted; the other five files
`m_last == max id`). New elements take `m_last+1, m_last+2, …` and the
writer sets `m_last` to the new maximum. Ids come in loose consecutive runs
(72 % of ElemTable neighbours are id+1), so consecutive allocation looks
native. `Global/ElemTable` decodes cleanly as one schema object
(`0x05c9 ElemTable`) + `u32 0` trailer, like every `Global/*` object stream
[V].

**The 40-byte `ElemRec` [V]** (field order = schema order; whole layout in
`docs/streams/04-elemtable.md`):

| off | field | value for a NEW element |
|---:|---|---|
| +0 | `u64 m_history.m_originalElementId` | = the new id |
| +8 | `u32 m_creationDate` (EpisodeId) | = new episode index E |
| +12 | `u32 m_lastModificationDate` | = E |
| +16 | `u32 m_lastUserModificationDate` | = E (or `0xFFFFFFFF` "never" — 4–41 % of records) |
| +20 | `u64 m_id` | = the new id (sort key; keep table ascending) |
| +28 | `u64 m_OwningElementId` | `-1` for free elements; the owner id for owned ones (e.g. an instance's per-host symbol clone is owned by its instance) |
| +36 | `u32 m_partitionId` | 0 |

`ElemRecPlan.pack()` emits exactly this row (see the demo output). E is
the new episode index = the current `Global/History` entry count (racbasic
848 → new episode 848, count 849) [V for the invariant
`max(m_lastModificationDate)+1 == episode count` in all six files].

## 3 · Record framing and unit-0 emission (seq 101/102/103)

Record layout [V] (`objects.iter_records`):

```
seq 101:  i64 id | u32 psize | payload{u16 class_id, object[psize-2]} | u32 psize
seq 102:  i64 id | u32 stamp | u32 psize | payload{u16 class_id, object} | u32 psize
seq 103:  i64 id | u32 stamp | u32 psize | payload{u16 class_id, object} | u32 psize
stamp   = adler32(payload) & 0xffffffff                        [V] SOLVED
sentinel: i64 -1 | (u32 stamp=1 for 102/103) | u32 psize=0 | u32 0
          exactly ONE per seq per unit, ALWAYS the LAST record of the unit's segment  [V]
```

For a new element the three payloads are:

| seq | class id | payload |
|---|---|---|
| 101 | `0x05e5 ElementHeader` | category, ids, view rules, class def ref, bbox, `ElementParents` (§5.4) |
| 102 | the element's class (`0x0f02 SWall`, `0x07c5 FamilyInstance`, …) | the object (§5) |
| 103 | `0x089e GElement` (cached geometry) **or** `0x0f2c SerializedDummy` (psize 2 = bare class id, stamp `0x0069003C`) | walls: dummy [H, test T1]; instances: clone the 300–600-byte `GElement` (§5.6) |

**Where in unit 0 [D]:** records are keyed by id in all three seqs (same
id order in 101/102/103 [V]); the order within unit 0 is neither id, nor
episode, nor dependency order (2,698/4,239 sampled parent references point
*forward*) — consistent with an unordered container's iteration order,
i.e. semantically arbitrary [H]. Primary choice: **insert each new element's
records immediately after the last existing record of the same class in
unit 0** (mimics the observed loose class clustering); fallback (test T3):
append just before the sentinel. Whatever the order, it must be identical
across the three seqs.

**Block re-emission of unit 0 (only unit 0 changes):**

```
for seq in (101, 102, 103):            # unit 0's segment for this seq
    stream = concat(records) + sentinel
    chunk stream into blocks of <= ~131,072 inflated bytes, respecting:
        flags: 4 whole-records | 6 last record continues | 7 pure continuation | 5 continuation ends
        A = record headers starting in block, C = record body bytes in block,
        ISIZE == hdr_len(seq)*A + C + adj(flags)   (adj: 4:0, 5:+4, 6:-4, 7:0)   [V, 13,535 blocks]
    per block: 26-byte header {u16 0x0f28, u32 flags, A, B=8+len(member), C, seq, u32 0}
               + gzip member (zlib level 3, sync flush, valid CRC32/ISIZE)
               + 6-byte trailer {u16 0x0f21, u32 B}
unit 0 ends with the 18-byte terminator + 0x0f3f footer (64-byte blob + UTF-16
'Data generated by Autodesk® Revit®'), unchanged in kind from the template.
then: units 1..k copied verbatim (separator + blocks + footer each), then the
stream end record. Simplest correct chunker: whole records only (flags 4)
while the next record fits; a record larger than the block budget spans
(6 → 7… → 5). The block budget need not match Revit's exactly — the reader
walks B, not a fixed size (dach/85 has 36-byte blocks).
```

The stream header's `u32 elem_table_count` = the new ElemTable count [V:
equal in every file]. Per-block `B` and the trailer copy of `B` must match
[V: 13,535/13,535].

### 3.1 The `stamp` proof (this agent)

| id (racbasic) | class | stored stamp | `adler32(u16 class_id + object)` |
|---:|---|---|---|
| 311 | Level | `0x63bdcdfa` | `0x63bdcdfa` |
| 195169 | Grid | `0xd806cf50` | `0xd806cf50` |
| 422243 | SWall | `0xbb166e01` | `0xbb166e01` |
| 422466 | FamilyInstance | `0xa5619f06` | `0xa5619f06` |
| 490150 | FamilySymbol | `0x9cd1fefe` | `0x9cd1fefe` |
| 857346 | RoomElem | `0x6c656cd7` | `0x6c656cd7` |

Then all 85,814 racbasic + 142,174 rme + 59,453 racadv records in each of
seq 102 and seq 103: 287,441 / 287,441 match. The SerializedDummy constant
`0x0069003C` = adler32(`2c 0f`); the sentinel's `1` = adler32(empty). The
u32 is Adler-32 — NOT CRC-32 — so it is trivially computed after
serialization. (Solves KNOWLEDGE unknown "B8"/`stamp`.)

## 4 · Referential integrity

Every ElementId a new element's records mention must resolve to an
existing template element (host document or embedded document), another new
element, or a negative built-in id (categories `-2000xxx`, BuiltInParameters
`-100xxxx`) [D]. `Document.check_references()` walks all three records and
reports dangling ids; the specimens' `references[]` arrays are the same walk
over real elements (e.g. wall 422243 → 81 ElementId references, all resolving). Beware
false ids: geometry topology tags (`m_faceHistTable[].m_id`, `GInfo.m_tag`,
`m_geomGeneratorId`, `m_paramId`) are small integers, not elements
(`mutate._NOT_ELEMENT_ID`).

## 5 · ELEMENT-CREATION RECIPE

### 5.1 The algorithm (`Document.add_wall` / `add_family_instance`)

```python
def create_element(kind, spec, template_doc):
    T = choose_specimen(template_doc, spec)          # a real element of the same class,
                                                     # SAME type/symbol (clone donor)  §5.2
    eid = template_doc.next_id()                     # watermark + 1                    §2
    E   = template_doc.new_episode                   # History entry count               §7

    obj = deepcopy(decode(T, seq=102))               # the polymorphic object
    patch identity:   obj.m_id = eid; parents/owners -> -1 unless meaningful
    patch references: level, type/symbol, host, phase   (must exist in template)  §4
    patch geometry:   wall: GLine + 7 ref-face planes; instance: InstanceInfo Trf   §5.3
    patch relations:  wall joins -> empty; instance sub-tables -> empty

    hdr = deepcopy(decode(T, seq=101))               # ElementHeader
    hdr.m_regenHistory = {m_historyMap: []}
    hdr.m_parents (ElementParents) = rebuilt dependency lists for the new deps   §5.4
    hdr.m_pBBox   = recomputed outline (estimate is enough)                      §5.4

    rep = SerializedDummy (wall)                     # regenerate on load  [H, T1]
       or deepcopy(decode(T, seq=103)) patched (Trf/or/symbolId/tags)  (instance)  §5.6

    row = ElemRec(orig=eid, create=mod=user=E, id=eid, owner=-1, partition=0)      §2
    for (seq, cls, o) in ((101, 0x5e5, hdr), (102, obj.class, obj), (103, rep.class, rep)):
        payload = u16 cls + encode_object(cls, o)    # rvt.encode  (parallel agent)     §8
        record  = frame(seq, eid, adler32(payload), payload)                      §3
    insert the three records into unit 0; append row to ElemTable; run diff() streams §1.1
```

### 5.2 Choosing the specimen (clone donor) [D]

The donor supplies every field the spec does not name — this is why the
approach works at all: the ~300-field object of a wall (compound-structure
faces, geometry steps, cells, param sets) is *correct by construction*
because it came from a valid wall of the same type.

- **Wall:** a straight (`GLine`) non-curtain `SWall` whose
  `m_WallAttributesId == spec.wall_type_id`; smallest such object (fewest
  joins/sweeps). No donor of that type ⇒ the type is not clonable yet
  (`wall_types_with_instances()`); raise, do not guess.
- **Family instance:** an instance with `m_symbolId == m_masterSymbolId ==
  spec.symbol_id`; else one of the same category with the direct
  (symbol == master) pattern; the caller may name the donor
  (`template_instance_id`) — required for face-hosted equipment (§6.3).

### 5.3 New straight wall — field sources (`SWall` object, seq 102)

Serialization is parent-first: `Element` (20 fields) → `HostObj` → `VWall`
→ `SWall` (0 own fields). "src" = **I**nput spec / **T**emplate clone /
**C**onstant / **X** computed. **Bold = the minimal set the writer must
set** (everything else is a straight clone).

| field | src | value / rule |
|---|:-:|---|
| `Element.m_pParamValueSetDouble ->ParamValueSetDouble.m_paramSet[]` | T + **X** | keep the donor's set; set param **−1001101** (computed height) = `top_elev − base_elev` (or spec height) and, when unconstrained, **−1001105** (unconnected height) = height. Other observed ids `-1001108/-1001109/-1001111/-1012828/-1012829` = 0 (offsets). BIP→name mapping is open item O2. |
| `m_pParamValueSetInt / AString / ElementId` | T | usually null on walls |
| `m_geomSteps -> GeomStepList` (`WallRefPlanesGStep`, `BaseWallGStep`, `JoinEndGStep`, `VerticalExtensionOfLayersGStep`, `SweepGStep`; each `m_pElem = weakref(2)`) | T | the regeneration recipe; identical per wall type; keep (its face/edge history tags are topology tags, not element ids) |
| `m_pGeomTable -> GeomTable.m_table[].m_geomGeneratorId` | T | keep |
| `m_constrInfo` | T | `[]` |
| `m_cellList -> CellList.m_cells[]` (`AnalyticalSpaceBoundingCell`, `CoverSettingsCell`, `PatternHelper`, …) | T | keep (per-class default cells) |
| `m_docAccess.m_pDoc` | C | `weakref(1)` (the document) |
| **`m_id`** | **X** | = new id (== record id in all 3 seqs, == ElemRec.m_id) |
| **`m_assocLevelId`** | **I** | base level id (existing) |
| `m_famId` | C | `-1` |
| `m_unplacedOwnerId`, `m_ownerDBViewId` | C | `-1` |
| **`m_createdPhaseId`** | I/T | phase id (racbasic/rme: `ProjectPhase` 86961) — must exist |
| `m_demolishedPhaseId` | C | `-1` |
| `m_designOptionId` | C | `-1` (main model) |
| `m_locked / m_moribund / m_dummy` | C | false |
| `HostObj.m_hostObjMiscData`, `m_oGeomToElemMap` | T | null (non-curtain) |
| `HostObj.m_roomBounding` | I/T | true |
| `VWall.m_drivenCGLineDataU/V` | C | null |
| **`m_pCurveDriver -> VWallDriver.m_pCrv -> GLine`** | **X** | `m_origin = p0 (z = base elev)`, `m_dirVec = unit(p1−p0)`, `m_endParams = [0, |p1−p0|]` (feet). `GInfo.m_flags 17301508` from T. Length = `endParams[1]−endParams[0]` [V]. |
| **`VWallDriver.m_sideJoins`, `m_controlJoinsSet`, `m_endJoins`** | **X** | `[]` — new wall is unjoined (Revit rebuilds joins on regen). `m_noJoinAtEnd [false,false]`, `m_midParams []`, `m_flip false`, `m_joinStrength 3` |
| **`m_pRefFaces[] -> Face -> Plane`** (7 in the donor: side faces + layer planes) | **X** | for each face keep its perpendicular OFFSET from the location line (from T) and rebuild `m_origin = p0 + n̂·offset`, `m_xVec = wall dir`, `m_yVec = [0,0,1]`, `m_Envelope.m_corners = [[0,0],[length, height]]`; `m_faceFlags_v9`, `GInfo` tags from T. (`Document._rebuild_wall_faces`) |
| `m_embeddedTo` | C | `[]` |
| `m_wallRunTimeData` | C | null |
| `m_keyRefOffset / m_locLineOffset` | T/I | location-line justification offset (0 = wall centerline) |
| **`m_WallAttributesId`** | **I** | wall type id (existing `BasicWallType`) |
| **`m_upToLevelId`** | **I** | top constraint level id, or `-1` (unconnected, height by param) |
| `m_analyticalProjectionSurfaceId/TopPlane/BottomPlane`, `m_contFootingId` | C | `-1` |
| `m_curtainAuxData.m_mullionTdFlags` | T | 128 for basic walls |
| `m_version` | C | 5 |
| `m_subWallGridIdInType` | C | `-1` |
| `m_wallStructuralUsage`, `m_wallKeyRef`, `m_wallCrossSection` | T | 1 / 0 / 1 |
| `m_isFlipped` | I/T | side |
| `m_isStructuralSignificant` | C | false |
| `m_oUserData`, `m_oDefiningFaceRefs` | C | null |

### 5.4 The `ElementHeader` (seq 101) and its `ElementParents`

`ElementHeader` (class `0x05e5`, ~280 bytes) [V, `rac_wall_422243_SWall.json`]:

| field | src | new value |
|---|:-:|---|
| `m_regenHistory.m_historyMap` | C | `[]` |
| **`m_categroryId`** (sic) | C by class | walls `-2000011` OST_Walls; doors `-2000023`; el. equipment `-2001040`; el. fixtures `-2001060`; lighting `-2001120`; rooms `-2000160`; MEP spaces `-2003600` |
| `m_familyId`, `m_ownerViewId`, `m_designOptionId`, `m_unplacedOwnerId`, `m_miscId` | C | `-1` (`m_familyId` = family id only for family-owned objects) |
| `m_viewRules.m_nVisibleViewFlags` | T | `-4225` |
| `m_abFlags4Bytes` | T | 6441 (wall) |
| **`m_classDef.m_ref`** | C | class-def ref = the u16 class index of the seq-102 class (`SWall` 0x0f02, `FamilyInstance` 0x07c5) — this is how seq 101 names the element's class |
| `m_pBBox -> Outline.m_minmax` | **X** | axis-aligned min/max in feet (wall: line ± thickness/2, base..base+height; instance: symbol footprint estimate). Regenerated by Revit — an estimate suffices [H]. |
| **`m_parents -> ElementParents`** | **X** | dependency lists (below) |

`ElementParents` for a new wall (all ids must exist):
`m_deletion = sorted{base level, top level, phase, wall type, self id}`;
`m_appearanceParents = {30 (a GStyleElem), base level, wall type}`;
`m_regenOnly = [30]`; every other list `[]`; `m_hasNonDetermRegenChildren
= false` (the donor's `true` refers to its hosted doors/rooms). For an
instance: `m_deletion = {level, symbol, phase, host?, self}`,
`m_appearanceParents = {symbol}`, `m_regenOnly = {family}`. The donor lists
mention the donor's own dependents (its doors, joined walls, rooms) — these
MUST be replaced, never copied (they would make deleting our wall delete the
donor's door) [D].

### 5.5 New family instance — field sources (`FamilyInstance` object, seq 102)

Chain `Element` → `Instance` → `InsertableInst` → `FamilyInstance` (39 own
fields). Phase-1 pattern = **free / face pattern**: `symbolId ==
masterSymbolId == the type`. Minimal set in bold.

| field | src | value / rule |
|---|:-:|---|
| Element fields | as §5.3 | `m_id` = new id, `m_assocLevelId` = level, phase, `-1`s |
| **`Instance.m_pInstanceInfo -> InstanceInfo.m_Trf`** | **X** | `m_3x3 = Rz(rotation)` rows `[[cosθ, sinθ, 0], [−sinθ, cosθ, 0], [0,0,1]]`, `m_or = position (ft)` — the placement transform [V vs `rme_panel_581483`, `rac_door_422466`] |
| **`InstanceInfo.m_symbolId`** | **I** | the type (== `m_masterSymbolId`) |
| `InstanceInfo.m_GRepId` | C | 0 |
| `InstanceInfo.m_cda.m_pDoc` | C | `weakref(1)` |
| `m_GInstanceId` | C | 0 |
| `InsertableInst.m_elevation` | I | offset above level (ft), 0 default |
| `m_hostParam` | X | only for line-hosted (doors): distance along the host wall's location line |
| **`m_hostId`** | **I** | `-1` (level-based free instance) or the host: a `SketchPlane` (face-based equipment, §6.3) or a wall (doors, phase 2) |
| `m_extraHostIds / m_explicitHostIds / m_refs / m_offsetPosArr / m_subInstTable / m_leaders` | C | `[]` |
| `m_pInstParams -> FamilyParams.m_params` | T | instance parameter values (electrical: load, poles, panel name…) — clone; per-instance overrides written here |
| `m_oFamInstSpec` | T | door: `FamInstDoor{m_doorNumber}`; equipment: null |
| `m_pDesignPropManager` | T | electrical: `ElectricalFamInstDesignPropertyManager{m_idSpace, m_idRoom, load data}` — remap `m_idSpace/m_idRoom` to the space containing the position (or clone as-is when placing near the donor) |
| `m_pCurveDriver` | C | null (point instances) |
| `m_pConnectorManager` | T | electrical instances carry an `RbsInstanceConnectorManager`; its `Connector.m_arrRefs[]` reference CONNECTED elements (the circuit) — for an unconnected new instance clone the donor's manager and clear/remap the refs (a fresh instance is on no circuit) |
| `m_posRelToGrid`, `m_oFamInstUserData`, `m_oPOFDriver`, `m_pInplaceInsertionHelper` | C | null |
| `m_instOrigin / m_RefDir / m_zAxis` | T | `[0,0,0] / [1,0,0] / [0,0,1]` (symbol-local frame) |
| **`m_masterSymbolId`** | **I** | = symbol id |
| `m_ownerElemId`, `m_superInstanceId`, `m_assocSketchPlaneId`, `m_analytical*PlaneId` | C | `-1` |
| `m_scheduleOnlyLevelId` | I/C | `-1`, or the level for face-hosted elements that schedule to a level |
| `m_famElemVisibility.m_flags` | T | `-1` |
| `m_structType / m_structUsage / m_insertOrientation` | T | 0 |
| `m_roomBounding` | T | true |
| `m_flippedX / m_flippedY / m_flippedFromToRoom` | I/T | mirror flags |
| `m_workPlaneBased` | X | true iff face-hosted (host = SketchPlane) |
| `m_workPlaneFlipped / m_useOffsetPos / m_invisible / m_bVertical / m_instDormant` | T | false…, `m_bVertical` true |

### 5.6 The geometry rep (seq 103)

- **Walls, wall types, rooms, symbols: `GElement` cached solid** (racbasic:
  64/64 walls, 14/14 rooms carry one; 18–56 KB). The writer emits
  **`SerializedDummy`** for a new wall [H, test T1]: the element object
  carries the full regeneration recipe (`m_geomSteps` + `m_pGeomTable`),
  and 73,951/85,814 racbasic records are already dummies (levels, grids,
  families, most annotation). Fallback if Revit rejects an ungenerated wall
  (T2): clone the donor's `GElement` and rigid-transform every `m_origin` /
  coordinate array (valid only when length/height match the donor).
- **Family instances: a small formulaic `GElement`** (`rme_panel_581483`
  390 B, `rac_door_422466` 298 B): `GElement{m_GInfo{m_categoryId =
  internal graphics category (124 el.-equipment, 44 doors), m_tag = elem id},
  m_subNodes: [GGroup?…, GInstance{InstanceInfo{Trf, m_or, m_symbolId}}],
  m_bBox, m_tightbBox, m_elementId, m_gElemType 3}`. **Clone the donor's rep
  and patch `m_tag`, `m_elementId`, the GInstance's `InstanceInfo` (same
  Trf/or/symbolId as the object) and the boxes** — implemented in
  `add_family_instance`.

### 5.7 Worked example (from the demo run)

`Document.load('racbasicsampleproject').add_wall(level_id=311,
wall_type_id=232827, p0=(0,0), p1=(20,0), height=10)` → donor 506386
("Interior - Partition"), new id 1,098,948 (= watermark 1,098,947 + 1),
episode 848, ElemRec `c4 c4 10 00 … | 50 03 00 00 ×3 | c4 c4 10 00 … | ff×8 |
00 00 00 00`, 0 dangling references. `add_family_instance` → id 1,098,949,
0 dangling references. Against rme: a panelboard `455409 '400 A'` cloned
from panel 581483 onto SketchPlane 581481, a receptacle 342654 cloned from
467291 onto wall 467294, an `STB 20.0` wall from Level 1→2 — all
referentially clean (`tests/test_mutate.py`, 13 passed).

## 6 · Hosting patterns (what the corpus permits)

### 6.1 Free / level-based instance — PHASE 1 [V pattern]
`m_hostId = -1`, `m_assocLevelId = level`, `symbolId == masterSymbolId`,
`m_workPlaneBased = false`. 202/495 racbasic instances (furniture, site,
generic models, PV panels, some lighting).

### 6.2 Wall — PHASE 1 (recipe §5.3), the acceptance-critical test.

### 6.3 Face-hosted MEP equipment — PHASE 1½ [V pattern]
Every rme electrical-equipment instance (panelboards, transformers,
switchboards) and receptacle is face-hosted: `m_workPlaneBased = true`,
`m_hostId` = a **`SketchPlane`** element lying on the host wall/face
(`SketchPlane.m_oPlaneRef -> GeomRef{m_elemId = host wall, m_geomTag =
face tag}`, `m_userId` = one instance on it), and several instances SHARE
one SketchPlane (581482–581485 all host 581481). ⇒ placing a panel on a
face that already carries equipment = **one new FamilyInstance whose
`m_hostId` is that existing SketchPlane** (verified clean:
`test_add_panelboard_rme`). Placing on a virgin face additionally needs a
new `SketchPlane` (class `0x0f5d`: `m_oPlaneRef`, `m_oTrf`, `m_userId`,
`m_flipZ`) cloned from an existing one on a face of the same host — phase
2 refinement. `m_or` z of face-hosted panels = mounting height on the face.

### 6.4 Host-cut instances (doors, windows) — PHASE 2 [V pattern]
16/16 doors and 17/17 windows reference a **per-host geometry-symbol
clone**: `InstanceInfo.m_symbolId` = an unnamed `FamilySymbol` (owned by
the instance/host, carrying `m_pCutLoops`, `m_cutDirs`, `m_closurePlanes`
for the wall thickness) while `m_masterSymbolId` = the real type (490150
vs 232780 in `rac_door_422466`). Recipe: reuse an EXISTING clone of the
same door type in a wall of the same type (share it, `m_symbolId` = clone
id) and set `m_hostId` = wall, `m_hostParam` = distance along the wall's
location line, `m_or` = the point on the line; otherwise author a clone
`FamilySymbol` (a fourth element) — the largest open recipe.

### 6.5 Circuits — PHASE 2 [V structure]
`RbsElectricalSystem` clone: rewrite `m_pConnectorMgr ->
RbsSystemConnectorManager.m_connPtrArray[].m_arrRefs[]` (loads: `{m_id =
device, m_nIndex 1, m_connType 1}`; the panel: `{m_id = panel, m_nIndex
50000+slot, m_connType 4}`), `m_baseConnectorIdArray`, `m_number`,
`m_strDescription` (panel name), voltage/rating/load doubles (internal
units: V ÷ 0.3048² etc.); AND the connected instances' own connector
managers must reference the circuit back (`Connector.m_arrRefs[].m_id =
circuit id`) — a two-sided edit, plus `ElementHeader` parents both ways.

## 7 · The save bookkeeping streams

**`Global/DocumentIncrementTable`** = `u16 0x53c` + `DocumentIncrementTable
{ m_increments : container<DocumentIncrement>, m_localIncrements :
same, m_permutation : [] }` + `u32 0` — decodes cleanly with the schema
decoder [V, this agent]. `DocumentIncrement` (0x53a) fields and the new
row's values:

| field | new value |
|---|---|
| `m_incrementVersions[]` (`DocumentIncrementVersion`) | `[{m_causedByIncrementNumber: -1, m_totalElements: <new host record count>}]` (the current increment lists one entry per live partition; a save that spawned a partition adds `{caused: N, 0}`) |
| `m_userName` | writer's chosen user name (samples: `zhangg`, `hansonje`, `loboarch`) |
| `m_comment` | `""` |
| `m_greatest.m_id` | new max EpisodeId (E) |
| `m_totalEpisodes` | E + 1 |
| `m_atimeStamp.m_lsb` | Unix time of the save (`m_msb` 0) |
| `m_majorVersion` | previous major + 1 |
| `m_totalElements` | 0 |
| `m_previewStreamRevision, m_globalStreamRevision, m_historyStreamRevision, m_elemTableStreamRevision, m_partitionTableStreamRevision, m_incrementTableStreamRevision, m_formatsStreamRevision, m_basicFileInfoStreamRevision, m_contentDocumentsStreamRevision, m_transmissionDataStreamRevision, …` | previous row's value **+1** for each stream re-written (all of them here) |
| `m_overwrite` | false |

Evidence (racbasic, 16 rows, one per save 2015-11-09 → 2025-03-13): the
last row's `m_incrementVersions[0].m_totalElements` = **85,814 = the
partition record count**; `m_totalEpisodes` 848 = History count;
`m_greatest` 847; timestamps monotone; every revision counter +1 per row.
Append the identical row to `m_localIncrements` (both containers are
byte-identical in all samples of non-workshared files).

**`Global/History`** (fully decoded, `docs/streams/06-content-history.md`):
prepend one 17-byte entry `{fresh RFC-4122 v4 GUID (bytes_le), 0x28}` as
entry 0, bump the two count fields (`+0x0e` and the array count). Entry 0's
GUID must equal **`BasicFileInfo`'s "Unique Document GUID"** (and the
"central model episode GUID"), stored there as UTF-16 text — update both
[V: identity holds in all six].

**`Global/Latest`**: no element data; nothing required. (Its
`ADocument.m_storedByRevitBuild` list of build strings — "Revit 2026 …
20250227_1515" is already last — need not grow.)

## 8 · Interface to the serializer (`rvt.encode`, parallel agent)

`mutate` hands over decoded dicts + framing metadata; the encoder is the
symmetric inverse of `rvt.objects` (parent-first field order; codebook:
AString `u32 count + UTF-16LE` / `0xFFFFFFFF` null, GUID 16, ElementId
i64, XYZ/Trf fixed double arrays, containers `u32 count + elements`,
owned/poly ptr `i32 pid + u16 class` with breadth-first deferred bodies,
weak ptr `u32 pid`). Contract assumed:

```python
rvt.encode.encode_record(seq, id, stamp, class_id, obj) -> bytes  # full framed record
# stamp for seq 102/103 = adler32(u16 class_id + object bytes); pass None -> encoder fills.
# seq 101 has no stamp field.  psize = 2 + len(object bytes).
```

`Document.serialize(el)` calls it if importable and otherwise returns
None (`test_serialize_stub`). The pointer `pid` numbering must be
reproduced per record: `pid -1` anonymous, `pid ≥ 3` for objects that are
weak-referenced later (e.g. GLine `pid 10` referenced by `RefFace`), `1`
= document, `2` = the record's root — the encoder should re-derive pids
from the dict tree, not preserve the donor's numbers verbatim [D].

## 9 · Acceptance test matrix (what the Windows/APS gate must run)

| test | file | expectation | de-risks |
|---|---|---|---|
| **T0** | seed re-emitted with zero changes through the full pipeline (records → blocks → gzip → pages+ECC → CFB) | opens identical | pipeline baseline (container V0 already passes) |
| **T1** | racbasic + 1 free family instance (dryer 677680 / PV panel 776839), rep = cloned GElement | new instance visible/selectable/schedulable | id allocation, ElemTable, unit-0 insertion, increment/episode bookkeeping |
| **T2** | racbasic + 1 wall (`Interior - Partition` 232827, Level 1→2), rep = SerializedDummy | wall regenerates, correct length/height/type | wall recipe, dummy-rep hypothesis |
| T2b | same, rep = donor GElement rigid-translated | fallback if T2's dummy is rejected | |
| T3 | T1 with records appended before the sentinel instead of class-clustered | opens | ordering hypothesis (§3) |
| T4 | T1 without new increment/episode (minimal-change variant) | opens? | whether §7 bookkeeping is mandatory |
| **T5** | rme + 1 panelboard on SketchPlane 581481 + 1 receptacle | equipment appears, has connectors, is circuit-assignable in Revit | MEP instance pattern |
| T6 | rme + 1 circuit (clone of 469428 wiring 2 existing receptacles to panel 581483) | circuit shows in the panel schedule | §6.5 two-sided edit |

## 10 · Confidence / unknowns

| claim | status |
|---|---|
| unit 0 = host document = ElemTable ids; units 1…k = embedded documents; ids file-wide unique | **V** (3 files, set equality) |
| adding elements = insert into unit 0, keep N, copy embedded units; no new save unit / partition | **V** structure + **D** |
| record framing, sentinel-last, `stamp = adler32(payload)`, `psize`, dummy const | **V** (287,441 records) |
| ElemRec layout; watermark = `IdentifierSource.m_last`; new id = watermark+1 | **V** |
| DocumentIncrement row semantics (per-save row, totalElements = record count, revisions +1) | **V** (racbasic 16 rows, rme 15, racadv 14) |
| History episode + BasicFileInfo GUID identity | **V** |
| clone-and-patch field recipes (§5.3–5.6), ElementParents lists | **H** — internally consistent and referentially clean, but only Revit can judge |
| new wall with SerializedDummy rep (no GElement) is accepted/regenerated | **H — test T2** |
| record order within unit 0 is semantically arbitrary | **H — test T3** |
| bbox / ref-face estimates suffice (regenerated) | **H** |

**Open items:** O1 wall types without a donor (exterior brick 397/54538);
O2 BuiltInParameter id → name table (`-1001101` height, `-1001105`
unconnected height inferred from values only); O3 door recipe = symbol
cut-clone (§6.4); O4 the u32 `Global/*` 8-byte prefix and Latest revision
mirrors — untouched here; O5 the internal graphics category ids in
`GInfo.m_categoryId` (124, 44, 137306…) — copied from same-category
donors; O6 whether Revit tolerates `m_lastUserModificationDate = E` vs
`0xFFFFFFFF`; O7 the `ATime`/user provenance policy for our synthetic save.

## 11 · Reproduction

```
RVT_SEG_CACHE=<dir> .venv/bin/python docs/writer/specimens/make_specimens.py   # regenerate the 19 specimen JSONs
RVT_SEG_CACHE=<dir> .venv/bin/python -m rvt.mutate racbasicsampleproject         # demo: new wall + instance plan
RVT_SEG_CACHE=<dir> .venv/bin/python -m pytest tests/test_mutate.py -v           # 13 passed
# catalog tables: rvt.mutate.Document.load(p).levels() / .symbols(cat) / .wall_types_with_instances()
```

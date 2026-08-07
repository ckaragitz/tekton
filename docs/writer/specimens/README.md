# Element specimens — decoded, annotated real elements for the writer

Agent: `mutation-planner`. Every file here is a **complete real element**
extracted from a sample project and decoded by `rvt.objects` (the
schema-directed decoder), joined across its three partition record streams
plus its `Global/ElemTable` row, with its full ElementId reference
closure. These are the CLONING TEMPLATES that `src/rvt/mutate.py` edits to
mint new elements, and the ground truth behind
`docs/writer/mutation-plan.md`.

Reproduce / extend: `docs/writer/specimens/make_specimens.py` (edit its
`SPECS` table, one entry per element id) regenerates every JSON here from
the corpus; the decoded values are exactly what
`rvt.objects.ObjectDecoder` yields (nested dicts; pointers as
`{ptr_class, pid, value}`; weak refs `{weakref: pid}`; ElementIds as
ints; GUIDs as strings; long containers capped at 60 entries with a
`"... N more"` marker).

## File format

```json
{
  "element_id": 422243,
  "note": "human description of the specimen and its relations",
  "elemtable": {                       // its 40-byte Global/ElemTable ElemRec, every byte labelled
    "found_in_ElemTable": true,
    "raw_40_bytes_hex": "63 71 06 00 ... ",
    "fields": {"+0 u64 m_history.m_originalElementId": ..., "+8 u32 creation EpisodeId": ..., ...}
  },
  "category": {"id": -2000011, "builtin": "OST_Walls"},   // from the seq-101 header
  "classDef": "SWall",                                     // ElementHeader.m_classDef
  "seq101": {  // ElementHeader record  (record framing + decoded object)
    "segment_offset": ..., "framing": "i64 id + u32 psize + payload + u32 psize",
    "elem_id": ..., "psize": ..., "class_id_hex": "0x05e5", "object_bytes": ...,
    "total_record_bytes": ..., "size_trailer_ok": true, "payload_head_hex": "...",
    "class": "ElementHeader", "clean": true, "consumed_of_object": "279/279",
    "value": { ...decoded ElementHeader... }
  },
  "seq102": { ... the polymorphic element object itself (SWall, Level, ...); adds "stamp" (u32) ... },
  "seq103": { ... the geometry rep: GElement (cached geometry) or SerializedDummy (psize 2) ... },
  "references": [                     // dependency closure: EVERY ElementId this element mentions
    {"from_seq": 102, "path": "m_WallAttributesId", "id": 198367,
     "target_class": "BasicWallType", "in_ElemTable": true, "in_partitions": true},
    ...
  ]
}
```

`stamp` (u32 in the seq-102/103 record headers) = `adler32(u16 class_id +
object bytes)` — solved by this agent, see mutation-plan §4.1. `clean:true`
+ `consumed_of_object == n/n` = the decoder consumed every object byte with
zero errors (all specimens here are clean).

## The specimens

### `racbasicsampleproject` — architectural (the wall/door template)

| file | element | what it teaches the writer |
|---|---|---|
| `rac_level_311_Level1.json` | Level 311 "Level 1", elev 0 ft (`DatumPlane` + deferred `Plane` surfaces, type `LevelAttributes` 305) | a datum: name in `m_text`, elevation = `m_pSurface->Plane.m_origin[2]`, seq103 = SerializedDummy |
| `rac_level_245423_Level2.json` | Level 245423 "Level 2", elev 9.84252 ft (3.0 m) | second level for wall top constraints |
| `rac_levelattr_305.json` | LevelAttributes 305 = the shared level TYPE (`m_attrId` of every project level) | type element referenced by all levels |
| `rac_grid_195169_1.json` | Grid 195169 "1", type GridAttributes 341 | `Grid < DatumPlane`; grid line = plane origin/xVec; seq103 SerializedDummy |
| `rac_wall_422243_SWall.json` | straight wall SWall 422243, base Level 1 (311) → top Ceiling (694), type BasicWallType 198367, location line `GLine` len 9.977 ft, joined to walls 198749/906885/845266, hosts door 422466; 7 driven ref faces; seq103 = 18,916-byte GElement solid | THE wall template: location line, level refs, type ref, joins, ref-face planes, param set (heights), ElementHeader parents |
| `rac_walltype_198367_BasicWallType.json` | BasicWallType 198367 "Wall - Timber Clad" (compound structure, cells) | the `m_WallAttributesId` target |
| `rac_door_422466_FamilyInstance.json` | door FamilyInstance 422466 hosted in wall 422243 at `m_hostParam` 2.034 (curve param), symbol 490150, master symbol 232780, level 311, `FamInstDoor.m_doorNumber '103'`; seq103 = 298-byte GElement (`GInstance`) | host-cut instance pattern: `symbolId != masterSymbolId` (per-host geometry clone) — phase-2 recipe |
| `rac_doorsymbol_490150_FamilySymbol.json` | FamilySymbol 490150: the per-wall CUT CLONE (name '') of master symbol 232780 "800 x 2100" | why doors need a symbol clone (cut loops for the host wall thickness) |
| `rac_doorfamily_218942_Family.json` | Family 218942 "Single-Flush" (`m_famDocGUID`) | family element; its element data lives in an embedded family document (a Partitions save unit + a ContentDocuments entry) |
| `rac_room_857346_RoomElem.json` | RoomElem (a Room) on Level 1 | rooms: `RoomElem`; seq103 = GElement (room solid) |

### `rmebasicsampleproject` — MEP / electrical (the equipment template)

| file | element | what it teaches the writer |
|---|---|---|
| `rme_level_378117_Level1.json` | rme host Level 1 (elev 0.309 ft) | MEP template datum |
| `rme_panel_581483_FamilyInstance.json` | electrical-equipment FamilyInstance 581483 = a panelboard ("M_Lighting and Appliance Panelboard - 208V MLO - Surface" family 454674), symbol 470440 with master 455409 "400 A"; FACE-HOSTED: `m_workPlaneBased`, `m_hostId` 581481 (a SketchPlane on the host wall face); `m_pDesignPropManager -> ElectricalFamInstDesignPropertyManager{m_idSpace 379575, m_idRoom 573809}`; seq103 = 390-byte GElement | equipment placement pattern: transform in `InstanceInfo.m_Trf` (3x3 + origin `m_or`), face host = SketchPlane element |
| `rme_panelsymbol_470440_FamilySymbol.json` | the panel's symbol | symbol→family→category chain |
| `rme_panelfamily_454674_Family.json` | the panelboard Family | family GUID → embedded family document (its ConnectorElems live there) |
| `rme_panelhost_581481_SketchPlane.json` | SketchPlane 581481 hosting panels 581482–581485 (shared by 4 instances) | face hosting is by reference to an EXISTING SketchPlane; several instances share one |
| `rme_circuit_469428_RbsElectricalSystem.json` | circuit "1" ("Power Technology 28"): `RbsSystemConnectorManager` with 9 receptacle refs (`m_nIndex 1, m_connType 1`) + panel 581483 (`m_nIndex 50001, m_connType 4`) | circuits are ordinary elements; a circuit = element-id refs (loads at index 1, the panel at 50000+slot); seq103 = SerializedDummy |
| `rme_fixture_467291_FamilyInstance.json` | receptacle FamilyInstance "M_Duplex Receptacle : Standard" (symbol 342654 == master), on circuit 469428, in space 379575 | direct-symbol pattern (`symbolId == masterSymbolId`) — the phase-1 instance recipe |
| `rme_space_379575_RoomElem.json` | MEP Space (also class `RoomElem`, category OST_MEPSpaces) | spaces are RoomElems in the space category |
| `rme_connectorelem_766662.json` | ConnectorElem (120 V, 1 pole) — NOT a host-document element (not in ElemTable): it lives inside an embedded family document unit | connectors come from the loaded family; the writer never authors them when instantiating a loaded family |

## How to read the id references

Each `references[]` row is one ElementId found anywhere in the three
records, with the JSON path where it occurs, the class of the target and
whether the target is a host-document element (`in_ElemTable`) or only a
partition record (embedded-document element / sub-object). This is the
element's **dependency closure** = exactly the ids a cloned copy must remap
or keep pointing at existing template elements. Negative ids are built-in
enum values (categories `-2000xxx`, BuiltInParameters `-100xxxx`), not
elements. Small positive ids in geometry sub-trees (`m_faceHistTable[].m_id`,
`GInfo.m_tag`) are geometry topology tags, not ElementIds — see
`mutate._NOT_ELEMENT_ID`.

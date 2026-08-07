# inbox — oracle-harness (wave 2, 2026-08-02)

Out-of-slice findings from wiring the ground-truth oracle
(`tests/oracle/`, `docs/streams/11-oracle.md`). The orchestrator should
merge the KNOWLEDGE-worthy items and route the rest to the owning agents.

## For KNOWLEDGE.md (verified, cite docs/streams/11-oracle.md)

1. **Type-id numbering is now externally proven.** Our schema-a id
   (definition order + `0x0c`) equals the class word ON DISK in Revit 2023,
   2024 and 2026: the Partitions framing tags resolve to `SegmentMarker` /
   `SegmentCheckback` / `SignatureMarker` / `ContentMarker` / `ContentKey`
   and the record class words to `ElementHeader` / `SerializedDummy` /
   `GElement` in every release. **vendor/rvt-rs's tag table is our id + 1**
   (219/219 cells) — anyone importing their CSV must subtract 1.
2. **The Partitions framing spec is release-independent when keyed by
   class NAME.** Same 18-byte header, 26-byte block header, 6-byte
   trailer, 18-byte terminator, `SignatureMarker` footer, 28-byte unit
   separator — only the u16 tag values change per release. A future
   `rvt.partitions` should take a `FramingTags` object resolved from the
   file's own schema (`tests/oracle/rvt_release.framing_tags`) instead of the
   hard-coded 2026 constants (`BLOCK_TAG=0x0f28` etc.). I did NOT edit
   `src/rvt/partitions.py`; the parametric walker lives in
   `tests/oracle/rvt_release.py::walk_partition` and could be promoted.
3. **ElementId is 32-bit in Revit ≤2023, 64-bit ≥2024** (matches the public
   2024 API `ElementId(long)` change). Consequences: seq101 header
   12 B / seq102-103 header 16 B pre-2024; `Global/ElemTable` records
   28 B `{u32 orig, u32 id, u32 create_ep, u32 mod_ep, u32 user_ep, u32
   part, i32 owner}` pre-2024 vs 40 B ≥2024. Auto-detection code:
   `oracle_extract.detect_record_layout` / `parse_elemtable_any`.
4. **The Partitions header's last u32 is that partition's own element
   count**, NOT the `Global/ElemTable` count (they coincide in our six 2026
   samples only because each has one partition). Einhoven: /0=2,520, /5=66,
   /6=0 … ; ElemTable=2,615. Core Interior: /46=20,156 … ; ElemTable=26,425.
5. **First confirmed IFC ↔ rvt class correspondences** (per-element,
   1,055/1,055): IfcWall↔`SWall`, IfcDoor/Window/Column↔`FamilyInstance`,
   IfcSlab/ShadingDevice↔`Floor` (+`BuildingPad`), IfcOpeningElement↔
   `FamilyInstance`|`CurveElem`, IfcBuildingStorey↔`Level`, IfcSpace↔
   `RoomElem`, IfcSite↔`SiteSurface`, IfcWallType↔`BasicWallType`,
   IfcSlabType↔`FloorAttributes`, loadable-family types↔`FamilySymbol`
   (+`Family`, `FamilySurrogate`), materials↔`MaterialElem`. System-family
   "types" are the `*Attributes` / `*Type` classes; loadable-family types
   are `FamilySymbol`. Curtain panels are `FamilyInstance`, grid lines
   `CurtainGridLine`.
6. **Live-model census**: distinct seq102 record ids (49,173) ≫ ElemTable
   ids (26,425) in the 47-save-unit file — partitions retain superseded
   object versions/graveyard; the LIVE set is the ElemTable, and the
   current version of an element is its last-written record. The Global/
   Latest / ContentDocuments decoders should assume "last record per id
   wins".

## What the full object decoder must confirm next (measurable NOW with this harness)

Each item below has ground-truth values already extracted in the cached
IFC summary (`tests/oracle/cache/2024_Core_Interior_slim.ifc.*.json`), so
the decoder agent gets a numeric score the moment it emits a value. Suggested
`compare_oracle.py` extensions in parentheses.

1. **Level elevations** — decode the `Level` record body (ids 16234,
   16235, 87755 …) and match `IfcBuildingStorey.Elevation` in feet
   (Basement 2 = −40, Level 13 = 185.5). First numeric field to nail; gives
   the double/units convention of the object stream. (add a
   `values_agreement` section: storey elevation deltas)
2. **Wall placement + geometry** — for the 360 `SWall` records, decode the
   location curve endpoints and base/top constraints; compare against the
   IfcWall `ObjectPlacement` origin + `IfcWallStandardCase` axis and
   `Pset_WallCommon`/quantity `Length`, `Height`. (element-wise geometry
   agreement, tolerance 1e-3 ft)
3. **Instance transforms** — 256 columns / 132 doors / 6 windows
   (`FamilyInstance`): decode insertion point + rotation, compare to
   `IfcLocalPlacement`; decode the symbol pointer → check it names the
   `FamilySymbol` whose type string we already located.
4. **Type parameters** — wall thickness (8"/6"/18") from `BasicWallType`
   compound structure vs `IfcMaterialLayerSetUsage` layer thicknesses;
   door width/height (`3 x 8`) vs IfcDoor `OverallWidth/OverallHeight`.
5. **Element → level → type pointers** — every joined element carries a
   host level (compare `IfcRelContainedInSpatialStructure` storey) and a
   type (`IfcRelDefinesByType`); decoding the ElementId reference fields in
   the seq102 body should reproduce both graphs exactly. (add
   `graph_agreement`: element→level, element→type match rates)
6. **Materials** — 9 material names already located in `MaterialElem`
   records; confirm the material ids referenced by wall/floor layer sets.
7. **Rooms** — 116 `RoomElem` records ↔ IfcSpace: number, name, level,
   area (`Qto_SpaceBaseQuantities`), boundary.
8. **Openings** — the 63 `CurveElem` openings: recover the rectangle sketch
   and host wall; the 138 insert openings should each be the void of a
   door/window instance (`IfcRelVoidsElement`/`IfcRelFillsElement` pairs).
9. **Curtain walls** — decode Einhoven wall 2808 (`SWall`) + its 24 panel
   `FamilyInstance`s + `CurtainGridLine`s; FME `Wall_Window.csv` payloads
   carry the panel grid geometry (x/y/z, rotation) to score against.

## Bugs / gaps for other agents

* **schema-a (agent schema):** the grammar desyncs at the SAME class in all
  three releases — `VarExpr.m_refCt`, descriptor `04 00 04 00` (kind 4 =
  int32, flags 0, then a non-zero u16 where the grammar expects the `u16 0`
  pad). One new descriptor rule finishes the last ~5 % of the class map for
  every release; run `tests/oracle/schema_drift.py` to re-measure.
  Also note the parsed 95 % already contains 4,140–4,386 classes (KNOWLEDGE
  still says "1,150 classes … expect ~4,600" — that section can be updated:
  the de-paged schema parses to ~4,4 k with one known gap).
* **strings_scan.classify():** treats any string containing `"` as
  `schema`/json, which mis-files human names with inch marks
  (`8" Interior Partition 3 Hour`). Suggest requiring `{`/`":`/`<` before
  calling a string structured. (Worked around in
  `oracle_extract.py`.)
* **rvt.meta.parse_basic_file_info** works on 2023/2024 BasicFileInfo
  unchanged (structure_version 14 in all) — good news, no action.
* **rvt.elemtable.parse_elemtable** assumes 40-byte records; add the
  28-byte pre-2024 layout (or reuse `oracle_extract.parse_elemtable_any`).
* **corpus opportunity:** `vendor/magnetar-revit-test-datasets/Revit/
  Families/*.rfa` (2024) + `phi-ag/rvt`'s 11-release RFA corpus give
  Formats/Latest for 2016–2026; `schema_drift.py` accepts any list of paths
  and would extend the drift table to all 11 releases in one run.

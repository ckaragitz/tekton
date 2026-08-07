# tests/oracle — the ground-truth oracle harness

Turns decoder work into a **measured loop**: every claim we make about the
`.rvt` element layer is checked against Revit's own IFC export of the *same*
model (and, for the model without an IFC, against FME/StrangeMatter
component exports that carry Revit UniqueIds). Re-runs cost ~2 s (JSON
summaries cached under `cache/`).

Ground truth (all under `vendor/magnetar-revit-test-datasets/`, MIT):

| pair | .rvt | oracle | identity proof |
|---|---|---|---|
| A | `Revit/2024_Core_Interior.rvt` (Revit **2024**) | `IFC Exports/2024_Core_Interior_slim.ifc` (IFC4, 1,055 tagged elements) | IFC `VersionGUID` == rvt `Unique Document GUID` (`2a619b2e…`) |
| A' | same .rvt | `Revit/2024_Core_Interior.ifc` (2 elements, "by element" export) | 2/2 element ids resolve into the same rvt |
| B | `Revit/Revit_IFC5_Einhoven.rvt` (Revit **2023**) | `FME Demos/*.csv|*.json` (26 Revit UniqueIds = docGUID + hex ElementId) | all 3 episode GUIDs are in the rvt's `Global/History` |

## Run

```bash
PY=.venv/bin/python
$PY tests/oracle/oracle_extract.py <file.rvt>            # rvt summary (cached)
$PY tests/oracle/oracle_ifc.py <file.ifc>                # ifc summary (cached)
$PY tests/oracle/compare_oracle.py <file.rvt> <file.ifc> [--md rep.md] [--json rep.json]
$PY tests/oracle/compare_oracle.py <file.rvt> --fme "vendor/magnetar-revit-test-datasets/FME Demos"
$PY tests/oracle/schema_drift.py                        # cross-release schema/tag drift
$PY -m pytest tests/oracle -q                            # regression gate (10 asserts)
```

`--refresh` forces re-extraction. Cache keys include file size + mtime.

## What each tool reads

* **`rvt_release.py`** — release-independent access. Parses the file's *own*
  `Formats/Latest` with the wave-1 grammar (`rvt.schema_a`), builds a
  `ClassMap` (id<->name; our id = definition order + `0x0c` = the class word
  found ON DISK), resolves the Partitions **framing tags by class name**
  (`SegmentMarker`/`SegmentCheckback`/`SignatureMarker`/`ContentMarker`/
  `ContentKey`), and walks any release's partition streams. Also
  `scan_records()`.
* **`oracle_extract.py`** — `.rvt` -> summary: BasicFileInfo release/build/
  GUIDs; stream inventory + CRC health; schema stats; `Global/ElemTable` ids
  (40-byte 64-bit records ≥2024, 28-byte 32-bit records ≤2023); every
  `Partitions/<N>` walked (blocks, CRC, units); per-seq record census by
  **class name**, record-id sets, auto-detected id width (u32 ≤2023 / i64
  ≥2024); a *live* class census (only ids present in ElemTable, latest
  record); decoded strings from `Global/*` and from seq102 record bodies
  **attributed to the owning record class** (`Level`, `BasicWallType`,
  `FamilySymbol`, `RoomElem`, `MaterialElem`, ...).
* **`oracle_ifc.py`** — `.ifc` -> summary via ifcopenshell: header
  (`VersionGUID`, `NumberOfSaves`), product/type counts, storeys (name,
  elevation), per-element `Tag` (= Revit ElementId; also embedded in
  `Name` = `Family:Type:Id`), storey membership, type names, spaces,
  materials, site name.
* **`compare_oracle.py`** — the AGREEMENT REPORT. Three evidence lines:
  (1) **element-id join** IFC `Tag` -> rvt seq102 record -> its schema
  class, aggregated per IFC entity with a purity score; (2) side-by-side
  count matching (schema-agnostic proposal / cross-check); (3) name
  agreement (storeys, wall/door/column/window/slab types, families, spaces,
  materials, site) locating each IFC name inside the rvt strings with the
  record class it lives in. Emits a scored correspondence table
  `IFC entity <-> rvt class`. `--fme` mode does the same via Revit
  UniqueIds for the Einhoven model.
* **`schema_drift.py`** — per-release class counts, pairwise id drift, a
  name-keyed drift table for the format-relevant classes, and a validation
  of `vendor/rvt-rs/docs/data/tag-drift-2016-2026.csv` (their tag = our
  id + 1, exactly, in all 219 cells).
* **`test_oracle.py`** — pytest gate pinning the headline agreements.

## Headline results (2026-08, wave 2)

Pair A: **1,055/1,055 (100 %)** IFC element ids found as rvt object records
AND in ElemTable; per-entity purity IfcWall->`SWall` 100 %, IfcDoor/
IfcWindow/IfcColumn->`FamilyInstance` 100 %, IfcSlab->`Floor` 99 %,
IfcOpeningElement->{`FamilyInstance` 69 % (inserts), `CurveElem` 31 %
(sketch openings)}; storeys 15/15 in `Level` records, wall types 4/4 in
`BasicWallType`, family types 12/12 in `FamilySymbol`(+`Family`/
`FamilySurrogate`), spaces 116/116 in `RoomElem`, materials 9/9, site
name `Surface:21971` -> `SiteSurface` record 21971. Pair B (2023, no IFC):
26/26 UniqueIds resolve (`hok.wall`->`SWall`, curtain panels/window->
`FamilyInstance`), all 3 episode GUIDs in History.

See `docs/streams/11-oracle.md` for the full report and the schema-drift
findings.

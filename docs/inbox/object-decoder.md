# inbox — object-decoder (wave 3) notes for the orchestrator

Deliverable summary: `src/rvt/objects.py` decodes element objects
schema-directed; racbasic seq 101/102/103 all 100 % clean full-record
decodes (306 classes), rst/rac advanced 100 %, corpus-wide seq 102
99.69 %. Docs: `docs/streams/10-objects.md`; tests
`tests/test_objects.py` (10 pass); samples
`extracted/_objects/racbasic_sample.json`.

Out-of-scope findings — please merge / route:

1. **BUG in `src/rvt/partitions.py::partition_stream_paths()`** (a file I
   may not edit): it globs `Partitions__*.bin`, which also matches the
   extraction artefact `Partitions__N.logical.bin`. `load_stream()`
   expects the RAW page-framed stream and de-pages it itself, so the
   `.logical.bin` copy gets mis-walked (39 seq-102 blocks instead of 562)
   and its payload is appended to the concat segment: racbasic seq 102
   became 68,124,988 bytes instead of 63,944,890, with a garbled duplicate
   of the head (phantom second `KeynoteTable` id 86291, bogus "AString
   length" failures at file-specific offsets). `partitions.concat_elements()`
   and any wave-1 record counts built on it inherit the duplication.
   Fix: exclude names ending `.logical.bin` (or match
   `Partitions__[0-9]+.bin` exactly). `objects.load_segment()` already
   applies the workaround. KNOWLEDGE's "racbasic 85,978 records" is the
   correct raw-only count (85,814 elements + 164 save-unit sentinels).

2. **Record framing correction for KNOWLEDGE.md "Partitions" section:**
   the wave-1 `u32 class_word` = `u16 class_id` + the object's first u16;
   the last 4 bytes of every record are a `u32 psize` repeat. Uniform
   layout: `i64 id [+ u32 stamp in seq 102/103] + u32 psize + payload{u16
   class_id, object[psize-2]} + u32 psize`. Sentinels: id -1, psize 0.
   seq-103 `SerializedDummy` = psize 2 (bare class id, empty object).
   Records are one-per-element-per-seq with IDENTICAL id sets across
   seq 101/102/103 (racbasic 85,814 each): seq 101 = ElementHeader,
   102 = element object, 103 = GElement geometry rep or dummy. This
   supersedes "class 0x0f2c ~SerializedDummy 86-90 % of seq 103" (they are
   empty placeholders) and the {i64 id, u32 body_size, u32 cls_word}
   16-byte seq-101 header (it is 12 bytes + payload + trailer).

3. **AString null encoding:** decoder now treats `u32 0xFFFFFFFF` char
   count as a null string (per 08-strings-map §6.2). Never triggered in the
   walked corpus but harmless.

4. **The Extensible-Storage schema table lives in `Global/Latest`**
   (ADocument's `ESSchemaStorage` 0x56f): schema JSON in UTF-16
   (`"autodesk.unit.unit:feet-1.0.1"`, field names `ASHRAETableName`,
   `AnalysisId`, schema `AREXContentGenerator`) at rme
   `Global__Latest.gz/000.bin +0x327614` / rstbasic `+0xe931f`, keyed by
   the same 16-byte schema GUIDs that lead the `ESEntity.m_blob` payloads
   in Partitions. `ESEntity.m_blob` is the one field whose wire form is
   NOT its schema descriptor: `i32 pid=-1` + schema GUID(16) + entity
   data. Suggested next task: run `ObjectDecoder` over `Global/Latest`
   (`ADocument` 0x1c) — the wave-1 heuristic parser in `global_latest.py`
   can be replaced/validated by the schema-directed decoder.

5. **Class naming corrections for KNOWLEDGE:** circuits in these files are
   `RbsElectricalSystem` (0x0d87), not `ElectricalCircuit` (0x0596, which
   never occurs as a record); the seq-102 "top classes" ordinals are
   confirmed by name (0x8cc GStyleElem 13,157, 0x2e1 CategoryElem 11,653,
   0x3ba CurveElem, 0xa0c LinearDimString, 0x84c FontElem, 0x486
   DBViewType, 0x1158 = ? not present — the wave-1 "1158" count row was
   likely 0x0486=1158dec DBViewType).

6. `elemtable.py`'s ids (8,401) are a strict subset of the 85,814
   partition record ids and `ElemRec.owner_id`s decode to real element ids;
   the ElemTable indexes elements-with-history, not all elements.

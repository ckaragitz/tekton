# estorage — Extensible-Storage decoder (record for the orchestrator)

Stream: THE EXTENSIBLE STORAGE (ES) DECODER — the last decode gap.
Territory written: `src/rvt/estorage.py`, `tests/test_estorage.py`,
`docs/writer/extensible-storage.md` (the spec — read that for the
grammar; this file is the evidence log + the integration DIFF).
Nothing in `src/rvt/objects.py` or any other existing module was edited.

## What 0x2314 turned out to be

**Not a class.** `ESEntity.m_blob`'s pointer token is `i32 pid` followed by
the entity's **16-byte in-model schema GUID** in place of the `u16` archive
class id. `0x2314` is the low u16 of GUID `762a2314-1d1c-4087-a58f-
bab902f57be5` (rme's `CoefficientFromTable` duct-fitting schema); rstbasic's
`0x7959` = `4c817959-…`; dach's `0xb137/0xe691/0x1548/0x2a2b` likewise. So
neither of the two hypotheses in the charter was quite it: it is an
out-of-archive-schema entity, and its "class" word is not a class id at all.
The archive class `ESBlob` (0x569, zero fields) is the C++ static type of
the blob and never appears on the wire. Verified on all six files.

## Findings (all [V] — byte-verified; details + hexdumps in the spec)

1. **Schema catalog** = `ESSchemaStorage.m_schemaUsageMap :
   container< pair< GUIDvalue, SchemaUsageInfo > >` inside `Global/Latest`
   (the `ADocument`'s AppInfo). `SchemaUsageInfo{ m_contentDocsKeys,
   m_schema : ESSchema, m_usedInHost }`, `ESSchema{ documentation, fields :
   container<ESField>, schemaName, vendorId, applicationGUID, guid,
   read/writeAccessLevel }`, `ESField{ documentation, fieldName,
   fieldTypeName, specTypeId (units), containerType 0/1/2, entryIndex,
   subSchemaGUID }` — **all ordinary archive classes**: the existing
   generic decoder decodes every entry unchanged; only LOCATION was needed
   (self-validating: entry map key GUID == decoded `ESSchema.m_guid`;
   entries contiguous; u32 before entry 0 == entry count). rme 2 schemas
   @0x327610, rstbasic 2 @0xe9264, dach 175 @0x391d2b (count verified), the
   three rac/rst-adv files register none (empty map, proven, not unfound).
   The prior object-decoder note (`docs/inbox/object-decoder.md` B1) had the
   token right but pointed at `m_storedForgeSchemas` (that is the Forge
   parameter/unit JSON map) — corrected here.
2. **Entity body** is deferred breadth-first into the record's owned-pointer
   queue (never inline after the token) and is the schema's field values
   concatenated in ascending `m_entryIndex`, **no header/count/GUID**. Types
   = the archive primitive codebook (int i32, double f64, bool u8, char
   i8/raw-bytes-in-arrays, TCHAR/AString/AStringWrapper = u32+UTF-16LE,
   GUIDvalue 16 raw, ElementId i64, XYZ 3×f64, UV 2×f64); containers:
   array = u32 count + elements, map (type `std::pair<K,V>`) = u32 count +
   count×(K,V); a nested `ESEntity` value is again `pid` (0 = null, 4 bytes)
   [+ subschema GUID] with its body deferred to the same queue.
3. **`EStorageTracking`** (sibling AppInfo, `m_trackingItems`) is Autodesk's
   own schema-GUID → host-element-ids registry (rme: 657 + 514 ids == the
   1,171 failing FamilyInstances exactly) → source of `es_report`.

## Results

* `verify_document` (whole ES-bearing records decoded by `ESDecoder`,
  re-encoded by `ESEncoder`, record bytes compared):
  **rme 1,171/1,171, rstbasic 7/7, dach 1,743/1,743 (6,085 entities incl.
  nested) — 0 undecodable ES elements, 100 % byte-exact re-encode.**
* Pure blob codec (`decode_entity_blob` / `encode_entity_blob`) on every
  contiguous entity closure: rme 1,171/1,171, rstbasic 7/7, dach
  3,480/3,480 (incl. 31 nested-descendant tails) byte-exact.
* Manipulate integration proven: with the ES decoder/encoder in place the
  rme fittings pass `EditSession._orig_bytes_check` and an ES field is
  editable by JSON path (`test_manipulate_precondition_passes_and_es_field_is_editable`).
* Native-diff proof: the DIFF below applied to a scratch copy of the package
  gives rstbasic **32,011/32,011** seq-102 records clean + byte-exact
  (was 32,004 + 7 ES failures) with `manipulate.EditSession` untouched, and
  without a catalog the failure is loud/true ("schema … not in the in-model
  catalog") instead of the bogus "unknown class 0x2314".
* Suite: `.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle` →
  **419 passed** (14 new; the dach corpus test is `slow`).

## Files written

| file | what |
|---|---|
| `src/rvt/estorage.py` | catalog locator + decoder (`schemas`, `locate_schema_map`, `locate_tracking`), field-type system (`parse_type`), `EntityCodec`, `decode_entity_blob` / `encode_entity_blob`, `ESDecoder` / `ESEncoder` (drop-in `ObjectDecoder`/`ObjectEncoder` + ES), `es_report`, `verify_document`, `collect_entity_closures`, CLI (`python -m rvt.estorage <project\|path> [--report [--walk]] [--roundtrip]`) |
| `tests/test_estorage.py` | 14 tests: type vocabulary, GUID codec, catalogs (rstbasic/rme + GUID-free locator agreement + empty-catalog file), blob round-trips (rstbasic/rme), the closed decode gap on rme 392203, record round-trips + tracking cross-check, `es_report`, manipulate precondition + ES-field edit, dach corpus zero-undecodable (`slow`) |
| `docs/writer/extensible-storage.md` | the spec: token, catalog layout with worked hexdumps, locators, blob grammar + type table + nested-entity proofs, corpus table, integration, confidence/unknowns |
| `docs/inbox/estorage.md` | this record |

## The `objects.py` / `encode.py` / `mutate.py` integration DIFF

`ESDecoder` / `ESEncoder` in `estorage.py` are exact behavioural previews;
this diff makes the base classes do it natively (validated on a scratch
copy: rstbasic 32,011/32,011, rme ES records 1,171/1,171 byte-exact, and
`manipulate.EditSession.value()` passing for RebarShape / FamilyInstance).

```diff
--- src/rvt/objects.py
+++ src/rvt/objects.py
@@ class ObjectDecoder:
-    def __init__(self, schema: Optional[Schema] = None):
+    def __init__(self, schema: Optional[Schema] = None, es_catalog=None):
         self.schema = schema or load_schema()
+        # Extensible-Storage schema catalog (rvt.estorage.ESSchemaCatalog);
+        # None = the model registers no ES schemas.  ESEntity blobs are
+        # decoded against it (see rvt.estorage).
+        self.es_catalog = es_catalog
+        self._es_codec_obj = None
         self._chain_cache: dict[int, list[ClassDef]] = {}
@@ (end of __init__)
         self.id_AStringWrapper = s.by_name["AStringWrapper"].type_id if "AStringWrapper" in s.by_name else None
+        self.id_ESEntity = s.by_name["ESEntity"].type_id if "ESEntity" in s.by_name else None
@@ decode_record: the breadth-first deferred loop
             while queue:
                 pend = queue.popleft()
                 obj.n_deferred += 1
+                if getattr(pend, "guid", None) is not None:      # queued ES entity body
+                    state.path = pend.path
+                    if self.es_catalog is None or self.es_catalog.get(pend.guid) is None:
+                        raise DecodeError(rd.p, f"ES entity blob: schema {pend.guid} "
+                                          f"not in the in-model catalog")
+                    pend.holder[pend.key] = self._es_codec().read_entity_body(
+                        rd, pend.guid, queue, pend.path)
+                    continue
                 cname = self.class_name(pend.class_id)
                 sub = self._decode_class(rd, pend.class_id, queue, state,
                                          f"{pend.path}->{cname}")
@@ class body
+    def _es_codec(self):
+        """rvt.estorage.EntityCodec over this decoder's ES catalog."""
+        if self._es_codec_obj is None:
+            from .estorage import EntityCodec, ESSchemaCatalog
+            self._es_codec_obj = EntityCodec(
+                self.es_catalog if self.es_catalog is not None else ESSchemaCatalog())
+        return self._es_codec_obj
+
     def _decode_class(self, rd: Reader, class_id: int, queue: deque, state: "_State",
                       path: str) -> dict:
+        if class_id is not None and class_id == self.id_ESEntity:
+            # ESEntity.m_blob token = i32 pid (0 null) + 16-byte SCHEMA GUID
+            # (a runtime class keyed by GUID, no u16 archive class); the entity
+            # body is deferred into the same breadth-first queue.
+            state.path = path + ".m_blob"
+            return {"m_blob": self._es_codec().read_entity_token(rd, queue, path + ".m_blob")}
         state.depth += 1
```

```diff
--- src/rvt/encode.py
+++ src/rvt/encode.py
@@ ObjectEncoder.__init__
         self.id_GUIDvalue = d.id_GUIDvalue
+        self.id_ESEntity = getattr(d, "id_ESEntity", None)
@@ encode_object: the breadth-first deferred loop
         while queue:
             pend = queue.popleft()
+            if isinstance(pend, tuple):                # (guid, entity) ES pending
+                g, ent = pend
+                self.dec._es_codec().write_entity_body(w, ent, queue,
+                                                     ent.get("schema") or g)
+                continue
             self._encode_class(w, pend.class_id, pend.value or {}, queue,
                                f"{pend.path}->{self.dec.class_name(pend.class_id)}")
@@ _encode_class
     def _encode_class(self, w: Writer, class_id: int, value: dict,
                       queue: deque, path: str):
+        if class_id is not None and class_id == self.id_ESEntity:
+            # ESEntity: emit the m_blob token; the entity body is queued
+            self.dec._es_codec().write_entity_token(
+                w, (value or {}).get("m_blob"), queue, path + ".m_blob")
+            return
         if not isinstance(value, dict):
```

`rvt.estorage.EntityCodec.read_entity_token` returns the `m_blob` holder
(`{"schema_guid","schema","pid","fields":None}` or `None` for pid 0) and
appends an `_ESPend` (carrying `.guid`) to the SAME queue; `read_entity_body`
decodes the fields (appending nested `_ESPend`s); the encoder appends
`(guid, entity)` tuples. `mutate.py`: after the decoder is built in
`Document.from_file` / `Document.load`, attach the catalog —
`doc.dec.es_catalog = rvt.estorage.schemas(doc, decoder=doc.dec)` (a helper
`Document.attach_es_catalog()`); `manipulate.py` needs no change (its
`ObjectEncoder(decoder=doc.dec)` mirrors the decoder). No `commit.py` /
`streams_edit.py` change (record bytes only).

## New work proposed (for TRACKER.md — orchestrator)

* Apply the DIFF (above) natively and drop the `ESDecoder`/`ESEncoder`
  subclasses; re-run manipulate's robustness pass — expected: rme/dach
  re-encode 100 %, the ES refusal note in `docs/writer/manipulation.md` §6/§9
  becomes obsolete.
* `KNOWLEDGE.md` "Object decoding" section: the corpus seq-102 clean rate is
  now 100.000 % and the ES model above should be summarised there
  (learned note filed: `docs/inbox/learned-estorage.md`).
* Optional (authoring, out of this stream's scope): writing a NEW entity /
  schema requires appending to `m_schemaUsageMap` + `EStorageTracking`
  (ADocument re-serialization) — only needed if generated files must carry
  add-in data; editing existing ES values works today.

BRANCH STATE: `src/rvt/estorage.py` + `tests/test_estorage.py` (14 passing, 1 slow) + `docs/writer/extensible-storage.md` + this record are complete and self-contained; no existing module was modified; the full suite passes (419) with the ES elements now decodable, byte-exact re-encodable and (with the DIFF applied) modifiable — the last decode gap is closed.

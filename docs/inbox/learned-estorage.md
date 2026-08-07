# learned — estorage stream (Extensible Storage), 2026-08-03

For the orchestrator to merge into KNOWLEDGE.md.

* **ES entity token = `i32 pid` + 16-byte SCHEMA GUID (no `u16` archive
  class).** The corpus-wide "pointer token pid=-1 to unknown class 0x2314"
  was never a class: `0x2314` is the low bytes of the schema GUID. ES entity
  classes are runtime types keyed by GUID; `ESBlob` (0x569, 0 fields) is a
  C++ static type that never appears on the wire. pid 0 = null entity (4
  bytes, no GUID).
* **The ES schema catalog lives in `Global/Latest`** as
  `ESSchemaStorage.m_schemaUsageMap : container< pair<GUIDvalue,
  SchemaUsageInfo> >` — ordinary archive classes (SchemaUsageInfo / ESSchema
  / ESField), decodable by the generic decoder as-is once LOCATED (each
  entry self-validates: map key GUID == its decoded `ESSchema.m_guid`;
  entries contiguous; preceding u32 = count). NOT `m_storedForgeSchemas`
  (that map is Forge unit/parameter JSON). Sibling AppInfo
  `EStorageTracking.m_trackingItems` = top-level schema GUID → host
  element ids (Autodesk's own registry).
* **Entity blob = field values in `ESField.m_entryIndex` order, no header**,
  deferred breadth-first into the record's owned-pointer queue like any
  pointed body (never inline after the token). Types = the archive primitive
  codebook (int i32, double f64, bool u8, TCHAR/AString/AStringWrapper =
  u32+UTF-16LE, GUIDvalue 16 raw, ElementId i64, XYZ/UV doubles); array =
  u32 count + elements (char[] = raw bytes); map (`std::pair<K,V>`) = u32
  count + K,V pairs; nested `ESEntity` = again a pid+subschema-GUID token
  whose body joins the same queue. The catalog's `m_fields` list is
  name-ordered — serialization order is entryIndex.
* **Corpus with `rvt.estorage`: 0 undecodable ES elements**, whole records
  byte-exact (rme 1,171, rstbasic 7, dach 1,743 / 6,085 entities). The
  three rac/rst-advanced files register NO schemas (empty map). Corpus-wide
  seq-102 clean rate → 100.000 % once the `objects.py`/`encode.py` diff in
  `docs/inbox/estorage.md` is applied; ES elements then pass manipulate's
  byte-exact edit precondition (they were the only refused class).
* Gotcha: analytical/derived caches duplicate ES values elsewhere in the
  same record (`MEPAnalyticalFittingData.m_ESFieldName/m_ESFieldValue`
  mirror the fitting's ES field) — editing the entity does not (and should
  not) rewrite those caches; regeneration is Revit's job.

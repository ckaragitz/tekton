# inbox — findings from agent `metadata` that fall outside its slice

Source: `src/rvt/meta.py`, `docs/streams/02-metadata.md`.

1. **Document creation GUID lives in element data.** The 16-byte binary GUID
   at Contents payload +0x46 (`e3e052f8-0156-11d5-9301-0000863f27ad` for
   racbasic/racadv/rme/rstbasic, a v1 GUID from ~2001; `20c8cdf4-…` dach;
   `771ca0ef-…` rstadv) occurs verbatim 80+ times inside
   `Partitions/15.gz/*.bin` (blocks 101, 096, 094, …) and once in
   `Global/PartitionTable`. Likely the "GLOBAL" partition GUID / UniqueId base.
   Useful anchor for the partition and elemtable agents.
2. **Class-stream serialization envelope** shared by `Contents` and
   `RevitPreview4.0`: `62 19 22 05` prologue (u32 magic, u32 28, u32 1,
   u32 0), then per record `magic + u32 class_ref`. `class_ref & 0x8000` ⇒ an
   inline class definition follows in the *exact* `Formats/Latest` class
   record shape (u16 name len + ASCII name + u16 0 + u32 version + u32
   field count + field records with type codes `04`=int32, `07`=double,
   `0E`=object ref (+u32 0 + i32 target), `02 50`=byte array). Preview
   defines `FilePreview` (idx 12, v7) and `ARasterImage` (idx 13, v3, 7
   fields — matches its Formats/Latest entry). Contents references
   already-known indexes 178–430 (per-file), so there is a per-document
   dynamic class table somewhere (Global/Latest?) worth mapping.
3. **Not all gzip trailers are corrupt** (refines the KNOWLEDGE gotcha):
   valid CRC32/ISIZE in `Contents`, `Global/DocumentIncrementTable`,
   `Global/ElemTable`, `Global/History`, `Global/PartitionTable`; invalid in
   `Formats/Latest`, `Global/Latest`, `Global/ContentDocuments` (racbasic
   check). The trailing region after the 8-byte trailer = 2–17 zero bytes +
   a size-correlated high-entropy blob (42 B Contents, 58–75 B DIT, 91 B
   History…) that never inflates → hypothesis: stale slack from in-place
   stream rewrites, not a footer record. Raw-inflate-after-10-bytes remains
   the correct decode.
4. **Payload type tags**: DIT = 0x053C, Contents record = 0x053E — a small
   integer tag space distinct from the schema class ids; 0x053D unaccounted.
5. `TransmissionData` ElementIds (keynote table 86291, assembly code table
   1002459, Revit Links) should resolve in `Global/ElemTable`.
6. Save-history usernames/timestamps (Unix seconds) in the DIT give a
   provenance trail; the last record's timestamp equals the PartAtom
   `<updated>` value, so both are the true save time.

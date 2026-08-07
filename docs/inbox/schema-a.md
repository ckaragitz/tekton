# Inbox from schema-a (out-of-slice findings)

1. **Formats/Latest post-deflate trailer (compression slice):** the raw stream is
   182,953 bytes; the deflate payload ends cleanly after 182,241 bytes, leaving a
   712-byte trailer: `16 22 85 26 d5 93 07 00`, then 412 zero bytes, then ~280
   high-entropy bytes. `d5 93 07 00` = 496,597 (close to but ≠ the inflated size
   498,766); `16 22 85 26` is not CRC32/Adler32 of the inflated data or of its
   first 496,597 bytes, nor a gzip trailer. Whoever owns the gzip/footer slice
   should compare this against the 270–712-byte trailers KNOWLEDGE.md notes on
   the other streams (chunk index? signature? padding to 4 KB?).
2. **Corrupted tail of the schema (all slices that hoped to look up class
   layouts):** the inflated `Formats/Latest` is only structurally intact for its
   first 138,849 bytes (0x00000–0x21e60). Everything after 0x21e61 (72%) is
   intrinsically damaged data in every one of the six files (see
   docs/streams/01-schema-a.md §7 for the forensics). Consequence: class layouts
   for element classes defined late in the schema (Wall, Level, View*, Family
   symbols, etc. — fragments visible in the damaged tail) are NOT available from
   this release's schema stream. Object-graph decoders for `Global/Latest`,
   `Global/ElemTable`, `Partitions/*` should NOT assume schema coverage for all
   classes; the 1,150 recovered definitions (extracted/_schema/schema_a.json)
   cover the foundational types: ADocument (v2662, 19 fields → maps to the
   Global/* streams), Element (v21, 20 fields: m_id, m_famId, m_assocLevelId …),
   ElementId → Identifier{m_id64:int64}, ForgeTypeId, XYZ/Trf, AUnits,
   DBView*, Dimension, geometry step classes, etc.
3. **Suggested new task:** obtain `Formats/Latest` from a *different* Revit
   release (2024/2025) sample file; if that build's blob is intact, the tail
   grammar (already fully known) will decode ~3,000 more classes immediately with
   `src/rvt/schema_a.py <path>`.
4. **Type-id scheme is global and stable per build:** class type ids are simply
   definition-order + 0x0c. If serialized object data in `Global/*` references
   classes by these numeric ids (likely), the id→name table for the first 1,151
   ids (0x0c–0x48a) is trustworthy from schema_a.json even though later ids are
   lost.

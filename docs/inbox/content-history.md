# Inbox — content-history agent (out-of-slice findings)

Do not act here; orchestrator to route. Evidence + code in
`docs/streams/06-content-history.md` and `src/rvt/content.py`.

## 1. gzip trailer is REAL (History/small streams) or STALE (appended streams) — not "corrupt"
Every `Global/*` deflate ends with `00 00 ff ff 02 0c 00` (sync-flush stored
block + two empty fixed blocks, last FINAL), then `crc32:u32, isize:u32`,
zero padding, then a 37–350 B opaque footer. CRC/ISIZE **validate** for
History, DocumentIncrementTable, PartitionTable in all six files; they are
**stale** (ISIZE < actual, CRC of neither full nor prefix) for
ContentDocuments, ElemTable and Latest in all six. Update KNOWLEDGE
("corrupt trailer" → per-stream: valid vs stale) and TRACKER A10 (footer =
the blob after crc/isize/padding; per-stream sizes recorded in my doc).

## 2. ElemTable does NOT inflate end-to-end in dach and rme (A4 agent!)
Same defect as CD in racadv/dach: a clean run of ~16k-symbol dynamic blocks,
then an invalid block header; not deflate64, not truncation, not bad
extraction. dach ElemTable primary decodes to 1,749,844 B (compressed to
260,879) then dies; rme ElemTable to 464,083 B (to 65,014); no byte-aligned
resync exists in the remainder (unlike CD). `rvt.content.inflate_global()`
implements resync recovery generically — reusable for ElemTable
(`from rvt.content import inflate_global`; `.payload`, `.segments`, `.gap`).
scan_gzip.py's `.gz/000.bin` is MISSING for these 4 streams; add a
recovery pass to the corpus tooling.

## 3. Class-id facts for the schema agent (A2)
Data-serialized u16 class tags observed: `0x0538` = history object
(`Global/History` byte 0, and `38 05 ff ff ff ff` null-ptr in every
embedded-document prologue = `m_pHistory`); `0x03a3`, `0x03a2` (entry marker
null ptrs); prologue tags `0x001c, 0x05c9, 0x03a7, 0x01a0, 0x1066, 0x0ff8,
0x0ae9` (0x0ae9 precedes an ElementId — likely the ElementId class);
`0x0644` container tag (element tables here and Latest's per-doc summary
records). u32 ids 808/833/837 (racbasic), 975/1003 (rstbasic), 770/783
(rme), 541/562 (rstadv) appear as element-record class fields; `0x341`
recurs as `41 03 00 00` count keys in Latest. A class-id → name table would
name all of these instantly.

## 4. For the Latest/ADocument agent (A5)
- ContentDocuments entries begin with the SAME field-tag sequence as
  `Global/Latest` (compare Latest+0x00..0x4a with any CD entry+0x20): the CD
  entries are ADocument-shaped embedded documents. Latest's slot after
  `e9 0a` is `-1`; CD's holds the host owner-family ElementId
  (`m_ownerFamilyId` per the schema field order). Latest format version 2662
  vs 2660 inside content docs.
- Latest holds a per-content-document table: all 60 racbasic CD GUID keys
  appear once each in ~92–100 B records at Latest 975, 1067, 1159, … =
  `(u32 classId, u32 count)*` + GUID + UTF-16 app string ("Autodesk Revit").
- Global/History's format-version list ends 2662 = the u32 at Latest+0x48
  (`66 0a`) — the document's current internal format version (Revit 2026).

## 5. For the ElemTable/Partitions agents (A4/A6)
Resolve host ElementId 1,018,036 (0xf88b4) — the owner-family element of
racbasic content document #0 (385 occurrences in Partitions/15 member 233).
Its class name settles whether ContentDocuments = embedded family documents.
Element ids of content documents cluster contiguously (0xf8893…, 0x10b0xx…).

# `Global/ElemTable` — the per-document element table (`ADocument.m_elemTable`)

Agent: `elemtable`. Code: `src/rvt/elemtable.py` (`.venv/bin/python
src/rvt/elemtable.py` decodes and cross-checks all six samples). Verified on
Revit 2026 build 20250227_1515 across all six corpus files unless stated.

## TL;DR

* The stream is the externalized `ADocument.m_elemTable` member: one
  serialized **`ElemTable`** object (schema class index **0x05c9**) =
  a `u32 count` followed by `count` **fixed 40-byte `ElemRec`** records sorted
  by ElementId, then an empty `GraveyardRec` array, then a 20-byte footer.
* It is **not** an id→(partition, byte-offset) location index. Each `ElemRec`
  carries the element's `ElementId`, its original id (worksharing
  renumbering), three **EpisodeId** version numbers (created / last modified /
  last user-modified) that index the `Global/History` episode list, the
  owning element's id, and a `PartitionId` (always 0 in the corpus).
* The record count equals the element count stored in the `Partitions/<N>`
  stream header (bytes 14–17) in every file, and `max(lastModified)+1`
  equals the `Global/History` episode count in every file — both are hard
  cross-checks.
* The raw stream is **page-framed** (65,249 = 64,896 payload + 353-byte
  block, see §1). After de-framing, all six ElemTables gunzip with a
  **valid CRC32/ISIZE** and land exactly on `6 + 40·count + 24` bytes.

## 1. Container / compression layout

`Global/ElemTable` raw stream (as read from the CFB via olefile):

| offset (raw) | size | value | meaning | evidence |
|---:|---:|---|---|---|
| 0 | 8 | `00 00 00 00 00 00 00 00` | 8-byte `Global/*` prefix; constant zero for ElemTable in all six files (other Global streams use 05/01 here — meaning TBD) | `raw[:8]` all files |
| 8 | 10 | `1f 8b 08 00 00 00 00 00 00 0b` | standard gzip header (no name, no extra) | all files |
| 18 | var | deflate data | **but** the underlying stream is page-framed: at raw offsets `64,896 + n·65,249` sit 353 bytes that are NOT payload and must be removed before inflating | see below |
| after deflate | 8 | `[u32 CRC32][u32 ISIZE]` | ordinary gzip trailer — **valid** once de-framed | CRC/ISIZE match table below |
| after trailer | 94–581 | zeros then junk | allocation slack to end of stream (racbasic: 336 zero bytes + 245 junk bytes) | racbasic tail dump |

**Page framing (the gotcha).** Page stride 65,249 = 64,896 (0xFD80)
payload + 353 non-payload bytes, counted from raw stream offset 0. Gap
offsets per ElemTable: racbasic none (fits one page); racadv 64,896;
rstadv/rstbasic 64,896; rme 64,896, 130,145; dach 64,896, 130,145, 195,394,
260,643. Reading the framed bytes raw makes zlib either fail (dach:
`invalid block type` at raw ~260,880; rme: `invalid code lengths set` at
~64,786) or silently desync ~64,897 bytes in (racadv/rst*: LZ garbage,
2.5–3.1 KB of excess output, CRC mismatch). Uniquely, removing exactly 353
bytes at 64,896 (found by exhaustive splice search on racadv) restores a
byte-exact ISIZE and CRC; the same rule then validates every file and every
other stream (independently found by agent `cross-file`, see
`docs/inbox/cross-file.md`). What the 353-byte block encodes is unknown
(first byte 0x00, high entropy — likely per-page ECC/integrity data).

De-framed inflate results (all gzip trailers valid):

| file | raw stream | pages | inflated payload | trailer CRC32 | count | 6+40·count+24 |
|---|---:|---:|---:|---|---:|---:|
| racbasic | 50,408 | 1 | 336,070 | `0xeb4f97d1` ✔ | 8,401 | 336,070 ✔ |
| racadv | 92,628 | 2 | 689,270 | `0xccf9b819` ✔ | 17,231 | 689,270 ✔ |
| rme | 151,224 | 3 | 1,125,310 | `0x2a34ad03` ✔ | 28,132 | 1,125,310 ✔ |
| rstadv | 75,341 | 2 | 554,230 | `0x9a8da16a` ✔ | 13,855 | 554,230 ✔ |
| rstbasic | 72,440 | 2 | 557,470 | `0xcda546f8` ✔ | 13,936 | 557,470 ✔ |
| dach | 296,563 | 5 | 1,991,070 | `0xc9e2744a` ✔ | 49,776 | 1,991,070 ✔ |

Decode recipe (`inflate_global_stream`):

```python
lin = deframe(raw)                    # drop 353 B at 64,896 + n*65,249
assert lin[8:11] == b'\x1f\x8b\x08'   # 8-byte prefix, then gzip
d = zlib.decompressobj(-15)           # raw inflate after the 10-byte header
payload = d.decompress(lin[18:])
end = len(lin) - len(d.unused_data)
crc, isize = struct.unpack('<II', lin[end:end+8])   # both validate
```

## 2. Payload layout (inflated bytes)

Confidence: **verified** (six files, sizes byte-exact, cross-checks match).

| offset | size | type | field | meaning | evidence |
|---:|---:|---|---|---|---|
| 0 | 2 | u16 | class tag | `0x05c9` = schema class index of `ElemTable` (the root object serialized in this stream) | constant `c9 05` in all six; class-index derivation §5 |
| 2 | 4 | u32 | `m_elemArr.count` | number of `ElemRec` records N | racbasic `d1 20 00 00` = 8,401; matches Partitions header & size formula |
| 6 | 40·N | ElemRec[N] | `m_elemArr` | fixed-size records **sorted ascending by `m_id`** | §3; strict sort verified in all six |
| 6+40N | 4 | u32 | `m_graveyardRecs.count` | number of `GraveyardRec` records; **0 in all samples** (so their wire size is unknown) | `00 00 00 00` in all six |
| 10+40N | 4 | u32 | marker | `0xFFFFFFFF` | all six |
| 14+40N | 2 | u16 | class tag | `0x096a` — schema class index of a small trailing object [hypothesis] | constant `6a 09` all six |
| 16+40N | 2 | u16 | pad | 0 | |
| 18+40N | 8 | u64 | last-id watermark | highest ElementId issued [hypothesis]: equals the last record's id in 5 files; in racbasic it is `0x10c4c3` while max id is `0x10c463` (96 higher — ids issued then deleted) | tails below |
| 26+40N | 4 | u32 | zero | 0 | |

Footer bytes per file (24 bytes = `00000000 ffffffff 6a09 0000 <u64> 00000000`):
racbasic `… 6a 09 00 00 c3 c4 10 00 …` (0x10c4c3), racadv `27 b1 06`
(0x6b127), rme `cd 8c 0d`, rstadv `85 23 04`, rstbasic `0c 78 16`, dach
`2e 86 41`.

## 3. `ElemRec` — the 40-byte record

Byte layout matches the schema field order exactly
(`ElemRec = { m_history, m_id, m_OwningElementId, m_partitionId }` with
`ElementHistory` inlined first). Confidence: layout **verified**; field
names **verified** against the de-framed schema; per-field semantics of the
three EpisodeIds **inferred** (invariants below).

| off | size | type | schema field | meaning | evidence |
|---:|---:|---|---|---|---|
| +0 | 8 | u64 | `m_history.m_originalElementId` | id the element was created with; ≠ `m_id` only after worksharing renumbering (dach: 1,476 records) | dach recs 13611+ e.g. id 0x18ba4a, orig 0x18a5ca; equal everywhere else |
| +8 | 4 | u32 | `m_history.m_creationDate` | **EpisodeId** (index into `Global/History` episode list) when the element was created; 0 = created in the first episode | grows monotonically with id: 0 → 846 across racbasic |
| +12 | 4 | u32 | `m_history.m_lastModificationDate` | EpisodeId of last modification; `max+1 == History episode count` in all six | racbasic max 847 vs History count 848, dach 2739/2740, … |
| +16 | 4 | u32 | `m_history.m_lastUserModificationDate` | EpisodeId of last *user* modification; `0xFFFFFFFF` = never (racbasic 620 records) | always creation ≤ user ≤ last (verified all six) |
| +20 | 8 | u64 | `m_id` | the ElementId (64-bit); **strictly increasing sort key** | ids 1…N mostly consecutive at start (built-ins), then sparse |
| +28 | 8 | u64 | `m_OwningElementId` | owning element's id, `0xFFFFFFFFFFFFFFFF` = none (31–65 % of records have an owner) | racbasic id 231→owner 230, 232→233, 236→235 (nested chain) |
| +36 | 4 | u32 | `m_partitionId.m_id` | partition number; **0 for every record in all six files** | column all-zero |

Invariants observed across all 128,331 records in six files (all True):
records strictly sorted by `m_id`; `originalElementId ≤ m_id`;
`creation ≤ lastUserModification ≤ lastModification` (when user field ≠
0xFFFFFFFF); the u64 owner is either -1 or an existing smaller-ish id.

Interpretation of the EpisodeIds [inferred, strong]: `Global/History`
starts `38 05 | 01 00 …` and its u32 at inflated offset 14 is the episode
count (racbasic 0x350 = 848), followed by 16-byte episode GUIDs. Every
file: `episode count == max(m_lastModificationDate) + 1`. So the three u32s
are version stamps ("dates" measured in save episodes, not wall-clock), and
elements last modified in the same save share the same value (racbasic:
2,100+ records with `m_lastModificationDate == 551`; only 154 distinct
values among 8,401 records).

`ElementHistory` also declares a fifth field `m_EpisodeCounts`
(`std::pair<EpisodeId,int>` array) after a `00 00 00 00` in the schema; it is
**not present** in the wire form (record is exactly 8+4+4+4 = 20 bytes) —
the class header's `04 00 00 00` = 4 serialized fields.

## 4. Worked example — racbasic (`racbasicsampleproject`)

Raw stream (50,408 B, one page, so no de-framing needed):

```
00000000: 00 00 00 00 00 00 00 00 | 1f 8b 08 00 00 00 00 00 00 0b   prefix | gzip hdr
deflate 18..49,819 → 336,070 bytes; trailer @49,819: d1 97 4f eb  c6 20 05 00
          CRC32=0xeb4f97d1 (matches), ISIZE=0x000520c6=336,070 (matches)
then 336 zero bytes + 245 junk bytes to the end of the stream (slack).
```

Inflated payload:

```
0000: c9 05 | d1 20 00 00                        class 0x05c9 ElemTable, count 8,401
0006: 01 00 00 00 00 00 00 00 | 00 00 00 00 | ff 02 00 00 | ff 02 00 00 |
      01 00 00 00 00 00 00 00 | ff ff ff ff ff ff ff ff | 00 00 00 00
      → orig=1, create_ep=0, mod_ep=767, usermod_ep=767, id=1, owner=-1, part=0
002e: 02 00 00 00 00 00 00 00 | 00 00 00 00 | 27 02 00 00 | 27 02 00 00 |
      02 00 00 00 00 00 00 00 | ff ff ff ff ff ff ff ff | 00 00 00 00
      → id=2, created ep 0, last modified ep 551
…
record 8,400 (last): id=0x10c463 create/mod/usermod ep = 846/846/846
tail: 00 00 00 00 | ff ff ff ff | 6a 09 00 00 | c3 c4 10 00 00 00 00 00 | 00 00 00 00
      graveyard count 0, marker -1, class 0x096a, watermark 0x10c4c3, 0
```

6 + 40·8,401 + 24 = 336,070 = ISIZE. Cross-checks: `Partitions/15` header
u32@14 = `d1 20 00 00` = 8,401 ✔; `Global/History` episode count = 848 and
the maximum `m_lastModificationDate` over all 8,401 records is 847, so
847+1 = 848 ✔ (the module asserts this per file).

Owner chains (racbasic, ids 230–236): 231→230, 233→230, 232→233, 235→234,
236→235 — a small tree of low built-in ids [hypothesis: category /
subcategory / material-asset hierarchy; needs the partitions decode to name
them]. Worksharing example (dach, record 13611): `id=0x18ba4a`,
`originalElementId=0x18a5ca` — ids are renumbered on sync-with-central, the
history keeps the birth id, and the table is sorted by the *current* id.

## 5. Schema tie-in (de-framed `Formats/Latest`)

The relevant classes only decode correctly in the **de-framed** schema
(byte 173,165 of the true 496,597-byte blob; the old corrupted inflate had
garbage there — which is why `ElemTable` was previously "not found").

```
ElemRec          (class 0x05c5)   4 fields
  m_history            type 0e 00 00 00 a5 03   → class 0x03a5 ElementHistory (inline)
  m_id                 type 0e 00 00 00 14 00   → ElementId (u64)
  m_OwningElementId    type 0e 00 00 00 14 00   → ElementId (u64)
  m_partitionId        type 0e 00 00 00 8f 05   → class 0x058f PartitionId {u32 m_id}
ElemRecPointers (0x05c6), ElementAndGRep (0x05c7), ElemRecPtr (0x05c8)  # runtime-only
ElemTable        (class 0x05c9)   2 fields
  m_elemArr            type 0e 50 00 00 c5 05   → 0x50 = array of class 0x05c5 (ElemRec)
  m_graveyardRecs      type 0e 50 00 00 ca 85   → array of class 0x05ca, 0x8000 bit
                                                  = "definition follows inline":
GraveyardRec     (class 0x05ca)   m_id (ElementId), m_partitionId (0x058f),
                                  m_history (0x03a5), m_pSource (ptr), m_bExpandAllOnLoad
                                  (bool), m_bLastElementIdOverride (bool)
ElementHistory   (class 0x03a5)   m_originalElementId (0x027e), m_creationDate (0x0253
                                  = EpisodeId), m_lastModificationDate (0x0253),
                                  m_lastUserModificationDate (0x0253); [4 wire fields],
                                  then m_EpisodeCounts array (not on the wire here)
```

Class-index derivation: `ElemRec` is defined 3 top-level classes before
`ElemTable`; `ElemTable.m_elemArr` references 0x05c5 ⇒ `ElemRec` = 0x05c5,
so `ElemTable` = 0x05c5+4 = **0x05c9** = the stream's leading u16 ✔.
Inline-defined classes carry `(index | 0x8000)`: GraveyardRec `ca 85` ⇒
0x05ca ✔ (matches its type reference), ElementHistory `a5 83` ⇒ 0x03a5 ✔,
PartitionId `8f 85` ⇒ 0x058f ✔. The footer's `6a 09` = class 0x096a is
therefore [hypothesis] another schema class tag (a small object holding the
u64 id watermark; a `KingIdWatermark`/`LastElementId`-style class — name to
be resolved by the schema agent's full class enumeration).

Consequence for the generator: to emit an ElemTable we must be able to (a)
allocate schema class index 0x05c9/records for the target release, (b)
write one 40-byte record per element with consistent EpisodeIds referencing
a self-authored `Global/History` episode list, sorted by id, (c) append the
footer with a watermark ≥ max id, gzip it, prepend the 8-byte zero prefix,
and (d) **re-page it into 64,896+353 pages with correct 353-byte blocks** —
the latter is not yet reproducible (block content unknown).

## 6. Statistics (all six files)

| file | records | id range | never user-modified | with owner | max ep (mod) | History episodes | renumbered |
|---|---:|---|---:|---:|---:|---:|---:|
| racbasic | 8,401 | 1 … 1,098,851 | 620 | 3,884 | 847 | 848 ✔ | 0 |
| racadv | 17,231 | 1 … 438,567 | 5,763 | 10,606 | 616 | 617 ✔ | 0 |
| rme | 28,132 | 1 … 888,013 | 2,591 | 12,853 | 795 | 796 ✔ | 0 |
| rstadv | 13,855 | 0 … 271,237 | 1,259 | 5,611 | 578 | 579 ✔ | 0 |
| rstbasic | 13,936 | 1 … 1,472,524 | 345 | 4,307 | 1,016 | 1,017 ✔ | 0 |
| dach | 49,776 | 2 … 4,294,190 | 3,296 | 32,255 | 2,739 | 2,740 ✔ | 1,476 |

All ids fit in 32 bits in this corpus (high dword 0) although the fields
are u64. `partitionId` = 0 for all 128,331 records.

## 7. Confidence

| claim | confidence |
|---|---|
| page framing 64,896+353, valid gzip trailers, decode recipe | verified (byte-exact CRC/ISIZE, six files) |
| `u16 0x05c9` + `u32 count` header; 40-byte fixed records; `6+40N+24` size | verified |
| record field boundaries and names (ElemRec / ElementHistory / PartitionId) | verified against de-framed schema + data |
| sorted by `m_id`; count == Partitions header count; `max mod ep + 1 == History episode count` | verified (six files) |
| u32s are EpisodeId version stamps (create ≤ user-mod ≤ mod) | strong inference (invariants + History count) |
| `m_OwningElementId` = owner element id | verified name; owner-tree semantics inferred |
| footer field meanings (`0x096a` class tag, watermark) | hypothesis |
| meaning of the 8-byte stream prefix; 353-byte page blocks | unknown |

## 8. Unknowns

1. Content/algorithm of the 353-byte per-page blocks (needed to *write* files;
   irrelevant for reading). First byte always 0x00; rest high entropy.
2. Meaning of the 8-byte `Global/*` prefix (zero for ElemTable in all six).
3. `GraveyardRec` wire format — array count is 0 in every sample, so its
   serialized layout (id, partitionId, history, pointer, two bools) is only
   known from the schema, not observed. Presumably populated when the
   graveyard (deleted-element records) is non-empty.
4. Exact identity of footer class 0x096a and whether the u64 is "last issued
   id" vs "next free id" (racbasic's 0x10c4c3 > max id by 0x60 supports
   "highest ever issued").
5. Why `partitionId` is 0 everywhere even in dach, which has two
   `Partitions/*` streams (84, 85) — likely 84/85 are stream *names* while
   PartitionId 0 is the single logical partition; needs the PartitionTable
   agent.
6. Semantics of `m_OwningElementId` per element class (category tree vs. host
   vs. family owner) — needs joined decode with `Partitions` element data.
7. Whether `m_lastUserModificationDate == 0xFFFFFFFF` means "never edited by a
   user" or "no worksharing user context" (dach, the workshared file, has the
   same convention).

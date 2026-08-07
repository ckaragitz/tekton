# 05 — `Global/PartitionTable` and `Partitions/<N>` (element data)

Slice owner: agent `partitions`. Code: `src/rvt/partitions.py`
(`.venv/bin/python src/rvt/partitions.py [project...] [--shallow]`).
Everything below is verified byte-for-byte against all six Revit 2026
samples unless tagged `[hypothesis]`. Offsets in `Partitions/<N>` are
**de-paged** offsets (see §1) unless a raw offset is stated.

## 0 · TL;DR

| Question | Answer | Confidence |
|---|---|---|
| Where is element data? | `Partitions/<N>` = 3 parallel logical record streams (`seq` 101/102/103) chunked into ~128 KiB gzip blocks, appended in "save units". | verified |
| Do records span gzip blocks? | Yes. Block flag word: 4 whole records, 6 record continues, 7 pure continuation, 5 continuation ends. Concatenating block payloads per `seq` yields a clean `[header][body]…` record stream (walk covers 100 % of every segment in every file). | verified |
| Record framing | `seq 101`: 16-B header `{i64 id, u32 size, u32 cls}` + body, cls = 0x5e5 ≈ `ElementHeader` for every record. `seq 102/103`: 20-B header `{i64 id, u32 stamp, u32 size, u32 cls}` + body; 102 holds the polymorphic element objects (`GStyleElem`, `CategoryElem`, `CurveElem`, …), 103 mostly cls 0xf2c/0x89e small records. Same record count and id set in all three segments. | verified (class names ±1, see §7) |
| What is `Global/PartitionTable`? | A **workset** table (one entry per file here): GUID, two element-ish ids, kind, UTF-16 name ("Workset1" / "Family : Title Blocks : A0 metric" / "Project Standards" / "Architektur"). It does NOT map `<N>` to streams. | verified layout; naming `[hypothesis]` |
| Why `Partitions/84` **and** `/85` in dach? | `<N>` is a document-increment counter; `Global/DocumentIncrementTable`'s first u32 = highest `<N>` + 1 in all six files. `85` is a nearly empty second partition (0 elements, 3 sentinel records). | verified |
| The "corrupt gzip trailer / 270–712 trailing bytes" mystery | **Solved.** Every OLE stream is stored in 64,896-byte pages, each full page followed by a 353-byte page-trailer record. Excise those and 100 % of gzip members have valid CRC32/ISIZE. Applies to `Formats/Latest` and `Global/*` too (see `docs/inbox/partitions.md`). | verified |

## 1 · Stream paging — read this first (corpus-wide)

Revit does not write a stream's payload contiguously. The raw OLE stream is

```
[ page 0: 64,896 (0xFD80) payload bytes ][ 353-byte page trailer ]
[ page 1: 64,896 payload bytes ][ 353-byte page trailer ] ...
[ last page: <= 64,896 payload bytes ]                       (no trailer)
```

Evidence:

* For every gzip member whose CRC failed, `physical_member_len − (B−8)` is
  **exactly** 353 or 706 (`B` = declared member length, §4.2). Distribution
  in racbasic `Partitions/15`: `{0: 875, 353: 279, 706: 2}`.
* The absolute stream offsets of the inserted 353-byte runs are
  64,896, 130,145, 195,394, 260,643, … i.e. `64,896 + k·65,249` — found by a
  CRC-validated splice search (remove 353 bytes at offset Q, re-inflate,
  compare with the stored CRC32/ISIZE) run independently on eight blocks;
  each solved block put its splice at the next multiple of 65,249.
* After removing `353 B` at those positions: **13,535 / 13,535** gzip members
  in all seven `Partitions/*` streams validate against their stored CRC32
  and ISIZE, `B == 8 + member_len` for every block, and
  `Formats/Latest` inflates to exactly its stored ISIZE = 496,597 bytes with
  matching CRC (0x26852216) — not the 498,766 partially-garbled bytes in
  `extracted/*/Formats__Latest.gz/000.bin`.
* Every page trailer begins with byte `0x00`; the second byte is a multiple
  of 0x10 (0x00…0xf0); the remaining 351 bytes are high-entropy (no zlib
  stream at any offset). Contents undecoded `[hypothesis: per-page
  checksum/signature record]`.

Consequence: **all** analysis must start from `depage(raw)`; the
pre-carved `extracted/*/*.gz/NNN.bin` files are wrong for any member that
crosses a page boundary (they contain a foreign 353-byte run decoded as
deflate, so their content is right up to that point and garbage after).
`clean_off → raw_off = clean_off + 353·⌊clean_off / 64896⌋`.

## 2 · `Global/PartitionTable`

8-byte stream header (`05 00 00 00 00 00 00 00`-style prefix, see A8) then
one gzip member; inflated 87–139 bytes. The stream is below one page, so
no paging. Layout of the inflated payload:

| off | size | type | field | racbasic value | notes |
|---|---|---|---|---|---|
| 0x00 | 2 | u16 | class ordinal | `0x0c80` (3200) | `[hypothesis]` schema class `PartitionTable` (§7) |
| 0x02 | 4 | u32 | version | 1 | constant |
| 0x06 | 4 | u32 | entry count | 1 | every sample has exactly one entry |
| 0x0a | 16 | GUID | workset unique id | `{E3E052F8-0156-11D5-9301-0000863F27AD}` | identical in the 4 files born from the same template; rstadv `{771CA0EF-…}`, dach `{20C8CDF4-…}` |
| 0x1a | 4 | u32 | 0 | 0 | |
| 0x1e | 4 | u32 | id_a | 352 | 352 in five files, 254 rstadv, 131 dach `[unknown; element id-like]` |
| 0x22 | 4 | u32 | id_b | 824 | per file: 596 / 776 / 556 / 989 / 2654. 824 recurs in racbasic `DocumentIncrementTable` right after user name "zhangg" `[hypothesis: last-edit episode / element id]` |
| 0x26 | 4 | i32 | -1 | -1 | |
| 0x2a | 4 | u32 | kind | 0 | 0 = user workset ("Workset1", "Architektur"), 1 = "Project Standards" (rstadv), 2 = "Family : Title Blocks : A0 metric" (racadv, rme) |
| 0x2e | 1 | u8 | 0 | 0 | |
| 0x2f | 4 | u32 | name length (UTF-16 units) | 8 | |
| 0x33 | 2n | UTF-16LE | name | "Workset1" | |
| … | 20 | u32×5 | 1, 1, 0, 1, 0 | | constant tail |

Worked hex (racbasic, whole payload, 87 bytes):

```
0000  80 0c 01 00 00 00 01 00 00 00 f8 52 e0 e3 56 01   class=0x0c80 v=1 n=1 GUID...
0010  d5 11 93 01 00 00 86 3f 27 ad 00 00 00 00 60 01   ...GUID  0  id_a=352
0020  00 00 38 03 00 00 ff ff ff ff 00 00 00 00 00 08   id_b=824 -1 kind=0 flag len=8
0030  00 00 00 57 00 6f 00 72 00 6b 00 73 00 65 00 74   "Workset
0040  00 31 00 01 00 00 00 01 00 00 00 00 00 00 00 01   1"  1 1 0
0050  00 00 00 00 00 00 00                              1 0
```

Cross-file table (from the tool):

| file | GUID | id_a | id_b | kind | name |
|---|---|---|---|---|---|
| racbasic | E3E052F8-… | 352 | 824 | 0 | Workset1 |
| racadv | E3E052F8-… | 352 | 596 | 2 | Family : Title Blocks : A0 metric |
| rme | E3E052F8-… | 352 | 776 | 2 | Family : Title Blocks : A0 metric |
| rstadv | 771CA0EF-… | 254 | 556 | 1 | Project Standards |
| rstbasic | E3E052F8-… | 352 | 989 | 0 | Workset1 |
| dach | 20C8CDF4-… | 131 | 2654 | 0 | Architektur |

Interpretation: this is the workset table of a **non-workshared** file
(single default workset). The partition stream number `<N>` never appears
in it — `Global/PartitionTable` does **not** index the `Partitions/<N>`
streams. `[hypothesis]` in a workshared file the entry count grows and the
`kind` field distinguishes user/family/standard/view worksets, mirroring the
Revit API `WorksetKind` enum (values differ from the API's).

## 3 · Which `Partitions/<N>` exist and why

| file | streams | `DocumentIncrementTable` u32 @+2 | ElemTable count | `Partitions` header `elem_table_count` |
|---|---|---|---|---|
| racbasic | 15 | 16 | 8401 | 8401 |
| racadv | 13 | 14 | 17231 | 17231 |
| rme | 14 | 15 | 28132 | 28132 |
| rstadv | 12 | 13 | 13855 | 13855 |
| rstbasic | 21 | 22 | 13936 | 13936 |
| dach | 84, 85 | 86 (`0x56`) | 49776 | 49776 (`/84`), 0 (`/85`) |

`Global/DocumentIncrementTable` starts `3c 05 <u32 next> …`; `next` is
always max(`<N>`)+1, so `<N>` is a monotonically increasing document
increment ("partition version") counter. dach kept two partition streams:
`84` = the whole model, `85` = an almost empty later partition (0 elements,
one sentinel record per segment). Its complete 291 bytes are the reference
example for the framing (annotated in §4.4).

## 4 · `Partitions/<N>` stream layout (de-paged)

### 4.1 Stream header — 18 bytes

| off | size | field | value | evidence |
|---|---|---|---|---|
| 0x00 | u32 | version | 9 | constant, all 7 streams |
| 0x04 | u32 | 0 | | |
| 0x08 | u16 | class ordinal | `0x03a3` (931) | same u16 leads `Global/ContentDocuments`, appears again in each unit separator and the end record; schema neighbourhood `ContentMarker/ContentRec` `[hypothesis]` |
| 0x0a | i32 | 0 | | |
| 0x0e | u32 | `elem_table_count` | racbasic 8401 = the count field at offset 2 of `Global/ElemTable` (`c9 05 d1 20 00 00`) | equal in every file where ElemTable is available |

### 4.2 Block framing (every compressed block)

```
+0x00  u16  0x0f28   block header tag (3880)
+0x02  u32  flags    4 | 5 | 6 | 7  (see 4.3)
+0x06  u32  A        record headers that START in this block
+0x0a  u32  B        8 + gzip member length  (1156/1156 in racbasic; 13,535/13,535 corpus-wide)
+0x0e  u32  C        record body bytes stored in this block (see 4.3)
+0x12  u32  seq      101 | 102 | 103   logical sub-stream
+0x16  u32  0
+0x1a  gzip member   1f 8b 08 00 00 00 00 00 00 0b | raw deflate | crc32 | isize
       u16  0x0f21   block trailer tag (3873)
       u32  B        copy of the header's B (bit-exact in every real block)
```

Worked example — racbasic block 0 (raw offsets equal de-paged offsets here):

```
0000: 09 00 00 00 00 00 00 00 a3 03 00 00 00 00 d1 20 00 00   stream hdr (v9, 0x3a3, 8401)
0012: 28 0f 04 00 00 00 a0 02 00 00 4c 3f 00 00 0c d5 01 00   tag flags=4 A=672 B=16204 C=120076
0022: 65 00 00 00 00 00 00 00                                 seq=101, 0
002c: 1f 8b 08 00 00 00 00 00 00 0b …16,186 bytes deflate…      member = 16,196 = B-8
3f70: 21 0f 4c 3f 00 00                                       trailer, B=0x3f4c=16204
3f76: 28 0f 04 00 00 00 a7 02 00 00 9b 3d 00 00 …             next block (A=679 B=15771)
```

Inflated block 0 = 130,828 bytes = 16·A + C (seq 101).

### 4.3 Flag word, ISIZE relation, record spanning

`flags` bit 2 (value 4) is always set. Bit 1 = "last record continues into
the next block", bit 0 = "block starts with the continuation of a record".
Chains observed: `4* → 6 → 7* → 5 → 4*` (23 chains in racbasic;
232 in dach). Exact relation between header, gzip ISIZE and the inflated
length (13,535 blocks, zero exceptions):

| flags | meaning | ISIZE (= inflated length) |
|---|---|---|
| 4 | only whole records | `hdr_len(seq)·A + C` |
| 6 | A ≥ 1; the last record's body continues in next block | `hdr_len·A + C − 4` |
| 7 | pure continuation, A = 0 | `C` |
| 5 | continuation ends here, A = 0 (nothing else observed) | `C + 4` |

`hdr_len` = 16 for `seq` 101, 20 for `seq` 102/103. `C` therefore counts
record body bytes except for a ±4 accounting wrinkle around a spanning
record (its 4-byte class word). Physically the record simply flows across
the block boundary: `20 + 487,202` body bytes of racbasic's first `seq`-102
record (class 0x9c3 ≈ `KeynoteTable`) occupy blocks 12–15 exactly and the
next record header follows immediately in the concatenated stream — no
per-fragment framing inside the payload.

### 4.4 Save units, footers, separators, end record

Blocks are grouped into **units**. Unit 0 is the original save (large runs:
racbasic blocks 0–11 seq 101, 12–109 seq 102, 110–232 seq 103 …); every
later unit is small (typically one 101, one 102, one 103 block =
one incremental save). racbasic has 164 units, dach `/84` 1,244.

```
unit terminator   28 0f | 00×16                     18 bytes (a flags=0 block hdr)
footer            3f 0f | u32 64 | 64 opaque bytes    [hypothesis: SignatureMarker, schema ~0x0f3f]
                  u32 34 | UTF-16LE "Data generated by Autodesk® Revit®"
                  (u32 0 blob / u32 0 chars in the tiny dach /85)
unit separator    a3 03 | i32 -1 | a2 03 | u32 counter | GUID(16)   28 bytes -> next unit's blocks
end record        a3 03 | i32 0 | i32 -1 | u32 0 | zero pad (0–484 B) | opaque tail (48–276 B)
```

Unit-separator GUIDs are real document identities: racbasic unit 1's
`{34B22600-3ED6-44B3-B4F1-6596F4D52B43}` occurs twice in `Global/Latest`
and once in `Global/ContentDocuments` (whose stream begins
`a3 03 ff ff ff ff a2 03 ff ff ff ff <that GUID> …`). The separator `u32
counter` ranges 185–4633 (racbasic 203–2160) `[unknown]`.

Annotated dach `Partitions/85` (whole stream, 291 bytes — an empty
partition: one unit, one block per segment, no signature blob):

```
0000  09 00 00 00 00 00 00 00 a3 03 00 00 00 00 00 00 00 00   hdr v9, 0x3a3, count=0
0012  28 0f 04 00 00 00 01 00 00 00 24 00 00 00 00 00 00 00   flags=4 A=1 B=36 C=0
0022  65 00 00 00 00 00 00 00                                 seq=101
002c  1f 8b … (28 B member -> 16 B: ff×8 00 00 00 00 00 00 00 00 = sentinel rec)
0048  21 0f 24 00 00 00                                       trailer B=36
004e  28 0f 04 00 00 00 01 00 00 00 25 00 00 00 00 00 00 00   A=1 B=37 C=0
005e  66 00 00 00 00 00 00 00 1f 8b … (20 B: ff×8 01 00 00 00 00×8)  seq=102
0085  21 0f 25 00 00 00 28 0f … 67 00 00 00 … 1f 8b …          seq=103 block
00c2  21 0f 25 00 00 00                                       last trailer
00c8  28 0f 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00   terminator
00da  3f 0f 00 00 00 00 00 00 00 00                           empty blob, empty string
00e4  a3 03 00 00 00 00 ff ff ff ff 00 00 00 00 00           end record
00f3  94 4c 28 dc af 06 f5 52 …(48 B opaque tail)
```

### 4.5 Header vs `index.json` correlation (task item b)

The 18-byte stream header does **not** index the gzip members: its only
count is `elem_table_count` (§4.1), unrelated to member counts. The
per-block `B` field is the member locator: `B == 8 + member length` for
100 % of blocks after de-paging, and its copy sits in the trailer, so the
framing is walkable without `index.json`. `index.json` (from
`tools/scan_gzip.py`) is now known to be wrong in two ways: it carved the
**paged** bytes (192/1068 racbasic members contain a page trailer inside
their deflate data) and it **missed ~8 % of members** (1068 carved vs 1156
real blocks in racbasic; the scanner resumed after `consumed` and skipped a
member when a false `1f 8b 08` matched inside data). The corpus should be
re-carved from de-paged streams — proposed in `docs/inbox/partitions.md`.

| file | pages | de-paged size | real blocks | `index.json` members | units | inflated total |
|---|---|---|---|---|---|---|
| racbasic 15 | 284 | 18,408,811 | 1156 | 1068 | 164 | 107,689,125 |
| racadv 13 | 248 | 16,068,461 | 999 | 910 | 122 | 94,977,765 |
| rme 14 | 469 | 30,416,107 | 2050 | 1902 | 306 | 187,994,090 |
| rstadv 12 | 215 | 13,913,588 | 1011 | 931 | 181 | 85,419,467 |
| rstbasic 21 | 93 | 5,971,253 | 414 | 383 | 53 | 39,813,772 |
| dach 84 | 1979 | 128,415,208 | 7902 | 7228 | 1244 | 697,805,989 |
| dach 85 | 1 | 291 | 3 | 3 | 1 | 56 |

## 5 · Block semantics (task item c) — conclusion

Blocks are ~131 KiB windows over **three contiguous logical byte
streams**, one per `seq` value; they are not self-contained records:

* records span block boundaries (flags 6/7/5 chains, §4.3);
* concatenating the inflated payloads of one `seq` in stream order yields a
  buffer that walks as `[record header][body]…` from byte 0 to the last
  byte with zero slack — verified for all 21 segments of the corpus (e.g.
  racbasic `seq` 102: 63,944,890 bytes, 85,978 records, walk covers 100 %);
* the three segments of a partition carry **the same record count and the
  same id multiset** (racbasic 85,978 records / 85,815 distinct ids in each
  of 101, 102, 103; dach 570,878 / 569,635) — three aspects of the same
  object list, in the same order.

Ordering within a segment is by save unit; ids increase within a run.

## 6 · Element record framing (task item d)

```
seq 101 record:  i64 id | u32 body_size | u32 cls_word | body[body_size]
seq 102/103   :  i64 id | u32 stamp | u32 body_size | u32 cls_word | body[body_size]
cls_word      :  low u16 = schema class ordinal, high u16 = 0 or small (2 seen)
```

Per-segment content:

| seq | header | class word | body | interpretation |
|---|---|---|---|---|
| 101 | 16 B | `0x5e5` (1509) for every real record | 100–300 B: `00 00`, 48 × `0xff`, then a nested `{u16 class, u32 1, i64 self-id, …}` sub-object; `f1 05` (0x5f1) recurring | one homogeneous header record per object — schema neighbourhood `ElementHeader / ElementRegenHistory` `[hypothesis §7]` |
| 102 | 20 B | polymorphic: 2252, 737, 954, 2572, 2124, 1158, 1989, 3152/3151, 2531 … | 100 B–500 KB; body ends by embedding another `{u16 class, u32 1, i64 self-id}` sub-record | the element objects proper (schema neighbourhood: `GStyleElem`, `CategoryElem`, `CurveElem`, `LinearDimensionType`, `FontTable`, `DBViewType*`, `InsertableInst`, `ParamElemFamily/Global` …) |
| 103 | 20 B | `0x0f2c` for 86–90 %, `0x89e` for most of the rest | 0x0f2c records: 2-byte body `00 00`, stamp constant `0x0069003c`; 0x89e records larger | `[hypothesis]` graphics reps / placeholders (schema neighbourhood `SerializedDummy` and `GElement/GRep`) |

`stamp` is a per-record 32-bit value, distinct per record in `seq` 102
(not crc32/adler32 of the body; `[unknown]` — version/hash). Sentinel
records: each save unit contributes exactly one record with `id = -1`,
`cls_word = 0` (racbasic: 164 units → 164 id −1 records per segment;
`seq` 102/103 sentinels carry `stamp = 1`).

Id cross-reference (racbasic): `Global/ElemTable` = 8,401 records of 40
bytes with ids 1…1,098,851; partition records cover 85,815 distinct ids
(1…1,098,776/1,098,851). 8,223 of the 8,401 ElemTable ids occur among the
partition records; partition ids are a superset → partitions hold every
serialized object (elements **plus** sub-objects/atoms), `ElemTable` only
the addressable elements `[hypothesis]`. Element id 86,291 (`13 51 01
00 00 00 00 00`) is the first record of block 0 in racbasic and is present
in ElemTable at offset 49,486 with paired fields `6e 01 00 00 4f 03 00 00
27 02 00 00`.

Worked record (racbasic `seq` 101, first record):

```
13 51 01 00 00 00 00 00   id = 86,291
77 00 00 00               body_size = 119
e5 05 00 00               cls_word = 0x5e5
00 00 ff×48 00 80 ff ff 1e 08 00 04 c3 09 00 00 00 00 ff ff ff ff
f1 05 01 00 00 00 13 51 01 00 00 00 00 00 …   nested {class 0x5f1, 1, self-id}
```

## 7 · Class ordinals seen in this slice `[hypothesis, ±1 drift]`

Derived from a first-occurrence ordinal scan of the **correctly de-paged**
`Formats/Latest` (496,597 bytes). Explicit ordinal anchors in the schema
show the scan drifts by +1 above ordinal ~250, so read the second column
as the most likely name and the neighbourhood as the error bar. The four
`Global/*` stream leads make the +1 correction near-certain
(ElemTable → `ElemTable`, DocumentIncrementTable →
`DocumentIncrementTable`, PartitionTable → `PartitionTable`,
History → `DocumentHistory`).

| ordinal | best name (+1 rule) | scan neighbourhood (ord−1, ord, ord+1 as scanned) | where seen |
|---|---|---|---|
| 0x001c (28) | ADocument | AppInfo, ADocument, DevBranchInfo | `Global/Latest` lead |
| 0x03a2 / 0x03a3 | ContentKey / ContentMarker (or Marker / Rec) | ContentKey, ContentMarker, ContentRec | stream header, separator, `ContentDocuments` |
| 0x0538 (1336) | DocumentHistory | DocumentChangedNumberingResponseData, DocumentHistory, EpisodeList | `Global/History` lead |
| 0x053c (1340) | DocumentIncrementTable | DocumentIncrementTable, DocumentStorageIndex, … | `Global/DocumentIncrementTable` lead |
| 0x053e (1342) | DocumentStorageIndexImpl (or DocumentStorageIndex) | …, UserTable | `Contents` lead |
| 0x05c9 (1481) | ElemTable | ElemTable, GraveyardRec | `Global/ElemTable` lead |
| 0x05e5 (1509) | ElementHeader | ElementHeader, ElementRegenHistory | every `seq` 101 record |
| 0x05f1 (1521) | (near ElementPartMakerInfo) | | inside `seq` 101 bodies |
| 0x0c80 (3200) | PartitionTable | Partition, PartitionTable, PartitionTableInterface | `Global/PartitionTable` lead |
| 0x0f28 (3880) | SegmentMarker | SegmentMarker, SelectionFilterElem | block header tag |
| 0x0f21 (3873) | SegmentCheckback | SegmentCheckback, SegmentConnector | block trailer tag |
| 0x0f3f (3903) | SignatureMarker | SignatureMarker, SingleCurveElementJoinDragControl | unit footer blob tag |
| 0x0f2c (3884) | SerializedDummy (or ServerPath) | SerializedDummy, ServerPath | `seq` 103 dominant class |
| 0x089e (2206) | GElement | GElement, GRep | `seq` 103 second class |
| 0x08cc (2252) | GStyleElem | GStyleElem, GStyleElemGroupHelper | `seq` 102 top class |
| 0x02e1 (737) | CategoryElem | CategoryElem, CategoryElemGroupHelper | `seq` 102 |
| 0x03ba (954) | CurveElem | CurveElem, CurveElemData | `seq` 102 |
| 0x0c50 (3152) | ParamElemFamily / ParamElemGlobal | | `seq` 102 |
| 0x09c3 (2499) | KeynoteTable | KeynoteEntryTable, KeynoteTable, KeynoteTableTracking | 487 KB spanning record |

The block/trailer/footer tag names (`SegmentMarker`, `SegmentCheckback`,
`SignatureMarker`) fit their roles so well that the +1 correction is
almost certainly right — hand this table to the schema agent (A2) for
confirmation with an exact ordinal enumeration.

## 8 · Confidence summary

| claim | confidence |
|---|---|
| 64,896/353 stream paging, universal | verified (100 % CRC on 13,535 members + schema stream) |
| PartitionTable byte layout | verified across 6 files; field meanings for id_a/id_b/kind partly `[hypothesis]` |
| Partitions stream header (18 B), block header (26 B), trailer (6 B) | verified |
| flags semantics and ISIZE relation table | verified (13,535 blocks, no exception) |
| three parallel segments with identical record counts | verified (7 streams) |
| record header layouts (16/20 B) and full-segment walk | verified (21/21 segments walk 100 %) |
| save units, terminator, footer, separator layouts | verified byte layout; blob semantics (signature) `[hypothesis]` |
| separator GUID = document/save identity linked to `Latest`/`ContentDocuments` | verified occurrence; role `[hypothesis]` |
| class-ordinal names | `[hypothesis]` ±1 |
| page-trailer contents, end-record tail, `stamp` field, id_a/id_b | unknown |

## 9 · Unknowns

1. Contents/purpose of the 353-byte page trailer (byte 0 always 0x00,
   byte 1 a multiple of 0x10, 351 high-entropy bytes) and of the 48–276-byte
   opaque tail after the end record. `[hypothesis]` integrity/signature
   records.
2. The 64-byte `0x0f3f` unit-footer blob (`SignatureMarker`?) — per-save
   digest? Two files' unit-0 blobs share no bytes.
3. `stamp` (u32 in `seq` 102/103 record headers) — not a checksum of the
   body; constant `0x0069003c` on the small `seq` 103 records.
4. `PartitionTable.id_a` / `id_b` semantics and the meaning of the u32
   separator `counter` (185–4633).
5. The internal structure of record bodies (the nested `{class, 1,
   self-id}` object header, the 48-byte `0xff` prefix in `ElementHeader`
   records) — next decoding target once the schema field lists are typed.
6. Precise class-ordinal enumeration (needs the schema agent's parser on
   the de-paged blob).

## 10 · Using the code

```bash
.venv/bin/python src/rvt/partitions.py                 # everything, all six files
.venv/bin/python src/rvt/partitions.py racbasicsampleproject
.venv/bin/python src/rvt/partitions.py --shallow       # framing stats only
```

```python
from rvt.partitions import (depage, load_partition_table, load_stream,
                            concat_elements, scan_element_headers)
pt = load_partition_table('racbasicsampleproject')       # workset table
s  = load_stream('extracted/racbasicsampleproject/Partitions__15.bin')
for b in s.blocks[:3]: print(b.brief())                  # framing
seg101 = s.concat_segment(101)                            # 15.3 MB record stream
for rh in scan_element_headers(seg101, 101, limit=5):
    print(rh.elem_id, rh.body_size, hex(rh.cls))
buf = concat_elements('racbasicsampleproject', seq=102)  # all partitions joined
```

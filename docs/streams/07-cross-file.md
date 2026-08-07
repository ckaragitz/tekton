# 07 — Cross-file structural comparison (constant vs variable structure)

Agent: `cross-file`. Corpus: the six Revit 2026 sample projects. Tool:
`tools_cross/compare.py` (reproduces every table in this section; run
`.venv/bin/python tools_cross/compare.py`).

Slice: for every stream present in >=5 of the 6 files, compare raw stream
heads and inflated payload heads column-wise and separate CONSTANT from
VARIABLE structure. Specifically resolves: (1) the 8-byte pre-gzip prefixes
on `Global/*`; (2) the trailing data after each deflate payload; (3) the
`Contents` wrapper; (4) cross-file identity of `Formats/Latest`,
`Global/PartitionTable`, `Contents`.

While resolving (2) this analysis discovered the **page framing** of every
Revit stream (section 2), which invalidates the previously-extracted
inflated corpus. That is the headline result.

---

## 1. The 8-byte pre-gzip prefix on `Global/*` streams — RESOLVED

Every `Global/*` stream = 8-byte little-endian prefix, then a gzip member.
The prefix is a **per-stream-name constant**, identical in all six files:

| stream                          | prefix bytes              | u64 LE | evidence |
|--------------------------------|---------------------------|--------|----------|
| `Global/Latest`                | `05 00 00 00 00 00 00 00` | 5 | manifest head_hex, all 6 |
| `Global/ContentDocuments`      | `01 00 00 00 00 00 00 00` | 1 | all 6 |
| `Global/DocumentIncrementTable`| `01 00 00 00 00 00 00 00` | 1 | all 6 |
| `Global/History`               | `01 00 00 00 00 00 00 00` | 1 | all 6 |
| `Global/ElemTable`             | `00 00 00 00 00 00 00 00` | 0 | all 6 |
| `Global/PartitionTable`        | `00 00 00 00 00 00 00 00` | 0 | all 6 |

* It never varies with file, file size, stream size or block count →
  it is not a size, count, offset or per-project value.
* The `Partitions/<N>` streams begin with the analogous u64 `9`
  (`09 00 00 00 00 00 00 00`) before their own header.
* [hypothesis, high confidence in the "per-stream constant" fact, medium in
  the meaning] The value is the **serialization version / format-flags word
  of the object externalized into that stream** (the `ADocument` member the
  stream carries — `Global/Latest` = `ADocument` itself = 5; the pointer
  members `m_pHistory`, `m_oContentTable`, increment table = 1;
  `m_elemTable`, `m_pPartitionTable` = 0). A writer must reproduce these
  literal values; a reader may treat them as opaque per-stream magic.

## 2. Trailing data after each deflate payload — RESOLVED (and much more)

### 2.1 The page frame — every stream is stored in 65,249-byte pages

**Fact (verified on every gzip-carrying stream in all 6 files).** The raw
OLE stream is not the logical stream. Revit writes it as pages:

| offset (raw)              | size    | content |
|---------------------------|---------|---------|
| `n*65249 + 0`             | 64,896 (0xFD80) | logical stream bytes (payload) |
| `n*65249 + 64896`         | 353     | **page-trailer block** (not payload) |

So the logical (decodable) stream = the raw stream with every 353-byte block
at raw offsets `64896 + n*65249` removed ("de-framing"). Streams shorter
than 64,896 bytes have no full-page trailer and were always readable, which
is why the small streams (History, PartitionTable, ...) previously appeared
"fine" while every large stream failed or silently mis-decoded.

Evidence:

* **Two-encoding cross-check on the schema.** `Formats/Latest` is
  byte-identical in the six `.rvt` files, and the same *payload* ships
  (compressed differently, 165,553 bytes) in the 2026 family sample
  `vendor/phi-ag-rvt/examples/Autodesk/racbasicsamplefamily-2026.rfa`.
  Both carry the identical gzip trailer `16 22 85 26 d5 93 07 00` = CRC32
  `0x26852216`, ISIZE `496,597`. Raw-inflating either yields a *longer*
  buffer (498,766 resp. 499,059 bytes) with the wrong CRC; the two decodes
  agree only up to payload offset 138,857 and are LZ garbage after their
  respective break points (`m_nCl\0\x13\0ma...` instead of
  `m_nClasses\x04...`, then runs like `hhhhhhh`, `OOOOOOOO`).
* **Splice search.** Exhaustively deleting `K` bytes at `P` around the
  break: the unique solution is `P=64896, K=353`, then a second block at
  `P=130145 (=64896+65249), K=353`. After removing both, the `.rvt` schema
  inflates to exactly 496,597 bytes with CRC32 0x26852216 — and the *same*
  two (offset, length) frames fix the independently-encoded `.rfa` copy.
  A frame position that is identical in two differently-compressed streams
  is a fixed byte-offset framing, not content.
* **Universality.** With the fixed constants (data 64,896 / trailer 353 /
  stride 65,249), every gzip trailer in the corpus validates — see the
  table in 2.3 — including `dach-sample-project/Global/ContentDocuments`
  (7,146,173 bytes, 109 frames, previously undecodable) and 196/196 sampled
  members spread across the 129 MB `dach-sample-project/Partitions/84`
  (1,978 frames). In `racbasicsampleproject/Partitions/15`, 90 of 400
  sampled gzip members cross a frame: all 90 fail CRC as extracted, 89/90
  verify after de-framing (310/310 non-crossing members were already valid).
* **Not an OLE artifact.** The 353-byte block is physically contiguous
  with the surrounding stream data in the container (racbasic
  `Formats/Latest`: stream bytes at file offset 105,824, frame at 105,856,
  continuation at 106,209 = 105,856+353), the CFB is v4 (4,096-byte
  sectors, no DIFAT), and `olefile`'s stream bytes match a fresh read.

### 2.2 What the 353-byte page-trailer block is

Unknown in meaning; characterized structurally:

* Fixed length 353 after every full 64,896-byte page. First byte always
  `0x00`; byte 1 is `0xN0` (high nibble varies, low nibble 0) across the 109
  frames of dach ContentDocuments; last byte in {`0x00`,`0x01`}; the middle
  is high-entropy with no column constancy.
* Deterministic function of the stream content: the byte-identical
  `Formats/Latest` streams carry byte-identical frames; different
  compressed data (the `.rfa`) has different frame bytes at the same
  offsets.
* Not any standard checksum of the page (CRC32/adler32/MD5/SHA-1/SHA-256 of
  the page or of the deflate slice do not occur in the block), and not
  Deflate64.
* [hypothesis] a **compressed per-page integrity / ECC record** written by
  Revit's paged stream writer (its size scales with page length for the
  final partial page — 2.4 — with a floor, the signature of a compressed
  fixed-format record). Irrelevant for *reading*; a native writer will have
  to reproduce it (open problem, see Unknowns).

### 2.3 The bytes after each deflate payload = a VALID gzip trailer

In de-framed coordinates every stream is a completely standard gzip member:

| offset (from deflate end) | size | field | meaning |
|---|---|---|---|
| `+0` | 4 | u32 LE | **CRC32** of the inflated payload — VALID |
| `+4` | 4 | u32 LE | **ISIZE** = payload length mod 2^32 — VALID |
| `+8` | N (0..~500) | `0x00` run | zero padding |
| `+8+N` | M | high-entropy | **final partial-page trailer block** (2.4) |

The deflate body itself is textbook zlib output: dynamic-Huffman blocks,
ending in a `Z_SYNC_FLUSH` marker (`00 00 ff ff`, exactly one per stream,
7 bytes before the trailer) followed by `02 0c 00` (empty non-final +
empty final fixed-Huffman block, i.e. `Z_FINISH`), then CRC32/ISIZE. So
Revit uses **stock zlib gzip** — the compression is 100 % standard once the
frames are removed.

Validation table (first/only gzip member of each stream, after de-framing;
`crc_ok` = CRC32 matches, `isz_ok` = length matches ISIZE):

| stream (file abbreviated) | raw size | frames | logical | inflated (=ISIZE) | crc_ok/isz_ok |
|---|---:|---:|---:|---:|---|
| Formats/Latest (all 6 files) | 182,953 | 2 | 182,247 | 496,597 | True/True |
| dach Global/Latest | 1,990,990 | 30 | 1,980,400 | 4,762,933 | True/True |
| racadv Global/Latest | 119,239 | 1 | 118,886 | 1,645,873 | True/True |
| racbasic Global/Latest | 117,192 | 1 | 116,839 | 1,500,644 | True/True |
| rme Global/Latest | 338,295 | 5 | 336,530 | 4,655,284 | True/True |
| rstadv Global/Latest | 127,427 | 1 | 127,074 | 1,704,781 | True/True |
| rstbasic Global/Latest | 129,986 | 1 | 129,633 | 1,586,246 | True/True |
| dach Global/ContentDocuments | 7,146,173 | 109 | 7,107,696 | 39,281,831 | True/True |
| racadv Global/ContentDocuments | 470,605 | 7 | 468,134 | 3,099,273 | True/True |
| racbasic Global/ContentDocuments | 818,555 | 12 | 814,319 | 5,080,768 | True/True |
| rme Global/ContentDocuments | 1,316,957 | 20 | 1,309,897 | 8,180,808 | True/True |
| rstadv Global/ContentDocuments | 624,855 | 9 | 621,678 | 4,071,888 | True/True |
| rstbasic Global/ContentDocuments | 224,661 | 3 | 223,602 | 1,365,825 | True/True |
| dach Global/ElemTable | 296,563 | 4 | 295,151 | 1,991,070 | True/True |
| racadv Global/ElemTable | 92,628 | 1 | 92,275 | 689,270 | True/True |
| racbasic Global/ElemTable | 50,408 | 0 | 50,408 | 336,070 | True/True |
| rme Global/ElemTable | 151,224 | 2 | 150,518 | 1,125,310 | True/True |
| rstadv Global/ElemTable | 75,341 | 1 | 74,988 | 554,230 | True/True |
| rstbasic Global/ElemTable | 72,440 | 1 | 72,087 | 557,470 | True/True |
| Global/History (all 6) | 10-46 KB | 0 | — | 10,689–46,738 | True/True |
| Global/DocumentIncrementTable (all 6) | 683–3,949 | 0 | — | 2,976–22,378 | True/True |
| Global/PartitionTable (all 6) | 134–179 | 0 | — | 87–139 | True/True |
| Contents (all 6) | 212–236 | 0 | — | 240–274 | True/True |
| Partitions/&lt;N&gt; 1st member (all 6) | — | 92–1,978 | — | ~131 KB | True/True |

("logical" = raw − frames×353.) Compare with the pre-existing extraction:
the raw-inflate of the framed `Global/Latest` (racbasic) gives 1,506,910
bytes (6,266 bytes too long, CRC mismatch); the schema gives 498,766
(2,169 too long); the four "undecodable" streams simply hit invalid deflate
where a frame's bytes fell inside a block header. All are the same defect.

### 2.4 The final partial-page trailer block (the old "270–712 trailing bytes")

After the gzip trailer + zero pad, the last page (length `L = raw −
frames×65249`, always < 64,896) is followed by a smaller high-entropy block
whose length M scales with L:

| stream / file | last-page L | zeros | M | 353·L/65249 |
|---|---:|---:|---:|---:|
| Formats/Latest (all 6) | 52,455 | 420 | 284 | 283.8 |
| racbasic Global/Latest | 51,943 | 343 | 281 | 281.0 |
| rstbasic Global/Latest | 64,737 | 413 | 350 | 350.2 |
| rstadv Global/Latest | 62,178 | 66 | 336 | 336.4 |
| racadv Global/Latest | 53,990 | 497 | 292 | 292.1 |
| dach Global/History | 46,314 | 166 | 251 | 250.6 |
| racbasic Global/ElemTable | 50,408 | 308 | 273 | 272.7 |
| rstbasic Global/ContentDocuments | 28,914 | 443 | 157 | 156.4 |
| racadv Global/ElemTable | 27,379 | 84 | 149 | 148.1 |
| History (racadv/racbasic/rme/rstadv), L 10–14 KB | | 1–6 | **91** | 55–77 |
| Global/DocumentIncrementTable, L 683–3,949 | | 1–17 | 58–75 | 4–21 |
| Global/PartitionTable, L 134–179 | | 0–4 | 37–46 | ~1 |
| Contents, L 212–236 | | 2–5 | 42–47 | ~1 |

For last pages above ~17 KB the block length is `≈ 353·L/65249`
(proportional to page length, same ratio as full pages); below that it
saturates at a floor (~91, then ~58, ~42, ~37 for tiny streams). Structure
matches the full-page trailer (starts `0x00`, ends `0x00/0x01`) —
[hypothesis] it is the *same* per-page record computed over the final,
shorter page, its compressed size scaling with input length. Never needed
for reading (nothing after the gzip ISIZE is payload).

Correction to `KNOWLEDGE.md`: the trailer is neither corrupt nor absent, and
there is no undecoded "second record" — the 270–712 bytes are 8 bytes of
valid gzip trailer + zeros + this page-trailer block.

## 3. The `Contents` stream wrapper (magic `62 19 22 05`) — layout resolved, one field open

`Contents` (212–236 bytes) is not gzip at offset 0; it is a tiny container
also used by `RevitPreview4.0` (whose payload is an uncompressed PNG-bearing
`FilePreview` object). Layout, byte-identical framing in all six files:

| off  | size | field | value(s) | meaning |
|------|------|-------|----------|---------|
| 0x00 | 4 | magic | `62 19 22 05` (u32 0x05221962) | container magic (constant) |
| 0x04 | 4 | u32 | 0x1c = 28 | [hypothesis] container version/header id (constant; also 0x1c in RevitPreview4.0) |
| 0x08 | 4 | u32 | 1 | [hypothesis] item count (constant; 1 in RevitPreview4.0 too) |
| 0x0C | 4 | u32 | 0 | reserved (constant) |
| 0x10 | 4 | magic | `62 19 22 05` again | start of the (single) item record (constant) |
| 0x14 | 4 | u32 | 183, 430, 213, 424, 264, 178 (racbasic, dach, racadv, rme, rstadv, rstbasic) | **varies per file — meaning unresolved.** In `RevitPreview4.0` this word is 0x0000800C = flag 0x8000 (payload NOT gzipped) \| class 12 = `A3PartyAImage` (schema ordinal 12; the `FilePreview` record's `m_pAImage`), so [hypothesis] low 16 bits = a type/class-id word, but the six per-file Contents values do not fit a per-release class ordinal |
| 0x18 | var | gzip member | 10-byte header, raw deflate, **valid** CRC32+ISIZE trailer | item payload (240–274 bytes inflated) |
| after | var | `0x00`×N + ~42-byte block | | zero pad + final page-trailer block (2.4) |

Contents payloads are *per-file* (6 distinct sha256) but structurally
constant: the inflated record starts `3e 05 ...`, contains the Revit build
string in UTF-16 (`20250227_1515(x64)`), the document name `GLOBAL`, a GUID
that also appears in that file's `Global/PartitionTable` payload
(`f852e0e3-5601-d511-9301-0000863f27ad` in racbasic/racadv/rme/rstbasic),
and in the worksharing samples the last-saved-by username — a small
**storage-manifest / document-info record**. (Field-level decode of the
payload is out of this slice.)

## 4. Cross-file identity of key inflated payloads — RESOLVED

Computed on **de-framed, CRC-verified** inflate:

| stream | identical across files? | size | sha256 (first 16) |
|---|---|---:|---|
| `Formats/Latest` | **yes, all 6** (and the 2026 `.rfa` payload) | 496,597 | `6459a9a93ebde32c` (CRC32 0x26852216) |
| `Global/PartitionTable` | no — 6 distinct (racbasic ≠ rstbasic even at equal length 87) | 87–139 | — |
| `Contents` | no — 6 distinct | 240–274 | — |

So the per-release schema (`Formats/Latest`) is a true constant, but its
**true size is 496,597 bytes**, not the 498,766-byte artifact previously in
`extracted/*/Formats__Latest.gz/000.bin` (that decode is correct only up to
offset 138,857). Full-length sha256:
`6459a9a93ebde32c26e4190de2756bf7a4592e63a0d142feca43c392ecdf8ac2`.

## 5. Raw-head (first 256 B) and inflated-head (first 512 B) constancy

Full column maps are in the `tools_cross/compare.py` output; summary of the
constant-vs-variable structure:

| stream | raw head constancy (of 256 B) | notes on the varying part |
|---|---|---|
| `BasicFileInfo` | 210/256 constant | UTF-16 fixed template; varying bytes are the per-file path/name characters and a length word near +212 |
| `Contents` | 35/236 | constant = wrapper (§3) + gzip header; deflate body varies |
| `Formats/Latest` | 256/256 (whole 182,953-byte stream identical) | per-release constant |
| `Global/ContentDocuments` | 20/256 | constant = 8-byte prefix (1) + gzip header + 2 leading deflate bytes |
| `Global/DocumentIncrementTable` | 19/256 | same pattern, prefix 1 |
| `Global/ElemTable` | 20/256 | prefix 0 + gzip header |
| `Global/History` | 19/256 | prefix 1 + gzip header |
| `Global/Latest` | 18/256 | prefix 5 + gzip header |
| `Global/PartitionTable` | 26/179 | prefix 0 + gzip header + first deflate bytes (payload heads similar) |
| `Partitions/<N>` | 46/256 | 44-byte binary header (u64 9, u32 0x3a3, constants at [16..23]); varying u16/u32 at [14..15], [24..31] scale with stream size — first-record length at [28..31] equals `firstMemberEnd − 36` |
| `ProjectInformation` | 117/256 | ZIP local header; u32@18 = compressed size (correlates 1.00 with stream size); constant member-name prefix `C:\Users\hansonje\AppData\Local\Temp\d53929fb-fe89-44dd-ad77-150f8df7d710\Revit` (same Autodesk temp dir in all 6 → all samples exported in one session), then a per-file GUID + `.project.xml` |
| `RevitPreview4.0` | 254/256 | wrapper (§3) with class word 0x800C + `FilePreview`/`m_pAImage` schema stub + PNG signature; only PNG chunk length bytes vary |
| `TransmissionData` | 249/256 | u16 length prefix (varies) then constant UTF-16 XML prolog |

Inflated (de-framed) heads:

| stream | inflated head constancy (of 512 B) | varying-field correlations |
|---|---|---|
| `Formats/Latest` | 512/512 | — (identical payload) |
| `Global/Latest` | 311/512 | first 83 bytes identical (ADocument header: `1c000000..`, `ffffffff` sentinels, `a7 03`), then UTF-16 `Revit 20…` version string at +88; alternating C/v beyond = same record structure with per-file ids/counts |
| `Global/ContentDocuments` | 372/512 | fixed record skeleton (`ffffffff` sentinels, 0x03a3/0x05c9 counts) with per-file ids |
| `Global/ElemTable` | 432/512 | 40-byte record period visible in the C/v map (`CCvv..CCvv..` every 40 columns) → fixed-size element-table records |
| `Global/History` | 63/512 | u32 sequences at +156.. increase monotonically and are shared by four files (racadv/racbasic/rme/rstbasic) — a common template's edit history; strong correlation with file size (+0.99) is the tail growth |
| `Global/DocumentIncrementTable` | 80/512 | header constant, entries per-file |
| `Global/PartitionTable` | 47/139 | constant `80 0c 01 00 00 00 01 00 00 00`, GUID at +10 shared by 4 files, per-file partition name (`Workset1`, `Family : Title Blocks : A0 metric`, `Project Standards`) as UTF-16 |
| `Contents` | 75/274 (see §3) | build string + GUIDs + name |

## 6. How to read a stream correctly (procedure)

1. Read the OLE stream `raw`.
2. **De-frame:** drop bytes `[64896+n*65249, +353)` for all `n` while inside
   the stream (`compare.deframe`).
3. Locate the gzip magic `1f 8b 08` (offset 0 for `Formats/Latest`, 8 for
   `Global/*` after the u64 prefix, 24 inside `Contents`, per-record in
   `Partitions/<N>`); skip the 10-byte gzip header; `zlib.decompressobj(-15)`.
4. **Verify** with the 8 bytes following the deflate data: CRC32 and ISIZE
   (they are valid — use them as the integrity check, and ISIZE is the true
   payload length).
5. Everything after that is padding + page-trailer block; ignore.

## Confidence

| claim | confidence |
|---|---|
| Global prefix is a per-stream constant (5/1/1/1/0/0) | certain |
| Prefix meaning = per-object serialization version | hypothesis |
| Page frame: 64,896 data + 353 trailer, stride 65,249, from raw offset 0 | certain (all streams, all files, incl. 129 MB / 1,978 frames, and an external `.rfa`) |
| gzip trailers (CRC32+ISIZE) valid after de-framing; compression is stock zlib | certain |
| Trailing bytes = gzip trailer + zeros + final page-trailer block | certain |
| Page-trailer block semantics (integrity/ECC record) | hypothesis |
| Contents wrapper offsets/constants; item word 0x14 unresolved | layout certain, field meaning open |
| Formats/Latest true size 496,597 / sha256 above; identity across files | certain |

## Unknowns

1. **Semantics of the 353-byte per-page trailer** and its short final
   variant (37–353 bytes): required to *write* a native `.rvt`; whether
   Revit's reader verifies it is untested. First byte `0x00`, size ∝ page
   length with a floor, deterministic per page content, not a standard
   hash. Candidate: compressed per-page checksum/ECC record. Needs a
   Revit-side experiment (edit a page-trailer byte, try to open the file).
2. Whether the page constants (64,896 / 353) vary with anything (release,
   worksharing, stream type). Constant in this 2026 corpus + one 2026 `.rfa`;
   the 2016–2025 `.rfa` schemas in `vendor/phi-ag-rvt/examples` also carry
   valid-looking ISIZE trailers that raw-inflate too long, so older releases
   are framed too — constants unverified there.
3. `Contents` item word at 0x14 (183/430/213/424/264/178): not a size, sum,
   ISIZE or CRC of anything in the stream; not a per-release class ordinal
   (schema identical, value differs). Possibly a per-document counter/id
   also stored in `Global/DocumentIncrementTable` — untested.
4. Zero-pad length N before the final block (0–497): no formula found; may
   simply be the writer's page buffer slack.
5. The `Partitions/<N>` 44-byte header semantics (out of slice; only the
   constant/varying map and "first-record length" observation recorded).

# 06 · `Global/ContentDocuments` and `Global/History`

Status: History **decoded** (full layout, all six samples). ContentDocuments
**framed and mapped** (container/entry structure and cross-links proven;
per-entry object internals partial). Tooling: `src/rvt/content.py`
(`python -m rvt.content` runs over all six extracted samples).

| stream | schema field (`Formats/Latest`, class `ADocument`) | racbasic raw → inflated | what it is |
|---|---|---|---|
| `Global/History` | `m_pHistory` (`0e 02` = owned object ptr) | 14,146 → 15,290 B | Save/episode history: upgrade-version list + newest-first array of episode GUIDs |
| `Global/ContentDocuments` | `m_oContentTable` (`0e 02`) | 818,555 → 5,106,253 B | Ordered map GUID → embedded content-document (an `ADocument`-shaped object per loaded content item — families [hypothesis]) |

Both streams use the common `Global/*` envelope (§1). All offsets below are
into the **inflated** payload unless stated as "raw".

---

## 1. The `Global/*` envelope (verified across all 36 Global streams)

```
raw:  [8-byte prefix][gzip hdr 10 B][raw deflate blocks ...]
      [00 00 ff ff][02 0c 00][crc32:u32][isize:u32][00 padding][footer blob]
```

| raw offset | size | field | meaning / evidence |
|---|---|---|---|
| 0x00 | 8 | prefix | little-endian u64. **Per-stream-type constant** across all six files: `ContentDocuments`, `History`, `DocumentIncrementTable` = `1`; `ElemTable`, `PartitionTable` = `0`; `Latest` = `5`. It does not track content (CD has 14–60 entries yet prefix is always 1) → **[hypothesis] a per-stream serialization/schema selector**, not a count. |
| 0x08 | 10 | gzip header | `1f 8b 08 00 00000000 00 0b` (CM=deflate, no flags, mtime 0, XFL 0, OS 0x0b = NTFS). |
| 0x12 | var | deflate | Raw deflate; decode with `zlib.decompressobj(-15)` (the file's own gzip trailer is not trustworthy, see below). |
| end−N | 7 | `00 00 ff ff 02 0c 00` | Writer's end signature, present in every stream: an empty **stored** block (`Z_SYNC_FLUSH` byte-align marker `00 00 ff ff`) followed by two empty **fixed-Huffman** blocks, the second `BFINAL=1` (`02 0c 00`). Exactly one `00 00 ff ff` per stream, always here (searched all 12 CD/History streams). |
| next | 4 | crc32 | gzip CRC32, little-endian. |
| next | 4 | isize | gzip ISIZE (uncompressed length mod 2³²). |
| next | var | zero padding | 0–443 bytes of `00` (racbasic History 5, CD 70; rstbasic CD 443). |
| next | var | footer blob | 37–350 high-entropy bytes to end of stream (History: 91 B in 4 of 6 files; CD 92–204 B). Not deflate at any offset (tested raw/zlib/gzip at every byte). **Undecoded — see Unknowns.** |

**Trailer validity — the "corrupt trailer" refined.** The trailer is a *real*
gzip trailer, not garbage:

- `Global/History` (all 6), `PartitionTable`, `DocumentIncrementTable`: CRC32
  **and** ISIZE match the inflated payload exactly (racbasic History:
  stored `84 57 52 a3` = crc32 `0xa3525784`, ISIZE `ba 3b 00 00` = 15,290 =
  payload length; verified with `zlib.crc32`). These streams inflate with the
  strict gzip wrapper.
- `Global/ContentDocuments`, `ElemTable`, `Latest` (the large, incrementally
  appended streams): CRC32 mismatches and **ISIZE < actual** in every file
  (racbasic CD: ISIZE 5,080,768 vs 5,106,253 actual, Δ=25,485; rstbasic CD
  Δ=6,024; rme CD Δ=46,260; rstadv CD Δ=19,570). The CRC also does not match the
  ISIZE-length prefix, so it is not a valid trailer of a truncated payload.
  Interpretation `[hypothesis]`: the trailer is *stale* — carried from an
  earlier serialization of the stream and not recomputed when the writer
  appended; Revit's reader ignores it. **Never validate CD/ElemTable/Latest by
  CRC/ISIZE.** (dach CD: ISIZE = 39,281,831 vs 10.6 MB recovered — see §3;
  there the stale ISIZE is probably close to the *true* uncompressed size.)

## 2. `Global/History` — episode/save history (FULLY DECODED)

Inflated payload layout, little-endian throughout. Verified byte-for-byte
against all six samples (`parse_history`), lengths reconcile exactly
(header + arrays + trailing u32 = payload size, e.g. racbasic
0x366 + 848·17 + 4 = 15,290).

| offset | size | type | field | value / evidence |
|---|---|---|---|---|
| 0x00 | 2 | u16 | class tag | **`0x0538`** in all six. The same tag appears as the null-pointer field `38 05 ff ff ff ff` inside every ContentDocuments document prologue (§4) → `0x0538` is the serialized class id of the history object (`m_pHistory` in embedded docs = null). Confidence: high. |
| 0x02 | 2 | u16 | object version | `1` in all six. |
| 0x04 | 10 | — | zeros | `00…00` in all six. |
| 0x0e | 4 | u32 | entry count (dup) | equals the array count at the array (848 racbasic, 1017 rstbasic, 796 rme, 579 rstadv, 617 racadv, 2740 dach). |
| 0x12 | 4 | u32 | 0 | |
| 0x16 | 5×16 | GUID[5] | header GUID slots | pattern **G, G, G, ZERO, G** in all six (racbasic G = `e340d1fc-19c1-4200-9ff0-415bc126641d`). G occurs **nowhere else** in the file (searched every stream, all encodings). `[hypothesis]` the history object's own identity/original-document GUID. |
| 0x66 | 4 | u32 | `nver` | 190 racbasic/rstbasic, 155 rme, 183 rstadv, 153 racadv, **11 dach**. |
| 0x6a | 4·nver | u32[] | **format-version list** | strictly ascending: racbasic `472, 481, 485, … , 2659, 2660, 2661, 2662`; dach `1548, 1550, 1551, 1844, 1848, 2288, 2557, 2646, 2655, 2659, 2662`. Last element is **2662 in all six** = the u32 stored as the format version in `Global/Latest`'s ADocument header (`66 0a` at Latest+0x48) and the ContentDocuments prologue variant (`64 0a` = 2660, §4). → the document's **upgrade history**: every internal *file-format version* the model has been saved under; 2662 = Revit 2026 (build 20250227). Confidence: high. |
| … | 4 | u32 | `nent` | entry count (= 0x0e). |
| … | 17·nent | rec[] | **episode entries** | see below. |
| … | 4 | u32 | 0 | trailing empty container / terminator; payload ends here in all six. |

**Episode entry (17 bytes):**

| off | size | field | evidence |
|---|---|---|---|
| +0 | 16 | GUID (`bytes_le`) | 6,597 entries across the corpus; all valid RFC-4122 (v4, plus v1 in the older-lineage files). No duplicates within a file. |
| +16 | 1 | tag byte | **`0x28` in all 6,597 records**. Meaning unknown (enum/marker). |

Semantics — **entry 0 is the newest episode, the last entry the oldest**:

- Entry 0's GUID == `BasicFileInfo`'s *"Unique Document GUID"* == *"Central
  model's episode GUID corresponding to the last reload latest"* in **all six**
  (racbasic `e6a03f8e-9e4e-4cfc-ae41-c3c559e42d55`, rstbasic
  `34447475-c1fb-44d1-b0f8-1adaa86cdbe1`, rme `f71f3b81-…`, rstadv
  `c460f867-…`, racadv `44bf6ce6-…`, dach `c45052e1-…`).
- The trailing entries are **version-1 (time-based) GUIDs whose embedded
  timestamps decrease monotonically toward the end**: racbasic entries
  843–847 decode to **2001-02-13 02:21:17** (node/MAC `00:00:86:3f:27:ad`),
  entry 724 to 2002-01-23. 67 v1 GUIDs in racbasic/rstbasic/rme/racadv (same
  ancestral sessions), 2 in rstadv, 0 in dach (all v4, newer lineage).
- Cross-file lineage: episode-GUID sets overlap between related Autodesk
  samples (racbasic∩rstbasic = 737 shared entries, racbasic∩racadv = 426,
  rme∩RAC/RST = 387) and are **disjoint** for the independent files
  (dach, rstadv share nothing) — exactly what an inherited edit-session log
  predicts.

**Conclusion:** `Global/History` = `ADocument::m_pHistory` = the model's
**episode history**: one 17-byte record per save/synchronize *episode*,
newest first, plus the ascending list of format versions the file has been
upgraded through. Confidence: high (structure), high (entry-0/BasicFileInfo
identity, v1 timestamps), medium (exact meaning of the header GUID and the
`0x28` tag byte).

**Worked example (racbasicsampleproject, inflated 15,290 B):**

```
0000: 38 05 01 00 00 00 00 00 00 00 00 00 00 00 50 03   tag=0x0538 ver=1 ... count=0x350=848
0010: 00 00 00 00 00 00 fc d1 40 e3 c1 19 00 42 9f f0   u32 0 | GUID slot0 = e340d1fc-19c1-4200-
0020: 41 5b c1 26 64 1d fc d1 40 e3 c1 19 00 42 9f f0                9ff0-415bc126641d | slot1 (=)
0030: 41 5b c1 26 64 1d fc d1 40 e3 c1 19 00 42 9f f0   | slot2 (=)
0040: 41 5b c1 26 64 1d 00 00 00 00 00 00 00 00 00 00   | slot3 = ZERO
0050: 00 00 00 00 00 00 fc d1 40 e3 c1 19 00 42 9f f0   | slot4 (=)
0060: 41 5b c1 26 64 1d be 00 00 00 d8 01 00 00 e1 01   nver=0xbe=190 | 472, 481,
 ...
035a: 65 0a 00 00 66 0a 00 00 50 03 00 00 8e 3f a0 e6   2661, 2662 | nent=848 | entry0 GUID
036a: 4e 9e fc 4c ae 41 c3 c5 59 e4 2d 55 28 6b 4c 6d   = e6a03f8e-9e4e-4cfc-ae41-c3c559e42d55 | 0x28 | entry1 ...
 ...
3ba2: 27 ad 28 f9 52 e0 e3 56 01 d5 11 93 01 00 00 86   entry846 tag 0x28 | entry847 = e3e052f9-0156-11d5-
3bb2: 3f 27 ad 28 00 00 00 00                            9301-0000863f27ad | 0x28 | u32 0 (end)
```

Raw stream head/tail (racbasic): prefix `01 00 00 00 00 00 00 00`, gzip hdr
at 0x08, deflate ends `00 00 ff ff 02 0c 00` at raw 0x36d1, trailer
`84 57 52 a3 ba 3b 00 00` (crc OK, isize 15,290 OK), 5 zero bytes, then the
91-byte footer blob `0a b8 5d 2e 70 …`.

## 3. Deflate anomaly & segment recovery (racadv, dach ContentDocuments)

`Global/ContentDocuments` in **racadvancedsampleproject** and
**dach-sample-project** does not inflate end-to-end: a standard inflater
fails mid-stream (`invalid code lengths set` @ raw 325,921 racadv;
`too many length or distance symbols` @ raw 1,631,077 dach). Established:

- The stream bytes are correct (OLE sector chain contiguous, byte-identical
  to a fresh `olefile` read); not Deflate64 (proper block cadence contradicts
  it); no second gzip member; no encryption signature.
- A block-level trace (custom instrumented inflater) shows a clean run of
  full-size dynamic blocks (~25.4 KB compressed / 16,384 symbols each), then a
  block whose *header itself* is invalid (over-subscribed code-length set);
  single-bit repair of that header does not exist.
- Further on, a strictly-valid dynamic block resumes and decodes cleanly to
  the `00 00 ff ff 02 0c 00` end signature: racadv at raw **356,781**
  (781,501 B recovered, ending exactly at the trailer), dach at raw
  **6,865,883** (1,548,828 B recovered). In racadv the resumable block is one
  full 16,384-symbol block chained back to bit 2,647,065; the true unreadable
  hole is ~5 KB of compressed data holding ~1–2 blocks.
- **The identical defect hits `Global/ElemTable` in dach and rme** (and only
  those). It is a *corpus/writer artifact concentrated in the large appended
  streams*, cause undetermined `[unknown]`: candidates are (a) genuine
  damage in the distributed samples, or (b) an append/session-splice writer
  behaviour we cannot yet model. Revit's own tolerance is unknown.

`inflate_global()` therefore performs **segment recovery**: decode the primary
run; on failure scan forward (byte-aligned) for the next strictly-valid
dynamic-Huffman block header (same acceptance test as zlib: complete,
non-oversubscribed code-length/literal/distance trees) that decodes to
end-of-stream; decode it with a 32 KiB window primed by the previous
segment's tail (`zdict`), and report the gap. Recovered-segment bytes reached
only through back-references into that unknown window are untrusted; the
resulting payload is nonetheless structurally intact (entry markers, keys
ascending) in both files:

| file | segment 0 | gap (raw) | segment 1 | payload |
|---|---|---|---|---|
| racadvanced | comp 18..323,602 → 2,110,080 B | 33,179 B | 356,781..470,499 → 781,501 B | 2,891,581 B (17 entries) |
| dach | comp 18..1,630,226 → 9,009,556 B | 5,235,657 B (!) | 6,865,883..7,145,792 → 1,548,828 B | 10,558,384 B (14 entries; stale ISIZE says ~39.3 MB → the 5.2 MB gap holds most of dach's content documents) |

## 4. `Global/ContentDocuments` — GUID-keyed table of embedded content documents

### 4.1 Container = ordered map keyed by GUID

The entire inflated payload (100% coverage in all six files, checked by
walking) is a **concatenation of entries**, each starting with the 12-byte
marker

```
a3 03 ff ff ff ff  a2 03 ff ff ff ff     (u16 0x03a3, i32 -1)(u16 0x03a2, i32 -1)
```

i.e. two null class-tagged object pointers (class ids 0x03a3=931, 0x03a2=930
`[hypothesis: base/related classes of the content-document object]`),
immediately followed by a **16-byte GUID key** (`bytes_le`). Keys are
**strictly ascending in raw byte (memcmp) order** in every file (racbasic:
first bytes `00,00,00,01,02,03,05,07,08,…,b7`) — the serialization of an
*ordered* map (`std::map<GUID, ContentDocument>` `[hypothesis]`). Entries
are **not length-prefixed**: an entry extends to the next marker; the map is
enumerated by marker scan validated by key monotonicity (this also rejects
in-payload false matches, e.g. rstbasic's zero-GUID hit at 0x6d267).

| file | payload | entries | keys ascending | skeleton / extended / anomalous |
|---|---|---|---|---|
| racbasic | 5,106,253 | **60** | yes | 29 / 7 / 24 |
| rstbasic | 1,371,849 | 26 | yes | 15 / 1 / 10 |
| rme | 8,227,068 | 32 | yes | 30 / 2 / 0 |
| rstadv | 4,091,458 | 27 | yes | 24 / 3 / 0 |
| racadv (recovered) | 2,891,581 | 17 | yes | 16 / 1 / 0 |
| dach (recovered) | 10,558,384 | 14 | yes | 11 / 3 / 0 |

### 4.2 Entry layout

Offsets relative to the entry marker. Bytes at +0x20.. are **byte-identical
to the opening of `Global/Latest`** (the host `ADocument`) except for two
extra tagged fields and the format-version value — i.e. every entry is a
serialized **`ADocument`-shaped object** (an embedded document).

| off | bytes | field | notes / evidence |
|---|---|---|---|
| +0x00 | `a3 03 ff ff ff ff` | tagged null ptr | class 0x03a3, value −1 |
| +0x06 | `a2 03 ff ff ff ff` | tagged null ptr | class 0x03a2, value −1 |
| +0x0c | 16 | **GUID key** | `bytes_le`; ascending; unique per file; each key also occurs in `Global/Latest` (§4.5) |
| +0x1c | u32 | `L` | for **skeleton** entries `entry_len == L + 36` exactly (46/60 racbasic, all rme/rstadv skeletons) → size of the fixed first body block; larger ("extended") entries continue past `+0x20+L` |
| +0x20 | `1c 00` + i32 −1 | tagged field (0x001c) | Latest: `1c 00` + 8 zero bytes + −1 (externalized `m_elemTable` `[hypothesis]`) |
| +0x26 | `c9 05` + u32 + i32 −1 | tagged field (0x05c9) | absent in Latest |
| +0x30 | `a7 03` + u32 **1** + i32 −1 | tagged field (0x03a7) | `1` `[hypothesis: m_pHostDocument = object #1, the host]` |
| +0x3a | `a0 01` + i32 −1 | tagged null ptr (0x01a0) | `m_pAppInfoManager` `[hypothesis]` |
| +0x40 | `66 10` + i32 −1 | tagged null ptr (0x1066) | Latest: `66 10` + u32 0 + −1 |
| +0x46 | `38 05` + i32 −1 | **`m_pHistory` = null** | 0x0538 = History class tag (§2) — embedded docs carry no history; the host's is the separate `Global/History` stream |
| +0x4c | `f8 0f` + u32 0 + i32 −1 | tagged field (0x0ff8) | |
| +0x56 | `e9 0a` + **u64 ElementId** | tagged ElementId field (0x0ae9) | racbasic entry keys map to host element ids 1,018,036 / 1,031,505 / 1,031,651 / …; **−1 in the host's own `Global/Latest`** at the same field → `[hypothesis, strong]` = `ADocument::m_ownerFamilyId` (schema field #11): the host **Family element that owns this embedded document**. Host id 1,018,036 recurs 385× in `Partitions/15` member 233. |
| +0x60 | i64 −1 | second id | `m_ownerFamilyContainingGroupId` `[hypothesis]` |
| +0x68 | u32 1 | | same in Latest |
| +0x6c | u32 **2660** | format version | Latest carries **2662**; content docs lag two format increments `[fact: value; meaning hypothesis]` |
| +0x70 | 11 × 00 | zeros | |
| +0x7b | i32 −1 | | |
| +0x7f | u16 **0x0644** | table tag | same tag opens the per-document GUID/summary records in `Global/Latest` (§4.5) |
| +0x81 | u32 count | element-record count | racbasic entry0: 225; typical skeleton 215–247 |
| +0x85 | count × 40 | **element records** | see §4.3 |
| … | var | further sections | tagged sequence (`6a 09 …`, index/value tables, 9-byte flag+id runs, doubles) ending in a 4×3 double **transform** (`… 00 00 f0 3f` = 1.0, `f0 bf` = −1.0) at skeleton end `[decoded landmarks only]` |
| entry_len−4 | u32 | `L` again | skeleton entries only |

Three entry kinds are observed:

- **skeleton** (majority; 19–58 KB): near-identical bodies. Two racbasic
  skeletons (19,828 vs 19,788 B, 225 vs 224 records) differ only in
  element-id bytes and one record → the *empty/default document scaffold* plus
  its per-document element ids.
- **extended** (few; up to **4.7 MB** dach, 4.5 MB rme, 1.4 MB racbasic): the
  same prologue, then additional non-length-prefixed sections carrying the bulk
  of the stream. They contain the only strings in the payload: UTF-16
  `"Floor Plans"`, `"Ceiling Plans"`, `"Elevations (Elevation 1)"`, `"3D
  Views"`, `"http://www.autodesk.com"`, `"Revit Default DB Server"` (racbasic
  0x1ec366, 0x390893) — **the default view names of a family document**.
- **anomalous** (racbasic 24, rstbasic 10, others 0): entries whose prologue
  and body carry the canonical structure with byte-valued *overlays*
  (`0x45 'E'`, `0x7b '{'` runs, `0x2a`, `0x55`, `0xff` injected into id and
  count fields; racbasic entry 38: format u32 reads `0x00550a64`, count
  `0x7b7b…`). 12,120 of 19,864 bytes differ from a clean skeleton, all
  substituting fill-like values for ids/zeros. `[unknown]` — cache slots of
  unloaded content, an unhandled sub-format, or a second interleaved stream;
  they still respect key ordering and marker framing.

### 4.3 First body block: element record table (tag 0x0644)

`u16 0x0644, u32 count`, then `count` 40-byte records:

| off | type | field | evidence (racbasic entry 0) |
|---|---|---|---|
| +0 | u64 | ElementId | `0xf8893` (1,017,995), ascending, mostly contiguous |
| +8 | u32 | class id A | 808 (0x328) for 147/225; also 837, 830, 820… |
| +12 | u32 | class id B | 833 (0x341) for 158/225; 837, 842, 844 |
| +16 | i32 | class id C | −1 whenever A is the dominant class, else = A |
| +20 | u64 | ElementId (repeat) | invariant `rec[0] == rec[4]` (holds for every record; used as validity check) |
| +28 | i64 | previous ElementId | −1 for record 0; a back-linked chain (85/224 point to the immediately previous record, others to earlier ones → a parent/owner chain) |
| +36 | u32 | 0 | always 0 |

A/B are class ids: `0x341` recurs as `41 03 00 00` in `Global/Latest`'s
per-class count tables (§4.5). Per-file dominant pairs: racbasic (808,833),
rstbasic (975,1003), rme (770,783), rstadv (541,562), racadv (572,603) →
they scale with the file, so they are **runtime-assigned ids** (element ids
of small early elements — e.g. category/style objects — or per-document
class ordinals) rather than fixed schema class numbers `[hypothesis]`. This
table is the embedded document's **element table**: the elements owned by
that content document (215–1,072 for skeletons).

### 4.4 What the content documents are `[hypothesis, strong]`

An `ADocument`-shaped object per entry, owner-family ElementId set (−1 in
the host), no history, family-style default view names in the big ones, one
element table per document, dozens per project (racbasic 60), and a stale
trailer ISIZE far beyond the recovered size in dach (39 MB): **the loaded
content documents = the family documents (and other loaded content) embedded
in the project**, `m_oContentTable` being their GUID-indexed store. Naming
each entry requires resolving its `m_ownerFamilyId` element (a `Family`
element in `Partitions/N` / `Global/ElemTable`) — see Next steps.

### 4.5 Cross-links (verified)

- **Every** CD key GUID (60/60 racbasic) appears once in `Global/Latest`, in
  a table of ~92–100-byte records (Latest offsets 975, 1067, 1159, …), each
  record = tagged counts of the form `(u32 classId, u32 n)` (e.g.
  `41 03 00 00 2b 00 00 00` = class 0x341 × 43) + the CD GUID + a
  length-prefixed UTF-16 string (`0e 00 00 00` + `"Autodesk Revit"` =
  the creating application). This is Latest's per-content-document summary
  (owned by the A5/Latest slice — flagged in inbox).
- Each key also appears once in exactly one `Partitions/15` gzip member and
  once in the raw partition stream (the loaded-content element referencing its
  document).
- The host owner ElementId (1,018,036) is a heavily referenced host element
  (385 hits in one partition block).

### 4.6 Worked example (racbasicsampleproject entry 0, payload offset 0)

```
0000: a3 03 ff ff ff ff a2 03 ff ff ff ff  00 26 b2 34   marker | key = 34b22600-3ed6-
0010: d6 3e b3 44 b4 f1 65 96 f4 d5 2b 43  74 4d 00 00   44b3-b4f1-6596f4d52b43 | L = 0x4d74 = 19828
0020: 1c 00 ff ff ff ff c9 05 00 00 00 00  ff ff ff ff   (0x1c,-1) (0x5c9,0,-1)
0030: a7 03 01 00 00 00 ff ff ff ff a0 01  ff ff ff ff   (0x3a7,1,-1) (0x1a0,-1)
0040: 66 10 ff ff ff ff 38 05 ff ff ff ff  f8 0f 00 00   (0x1066,-1) (0x538 hist=null) (0xff8,
0050: 00 00 ff ff ff ff e9 0a b4 88 0f 00  00 00 00 00    0,-1) (0xae9, ElementId 0xf88b4 = 1018036)
0060: ff ff ff ff ff ff ff ff 01 00 00 00  64 0a 00 00   i64 -1 | u32 1 | format 0xa64 = 2660
0070: 00 00 00 00 00 00 00 00 00 00 00 ff  ff ff ff 44   zeros | -1 | tag 0x0644
0080: 06 e1 00 00 00 93 88 0f 00 00 00 00  00 28 03 00     count 0xe1=225 | rec0: id 0xf8893, 808,
0090: 00 41 03 00 00 ff ff ff ff 93 88 0f  00 00 00 00     833, -1, self, prev=-1, 0 ...
 ... entry ends at 0x4d94: u32 74 4d 00 00 (=L), then entry 1's marker at 0x4d98.
```

## 5. Confidence summary

| claim | confidence |
|---|---|
| Envelope: 8-byte per-stream-type prefix, gzip, end signature `00 00 ff ff 02 0c 00`, crc32/isize trailer, padding, footer | high (all 36 streams) |
| History layout (header, GUID slots, version list, 17-byte episodes, terminator) | high (6/6 files, exact length reconciliation) |
| History entry 0 = unique document GUID; entries newest→oldest; v1 timestamps; lineage sharing | high |
| Version list = upgrade history, 2662 = current format | high |
| History header GUID meaning; `0x28` tag byte | low (unknown) |
| CD = ordered GUID-keyed map, marker framing, monotonic keys, 100% coverage | high |
| CD entry = ADocument-shaped embedded document; ElementId at +0x58 = owner family element | medium-high |
| CD element-record table (40-byte layout, invariants) | high (fields A/B/C semantics: medium) |
| Content documents = loaded family/content documents | medium (strong circumstantial: view names, owner id, GUID cross-links) |
| Stale-trailer explanation; cause of the racadv/dach deflate hole; anomalous-entry overlays | low-medium (documented as unknowns) |

## 6. Unknowns

1. **Footer blob** after the trailer padding (37–350 B per stream). Not
   deflate; per-stream, per-file; History clusters at 91 B. Untouched.
2. **Cause of the mid-stream deflate hole** in racadv/dach CD and dach/rme
   ElemTable, and whether Revit reads through it. Also the meaning of the
   stale CRC/ISIZE (dach ISIZE 39.3 MB suggests ~29 MB of dach content
   documents live in the unreadable 5.2 MB compressed gap).
3. **Anomalous CD entries** with `0x45/0x7b/0x55/0xff` value overlays
   (racbasic 24/60, rstbasic 10/26; none in rme/rstadv/racadv/dach).
4. Class-tag → name mapping (0x0538 history, 0x03a3/0x03a2 entry tags,
   0x001c/0x05c9/0x03a7/0x01a0/0x1066/0x0ff8/0x0ae9 prologue tags, 0x0644 table
   tag) — needs the `Formats/Latest` class-id table (A2).
5. Semantics of the History header GUID slots and the constant `0x28` tag
   byte; whether `nver`'s list ends with a *per-episode* mapping.
6. Extended-entry internals beyond the first block (the multi-MB family
   payloads); the u32 `L` semantics for non-skeleton entries; the identity of
   `Latest`'s per-content-document 92–100 B summary records (A5).
7. Naming each content document: resolve `m_ownerFamilyId` ElementIds
   (1,018,036 …) against ElemTable/Partitions to get family names.

# INBOX from agent `elemtable` — out-of-slice findings

Reproducible with `src/rvt/elemtable.py` (runs on all six files).

## 1. Stream page-framing — independent corroboration of `cross-file.md`

Same result as agent `cross-file`, reached independently from the ElemTable
slice: every raw OLE stream is stored in pages of **65,249 bytes =
64,896 (0xFD80) payload + 353-byte per-page block** counted from stream
offset 0 (the 8-byte `Global/*` prefix included). Strip the 353-byte blocks
before inflating and **every gzip trailer validates (CRC32 + ISIZE)** — the
"corrupt trailer / trailing junk" gotcha in `KNOWLEDGE.md` is an artifact.
ElemTable-specific proof:

* dach `Global/ElemTable` (296,563 B, 5 pages, gaps @ 64,896 / 130,145 /
  195,394 / 260,643) and rme `Global/ElemTable` (151,224 B, 3 pages), which
  do not inflate at all as extracted (`invalid block type` / `invalid code
  lengths set`), inflate to CRC-valid 1,991,070 B / 1,125,310 B once
  de-framed.
* racadv/rstadv/rstbasic ElemTables previously "inflated" but with ISIZE
  overshoot (692,342 vs true 689,270; 557,043 vs 554,230; 560,017 vs
  557,470) — the excess was LZ desync garbage after raw offset 64,896.
* Payload sizes now hit `6 + 40*count + 24` exactly in all six files.

So `extracted/*/Global__ElemTable.gz/000.bin` is corrupt for every file
except racbasic (whose stream fits in one page). Same for `Formats/Latest`
(true 496,597 B), so **the schema regions past ~139 KB inflated were garbage
in the old corpus** — the `ElemRec`/`ElemTable`/`GraveyardRec`/`Episode`
class definitions used below are only readable in the de-framed schema.

## 2. Cross-stream links found while decoding (for the partitions / history / schema agents)

* **`Partitions/<N>` binary header, u32 at bytes 14–17 == ElemTable record
  count** in all six files (dach 49,776; racadv 17,231; racbasic 8,401; rme
  28,132; rstadv 13,855; rstbasic 13,936). Header shape:
  `09 00 00 00 | 00 00 00 00 | a3 03 00 00 | 00 00 | <u32 elem count> | 28 0f 04 00 | ...`
  (`a3 03` and `28 0f 04 00` constant). dach's `Partitions/85` has count 0.
* **`Global/History` u32 at inflated offset 14 == max(ElemRec.m_lastModificationDate)+1**
  (racbasic 848, racadv 617, rme 796, rstadv 579, rstbasic 1017, dach 2740)
  — it is the **episode (version) list**; the 16-byte repeating entries after
  it are episode GUIDs. The u32 fields inside every ElemRec are `EpisodeId`
  indices into this list.
* Schema evidence (de-framed `Formats/Latest`): serialized objects/streams
  start with a **u16 schema class index** (`Global/ElemTable` = 0x05c9 =
  `ElemTable`; `Global/DocumentIncrementTable` starts 0x053c; `Global/History`
  starts 0x0538). In field type codes `0e <flags> 00 00 <u16 class>` the
  0x8000 bit on the class marks an **inline (first-use) class definition**
  (e.g. `m_graveyardRecs 0e 50 00 00 ca 85` immediately followed by the
  `GraveyardRec` definition ⇒ GraveyardRec = 0x05ca; `ElementHistory`
  declared as `a5 83` ⇒ 0x03a5; `PartitionId` `8f 85` ⇒ 0x058f). Top-level
  class definitions are otherwise index-implicit (sequential): `ElemRec`
  (0x05c5) → 3 classes → `ElemTable` (0x05c9). Flag byte `0x50` after `0e`
  = array/vector of the class; `0x14` = raw `ElementId` (u64).

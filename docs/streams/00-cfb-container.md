# 00 — The container: OLE2 / Compound File Binary (CFB)

Slice: the outermost layer of a `.rvt` — the Microsoft Compound File Binary
container that every stream (`BasicFileInfo`, `Global/*`, `Partitions/N`, …)
lives inside. This section (1) records the exact CFB parameters of the six
Revit 2026 samples, (2) documents our pure-Python **writer**
(`src/rvt/cfb_writer.py`) and **round-trip harness**
(`src/rvt/roundtrip.py`), and (3) states precisely what a round trip
preserves, what legitimately differs, and which independent readers accept
the output.

Normative reference: **[MS-CFB] Compound File Binary File Format v12.0**
(Microsoft Open Specifications, 2024-04-23). Section numbers below (e.g.
`[2.2]`) cite that document. Reader used for extraction: `olefile 0.47`.
Independent verification reader: `compoundfiles 0.3`.

Reproduce everything here:

```bash
P=/Users/ck/dev/things/rev-revit
PYTHONPATH=$P/src $P/.venv/bin/python -m rvt.roundtrip --params $P/samples/rstbasicsampleproject.rvt
PYTHONPATH=$P/src $P/.venv/bin/python -m rvt.roundtrip \
    $P/samples/rstbasicsampleproject.rvt $P/experiments/roundtrip/rstbasicsampleproject.rvt \
    --verify --byte-report
$P/.venv/bin/python -m pytest $P/tests/test_roundtrip.py -v -s
```

---

## 1. Sample CFB parameters (all six)

Every sample is a **version-4 compound file: 4,096-byte sectors**, 64-byte
mini sectors, mini-stream cutoff 4,096 — including the 6.7 MB
`rstbasicsampleproject`. So v4 is not "forced by the 139 MB file"; Revit 2026
simply always writes v4. (139 MB is far below the 2 GB v3 ceiling `[2.9]`,
and even the 139 MB file needs no DIFAT sectors: its 34 FAT sectors fit in
the header's 109-slot DIFAT array `[2.2]`. A v4 file only needs DIFAT
sectors once it exceeds 109 FAT sectors × 1,024 entries × 4,096 B ≈ 457 MB;
a v3 file already at 109 × 128 × 512 B ≈ 6.9 MB.)

| sample | file size | sectors¹ | ver | sector / mini | FAT sect | DIFAT | dir sect | miniFAT sect | mini stream | entries |
|---|---:|---:|:--:|:--:|:--:|:--:|:--:|:--:|---:|:--:|
| rstbasicsampleproject | 6,672,384 | 1,628 | 4 | 4096 / 64 | 2 | 0 | 1 | 1 | 8,640 B | 16 |
| racbasicsampleproject | 19,759,104 | 4,823 | 4 | 4096 / 64 | 5 | 0 | 1 | 1 | 7,168 B | 17 |
| racadvancedsampleproject | 17,088,512 | 4,171 | 4 | 4096 / 64 | 5 | 0 | 1 | 1 | 10,368 B | 17 |
| rmebasicsampleproject | 32,653,312 | 7,971 | 4 | 4096 / 64 | 8 | 0 | 1 | 1 | 9,536 B | 17 |
| rstadvancedsampleproject | 15,069,184 | 3,678 | 4 | 4096 / 64 | 4 | 0 | 1 | 1 | 6,720 B | 17 |
| dach-sample-project | 138,977,280 | 33,929 | 4 | 4096 / 64 | 34 | 0 | 1 | 1 | 10,496 B | 18 |

¹ sectors after the 4,096-byte header; file size = (sectors + 1) × 4096
exactly for every sample (no trailing partial sector, no free sectors).

Header constants identical in all six: signature `D0 CF 11 E0 A1 B1 1A E1`,
header CLSID all-zero, minor version `0x003E`, byte order `0xFFFE`,
transaction signature `0`, mini-stream cutoff `0x1000`,
`FirstDIFATSectorLocation = ENDOFCHAIN (0xFFFFFFFE)`, `NumDIFATSectors = 0`,
directory chain always exactly one sector starting at sector 1, mini FAT
one sector at sector 2, FAT sector #0 at sector 0. **Confidence: certain**
(read directly from all six headers).

Metadata invariants across all six (confidence: certain):

- **Every CLSID is CLSID_NULL** (root, storages and streams). Revit does not
  brand the container with a class GUID.
- **Every state-bits (dwUserFlags) field is 0.**
- **Stream entries carry no timestamps** (creation = modified = 0), exactly
  as `[2.6.1]` requires.
- **The root entry has creation time 0** (`[2.6.2]` MUST) and a **non-zero
  modified time** (the save time). The three storages `Formats`, `Global`,
  `Partitions` carry both creation and modified FILETIMEs (a few seconds
  apart — the order in which Revit created them during the save).
- Streams < 4,096 bytes live in the mini stream, ≥ 4,096 in regular sectors
  — the plain `[2.6.3]` cutoff rule, no exceptions. (`RevitPreview4.0` and
  `TransmissionData` fall on either side depending on the file.)

---

## 2. Directory order and per-entry metadata

The directory (stream-ID order) is what our writer preserves verbatim. It
is stable in *shape* across samples: root, `Formats`, [`RevitPreview4.0`],
`Global`, `Partitions`, `Contents`, `TransmissionData`, `BasicFileInfo`,
`ProjectInformation`, `Partitions/<N>`, then the `Global/*` streams
(`DocumentIncrementTable`, `History`, `PartitionTable`, `ContentDocuments`,
`ElemTable`, `Latest`), then `Formats/Latest`, and — dach only — a second
partition stream `Partitions/85` last. i.e. Revit creates the four storages
first, then fills the root, then `Partitions/`, then `Global/`, then
`Formats/`. `rstbasicsampleproject` lacks `RevitPreview4.0` (16 entries);
`dach-sample-project` has two partition streams (18 entries); the rest have
17.

Legend for the tables: `in` = where the stream's bytes live (`mini` = mini
stream, `FAT` = regular sectors); `color`/`L`/`R`/`C` = the red-black colour
and left-sibling / right-sibling / child stream-IDs as written by Revit's
writer (informational — we regenerate these); times are FILETIME→UTC.
All CLSIDs null, all state bits 0 (columns omitted).

### rstbasicsampleproject (16 entries)

| sid | type | path | size | in | color | L | R | C | ctime (UTC) | mtime (UTC) |
|--:|---|---|--:|:-:|:-:|:-:|:-:|:-:|---|---|
| 0 | root | Root Entry | 8,640 | – | red | – | – | 1 | 0 | 2025-03-13 14:26:44 |
| 1 | storage | Formats | 0 | – | black | 2 | 3 | 15 | 2025-03-13 14:26:42 | 2025-03-13 14:26:44 |
| 2 | storage | Global | 0 | – | black | – | – | 11 | 2025-03-13 14:26:43 | 2025-03-13 14:26:43 |
| 3 | storage | Partitions | 0 | – | red | 4 | 5 | 8 | 2025-03-13 14:26:43 | 2025-03-13 14:26:44 |
| 4 | stream | Contents | 212 | mini | black | – | – | – | 0 | 0 |
| 5 | stream | TransmissionData | 3,838 | mini | black | 6 | 7 | – | 0 | 0 |
| 6 | stream | BasicFileInfo | 2,171 | mini | red | – | – | – | 0 | 0 |
| 7 | stream | ProjectInformation | 969 | mini | red | – | – | – | 0 | 0 |
| 8 | stream | Partitions/21 | 6,003,729 | FAT | black | – | – | – | 0 | 0 |
| 9 | stream | Global/DocumentIncrementTable | 1,096 | mini | black | 12 | – | – | 0 | 0 |
| 10 | stream | Global/History | 17,144 | FAT | black | 14 | 13 | – | 0 | 0 |
| 11 | stream | Global/PartitionTable | 134 | mini | black | 10 | 9 | – | 0 | 0 |
| 12 | stream | Global/ContentDocuments | 224,661 | FAT | red | – | – | – | 0 | 0 |
| 13 | stream | Global/ElemTable | 72,440 | FAT | red | – | – | – | 0 | 0 |
| 14 | stream | Global/Latest | 129,986 | FAT | red | – | – | – | 0 | 0 |
| 15 | stream | Formats/Latest | 182,953 | FAT | black | – | – | – | 0 | 0 |

### racbasicsampleproject (17)

| sid | type | path | size | in | color | L | R | C | ctime (UTC) | mtime (UTC) |
|--:|---|---|--:|:-:|:-:|:-:|:-:|:-:|---|---|
| 0 | root | Root Entry | 7,168 | – | red | – | – | 4 | 0 | 2025-03-13 14:20:34 |
| 1 | storage | Formats | 0 | – | red | 3 | 5 | 16 | 2025-03-13 14:20:28 | 2025-03-13 14:20:34 |
| 2 | stream | RevitPreview4.0 | 12,469 | FAT | red | 7 | 6 | – | 0 | 0 |
| 3 | storage | Global | 0 | – | black | – | – | 12 | 2025-03-13 14:20:30 | 2025-03-13 14:20:31 |
| 4 | storage | Partitions | 0 | – | black | 1 | 2 | 9 | 2025-03-13 14:20:31 | 2025-03-13 14:20:34 |
| 5 | stream | Contents | 212 | mini | black | – | – | – | 0 | 0 |
| 6 | stream | TransmissionData | 2,620 | mini | black | – | 8 | – | 0 | 0 |
| 7 | stream | BasicFileInfo | 2,171 | mini | black | – | – | – | 0 | 0 |
| 8 | stream | ProjectInformation | 1,001 | mini | red | – | – | – | 0 | 0 |
| 9 | stream | Partitions/15 | 18,508,710 | FAT | black | – | – | – | 0 | 0 |
| 10 | stream | Global/DocumentIncrementTable | 862 | mini | black | 13 | – | – | 0 | 0 |
| 11 | stream | Global/History | 14,146 | FAT | black | 15 | 14 | – | 0 | 0 |
| 12 | stream | Global/PartitionTable | 134 | mini | black | 11 | 10 | – | 0 | 0 |
| 13 | stream | Global/ContentDocuments | 818,555 | FAT | red | – | – | – | 0 | 0 |
| 14 | stream | Global/ElemTable | 50,408 | FAT | red | – | – | – | 0 | 0 |
| 15 | stream | Global/Latest | 117,192 | FAT | red | – | – | – | 0 | 0 |
| 16 | stream | Formats/Latest | 182,953 | FAT | black | – | – | – | 0 | 0 |

### racadvancedsampleproject (17)

| sid | type | path | size | in | color | L | R | C | ctime (UTC) | mtime (UTC) |
|--:|---|---|--:|:-:|:-:|:-:|:-:|:-:|---|---|
| 0 | root | Root Entry | 10,368 | – | red | – | – | 4 | 0 | 2025-03-13 14:19:10 |
| 1 | storage | Formats | 0 | – | red | 3 | 5 | 16 | 2025-03-13 14:19:05 | 2025-03-13 14:19:10 |
| 2 | stream | RevitPreview4.0 | 2,165 | mini | red | 7 | 6 | – | 0 | 0 |
| 3 | storage | Global | 0 | – | black | – | – | 12 | 2025-03-13 14:19:07 | 2025-03-13 14:19:07 |
| 4 | storage | Partitions | 0 | – | black | 1 | 2 | 9 | 2025-03-13 14:19:07 | 2025-03-13 14:19:10 |
| 5 | stream | Contents | 212 | mini | black | – | – | – | 0 | 0 |
| 6 | stream | TransmissionData | 3,802 | mini | black | – | 8 | – | 0 | 0 |
| 7 | stream | BasicFileInfo | 2,183 | mini | black | – | – | – | 0 | 0 |
| 8 | stream | ProjectInformation | 924 | mini | red | – | – | – | 0 | 0 |
| 9 | stream | Partitions/13 | 16,155,652 | FAT | black | – | – | – | 0 | 0 |
| 10 | stream | Global/DocumentIncrementTable | 683 | mini | black | 13 | – | – | 0 | 0 |
| 11 | stream | Global/History | 10,214 | FAT | black | 15 | 14 | – | 0 | 0 |
| 12 | stream | Global/PartitionTable | 179 | mini | black | 11 | 10 | – | 0 | 0 |
| 13 | stream | Global/ContentDocuments | 470,605 | FAT | red | – | – | – | 0 | 0 |
| 14 | stream | Global/ElemTable | 92,628 | FAT | red | – | – | – | 0 | 0 |
| 15 | stream | Global/Latest | 119,239 | FAT | red | – | – | – | 0 | 0 |
| 16 | stream | Formats/Latest | 182,953 | FAT | black | – | – | – | 0 | 0 |

### rmebasicsampleproject (17)

| sid | type | path | size | in | color | L | R | C | ctime (UTC) | mtime (UTC) |
|--:|---|---|--:|:-:|:-:|:-:|:-:|:-:|---|---|
| 0 | root | Root Entry | 9,536 | – | red | – | – | 4 | 0 | 2025-03-13 14:24:17 |
| 1 | storage | Formats | 0 | – | red | 3 | 5 | 16 | 2025-03-13 14:24:07 | 2025-03-13 14:24:17 |
| 2 | stream | RevitPreview4.0 | 2,444 | mini | red | 7 | 6 | – | 0 | 0 |
| 3 | storage | Global | 0 | – | black | – | – | 12 | 2025-03-13 14:24:11 | 2025-03-13 14:24:11 |
| 4 | storage | Partitions | 0 | – | black | 1 | 2 | 9 | 2025-03-13 14:24:11 | 2025-03-13 14:24:17 |
| 5 | stream | Contents | 212 | mini | black | – | – | – | 0 | 0 |
| 6 | stream | TransmissionData | 2,618 | mini | black | – | 8 | – | 0 | 0 |
| 7 | stream | BasicFileInfo | 2,171 | mini | black | – | – | – | 0 | 0 |
| 8 | stream | ProjectInformation | 923 | mini | red | – | – | – | 0 | 0 |
| 9 | stream | Partitions/14 | 30,581,311 | FAT | black | – | – | – | 0 | 0 |
| 10 | stream | Global/DocumentIncrementTable | 780 | mini | black | 13 | – | – | 0 | 0 |
| 11 | stream | Global/History | 13,195 | FAT | black | 15 | 14 | – | 0 | 0 |
| 12 | stream | Global/PartitionTable | 179 | mini | black | 11 | 10 | – | 0 | 0 |
| 13 | stream | Global/ContentDocuments | 1,316,957 | FAT | red | – | – | – | 0 | 0 |
| 14 | stream | Global/ElemTable | 151,224 | FAT | red | – | – | – | 0 | 0 |
| 15 | stream | Global/Latest | 338,295 | FAT | red | – | – | – | 0 | 0 |
| 16 | stream | Formats/Latest | 182,953 | FAT | black | – | – | – | 0 | 0 |

### rstadvancedsampleproject (17)

| sid | type | path | size | in | color | L | R | C | ctime (UTC) | mtime (UTC) |
|--:|---|---|--:|:-:|:-:|:-:|:-:|:-:|---|---|
| 0 | root | Root Entry | 6,720 | – | red | – | – | 4 | 0 | 2025-03-13 14:25:49 |
| 1 | storage | Formats | 0 | – | red | 3 | 5 | 16 | 2025-03-13 14:25:44 | 2025-03-13 14:25:49 |
| 2 | stream | RevitPreview4.0 | 2,206 | mini | red | 7 | 6 | – | 0 | 0 |
| 3 | storage | Global | 0 | – | black | – | – | 12 | 2025-03-13 14:25:46 | 2025-03-13 14:25:46 |
| 4 | storage | Partitions | 0 | – | black | 1 | 2 | 9 | 2025-03-13 14:25:46 | 2025-03-13 14:25:49 |
| 5 | stream | Contents | 236 | mini | black | – | – | – | 0 | 0 |
| 6 | stream | TransmissionData | 4,140 | FAT | black | – | 8 | – | 0 | 0 |
| 7 | stream | BasicFileInfo | 2,183 | mini | black | – | – | – | 0 | 0 |
| 8 | stream | ProjectInformation | 972 | mini | red | – | – | – | 0 | 0 |
| 9 | stream | Partitions/12 | 13,989,130 | FAT | black | – | – | – | 0 | 0 |
| 10 | stream | Global/DocumentIncrementTable | 707 | mini | black | 13 | – | – | 0 | 0 |
| 11 | stream | Global/History | 10,246 | FAT | black | 15 | 14 | – | 0 | 0 |
| 12 | stream | Global/PartitionTable | 155 | mini | black | 11 | 10 | – | 0 | 0 |
| 13 | stream | Global/ContentDocuments | 624,855 | FAT | red | – | – | – | 0 | 0 |
| 14 | stream | Global/ElemTable | 75,341 | FAT | red | – | – | – | 0 | 0 |
| 15 | stream | Global/Latest | 127,427 | FAT | red | – | – | – | 0 | 0 |
| 16 | stream | Formats/Latest | 182,953 | FAT | black | – | – | – | 0 | 0 |

### dach-sample-project (18)

| sid | type | path | size | in | color | L | R | C | ctime (UTC) | mtime (UTC) |
|--:|---|---|--:|:-:|:-:|:-:|:-:|:-:|---|---|
| 0 | root | Root Entry | 10,496 | – | red | – | – | 5 | 0 | 2025-03-13 14:12:51 |
| 1 | storage | Formats | 0 | – | black | 3 | – | 16 | 2025-03-13 12:58:45 | 2025-03-13 13:08:34 |
| 2 | stream | RevitPreview4.0 | 12,912 | FAT | red | 7 | 6 | – | 0 | 0 |
| 3 | storage | Global | 0 | – | black | – | – | 11 | 2025-03-13 13:03:20 | 2025-03-13 14:12:51 |
| 4 | storage | Partitions | 0 | – | black | – | 2 | 9 | 2025-03-13 13:03:38 | 2025-03-13 14:12:51 |
| 5 | stream | Contents | 220 | mini | black | 1 | 4 | – | 0 | 0 |
| 6 | stream | TransmissionData | 4,272 | FAT | black | – | 8 | – | 0 | 0 |
| 7 | stream | BasicFileInfo | 2,155 | mini | black | – | – | – | 0 | 0 |
| 8 | stream | ProjectInformation | 3,533 | mini | red | – | – | – | 0 | 0 |
| 9 | stream | Partitions/84 | 129,113,442 | FAT | black | – | 17 | – | 0 | 0 |
| 10 | stream | Global/DocumentIncrementTable | 3,949 | mini | red | 12 | – | – | 0 | 0 |
| 11 | stream | Global/History | 46,314 | FAT | black | 15 | 10 | – | 0 | 0 |
| 12 | stream | Global/PartitionTable | 145 | mini | black | 14 | 13 | – | 0 | 0 |
| 13 | stream | Global/ContentDocuments | 7,146,173 | FAT | red | – | – | – | 0 | 0 |
| 14 | stream | Global/ElemTable | 296,563 | FAT | red | – | – | – | 0 | 0 |
| 15 | stream | Global/Latest | 1,990,990 | FAT | red | – | – | – | 0 | 0 |
| 16 | stream | Formats/Latest | 182,953 | FAT | black | – | – | – | 0 | 0 |
| 17 | stream | Partitions/85 | 291 | mini | red | – | – | – | 0 | 0 |

(`Formats/Latest` is 182,953 bytes in every file — the per-release schema
blob; the dach `Formats` storage timestamps predate the others by ~70 min,
i.e. that project was created earlier and re-saved.)

---

## 3. Layout tables and worked hex examples

### 3.1 The header `[2.2]` — first 512 bytes, sector "-1"

| offset | size | field | Revit 2026 value | evidence |
|--:|--:|---|---|---|
| 0x00 | 8 | Header Signature | `D0 CF 11 E0 A1 B1 1A E1` (MUST) | all six |
| 0x08 | 16 | Header CLSID | all zero (MUST) | all six |
| 0x18 | 2 | Minor Version | `3E 00` (SHOULD 0x003E) | all six |
| 0x1A | 2 | Major Version | `04 00` → v4 | all six |
| 0x1C | 2 | Byte Order | `FE FF` = 0xFFFE (MUST) | all six |
| 0x1E | 2 | Sector Shift | `0C 00` → 4,096-byte sectors (MUST for v4) | all six |
| 0x20 | 2 | Mini Sector Shift | `06 00` → 64 (MUST) | all six |
| 0x22 | 6 | Reserved | zero (MUST) | all six |
| 0x28 | 4 | Number of Directory Sectors | `01 00 00 00` (v4 field; MUST be 0 in v3) | all six |
| 0x2C | 4 | Number of FAT Sectors | 2 … 34 (see §1) | header |
| 0x30 | 4 | First Directory Sector Location | 1 | all six |
| 0x34 | 4 | Transaction Signature | 0 (transactions not used) | all six |
| 0x38 | 4 | Mini Stream Cutoff | `00 10 00 00` = 0x1000 (MUST) | all six |
| 0x3C | 4 | First Mini FAT Sector Location | 2 | all six |
| 0x40 | 4 | Number of Mini FAT Sectors | 1 | all six |
| 0x44 | 4 | First DIFAT Sector Location | `FE FF FF FF` (ENDOFCHAIN — none) | all six |
| 0x48 | 4 | Number of DIFAT Sectors | 0 | all six |
| 0x4C | 436 | DIFAT[0..108] | FAT sector numbers, unused = `FF FF FF FF` | header |
| 0x200 | 3,584 | v4 zero fill to 4,096 (MUST) | zero | all six |

Worked example — `rstbasicsampleproject.rvt` bytes 0x00–0x5F:

```
00000000: d0cf 11e0 a1b1 1ae1 0000 0000 0000 0000  signature | CLSID null
00000010: 0000 0000 0000 0000 3e00 0400 feff 0c00  ...       | minor 3E, major 4, FFFE, shift 0C
00000020: 0600 0000 0000 0000 0100 0000 0200 0000  minishift 6, reserved | csectDir=1, csectFat=2
00000030: 0100 0000 0000 0000 0010 0000 0200 0000  sectDirStart=1, txsig=0, cutoff=0x1000, sectMiniFatStart=2
00000040: 0100 0000 feff ffff 0000 0000 0000 0000  csectMiniFat=1, sectDifStart=ENDOFCHAIN, csectDif=0, DIFAT[0]=0
00000050: 3200 0000 ffff ffff ffff ffff ffff ffff  DIFAT[1]=0x32 (50), DIFAT[2..]=FREESECT
```

Note DIFAT[1] = **sector 50**: Windows' Structured Storage grows the FAT lazily,
so FAT sector #2 sits in the middle of the data (see §4.1).

Sector *N* starts at file offset `(N + 1) × 4096` `[2.3]`. The FAT sector at
sector 0 (file offset 0x1000) begins `FDFFFFFF FEFFFFFF FEFFFFFF 04000000 …`:
sector 0 = FATSECT, sector 1 (directory) = ENDOFCHAIN, sector 2 (mini FAT)
= ENDOFCHAIN, sector 3 → 4 → 1627 → ENDOFCHAIN (the mini stream chain).

### 3.2 Directory entries `[2.6.1]` — 128 bytes each, 32 per v4 sector

| offset | size | field | notes |
|--:|--:|---|---|
| 0x00 | 64 | Directory Entry Name | UTF-16LE, NUL-terminated, ≤ 31 chars; `/ \ : !` illegal |
| 0x40 | 2 | Name Length | bytes incl. terminating NUL (e.g. "Root Entry" → 0x16 = 22) |
| 0x42 | 1 | Object Type | 0x00 unallocated · 0x01 storage · 0x02 stream · 0x05 root |
| 0x43 | 1 | Color | 0x00 red · 0x01 black |
| 0x44 | 4 | Left Sibling ID | NOSTREAM = 0xFFFFFFFF when none |
| 0x48 | 4 | Right Sibling ID | NOSTREAM when none |
| 0x4C | 4 | Child ID | root of the storage's sibling tree; NOSTREAM for streams |
| 0x50 | 16 | CLSID | null in every Revit sample |
| 0x60 | 4 | State Bits | 0 in every Revit sample |
| 0x64 | 8 | Creation Time (FILETIME) | storages only; root & streams = 0 |
| 0x6C | 8 | Modified Time (FILETIME) | root + storages; streams = 0 |
| 0x74 | 4 | Starting Sector | first sector (regular) or first **mini** sector (< cutoff) |
| 0x78 | 8 | Stream Size | full 64-bit in v4; for the root = mini-stream size |

Worked example — the root entry of `rstbasicsampleproject.rvt` (sector 1, file
offset 0x2000):

```
00002000: 5200 6f00 6f00 7400 2000 4500 6e00 7400  "Root Entry" UTF-16LE
00002010: 7200 7900 0000 ...                        (zero-padded to 64 bytes)
00002040: 1600 0500 ffff ffff ffff ffff 0100 0000  namelen 0x16, type 05 root, colour 00 red,
                                                   L=NOSTREAM, R=NOSTREAM, C=1 (Formats)
00002050: 0000 ....                                 CLSID null
00002060: 0000 0000 | 0000 0000 0000 0000 | 008d 09f2  state 0 | ctime 0 | mtime (lo)
00002070: 2394 db01 | 0300 0000 | c021 0000 0000 0000    mtime (hi) | start=3 | size=0x21C0=8,640
```

Free entries after the last used slot (16 of 32 in this file) are exactly as
`[2.6.3]` prescribes: 128 zero bytes except Left/Right/Child = NOSTREAM —
verified in every sample and reproduced by the writer.

---

## 4. What Revit's own writer does (informational; we do NOT copy this)

These are properties of Windows' Structured Storage implementation, not
requirements. They explain why a byte-identical round trip is not achievable
without emulating STG's allocation history — and why it does not matter.

**4.1 Sector allocation is interleaved / append-order.** FAT sectors are
allocated on demand and land wherever the file was growing at the time:
rstbasic FAT sectors at [0, 50]; racbasic [0, 54–57]; racadvanced
[0, 51–53, 4052]; rme [0, 51–57]; rstadvanced [0, 52–54]; dach
[0, 56–85, 31608, 32166, 32167]. Streams are scattered in write order; the
mini stream itself is fragmented (rstbasic chain 3→4→1627, dach 3→4→33928,
rstadvanced 3→6). No sample contains any FREESECT within the file range —
Revit's save produced a fully compacted allocation.

**4.2 The red-black trees are real insertion-order RB trees** (mix of red and
black nodes, e.g. rstbasic: `Formats`(black) left→`Global`(black),
right→`Partitions`(red), whose children `Contents`/`TransmissionData` are
black, whose children `BasicFileInfo`/`ProjectInformation` are red). Ordering
key confirmed to be `[2.6.4]` length-then-uppercase: "Global"(6) <
"Formats"(7) < "Contents"(8) < "Partitions"(10) < "BasicFileInfo"(13) <
"TransmissionData"(16) < "ProjectInformation"(18).

**4.3 Slack bytes are NOT zeroed.** The unused tail of a stream's last sector
(and of the mini-stream sectors) carries left-over buffer garbage — e.g.
`Formats/Latest` ends with 1,367 slack bytes `ff ff ff ff …` in rstbasic and
`06 00 00 ac 06 00 00 ad …` in the RAC/RME/RST-advanced files; `Partitions/21`
carries `0a a7 9c 38 ad c5 71 ef …`; rstadvanced `TransmissionData` slack even
holds UTF-16 XML fragments (`<?xml versi…`). `[2.7]` says the unused portion
"SHOULD be filled with zeroes to avoid leaking unintended information";
Revit/STG does not. **These bytes are outside every stream and are never seen
by any reader** — they only defeat byte-for-byte identity.

**4.4 Mini-stream packing order** is creation order, not directory order
(rstbasic mini starts: `ProjectInformation` 0, `BasicFileInfo` 16,
`TransmissionData` 50, `Contents` 110, `PartitionTable` 114,
`DocumentIncrementTable` 117 — × 64-byte mini sectors).

---

## 5. The writer: `write_cfb(path, entries)`

`entries` is an ordered list of `CfbEntry(path, entry_type, data, clsid,
state_bits, ctime, mtime)`; `entries[0]` is the root; the **list index is
the stream ID**, so directory order round-trips exactly. Algorithm (all
`[MS-CFB]`-cited in the source):

1. Validate names (≤ 31 UTF-16 units, no `/ \ : !`), the storage hierarchy
   and per-storage uniqueness under the `[2.6.4]` uppercase key.
2. Streams `< 4096` B → mini stream in list order, each padded to 64 B; mini
   FAT chains built alongside (`[2.4]`). Empty streams and (if no mini
   streams) the root get `Starting Sector = ENDOFCHAIN`.
3. Solve the FAT/DIFAT fixed point (`[2.3]`, `[2.5]`): the FAT must map its own
   sectors (FATSECT), DIFAT sectors (DIFSECT), the directory chain, mini-FAT
   chain, mini-stream chain and every regular stream chain; entries past
   end-of-file are FREESECT. DIFAT sectors appear only past 109 FAT sectors
   (exercised by the v3 synthetic test — never needed by the six samples).
4. Deterministic contiguous layout: `[header][FAT×F][DIFAT×X][DIR][miniFAT]
   [mini stream][each regular stream, in directory order]`.
5. Per-storage sibling trees: children sorted by the CFB key, laid out as a
   **balanced, all-black binary search tree** — explicitly sanctioned by
   `[2.6.4]` ("the simplest implementation … would be to mark every node as
   black"). Root, storages and streams all colour black.
6. Free directory slots per `[2.6.3]`; slack zero-filled per `[2.7]`; v4
   header zero-padded to 4,096 per `[2.2]`.

`python -m rvt.roundtrip in.rvt out.rvt [--verify] [--byte-report]` reads
every entry (stream-ID order, storage tree, CLSID, state bits, FILETIMEs,
bytes) via `olefile` and re-emits it via the writer.

### Preserved by a round trip (asserted by `--verify` / the test suite)

| item | preserved | how |
|---|:-:|---|
| directory **order** (stream IDs) and count | yes | list order = stream ID |
| storage tree (`Formats/`, `Global/`, `Partitions/`) | yes | full paths |
| every stream's **bytes** | yes | sha256-compared |
| CLSIDs (all null here) | yes | GUID string ↔ 16-byte round trip |
| state bits | yes | copied |
| creation / modified FILETIMEs (root, storages) | yes | raw uint64 copied |
| CFB major version, sector & mini-sector size, cutoff | yes | v4 / 4096 / 64 / 0x1000 |
| mini-vs-regular placement of each stream | yes | same cutoff rule ⇒ same sets |
| entry count / dir sectors / mini-stream size / FAT count / **file size** | yes for all six² | falls out of the geometry |

² Not guaranteed in general, but true for every sample: same sector count and
therefore an **identical file size** to the byte (Revit's save left no free
sectors, and our layout has the same content-sector total; FAT-sector counts
also coincide).

### Legitimately different (why byte-identical is NO)

Category → cause (all confirmed by `--byte-report` on all six):

- **sector layout** — we emit contiguous chains, FAT sectors first; STG
  interleaves (see §4.1). Every `Starting Sector` differs; the header's
  `First Directory / Mini FAT Sector` differ (ours: dir after the FAT block,
  originals: dir at 1, mini FAT at 2, FAT#1+ mid-file).
- **directory tree** — balanced all-black BSTs vs. STG's insertion-order
  red-black trees (colours and L/R/C links differ; the *names, order and
  containment* are identical).
- **padding / slack** — we zero-fill slack (`[2.7]` SHOULD); originals leak
  garbage (§4.3). This alone makes byte identity impossible without copying
  meaningless bytes.

No other category ever fires: no timestamp, CLSID, state-bit, size, count or
header-constant differences.

---

## 6. Reader compatibility (confirmed)

All six round-tripped outputs (`experiments/roundtrip/*.rvt`) are accepted,
with **zero warnings/defects**, by:

- `olefile 0.47` opened with `raise_defects=DEFECT_INCORRECT` (strict) —
  identical tree, sizes, mini/regular classification, CLSIDs, timestamps.
- `compoundfiles 0.3` (independent implementation, warns on any FAT/DIFAT/
  header/directory irregularity) — no warnings; identical tree and sizes.
- Both readers also accept the synthetic edge cases: DIFAT-bearing v3 file,
  empty streams, no-mini-stream file, 72-entry / 3-directory-sector file.

Revit itself reads `.rvt` through the standard Windows Structured Storage
API, which accepts any spec-conformant layout; container-level differences
(layout, tree shape, slack) are invisible above the container. Actual
open-in-Revit acceptance is untested here (needs Windows/Revit or APS) —
that is a question about the *stream contents*, not this container layer.

Timing (Apple Silicon, warm cache, includes verify): rstbasic 0.03 s,
racbasic 0.05 s, racadvanced 0.04 s, rme 0.07 s, rstadvanced 0.04 s,
**dach (139 MB) 0.30 s** — the "slow" marker is precautionary only.

---

## 7. Confidence and unknowns

Certain (verified on all six + independent readers): every value in §1–§3,
the invariants (v4 always, null CLSIDs, zero state bits, stream timestamps
zero, root ctime zero), the mini/regular cutoff rule, reader acceptance of
the writer's output, and the reasons byte identity fails (§5).

Unknowns / open questions:

- Whether **Revit** requires anything beyond CFB validity of the container
  (e.g. specific stream order, or the `Formats`/`Global`/`Partitions`
  creation-time ordering) — untestable without Revit; the writer preserves
  order and timestamps anyway. `[hypothesis]` No: Revit uses the OS storage
  API and cannot even see layout or tree colouring.
- Whether Revit ever writes a **non-null root CLSID or state bits** in other
  files (worksharing-enabled central models, older versions). Not seen here.
- The **transaction signature** is always 0 in these single-user files;
  worksharing/central files were not sampled.
- We do not model the range-lock sector `[2.8]` (only relevant to files
  ≥ 2 GB) or v3 files > 2 GB; the writer raises for oversized v3 streams.
- Byte-identical output would require emulating STG's on-demand FAT growth,
  its RB insertion sequence and its slack garbage — deliberately out of
  scope (the bytes carry no information).

Out-of-scope observations go to `docs/inbox/cfb-writer.md`.

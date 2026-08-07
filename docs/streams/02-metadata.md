# 02 — Metadata streams

Decoded across all six Revit 2026 samples by `src/rvt/meta.py`
(`.venv/bin/python src/rvt/meta.py` dumps everything below for every
extracted project). This section covers the small, non-element streams:

| Stream | Size | What it is | Parser |
|---|---|---|---|
| `BasicFileInfo` | 2,155–2,183 B | packed binary record + UTF-16 "key: value" mirror | `parse_basic_file_info` |
| `Contents` | 212–236 B raw / 240–274 B inflated | class-stream wrapper → gzip → fixed-size "document contents" record | `parse_contents` |
| `TransmissionData` | 2.6–4.3 KB | u32 char count + UTF-16LE XML (external file refs) | `parse_transmission` |
| `ProjectInformation` | 920–3,533 B | ZIP archive, one member: Autodesk **PartAtom** Atom XML | `parse_project_info` |
| `RevitPreview4.0` | 2.1–12.9 KB (absent in rstbasic) | class-stream, uncompressed, embedded 128×128 PNG | `extract_preview` |
| `Global/DocumentIncrementTable` | 683–3,949 B raw / 2,976–22,378 B inflated | table of per-save increment records (×2 copies) | `parse_doc_increment` |

Conventions: little-endian; `ustr` = u32 UTF-16 character count followed by
UTF-16LE code units (no terminator); binary GUIDs use Windows mixed-endian
layout (`uuid.UUID(bytes_le=...)`). Offsets in worked examples are for
`racbasicsampleproject` unless noted.

---

## 1. `BasicFileInfo`

A **packed** binary record (no alignment padding), followed by an ASCII CRLF,
then a UTF-16LE human-readable mirror of the same fields, then a final ASCII
CRLF. Because the binary part contains single `u8` flags, the mirror text
begins at an odd byte offset (0x263 in racbasic) — which is why decoding the
whole stream as one UTF-16 string shows garbage in the middle. **Confidence:
high** — the parser consumes all six files with zero unaccounted bytes and
every binary field is confirmed by its mirror-text twin.

### Layout (racbasic offsets; sizes vary with string lengths)

| Off | Size | Type | Field | Value (racbasic) | Evidence |
|---|---|---|---|---|---|
| 0x000 | 4 | u32 | structure_version | 14 (all files) | constant across corpus [hypothesis: BFI struct version] |
| 0x004 | 2 | u16 | worksharing_state | 0 | mirror `Worksharing: Not enabled`; [hypothesis] enum, 10 zero bytes 0x04–0x0d in every sample |
| 0x006 | 4 | ustr | username | "" (len 0) | mirror `Username: ` |
| 0x00a | 4 | ustr | central_model_path | "" | mirror `Central Model Path: ` |
| 0x00e | 12 | ustr | format | "2026" | mirror `Format: 2026` |
| 0x01a | 40 | ustr | build | "20250227_1515(x64)" | mirror `Build:` |
| 0x042 | 4+2n | ustr | last_save_path | `C:\Users\hansonje\Desktop\Downloadable Files\racbasicsampleproject.rvt` | mirror `Last Save Path:` |
| 0x0d2 | 4 | u32 | open_workset_default | 3 | mirror `Open Workset Default: 3` |
| 0x0d6 | 1 | u8 | project_spark_file | 0 | mirror `Project Spark File: 0`; this u8 shifts everything after to odd offsets |
| 0x0d7 | 76 | ustr | central_model_identity | nil GUID | mirror |
| 0x123 | 10 | ustr | locale_when_saved | "ENU" | mirror `Locale when saved: ENU` |
| 0x12d | 1 | u8 | all_local_changes_saved_to_central | 0 | mirror |
| 0x12e | 4 | u32 | central_version_number | 16 | mirror; == "Unique Document Increments" |
| 0x132 | 76 | ustr | central_episode_guid | e6a03f8e-9e4e-4cfc-ae41-c3c559e42d55 | mirror `Central model's episode GUID corresponding to the last reload latest` |
| 0x17e | 76 | ustr | unique_document_guid | same GUID | mirror `Unique Document GUID` |
| 0x1ca | 8 | ustr | unique_document_increments | "16" (a string!) | mirror; equals `Global/DocumentIncrementTable` record count |
| 0x1d2 | 76 | ustr | model_identity | nil GUID | mirror `Model Identity` |
| 0x21e | 1 | u8 | is_single_user_cloud_model | 0 (False) | mirror |
| 0x21f | 32 | ustr | author | "Autodesk Revit" | mirror `Author:` |
| 0x23f | 36 | ustr | client_app_name | "RevitApplication" | mirror `ClientAppName:` |
| 0x263 | rest | `0D 0A` + UTF-16LE text + `0D 0A` | mirror_text | 19 `key: value` lines separated by UTF-16 CRLF | decodes cleanly in all six |

Per-file increments (BFI ↔ DIT record count): racbasic 16, racadvanced 14,
rme 15, rstbasic 22, rstadvanced 13, dach 86 — all match.

Worked bytes (racbasic 0x0d2): `03 00 00 00 | 00 | 24 00 00 00 30 00 30 00 ...`
= open_workset_default=3, project_spark_file=0, then the 36-char nil GUID
string whose length prefix sits at the odd offset 0x0d7.

## 2. `Contents`

### 2.1 Raw wrapper — the "class-stream" prologue

`Contents` and `RevitPreview4.0` share a 24-byte prologue opened by the
magic `62 19 22 05` (u32 `0x05221962`). **Confidence: high** on structure,
medium on semantics.

| Off | Size | Type | Field | racbasic | Notes |
|---|---|---|---|---|---|
| 0x00 | 4 | u32 | magic | 0x05221962 | all files |
| 0x04 | 4 | u32 | unknown_28 | 28 (0x1c) | constant [hypothesis: record-format version] |
| 0x08 | 4 | u32 | count | 1 | [hypothesis: number of serialized objects] |
| 0x0c | 4 | u32 | zero | 0 | |
| 0x10 | 4 | u32 | magic again | 0x05221962 | record start |
| 0x14 | 4 | u32 | class_ref | 183 (racadv 213, rme 424, rstbasic 178, rstadv 264, dach 430) | no `0x8000` flag → reference to an already-registered class index; varies per document [hypothesis: per-document dynamic class table]. In the Preview stream the same slot holds `0x800C` = "inline definition of class #12 follows". |
| 0x18 | var | gzip | payload | member with **valid** CRC32/ISIZE trailer | inflates to 240–274 B |
| after trailer | 2–5 zero bytes + 42 B | slack | high entropy, does not inflate | [hypothesis: stale bytes from an in-place rewrite; not part of the object] |

### 2.2 Inflated payload (240 B fixed + optional username)

The payload is a **fixed-size 240-byte record**; the only variable part is
the optional owner user name (+4+2n bytes: racadv/rme "A" → 246 B, rstadv
"Steven Campbell" → 274 B). **Confidence: high** for the tokenisation
(parser consumes to the zero fill in all six), low for field meanings.

| Rel | Type | Field | racbasic | dach | Notes |
|---|---|---|---|---|---|
| +0x00 | u16 | type_tag | 0x053E | 0x053E | cf. DIT payload tag 0x053C |
| +0x02 | u32 | has_username | 0 | 0 | 1 in racadv/rme/rstadv |
| … | ustr | username (if flag) | — | — | "A" / "A" / "Steven Campbell" [hypothesis: model owner / creator login] |
| … | u32,u32 | zeros | 0,0 | 0,0 | |
| … | ustr | partition_name | "GLOBAL" | "GLOBAL" | matches `Global/` stream namespace |
| … | 36 B | zero block | 0… | 0… | [hypothesis: two nil binary GUIDs + u32 0] |
| … | u32 | one | 1 | 1 | |
| … | 16 B | creation_guid (binary GUID) | e3e052f8-0156-11d5-9301-0000863f27ad | 20c8cdf4-7814-4cd6-bd38-8339fd18d1e2 | same GUID appears (binary) 80+ times in `Partitions/15` element data and in `Global/PartitionTable` → the document/partition creation GUID (base of element UniqueIds) |
| … | u16 | marker | 0xFFFF | 0xFFFF | 0x0000 in the three files that carry a username |
| … | u32 | zero | 0 | 0 | |
| … | u8 | zero | 0 | 0 | this u8 makes the build string land at odd offset 0x5D |
| 0x5D | ustr | build | "20250227_1515(x64)" | same | |
| +0 after build | u32×5 | unknown_hdr5 | (7, 0, 10, -1, 3) | (7, 76, 1, -1, 3) | others (7, 0, 3, -1, 3); `7` constant [hypothesis: sub-record version]; `-1, 3` constant |
| … | u8, u16 | 1, 0 | 1, 0 | 1, 0 | |
| … | i32[] until -1 | counters | 436,444,444,444,333,444,445,415,333 | 647,1972,1972,1972,1534,1972,1976,1796,1534 | = last DIT record's counters **with index 7 removed** |
| … | u32 | counter_g | 322 | 1526 | = last DIT record's `G` |
| … | (i32 −1, u16)×2 | trailing_pairs | (−1,1420), (−1,1426) | same | constant in all six [hypothesis: built-in ElementIds / sentinel ids] |
| … | 28 B | zero fill | 0… | 0… | pads record to 240 B |

The v1 (time-based, epoch ≈ 2001) GUID `e3e052f8-0156-11d5-9301-0000863f27ad`
is shared by racbasic, racadvanced, rme and rstbasic — those templates all
descend from one ancestor document; dach and rstadvanced have their own.

## 3. `TransmissionData`

| Off | Size | Type | Field |
|---|---|---|---|
| 0x00 | 4 | u32 | UTF-16 character count `n` (stream size = 4 + 2n, exact in all six) |
| 0x04 | 2n | UTF-16LE | XML document, no BOM, ends with `\r\n` |

**Confidence: high.** The XML is `<TransmissionData isTransmitted="false"
userData="" version="5">` with one `<ExternalFileReference>` per external
resource: `ElementId`, `ExternalFileReferenceType` (Keynote Table, Assembly
Code Table, Decal, Revit Link…), `LastSavedPath`, `LastSavedAbsolutePath`,
`LastSavedPathType`, `LastSavedLoadState`, `DesiredPath`, `DesiredPathType`,
`DesiredLoadState`. Reference counts: racbasic 2, rme 2, racadv 3 (incl. a
Decal jpg), rstbasic/rstadv/dach 3 (each with one `Revit Link`). This is the
same document the public `TransmissionData` API class edits, and the
`ElementId`s (e.g. keynote table 86291) cross-reference `Global/ElemTable`.

## 4. `ProjectInformation` (ZIP → PartAtom XML)

The stream is a complete **ZIP archive** (`PK\x03\x04`), one deflated member
named after a temp path:
`C:\Users\hansonje\AppData\Local\Temp\<guid>\Revit<guid>.project.xml`.
The member's DOS date/time fields are junk (years 1986–2069); `flag_bits=2`,
`create_system=0`, method 8. **Confidence: high.** This is where the legacy
`PartAtom` stream went: the XML root is an Atom `<entry>` with the
`urn:schemas-autodesk-com:partatom` (`A:`) namespace — the same schema Revit's
`Application.ExtractPartAtomFromFamilyFile` emits.

Mapping to Revit Project Information parameters:

| XML | Meaning |
|---|---|
| `<title>` / `A:design-file/A:title` | model title / file name |
| `<updated>` / `A:updated` | last save time (UTC) — 2025-03-13 for all six |
| `A:product`, `A:product-version` | "Revit", "2026" |
| `A:taxonomy` term/label | `adsk:revit`, `adsk:revit:grouping` |
| `A:features/A:feature/A:group` (`A:title` = parameter group) | Project Information parameter groups: Identity Data, IFC Parameters, Route Analysis, Other, Construction, Text… |
| child elements of a group | one element per parameter: tag = parameter name (`Project_Name`, `Client_Name`, `Project_Number`, `Project_Address`, `Project_Status`, `Project_Issue_Date`, `Author`, `Organization_Name`, `Building_Name`, `Design_Option`, or shared-parameter names), attributes `displayName`, `type` (`system`/`shared`), `id` (shared-parameter GUID), `typeOfParameter` (`Text`, `Multiline Text`), text = value |

Examples: racbasic → Project Name "Sample House", Number "001-00", Client
"Autodesk", Author "Samuel Macalister"; dach carries 10 shared parameters with
their GUIDs (`Bauherr`, `Baustellenort`, `PrintManagerSettings`, …).

## 5. `RevitPreview4.0`

Uncompressed class-stream: the shared 24-byte prologue (§2.1) with
`class_ref = 0x0000800C` (bit 15 = **inline class definition follows**),
then two class definitions in exactly the `Formats/Latest` record shape,
then one `ARasterImage` instance. Present in 5 of 6 files (rstbasic has no
preview). **Confidence: high** — the parser lands exactly on the stream end
in all five files.

| Off | Size | Type | Field | Value |
|---|---|---|---|---|
| 0x00–0x17 | 24 | prologue | see §2.1 | class_ref = 0x800C |
| 0x18 | 2+11 | u16 + ASCII | class name | `FilePreview` |
| 0x25 | 2 | u16 | 0 | |
| 0x27 | 4 | u32 | class version | 7 |
| 0x2b | 4 | u32 | field count | 1 |
| 0x2f | 4+9 | u32 + ASCII | field name | `m_pAImage` |
| 0x3c | 4+4+4 | type descriptor | `0E 01 00 00` (0x0E = object ref), u32 0, i32 −1 (target = next inline class) | |
| 0x48 | 4 | u32 | class_ref | 0x800D (define class 13) |
| 0x4c | 2+12 | u16 + ASCII | class name | `ARasterImage` (also present, v3/7 fields, in `Formats/Latest`) |
| 0x5a | 2, 4, 4 | u16 0, u32 version 3, u32 field count 7 | | |
| 0x64… | | 7 field records | `m_compressedImage` type `02 50 00 00` (byte + 0x50xx array flag), `m_dpiX`, `m_dpiY`, `m_widthInFeet`, `m_heightInFeet` type `07` (double), `m_width`, `m_height` type `04` (int32) | |
| 0xe3 | 4 | u32 | instance prologue | 0 [hypothesis] |
| 0xe7 | 4 | u32 | PNG byte length | 12194 (racbasic) |
| 0xeb | n | bytes | `m_compressedImage` = PNG (`89 50 4E 47`), 128×128 RGBA (IHDR), sRGB/gAMA/pHYs chunks | written to `extracted/<file>/preview.png` |
| 0xeb+n | 8×4 | f64 | m_dpiX, m_dpiY, m_widthInFeet, m_heightInFeet | 95.9866, 95.9866, 0.0, 0.0 |
| … | 4+4 | i32 | m_width, m_height | 128, 128 (== stream end) |

The image is Revit's shaded 3D thumbnail (visually verified for racbasic).

## 6. `Global/DocumentIncrementTable`

Raw stream = 8-byte header `01 00 00 00 00 00 00 00` + gzip (valid
CRC/ISIZE trailer here) + a few zero bytes + 58–75 B slack. Inflated payload:

```
u16   type_tag = 0x053C
u32   count = N            (== BasicFileInfo "Unique Document Increments")
Record[N]                  (variable length, layout below)
u32   count2 = N           (the table is serialized a SECOND time)
Record[N]                  (byte-identical to copy 1 in all six samples)
8 x 00                     trailer
```

**Confidence: high** for the structure (parser consumes every byte of all six
payloads, both copies match); medium for field semantics.

Record layout:

| Type | Field | Notes |
|---|---|---|
| u32 | npairs | 1–5 |
| (i32 key, i32 value) × npairs | pairs | first pair key is always **−1**, value = an ElementId-sized number (78931…; small values 0/2/51 on `flag=0` records) [hypothesis: id watermark / episode element]; extra pairs are `(k, count)` with k ≈ increment number, last extra value 0 [hypothesis: `std::map` of EpisodeId → count]; the newest (2026) record has only the −1 pair |
| ustr | username | Windows login of the saver: zhangg, xuew, loboarch, hansonje, MatthiasRN19, `autodesk@peter-eisen.at` (Autodesk-ID email in dach) … |
| u32 | 0 | |
| u32, u32 | id_pair | two consecutive small ids per record (824,825 → 847,848) [hypothesis: pair of ElementIds/EpisodeIds allocated by the save] |
| u32 | 0 | |
| u32 | timestamp | **Unix seconds, UTC**; last record = 2025-03-13 (matches ZIP `updated`); first records date to Nov 2015 → the Autodesk sample templates' own save history since Revit 2017 |
| u32 | sequence | 1…N increment number (a few numbers skipped in old records) |
| u32 | X | 0 in every historical record; == the −1 pair value in the newest record |
| i32[] until −1 | counters | always 10 monotone int32 watermarks (e.g. racbasic 436,444,444,444,333,444,445,183,415,333); index 7 grows only on `flag=1` records |
| u32 | counter_g | +1 per record (racbasic 307→322) |
| u8 | flag | 1 = ordinary modifying save, 0 = save that changed no elements? [hypothesis] |

Worked example (racbasic record #1 at payload 0x06):
`02 00 00 00` npairs=2, `ff ff ff ff 53 34 01 00` (−1, 78931),
`01 00 00 00 00 00 00 00` (1, 0), `06 00 00 00 z.h.a.n.g.g.` user "zhangg",
`00 00 00 00 38 03 00 00 39 03 00 00 00 00 00 00` (0, 824, 825, 0),
`8d 2d 40 56` = 1447046541 = 2015-11-09T05:22:21Z, `01 00 00 00` seq 1,
`00 00 00 00` X, ten counters, `ff ff ff ff`, `33 01 00 00` G=307,
`01` flag.

The `Contents` payload embeds the newest record's counter block (minus
index 7) and its `G`, so `Contents` is the "current increment state" plus
identity, while the DIT is the full save history.

## Cross-cutting observations (also filed to `docs/inbox/metadata.md`)

* The class-stream framing (`62 19 22 05` prologue, `0x8000 | idx` inline
  class definitions in the exact `Formats/Latest` record shape, per-object
  class references) is a general serialization envelope — expect it in other
  streams.
* Not every gzip trailer is corrupt: `Contents`, `Global/DocumentIncrementTable`,
  `Global/ElemTable`, `Global/History`, `Global/PartitionTable` carry **valid**
  CRC32/ISIZE; `Formats/Latest`, `Global/Latest`, `Global/ContentDocuments`
  do not. The bytes after the 8-byte trailer (2–17 zeros + a
  size-correlated high-entropy blob) never inflate — [hypothesis] stale slack
  from in-place stream rewrites.
* Payload type tags seen: `0x053C` (DIT), `0x053E` (Contents record).

## Unknowns

1. `BasicFileInfo` u32 14 at 0x00 and the 2-byte worksharing field — need a
   worksharing-enabled file to confirm.
2. Contents wrapper `class_ref` (178–430, varies per file) and `unknown_28`.
3. Contents `unknown_hdr5` = (7, a, b, −1, 3) and the constant `(−1,1420)`,
   `(−1,1426)` trailing pairs.
4. Semantics of the 10 DIT counters, `id_pair`, the −1 pair value, `X`, `G`
   and `flag`; why the DIT table is written twice.
5. Why `Contents.counters` omits DIT counter index 7.
6. The 42-byte (Contents) / 58–75-byte (DIT) trailing slack blobs.
7. `RevitPreview4.0` instance-prologue u32 0 and prologue `count`/`28`.

# Prior art — RVT/RFA/RTE/RFT binary format

Agent slug: `prior-art-format`. Date: 2026-08-02. Read alongside
`KNOWLEDGE.md`; contradictions are listed separately in
`docs/inbox/prior-art-corrections.md`.

Purpose: an exhaustive map of everything already published about the Revit
container/serialization format, so this fleet never re-derives a known result,
plus concrete porting notes for the two open-source parsers that matter.

Everything cited below was fetched/read on 2026-08-02. Local mirrors of the
important sources are under `vendor/` (see §8).

---

## 0. Executive summary

1. **There is exactly one deep public reverse-engineering effort:
   `DrunkOnJava/rvt-rs`** (Apache-2, Rust, ~55 K lines, built 2026-04-19 →
   present). It goes far beyond the brief's expectation. It has: a
   `Formats/Latest` schema parser with per-class **serialization tags**
   (u16, `0x8000` flag), parent/ancestor links, a **100 % field-type
   classifier** for the C++ type encodings, an 11-release **tag-drift
   dataset**, a partial schema-directed `ADocument` walker over
   `Global/Latest`, an `ElemTable` layout parser (12/28/40-byte record
   variants), a `Partitions/NN` 44-byte header + chunk scanner, a decoded
   `Global/PartitionTable`, a decoded `Contents` header, a byte-preserving
   round-trip writer, and one fully decoded element record (Revit 2023
   `ArcWall`). Its own docs are honest that **element extraction from real
   project files does not work yet** — the partition-stream record envelope
   is unsolved. Cloned to `vendor/rvt-rs/`.
2. **`phi-ag/rvt` is TypeScript, not Rust** (npm `@phi-ag/rvt`, MIT, Peter
   Hirn). It parses only: the CFB container (own implementation),
   `BasicFileInfo` (a genuine byte-level grammar with three layout
   versions 10/13/14), and the PNG in `RevitPreview4.0`. Its README has a
   40-byte `ElemTable` layout *hypothesis* that is not implemented. Its
   killer asset is the **11-release corpus** of the same family file
   (`examples/Autodesk/*.rfa`, 2016→2026, CC-BY-NC-SA), fetched into
   `vendor/phi-ag-rvt/examples/Autodesk/`.
3. **The gzip-trailer story is more subtle than `KNOWLEDGE.md` says.** The
   trailer is *present* (`[CRC32][ISIZE]`, then zero padding, then a
   variable-size trailing block). On small/medium streams the CRC32/ISIZE
   **validate perfectly**; on large streams (`Formats/Latest`,
   `Global/Latest`, `Global/ContentDocuments`, big `ElemTable`s) our
   raw-inflate output **does not match** the writer's own CRC/ISIZE and the
   `Formats/Latest` output is visibly garbled beyond ~0x22000. Independent
   corroboration: a 2025 ZDI/Trend Micro exploit write-up states that
   `Global/Latest` is `header + gzip payload + zero padding + ECC trailer`,
   that Revit **auto-repairs perturbed streams using the ECC** (routines in
   `Utility.dll`) and rejects streams whose ECC does not match, and that
   naive re-gzip is rejected. This is the single most important correction
   for tracks A and D — see `docs/inbox/prior-art-corrections.md` §1.
4. **The on-wire object model is a 16-bit class-index tagged serializer.**
   ZDI (Revit 2025): the deserializer reads a **u16 class index**; 4,611
   serializable classes are registered (`Utility!ArchiveClassMaps::loadClass`
   / `ARuntimeClass::createObject`); e.g. `AString` = index `0x1f`;
   strings are length-prefixed, not NUL-terminated. rvt-rs independently
   derives the same u16 tag concept from `Formats/Latest` (tag with the
   `0x8000` flag, drifting per release, `AbsCurveGStep`, `HostObjAttr`, …)
   and cross-checked every schema class name against the exported symbols
   of the public `RevitAPI.dll` NuGet package. `Formats/Latest` **is** the
   file-local copy of the archive class map — the Rosetta stone claim in
   `KNOWLEDGE.md` is confirmed by two independent sources.
5. **New corpora available**: `magnetar-io/revit-test-datasets` (MIT) —
   two real project files (`Revit_IFC5_Einhoven.rvt` 2023,
   `2024_Core_Interior.rvt` 2024) **plus their IFC exports** (a decoding
   oracle!) and four family files. Fetched into
   `vendor/magnetar-revit-test-datasets/` (277 MB).
6. **Sibling formats**: `.rfa/.rte/.rft` are the same CFB container with
   the same stream inventory; the only structural differences observed
   are (a) families carry `PartAtom` (plain Atom XML) and exactly one
   `Partitions/N`, projects carry `ProjectInformation` (a ZIP wrapping the
   same Atom XML) and may carry **many** `Partitions/N` streams; (b) the
   `ElemTable` record framing differs (12-byte family vs 28/40-byte
   project); (c) `Global/PartitionTable` layout differs (167 B family vs
   87 B project). Verified against 11 phi-ag RFAs, 4 magnetar RFAs, 2
   magnetar RVTs and our six 2026 RVTs (§6).

---

## 1. Annotated bibliography

Ordering: most transferable first. "Agreement" is relative to
`KNOWLEDGE.md` as of 2026-08-02.

### 1.1 Open-source parsers (byte-level)

| # | Source | What it establishes | Agreement with KNOWLEDGE.md |
|---|---|---|---|
| B1 | **DrunkOnJava/rvt-rs** — <https://github.com/DrunkOnJava/rvt-rs> (Apache-2.0; author Griffin Long, AI-assisted; local: `vendor/rvt-rs/`). Key files: `src/formats.rs`, `src/walker.rs`, `src/elem_table.rs`, `src/partitions.rs`, `src/compression.rs`, `src/object_graph.rs`, `src/arc_wall_record.rs`, `docs/rvt-moat-break-reconnaissance.md` (master narrative, 1,733 lines), `docs/data/tag-drift-2016-2026.csv`, `reports/element-framing/RE-*.md`. | The most complete public account. Container, truncated-gzip framing, `Formats/Latest` schema wire format (§2.1), field-type encoding table (§2.2), tag drift, `Global/Latest` framing (upgrade-history strings + two sequential-id "directories" + schema-referenced tail), `ElemTable` layouts, `ContentDocuments` linked-list records (2024), `Partitions/NN` 44-byte header + multi-chunk gzip, partition tag-density analysis, ArcWall record decode (2023 only), `Contents` and `RevitPreview4.0` `62 19 22 05` wrapper, `Global/PartitionTable` GUID. Also documents *failures*: element instances live in `Partitions/*`, envelope unknown; ADocument walk only validated 2024–2026. | Confirms: CFB; skip-10-then-raw-inflate; `Formats/Latest` per-release class dictionary; ADocument fields ↔ `Global/*` streams; 8-byte prefix on `Global/*`. **Extends** almost everything else. **Disagrees**: claims the `Global/*` 8-byte prefix is always `[u32 0][u32 0]` (ours are `05/01/00 …`, see corrections §3). |
| B2 | **phi-ag/rvt** — <https://github.com/phi-ag/rvt>, npm `@phi-ag/rvt` (MIT; Peter Hirn; TypeScript; local: `vendor/phi-ag-rvt/`). Files: `src/cfb/*` (CFB v3/v4, FAT/miniFAT/DIFAT), `src/info.ts` (`BasicFileInfo` grammar), `src/thumbnail.ts`, README "Reverse Engineering" section (ElemTable 40-byte hypothesis), `src/node.test.ts` (golden metadata for 11 releases). | A validated **byte grammar for `BasicFileInfo`** across file-version words 10 (2017/18), 13 (2019/20), 14 (2021–2026); `RevitPreview4.0` = PNG located by magic; a plausible 40-byte `ElemTable` record hypothesis (int64 id, 3×int32, id again, int64, int32) with a `[u8 ver][u8 05][int32 count]` header. Ships the 11-release RFA corpus + expected metadata (paths, GUIDs, build strings). | Confirms `BasicFileInfo` mixed-encoding metadata. Its 40-byte ElemTable hypothesis matches the 2024+/2026 project layout rvt-rs measured (and ours, §6.3). |
| B3 | **teocomi/Reveche** — <https://github.com/teocomi/Reveche> (MIT, C#, 2015) | Version check via `BasicFileInfo` only (based on Tammik 2013). | Consistent, no new bytes. |
| B4 | **ricaun-io/ricaun.Revit.FileInfo** — <https://github.com/ricaun-io/ricaun.Revit.FileInfo>; **vampirefu/RevitFileVersion**; **Tereami/ShowRevitVersion** (OpenMcdf); **KennanChan/RevitFileUtility**; **UserDevtec/Revit-RFA-File-Extractor**; **yiskang/DA4R-RevitBasicFileInfoExtract** (uses Revit API `BasicFileInfo.Extract`). | All `BasicFileInfo`-regex tools ("Revit Build:" for ≤2018, "Format:" for 2019+; unit-tested 2014–2024). | Consistent. |
| B5 | **chuongmep/revit-extractor** — <https://github.com/chuongmep/revit-extractor> | Wraps Autodesk's shipped `RevitExtractor.exe`; **requires a local Revit install**; not a binary parser. | N/A. |
| B6 | **datadrivenconstruction/cad2data-Revit-IFC-DWG-DGN** — closed-source `RvtExporter.exe` wrapper (per rvt-rs landscape doc). | Proves conversion is feasible; discloses nothing. | N/A. |
| B7 | **thezdi/CompoundFileTool** — <https://github.com/thezdi/CompoundFileTool> | ZDI's tool to explode/rebuild a CFB into a folder tree; used to patch `Global/Latest` for fuzzing. Useful for our Track D round-trips. | N/A. |

### 1.2 Security research (highest byte-level authority after B1)

| # | Source | What it establishes |
|---|---|---|
| S1 | **ZDI (Simon Zuckerbraun), "Crafting a Full Exploit RCE from a Crash in Autodesk Revit RFA File Parsing"**, 2025-10-06, <https://www.thezdi.com/blog/2025/10/6/crafting-a-full-exploit-rce-from-a-crash-in-autodesk-revit-rfa-file-parsing> (CVE-2025-5037, Revit 2025). Mirrored/summarised in HackTricks "Office file analysis" (<https://github.com/HackTricks-wiki/hacktricks/…/office-file-analysis.md>, section "OLE Compound File exploitation: Autodesk Revit RFA – ECC recomputation and controlled gzip"). | (1) `Global\Latest` layout = **brief header + gzip payload + zero padding + high-entropy error-correcting-code (ECC) trailer**. (2) Revit *auto-repairs* small perturbations from the ECC and *rejects* streams whose ECC mismatches; naive gunzip/edit/gzip does not round-trip ("Recompress with a Revit-compatible gzip implementation … Recompute the ECC trailer over the padded stream"). ECC + gzip routines live in `Utility.dll` (public symbols + diagnostic strings). (3) The deserializer reads a **16-bit class index** per object; **4,611 classes** registered in Revit 2025; `AString` = `0x1f`, `std::pair< ElementId, ElementIdSetWrapperClass >` = `0xc4`; object construction via `Utility!ARuntimeClass::createObject`, class maps via `Utility!ArchiveClassMaps::loadClass`; `PersistentClass`+`ARuntimeClass` (name pointer at +0). (4) Strings are **length-prefixed** (may contain NULs). |
| S2 | Autodesk KB troubleshooting article with assertion string `Assertion failed: line 797 of ElemTable\Marshaller.cpp` (per rvt-rs landscape doc §5). | Internal module names: `ElemTable/Marshaller.cpp` — the element table has a dedicated marshaller with a length-check assertion → length-prefixed record framing. |
| S3 | rvt-rs cross-check of schema class names against the public **`RevitAPI.dll` NuGet symbol export** (README "Results at a glance"). | Every top-level class name in `Formats/Latest` (`ADocument`, `DBView`, `HostObj`, `Symbol`, `ElementId`, `APropertyDouble3`, …) appears as a decorated C++ symbol → schema names are genuine RTTI/serialization identifiers (matches our `KNOWLEDGE.md` "not obfuscated" claim). |

### 1.3 Autodesk-side documentation and official read surfaces

| # | Source | What it establishes |
|---|---|---|
| A1 | Revit API `BasicFileInfo` class + static `BasicFileInfo.Extract(path)` — <https://help.autodesk.com/view/RVT/2026/ENU/?guid=475edc09-cee7-6ff1-a0fa-4e427a56262a> | Official reader of the `BasicFileInfo` stream from a *closed* file: SavedInVersion, IsWorkshared, CentralPath, Username, LatestCentralVersion, AllLocalChangesSavedToCentral, DocumentVersion (GUID + save count), LanguageWhenSaved. This is the *field list* our `BasicFileInfo` decoder should reproduce. |
| A2 | Revit API `TransmissionData` class (`ReadTransmissionData` / `WriteTransmissionData` on a closed file) — <https://www.revitapidocs.com/2022/d78d1e9c-1cee-1336-88d5-b605dacd077d.htm>; Tammik "List Linked Files and TransmissionData" <https://jeremytammik.github.io/tbc/a/0583_list_links.htm>; eTransmit add-in. | The `TransmissionData` stream (UTF-16 XML of external-file references + a `IsTransmitted` flag) is officially readable **and writable** without opening the model. A ready-made round-trip test for our writer. |
| A3 | Revit API `Document.ExtractPartAtomFromFamilyFile` / family part-atom export; Autodesk `partatom` XML namespace `urn:schemas-autodesk-com:partatom`. | Official semantics of the `PartAtom` stream (title, id, updated, taxonomy, category/OmniClass, `design-2d`/`design-3d` links). |
| A4 | **Autodesk/revit-ifc** — <https://github.com/Autodesk/revit-ifc> (Apache-2) | Runs *inside* Revit via the API; not a file parser, but the authoritative Revit-category→IFC mapping and property-set naming to reuse for Track B. |
| A5 | Autodesk KB "Revit file types" (RVT/RTE = projects; RFA/RFT = families) — cited by Just Solve wiki. | Sibling-format equivalence at the container level. |

### 1.4 Jeremy Tammik / The Building Coder (Autodesk DevRel)

| # | Post | Establishes |
|---|---|---|
| T1 | "RVT File Version" (2008-10) `rvtver.py` — <https://thebuildingcoder.typepad.com/blog/2008/10/rvt-file-version.html> | First public statement that RVT is OLE structured storage; version by scanning for `Autodesk Revit` build string. |
| T2 | "Open Revit OLE Storage" (2010-06) — <https://thebuildingcoder.typepad.com/blog/2010/06/open-revit-ole-storage.html> (also <https://jeremytammik.github.io/tbc/a/0391_open_ole_storage.htm>) | C# OLE viewer enumerating streams incl. preview image. |
| T3 | "Basic File Info and RVT File Version" (2013-01) — <https://jeremytammik.github.io/tbc/a/0887_rvt_file_version.htm> | Victor Chekalin's `System.IO.Packaging` reader; notes `BasicFileInfo` is **mixed encoding** — UTF-16LE fields plus a block that only renders when decoded as *big-endian* UTF-16 (i.e., ASCII/UTF-8 at an odd byte offset). Independently confirms our `KNOWLEDGE.md` "odd-offset ASCII block" note. |
| T4 | "Determining RVT File Version Using Python" (2017) — <https://jeremytammik.github.io/tbc/a/1570_rvt_version_py.html> | `olefile` + UTF-16LE decode + `r"\d{4}"` regex. |
| T5 | "64-Bit Element Ids, Maybe?" (2022-11) — <https://thebuildingcoder.typepad.com/blog/2022/11/64-bit-element-ids-maybe.html> | ElementId widened from 32 to 64 bit around Revit 2024 API. Explains the 28-byte (u32-era) vs 40-byte (u64-era) `ElemTable` records and u64 ids in 2024+ `ContentDocuments`. |
| T6 | Reddit/old.reddit quote (2023) via rvt-rs: Tammik — "Finding the right pointers into the partition data seems a lot harder and I currently wouldn't even know where to start." | Autodesk DevRel confirms partition data is publicly undocumented. |

### 1.5 Digital-preservation registries

| # | Source | Establishes |
|---|---|---|
| P1 | Just Solve / Archive Team wiki "Revit" — <http://fileformats.archiveteam.org/wiki/Revit> | Extensions `.rfa .rft .rte .rvg .rvt .rws`; released 2000 (Charles River Software; Autodesk acquired 2002); Microsoft Compound File; historical eras: Revit library 4.0–9.0 has no `BasicFileInfo`; 2008–2018 `BasicFileInfo` "Revit Build: …"; 2019+ new format "Format: 2020 Build: …"; sample-file links (incl. web.archive Revit library v6 ~2004, 2015/2020 sample projects). |
| P2 | PRONOM PUIDs: extension-only x-fmt/443..448 (rfa, rft, rte, rvg, rvt, rws) and container-signature PUIDs **fmt/1346–fmt/1351** (Revit File 4; Project 2010; Family 2008; Family 2010; Project 2019; Family 2019) — <https://www.nationalarchives.gov.uk/PRONOM/fmt/1351>. | Formal identification exists via DROID **container signatures** (below). |
| P3 | DROID container signature file (`digital-preservation/droid` repo, `container-signature-20260119.xml`, IDs 43000–43050). | Identification recipe: OLE2 containing `Formats` + `BasicFileInfo`; 2010-era: UTF-16LE `"Revit Build:"` in first 1 KB of `BasicFileInfo`; 2019+: UTF-16LE `"Author: Autodesk Revit\r"` in the *last* 1 KB of `BasicFileInfo`; family vs project distinguished by a `PartAtom` stream containing ASCII `"application/rfa"` (2010+) — exactly our observation that only families have `PartAtom`. Oldest signature ("Revit File 4"): streams `Formats` + `Contents` only. |

### 1.6 Q&A / forum threads

| # | Source | Establishes |
|---|---|---|
| F1 | reverseengineering.stackexchange #18868 (2018) "Analyzing a Revit project file" — <https://reverseengineering.stackexchange.com/questions/18868> (no answers). | Stream tree incl. `ProjectInformation`, `Partitions/6`; `Global/History` starts `01 00 00 00 00 00 00 00` then gzip magic at offset 8; inflated History begins `5d 04 01`, a 16-byte GUID repeated 3–4×, ~860 bytes of "alternating null words", monotonically increasing counter — a partial `History` layout sketch nobody has finished. |
| F2 | Autodesk forum "You can parse .rvt files" (2025-01) — <https://forums.autodesk.com/t5/revit-api-forum/you-can-parse-rvt-files/td-p/13242649> (Cloudflare-blocked in this session; per rvt-rs it covers `BasicFileInfo` only). | — |
| F3 | Autodesk forum "Atom XML file from Revit PROJECT file (not family PartAtom XML)" — <https://forums.autodesk.com/t5/revit-api-forum/atom-xml-file-from-revit-project-file-not-family-partatom-xml/td-p/11286654> | Community awareness that projects also carry Atom XML — this is our `ProjectInformation` ZIP (see corrections §2). |

### 1.7 Commercial / cloud (ceiling, not sources)

- **ODA BimRv SDK** (<https://www.opendesign.com/products/bimrv>): read `.rvt/.rfa/.rte` 2011/2015→latest, write latest; paywalled; no public spec. Existence proof that read+write from bytes is achievable.
- **Autodesk APS/Forge Model Derivative**: cloud conversion to SVF/SVF2; irrelevant to bytes; ToS forbids format derivation for Forge users.
- Apache Tika: only generic OLE2 detection (rvt-rs's claim that Tika reads `BasicFileInfo` was **not** confirmed by me — treat as unverified).

### 1.8 Corpora (redistributable)

| Corpus | License | Contents | Where |
|---|---|---|---|
| phi-ag/rvt `examples/Autodesk/` | CC-BY-NC-SA 3.0 (Autodesk CC terms) | 11× `rac_basic_sample_family` RFA, one per release 2016–2026, download URLs in its `examples/Autodesk/README.md` (`revit.downloads.autodesk.com/.../racbasicsamplefamily.rfa`) | `vendor/phi-ag-rvt/examples/Autodesk/` (LFS objects fetched, sha256-verified) |
| magnetar-io/revit-test-datasets | MIT | `Revit_IFC5_Einhoven.rvt` (2023, 0.9 MB), `2024_Core_Interior.rvt` (34 MB), **`2024_Core_Interior.ifc` + `_slim.ifc` exports of the same model**, 4 RFAs (door, columns, mullion profile), FME/Rhino demos | `vendor/magnetar-revit-test-datasets/` (LFS objects fetched, sha256-verified) |
| SSeelos/MyRevitProject | none declared | 2025 `.rvt`, 459 KB — probe-only per rvt-rs; not fetched | — |

---

## 2. What the prior art has actually established (byte level)

This section digests B1 (rvt-rs) unless another source is named. Cross-checks
against our 2026 corpus are in §6.

### 2.1 `Formats/Latest` wire format (rvt-rs `src/formats.rs`)

Class record:

```
[u16 name_len][name ASCII]           class name (upper-case first char)
[u16 tag_word]                        bit 0x8000 set ⇒ tagged (top-level
                                      serializable); low 15 bits = tag id.
                                      bit clear ⇒ this occurrence is a
                                      *reference* to an existing class.
tagged classes only:
  [u16 pad=0][u16 parent_name_len][parent name]
  [u16 ancestor_tag]                  0 or the tag of a mixin/protocol class
  [u32 field_count][u32 field_count]  duplicated declared field count
then field records:
  [u32 name_len][field name ASCII]    (u32 prefix, unlike class names)
  [type-encoding block]               see §2.2
  optionally [u16|u32 len][C++ type signature ASCII] e.g. "std::pair< ElementId, double >"
```

- Verified example (2024): `HostObjAttr` = `{tag=0x006b (107), parent=Symbol,
  ancestor_tag=0x0025 (APIVSTAMacroElem), declared_field_count=3}`, fields
  `m_symbolInfo` (Pointer kind 2 `0e 02 00 00`), `m_renderStyleId`,
  `m_previewElemId` (ElementId `0e 00 00 00 14 00`).
- 395–405 classes parsed per file, **only ~80 carry tags**; the rest are
  parents/mixins/embedded types. Class-name literals like `Wall`, `Floor`,
  `Door`, `Level` **do not exist** in the schema — concrete names do
  (`ArcWall` 0x0191 in 2023 / 0x019c in 2024, `VWall`, `WallCGDriver`, …).
- Tags are assigned by stable alphabetical enumeration and **drift** when
  new classes are inserted; 6 alphabetically-early classes are stable across
  2016–2026 (`A3PartyAImage` 0x000d, `ADTGridImportVocabulary` 0x0012,
  `ADocWarnings` 0x001b, `APIVSTAMacroElem` 0x0025,
  `APIVSTAMacroElemTracking` 0x0028, `AProperties` 0x002a). ⇒ **never
  hard-code tags; re-read the schema per file.** Dataset:
  `vendor/rvt-rs/docs/data/tag-drift-2016-2026.csv` (122 classes × 11
  releases).
- Caveat (potentially load-bearing for us): rvt-rs caps schema scanning at
  the first **64 KB** of the inflated stream because "beyond that … binary
  object data … trips our class-name heuristic". Our own analysis (corrections
  §1) shows the inflated `Formats/Latest` **degrades from ~0x22000 onward
  because of a decompression mismatch**, so the "binary noise" may simply be
  mis-inflated schema. Do not inherit the 64 KB cap; fix decompression first.
- ZDI (S1) puts the true class inventory at **4,611** in Revit 2025 (from
  process memory), an order of magnitude more than the ~400 rvt-rs recovers —
  another hint that most of the schema stream is currently unread.

### 2.2 Field type-encoding block (rvt-rs `FieldType`, 100 % classified)

First byte = category; bytes 1–2 = little-endian sub-code.

| Encoding | Meaning | Wire size (per rvt-rs walker) |
|---|---|---|
| `01 00 00 00` | bool | 1 (padded in some contexts) |
| `02 00 00 00` | u16/i16 | 2 |
| `03 00 00 00` | i32 alias (2016–2018 only, `UserID.m_id`, `ElementRegenerationInfo.m_nAtomType`) | 4 |
| `04 00 00 00` | u32 (legacy discriminator) | 4 |
| `05 00 00 00` | u32/i32 (2019+) | 4 |
| `06 00 00 00` | f32 | 4 |
| `07 00 00 00` | f64 | 8 |
| `08 00 60 00` / `08 60 00 00` | UTF-16LE string, `[u32 char_count][chars]` | var |
| `09 00 00 00` | GUID | 16 |
| `0b 00 00 00` | u64/i64 | 8 |
| `0e 00 00 00 14 00 (00 00)` | `ElementId` (ref to root class tag 0x14) | 8 in ADocument (`[u32 tag_or_0][u32 id]`) |
| `0e 00 00 00 <u16 tag> <u16 sub>` | typed ElementId reference to class `<tag>` | 8 |
| `0e 01|02|03 00 00` | pointer kinds A/B/C | 8 (`[u32 a][u32 b]`, 0 / all-ones = NULL) |
| `<k> 10 00 00 …` | `std::vector<k>` for k ∈ {01,02,04,05,06,07,0b,0d,0e} | `[u32 count][items]` |
| `<k> 50 00 00 …` | container (`std::map`/`set`) of base k; 0x0e variant embeds the C++ signature (`std::pair< … >`) and a class tag | 0x0e: 2-column `[u32 n][n×(u16 id,u32 mask)][u32 n2][…]` |
| `0d …` | point / transform base (appears only inside vector/container) | 3×f64 for points |

Scalar-base containers have **no body** in the schema (their earlier
"28-byte body" was the next field's header, `docs/container-wire-format-2026-04-21.md`).

### 2.3 `Global/Latest` framing (rvt-rs docs §Q6.x + `walker.rs`)

- Not an index+heap; a **flat schema-directed serialization** (protobuf-style,
  instances are *not* tag-delimited — searching for a class's tag as an
  aligned u32 found 2 hits where a u16 scan found ~6,600).
- Layout on the 2024 family sample: `[custom 8-byte prefix][gzip]`; inflated:
  header (~0x53) → **upgrade-history UTF-16LE strings** (`[u32 tag][u32
  char_count][utf16]`, first tag `0x00000007`) → **Table A** (offset 0x363,
  ~131 sequential-id records `[u32 id][u16 val][opt pad/extra]`) → **Table
  B** (~141 records, mostly 12-byte `[u32 id][ffffffff][ffffffff]` nulls) →
  ~935 KB **schema-referenced instance mass** (class-tag density 33× the
  pre-directory region). The ADocument singleton is *inside* that mass,
  located by a heuristic + scoring detector (`find_adocument_start_with_schema`,
  `walker.rs:421`).
- ADocument wire shapes validated 2024–2026: Pointer = 8 bytes; ElementId(Ref)
  = `[u32 tag_or_0][u32 id]` — the last three ADocument fields decode
  identically (`{0,27},{0,31},{0,35}`) across 2024/2025/2026; Container(0x0e)
  = 2-column id/mask lists.
- Family vs project: on projects (Einhoven 2023, Core Interior 2024)
  ADocument sits at 0x1ee5 / 0x157e0 respectively, surrounded by inline
  UTF-16 strings (view/schedule names are packed inline in `Global/Latest`,
  not in a string table).
- **`Global/Latest` holds document-level singletons only** (ADocument,
  categories, styles, levels …). Element instances are in `Partitions/*`.

### 2.4 `Global/ElemTable` (rvt-rs `elem_table.rs`, doc `elem-table-record-layout`)

Header: `[u16 element_count][u16 record_count][12 B zero]`; family files
also show `header_flag=0x0011` at 0x1e/0x22. Record framing by variant:

| Variant | Record start | Marker | Stride | id layout |
|---|---|---|---|---|
| Family 2016–2026 | 0x30 | none | 12 | `[u32 a][u32 b][u32 c]` (semantics open) |
| Project 2023 (u32 ids) | 0x1e | `FF FF FF FF` | 28 | `[+4]=u32 id_primary, [+8]=u32 id_secondary, +12: 16 B payload` |
| Project 2024 (u64 ids) | 0x22 | `FF×8` | 40 | `[+12]=u32 id, [+32]=u32 id2` (u64 halves) |

Established negatives: the payload bytes are **not** offsets into
`Global/Latest`; the `ElemTable` is the *authoritative declared-id set*, not
a location index. Ids beyond the sequential 1..N block use a different layout
near the stream end (unresolved). Note `Marshaller.cpp` (S2) implies
length-checked marshalling.

### 2.5 `Global/ContentDocuments` (rvt-rs RE-17/RE-20)

2024 project: 40-byte linked-list records
`[u64 id][u32 19][u32 19][u32 0xFFFFFFFF][u64 id_again][u64 prev_id or all-F][u32 0]`
with monotonically increasing ids (40369, 40370, …) that live in a *different
id space* than `ElemTable` (6/30,705 overlap). 2023 layout differs (u32 ids,
smaller records) — unfinished. Family files: 82 bytes, essentially empty.

### 2.6 `Global/PartitionTable`, `Contents`, `RevitPreview4.0`, `History`

- Family `PartitionTable` (167 B inflated, 165 B invariant 2016–2026):
  `[u16 version_counter (2016=2572 … 2026=3200)][u32 1][u32 1][GUID
  {3529342d-e51e-11d4-92d8-0000863f27ad}][u32 0][u32 str_len]
  [ffffffffffffffff][u32 record_count=2][u16 0x3000][UTF-16 "Family : … -
  Upgrade"][19-byte footer]`. Projects: shorter (87 B), different GUID per
  file — the family GUID is **not** a universal Revit magic (rvt-rs corrected
  itself; our 2026 project has yet another UUIDv1, §6.6).
- `Contents`: 4-byte magic `62 19 22 05` (Revit's "custom wrapper follows"
  marker, shared with `RevitPreview4.0`), a small table (`u32 27, 1, 1,
  compressed_len, 2048, run of u16 pairs`), gzip at 0x5b; inflated 268 B of
  UTF-16LE: creator name, `GLOBAL` label, the format GUID bytes, build
  string. (Our 2026 files: `62 19 22 05 1c 00 00 00 01 00 00 00 …`, gzip at
  a smaller offset — same family.)
- `RevitPreview4.0`: same `62 19 22 05` ~300-byte wrapper + PNG at first
  `89 50 4E 47 0D 0A 1A 0A`.
- `History`: rvt-rs only extracts the "Revit YYYY  build" upgrade strings
  (they actually live near the top of `Global/Latest`; F1 gives a 2018
  sketch of the real `History` stream: `5d 04 01` magic, GUID×4, counter
  table).

### 2.7 `Partitions/NN` (rvt-rs `partitions.rs`, RE-01/09/11/13/14.x)

- Exactly **44 header bytes**, then a run of concatenated *truncated-gzip*
  chunks located by scanning for `1F 8B 08`. Header fields (unresolved):
  `[u32 chunk_count+1?][u32 0][12 B "size block"][u32×4 trailer]`; the
  trailer u32s are **not** per-chunk offsets (tested negatively across 6
  releases). Family files: 5–10 chunks; projects: dozens to ~925 per stream
  and **several `Partitions/N` streams per file** (2023 Einhoven: 0–6; 2024
  Core Interior: 46,48,51,53,55,59,61,65).
- Gzip **chunk boundaries are not record boundaries** (a 16-byte
  per-chunk-header hypothesis was refuted: leading u32s repeat across chunks
  and don't match lengths). Concatenate all inflated chunks into one logical
  buffer before parsing. (2024 partitions have quasi-monotonic leading u32s
  — possible ids — unresolved.)
- The concatenated partition data is a **soup of sub-component records
  keyed by u16 class tags**, not one record per architectural element. The
  same ~13–16 tag classes dominate every partition on every file
  (`AnalyticalLevelAssociationCell`, `AbsCurveGStep`, `HostObjAttr`,
  `AbsDbViewPressureLossReport`, `ADTGridImportVocabulary`, `GeomStep`,
  `AppearanceAsset`, `ATFProvenanceBaseCell`, `A3PartyAImage`, …). A
  wall/floor is a *composition* of sub-records.
- Signal-vs-noise methodology (transferable): u16 tag hit-count vs
  uniform-random baseline (`total/65536`); then filter real records by
  `bytes[+2..+4] == 00 00` after the tag (kills UTF-16 text coincidences;
  e.g. `0x6b 0x00` = the letter "k" inside `".units"` strings). Post-filter
  kept-ratios: >50 % = real record classes; 10–40 % bimodal; <5 % text
  artifacts (e.g. `AbsCurveGStep`).
- **First fully decoded element record: Revit 2023 `ArcWall`** (tag 0x0191,
  Einhoven `Partitions/5`, 32/32 clean occurrences):
  `+0 u16 tag; +2 u16 0; +4 u32 0x00088004; +8 u32 count/version (1 std, 3
  compound); +0xc u32 3; +0x10 u16 variant (0x07fa std / 0x0821 compound);
  +0x12 6×f64 coords; +0x42 6×f64 duplicate; +0x72 u8 0x03`; ~292 B (single)
  / 568 B (double) spacing. **Does not transfer to 2024** (tag 0x019c, no
  0x07fa variant among 919 candidates) — expect further drift in 2025/2026.
- Structural constants seen in several record families:
  `0x00000576 (1398)`, `0x00001d94 (7572)`, `0xFFFFFFFF` sentinels — likely
  family/schema-level identifiers, unresolved.
- Different `Partitions/N` streams carry different element populations
  (ArcWall only in Einhoven `Partitions/5`) — partition number may correlate
  with worksets/categories (hypothesis).

### 2.8 `Global/ElemTable` ↔ instance data linkage — the open frontier

Everyone's blocker (rvt-rs D11/RE-01): there is **no known map from
ElementId → (partition, offset)**. `ElemTable` payload bytes are not
offsets; `ContentDocuments` is a linked list in another id space; ADocument's
`m_elemTable` "pointer" `(2097249, 49)` is not a byte offset. rvt-rs's best
guess: build a handle index by **schema-directed one-pass scanning** where
each instance's self-id comes from its own `m_id` field. This is exactly
where our fleet should aim its heavier tooling (11-release deltas, real
project corpus with an IFC oracle).

### 2.9 phi-ag/rvt `BasicFileInfo` grammar (`src/info.ts`)

```
[i32 fileVersion]                          10=2017/18, 13=2019/20, 14=2021+ (2026 = 14, §6.1)
v10:  [i32 char_count]"Autodesk Revit YYYY (Build: yyyymmdd_hhmm(x64))" at offset 14
v13+: scan for marker 04 00 00 00, next 8 bytes = UTF-16 "YYYY";
      then [i32 char_count][build string]
[i32 char_count][UTF-16 original path]
[u16 unknown (3 or 4)][3 bytes pad]
[i32 char_count][UTF-16 guid1 = document/identity GUID]
[i32 char_count][UTF-16 locale, e.g. "ENU"]
[5 bytes unknown][i32 char_count][UTF-16 guid2][i32 char_count][UTF-16 guid3 (= guid2)]
[u16 pad_count][2 bytes][pad_count×2][i32 char_count][UTF-16 guid4 (= guid1)]
v13+: [u8 flag][i32 char_count][UTF-16 appName] (v14: a second appName string)
v14: [u8 padding flag (4⇒skip 5 else 2)] then the human-readable
     "Worksharing: … Username: … Central Model Path: … Format: YYYY Build: …
     Last Save Path: … Open Workset Default: … Project Spark File: … Central
     Model Identity: … Locale when saved: … All Local Changes Saved To
     Central: … Central model's version number corresponding to the last
     reload latest: … Central model's episode GUID: … Unique Document GUID: …
     Unique Document Increments: …" UTF-16 text block up to (len-2|5).
```

The GUID fields returned are `identityId` (00000000-… for non-workshared) and
`documentId`. Golden values for the 11 sample families are in
`vendor/phi-ag-rvt/src/node.test.ts` (e.g. 2026: build `20250227_1515(x64)`,
documentId `5ee56283-7ce7-4af9-8c63-7265dce3247d`).

---

## 3. Known-vs-unknown matrix

Legend: ✔ solved & reproducible · ◐ partial/hypothesis · ✘ unknown ·
"us" = this project as of `KNOWLEDGE.md` 2026-08-02.

| Layer / question | phi-ag | rvt-rs | ZDI/others | us | Best source |
|---|---|---|---|---|---|
| CFB container read | ✔ (own impl) | ✔ (`cfb` crate) | ✔ (CompoundFileTool) | ✔ olefile | any |
| CFB byte-identical rebuild (sector layout, 4 KB v4 sectors, miniFAT at sector 2 except 2025) | ✘ | ◐ (`docs/cfb-structural-layout-2026.md`) | ✘ | ✘ | rvt-rs |
| Stream inventory + family/project split | ✘ | ✔ (12 invariant + Partitions/NN; PartAtom "required" — wrong for projects) | DROID ✔ | ✔ | us + DROID |
| Truncated-gzip framing | ✘ | ✔ (`compression.rs`, encoder too) | ZDI ✔ ("Revit-compatible gzip") | ✔ | — |
| Gzip trailer / zero pad / ECC block | ✘ | ✘ (unnoticed) | ZDI ◐ (exists; algorithm in Utility.dll) | ◐ (measured §6.4) | **open — S1** |
| Correct decompression of large streams | ✘ | ✘ (silently accepts divergent output) | ZDI ◐ (uses Revit DLL wrapper) | ✘ | **open** |
| `BasicFileInfo` grammar | ✔ | ◐ (regex) | official API ✔ | ◐ | phi-ag + A1 |
| `Contents` header | ✘ | ✔ | ✘ | ◐ (magic seen) | rvt-rs |
| `PartAtom` / `ProjectInformation` | ✘ / ✘ | ✔ (parse+encode) / ✘ | ✘ | ✔ (ZIP+XML found by us) | us + rvt-rs |
| `RevitPreview4.0` | ✔ | ✔ | ✘ | ✔ | any |
| `TransmissionData` | ✘ | ✘ | official API ✔ | ◐ | A2 |
| `Formats/Latest` class records + tags | ✘ | ✔ | ZDI ✔ (u16 class index, 4,611 classes) | ◐ (strings only) | rvt-rs + S1 |
| Field type encodings | ✘ | ✔ (100 % on their corpus) | ✘ | ✘ | rvt-rs |
| Tag drift across releases | ✘ | ✔ (CSV) | ✘ | ✘ | rvt-rs |
| `Global/Latest` header + upgrade history | ✘ | ✔ | ✘ | ✘ | rvt-rs |
| `Global/Latest` Table A/B directories | ✘ | ◐ (semantics unknown) | ✘ | ✘ | rvt-rs |
| ADocument instance decode | ✘ | ◐ (2024–2026 validated; 2016–2023 shaped) | ✘ | ✘ | rvt-rs |
| `Global/ElemTable` layout | ◐ (README hypothesis, correct for 2024+) | ✔ (3 variants) | KB assert | ◐ | rvt-rs |
| `Global/ContentDocuments` records | ✘ | ◐ (2024 40-B linked list; 2023 different) | ✘ | ✘ | rvt-rs |
| `Global/PartitionTable` | ✘ | ✔ family / ◐ project | ✘ | ◐ | rvt-rs |
| `Global/History` / `DocumentIncrementTable` internals | ✘ | ✘ | RE.SE sketch (F1) | ✘ | **open** |
| `Partitions/NN` 44-B header | ✘ | ◐ (fields unresolved; not offsets) | ✘ | ◐ | rvt-rs |
| Partition record envelope / element composition | ✘ | ◐ (tag-soup model; ArcWall 2023 only) | ZDI ◐ (u16 class-index deserializer) | ✘ | **open** |
| ElementId → data location index | ✘ | ✘ (refuted 5 hypotheses) | ✘ | ✘ | **open** |
| Geometry payload (curves/solids inside records) | ✘ | ◐ (ArcWall coords only) | ✘ | ✘ | **open** |
| Semantic writer / Revit-openable output | ✘ | ✘ (stream-level patch only; sector layout not byte-identical) | ZDI ◐ (needs ECC recompute; uses Revit DLLs) | ✘ | **open — S1 gate** |
| .rfa/.rte/.rft container equivalence | ✔ (corpus is RFA) | ✔ (all four claimed) | DROID ✔ | ✔ (§6.6) | — |

---

## 4. What phi-ag/rvt already solved and how to port it to Python

Reality check first: the brief expected phi-ag/rvt to be a Rust project with a
`Formats/Latest` schema parser. **It is TypeScript and has no schema
parser.** What it *does* have is small, correct and directly portable. The
schema-parser role the brief anticipated is filled by rvt-rs (§5). Ports
below target `src/rvt/` in this repo.

### 4.1 CFB reader — `src/cfb/*.ts` → *do not port*

`Cfb.initialize` / `parseHeader` / `parseDirectory` / `fatSectorChain` /
`miniStreamOffset` (see `vendor/phi-ag-rvt/src/cfb/cfb.ts`, `header.ts`,
`directory.ts`) re-implement MS-CFB v3/v4 (sector shift 12 ⇒ 4 KB sectors
for Revit files, mini-sector shift 6, DIFAT handling, 128-byte directory
entries). We already have `olefile`, which is equivalent and mature. **Port
value: none**, except two facts to keep: Revit files are **CFB major version
4 / 4 KB sectors** (also confirmed by rvt-rs's sector-layout doc), and
`entryData` picks mini-stream vs FAT by the `miniFatCutoff` (4096) — relevant
only when we *write* (small streams like `Global/PartitionTable`, 134 B, live
in the mini-stream).

### 4.2 `BasicFileInfo` — `src/info.ts` → **port** as `src/rvt/basic_file_info.py`

Direct transliteration of `parseFileInfo` (info.ts:218), `parseString`
(info.ts:57), `parseVersion10/13` (info.ts:74–94), `parseGuids` (info.ts:115),
`parseAppName` (info.ts:147), `contentBounds` + `parseContent` (info.ts:166–193).
Python skeleton (field grammar in §2.9):

```python
def parse_basic_file_info(b: bytes) -> dict:
    ver = int.from_bytes(b[0:4], "little")   # 10 | 13 | 14  (2026 → 14)
    ...  # follow §2.9; strings are [i32 char_count][utf-16le]
```

Add the fields the official API exposes (A1) as the target output schema, and
keep phi-ag's own TODO: replace UTF-8 `True`/`False` tokens embedded in the
v14 content block. Test vectors: `vendor/phi-ag-rvt/src/node.test.ts`
(version/build/locale/identityId/documentId/path for all 11 releases) — copy
into our test suite verbatim.

### 4.3 `RevitPreview4.0` — `src/thumbnail.ts` → **port** (trivial)

`parsePreview` (thumbnail.ts:20): return bytes from the first
`89 50 4E 47 0D 0A` onward. Add the ~300-byte `62 19 22 05` wrapper decode
from rvt-rs `contents_probe.rs` when the metadata agent gets there.

### 4.4 `ElemTable` 40-byte hypothesis (README only) → adopt as the 2024+ layout

phi-ag README: after a 6-byte header `[u8 file_version_byte][u8 0x05][i32
entry_count]`, 40-byte records
`[i64 id][i32 u1][i32 u2][i32 u3][i64 id_again][i64 u4][i32 u5]`. Combined
with rvt-rs's project-2024 findings (§2.4) and our own 2026 measurement (§6.3:
`FF×8` markers, stride 40, first at 0x22), this gives a consistent picture:

```
2024+/2026 project ElemTable, records start 0x22, stride 40:
  +0   u64 marker = 0xFFFFFFFFFFFFFFFF
  +8   u32 (0)
  +12  u64 ElementId (id_primary)         ← phi-ag "Id"
  +20  u32 ×3 (0 on our sample; phi-ag "Unknown 1..3")
  +32  u64 ElementId again (id_secondary)  ← phi-ag "Id (2)"
  ... interpretation of the remaining ints unresolved
```

Header per rvt-rs: `[u16 element_count][u16 record_count]`; per phi-ag:
`[u8][u8 05][i32 total]` — our 2026 header (`c9 05 d1 20 …` = 1481, 8401)
fits rvt-rs's reading (§6.3). Port `rvt-rs elem_table::detect_layout` (below).

### 4.5 Corpus/tests → port

`examples/Autodesk/*.rfa` + `src/node.test.ts` → our cross-release
regression fixtures (metadata golden values 2016–2026).

---

## 5. What rvt-rs already solved and how to port it to Python

This is the section the brief *meant*. Ordered by value. All paths relative
to `vendor/rvt-rs/`. Where rvt-rs is provably wrong or unverified for our
2026 files, it is flagged.

| rvt-rs component | Port target | Notes / edits needed |
|---|---|---|
| `src/formats.rs::parse_schema` (line 536), `FieldType::decode` (line 327), `FieldType::encode` (line 461), `ClassEntry`/`FieldEntry`/`SchemaTable`, `tagged_ancestor` (line 161) | `src/rvt/schema.py` | Straight port (~400 lines Python). **Drop the 64 KB `SCHEMA_SCAN_LIMIT`** and instead solve decompression (corrections §1); expect far more than 400 classes if ZDI's 4,611 figure applies. Keep the record grammar of §2.1/2.2 and their 20+ pinning unit tests (`formats.rs` tests lines 900–1567) as our test vectors. |
| `src/compression.rs` (`gzip_header_len`, `inflate_at_with_limits`, `find_gzip_offsets`, `inflate_all_chunks`, `truncated_gzip_encode(+_with_prefix8)`) | already ≈ `tools/scan_gzip.py`; add encoder to `src/rvt/compression.py` | Same skip-header raw-inflate we use. **Both are silent on the trailer** — port must additionally *return the trailer* (CRC32, ISIZE, zero-pad length, trailing block) and *validate* CRC/ISIZE, flagging mismatches. Their encoder writes a bare 10-byte header + raw deflate with no trailer — S1 says Revit will reject that for streams needing an ECC. |
| `src/elem_table.rs::detect_layout` / `parse_records_from_bytes` / `parse_records` | `src/rvt/elem_table.py` | Port; our 2026 = the 40-byte variant. Add u64 interpretation (T5). |
| `src/partitions.rs::parse_header` / `find_chunks` | `src/rvt/partitions.py` | Port (44-byte header constant confirmed 2016–2026 and on our 2026 file, §6.5). |
| `src/streams.rs` (names, `partition_for_year` 2016=58 … 2026=69) | `src/rvt/streams.py` | Family-file mapping only; project files have arbitrary/multiple N (§6.6). |
| `src/basic_file_info.rs` (regex approach + `encode`) | fold into 4.2 | Weaker than phi-ag's grammar; take only the round-trip encoder idea and the two version-string patterns. |
| `src/part_atom.rs` (parse + `encode`) | `src/rvt/part_atom.py` | Port; also handle the **project variant**: `ProjectInformation` = ZIP → `*.project.xml` in the same `partatom` namespace (our finding, corrections §2). |
| `src/object_graph.rs::DocumentHistory` + `extract_string_records` | `src/rvt/global_latest.py` | Port the `[u32 tag][u32 char_count][utf16]` string-record scanner and the "Revit YYYY" history extractor. |
| `src/walker.rs` (`InstanceField`, `read_field_by_type` ~line 300, `read_adocument` 370, `find_adocument_start_with_schema` 421, `trial_walk` 499, `walk_score` 565, Container 2-column decoder 622) | `src/rvt/walker.py` | Port the wire-shape table (§2.3) and the entry-point heuristics as a starting point; treat outputs as **unvalidated** until decompression is fixed. |
| `src/class_tag_map.rs` + `docs/data/tag-drift-2016-2026.csv` | data file in `docs/data/` | Copy the CSV (attribution) — instant per-release tag lookup for the 122 tracked classes. |
| `src/corpus.rs` (per-byte Invariant/LowVariance/MonotonicInt/… delta classifier) | `tools/corpus_delta.py` | Nice generic technique for our 6-file corpus. |
| `src/arc_wall_record.rs` (2023 ArcWall) | reference only | 2023-only; use as the template for our per-record decoders once envelope is solved. |
| `src/writer.rs` (`write_with_patches`), `docs/cfb-structural-layout-2026.md` | Track D notes | Stream-level patch + re-gzip + CFB rebuild via `cfb` crate; not byte-identical (sector allocation); **no ECC** ⇒ per S1 likely rejected by Revit for the big streams. |
| `reports/element-framing/RE-*.md`, `docs/rvt-moat-break-reconnaissance.md`, `docs/re/revit-wire-format-landscape-2026-04-21.md`, `docs/project-file-corpus-probe-2026-04-21.md` | required reading for the partitions/ElemTable/Latest agents | Read these before probing; they contain 20+ refuted hypotheses (chunk headers, offsets-in-ElemTable, ancestor-tag lookup, TLV directory = ADocument, Q7 trailer table …). |

### 5.1 Methodological transfers (independent of code)

1. **Tag-density statistics**: count u16 occurrences of every schema tag vs
   the uniform baseline (`positions/65536`); ratios ≫ 1 are real record
   classes. Second-stage filter `buf[pos+2:pos+4]==b"\0\0"` separates real
   records from UTF-16 text coincidences.
2. **Cross-release delta classification** (invariant / low-variance /
   monotonic / variable bytes) to find structure without semantics.
3. **11-release oracle**: any hypothesis must survive 2016–2026 (their corpus
   + ours). Cheap, decisive.
4. **Concrete-class thinking**: forget `Wall`; look for `ArcWall`/`VWall`/…
   and their per-release tags.
5. **Negative results are catalogued** (RE-09, Q6.3, Q6.4, RE-18, Q7): read them
   before repeating.

---

## 6. Sibling formats and cross-corpus verification (our analysis)

All numbers below produced today with `olefile`/`zlib` against
`vendor/*` and `samples/`; offsets are byte offsets in the named stream.

### 6.1 `BasicFileInfo` (racbasicsampleproject.rvt, 2026)

`0x00: 0e 00 00 00` (fileVersion = 14, phi-ag "v14" ✔), `0x0e: 04 00 00 00`
(v13+ version marker ✔), `0x12: "2026"` UTF-16, `0x1a: 12 00 00 00` (18-char
string) + `"20250227_1515(x64)"` — phi-ag's `parseVersion13` grammar holds on
a 2026 *project* file (their corpus is families only).

### 6.2 `Formats/Latest` first class record (all six 2026 files identical)

Inflated `0x0000: 00 00 0d 00 "A3PartyAImage" 0d 80 00 00 0d 00
"A3PartyObject" …` → u16 len 13, name, u16 `0x800d` = **tag 0x000d with
the 0x8000 tagged flag** — exactly rvt-rs's grammar, and `A3PartyAImage=0x000d`
is one of their six 2016–2026 stable tags. `KNOWLEDGE.md`'s "length-prefixed
class names" is the same record.

### 6.3 `Global/ElemTable` (racbasic 2026, inflated 336,070 B)

`0x00: c9 05 d1 20` → u16 element_count = 1481, u16 record_count = 8401
(rvt-rs header ✔). First `FF×8` markers at 0x22, 0x4a, 0x72, 0x9a ⇒
**stride 40, explicit 8-byte marker, records start 0x22** = rvt-rs's
"project 2024" variant and phi-ag's 40-byte hypothesis. Record 0:
`0x22: FF×8 | 00 00 00 00 | 02 00 00 00 …`.

### 6.4 Compression trailers (all six files) — see corrections §1

For every gzip'd stream the deflate data is followed by
`[u32 CRC32][u32 ISIZE][N zero bytes][M trailing bytes]`. Streams whose
inflated size is small **validate** (e.g. racbasic `Global/History`:
CRC32 `0xa3525784`, ISIZE 15,290 — both match; racbasic
`Global/ElemTable`: `0xeb4f97d1` / 336,070 — match). Every
`Formats/Latest` (ISIZE 496,597 vs 498,766 inflated), every `Global/Latest`
(e.g. racbasic ISIZE 1,500,644 vs 1,506,910) and every large
`ContentDocuments`/`ElemTable` **mismatch**, and the inflated
`Formats/Latest` shows LZ77-desync-style garbling from ~0x22000 (first
anomaly `0x222c0`: `"…ueDateeeeeeee\x05\x00…"`). This is the ZDI "ECC
trailer" (S1) plus something we do not yet decode correctly.

### 6.5 `Partitions/15` (racbasic 2026)

Raw `0x00: 09 00 00 00 00 00 00 00 a3 03 00 00 00 00 d1 20 00 00 28 0f 04 00
00 00 a0 02 00 00 4c 3f 00 00 0c d5 01 00 65 00 00 00 00 00 00 00`, first gzip
magic at **offset 44** ⇒ rvt-rs's 44-byte header constant holds on Revit
2026. (1,156 `1F 8B 08` triplets in the stream; some are coincidences — the
inflate-what-inflates approach both projects use is the right one.) Note
`0x0e: d1 20` = 8401 = the ElemTable record_count (u16) — a cross-stream
constant worth handing to the partitions agent, and `a3 03` (931) recurs in
`ContentDocuments`/`Global/Latest` heads (§6.7).

### 6.6 Container equivalence and family/project differences

Stream inventories measured today:

| Stream | 11 phi-ag RFAs (2016–2026) | 4 magnetar RFAs (2023) | Einhoven .rvt 2023 | Core Interior .rvt 2024 | our six .rvt 2026 |
|---|---|---|---|---|---|
| `BasicFileInfo`, `Contents`, `Formats/Latest`, `Global/{ContentDocuments,DocumentIncrementTable,ElemTable,History,Latest,PartitionTable}`, `TransmissionData` | ✔ | ✔ | ✔ | ✔ | ✔ |
| `RevitPreview4.0` | ✔ | ✔ | ✔ | ✔ | 5/6 (absent in rstbasic ⇒ optional) |
| `PartAtom` (plain Atom XML) | ✔ (incl. 2026) | ✔ | — | — | — |
| `ProjectInformation` (ZIP → `…\Revit<GUID>.project.xml`, same `partatom` namespace) | — | — | ✔ | ✔ | ✔ |
| `Partitions/N` | exactly 1 (N: 58,60…69, +1 per release the file passes through) | 1 (`Partitions/0`) | 7 (`0–6`) | 8 (`46,48,51,53,55,59,61,65`) | 1 (`12…21`) or 2 (dach: `84,85`) |

Conclusions: **.rfa/.rte/.rft and .rvt share the container and stream
grammar**; the family-specific `Partitions/N` numbering (N increments each
release the *same file* is upgraded — the phi-ag file has been upgraded
yearly since 2016) is a save/upgrade counter, not a version constant, which
is why project files show arbitrary N and several partitions. Our
`KNOWLEDGE.md` PartAtom claim must be reworded (corrections §2).

`Global/PartitionTable` (racbasic 2026, inflated 87 B): `0x00: 80 0c` =
3200 (rvt-rs's per-release counter value for 2026 ✔), `0x0a` GUID bytes
`f8 52 e0 e3 56 01 d5 11 93 01 00 00 86 3f 27 ad` →
`{e3e052f8-0156-11d5-9301-0000863f27ad}` (UUIDv1, **same node
`0000863f27ad`** as the family GUID rvt-rs found — supports "Autodesk
build-machine UUIDv1s minted ~2000"), then `[u32 str_len=0x38? …][ffffffff]
[…]["Workset1" UTF-16]…`. Project layout = rvt-rs's 87-byte project variant.

### 6.7 `Global/Latest` / `Global/ContentDocuments` heads (racbasic 2026)

`Global/Latest` inflated `0x00: 1c 00 00 00 00 00 00 00 00 00 ff ff ff ff
a7 03 01 00 00 00 ff ff ff ff a0 01 ff ff ff ff 66 10 … e9 0a ff…` then at
`0x53: 08 00 00 00 | 45 00 00 00 | "Revit 2018 - Preview Pre-Release …"` and
at `0x35f` `"Revit 2026 2026 (20250226.000) : 20250227_1515"` — rvt-rs's
`[u32 tag][u32 char_count][utf16]` upgrade-history records ✔ (their first
tag `0x00000007` differs; ours starts with `0x08` — a per-file variation to
note). `Global/ContentDocuments` starts `a3 03 ffffffff a2 03 ffffffff …`
(u32 id pairs 931, 930), i.e. the **2023-style u32 layout**, not rvt-rs's 2024
40-byte u64 linked list — the 2026 stream evidently differs again; do not
assume the 2024 layout.

---

## 7. Recommendations to the orchestrator

1. **Compression first.** Make the truncated-gzip decoder report and check
   `CRC32/ISIZE`, decode the zero-pad + trailing block, and resolve the
   large-stream divergence (corrections §1). Every downstream layer
   (schema >64 KB, `Global/Latest` instance mass, `ContentDocuments`,
   partitions) currently reads possibly-corrupted bytes. Locate the ECC/gzip
   routines in `Utility.dll` per ZDI if a Windows box is available.
2. **Adopt rvt-rs's schema grammar and field-type table wholesale** (port
   `formats.rs`), then re-derive on our 2026 corpus without the 64 KB cap.
3. **Use the magnetar corpus as ground truth**: `2024_Core_Interior.rvt` +
   its own `2024_Core_Interior.ifc` export gives element counts/geometry to
   validate decoders — something rvt-rs never had wired up.
4. **Do not re-run refuted probes** (list in §5.1 item 5).
5. **Writer track (D)**: assume Revit validates the trailing ECC block on at
   least the large streams (S1). A writer must (a) reproduce Revit's gzip
   framing, (b) recompute the ECC, or (c) discover whether Revit accepts a
   stream form without ECC (worth an experiment: small streams in real files
   have small trailing blocks too, so probably not optional).
6. **Attribution/licensing**: rvt-rs is Apache-2.0, phi-ag/rvt MIT, DROID
   BSD-3, magnetar MIT, Autodesk samples CC-BY-NC-SA. Ports must carry
   NOTICE lines; the tag-drift CSV needs attribution.

---

## 8. Local mirrors created by this agent

| Path | What |
|---|---|
| `vendor/phi-ag-rvt/` | phi-ag/rvt @ HEAD (2026-08-01), with all 11 `examples/Autodesk/*.rfa` LFS objects materialised (sha256-verified) |
| `vendor/rvt-rs/` | DrunkOnJava/rvt-rs @ 21aa0e0 (2026-04-25); read `README.md`, `docs/rvt-moat-break-reconnaissance.md`, `reports/element-framing/`, `src/{formats,walker,elem_table,partitions,compression,object_graph}.rs` |
| `vendor/magnetar-revit-test-datasets/` | magnetar-io/revit-test-datasets @ HEAD with `.rvt/.rfa/.ifc` LFS objects materialised (2 projects + 4 families + IFC exports) |

Analysis scripts used for §6 were ad hoc (per the write-path rules of this
task) and are reproduced inline in `docs/inbox/prior-art-corrections.md`.

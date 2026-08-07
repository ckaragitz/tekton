# Inbox — prior-art corrections to KNOWLEDGE.md (agent: prior-art-format)

Date: 2026-08-02. Companion to `docs/prior-art.md`. Each item: the current
claim, the contradicting/refining source, my own byte-level check, and the
suggested rewrite. Ordered by impact. Everything here is a *proposal* for the
orchestrator to merge; I have not edited `KNOWLEDGE.md`.

---

## 1. CRITICAL — the gzip trailer is not "corrupt/absent", and large streams do not inflate correctly

**KNOWLEDGE.md says** (Compression): "valid 10-byte gzip header with a
corrupt trailer … correct method: skip 10 bytes and raw-inflate … after each
deflate stream there are ~270–712 bytes of trailing data (not the 8-byte gzip
trailer) — an as-yet-undecoded footer".

**Prior art:** ZDI blog (2025-10, CVE-2025-5037, Revit 2025 —
<https://www.thezdi.com/blog/2025/10/6/crafting-a-full-exploit-rce-from-a-crash-in-autodesk-revit-rfa-file-parsing>)
states `Global\Latest` = *header + gzip payload + zero padding + ECC
trailer*; "Revit will auto-repair small perturbations to the stream using
the ECC trailer and will reject streams that don't match the ECC"; naive
gunzip→edit→gzip does not round-trip; the gzip and ECC routines are in
`Utility.dll` (public symbols + diagnostic strings). ZDI built a wrapper
that calls Revit's own DLL entry points to gzip/gunzip and recompute ECC.

**My check (all six 2026 files, `zlib.decompressobj(-15)` on `raw[hdr+10:]`):**

The 8 bytes immediately after the deflate data are a **well-formed gzip
trailer `[u32 CRC32][u32 ISIZE]`**, followed by a run of zero bytes, followed
by a variable-length trailing block (the ZDI "ECC"). Whether the trailer
*validates* depends on stream size:

| Stream (racbasic 2026) | deflate len | inflated | CRC32 field | ISIZE field | valid? | zero pad | trailing block |
|---|---:|---:|---|---:|---|---:|---:|
| Global/PartitionTable | 71 | 87 | `0x8074fb61` | 87 | ✔ | 0 | 37 |
| Global/DocumentIncrementTable | 771 | 3,710 | `0x0fdc0228` | 3,710 | ✔ | 6 | 59 |
| Global/History | 14,024 | 15,290 | `0xa3525784` | 15,290 | ✔ | 5 | 91 |
| Global/ElemTable | 49,801 | 336,070 | `0xeb4f97d1` | 336,070 | ✔ | 308 | 273 |
| Global/Latest | 116,542 | 1,506,910 | `0x1ad5050d` | 1,500,644 | ✘ (Δ 6,266) | 343 | 281 |
| Formats/Latest | 182,231 | 498,766 | `0x26852216` | 496,597 | ✘ (Δ 2,169) | 420 | 284 |
| Global/ContentDocuments | 818,266 | 5,106,253 | `0xcf85fbd1` | 5,080,768 | ✘ (Δ 25,485) | 70 | 193 |

Across all six files: every `History` / `DocumentIncrementTable` /
`PartitionTable` and the racbasic `ElemTable` (336,070 B inflated)
**validate**; every `Formats/Latest` (byte-identical, ISIZE 496,597),
every `Global/Latest`, every `ContentDocuments`, and every `ElemTable`
above ~500 KB inflated **do not** — our inflate produces ~0.4–0.5 % *more*
bytes than ISIZE and a non-matching CRC (Δ: Formats 2,169; racbasic Latest
6,266; rst Latest 7,003; dach Latest 24,041; ContentDocuments 25,485;
rstbasic ElemTable 2,547; racadv ElemTable 3,072). Additionally these streams
fail to inflate at all with zlib in some files: dach `Global/ElemTable`
("invalid block type"), dach + racadv `ContentDocuments`, rme `ElemTable`
("invalid code lengths set") — and correspondingly **`extracted/<file>/*.gz`
has no `index.json` for those streams: the current corpus is missing data**.

Where the mismatch shows in content: the inflated `Formats/Latest` is clean
schema through the first ~139 KB and then shows classic LZ77-desync
artifacts (first anomaly `0x222c0`: `"…ueDateeeeeeee 05 00 44 00 02 …"`;
runs like `eeeeeeeeeeee`, `OOOOOOOOOOOO`, jumbled type names
`"class std::vector<…"` → `"sDBWithDatu_Fi", "eIdompp@th"`), density
increasing toward the end. A pure-Python inflate (bit-identical to zlib on
this stream) shows the bitstream itself is well-formed and *standard*:
10 blocks (7 dynamic, 2 fixed, 1 stored), max distance 32,505, max length
241, no length code 285, no distance codes 30/31 — so **not Deflate64**
(the `inflate64` Python package reproduces zlib's output byte-for-byte on
`Formats/Latest` and errors on the others). The garbling is therefore
either (a) genuine content (unlikely: the writer's own CRC/ISIZE disagree
with it) or (b) our decode diverging from the encoder's input. rvt-rs never
noticed (its `inflate_at` ignores the trailer, and it caps schema parsing at
64 KB with the note "beyond this … binary noise").

**Hypotheses to test (for the compression agent):**

- H1 (favoured): the compressed bodies of large streams are **deliberately
  perturbed and only decodable after applying the ECC repair** described by
  ZDI ("auto-repair … using the ECC trailer") — i.e. ECC-decode the
  compressed stream first, then gunzip; small streams may be below a
  perturbation threshold. The trailing-block sizes are *not* proportional
  to stream size (37–350 B; `91` recurs across unrelated streams), so if it
  is Reed-Solomon-like it is over a fixed layout, not a fixed rate — inspect
  `Utility.dll` (strings mention ECC per ZDI) on a Windows box.
- H2: large streams are written by a chunked writer whose CRC/ISIZE
  counters exclude periodic in-band records (~1 byte per ~200–250 payload
  bytes); the divergence in `Formats/Latest` would then be interleaved
  records, but the observed jumbling argues against clean interleaving.
- H3: the trailing block after the zero padding contains a table needed to
  reassemble/patch the payload (offset/length fix-ups).
- Cheap discriminator: obtain a `Formats/Latest` for the same build from a
  different channel (e.g. the schema inside a magnetar 2024 RFA vs 2024
  project — rvt-rs found 17,266 byte-identical bytes across variants) and
  diff the inflated outputs; also check whether any of the 11 phi-ag RFAs
  (their `Formats/Latest` inflated 473 KB per rvt-rs) validates.

**Suggested KNOWLEDGE.md rewrite:** "Every gzip'd payload is
`[10-byte gzip header][raw DEFLATE][u32 CRC32][u32 ISIZE][zero padding]
[variable trailing block ('ECC' per ZDI)]`. Raw-inflating from header+10
recovers the payload **and validates CRC32/ISIZE for streams up to ~350 KB
inflated**; for `Formats/Latest`, `Global/Latest`, `ContentDocuments` and
large `ElemTable`s the same procedure yields ~0.45 % extra bytes, a CRC
mismatch and visibly corrupted content (Formats/Latest degrades past
~0x22000) — decoding of large streams is UNSOLVED; treat all analysis of
inflated bytes beyond the first divergence as suspect. Revit itself
verifies/repairs streams via the trailing ECC (ZDI 2025)."

Also add: `Formats/Latest` is byte-identical across our six files, so its
CRC/ISIZE (`0x26852216` / 496,597) is a fixed oracle for testing candidate
decoders.

## 2. `PartAtom` / `ProjectInformation` — hypothesis confirmed, wording wrong

**KNOWLEDGE.md says:** "No `PartAtom` stream in these Revit 2026 files
(older docs assume one). [hypothesis] its role moved into
`ProjectInformation` (a ZIP archive)."

**Facts:** `PartAtom` is a **family-file** stream (present in the 2026 phi-ag
RFA and all 4 magnetar RFAs; plain Atom XML, `xmlns:A="urn:schemas-autodesk-com:partatom"`,
`link type="application/rfa"` — DROID container signatures use exactly that
literal to tell families from projects). `ProjectInformation` is the
**project-file** analog, present in every `.rvt` I inspected (ours, magnetar
2023/2024, the 2018 RE.SE case): a ZIP (`PK\x03\x04`) with one member named
`C:\Users\<user>\AppData\Local\Temp\<guid>\Revit<guid>.project.xml`, whose
content is the same Atom/partatom document with `link type="application/rvt"`,
`<A:product-version>2026</A:product-version>` and the project-information
parameters (`Organization_Name`, `Author`, `Project_Issue_Date`, …).
Nothing "moved"; the two file classes carry different streams.

**Rewrite:** "Families (.rfa/.rft) carry `PartAtom` (plain Atom XML);
projects (.rvt/.rte) carry `ProjectInformation` (ZIP-wrapped
`*.project.xml`, same `partatom` namespace). Presence of `PartAtom` vs
`ProjectInformation` distinguishes family from project files (DROID
fmt/1349-1351 use `"application/rfa"` in `PartAtom`)."

## 3. The 8-byte `Global/*` prefix — refine both ways

**KNOWLEDGE.md:** prefixes `05 00…`, `00 00…`, `01 00…`, meaning TBD.
**rvt-rs claims** the prefix is `[u32 0][u32 0]` "in every file we've
inspected" (`compression.rs::truncated_gzip_encode_with_prefix8`) — **wrong
for our 2026 project files** (`Global/Latest`=`05`, `Global/History`/
`ContentDocuments`/`DocumentIncrementTable`=`01`, `Global/ElemTable`=`00`)
and rvt-rs's own later note says a 2025 project's `Global/History` had *no*
prefix at all (gzip magic at offset 0) — hence their `inflate_at_auto`
(scan for first magic). Also record the sibling wrapper: `Contents` and
`RevitPreview4.0` do not use the 8-byte prefix; they use the `62 19 22 05`
custom-wrapper header (rvt-rs) — our `Contents` head is
`62 19 22 05 1c 00 00 00 01 00 00 00 00 00 00 00 62 19 22 05 b7 00 00 00`
then gzip.

**Rewrite:** keep our observed byte values; add "prefix is optional in
some 2025+ project files; scan for the first `1F 8B 08`", and the
`62 19 22 05` wrapper family for `Contents`/`RevitPreview4.0`.

## 4. `Partitions/<N>` — refine

**KNOWLEDGE.md:** "binary header (`09 00 00 00 00 00 00 00 a3 03 00 00 …`),
then ~131 KB independently-gzipped blocks (876 in racbasic)". Refinements:

1. Header is exactly **44 bytes** (rvt-rs, constant 2016–2026; our racbasic
   `Partitions/15` has its first gzip magic at offset 44 ✔). rvt-rs's field
   reading: `[u32 count+1][u32 0][12 B size block][4×u32 trailer]`; the four
   trailer u32s are **not** per-chunk offsets (tested, refuted). Our head:
   `a3 03` (931) recurs at the top of `Global/Latest` and `ContentDocuments`;
   `d1 20` (8401) = the `ElemTable` u16 record_count.
2. Gzip-chunk boundaries are **compression pagination, not record
   boundaries** (rvt-rs RE-09): records span chunks; concatenate all
   inflated chunks into one logical buffer before parsing. (Given §1, each
   chunk's own CRC/ISIZE should be checked — the ~131 KB inflated chunk
   size we see is small enough that most chunks may validate.)
3. Project files can have **many `Partitions/N` streams** (magnetar 2023:
   `0–6`; 2024: `46,48,51,53,55,59,61,65`; our dach: `84,85`). N is not a
   version constant for projects; only the single family stream tracks
   58…69 per release (it increments each time that same file is upgraded).
4. "876 members" vs a raw scan finding 1,156 `1F 8B 08` triplets in
   racbasic `Partitions/15`: some triplets are coincidences that fail to
   inflate (rvt-rs skips such chunks silently) — worth stating how our count
   was derived.

## 5. Corpus-quality flag (tools/scan_gzip.py output)

The following streams have no carved/inflated members in `extracted/`
(zlib raw-inflate fails mid-stream — see §1): dach `Global/ElemTable`,
dach `Global/ContentDocuments`, rme `Global/ElemTable`, racadv
`Global/ContentDocuments` (verify: no `index.json` in the `.gz/` dirs).
Agents relying on those streams currently see nothing/partial data. Also
`racbasicsampleproject/Global__ElemTable` was carved in `"gzip"` mode
(CRC-validated) while others were `"raw+10"` — worth recording per stream
whether the trailer validated.

## 6. Additions that agree with / extend KNOWLEDGE.md (no conflict, worth merging)

1. **Class tags**: after each class name in `Formats/Latest` a u16 with the
   `0x8000` bit set gives the class's serialization tag (`A3PartyAImage` =
   `0x800d` at inflated offset 0x11 in every one of our six files); tags
   drift per release; only ~80/400 classes are tagged; instance data is
   schema-directed and tag-referenced (rvt-rs) — and ZDI confirms the
   runtime deserializer reads a **u16 class index** (`AString`=0x1f in
   2025, 4,611 registered classes, class maps via
   `Utility!ArchiveClassMaps::loadClass`). ⇒ `Formats/Latest` is the file
   copy of the archive class map; expect thousands of classes once §1 is
   solved (rvt-rs's 64 KB scan cap is an artefact).
2. **ElementIds are 64-bit since Revit 2024** (Tammik 2022 post); our 2026
   `ElemTable` uses the 40-byte record variant with `FF×8` markers, first
   record at inflated offset 0x22, stride 40, header `[u16 element_count=1481]
   [u16 record_count=8401]` (racbasic) — matches rvt-rs "project 2024"
   layout and phi-ag's 40-byte hypothesis.
3. `Global/PartitionTable` (racbasic 2026, 87 B inflated): u16 `0x0c80` =
   3200 at 0 (rvt-rs's per-release counter, 2026 value ✔), UUIDv1
   `{e3e052f8-0156-11d5-9301-0000863f27ad}` at 0x0a (same
   `…0000863f27ad` node as the family-file GUID rvt-rs published; the value
   differs per project), then `"Workset1"` UTF-16 — the project-file layout.
4. Official readable/writable surfaces without opening the model:
   `BasicFileInfo.Extract`, `TransmissionData.ReadTransmissionData /
   WriteTransmissionData` (Revit API) — use as oracles for our
   `BasicFileInfo`/`TransmissionData` codecs.
5. Format identification: PRONOM fmt/1346–1351 with DROID container
   signatures (streams `Formats`+`BasicFileInfo`; UTF-16LE `"Revit Build:"`
   ≤2018 or `"Author: Autodesk Revit\r"` near EOF for 2019+; `PartAtom`
   containing `"application/rfa"` for families).
6. `RevitPreview4.0` is optional (absent in `rstbasicsampleproject.rvt`).
7. Task-brief erratum: `phi-ag/rvt` is **TypeScript** (npm `@phi-ag/rvt`,
   Peter Hirn), not Rust; the Rust reader is `DrunkOnJava/rvt-rs` (Griffin
   Long). Neither README mentions an OpenDAL affiliation.

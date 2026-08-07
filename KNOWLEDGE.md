# KNOWLEDGE — established facts, decisions, gotchas

Append learnings as they happen. Orchestrator merges agent inbox notes here.
Everything below is verified against the six sample files unless marked
`[hypothesis]`.

## Container

- `.rvt` is a **Microsoft OLE2 / Compound File Binary (CFB)** document. Readable
  with `olefile`. No encryption on the container.
- Stream inventory is small and stable across projects (12–14 streams):
  - `BasicFileInfo`, `Contents`, `ProjectInformation`, `TransmissionData`,
    `RevitPreview4.0` (optional), `Formats/Latest`, and under `Global/`:
    `Latest`, `ElemTable`, `PartitionTable`, `ContentDocuments`, `History`,
    `DocumentIncrementTable`, plus one (rarely two) `Partitions/<N>`.
- **No `PartAtom` stream in these Revit 2026 files** (older docs assume one).
  `[hypothesis]` its role moved into `ProjectInformation` (a ZIP archive).

## *** NATIVE WRITER PROVEN END-TO-END (2026-08-03, V15) ***

- V15 = the WHOLE rstbasic file re-written by us — every ECC-framed stream
  recompressed by our gzip and re-framed with recomputed CRCIO trailers;
  the Autodesk Viewer translated and rendered it (full {3D} + sheet set
  identical). Every framed byte on disk was produced by our writer.
  => CFB container + zlib framing + block framing + per-page ECC are all
  correct and accepted. See docs/acceptance-log.md (Batch 3).
- The writer chain (all proven byte-exact): `objects.py` (decode) +
  `encode.py` (100.000% round-trip, 1,153,554 records / 397 classes) +
  `stream_encoders.py` (36/36 small streams) + `partitions.py` framing +
  `writer.gzip_member(level=3, sync_flush=True)` + `ecc.frame_stream` +
  `cfb_writer.write_cfb`.

## Authoring semantics — SOLVED (wave 3, mutation-planner + stream-encoders)

- **Record stamp SOLVED:** the u32 stamp in seq-102/103 record headers =
  `zlib.adler32(u16 class_id + object bytes)`; verified 287,441/287,441
  records (independently re-checked 200/200). Sentinel stamp 1 =
  adler32(empty); SerializedDummy constant 0x0069003C = adler32(2c 0f).
  Editing any object requires recomputing its record stamp (the DLL's
  exported `Adler32::*` is THIS mechanism, not the page ECC).
- **Save units are DOCUMENTS, not saves:** in Partitions/N, save-unit 0 =
  the host document (its seq-102 ids == Global/ElemTable ids EXACTLY, set
  equality in all files); units 1..k = one embedded family/content
  document each (separator GUID = its ContentDocuments key; separator u32
  counter = its record count). ElementIds are unique file-wide.
- **Element-creation recipe [decided by evidence]:** insert THREE records
  per new element (seq 101 ElementHeader / seq 102 object / seq 103
  GElement-or-SerializedDummy) into save unit 0; append one 40-byte
  ElemRec to Global/ElemTable with id = watermark+1 (ElemTable footer
  `IdentifierSource.m_last` = monotonic highest-ever-issued id; racbasic
  1,098,947 vs max live id 1,098,851); record the save (new
  DocumentIncrementTable row, new History episode, BasicFileInfo GUID/
  increments); re-block ONLY unit 0, copy embedded units byte-for-byte;
  keep the same Partitions/N (N = current major increment − 1). Revit
  rewrites the whole stream each save; it does not append save units.
  The sentinel record (id −1, psize 0) is always the LAST record of each
  unit's per-seq segment; the three seqs must carry identical id sets.
- **Cross-stream save invariants (verified 6/6 files):** History count ==
  max(ElemRec.modified_ep)+1; DIT newest id_pair == (History count−1,
  History count); BasicFileInfo 'Unique Document Increments' ==
  central_version_number == DIT record count; BFI Unique Document GUID ==
  History entry[0]; Contents.counters == newest DIT counters with index 7
  removed and Contents.G == DIT G; Partitions header count == ElemTable
  count. `streams_edit.record_save()` applies them; `save_impact(N)`
  reports what changes when N elements are added.
- Instantiation patterns [verified]: doors/windows reference a per-host
  geometry-symbol CLONE (host-cut instances = phase 2); free/face
  instances use symbolId == masterSymbolId; ALL rme electrical equipment
  is FACE-HOSTED (m_workPlaneBased, host = a SketchPlane on the wall
  face) — panelboards/receptacles need a SketchPlane host record too.
- Geometry: levels/grids/families/circuits carry SerializedDummy reps;
  walls/rooms/symbols/instances carry GElement. New instance reps are
  ~300–600-byte formulaic GElement{GInstance{InstanceInfo}} (clonable);
  new walls may emit SerializedDummy relying on regeneration (test T2).
- 19 complete decoded real specimens (level, grid, wall, wall type,
  door + symbol + family, room; MEP panelboard/circuit/receptacle/space/
  connector) live in `docs/writer/specimens/*.json` — the templates for
  authoring. Plan: `docs/writer/mutation-plan.md`; catalog of loaded
  types/symbols per template file: `docs/writer/template-catalog.md`.

## Element creation — COMMIT LAYER (wave 3+, `src/rvt/commit.py`)

- `commit_new_elements(src, out, [ {seq: record_bytes}... ], [ElemRecPlan...])`
  is the writer's final assembly: appends each new element's three
  records (seq 101/102/103) into save-unit 0 immediately BEFORE the per-seq
  sentinel (which stays last), recomputes the touched block's counters
  (A += n; C from the identity ISIZE == hdr_len(seq)*A + C + adj(flags),
  adj = {4:0, 5:+4, 6:-4, 7:0}), recompresses every block (B), appends the
  ElemRecs to Global/ElemTable (id-sorted, watermark raised), bumps the
  partition header elem_table_count (u32 @ logical offset 14), re-frames
  both streams with real ECC and rebuilds the container. New ElemRecs reuse
  an EXISTING episode so the History invariant holds without touching
  save-history streams (minimal commit; `streams_edit.record_save()` layers
  a full save on later). `verify_written()` proves CRC/ECC/walker/stamps/
  counts/sentinels and re-decodes the new element in all three seqs.
- Unit-0 block layout: blocks group by seq in stream order (rstbasic:
  22 x seq101, 127 x seq102, 64 x seq103), so appending before each
  sentinel touches only the LAST block of each run. Records span blocks
  only when huge (seq-102 max body 487 KB); appended records fit whole.
- `rvt.mutate.Document.serialize()` now works via the module-level
  `rvt.encode.encode_record(seq, id, stamp=None, class_id, obj)` adapter,
  which encodes the object and computes stamp = adler32(u16 class||body).
- Element-creation API in use: `Document.add_family_instance(symbol_id,
  level_id, position(ft), rotation, template_instance_id)` (free-standing
  pattern: symbolId == masterSymbolId, hostId -1) and `add_wall(...)`;
  placement lives at `m_pInstanceInfo.value.m_Trf.m_or` (+ mirror
  `m_instOrigin`). First created element = V20 (a 450x450 concrete column,
  id 1,472,525 = watermark+1) — acceptance pending in the viewer.

## *** THE GOAL — ACHIEVED (2026-08-03) ***

- **Design IFC / spec -> native .rvt is PROVEN end-to-end, and created
  geometry is VISUALLY CONFIRMED.** Chain: Claude-Design IFC ->
  `tools/ifc_to_spec.py` (ifcopenshell: storeys -> levels, IfcWall ->
  walls, or 4 perimeter walls synthesized from a room-shell proxy/space
  footprint, IfcElectricDistributionBoard -> panelboard, IfcTransformer
  -> transformer, positions/rotation/elevation from ObjectPlacement, dims
  from geometry bbox, psets carried over) -> spec.json ->
  `tools/spec_to_rvt.py` (rme MEP template: add_wall + add_family_instance,
  commit_new_elements, verify_written) -> .rvt accepted by Autodesk.
  V23 (spec) / V25 (from IFC, zero hand-authoring) / V26 (+ synthesized
  walls) all translate. VISUAL PROOF: the whole-model {3D} of a generated
  file shows the building smaller (extents grew) plus a detached cluster
  at the room's offset location, vs the untouched control (V24) filling
  the frame — created elements are real rendered geometry.
- Equipment templates in rme: panelboards on symbol 619617 (480V MCB
  Surface :: 400 A, from hosted instance 742670 with host removed),
  transformers on 621242 (Dry Type 480-208Y120 :: 500 kVA, free-standing
  instance 624416), switchboard 629946 (free-standing). Free-standing
  placement of the wall-family panelboard IS accepted by the translator.
- Remaining honest gaps: panels placed UNHOSTED (v1; face-hosting on new
  walls needs SketchPlanes); circuits / panel schedules NOT authored
  (connector managers are cloned, no ElectricalSystem creation yet);
  target release fixed at Revit 2026 (per-release schema); commercial
  .rvt-write needs legal review.

## Electrical circuits (RbsElectricalSystem) — MODEL SOLVED (2026-08-03)

Ground truth from 187 circuits in the rme sample (e.g. circuit 469428
"Power Technology 28": 9 receptacle loads on one panel):
- A circuit (`RbsElectricalSystem`, class 0x0D87, seq-103 rep =
  SerializedDummy — no geometry) OWNS one connector per member LOAD plus a
  FINAL connector for its BASE EQUIPMENT (the feeding panel):
  `conn[0..n-1].refs -> {load_id, load_supply_conn(~1), connType 1}`;
  `conn[LAST].refs -> {panel_id, panel_slot, connType 4}`;
  `m_baseConnectorIdArray = [{self, LAST, connType 4}]`;
  `m_pathNodes[0].m_elemId = first load`.
- Back-links (both sides, `connType 4`): each load's supply connector
  `refs -> {circuit, i}`; the panel's SLOT connector `refs -> {circuit, LAST}`.
- **Panel connectors:** the 50000-series (50000, 50001, ...) are the
  per-circuit SLOTS — one circuit each, NEVER shared (a panel referenced by
  23 circuits uses 23 distinct slots). A panel's low index (1) is its OWN
  incoming supply, used when the panel is itself a MEMBER of an upstream
  feeder (e.g. transformer 622028 -> panel 622027 in circuit 623656: the
  transformer's 50000 connector is the BASE, the 208 V panel's conn 1 is a
  member — i.e. "transformer secondary feeds panel", NOT panel-feeds-xfmr).
- Header parents: `m_deletion = {panel, loads..., self, cableType,
  cableSizeElementId}`, `m_appearanceParents = {panel, loads...}`.
- `Document.add_circuit(panel, load, ...)` implements this recipe for
  elements CREATED IN THE SAME COMMIT (mutual links wired pre-serialize);
  auto-allocates the next unused 50000-series panel slot and the load's
  lowest supply connector. Circuiting EXISTING elements needs in-place
  record edits (phase 2). Graph-closure verified on V29 (3 circuits).

## Connector hygiene for created equipment (fixed 2026-08-03)

Cloned equipment must NOT keep the template's connector `m_arrRefs`
(dangling one-way links into the template's circuits) — new gear starts
UNCONNECTED (`Document._scrub_connectors`), and template selection must be
an exact symbol match first (`_template_instance` two-pass) so a panel is
never born with a transformer's connector set (5 vs the panel's 11).

## Global/Latest (the ADocument) — FULLY SOLVED (2026-08-03)

- Global/Latest logical stream = u64 prefix 5 + u16 class 0x1c (ADocument)
  + the ADocument OBJECT GRAPH + constant trailing u32 0 — the SAME
  schema-directed serialization as element records. rvt.objects.
  ObjectDecoder decodes it with TWO hooks (src/rvt/adocument.py): archive
  pid seed {1} (the document is archive object #1; weak refs to it are
  u32 1; first indexed sub-object = pid 2) and a lifted container cap.
  ObjectEncoder re-serializes byte-exact with NO change. Coverage
  100.0000%, 0 errors, byte-exact round trip on all six samples + G0.
  There are NO undecoded regions. (TRACKER G1a technically CLOSED.)
- The "Forge JSON corpus" (~1.33 MB, 84% of Latest) = ESSchemaStorage:
  893 unit + 422 spec/parameter-group (typeid, json) pairs — Autodesk's
  installed Revit Unit Schemas, BYTE-IDENTICAL in all six samples = shipped
  PRODUCT DATA (like Formats/Latest), NOT sample authorship; not published in
  any public autodesk-forge repo => counsel item, not a copy-of-sample issue.
- AppInfoManager.m_appInfoArr = FIXED 241-slot registry (168 always
  populated); a document's dangling ids live in LIVE registries
  (category/style catalogue, per-class trackers, positional singleton
  table, view index) — NOT a deletion graveyard.
- READER FACTS (viewer bisection 2026-08-03): Latest-DANGLING references are
  NOT fatal (R5, R9 with thousands PASS). Removing embedded family
  documents / splicing save units while content registries expect them IS
  fatal (R9b, R10b, G0 FAIL). => never remove content without reconciling
  ContentTable / ContentDocuments / registries; a genesis file must keep
  the content machinery COHERENT (G1 candidates test exactly this).

## Container writing — SOLVED (Track D1)

- Pure-Python CFB writer implemented from [MS-CFB]: `src/rvt/cfb_writer.py`
  (`write_cfb(path, entries)`), plus `src/rvt/roundtrip.py`
  (`--verify`, `--byte-report`, `--params`). All six samples round-trip
  with **identical streams**, confirmed by two independent readers (`olefile`
  strict + `compoundfiles`). 15 tests in `tests/`.
- All samples are **CFB v4** (4096-byte sectors), mini-sector 64, cutoff
  0x1000, **0 DIFAT sectors** even for the 139 MB file (34 FAT sectors <
  109 header slots; v4 DIFAT only kicks in past ~457 MB). All CLSIDs null,
  all state bits 0, stream timestamps 0; only root mtime + storage
  ctime/mtime carry save time.
- Output is intentionally NOT byte-identical: differs in sector layout,
  RB-tree colouring/linkage (we emit valid balanced all-black BSTs), and
  slack (we zero-fill; Autodesk's writer leaks heap garbage into slack —
  e.g. UTF-16 XML fragments in `TransmissionData` slack). Revit uses the
  layout-agnostic Structured Storage API, so stream equality is the
  correct target. File sizes come out byte-for-byte equal anyway.
- => Emitting a syntactically valid `.rvt` **container** is done. What
  remains for a real writer is producing valid stream *contents*.

## Version / provenance

- All six samples are **Revit 2026**, build `20250227_1515(x64)` (from
  `BasicFileInfo`). Format field literally reads `Format: 2026`.
- `BasicFileInfo` is mixed-encoding: leading fields UTF-16LE, then a block of
  ASCII/UTF-8 text that appears at an odd byte offset (shows as garbage when
  the whole stream is decoded as one UTF-16 string). Contains: version, build,
  original path, several GUIDs, worksharing state, username, central model
  path, locale (`ENU`), `Central Model Identity`, `Unique Document GUID`.

## Storage layering — CORRECTED (wave 1). READ THIS FIRST.

An earlier version of this file claimed "corrupt gzip trailers, so
raw-inflate skipping the header". THAT WAS WRONG and produced silently
garbled data past every 64 KB. The real model, established independently by
three agents (cross-file, partitions, prior-art) and now the canonical
reader (`src/rvt/container.py`):

- **PAGE FRAMING (layer 1).** Every raw OLE stream is stored as pages of
  **64,896 (0xFD80) payload bytes, each followed by a 353-byte opaque
  page-trailer block** ("ECC trailer" per ZDI's 2025 Revit research; Revit's
  auto-repair/verify lives in `Utility.dll`). Trailers sit at raw offsets
  `64896 + k*65249`. `container.depage()` strips them → the **logical
  stream**. Decode ONLY from logical bytes (`extracted/*/<S>.logical.bin`,
  or `RvtDocument.logical()`).
- **After de-paging every gzip trailer is VALID** (CRC32 + ISIZE correct):
  13,583/13,583 members verify across all six files. Deflate is textbook
  zlib (dynamic blocks, one `00 00 ff ff` sync-flush, `Z_FINISH`). Layout
  after the payload: gzip trailer(8) + zero pad + a shorter trailer block
  for the final partial page. `Member.crc_ok` records verification.
- **True sizes:** `Formats/Latest` = **496,597 bytes** inflated
  (sha256 6459a9a9…), identical in all six files AND in a 2026 `.rfa`.
  racbasic `Global/Latest` = 1,500,644 (not 1,506,910). racbasic
  `Partitions/15` = **1,156** gzip blocks (the old carver both garbled and
  under-counted at 1,068).
- **8-byte `Global/*` prefixes RESOLVED:** a per-stream-name u64 constant,
  identical in all files — `Latest`=5, `ContentDocuments`=1,
  `DocumentIncrementTable`=1, `History`=1, `ElemTable`=0,
  `PartitionTable`=0; `Partitions/<N>` begins with u64 9. `[hypothesis]`
  per-object serialization version/flags word. Not a size/count/offset.
- **`Contents` wrapper (magic `62 19 22 05` = 0x05221962):** [0]magic
  [4]u32 0x1c [8]u32 item-count 1 [12]u32 0 [16]magic again [20]u32 varies
  [24]gzip member, then pad + final page block. `RevitPreview4.0` uses the
  same wrapper with item word 0x0000800C = flag 0x8000 (uncompressed) |
  class 12 (`A3PartyAImage`) — so the low word is a class-id word.
- **THE 353-BYTE PAGE TRAILER IS A VERIFIED PER-PAGE ECC — CONFIRMED BY
  THE AUTODESK VIEWER (acceptance batches 1–2, docs/acceptance-log.md).**
  Autodesk's translator REJECTS a file if any page's trailer does not
  match its content (V8: only 351 trailer bytes changed => "Processing
  failed"), and rejects any recompression (which invalidates trailers).
  Our container writer itself is accepted (V0 PASS — full 3D + sheets
  render). The trailer is a deterministic, KEYLESS pure function of the
  page bytes: byte-identical schema pages across all six files carry
  byte-identical trailers. Layout: byte0 = 0x00, byte1 = nibble<<4
  (16-value field), last byte = 0/1 flag, middle ~350 bytes ≈ uniform
  entropy (parity/code). Final partial page carries a proportionally
  shorter trailer. **Computing this ECC is the sole remaining blocker for
  the native writer** — everything else (CFB, gzip, framing) is done and
  accepted. `[TOP PRIORITY — the writer's critical path]`
  V9 RESULT (2026-08-02): a file with ONE deliberately-flipped trailer
  byte TRANSLATED SUCCESSFULLY while all-zeroed trailers FAILED ⇒ a
  genuine **error-correcting code with auto-repair** (bounded correction
  capacity), NOT a hash — RS/BCH family, reproducible. Lead hypotheses
  matching the arithmetic (350 code bytes = 175 × 2): chunked GF(2^8) RS
  with 2 parity bytes per ~372-byte chunk, or one GF(2^16) RS codeword
  over the 32,448-word page with 175 parity words. A 5-agent crack fleet
  is running (docs/ecc-brief.md; live lead docs/inbox/ecc-LEAD.md). The
  trailer region cannot be truncated off — V14 (original bytes, tail
  removed) FAILED; it is mandatory even for sub-page streams.
- **ECC SOLVED (2026-08-03) — `src/rvt/ecc.py`.** Reverse-engineered from a
  real Utility.dll (Revit 2023.1.9, extracted from Autodesk's public RevitLT
  update EXE→msp→cab), module `Foundation\Utility\CRCIO.cpp`. It is NOT
  Reed-Solomon/BCH/Adler: it is **255 bit-interleaved shortened-Hamming
  CRC-11 codewords** over the whole 65,249-byte page. Params for a full
  page: m=11 checksum bits, reflected poly 0x500 (x¹¹+x²+1), period 2047,
  align 2, N=9-bit pad-byte-count field. Encoding: buf = 65,249 zero bytes,
  buf[:64896]=data; preChecksumBits=(2047-11)×255=519,180; the 9-bit
  pad-count field sits at bit 519,171 (LSB-first bit numbering, bit0=LSB
  of each byte); lane i = every bit position p with p mod 255 == i, CRC
  per lane (init 0, no xorout: `fb=(c^bit)&1; c>>=1; if fb: c^=0x500`)
  over bits 0..519,179; parity bit j (0..10) of lane i lands at bit
  519,180+i+j×255 ⇒ bytes 64,896..65,248 = the 353-byte trailer. This is
  why NO byte-aligned checksum ever matched (bit-interleaved), why byte 0 is
  0x00 and byte 1 a nibble field (the pad-count field's low bits), and why
  V9's flipped byte was silently repaired (per-lane single-bit correction —
  "rescued N bit(s)"). Smaller final partial pages use the same scheme with
  a size-class parameter set (m∈{11,9,7,6,5,4,3,2}) selected by data length
  via thresholds [5081,1274,548,256,105,40,7]; `ecc.select_params(n)` and
  `ecc.frame_stream(logical)` implement it. VALIDATION: 51/51 full-page
  trailers byte-exact across all six files and every framed stream; 6/6
  large partial pages VERIFY against the file's own bits (re-encoding can't
  reproduce Autodesk's partial pages only because Autodesk leaks heap
  garbage into the pad region — irrelevant to writing, we zero-fill).
  The DLL exports `Adler32::*` symbols too but they are a red herring for
  the page trailer (used elsewhere). `Adler32::ErrorRecoveryLimit`=65520.
- Streams stored with NO CRCIO paging (write freely): `BasicFileInfo`,
  `ProjectInformation`, `TransmissionData`, `RevitPreview4.0` (their
  parsers consume every byte as content).
- Logical-length convention for framed streams: the logical stream is
  EXACTLY prefix + gzip member(s) [+ partition end record]; everything
  after (zero pad + pad-count + parity) belongs to the final ECC block, not
  the logical stream. `depage()`'s tail chunk therefore contains junk after
  the true logical end — decoders ignore it; the writer must construct
  logical from decoded structures, never from `depage()`'s tail.
- COMPRESSION SOLVED: Revit's compressor is stock zlib deflate LEVEL 3 +
  sync-flush (byte-identical for 181,522/181,525 bytes of the schema
  member; only the final block-ending differs). Autodesk's inflater is
  stock zlib and accepts our streams at any level. Use level 3 + sync
  flush to mimic exactly (`writer.gzip_member(level=3)`).
- `Contents` (DocumentStorageIndex, class 0x53e) contains NO per-stream
  sizes/CRC/Adler — it is a name/GUID/build-string index, not an integrity
  registry. No stream-level checksum exists; the per-page ECC is the one
  and only integrity mechanism observed.

## Partitions (element data) — DECODED to record level (wave 1)

- `Partitions/<N>`: `N` = the **document-increment counter**
  (`Global/DocumentIncrementTable` first u32 = max(N)+1). dach kept two
  (`/85` is an empty later partition: 0 elements, the annotated reference).
- Logical stream = 18-byte header (u32 9, u32 0, u16 0x3a3, i32 0, u32
  elem_table_count == `Global/ElemTable` count) + a run of **~128 KiB gzip
  blocks**, each wrapped by a 26-byte block header {u16 0x0f28, u32 flags
  (4 whole records / 6 continues / 7 continuation / 5 ends), u32 A, u32 B
  (= 8 + gzip len, mirrored in a 6-byte 0x0f21 trailer), u32 C, u32 seq
  (101/102/103), u32 0}. ISIZE == hdr_len(seq)*A + C + adj, exact on all
  13,535 blocks.
- Element data = **three parallel logical record streams (seq 101/102/103)**;
  records DO span block boundaries; concatenating block payloads per seq
  yields a contiguous record stream that walks 100% (racbasic: 85,978
  records). Record framing: seq 101 = 16-byte {i64 id, u32 body_size, u32
  cls_word}, cls 0x5e5 (~ElementHeader) each; seq 102/103 = 20-byte {i64
  id, u32 stamp, u32 body_size, u32 cls_word}. seq 102 = the polymorphic
  element objects (top classes 2252/737/954/2572/2124/1158 ≈ GStyleElem/
  CategoryElem/CurveElem/LinearDimensionType/FontTable/DBViewType). seq 103
  = 86–90% class 0x0f2c (~SerializedDummy) + 0x89e (~GElement).
- Blocks group into **save units** (racbasic 164, dach 1,244): unit 0 =
  original save; each unit ends with an 18-byte terminator, a 0x0f3f 64-byte
  opaque blob, the UTF-16 string 'Data generated by Autodesk® Revit®', and a
  28-byte separator (a3 03, -1, a2 03, u32 counter, 16-byte GUID) that
  recurs in Global/Latest and ContentDocuments.
- `Global/PartitionTable` = the **WORKSET table**, not a partition index:
  u16 class 0x0c80, u32 version 1, u32 count, per entry GUID(16), ids,
  kind (0 user / 1 'Project Standards' / 2 title-block), u32 name_len +
  UTF-16 name ('Workset1'/'Architektur').
- `Global/ElemTable` = `ADocument.m_elemTable` (class 0x05c9): u32 count +
  count × 40-byte `ElemRec` sorted by ElementId + graveyard count + footer.
  NOT an id→(partition,offset) index. Its ids are a subset of partition
  record ids (racbasic: 8,401 records; 8,223 ids also in partitions).
- `Global/History` = `ADocument.m_pHistory` (class 0x0538): upgrade
  format-version list (ends **2662 = Revit 2026** in all six) + newest-first
  array of 17-byte episode records (GUID + 0x28); entry 0 == BasicFileInfo's
  Unique Document GUID. `Global/ContentDocuments` = an object array (not
  embedded blobs); DocumentIncrementTable = per-save increment records.
- Stream-lead **u16 class ordinals** (drift ±1): 0x1c ADocument
  (Global/Latest), 0x5c9 ElemTable, 0x53c DocumentIncrementTable, 0x538
  History, 0x53e Contents, 0xc80 PartitionTable, 0x3a2/0x3a3
  ContentMarker/ContentRec, framing tags 0x0f28/0x0f21/0x0f3f.

## Prior art — what already exists (wave 1)

- **`DrunkOnJava/rvt-rs`** (Rust, Apache-2, ~55K lines, built 2026-04) is
  the state of the art: Formats/Latest class-record grammar (u16 tags,
  0x8000 parent flag — corroborates our schema-a grammar), a full field
  type-encoding table, an 11-release **tag-drift CSV**, Global/Latest
  framing, ElemTable/ContentDocuments/PartitionTable layouts. Cloned to
  `vendor/rvt-rs`. Its ~400-class count / 64 KB scan cap is an artefact of
  the same paging problem we hit — the true class map is far larger.
- **`phi-ag/rvt`** is TypeScript (npm `@phi-ag/rvt`, MIT), shallow: CFB +
  BasicFileInfo + preview PNG only; ships an 11-release RFA corpus. Cloned
  to `vendor/phi-ag-rvt` (LFS objects fetched).
- **`magnetar-io/revit-test-datasets`** (MIT): real `.rvt` files
  (Revit_IFC5_Einhoven 2023, 2024_Core_Interior 34 MB, RFAs) WITH matching
  IFC exports of the same models = a **ground-truth oracle** for element
  decoding no prior project wired up. Cloned to `vendor/`.
- **ZDI 2025 Revit deserialization research** independently confirms the
  object model: deserializer reads a **u16 class index**; **4,611
  serializable classes** registered in Revit 2025 via
  `Utility!ArchiveClassMaps::loadClass` / `ARuntimeClass::createObject`;
  `AString` = index 0x1f; strings length-prefixed. So `Formats/Latest` IS
  the on-disk archive class map — expect ~4,600 classes once fully decoded.
- Sibling formats `.rfa/.rte/.rft` use the identical CFB container; RFAs
  add `PartAtom` (Atom XML, `application/rfa`) and exactly one Partitions/N
  (N increments per upgrade: 58 in 2016 → 69 in 2026). `ProjectInformation`
  ZIP wraps `<Temp>\Revit<guid>.project.xml` in the same partatom namespace.
- Official closed read/write surfaces exist for `BasicFileInfo`
  (`BasicFileInfo.Extract`) and `TransmissionData`
  (`Read/WriteTransmissionData`) — usable as codec oracles.
- PRONOM: `x-fmt/443–448`, container PUIDs `fmt/1346–1351` (DROID sigs).

## Schema — FULLY SOLVED (wave 2, `src/rvt/schema.py`, `schema.json`)

- Formats/Latest parses to EOF: 496,589 bytes + 8-byte zero sentinel,
  ZERO gaps, ZERO unresolved refs, identical across all six files.
  **4,690 classes** (3,604 top-level ASCII-sorted class records + 1,086
  inline definitions), 12,558 fields, type ids 0x000c–0x125d. Id model =
  definition order + 0x0c with NO drift; anchor validation 16/16 (ADocument
  0x1c, ElementId 0x14, AStringWrapper 0x1f, Element 0x25, ElemTable 0x5c9,
  DocumentHistory 0x538, DocumentIncrementTable 0x53c,
  DocumentStorageIndexImpl 0x53e = Contents, PartitionTable 0xc80,
  ElementHeader 0x5e5, SerializedDummy 0xf2c, GElement 0x89e,
  GStyleElem 0x8cc, CategoryElem 0x2e1; 0x3a2/0x3a3 = ContentKey/
  ContentMarker, ContentRec = 0x3a4).
- Kind codebook (ground-truth from 394 std::pair<> classes): 0x01 bool,
  0x02 char, 0x03 short, 0x04 int, 0x05 uint, 0x06 float, 0x07 double,
  0x08 AString (flags 0x60), 0x09 GUID, 0x0a classref, 0x0b int64,
  0x0d inline-array, 0x0e class-ref. (Corrects rvt-rs and schema-a.)
- rvt-rs's per-class "tag" = the inline-defined base class's id = our
  id + 1 (60/60). 407 electrical/MEP classes exported to
  `extracted/_schema/mep_classes.txt` (e.g. 0x596 ElectricalCircuit,
  0x381 ConnectorElem, 0x2b6 CableTray, 0xb48 PanelScheduleView).
- Element (0x25) has 895 descendants, max inheritance depth 7.

## Object decoding — WORKS CORPUS-WIDE (wave 2, `src/rvt/objects.py`)

- Schema-directed decode of partition records: racbasic **85,814/85,814
  seq-102 records (306 classes) decode with 100% of body bytes consumed,
  0 errors**; seq 101 (ElementHeader) and seq 103 (GElement /
  SerializedDummy) also 100%; corpus-wide seq-102 clean rate 99.69% — the
  ONLY failures are Extensible-Storage entity blobs (ESEntity.m_blob),
  whose runtime ES schemas live in Global/Latest's ADocument ES schema
  table (clear resolution path).
- Record framing (CORRECTED): `i64 id [+u32 stamp for seq 102/103] +
  u32 psize + {u16 class_id, object[psize-2]} + u32 psize repeat`;
  the wave-1 "u32 class_word" = u16 class_id (schema type_id, IDENTITY
  mapping) + first u16 of the object. One record per element per seq;
  identical id sets across seqs 101/102/103; all Global/ElemTable ids are
  a subset; `Element.m_id == record id` for every decoded object.
- Field order = **parent-first** (root base Element's 20 fields first).
  Serialization codebook verified: AString = u32 count + UTF-16LE
  (0xFFFFFFFF = null); GUID 16 raw; ElementId flattened to i64 (-1
  invalid); XYZ/UV/Trf = schema fixed double arrays; containers = u32
  count + elements; owned/poly pointers = i32 pid (0 null, -1 anonymous,
  >0 archive object index, seen pid = back-reference) + u16 class, pointed
  bodies deferred breadth-first.
- Real semantics decoded: Level 0x9e7 elevations (via DatumPlane→Plane
  origin z, feet; racbasic Level 2 = 3.0 m); walls SWall 0xf02 (< VWall <
  HostObj) with location lines (GLine origin/dirVec/endParams; lengths);
  Grid 0x90e; views. In rmebasic EVERY MEP/electrical class decodes 100%:
  RbsElectricalSystem circuits ('PP-1B', 20 A, 208 V internal 2238.89),
  ConnectorElem→ConnectorElemDomainElectrical (120 V, poles), voltage/
  distribution types, ElectricalSetting, panel schedule views.
- **The encoder/serializer is now the symmetric inverse of a KNOWN codebook
  — mechanical, not research. Writer critical path = ECC only.**
- Bug fixed: `partitions.partition_stream_paths()` previously globbed the
  `.logical.bin` corpus artefact and double-walked segments.

## Schema (Formats/Latest) — grammar history (wave 1)

- Grammar (release-independent, corroborated by rvt-rs + ZDI): class_record
  = u16 0 + u16 nameLen + ASCII name + u16 parentRef (0 none; 0x8000|id =
  parent defined inline; else backward ref) + u32 version + u32 fieldCount
  + fields + u32 guidCount + guids. field = u32 nameLen + name + 4-byte tag
  (kind, flags, u16 0) + [u32 count if flags high-nibble 1] + [u16 typeRef
  for kind 0x0e; 0x8000|id = inline definition] + [anonymous " " element
  sub-field for kind 0x0d arrays]. **Type ids = definition order + 0x0c**;
  ids < 0x0c are primitives (01 bool, 04 int32, 05 uint32, 06 float, 07
  double, 08 AString, 09 GUID, 0b int64, 0d inline-array, 0e class …).
  Inheritance IS encoded via parentRef (Element is the universal base).
- schema-a decoded the first 138,849 bytes flawlessly (1,150 classes, 3,111
  fields, 877/877 refs resolve) then hit "corruption" at 0x21e61 — which
  was the PAGE-FRAMING ARTEFACT, not Revit. `src/rvt/schema_a.py` must be
  re-run on the correct 496,597-byte de-paged schema; expect ~4,600 classes
  including Wall/Level/View and the electrical classes. `[wave 2]`
- schema-b's independent statistical decode corroborates the grammar and
  produced a pair<>-calibrated type-tag codebook (`schema_b.json`).
- Most-referenced types: ElementId 615, XYZ 54, Trf 21, GUIDvalue 16,
  ForgeTypeId 8, GeomRef 7. `ADocument` v2662, 19 fields, 1,509-GUID
  trailer; `Element` (v21, 20 fields) is the universal base.

## The schema (`Formats/Latest`) — the Rosetta stone

- **Byte-identical across all six files** (sha256 prefix `8f551c2218c6e015`,
  182,953 bytes compressed → **498,766 bytes inflated**). It is a
  **per-release constant** (Revit 2026 build). Decode once, reuse for every
  2026 file. Different releases will need their own schema blob.
- It is a self-describing **class dictionary**: length-prefixed class names
  (`A3PartyAImage`, `A3PartyObject`, `ACDPtrWrapper`, `ADocument`), each
  with ordered **field records** (`m_pACD`, `m_mapIntValues`, `m_elemTable`,
  `m_pHistory`, `m_pPartitionTable`, `m_oContentTable`) and full **C++ type
  strings** (`std::pair< ElementId, int >`, `ElementId`, `AString`,
  container templates with nested `first`/`second`). ~27,900 strings.
- `ADocument`'s fields map directly onto the top-level streams
  (`m_elemTable` ↔ `Global/ElemTable`, `m_pHistory` ↔ `Global/History`,
  `m_pPartitionTable` ↔ `Global/PartitionTable`, `m_oContentTable` ↔
  `Global/ContentDocuments`). So `Global/Latest` is the serialized
  `ADocument` object graph, and the streams are its externalized members.
- Naming convention: Autodesk classes are `A`-prefixed (`ADocument`,
  `A3Party*`, `ADTGrid*`), members `m_`-prefixed. This is genuine internal
  C++ RTTI/serialization metadata, not obfuscated.

## Sizes (racbasicsampleproject, for scale)

- `Global/Latest` 117 KB → 1.5 MB; `Global/ContentDocuments` 818 KB → 5.1 MB;
  `Global/ElemTable` 50 KB → 336 KB; `Partitions/15` 18.5 MB → ~876×131 KB.

## Environment / tooling

- macOS host, Python 3.12 via `uv` venv at `.venv/`. `olefile` installed.
- No Rust toolchain (`cargo` missing) — if we lean on `phi-ag/rvt` (Rust
  prior art), read its source rather than build it.
- Revit itself is Windows-only; nothing here can open a `.rvt` in Revit.
  Round-trip acceptance testing needs the user (Windows/Revit) or Autodesk
  APS Design Automation.

## Audience & acceptance testing (from user)

- End users are the user's **brothers** (external, non-developers) who have
  an **Autodesk / Revit account through their work**. Deliverables must be
  brother-friendly (clear CLI or simple UI, install/run docs, handoff docs).
- Revit acceptance testing (does Revit open our output) runs through them at
  work. Their work Autodesk account also makes **APS Design Automation** a
  viable headless-generation route, subject to their firm's IT policy.
- HARD CONSTRAINT: Revit cannot open files from a NEWER release. Generated
  files must target a version ≤ the brothers' installed Revit. `[open]`
  their exact Revit version is unconfirmed — samples/schema are 2026.
- IFC output sidesteps versioning (any Revit imports IFC) — a second reason
  IFC is the guaranteed path.

## The workflow (from user) — DECIDED

- **Claude Design is the authoring surface.** The brothers/user build the
  model, specs, shop drawings and renderings in Claude Design, and Design
  emits **IFC** directly. The user has done this before and it worked.
- Therefore this project is the **bridge**: ingest Design-authored IFC →
  validate → repair/normalize → enrich for Revit → deliver something
  **editable as native Revit elements** (not generic/in-place geometry).
  IFC-in is a FIRST-CLASS INPUT. Native `.rvt` output is the deeper goal
  that maximises editability.
- Key technical hinge: getting IFC *into* Revit is trivial (Open IFC /
  Link IFC); getting it in as *editable native families* depends on the
  IFC entity classes + geometry representations chosen at authoring time
  (e.g. `IfcWallStandardCase` with extruded/swept solid → native Wall,
  vs. arbitrary `IfcBuildingElementProxy`/Brep → DirectShape blob). So a
  major deliverable is a **Design authoring guide/skill** that makes
  Design's IFC Revit-native-import-optimal, plus the hardening tool.
- Domain is **electrical / MEP for transit & institutional facilities**
  (e.g. "DDOT Coolidge – Area E bus storage electrical room"): panelboards,
  transformers, plenum-rated lighting, trapeze hanger supports, one-lines,
  panel schedules, BOMs, submittals. `rmebasicsampleproject.rvt` is the most
  relevant sample. Revit targets: MEP/Electrical categories.

## Ground truth: Design's IFC exporter (Chicago plenum project) — ANALYSED

- Design project "Chicago plenum recessed light" contains `ifc-export.js`
  (a client-side JS IFC4 writer, "three-d-stage IFC writer") plus real
  three.js model files and six exported `.ifc` files. Sample saved locally:
  `samples/design-ifc/bs-area-e-electrical-room.ifc` (84 KB). Also
  `panelboard-shared-parameters.txt` — a valid Revit shared-parameters file
  (PanelName, Voltage/ELECTRICAL_POTENTIAL, Phases, Wires, BusRating,
  MainsType, MainsRating, ShortCircuitRatingkA, Mounting, NumberOfCircuits,
  NeutralRating) — the ready-made bridge from IFC psets to Revit parameters.
- SEMANTICS: EXCELLENT. Valid IFC4 STEP; correct Project→Site→Building→
  Storey tree; metre + electrical units (volt/amp/watt); real classes —
  6× `IfcElectricDistributionBoard` (panels B-HG4, B-LR1, B-HQ1, B-LQ1,
  B-SLQ1, B-SHQ1), 3× `IfcTransformer`, `IfcDiscreteAccessory` (trapeze
  hangers), 1 proxy; typed psets (PanelSchedule, TransformerSchedule,
  SupportSchedule, RoomInformation) incl. `IfcElectricVoltageMeasure` etc.;
  type objects via `IfcRelDefinesByType`; materials via `IfcSurfaceStyle`;
  correct 22-char IFC GUIDs. This will import into the RIGHT Revit
  categories with full schedule data.
- GEOMETRY = THE EDITABILITY CEILING: 100% `IfcTriangulatedFaceSet` (50
  facesets, 0 extrusions), vertex coordinates baked to world space, every
  element placed with an identity `IfcLocalPlacement` under a single
  "Level 1" storey. In Revit this imports as **DirectShape** blobs:
  categorized/named/schedulable with psets as parameters, but not
  parametrically editable, no meaningful insertion point/rotation, and no
  MEP connectors.
- MEP HARD LIMIT: Revit's IFC importer never creates functioning electrical
  connectors or circuits from IFC. IFC→Revit MEP is lossy at connectivity
  no matter how good the IFC is. Hence two "editable" tiers:
  * Tier 1 (better IFC, achievable now): real placement transforms /
    insertion points, `IfcExtrudedAreaSolid` for prismatic gear instead of
    triangle soup, `IfcMappedItem` instancing for repeated types, multi-
    storey, spaces. => clean, movable, dimensionally-honest, data-rich
    reference geometry (still DirectShape, no connectors).
  * Tier 2 (true native MEP families + circuits): Revit API only — APS
    Design Automation add-in placing real (manufacturer/library) families,
    setting parameters (their shared-params file maps 1:1), building
    circuits => real `.rvt`. Or the native `.rvt` writer (harder). This is
    where the brothers' Autodesk account and the RVT reverse-engineering pay
    off, and why MEP raises the "editable" bar higher than architecture.
- Highest-leverage move: fix `ifc-export.js` AT THE SOURCE (extrusions,
  placements, mapped items) so every future Design model exports Tier-1
  IFC — we have write access to the Design project (get user OK first).

## Delivery architecture — DECIDED (Skill-first)

- Primary delivery vehicle is a **Skill with bundled scripts**, not an MCP
  server. A skill folder ships `SKILL.md` (the playbook) + `scripts/` (the
  engine) + the `rvt` library. Cowork and claude.ai execute those scripts in
  their built-in **Linux code-execution sandbox** — the same runtime that
  powers Anthropic's docx/xlsx/pdf skills. That sandbox is what "runs the
  CLI"; no server, no install, works across surfaces. The user proposed
  this; it supersedes the earlier MCP-first recommendation.
- CLI, skill script, and any future MCP tool are all thin front doors onto
  ONE library — so wrapping the same code as MCP later is zero rework.
- Sandbox being Linux is an ADVANTAGE: `ifcopenshell` ships manylinux
  wheels, likely sidestepping the Windows native-deps packaging problem.
- Flow: user exports IFC from Claude Design → attaches it in Cowork/claude.ai
  → skill runs the script → Revit-ready file returned (or dropped in a
  folder Cowork can see).
- MCP is the ESCALATION path, triggered only by a concrete need: holding
  secrets (APS credentials for the auto-validation gate), writing straight
  to a specific local folder, jobs exceeding sandbox time/memory limits, or
  deps/egress the sandbox refuses.
- `[open]` verify empirically: `pip install ifcopenshell` inside a real
  Cowork sandbox; sandbox time/memory limits on a large model; whether APS
  network egress is permitted from the sandbox (else validation moves to
  MCP). Claude Design itself is the author, likely not the script runner —
  the skill runs where they chat, with the Design IFC attached.

## Product requirement (from user)

- The generator must be **repeatable and parameterized**: accept arguments /
  a spec and consistently produce any kind of `.rvt`. Design the input as a
  stable, versioned **building spec (JSON)** — levels, grids, walls, doors,
  windows, floors, roofs, rooms, families, project metadata — with sensible
  defaults. Claude Design authors/edits the spec; the generator is a
  deterministic CLI/library.


## THE REDUCTION LAW (K1 autopsy, 2026-08-04, viewer-confirmed by K1a_editfree PASS)

A referrer of removed content is either DELETED WITH the content or LEFT
BYTE-IDENTICAL — never "neutralised" (null id / dropped struct / pruned map)
into a state no Autodesk file exhibits. K1 (R5 minus placed model) broke
this: rvt.manipulate's neutralise pre-pass edited 404 surviving referrers
(a registry-indexed default FamilySymbol orphaned m_familyId->-1 with its
Family deleted; surrogates nulled; a stair symbol un-hosted; schedule
grid-intersection structs dropped; view state maps pruned) and the file
CRASHED the reader (exit -1073741831) — silently, since the validator and
ElemTable read it as 6,540 clean rows. The certified reduction ladder is
EDIT-FREE (pure maxgc + four-registry document reconciliation). Rules: the
family/type layer is atomic; never drop structured entries from a survivor's
arrays; model-view state maps leave with the view; the only sanctioned
reduction generator is maxgc; and A BASE IS VIEWER-CERTIFIED BEFORE
ANYTHING IS BUILT ON IT (tools/probe_batch.py enforces base+control per
batch). The M2/M3 modify path remains sound for genuine user edits (M3
certified) — the law is about REDUCTION referrers, not user modification.

## IN-PLACE SUBSTITUTION IS THE PROVEN GENESIS MECHANISM (batch 15, 2026-08-04)
regadd.substitute_element (zero registration motion: same id / ElemTable row
/ record positions / registry slots; only the seq-102 object record changes)
took certified K4 to Y9 — settings + 1,407-row catalog + palette + datum +
view constellations ALL our constructors' output — and Y9 LOADS (with the
single-layer probes Y1 pen table and Y_cat catalog also PASSING). The
remaining genesis work is the Yn residue: 2,009 K4 elements in 11 named
buckets, each = author a constructor + an in-place rung.


## ***** GENESIS ACHIEVED (2026-08-04) *****
The composed genesis project base G_ABPD (experiments/genesis/subst_k4/
compose/G_ABPD.rvt) LOADS in Autodesk's reader as a browsable model.  Recipe:
certified family-free base K4 -> in-place substitution ladder (Y1..Y9,
ZA_deep, ZC_deep) -> tools/genesis_compose.py composes the certified rung
contributions by id (proven byte-exact by its 'anchor' against ZA_deep) +
the reduce-law maxgc deletion set.  Every layer that goes INTO the file is
individually viewer-certified; the composer transplants each rung's changed
object records onto the deep base at the same element ids (in-place ==>
Latest/ElemTable byte-identical, disjointness + parent-coherence asserted).
Batches carry a certified control; a translation-PASS is confirmed by
opening the viewer (a 'pass' can also be the 'Design is empty' short-
circuit for symbol-only files).

## LOAD IS NOT RENDER — and the render road is short (2026-08-04)
An element's drawable geometry lives in its seq-103 record: a decodable
GElement B-rep scene graph (Face/EdgeLoop/Plane/Edge), the SAME grammar
rvt.famgen.geometry authors byte-exact for family solids.  Created walls
carried a 2-byte SerializedDummy rep (nothing to draw); the cloud extractor
draws baked geometry only and never regenerates (desktop Revit does).
rvt.render.brep authors the wall solid; render-emit's reproduce_native_wall
rebuilds a native wall's rep with ZERO differing leaves.  Our loaded symbols
and their instances DO carry real solids (the instance layer renders).
RETRACTED: verdict #22's 'one defective family' — the failing delta is
created WALLS + LOADED FAMILY DOCUMENTS TOGETHER (walls alone pass, families
alone empty-pass); the mechanism is under bisection.


## CREATION IS VISIBLE (2026-08-04, viewer screenshot)
RSOLID_walls_A_solid.rvt — 4 created walls carrying authored seq-103 GElement
six-face solids (rvt.render.brep) on the LOAD-certified walls-only genesis
base — RENDERS in Autodesk's viewer as a shaded 3D room shell.  LOAD +
RENDER both proven for created content.  Remaining creation-path bug (named,
not fixed): ANY embedded family unit + created content trips the audit
(R_inst_box, F_msb, F_lp4 all FAIL) — instances on the genesis lineage are
unproven until it is fixed; the front door detects and degrades it honestly
(PROOF-ONLY stamp or --strict split).

## TEKTON FRONT DOOR (2026-08-04)
tools/frontdoor.py author --prompt TEXT | --ifc FILE.ifc | --rvt FILE.rvt
--edit SPEC: one entrypoint, three inputs, one intent model, one build step
onto the pinned certified genesis base G_ABPD, one deliverable manifest.
Prompt path = documented AI-surface handoff (scene brief -> Three.js ->
IFC4 with our tagging-contract Psets -> back through --ifc) with a
built-in no-API-key rules parser fallback.  Shipped as plugin skills
tekton-author / tekton-edit / tekton-inspect; MCP is the documented future
path (docs/product/MCP-PATH.md) for surfaces that cannot run skills.

## The instance-audit campaign (2026-08-05 overnight; verdicts #31–#42)

The longest hunt in the project: why does Autodesk's audit reject any file
where an INSTANCE references one of OUR generated family documents, while
every other operation passes? Eighteen viewer rounds of single-variable
experiments produced two REAL fixed defect classes and one honest wall:

**Fixed in core (keep forever):**
- **The 0x0f3f unit footer blob is mandatory** on any unit an instance
  walks into: every native unit carries a distinct 64-byte high-entropy
  blob; presence-only (a random blob passes — E1b), content unverified.
  Our writers emitted blen=0 for months; `factory.build_family_save_unit`
  now emits the deterministic sha512 nonce (`famdoc_adoc.build_footer`).
- **The D1–D5 corpus laws** (instance connector-manager class =
  FamilyInstanceConnectorManager 13,636/13,636; ContentTable GUID-sorted;
  the two non-null owned slots; the populated connector cell; the
  ProjectPhase lookup) — all real, all fixed, validator rules E1–E3 live.

**Exonerated by byte-level single-variable experiments** (do not re-suspect
without new evidence): load machinery (byte-copied native constellation),
registration row content, CategoryTracking totality, the inline famdoc
ADocument, symbol form (all variants), famdoc single content axes
(geometry/params/datums/views/connector), the frame (self-Family fields,
UnitsElem, view chain, ownership topology), element order (both
directions), gzip/ECC/CFB envelope (Autodesk's exact gzip recipes are now
cracked byte-for-byte in tools/terminal_diff.py), the 12 perfect corpus
separators flipped coherently (BX_conj).

**The wall:** a famgen-ASSEMBLED famdoc under an instance still fails while
a donor-DERIVED body reduced to the same content passes (SUB_ALL). The one
unprobed sub-axis: sparse m_familyIds indices. The decisive instrument is
desktop Revit's own error dialog — the REVIT-CHECK-KIT
(experiments/terminal/REVIT-CHECK-KIT.md) packages the two files and
instructions for a human with Revit.

**Method lessons (institutional):** the viewer only ever says "corrupt" —
build matched pass/fail pairs and flip ONE variable; a passing substrate
(donor body) accepting all our content while our assembly fails means the
defect can hide BELOW the record layer (the blob was invisible to every
record-level diff); voided rounds are real (the empty blob invalidated an
entire content-bisection round — re-run, don't reinterpret); "uninstanced
tolerance" misleads (H10/L_v2 passed only because nothing walked the unit).

**Also this session:** the four-release engine completed — G_ABPD_2024/2025
composed+certified (32-bit records32 era for 2023; native 2025/2024
authoring via release_ctx), the permutation matrix/router shipped, the
performance work landed (zero-install IFC via steplite, schema caches,
one-call dispatch), and the plugin bundles three composed bases.

## The instance-audit campaign, day 2 (2026-08-05; verdicts #43–#48)

The field testers' template tip drove the second day. Confirmed laws and
the final honest cell map:

**The template-birth law (confirmed):** everything Revit-born passes our
entire pipeline — both species (standalone .rfa: T2a; embedded famdoc:
TB0g) even onto composed bases with instances. The load-any-.rfa route
and extract-family→place are CERTIFIED product paths.

**The precise open cell:** OUR generated famdocs + placed instances fail
ONLY on OUR reduced/composed bases. The same bytes pass on pristine
sample bases (T1r/T1u/U16 on rst) — which means prompt-equipment INTO
USER PROJECTS (the add_to_project route) rides the passing cell; the
field workflow works. Only from-scratch-equipment-on-from-scratch-base
remains gated.

**Exonerated on day 2** (single-variable, viewer-verdict each): shell
species, union machinery, base instance (K4/G_ABP/G_ABPD all reject;
targets byte-born on K4 — content of ref targets irrelevant), walked
render binds, full self-containment, host symbol table blanks, the
frozen-birth-id identity strings + born flag coherence (perfect 4-cell
correlate, not cause), the inline ADocument flavour (again).

**Instruments built (reusable):** the four-surface host-ref census, the
walked-bind census, the identity census, byte-surgery with per-seq
multiset proofs, famdoc transplant via watermark-equality, the species
probe machinery. Watermark law: rst == K4 == G_ABP == G_ABPD == 1472524
enables byte-exact famdoc transplants across the whole lineage.

**Terminal instrument:** desktop Revit's own error dialog
(experiments/terminal/REVIT-CHECK-KIT.md — two files, two screenshots).
The audit distinguishes files our byte instruments measure as
lawful-equivalent; the dialog names what the viewer never says.

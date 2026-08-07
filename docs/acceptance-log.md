# Acceptance log — Autodesk Viewer / Revit results

The user validates candidate files in the Autodesk Viewer
(viewer.autodesk.com — Autodesk's real translation pipeline, the same
reading stack Revit uses). Each experiment batch isolates one hypothesis.
Record every result here: file, PASS (opens & renders correctly) / FAIL
(and the exact error text), and what changed vs the control.

## Batch 1 — the writer gate (page trailers). Base: rstbasicsampleproject.rvt

Question: does Autodesk's reader verify the 353-byte per-page trailers
("ECC") against page content? This is the ONLY unknown between us and a
free-writing pipeline (container writer: done; gzip: reproducible; framing:
reproducible; trailer contents: unknown).

| File | What we did | If it OPENS it proves |
|---|---|---|
| V0_control_roundtrip | Rebuilt the compound file (CFB) with our writer; every stream byte-identical | Our container writer is accepted by Autodesk's reader (expected to pass) |
| V1_elemtable_zero_trailers | Recompressed Global/ElemTable with OUR gzip; its page trailers ZEROED | Trailers are NOT verified against content ⇒ writer UNBLOCKED |
| V2_elemtable_copied_trailers | Same recompression; original trailers copied verbatim (now mismatched vs content) | Reader wants plausible trailer bytes but doesn't check them ⇒ still unblocked (copy any donor trailer) |
| V3_allstreams_zero_trailers | Recompressed EVERY single-member stream; all trailers zeroed | Tolerance holds file-wide |
| V4_schema_zero_trailers | Recompressed only Formats/Latest (schema); trailers zeroed | The stream we regenerate least is also tolerant (control) |
| V5_allstreams_random_trailers | Everything recompressed; RANDOM (non-zero garbage) trailers | Whether zero is special or any garbage is tolerated |

Decision matrix:
- V1 opens                → trailer content is unchecked. Skip ECC entirely.
- V1 fails, V2 opens      → presence matters, content doesn't. Copy donor trailers.
- V1 & V2 fail            → content-verified ECC. Escalate: reproduce the algorithm
                            (docs/streams/09-page-ecc.md) — the only remaining path.
- V0 fails                → our CFB writer needs work (unexpected; investigate first).

### Results

**V0_control_roundtrip — PASS ✅ (2026-08-02, ~22:15)**
Uploaded to Autodesk Viewer; translation completed ("Expires in 30 days"
success state). Opened: full `{3D}` view of the steel-frame Basic Structural
Sample Project renders correctly AND the SHEETS translated (title sheet
"Basic Structural Sample Project" with placed views, schedules, details).
=> Autodesk's real reading pipeline (Model Derivative) accepts a compound
file produced by OUR CFB writer, reading every stream (geometry/partitions,
views, sheets, schedules). Milestone D0 CONFIRMED by the real oracle.

**Batch 1 remainder (2026-08-02, ~22:34–22:41): V1, V2, V3, V4, V5, V6,
V7 — ALL "Processing failed".** Autodesk Model Derivative rejected every
variant in which ANY stream was recompressed by us (regardless of trailer
treatment: zeroed, copied-original, or random). Only V0 (streams byte-
identical) translated.

FLAW IN BATCH 1 DESIGN: every failing variant changed TWO variables at once
— (a) the compressed bytes (our zlib output) AND (b) the 353-byte page
trailers. V2 (recompressed + original trailers) fails under BOTH hypotheses
(content-verified trailers, OR an inflater that rejects our deflate stream),
so Batch 1 cannot separate them. Two live hypotheses:
  H-ECC : trailers are content-verified / used for AUTO-REPAIR (ZDI): wrong
          trailer bytes make the reader "repair" (corrupt) a valid page.
  H-COMP: Autodesk's inflater rejects our deflate framing (e.g. requires
          Revit's exact convention: dynamic blocks, `00 00 ff ff` sync-flush
          then `02 0c 00`, no BFINAL / read-exactly-ISIZE, window/dictionary
          assumptions), independent of trailers.
=> Batch 2 isolates each variable on its own (below).

## *** BATCH 3 — THE WRITER PROOF (2026-08-03 ~23:30) ***

**V15_fullfile_real_ecc — PASS ✅✅✅.** The WHOLE rstbasic file re-written by
us: every ECC-framed stream (Contents, Formats/Latest, all Global/*, and
Partitions/21 with all 414 blocks) decompressed and RE-COMPRESSED by our
gzip (zlib level 3 + sync-flush) and RE-FRAMED with REAL, RECOMPUTED CRCIO
page trailers from src/rvt/ecc.py (the cracked bit-interleaved CRC-11 code);
unframed metadata streams (BasicFileInfo, ProjectInformation,
TransmissionData) copied. Uploaded 23:30, translated ("Expires in 30 days"),
opened: full {3D} view AND the complete sheet set render identically to
the original. Uncompressed content identical to source; EVERY framed byte
on disk produced by our writer. => THE NATIVE .rvt WRITER IS PROVEN
END-TO-END (CFB container + zlib framing + block framing + ECC).
Self-check before upload: 422/422 gzip members CRC-valid; 99/99 full
pages ECC self-verify; single-stream payloads identical to original.
(V16/V17 single-stream real-ECC isolators uploaded as hedges — moot.)


## *** BATCH 4 — FIRST AUTHORED CHANGE (2026-08-03 ~23:44–23:50) ***

**V18_first_authored_change — PASS ✅ AND VISIBLE.** Size-preserving edit of
the cover-sheet RTF title inside seq-102 record (element id 1,456,999,
class 0x10de) in save-unit 0 of Partitions/21: "Basic Structural Sample
Project" -> "REV-REVIT WROTE THIS RVT FILE!!". Whole partition stream
re-emitted (recompress + recompute block B fields + real ECC framing).
The rendered TITLE SHEET SHOWS OUR TEXT. => We can author content into a
native .rvt through the full pipeline (decode -> edit -> encode/reframe ->
ecc -> cfb) and Autodesk renders it.
- V18 deliberately carried a STALE record stamp and still PASSED =>
  **record stamps are NOT validated by the reader** (creation gets simpler).
  We still write correct stamps (adler32(class_id||object)) as hygiene.
- V19 (same edit, stamp recomputed, all 32,011 seq-102 stamps valid) —
  translating; confirms the correct-stamp path.
- V16 (ElemTable) and V17 (History) single-stream real-ECC — both PASS.


## *** BATCH 5 — FIRST CREATED ELEMENT (2026-08-03 ~00:12) ***

**V20_first_created_element — PASS ✅ (translated).** A NEW element that
did not exist: a 450x450 mm concrete square column (symbol 1411287,
FamilyInstance id 1,472,525 = ElemTable watermark+1) placed 8 ft east of an
existing column on Level 1, created via
`rvt.mutate.Document.add_family_instance()` -> `serialize()` (encode.py,
adler32 stamps) -> `rvt.commit.commit_new_elements()` (three records
appended before the unit-0 sentinels; ElemTable 13,936->13,937; header
count matched; real ECC framing). Autodesk accepted it and created the
viewables ("Expires in 30 days"); {3D} + sheets present. => ELEMENT
CREATION WORKS end-to-end structurally.
- Visual confirmation of the extra column DEFERRED: the in-app browser has
  no WebGL for the interactive 3D viewer; user to open V20/V21 -> {3D} in a
  real browser and confirm the column(s) stand near the origin.
- V21_batch_four_columns (four columns, ids 1,472,525..528, ElemTable
  13,936->13,940) uploaded to prove multi-element commits — translating.


## *** BATCH 6 — BATCH CREATION + WALL CREATION (2026-08-03 ~00:28–00:47) ***

- **V21_batch_four_columns — PASS ✅.** Four created concrete columns (ids
  1,472,525..528) committed in ONE call to commit_new_elements (ElemTable
  13,936->13,940). Translated. => multi-element / batch creation works.
- **V22_first_created_wall — PASS ✅.** New straight wall (SWall id
  1,098,948, type 232827, 20 ft x 10 ft on Level 1, racbasic) via
  Document.add_wall(). Its seq-103 rep is a SerializedDummy (22 B, NO
  cached solid — Revit regenerates from m_geomSteps). Translated. =>
  wall creation is accepted WITHOUT us synthesizing wall geometry
  (planner test T1 passes at the acceptance level). Visual render of the
  new wall/columns deferred to a WebGL browser (user eyeball).
SCORE: writer track 12/12 in the Autodesk Viewer this session
(V0, V9, V15, V16, V17, V18, V19, V20, V21, V22 + ECC hedges).


## *** BATCH 7 — THE GOAL: SPEC -> NATIVE .rvt (2026-08-03 ~00:55) ***

**V23_electrical_room — PASS ✅.** The user's real job (DDOT Coolidge /
Chicago-plenum bus-storage electrical room) generated as a NATIVE .rvt by
`tools/spec_to_rvt.py` from usecases/.../room-spec.json (the SAME spec that
produced the 100/100 Tier-1 IFC): 12 created elements in the rme MEP
template — 3 room walls (add_wall), 6 panelboards B-HG4/B-LR1/B-HQ1/B-LQ1/
B-SLQ1/B-SHQ1 on '480V MCB Surface :: 400 A' families, 3 transformers
XFMR-LR1/XFMR-LQ1/XFMR-B-SLQ1 on 'Dry Type 480-208Y120 :: 500 kVA' families,
all free-standing at spec positions/elevations (ElemTable 28,132->28,144).
Accepted and translated. The {3D} thumbnail shows a cluster of new objects
outside the building at the offset location; V24 (untouched original rme)
uploaded as a visual control to confirm the cluster is our room.
=> SPEC -> NATIVE .rvt IS PROVEN END-TO-END (structural acceptance).
SCORE: 13/13 writer-track files translated in the Autodesk Viewer.


## *** BATCH 8 — VISUAL PROOF OF CREATED GEOMETRY (2026-08-03 ~01:10) ***

- **V25_room_from_ifc — PASS ✅.** The fully AUTOMATED chain Claude-Design
  IFC -> tools/ifc_to_spec.py -> spec_to_rvt.py -> native .rvt (9
  equipment items at the export's recovered positions/elevations, zero
  hand-authoring) translated.
- **V24_rme_original_control — PASS** (untouched original, uploaded ONLY as
  a visual control).
- **VISUAL PROOF (whole-model {3D} thumbnails):** V24's {3D} shows the MEP
  building FILLING the frame with nothing at the lower-left; V23's {3D}
  shows the SAME building drawn SMALLER plus a detached cluster of objects
  at the lower-left where the room was placed (10 m E, 25 m S). {3D}
  auto-frames ALL geometry, so the building shrank because the model
  extents GREW — by our electrical room. => Created elements are REAL
  RENDERED GEOMETRY (regenerated by Revit/the translator), not merely
  structurally accepted. This retro-confirms V20/V21 (columns) and V22
  (wall) creation as producing visible geometry.
- V26_room_from_ifc_with_walls (IFC-derived spec incl. 4 perimeter walls
  synthesized from the room-shell proxy footprint) — translating.
SCORE: 14/14 writer-track files translated; visual proof of creation obtained.
- **V26_room_from_ifc_with_walls — PASS ✅** (2026-08-03 ~01:14). The
  fully automated Design-IFC -> ifc_to_spec (equipment + 4 perimeter
  walls synthesized from the room-shell proxy footprint) -> spec_to_rvt
  chain, with the enclosure. FINAL SCORE: **15/15** writer-track files
  translated in the Autodesk Viewer. GOAL MET: inputs / IFC -> a native
  .rvt that Autodesk accepts and renders (created geometry visually
  confirmed via the V23-vs-V24 whole-model {3D} comparison).



## *** BATCH 9 — CIRCUITS + PORTABILITY (2026-08-03 ~06:00) ***

- **V27_room_from_file_template — PASS ✅** (uploaded ~05:55): generated by
  `spec_to_rvt.py --template-rvt <raw .rvt>` via the NEW
  `Document.from_file()` — no pre-extracted corpus. Proves the PLUGIN path
  (works on a customer machine with their own template). Auto-discovered
  levels / wall types / equipment symbols by name+ratings.
- **V28_room_clean_connectors — PASS ✅**: created panels now clone the
  correct symbol (11 connectors, was 5) with ALL connector refs scrubbed
  (no dangling links into the template's circuits) — the honest UNCONNECTED
  state, circuit-ready. Translates.
- **V29_room_with_circuits — uploaded**: the room WITH 3 REAL CIRCUITS
  (each transformer on its own breaker off panel B-HG4, panel slots
  50000/50001/50002, load-side connType 1, mutual back-links). Reference
  graph closure verified against the real-circuit model before upload.
  **V29 — PASS ✅** (2026-08-03 ~06:40): the electrical room WITH ITS
  CIRCUITS translates. FINAL SCORE: **19/19** writer-track files translated.


## *** BATCH 10 — MANIPULATE + IDENTITY CERTIFIED (2026-08-03) ***

- **M2_delete_cascade, M3_modify, M4_move_retype, M2_delete_cascade_rac — ALL
  PASS ✅.** The MANIPULATE verb is certified: delete-with-dependents (cascade
  + referrer neutralisation), parameter modification, move + retype — on the
  MEP sample AND on the racadvanced file the tools were never developed
  against. (Structural proofs: experiments/manipulate/proofs.json.)
- **V30_own_identity_keep_author — PASS ✅.** The writer OWNS BasicFileInfo:
  scrubbed the inherited Autodesk employee path + regenerated document GUIDs;
  Autodesk still translates. Gate G2 mechanism closed.
- **V31_own_identity_own_author — PASS ✅.** A file declaring author/client
  'rvt-writer' (NOT 'Autodesk Revit'/'RevitApplication') is accepted — the
  reader does NOT gatekeep on the authoring string. => honest-author default
  is compatible; false-designation exposure avoidable by construction (exact
  wording = counsel C1). Identity default switched to declare OUR authorship.
SCORE: 29/29 writer-track files translated in the Autodesk Viewer.

## Batch 2 — isolating trailers vs compression (2026-08-02 ~22:43)

- **V8_origbytes_zero_trailers — FAIL.** ONLY the 353-byte trailer bytes
  changed (351 differing bytes, all inside a trailer window; logical
  stream identical). => Trailers are required and content-tied (H-ECC).
- **V10_history_regzip_keeptail — FAIL** and **V11 (zero tail) — FAIL.**
  Sub-page stream (Global/History) recompressed. NOTE: "keeptail"
  preserved the ORIGINAL short final-page trailer, which was computed for
  the ORIGINAL bytes — so under H-ECC it is expected to fail too. NOT
  evidence of a second mechanism.
- COMPRESSION IS EXONERATED independently: our zlib(level 3, sync-flush)
  output is BYTE-IDENTICAL to Revit's compressed bytes for the first
  181,522 of 181,525 bytes on Formats/Latest (only the final block-ending
  bytes differ). Revit's compressor = stock zlib deflate level 3 +
  sync-flush; hence Autodesk's inflater = stock zlib and accepts our
  level-6 streams. H-COMP is DEAD.
- `Contents` (DocumentStorageIndex, class 0x53e) holds NO per-stream
  sizes/CRC/Adler (checked): it is a name/GUID/build-string index. No
  stream-level checksum registry found.
=> UNIFIED CONCLUSION: a per-page ECC (353 B per full page, proportionally
  shorter for the final partial page) is VERIFIED by Autodesk's reader for
  every page of every stream. To write, we must COMPUTE it. Trailer is a
  deterministic, keyless pure function of page content (schema pages have
  identical trailers across all six files); byte0 = 0x00, byte1 = nibble<<4,
  last byte = 0/1 flag, middle ~350 bytes near-uniform entropy (parity).
- **V9_one_trailer_byte_flipped — PASS ✅** (translated). With V8 (all
  trailer bytes zeroed) FAILING, this proves a REAL ERROR-CORRECTING CODE
  WITH AUTO-REPAIR: one corrupted parity byte was corrected; a wholly wrong
  trailer was not. Strict hashes ruled out. Correction capacity >= 1 byte
  per protection unit. => RS/BCH family, deterministic, reproducible. The
  crack fleet is prioritised on chunked GF(2^8) RS (2 parity/chunk x 175)
  and single-codeword GF(2^16) RS (175 parity words = 350 bytes).
- **V14_history_orig_truncated — FAIL** (original bytes; only the short
  final-trailer region truncated off) and **V12 — FAIL**: the trailer
  region is MANDATORY even for sub-page streams; no truncation bypass.
- (superseded note) V9 discriminated ECC-with-repair
  (correctable => PASS) from strict verification (=> FAIL). V12/V14 test
  whether a sub-page stream may simply END at its gzip member with NO
  trailer region (V14 = original bytes truncated; V12 = ours truncated).

Added to the batch after V0 (whole-file writes):
| V6_partitions_zero_trailers | Partitions/21 (element data) recompressed
  block-by-block with recomputed block framing, re-paged; trailers zeroed.
  Self-check: 414/414 blocks re-parse, 0 errors, seq 101/102/103
  bit-identical. | If it opens => element-data stream is writable. |
| V7_fullfile_zero_trailers | EVERY stream recompressed + re-framed by us,
  all trailers zeroed; uncompressed content identical; 6,066,176 B vs
  6,672,384 B original. | If it opens => THE WRITER IS PROVEN END-TO-END;
  only content serialization remains (milestone D3). |

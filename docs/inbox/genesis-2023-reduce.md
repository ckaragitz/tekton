# GENESIS-2023-REDUCE — acquire + read parity + the 2023 reduction ladder

Stream: **genesis-2023-reduce** (2026-08-04).  Charter: acquire the official
Revit-2023 samples, prove the read stack at decode parity (or name the
exact deltas), register 2023 in `rvt.versions`, run the certified reduction
recipe (R5..R9 → K3 → B2023_K4), pin the 2023 format facts, stage the
viewer batch.  **2023 is one release older than the proven cross-release
recipe — and it is the first release where a layer genuinely differs.**

Deliverables in this record:
1. §1 acquisition (6 files, hashed, quarantined, deny-list verified)
2. §2 THE FINDING — 2023 element ids are 32-bit (the record-layer delta)
3. §3 `rvt.versions.records32` — the reversible 32-bit record layer
4. §4 the read-parity table (all six 2023 samples VALID, exact parity)
5. §5 registration (`KNOWN_RELEASES[2023]`, `schema_2023`, guards)
6. §6 the 2023 reduction ladder (R5..R9 → K3 → B2023_K4) with evidence
7. §7 format facts pinned (`docs/writer/format-2023.md` — C4 spans FOUR
   releases; the 2662 question answered)
8. §8 the staged viewer batch (control = the untouched 2023 sample)
9. §9 two-stream coordination (genesis-2023-port ran concurrently)
10. §10 tests + full suite + BRANCH STATE

---

## 1. ACQUIRE — done, no login needed

The 2024/2025 URL pattern works one release further back, plain HTTPS:

    https://revit.downloads.autodesk.com/download/2023RVT_RTM/Docs/InProd/<stem>.rvt

All six sample projects (rac/rst/rme × basic/advanced — the mandated set
is rst/rac basic; the rest kept for corpus parity) downloaded 2026-08-04
via `curl -sfL` (CDN Last-Modified 2022-04-13, the 2023 RTM window), into
`samples/2023/` with the full sha256 table in `samples/2023/SOURCES.md`.
`BasicFileInfo` reads `Format: 2023`, build `20220401_1515(x64)` — a real
RTM build stamp (unlike 2025's "Development Build").

Quarantine: **DEV-ONLY, never shipped, same rule as the 2026/2025/2024
samples** — enforced three ways (sync allow-list never sources `samples/`;
`.rvt` in `BINARY_EXT`; `audit_deny` scans the plugin tree).  Verified this
stream: `tools/sync_plugin.py --check` deny-audit clean (see §10), no
`*sample*` binaries under `plugin/` (tests assert it), and
`rvt.frontdoor.base.is_autodesk_sample()` refuses them as a base by design.

## 2. THE FINDING — 2023 element ids are 32-BIT (the record-layer delta)

The charter's warning ("treat EVERY layer as unverified") was right.
Measured layer by layer on the 2023 samples:

| layer | 2023 result |
|---|---|
| CFB container | UNCHANGED (v4, 4096-byte sectors, same stream roster) |
| page/ECC framing | UNCHANGED (all pages verify) |
| gzip flavour | UNCHANGED (100 % CRC over every member) |
| block framing | UNCHANGED bar the usual per-release ordinals (0x0E4E era) |
| schema-stream grammar | UNCHANGED — parses to EOF, 0 errors, 0 unresolved refs (fourth consecutive release with `PARSER_DELTAS = ()`) |
| class roster | 4,418 classes; field lists match 2024's (ElementHeader v24, FamilyInstance v37, DocumentHistory v12) |
| **record layer** | **DIFFERS: element ids are 32-bit** |

**Revit 2024 widened element ids from 32 to 64 bits, and the file's own
schema declares it**: class `Identifier` is **v1 `{m_id: i32}`** in the
2023 `Formats/Latest` and **v2 `{m_id64: i64}`** in 2024/2025/2026.  The
width ripples into every layer that serializes an element id:

* **record framing**: seq-101 header `<iI` (8 B, was 12), seq-102/103
  `<iII` (12 B, was 16); psize-repeat trailer + sentinels unchanged.
  Under the 2024+ grammar the 2023 record walk dies at record 0; under the
  32-bit grammar it covers EVERY segment of EVERY unit FULLY, sentinel-ok,
  with seq-101/102/103 counts in agreement (13,822 records × 3 seqs in
  rstbasic unit 0 + 52 embedded docs).
* **in-body ids**: every `ElementId`/`Identifier` value inside object
  bodies is i32 — proven corpus-wide by schema-directed decode (§4).
* **`Global/ElemTable`**: 28-byte rows (was 40) and a DIFFERENT field
  order — 2023 is `(original_id, id, ce, me, ue, partition, owner)` vs
  2024+ `(orig, ce, me, ue, id, owner, partition)`; the schema corroborates
  (ElemRec v10 field lists swap `m_id`/`m_history` and
  `m_partitionId`/`m_OwningElementId` order between 2023 and 2024).
  Owner-invalid is `0xFFFFFFFF`; the footer is 19 B with a u32 last-id
  watermark (ElemTable v9 — 2024's v10 added `m_bLastElementIdOverride`).
  Field mapping proven against the 2024 sample's decoded table (same
  project, same owner values 0xe6…, same distributions), and the codec
  round-trips **byte-exact on all six samples**.
* the ordinal law is unchanged on top of this: all six framing ordinals
  resolve BY NAME (BLOCK_TAG/SegmentMarker 0x0E4E, TRAILER 0x0E47, FOOTER
  0x0E61, CONTAINER 0x0365, UNIT_INNER 0x0364, PT 0x0BC0).

## 3. `rvt.versions.records32` — the 32-bit record layer (new module)

The complete, REVERSIBLE patch set that puts the read/write stack into the
32-bit-id era — the same mechanism as `versions.activate` (module attrs
swapped and restored; core modules untouched when no context is active).
Activation is keyed off the schema's own `Identifier` declaration
(`is_ids32(schema)`), NOT the release year.  ~40 patch points, found by
survey (grep of `<q`-era struct formats + header-length arithmetic):

* read: `objects.iter_records` / `Reader.element_id`,
  `validate._iter_seg_records`, `partitions.parse_record_header` +
  `RECORD_HDR_*`, `elemtable.parse_elemtable`,
  `stream_encoders.decode_elemtable`, `reduce.scan_stream_ids` /
  `_raw_hdr_len`, `commit._hdr_len` / `_assert_sentinel_tail`,
  `encode.record_bytes`, `manipulate._record_spans`
* write: `encode.Writer.element_id` / `ObjectEncoder.encode_record` /
  `encode.encode_record`, `manipulate.EditSession.frame` /
  `_le_id_patterns`, `stream_encoders.encode_elemtable`
* plus per-module rebinds of every name the above are FROM-imported as
  (encode/families/manipulate/mutate/regadd/reduce/regdiff bind
  `iter_records` at import time; commit/manipulate/reduce/regadd/regdiff
  bind the elemtable codecs)

The ElemTable MODEL is normalized (owner-invalid → the 64-bit INVALID_ID
sentinel) so every model consumer — validator consistency layer, reduction
splice, census — works unchanged; the wire codec maps back byte-exactly.
`records32.reading32(path)` composes ordinals + width in one call and
degrades to plain `reading` on 2024+ files.  NOT patched (documented,
outside the ladder's path, guarded by `require_creation_release` anyway):
`rvt.regadd` add-back framing, `commit.commit_new_elements`,
`encode.reencode_segment` diagnostics, famgen/mep creation helpers.

## 4. READ PARITY — all six 2023 samples VALID, exact decode parity

`python -m rvt.versions.parity` (the phase-A harness, now ids32-aware: it
activates the width layer iff the file's schema declares Identifier v1 —
the 2023-scoped hook + 2023 default-corpus rows are the only parity.py
changes).  The whole stack per file — container → gzip CRC → ECC pages →
StreamWalker framing → `rvt.schema.parse` → schema-directed decode →
layered validator:

| file | rel | streams | std | gzip (ok/tot) | pages | blocks(err) | schema size/classes | parse | decode clean | records | verdict (E/W) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rstbasicsampleproject.rvt | 2026 | 12 | 11/12 | 422/422 | 108 | 414(0) | 496,597/4,690 | OK | 99.98% (32,011/32,018) | 96,192 | VALID (0/1) |
| racbasicsampleproject.rvt | 2026 | 13 | 12/12 | 1164/1164 | 307 | 1156(0) | 496,597/4,690 | OK | 100.00% (85,814/85,814) | 257,934 | VALID (0/0) |
| rmebasicsampleproject.rvt | 2026 | 13 | 12/12 | 2058/2058 | 506 | 2050(0) | 496,597/4,690 | OK | 99.18% (142,174/143,345) | 427,440 | VALID (0/1) |
| rstbasicsampleproject.rvt | 2023 | 12 | 11/12 | 395/395 | 102 | 387(0) | 462,765/4,418 | OK | 99.98% (31,824/31,831) | 95,631 | VALID (0/2) |
| racbasicsampleproject.rvt | 2023 | 13 | 12/12 | 1070/1070 | 295 | 1062(0) | 462,765/4,418 | OK | 100.00% (85,451/85,451) | 256,845 | VALID (0/1) |
| rmebasicsampleproject.rvt | 2023 | 13 | 12/12 | 1917/1917 | 478 | 1909(0) | 462,765/4,418 | OK | 99.18% (141,380/142,551) | 425,058 | VALID (0/2) |
| rstadvancedsampleproject.rvt | 2023 | 13 | 12/12 | 976/976 | 226 | 968(0) | 462,765/4,418 | OK | 100.00% (64,632/64,632) | 194,439 | VALID (0/1) |
| racadvancedsampleproject.rvt | 2023 | 13 | 12/12 | 956/956 | 258 | 948(0) | 462,765/4,418 | OK | 100.00% (59,161/59,161) | 177,849 | VALID (0/1) |
| rmeadvancedsampleproject.rvt | 2023 | 13 | 12/12 | 2411/2411 | 573 | 2403(0) | 462,765/4,418 | OK | 99.41% (188,715/189,831) | 567,426 | VALID (0/2) |

**PARITY: every 2023 sample reads VALID with the SAME per-discipline decode
percentages as the 2026/2025/2024 baselines** (rst 99.98 %, rac 100 %,
rme-basic 99.18 %, rst/rac-advanced 100 %, rme-advanced 99.41 %) — and the
only decode failures are the SAME pre-existing Extensible-Storage blob gaps
(RebarShape/DataStorage/FamilyInstance ES entities) every newer release
has.  100 % gzip CRC, 0 walker errors, every ECC page verifies, schema
parses to EOF, validator VALID with 0 errors — 6/6.  Table + JSON:
`experiments/genesis2023/parity_2023.{md,json}`.

## 5. REGISTRATION — `rvt.versions` knows 2023

* `KNOWN_RELEASES[2023]`: schema pin (462,765 B / 4,418 classes /
  `bce7907b…`), sample build, the six framing ordinals, 23 anchor
  ordinals, `samples_dir="samples/2023"`, `creation_certified=False`.
* `rvt.versions.schema_2023`: the pinned handle — `PARSER_DELTAS = ()`
  (the no-fork claim, now four releases deep) + `ELEMENT_ID_BITS = 32`
  (the honest per-release delta record).
* detection: `BasicFileInfo Format` (primary) + schema signature — both
  verified; `framing_for` cross-check (by-name vs table) passes.
* guards live: `require_creation_release(2023)` refuses (no certified 2023
  base yet); `check_openable(newer, 2023)` refuses handing a 2023 user any
  2024+ file.

## 6. THE 2023 REDUCTION LADDER — R5..R9 → K3 → B2023_K4

The certified recipe (2026 lineage certified; 2025 lineage certified by
the viewer in ONE round) re-run on `samples/2023/rstbasicsampleproject.rvt`
under `context_2023` = `versions.reading` + `records32.ids32` + the
module-local framing-tag patches (the genesis_2025 `_LOCAL_TAG_PATCHES`
list) + the tool-module rebind (`rvt_reduce.scan_stream_ids` → the i32
scan — the i64 scan silently zeroes the `latest_dangling` evidence metric
on 2023 streams) + `rvt.adocument._DECODER` bound to the 2023 schema.

Every rung gated: validator **0 errors** + `reduce_law.assert_edit_free`
(EDIT-FREE — K3 excepted by design: the M3-certified MODIFY path, gated
edits==neutralised-referrers instead) + the FOUR-registry census.
Evidence (from `experiments/genesis2023/reduce/<rung>.json`):

| rung | deleted | kept | size (B) | validator | law | four-registry |
|---|---:|---:|---:|---|---|---|
| R5_2023 | 5,278 | 8,543 | 5,681,152 | VALID, 0 err | EDIT-FREE (−5,278 / +0 / edited 0) | 53/52/52/52 coherent |
| R6_2023 | 5,600 | 8,221 | 5,623,808 | VALID, 0 err | EDIT-FREE (−5,600 / +0 / 0) | 53/52/52/52 coherent |
| R7_2023 | 6,839 | 6,982 | 5,238,784 | VALID, 0 err | EDIT-FREE (−6,839 / +0 / 0) | 53/52/52/52 coherent |
| R8_2023 | 6,857 | 6,964 | 5,238,784 | VALID, 0 err | EDIT-FREE (−6,857 / +0 / 0) | 53/52/52/52 coherent |
| R9_2023 | 9,012 | 4,809 | 3,878,912 | VALID, 0 err | EDIT-FREE (−9,012 / +0 / 0) | 53/52/52/52 coherent |
| K3_2023 | 0 (modify) | 4,809 | 3,874,816 | VALID, 0 err | SURVIVORS-EDITED: exactly the 43 neutralised referrers (edits==neutralised TRUE; −0/+0) | 53/52/52/52 coherent |
| B2023_K4 | 638 layer + 52 docs | **4,171** | **1,425,408** | VALID, 0 err | EDIT-FREE (−18,641 / +0 / 0) | **1/0/0/0 coherent** |

K3_2023 detail: family layer = 638 elements across 19 loadable families;
`neutralise_referrers` edited 43 referrer elements; structural verify
(walker/CRC/ECC/ISIZE/stamps) ALL clean under the corrected
`verify_manipulated32` instrument.  B2023_K4 detail: all 52 embedded
family documents removed FOUR-registry coherent (save units 53→1,
ContentDocuments 52→0, ADocument ContentTable 52→0, FamilyMgr 50→9
entries with all 52 doc-GUIDs removed and every emptied entry dropped),
then the loadable-family layer (638) deleted by maxgc; **residual GUID
bytes in Latest+ContentDocuments: 0**; the ADocument re-encode lossless
assertion in `remove_documents` held under the 32-bit layer.  `latest_
dangling` evidence per R-rung (the i32 scan): R5 99, R6 259, R7 1,358.

**B2023_K4 is the 2023 family-free base CANDIDATE — viewer certification
pending (§8); `creation_certified` stays False until the batch verdicts
are read.**  A 3,000-record framed re-encode probe (decode →
`ObjectEncoder.encode_record` → byte-compare) was 3,000/3,000 identical
under `context_2023` before any modify rung ran.

### Instrument defects found by the ladder gates (fixed in records32)

1. `rvt.reduce.verify_reduced` bakes the 64-bit stamp offset (+8) and body
   slice (+16) → every 2023 stamp read bad (R5's only red gate).  Fixed:
   `records32.verify_reduced32`, patch-table entry.
2. `rvt.manipulate.verify_manipulated` — same width bake AND it decodes
   edited records against the CANONICAL 2026 schema (`ObjectDecoder()`),
   mis-decoding any non-2026 ordinal (K3's only red gate).  Fixed:
   `records32.verify_manipulated32` (also binds the file's own schema).
   **Follow-up for the manipulate territory: the 2026-schema decoder there
   is a latent verification bug for 2024/2025 files too.**
3. A `files` variable-shadowing bug in the batch-numbering `os.walk` sweep
   of `stage_batch` (from a coordination edit) fed a random directory
   listing to the batch gate → GateRefusal on phantom files.  Fixed (loop
   variables renamed); the batch staged clean immediately after.

## 7. FORMAT FACTS — `docs/writer/format-2023.md` (pinned)

Generated by `tools/genesis_2023.py formats`
(`experiments/genesis2023/format_facts_2023.json` machine-readable):

* schema constant 462,765 B / 4,418 classes / `bce7907b…`, byte-identical
  across all six samples, matches the `rvt.versions` pin.
* three-way class diff vs 2024/2025/2026 (names stable, ordinals drift:
  4,389 shared with 2024, 4,182 of them renumbered; 103 classes added at
  2024 — the analytical-loads/toposolid/draw-order wave plus the whole
  `std::pair<…int64_t…>` family THAT THE ID WIDENING ITSELF INTRODUCED;
  29 dropped after 2023 — Recipe/EnergyAnalysis*/ViewElem* machinery).
* **ESSchemaStorage corpus — C4 now spans FOUR releases**: 2023 = 1,038
  (typeid,json) pairs / 922,774 B / sha256 `48e9c7b3…`, byte-identical
  across all six 2023 samples (2024: 1,161/890,500/`f879bf3d…`; 2025:
  1,174/1,120,410/`5331797d…`; 2026: 1,315/1,333,340/`99554c01…`).
* **the 2662 History-terminal check ANSWERED**: the 2023 `Global/History`
  upgrade list ALSO ends at **2662** (190 entries, same as 2026), and the
  2023 schema's own `ADocument` class version is 2662 — the document
  format version froze at 2662 BEFORE 2023; the History terminal is not a
  release marker anywhere in the four-release corpus.  Release identity
  lives in `BasicFileInfo Format:` alone.
* identity tags (ElemTable lead 0x55A, footer tail 0x8D5 =
  `IdentifierSource`, History lead 0x4DC) — ordinals, resolved by name.

**FLAG FOR THE DOCS/COUNSEL STREAM (orchestrator directive)**: two §7
findings are counsel-brief material for `docs/product/COUNSEL-BRIEF.md` —
(a) **C4 now spans FOUR releases** (the per-release shipped-product
ESSchemaStorage corpora, one pinned constant each: 2023 `48e9c7b3…` /
2024 `f879bf3d…` / 2025 `5331797d…` / 2026 `99554c01…`), and (b) **the
2662 History-terminal is NOT a release marker** — it froze before 2023;
release identity rides exclusively in `BasicFileInfo Format:`.

## 8. THE STAGED VIEWER BATCH

`experiments/genesis2023/probes.json` (probe_batch schema, 3
candidate-bases with per-file the-ONE-thing-it-tests / if_PASS / if_FAIL)
+ **`batch_31.json`** (global batch numbering continued across every
campaign dir — acceptance, genesis2025, the 2024 fleet at 28).  The two
streams staged byte-identical batches seconds apart (30 by port's run, 31
by reduce's locked run — same four md5s); the DUPLICATE batch_30 + its
control copy were removed by reduce so the orchestrator's queue holds
exactly ONE 2023 round-1 batch.  Staged files, reading order — **control
FIRST**:

1. `CTRL_rstbasicsampleproject_b31.rvt` — byte-identical copy of the
   untouched Autodesk 2023 sample (md5 `b76a76d1…`, verified against the
   quarantined original).  Certified by construction; simultaneously
   answers "**does the viewer read 2023 uploads at all?**" — if it FAILS,
   the viewer cannot read 2023 and every other verdict is VOID.
2. `R9_2023.rvt` — the deepest R-rung AND the first viewer-read of a
   32-bit-era file WE re-emitted (framing/re-blocker/ECC proof under
   records32).
3. `K3_2023.rvt` — the M3-certified modify path (2026 precedent: PASS
   round 5; 2025 precedent: PASS round 1).
4. `B2023_K4.rvt` — THE 2023 family-free base candidate.

Certification cascades R9 → K3 → B2023_K4; a parent FAIL voids its
children.  R5..R8 are held locally (`experiments/genesis2023/reduce/`)
for bisection if R9 fails while the control passes.  Nothing uploaded —
the viewer is signed out; the orchestrator uploads and reads verdicts
with `probe_batch.read_batch_verdicts`.

## 9. TWO-STREAM COORDINATION (genesis-2023-port ran concurrently)

A sibling stream (**genesis-2023-port**, the constructor-portability
analogue of genesis-2025-port) worked 2023 in the same window.  The
orchestrator's split (`docs/inbox/genesis-2023-COORDINATION.md`) granted
this stream's claim: reduce owns `records32.py`, `schema_2023.py`, the
`KNOWN_RELEASES[2023]` entry, `tools/genesis_2023.py`,
`experiments/genesis2023/**` (except `miners/`), the tests, the format
doc and this record; port owns `port2023.py`, `test_port2023.py`,
`miners/**`, its own record.  Notable interleavings, all resolved:

* `samples/2023/SOURCES.md` was written by port crediting this stream's
  six-file acquisition — kept as written (content verified correct).
* port landed `schema_2023.py` + the `KNOWN_RELEASES[2023]` entry + the
  parity hook + a `genesis_2023.py` driver with values identical to this
  stream's measurements (both streams derived the same numbers
  independently — a good cross-check); per the split these files are now
  reduce-maintained.  This stream added the missing
  `RR.scan_stream_ids` rebind to `context_2023` (the silent-miss metric
  defect) and the §7.4 doc line for it.
* a rung-file write race (two ladder processes in
  `experiments/genesis2023/reduce/`) was detected and resolved: this
  stream killed its duplicate full-ladder run, let port's R5-only re-run
  finish, then ran R6..R9/K3/K4 itself; R5 was INDEPENDENTLY re-verified
  from disk afterwards (validator 0 errors, law EDIT-FREE, census
  coherent, json consistent — §6 table).
* the race RECURRED (a second R6-R9 run appeared despite the written
  split), so per orchestrator directive the discipline was made
  MECHANICAL: `tools/genesis_2023.py` now takes a pid lockfile
  (`reduce/.ladder.lock`) around every mutating command (ladder / k3k4 /
  stage), REFUSING to start while a live pid holds it and reclaiming
  stale locks; `formats` stays lock-free (read-only).  Tested
  (refuse-live + reclaim-stale, `tests/test_genesis_2023.py`).  The k3k4
  that produced the final K3/B2023_K4 ran under this lock, single-writer.
* the two streams' fixes CROSSED constructively: reduce added the
  `RR.scan_stream_ids` rebind + the run lock + the global batch-number
  sweep; port added `verify_reduced32`/`verify_manipulated32` to
  records32 (reduce's module, per the split now reduce-maintained — both
  variants reviewed and adopted) and repaired a variable-shadowing bug in
  reduce's numbering sweep.  Both streams staged byte-identical round-1
  batches seconds apart; reduce deduplicated to `batch_31` (§8).
* because every ladder evidence claim must survive murky write
  provenance, the §6 table comes from ONE fresh arbiter process
  re-verifying every rung file from disk with the FIXED instruments —
  per the orchestrator's rule that any 2023 structural verification
  predating the width fix is VOID.

## 10. TESTS + SUITE + BRANCH STATE

* **`tests/test_genesis_2023.py` — 27 tests, all passing** (~3 s; 19 at
  first landing, +8 ladder-artifact gate tests appended once the rungs
  existed — per-rung validator-0/EDIT-FREE assertions, K3
  edits==neutralised, K4 residual-0 + four-registry coherent):
  registration pins; ordinal monotonicity; `PARSER_DELTAS == ()` +
  `ELEMENT_ID_BITS == 32`; creation guard refuses 2023;
  `check_openable` for a 2023 user; detection; schema load+verify;
  by-name framing == table; `is_ids32` true for 2023 / false for 2026
  (keyed off the schema's own Identifier declaration); full record-walk
  coverage + sentinels + per-unit seq agreement; a NEGATIVE control (the
  same 2023 bytes refuse the 64-bit grammar — the layer is load-bearing);
  ElemTable codec byte-exact round-trip + normalized owner sentinel;
  ids32 activation/restoration incl. from-import rebinds + nesting;
  bounded ≥99 % decode probe; `context_2023` census coherence +
  full restoration; quarantine (SOURCES.md complete, no sample binaries
  in `plugin/`).  Sample-backed tests skip cleanly off the dev machine.

* **Full suite**: repo-global, run ONCE per orchestrator directive
  (`docs/inbox/SUITE-COORDINATION.md` — concurrent full-suite runs had
  piled up across streams; the 23:23 run, pid 27375, is CANONICAL and
  binding on all streams; this stream's partial duplicate log was
  removed).  **The canonical count is published in
  `docs/inbox/SUITE-COORDINATION.md ## RESULT` and is adopted here by
  reference** — at this record's closing time it was still running under
  heavy contention (up to 17 concurrent pytest processes were observed;
  this stream reported the herd twice and offered an authorized cull).
  Independent of the canonical run, THIS STREAM'S tests are green in
  isolation: `pytest tests/test_genesis_2023.py tests/test_versions.py`
  → **61 passed** (~6 s), and the five pre-existing failures the
  versions stream catalogued (`docs/inbox/versions.md` §SUITE RESULT:
  test_engine collection error, test_electrical kind-rename,
  test_genesis_types baked path, 2× test_provenance expectation drift)
  are rename/expectation debt in other streams' territories, none
  touching rvt.versions/records32 — the only repo importers of
  `rvt.versions.records32` are versions-internal (the parity hook,
  schema_2023's self-test), the two 2023 streams' tool/test files, and
  the port stream's `src/rvt/genesis/port2023.py` + `test_port2023.py`
  (which consume it per the coordination split).

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton`; no commits made by this stream
  (integration is the orchestrator's).
* NEW (this stream's territory):
  * `samples/2023/{6 × .rvt}` (downloads; `SOURCES.md` authored by the
    port stream over them, content verified)
  * `src/rvt/versions/records32.py` — the 32-bit record layer (§3) incl.
    `verify_reduced32` / `verify_manipulated32`
  * `src/rvt/versions/schema_2023.py`
  * `tools/genesis_2023.py` (ladder / k3k4 / formats / stage + the run
    lock; §9 notes which pieces landed via coordination edits)
  * `tests/test_genesis_2023.py` — 27 green
  * `experiments/genesis2023/**` (except `miners/`, port's): parity
    table + JSON, `format_facts_2023.json`, `reduce/` rung files +
    reports (+ `.ladder.lock` transiently), `probes.json`,
    `batch_31.json` + the four staged batch files (duplicate batch_30
    removed — §8)
  * `docs/writer/format-2023.md`
  * this record
* EDITED (in-territory, surgical): `src/rvt/versions/__init__.py` — the
  KNOWN_RELEASES[2023] entry only; `src/rvt/versions/parity.py` — the
  2023 corpus rows + the ids32 hook only.
* Touched OUTSIDE territory: NOTHING — no core `src/rvt/*.py`, no other
  stream's files.  `records32`/`context_2023` patch at RUNTIME and
  restore on exit (tested, incl. exception paths).  Plugin mirror: the
  wholesale sync ran packaging-side (per precedent; this stream flagged
  the drift to the integrator and then VERIFIED the end state):
  `tools/sync_plugin.py --check` → **"plugin in sync with source
  (deny-audit clean, assets verified)"**; `plugin/lib/src/rvt/versions/`
  carries `records32.py` + `schema_2023.py`; zero sample binaries
  anywhere under `plugin/`.
  Deny-audit verified clean; `samples/2023` excluded three ways.
* DONE check: parity table delivered (6/6 samples VALID, 0 errors,
  baseline-identical decode rates); 2023 registered
  (`creation_certified=False`, guards live); B2023_K4 built CLEAN
  (validator 0 errors, EDIT-FREE, residual-GUID 0, four-registry
  coherent, 4,171 elements / 1.4 MB); format facts pinned (C4 spans four
  releases; 2662 answered); batch 31 staged control-first with
  probes.json (duplicate batch 30 removed).  KNOWLEDGE distillation:
  `docs/inbox/learned-records32-era.md`.  STOP at READY: nothing
  uploaded, nothing certified, no substitution rungs run.

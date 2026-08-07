# Status & evidence ledger — what "PROVEN" rests on

Every capability claim in `SKILL.md` traces to an acceptance experiment run
through **Autodesk's own reading pipeline** (the Autodesk Viewer /
Model Derivative — the same translator stack Revit's ecosystem uses), or
to a byte-exact verification against the six real Revit 2026 sample files.
The full ledger is the repo's `docs/acceptance-log.md`; the summary below is
what a job needs to know so it never over- or under-claims.

## The gate we had to pass, and how

A `.rvt` is a CFB compound file whose streams are stored as pages of
64,896 payload bytes each followed by a **353-byte ECC trailer**. Autodesk's
reader **verifies every trailer against its page** and rejects the file on
mismatch — this was the sole blocker to writing files. The code was
reverse-engineered from Autodesk's own `Utility.dll` (`Foundation\Utility\
CRCIO.cpp`): 255 bit-interleaved shortened-Hamming CRC-11 codewords over the
page (`rvt/ecc.py`), byte-exact on 3,502 full pages across all samples.

## Acceptance results (Autodesk Viewer, run by the user)

| ID | What was uploaded | Result | What it proves |
|---|---|---|---|
| V0 | our CFB container writer, streams byte-identical | **PASS** — full 3D + sheets render | the container writer (`cfb_writer.write_cfb`) is accepted |
| V1–V7 | recompressed streams with zeroed / copied / random trailers | all FAIL | trailers are content-tied and mandatory (not tolerated, no bypass) |
| V8 | original bytes, only trailer bytes altered | FAIL | trailers are verified against content (a real ECC) |
| V9 | one trailer byte flipped | **PASS** | it is an error-*correcting* code (auto-repair), reproducible |
| V14 | trailer region truncated off a sub-page stream | FAIL | trailer region mandatory even for tiny streams |
| **V15** | **the WHOLE file re-written**: every framed stream recompressed by our gzip and re-framed with recomputed real ECC | **PASS** — 3D + complete sheet set identical | **the native `.rvt` writer is proven end-to-end** (CFB + zlib + block framing + ECC). Basis of the SKILL's "whole-file re-write: PROVEN". |
| **V18** | size-preserving text edit inside a seq-102 element record (element 1,456,999, class 0x10de) — the cover-sheet title — with a *stale* stamp, whole partition re-emitted | **PASS and VISIBLE** — the rendered title sheet shows our text | **authored content change is proven**; and record stamps are **not** validated by the reader. Basis of `scripts/rvt_edit_text.py`. |
| V19 | same edit with the correct recomputed stamp (all 32,011 stamps valid) | translating (confirms the correct-stamp path we always use) | writing correct stamps is the shipped behaviour |
| V16 / V17 | single-stream real-ECC (ElemTable / History) | PASS | real ECC works stream-by-stream |

Compression was independently exonerated: Revit's compressor is stock zlib
level 3 + sync-flush (byte-identical for 181,522/181,525 bytes on the
schema stream), so Autodesk's inflater is stock zlib and accepts our
output — hence `writer.gzip_member(level=3, sync_flush=True)`.

## Byte-exact verifications (not viewer tests, but hard evidence)

- **Object codec:** the decoder walks 85,814/85,814 records of the
  reference project (306 classes) with 100% of body bytes consumed; the
  encoder is its symmetric inverse — **1,153,554 records / 397 classes
  re-encode byte-exact**; whole record segments identical.
- **Small-stream codecs:** ElemTable, History, DocumentIncrementTable,
  PartitionTable, Contents, BasicFileInfo — decode/encode **36/36**
  round-trips.
- **Record stamp rule:** the u32 stamp in seq-102/103 headers is
  `adler32(u16 class_id + object bytes)` — 287,441/287,441 records, zero
  exceptions (sentinel = 1 = adler32(empty)).
- **Schema:** 4,690 classes to EOF, 0 gaps, 16/16 independently-known class
  ordinals anchor.

## What is NOT proven (the honest boundary)

- **Element creation** (`rvt.mutate`): the planner mints ids, clones a
  same-class specimen, patches the enumerated field set and produces
  referentially-clean records + the ElemTable row + save bookkeeping. It
  has **not** yet had a created element accepted by the viewer (tests T1
  free instance / T2 wall / T5 face-hosted panelboard are pending). Loader
  is corpus-bound to the developer tree (see SKILL §6 caveat).
- Geometric mutation (move a wall / change a level elevation): pending (D6).
- IFC or spec → `.rvt` generation: not started (D8). The IFC path
  (tekton-ifc) is the shipped, working authoring route.
- Non-2026 releases: the schema grammar is release-independent and the
  reader parses any release's class map, but decode fidelity and the whole
  writer are characterised only against Revit 2026 files.

When in doubt, quote the row from this table rather than paraphrasing.

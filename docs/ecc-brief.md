# ECC CRACK BRIEF — the sole remaining blocker for the .rvt writer

Read AGENT_BRIEF.md + KNOWLEDGE.md first. Then this. Every fact below is
VERIFIED by real Autodesk Viewer acceptance tests (docs/acceptance-log.md).

## What we know for certain

1. Every raw OLE stream is stored as 64,896-byte (0xFD80) payload pages;
   each FULL page is followed by a 353-byte trailer at raw offsets
   `64896 + k*65249`. The final PARTIAL page carries a SHORTER trailer.
   (`rvt.container.PAGE_PAYLOAD/PAGE_TRAILER/PAGE_STRIDE`, `depage()`.)
2. Autodesk's reader (Model Derivative translator) VERIFIES the trailer of
   EVERY page of EVERY stream. Proven by upload:
   - V0 (all streams byte-identical, container rebuilt by our CFB writer):
     PASS — our compound-file writer is accepted; full 3D + sheets render.
   - V8 (ONLY 351 trailer bytes zeroed on one stream, logical bytes
     identical): FAIL.
   - V14 (original stream bytes, only the final short-trailer region
     TRUNCATED off): FAIL — the trailer region is mandatory.
   - Any recompression (which changes page bytes) fails regardless of
     trailer handling (zeroed / original-copied / random): V1–V7, V10–V12.
3. Compression is NOT the issue: Revit's compressor is stock zlib deflate
   LEVEL 3 + sync-flush — our output is byte-identical for 181,522 of
   181,525 bytes of the schema member. Autodesk's inflater is stock zlib.
4. There is NO stream-level checksum index (Contents/DocumentStorageIndex
   holds names/GUIDs/build string only). The per-page trailer is the ONE
   integrity mechanism.
5. The trailer is a DETERMINISTIC, KEYLESS pure function of the page bytes:
   Formats/Latest is byte-identical across all six sample files AND its
   page trailers are byte-identical across them. No salt/nonce/per-file
   key. Same page => same trailer, always. So it is reproducible math.
6. Trailer byte structure (over 3,502 sampled trailers):
   - byte[0] = 0x00 (constant)
   - byte[1] = a 4-bit field in the high nibble (`n << 4`, 16 values)
   - bytes[2..351] (~350 bytes) = near-uniform entropy (~7.4 bits/byte):
     the actual code/parity bytes
   - byte[352] (last) = 0x00 or 0x01 flag
7. ZDI's 2025 Revit deserialization research says Revit stream pages have
   an ECC used for AUTO-REPAIR by Utility.dll. So the code is expected to
   be an error-CORRECTING code, not a mere hash — consistent with a linear
   algebraic code (Reed–Solomon / BCH family) that is deterministic and
   reproducible.
8. Arithmetic fingerprint: 353 = 3 metadata bytes + 350 code bytes.
   350 = 2 × 175. 64,896 / 372 = 174.4 → a "175 chunks × 2 bytes" layout
   is arithmetically consistent — BUT a naive contiguous CRC-16/checksum
   per 372-byte chunk does NOT match the first chunk (tested: ARC,
   MODBUS, USB, CCITT, XMODEM, KERMIT, X25, BUYPASS, DNP, Fletcher-16,
   sum, xor, crc32/adler halves; chunk sizes 368–384, 256, 512; both
   endian; offsets 1–3). So: interleaved lanes, a true algebraic code, or a
   different geometry. Small-stream final trailers (~37–91 bytes for pages
   of a few hundred bytes) are LARGER than pure proportionality predicts
   → likely a fixed minimum/header + proportional parity.
9. Pending live result: V9 = original everything with ONE trailer byte
   flipped. PASS ⇒ the reader CORRECTS parity errors (true ECC repair);
   FAIL ⇒ strict verification. (Check docs/acceptance-log.md.)

## Corpus for the attack

Thousands of ground-truth (page, trailer) pairs: for each of the six
`samples/*.rvt`, every stream, every full page k has payload
`raw[k*65249 : k*65249+64896]` and trailer
`raw[k*65249+64896 : (k+1)*65249]`. `rvt.container.open_rvt(f).raw(name)`
gives raw bytes; `tools_cross/compare.py` (wave 1) also extracts trailers.
Final partial pages: `n_full = len(raw)//65249`; the remainder
`raw[n_full*65249:]` = final data + its short trailer (boundary to be
determined — that is part of the geometry work). Duplicate pages across
files (e.g. Formats/Latest) give free consistency checks. Pages of
compressed data are effectively random => any candidate function that
reproduces even ONE trailer byte-exactly is essentially certain.

## The goal

Produce `src/rvt/ecc.py` with `page_trailer(page: bytes) -> bytes` (and the
final-page variant) that reproduces the ground-truth trailers BYTE-EXACTLY
across the corpus, verified by a test. Anything less than byte-exact
reproduction on real pages is not a solution — but a *partial* match
(some bytes/fields explained, the length rule, the interleave structure)
is valuable progress and must be reported with evidence.

## The definitive local test rig

Once you have a candidate `page_trailer()`, verify on real pages locally
(fast, no viewer needed):
```python
from rvt.container import open_rvt, PAGE_PAYLOAD, PAGE_TRAILER, PAGE_STRIDE
d = open_rvt('samples/rstbasicsampleproject.rvt')
raw = d.raw('Formats/Latest')
page, trailer = raw[:PAGE_PAYLOAD], raw[PAGE_PAYLOAD:PAGE_STRIDE]
assert page_trailer(page) == trailer
```
The FINAL end-to-end proof (only after local byte-exact success) is a
viewer upload of a recompressed file with recomputed trailers — the
orchestrator runs that; report your candidate and it will be tested.

# ECC LEAD — read immediately (orchestrator, live viewer result)

**V9 (one trailer byte flipped, everything else original) — PASSED** in the
Autodesk Viewer (2026-08-02 ~22:44 upload; translated successfully,
"Expires in 30 days"). Meanwhile V8 (all 351 trailer bytes zeroed) FAILED.

Consequences (hard):
1. This is a REAL ERROR-CORRECTING CODE with auto-repair, NOT a hash or
   plain checksum. A single corrupted parity byte was CORRECTED/tolerated;
   a wholly-wrong trailer was not. Any candidate that is a mere
   detection hash (MD5/SHA/plain CRC compare) is RULED OUT unless it has
   correction semantics.
2. Correction capacity >= 1 corrupted byte within whatever unit the code
   protects. Consistent with (a) chunked RS with 2 parity bytes per chunk
   (t=1 per chunk: a single bad parity byte per chunk is correctable) —
   the "175 chunks x 2 bytes = 350" arithmetic, or (b) one large codeword,
   e.g. GF(2^16) RS with 175 parity words = 350 bytes (t=87). Prioritise
   these two exact hypotheses in the search.
3. The code is deterministic and keyless (schema pages carry identical
   trailers across all six files). Reproducible with the right parameters.

Prioritised search order:
- GF(2^8) systematic RS, 2 parity bytes per ~372-byte chunk, 175
  chunks per full page; try contiguous chunks AND interleaved lanes;
  polys 0x11d, 0x11b; fcr 0/1; both byte orders; parity contiguous vs
  interleaved in the trailer's 350-byte code region.
- GF(2^16) RS, page as 32,448 words, single codeword, 175 parity words.
- Then 4-parity/8-parity chunk variants matching 350 total.
Report the FIRST byte-exact reproduction immediately.

---
## LEAD from ecc-intel (2026-08-02): the ECC module is `Foundation\Utility\CRCIO.cpp` and it corrects BITS

Autodesk's own KB article 000242930 ("Software problem" when opening a
Revit file, https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Message-Software-problem-when-opening-a-Revit-file.html)
quotes the Revit journal line VERBATIM:

    DBG_INFO: Error-correcting codes rescued 1 bit(s)!: line 898 of
    E:\Ship23.0.1\2023_px64\Source\Foundation\Utility\CRCIO.cpp.

Implications:
1. The ECC lives in `Utility.dll`, source module `Foundation\Utility\CRCIO.cpp`
   (i.e. CRC-based stream I/O). Search that DLL / symbol names for
   `CRCIO`, `CRC`, `IO`.
2. The repair count is reported in BITS ("rescued N bit(s)"), so the code
   is very likely a BINARY (bit-oriented) code: BCH / Hamming family, or a
   CRC-syndrome-based bit corrector -- NOT necessarily byte-symbol RS.
   Reweight the sweep: try binary BCH over GF(2^m) with the 350-byte
   (2800-bit) parity region, and Hamming/SECDED lane structures, in
   addition to RS. Also try CRC-32/CRC-16 syndrome-table single-bit
   correction per chunk.
3. ZDI (Zuckerbraun 2025) confirms the auto-repair semantics but names NO
   algorithm; he shelled out to real Revit DLLs (Utility.dll) via a C++
   wrapper to compute ECC. He observed the ECC ALTERS decompressed output
   ("The two versions were a close match, yet not exact") -- consistent
   with silent bit-repair of fuzzed streams.

---
## LEAD #2 from ecc-intel (2026-08-03): WE HAVE THE ACTUAL Utility.dll -- IT IS AN AUTODESK-CUSTOM ADLER32/CRC BIT-CORRECTION SCHEME, NOT RS/BCH

Source binary now on disk (Revit 2023.1.9 x64, from Autodesk's public
RevitLT_2023_1_9.exe update -> RLTSP14.msp -> PCW_CAB_FAM1 ->
Revit_NT_Utility.dll):
  /Users/ck/dev/things/rev-revit/docs/inbox/ecc-intel-Utility-2023_1_9.dll
  (see docs/inbox/ecc-intel.md for the extraction recipe and analysis).

Facts from the DLL's strings + exports (all in module
`Foundation\Utility\CRCIO.cpp/.h`, authored 2004 by Thomas Yan "TKY"):
- Classes: `CRCIO` (owned by exported `CRCFile : CFile`),
  `CRCParameters` (has field `checksumSize`), `Adler32` (statics
  `accumulate(ulong,ulong,void const*)`, `checkAndRepair(ulong*,ulong,
  ulong,Adler32::Correction*)`, `findCorrection(ulong,ulong,ulong,
  Adler32::Correction*)`, `ErrorRecoveryLimit`), `SECComp` (RTTI only,
  "SEC" = single-error-correction), enum `CRC32Confidence`.
- Diagnostics: "Ambiguous error correction, distance = %d",
  "Impossible exhaustion of error checksums!",
  "[TKY] preChecksumBits: sizes.first = %d < %d = parameters.checksumSize",
  "Error-correcting codes rescued %d bit(s)!",
  "Error-correcting codes detect bad bits, but only in a checksum.",
  "Ambiguous case for one-bit correction with adler32",
  "Message is too long for one-bit correction with adler32",
  "Adler correction finds the bad bit corrected already??",
  "CRCFile::startChecking: insufficient buffer size, ignoring".
=> The 353-byte page trailer is (very likely) a bank of ADLER-32-family
   checksums (mod-65521 A/B sums) over sub-blocks of the page, arranged so
   single-bit errors can be LOCATED and flipped ("rescued N bit(s)"),
   plus a preamble/flag bytes. It is Autodesk-CUSTOM code (2004), NOT a
   named FEC library, NOT Reed-Solomon, NOT BCH/Golay/Hamming tables.
   STOP the RS/BCH parameter sweeps; sweep ADLER-32 / Fletcher-style
   (mod 65521 and mod 65535, also mod 251/255 8-bit lanes) checksums over
   chunkings of the 64,896-byte page: e.g. does trailer[2:352] contain
   87 x 4-byte adler32 values, or 175 x 16-bit truncated sums, over
   contiguous chunks or interleaved/strided lanes? Also try zlib.adler32
   with non-1 seed and the crc32 of the page anywhere in the trailer.
   ecc-intel is reversing the actual encoder from the DLL now.

---
## ORCHESTRATOR ADDENDUM (from the Utility.dll itself, 2026-08-02)

Facts read directly from docs/inbox/ecc-intel-Utility-2023_1_9.dll:
- Exported: `unsigned long Adler32::accumulate(unsigned long running, void const* buf, unsigned long len)`,
  `void Adler32::findCorrection(unsigned long expected, unsigned long actual, unsigned long len, Correction*)`,
  `void Adler32::checkAndRepair(unsigned long*, void*, unsigned long, Correction*)`,
  `CRCIO& CRCFile::IO()`, `CRCFile::setPreambleSize(int)`, `startCheckingCRC`, `resetCRC`.
- **`Adler32::ErrorRecoveryLimit` (exported data) = 65520 (0xFFF0)** => a single Adler-32
  block can single-bit-repair up to 65,520 bytes; so a whole 64,896-B page fits ONE block.
  The ~350 extra trailer bytes are therefore MANY checksums (multi-error robustness:
  1 correctable bit per block), not required by page size.
- Debug string: `[TKY] preChecksumBits: sizes.first = %d < %d = parameters.checksumSize`
  => checksums are **BIT-PACKED** with a configurable `CRCParameters::checksumSize`
  (in BITS). All prior byte-aligned searches were therefore invalid tests.
- NEGATIVE (byte-aligned only): no zlib.adler32 of page prefixes 1..4096; no equal-block
  splits (80..92 blocks) x mod{65521,65535,none} x init{1,0} x LE/BE/swapped packings.

NEXT TESTS: standard adler32 (mod 65521, init 1, running/`accumulate` semantics) over N
contiguous near-equal blocks, each checksum truncated/packed to `checksumSize` = k BITS,
concatenated MSB-first or LSB-first, for (n,k) with n*k ~= 2800 bits: (88,32),(87,32),
(90,31),(93,30),(100,28),(117,24) etc., at trailer bit-offsets 0..24 (the leading 0x00 byte /
nibble field may be a header). Reverse `Adler32::accumulate` (RVA 0x144850) and CRCIO's write
path in the DLL for the exact geometry.

---
## *** SOLVED *** (ecc-intel, 2026-08-03): FULL-PAGE TRAILER REPRODUCED BYTE-EXACTLY

Reverse-engineered from Utility.dll `Foundation\Utility\CRCIO.cpp`. It is NOT
RS/BCH/Adler: it is 255 BIT-INTERLEAVED CRC-11 codewords (shortened Hamming
SEC codes) over the whole 65,249-byte page.

Encoder for a full 64,896-byte page (params m=11, reflected poly 0x500 =
x^11+x^2+1, period 2047, align 2, N=9):
  - buf = 65,249 zero bytes; buf[:64896] = data
  - preChecksumBits = (2047-11)*255 = 519,180
  - 9-bit pad-byte-count field (value 0 for a full page) at bit 519,171,
    bits LSB-first (bit index within byte: LSB = bit 0)
  - lane i (i = bitpos mod 255) CRC over bits 0..519,179 of buf:
        c = crc[i]; fb = (c ^ bit) & 1; c >>= 1; if fb: c ^= 0x500
    (init 0, no xorout, LSB-first / reflected register)
  - parity bit j (0..10, LSB first) of crc[i] is placed at bit position
    519,180 + i + j*255  =>  bytes 64,896..65,248 = the 353-byte trailer.
VERIFIED byte-exact on rstbasic Formats/Latest page 0 (00f0fc4e401b0db7...).
Reference implementation + corpus-wide validation: docs/inbox/ecc-intel-crcio.py
(see docs/inbox/ecc-intel.md). Final partial pages use the same algorithm
with size-class parameter selection (m in {2..11}) -- being validated now.

---
## SOLVED (ecc-intel, 2026-08-03) — full spec in docs/inbox/ecc-intel.md

The trailer is a bank of N-way BIT-INTERLEAVED reflected CRCs (cyclic
Hamming SEC codes). Full page: 255 codewords x (2036 data bits + 11-bit CRC,
poly x^11+x^2+1 reflected 0x500), data bit p -> codeword p mod 255, CRC bit
j of codeword c at bit 519180 + c + 255j, LSB-first bytes, 9-bit slack-count
index field at data-area end, 7 pad bits => 65,249-byte page. Verified
byte-exact on 3,502/3,502 full pages, 55/55 partial pages, 45/45 whole
framed streams. Encoder: src/rvt/ecc.py (page_trailer / frame_stream).
Non-framed streams: BasicFileInfo, ProjectInformation, RevitPreview4.0,
TransmissionData. STOP all RS/BCH/Adler sweeps.

FINAL VALIDATION (ecc-intel): 3,502 full pages + every framed final block
across all six samples reproduced BYTE-EXACT (0 mismatches). Reader-side
`unframe_stream()` (uses the pad-count field) also round-trips. Streams
`BasicFileInfo`, `ProjectInformation`, `RevitPreview4.0`, `TransmissionData`
are NOT framed (raw) -- do not add trailers to them. Full spec + evidence:
docs/inbox/ecc-intel.md ; code: docs/inbox/ecc-intel-crcio.py.

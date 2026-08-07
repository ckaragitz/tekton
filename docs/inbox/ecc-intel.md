# ecc-intel — DECISION BRIEF: the Revit page trailer is Autodesk's `CRCIO` code, and it is CRACKED (byte-exact)

Agent: ecc-intel (intelligence angle). Date: 2026-08-03.
Status: **SOLVED**. The 353-byte page trailer (and every final-partial-page
block) is reproduced BYTE-EXACTLY by
`docs/inbox/ecc-intel-crcio.py` on ALL 3,502 full pages and every final
block of every CRCIO-framed stream in all six sample files (zero mismatches).
The algorithm was recovered by disassembling the actual Autodesk binary, so
no parameter sweep is needed. `solved = true`.

---

## 1. What it actually is (one paragraph)

The trailer is NOT Reed–Solomon, BCH, Golay, Hamming tables, or any FEC
library. It is a bespoke Autodesk scheme implemented in
`Foundation\Utility\CRCIO.cpp` (Revit's `Utility.dll`, authored 2004 by
Thomas K. Yan, "TKY"). A raw stream is written through `CRCFile : CFile`,
whose `CRCIO` object cuts the logical stream into blocks. Each block of up
to 64,896 payload bytes becomes a 65,249-byte encoded block that is treated
as **255 bit-interleaved codewords**: lane `i` = every bit position `p` with
`p mod 255 == i`. Each lane carries `2036` data bits and an **11-bit
reflected CRC** (generator `x^11 + x^2 + 1`, reflected constant `0x500`,
register init 0, no final xor). Because the codeword length `2047 =
2^11 - 1` equals the period of the primitive polynomial, each lane is a
(shortened) Hamming single-error-correcting code — hence Autodesk's journal
message "Error-correcting codes rescued %d bit(s)!" and ZDI's observation
that Revit silently repairs light fuzz damage. Smaller final blocks use a
smaller size class (m ∈ {11,9,7,6,5,4,3,2}) chosen by the block's byte
count, with the number of lanes recomputed from the data length.

## 2. Exact algorithm (verified byte-exact)

Reference implementation: `docs/inbox/ecc-intel-crcio.py`
(`encode_block`, `page_trailer`, `frame_stream`, `select_params`).

For a data block `data` (n = len(data) bytes) and its size class
`(m, poly, period, align)`:

```
N        = size_field_bits(period, align)          # 9 for the m=11 class
bits     = 8*n
D        = period - m                              # data bits per lane
if bits + N <= 65*D:                                # small block
    second = 65                                     # lanes
    first  = (bits + N + 64)//65 + m                # bits per lane
else:                                               # normal case
    cw     = ceil((bits + N)/D)
    if (cw - 65) % align: cw += align - ((cw-65) % align)
    second = cw ; first = period
total_bits = first*second ; total_bytes = ceil(total_bits/8)
pre        = (first - m)*second                     # "preChecksumBits"
buf        = data zero-padded to total_bytes
pad_bytes  = (pre - bits - N) >> 3                  # zero bytes after data
write pad_bytes as an N-bit LSB-first field at bit position (pre - N)
for p in 0..pre-1:   lane = p mod second ; bit = (buf[p>>3] >> (p&7)) & 1
    c = crc[lane]; fb = (c ^ bit) & 1; c >>= 1; if fb: c ^= poly; crc[lane]=c
for lane i, parity bit j (0..m-1, LSB of the register first):
    if (crc[i]>>j)&1: set bit at position pre + i + j*second
```
Bit numbering is LSB-first inside each byte (bit `p` = byte `p>>3`, mask
`1 << (p&7)`).

Full page (n = 64,896, class m=11, poly 0x500, period 2047, align 2):
N=9, second=255, first=2047, total 521,985 bits = 65,249 bytes
(= PAGE_STRIDE), pre = 519,180, pad_bytes = 0, size field at bit 519,171,
parity bit j of lane i at 519,180 + i + 255*j → bytes 64,896..65,248 =
the observed 353-byte trailer. This EXPLAINS every prior statistical
observation: byte[0] = 0x00 (3 pad bits + low bits of the zero size
field), byte[1] = `nibble<<4` (size field high 4 bits then parity bits of
lanes 0–3 at j=0), last byte ∈ {0,1} (only bit 521,984 = lane 254, j=10
lands in it), middle bytes ≈ uniform (2,805 parity bits of random data).

Size-class selection (mirrors DLL fn `0x87220`), by data byte-count n:
| n range | (m, poly, period, align) |
|---|---|
| n > 5081 | (11, 0x500, 2047, 2) |
| 1275..5081 | (9, 0x110, 511, 2) |
| 549..1274 | (7, 0x60, 127, 2) |
| 257..548 | (6, 0x30, 63, 2) |
| 106..256 | (5, 0x14, 31, 2) |
| 41..105 | (4, 0xC, 15, 2) |
| 8..40 | (3, 5, 7, 2) |
| ≤ 7 | (2, 3, 3, 4) |
(thresholds recomputed from the DLL's own formula in `_thresholds()`;
the polys are reflected primitive polynomials — `0x500` ↔ x^11+x^2+1,
`0x110` ↔ x^9+x^4+1, `0x60` ↔ x^7+x+1, `0x30` ↔ x^6+x+1, `0x14` ↔ x^5+x^2+1,
`0xC` ↔ x^4+x+1, `5` ↔ x^3+x+1, `3` ↔ x^2+x+1.)

Writer recipe (`frame_stream`): split the logical stream into 64,896-byte
chunks, `encode_block` each with the m=11 class, and encode the final short
chunk with `select_params(len(chunk))`. NOTE: the final block's overhead is
NOT ≤353 bytes — it is `pad_bytes` zeros (up to 508) + parity, e.g.
rstbasic `Global/Latest` final block: 63,974 data bytes → 64,737 encoded
(763 bytes overhead).

## 3. Validation evidence (real corpus, byte-exact)

Run: `.venv/bin/python docs/inbox/ecc-intel-validate.py`
```
[  62.3s] rstbasicsampleproject.rvt:  full_ok=99   full_bad=0
[ 142.9s] racbasicsampleproject.rvt:  full_ok=397  full_bad=0
[ 206.3s] rmebasicsampleproject.rvt:  full_ok=894  full_bad=0
[ 266.8s] racadvancedsampleproject.rvt full_ok=1152 full_bad=0
[ 314.5s] rstadvancedsampleproject.rvt full_ok=1379 full_bad=0
full pages: ok=1379 bad=0 (cumulative), final blocks reproduced: 38 (+7
via the wider search below); framed-stream failures: NONE.
```
The three "failures" in that run were only the tail-length search window
being too narrow; a wide search reproduces them too:
`Formats/Latest` final block L=51,751 (704 B overhead) ✔, rstbasic
`Global/Latest` L=63,974 ✔, racadvanced `Global/Latest` L=53,201 ✔ —
all `match True`. dach (139 MB): `full_ok=2123 full_bad=0`, all framed
final blocks reproduced (its Formats/Latest tail is the same L=51,751
block, identical across all files). GRAND TOTAL: 3,502 full pages +
all final blocks byte-exact, 0 mismatches. First byte-exact hit (rstbasic
Formats/Latest page 0):
`(11, 1280, 2047, 2) len 65249 match 00f0fc4e401b0db7...` (identical to
the on-disk trailer).

**CORRECTION for KNOWLEDGE.md**: four stream types are NOT CRCIO-framed at
all (they are raw, so external tools can read them): `BasicFileInfo`,
`ProjectInformation`, `RevitPreview4.0`, `TransmissionData` (and presumably
`PartAtom` in families). Every other stream (incl. `Contents`,
`ElemTable`, `Formats/Latest`, `Global/*`, `Partitions/*`) is framed. The
writer must NOT frame those four.

Also explains the V9 acceptance result: flipping trailer byte 0 (bits
519,168–519,175) puts exactly ONE bit error into each of 8 different
lanes; each 11-bit lane CRC is a Hamming SEC code, so all 8 bits were
corrected ("rescued 8 bit(s)") and the file translated.

## 4. Evidence chain / how it was found (quotes + URLs)

1. **ZDI 2025** (Simon Zuckerbraun,
   https://www.thezdi.com/blog/2025/10/6/crafting-a-full-exploit-rce-from-a-crash-in-autodesk-revit-rfa-file-parsing)
   — quoted verbatim from the fetched page: "After the gzipped data,
   though, I found that there was some sort of padding section consisting
   of zeroes, and finally another section of high-entropy data." ...
   "After puzzling over this for a while, I discovered that the final
   section consisted of error correcting codes. Public symbols and
   diagnostic log text strings found in Utility.dll assisted me in reaching
   this understanding." ... "If the damage is minor, the data may be
   successfully recovered. In that case, the changes made by the fuzzer
   will be reverted entirely." ... "I accomplished this by copying a
   minimal subset of low-level DLLs and configuration files from a Revit
   install and writing a wrapper in C++ to call the appropriate methods.
   This took care of the gzip/gunzip as well as the error correction tasks
   in a single step." → he never named the algorithm; the trail led to
   the DLL.
2. **Autodesk KB 000242930** ("Software problem" when opening a Revit file,
   https://www.autodesk.com/support/technical/article/caas/sfdcarticles/sfdcarticles/Message-Software-problem-when-opening-a-Revit-file.html)
   quotes the journal line: `DBG_INFO: Error-correcting codes rescued 1
   bit(s)!: line 898 of E:\Ship23.0.1\2023_px64\Source\Foundation\Utility\CRCIO.cpp.`
   → named the module `CRCIO.cpp` and revealed the code corrects BITS.
3. **The binary itself.** Autodesk's public update
   `https://up.autodesk.com/prd/2023/RVTLT/EB2014B8-FDFC-3C7C-ACA7-E69780FB87D2/RevitLT_2023_1_9.exe`
   (829,129,584 B) → 7z-extract → `x64/RLTSP14.msp` → `PCW_CAB_FAM1` →
   `Revit_NT_Utility.dll.D53D7C22_D946_4B75_9B91_DA5476E29581` = Revit
   2023.1.9 `Utility.dll` (sha256
   d9fd5a2ecbc391fbe2d450273fff905591360667624ebe760dc6554ddc0a2f82),
   copied to `docs/inbox/ecc-intel-Utility-2023_1_9.dll`. Its strings:
   `Error-correcting codes rescued %d bit(s)!`, `Error-correcting codes
   detect bad bits, but only in a checksum.`, `Ambiguous error correction,
   distance = %d`, `Impossible exhaustion of error checksums!`,
   `[TKY] preChecksumBits: sizes.first = %d < %d = parameters.checksumSize`,
   `CRCFile::startChecking: insufficient buffer size, ignoring`, RTTI
   `.?AVSECComp@@`, `namespace_getclassCRCParameters`, exports `CRCFile::*`,
   `?IO@CRCFile@@IEBAAEAVCRCIO@@XZ`. Disassembly (capstone; scripts in the
   session scratchpad) of: `CRCIO::write` (RVA 0x85150), the page flush
   (0x85a20), the CRC-lane accumulator (0x869e0), the parity placer
   (0x86910), the geometry function (0x872e0), the parameter constructor
   (0x86cb0), the eight static parameter objects (initializers at RVA
   0x5bc0–0x5f00, e.g. `(0x20, 0xEDB88320, 0xbbd, 2)` = a CRC-32 class and
   `(0xB, 0x500, 0x7FF, 2)` = the page class), and the selection thresholds
   (0x86e90). The Python encoder is a direct transcription and matched real
   trailers on the first attempt.

## 5. What is NOT the page ECC (do not chase)

- `Adler32::checkAndRepair / findCorrection / accumulate` (exported;
  standard zlib Adler-32 mod 65521 with a single-bit-flip solver, strings
  "Ambiguous case for one-bit correction with adler32", "Hooray, checksums
  fixed the temporary file") — used for CompactMemory temporary files, NOT
  for stream pages.
- `CompressFile` / `CRC32Confidence` / `computeChecksum@StorageUtil` —
  stream-level bookkeeping, not the per-page code.
- The extra parameter objects with alternate polys (0x108, 0x90, 0x48,
  0x44, 0x41, 0x21, 0x12, 9, 6) exist in the DLL but are not in the
  selection table used by CRCIO.
- All published FEC libraries and Autodesk patents: no attribution/patent
  exists because the code is home-grown (2004).

## 6. Open items / next steps for the orchestrator

1. Promote `docs/inbox/ecc-intel-crcio.py` to `src/rvt/ecc.py` (my write
   scope is docs/inbox only), add a corpus test (`page_trailer(page) ==
   trailer` for all full pages; `frame_stream(logical) == raw` for framed
   streams). Fix `container.depage()`: the final block is not "payload +
   short trailer" — the exact logical length is recoverable from the
   pad-count field: `logical_len = (pre - N)/8 - pad_bytes` (integer
   division; equivalently strip `pad_bytes` + size field + parity).
2. Update KNOWLEDGE.md: (a) the trailer is CRCIO interleaved CRC-11 lanes
   (spec §2); (b) BasicFileInfo / ProjectInformation / RevitPreview4.0 /
   TransmissionData are UNFRAMED.
3. Write side is complete; the reader/repair side (0x84330 verify+repair,
   0x85400 SEC correction with the "Ambiguous error correction" search) is
   only needed if we want to REPAIR damaged files ourselves. Untested edge:
   the (2,3,3,4) class (blocks ≤ 7 bytes) — no such block in the corpus.
4. The final Viewer proof: recompress a stream (level-3 sync-flush gzip)
   and re-frame it with `frame_stream()` — the trailers will now be valid.

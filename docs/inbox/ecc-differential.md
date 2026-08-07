# ecc-differential — linearity, near-duplicate inventory, and support structure of the page-trailer ECC

Agent: ecc-differential (2026-08-02). Script: `experiments/ecc/differential.py`
(run with the project venv; `--fast` for a 26 s subset run, full run ~70 s).

## TL;DR

* The 353-byte page trailer is a **GF(2)-linear, keyless, systematic
  cyclic code** — the trailer field is (with fixed zero padding) the parity
  `P(x) = M(x)·x^2817 mod g(x)` of the payload polynomial `M(x)` (LSB-first
  bits, first bit = highest degree), with **g(x) = h11(x^255) = x^2805 +
  x^510 + 1**, h11(y) = y^11 + y^2 + 1.  This is the code recovered by the
  ecc-writer-gate agent (`experiments/ecc/ecc_codec.py`); this document
  supplies the differential/linearity classification and verifies that map
  against **every** unique full page in the corpus.
* **Verification (byte-exact, real trailers):** 3,492 / 3,492 unique
  64,896-byte pages across all six sample files and all streams reproduce
  their real 353-byte trailers exactly (`differential.py`, Part B). The
  brief's rig assertion passes (rstbasic `Formats/Latest` page 0, first 8
  trailer bytes real `00f0fc4e401b0db7` == computed `00f0fc4e401b0db7`).
* **Linearity confirmed on real data:** `F(0-page) = 0-trailer` (no affine
  constant) and superposition `F(A xor B) == T_A xor T_B` holds for 200/200
  random pairs of *real* pages with their *real* Autodesk trailers.
* **Locality classification:** support is **local in the bit-interleaved
  domain** (page bit i touches only the 11 parity bits of lane
  `L(i) = ((8·64896 − 1 − i) + 2817) mod 255`) but **globally diffused in the
  byte-offset domain** (one page byte spans 8 lanes → up to 88 trailer bits
  spread over ~320 of the 353 trailer bytes). This is why every earlier
  contiguous "372-byte chunk → 2 parity bytes" CRC search failed: the code
  is NOT chunked by page offset; it is 255-way *bit* interleaved.
* **Near-duplicate inventory: none exist.** No two distinct full pages in
  the corpus share even one aligned 1 KiB block; the closest pair differs in
  64,436 of 64,896 bytes. The only exact duplicates are `Formats/Latest`
  pages 0 and 1 (identical in all six files, identical trailers → keyless
  code confirmed). So the classic natural-pair differential attack has no
  material; the differential was executed through the (proven-correct)
  linear map instead.

## Corpus / near-duplicate inventory (Part A)

| metric | value |
|---|---|
| full 64,896-byte pages with trailers (6 files, all streams) | 3,502 |
| unique payloads | 3,492 |
| identical payloads with DIFFERENT trailers | **0** (keyless) |
| payloads occurring >1× | 2 (`Formats/Latest` p0, p1 × 6 files) |
| pairs sharing an aligned 1,024-byte block | **0** |
| 64-byte shingle candidate pairs (misaligned shared content) | ~495–529 |
| minimum aligned byte-diff among all candidates | 64,436 / 64,896 (rme Partitions/14 p94 vs p95) |

Conclusion: pages are gzip payload at arbitrary offsets; edits shift bytes,
so no in-place near-duplicates arise. A^B^C^D=0 relations are impossible on
this data. Evidence source: `differential.py` Part A output.

## Linearity evidence (Part B)

Model under test `F` = `ecc_codec.full_page_trailer` (I=255 interleave,
Hamming order m=11, pad_low=12 zero bits, t_pad=7 zero bits, 2,805 parity
bits → 353-byte field).

| test | result |
|---|---|
| `F(page) == real trailer` for every unique full page | **3,492 / 3,492** byte-exact |
| `F(bytes(64896)) == bytes(353)` | True → linear (not affine) |
| `F(A ^ B) == T_A ^ T_B`, A,B real pages, T real trailers | 200 / 200 |

Because F reproduces all real trailers and is linear by construction, the
true trailer function is GF(2)-linear on the entire observed corpus: T = M·G
for a fixed 519,168 × 2,824 GF(2) generator (parity) matrix G whose columns
are the single-bit differentials below.

## Locality / generator-column evidence (Part C) — the exact page-bit → parity map

Definitions (bit index = LSB-first: bit t of byte b is index 8b+t; trailer
field bit j likewise inside the 353-byte trailer):

* payload bit i has parity-poly degree `D(i) = (519167 − i) + 2817`;
* lane `L(i) = D(i) mod 255`; lane power `s(i) = (D(i) − L(i)) / 255`;
* parity coefficient `e` (0 ≤ e < 2805) lives at trailer-field bit
  `j(e) = 2823 − 7 − e = 2816 − e`; coefficient e belongs to lane `e mod 255`;
* flipping payload bit i XORs the trailer with the pattern
  `{ j(L(i) + 255·t) : t ∈ [0,10], bit t of (y^s(i) mod h11(y)) = 1 }`,
  h11(y) = y^11 + y^2 + 1 — i.e. one column of the 255-interleaved Hamming
  code; support weight 1..11, always inside lane L(i) only.

Verified single-bit differentials (delta = F(e_i), all inside their lane and
equal to the predicted `y^s mod h11` pattern):

| page byte:bit | i | lane | delta-trailer field bits (LSB-first) |
|---|---:|---:|---|
| 0:0 | 0 | 254 | 12, 2307 |
| 0:1 | 1 | 253 | 13, 2308 |
| 0:7 | 7 | 247 | 19, 2314 |
| 1:0 | 8 | 246 | 20, 2315 |
| 12:4 | 100 | 154 | 112, 2407 |
| 254:7 | 2039 | 0 | 521, 1031, 1541, 2051, 2816 |
| 255:0 | 2040 | 254 | 12, 522, 1032, 1542, 2052, 2307 |
| 8191:7 | 65535 | 254 | 267, 777, 1287, 2307 |
| 32447:7 | 259583 | 6 | 2555, 2810 |
| 32448:0 | 259584 | 5 | 2556, 2811 |
| 64895:0 | 519160 | 19 | 2287, 2797 |
| 64895:6 | 519166 | 13 | 2293, 2803 |
| 64895:7 | 519167 | 12 | 2294, 2804 |

Trailer field bits 0–11 (byte 0 and low nibble of byte 1) and bits
2817–2823 (byte 352 above bit 0) are structurally zero — matching the
observed `00`, `n<<4`, and `00/01` byte statistics; bits 12–2816 are the
2,805 parity coefficients (11 per lane × 255 lanes).

Byte-level consequence: page byte b covers 8 consecutive degrees → 8
distinct lanes → up to 8×11 = 88 trailer bits at field positions spaced 255
bits apart → touches ~21–30 distinct trailer bytes spanning almost the whole
353-byte trailer (example: page byte 12345 → trailer bytes 10 … 330).
Classification: **local support only in the interleaved-bit basis; global
diffusion in the offset basis**. Family: cyclic Hamming (a BCH sub-case),
not Reed–Solomon, not a hash; single-bit-error-correcting per lane, i.e.
corrects any burst of ≤ 255 bits per page — consistent with the V9 viewer
result (one flipped trailer byte was auto-repaired).

## Unknowns / not covered here

* Final partial-page (short) trailers were not re-derived by this agent;
  `ecc_codec.py` proposes a parameter-selection rule — see that agent's
  report for its verification status.
* The linearity/superposition tests are exercised through the recovered
  map (necessarily, since no natural page differentials exist); their
  validity rests on the 3,492/3,492 byte-exact reproduction.

## Files

* `experiments/ecc/differential.py` — inventory + linearity + column probes.
* This note. No other files written; `ecc_codec.py` is another agent's file
  and was only imported, not edited.

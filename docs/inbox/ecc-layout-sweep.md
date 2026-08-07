# ECC layout sweep — RESULT: page ECC SOLVED (full pages byte-exact) + final-block geometry cracked

Agent: `ecc-layout-sweep`. Code: `experiments/ecc/layout_sweep.py` (winning
encoders + corpus verifiers + the negative sweep grid); grid log
`experiments/ecc/layout_sweep_log.json`.

## Headline (byte-exact, corpus-wide) — the writer's blocker is removed

```
[POSITIVE] 255 bit-lane CRC-11 model on ground truth: byte-exact = True   (9.1 ms)
[verify_corpus] full pages checked: 3502, byte-exact: 3502, mismatch: 0   (2.8s, 29 streams)
DIRECT-FROM-OLE verification: streams with full pages=29, full pages=3502, byte-exact=3502, mismatch=0
[verify_final_blocks] ECC-framed final blocks: 55; parameter rule located a divisible codeword: 55/55;
                      zero-header writer byte-exact: 14/55; unframed streams: 23
ASSERT PASS: lane_crc11_trailer(page) == trailer   (Formats/Latest full page 0)      <- ecc-brief test rig
ASSERT PASS: final_trailer(final[:52173]) == final[52173:]   (Formats/Latest final block, 282-byte field)
ASSERT PASS: final_trailer == real 90-byte field   (rstadvanced Global/History final block)
```
(3,502 = the exact population characterised in ecc-brief §6: all six files,
every raw OLE stream with ≥1 full page, read both from `extracted/*.bin` and
directly from the compound files. 55 = every final partial block of every
ECC-framed raw stream.)

## The winning layout, in the sweep's own "lane" language

The task's hypothesis space was right in spirit — the code IS an
interleave of independent per-lane sub-results — but at **bit** granularity,
**255 lanes**, and the per-lane function is a **CRC-11** (a cyclic Hamming
code), not a byte checksum. Full 64,896-byte page:

| item | value / rule | evidence |
|---|---|---|
| bit convention | bytes read LSB-first inside each byte (deflate order); first bit = highest-degree coefficient | byte-exact reproduction |
| message | payload bits + `pad_low = 12` zero bits = 519,180 bits = 255 × 2036 | 8·64896+12 = 255·(2047−11) |
| lanes | interleave depth **I = 255** at **bit** stride 255: message bit `i` → lane `r = (254 − i) mod 255` (= exponent residue class mod 255); each lane = 2036 message bits, highest degree first | reshape(2036,255) column model reproduces trailers |
| per-lane code | Hamming (2047,2036): 11 parity bits = **CRC-11**, `h(y)=y^11+y^2+1` (0x805), init 0, no reflect/xorout | classic min-weight primitive of degree 11 |
| code region | 255 × 11 = 2805 parity bits; lane `r` degree `q` parity bit sits at codeword exponent `E = 255·q + r`, i.e. trailer **field bit `j = 2816 − E`** | byte-exact |
| trailer field | 2824 bits = 353 bytes = 12 leading zero bits ‖ 2805 code bits ‖ 7 trailing zero bits | explains byte0=0x00, byte1 low nibble 0, last byte ∈ {0,1} (ecc-brief §6): they are pad + parity, not metadata |
| whole-codeword view | payload‖field ≡ 0 mod g(x)=h(x^255)=x^2805+x^510+1 (deg 2805). Each exponent-residue class mod 255 is an independent Hamming lane ⇒ corrects 1 bit per lane per page (any burst ≤ 255 bits) — consistent with V9 (single flipped byte PASSED = corrected) | ecc-LEAD.md |

Why every byte-lane / chunk checksum family fails (and the sweep proves it):
the 2805 code bits are **transposed** — 11 consecutive groups of 255 bits
(group `q` = parity bit `q` of *every* lane) — and the lanes are bit-strided,
so no byte-aligned 2/4-byte sub-result of any byte-granular lane can line up.

## Final (partial) block model — geometry rule cracked (55/55 blocks)

Every ECC-framed stream ends with ONE final codeword `[payload P bytes][field F
bytes]`, divisible as a whole by `g(x) = h_m(x^I)`. Solved for every final
block in the corpus with a poly-agnostic **lane-GCD attack** (deal the block's
bits into I exponent-residue lanes, GCD the lane polynomials; the GCD is
h_m(y) exactly when I is right — recovers I, m AND h with no assumptions).
Parameters, derived from the payload alone (`n = 8·P` bits):

```
degree table (writer supports ONLY these):  h_4 = y^4+y+1 (0x13), h_5 = y^5+y^2+1 (0x25),
                                            h_7 = y^7+y+1 (0x83), h_9 = y^9+y^4+1 (0x211),
                                            h_11 = y^11+y^2+1 (0x805)
for m in (4,5,7,9,11):  K_m = 2^m-1-m ;  I_m = max(65, round(n / K_m)) ; require I_m <= 255
choose (I,m) minimising total parity I*m.          # 55/55 final blocks reproduced
F = ceil(I*m / 8) bytes ;  base = 8F - I*m (0..7) leading field bits.
field = [base header bits][I*m parity bits], t_pad = 0.
```

- The `base` (≤7) leading header bits are **included in the CRC message**
  (payload‖header); their values look random across the corpus (11/17 of the
  base=1 blocks have 0, the rest 1; no relation to payload) — i.e. junk /
  uninitialised buffer bits. Zeroing them yields a valid codeword under the
  reader's expected geometry; then parity = the plain systematic remainder
  `M(x)·x^(8F) mod g` written in the field's last I·m bits. 14/55 corpus
  final blocks have zero header bits and are reproduced BYTE-EXACT by
  `final_trailer()`; the other 41 differ only in those ≤7 junk bits
  (structurally validated: every block passes the divisibility/syndrome check).
- Full pages are the fixed special case F=353 (base=19 = 12 leading + 7
  trailing zero bits; the leading 12 are zero on all 3,502 pages).
- Worked instance (Formats/Latest, identical in all six files): final block
  R=52,455: P=52,173, F=282, I=205, m=11, base=1 (header bit 0) →
  `final_trailer(payload)` = the real 282-byte field, byte-exact.
- Streams **without** ECC framing (no trailer, not codewords): `BasicFileInfo`,
  `TransmissionData`, `ProjectInformation`, `RevitPreview4.0` (the non-native
  metadata/preview streams). ECC-framed: `Formats/*`, `Contents`,
  `Global/{Latest,ElemTable,ContentDocuments,History,DocumentIncrementTable,PartitionTable}`,
  `Partitions/*` — the writer must frame exactly this set.
- `[hypothesis]` The reader is syndrome/correction based (V9 PASS), so a
  zero-header final field should be accepted; needs one viewer upload to
  confirm (recompute all trailers with these two functions).

## Systematic negative sweep (the assigned byte-granular hypothesis space)

`negative_sweep()` ran **11,468 layout×function×target variants** on the
ground-truth page, comparing 16-bit lane sub-results against the trailer
carved as words at four alignments × both endiannesses, ordered and reversed.
**Zero positional leads**; only isolated single-position chance coincidences
(~175/65,536 per lane list). Full grid in `layout_sweep_log.json`:

| family | parameters swept | per-lane functions | result |
|---|---|---|---|
| A. contiguous chunks | c ∈ {372,371,373,370,374,368,376,384,366,365,364,360,256,512,350} + 175 fractional near-equal chunks | sum8-lo/hi, sum16(le), sum8×2, xor8, xor16(le), sum16w, Fletcher-16, Adler-16(mod251), CRC-32 lo/hi/xor-fold; **CRC-16 bank** (c∈{372,371,373,350,frac175}): polys 0x8005/0x1021/0x3D65/0x0589/0xA097/0x8BB7/0xC867/0x1DCF × init {0,0xFFFF,0x1D0F,0x554D} × refl {F,T} × xorout {0,0xFFFF} | all | 5 scattered single hits, no lead |
| B. byte-interleaved lanes | stride ∈ {175,350,87,88,174,176,255,353,351}; CRC-16 bank on 175/350/255 | same bank | 4 scattered single hits, no lead |
| C. word-interleaved lanes | 16-bit words stride {175,87,88}; 32-bit words stride {87,88,175} | same bank | ≤1 scattered hit, no lead |
| D. metadata joined | trailer bytes [0],[1],[352] prepended/appended, [0:2] prepended; chunks 372/371 | same bank | ≤1 scattered hit, no lead |
| E. column parity | page reshaped R×C, C ∈ {175,350,353,351,349,348,176,174,87,88}; column XOR / column byte-sum vs code bytes at 3 alignments | col-xor, col-sum8 | none above chance |
| CRC-16 positional hits | over all crc16 param combos | — | 47 isolated single positions (chance) |

## Writer recipe (drop-in for `src/rvt/ecc.py`)

`experiments/ecc/layout_sweep.py` exports:
- `lane_crc11_trailer(page: bytes) -> bytes` — 353-byte trailer of a full
  64,896-byte page (numpy, ~2 ms/page batched); byte-exact on 3,502/3,502.
- `select_params(payload_len) -> (I, m, F)` and `final_trailer(payload) -> bytes`
  — final-block field with zero header bits (valid codeword; byte-exact
  whenever the original header bits were zero).
- `verify_corpus()`, `verify_final_blocks()`, `negative_sweep()`.

## Files written (this agent)

- `/Users/ck/dev/things/rev-revit/experiments/ecc/layout_sweep.py`
- `/Users/ck/dev/things/rev-revit/experiments/ecc/layout_sweep_log.json`
- `/Users/ck/dev/things/rev-revit/docs/inbox/ecc-layout-sweep.md` (this note)

## Unknowns / open

1. Header bits: whether Autodesk's reader ignores the ≤7 leading header bits
   of a final field (zero-header codeword accepted) — expected yes (syndrome
   decoder, V9), needs one live upload to confirm.
2. Whether degrees 6, 8, 10 are truly absent from the writer's table (never
   selected in this corpus; the rule with {4,5,7,9,11} fits 55/55 — with
   m=10 allowed it would have mispredicted rst Global/ElemTable).
3. Round-half tie behaviour of `round(n/K_m)` (no corpus case within 0.08 of
   a .5 boundary).

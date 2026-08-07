# ECC GEOMETRY — CRACKED end-to-end (agent `ecc-geometry`)

Code: `experiments/ecc/geometry.py` (verification + probe + writer functions).
Run `python geometry.py` (full verification, ~3 min) or `python geometry.py reframe`.
All statements below are verified byte-exactly against ALL SIX 2026 sample
files **and** independently against 18 more Revit files (2016–2026 vendor
corpus) — the geometry has been version-stable for a decade.

## 0. TL;DR (for the writer / LEAD)

* A stream = **payload buffer** (the logical bytes) chopped into pages.
  Every page is ONE codeword ("block") of the SAME code family:
  `g(x) = h_m(x^I)`, `h_m` = primitive trinomial of degree m, i.e. the block's
  bits (LSB-first per byte, first bit = highest degree) dealt round-robin
  into **I lanes**, each lane a cyclic (2^m−1, 2^m−1−m) Hamming/CRC-m
  codeword. Trinomials: m=4 `x^4+x+1`, 5 `x^5+x^2+1`, 6 `x^6+x+1`,
  7 `x^7+x+1`, 9 `x^9+x^4+1`, 11 `x^11+x^2+1`.
* **Full page** = the block for a 64,896-byte payload chunk = (I,m)=(255,11):
  codeword N = 2047·255 = 521,985 bits, block R = ⌈N/8⌉ = 65,249 bytes,
  **7 trailing zero pad bits** (8R−N), 255·11 = 2,805 parity bits, message
  capacity 519,180 bits = 8·64,896 + **12** (those 12 unused message bits are
  the "always-zero" byte0 + low nibble). ⇒ the whole "3 metadata bytes /
  0-1 flag" story is PURE GEOMETRY, no semantics. 3,502/3,502 full pages obey
  it; an independent big-int encoder in `geometry.py` reproduces sampled
  full trailers byte-exactly (35/35), `layout_sweep.py` all 3,502.
* **FINAL (partial) block** — the crux of this angle — is byte-exactly
  explained by ONE rule (55/55 blocks in the six 2026 files, 179/179 in the
  2016-2026 vendor files, parity regenerated from message bits = real bytes
  in every case, including all six `Formats/Latest` finals):
  ```
  P' = payload buffer length (bytes) that goes into the final block
  K(m) = 2^m − 1 − m,  L(m) = 2^m − 1,  m tried in order 4,5,6,7,9,11
  for m in (4,5,6,7,9,11):
      I = max(65, ceil(8·P' / K(m)))
      if I <= I_MAX (or m == 11):  break            # I_MAX ∈ {79,80,81}, see §5
  if I == 65 and 8·P' <= 65·K(m):   # SHORTENED case (lanes shorter than 2^m−1)
      R = P' + ceil(65·m/8);  N = 8·R;  t_pad = 0;  F = ceil(65·m/8) field bytes,
      the field's first 8F−65m bits are extra message bits (write them as 0)
  else:                             # QUANTIZED case (every lane full length)
      N = L(m)·I;  R = ceil(N/8);  t_pad = 8R − N = I mod 8 trailing zero bits;
      message capacity K(m)·I bits ≥ 8·P'; payload occupies the block's first
      P' bytes, the rest of the message region is zero (Revit sometimes leaves
      junk there — irrelevant to validity)
  parity = the codeword's m·I lowest-degree coefficients
         = (message(x)·x^{m·I}) mod g(x), stored just above the t_pad bits
         (block(x) = codeword(x)·x^{t_pad}).
  ```
  A full page is exactly this rule at P'=64,896 → (I,m)=(255,11), R=65,249.
* **Trailer length as a function of the final page** (the question I was
  given) is therefore NOT a simple `a + b·ceil(D/c)` law and NOT proportional
  to D: it is the field of a shortened/quantized codeword whose parameters
  come from the payload buffer length P' via the staircase above. Every
  observed short trailer length is reproduced (see the tables), including
  the tiny ones the brief flagged (37 bytes for a 97-byte page: (I,m)=(71,4)).
* Byte-exact test-rig assertion output (real bytes):
  ```
  ASSERTION PASSED: encode_full_page(page)[64896:] == trailer  (353 bytes byte-exact)
  ASSERTION PASSED: rebuild_block(final block, I=205, m=11, t_pad=5) == real final block (52455 bytes, byte-exact)
  [2026 samples] final blocks: 55; parity byte-exact regenerated: 55/55; length/t_pad quantization holds: 55/55; D<=capacity: 55/55; writer-rule reproduces (m,I,R) for some P>=D: 55/55
  [vendor files] final blocks: 179; parity byte-exact regenerated: 179/179; length/t_pad quantization holds: 179/179; D<=capacity: 179/179; writer-rule reproduces (m,I,R) for some P>=D: 179/179
  ```

## 1. Full-page rule — verified, zero exceptions

Over ALL streams of ALL six samples (`open_rvt`): 78 streams, 3,502 full
pages. For every k with `k·65249 + 65249 ≤ len(raw)`:
payload `raw[k·65249 : k·65249+64896]`, trailer `raw[k·65249+64896 : (k+1)·65249]`.

| property (all 3,502 full-page trailers) | result |
|---|---|
| byte0 | 0x00 in 3,502/3,502 |
| byte1 low nibble | 0 in 3,502/3,502; high nibble uniform over 16 values (198–242 each) |
| byte352 (last) | 0x00: 1,782 / 0x01: 1,720 (a fair coin); never > 1 |
| nibble ⟂ page index k, ⟂ last-page, ⟂ flag | no correlation (they are 5 parity bits, not metadata) |
| independent re-encode (my big-int mod-g encoder) | byte-exact on 35/35 sampled pages (every 101st) |
| lane encoder (`layout_sweep.py`) | byte-exact 3,502/3,502 (other agent) |

**Anatomy of the 353-byte full trailer as an LSB-first bit field**
(bit i = byte i//8, bit i%8):

| bits | count | content |
|---|---:|---|
| 0–11 | 12 | zero — the 12 unused message bits (capacity 519,180 − payload 519,168) |
| 12–2816 | 2,805 | 255 lanes × 11 CRC-m parity bits (nibble of byte1 = bits 12–15, byte352 bit0 = bit 2816 = the exponent-0 parity bit) |
| 2817–2823 | 7 | trailing pad = 8·65249 − 2047·255; block(x)=codeword(x)·x^7 |

So there are NO metadata bytes: byte[0], byte[1]&0x0f and byte[352]&0xfe are
structural zeros; everything else is code. (The brief's §6 "3 metadata
bytes" hypothesis is retired.)

## 2. Final partial page — the boundary and length rule, SOLVED

The final "page" is a block of R = len(raw) − ⌊len(raw)/65249⌋·65249 bytes
(if len(raw) is an exact multiple of 65249 the last stride is itself the
final block — happens when P' ≥ 64,644, e.g. the 2017 rfa `Formats/Latest`).
Inside it: `[payload P' bytes][zero-or-junk message slack][field]`, and the
whole block is one codeword. **The data/trailer boundary is not marked by
the bytes at all** (that is why the zero-pad boundary looked ambiguous):
what the reader can do is derive (I,m) from R (or try the small candidate
set — see §5) and check the syndrome; the payload/junk split is the writer's
business. For OUR writer the boundary is simply where we stop writing data.

### 2.1 Every final block of the six 2026 samples (55, incl. Partitions/*)

(I,m) found by pure divisibility (a random block divisible by h_m(x^I) has
probability 2^{−I·m} ≤ 2^{−260}), then P' interval derived from capacity,
D = last gzip member end (hard lower bound for P'), parity regenerated from
the block's own message bits and byte-compared:

| file | stream | R (block) | I | m | mode | t_pad | field bytes F | payload P' interval | D (gzip end) | parity regen |
|---|---|---:|---:|---:|---|---:|---:|---|---:|---|
| dach-sample- | Contents | 220 | 65 | 5 | short | 0 | 41 | [0,179] | 173 | True |
| dach-sample- | Formats/Latest | 52455 | 205 | 11 | quant | 5 | 283 | [51919,52172] | 51751 | True |
| dach-sample- | Global/ContentDocuments | 34032 | 133 | 11 | quant | 5 | 184 | [33595,33848] | 33659 | True |
| dach-sample- | Global/DocumentIncrementTable | 3949 | 65 | 9 | short | 0 | 74 | [0,3875] | 3868 | True |
| dach-sample- | Global/ElemTable | 35567 | 139 | 11 | quant | 3 | 192 | [35122,35375] | 35164 | True |
| dach-sample- | Global/History | 46314 | 181 | 11 | quant | 5 | 250 | [45811,46064] | 45897 | True |
| dach-sample- | Global/Latest | 33520 | 131 | 11 | quant | 3 | 181 | [33086,33339] | 33103 | True |
| dach-sample- | Global/PartitionTable | 145 | 77 | 4 | quant | 5 | 40 | [105,105] | 104 | True |
| dach-sample- | Partitions/84 | 50920 | 199 | 11 | quant | 7 | 275 | [50392,50645] | 50422 | True |
| dach-sample- | Partitions/85 | 291 | 75 | 5 | quant | 3 | 48 | [241,243] | 194 | True |
| racadvanceds | Contents | 212 | 65 | 5 | short | 0 | 41 | [0,171] | 166 | True |
| racadvanceds | Formats/Latest | 52455 | 205 | 11 | quant | 5 | 283 | [51919,52172] | 51751 | True |
| racadvanceds | Global/ContentDocuments | 13862 | 65 | 11 | short | 0 | 90 | [0,13772] | 13764 | True |
| racadvanceds | Global/DocumentIncrementTable | 683 | 65 | 7 | short | 0 | 57 | [0,626] | 624 | True |
| racadvanceds | Global/ElemTable | 27379 | 107 | 11 | quant | 3 | 148 | [26978,27231] | 27146 | True |
| racadvanceds | Global/History | 10214 | 65 | 11 | short | 0 | 90 | [0,10124] | 10122 | True |
| racadvanceds | Global/Latest | 53990 | 211 | 11 | quant | 3 | 291 | [53446,53699] | 53201 | True |
| racadvanceds | Global/PartitionTable | 179 | 65 | 5 | short | 0 | 41 | [0,138] | 134 | True |
| racadvanceds | Partitions/13 | 39149 | 153 | 11 | quant | 1 | 211 | [38685,38938] | 38573 | True |
| racbasicsamp | Contents | 212 | 65 | 5 | short | 0 | 41 | [0,171] | 166 | True |
| racbasicsamp | Formats/Latest | 52455 | 205 | 11 | quant | 5 | 283 | [51919,52172] | 51751 | True |
| racbasicsamp | Global/ContentDocuments | 35567 | 139 | 11 | quant | 3 | 192 | [35122,35375] | 35304 | True |
| racbasicsamp | Global/DocumentIncrementTable | 862 | 65 | 7 | short | 0 | 57 | [0,805] | 797 | True |
| racbasicsamp | Global/ElemTable | 50408 | 197 | 11 | quant | 5 | 272 | [49883,50136] | 49827 | True |
| racbasicsamp | Global/History | 14146 | 65 | 11 | short | 0 | 90 | [0,14056] | 14050 | True |
| racbasicsamp | Global/Latest | 51943 | 203 | 11 | quant | 3 | 280 | [51410,51663] | 51319 | True |
| racbasicsamp | Global/PartitionTable | 134 | 71 | 4 | quant | 7 | 37 | [97,97] | 97 | True |
| racbasicsamp | Partitions/15 | 43243 | 169 | 11 | quant | 1 | 233 | [42757,43010] | 42457 | True |
| rmebasicsamp | Contents | 212 | 65 | 5 | short | 0 | 41 | [0,171] | 168 | True |
| rmebasicsamp | Formats/Latest | 52455 | 205 | 11 | quant | 5 | 283 | [51919,52172] | 51751 | True |
| rmebasicsamp | Global/ContentDocuments | 11977 | 65 | 11 | short | 0 | 90 | [0,11887] | 11878 | True |
| rmebasicsamp | Global/DocumentIncrementTable | 780 | 65 | 7 | short | 0 | 57 | [0,723] | 718 | True |
| rmebasicsamp | Global/ElemTable | 20726 | 81 | 11 | quant | 1 | 112 | [20361,20614] | 20502 | True |
| rmebasicsamp | Global/History | 13195 | 65 | 11 | short | 0 | 90 | [0,13105] | 13099 | True |
| rmebasicsamp | Global/Latest | 12050 | 65 | 11 | short | 0 | 90 | [0,11960] | 11952 | True |
| rmebasicsamp | Global/PartitionTable | 179 | 65 | 5 | short | 0 | 41 | [0,138] | 133 | True |
| rmebasicsamp | Partitions/14 | 44779 | 175 | 11 | quant | 7 | 242 | [44284,44537] | 43981 | True |
| rstadvanceds | Contents | 236 | 65 | 5 | short | 0 | 41 | [0,195] | 192 | True |
| rstadvanceds | Formats/Latest | 52455 | 205 | 11 | quant | 5 | 283 | [51919,52172] | 51751 | True |
| rstadvanceds | Global/ContentDocuments | 37614 | 147 | 11 | quant | 3 | 203 | [37158,37411] | 37381 | True |
| rstadvanceds | Global/DocumentIncrementTable | 707 | 65 | 7 | short | 0 | 57 | [0,650] | 646 | True |
| rstadvanceds | Global/ElemTable | 10092 | 65 | 11 | short | 0 | 90 | [0,10002] | 9996 | True |
| rstadvanceds | Global/History | 10246 | 65 | 11 | short | 0 | 90 | [0,10156] | 10149 | True |
| rstadvanceds | Global/Latest | 62178 | 243 | 11 | quant | 3 | 335 | [61590,61843] | 61776 | True |
| rstadvanceds | Global/PartitionTable | 155 | 65 | 5 | short | 0 | 41 | [0,114] | 112 | True |
| rstadvanceds | Partitions/12 | 25844 | 101 | 11 | quant | 5 | 140 | [25451,25704] | 25039 | True |
| rstbasicsamp | Contents | 212 | 65 | 5 | short | 0 | 41 | [0,171] | 168 | True |
| rstbasicsamp | Formats/Latest | 52455 | 205 | 11 | quant | 5 | 283 | [51919,52172] | 51751 | True |
| rstbasicsamp | Global/ContentDocuments | 28914 | 113 | 11 | quant | 1 | 156 | [28505,28758] | 28314 | True |
| rstbasicsamp | Global/DocumentIncrementTable | 1096 | 69 | 7 | quant | 5 | 61 | [1021,1035] | 1017 | True |
| rstbasicsamp | Global/ElemTable | 7191 | 65 | 11 | short | 0 | 90 | [0,7101] | 7097 | True |
| rstbasicsamp | Global/History | 17144 | 67 | 11 | quant | 3 | 93 | [16798,17051] | 16875 | True |
| rstbasicsamp | Global/Latest | 64737 | 253 | 11 | quant | 5 | 349 | [64135,64388] | 63974 | True |
| rstbasicsamp | Global/PartitionTable | 134 | 71 | 4 | quant | 7 | 37 | [97,97] | 97 | True |
| rstbasicsamp | Partitions/21 | 821 | 65 | 7 | short | 0 | 57 | [0,764] | 587 | True |

("field bytes F" = ⌈(m·I + t_pad)/8⌉ = the bytes touched by parity+pad; the
short/trailer *length* asked for by the brief is R − P'. Note P' is Revit's
payload BUFFER length, D ≤ P': the buffer carries slack — 168…422 zero (and
sometimes junk) bytes after the gzip end — which is why the raw remainder
length was a "step function of D": the writer sized the buffer, not the
data. Where P'min=P'max the buffer length is pinned exactly, e.g. the
racbasic/rstbasic `Global/PartitionTable`: P'=97=D, F=R−P'=37 exactly, the
brief's "~37-byte trailer for a page of a few hundred bytes".)

### 2.2 The rule reproduces the (R → I,m) staircase across 2016–2026

234 final blocks over 24 files, all (I,m) recovered by divisibility, all
consistent with the writer rule for some P' ≥ D. Observed steps (excerpt,
vendor files aggregated; the full 2026 table is above):

| m | I | mode | R examples | note |
|---:|---:|---|---|---|
| 4 | 65 | short | 82 | payload ≤ 89 B (rfa `Global/ContentDocuments`, ×13) |
| 4 | 67,69,71,75,77 | quant | 126,130,134,141,145 | R = ⌈15·I/8⌉ exactly; `Global/PartitionTable` 2026: R=134→I=71, R=145→I=77 |
| 5 | 65 | short | 155…252 | R = P'+41 (Contents, PT) |
| 5 | 69,71,73,75,77,79 | quant | 268,276,283,291,299,307 | R = ⌈31·I/8⌉ exactly |
| 6 | 65 | short | 350 | R = P'+49 (only sample: Einhoven 2023 DIT, P'=301) |
| 7 | 65 | short | 683…1032 | R = P'+57 (all six 2026 `Global/DocumentIncrementTable`) |
| 7 | 69,73 | quant | 1096, 1159 | R = ⌈127·I/8⌉ (rstbasic DIT I=69; 2024 rfa Partitions/67 I=73) |
| 9 | 65 | short | 1463…3949 | R = P'+74 (26 blocks) |
| 11 | 65 | short | 5176…16632 | R = P'+90 (P' from 5,086 [rac-2018 Formats/Latest] to 16,542) |
| 11 | 66…255 | quant | 16888…65249 | R = ⌈2047·I/8⌉ exactly; e.g. 17144 (I=67), 20726 (I=81), 27379 (I=107), 52455 (I=205 = the six `Formats/Latest`), 64737 (I=253), 65249 (I=255 = a full page) |

The switch-over payload thresholds (I_MAX·K_m/8 with I_MAX=81):
m=4 ≤ 111 B < m=5 ≤ 263 B < m=6 ≤ 577 B < m=7 ≤ 1,215 B < m=9 ≤ 5,082 B
< m=11 ≤ 64,896 B. Tight corpus confirmations: P'=105 uses (77,4) but
P'=114 uses (65,5); P'=256 uses (79,5); P'=301 uses (65,6); P'=1,035 uses
(69,7); P'=5,086 uses (65,11) (⇒ I_MAX ≤ 81 since m=9 would need I=82);
P'=64,896 ⇒ (255,11).

## 3. Answers to the four assigned sub-questions

1. **Full-page rule exceptions: NONE.** 3,502/3,502 (byte0=0, low nibble 0,
   last ≤ 1), and the (255,11) codeword regenerates them byte-exactly.
2. **Final partial page rule:** solved (§2). `n_full = len(raw)//65249`;
   `rem = raw[n_full·65249:]` (R = len(rem)); the block's parameters follow
   from R (§5 inversion) and its parity is a pure function of the block's
   message bits. The **short trailer length t = R − P'** where P' is the
   payload buffer; as a function of the data length D it is not a function
   at all (P' ≥ D includes writer slack), but **as a function of P' it is
   exactly**: t = ⌈65m/8⌉ ∈ {33,41,49,57,74,90} in the shortened cases
   (m=4,5,6,7,9,11) and t = ⌈L(m)·I/8⌉ − P' in the quantized cases. Every
   (D, t-interval) pair is listed in the §2.1 table (D column + F/P' columns).
   All the brief's candidate laws (a+b·ceil(D/c), round(353·D/64896)) are
   refuted: e.g. D=97→37, D=1764→75 but D=2266→74, D=51751→282…284.
3. **Metadata bytes decoded:** there are none. byte[0]=0 and the low nibble
   of byte[1] are the 12 unused message bits of the (255,11) block; the high
   nibble of byte[1] and byte[352] bit 0 are ordinary parity bits (their
   distributions are uniform / a fair coin and independent of page index,
   stream, and last-page-ness — verified over 3,502 pages); the last byte's
   upper 7 bits are the block's trailing pad (t_pad = 255 mod 8 = 7). On
   final blocks the analogous facts are: t_pad = I mod 8 zero bits at the end
   (quantized) or none (shortened), and 8F−m·I "base" bits at the start of the
   field that are just extra message bits (zero when Revit's buffer was
   clean, junk otherwise; the reader accepts either).
4. **Code-region scaling:** on a full page the code region is exactly 2,805
   bits (bits 12..2816), NOT 350 bytes = 2,800 bits — the "350 = 175×2"
   arithmetic was a coincidence. The code does not scale in 2-byte units per
   372-byte chunk; it scales as `parity bits = m·I` with (I,m) from the
   staircase (§0), e.g. 284 bits (71,4) at P'=97, 585 bits (65,9) for
   1.2–4 KB payloads, 715 bits (65,11) for 5–16 KB payloads, 2,255 bits
   (205,11) for the schema final block, 2,805 bits (255,11) for a full page.

## 4. Corrections to earlier fleet notes

* `layout_sweep.py`'s claim that `Global/PartitionTable` (and by the same
  detector `Contents`-like tiny streams) carry NO ECC is WRONG: PT is
  ECC-framed with **m=4** (racbasic/rstbasic: (71,4), R=134; dach: (77,4),
  R=145) or m=5 (racadv/rme/rstadv/rfa: (65,5) shortened). Their parameter
  rule (`I=max(65, round(8P/K_m))` over m∈{5,7,9,11} minimising I·m, plus
  `F=ceil(I·m/8)`) is a fitted approximation that happens to hit their 52
  blocks; the true rule adds m=4 and m=6, uses `ceil`, an I ≤ ~81 gate rather
  than "minimise I·m", the R-quantisation `R=ceil(L(m)·I/8)` and t_pad = I
  mod 8. Everything else in their note (255 lanes, CRC-11, 12+7 pad bits) is
  right and is a special case of §0.
* Streams genuinely WITHOUT ECC framing (no page slicing, no divisor found,
  plain bytes): `BasicFileInfo`, `TransmissionData`, `ProjectInformation`,
  `RevitPreview4.0` (all six samples), and `PartAtom` in .rfa. Everything
  else — `Formats/Latest`, `Contents`, all `Global/*` INCLUDING
  `Global/PartitionTable`, all `Partitions/*` — is ECC-framed.

## 5. Reader-side inversion and the writer recipe (for cfb-writer / LEAD)

Because R alone determines (I,m) except at three payload sizes, a reader
can invert the staircase; the writer must simply emit blocks a Revit writer
could emit. Reachable (R → (I,m)) is one-to-one **except** R ∈ {314 [(5,81)
or (6,65)], 638 [(6,81) or (7,65)], 5174 [(9,81) or (11,65)]}. The lane
ceiling for m<11 is pinned by the corpus to **I_MAX ∈ {79, 80, 81}** (all
three reproduce all 234 blocks; ≤78 breaks racbasicfamily-2024 `Contents`
(79,5); ≥82 breaks rac-2018 `Formats/Latest` (65,11)). **Safe writer policy:**
never emit I ∈ {79,80,81} for m<11 (pad the payload with a few zero bytes
into the next m's shortened range) and never emit the m=6 range if you want
to stay within combinations *observed in 2026 files* (m=6 appears only in a
2023 file; the trinomial x^6+x+1 fits the family so it is very likely fine).
Recipe:

```python
from experiments.ecc.geometry import frame_stream        # payload -> raw stream
raw = frame_stream(logical_payload)                       # pages + final block
# or per block: encode_final_block(payload), encode_full_page(page64896)
```

`geometry.py reframe` rebuilds 43 whole raw streams (≤6 pages each) from
their own payload buffers: 6/43 are byte-identical to Revit's originals; the
other 37 differ ONLY inside the message slack between the payload end and
the parity (Revit's buffer sometimes carries stale junk bytes there — e.g.
`Formats/Latest` final has 4 junk bits at the end of byte 52,171 and low
nibble of byte 52,172) and their parity therefore differs, yet every rebuilt
block re-derives to the same (I,m) and passes the syndrome check (43/43).
With the SAME message bits (junk included) the encoder reproduces Revit's
parity byte-exactly on all 234 final blocks — that is the byte-exact proof.

## 6. Method notes (how the boundary was actually found)

* The zero-pad/trailer boundary is unrecoverable from local byte structure;
  it took (a) the observation that identical-content streams share the same
  remainder length across files while different-content streams with the same
  D do not (⇒ buffer slack, not a length law), then (b) the discovery that
  even D-vs-length is NON-MONOTONE within one version (2026 rfa
  `Global/DocumentIncrementTable` D=1,764 → t≥75 vs `Global/History`
  D=2,266 → t≤74), which killed every "t = f(D)" hypothesis, and finally
  (c) an exhaustive divisor probe (`geometry_probe.py`): for each block try
  all (I ≤ 255, primitive trinomial m ≤ 11) with a numpy per-lane LFSR; a
  divisor with I·m ≥ 260 is a certainty (p = 2^−I·m). The (R,I,m) table it
  produced exposed the quantisation R = ⌈(2^m−1)·I/8⌉ and the I=65 floor at
  once (e.g. 8R − 2047·I ∈ {3,5} for every large m=11 block).
* All probe/verify code: `experiments/ecc/geometry.py`
  (`analyse_final_block`, `probe_block`, `verify_full_page_rule`,
  `verify_final_blocks`, `reframe_demo`), the raw sweep that found m=4:
  `experiments/ecc/geometry_probe.py`; per-block JSON of the whole 24-file
  corpus: scratchpad `geom/geometry_table.json`.

## 7. Unknowns / caveats

1. I_MAX is 79, 80 or 81 (corpus cannot separate them; avoid emitting
   I∈{79,80,81} for m<11 and the point is moot).
2. m=6 (x^6+x+1) is inside the rule but observed only in a 2023 file
   (Einhoven DIT, P'=301); m=8/10 have no primitive trinomial and are indeed
   never used. Whether the 2026 reader still accepts m=6 blocks is untested —
   a writer can dodge the m=6 payload range (264…577 B) by padding.
3. Whether the reader derives (I,m) from R by the same formula or simply
   tries the small candidate set is unknown (needs Utility.dll or a viewer
   probe); either way blocks produced by this rule are ones Revit itself
   produces. The three ambiguous R values (§5) should be avoided defensively.
4. The message-slack junk in Revit's own final blocks (§5) proves the reader
   does not care about the payload/junk split; but an end-to-end viewer test
   of `frame_stream` output (all-zero slack) is still the required final
   proof — hand `geometry.frame_stream` to the writer gate.
5. Correction capacity: 1 bit per lane (Hamming) ⇒ any single burst ≤ I bits
   per block, consistent with V9 (one flipped trailer byte repaired).

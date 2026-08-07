# 12 — Element object ENCODER: byte-exact decode → encode round trip

Status: **DONE — the schema-directed encoder is the proven exact inverse of
the decoder.** Every partition record that `rvt.objects` decodes cleanly
is re-serialized to the **identical byte string** (record header, sizes,
class id, object body, size-repeat trailer), across all five sub-100 MB
sample projects and all three record streams (seq 101 / 102 / 103), and
whole per-seq segments reconstruct byte-for-byte.

- Encoder: `src/rvt/encode.py` (`ObjectEncoder`, `Writer`, `encode_record`,
  `roundtrip_segment`, `reencode_segment`; driver `python -m rvt.encode
  [project] [seq...]`).
- Tests: `tests/test_encode.py` (11 tests, ~45 s; full-corpus, no
  sampling).
- Decoder fixes required for byte-exactness: two, both minimal — see §6
  and `docs/inbox/serializer.md`.

Confidence: **[V]** = verified by byte-for-byte equality over the full
corpus (below). There is nothing statistical here: a record either
reproduces exactly or it does not, and all of them do.

## 1. Results — pass rates (byte-exact)

A record **PASSES** iff `encode_record(seq, id, stamp, class_id,
decoded_value) == original record bytes` (all of: `i64 id`, `u32 stamp`,
`u32 psize`, `u16 class_id`, every object byte, trailing `u32 psize`).
"tested" = every record whose decode is clean (100 % of body bytes
consumed, no error) plus every save-unit sentinel (id −1). The only records
outside the tested set are the corpus's Extensible-Storage entity records
(`ESEntity.m_blob`, blocker B1 in `10-objects.md`), which do not decode
and therefore have no value dict to re-encode.

| project | seq | records | tested | byte-exact PASS | fail | distinct classes | skipped (undecodable) |
|---------|----:|--------:|-------:|----------------:|-----:|-----------------:|---------------------:|
| racbasicsampleproject | 101 | 85,978 | 85,978 | **85,978 (100.000 %)** | 0 | 1 | 0 |
| racbasicsampleproject | 102 | 85,978 | 85,978 | **85,978 (100.000 %)** | 0 | 306 | 0 |
| racbasicsampleproject | 103 | 85,978 | 85,978 | **85,978 (100.000 %)** | 0 | 2 | 0 |
| rmebasicsampleproject | 101 | 142,480 | 142,480 | **142,480 (100.000 %)** | 0 | 1 | 0 |
| rmebasicsampleproject | 102 | 142,480 | 141,309 | **141,309 (100.000 %)** | 0 | 306 | 1,171 |
| rmebasicsampleproject | 103 | 142,480 | 142,480 | **142,480 (100.000 %)** | 0 | 2 | 0 |
| racadvancedsampleproject | 101 | 59,575 | 59,575 | **59,575 (100.000 %)** | 0 | 1 | 0 |
| racadvancedsampleproject | 102 | 59,575 | 59,575 | **59,575 (100.000 %)** | 0 | 312 | 0 |
| racadvancedsampleproject | 103 | 59,575 | 59,575 | **59,575 (100.000 %)** | 0 | 2 | 0 |
| rstadvancedsampleproject | 101 | 65,147 | 65,147 | **65,147 (100.000 %)** | 0 | 1 | 0 |
| rstadvancedsampleproject | 102 | 65,147 | 65,147 | **65,147 (100.000 %)** | 0 | 300 | 0 |
| rstadvancedsampleproject | 103 | 65,147 | 65,147 | **65,147 (100.000 %)** | 0 | 2 | 0 |
| rstbasicsampleproject | 101 | 32,064 | 32,064 | **32,064 (100.000 %)** | 0 | 1 | 0 |
| rstbasicsampleproject | 102 | 32,064 | 32,057 | **32,057 (100.000 %)** | 0 | 310 | 7 |
| rstbasicsampleproject | 103 | 32,064 | 32,064 | **32,064 (100.000 %)** | 0 | 2 | 0 |

Corpus total: **1,153,554 tested records, 1,153,554 byte-exact (100.000 %),
0 failures**, over **397 distinct record classes** (seq 101 =
`ElementHeader` 0x5e5, seq 103 = `GElement` 0x89e + `SerializedDummy`
0x0f2c, seq 102 = 300–312 element classes per file), well above the ≥ 99 %
target. `dach-sample-project` (128 MB partition) not run — runtime only,
same reason as `10-objects.md` B3.

**Whole-segment reconstruction [V].** `reencode_segment(seg, seq)` decodes
*every* record of a segment and rebuilds the whole byte stream (records
that do not decode — the ES-entity records only — and id −1 sentinels are
passed through verbatim). Result is **byte-identical** to
`partitions.concat_segment(seq)` for every project × seq measured:

| project | seq | segment bytes | identical |
|---------|----:|--------------:|:---------:|
| rstbasicsampleproject (Partitions/21) | 101 | 5,888,965 | ✓ |
| rstbasicsampleproject (Partitions/21) | 102 | 25,524,205 | ✓ (7 ES records passed through) |
| rstbasicsampleproject (Partitions/21) | 103 | 8,400,602 | ✓ |
| racbasicsampleproject | 101 / 102 / 103 | 15,268,302 / 63,944,890 / 28,475,933 | ✓ ✓ ✓ |
| rmebasicsampleproject | 101 / 102 / 103 | 26,490,620 / 111,373,476 / 50,129,994 | ✓ ✓ ✓ (1,171 pass-through) |
| racadvancedsampleproject | 101 / 102 / 103 | 11,472,937 / 52,050,283 / 31,454,545 | ✓ ✓ ✓ |
| rstadvancedsampleproject | 101 / 102 / 103 | 11,456,138 / 47,047,439 / 26,915,890 | ✓ ✓ ✓ |

Reproduce: `python -m rvt.encode racbasicsampleproject 102 101 103` (prints
the per-seq record pass rate, any first-divergence hex diff, and the
whole-segment identity check); `pytest tests/test_encode.py -s`.

## 2. Design — the transpose of the decoder

The encoder walks the **same schema, in the same order, with the same
dispatch** as `ObjectDecoder`; every `Reader.x()` call site in the decoder
has a `Writer.x()` call site here. `ObjectEncoder` holds an `ObjectDecoder`
and reuses its parsed schema and its parent-first `chain()` cache, so the
two can never disagree about class layout.

```
encode_record(seq, id, stamp, class_id, value)
  = header + u16 class_id + encode_object(class_id, value) + u32 psize
encode_object(class_id, value)                       # object bytes only
  _encode_class(root)                                # parent-first fields
  then drain the deferred-body FIFO breadth-first     # same queue discipline
_encode_class(cid, dict) : for cd in chain(cid): for f in cd.fields:
                             _encode_field(f, dict[key(cd,f)])
_encode_field  : AString / inline-array(0x0d) / container(shape 5) /
                 fixed-array(shape 1) / scalar
_encode_scalar : primitive / GUID / classref(0x0a) / class(0x0e):
                 value-class inline | weakref u32 | pointer token
_encode_pointer: None→i32 0 | backref→i32 pid | new→i32 pid + u16 class,
                 body queued (deferred)
```

## 3. Record framing (`encode_record`) [V]

Exactly the framing proven in `10-objects.md §2`:

| offset | size | field | written value |
|-------:|-----:|-------|---------------|
| 0 | 8 | `i64 id` | element id (record id) |
| 8 | 4 | `u32 stamp` | seq 102/103 only (absent in seq 101); the original stamp is passed through — it is per-record metadata not derivable from the object (B8) |
| 8/12 | 4 | `u32 psize` | 2 + len(object bytes) |
| … | 2 | `u16 class_id` | schema type_id (identity mapping) |
| … | psize−2 | object | `encode_object` output |
| … | 4 | `u32 psize` | repeat |

Degenerate kinds: save-unit **sentinel** (`id = −1`) = header with
`psize = 0`, **no class word**, trailer `u32 0` (16 or 20 bytes total);
**`SerializedDummy`** (seq 103) = a zero-field class → empty object,
`psize = 2`. Both reproduce exactly (racbasic seq 103: 85,978/85,978).

## 4. Codebook symmetry — decoder `Reader` ↔ encoder `Writer`

Every row is byte-exact-verified by the corpus round trip.

| construct (schema kind / flags) | decode (`objects.Reader`) | encode (`encode.Writer`) | byte-exactness note |
|---|---|---|---|
| `bool` (kind 01) | `bool(u8)` | `u8(1 if v else 0)`; a non-bool raw int is written back unchanged | corpus bools are all 0/1 |
| `char` (02) | `u8` | `u8` | |
| `short` (03) | `i16` | `i16` | |
| `int` (04) / `uint` (05) | `i32` / `u32` | `i32` / `u32` | |
| `float` (06) | `f32` → Python float | `struct '<f'` | f32→f64→f32 is bit-exact for all corpus values (no NaN payloads observed) |
| `double` (07) | `f64` | `struct '<d'` | bit-exact incl. `-0.0`, denormals |
| `int64` (0b) | `i64` | `i64` | |
| `AString` (08, flags 0x60) | `u32 n` code units + UTF-16LE, `n == 0xFFFFFFFF` → `None` | `None` → `0xFFFFFFFF`; else `u32 (len(utf16le)/2)` + bytes | count is UTF-16 **code units** (surrogate pairs = 2); `surrogatepass` on both sides (§6.2) |
| container/array of AString (shape 5 / 1) | `count32` then n × astring | `u32 len` (shape 5 only) then n × astring | fixed-array count comes from the schema, never written |
| `GUID` (09) | 16 raw → `d1-d2-d3-t0t1-t2..7` string (d1..d3 LE) | `guid_to_bytes()` parses it back | lossless string form |
| class-def ref (0a) | `u16` → `{"classref": name}` | `u16 by_name[name].type_id` | class names are unique (0 duplicates in 4,690) |
| `ElementId`/`Identifier` value (0e 00 → 0x14) | `i64`, −1 invalid | `i64` | flattened both ways |
| `XYZ` / `UV` value | `3d` / `2d` list | `3d` / `2d` | flattened both ways |
| `GUIDvalue` value | as GUID | as GUID | flattened both ways |
| other inline value class (0e 00) | recursive `_decode_class` (parent-first) | recursive `_encode_class` | nested pointers go to the **same** record FIFO |
| fixed array (flags≫4 = 1) | schema `count` elements, no length on wire | elements only | count from schema |
| container (flags≫4 = 5) | `u32 count` + elements | `u32 len(list)` + elements | |
| inline-array wrapper (0d) | anonymous element descriptor repeated | same, element field re-encoded per item | |
| owned/poly pointer (0e 01/02/04) | `i32 pid`; 0 → `None`; seen pid>0 → `{"backref_pid"}`; else `u16 class` + body **deferred** to FIFO | `None` → `i32 0`; `{"backref_pid"}` → `i32 pid`; else `i32 pid` + `u16 class`, body queued | decoder **preserved every pid it read**, so writing them back reproduces the ORIGINAL numbering (1 = document, 2 = record root, 3… = allocated, −1 = anonymous); the FIFO drains in the identical breadth-first order |
| weak pointer (0e 03) | `u32 pid` → `{"weakref": pid}` | `u32 pid` | |
| record trailer | `u32 psize` repeat checked | written = psize | |

Why the pid numbering / deferred order reproduce for free: the decoder does
not renumber anything — the value tree carries `pid` on every pointer token
and encodes the token *kind* structurally (`ptr_class` = new object with
body, `backref_pid` = reference to an already-serialized index, `weakref`,
`None`). Re-walking the tree in schema order therefore emits the same tokens
in the same sequence, and appending bodies to a FIFO at the same moments the
decoder appended them yields the identical breadth-first body order. No
allocator has to be re-derived, which is exactly why 300+ classes with
100-plus-object trees (`FamilySymbol`) round-trip on the first try.

## 5. What "byte-exact" covers

For each of the 1.15 M tested records the comparison is over the **entire
raw record** including the 16/20-byte header (`id`, `stamp`, `psize`) and
the trailing `psize` repeat — not just the object body. The `stamp` is
carried from the source record (it is per-record metadata whose derivation
is unknown, B8, and is not a property of the object), everything else is
computed. So the encoder is a complete record synthesizer given `(id, stamp,
class_id, value)`; only `stamp`'s *generation* for a brand-new record
remains open (§7).

## 6. Quirks required for byte-exactness (the two decoder fixes)

Both were latent decoder **information losses** invisible to the decode-rate
metric (records still consumed 100 % of their bytes) but fatal to
reversibility. Fixed minimally in `objects.py`; all 147 pre-existing tests
still pass. Full write-up: `docs/inbox/serializer.md`.

**6.1 Shadowed field names collided in the flat value dict.** 18 of the
4,690 classes re-declare an ancestor's field name (e.g. `PropertySetLibrary`
declares its own `m_locked` in addition to `Element.m_locked`;
`RbsFlexPipeType.m_dRoughness`; `m_pConnectorManager` across the
`RbsInsulation` family; `EnergyAnalysisSurface.m_id`;
`MasterImportSymbol.m_subSymbolMap{Int,ElemId}`; `PanelScheduleView.
m_oTableData`; `ArcLengthDim.m_witnessRefs`; …). The decoder keyed a flat
dict by bare name, so the later value overwrote the earlier — a silent loss,
found because it produced the only two round-trip failures in racbasic
(1 × `RbsFlexPipeType`, 1 × `PropertySetLibrary`; first divergence at
`Element.m_locked` written as `01` where the wire had `00`). **Fix
(`objects.field_key`)**: the FIRST occurrence keeps its plain name
(existing consumers untouched); a shadowing re-declaration is stored under
`"<DeclaringClass>::<name>"`. `encode.py` applies the identical rule when
looking values up, so decode → encode stays symmetric.

**6.2 AString decoded with `errors="replace"`.** A lone UTF-16 surrogate
would have decoded to U+FFFD and re-encoded to different bytes. No corpus
record contains one (pass rate was already 100 % before the change), but
the encoder must be a true inverse, so `Reader.astring` now uses
`errors="surrogatepass"` and `Writer.astring` encodes with the same, which
is a bit-exact bijection for any 16-bit unit sequence
(`test_astring_surrogate_and_null_edges`). The change is invisible for every
valid string.

Checked and found **not** to need handling (would have shown as failures):
non-0/1 `bool` bytes, NaN payload bits in `float`/`double`, `-0.0`,
ambiguous zero-length containers, trailing pad after zero-field stub
objects, ambiguous null-vs-empty AString. All 100 % exact as-is.

## 7. Extensible-Storage records — opaque pass-through

The 1,178 records that do not decode (1,171 rme `FamilyInstance`, 6
rstbasic `RebarShape`, 1 rstbasic `DataStorage`; all `ESEntity.m_blob`,
`10-objects.md` B1) cannot be re-encoded from a dict because the blob's
length is unknown, so no clean raw span can be delimited inside the object.
Per the brief they are treated as opaque: `reencode_segment` copies such a
record's original bytes verbatim, which is why whole-segment reconstruction
is still byte-identical. Emitting a *new* ES record from scratch waits on
B1 (the ADocument ES-schema table).

## 8. Unknowns / open items

- **`stamp` (u32, seq 102/103 header)** — reproduced by pass-through; how
  Revit *generates* it for a new/modified record is unknown (85,799
  distinct values over racbasic's 85,814 records ⇒ `[H]` per-object
  hash/timestamp). Needed only when synthesizing brand-new records; a
  copied/edited record can reuse a plausible value. Verify against Revit's
  loader (does it validate the stamp?) in the writer acceptance loop.
- **New-object pid allocation policy** — reproducing existing pids is
  trivial (they ride the value tree), but a from-scratch element needs the
  allocator's rule for *which* sub-objects get an indexed pid > 2 versus
  −1 (anonymous). Observed convention: only objects that are the target of a
  later weak/back reference are indexed (encounter order from 3). `[H]`
  Provide an `assign_pids()` normalizer once the loader's tolerance is
  known (does an unreferenced −1 vs 3 matter?).
- **ES-entity records** (0.1 % of corpus) pass through opaque, not
  re-encodable field-wise (B1).
- **dach-sample-project** not exercised (runtime).
- Value-dict schema: the encoder trusts the dict shape the decoder emits
  (`ptr_class`/`pid`/`value`, `backref_pid`, `weakref`, `classref`); a
  hand-built dict must follow the same conventions (documented in the
  `encode.py` module docstring). A `validate_value()` pass with friendly
  errors for hand-authored objects is future work.

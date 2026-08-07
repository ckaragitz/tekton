# inbox: schema-b — cross-cutting findings for the orchestrator

## 1. `Formats/Latest` is only 27.8 % faithful (affects EVERY schema consumer)

The inflated schema stream (`Formats__Latest.gz/000.bin`, 498,766 B) is a
clean class dictionary for bytes `0x0–0x21DFA` (1,150 class records, names
`A3PartyAImage` … `DC3DGraphicsSettings` + head of `DDGraphSerializable`) and
**scrambled beyond `~0x21E64`** — 72 % of the stream. Evidence in
`docs/streams/01-schema-b.md` §7: field density collapses per 8 KiB window;
one 38-byte record header (`DBView3dEnergyAnalysis` @`0x20A7E`) is
duplicated verbatim ≥30 times in the tail; our own token-level deflate
decoder (byte-identical output to zlib) shows the tail is stitched from
scattered short LZ matches; the gzip CRC/ISIZE never match; the same collapse
appears in Revit family samples 2016–2026. Diagnosis: writer-side LZ encoder
defect — the deflate stream faithfully encodes garbage. **Class records
alphabetically after `DDG…` are not recoverable from this stream in any of
the six files.** Any agent claiming a full class list from this stream is
reading the LZ-duplicated garbage.

Implication for the tracker: A2 ("schema decode") can only be ~28 % complete
from `Formats/Latest`; the rest of the schema must come from
`Global/*` object data, another release, or reconstruction.

## 2. The known "corrupt gzip trailer" is the same defect

CRC/ISIZE mismatch on every stream + this scrambling both point at a
home-grown deflate writer in Revit. Worth checking whether `Global/*` /
`Partitions` gzip members show ANY signs of similar late-stream degradation
(they are much smaller so may be entirely within the encoder's safe range —
schema is the only >139 KB single member seen so far). Suggested check:
recompress each inflated member with zlib level 3 and compare compressed
prefixes; a long exact prefix match followed by divergence at ~40 KB is
this encoder's signature.

## 3. Grammar facts other agents can reuse (verified, method-B derived)

* Class ordinals start at **12**, assigned in definition order; `0x8000|N`
  = inline definition of ordinal N follows; `ElementId` = ordinal **20**
  (`0e 00 00 00 14 00`), `AString` fields are tag `08 60`, `Int64` = `0b`,
  `double` = `07`, `int` = `04`, `bool` = `01`, `unsigned long` = `05`,
  `float` = `06`, GUID = `09` — calibrated from `std::pair<>` synthetic
  class names, zero conflicts.
* Record layout: `u16 0000 marker, u16 nameLen, name, u16 baseRef,
  [inline base record], u32 version, u32 fieldCount, fields,
  u32 nGuid, guids[16*n]`. Top-level records tile the stream with zero gaps.
* 26 classes end with GUID lists (ADocument 1,509, AUnits 13, …) — meaning
  unknown.

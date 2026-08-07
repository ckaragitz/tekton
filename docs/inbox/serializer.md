# inbox — serializer (encoder agent)

## Decoder edits made (minimal, required for byte-exact round trip)

Two edits to `src/rvt/objects.py`, both fixing latent **information loss**
that the decode-rate metric could not see (records still consumed 100 % of
their bytes). All 147 pre-existing tests pass unchanged after them.

### 1. Shadowed (re-declared) field names collided in the flat value dict

`_decode_class` built `out[f.name] = value`. 18 of 4,690 classes re-declare
an ancestor's field name in their parent-first chain, so the later value
silently OVERWROTE the earlier one — the earlier field's value was lost, and
on re-encode both wire positions received the surviving value. This was the
sole cause of the initial round-trip failures (racbasic: 1 × RbsFlexPipeType
at `m_dRoughness`, 1 × PropertySetLibrary at `Element.m_locked`).

Affected classes (chain has a duplicate name): ArcLengthDim
(m_witnessRefs), DatumAlignment (m_locked), ElementTracking /
ElementTrackingData (m_pADoc), EnergyAnalysisSurface (m_id),
MasterImportSymbol (m_subSymbolMapInt, m_subSymbolMapElemId),
PanelScheduleView (m_oTableData), PropertySetLibrary (m_locked),
RbsColorFillSchema (m_dFillContourAtSize, m_dFillWidth), RbsDuctInsulation /
RbsInsulation / RbsInsulationLiningBase / RbsReference / RbsDuctLining
(m_pConnectorManager), RbsFlexPipeType (m_dRoughness), + 3 more. (Reproduce
with the chain scan in `12-encode.md` §6.1.) Zero within-class duplicates.

Fix: new helper `objects.field_key(cd, f, out)` — the FIRST occurrence
keeps its plain name (so `m_id`, `m_text`, `m_locked`, etc. and every
existing consumer/test are unaffected); a shadowing re-declaration is keyed
`"<DeclaringClass>::<name>"` (with a `#n` suffix guard for a hypothetical
triple shadow, never hit). `encode.py` imports the same helper and applies
the identical rule, keeping decode → encode symmetric.

NOTE for anyone reading decoded JSON: e.g. a PropertySetLibrary now exposes
BOTH `m_locked` (Element's) and `PropertySetLibrary::m_locked`; previously
only the derived one survived under the name `m_locked` and the base value
was gone. Any prior analysis that read `m_locked`/`m_id`/`m_pConnectorManager`
on those 18 classes was reading the DERIVED class's value, not Element's.

### 2. AString decode `errors="replace"` → `"surrogatepass"`

A lone UTF-16 surrogate decoded to U+FFFD and re-encoded to different bytes.
No corpus record contains one (racbasic/rme were already 100 % byte-exact
before this change), but the encoder must be a genuine inverse.
`Reader.astring` now decodes with `errors="surrogatepass"` and
`Writer.astring` encodes with the same — a bit-exact bijection for any
16-bit unit sequence. Every valid string is unchanged.

## Checked and NOT changed (verified exact as-is by the 1.15 M-record corpus
round trip)

- non-0/1 bool bytes: none in corpus (all bools 0/1).
- NaN payload bits in float/double: none.
- `-0.0`, denormals: `struct` round-trips them bit-exact.
- zero-length containers / null-vs-empty AString / stub-object trailing pad:
  all unambiguous on the wire.

## Out-of-scope observations (not acted on)

- `objects.load_segment` and `partitions.partition_stream_paths` both now
  skip `.logical.bin`; fine. But `load_segment` re-inflates every partition
  on each call (racbasic ~11 s of a 14 s decode). `roundtrip_segment` is
  therefore I/O-bound; a persistent `RVT_SEG_CACHE` default under
  `extracted/_cache/` would halve every partition-consuming agent's runtime.
  Owner: whoever maintains `objects.py`/`partitions.py`.
- The `stamp` u32 (seq 102/103 header) is the only record field the encoder
  cannot synthesize for a NEW record (it passes the source value through).
  Whether Revit's loader validates it should be added to the writer
  acceptance-test queue (fixture: rewrite one record with stamp 0 /
  stamp+1 and open in the viewer). Owner: acceptance harness.
- New-object pid allocation policy (which sub-objects get indexed pid > 2 vs
  −1) is unstudied; needed before hand-authoring elements from scratch.

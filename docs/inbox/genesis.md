# genesis — workstream record (GENESIS RESEARCH, 2026-08-03)

Charter: the pure-independence proof — a valid `.rvt` synthesized from
nothing. Tonight = research: (a) minimal-document reduction machinery +
staged reductions, (b) irreducible-core map, (c) synthesis plan. Territory
touched ONLY: `src/rvt/reduce.py`, `tools/rvt_reduce.py`,
`experiments/genesis/*`, `tests/test_reduce.py`, `docs/writer/genesis.md`,
this file. No orchestrator-owned files edited.

## Deliverables

| item | path | state |
|---|---|---|
| deletion writer (element DELETE + unit-0 re-blocking + structural verifier + reference-graph tools) | `src/rvt/reduce.py` | done, tested |
| staged driver (stage taxonomy, closure/safe-sweep, per-stage JSON reports) | `tools/rvt_reduce.py` | done |
| 8 staged reductions + identity control | `experiments/genesis/R{1..4}[s].rvt`, `R0_identity.rvt`, `R*.json`, `summary.json` | on disk, ALL structurally clean |
| tests (framing units + real-file integration) | `tests/test_reduce.py` (6 tests) | pass |
| plan + irreducible-core map + content strategy | `docs/writer/genesis.md` | done |

Reproduce: `.venv/bin/python tools/rvt_reduce.py` (72 s) from the repo
root; `--stage R2` for one; `--no-safe` skips the `R<n>s` variants.

## Files the orchestrator should viewer-test (in this order)

`experiments/genesis/R0_identity.rvt` (control: re-blocked, nothing
deleted — must open, else the re-emission itself is at fault), then
`R1s.rvt` (31 deletions, zero dangling anywhere), `R2s.rvt` (762
deletions, zero dangling), `R1.rvt` (7,627 deletions: whole model +
dependents; **1,281 ids left dangling inside Global/Latest** — the decisive
probe), `R2.rvt` (8,335; ZERO views survive), `R3.rvt` (9,337; no
symbols/families), `R4.rvt` (11,097; 2,839-element skeleton). Deepest that
translates = GENESIS SEED-0. Full table + risk ordering: genesis.md §3.

## Evidence log

### E1. Autodesk's partition blocking algorithm — reproduced byte-for-byte
`reduce.reblock()` rule: pack whole records greedily while payload ≤
131,072 (flags 4); a record with framed length > 131,072 starts a fresh
block, body-chunked at exactly 131,072 (flags 6 → 7… → 5, u32 size-repeat
in the last block). Applied to rstbasic's own three unit-0 record streams it
regenerates **all 213 blocks identically** — payload bytes, flags, A, C —
including the 4 spanning chains (seq102: `[6,7,7,5]`, `[6,5]`, `[6,5]`;
seq103: `[6,5]`, `[6,5]`). Flags-6 blocks are exactly 16 + 131,072 =
131,088 payload bytes (header + first body chunk); flags-7 exactly 131,072;
whole-record blocks max 131,071. (`test_identity_delete_reproduces_original_blocking`.)

### E2. The reader does NOT validate the block `C` (or `A`) counter
The proven-accepted commit outputs (V23–V29, translated by Autodesk) carry
`C` computed with header length 12/16, i.e. **4·A larger** than Autodesk's
own convention (`C = payload − 16·A` seq101 / `− 20·A` seq102/103, exact
on every original block; V28 seq101 last block: A=265, stored C=34,574 vs
correct 33,514). They translate anyway ⇒ `A`/`C` are advisory; only `B`
(member length, mirrored in the 0x0f21 trailer) frames the stream.
`reduce.py` writes the correct C regardless. (commit.py `_hdr_len` could
adopt 16/20 for hygiene — orchestrator's call; not my territory.)

### E3. `Global/Latest` (ADocument) references model content directly
i64 scan of the inflated ADocument (1,586,246 B) for host ElementIds
(ids ≥ 4,096 to suppress false positives): **6,175 / 13,936 elements
referenced**, in 8-byte-stride arrays:
- @113,328: 4 FamilyInstance ids (preceded by `9b 5b e1 ff.. 04 00 00 00` = count 4)
- @117,704: 30 FamilyInstance ids (count field 0x1e)
- @149,731: **490 ids** = 432 FamilyInstance + 35 LineLoad + 9 SWall +
  5 Floor + 5 AreaLoad + 4 ContFooting (count field 0x1ea) — i.e. every
  placed structural element `[hypothesis: analytical-model / element-set list]`
- @1,497,153: 11 Grid + 3 FamilyInstance ids (count 0x0e)
ContentDocuments references ≥ 69 host ids in the NAIVE scan (45 GStyleElem
etc., ids < 4,096) but only 1 above the threshold — it points at its own
save units by GUID, not at host elements. **This is the genesis blocker:**
no dangling-free deep reduction without an ADocument re-encoder
(genesis.md §4.4, §6.3).

### E4. Deletion cascade sizes (reference graph over all three seqs)
Graph: 13,936 nodes, 81,066 edges (via `mutate._collect_ids` on decoded
seq101+102+103). Seed = 30 "placed model" classes (1,561 elements).
Dependency closure (survivor references deleted ⇒ delete survivor) ⇒
7,627 deletions: pulls in 4,344 CurveElem, 709 LinearDimString, 229
TextNote, 171 SketchPlane, 140 VarSketch, 62 Viewport, 56 FilledRegion,
37 IndependentTag, 25 Viewer + section/schedule views cutting the model.
Only 21 survivors keep dangling refs (13 CategoryElem, 8 GStyleElem —
category/style objects listing member elements). The zero-dangling safe
sweep of the same seed removes just 31 (30 unreferenced FamilyInstances,
1 StairsPathElement) because Global/Latest references the rest.

### E5. Family documents are renumbered when embedded
Standalone `racbasicsamplefamily-2026.rfa`: unit-0 ids **0..7,674**
(1,992 elements). Embedded family documents in rstbasic (units 1..52):
ids **1,226,444..1,471,978**, host document 1..1,472,524, no overlap ⇒
ids ARE unique file-wide and loading an `.rfa` requires a full ElementId
remap of the family's records. The 2026 `.rfa` shares the identical
`Formats/Latest` (sha256 6459a9a9…) and stream set (+PartAtom,
+RevitPreview); its `Global/ContentDocuments` is 82 raw bytes (empty form)
and `Global/Latest` only 68,508 raw bytes ⇒ **a family file is the
easiest genesis milestone** (genesis.md §5, §6.5).

### E6. Sizes / composition of rstbasic
Partitions/21 logical 5,971,253 B = unit 0 (host doc) 3,905,353 B + 52
embedded family documents 2,055,878 B; Global/Latest 1.59 MB inflated;
ContentDocuments 1.37 MB inflated (52 docs); ElemTable 557,470 B
inflated. R4 (skeleton) = 2,859,008 B: what remains is dominated by the
embedded family units + Latest + ContentDocuments — the reduction floor for
the current engine is set by the streams we do not yet rewrite.

## Gotchas found (for KNOWLEDGE.md merge)

1. **Full-stride final CRCIO block.** A final partial block whose data
   length falls in the full-size class (5,082..64,896 B) encodes to exactly
   one 65,249-byte stride and is indistinguishable from a full page BY
   LENGTH. Hit by R1s (final block = 64,875 data bytes, pad-count field 21).
   The file is CORRECT (pad-count decodes 64,875, re-encode byte-exact);
   any verifier that counts full pages as `len(raw)//65249` false-alarms.
   `reduce.unframe_exact()` implements the reader's rule: only pages
   FOLLOWED by more bytes are full pages; the last ≤stride block always
   decodes its length from the pad-count field (a true full page reads
   pad = 0 ⇒ 64,896 — verified on the source's page 0). **`ecc.unframe_stream`
   and `commit.verify_written`'s ECC loop share this ambiguity** (out of my
   territory — flag for their owners).
2. **History invariant vs deletion.** count(History) == max(modified_ep)+1;
   deleting the element carrying the maximum episode breaks it silently.
   The closure driver protects that element; a real save (record_save)
   should accompany deletion in the product path.
3. **The depage tail is stale ECC junk.** Everything after the end record
   in a `logical()` buffer is the source's final-block parity; both
   commit.py and reduce.py carry ~68 B of it forward and re-encode it
   (harmless — the parser stops at the end record — but a genesis writer
   should terminate the logical stream cleanly after the 14-byte end
   record).
4. **The i64 id scan under-counts references to small ids** (< 4,096:
   categories, styles, materials created first). Protection of those uses
   the class taxonomy (KEEP_ALWAYS), not the scan. An exact ADocument
   decoder retires both heuristics.

## Open questions (need the viewer / next session)
- Does the reader tolerate dangling ElementIds inside ADocument (R1)?
- Is at least one view mandatory (R2)? Are levels mandatory (all stages
  keep them)? Do host Family/FamilySymbol elements have to accompany their
  embedded content documents (R3 keeps units, deletes host symbols)?
- Exact semantics of the 490-element ADocument array (analytical model set?
  regen dirty set?) — decides whether an empty-model project even carries it.
- Legal: `Formats/Latest` + category/style tables are format constants
  every Revit file contains; treating them as interoperability data (not
  content) needs the review already flagged in KNOWLEDGE.

## Proposed next tasks (orchestrator decides)
1. Viewer-test the ladder (above); record the deepest pass in
   `docs/acceptance-log.md`.
2. Stream: **ADocument decoder/encoder** (`Global/Latest`) — the critical
   path for everything deeper than the safe sweep and for genesis.
3. Stream: minimal `.rfa` synthesis (family genesis first — smallest thing
   exercising every encoder incl. an EMPTY ContentDocuments).
4. Stream: ContentDocuments encoder + external `.rfa` loader (id remap).
5. Fold E2 (C counter advisory) and the full-stride-block rule into
   KNOWLEDGE.md; consider correcting commit.py's C for hygiene.

BRANCH STATE: no VCS in repo (plain directory); all work is uncommitted
files at the paths above — src/rvt/reduce.py, tools/rvt_reduce.py,
tests/test_reduce.py, docs/writer/genesis.md, docs/inbox/genesis.md,
experiments/genesis/{R0_identity,R1,R1s,R2,R2s,R3,R3s,R4,R4s}.rvt + .json +
summary.json. Full suite green at handoff (see final report). READY.

# genesis-controls — THE THREE-WAY SEPARATION {ADD PATH vs OBJECT SHAPE vs OUR VALUES} (workstream record, 2026-08-03)

Charter (orchestrator verdicts #9, "the divide is CONSTRUCTED vs CLONED"):
every file whose element records are Autodesk's VERBATIM bytes LOADS in
Autodesk's own reader; EVERY file carrying our FROM-SCRATCH CONSTRUCTED
objects (settings singletons, catalog rows, house content) FAILS with
`Revit-DocumentCorruption` + `Design is empty` + an extractor crash — on the
K1 lineage too (R2 / X5 / R1 / R3 FAIL) and after registry-parity repair.
Build, for ONE class first (the PenWidthTableElem = the ladder's X1 class,
smallest and best understood), THREE controls each derived from K1
(Autodesk's viewer-PASSED empty-project skeleton) by ONE change and each
through the SAME add path the X-rungs use: hold, in turn, the ADD PATH, the
OBJECT SHAPE / header / rep, and OUR VALUES constant.  Then the same three
for ONE built-in object-styles catalog row.

Territory touched ONLY (as chartered): `tools/genesis_controls.py` (new),
`tests/test_genesis_controls.py` (new, 14 pass), `experiments/genesis/
controls/` (X0 X1v X1u C0 C1v C1u + optional C0all X0k X1ua X1ub `.rvt`,
per-probe `.json`, `probes.json`, `findings.json`), this record.  NO
existing `src/rvt/*.py`, tool or test edited — the substitution engine
(`tools/genesis_substitute.py`) and every codec / constructor is IMPORTED.
No browser / viewer use: the files are LEFT ON DISK for the orchestrator's
queue; every branch of the reading tree is written into `probes.json`.

## Result in one screen

**All six controls (+ four optional bisectors) built, EVERY ONE
validator-VALID (0 errors), structurally proven, registry-parity 1/1 (C0all
1348/1348), four-registry coherent, 0 NEW dangling ids — each derived from
K1 by ONE change through the substitution engine's own add path, with the
byte-identity ASSERTIONS in its `.json`.**  Reproduce:
`.venv/bin/python tools/genesis_controls.py --with-optional` (~5 min).

| # | probe | class | records = | ONE change vs its passing sibling | asserted |
|--:|---|---|---|---|---|
| 1 | **X0** | pen table | Autodesk's OWN element 2, re-encoded byte-exactly, new id | element 2 travelled through OUR add path (delete + append + registry re-point + Latest re-encode + re-block) | all 3 seqs byte-identical to K1's at the original id |
| 2 | **X1v** | pen table | OUR constructor fed AUTODESK'S EXACT values (feet) | as X0 — and X1v's records ARE X0's | header + object + rep byte-identical => **X1v == X0 (NO upload)** |
| 3 | **X1u** | pen table | OUR constructor, OUR widths; Autodesk's 6 metric scale keys / 16 pens / flags pinned | the 128 width doubles (vs X1v/X0); the 6 scale KEYS (vs the ladder's X1) | only doubles differ; header byte-identical |
| 4 | **C0** | catalog row 34 (OST_Windows projection) | Autodesk's OWN row, re-encoded byte-exactly, new id | row 34 travelled through OUR add path (CategoryTracking leaf re-pointed) | all 3 seqs byte-identical at the original id |
| 5 | **C1v** | catalog row 34 | OUR new_gstyle fed the row's EXACT values | ONE header flag bit (0x2000): our preset 0x400001e vs the row's 0x400201e | object + rep byte-identical; header xor 0x2000 |
| 6 | **C1u** | catalog row 34 | OUR catalog constructor's LITERAL row (our pen 1 / colour 0x181818) | the two VALUES vs C1v — byte-for-byte the row X6a / R2 shipped | value delta = {m_penNumber, m_color} |
| 7 | *C0all* (opt) | ALL 1,348 referrer-free built-in rows | Autodesk's OWN rows, re-encoded byte-exactly, new ids | the catalog-SCALE version of C0 (R2's population; R2's missing third with R2s) | 1348/1348 rows byte-identical at their original ids |
| 8 | *X0k* (opt) | pen table | Autodesk's element 2 re-inserted AT ITS OWN id | ZERO registry / id motion (Global/Latest byte-identical to K1's); only record position + our ElemTable row differ | Latest == K1's; row (2,1016,1016,1016) vs K1's (2,0,976,976) |
| 9/10 | *X1ua / X1ub* (opt) | pen table | the two halves of the width doubles (96 model / 32 perspective+draft) ours vs Autodesk's | upload only if X1u FAILS | — |

Recommended upload batch (ONE round): **X0, X1u, C0, C1v, C1u + C0all + the
addback stream's un-uploaded R2s.**  X1v needs NO upload (its Partitions /
Latest / ElemTable streams are byte-identical to X0's — `collapse_check`).
X0k / X1ua / X1ub are pre-built follow-ups keyed to specific FAILs.

## The reading tree (also `probes.json:decision_tree`)

* **X0 FAIL** ⇒ OUR ADD PATH ITSELF corrupts a settings singleton — every
  X-rung is void until fixed.  X0.json diffs what our path wrote against
  K1's original registration (ElemTable row (0,976,976)→(ep,ep,ep) with
  original_id = the new id; the three records moved from mid-stream to the
  unit end; id 2 → 1,500,000 leaving a hole at the front of the id space;
  the `PenWidthTableInfo` leaf rewritten to a 1.5M id; the identity scrub).
  **Upload X0k**: X0k PASS ⇒ the new-id / registry-rewrite half; X0k FAIL ⇒
  the record-append / ElemTable-row half.
* **X0 PASS + X1u PASS** ⇒ path fine, our width VALUES fine ⇒ the ONLY
  variable left in the ladder's X1 is the six scale KEYS (our imperial
  24/48/96/192/384/768 in a metric-lineage document vs the specimen's
  10/20/50/100/200/500).  X1 FAIL then names the constraint (a valid
  view-scale set / units consistency — a one-line settings fix); X1 PASS
  retires PenWidthTableElem entirely.
* **X0 PASS + X1u FAIL** ⇒ a width VALUE is audited ⇒ X1ua + X1ub localize
  it to 96 vs 32 doubles.
* **X1v** — no upload (byte-identical twin of X0).  Its value is the
  build-time assertion: our pen-table constructor reproduces Autodesk's
  element COMPLETELY (header + object + rep) given exact values ⇒ shape /
  header / rep are exonerated BY CONSTRUCTION; X1's variables reduce to
  {width values, scale keys}.
* **C0 FAIL** ⇒ the add path corrupts a CATALOG row (with X0: both fail ⇒
  the path generally; only C0 ⇒ the CategoryTracking / high-id-catalog-row
  specifics).  R2 / X6a inherit it.
* **C0 PASS + C1v FAIL** ⇒ THE ELEMENTHEADER FLAG WORD IS AUDITED for
  built-in object-style rows — our catalog constructor's single preset
  (0x400001e, vs SIX presets in the accepted catalog, finding G1) can ALONE
  explain R2 / X6a; since finding G2 shows the presets are per-document not
  per-category, the valid-combination rule is mined from `findings.json`.
* **C0 PASS + C1v PASS + C1u FAIL** ⇒ our object-style VALUES (pen number /
  COLORREF) are audited ⇒ a pen/colour twin pair splits them (seconds).
* **C0 PASS + C1v PASS + C1u PASS** ⇒ the SINGLE-ROW substitution is FULLY
  EXONERATED — path, shape, header preset and values all reader-clean ⇒
  R2's / X6a's failure is a WHOLE-CATALOG effect.  **Upload C0all + R2s**:
  C0all PASS + R2s PASS ⇒ R2's killer is a MULTI-row property of OUR rows
  (our one preset / ink colour across the whole table); C0all FAIL ⇒ the
  add path breaks AT SCALE (mass id motion / mass CategoryTracking rewrite /
  1,348 fresh-episode rows), not per row.
* **ALL SIX PASS** ⇒ the constructed-object divide is NOT per-object for
  either class; it is a MULTI-object / scale / interaction property (X5 =
  51 more classes at once; R2 = 1,348 rows at once) — run the same
  separation cumulatively (C0all first) and per-class trios over X2..X5.

## New format / constructor findings (evidence — merge into KNOWLEDGE.md)

1. **P1 — The pen table's stored doubles are NOT `mm / 304.8` of the
   displayed mm values [V, `findings.json:P1`].**  Feeding the specimen's
   own feet values back through the constructor's mm interface
   (feet × 304.8) reproduces 120 of the 128 doubles but loses the last
   mantissa bit on the eight 9.0-mm pens: Autodesk stores
   `0.029527559055118106` while 9.0/304.8 = `0.02952755905511811`, and **NO
   double m within ±4000 ulps of 9.0 satisfies m/304.8 = the stored value**
   — the mm interface cannot express it (the differing framed-record bytes
   are the stamp + payload offsets 227/235/243/371/379/507/515/651).  The
   17 distinct stored widths derive from at least two different formulas
   (0.1/0.18/5/6/7/10 mm match `mm/304.8`; 0.35/0.7/1.4/2.8/9 match
   `mm×(1/25.4)×(1/12)`; 0.25/0.5/1/2/4/8 match neither) — i.e. the table
   was authored on an inch / doubling basis, not in mm.  Consequence: the
   settings stream's `test_reproduce_pen_width_table_id2` proves a
   SELF-round-trip (encode→decode→encode of OUR value equals itself and the
   float-rounded structure matches), NOT identity with the specimen.
   Reader-relevance: nil (a last-ulp width is not audited) — but "byte-exact
   reproduction" claims must be phrased against the SPECIMEN's bytes.
2. **P2 — For PenWidthTableElem our constructor's {header, object shape,
   rep} are Autodesk-identical [V]**: fed exact feet it reproduces
   element 2's header (abFlags 8222, vis −32768, deletion [self], no
   wildcards / regenOnly), object AND rep (empty SerializedDummy)
   BYTE-IDENTICALLY (X1v.json), so X1v collapses onto X0 and X1's only
   variables vs the accepted specimen are the width VALUES and the scale
   KEYS.  Note the ladder's X1 keys OUR imperial breakpoints (24…768) while
   K1 is metric (10…500) — if X1 FAILs with X0/X1u PASSING, that key set is
   the first suspect.
3. **G1 — Built-in object-style rows do NOT share one ElementHeader flag
   word or cell-list shape [V, `findings.json:G1`, K1's 1,407 rows]**: SIX
   distinct `m_abFlags4Bytes` presets — 0x400081e (645 rows), 0x400200e
   (492), 0x400080e (145), 0x400201e (79), 0x400000e (31), 0x400001e (15)
   — bits 0x10 / 0x800 / 0x2000 vary; and 790 of 1,407 rows carry a
   `CellList{PatternHelper}` (uncorrelated with the line-pattern id: all
   four (cell, pattern −1) combinations occur).  Everything else in the row
   header is universal (m_categroryId −1, vis −32768, empty appearance
   parents, deletion = self + material/pattern element ids).  Our
   `new_gstyle` emits the SINGLE preset 0x400001e and a null cell list ⇒
   fed each row's exact values it reproduces only **15 / 1,407** rows
   completely (object 617 = exactly the null-cell-list rows; header 15).
   R2 / X6a shipped ~1,392 rows deviating from the accepted specimen in
   these fields.
4. **G2 — …but the flag word and cell-list presence are NOT per-category
   FORMAT CONSTANTS [V, `findings.json:G2`]**: across rst / rme / rac the
   same (category, style-type) key carries DIFFERENT presets / cell-list
   states for **916 of the 1,407** keys (e.g. −2000085 projection is
   0x400081e in rst & rac but 0x400201e in rme, with a cell list in rst/rac
   and none in rme).  They are per-document creation-history artefacts;
   EVERY combination is reader-accepted somewhere, and our own combination
   (0x400001e + null cell list) itself occurs in accepted files (K1's
   walls / ceilings rows; other categories in rme).  ⇒ the per-row
   header / cell divergence is a WEAK candidate for R2's failure; C1v
   settles it in one round, and the weight moves onto the catalog-SCALE
   add path (C0all) and the never-uploaded mechanics control R2s.
5. **The add path's exact fingerprint for a re-inserted singleton [V,
   X0/X0k]**: ElemTable row (original_id = new id or self, creation =
   modified = user_modified = the parent's MAX episode — 1016 on K1 — vs
   the specimen's (0, 976, 976)); the three records appended before each
   seq's sentinel (K1's element-2 records sit at seq-102 position 2,516 of
   6,541); watermark raised to the new id; the registry leaf value
   rewritten in place; Global/Latest re-encoded byte-exactly (same length);
   BasicFileInfo / DocumentIncrementTable identity scrubbed (V30–V32
   path).  Every X0-class file comes out at EXACTLY K1's byte size
   (4,489,216) — content-conserving.
6. **A same-id delete-then-re-add cannot go through the substitution
   engine [V]**: its stage-A append + stage-B delete of the SAME id would
   remove both records; X0k therefore drives the two halves directly
   (`rvt.reduce.delete_elements` then `rvt.commit.commit_new_elements`) and
   certifies that Global/Latest stays BYTE-IDENTICAL to K1's (the registry
   still names id 2, present again) — the cleanest possible add-path
   bisector.
7. **1,348 of K1's 1,407 built-in object-style rows have ZERO referrers
   (host or embedded) and exactly ONE registry leaf each
   (`CategoryTracking.m_gstyleData[*].m_gstyleId`) [V]** — the K6/R2/X6a
   population; the other 59 are referenced (K6 kept them).  Decode →
   re-encode is byte-exact for all 1,348 (all three seqs) — C0all's proof.

## Answers to the charter's byte-identity questions

* **Can our pen-table constructor reproduce its specimen byte-exact from
  the specimen's values?**  Through its public (mm) interface: **NO** — 8
  of 128 doubles are unreachable (P1, first differing framed byte = the
  seq-102 stamp at offset 8; first differing payload offset 227).  Fed the
  exact FEET values (structure via the constructor, doubles set to the
  specimen's): **YES, header + object + rep, all three seqs** (P2) — the
  X1v assertion, which makes X1v ≡ X0.
* **Can our GStyle constructor reproduce the chosen catalog row?**  OBJECT
  and REP byte-exactly YES; the HEADER NO — it differs from the row's own
  in exactly ONE flag bit (0x2000: ours 0x400001e vs the row's 0x400201e),
  which is precisely C1v's single variable.  Across the whole catalog our
  constructor is complete on 15 / 1,407 rows (G1) — but G2 shows the field
  is not a format constant, so "complete reproduction" is not the reader's
  bar; the C-trio measures the bar directly.

## Gotchas found (for KNOWLEDGE.md merge)

1. `commit_new_elements` IGNORES the plan's episodes: every appended
   ElemTable row gets `creation_ep = modified_ep = user_modified_ep =
   max(modified_ep of the parent)` and `original_id = elem_id` — a
   re-inserted OLD element does NOT get its original episodes back (X0's
   diff; the addback "restored rows" carry refreshed episodes too).
2. The substitution engine allocates each rung's ids from a FRESH context
   (`IdSource(watermark→100k band)`), so every single-record control lands
   on the SAME new id (1,500,000 on K1) — probes are comparable id-for-id
   with the ladder's X1.
3. `record_bytes` lives in `rvt.encode` (not `rvt.objects`);
   `Record.payload` is the object bytes with the u16 class stripped, so
   `dec.decode_record(class_id, payload)` is the decode call and
   `encode_record(seq, id, None, class_id, value)` re-frames it — the
   proven byte-exact round trip that makes the "verbatim" probes honest.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/genesis/settings.py` (genesis-singletons owner)** —
  `pen_width_table`: (a) accept `*_pens_ft` (feet) arguments alongside the
  mm ones so an exact-value reproduction / a units-consistent author path
  exists without post-patching (P1); (b) reconsider `PEN_SCALE_BREAKPOINTS
  = [24,48,96,192,384,768]` (imperial architectural denominators) — a
  metric-lineage document keys 10/20/50/100/200/500; make the breakpoint
  ladder follow the document's unit lineage (X1u vs X1 isolates exactly
  this).  Also `test_reproduce_pen_width_table_id2` should compare ENCODED
  BYTES to the specimen's framed record (it currently proves a self-round-
  trip; P1).
* **`src/rvt/genesis/types.py::new_gstyle` / `catalog.py`** (only if C1v
  FAILS): add per-row `ab_flags` / `cell_list` parameters and a
  valid-combination table for the built-in object-style header presets
  (the six observed words + the PatternHelper cell) — the census in
  `findings.json:G1` is the source; G2 says do NOT hard-code per category.
* **`tools/genesis_addback.py` (genesis-addback)** — R2's verdict was
  read as attributable to our rows because "R2s reproduces K1"; R2s was
  NEVER uploaded and is not byte-identical to K1 (restored rows carry
  refreshed episodes and unit-end positions — the same fingerprint as X0's).
  Upload R2s with C0all: only R2s PASS + C0all PASS makes R2's failure OUR
  ROWS.
* **`src/rvt/validate.py` (validation)** — nothing new; every control is
  VALID by construction.  (The consistency rules the reader enforces remain
  the addback stream's parity list; this stream's byte-identity harness
  `byte_compare` / `verbatim_typerecord` is reusable for any "is our
  constructor's output the specimen's bytes?" gate.)
* **`tools/sync_plugin.py`** — this stream adds `tools/genesis_controls.py`
  only (no `src/` module) — nothing new for the plugin bundle.
* **KNOWLEDGE.md owner** — merge findings 1–7 and gotchas 1–3.

## Open questions (need the viewer / a decision)

* The verdicts, read per the tree above: **X0, X1u, C0, C1v, C1u (+ C0all,
  R2s)** in one batch.  X1v is settled without upload.
* Whether X1's imperial scale-key ladder in a metric-lineage file is the
  ladder's first pen-table defect — decided by X1's verdict against X0 +
  X1u (all three of ours PASS-clean by construction; only the viewer can
  say).
* If C0/C1v/C1u all PASS while R2 stays FAILED: the catalog killer is a
  MULTI-row property — the census (G1) offers two whole-table hypotheses
  to bisect next: our SINGLE header preset across all 1,348 rows (a
  distribution the reader may audit even though each value alone is
  legal), and our INK colour 0x181818 / pen numbers on 1,300+ rows.  A
  "C1v-all" (all rows via our constructor fed exact values + presets +
  cells patched to each row's own) is buildable from this stream's parts.

## Proposed next tasks (orchestrator decides)

1. Upload the batch; read per the tree.  Every branch is pre-built or
   named with its builder (`tools/genesis_controls.py --only …`).
2. If X0 PASS: retire "the add path" as a suspect for singletons in every
   genesis stream (record in KNOWLEDGE.md); if C0 + C0all PASS: same for
   catalog rows at scale.
3. Fold `byte_compare` + `verbatim_typerecord` (the "is our output the
   specimen's bytes?" harness) into the constructor test tiers of the
   settings / types / catalog streams — every constructor that claims
   reproduction should assert BYTES, per P1.
4. Run the same trio for the NEXT X-ladder classes (X2..X5's 60-odd
   singletons) — the tool is table-driven: one `SpecRecord` element + one
   constructor call per class; the singleton classes with a UET positional
   slot exercise the one registry surface these two classes do not.

## Verification

* `tools/rvt_validate.py` on all ten emitted files → VALID 0 errors (the
  engine's certification, in each `.json:validator`); per-file: structural
  proof clean, registry parity 100 % (C0all 1348/1348 pairs), 0 old ids
  left in the document object, **0 NEW dangling ids**, four-registry
  coherence 53/52/52 (K1's), 0 referrers to re-point (the classes were
  chosen referrer-free), 0 embedded-document referrers.
* `.venv/bin/python -m pytest tests/test_genesis_controls.py -q` → **14
  passed** (33 s): the specimen elements are the documented ones; Autodesk's
  own records re-encode byte-exactly (X0/C0's premise); the identity rebase
  touches only `m_id` + the own `m_deletion` entry; the P2 assertion
  (constructor fed exact feet reproduces all 3 seqs); the P1 finding pinned
  (naive mm feed differs in 11 bytes / 8 doubles, stored double unreachable
  from any mm); the G1 anchor rows (row 30 complete, row 34 object-only,
  header xor 0x2000); C1u vs C1v = exactly {pen, colour}; X1u differs from
  the specimen only in doubles; the two classes' zero referrers / one leaf;
  the manifest order + tree; every built control certified VALID and
  parity-clean; X1v ≡ X0 at the stream level; one END-TO-END C1v build.
* Full suite: see BRANCH STATE.

## Reproduction (repo root, .venv python)

```
python tools/genesis_controls.py                     # X0 X1v X1u C0 C1v C1u + findings + manifest (~4 min)
python tools/genesis_controls.py --with-optional     # + C0all X0k X1ua X1ub (~7 min)
python tools/genesis_controls.py --only C1v          # any subset
python tools/genesis_controls.py --findings-only     # the P1 / G1 / G2 census -> findings.json
python tools/genesis_controls.py --manifest-only     # re-write probes.json from the reports on disk
python tools/rvt_validate.py --quiet experiments/genesis/controls/*.rvt      # OK errors=0 (x10)
python -m pytest tests/test_genesis_controls.py -q   # 14 passed
```

Arbiter output (this session, from the engine's certification):

```
X0     VALID  errors=0 warnings=1  parity 1/1     new dangling 0
X1v    VALID  errors=0 warnings=1  parity 1/1     new dangling 0   (== X0, no upload)
X1u    VALID  errors=0 warnings=1  parity 1/1     new dangling 0
C0     VALID  errors=0 warnings=1  parity 1/1     new dangling 0
C1v    VALID  errors=0 warnings=1  parity 1/1     new dangling 0
C1u    VALID  errors=0 warnings=1  parity 1/1     new dangling 0
C0all  VALID  errors=0 warnings=1  parity 1348/1348 new dangling 0
X0k    VALID  errors=0 warnings=1  Global/Latest byte-identical to K1's
X1ua   VALID  errors=0 warnings=1
X1ub   VALID  errors=0 warnings=1
```
The one warning is K1's own pre-existing extensible-storage decode gap
(6 RebarShape + 1 DataStorage residue), present on the pristine sample and
on K1 itself — untouched by any control.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files:
`tools/genesis_controls.py`, `tests/test_genesis_controls.py` (14 pass),
`docs/inbox/genesis-controls.md` (this file), and under `experiments/
genesis/controls/`: `X0 X1v X1u C0 C1v C1u C0all X0k X1ua X1ub .rvt` + one
`.json` certification report each + `probes.json` (the ordered manifest +
full decision tree) + `findings.json` (P1 pen-double analysis, G1 catalog
header/cell census on K1, G2 cross-sample non-constancy).  Every emitted
`.rvt` = validator VALID (0 errors), structural proof clean, registry
parity 100 %, four-registry coherent, 0 NEW dangling ids, with its
byte-identity assertions recorded.  Full suite this session
(`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`): **805
passed, 3 failed** of 808 (924 s).  This stream's 14 tests are among the
805.  The 3 failures are the pre-existing, other-stream ones every recent
record lists, none touching this stream's files: `tests/test_plugin_sync.py
::test_plugin_is_in_sync_with_source` (the plugin-bundle drift; this stream
adds NO `src/` module, so nothing new to sync — fix remains the
orchestrator's `python tools/sync_plugin.py` run) and `tests/
test_provenance.py::{test_G0_resource_refs_are_counted, test_G0_identity_
dit_usernames_still_leak}` (the STALE assertions pinning the pre-genesis-2
G0 defects; their owner's diff is in docs/inbox/genesis-2.md).  STOPPED AT
READY — the ten files await the orchestrator's viewer gate; the recommended
one-round batch is X0, X1u, C0, C1v, C1u + C0all + the addback stream's
un-uploaded R2s.

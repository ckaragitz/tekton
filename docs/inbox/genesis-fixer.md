# genesis-fixer — THE FIXER + RE-EMITTER: the pen table and the object-styles catalog, field-diffed against every specimen, corrected, and re-emitted (workstream record, 2026-08-03/04)

Charter (orchestrator verdict #9, "the divide is CONSTRUCTED vs CLONED"):
every file carrying our FROM-SCRATCH constructed objects FAILS
(`Revit-DocumentCorruption` + `Design is empty` + extractor crash) while
every clone/verbatim file LOADS — even on the K1 lineage (R2 / X5 / R1 / R3
FAIL) with mechanics controls (R2s == K1) and registry-parity repair.  This
stream reproduces the linter's method BY HAND on the two convicted classes
(the project **PenWidthTableElem** — X1's class — and the built-in
**GStyleElem** object-styles catalog — X6a / R2 / K6's class), diffs OUR
constructors' output FIELD BY FIELD against EVERY specimen in all six
samples, FIXES every mis-shaped field in `src/rvt/genesis/settings.py` +
`src/rvt/genesis/catalog.py` (the singletons stream's modules, now this
stream's), adds a test per fixed class, RE-EMITS the settings + catalog
rungs (X1..X5, X10, X6a) into `experiments/genesis/subst_v2/`, and builds
the two belt-and-braces IN-PLACE PAYLOAD PROBES **X_pen** and **X_cat**.

Territory touched ONLY (as chartered): `src/rvt/genesis/settings.py`,
`src/rvt/genesis/catalog.py`, `tests/test_genesis_settings.py` (extended,
45 -> 61 tests), `experiments/genesis/subst_v2/*` (build_v2.py driver, the
frozen `builtin_style_profile.json`, X_pen / X_pen_obj / X_cat / X_cat_obj
+ X1 X2 X3 X4 X5 X10 X6a `.rvt` + per-file `.json` + `probes.json`), this
record.  NO other `src/rvt/*.py`, tool or test edited; the substitution
engine (`tools/genesis_substitute.py`), the manipulate / commit / codec
layers and `rvt.objlint` (the linter stream's, landed mid-session) are
IMPORTED.  No browser / viewer use: the eleven files are LEFT ON DISK for
the orchestrator's queue with a manifest ordered by information value.

## Result in one screen

* **THE FIELD DIFF (done FIRST, by hand, before any fix)** — 3,494
  PenWidthTableElem specimens and 8,442 built-in host GStyleElem rows
  decoded across all six samples and diffed against our constructors'
  output (§Findings).  Verdict on OUR output: the SHAPE is specimen-exact
  (same 24 top-level keys, same pointer classes / null-ness / container
  shapes, header category −1 like all 8,442 specimens, deletion rule
  respected, seq-103 SerializedDummy like every specimen) — but **the
  VALUES / per-key STRUCTURE violate specimen invariants: 1 field family in
  the pen table (the model scale KEY SET) and 6 field families in the
  catalog (2,560 fields), all keyed by (category, style-type) — invisible
  to a class-pooled linter, which is why `rvt.objlint` (landed 23:49) lists
  NOTHING for GStyleElem and, on the pen table, exactly the scale ENUM
  plus two ADD-PATH (ElemTable) rules.**  The two instruments converge.
* **FIXED**: `settings.pen_width_table` now emits the six-sample format
  constant scale set **[10, 20, 50, 100, 200, 500]** (was 24…768; **768 is
  in ZERO of 3,494 specimens**), widths stay OUR ISO-128 series (inside the
  corpus width range); a direct-FEET argument path was added (the exact-
  value probe path — reproduces rst id 2's OBJECT BYTES identically, a
  test).  `catalog.builtin_style_catalog` is now SHAPED per (category,
  type) by the frozen **structural PROFILE** (`experiments/genesis/subst_v2/
  builtin_style_profile.json`, derived by `catalog.derive_builtin_style_
  profile` over 8,442 rows): the ElementHeader flag word (its LOW BYTE is
  a per-CATEGORY compiled-in property — 679 keys 0x0E / 728 keys 0x1E,
  55 mixed), 380 pattern-NULL cells, 40 pen-NULL cells, 48 always-screen-
  sized keys, 32 built-in material ids, 192 document-WIRED keys (pattern /
  material referencing a document element — the rung passes the parent's
  own).  Colours and pen VALUES stay ours.  **The fixer's specimen lint
  reads 0 hard findings on both fixed constructors (pre-fixer catalog:
  2,560 hard findings — 1,345 rows carried a flag word outside their key's
  observed set outright); `rvt.objlint.lint_object` reads 0 findings on
  both (object + header + rep scope).**
* **RE-EMITTED (11 files, EVERY ONE validator-VALID 0 errors,
  `experiments/genesis/subst_v2/`)**: the four **in-place payload probes**
  X_pen / X_cat (+ object-only twins X_pen_obj / X_cat_obj) = K1 with the
  EXISTING elements' records REPLACED IN PLACE by ours built AT THE SAME
  IDS (certified modify path; Global/Latest and every non-partition stream
  byte-identical to K1's; ElemTable untouched) — the ADD PATH removed
  entirely, so a FAIL convicts our OBJECT PAYLOAD alone; and the **v2
  ladder rungs X1 X2 X3 X4 X5 X10 X6a** re-derived with the fixed
  constructors through the substitution engine (parity 100 %, 0 new
  dangling; X6a v2 wires the strict 'elem' keys to the parent's own
  pattern / material elements).  Reproduce:
  `.venv/bin/python experiments/genesis/subst_v2/build_v2.py` (~3.5 min).
* **Tests**: `tests/test_genesis_settings.py` 45 → **61 passing** (the
  fixer's tier: scale-set constant + pen lint clean/bites; profile frozen
  & shaped; catalog lint clean / bites on the pre-fixer shape (>2000
  hard); wiring + id_map; the profile's STRICT rules hold on rstbasic's own
  1,407 rows; the six-sample scale set on rst + rme; the four v2 files
  validate; manifest consistency; `rvt.objlint` 0 findings on both fixed
  outputs and biting on the pre-fixer pen table; the feet path reproduces
  the specimen's object bytes).  Full suite: see BRANCH STATE.

## THE FINDINGS — the linter's method by hand (`experiments/genesis/subst_v2/analysis/{census_pen_gstyle,pen_deep,gstyle_deep,gstyle_flags}.py` + their JSON dumps)

Method: decode every specimen (seq-101 header + seq-102 object; seq-103
class; ElemTable row) of the two classes in all six samples; flatten to
leaf paths; profile per path (kinds / value sets / list lengths / pointer
classes / null rate); diff OUR record path by path; then KEY the catalog
by (category id, style type) and re-profile per key.  Corpus:
**PenWidthTableElem 3,494** (6 project tables m_famId −1 + 3,488
family-scoped) and **GStyleElem 154,528** file-wide (**8,442 = the six
files' 1,407-row built-in host tables**, our catalog's population).

### F1  PenWidthTableElem — one field family, plus two ADD-PATH properties

| # | field | OURS (pre-fixer) | specimens (all six project tables) | class | fixed |
|--:|---|---|---|---|:--:|
| P1 | `m_pPenWidthTable->PenWidthTable.m_modelPenInfo[].m_invertedScale` (the model scale KEY SET) | {24, 48, 96, 192, 384, 768} | **{10, 20, 50, 100, 200, 500} in all six project tables** and 2,610 / 3,488 family tables ({12…384} in 859 curtain-family tables, 5 tables {1,10,100}, 14 seven-column tables); **768 occurs in 0 / 3,494**; the same set in imperial rme / rac ⇒ NOT a unit-lineage choice, a per-release DEFAULT constant | ENUM / format constant | **YES** |
| — | `…m_pens[16]` (widths, mm) | 0.13 … 8.0 (ISO 128), monotone, 16 per vector | project tables 0.053 … 10.0 (corpus 0.025 … 200), monotone, 16, duplicates allowed | value (ours, in range) | — |
| — | top-level keys, `m_famId`, `m_cellList`, persp/draft `m_invertedScale −1`, header (ab 8222 / vis −32768 / cat −1 / fam −1 / deletion [self]), seq-103 SerializedDummy | identical shape (5/6 project headers byte-value equal; racbasic differs only by its 0x800 cell-list era bit + a present CellList) | — | shape | ✓ conformant |
| A1 | `ElemTable` creation episode | our commit path stamps the parent's MAX episode | **birth episode 0** on all six project pen tables (`ETR.created_at_birth` = TRUE, objlint) | ADD PATH (ElemTable), not a constructor field | held by X_pen (in place); proposed diff below |
| A2 | element id band | our allocator's high band (≥ 1.5 M) | **id < 5,000** in all six (id 2 / 3 / 11) (`ETR.id_band`, objlint) | ADD PATH (id allocation) | held by X_pen; proposed diff |

P1 is the ONLY object-field defect; the constructor's structure was
already proven byte-exact (feed the specimen's values → the object) — the
controls stream's P2 re-proves it (X1v ≡ X0).  A1/A2 are why an in-place
X_pen is the only pen-table probe that can hold EVERY mined invariant.

### F2  GStyleElem (built-in object-styles rows) — six per-KEY field families

Class-POOLED, our rows sit inside every value set except the (arbitrary)
colour: gstyleType 1/2, ownerId / famId / designOption / assocLevel −1,
docAccess weak 1, all param sets null, no geometry, header categroryId
−1 (all 8,442), familyId −1, deletion = self (+ document pattern /
material only), pens 0..8, patterns {−1, −3000010, −300001x, doc elems},
materials {−1, −40000xx, doc elems} — which is exactly why `rvt.objlint`
(class / cohort pooled) finds NOTHING here.  KEYED by (category, type)
the picture inverts: each key has a STRUCTURAL profile every one of the
six files agrees on, and our uniform-shape rows broke it on 2,560 fields:

| # | field | rule (per key, six files) | OURS (pre-fixer) | keys affected | fixed |
|--:|---|---|---|--:|:--:|
| G1 | `HDR.m_abFlags4Bytes` LOW BYTE | **constant per key** (1,352/1,407): 0x0E for 679 keys, 0x1E for 728, 55 mixed; the ERA bits (0x2000 / 0x800) are per-DOCUMENT artefacts (0x800 ⟺ a CellList is present, 1,706 rows) | uniform 0x…1E (the types-stream preset 0x400001e) ⇒ the whole flag word outside the key's observed set for **1,345 rows**, the low byte wrong for 679 | 679 low-byte / 1,345 word | **YES** (modal per-key word, cell-list bit cleared) |
| G2 | `m_pGStyle->GStyle.m_linePatternId` | **380 keys carry −1 (NO pattern cell) in every file**; 30 keys always one specific non-solid BUILT-IN pattern (−3000012 hidden ×14, −3000020, −3000016, −3000013/14, −3000050/51); 165 keys always a DOCUMENT pattern element; 6 mixed null/element; the rest solid-family | uniform solid −3000010 | 416 | **YES** ('null' / 'builtin:<id>' / 'elem' → parent-wired / 'nullwire' / 'solid') |
| G3 | `…GStyle.m_penNumber` | **40 keys carry pen 0 or −1 (NO pen) in every file**; else 1..8 | our discipline pens 1..5 everywhere | 40 | **YES** ('null0' / 'nullneg1' / ours) |
| G4 | `…GStyle.m_isScreenSized` | **48 keys TRUE in every file, 0 keys mixed** (the analytical categories) | uniform False | 48 | **YES** |
| G5 | `…GStyle.m_materialElemId` | 1,264 keys −1 always; **32 keys always a BUILT-IN material id** (−4000010 ×19 keys, −4000031…−4000052); 27 keys always a DOCUMENT material element; 84 mixed (null in-set) | uniform −1 | 59 | **YES** ('null' / 'builtin:<id>' / 'elem' → parent-wired / 'nullwire') |
| G6 | header cell-list era bit 0x800 / `m_cellList` | 0x800 ⟺ CellList{PatternHelper} present (rst / rac era only); we emit no CellList ⇒ the bit must be CLEAR | preset had it clear | — | ✓ asserted |
| — | colour `m_color` | arbitrary COLORREF (87 distinct incl. user values) | our discipline scheme / INK 0x181818 (not in any specimen) | — | KEPT (ours; the value-bearing field) |
| — | id / ElemTable band + vintage | built-in style rows: `ETR.created_at_birth` and `id_band` are ENUM (both values observed) — NOT strict for this class | our high band, current episode | — | in-set (and X_cat holds K1's own rows anyway) |

Reading G1 with the controls stream's G2: their census shows the FLAG
WORD's ERA bits differ per document for 916 keys (a "weak candidate");
the SIX presets they list are the two low bytes × the era bits.  What the
per-key census adds is that the LOW BYTE (bit 0x10) does NOT vary across
the six files for a given key — a per-CATEGORY compiled-in property our
single preset got wrong for ~half the enum.  Both hold; the profile keeps
the low byte per key and clears the cell-list era bit we cannot honour.

### F3  What the diff EXONERATED (measured, in-shape)

Everything else in both records: the GStyle sub-object key set and
pointer class, the 24-key object shape, every base-Element sentinel, the
seq-101 header shape (parents lists all empty, classDef, regenHistory,
bbox null, vis −32768, familyId −1, categroryId −1), the deletion-set
rule, the seq-103 SerializedDummy, our pens (in range) and — up to the
counsel question — our colours.  T_conduit_types (our from-scratch conduit
/ wire types, viewer PASS) already proved the SHARED construction
machinery (`blank_object` + `element_defaults` + `element_header` +
record framing) is accepted; the defect had to be class-specific values /
per-key structure — which is what F1/F2 name.

## THE FIXES (`src/rvt/genesis/settings.py` + `catalog.py`)

**settings.py — the pen table.**  `PEN_SCALE_BREAKPOINTS = [10, 20,
50, 100, 200, 500]` (+ `PEN_SCALE_SET`), documented as the per-release
format constant it is (the Line Weights dialog's fixed model columns);
our ISO-128 width vectors and the coarser-scale shift rule are unchanged
(theirs by value, ours by expression).  New: `PEN_WIDTH_MM_RANGE` /
`PEN_WIDTH_MM_PROJECT_RANGE` (the corpus width envelope);
`lint_pen_width_table(rec)` = the pen-table specimen invariants (scale
set exact & ascending, 16 monotone pens per vector inside the corpus
range, persp / draft scale −1, m_famId −1, no CellList, header cat / fam
−1, low flag byte 0x1E, cell-list bit clear); the direct-feet arguments
`model_pens_ft / perspective_pens_ft / annotation_pens_ft` (the exact-
value path — fed rst id 2's stored feet, the OBJECT re-encodes to the
specimen's BYTES; the controls stream's P1 request, on the module this
stream now owns).

**catalog.py — the object-styles table.**
`derive_builtin_style_profile()` (the six-sample derivation, sharing the
module's ONE `Document.load` with the enum derivation) →
`builtin_style_profile.json` (per key: modal flag word with the cell-list
bit cleared + the observed set, vis flags, pattern rule + built-in id set,
material rule + built-in id set, screen-sized flag, pen rule + observed
range; STRUCTURE ONLY — no colour recorded, a test asserts it);
`load_builtin_style_profile()`; `builtin_style_catalog(…, profile=,
use_profile=True, wiring={(cat,type): {'material_id','line_pattern_id'}},
id_map={(cat,type): elem_id})` applies the profile per row (STRICT rules
'null' / 'builtin:<id>' / 'elem' hold everywhere; 'elem' keys take the
caller's document WIRING — the rung passes the parent's own reference, our
object / the document's wiring — else fall back with a soft note;
'nullwire' / 'solid' keys keep OUR default; `id_map` pins rows to EXISTING
ids for the in-place probe; `use_profile=False` reproduces the pre-fixer
shape for A/B); `lint_builtin_style_catalog(records, standalone=)` = the
per-key specimen lint (hard = format-constant violations, soft = the two
document-wiring inputs left at their standalone default).  Rule taxonomy
after one refinement caught by the tests (a mixed {null, element} key must
NOT get the strict 'null' label): pattern {null 380, solid 827, elem 165,
nullwire 6, builtin:<7 ids> 30}; material {null 1,264, nullwire 84, elem
27, builtin:<13 ids> 32}; screen-sized 48; pen-null 40; low bytes {0x0E
679, 0x1E 728}.

Post-fix, on the DEFAULT constructor outputs: pen lint **0 hard**;
catalog lint **0 hard / 192 soft** (165 pattern + 27 material document-
wiring inputs — resolved to **0** on the K1 lineage where the parent's
elements exist; the rung and X_cat pass the wiring); catalog round-trip
1,407/1,407 clean + byte-exact; `rvt.objlint.lint_object` (the linter
stream's mined invariants, object + header + rep scope) **0 findings** on
both — and it flags the pre-fixer pen table's scale set (ENUM), proving
the two instruments agree.  All 45 pre-existing settings tests still pass
(the reproduction tier is untouched — the fixes change DEFAULTS and add
options, never the proven layouts).

## THE RE-EMIT (`experiments/genesis/subst_v2/`, `build_v2.py`)

Eleven files, every one `tools/rvt_validate.py` VALID (0 errors; the 1
warning on K1-lineage files is K1's own pre-existing ES decode gap).

### Why the belt-and-braces probes are IN PLACE (the R2 confound)

R2 / X6a / K6 convicted "our catalog rows" only WEAKLY: every X/R rung
substitutes our records at NEW ids (delete old + append ours + re-point +
Latest re-encode).  R2 (K6 + our 1,348 rows) therefore ALSO carried (a) our
commit path's ElemTable rows / fresh episodes / high ids and (b) ~1,400
references from INSIDE the embedded family documents to the deleted OLD
catalog ids left DANGLING (the ladder measured 1,421 such uneditable edges
on the X5 base and derives its own X6a AFTER the document removal for
exactly that reason; the parity audit never checks document internals;
and the controls record notes R2s — R2's mechanics control — was never
uploaded and is not byte-identical to K1).  An in-place probe kills every
one of those variables:

| probe | file | ONE change vs K1 (viewer PASS) | held constant BY CONSTRUCTION | attributes |
|---|---|---|---|---|
| **X_cat** | `X_cat.rvt` | K1's **1,407** built-in object-style rows' seq-101 + seq-102 records REPLACED IN PLACE by OUR profiled rows built AT THE SAME IDS (2,814 records; strict 'elem' keys wired to the SAME elements the old rows referenced) | ids, ElemTable (rows / vintage / band), CategoryTracking + every registry (`Global/Latest` byte-identical to K1's), every embedded document, all 10 non-partition streams | OUR CATALOG OBJECT PAYLOAD alone (R2 / X6a / K6 attributed in one file) |
| **X_pen** | `X_pen.rvt` | K1's element **2** (project pen table) header + object replaced in place by OUR pen table built at id 2 (the P1-fixed scale set, our widths) | the same; the row keeps id 2 / birth episode (holds A1 / A2 too) | OUR PEN-TABLE PAYLOAD alone |
| X_cat_obj | `X_cat_obj.rvt` | as X_cat, seq-102 OBJECTS only (K1's own ElementHeaders kept; the 790 rows whose kept header carries the cell-list era bit 0x800 also keep K1's own `CellList{PatternHelper}` so header ⟺ cell stay consistent — body VALUES ours) | + the header word | header vs body (follow-up to an X_cat FAIL) |
| X_pen_obj | `X_pen_obj.rvt` | as X_pen, object only | + the header | follow-up to an X_pen FAIL |

Mechanics: `rvt.manipulate.EditSession` (working copy → overwrite with our
object → `replacement()` re-encoded byte-exactly with a recomputed stamp)
→ `commit_plans` (the viewer-certified M3 / M4 modify path).  Certified per
file: **0 rows skipped** (every original K1 record was byte-exact
editable), validator VALID 0 errors, the target ids re-decode CLEAN and
EQUAL our records (1,407/1,407, 1/1), ElemTable count unchanged (6,540),
**Global/Latest and all 10 non-partition streams byte-identical to
K1's**, watermark unchanged.  X_pen ≙ the controls' X0k (theirs re-inserts
AUTODESK's element 2 at id 2 = the add-path bisector; mine puts OUR object
at id 2 = the payload bisector) — together with X0 / X1u / C0 / C1v /
C1u / C0all the {ADD PATH × PAYLOAD × VALUES} matrix is complete (§Reading).

### The v2 ladder rungs (the add-path route, cumulative)

`X1 X2 X3 X4 X5 X10 X6a` re-derived by the substitution engine from K1 with
the fixed constructors (X1 = the fixed pen table; X6a v2 = the profiled
catalog + parent wiring; X2..X5 / X10 unchanged constructors rebuilt on the
new X1).  Each: validator VALID 0 errors, structural proof, registry
parity 100 % (X6a 1407/1407), 0 old ids left, 0 NEW dangling, four-registry
coherent; X6a's build notes carry the catalog lint (hard 0 / soft 0 — the
parent wiring resolved every 'elem' key).  These stay informative for the
LADDER's continuity, but the payload probes read first.

### Reading the verdicts (also `probes.json:reading_the_results`; upload order = information value)

**Upload X_cat + X_pen first; the *_obj twins and the rungs are keyed follow-ups.**

* **X_cat PASS + X_pen PASS** ⇒ both convicted CONSTRUCTORS are reader-
  accepted objects.  With the controls' X0 (their pen table through OUR
  add path): X0 PASS ⇒ everything about a single-object substitution is
  clean ⇒ the constructed-base defect is a MULTI-object / scale property
  (the controls' C0all: all 1,348 Autodesk rows through the add path) or
  lives in a class this pair does not cover (X2..X5's 60 singletons — run
  the same in-place trio there next).  X0 FAIL ⇒ the ADD PATH is the killer
  for singletons (X0k bisects it); either way our two constructors are
  RETIRED from the suspect list, and the base of record should mint these
  two classes IN PLACE / at low ids (A1 / A2, §Diffs).
* **X_cat FAIL** ⇒ our catalog OBJECTS are rejected even after the six
  per-key repairs — the residual is a VALUE the reader audits (our INK
  colour 0x181818 / pen distribution — the controls' C1u tests exactly
  {pen, colour} on one row) or an unmeasured field: read the card message;
  upload **X_cat_obj** (K1's own headers): X_cat_obj PASS ⇒ our profiled
  flag word is STILL the defect (mine the six-preset table with the
  controls' `findings.json:G1`, era bits included); X_cat_obj FAIL ⇒ the
  object BODY (bisect by profile class: null-pattern / screen-sized /
  built-in-material keys — buildable in seconds via `id_map` subsets).
* **X_pen FAIL** ⇒ upload **X_pen_obj**; PASS ⇒ our ElementHeader for
  the pen table; FAIL ⇒ the object BODY — since the layout reproduces the
  specimen byte-exact given exact values (the feet-path test / the
  controls' X1v ≡ X0), the residual is a WIDTH-VALUE constraint (the
  controls' X1u / X1ua / X1ub localize it).
* **X_pen PASS + X1 (v2 rung) FAIL** ⇒ the pen table's ADD-PATH properties
  are audited (A1 birth episode / A2 id band, or X0's registry-rewrite
  fingerprint) ⇒ the substitution engine must reuse the old id / birth
  episode for the pen table (a proposed diff below), not our object.
* **X6a (v2) FAIL with X_cat PASS** ⇒ same reading for the catalog: the
  1,407-row substitution's add path (fresh episodes / high ids / mass
  CategoryTracking rewrite — the controls' C0all axis), not our rows.
* Every earlier rung's `if_PASS` / `if_FAIL` is carried in its `.json` and
  in the manifest verbatim from the substitution engine.

## New format / method findings (evidence — merge into KNOWLEDGE.md)

1. **The project pen table's model scale set is a per-release DEFAULT
   constant [V, six-sample census]**: {10, 20, 50, 100, 200, 500} on the
   `m_famId −1` table of every 2026 sample INCLUDING the imperial rme /
   rac projects; 768 (1/64" imperial) appears in 0 / 3,494 corpus pen
   tables; curtain-family tables carry {12, 24, 48, 96, 192, 384}.  Users
   may add / remove columns (14 seven-column and 5 three-column tables
   exist), but the default project table is the metric-looking six.
2. **The LOW BYTE of a built-in GStyle row's `m_abFlags4Bytes` (bit
   0x10) is a per-(category, type) compiled-in property [V, 8,442 rows]**:
   constant across all six files for 1,352 / 1,407 keys (0x0E ×679, 0x1E
   ×728, 55 mixed, mostly the −2008103…110 band); the ERA bits (0x2000 =
   "born early", 0x800 ⟺ carries a CellList{PatternHelper}) vary per
   DOCUMENT (the controls' G2) — so the valid word for OUR row is (the
   key's modal word) & ~0x800.  Every built-in style row also carries
   0x4000000.
3. **The object-styles table is per-key SHAPED, not uniform [V]**: 380
   (category, type) keys have NO line-pattern cell (−1 in every file); 30
   always one specific NON-solid BUILT-IN pattern (the built-in pattern
   ids −3000012 / −3000013 / −3000014 / −3000016 / −3000020 / −3000050 /
   −3000051 exist beside −3000010 solid — first sighting of a built-in
   line-pattern id RANGE); 165 always a document pattern element; 40 have
   NO pen (0 / −1); 48 are always screen-sized (the analytical set — the
   288 green screen-sized rows corpus-wide); 32 always carry a BUILT-IN
   MATERIAL id (−4000010 ×19 keys and −4000031…−4000052 — first sighting
   of a built-in MATERIAL id range, the analogue of built-in patterns);
   27 always a document material.  A complete catalog must reproduce
   this shape per key or ~2,500 fields sit outside their observed sets.
4. **Class-pooled invariant mining CANNOT see per-key structure [V,
   method]**: `rvt.objlint` (class + cohort pooled, incl. a
   `GStyleElem|builtin` cohort) reports ZERO findings on our catalog rows
   even pre-fixer, because −1 patterns, pen 0, both screen-sized values
   and both flag low bytes are all "observed" in the pool.  Any catalog /
   table-like class needs a KEYED profile (this stream's method) beside
   the pooled linter; the two are complementary and agree where they
   overlap (the pen scale ENUM).
5. **Every original K1 built-in style / pen-table record is byte-exact
   editable by the certified modify path [V, 2,822 in-place record
   replacements, 0 refusals]** — in-place substitution at existing ids is
   a general genesis primitive: OUR object payload with the document's own
   ids, ElemTable rows, vintage and registrations, and NO re-pointing
   (the embedded-document pinning that forced X10 before X6a simply
   vanishes: nothing moves).  It is also the cheapest possible attribution
   experiment (K1 → probe in ~4 s).
6. **The R2 attribution had a confound the parity audit could not see
   [inference from V]**: substituting the catalog at NEW ids on a base
   WITH embedded documents (K6) leaves the documents' ~1,400 internal
   style references dangling (uneditable); the substitution ladder
   measured 1,421 such edges and ordered X10 (document removal) before
   X6a for that reason — R2 skipped that ordering.  Read R2 as "our rows
   OR the mass add path OR document-internal dangling", not "our rows".

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`tools/genesis_substitute.py` (genesis-substitute owner)** — (a) the
  pen-table rung (X1) and the catalog rung (X6a) should substitute IN PLACE
  at the existing ids (this stream's `_replace_element` /
  `EditSession.replacement` path, or `id_map` for the catalog): it holds
  the two ADD-PATH invariants objlint mined for the project pen table
  (birth-episode ElemTable row, id < 5,000), removes ~99 view re-points
  and 1,407 CategoryTracking rewrites, and makes the "embedded documents
  pin the catalog" ordering constraint disappear — the rung could derive
  straight from K1; (b) pass `wiring=` per key into
  `CAT.builtin_style_catalog` from the old rows (my `build_X6a_v2` in
  `build_v2.py` is the reference); (c) X1's docstring still says "our
  imperial scale breakpoints".
* **`src/rvt/commit.py` (commit-layer owner)** — `commit_new_elements`
  IGNORES the plan's `creation_ep` (it stamps every appended row with the
  parent's max episode; the controls' gotcha 1 concurs): honour an
  explicit `plan.creation_ep` so a genesis writer can mint birth-episode
  (0) rows for the classes whose specimens are always birth rows (the
  project pen table, per objlint's `ETR.created_at_birth`).
* **`src/rvt/genesis/types.py` (types owner)** — `new_gstyle` should
  accept `ab_flags` / `visible_flags` (I set them on the returned record's
  header post-hoc — legal, but a parameter is cleaner) and could take the
  screen-sized / null-pen / null-pattern profile keys directly;
  `default_object_styles()` (the quarantined Autodesk-table reader) is
  superseded by the profiled catalog and should be retired with its
  quarantine file.
* **`tools/genesis_assemble.py` / `src/rvt/genesis/house_standard.py`
  (genesis-2 / house-content)** — the house standard's 46 own
  `new_gstyle` rows are built OUTSIDE the profile (uniform preset, solid,
  −1 material): route them through `catalog.builtin_style_catalog(
  exclude_categories=[])` with the house scheme, or apply
  `catalog._apply_row_profile` per row, so the base's own styles carry the
  per-key flag byte / cells too.  The G-line base should MINT the pen
  table and the catalog in place (low ids, birth episode) per finding 5.
* **`src/rvt/objlint.py` (linter owner)** — add KEYED cohorts for
  table-like classes (GStyleElem keyed by (category, type),
  PenWidthTableElem by scale set): the pooled `GStyleElem|builtin` cohort
  reads 0 findings on rows this stream measures 2,560 defects on.  My
  `builtin_style_profile.json` is a ready-made keyed invariant source.
* **`src/rvt/validate.py` (validation)** — the per-key catalog profile
  (`catalog.lint_builtin_style_catalog`) and the pen-table invariants
  (`settings.lint_pen_width_table`) are consistency rules the validator
  lacks; every FAILED candidate carrying our old catalog scored VALID.
* **`docs/writer/substitution-ladder.md` §4 / `docs/inbox/genesis-
  substitute.md`** (their owner) — X6a's "0 rows value-identical to
  Autodesk's table" claim now needs the per-key nulls: our −1 / 0 / TRUE
  structural cells ARE identical to theirs by construction (they are
  format constants, not expression); the value-identity claim should key
  on the value-bearing pair {pen (non-null keys), colour}.  (The
  singletons stream's `test_catalog_rows_are_never_value_identical_to_the_
  autodesk_table` compares (pen, colour, pattern, screen-sized) 4-tuples
  and still reads 0 identical rows — our colours are never theirs — but
  the pattern / screen-sized / null-pen columns are now SHARED BY DESIGN
  on the structural keys, so the docs' premise should be restated as
  "value-bearing pair never identical; structural cells are the shared
  format constants".)
* **KNOWLEDGE.md owner** — merge findings 1–6.
* **`tools/sync_plugin.py`** — this stream edits two bundled modules
  (`src/rvt/genesis/settings.py`, `catalog.py`); the pre-existing
  plugin-drift test stays red until the orchestrator's sync run (as every
  recent record notes).  Note a DATA dependency the bundle must carry:
  `catalog.builtin_style_catalog` reads `experiments/genesis/subst_v2/
  builtin_style_profile.json` at generation time (like the singletons
  stream's `builtin_category_enum.json` it already sits beside) — both
  JSONs belong in the shipped data set (or get promoted under
  `src/rvt/genesis/data/`, an orchestrator decision).

## Open questions (need the viewer / a decision)

* The eleven verdicts, read per §Reading — **X_cat and X_pen first**.
* **Colour as expression vs value constraint**: if X_cat FAILS while
  X_cat_obj FAILs and the card message points at graphics, our INK
  0x181818 / discipline palette becomes the C1u question at table scale;
  a one-line variant (`catalog_scheme` → the specimens' 6772-row modal
  black on the neutral disciplines) is buildable in seconds but crosses
  into value-identity — a counsel + orchestrator call, NOT taken here.
* **The 84 'nullwire' material keys / 6 'nullwire' pattern keys** carry
  our null; if a probe implicates "a null where the parent had an
  element", the profile can tighten them to 'elem' (wired) with a
  one-token change per key.
* **The two ADD-PATH invariants (A1 / A2)** are held only by the in-place
  probes; whether the ladder / assembler adopt in-place minting is the
  orchestrator's decision (it also fixes the R2-class confound
  permanently).

## Proposed next tasks (orchestrator decides)

1. Upload **X_cat, X_pen** (+ the controls' X0, C0all); read per the
   trees; the *_obj twins and X1..X6a v2 are the pre-built follow-ups.
2. If both PASS: switch the ladder / assembler to IN-PLACE minting for
   the pen table + catalog (the diffs above), retire both classes from
   the suspect list, and run this stream's method (keyed field diff +
   in-place probe) over X2..X5's ~60 singleton classes and the X9
   skeleton classes objlint already ranks (MaterialElem assets, the
   view constellation's NEVER_NULL machinery, ElectricalLoadClassification
   param twins) — the linter's bug list is the queue, this stream's
   probe primitive is the verdict.
3. Fold `settings.lint_pen_width_table`, `catalog.lint_builtin_style_
   catalog` and the profile into `rvt.validate` (§Diffs) so a candidate
   carrying an unprofiled catalog can no longer score VALID.
4. Feed `builtin_style_profile.json` to the linter as its GStyleElem
   keyed cohort source.

## Verification

* Constructors: `python -m rvt.genesis.settings` (constellation round-
  trip clean + byte-exact, 0 dangling — unchanged); `python -m
  rvt.genesis.catalog` → 1,407 rows, round-trip 1407/1407, **specimen
  lint hard 0** (`--derive-profile` re-freezes the profile).
* `.venv/bin/python -m pytest tests/test_genesis_settings.py -q` →
  **61 passed** (61 s): the pre-existing 45 (structural / reproduction /
  enum / catalog / registry / S-ladder tiers) + this stream.s 16 (§Result
  bullet).
* Every emitted `.rvt`: `tools/rvt_validate.py` VALID 0 errors (per-file
  `.json:validator`); the four in-place probes: 0 skipped records,
  1,407/1,407 (+1/1) target objects re-decode EQUAL to ours, ElemTable
  count 6,540 unchanged, **Global/Latest + all 10 non-partition streams
  byte-identical to K1's**; the seven rungs: structural proof, parity
  100 %, 0 new dangling, four-registry coherent (the engine's own gates).
* Full suite: see BRANCH STATE.

## Reproduction (repo root, .venv python)

```
python -m rvt.genesis.catalog --derive-profile     # re-derive + freeze builtin_style_profile.json (~2.5 min), catalog + lint
python -m rvt.genesis.settings                      # constellation self-test
python experiments/genesis/subst_v2/build_v2.py     # X_pen X_pen_obj X_cat X_cat_obj + X1 X2 X3 X4 X5 X10 X6a + probes.json (~3.5 min)
python experiments/genesis/subst_v2/build_v2.py --probes-only          # the four in-place probes (~25 s)
python experiments/genesis/subst_v2/build_v2.py --only X_cat --probes-only
python experiments/genesis/subst_v2/build_v2.py --manifest-only        # re-write probes.json
python tools/rvt_validate.py --quiet experiments/genesis/subst_v2/*.rvt # OK errors=0 (x11)
python -m pytest tests/test_genesis_settings.py -q  # 61 passed
```

Arbiter output (this session):

```
X_pen      VALID errors=0 warnings=1   in place: 1 element / 2 records, Latest == K1's
X_pen_obj  VALID errors=0 warnings=1   in place: 1 element / 1 record
X_cat      VALID errors=0 warnings=1   in place: 1407 elements / 2814 records, Latest == K1's
X_cat_obj  VALID errors=0 warnings=1   in place: 1407 elements / 1407 records
X1  VALID errors=0 warnings=1  parity 1/1        new dangling 0   4,489,216 B
X2  VALID errors=0 warnings=1  parity 10/10      new dangling 0   4,481,024 B
X3  VALID errors=0 warnings=1  parity 6/6        new dangling 0   4,407,296 B
X4  VALID errors=0 warnings=1  parity 8/8        new dangling 0   4,407,296 B
X5  VALID errors=0 warnings=1  parity 53/53      new dangling 0   4,407,296 B
X10 VALID errors=0 warnings=1  coherence 1/0/0/0                  1,441,792 B
X6a VALID errors=0 warnings=1  parity 1407/1407  new dangling 0   1,433,600 B
```
The one warning on every K1-lineage file is K1's own pre-existing
extensible-storage decode gap (6 RebarShape + 1 DataStorage), present on
the pristine sample and on K1 itself — untouched by any file here.

## BRANCH STATE

No VCS (plain directory).  Files EDITED (the singletons stream's modules,
this stream's territory by charter exception): `src/rvt/genesis/settings.py`
(scale-set constant + width-range constants + `lint_pen_width_table` + the
direct-feet argument path), `src/rvt/genesis/catalog.py` (the per-key
structural profile: derive / freeze / load, the profile-shaped
`builtin_style_catalog` with `wiring` + `id_map` + `use_profile`,
`lint_builtin_style_catalog`; module docstring + demo updated).  Files
ADDED: `tests/test_genesis_settings.py` grew by the fixer tier (45 -> 61
test cases, all pass); `experiments/genesis/subst_v2/build_v2.py` (the
driver), `experiments/genesis/subst_v2/builtin_style_profile.json` (the
frozen profile, 1,407 keys), the eleven probe files X_pen X_pen_obj X_cat
X_cat_obj X1 X2 X3 X4 X5 X10 X6a (`.rvt` + `.json` each) + `probes.json`,
`experiments/genesis/subst_v2/analysis/` (the census scripts + JSON dumps
behind §Findings), and this record.  Every emitted `.rvt` = validator
VALID (0 errors), the four in-place probes with Global/Latest and all
non-partition streams BYTE-IDENTICAL to K1's and 1,407/1,407 (+1/1)
target objects re-decoding equal to ours; the seven rungs parity-clean,
0 new dangling, four-registry coherent.  Full suite this session
(`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`): **805
passed, 3 failed** (907 s) — the 3 failures are the pre-existing,
other-stream ones every recent record lists (`test_plugin_sync.py::test_
plugin_is_in_sync_with_source` = the plugin-bundle drift this stream's
two edited modules join, fix = the orchestrator's `tools/sync_plugin.py`
run; `test_provenance.py::{test_G0_resource_refs_are_counted,
test_G0_identity_dit_usernames_still_leak}` = the stale pre-genesis-2 G0
assertions); this stream's 16 new cases are among the 805 (the settings +
substitute files re-verified 70/70 after the last additive edit).
STOPPED AT READY — X_cat / X_pen (+ *_obj twins) and the seven v2 rungs
await the orchestrator's viewer gate; the reading trees are in
`probes.json` and §Reading; the diffs for the substitution engine / commit
layer / objlint / validate / assembler streams are listed in §Diffs.

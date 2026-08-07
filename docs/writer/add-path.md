# The fixed non-instance ADD path and the in-place SUBSTITUTE path (`rvt.regadd`)

Owner: the **genesis-addfix** stream (workstream record: `docs/inbox/genesis-addfix.md`).
Code: `src/rvt/regadd.py`; probes: `experiments/genesis/regadd/`; tests:
`tests/test_regadd.py` (24 pass).

This document specifies (1) what a loadable file's registration of a
non-instance element looks like, measured over the six 2026 samples + K1;
(2) the two operations built on those facts; (3) the probe ladder that
tests them; and (4) the forensic finding that reframes the whole "the add
path is the bug" reading of ORCHESTRATOR VERDICTS #11.

---

## 0. The finding that comes first — the ~00:25 batch has no positive control

ORCHESTRATOR VERDICTS #11 (docs/inbox/genesis-audit.md) reads X0's FAIL
(Autodesk's OWN pen table, exact bytes, re-inserted through our add path) as
"the ADD PATH is the bug".  This stream's byte-level forensics
(`experiments/genesis/regadd/*.diff.json`, measurements m1–m8 in the record)
established four facts the verdict record does not carry:

1. **X_pen and X_cat also FAILED** (viewer-certified.json, ~00:25) — the
   fixer's IN-PLACE payload probes, which do **not** use the add path at all
   (`build_v2.py::_emit_inplace` = `manipulate.commit_plans` replacing an
   existing id's records in place; ElemTable untouched, Global/Latest
   byte-identical to K1's).
2. **X_pen differs from the reader-PASSING K1 in exactly ONE record**:
   element 2's seq-102 pen-table object (1,223 bytes both sides), whose
   only differing fields are the 128 pen-width doubles; the ElemTable
   stream, Latest and the other 10 streams are byte-identical to K1's, and
   the unit-0 id order and block partition are identical.  (The re-chunk
   boundaries manipulate uses differ from K1's, but that chunker's layout is
   itself reader-CERTIFIED via M2/M3/M4.)  A corruption audit that rejects
   ordinary line-weight values is not plausible — users edit that table
   freely.
3. **For C0's class the OLD add path wrote NOTHING out-of-corpus**: the
   9,849 built-in GStyle rows in the corpus span every id band, 83 % are
   NOT birth-episode, all are un-owned, and they sit at every stream
   position (m8/m6).  C0's late-episode / 1.5M-id / unit-end-appended row
   is IN-SET on every axis — yet C0 FAILED.
4. **No writer module changed** between the last CERTIFIED file (L1a,
   written 19:58, certified ~21:05 08-03) and the failed batch (X0 / X_pen
   written 23:46–23:50): the same code produced both.

The five files of the ~00:25 batch (X0, X1u, C0, X_pen, X_cat) **all
failed and no positive control was uploaded**.  A single defect cannot
explain both X0 (Autodesk's content via the add path) and X_pen (our
content, no add path) — and the batch-level explanation (viewer /
translator / upload session failure) is not excluded by anything on
record.  **The first probe of this stream's ladder is therefore a positive
control (XR_null, §4) that MUST pass; if it fails, every verdict since
~22:50 08-03 is suspect and must be re-read.**

---

## 1. What a loadable file's registration of a non-instance element looks like

Registering an element = five things: its **id**, its `Global/ElemTable`
**row** (creation / modified / user-modified episodes, owner, original id,
partition), the **position** of its three records in the unit-0 seq streams,
its **ElementHeader** (parents lists / flags), and its **ADocument
registry** slots (`Global/Latest`).  Measured per class (script m8 in the
record; corpus = the six samples + K1, project-scoped vs family-scoped
split):

### 1.1 Vintage (ElemTable episodes) and id band

| class (project scope) | creation ep 0 | id band | user-modified | note |
|---|---|---|---|---|
| AllProjectPhases | **7/7** | **<5k (id 1)** | a real episode | universal birth singleton |
| DBViewProject | **7/7** | **<5k (id 230)** | a real episode | universal birth singleton |
| PenWidthTableElem (project, `m_famId -1`) | **7/7** | **<5k (2 / 3 / 11)** | a real episode | universal birth singleton; the 58 family-scoped copies are owned by @Family at late episodes |
| KeynoteTable, ProjectInfo, UnitsElem, TrueNorth, RbsDbViewSystemNavigator, KeynotingSystem, StructSettingsElem | 1–2 / 7 | mixed <5k…<500k | a real episode | born at feature-first-use / upgrade — **no universal vintage** |
| BrowserOrganization | 3/79 | mostly <50k | a real episode | — |
| ConstructionSetProject, ReconcileBrowserSettingsElem, AutoJoinTracker, WallJoinDefaultSetting, InitialViewSettings, ElectricalSetting | 0/7 | <500k / <5M | a real episode | never birth |
| **GStyleElem built-in** (9,849) | 1,697 / 9,849 | **every band** | any | **unconstrained** |
| FillPattern / LinePattern / Material | 12–20 % | every band | any | unconstrained |

Rules that hold **7/7** for every project singleton measured: the row is
un-owned; `original_id == id`; `partition_id == 0`; **user-modified is a
real episode, never the 0xFFFFFFFF "never" sentinel**.  The linter's
pooled `ETR.created_at_birth` / `ETR.id_band` rules mix scopes (a
family-scoped pen table is high-id and late) — the project cohort is the
one that binds.

### 1.2 Ownership (`ElemRec.m_OwningElementId`) — the objlint web, confirmed

TextNoteAttributes / LevelAttributes own {CategoryElem, FontElem}
(2,026/2,026, 13/13); every FontElem is owned by an annotation-attributes
type (5,982/5,982 — and the ~1,084 project fonts are owned by attribute
types too, m8); sub-category CategoryElem owns its GStyle (8,225/8,227) and
is owned by an attributes type (7,542/8,227); Viewer / DBDrawing are owned
by their view (507/507, 831/831); Viewport by a DBDrawing (1,028/1,028);
RbsDbViewSystemNavigator owns {Viewer, DBDrawing}; RevisionNumberingSequence
is owned by AllProjectRevisions.  Built-in GStyle rows and the pen table
are un-owned.  All of this is `REG_RULES` in `regadd.py` (each rule carries
its support).

### 1.3 Position — the measurement that changes the design

Charter question: *are the unit-0 seq streams id-ascending? if so insert in
sorted position, not append.*  **Answer: NO** (m1, all six samples + K1):

* The record ORDER is identical across seq 101 / 102 / 103 (same id at the
  same index) but is **NOT id-ascending** (42–222 descents per file) and
  **NOT episode-ordered** (m2, m7: per-creation-episode cohorts are neither
  contiguous nor internally ascending; the birth cohort has descents).
* It is not a topological order of the typed reference graph either
  (58 % / 42 % forward/backward edges on K1, m5).
* It is Revit's internal element-storage order, and **reductions preserve
  it** (K1's order == rstbasic's order minus the deleted elements).
* **Global order is provably NOT a hard audit**: `commit_new_elements`
  appends every created element at the unit end and those files are
  CERTIFIED (V20..V29, T_conduit_types, L1a's family layer).
* What IS reproducible: the document-birth low-id run keeps **consecutive
  ids stream-adjacent** — K1 / rstbasic: …, 1 (AllProjectPhases),
  2 (PenWidthTable), 3 4 5 6 (FillPatterns), … up to 22 contiguous; dach:
  3, 6, 11, 12, 13 ….

Hence the placement policies in `regadd.choose_position`:
`'auto'` = **ID-HOLE** (insert between the stream-adjacent id neighbours
that bracket the new id — reproduces the birth run byte-for-byte; measured
K1 low ids 26/29 are stream-adjacent so id 27 lands between them), else
**after the id-predecessor** when it sits in a locally ascending stretch,
else **append** (the proven default for user content); plus explicit
`'append'`, `'after:<eid>'`, `'index:<n>'`.  Every choice is reported
with its neighbourhood.

### 1.4 The registry (ADocument)

For an in-place substitution the registry is **untouched by construction**
(Global/Latest byte-identical).  For a new element `regadd` populates the
class's surfaces through `genesis.settings.apply_adoc_registry` (the
singletons stream's proven UET / AppInfo / browser / navigator / ETD /
def-type / sysfam / CategoryTracking handlers) and/or re-points an old
id's slots to the new id with the arbiter's **schema-typed** leaf walker
(`genesis_assemble.AdocGraphEditor` — never a byte scan: id 2 is
byte-mentioned by ~40 geometry counters that are not ElementIds).  The
tree is re-encoded byte-exactly (round-trip proven or the emit refuses).

### 1.5 A shared-writer defect found and fixed on the way

`open_rvt().logical()` (depage) leaks the final page's ECC pad junk after
the true logical end (61 bytes on K1's `Partitions/21`).  `reduce`,
`manipulate` and `commit` all copy `logical[u0_footer:]` and truncate at the
walker's "end record" — which absorbs that junk — so every re-emitted file
carries the source's pad junk as content.  **Reader-tolerated** (K3 / K4 /
R0_identity are certified) but it makes byte-identity impossible.
`regadd.EditImage` loads the **exact** logical (`reduce.unframe_exact`,
pad-count-decoded); with it a null substitution re-emits K1's
`Partitions/21` **raw-byte-identical**.  Recommended as the corpus-wide
loading convention (see §6 diffs).

---

## 2. `substitute_element` / `substitute_elements` — the in-place content swap

```
substitute_element(src, out, target_id, records=None, *, null=False,
                   keep_row=True, vintage=None, seqs=(101,102,103))
substitute_elements(src, out, {id: records, ...}, *, null=False, ...)   # batch, one image
```
The old element keeps its **id**, its **ElemTable row** (the ElemTable
STREAM is copied byte-identical unless `vintage=` rewrites episodes), the
**position** of each record (replaced in place), the **block partition**
(when record lengths are unchanged — the pen table's 1,223-byte object is;
`XR0` asserts partition identity in all three seqs), every **registry
slot** (Global/Latest byte-identical) and every embedded document.
`records` = a `TypeRecord` (encoded at `target_id`) or `{seq: framed
bytes}` / `{seq: (class_id, value)}`.  `null=True` re-writes the element
with **its own exact bytes** and asserts the emitted Partitions stream is
**byte-identical** to the parent's — the zero-motion proof and the batch
positive control.  This is the operation the substitution ladder needs
(pure content swap, zero registration motion) — and because ids do not
move, the "family removal must precede catalog substitution" ordering rule
is **moot** (embedded documents' catalog references stay valid; XR3
derives from K1 with all 52 family documents intact).

## 3. `add_element_like_original` — the fixed ADD path

```
add_element_like_original(src, out, records, *, class_name, new_id=None,
        replace_old_id=None, place='auto', cohort='project',
        creation_ep=None, modified_ep=None, user_modified_ep=None,
        preserve_row_of=None, owner_id=-1, owned_child_ids=(),
        register=False, latest_remap=None, strict_rules=False)
```
Fixes the OLD path's four measured defects:

| aspect | OLD path (`commit_new_elements` via the ladder) | FIXED (`regadd`) |
|---|---|---|
| id | watermark + 100k band (1,500,000 on K1) | explicit `new_id` (a low-band free id for a birth singleton) or watermark+1 |
| ElemTable row | `creation = modified = user_modified = parent's MAX episode` (1016), `original_id = new id` — the controls' "gotcha 1" | `vintage_for(class)`: creation-episode **0** for the birth singletons (7/7 fact), else the parent's episode; user-modified always a **real episode** (never 0xFFFFFFFF); `preserve_row_of` COPIES a loadable file's own row (episodes + owner + original id); `owner_id` + `owned_child_ids` wire the ownership web; `check_registration` LINTS against `REG_RULES` (`strict_rules=True` refuses) |
| position | appended before the sentinel (unit end) | `choose_position`: ID-HOLE / after-predecessor / append (§1.3), reported with the neighbourhood; a same-id re-add returns to the deleted element's own position |
| registry | ladder re-points leaves after the append | `latest_remap={old: new}` (schema-typed, edit log) and/or `register=True` (`apply_adoc_registry`); untouched Latest is byte-identical |

Both operations REPORT (JSON-able), run the validator + `verify_reduced`,
and attach `stream_diff_report(parent, out)`: per stream raw-identity;
unit-0 records added / removed / changed with field-level decode diffs;
per-seq id order + block partition identity; ElemTable rows added /
removed / changed; ADocument identity (typed-leaf changes when it
differs); embedded-unit digests.  The certification ASSERTS: no record id
touched beyond the target(s); the streams that must be byte-identical are;
null mode is zero-motion; id order unchanged unless records were added /
removed.

## 4. The probe ladder (`experiments/genesis/regadd/build_regadd.py`)

Every file derives from K1 (viewer-PASS lineage) by ONE change; every
`.json` carries `if_PASS` / `if_FAIL`; every `.diff.json` is the measured
delta.  Built + certified VALID (0 validator errors) this session:

| # | probe | one change vs its passing sibling | asserted at build |
|--:|---|---|---|
| 1 | **XR_null** (UPLOAD FIRST) | element 2 substituted by ITS OWN bytes | **every stream RAW-byte-identical to K1** = the batch positive control |
| 2 | **XR0** | element 2's records = OUR pen table (fixed scale set + our widths), in place | ONE record changed (id 2, same length); ElemTable / Latest / 10 streams identical; id order + **block partition identical in all 3 seqs**; the only field diffs are the pen doubles |
| 3 | XR0v (no upload) | our constructor fed K1's EXACT feet at id 2 | our records == K1's byte-for-byte, all 3 seqs; the file is raw-identical to K1 (collapses onto XR_null) |
| 4 | **XR1** | catalog row 34 (OST_Windows projection) = OUR profiled row, in place | only id 34 changed |
| 5 | XA0 (no upload) | delete id 2 + re-add Autodesk's EXACT records at id 2 via the fixed add path (row copied, same-id in-place, Latest untouched) | **raw-byte-identical to K1** = the add path is zero-motion |
| 6 | XA1 (no upload) | the fixed add path with OUR pen table at id 2 | **raw-byte-identical to XR0** = add-path mechanics == in-place mechanics |
| 7 | **XA2** | **X0 done right**: Autodesk's EXACT pen table added at a FREE LOW id (**27**, corpus band; X0 used 1,500,000) with K1's OWN row COPIED (**ce 0 / me 976 / ue 976**; X0 wrote 1016/1016/1016), inserted at the **ID-HOLE** between 26 and 29 (X0 appended at the unit end), PenWidthTableInfo leaf re-pointed 2→27 (typed, 1 edit) | 0 rule violations; ADocument round-trip byte-exact; the ONLY differences from K1 = {id 2 records removed, id 27 records added at the hole, one ElemTable row moved, one Latest leaf} — the DIRECT sibling of X0 differing only in the registration |
| 8 | **XR3** | ALL **1,407** built-in catalog rows = OUR profiled catalog, in place (catalog lint 0 hard / 0 soft) | 2,228 records changed = 1,407 objects + the headers that differ; ElemTable / Latest identical |
| 9 | **XR2** | the settings singletons in place, the **1:1** subset of the ladder's X1..X5 (78 elements, 65 classes) | only those ids changed; the classes that CANNOT be in place are LISTED (§4.1) |
| 10 | **XR_deep** | XR2 + XR3 (1,485 elements in place) | as above |

Reading (probes.json:decision_tree): **XR_null FAIL ⇒ the batch / viewer
pipeline is broken; stop and re-read every FAIL since ~22:50 08-03 against
a fresh control (re-upload K1.rvt to confirm).**  XR_null PASS + XR0 PASS
⇒ our pen-table content is reader-clean and X_pen's failure was the
manipulate re-chunk on K1 or the batch; X0's failure then convicts the OLD
registration and **XA2** is the fix's proof (PASS ⇒ registration audited
and fixed — KNOWLEDGE-grade; FAIL ⇒ a birth singleton must not be moved
to a new id at all: mint them at their canonical ids, in place — XR0's
route).  XR1 → XR3 reads the catalog row then table; XR2's residue list is
the add-path work queue.

### 4.1 The assertion that CANNOT hold — classes with no pure in-place form

XR2's `residue_not_inplaceable` (measured, not guessed): the
**BrowserOrganization set** (K1 has 11; our house scheme is 6 — 4 map 1:1
by tree role, 2 of ours are new-only, 7 olds are pure deletions), and three
X5 deletions (WorksharingViewModeSettings, 2 × PrintSettings).  Their
corpus registration genuinely differs from a content swap (different
element COUNT / new registry companions), so they need
`add_element_like_original` with the class rule; the same holds for any
constellation our constructor grows (a navigator's owned Viewer / Viewport
/ DBDrawing when the counts differ, an ElectricalLoadClassification's six
param-element companions, an annotation type's owned CategoryElem +
FontElem).  The in-place ladder ends exactly there.

## 5. Reproduce

```
.venv/bin/python -m rvt.regadd --demo                       # the null substitution on K1
.venv/bin/python -m rvt.regadd --rule PenWidthTableElem     # a corpus rule
.venv/bin/python -m rvt.regadd --diff PARENT.rvt OUT.rvt    # the stream diff report
.venv/bin/python experiments/genesis/regadd/build_regadd.py # the ten probes + probes.json (~2 min)
.venv/bin/python -m pytest tests/test_regadd.py -q          # 24 passed
```

## 6. Diffs proposed for files outside this territory (NOT applied)

* **`src/rvt/reduce.py` / `manipulate.py` / `commit.py` (their owners)** —
  load the partition's logical via `reduce.unframe_exact(raw)` instead of
  the depaged `logical()`: the depage tail carries the source's ECC pad
  junk (61 B on K1) into every re-emitted file (reader-tolerated, but it
  bloats each generation and forbids byte-identity).  One-line change per
  writer; `regadd.EditImage` is the reference.
* **`src/rvt/commit.py::commit_new_elements`** — honour `plan.creation_ep /
  modified_ep / user_modified_ep / original_id` instead of stamping the
  parent's max episode into all three (the controls' gotcha 1 = this
  stream's defect A1); accept an insertion index (position) per element.
* **`tools/genesis_substitute.py`** — for 1:1 same-class rungs, substitute
  IN PLACE (this module) instead of delete+append: the pen table / catalog
  keep their ids, rows, positions and registrations (no re-point pass, no
  R2-class embedded-document confound); the ordering constraint "X10 before
  X6a" disappears.
* **`tools/genesis_assemble.py` / the genesis writer** — a fresh genesis
  document must MINT its birth singletons AT their canonical low ids (1
  AllProjectPhases, 2 pen table, 230 DBViewProject, …) with episode-0 rows,
  ordered id-ascending (all elements are birth-vintage), not allocated from
  a high band.
* **`src/rvt/objlint.py` / `validate.py`** — `regadd.check_registration` +
  `REG_RULES` are the ElemTable-vintage / ownership rules as an ASSERTABLE
  table; a candidate whose registration violates them should not score
  VALID.

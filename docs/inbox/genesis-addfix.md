# genesis-addfix — THE FIXED NON-INSTANCE ADD PATH + THE IN-PLACE SUBSTITUTE PATH (workstream record, 2026-08-04)

Charter (ORCHESTRATOR VERDICTS #11): X0 (Autodesk's OWN pen table, exact
bytes, re-inserted through OUR add path) and C0 (Autodesk's own catalog row
verbatim via our path) BOTH FAIL 'Revit-DocumentCorruption' — our objects
are exonerated, the ADD PATH for non-instance elements corrupts; the
family-instance add path is proven.  Build the fixed registration procedure
(`src/rvt/regadd.py`: `add_element_like_original` + `substitute_element`)
and re-emit XR0..XR_deep with the object-bytes-only assertions.

Territory touched ONLY (as chartered): `src/rvt/regadd.py` (new),
`tests/test_regadd.py` (new, 24 pass), `experiments/genesis/regadd/*`
(build_regadd.py driver, analysis/m1..m8 scripts, ten `.rvt` + per-probe
`.json` + `.diff.json`, `probes.json`), `docs/writer/add-path.md` (the
design / results document — READ IT for the layout tables and the corpus
rules), this record.  NO existing `src/rvt/*.py`, tool or test edited; the
constructors (`genesis.settings.pen_width_table`, `catalog.builtin_style_
catalog`), the substitution engine's rung builders, the arbiter, the
adocument codec and the reduce writer are IMPORTED.  No browser / viewer
use: the seven upload files are LEFT ON DISK for the orchestrator, ordered
in `probes.json:reading_order` with a full decision tree.

---

## THE FIRST-ORDER FINDING — READ BEFORE ANY VERDICT (it is not in the audit yet)

**The charter's premise ("X0 FAIL ⇒ the add path is the bug, our objects
are exonerated") is under-determined by the batch that produced it, and the
forensic evidence points at a batch/pipeline failure that must be excluded
FIRST.**  Measured this session (scripts `experiments/genesis/regadd/
analysis/m1..m8`, diffs `experiments/genesis/regadd/*.diff.json`):

1. **X_pen and X_cat ALSO FAILED** (docs/coverage/viewer-certified.json,
   the same ~00:25 batch) — the fixer's IN-PLACE payload probes, which use
   `manipulate.commit_plans` on K1 and do **not** use the add path at all
   (ElemTable count unchanged, Global/Latest byte-identical to K1's, 10
   non-partition streams identical — per X_pen.json).  Verdict #11
   dismisses them as "subsumed by X0"; they cannot be — they hold the add
   path CONSTANT (absent) and vary only OUR CONTENT.
2. **X_pen differs from the reader-PASSING K1 in exactly ONE record** (my
   m3/m4 diff): element 2's seq-102 pen-table object, 1,223 bytes both
   sides, whose ONLY differing fields are the 128 pen-width doubles (even
   nominally identical mm values are different doubles — Autodesk's are
   not mm/304.8-derived, the fixer's P1).  ElemTable stream, Latest, the
   other streams, the unit-0 id order: identical.  The re-chunk boundaries
   differ (manipulate's spanning first block 131,072 B vs K1's 131,088) but
   that chunker's layout is itself reader-CERTIFIED (M2 / M3 / M4 carry it).
   A corruption audit that rejects a table of ordinary line weights
   (0.13…8.0 mm) is not credible — users edit that table freely.
3. **For C0's class the OLD add path wrote NOTHING out-of-corpus** (m8):
   the 9,849 built-in GStyle rows in the corpus span EVERY id band, 8,152
   are NOT birth-episode, all are un-owned, and they sit at every stream
   position (m6).  C0's late-episode / 1.5M-id / unit-end-appended row is
   IN-SET on every axis — yet C0 FAILED.  So even for C0 the "registration
   is out of corpus" explanation is unavailable.
4. **No writer module changed** between the last CERTIFIED file (L1a,
   written 19:58 08-03, certified ~21:05) and the failed batch (X0 / C0
   written 23:46–23:47, X_pen / X_cat 23:50): the identical writer code
   produced both — a code regression is EXCLUDED (mtimes recorded).
5. **The ~00:25 batch — X0, X1u, C0, X_pen, X_cat — ALL FAILED and
   contained NO POSITIVE CONTROL.**  Neither did the ~23:11 (X1) nor the
   ~22:50 (R1..R3, X5, X9) batches; the last recorded PASS of anything is
   L1a (~21:05).  X0 (Autodesk's content + add path) and X_pen (our content,
   no add path) cannot BOTH follow from one defect; the parsimonious
   readings are (a) TWO independent audits (pen-width values AND
   registration) — implausible given points 2–3, or (b) a BATCH-LEVEL
   failure (viewer / translator / upload session) making every file in the
   round fail regardless of content.  Nothing on record excludes (b).

**⇒ THE FIRST FILE TO UPLOAD IS A POSITIVE CONTROL: `XR_null.rvt` (K1 with
its pen table substituted by ITS OWN exact bytes — asserted RAW-byte-
identical to K1 in EVERY stream = a content-identical copy of the
certified-lineage base).  IT MUST PASS.  IF IT FAILS, the pipeline is
broken and EVERY genesis FAIL since ~22:50 08-03 (X0, C0, X1u, X_pen,
X_cat, the X-ladder, R1..R3) is a false negative — STOP interpreting, do not
touch the writer, re-upload `K1.rvt` and one certified file (e.g. `K4.rvt`)
to localize.**  Only if XR_null PASSES do the other verdicts read as
written.  This single control is worth more than the rest of the ladder:
it converts a night of un-controlled negatives into readable data.

---

## Result in one screen

**Both operations built on the mechanics of a KNOWN-PASSING writer
(`rvt.reduce` — the K3 / K4 / KD1 / R-line re-blocker), with a byte-diff
report ASSERTING what each probe changed; ten probe files built, EVERY ONE
validator-VALID (0 errors) + structurally proven, the byte-identity
assertions holding EXACTLY:**

| # | probe | one change vs its PASSING sibling | asserted (checked, not claimed) | upload |
|--:|---|---|---|:--:|
| 1 | **XR_null** | element 2 substituted by ITS OWN exact bytes | **every stream RAW-byte-identical to K1** (12/12) | **FIRST** |
| 2 | **XR0** | element 2's records = OUR pen table (fixed scale set + our widths), IN PLACE | ONE record changed (id 2, 1,223 B = same length); ElemTable / Latest / 10 streams identical; id order + **block partition identical in all 3 seqs**; only field diffs = the pen doubles.  = the fixer's X_pen MINUS the re-chunker variable | yes |
| 3 | XR0v | our constructor fed K1's EXACT feet at id 2 | our records == K1's byte-for-byte (3 seqs); file **raw-identical to K1** — collapses onto XR_null (the P2 assertion, re-proven end-to-end) | no |
| 4 | **XR1** | catalog row 34 (OST_Windows projection) = OUR profiled row, IN PLACE | only id 34 changed | yes |
| 5 | XA0 | delete id 2 + re-add Autodesk's EXACT records at id 2 via the FIXED add path (row copied, same-id in-place, Latest untouched) | **raw-byte-identical to K1** = the add path is zero-motion when the registration is unchanged | no |
| 6 | XA1 | the fixed add path carrying OUR pen table at id 2 | **raw-byte-identical to XR0** = add-path mechanics == in-place mechanics | no |
| 7 | **XA2** | **X0 DONE RIGHT**: Autodesk's EXACT pen table added at a FREE LOW id **27** (corpus band; X0: 1,500,000) with K1's OWN row COPIED (**ce 0 / me 976 / ue 976**; X0: 1016/1016/1016), inserted at the **ID-HOLE between 26 and 29** (X0: appended at the unit end), PenWidthTableInfo leaf re-pointed 2→27 (schema-typed, 1 edit) | 0 corpus-rule violations; ADocument round-trip byte-exact; the ONLY deltas vs K1 = {id 2 records removed, id 27 records added at the hole, one ElemTable row, one Latest leaf} — X0's direct sibling differing ONLY in the registration | yes |
| 8 | **XR3** | ALL **1,407** built-in catalog rows = OUR profiled catalog, IN PLACE (lint 0 hard / 0 soft) | 2,228 records changed (1,407 objects + differing headers); ElemTable / Latest identical; NO family removal needed (in-place moves nothing) | yes |
| 9 | **XR2** | the settings singletons IN PLACE, the **1:1 subset** of the ladder's X1..X5 (78 elements / 65 classes) | only those ids changed; the non-in-placeable residue LISTED (browser-org set: 11 old / our 6 → 4 in-placed, 2 new-only, 7 deletions; 3 X5 deletions) | yes |
| 10 | **XR_deep** | XR2 + XR3 (1,485 elements in place) | as above | yes |

Reproduce: `.venv/bin/python experiments/genesis/regadd/build_regadd.py`
(~2 min; `--only`, `--manifest-only`, `--skip-deep`).  `probes.json`
carries the ordered manifest + the full decision tree; each `<probe>.json`
its `if_PASS` / `if_FAIL`; each `<probe>.diff.json` the measured delta.

**Upload ONE round in THIS order: XR_null (positive control), XR0, XR1,
XA2, XR3, XR2, XR_deep.**  XR0v / XA0 / XA1 are build-time assertions
(byte-identical twins of XR_null / K1 / XR0) — no viewer round needed.

## THE MEASUREMENTS BEHIND THE CODE (charter items (a)–(f))

Corpus = all six 2026 samples + K1; scripts + JSON in `experiments/genesis/
regadd/analysis/`; full tables in `docs/writer/add-path.md` §1.

**(c) POSITION — the charter's premise is refuted, and replaced (m1, m2,
m5, m6, m7).**  The unit-0 seq streams are **NOT id-ascending** in ANY
file (42–222 descents per file; the id order is identical across seq
101/102/103), NOT episode-ordered (per-creation-episode cohorts are neither
contiguous nor internally ascending, m7), and NOT a topological order of
the typed reference graph (58/42 % forward/backward on K1, m5).  It is
Revit's internal element-storage order; **reductions preserve it** (K1's
order == rstbasic's minus deletions).  **Global order is provably NOT a
hard audit**: `commit_new_elements` appends every created element at the
unit end and those files are CERTIFIED (V20..V29, T_conduit_types).  What
IS reproducible: the document-birth low-id run keeps consecutive ids
**stream-adjacent** (K1/rstbasic: …, 1 AllProjectPhases, 2 pen table,
3 4 5 6 FillPatterns … contiguous to 22; dach: 3, 6, 11, 12 …).  ⇒
placement policy `'auto'` = **ID-HOLE** (insert between the stream-
adjacent bracketing id neighbours — reproduces the birth run byte-for-byte;
XA2's id 27 landed exactly between 26 and 29), else after-the-ascending-
predecessor, else append; every choice reported with its neighbourhood.

**(b) VINTAGE + OWNER — measured per class, project vs scoped (m8).**
Only THREE classes are creation-episode 0 in EVERY file: AllProjectPhases
(7/7, id 1), DBViewProject (7/7, id 230), the project PenWidthTableElem
(7/7, id 2 / 3 / 11) — all `<5k`.  Every OTHER settings singleton
(KeynoteTable, UnitsElem, ProjectInfo, StructSettingsElem, the browser /
navigator / MEP settings…) is born LATER in most files (0–2 / 7 at
episode 0) — the linter's `ETR.created_at_birth` ENUM was reading the
pooled cohort; there is NO universal vintage for them.  Universal for every
project singleton: un-owned, `original_id == id`, partition 0, **user-
modified is a real episode, NEVER the 0xFFFFFFFF "never" sentinel** — which
`streams_edit.elemtable_add_element` writes BY DEFAULT (`user_modified_ep=
NO_EPISODE`) and `commit_new_elements` overrides with the parent's max
episode; `regadd.vintage_for` writes creation 0 for the birth trio, the
parent episode otherwise, and always a real user-modified episode.  The
ownership web (TextNoteAttributes / LevelAttributes own {CategoryElem,
FontElem}; FontElem owned 5,982/5,982; Viewer / DBDrawing by their view;
Viewport by DBDrawing; navigator owns {Viewer, DBDrawing}; revision
sequences by AllProjectRevisions) is confirmed by the ElemTable rows and
encoded in `REG_RULES`; `owned_child_ids` wires it, `check_registration`
lints it.  **The two known defects the old path never left un-committed
(owner INVALID where the corpus owns; episode = latest where the corpus
says 0) are exactly what `check_registration` catches** (`strict_rules=
True` refuses).

**(d) HEADER — validated, not invented.**  The pen table's seq-101 header
is the specimen's byte-for-byte (XR0v: our constructor at id 2 reproduces
K1's header exactly); the catalog rows carry the fixer's profiled flag
words.  Class header rules (SunAndShadowSettings' appearance/regen =
[BasePoint], BasePoint's regen length 2, …) stay the constructors' job;
`regadd` transports what it is given and reports the diff.

**(e) REGISTRY — schema-typed, byte-exact, or untouched.**  In-place ⇒
Global/Latest byte-identical by construction.  New element ⇒ `register=
True` (`settings.apply_adoc_registry`, the singletons stream's proven
surfaces) and/or `latest_remap={old: new}` (the arbiter's typed leaf
walker — XA2's single edit is `AppInfoManager.m_appInfoArr[38]->
PenWidthTableInfo.m_penWidthTableElemId 2 -> 27`; never a byte scan: id 2 is
byte-mentioned by ~40 non-id counters).  Re-encoded byte-exactly (round-
trip proven or the emit refuses).

**(f) The two known defects are un-emittable by default** (see (b)).

**A shared-writer defect found and fixed en route.**  `open_rvt().
logical()` (depage) leaks the final page's ECC pad junk after the true
end (61 B on K1's Partitions/21); `reduce` / `manipulate` / `commit` all
copy `logical[u0_footer:]` and truncate at the walker's "end record",
which absorbs the junk — every re-emission carries the source's pad junk
as content (reader-tolerated: K3 / K4 / R0_identity certified; but each
generation bloats and byte-identity is impossible).  `regadd.EditImage`
loads the EXACT logical (`reduce.unframe_exact`, pad-count-decoded); with
it XR_null's Partitions RAW stream is byte-identical to K1's.  My first
null attempt was NOT identical — the assertion caught it; the diff report
now compares RAW streams (immune to depage junk).  Diff for the three
writers in §Diffs.

## New findings for KNOWLEDGE.md (evidence in the analysis scripts)

1. **[V, m1] The unit-0 record order is the SAME across seq 101/102/103
   and is Revit's internal storage order — not id-, episode- or
   dependency-ordered; reductions preserve it; the reader does not audit
   it (appended user content certified).**  The birth low-id run keeps
   consecutive ids adjacent (the reproducible anchor for insertion).
2. **[V, m8] Only AllProjectPhases (id 1), DBViewProject (id 230) and the
   project PenWidthTableElem (id 2/3/11) are creation-episode 0 in 7/7
   files; every other settings singleton has no universal vintage.
   Universal for all project singletons: un-owned, un-renumbered, partition
   0, user-modified = a real episode (never "never").**
3. **[V, m8] Built-in GStyle catalog rows are unconstrained on every
   registration axis** (band / episode / owner / position) — so no
   registration property can explain C0's failure.
4. **[V, m3/m4] X_pen (FAIL) differs from K1 (PASS) in exactly one record
   — the pen doubles — plus manipulate's certified re-chunk boundaries.**
5. **[V] The depaged `logical()` carries the final page's pad junk;
   `reduce.unframe_exact` is the exact reader; re-framing the exact
   logical reproduces the raw stream byte-for-byte.**
6. **[V] `commit_new_elements` stamps the parent's max episode into all
   three ElemRec episodes and `original_id = new id` regardless of the
   plan** (the controls' gotcha 1, re-confirmed) — the birth-vintage row
   is unreachable through it; `regadd` writes it.
7. **[V, m8] `elemtable_add_element`'s default `user_modified_ep=NO_EPISODE`
   ("never") occurs on ZERO project singletons in the corpus** — a third
   silent default any settings-class caller should override.

## Gotchas (for KNOWLEDGE.md merge)

1. The stream-diff / identity checks must compare RAW streams (or
   `unframe_exact` logicals): two content-identical files depage to
   different tails.
2. `catalog.builtin_style_catalog` needs an id allocator for the enum
   categories not covered by `id_map` (the in-place single-row probe hit
   the `ids=None` ValueError; pass a throwaway `IdSource`).
3. A same-id delete-and-re-add is `add_element_like_original(replace_old_id
   == new_id, place='auto')` — it returns to the deleted element's own
   positions and copies the row via `preserve_row_of`; done right it is a
   byte-level no-op (XA0), which the substitution engine cannot do (its
   stage A appends + stage B deletes the same id).
4. Our pen-table object encodes to EXACTLY the specimen's length (1,223
   B), so an in-place swap preserves the block partition byte-for-byte —
   the reason XR0 has ONE differing record and zero mechanics deltas.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/reduce.py`, `manipulate.py`, `commit.py` (their owners)** —
  load the partition logical via `reduce.unframe_exact(raw)` instead of
  `doc.logical()` (finding 5); one-line change each; `regadd.EditImage` is
  the reference.  Not correctness-critical (reader-tolerated) but it is
  the difference between "re-emission == parent" and "≈ parent".
* **`src/rvt/commit.py::commit_new_elements` (commit-layer owner)** —
  honour the ElemRecPlan's `creation_ep` / `modified_ep` /
  `user_modified_ep` / `original_id` (finding 6; the controls stream and
  the fixer proposed the same); accept a per-element insertion index so
  callers can place records (this stream's `choose_position` returns it).
* **`src/rvt/streams_edit.py::elemtable_add_element` (its owner)** —
  reconsider the `user_modified_ep=NO_EPISODE` default (finding 7); the
  corpus has NO project singleton with "never" — default to `modified_ep`.
* **`tools/genesis_substitute.py` (its owner)** — for 1:1 same-class
  rungs (X1 pen table, the X3/X4/X5 singletons, X6a's catalog rows) call
  `regadd.substitute_elements` instead of delete+append+re-point: ids /
  rows / positions / registrations are preserved by construction, the
  parity assertion becomes trivial, and the "X10 (family removal) before
  X6a" ordering constraint disappears (my XR3 derives from K1 with all 52
  family documents intact).  Only the genuine residue (count-mismatched
  classes, new-only companions) needs the add path — via
  `add_element_like_original` with `place='auto'` + the class rule.
* **`tools/genesis_assemble.py` / the genesis writer** — a fresh genesis
  document is ALL birth-vintage: MINT the singletons AT their canonical
  low ids (1 AllProjectPhases, 2 pen table, 230 DBViewProject, …) with
  episode-0 rows, ordered id-ascending; never allocate them from a high
  band and never move them (XA2's verdict decides whether "move" is fatal
  or merely non-canonical).
* **`src/rvt/objlint.py` / `validate.py` (their owners)** — `REG_RULES`
  + `check_registration` are the ElemTable-vintage / ownership rules as an
  assertable table; a candidate whose registration violates them should
  not score VALID (the pooled linter cohort mis-reads the project-vs-scoped
  vintage — finding 2).
* **The orchestrator / genesis-audit.md** — record the ~00:25 batch's
  X_pen / X_cat verdicts as UN-INTERPRETABLE (not "subsumed by X0"), record
  that the batch had NO positive control, and read this stream's XR_null
  BEFORE any further genesis verdict.  Verdict #11's "the add path is the
  bug" should be held as ONE hypothesis, alongside "the batch failed", until
  XR_null reads.
* **KNOWLEDGE.md owner** — merge findings 1–7 and gotchas 1–4.
* **`tools/sync_plugin.py`** — this stream adds ONE `src/` module
  (`src/rvt/regadd.py`) to the plugin-drift list (the pre-existing
  `test_plugin_sync` failure every recent record lists); fix remains the
  orchestrator's `python tools/sync_plugin.py` run.

## The assertions the charter names that CANNOT hold, stated precisely

* **"XR2 = the settings layer X1..X5 done via substitute_element (each
  singleton swapped in place)"** holds for the 1:1 subset only (78 of the
  X-ladder's old elements, 65 classes).  The **BrowserOrganization set
  (11 old vs our house set of 6), the 2 new-only orgs, and the pure
  deletions (WorksharingViewModeSettings, 2 × PrintSettings)** have NO
  in-place form — their corpus registration genuinely differs from a
  content swap (different element COUNT / new registry companions).
  Listed in `XR2.json:residue_not_inplaceable`; they are the add path's
  work queue.  The same limit will hold for any constellation whose element
  count our constructor changes (a navigator's owned trio, an
  ElectricalLoadClassification's six param companions, an annotation
  type's owned CategoryElem + FontElem when created fresh).
* **"XR3 on the family-removed base per the ordering rule"** — the rule
  does not apply: in-place substitution changes no id, so the embedded
  family documents' catalog references stay valid; XR3 derives from K1
  with families intact (closer to the proven base = a cleaner probe).
* **"every file validator 0 errors + a K1 byte-diff report per stream
  showing ONLY object bytes changed"** — holds for XR0 / XR1 / XR3 / XR2 /
  XR_deep (assert: ElemTable identical, Latest identical, id order
  identical, block partition identical where lengths hold) and holds as
  BYTE-IDENTITY for the three nulls (XR_null / XR0v / XA0 == K1; XA1 ==
  XR0).  XA2 is a genuine registration change by design (ElemTable +
  Latest + Partitions differ, everything else identical) — its diff
  documents the whole delta.

## Open questions (need the viewer)

* **XR_null's verdict, before all else** — it decides whether the last
  three batches are readable at all.
* XR0 (our pen values, in place, zero mechanics delta) vs XA2 (X0 done
  right) vs X0 — read per the decision tree in `probes.json`.
* If XA2 PASSES: per-rule twins (id-band-only / vintage-only /
  position-only, seconds to build with `add_element_like_original`) split
  the credit among the three registration axes.
* If XA2 FAILS with XR_null PASSING: is X0k's verdict on record?  X0k
  (Autodesk's pen table re-inserted at ITS OWN id, appended position,
  rewritten row) + XA2 + X0 triangulate {move-to-new-id} vs {position}
  vs {row}.  (X0k was uploaded per verdict #11 but has NO recorded verdict.)

## Verification

* `.venv/bin/python -m pytest tests/test_regadd.py -q` → **24 passed**
  (24 s): the corpus rules (birth trio ep 0 / <5k; catalog unconstrained;
  vintage_for / check_registration catching the two defects; scoped vs
  project pen rule); the placement policies on synthetic runs (id-hole,
  after-predecessor, append, explicit, sentinel guard); K1 end-to-end
  (null substitution zero-motion = every stream raw-identical; in-place
  content substitution changes exactly the target with ElemTable / Latest
  / partition / order identical and only pen-double field diffs; the
  exact-feet constructor reproduces K1; the add-path null == K1; the add
  path at a new low id conforms + registry re-point + validator VALID;
  strict_rules refuses X0's registration; batch null substitution
  zero-motion).
* Every probe file: validator VALID 0 errors + `verify_reduced` structural
  proof + the diff assertions (per-file `.json:verdict/problems`).
* Full suite: see BRANCH STATE.

## Reproduction (repo root, .venv python)

```
python -m rvt.regadd --demo                          # the K1 null substitution (proves zero motion)
python -m rvt.regadd --rule PenWidthTableElem        # print a corpus rule
python -m rvt.regadd --diff PARENT.rvt OUT.rvt       # the stream diff report
python experiments/genesis/regadd/build_regadd.py    # the ten probes + probes.json  (~2 min)
python experiments/genesis/regadd/build_regadd.py --only XR_null,XR0
python experiments/genesis/regadd/analysis/m1_positions.py   # (m1..m8: the corpus measurements)
python -m pytest tests/test_regadd.py -q             # 24 passed
```

Arbiter output (this session): all ten `experiments/genesis/regadd/*.rvt`
= validator VALID 0 errors, structural proof clean; XR_null / XR0v / XA0
raw-byte-identical to K1 (12/12 streams); XA1 raw-byte-identical to XR0;
XR0 / XR1 / XR3 / XR2 / XR_deep changed exactly the substituted ids with
ElemTable + Latest identical; XA2 = 0 rule violations, 1 typed registry
edit, embedded units identical.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files: `src/rvt/regadd.py`,
`tests/test_regadd.py` (24 pass), `docs/writer/add-path.md`,
`docs/inbox/genesis-addfix.md` (this file), and under `experiments/
genesis/regadd/`: `build_regadd.py`, `analysis/m1..m8*.py` (+ two JSON
dumps), the ten probe files `XR_null XR0 XR0v XR1 XA0 XA1 XA2 XR3 XR2
XR_deep .rvt` + one `.json` + one `.diff.json` each + `probes.json` +
`demo_null.rvt`.  Every emitted `.rvt` = validator VALID (0 errors),
structurally proven, its byte-identity assertions holding as tabled.  Full
suite this session (`.venv/bin/python -m pytest tests/ -q --ignore=tests/
oracle`): **888 passed, 3 failed** of 891 (968 s).  This stream's 24
tests are among the 888.  The 3 failures are the pre-existing, other-
stream ones every recent record lists — none touching this stream's
files: `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source`
(the plugin-bundle drift; this stream adds ONE `src/` module, `regadd.py`,
to that list — fix remains the orchestrator's `python tools/sync_plugin.py`
run) and `tests/test_provenance.py::{test_G0_resource_refs_are_counted,
test_G0_identity_dit_usernames_still_leak}` (the STALE assertions pinning
the pre-genesis-2 G0 defects).  STOPPED AT READY — the seven
upload files await the orchestrator's viewer gate in the ordered batch
above; **XR_null must be read FIRST as the positive control**; the
reading trees are in `probes.json` and each `.json`; the diffs for the
substitution engine / commit layer / reduce / streams_edit / objlint /
validate / assembler / KNOWLEDGE streams are listed in §Diffs.

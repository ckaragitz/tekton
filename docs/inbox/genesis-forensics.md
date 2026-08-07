# genesis-forensics — THE REGISTRATION DIFF (workstream record, 2026-08-04)

Charter (orchestrator verdicts #11): X0 (Autodesk's OWN pen table, exact
bytes, re-inserted through OUR add path at id 1,500,000) and C0 (Autodesk's
own catalog row 34 verbatim through our path) both FAIL
`Revit-DocumentCorruption` while the family-INSTANCE add path is PROVEN — so
the bug lives in the DELTA between how a loadable file registers such
elements and how our path does. Measure that delta field by field:
(1) the ElemTable row, (2) the ElementHeader, (3) the record POSITION in the
unit-0 seq streams, (4) the ADocument registries, (5) the original's deletion —
each against K1 (Autodesk's registration, PASS), the proven created
FamilyInstance (V20, PASS), and six-sample corpus invariants; deliver the
diff table + the RANKED deviation list. This stream builds NO probes.

**Deliverables:** `docs/writer/registration-diff.md` (the diff table + the
ranked list, §0–§11), `src/rvt/regdiff.py` (`registration_of(doc, eid)` →
the full registration record: ElemTable row + decoded ElementHeader +
per-seq record positions and their id-ascending RUN + ADocument registry
surface + ElemTable ownership; `diff_registrations`; `unit0_runs`;
`mine_record_order` / `mine_elemtable_invariants`; `inbound_referrers`),
`tests/test_regdiff.py` (12 pass), this record. Territory respected: no
existing `src/rvt/*.py`, tool or test edited; no `.rvt` written; no browser.

## Result in one screen

Every dimension X0/C0 change vs K1 measured to the byte; each calibrated
against V20 (the proven path) and the corpus. Ranked (full argument in the
deliverable §7):

1. **RANK 1 — the DELETE + REGISTRY VALUE-REWRITE.** X0/C0 delete the
   original registered element and rewrite its single ADocument registry leaf
   (`PenWidthTableInfo.m_penWidthTableElemId 2 → 1,500,000`;
   `CategoryTracking.m_gstyleData[1402].m_gstyleId 34 → 1,500,000`) — a
   3-byte, single-leaf, codec-byte-exact edit that has **never occurred in
   any viewer-PASSED file**. It is the ONE dimension shared by X0 and C0 that
   V20 does not have, and (fact below) C0's failure has no other explanation.
2. **RANK 2 — birth-VINTAGE row rewritten** (pen table only): `(orig 2, ce 0,
   me 976, ue 976, id 2)` → `(1.5M, 1016, 1016, 1016, 1.5M)`; the project pen
   table is `ce == 0` and id `<5k` in **6/6** samples (only three classes carry
   such a universal law: project PenWidthTableElem, AllProjectPhases,
   DBViewProject). **Falsified as the COMMON cause by C0**: 4,124 of the 8,442
   accepted built-in `GStyleElem` host rows carry C0's exact row signature
   (fresh episode ce == me == ue > 0, un-owned, band ≥ `<500k`) — rstbasic
   itself has built-in style rows 1,472,449.. created in episode 1015. So
   vintage is an *additional* candidate for the pen table at most (MEDIUM).
3. **RANK 3 — record moved to the END of unit 0. RETIRED by V20.** New law
   established: the unit-0 record stream is NOT id-sorted; it is a sequence
   of id-ascending RUNS grouped by the rows' MODIFIED episode, **newest-
   modified run FIRST** (all six samples; identical order in seqs
   101/102/103). K1's element 2 (row me 976) sits in the ep-976 run at index
   2,516; X0's 1,500,000 (row me 1016) is appended LAST, inside the OLDEST
   (ep-277) run — an inversion of the law. **V20's proven created instance
   sits at the identical position class (last record, ep-277 run, ep-1016
   row) and PASSED.** Position is not audited.
4. RANK 4 (low): `original_id = new id`, watermark jump +27,475 vs V20's +1.
5. **RETIRED, with the proving control:** the identity rebase / constructor
   / header / rep (X0's records differ from K1's ONLY in the record id, the
   object's `m_id`, and the header's `m_deletion` self entry — 6/10/3 framed
   bytes; the header carries NO episode mirror, `m_regenHistory.m_historyMap`
   is empty); the stamp (0/13,080 mismatches in K1, X0, X0k, X_pen); the
   `Global/Latest` re-encode (X0 vs K1 = exactly the 3 leaf bytes; codec
   byte-exact); identity scrub (V30/V31/V32); re-block / seq coherence /
   save-history cross-invariants (K1..K4, KD1, R5, R9, L1a, M3/M4; History
   1017 == max ep 1016 + 1 holds on every probe); deletion collateral (K1's
   ids 2 and 34 have **0** typed inbound referrers — independently re-derived
   over host + all 52 embedded units — 0 owned rows, un-owned).

## THE BLOCKING FINDING — the instrument, not the file (read before X0k / genesis-7)

Measured stream-by-stream: the fixer's in-place payload probes **X_pen** and
**X_cat** differ from K1 in **`Partitions/21` ONLY** — every other stream,
including `Global/Latest` and the ElemTable, is **raw byte-identical** to
K1's; X_pen's pen-table records sit at their ORIGINAL position 2,516 with
the seq-101 header **byte-identical** and only the seq-102 object's 126 width
doubles ours (684 differing bytes). So **X_pen's change set ∩ X0's change
set = ∅** — and both are recorded FAILED in the same ~00:25 viewer round
(with X1u, X_cat, C0). Two orthogonal probes both failing is logically
over-determined:

* either there are TWO independent load-time constraints — OUR add path AND
  our pen-table doubles — which VOIDS the in-place fallback and falsifies
  verdict #11's headline "our objects are exonerated";
* or **the round did not discriminate**. Supporting the second: the last
  viewer PASS on record is **L1a (~21:05)**; since then **12 consecutive
  FAILs across four rounds and ZERO known-PASS controls uploaded**. An
  instrument that has read 12 FAILs / 0 PASSes with no positive control is
  uncalibrated ("zero successes over N events is a defect signature").

Also: verdict #11 records *"X_pen, X_cat, X1u also FAIL (now uninterpretable
— subsumed by X0)"*. **X_pen is NOT subsumed by X0** — it is the ORTHOGONAL
probe (the fixer's own record and this stream's diff both say so). That
sentence is a misattribution and should be struck.

**Recommended before any further verdict is read:** ONE round containing a
**byte-identical copy of an already-CERTIFIED file** (e.g. K4.rvt renamed) +
**X0k** + a **re-upload of X_pen**. The 2×2×2 reading table is in the
deliverable §8; in short — certified copy FAILs ⇒ the round is unreliable and
every conviction since ~21:05 must be re-run against a control; certified
copy PASSES ⇒ X_pen's verdict is a real, independent payload conviction and
X0k splits rank 1 from ranks 2/3.

## New format / method findings (evidence — merge into KNOWLEDGE.md)

1. **The unit-0 record-order law [V, six samples].** Save-unit 0's three
   parallel seq streams (101/102/103) carry IDENTICAL element orders, and
   that order is a sequence of maximal id-ascending RUNS (46 in rstbasic, up
   to 216 in rme) grouped by the ElemTable rows' MODIFIED episode, ordered
   newest-modified FIRST, oldest LAST (rstbasic: 0 violations of strictly
   descending modal episode across 46 runs; larger files 2–11 non-descending
   adjacent pairs of ~120–215 = mixed-episode runs). An element's records
   sit in the run of ITS OWN last-modified episode: rstbasic's project pen
   table (row me 976) at host index 9,889/13,936, right after id 1
   (AllProjectPhases), inside the settings/catalog ep-976 run. Birth-episode
   singletons therefore live deep inside the stream, never at the front or
   end. `rvt.regdiff.unit0_runs / mine_record_order`.
2. **Our append-before-sentinel is a WRITE-ORDER inversion the reader
   tolerates [V]** — V20's proven created instance is the LAST record of
   unit 0, inside the OLDEST-episode (ep 277) run, with an ep-1016 row, and
   PASSED. Position is not audited.
3. **Only three singleton classes carry a universal ElemTable birth-vintage
   law [V, 6/6]:** the project `PenWidthTableElem` (m_famId −1),
   `AllProjectPhases`, `DBViewProject` — `creation_ep == 0` AND id `<5k`.
   Every other genesis singleton (Units, ProjectInfo, TrueNorth,
   ExternalParamLock, DaylightSourceIdSet, KeynoteTable, StructSettings,
   the MEP settings…) is birth in only 1–2 of the six files; the catalog
   classes (GStyle/Category/FillPattern/LinePattern/Material) are birth in
   ≤ 20 % of rows and span every id band.
4. **Built-in object-style rows are ROUTINELY registered fresh, high and
   late [V, 8,442 rows]:** 4,124 of the six samples' 8,442 built-in
   `GStyleElem` host rows are created == modified == user-modified in a
   fresh episode (> 0), un-owned, band ≥ `<500k`; rstbasic's own rows
   1,472,449–1,472,454 were created in episode 1015 (its second-to-last).
   A high-id, fresh-episode, un-owned catalog row is normal — C0's row
   breaks no law.
5. **Episode relationships are not audited for instances [V]:** 100 % of
   16,091 accepted FamilyInstance rows have creation < modified, yet V20's
   created instance carries ce == me == 1016 and PASSED.
6. **Singleton / catalog registrations are single scalar leaves [V]:** the
   project pen table lives ONLY in `AppInfoArr[38] PenWidthTableInfo
   .m_penWidthTableElemId`; a built-in style row ONLY in
   `AppInfoArr[28] CategoryTracking.m_gstyleData[i].m_gstyleId` (a map VALUE,
   not a key — re-pointing changes no ordering). Neither sits in a positional
   UET slot; the schema-typed walk finds no second mirror. Our re-point =
   exactly 3 changed bytes in `Global/Latest` (offsets 120,816 / 91,380);
   X0k's Latest is byte-identical to K1's.
7. **The registration-state ladder as observed by the reader** (all prior
   verdicts + these): registered leaf INTACT → PASS (K/R/M-line); leaf →
   DELETED id (dangling) → PASS (R5, R9); leaf NULLED while live → FAIL
   (P4, P6); registered element REMOVED → FAIL (K5, K6, K5a–d); leaf
   RE-POINTED to a fresh element (X0, C0) → FAIL once, **never yet passed**.

## Gotchas found (for KNOWLEDGE.md merge)

1. `commit_new_elements` IGNORES the plan's episodes and `original_id`
   (re-confirmed: X0k's plan asked for `(0,0,0)`, the row came out
   `(1016,1016,1016)`); it can never emit a birth-vintage or renumbered row.
   Any rank-2 probe needs it to honour `plan.creation_ep / original_id` first.
2. The typed ADocument walker (`GA.AdocGraphEditor`) lives in a TOOL; a
   compact `TypedIdWalker` now exists in `src/rvt/regdiff.py` for surfaces /
   referrer scans without importing tools (same typing rules: kind 0x0E +
   ElementId/Identifier, so the pen table's id 2 has no false positives).
3. `RegDoc` picks the host partition by matching the ElemTable count
   against the stream-header count (dach carries a second, empty partition).

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/commit.py`** — honour `plan.creation_ep`, `modified_ep`,
  `user_modified_ep`, `original_id` when given (rank-2 probes; the assembler's
  base of record if genesis mints birth rows).
* **`tools/genesis_controls.py`** — the rank-1 splitters keyed to X0k:
  `X0e` (X0k + episodes forced to K1's `(0,976,976)`), `X0p` (records
  PREPENDED into the newest-episode run instead of appended), `X0c` (X0k plus
  ONLY the leaf rewritten to a scratch id — pure re-point, no add/delete);
  **and a certified-copy control in EVERY upload round** (the deliverable §8).
* **`tools/genesis_substitute.py`** — an IN-PLACE mode for single-scalar-
  leaf classes (the fixer's `EditSession.replacement` primitive): zero
  registration dimensions change; pending the §8 control, the leading
  architecture for the K/X ladder.
* **KNOWLEDGE.md owner** — merge findings 1–7 and gotcha 1.
* **`docs/inbox/genesis-audit.md` / orchestrator** — strike "X_pen … subsumed
  by X0" (misattribution); adopt the certified-copy control rule.
* **`tools/sync_plugin.py`** — this stream adds ONE `src/` module
  (`src/rvt/regdiff.py`) to the plugin-drift list; the pre-existing
  `test_plugin_sync` failure stays red until the orchestrator's sync run.

## Verification

* `.venv/bin/python -m pytest tests/test_regdiff.py -q` → **12 passed**
  (K1's registration row/header/surface/position; the run law; X0's diff
  dimensions + verbatim records + the 3-byte Latest edit; the codec's
  byte-exactness; the single-leaf surface; the V20 calibration; the 0/0
  deletion collateral; X0k's Latest-identity + moved records; C0's leaf).
* `python -m rvt.regdiff` (demo) and `--mine` (six-sample census, ~4 s) run
  clean; every emitted probe re-verified validator-VALID
  (`tools/rvt_validate.py`); upload copies md5-identical to the builds.
* Full suite: see BRANCH STATE.

## Open questions (need the viewer / a decision)

* The §8 control round (certified copy + X0k + X_pen re-upload) — until it
  runs, X0/C0's FAILs are provisional and X_pen/X_cat's are unread.
* X0k's verdict (staged, unread) — the rank-1 vs rank-2/3 arbiter, only
  interpretable alongside the control.
* Whether the reader audits birth-vintage at all — no accepted file
  contains a re-added birth singleton; moot if the in-place mode is adopted.

## BRANCH STATE

* No VCS (plain directory). NEW, uncommitted files, this stream's territory
  only: `src/rvt/regdiff.py`, `tests/test_regdiff.py` (12 pass),
  `docs/writer/registration-diff.md`, `docs/inbox/genesis-forensics.md`
  (this file). NO existing `src/` module, tool, test or `.rvt` touched.
* DONE per charter: the complete diff table {K1-original, X0-ours,
  V20-instance-proven, corpus-invariant} across all five dimensions
  (deliverable §2–§6) and the RANKED list of X0's deviations from the
  singleton-class invariants that are NOT deviations in the proven instance
  path (deliverable §7, four ranks + retired items), plus the missing-control
  blocker (§8). No probes built (as chartered).
* Full suite this session (`.venv/bin/python -m pytest tests/ -q
  --ignore=tests/oracle`): **819 passed, 3 failed** of 822 (915 s). This
  stream's 12 tests are among the 819. The 3 failures are the pre-existing,
  other-stream ones every recent record lists — none touching this stream's
  files: `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source`
  (the plugin-bundle drift; this stream adds ONE `src/` module,
  `src/rvt/regdiff.py`, to that list — fix = the orchestrator's
  `tools/sync_plugin.py` run) and `tests/test_provenance.py::{test_G0_
  resource_refs_are_counted, test_G0_identity_dit_usernames_still_leak}`
  (the STALE assertions pinning the pre-genesis-2 G0 defects; owner: the
  provenance stream).
* STOPPED AT READY — the ranked list and the §8 control specification are
  the hand-off to the orchestrator / controls stream.

# genesis-addpath-probes — PER-RULE VERBATIM CONTROLS for the ADD PATH (workstream record, 2026-08-04)

Charter (ORCHESTRATOR VERDICTS #11, "THE ADD PATH IS THE BUG"): X0 (Autodesk's
OWN pen table, exact bytes, re-inserted through OUR add path at new id
1,500,000) and C0 (Autodesk's own catalog row verbatim via our path) BOTH FAIL
`Revit-DocumentCorruption`.  OUR OBJECTS ARE EXONERATED; the ADD PATH for
non-instance elements corrupts, while the family-INSTANCE add path is PROVEN
(V20..V29 created instances / walls / conduits / circuits LOAD).  Turn each
candidate deviation of the add path into a ONE-change probe FROM THE FAILING
X0 (or from the passing K1) so the reader tells us WHICH registration rule is
audited.

Territory touched ONLY (as chartered): `tools/genesis_addpath_probes.py`
(new), `tests/test_addpath_probes.py` (new, 45 pass), `experiments/genesis/
addpath/` (14 `.rvt` + 14 `.json` + `delta.json` + `probes.json`), this
record.  NO existing `src/rvt/*.py`, tool or test edited — every dependency
(`rvt.reduce` / `commit` / `adocument` / `identity` / `encode` / `objects`,
`tools/genesis_controls.py`, `genesis_substitute.py`, `genesis_assemble.py`)
is IMPORTED.  No viewer / browser use: the files are LEFT ON DISK with
`probes.json` (the ordered reading tree) for the orchestrator's queue.

## Result in one screen

**14 probe files built, EVERY ONE certified (validator 0 errors, structural
proof, target records re-decoded clean, ElemTable row / record position /
ADocument leaf / watermark exactly as intended, changed-stream set vs the
template EXACTLY the intended one change), 45/45 tests, with the two anchor
proofs holding: `P_all` (element 2 deleted and re-added through this stream's
own assembler with everything restored) is BYTE-IDENTICAL TO K1 IN EVERY
STREAM — the delete + re-add mechanics are LOSSLESS — and `P_x0` /
`P_sameid` are semantic twins of X0 / X0k (ElemTable model, ADocument tree,
unit-0 record bytes + order, identity fields all equal; the only raw
differences are reader-tolerated compression / junk cosmetics).**  Reproduce:
`.venv/bin/python tools/genesis_addpath_probes.py` (~3.5 min).

The probe set is DERIVED FROM THE MEASURED DELTA (below), not from the
brief's guesses — and two of the brief's named dimensions COLLAPSE onto X0
by measurement (owner, flags: byte-identical no-ops, no file, no upload).

## THE MEASUREMENT (`experiments/genesis/addpath/delta.json`, `--delta-only`)

Byte-comparing K1 (PASS) with X0 (FAIL) stream by stream, decoding both
ElemTables, both ADocument trees and both unit-0 record streams, the ENTIRE
difference between the passing registration and the add path's is:

| # | dimension | K1 (PASS) | X0 = our add path (FAIL) | streams touched |
|--:|---|---|---|---|
| 1 | **ID MOTION** | element id 2; watermark 1,472,524; ONE ADocument leaf `PenWidthTableInfo.m_penWidthTableElemId = 2` | id 1,500,000 (records' `m_id` + own deletion-list entry), watermark 1,500,000, the SAME single leaf = 1,500,000 (**the ADocument differs in EXACTLY ONE leaf** — measured over the full 6,571-reference tree) | Partitions, ElemTable, Latest |
| 2 | **EPISODES (vintage)** | ElemRec row 2 = (creation 0, modified 976, user_modified 976) — objlint's `ETR.created_at_birth`, TRUE in 6/6 project pen tables | (1016, 1016, 1016) = the parent's MAX modified episode ×3 (`commit_new_elements` IGNORES the plan's episodes) | ElemTable (12 bytes) |
| 3 | **RECORD POSITION** | the three per-seq records sit at index **2,516 of 6,541** in EACH seq (identical order in 101/102/103), immediately AFTER element 1 and BEFORE element 3 | APPENDED at the unit-0 END (index 6,539, before the sentinel) | Partitions |
| 4 | **IDENTITY** | K1's BasicFileInfo (`hansonje` path, `Autodesk Revit` author) + DIT usernames | our scrub: username/author/client_app `rvt-writer`, `last_save_path` = temp name; DIT usernames all `rvt-writer` (**V30/V31/V32-PROVEN** on the working base) | BasicFileInfo, DIT |
| — | *cosmetic* | K1's original block compression; 603-byte end-record (68-byte marker + inherited ECC-pad junk) | `commit_new_elements` RE-COMPRESSES all 281 blocks (embedded units included — 201/201 inflate identically, 0/201 members byte-identical) and appends one more junk generation (823-byte end record) | reader-tolerated (V15, V20..V29, K3/K4 PASS) — **not a candidate rule**; this stream's probes add none |

**COLLAPSED (measured, no file, no upload — recorded in `probes.json:collapsed_probes_no_file`):**
* **P_owner ≡ X0.**  The ElemRec owner is `0xFFFF…FF` (INVALID) in K1's row 2
  AND in X0's row; the pen table's ElementHeader has category −1, empty
  appearance/regen parents, deletion = [self] — the ElemTable owner is the
  only ownership channel and it is identical.  Byte-identical no-op.
* **P_flags ≡ X0.**  The 40-byte ElemRec HAS NO flag field
  (original_id, 3 episodes, id, owner, partition); X0's ElementHeader is
  Autodesk's own header with EXACTLY ONE decoded difference from K1's — its
  own `ElementParents.m_deletion[0]` entry 2 → 1,500,000 (the identity rebase
  = dimension 1).  The flag word `m_abFlags4Bytes` and every other header
  byte are identical (X0.json's byte-identity assertion re-verified here).

**The unit-0 record order is NOT id-sorted** (a new, load-bearing format
fact): 43 ascending id-runs; the max id 1,472,524 sits at position **131**
of 6,540 (in the FIRST run, with the newest content); the birth-vintage
block (ids 1, 2, 3, 4, … creation episode 0) starts at position **2,515**;
the LAST real record is id 49,026 (creation episode 277).  So "append at
the unit end" does NOT match where K1 keeps either its highest ids OR its
birth singletons.  (Creation episode is NOT monotone in id even in the
pristine samples — thousands of exceptions — so an id-vs-episode ordering
rule is ruled out.)

## THE PROBES (`experiments/genesis/addpath/`, `probes.json`)

Every probe carries AUTODESK'S OWN pen-table records (K1's element 2,
identity-rebased by the byte-exact codec when the id changes — the rebase is
proven byte-identical at the original id first, and the 1,500,000 rebase
reproduces X0's actual records byte-for-byte, tested), so NO probe can be
confounded by our object payload.  Each is built from a template's own
material (its true partition logical via `unframe_exact`, its ElemTable
model, its ADocument tree, its identity streams) with ONLY the intended
streams replaced — the certification asserts the changed-stream set equals
the intended one exactly.

### A. FROM-K1 SINGLES — the PRIMARY batch (K1 + ONE add-path deviation each)

| # | probe | ONE change vs K1 (PASS) | streams changed | PASS means | FAIL means |
|--:|---|---|---|---|---|
| 1 | **P_ep_only** | row 2's episodes (0,976,976) → (1016,1016,1016): a 12-byte ElemRec edit, NOTHING else | ElemTable | vintage alone tolerated | **ELEMTABLE VINTAGE IS A HARD RULE**: birth-vintage singletons must keep creation episode 0 / birth-era episodes; FIX = `commit_new_elements` honours an explicit `ElemRecPlan.creation_ep` + genesis mints birth-vintage classes at episode 0 |
| 2 | **P_pos_only** | element 2's own records MOVED from index 2,516 (after element 1) to the unit end | Partitions | position alone tolerated | **RECORD POSITION IS A HARD RULE** for this element (append-at-end is proven for instances only) — the writer must place non-instance elements at their canonical position |
| 3 | **P_allnew** | element re-registered at the NEW HIGH id 1,500,000 IN PLACE (records rebased at their original index, birth episodes, K1 identity, watermark raised, the ONE leaf re-pointed) | Partitions, ElemTable, Latest | id motion alone tolerated (a singleton CAN take a new high id) | **THE ID MOTION IS FATAL** — read P_lowid |
| 4 | **P_lowid** | as P_allnew but the new id is **27** (free, unreferenced in host graph AND ADocument, inside the birth band, watermark NOT raised) | Partitions, ElemTable, Latest | (with P_allnew FAILING) **the HIGH ID BAND is the rule** → allocate settings singletons LOW ids from birth | (with P_allnew FAILING) ANY re-registration of this element is fatal (the leaf re-point itself) → genesis must mint the pen table AT ITS CANONICAL id 2 |
| — | P_ident_only (optional) | the identity scrub alone (BFI + DIT), the V30..V32-proven path | BFI, DIT | expected | lineage-specific identity dependence (would contradict V30..V32) |

### B. FROM-X0 RESTORES — same round if capacity (X0 with ONE dimension restored)

| probe | ONE change vs X0 (FAIL) | streams changed | reads with |
|---|---|---|---|
| **P_ep** | row 1,500,000's episodes → (0,976,976) | ElemTable | P_ep_only: PASS here + FAIL there = vintage is the SOLE, closed diagnosis |
| **P_order** | the three appended records moved from the unit end back to the ORIGINAL position (right after element 1) | Partitions | P_pos_only; also the interaction detector (position × new id) |
| P_ident (optional) | K1's original BasicFileInfo + DIT restored | BFI, DIT | P_ident_only |

### C. FROM-X0k RESTORES — OPTIONAL (pre-built for the branch where X0k FAILS)

X0k (verdict PENDING, already queued) = pen table re-added AT ITS OWN id 2:
records at the unit end, episodes (1016,1016,1016), identity scrubbed,
**ZERO registry motion** (Global/Latest byte-identical to K1's — verified).
`P_sameid_ep` (episodes restored), `P_sameid_order` (records moved back to
the original position — the seq record streams then equal K1's exactly),
`P_sameid_ident` (identity restored): one restore each vs X0k.  Only
informative if X0k FAILS; with X0k PASSING the from-K1 singles already
answer everything at the same id.

### D. ANCHORS — NO UPLOAD (construction proofs)

* **P_all** = element 2 deleted and re-added through this assembler with
  ALL FOUR dimensions at K1's convention → **BYTE-IDENTICAL TO K1 IN EVERY
  STREAM** (asserted, tested).  PROVES the delete + re-add mechanics are
  LOSSLESS: nothing outside {the 3 records, the ElemTable row, the ONE
  ADocument leaf} encodes the element (no ordinal / offset table / hidden
  checksum), so the whole bug IS one — or an interaction — of the four
  dimensions.  Its verdict IS K1's (PASS): no upload.
* **P_x0** = ALL FOUR add-path deviations applied by this assembler →
  **SEMANTIC TWIN OF X0** (ElemTable model, ADocument tree, unit-0 record
  bytes + order, DIT usernames all equal; identity fields equal except
  `last_save_path`; the only raw differences are X0's block RE-compression —
  201/201 embedded blocks inflate identically, 0/201 compressed members
  identical — and one fewer junk generation).  PROVES this assembler is a
  faithful stand-in for `commit_new_elements`, so every from-K1 single
  genuinely reads as "the add path with all but one deviation removed".
* **P_sameid** = X0k's registration reproduced → semantic twin of X0k (same
  proof shape).  Verdict = X0k's: no upload.

## THE READING TREE (`probes.json:decision_tree`)

Given: K1 PASS, X0 FAIL, and P_all ≡ K1 byte-for-byte ⇒ the bug is one (or
an interaction) of {ID MOTION, EPISODES, POSITION, IDENTITY}.  Upload the
PRIMARY batch **P_ep_only, P_pos_only, P_allnew, P_lowid** (+ P_ep, P_order if
the round has room; X0k is already queued).

* **P_ep_only FAIL** ⇒ vintage is a hard rule (a 12-byte episode edit alone
  corrupts K1).  Fix and confirm with **P_ep PASS** (X0 rescued by episodes
  alone) — a closed, single-cause diagnosis.
* **P_pos_only FAIL** ⇒ record position is a hard rule for birth singletons
  (append-at-end is valid only for instance/type content) ⇒ the writer needs
  canonical placement; confirm with **P_order PASS**; the next bisect ("unit
  end" vs "birth-block start" vs "exact original slot") is buildable in
  seconds with this tool.
* **P_allnew FAIL** ⇒ registering the singleton at a new high id is fatal by
  itself; **P_lowid** then names it: PASS ⇒ the HIGH BAND (mint settings
  singletons at LOW ids); FAIL ⇒ any re-registration / leaf re-point of this
  element is fatal (mint the pen table at its canonical id 2, never move it).
* **Several from-K1 singles FAIL** ⇒ several independent rules; each named;
  the from-X0 restores say whether any single restoration suffices.
* **ALL from-K1 singles PASS while X0 FAILS** ⇒ an INTERACTION (a dimension
  fatal only combined with another, typically with the id motion) ⇒ read
  the from-X0 restores: P_ep PASS ⇒ vintage × new-id; P_order PASS ⇒
  position × new-id; none ⇒ 3-way ⇒ pairwise probes next round (each is one
  `probe_specs()` entry away).
* **Consistency with X0k**: X0k PASS predicts P_ep_only / P_pos_only /
  P_ident_only PASS and pushes the fault onto the id motion (expect P_allnew
  FAIL); X0k FAIL predicts one of those three FAILS and the matching
  P_sameid_* restore PASSES.

## Cross-stream observation the orchestrator MUST see: X_pen ALSO FAILED

`docs/coverage/viewer-certified.json` records `experiments/genesis/subst_v2/
X_pen.rvt` as FAILED in the same 00:25 batch as X0/C0.  X_pen is the
fixer's IN-PLACE probe (our pen-table object at ITS OWN id 2 via the
CERTIFIED modify path) — and, **measured here, X_pen differs from K1 in
`Partitions/21` ONLY** (BasicFileInfo, DIT, ElemTable, Latest byte-identical
to K1's; no add path, no identity scrub, no registry motion, record IN PLACE
at index 2,516).  **X_pen therefore convicts OUR PEN-TABLE PAYLOAD
independently of the add path** — a SECOND, separate bug that the "our
objects are exonerated" summary of verdicts #11 does not cover: X0/C0 prove
Autodesk's payload fails through our ADD PATH; X_pen proves our payload
fails WITHOUT it.  Both must be fixed for genesis.  This stream attacks only
the add path (every probe here carries Autodesk's payload); the fixer's own
tree names the payload follow-up (**X_pen_obj**: K1's own header, our object
body — never uploaded).

## New format / method findings (evidence — merge into KNOWLEDGE.md)

1. **The add path's COMPLETE registration delta is four dimensions [V,
   K1 vs X0 measured to the byte]**: id motion (records' identity + row id
   + watermark + exactly ONE ADocument leaf), ElemTable episodes
   (0,976,976 → parent max ×3), record position (mid-stream slot → unit
   end), identity scrub — and NOTHING else beyond reader-tolerated
   compression / trailing-junk cosmetics.  The pen table's ElementHeader
   flag word and ElemRec owner are NOT touched by the add path (both are
   Autodesk-identical in X0).
2. **Element registration is fully contained in {3 records, 1 ElemTable
   row, its ADocument leaf(s)} [V, P_all byte-identity]**: deleting an
   element and re-adding those parts identically reconstitutes the file
   BYTE-FOR-BYTE — there is no ordinal, offset table or per-element state
   elsewhere.
3. **The unit-0 seq record streams are NOT id-sorted [V, K1]**: 43
   ascending id-runs; max id at position 131; the birth-vintage block
   starts at position 2,515; the last record is a birth-era element; the
   three seqs carry IDENTICAL id order.  A record's stream position is an
   independent, potentially audited coordinate — "append at the unit end"
   matches neither K1's placement of its highest ids nor of its birth
   singletons.  Creation episode is NOT monotone in id (thousands of
   exceptions even in pristine samples).
4. **`commit_new_elements` re-compresses EVERY block, embedded family units
   included [V, X0 vs K1]**: all 201 embedded blocks inflate identically but
   0/201 compressed members are byte-identical to K1's; and each re-block
   generation appends the source's final-page ECC pad to the partition
   "end record" (K1 603 B, X0 823 B, K4 ~1.6 KB).  READER-TOLERATED (V15,
   V20..V29, K3/K4 PASS) ⇒ cosmetic; but see the delete_elements diff below
   — it is why no delete/commit product can be byte-identical to its parent.
5. **A file's TRUE partition logical must come from `unframe_exact()`, not
   the depaged `logical()` [V]**: `frame_stream(unframe_exact(raw)) == raw`
   byte-for-byte, whereas the depaged tail carries the final page's ECC pad
   region past the true end (that region is what accumulates as "end
   record" junk).
6. **The pen table (element 2) has ZERO host referrers and EXACTLY ONE
   ADocument reference** (`PenWidthTableInfo.m_penWidthTableElemId`) [V,
   typed graph + full-tree scan] — the ideal single-registry-leaf class for
   registration controls; id 27 is a free id, unreferenced in the host graph
   AND the ADocument, inside the birth band (the P_lowid target).

## Answers to the charter's byte-identity assertions

* **Can P_all be stream-identical to K1?**  YES — **BYTE-IDENTICAL IN EVERY
  STREAM**, not merely stream-identical (asserted per stream in
  `P_all.json:anchor_proof`, tested).  The delete + re-add mechanics are
  lossless and the whole bug is a registration DETAIL among the four measured
  dimensions.
* **Residual byte diff vs K1 per probe (asserted in each `.json:streams_vs.
  K1`)**: P_ep_only {ElemTable}; P_pos_only {Partitions}; P_ident_only
  {BFI, DIT}; P_allnew / P_lowid {Partitions, ElemTable, Latest}; the
  from-X0 / from-X0k probes carry their template's other three deviations
  (listed per probe).  In every case the residual is EXACTLY the intended
  dimension set — no probe carries an unaccounted byte.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/reduce.py::delete_elements` (reduce / manipulation owner)** —
  build the output from `unframe_exact(raw)` (the true logical) instead of
  `doc.logical()` and truncate the trailing region at the true end: today
  the depaged tail's final-page ECC pad is copied into the output logical,
  growing the "end record" ~65 B per re-block generation (K1 603 B → 668 B;
  K4 ~1.6 KB).  Reader-tolerated (K3/K4/KD1 PASS), so LOW priority — but it
  is why re-blocking K1 with zero deletions changes 65 bytes, and it made
  the "is X reblock-identical to its parent" question unanswerable until
  now.  This stream's `assemble_partition` is the reference (trail from the
  true logical; byte-identity proven by P_all).
* **`src/rvt/commit.py::commit_new_elements` (commit-layer owner)** —
  conditional on the verdicts: (a) honour `plan.creation_ep / modified_ep /
  user_modified_ep` (it IGNORES them today; the controls' gotcha 1 and the
  fixer's diff concur) so birth-vintage classes get episode 0 — required if
  P_ep_only FAILS; (b) a record-placement parameter (canonical position vs
  unit end) — required if P_pos_only FAILS; (c) it re-compresses every
  embedded-unit block (tolerated but gratuitous; a byte-copy of untouched
  units would make outputs diff-clean).
* **`tools/genesis_controls.py` / `genesis_substitute.py` (controls /
  substitute owners)** — the X-rung add path inherits all four deviations;
  once the verdicts name the rule, the substitution engine should register
  singletons IN PLACE / at low ids / with birth episodes / at canonical
  positions (the fixer's `id_map` in-place primitive already exists).
* **`docs/coverage/viewer-certified.json` (orchestrator)** — the failed
  entry for `X_pen.rvt` deserves its own note: it is NOT an add-path failure
  (Partitions-only, in place, all other streams K1-identical) — it convicts
  our pen payload; and the "our objects are exonerated" summary should be
  amended accordingly (§Cross-stream observation above).
* **`src/rvt/validate.py` (validation owner)** — none of the four
  dimensions is a validator rule today (every probe here and every FAILED
  add-path file scores VALID 0 errors); once a verdict names the rule
  (vintage / position / id band), add it as a consistency rule so a
  genesis candidate cannot score VALID while carrying it.
* **KNOWLEDGE.md owner** — merge findings 1–6.
* **`tools/sync_plugin.py`** — this stream adds NO `src/` module (a tool +
  tests + experiment files only) ⇒ nothing new for the plugin bundle; the
  pre-existing plugin-drift test is untouched by this stream.

## Open questions (need the viewer)

* The PRIMARY batch verdicts, read per the tree above: **P_ep_only,
  P_pos_only, P_allnew, P_lowid** (+ P_ep / P_order same round; X0k already
  queued).  Every `if_PASS` / `if_FAIL` branch is pre-stated in `probes.json`
  and in each `.json`.
* X0k's own verdict (queued before this stream) — it prunes half the tree
  (see "Consistency with X0k").
* Whether X_pen's payload conviction is confirmed by X_pen_obj (the fixer's
  pre-built object-only twin) — a second bug, outside this stream, that
  genesis needs closed regardless of the add-path verdicts.

## Proposed next tasks (orchestrator decides)

1. Upload the PRIMARY batch; read per the tree; the named rule's fix lands
   in `commit.py` (+ the substitution engine / genesis writer) — every fix
   candidate above is a small, localized change once the dimension is
   known.
2. If ALL four singles PASS: build the pairwise interaction probes (each a
   one-line `probe_specs()` entry; ~12 s each) — id×episodes, id×position,
   id×identity — and re-run.
3. Once the rule is named and fixed: re-derive X0 with the fixed add path
   (Autodesk's payload) as the acceptance gate for the fix, THEN re-open the
   X-ladder / genesis assembly — and separately close X_pen (our payload).
4. Fold `assemble_partition` / `load_material` (true-logical assembly, no
   junk, byte-identity-capable) into the writer's toolbox as the canonical
   partition assembler; fix `delete_elements`' tail per §Diffs.

## Verification

* `tools/rvt_validate.py --quiet experiments/genesis/addpath/*.rvt` → 14 ×
  `OK errors=0 warnings=1` (pasted below); per-file `.json:validator` +
  `structural` + `verify_written` + `intended_state` + `streams_vs` +
  `anchor_proof`.
* `.venv/bin/python -m pytest tests/test_addpath_probes.py -q` → **45
  passed** (14 s): the measured delta pinned (5 streams / 1 leaf / rows /
  positions / compression / collapses / free low id); assembler
  byte-exactness (partition round trip, reassembly identity, ElemTable
  re-encode identity, move-and-move-back identity, the 1.5M rebase equals
  X0's actual records, framed-record parsing); every probe certified with
  its exact one-change stream set, target position and watermark; the three
  anchor proofs; manifest consistency.
* Full suite: see BRANCH STATE.

## Reproduction (repo root, .venv python)

```
python tools/genesis_addpath_probes.py                # all 14 probes + delta.json + probes.json (~3.5 min)
python tools/genesis_addpath_probes.py --only P_all,P_ep_only
python tools/genesis_addpath_probes.py --manifest-only            # re-write probes.json
python tools/genesis_addpath_probes.py --delta-only               # the measured K1 vs X0 delta
python tools/rvt_validate.py --quiet experiments/genesis/addpath/*.rvt   # OK errors=0 (x14)
python -m pytest tests/test_addpath_probes.py -q      # 45 passed
```

Arbiter output (this session):

```
OK   experiments/genesis/addpath/P_all.rvt          errors=0 warnings=1   (== K1 byte-for-byte)
OK   experiments/genesis/addpath/P_allnew.rvt       errors=0 warnings=1
OK   experiments/genesis/addpath/P_ep.rvt           errors=0 warnings=1
OK   experiments/genesis/addpath/P_ep_only.rvt      errors=0 warnings=1
OK   experiments/genesis/addpath/P_ident.rvt        errors=0 warnings=1
OK   experiments/genesis/addpath/P_ident_only.rvt   errors=0 warnings=1
OK   experiments/genesis/addpath/P_lowid.rvt        errors=0 warnings=1
OK   experiments/genesis/addpath/P_order.rvt        errors=0 warnings=1
OK   experiments/genesis/addpath/P_pos_only.rvt     errors=0 warnings=1
OK   experiments/genesis/addpath/P_sameid.rvt       errors=0 warnings=1   (twin of X0k)
OK   experiments/genesis/addpath/P_sameid_ep.rvt    errors=0 warnings=1
OK   experiments/genesis/addpath/P_sameid_ident.rvt errors=0 warnings=1
OK   experiments/genesis/addpath/P_sameid_order.rvt errors=0 warnings=1
OK   experiments/genesis/addpath/P_x0.rvt           errors=0 warnings=1   (twin of X0)
```
The one warning is K1's own pre-existing extensible-storage decode gap (6
RebarShape + 1 DataStorage residue), present on K1 itself — untouched by
any probe.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files:
`tools/genesis_addpath_probes.py`, `tests/test_addpath_probes.py` (45
pass), `docs/inbox/genesis-addpath-probes.md` (this file), and under
`experiments/genesis/addpath/`: fourteen probes `P_ep_only P_pos_only
P_allnew P_lowid P_ident_only P_ep P_order P_ident P_sameid_ep
P_sameid_order P_sameid_ident P_all P_x0 P_sameid` (`.rvt` + `.json`
certification report each) + `delta.json` (the measured K1-vs-X0 delta +
the P_owner / P_flags collapse evidence) + `probes.json` (ordered manifest +
decision tree + upload plan).  Every emitted `.rvt` = validator VALID (0
errors), structural proof clean, target records / ElemTable row / record
position / ADocument leaf / watermark exactly as intended, changed-stream
set exactly the intended one change; P_all BYTE-IDENTICAL to K1; P_x0 /
P_sameid semantic twins of X0 / X0k.  Full suite this session
(`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`): **864
passed, 3 failed** of 867 (933 s).  This stream's 45 tests are among the
864.  The 3 failures are the pre-existing, other-stream ones every recent
record lists, none touching this stream's files: `tests/test_plugin_sync.py
::test_plugin_is_in_sync_with_source` (the plugin-bundle drift — this
stream adds NO `src/` module, so nothing new to sync; fix remains the
orchestrator's `python tools/sync_plugin.py` run) and `tests/
test_provenance.py::{test_G0_resource_refs_are_counted,
test_G0_identity_dit_usernames_still_leak}` (the STALE assertions pinning
the pre-genesis-2 G0 defects; their owner's diff is in docs/inbox/
genesis-2.md).  STOPPED AT READY — the PRIMARY batch (P_ep_only, P_pos_only, P_allnew, P_lowid) +
the SECONDARY (P_ep, P_order) await the orchestrator's viewer gate; the
reading tree is in `probes.json` and above; the X_pen cross-stream
observation is flagged for the orchestrator.

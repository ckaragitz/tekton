# THE REGISTRATION DIFF — how our add path registers a singleton/catalog element vs Autodesk's own registration vs the PROVEN instance path

Stream **genesis-forensics** (2026-08-04). Instrument: `src/rvt/regdiff.py`
(`registration_of`, `diff_registrations`, `unit0_runs`, `mine_*`), tests
`tests/test_regdiff.py` (12 pass), record `docs/inbox/genesis-forensics.md`.
Everything below was **measured this session** on the exact files the reader
judged; commands are in §9. No `.rvt` was written and no other stream's file
was edited.

The charter: ORCHESTRATOR VERDICTS #11 — **X0** (Autodesk's OWN pen table,
byte-exact, re-inserted through OUR add path at new id 1,500,000) and **C0**
(Autodesk's own object-styles row 34 verbatim through our path) both FAIL
`Revit-DocumentCorruption`, while the family-INSTANCE add path (V20..V29) is
viewer-PROVEN. Since X0/C0 hold the CONTENT byte-identical to the accepted
specimen, the corruption must live in the REGISTRATION delta. This document
measures that delta, field by field, in five dimensions, calibrates each
dimension against the proven instance path and against six-sample corpus
invariants, and ranks the residual.

---

## 0. One-screen verdict

**Every registration dimension our add path changes has been measured to the
byte.** Ranked by "unique to X0/C0 and never present in any viewer-PASSED
file" (the full argument is §7):

| rank | X0/C0 deviation | in V20 (proven)? | corpus law broken? | measured evidence |
|:--:|---|:--:|:--:|---|
| **1** | **The DELETE + REGISTRY VALUE-REWRITE**: the original registered element is deleted and its ADocument registry leaf (a scalar `PenWidthTableInfo.m_penWidthTableElemId` / a `CategoryTracking.m_gstyleData[i].m_gstyleId` value) is rewritten from the old id to the fresh id. | **NO** — V20 registers nothing and deletes nothing | no law exists — the operation has simply **never occurred in any accepted file** | §5: exactly ONE typed leaf changes (3 payload bytes, offsets 120,816 / 91,380); the codec is byte-exact; §6: 0 referrers, 0 owned rows for both originals |
| **2** | **Birth-VINTAGE row rewritten to a fresh episode** (pen table): ElemTable row (0, 976, 976) → (1016, 1016, 1016), id 2 → 1,500,000 (band `<5k` → `<5M`), `created_at_birth` TRUE → FALSE. | the (1016,1016,1016) SHAPE is shared with V20; the CLAIM "birth singleton born in episode 1016" is not | project pen table = ce 0 & id `<5k` in **6/6** samples; **but C0's identical row change breaks NO law** (§4: 4,124 accepted built-in style rows carry C0's exact fresh-episode/high-band/un-owned signature) — so vintage CANNOT explain C0 and is not NEEDED to explain X0 | §4 |
| **3** | **Record moved to the END of unit 0** (index 2,516 → 6,539, into the OLDEST-episode run, modal ep 277) — an inversion of the (modified_ep DESC, id ASC) stream law of §3. | **YES — identically**: V20's created instance is also the LAST record, also in the ep-277 run | the law is a write-order artefact; V20 violates it identically and PASSES | §2, §3 — **EXONERATED as a solo cause** |
| 4 | `original_id` = new id (no renumbering trail); watermark jump 1,472,524 → 1,500,000 (27,475-id gap) | V20: original_id = new id too; V20 bumps by exactly +1 | `renumbered` is 0–3 % everywhere; no accepted file has a re-added singleton | §4 — weak, listed for completeness |
| — | ElementHeader / object body | identical machinery | — | §2: byte-identical modulo the id leaves; the header carries NO episode mirror (`m_regenHistory.m_historyMap` empty) — **retired** |
| — | identity scrub (BasicFileInfo / DIT usernames) | V30/V31/V32 certified | — | **retired** (proven on the same rst lineage) |
| — | re-block / stamps / Latest re-encode / seq-order coherence | K1, K3, K4, KD1, R5, R9, L1a, M3, M4 | — | §5/§6: 0/13,080 stamp mismatches; Latest diff = the one leaf; seq orders 101==102==103 — **retired** |

**Reading:** the dimension that is UNIQUE to X0 ∩ C0, absent from every
viewer-PASSED file, and NOT explainable away by any corpus law is rank 1: a
live registry leaf re-pointed from a deleted element to a freshly registered
one. Rank 2 (vintage) is an *additional* candidate for the pen table only,
falsified as a *common* cause by C0. Rank 3 (position) is retired by V20.

**BUT — read §8 before acting on any of this.** The same viewer round that
convicted X0/C0 ALSO convicted **X_pen** and **X_cat**, which are IN-PLACE
payload probes (measured here: every non-partition stream raw-identical to
K1's, the pen-table records at their ORIGINAL position 2,516 with the seq-101
header byte-identical — §2). X_pen's change set is DISJOINT from X0's. Two
orthogonal probes both failing is logically over-determined: either there are
two independent load-time constraints (registration AND our pen doubles), or
the ~00:25 round is not a reliable instrument — and NO known-PASS control has
been uploaded in the last four rounds (12 consecutive FAILs since L1a ~21:05).
§8 states the required control before genesis-7 spends another round.

---

## 1. The three subjects and the corpus

| file | element | verdict | role |
|---|---|---|---|
| `experiments/genesis/triage/K1.rvt` | id **2** (project `PenWidthTableElem`); id **34** (built-in `GStyleElem`, OST_Windows projection) | viewer **PASS** | Autodesk's own registration of the two convicted elements |
| `experiments/genesis/controls/X0.rvt` | id **1,500,000** (K1's element 2, byte-exact, through OUR add path) | viewer **FAIL** | the singleton add path under test |
| `experiments/genesis/controls/C0.rvt` | id **1,500,000** (K1's row 34, byte-exact, through OUR add path) | viewer **FAIL** | the catalog-row add path under test |
| `experiments/genesis/controls/X0k.rvt` | id **2** (K1's element 2 deleted then re-appended AT ITS OWN id) | **pending** | the add-path bisector (holds Latest byte-identical) |
| `experiments/acceptance/V20_first_created_element.rvt` | id **1,472,525** (created `FamilyInstance`, watermark + 1) | viewer **PASS** | the PROVEN add path — the calibration column of every table |
| `experiments/genesis/subst_v2/X_pen.rvt` | id **2** (K1's pen table replaced IN PLACE by OUR payload) | viewer **FAIL** (§8) | the payload-only probe (no registration change at all) |
| six 2026 samples (`extracted/`) | 128k host elements | Autodesk-authored | the corpus laws (§3, §4) |

---

## 2. Dimensions 1–2: the ElemTable row and the ElementHeader — field by field

`registration_of(file, id)` (this stream's `src/rvt/regdiff.py`) decodes the
40-byte `ElemRec`, the seq-101 `ElementHeader`, and the object identity.

### 2.1 The ElemTable row (all 7 fields; `<QIIIQQI>`)

| field | **K1 id 2** (Autodesk, PASS) | **X0 id 1,500,000** (ours, FAIL) | **X0k id 2** (ours, pending) | **V20 id 1,472,525** (ours, PASS) | corpus invariant (project pen table, 6 files) |
|---|---|---|---|---|---|
| `m_history.originalElementId` | 2 | 1,500,000 | 2 | 1,472,525 | `renumbered` false in **6/6** (orig == id) — ours conforms |
| `m_history.creationDate` | **0** | **1016** | **1016** | 1016 | **0 in 6/6** (birth) — **X0/X0k VIOLATE** |
| `m_history.lastModificationDate` | 976 | 1016 | 1016 | 1016 | ≥ creation; the pen table sits in its run's episode (976) |
| `m_history.lastUserModificationDate` | 976 (set) | 1016 (set) | 1016 (set) | 1016 (set) | never `0xFFFFFFFF` for the project table (6/6) — ours conforms |
| `m_id` | 2 | 1,500,000 | 2 | 1,472,525 | id band **`<5k` in 6/6** — **X0 violates** (`<5M`); X0k conforms |
| `m_OwningElementId` | INVALID | INVALID | INVALID | INVALID | un-owned in 6/6 project tables — ours conforms |
| `m_partitionId` | 0 | 0 | 0 | 0 | 0 in 128,331/128,331 corpus rows — ours conforms |
| index in the id-sorted table | 1 of 6,540 | **6,539 of 6,540** (last) | 1 | 13,936 (last) | table is id-sorted (6/6) — ours conforms (highest id ⇒ last) |
| footer `IdentifierSource.m_last` | 1,472,524 | **1,500,000** (+27,476) | 1,472,524 | 1,472,525 (+1) | monotone highest-ever-issued; racbasic exceeds max id by 96 |

Our add path (`rvt.commit.commit_new_elements` → `streams_edit.elemtable_add_element`)
writes `(original_id = new id, creation = modified = user_modified = max(modified_ep of the parent))` —
**it never reproduces a birth-vintage row and it ignores the plan's episodes**
(the controls' gotcha 1, re-confirmed by X0k: its plan asked for episodes
`(0,0,0)` and the row came out `(1016,1016,1016)`).

### 2.2 The ElementHeader (seq 101) and the object identity (seq 102)

Full decode of K1's element-2 header (16 fields) and X0's:

```
m_regenHistory   {m_historyMap: []}        <- EMPTY: the header carries NO episode/history mirror
m_categroryId    -1        m_familyId -1     m_ownerViewId -1    m_designOptionId -1
m_unplacedOwnerId -1       m_miscId -1
m_viewRules      {m_nVisibleViewFlags: -32768}
m_abFlags4Bytes  8222      m_classDef {classref: PenWidthTableElem}   m_pBBox null
m_parents        ElementParents {m_deletion: [2], m_regenOnly: [], m_regenWildcards: [],
                                 m_nonDetermRegenChildren: [], m_dependency ..., m_appearanceParents: []}
```

Field-level diff K1(id 2) vs X0(id 1,500,000): **exactly two leaves change**,
both id-implied:

* header `.m_parents.value.m_deletion[0]`: `2 → 1,500,000`
* object `.m_id`: `2 → 1,500,000`

Byte-level, the FRAMED records (header + payload + trailer):

| seq | framed bytes | differing bytes X0 vs K1 | offsets | meaning |
|--:|--:|--:|---|---|
| 101 (ElementHeader) | 135 | **6** | 0–2, 90–92 | i64 record id; the `m_deletion` self entry |
| 102 (object) | 1,223 | **10** | 0–2, 8–11, 54–56 | i64 record id; the recomputed adler32 stamp; `Element.m_id` |
| 103 (SerializedDummy) | 22 | **3** | 0–2 | i64 record id |

X0k's three records are **byte-identical** to K1's (same id, same stamp
`0xf92cf70f` = `adler32(u16 class ‖ body)`, verified). The stamp mechanism is
correct in every file measured (**0 mismatches / 13,080** stamped records in
K1, X0, X0k and X_pen). **Verdict: our identity rebase touches only the two
id-implied leaves; the constructor, header machinery, stamp and rep are
Autodesk-identical — retired as suspects for X0/C0.**

X_pen (the in-place payload probe, for contrast): seq-101 header
**byte-identical** to K1's; seq-102 object differs in **684 bytes** — the
126 pen-width doubles (our ISO series vs Autodesk's) plus the stamp bytes
8–11; identical top-level keys, identical scale keys `{10,20,50,100,200,500}`,
identical perspective/draft `-1` scales, header decoded-equal. So **X_pen's
change set ∩ X0's change set = ∅**.

---

## 3. Dimension 3: RECORD POSITION — the unit-0 stream is NOT id-sorted; it is runs grouped by MODIFIED episode, newest first

### 3.1 The corpus law (`rvt.regdiff.mine_record_order`, all six samples)

The host document's three parallel seq streams (101/102/103) carry
**identical element orders** in every file measured (K1, X0, X_pen, V20).
That order is **not** id-ascending as a whole; it is a sequence of maximal
id-ascending RUNS, and each run is (modally) one MODIFIED episode, ordered
**newest-modified run FIRST, oldest LAST**:

| sample | host recs | runs | single-episode runs | adjacent-id-ascending | run modal-episode strictly descending | head episodes → tail |
|---|--:|--:|--:|--:|:--:|---|
| rstbasic | 13,936 | 46 | 34 | 0.9968 | **yes (0 violations)** | 1016,1015,1014,1013,1011,… → 660,623,551,277 |
| rstadv | 13,855 | 184 | 126 | 0.9868 | 8 violations / 183 pairs | 578,577,575,… → 4,3,1,0 |
| racbasic | 8,401 | 119 | 90 | 0.9859 | 2 / 118 | 847,846,844,… → 410,294,277 |
| racadv | 17,231 | 185 | 132 | 0.9893 | 11 / 184 | 616,615,613,… → 3,2,1,0 |
| rme | 28,132 | 216 | 163 | 0.9924 | 8 / 215 | 795,794,792,… → 3,2,1,0 |
| dach | 49,776 | 175 | 131 | 0.9965 | 4 / 174 | 2738,2686,2736,… → 2353,2352 |

Read: each save wrote its dirty elements as one id-ascending segment,
newest saves written FIRST (a compaction that copies the previous stream
behind the fresh segment). An element's records sit **in the run of ITS OWN
last-modified episode**: rstbasic's element 2 (row modified_ep 976) sits at
host index 9,889 of 13,936, immediately after id 1 (`AllProjectPhases`),
inside the ep-976 run of settings/catalog elements
(`GStyleElem` 1,507, `ParamElemExternal` 466, `CategoryElem` 337, the
fill patterns, ids 1..1,454,521). Birth-episode singletons therefore live
DEEP INSIDE the stream in their mid-history episode group — never at the
front, never at the end. Confidence **HIGH** (statistical, six files; the
larger files show a few percent of non-descending adjacent run pairs where
minority-episode records sit in a run — the law is modal, not exact).

### 3.2 Where each subject's records sit (seq 102 unit 0; 101/103 identical)

| subject | index / total | run (index/of) | run's modal modified_ep | own row modified_ep | prev id / next id | consistent with law? |
|---|---|---|--:|--:|---|:--:|
| K1 id 2 | **2,516** / 6,540 | 19 / 43 | **976** | 976 | 1 / 3 | ✓ |
| X0 id 1,500,000 | **6,539** / 6,540 (LAST) | 42 / 43 | **277** (oldest) | 1016 | 49,026 / — | ✗ (ep-1016 element inside the ep-277 run) |
| X0k id 2 | 6,539 / 6,540 (LAST) | 42 / 43 | 277 | 1016 | 49,026 / — | ✗ |
| C0 id 1,500,000 | 6,539 / 6,540 (LAST) | 42 / 43 | 277 | 1016 | 49,026 / — | ✗ |
| **V20 id 1,472,525 (PASS)** | **13,936 / 13,937 (LAST)** | 45 / 46 | **277** | 1016 | 49,026 / — | **✗ — and it PASSED** |

Our add path appends the three records immediately BEFORE each seq's
sentinel = the LAST position of unit 0 = inside the OLDEST-episode run. A
real Revit save would have PREPENDED them (newest-modified first). **V20's
proven created instance sits at the identical position class (last record,
ep-277 run, ep-1016 row) and PASSED — so the reader does NOT audit record
position against the episode law.** Position is exonerated as a solo cause
(confidence **HIGH**: a certified counter-example, not an inference). The only
residual question ("is position audited for SINGLETON classes but not for
instances?") is answered by X0k, which shares the position defect and holds
the registry constant.

---

## 4. Dimension 1-corpus: ElemTable-row INVARIANTS per class — where the constructed classes differ from FamilyInstance

`rvt.regdiff.mine_elemtable_invariants` over all 128,331 host rows of the six
samples (project cohort; PenWidthTableElem restricted to `m_famId == -1`):

| class | n | birth (ce=0) | creation_ep hist 0/1/2/3+ | id bands | renumbered | owned | usermod-never | in run matching own modified_ep |
|---|--:|--:|---|---|--:|--:|--:|--:|
| **PenWidthTableElem** (project) | 6 | **1.00** | {0: 6} | **{`<5k`: 6}** | 0.00 | 0.00 | 0.00 | 1.00 |
| **AllProjectPhases** | 6 | **1.00** | {0: 6} | {`<5k`: 6} | 0.00 | 0.00 | 0.00 | 0.67 |
| **DBViewProject** | 6 | **1.00** | {0: 6} | {`<5k`: 6} | 0.00 | 0.00 | 0.00 | 1.00 |
| UnitsElem / ProjectInfo / ExternalParamLock / DaylightSourceIdSet / KeynoteTable | 6 | 0.17 | {0: 1, 3+: 5} | `<50k`/`<500k` (dach `<5k`) | 0.00 | 0.00 | 0.00 | 0.83–1.00 |
| TrueNorth | 6 | 0.33 | {0: 2, 3+: 4} | `<50k` 4 / `<5k` 2 | 0.00 | 0.00 | 0.00 | 1.00 |
| PhaseFilterElem | 50 | 0.48 | mixed | mixed | 0.00 | 0.00 | 0.00 | 0.82 |
| **GStyleElem** (all) | 17,115 | 0.10 | {0: 1680, 3+: 15360} | `<5M` 7,845 / `<500k` 6,371 / `<5k` 1,826 | 0.01 | **0.51** (sub-category rows → `CategoryElem`) | 0.00 | 0.69 |
| **CategoryElem** | 8,227 | 0.02 | {0: 152, 3+: 8005} | spread | 0.02 | **0.92** | 0.01 | 0.42 |
| FillPatternElem / LinePatternElem / MaterialElem | 485–1,068 | 0.09–0.20 | mixed | spread over every band | ≤0.02 | 0.00 | 0.00 | 0.97–1.00 |
| TextNoteAttributes / FontElem / Viewer / Viewport / DBDrawing | 507–5,982 | ≤0.02 | mostly 3+ | mostly `<5M` | ≤0.03 | **0.97–1.00** (the ownership web) | ≤0.05 | 0.14–0.39 |
| **FamilyInstance** (PROVEN class) | 16,091 | **0.00** | {3+: 16091} | `<500k` 8,238 / `<5M` 7,853 | 0.01 | 0.58 (hosted) | 0.30 | 0.68 |
| SWall / FamilySymbol / Family / RbsElectricalSystem / RbsConduitType | 20–2,715 | 0.00–0.01 | 3+ | high bands | ≤0.01 | ≤0.06 | ≤0.50 | 0.5–1.0 |

Two facts fall out that the ranking depends on:

1. **The only universal (6/6, zero counter-examples) ElemTable laws in the
   whole singleton set are the birth-vintage of exactly three classes** —
   the project `PenWidthTableElem`, `AllProjectPhases`, `DBViewProject`
   (`creation_ep == 0` AND id `<5k`). Every other genesis singleton is birth in
   only 1–2 of the six files; the object-styles catalog classes are birth in
   ≤ 20 % of rows.
2. **The C0 row is 100 % corpus-normal.** Counting built-in `GStyleElem` host
   rows (`m_famId == -1`, built-in category) across the six accepted samples:
   8,442 rows; only 1,524 (18 %) are birth; bands {`<500k` 4,018, `<5M`
   2,200, `<5k` 1,524, `<50k` 700}; and **4,124 of 8,442 carry C0's exact row
   signature — created == modified == user-modified in a FRESH episode > 0,
   un-owned, band ≥ `<500k`.** rstbasic itself (K1's own ancestor) has
   built-in style rows **1,472,449..1,472,454 created in episode 1015** — the
   second-to-last episode — at ~1.47 M ids. Revit *routinely* registers
   built-in object-style rows at high ids in late episodes (when a category
   first appears). **C0's failure therefore cannot come from ANY ElemTable-row
   property.** And since C0 and X0 fail with the same signature, the
   parsimonious common cause excludes the row for X0 too.
3. Calibration in the other direction: **100 % of the 16,091 accepted
   `FamilyInstance` rows have creation_ep < modified_ep, yet V20's created
   instance carries creation == modified == 1016 and PASSED** — the reader
   does not audit episode relationships for instances at all.

X0's *specific* row (a project pen table, `m_famId == -1`, at a fresh
episode / high id / un-owned) has **no accepted counterpart**: the 6 project
tables are all birth `<5k`; the 50 family-scoped tables are all non-birth but
are a different cohort. So rank 2 (vintage) stays a live *additional*
candidate for the pen table specifically — an inference from universality
(confidence **MEDIUM**), never a measured cause.

---

## 5. Dimension 4: the ADocument — the identity rebase touches EXACTLY ONE registry leaf

`RegDoc.adoc_surface` (schema-typed walk of all 14,812 ElementId-typed
leaves of K1's `Global/Latest`, 1,586,246 inflated bytes):

| element | typed leaves holding it in K1 | leaf | in X0/C0 |
|---|--:|---|---|
| id 2 (pen table) | **1** | `ADocument.m_pAppInfoManager->AppInfoManager.m_appInfoArr[38]->PenWidthTableInfo.m_penWidthTableElemId` | value `2 → 1,500,000` |
| id 34 (catalog row) | **1** | `ADocument.m_pAppInfoManager->AppInfoManager.m_appInfoArr[28]->CategoryTracking.m_gstyleData[1402].m_gstyleId` | value `34 → 1,500,000` |

Both registrations are single scalar VALUES — not map keys — so re-pointing
changes no ordering / no key sort. Neither element sits in a positional
`UniqueElementsTracking` slot; neither has any second (untyped) mirror the
walk can miss. Byte-level, the whole inflated `Global/Latest` payload of X0 vs
K1: **length identical (1,586,246), exactly 3 differing bytes** at offset
120,816 — the little-endian i64 leaf value `02 00 00 00 …` → `60 e3 16 00 …`;
C0: 3 bytes at offset 91,380 (`22 …` → `60 e3 16 …`); X0k: **0** differing
bytes. The ADocument codec is byte-exact on K1 (`decode → encode == payload`,
1,586,246 B; `tests/test_regdiff.py::test_adocument_codec_byte_exact_on_k1`).
**Verdict:** the registry motion of our add path is a single, coherent,
minimal value edit; the re-serialization is exonerated (confidence **HIGH**).
What is NOT exonerated is the *operation itself*: no viewer-PASSED file in
the whole certification history contains a registry leaf whose value was
rewritten from a deleted element to a freshly registered one. Dangling leaves
(value → a deleted id) are tolerated (R5, R9 PASS); nulled live leaves are
fatal (P4, P6 FAIL); removed singletons/catalog rows are fatal (K5, K6 FAIL);
a **re-pointed** live leaf (X0, C0) has now failed once and never passed.

---

## 6. Dimension 5: the DELETION of the original — collateral measured

The delete half (`rvt.reduce.delete_elements` inside the substitution
engine's stage B) removes the original's three unit-0 records and its ElemRec.
Measured collateral on K1 (independent typed re-derivation, host + all 52
embedded units, `rvt.regdiff.inbound_referrers`):

* id 2 (pen table): **0 typed inbound referrers**, owns **0** ElemTable
  rows, own `m_OwningElementId` = INVALID, `m_parents.m_appearanceParents` /
  `m_regenOnly` empty. Removing it leaves nothing dangling except the one
  registry leaf, which the engine re-points (§5).
* id 34 (catalog row): **0** referrers, owns 0 rows, un-owned. (The controls
  stream chose it for exactly that property; C0all covers the 1,348-row
  referrer-free population.)
* K1 carries **0 renumbered rows** (`original_id ≠ id`), 4,847 rows with
  `creation ≠ modified` and 63 `user_modified = never` rows — our delete/add
  touches only the target row, so the table's episode texture is preserved,
  and every save-history cross-invariant still holds on X0/X0k/C0
  (`History count 1017 == max(modified_ep) 1016 + 1`; DIT/BFI mirrors).

The deletion mechanics themselves are certified (M2_delete_cascade,
K1..K4, R5, R9 — thousands of typed deletions). What is NOT certified is
deleting a REGISTERED singleton/catalog row (K5/K6/K5a-d prove that removing
one *without* replacement is fatal) — which is why X0/C0's delete only ever
occurs together with the rank-1 re-point.

---

## 7. Deviations of X0 from the singleton-class invariants, RANKED (the deliverable list)

Every deviation of X0's registration from K1's, marked whether the PROVEN
instance path (V20) shares it and whether a corpus law is broken. The
controls stream turns this list into one-change files.

| # | deviation (X0 vs K1's registration of the same element) | shared by V20? | corpus law broken? | discriminating probe | confidence it is load-bearing |
|:--:|---|:--:|:--:|---|---|
| **1** | Registry leaf value rewritten `2 → 1,500,000` while the original element 2 is DELETED (the delete + re-point of a REGISTERED singleton). C0's exact analogue (`CategoryTracking` value `34 → 1,500,000` + row 34 deleted) fails identically **with a row that breaks no law (§4)**. | NO | none exists — never occurred in an accepted file | **X0k** (deletes + re-appends id 2 with `Global/Latest` byte-identical to K1's): X0k PASS ⇒ rank 1 confirmed; X0k FAIL ⇒ ranks 2/3-mechanics instead. Also **C0all** + **R2s** for the catalog scale. | **HIGH** as the leading candidate: it is the ONE dimension in X0 ∩ C0 that no passing file has, and §4 falsifies vintage as the common cause. |
| **2** | ElemTable row of a birth-vintage singleton rewritten `(orig 2, ce 0, me 976, ue 976, id 2)` → `(1.5M, 1016, 1016, 1016, 1.5M)`: `created_at_birth` TRUE→FALSE, band `<5k`→`<5M`. | the (ep,ep,ep) shape yes; the birth-singleton claim no | **YES**: project pen table ce=0 & `<5k` in 6/6 | X0k holds this defect at the ORIGINAL id (still (1016×3) but band `<5k`); a `--creation-ep 0` re-mint (needs `commit_new_elements` to honour `plan.creation_ep` — proposed diff §10) isolates it fully. | **MEDIUM** — universal law with zero counter-examples, but falsified as the *common* X0+C0 cause by §4; an *additional* pen-table constraint at most. |
| **3** | Records appended at the END of unit 0 (index 6,539, ep-277 run) instead of prepended into the newest-episode run / left at index 2,516. | **YES, identically** (V20 last, ep-277 run) | write-order law inverted — but V20 inverts it identically and PASSES | none needed — retired by V20; X0k re-confirms for the singleton class specifically. | **LOW** (a certified counter-example exists). |
| **4** | `original_id` = the new id (no renumbering trail: a real renumber keeps the birth id in `originalElementId`); watermark jump `1,472,524 → 1,500,000` (a 27,475-id hole) vs V20's +1. | orig==id yes; +1 vs jump no | `renumbered` 0.00–0.03 corpus-wide; racbasic's watermark exceeds its max id by 96 (holes are normal) | fold into the rank-2 re-mint (`original_id = 2`, id = watermark+1). | **LOW**. |
| **5** | Identity scrub (`BasicFileInfo` author/GUID text, DIT usernames) — X0/X0k/C0 carry it; K1 does not. | V20 predates it | — | V30/V31/V32 certified the exact path | **RETIRED**. |
| — | ElementHeader / object / rep bytes; stamps; block re-chunk; seq-order coherence; `Global/Latest` re-encode; History/DIT/BFI cross-invariants | — | — | — | **RETIRED** (§2, §5, §6). |

**The decision the next round makes:** X0k separates rank 1 from ranks 2–4
in one verdict (it holds `Global/Latest` byte-identical to K1's — no id
change, no registry rewrite — while sharing the position defect, the
fresh-episode row and the identity scrub). Read it *only alongside a
known-PASS control* (§8).

---

## 8. THE CONTROL THE INSTRUMENT IS MISSING (blocking recommendation)

Measured stream-level composition of the two "in-place payload" probes the
fixer stream built (`experiments/genesis/subst_v2/`):

| stream | X_pen vs K1 | X_cat vs K1 |
|---|---|---|
| every non-partition stream (BasicFileInfo, Contents, Formats/Latest, ContentDocuments, DIT, ElemTable, History, **Global/Latest**, PartitionTable, ProjectInformation, TransmissionData) | **raw byte-identical** | **raw byte-identical** |
| `Partitions/21` | +16 logical bytes (element 2's seq-102 object = our pen doubles at the ORIGINAL position 2,516; seq-101 header byte-identical; block gzip recompression) | −1,476 logical bytes (1,407 rows' objects ours, in place) |

So X_pen changes NOTHING but the pen-table object payload (registration,
position, row, header, registry all K1's own), and it is recorded as FAILED
in the same ~00:25 round as X0 (registration-only, content verbatim).
**X_pen ∩ X0 = ∅** (measured). Both failing means either two independent
constraints exist (the add path AND our pen doubles) — in which case the
whole in-place fallback the fixer stream proposes is void — or **the round
did not discriminate**. Facts supporting the second reading:

* The last viewer PASS on record is **L1a (~21:05)**. Since then **12
  consecutive FAILs** across four rounds (22:50: R2/X5/X9/R1/R3; 23:11: X1;
  ~00:25: X0/X_pen/X1u/X_cat/C0), and **not one known-PASS control was
  uploaded in any of those rounds**. Per the fleet rule *"zero successes over
  N events is a defect signature, not silence"*, an instrument that has read
  12 fails and 0 passes with no positive control is uncalibrated.
* ORCHESTRATOR VERDICTS #11 states *"X_pen, X_cat, X1u also FAIL (now
  uninterpretable — subsumed by X0)"*. **X_pen is NOT subsumed by X0** — it
  is the orthogonal probe (the fixer's own record says so, and the stream
  diff above proves it). If its FAIL is real, it independently convicts OUR
  PEN-TABLE PAYLOAD (126 doubles, structure and header specimen-exact) —
  which would falsify verdict #11's headline *"our objects are exonerated"*.
* The upload copies are byte-identical to the certified builds
  (md5-verified: X0, X0k, X1u, C0, C0all, C1u, X_pen, X_cat) and every one is
  validator-VALID — no staging artefact explains anything.

**Recommendation (do this before reading X0k or building genesis-7):**
upload, in ONE round, a **byte-identical copy of an already-CERTIFIED file**
(e.g. `experiments/genesis/triage/K4.rvt`, renamed) **together with X0k and
a re-upload of X_pen**. Then:

| control (certified copy) | X_pen | X0k | reading |
|:--:|:--:|:--:|---|
| PASS | PASS | PASS | the ~00:25 round was bad; X0/C0's convictions are ALSO suspect — re-upload X0/C0 with the control |
| PASS | PASS | FAIL | rank 2/3 mechanics (row episodes / position) — re-mint birth-vintage in place |
| PASS | FAIL | PASS | our pen doubles are audited (payload) AND rank 1 (registry re-point) — two constraints; in-place at low id needs the payload fixed too |
| PASS | FAIL | FAIL | payload AND the mechanics; the K/X ladder must go in-place AND birth-vintage |
| **FAIL** | any | any | **the viewer round is unreliable — no verdict since ~21:05 counts; re-run every conviction against a fresh control** |

Until the certified copy PASSES in a round, **treat X0/C0's FAILs as
provisional** and X_pen/X_cat's as unread.

---

## 9. Reproduction (repo root, `.venv/bin/python`)

```
python -m rvt.regdiff                                        # K1 id2 / X0 id1.5M / V20 table + diffs + run law
python -m rvt.regdiff experiments/genesis/controls/C0.rvt 1500000
python -m rvt.regdiff --runs experiments/genesis/triage/K1.rvt      # the run structure of a file (JSON)
python -m rvt.regdiff --mine                                 # six-sample census (order law + ElemTable invariants), ~4 s
python -m pytest tests/test_regdiff.py -q                    # 12 passed
```

Scratch instruments behind §2/§5/§8 (session scratchpad `.../scratchpad/regdiff/`):
`streamdiff.py` (per-stream identity of every probe vs K1), `recdiff.py`
(record positions + framed-byte diffs), `latestbytes.py` (the 3-byte Latest
diff + codec byte-exactness), `stamps.py` (0/13,080 mismatches), `xpen_obj.py`
(X_pen payload = 126 doubles only), `runs_ep.py` (the modified-ep run law),
`lookalike.py` (the 4,124 C0-signature rows), `c0check.py` (referrers 0/0).

---

## 10. Diffs proposed for files outside this territory (NOT applied)

* **`src/rvt/commit.py::commit_new_elements`** (commit-layer owner) — honour
  an explicit `plan.creation_ep` / `plan.original_id` instead of stamping
  `max(modified_ep)` and `original_id = elem_id` (the controls' gotcha 1;
  X0k's plan asked for `(0,0,0)` and got `(1016,1016,1016)`). This is the
  prerequisite for ANY rank-2 (vintage) probe.
* **`tools/genesis_controls.py`** (controls stream) — build the rank-1
  splitters keyed to X0k's verdict: `X0e` (X0k + row episodes forced to K1's
  `(0,976,976)` — the pure-position bisector); `X0p` (X0 with the records
  PREPENDED to the newest-episode run instead of appended); `X0c` (X0k plus
  ONLY the registry leaf rewritten to a scratch id — the pure re-point
  bisector, no add/delete at all). Each is one change from a sibling.
* **`tools/genesis_substitute.py`** (substitution engine) — for classes whose
  registration is a single scalar leaf, offer an IN-PLACE mode (the fixer's
  `EditSession.replacement` primitive): no delete, no registry rewrite, the
  original id/row/position kept — the only mode that changes ZERO
  registration dimensions. (Pending §8's control, this is the leading
  architecture for the K/X ladder.)
* **`src/rvt/validate.py`** (validation) — nothing to add: every dimension
  measured here is either satisfied by our files or not a validity rule;
  the missing gate is a viewer control, not a validator layer.
* **KNOWLEDGE.md owner** — merge §3's record-order law (unit 0 = runs by
  modified_ep DESC, id ASC within run; the three seq orders are identical),
  §4's two facts (only three classes carry a universal birth-vintage law;
  4,124 accepted built-in style rows carry the fresh-episode/high-band
  signature), §5 (single-leaf registrations, no untyped mirrors), and the §8
  instrument rule (every viewer round must carry a certified-copy control).

---

## 11. Unknowns

* Whether the ~00:25 round's five FAILs are real (§8 — the blocking
  unknown; resolves with one certified-copy control).
* X0k's verdict (staged in `experiments/acceptance/`, unread as of this
  record) — the rank-1 vs rank-2/3 arbiter.
* Whether the reader audits birth-vintage AT ALL: no accepted file contains
  a re-added birth singleton, so rank 2 is inference, not observation. If the
  pure in-place mode (§10) is adopted, the question becomes moot for genesis
  (in-place keeps `(0, 976, 976)` and id 2).
* Why the run law admits 2–11 non-descending adjacent run pairs in the
  larger samples (mixed-episode runs / interleaved partial saves) — a
  compaction detail, immaterial to the ranking since position is retired.
* The 27,475-id watermark hole and `original_id = new id` (rank 4): never
  isolated because they never travel without rank 1; the §10 re-mint folds
  them in for free.

## BRANCH STATE

* No VCS (plain directory). NEW files, this stream's territory only:
  `src/rvt/regdiff.py`, `tests/test_regdiff.py` (12 pass),
  `docs/writer/registration-diff.md` (this file),
  `docs/inbox/genesis-forensics.md`. No `.rvt` written; no other file edited.
* Findings: the record-order law (§3), the three universal birth-vintage
  classes and the corpus-normality of C0's row (§4), the single-leaf /
  3-byte registry edit (§5), the 0/0 deletion collateral (§6), the ranked
  list (§7), and the missing-control blocker (§8).
* Full suite this session: see `docs/inbox/genesis-forensics.md`.

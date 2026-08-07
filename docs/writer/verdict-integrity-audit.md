# VERDICT INTEGRITY AUDIT — which of the genesis campaign's verdicts still count

Stream: **genesis-discipline** (2026-08-04). Subject: every viewer verdict
recorded during the genesis campaign (2026-08-03 ~14:45 → 2026-08-04 ~02:45;
`docs/inbox/genesis-audit.md` ORCHESTRATOR VERDICTS #1–#15 +
`docs/coverage/viewer-certified.json`). Question, for **every** recorded
FAIL: *was its base viewer-certified at the time, and did its round carry a
known-PASS control?* The classification below is **mechanical**, produced
by `tools/probe_batch.py retro` (the same rules the new batch gate applies to
every future round — control first, then base, then attribution); the
commentary is mine. Reproduce: `.venv/bin/python tools/probe_batch.py retro`.

---

## 0. Verdict in one paragraph

Of the **35 recorded FAILs**, **31 are VOID** (their base was never certified,
or had itself failed — 21 sit on the K1 lineage, 9 on the G0/G1 assembler
lineage, 1 on an untested reduction rung), **3 are UNGUARDED** (base fine, round carried no known-PASS file:
P4_ids_null, P6_all, and K1 itself), and exactly **1 is SOUND** — R9b, whose
finding (coherent four-registry removal required) was confirmed constructively
by KD1. The eleven PASSes all survive (a PASS is self-certifying). Only **one
round in fourteen** (#12) carried a deliberate certified control; **eight of
the twelve FAIL-bearing rounds carried no passing file at all**, including the
four consecutive rounds (#8–#11) that produced the retracted "constructed vs
cloned / add-path is the bug / two independent constraints" narrative. **Bug A
of verdict #6 — "the settings singletons are required" and "the built-in
style catalog is required" — is VOID:** K5 and K6 were reductions of K1, and
K1 fails on its own. What survives with real evidence is short and load-bearing:
the ADocument codec and its dangling-tolerance (R5/R9), the four-registry
content-document law and the Bug-B fix (R9b→KD1), family documents not
required (K4), our loadable family accepted (L1a), the identity/authorship
layer (V30–V32), our constructed conduit types accepted (T_conduit_types), the
live-registry-id rule (P4/P6, unguarded but consistent), the two death
signatures, and — the campaign's real product — **K1 is a broken base**
(round 14, base R5 certified). Everything the linter/fixer mined from the
CORPUS (scale-key sets, per-category flag profiles, ownership webs, vintage
bands, the record-order law) is a fact about real files and never depended on
any verdict.

## 1. Method — the two axes, applied round by round

A viewer FAIL is *evidence about the probe's change* only when two things
hold at verdict time:

1. **Its BASE was itself certified** — viewer-PASSED and listed in
   `docs/coverage/viewer-certified.json` `certified` (or is an Autodesk
   sample, the reader's own reference file). "Derived from a certified file"
   is not certification; the "(viewer PASS)" prose written inside a
   `probes.json` is not evidence — 25 probe entries (six manifests, plus three
   stream-level anchors) carried exactly that prose about
   K1, and K1 had never been uploaded. A base that had itself **FAILED** is
   worse: the probe measures nothing.
2. **Its ROUND carried a known-PASS control**, so a broken oracle
   (throttling, dedupe, stale reads, service degradation) cannot masquerade
   as a finding. Historically there was ONE deliberate control round (#12,
   `CTRL_L1a_recheck` + `CTRL_R9_recheck`, ~01:55 on 08-04); before it, the
   only "controls" were co-uploaded candidates that happened to PASS — which
   guard a round only by luck (a candidate that FAILS proves nothing about the
   oracle, and rounds #8–#11 had zero passes).

Classification of a FAIL: **VOID** if its base was never certified or had
failed; else **UNGUARDED** if the round carried no passing file; else
**SOUND**. A PASS **SURVIVES** (nothing on a broken oracle passes by
accident). `read_batch_verdicts()` applies precisely this order to every
future round, and *refuses* to interpret a round with no control.

## 2. Certification timeline (what was actually certified, when)

* **Round 0 (pre-campaign, acceptance batches 1–10, 08-02 22:15 → 08-03
  ~12:00):** V15…V31, H1/H2, M2/M3/M4/M2_rac, R0_identity, R4s certified —
  every one of those batches carried in-round passes (V0, V9, V15 …); the
  writer, ECC, identity, manipulate, hosting and reduction-safety proofs are
  outside the retraction and untouched. The six Autodesk samples are certified
  sources by definition.
* **Certified during the campaign, in order:** V32 + T_conduit_types (round 1,
  ~14:50); R5 + R5s (round 2, ~16:00); R9 (round 3, ~17:05); K3 + K4 + KD1
  (round 5, ~20:25); L1a (round 6, ~21:05); CTRL_L1a_recheck +
  CTRL_R9_recheck (round 12, ~01:55).
* **Never certified but built on anyway:** **K1** (declared base of 25 probe entries; ~21 uploads across
  rounds 5–14; first uploaded round 14, where it FAILED), the G0 ladder rungs
  G0a–G0d, R10, X2–X4/X6a–X8/X10 (cumulative substitution rungs), K5b/K5c, S2,
  the factory `.rfa` under `L_v2`/FG1.

## 3. The map — every recorded verdict, classified

Column "base (status at verdict)" is the base's ledger status *as of that
round*; "control in round" names any file that PASSED in the same round.
Generated by `tools/probe_batch.py retro` (46 rows: 35 FAILs, 11 PASSes).

| # | round | file | verdict | base (status at verdict) | control in round | CLASS |
|--:|---|---|---|---|---|---|
| 1 | 1 | `G0.rvt` | FAIL | `G0d.rvt` NEVER certified | co-uploaded file(s) PASSED: V32_own_dit_usernames.rvt, T_conduit_types.rvt | **VOID** |
| 2 | 1 | `V32_own_dit_usernames.rvt` | PASS | `rstbasicsampleproject.rvt`  |  | **SURVIVES** |
| 3 | 1 | `T_conduit_types.rvt` | PASS | `rmebasicsampleproject.rvt`  |  | **SURVIVES** |
| 4 | 2 | `R5.rvt` | PASS | `rstbasicsampleproject.rvt`  |  | **SURVIVES** |
| 5 | 2 | `R5s.rvt` | PASS | `rstbasicsampleproject.rvt`  |  | **SURVIVES** |
| 6 | 2 | `R10b.rvt` | FAIL | `R10.rvt` NEVER certified | co-uploaded file(s) PASSED: R5.rvt, R5s.rvt | **VOID** |
| 7 | 3 | `R9.rvt` | PASS | `rstbasicsampleproject.rvt`  |  | **SURVIVES** |
| 8 | 3 | `R9b.rvt` | FAIL | `R9.rvt` certified this round (co-uploaded PASS) | co-uploaded file(s) PASSED: R9.rvt | **SOUND** |
| 9 | 4 | `G1_candidate.rvt` | FAIL | `G0.rvt` FAILED (round 1) | NONE -- no known-PASS file in the round | **VOID** |
| 10 | 4 | `G1a.rvt` | FAIL | `G0.rvt` FAILED (round 1) | NONE -- no known-PASS file in the round | **VOID** |
| 11 | 4 | `G1b.rvt` | FAIL | `G0.rvt` FAILED (round 1) | NONE -- no known-PASS file in the round | **VOID** |
| 12 | 4 | `P4_ids_null.rvt` | FAIL | `rstbasicsampleproject.rvt` sample-source (certified by definition) | NONE -- no known-PASS file in the round | **UNGUARDED** |
| 13 | 4 | `P6_all.rvt` | FAIL | `rstbasicsampleproject.rvt` sample-source (certified by definition) | NONE -- no known-PASS file in the round | **UNGUARDED** |
| 14 | 5 | `K3.rvt` | PASS | `R9.rvt`  |  | **SURVIVES** |
| 15 | 5 | `K4.rvt` | PASS | `K3.rvt`  |  | **SURVIVES** |
| 16 | 5 | `KD1.rvt` | PASS | `R9.rvt`  |  | **SURVIVES** |
| 17 | 5 | `K5.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | co-uploaded file(s) PASSED: K3.rvt, K4.rvt, KD1.rvt | **VOID** |
| 18 | 5 | `K6.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | co-uploaded file(s) PASSED: K3.rvt, K4.rvt, KD1.rvt | **VOID** |
| 19 | 6 | `L1a_rstbasic_loaded_levelhead.rvt` | PASS | `rstbasicsampleproject.rvt`  |  | **SURVIVES** |
| 20 | 6 | `S5.rvt` | FAIL | `G1_candidate.rvt` FAILED (round 4) | co-uploaded file(s) PASSED: L1a_rstbasic_loaded_levelhead.rvt | **VOID** |
| 21 | 6 | `S4.rvt` | FAIL | `G1_candidate.rvt` FAILED (round 4) | co-uploaded file(s) PASSED: L1a_rstbasic_loaded_levelhead.rvt | **VOID** |
| 22 | 6 | `S3.rvt` | FAIL | `G1_candidate.rvt` FAILED (round 4) | co-uploaded file(s) PASSED: L1a_rstbasic_loaded_levelhead.rvt | **VOID** |
| 23 | 6 | `S1.rvt` | FAIL | `G1_candidate.rvt` FAILED (round 4) | co-uploaded file(s) PASSED: L1a_rstbasic_loaded_levelhead.rvt | **VOID** |
| 24 | 7 | `K5a.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 25 | 7 | `K5d.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 26 | 8 | `R1.rvt` | FAIL | `K5.rvt` FAILED (round 5) | NONE -- no known-PASS file in the round | **VOID** |
| 27 | 8 | `R2.rvt` | FAIL | `K6.rvt` FAILED (round 5) | NONE -- no known-PASS file in the round | **VOID** |
| 28 | 8 | `R3.rvt` | FAIL | `S5.rvt` FAILED (round 6) | NONE -- no known-PASS file in the round | **VOID** |
| 29 | 8 | `X5.rvt` | FAIL | `X4.rvt` NEVER certified | NONE -- no known-PASS file in the round | **VOID** |
| 30 | 8 | `X9.rvt` | FAIL | `X8.rvt` NEVER certified | NONE -- no known-PASS file in the round | **VOID** |
| 31 | 9 | `X1.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 32 | 10 | `X0.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 33 | 10 | `X1u.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 34 | 10 | `C0.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 35 | 10 | `X_pen.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 36 | 10 | `X_cat.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 37 | 11 | `X0k.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 38 | 12 | `CTRL_L1a_recheck.rvt` | PASS | `L1a_rstbasic_loaded_levelhead.rvt`  |  | **SURVIVES** |
| 39 | 12 | `CTRL_R9_recheck.rvt` | PASS | `R9.rvt`  |  | **SURVIVES** |
| 40 | 13 | `XR0.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 41 | 13 | `XA2.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 42 | 13 | `P_ep_only.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 43 | 13 | `P_pos_only.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 44 | 13 | `P_ident_only.rvt` | FAIL | `K1.rvt` NEVER certified (itself FAILED later, round 14) | NONE -- no known-PASS file in the round | **VOID** |
| 45 | 14 | `K1.rvt` | FAIL | `R5.rvt` certified | NONE -- no known-PASS file in the round | **UNGUARDED** |
| 46 | 14 | `XR_null.rvt` | FAIL | `K1.rvt` FAILED (round 14) | NONE -- no known-PASS file in the round | **VOID** |

Totals: **46 verdicts — 35 FAIL (31 VOID · 3 UNGUARDED · 1 SOUND) · 11 PASS
(SURVIVE)**. Rounds with any in-round PASS: 1, 2, 3, 5, 6, 12. Rounds with a
*deliberate* certified control: **12 only**. FAIL-bearing rounds with **no**
passing file: 4, 7, 8, 9, 10, 11, 13, 14.

## 4. What is VOID — said plainly

**The K1 lineage (21 FAILs, rounds 5, 7, 8, 9, 10, 11, 13, 14).** K1 = "R5
minus the placed model" (the triage stream's maximal-GC reduction, never
uploaded until round 14, where it — and its byte-identical twin XR_null —
crashed `-1073741831`). Every K1-derived FAIL is that defect wearing a
costume. VOID, individually:
K5, K6, K5a, K5d (the singleton/catalog *removal* probes); R1, R2 (add-backs
onto K5/K6); X1, X5, X9 (the substitution ladder — X5/X9 also sit on
never-uploaded parent rungs X4/X8); X0, C0, X1u, X_pen, X_cat (the three-way
separation + the fixer's in-place payload probes); X0k (whose crash
signature was, in hindsight, the first sighting of K1's own death mode); XR0,
XA2, P_ep_only, P_pos_only, P_ident_only (the regadd / per-rule isolators);
XR_null. **Therefore VOID as conclusions:** verdict #6's *Bug A* — **"the
settings singletons are required" and "the built-in style catalog is
required" rest solely on K5/K6, i.e. on K1, and are VOID**, not established;
verdict #9's *"the divide is constructed vs cloned objects"*; verdict #10's
*"our values violate a value grammar" as the cause*; verdict #11's *"the ADD
PATH is the bug"* (X0/C0); verdicts #13/#14's *"two independent constraints"*.
UNJUDGED, not condemned: our constructors, the regadd add/substitute paths,
and our values were never tested against a loadable base.

**The G0/G1 assembler lineage (9 FAILs, rounds 1, 4, 6, 8) plus R10b
(round 2).** G0's own
ladder rungs (G0a–G0d) were never viewer-tested, so G0's failing step was
never localised — and its recorded lead suspect (6,175 dangling ids) was
**REFUTED** by R5/R9. G1_candidate/G1a/G1b were rebuilt over the failed G0
skeleton, in a round with no passing file. The S-set (S1, S3, S4, S5) put our
content on the failed G1 base ("cannot separate mis-shaped content from an
independent G1-base defect" — their own note); R3 built on S5. R10b sat on the
never-uploaded R10 rung. All VOID — *the G0/G1 base has its own unlocalised
defect and every conclusion drawn from G1's failures is suspect*.

## 5. What SURVIVES — the honest evidence base

| finding | carried by | class | note |
|---|---|---|---|
| Latest-DANGLING references are NOT fatal, at any tested scale | R5, R5s, R9 PASS | SURVIVES | G0's 6,175 dangling ids were never the cause |
| Removing embedded family documents / units while the content registries expect them IS fatal — the FOUR-registry law; Bug B named and FIXED | R9b FAIL (**SOUND**) → KD1 PASS | SOUND + confirmed | the campaign's one properly-controlled failure, closed constructively |
| Embedded family documents are NOT required by the reader | K4 PASS (52 documents removed, four-registry coherent) | SURVIVES | on the R9 lineage |
| Annotation-head USAGE fields are nullable | K3 PASS | SURVIVES | |
| OUR generated family LOADS into a project via the four-registry loader | L1a PASS, re-certified by CTRL_L1a_recheck | SURVIVES | |
| OUR constructed conduit types are reader-accepted objects | T_conduit_types PASS | SURVIVES | the one direct proof that constructor output loads |
| The writer OWNS the identity block; scrubbed DIT usernames accepted | V30–V32 PASS | SURVIVES | pre-genesis + round 1 |
| The oracle was healthy at ~01:55 (and certified files re-pass byte-identically) | CTRL_L1a_recheck, CTRL_R9_recheck PASS | SURVIVES | the ONE deliberate control round; retro-guards verdicts read after L1a's ~21:05 pass through ~01:55 |
| **K1 is a broken base** — the "R5 minus placed model" maximal-GC reduction introduces a CRASH defect (`-1073741831`) | K1_base FAIL (base **R5 certified**), corroborated by XR_null (byte-identical, same crash) | UNGUARDED-but-decisive | see §6: robust under either branch |
| Live registry ids must index PRESENT rows; nulling live ids on a working base is fatal while dangling ids of deleted rows are tolerated | P4_ids_null / P6_all FAIL on the certified rst sample | UNGUARDED | uploaded in the pass-less round 4, read out at #6 after K3/K4/KD1 passed; consistent with R5/R9 and the AppInfo registry model — treat as good evidence pending a controlled re-run |
| Every FACT the linter/fixer mined from the CORPUS — pen-table scale-key set {10,20,50,100,200,500}, per-category header-flag profiles, pattern/pen null cells, ownership webs, birth-vintage bands, the unit-0 record-order law, the delete-floor / pinning webs | 3,494–59,770 real specimens, six samples | corpus fact (not a verdict) | descriptive laws of real files; independent of every base and every viewer round — they SURVIVE by construction |
| The AUDIT vs CRASH death-signature vocabulary (`Revit-DocumentCorruption` + `-1073742517` vs no line + `-1073741831`) | the failed-card messages across ~30 files | descriptive | K1 dies by CRASH; its heavier-modified children tripped the AUDIT |
| The ADocument codec (byte-exact), ContentDocuments grammar, registry-parity instruments, the validator layers | round-trip on all six samples + G-files; suites green | code + tests | necessary, not sufficient (VALID ≠ loads) |

## 6. The round-14 finding itself — is K1's own FAIL trustworthy?

Strictly it reads **UNGUARDED**: no certified control was uploaded *inside*
the ~02:27 round. It is nevertheless decisive, for three reasons:

1. **Oracle health for the window is established** by the two certified
   controls that passed at ~01:55 (round 12), 50 minutes earlier — the first
   and only deliberate control round of the campaign.
2. **Internal consistency:** K1_base and XR_null are byte-identical files
   uploaded together and both fail with the *same* signature
   (`-1073741831`, no corruption line) — a flaky oracle does not track byte
   identity, and that same signature had already appeared on K1's two nearest
   byte-neighbours (X0k, XR0) in earlier rounds.
3. **The retraction is robust under EITHER branch.** If the oracle was
   healthy at 02:45, K1 is broken and the K1 lineage is void. If the oracle
   was *sick* at 02:45, then rounds 8–14 were unreliable anyway — and the K1
   lineage is *still* unread. There is no branch on which verdicts #9–#14
   stand.

Attribution is also clean: K1's base R5 is certified (round 2), and K1
differs from R5 by exactly the maximal-GC "placed model" removal — so the
defect lives in that removal (the triage stream pre-staged the split file
`K1_step1_neutralised.rvt` for exactly this bisection). The *next* K-round
should carry: a fresh `CTRL_` copy, `K1_step1_neutralised.rvt` (candidate-
base), and the first rung of the ladder **rebased on the certified,
family-free K4** — through `tools/probe_batch.py stage`, which will refuse
anything else.

## 7. The four control-less runs — the exact failure mode, quantified

Rounds **8, 9, 10, 11** (08-03 ~22:47 → 08-04 ~00:50): **12 uploads, 12
FAILs, ZERO passes, ZERO controls**, four rounds running — every one on the
uncertified K1 or a failed base. The forensics stream flagged the anomaly at
verdict #12 ("13 consecutive FAILs since the last PASS; zero successes over N
events is a defect signature") and the controls came only at ~01:55. Round 13
then staged `XR_null` *as* the positive control — but XR_null is a copy of
the **uncertified** K1, so it was not a control at all (a control is a
byte-identical copy of a *certified* file), and its read was stale besides.
Round 14 finally uploaded the base. **Twelve hours and fourteen rounds of
viewer budget produced exactly one soundly-controlled failure (R9b) and one
decisive, unguarded one (K1's own).**

## 8. Ledger and record discrepancies found (for the orchestrator)

1. **R4s / R0_identity are ledger-CERTIFIED, yet `docs/writer/genesis-status.md`
   (E5), `docs/inbox/genesis-assembler.md`, and `genesis-audit.md` §B6 assert
   "no G- or R-rung has a recorded viewer pass" / retract "R4s viewer PASS".**
   The two statements cannot both hold. The ledger is the authority; the
   acceptance log simply stopped being written at batch 10, which is what
   misled the auditor. Cheapest settlement: include a byte-identical
   `CTRL_R4s` copy as the control of some future round — it re-proves both the
   entry and the oracle in one file.
2. **XR_null's FAIL (verdict #15) is missing from the ledger's `failed`
   array.** And 18 genesis-era files sit in `experiments/acceptance/` with
   no recorded verdict at all: C0all, C1u, K2, K4b, K5b, K5c, KD1a, S2, X10,
   X6a, XR1, XR3, P_allnew, P_lowid, R1s, P1_names, L_v2, G0a (K1's own
   verdict is recorded, but under the `triage/K1.rvt` path while the upload
   was named `K1_base.rvt`). Each is either a PENDING read the orchestrator
   forgot, or a file staged and never uploaded — the queue-as-directory
   pattern loses that distinction; the batch manifests (`batch_<n>.json`)
   exist to keep it.
3. **The six Autodesk samples are not listed in `certified`**, yet L1a, P4/P6,
   V32 and the whole R-ladder declare a sample as base. `tools/probe_batch.py`
   admits `samples/*.rvt` as certified sources by rule (they are the reader's
   own reference files); the orchestrator may prefer to list them explicitly
   so the ledger needs no exception.
4. **The `failed` entries' `note` fields assert several now-VOID causes**
   (K5/K6 "singletons/catalog REQUIRED", X0/C0 "THE DECISIVE READOUT: the add
   path corrupts", the round-8 "constructed vs cloned" quintet, G0's "lead
   suspect: dangling ids"). Per this audit they are now **annotated in place**
   with a `cause_status` field (VOID / REFUTED / CONFIRMED / SOUND /
   UNGUARDED) — history preserved, cause classified.
5. Timestamps: R2/R3/X5/X9/K5a/K5d/R1 carry `when` "~22:50 / ~21:10" but were
   read out in verdict #9 at ~23:00; P4/P6 have no `when` at all (uploaded
   ~17:56, read ~20:25). Round assignment above follows upload time.

## 9. The mechanism now in place

`tools/probe_batch.py` (tests: `tests/test_probe_batch.py`, 34 pass) makes
tonight's two failures un-committable:

* **`stage`** resolves every probe's declared base from its `probes.json`
  (all eleven corpus manifest conventions; a probe with no declared base is
  refused), **refuses** the batch unless every base is *itself* in the
  ledger's `certified` (a recorded-FAIL base is refused with the failure's
  own text; "(viewer PASS)" prose is ignored), **generates the control**
  automatically (`CTRL_<newest-certified>_b<n>.rvt`, byte-identity asserted),
  copies the batch into `experiments/acceptance/`, and writes
  `batch_<n>.json` = `{file, md5, base, base_certification, kind}` per
  entry, **control first** in the reading order. A file uploaded *to be
  certified* is a `--candidate-base` (exempt from the base rule; a candidate
  whose declared lineage is a recorded failure is warned, not refused).
* **`verdicts` / `read_batch_verdicts()`** reads the round in the only safe
  order: control FAILED ⇒ `VOID_ROUND`, every verdict void, pause and
  re-upload a fresh control alone; control pending ⇒ interpret nothing; a
  probe whose base is uncertified ⇒ refuse it and demand the base be
  uploaded first; only then attribute a FAIL to the probe's own change, and
  emit ledger-update snippets (`certified` / `failed`) for the orchestrator.
* **`check`** dry-runs the gate; **`resolve`** prints a probe's declared base
  and its ledger status; **`retro`** regenerates §3 of this document.

Demonstration: the exact batches of 08-04 cannot be staged today —
`probe_batch.py check experiments/genesis/addpath/P_ep_only.rvt
experiments/genesis/controls/X0.rvt` refuses both, naming K1's recorded
failure. Run against yesterday's ledger — K1 merely *absent* from
`certified` — the gate refuses the very first K5/K6 upload at ~19:12 with
"declared BASE K1.rvt is NOT certified: upload it as a candidate-base
first". That single refusal is the five hours.

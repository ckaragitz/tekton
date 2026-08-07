# genesis-autopsy — THE K1 AUTOPSY (workstream record, 2026-08-04)

Charter: explain why `K1.rvt` (= "R5 minus the placed model", the never-uploaded
base of the whole substitution program, ORCHESTRATOR VERDICTS #15) FAILS the
Autodesk reader with the CRASH signature while its parent R5 PASSES; diff K1
vs R5 at the element level; cross-reference with the certified reduction
ladder; build the K1a..K1f bisection ladder from R5; state THE LAW. Territory
touched ONLY: `tools/k1_autopsy.py` (new), `experiments/genesis/autopsy/*`
(9 probe files + per-rung JSON + `probes.json` + `autopsy_evidence.json`),
`docs/writer/k1-autopsy.md` (the deliverable), this record. NO existing
`src/rvt/*`, tool or test edited; the tool IMPORTS `genesis_triage`,
`rvt_reduce`, `rvt.reduce`, `rvt.manipulate`, `rvt.validate`, `rvt.regdiff`.
No browser use — the ladder awaits the orchestrator's viewer gate.

## Result in one screen

**K1's entire difference from the union of viewer-PASSED files is 22
surviving elements EDITED by K1's neutralise pre-pass + ONE deleted room every
passing file keeps** — a closed accounting, with a byte-record-exact
recomposition proof. Everything else is R5's bytes or a deletion the
certified R9/R6 also made. Full report: `docs/writer/k1-autopsy.md`.

The five measured facts that close it:

1. **Two-step decomposition** (`R5 -> K1_step1_neutralised.rvt -> K1`): step
   1 (rvt.manipulate `neutralise_referrers`, the M2/M3-certified modify path)
   **edited 404 surviving referrers**; step 2 (maxgc `delete_elements`) is a
   pure delete — **0 survivor records touched**. 381 of the 404 edited
   elements were then deleted; **exactly 23 edited elements survive**.
2. **Deletion cross-reference**: of K1's 2,117 deletions, **2,084 are also
   deleted by certified R9 and 31 by certified R6**; only 2 are R9-kept —
   title-block instance 1457033 (deleted by the PASSING K4 → vindicated) and
   area `RoomElem` **1004910** (kept by R9/R10/K3/K4 → the ONE unvindicated
   deletion). The deletion recipe is not the crime scene.
3. **Stream identity**: `Global/Latest`, `History`, `ContentDocuments`,
   `BasicFileInfo`, `DocumentIncrementTable`, `PartitionTable`, `Contents`,
   `Formats/Latest`, `ProjectInformation`, `TransmissionData` are
   **byte-identical to R5's AND R9's**; only `ElemTable` + `Partitions/21`
   differ. K1's 1,066 `Latest`-dangling ids ⊆ R9's tolerated 3,014 **except
   the one room**; the four-registry content census is identical R5=R9=K1.
4. **The 23 survivors** (full field-level table in the deliverable §2): a
   **registry-indexed category-DEFAULT `FamilySymbol` orphaned** (876569,
   `m_familyId -> -1`, its Family DELETED) + its two surrogates; a
   `StairsTriserSymbol` with `m_hostId -> -1`; the **Graphical Column
   Schedule** with whole `m_visGridIntPntArr` struct entries dropped (273
   leaves, live grid refs collaterally gone); 5 3D views + 1 section with
   pruned hidden-element / ad-hoc-override / parent maps (up to 916 leaves);
   a rendering view with `m_imageInstanceId -> -1`; an area `LevelRoomPlan` /
   `AreaSchemePlanTopologies` pruned of the kept room; an interior-elevation
   arrow attached to nothing; and 8 sheets with `m_sheetTitleBlockId -> -1` —
   the last **byte-vindicated** (sheet 1457028's K1 record is byte-identical
   to the PASSING K3/K4 record). **22 of the 23 are byte-states no passing
   file carries.** The certified ladder v2 never edits a survivor at all.
5. **Two closure proofs**: (a) RECOMPOSITION — R5 + all six edit classes +
   maxgc reproduces K1 **byte-record-exact**; (b) the transient
   CurveElem/LinearDimString/Alignment edit class (381 doomed referrers) is
   **redundant** — the 12 persistent classes alone reproduce K1's exact
   2,117-id deletion set and its 23 records (G6 exonerated analytically; that
   twin file is not a probe).

## THE LAW (short form — full text in the deliverable §4)

**A referrer of removed content is either DELETED WITH the content or LEFT
BYTE-IDENTICAL — never "neutralised" into a state no Autodesk file
exhibits.** Family/type layer is atomic (never null a symbol's family / a
surrogate's element / a riser symbol's host while the object survives —
least of all a registry-indexed default type); never drop structured entries
from a survivor's arrays (schedule grid-intersection structs, topology
segments); model-view state maps leave WITH the view (R6's rule); the only
sanctioned reduction generator is maxgc + four-registry document
reconciliation; a base is CERTIFIED before anything builds on it. The
CORRECTED K1 recipe is mechanical from the round-1 verdicts: for each edit
group whose single rung FAILS, DELETE that group's referrers with their
content instead of neutralising; keep the groups whose rungs PASS. Bonus
analytic finding (K1v): the "empty project that KEEPS the sample's
model-referencing view constellation" is **not delete-reachable** (the
model-viewing views are pinned by viewports on the surviving sheets) — the
certified shape of "empty" is R9's/K4's: those views leave with the model.

## THE LADDER — batch for the orchestrator (`experiments/genesis/autopsy/`)

Manifest: **`experiments/genesis/autopsy/probes.json`** (ordered by
information value, `reading_the_results` = the full interpretation tree).
Every probe declares **base = experiments/genesis/R5.rvt, which IS in
viewer-certified.json 'certified'** (derived in ONE step — no probe stacks
on an untested probe); `CTRL_R5_recheck.rvt` is the batch's byte-identical
certified control (md5 = R5's). All 9 files: `rvt_validate` VALID, 0
errors, arbiter CLI pasted in §Verification. Stage the upload through
`tools/probe_batch.py stage ...` (the discipline stream's gate) — this
batch satisfies its rules by construction (certified base + certified
control), but I did not run that tool (not my territory).

| # | file | tests (the ONE thing) | deleted | if FAIL |
|--:|---|---|--:|---|
| 1 | `CTRL_R5_recheck.rvt` | oracle health (md5-identical R5) | 0 | void the batch |
| 2 | `K1a_editfree.rvt` | K1 with ALL survivor edits removed (pure maxgc, zero edits) | 599 | deletion set fatal in views-present context |
| 3 | `K1_suspect.rvt` | ONLY the in-place-family orphaning (3 K1-identical records + 78 deletions); nothing else changed | 78 | orphaning a live indexed type is fatal at any scope |
| 4 | `K1e_orphaning.rvt` | K1a + G4 (symbol/surrogates/riser-symbol edits, K1's bytes) | 677 | law clause 1 |
| 5 | `K1d_schedule.rvt` | K1a + G3 (graphical-column-schedule struct drops) | 969 | law clause 2 |
| 6 | `K1f_topology.rvt` | K1a + G5 (topology/arrow edits + the kept-room deletion) | 600 | topology surgery / kept-room deletion fatal |
| 7 | `K1c_viewmaps.rvt` | K1a + G2 (3D/section/rendering state-map edits) | 859 | law clause 3 |
| 8 | `K1b_sheets.rvt` | K1a + G1 (sheet title-block nulls) — EXPECTED PASS (K3/K4-vindicated); the internal control | 607 | vindication argument wrong — re-examine |
| 9 | `K1v_delete_referrers.rvt` | zero-edit sibling of K1a with the 23 referrers ALSO deleted (with released content) | 696 | referrer-layer deletion delta is fatal |

Each single-group rung carries K1's **byte-identical** edited records for
its group's referrers (proven); K1_suspect's 3 edited records are K1's
exact bytes and its Family 876493 IS deleted (a genuine orphan, not a nulled
link to a present target). K1a's residue (1,525 seed elements pinned by the
UNEDITED views: `RebarInSystem <- DBView3d ×612`, `Rebar <- DBView3d ×228`,
`DPart ×123`, `FamilyInstance <- DBViewGraphSchedColumn ×30` …) is exactly
what the group edits unlock: singles unlock 8..370 each, all five together
2,117 (`autopsy_evidence.json:unlock_table`, simulator == real for every
rung); pairwise interaction is tiny (G3+G2 28, G4+G2 18) — ~755 deletions need
≥3 groups' pins cut (the model is ONE connected pin-component).

**Prior expectation** (mine, for the record — the viewer decides): CTRL PASS,
K1b PASS, K1a PASS; the killer is G4 (registry-indexed orphan symbol →
`K1_suspect`/`K1e` FAIL) or G3 (schedule) or G5; G2 is the closest to
Revit's own delete semantics. If instead ALL five singles PASS with K1a, the
crash is a ≥2-group interaction and the SAFE recipe skips the interaction hunt
entirely: delete all 22 unvindicated referrers with the model (law clause
"deleted WITH the content" — K4/R9's certified shape).

## New instruments / findings (evidence — for KNOWLEDGE.md merge)

1. **Survivor-modification is invisible to the ElemTable and to the
   validator** — K1 is 6,540 clean rows, VALID 0 errors — and only visible to
   a record-byte diff over all three seqs (`k1_autopsy.element_diff`). Every
   future reduction/genesis report should print "survivors modified: N" as a
   first-class number; a reduction with N > 0 is not a reduction.
2. **Byte-vindication by a passing file** (element present in a PASSING
   file, byte-identical record) settles a suspect without a viewer round — it
   retired the 8 G1 sheets before upload. Generalisable: a corpus index of
   {element-byte-state → passing files carrying it}.
3. **The certified ladder v2 is edit-free by construction** (maxgc puts a
   would-be-edited referrer in the seed instead); the K1 neutralise pre-pass
   was the first departure from that and produced the whole class of
   never-seen states. `_neutralise`'s "drop the struct entry that mentions a
   target" rule is now BANNED for genesis output (law clause 2).
4. **In-memory group-set unlock simulator** (`unlock_table`: cut S-class
   survivor→target edges, then maxgc) matches every real rung's deletion
   count exactly — sizes any pair/triple probe before building it.
5. **The placed model of rstbasic is one connected pin-component** (halves of
   K1's removal set collect only 61/205 dangling-free elements): "R5 minus
   halves of the model" is not a buildable probe shape here; deletion
   bisection must run over referrer classes / groups, not model halves.
6. **`rvt.manipulate.session()` is cached on the Document** — reset `work` /
   `plans` / `removed` per probe or a prior probe's neutralised working copy
   leaks into the next (k1_autopsy resets explicitly). Suggest an official
   `session(doc, fresh=True)` (manipulate owner).

## Diffs / hooks proposed OUTSIDE this territory (NOT applied)

* **`tools/genesis_triage.py` (triage owner)** — `build_K1` should be
  re-derived by DELETION per the law: seed = placed model ∪ the
  model-referencing views/schedule/room-topology/arrow (deleted with the
  content, R6/R9-style) ∪ the in-place family layer entire; ZERO
  `neutralise_referrers` (or restricted to the ONE edit class the ladder
  proves legal — G1 today; G2 if K1c passes). `_inplace_family_chains` must
  follow `m_familyId` / surrogate links so an in-place family is removed
  with its `FamilySymbol` + surrogates (today it strands the symbol, which the
  neutraliser then orphans).
* **`src/rvt/manipulate.py` (manipulate owner)** — expose a fresh-session
  constructor; consider making `_neutralise`'s struct-drop rule opt-in per
  field (it is right for `m_hiddenElements`, wrong for `m_visGridIntPntArr`);
  a per-class allowlist would encode the ladder's verdicts as they land.
* **`src/rvt/validate.py` (validator owner)** — three cheap coherence rules
  the reader evidently cares about and the arbiter lacks: `FamilySymbol.
  m_familyId != -1` (and its Family present), `StairsTriserSymbol.m_hostId`
  present, `FamilySurrogate.m_elemId` present — the family/type-layer
  atomicity law as validator errors. (Which of them is the *crash* is what
  the ladder decides; all three are corpus invariants — 0 counter-examples in
  the passing corpus.)
* **`docs/coverage/viewer-certified.json` (orchestrator)** — this stream
  wrote NO entries; when the verdicts land, K1's failed entry gains its
  autopsy pointer (this file + `docs/writer/k1-autopsy.md`) and each rung its
  verdict.
* **`tools/probe_batch.py` (discipline owner)** — this batch's `probes.json`
  declares `base` per probe; if the gate wants a different key spelling, the
  manifest is one-line fixable — please tell this stream rather than
  editing the ladder files.

## Verification (arbiter, this session, repo root)

```
.venv/bin/python tools/rvt_validate.py --quiet experiments/genesis/autopsy/*.rvt
OK   CTRL_R5_recheck.rvt        errors=0 warnings=1
OK   K1_suspect.rvt             errors=0 warnings=1
OK   K1a_editfree.rvt           errors=0 warnings=1
OK   K1b_sheets.rvt             errors=0 warnings=1
OK   K1c_viewmaps.rvt           errors=0 warnings=1
OK   K1d_schedule.rvt           errors=0 warnings=1
OK   K1e_orphaning.rvt          errors=0 warnings=1
OK   K1f_topology.rvt           errors=0 warnings=1
OK   K1v_delete_referrers.rvt   errors=0 warnings=1
md5(CTRL_R5_recheck.rvt) == md5(R5.rvt) = f0e39d2140750e84696ef39bf502da3b
```
(the one warning everywhere = the corpus-wide DataStorage/RebarShape ES decode
gap, present in R5 itself). Every rung's own JSON report also carries the
`rvt.reduce.verify_reduced` structural proof (CRC/ECC/walker/stamps/id-set/
count/sentinel — all pass) and the group-neutralisation edit log.

## Open questions (need the viewer / the orchestrator)

* The 9 verdicts, read in `probes.json` order — that IS the finding.
* Is hidden-element / ad-hoc-override PRUNING (G2) legal, or must model views
  leave with the model? (K1c decides law clause 3's final wording.)
* If all five singles PASS: do we spend a round on the interaction pairs, or
  adopt the "delete every unvindicated referrer" recipe directly? (My
  recommendation: adopt the recipe — it is the certified shape either way.)

## BRANCH STATE

No VCS (plain directory). New, uncommitted files: `tools/k1_autopsy.py`;
`docs/writer/k1-autopsy.md`; `docs/inbox/genesis-autopsy.md` (this file);
`experiments/genesis/autopsy/` = 9 probe `.rvt` (CTRL_R5_recheck,
K1a_editfree, K1_suspect, K1e_orphaning, K1d_schedule, K1f_topology,
K1c_viewmaps, K1b_sheets, K1v_delete_referrers) + one `.json` report per
rung + `probes.json` + `autopsy_evidence.json`. Every emitted `.rvt` =
validator VALID (0 errors), structural proof clean, derived in ONE step from
certified R5; CTRL md5-identical to R5. Discarded during the session (not on
disk): `K1z_persistent` (a byte-record twin of K1 — recorded in
`autopsy_evidence.json:k1z_persistent_equivalence`), `K1h1/K1h2` removal-set
halves (61/205 collectable — the model is one pin-component). Full suite
this session: `.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle` →
**934 passed, 2 failed (973 s)**; the 2 failures are the pre-existing
STALE `tests/test_provenance.py::test_G0_resource_refs_are_counted` +
`::test_G0_identity_dit_usernames_still_leak` (they assert the OLD G0's
leaks; the rebuilt G0 no longer leaks — owner: the provenance stream, listed
in every recent record); no failure touches this stream's files, and the
formerly-failing `test_plugin_sync` now passes. This stream adds no tests
(tests/ is outside its territory); the tool is exercised by the recomposition
proof, the K3/K4 byte-vindication checks and the unlock-simulator's
validation against every real rung. STOPPED AT READY — the 9 probes await
the orchestrator's viewer gate; **do not build on K1a until it is itself
certified.**

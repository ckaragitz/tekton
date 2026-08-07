# inbox — instbug-bisect (THE MINIMAL BISECTION LADDER for the product-path bug)

Stream: **instbug** (2026-08-05).  Charter: the demo's `_stages/` ladder
bundles the axes (family-load AND instance-place per stage); build the FINER
ladder on the certified genesis base **G_ABPD** that separates {N family
documents loaded} from {instances placed} from {walls}, every file
validator-clean, verified with regdiff + the four-registry census +
reduce_law-style byte accounting vs its parent, staged through
`tools/probe_batch.py` (base certified, control = byte-identical G_ABPD
copy), probes.json ordered for maximum information.

Territory touched ONLY: `tools/bisect_instance_bug.py` (new),
`experiments/instbug/**` (new), `tests/test_instbug.py` (new), this record,
plus the probe_batch staging copies in `experiments/acceptance/`
(batch_32.json + the 8 rungs + CTRL_G_ABPD_b32.rvt — the staging mechanism's
own output dir).  No `src/rvt/**` file, no existing tool, test, or sample
was edited.  No browser used; the batch sits STAGED for the orchestrator's
viewer gate.

## Result in one screen

* **THE LADDER IS BUILT AND STAGED** — 8 rungs, every one `rvt.validate`
  **VALID 0 errors at emission** (1 warning each = the known inherited
  DataStorage / RebarShape decoder gap, present in the certified bases
  themselves), four-registry **coherent**, identity gate **PASS**,
  reduce-law survivor check **0 removed / 0 modified** (pure adds), staged
  as **batch 32** (`experiments/acceptance/batch_32.json`) with the control
  pinned to **G_ABPD** (`CTRL_G_ABPD_b32.rvt`, md5-identical
  `1f1ff65bd68415a05228d6b6ac2bf271`).  Minutes after staging, the
  instbug-FIX stream landed two new validator rules that the unfixed rungs
  trip BY DESIGN — see **§8 VALIDATOR DRIFT**, which classifies every
  finding (zero unexpected errors on every rung) and pairs each rung with
  its fixed A/B counterpart.
* **Every rung is the demo's OWN code path** — the same prompt
  (`"an electrical room rated for 250V with 6 panels"`) through
  `rvt.frontdoor.prompt_intent`, the same chained loader
  (`tools/ifc_intent.py stage_load` → `rvt.famgen.loader
  .load_family_into_project(place=False)`), the same placement
  (`stage_equipment` → frontdoor `ConstructedSpecimens` template →
  `rvt.mutate.Document.add_family_instance` → `rvt.commit
  .commit_new_elements`).  **BX_f6i6 is shape-identical to the failing
  `DEMO_250v_room.rvt`**: 7 save units / 6 ContentDocuments / 6 ContentTable
  / 15 FamilyMgr rows / 3,216 ElemTable rows — the reproduction control.
  The only foreign ingredient in the ladder is BX_w_f1i1's wall, and it is
  the CERTIFIED one (W1_gabpd_wall_solid mechanism: `add_wall` R5-specimen
  clone mode 'min' + the seq-103 GElement B-rep baked via
  `regadd.substitute_elements` — viewer PASS + RENDERS on G_ABPD).
* **Two of the charter's named suspects are measured DEAD** (§3):
  `Global/PartitionTable` (1 workset row, byte-identical through every load
  / place / wall hop — and Autodesk's own 53-unit rst sample carries the
  same single row) and the `Contents` DocumentStorageIndex (counters
  `[612, 628, 628, 628, 517, 628, 629, 599, 517]`/506 byte-identical
  through every hop — and IDENTICAL in the 53-unit sample, so the counters
  do not track documents even in Autodesk's own files).  Neither registry
  moves when Autodesk adds documents, and neither moves when we do.
* **The four-registry bookkeeping is coherent at every N** (§2): each load
  = exactly +1 save unit / +1 ContentDocuments entry / +1 ContentTable
  record / +1 FamilyMgr entry, GUID sets equal, on the genesis base AND the
  sample base.  Whatever the audit rejects, it is not a count/GUID
  incoherence our census can see — consistent with `rvt.validate` saying
  VALID 0 errors on every failing file.
* **The placed instance is UNREGISTERED in the ADocument on BOTH bases**
  (§4): regdiff's typed walk of the whole document object finds the
  instance ids in ZERO ADocument leaves — on G_ABPD and on the rst sample
  alike (the loader registers only the surrogate → FamilyMgr and the symbol
  → ElementTrackingData; `commit_new_elements` touches no registry).  The
  registration SHAPE our path produces is base-independent; V20..V29 prove
  unregistered created instances are viewer-TOLERATED on sample bases —
  SX_f6i6 now tests the same tolerance for instances of OUR OWN loaded
  families (no such file has ever been judged anywhere; render-instances
  §1's corollary still holds).
* **One measurable writer-vs-Autodesk ordering delta, quantified** (§5):
  every commit APPENDS the new records at the END of the unit-0 segment,
  while every Autodesk-saved file keeps newest-modified record runs FIRST.
  At 6 chained loads the appended block becomes its own run (modal episode
  1016 at the segment tail after runs descending to 551) and
  `regdiff.run_law_report` flags exactly 1 newest-first violation — on the
  genesis chain AND the sample chain.  Small certified adds (V20..V29, L1a,
  walls_only, W1, WF) carry the same append-at-end bytes and PASSED, so
  append-at-end per se is tolerated at small N; whether the run-scale form
  is the audit's trigger is exactly what BX_f6/SX_f6i6 vs BX_f2 reads out.

## §1  The ladder (upload/reading order = maximum information first)

All files `experiments/instbug/<rung>.rvt`, staged copies
`experiments/acceptance/<rung>.rvt`; md5s + declared bases in
`experiments/instbug/probes.json`; full per-rung accounting in
`experiments/instbug/accounting.json` (regenerate: §7).  Fresh GUIDs are
minted per rebuild — re-hash after any rerun.

| # | rung | base | fams | inst | walls | the ONE thing it tests |
|--:|---|---|--:|--:|--:|---|
| 1 | **BX_f2** | G_ABPD | 2 | 0 | 0 | the SECOND family-document append alone (the narrowest open axis) |
| 2 | **BX_f1i1** | G_ABPD | 1 | 1 | 0 | ONE placed instance of OUR family, the demo's own path, N=1 |
| 3 | **SX_f6i6** | rst sample | 6 | 6 | 0 | THE CROSS-CHECK: the identical operation on Autodesk's base (expected PASS) |
| 4 | **BX_f6i6** | G_ABPD | 6 | 6 | 0 | the demo shape rebuilt (expected FAIL — reproduction control) |
| 5 | **BX_f2i2** | G_ABPD | 2 | 2 | 0 | the scale point between 1 and 6 |
| 6 | **BX_f6** | G_ABPD | 6 | 0 | 0 | the full load chain alone (symbol-only caveat) |
| 7 | **BX_f1** | G_ABPD | 1 | 0 | 0 | the single-append control (symbol-only caveat) |
| 8 | **BX_w_f1i1** | G_ABPD | 1 | 1 | 1 | the FULL PRODUCT SHAPE: load → certified W1-recipe wall → place (L→W→E, the product's order) |

**Empty-design caveat (stage_L8_lp4 lesson, render-instances §1):** BX_f1 /
BX_f2 / BX_f6 carry loaded families and NO model elements; a "Design is
empty" translation is an extractor short-circuit, NOT an audited pass.
Their FAIL is strong evidence; their PASS is weak.  The instance rungs are
the audited discriminators.  (Note G_ABPD itself translated as a browsable
model, not empty — the base's datum/sheet may force a real audit even on
the symbol-only rungs; the card text decides.)

**Reading the matrix** (also in `probes.json → reading_the_matrix`):
CTRL FAIL → round VOID.  BX_f2 FAIL → multiple loads alone convicted
(instances exonerated).  BX_f1i1 FAIL → instance-on-genesis convicted at
N=1 (R_inst_box's reading confirmed on G_ABPD proper with the demo's own
specimen path).  BX_f1i1 PASS + BX_f2i2/BX_f6i6 FAIL → the N>1 axis.
SX_f6i6 PASS + BX_f6i6 FAIL → base-lineage-specific (the genesis lineage's
registry state × the append/instance paths).  SX_f6i6 FAIL → the OPERATION
is defective everywhere; base exonerated; prime suspect becomes the
constructed instance template (V20..V29 cloned REAL host specimens and
passed; the demo path clones a schema-constructed template).
BX_w_f1i1 FAIL with BX_f1i1 PASS → the wall×family interaction in the
product's L→W→E order (the stage_W/F_ signature: families-then-walls FAILED
while walls-then-family — WF — PASSED; my rung holds family content and
wall mechanism constant, isolating the order/interaction).

## §2  Per-rung registry + byte accounting (vs the IMMEDIATE parent)

Every number below is from `experiments/instbug/accounting.json`
(recompute: `tools/bisect_instance_bug.py verify`).  Δ columns are child −
parent; "reg-surface adds" = added ids the ADocument indexes (regdiff typed
walk) / added ids it does not.

| rung | immediate parent | Δunits | ΔCD | ΔCT | ΔFM | ΔElemTable (ids) | streams changed (bytes) | val err/warn | coherent | survivor law | reg-surface adds |
|---|---|--:|--:|--:|--:|---|---|---|---|---|---|
| BX_f1 | G_ABPD | +1 | +1 | +1 | +1 | +18 (twins ×14, Family, FamilySurrogate, FamilySymbol, FamSymSurrogate) | BasicFileInfo −216, ContentDocuments +462, DocumentIncrementTable −129, ElemTable +577, Latest ±0, Partitions/21 +11,367 | 0/1 | yes | 0 rm / 0 mod | 2 / 16 |
| BX_f2 | stage_L1 (=BX_f1 bytes) | +1 | +1 | +1 | +1 | +18 | BasicFileInfo ±0, ContentDocuments +310, ElemTable ±0¹, Latest ±0¹, Partitions/21 +9,360 | 0/1 | yes | 0 / 0 | 2 / 16 |
| BX_f6 | stage_L5 | +1 | +1 | +1 | +1 | +18 | same shape as BX_f2 | 0/1 | yes | 0 / 0 | 2 / 16 |
| BX_f1i1 | stage_L1 | 0 | 0 | 0 | 0 | +1 (instance 1472584) | BasicFileInfo −60, ElemTable ±0¹, Partitions/21 +317 | 0/1 | yes | 0 / 0 | 0 / 1 |
| BX_f2i2 | stage_L2 | 0 | 0 | 0 | 0 | +2 | same shape | 0/1 | yes | 0 / 0 | 0 / 2 |
| BX_f6i6 | stage_L6 | 0 | 0 | 0 | 0 | +6 | BasicFileInfo −60, ElemTable ±0¹, Partitions/21 +1,023 | 0/1 | yes | 0 / 0 | 0 / 6 |
| BX_w_f1i1.hop_wall | stage_L1 | 0 | 0 | 0 | 0 | +1 (SWall 1472584, baked B-rep) | BasicFileInfo −28, ElemTable ±0¹, Partitions/21 +1,560 | 0/1 | yes | 0 / 0 | 0 / 1 |
| BX_w_f1i1 | the walled file | 0 | 0 | 0 | 0 | +1 (instance 1472585) | BasicFileInfo −24, ElemTable ±0¹, Partitions/21 +317 | 0/1 | yes | 0 / 0 | 0 / 1 |
| SX_f6i6 | rst stage_L6 | 0 | 0 | 0 | 0 | +6 (14,044 → 14,050 rows) | BasicFileInfo −60, ElemTable +24, Partitions/21 +1,023 | 0/1 | yes | 0 / 0 | 0 / 6 |

¹ raw stream bytes changed, size unchanged (fixed-slack stream).

Constant on EVERY hop, both bases: `Global/PartitionTable` (1 row
'Workset1', byte-identical) and `Contents`/DocumentStorageIndex (counters
byte-identical) — see §3.  The rst chain's own loads (stage_L1..L6 on the
sample) carry the identical per-load shape: +1/+1/+1/+1, +18 rows each,
coherent at every step — the loader's bookkeeping does not distinguish the
bases at the count/GUID level.

Notes.  (a) The FIRST load onto G_ABPD also rewrites
`Global/DocumentIncrementTable` (−129 B); every subsequent commit re-emits
it byte-identically — the commit path normalizes the DIT once, then holds
it stable.  (b) The loads' ElemTable payload grows +577 B on the first
append and stays size-stable after (slack).  (c) BasicFileInfo deltas are
the per-commit identity rewrite (fresh GUIDs, our authoring string —
identity gate PASS on every rung).

## §3  Two charter suspects measured DEAD; one still open

* **PartitionTable rows**: 1 entry ('Workset1') in G_ABPD, in every rung,
  in the untouched rst sample (53 save units), and in every intermediate.
  The workset partition table does not track save units in Autodesk's own
  files; our append path leaves it byte-identical.  DEAD as a suspect.
* **StorageIndex (`Contents`)**: counters and counter_g are byte-identical
  across G_ABPD (1 unit), all our rungs (2..7 units), and the rst sample
  (53 units).  The storage index does not count documents in Autodesk's own
  files; our path leaves it untouched.  DEAD as a suspect.
* **Unit numbering / append mechanics**: our unit splice appends the new
  save unit at the partition tail with its GUID registered in all four
  registries (walker clean, `id_sets_identical` true per load report).
  Counts coherent at every N on both bases.  What the census CANNOT see —
  and stays open for the viewer matrix — is any ordering/placement
  constraint among units or records the audit enforces beyond counts (§5).

## §4  Registration facts (regdiff, per rung)

* Each load registers exactly **2 of its 18** new host ids in the document
  object: the FamilySurrogate →
  `AppInfoManager[FamilyMgr].m_arrLoadedFamilyInfo[k].m_surrogateId` and
  the FamilySymbol →
  `AppInfoManager[ElementTrackingData].m_symbols[cat].m_elemIdSet` .  The
  other 16 (14 ParamElemFamily twins, the host Family, the FamSymSurrogate)
  are referenced only element-to-element — identical on both bases.
* The **placed instances appear in ZERO ADocument leaves** (typed walk of
  the whole decoded document object), on G_ABPD and on rst alike.
  `commit_new_elements` registers nothing; only the loader's `place=True`
  branch would have written the instance into ElementTrackingData, and the
  product path (stage E) never uses it.  Precedent: V20..V29's created
  instances (of the samples' own symbols) were equally unregistered and
  PASSED — on sample bases.  An instance of OUR OWN loaded family has never
  been viewer-judged on ANY base (L1a/L_v2/L_downlight are all
  `place=False`; R_inst_box FAILED on ZA_deep) — SX_f6i6 is the first clean
  sample-base test of exactly that.
* Instance ElemTable rows: `creation_ep == modified_ep == user_modified_ep
  = 1016` (the host's current episode, no new History row), owner INVALID,
  partition 0, appended as the last row; record positions: last in each seq
  segment.  Identical shape on both bases (SX rows differ only in
  index/watermark).
* `run_law_report` (the corpus record-order law: runs grouped by modified
  episode, newest FIRST, id-ascending inside): **id-ascending holds
  (≥0.995)** everywhere; the newest-first clause is where our writer
  differs — §5.

## §5  The one ordering delta (open, and exactly what the ladder reads on)

Our commits append new records at the segment END.  Autodesk-saved files
put the newest-modified run FIRST.  Measured consequences:

* ≤2 loads (≤ ~40 records): the appended block is absorbed into the tail
  run (modal episode stays 551); `run_law_report` reads 0 violations —
  BX_f1, BX_f2, BX_f1i1, BX_f2i2, BX_w_f1i1 all read clean.
* 6 loads (108+ records): the block becomes its own run — modal episode
  1016 at the tail, after runs descending 1015 → 551 — **1 newest-first
  violation**: BX_f6, BX_f6i6, and the rst-chain SX_f6i6 all read it.  The
  untouched rst sample reads 0.
* The BYTE fact (append-at-end) is present in every certified small-N file
  (V20..V29, L1a, walls_only, W1, WF) — viewer-tolerated there.  So the
  ordering delta convicts nothing by itself; but it is the only
  writer-vs-Autodesk structural delta this instrument found that SCALES
  WITH N in the direction of the evidence (1 load WF PASS; 6-load demo and
  8-load stage_W FAIL).  BX_f2 (0 violations) vs BX_f6 (1 violation), with
  BX_f1i1/BX_f2i2 in between, brackets it.

**Validator note (charter: "when you find it, ADD the check").**  The audit
rule is NOT yet identified — every failing file in the evidence matrix is
VALID 0 errors under every check we have, and this ladder's job is to make
the viewer name the axis.  Two checks are READY to be added to
`rvt.validate` the moment the verdicts land on their side (each is one
measured predicate of this instrument, both currently true of every
Autodesk-saved file and false/absent in ours at some N): (1) newest-first
run order in unit-0 segments (§5); (2) — only if SX_f6i6 fails —
placed-instance registration in ElementTrackingData (§4).  Wiring either in
BEFORE a verdict names it would make the validator reject certified-PASS
shapes (V20..V29 carry append-at-end), so the checks wait for the readout.

## §6  Staging record + requests for the orchestrator

* **Batch 32 staged** (control first): `CTRL_G_ABPD_b32.rvt` (byte-identical
  G_ABPD), then BX_f2, BX_f1i1, SX_f6i6, BX_f6i6, BX_f2i2, BX_f6, BX_f1,
  BX_w_f1i1.  Manifest `experiments/acceptance/batch_32.json`; every
  probe's declared base certified (G_ABPD) or an Autodesk sample source
  (rst).  Gate: `probe_batch check` ADMISSIBLE, zero violations.
* **Read the cards, not just the verdicts** — for the symbol-only rungs
  (BX_f1/f2/f6) record whether the card says 'Design is empty' (unaudited)
  vs a real audit outcome; for instance rungs read the model tree (an
  instance node under the level = the render answer for free).
* **Batch-numbering hygiene**: `probe_batch.next_batch_number` scans only
  `experiments/acceptance/`, but batch numbers are campaign-global and 17,
  28, 29, 31 were already used by the 2023/2024/2025 campaigns in their own
  dirs.  My first stage minted a colliding `batch_17.json`; it was removed
  and restaged as batch 32 via a campaign-global scan
  (`bisect_instance_bug.stage` does this itself).  DIFF PROPOSAL for the
  probe_batch owner (their territory): make `next_batch_number` glob
  `experiments/**/batch_*.json` recursive so no future stream can collide.
* After the readout: the matrix cell that fires names the next stream
  (§1); the accounting.json rows give that stream its exact byte-level
  starting point per rung.

## §7  Reproduce (repo root, `.venv/bin/python`)

```
tools/bisect_instance_bug.py build            # all 8 rungs + accounting + probes.json (~4 min)
tools/bisect_instance_bug.py build --only BX_f2,BX_f1i1
tools/bisect_instance_bug.py verify           # re-run the accounting gates on the emitted files
tools/bisect_instance_bug.py stage            # probe_batch gate + G_ABPD control (campaign-global batch no.)
tools/rvt_validate.py experiments/instbug/<rung>.rvt      # 0 errors each
tools/probe_batch.py check experiments/instbug/BX_*.rvt experiments/instbug/SX_f6i6.rvt
python -m pytest tests/test_instbug.py -q     # 9 tests
```

## §8  VALIDATOR DRIFT (2026-08-05 00:02) — the fix stream's rules land; the ladder's findings decompose EXACTLY along its axes

Timeline: this ladder was emitted ~23:55–23:59 and staged as batch 32 at
~00:03 with every rung `rvt.validate` VALID 0 errors.  At **00:02** the
sibling **instbug-fix** stream (`src/rvt/famload_fix.py`, territory:
that module + `experiments/instbug/fix/**` + the rvt.validate
loaded-content rule) landed two corpus-law checks in the shared validator:

* **D1** — a placed FamilyInstance's `m_pConnectorManager` must be class
  `FamilyInstanceConnectorManager` or null (corpus 13,636/13,636); the
  product path (`ifc_intent._connector_manager_for`, and famgen's
  `author_family_instance`) writes base-class `ConnectorManager`.
* **D2** — `ContentTable.m_ContentRecSet` ascending by ContentKey GUID
  (bytes_le; corpus law, `rvt.famload` sorts); chained `famgen.loader`
  loads APPEND, so every N≥2 chain is unsorted (GUIDs are random).

Re-verified against the CURRENT validator
(`tools/bisect_instance_bug.py verify`, persisted as `validator_now` per
rung in accounting.json + probes.json):

| rung | D1 (instances) | D2 (N≥2 loads) | unexpected errors |
|---|--:|--:|--:|
| BX_f1 | 0 | 0 | 0 |
| BX_f2 | 0 | 1 | 0 |
| BX_f6 | 0 | 1 | 0 |
| BX_f1i1 | 1 | 0 | 0 |
| BX_f2i2 | 1 | 1 | 0 |
| BX_f6i6 | 1 | 1 | 0 |
| BX_w_f1i1 | 1 | 0 | 0 |
| SX_f6i6 | 1 | 1 | 0 |

**The mapping is exact**: D1 fires iff the rung places instances; D2 fires
iff the rung chains ≥2 loads; nothing else fires anywhere.  The two
independently-mined defects decompose precisely along this ladder's two
axes — corroborating the axis split from the static side before any viewer
verdict.  The failing evidence files read the same way (DEMO_250v_room:
D1+D2; the demo file is the ladder's own shape).  Note D1/D2 cannot be the
whole story by themselves: **R_inst_box FAILED carrying NEITHER** (one
load, null manager — the fix stream's own docstring concedes it), and
BX_f1's clean state matches WF's pass.  The A/B decides.

**Status under the hard rule** ("every emitted probe validator 0 errors"):
held at emission; under the current validator the unfixed rungs carry
exactly the D1/D2 findings they exist to reproduce — the demo's own
defects, now named.  They are classified, not hidden (`validator_now` in
probes.json; gate = zero UNEXPECTED errors, which holds on all 8).
"Fixing" these rungs would destroy the reproduction control and duplicate
the fix stream; the two ladders are the A/B:

* UNFIXED (mine, batch 32): BX_f2, BX_f1i1, BX_f6i6, SX_f6i6 …
* FIXED (fix stream, `experiments/instbug/fix/`): `BXfix_f1i1.rvt`,
  `BXfix_f6i6.rvt`, `DEMO_250v_room_v2.rvt` (+ their A/B order pair).

**Joint reading** (upload the pairs in the SAME round, one control):
unfixed FAIL + fixed PASS at the same rung = D1/D2 (whichever the rung
carries) is the mechanism, PROVEN; both FAIL = the mechanism is deeper
(and my §5 run-order delta plus the fix stream's R_inst_box caveat are the
next suspects); unfixed PASS = the audit does not enforce that corpus law
on that shape (and the empty-design caveat applies to the symbol-only
rungs).  My §5 validator-check candidates stand, now refined: the
run-order (newest-first) check remains the one measured writer-vs-corpus
delta NO current validator rule covers.

## BRANCH STATE

* **status**: DONE — LADDER BUILT, VERIFIED, STAGED (batch 32, control =
  G_ABPD copy).  STOPPED AT READY: nothing uploaded; the viewer queue is
  the orchestrator's.
* **no VCS** (tree is not a git repo).  Files written: `tools/
  bisect_instance_bug.py`, `experiments/instbug/**` (8 rungs + probes.json
  + accounting.json + `_build/` chains), `tests/test_instbug.py`, this
  record; staging copies + `batch_32.json` in `experiments/acceptance/`
  via `probe_batch.stage` (its designed output).  A colliding
  `batch_17.json` + `CTRL_G_ABPD_b17.rvt` were created and REMOVED within
  this session (§6).  Nothing else touched.
* **gates**: all 8 rungs validator VALID 0 errors AT EMISSION (1 known
  inherited warning), four-registry coherent, identity PASS, survivor law
  0/0, probe_batch ADMISSIBLE; staged copies md5-verified; control md5 ==
  G_ABPD.  BX_f6i6 == DEMO_250v_room in registry shape and row count.
  Under the CURRENT validator (post-drift, §8): zero UNEXPECTED errors on
  every rung; the D1/D2 findings land exactly on the rungs whose axis they
  belong to (the reproduction is faithful by measurement).
* **load-bearing measurements**: PartitionTable + StorageIndex dead as
  suspects (§3); four-registry coherent at every N on both bases (§2);
  placed instances unregistered in the ADocument on BOTH bases (§4); the
  append-at-end vs newest-first run-order delta, threshold-quantified (§5).
* **tests**: stream-local `tests/test_instbug.py` = **10 passed** (1.0 s),
  including the drift-aware check that the current validator's findings on
  the unfixed ladder are EXACTLY {D1 on instance rungs, D2 on N≥2-load
  rungs, nothing else}.  Full-suite rule: per
  `docs/inbox/SUITE-COORDINATION.md` the canonical run (pid 27375) is
  adopted; NO full-suite run was launched by this stream; its published
  count was still pending at the time of writing.
* **NOT VIEWER-TESTED**: every claim above is the machine gate; no
  acceptance claim is made.  All rungs are PROOF-ONLY (genesis-lineage /
  sample bases + our layer).
* **next action (orchestrator)**: upload batch 32 in manifest order,
  IDEALLY in the same round as the fix stream's `BXfix_f1i1` /
  `BXfix_f6i6` / `DEMO_250v_room_v2` counterparts (one control covers
  both — the unfixed/fixed pairs are the mechanism A/B, §8); verdicts land
  in `docs/coverage/viewer-certified.json`; read with §1's matrix + §8's
  joint reading.

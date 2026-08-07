# inbox — instbug-forensics (THE FORENSIC DIFF: what the audit sees on the genesis lineage)

Stream: **instbug-forensics** (2026-08-05).  Charter: the product-path bug —
files that LOAD MULTIPLE family documents or PLACE INSTANCES onto the genesis
lineage trip Revit's consistency audit (Revit-DocumentCorruption, extractor
−1073742517) while the same operations on sample bases pass.  Diff EVERYTHING
about the family-load + instance registration between the matched pair
`L_v2_panel_loaded.rvt` (PASS) and the demo's `stage_L1_pp1.rvt` (failing
lineage), reconcile `docs/inbox/render-instances.md`, and rank candidate
defects by the palette discipline: *present in EVERY failing file, absent in
EVERY passing file*.

**Territory touched ONLY:** `tools/instbug_forensics.py` (new, read-only over
every stream), `experiments/instbug/forensics/{surveys,deltas}.json`, this
record.  No `.rvt` emitted, no `src/` edited, no tests added, no browser.
Everything below was measured this session from the file bytes; reproduce with
`.venv/bin/python tools/instbug_forensics.py all` (~2 min; per-pair reruns via
`survey` / `delta` / `unitdiff` subcommands).

---

## 0. One-screen verdict

* **The registration machinery is NOT byte-broken where everyone has been
  looking.**  The four registries of the failing-lineage load
  (`stage_L1_pp1`) are entry-for-entry the same shape as the viewer-PASSED
  loads (`L_v2` on rstbasic, `WF_nofix` on the certified walls-only base):
  one GUID in all four surfaces, sorted where n=1, coherent counts, correct
  separators, correct ContentDocuments grammar, correct FamilyMgr entry,
  identical ContentTable record shape `{author 'rvt-writer', creation=mod=
  1016, user=-1, episode_counts [(1016, unit_records)]}`.
* **Two corpus-law violations and one never-judged shape DO separate fail
  from pass** (§3: the ranked list): the **ContentTable order law** breaks at
  the 2nd load (chronological append vs the GUID-`bytes_le`-sorted corpus
  form famload enforces — CT no longer matches the CD stream), the
  **host-symbol ConnectorDataCell** exists in five of six failing files and
  in ZERO passing files, and **no placed instance of OUR loaded family has
  ever passed a real audit on ANY base** — the brief's premise that
  L_v2 was "loaded+placed" is corrected by its own bytes: **L_v2 contains 0
  instances of our symbol** (`place=False`; famload has no placement path),
  and the famgen `place=True` outputs were never uploaded.
* **genesis-12's two-null mechanism is REFUTED as the discriminator**:
  `WF_nofix` carries both nulls (`Family.m_oFamDimConstrMgr=None`,
  `FamilySymbol.m_pMoveRestrictions=None`) and PASSED a real audit (walls
  present, real model tree).  Verdict #27 already recorded the pass; the
  bytes here confirm the nulls are aboard that passing file (§2.4).
* **The single factor that scores perfectly on the ranking criterion is an
  OPERATION shape, not (yet) a byte**: *a `commit_new_elements` run on a
  partition that already contains an our-spliced family unit* ("post-load
  commit") is present in every audit-FAIL and absent from every audit-PASS —
  but the byte forensics show its rewrite is surgical (the spliced unit is
  **raw-byte-identical** across the next load's commit; only unit-0's three
  appended segments + headers/trailers/ElemTable/BFI change; gzip
  recompression of foreign blocks is V20-proven tolerated).  Revit sees only
  bytes, so §3.1 states exactly what byte states co-occur with it and the
  §5 probes are designed to break the confound.

---

## 1. The matched pair, measured (charter core)

`stage_L1_pp1` = G_ABPD + ONE panel family, `rvt.famgen.loader
.load_family_into_project(place=False)` — the demo ladder's first rung.
`L_v2_panel_loaded` = rstbasic + ONE panel family, `rvt.famload
.load_family_documents` (no placement).  Same host ids by coincidence of
watermarks (family 1472566, twins 1472567–80, surrogate 1472581, then
1472582/1472583).  Full surveys in `experiments/instbug/forensics/
surveys.json`; deltas in `deltas.json` (`PASS_load_on_sample` vs
`FAIL_lineage_load_on_genesis` vs `PASS_load_on_walls_base`).

Identical between the two loads (all measured, not assumed): four-registry
GUID presence; ContentDocuments sorted insert + intact 14-byte end record;
ContentTable record field-shape; FamilyMgr single-GUID entry; ElemTable row
tuples (episodes 1016/1016/1016, owner semantics, watermark raise covering
the embedded ids); unit-0 append position (before each seq sentinel);
History/PartitionTable untouched; `Contents` (DocumentStorageIndexImpl 0x53e)
byte-constant — its 9 counters `[612,628,…,517]` are the same in rstbasic,
G_ABPD and every derivative: the storage index never varies and indexes
nothing we change (charter's "StorageIndex" axis: measured, exonerated).

The whole loader delta (famload "annotation flavour" vs famgen "component
flavour"), from field-level diffs of the same-id elements:

| surface | famload / L_v2 (PASS) | famgen / stage_L1 (fail lineage) |
|---|---|---|
| `Family.m_oFamDimConstrMgr` | `FamDimConstrMgrImpl{}` (lawful empty) | **None** |
| `FamilySymbol.m_pMoveRestrictions` | empty `Matrix` | **None** |
| `FamilySymbol.m_arrConnectorData` | `[]` | **1 ConnectorDataCell** |
| symbol seq-103 / geometry | SerializedDummy; `m_geomSteps/m_pGeomTable` None | **baked GElement** + GeomStepList + GeomTable |
| `m_hasParamDefValue` | 1 | 0 |
| `m_strongRefs` | [] | 2 refs |
| `m_geomTag2MaterialId` | [] | 1 entry |
| id order | FamSymSurrogate **before** FamilySymbol (= native rstbasic 1417014 < 1417017) | inverted (symbol 1472582 < surrogate 1472583) |
| FamilyTypeTable | one blank ' ' row, idx 0 | 2 rows, idx 1 |
| preview view | viewFamily 107 / type 6 | 109 / 1, scale 0.05 |
| `m_oFamDoc.m_coreIds` | [] (rst has no −2001040 GStyle) | [124] (+ load-class row when host has one — G_ABPD does **not**: `load_class_host = -1`, the 'Power' row the rme-certified path binds is absent from the genesis lineage) |
| ADocument registrations | CT sorted-in; FamilyMgr sorted; ETD row **skipped** when the host lacks the category | CT **appended**; FamilyMgr appended; ETD `m_symbols` row **created** (−2001040) |

Which of these matter?  `WF_nofix` (famgen, bare box, certified walls-only
base, load-as-last-op) PASSED a real audit carrying: both nulls, baked
symbol geometry, `m_hasParamDefValue 0`, the id-order inversion, the created
ETD row, the appended (n=1, trivially sorted) CT entry.  **Every famgen
flavour delta except the ConnectorDataCell is therefore exonerated as a
standalone killer** — and the cell is exactly what the box lacks and every
electrical room family carries (measured: stage_W 8/8 symbols with a cell,
F_msb 1/1, room2500 8/8, demo 1 per panel; every passing file: zero cells).

## 2. The evidence matrix and what each PASS exonerates

Verdicts from `docs/coverage/viewer-certified.json` + genesis-audit
ORCHESTRATOR VERDICTS #24–#28; byte facts all measured here.

| file | ops (chronological) | verdict | famgen | conn cell | inst-of-ours | ≥2 loads (CT unsorted) | post-load commit |
|---|---|---|---|---|---|---|---|
| G_ABPD / ZA_deep / walls_only / W1 / V20..V29 | no family load | PASS | – | – | – | – | – |
| L1a / L_v2 / L_downlight (rst sample) | load LAST (famload) | PASS | – | – | – | – | – |
| WF_nofix / WF_fix (walls base) | walls in base → load LAST | **PASS** | ✓ | – | – | – | – |
| F_lp4 | load → walls | FAIL | ✓ | ✓ | – | – | ✓ |
| F_msb | load → walls | FAIL | ✓ | ✓ | – | – | ✓ |
| R_inst_box | load → instance | FAIL | ✓ | – | ✓ | – | ✓ |
| stage_W_loaded_walls | 8 loads → walls | FAIL | ✓×8 | ✓ 8/8 | – | ✓ | ✓ |
| electrical_room_2500a | 8 loads → walls → 8 inst | FAIL | ✓×8 | ✓ 8/8 | ✓ | ✓ | ✓ |
| DEMO prompt_room | 6 loads → 6 inst | FAIL | ✓×6 | ✓ | ✓×6 | ✓ | ✓ |
| stage_L8_lp4 | 8 loads, nothing after | non-test ("Design is empty") | ✓×8 | ✓ 8/8 | – | ✓ | ✓ (loads 2–8) |

(`R_inst_downlight` fails with the third signature — Revit-InternalError
crash, family content — out of scope per charter; noted that it is also a
post-load commit file.)

### 2.1 Exonerations proven this session (byte + verdict)

* **Wall content**: F_lp4's four walls ≡ `walls_only`'s four walls
  byte-identical modulo own ids (4/4 objects; measured) — extends
  render-instances' stage_W finding to the F_ set.
* **Commit's re-emission of foreign units**: V20 = rstbasic + one instance
  commit; every one of the 52 native family units was recompressed
  (member_len shifts, e.g. block0 17132→17136, payload md5 unchanged) and
  the file PASSED.  And the second demo load's commit left PP-1's spliced
  unit **raw-byte-identical** (`unitdiff stage_L1 stage_L2`: separator +
  blocks + trailers 7302 B unchanged) — the commit path's partition rewrite
  is byte-surgical: only the stream header count, unit-0's three last
  blocks (A/B/C + member + trailer), ElemTable, BasicFileInfo, DIT-scrub,
  and the end-slack change (skeleton diff: 10 diffs, all legitimate).
* **End-record slack**: grows monotonically on every rewrite (rstbasic 68 B
  → G_ABPD 1,862 → WF_nofix 3,067 → stage_W 7,842); present on BOTH sides
  (passing WF/W1/walls_only carry KBs of it) — tolerated, not the
  discriminator.
* **FamilyMgr "ghost" entries**: the 9 empty-GUID entries (surrogates 8484…
  876494) in every genesis-lineage file are **native** — rstbasic itself
  carries the same 9 among its 50 — not a K4-reconciliation artifact.
* **Unit order vs CD order**: the corpus stores partition units GUID-sorted
  and CD-matching (rstbasic: unit order == CD order == sorted).  L_v2
  (PASS) appended its unit at the END while its CD entry sorted in —
  breaking both unit-sortedness and unit/CD correspondence — **tolerated**.
* **Record-order run law**: appended records extend unit-0's tail run in
  every writer output; V20 (PASS) and L_v2 (PASS) violate/stretch the
  (modified-ep DESC) law exactly like the failing files (run_law_report:
  L_v2 1 violation-PASS, F_lp4 0 violations-FAIL) — not the discriminator.
* **ETD row creation, symbol-id order inversion, `m_hasParamDefValue 0`,
  baked symbol geometry, both famgen nulls**: aboard the passing WF_nofix.
* **Instance absent from `ETD.m_elems`**: V20's created instance is not in
  rstbasic's ETD either — PASS (sample-base-conditional exoneration; the
  genesis-side row −2001040 exists and is natively empty `[]`).

### 2.2 Reconciliation with docs/inbox/render-instances.md (charter item)

Its walls+8-families finding — stage_W differs from stage_L8_lp4 by exactly
the wall records, walls byte-clean, units record-identical, therefore "the
loaded family layer never survived a real audit; the walls merely FORCED
one" — **stands and sharpens**: the corrupt state pre-exists in stage_L8
(unaudited because symbol-only = empty design), and this session names what
that state uniquely contains: an 8-entry chronological (unsorted)
ContentTable disagreeing with the sorted CD stream, 8 connector-cell
symbols, 7 post-load commits.  Its §3 loader A/B (famgen bakes symbol
GElement, famload writes SerializedDummy) is confirmed field-level here and
the baked side is now viewer-exonerated by WF_nofix.

### 2.3 The demo's instances carry a shape no certified file exhibits

prompt_room's six instances (1472879–84, stage-E `ConstructedSpecimens`
path): `m_createdPhaseId = -1` and **no phase in the header deletion list**
(`[311, symbol, self]`), while every certified created element carries
`ProjectPhase 86961` (V20 instance: `[311, 86961, 1411287, self]`; W1/
walls_only walls: 86961; R_inst_box kept 86961 via the R5-specimen path —
so this is demo-specific, additional to whatever kills R_inst_box).  Also
shared by all our genesis-side instances vs the V20-certified shape:
`m_geomSteps None` + 1-row `m_pGeomTable` (V20: GeomStepList + 156-row
cloned table), 2-cell `m_cellList` (V20: 5), `m_useOffsetPos False` (V20:
True), rebuilt `m_pConnectorManager` (V20: None).

### 2.4 genesis-12's two-null mechanism — status after WF

`build_g12_probes.py` predicted "WF_nofix FAIL + WF_fix PASS = proof".
Verdict #27: **both PASSED**.  Measured here: WF_nofix's symbol
`m_pMoveRestrictions=None`, family `m_oFamDimConstrMgr=None` — the nulls are
in the passing file.  The pure null-pair hypothesis is dead; a conditional
variant (nulls audited only when an instance walks the symbol) remains
consistent with R_inst_box/demo/room2500 but is indistinguishable from
candidate #2 until the §5 probes run.

---

## 3. THE RANKED DEFECT LIST (the deliverable)

Criterion: present in EVERY audit-failing file / absent in EVERY
audit-passing file; then concreteness of the byte mechanism.  Every failing
file carries ≥2 candidates — the set is CONFOUNDED; §5 is the minimal probe
set that separates them.

**#1 — POST-LOAD COMMIT (operation-shape candidate; perfect separation,
no byte mechanism found).**  `rvt.commit.commit_new_elements` running on a
file that already contains an our-spliced family unit: present in 6/6
failing files (loads 2..N of every chain, every wall stage after a load,
every instance commit), absent from 100% of passing files (every certified
load — L1a, L_v2, L_downlight, WF_fix, WF_nofix — was the file's LAST
operation; V20..V29 committed onto native-unit files only; H1/H2 host
native symbols, no load).  BUT: the commit's rewrite is proven
byte-surgical (§2.1), so if this is causal the flipped byte is one nobody
has measured — and if it is not, it is the shadow of #2/#3/#4, which
co-occur with it everywhere.  Probes P2/P1 decide (§5).  Note the demo
would hit this even with #3/#4 fixed, so the fix stream should treat P2's
verdict as gating for the product path.

**#2 — A PLACED INSTANCE OF OUR LOADED SYMBOL (never passed anywhere).**
Present in R_inst_box + demo + room2500; absent from every passing file —
and from every passing file ON THE SAMPLE BASES TOO: the evidence matrix's
"L_v2 loaded+placed PASS" premise is false in the bytes (L_v2: 0
FamilyInstances of symbol 1472583), and no famgen `place=True` output was
ever uploaded (asset-forge L4/L5 files are validator-proven only;
`stage_L8_lp4`'s "certified" row is the discredited empty-design non-test —
still uncorrected in coverage).  So "instance-of-our-family" is unjudged on
samples and 3/3 failing on the genesis lineage.  Byte evidence of deviation
from the ONLY certified created-instance shape (V20, native symbol): §2.3
list; plus the symbol it points to carries famgen's nulls (#5) and, for the
demo, the phaseless header.  Probe P3 decides whether this is base-
independent (the instance path itself) or genesis-conditional.

**#3 — THE HOST-SYMBOL ConnectorDataCell (famgen electrical flavour;
never in a passing file).**  `FamilySymbol.m_arrConnectorData = [1 cell]`:
present in F_lp4, F_msb, stage_W (8/8), room2500 (8/8), demo (each panel) —
5/6 failing files (absent only from R_inst_box, whose box has no
connectors); absent from 100% of passing files (WF box: 0 cells; famload
writes `[]`).  The cell grammar was inferred from the rme specimen and has
NEVER been viewer-tested; on the genesis lineage it is additionally built
with `load_class_host = -1` (the host has no 'Power' /
ElectricalLoadClassification row → the −1140014 row is omitted — a cell
variant that exists in no corpus file).  This is the ONLY famgen-symbol
delta not exonerated by WF_nofix.  Probe P1 decides.  Together #2 ∪ #3
covers 6/6 failing files with 0 passing hits — the strongest two-defect
model.

**#4 — ContentTable ORDER: chronological appends break the GUID-sorted
corpus law from the 2nd load on (CT ≠ CD).**  Every corpus file and every
passing file has `m_ContentRecSet` in ascending `UUID.bytes_le` order,
matching the CD stream (rstbasic measured True/True; famload sorts by
design).  `rvt.famgen.loader.register_in_host_adocument` APPENDS —
measured: demo CT order `[ae104549, 48b94937, 0f0089db, c06f867a, 2c099cde,
eeab853e]` = load order, sorted=False from stage_L2 onward; stage_W /
stage_L8 / room2500 8-entry order unsorted; the CD stream stays sorted
(`insert_content_document` sorts) — so **the two content surfaces disagree
in every N≥2 file and agree in every passing file** (n≤1 trivially).
Mechanism shape: a reader that walks CT and CD positionally attributes
episode counts/authors to the wrong documents from the first divergence —
squarely a "consistency audit" smell.  Covers stage_W/room2500/demo but not
R_inst/F_ singles → cannot be the sole cause; cheap to fix regardless (sort
on append, famload-style).  Probe P4 decides.

**#5 — famgen's two nulled owned pointers (genesis-12) — DEMOTED:
refuted as a standalone cause by WF_nofix's PASS (nulls aboard, real
audit).**  Still corpus-anomalous (`m_oFamDimConstrMgr` present 831/831
host Families, `m_pMoveRestrictions` 2710/2710 symbols) and still present
in every failing file — but the criterion requires absence from passing
files, and WF_nofix breaks it.  Only viable as a CONJUNCT of #2 (audited
when an instance walks the symbol); the `fix_family_layer_records` repair
is already built and cheap, so the fix stream should apply it to the
instance probes anyway (it can only reduce anomaly surface).

**#6 — measured and exonerated as standalone killers** (each has a passing
counterexample; listed so nobody re-suspects them): unit-append order vs CD
(L_v2), end-record slack growth (all passes), ETD `m_symbols` row creation
(WF), symbol/surrogate id inversion (WF), baked symbol geometry (WF),
`m_hasParamDefValue 0` (WF), instance absent from ETD `m_elems` (V20,
sample-conditional), record-order run-law stretch (V20/L_v2), commit's
recompression of foreign units (V20), identity scrubs of BFI/DIT (all
writer outputs), Contents/DocumentStorageIndex (byte-constant everywhere),
FamilyMgr empty-GUID entries (native), History/PartitionTable (untouched,
byte-same), the History invariant count==max_ep+1 (holds in every file
here), ElemTable footer shape (uniform).

---

## 4. Corrections other records should carry

1. **Evidence-matrix premise**: "L_v2_panel_loaded = loaded+placed" → in
   the bytes it is loaded, NOT placed (0 instances of our symbol;
   `place=False` — render-instances §1 already said this; the demo-bug
   charter restated the stale version).  Consequence: *no placed instance
   of our loaded family was ever sample-certified* — P3 fills the hole.
2. `docs/coverage/viewer-certified.json` still lists `stage_L8_lp4.rvt` as
   certified "family LOAD + instance PLACEMENT ... (PASS)" — it contains 0
   instances and its pass is the empty-design short-circuit
   (render-instances §1, confirmed here: 8 units, 0 FamilyInstance).
   The row keeps poisoning briefs; it should be annotated like the #15-era
   retractions (orchestrator territory).
3. genesis-12's "WF_nofix FAIL expected" table is superseded by #27 —
   record updated by this file's §2.4 (their territory to fold in).

## 5. The decisive probe set (for the fix stream — recipes, not files)

Batch law: certified base + byte-identical control per round
(`tools/probe_batch.py stage`).  All bases below are viewer-certified.
Every probe is a single-variable read against §3.

* **P1 `WF_panel`** = `electrical_room_2500a_walls_only.rvt` + the PRL1X
  panel (same `build_room_product` kwargs as F_lp4) loaded LAST (famgen,
  `place=False`, nothing after).  FAIL → **#3 confirmed** (the cell/panel
  layer kills regardless of order; #1 collapses for the F_ class);
  PASS → #3 dead, #1 alive for F_.
* **P2 `WF_box_wall`** = `WF_nofix.rvt` (certified this session? if the
  orchestrator prefers, rebuild from walls_only) + ONE more wall committed
  after the load (box family: no cell, no instance, CT n=1).  The PUREST #1
  probe.  FAIL → post-load commit corrupts; diff its bytes against
  WF_nofix (this tool) — the delta is ONLY the wall records + ElemTable +
  BFI + slack, so the flipped byte becomes findable.  PASS → **#1 refuted
  entirely**; the demo bug decomposes into #2/#3/#4.
* **P3 `L_v2_placed`** = rstbasic + panel loaded + ONE instance placed
  (stage-E recipe with the real phase).  FAIL → **#2 is base-independent**
  (the instance/symbol linkage path itself); PASS → #2 is
  genesis-conditional (and P3's twin on G_ABPD isolates the base term).
* **P4 `WF_2box` / `WF_2box_sorted`** = walls_only + TWO box loads (CT 2
  chronological entries), and the same file with ONLY the CT re-sorted in
  place (adocument edit, byte-diff = the two records' order).  unsorted
  FAIL + sorted PASS → **#4 proven** (and the validator check lands);
  both-FAIL → the 2nd-load mechanics (#1) own it; both-PASS → #4 dead at
  n=2 (retest at n=6 with the demo GUIDs).
* **P5 demo-phase fix** (after P1–P4 land): stage-E instances built with
  the base's ProjectPhase (86961 is present and ours in G_ABPD) + header
  deletion carrying it — removes the §2.3 demo-only anomaly.

## 6. Cross-territory diffs proposed (NOT applied — owners' territory)

* `src/rvt/famgen/loader.py::register_in_host_adocument` — sort the
  ContentTable after append, exactly famload's line:
  `recs.sort(key=lambda r: uuid.UUID(str((r.get("m_ContentKey") or {}).get("m_guidKey"))).bytes_le)`
  (and mirror famload's FamilyMgr sort-by-surrogate for N-load parity).
  Fixes #4 by construction; harmless for n=1.
* `tools/ifc_intent.py::stage_equipment` (+ `tools/render_probes.py`
  instance path) — set `m_createdPhaseId` (object + header deletion) from
  the host's ProjectPhase instead of −1 (§2.3; the demo-only anomaly).
* `src/rvt/validate.py` — AFTER P4 reads out: add a consistency check
  "ContentTable m_ContentRecSet is GUID-`bytes_le`-ascending and set-equal
  to ContentDocuments order" (error if P4 proves it, else warning).  The
  charter's "the audit checks something our validator does not" is real:
  today `rvt.validate` says VALID 0 errors on every failing file measured
  here (re-confirmed on prompt_room / F_lp4 / stage_W via each build's own
  gate logs); the CT-order law is the one *corpus-universal* invariant the
  failing multis violate that the validator never looks at.
* `src/rvt/famgen/loader.py` (flavour convergence, lower priority): adopt
  famload's lawful empty `FamDimConstrMgrImpl` / `Matrix` forms (#5's
  repair, `residue_c.fix_family_layer_records` exists) and famload's
  surrogate-before-symbol id order — both corpus-parity cleanups now
  exonerated as sole causes but free anomaly-surface reduction.

## 7. Reproduce

```
.venv/bin/python tools/instbug_forensics.py all                # surveys + deltas (17 files)
.venv/bin/python tools/instbug_forensics.py survey FILE        # one file, full registration surface
.venv/bin/python tools/instbug_forensics.py delta BASE DERIVED # one load/commit delta
.venv/bin/python tools/instbug_forensics.py unitdiff A B       # raw per-unit byte identity
```
Key one-liners behind §1–§3 claims (all rerun-able): the three-way load
delta (`deltas.json`: PASS_load_on_sample / FAIL_lineage_load_on_genesis /
PASS_load_on_walls_base), `unitdiff stage_L1 stage_L2` (spliced unit
raw-identical), the V20 recompression proof (`PASS_commit_on_sample`),
CT orders in `surveys.json → latest.content_table*`, connector-cell counts
(§2 script), instance/header diffs vs V20 (regdiff `_header_summary`).

## BRANCH STATE

* **status: DONE** — the ranked defect list (§3) with byte evidence per
  candidate, the exoneration ledger (§2.1/§3.6), the render-instances
  reconciliation (§2.2), the premise corrections (§4), the minimal
  separating probe set (§5) and the cross-territory fix diffs (§6).
  Stopped at READY; no probe built (charter DONE = the list; the §5
  recipes are single-variable and batch-law-ready for the fix stream).
* **files written**: `tools/instbug_forensics.py`,
  `experiments/instbug/forensics/surveys.json` + `deltas.json`, this
  record.  Nothing else touched; no `.rvt` emitted; zero donors; no
  Autodesk install dirs; read-only over every input.
* **tests**: none added (territory has no test surface; the tool was
  smoke-run end-to-end this session).  Full suite NOT run per
  `docs/inbox/SUITE-COORDINATION.md` (canonical run 27375 owns the box);
  no pytest process launched by this stream.
* **the load-bearing sentence for the fix stream**: fix #4 (one sort line)
  and #5 (existing repair) immediately because they are free; then run
  P1/P2/P3 in one batch — P1 names the F_-class killer, P2 decides whether
  the product path's "load then build" order is itself the bug, P3 decides
  whether ANY instance of our families can pass anywhere; the demo needs
  #2's answer plus #4's fix plus (if P2 fails) a pipeline reorder
  (place-before-splice, i.e. famgen `place=True`-style one-commit loads —
  note the loader already supports it and it has never been uploaded).
* **open questions**: whether the audit walks CT/CD positionally (P4);
  whether the two nulls are instance-conditional (#5 × P3); the
  R_inst_downlight third-signature family-content crash (other stream).

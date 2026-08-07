# instbug-fix — THE PRODUCT-PATH BUG: DEFECTS NAMED, FIXED, DEMO RE-EMITTED

Stream: **instbug-fix** (2026-08-05).  Charter: the product-path bug (the
USER'S OWN from-scratch demo `DEMO_250v_room` failed the Autodesk audit,
`Revit-DocumentCorruption` / extractor exit `-1073742517`): name the
mechanical defect(s) in what the product path writes onto the genesis
lineage, fix them in a wrapper layer, re-emit the demo EXACTLY through the
fixed path + the minimal proof pair, ADD the missing consistency rule to
`rvt.validate`, and run the validator regression on the certified corpus.

**Territory touched ONLY:** `src/rvt/famload_fix.py` (new),
`tests/test_famload_fix.py` (new, 13 pass), `experiments/instbug/fix/**`
(A/B experiment + fix probes + reports + probes.json), the new
loaded-content rule in `src/rvt/validate.py` (chartered edit), this record.
Sanctioned regeneration: `tools/sync_plugin.py` (standing rule; validation
PASS, `test_plugin_sync` 7 pass).  `rvt.famgen.loader`, `tools/ifc_intent.py`
and `rvt.frontdoor.standalone` are NEVER edited — the fix layer
monkey-patches them inside a context manager and §DIFFS carries the exact
source patches for their owners.  No browser; the staged batch waits on the
orchestrator's viewer gate.

## Result in one screen

* **FOUR corpus-law violations + one certified-shape gap named on the demo
  path, all measured this session** (§2): D1 every placed instance of our
  loaded families carries a connector manager of class `ConnectorManager` —
  corpus 13,636/13,636 says `{null, FamilyInstanceConnectorManager}`; D2 the
  ContentTable record set is UNSORTED from the second chained famgen load —
  the six samples and `rvt.famload` (L1a-certified) sort by ContentKey GUID;
  D3 the two null owned slots (`Family.m_oFamDimConstrMgr` 0/831,
  `FamilySymbol.m_pMoveRestrictions` 0/2710); D4 our
  `ConnectorDataCell.m_oRelevantParams` table is EMPTY — corpus 228/228
  cells carry 11..21 rows, electrical-equipment cells ONE canonical 15-row
  order (22/22); D5 the demo instances carry no ProjectPhase because
  `ConstructedSpecimens` looks up `ids_of_class("Phase")` — the class is
  `ProjectPhase` — so the phase never resolves (V20's certified shape
  carries it in the object AND the header deletion list).
* **The fix layer** `rvt.famload_fix` (§3): lawful builders
  (`electrical_connector_cell`, `lawful_instance_connector_manager`,
  `sort_content_recset`, the residue_c empty forms re-exported) + a
  `fixed_product_path()` context manager that patches the LIVE product path
  (famgen.loader authoring + registration, every loaded `ifc_intent` module,
  `ConstructedSpecimens`), + `assert_fixed()` — the machine proof read back
  from the emitted bytes.
* **RE-EMITTED through the fixed path** (§4): `DEMO_250v_room_v2.rvt` (the
  user's exact prompt, end to end through `rvt.frontdoor.run`) +
  `BXfix_f1i1.rvt` / `BXfix_f6i6.rvt` (the minimal proof pair on the
  forensics stream's own rung recipe).  All three: **validator 0 errors
  (INCLUDING the new rule), all fix assertions hold, four-registry
  coherent** — and the fixed demo's ContentTable order now equals the
  ContentDocuments order exactly as in the rst sample (measured both).
  **Batch 33 staged** with a byte-identical G_ABPD control.
* **THE VALIDATOR GAP IS CLOSED** (§5): a new `loaded-content` rule set in
  `rvt.validate` — E1 four-registry coherence as an ERROR (the audit law
  PROVEN by R9b-FAIL vs KD1-PASS, the one SOUND fail of the
  verdict-integrity audit; the census checked it, the validator did not),
  E2 ContentTable GUID order (ERROR), E3 instance connector-manager class
  (ERROR), W1/W2 the null owned slots, W3 the below-floor connector cell
  (warnings — WF_nofix viewer-PASSED carrying W1/W2, so they cannot be
  errors).  **The OLD demo now fails validation with 2 errors** (it was
  VALID 0 before — the charter's gap); certified files stay 0-error
  (regression §6).
* **Honesty limit** (§7): `R_inst_box` (ZA_deep + the bare BOX family + one
  instance) audit-FAILED while carrying NONE of D1..D5 on its instance —
  every axis the V20-certified instance calibrates is lawful there.  If the
  BXfix pair still fails the viewer, the prime residual is the famgen baked
  symbol-geometry `[H]` grammar under the audit's deep walk (only ever
  viewer-accepted UNREFERENCED, in WF_nofix); the pre-branched next rung is
  the `symbol_solid=False` variant.

## §1  Evidence base (what separates PASS from FAIL, re-measured)

The viewer matrix (docs/coverage/viewer-certified.json + genesis-audit
verdicts #22–#27) is three-way confounded (family content x operation order
x element kind).  This stream's clean instruments:

1. **The A/B ORDER experiment** (`experiments/instbug/fix/ab_experiment.py`,
   files `AB_A_wallsfirst.rvt` / `AB_B_loadfirst.rvt`): the same final
   content (genesis lineage + 4 walls + the bare box family), built in the
   two orders (walls→load = WF_nofix's PASS shape; load→walls = F_lp4's
   FAIL shape).  Byte-level result: **the two files are ISOMORPHIC modulo id
   renumbering** — unit-0 record order and ElemTable rows are id-ascending
   in both, registries identical after role normalization, wall records
   byte-identical modulo ids.  The 11 apparent `Latest` leaf diffs are
   normalization artifacts over the base's own stale 1472521–24 references
   (present identically in both).  ⇒ operation ORDER per se produces no
   unlawful structure; the discriminator must be content-level (or absolute
   id cross-references, excluded by the base's watermark 1472524 covering
   the stale ids).  The pair is kept on disk as an order-isolate the
   orchestrator may stage if budget allows.
2. **`commit_new_elements` is byte-clean over our spliced units**: the demo
   instance commit (stage_L6 → prompt_room) leaves units 1..6 and every
   untouched unit-0 block byte-identical (member md5s equal) — only the
   three unit-0 tail blocks gain the 6 instance records.  The
   commit-after-splice suspicion is retired at the byte level.
3. **The registration deltas** (with the instbug-forensics stream's
   `deltas.json`, gratefully consumed): `contenttable_sorted` flips FALSE at
   the SECOND chained famgen load and stays false through the demo; the rst
   sample, L_v2, and every viewer-PASSED file are sorted.  FamilyMgr entry
   order is NOT a law (the rst sample itself is `familymgr_sorted=false`).
   `Contents` (DocumentStorageIndex) counters and `Global/PartitionTable`
   are byte-identical across base/pass/fail — both charter suspects retired.
   L_v2 carries NO placed instance — **no placed instance of OUR OWN family
   had ever viewer-passed anywhere** (render-instances' finding, confirmed);
   the certified created-instance shape is V20 (a SAMPLE family's symbol).
4. **The objlint + corpus mine** (six samples): the findings in §2, each
   with support counts; V20's certified instance CALIBRATES away the
   `m_appearanceParents.#len` and `m_regenOnly.#len` findings (it carries
   both and passed) and the header-flags delta (2344 occurs 31x in rme).

## §2  The defects (each: law, violation, where in the code)

| # | law (support) | our violation | writer site |
|---|---|---|---|
| **D1** | `FamilyInstance.m_pConnectorManager` ∈ {null, `FamilyInstanceConnectorManager`} (13,636/13,636, 6 samples; schema: the subclass adds no fields) | class `ConnectorManager` on EVERY placed instance of ours (demo x6, electrical_room x8; R_inst_box carried null) | `rvt/famgen/loader.py:1165` (`author_family_instance`), `tools/ifc_intent.py::_connector_manager_for` |
| **D2** | ContentTable records ascending by ContentKey GUID bytes_le, = the ContentDocuments order (6/6 samples; famload sorts — L1a/L_v2 certified) | unsorted from the 2nd chained load (stage_L2.., stage_W, both demos) | `rvt/famgen/loader.py::register_in_host_adocument` (append, no sort) |
| **D3** | `Family.m_oFamDimConstrMgr` present 831/831; `FamilySymbol.m_pMoveRestrictions` present 2710/2710 (empty forms; WF_fix viewer-PASSED the fixed records) | both null on every famgen-loaded family/symbol | `author_host_family` (~736), `author_family_symbol` |
| **D4** | `ConnectorDataCell.m_oRelevantParams` = 11..21 rows (228/228 rme cells); electrical equipment: ONE canonical 15-row id order (22/22) with the connector's literal values | 0 rows (bindings only) on our panel host families | `rvt/famgen/loader.py::_connector_data_cells` |
| **D5** | the certified created-instance shape (V20) carries `m_createdPhaseId` = a live ProjectPhase + that phase in the header deletion list (corpus ENUM allows null; V20 is the certified recipe) | demo instances: phase −1, no deletion entry — `ConstructedSpecimens` queries `ids_of_class("Phase")`; the class is `ProjectPhase`, so the lookup always misses | `rvt/frontdoor/standalone.py::ConstructedSpecimens.__init__` |

The canonical 15-row cell (measured, rme): param ids `-1140002 (voltage),
-1150159, -1140018 (31=3-pole/30=1-pole), -1133412 (1), -1140009 (1),
-1140008 (power factor), -1140001 (poles), -1140131, -1140014 (load-class
ELEMENT id), -1140000, -1140003, -1140007, -1140006, -1140005 (apparent
load), -1140004` — row shape `{m_str, m_oExpression, m_value, m_elemId,
m_paramId, m_int, m_instance, m_reporting}`.

## §3  The fix layer — `src/rvt/famload_fix.py`

* `electrical_connector_cell(con, bindings, load_class_host)` — the corpus
  15-row cell from our connector facts (voltage / poles / pf / load / LC),
  corpus constants elsewhere.
* `lawful_instance_connector_manager(slots)` — the D1 class identity.
* `sort_content_recset(latest_value)` / `recset_sorted` — the D2 order
  (famload's exact bytes_le key).
* `famdim_constr_empty` / `move_restrictions_empty` — re-exported from
  `rvt.genesis.residue_c` (the WF_fix-certified forms).
* `fixed_product_path()` — a context manager that patches, for the duration
  of a build: famgen.loader `register_in_host_adocument` (sort after
  append), `author_host_family` / `author_family_symbol` (the D3 forms +
  `assign_pids` re-run), `author_family_instance` (D1),
  `_connector_data_cells` (D4); every loaded `tools/ifc_intent` module's
  `_connector_manager_for` (D1); `rvt.frontdoor.standalone.
  ConstructedSpecimens` (D5: resolve `ProjectPhase`, take the highest id =
  the 'New Work' convention the sample instances use, rebuild the instance
  template with it).  All patches revert on exit; the loader's own
  roundtrip gate re-proves every patched record byte-exact
  (encode→decode) during the build.
* `assert_fixed(path)` — reads an emitted file and proves the D1..D5 states
  + the four-registry census from the bytes.

## §4  The re-emit (experiments/instbug/fix/, all built this session)

| file | recipe | validator | fix assertions | census |
|---|---|---|---|---|
| `BXfix_f1i1.rvt` | G_ABPD + PP-1 loaded + 1 instance — the forensics stream's own rung code (`tools/bisect_instance_bug.py` chain+place) under `fixed_product_path()` | **VALID 0 err** (1 warn = the base's standing ES-blob gap) | **ALL HOLD** | 2/1/1 coherent |
| `BXfix_f6i6.rvt` | G_ABPD + 6 panels + 6 instances (same) | **VALID 0 err** | **ALL HOLD** | 7/6/6 coherent |
| `DEMO_250v_room_v2.rvt` | the user's exact prompt "an electrical room rated for 250V with 6 panels", END TO END through `rvt.frontdoor.run` under the fix (out dir `demo_v2/` with the full manifest) | **VALID 0 err** | **ALL HOLD** | 7/6/6 coherent |

Registry accounting of the fix (old demo → v2): ContentTable order
`ae104549, 48b94937, 0f0089db, c06f867a, 2c099cde, eeab853e` (load order,
UNSORTED) → `c8880931, 018c7972, 0589a076, 1de5d8d8, 460644eb, 556097fa`
(ascending bytes_le, == the ContentDocuments order — the rst-sample law,
verified equal on both); instance manager `ConnectorManager` x6 →
`FamilyInstanceConnectorManager` x6; `m_createdPhaseId` −1 → 86961 ('New
Work') + in every instance's deletion list; family `m_oFamDimConstrMgr`
null → `FamDimConstrMgrImpl` empty form; connector cell 0 rows → the
canonical 15.  Full machine reports: `fix_probes.json`,
`probes.json` (staged), builds reproducible via
`.venv/bin/python experiments/instbug/fix/build_fix_probes.py` (~51 s;
fresh GUIDs per rebuild — re-hash after any rerun).

**STAGED: batch 33** (`experiments/acceptance/batch_33.json`) — control
`CTRL_G_ABPD_b33.rvt` (byte-identical G_ABPD) + the three probes, read
order CTRL → BXfix_f1i1 → BXfix_f6i6 → DEMO_250v_room_v2; the full
reading matrix is in `experiments/instbug/fix/probes.json`.

## §5  The validator rule (`rvt.validate`, semantic layer, `loaded-content`)

The charter's gap: `rvt.validate` said VALID 0 errors on every audit-failed
file.  New checks (method `_check_loaded_content`, called at the end of the
semantic layer):

* **E1 (ERROR) FOUR-REGISTRY COHERENCE** — save-unit GUIDs =
  ContentDocuments entries = ContentTable records = FamilyMgr GUID list
  (counts AND sets).  This is the audit law the campaign PROVED (R9b's
  2-of-4 splice FAILED, KD1's 4-of-4 reconciliation PASSED — the single
  SOUND fail in the verdict-integrity audit); the four-registry census
  checked it, the validator did not.  Skipped when the file carries no
  content documents and no extra units (nothing to check).
* **E2 (ERROR)** ContentTable ascending by ContentKey GUID (checked when
  ≥ 2 content documents; needs the ADocument decode, done lazily).
* **E3 (ERROR)** every unit-0 `FamilyInstance`'s connector manager is null
  or `FamilyInstanceConnectorManager`.
* **W1/W2 (WARNING)** the D3 nulls (cannot be errors: WF_nofix
  viewer-PASSED carrying them). **W3 (WARNING)** a `ConnectorDataCell`
  below the 11-row corpus floor.

Detection proof (all measured): `prompt_room.rvt` (the failed demo) **2
errors** (E3 x6 + E2); `electrical_room_2500a` **2 errors** (E3 x8 + E2);
`stage_W_loaded_walls` **1 error** (E2); the old demo ladder bisects
exactly at the law break (stage_L1 0 errors, stage_L2/L3/L6 1 error each);
`F_lp4` / `F_msb` / `R_inst_box` stay 0-error but carry the W1/W2 (+W3 on
the panels: F_lp4's cell has 1 row) warnings — consistent with §7's honest
residual (their failure axis has no measured corpus violation).
`DEMO_250v_room_v2` and every certified file report 0 errors.

## §6  Validator regression on the certified corpus

`experiments/instbug/fix/validator_regression.py` — every on-disk
`viewer-certified.json` 'certified' entry + the six samples through the
full validator (**81 files checked**, 1 not on disk [V15], 597 s;
`validator_regression.json`):

* **ZERO false positives from the new rule on any viewer-PASSED file.**
  The one loaded-content flag in the certified list is
  `stage_L8_lp4.rvt` (E2, unsorted after its 8 chained loads) — the
  DOCUMENTED NON-TEST: its recorded 'PASS' was the 'Design is empty'
  extractor short-circuit that never audited the loaded-family layer
  (render-instances §1; verdict #25 retraction; the discipline stream's
  control-source warning).  The flag states a true fact about an unaudited
  file; classified `known_nontest` in the JSON, never silently excluded.
  Proposed to the orchestrator: annotate that ledger entry.
* **Pre-existing (NOT from this rule): V30/V31/V32** each carry one OLD
  consistency-layer error (`BasicFileInfo Unique Document GUID != History
  entry[0] GUID` — the deliberate identity-rewrite probes; their
  `loaded_content_errors` are empty).  The viewer certified them despite
  the mismatch — a pre-existing validator-vs-reader divergence for the
  identity stream's owner, recorded here, untouched.
* Every other certified file, all six samples included (the deepest
  E1/E2 exercise: 52-unit registries): **0 errors**.
* Detection on the failed product-path set: 3/6 flagged as ERRORS
  (prompt_room 2, electrical_room_2500a 2, stage_W 1); the other three
  (R_inst_box, F_lp4, F_msb) 0 errors + the W1/W2/W3 warnings — the §7
  residual, stated, not papered over.

Stream-local tests: `tests/test_famload_fix.py` **13 pass** (cell grammar,
manager class, sort law, patch/revert, emitted-file assertions, the rule's
detect-old / clean-certified / clean-fixed triple).  Validator-adjacent
suites re-run (validate has no dedicated test file; these four import and
exercise it): `test_famload.py` + `test_reduce_v2.py` + `test_latest_probes.py`
+ `test_genesis_settings.py` = **94 passed** in 157 s.  `test_plugin_sync`
7 pass after the sanctioned `tools/sync_plugin.py` run.

## §7  What the fix does NOT claim (the honest residual)

* `R_inst_box` failed the audit carrying NONE of D1..D5 on its instance
  (manager null, N=1 so D2 moot, box family so D4 moot, phase 86961
  present, header flags 2344 corpus-lawful, V20 calibrates the rest).  Its
  un-eliminated delta vs every passing file: the audit WALKS INTO our
  loaded family through the instance reference, and the famgen loader's
  baked symbol geometry (`m_geomSteps` + `m_pGeomTable` + the seq-103
  GElement, the `[H]` one-specimen grammar) has only ever been
  viewer-accepted UNREFERENCED (WF_nofix).  If BXfix_f1i1 FAILS, build the
  `symbol_solid=False` rung (famload's SerializedDummy symbol form —
  certified referenced on the rst base by L1a's lineage) — one
  `build_fix_probes.py` variant away.
* The WF matrix's other pre-staged dimensions (famgen 2-row vs famload
  1-row `FamilyTypeTable`, surrogate record order, `m_familyIds` width)
  remain unexercised; they are famgen-vs-famload deltas BOTH present in
  passing and failing famgen files, so the current evidence cannot rank
  them above [H].
* The 2-entry `m_defElementTypeMap` / `AppInfoSystemFamiliesNames` stale
  references at ids 1472521–24 in the whole genesis lineage sit BELOW the
  ElemTable watermark (1472524), so new allocations never collide today —
  but any future watermark rewind would revive them as wrong-kind
  elements; noted for the genesis owners.

## DIFFS for other owners (exact patches; NOT applied — the fix layer
carries them at runtime until the owners land them)

1. `src/rvt/famgen/loader.py::register_in_host_adocument` — after
   `recs.append(ours)`:

       recs.append(ours)
   +   # corpus order: ContentTable records ascend by ContentKey GUID,
   +   # like the ContentDocuments stream [V 6/6 samples; famload's rule]
   +   recs.sort(key=lambda r: uuid.UUID(
   +       str((r.get("m_ContentKey") or {}).get("m_guidKey"))).bytes_le)
       rep["content_table_records"] = len(recs)

2. `src/rvt/famgen/loader.py::author_family_instance` (~line 1165):

   -   obj["m_pConnectorManager"] = _ptr("ConnectorManager", {
   +   obj["m_pConnectorManager"] = _ptr("FamilyInstanceConnectorManager", {
           "m_setDeletedConnectors": [],
           "m_connPtrArray": slots,
           "m_modifiers": [],
       })

3. `tools/ifc_intent.py::_connector_manager_for`:

   -   return {"ptr_class": "ConnectorManager", "pid": -1,
   +   return {"ptr_class": "FamilyInstanceConnectorManager", "pid": -1,
               "value": {"m_setDeletedConnectors": [], "m_connPtrArray": slots,
                         "m_modifiers": []}}

4. `src/rvt/famgen/loader.py::_connector_data_cells` — replace the
   body's row-building with the corpus cell (or delegate):

       from ..famload_fix import electrical_connector_cell
       def _connector_data_cells(product, plan):
           facts = _connector_facts(product)
           cells = []
           for con in facts["connectors"]:
               bindings = [{"first": int(prop),
                            "second": int(plan.twin_of.get(fam, fam))}
                           for prop, fam in con.get("bindings") or []]
               cells.append(electrical_connector_cell(
                   con, bindings=bindings,
                   load_class_host=plan.load_class_host))
           return cells

5. `src/rvt/famgen/loader.py` — the genesis-12 §4 two-null patch stands as
   written there (`author_host_family` m_oFamDimConstrMgr; the
   `author_family_symbol` m_pMoveRestrictions line — famload.py:805 carries
   the exact Matrix form).

6. `src/rvt/frontdoor/standalone.py::ConstructedSpecimens.__init__`:

   -   phases = base_doc.ids_of_class("Phase")
   -   phase_id = int(phases[0]) if phases else -1
   +   phases = sorted(base_doc.ids_of_class("ProjectPhase"))
   +   phase_id = int(phases[-1]) if phases else -1   # 'New Work' convention

## KNOWLEDGE.md lines proposed (orchestrator merges)

* *A placed FamilyInstance's connector manager is a
  `FamilyInstanceConnectorManager` (13,636/13,636 corpus; the base
  `ConnectorManager` class appears in no Autodesk instance) — the schema
  subclass adds no fields, the class identity alone is load-bearing.*
* *ContentTable records ascend by ContentKey GUID bytes_le, in the SAME
  order as the ContentDocuments stream (6/6 samples; famload sorts, and
  any chained loader must re-sort after each append).*
* *The four-registry coherence law is now a VALIDATOR ERROR (E1), not just
  a census fact; the validator also gates ContentTable order (E2) and the
  instance manager class (E3).*
* *`Contents` = the DocumentStorageIndex (counters + creation GUID); it and
  `Global/PartitionTable` are inert under loads/commits — identical bytes
  across the whole pass/fail matrix (charter suspects, retired).*
* *`ids_of_class("Phase")` finds nothing — the project-phase class is
  `ProjectPhase` (the ConstructedSpecimens phase bug).*

## BRANCH STATE

* **status: DONE — READY FOR THE VIEWER QUEUE.**  Batch 33 staged
  (`experiments/acceptance/batch_33.json`: CTRL_G_ABPD_b33 + BXfix_f1i1 +
  BXfix_f6i6 + DEMO_250v_room_v2); nothing uploaded (orchestrator's gate).
  Stopped at READY.
* **NEW files:** `src/rvt/famload_fix.py`; `tests/test_famload_fix.py` (13
  pass); `experiments/instbug/fix/`: `ab_experiment.py`, `ab_diff.py`,
  `AB_A_wallsfirst.rvt`, `AB_B_loadfirst.rvt`, `AB_B_step1_loaded.rvt`,
  `ab_build.json`, `build_fix_probes.py`, `BXfix_f1i1.rvt`,
  `BXfix_f6i6.rvt`, `DEMO_250v_room_v2.rvt`, `demo_v2/` (the full frontdoor
  out dir + manifest), `fix_probes.json`, `probes.json`,
  `validator_regression.py`, `validator_regression.json`; this record.
* **EDITED (chartered):** `src/rvt/validate.py` — the `_check_loaded_content`
  rule set (E1/E2/E3 errors + W1/W2/W3 warnings), called from the semantic
  layer.  Sanctioned regeneration: `tools/sync_plugin.py` (plugin bundle +
  tekton-plugin.zip rebuilt, validation PASS).
* **Gates:** every emitted probe validator VALID 0 errors under the NEW
  rule; `assert_fixed` ALL HOLD on all three; four-registry coherent;
  `probe_batch check` ADMISSIBLE (base G_ABPD `[certified]`); batch 33
  staged with the byte-identical control.  Validator regression: 81
  certified files + six samples, ZERO false positives from the new rule
  (one documented non-test flag = stage_L8_lp4; V30-32's single errors are
  pre-existing consistency-layer findings with empty loaded-content lists).
* **DONE check:** defect(s) named (D1..D5, §2) ✔; fixed
  (`rvt.famload_fix`, §3) ✔; demo re-emitted exactly (§4) ✔ + proof pair ✔;
  validator rule added (§5) ✔ + regression clean (§6) ✔;
  staged proof batch (batch 33) ✔.
* **NOT viewer-tested:** every "VALID"/"HOLD" above is the machine gate; no
  acceptance claim is made.  The honest residual (§7) is pre-branched for
  the verdict reader.
* **Cross-territory diffs:** §DIFFS (famgen/loader.py x4, ifc_intent.py,
  frontdoor/standalone.py) — to their owners on a BXfix PASS.
* **full suite:** NOT run by this stream — the SUITE-COORDINATION hard rule
  binds (single canonical run, orchestrator-owned; count publishes there;
  every stream adopts it).  Stream-local: `test_famload_fix.py` 13 pass;
  the four validator-exercising suites (`test_famload` / `test_reduce_v2` /
  `test_latest_probes` / `test_genesis_settings`) 94 pass — run because
  this stream EDITED `validate.py` (the chartered "run its full test file";
  the validator has no dedicated file, these four exercise it);
  `test_plugin_sync` 7 pass.

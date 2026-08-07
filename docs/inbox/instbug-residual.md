# instbug-residual — THE INSTANCE RESIDUAL, CORNERED (batch 34 staged)

Stream: **instbug-residual** (2026-08-05).  Charter: kill or confirm the
hypothesis that Autodesk's open-time audit rejects **famgen's baked
FamilySymbol geometry when an instance references it** — the residual left
after the D1..D5 fixes landed and BXfix_f1i1 / BXfix_f6i6 /
DEMO_250v_room_v2 STILL failed while SX_f6i6 (same famgen operation, rst
SAMPLE base) failed and the famload-path L_v2 load on the same sample
passed.  Three instruments: the no-solid variant rungs, the matched-pair
forensics, the famload cross-check rungs.

**Territory touched ONLY:** `tools/residual_probe.py` (new),
`tests/test_residual.py` (new, 12 pass), `experiments/instbug/residual/**`
(4 rungs + _build chains + 5 JSON evidence files), this record, and the
staged copies `probe_batch` itself writes under `experiments/acceptance/`
(batch_34.json + the 4 probes + the control).  **No src module was edited**
— the charter's pre-authorized `src/rvt/famgen/nosolid_variant.py` wrapper
was NOT needed and does not exist: `loader.author_family_symbol` already
has the `solid=False` (F4b) mode and `load_family_into_project` exposes
`symbol_solid` independently of the product's own solid; this stream merely
composes them (`tests/test_residual.py::test_no_loader_edit_was_needed`
pins that).  No browser (STAGE only), no Autodesk install dirs, zero
donors, no full-suite run (stream-local `tests/test_residual.py` only).

## Result in one screen

* **BATCH 34 STAGED** (control = byte-identical certified G_ABPD copy,
  `CTRL_G_ABPD_b34.rvt`; md5-verified).  Reading order — maximum
  information first:
  1. **BXns_f1i1** — G_ABPD + ONE famgen family + ONE placed instance,
     the demo's own path, with **ONE change vs the FAILED BXfix_f1i1**:
     `symbol_solid=False` (host symbol = SerializedDummy, no geometry
     history; the embedded family document KEEPS its authored solid).
     One verdict kills or confirms the geometry hypothesis.
  2. **SL_f6i6** — the SAME six generated family documents loaded into the
     rst sample by the **certified rvt.famload path** (L_v2's recipe) + six
     instances by the demo's own `stage_equipment`.  PASS here + SX_f6i6's
     recorded FAIL = **path attribution proven at N=6**.
  3. **BXns_f6i6** — the demo shape (6+6), no-solid: the product-decision
     rung.
  4. **SL_f1i1** — the famload N=1 point.
  Every rung: **validator 0 errors (0 unexpected), four registries
  coherent, survivor law OK (pure adds), identity PASS**; per-hop registry
  accounting in `experiments/instbug/residual/accounting.json` (load hop:
  +nf on all four registries; instance hop: +ni ElemTable rows, registries
  untouched).  Instances carry the D-fix shapes (FamilyInstanceConnector-
  Manager, phase 86961 — machine-read back from the emitted bytes).
* **The one-change law is byte-proven** (pair P3, matched_pair_delta.json):
  BXns_f1i1's symbol vs the FAILED BXfix_f1i1's symbol — **84 fields equal,
  zero only-in-one, exactly THREE differing 102-fields** (`m_geomSteps`,
  `m_pGeomTable`, `m_geomTag2MaterialId`) **plus the seq-103 rep class**
  (GElement -> SerializedDummy).  Same symbol id (1472582) in both — the
  deterministic id allocation makes the pair minimal by construction.
* **The corpus separator is exact** (delta_matrix.json, 12 recorded FAILs
  x 11 recorded PASSes, all surveyed from the bytes):
  - `our_instance_reaches_our_baked_geometry` — **9/12 FAIL, 0/11 PASS**
    (the 3 non-carrying FAILs are the walls x loaded-family axis with ZERO
    instances: F_lp4, F_msb, stage_W_loaded_walls — a different, older
    axis, g12's territory).
  - `our_instance_of_our_family` (geometry aside) — **the SAME 9/12 vs
    0/11**.  The recorded corpus CANNOT split "the baked geometry is the
    poison" from "any instance of our family is the poison" — **no file
    with an instance of our family has ever passed, in any form**.  The
    BXns/SL rungs are exactly the experiment that splits these two
    hypotheses (dummy-symbol instances of our families).
  - The instance MECHANISM is exonerated: H1/H2/V20 place OUR instances of
    SAMPLE symbols (with cloned GElement instance reps!) and pass —
    `sample_symbol_instanced_by_us`: 0/12 FAIL, 3/11 PASS.
  - Un-referenced baked famgen symbols pass real audits (WF pair with
    walls) and empty-design reads (BX_f2, stage_L8_lp4):
    `our_uninstanced_baked_symbol` 4/11 PASS.
* **The suspect list = the famload-vs-famgen symbol delta** (pair P1, same
  rst base, same kind of generated panel family; A = famload PASS side,
  B = famgen FAIL side; 75 fields equal, 0 only-in-one, 12 differing):
  1. seq-103 rep: **SerializedDummy vs GElement** (6 faces / 12 edges /
     1 Geometry node, flat tag space 0..20, root GInfo category 124 — the
     `[H]` one-specimen grammar);
  2. `m_geomSteps`: **None vs BaseFamilySymbolGStep** (8 face-hist,
     12 edge-hist, 1 curve-hist, version 4, flags 761725);
  3. `m_pGeomTable`: **None vs 21-row GeomTable**;
  4. `m_geomTag2MaterialId`: `[] vs [{20,-1}]`;
  5. `m_strongRefs`: `[] vs 2` symbol-space strong refs;
  6. `m_arrConnectorData`: `[] vs 1` (famgen authors connector frames on
     the symbol; famload leaves them off);
  7. `m_outline` extents differ (numeric);
  8. `m_hasParamDefValue`: 1 (famload) vs 0 (famgen);
  9. `m_pMoveRestrictions` null on the OLD famgen side — **already covered
     by the landed D3-class fix** (current loader authors the empty Matrix;
     BXns carries it — validator W1/W2 clean);
  10. header `m_abFlags4Bytes` 2218 vs 2488; header parents deletion 17 vs
      20 + regenOnly 0 vs 1 (famgen adds the category GStyle);
  11. host Family: `m_pFamilyTypes` **1 row (famload) vs 2 rows (famgen)**,
      `core_ids` [] vs [124, 113944], `m_oFamDimConstrMgr` present vs null
      (old side; D3-covered now) — the WF-matrix dimensions, still both
      present in passing AND failing famgen files, so still un-ranked above
      the geometry;
  12. identity/content fields (ids, names, GUIDs, param rows) — benign.
  Annotation: items 9 and the instance-side D1/D5 deltas are **already
  landed and proven NON-decisive** (BXfix failed carrying them); pair P4
  shows the SL vs SX instances differ ONLY in D1/D5 + which symbol they
  point at — so an SL_f6i6 PASS attributes the residual to the symbol-side
  delta list above, items 1–8 + 10–11.
* **The instance-side variant is real** (P2 + the survey): the three FAILs
  that don't carry a baked SYMBOL under the instance carry **our-authored
  GElement on the INSTANCE itself** (R_inst_box, R_inst_downlight,
  electrical_room_2500a — the render stream's instance-bake).  The passing
  H1/H2/V20 instance GElements are CLONES of sample instances.  So the
  common surface of every instance-rung FAIL is: **an audit walk from a
  placed instance reaches OUR-AUTHORED family-space geometry** (on the
  symbol or on the instance).  Our wall B-rep grammar (W1, walls_A) passes
  — the family geometry grammar is the suspect, not authored geometry per
  se.
* **The corpus law for the fix** (corpus_symbols.json, 1,160 FamilySymbols
  across rstbasic/rstadvanced/racbasic/rme): **every symbol referenced by a
  FamilyInstance is GElement + m_geomSteps (201/201)** — zero instanced
  SerializedDummy anywhere; the SerializedDummy form exists only
  UNINSTANCED (98) and **still carries m_geomSteps + m_pGeomTable** (20
  examples recorded).  The dummy+no-steps form famload writes (and BXns
  copies) appears in NO sample — off-corpus, though viewer-tolerated
  unreferenced (L1a, L_v2, L_downlight).

## Reading the batch (the fix spec, pre-branched per verdict)

* **BXns_f1i1 PASS** => the geometry hypothesis CONFIRMED: the audit
  rejects famgen's baked symbol geometry under an instance reference.
  Product fork, both viable immediately:
  (a) **ship `symbol_solid=False` on the product path** — one flag in
  `tools/ifc_intent.stage_load` / `frontdoor` (owners: instbug/frontdoor
  streams); geometry regenerates from the embedded document (BXns_f6i6's
  verdict = that decision at demo scale; note the viewer may then show no
  baked panels until regeneration, the L8 lesson);
  (b) **author the corpus-lawful bake** — replace the `[H]` one-specimen
  grammar using the 201 instanced GElement+steps corpus symbols as the
  grammar-mining set; the P1 delta items 1–4 are exactly what must become
  lawful.
* **BXns_f1i1 FAIL + SL_f6i6 PASS** => the poison is famgen's HOST-side
  authorship beyond the three geometry fields: the fix spec is "make famgen
  register/author what famload does", and the remaining suspect set is P1
  items 5–8 + 10–11 (connector data / strong refs / outline / flags /
  parents / FamilyTypeTable shape) — each a one-field A/B rung away.
* **BXns_f1i1 FAIL + SL_f6i6 FAIL** => the residual is the INSTANCE side
  (ConstructedSpecimens template / stage_equipment shape) — the only
  un-eliminated instance-side deltas are the template-clone scaffolding
  fields (P4 shows everything else is D-covered); L_v2's no-instance PASS
  bounded nothing about placement (P2's recorded note).
* **BXns FAIL at N=6 only** (f1i1 PASS, f6i6 FAIL) => a second,
  scale-dependent defect; diff the two rungs' accounting.
* **Next rung if the dummy form itself is suspected** (both BXns FAIL and
  the corpus argument is invoked): the corpus's OWN no-cache form =
  SerializedDummy rep + m_geomSteps/m_pGeomTable KEPT — one variant in
  `author_family_symbol` (author the history tables without the cached
  GElement); the 20 recorded `examples_dummy_uninstanced` are its spec.

## Honest limits

* `L_v2_panel_loaded`'s PASS is the orchestrator's ~01:20 viewer report;
  it is **not in the ledger's certified array** — recorded as such in
  forensics_surveys.json (`verdict_source`).  Its evidentiary role
  (famload load accepted on rst) is unchanged either way; SL rungs do not
  build on it, they re-run the recipe.
* R_inst_downlight is the one FAIL whose symbol was already dummy — but
  its INSTANCE carries our authored GElement and its build predates every
  D-fix; it fits the refined surface ("walk reaches our authored family
  geometry"), not the narrow symbol-bake claim.  BXns/SL instances carry
  SerializedDummy reps (verified), so the new rungs test the clean cell.
* The walls x loaded-family axis (F_lp4 / F_msb / stage_W_loaded_walls,
  zero instances) is NOT explained by this stream's separator and remains
  g12/render territory; nothing here contradicts their record.
* Fresh GUIDs are minted per rebuild — re-hash after any rerun (recorded
  md5s in accounting.json/batch_34.json are the staged bytes).

## Verification (how to re-run)

* Rungs: `.venv/bin/python tools/residual_probe.py build` (~120 s; writes
  accounting.json + probes.json under experiments/instbug/residual/).
* Evidence: `... residual_probe.py forensics` (~10 s; forensics_surveys /
  delta_matrix / matched_pair_delta), `... residual_probe.py mine` (~6 s;
  corpus_symbols.json).
* Staging: `... residual_probe.py stage` (gate + control; wrote
  experiments/acceptance/batch_34.json).
* Tests: `.venv/bin/python -m pytest tests/test_residual.py -q` -> **12
  passed** (rung shapes read back from bytes, one-change law, matrix
  separators, corpus law, batch control identity).  Full suite: NOT run
  (SUITE-COORDINATION binding rule; stream-local file only).

BRANCH STATE: no git repo (working tree); deliverables =
`tools/residual_probe.py` (new, 1,115 lines; build/forensics/mine/stage),
`tests/test_residual.py` (new, 12 tests PASS),
`experiments/instbug/residual/` {BXns_f1i1.rvt c4ee7223, SL_f6i6.rvt
3459beef, BXns_f6i6.rvt ff708a0f, SL_f1i1.rvt f326f0dc, probes.json,
accounting.json, matched_pair_delta.json (P1 famload-vs-famgen symbol,
P2 instance references, P3 one-change, P4 SL-vs-SX instance),
delta_matrix.json, forensics_surveys.json, corpus_symbols.json, _build/**},
staged batch `experiments/acceptance/batch_34.json` + CTRL_G_ABPD_b34.rvt
(byte-identical certified control) + the four staged probes, this record.
Verdicts — the four rungs are built, gated (validator 0/0 unexpected,
coherent, survivor-law, identity PASS) and STAGED as batch 34 in reading
order BXns_f1i1 -> SL_f6i6 -> BXns_f6i6 -> SL_f1i1; the matched-pair delta
list is ranked with D-coverage annotations (the un-eliminated symbol-side
set = baked rep + geomSteps + geomTable + geomTag2Material + connector
data/strong refs/outline/flags/parents/type-table shape); the corpus law
is measured (201/201 instanced sample symbols are GElement+steps; dummy+
no-steps is off-corpus; dummy corpus symbols keep their history tables);
the fix spec is pre-branched per verdict (no-solid product decision vs
corpus-lawful bake vs famload-parity authoring vs instance-template
residue); NO source module edited, nosolid_variant.py proven unnecessary.
STOP at READY — the orchestrator uploads batch 34.

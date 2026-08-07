# inbox — asset-forge (the asset factory + the LOADER)

Stream: THE ASSET FORGE (2026-08-03, two sessions). Charter: compose the three
foundry streams (family-skeleton / facts-store / family-geometry) into the
first real generated families **and put one in a project.** Full spec:
`docs/writer/asset-factory.md`. Territory touched ONLY:
`src/rvt/famgen/factory.py` (+ this session's `src/rvt/famgen/loader.py`,
a new sibling module of the same stream), `tools/make_family.py`,
`tests/test_famgen_factory.py` (24 pass) + `tests/test_famgen_loader.py`
(new, 13 pass), `experiments/families/factory/*`,
`docs/writer/asset-factory.md`, this file. No existing `src/rvt/*.py`,
`src/rvt/genesis/*`, `src/rvt/famgen/{skeleton,catalog,geometry}.py`, tools
or tests of other streams edited (all IMPORTED only). No browser used; the
outputs sit on disk for the orchestrator's viewer gate.

## Result in one screen

* **THE LOAD PROOF IS BUILT.** `experiments/families/factory/
  project_with_generated_panel.rvt` = the rme sample + OUR generated Eaton
  Pow-R-Line 480Y/277 V 400 A MCB 42-circuit panelboard, loaded (host
  `Family` 888055 'Panelboard 480Y/277 400A MCB 42ckt Surface' + host
  `FamilySymbol` 888071 '400A MCB 42ckt' carrying OUR authored symbol
  solid) and PLACED (one `FamilyInstance` 888073, `symbol == masterSymbol`,
  on the sample's wall SketchPlane) — **`rvt_validate` VALID, 0 errors**
  (all three layers, 427,623 records / 2.57 M references; its single warning
  is the untouched sample's own known decoder gap, byte-identical on the
  baseline). Container CRC + the validator's structure-layer ECC clean,
  partition walker clean (307 units, ours at 306), `Global/ElemTable` +19
  rows, the host `ADocument` decodes clean with all three loaded-family
  registrations, `family_documents` lists our family (unit 306, 41 records,
  1 type, `big2small_count` 14), targeted provenance of everything the load
  added = ZERO suspects. Plus the triage rungs `project_with_generated_
  panel_dummy.rvt` (symbol geometry left to Revit — F4b) and
  `project_with_loaded_panel.rvt` (loaded, not placed); all three
  0-error VALID with `.json` reports beside them.
* **The brief's exact route is proven [V]:** on the LOADED project
  `rvt.mutate.Document.from_file(...).symbols()` lists our symbol and the
  STANDARD `Document.add_family_instance(symbol_id=our symbol)` works on our
  NEW symbol (cloning our placed instance as its template). The loader
  authors the first placement (a brand-new symbol has no instance to clone);
  the certified mutation API places more.
* **The three standalone generated families are re-verified green this
  session** (`.venv/bin/python -m rvt.famgen.factory`):
  `eaton_prl_400A_42sp_480Y.rfa`, `xfmr_75kVA_480-208Y120.rfa`,
  `troffer_2x4_recessed.rfa` — each verify OK · VALID 0 errors (family
  mode) · provenance OK. The prior session's L1–L3 (ContentDocuments
  grammar solved, save-unit splice, embedded ADocument authoring) stand and
  are consumed by the loader.
* **NEW FORMAT KNOWLEDGE (this session) — the family-LOAD contract [V]:**
  what a loaded family IS in a project file — 5 host record types +
  3 ADocument registrations + the streams — decoded from the rme specimen
  (host Family 454674 + its embedded document unit 243, symbol 455409,
  instance 471580) and reproduced field-by-field. Details in "Findings".

## Findings (the load contract; evidence in asset-factory.md §5 + tests)

- **A loaded family = these host records [V]:** (a) one host
  `ParamElemFamily` TWIN per TOP-LEVEL family user parameter (7/7 twinned
  on the specimen; the 3 untwinned params belong to its NESTED annotation
  families) — the family's own parameter object with exactly 4 rewrites
  (id, `m_paramElemId`, `m_famId` → host Family, `m_typeId` →
  `revit.local.family:<32-hex session guid><%08x host id>-1.0.0`), ElemRec
  owner = the host Family; (b) a `FamilySurrogate` `{m_elemId = host Family,
  m_name, m_categoryId, m_previewElemId, m_guid}`; (c) the host `Family`;
  (d) one host `FamilySymbol` per instantiated type + a `FamSymSurrogate`
  each; (e) the placed `FamilyInstance`s. Header deletion lists: Family =
  built-in param ids + coreIds + every big2small host id + self + twins +
  surrogate; Symbol = built-ins + Family + twins + self + its
  FamSymSurrogate, with the CATEGORY (−2001040) and the geometry bbox on the
  header, `regenOnly` = the category GStyle; twin = `[Family, self]`;
  surrogate = `[Family, self(, preview)]`.
- **`Family.m_oFamDoc.m_big2SmallMap2` decoded [V]:** `{first: HOST id,
  second: {m_id64: EMBEDDED id}}` pairs, one per family element that has a
  host-side twin (parameter twins + the category / object-style / font /
  dimension-style / annotation-attribute rows the family doc COPIES from the
  host — 52 pairs on the specimen: 7 param twins + 45 style rows). Our doc
  carries no style copies → our map = the 14 param twins only [H
  completeness]. `m_coreIds` = the host resources the family binds to
  (fill/line patterns, category GStyles, a material, the resolved load
  classification).
- **`Family.m_familyIds` (host flavour) [V]:** = only the host-side twins
  the LOAD CREATED (not the pre-existing category rows), each with the SAME
  absorbed index its embedded counterpart carries in the family doc's own
  `m_familyIds` (455334→1106 ≡ 786844→1106; 454678→297 ≡ 786443→297).
- **The host Family is the embedded self-Family transformed [V]:** the
  full transform is the field-by-field diff of specimen host Family vs its
  own embedded self-Family (519 differing leaves): id remap; `m_name` set
  (the doc's self-Family is nameless); `m_famDocGUID` minted;
  `m_surrogateId`; `m_oFamDoc` = a REGISTERED `FamilyDocument` (pid 3 — the
  record's first registered object per the archive numbering rule);
  narrowed `m_familyIds`; a leading blank ' ' type row (= the current
  values); host-only `m_dbviewInfos` (preview views), `ConnectorDataCell`
  (voltage/poles/load rows + the resolved LC in the `-1140014` row +
  `propId → famParam` bindings on the host twins),
  `FamilyReferenceIdxMgr` (reference INDEX → (Is-Reference code, name);
  the map KEYS are the origin RefPlanes' ABSORBED indices), `m_defaultHeight*`
  = −1e30; family-doc-only state dropped (`m_oFamDimConstrMgr`, `m_fsdos`,
  `m_refs`, `m_deletableElements`).
- **The SYMBOL geometry is the load's real cargo [V grammar, H acceptance]:**
  a placed instance's own rep is just `GInstance → symbolId`; what displays
  is the host `FamilySymbol`'s seq-103 `GElement` = the family solid
  REGENERATED at the type's parameter values, wrapped `[GFilter…, Geometry]`
  under a root `GInfo{m_categoryId = the category GStyle, m_tag = symbol
  id}`; the solid's faces/edges carry SYMBOL-SPACE ids in `GInfo.m_tag`, and
  `m_geomSteps` (a `BaseFamilySymbolGStep`) maps each id back to
  `[kind, tag, formAbsorbedIndex]` (5 face / 3 edge / 65 solid node / 6
  graph node) with `m_pGeomTable` = one `{generator 1}` per id 0..N. For
  our single-type single-form family the symbol solid IS our extrusion's
  authored solid (geometry stream), re-tagged.
- **The three host-ADocument registrations of a loaded family [V, and
  they are the ONLY three — whole-tree search]:** `ContentTable.
  m_ContentRecSet` record (guid, author, history episodes, per-episode
  record counts); `AppInfoManager[FamilyMgr].m_arrLoadedFamilyInfo`
  `{surrogateId, m_familyDocGUIDs [content GUID, +one GUID per NESTED
  embedded document]}` (single-GUID entries are the norm, 47/159; nested
  family documents are FLATTENED into the host's ContentDocuments — the
  panel specimen's second GUID is its nested "Section Tail" annotation);
  `AppInfoManager[ElementTrackingData]` per-category symbol / element id
  sets.
- **Constants nailed [V]:** all 159 host `FamilySurrogate`s share the ONE
  `m_guid = e3e052f8-0156-11d5-9301-0000863f27ad` (a format-level creator
  identifier, not content); `m_previewElemId = -1` on 56/159 (the rest
  point at `LegendComponent`s of the sample's legend VIEW = project content,
  not a load requirement); host GStyle 124 = the Electrical-Equipment
  category's projection style (resolved BY CATEGORY); the family's
  connector load classification resolves BY NAME to a host LC (our
  'Power' → host 638830 'Power').
- **Embedded-document elements are NOT rows of the host `Global/ElemTable`
  [V]:** 28,132 host rows, all partition 0; no `786xxx` embedded id has a
  host row — they live in each embedded document's own INLINE ElemTable
  (the L3 ADocument), so a load adds host rows only for its ~19 HOST
  elements, and the ElemTable watermark just has to clear the max host id.
- **Face-hosted placement of the specimen panels uses a per-host SLAVE
  geometry symbol [V]:** instance `InstanceInfo.m_symbolId` = a NAMELESS
  symbol (470440) whose `m_masterSymbolId` is the named type (455409); the
  nameless symbols (470440/470469/471762/742645) are these slaves. Ours
  uses `symbol == masterSymbol` (the free/simple pattern `rvt.mutate`
  verified on racbasic) — an acceptance question (H5).
- **The write is a two-pass compose of certified machinery [V]:** pass 1 =
  `rvt.commit.commit_new_elements` (host elements into save unit 0 +
  ElemTable + identity); pass 2 = replace `Global/ContentDocuments` (L1),
  splice our save unit into `Partitions/<N>` before the end record (L2/L3),
  replace `Global/Latest` (L5), each re-framed with real CRCIO ECC
  (`ecc.frame_stream` / `wrap_global_stream`) via `read_entries` +
  `write_cfb`. Before any byte is written, every authored record passes an
  encode → decode byte-exact round-trip gate (57/57).
- **CROSS-MODULE finding (not mine): `commit.verify_written` vs
  `ecc.frame_stream` disagree on the LAST page trailer when a stream's
  logical length is an EXACT multiple of the page payload** (469 full
  pages, zero remainder — hit by coincidence on the unplaced variant;
  first two trailer bytes differ). The validator's structure layer (real
  RS/ECC verification of every page) declares the same file VALID 0
  errors, so it is a false positive of `verify_written`'s trailer-recompute
  heuristic (or a boundary quirk of `ecc.page_trailer`), not a file defect.
  The loader's verdict therefore rests on the structure layer; the
  heuristic count is kept as a diagnostic. Worth an owner's look
  (commit.py / ecc.py).
- **PARALLEL-STREAM CONVERGENCE (integration decision for the
  orchestrator):** a concurrent stream is building `src/rvt/famload.py` —
  the same KIND of loader from the genesis side (embedding OUR annotation
  head families, `famgen/heads.py`, into OUR generated project skeleton for
  the K-ladder). It independently arrived at the SAME load grammar (param
  twins with the 4 rewrites, FamilySurrogate + FamSymSurrogate, the host
  Family with `m_big2SmallMap2` / coreIds, twin-keyed FamilySymbol rows,
  the ContentTable / FamilyMgr / ElementTrackingData registrations, the same
  `e3e052f8…` surrogate-GUID constant across BOTH rme AND rst hosts) —
  strong independent VALIDATION of this stream's decoding. It also carries
  an external viewer datum this stream should relay: the earlier reduction
  splices (R9b/R10b) that reconciled ONLY the partition unit +
  ContentDocuments (not ContentTable / FamilyMgr) FAILED the viewer — which
  vindicates the prior asset-forge session's refusal to emit a half-loaded
  file and this session's full reconciliation. The two loaders duplicate
  core logic and should be MERGED after this tick: theirs = multi-family,
  annotation categories, usage repointing, our constructed host, no symbol
  geometry (2D view-symbol families); mine = MEP equipment into a REAL
  Autodesk host, the symbol-geometry cache (a 3D solid the instances
  display), a PLACED FamilyInstance with a rebuilt connector manager,
  by-category GStyle and by-name load-classification resolution. Neither
  file was touched by the other stream.

## What blocked NOTHING this time — but the honest acceptance ledger [H]

The structural / codec / walker / validator / decoder proofs are all
green [V]; what only Revit / the viewer can answer (each has a triage rung
on disk):

* **H1** the embedded ADocument's all-null `AppInfoManager` (L3);
* **H2** the symbol geometry bookkeeping (history tables + GeomTable +
  the flat id space, inferred from ONE specimen) — the `_dummy` variant
  leaves the symbol geometry to Revit's regeneration (F4a/F4b triage);
* **H3** big2small / coreIds completeness for a family doc without
  category/style copies (ours has none; the specimen twins 45 style rows);
* **H4** surrogate `previewElemId -1`, the shared creator GUID, the
  single-GUID FamilyMgr entry;
* **H5** `symbol == masterSymbol` on a face host + the rebuilt one-slot
  connector manager;
* **H6** the ContentTable author string is ours; the load reuses the
  host's current save episode (no new History / increment row).

## Recommendation

1. **VIEWER / REVIT-GATE `project_with_generated_panel.rvt` FIRST** — one
   file that proves the whole product sentence (generate the asset AND load
   AND place it). On a fail, the ladder isolates the layer:
   `project_with_loaded_panel.rvt` (does the loaded family LIST — L4/L5
   host records without the placement variable), `project_with_generated_
   panel_dummy.rvt` (does the instance DISPLAY when Revit regenerates the
   symbol — H2), the standalone `eaton_prl_400A_42sp_480Y.rfa` (does the
   family document itself open — L3 / the skeleton ladder).
2. **Promote into core (owners' diffs, below):** the ContentDocuments codec
   → `rvt/content.py`; the family-mode `validate.py` diff (family-skeleton
   §13, still runtime-only); a look at the `verify_written` / `ecc`
   boundary-page quirk.
3. **Follow-ups now cheap:** multi-type loads (one host FamilySymbol +
   FamSymSurrogate per type row — the transform already keys every row by
   the twins); the symbol's registered reference faces (`m_refFaces`, so
   placed instances offer reference snapping — 14 `Face`+`Plane` objects
   on the specimen, deliberately omitted, GAP #11); loading the transformer
   / luminaire (the loader is category-generic: it resolves the category
   GStyle, the load classification by name, and a specimen instance of the
   category — the rme host has instances of both).

## Requests for the orchestrator

1. **VIEWER / REVIT-TEST, ordered by information value:**
   - `experiments/families/factory/project_with_generated_panel.rvt` —
     open the project: our family listed under Electrical Equipment; the
     placed instance (a 20 × 60 × 5.75 in surface panel) ~4 ft along the
     wall from the sample's own panelboard, with our contract parameters /
     Manufacturer Eaton / Model PRL2X and a 480 V 3-pole feed connector.
     **A pass proves generated families are loadable + placeable end to
     end.**
   - `project_with_generated_panel_dummy.rvt` — same, symbol geometry
     left to Revit (answers H2 by contrast).
   - `project_with_loaded_panel.rvt` — loaded, not placed (isolates L4/L5).
   - the three standalone `.rfa` (unchanged from the prior request):
     `eaton_prl_400A_42sp_480Y.rfa` (flagship), `xfmr_75kVA_480-208Y120.rfa`,
     `troffer_2x4_recessed.rfa`.
2. **`docs/writer/asset-factory.md` §5 for KNOWLEDGE.md:** the family-LOAD
   contract — host record set + big2SmallMap2 / m_familyIds semantics +
   the symbol-geometry grammar + the three ADocument registration sites +
   the constants (surrogate GUID, previewElemId −1, category GStyle,
   LC-by-name, embedded elements not in the host ElemTable, the flattened
   nested-document rule, the slave-symbol placement pattern) — plus the
   prior session's ContentDocuments grammar, connector host-face rule and
   the family-parameter `-1.0.0` spec ids.
3. **`tools/sync_plugin.py`:** the plugin drift test lists my
   `src/rvt/famgen/factory.py` (edited) and the NEW
   `src/rvt/famgen/loader.py`, plus the other streams' files — left for the
   orchestrator's post-integration sync run (running it here would re-zip
   the plugin around other streams' unfinished work).
4. **Core diffs (none REQUIRED by this stream — all composed, nothing
   edited). Promotions / findings worth an owner's diff:** (a)
   `parse/assemble/insert_content_documents` → `rvt/content.py` (retire the
   32/305 wave-1 scanner); (b) the family-mode `validate.py` diff (family-
   skeleton §13); (c) `commit.verify_written` / `ecc.page_trailer` boundary
   page when `len(logical) % PAGE_PAYLOAD == 0` (heuristic false positive
   above — the loader gates on the validator's structure layer instead);
   (d) `rvt.mutate.add_family_instance` could learn the slave-symbol
   (symbol ≠ master) face-hosted pattern the specimen panels use.
5. A standalone Autodesk lighting-fixture `.rfa` (2026) in `samples/`
   would let the luminaire path add an ImposterLight light-source element —
   the family-authoring stream's standing request, now with a consumer.
6. **MERGE the two loaders** (`rvt.famgen.loader` here + the parallel
   stream's `rvt.famload`): one host-side load layer with the union of the
   two feature sets (multi-family / usage-repointing / annotation heads +
   symbol geometry / placed instances / real-host resource resolution),
   sharing ONE param-twin / surrogate / host-Family / registration
   implementation. See the convergence finding above.

## Verification

- `.venv/bin/python -m rvt.famgen.factory` — the three standalone `.rfa` +
  reports (~5 s; verdict table) + the fast loader readiness (P1–P5).
- `.venv/bin/python -m rvt.famgen.loader` — the load ladder: three `.rvt`
  + `.json` reports in `experiments/families/factory/` (~5 min; ~90 s per
  write is the partition re-gzip + a 32 MB CFB write; the authoring itself
  is ~3 s).
- `.venv/bin/python tools/make_family.py load -o out.rvt [--no-place]
  [--dummy-symbol] [--no-validate]` — the front door for the load;
  `panelboard|transformer|luminaire|proofs|provenance|loader` unchanged.
- `.venv/bin/python -m pytest tests/test_famgen_loader.py -q` → **13
  passed** (~110 s: 11 fast tests off one dry-run authoring pass — host
  survey resolutions, id/twin plan, all 19 records round-trip byte-exact,
  the host-Family transform properties, the symbol-geometry id-space
  self-consistency, the surrogates' constants, the instance targeting our
  symbol with a rebuilt one-slot connector manager, the three ADocument
  registrations on the REAL host tree; plus one real validated load
  asserting every read-back proof + `rvt_validate` 0 errors + the
  standard-API placeability of our new symbol).
- `.venv/bin/python -m pytest tests/test_famgen_factory.py -q` → **24
  passed** (unchanged; the loader-readiness test now asserts L4/L5 read
  BUILT).
- Full suite (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`)
  → see BRANCH STATE for the count; the known cross-stream failures
  (`test_plugin_sync.py` drift; the parallel provenance/genesis streams'
  G0 tests) are independent of famgen (my changes are additive: one new
  module + one new test file + the factory/CLI/spec/record updates).

BRANCH STATE: no git repo (working tree); deliverables complete —
src/rvt/famgen/loader.py (NEW: the L4/L5 loader — host survey + resource
resolution, load plan / twins / absorbed indices, host-record authors:
param twins, FamilySurrogate, host Family (self-Family transform),
FamilySymbol (+ symbol geometry: geomSteps history / GeomTable / seq-103
solid) or dummy variant, FamSymSurrogate, FamilyInstance (placement +
rebuilt connector manager), ADocument registrations, two-pass write,
verify_loaded_project, provenance_ours, the ladder driver),
src/rvt/famgen/factory.py (LOADER_SPEC now BUILT, loader_readiness emit
handoff), tools/make_family.py (`load` command),
tests/test_famgen_loader.py (13 pass) + tests/test_famgen_factory.py (24
pass, readiness assertion updated), docs/writer/asset-factory.md (§5 the
built loader, §6.1 acceptance ledger, §7 the load-first viewer queue),
experiments/families/factory/{project_with_generated_panel.rvt,
project_with_generated_panel_dummy.rvt, project_with_loaded_panel.rvt +
.json reports, eaton_prl_400A_42sp_480Y.rfa, xfmr_75kVA_480-208Y120.rfa,
troffer_2x4_recessed.rfa + .json}; READY — the LOAD PROOF exists
(project_with_generated_panel.rvt: our generated family embedded + loaded +
one placed instance, rvt_validate VALID 0 errors, all read-back proofs
green, provenance of everything the load added clean) and awaits the
viewer / Revit acceptance gate with its triage ladder; next code steps
after acceptance = multi-type loads, the symbol's reference faces, and
promoting the ContentDocuments codec into rvt/content.py.

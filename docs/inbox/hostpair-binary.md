# hostpair — THE HOST-PAIR BYTE-COPY BINARY (batch 38 staged) + THE SPECULATIVE FIX (batch 39 staged)

Stream: **hostpair** (2026-08-05, post-verdict-#33).  Charter: H7 proved an
UNMODIFIED Autodesk famdoc (the rst sample's own M_Concrete-Square-Column,
unit 36), id-rebased and loaded through rvt.famload with one
template-placed instance, FAILS the audit on its own sample base — famdoc
content exonerated; the defect lives in what the load path AUTHORS AROUND
the family.  Build the binary that decides WHICH half (the authored host
Family/FamilySymbol elements vs the unit/four-registry registration rows),
compute the fix spec, and build the fix speculatively while verdicts wait.

**Territory touched ONLY:** `tools/hostpair_probe.py` (new),
`src/rvt/famload_hostfix.py` (new), `experiments/hostpair/**` (new),
`tests/test_hostpair.py` (new), this record, and the staging copies
`probe_batch` itself writes under `experiments/acceptance/` (batch
manifests + probes + controls — its designed output).  No existing src
module, tool, or test edited.  No browser (STAGE only — the orchestrator
uploads); no Autodesk install dirs; zero donors in shipped output (every
probe is PROOF-ONLY sample-derived dev content, quarantined in
experiments/, exactly like the H7/SX/SL precedents; the famload_hostfix
module ships NO donor bytes — it authors from mined field laws).

## Result in one screen

* **THE BINARY IS BUILT, GATED, STAGED AS BATCH 38** — CTRL (byte-identical
  untouched rst copy, md5 `b3235ad2743f19bcfff243654fec35dd`) + **H9** +
  **H10**, every probe `rvt.validate` **VALID 0 errors / 0 unexpected**
  (1 warning = the standing inherited decoder gap present in the untouched
  sample), four-registry **coherent** (H10 load hop +1/+1/+1/+1; H9
  instance hop registry-silent), survivor law **0 removed / 0 modified**,
  identity gate **PASS**.
* **H9** = H7's exact load (same `famdoc_bisect.build_donor` rebase, same
  famload unit build + inline ADocument + four-registry registration
  functions) **but the host-side family layer is the donor's own NATIVE
  22-element constellation as ID-REBASED BYTE-COPIES** + ONE instance by
  H7's exact template recipe.  **H10** = H9's immediate parent
  (byte-identical md5 to `_build/H9_load.rvt`): same load, NO instance.
* **The byte-copy claim is machine-proven, not aspirational**: the native
  cluster re-encodes byte-exact (66/66 records), so the emitted copies
  differ from the native bytes by exactly the remap + **five declared
  content moves** (`copy_report.json`, exhaustive leaf ledger: 284
  id-remapped leaves + `m_name` ×2 + fresh `m_famDocGUID` + the content
  GUID + the twin's id-derived local-type suffix — nothing else).
* **The 2×2 matrix this completes** (recorded cells from the ledger):

  |                        | no instance                | one instance |
  |---|---|---|
  | famload-authored pair  | L_v2 / BX_f2 **PASS**      | H7 **FAIL** (b37) |
  | native byte-copies     | **H10** (b38, expect PASS) | **H9** (b38, the verdict) |

* **THE SPECULATIVE FIX IS BUILT AND STAGED AS BATCH 39** —
  `src/rvt/famload_hostfix.py` authors the **corpus-lawful instanced-symbol
  form** (mined from ALL 201 instanced FamilySymbols across four samples)
  on BOTH loaders, **opt-in, default OFF** (famload_fix-style live patch;
  no loader changes behaviour until a caller asks).  CTRL (byte-identical
  certified G_ABPD) + **BXhf_f1i1** (ONE change vs batch-33's failed
  BXfix_f1i1: the symbol geometry form) + **DEMO_250v_room_v3** (the
  user's exact prompt "an electrical room rated for 250V with 6 panels",
  end-to-end through `rvt.frontdoor.run` under the fix).  Both: validator
  **0 errors / 0 unexpected**, four-registry coherent (+1u / +6u),
  survivor OK, and `assert_symbol_form` **OK on every loaded symbol**
  (1 + 6).
* Stream-local tests: `tests/test_hostpair.py` → **17 passed**.  Full
  suite NOT run (SUITE-COORDINATION hard rule; the canonical published
  count 1697/7/2 is adopted).

## §1  H9 — what exactly was built

The native host constellation of the donor family (all measured, pinned by
`survey_cluster()` — the build refuses on a drifted base):

| native id | class | copied to | role |
|---|---|---|---|
| 1410863 | Family | 1472942 | the host family (50-row big2small, 5-pair type table, 16-row m_familyIds) |
| 1411267 | FamilySurrogate | 1472943 | carries `m_previewElemId` → the preview |
| 1411268 | LegendComponent | 1472944 | the type-preview component (GElement rep) |
| 1411269–1411284 | 16 family-scoped resource twins (TextNote/TagNote-Attributes, CategoryElem ×5, GStyleElem ×5, LeaderStyle, FontElem ×3, **ParamElemFamily 'b' = 1411280**) | 1472945–1472960 | header `m_familyId` = the family; ElemTable owner CHAINS (mirrored, remapped) |
| 1411287 | FamilySymbol '450 x 450mm' | 1472961 | **the V20-certified instance target**: GElement rep + GeomStepList + 34-row GeomTable + 14 refFaces + 2 strongRefs |
| 1411288 | FamSymSurrogate | 1472962 | |
| 1411406 | FamilySymbol '' (slave, m_masterId → 1411287) | 1472963 | |

Remap law (measured before building): typed-reference census of the
cluster = 228 cluster-internal / 238 host-shared / 583 builtin-negative /
**0 unresolved / 0 embedded-typed**; the ONLY embedded-unit references are
the 50 `big2SmallMap2[].second.m_id64` values → remapped through the SAME
famdoc rebase map H7 used.  Host-shared ids (coreIds, materials, line
styles, catalog rows 277…, DimensionStyle 1468016, Levels 311/245423)
stay byte-identical — the copies live in the very host that owns them.
Native relative id order preserved (family < surrogate < preview < twins <
symbol < symsurrogate < slave — note the donor's own symbol-before-
surrogate order, the opposite of the annotation flavour famload mirrors).

Registration = famload's own machinery, H7-verbatim:
`F.author_embedded_adocument` (the all-null inline-ADocument flavour H7
carried), `F.build_family_save_unit`, `commit_new_elements`
(identity `{"username": ""}`), `F.splice_save_unit`,
`F.insert_content_document`, `FL.register_in_host_adocument` (ContentTable
GUID-sorted, FamilyMgr entry, ETD: the existing −2001330 row gains our
symbol — the native symbol is tracked there too, measured).  The plan
carries the NATIVE rosters: **one** twin (the native family twins ONE of
the famdoc's two ParamElemFamily; famload twins BOTH — recorded as an
intentional H9↔H7 delta of exactly the surface under test), one type
symbol, the slave uninvolved in registration (native law: slave untracked,
no surrogate).

Instance: `famdoc_bisect.place_probe` verbatim (ConstructedSpecimens +
`add_family_instance` + commit at the fixed position; category = the
family's own −2001330; connmgr = template's None).  Read back from the
emitted bytes: instance 1472964, phase 86961, `m_masterSymbolId` → the
copied symbol, header deletion `[311, 86961, 1472961, 1472964]` — the
exact V20-certified shape (`[311, 86961, 1411287, self]`).

The five content moves (everything that is NOT a pure id remap;
`copy_report.json` is the exhaustive machine ledger and the build REFUSES
on any undeclared delta):
1. Family `m_name` → 'M Concrete-Square-Column H9' (collision avoidance —
   the native original stays loaded in the same host; H7's own precedent
   shape).
2. Family `m_famDocGUID` → fresh uuid4 (document identity must be unique).
3. Family `m_oFamDoc.m_contentDocGUID` → OUR loaded unit's GUID.
4. FamilySurrogate `m_name` → same rename (mirrors the family name).
5. Twin `m_pParamDef.m_typeId` trailing 8 hex → the new twin id (measured
   law: trailing hex == the twin's own id on every sampled corpus twin;
   the 32-hex session prefix kept byte-identical — sessions span families
   in the corpus).

## §2  H10 — and why "register the famdoc a second time" is nonsensical

The charter's first-choice H10 (re-register the EXISTING donor unit
without a new unit) is structurally impossible in this format: all four
registries key by content-document GUID (unit separator GUID ==
ContentDocuments entry == ContentTable `m_guidKey` == FamilyMgr
`m_familyDocGUIDs`), the corpus carries **52/52 unique GUIDs** on rstbasic,
`famload.register_in_host_adocument` hard-refuses a duplicate ("content
GUID already registered"), and the four-registry coherence census compares
GUID SETS and counts — a duplicate row cannot be represented as anything
but incoherence.  A "second registration" would need a second GUID, which
means a second unit — which is H9 minus nothing.  So H10 = the fallback
the charter names: **H9 minus the instance** — the load file itself,
byte-identical to H9's immediate parent, staged as its own probe.  It
completes the 2×2 against L_v2/BX_f2 (famload-authored, uninstanced,
PASS).

## §3  The decision table (probes.json `reading_the_matrix`, staged)

* **CTRL FAIL** → round VOID.
* **H9 PASS** (with the recorded H7 FAIL) → **the defect IS famload's
  authored host elements** — native copies under the SAME registration +
  SAME instance recipe pass where famload's authored pair failed.  Fix
  spec = §4's ranked diff; `famload_hostfix` (batch 39) is the first
  implementation rung of exactly that spec.
* **H9 FAIL + H10 PASS** → the copies are lawful uninstanced but an
  instance still kills the load; with V20 certifying an instance of the
  NATIVE original on this base, the remaining our-authored surface is
  **the registration rows / the re-encoded unit** → next rung **H11**: H9
  with the ContentTable / FamilyMgr / ContentDocuments rows byte-modeled
  field-by-field on an Autodesk multi-unit file's own row shapes (design:
  take rstbasic's own 52 rows as the mold — author, per surface, a row
  whose every non-GUID field is byte-equal to a native row's: ContentTable
  `m_author` 'Autodesk Revit', real episode history/counts read from a
  native record; FamilyMgr entry shape is already 1-GUID native; the
  inline ADocument swapped for a remapped native one is the H6 axis,
  already FAILED — so H11's axis is the two Latest-side rows + the
  ContentDocuments entry framing).
* **H9 FAIL + H10 FAIL** → the copies themselves are rejected even
  uninstanced (famload's authored elements pass that cell) — a copy delta
  is unlawful (duplicate-family shape / renamed surrogate / carried
  preview / slave); re-examine `copy_report.json`'s five moves, rebuild
  minus the preview+slave sub-cluster as H9b.
* **H9 PASS + H10 FAIL** → incoherent; oracle noise; re-run.

## §4  The ranked famload-vs-native field diff (hostfix_spec.json — the fix spec, computed now)

A = the NATIVE element (V20-certified layer), B = famload's authored
element (H7's load file, batch-37 evidence).  Ranked by the audit's deep
walk from a placed instance:

1. **FamilySymbol — the headline.**  rep **GElement vs SerializedDummy**;
   `m_geomSteps` **GeomStepList (1 BaseFamilySymbolGStep, version 7,
   flags 761725, 21 face-hist + 12 edge-hist + 1 curve-hist) vs None**;
   `m_pGeomTable` **34-row GeomTable vs None**; `m_refFaces` **14 plane
   Faces vs []**; `m_strongRefs` 2 vs []; `m_hasParamDefValue` **0 vs 1**;
   plus `m_outline` / `m_cutPlaneHeights` / `m_pParams` /
   `m_pMoveRestrictions` / `m_geomTag2MaterialId` shape deltas.
2. **Family.**  `m_pFamilyTypes` 5 named pairs (idx 1) vs ONE blank ' '
   row (idx 0); `m_familyIds` 16 resource-twin rows vs param twins only;
   `m_oFamDoc.m_big2SmallMap2` 50 rows vs param twins only; `m_dbviewInfos`
   component preview vs annotation 107/6; `m_oFamilyReferenceIdxMgr`,
   `m_cellList`, `m_familyParams`, `m_nextAbsorbedIndex`,
   `m_predefinedLimitIdx`, `m_bIsSavable`, `m_path`, `m_omniClassCode`,
   `m_seekItemId`, `m_oFamDimConstrMgr`.
3. **FamilySurrogate.**  `m_previewElemId` → a real LegendComponent vs −1
   (famload authors NO preview constellation at all).
4. **FamSymSurrogate.**  id fields only — near-parity.
5. **ParamElemFamily twin.**  `m_pParamDef` internals — near-parity; the
   ROSTER differs (native twins 1 of 2 params; famload twins every param).

famload additionally authors NO counterpart for: the LegendComponent
preview, the 16 resource twins, the slave symbol.

## §5  The corpus law behind the fix (mined this session; re-mineable)

`experiments/hostpair/corpus_geometry_grammar.json`
(`rvt.famload_hostfix.mine()`), ALL **201** instanced FamilySymbols across
rstbasic / rstadvanced / racbasic / rme:

* **201/201**: rep = GElement, root `GInfo.m_tag` = the symbol id, rep
  flags 2; exactly ONE `BaseFamilySymbolGStep` (id 1); GeomStepList
  idCounter 2, `latestGStepType [2,2,2,2,2]`, all other lists empty, all
  snapshots null; GeomTable bigTableOwner null / refPntMirrored False.
* **0/201** single-subnode reps (famgen's authored roster!); **193/201**
  end with a bare empty Geometry node (8 end in GRichText label tails).
* **0/201** empty `m_refFaces` (min 9, max 82) — and the type-6
  face-history rows `[6, tag, -1]` ARE the refFaces' tags (measured
  876569: 9 == 9): they are the family's REFERENCE PLANES projected into
  symbol space (origin planes flags 2622116, other datums 2622180) — NOT
  the "graph node" reading famgen's one-specimen [H] grammar guessed.
* **200/201** `m_hasParamDefValue` 0 (famload writes 1 on its dummy).
* Attested-variable (kept from famgen's lawful bake): list flags 9|11,
  step version 7|4|3|6, step flags 761725 modal.

So the two loaders were BOTH off-corpus for instanced symbols: famload's
dummy+no-steps form appears in NO sample; famgen's bake violates three
mined invariants (single-GFilter roster, no trailing Geometry node, empty
refFaces).  `famload_hostfix.corpus_symbol_form()` corrects both: famgen's
proven face/edge/curve tagging pipeline + (a) reference-face node rows
with matching `m_refFaces` authored from the family's origin RefPlanes +
Ref. Level, (b) the `[empty GFilter, content GFilter, trailing Geometry]`
roster (the dominant minimal corpus shape, 71/201), (c)
hasParamDefValue 0.  Emitted BXhf_f1i1 symbol, read back from bytes:
22-id space (3 ref nodes + 6 faces + 12 edges + 1 form tag), 22-row
table, 3 refFaces with tags == the type-6 rows, trailing bare Geometry —
`assert_symbol_form` green on all 7 staged symbols (1 + 6).

Wiring: **opt-in, default OFF** — `corpus_symbol_form()` context manager
patches `rvt.famgen.loader.author_family_symbol` +
`rvt.famload.author_family_symbols` for the block and reverts (the exact
live-patch wiring `rvt.famload_fix.fixed_product_path` established for
D1..D5), plus `load_family_into_project(..., hostfix=True)` /
`load_family_documents(..., hostfix=True)` convenience wrappers.  The
one-line permanent wiring into the loaders' own signatures is deliberately
NOT made until a viewer verdict blesses the form.

## §6  Honest limits

* **H9's confidence bound**: the copies carry five declared content moves;
  if the audit objects to any of them (the rename, the fresh famDocGUID),
  an H9 FAIL could be mis-attributed to registration.  H10 splits most of
  that (the moves are all present uninstanced), and the moves are each
  individually forced (uniqueness constraints measured in-corpus).
* **The twin-roster delta**: H9 carries the native 1-twin roster where H7
  carried famload's 2 — deliberate (byte-copies mean the native roster)
  but it means H9 PASS convicts famload's host-element authoring
  INCLUSIVE of its twin-roster choice; the per-field culprit inside that
  set is then batch 39's + follow-up rungs' question.
* **The fix's reference-face law** is authored from two deep-read
  specimens + the 201-symbol never-empty invariant; the corpus also
  carries form-derived reference faces (flags 2621668, type-5-linked)
  this module does NOT author, and our 3-plane datum set is below the
  corpus minimum COUNT of 9 (which belongs to 3×3-grid families — the
  count is family-content-derived, not a constant).  Confidence: the
  roster/trailing-node/hasParamDef corrections are 0-or-200-of-201
  invariants (high); the refFace payload is a two-specimen shape copy
  (medium).  The viewer verdict on batch 39 is the judge; a BXhf FAIL
  does NOT invalidate the H9/H10 reading (independent bases + controls).
* **DEMO_250v_room_v3's frontdoor status** is PROOF-ONLY (self-checks
  PASS) — the front door's own honesty stamp; the staged file is the
  combined output, validator-clean, deliverable-rule compliant (stamped,
  handed over).
* Fresh GUIDs are minted per rebuild — the STAGED bytes are canonical;
  `fix_accounting.json` gates were re-run against the exact staged
  batch-39 bytes after a rebuild minted fresh GUIDs (the staged copies
  were never overwritten — probe_batch's no-overwrite gate held).

## §7  Verification (how to re-run)

```
.venv/bin/python tools/hostpair_probe.py survey    # native-cluster pins (22 elements, 66/66 byte-exact)
.venv/bin/python tools/hostpair_probe.py build     # H9 + H10 (+ gates + probes.json)  ~46 s
.venv/bin/python tools/hostpair_probe.py diffspec  # hostfix_spec.json (famload vs native, ranked)
.venv/bin/python tools/hostpair_probe.py verify    # re-run gates on emitted probes
.venv/bin/python tools/hostpair_probe.py stage     # batch 38 (control = rst copy)
.venv/bin/python tools/hostpair_probe.py fixdemo   # BXhf_f1i1 + DEMO_250v_room_v3  ~22 s
.venv/bin/python tools/hostpair_probe.py stagefix  # batch 39 (control = G_ABPD copy)
.venv/bin/python -m pytest tests/test_hostpair.py -q   # 17 passed
```

## BRANCH STATE

* **status: DONE — BATCH 38 (the H9/H10 binary) AND BATCH 39 (the
  speculative fix ladder) BUILT, GATED, STAGED; the decision table and the
  ranked famload-vs-native field diff computed and recorded.**  STOPPED AT
  READY: nothing uploaded; the viewer queue is the orchestrator's.
* **no VCS** (working tree, not a git repo).  Files written:
  `tools/hostpair_probe.py` (new, ~1,440 lines; survey/build/diffspec/
  verify/stage/fixdemo/stagefix), `src/rvt/famload_hostfix.py` (new, ~690
  lines; the corpus-lawful symbol form + opt-in wiring + miner +
  assertions), `tests/test_hostpair.py` (new, 17 pass),
  `experiments/hostpair/` {H9.rvt md5 `2eb3a66f`, H10.rvt `e28952e7`,
  BXhf_f1i1.rvt `1d6d2dd7`, DEMO_250v_room_v3.rvt `d7798f2b`,
  probes.json, accounting.json, fix_accounting.json, copy_report.json,
  hostfix_spec.json, native_cluster_survey.json,
  corpus_geometry_grammar.json, `_build/**` (H9_load.rvt + load_report +
  demo_v3/ + chain dirs), `_survey/**` (measurement scripts, dev-only)},
  staging copies + `batch_38.json` (CTRL_rstbasicsampleproject_b38
  `b3235ad2`, = the untouched sample) + `batch_39.json` (CTRL_G_ABPD_b39,
  byte-identical certified G_ABPD) under `experiments/acceptance/` via
  `probe_batch.stage` (its designed output).
* **gates**: all four probes validator VALID 0 errors / 0 unexpected;
  four-registry coherent (H10 +1/+1/+1/+1; H9 instance hop
  registry-silent; BXhf +1u; DEMO +6u); survivor law 0/0 everywhere;
  identity PASS (H9/H10); byte-copy ledger = 284 id-remapped leaves + 5
  declared moves, zero undeclared; `assert_symbol_form` OK on 7/7 staged
  fix symbols; controls md5-verified byte-identical to their bases; all
  staged copies md5-verified against manifests and experiments/ copies.
* **NOT VIEWER-TESTED**: every claim above is the machine gate; no
  acceptance claim is made.  All probes PROOF-ONLY (quarantined
  sample-derived content; never bundled — the deliverable rule's dev-only
  lane).  `famload_hostfix` is OFF by default everywhere.
* **next action (orchestrator)**: upload batch 38 in manifest order (H9
  first), then batch 39 (BXhf_f1i1 first); verdicts to
  `docs/coverage/viewer-certified.json`; read batch 38 with
  `experiments/hostpair/probes.json → reading_the_matrix` and batch 39
  with `→ fix_reading`.  H9 PASS ⇒ flip the fix campaign to the §4 spec
  (famload_hostfix is rung 1); H9 FAIL + H10 PASS ⇒ commission H11 (the
  registration-row byte-model, §3 design).

# famdoc-bisect — THE HYBRID FAMILY-DOCUMENT BISECTION (staged)

Stream: **famdoc-bisect** (2026-08-05).  Charter: the one open product bug —
instances of OUR generated families fail the open-time audit on any base,
any load path, any symbol form (D1..D5 landed), while instances of
Autodesk-authored families pass — so the defect is INSIDE our generated
family DOCUMENT, deep-walked only when an instance references it.  Build
the hybrid ladder that finds WHAT: probes on the certified rst sample, each
= untouched sample + ONE loaded family document + ONE placed instance,
where the family document is a hybrid of an Autodesk-authored famdoc body
with OUR subtrees swapped in one axis at a time; plus the ranked
per-element diff checklist the hybrids test.

**Territory touched ONLY:** `tools/famdoc_bisect.py` (new),
`experiments/famdoc_bisect/**` (new), `tests/test_famdoc_bisect.py` (new),
this record, and the staging copies `probe_batch` itself writes under
`experiments/acceptance/` (batch manifest + probes + control — its designed
output).  No `src/**` file, no existing tool or test edited.  No browser
(STAGE only — the orchestrator uploads); no Autodesk install dirs; zero
donors in shipped output (every probe is PROOF-ONLY sample-derived dev
content, quarantined in experiments/ exactly like the SX/SL precedents).

## Result in one screen

* **THE LADDER IS BUILT, GATED AND STAGED AS BATCH 37** — 8 probes, every
  one `rvt.validate` **VALID 0 errors / 0 unexpected** (1 warning = the
  standing inherited RebarShape/DataStorage decoder gap, present in the
  untouched sample itself), four-registry **coherent** (+1/+1/+1/+1 per
  load hop, instance hop registry-silent), reduce-law survivor check
  **0 removed / 0 modified** (pure adds), identity gate **PASS**, staged
  (`experiments/acceptance/batch_37.json`) with the control pinned to the
  **UNTOUCHED rst sample** (`CTRL_rstbasicsampleproject_b37.rvt`,
  md5-identical `b3235ad2743f19bcfff243654fec35dd`; every staged probe
  copy md5-verified against its source and the manifest).
* **The donor body is the strongest possible control**: the rst sample's
  OWN embedded `M_Concrete-Square-Column` famdoc (unit 36, 417 records,
  SELF-CONTAINED — measured: its one nested Family element carries no
  content document).  Its native symbol `450 x 450mm` is the exact symbol
  the certified **V20** instance points at — placement of an instance of
  this family on this base is already viewer-PASSED; the ONE new mechanism
  H7 adds is the famload load of an id-rebased copy.
* **Every hybrid is an ADD-form union** (our subtree added to the intact
  donor body, registered in the donor self-Family exactly like its own
  members: header deletion list + `m_familyIds` absorbed indices + for
  parameters all four table surfaces).  No donor element is deleted — a
  FAIL convicts OUR added grammar, never a botched excision, and the
  probes are mutually independent.
* **The id rebase is the loader's own machinery** (`_walk_replace_ids`
  over a monotone map into a block above the rst watermark 1,472,524); the
  418/418-record encoder roundtrip of the donor unit is byte-exact
  (measured before any build), and a schema-typed reference scan (the
  validator's own RefDecoder) proves every ElementId-typed value of every
  hybrid resolves in-unit or to an rst-host-resident id (the standalone
  dev `.rfa` of each hybrid documents the same split; the probe-file
  validator's clean reference pass is the binding proof).
* **The per-element diff checklist is extracted and ranked**
  (`experiments/famdoc_bisect/famdoc_diff.json`): our famdoc vs the
  SAME-CATEGORY Autodesk panelboard (rme 208V MCB, unit 30 — nested, so
  diff-only) and vs the hybrid donor column, singleton-by-singleton
  (extrusion / sketch / curves / self-Family / params / datum / connector /
  views / units), ranked by what the audit's deep walk visits from a
  placed instance, with the inline-ADocument gap quantified (Autodesk
  embeds 131 populated AppInfoManager registries; our loads author the
  all-null 239-slot form).

## §1  The ladder (upload/reading order = maximum information first)

All files `experiments/famdoc_bisect/<rung>.rvt`; md5s + declared bases in
`experiments/famdoc_bisect/probes.json`; per-rung accounting in
`accounting.json`; per-hybrid assembly reports in
`_build/<rung>/hybrid_report.json`.  Fresh GUIDs are minted per rebuild —
re-hash after any rerun.

| # | rung | family document | the ONE thing it tests |
|--:|---|---|---|
| 1 | **H7** | the Autodesk column famdoc, id-rebased, otherwise verbatim | control-A: famload + rebase + our template placement on a LAWFUL document (all three ingredients individually certified: famdoc native to this base, famload = L1a/L_v2, placement = V20) |
| 2 | **H1** | H7 + our GEOMETRY subtree (ExtrusionElem + VarSketch + 4 CurveElems + SketchPlane) | our geometry-form grammar under the instance walk (the downlight precedent makes it prime) |
| 3 | **H2** | H7 + our PARAM/TYPE layer (14 ParamElemFamily + rows in all four self-Family surfaces) | our parameter/type-table grammar |
| 4 | **H3** | H7 + our DATUM layer (2 origin RefPlanes + Level + LevelAttributes) | our reference/datum grammar |
| 5 | **H4** | H7 + our VIEW constellation (the 8-element plan-view chain) | our view/preview grammar |
| 6 | **H5** | H7 + our CONNECTOR layer (ConnectorElem + ElectricalLoadClassification + the apparent-load param), face ref repointed to the donor solid (tag 2 exists on both — measured) | our connector grammar |
| 7 | **H6** | H7's document with the DONOR's OWN inline ADocument carried (remapped; fresh history identity per the measured native law) | the inline-ADocument axis (131 populated registries vs our all-null form) |
| 8 | **H8** | OUR famdoc verbatim, famload + the demo's own stage_equipment (the instbug-residual SL_f1i1 recipe) | control-B: the known-FAIL anchor |

Placement: H1..H7 uniform (ConstructedSpecimens template +
`add_family_instance` + commit at a fixed position, instance category = the
family's own, connector manager = the template's `None` — corpus-lawful);
H8 = the demo's own recipe byte-faithfully (product
FamilyInstanceConnectorManager, intent position) so the recorded SL_f1i1
FAIL reproduces exactly.  All instances carry phase 86961 + the D-fix
shapes (machine-read back from the emitted bytes).

**Reading the matrix** (full text in `probes.json → reading_the_matrix`):
CTRL FAIL → round VOID.  **H7 PASS + H8 FAIL** → the round is bracketed:
machinery lawful, our document content is the poison; each H1..H5 FAIL
independently convicts that axis of our grammar (fix in deep-walk rank
order H1 > H2 > H3 > H5 > H4).  **H7 FAIL** → the machinery corrupts a
lawful document; H6 then splits the inline-ADocument axis (H6 PASS + H7
FAIL convicts our authored minimal inline ADocument) from the unit
re-encode/rebase and famload host flavour (both FAIL) — with V20 already
certifying the placement half.  **All H1..H6 PASS + H8 FAIL** → no single
added axis reproduces it; the defect is in what only H8 carries (our
whole-document composition: the S0 skeleton itself, element ordering, the
registry singletons, or an axis interaction) — next ladder: pairwise
unions or the inverse bisection.

## §2  Why THIS donor (and what the alternatives lacked)

* Surveyed every embedded famdoc in rst/rme/rac basic+advanced and dach:
  **no nested-free electrical famdoc exists anywhere** (every rme
  electrical fixture/equipment famdoc embeds 1–3 REAL nested content
  documents — measured `m_oFamDoc.m_contentDocGUID` per nested Family).
  Loading one would need multi-unit nested-document machinery that neither
  famload nor the extract assembler supports (both refuse nested), and the
  registration shape of a nested unit (its surrogate lives INSIDE the
  parent unit) is not authorable host-side today.
* The rst column famdoc is the unique candidate that is simultaneously:
  same-file-native (the control literally contains it), instance-certified
  (V20), self-contained (nested Family is docless — the level-head symbol
  family lives entirely inside the unit), fully decodable (418/418
  roundtrip), and a MODEL family with a real solid (apples-to-apples for
  the geometry axis).  Category differs from ours (-2001330 vs -2001040);
  the same-category comparison lives in the DIFF deliverable instead
  (§3), where nestedness does not matter.
* Known constant of the donor path, recorded: famload twins EVERY
  ParamElemFamily in the unit — including the nested level-head family's
  'Radius' param — so H1..H7 carry 2 host twins where the native host
  carries 1 (+resource twins).  Constant across all donor rungs, absent
  from H8; exonerated wholesale if H7 passes.

## §3  The ranked per-element diff checklist (famdoc_diff.json)

Two references, field-level diffs of the matched singletons, ranked by the
deep walk from a placed instance (rank 1 = what symbol geometry
regeneration touches first):

1. **Geometry pipeline** (ExtrusionElem obj+rep / VarSketch / CurveElem /
   SketchPlane) — the instance→symbol→geomSteps/GeomTable walk's deepest
   content.
2. **self-Family** (FamilyTypeTable / m_familyParams / m_familyIds /
   order cell) — the type row the host symbol carries.
3. **Datum** (RefPlane / Level / LevelAttributes).
4. **Connector** (ConnectorElem — vs the rme panelboard's, the same
   category the [H] grammar was mined from).
5. **Views** (DBViewPlan + satellites).
6. **Registry / inline ADocument** — class-histogram gap (the donor
   column carries 68 CategoryElem + 68 GStyleElem + 31 FontElem + dim
   styles… our docs carry NONE of the style/registry tables) and the
   inline-ADocument gap (131 populated AppInfoManager slots + multi-episode
   history vs our all-null single-episode form; H6/H7 read this axis).

`only_in_A` fields = surfaces our grammar never authors; `only_in_B` =
what we author that Autodesk does not; `differing` = shared fields with
different shapes.  The checklist is the fix-spec source for whichever axis
the viewer convicts.  Load-bearing measured highlights (rme panelboard A
vs our panel B, field names from the JSON):

* **ExtrusionElem** — 7 differing / 19 equal, and the seq-103 GElement is
  STRUCTURALLY AT PARITY (both: 1 Geometry node, 6 faces / 12 edges, tag
  range 0..17, same flags) — the box solid itself is not the obvious gap;
  the differing fields are `m_geomSteps` (the FORM-level geometry history
  — theirs populated, ours not), `m_famElemVisibility`, `m_cellList`,
  `m_pParamValueSetDouble`, `m_sideRefPlaneCurveBased`.
* **VarSketch** — the widest form-level gap (16 differing): `m_geomSteps`,
  `m_pGeomTable`, `m_oParamPlane`, `m_absorbedCurves` +
  `m_absorbedCurvesData`, `m_curveObjIdxMap`, `m_oGuessCache`,
  `m_version`, `m_highResidualTol`, `m_elemIdsPairSet`, `m_nextIndex`…
* **CurveElem** — `m_geomSteps`, `m_pCurveDriver`, `m_referenceType`,
  `m_ownerDBViewId`, `m_detail`, `m_useOffsetPos`, header
  `m_pBBox`/`m_ownerViewId`/`m_miscId`.  So the geometry-HISTORY family
  of fields (`m_geomSteps`/`m_pGeomTable`) differs on the famdoc's OWN
  form elements, not just on the host symbol — the instbug-residual P1
  finding extends into the document; H1 carries exactly this shape.
* **self-Family** — 19 differing incl. `m_nextAbsorbedIndex`,
  `m_refTypeIds`, `m_refs`, `m_fsdos`, `m_deletableElements`,
  `m_predefinedLimitIdx`, `m_oFamDimConstrMgr`, `m_pFamilyTypes`,
  `m_familyParams`, `m_cellList`, `m_lockedParameterIdsForDirect…`.
* **ConnectorElem** — 8 differing: `m_pDomain`, `m_pFaceU`, `m_pFaceV`,
  `m_idPrimaryElem`, `m_oPlaneRef`, `m_cellList` (the [H]-grammar
  surfaces; H5 carries ours).
* **ParamElemFamily** — only 3 differing (`m_pParamDef` + ids): the
  param-def grammar is NEAR PARITY, ranking H2 below H1/H5 on priors.

## §4  Gates (all machine, per probe; no acceptance claim)

* `rvt.validate` **0 errors / 0 unexpected** on every probe (current
  validator incl. the E1/E2/E3 loaded-content rules; D1 does not fire —
  connector managers are `None` or `FamilyInstanceConnectorManager`; D2
  cannot fire at one load).
* Four-registry census coherent; load hop +1/+1/+1/+1; instance hop
  registry-silent (+1 ElemTable row only) — the SX/SL-established shape.
* Survivor law: 0 removed / 0 modified vs the immediate parent (pure
  adds); identity gate PASS.
* Schema-typed reference resolution (validator's RefDecoder): every
  ElementId-typed value in every hybrid famdoc resolves in-unit or to an
  rst-host-resident id; **unresolved-anywhere = 0** is a build-refusing
  gate.  The standalone dev `.rfa` of each hybrid (never staged) documents
  the same split under the family-mode validator: the host-resident
  remainder is the expected project-hosted-family shape — the probe file,
  which re-embeds the document into the very host that owns those ids, is
  where the reference pass is binding, and it is clean.
* H-specific proofs read back from the emitted bytes: H1 carries 2
  extrusions / 15 curves; H2 16 ParamElemFamily with our rows in every
  type pair; H5's connector geomRef → the donor extrusion, tag 2, its
  param-driven cell → the carried param; H6's ContentDocuments entry
  carries 131 populated AppInfoManager slots (H7: 0); H8 = 41-element our
  famdoc + FamilyInstanceConnectorManager instance.

## §5  Honest limits

* The id rebase is unavoidable (element ids are file-wide unique; the
  donor's originals are already taken by its native copy).  H7 therefore
  proves "famload + rebase + placement", not famload alone; the 418/418
  byte-exact roundtrip and the loader's own record gate bound the rebase
  delta to exactly the remapped id values.
* The H1..H7 instance rides the CONSTRUCTED template with connmgr None;
  H8 rides the product connmgr.  R_inst_box (null connmgr, FAIL) pins
  that null managers do not save our families, so the H8 anchor's product
  manager is not load-bearing for the bisection — recorded, not assumed.
* famload's host flavour (1-blank-row type table, dummy symbol, minimal
  inline ADocument, twin-every-param) differs from the native component
  host shape (5-pair table, baked GElement symbols, 50-row big2small with
  resource twins) — CONSTANT across all 8 probes and already
  viewer-tolerated uninstanced (L1a/L_v2); H7 is exactly the rung that
  tests it under an instance.
* The donor famdoc references rst host resources (line styles, materials,
  fill patterns — the native big2small's small-id rows); those resolve in
  the probe host by construction.  The hybrids are therefore
  PROJECT-HOSTED documents, not standalone families — the dev `.rfa`s are
  evidence artifacts only.
* An H1..H5 PASS exonerates that axis ONLY in add-form (grammar
  lawfulness); a defect that requires our subtree to be the DOCUMENT'S OWN
  (e.g. the family's sole geometry) would surface in H8 but not the
  hybrid — the pre-branched "all-pass" reading covers it.

## §6  Verification (how to re-run)

```
.venv/bin/python tools/famdoc_bisect.py build            # all 8 probes (~13 min)
.venv/bin/python tools/famdoc_bisect.py build --only H7,H1
.venv/bin/python tools/famdoc_bisect.py diff             # famdoc_diff.json
.venv/bin/python tools/famdoc_bisect.py verify           # re-run gates on emitted probes
.venv/bin/python tools/famdoc_bisect.py stage            # probe_batch gate + rst control
.venv/bin/python -m pytest tests/test_famdoc_bisect.py -q
```

Stream-local tests: `tests/test_famdoc_bisect.py` -> **12 passed** —
donor pinning (shape, self-containedness, inline-adoc census 131/239),
rebase closure (no old id survives; monotone order), axis-set multisets,
hybrid registration invariants (deletion/familyIds/type-table coverage),
emitted-probe gates + axis content + the H6/H7 inline-adoc split (0 vs
131 populated slots read back from the staged bytes), probes.json shape.
Full suite: NOT run (SUITE-COORDINATION hard rule; the canonical
published count 1697/7/2 is adopted).

## BRANCH STATE

* **status: DONE — LADDER BUILT, GATED, STAGED (batch 37); DIFF CHECKLIST
  EXTRACTED.**  STOPPED AT READY: nothing uploaded; the viewer queue is
  the orchestrator's.
* **no VCS** (working tree, not a git repo).  Files written:
  `tools/famdoc_bisect.py` (new, ~1,080 lines; build/diff/verify/stage),
  `tests/test_famdoc_bisect.py` (new, 12 pass),
  `experiments/famdoc_bisect/` {H1..H8.rvt (staged md5s: H7 149f5772, H1
  bfe5dc60, H2 8ffc5713, H3 cd412cfc, H4 1d275931, H5 534773e7, H6
  a1099ab6, H8 ea18a034), probes.json, accounting.json,
  famdoc_diff.json, `_build/**` (per-rung load files, hybrid reports, dev
  .rfas)}, this record, staging copies + `batch_37.json` +
  `CTRL_rstbasicsampleproject_b37.rvt` under `experiments/acceptance/`
  via `probe_batch.stage` (its designed output).
* **gates**: every probe validator VALID 0 errors / 0 unexpected,
  four-registry coherent, survivor law 0/0, identity PASS, typed-reference
  resolution 0 unresolved-anywhere (29 host-resident donor resource refs,
  constant across all donor rungs), probe_batch ADMISSIBLE (bases resolve
  as `sample`), control + all staged copies md5-verified.
* **NOT VIEWER-TESTED**: every claim above is the machine gate; no
  acceptance claim is made.  All probes PROOF-ONLY (quarantined
  sample-derived content; never bundled — the deliverable rule's dev-only
  lane).
* **next action (orchestrator)**: upload the batch in manifest order
  (H7 first), verdicts to `docs/coverage/viewer-certified.json`, read with
  `probes.json → reading_the_matrix`; the convicted axis's fix spec starts
  from `famdoc_diff.json`'s ranked entries for that axis.

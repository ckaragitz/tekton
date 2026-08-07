# genesis-triage-census — workstream record (THE REQUIRED-SET CENSUS, 2026-08-03)

Charter: build the empirical model of the MANDATORY element / stream / save-unit
set from POSITIVE evidence — the files Autodesk's reader ACCEPTS — and diff the
six rejected files against it; deliver the ranked table + the top hypotheses for
Bug A and Bug B with the single probe each needs. Territory touched ONLY:
`src/rvt/census.py` (new), `tests/test_census.py` (new, 12 pass),
`docs/writer/required-set.md` (new, the deliverable), this file. NO existing
`src/rvt/*.py`, test, tool or experiment file edited (all IMPORTED read-only);
no probe files emitted (not this stream's job); no browser use.

## Result in one screen

The deliverable is `docs/writer/required-set.md`. Headline (all measured this
session by `rvt.census`, 38 files, ~15 s):

* **149 element classes are present in EVERY one of the 32 accepted files; 70
  of them carry the IDENTICAL count in all 32** (settings singletons + compiled-in
  catalogs — from a 3,709-element reduction to the 49,776-element German
  worksharing project). This 70-class invariant tier is the strongest positive
  evidence the format has produced.
* **BUG A named:** all four G-files have byte-identical element inventories (234
  elements / 47 classes) missing **110 of the 149 core classes incl. 62 of the
  70 invariant ones** (the MEP settings/sizes singletons, `HVACLoadSpaceTypeElem`
  125, `KeynoteTable`, `StructSettingsElem`, `AutoJoinTracker`, `GraphicsCache`,
  `RbsDbViewSystemNavigator`, …), 16–40× short on the catalog classes it has
  (`GStyleElem` 94/1,533, `CategoryElem` 7/284, `FontElem` 3/96), and zero family
  machinery (accepted floor: 21 families / 13 with docs / 52 embedded units).
  Top hypotheses A1 constellation, A2 catalog depth, A3 zero families — probes
  named (required-set.md §5).
* **BUG B located below the element layer:** `census(R9).classes ==
  census(R9b).classes` exactly (test asserts it); R9b/R10b differ from R9 only in
  units 53→15 / CD entries 52→14 while the ADocument `ContentTable` still lists
  52 → **38 dangling content records**. Top hypothesis B1 = purge the ContentTable
  to the 14 survivors on R9b; B2 = the `Partitions/21` unit splice; **B3
  (ContentDocuments framing) CLOSED** — R9b's/R10b's CD payloads reassemble
  BYTE-EXACT through the asset-forge solved grammar.
* **DBViewType head-family question EXONERATED:** the 72 `m_famId` refs point at
  the 8 document-less curtain-wall system families (never heads); accepted `dach`
  has 23 view types referencing NO family → G1's reference-free view types are an
  accepted shape (count 3 vs floor 23 is the only residual concern there).

## Deliverables

| item | path | state |
|---|---|---|
| census + diff library (`census`, `mandatory_set`, `class_presence`, `missing_from`, `count_shortfall`, `rank_suspects`, `stream_unit_matrix`, `dbviewtype_report`, `run`, `run_certified`, CLI) | `src/rvt/census.py` | done, `python -m rvt.census --certified` ~15 s |
| tests (rst census vs ElemTable; units/coherence; DBViewType finding; diff maths on synthetic censuses; the R9==R9b Bug-B attribution; the G1 Bug-A gap) | `tests/test_census.py` | 12 pass, 0.7 s |
| the ranked table + hypotheses (human deliverable, incl. Appendix A = all 149 rows) | `docs/writer/required-set.md` | done |
| full corpus census JSON (regenerable, not committed) | `python -m rvt.census --certified --json <path>` | scratchpad copy at hand-off |

## Evidence log (measured this session)

* Corpus = 6 samples + 26 certified-on-disk (viewer-certified.json lists 27;
  `experiments/acceptance/V15_regzip_ecc_full.rvt` is ABSENT from disk — flag
  for the orchestrator, the census skips it) = 32 accepted; 6 failed.
* Host document = partition save-unit 0 of the first `Partitions/<N>` — its
  seq-102 id set equals `Global/ElemTable` ids exactly on all 38 files, including
  dach (2 partition streams; the second stream's single unit is GUID-less =
  a second host-side unit, not a family document).
* Family-document units = GUID-carrying units; their GUID set == the
  `ContentDocuments` entry GUID set on EVERY accepted file (dach 1,243, rme 305,
  rst-lineage 52). Min over accepted: 52 embedded documents, 21 host families,
  13 families with documents (all set by the rst lineage / R9).
* R9's PASS single-handedly proves 81 classes OPTIONAL (incl. `HubsTracker`,
  `GCSTracker`, `InitialViewSettings`, `PostedWarningElem`, `AllPlanTopologies`,
  the whole host-content type stack) — do not chase them.
* R4s is NOT a deep element reduction (13,138 elements, 290 classes) — the
  ladder-v1 label "near-minimal" is a misnomer; R9 is the deepest accepted
  inventory (3,709 / 162 classes).
* Stream presence identical (12 streams) across every file incl. all failures;
  `RevitPreview4.0` is rme/rac-lineage-only → optional.
* R9b's / R10b's `Global/ContentDocuments` = `parse → assemble` byte-exact,
  clean 14-byte end record, `u64 1` prefix — CD framing exonerated (B3 closed).

## Gotchas found (for KNOWLEDGE.md merge)

1. **The intersection over the accepted corpus is really "R9's residue ∩ every
   sample"** — R9 sets 39 minima; a minimum is "smallest observed", not a floor.
   Only the 70 invariant-count classes are floor-strength evidence.
2. **`DBViewType.m_famId` in every English-lineage file points at the 8 curtain-
   wall SYSTEM families (9 view types each), never at annotation heads** — the
   reduction record's `Family ← DBViewType ×72` pin is these; the 12 head
   families are pinned only by their own family-scoped `CategoryElem`/`GStyleElem`/
   `FontElem`/text-type children (`m_famId` = the family). dach references none.
3. **A `ContentTable` record's key is `m_ContentKey.m_guidKey`** (the content-
   document GUID) — the exact join key for the coherence tuple (units ↔ CD
   entries ↔ ContentTable); `content_records_without_document` is the Bug-B
   metric (R9b/R10b = 38).
4. **The document-settings constellation is countable at the ELEMENT layer**
   (70 invariant-count classes) — a second instrument for the ADocument's
   `UniqueElementsTracking` 72-slot table; they name the same gap in G1.
5. dach = the corpus's independence witness (German names, worksharing, 353
   classes) — the reason the 149-class intersection is not a template artefact.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/content.py` (content stream):** promote the asset-forge
  ContentDocuments codec (`parse/assemble/insert_content_documents`) out of
  `rvt.famgen.factory` — the census imports it from famgen today, which is an
  odd dependency direction for a container-layer parser.
* **`tools/rvt_reduce.py` (genesis-reduction stream):** probe **B1** = R9b +
  `ContentTable.m_ContentRecSet` purged to the 14 surviving GUID records via
  `rvt.adocument` `write_with_latest` (their keys are the 14 CD entry GUIDs);
  probe **B2** = R9 with the 38 CD entries removed + ContentTable purged, but
  `Partitions/21` untouched. Both differ from a known file by one class.
* **`tools/genesis_assemble.py` (genesis assembler stream):** probe **A2** = G1
  + full object-styles catalog only; **A1** = G1 + the 62 invariant-class
  element groups + their singleton-slot registrations (the exact class list is
  Appendix A of required-set.md, `count invariant` rows with `in G1 = 0`).
* **`src/rvt/validate.py` (validation stream):** the census's coherence tuple
  is a natural fourth validator layer (`content_records_without_document > 0`
  ⇒ error) — it would have flagged R9b/R10b, which validate 0-error today. Also a
  `--required-set` advisory: warn when a mandatory class (Appendix A) has count 0.
* **orchestrator:** `experiments/acceptance/V15_regzip_ecc_full.rvt` is listed
  in `viewer-certified.json` but not on disk (the on-disk sibling
  `V15_fullfile_real_ecc.rvt` — an rst whole-file rewrite — lacks NONE of the
  149 mandatory classes, so the missing file would not shrink the set).

## Open questions (need the viewer)

* Probe order recommendation: build the **K-floor** file = G1_candidate + A2
  catalog + A1 constellation (zero families) FIRST — one upload decides whether
  Bug A closes without families; then A3 (one coherent embedded family) only if it
  fails. On the reduction side, B1 alone decides Bug B.
* Is any of the 39 R9-set minima actually a floor (e.g. `Family` 21 = the
  curtain octet + 13 head/title families)? Only an R11+ rung answers it; the
  census cannot.

## Full-suite result at handoff

This stream's `tests/test_census.py` = **12/12 pass** (0.7 s), run repeatedly.
The full suite (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`,
~10 min) was launched but had NOT finished at the forced hand-off — its count
is UNVERIFIED here; the expected result is the corpus baseline (previous records:
600+ pass) + 12 new census tests, with the same three pre-existing failures
outside this territory: `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source`
(plugin bundle drift — my new `src/rvt/census.py` will join the drift list at
the orchestrator's next `tools/sync_plugin.py` run) and the two stale
`tests/test_provenance.py` G0 assertions (`test_G0_resource_refs_are_counted`,
`test_G0_identity_dit_usernames_still_leak`) whose owner-diff genesis-2 recorded.
This stream added no other files and touched no existing source, so it cannot
have introduced a new failure elsewhere; the orchestrator should re-run the suite.

BRANCH STATE: no VCS (plain directory); all work is uncommitted files —
`src/rvt/census.py` (new), `tests/test_census.py` (new, 12 pass),
`docs/writer/required-set.md` (new, deliverable incl. the 149-row Appendix A),
`docs/inbox/genesis-triage-census.md` (this). No probes emitted, no existing
file edited. READY — the ranked table names A1/A2 (constellation + catalog
floor) as the first Bug-A rung and B1 (stale ContentTable, 38 dangling content
records) as the Bug-B rung; the other two streams build them.

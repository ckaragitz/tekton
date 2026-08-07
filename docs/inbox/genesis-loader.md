# genesis-loader — THE K4-FAIL BRANCH: the embedded family-document loader + our head-family set (workstream record, 2026-08-03)

Charter: if the Autodesk reader REQUIRES embedded family documents (K4 FAIL
with KD1 / K3 PASS), the constructed genesis base needs OUR families
INSERTED as proper embedded documents — the exact inverse of the triage
stream's `remove_documents`, reconciling ALL FOUR registries.  Build the
loader (`src/rvt/famload.py`), our twelve annotation-head families
(`src/rvt/famgen/heads.py`), and the proofs L1 (loader on a passing base),
L2 (K1 with the Autodesk heads REPLACED by ours), L3 (G1_candidate + our
heads = the K4-FAIL fix candidate) — pre-built so no verdict waits on a
cold start.  The full spec / field map is `docs/writer/family-loader.md`.

Territory touched ONLY: `src/rvt/famload.py` (new), `src/rvt/famgen/heads.py`
(new), `tests/test_famload.py` (new, 12 pass), `experiments/genesis/loader/*`
(L1a / L1b / L2 / L3 / L3b `.rvt` + twelve `head_*.rfa` + per-probe JSON +
`probes.json` + `heads_report.json`), `docs/writer/family-loader.md` (new),
this record.  NO existing `src/rvt/*.py`, `src/rvt/genesis|famgen` module,
tool or test edited — every dependency (asset-forge factory L1/L2/L3
machinery, the family skeleton, the ADocument / commit / manipulate codecs,
the triage stream's removal tools for L2) is IMPORTED.  No browser / viewer
use: the probes are left on disk with a manifest for the orchestrator's
certification queue.

Coordination note: a parallel stream was writing `src/rvt/famgen/loader.py`
(the asset-forge L4/L5 host loader: COMPONENT families, placed instances,
symbol solid geometry, host = the rme sample; live-edited during this
session, since finished — its `experiments/families/factory/project_with_
*_panel.rvt` proofs are on disk).  This stream deliberately does NOT import
that file (it was live-edited while this was built): the genesis branch needs
the ANNOTATION-family flavour of the host layer plus the four-registry census
/ usage repointing / multi-family write, decoded here against rstbasic's own
head families.  The two loaders share `rvt.famgen.factory`; the ContentTable
/ FamilyMgr / ETD registration bodies are the same format shapes and belong in
one shared core (consolidation proposal in §Diffs).  TWO loaders now exist by
flavour: `rvt.famgen.loader` (component: placement + connectors + symbol
geometry, single family, rme host) and `rvt.famload` (annotation: usage
repointing, N families in one write, any host, the census instrument).

## Result in one screen

**The loader works and the whole L ladder is BUILT, self-verified and
arbiter-clean (0 errors on every file).**  Reproduce:
`.venv/bin/python -m rvt.famload --proofs` (~3 min, all rungs).

| probe | file (experiments/genesis/loader/) | base | after (units / CD / ContentTable / FamilyMgr-guids) | self-checks |
|---|---|---|---|---|
| **L1a** | `L1a_rstbasic_loaded_levelhead.rvt` | rstbasic (viewer PASS) + our level head loaded, unreferenced | 54 / 53 / 53 / 53, coherent | VALID 0 err |
| **L1b** | `L1b_rstbasic_our_heads_active.rvt` | rstbasic + all twelve loaded + every SET head usage field (11 of 43) → OUR symbols | 65 / 64 / 64 / 64, coherent | VALID 0 err |
| **L3** | `L3_G1_candidate_our_heads.rvt` | **G1_candidate (viewer FAIL) + all twelve loaded + its level type's `m_familyTagId` → our level head — THE K4-FAIL FIX CANDIDATE** | 13 / 12 / 12 / 12, coherent | VALID 0/0 |
| **L3b** | `L3b_G1_candidate_our_heads.rvt` | G1_candidate + our level head only + the same repoint | 2 / 1 / 1 / 1, coherent | VALID 0/0 |
| **L2** | `L2_K1_our_heads.rvt` | K1 (Autodesk's empty-project skeleton): our twelve loaded + repointed, then the twelve like-category AUTODESK head families (12 documents, 296 elements) removed COHERENTLY | 53 / 52 / 52 / 52, coherent, 0 residual GUID bytes | VALID 0 err |
| `head_<key>.rfa` ×12 | (standalone form of the same families) | — | — | family-mode VALID ×12 |

Recommended upload batch (one round): **L1a, L1b, L3, L2** (L3b is the
pre-built follow-up if L3 fails on a card message that points at the OTHER
eleven heads; `head_level_head.rfa` is the family-editor question).  The
reading tree is in `probes.json:reading_the_results` and §Reading below.

## Reading the verdicts

* **L1a PASS** ⇒ the load mechanism (four registries + the annotation
  host-side layer) is reader-accepted on a passing base.  **L1a FAIL** ⇒
  a loader defect (registry or record shape); everything else moot; bisect
  with `four_registry_census` + the H1–H6 acceptance list in each `.load.json`.
* **L1a PASS & L1b PASS** ⇒ our annotation-SKELETON head families are
  acceptable ACTIVE heads: family-document CONTENT (the head shape / label /
  view constellation) is NOT required — L3's only remaining variable is the
  constructed base itself.
* **L1a PASS & L1b FAIL** ⇒ a REFERENCED head must carry real content (detail
  geometry / label) — the head-content ladder is the next stream and L3
  cannot pass with these families.
* **L3 PASS** ⇒ embedded family documents were the K4-FAIL fix: the genesis
  base + OUR loaded families opens; the loader is the genesis-2 base's
  family route.  **L3 FAIL (L1a/L1b PASS)** ⇒ family documents alone do not
  fix the constructed base — the residual is the base's other missing
  skeleton content (the K5x / K6 verdicts); read the card message.
* **L2 PASS** ⇒ our heads substitute on the FULL Autodesk skeleton.
  **L2 FAIL (K1 & L1b PASS)** ⇒ the Autodesk head-family REMOVAL took a
  family-scoped host row a survivor needs — bisect against L1b.
* Any card message DIFFERENT from `Revit-DocumentCorruption` is a spotlight.

## New format findings (evidence — merge into KNOWLEDGE.md)

1. **The four registries CONFIRMED as the load contract [V]** — a document
   GUID lives in the `Partitions/<N>` unit separator, its
   `Global/ContentDocuments` entry, the ADocument
   `ContentTable.m_ContentRecSet` record and the ADocument
   `FamilyMgr.m_arrLoadedFamilyInfo` entry (AppInfo slot 0, `{m_surrogateId,
   m_familyDocGUIDs}`).  The loader adds all four coherently; the census
   (`famload.four_registry_census`) reads them and their GUID-set equality
   (rstbasic 53/52/52/52-guids; the FAILED R9b/R10b were 15/14/**52**/**52**).
2. **`Global/PartitionTable` is NOT a document registry [V]** — it is the
   workset table (class 0xc80, one `Workset1` row on rstbasic regardless of
   its 52 embedded documents); loading adds NO row (corrects the charter's
   "a Global/PartitionTable row").
3. **The id watermark spans embedded documents [V]** — rstbasic's
   `Global/ElemTable` footer `IdentifierSource.m_last` = 1,472,524 exceeds
   EVERY embedded document element id (heads at 1,393,072..1,471,960):
   element ids are unique file-wide and the host watermark covers the
   documents.  The loader builds each document above the host watermark and
   its host elements above the document, so the committed watermark covers
   everything (asserted).
4. **The ANNOTATION-family host flavour differs from the component (rme)
   flavour [V, rstbasic level head vs the asset-forge stream's panelboard]:**
   `m_partType` **−1**; the host `FamilyTypeTable` = ONE blank `' '` row
   (types live only as FamilySymbols) while the embedded self-Family's type
   table is EMPTY; the empty `FamDimConstrMgrImpl` is KEPT on the host Family
   (the rme rule drops it); one `DBViewInfoForPreview` {viewFamily 107,
   viewType 6}; `FamilyReferenceIdxMgr` maps the two origin planes' absorbed
   indices to code 10 (unnamed); the host param TWIN keeps
   `m_designOptionId = −4`.  Header constants: Family (10/−32768),
   FamilySymbol (2218/−32768), ParamElemFamily (8202/−32768),
   FamilySurrogate + FamSymSurrogate (10/**−32640**).
5. **`FamilySurrogate.m_guid` is a format constant [V]** —
   `e3e052f8-0156-11d5-9301-0000863f27ad` on all 159 rme surrogates AND
   rstbasic's; not content.  `FamilyMgr` entries reference the SURROGATE id
   (`m_surrogateId`), not the Family.
6. **Head-family USAGE = field + header deletion [V]** — rstbasic
   `LevelAttributes` 305: `m_familyTagId` = the head symbol AND the symbol id
   in its seq-101 `m_parents.m_deletion`; repointing must edit both (the
   loader's `repoint_usage` does, byte-exact via `rvt.manipulate`).  The full
   referrer set is the K3 finding's (Level/Grid/Callout/Viewport attributes
   `.m_familyTagId`, Section head/tail, InteriorElev
   `.m_elevationSymbolId`, StructSettings `.m_bcFixedFamilyId`) — 43 such
   fields on rstbasic (11 set / 32 unset), 1 on G1_candidate (unset).
7. **`ElementTrackingData` does not track annotation-head symbols [V
   rstbasic]** — no `-2006020` (level heads) row exists; the loader appends
   symbol ids only into an EXISTING category row (never creates one).
8. **The ContentTable record shape [V]** — `{m_pHostDocument weak 1,
   m_ContentKey.m_guidKey, m_author ('Autodesk Revit' on the sample →
   'rvt-writer' ours), m_history{originalElementId −1, creationDate ep,
   lastModificationDate ep, lastUserModificationDate −1}, m_EpisodeCounts
   [(episode, record count)]}`, records in ascending-GUID order (the loader
   sorts).

## Gotchas found (for KNOWLEDGE.md merge)

1. `rvt.commit.verify_written()['new_ids_found']` is `{seq: {id: {class,
   clean}}}`, keyed by SEQ first (an easy mis-read).
2. A loader must allocate embedded-document ids ABOVE the host watermark
   and host-element ids ABOVE those, or the ElemTable watermark under-covers
   the file's ids (the reader's IdentifierSource invariant).
3. `rvt.manipulate.modify_element` / `commit_plans` edit BOTH seq-102 objects
   and seq-101 headers of the same element in one plan (usage field +
   deletion list) — the certified modify path handles multi-seq edits.
4. When every usage repoint is skipped (`only_if_set` on `−1` fields) the
   loaded stage file IS the output — do not delete it before renaming (a
   bug caught and fixed by `test_usage_repoint_only_if_set_semantics`).
5. `FamilyDoc.finalize()` writes the FULL type table into the self-Family;
   an ANNOTATION embedded document's specimen carries an EMPTY table — our
   documents keep their single named type (divergence H6, un-viewer-tested).

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/famgen/factory.py` / `src/rvt/content.py` (asset-forge owner /
  content owner):** promote `parse/assemble/insert_content_documents` +
  `build_family_save_unit` / `splice_save_unit` /
  `author_embedded_adocument` into `rvt/content.py` + `rvt/famload.py`'s
  registry code beside them — three tools now import the factory's private
  loader half (the triage stream, this stream, the parallel L4/L5 loader).
* **`src/rvt/famgen/loader.py` (the parallel asset-forge L4/L5 stream):**
  consolidation, not a bug: `register_in_host_adocument`, the
  ContentTable-record / FamilyMgr-entry / ETD bodies, `survey_host`,
  `_appinfo_slot` are duplicated in `rvt/famload.py` by necessity (the file
  was live-edited during this session and could not be a dependency).  Once
  it lands, one shared `rvt/loading_core.py` (registrations + census +
  splice/verify) with two flavours (component: placement + connectors +
  symbol geometry; annotation: usage repointing + multi-family) removes the
  overlap.  Also flag for that stream: `Global/PartitionTable` needs no row
  (finding 2) and ETD should append only into an EXISTING category row
  (finding 7 — its `setdefault` creates rows the samples never have for
  untracked categories).
* **`src/rvt/validate.py` (validation stream):** the four-registry
  coherence rule (finding 1) as a consistency-layer check — it would have
  flagged R9b / R10b / the audited G0 (`famload.four_registry_census` is the
  reference implementation; the genesis-triage record proposed the same).
* **`src/rvt/famgen/skeleton.py` (family-skeleton owner):** (a)
  `CATEGORY_LABEL` lacks the seven annotation-head categories (our `.rfa`
  PartAtom labels fall back to `Category -2006020` — cosmetic; the label
  map is in `heads.CATEGORY_LABEL`); (b) `new_family_parameter` has no
  `ParamDefString` / `ParamDefYesNo` / `ParamDefFamType` variants (the sample
  head families use them for Name / Elevation / Filled / View Name / Ref /
  Arrow Type; ours use `ParamDefValue` with the string spec or omit the
  Yes/No + FamType params).
* **`tools/genesis_triage.py` (triage owner):** L2 imports
  `neutralise_referrers`, `remove_documents`, `_class_hist`, `validate`,
  `_residual_guid_hits` and `rvt_reduce.{build_state_v2, maxgc,
  _protect_history}` — worth a stable public surface (they are the coherent
  family-removal recipe every future replacement probe needs).
* **`tools/sync_plugin.py` (orchestrator):** the plugin-drift test will add
  `src/rvt/famload.py` + `src/rvt/famgen/heads.py` to its list — left for
  the post-integration sync run.

## Open questions (need the viewer / a decision)

* The five probe verdicts, read per §Reading (L1a → L1b → L3 → L2, then
  L3b).  Every branch of the tree is pre-built except the "L1b FAIL"
  branch (head CONTENT — detail-curve + label constructors, not built).
* **H1–H6** (each `.load.json` acceptance list): all-null embedded
  AppInfoManager; SerializedDummy symbol rep with empty geometry
  bookkeeping; no head shape / label; core-id / big2small minimality;
  current-episode load without a new History episode; the host blank-row
  FamilyTypeTable + our single-type embedded table.  Only the viewer
  answers them; a FAIL card message on L1a/L1b will point at one.
* Whether a loaded head family needs its family-scoped HOST children (the
  Autodesk host carries ~19 subcategory / font / attribute rows per head
  because its DOCUMENT references them; ours references none, so creates
  none) — un-probed; the specimen is rstbasic 1388846..1388864.
* The K-ladder verdicts themselves (K4 / KD1 / K3): if **K4 PASSES** this
  whole branch is deprioritised (families not required); L2 / L1b remain
  useful only for the head-substitution question.

## Proposed next tasks (orchestrator decides)

1. Upload L1a + L1b + L3 + L2 (one batch); read per §Reading; L3b /
   `head_level_head.rfa` as the pre-built follow-ups.
2. If **L1b FAILS**: the head-CONTENT stream — symbolic `CurveElem`
   (detail lines / arcs owned by the family plan view), `FilledRegion`, and
   the `TagNote` label bound to a parameter, reconstructed byte-exact from
   the smallest heads (rstbasic units 26 View Title / 34 Level Head / 17
   Section Head); then re-emit L1b / L3 through the SAME loader.
3. If **L3 PASSES**: fold the loader into the genesis-2 assembler as the
   family route of the base of record (`load_family_documents` on the
   candidate + `default_repoints`), retire the K4-FAIL question, and start
   the counsel item for the head families (they are 100 % ours).
4. Consolidate the two loaders (`rvt/famload.py` annotation flavour +
   `rvt/famgen/loader.py` component flavour) over one registration / census /
   splice core once the parallel stream lands (see §Diffs).
5. The four-registry coherence rule into `rvt.validate` (finding 1).

## Verification

* `.venv/bin/python -m pytest tests/test_famload.py -q` → **12 passed**
  (2.3 s): the twelve head builders + byte-exact round-trip; the embedded
  unit contract; `.rfa` emission + family-mode validation; the census on
  the sample (53/52/52/52) + the genesis base (1/0/0/0); the dry-run plan /
  roundtrip gate; a full load + repoint into G1_candidate with read-back of
  the usage field, the header deletion list and the host Family / symbol /
  surrogate / twin linkage; multi-family registry motion (+3 in all four);
  `only_if_set` semantics; the below-watermark refusal.
* Shape conformance: in L1a our loaded host `Family` decodes to the SAME
  field set / value types as the Autodesk head host Family beside it in the
  same file — 1 difference in 120+ fields (`m_trivialParamIds` list length
  0 vs 2, content); FamilyTypeTable = one blank `' '` row in both; identical
  cell / pointer classes.  Our new host records carry zero suspect strings
  (only our names, our GUIDs, our `revit.local.family:` param ids and format
  vocabulary — factory suspect scan).
* `.venv/bin/python -m rvt.famload --proofs` regenerates every deliverable
  and prints the ladder table; every `.rvt` = four-registry COHERENT +
  `verify_loaded_project ok` + `rvt_validate` VALID 0 errors (arbiter
  output in §7); every `.rfa` = read-back verified + family-mode VALID.
* Full suite (`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`,
  751 s): **663 passed, 3 failed** — all three failures pre-existing and
  outside this stream (see BRANCH STATE).

## §7 Arbiter output (this session, repo root)

```
.venv/bin/python tools/rvt_validate.py --quiet experiments/genesis/loader/L*.rvt
OK   experiments/genesis/loader/L1a_rstbasic_loaded_levelhead.rvt  errors=0 warnings=1
OK   experiments/genesis/loader/L1b_rstbasic_our_heads_active.rvt  errors=0 warnings=1
OK   experiments/genesis/loader/L2_K1_our_heads.rvt  errors=0 warnings=1
OK   experiments/genesis/loader/L3_G1_candidate_our_heads.rvt  errors=0 warnings=0
OK   experiments/genesis/loader/L3b_G1_candidate_our_heads.rvt  errors=0 warnings=0
```
The one warning on the sample-derived files is the sample's own pre-existing
extensible-storage decode gap (RebarShape / DataStorage; on the pristine
sample too); the G1-based probes are 0/0.  Family mode
(`rvt.famgen.skeleton.validate_family`) on all twelve `head_*.rfa`: VALID,
0 errors, 0 warnings (`heads_report.json`).

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files: `src/rvt/famload.py`,
`src/rvt/famgen/heads.py`, `tests/test_famload.py` (12 pass),
`docs/writer/family-loader.md`, `docs/inbox/genesis-loader.md` (this
file), and under `experiments/genesis/loader/`: `L1a_rstbasic_loaded_
levelhead.rvt`, `L1b_rstbasic_our_heads_active.rvt`, `L2_K1_our_heads.rvt`,
`L3_G1_candidate_our_heads.rvt`, `L3b_G1_candidate_our_heads.rvt` (each with
`<probe>.json` and, for the loads, `<file>.load.json`), the twelve
`head_<key>.rfa`, `heads_report.json`, `probes.json`.  Every emitted `.rvt`
= four registries COHERENT + arbiter VALID (0 errors) + walker / ECC / CRC /
stamps clean; every `.rfa` = family-mode VALID.  Full suite this session
(`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`, 751 s):
**663 passed, 3 failed** — the three failures are the pre-existing,
other-stream ones every recent record lists (`test_plugin_sync.py::test_
plugin_is_in_sync_with_source` = plugin-bundle drift, orchestrator's
`tools/sync_plugin.py` run; `test_provenance.py::test_G0_resource_refs_are_
counted` + `::test_G0_identity_dit_usernames_still_leak` = the stale G0
assertions genesis-2 already diffed); this stream's 12 tests are among the
663.  STOPPED AT READY — the L probes + the twelve
`.rfa` await the orchestrator's viewer gate; the head-CONTENT constructors
(needed only if L1b FAILS) and the loader consolidation with the parallel
asset-forge stream are the recorded next steps.

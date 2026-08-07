# GENESIS 2024 — THE REDUCTION LADDER: sample → B2024_K4

Stream: **genesis-2024-reduce** (2026-08-04).  Charter: mirror
`tools/genesis_2025.py` at the third release — re-run the certified recipe
(rstbasic → maxgc R-rungs → K3 usage-nulls → K4 family-free, four-registry
coherent) on Autodesk's Revit-2024 rst basic sample, gate EVERY rung on
validator-0-errors + `rvt.reduce_law.assert_edit_free` + the four-registry
census + release-detection = 2024, pin the 2024 format data, and stage the
viewer batch (nothing uploaded; the orchestrator uploads).

**DONE conditions met: B2024_K4 exists, validator-clean, law-clean,
four-registry coherent, detects as 2024; format facts pinned
(`docs/writer/format-2024.md`); batch staged
(`experiments/genesis2024/batch_28.json` + `probes.json`).**

Driver: `tools/genesis_2024.py` (subcommands ladder / k3k4 / formats /
stage / all).  Tests: `tests/test_genesis_2024.py` (34, all green).
Precedent this ladder leans on: verdicts #28 — the identical 2025 ladder
(genesis_2025.py) certified in ONE round, control included; the certified
2026 recipe transfers wholesale.

---

## 1. THE LADDER — every rung validator-0-errors + law-clean + censused + release-gated

**Sample chosen: `samples/2024/rstbasicsampleproject.rvt`** (sha256
`aab838f861e0473b…`, 6,602,752 B — the pinned SOURCES.md entry) — the same
lineage sample as the certified 2026 and 2025 ladders (rst basic; the
comparison means nothing on any other sample), and again the smallest of
the six.  Shape on load: 13,819 host elements, 31,842 ids file-wide, 53
save units = 52 embedded family documents — the SAME 52-document count as
the 2026 and 2025 rst samples.  Everything ran inside
`rvt.versions.reading` + the local-tag patch set via
`genesis_2024.release_context` (§4).  Seeds are the certified 2026 seeds
(`rvt_reduce.stage_seed_v2`), deletion is maxgc, the emitters are the
certified `rvt.reduce.delete_elements` / `genesis_triage.remove_documents`
— no new mechanism, third release running.

| rung | recipe | deleted | kept | size (B) | structural | validator E/W | reduce_law | units/CD/CT/FMguids | release |
|---|---|--:|--:|--:|:--:|:--:|:--:|:--:|:--:|
| R5_2024 | annotation + schedules (maxgc) | 5,279 | 8,540 | 5,914,624 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 | 2024, tags {0xe7c} |
| R6_2024 | + views except {3D}+Level 1 | 5,601 | 8,218 | 5,853,184 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 | 2024, tags {0xe7c} |
| R7_2024 | + unused types/materials/patterns | 6,843 | 6,976 | 5,455,872 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 | 2024, tags {0xe7c} |
| R8_2024 | + options/phases/links/topologies | 6,861 | 6,958 | 5,455,872 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 | 2024, tags {0xe7c} |
| R9_2024 | + family layer hosts + placed model | 10,160 | 3,659 | 3,272,704 | ok | 0/2 | **EDIT-FREE** | 53/52/52/52 | 2024, tags {0xe7c} |
| K3_2024 | R9 + loadable-family USAGE nulled | 0 (modify) | 3,659 | 3,272,704 | ok | 0/2 | modify: 9 edits, **exactly the neutralised set** | 53/52/52/52 | 2024, tags {0xe7c} |
| **B2024_K4** | K3 − family layer − ALL 52 docs, 4-registry | 364 elems + 52 units | **3,295** | **831,488** | ok | **0/2** | **EDIT-FREE** (vs K3) | **1/0/0/0 COHERENT** | **2024, tags {0xe7c}** |

Gate lines pasted (the driver aborts on any non-green, so these are the
actual outputs):

```
[R5_2024] deleted 5,279 / kept 8,540 | 5,914,624 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52 | release 2024 tags ['0xe7c']
[R6_2024] deleted 5,601 / kept 8,218 | 5,853,184 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52 | release 2024 tags ['0xe7c']
[R7_2024] deleted 6,843 / kept 6,976 | 5,455,872 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52 | release 2024 tags ['0xe7c']
[R8_2024] deleted 6,861 / kept 6,958 | 5,455,872 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52 | release 2024 tags ['0xe7c']
[R9_2024] deleted 10,160 / kept 3,659 | 3,272,704 B | structural=True validator_ok=True (errors 0) | law=EDIT-FREE | units 53 CD 52 CT 52 FM 52 | release 2024 tags ['0xe7c']
[K3_2024] layer 364 elements (13 loadable families); referrers edited 9; edits==neutralised: True; validator_ok=True (errors 0); units 53 CD 52 CT 52 FM 52; release 2024 tags ['0xe7c']
[B2024_K4] docs removed 52 (units 53->1, CD 52->0, CT 52->0, FM 50->9); layer deleted 364; 831,488 B; structural=True validator_ok=True (errors 0); law=EDIT-FREE; residual-guid-bytes 0; units 1 CD 0 CT 0 FM 0 coherent=True; release 2024 tags ['0xe7c']
```

* `reduce_law.assert_edit_free` for every REDUCTION rung, against the byte
  state of its parent over all three record seqs — all **EDIT-FREE,
  0 survivors edited, 0 ids added**.  The literal guard outputs:

```
[EDIT-FREE] R5_2024 vs rstbasic-2024 (sample): removed 5,279, added 0, common 26,563, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] R6_2024 vs rstbasic-2024 (sample): removed 5,601, added 0, common 26,241, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] R7_2024 vs rstbasic-2024 (sample): removed 6,843, added 0, common 24,999, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] R8_2024 vs rstbasic-2024 (sample): removed 6,861, added 0, common 24,981, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] R9_2024 vs rstbasic-2024 (sample): removed 10,160, added 0, common 21,682, SURVIVORS EDITED 0 (vindicated 0)
[EDIT-FREE] B2024_K4 vs K3_2024: removed 18,387, added 0, common 3,295, SURVIVORS EDITED 0 (vindicated 0)
```

  (The `common` universe counts EVERY save unit's records, so untouched
  embedded family documents are proven byte-identical too; B2024_K4's
  `removed 18,387` includes the 52 spliced documents' record ids.)
* **K3_2024 is the one declared MODIFY rung** (the M3-certified usage-null
  path; viewer-certified as a state in 2026 round 5 AND as K3_2025 in
  verdicts #28).  The law instrument (`check_reduction`, non-raising)
  proves: **removed 0, added 0, survivors edited 9, and the edited set ==
  the neutralised-referrer set EXACTLY**.  Edit classes = the certified K3
  signature verbatim: SectionAttributes ×2, LevelAttributes,
  ViewportAttributes, GridAttributes, InteriorElevAttributes, CalloutTag,
  StructSettingsElem, CopyWatchProperties.  Policy consulted:
  `reduce_law.law_policy().permits("neutralise-referrers",
  "research-probe")`; B2024_K4's verdict is only read with K3_2024's.
* Four-registry census every rung (save units − 1 == ContentDocuments ==
  ContentTable == FamilyMgr doc-GUIDs): 52/52/52/52 through K3;
  **B2024_K4 = 1 unit / 0 / 0 / 0**, **residual GUID bytes in
  Latest+ContentDocuments = 0**.  FamilyMgr keeps 9 entries with zero doc
  GUIDs — the curtain-wall SYSTEM families, exactly the 2026 and 2025 K4
  shape (FM 50→9 both years).
* Validator depth on B2024_K4: 12 streams, 23 partition blocks, 9,888
  records, 3,295 elements decoded, 42,134 refs checked, 1 decode failure
  (the pre-existing Extensible-Storage blob gap class every release shows)
  — 0 errors / 2 warnings, the same E/W class as the untouched samples in
  the versions parity table.
* **Release gate, NEW in this driver and recorded per rung** (`release_gate`
  in every report, part of the self-check): `versions.detect_release` = 2024
  on every emitted file AND the complete on-disk set of partition
  block-header tags is `{0xe7c}` (the 2024 SegmentMarker ordinal) with
  walker 0 errors — no 2026/2025 tag survived any emit.

### B2024_K4 vs the certified lineages — the divergence IS the schema drift

| | K4 (2026, certified) | B2025_K4 (2025, certified) | B2024_K4 |
|---|--:|--:|--:|
| elements | 3,342 | 3,333 | 3,295 |
| save units / CD / CT | 1 / 0 / 0 | 1 / 0 / 0 | 1 / 0 / 0 |
| loadable families removed | 13 | 13 | 13 (same names: section/level/grid/callout/elevation heads, A1 metric, M_View Title, M_HSS Square-Column, boundary condition) |
| embedded documents removed | 52 | 52 | 52 |

Class-census comparison B2024_K4 vs B2025_K4 (150 vs 153 classes): the
ONLY classes present in one and absent from the other are classes that do
not EXIST in the other release's schema — `ForgeConnectionTracker` (2024-only,
dropped in 2025) vs `BuildingOperatingYearSchedule` / `MEPNetworkDataElem` /
`STEPExportSettings` / `SheetsInSheetCollectionTracker` (introduced in 2025)
— and exactly ONE shared class differs in count (`GStyleElem` 1,442 vs
1,451, the per-release style-catalog drift).  **The K4 shape is
release-invariant modulo the schema's own class set** (pinned as
`test_k4_census_divergence_from_2025_is_exactly_schema_drift`).

## 2. THE 2024 FORMAT DATA — pinned (`docs/writer/format-2024.md`)

Machine-readable: `experiments/genesis2024/format_facts_2024.json`.
Highlights (full tables + the complete only-in lists in the doc):

* **Formats/Latest 2024**: 470,502 B, 4,492 classes, sha256 `0bfb947b…`
  (matches the `rvt.versions` pin; byte-identical across all six 2024
  samples — re-verified).
* **Class diffs, BOTH newer releases** (by NAME, all three schemas parsed
  fresh): 2025→2024 = 4,477 shared / **4,403 renumbered** / 74 same-ordinal
  / 123 only-2025 / 15 only-2024; 2026→2024 = 4,464 shared / 4,390
  renumbered / 74 same-ordinal / **226 only-2026** / 28 only-2024.  The
  2026-only set vs 2024 is a superset of the 2026-only set vs 2025 (the
  conductor catalog + numbering machinery included) — a 2024 constructor
  may emit none of them.
* **ESSchemaStorage / product corpus — counsel C4 now covers THREE
  releases' corpora**: 2024 = 1,161 (typeid,json) pairs in two tables
  (880 unit + 281 spec/parameter-group), **890,500 B**, corpus sha256
  `f879bf3d7283f799…`, byte-identical across all six 2024 samples.  The
  same instrument re-measured the references: 2025 = 1,174 pairs /
  1,120,410 B `5331797d…` and 2026 = 1,315 pairs / 1,333,340 B `99554c01…`
  — BOTH byte-equal to the 2025 stream's independent measurements
  (cross-validated in `test_esschema_corpus_reference_rows_match_the_2025_stream`).
  The corpora differ materially release-to-release: a 2024 writer carries
  the 2024 corpus, never a newer one.
* **Identity markers**: BasicFileInfo `Format: 2024`, build
  `20230308_1635(x64)` (matches the `rvt.versions` sample_build pin);
  ElemTable lead tag 0x583 (=ElemTable), footer tail class 0x901
  (=IdentifierSource), History lead tag 0x4ff — ordinals, resolved by
  name, round-trip automatically.
* **History terminal check — the 2662 finding holds from the 2024 side**:
  the Global/History upgrade-version list is **IDENTICAL across
  2024/2025/2026** (190 entries, ends 2662; `identical_across_releases:
  true`), and the ADocument class's schema `version` stamp is **2662 in
  all three releases' own schemas**.  2662 is NOT a release marker; the
  release authority is BasicFileInfo `Format:`.  A 2024 writer writes 2662
  unchanged — exactly as format-2025.md predicted.

## 3. THE STAGED VIEWER BATCH — `experiments/genesis2024/` (batch 28)

Nothing was uploaded.  Staged through the `tools/probe_batch.py` gate
(`stage_batch`, batch_n=28 — see the numbering note below):

| order | file | kind | base (declared in probes.json) |
|--:|---|---|---|
| 0 | `CTRL_rstbasicsampleproject_b28.rvt` | control | byte-identical copy of `samples/2024/rstbasicsampleproject.rvt` (md5-verified == the 2024 sample, != the 2025 one, != the 2026 one) |
| 1 | `R9_2024.rvt` | candidate-base | the 2024 sample |
| 2 | `K3_2024.rvt` | candidate-base | `reduce/R9_2024.rvt` |
| 3 | `B2024_K4.rvt` | candidate-base | `reduce/K3_2024.rvt` |

* **Every 2024 file is a candidate-base** — nothing 2024 is in the ledger;
  certification cascades down the lineage (per-entry if_PASS/if_FAIL in
  `probes.json`; a parent FAIL voids its children).
* **The control doubles as the 2024 oracle question** ("does the viewer
  read 2024 uploads at all?"): Autodesk's own untouched 2024 bytes —
  certified by construction (`probe_batch` `sample` status).  Control FAIL
  ⇒ every other verdict VOID.
* **The spine only** (R9 → K3 → B2024_K4), NOT R5: verdicts #28 proved the
  recipe transfers wholesale (the 2025 round certified R9/K3/K4 in one
  go), so the round spends its slots on the lineage spine; **R5..R8_2024
  are built, gated and on disk** (`experiments/genesis2024/reduce/`) for
  bisection if R9_2024 fails.
* `probes.json` lineage verified resolvable via `probe_batch.resolve_base`
  from BOTH the staged copies and the reduce/ originals.  Basenames are
  collision-free vs every prior upload (`R9_2024.rvt` vs 2025's
  `R9_2025.rvt` vs 2026's `R9.rvt`).
* Canonical paths for the ledger + future base declarations: the
  `reduce/` originals (`experiments/genesis2024/reduce/B2024_K4.rvt`,
  sha256 `505ed303f9c9e89e…`, 831,488 B); a 2024 substitution ladder
  declares `"base": "experiments/genesis2024/reduce/B2024_K4.rvt"`.
* **Batch-numbering note (cross-stream race, resolved)**: manifests on disk
  only reached batch_17, but rounds 18–27 left `CTRL_*_b<n>` controls
  without manifests, so scanning manifests alone would have re-issued a
  used number.  `genesis_2024.global_next_batch_number` scans BOTH
  (all `experiments/**/batch_*.json` + all `CTRL_*_b<n>.*` names) → 28.
  While this stream was staging 28, the 2025 compose fleet staged batch 29
  (`experiments/genesis/subst_k4_2025/compose/batch_29.json`) — no
  collision; the numbering invariant is UNIQUENESS, not "newest", and the
  test asserts exactly that.

## 4. THE CONTEXT — generalized, not duplicated blindly

`genesis_2024.release_context(src)` is `genesis_2025.context_2025` with
the source file as the only parameter: `rvt.versions.reading(src)` + the
SAME seven module-local framing-tag patches (rvt.reduce BLOCK_TAG /
BLOCK_TRL_TAG, rvt.manipulate BLOCK_TAG/TRAILER_TAG, rvt.commit +
rvt.writer BLOCK_TRL_TAG, rvt.famgen.factory CD_SEPARATOR/CD_END_RECORD,
rvt.adocument._DECODER rebound to the file's schema).  Nothing in the
patch set is release-specific — every value derives from the ACTIVE
ordinals — so the helper works unmodified for 2024, 2025 and any future
release (`test_release_context_is_release_general` proves it binds 0x0ED9
on the 2025 sample).  `context_2024` = release_context + a wrong-release
refusal (asserts detect_release(src) == 2024 and the active ordinals ==
the pinned 2024 table).

### Proposed cross-territory diffs (NOT applied; orchestrator/owners merge)

1. **genesis_2025.py adopts the shared helper** (one import + one deletion
   — its `context_2025`/`_LOCAL_TAG_PATCHES` become):

```python
# tools/genesis_2025.py
from genesis_2024 import release_context, _LOCAL_TAG_PATCHES  # shared

@contextmanager
def context_2025(src: str = SRC):
    with release_context(src) as ords:
        yield ords
```

   (Or move `release_context` + `_LOCAL_TAG_PATCHES` into a neutral
   `tools/genesis_context.py` both import — naming is the owners' call;
   the semantics are already identical, byte-for-byte the same patch list.)
2. **The permanent fix stays the versions stream's**: fold the local-tag
   patches into `rvt.versions.activate` so `reading()` covers the emit
   path (the sketch in docs/inbox/genesis-2025-reduce.md §4 stands
   unchanged; this stream re-confirms the seven entries are sufficient at
   a third release — the release gate proves no baked tag leaked).
3. **Plugin drift observed, NOT mine (and moving)**: `tools/sync_plugin.py
   --check` reported different drift sets over the session as the fleet
   worked (`src/rvt/genesis/{port2024,y2025_b}.py` at 23:20; at
   record-close `src/rvt/frontdoor/standalone.py`, `src/rvt/famgen/
   loader.py`, `tools/ifc_intent.py`) — all SIBLING streams' files,
   mid-flight; their owners (or the orchestrator at merge) run
   `python tools/sync_plugin.py`.  This stream added NO src/ or
   plugin-bundled files, so it introduces zero drift of its own.

## 5. PROPOSED KNOWLEDGE.md / counsel touch-ups (orchestrator merges)

1. Counsel C4 (per-release product corpora): now THREE pinned constants —
   2024: 1,161 pairs / 890,500 B `f879bf3d…`; 2025: 1,174 / 1,120,410 B
   `5331797d…`; 2026: 1,315 / 1,333,340 B `99554c01…` (§2 above,
   format-2024.md §3 the authoritative table).
2. docs/writer/genesis-2025-plan.md portability table: the 2024 column is
   now measured (4,492 classes, 123 classes 2025-only vs 2024, 226 classes
   2026-only vs 2024, 74 ordinal-stable names vs either newer release).
3. `rvt.versions.KNOWN_RELEASES[2024].creation_certified` stays **False**
   until the orchestrator's viewer round reads out batch 28; on a
   B2024_K4 PASS the 2024 campaign proceeds to constructor retarget +
   substitution (the G25-3/4 pattern at 2024 — `src/rvt/genesis/
   port2024.py` already appeared in the port stream's territory).

## 6. TESTS + SUITE

* `tests/test_genesis_2024.py` — **34 tests, all green, 0.77 s**
  (context patch/restore + wrong-release refusal + release-generality;
  per-rung validator/structural/law verdicts; per-rung RELEASE gate
  (detect=2024, tags {0xe7c}); K3's edits==neutralised invariant;
  four-registry coherence incl. B2024_K4 = 1/0/0/0; B2024_K4 detects as
  2024 + walks clean with 1 unit; K4-census divergence == schema drift;
  staged control byte-identity against ALL THREE releases' samples; batch
  number uniqueness; probes lineage resolvable; format pins match
  `rvt.versions`; both class diffs; corpus cross-validation vs the 2025
  stream's facts; the 2662 release-stability finding incl. the ADocument
  schema-version stamp).  Every artifact-dependent test skips cleanly off
  this machine.
* Full suite: see SUITE RESULT below.

## SUITE RESULT

**Full suite: 1,662 passed, 9 failed, 2 skipped, 0 collection errors**
(all 85 files under `testpaths=tests`, canonical flags
`-q --continue-on-collection-errors`).  Two single-process attempts of the
root run were SIGKILLed mid-run with no summary (~41% and ~30%; exit 137;
~43 GB RAM free at the time — the kills coincide with the 2025/2023
compose-fleet's concurrent orchestration, not OOM), so the counted run was
executed as the SAME collection per-file serially with kill-retry
(session scratchpad `/private/tmp/claude-502/-Users-ck-dev-things/
91c616fc-3cee-49e7-be61-74bc4edd8fdb/scratchpad/`: `run_suite_chunked.sh`,
per-file summaries in `suite_2024_chunked.txt`, summed by
`tally_suite.py`) — zero files needed a retry once run in small units.

* `tests/test_genesis_2024.py` (this stream): **34 passed** — in the
  counted run AND standalone after the final artifact regeneration.
* The versions-stream baseline (1,284 passed / 4 failed / 5 skipped /
  1 collection error, 19:49) has moved massively under today's fleet:
  **all five baseline defects now PASS** (test_engine collection,
  test_electrical, test_genesis_types, test_provenance ×2 — fixed by
  sibling streams), and the fleet added ~+340 passes beyond this stream's
  +34.
* The 9 current failures sit in SIX files, ALL other streams' territories,
  none reading this stream's files (grep-verified: no failing file
  references `experiments/genesis2024` or globs it):
  `test_famgen_loader` (1), `test_frontdoor` (2),
  `test_frontdoor_standalone` (2), `test_genesis_assemble` (1),
  `test_surface_perf` (2, a wall-clock bound under fleet load),
  `test_y2025_a::test_probes_manifest` (KeyError 'certified_by' in that
  stream's own manifest).  Attribution corroborated by
  `tools/sync_plugin.py --check` at record-close: the drifting files are
  exactly `src/rvt/frontdoor/standalone.py`, `src/rvt/famgen/loader.py`,
  `tools/ifc_intent.py` — the siblings are mid-rewrite on the very modules
  whose tests fail.  This stream edited NO existing source or test file
  (purely additive), so its delta is exactly its +34 passes.

## BRANCH STATE

* Repo `/Users/ck/dev/things/tekton` — no git branch work (repo has no
  commits; integration is the orchestrator's).
* NEW (this stream's territory, all additive):
  * `tools/genesis_2024.py` — the driver (release_context/context_2024,
    ladder, K3/K4, per-rung release gate, format facts, collision-free
    batch numbering, staging)
  * `experiments/genesis2024/reduce/{R5,R6,R7,R8,R9}_2024.rvt+.json`,
    `K3_2024.rvt+.json`, `B2024_K4.rvt+.json` (sha256 B2024_K4
    `505ed303f9c9e89e…`, 831,488 B)
  * `experiments/genesis2024/{probes.json, batch_28.json,
    CTRL_rstbasicsampleproject_b28.rvt, R9_2024.rvt, K3_2024.rvt,
    B2024_K4.rvt}` (the staged batch),
    `experiments/genesis2024/format_facts_2024.json`
  * `docs/writer/format-2024.md`
  * `tests/test_genesis_2024.py` (34 green)
  * this record
* Touched OUTSIDE territory: **NOTHING** — no `src/rvt/**`, no existing
  tool, test or doc edited; genesis_2025.py NOT edited (the shared-helper
  adoption is a PROPOSED diff, §4).  The concurrent 2025 compose fleet's
  territory (`experiments/genesis/subst_k4_2025/**`, `tools/
  genesis_compose_2025.py`, `src/rvt/genesis/{port2024,y2025_b}.py`,
  batch 29) untouched; no file collisions (their batch is 29, mine 28).
* DONE check: **B2024_K4 validator-clean (0 errors) + law-clean
  (EDIT-FREE vs K3_2024; every reduction rung EDIT-FREE vs its parent) +
  four-registry coherent (1/0/0/0, residual GUID bytes 0) + release gate
  2024/{0xe7c} on every rung; format facts pinned (schema + class diffs vs
  2025 AND 2026 + three-release corpus + History-2662 check); batch
  staged with the untouched-sample control.**  STOP at READY: nothing
  uploaded, nothing certified — B2024_K4 is a CANDIDATE base until the
  orchestrator's viewer round reads out;
  `KNOWN_RELEASES[2024].creation_certified` stays False.

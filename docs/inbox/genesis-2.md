# genesis-2 — workstream record (THE G1 CANDIDATE: our own ADocument, 2026-08-03)

Charter: synthesize OUR OWN `ADocument` (`Global/Latest`) for G0 and produce the
first **G1 CANDIDATE** — the ADocument re-encoded via the (already existing)
codec with (a) every project-data string ours, (b) the element-id registries
rebuilt to reference EXACTLY the elements G0 contains (zero dangling), (c) the
Forge JSON corpus handled per the landmarks' determination, (d) our
BasicFileInfo / DIT identity; MEASURE with the provenance ledger v2 and the
validator; write `docs/writer/genesis-status.md` v2; save `G1_candidate.rvt`
plus the max-safety (`G1a`) / max-purity (`G1b`) variants and list them for
viewer testing.  Serves TRACKER P0 gate **G1 GENESIS BASELINE** (sub-gates
G1a ADocument encoder — closed by the codec + this construction; G1b own
content — landed via D1; G1c resource ids — dispositions applied by the house
standard; G1d multi-baseline + stream ledger — the certifying instrument).

Territory touched ONLY: `tools/genesis_assemble.py` (v2: house-standard D1
integration, the DIT username scrub in the own-save, the GENESIS-2 section),
`tests/test_genesis_assemble.py` (one assertion adapted to the house-standard
manifest), `tests/test_genesis2_adocument.py` (new), `experiments/genesis/G1*`
(+ the rebuilt `G0*` ladder, `G0_safe.rvt`), `docs/writer/genesis-status.md`
(v2), this file.  NO `src/rvt/*` module edited (the codec, house standard,
identity, provenance and validator modules are read-only imports); NO browser /
viewer use — files are LISTED for the orchestrator's certification queue.

## Result in one screen

The full analysis is `docs/writer/genesis-status.md` (v2).  Headline:

* **`experiments/genesis/G1_candidate.rvt` (331,776 B) — validator VALID
  (0 errors / 0 warnings), 234-element house-standard inventory, and a
  `Global/Latest` (the serialized ADocument) WE CONSTRUCT**: the sample's
  10,175 dangling element-id references purged to ZERO (schema-typed walk over
  14,652 ElementId leaves; independently confirmed by an i64 byte-window scan —
  2 residual windows, both proven coincidences), the registries repopulated to
  index exactly our inventory (214 of our 234 ids appear in the object by the
  byte scan — category / graphic-style catalogue, per-class trackers, the
  positional singleton table, the view index, level→plan / view→sketch-plane
  maps, default-type map, custom-element type map, system-family index; the
  other 20 are classes no sample ADocument references), every sample name cache / user map /
  link-reconcile dataset / content record emptied, the "saved by" list reduced
  to the product build constant, identity ours in BasicFileInfo AND every save
  episode (ledger identity layer: no violations).
* **The v2 gate verdict on the candidate is FAIL — honestly, and now fully
  ATTRIBUTED**: 135 machinery-class element clones (the own-content stream's
  NO-FREE-CHOICE population), 1,346,347 identical `Global/Latest` bytes of
  which 1,333,338 = the Autodesk unit-schema corpus (product data identical in
  all six samples; counsel C4-class per docs/writer/latest-regions.md — the
  landmarks determination (c) "regenerable from a public repo" is FALSE, so
  the corpus is CARRIED + FLAGGED as the residual) and ~13 KB shared format
  machinery, 7,400 resource refs (the corpus's typeIds + required tokens),
  lineage advisories, `Formats/Latest` = counsel C4.  `G1b.rvt` (corpora
  emptied) demonstrates the corpus is the entire byte residual: 11,776
  identical Latest bytes, 107 refs, 16.6 % identical excluding the schema.
* Four validator-VALID viewer probes on disk (`G1a` max-safety = the
  zero-dangling coherence probe; `G1_candidate`; `G1b` max-purity;
  `G1_candidate_safe` over the `scrub="safe"` content twin), each isolating one
  hypothesis (`docs/writer/genesis-status.md` §7).

## Deliverables

| item | path | state |
|---|---|---|
| pipeline v2 (D1 house standard, DIT username scrub, registry-map derivation, schema-typed purge engine, inventory, 3 authoring modes, G1 stage, byte-scan / census verification, ledger-v2 certification) | `tools/genesis_assemble.py` | done, reproducible (~45 s full) |
| the G1 set | `experiments/genesis/{G1a,G1_candidate,G1b,G1_candidate_safe}.rvt` | all VALIDATE 0/0, self-decode ok |
| the rebuilt element ladder + safe twin | `experiments/genesis/{G0a,G0b,G0c,G0d,G0,G0_safe}.rvt` | all VALIDATE 0 errors |
| certification | `G1_validate.json`, `G1_provenance.json`(+`.txt`), `G1_gate.json`, `G1*_authoring/_provenance/_validate.json`, `G1_baseline_G0_provenance.json` | done |
| derived registry semantics (position / enum / category / GUID tables) | `experiments/genesis/G1_registry_maps.json` (`--only maps`) | done |
| pipeline records / manifest | `G1_pipeline.json`, `G0_pipeline.json`, `G0_manifest.json` | done |
| tests | `tests/test_genesis_assemble.py` (11), `tests/test_genesis2_adocument.py` (9, new) | 20 pass |
| status v2 (human deliverable) | `docs/writer/genesis-status.md` | done |

Reproduce: `.venv/bin/python tools/genesis_assemble.py` (repo root).

## How each charter item was met

* **(a) every project-data string OURS** — the name caches / user maps /
  LB dataset / last-used parameter names / colour-fill caches are emptied
  (a fresh document has none); the string census in each authoring report
  shows the sample watch-list (rooms, sheets, assemblies, materials, usernames)
  17 groups → 0 in the candidate.  What text remains is product vocabulary
  (updater ids, folder names, 'WireSizes.xml', numbering-partition tokens)
  and, in the candidate only, the Forge corpus (flagged).
* **(b) registries rebuilt to reference exactly G0's elements** —
  `_populate_registries` + the frozen `G1_registry_maps.json` (semantics
  DERIVED from five samples: the singleton position table is 72/72 identical
  across samples; the ElementTypeGroup and category enums are stable; parallel
  arrays verified equal-length in every sample).  214 of our 234 ids are
  indexed (byte scan; the id-key census reports 205 because the default-type
  map's values sit under a generic key); the other 20 (Viewer / Viewport /
  ExtentElem / ModelClipBox / LightSchemeElement / FontElem / GeoSite /
  ProjectPhase) are classes the ADocument never references in any sample.
* **(c) the Forge corpus** — landmarks determination: (a) identical product
  data / (c) NOT regenerable from a public open-source repo → per the task's
  fallback ladder and the probe rule (no viewer verdict on the P3a/P3b probes
  yet → only the length-preserving rename P1 assumed safe): **carried and
  FLAGGED as the residual** in the candidate; **emptied** in G1b (the file
  that measures whether it is load-bearing); reported separately (counsel
  C4-class, beside `Formats/Latest`) in the gate summary — the instrument's
  `stream-modified-lineage` blocking entry on Global/Latest is 99.0 % this
  corpus (G1b: 11,776 B without it).
* **(d) our BasicFileInfo / DIT identity** — BasicFileInfo was already ours
  (G0 own-save); genesis-2 adds the V32 username scrub to the own-save (every
  DIT episode signed `rvt-writer`) — the ledger identity layer now passes on
  every emitted file (it was the one identity violation in the audit's run).

## Evidence log (measured this session)

### E1. The ADocument's dangling references are its LIVE element index — and are gone
Schema-typed walk (`AdocGraphEditor.iter_leaves`, parallel with the archive
class map, every AppInfo body + ContentTable + NOBLE): **14,652
ElementId-typed leaves in G0's ADocument, 10,175 referencing deleted sample
elements** (the landmarks' byte scan said 10,002 hits / 6,405 distinct — the
schema walk is the exact count and adds the `int64`-typed id keys of
`BasedOnTracker.m_nOriginalElemIdAsInt64` and the browser expanded-node
identifiers, which a field-name heuristic misses).  Purge: 8,892 registry
entries dropped whole, 138 positional slots nulled, 22 scalars invalidated.
Post-condition on every emitted tree: zero dangling ElementId leaves;
independent i64 window scan of the serialized payload against the union of all
six samples' ElemTable ids (≥ 4,700): **9,633 windows → 2** in the candidate,
both located and classified as coincidence (a `0x25` class id followed by
zero padding; a FILETIME/double fragment) — recorded in the record so no
future audit mistakes them for references.

### E2. Registry SEMANTICS are compiled-in constants (derivable, verified)
Derived per sample by attributing every registry id to its element class:
`UniqueElementsTracking.m_elemIds` position → singleton class: **72/72
positions identical across rst / rac / rme (+2 adv)** = a compiled-in
registration order → safe to repopulate positionally (our five singletons at
[2] ProjectInfo, [59] ElectricalSetting, [66] CableTraySizes, [67]
ConduitSizes, [74] AllProjectPhases).  `SymbolIdMgr.m_defElementTypeMap`
key = the ElementTypeGroup enum → class: 132/150 groups agree (disagreements
are only present-vs-absent).  `ElementTrackingData` category → class: 62/62
(symbols) and 63/65 (elems) agree.  BUT `AppInfoSystemFamiliesNames` keys
agree only **30/161** → they are DOCUMENT-LOCAL allocations, never reused
(fresh keys 0..14 for our 15 system families).  Custom-element data-type
GUIDs (from the MEP sample) are exactly the four conductor-cell types our
catalog carries + wire-conduit type + cable size.

### E3. Only anonymous (pid −1) holders live inside the registries
A scan of the whole graph: the ONLY positive-archive-pid holders are the 180
AppInfo slot objects (pids 2..181); weak references target 1 (the document)
×251, 152 (`NumberingAppInfo`) ×10, 173 (`AppInfoElementsAssociations`) ×3;
no back-references at all.  Because the purge never removes / reorders slot
objects and only drops container elements holding anonymous (−1) sub-objects,
every pid and weak reference stays valid — asserted by the encode→decode tree
equality on every file (a shifted pid would derail the re-decode).

### E4. The v2 gate residual is ENTIRELY corpus + machinery + lineage
Ledger v2 on all four G1 files + the new G0 (`G1_gate.json`,
`G1_baseline_G0_provenance.json`): the candidate's blocking Latest bytes
(1,346,347) minus the flagged corpus (1,333,338, measured in the authoring
report) = ~13 KB shared machinery — corroborated by G1b's 11,776 identical
Latest bytes with the corpora emptied.  Elements: 135 clones in the union over
six samples, class-by-class the own-content NO-FREE-CHOICE machinery (90 house
GStyleElem rows, view frames, conductor name-cells …); 99 created (69 with
max-similarity < 0.40).  Identity layer clean on every file.  Excluding the two
product corpora (schema + unit schemas), 17.2 % of the candidate's remaining
bytes are baseline-identical and every one is a lineage advisory or Latest
machinery — 0 in the elements / ElemTable / content / identity / metadata.

### E5. The two international-standard content variants read the same
`G1_candidate_safe.rvt` (candidate ADocument over the `scrub="safe"` house
standard): 140 clones vs 135 (the un-blanked asset descriptors read a shade
closer to the samples), 7,445 refs vs 7,400 — the fallback is measurably the
weaker file legally, kept only as the reader-tolerance bisection twin.

## Gotchas found (for KNOWLEDGE.md merge)

1. **The ADocument's element references are its LIVE indexes, not a
   graveyard** (confirms the landmarks stream): the category / graphic-style
   catalogue, per-class element indexes, positional singleton table, view
   index, default-type map — every one must be REGENERATED over the new
   inventory, not merely nulled; the purge alone (G1a) leaves a document
   object that indexes nothing.
2. **Positional and parallel registries exist and must never be compacted:**
   `UniqueElementsTracking.m_elemIds` (position = singleton kind, 72 fixed
   positions), `CategoryToIdMap.m_categoryIds/m_ids`, `SymbolIdMgr.m_paramSetKeys
   /m_paramSets`, `DBViewInfo.m_defaultTemplateIds`, plus the cross-sample-
   verified pairs in `G1_registry_maps.json:PARALLEL_GROUPS`.  Detection rule
   that never desyncs: null in place if the container is a listed positional
   field, is in a parallel group, or already contains a −1; otherwise drop the
   innermost enclosing container element.
3. **Sample element ids hide outside ElementId-typed fields:** as `int64`
   (`BasedOnTracker.m_nOriginalElemIdAsInt64`), as plain-int UI state
   (`BrowserOrganizationTracking.m_setExpandedNodes[].m_identifier`), and as
   TEXT (the `LB_Associations` reconcile rows) — a byte-level id scan is the
   only complete check; the schema-typed walk needs the name markers for the
   first two and the cache-emptying policy for the third.
4. **`AppInfoSystemFamiliesNames` keys are document-local** (30/161 agree
   across samples) — never treat them as an enum.
5. The landmarks' "Forge table 1 header i64 ownerElementId" was a byte-view
   mis-framing: the schema decode of `ESSchemaStorage` has no such field (the
   40 bytes belong to the previous FIFO body); the units element is indexed
   only by `UnitsTracking.m_unitsElemId`.
6. **A fresh document's ADocument is mostly EMPTY registries**: after the
   purge + our repopulation the Latest payload without the corpus is ~26 KB
   (G1b), i.e. the 1.59 MB stream was ~84 % corpus + ~14 % sample indexes /
   caches + ~2 % machinery.
7. Every reader-accepted file to date carried the INHERITED save-history
   lineage; minting a single-episode lineage couples History / DIT /
   PartitionTable / Contents AND the `Partitions/<N>` stream name (N = the DIT
   increment counter − 1) — an untested coupling deliberately kept out of the
   ADocument question.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/adocument.py` (adoc-grammar stream):** the purge engine and the
  registry semantics belong beside the codec — suggest lifting
  `AdocGraphEditor` (schema-typed leaf walk + purge) and the transform set
  into `rvt.adocument` (`purge_dangling_ids(tree, live_ids)`,
  `author_document(tree, inventory, maps, mode)`), and adding the byte-scan
  post-condition to its proof builder.  Also: `element_ids()`'s key-name
  heuristic misses `m_DBDrawingsIndex` / int64 id keys — the schema-typed
  walk is the accurate replacement.
* **`src/rvt/validate.py` (validation stream):** the adoc-grammar record's
  proposed ADocument decode + dangling-count layer would have flagged G0
  (6,405 dangling) and passes on every G1 file — the assembler's post-conditions
  duplicate it today.
* **`src/rvt/provenance.py` (provenance stream, D3 follow-up):** the ledger
  now blocks on the Forge corpus bytes and the required-token typeIds; once
  counsel classifies them, a `product_constant_regions` mask (like the schema
  stream's C4 treatment) and the definition-field comparator for machinery
  classes would let the gate express the ruling instead of the raw byte /
  shingle counts.  The candidate is the population to design them on.
* **skeleton / systemtypes streams:** the 67 missing document-settings
  singletons + `PenWidthTableElem` + `BrowserOrganization` (§5.2 of the status)
  — the constructor queue if G1a fails while G0_A0 passes.
* **orchestrator:** `python tools/sync_plugin.py` (the shared, pre-existing
  plugin-drift test — this stream added no `src/` module).
* **`tests/test_provenance.py` (provenance stream) — two STALE assertions**
  pinning the pre-genesis-2 G0's now-retired defects, both of which this
  stream was chartered to fix (the DIT-username scrub was requested of the
  assembler by the provenance-v2 record itself; the asset-library descriptors
  were dropped by the own-content dispositions).  Exact diff for their owner:

  ```diff
  --- a/tests/test_provenance.py
  +++ b/tests/test_provenance.py
  @@ def test_G0_resource_refs_are_counted():
       assert rr["total_refs"] > 5000                     # thousands of Forge typeIds
       assert rr["by_pattern"]["forge-typeid"] > 5000
  -    assert rr["by_pattern"].get("asset-library-fbx", 0) >= 1
  +    # genesis-2 (own-content D1): the assetlibrary_base.fbx descriptors are
  +    # dropped from OUR records; the corpus typeIds + required tokens remain
       assert rr["elements_with_refs"] >= 1               # OUR records carry some too
  @@ -def test_G0_identity_dit_usernames_still_leak():
  +def test_G0_identity_dit_usernames_are_scrubbed():
  -    """... its DocumentIncrementTable still carries the sample's employee
  -    usernames — the ledger must say so (the writer's V32 scrub post-dates G0.rvt)."""
  +    """genesis-2: the own-save signs EVERY DIT episode with our username
  +    (the V32 scrub, now in the assembler) — no username violation remains."""
       ...
  -    assert "DocumentIncrementTable.username" in fields
  +    assert "DocumentIncrementTable.username" not in fields
  ```

## Open questions (need the viewer / a decision)

* Does the reader open **G1a** (zero-dangling coherence, everything else
  reader-accepted-shaped)?  This is THE genesis-2 question.  Then G1_candidate
  (our full document object), then G1b (is the corpus load-bearing?).
* Counsel: the Forge unit-schema corpus (C4-class), `Formats/Latest` (C4), the
  machinery-class element classification (135 elements, listed), the
  required-token identifiers incl. the `'Data generated by Autodesk® Revit®'`
  save-unit banner (own-content §5), the authoring / build strings (C1).
* Is a document with no PenWidthTable / no system-navigator view / 5 of 72
  settings singletons acceptable to the reader?  (Not measurable without the
  viewer; the missing list is the constructor backlog.)
* The minted single-episode lineage (History = [our episode], DIT = [our
  record], `Partitions/0`?) — the next dedicated probe once a G1 file passes.

## Proposed next tasks (orchestrator decides)

1. **Viewer-test the four G1 files** in the order of §7 of the status; the
   first PASS is the genesis-2 base of record and the last Autodesk stream
   (the ADocument) is retired as an engineering block.
2. **Counsel memo** with the four named corpora / populations above; the
   candidate is the measured file to attach.
3. If G1a FAILS: run the latest-probes stream's `P0_control` / `G0_A0` (pure
   re-encode) to split codec-vs-content, then the settings-singleton
   constructors (systemtypes / skeleton).
4. Lift the purge/authoring engine into `rvt.adocument` (proposal above) so
   `spec_to_rvt` / the job runner author their own ADocument on any template —
   the same three modes generalize (template purge → our registries).
5. The minted-lineage probe (History/DIT/PartitionTable/Contents/partition
   name) as its own one-hypothesis rung on top of the first passing G1 file.

## Full-suite result at handoff

`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle` (615 s) →
**599 passed, 3 failed**.  This stream's tests: `tests/test_genesis_assemble.py`
11/11 + `tests/test_genesis2_adocument.py` 9/9 (34/34 with
`tests/test_adocument.py`, no skips).  The three failures, none in this
stream's territory:
1. `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source` — the
   pre-existing plugin-bundle drift every recent record reports (fix =
   `python tools/sync_plugin.py`, orchestrator-run; this stream added no
   `src/` module and contributes nothing to the drift);
2. `tests/test_provenance.py::test_G0_resource_refs_are_counted` and
3. `tests/test_provenance.py::test_G0_identity_dit_usernames_still_leak` — the
   two STALE provenance-stream assertions above, which pin exactly the G0
   defects genesis-2 was chartered to remove (they PASS on the previous
   G0.rvt and would pass again only by re-introducing the leak); diff for
   their owner given above.

BRANCH STATE: no VCS (plain directory); all work is uncommitted files at the
paths above — `tools/genesis_assemble.py` (v2), `tests/test_genesis2_adocument.py`
(new), `tests/test_genesis_assemble.py` (1 assertion adapted),
`experiments/genesis/{G0a,G0b,G0c,G0d,G0,G0_safe}.rvt` (rebuilt),
`experiments/genesis/{G1a,G1_candidate,G1b,G1_candidate_safe}.rvt` (new) +
`G1_validate.json`, `G1_provenance.json/.txt`, `G1_gate.json`,
`G1_pipeline.json`, `G1_registry_maps.json`, `G1_baseline_G0_provenance.json`,
`G1*_authoring/_provenance/_validate.json`, `G0_manifest.json`,
`G0_pipeline.json`, `docs/writer/genesis-status.md` (v2), this file.  Every
emitted `.rvt` validates 0 errors / 0 warnings; every G1 ADocument re-decodes
to the authored tree; the candidate's v2 gate reading = FAIL with a fully
attributed residual (corpus / machinery / lineage / counsel).  READY.

# genesis-assembler — workstream record (THE FIRST GENESIS CANDIDATE, 2026-08-03)

Charter: compose the FIRST GENESIS CANDIDATE `experiments/genesis/G0.rvt` — a
valid Revit 2026 project with NO Autodesk-authored expression, or the closest
achievable approximation with an honest gap list — from the four excavation
streams' deliverables (genesis-reduction, provenance, systemtypes, skeleton).
Serves TRACKER P0 gate **G1 GENESIS BASELINE**.

Territory touched ONLY: `tools/genesis_assemble.py` (new),
`tests/test_genesis_assemble.py` (new), `experiments/genesis/` (G0 ladder +
reports), `docs/writer/genesis-status.md` (new), this file. NO protected
`src/rvt/*` module, NO existing test, NO orchestrator-owned file, NO other
stream's deliverable was edited (the two defects found in others' code are
recorded below as exact diffs). No browser used; viewer-test files are LISTED,
not tested.

## Result in one screen

The full analysis, tables and the ordered path to zero are in
**`docs/writer/genesis-status.md`** (the human deliverable). Headline:

* **`G0.rvt` (380,928 B) is validator-VALID (0 errors, 0 warnings) with an
  element inventory that is 100 % ours** — 205 elements built field-by-field
  by our constructors; **0 `autodesk-sample`, 0 `ours-modified`, 0
  `unmatched`, 0 embedded Autodesk family documents**; our own document GUID
  (History entry 0), author/username `rvt-writer`, our `ProjectInformation`
  and `TransmissionData`, an empty (canonical 14-byte) `ContentDocuments`.
* The reduction the charter asks for is exact and monotone across a
  five-rung, all-VALID ladder: `autodesk-sample` **3,022 → 165 → 165 → 0 → 0**
  (G0a → G0b → G0c → G0d → G0), family docs 14 → 0.
* The provenance gate still reports **FAIL — 139 gated `transitive-cloned`**.
  With zero sample elements present, all 139 are the *structural-similarity
  heuristic* firing on classes whose bytes are Revit **product-default
  machinery** (86 built-in object-style rows, view display satellites, the 5
  standard phase filters, UnitsElem, label templates) — the "format constant
  vs expression" classification question the ledger's own §5/§6.2 already
  routed to counsel, now measured as a concrete 139-element population.
* The one true remaining Autodesk stream is **`Global/Latest` (ADocument,
  1.59 MB inflated)**, carried verbatim, now referencing **6,175 dangling
  sample-lineage ids and 0 of ours** — plus the inherited save-history
  lineage. Retiring it = the ADocument codec (genesis.md §6.3). Whether the
  READER opens G0 anyway is the exact question the ladder measures.

## Deliverables

| item | path | state |
|---|---|---|
| the assembler (content composer + 5-stage ladder + certification) | `tools/genesis_assemble.py` | done, `--only content` / full-ladder modes, ~10 s |
| the candidate + ladder | `experiments/genesis/G0.rvt`, `G0a.rvt`, `G0b.rvt`, `G0c.rvt`, `G0d.rvt` | all VALIDATE 0 errors |
| certification | `experiments/genesis/G0*_validate.json`, `G0*_provenance.json` (+ `.txt` tables) | done |
| composition record (every element we author) | `experiments/genesis/G0_manifest.json` | 205 entries |
| pipeline record (stage-by-stage evidence) | `experiments/genesis/G0_pipeline.json`, `G0_streams.json` | done |
| tests | `tests/test_genesis_assemble.py` | 11 pass (10 unit + 1 end-to-end ladder) |
| status / gap analysis (human deliverable) | `docs/writer/genesis-status.md` | done |

Reproduce (repo root): `.venv/bin/python tools/genesis_assemble.py`.

## Files the orchestrator should VIEWER-TEST (ordered by confidence)

Run the reduction stream's R-probes first (their record §5), then, in
order: `experiments/genesis/G0a.rvt` (insertion only), `G0b.rvt` (deep GC
delete), `G0c.rvt` (empty ContentDocuments), `G0d.rvt` (100 %-ours inventory,
inherited identity), `G0.rvt` (own identity/save). What each isolates and what
each PASS/FAIL means: `genesis-status.md` §7. NOTE (E5): no reduction depth is
viewer-proven — the "R4s = deepest viewer PASS" claim in the provenance and
skeleton records is NOT in `docs/acceptance-log.md`.

## Evidence log

### E1. The ledger's judgement of our constructors — measured before design
Ran `tools/provenance.py` on the types stream's three (never-ledgered) proof
files vs the MEP baseline. `T_walltype`: 10/12 `ours-created` (materials,
patterns, floor/roof/ceiling types); the 2 wall types read cloned **by
lineage only** (one referenced the SAMPLE's fill pattern 4; both hit the
compound-structure false positive — E6/D1). `T_settings`: voltage /
distribution / demand-factor types created; the parametric REPRODUCTIONS of
Autodesk's own load classes cloned at 0.80 (correct — they ARE Autodesk's
values); tiny CategoryElem/GStyleElem/FontElem companions land at exactly the
0.50 shingle threshold. `T_conduit_types`: reproductions of 'EMT'/'XHHW'/
conductor cells cloned 0.55–0.82; the sizes singletons and our conduit types
created. ⇒ **design rules: fresh ids above the watermark; OUR values, never a
reproduction of Autodesk's; total self-containment.**

### E2. The delete floor of a project is EMPTY (given no embedded documents)
On R10b, `maxgc(seed = all 3,022 host elements)` keeps only 165, and all 165
are pinned by elements INSIDE the 14 embedded family documents (their curve
elements / views / filled regions reference the HOST's object styles:
`GStyleElem <- CurveElem x156`, `<- DBViewDrafting x30`, `FillPatternElem
<- FilledRegionAttributes x27`; the docs' internal ids are remapped into
the host id space, KNOWLEDGE §Save units). Remove the documents ⇒ nothing
pins anything ⇒ every host element is deletable while staying
validator-clean. The category/style catalog the reduction stream never
seeded is fully releasable. (Second GC pass on G0c: kept set EMPTY.)

### E3. Our elements pin nothing and reference nothing outside themselves
`build_our_content` allocates all 205 ids from one source starting above the
lineage watermark and its pre-flight asserts 205/205 records round-trip
clean+byte-exact and **0 dangling references** (checked with the types
stream's `_element_refs`, plus a unit test that grafting a sample id into a
wall type IS caught). Cross-wiring is entirely internal: wall layers → our
materials → our patterns; `AllProjectPhases` phasing overrides → our four
phase materials + our patterns (no −1 unknowns, no sample refs); levels →
our UnitsElem + our GeoLocation; views → our phases/filters/view types/levels
/document sun. This is what makes both GC passes provably total (E2) and
what makes the lineage detector unable to fire in G0.

### E4. The own-save is coherent under the arbiter
`stage_own_save` = `streams_edit.record_save` (episode 1017 prepended, GUID
= our document GUID, DIT record 23, Contents counters, BFI increments/version
/GUIDs) + every ElemRec re-stamped `(creation, modified, user_modified) =
1017` (the whole inventory was born in the genesis episode) +
`identity.own_identity_model` (author/client/username `rvt-writer`, no path)
+ our `ProjectInformation` ZIP + our `TransmissionData`. `rvt_validate`
returns VALID: History count 1018 == max(modified_ep)+1; DIT id_pair
(1017,1018); BFI GUID == History[0]; increments 23 == DIT count. This
retires — for genesis files — the systemtypes D1 problem (identity scrub
breaking BFI-GUID/History coherence) by construction: the GUID we assert IS
the new episode's.

### E5. No reduction depth is viewer-proven (record correction)
`docs/acceptance-log.md` (the authoritative record, 29/29 + M-series
PASSes) contains NO entry for any `R*.rvt`. The provenance record's
"R4s (deepest that PASSED the viewer)" / `R4s_deepest_viewer_passed.json`
naming and the skeleton spec's "deepest PASS on record is R4s" are
uncorroborated. Only the M-series certifies DELETION as an accepted
operation. Every ladder rung (R- and G0-) is an untested probe.

### E6. Metadata streams carried live contamination + dangling ids
Beyond `BasicFileInfo`, two RAW streams still carried Autodesk-authored
sample metadata and an Autodesk employee's local paths (`C:\Users\<name>\…`):
`ProjectInformation` (Atom partatom XML: `<title>rstbasicsampleproject</title>`,
'Sample House', 'Client Name: Autodesk'; ZIP member NAMED with the employee's
temp path) and `TransmissionData` (`u32 code-unit count + UTF-16LE XML` of
external file refs — keynote table 86291, assembly-code table 1218726, a
Revit link 1250029: three element ids that NO LONGER EXIST in G0, plus
absolute Desktop paths). The identity policy scrubs only BFI. G0 now emits
its own (partatom XML from `PROJECT_META`, member `Revit<guid>.project.xml`;
TransmissionData with zero references). **This is a G2-class leak the
identity path should own generally** — see next tasks.

## Gotchas found (for KNOWLEDGE.md merge)

1. **The deletable floor of a project is bounded by embedded-document
   content, not by the host graph or the validator.** Embedded family
   documents' internal elements reference the HOST document's object
   styles / patterns / materials (their category ids are remapped into the
   host space on load), so those host rows are pinned until the documents
   are removed. Remove all units first (or GC twice) to reach empty.
2. **`ContentDocuments` in a family-free project = the 14-byte empty form**
   (`a3 03 00 00 00 00 ff ff ff ff 00 00 00 00`) — the unit-removal splice
   converges to exactly the `.rfa` empty form; a project stream CAN carry it
   (validator-clean; reader-open pending G0c).
3. **The provenance clone heuristic saturates on machinery-dominated
   classes.** Any element whose serialized bytes are mostly product-default
   shell (GStyleElem rows ~8 authored bytes in ~60; DBView satellites; the
   5 phase filters; UnitsElem; label-template classes) reads
   `transitive-cloned` (0.55–0.90) no matter who authors it. It is not
   evidence of copying; it is the "format constant vs expression" question
   (ledger §5). Companion elements (Font/Category/GStyle of a text type) sit
   at exactly the 0.50 threshold — a coin flip.
4. **`ProjectInformation` / `TransmissionData` are unowned identity
   surface** carrying the same employee-path contamination BFI had, and
   `TransmissionData` references ElementIds that reduction/genesis deletes.
   Any file our writer emits from a template should regenerate both (see
   next tasks; generators exist in `tools/genesis_assemble.py`).
5. **A genesis save can be coherently self-consistent by re-stamping ALL
   ElemRecs into the new episode** (creation = modified = user_modified =
   E): History count = E+1 = max(modified_ep)+1 holds and the story is true
   (the inventory was created in that save). `record_save` alone is NOT
   enough when no ElemRec carries the new episode.
6. **The "R4s viewer-passed" claim is uncorroborated** (E5) — treat the
   reduction ladder as untested; do not build on that assumption.
7. Small-integer ENUM fields masquerade as ids in generic reference walks:
   `DBViewType.m_systemFamilyIdx` (102/109/111 = view families) plus the
   compound-structure grid indices — see D1.

## Diffs / hooks proposed for files outside this territory (NOT applied)

### D1 — `src/rvt/provenance.py` (provenance stream): compound-structure false positives
The lineage extractor `_reference_ids` excludes geometry-index subtrees
(`_GEOM_PATH_TOKENS`) but not the type-definition topology subtrees, so
`WallType` compound-structure indices (segment `m_id`, `m_regionId`,
`m_layerId`, `m_regionToLayerMap`) and grid steps decode as ElementIds
2…8 and match a template's PenWidthTable (2) / fill patterns (3–8):
every compound-structure type in any file that keeps low-id sample
elements reads `transitive-cloned` via bogus lineage (why the types stream's
`T_walltype.rvt` wall types were flagged). Mirror the types stream's
exclusions (`genesis/types.py` `_NOT_ELEMENT_ID_SUBTREES` /
`_NOT_ELEMENT_ID_KEYS`):

```diff
--- a/src/rvt/provenance.py
+++ b/src/rvt/provenance.py
@@
-_GEOM_PATH_TOKENS = ("m_geomSteps", "m_faces", "m_edges", "m_geomTops",
-                     "Snapshot", "HistTable", "m_faceHist", "m_edgeHist",
-                     "m_GInfo", "m_pBBox")
+_GEOM_PATH_TOKENS = ("m_geomSteps", "m_faces", "m_edges", "m_geomTops",
+                     "Snapshot", "HistTable", "m_faceHist", "m_edgeHist",
+                     "m_GInfo", "m_pBBox",
+                     # type-definition topology (indices, not ElementIds):
+                     # compound-structure grid + wall/vertical-region structure
+                     "m_oVertRegStructure", "m_grid", "m_segRefFaceKeys",
+                     "m_regionToLayerMap")
+
+#: leaf keys whose integer values are indices / enums, never ElementIds
+_NOT_ID_KEYS = frozenset({"m_regionId", "m_segmentIds", "m_layerId",
+                          "m_idCounter", "m_layerFunction", "m_layerPriority",
+                          "m_embeddingType", "m_gstyleType", "m_categoryType",
+                          "m_paramId", "m_systemFamilyIdx"})
@@ def _reference_ids(doc, eid: int) -> List[Tuple[str, int]]:
-    return [(p, i) for p, i in refs
-            if i != eid and not any(t in p for t in _GEOM_PATH_TOKENS)]
+    out = []
+    for p, i in refs:
+        if i == eid or any(t in p for t in _GEOM_PATH_TOKENS):
+            continue
+        leaf = p.rsplit(".", 1)[-1].split("[")[0]
+        if leaf in _NOT_ID_KEYS:
+            continue
+        out.append((p, i))
+    return out
```

### D2 — `src/rvt/identity.py` (identity/commit path): own ALL identity streams
Extend the writer's identity ownership to `ProjectInformation` and
`TransmissionData` (E6/gotcha 4), so `commit_new_elements` / `spec_to_rvt`
never emit the template's project metadata + employee paths. Suggested
shape (the two generators already exist as `our_project_information_zip` /
`our_transmission_data` in `tools/genesis_assemble.py` and can be lifted):

```diff
--- a/src/rvt/identity.py
+++ b/src/rvt/identity.py
+def own_project_information(raw_zip: bytes, *, project_name: str,
+                            document_guid: str, filename: str = "",
+                            timestamp_iso: str = "") -> bytes:
+    """Regenerate the PartAtom project.xml ZIP from OUR project metadata
+    (scrub the sample's title/parameters and the employee temp-path
+    member name)."""
+    ...
+
+def own_transmission_data(raw: bytes, *, keep_refs: Sequence[int] = ()) -> bytes:
+    """Regenerate TransmissionData (u32 code-unit count + UTF-16LE XML),
+    dropping ExternalFileReferences whose ElementId is not in ``keep_refs``
+    (and scrubbing absolute local paths).  Empty when nothing external."""
+    ...
--- a/src/rvt/commit.py   (step 3, next to own_basic_file_info)
+        for meta in ("ProjectInformation", "TransmissionData"):
+            ...  # call the two functions above, gated like own_basic_file_info
```

### D3 — provenance ledger, follow-up to the counsel decision (design note, no diff)
A definition-field comparator for machinery-dominated classes and a
declarative per-class `machinery_bytes` mask (genesis-status.md §6 step 4),
so the "format constant vs expression" call is expressed in the instrument
once counsel makes it. Not a bug — a design decision for the ledger owner.

## Open questions (need the viewer / a decision)

* **Does the reader open G0** — a document whose `ADocument` references
  6,175 dead ids and indexes none of the (fully-ours) inventory? The single
  most valuable viewer test after R5. (G0a…G0d bisect the failure if not.)
* Does a PROJECT with the empty `ContentDocuments` open (G0c)? (Skeleton
  unknown #8; R9b/R10b's sibling question.)
* Classification: is Revit product-default machinery (object-style pens,
  units format table, phase-filter vectors, stock view display settings,
  label templates) "Autodesk-authored expression" or "format constant"?
  Decides whether G0's 139-element residual is a real gap or an instrument
  artefact — counsel + provenance owner (genesis-status §6.4).
* Should the genesis base ship the FULL 1,074-category object-styles table
  (available, withheld pending the above) or a house standard? Product /
  counsel decision, not engineering.
* Reader minima: is one level / one view / no PenWidthTable / no
  BrowserOrganization acceptable? G0 carries no pen-width table (neither
  constructor stream built one) — flagged for the systemtypes queue.

## Proposed next tasks (orchestrator decides)

1. **Viewer-test** the R-probes then the G0 ladder (this file §"VIEWER-TEST");
   record in `docs/acceptance-log.md`. Whichever G-rung is the last PASS
   becomes the practical genesis base of record.
2. **Stream: ADocument (`Global/Latest`) decoder→encoder** — the last
   Autodesk stream in G0 and the enabler of the bottom-up path
   (`minimal_globals` + `[our episode]` history). THE remaining engineering
   critical path (genesis.md §6.3), regardless of viewer results.
3. **Apply D1** (provenance false positive) and **D2** (own the two
   metadata streams in the identity path) — small, high-value, generalize
   what G0 does locally.
4. **Counsel + ledger owner: the classification decision** on
   product-default machinery, with the ledger follow-ups in D3. G0's 139-item
   list (`G0_provenance.json`) is the review population.
5. **Systemtypes queue for a complete base**: PenWidthTableElem, DimensionStyle
   (+companions), the MEP settings catalogs (RbsWireSizesElem …), and the
   annotation-default types — then a `G1` re-assembly using the same
   `tools/genesis_assemble.py` composer (add records to `build_our_content`).
6. **`tools/sync_plugin.py` once all streams land** (the shared, expected
   `test_plugin_sync` failure — `plugin/` is nobody's territory this wave;
   this stream added no `src/` module so it does not add to the drift).

## Full-suite result at handoff

`.venv/bin/python -m pytest tests -q` → **471 passed, 1 failed in 586.5 s
(9 m 46 s)**. This stream's `tests/test_genesis_assemble.py` = **11/11 pass**
(10 unit tests of OUR content + 1 end-to-end ladder test that rebuilds and
certifies all five rungs in a temp dir). The single failure is the
pre-existing, shared `tests/test_plugin_sync.py::test_plugin_is_in_sync_with_source`:
`plugin/` has drifted from `src/` by 12 files owned by OTHER concurrent
streams (`provenance.py`, `identity.py`, `estorage.py`, `mep/*`,
`genesis/{skeleton,types,__init__,data/object_styles.json}`); fixed by the
orchestrator's single `python tools/sync_plugin.py` run after all streams
land. This stream added NO `src/` module (its code lives in `tools/`), so it
contributes NOTHING to the drift. The previously-reported order-flaky
`test_mep_views_spaces` failure did not reproduce (passed).

BRANCH STATE: no commits (git repo with an unborn `main`); all work is
uncommitted files at the paths above — `tools/genesis_assemble.py` (new),
`tests/test_genesis_assemble.py` (new), `docs/writer/genesis-status.md` (new),
`docs/inbox/genesis-assembler.md` (this, new), `experiments/genesis/{G0a,G0b,
G0c,G0d,G0}.rvt` + `{G0a,G0b,G0c,G0d,G0}_{validate,provenance}.json` (+`.txt`)
+ `G0_manifest.json`, `G0_pipeline.json`, `G0_streams.json`. All five
ladder files validate 0 errors (G0: 0 warnings); G0 ledger: 0 autodesk-sample
/ 0 modified / 0 unmatched / 0 family docs / 205 host = 63 created + 142
similarity-flagged; 11/11 tests pass. NO protected `src/rvt/*` module, no
existing test, no orchestrator-owned or sibling-stream file edited; no
browser used. READY.

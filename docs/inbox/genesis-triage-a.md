# genesis-triage-a — BUG A skeleton-completeness bisection (workstream record, 2026-08-03)

Charter: build the BUG-A bisection ladder — probe files that walk TOP-DOWN
from viewer-PASSED reductions of the rst basic sample (R5, R9) toward the
G1_candidate condition (constructed base, viewer FAIL), removing ONE class of
content per rung, so that the first rung the Autodesk viewer REJECTS names
the class the reader requires and our validator does not. Every probe must
be dangling-free by construction and pass `tools/rvt_validate.py` with ZERO
errors. Deliver the K rungs + `probes.json` manifest + the inverse census
(`docs/writer/skeleton-census.md`) + a suspect ranking; the oracle (viewer
uploads) is the orchestrator's.

Territory touched ONLY: `tools/genesis_triage.py` (new),
`tests/test_genesis_triage.py` (new, 7 tests),
`experiments/genesis/triage/*` (13 probe files + per-rung JSON reports +
`probes.json` + one non-uploaded intermediate), `docs/writer/skeleton-census.md`
(new), this record. NO existing `src/rvt/*.py`, tool or test edited — the
tool IMPORTS `tools/rvt_reduce.py` (ladder v2: reference graph, maxgc, unit
splice), `tools/genesis_assemble.py` (the schema-typed ADocument editor +
registry maps), `rvt.reduce`, `rvt.manipulate` (the M2/M3-certified soft-
referrer neutralisation + modify commit), `rvt.adocument` (byte-exact
codec), `rvt.famgen.factory` (solved ContentDocuments grammar), `rvt.families`.
No browser / viewer use.

## Result in one screen

**13 validator-VALID probe files (0 errors each, arbiter CLI pasted in §7),
each derived from a viewer-PASSED anchor (or the previous rung) by removing
one class of content**, plus the manifest and census. Reproduce:
`.venv/bin/python tools/genesis_triage.py` (repo root, ~3 min all rungs).

| # | probe | derived from | the ONE thing it tests | shape after |
|--:|---|---|---|---|
| 1 | **K4** | K3 (← R9 PASS) | ZERO loadable families + ZERO embedded documents on the sample's FULL skeleton — the G1 condition reproduced from the passing side. **THE CRUX.** | 3,342 elem, units 1, CD 0, ContentTable 0, FamilyMgr 9/0 |
| 2 | KD1 | R9 PASS | Bug-B control: R9b's exact 38 orphan documents removed COHERENTLY (all four document registries reconciled) | 3,709 elem, units 15, CD 14, CT 14, FamilyMgr 22/14 |
| 3 | K3 | R9 PASS | annotation-head/tag USAGE nulled (level/grid/callout/viewport/section attrs, StructSettings, CopyWatch, sheet title-block ref → -1); families + docs KEPT (pure modify) | 3,709 elem, all 52 docs |
| 4 | K5 | K1 | the whole settings-SINGLETON set G1 lacks (assembler §5.2 hypothesis) removed, incl. registry slots nulled | 6,448 elem |
| 5 | K6 | K1 | the un-referenced built-in-category graphic-style CATALOG removed (2,151 rows: 1,622 GStyle + 171 Category + patterns/assets/materials) | 4,389 elem |
| 6 | K4b | K3 | K4 but ONE loadable family ('M_View Title') kept WITH its document, unused — the K4-FAIL splitter | 3,363 elem, units 2, CD 1, CT 1 |
| 7 | KD1a | R9 PASS | KD1 with ONLY the ContentTable reconciled (FamilyMgr entries still name the removed GUIDs) — splits WHICH registry is Bug B | 3,709 elem, 15/14/14, residual GUID bytes 38 |
| 8–11 | K5a K5b K5c K5d | K1 | pre-built bisection of K5: PenWidthTableElem id 2 / BrowserOrganization + system navigator / MEP-structural settings singletons / the remaining UniqueElement singletons | 6,539 / 6,527 / 6,498 / 6,493 elem |
| 12 | K1 | R5 PASS | reference EMPTY PROJECT on Autodesk's own skeleton (placed model removed, views' references neutralised as Revit's own delete does); parent of K2/K5x/K6; the census baseline | 6,540 elem |
| 13 | K2 | K1 | view-minimality on the full skeleton ({3D} + Level 1 only) | 6,092 elem |

Recommended first upload batch (all one round): **K4 + KD1 + K3** (the family-
document question with its control and parent) **+ K5 + K6** (singletons and
catalog on the empty-project base). K5a..K5d / K4b / KD1a are the pre-built
follow-ups; K1/K2 are the expected-PASS parents.

## Reading the verdicts (also in `probes.json:reading_the_results`)

* **K4 PASS** ⇒ loadable families / embedded documents are NOT required ⇒
  Bug A is a settings singleton (the K5x FAIL names it) or the style catalog
  (K6 FAIL) or another census class.
* **K4 FAIL & KD1 PASS & K3 PASS** ⇒ the reader REQUIRES the loadable-family /
  embedded-document machinery even when nothing references those families ⇒
  the genesis base MUST carry a family-document set ⇒ the asset-forge L4/L5
  host loader is the critical path. K4b then splits "any one document" from
  "the specific annotation-head set".
* **K3 FAIL** ⇒ the head/tag USAGE fields must name real families ⇒ K4 is
  unreadable; genesis must author view types WITH head families.
* **KD1 FAIL** ⇒ even four-registry-coherent unit removal is rejected ⇒ a
  fifth document surface exists; K4 unreadable. **KD1 PASS & KD1a FAIL** ⇒
  the FamilyMgr loaded-family registry (not the ContentTable) was Bug B.
* **K5 FAIL** ⇒ one of K5a..K5d fails too and names the required singleton
  group (K5a = PenWidthTableElem id 2 is the prior).
* **K6 FAIL** ⇒ the un-referenced built-in-category style catalog is
  required ⇒ genesis must generate the full object-styles table.
* **K3, K4, K5, K6 all PASS** ⇒ the required class is one this ladder did not
  isolate: the 19 project `DBViewType`s + annotation-attribute types, the ~450
  settings CATALOGS (HVACLoad*, wire/pipe/duct types, load classifications),
  the 8 curtain SYSTEM families' host-scoped editor elements, grids/refplanes
  ⇒ next ladder: R9 minus the view-type layer / R9 minus the settings
  catalogs / R9 minus the curtain-system-family layer (each is one more rung
  on the same tool).

## New format findings (evidence — merge into KNOWLEDGE.md)

1. **`m_famId` SCOPING = family-owned host content, and it explains the "91
   DBViewTypes"** [V]. In rstbasic, 72 of the 91 `DBViewType`s carry
   `m_famId` = one of the 8 curtain-wall SYSTEM families (Rectangular /
   Circular / L / V / Trapezoid / Quad corner mullions, System Panel, Empty
   System Panel — element ids 8482/8483/12609/12613/18428/18432/18436/18440),
   **9 per family**: they are the system families' FAMILY-EDITOR view types
   (Floor Plan / Ceiling Plan / Section 1 / …) living in the HOST document,
   `m_famId`-scoped — exactly the machinery an embedded family DOCUMENT
   carries internally for a loadable family. Same for 8 of the 9
   `PenWidthTableElem`s (the REAL project pen table is **element id 2**,
   `m_famId` = -1) and 8 each of SectionAttributes / CalloutTag /
   InteriorElevAttributes / DimensionStyle. The 19 remaining DBViewTypes are
   the project's real view types. Every family-scoped child (sub-categories,
   styles, fonts, text/tag/leader/dim/section attribute types, params,
   image symbols) carries `m_famId` = its family.
2. **Family linking fields** [V, K3's neutralisation set proves it]:
   `FamilySymbol.m_familyId` = its Family (its `m_famId` is **-1**);
   `FamilySurrogate.m_elemId` = its Family; `FamSymSurrogate.m_elemId` = its
   FamilySymbol (+ `m_famSurrogateId`); `ParamElemFamily` is ElemTable-owned
   (`m_OwningElementId`) by the Family; family-scoped children `m_famId`. The
   only OUTSIDE references into the loadable-family layer of a reduced project
   are USAGE fields: `LevelAttributes/GridAttributes/CalloutTag/
   ViewportAttributes.m_familyTagId`, `SectionAttributes.m_sectionHead|Tail
   FamilyTagId`, `InteriorElevAttributes.m_elevationSymbolId`,
   `StructSettingsElem.m_bcFixedFamilyId`, `CopyWatchProperties.m_typeCopyMap
   [*].second.m_elementId`, `DBViewDrafting.m_sheetTitleBlockId`, plus each
   referrer's seq-101 `ElementHeader.m_parents.m_deletion[]` entry (K3 edits
   exactly these 12 elements / 21 fields and nothing else).
3. **A document GUID lives in FOUR places** [V, byte-scanned]: the save-unit
   separator inside `Partitions/<N>`, its `Global/ContentDocuments` entry, the
   ADocument `ContentTable.m_ContentRecSet[].m_ContentKey.m_guidKey`, and
   `FamilyMgr.m_arrLoadedFamilyInfo[].m_familyDocGUIDs[]` (`AppInfoManager`
   slot 0; 50 entries in rstbasic, one per family, each `{m_surrogateId,
   m_familyDocGUIDs}`; system families' lists are empty). COHERENT removal
   must touch all four (`genesis_triage.remove_documents`); the R9b/R10b
   splices touched only the first two.
4. **Embedded documents reference HOST catalog rows** [V, 1,841 typed edges
   in K1]: elements INSIDE the embedded family documents (units 1..k) hold
   ElementId references to HOST elements — CurveElem → host GStyleElem
   ×608, views inside documents → GStyleElem ×~344, FilledRegionAttributes →
   FillPatternElem ×93, Family/FamilySymbol (in-doc) → GStyleElem/Material,
   DBViewType (in-doc) → MaterialElem ×31. So a family cannot be deleted while
   its document exists (the document pins the host's family-scoped rows,
   whose `m_famId` pins the family) — "remove a family" = family elements +
   family-scoped children + document, TOGETHER; and a document INSERTED into
   a host (asset-forge L4/L5) must have its outbound host-row references
   resolve. This is why K4 removes the loadable-family layer and all
   documents in ONE rung.
5. **Two-bug model corroborated by the four-registry census** [V]:

   | file | units | CD | ContentTable | FamilyMgr entries/guids | viewer |
   |---|--:|--:|--:|--:|---|
   | R9 | 53 | 52 | 52 | 50/52 | PASS |
   | R9b, R10b | 15 | 14 | **52** | 50/**52** | FAIL |
   | G0 (v1) | 1 | 0 | **52** | 50/**52** | FAIL |
   | G1a, G1_candidate | 1 | 0 | 0 | 0/0 | FAIL |
   | KD1 (new) | 15 | 14 | 14 | 22/14 | ? |
   | K4 (new) | 1 | 0 | 0 | 9/0 | ? |

   R9b/R10b (and the audited G0) are doubly incoherent — both registries name
   38 vanished documents (Bug B). G1a/G1_candidate are COHERENT on both and
   still FAIL — so Bug A is genuinely NOT this surface: it is skeleton
   completeness, which is what the K5x/K6/K4 rungs bisect. KD1 = R9b done
   coherently (the mechanism control); KD1a splits ContentTable vs FamilyMgr.
6. **maxgc + neutralise composes into a general "remove a class" operator**:
   K1 (model gone, views intact) requires neutralising the views'
   `HiddenElementsViewSettings.m_hiddenElements` lists (1,195 refs in the 3D
   views), `AdHocOverrides.m_elementMap`, schedule column-id arrays and sheet
   title-block ids — the certified soft-referrer rule (M2) — before the model
   is collectable. The K5x/K6 rungs also purge exactly the deleted ids from
   the ADocument registries (`genesis_triage.purge_ids_from_latest`, driving
   the genesis-2 `AdocGraphEditor` with live = every id the tree references
   MINUS the deleted set), so a removed singleton's positional slot reads -1
   (G1's condition) rather than a dangling id.

## The empty-project census (K1) vs G1_candidate — the inverse required set

`docs/writer/skeleton-census.md` (regenerated by the tool): 205 classes are
present in K1 (Autodesk's own empty-project skeleton, 6,540 elements) and
ABSENT from G1_candidate (234 elements), ranked settings-singletons /
registries → category-style catalog → settings catalogs → view/annotation
type layer → family layer, each row naming the rung that tests it. Head of
the list (all K5a..K5d / K6): PenWidthTableElem (id 2 + 8 family copies),
BrowserOrganization ×11, RbsDbViewSystemNavigator, StructSettingsElem,
WallJoinDefaultSetting, AutoJoinTracker, KeynoteTable, InitialViewSettings,
the RbsWire/Pipe/Duct/Conduit/CableTray Settings + Sizes singletons,
MEPSystemTracker, then GStyleElem 2,173 vs G1's 94 / CategoryElem 606 vs 7.
The full class-by-class matrix (R9, K1–K6, K4b, KD1, G1_candidate) is in the
doc; the census RANKS, the K rungs DECIDE.

## What each Branch-A rung leaves standing (attributable residues)

* K1: 7 seed elements survive (6 area-boundary/room-separation CurveElems
  pinned by AreaScheme/LevelRoom plan topologies, 1 locked dimension pinned by
  ref planes); every catalog, type, family, view, singleton, datum intact.
  ADocument untouched (its ~2,100 newly-dangling model ids are within the
  R9-proven tolerance).
* K2: 116 view companions survive, pinned by DBViewProject / DBViewTypes /
  the two keeper views (Section/InteriorElev attributes, 20 sub-category rows
  of the kept views' families, viewports/drawings of the keepers).
* K5: seed 128, 96 deleted, 32 pinned survivors — WorksetVisibilitySettings
  Elem (pinned by every view), AreaMeasureElem (AreaTypeElem/plan topologies/
  curves), ProjectRevision + AllProjectRevisions + RevisionNumberingSequence
  (a kept drafting view), 4 of 11 BrowserOrganization (DBViewProject), the 8
  family-scoped PenWidthTables (their curtain families), EnergyDataSettings,
  ZoneScheme, AreaSettingsElem, RbsPipe/DuctSettingsElem, the sheet-collection
  / MEP-component / MEP-network / keynote-tags / revision-clouds trackers, and
  ActiveGeoLocationTrackingElement. K5a therefore removes ONLY the real pen
  table (id 2); K5b 7 BrowserOrganization + the system navigator + browser
  settings; K5c 44 (StructSettings, ReinforcementSettings, wire/pipe/duct/
  conduit/cable-tray settings+sizes, structural-connection / SSE-point /
  fabrication / area / energy / MEP-hidden-line settings, AllPlanTopologies);
  K5d 48 (wall-join/auto-join/keynote/revision/print/export/copy-monitor/
  numbering/sheet-set/trackers/plan topologies). Purge totals per rung are in
  each `K5*.json` (`latest_purge`).
* K6: 986 catalog rows survive (551 GStyle + 435 CategoryElem: the family
  sub-categories pinned by the 50 families and their DOCUMENTS, styles pinned
  by curve/import/view records, 61 materials, 49 assets, 15 fill + 8 line
  patterns, the 8 family pen tables). Deleted: 1,622 GStyle + 171 Category +
  142 line patterns + 101 fill patterns + 82 assets + 32 materials, and their
  2,155 registry rows dropped from the ADocument.

## Gotchas found (for KNOWLEDGE.md merge)

1. Findings 1–4 above (m_famId scoping / linking fields / four-place GUID
   map / cross-document catalog references) — each is a rule any future
   family REMOVAL or INSERTION must honour.
2. `rvt_reduce.build_state_v2`'s reference graph is FILE-WIDE (embedded
   units' records are referrers too). This is what silently kept the last 21
   families and the family-scoped catalog rows in R9/R10, and it is why the
   attributable pin evidence there ("Family ← DBViewType ×72") is really
   "curtain SYSTEM family ← its 9 family-editor view types" — an ownership
   edge, not a default-head usage. The `deep_census.md` reading "the 91 view
   TYPES carry default head/tag families" must be corrected: only the 19
   project view types reference head families, via the usage fields in
   finding 2, and NOT via `DBViewType.m_famId`.
3. `rvt.manipulate.referrers()` finds referrers inside embedded units too;
   the modify path re-emits only unit 0, so a neutraliser must FILTER to
   host referrers (`genesis_triage.neutralise_referrers` does, and reports
   the embedded ones).
4. Deleting a settings singleton from a sample-lineage file leaves its
   `UniqueElementsTracking` positional slot naming a dead id — a state no
   sample and no constructed base is ever in; the K5x rungs purge it (slot →
   -1) so the probe matches G1's condition instead of inventing a third one.
5. `CustomElement` in rstbasic = the wire/cable CONDUCTOR CELLS referenced
   by RbsWire/RbsCable types (settings-catalog data), NOT placed content —
   excluded from the K1 model seed.

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`tools/rvt_reduce.py` (reduction stream)** — `run_stage_r9b` /
  `remove_units` should reconcile the ADocument (ContentTable +
  FamilyMgr, finding 3): today its output (R9b/R10b) is exactly the
  incoherent shape the coherence table convicts. `genesis_triage.
  remove_documents` is the complete recipe; lifting it into `rvt.reduce`
  or `rvt.content` beside the asset-forge's `parse/assemble_content_
  documents` retires the wave-1 scanner and Bug B's mechanism together.
  Also its `V2_CHILD_CLASSES` should treat ANY class with `m_famId` = a
  seeded Family as an ownership child (finding 1) — the delete-only ladder
  can then remove families completely instead of stranding them.
* **`tools/genesis_assemble.py` / genesis-2 stream** — when family
  documents are eventually LOADED into the base (asset-forge L4/L5), the
  loader must ALSO write the `FamilyMgr.m_arrLoadedFamilyInfo` entry
  (`{m_surrogateId, m_familyDocGUIDs}`) beside the ContentTable record
  (finding 3), and the inserted document's outbound references to host
  category/style/pattern/material rows must resolve (finding 4).
* **`src/rvt/families.py` (family stream)** — `family_documents()` could
  expose the linking fields of finding 2 (symbol `m_familyId`, surrogate
  `m_elemId`, FamSymSurrogate chain) as a `family_closure(doc, family_id)`
  helper; three tools now re-derive it.
* **`docs/writer/deep_census.md` / KNOWLEDGE.md owner** — correct the
  "91 view types default to head families" reading per gotcha 2.
* **`tools/sync_plugin.py`** — the pre-existing plugin drift test (this
  stream adds `tools/genesis_triage.py`, which the plugin does NOT bundle;
  no `src/` module added, so nothing new to sync from this stream).

## G2a (ADD the suspect class to G1) — assessed, not built

No OUR-constructor exists for any top suspect (`rvt.genesis.skeleton`'s only
mention of `PenWidthTableElem` is the slot-2 entry of the position table;
genesis-2 §5.2 lists the 67 missing singletons as an empty constructor
queue). A sample-COPY G2a (transplant PenWidthTableElem id 2's three records
into G1_candidate with a fresh id via `rvt.commit.commit_new_elements`, then
point OUR `UniqueElementsTracking` slot at it via the codec) is buildable,
but it duplicates K5a's question with weaker attribution (id re-map + our
ADocument slot edit are two extra variables) and would be a flagged
diagnostic-only copy. Recommendation: build a G2a only AFTER a K5x/K6 verdict
names the class, and then from OUR constructor (the skeleton / systemtypes
streams' backlog), not a copy.

## §7 Arbiter output (this session, repo root)

```
.venv/bin/python tools/rvt_validate.py --quiet experiments/genesis/triage/*.rvt
OK   experiments/genesis/triage/K1.rvt   errors=0 warnings=1
OK   experiments/genesis/triage/K2.rvt   errors=0 warnings=1
OK   experiments/genesis/triage/K3.rvt   errors=0 warnings=1
OK   experiments/genesis/triage/K4.rvt   errors=0 warnings=1
OK   experiments/genesis/triage/K4b.rvt  errors=0 warnings=1
OK   experiments/genesis/triage/KD1.rvt  errors=0 warnings=1
OK   experiments/genesis/triage/KD1a.rvt errors=0 warnings=1
OK   experiments/genesis/triage/K5.rvt   errors=0 warnings=1
OK   experiments/genesis/triage/K5a.rvt  errors=0 warnings=1
OK   experiments/genesis/triage/K5b.rvt  errors=0 warnings=1
OK   experiments/genesis/triage/K5c.rvt  errors=0 warnings=1
OK   experiments/genesis/triage/K5d.rvt  errors=0 warnings=1
OK   experiments/genesis/triage/K6.rvt   errors=0 warnings=1
```
The one warning on every file (and on the pristine sample) is the known
DataStorage / RebarShape extensible-storage decode gap; it is not touched by
any rung. Each rung's own report (`experiments/genesis/triage/<K>.json`)
also carries the `rvt.reduce.verify_reduced` structural proof (CRC / ECC /
walker / stamps / id-set / count / sentinel checks — all pass) and, for the
document-removal rungs, `residual_guid_bytes = 0`.

## Full-suite result at handoff

`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle` → see BRANCH
STATE below for the count. This stream's `tests/test_genesis_triage.py` = 7
passed (18 s): the R9 anchor's four-registry coherence; the family-layer
linking rules and the "outside referrers are only usage fields" invariant;
coherent 38-document removal (four registries + 0 residual GUID bytes +
validator 0 errors); the exact-id ADocument purge; an end-to-end K3→K4 crux
path in a temp dir; manifest / census consistency.

## Open questions (need the viewer / the orchestrator)

* The verdicts on the 13 probes, in the §"Reading" order — K4/KD1/K3/K5/K6
  first. Every branch of the interpretation tree is pre-built except the
  "all four PASS" branch, whose next rungs are named above.
* Whether the 8 curtain SYSTEM families and their 72 host-scoped
  family-editor DBViewTypes are themselves required (no rung removes them
  yet — every K file keeps them, so no verdict here informs it).
* Whether an INSERTED family document must reference host rows (finding 4) or
  may be fully self-contained (a standalone .rfa's document is) — the
  asset-forge load proof will hit this first.

## Proposed next tasks (orchestrator decides)

1. Upload K4 + KD1 + K3 + K5 + K6 (one batch); then the pre-built follow-ups
   the first verdicts select (K4b / KD1a / K5a..K5d / K1).
2. Whichever class a FAIL names → its constructor (skeleton / systemtypes /
   asset-forge queue) → a G2 built by OUR constructor, certified by the same
   validator + this ladder's K1 census as the reference.
3. Fold finding 3 into the reduction stream's `remove_units` and finding 1's
   ownership rule into `V2_CHILD_CLASSES`; fold the four registries into the
   validator's coherence layer (it would then have flagged R9b/R10b).
4. If all four PASS: the next-ladder rungs (view-type layer / settings
   catalogs / curtain-system-family layer), same tool, one function each.

## BRANCH STATE

No VCS (plain directory). New, uncommitted files: `tools/genesis_triage.py`,
`tests/test_genesis_triage.py` (7 pass), `docs/writer/skeleton-census.md`,
`docs/inbox/genesis-triage-a.md` (this file), and under
`experiments/genesis/triage/`: `K1 K2 K3 K4 K4b KD1 KD1a K5 K5a K5b K5c K5d
K6 .rvt` + one `.json` report each + `probes.json` +
`K1_step1_neutralised.rvt` (intermediate, not for upload). Every emitted
`.rvt` = validator VALID (0 errors), structural proof clean, document
registries coherent by construction. (The same directory also carries
`B1..B5.rvt`, `B*_v2report.json`, `probes_bug_b.json` — a PARALLEL Bug-B
stream's files, not this stream's; untouched. My `probes.json` is the K
manifest; their `probes_bug_b.json` is the B manifest — no collision. If
that B-ladder already carries a coherent-removal control the orchestrator may
prefer it to KD1/KD1a; KD1 stays listed because it is K4's prerequisite.)
Full suite this session: `.venv/bin/python -m pytest tests/ -q
--ignore=tests/oracle` → **638 passed, 3 failed (664 s)**; the 3 failures
are the pre-existing, other-stream ones every recent record lists —
`test_plugin_sync.py::test_plugin_is_in_sync_with_source` (plugin bundle
drift; fix = the orchestrator's `python tools/sync_plugin.py` run) and the
two STALE `test_provenance.py` G0 assertions genesis-2 already diffed —
none touches this stream's files, and this stream's 7 tests are among the
638. STOPPED AT READY — the 13 probes await the orchestrator's viewer
gate.

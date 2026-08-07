# genesis-addback — the ADD-BACK probes + the REGISTRY-PARITY audit (workstream record, 2026-08-03)

Charter (orchestrator verdicts #6/#7): every constructed base FAILS with
Autodesk's own `Revit-DocumentCorruption` / `Design is empty` — including
S1..S5, which put OUR settings singletons + OUR complete built-in style
catalog onto the FAILING G1 base and therefore could not separate "our
constructors / registry wiring are wrong" from "the G1 base carries an
independent defect".  This stream ISOLATES the question by building from
the PASSING side: our content is added to the KNOWN-GOOD Autodesk
empty-project skeleton (K1's lineage) at EXACTLY the point the sample's own
content was removed (K5 = minus the singletons, K6 = minus the built-in
style catalog; both viewer FAIL), with every removed row our constructors
do NOT cover restored VERBATIM — so the ONLY difference from a passing
file is OUR substitution.  Plus the REGISTRY-PARITY AUDIT: for every
registry surface the reader walks, K1's document object vs S5's,
class-keyed, every mismatch classified and ranked.

Territory touched ONLY (as chartered): `tools/genesis_addback.py` (new),
`tests/test_genesis_addback.py` (new, 23 tests), `experiments/genesis/
addback/` (R1, R1s, R2, R2s, R3 `.rvt` + per-probe `.json` reports +
`probes.json` + `registry_parity.json`), `docs/writer/registry-parity.md`
(new), this record.  NO existing `src/rvt/*.py`, tool or test edited —
every dependency is IMPORTED (`rvt.genesis.{settings,catalog,types}`,
`rvt.{adocument,commit,reduce,mutate,manipulate,validate}`,
`tools/genesis_triage.py`'s `purge_ids_from_latest`, `tools/genesis_
assemble.py`'s schema-typed `AdocGraphEditor`).  No browser / viewer use:
the probes are LEFT ON DISK with a manifest for the orchestrator's
certification queue.

## Result in one screen

**Five validator-VALID probe files (0 errors, 0 NEW dangling document-object
references, four-registry coherent 53/52/52/50 = K1's exact coherence),
each named-purpose, plus the parity audit.**  Reproduce:
`.venv/bin/python tools/genesis_addback.py` (~2.5 min, repo root).

| probe | base | + restored from K1 | + OUR elements | elements | bytes | self-parity vs K1 (sev-0) |
|---|---|--:|--:|--:|--:|--:|
| **R1** | K5.rvt (FAIL) | 38 (the 10 uncovered classes) | **50** (the 48 covered singleton classes) | 6,532 | 4,481,024 | **0** |
| **R1s** | K5.rvt | 88 (everything but pen table + browser orgs) | 3 (pen table + 2 house browser orgs) | 6,535 | 4,485,120 | **0** |
| **R2** | K6.rvt (FAIL) | 803 (sub-categories, patterns, materials, assets, pen table) | **1,348** (OUR built-in object-style rows, RE-POINTED) | 6,540 | 4,472,832 | **0** |
| **R2s** | K6.rvt | **2,151 = ALL** (mechanics control) | 0 | 6,540 | 4,489,216 | **0** |
| **R3** | S5.rvt (FAIL) | — | — (8 registry repairs, rows unchanged) | 1,654 | 389,120 | 2 (principled) |

"Self-parity 0" = the parity engine turned on the probe itself finds
ZERO severity-0 divergence from K1's registry shape for the classes the
probe carries — our substituted classes are registered EXACTLY where the
sample's own rows were.  Recommended upload batch (one round): **R2s + R1 +
R2** (R2s certifies the mechanics; R1 and R2 are the two verdicts); R1s and
R3 are the pre-built follow-ups.

## Why these probes are readable when S1..S5 were not

* **The mechanics are proven by construction and by control.**  Every
  probe is built the same way: (1) TRANSPLANT the sample's own rows we do
  not substitute back into the K-base (verbatim framed record bytes,
  original ids, original ElemTable owner ids, appended before the unit
  sentinel — Autodesk's own passing sample is NOT id-ordered: 42-45
  order inversions, its unit-0 records literally start with the
  KeynoteTable / AssemblyCodeTable, so appended low-id records are within
  the reader's proven tolerance); (2) REINSTATE K1's document object,
  purged of exactly the still-absent (substituted) ids — because K5/K6
  were themselves produced from K1's object by exactly this purge (a
  superset of it), every restored sample row comes back at its EXACT
  original registry position with its exact original neighbours; (3)
  commit OUR elements; (4) populate the registries over ours (R1) /
  RE-POINT every reference at ours (R2); (5) certify + self-parity.
  **R2s (all 2,151 K6 deletions restored, nothing substituted) reproduces
  K1: identical element-record SETS in all three seqs, `Global/Latest`
  byte-IDENTICAL to K1's, `ContentDocuments` / `History` / `BasicFileInfo`
  identical, even the same total byte size 4,489,216.**  Its only
  differences from K1 are the writer's own proven-benign ones (record
  order/blocking, the restored rows' refreshed episode metadata, the
  increment-table identity scrub V32 PASSED).  A PASS on R2s makes R1 and
  R2 readable; a FAIL convicts the mechanics and voids both.
* **R2's re-point is complete by construction.**  Our frozen graphic-
  category enum (1,074 categories, 333 cuttable) covers EXACTLY the 1,348
  (built-in category, style type) pairs K6 deleted — 1,018 projection +
  330 cut, **0 pairs our enum lacks** — giving a clean 1:1 map
  {K1's deleted row id -> our new row id}.  A schema-typed remap over K1's
  reinstated document object rewrote **exactly 1,348 references, all in
  `CategoryTracking.m_gstyleData`** (the two `SymbolIdMgr` references to
  built-in styles point at rows K6 KEPT, so they were untouched), leaving
  0 dangling.  R2 = the passing skeleton with the built-in object-styles
  table's ROW VALUES ours and NOTHING else changed.
* **R1's wiring is to K5's own companions**, discovered from the base
  itself, so our singletons name what the sample's named: units 19236, the
  DOCUMENT sun 54520 (the one the sample's `<Shading>`/`<Raytracing>`
  presets and its project view + navigator all share via
  `m_lights.m_sunAndShadowSettingsId`), phase 86961 / filter 375, Level 1
  (311), workset visibility 113134 (kept), the KEPT MEP component/network
  trackers 907354/1468014 and pipe/duct settings 102128/102127 (our
  deleted MEPSystemTracker + LayoutNodesTracker are rebuilt around them
  with the sample's own regenOnly shape), the wire catalog SYMBOLS present
  in K5 (Copper 102411 / Aluminium 102412, 75/90 C ratings, THHN/THWN-2/
  XHHW-2 among the 26 insulations) under which OUR NEC ampacity table is
  keyed, the SURVIVING KeynoteTable 86291 our KeynotingSystem names, the
  'Title w Line' viewport type 324 the sample navigator's own viewport
  used, and the surviving link document 1250030 our CopyWatchProperties
  names (registered in `CopyWatchModeMgr` parallel to it, exactly where
  the sample's link copy/watch state sat).  The 4 per-tree 'all' default
  BrowserOrganizations SURVIVED K5 (m_bDefault=True), so ours adds only
  our 2 house schemes — registered by a MINIMAL path that appends to
  `m_elemIdSet` and leaves the base's per-tree default map / folder cache
  / expanded-node state exactly as the accepted file had it (the
  assembler's cache-clearing path suits a from-scratch document, not a
  skeleton whose defaults are present).

## Reading the verdicts (also in `probes.json:reading_the_results`)

* **R2s FAIL** => the add-back MECHANICS introduce a defect => R1/R2
  unreadable; diff R2s against K1 stream-by-stream (they should differ
  only in record order / episodes / the increment-table scrub).
* **R2s PASS + R1 PASS** => OUR document-settings singleton constellation
  (S3/S5's, all 48 K5-deleted classes it covers) is an ACCEPTABLE
  SUBSTITUTE => S5's failure was the G1 BASE (an independent defect), not
  our singletons => build **G2 = the KNOWN-GOOD SKELETON with our content
  substituted class-by-class** (the substitution ladder from the passing
  side the orchestrator decided on; this stream's transplant + reinstate
  machinery is exactly its engine).
* **R2s PASS + R1 FAIL** => our singleton constructors and/or their
  registry wiring are rejected even on the good skeleton => R1s bisects:
  R1s PASS puts the defect in the MEP / structural / tracker constructors;
  R1s FAIL puts it in the pen table / browser substitution itself.
* **R2s PASS + R2 PASS** => OUR complete built-in object-styles catalog
  (our discipline colours/weights over the frozen enum, 0 rows
  value-identical to Autodesk's) is an acceptable substitute => K6's and
  S4's failures were the base / the BUNDLED pen table (K6 also deleted
  it — a K-ladder confound both R2 and R2s hold constant by restoring it).
* **R2s PASS + R2 FAIL** => our catalog ROW VALUES / shape are rejected
  (the registration is provably right — see the audit) — read R2's
  catalog report; the parity audit already proves the CategoryTracking
  registration itself is clean.
* **R3 PASS** => S5's defect was registry INDEXING (its rows were fine)
  => adopt every R3 fix (below) in the assembler / `settings.ADOC_
  REGISTRY` / `apply_adoc_registry`.  **R3 FAIL** => registry indexing
  was not S5's only defect; the residual is the inventory/content
  difference the audit lists as informational, or the G1 base itself.

## THE PARITY AUDIT — why S1..S5 failed (`docs/writer/registry-parity.md`)

The engine (§Method below) diffed EVERY id-holding registry surface of
K1's document object against S5's: 241-slot AppInfo bodies, the
positional UET table, named scalar members, and every container as
class-keyed row signatures.  **Final: 214 mismatches, 11 of severity 0**
(the P4/P6 corruption signature = a PRESENT row the registry does not
index the way the accepted file does), 34 severity 1 (conditional /
regenerable-state), 169 informational (inventory gaps by design):

1. **THE DEFAULT-TYPE MAP is the largest gap** — `SymbolIdMgr.
   m_defElementTypeMap` (group -> default element).  Groups are
   COMPILED-IN constants, one per class AND — for `DBViewType` — one per
   VIEW FAMILY: group 62 = the 3D-view family default, 63 walkthrough, 64
   rendering, 65 schedule, 66 legend, 67 cost report, 68 sheet, 69
   drafting, 70 structural plan, 71 floor plan, 72 ceiling plan, 73/81
   section, 74 detail, 75/76 elevation, 79 pressure-loss report, 80 panel
   schedule, 107 column schedule, 150 analysis report [DERIVED: K1's own
   map targets read against their `m_systemFamilyIdx`].  **S5 carries NO
   default view type for 18 of its 19 view families** and no default of
   6 other present classes (ConstructionSetProject group 110, Floor
   groups 4/5, TextNote groups 12/139, the default line style group 41).
   Cause: `apply_adoc_registry`'s def-type rule only fills classes with a
   SINGLE group and a "type-like" name — DBViewType (20 family groups),
   ConstructionSetProject, Level, the multi-group attribute classes are
   silently skipped.  A default-type lookup at view creation / first
   placement is exactly the kind of walk the reader does at load.
2. **The object-styles catalog registration is CLEAN in S5** —
   `CategoryTracking.m_gstyleData` K1 2,183 rows vs S5 1,414; built-in
   (category, type) keys missing in S5: **0**; S5 present GStyle rows
   NOT indexed: **0**; dangling: **0**.  So our 1,320 catalog rows ARE
   indexed; if S4/S5's catalog is at fault it is the row VALUES (which
   R2 tests on the good skeleton), not the registry.  (`m_categoryData`
   likewise clean.)
3. **The positional singleton table is CLEAN in S5** —
   `UniqueElementsTracking`: every slot S5 populates holds the compiled-
   in class of that position; our `UET_POS_TO_CLASS` wiring is confirmed
   correct against the passing skeleton (S5's extra GCSTracker slot 15 is
   an occupied slot K1 leaves empty — informational).
4. **Four smaller genuine gaps**: `PrintSettingsTracking.m_idMRU` (the
   MRU pointer, null in S5); `RbsSystemNavigatorTracking.m_voltageType
   IdSet` (K1 registers its voltage type there; S5's 6 are unregistered);
   `ElemsSetWithCellsTracking.m_elemIdSetMap` — the CELL-KIND registry
   (below): S5's KeynoteTable + EnergyDataSettings hold external-file /
   -resource reference cells but are NOT registered under their cell-kind
   sets; `CopyWatchModeMgr` — S5 carries a fully-NULLED parallel
   link-row pair ([-1]/[-1], the assembler's purge residue) and its
   (no-link) CopyWatchProperties element is registered nowhere.
5. **34 severity-1** = conditional registries whose rule the generic
   engine cannot verify (`SymbolIdMgr.m_paramSets` / `m_paramSetKeys` —
   per-element parameter sets K1 keeps for 5 of 9 levels / 5 of 93
   materials / etc.; the level->MEP-layout-offset maps; per-user
   worksharing settings; template / sketch-plane / open-window session
   state; `NewItemNumber` MEP numbering counters; the `NOBLE` colour-fill
   / analysis caches — the passing skeleton's own copies are majority
   DANGLING, and R9 PASSES with an empty plan-topology map) — flagged for
   review, capped below severity 0.

**Bottom line for genesis-2:** S5's document object is missing SEVERAL
per-element registrations the reader plausibly requires — chiefly the
default-type map — while the two things S5 was BUILT to test (the
singleton UET slots and the catalog's CategoryTracking rows) are
correctly wired.  R1/R2 hold every one of these other surfaces at K1's
own state (they inherit K1's document object), so their verdicts are
about our CONTENT alone; R3 is S5 with the 11 severity-0 gaps repaired.

## New format findings (evidence — merge into KNOWLEDGE.md)

1. **The default-type map's DBViewType groups are per VIEW FAMILY**
   [V, K1's map read against `m_systemFamilyIdx`]: `SymbolIdMgr.
   m_defElementTypeMap` group 62 -> the 3D-view family (idx 102) default
   type, 63 -> 103, 64 -> 104, 65 -> 105, 66 -> 117 (legend), 67 -> 106,
   68 -> 107, 69 -> 108, 70 -> 120, 71 -> 109 (floor plan), 72 -> 111
   (ceiling plan), 73/81 -> 112 (section), 74 -> 113, 75/76 -> 114
   (elevation), 79 -> 116, 80 -> 118, 107 -> 119, 150 -> 121; family 115
   (loads report) has NO default group.  Also single-class defaults:
   group 4 = the FLOOR type, group 5 = the FOUNDATION-SLAB type
   (category -2001300), 12 AND 139 = the TextNoteAttributes default (the
   schedule text default shares it), 15 = the default LEVEL element, 41 =
   the default GStyle (K1's = the projection style of built-in category
   -2000044), 110 = the ConstructionSetProject.  A document with
   elements of the class / view types of the family carries the group's
   default row; our `apply_adoc_registry` fills only single-group
   "type-like" classes (`CLASS_TO_DEF_GROUPS` len-1 rule), so a
   census-complete candidate ships WITHOUT any view-family default.
2. **`ElemsSetWithCellsTracking.m_elemIdSetMap` is the CELL-KIND
   registry** [V, K1 exact]: a MAP keyed by cell kind — key **1200** =
   the set of every element holding an `ExternalFileReferenceCell` (K1:
   21/21 holders in the set, 0 non-holders), key **-100** = every
   `ESEntityCell` (extensible-storage) holder (7/7), key **1201** = the
   `ExternalResourceReferenceCell` holders that carry live external
   resource references (K1: keynote table, energy settings, assembly-code
   table, link symbol — 4 of its 8 resource-cell holders; the appearance
   assets' resource cells are unregistered => the 1201 rule is
   conditional, the 1200 / -100 rules are exact).  Any constructor that
   emits an ExternalFile/ExternalResource/ESEntity cell (our
   KeynoteTable, EnergyDataSettings) MUST register the element here.
3. **The sample's own unit-0 records are NOT id-ordered** [V]: K1 has 42
   order inversions, the pristine rst sample 45; the segment literally
   STARTS with element 86291 (KeynoteTable) and 1218726
   (AssemblyCodeTable) and ends with ids ~49026 — Autodesk's writer
   re-appends rewritten rows at the end.  Therefore appending records at
   the end of the unit at LOW ids (our transplant) is a shape the reader
   already accepts; record order is not a variable.
4. **K6 (the catalog removal) ALSO deleted the project pen table (id 2)**
   [V — unreferenced, so maxgc took it]: K6's viewer FAIL bundles the
   catalog with the pen table.  R2/R2s remove the confound by restoring
   the pen table in both.  (Similarly the K5 seed did not include the
   KeynoteTable itself — K5 KEPT it, only its KeynotingSystem died.)
5. **`DBViewTypesForNewLevel.m_newLevelDBViewTypes` = [-1, floor-plan
   type, ceiling-plan type, structural-plan type]** [V, K1] — a leading
   -1 sentinel slot then the three plan-family defaults; S5's [floor,
   ceiling] lacks the sentinel and the structural plan.
6. **The `WorksharingDisplaySettingsTracking.m_userToSettingsMap` entry
   is the PER-USER copy** (K1 has the project element + one user copy;
   a fresh document has the project element only) — conditional, not a
   defect for a base with no user customisation.
7. **`AbsLayoutAppInfo.m_map{Duct,Pipe,CabelTray,Conduit}LevelToOffsets`
   map EVERY level -> {offset set, selected offset}** in K1 (9 of 9 /
   7 of 9 levels) — the MEP auto-routing offsets remembered per level;
   session preference data, but populated for all levels in the accepted
   file (R3 fills our two levels with OUR routing offsets).

## The engine (method — reusable, in `tools/genesis_addback.py`)

* **Transplant** (`transplant`): the donor's EXACT framed record bytes
  (seq 101/102/103, from `rvt.encode.record_bytes` over the walked unit)
  + its ElemTable row (owner id preserved) committed at the ORIGINAL id
  through `rvt.commit.commit_new_elements`; canonical re-block after.
* **Reinstate reference object** (`reinstate_reference_latest`): swap
  in K1's `Global/Latest`, then `genesis_triage.purge_ids_from_latest`
  with `deleted = still-absent ids only` (live = every id K1's tree
  references minus those) — K1's inherited, R5/R9-proven-tolerated model
  dangles are LEFT ALONE by construction; the certification separates
  `dangling_inherited_tolerated` (also dangling in the base's own object)
  from `dangling_NEW` (must be 0).
* **Re-point** (`remap_ids_in_tree`): the schema-typed ElementId leaf
  walk (`AdocGraphEditor.iter_leaves`, complete by construction) with an
  old->new id map over EVERY body; nothing name-heuristic.
* **Special registrations** (`special_registrations`): the surfaces
  `settings.ADOC_REGISTRY` does not cover, applied so our substituted
  classes sit exactly where the sample's rows sat — the print-settings
  MRU pointer, the `CopyWatchModeMgr` parallel slot beside the surviving
  link, the def-type map group of a substituted class (`Construction
  SetProject` group 110 — the purge DROPS the row, ours must re-add it),
  the cell-kind sets for any of our external-cell holders.  Every one of
  these was FOUND by turning the parity engine on R1 itself and iterating
  until R1's self-parity read 0 severity-0.
* **Parity** (`registry_profile` / `parity_compare`): per file, every
  ElementId-typed leaf profiled as (i) UET positional slots, (ii) named
  scalar members, (iii) per container a Counter of CLASS-KEYED ROW
  SIGNATURES — a struct row = (its non-id scalar key fields, its
  immediate id fields as class descriptors), a nested set member = (row
  key + generic in-row path + class), an id-list entry = (class); built-in
  category ids / enum sentinels stay in the key as their raw values, so
  the object-styles table compares exactly.  The comparison distinguishes
  a **COMPLETE (per-element mandatory) registry** (the reference registers
  ALL its elements of the class there) from a **CONDITIONAL** one (a
  rule-based subset), reports coverage-relative (a class is a gap only if
  the subject leaves some of ITS OWN elements unregistered or lacks the
  key entirely — never for merely having fewer elements), skips the
  reference's own dangling residue and any subject dangle the reference
  ALSO dangles (INHERITED), and carries three specialised detail passes
  (CategoryTracking built-in/sub-category keys, the SymbolIdMgr view-
  family defaults, the cell-kind rule) plus a `KEYED_POLICY` /
  `ASSESSED_REGENERABLE` table encoding the domain judgment explicitly.
  **Self-check property: `parity_compare(K1, K1)` and `parity_compare(K1,
  R2s)` read 0 severity-0** (tests pin the former).

## R3's repairs (each derived from K1's own shape; the assembler's fix list)

| # | surface | repair |
|--:|---|---|
| 1 | `SymbolIdMgr.m_defElementTypeMap` | 18 view-family defaults (S5's own view types via the family->group constants) + Floor (group 4), TextNote (12, 139), the default line style (group 41 = our projection style of built-in category -2000044), ConstructionSetProject (group 110) = **23 rows** |
| 2 | `PrintSettingsTracking.m_idMRU` | -> our PrintSettings |
| 3 | `RbsSystemNavigatorTracking.m_voltageTypeIdSet` | += S5's 6 voltage types |
| 4 | `ElemsSetWithCellsTracking.m_elemIdSetMap` | KeynoteTable + EnergyDataSettings into sets 1200 AND 1201 (4 memberships) |
| 5 | `DBViewTypesForNewLevel.m_newLevelDBViewTypes` | rebuilt to [-1, floor plan, ceiling plan, structural plan] |
| 6 | `CopyWatchModeMgr` | dropped the fully-nulled [-1]/[-1] parallel link rows; our CopyWatchProperties -> `m_inDocCopyWatchProps` (no link document exists) |
| 7 | `AbsLayoutAppInfo.m_map*LevelToOffsets` | OUR MEP layout offsets for S5's 2 levels in the 4 maps |
| 8 | (CategoryTracking / UET / scalar sweeps) | ran, found nothing to change (already clean) |

Post-repair self-parity: **2 severity-0 remain, both principled** — the
foundation-slab default (group 5; S5's single floor type is a plain
floor, no structural-foundation type exists to be its default) and the
`m_linkCopyWatchProps` per-element demand (S5 has NO link document; the
in-document member is the honest home for a no-link copy/watch state).

## Diffs / hooks proposed for files outside this territory (NOT applied)

* **`src/rvt/genesis/settings.py` (genesis-singletons owner) —
  `apply_adoc_registry` / `ADOC_REGISTRY`:** adopt the seven repair
  classes above as REGISTRY RULES: (a) the def-type map — the DBViewType
  per-family group table (finding 1) and the single-class defaults for
  ConstructionSetProject / Level / TextNoteAttributes (12+139) /
  FloorAttributes (4 vs 5 by foundation-slab category) / the default
  GStyle (group 41 = the projection style of category -2000044); (b)
  `PrintSettings` also sets `PrintSettingsTracking.m_idMRU`; (c)
  `RbsVoltageType` -> `RbsSystemNavigatorTracking.m_voltageTypeIdSet`;
  (d) elements emitting ExternalFile / ExternalResource / ESEntity cells
  -> `ElemsSetWithCellsTracking.m_elemIdSetMap` keys 1200 / 1201 / -100;
  (e) `DBViewTypesForNewLevel` = [-1, floor, ceiling, structural]; (f)
  no `CopyWatchProperties` element unless a link exists (or register it
  `m_inDocCopyWatchProps`); (g) the browser-organization registration
  should NOT clear a base's folder cache / expanded nodes / default map
  when the base already carries defaults (only append to `m_elemIdSet`).
  All seven are exercised working in `special_registrations` /
  `build_R3` — lift them.
* **`tools/genesis_assemble.py` (genesis-2)**: the two production
  gaps the audit convicts in G1_candidate/S5 — the def-type map and
  the fully-nulled `CopyWatchModeMgr` parallel rows the purge leaves
  behind (drop rows whose whole parallel tuple is null); and adopt the
  parity engine as the STANDING CHECK for every candidate:
  `parity_compare(K1, candidate)` must read 0 severity-0 for the
  candidate's classes before an upload (this stream's probes all do).
* **`src/rvt/validate.py` (validation)**: the parity engine's
  severity-0 classes (unpopulated mandatory slot, present-row-not-
  indexed, dangling entry not shared with the reference, wrong-class
  slot, missing default of a present class / view family, cell-kind
  membership) are the CONSISTENCY rules the validator is missing — the
  reason every FAILED candidate scores VALID.  `registry_profile` is the
  reference implementation of the walk; the per-registry policy tables
  (`KEYED_POLICY`, `ASSESSED_REGENERABLE`, `CELL_KIND_SETS`) are the
  rule set.
* **`tools/genesis_triage.py` (triage-a)**: two K-ladder confounds this
  stream removes and the census should note — K6 also deleted the
  project pen table (id 2, unreferenced), and the K5 seed never
  contained the `KeynoteTable` itself (it survived; only KeynotingSystem
  was deleted).  Also `purge_ids_from_latest`'s row-DROP for the
  def-type map means a purged singleton's default group VANISHES (not
  nulled) — any add-back / assembler must re-add the group row, not just
  set it.
* **KNOWLEDGE.md owner**: merge findings 1-7.
* **`tools/sync_plugin.py`**: this stream adds `tools/genesis_addback.py`
  only (no `src/` module) — nothing new for the plugin bundle.

## Reproduction (repo root, .venv python)

```
python tools/genesis_addback.py                 # all probes + parity + R3  (~2.5 min)
python tools/genesis_addback.py --only R1,R2s    # some probes
python tools/genesis_addback.py --parity-only    # the audit + R3 (~3 s)
python tools/rvt_validate.py --quiet experiments/genesis/addback/*.rvt      # OK errors=0 (x5)
python -m pytest tests/test_genesis_addback.py -q                           # 23 passed
```

Arbiter output (this session, pasted):

```
OK   experiments/genesis/addback/R1.rvt  errors=0 warnings=1
OK   experiments/genesis/addback/R1s.rvt  errors=0 warnings=1
OK   experiments/genesis/addback/R2.rvt  errors=0 warnings=1
OK   experiments/genesis/addback/R2s.rvt  errors=0 warnings=1
OK   experiments/genesis/addback/R3.rvt  errors=0 warnings=0
```
The one warning on the K1-lineage files is the sample's own pre-existing
extensible-storage decode gap (RebarShape / DataStorage), present on the
pristine sample and on K1 itself; every file also passes the four-registry
coherence census (units 53 / ContentDocs 52 / ContentTable 52 /
FamilyMgr 50 = K1's) and the ADocument self-decode with **0 NEW dangling
ids** (the 1,245 inherited dangles are K1's own R5/R9-proven-tolerated
model residue, present in K1 and every K rung).

## Open questions (need the viewer / the orchestrator)

* The five verdicts, read per §"Reading the verdicts" — **R2s first (or
  together): R2s + R1 + R2 in one batch.**  Every branch of the tree is
  pre-built (R1s bisects an R1 FAIL; R3 is the registry-repair shot).
* If R1 or R2 FAILS with a card message DIFFERENT from
  `Revit-DocumentCorruption` it is a spotlight — the substituted class is
  named by which probe fails (R1 vs R2) and R1s halves R1.
* Whether the default-type map is genuinely REQUIRED (the audit's strongest
  candidate for S5's fatal gap) is settled ONLY by R3's verdict (or by an
  S5+defaults-only variant this stream can emit in seconds from the same
  engine if the orchestrator wants the repairs unbundled: `build_R3` with a
  filter — say the word).
* The 34 severity-1 CONDITIONAL registries (param sets, layout offsets,
  worksharing user map, session state) — deprioritised as regenerable;
  revisit only if R3 PASSES and a minimal repair set is wanted.

## Proposed next tasks (orchestrator decides)

1. Upload **R2s + R1 + R2** (one round); read per §"Reading the verdicts".
2. If **R1 + R2 PASS**: build **G2 = the substitution ladder from the
   passing side** — this stream's `transplant` / `reinstate_reference_
   latest` / `apply_our_registries` / `remap_ids_in_tree` compose it
   directly: start from K1, substitute OUR content class by class (X1
   pen table ... Xn = zero Autodesk-authored elements), viewer-gating each
   rung; the first FAIL names the one class of ours the reader rejects.
3. Upload **R3**; if it PASSES, S5's defect was registry indexing — adopt
   the fix list in the assembler and re-emit the G-line through it.
4. Fold the parity engine into `src/rvt/validate.py` as the consistency
   layer (§Diffs) so a FAILING candidate can no longer score VALID.
5. Merge the seven registry rules into `settings.ADOC_REGISTRY` /
   `apply_adoc_registry` and the KNOWLEDGE findings.

## BRANCH STATE

No VCS (plain directory).  New, uncommitted files: `tools/genesis_
addback.py`, `tests/test_genesis_addback.py` (23 pass), `docs/writer/
registry-parity.md`, `docs/inbox/genesis-addback.md` (this file), and
under `experiments/genesis/addback/`: `R1 R1s R2 R2s R3 .rvt` + `R1 R1s
R2 R2s R3 .json` (per-probe certification records) + `probes.json` (the
upload manifest) + `registry_parity.json` (the full audit).  Every emitted
`.rvt` = arbiter VALID (0 errors), four-registry coherent, ADocument
self-decode clean, **0 NEW dangling references**, and R1 / R1s / R2 /
R2s show **0 severity-0 self-parity divergence** from K1 (R2s reinstates
K1's document object BYTE-FOR-BYTE).  Full suite this session
(`.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`) →
**759 passed, 3 failed** of 762 (845 s); the 3 failures are the
pre-existing, other-stream ones every recent record lists, none touching
this stream's files: `tests/test_plugin_sync.py::test_plugin_is_in_sync_
with_source` (plugin-bundle drift; fix = the orchestrator's
`tools/sync_plugin.py` run — this stream adds no `src/` module) and
`tests/test_provenance.py::{test_G0_resource_refs_are_counted, test_G0_
identity_dit_usernames_still_leak}` (the STALE assertions pinning the
pre-genesis-2 G0 defects, diffed by their owner).  This stream's 23 tests
are among the 759.  STOPPED AT READY — the five probes await the
orchestrator's viewer gate; the substitution ladder from the passing side
(G2) and the validator's consistency layer are the recorded next steps.

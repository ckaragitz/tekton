# genesis-deletion — THE DELETION ENDGAME (delete-with-content by the reduction law) — workstream record, 2026-08-04

Charter: retire, BY THE REDUCTION LAW, everything on the certified base that
must LEAVE rather than be substituted — the 8 curtain-SYSTEM families'
232-element coherent-removal set, the linked-model pair (Group B's designed
deletion), the 99-element Group-A removal queue, and the room-loop / legend /
constraint-dimension content constellations (residue-A's dispositions) — by
the CERTIFIED maxgc reduction + document reconciliation ONLY (deletion-with-
content, NEVER neutralisation), every output passing
`src/rvt/reduce_law.py assert_edit_free(parent, child)` (0 edited survivors).

**Territory touched ONLY:** `tools/genesis_deletion.py` (new),
`tests/test_genesis_deletion.py` (new, 23 pass), `experiments/genesis/
subst_k4/deletion/*` (5 `.rvt` + certification reports + law reports +
`probes.json` + `endgame.json` + `residue_after_D_all.json` + the standing
control), this record.  No existing `src/rvt/*.py`, tool, test or `.rvt` was
edited; `rvt.reduce` (the certified deleter), `rvt.reduce_law` (THE LAW),
`rvt_reduce.build_state_v2 / maxgc` (the arbiter's graph), `rvt.famload.
four_registry_census`, `rvt.validate`, `rvt.genesis.residue_a`
(`curtain_constellation`, `residue_by_class`), `genesis_substitute.
adoc_surface` are IMPORTED.  No browser / viewer use: the five files + the
control + `probes.json` are left for the orchestrator's queue.

## Result in one screen

**Every DELETE-REACHABLE deletion of the endgame is emitted from the
certified ZA_deep and passes every gate: 5 files (D_all + 4 singles), each
`reduce_law.assert_edit_free` EDIT-FREE (0 edited survivors, 0 added ids),
validator VALID (0 errors), structurally proven, four-registry coherent,
Global/Latest + Global/ContentDocuments + Global/PartitionTable + identity
streams BYTE-IDENTICAL to ZA_deep (only `Partitions/21` + `Global/ElemTable`
re-emitted); the deleted ids' ADocument registry entries are LEFT DANGLING
(never nulled, never dropped) and censused per file.**  Reproduce (~6 s):
`.venv/bin/python tools/genesis_deletion.py`.

**And the campaign finding this stream proves with graph + field evidence:
three of the endgame's targets are NOT delete-reachable on ZA_deep — the
`RvtLinkSymbol`, the room-boundary loop, and two type-preview legend
components — and the anchors are OUR OWN landed slots' inherited seq-101
headers / kept wiring (below, §Findings 1–3).  Their retirement is a
CONSTRUCTOR fix (clean-header view rung; area-scheme wiring), not more
deletion.**

Base: `experiments/genesis/subst_k4/residue_a/ZA_deep.rvt` — CERTIFIED
(ledger: "*** GROUP-A RESIDUE LOADS ***", VERDICTS #18; family-free K4
lineage: 1 save unit, 0 embedded documents, ContentTable / ContentDocuments
empty, four-registry COHERENT).  Control: `deletion/CTRL_ZA_deep_base.rvt`
(md5 `56308637529a0d0a95976f5701e2615e`, byte-identical to ZA_deep; stage the
batch with `--control-from experiments/genesis/subst_k4/residue_a/ZA_deep.rvt`
so the gate's generated `CTRL_ZA_deep_b<n>.rvt` copies THIS base).

| # | file | constellation deleted (delete-with-content) | del | law | validator | dangling ADocument ids |
|--:|---|---|--:|---|---|---|
| 1 | **D_all** | curtain systems + link instance side + constraint-dim group (union of the singles) | 240 | EDIT-FREE (removed 240, added 0, survivors edited 0) | VALID 0 err | 94 ids: CategoryElem 40 + GStyleElem 40 (CategoryTracking rows), FamilySurrogate 8 (FamilyMgr), RefPlane 3 (DatumTracking), LinearDimString 1 (ConstraintDimTracking), RvtLinkInstance 1 (RvtLinkInstTracking), CopyWatchProperties 1 (CopyWatchModeMgr ×2 paths) |
| 2 | **D_curtain** | the 8 curtain-SYSTEM families' whole atomic layer: 232 + the 2 surrogate type-previews | 234 | EDIT-FREE (removed 234, added 0, survivors edited 0) | VALID 0 err | 88 ids: CategoryElem 40 + GStyleElem 40 (CategoryTracking) + FamilySurrogate 8 (FamilyMgr) |
| 3 | **D_links** | RvtLinkInstance 1250030 + CopyWatchProperties 1250031 (our Y5 object bound to it) | 2 | EDIT-FREE (removed 2, added 0, survivors edited 0) | VALID 0 err | 2 ids over 4 paths: RvtLinkInstTracking, CopyWatchModeMgr (m_linkDocIds + m_linkCopyWatchProps), ElementTrackingData |
| 4 | **D_content** | LinearDimString 763420 + its 3 locked reference planes 699327 / 699381 / 763366 | 4 | EDIT-FREE (removed 4, added 0, survivors edited 0) | VALID 0 err | 4 ids: RefPlane 3 (DatumTracking + ElementTrackingData), LinearDimString 1 (ConstraintDimTracking) |
| 5 | **D_queue** | the 99-queue's LAWFUL CLOSURE = curtain (234) ∪ dim group (4) | 238 | EDIT-FREE (removed 238, added 0, survivors edited 0) | VALID 0 err | 92 ids (curtain 88 + dim group 4) |

Independent arbiters (this session, pasted): `tools/rvt_validate.py --quiet
deletion/*.rvt ZA_deep.rvt` → 7 × `OK errors=0 warnings=1` (the warning =
the standing Extensible-Storage decode gap on 1 DataStorage element,
untouched); `python -m rvt.reduce_law ZA_deep.rvt deletion/<f>.rvt` → 5 ×
`[EDIT-FREE] ... SURVIVORS EDITED 0` exit 0; `tools/probe_batch.py check
deletion/D_*.rvt` → **ADMISSIBLE** (every probe's base = ZA_deep
`[certified]`).  All five md5s differ; the control's md5 = ZA_deep's.

Set relations (asserted by tests): D_all = D_curtain ∪ D_links ∪ D_content
∪ D_queue; D_queue = D_curtain ∪ D_content; D_all − D_queue = {1250030,
1250031}; the three singles are pairwise disjoint; every set is maxgc-CLOSED
(seed → maxgc deletes exactly the seed, 0 pinned); no set touches the
History-invariant carrier (KeynoteTable 86291, max modified episode) and
no set deletes an OUR-landed slot except the one documented (our
CopyWatchProperties, delete-with-the-link).

Residue after D_all (`deletion/residue_after_D_all.json`): 3,102 elements,
1,805 ours (1,806 − our CopyWatchProperties), 1,297 K4-inherited residue —
Group B's M..Z classes (ParamElem* 791, wire/pipe catalog, definitions,
sketch/ref planes …), the product-data / analysis buckets (HVAC 212, misc
43), and the BLOCKED constellations (link symbol, room loop 8, 2 type
previews) — the honest queue for the next phase.

## The method

Every rung is `rvt_reduce.maxgc` over the arbiter's typed reference graph
(EVERY seq of EVERY record — seq-101 headers included) followed by
`rvt.reduce.delete_elements` (the certified re-blocking deleter behind
R5..R10 / K4).  Before maxgc, each seed is grown to its **delete-with-content
closure** (the referrers of removed content are IN the seed), and maxgc must
then pin NOTHING — a pinned member means the seed was not a coherent
constellation and the rung REFUSES to emit (reports the pins) rather than
silently keeping content.  The policy gate (`reduce_law.law_policy().permits
("maxgc", "reduction-rung")` → ALLOW; `"neutralise-referrers"` → REFUSE)
is asserted at emission.  Global/Latest / ContentDocuments / PartitionTable
/ History / DIT / BasicFileInfo are NEVER touched (asserted stream-by-stream
per file): survivor registry parity is 100% BY CONSTRUCTION, NO live registry
id is nulled (P4/P6), and the deleted ids' ADocument entries are LEFT
DANGLING and censused by `genesis_substitute.adoc_surface` (dangling
ADocument ids are viewer-tolerated: R5 / R9 — and the curtain lineage's own
FamilyMgr already carries the dangling surrogate 876494 in the certified
K4 / Y9 / ZA_deep, so a dangling loaded-family surrogate is proven-legal
IN THIS LINEAGE).

Per-file certification (`deletion/<name>.json`): deletion set + pin
evidence, the `assert_edit_free` verdict + full `EditFreeReport`, `verify_
reduced` structural proof, the validator report, `four_registry_census`,
`stream_identity` (which streams are byte-identical to the base), the
`dangling_census` (deleted ids' ADocument registry surface by class and by
registry path), registry-parity statement, census-after.  Plus
`<name>_law.json` (the standalone law report) per file.

## FINDINGS (evidence [V] = verified this session — merge into KNOWLEDGE.md)

1. **The `RvtLinkSymbol` 1250029 is NOT delete-reachable on ZA_deep, and
   the anchor is OUR OWN view constellation** [V, graph + decoded fields].
   Seven records reference the symbol; six are OUR landed slots:
   DBViewProject 230 (`ElementHeader.m_parents.m_deletion[8]`), DBViewPlan
   245443 / 1064656 (`m_deletion[13]`), DBView3d 1454508 (`m_deletion[5]`),
   the Y2 navigator 69851 (`m_deletion[7]`) — all Y9 / Y2 LANDED — plus our
   CopyWatchProperties 1250031 (deleted here); the seventh, the residue
   DBViewDrafting 1457028, names it in a **validator-gated seq-102 field**
   (`m_pRvtLinkOverrides->RvtLinkOverrides.m_displaySettingsMap[0].first`) and
   its header.  Root cause: **in-place substitution replaced only seq-102
   objects, so OUR slots' seq-101 ElementHeader.m_parents webs are the
   sample's ORIGINALS, and they list the link symbol as a deletion parent**.
   maxgc pins the symbol; deleting it would leave a dangling seq-102 id
   (validator ERROR) and require editing our views' headers (BANNED).  The
   endgame's step-15 assumption ("its referrers ... are LEFT BYTE-IDENTICAL
   with dangling ids") does not hold for PARTITION referrers — only ADocument
   danglers are proven tolerated.  D_links therefore retires the INSTANCE
   side only.  **Fix (substitution stream):** re-emit our view / navigator
   slots WITH OUR HEADERS (a `regadd` full-record in-place rung,
   `seqs=(101,102)`) whose parent lists name only surviving elements; then
   `{symbol + the drafting-view constellation}` (itself pinned by our plans
   245443 / 1064656 + their Viewers) becomes ONE clean maxgc rung — and the
   symbol's external-file name / path (the sample-lineage string) leaves
   with it (or in the own-save identity step).
2. **The room-boundary loop is NOT delete-reachable on ZA_deep, anchored to
   OUR area-scheme object** [V].  The room content {RoomElem 1004910,
   LevelRoomPlan 1004909, 5 area-boundary CurveElems 1004904–08, boundary
   SketchPlane 245433} is contained by `AreaSchemePlanTopologies` 9744 — its
   seq-102 `m_pSet->PlanTopologies.m_set[0].m_levelRoomPlanId` names the
   LevelRoomPlan and its header lists the room + curves as regen children
   (law clause 2: the containing topology leaves WITH its content) — and
   **9744 is pinned by OUR Y5-landed `AreaMeasureElem` 9490**, whose
   seq-102 `m_areaSchemePlanTopologyElemId` (a validator-gated field) +
   header `m_deletion[3]` name it: our constructor KEPT the slot's wiring to
   the sample's plan topology.  Chain: room ← 9744 ← OUR 9490 ⇒ BLOCKED.
   The room stays byte-identical (the law's own alternative).  **Fix
   (settings stream / Y5):** the `AreaMeasureElem` constructor emits
   `m_areaSchemePlanTopologyElemId = -1` (and no header parent to the
   sample topology) on a base whose plan topology is content-to-remove;
   then `{9744 + room content}` is one clean rung.  (Corollary: the room's
   RoomElem, its curves and its LevelRoomPlan do NOT reference each other —
   the "constellation" is held together entirely by 9744; residue-A's
   finding 9 ("AreaSchemePlanTopologies 9744 belongs to the room") is exact,
   the atomicity is the topology's.)
3. **The 4 residue LegendComponents are TYPE-PREVIEW elements, not "graphics
   in a legend view"** [V, decoded fields; `m_ownerDBViewId = -1` on all 4].
   Each type owns its preview via `m_previewElemId` (a validator-gated
   seq-102 field) + a header deletion parent, and the component's own header
   `m_deletion[0]` (+ `m_componentType` where set) names the type:
   BasicWallType 600634 ↔ 907404, FloorAttributes 1201129 ↔ 1201130,
   curtain FamilySurrogate 12610 ↔ 907423, 12614 ↔ 907424.  **A preview
   leaves ONLY with its type**: 907423 / 907424 leave with the curtain
   constellation (they were its ONLY outside referrers — folded into
   D_curtain, delete-with-content); 907404 / 1201130 belong to the residue
   system-family types the types stream substitutes / retires (its
   decision, exactly like the curtain surrogates' previews here).  Corrects
   residue-A's "4 legend graphics displaying types in a legend view" and the
   endgame's step-18 zero-referrer assumption for LegendComponents.
4. **The 8 curtain-SYSTEM families' constellation is EXACTLY coherent**
   [V]: Group A's `curtain_constellation.json` 232-set has precisely TWO
   outside referrers on the live graph — the two surrogate type-previews of
   finding 3 — and with them the 234-seed maxgc-closes (0 pinned).  Its
   ADocument surface = 40 CategoryTracking `m_categoryData` rows + 40 style
   rows (`m_gstyleData.m_categoryId / m_gstyleId`) + 8 `FamilyMgr.
   m_arrLoadedFamilyInfo[].m_surrogateId` entries, LEFT DANGLING (the R9
   shape).  **The curtain lineage ALREADY carries a dangling FamilyMgr
   surrogate (876494 — an entry naming a non-existent element in the
   certified K4 / Y9 / ZA_deep)** [V], so a dangling loaded-family
   surrogate is proven-legal in this lineage; the 9 FamilyMgr entries with
   EMPTY document-GUID lists are the SYSTEM families' registrations (the
   four content registries are untouched: system families own no embedded
   document).  D_curtain IS the endgame's flagged unproven mechanic
   (step 22, "system-family removal has no viewer-passed precedent"),
   isolated as its own single with the certified control.
5. **The linked model's companions on ZA_deep are OUR objects** [V]:
   `CopyWatchProperties` 1250031 and `RvtLinkInstanceAppearanceParentElem`
   132481 were LANDED by Y5 (our settings constellation filled the slots
   the sample link created).  1250031's seq-102 `m_linkId` = the instance ⇒
   it MUST leave with it (delete-with-content of our own object — sanctioned:
   the referrer leaves WITH the content); 132481 references nothing and is
   referenced only by the instance ⇒ KEPT (deleting it would empty
   UniqueElementsTracking positional slot 41 for no gain).  **Hook (settings
   stream):** on a link-free genesis base the Y5 constructors for
   CopyWatchProperties / RvtLinkInstanceAppearanceParentElem should not run.
6. **The constraint-dimension group is CLOSED and its planes leave WITH the
   dimension** [V]: RefPlanes 699327 / 699381 / 763366 name LinearDimString
   763420 in their seq-102 `m_constrInfo[0]->EqConstrInfo.m_constrId` (the
   EQ constraint) + headers; the dimension's `m_witnessRefs[k].
   m_pWitnessRef->GeomSegInPlaneRef.m_geomRef.m_elemId` name the planes;
   nothing else references any of the four ⇒ one atomic unit (endgame §2
   row 3 confirmed) — so the endgame's "only the dimension goes if our
   refplanes stay" branch (step 17) is FALSE on this base: the planes are
   the sample's and MUST leave with the dimension.  Its ADocument surface:
   `DatumTracking.m_elemIdSet` (3 planes) + `ConstraintDimTracking.m_elemIdSet`
   (the dim), left dangling.
7. **The 99-element removal queue is not an independent deletion set**
   [V, live re-derivation: exactly 99]: 88 of its members (72 family-editor
   DBViewTypes + 8 Families + 8 surrogates) are the ATOMIC curtain family
   layer (clause 1 forces their 144 scoped children out with them), and its
   11 content members belong to constellations (dim group 1, blocked room 6,
   blocked type-previews 2, curtain-folded previews 2).  Its LAWFUL CLOSURE
   is exactly D_curtain ∪ D_content (238); D_queue emits that closure.
8. **`SlaveSymbolTrackerElem` 1454535 is NOT curtain machinery on this base**
   [V]: its master is `FabricSheetType` 1352719 (mutual references) — it
   leaves with the fabric-sheet system type (the endgame's "SlaveSymbol
   Tracker (via FabricSheetType)" is right; residue-A's "rides with the
   curtain removal" is wrong on ZA_deep).  Left in place (not in charter).
9. **The endgame's later Phase-III singles, measured on ZA_deep** (recorded,
   NOT emitted — other streams' dispositions / counsel items): surplus
   browser schemes 5/5 delete-reachable (clean leaves — residue-A's explicit
   "surplus-removal"; a D_surplus single or the own-save step); drafting-view
   constellation 0/7 (pinned by OUR plans + Viewers ⇒ the "adopt or delete"
   question is ANSWERED: ADOPT — and it is the second pin on the link
   symbol); HVAC / energy database 207/212 (5 pinned via our
   EnergyDataSettings + the blocked room; counsel item, step 23); misc
   analysis / area machinery 32/43 (AreaType / topology rows pinned by our
   area schemes; step 24); fabric-sheet types + slave tracker 3/3.
10. **The mechanism is proven end-to-end at 240-element scale** [V]: maxgc
    delete-with-content on the in-place-substituted certified base keeps
    every survivor byte-identical (reduce_law EDIT-FREE), leaves the four
    content registries coherent (trivially — no documents move), and the
    unit-0 re-blocker re-flows 16 → 15 blocks with the ISIZE identity and
    every stamp intact; the whole batch builds in ~6 s.

## Diffs / hooks proposed for files OUTSIDE this territory (NOT applied)

* **The substitution / view-constructor stream (Y2 / Y9 owners,
  `tools/genesis_substitute*.py`, `rvt.genesis` view builders)** — finding 1:
  a **clean-header in-place rung**: re-emit our view / navigator constellation
  slots with `regadd.substitute_elements(..., seqs=(101, 102))` so their
  `ElementHeader.m_parents` (deletion / appearance / regen webs) name ONLY
  surviving elements (drop the RvtLinkSymbol parent from views 230, 245443,
  1064656, 1454508, 69851).  General rule to adopt: an in-place substitution
  that keeps the sample's seq-101 header inherits the SAMPLE's dependency
  web — headers are content too.  Provide (or let this stream compute) the
  "residue-anchor census" (§Instruments) as the input list.
* **The settings stream (Y5 owners, `rvt.genesis.settings`)** — findings 2
  and 5: (a) the `AreaMeasureElem` constructor's `m_areaSchemePlanTopology
  ElemId` should be `-1` (no wiring to the sample's plan topology) on a base
  whose topology is content-to-remove — then the room constellation +
  topology 9744 is one clean deletion rung; (b) skip `CopyWatchProperties` /
  `RvtLinkInstanceAppearanceParentElem` on a link-free base.
* **`docs/writer/genesis-endgame.md` (Group B's document)** — corrections
  from the live graph: step 15 (link) — the SYMBOL is pinned by our views'
  headers, partition-dangling is NOT viewer-proven; only the instance side
  is a deletion (this record's D_links) and the symbol waits on the
  clean-header rung; step 16 (room) — atomic via `AreaSchemePlanTopologies`
  9744, blocked by OUR AreaMeasureElem's wiring; step 17 (dim) — the three
  planes MUST leave with the dimension on any base where they are the
  sample's (they name it in `EqConstrInfo.m_constrId`); step 18/19 — the 4
  LegendComponents are TYPE-PREVIEWS owned via `m_previewElemId`, never
  zero-referrer leaves; §2's drafting-view constellation — pinned by our
  plans ⇒ ADOPT branch only; step 22 (curtain) — the set has 2 more members
  (the surrogate previews) and is the endgame's proven-clean atomic unit.
* **`experiments/genesis/subst_k4/residue_a/curtain_constellation.json` /
  `docs/inbox/genesis-residue-A.md` (Group A)** — add the 2 surrogate
  type-preview LegendComponents (907423, 907424) to the coherent-removal
  set (its only outside referrers); reword "4 legend graphics displaying
  types in a legend view" to "4 type-preview components owned by their
  types' `m_previewElemId`"; the tracker note (finding 8).
* **`docs/coverage/viewer-certified.json` (orchestrator)** — add the five
  D files + the control as they read out; every report names its base
  (ZA_deep) + certification + control; on D_all PASS, D_all is the next
  certified deep base (its `residue_after_D_all.json` is the queue).
* **KNOWLEDGE.md owner** — merge findings 1–10; the two general laws worth
  a section of their own: **(i) in-place substitution inherits the sample's
  seq-101 dependency webs — the deletion endgame's real blockers are our own
  slots' inherited headers**; **(ii) dangling ADocument ids are tolerated,
  dangling PARTITION references are not (validator-gated + no viewer
  precedent) — a referrer in the partition leaves WITH the content or the
  content stays**.
* **`tools/sync_plugin.py`** — this stream adds a TOOL (`tools/genesis_
  deletion.py`), NOT a `src/rvt` module: the plugin bundle mirrors `src/rvt`
  only, so no sync is required and `tests/test_plugin_sync.py` is
  unaffected (verified in the full-suite run below).

## Pre-specified follow-up variants (ONE change each; build only on a FAIL)

* **D_curtain_reconciled** = D_curtain's exact deletion + the SANCTIONED
  registry-reconciliation purge (`genesis_triage.purge_ids_from_latest` — the
  schema-typed ADocument purge of EXACTLY the 234 deleted ids: the 8
  dangling FamilyMgr entries + 80 CategoryTracking rows dropped, Revit's own
  deletion semantics).  Variable: dangling vs reconciled registries.  NOTE:
  the ADocument id-purge has no certified precedent on the K4 lineage (its
  neighbour P4/P6 — nulling LIVE ids — is fatal), so it is its OWN rung with
  the control, never a silent addition.
* **D_content_reconciled** = D_content + the same purge of the 4 deleted ids
  (DatumTracking + ConstraintDimTracking entries).
* **D_curtain family-layer bisection** (research-probe purpose ONLY — not
  clause-1-legal as a base): the 8 Families + 8 surrogates + previews WITHOUT
  the sub-category / view-type / font children, and vice versa, to name the
  layer the reader objects to if D_curtain FAILS with the control PASSING.

## Instruments this stream adds (in `tools/genesis_deletion.py`)

* `curtain_constellation / links_constellation / content_constellation /
  queue99 / queue99_closure / build_endgame` — the constellations with their
  graph proof (`outside_referrers` MUST be empty; each blocked constellation
  carries its `anchor_chain` / `pinned_by` with the exact decoded field paths
  via the arbiter's own `_RefDecoder`).
* `adocument_dangling_census(path, deleted_ids)` — the deleted ids' ADocument
  registry surface (by class / by registry path) = what a deletion leaves
  dangling.
* `stream_identity(base, out)` — the per-stream byte-identity proof (only
  `Global/ElemTable` + the partition may differ).
* `next_queue(st)` — the remaining Phase-III candidates with their measured
  maxgc reach-ability (finding 9).
* The **residue-anchor** idea for the constructor streams: for any residue
  set X, `_outside_referrers(st, X)` ∩ landed slots = OUR slots whose
  inherited references pin X — the exact fix list for the clean-header /
  wiring rungs.

## Open questions (need the viewer / a decision)

* The five verdicts, in `probes.json:upload_order_bisection_first` (control
  FIRST, then D_all; the singles only on a D_all FAIL).  Every branch is
  pre-stated per probe (`if_PASS` / `if_FAIL`, `reading_the_results`).
* D_curtain is the batch's real question: SYSTEM-family removal with
  dangling FamilyMgr / CategoryTracking entries (the R9 pattern applied to
  system families for the first time).  On a FAIL: read the card message,
  then D_curtain_reconciled (above).
* Whether the reader accepts an unplaced link (D_links — symbol present,
  instance + copy-monitor gone).  If not, the link waits for the
  clean-header rung and leaves WHOLE.
* The three constructor fixes (clean-header view rung; area-scheme wiring;
  the system-type preview policy) are the substitution / settings / types
  streams' — this record hands over the exact field list.
* Counsel items untouched by design (container layer: the sample's
  ADocument object, Formats/Latest, the Forge corpus; own-save last).

## Verification

* `.venv/bin/python tools/genesis_deletion.py` → 5 × `VERDICT VALID`
  (each: `[EDIT-FREE] ... SURVIVORS EDITED 0`, validator VALID errors 0,
  structural ok, coherent, only-partition+ElemTable-differ True); writes
  `deletion/probes.json`, `endgame.json`, `residue_after_D_all.json`, the
  control; ~6 s.
* `.venv/bin/python tools/genesis_deletion.py --analysis` → the endgame
  decision (constellations / sets / blocked table / next queue), no files.
* `.venv/bin/python tools/rvt_validate.py --quiet experiments/genesis/subst_k4/deletion/*.rvt`
  → 6 × `OK errors=0 warnings=1` (5 probes + the control), independent
  arbiter, this session.
* `.venv/bin/python -m rvt.reduce_law ZA_deep.rvt deletion/<name>.rvt` → 5 ×
  `[EDIT-FREE]` exit 0 (THE GUARD, standalone), this session.
* `.venv/bin/python tools/probe_batch.py check deletion/D_{all,curtain,links,content,queue}.rvt`
  → `ADMISSIBLE`; `resolve` reports base ZA_deep `[certified]` per probe.
* `.venv/bin/python -m pytest tests/test_genesis_deletion.py -q` → **23
  passed** (4 s): the law policy (maxgc ALLOW / neutralise REFUSE), base
  certification, the four constellations + their graph proofs (curtain =
  the JSON 232 + exactly the 2 previews; links = instance side, symbol
  pinned by OUR views' seq-101 headers + the drafting view's seq-102 map;
  content = the dim group, room + previews blocked with seq-102 evidence),
  the 99-queue closure, set relations, no set touches the history carrier /
  our slots beyond the documented one, every set maxgc-closed, an
  end-to-end emission of D_curtain / D_links / D_content in a temp dir
  (verdict VALID, `assert_edit_free` PASS incl. the guard called DIRECTLY,
  validator 0, coherence, byte-identity, dangling census by registry path),
  the probes manifest (bisection-first, certified base resolved by
  `probe_batch.resolve_base`, control md5 = base md5), and the committed
  batch's reports.
* Full suite: see BRANCH STATE.

## BRANCH STATE

No VCS (plain directory).  NEW files, this stream's territory only:
`tools/genesis_deletion.py` (constellations + graph proof + rung operator
+ dangling census + probes manifest + endgame accounting),
`tests/test_genesis_deletion.py` (23 pass), `docs/inbox/genesis-deletion.md`
(this record), and under `experiments/genesis/subst_k4/deletion/`:
`D_all.rvt`, `D_curtain.rvt`, `D_links.rvt`, `D_content.rvt`,
`D_queue.rvt` + one `<name>.json` certification report and one
`<name>_law.json` (the `assert_edit_free` report) each,
`CTRL_ZA_deep_base.rvt` (md5-identical to ZA_deep — the batch control),
`probes.json` (bisection-first, base = ZA_deep certified, control named),
`endgame.json` (constellations / blocked table / next queue),
`residue_after_D_all.json` (the queue after D_all: 1,297 residue elements,
1,805 ours of 3,102).  NO existing `src/` module, tool, test or `.rvt`
edited; no browser / viewer use.  Every emitted `.rvt` = validator VALID (0
errors), structurally proven, `reduce_law.assert_edit_free` EDIT-FREE (0
edited survivors, 0 added ids), four-registry coherent, Global/Latest +
ContentDocuments + PartitionTable + identity streams byte-identical to
ZA_deep, dangling ADocument entries censused per file.

Full suite this session (`.venv/bin/python -m pytest tests/ -q
--ignore=tests/oracle`): **1073 passed, 2 failed** of 1075 (16:29) — this
stream's 23 tests are among the 1073.  The 2 failures are the pre-existing,
other-stream STALE assertions every recent record lists (`tests/
test_provenance.py::test_G0_resource_refs_are_counted` and
`::test_G0_identity_dit_usernames_still_leak` — they pin the
pre-genesis-2 G0's defects; owner: the provenance stream); neither touches
this stream's files.  `tests/test_plugin_sync.py` PASSES (this stream added
no `src/rvt` module, so no plugin sync was needed).

STOPPED AT READY — the five files + control await the orchestrator's viewer
batch (`tools/probe_batch.py stage experiments/genesis/subst_k4/deletion/
D_{all,curtain,links,content,queue}.rvt --control-from experiments/genesis/
subst_k4/residue_a/ZA_deep.rvt`), read control-first then D_all, singles on
a D_all FAIL.  The three constructor fixes (findings 1, 2, 5) and the
pre-specified reconciled variants are the recorded next work; on D_all PASS,
D_all is the next certified deep base and `residue_after_D_all.json` is
its queue.

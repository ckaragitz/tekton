# K1 AUTOPSY — why "R5 minus the placed model" fails when R5 passes

Stream: **genesis-autopsy** (2026-08-04). Subject: `experiments/genesis/triage/K1.rvt`,
the never-uploaded base of the entire substitution program (ORCHESTRATOR
VERDICTS #15). Parent: `experiments/genesis/R5.rvt` (viewer **PASS**). Death:
**CRASH** signature — extractor exit `-1073741831`, *no* `Revit-DocumentCorruption`
line, "Design is empty" (the file passes Revit's structural audit and the
extractor dies afterwards; contrast the **AUDIT** signature `-1073742517` of
K1's constructed children).

Everything below was **measured this session** with `tools/k1_autopsy.py`
(reproduction §8). Evidence: `experiments/genesis/autopsy/autopsy_evidence.json`.

---

## 0. Verdict in one screen

**K1's difference from every viewer-PASSED file is confined to 22 surviving
elements EDITED by K1's neutralise pre-pass, plus ONE deleted room every
passing file keeps.** Nothing else in the file is unaccounted for:

| K1's difference from R5 | measured | disposition |
|---|---:|---|
| elements deleted | 2,117 | **2,115 are ALSO deleted by the CERTIFIED ladder** (2,084 by R9, 31 by R6); the 2 exceptions: title-block instance 1457033 (deleted by the PASSING K4 → vindicated) and area RoomElem **1004910** (kept by R9/R10/K3/K4 → the ONE unvindicated deletion) |
| surviving elements modified | **23** | 1 byte-vindicated (sheet 1457028 = the passing K3/K4 record byte-for-byte); **22 in byte-states NO passing file carries** |
| global streams | `Latest` `History` `ContentDocuments` `BasicFileInfo` `DocumentIncrementTable` `PartitionTable` `Contents` `Formats/Latest` `ProjectInformation` `TransmissionData` | **byte-identical to R5's and R9's** (sha-256 of the logical streams); only `Global/ElemTable` + `Partitions/21` differ (the deletion itself) |
| `Global/Latest` dangling ids | 1,066 | a **subset of R9's tolerated 3,014** except ONE id: room 1004910 |
| four-registry content census | units 53 / CD 52 / CT 52 / FamilyMgr 50·52 | **identical to R5 and R9** (content machinery untouched) |

K1 was built in **two steps** (`tools/genesis_triage.py::build_K1`): step 1
`neutralise_referrers` (`rvt.manipulate` — the M2/M3-certified modify path)
**edited 404 surviving referrers of the placed model**; step 2 maxgc-deleted
the model. The autopsy proves step 2 is a pure delete (0 survivor records
touched) and that **381 of the 404 edited elements were then deleted** — the
transient `CurveElem` / `LinearDimString` / `Alignment` edits leave no
surviving record. **Exactly 23 edited elements survive.** The certified ladder
v2 (R5..R10) is **pure maxgc deletion — no stage ever edits a survivor**
(`docs/inbox/genesis-reduction.md` §4: "the boundary is entirely 'requires
editing a survivor'"). K1 is the first file in the genesis lineage to edit
survivors of these classes; K3 (which also neutralises, and PASSES) touched
only usage fields of view/annotation *type* elements — one of which
byte-vindicates K1's sheet edit.

**Two proofs close the accounting.** (1) *Recomposition*: R5 + all six edit
classes + maxgc reproduces K1 **byte-record-exact** (identical 2,117-id
deletion set, identical 23 edited records). (2) *Redundancy of the transient
class*: R5 + only the 12 **persistent** referrer classes + maxgc already
reproduces K1 record-for-record — the CurveElem/LinearDimString/Alignment
pin-cutting unlocks **nothing** (G6 exonerated analytically; that file, a
twin of K1, is not a probe).

---

## 1. The removal diff (K1 vs R5), certified against R6..R9

K1 deletes 2,117 host-document elements from R5 (K1a's edit-free maximum is
599 — the neutralisation edits unlock the other 1,518). Per certified stage
that ALSO deletes the id (the ladder is cumulative: R6 ⊃ R7 ⊃ R8 ⊃ R9 ids):

| certified stage that also deletes it | count |
|---|--:|
| **R9** (families + placed model gone, viewer PASS) | **2,084** |
| **R6** (views gone: 29 view-owned annotation `FamilyInstance`s of the 'Title Sheet' / legend views, 1 `StairsPathElement`, 1 `ImageInstance`) | 31 |
| **kept by R9** (never certified-deleted) | **2** |

The two: **1457033** `FamilyInstance` (the A1-metric title block on sheet
'Framing Plans' — present in R9/R10/K3, **deleted by K4 which PASSED** →
vindicated) and **1004910** `RoomElem` (an *area*, kept by R9, R10, K3 and K4
alike; its deletion also puts the ONE Latest-dangling id K1 has beyond R9's
set — in `ColorFillSecondaryData`, `RoomTracking.m_areaIds`,
`ElementTrackingData`, the same registries R9's 30 deleted rooms dangle in →
tolerated). Deleted classes: `FamilyInstance` 497, `RebarInSystem` 224,
`CurveElem` 210, `LinearDimString` 201, `ReferencePoint` 128, `Rebar` 122,
`Hub` 122, `AnalyticalMember` 90, `SketchPlane` 89, `VarSketch` 84,
`RegenSplitterElem` 68, `DPart` 45, `RebarSystem` 44, `LineLoad` 35,
`RoomElem` 31, `PostedWarningElem` 22, `BoundaryConditions` 20, … , the
`GCSTracker` / `HubsTracker` cache singletons — every one also deleted by R9.
**The deletion recipe is not the crime scene.**

---

## 2. The survivor-modification check — the crime scene

A reduction leaves survivors byte-identical; K1's does not. The 23 modified
survivors (all host elements; leaf counts = decoded field changes across
seq 101 header + seq 102 object):

| id | class | name | group | leaves | in R9? | edit |
|---|---|---|---|--:|:-:|---|
| 876569 | FamilySymbol | (in-place 'building option') | **G4** | 6 | ✗ | `m_familyId → -1`, `m_ownerInstanceId → -1` — **its Family 876493 DELETED**; the symbol is **registry-indexed** as a category DEFAULT (`SymbolIdMgr.m_defCatSymIds`) and in `BasedOnTracker` |
| 876494 | FamilySurrogate | building option 2 | G4 | 3 | ✗ | `m_elemId → -1` (surrogate depicting nothing) |
| 876570 | FamSymSurrogate | building option 1 | G4 | 1 | ✗ | `m_parents.m_regenOnly` pruned |
| 513310 | StairsTriserSymbol | — | G4 | 5 | ✗ | `m_hostId → -1` (its stairs deleted) |
| 1250040 | DBViewGraphSchedColumn | Graphical Column Schedule | **G3** | 273 | ✗ | whole `m_visGridIntPntArr` **struct entries dropped** (each named a deleted column in `m_columnIdArr`), collaterally dropping references to **still-present grids** and per-entry `m_pDoc` weakrefs |
| 1004909 | LevelRoomPlan | — | **G5** | 2 | ✓ (unedited) | `m_planTopology.m_rooms[]` pruned of area 1004910 |
| 9744 | AreaSchemePlanTopologies | — | G5 | 2 | ✓ (unedited) | `m_parents` regen children pruned of 1004910 |
| 8231 | InteriorElevArrow | — | G5 | 2 | ✗ | `m_endAttach0.m_geomRef.m_elemId → -1` (attached to nothing) |
| 1141621 | DBView3d | Structure (Complete) | **G2** | 7 | ✗ | hidden-element list + `m_parents` pruned |
| 1250103 | DBView3d | Structure (Foundation) | G2 | 563 | ✗ | idem |
| 1383083 | DBView3d | Structure 3D box Wall | G2 | 82 | ✗ | idem |
| 1386343 | DBView3d | Central Pile | G2 | 916 | ✗ | idem + `m_oAdHocOverrides.m_elementMap` entries dropped |
| 1457170 | DBView3d | Central Pile — 3D | G2 | 916 | ✗ | idem |
| 1199134 | DBViewSection | Section Wall | G2 | 306 | ✗ | idem |
| 1456455 | DBViewRendering | Structure Complete | G2 | 2 | ✗ | `m_imageInstanceId → -1` |
| 1456977, 1457045, 1457064, 1457151, 1457181, 1457199, 1457228 | DBViewDrafting ×7 | sheets | **G1** | 2 each | ✗ | `m_sheetTitleBlockId → -1` — same edit as… |
| **1457028** | DBViewDrafting | Framing Plans | G1 | 2 | ✓ | …the sheet **byte-identical to the PASSING K3/K4 record** ⇒ the whole G1 edit class is proven reader-legal |

Not on the list — and telling: the keeper `{3D}` view (1454508) is **not**
edited; the five edited 3D views are the sample's *structural* 3D views,
which R9 deleted at R6. Every edited class is one R9 never carried in this
state: R9 deleted the views, sheets, schedule, room plans and family layer
*with* their content; K1 kept them and rewrote them.

**The mechanism, exactly.** `rvt.manipulate._neutralise` applies three rules to
every survivor field naming a placed id: scalar → `-1`; bare id in a list →
removed; *"a structured entry inside a list that mentions a target anywhere
→ the whole entry is DROPPED"*. That third rule is what butchers the graphical
column schedule (dropping grid-intersection structs together with their
live grid ids), and the second/first are what orphan the type layer. These
are *Revit-semantics guesses* — reasonable for hidden-element lists (Revit
does prune them), never validated for schedules, surrogates, riser symbols,
arrows or plan topologies. K1 is where all of them met the reader at once.

---

## 3. Ranked suspects (for the CRASH signature)

The audit did **not** fire (the ids all exist and reference each other
consistently); the **extractor** crashed while walking the document. Ranked by
crash-plausibility × unprecedentedness, each is a one-file probe in the ladder:

1. **G4 — the orphaned, registry-indexed FamilySymbol** (876569, family →
   -1). A live *default type* (indexed by `SymbolIdMgr.m_defCatSymIds`) whose
   family pointer is null: id-existence checks pass; any walker that resolves
   symbol → family dereferences null. Probe: **`K1_suspect`** (this and
   nothing else: 78 deleted, 3 edited records byte-identical to K1's) and
   **`K1e_orphaning`** (the group in K1's full context, stairs riser included).
2. **G3 — the graphical column schedule** with wholesale-dropped
   grid-intersection structs (273 leaves; a view state Revit itself never
   writes — it *regenerates* this table). A rendered view. Probe:
   **`K1d_schedule`**.
3. **G5 — plan-topology / attachment surgery**: the area `LevelRoomPlan` /
   `AreaSchemePlanTopologies` pruned of the one area every passing file
   keeps (and that area deleted), the interior-elevation arrow attached to
   nothing. Probe: **`K1f_topology`**.
4. **G2 — the 3D / section view state maps** (hidden-element lists, ad-hoc
   overrides, header parent webs — up to 916 leaves per view; the largest
   edit volume but the class of edit closest to Revit's own delete). Probe:
   **`K1c_viewmaps`**.
5. **G1 — sheet title blocks: EXPECTED PASS** (byte-vindicated by K3/K4).
   Probe: **`K1b_sheets`** — the ladder's *internal* control that the
   neutralise + delete mechanics themselves are accepted.

Deliberately **not** a suspect: the deletion set (R9-vindicated), the
transient G6 sketch/dimension edits (analytically redundant, §0), the
ADocument (byte-identical to R9's; dangling ⊂ R9's + one tolerated room), the
content registries (census identical).

---

## 4. THE LAW

> **A referrer of removed content is either DELETED WITH the content or LEFT
> BYTE-IDENTICAL; it is never "neutralised" into a state no Autodesk file
> exhibits.** Concretely, the reduction ladder / substitution engine MUST
> obey:
>
> 1. **Family/type layer is atomic.** `Family` + `FamilySymbol` +
>    `FamilySurrogate` + `FamSymSurrogate` + `StairsTriserSymbol` + `m_famId`
>    children + instances are removed TOGETHER (R9 / K3-K4 pattern) or not at
>    all. Never null `FamilySymbol.m_familyId`, `FamilySurrogate.m_elemId` or
>    a symbol's `m_hostId` while the symbol survives — least of all a symbol
>    the ADocument indexes as a category default.
> 2. **Never drop structured entries from a survivor's arrays** (schedule
>    `m_visGridIntPntArr`, plan-topology segments, connector/ref entries):
>    the containing view/topology is deleted with its content, or the content
>    is kept. `_neutralise`'s "drop the struct that mentions a target" rule is
>    BANNED for genesis output.
> 3. **View state maps go with the view.** A model view (3D / section /
>    rendering / graphical schedule) whose content is being removed is
>    DELETED (with its `Viewer`/`DBDrawing`/viewport companions and the sheets
>    that place it), exactly as R6 does — not un-hidden / un-overridden. (If
>    K1c PASSES this clause relaxes to "hidden/override pruning is legal";
>    the ladder decides.)
> 4. **Whatever remains is byte-identical to a viewer-PASSED source.** The
>    only sanctioned generator of a reduced base is `maxgc` over the
>    validator's own reference graph — dangling-free by construction, zero
>    survivor edits — plus the FOUR-registry document reconciliation (KD1)
>    when embedded documents are removed. A rung that "needs to edit a
>    survivor" is a rung that must instead put that survivor in the seed.
> 5. **A base is CERTIFIED before anything is built on it** (the standing
>    hard law), and *the empty project that KEEPS the sample's
>    model-referencing view constellation is not delete-reachable* (K1v
>    §5: the model-viewing views are pinned by viewports on the surviving
>    sheets) — so the certified shape of "empty" is R9's / K4's: those views
>    leave with the model.
>
> **Corrected K1 recipe (mechanical from the round-1 verdicts):** for every
> edit group whose single rung FAILS, DELETE that group's referrers with
> their content instead of neutralising them; keep the groups whose rungs
> PASS (their edits are then proven reader-legal). If ALL five single rungs
> PASS, the killer is a ≥2-group interaction and the safe recipe is to delete
> ALL 22 unvindicated referrers with the model (K4/R9's certified shape).

---

## 5. The bisection ladder (`experiments/genesis/autopsy/`, manifest `probes.json`)

Every rung derives from **certified R5** in ONE step (no rung stacks on an
untested base); all are `rvt_validate` VALID (0 errors, the corpus-wide
DataStorage/RebarShape warning only); `CTRL_R5_recheck.rvt` is a
byte-identical copy of R5 (md5 `f0e39d21…` = R5's) — the batch's certified
control. Each single-group rung carries **K1's byte-identical edited
records** for its group's referrers (proven) and differs from
`K1a_editfree` by that one edit class plus the deletions it unlocks.

| # | file | what it is (vs its PASSING sibling) | deleted | elements | if FAIL means |
|--:|---|---|--:|--:|---|
| 1 | `CTRL_R5_recheck.rvt` | md5-identical R5 (oracle health / base control) | 0 | 8,657 | oracle sick — void the batch |
| 2 | `K1a_editfree.rvt` | R5 minus maxgc(placed model), **zero edits**: K1 with its entire novelty removed. THE ladder base | 599 | 8,058 | deletion set fatal *with views present* (contradicts R9-vindication) → bisect deletions |
| 3 | `K1_suspect.rvt` | R5 minus ONLY the in-place family 'building option' + orphaning of its symbol/surrogates (3 records = K1's bytes); nothing else touched | 78 | 8,579 | **orphaning a live registry-indexed type is fatal at any scope** — law clause 1 proven |
| 4 | `K1e_orphaning.rvt` | K1a + the G4 edits (symbol/surrogates/riser symbol) in full context | 677 | 7,980 | clause 1 |
| 5 | `K1d_schedule.rvt` | K1a + the G3 graphical-column-schedule edit | 969 | 7,688 | clause 2 |
| 6 | `K1f_topology.rvt` | K1a + the G5 topology/arrow edits (+ room 1004910 deleted) | 600 | 8,057 | topology surgery / the kept-room deletion is fatal |
| 7 | `K1c_viewmaps.rvt` | K1a + the G2 view state-map edits (5 3D + section + rendering) | 859 | 7,798 | clause 3 |
| 8 | `K1b_sheets.rvt` | K1a + the G1 sheet edits — **expected PASS** (K3/K4-vindicated); the internal control | 607 | 8,050 | the vindication argument is wrong (K1's blocking differs from K3's) — re-examine |
| 9 | `K1v_delete_referrers.rvt` | the delete-only maximum: K1a + the 23 referrers deleted WITH the content they release, still **zero edits** | 696 | 7,961 | a zero-edit sibling of K1a fails → the referrer-layer deletion delta names it |

**Reading the batch** (also encoded in `probes.json:reading_the_results`): CTRL
FAIL → void. **K1a PASS + exactly one K1x FAIL → that group's edit class IS
the mechanism; its clause is the law.** K1a PASS + all K1x PASS → the killer
is a ≥2-group interaction: pairwise unlocks are tiny (G3+G2 = 28, G4+G2 = 18);
~755 deletions need ≥3 groups' pins cut (the model is ONE connected
pin-component — `autopsy_evidence.json:unlock_table`, whose simulator matches
every real rung's deletion count exactly); round 2 = `--pair` rungs, or
skip straight to law clause "delete the referrers with the model". K1a FAIL
→ the deletion set is fatal in the views-present context (an untouched view
cannot survive its emptied model) → bisect the deletion classes on R5.
Worst case: **round 1 names the group, round 2 the element, round 3
confirms — ≤ 3 viewer rounds.**

---

## 6. What K1v additionally established (an analytic finding, no viewer needed)

`K1v_delete_referrers` seeds the 23 referrers themselves for deletion *with*
their content and still collects only **696** elements (vs K1's 2,117): the
model-viewing 3D/section views are **pinned by viewports on the surviving
sheets** (`DBViewDrafting <- Viewport <- DBViewSection ×9`, `Section ×8` …)
and the browser/project constellation. **"The empty project that keeps the
sample's whole view/sheet constellation" cannot be produced by deletion** —
which is precisely why K1's author reached for the neutraliser. R9's
certified answer is that the sheets and model views leave *with* the model.
Genesis inherits that answer: a constructed base authors its own (empty)
view set; it does not carry a sample's model views over an empty model.

---

## 7. Instruments and gotchas

* `element_diff` / `field_diff` (k1_autopsy) — record-byte comparison over all
  three seqs is the correct survivor-modification instrument; the ElemTable
  alone cannot see a modified record (it saw K1 as "6,540 clean rows").
* The K3/K4 **byte-vindication** technique — an element also present in a
  PASSING file, compared byte-for-byte — settles legality without a viewer
  round; it retired 8 of the 23 suspects (G1) before any upload.
* `unlock_table` — the in-memory group-set simulator (cut S-class survivor →
  target edges, then maxgc) matches every real rung (599/607/859/969/677/
  600/2,117); use it to size any pair/triple before building it.
* `Document.from_file` id maps span all save units; restrict to
  `et_by_id` (host) for reduction diffs.
* `rvt.manipulate.session()` is cached on the Document — reset `work` /
  `plans` / `removed` per probe or an earlier probe's neutralised working
  copy leaks into the next (k1_autopsy resets it explicitly).
* `genesis_triage.census` reports `familymgr_entries: None` for R5-lineage
  files in its own K1.json (a decode-path difference), yet the four-registry
  tuple is identical R5 = R9 = K1 when re-run — the content machinery was
  never in play.

## 8. Reproduction (repo root, `.venv/bin/python`)

```
tools/k1_autopsy.py --analyze        # the diff / cross-reference / streams / Latest → autopsy_evidence.json
tools/k1_autopsy.py --recompose      # the recomposition proof (all six edit classes == K1, byte-record-exact)
tools/k1_autopsy.py --unlock         # the group-set unlock simulator + validation vs the real rungs
tools/k1_autopsy.py --build          # the ladder + probes.json  (~7 min)
tools/k1_autopsy.py --pair G3_schedule+G2_viewmaps   # round-2 interaction rung on demand
tools/rvt_validate.py --quiet experiments/genesis/autopsy/*.rvt   # 9 x OK (0 errors, 1 known warning)
```

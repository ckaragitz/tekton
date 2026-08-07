# subtractive — THE SUBTRACTIVE LADDER on U16 (staged, batch 46)

Stream: **subtractive** (2026-08-05).  Charter: verdicts #39 read batch 45
as an INVERSION — the donor famdoc body accepts everything of ours (U16 +
U12345 + all pairs PASS) while nothing swapped into OUR lean document saves
it (F1, F2/F3/F4, H8B all FAIL, B0 FAIL).  So the audit requires something
the donor's remaining body elements PROVIDE and our lean 41-element famdoc
LACKS (missing element infrastructure), or a whole-document property
(element order / unit shape).  This round runs the subtractive
delta-debugging ladder on **U16** (the certified-PASS substrate): delete
the donor's extra elements by CLASS-GROUP under a lawful famdoc deletion
discipline until the PASS flips to FAIL — the flip names the required
infrastructure.  The order hypothesis gets its own probe from the other
direction (SUB_O1).

**Territory touched ONLY:** `tools/subtractive.py` (new),
`experiments/subtractive/**` (new), `tests/test_subtractive.py` (new), this
record, and the staging copies `probe_batch` itself writes under
`experiments/acceptance/`.  `tools/famdoc_final.py` (the U16 recipe:
`make_union_doc`, `famdoc_reference_resolution`, `_b0_style_gates`,
`donor_frame`), `tools/famdoc_bisect.py` (donor loading, dev-rfa RefDecoder
gate, famload, placement), `tools/famdoc_blobs.py` (blob gate),
`tools/bisect_instance_bug.py`, `tools/probe_batch.py`, `tools/ifc_intent.py`
are IMPORTED, never edited.  No `src/**` edits.  No browser (STAGE only —
the orchestrator uploads); no Autodesk install dirs; zero donors in shipped
output (every probe PROOF-ONLY, quarantined); no full-suite runs
(SUITE-COORDINATION).

## Result in one screen

* **THE SUBTRACTIVE ROUND IS BUILT, GATED AND STAGED AS BATCH 46** — 11
  probes + 2 controls, every probe `rvt.validate` **VALID 0 errors / 0
  unexpected**, four-registry **coherent** (+1 unit load hop, instance hop
  registry-silent), survivor law 0/0, identity **PASS**, schema-typed
  reference resolution **unresolved-anywhere = 0 on every famdoc**, **every
  save unit of every probe carries the 64-byte 0x0f3f blob with the added
  unit's nonce byte-verified**, deletion residual scan **0 on every
  survivor of every probe**, both controls + all 13 staged copies
  md5-verified.  `verify` re-run post-build: **11/11 gates_ok**.  **39
  stream-local tests pass.**
* **THE DONOR IS CLASSIFIED, EXACTLY** (§1) — the frame (6) is measured
  hard-self-contained; the remaining **411** donor elements partition into
  **seven class-groups** (S1 13 / S2 11 / S3 19 / S4 85 / S5 125 / S6 116 /
  S7 42), with the full class→group map printed below and pinned by tests.
  The roster equivalence (~26 donor elements playing our 41 roles; the
  connector layer has NO donor equivalent) is recorded as metadata — U16
  carries OUR copy of every roster class, so no deletion ever removes a
  roster class from the document: **a flip convicts donor-only
  infrastructure.**
* **THE FAMDOC DELETION LAW WORKS** — cascade closures computed from the
  measured reference graph (registry surfaces scrubbed, hard referrers
  cascaded, ownership children die with parents), ONE detach normalization
  (`LevelAttributes.m_familyTagId → -1`, our famgen's own certified form,
  fires only in SUB_S6), and a build-refusing residual scan that proved 0
  leftover references on every probe.  SUB_ALL lands EXACTLY on the lean
  shape: **452 → 41 elements** (donor frame 6 + our carried 35).
* **SUB_O1 tests the order hypothesis from the other direction** — our
  famdoc with 38/41 ids re-assigned so ascending-id order follows the
  donor's convention (styles-before-family artifacts aside, the donor puts
  the self-Family first among our roles, viewer-before-view, UnitsElem late
  at ~21st, params late, geometry mid; ours authored UnitsElem 2nd, params
  mid, geometry last), through the EXACT B0 recipe (famgen loader on
  G_ABPD under `corpus_symbol_form`, demo placement).
* **author_spec.json sketches what famgen would need to AUTHOR** for the
  top-2 prior groups (S5 styles/categories/fonts, S6 nested annotation
  family) at panelboard class — donor structure from the column, counts
  from the RME panelboard donor (549 elements: **84 CategoryElem + 84
  GStyleElem + 41 FontElem + 31 DBViewTypes + 3 nested annotation
  families**; electrical famdocs carry MORE of this furniture than the
  structural column, not less), honest unknowns listed.

## §1  THE CLASSIFICATION (the charter's centerpiece)

Donor = `M_Concrete-Square-Column` (rst unit 36, 417 elements, 72 classes).
**FRAME** (kept in every probe): self-Family 1410872 + UnitsElem 1411008 +
project-view chain 1410913/1410912/1410914/1410915 — measured: their only
non-registry references are to each other (`closure(frame) = frame`).

The seven groups over the other 411 (sizes pinned by tests):

| group | n | what it is | cascade pulls (closure−seed) |
|---|--:|---|--:|
| S1 sketch/geometry infra | 13 | donor extrusion + its sketch (VarSketch, 4 CurveElem, SketchPlane) + 3 standalone sketch-stub pairs | +6 (its alignments) |
| S2 dims/constraints | 11 | LinearDimString 4 + Alignment 7 outside the nested family (RadialDim: all nested) | +0 (clean sink) |
| S3 datum/reference infra | 19 | 2 Levels, LevelAttributes + its cat/gstyle/font furniture, 7 RefPlanes, 2 datum-hosted SketchPlanes, BaseLevelTracker, TrueNorth | +57 (plan/section view furniture crops to these planes and follows: 6 Viewer + 6 DBDrawing + 6 Viewport + 6 ExtentElem + 6 SketchGrid + 6 view SketchPlanes + 4 DBViewSection + 2 DBViewPlan + dims + the extrusion-sketch chain) |
| S4 view/annotation locals | 85 | 11 extra DBViewTypes (10 more are nested), 4 sections + 3D + 2nd plan chains (Viewer/DBDrawing/Viewport/ExtentElem/SketchGrid/view SketchPlanes), CalloutTag + SectionAttributes + InteriorElevAttributes (+their cat/font subtrees), Sun, 2 BrowserOrganization, ModelClipBox, Viewer3d | +21 (7 RefPlanes via crop extents, dims, 2 sketch stubs) |
| S5 styles/categories/fonts | 125 | DimensionStyle 8 + LeaderStyle 7 + SpotElevationStyle 3 + TextNote/TagNote/FilledRegion attrs + Text3d + RevisionCloud + ReferenceViewer + their OWNED CategoryElem 43 / GStyleElem 43 / FontElem 15 subtrees | +12 (the dims/alignments styled by them; 1 nested dim) |
| S6 nested level-head family | 116 | Family 1411054 'Level Head - Upgrade' + its 112 registered members (its own 10 DBViewTypes, 3 DimensionStyles, filled regions, tag notes, 2D curves, dims, drafting-view chain) + FamilySymbol + FamilySurrogate + FamSymSurrogate | +0 (clean, with the ONE detach) |
| S7 struct/settings residue | 42 | LoadNature 8 + LoadCase 8 (universal family-editor furniture — the ELECTRICAL panelboard donor carries them too), StructConnectionType 5, AnalyticalLinkType, StructSettings + the settings singletons (area/autocam/autojoin/coordsys/divide/draworder/dwg/step/pen/daylight/appearance-parents/…), the SF's ONE ParamElemFamily | +2 (dims labeled by the param) |

**Full class→group map** (counts; 72 classes, Σ=417):

```
Alignment S2:7 | AnalyticalLinkType S7:1 | AreaSettingsElem S7:1
AutoCamSettingsElem S7:1 | AutoJoinTracker S7:1 | BaseLevelTracker S3:1 S6:1
BrowserOrganization S4:2 | CalloutTag S4:1 S6:1
CategoryElem S3:2 S4:5 S5:43 S6:18 | ComponentRepeaterSlotSpecialType S7:2
CoordinateSystemDisplayElem S7:1 | CorniceAttr S6:1 S7:1 | CoverType S6:1 S7:1
CurveElem S1:4 S6:7 | DBDrawing FRAME:1 S4:7 S6:1 | DBView3d S4:1
DBViewDrafting S6:1 | DBViewPlan S4:2 | DBViewProject FRAME:1
DBViewSection S4:4 | DBViewType S4:11 S6:10 | DaylightSourceIdSet S6:1 S7:1
DefaultDivideSettings S7:1 | DimensionStyle S5:8 S6:3 | DrawOrder3dElem S7:1
Dwg2dExportUserSettingsData S7:1 | ExtentElem S4:7 | ExtrusionElem S1:1
FamSymSurrogate S6:1 | Family FRAME:1 S6:1 | FamilySurrogate S6:1
FamilySymbol S6:1 | FilledRegion S6:2 | FilledRegionAttributes S6:2
FontElem S3:1 S4:5 S5:15 S6:10 | GStyleElem S3:2 S4:5 S5:43 S6:18
InteriorElevAttributes S4:1 S6:1 | LeaderStyle S5:7 S6:3 | Level S3:2
LevelAttributes S3:1 | LinearDimString S2:4 S6:7 | LoadCaseElem S7:8
LoadNatureElem S7:8 | ModelClipBox S4:1 | ParamElemFamily S6:1 S7:1
PenWidthTableElem S6:1 S7:1 | PropertyAttr S6:1 S7:1 | RadialDim S6:3
RefPlane S3:7 S6:2 | ReferenceViewerAttributes S5:1 | RevealAttr S6:1 S7:1
RevisionCloudAttr S5:1 | RvtLinkInstanceAppearanceParentElem S7:1
STEPExportSettings S7:1 | SectionAttributes S4:4 S6:1 | SketchGrid S4:8
SketchGridAppearanceParentElem S7:1 | SketchPlane S1:4 S3:2 S4:6 S6:3
SpotElevationStyle S5:3 | StructConnectionType S7:5 | StructSettingsElem S7:1
SunAndShadowSettings S4:1 | TagNote S6:2 | TagNoteAttributes S5:1 S6:1
Text3dAttrSymbol S5:1 S6:1 | TextNoteAttributes S5:2 S6:1
TrueNorth S3:1 S6:1 | UnitsElem FRAME:1 | VarSketch S1:4 S6:3
Viewer FRAME:1 S4:6 S6:1 | Viewer3d S4:1 | Viewport FRAME:1 S4:7 S6:1
```

Assignment law (structural, per-element, test-pinned): frame roles by
`famdoc_final.donor_frame`; nested-cluster membership = the nested Family's
own `m_familyIds` registry (112 members — the SF registers only 304 = 417 −
112 − self, measured) + the Family + symbol + surrogates; CategoryElem /
GStyleElem / FontElem follow their OWNER constellation's group (every one
of the 68+68+31 is owned by an annotation attr — there is NO free-floating
category table in the donor); SketchPlanes by role (`m_ownerDBViewId` set →
S4 view plane; `m_userId` set → S1 sketch's plane; else S3 datum-hosted);
everything else by class.

**Measured structural discoveries the next rounds should know:**

* The category/style/font system is annotation-attr FURNITURE: attrs own
  their CategoryElems (which own their GStyleElems) and FontElems, with
  mutual Category↔GStyle references and owner backrefs.
* The nested 'Level Head - Upgrade' family is a COMPLETE mini-famdoc inline
  (own view types ×10, own styles, own drafting-view chain, 2D filled
  regions/tag notes/curves/dims), registered in the outer unit's element
  space, bound to the datum by `LevelAttributes.m_familyTagId → its
  FamilySymbol`.  OUR famgen authors `m_familyTagId = -1`.
* The donor's reference topology decomposes into REGISTRY surfaces (header
  `m_parents` lists; a Family's nine membership surfaces; a VarSketch's dim
  lists) vs HARD field refs — the deletion law scrubs the former and
  cascades the latter, and the residual scan proves the dichotomy is
  exhaustive on every probe.
* Even the ELECTRICAL panelboard famdoc (rme unit 30, 549 elements)
  carries LoadCase/LoadNature pairs, 31 view types, 84+84+41
  cat/gstyle/font locals and THREE nested annotation families — this
  furniture is universal family-editor infrastructure, not
  structural-category residue.

## §2  The ladder (staged reading order = maximum information first)

All probes `experiments/subtractive/<rung>.rvt`, staged byte-identical to
`experiments/acceptance/`; manifest `experiments/acceptance/batch_46.json`.
Fresh GUIDs are minted per rebuild — re-hash after any rerun.

| # | rung | md5 | base | deleted → left | the ONE thing it tests |
|--:|---|---|---|---|---|
| 1 | **SUB_ALL** | `7bf5ad5a` | rst | 411 → **41** | the anchor: U16 minus ALL groups = donor frame + our 35 = OUR lean shape reached by deletion (expected FAIL) |
| 2 | **SUB_S5** | `ca7c317a` | rst | 137 → 315 | styles/categories/fonts (top prior: the largest family our famdoc lacks ENTIRELY) |
| 3 | **SUB_S6** | `32c3df5b` | rst | 116 → 336 | the nested level-head family cluster (with the one detach) |
| 4 | **SUB_S4** | `ce33b78a` | rst | 106 → 346 | view/annotation locals (extra view types + section/3d/drafting/2nd-plan chains) |
| 5 | **SUB_S7** | `c875686c` | rst | 44 → 408 | struct/settings residue (load cases, struct types, settings singletons, the SF param) |
| 6 | **SUB_S2** | `5a0d73db` | rst | 11 → 441 | dims/constraints (clean sink; zeroes only `Alignment` document-wide) |
| 7 | **SUB_S1** | `2d4af5c0` | rst | 19 → 433 | donor sketch/geometry infra (OUR carried geometry remains) |
| 8 | **SUB_S3** | `62240e13` | rst | 76 → 376 | datum/reference infra + the view furniture that crops to it |
| 9 | **SUB_S5A** | `3071576a` | rst | 129 → 323 | the dim-flavored HALF of S5 (Dimension/Leader/SpotElevation constellations) — the pre-built bisection of the top-prior group |
| 10 | **SUB_S5B** | `711a55bc` | rst | 16 → 436 | the text/region-flavored HALF of S5 |
| 11 | **SUB_O1** | `957e287f` | G_ABPD | perm 38/41 | ELEMENT ORDER: our famdoc renumbered to the donor's convention through the EXACT B0 recipe |

Controls: `CTRL_rstbasicsampleproject_b46` (gates every SUB_ deletion
probe) + `CTRL_G_ABPD_b46` (gates SUB_O1), both byte-identical
md5-verified.

**Reading the matrix** (full text in `probes.json → reading_the_matrix`):

* **U16 (batch 45, certified PASS) brackets the top; SUB_ALL the bottom.**
* **SUB_Sx FAIL** → THE FLIP: that group's infrastructure is REQUIRED.
  The document retains OUR copy of every roster class, so the conviction
  names donor-only furniture — each probe's
  `classes_zeroed_documentwide` (in accounting.json/probes.json) is the
  exact candidate class list.  Next round bisects INSIDE the convicted
  group (for S5 the halves are already in this batch).
* **SUB_Sx PASS** → that group alone is not required.
* **ALL singles PASS + SUB_ALL FAIL** → the requirement is a UNION —
  next round runs cumulative deletions in reading order (mechanical).
* **ALL singles FAIL** → suspect the SHARED deletion mechanics FIRST
  (every deletion probe leaves the donor inline-ADocument's deep
  registries dangling over the deleted ids — tolerated at PROJECT level by
  the genesis-deletion precedent, unproven at famdoc level): rebuild ONE
  single with a scrubbed ADocument before reading convictions.
* **SUB_ALL PASS** → inversion again: the lean roster is lawful when
  REACHED BY DELETION — the defect would be in how our famdoc AUTHORS the
  same shape (field grammar, not roster); diff SUB_ALL's famdoc vs B0's
  element-by-element.
* **SUB_O1 PASS** → element order was the whole-document property; the fix
  is famgen's allocation order (mechanical).  **SUB_O1 FAIL** → order
  alone does not heal B0 — consistent with missing infrastructure.

## §3  The deletion law (the mechanics, all machine-gated per probe)

Every deletion probe is the EXACT certified U16 recipe
(`famdoc_final.make_union_doc('U16', wm)` → donor body + our 35 carried
elements registered in the donor self-Family) with the lawful deletion
injected between union assembly and the famload:

1. **Cascade closure** (original donor id space, from the measured graph):
   children die with owners; any element referencing a deleted element on
   a NON-registry surface joins the deletion.  Frame + carried may never
   join (build-refused; measured: never happens).
2. **Registry scrub** (the ONLY survivor edits; censused per surface, per
   probe): any Family's `m_familyIds` rows / `m_familyParams` rows / type
   table rows / locked list / order cell / `m_deletableElements` /
   `m_oFamDimConstrMgr` entries / `m_refs` entries / `m_fsdos` entries;
   every survivor's header `m_parents` lists; a VarSketch's
   `m_dimIds`/`m_dimData`.  SUB_ALL's census: 299 `m_familyIds` rows +
   299 header-deletion entries + the dim-constraint manager's 9 entries +
   the ref table's 2 + 5 type-table rows + …
3. **The ONE detach normalization**: SUB_S6 sets the surviving
   LevelAttributes' `m_familyTagId` (donor: the nested FamilySymbol) to
   **-1** — the value OUR famgen authors in the B3-certified datum axis.
   Recorded per probe; fires nowhere else (pinned).
4. **Residual scan** (build-refusing): after scrub+detach, an int-walk over
   every survivor proves ZERO references into the deleted set.  0 on all
   10 deletion probes.
5. **Inline-ADocument treatment**: the donor's own inline ADocument
   (U16's axis-6 swap) with the deleted ids' ElemTable rows DROPPED, the
   carried roster's rows appended (35), `m_last` raised, history GUIDs
   re-keyed fresh, clean re-decode gated.  Deep registries
   (AppInfoManager) keep their entries — the dangling census is recorded
   per probe (SUB_ALL: 359 dangling refs across 5 registry keys; SUB_S2:
   0).  Kept rows' owners proven surviving.
6. **Gates** (unchanged from famdoc-final's law): probe validator 0/0,
   four-registry coherent, load hop +1 unit / instance hop +0, survivor
   law, identity PASS, dev-rfa RefDecoder `unresolved_anywhere = 0`
   (host-resident danglings are the substrate's own certified pattern —
   U16 shows 29, SUB_ALL 9), blob census 64 B × every unit with the added
   unit's nonce byte-verified.

**SUB_O1's mechanics**: `build_product(start_id = wm+1)` under
`corpus_symbol_form`, then a PURE ID PERMUTATION over the same contiguous
block (sorted by donor-convention role rank: self-Family, LevelAttributes,
Level, plan Viewer-then-view-then-drawing-then-viewport, RefPlanes, proj
chain, sketch-then-extrusion-then-curves-then-plane, extent, UnitsElem,
params ×14, view type, sun, view sketch plane; our connector layer — no
donor equivalent — last), every occurrence remapped by the famgen loader's
own conservative int-walk, then the loader + demo placement UNTOUCHED (the
loader keeps the product's own ids — measured; the emitted unit's record
order is ascending-id by construction).  38/41 ids moved; the permutation
is asserted a bijection; symbol-form + connector-manager + one
dangling-free instance gates re-asserted (`_b0_style_gates`).

## §4  Honest limits

* **The deletion probes share one non-deletion delta vs U16**: the inline
  ADocument's deep registries dangle over deleted ids (censused; 0 for
  SUB_S2, 359 for SUB_ALL).  The genesis-deletion precedent tolerated
  exactly this at project level (viewer-certified lineage); it is UNPROVEN
  at famdoc level — hence the ALL-singles-FAIL branch in the reading
  matrix names it the first suspect, and one rebuilt single with a
  scrubbed ADocument is the designed disambiguator.
* **SUB_S6 carries the one detach edit** (`m_familyTagId → -1`).  Its FAIL
  would strictly convict {cluster + detach}; the detach value is our
  famgen's own form, present in the B3-certified datum axis on this same
  donor body — but B3 ADDED our element beside the donor's; no certified
  file yet carries a donor LevelAttributes with -1.
* **Group singles are closures, not seeds** — S3's single deletes 76
  elements (its 19 + the view furniture cropping to its planes), S5A's
  129.  The per-probe `pull_census` + `classes_zeroed_documentwide` keep
  the reads honest: a conviction names the CLOSURE, and the zeroed-class
  list is the candidate requirement space.
* **SUB_O1 varies ONLY the id assignment.**  Unit shape (record framing,
  blob layout, segment order) is varied by no probe in this round; if
  every probe PASSES and SUB_ALL somehow passes too, unit shape is the
  remaining suspect space (next round: byte-level unit diffing).
* The roster equivalence is partial by design where our shapes differ
  (donor sketch aligns 4 face planes; ours authors 2 origin planes; donor
  SF carries 1 param vs our 14; no donor connector layer) — recorded in
  `classification.json → roster_equivalence`.

## §5  Verification (how to re-run)

```
.venv/bin/python tools/subtractive.py classify        # class->group map + closures
.venv/bin/python tools/subtractive.py build           # all 11 probes (~8 min)
.venv/bin/python tools/subtractive.py build --only SUB_ALL,SUB_O1
.venv/bin/python tools/subtractive.py verify          # re-run every gate
.venv/bin/python tools/subtractive.py spec            # author_spec.json
.venv/bin/python tools/subtractive.py stage           # probe_batch + 2 controls
.venv/bin/python -m pytest tests/test_subtractive.py -q   # 39 stream-local tests
```

Stream-local tests: **39 passed** — partition sizes + exactness + frame
roles + nested-cluster shape + class-map pins + equivalence pins + S5-half
partition, closure sizes + clean-single pins + detach-fires-only-for-S6 +
frame-never-cascades + SUB_ALL-is-the-union + cascade censuses, per-probe
gate law + deletion/ADocument-row arithmetic + lean-shape landing +
zeroed-class reads + detach-applied proof + scrub census + dangling census,
O1 bijection/order/symbol-form/rank pins, probes.json order/bases/md5s +
reading-matrix branch coverage + staged-file md5s, classification.json +
author_spec.json content pins, deletion-primitive unit tests, ladder-name
collision guard (`SUB_` prefix vs the acceptance folder's historical
`D_all.rvt` on a case-insensitive filesystem).  Full suite: NOT run
(SUITE-COORDINATION hard rule).

## BRANCH STATE

* **status: DONE — THE SUBTRACTIVE LADDER BUILT, GATED, STAGED (batch 46)
  WITH THE FULL CLASSIFICATION, THE DELETION LAW, THE ORDER PROBE AND THE
  AUTHOR SPEC.**  STOPPED AT READY: nothing uploaded; the viewer queue is
  the orchestrator's.
* **no VCS** (working tree, not a git repo).  Files written:
  `tools/subtractive.py` (new, ~1860 lines; classify/build/verify/spec/
  stage), `tests/test_subtractive.py` (new, 39 pass),
  `experiments/subtractive/` {SUB_ALL, SUB_S5, SUB_S6, SUB_S4, SUB_S7,
  SUB_S2, SUB_S1, SUB_S3, SUB_S5A, SUB_S5B, SUB_O1}.rvt (md5s in §2),
  probes.json (decision table + per-probe deletion/permutation summaries),
  classification.json (the class→group map + roster equivalence + per-probe
  closures + detach law), author_spec.json (S5+S6 authoring spec, column
  structure + panelboard counts), accounting.json (full gates + blob proof
  + deletion/scrub/dangling censuses per probe), `_build/**` (per-probe
  deletion reports, load files, dev rfas, the O1 permutation record),
  `_explore/**` (the measurement scripts + graph dumps this classification
  was derived from), this record; staging copies + `batch_46.json` +
  `CTRL_rstbasicsampleproject_b46.rvt` + `CTRL_G_ABPD_b46.rvt` under
  `experiments/acceptance/`.
* **gates**: every probe validator VALID 0/0, four-registry coherent,
  survivor 0/0, identity PASS, refs unresolved-anywhere 0, deletion
  residual 0, blob census 64 B on every unit + added-unit nonce verified,
  SUB_O1 symbol form + product connmgr + exactly one dangling-free
  instance, probe_batch ADMISSIBLE (2 controls), all staged copies
  md5-verified.  `verify` post-build: 11/11 gates_ok.
* **NOT VIEWER-TESTED**: every claim above is the machine gate; no
  acceptance claim is made.  All probes PROOF-ONLY (donor-derived,
  quarantined, never bundled).
* **next action (orchestrator)**: upload batch 46 in manifest order (both
  CTRLs first, then SUB_ALL, SUB_S5, SUB_S6, SUB_S4, SUB_S7, SUB_S2,
  SUB_S1, SUB_S3, SUB_S5A, SUB_S5B, SUB_O1), verdicts to
  `docs/coverage/viewer-certified.json`, read with `probes.json →
  reading_the_matrix`.  A group conviction takes that probe's
  `classes_zeroed_documentwide` as the candidate space and bisects inside
  the group next round (S5's halves already staged); an S5/S6 conviction
  takes `experiments/subtractive/author_spec.json` as the famgen
  authoring spec; an order conviction fixes famgen's allocation order.

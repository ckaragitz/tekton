# famdoc-final — COMBINATION vs FRAME: THE ROUND THAT DECIDES (staged, batch 45)

Stream: **famdoc-final** (2026-08-05).  Charter: verdicts #38 read batch 44
as B7 PASS (machinery exonerated with blobs) + B1..B6 ALL PASS (every one
of our content axes lawful ALONE on the donor body) + B0 FAIL (our complete
famgen famdoc) — so the defect is EITHER a **combination** of our axes OR
the **residual frame** (the famdoc elements outside all six categories).
This round asks both questions FROM BOTH DIRECTIONS in one staged batch,
with the pair bisection and the frame singles pre-built so the NEXT round
needs no build cycle.

**Territory touched ONLY:** `tools/famdoc_final.py` (new),
`experiments/famdoc_final/**` (new), `tests/test_famdoc_final.py` (new),
this record, and the staging copies `probe_batch` itself writes under
`experiments/acceptance/` (its designed output).  `tools/famdoc_bisect.py`
and `tools/famdoc_blobs.py` are IMPORTED, never edited (path-parameterized
primitives only — no module-dir repoints needed; no cross-voice writes).
No `src/**` edits.  No browser (STAGE only — the orchestrator uploads); no
Autodesk install dirs; zero donors in shipped output (every probe
PROOF-ONLY, quarantined); no full-suite runs (SUITE-COORDINATION).

## Result in one screen

* **THE DECIDING ROUND IS BUILT, GATED AND STAGED AS BATCH 45** — 10
  probes + 2 controls, every probe `rvt.validate` **VALID 0 errors / 0
  unexpected**, four-registry **coherent** (+1 unit load hop, instance hop
  registry-silent), survivor law 0/0, identity **PASS**, schema-typed
  reference resolution **unresolved-anywhere = 0 on every famdoc**
  (RefDecoder against unit + its real host — G_ABPD for the F-probes),
  **every save unit of every probe carries the 64-byte 0x0f3f blob with
  the added unit's nonce byte-verified** (famdoc-blobs' gate, re-derived
  independently in this stream's tests), both controls + all staged copies
  md5-verified.  `verify` re-run post-build: 10/10 gates_ok.  45
  stream-local tests pass.
* **THE FRAME IS MEASURED AND PRINTED** (§1) — exactly SIX of our 41
  famdoc elements sit outside all six batch-44 axis sets, in THREE natural
  groups; the donor has a 1:1 class-matched equivalent for each, plus two
  `BrowserOrganization` elements its project view references that ours
  lacks.
* **frame_diff.json IS THE FIX SPEC** — the per-element field diff of our
  frame vs the donor's, ranked deep-walk-first, every self-Family key
  tagged with its swap disposition (15 differing donor fields ARE tested
  by F1/F2; the kept-ours residue is listed under `untested_by_swap`),
  including the measured **ownership frame delta** (the donor's UnitsElem
  and DBViewProject are OWNED by the self-Family; ours were top-level —
  it rides in the inline-ADocument ElemTable row, invisible to a field
  diff, adopted by the swap).
* **The converse (F1) holds everything else at B0**: the F-probes run the
  EXACT B0 recipe — famgen loader chain on G_ABPD under
  `corpus_symbol_form`, the demo's own `stage_equipment` placement,
  product `FamilyInstanceConnectorManager` read back from the emitted
  bytes, symbol-form gate re-asserted — with the frame swap injected
  between `build_product` and the load.  The ONLY delta vs the failing B0
  is the frame.
* **H8B closes the loader/base split** the batch-44 record flagged: our
  famdoc VERBATIM (corpus symbol form = B0's own famdoc flavour) through
  famload on rst — batch 37's H8 was VOID (empty blob); with the blob its
  verdict is new information either way the F-reads land.

## §1  THE FRAME ROSTER (the charter's centerpiece — this IS the frame)

Of our 41-element famdoc, the six-axis union covers 35
(geometry 7 / params 14 / datum 4 / views 8 / connector 2).  The SIX
outside, with their donor equivalents (donor ids from rst unit 36,
M_Concrete-Square-Column):

| group | role | ours (class) | donor equiv | swapped by |
|---|---|---|---|---|
| G1 | self_family | `Family` | 1410872 | F1, F2 |
| G2 | units | `UnitsElem` | 1411008 | F1, F3 |
| G3 | proj_view | `DBViewProject` | 1410913 | F1, F4 |
| G3 | proj_viewer | `Viewer` (owned by proj_view) | 1410912 | F1, F4 |
| G3 | proj_drawing | `DBDrawing` (owned by proj_view) | 1410914 | F1, F4 |
| G3 | proj_viewport | `Viewport` (owned by proj_drawing) | 1410915 | F1, F4 |

plus, imported WITH G3 (the donor's project view references them via
header `m_regenOnly`; ours references nothing): **2 ×
`BrowserOrganization`** (donor 1411145/1411146, registered in the
self-Family with fresh absorbed indices 40/41, counter bumped to 42).

Measured frame deltas the swap carries (full detail in frame_diff.json):
the self-Family's 15 differing non-membership fields (`m_seekItemId`,
`m_omniClassCode`, `m_appVersionAtInitialLoad/AtLoad`, `m_bIsSavable`,
`m_bHasAnyDummyRefs`, `m_shouldStayParametric`, `m_isVertical`,
`m_isWorkPlaneBased`, `m_eStructMaterialType`, `m_fsdos`,
`m_pParamValueSetInt`, `m_defaultColumnHeight`,
`m_defaultHeightAboveLevel`, `m_defaultHostThickness`), the G2/G3 whole
elements, and the **ownership topology** (units + proj_view
self-Family-owned in the donor).  Kept OURS by the field law (membership
registries, identity, registry-coupled counters): recorded per-key in
frame_diff.json; the 14 kept-ours keys that DIFFER from the donor are
listed under `untested_by_swap` — the honest residue.

## §2  The ladder (staged reading order = maximum information first)

All probes `experiments/famdoc_final/<rung>.rvt`, staged byte-identical to
`experiments/acceptance/`; manifest `experiments/acceptance/batch_45.json`.
Fresh GUIDs are minted per rebuild — re-hash after any rerun.

| # | rung | md5 | base | the ONE thing it tests |
|--:|---|---|---|---|
| 1 | **U16** | `4d809455` | rst | donor body + ALL SIX additions at once: the 35-element union of B1..B5's subtrees registered in the donor self-Family + B6's donor-inline-ADocument swap (ElemTable extended with the carried roster, IdentifierSource raised).  452 elements |
| 2 | **F1** | `2a1430e8` | G_ABPD | the CONVERSE: our famdoc with the donor FRAME swapped in (G1+G2+G3 + 2 imports), the exact B0 recipe otherwise |
| 3 | **U12345** | `68c3bdea` | rst | the same 35-element union with OUR authored inline ADocument — the B0-minus-frame shape (what B0 actually carries) |
| 4 | **H8B** | `4330bfbf` | rst | our famdoc VERBATIM (corpus symbol form) through famload — the loader/base split anchor |
| 5 | **U12** | `ff59a069` | rst | geometry × params (438 elements) |
| 6 | **U15** | `2a12fd3e` | rst | geometry × connector (427; the connector's face ref resolves to OUR carried extrusion) |
| 7 | **U25** | `81cccedf` | rst | params × connector (433; face ref repointed to the donor extrusion) |
| 8 | **F2** | `5f0b57a5` | G_ABPD | ONLY the self-Family frame-field swap |
| 9 | **F3** | `797d2dd1` | G_ABPD | ONLY the units registry swap |
| 10 | **F4** | `67f72180` | G_ABPD | ONLY the project-view chain swap (+2 imports) |

Controls: `CTRL_rstbasicsampleproject_b45` (gates U16/U12345/H8B/U12/U15/
U25) + `CTRL_G_ABPD_b45` (gates F1..F4), both byte-identical md5-verified.

**Reading the matrix** (full text in `probes.json → reading_the_matrix`):

* **U16 FAIL** → a combination is guilty; U12345 places the ADocument
  axis (both FAIL → pairs U12/U15/U25 bisect NOW; U16-only FAIL → the
  donor-ADocument swap is implicated in combination).
* **U16 PASS + U12345 FAIL** → our authored inline-ADocument × content
  interaction (the donor ADocument rescues the same union).
* **U16 PASS + U12345 PASS** → no union of our added axes reproduces B0
  → read F1: **F1 PASS = FRAME CONVICTION CONFIRMED FROM BOTH
  DIRECTIONS** (loader+base+recipe held exactly at B0's on the F side);
  F2/F3/F4 name the group; frame_diff.json's `donor` entries are the fix
  spec.  **F1 FAIL** → the frame's guilt is not in the swappable fields →
  H8B splits: H8B PASS convicts the famgen-loader/G_ABPD delta; H8B FAIL
  re-convicts our famdoc content under exonerated machinery, leaving
  element order / unit shape / the `untested_by_swap` fields as the
  suspect space.
* **Either control FAIL** → that base's probes VOID.

## §3  The two swap mechanisms (both machine-gated per probe)

**U-unions** (famdoc_bisect's H-machinery generalized to axis SETS): an
anchor is repointed to the donor's only when the axis that carries it is
NOT in the union — U16/U12345 repoint ONLY our self-Family ref (level,
plan view, extrusion all carried); U12/U15 repoint the level; U25 repoints
the extrusion for the connector's face ref.  Registration follows the
proven per-axis conventions (H2's with built-in rows when axis 2 rides,
H5's single-param form otherwise; absorbed indices continue the donor's
counter at 3165).  The carried-subtree dangling scan (no above-watermark
ref outside the hybrid) and the dev-rfa RefDecoder pass gate every union.
U16's ADocument swap extends the proven H6 recipe: donor inline ADocument
remapped + history GUIDs re-keyed fresh + **one ElemTable row per carried
element appended** (donor's own row shape, ids/owners in hybrid space) +
IdentifierSource `m_last` raised over the roster (recorded before/after;
B6 measured that a stale-small `m_last` also passes).

**F-swaps** (the converse): donor equivalents id-rebased to OUR element
ids (content refs into the frame stay valid by construction), internal
refs repointed through the frame equivalence map via the famgen loader's
own conservative `_walk_replace_ids`, donor ownership topology ADOPTED
(recorded per element).  The self-Family follows the deterministic FIELD
LAW (member-ref surfaces + identity + registry-coupled counters stay
ours; everything else donor) — the build's disposition table is asserted
equal to frame_diff.json's.  Build-refusing gates: identical top-level key
sets, zero residual donor-block ids anywhere in the document, RefDecoder
resolution against unit+G_ABPD, corpus symbol form, product connector
manager, exactly one dangling-free instance.

## §4  Honest limits

* The F-swap tests element FIELD content + ownership.  Element ORDER,
  unit shape, types/current-type, document identity surfaces, and the
  kept-ours fields (frame_diff.json `untested_by_swap`: e.g.
  `m_nextAbsorbedIndex`, `m_refTypeIds`, `m_oFamDimConstrMgr`,
  `m_deletableElements`, `m_refs` — all membership/counter-coupled, they
  CANNOT carry donor values over our roster) are NOT varied by any F
  probe; on F1 FAIL + H8B FAIL they are the remaining suspect space and
  the record says so in the decision table.
* U16 carries the donor's ADocument with OUR roster appended — a state
  neither B6 (donor roster only) nor B0 (our authored ADocument) carried;
  U12345 exists precisely so the frame inference never rests on U16
  alone.
* The BrowserOrganization imports make F1/F4's famdoc 43 elements (ADD
  form, registered); F2/F3 stay 41 — group reads are per-group, not
  roster-size-controlled (recorded).
* An F-probe PASS convicts OUR frame fields; it cannot say WHICH field —
  that is the next round's single-field ladder over frame_diff.json's
  `donor` entries (F2/F3/F4 narrow to the element group first).
* 201/55150 (donor deletion-list host ids) and 1177727 (donor `m_fsdos`
  material) are resident in BOTH rst and G_ABPD ElemTables — measured
  before the swap design; they ride as ordinary project-hosted-family
  host refs and the RefDecoder pass proves them resolvable.

## §5  Verification (how to re-run)

```
.venv/bin/python tools/famdoc_final.py roster            # print the frame roster
.venv/bin/python tools/famdoc_final.py diff              # frame_diff.json (fix spec)
.venv/bin/python tools/famdoc_final.py build             # all 10 probes (~5 min)
.venv/bin/python tools/famdoc_final.py build --only U16,F1
.venv/bin/python tools/famdoc_final.py verify            # re-run every gate
.venv/bin/python tools/famdoc_final.py stage             # probe_batch + 2 controls
.venv/bin/python -m pytest tests/test_famdoc_final.py -q # 45 stream-local tests
```

Stream-local tests: **45 passed** — frame roster + donor-role pins,
frame_diff disposition/ownership law, per-probe independent blob census +
nonce (10), gate greenness (10), union carried counts + repoint law + the
U16 ADocument extension + registration conventions, F-group swap scope +
ownership adoption + disposition equality with the fix spec + **donor
fields read back from F1's emitted bytes** (seekItemId/appVersion donor,
identity ours, 42-row registry), B0-recipe pins on every F probe, H8B
recipe pins, probes.json order/bases/md5s, decision-table branch coverage,
staged-batch two-control + md5 + build-identity pins.  Full suite: NOT
run (SUITE-COORDINATION hard rule).

## BRANCH STATE

* **status: DONE — THE COMBINATION-vs-FRAME ROUND BUILT, GATED, STAGED
  (batch 45) WITH THE FRAME ROSTER, frame_diff.json AND THE FULL DECISION
  TABLE.**  STOPPED AT READY: nothing uploaded; the viewer queue is the
  orchestrator's.
* **no VCS** (working tree, not a git repo).  Files written:
  `tools/famdoc_final.py` (new, ~1630 lines; roster/diff/build/verify/
  stage), `tests/test_famdoc_final.py` (new, 45 pass),
  `experiments/famdoc_final/` {U16,F1,U12345,H8B,U12,U15,U25,F2,F3,F4}.rvt
  (md5s in §2), probes.json (decision table + frame roster + per-probe
  gates), frame_diff.json (ranked fix spec incl. ownership),
  accounting.json (full gates incl. blob_proof per probe AND parent),
  `_build/**` (per-probe union/frame-swap reports, load files, dev rfas,
  F chains)}, this record, staging copies + `batch_45.json` +
  `CTRL_rstbasicsampleproject_b45.rvt` + `CTRL_G_ABPD_b45.rvt` under
  `experiments/acceptance/`.
* **gates**: every probe validator VALID 0/0, four-registry coherent,
  survivor 0/0, identity PASS, refs unresolved-anywhere 0 (per-famdoc
  RefDecoder vs its real host), blob census 64 B on every unit of every
  probe + parent with added-unit nonce byte-verified, F-swap donor-block
  residual 0, corpus symbol form + product connmgr on every
  B0-recipe probe, probe_batch ADMISSIBLE, both controls + all staged
  copies md5-verified.  `verify` re-run post-build: 10/10 gates_ok.
* **NOT VIEWER-TESTED**: every claim above is the machine gate; no
  acceptance claim is made.  All probes PROOF-ONLY (U-probes and the
  F-probes' swapped/imported elements are sample-derived, quarantined,
  never bundled).
* **next action (orchestrator)**: upload batch 45 in manifest order (both
  CTRLs first, then U16, F1, U12345, H8B, U12, U15, U25, F2, F3, F4),
  verdicts to `docs/coverage/viewer-certified.json`, read with
  `probes.json → reading_the_matrix`.  Every branch is pre-built: a
  combination conviction reads the pairs already staged; a frame
  conviction reads F2/F3/F4 already staged and takes
  `experiments/famdoc_final/frame_diff.json` as the fix spec (`donor`
  dispositions first, ownership included); the loader split reads H8B.

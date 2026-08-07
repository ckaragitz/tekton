# catchain — the famgen-CHAIN residue probes (post-verdict-#41)

Stream charter: batch 47 exonerated pure record ORDER in both directions
(M1 FAIL / M2 PASS) and convicted none of the single-field byte morphs
(M3 order-cell dedup, M4 sparse counters, M5 partType −1, M6 deletion
prefix — ALL FAIL).  The survivors from `experiments/layout/
layout_diff.json`'s 12 perfect separators are the ENTANGLED residues only
a full famgen-chain rebuild can flip coherently: the family CATEGORY (+
everything category-coupled), the 1-row-vs-5-row FamilyTypeTable shape,
the locked/param BIP group, the missing materials group — possibly a
CONJUNCTION (all 12 co-vary in the corpus).  Build four one-recipe-change
variants of B0 through the FULL chain (no byte surgery) + the two
bisection pre-builds; stage with a certified control.
Territory: `src/rvt/famgen/catprobe.py`, `tools/catchain.py`,
`experiments/catchain/**`, `tests/test_catchain.py`, this record.

## 0. State

**BUILT, GATED, STAGED — batch 48 (7 files), NOT uploaded (stage-only
rule; the orchestrator uploads).**  All six probes ride the exact B0
recipe (G_ABPD + ONE famgen panelboard + ONE placed instance, famgen
loader under `famload_hostfix.corpus_symbol_form`, demo `stage_equipment`
placement) with the probe's recipe change applied through the chain's own
constructors — the famdoc self-Family, the host Family (a self-Family
object copy), the FamilySymbol/surrogates/FamilyInstance headers, the
ADocument CategoryTable row and the symbol-geometry GStyle all move
TOGETHER, which is exactly what the batch-47 byte morphs could not do.
Every gate is green on every probe: validator 0 errors (0 unexpected),
four-registry coherent, load hop +1 unit / instance hop +0, survivor law,
identity PASS, blob 64-B ×2 with the added unit's deterministic nonce
verified, exactly ONE dangling-free instance with
`FamilyInstanceConnectorManager`, corpus-lawful symbol form, doc-level
record roundtrip 123/123, and the emitted famdoc's FEATURE VECTOR
machine-verified against the intended recipe (layout-law's own
`unit_features`/`CANDIDATES` instruments).  `tests/test_catchain.py`
13/13.

## 1. The mined corpus shapes (the laws the recipes reproduce)

Mined 2026-08-05 from SUB_ALL (matched-pair PASS anchor), B7 (pure donor
famdoc) and B0 (famgen FAIL anchor); machine copy in
`experiments/catchain/corpus_shapes.json` (rebuild: `tools/catchain.py
mine`).

* **Type table (BX_types_5)** — the donor famdoc table is NOT "5 real
  types": it is a leading **BLANK `' '` pair whose rows byte-equal the
  current-values set (`m_familyParams`)** + the real types, `m_idx = 1`.
  True on SUB_ALL (` `, 300/450/600/750mm pairs re-keyed to our params by
  the U16 merge) AND on B7 (the donor's own ` ` + four column sizes) —
  the famdoc-side blank-pair convention famgen never authored (famgen: 1
  real pair, idx 0).  Recipe: blank pair (current-values copy) + the
  product's own type + 3 rating variants (100/400/600 A, distinct names),
  `current_type = 1`, re-derived by the chain's own `finalize`.
* **Locked/param BIP (BX_bip)** — `-1001205` (cost BIP) in
  `m_lockedParameterIdsForDirectManipulation` (donor: `[-1001205, <3
  dims>]`; B7: `[-1001205, <1 dim>]` — the BIP sorts first) **and** in
  the identityData palette of the order cell — **with NO value row**
  (neither SUB_ALL nor B7 carries a −1001205 row in familyParams/types;
  the earlier "18 rows incl. BIP −1001205" reading in layout-law §1 was
  imprecise — the 18th row is the material row, see next).  The donor's
  full identity palette also lists unvalued BIPs −1152384, −1140422,
  −1010108, −1010105, −1002500, −1005554; the probe adds only the
  locked/palette −1001205 (the (c) axis), the rest is recorded here.
* **Materials group (in BX_conj)** — three coupled surfaces: (i) the
  `-1005500` material BIP as an **INSTANCE value row on every type + the
  current-values set** (`{m_paramId −1005500, m_elemId <material>,
  m_instance true}` — the 17→18 row delta), (ii) a `MaterialFSDO` in
  `m_fsdos` (`{m_categoryId <own category>, m_materialId <material>,
  m_famParamId −1005500}`), (iii) a `materials-1.0.0` group FIRST in the
  order cell holding `[-1005500]`.  The donor's material id 1177727 is
  NOT a unit element (dangles outside the unit) and the corpus PASSES
  with it — the separator is the row/group presence, so our recipe uses
  `m_elemId = -1` (unassigned; no dangling ref introduced).
* **Counters** — `m_nextAbsorbedIndex 3165` / `m_predefinedLimitIdx
  1963` (sparse edit history).  The donor's `m_familyIds` INDEX values
  are also sparse (gap 3160), but M4 probed the two scalars alone and the
  conjunction reuses exactly the M4 surface (indices stay dense) — the
  ranked candidate (`sf_absorbed_dense`) flips on the scalars.
* **Deletion prefix** — the self-Family header `m_deletion` opens with
  the NON-ELEMENT parents **in order** `[category, −1005500, −1001205,
  <material elem>]` before the element ids.  The conjunction prepends
  exactly the parents it authors (`[category, −1005500, −1001205]`;
  no material element exists to name) — M6's one-liner completed to the
  measured set.
* **refTypeIds** — `[4]` on SUB_ALL AND B7; `[]` on B0.
* **Category** — the donor famdoc is structural-column −2001330 with
  `m_partType −1`; every PASS famdoc carries partType −1, every FAIL 14.
  The GM id **−2000151** is verified in the schema constants
  (`skeleton.OST_GENERIC_MODEL`, specimen-verified) AND on the host
  itself: G_ABPD carries a GM **projection GStyle (id 118, type 1)** +
  cut style 119 — the symbol geometry binds a real host style under GM
  exactly as B0's did under electrical (124).

## 2. The probes (batch 48, reading order)

Every probe = the B0 recipe + ONE recipe change, built by
`tools/catchain.py build`; features machine-checked per build AND per
`verify` (12-separator vector + exact values).  `experiments/catchain/
probes.json` carries the full per-probe gates + the decision table.

| # | probe | the ONE change | separators flipped to PASS side |
|---|-------|----------------|---------------------------------|
| 1 | BX_conj (md5 47a68a11) | ALL famgen residues at once: GM category(+partType −1) + 5-row table + locked/palette BIP + materials machinery + order-cell dedup (`layout_law.normalize_order_cell`) + M4 counters + deletion prefix + refTypeIds [4] | **all 12** (machine-verified: cells `[materials, dimensions, identityData, electrical]`, 18 fp rows, absorbed 3165/limit 1963, deletion opens `[−2000151, −1005500, −1001205]`, fsdos 1, refTypeIds [4], 5 pairs idx 1, cat −2000151 pt −1) |
| 2 | BX_cat_gm (6d7ed2f3) | category = GENERIC MODEL end to end: famdoc self-Family + host Family copy + symbol/surrogates/instance headers + ADocument CategoryTable row (−2000151: `[7848, <our symbol>]`; the −2001040 row stays empty) + GM GStyle 118 symbol geometry + placement scrub | sf_category_is_ours_electrical, sf_partType_set |
| 3 | BX_types_5 (088530c6) | the donor table shape: ` ` + `225A MLO 42ckt` + `100A/400A/600A` variants, idx 1 | sf_single_type_pair, sf_type_idx_zero |
| 4 | BX_bip (8db29a11) | locked + palette −1001205, no value row | sf_locked_no_bip |
| 5 | BX_conj_minus_cat (3cd1795d) | BX_conj with electrical-equipment + partType 14 kept (category & partType move as ONE axis) | 10 of 12 (category pair kept FAIL-side) |
| 6 | BX_conj_minus_types (70e4fa88) | BX_conj with the 1-pair idx-0 table kept | 10 of 12 (table pair kept FAIL-side) |

Staged: `experiments/acceptance/batch_48.json` — CTRL_G_ABPD_b48
(byte-identical certified control) + the 6 probes, staged copies
md5-verified, every base resolved to the certified G_ABPD.  **STAGE ONLY
— the orchestrator uploads in `reading_order`.**

Recorded design decisions:

* **BX_conj includes refTypeIds [4]**, which verdict #41's commission did
  not enumerate — without it the conjunction would leave 1 of the 12
  perfect separators on the FAIL side and "BX_conj FAIL ⇒ defect outside
  everything enumerated" would be unsound.  The conj is now a TRUE 12/12
  upper bound of the corpus's byte-observable residue space.
* **partType follows the category** (charter's coupling rule): GM probes
  author −1; minus_cat keeps 14 with electrical.  M5 already proved −1
  alone (on electrical) fails, so the pair moves as one axis.
* Two accepted chain conventions (neither is a measured separator, both
  recorded): the familyParams row ORDER follows famgen's sort (user
  params then BIPs by magnitude; the donor opens with −1005500), and on
  types5 probes the HOST Family table carries its own leading blank row
  on top of the famdoc's (host side is base-coupled and exonerated —
  H8B).

## 3. Decision table (mirror of probes.json `reading_the_matrix`)

* **CTRL FAIL** — round VOID; re-stage.
* **BX_conj PASS** — the law lives INSIDE the enumerated residues; the
  corpus's byte-observable suspect list is confirmed sufficient.  Then:
  any single PASS names its axis outright; all singles FAIL ⇒ conjunction
  of ≥ 2 — read the pre-built minus rungs: minus_cat FAIL ⇒ category
  NECESSARY; minus_cat PASS ⇒ category unnecessary (bisect
  types/bip/materials/dedup/counters/deletion/refTypeIds next round,
  same conj-minus-one pattern); symmetrically minus_types.
* **BX_conj FAIL** — the defect is OUTSIDE everything enumerated: all 12
  perfectly-separating byte residues authored to the PASS side through a
  coherent chain and the audit still rejects.  The byte-diff instrument
  is exhausted at this scale; **the honest next instrument is the
  desktop-Revit kit** (observe the audit's actual complaint on
  B0/BX_conj directly).  Singles then serve as corroboration only.
* **BX_cat_gm PASS** — the audit demands category-consistent
  infrastructure our electrical famdoc lacks (partType-14 panelboards
  imply panel-schedule machinery).  Fix fork: ship GM equipment families
  (works today; schedules/tags lose the category filter) or author the
  electrical infra (next stream).  Deliverable rule holds either way —
  gates are labels, the built family ships stamped.
* **BX_types_5 PASS** — promote `catprobe.apply_types5` (blank pair +
  idx 1) into famgen `finalize`; **BX_bip PASS** — promote
  `apply_bip_lock`.  Either fix is one call, already implemented.
* **Minus rungs are read ONLY under BX_conj PASS** (a minus verdict with
  conj FAIL carries no information about necessity).

## 4. Instruments (reused, never edited)

`tools/layout_diff.py` (UnitX / unit_features / CANDIDATES — the feature
gate), `tools/famdoc_blobs.py` (blob_proof nonce verification +
campaign-global batch numbering), `tools/bisect_instance_bug.py`
(demo model, placement, account), `tools/ifc_intent.py` (build_product,
host_watermark, stage_equipment), `tools/probe_batch.py` (staging law),
`rvt.famload_hostfix.corpus_symbol_form`, `rvt.famgen.layout_law.
normalize_order_cell` (the M3 fix, reused verbatim in the conj).
NEW: `src/rvt/famgen/catprobe.py` — `category_override` (runtime-patches
`skeleton.new_family_document` + `loader.survey_host` + the placement
scrub constant, restored on exit; no shared file edited) +
`apply_residues` (the doc-level recipes; ONE chain re-finalize derives
every coupled surface, then the post-finalize field recipes).

## BRANCH STATE

* Working tree only (repo has no git); all artifacts inside territory:
  `src/rvt/famgen/catprobe.py`, `tools/catchain.py`,
  `tests/test_catchain.py` (13/13),
  `experiments/catchain/{BX_conj, BX_cat_gm, BX_types_5, BX_bip,
  BX_conj_minus_cat, BX_conj_minus_types}.rvt`,
  `experiments/catchain/{probes.json, accounting.json,
  corpus_shapes.json, _build/**}`, plus the staged copies + manifest
  probe_batch itself writes: `experiments/acceptance/{batch_48.json,
  CTRL_G_ABPD_b48.rvt, BX_*.rvt}` (its designed output).
* No shared famgen/tools file edited (catprobe is new; overrides are
  scoped context managers).  No full-suite run (test_catchain.py only).
  No donors in anything shippable — the probes carry ONLY famgen-authored
  content on the certified G_ABPD base (donor shapes are reproduced as
  mined FIELD VALUES, zero donor bytes; the blob nonce proof enforces
  this machine-side).  No browser; no Autodesk install dirs.
* NEXT (orchestrator): upload batch 48 in `reading_order` (BX_conj
  first); read verdicts against §3 / `experiments/catchain/probes.json`;
  on BX_conj PASS the bisection continues from the pre-built minus rungs;
  on BX_conj FAIL commission the desktop-Revit kit.

# layout-law — the matched-pair diff, the morph round, and the port

Stream charter (post-verdict-#40): name the physical-layout law behind
SUB_ALL (PASS) vs F1 (FAIL) and port it to famgen emission.
Territory: `tools/layout_diff.py`, `src/rvt/famgen/layout_law.py`,
`experiments/layout/**`, `tests/test_layout_law.py`, this record.

## 0. One-paragraph verdict

**The #40 premise — "content equal, construction different => the audit
rejects our physical layout" — is REFUTED by measurement.**  The matched
pair is element-roster-equal (mod F1's 2 imported BrowserOrganizations) and
25/41 content-corresponding records are **byte-model-identical after id
normalization**, but the self-Family record and its header carry a finite
**kept-ours field residue** (the fields the F-probe swap deliberately kept
ours: category, partType, type-table shape, order-cell shape, counters,
refTypeIds, locked/param BIP rows, deletion-parent convention) — and that
residue **separates the entire 29-file corpus perfectly** (true in all 7
FAIL, false in all 22 PASS), while **every pure ORDER predicate is already
exonerated observationally**: SUB_O1 (FAIL) carries a donor-convention
order and B7 (PASS) carries the donor's native order, so no ordering
separates PASS from FAIL.  Batch 47 (STAGED, 2 controls + 7 probes) tests
order **directly** anyway (M1/M2 pure byte transplants, machine-proven
content-untouched) and splits the residue one field-axis at a time
(M3..M6); `layout_law.py` ports the M1 convention behind an opt-in flag,
proven end-to-end by BX_layout_f1i1.  DEMO v6 is HELD (see §6).

## 1. What was measured (tools/layout_diff.py enumerate → experiments/layout/layout_diff.json)

The added famdoc unit (last unit of `Partitions/21`) of both probes,
decomposed to records; roles aligned by (class, k-th-by-ascending-id);
per-record decoded values id-normalized through the alignment and
leaf-diffed with ORDER/FIELD/IDENTITY/CONTENT classification; block
packing; the inline ADocument (located by unit GUID); host side via the
base+loader-matched comparator H8B (same rst base, same famload loader,
FAIL — the cleanest pair in the corpus: its delta is unit content alone).

**The complete suspect list between SUB_ALL (PASS) and F1 (FAIL):**

| # | surface | class | delta |
|---|---------|-------|-------|
| 1 | record order (seq 101/102/103, same permutation) | ORDER | SUB_ALL: self, projViewer, projView, projDrawing, projViewport, units, then our 35 in famgen order (a **deletion artifact** — donor relative order of the 6 surviving frame elements). F1: famgen allocation order (self, units, levelType, level, projView, projViewer, projViewport, projDrawing, …). Both ascending-id. |
| 2 | self-Family seq-102 record | FIELD | m_categoryId (−2001330 donor structural-column vs −2001040 ours electrical-equipment); m_partType (−1 vs 14); m_pFamilyTypes (5 pairs, idx 1 vs 1 pair, idx 0); m_familyParams (18 rows incl. donor BIP −1001205 vs our 17); m_locked (4 incl. BIP vs 3); m_nextAbsorbedIndex (3165 sparse vs 42 dense); m_predefinedLimitIdx (1963 vs 35); m_refTypeIds (1 vs 0); m_cellList (materials+dims+identity+electrical, one identity group vs dims+identity+electrical+identity — famgen emits **two identityData groups**, a duplicate group key no PASS file carries) |
| 3 | self-Family seq-101 header | FIELD | m_parents.m_deletion: donor opens with 4 non-element parents (category −2001330, −1005500, BIP −1001205, external 1177727) then all elements; ours = elements only |
| 4 | DBViewProject header | CONTENT-coupled | m_regenOnly 0 vs 2 (F1's BrowserOrg imports; SUB_ALL passes WITHOUT BrowserOrgs → their presence is not required) |
| 5 | 14 ParamElemFamily records | IDENTITY | `revit.local.family:<famGUID><elemIdHex>` — suffix == own element id in BOTH (verified law); the delta is the family GUID alone |
| 6 | packing / envelope | PARITY | 1 block per seq, flags 4, same packer; counter == n_elements; 64-B footer blob both (E1b: content-indifferent) |
| 7 | inline ADocument | FIELD | 484 B/row (remapped donor, deep registries) vs 72 B/row (our authored minimal); ElemTable rows == unit ids, ascending, m_last == max in both. **Minimal-authored form EXONERATED**: B7 itself is 43 B/row and PASSES (so do B1..B6, U-probes) |
| 8 | host side | BASE-COUPLED | separated via H8B (same base+loader): host deltas do not carry the split |

## 2. The ranking (present-in-all-FAIL / absent-in-all-PASS, 29 files)

Corpus: PASS = SUB_ALL, SUB_S1..S7, S5A, S5B, B1..B7, U12, U15, U25, U16,
U12345 (22).  FAIL = F1, F2, F3, F4, H8B, B0, SUB_O1 (7).  E1/E1b excluded
(H12 byte-copies, donor-shaped == B7); DEMO v5 excluded (7 units, verdict
does not localize).

**12 candidates separate PERFECTLY — every one a self-Family field-residue
feature:** `cell_dup_identity_groups`, `cell_no_materials_group`,
`hdr_deletion_elements_only`, `hdr_deletion_lacks_category`,
`sf_absorbed_dense`, `sf_category_is_ours_electrical`, `sf_locked_no_bip`,
`sf_partType_set`, `sf_predefinedLimitIdx_small`, `sf_refTypeIds_empty`,
`sf_single_type_pair`, `sf_type_idx_zero`.

**No ORDER predicate separates**: `order_view_before_viewer` is true in
6/7 FAIL but false in SUB_O1 (donor-convention order, still FAIL);
`ascending_id` is true everywhere.  **Exonerated by the scan:**
minimal-authored inline ADocument (B7+B1..B6+U's all pass with it),
empty m_deletableElements (SUB_ALL passes with it), familyParams-BIP-row
(measured false everywhere — famgen does emit BIP rows),
BrowserOrg presence (SUB_ALL passes without).

The 12 separating candidates co-vary perfectly (donor-derived self-Family
vs famgen self-Family) — observationally indistinguishable.  Splitting
them is the morph round's job.

## 3. Batch 47 — STAGED (experiments/acceptance/batch_47.json)

2 controls (byte-identical rst + G_ABPD copies) + 7 probes, every gate
green (validator 0 errors, walker clean, 64-B blob, unit records decode
clean, adoc rows == unit ids, single-stream delta vs source), staged
copies md5-verified.  **STAGE ONLY — the orchestrator uploads.**

| probe | one change | mechanics proof |
|-------|-----------|-----------------|
| M1 | F1's 44 records re-sequenced to SUB_ALL's physical order (BrowserOrgs last) | per-seq record byte **multisets permutation-equal**; no-edit re-emission byte-exact before surgery |
| M2 | converse: SUB_ALL's 42 records in famgen roster order | same proofs |
| M3 | F1 + order cell merged to one identityData group (dims<identity<electrical) | encode(decode(x))==x gated before patch; param-id multiset unchanged |
| M4 | F1 + donor sparse counters (nextAbsorbed 3165, limitIdx 1963) | roundtrip-gated scalar patch |
| M5 | F1 + m_partType −1 on BOTH mirrored surfaces (famdoc Family + host Family — mirroring measured on SUB_ALL/H8B/F1) | roundtrip + host-block re-gzip byte-exact gates |
| M6 | F1 + category id prepended to header m_deletion (donor convention) | roundtrip-gated header patch |
| BX_layout_f1i1 | the B0 recipe rebuilt through `layout_law.normalize_doc` (M1 order, monotone ids) | full famgen chain; emitted order machine-verified == convention |

Reading map + verdict→action table: `experiments/layout/probes.json`
(`reading_the_matrix`) and `layout_diff.json` (`decision_table`).  Key
rows: M1 PASS ⇒ order is audited despite SUB_O1×B7 (port ships, v6 next);
M1 FAIL + M2 PASS ⇒ order closed experimentally, law is in M3..M6's
residue; ALL FAIL ⇒ the law is a conjunction or in the five unprobed
residue axes — next round builds BX_cat_gm (category=generic_model through
the famgen chain — category is the top unprobed candidate and byte surgery
cannot flip it coherently), BX_types_5, BX_bip.

## 4. The port — src/rvt/famgen/layout_law.py (opt-in, default OFF)

`normalize_doc(doc, order="donor_frame_first")` — id-assignment
normalization on the finalized doc (the SUB_O1 injection point): a pure
bijection over the same id block so ascending-id (== physical record
order under `build_unit_segments`) follows the M1 convention (self-Family,
proj viewer/view/drawing/viewport, units, then famgen order).  Remaps
every id occurrence, owner links, cached view ids, and **heals the
id-embedded `revit.local.family` suffixes** (measured law: suffix == own
element id — the project loader rewrites them anyway, the standalone .rfa
path needs the heal).  `normalize_order_cell(doc)` — the M3 fix (merge
duplicate group keys; content-preserving, refuses if the param-id multiset
changes).  Nothing in the default pipeline calls either.
`tests/test_layout_law.py`: 8/8 green (convention, bijection, content
census, typeId heal, registry non-staleness, idempotence, emission order,
refusal on unfinalized, order-cell merge).

## 5. Corrections to the running story

* Verdict #40's "content equal" holds only at roster granularity.  The
  construction paths differ in REAL FIELDS the F-swap deliberately kept
  ours (`SF_KEEP_IDENTITY`/`SF_KEEP_REGISTRY` in tools/famdoc_final.py) —
  those fields were never tested by F2 and are exactly the corpus-perfect
  residue.
* SUB_ALL's record order is a **deletion artifact** (donor relative order
  of 6 surviving elements + carried tail), NOT Autodesk's native
  convention — the native convention is what SUB_O1 tested, and it FAILED.
  Any order-law reading of batch 47 must reconcile with that.
* The inline-ADocument axis is now exonerated with force: B7 (donor
  famdoc, PASS) itself carries the minimal 43 B/row authored adoc.

## 6. DEMO v6 — HELD, with reason

The charter commissioned v6-through-the-port speculatively "if the
convention is confidently authorable".  Not met: the order convention the
port authors is corpus-exonerated as a sole law before upload (SUB_O1 ×
B7), so a v6 staged now would re-test a hypothesis two recorded verdicts
already reject and spend a demo-scale upload doing it.  The port + its
injection point are BUILT and proven end-to-end by BX_layout_f1i1; v6 is
one command (`tools/layout_diff.py` port pattern on
`tools/frontdoor.py`'s chain) behind whichever batch-47 verdict names the
law.  If M-verdicts convict a field axis instead, v6 goes through THAT fix
(M3's is already implemented as `normalize_order_cell`; M4/M6 are
one-liners in `skeleton.finalize`; M5 is a product decision — partType −1
until panel infra is authored).

## BRANCH STATE

* Working tree only (repo has no git); all artifacts under territory:
  `tools/layout_diff.py` (enumerate/probes/verify/stage, all run green),
  `src/rvt/famgen/layout_law.py`, `tests/test_layout_law.py` (8/8),
  `experiments/layout/{layout_diff.json, probes.json, accounting.json,
  M1..M6.rvt, BX_layout_f1i1.rvt, _build/**}`,
  `experiments/acceptance/{batch_47.json, CTRL_rstbasicsampleproject_b47,
  CTRL_G_ABPD_b47, M1..M6, BX_layout_f1i1}.rvt` — staged, md5-verified,
  NOT uploaded.
* No edits outside territory; no full-suite run; no donors in anything
  shippable (probes are quarantined proof-only dev content).
* NEXT (orchestrator): upload batch 47 in `reading_order`; read verdicts
  against `layout_diff.json.decision_table`; on ALL-FAIL commission
  BX_cat_gm / BX_types_5 / BX_bip through the famgen chain.

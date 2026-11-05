# #1085 — undriven extrusions are side-ref-plane curve based

Stream: self-battery (index `docs/inbox/self-battery.md`). Issue #1085, steer #1084.

## What was built

`src/rvt/famgen/geometry.py` authored `ExtrusionElem.m_sideRefPlaneCurveBased = False` at both
extrusion sites:
- the polygon/box profile form at `:1452`;
- the circle profile form at `:2500`.

Both now write **True**. That is what every born extrusion carries: 2,161 of 2,161 in the
quarantined corpus, as counted by the #796 conformance instrument.

The drive law's item 4 (`rvt.famgen.drive_law`, #904) still flips a False extrusion to True. On our
own extrusions it is now a no-op. It stays as the safety net for a document authored before this
change, and a test shows it still fires.

## Evidence

- **Matched pair, single variable.** An undriven box and an undriven cylinder were built from
  `main`'s source and from this change. The inputs were the same, with
  `SOURCE_DATE_EPOCH=1700000000` and `PYTHONHASHSEED=0`.
  - `tools/famdiff.py BEFORE AFTER --all` reports **exactly one decoded difference per file**:
    `ExtrusionElem /m_sideRefPlaneCurveBased  ref: False  our: True  [1/1 pairs]`.
  - At the byte level, the one record changes in one byte. The content-derived document GUID
    (#168) moves with it, in `BasicFileInfo`, `Contents`, `Global/History`,
    `Global/PartitionTable` and one framing value in `Partitions/0`, as it does for any authored
    field. A staged desktop pair would differ in document identity too.
  - A second build of the after files is byte-identical to the first.
  - Both after files pass `tools/rvt_validate.py --family` as `VALID (no errors); warnings=0`.
  - Both pass `tools/make_family.py provenance` with `"ok": true`.
  - The pair is kept in the session scratchpad only. It is not committed and not staged.
- **Battery, affected lanes.** `tools/self_battery.py --only "fan-powered-box|part_shape|prism|ifc_route"` was run with the corpus at 2026, 2025 and 2024.
  - Result: 123 rows, **85 pass / 15 fail / 23 alias**, and **0 rows** carry the
    `m_sideRefPlaneCurveBased` question.
  - Before the change, the field was the failing question on 49 of these rows (#796 record, class 3). Every one of them now passes.
  - The 15 remaining failures are other classes, each already tracked:
    - 12 are `part_shape` circles at 2024 failing at **build** (`KeyError: ArcElemCell`, #786 / #241);
    - 3 are `prism:rect prism_drive=372`, one per release. That is the #372 chain (#1076). Its conformance questions fell from 5 to 4: the side-ref-plane one is gone, and the `m_dimVersion` ones remain.
- **Full battery on `main` 9e92914 plus this change** (with the corpus, all three releases, a fresh mine):
  - **435 rows: 324 pass / 41 fail / 0 refused / 70 alias.** Before this change it was 275 / 90.
  - The 49 rows moved to pass. The 41 left are the other filed classes: 34 for 2024 arc builds (#786 / #241), 2 for downlight writes (#94), 3 for `'372'` prisms (#1076) and 2 for nested `m_refFaces` (#1086).
  - The **pinned probes are 7/7**. That includes `shape_mixed_assembly`, which failed on this one field before.
- **Tests.** `tests/test_side_ref_plane_1085.py` has 15 tests:
  - every part shape (5 generic, 3 composite);
  - the undriven rect and ring prisms;
  - both fan-powered kinds;
  - the drive law as a no-op on our own extrusions;
  - the drive law still flipping a False extrusion;
  - the field read back from the written file under its own release.
  - Without the fix, **14 of the 15 fail**. Only the drive-law safety net passes (the law still
    flips a False extrusion), which is independent of the fix by design.
  - With the fix, all pass. That includes the read-back through the #796 `iter_objects`, now
    at 2026, 2025 and 2024 after the review.
- **Regression.** The 26 test files that build or inspect extrusions give 790 passed, 78 skipped, 0 failed with the change.
  - The files: famgen geometry, factory, families, determinism, bisect, IFC assembly and family, drive law, the drives-rest suites, and anatomy, among others.
  - **That set missed two shard modules**, `tests/test_matrix_evidence_981.py` and `_984.py`. They pin the generator fingerprints of the two evidence lineages (`matrix.EVIDENCE_FORMS`), and the first head of this PR turned 5 of their tests red. The independent review caught it, and the sandboxed CI on that head showed exactly those 5 (6,682 passed). They now pass, with the fix below; with `tests/test_doc_caveats_990.py` and `tests/test_router.py` added, the set gives 215 passed, 13 skipped.

## What this is not

- It is a **conformance** fix, not a behaviour fix. Our undriven extrusions already open on the
  desktop with False. The change is made because every born specimen carries True, and no route
  claims a new Revit behaviour from it (hard rule 4).
- Driven documents already carried True on every extrusion, since the law flips every extrusion in the document. The owner's desktop opened that law (#904). So True on undriven extrusions inside a driven document already has a desktop verdict; True in a wholly undriven document does not have one yet.
- **No desktop check is asked for.** Per S-2026-09-04-a, it rides with the next verdict-harness batch if one is warranted. Nothing is staged.
- **The certified ledger is unchanged**: its family evidence is fixed `.rvt` files, not regenerated ones.
- **What changes in each lineage (#1085 DONE 5).**
  - **Undriven lanes** change in this field plus the content-derived document GUID: part shapes, undriven prisms, the fan-powered box.
  - **Driven lineages** change in the document GUID only, because the drive law already set the field True on every extrusion of a driven document. These are the two `matrix.EVIDENCE_FORMS` recipes:
    - the IFC downlight (`L_downlight_loaded.rvt`, #981);
    - the stage_L8 family set: panelboards, transformer, house switchboard (`stage_L8_lp4.rvt`, #984).
  - `finalize` derives the document GUID from content before the law runs. The authored value is now True at that moment, so the GUID moves.
  - Their new reviewed fingerprints are recorded in `src/rvt/frontdoor/matrix.py`, `reviewed_at` "#1085":
    - downlight: 2026 `94bf9a65…`, 2025 `78914361…`;
    - stage_L8: 2026 `54fc1536…`, 2025 `8bb37bcb…`.
  - `DOWNLIGHT_EARLIER_FORM`, `STAGE_L8_EARLIER_FORM` and the doc rows that repeat them (`docs/product/PERMUTATION-MATRIX.md`, `plugin/docs/HONEST-STATUS.md`) name the change.
- **The DONE 3/4 pair is not staged.** No behaviour is claimed: True on every extrusion of a driven document already rode the #904 desktop-verified law. A desktop check, if one is ever warranted, rides the next batched verdict run (S-2026-09-04-a).

## BRANCH STATE

- **Files:**
  - `src/rvt/famgen/geometry.py` (two lines);
  - `src/rvt/frontdoor/matrix.py` (the two evidence fingerprints and caveats);
  - `docs/product/PERMUTATION-MATRIX.md`, `plugin/docs/HONEST-STATUS.md` (the caveat rows);
  - the plugin mirrors (`tools/sync_plugin.py`);
  - `tests/test_side_ref_plane_1085.py` (new);
  - `tests/ci_shard.d/1085-side-ref-plane.txt` (new);
  - this fragment, plus one index line in `docs/inbox/self-battery.md`.
- **Gates:** listed in the PR body.
- **Staged / shipped:** nothing staged for the viewer.

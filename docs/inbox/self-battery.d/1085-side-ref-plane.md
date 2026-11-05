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
  - `tools/famdiff.py BEFORE AFTER --all` reports **exactly one difference per file**:
    `ExtrusionElem /m_sideRefPlaneCurveBased  ref: False  our: True  [1/1 pairs]`.
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
  - Without the fix, **13 of the 14 build-side tests fail**. The one that passes is the
    safety-net test (the law still flips a False extrusion), which is independent of the fix by design.
  - With the fix, all 15 pass. That includes the read-back through the #796 `iter_objects`.
- **Regression.** The 26 test files that build or inspect extrusions give 790 passed, 78 skipped, 0 failed with the change.
  - The files: famgen geometry, factory, families, determinism, bisect, IFC assembly and family, drive law, the drives-rest suites, and anatomy, among others.

## What this is not

- It is a **conformance** fix, not a behaviour fix. Our undriven extrusions already open on the
  desktop with False. The change is made because every born specimen carries True, and no route
  claims a new Revit behaviour from it (hard rule 4).
- Driven documents already carried True on every extrusion, since the law flips every extrusion in the document. The owner's desktop opened that law (#904). So True on undriven extrusions inside a driven document already has a desktop verdict; True in a wholly undriven document does not have one yet.
- **No desktop check is asked for.** Per S-2026-09-04-a, it rides with the next verdict-harness batch if one is warranted. Nothing is staged.
- **The certified ledger is unchanged**: its family evidence is fixed `.rvt` files, not regenerated ones. Future builds of the IFC downlight and the fan-powered box differ from earlier ones in exactly this field.

## BRANCH STATE

- **Files:**
  - `src/rvt/famgen/geometry.py` (two lines);
  - `plugin/lib/src/rvt/famgen/geometry.py` (mirror, by `tools/sync_plugin.py`);
  - `tests/test_side_ref_plane_1085.py` (new);
  - `tests/ci_shard.d/1085-side-ref-plane.txt` (new);
  - this fragment, plus one index line in `docs/inbox/self-battery.md`.
- **Gates:** listed in the PR body.
- **Staged / shipped:** nothing staged for the viewer.

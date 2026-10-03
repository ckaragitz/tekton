# #996: what WF_fix / WF_nofix certify, stated once; a caveat for each cited file

Refs #996 (from the review of #995), PG1.

## What was built

1. **One wording of the walls + families shape.** WF_fix and WF_nofix are
   both walls + **one** loaded family. The ledger's WF_nofix entry and
   verdict #27 (genesis-audit.md) say the failing file had 8 families and
   leave the attribution open. No walls + N families ladder has run since:
   `genesis-audit.md` has no later entry, and the ledger has no WF file other
   than these two.
   - `matrix.WALLS_FAMILY_SHAPE` = "walls + one loaded family (WF_fix /
     WF_nofix; whether more families in one file pass is open, verdict #27)".
   - `matrix._OPEN_BUG` and `intent.OPEN_BUG_TEXT` / `_CELL_WHY` build from
     that constant. `GENESIS-BASE.md`, `PERMUTATION-MATRIX.md` (3 rows and the
     "Open bug r2" bullet, which said **exonerated**), `HONEST-STATUS.md` and
     `SKILL.frontdoor.md` quote it verbatim.
   - The `combination_check` reasons are now sized by the family count
     (`intent._wf_shape`). One family reads "the WF_fix / WF_nofix certified
     shape". N > 1 reads "certified only as … with N families no viewer
     verdict exists". The `--strict` hint no longer calls the shell
     "certified".
   - Stale text was fixed along the way:
     - `HONEST-STATUS.md`'s open-cell row named the wrong cell ("walls AND
       placed families") and a stamp the engine has not emitted since the
       stamp keyed on placed instances. `SKILL.frontdoor.md` (shipped in
       `plugin/lib`) did the same.
     - `src/rvt/frontdoor/__init__.py` and the `build.py` docstrings were
       corrected.
     - Three comments in `tests/test_frontdoor.py` were corrected.
2. **A caveat for each cited file** (`tests/test_doc_caveats_990.py`).
   - The unit must still carry the caveat's issue tag.
   - The kind phrase must now follow the file's own mention, before the next
     registered file named in the unit. The #996 false pass now fires for
     `stage_L8_lp4.rvt`: "ROOM2025_walls.rvt (an earlier form, #984) and
     stage_L8_lp4.rvt certified".
   - Names joined only by separators (`A` / `B`, "A + B", "A and B") form one
     group, and the caveat after the group covers all of them ("both
     mechanism only"). Six such groups in the docs needed this.
   - The tag is unit-level because REQUIREMENTS.md's note writes "(#984)"
     once, before naming three files.
3. **Smaller items.**
   - `tests/test_ci_fresh.py` near-miss commit: `docs/product-x.md` is
     tolerated drift.
   - The #990 record's BRANCH STATE file list omits
     `plugin/docs/HONEST-STATUS.md`, which #995 changed (its "Staged" line
     says so). Correction, 2026-10-03: the list should include it. That
     fragment is left as written.

## Evidence
- `tests/test_open_cell_996.py` (new, 61 cases) pins:
  - the constant's words;
  - the ledger still saying one family / 8 families;
  - the engine texts quoting the constant;
  - each quoting surface carrying it verbatim;
  - no scanned surface matching the overclaim pattern (frontdoor `*.py` /
    `*.md`, the shipped skills, `plugin/docs`, `docs/product`; REQUIREMENTS.md
    is a dated log and is excluded);
  - the pattern firing on all six old texts;
  - the family-count wording.
- Gates (`RVT_SKIP_LARGE=1`): test_open_cell_996 + test_doc_caveats_990 +
  test_frontdoor + test_router + test_matrix_evidence_981/_984 +
  test_place_fixtures together: **372 passed / 18 skipped**.
  test_ci_fresh: 28 passed / 2 skipped. `intent` now imports `matrix` for the
  constant: +2.4 ms to `import rvt.frontdoor.intent` (44 ms total, `-X importtime`).

## Open
- `tools/frontdoor.py:35-38` (a hot file) still describes the old
  walls+families bug and stamp in its module docstring. That needs a
  `hot-file` PR of its own: #998.
- Whether walls + N families in one file pass is still open. A walls + N
  families ladder (N = 2, 4, 8, one variable per batch) is the experiment
  that decides it, and it needs a viewer round.

## BRANCH STATE
- Files: `src/rvt/frontdoor/{matrix,intent,build,__init__}.py`,
  `src/rvt/frontdoor/SKILL.frontdoor.md` + their `plugin/lib` mirrors (sync),
  `plugin/skills/tekton-author/references/GENESIS-BASE.md`,
  `plugin/docs/HONEST-STATUS.md`, `docs/product/PERMUTATION-MATRIX.md`,
  `tests/test_open_cell_996.py` (new), `tests/ci_shard.d/996-open-cell.txt`
  (new), `tests/test_doc_caveats_990.py`, `tests/test_ci_fresh.py`,
  `tests/test_frontdoor.py` (comments only), this fragment.
- Staged: nothing. A wording change certifies nothing (hard rule 4).

# #990: every shipped skill doc and product doc carries the caveat where it names registered evidence

Stream: perm-matrix. Issue #990 (follow-up to #984 / #989 and #988 / #991).

## What changed

1. **`plugin/skills/tekton-author/references/GENESIS-BASE.md` item 3** (a shipped skill
   reference). It was headed "THE OPEN BUG -- walls + loaded families TOGETHER". It cited
   `electrical_room_2500a_walls_only.rvt` ("walls alone PASS") and `stage_L8_lp4.rvt`
   ("families alone PASS") with no #984 caveat, and it described a stale front-door policy:
   `--strict` shell = walls only, and a default stamp of `walls+families combination
   unverified`. Its heading is now "THE OPEN CELL -- PLACED INSTANCES of our generated
   families on our composed genesis base", in `matrix._OPEN_BUG`'s wording: walls, loaded
   families and walls + loaded families are certified (WF_fix / WF_nofix). The 2500a shell is
   marked **mechanism only** (#984) and stage_L8 an **earlier form** (#984), with the ledger's
   verdicts #24/#25 wording. The stamp is `intent.OPEN_CELL_STAMP`, and `--strict` now reads
   shell = walls + loaded families, equipment = the placed instances.
2. **`docs/product/REQUIREMENTS.md`**: line 98 (the `(8)` ledger-parity finding) gets a
   `[#990 note: ...]`. It says electrical_room_2500a_walls_only and W1 are MECHANISM ONLY and
   ROOM2025_walls is an EARLIER FORM, so none of the three certifies today's front-door
   output. The widened guard found three more lines in the same dated measurement logs, and
   they get the same treatment:
   - line 96: W1 + RSOLID are mechanism only (#984);
   - line 154: L1a is mechanism only (#984), and L_downlight_loaded is an earlier form (#981);
   - line 187: ROOM2025_walls is an earlier form (#984).

   The measurements themselves are untouched: each note is appended in brackets.
3. **`docs/product/PERMUTATION-MATRIX.md` row `prompt → rfa → loaded-rvt`**:
   - *how* gains the open-cell clause and stamp.
   - *evidence* gains `tests/test_frontdoor_standalone.py`, the fresh-clone placing test, with
     no viewer verdict.

   These are the two clauses the chain's note in `matrix.py` carries.
4. **`matrix.STAGE_L8_EARLIER_FORM`**: "verdict #25 RETRACTED it as an empty-design
   translation" now reads in the ledger's wording (#991): "verdicts #24/#25: placement on the
   genesis lineage unproven (#24), and the PASS an empty-design short-circuit (8 families + 0
   walls + 0 instances, #25)". The five PERMUTATION-MATRIX.md rows that paraphrased "verdict
   #25 retracted its PASS" (59, 68, 70, 85, 101) are aligned the same way. On the test side:
   - `tests/test_matrix_evidence_984.py`'s token list is updated **deliberately**. It drops
     "verdict #25" / "RETRACTED", adds "verdicts #24/#25" and the two ledger clauses, and
     asserts "RETRACTED" is absent.
   - The test is renamed `..._states_verdicts_24_25_and_the_current_status`.
   - `plugin/docs/HONEST-STATUS.md:30` carries the same paraphrase. It is left as is because
     it is outside this territory, and it still passes every guard (it says "earlier form",
     #984). It is a one-phrase follow-up.
5. **The guard, `tests/test_doc_caveats_990.py`** (new; shard drop-in
   `tests/ci_shard.d/990-doc-caveats.txt`).
   - **Scope:** `plugin/skills/**/SKILL.md`, `plugin/skills/**/references/*.md`,
     `plugin/docs/*.md` and `docs/product/*.md`.
   - **Rule:** for every `EVIDENCE_FORMS` / `EVIDENCE_MECHANISMS` path, a *unit* that matches
     one of its `doc_names` regexes must contain the caveat's tag and kind phrase. The tag is
     `#981` for the downlight and `#984` for the rest. The phrase is `earlier form` or
     `mechanism only`, matched case-insensitively.
   - **Units:** a table row is one line; each line inside a code fence is a unit (the dated
     logs keep one finding per line); prose is a paragraph, split at each new list item,
     because prose wraps.
   - **Self-tests:** the guard fires on the shapes #990 found: the wrapped prose of the old
     item 3, the fenced log line and an uncaveated table row. It also checks that a caveat in
     the next list item does not cover this one, and that every registered file is named
     somewhere in scope, so a drifted `doc_names` is caught.
   - **Pins:** GENESIS-BASE.md carries `OPEN_CELL_STAMP` and not the stale stamp, and the
     chain row carries both clauses.
   - **Exclusions: none.** `EXCLUDED` is an empty dict that must list path + reason. The
     dated logs are caveated in place, not exempted.
6. **The freshness law (forced by 5).** The guard reads every `docs/product/*.md` from the CI
   shard. `tests/conftest.py` / `test_ci_fresh.py` therefore require `tools/dev/ci_fresh.sh`
   `SHARD_READS` to cover them, so `product/PERMUTATION-MATRIX[.]md$` widened to `product/`,
   the whole directory: a docs/product file *added* on main is then STALE as well. In
   `tests/test_ci_fresh.py`:
   - one STALE row is added (`docs/product/REQUIREMENTS.md`);
   - the awk near-miss fixture `docs/product/PERMUTATION-MATRIX-md` would now be blocking, so
     it becomes `docs/coverage-x.md`, a near miss of the `coverage/` slash. The
     `AUTONOMY_md` near miss still exercises the literal dot.

   The guard spells its `plugin/docs` glob as a join, because the scanner reads a
   `plugin/docs/*` literal as the repo's own `docs/`.

## Not proven (hard rule 4)
Caveats in prose say what the ledger certifies. None of this makes any file open in Revit.

## BRANCH STATE
- Files: `plugin/skills/tekton-author/references/GENESIS-BASE.md`, `docs/product/REQUIREMENTS.md`,
  `docs/product/PERMUTATION-MATRIX.md`, `src/rvt/frontdoor/matrix.py` (one caveat constant) +
  its mirror `plugin/lib/src/rvt/frontdoor/matrix.py` (sync), `tests/test_matrix_evidence_984.py`,
  `tests/test_doc_caveats_990.py` (new), `tests/ci_shard.d/990-doc-caveats.txt` (new),
  `tools/dev/ci_fresh.sh` (SHARD_READS), `tests/test_ci_fresh.py`, this fragment.
- Gates (`RVT_SKIP_LARGE=1`): test_matrix_evidence_981 + _984 + test_doc_caveats_990 + test_router*.py +
  test_frontdoor_manifest_pin + test_ci_fresh + test_conftest_scaffolding + test_records_layout +
  test_plugin_sync together: **354 passed / 15 skipped** (144 s); test_doc_caveats_990 alone 35 passed. `tools/route.py matrix`
  self-audit clean (25 cells / 27 stages / 5 chains). `tools/sync_plugin.py` then `--check`
  in sync. `validate_plugin.py` PASS. `check_portable_paths.py` ok.
- Staged: nothing. The HONEST-STATUS.md:30 "verdict #25 retracted" phrase was aligned to the
  verdicts #24/#25 wording when this shipped (plugin/docs is hand-authored, §3b).

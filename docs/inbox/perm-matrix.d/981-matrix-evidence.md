# #981 — the downlight's certified evidence is named as an EARLIER form, and a guard keeps it honest

Stream: perm-matrix (index `docs/inbox/perm-matrix.md`). Issue #981 (Refs #980 #916 #913 #950,
PG1). Route taken: **2 (re-word)**; staging a viewer batch for the current downlight is the
separate, human-gated route 1 and is not done here.

## What was wrong

`src/rvt/frontdoor/matrix.py` cited `certified:experiments/families/ifc/L_downlight_loaded.rvt`
for `rvt.ifc.famfrom_ifc:make_downlight` in six places — stages `facts->rfa` and `rfa-load`,
cells `ifc->rfa`, `rfa->rvt`, `rfa+rvt->rvt`, chain `ifc->rfa->loaded-rvt` — and
`docs/product/PERMUTATION-MATRIX.md` in four rows. The downlight's generator output has moved
since that certification: parameter drives (#913 / #950, 2026-10-02) and one full arc per plan
circle (#916 / #980; can / trim / lens). `verify_evidence()` only checked that the citation is
in the ledger, so nothing noticed.

## What changed

- **Wording.** One constant, `matrix.DOWNLIGHT_EARLIER_FORM`, now rides every row citing the
  file (stage `does`, cell caveats, chain note): the certified file holds an EARLIER form;
  it was certified on 2026-08-04 (verdict #21), before the repo's history, and the family has
  changed in many ways since -- among them standard parameters (#601/#631), drives
  (#913/#950) and full-arc plan circles (#916/#980), the list stated as not complete (the
  first push named only the last two; corrected after the #985 review); today's output is
  family-mode validator VALID (0 errors) with NO viewer or desktop-Revit verdict; the
  certification speaks for the earlier form and the four-registry load mechanism. `_RFA_HOST`
  names it as an earlier form too. **No status changed** (all six still `works` — their
  `works` rests on runnable tests; the doc already said the certification is of the loaded
  project, not a standalone `.rfa`). No citation was removed or added.
- **Rendered doc.** `PERMUTATION-MATRIX.md` is hand-kept (pinned by `tests/test_router.py` for
  status only); its four rows naming `L_downlight` (ifc → rfa, rfa → rvt, rfa + rvt → rvt,
  ifc → rfa → loaded-rvt) gained the same "an earlier form … #981" parenthesis, and so did
  the Family-generation row of `plugin/docs/HONEST-STATUS.md` (hand-authored, §3b).
- **Guard.** `matrix.EVIDENCE_FORMS`: certified file → `{generator, build, certified,
  reviewed, reviewed_at, caveat}`. `certified` = the generator's output sha256 at
  certification (`None` for the downlight: not knowable — the ledger entry predates the repo's
  history and the certified load was built with the owner-machine family container);
  `reviewed` = the sha256 the wording was last reviewed against, per release.
  - `verify_evidence()` (static, no build, so `tools/route.py matrix` and `test_router` see it):
    a row citing a file whose `certified != reviewed` must contain that entry's caveat.
  - `generator_fingerprint(path, release)` rebuilds through the cited generator exactly as
    `build` says (default IFC facts, `start_id=1000`, `standalone_family_write(provenance=False)`
    to `f.rfa`, inside the release's build context — the plan-arc record's convention, which is
    why the numbers agree with `param-drive.d/916-plan-arc.md`'s head column).
  - `tests/test_matrix_evidence_981.py` fails when the rebuilt sha differs from `reviewed`,
    with a message saying to re-word first and only then re-record the fingerprint.

## Evidence (numbers)

- Reviewed fingerprints at `18153b4`: 2026 `ea274092…7910`, 2025 `4a67e333…79bb`, family-mode
  validator 0 errors both; identical to the #980 record's head column (`ea274092…` /
  `4a67e333…`). The file name is in the bytes (`downlight.rfa` gives `e3cd5920…`), the
  directory is not (test pins two directories equal). ~1 s per build.
- The issue quotes 2026 `df3f33da→5105cbcf` / 2025 `82545de6→f94f39ea`: a different build
  convention (file name / writer) — not reproduced here; the guard records its own convention
  explicitly in `build`.

## What the guard can and cannot prove

- CAN: the matrix's words cannot silently outlive the next byte change to the downlight — the
  rebuild test goes red in that PR; and no row can cite the file without the caveat.
- CANNOT: say anything about Revit (hard rule 4); a matching fingerprint means "the bytes the
  wording was reviewed against", nothing more. It cannot tell whether the *certified* `.rvt`'s
  family equals any generator output (git-ignored binary, unrecorded fingerprint, different
  container) — hence `certified: None` and the mandatory caveat. It covers only files
  registered in `EVIDENCE_FORMS`; nothing auto-discovers other certified generated families.
  And it fingerprints ONE recipe (`standalone_family_write` on the bundled base), not
  necessarily the bytes a user gets: the product-IFC downlight lane still needs the
  owner-disk family container (#94) and falls back to a `generic_model` on a fresh clone.
- Open question (not changed, outside #981's DONE): `L1a_rstbasic_loaded_levelhead.rvt` and
  `stage_L8_lp4.rvt` are cited as *load-mechanism* evidence and also contain families our
  generators made in August; their generators' output has very likely moved too. They are
  cited for the loader, not the family form, so they were left unregistered; registering them
  needs their build recipes (the level-head and the stage-L8 family) found first.

## BRANCH STATE

Branch `fix-981` from `18153b4`, one local commit, not pushed. *Update:* shipped as PR #985
on `claude/pull-latest-main-1cmo56`, rebased onto `a615735`. After the PR's 🛑 review: the
caveat no longer reads as the complete list of changes (the certification predates the
repo's history; standard parameters #601 / #631 are named too), and
`plugin/docs/HONEST-STATUS.md`'s Family-generation row carries the earlier-form note.
- `src/rvt/frontdoor/matrix.py` (+ mirror `plugin/lib/src/rvt/frontdoor/matrix.py` via sync):
  `DOWNLIGHT_EARLIER_FORM`, `EVIDENCE_FORMS`, `evidence_form_is_earlier`,
  `generator_fingerprint`, the `verify_evidence` hook, caveat on six rows + `_RFA_HOST`.
- `docs/product/PERMUTATION-MATRIX.md`: four rows re-worded.
- `tests/test_matrix_evidence_981.py` (11 tests) + `tests/ci_shard.d/981-matrix-evidence.txt`.
- Gates (`RVT_SKIP_LARGE=1`): test_matrix_evidence_981 11 passed; test_router,
  test_router_load_release, test_router_release, test_famgen_archetypes,
  test_frontdoor_json_strict, test_rfa_load, test_specsheet_route_688, test_ci_fresh,
  test_matrix_evidence_981 together 469 passed / 14 skipped; test_conftest_scaffolding +
  test_frontdoor_manifest_pin + test_records_layout 66 passed; test_plugin_sync 9 passed;
  `tools/route.py matrix` self-audit clean (25 cells / 27 stages / 5 chains);
  `tools/sync_plugin.py` then `--check` in sync; `validate_plugin.py` PASS;
  `check_portable_paths.py` ok.
- Also written (after the #985 review): `plugin/docs/HONEST-STATUS.md` (one row),
  `docs/inbox/param-drive.d/983-rereview-correction.md` (the #979 record correction, in its
  own fragment), the new test `test_the_plugin_honest_status_says_earlier_form_too`.
- Staged: nothing (no viewer batch; route 1 is a separate human-gated step).

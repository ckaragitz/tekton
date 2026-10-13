# #1058 -- a shared-parameter file row never refuses a family job

Stream **family-shared-params** (tech-lead session, 2026-10-08). Closes #1058. Refs #1053 #1047.

## What changed
Before this, `FamilyDoc.add_family_parameter` RAISED when a row of the document's shared-parameter
file named the parameter but the writer could not author it as that row:
- a DATATYPE that disagrees with the parameter's spec;
- a DATATYPE the writer has no spec for. `SHARED_DATATYPE_SPECS` holds no `YESNO` and no
  `NUMBER_OF_POLES`, which are Revit's own datatypes for a Yes/No and a number-of-poles parameter,
  and our own `tools/shared_params_from_rfa.py --txt` writes them;
- a parameter authored per instance or by formula.

The constructor then refused the whole job and delivered no file (hard rule 1). It took only one
row such as "Show Front Clearance YESNO", which `equipment_clearance` authors on every equipment
family. #1053's third review found it.

Now:
- **A YESNO row is authored SHARED** at its GUID with the Yes/No storage (`ParamDefYesNo`), the
  storage class the parameter-profile path already writes (#866). That is #1058 DONE (1).
- **Every other row the writer cannot author is not used.** The parameter is authored LOCAL, and a
  note names the row and the true reason:
  - **a datatype not yet authored shared** (NUMBER_OF_POLES, ELECTRICAL_FREQUENCY …): "this writer
    does not author a shared 'NUMBER_OF_POLES' parameter yet (the row itself is fine)". DONE (1)
    allows a number-of-poles row to stay local; panel_can's own poles parameter is local-only
    anyway.
  - **a disagreeing datatype:** "the file declares DATATYPE 'TEXT' but the family authors it as …
    (fix the file row to share it)";
  - **a per-instance or formula parameter:** "this route does not share such a parameter (the
    parameter-profile path does, #866)".
Two things hold as before:
- No second GUID ever papers over a disagreement. That was #165's reason for the refusal, and it
  stands.
- A row that matches is still authored SHARED at its GUID.

## Evidence
- `tests/test_shared_rows_never_refuse_1058.py`: **7 passed**. One file holds a YESNO type
  switch, a per-instance switch, a formula switch, a NUMBER_OF_POLES row, a TEXT Width and a
  matching Voltage. With it:
  - `make_panelboard`, `make_transformer` and `make_device` each deliver VALID with 0 errors;
  - every unusable row is local, its note giving its own reason;
  - the YESNO switch and Voltage are shared;
  - `make_family.py panelboard --shared-params` exits 0.
- **The YESNO row read back from the written panelboard** is a `ParamElemExternal` with
  `ParamDefYesNo` storage at the row's GUID. Its value equals the local build's, and no GUID appears
  twice.
- **The per-instance and formula branches are pinned directly:** a matching LENGTH row leaves the
  parameter local with its instance binding (`m_instanceParam`) or its formula, while a plain one is
  shared.
- **Mutation.** Five single-line mutations each fail the file:
  - the formula condition dropped;
  - the local fallback losing its instance binding;
  - the Yes/No storage dropped;
  - YESNO unmapped;
  - the not-yet-shared note dropped.

  Before this round, a review's mutants on the first two survived.
- **A standard parameter is kept, not dropped.** A standard parameter (the #601 step) whose row
  has another datatype used to vanish from the family, reported only as "skipped" (found by
  #1053's fourth review). It is now authored LOCAL with the row named. Two such rows are read back
  from the written file. On `main`'s skeleton the same test fails.
- The two tests that pinned the refusal now pin the new behaviour: local + note, never a second
  GUID.
  - `test_famgen_factory`: Width TEXT through `make_panelboard`.
  - `test_famgen_skeleton`: a DATATYPE clash and an instance row.
- **`test_panel_can_1047`'s shared-file test** now finds the YESNO "Show Front Clearance" shared
  (`ParamDefYesNo`). It sets aside a TEXT "Power Factor" row instead, to keep pinning panel_can's
  datatype check.
- **Related suites:** this file, `test_panel_can_1047`, `test_famgen_factory`,
  `test_famgen_skeleton`, `test_param_profile_866/875/886` and `test_shared_params_from_rfa_866`
  give **221 passed, 14 skipped**. Plugin sync is clean.

## Limits
- **Still local:**
  - A NUMBER_OF_POLES row (and any other datatype not in `SHARED_DATATYPE_SPECS`) stays local
    through `add_family_parameter`.
  - A per-instance or formula parameter with a matching row stays local here, while the
    parameter-profile path (#866) shares such parameters.
- **Storage.** A matching TEXT or INTEGER row is authored with the `ParamDefValue` storage, not
  `ParamDefString` / `ParamDefInt`. That predates this PR and is a follow-up.
- **Reader refusals.** A malformed row (bad GUID, repeated name) still refuses inside the reader,
  and two names sharing one GUID are both authored. That is #1061, which follows this PR.

## BRANCH STATE
- **Files:**
  - `src/rvt/famgen/skeleton.py` (`add_family_parameter`'s shared branch);
  - `tests/test_famgen_factory.py`, `tests/test_famgen_skeleton.py` (the refusal pins, now notes);
  - `tests/test_panel_can_1047.py` (its shared-file test: the YESNO row now shares);
  - `tests/test_shared_rows_never_refuse_1058.py`, `tests/ci_shard.d/1058-shared-rows.txt`;
  - this record;
  - the plugin mirror.
- **Gates:** in the PR body. Nothing is staged for the viewer.

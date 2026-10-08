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

Now such a row is **not used**. The parameter is authored LOCAL, and a note names the row and the
reason ("shared-parameter file row 'Width' NOT used -- the file declares DATATYPE 'TEXT' but …").
Two things hold as before:
- No second GUID ever papers over a disagreement. That was #165's reason for the refusal, and it
  stands.
- A row that matches is still authored SHARED at its GUID.

## Evidence
- `tests/test_shared_rows_never_refuse_1058.py`: **5 passed**. One file holds a YESNO type
  switch, a per-instance switch, a formula switch, a NUMBER_OF_POLES row, a TEXT Width and a
  matching Voltage. With it:
  - `make_panelboard`, `make_transformer` and `make_device` each deliver VALID with 0 errors;
  - every unusable row is local and named in a note;
  - Voltage is shared;
  - `make_family.py panelboard --shared-params` exits 0.
- **A standard parameter is kept, not dropped.** A standard parameter (the #601 step) whose row
  has another datatype used to vanish from the family, reported only as "skipped" (found by
  #1053's fourth review). It is now authored LOCAL with the row named. Two such rows are read back
  from the written file. On `main`'s skeleton the same test fails.
- The two tests that pinned the refusal now pin the new behaviour: local + note, never a second
  GUID.
  - `test_famgen_factory`: Width TEXT through `make_panelboard`.
  - `test_famgen_skeleton`: a DATATYPE clash and an instance row.
- **Related suites:** `test_famgen_factory`, `test_famgen_skeleton`, `test_shared*`,
  `test_param_profile*`, `test_profile_map*`, `test_transformer_mass_630` and
  `test_equipment_clearance_882` give **226 passed, 14 skipped**. Plugin sync is clean.

## Limits
- A YESNO or NUMBER_OF_POLES row is never authored SHARED: there is no shared Yes/No or
  number-of-poles writer yet. Sharing them is a separate step, with a corpus check of the
  storage class.

## BRANCH STATE
- **Files:**
  - `src/rvt/famgen/skeleton.py` (`add_family_parameter`'s shared branch);
  - `tests/test_famgen_factory.py`, `tests/test_famgen_skeleton.py` (the refusal pins, now notes);
  - `tests/test_shared_rows_never_refuse_1058.py`, `tests/ci_shard.d/1058-shared-rows.txt`;
  - this record;
  - the plugin mirror.
- **Gates:** in the PR body. Nothing is staged for the viewer.

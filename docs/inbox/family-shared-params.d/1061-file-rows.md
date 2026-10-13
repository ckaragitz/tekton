# #1061 -- a shared-parameter file's unreadable rows never refuse the family

## What changed
`skeleton.read_shared_parameter_file` used to stop the whole family job with a `ValueError` on any of
these, and on `main` `make_family.py panelboard --shared-params dup.txt` exited 2 with "factory
refused the job" (found by #1053's fourth review):
- a repeated name;
- a malformed GUID;
- a row before its `*KIND` header.

A user's file is input we do not control (hard rule 1). Each such row is now **not used**, and the
table's `notes` name it with its file line. The first row of a name is the one used.

**One GUID under two names** used to be read as two rows and written shared twice. Now:
- only the first name keeps the GUID;
- the later name is not used, and noted;
- this holds for a file and for parsed rows passed in (`shared_param_table`).

`SharedParamTable` is a `dict` with `.notes`, and `new_family_document` copies the notes onto the
family's notes. `strict=True` keeps the old `ValueError` for tools that audit a file.

## Evidence
- **`tests/test_shared_file_rows_1061.py`: 7 passed.** Each of the four row problems is checked:
  - through the reader (the notes name each one);
  - in `strict=True`, each on its own file, refused with its own reason (repeated name, malformed
    GUID, one GUID under two names);
  - through `make_panelboard`, which delivers VALID with 0 errors, shares the first row of a name
    at its GUID, and never carries one GUID twice;
  - through the CLI, which exits 0 with VALID.
- **The grammar-edge test in `test_famgen_factory`** now pins `strict=True`'s refusals and
  non-strict's notes. The datatype-clash case there uses its own GUID, so it keeps testing #1058's
  rule. A new case pins the GUID rule: a row reusing PanelName's GUID is not read, and PanelName
  keeps it.
- **Mutation.** Each of these single-line mutants fails the files:
  - the strict GUID-under-two-names check dropped;
  - the reader's one-GUID-per-row pass bypassed;
  - a repeated name's later row used.
- **#1068's last review nits ride here**, since they are the same code:
  - `test_shared_rows_never_refuse_1058` adds a Yes/No case. A TEXT row on a Yes/No type parameter
    is told to fix the row, because a YESNO row would share it. Taking YESNO out of
    `SHAREABLE_SPECS` now fails it.
  - Its module docstring says where the "fix the row" hint is given.
- **Related suites:** with `test_famgen_factory`, `test_famgen_skeleton`,
  `test_shared_rows_never_refuse_1058`, `test_shared_params_from_rfa_866`, `test_panel_can_1047` and
  `test_conftest_scaffolding`, the counts are in the PR body.

## BRANCH STATE
- **Files:**
  - `src/rvt/famgen/skeleton.py`;
  - `tools/shared_params_from_rfa.py` (comments only);
  - `tests/test_shared_file_rows_1061.py` (new);
  - `tests/test_famgen_factory.py`;
  - `tests/test_shared_rows_never_refuse_1058.py` (#1068's review nits);
  - `tests/ci_shard.d/1061-shared-file-rows.txt`;
  - this record;
  - the plugin mirror.
- Built on `main` after #1068 (#1058) merged.
- **Gates:** in the PR body. Nothing is staged for the viewer.

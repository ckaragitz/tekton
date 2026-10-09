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
- **`tests/test_shared_file_rows_1061.py`: 4 passed.** Each of the four row problems is checked:
  - through the reader (the notes name each one; `strict=True` raises);
  - through `make_panelboard`, which delivers VALID with 0 errors and never carries one GUID twice;
  - through the CLI, which exits 0 with VALID.
- **The grammar-edge test in `test_famgen_factory`** now pins `strict=True`'s refusals and
  non-strict's notes. The datatype-clash case there uses its own GUID, so it keeps testing #1058's
  rule. A new case pins the GUID rule: a row reusing PanelName's GUID is not read, and PanelName
  keeps it.
- **Related suites:** with `test_famgen_factory`, `test_famgen_skeleton`,
  `test_shared_rows_never_refuse_1058` and `test_shared_params_from_rfa_866`: 98 passed, 14 skipped.

## BRANCH STATE
- **Files:**
  - `src/rvt/famgen/skeleton.py`;
  - `tools/shared_params_from_rfa.py` (comments only);
  - `tests/test_shared_file_rows_1061.py` (new);
  - `tests/test_famgen_factory.py`;
  - `tests/ci_shard.d/1061-shared-file-rows.txt`;
  - this record;
  - the plugin mirror.
- Built on #1058's commit, so it opens after #1058 merges.

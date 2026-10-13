# #1061 -- a shared-parameter file's unreadable rows never refuse the family

## What changed
`skeleton.read_shared_parameter_file` used to stop the whole family job with a `ValueError` on any of
these, and on `main` `make_family.py panelboard --shared-params dup.txt` exited 2 with "factory
refused the job" (found by #1053's fourth review):
- a repeated name;
- a malformed GUID;
- a row before its `*KIND` header.

A user's file is input we do not control (hard rule 1). Each such row is now **not used**, and the
table's `notes` name it with its file line.

**Every row is taken in file order, as it is read** (`_RowCheck`), against the rows already taken.
A row is not used when:
- it has no name (blank or only spaces);
- it has no valid GUID;
- it repeats an earlier row exactly (the same name and GUID);
- its GUID is already taken under another name. One GUID under two names used to be read as two
  rows and written shared twice.

Every note, and a strict read's refusal, comes in file order. #1072's second review found strict
stopping at a header-less row after a repeated name.

**A second row of a name, with its own GUID, is kept as that name's alternative.** Revit's own
files may carry one name under several GUIDs, and `shared_params_from_rfa` writes them sorted by
GUID, so "the first row" is arbitrary. `SharedParamTable.fit` makes a parameter take the first row
of its name whose DATATYPE fits it, said in a note. `add_family_parameter` and panel_can's
`_keep_local` call it. Before, a name whose first row had another DATATYPE stayed local with a note
that contradicted itself (#1072's second review).

GUIDs are canonicalised (case, braces). Parsed rows passed in (`shared_param_table`) take the same
checks and are named by their KEY: an invalid or braced GUID used to reach the encoder and refuse
the job. A table passed back in is copied with its notes and alternatives.

`SharedParamTable` is a `dict` with `.notes`, and `new_family_document` copies the notes onto the
family's notes. `strict=True` keeps the old `ValueError` for tools that audit a file.

## Evidence
- **`tests/test_shared_file_rows_1061.py`: 15 passed.** Each of the row problems is checked:
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
- **Pinned since the first review:**
  - its exact case: a GUID-taken row, then a valid row of the same name, which is the one used;
    strict stops at the first line;
  - a GUID twin on a name the panelboard really authors (Voltage), which is never shared;
  - parsed rows with a braced upper-case GUID (canonicalised), an invalid GUID and an empty name;
  - a passed-in table's notes, which reach the family's notes;
  - a file row with no name.
- **Pinned since the second review:**
  - strict stops at line 8 (a repeated name) before line 9 (no header), and the notes come in file
    order;
  - two Voltage rows (TEXT, then ELECTRICAL_POTENTIAL): `make_panelboard` and `make_panel_can`
    share the second, the note says so, and nothing calls Voltage unused or local;
  - an alternative's GUID is never reused by another name;
  - parsed rows are named by their key (a renamed dataclass, an object with no `.name`), and a name
    of only spaces is not used.
- **`test_shared_params_from_rfa_866`** reads our own written TXT with `strict=True`, since it is an
  audit.
- **Mutation.** Each of these single-line mutants fails the files:
  - (second round) `fit` bypassed in `add_family_parameter` or in panel_can; an alternative's GUID
    not reserved; a name of spaces kept; rows not named by their key; the rows taken after the read
    instead of during it;
  - the GUID owner not recorded;
  - the GUID check skipped;
  - no canonical GUID;
  - an empty name kept;
  - a passed-in table's notes dropped;
  - the file's notes not attached;
  - (first round) the strict two-names check, and a repeated name's later row used.
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
  - `tests/test_famgen_factory.py`, `tests/test_shared_params_from_rfa_866.py` (strict audit read);
  - `tests/test_shared_rows_never_refuse_1058.py` (#1068's review nits);
  - `tests/ci_shard.d/1061-shared-file-rows.txt`;
  - this record;
  - the plugin mirror.
- Built on `main` after #1068 (#1058) merged.
- **Gates:** in the PR body. Nothing is staged for the viewer.

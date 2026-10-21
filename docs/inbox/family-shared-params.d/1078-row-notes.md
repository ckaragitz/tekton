# #1078 -- shared-parameter row notes that name a code-given row's GUID, and one row type

Stream **family-shared-params** (tech-lead session, 2026-10-21). Closes #1078. Refs #1061 #1072.

The round-4 independent review of #1072 returned NITS. This closes them.

## What changed (`src/rvt/famgen/skeleton.py`)
- **A row given in code is named by its GUID as given.** A file row's note carries its line. A row
  given in code had nothing to tell two rows of one name apart, so its note now reads
  `row 'X' NOT used (GUID '…') -- …`. The same applies to `row 'X' (GUID '…') repeats a name …`.
- **`take_swap` says nothing when `fit` swapped back.** `fit` may set a name's alternative in place
  and, for a later parameter, return to the first row. The row shared is then the first row, so no
  note may say another one is.
- **Every row a checked table keeps is a `SharedParamDef`** with its canonical GUID. A row object of
  another class, dataclass or not, is rebuilt from its fields and named by its key. It is never
  handed on as the caller's own object.
- **A refused shared row names the name's other rows.** When no row of a name fits a parameter, the
  "NOT used … authored LOCAL" note adds the DATATYPE of each alternative it also could not use. A
  per-instance or formula parameter never says so: its rows were never tried, because this route
  does not share such a parameter whatever the row.

## Evidence
- **`tests/test_shared_file_rows_1061.py`: 24 passed** (19 before, plus 5 new):
  - two names' alternatives never share a GUID; the second is refused with its GUID named;
  - a checked table passed back in keeps its alternatives with no second "repeats a name" note;
  - a dataclass row with no `name` field becomes a `SharedParamDef` named by its key, and is shared;
  - a swap that `fit` undid is never reported, and a real one is reported once;
  - a refused row names the other DATATYPEs tried. The per-instance switch test now also pins that
    its note never does.
- Two existing expectations carry the new wording for code-given rows (one here, one in
  `tests/test_famgen_factory.py`). File rows' notes are unchanged.
- Neighbouring modules (`test_famgen_factory`, `test_shared_params_from_rfa_866`,
  `test_shared_rows_never_refuse_1058`, this module): 116 passed, 5 skipped.

## BRANCH STATE
- **Files:**
  - `src/rvt/famgen/skeleton.py`;
  - `tests/test_shared_file_rows_1061.py`, `tests/test_famgen_factory.py`;
  - `docs/inbox/family-shared-params.d/1061-file-rows.md` (its file list: `panel_can.py` added,
    a doubled line removed);
  - this record;
  - the plugin mirror.
- **Gates:** in the PR body. Nothing is staged for the viewer.

# #1008: a text value keeps the user's quotes; "set P to" with no value is refused

Refs #1008, #1006, #1007. S-2026-09-22-a.

## What was built
- **`_convert_value` (text carrier)** unquotes a value only when one matching pair wraps all of it (`"x"`, `'x'`). Before, `strip("\"'")` removed any leading or trailing quote characters, so `set Finish = 'quoted' value` stored `quoted' value`, a string the user never typed. Now `'quoted' value`, `3/4" EMT` and `it's fine` are stored exactly as typed, and `"to"` stores `to`.
- **The sentence grammar refuses a set with no value.** `set Finish to`, `set Finish =` and `set Finish of type T1 =` used to store the delimiter ("to" / "="). Now they are refused by name. A **JSON op**'s empty value is left alone, so it stays a deliberate clear.

## Evidence
- `tests/test_edit_values_1008.py` (new, 12 cases):
  - 8 unquoting rules;
  - 3 no-value refusals;
  - one read-back on a generated conduit: `set Finish = 'hot dip' galvanized` reads back exactly that.
- On base (PR #1010's first head 064905d), 5 of the 12 fail; with the fix, all 12 pass.
- With the 994 / 1000 / 1003 / 1006 / 1009 edit suites, `test_edit_drives_909`, `test_edit_family_{marks_678,mass_659,size_668}`, scaffolding, `test_convert`, `test_router` and `test_convert_combo`: 465 passed / 29 skipped.
- The new module is an `ADOPTERS` row in `tests/test_conftest_scaffolding.py`.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_values_1008.py` (new);
  - `tests/ci_shard.d/1008-edit-values.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. Hard rule 4: no claim here rests on a desktop verdict.

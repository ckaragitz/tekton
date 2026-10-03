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
- On base (PR #1010's first head 064905d, and main fadb9fc alike), 5 of the first 12 fail; with the fix, all 12 pass.
- With the 994 / 1000 / 1003 / 1006 / 1009 edit suites, `test_edit_drives_909`, `test_edit_family_{marks_678,mass_659,size_668}`, scaffolding, `test_convert`, `test_router` and `test_convert_combo`: 465 passed / 29 skipped.
- The new module is an `ADOPTERS` row in `tests/test_conftest_scaffolding.py`.

## Review round (PR #1012, head df299d7, 🛑)
The pair check compared only the first and last characters. A value made of two quoted pieces therefore lost its outer quotes: `set Finish = "a" and "b"` read back from the written `.rfa` as `a" and "b`. That is the exact defect #1008 exists to fix.
- **Fixed:** a value is unquoted only when its outer quote character does not occur inside it, i.e. one pair wraps all of it. `"a" and "b"`, `'x' or 'y'` and `'it''s'` stay as typed. `" x "` keeps its inner spaces, and `""` is a deliberate clear.
- **Nit, fixed:** the no-value refusal now fires only when a delimiter really **ends** the clause (`_ends_on_delimiter`). `set Finish to to`, `= to` and `= =` give the value "to" / "=" again.
- **Nit, fixed:** an unknown parameter is named first (`set Bogus to` → "no parameter 'Bogus'").

**Evidence.**
- `test_edit_values_1008` now has 22 cases, including a read-back of `"a" and "b"` on the generated conduit.
- On main fadb9fc, 9 fail; on this head, all 22 pass.
- The 14 edit suites: **482 passed / 29 skipped**. The first round's "465 / 29" was measured against PR #1010's first head (064905d); against main fadb9fc it was 472 / 29, as the review found.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_values_1008.py` (new);
  - `tests/ci_shard.d/1008-edit-values.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. Hard rule 4: no claim here rests on a desktop verdict.

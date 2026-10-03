# #1006: an unquoted multi-word type name is one name, or a refusal

Refs #1006, #994, #1003, #1005. S-2026-09-22-a (a defect is retired by a fix).

## The defect (found by the review of PR #1005, reproduced on main e074a18)
`_match_set` knew a type name only when it was quoted or a single token. Generated families' type names have spaces ("Conduit - Straight Run 0.75 in 10 ft"), and three things went wrong:
- `set Finish of type Conduit - Straight Run to black` took type "Conduit". `_op_set` matches a type by substring, so the edit targeted the real type and wrote Finish = **"- Straight Run to black"**.
- `set Finish color of type <full name> to black` folded the whole clause into the value of the **default** type.
- `set Width of type Big One to 3 ft` gave type "Big" and value "One to 3 ft".

## The fix
`_quote_type_name(inv, clause)` runs first in `_match_set`, and inside `_value_hint`.
- When it finds an unquoted `of type`, it resolves the family's own type names: the longest one that matches, case-insensitive, at a word boundary. It quotes that name, so the existing grammar reads it whole. That includes names containing "to" ("Run to Ground"), and a name whose prefix is another type name.
- An unquoted name that is not one of the family's types, and runs over more than one word before the `to`/`=` delimiter, is **refused by name**. The refusal lists the types and suggests the quoted form.
- A single-token name keeps the old grammar, which already refuses a name that matches no type.

## Evidence
`tests/test_edit_type_names_1006.py` (new, 12 cases):
- 8 parse rows: the issue's four, case-insensitive with the longest name winning, a name containing "to", the quoted form, and no type;
- 2 refusals;
- the hint keeping a full type name whole;
- one end-to-end case: on a generated conduit, `set Finish of type <its unquoted spaced type name> to black` reads back Finish = "black" with self-checks OK, and a wrong multi-word name is refused.

On base (PR #1005's head `c19f298`), 9 of the 12 fail; with the fix, all 12 pass. The neighbouring edit suites and the scaffolding check together: 132 passed / 8 skipped (`test_conftest_scaffolding`, `test_edit_leftovers_994`, `test_edit_nits_1000`, `test_edit_hint_1003`, `test_edit_drives_909`, `test_convert`). The new module is an `ADOPTERS` row in `tests/test_conftest_scaffolding.py`.

The issue's DONE (1) said row 1 "targets the named type with value black". Its caption is "Finish color", which this family does not have, so the correct outcome is a refusal by name (#994). It now parses the type whole, the caption is refused, and the hint reads `set Finish of type "<name>" = color to black`.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_type_names_1006.py` (new);
  - `tests/ci_shard.d/1006-edit-type-names.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. No claim here rests on a desktop verdict (hard rule 4).

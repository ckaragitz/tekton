# #1009: a rename names its type exactly; a caption containing "of type" is a parameter

Refs #1009, #1006, #1007. S-2026-09-22-a.

## What was built
- **`_op_rename_type` matches the old name exactly** (case-insensitive, one pair of quotes stripped) or refuses by name, listing the types. With types T10 / T2, `rename type T1 to Z` renamed **T10**, on main too. That is the same mis-target #1007 retired for sets (B1). A one-type family may still omit the old name.
- **`_resolve_type_name` skips an `of type` that is part of one of the family's captions.** For example `Size of Type`, when the clause starts with that caption at a word boundary. #1007 had read it as a qualifier and refused `set Size of Type to 5`, which main parsed. A real qualifier after such a caption still resolves, and a wrong one is still refused.

## Evidence
- `tests/test_edit_rename_exact_1009.py` (new, 15 cases): partial old names refused, exact names in any case or quoted, the one-type omission, the parse-level refusal, the four caption forms, and a wrong type after the caption.
- On base (PR #1007 head 2c09b48), the partial renames and the caption forms fail; with the fix, all 15 pass.
- With the #994 / #1000 / #1003 / #1006 suites, `test_edit_drives_909`, scaffolding, `test_convert`, `test_router`, `test_convert_combo` and `test_reduce`: 350 passed / 35 skipped. No caller relied on rename substring matching.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_rename_exact_1009.py` (new);
  - `tests/ci_shard.d/1009-edit-rename-exact.txt` (new);
  - this fragment.
- Staged: nothing. Hard rule 4: no claim here rests on a desktop verdict.

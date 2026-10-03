# #1009: a rename names its type exactly; a caption containing "of type" is a parameter

Refs #1009, #1006, #1007. S-2026-09-22-a.

## What was built
- **`_op_rename_type` matches the old name exactly** (case-insensitive, one pair of quotes stripped) or refuses by name, listing the types. With types T10 / T2, `rename type T1 to Z` renamed **T10**, on main too. That is the same mis-target #1007 retired for sets (B1). A one-type family may still omit the old name.
- **`_resolve_type_name` skips an `of type` that is part of one of the family's captions.** For example `Size of Type`, when the clause starts with that caption at a word boundary. #1007 had read it as a qualifier and refused `set Size of Type to 5`, which main parsed. A real qualifier after such a caption still resolves, and a wrong one is still refused.

## Evidence
- `tests/test_edit_rename_exact_1009.py` (new, 15 cases): partial old names refused, exact names in any case or quoted, the one-type omission, the parse-level refusal, the four caption forms, and a wrong type after the caption.
- On base (main 2698836, PR #1007 squash-merged), the partial renames and the caption forms fail; with the fix, all 15 pass.
- With the #994 / #1000 / #1003 / #1006 suites, `test_edit_drives_909`, scaffolding, `test_convert`, `test_router`, `test_convert_combo` and `test_reduce`: 350 passed / 35 skipped. No caller relied on rename substring matching.

## Review round (PR #1010, head 064905d, 🛑)
The caption skip fired on any caption containing "of type", even when a **shorter** caption plus a real qualifier was the reading. With captions Size / Size of Type and types Big / Big One, `set Size of type Big One = 5` bypassed the #1006 resolution and the #1007 backstop. The grammar then cut the name, and the clause wrote "One = 5" to type **Big**. Main read it correctly.

Fixed: the skip does not fire when the words before the caption's own "of type" are another caption **and** the words after it start with a type of this family; that is the shorter caption's qualifier.

The same probe also found an older mis-target in the grammar's first step, also on main. `set Size of Type 5` with both captions took caption Size, read "of Type 5" as an explicit `of type` with no type, and wrote "of Type 5" to Size. Step 1 now skips a caption whose remainder starts with `of type` but yields no type, so the longer caption reads it.

Added: 7 cases for the review's family (22 in the module in total). Gates: the 1009 / 1006 / 1003 / 1000 / 994 edit suites, `test_edit_drives_909`, `test_edit_family_{marks_678,mass_659,size_668}`, scaffolding, `test_convert`, `test_router`, `test_convert_combo` and `test_reduce`: **465 passed / 35 skipped**. The rename side was confirmed correct by the review. It also found that unquoted `rename type Run to Panel to X` (OLD captured as "Run") is now refused, where main substring-matched it and renamed "Run to Panel" to "Panel to X".

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_rename_exact_1009.py` (new);
  - `tests/ci_shard.d/1009-edit-rename-exact.txt` (new);
  - this fragment.
- Staged: nothing. Hard rule 4: no claim here rests on a desktop verdict.

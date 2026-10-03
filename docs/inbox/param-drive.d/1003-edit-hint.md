# #1003: the refusal hint keeps "of type T" as the type

Refs #1003, #1000, #1001.

## What was built
`_value_hint` (`src/rvt/convert/modify_family.py`) takes the first `of type T` qualifier out of the refused clause's tail (`_RE_OF_TYPE`, for bare, `"…"` and `'…'` forms) and puts it back in its parsed position before the `=`. The qualifier keeps the user's quoting. So `set Finish color of type T1 to black` now hints `set Finish of type T1 = color to black`, which re-parses as caption Finish, value "color to black", type T1. Before this change the hint folded the qualifier into the value, and the hinted clause re-parsed with no type. The hint is message text only, so nothing was ever written wrongly. The change is to the recovery the hint names.

## Evidence
- `tests/test_edit_hint_1003.py` (new, 4 cases): each hinted example re-parses through `_match_set` to the intended caption, value and type.
  - On base `5966d70`, 3 of the 4 fail: every case with a qualifier.
  - With the fix, all 4 pass.
- `test_edit_leftovers_994` + `test_edit_nits_1000` + `_1003`: 50 passed.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror (sync);
  - `tests/test_edit_hint_1003.py` (new);
  - `tests/ci_shard.d/1003-edit-hint.txt` (new);
  - this fragment.
- Staged: nothing. Hard rule 4: no claim here rests on a desktop verdict.

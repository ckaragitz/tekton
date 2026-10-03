# #1014: a colon after a caption is a delimiter; glued punctuation and mistyped long captions are refused

Refs #1014, #1011, #1013, #1008. S-2026-09-22-a. Measured by the reviews of PR #1013; all of it was on main too.

## What was built (`src/rvt/convert/modify_family.py`)
1. **A colon right after a caption reads like `=`.** In `_match_set_inner`'s caption list, a caption whose remainder starts with `:` gets `= `. `_RE_AFTER_NAME` also accepts `:` after a resolved type name. So `set Tray Type: 1`, `set Tray  Type: 1`, `set Tray Type:1` and `set Tray Type of type T1: 1` all store "1", not ": 1". A colon inside a value (`= 10:30`, `to a:b`) is kept.
2. **Punctuation glued to the longest caption is refused** (in `_refuse_glued_caption`): `set Mark^ 1`, `set Mark Note-1`, `set Mark-1`, `set Size of Type A- 1`. Before, they stored "^ 1" / "-1" / "- 1". The refusal does not apply when:
   - a longer caption is what was typed;
   - a shorter caption reads the clause with `to` / `=` (`set Distance to Wall-mounted box` stays Distance = "Wall-mounted box");
   - the character is `:`, `=`, a quote or whitespace.

   The message names no caption.
3. **`<caption> to <text> = v` is refused when a longer caption starts with `<caption> to`.** `set Distance to Walls = 5` (or `Wáll`) used to write Distance = "Walls = 5". It is now refused: "no parameter 'Distance to Walls'". `set Finish to a=b`, where no `Finish to …` caption exists, still stores "a=b".

## Evidence
- `tests/test_edit_colon_1014.py` (new, 18 cases: 11 reads, 6 refusals, and a read-back of `set Finish: hot dip` on a generated conduit). On main 92299eb, 11 of the 18 fail; with the fix, all 18 pass.
- The 17 edit / convert suites (the 16 of #1013 plus this module): **577 passed / 35 skipped**. The ADOPTERS row is added.
- The #1013 reviewers' instruments, rerun at this head:
  - **ASCII sweep (46,944 clauses):** against main, OK→OK 16,079; REFUSE→OK 2,456; WRONGVAL→OK **1,308**; WRONGCAP→OK 266; WRONGCAP→REFUSE 40; REFUSE→REFUSE 26,795. There is **no wrong value or wrong caption left**, and no OK→worse. Against #1013's head: REFUSE→OK 523 and WRONGVAL→OK 1,080; nothing else moved.
  - **`uni.py` / `uni2.py`:** 21 differences from #1013's head, all of them `Wall<letter>= red`-style writes into the shorter caption, now refused.
  - **`hunt.py`:** 275 differences from #1013's head, all writes of a value starting with stray punctuation (`´ red`, `^ 1`), now refused.

## Correction to the #1011 record
`1011-edit-caption-readings.md` reports 554 passed / 35 skipped for #1013's final head. The independent review measured **558 / 35** for those 16 suites at that head (a1fba67). The fragment shipped as it was; this is the correction.

## Still open
`param_by_caption`'s fuzzy substring match: `set NEMA Configurationé red` (NFD) writes NEMA Configuration = "Configurationé red". The JSON-op path relies on that fuzzy match too. Changing it needs its own decision and is not done here.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_colon_1014.py` (new);
  - `tests/ci_shard.d/1014-edit-colon.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).

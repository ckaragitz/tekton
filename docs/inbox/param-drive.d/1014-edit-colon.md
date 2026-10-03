# #1014: a colon after a caption is a delimiter; glued punctuation and mistyped long captions are refused

Refs #1014, #1011, #1013, #1008. S-2026-09-22-a. Measured by the reviews of PR #1013; all of it was on main too.

## What was built (`src/rvt/convert/modify_family.py`)
1. **A colon glued to a caption reads like `=`.** In `_match_set_inner`'s caption list, a caption immediately followed by `:` (no space) gets `= `. So `set Tray Type: 1`, `set Tray  Type: 1` and `set Tray Type:1` store "1", not ": 1". (A colon after a type name is not a delimiter; see the second review round.) A colon inside a value (`= 10:30`, `to a:b`) is kept.
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

## Review round (PR #1016, head 79af247, 🛑)
- **Blocking: a colon after a space was also read as a delimiter.** The caption list stripped whitespace before checking for `:`, and `_RE_AFTER_NAME` allowed `\s*:`. So `set Note :)` stored ")", and `set Ratio :1` / `set Width of type T1 :)` lost their colons: 119 OK→WRONGVAL in the review's 27,896-clause probe. Now only a colon **glued** to the caption or type name is a delimiter (`body[end] == ':'`, and `:\s*` in `_RE_AFTER_NAME`). After a space, the colon is part of the value, as on main.
- **The `<caption> to … = v` refusal matched without a word boundary.** Captions Distance / Distance tolerance refused `set Distance to a=b`. It now needs a caption starting with `<caption> to ` (whole words).

**Re-measured at this head:**
- The review's own probe (`adv9.py`, 27,896 clauses) against main: OK→OK 7,617; REFUSE→OK 485; WRONGVAL→OK 1,283; WRONGVAL→REFUSE 1 (`set Width, 3`, which stored ", 3"). There is **no OK→worse**. The remaining 1,263 WRONGVAL→WRONGVAL are quoted bare values (`set Note "hi"` keeps its quotes), which predate this PR.
- The ASCII sweep is unchanged: no wrong value or caption left.
- `test_edit_colon_1014` now has 24 cases; the 17 suites give **583 passed / 35 skipped**.

## Second review round (PR #1016, head a6656c9, 🛑)
Extending the colon rule to **type names** (`_RE_AFTER_NAME`) regressed:
- with types T1 / T1:B, `of type T1:C = 3` wrote T1 = "C = 3";
- `of type A:B = 3` (types A / A:B) was refused although main read it.

The type-name grammar goes **back to main's**: no colon delimiter after a type. `of type A:B = 3` reads type A:B again, and the mistyped forms are refused as before. On the caption side:
- **A glued colon with no value is always refused,** naming no caption. `set Note:` used to write a blank (and with captions Note and Note:, a blank into Note).
- **The colon form of a mistyped longer caption is refused.** `set Note: Installs = x`, with a caption "Note: Install", never becomes Note = "Installs = x".
- **Both checks stand down when a longer caption already matched** (`set Note: Install = x` reads that caption).

**At this head:**
- `test_edit_colon_1014` has **38 cases**, including families whose type names contain `:`.
- The 17 suites: **597 passed / 35 skipped**.
- The reviewer's `hunt10.py` / `hunt11.py`: every clause reads the named caption and type with the user's value, or is refused.

## Third review round (PR #1016, head 8934b78, 🛑)
The colon→`=` rewrite on a SHORTER caption ran even when a LONGER caption had matched first. Its `=` reading then won in the explicit-delimiter step: `set Note: A"x"` (captions Note / Note: A) wrote Note = `A"x"`, and `set Mark: Ref"x"` wrote into Mark. The review's prefix-colon probe found 93 such writes. Fixed:
- **The rewrite stands down when a longer caption already matched.**
- **A glued colon with no value is refused whichever caption matched** (`set Note:` with captions Note / Note: never writes ":").
- **A glued colon followed by another delimiter is refused** (`set Note to A: to x`, `:= x`).
- **The mistyped-longer-caption test is narrowed.** With a caption literally named "Note:", `set Note: Installs = x` names it exactly, as on main. The refusal is pinned on a family without one.

**At this head:**
- The reviewer's `hunt12.py` (6,501 clauses) against main had no write to a different caption, but its 516 writes → refusals included 136 well-formed clauses for a caption named `Note:` (corrected in the fourth round below).
- The ASCII sweep and `adv9.py` show no OK→worse.
- `test_edit_colon_1014` has 50 cases; the 17 suites give **609 passed / 35 skipped**.
- The pre-existing `;`-inside-quotes split is filed as #1017.

## Fourth review round (PR #1016, head b9c8b21, 🛑)
- **Blocking.** The new two-delimiter refusal ran even when a LONGER caption had matched. With a caption literally named "Note:", `set Note: = x` / `set Note: to x` were refused, where main and 8934b78 wrote Note: = "x" (136 OK→REFUSE in hunt12). It now sits under the same "no longer caption matched" guard as the colon rewrite. The no-value refusal stays unconditional.
- **Also fixed.** An `=` inside a quoted value no longer counts as a mistyped longer caption: `set Note to "A = 1"` stores `"A = 1"` even with a "Note to A" caption.
- **Re-measured.** hunt12 against main: no write to a different caption; 851 values change (all dropped glued colons); 18 refusals → reads.
  - Of the remaining writes → refusals, every one main wrote *cleanly* (`set <cap> to|= <value>`) is the intended mistyped-longer-caption refusal (`set Note to AB = 1` with a "Note to A" caption).
  - The cases in the first bullet read again.
- `test_edit_colon_1014` has 57 cases; the 17 suites give **616 passed / 35 skipped**.

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

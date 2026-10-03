# #1011: "of type" and caption readings never land in the wrong parameter

Refs #1011, #1009, #1010, #1007. S-2026-09-22-a. Found by the second review of PR #1010; all were on main too.

## What was built (`src/rvt/convert/modify_family.py`)
- **`_caption_of_type(inv, clause)`**, extracted from `_resolve_type_name`, decides whether a caption that contains "of type" (`Size of Type`) is the parameter. It returns where a qualifier may begin. When a SHORTER caption plus a type of the family also reads the words (`set Size of type Big One = 5`), that reading wins, as in #1010. It is **refused, naming both readings**, when:
  - the long caption is followed by `to` or `=`, or
  - both readings take a bare value (`set Size of Type A = 5` with captions Size / Size of Type A and type A; `set Size of Type Big Mac`).
- **`_match_set` refuses "of type" as a value.** With no type read, a value that starts with "of type" is refused: `set Size of Type` used to write "of Type" into **Size** (item 1).
- **A typed value ending in a type is refused.** A typed clause whose value ends in `of type <a type of this family>` (`_ends_in_type`) is refused (item 3). #1007's B2 only covered untyped clauses.
- **`_match_set_inner(prefer=...)`** drops shorter captions whose remainder starts with "of type" when a longer caption containing "of type" was named. `set Size of Type 5 mm` therefore parses as Size of Type = "5 mm" (item 4); before, it was refused because "5" was read as a type.

- **A clause that is exactly a multi-word caption with no value is refused** ("no value given for 'Distance to Wall'"). This holds with or without a trailing `to`/`=` or punctuation. With captions Distance / Distance to Wall, `set Distance to Wall to` used to write Distance = "Wall to", and `set Distance to Wall` wrote Distance = "Wall". The second review of PR #1012 found this; it is on main too. A family with only a "Distance" caption still reads `set Distance to Wall` as Distance = "Wall".

## Evidence
- `tests/test_edit_caption_readings_1011.py` (new, 21 cases):
  - 10 refusals, 3 of them the caption-only no-value forms;
  - 10 reads, including #1010's case unchanged;
  - an end-to-end case on a generated conduit carrying text parameters Size / Size of Type. `set Size of Type` is refused and neither value changes; `set Size of Type 5 mm` reads back "5 mm".
- On base (main + #1008, df299d7), 12 of the 21 fail; with the fix, all 21 pass.
- The 1011 / 1008 / 1009 / 1006 / 1003 / 1000 / 994 edit suites, `test_edit_drives_909`, scaffolding (an ADOPTERS row), `test_convert`, `test_router`, `test_convert_combo` and `test_reduce`: 392 passed / 35 skipped.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_caption_readings_1011.py` (new);
  - `tests/ci_shard.d/1011-edit-caption-readings.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. Hard rule 4: no claim here rests on a desktop verdict.

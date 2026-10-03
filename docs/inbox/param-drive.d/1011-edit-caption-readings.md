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

## Review round (PR #1013, head b5d04ec, 🛑)
The caption-only check had gaps, and each one still wrote the user's words into **Distance**. All were confirmed end to end, and all were on main too:
- extra whitespace (`set Distance to  Wall to`);
- a trailing `?` or `:`;
- above all, the long caption followed by a bare value (`set Distance to Wall 3 ft` → Distance = "Wall 3 ft").

The first round's "with or without a trailing to/= or punctuation" was overstated. Fixed:
- **Whitespace and punctuation.** Captions now match with any whitespace between their words, both in the grammar and in the caption-only check. The check also strips `?` and `:`. A value's own spacing is kept (`= two  spaces`).
- **The longest caption wins.** The longest caption the clause names, followed by a bare value, is the parameter (`set Distance to Wall 3 ft` → Distance to Wall = "3 ft"; `…: 3` → "3"). If that value itself holds `to`/`=` (`set Distance to Wall height to 3`), the shorter caption's reading is just as possible, so the clause is refused naming both. The rule stands down when the type resolver already decided a qualifier, which keeps #1010's `set Size of type Big One = 5`.
- **Clearer refusal.** An untyped value starting with "of type" now says to quote it (review nit).

**Real-family regression.**
- Families: the 7 archetypes (cable_tray, conduit, junction_box, lighting_control_panel, strut_channel, strut_trapeze, wireway).
- Clauses: every caption × type × five forms (`to 1`, `= x`, `of type T = 1`, `of type "T" to 1`, bare `1`), 600 in all.
- Result: **0 differences from main**, and 0 new refusals.
- The review's own sweep of about 7,000 clauses over 11 families found the only differences to be bare `set C` / `set C to`, now refused (improvements).

**Tests at that head:** 31 cases (main failed 21), and 510 passed / 35 skipped across the 16 suites. These numbers are superseded below.

## Second review round (PR #1013, head a174288, 🛑)
- **B1. A quoted type counted as "untyped".** `_resolve_type_name` returns `""` for a quoted qualifier, and `typed=bool(qual)` read that as untyped. So the longest-caption rule fired on `set Size of type "Big One" = 5`, either refusing it or writing `'"Big One" 5'` to Size of Type. That is exactly the form the two-readings refusal tells the user to write. Now `typed=qual is not None`, and `_caption_of_type` recognises a **quoted** type after the shorter caption as the qualifier.
- **B2. Exact-spacing caption comparisons.** The type resolver still compared captions with exact spacing. `set Distance to  Wall of type T 1 = 4` therefore skipped type resolution, and with types T / T 1 it wrote "1 = 4" to type **T**. A new `_canon_caption_span` rewrites the caption the clause starts with (the longest, whitespace-tolerant) to single spaces before anything else runs. The user's own words and casing are kept for messages, and the value is never touched.

## Third review round (PR #1013, head ad438e8, 🛑)
The longest-caption rule (from a174288) accepted a caption that ends inside a word. The grammar's boundary check `(?![A-Za-z0-9_])` lets `-`, `'`, `"`, `.`, `/`, `(` and `,` through. So `set Distance to Wall-mounted box` wrote "-mounted box" into **Distance to Wall**; main wrote "Wall-mounted box" into Distance, correctly. This was confirmed end to end. Now the rule applies only to a caption that ends where the user ended a word: whitespace, the end of the clause, `:` or `=`. Otherwise main's explicit-first ordering reads the clause. Added 9 such cases and an end-to-end read-back, for 47 cases in all.

The same review's 25,080-clause sweep over 15 families found otherwise only improvements against main, plus that one regression. Head vs a174288 showed only improvements. It also measured an older value defect: `set Tray Type: 1` stores ": 1". That is filed separately as #1014.

## Fourth review round (PR #1013, head 9d785e0, 🛑)
The caption-match boundary `(?![A-Za-z0-9_])` (from a174288) is ASCII-only, while main's `isalnum()` is not. A caption ending inside a word of non-ASCII letters or digits therefore still matched. The fallback loop then cut the word:
- `set Size of Type Aé` (captions Size of Type / Size of Type A) wrote Size of Type **A** = "é";
- `set Mark Noteé` wrote Mark Note = "é".

The review's unicode probe counted 1,456 refusals that turned into writes and 1,040 changed values. The boundary became `(?!\w)` in both places; the fifth round (below) found that this alone is not enough. Added 6 cases, for 53 in total.

The review's 46,944-clause, 21-family sweep at 9d785e0 (all ASCII) showed **no transition from OK to anything worse** against main. Its only remaining wrong values are #1014's ": v" prefix: 90 double-spaced `C  C: v` clauses now reach it, as noted on #1014. With the fix, the unicode probe matches main on 8,550 of 8,560 clauses, and the other 10 are improvements.

## Fifth review round (PR #1013, head 6360900, 🛑)
`(?!\\w)` was not the whole fix. The previous round called it "Unicode-aware", which overstated it. Combining marks (NFD input such as 'A' + U+0301), format characters (U+200D) and emoji are not `\\w`. A caption ending right before one was therefore still named, and the orphaned mark was written as the value: `set Size of Type Á 5` wrote "\u0301 5" to Size of Type **A**, where main refused.

Fixed in three steps:
- **One boundary rule (`_word_ends`).** A word continues through letters, digits, `_`, combining marks, format characters and symbols. It is used in all three boundary checks (`_canon_caption_span`, `_match_set_inner`, `_caption_of_type`).
- **Glued captions are refused (`_refuse_glued_caption`).** A clause in which any caption runs straight into such a character cannot be read safely, because every reading writes a cut or orphaned word. Letters (`Aé`) and punctuation (`Wall-mounted`) read as before.
- **The two-readings refusal now needs a real second reading.** A shorter caption must actually be followed by `to`/`=`. So `set Mark Note x to red` reads Mark Note = "x to red", as main does, and is no longer refused.

**Sweeps at this head, rerun with the reviewers' own scripts:**
- **ASCII (46,944 clauses, 21 families):** the transition table is identical to the fourth and fifth reviews', with **no OK → worse**.
- **First Unicode probe (8,560):** matches main except 10 improvements.
- **Mark/ZWJ/emoji/NBSP probe (11,984):**
  - 1,974 clauses main **wrote** with an orphaned mark or a cut word are now refused;
  - 18 NBSP-separated clauses now read the long caption (improvements);
  - no other differences.

## Sixth review round (PR #1013, head b41ab3f, 🛑)
- **B1. A longer caption read as a glued prefix.** `_refuse_glued_caption` refused a clause whenever a SHORTER caption ran into a symbol, even when the user had typed a longer caption in full. With captions Size / Size™ Code, `set Size™ Code = 5` was refused, and the hint said `set Size = <value>`, which points at a parameter the user did not name. Now:
  - the refusal fires only when no longer caption matches there and ends a word;
  - its message names no caption: "name the parameter in full … set <Parameter> = <value>".
- **B2. NFC/NFD.** A caption stored in one Unicode normalisation form was missed when the clause was typed in the other (present since a174288), and the value went to the shorter caption. Now:
  - `_caption_matches` matches every caption with any whitespace, case-insensitively and in either form, and maps the end back to the clause's own indices;
  - `_canon_caption_span` rewrites the span to the stored caption's text when only the form differs, so every later step sees the stored caption;
  - the glued check runs after that canonicalisation.

**This head.** The module has 69 cases (B1 ×7, B2 ×2 added). Main fails 34, b41ab3f fails 12, and this head passes all 69. The 16 suites give **554 passed / 35 skipped**. The reviewers' instruments, rerun:
- ASCII sweep: the transition table is identical to the fourth through sixth rounds' (no OK → worse);
- `uni.py` and `uni2.py`: identical to b41ab3f's results against main;
- the sixth reviewer's 1,094-clause hunt: its `over|` (B1) and `nf|` (B2) rows now read the named caption.

## Evidence
- `tests/test_edit_caption_readings_1011.py`: **69 cases**, covering refusals, reads, every review round's probes, and three end-to-end read-backs on generated conduits with colliding text parameters. Main fails 34; head b41ab3f fails 12; this head passes all 69.
- Real-family regression: 600 well-formed clauses (7 archetypes × every caption × type × five forms) give **0 differences from main**. The second review's own 5,861-clause, 21-family sweep found only improvements, apart from B1.
- The 16 suites: 1011 / 1008 / 1009 / 1006 / 1003 / 1000 / 994, `test_edit_drives_909`, `test_edit_family_{marks_678,mass_659,size_668}`, scaffolding (ADOPTERS row), `test_convert`, `test_router`, `test_convert_combo`, `test_reduce`. Result: **554 passed / 35 skipped** (at this head). The 600-clause real-family regression is re-run at this head, with 0 differences from main.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_caption_readings_1011.py` (new);
  - `tests/ci_shard.d/1011-edit-caption-readings.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. Hard rule 4: no claim here rests on a desktop verdict.

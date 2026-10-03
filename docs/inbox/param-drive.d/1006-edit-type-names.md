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

## Review round (PR #1007, 2026-10-03)
I re-probed the bare-value form while the independent review ran, and the same mis-target was still there. `set Finish of type Big Two black` (no `to`/`=`) took type "Big", which substring-matched 'Big One', and wrote "Two black" to it. `set Finish of type Conduit - Straight black` did the same. Without a delimiter, the name's end can't be told from the value's start. So in that form the first word must now be **exactly** one of the family's types (any case), and anything else is refused by name. `set Finish of type Big One black` and `set Width of type t1 3 ft` still work. There are 4 new cases; the six edit suites plus the scaffolding check give 136 passed / 8 skipped.

## Second review round (PR #1007 head 63d4cbc, 🛑): rewritten
The independent review found that the first `_quote_type_name` **added** mis-targeted writes:
1. **It stopped at a shorter type name.** The only check after the match was "the next character is not alphanumeric", so `of type Big One XLL to black` (types Big One / Big One XL) wrote "XLL to black" to 'Big One'. `Typ 1 0` did the same with 'Typ 1 '.
2. **It injected quotes into values.** It quoted an `of type` found anywhere, so `set Finish = x of type Big One to y` stored `x of type "Big One" to y`.
3. **`Big One=black` landed in the default type.** It rewrote this to `"Big One"=black`, which the grammar does not accept, and the clause fell through to the default type with a garbled value.
4. **The bare form still cut at the first word.**

The rewrite, `_quote_type_name` plus `_RE_AFTER_NAME` / `_refuse_type`:
- Only the `of type` that qualifies the **parameter** counts: before any `=` or quote, and before any `to` unless the words before it are exactly a caption ("Distance to Wall"). Text inside the value is never touched.
- A type name, matched longest first and case-insensitively, must be followed by the end, `to`, `=` (with or without spaces), or one space and a bare value. It is re-emitted in the grammar's quoted form, with single quotes for a name containing `"`.
- A name followed by more words and then a delimiter is not a match, and with nothing else fitting the clause is refused.
- In the bare form, the clause is refused when:
  - the next word could begin or extend the next word of a longer type of this family (`Big One X…` with 'Big One XL'), or
  - several bare value words start with a letter (`Default Extra black`; `= <value>` says it unambiguously, and `T1 3 ft` still parses).
- Unknown multi-word names, or names carrying `.`/`,`/`;`, are refused by name.

**Evidence.**
- `test_edit_type_names_1006` now has 41 cases, adding every probe from the review. Against them, `origin/main`'s parser fails 31, the previous PR head (edcead1) fails 13, and this head passes all 41.
- The reviewer's first probe script then reported every case as either the user's named type or a refusal; the third round below found the no-value forms it did not cover.
- The six edit suites plus the scaffolding check: 161 passed / 8 skipped.

## Third review round (head e7387ea, 🛑)
The review found the rewrite still wrote the user's text into the default type when **no value** followed the name. `set Finish of type Big One` (and `… then black`) stored Finish = `of type "Big One`, with a quote the user never typed. On a generated conduit this was stored end to end. Fixes:
- **No value.** A matched name with no value after it (end, a bare `to`, or `=`) is refused: "no value given for type …". So is an unknown single word with no value, and a quoted name with no value.
- **Value ending in a type.** A value that **ends** in `of type <a type of this family>` (`set Finish to black of type Big One`) is refused, with how to set that type or keep the words as text. Main and the previous head wrote it to the default type.
- **Two valid readings.** When a shorter type of the family also gives a valid `to`/`=` reading (`of type X to Y to z`, types X / 'X to Y'), the clause is refused rather than one reading picked.
- **Backstop.** `_match_set` now runs through `_resolve_type_name`, which reports whether the clause carried an unquoted or quoted `of type` qualifying its parameter. If it did and the grammar did not read a type (or read a different one), the clause is refused. It can never fall through to the default type.

**Evidence.** `test_edit_type_names_1006` now has 52 cases. Against the version before the last change, `origin/main` failed 39 of 51, the previous head (e7387ea) failed 8 of 51, and this head passed 51 of 51. The reviewer's 88 case lines (their `p2.py` with c2/c3) show every non-refused clause going to the named type. The only default-type writes left are untyped clauses (`set Length to 20 ft`, `set Finish = galvanized to spec`, …) and two older value defects, now filed as #1008: uneven quote stripping, and `set Finish to` storing "to". The six edit suites plus the scaffolding check: 171 passed / 8 skipped.

**Correction to the first round's text.** A single-word name before the delimiter is not always refused when it matches no type: `_op_set` falls back to a unique substring match. In a one-type family `of type Big to black` targets 'Big One' (accepted below).

**Accepted as they are (same as main).**
- In a one-type family, a single-word partial name (`of type Big to black`) resolves to that one type by substring. The target is unambiguous.
- A doubled space inside a name is refused rather than normalised.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_type_names_1006.py` (new);
  - `tests/ci_shard.d/1006-edit-type-names.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. No claim here rests on a desktop verdict (hard rule 4).

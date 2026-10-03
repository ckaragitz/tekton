# #1017 — a quoted value keeps its `;` / `,` / `then` / newline

## What was built
- `parse_family_edit` used to split edit text on `;`, newlines, `then` and `, set|rename` without looking at quotes. `set Note = "a; b"` became Note = `"a` plus an unparsed `b"`.
- New `_split_clauses` (`src/rvt/convert/modify_family.py`) skips a separator inside a quoted span. A span is a `"…"` or `'…'` pair that:
  - opens at a word start (after start of text, whitespace or one of `= : , ; (`);
  - closes at a word end (before end of text, whitespace or one of `. ; , ! ? )`).
- A quote with no such close is literal, so these split exactly as before:
  - `set Mark = Bob's; set Note = Ann's` (apostrophes);
  - `set Note = "a; b` (unbalanced quote);
  - `set Note = 5"; …` (inch mark).

## Evidence
- `tests/test_edit_quoted_split_1017.py`, 13 cases: 12 split cases plus a read-back on a generated conduit, where `set Finish = "hot dip; galv, set Mark"` stores the text whole.
- The 17 edit/convert suites of #1014 plus this module: **637 passed / 28 skipped**.
- `tools/sync_plugin.py --check` is clean.

## Open
`src/rvt/frontdoor/edit.py:292` (the `.rvt` edit lane) splits clauses the same quote-blind way. It is outside this issue's territory and left for its own issue.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_quoted_split_1017.py` (new);
  - `tests/ci_shard.d/1017-edit-quoted-split.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).

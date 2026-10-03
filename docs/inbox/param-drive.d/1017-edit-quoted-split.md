# #1017 — a quoted value keeps its `;` / `,` / `then` / newline

## What was built
- `parse_family_edit` used to split edit text on `;`, newlines, `then` and `, set|rename` without looking at quotes. `set Note = "a; b"` became Note = `"a` plus an unparsed `b"`.
- New `_split_clauses` (`src/rvt/convert/modify_family.py`) skips a separator inside a quoted span. A span is a `"…"` or `'…'` pair whose opening quote:
  - comes at a word start (after start of text, whitespace or one of `= : , ; (`);
  - is followed by something other than a space, `;` or `,`;
  - has its NEXT copy of the same quote closing at a word end (before end of text, whitespace or one of `. ; , ! ? )`), not right after a digit (a unit mark: `3'`, `5"`) or a space.
- Any other quote is literal and splits exactly as on main:
  - apostrophes (`Bob's`, `'90s`);
  - feet/inch marks;
  - a glued `"A"B`;
  - an unbalanced quote.
- A quoted span that runs across what reads as a further `set` / `rename` clause is **refused**. `set Note = 'heavy; set Mark = workers'` has the same shape as a stray apostrophe pairing with the next edit's possessive, and a refusal is recoverable where a swallowed edit is not.

## Evidence
- `tests/test_edit_quoted_split_1017.py`, 26 cases:
  - 20 split cases;
  - 4 refusals;
  - a read-back on a generated conduit, where `set Finish = "hot dip; galv then coat"` stores the text whole;
  - a parse on the conduit, where `'90s style; set Length = 3'` keeps both edits.
- The 17 edit/convert suites of #1014 plus this module: **650 passed / 28 skipped**.
- `tools/sync_plugin.py --check` is clean.

## Review round 1 (PR #1018, head 3b56703, 🛑)
- **Blocking.** The close search ran past other quotes and across separators. So a stray quote paired with a LATER clause's quote and swallowed that clause silently, for example Finish = `'90s style; set Length = 3'` with the Length edit lost. This contradicted DONE bullet 2.
- **Fixed by the rules above:**
  - only the next copy of the quote can close;
  - no unit-mark or space-preceded close;
  - no opening onto a space or separator;
  - a refusal for a span over a further `set`/`rename`.
- **DONE amended.** `set Note = 'x, set Width = 2'` now splits as on main, because `2'` reads as feet. That text cannot be told from the review's `'90s style, set Length = 3'`. The issue records the amendment.
- **Re-measured with the reviewer's differential** (`r14/diff.py`, 13,176 texts, main against this tree):
  - 3,852 + 120 + 18 texts keep their op count, with the quoted value now whole;
  - 70 that main wrote are now refused (a leading `'90s` / `'tis` / `'heavy` closed by the next edit's `workers'` / `dogs'`, or an unbalanced `"a; b` closed by `a; b"`);
  - 0 texts lose a clause silently.

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

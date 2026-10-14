# #1025 — a caption word glued to digits names its parameter inside quotes; the NOT-applied status is pinned

## What was built
- **Letter → digit split.** `_split_camel` (`src/rvt/convert/modify_family.py`) now also splits a letter from the digits after it: "AT1" → "AT 1", "Rating IN1" → "Rating IN 1".
- **Numbers are not words in `_leads`.** Pure-digit words are skipped when it checks the first and last word of a caption, so `IN` still ends "Rating IN1".
- **The bug this closes.** With a caption `AT1` or `IN1`, `set Mark = 'see note; set AT 5 A'` used to store the whole quoted value as text, although `set AT 5 A` unquoted applies `AT1`. It is now refused as a further edit, as it is on main for every other caption form. This was the #1024 final review's optional nit 2.
- **The boundary that stays, now named.** An all-caps caption glued to a word (`ONDELAY`, `RATINGAT`) cannot be told from a word that merely starts or ends with a function word (`NOMINAL` holds `NO`) without a dictionary. Inside quotes, `set ON …` stays text there. The same holds for:
  - lowercase glued pieces (`Ratingat`, `Offat`, `Größeat`);
  - digit-then-lowercase (`1at`);
  - inner words in any separator form (`Rating/AT/Value`, `of a` in "Number of a Kind").

  When the old quote-blind split wrote any of these, it wrote to the wrong parameter.
- **Pinned by tests.** These were the #1024 final review's optional nit 4:
  - the family-edit route status suffix `N clause(s) NOT applied (see caveats)` (`frontdoor/router._r_rfa_modify`);
  - the `(+N more in route.json / ROUTE.md)` line of `tools/route.py`'s text output.

## Evidence
- `tests/test_edit_digit_glued_1025.py`, 18 cases:
  - 7 `_split_camel` forms;
  - 4 digit-glued captions refused in quotes and applied unquoted;
  - the all-caps boundary;
  - prose staying text;
  - the "+N more" line with 11 caveats and with 8;
  - the route status on a generated conduit: 4 clauses not applied, the family still delivered, and no suffix when everything reads.
- An ADOPTERS row and a shard drop-in are added.
- **Suites:** `tests/test_edit_*.py`, `test_rvt_edit_quoted_split_1019`, `test_modify_family*`, `test_conftest_scaffolding`, `test_convert`, `test_router`, `test_convert_combo`, `test_reduce`, `test_frontdoor`, `test_frontdoor_json_strict`, `test_one_job_module`, `test_release_ctx_refusal`, `test_stagelog`, `test_plugin_sync` and `test_route*` give **977 passed / 41 skipped** with `RVT_SKIP_LARGE=1`. `tools/sync_plugin.py --check` is clean.
- **Against main 3e8634b, with the #1024 reviewers' instruments:**
  - **Extended enumerator** (`r26/probe/en2.py`, 65,143 old-applied cases): the `dig_suf`, `dig_suf_word` and `dig_last` residues each drop from 1,395 to 0. Everything left is the boundary above.
  - **Position enumerator** (`r25/probe/en.py`) and the prose grid (`r20/fp.py`, 140 fragments × 21 real families): unchanged. None of the real families has a digit caption.
  - **Fuzz, seed 9901:** `r15/fuzz.py` (40,000 texts), `r23/fuzzA.py` (20,000) and the real conduit (`r18/real/fz.py`, 20,000) are all identical to main.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_digit_glued_1025.py` (new);
  - `tests/ci_shard.d/1025-edit-digit-glued.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).

# #1025 — a caption word glued to digits names its parameter inside quotes; the NOT-applied status is pinned

## What was built
- **Letter → digit split.** `_split_camel` (`src/rvt/convert/modify_family.py`) now also splits a letter from the digits after it: "AT1" → "AT 1", "Rating IN1" → "Rating IN 1".
- **Numbers are not words in `_leads`.** Pure-digit words are skipped when it checks the first and last word of a caption, so `IN` still ends "Rating IN1".
- **The bug this closes.** With a caption `AT1` or `IN1`, `set Mark = 'see note; set AT 5 A'` used to store the whole quoted value as text, although `set AT 5 A` unquoted applies `AT1`. It is now refused as a further edit, as it is on main for every other caption form. This was the #1024 final review's optional nit 2.
- **Captions are read two ways.** `_caption_readings` gives `_leads` and `_near_caption` both the split reading (numbers dropped: "Rating IN1" → rating, in) and the caption as written ("L1 Current" → l1, current). So a digit-bearing key that several captions share (`L1`, `A1`, `CB1`, `Lamp1`, `Pipe2`) is still a further edit inside quotes, as it is on main. The first head of this PR stored those as text (review round 1 below).
- **The boundary that stays, now named.** These cases stay text by design:
  - an all-caps caption glued to a word (`ONDELAY`, `RATINGAT`);
  - lowercase glued pieces (`Ratingat`, `Offat`, `Größeat`);
  - digit-then-lowercase (`1at`);
  - inner words in any separator form (`Rating/AT/Value`, `of a` in "Number of a Kind").

  Why each class stays text:
  - **Inner words** (`AT` in `Rating/AT/Value`, `of` in "Number of Lamps") stay text under the #1024 rule that only a caption's **first or last** word names it.
  - **Glued pieces** (lowercase `Ratingat`, all-caps `ONDELAY`, digit-then-lowercase `1at`) cannot be told from a function word inside another word without a dictionary.

  The old quote-blind split resolved all of these by substring: **sometimes to the meant parameter** (`ON` → ONDELAY, `AT` → RATINGAT, `AT` → Rating/AT/Value, `at` → Ratingat), sometimes not (`NO` → NOMINAL, `at` → Material). Main stores the same cases as text, so nothing here regresses. Only the **all-caps** meant-parameter cases (ONDELAY, RATINGAT) are filed, as #1077. The inner-word and lowercase-glued meant cases stay text by design under the rules above.
- **The trade-off this PR accepts.** Value prose inside a quoted value is now refused when its leading word names a digit caption. That happens in three ways:
  - **Starts or ends a digit caption:** `'PVC; set in concrete'` with `IN1`, `"x; set a sleeve"` with `A1`, `'x; set at noon'` with `Breaker AT1`.
  - **Ends a spaced digit caption:** `Rating IN 1` and `Phase A 1`. Main stored these as text. They are newly refused because `_leads` skips pure-digit words.
  - **Is the stem of a digit-glued token several captions share:** `'see detail; set pipe in sleeve'` with "Upstream Pipe2 Diameter" and "Downstream Pipe2 Diameter", through `_near_caption`'s union of the two readings. Old refused that one too ("no parameter 'pipe'").

  The refusal is recoverable: close the quote before the separator, or use a JSON op. It is measured with a scratch probe (not committed): 101 value-prose fragments (function-word-led and a few stems) × 20 digit-caption families × 2 separators × 2 quote styles = **8,080 texts**. Head newly refuses **224** and newly accepts **0**:

  | Class | Newly refused |
  |---|---|
  | Word starts the caption | 96 |
  | Word ends the caption | 72 |
  | Spaced end-forms | 48 |
  | Shared stems | 8 |

  On the 140 × 21 real-family prose grid the trade-off is 0, because no real family has a digit caption. An earlier version of this bullet cited "211 of 14,858" from a probe lost with the session's machine; its listed breakdown summed to 141 and said "start" where four captions end with the word. That figure is superseded by the measurement above (PR #1074 review round 2).
- **Pinned by tests.** These were the #1024 final review's optional nit 4:
  - the family-edit route status suffix `N clause(s) NOT applied (see caveats)` (`frontdoor/router._r_rfa_modify`);
  - the `(+N more in route.json / ROUTE.md)` line of `tools/route.py`'s text output.

## Evidence
- `tests/test_edit_digit_glued_1025.py`, 22 tests:
  - 7 `_split_camel` forms;
  - 4 digit-glued captions refused in quotes and applied unquoted;
  - the all-caps boundary;
  - prose staying text;
  - the "+N more" line with 11 caveats and with 8;
  - the route status on a generated conduit: 4 clauses not applied, the family still delivered, and no suffix when everything reads;
  - 5 shared digit-bearing keys refused in quotes (review round 1);
  - the pinned trade-off: `IN1` + `'PVC; set in concrete'` is refused.
- An ADOPTERS row and a shard drop-in are added.
- **Suites:** `tests/test_edit_*.py`, `test_rvt_edit_quoted_split_1019`, `test_modify_family*`, `test_conftest_scaffolding`, `test_convert`, `test_router`, `test_convert_combo`, `test_reduce`, `test_frontdoor`, `test_frontdoor_json_strict`, `test_one_job_module`, `test_release_ctx_refusal`, `test_stagelog`, `test_plugin_sync` and `test_route*` give **984 passed / 41 skipped** with `RVT_SKIP_LARGE=1` (977 / 41 at the first head, 983 / 41 at round 1). `tools/sync_plugin.py --check` is clean.
- **Against main 3e8634b, with the #1024 reviewers' instruments:**
  - **Extended enumerator** (`r26/probe/en2.py`, 65,143 old-applied cases): the `dig_suf`, `dig_suf_word` and `dig_last` residues each drop from 1,395 to 0. Everything left is the boundary above.
  - **Position enumerator** (`r25/probe/en.py`) and the prose grid (`r20/fp.py`, 140 fragments × 21 real families): unchanged. None of the real families has a digit caption.
  - **Fuzz, seed 9901:** `r15/fuzz.py` (40,000 texts), `r23/fuzzA.py` (20,000) and the real conduit (`r18/real/fz.py`, 20,000) are all identical to main. None of these fuzzers carries a digit caption, so this holds by construction and is evidence only that nothing else changed. The digit differential is the en2 shapes above and the review's enumerators below.

## Review round 1 (PR #1074, head 480bbbf, 🛑)
- **Blocking.** The record said that whenever the old split wrote an all-caps glued or similar boundary case, "it wrote to the wrong parameter". That is false for ONDELAY and RATINGAT, where old wrote the meant parameter. It is corrected above, and the residue is filed as #1077.
- **Fixed in the same push (the review's optional nit 2).** The letter → digit split had dropped the as-written token, so `L1` / `A1` / `CB1` / `Lamp1` / `Pipe2` shared by several captions were stored as text where old and main refused. `_caption_readings` restores the as-written reading.
  - The review's `dkey.py` enumerator: 1,548 of 5,472 cases were newly accepted at head 480bbbf; now **0**, and this tree equals main on all 5,472.
  - The glued-token enumerator `tok.py`: 468 of 468 equal main (224 at 480bbbf).
  - The en2 residues are unchanged from 480bbbf: the `dig_*` suffix rows stay at 0.
- **Also carried:** the trade-off sentence with its measured size (nit 3), and the evidence wording on test counts and fuzz coverage (nit 4).

## Review round 2 (PR #1074, head 804b198, 🛑, wording only)
- **Blocking 1.** The trade-off bullet's numbers did not add up (141 listed against a stated 211), it said "start" where captions end with the word, and it left out the newly refused spaced end-forms. Rewritten above from a re-run probe: 8,080 texts, 224 newly refused, 0 newly accepted, broken down by class.
- **Blocking 2.** "The meant-parameter cases are filed as #1077" claimed tracking that #1077 (all-caps only) does not give. It now names only the all-caps cases for #1077 and gives each class its own reason (nit 4).
- **Nit 3.** The shared inner digit stem (`pipe` with "…Pipe2…" captions) is named in the trade-off.
- **Nit 5.** A test pins the split-reading half of `_near_caption`'s union: "Upstream/Downstream Pipe2 Diameter" with `'x; set Pipe 4 in'` refuses. It kills the mutant that restores main's as-written-only reading.
- The review measured no edit swallowed against main across 688,471 enumerated texts. Unquoted outcomes are identical on old, main and head.

## BRANCH STATE
- Files:
  - `src/rvt/convert/modify_family.py` and its `plugin/lib` mirror;
  - `tests/test_edit_digit_glued_1025.py` (new);
  - `tests/ci_shard.d/1025-edit-digit-glued.txt` (new);
  - `tests/test_conftest_scaffolding.py` (an ADOPTERS row);
  - this fragment.
- Staged: nothing. No desktop verdict is claimed (hard rule 4).

# #855: a comma between one item's ratings does not cut its count off

Stream: prompt-grammar. Issue: #855. Found by the independent review of #848,
round 3.

## What was wrong

The equipment clause closes its window at every `,` / `;`. Spec phrasing puts
commas between the ratings of *one* item, so the count before the first comma
was outside the window and the plural took its default of 2.

| prompt | `main` (`c06f845`) | this PR |
|---|---|---|
| `four 225A, MCB panels` | 2 | 4 |
| `three 75 kVA, dry-type transformers` | 2 | 3 |
| `six 225A, 3-phase, 4-wire panels` | 2 | 6 |
| `four 3-phase, 4-wire panels` | 2 | 4 |
| `three 480V, 3-phase transformers` | 2 | 3 |
| `four 75 kVA, 3-phase, 4-wire transformers` | 2 | 4 |
| `three 4-wire, 3-phase panels` | 2 | 3 |

Before #848, some of these came out right only by luck: the `4` of `4-wire`
was taken as the count.

## Fix

`over_rating_commas` in `parse_prompt` (`src/rvt/frontdoor/prompt_intent.py`).
After `clause_window`, it moves the clause start back across a `,` / `;` only
when both of these hold:
- **no count follows the comma** (checked after ratings are stripped);
- **the text before it**, back to the previous boundary, is a count and ratings
  alone (`_strip_ratings` + `_only_ratings`, the same readers the maker gap
  uses).

It repeats over several commas. A comma that starts a new item still splits:
- `a 225A panel, two transformers` → 1 + 2;
- `two 225A panels, a 75 kVA transformer` → 2 panels at 225 A and 1 transformer
  at 75 kVA, with no rating crossing over.

Ratings before the comma now reach the item (`four 225A, MCB panels` → 225 A MCB).

## Evidence

- New `tests/test_prompt_rating_commas_855.py`: **17 passed**. With the fix
  stashed: **8 failed / 9 passed** (the 9 are the must-still-split guards).
- `pytest tests/test_prompt_rating_commas_855.py tests/test_prompt_phase_count_845.py
  tests/test_prompt_intent.py tests/test_prompt_intent_775.py tests/test_frontdoor.py
  tests/test_router.py` gives **304 passed, 19 skipped, 0 failed**
  (`RVT_SKIP_LARGE=1`, no samples; the skip count depends on the environment).
- `tools/prompt_battery.py --rows`: **99/100**. The same single pre-existing
  `Lighting control / relay panel` row fails as on `main`.
- `tools/sync_plugin.py --check` clean; `validate_plugin.py` PASS;
  `check_portable_paths.py` ok; `test_plugin_sync.py test_bootstrap.py
  test_coldstart.py test_surface_perf.py` gives 40 passed.

## BRANCH STATE

- Branch: `claude/eager-franklin-xgzgda`, restarted from `main` @ `c06f845` after #848
  merged.
- Files written:
  - `src/rvt/frontdoor/prompt_intent.py` (+ its mirror `plugin/lib/src/rvt/frontdoor/prompt_intent.py`)
  - `tests/test_prompt_rating_commas_855.py`
  - `tests/ci_shard.d/855-prompt-rating-commas.txt`
  - this record
- Shipped: `over_rating_commas`.
- Staged, not shipped: nothing.

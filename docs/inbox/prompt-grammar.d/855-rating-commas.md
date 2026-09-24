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

`over_rating_commas` in `parse_prompt` (`src/rvt/frontdoor/prompt_intent.py`),
called right after `clause_window`. It walks the clause start back across `,` / `;`
and **keeps the move only when the chain has the shape count → ratings → noun**.
For every comma it crosses:
- no count follows it;
- no other equipment noun lies between it and this noun;
- the segment before it, once ratings are stripped, holds no tag token (`LP-1`)
  and nothing but a count or ratings.

The walk stops at the first segment that holds a count. If it never reaches one,
the **original** start is kept.

**Review round 1 (🛑) found that the first version leaked ratings.** It accepted
any ratings-only chain, so one item's *trailing* ratings reached the next item:
- `panel LP-1, 225A, MCB, panel LP-2, 100A, MLO`: LP-2 got 225 A MCB;
- `a transformer, 75 kVA, panels`: the panels got 75 kVA.

The count requirement, the tag check and the noun check are that fix. 11 pins cover
the leak directions (tagged items, a semicolon, spaces/mounting, and ratings crossing
between kinds). All 11 fail on the first version and pass on `main` and here.

What still holds:
- a comma that starts a new item splits (`a 225A panel, two transformers` → 1 + 2);
- ratings before the comma reach their own item (`four 225A, MCB panels` → 4 × 225 A MCB;
  `three 400A, 65 kA, switchboards` → 3 × 400 A / 65 kA).

## Evidence

- `tests/test_prompt_rating_commas_855.py` (28 tests):
  - this head: **28 passed**;
  - `main`'s source (`c06f845`): **8 failed**, all count pins; the 11 leak pins pass;
  - the first version (`17ba882`): **11 failed**, all leak pins.
- `pytest tests/test_prompt_rating_commas_855.py tests/test_prompt_phase_count_845.py
  tests/test_prompt_intent.py tests/test_prompt_intent_775.py tests/test_frontdoor.py
  tests/test_router.py` gives **315 passed, 19 skipped, 0 failed**
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
- Shipped: `over_rating_commas` (round 1: count-terminated chains only; no tag; no other noun).
- Found, not widened: `four 225A MCB panels named LP` builds 8 on `main` (`named LP` is also
  read as a lighting-panelboard noun). Filed as #857.
- Staged, not shipped: nothing.

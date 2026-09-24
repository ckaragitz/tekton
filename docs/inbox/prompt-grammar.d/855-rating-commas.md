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

**Review round 2 (🟡) raised two edge cases, both fixed:**
- The count that ends the chain is **one** count token, so a run of numbers is not a
  count: `26 24 16, 225A, MCB panelboards` stays at the plural default, where the
  round-1 code read 16. A lone number still counts (`four, 225A, panels` → 4). The
  no-comma form, `26 24 16 225A MCB panelboards`, already gives 16 on `main`; it is
  filed as #858.
- A **plural** noun takes a number, never `a` / `an` / `single`. So
  `a transformer, a 75 kVA, panels` keeps the 75 kVA on the transformer, and gives
  2 panels with no kVA. A singular noun still counts `a`: `a 225A, MCB panel` → 1 at
  225 A MCB. On `main` that panel lost its 225 A.

**Visible change (consistent with the no-comma form):** an explicit count wins over
named tags, so `four 225A, MCB panels LP-1 and LP-2` now gives 4 items (LP-1, LP-2,
PP-3, PP-4, all 225 A MCB). `main` gave 2 because it never saw the count.

What still holds:
- a comma that starts a new item splits (`a 225A panel, two transformers` → 1 + 2);
- ratings before the comma reach their own item (`four 225A, MCB panels` → 4 × 225 A MCB;
  `three 400A, 65 kA, switchboards` → 3 × 400 A / 65 kA).

## Evidence

- `tests/test_prompt_rating_commas_855.py` (32 tests):
  - this head: **32 passed**;
  - `main`'s source (`c06f845`): **9 failed**, the 8 count pins plus `a 225A, MCB panel`
    losing its rating; the leak pins pass;
  - the first version (`17ba882`): **11 failed**, all leak pins;
  - round 1 (`7a627d6`): **3 failed**, the round-2 pins.
- `pytest tests/test_prompt_rating_commas_855.py tests/test_prompt_phase_count_845.py
  tests/test_prompt_intent.py tests/test_prompt_intent_775.py tests/test_frontdoor.py
  tests/test_router.py` gives **319 passed, 19 skipped, 0 failed**
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
- Shipped: `over_rating_commas`:
  - round 1: count-terminated chains only, with no tag and no other noun on the way;
  - round 2: one count token ends the chain, and a plural takes a number, not an article.
- Found, not widened: `four 225A MCB panels named LP` builds 8 on `main` (`named LP` is also
  read as a lighting-panelboard noun). Filed as #857.
- Found, not widened: `26 24 16 225A MCB panelboards` builds 16 on `main`. Filed as #858.
- Staged, not shipped: nothing.

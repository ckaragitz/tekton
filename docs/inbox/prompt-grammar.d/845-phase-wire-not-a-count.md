# #845: a phase / wire / pole designator is never an equipment count

Stream: prompt-grammar. Issue: #845. Found while generating the owner's test
panelboard (steer #847 session).

## What was wrong

| prompt | `main` | this PR |
|---|---|---|
| `a 208/120V 3-phase panelboard` | 3 panelboards | 1 |
| `a 208/120V 4-wire panelboard` | 4 | 1 |
| `a 208/120V 3-phase 4-wire panelboard` | 4 | 1 |
| `a three phase four wire 480Y/277V panelboard` | 4 | 1 |
| `a 75 kVA 3-phase transformer` | 3 transformers | 1 |
| `two 3-phase panels` | 3 | 2 |
| `2 208Y/120V 3-phase 4-wire panels` | 4 | 2 |
| `three single-phase transformers` | 1 | 3 |

The equipment clause looks for a count in the words before the noun. It
scrubs rating expressions from those words first (amps, kVA, kA, spaces,
sections, voltages, storeys, level refs), but it did not scrub phase / wire /
pole designators. So the nearest digit or number word won as the count.

## Fix

A new `_RE_PHASE_WIRE` in `src/rvt/frontdoor/prompt_intent.py`, added to the
count scrub (`head_count`) only. It covers:
- `3-phase`, `three phase`, `single-phase`
- `3PH`, `3Ø`, `3φ`
- `4-wire`, `four wire`, `4W`
- `3-pole`, `3P`

Attribute extraction (`window`) is unchanged.

Guards, each added after an independent review round on the PR:
- **Round 1:** a designator word that opens a hyphen compound is not a
  designator (`three pole-mounted`, `four wire-guarded`,
  `three phase-converter`). A chained designator is still one
  (`three-phase-four-wire`, `3-phase-4-wire`).
- **Round 2:** only `pole` refuses a following `mount…` / `top…`
  (`three pole mounted`, `pole top`). After `phase` / `wire`, `top-feed` /
  `top fed` is a panel attribute, so `a 3-phase top-feed panelboard` is one panel.

**Decision (pinned):** before an uncounted plural, the designator reading wins
(`three phase transformers`, `four wire panels`), following trade usage. The
plural then takes its stated default of 2, and `coverage.defaults_applied`
says so ("plural with no count: assumed 2"). `main` read those as counts.

## Evidence (final head)

- `tests/test_prompt_phase_count_845.py` (33 tests), run against each version:
  - this head: **33 passed**;
  - `main`'s source: **17 failed / 16 passed**;
  - round 0 (`cfa5c3f`): **7 failed**;
  - round 1 (`b2e7be7`): **4 failed**.
- `pytest tests/test_prompt_phase_count_845.py tests/test_prompt_intent.py
  tests/test_prompt_intent_775.py tests/test_frontdoor.py tests/test_router.py`
  gives **287 passed, 19 skipped, 0 failed** (`RVT_SKIP_LARGE=1`, no samples).
- `tools/prompt_battery.py --rows` (round 0): **99/100 both before and after**. The
  one row is the same pre-existing `Lighting control / relay panel` refusal.
- `tools/sync_plugin.py --check` clean; `validate_plugin.py` PASS;
  `check_portable_paths.py` ok; `tests/test_plugin_sync.py` 9 passed;
  `test_bootstrap.py test_coldstart.py test_surface_perf.py` 31 passed.

## Findings

- A `single-phase 120/240V panelboard` emits `Phases 3, Wires 4`, because the
  contract hard-codes them. Filed as #846.
- `3 pole-mounted transformers` builds 2 on `main`, because `_RE_SPACES` reads
  "3 pole" as spaces. Filed as #854. The spelled-out form is correct here.
- Coverage nit (same as `main`, no effect on counts): the count-word mark loop
  runs over `head`, not `head_count`, so `three three-phase panelboards`
  reports only `-phase` as ignored.

## BRANCH STATE

- Branch: `claude/eager-franklin-xgzgda`, from `main` @ `06b4cc3`.
- Files written:
  - `src/rvt/frontdoor/prompt_intent.py` (+ its mirror `plugin/lib/src/rvt/frontdoor/prompt_intent.py`)
  - `tests/test_prompt_phase_count_845.py`
  - `tests/ci_shard.d/845-prompt-phase-count.txt`
  - this record
- Shipped: the count scrub with its round-1 and round-2 guards.
- Staged, not shipped: nothing.

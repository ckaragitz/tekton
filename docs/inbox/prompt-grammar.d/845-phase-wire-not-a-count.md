# #845: a phase / wire / pole designator is never an equipment count

Stream: prompt-grammar. Issue: #845. Found while generating the owner's test
panelboard (steer #847 session).

## What was wrong

| prompt | before | after |
|---|---|---|
| `a 208/120V 3-phase panelboard` | 3 panelboards | 1 |
| `a 208/120V 4-wire panelboard` | 4 | 1 |
| `a 208/120V 3-phase 4-wire panelboard` | 4 | 1 |
| `a three phase four wire 480Y/277V panelboard` | 4 | 1 |
| `a 75 kVA 3-phase transformer` | 3 transformers | 1 |
| `two 3-phase panels` | 3 | 2 |
| `2 208Y/120V 3-phase 4-wire panels` | 4 | 2 |

The equipment clause looks for a count in the words before the noun. It
scrubs rating expressions from those words first (amps, kVA, kA, spaces,
sections, voltages, storeys, level refs), but it did not scrub phase / wire /
pole designators. So the nearest digit, the `3` of `3-phase` or the `4` of
`4-wire`, won as the count. An explicit count *before* the designator also
lost to it, which is why `two 3-phase panels` came out as 3.

## Fix

A new `_RE_PHASE_WIRE` in `src/rvt/frontdoor/prompt_intent.py`, added to the
count scrub only. It covers:
- `3-phase`, `three phase`, `single-phase`
- `3PH`, `3Ø`, `3φ`
- `4-wire`, `four wire`, `4W`
- `3-pole`, `3P`

Attribute extraction is unchanged.

## Evidence

- New `tests/test_prompt_phase_count_845.py`: **17 passed** with the fix,
  **8 failed / 9 passed** with the fix stashed. So the 8 pins earn their
  names, and the 9 are guards.
- `pytest tests/test_prompt_intent.py tests/test_prompt_intent_775.py
  tests/test_prompt_phase_count_845.py tests/test_frontdoor.py tests/test_router.py`
  gives **271 passed, 19 skipped, 0 failed** (`RVT_SKIP_LARGE=1`, no samples).
- `tools/prompt_battery.py --rows`: **99/100 both before and after**. The one
  row is the same pre-existing `Lighting control / relay panel` refusal,
  unrelated to this change.
- `tools/sync_plugin.py --check` clean; `validate_plugin.py` PASS;
  `check_portable_paths.py` ok; `tests/test_plugin_sync.py` 9 passed.

## Findings

- Phases and Wires are hard-coded to 3 and 4 for every prompted panelboard.
  A `single-phase 120/240V panelboard` emits `Phases 3, Wires 4`. Filed
  as #846; it is not widened into this PR.

## BRANCH STATE

- Branch: `claude/eager-franklin-xgzgda`, from `main` @ `06b4cc3`.
- Files written:
  - `src/rvt/frontdoor/prompt_intent.py` (+ its mirror `plugin/lib/src/rvt/frontdoor/prompt_intent.py`)
  - `tests/test_prompt_phase_count_845.py`
  - `tests/ci_shard.d/845-prompt-phase-count.txt`
  - this record
- Shipped: the count scrub.
- Staged, not shipped: nothing.

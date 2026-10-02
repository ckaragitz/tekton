# 959 nits — one input refusal for the ceiling-hung equipment families

Stream **equipment-detail** (tech-lead session, 2026-10-02). Refs #926. Carries the 🟡 nits of the independent review of #959 (head `0b6ec8f`).

## What changed

- **`equipment_common.positive_finite(val, what, unit)`** is the one refusal for an invalid number. It refuses a bool, a non-numeric string, NaN, an infinity, zero or a negative, with a `ValueError` reading "*what* must be a positive, finite number of *unit*, got …".
  - Before, `length_in="abc"` surfaced as `float()`'s own message.
- **`fan_powered`** uses it for the dimensions, the inlet and the supply voltage. A duplicated layout comment is merged into one.
- **`fan_coil`** uses it too: dimensions in inches, voltage in volts. This closes the gap #926 closed for the fan-powered box:
  - Before, a NaN dimension passed the fan coil's `<= 0` check.
  - Before, a non-positive dimension was re-raised from `fan_coil_parts` with the cabinet printed in feet.
  - `fan_coil_parts` itself now refuses a non-finite cabinet too, and prints it in inches.
- **Recorded here as the review asked:** #959 also changed one user-visible note in every *hardware-present* fan-powered build. The working-space zone note reads "in front of the electrical enclosure" where it used to read "in front of the disconnect". The disconnect is a toggle on that enclosure, and the zone is measured from the enclosure face.

Output for valid input is unchanged: the same floats reach the same code paths. No `.rfa` byte change is intended.

## Evidence

- `tests/test_fan_powered_895.py` and `tests/test_fan_coil_893.py` were run together: **100 passed**. New cases:
  - non-numeric dimension and voltage refusals in their units (both families);
  - NaN / zero / negative / bool fan coil dimensions;
  - `fan_coil_parts` with a NaN cabinet;
  - the electric heater panel centred (`cx == 0`) at 41, 44, 60 and 120 in.
- `tools/sync_plugin.py --check`: clean.

## Open

- The #959 review's other note: an inlet larger than the casing end records `Inlet Diameter` as `given` while nothing is drawn, and the note explains why. It is left as is.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/{equipment_common,fan_coil,fan_powered}.py` and their `plugin/lib` mirrors;
  - `tests/test_fan_coil_893.py`, `tests/test_fan_powered_895.py`;
  - this record.
- Gates: the stream-local tests above, plugin sync clean, session CI and independent review on the PR head before merge.
- Nothing is staged for the viewer; there is no certification claim (hard rule 4).

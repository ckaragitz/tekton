# 903 — fan coil follow-ups: stated assumptions, refused impossibilities, delivery at 2024 and above 1000 V

Stream **equipment-detail** (tech-lead session, 2026-10-01). Issue #903, the nits of #902's third independent review.

## What changed (`src/rvt/famgen/fan_coil.py`)

- **The voltage-to-ground note names its reading.**
  - Single-phase 240 V is "read as the 120/240 V single-phase system". A load on a corner-grounded 240 V delta would need the deeper space.
  - Three-phase 240 V is "read as a delta (240Y/139 V systems exist)", not "is a delta".
  - The note builder is `_note_vtg`.
- **Impossible supplies are refused up front:** a voltage that is not positive and finite (0, −5, inf, NaN), and phases that are not exactly 1 or 3 (0, 2, 1.5, `True`).
- **Above 1000 V to ground**, the 110.26(A) table does not apply (`ClearanceError`). The unit is delivered without the zone, with a "clearance zone NOT drawn" note and no toggle parameters (hard rule 1). Before, no file was written.
- **The shared `equipment_clearance.add_clearance_zones` delivers too** (#903 DONE 3; this was missed in the PR's first head and caught by review). On a `ClearanceError` it returns no forms and no toggles, and the family carries a "clearance zones NOT drawn" note. The panelboard and transformer callers already handle an empty `forms` list.
- **A voltage of `True` is refused**, like a boolean phase count.
- **2024 delivers.**
  - The 2024 class map has no `ArcElemCell`, so a full build raised `KeyError` and wrote nothing (#786).
  - `_arcs_available()` checks the map in force. When arcs are missing, the round parts (coil and drain stubs, conduit hub) are drawn as square boxes of the same size and place, with a "drawn SQUARE" note.
  - 2025 and 2026 keep true arcs.
- **The zone is authored by `_add_zone`;** the code is unchanged, only moved.
- `tests/test_fan_coil_893.py`:
  - `test_the_cli_passes_voltage_to_ground` now checks the effect through `--json`: a 3 ft zone and no delta note when the flag is given, 3.5 ft and the delta note when it is not;
  - the trailing whitespace and the E305 blank line are fixed.

## Evidence

- `tests/test_fan_coil_893.py`: 42 tests, adding the refused-supply table, the 120/240 V note, the 4160 V delivery and the 2024 row.
  - `G_ABPD_2024` default and non-fused 240 V/3-phase builds: VALID with 0 errors and provenance ok, with the square note.
  - The 2025 builds: VALID, with no square note.
- Together with `test_conftest_scaffolding.py` (the #707 leak guard): all pass.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`.
- Written: `src/rvt/famgen/fan_coil.py`, `src/rvt/famgen/equipment_clearance.py`, `tests/test_fan_coil_893.py`, this fragment and the index line, and the mirror.
- Staged: nothing.
- No certification claim.

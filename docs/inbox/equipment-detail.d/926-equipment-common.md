# 926 — fan-powered box follow-ups and the shared equipment helpers

Stream **equipment-detail** (tech-lead session, 2026-10-02). Issue #926, the nits of #925's independent review.

## What changed

- **`rvt.famgen.equipment_common`** (new) holds what the ceiling-hung equipment families share. These moved unchanged in behaviour out of `fan_coil`, so a third family does not import private helpers across modules:
  - `poles_for` and `voltage_to_ground_for` (with `LINE_TO_NEUTRAL_V`);
  - `note_voltage_to_ground` (was `_note_vtg`);
  - `add_working_zone(doc, forms, ws, H, y0, zx, where, vtg)` (was `_add_zone`). The wording now comes from the caller: "disconnect" / "electrical end" for the fan coil, "electrical enclosure" / "service side" for the fan-powered box.
  - `arcs_available` and `square_round_part` (was `_arcs_available` / `_square`).

  `fan_coil` re-exports the public names and keeps its private aliases.
- **`fan_powered`:**
  - Given dimensions and the inlet must be positive, finite numbers of inches, or are refused with a `ValueError` that says so. Before, a non-positive inlet fell into the casing-only fallback, recorded as `given`, and a NaN surfaced as a deep `FactoryError`. Refusal messages now print inches.
  - **The casing-only branch says only what it drew:** no inlet, discharge or induction openings to draw to, and the zone in front of the service side.
  - **The service-side comment matches the layout.** An electric heater's control panel is centred between the controls and the electrical enclosure, so it scales with the length.

## Evidence

- **The fan coil is byte-identical to main after the move:** sha256 of the written `.rfa` for the default unit, 240 V three-phase, cabinet-only and 4160 V matches `origin/main`.
- `tests/test_fan_powered_895.py`: 38 passed. New tests cover:
  - refused non-positive, NaN and boolean dimensions (in inches);
  - truthful casing-only notes;
  - contact for every attached part (inlet on the casing, enclosures on the side, toggle on its enclosure, discharge on the coil or casing, fan module and filter, reheat stubs on the coil, actuator on the collar), not only no interpenetration;
  - the helpers living in `equipment_common`.
- With `test_fan_coil_893.py`, `test_equipment_drives_913.py` and the scaffolding test: all pass.

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`.
- Written:
  - `src/rvt/famgen/equipment_common.py` (new), `src/rvt/famgen/fan_coil.py` (helpers moved out, imports), `src/rvt/famgen/fan_powered.py`;
  - `tests/test_fan_powered_895.py`;
  - this fragment and its index line, and the mirrors.
- Staged: nothing.
- No certification claim.

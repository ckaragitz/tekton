# 822 — every recognised kind no lane builds carries a recorded decision (DONE 1–2)

Stream **mep-taxonomy** (tech-lead session, 2026-10-07). Refs #822. This covers DONE 1 and 2; DONE 3, the kinds themselves, follows in its own PRs, electrical first.

## The count, reproduced on main (`02ba128`)

84 rows break down as follows:
- **79** with a category;
- **63** with no build lane: **1** umbrella (`luminaire`, a generic word with `refine`) and **62** leaf kinds with no builder.

By discipline, the 62 are: electrical 12, lighting 10, fire_alarm 6, technology 7, mechanical 15, plumbing 11, fire_protection 1. These match the numbers on #822.

**Also measured: a real gap in a kind we can already build.** "create a fan coil unit family" through `tools/route.py run --prompt … --output rfa` delivers nothing. Yet `rvt.famgen.fan_coil:make_fan_coil_unit` (#893) builds and validates that family. The constructor exists; the taxonomy row and the prompt route do not reach it. It is the first kind DONE 3 wires.

## What changed

- **`taxonomy.DECISIONS`** maps every gap row to `(outcome, reason)`, with outcome one of `archetype` / `catalog` / `not generated` (`DECISION_OUTCOMES`), the three honest outcomes #822 names. Supporting helpers are `gap_rows()` and `decision(row)`.
- **`taxonomy.check()`** now fails on four things, so a new taxonomy row cannot add a silent refusal, and a decision cannot outlive the gap it explains:
  - a gap row without a decision;
  - a decision whose row is no longer a gap;
  - an unknown outcome;
  - an empty reason.
- **The refusal line names the decision.** `builder_available()`, which the prompt route quotes, now ends with one of:
  - "planned lane (archetype, #822): …";
  - "not generated here, by decision: …".

  Previously it only said no lane builds the kind.
- **No near-miss mapping.** The `vav_box` row (aliases include "fan powered box") is not pointed at the fan-powered terminal (#895). Its decision says a bare VAV box must never be built as one.

## The decision table (DONE 1)

Generated from `taxonomy.DECISIONS`.

| discipline | archetype | catalog | not generated |
|---|---|---|---|
| electrical | 11 | 0 | 1 |
| lighting | 0 | 10 | 0 |
| fire_alarm | 1 | 5 | 0 |
| technology | 0 | 7 | 0 |
| mechanical | 15 | 0 | 0 |
| plumbing | 11 | 0 | 0 |
| fire_protection | 1 | 0 | 0 |

| kind | discipline | decision | reason |
|---|---|---|---|
| `motor_control_center` | electrical | archetype | a lineup of vertical sections at standard section sizes |
| `disconnect_switch` | electrical | archetype | an enclosure product class with a standard shape, as the lighting control panel (the fan coil already builds one as a part) |
| `variable_frequency_drive` | electrical | archetype | an enclosure product class with a standard shape, as the lighting control panel |
| `automatic_transfer_switch` | electrical | archetype | an enclosure product class with a standard shape, as the lighting control panel |
| `ups` | electrical | archetype | an enclosure product class with a standard shape, as the lighting control panel |
| `generator` | electrical | archetype | a packaged generator set: skid, engine-generator and enclosure at nominal sizes |
| `meter_center` | electrical | archetype | an enclosure product class with a standard shape, as the lighting control panel |
| `enclosed_circuit_breaker` | electrical | archetype | an enclosure product class with a standard shape, as the lighting control panel |
| `busway` | electrical | not generated | a busway RUN is drawn, not loaded as a family; its plug-in units and end fittings may become families later |
| `cable_tray_fitting` | electrical | archetype | elbows / tees / reducers derived from the cable tray archetype's own sizes |
| `conduit_fitting` | electrical | archetype | fittings derived from the conduit archetype's trade sizes |
| `floor_box` | electrical | archetype | a recessed box at standard gang sizes |
| `high_bay` | lighting | catalog | luminaires are built from a manufacturer record, as the troffer and the downlight are; this type needs a held record |
| `linear_luminaire` | lighting | catalog | luminaires are built from a manufacturer record, as the troffer and the downlight are; this type needs a held record |
| `wall_pack` | lighting | catalog | luminaires are built from a manufacturer record, as the troffer and the downlight are; this type needs a held record |
| `wall_sconce` | lighting | catalog | luminaires are built from a manufacturer record, as the troffer and the downlight are; this type needs a held record |
| `exit_sign` | lighting | catalog | luminaires are built from a manufacturer record, as the troffer and the downlight are; this type needs a held record |
| `emergency_light` | lighting | catalog | luminaires are built from a manufacturer record, as the troffer and the downlight are; this type needs a held record |
| `pole_light` | lighting | catalog | luminaires are built from a manufacturer record, as the troffer and the downlight are; this type needs a held record |
| `occupancy_sensor` | lighting | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `dimmer_switch` | lighting | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `daylight_sensor` | lighting | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `smoke_detector` | fire_alarm | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `heat_detector` | fire_alarm | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `pull_station` | fire_alarm | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `horn_strobe` | fire_alarm | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `duct_smoke_detector` | fire_alarm | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `fire_alarm_control_panel` | fire_alarm | archetype | an enclosure product class with a standard shape, as the lighting control panel |
| `data_outlet` | technology | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `telephone_outlet` | technology | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `speaker` | technology | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `card_reader` | technology | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `security_camera` | technology | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `intrusion_detector` | technology | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `nurse_call_station` | technology | catalog | a wall/ceiling device built by the device lane from a held catalog record, as the receptacle is |
| `air_handling_unit` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `rooftop_unit` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `fan_coil_unit` | mechanical | archetype | a house model exists (rvt.famgen.fan_coil:make_fan_coil_unit, #893) but is not wired to this row or the prompt route yet |
| `vav_box` | mechanical | archetype | the fan-powered terminal exists (rvt.famgen.fan_powered, #895) and answers this row's 'fan powered box' alias once wired; a bare VAV box (single duct, no fan) must never be built as one |
| `exhaust_fan` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `pump` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `boiler` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `chiller` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `cooling_tower` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `unit_heater` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `split_system` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `energy_recovery_unit` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `expansion_tank` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `fire_damper` | mechanical | archetype | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `volume_damper` | mechanical | archetype | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `water_heater` | plumbing | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `water_closet` | plumbing | archetype | a fixture with a standard shape for its class, at nominal sizes |
| `urinal` | plumbing | archetype | a fixture with a standard shape for its class, at nominal sizes |
| `lavatory` | plumbing | archetype | a fixture with a standard shape for its class, at nominal sizes |
| `sink` | plumbing | archetype | a fixture with a standard shape for its class, at nominal sizes |
| `drinking_fountain` | plumbing | archetype | a fixture with a standard shape for its class, at nominal sizes |
| `shower` | plumbing | archetype | a fixture with a standard shape for its class, at nominal sizes |
| `floor_drain` | plumbing | archetype | a fixture with a standard shape for its class, at nominal sizes |
| `backflow_preventer` | plumbing | archetype | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `pressure_reducing_valve` | plumbing | archetype | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `valve` | plumbing | archetype | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `fire_pump` | fire_protection | archetype | packaged equipment with a standard shape for its class, at nominal sizes |

## Evidence

- **`tests/test_taxonomy_decisions_822.py`: 6 passed.** It covers:
  - every gap is decided and `check()` is clean;
  - the gap count is ≤ 62;
  - a missing, stale, bad-outcome or empty-reason decision each fails the check;
  - the refusal names the decision;
  - the VAV-box near miss is ruled out.
- **The 14 test modules that touch the taxonomy, plus `test_plugin_sync`, scaffolding and `test_router`: 801 passed, 44 skipped.**
- `tools/sync_plugin.py --check`: clean.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/taxonomy.py` and its plugin mirror;
  - `tests/test_taxonomy_decisions_822.py` with the drop-in `tests/ci_shard.d/822-taxonomy-decisions.txt`;
  - this record.
- Shipped on merge.
- **Next (DONE 3):** wire the fan coil (`fan_coil_unit`) and the fan-powered terminal (the VAV row's "fan powered box" alias, with no bare-VAV near miss) to the taxonomy and the prompt route. Then the electrical archetypes, one PR each.
- No Revit claim (hard rule 4).

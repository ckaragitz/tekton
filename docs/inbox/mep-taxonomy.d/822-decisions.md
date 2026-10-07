# 822 — every recognised kind no lane builds carries a recorded decision (DONE 1–2)

Stream **mep-taxonomy** (tech-lead session, 2026-10-07). Refs #822. This covers DONE 1 and 2; DONE 3, the kinds themselves, follows in its own PRs, electrical first.

## The count, reproduced on main (`02ba128`)

84 rows break down as follows:
- **79** with a category;
- **63** with no build lane: **1** umbrella (`luminaire`, a generic word with `refine`) and **62** leaf kinds with no builder.

By discipline, the 62 are: electrical 12, lighting 10, fire_alarm 6, technology 7, mechanical 15, plumbing 11, fire_protection 1. They match #822's numbers. #822 counted 83 rows / 78 with a category because the `strut_trapeze` row, which has a lane, was added after it was filed. #822's "lighting 11" includes the `luminaire` umbrella.

**Also measured: a real gap in a kind we can already build.** "create a fan coil unit family" through `tools/route.py run --prompt … --output rfa` delivers nothing. Yet `rvt.famgen.fan_coil:make_fan_coil_unit` (#893) builds and validates that family. The constructor exists; the taxonomy row and the prompt route do not reach it. It is the first kind DONE 3 wires.

## What changed

- **`taxonomy.DECISIONS`** maps every gap row to `(outcome, reason)`, with outcome one of `archetype` / `catalog` / `not generated` (`DECISION_OUTCOMES`), the three honest outcomes #822 names. Supporting helpers are `gap_rows()` and `decision(row)`. `describe()` / `make_family.py taxonomy --json` carry the decision as a structured `decision` field.
- **All 62 are `archetype`, and why.** Steer #591 (S-2026-08-10-e) says a product named with no dimensions is generated at its class's standard nominal sizes, never refused and never wearing a manufacturer's numbers. Every gap kind has a standard shape for its class, so the archetype lane closes each one. A held manufacturer record later adds catalog members beside it, as the troffer / downlight / receptacle lanes have. `catalog` as the *only* lane would have left lighting and device prompts refusing until a record exists, which is what #1043's first review caught.
- **Busway.** Revit has no busway system family: busway is modelled with loadable families. The row's old note ("a busway RUN is drawn, not loaded") was wrong and is corrected. Busway is an archetype like the rest, not "not generated".
- **`taxonomy.check()`** now fails on four things, so a new taxonomy row cannot add a silent refusal, and a decision cannot outlive the gap it explains:
  - a gap row without a decision;
  - a decision whose row is no longer a gap;
  - an unknown outcome;
  - an empty reason.
- **The refusal line names the decision.** `builder_available()`, which the prompt route quotes, now ends with one of:
  - "next for this kind (#822): the archetype lane -- …";
  - "by decision it is not generated here: …".

  Previously it only said no lane builds the kind.
- **No near-miss mapping.** The `vav_box` row (aliases include "fan powered box") is not pointed at the fan-powered terminal (#895). Its decision says a bare VAV box is never built as one.
- **Conflict rows.** A gap row whose category is in conflict (#516) still needs a decision. Its conflict line reaches the user first. No gap row is in conflict today.

## The decision table (DONE 1)

Generated from `taxonomy.DECISIONS`.

| discipline | archetype | catalog | not generated |
|---|---|---|---|
| electrical | 12 | 0 | 0 |
| lighting | 10 | 0 | 0 |
| fire_alarm | 6 | 0 | 0 |
| technology | 7 | 0 | 0 |
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
| `busway` | electrical | archetype | straight sections and fittings at nominal ampacity sizes -- Revit models busway with loadable families, not a system family |
| `cable_tray_fitting` | electrical | archetype | elbows / tees / reducers derived from the cable tray archetype's own sizes |
| `conduit_fitting` | electrical | archetype | fittings derived from the conduit archetype's trade sizes |
| `floor_box` | electrical | archetype | a recessed box at standard gang sizes |
| `high_bay` | lighting | archetype | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `linear_luminaire` | lighting | archetype | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `wall_pack` | lighting | archetype | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `wall_sconce` | lighting | archetype | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `exit_sign` | lighting | archetype | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `emergency_light` | lighting | archetype | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `pole_light` | lighting | archetype | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `occupancy_sensor` | lighting | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `dimmer_switch` | lighting | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `daylight_sensor` | lighting | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `smoke_detector` | fire_alarm | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `heat_detector` | fire_alarm | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `pull_station` | fire_alarm | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `horn_strobe` | fire_alarm | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `duct_smoke_detector` | fire_alarm | archetype | a duct-mounted housing with its sampling tubes, at nominal sizes |
| `fire_alarm_control_panel` | fire_alarm | archetype | an enclosure product class with a standard shape, as the lighting control panel |
| `data_outlet` | technology | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `telephone_outlet` | technology | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `speaker` | technology | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `card_reader` | technology | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `security_camera` | technology | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `intrusion_detector` | technology | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `nurse_call_station` | technology | archetype | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `air_handling_unit` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `rooftop_unit` | mechanical | archetype | packaged equipment with a standard shape for its class, at nominal sizes |
| `fan_coil_unit` | mechanical | archetype | a fan coil constructor exists (#893); this kind and the prompt route do not reach it yet |
| `vav_box` | mechanical | archetype | the fan-powered terminal (#895) will answer this kind's 'fan powered box' wording; a bare VAV box (single duct, no fan) is never built as one |
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

- **`tests/test_taxonomy_decisions_822.py`: 7 passed.** It covers:
  - every gap is decided and `check()` is clean;
  - the gap count is ≤ 62 (a deliberate ceiling: a later PR that adds a gap row *with* its decision must raise it, and say why in its record; it may never be raised to hide a refusal);
  - a missing, stale, bad-outcome or empty-reason decision each fails the check;
  - the refusal and `describe()` name the decision;
  - busway is a loadable (archetype) kind;
  - the VAV-box near miss is ruled out.
- **The 14 test modules that touch the taxonomy, plus `test_plugin_sync`, scaffolding, `test_router` and `test_doc_caveats_990`: 837 passed, 44 skipped.**
- `tools/sync_plugin.py --check`: clean.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/taxonomy.py` and its plugin mirror;
  - `tests/test_taxonomy_decisions_822.py` with the drop-in `tests/ci_shard.d/822-taxonomy-decisions.txt`;
  - this record.
- Shipped on merge.
- **Next (DONE 3):** wire the fan coil (`fan_coil_unit`) and the fan-powered terminal (the VAV row's "fan powered box" alias, with no bare-VAV near miss) to the taxonomy and the prompt route. Then the electrical archetypes, one PR each.
- No Revit claim (hard rule 4).

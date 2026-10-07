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
- **All 62 are `archetype`, and why.** Steer #591 (S-2026-08-10-e) says a product named with no dimensions is generated at its class's standard nominal sizes, never refused and never wearing a manufacturer's numbers. A held manufacturer record later adds catalog members beside each, as the troffer / downlight / receptacle lanes have. Not every row is one shape, though. **31 rows name several distinct products** under one kind, for example:
- a split system (outdoor unit + indoor unit);
- fan coils (horizontal concealed / vertical cabinet / ceiling cassette);
- "exhaust fan" (inline / roof exhauster / utility set);
- security cameras (dome / bullet / PTZ);
- busway (straight section / fitting / plug-in unit / end closure);
- valves, sinks, drains, pumps and boilers.

They are listed with their products in **`taxonomy.REFINE_FIRST`**, a permanent table, and **their rows are permanent too**.

Each such row stays in `_ROWS`, unbuilt, holding the words that name all of its products ("fan coil unit", "fcu"). The honest answer to those words is "this name covers several products (…)". The products are added as rows *beside* it, each with only the words that name it ("horizontal fan coil"), each with its own builder or decision. The decision for the multi-product row is derived from the table: one archetype per product, never one box for all.

**`check()` fails if a `REFINE_FIRST` key is missing from `_ROWS` (removed or renamed away), has a build mechanism, or is a generic (`refine`) word.** `refine` in this taxonomy is a *category-wide* generic word, not a split, which is what #1043's fourth review caught.

Tests pin this, patching `_ROWS`, its key index and its alias index together, the way a real edit would:
- **The mechanism bypass fails:** the row given a builder.
- **The rename bypass fails:** same label and words, new key, with a builder.
- **The prescribed split passes:** fan coil horizontal / vertical / cassette rows beside the kept row. With it, "fan coil unit", "fan coil" and "fcu" still resolve to the unbuilt row, and "horizontal fan coil" resolves to the built one.

**The guard's stated limit.** Moving the row's shared *words* onto a built row, so that "fcu" resolves to one product, is a resolution question. It is not caught here; it is added to #1044 as its DONE 4.

That #893 constructor builds the *horizontal concealed* unit only, so it answers that product's row once added, never the multi-product row or a vertical or cassette request. The remaining 31 rows have one standard shape for their class.

Pre-existing **aliases that name a different product** (e.g. "water source heat pump" → split system, "packaged terminal unit" → VAV box) are a resolution bug of their own, filed as #1044. `catalog` as the *only* lane would have left lighting and device prompts refusing until a record exists, which is what #1043's first review caught.
- **Busway.** Revit has no busway system family: busway is modelled with loadable families. The row's old note ("a busway RUN is drawn, not loaded") was wrong and is corrected. Busway is an archetype like the rest, not "not generated".
- **`taxonomy.check()`** now fails on four things, so a new taxonomy row cannot add a silent refusal, and a decision cannot outlive the gap it explains:
  - a gap row without a decision;
  - a decision whose row is no longer a gap;
  - an unknown outcome;
  - an empty reason.
- **The refusal line names the decision.** `builder_available()`, which the prompt route quotes, now ends with one of:
  - "planned: built at standard nominal sizes for its class";
  - "planned: this name covers several products (…), each to be built on its own at standard nominal sizes";
  - "by decision it is not built here: …".

  The internal rationale stays in `DECISIONS`; the user line carries no issue numbers or module paths, and never the word "generated" on a kind no lane builds (`test_taxonomy_692` pins that).

  Previously it only said no lane builds the kind.
- **No near-miss mapping.** The `vav_box` row (aliases include "fan powered box") is not pointed at the fan-powered terminal (#895). Its decision is to refine it first: the fan-powered wording is split off for #895's constructor, and a single-duct VAV box gets its own archetype. A test checks that "vav box" resolves to its own, still-unbuilt row.
- **Conflict rows.** A gap row whose category is in conflict (#516) still needs a decision. Its conflict line reaches the user first. No gap row is in conflict today.

## The decision table (DONE 1)

Generated from `taxonomy.decision()` over `DECISIONS` (one-shape rows) and `REFINE_FIRST` (multi-product rows).

| discipline | archetype | catalog | not generated |
|---|---|---|---|
| electrical | 12 | 0 | 0 |
| lighting | 10 | 0 | 0 |
| fire_alarm | 6 | 0 | 0 |
| technology | 7 | 0 | 0 |
| mechanical | 15 | 0 | 0 |
| plumbing | 11 | 0 | 0 |
| fire_protection | 1 | 0 | 0 |

| kind | discipline | decision | products (rows added beside it) | reason |
|---|---|---|---|---|
| `motor_control_center` | electrical | archetype | — | a lineup of vertical sections at standard section sizes |
| `disconnect_switch` | electrical | archetype | — | an enclosure product class with a standard shape, as the lighting control panel (the fan coil already builds one as a part) |
| `variable_frequency_drive` | electrical | archetype | — | an enclosure product class with a standard shape, as the lighting control panel |
| `automatic_transfer_switch` | electrical | archetype | — | an enclosure product class with a standard shape, as the lighting control panel |
| `ups` | electrical | archetype | — | an enclosure product class with a standard shape, as the lighting control panel |
| `generator` | electrical | archetype | — | a packaged generator set: skid, engine-generator and enclosure at nominal sizes |
| `meter_center` | electrical | archetype | meter stack / center, meter socket, CT cabinet | archetype per product: this kind names several products with no single shape (meter stack / center, meter socket, CT cabinet), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `enclosed_circuit_breaker` | electrical | archetype | — | an enclosure product class with a standard shape, as the lighting control panel |
| `busway` | electrical | archetype | straight section, elbow / tee fitting, plug-in unit, end closure | archetype per product: this kind names several products with no single shape (straight section, elbow / tee fitting, plug-in unit, end closure), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `cable_tray_fitting` | electrical | archetype | elbow, tee, cross, reducer | archetype per product: this kind names several products with no single shape (elbow, tee, cross, reducer), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all; each sized from the cable tray archetype's own sizes |
| `conduit_fitting` | electrical | archetype | elbow, conduit body, coupling | archetype per product: this kind names several products with no single shape (elbow, conduit body, coupling), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all; each sized from the conduit archetype's trade sizes |
| `floor_box` | electrical | archetype | floor box, poke-through | archetype per product: this kind names several products with no single shape (floor box, poke-through), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `high_bay` | lighting | archetype | round high bay, linear high bay | archetype per product: this kind names several products with no single shape (round high bay, linear high bay), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `linear_luminaire` | lighting | archetype | strip, linear pendant, wraparound | archetype per product: this kind names several products with no single shape (strip, linear pendant, wraparound), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `wall_pack` | lighting | archetype | — | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `wall_sconce` | lighting | archetype | — | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `exit_sign` | lighting | archetype | — | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `emergency_light` | lighting | archetype | — | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `pole_light` | lighting | archetype | — | a luminaire with a standard shape for its type, at nominal sizes; catalog members join when a manufacturer record is held |
| `occupancy_sensor` | lighting | archetype | wall-switch sensor, ceiling sensor | archetype per product: this kind names several products with no single shape (wall-switch sensor, ceiling sensor), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `dimmer_switch` | lighting | archetype | — | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `daylight_sensor` | lighting | archetype | interior daylight sensor, exterior photocell | archetype per product: this kind names several products with no single shape (interior daylight sensor, exterior photocell), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `smoke_detector` | fire_alarm | archetype | — | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `heat_detector` | fire_alarm | archetype | — | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `pull_station` | fire_alarm | archetype | — | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `horn_strobe` | fire_alarm | archetype | horn / strobe, speaker / strobe, strobe only | archetype per product: this kind names several products with no single shape (horn / strobe, speaker / strobe, strobe only), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `duct_smoke_detector` | fire_alarm | archetype | — | a duct-mounted housing with its sampling tubes, at nominal sizes |
| `fire_alarm_control_panel` | fire_alarm | archetype | — | an enclosure product class with a standard shape, as the lighting control panel |
| `data_outlet` | technology | archetype | — | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `telephone_outlet` | technology | archetype | — | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `speaker` | technology | archetype | ceiling / paging speaker, intercom station | archetype per product: this kind names several products with no single shape (ceiling / paging speaker, intercom station), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `card_reader` | technology | archetype | — | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `security_camera` | technology | archetype | dome camera, bullet camera, PTZ camera | archetype per product: this kind names several products with no single shape (dome camera, bullet camera, PTZ camera), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `intrusion_detector` | technology | archetype | PIR motion detector, glass-break detector, door contact | archetype per product: this kind names several products with no single shape (PIR motion detector, glass-break detector, door contact), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `nurse_call_station` | technology | archetype | — | a wall / ceiling device with a standard shape, at nominal sizes; catalog members join when a manufacturer record is held |
| `air_handling_unit` | mechanical | archetype | air handling unit, make-up air unit, DOAS unit | archetype per product: this kind names several products with no single shape (air handling unit, make-up air unit, DOAS unit), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `rooftop_unit` | mechanical | archetype | — | packaged equipment with a standard shape for its class, at nominal sizes |
| `fan_coil_unit` | mechanical | archetype | horizontal concealed, vertical cabinet, ceiling cassette | archetype per product: this kind names several products with no single shape (horizontal concealed, vertical cabinet, ceiling cassette), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all; the fan coil constructor (#893) builds the horizontal concealed unit only, so it answers the horizontal concealed product row once one is added -- never this row, a vertical or a cassette request |
| `vav_box` | mechanical | archetype | single-duct VAV box, fan-powered terminal | archetype per product: this kind names several products with no single shape (single-duct VAV box, fan-powered terminal), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all; the fan-powered constructor (#895) answers only the 'fan powered box' wording -- a single-duct VAV gets its own archetype |
| `exhaust_fan` | mechanical | archetype | inline fan, roof exhauster, utility set, ceiling / cabinet exhaust fan | archetype per product: this kind names several products with no single shape (inline fan, roof exhauster, utility set, ceiling / cabinet exhaust fan), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `pump` | mechanical | archetype | inline / circulator, end suction, base-mounted, packaged booster set | archetype per product: this kind names several products with no single shape (inline / circulator, end suction, base-mounted, packaged booster set), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `boiler` | mechanical | archetype | wall-hung condensing boiler, floor-standing hot water boiler, steam boiler | archetype per product: this kind names several products with no single shape (wall-hung condensing boiler, floor-standing hot water boiler, steam boiler), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `chiller` | mechanical | archetype | air-cooled chiller, water-cooled chiller | archetype per product: this kind names several products with no single shape (air-cooled chiller, water-cooled chiller), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `cooling_tower` | mechanical | archetype | open cooling tower, closed-circuit fluid cooler | archetype per product: this kind names several products with no single shape (open cooling tower, closed-circuit fluid cooler), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all; the 'evaporative cooler' wording also names an air-side unit |
| `unit_heater` | mechanical | archetype | unit heater, cabinet unit heater | archetype per product: this kind names several products with no single shape (unit heater, cabinet unit heater), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `split_system` | mechanical | archetype | outdoor condensing unit / heat pump, wall-mount indoor head, ceiling cassette indoor unit, ducted indoor unit | archetype per product: this kind names several products with no single shape (outdoor condensing unit / heat pump, wall-mount indoor head, ceiling cassette indoor unit, ducted indoor unit), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all; a split system is two pieces of equipment, never one packaged box |
| `energy_recovery_unit` | mechanical | archetype | — | packaged equipment with a standard shape for its class, at nominal sizes |
| `expansion_tank` | mechanical | archetype | — | packaged equipment with a standard shape for its class, at nominal sizes |
| `fire_damper` | mechanical | archetype | — | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `volume_damper` | mechanical | archetype | — | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `water_heater` | plumbing | archetype | tank water heater, tankless water heater | archetype per product: this kind names several products with no single shape (tank water heater, tankless water heater), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `water_closet` | plumbing | archetype | floor-mount water closet, wall-hung water closet | archetype per product: this kind names several products with no single shape (floor-mount water closet, wall-hung water closet), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `urinal` | plumbing | archetype | — | a fixture with a standard shape for its class, at nominal sizes |
| `lavatory` | plumbing | archetype | wall-hung lavatory, countertop lavatory | archetype per product: this kind names several products with no single shape (wall-hung lavatory, countertop lavatory), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `sink` | plumbing | archetype | counter / kitchen sink, service / mop sink | archetype per product: this kind names several products with no single shape (counter / kitchen sink, service / mop sink), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `drinking_fountain` | plumbing | archetype | drinking fountain, bottle filler | archetype per product: this kind names several products with no single shape (drinking fountain, bottle filler), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `shower` | plumbing | archetype | — | a fixture with a standard shape for its class, at nominal sizes |
| `floor_drain` | plumbing | archetype | floor drain, floor sink, trench drain | archetype per product: this kind names several products with no single shape (floor drain, floor sink, trench drain), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |
| `backflow_preventer` | plumbing | archetype | — | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `pressure_reducing_valve` | plumbing | archetype | — | an in-line accessory sized by its duct / pipe, at nominal sizes |
| `valve` | plumbing | archetype | ball, gate, butterfly, check | archetype per product: this kind names several products with no single shape (ball, gate, butterfly, check), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all; each sized by its pipe |
| `fire_pump` | fire_protection | archetype | fire pump, jockey pump | archetype per product: this kind names several products with no single shape (fire pump, jockey pump), so one row per product is added beside this one (each with the words that name only it) and gets its own archetype; this row stays, unbuilt, for the words that name them all -- never one box for all |

## Evidence

- **`tests/test_taxonomy_decisions_822.py`: 12 passed.** Both `REFINE_FIRST` rules are mutation-checked: disabling either makes its bypass test fail. It covers:
  - every gap is decided and `check()` is clean;
  - the gap count is ≤ 62 (#822 DONE 4: the count trends down only by building kinds, never up);
  - a missing, stale, bad-outcome or empty-reason decision each fails the check;
  - the refusal and `describe()` name the decision;
  - busway is a loadable (archetype) kind;
  - every `REFINE_FIRST` row has at least two products and a derived split-first decision, and none is also in `DECISIONS`;
  - such a row given a builder, or renamed away, fails `check()`; the prescribed split passes, and the shared words stay unbuilt;
  - a "not generated" reason the user would read cannot carry an issue number, a module path or the word "generated";
  - a "not generated" refusal promises no later lane;
  - the VAV-box near miss is ruled out by routing, not by wording.
- **842 passed, 44 skipped** for every module that mentions the taxonomy (`grep -l taxonomy tests/test_*.py`: 14 files), plus `test_plugin_sync`, `test_conftest_scaffolding`, `test_router` and `test_doc_caveats_990`. Rerun with `pytest $(grep -l taxonomy tests/test_*.py) tests/test_plugin_sync.py tests/test_conftest_scaffolding.py tests/test_router.py tests/test_doc_caveats_990.py`.
- `tools/sync_plugin.py --check`: clean.

## BRANCH STATE

- Files:
  - `src/rvt/famgen/taxonomy.py` and its plugin mirror;
  - `tests/test_taxonomy_decisions_822.py` with the drop-in `tests/ci_shard.d/822-taxonomy-decisions.txt`;
  - this record.
- Shipped on merge.
- **Next (DONE 3):** add the fan coil's product rows beside `fan_coil_unit` (horizontal concealed / vertical cabinet / ceiling cassette) and wire the horizontal concealed row to the #893 constructor. Likewise add the VAV row's fan-powered terminal row for #895. Then the electrical archetypes, one PR each.
- No Revit claim (hard rule 4).

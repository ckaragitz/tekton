# 895 — a fan-powered terminal unit (series or parallel)

Stream **equipment-detail** (tech-lead session, 2026-10-01). Issue #895, from steer #891 ("do your research about fan coil units or fan power boxes").

## Research (anatomy and class proportions only)

The sources were public product pages and engineering guides for series and parallel fan-powered terminal units, read through web search snippets; page fetches are blocked by this environment's egress policy. No manufacturer dimension, model or part number is carried. What the code follows:
- **Casing:** a lined casing hung above the ceiling, standard height about 17–20 in (low-profile about 10.5–12.5 in), in a handful of casing sizes.
- **Primary air:** a round inlet (classes of about 4–16 in) with its damper, flow sensor and actuator.
- **Series:** the fan sits in the airstream and draws plenum air through an induction opening (often filtered).
- **Parallel:** the fan sits beside the primary airstream, with its own induction opening in the casing wall and a backdraft damper.
- **Discharge:** a rectangular duct connection, optionally after hot-water or electric reheat.
- **Electrical:** a controls enclosure and a high-voltage connection with a disconnect.

## What was built

**`rvt.famgen.fan_powered`:**
- `fan_powered_parts(L, W, H, kind=, inlet_d=, reheat=)`. Airflow is +x; the service side is +y.
  - The casing.
  - The round primary inlet at −x (meeting the casing face), with its damper actuator.
  - The induction opening filter: beside the inlet for series; in the wall of a side fan module for parallel.
  - The discharge collar at +x, after a hot-water reheat coil with two stubs when asked.
  - On the service side, each in its own slot clear of the corner brackets: the controls enclosure at the inlet end, the electrical enclosure (toggle disconnect, conduit hub) at the discharge end, and an electric heater's control panel between them.
  - 4 hanger brackets.
- `make_fan_powered_box(kind=, length_in=, width_in=, height_in=, inlet_in=, reheat=, voltage=, phases=, voltage_to_ground=)`. Mechanical Equipment.
  - **Defaults:** dimensions `nominal` unless given (40 × 30 × 18 in, 10 in inlet; 44 in long with electric reheat). Voltage and phases are `assumed` unless given (277 V single-phase, the common ECM-motor supply).
  - **Connectors:** one power and one conduit connector (#894) on the electrical enclosure.
  - **Working space:** the NEC working space in front of the electrical enclosure, drawn the unit's height (110.26(A)(4)), magenta and toggleable.
  - **Odd inputs:** a casing too small for its hardware delivers the casing alone, with a note. Invalid input (kind, reheat, voltage, phases) is refused.
- **CLI:** `tools/make_family.py fan-powered-box --kind {series,parallel} --reheat {none,hot_water,electric} [--length --width --height --inlet --voltage --phases --voltage-to-ground]`.
- **Shared with the fan coil:**
  - `poles_for`, `voltage_to_ground_for`, `_add_zone`, `_note_vtg`, `_arcs_available` and `_square`, imported from `fan_coil`.
  - **`_square` fixed:** it drew every horizontal cylinder along y. An x-axis cylinder (this unit's inlet) is now kept along x. The fan coil has no x-axis cylinder, so nothing shipped is affected.
- **#920 wording nits** in `mep_connectors`: "in a 2025 file", and "not domain state".

## Evidence

- `tests/test_fan_powered_895.py`:
  - no overlap between any two parts, for 4 kinds × 3 sizes;
  - the inlet meets the casing face along x;
  - induction placement per kind;
  - provenance, connectors (277 V gives 1 pole) and the zone (277 V to ground gives 3.5 ft);
  - the longer electric default;
  - refused inputs;
  - the small-casing delivery;
  - VALID with 0 errors at 2026, 2025 and 2024 for series and parallel with hot-water reheat;
  - the CLI.
- With `test_fan_coil_893.py` (plus the `_square` x-axis test) and the scaffolding test: 95 passed.

## Open

- **Duct and hydronic connectors:** no corpus specimen pins their system (#894). Inlet, discharge, induction and reheat stay geometry, said in the notes.
- **Sizes do not drive the parts:** the #913 program owns the constraint wiring.
- **"Behaves in Revit"** needs a desktop verdict (hard rule 4).

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`.
- Written:
  - `src/rvt/famgen/fan_powered.py` (new), `src/rvt/famgen/fan_coil.py` (`_square`), `src/rvt/famgen/mep_connectors.py` (docstring), `tools/make_family.py` (`fan-powered-box`);
  - `tests/test_fan_powered_895.py` and its drop-in, `tests/test_fan_coil_893.py`;
  - this fragment and its index line, and the mirrors.
- Staged: nothing.
- No certification claim.

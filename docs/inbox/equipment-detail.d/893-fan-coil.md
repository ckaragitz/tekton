# 893 — a fan coil unit with a unit-mounted fused disconnect

Stream **equipment-detail** (tech-lead session, 2026-10-01). Issue #893, from steer #891.

**Ask.** The owner wrote: "What about a fan coil unit with a disconnect on it? 30AF/15AS". Then: "I want you to learn how to build anything, so try your best and do your research about fan coil units or fan power boxes" (#891). `fan_coil_unit` was a taxonomy and vendor-directory name with no build lane.

## Research (anatomy and class proportions only)

The sources were public installation manuals and product pages for horizontal concealed fan coils. They were read through web search snippets; direct page fetches are blocked by this environment's egress policy. No manufacturer dimension, model or part number is carried. What the code follows:
- A ceiling-hung cabinet about 10–11 in high and about 2 ft deep in the airflow direction. Its length grows with airflow (classes of roughly 200–1200 cfm).
- A rear return through a filter rack, and a front rectangular supply duct collar.
- A removable bottom access panel for the fan, motor and filter.
- Coil connections (3/4 in) and the sloped drain pan's outlet on one end.
- The electrical junction / control box on the end opposite the coil connections. Field power enters through 7/8 in knockouts on the side or top.
- Hanger brackets for the rods.

## What was built

**`rvt.famgen.fan_coil`:**
- `fan_coil_parts(L, D, H)` returns 17 parts. Airflow is +x; the piping end is −y and the electrical end +y.
  - the cabinet;
  - the supply duct collar and the return filter rack;
  - a bottom access panel;
  - 4 hanger brackets;
  - 3/4 in coil supply and return stubs, and a condensate stub at the drain pan;
  - the unit control box;
  - the fused disconnect, with its operating handle, rating label and conduit hub.
- `make_fan_coil_unit(...)` builds a Mechanical Equipment family:
  - dimensions `nominal` (42 × 23 × 10.5 in for the class) unless given;
  - the disconnect's frame and fuse `given` (30 AF / 15 AS);
  - the voltage `assumed` (208 V, 1-phase) unless given.
- **One electrical connector, on the disconnect's top (the conduit hub)**, 2 poles, bound to `Voltage`.
- **The NEC 110.26(A) working space in front of the disconnect**: magenta, and toggleable through the #882 parameters.
  - It is drawn the unit's height. A ceiling-hung family does not know the floor, and above a suspended ceiling 110.26(A)(4) (limited access) governs.
  - Its voltage to ground is 120 V for a ≤ 240 V supply, stated.
- **Category standards:** 16 mechanical-equipment standard parameters authored, blank (S-2026-08-11-a).
- **CLI:** `tools/make_family.py fan-coil [--length --depth --height --voltage --phases --frame --fuse --non-fused …]`.

## Evidence

- `tests/test_fan_coil_893.py` (8 tests):
  - the anatomy (pipes and power on opposite ends, the drain low, the disconnect within the height, the hub on top);
  - a refused small cabinet;
  - the provenance tiers;
  - the connector on the disconnect;
  - the zone toggle, magenta and limited-access note;
  - VALID with 0 errors on 2026 and inside the 2025 build context;
  - the CLI.
- **Delivered to the owner:** `FanCoilUnit_Horizontal_208V-1Ph_30AF-15AS_R2026/R2025.rfa`. Both are VALID with 0 errors under `rvt_validate` and family mode, with provenance ok, 17 forms and 1 connector.

## Review round 1 (#902): what changed

- **Poles follow the supply.** `poles_for` returns 3 for three-phase. Single-phase is 1 pole line-to-neutral (120 / 127 / 277 / 347 V) and 2 poles line-to-line (208 / 240 / 480 / 600 V). The first head gave a 277 V unit 2 poles, which matches no distribution system.
- **Voltage to ground follows the supply.** `voltage_to_ground_for`: 208 → 120, 240 → 120, 480 → 277, 600 → 347, a line-to-neutral supply its own, else V/√3. The value is stated in the notes.
- **Provenance from presence, not from value.**
  - `voltage` and `phases` default to `None` in both the function and the CLI. A value the caller states is `given` ("the request"), even when it equals the assumption.
  - The disconnect's sources are built from the actual values.
  - A non-fused unit carries no fuse fact, and its part is a plain "disconnect switch".
- **Odd dimensions still deliver.**
  - A cabinet too small for its end hardware is delivered alone, with its power connector on the electrical end, the working space in front of that end, and a note.
  - The minimum depth for the end hardware is 16 in. Below 15.5 in, the control box and the disconnect overlapped.
- **The panelboard factory's tiny-box fallback is now tested through `make_panelboard`.**
- **Tests:** `tests/test_fan_coil_893.py` has 23 tests (pole/ground table, 277 V, non-fused, 4 odd shapes, no overlap at the minimum depth). Together with the panelboard detail tests: 32 passed.

## Open

- **Pipe and duct connectors are not authored** (#894). The writer has only the electrical domain, so the coil, drain and duct connections are geometry, and the notes say so.
- Fan-powered terminal units (#895).
- No desktop verdict (hard rule 4).

## BRANCH STATE

Branch `claude/eager-franklin-xgzgda`.
- Written:
  - `src/rvt/famgen/fan_coil.py` (new), `tools/make_family.py` (the `fan-coil` subcommand);
  - `tests/test_fan_coil_893.py` and its drop-in;
  - this fragment, and the mirrors.
- Carried from #897's second review (nits):
  - the `892-panelboard-parts.md` latency table corrected to the reviewer's 6-run sample (+1.0 s, not +0.6 s);
  - a guard for tiny panelboard boxes (refused by `panelboard_parts`; the factory delivers the box and says so) with a test;
  - the stale `make_panelboard` comment;
  - #885 → #892 in `tests/test_famgen_factory.py`.
- Staged: nothing.
- No certification claim.

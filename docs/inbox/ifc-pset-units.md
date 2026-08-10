# ifc-pset-units — pset length / area / volume measures honour the IFC project's unit assignment (issue #348)

## eng #348 — 2026-08-10

Stream: `ifc-pset-units` (eng #348, cloud engineer session started by the tech-lead session,
2026-08-10). Charter = issue #348 (Refs #153, #154; **PG1** trustworthy output; size S).
Territory: `src/rvt/ifc/intent.py` (`_psets` + new unit helpers), the two re-pinned
conformance expectations `tests/ifc_conformance/{a_units_mm,b_units_feet}.expected.json`
(regenerated ONLY through `tools/dev/make_ifc_fixtures.py --update-expected`), the
`a_units_mm` registry note in `tools/dev/make_ifc_fixtures.py`, NEW
`tests/test_ifc_intent_units.py` + its shard drop-in `tests/ci_shard.d/348-pset-length-units.txt`,
the regenerated mirror `plugin/lib/src/rvt/ifc/intent.py`, this record. NOT touched:
`src/rvt/ifc/steplite.py` (called, never edited — no new row was needed), `tools/ifc_intent.py`,
`src/rvt/frontdoor/**`, hot files.

## Why

`rvt.ifc.intent._psets()` returned `ifcopenshell.util.element.get_psets()` verbatim. Both
backends (the real wheel and steplite) unwrap every `IfcPropertySingleValue` to a bare Python
number, so a millimetre file's `RoomInformation.ClearWidth = IFCLENGTHMEASURE(5800.)` reached
`model.room.info` — and from there `RoomShell.clear["clearWidth_m"]`, a key that *says*
metres — as `5800.0`, while every vertex-derived number of the same intent had been
multiplied by `length_scale_m_per_unit = 0.001`. Pinned evidence before the change:
`tests/ifc_conformance/a_units_mm.expected.json` → `room.info.ClearWidth == 5800.0`;
`b_units_feet` → `19.029` (feet). A Revit / ArchiCAD export writes dimensions exactly this way
(length measures in project units), so any consumer comparing `ClearWidth` with the wall ring
was off by ×1000 on a mm file and ×3.28 on a feet file.

## What was built (`src/rvt/ifc/intent.py`)

* `_DIMENSIONED`: wrapped measure class (of an `IfcPropertySingleValue`) or quantity class →
  (`IfcUnitEnum` it is expressed in, power an SI prefix carries): `IfcLengthMeasure`,
  `IfcPositiveLengthMeasure`, `IfcNonNegativeLengthMeasure`, `IfcQuantityLength` → LENGTHUNIT¹;
  `IfcAreaMeasure`, `IfcQuantityArea` → AREAUNIT²; `IfcVolumeMeasure`, `IfcQuantityVolume` →
  VOLUMEUNIT³. Everything else (`IfcReal`, `IfcInteger`, `IfcCountMeasure`, `IfcMassMeasure`,
  labels, enumerated / list values) passes through untouched.
* `_si_factor(unit, power)`: SI value of ONE `IfcNamedUnit` — conversion-based chains multiply
  through (`FOOT` = 0.3048 m; `INCH` = 25.4 × MILLI METRE = 0.0254 m), an SI prefix counts
  `power` times (MILLI on CUBIC_METRE = 1e-9). Derived / context-dependent / absent → 1.0.
* `_unit_scales(f)`: `{LENGTHUNIT, AREAUNIT, VOLUMEUNIT} → factor` for the project's
  `UnitsInContext`. **The length factor IS `_length_scale(f)`** (= `calculate_unit_scale`, THE
  number `resolve_intent` applies to every vertex), so a pset length and a coordinate can never
  disagree by construction. Area and volume read their
  OWN assigned unit — deliberately NOT `length_scale²` / `³` as the issue text sketched: a Revit
  mm export routinely keeps `AREAUNIT = SQUARE_METRE`, and squaring 0.001 onto it would turn a
  correct 24.9 m² into 2.5e-5. (`calculate_unit_scale(f, "AREAUNIT")` was not usable either: on
  both backends it applies a prefix once regardless of SQUARE_/CUBIC_, so MILLI SQUARE_METRE
  reads 1e-3 instead of 1e-6, and it cannot take a single property's `Unit`.)
* `_measure_factors(prod, unit_scales)`: `get_psets` (either backend) unwraps values and drops
  their measure class, so this walks the same definitions **in its order** (the TYPE's
  `HasPropertySets` first, then the occurrence's `IsDefinedBy` → `IfcRelDefinesByProperties`) and
  records `{(pset, property): factor}` with last-writer-wins exactly as `get_psets` merges — an
  occurrence `IfcReal` over a type `IfcLengthMeasure` therefore ends at factor 1.0 and does not
  inherit the type's 0.001 (pinned by the `Clearance` row of the new test); a property's or
  quantity's own `Unit` beats the project's. The docstring states the invariant that this walk and
  `get_psets` must move together.
* `_psets(prod, unit_scales)` (**`unit_scales` now required** — an omittable argument would let a
  future caller silently reintroduce #348): values still come from `_ue.get_psets` (so steplite ==
  ifcopenshell value parity is inherited, not re-derived); each value is multiplied by its factor
  when that is ≠ 1. `resolve_intent` computes `_unit_scales(f)` once per file. The three existing
  `tests/test_ifc_intent.py` callers now pass `I._unit_scales(f)` (metre synth files: identity).
* **Deliver, never withhold (review round 1, hard rule 1).** The reviewer's probe — a
  conversion-based AREAUNIT whose `ConversionFactor` is `$` — made head 6911e35 exit 3
  (`IFC intent failed: AttributeError … ValueComponent`) with NO `.rvt`, where `main` delivered.
  Now every unit read keeps `_length_scale`'s posture: `_unit_scales(f, notes)` catches a
  malformed AREAUNIT / VOLUMEUNIT per unit type → factor 1.0 + ONE intent note
  (`"AREAUNIT unreadable (AttributeError: …): pset area measures are left in file units"`,
  appended to `model.notes`); a property's own unreadable `Unit` → factor 1.0 for that property;
  and `_psets` wraps `_measure_factors` exactly like the `get_psets` call above it (a malformed
  pset graph → no factors, values verbatim). Pinned by
  `test_unreadable_unit_falls_back_and_still_resolves` (red on 6911e35, green after, both backends).
* Only `is_a(name)` / attribute reads that steplite already serves are used
  (`IfcPropertySingleValue.Unit`, `IfcPhysicalSimpleQuantity.Unit`, `IfcSIUnit.Prefix`,
  `IfcConversionBasedUnit.ConversionFactor`, `IfcMeasureWithUnit.{ValueComponent,UnitComponent}`
  all have rows) — **no steplite row was needed, nothing filed on #337.**
  `IfcNonNegativeLengthMeasure` has no CamelCase entry in steplite's typed-value table, which is
  why the lookup asks `value.is_a(cls)` per `_DIMENSIONED` row (case-insensitive on both backends)
  instead of keying the table by `value.is_a()` strings.

### /simplify pass (reuse · simplification · efficiency · altitude) — applied vs kept

Applied: `unit_scales` made required (was `=None` for three legacy test callers — a bandaid on a
correctness fix); `_unit_scales(f)` takes no echoed `length_scale` parameter (derives it from
`_length_scale` itself); one `_DIMENSIONED` table instead of two + a table-parameterised helper;
factors written unconditionally with last-writer-wins (no `pop` emulation, no dead `None` /
`IfcTypeObject` guards, no redundant `isinstance` at the use site); the test module shrank to one
assertion helper, one in-process test, ONE steplite-child parity test, one metre-file verbatim
check (was: every test parametrised over backends, a "raw mode" pinned as law, a vacuous int
assert). Kept, with reasons: (a) the name-keyed factor overlay joined onto `get_psets` output —
the alternative single typed walk would re-implement `get_psets`' value semantics
(enumerated / list / complex properties, quantity attribute order) for two backends, a larger
duplication than the join; invariant now documented in the docstring; (b) the local `_SI_PREFIX` +
`_si_factor` — the shared two-backend surface is exactly `{open, by_type, get_psets, get_type,
calculate_unit_scale, get_local_placement}`, none power-aware or single-unit; converging belongs
to the steplite/shim stream (a leaf `rvt/ifc/_units.py` both could import), not to an
`intent.py`-only PR; (c) `_length_scale` stays `calculate_unit_scale` (the parity-tested vertex
law) rather than being re-derived from `_si_factor`. Efficiency: measured by the reviewer on
`electrical-room-2500a.ifc` (14 products, 89 properties, steplite): the whole feature is ~0.6 ms
of a ~700 ms resolve; import-time delta within noise (two dict literals, no new imports).

## Re-pinned expectations — every changed number, and why it is a correction, not a loosening

`python3 tools/dev/make_ifc_fixtures.py --update-expected` → `expected: 2 re-pinned
['a_units_mm', 'b_units_feet']`; the other eight fixtures did not move. `.ifc` bytes untouched
(`--check` ok). The complete diff:

| fixture | field | was | now | why |
|---|---|---|---|---|
| `a_units_mm` | `room.info.ClearWidth` | 5800.0 | 5.8 | `IFCLENGTHMEASURE` in a MILLI METRE file × 0.001 — the same 5.8 m the wall ring spans (`walls[0]` runs x = −3.0 … 3.0 minus the 0.2 wall) |
| `a_units_mm` | `room.info.ClearDepth` | 4300.0 | 4.3 | same law |
| `a_units_mm` | `room.info.ClearHeight` | 3000.0 | 3.0 | same law; equals the pinned wall `height` 3.0 |
| `a_units_mm` | `notes[1]` | "…come back UNSCALED today (5800, not 5.8) … its own follow-up" | "…come back in METRES (5.8, not 5800) … (#348); unitless IfcReal / IfcInteger … untouched" | registry note in `make_ifc_fixtures.py` updated; the header is regenerated from it |
| `b_units_feet` | `room.info.ClearWidth` | 19.029 | 5.8 | `IFCLENGTHMEASURE` in a conversion-based FOOT file × 0.3048; the fixture authored `(6.0 − 0.2) / 0.3048` ft |
| `b_units_feet` | `room.info.ClearDepth` | 14.108 | 4.3 | same law |
| `b_units_feet` | `room.info.ClearHeight` | 9.843 | 3.0 | same law |

Nothing else in either file changed: `length_scale_m_per_unit` (0.001 / 0.3048), every
`insertion_m`, wall start/end/thickness/height, `dims_m`, the DP-1 contract (`BusRating 400.0`
is `IFCREAL`, `NumberOfCircuits 42` is `IFCINTEGER` — untouched by design), census, feeders.
`i_schema_ifc2x3` (metre file, `ClearWidth 4.8`) and the shipped `inputs/ifc/electrical-room-2500a.ifc`
(metre file: `ClearWidth 9.0 / ClearDepth 6.0 / ClearHeight 3.66`) are unchanged — scale 1.0
is a no-op, asserted by `test_metre_file_pins_are_unchanged`.

## Evidence (this VM: Linux, Python 3.11, fresh `.venv` from `scripts/cloud-setup.sh`)

New test `tests/test_ifc_intent_units.py` — hand-authored STEP text inside the test (ours; no
ifcopenshell, numpy or samples needed): a MILLI METRE project with `AREAUNIT = SQUARE_METRE`,
`VOLUMEUNIT = MILLI CUBIC_METRE`, an `INCH` conversion-based unit used as one property's and one
quantity's own `Unit`, a type object whose pset the occurrence partly overrides, and an
`IfcElementQuantity`. 20 pinned values (table in the test's `EXPECTED`). It runs on the selected
backend AND, when that is the real wheel, again in a child pinned to steplite:

* with ifcopenshell 0.8.5 installed (`uv pip install -e '.[ifc]'`):
  `tests/test_ifc_intent_units.py` → **3 passed** (in-process = ifcopenshell, + the steplite
  child parity test); wheel-less shape (`RVT_STEPLITE_FORCE=1`): **2 passed, 1 skipped**
  (in-process = steplite; the child test skips as redundant);
* stream-local set WITH the wheel — `tests/test_ifc_intent_units.py tests/test_ifc_conformance.py
  tests/test_ifc_intent.py tests/test_steplite.py tests/test_ifc_census.py
  tests/test_ifc_read_fallback.py tests/test_lazy_ifc_import.py tests/test_ifc_authoring_gate.py`
  → **114 passed, 1 xfailed** (the pre-existing #159 parity xfail in test_ifc_conformance;
  113 + 1 before the review-round test was added);
* the same forced to steplite (`RVT_STEPLITE_FORCE=1`; `test_ifc_intent_units + test_ifc_conformance
  + test_steplite + test_ifc_census`) → **45 passed, 23 skipped** (real-wheel parity legs skip);
* `tools/dev/make_ifc_fixtures.py --check` → `ok: 10 fixtures checked`; `tests/test_plugin_sync.py`
  → **9 passed**;
* `tools/sync_plugin.py` rebuilt, `--check` → "plugin in sync with source";
  `plugin/scripts/validate_plugin.py` → PASS (25 assertions); `tools/dev/check_portable_paths.py`
  → ok; `python3 tools/dev/shard_list.py --print` lists `tests/test_ifc_intent_units.py`.
* **/verify (drove the real surface):** `.venv/bin/python tools/frontdoor.py author --ifc
  tests/ifc_conformance/a_units_mm.ifc --target-version 2025 --out out/verify/mm --json` → exit 0
  in 3.4 s, delivers `a_units_mm.rvt` + `intent.json` + MANIFEST (status line `PROOF-ONLY (self-checks
  PASS …)` — the standing instance-route stamp, unchanged by this PR); `intent.json` →
  `room.roomInformation = {ClearWidth 5.8, ClearDepth 4.3, ClearHeight 3.0}` and
  `room.clear = {clearWidth_m 5.8, …, centerline_extents_m x [-3.0, 3.0]}` (was 5800 / 4300 / 3000
  under a `_m` key); `tools/rvt_validate.py out/verify/mm/a_units_mm.rvt` → `verdict: VALID (no
  errors); warnings=0` (validates 0 errors — not a load claim). `b_units_feet.ifc` resolves
  `clearWidth_m 5.7999998808` (feet rounding in the fixture); `electrical-room-2500a.ifc` unchanged
  (`9.0 / 6.0 / 3.66`).
* **/verify, review round 1:** the reviewer's malformed file (`BROKEN_IFC_TEXT` from the test,
  written to `out/verify/broken_units.ifc`) through `frontdoor.py author --ifc … --target-version
  2025` → **exit 0, `broken_units.rvt` delivered**, `intent.json.notes` carries the one
  `AREAUNIT unreadable (…)` line, `rvt_validate` → `VALID (no errors)` (head 6911e35: exit 3, no
  file). Portable paths ok 2864 (main moved); plugin re-synced, `--check` clean, validate PASS,
  `test_plugin_sync` 9 passed.

## Findings / follow-ups

* `ifcopenshell.util.unit.calculate_unit_scale` (0.8.5) and steplite's mirror both ignore the
  SQUARE_/CUBIC_ exponent of a prefixed SI area/volume unit. Nothing in the engine calls them for
  anything but LENGTHUNIT today, so no issue is filed; if the steplite stream ever serves a
  power-aware `convert_unit` + `prefixes` on the shim's `ifcopenshell.util.unit`, `intent.py`
  could drop `_SI_PREFIX` / `_si_factor` (noted for #337's owner, not filed — it would be reuse
  polish, not a defect).
* `src/rvt/frontdoor/prompt_intent.py` already builds `room.info` / `room.clear` in metres for
  the prompt route, so the two routes now agree; `src/rvt/frontdoor/ifc_out.py` writes
  `ClearWidth` from `clear["clearWidth_m"]` into a METRE file — unaffected.

## BRANCH STATE

* Branch `cam/348-pset-length-units` cut from `main` @ e5b7864, rebased onto a34d545 before the
  PR; PR #393 opened ready (not draft), `Closes #348`. Review round 1 (tech lead, head 6911e35):
  sandboxed CI PASS 1276/128s/4xf, verdict 🟡 with one required fix (malformed-unit fallback) —
  landed as the second commit on the same branch. Regime #302: GitHub check runs mean nothing; the tech-lead session runs the
  shard on the head SHA, obtains the independent review, and merges via API.
* Files: `src/rvt/ifc/intent.py` (edited), `plugin/lib/src/rvt/ifc/intent.py` (regenerated
  mirror), `tools/dev/make_ifc_fixtures.py` (one registry note),
  `tests/ifc_conformance/a_units_mm.expected.json` + `b_units_feet.expected.json` (re-pinned via
  `--update-expected`, table above), `tests/test_ifc_intent.py` (three `_psets` call sites pass
  `_unit_scales(f)`), NEW `tests/test_ifc_intent_units.py`, NEW
  `tests/ci_shard.d/348-pset-length-units.txt`, NEW `docs/inbox/ifc-pset-units.md`.
* Gates: see Evidence. Nothing staged for the viewer; no certification claim; no `.rvt` bytes
  change (the IFC reader feeds intent JSON, not container bytes).

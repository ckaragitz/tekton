# ifc-conformance — owned IFC fixtures with pinned resolver expectations (issue #154)

Stream: `ifc-conformance` (eng #154, cloud session, 2026-08-09). Charter = issue #154
(Refs #108 wave 2, PG3). Territory: NEW `tools/dev/make_ifc_fixtures.py`, NEW
`tests/ifc_conformance/**`, NEW `tests/test_ifc_conformance.py`, one line in
`tests/ci_shard.txt`, this record. Read-only use of `src/rvt/ifc/**` — no resolver or
steplite change (eng #152 holds `intent.py` / `steplite.py` this wave).

## What was built

* **`tools/dev/make_ifc_fixtures.py`** — a stdlib-only, deterministic ISO-10303-21 text
  writer in the style of `rvt.frontdoor.ifc_out._W` (`_W.add(text) -> '#n'`, `_f`, `_s`,
  md5-seeded 22-char GlobalIds, pinned `FILE_NAME` stamp) plus a small `Model` builder
  (project/site/building scaffolding, storeys with real `IfcLocalPlacement`s, box solids as
  `IfcTriangulatedFaceSet` (IFC4) or `IfcFacetedBrep` (IFC2X3), `IfcExtrudedAreaSolid`
  bodies, psets incl. `IfcLengthMeasure` values, type assignment, containment/aggregation)
  and **nine registered fixtures** `@fixture(name, pins, notes, parity_xfail)`. Every byte
  of every fixture comes from parameters in the script — nothing is read from, let alone
  copied out of, `samples/ vendor/ extracted/ usecases/ inputs/` (hard rule 3). CLI:
  * *(default)* write `tests/ifc_conformance/*.ifc`;
  * `--check` drift gate (committed `.ifc` == generator output, no stray/missing files, every
    fixture has its `.expected.json`) → exit 1 on any;
  * `--update-expected` re-pins `<name>.expected.json` from TODAY's resolver under the
    forced steplite shim (the deliberate act a behaviour-changing PR performs);
  * `--list` fixture table; `--resolve` (internal) = the one place the engine is imported:
    `summarize(path)` projects `resolve_intent()` onto the pinned summary and both the test
    and `--update-expected` call it in a child interpreter so the backend is chosen by the
    environment alone (`RVT_STEPLITE_FORCE=1` → shim first, via `rvt.ifc._fallback`).
* **`tests/ifc_conformance/`** — 9 × (`<name>.ifc`, `<name>.expected.json`). Header of every
  `.ifc`: `/* hand-authored by tekton -- no third-party bytes. written by
  tools/dev/make_ifc_fixtures.py (fixture <name>) -- regenerate, never edit. pins: … */`
  (ASCII `--`: ISO-10303-21 text is basic-alphabet only, so the em dash of the issue text is
  spelled `--`; real ifcopenshell and steplite both accept the comment — verified, log clean).
* **`tests/test_ifc_conformance.py`** (in `tests/ci_shard.txt`) — 30 tests:
  registry == committed files; `make_ifc_fixtures.py --check` exit 0; generator deterministic;
  per-fixture hygiene (< 20 KB, ASCII, LF, portable lowercase name, header mark, FILE_SCHEMA,
  expected doc well-formed, any `parity_xfail` cites `#NNN`); **steplite summary == pinned
  expectation** per fixture (one child interpreter for all nine, `RVT_STEPLITE_FORCE=1`,
  asserts `backend == "steplite"` so green means green-on-the-shim even where the wheel is
  installed; failure prints a unified diff + the re-pin instruction); **real-ifcopenshell
  parity == steplite** per fixture when a real ifcopenshell is importable (skips otherwise),
  known divergences `xfail(strict=True)` with the issue number so the fixing PR must flip them.

## The fixtures and what they pin (today's behaviour, honestly)

| fixture | bytes | pins | today's notable behaviour pinned (issue that will flip it) | parity |
|---|---:|---|---|---|
| `a_units_mm` | 6082 | `IfcSIUnit` MILLI METRE → scale 0.001; 6×4.5 m room shell + wall panel authored in mm | scale 0.001; walls/insertion back in metres (DP-1 at [1.0, 2.15, 1.3]); `RoomInformation` `IfcLengthMeasure`s come back **unscaled** (5800) — informational, pinned as-is | = |
| `b_units_feet` | 6553 | `IfcConversionBasedUnit` FOOT (0.3048 via `IfcMeasureWithUnit`) | scale 0.3048; identical metres geometry to (a) | = |
| `c_storeys_relative_placement` | 5627 | building rotated 90° + offset (10,5); storeys 0 / 4 m; products on NON-identity local placements with local vertices | levels L1 Ground 0 / L2 First 4.0; T-1 → L1 at [9,7,0], LP-2 → L2 at [9.5,7.9,5.4], `position_source = placement-chain + local geometry`; feeder T-1→LP-2 `secondary`; LP-2 "lighting panel 208Y/120" classifies `receptacle_panelboard` (voltage rule precedes name rule — today's order) (#156 adds the base-level mapping expectation) | = |
| `d_wall_opening_door` | 5448 | `IfcWallStandardCase` extrusion + `IfcOpeningElement`/`IfcRelVoidsElement` + `IfcDoor`/`IfcRelFillsElement` + one tessellated panel | wall = equipment kind `wall`, `has_body false`, insertion = placement origin [1,2,0] (#152 reads the extrusion; #157 makes it a WallRun with the opening); room null; door absent under steplite | **xfail #155** (IfcDoor dropped by steplite's IfcProduct closure, kept by ifcopenshell as `proxy`/recorded) |
| `e_space_in_storey` | 5872 | `IfcSpace` aggregated in L2 (3.5 m); RP-2 contained in the SPACE, LP-1 in L1 | RP-2 gets `level L2` through space→storey; the space itself appears nowhere in the intent (#158) | = |
| `f_board_type_psets` | 6469 | board + `IfcElectricDistributionBoardType` (`IfcRelDefinesByType`), occurrence `PanelSchedule` over a type-level one, `Pset_ManufacturerTypeInformation` on the type, MSB switchboard in file | `typeName` from the type; Mounting SURFACE (occurrence wins) + NumberOfCircuits 42 (from type); Manufacturer/ModelLabel folded into the contract; feeders UTILITY→MSB, MSB→DP-1; MSB → `house` family plan | = |
| `g_mep_recorded_kinds` | 5634 | `IfcTransformer` VOLTAGE + pad, `IfcCableCarrierSegment` CABLETRAYSEGMENT with `conduit_msb_t1`, `IfcDiscreteAccessory` BRACKET strut | kinds transformer / conduit_run / support; tray + strut `recorded`; conduit run corroboration item listed; feeder root MSB external, edge `primary` | = |
| `h_mapped_item_reuse` | 5680 | one `IfcRepresentationMap` reused by 3 panels via `IfcMappedItem` + `IfcCartesianTransformationOperator3D` (2 translated, 1 rotated) | three distinct insertions [1,4.1,1.4] / [2.5,4.1,1.4] / [4.9,2,1.4]; LP-3 front normal rotated to +X (yaw 90) | = |
| `i_schema_ifc2x3` | 9666 | `FILE_SCHEMA(('IFC2X3'))`, `IfcFacetedBrep` bodies, proxy room shell with CompositionType, `IfcElectricDistributionPoint` panel | schema reported IFC2X3; room shell 4 walls read from breps; steplite: equipment **empty** (no 2x3 class row); ifcopenshell: DP-1 as kind `proxy`, recorded, floor (#159 classifies it) | **xfail #159** |

The pinned summary per fixture (`expected`): schema, project, `length_scale_m_per_unit`,
levels (id/name/elevation/elevation_from_placement), equipment (tag, name, ifcClass,
predefinedType, kind, disposition, level, typeName, has_body, insertion_m, front_normal,
yaw_deg, dims w/d/h, mounting, position_source, fed_from, contract subset, item names),
other_products, room (walls with start/end/thickness/height/base/openings, doors, info),
feeders, conduit_runs, family_plans (tag/kind/status/catalog), audit subset. Numbers rounded
to 3 dp (scale 6 dp, yaw 1 dp) — the fixtures are authored on round values so no pin sits on
a rounding boundary. Census key: to be added by #153 (`summarize()` is the one place).

## Evidence

* Both backends open all nine with a clean log (real ifcopenshell 0.8.x `get_log()` empty;
  steplite parses every record incl. the classes outside its schema subset). Product closures
  differ exactly and only where predicted: (d) `IfcDoor`, (i) `IfcElectricDistributionPoint`.
* `tests/test_ifc_conformance.py` — **with** ifcopenshell (`.venv`, `.[test]`+wheel):
  `28 passed, 2 xfailed in 1.71s`; **without** (`uv venv .venv-noifc` + `.[test]` only, the CI
  shape): `21 passed, 9 skipped in 1.01s` (the 9 = parity, skipped by design). `--durations=5`:
  1.22 s real-backend child, 0.32–0.87 s steplite child, 0.07 s `--check`; whole module ≈ 1–2 s
  (target < 30 s).
* Stream gates: `tests/test_ifc_conformance.py tests/test_steplite.py tests/test_ifc_intent.py -q -rs`
  with ifcopenshell → `64 passed, 2 xfailed in 11.33s`. Without ifcopenshell the same command
  **errors at collection in `test_ifc_intent.py`** (`No module named 'ifcopenshell.guid'`) —
  pre-existing on `main` @ 311dee9 and order-dependent (`test_ifc_intent.py` alone: `1 skipped`;
  `test_ifc_conformance.py test_steplite.py` without it: `25 passed, 16 skipped in 1.12s`);
  not this stream's file → filed **#320**.
* `python3 tools/dev/make_ifc_fixtures.py --check` → `ok: 9 fixtures checked`; 
  `python3 tools/dev/check_portable_paths.py` → `ok: 2791 tracked paths are portable`;
  `tools/sync_plugin.py --check` → `plugin in sync with source` (nothing under `src/` touched).
* /verify (front door consumes the fixtures end-to-end on the shim):
  `RVT_STEPLITE_FORCE=1 .venv/bin/python tools/frontdoor.py author --ifc tests/ifc_conformance/f_board_type_psets.ifc --out out/verify/f_board_type_psets --json`
  → exit 0, status `PROOF-ONLY (self-checks PASS…)`, `errors: []`, `f_board_type_psets.rvt`
  delivered; MANIFEST: `equipment (2): switchboard×1, distribution_panelboard×1`,
  `created: 0 walls, 2 equipment instances, 2 loaded families`, families `Switchboard MSB 2000A
  480Y/277` (house) + `Distribution Panelboard DP-1 480Y/277 400A MB 42sp` (PRL2X).
  Same for `a_units_mm.ifc` → `room 'Electrical Room room shell': 4 walls (0 synthesized), 0
  doors`, `equipment (1): distribution_panelboard×1`, `created: 4 walls, 1 equipment instances,
  1 loaded families`. `tools/rvt_validate.py` on both delivered `.rvt`: `verdict: VALID (no
  errors); warnings=1` (the known DataStorage decoder-gap warning), JSON `ok: true`, 0 error
  findings. (Validates 0 errors — not a "loads" claim, rule 4.)

## Findings (pinned, cited, not fixed here)

1. `IfcLengthMeasure` pset values are not unit-scaled by the resolver (mm file → `ClearWidth
   5800`). Only informational fields are affected today (`RoomInformation` is echoed, never
   built from), so it is pinned with a note rather than filed; #153's census/#158's space
   intake should decide whether pset measures get converted.
2. `_classify_equipment` tests the ≤ 240 V receptacle rule before the `lighting|lp-` name
   rule, so an "LP-n lighting panel 208Y/120 V" is a `receptacle_panelboard` (fixtures c, h).
   Pinned as today's order; whoever changes it re-pins deliberately.
3. #155 / #159 divergences reproduced minimally by (d) and (i) — those issues now have a
   one-line checkable DONE: their PR turns the strict xfail into a pass (pytest will fail the
   suite on XPASS until the `parity_xfail` entry is removed and `--update-expected` re-run).
4. #320 (new): `test_ifc_intent.py` collection is order-dependent without the wheel.

## How later issues use this

* Behaviour change in the resolver/steplite → run the module; the failing fixture prints a
  unified diff; if intended: `python3 tools/dev/make_ifc_fixtures.py --update-expected`,
  commit the `.expected.json` diff, and edit that fixture's `notes` / `parity_xfail` in the
  registry (the note citing your issue is the line to delete).
* New conformance case → add a `@fixture(...)` builder (parameters only, never pasted entity
  lines), run the script, `--update-expected`, commit all three (script, `.ifc`, `.expected.json`).

## BRANCH STATE

* Branch `cam/154-ifc-conformance-fixtures` from `main` @ 311dee9; PR opened ready (not
  draft) with `Closes #154`; regime #302: checks on GitHub are meaningless, the tech-lead
  session runs the shard on the head SHA and merges via API.
* Files added: `tools/dev/make_ifc_fixtures.py`, `tests/test_ifc_conformance.py`,
  `tests/ifc_conformance/{a_units_mm,b_units_feet,c_storeys_relative_placement,d_wall_opening_door,e_space_in_storey,f_board_type_psets,g_mep_recorded_kinds,h_mapped_item_reuse,i_schema_ifc2x3}.{ifc,expected.json}`,
  `docs/inbox/ifc-conformance.md`. Edited: `tests/ci_shard.txt` (+1 line).
* Not touched: `src/**` (sync `--check` clean), `samples/ vendor/ extracted/`, workflows, hot files.
* Gates: see Evidence (module green with and without ifcopenshell; `--check` clean; portable
  paths clean). Nothing staged for the viewer; no certification claim.
* Follow-ups filed: #320. Open questions: none blocking; findings 1–2 are notes for #153/#158
  and the classifier's owner, not new issues (searched: #152 #153 #155–#159 cover the rest).

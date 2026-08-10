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
  * *(default)* write `tests/ifc_conformance/*.ifc` and refresh each `.expected.json`'s
    registry-derived header (pins / notes / parity_xfail) without touching its `expected` body;
  * `--check` drift gate (committed `.ifc` == generator output, every fixture has its
    `.expected.json` **and its header matches the registry**, no stray files) → exit 1 on any
    — so a note or xfail edited in the script but not re-committed turns CI red instead of
    leaving a stale JSON;
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
* **`tests/test_ifc_conformance.py`** (in `tests/ci_shard.txt`) — 29 tests:
  `make_ifc_fixtures.py --check` exit 0 (the CLI drift gate); generator deterministic;
  per-fixture hygiene (< 20 KB, ASCII, LF, portable lowercase name, header mark, FILE_SCHEMA
  taken from the fixture's own `Model.schema`, any `parity_xfail` cites `#NNN`); **steplite
  summary == pinned expectation** per fixture (one child interpreter for all nine,
  `RVT_STEPLITE_FORCE=1`, the module fixture asserts the child really ran `steplite` so green
  means green-on-the-shim even where the wheel is installed; failure prints a unified diff +
  the re-pin instruction); **real-ifcopenshell parity == steplite** per fixture when a real
  ifcopenshell is importable (skips otherwise), known divergences `xfail(strict=True)` with the
  issue number so the fixing PR must flip them.

## The fixtures and what they pin (today's behaviour, honestly)

| fixture | bytes | pins | today's notable behaviour pinned (issue that will flip it) | parity |
|---|---:|---|---|---|
| `a_units_mm` | 6082 | `IfcSIUnit` MILLI METRE → scale 0.001; 6×4.5 m room shell + wall panel authored in mm | scale 0.001; walls/insertion back in metres (DP-1 at [1.0, 2.15, 1.3]); `RoomInformation` `IfcLengthMeasure`s come back **unscaled** (5800) — informational, pinned as-is | = |
| `b_units_feet` | 6553 | `IfcConversionBasedUnit` FOOT (0.3048 via `IfcMeasureWithUnit`) | scale 0.3048; identical metres geometry to (a) | = |
| `c_storeys_relative_placement` | 5627 | building rotated 90° + offset (10,5); storeys 0 / 4 m; products on NON-identity local placements with local vertices | levels L1 Ground 0 / L2 First 4.0; T-1 → L1 at [9,7,0], LP-2 → L2 at [9.5,7.9,5.4], `position_source = placement-chain + local geometry`; feeder T-1→LP-2 `secondary`; LP-2 "lighting panel 208Y/120" classifies `receptacle_panelboard` (voltage rule precedes name rule — today's order) (#156 adds the base-level mapping expectation) | = |
| `d_wall_opening_door` | 5448 | `IfcWallStandardCase` extrusion + `IfcOpeningElement`/`IfcRelVoidsElement` + `IfcDoor`/`IfcRelFillsElement` + one tessellated panel | **re-pinned in this PR after #152 landed (PR #327)**: wall = equipment kind `wall`, `has_body true`, insertion = footprint centre [4,2,0] via the (1,2,0) placement, dims 6.0×0.2×3.0, `placement-chain + local geometry`, item name null (unstyled extrusion); still not a WallRun and room null (#157); door absent under steplite | **xfail #155** (IfcDoor dropped by steplite's IfcProduct closure, kept by ifcopenshell as `proxy`/recorded) |
| `e_space_in_storey` | 5872 | `IfcSpace` aggregated in L2 (3.5 m); RP-2 contained in the SPACE, LP-1 in L1 | RP-2 gets `level L2` through space→storey; the space itself appears nowhere in the intent (#158) | = |
| `f_board_type_psets` | 6469 | board + `IfcElectricDistributionBoardType` (`IfcRelDefinesByType`), occurrence `PanelSchedule` over a type-level one, `Pset_ManufacturerTypeInformation` on the type, MSB switchboard in file | `typeName` from the type; Mounting SURFACE (occurrence wins) + NumberOfCircuits 42 (from type); Manufacturer/ModelLabel folded into the contract; feeders UTILITY→MSB, MSB→DP-1; MSB → `house` family plan | = |
| `g_mep_recorded_kinds` | 5634 | `IfcTransformer` VOLTAGE + pad, `IfcCableCarrierSegment` CABLETRAYSEGMENT with `conduit_msb_t1`, `IfcDiscreteAccessory` BRACKET strut | kinds transformer / conduit_run / support; tray + strut `recorded`; conduit run corroboration item listed; feeder root MSB external, edge `primary` | = |
| `h_mapped_item_reuse` | 5680 | one `IfcRepresentationMap` reused by 3 panels via `IfcMappedItem` + `IfcCartesianTransformationOperator3D` (2 translated, 1 rotated) | three distinct insertions [1,4.1,1.4] / [2.5,4.1,1.4] / [4.9,2,1.4]; LP-3 front normal rotated to +X (yaw 90) | = |
| `i_schema_ifc2x3` | 9666 | `FILE_SCHEMA(('IFC2X3'))`, `IfcFacetedBrep` bodies, proxy room shell with CompositionType, `IfcElectricDistributionPoint` panel | schema reported IFC2X3; room shell 4 walls read from breps; steplite: equipment **empty** (no 2x3 class row); ifcopenshell: DP-1 as kind `proxy`, recorded, floor (#159 classifies it) | **xfail #159** |

The pinned summary per fixture (`expected`): schema, project, `length_scale_m_per_unit`,
levels (id/name/elevation/elevation_from_placement), equipment (tag, name, ifcClass,
predefinedType, kind, disposition, level, typeName, has_body, insertion_m, front_normal,
yaw_deg, every `dims_m` key, mounting, position_source, fed_from, the whole non-private
contract, item names),
other_products, room (walls with start/end/thickness/height/base/openings, doors, info),
feeders, conduit_runs, family_plans (tag/kind/status/catalog), audit subset. Numbers rounded
to 3 dp (scale 6 dp, yaw 1 dp) — the fixtures are authored on round values so no pin sits on
a rounding boundary. Census key: to be added by #153 (`summarize()` is the one place).

## Evidence

* Both backends open all nine with a clean log (real ifcopenshell 0.8.x `get_log()` empty;
  steplite parses every record incl. the classes outside its schema subset). Product closures
  differ exactly and only where predicted: (d) `IfcDoor`, (i) `IfcElectricDistributionPoint`.
* `tests/test_ifc_conformance.py` (final head, after /simplify) — **with** ifcopenshell (`.venv`,
  `.[test]`+wheel): `27 passed, 2 xfailed in 1.20s`; **without** (`uv venv .venv-noifc` +
  `.[test]` only, the CI shape): `20 passed, 9 skipped in 0.46s` (the 9 = parity, skipped by
  design). `--durations=5`: ≈0.8 s real-backend child, 0.30 s steplite child, 0.07 s `--check`;
  whole module ≈ 0.5–1.2 s (target < 30 s).
* Stream gates: `tests/test_ifc_conformance.py tests/test_steplite.py tests/test_ifc_intent.py -q -rs`
  with ifcopenshell → `63 passed, 2 xfailed in 9.51s`. Without ifcopenshell the same command
  **errors at collection in `test_ifc_intent.py`** (`No module named 'ifcopenshell.guid'`) —
  pre-existing on `main` @ 311dee9 and order-dependent (`test_ifc_intent.py` alone: `1 skipped`;
  `test_ifc_conformance.py test_steplite.py` without it: `24 passed, 16 skipped in 1.15s`);
  not this stream's file → filed **#320**.
* `python3 tools/dev/make_ifc_fixtures.py --check` → `ok: 9 fixtures checked` (and the header
  guard demonstrably fires: an in-memory edit of one fixture's `notes` makes `check()` return
  `drift: d_wall_opening_door.expected.json header is stale vs the registry`);
  `python3 tools/dev/check_portable_paths.py` → `ok: 2792 tracked paths are portable`;
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
   built from); pinned with a note hung on **#153** (census / measure handling).
2. `_classify_equipment` tests the ≤ 240 V receptacle rule before the `lighting|lp-` name
   rule, so an "LP-n lighting panel 208Y/120 V" is a `receptacle_panelboard` (fixtures c, h).
   Pinned as today's order; filed **#331** (XS: bug vs intended) and cited in both notes.
3. #155 / #159 divergences reproduced minimally by (d) and (i) — those issues now have a
   one-line checkable DONE: their PR turns the strict xfail into a pass (pytest will fail the
   suite on XPASS until the `parity_xfail` entry is removed and `--update-expected` re-run).
4. #320 (new): `test_ifc_intent.py` collection is order-dependent without the wheel.

## /simplify pass (4 review angles) — applied vs deliberately kept

Applied: registry↔JSON header drift now guarded by `--check` and refreshed by the default run
(was split-brain); FILE_SCHEMA check reads the fixture's `Model.schema` (was name-keyed); `;` in
`pins` is an assertion like its neighbours (was silently rewritten); the whole non-private
contract and every `dims_m` key are pinned (was an allow-list that #152/#157 would have had to
edit); `Model.board()` folds the 7× repeated panel triple; dead `_enum`, the no-op `_f` branch,
never-varied kwargs (`project`, `site_axis`, `axis(z=)`, `extrusion(position=)`,
`product(description=)`, `room_shell(name/info/cls)`, `storey(axis=)`, `--out`, `--python`)
removed; `spatial()` folded into `Model(...)`; the module fixtures strip/assert `backend` once;
the redundant registry-vs-files test dropped (`check()` covers it). Kept on purpose: the
~45 lines of STEP primitives mirrored from `ifc_out` (`_W/_f/_s/_guid/box_pts`) — importing them
would execute `rvt.frontdoor` (9 engine modules, mutates `sys.path` via `rvt.ifc`) at generator
import and make fixture bytes a function of another stream's private helpers; if a third stdlib
STEP writer appears, the home is a side-effect-free `src/rvt/ifc/stepwrite.py` (separate PR).
Kept: `summarize()` as an explicit projection rather than a deny-listed `intent_to_json` (the
full JSON carries catalog facts, geometry boxes and prose notes that would re-pin in unrelated
PRs; the DONE names an allow-list). Kept: the local "real ifcopenshell importable" predicate —
consolidating the three test-side copies into a `tests/` helper touches
`tests/test_ifc_read_fallback.py` (another stream's file); noted for #155's steplite pass.

## How later issues use this

* Behaviour change in the resolver/steplite → run the module; the failing fixture prints a
  unified diff; if intended: `python3 tools/dev/make_ifc_fixtures.py --update-expected`,
  commit the `.expected.json` diff, and edit that fixture's `notes` / `parity_xfail` in the
  registry (the note citing your issue is the line to delete).
* New conformance case → add a `@fixture(...)` builder (parameters only, never pasted entity
  lines), run the script, `--update-expected`, commit all three (script, `.ifc`, `.expected.json`).

## BRANCH STATE

* Branch `cam/154-ifc-conformance-fixtures` from `main` @ 311dee9, rebased onto f0bde6a (#309) again onto ba9e439 (#319 + #323) and onto 950d4b6 (#327 = #152, clean; `tests/ci_shard.txt` conflicts = keep both, my line last); PR opened ready (not
  draft) with `Closes #154`; regime #302: checks on GitHub are meaningless, the tech-lead
  session runs the shard on the head SHA and merges via API.
* Files added: `tools/dev/make_ifc_fixtures.py`, `tests/test_ifc_conformance.py`,
  `tests/ifc_conformance/{a_units_mm,b_units_feet,c_storeys_relative_placement,d_wall_opening_door,e_space_in_storey,f_board_type_psets,g_mep_recorded_kinds,h_mapped_item_reuse,i_schema_ifc2x3}.{ifc,expected.json}`,
  `docs/inbox/ifc-conformance.md`. Edited: `tests/ci_shard.txt` (+1 line).
* Not touched: `src/**` (sync `--check` clean), `samples/ vendor/ extracted/`, workflows, hot files.
* Gates: see Evidence (module green with and without ifcopenshell; `--check` clean; portable
  paths clean). Nothing staged for the viewer; no certification claim.
* **Re-pin after #152 (PR #327) merged under this branch** — the designed workflow, exercised once
  before landing: rebased onto main @ 950d4b6 (clean); the module went `1 failed` on exactly
  `d_wall_opening_door`; `--update-expected` re-pinned that one file and nothing else; every
  flipped field is #152's doing (W-1: `has_body` false→true, `insertion_m` [1,2,0]→[4,2,0],
  `dims_m` {}→{w 6.0, d 0.2, h 3.0, footprint_area 1.2}, `position_source` placement-chain →
  placement-chain + local geometry, `items` []→[null]); DP-1 and every other fixture unchanged;
  parity: still exactly the two strict xfails (#155: under real ifcopenshell the door now also
  has its 0.9×0.05×2.1 body read, W-1/DP-1 identical across backends; #159 unchanged), no XPASS.
  Notes updated (#152 cited as landed; a→#153; c/h→#331); `.ifc` bytes untouched. Gates on the
  re-pinned head: `--check` ok 9/9; module 27 passed / 2 xfailed with the wheel, and
  `test_ifc_conformance + test_steplite + test_ifc_intent` **without** the wheel now
  `27 passed, 18 skipped` (#327 also fixed #320); portable paths ok 2801; plugin in sync.
* Follow-ups filed: #320 (since fixed by #327), #331. Open questions: none blocking.

---

## eng #331 — 2026-08-10: an `LP-n … lighting panel` at 208Y/120 V is a lighting panelboard (finding 2 resolved as a bug, option (a))

Stream: eng #331 (cloud engineer session started by the tech-lead session; issue #331, Refs #154).
Territory used: `src/rvt/ifc/intent.py::_classify_equipment` only (+ its `plugin/lib` mirror via
`tools/sync_plugin.py`), the two fixture `notes` in `tools/dev/make_ifc_fixtures.py`, the two
re-pinned `tests/ifc_conformance/*.expected.json` (through `--update-expected`, never by hand),
NEW `tests/test_ifc_classify_equipment.py` + `tests/ci_shard.d/331-lp-lighting-classify.txt`,
this section. Base: `main` @ 2b87024 (#407; after #393 / #400 / #405 touched `intent.py` nearby).

**Decision: bug, not intended.** Three voices already said an LP-tagged / lighting-named board is
a lighting panelboard whatever its voltage: the prompt route (`prompt_to_intent("a 100 A 208Y/120 V
lighting panel LP-1")` → `LP-1 lighting_panelboard 208Y/120 V`), the family the mapper then builds
(`Lighting Panelboard LP-1 208Y/120 100A MLO 42sp`, PRL1X — the 208 V catalog member is chosen by
voltage independently of the kind), and the fixture author's own names. Only the resolver's rule
*order* disagreed: `receptacle|appliance` **or ll ≤ 240 V** was one test, evaluated before
`lighting|lp-`, so the voltage heuristic overrode explicit text. 208Y/120 lighting panels are
ordinary (LED lighting on 120 V circuits); voltage is a fallback for boards whose text says
nothing, not evidence against what the text says.

**The change.** The panelboard branch of `_classify_equipment` (`IfcElectricDistributionBoard`,
after the untouched switchboard test) is now ONE plain function in the same module,
`panelboard_flavour(hay, *, ll, bus, mains) -> kind` — extracted so that whoever labels a board
without an IFC product in hand (the rvt→ifc extractor, #412) calls *the* rule instead of keeping a
copy of it (the /simplify altitude review's point; the #355 `carrier_for_param` pattern).
`_classify_equipment` builds `hay` / reads the contract exactly as before and delegates. Inside it:
explicit role evidence first, heuristics second, each group in its old internal order —
1. `receptacle|appliance|rp-` in name/description/object type/tag → `receptacle_panelboard`
   (`rp-` is new: the receptacle twin of the existing `lp-` / `dp-` prefixes; no tracked file has it);
2. `lighting|lp-` → `lighting_panelboard`;
3. `dp-` (our third tag prefix) → `distribution_panelboard`;
4. `ll ≤ 240 V` → `receptacle_panelboard` (was fused into 1);
5. `BusRating ≤ 225` and MLO ("lugs") → `lighting_panelboard` (was fused into 2);
6. the bare word `distribution`, or `BusRating ≥ 250` → `distribution_panelboard` (still last);
7. else `panelboard`.
A receptacle/appliance *word* still beats an `LP-` *prefix* (rule 1 before 2, as today), which is
what keeps `inputs/ifc/electrical-room-2500a.ifc`'s `LP-4 - receptacle / appliance panelboard,
208Y/120 V` and every Revit-exported `M_Lighting and Appliance Panelboard - 208V/480V …` (rme) a
`receptacle_panelboard` — pinned as today's reading; whether that NEC generic phrase should count as
role evidence at all (the prompt route reads the same words as *lighting*) is filed as **#414**, a
decision for both classifiers at once, not patched here. `dp-` **was** promoted (rule 3) after the
altitude review reproduced the same self-disagreement #331 fixes for LP on the prompt→ifc→rvt path:
`route.py run --output ifc --prompt "… a 400 A 208Y/120 V distribution panel DP-1 and a 100 A
208Y/120 V lighting panel LP-1"` writes `intent.json` = `DP-1 distribution_panelboard, LP-1
lighting_panelboard`, and re-resolving the emitted `prompt_intent.ifc` gave `DP-1
receptacle_panelboard, LP-1 receptacle_panelboard` on the old order → now `DP-1
distribution_panelboard, LP-1 lighting_panelboard` (measured both ways on this head). The bare word
`distribution` deliberately stays **below** the voltage rule: it is IEC's generic name for *any*
board, so a 230 V `Distribution Board DB-1` remains a branch (`receptacle_`) panel rather than
silently becoming a feeder panel — pinned both ways in the new test. No tracked board carries `dp-`
at ≤ 240 V (rme's `MDP-n` are 480 V and say "Appliance" first), so the snapshot below is unchanged
by the promotion.

**Re-pinned expectations — every changed value, old → new, and why** (`python3
tools/dev/make_ifc_fixtures.py --update-expected` → `expected: 2 re-pinned
['c_storeys_relative_placement', 'h_mapped_item_reuse']`; `.ifc` bytes untouched — `git diff
tests/ifc_conformance/*.ifc` empty; the notes live only in the JSON header):

| fixture | path in `expected` | old | new | reason |
|---|---|---|---|---|
| `c_storeys_relative_placement` | `equipment[LP-2].kind` | `receptacle_panelboard` | `lighting_panelboard` | **correction**: name "LP-2 lighting panel 208Y/120 V" + tag `LP-2`; rule 2 now fires before the 208 V fallback |
| `c_storeys_relative_placement` | `family_plans[LP-2].kind` | `receptacle_panelboard` | `lighting_panelboard` | follows the equipment kind (plan kind = equipment kind; catalog/variant unchanged: eaton/pow-r-line-panelboards, resolved) |
| `c_storeys_relative_placement` | `notes[1]` ("#331: LP-2 is named a lighting panel but classifies receptacle… today's order, pinned") | present | removed | the note existed to cite this issue; the pin is now the intended value |
| `h_mapped_item_reuse` | `equipment[LP-1].kind`, `[LP-2].kind`, `[LP-3].kind` | `receptacle_panelboard` ×3 | `lighting_panelboard` ×3 | **correction**, same rule: "LP-n lighting panel 208Y/120 V", tags `LP-1..3` |
| `h_mapped_item_reuse` | `family_plans[LP-1..3].kind` | `receptacle_panelboard` ×3 | `lighting_panelboard` ×3 | follows the equipment kind; status/catalog unchanged |
| `h_mapped_item_reuse` | `notes[1]` ("#331: the LP-n lighting panels at 208Y/120 V classify receptacle… today's order, pinned") | present | removed | as above |

Nothing else in either file changed (levels, insertions, fronts, dims, contract, feeders, census
identical); no other fixture re-pinned; `e_space_in_storey` (RP-2 receptacle 208 V →
`receptacle_panelboard`, LP-1 lighting 480 V → `lighting_panelboard`) is the standing control and
did not move. This is a tightening, not a loosening: the fixtures now pin the value the issue
decided is right, and the notes that flagged the old value as provisional are gone.

**No other classification moved — measured, not assumed.** A snapshot script classified every
`IfcElectricDistributionBoard` in every tracked `.ifc` (25 files: `inputs/`, `usecases/`,
`plugin/examples/`, `plugin/skills/*/examples/`, `experiments/**` incl. the Revit-exported
`rme_QUARANTINED.ifc` with 25 boards, and the 10 fixtures) before and after, under **both**
backends: `changed rows: 4 of 111` on real ifcopenshell 0.8.5 and `4 of 111` on the forced steplite
shim — exactly c/LP-2 and h/LP-1..3, `receptacle_panelboard → lighting_panelboard`, nothing else
(rme's `LP-1 … M_Lighting and Appliance Panelboard - 480V` stays receptacle via "appliance";
chicago-plenum `B-LQ1/B-LR1/B-SLQ1` stay receptacle via voltage; every DP/MSB/PANEL-A unchanged).

**Evidence (both backends; `.venv` = `.[test]` + the `.[ifc]` wheel, steplite forced with
`RVT_STEPLITE_FORCE=1`):**
* `tests/test_ifc_classify_equipment.py` (NEW, backend-free stub product, 16 tests: the #331 case,
  prefix-only LP-/RP-/DP- at the "wrong" voltage, word-beats-prefix LP-4, the rme naming (pinned,
  #414), the four heuristic fall-throughs, `Distribution Board DB-n` at 230 V vs 480 V, role words in
  ObjectType/Description, switchboard precedence, and `panelboard_flavour` callable without a
  product): `16 passed in 0.09s` (wheel) / `16 passed in 0.09s` (forced steplite); against the *old*
  `intent.py` (stash check) `6 failed, 10 passed` — exactly the LP-2 / LP-1-prefix / RP-1-prefix /
  DP-1-prefix / ObjectType cases + the missing helper: the test pins the change, not a tautology.
  Listed in the shard via `tests/ci_shard.d/331-lp-lighting-classify.txt` (numpy only, no samples,
  no wheel).
* Stream-local (final head): `RVT_SKIP_LARGE=1 pytest tests/test_ifc_conformance.py
  tests/test_ifc_classify_equipment.py tests/test_ifc_intent.py tests/test_steplite.py -q -rs` →
  **with ifcopenshell** `104 passed, 1 xfailed in 7.50s` (the xfail = #159, unchanged; parity
  real == steplite holds on c and h with the new kinds); **forced steplite** `53 passed, 25 skipped
  in 1.10s` (the 25 = `test_ifc_intent.py` module skip + steplite-vs-real comparisons, by design).
* `python3 tools/dev/make_ifc_fixtures.py --check` → `ok: 10 fixtures checked`; `--update-expected`
  re-run on the final head → `expected: unchanged` (the helper extraction and the `dp-` promotion
  move no fixture).
* Front door on the flipped fixtures, both backends (`tools/frontdoor.py author --ifc
  tests/ifc_conformance/<fx>.ifc --out out/verify331/<fx>-<backend> --json`): all four runs
  `exit 0`, `ok: true`, `errors: []`, status `PROOF-ONLY (self-checks PASS…)` (the standing
  open-cell label, rule 1 — delivered); `intent.json` kinds: h → `LP-1/LP-2/LP-3
  lighting_panelboard`, c → `T-1 transformer, LP-2 lighting_panelboard` on real **and** steplite;
  MANIFEST: `equipment (3): lighting_panelboard×3` / `equipment (2): transformer×1,
  lighting_panelboard×1`, families `Lighting Panelboard LP-n 208Y/120 100A MLO 42sp (eaton/
  pow-r-line-panelboards PRL1X; ok=True)`, `created: 0 walls, 3 equipment instances, 3 loaded
  families`; `tools/rvt_validate.py` on each delivered `.rvt` → `verdict: VALID (no errors);
  warnings=1` (the known DataStorage decoder-gap warning). Validates 0 errors — not a "loads in
  Revit" claim (rule 4); nothing staged for the viewer. Re-run on the final head (helper + `dp-`):
  identical kinds / families / verdicts on all four.
* /verify, prompt→ifc→rvt on the final head: the `route.py run --output ifc` file above fed back
  through `frontdoor.py author --ifc out/verify331/dp208/prompt_intent.ifc` → exit 0, `ok true`,
  `errors []`, kinds `DP-1 distribution_panelboard, LP-1 lighting_panelboard`, families `Distribution
  Panelboard DP-1 208Y/120 400A MB 42sp` + `Lighting Panelboard LP-1 208Y/120 100A MLO 42sp` (both
  PRL1X), `created: 4 walls, 2 equipment instances, 2 loaded families`, `rvt_validate` → `VALID (no
  errors); warnings=1`. Before this PR the same IFC re-resolved as two `receptacle_panelboard`s.

**Finding → follow-up #412 (outside this territory, patch supplied there).**
`src/rvt/convert/rvt_to_ifc.py::_classify` is a hand *copy* of the old precedence (its docstring
says it mirrors `_classify_equipment`). Measured on this head: `convert_rvt_to_ifc(out/verify331/
h_mapped_item_reuse-lite/h_mapped_item_reuse.rvt)` extracts `receptacle_panelboard` for the three
families named `Lighting Panelboard LP-n 208Y/120 …` (voltage first — wrong before and after this
PR), the re-resolved IFC now says `lighting_panelboard`, so the round-trip table reads `kind_ok
False ×3, equipment_survived 0/3, all_survived False` and the manifest gains the "round-trip
survival is PARTIAL" degradation label (IFC delivered regardless). Scope of the effect: only ≤ 240 V
boards whose text says lighting/LP- (or RP- boards above 240 V) on the rvt→ifc route with
round-trip on; 480Y/277 rooms (acceptance room, `SMALL_ROOM_PROMPT`, every shard test) unaffected.
With `panelboard_flavour` now extracted, #412 is a three-line change: `_classify` calls
`panelboard_flavour(hay, ll=ll, bus=bus, mains=…)` and the copy disappears. If the reviewer prefers
that inside this PR, it is one push; it was kept out only because the charter limited `src/` to
`_classify_equipment`.

**/simplify (4 angles) — applied vs kept.** Applied: `v`/`bus` no longer computed ahead of the
text-only rules (simplification + efficiency, same finding); the test's needless `dict(schedule)`
copy dropped; the flavour rules lifted into the shared `panelboard_flavour` and `dp-` promoted with
the bare word kept low (altitude 1 + 2, above); the rme "Lighting and Appliance" test row reworded
from "intended" to "pinned as-is, #414's call" and #414 filed (altitude 3). Reuse: clean (no
backend-free product stub or classify table existed; `test_ifc_intent.py`'s helpers sit behind its
module-level ifcopenshell skip). Kept: the test still drives the private `_classify_equipment`
(that is the integration the fixtures depend on) plus one direct `panelboard_flavour` test for
#412's caller.

### BRANCH STATE (eng #331)

* Branch `cam/331-lp-lighting-classify` from `main` @ 2b87024; PR opened ready with `Closes #331`;
  regime #302 (GitHub checks meaningless; tech-lead session runs sandboxed CI on the head and merges).
* Files: `src/rvt/ifc/intent.py` (`_classify_equipment` + the `panelboard_flavour` helper it now
  delegates to; nothing else in the module) + `plugin/lib/src/rvt/ifc/intent.py` (the one sync
  mirror; `tools/dev/` is not shipped); `tools/dev/make_ifc_fixtures.py` (two `#331` notes removed,
  −5 lines); `tests/ifc_conformance/c_storeys_relative_placement.expected.json`,
  `tests/ifc_conformance/h_mapped_item_reuse.expected.json` (re-pinned, table above);
  NEW `tests/test_ifc_classify_equipment.py`, NEW `tests/ci_shard.d/331-lp-lighting-classify.txt`;
  this section.
* Not touched: `.ifc` fixture bytes, `rvt_to_ifc.py` (#412), `prompt_intent.py` (#414), hot files,
  workflows, `TRACKER.md`.
* Gates: above + `tools/sync_plugin.py` then `--check` clean, `plugin/scripts/validate_plugin.py`
  PASS (25 assertions), `tools/dev/check_portable_paths.py` ok (2881), `tests/test_plugin_sync.py
  tests/test_shard_list.py tests/test_bootstrap.py` 40 passed (counts repeated in the PR body).
  Nothing staged; no certification claim.
* Follow-ups filed: #412 (rvt→ifc calls the shared rule), #414 ("Lighting and Appliance Panelboard"
  phrase, one decision for both classifiers). Open questions: none blocking.

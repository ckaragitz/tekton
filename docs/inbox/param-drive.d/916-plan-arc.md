# 916 — a plan circle is ONE full arc, as born plan circles draw it (DONE 3 for the plan)

Stream: **param-drive** (fragment; index `../param-drive.md`). Issue **#916** DONE 3 for
the circles on the Ref. Level (horizontal sketch planes), following #955 (the runs, record
`916-run-arc.md`). Base `0c93e62`. No probe families were made and nothing was sent to the
owner. No Revit claim is made here (hard rule 4): the full plan arc is AUTHORED, the
assembled families UNVERIFIED.

## Census (421-family private reference corpus — development instrument, counts only)

Scripts in the session scratchpad (`plan916/census.py`, `split.py`, never committed): the
#955 census with the sketch-normal filter switched from horizontal to vertical (sketch
plane horizontal), plus a pass over every circle in every horizontal-plane sketch.

- **Population.** Extrusions whose sketch plane is horizontal and whose sketch holds only
  arcs: 235 single circles, 19 rings, 106 other all-arc profiles. Work plane of the 235:
  a Level 190, a reference plane 12, none resolved 33.
- **One full arc vs two halves.** **235 / 235** single circles are ONE `CurveElem` whose
  `GArc` has endParams [0, 0]; none is two halves. Over every circle in every
  horizontal-plane sketch (any profile, grouped by centre and radius): **858** contain a
  full arc (854 a single one), **33** are split into partial arcs (5 of them the
  [−π, 0] + [0, π] pair this engine drew, 10 [0, π] + [π, 2π], 18 other splits).
- **The CurveElem** (of 235): no control joins 235; cells SketchMembership + ArcElemCell
  232 (+ PatternHelper 3); curve history (2: 0), (2: 1) 235; 2-row geometry table 235;
  header deletion [family, SketchPlane, sketch, self] 235; appearance [sketch] 235;
  regenOnly [work plane, extrusion] 202, [extrusion] 19, other 14; rep one full `GArc`,
  root flags 32, gElemType 2 — 235; centre marker tag 1 — 235.
- **The sketch:** halves tag 0 [0, π] / tag 1 [π, 2π] 230 (5 renumbered); curve history
  (1: −10000), (0: 0) 222; geometry table 2 rows with `m_nextIndex` 1 — 220; ONE solver
  record, a `VarSketchArcObj`, 235, `m_unbounded` True 235, `m_angleCoef` = the radius 198,
  angle params 0 … 2π × radius 170 (2π … 4π 24, other 41); no constraint or point records
  235; rep lists the [π, 2π] half first 235. Guess cache `m_nPar` 5 on 213 (this engine
  writes 0 — the convention #955 already states).
- **The extrusion:** helper loop (tag 1 [π, 2π], tag 0 [0, π]) 176 (5 renumbered, 54 with
  the tags swapped); face history caps, U side, L side 229; edge history 6/7, 3/4, 9, 8 —
  228; geometry table 10 rows 228; B-rep 2 Plane + 2 CylSurf faces, 6 edges 234.
- **Dimensions on the full arc:** labelled `RadialDim`s witness geomTag 0 with a cached
  [0, π] arc — type-9 (diameter) style 17, type 2 16, type 0 4 (all cached [0, π]);
  unlabelled radials 166; centre locks (`Alignment`, geomTag 1) 41 (10 to an origin
  plane, 31 to other planes); centre dimensions (`LinearDimString`, geomTag 1) 361.

**Reading.** Every censused field matches the run census's modal shape at the same or a
higher share, so `geometry.full_arc_cylinder_form` (#955) is the plan circle as born
without a field changed. The rotated-B-rep `cylinder_x` / `cylinder_y` was not censused
(it is not a born construction — its plan authoring circle is turned by its B-rep only)
and stays as is, as the brief asked.

## What was built

- **`src/rvt/famgen/geometry.py`:** `cylinder(..., full_arc=None)` draws
  `full_arc_cylinder_form` (kind still `"cylinder"`; the tessellation facts kept; its own
  plan note) unless `full_arc=False`; module switch `PLAN_CIRCLE_FULL_ARC = True` — the
  documented way back to the two-half form (the form with the #589 load verdict). The
  census block above the full-arc helpers gained the plan counts; the
  `full_arc_cylinder_form` docstring no longer says plan circles are untouched.
- **`src/rvt/famgen/factory.py`:** `add_cylinder_form(..., full_arc=None)` passes it on;
  the rotated-B-rep `cylinder_x` / `cylinder_y` passes `full_arc=False` (bytes unchanged).
- Words only: `diameter_law.py` module docstring (the labelled arc is the full arc now;
  the P5 radius verdict was on a half arc and does not carry over), `drive_law._arcs_of`
  docstring, `run_law.py` comment, `archetypes.py` trapeze limit (no longer says the rods'
  diameter sits on a half arc). None of these change a byte (measured below).
- What follows with no further code: the trapeze's Rod Diameter labels each rod's ONE
  full arc, and the follow drive (#904 P4) locks each rod's centre ONCE (it locked each
  half before); `factory`'s "placed on a half arc" diameter note is conditional and drops;
  the downlight's can / trim / lens diameters sit on full arcs.

## Byte deltas (sha256 prefix, fixed output path, base `0c93e62` vs this branch)

Changed, on purpose — every product that carries a plan circle (file sizes unchanged):

| product | 2026 base → head | 2025 base → head |
|---|---|---|
| `cylinder` part | `4bb4a724…` → `42b191f0…` | `ad28d14e…` → `841da2bc…` |
| `cylinder` part + labelled D | `d34bae56…` → `6fd4cd4c…` | `119f6ec5…` → `df9148ae…` |
| strut trapeze (solid) | `83586ff9…` → `01997b0d…` | `300a9b75…` → `45c8eba8…` |
| strut trapeze, nested hardware | `d010ba41…` → `d54b4a2f…` | `50c564e2…` → `c446ef50…` |
| IFC downlight | `b4fb891b…` → `ea274092…` | `a5378ecb…` → `4a67e333…` |
| fan-powered box | `8cdd5316…` → `90ff4025…` | `f3bf2730…` → `2652fc29…` |
| fan coil | `65aea2cd…` → `d2a1fc73…` | `efd11004…` → `889d113b…` |

The fan-powered box and fan coil were in the brief's byte-identical list, but both carry a
plan `cylinder` part (one each, beside rotated `cylinder_y` stubs that keep their bytes),
so they change with the rule; that is the rule applied, not a side effect.

Element deltas read back from the written files (2026 = 2025): per plan circle −1
`CurveElem` (cylinder 2 → 1, trapeze 4 → 2, downlight 6 → 3, fan-powered 4 → 3 arcs with
1 full, fan coil 8 → 7 with 1 full); trapeze centre locks on rod arcs 4 → 2; diameter
`RadialDim`s unchanged in number (cylinder 1, trapeze 2, downlight 3), all type-9, all
witness geomTag 0 with a cached [0, π] arc — on a full arc now, on a half arc before.

Unchanged, byte-identical on 2026 **and** 2025: panelboard, transformer, LCP, cable tray,
wireway, junction box, strut channel, conduit, prism, the −Y run of #955, the
rotated-B-rep `cylinder_x`.

**Attribution:** this branch with `PLAN_CIRCLE_FULL_ARC = False` reproduces all fourteen
base SHAs above exactly — the word changes change no bytes, the full plan arc is the
whole delta.

## Evidence

- **`tools/rvt_validate.py`:** ok, 0 errors / 0 warnings on all 14 changed files (7
  products × 2026 / 2025).
- **`constraint_law.check_file == []`** on all 14, host unit; the nested trapeze's 2
  nested units each `[]` too (CG1 … CG11).
- **Drives still wired:** Rod Diameter `wired 1`, 2 dims, `half_arc False`, no "not wired"
  note; the downlight's 3 diameters and the labelled `cylinder` part's 1 wired; every
  centre lock judged on its plane (the follow drive's own `_locks_on_planes`: 2 arc locks,
  0 off-plane, per tier count; CG over the written files above).
- **Latency** (trapeze build + write, warmed, min of 5, three alternating runs, one
  process each): base 1.272 / 1.098 / 1.200 s, branch 1.167 / 1.196 / 1.173 s — no
  measurable change. Not a `surface_bench` measurement.
- **`tools/self_battery.py`:** 27 / 27 PASS.

## Re-pinned tests (deliberate)

- `tests/test_run_arc_916.py`: the "plan circles keep two half arcs" test now covers only
  the rotated-B-rep `cylinder_x` (it asserted the old plan form); the downlight
  never-reaches-the-full-arc test is removed (its opposite is now asserted in
  `test_plan_arc_916.py`).
- `tests/test_diameter_916.py`: the trapeze note no longer carries the half-arc caveat;
  `half_arc` is False.
- `tests/test_drive_follow_904.py`: follow locks 4 + 16·tiers → 2 + 16·tiers and arc locks
  4 → 2 (one centre lock per rod circle); the generic box + circle follow 4 → 3 locks, arc
  locks 2 → 1.
- `tests/test_ifc_assembly.py` (#589 solver-record test): one record per curve the map
  names (1), the sketch absorbing two halves (2) — the crash law (records = map) unchanged.
- `tests/test_famgen_geometry.py`: the two-half schema round-trip calls
  `G.cylinder(..., full_arc=False)` explicitly (that form still ships, for the rotated
  B-rep); the owner-machine emit test counts `+ len(fb.elements)` records.
- `tests/test_cylinder_tessellation_530.py`: a plan cylinder bundle is 4 elements, not 5.

## Honest limits

- **No desktop verdict** for a full plan arc, its label, its one centre lock, or anything
  else here (hard rule 4). The two-half form HAS a desktop load verdict (#589, Revit 2026);
  that verdict does not carry over. `PLAN_CIRCLE_FULL_ARC = False` is the way back.
- **The downlight's diameter note is now wrong** and is not fixed here: `src/rvt/ifc/` is
  another PR's territory this round. *(Applied when shipped: the note now follows
  `half_arc`.)* `famfrom_ifc._wire_downlight_drives` (around line
  789) still appended "… placed on a half arc of this engine's two-half circle". Patch for
  whoever holds that file:

  ```diff
  -            f"on {dia['dims']} circle(s), the Revit-born type-9 diameter dimension placed "
  -            "on a half arc of this engine's two-half circle")
  +            f"on {dia['dims']} circle(s), the Revit-born type-9 diameter dimension"
  +            + (" placed on a half arc of this engine's two-half circle"
  +               if dia.get("half_arc") else ""))
  ```
- **Centre locks to the origin planes** are still not authored for plan circles that are
  not followers (born: 41 centre `Alignment`s over 235 circles).
- Engine conventions kept, as on the runs: curve `m_GInfo` flags, the guess cache's
  `m_nPar` 0 (born 5 on 213 / 235), the solver record in the sketch's own 2D frame.
- `cylinder_x` / `cylinder_y` without `work_plane: "vertical"` keep their rotated-B-rep
  two-half circle (desktop round 4's construction); a born-way run is `work_plane:
  "vertical"`.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/geometry.py`, `factory.py`, `diameter_law.py`, `drive_law.py`,
  `run_law.py`, `archetypes.py` (+ their `plugin/lib/` mirrors via `tools/sync_plugin.py`).
- `tests/test_plan_arc_916.py` (new, 7 functions / 12 cases) +
  `tests/ci_shard.d/916-plan-arc.txt`; re-pins in `test_run_arc_916.py`,
  `test_diameter_916.py`, `test_drive_follow_904.py`, `test_ifc_assembly.py`,
  `test_famgen_geometry.py`, `test_cylinder_tessellation_530.py`.
- This fragment. Not touched: `src/rvt/ifc/**`, `constraint_law.py`, `trapeze_nested.py`.

**Gates** (`RVT_SKIP_LARGE=1`)
- test_plan_arc_916, test_run_arc_916, test_diameter_916, test_drives_rest_913,
  test_archetype_drives_913, test_trapeze_nested_917, test_nested_heights_940,
  test_angular_eq_948, test_constraint_law, test_constraint_law_910, test_cg5_956,
  test_cg7_953, test_sketch_hv_952, test_famgen_archetypes, test_ifc_assembly,
  test_conftest_scaffolding: 583 passed / 4 skipped (test_plugin_sync failed in that run
  only because the mirrors were not yet synced; re-run below).
- Wider: drive_follow_904, drive_law_904, edit_family_size_668, equipment_drives_913,
  famfrom_ifc_standards, famgen_catalog, famgen_factory, famgen_geometry,
  famgen_size_bound_806, fan_coil_893, fan_powered_895, height_law_787,
  horizontal_cylinder_fit, ifc_assembly_628, ifc_census, ifc_family, lock_column_915,
  luminaire_sizes_682, nest_917, nest_locks_917, orient_514, partition_tail_938,
  pset_drive_714, strut_trapeze_899, loader_refindex_947, standards_photometric_641,
  cylinder_tessellation_530: 725 passed / 15 skipped / 4 failed — the 4 were
  test_drive_follow_904's lock counts, re-pinned above.
- After sync: test_plugin_sync, test_drive_follow_904, router, router_load_release,
  intent_faulted, maker_adjacency_739, maker_qualifiers_742, taxonomy_692,
  taxonomy_build_766, taxonomy_wiring_692, standards_apply_safe, steplite: 708 passed /
  12 skipped.
- `tools/sync_plugin.py` rebuilt; `--check` clean; `plugin/scripts/validate_plugin.py`
  PASS (25 assertions); `tools/dev/check_portable_paths.py` ok; `tools/self_battery.py`
  27 / 27.

**Shipped vs staged:** the full arc is the default for every plan circle. Nothing staged
for a viewer or desktop round.

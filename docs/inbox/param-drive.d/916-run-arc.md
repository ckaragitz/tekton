# 916 — a horizontal run's circle is ONE full arc, as born runs draw it (DONE 3 for runs)

Stream: **param-drive** (fragment; index `../param-drive.md`). Issue **#916** DONE 3 for
the horizontal runs of `run_law` (merged in #950), plus the #950 review nits. No probe
families were made and nothing was sent to the owner. No Revit claim is made here (hard
rule 4): the full-arc run is AUTHORED, the assembled family UNVERIFIED.

## What was chosen: the full arc (not the concentric fallback)

The born shape is reproducible inside our writer field for field, so the run's circle is
now one full arc and the diameter label sits on it. The concentric-dimension fallback
(flags-28 tie between two half arcs) was not needed and was not written.

## Census (421-family private reference corpus — development instrument, counts only)

Scripts in the session scratchpad (`arc916/census.py`, never committed). Population: every
`ExtrusionElem` whose sketch normal is horizontal and whose sketch holds only arcs; the
runs are those whose profile is one circle (147) or a ring (4).

- **Origin-plane re-count (the #950 nit).** Work plane = the origin centre plane on
  **74 / 147** single circles; with the 4 rings (all on it) **78 / 151**; another plane
  18, unresolved 55. Both numbers were right for their own denominator — `run_law.py`
  counted circles, `913-drives-rest.md` counted every run. `run_law.py` now states both;
  the #913 record is left as written (another PR's record) and is correct as it stands.
- **The circle's CurveElem** (147 / 147 single circles unless stated): ONE `CurveElem`,
  driver `GArc` endParams [0, 0]; `m_controlJoinsSet` empty; cells SketchMembership +
  ArcElemCell (141; + PatternHelper 6); curve history (2: 0), (2: 1); 2-row geometry
  table; header deletion [family, SketchPlane, sketch, self]; appearance [sketch];
  regenOnly [work plane, extrusion] 92, [extrusion] 32; rep one full `GArc`, root flags
  32, gElemType 2; centre marker tag 1.
- **The sketch:** absorbs it as two halves — tag 0 [0, π], tag 1 [π, 2π] (140 + 7 with
  renumbered tags); curve history (1: −10000), (0: 0) (132); geometry table 2 rows,
  `m_nextIndex` 1 (132); `m_absorbedCurvesData` 2; ONE solver record, a
  `VarSketchArcObj` (147) with `m_unbounded` True (147), `m_angleCoef` = the radius and
  angle params 0 … 2π × radius (105); no constraint or point records (147); the rep lists
  the [π, 2π] half first (147).
- **The extrusion:** helper loop (tag 1 [π, 2π], tag 0 [0, π]) (136; 7 more with
  renumbered tags, 4 with the two tags swapped); ExtrusionGStep tag map identical to this engine's two-half-arc form —
  faces 5 = (3, curve 0), 2 = (3, curve 1), edges 6/7, 3/4, 9, 8 (139 / 147), listed caps,
  U side, L side (138); geometry table 10 rows (140); B-rep 2 Plane + 2 CylSurf faces,
  6 edges (147 / 147) — so `solid_cylinder_brep` is reused unchanged.
- **The diameter on a full arc:** labelled type-9 `RadialDim` on 21 single full-arc
  circles (24 over all 151 runs), witness geomTag 0 with a cached [0, π] arc (every
  non-flipped radial witness) — exactly what `diameter_law` already writes.
- **Centre locks (B):** 20 `Alignment`s (flags 30) witness a single circle's centre
  (geomTag 1): 14 to origin reference planes, 3 to other planes, 3 to a nested instance
  — the 10 / 151 runs that lock both. Not authored: in a vertical sketch one of the two
  locks would be to the Ref. Level, a lock no lane here authors, so it is a stated gap,
  not a cheap add.

## What was built

- **`src/rvt/famgen/geometry.py`:** `full_arc_cylinder_form` + `new_full_arc_curve_elem`,
  `new_var_sketch_full_arc`, `_full_arc_solver_obj` — the census shape above, built from
  the existing constructors and reshaped; `new_cylinder_extrusion(lower_half=)` (default
  [−π, 0], so every existing caller is byte-identical); the face / edge history listed
  U-first as born.
- **`src/rvt/famgen/run_law.py`:** `add_run_cylinder` authors the full-arc form (the
  tessellation facts and note kept); `centre_z` recorded; module docstring: the born
  census, the reconciled 74 / 147 vs 78 / 151, the gaps.
- **#950 review nits:**
  - `_end_plane(..., reach)`: `P = max(ctx P, |at| + 1, reach + 1)`, `reach` = the
    farthest a cap face sits from the origin across the run (|cross| + r) **or up it**
    (|z| + r — the z term goes one step beyond the nit: the plane's surface y is up, so a
    raised run's face also has to fit). `_face_lock`'s plane-witness trace widens the
    same way (`max(ctx P, max(|y0|, |y1|) + 1)`). Both reduce to the old value for every
    run within the default envelope (measured: no byte change, below).
  - `wire_run_length` raises `RunError` (not `RuntimeError`) on a finalized document, as
    its class and docstring say; `tests/test_drives_rest_913.py` re-pinned to
    `RL.RunError, match="finalized"` (deliberate: the old pin asserted the disagreement).
  - `factory.py`: the DIAMETERS (#916) comment moved back above the diameter code; a
    `work_plane="vertical"` on a non-run shape now adds a doc note (the shape is still
    built on the Ref. Level — delivered, said, not raised; no byte change).
  - `archetypes.py`: the conduit's limit now says one full arc and names the centre-lock
    gap instead of the half-arc gap.
- **`tests/test_run_arc_916.py`** (new, 11 functions / 16 cases) +
  `tests/ci_shard.d/916-run-arc.txt`; leak guard as in `test_drives_rest_913.py`.

## Evidence

- **Our written conduit against the census** (the census script run on our own 2026
  file): every censused field equals the born modal value — CurveElem (endParams, joins,
  cells, history, table, header deletion / appearance / regenOnly [wp, ext], rep), sketch
  (halves, history, table + nextIndex, one unbounded arc record with angleCoef = r and
  0 … 2πr, no constraint records, rep order), extrusion (loop, face / edge history and
  order, table 10, B-rep 2 + 2 faces / 6 edges), the labelled type-9 diameter on geomTag
  0 with a [0, π] cached arc. Two fields stay this engine's convention, as on every other
  sketch: the curve `m_GInfo` flags and the guess cache's `m_nPar` (0).
- **`tools/rvt_validate.py`:** ok, 0 errors / 0 warnings on 8 files — conduit 3/4 in, conduit
  2 in, a −Y run (off-centre, raised), a plain +X run; each 2026 and 2025.
  `constraint_law.check_file == []` on all 8.
- **Byte identity, base `3f575d3` vs this branch** (sha256 prefix, fixed output path,
  2026): unchanged — `cylinder_x` rotated B-rep `edc9493c21e45d48`, plan `cylinder` part
  `4bb4a724e9306c84`, box with `work_plane="vertical"` `d56acfd989e7f4dd`, strut trapeze
  (plan diameters) `19cb02558cb9e666`, LCP `f3e5da5278203035`, cable tray
  `0121098d8eeb0398`, wireway `ce3e7c7a428799ac`, junction box `d27000d28dd35cd4`, strut
  channel `7d3584f40ede4ed9`, prism `caba26b11557958d`, IFC downlight `b4fb891bff63b099`.
  Changed, on purpose (the runs): conduit `0cd4d9c3…` → `f37465c3…`, conduit 2 in
  `820462a3…` → `85fb932c…`, −Y run `05346663…` → `95194dc3…`, plain +X run `b178a4ad…` →
  `9e8cad32…` (file sizes unchanged: 229,376 / 229,376 / 229,376 / 225,280 bytes).
  **Attribution:** the branch with the full arc swapped back for the two-half form
  reproduces all four base SHAs exactly — the nits change no bytes, the full arc is the
  whole delta.
- **Latency** (conduit build + write, warmed, min of 5, one process, three alternating
  runs each; another agent was running on the machine): base 0.182 / 0.185 / 0.167 s,
  branch 0.170 / 0.165 / 0.170 s — no measurable change. Not a `surface_bench` measurement.
- **`tools/self_battery.py`:** 26 / 26 PASS.

## Honest limits

- **No desktop verdict** for a full-arc run, its label, or anything else here (hard
  rule 4). Validator green is a fact about the file, never evidence Revit opens it.
- **Centre not locked** to the origin planes (born 10 / 151) — above.
- **Solver records** keep the circle in the sketch's own 2D frame (unchanged gap); the
  curve-geometry flags and `m_nPar` stay engine convention.
- **The plan circles** (cylinder parts, trapeze rods, downlight circles, the rotated-B-rep
  `cylinder_x`) keep two half arcs; their diameters still sit on the [0, π] half
  (`diameter_law`'s gap for plan circles). Extending the full arc there is a separate
  change with its own census (plan circles were not censused here).

## Correction (2026-10-02, folded in by #952 from the #955 review)

Two facts above are wrong, the rest stands: the PR's base was `3e03fd3`, not
`3f575d3` (the "Byte identity, base ..." line names the wrong commit), and
`tests/test_run_arc_916.py` has **9** test functions / 16 collected cases, not
11 / 16.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/geometry.py`, `src/rvt/famgen/run_law.py`, `src/rvt/famgen/factory.py`,
  `src/rvt/famgen/archetypes.py` (+ their `plugin/lib/` mirrors via `tools/sync_plugin.py`).
- `tests/test_run_arc_916.py` (new) + `tests/ci_shard.d/916-run-arc.txt`;
  `tests/test_drives_rest_913.py` (one re-pin, above).
- This fragment.
- Not touched: `constraint_law.py`, `drive_law.py`, `trapeze_nested.py`, `diameter_law.py`.

**Gates**
- `tests/test_drives_rest_913.py`, `test_diameter_916.py`, `test_archetype_drives_913.py`,
  `test_drive_law_904.py`, `test_trapeze_nested_917.py`, `test_run_arc_916.py`:
  148 passed.
- Wider batch (archetype_alias_order_812, cylinder_tessellation_530,
  edit_family_size_668, famgen_archetypes, famgen_size_bound_806, famgen_standards,
  fan_coil_893, fraction_parse_831, lock_column_915, orient_514, partition_tail_941,
  specsheet_route_688, ifc_assembly; `RVT_SKIP_LARGE=1`): 798 passed / 5 xfailed /
  0 failed.
- `tools/sync_plugin.py` rebuilt; `--check` clean; `plugin/scripts/validate_plugin.py`
  PASS (25 assertions); `tools/dev/check_portable_paths.py` ok;
  `tests/test_plugin_sync.py` 9 passed.

**Shipped vs staged:** the full-arc run is the default for every `work_plane: "vertical"`
run (the conduit archetype included). Nothing staged for a viewer or desktop round.

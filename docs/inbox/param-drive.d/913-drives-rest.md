# 913 — the rest of the survey: the conduit, the single prism and the IFC downlight constrained

Stream: **param-drive** (fragment; index `../param-drive.md`). Steer **#913** (*"every
generated family's parts constrained to parameter drives"*). This closes three of the
four rows `913-equipment-drives.md` left unwired. No probe families were made and
nothing was sent to the owner, per the steer.

## The rows, before and after

| Constructor (route) | Before | After (default) | Old behaviour kept |
|---|---|---|---|
| `make_archetype` **conduit** (prompt, famspec, taxonomy) | none: a vertical Ref. Level extrusion whose B-rep alone is rotated (#591 round 4); "Outside Diameter" not a family parameter | the run **authored the born way** (circle on the vertical centre plane, extruded along it); new `Outside Diameter` / `Length` parameters; **Length** drives both end faces symmetrically, **Outside Diameter** labels the circle | the rotated-B-rep `cylinder_x` is unchanged for every other caller (the IFC assembly route); no test or route pins the old conduit bytes |
| `make_generic_model` **single prism** (spec-sheet lane, prompt shapes) | the #372 first-solid chain on a rectangle; nothing on a polygon | `prism_drive="law"`: Width / Depth symmetric on the body's edges, Height on its cap faces (base held to the origin by a locked height when raised or sunk); a polygon gets Height only | `prism_drive="372"` (byte-identical to base) / `None` |
| `ifc.famfrom_ifc.make_downlight` (facts → rfa) | none | `drive="law"`: Frame Length / Frame Width, Bar Hanger Span (plan), Housing / Trim / Lens Diameter (circles), Housing Height (can, the LED driver riding its top) | `drive=None` (byte-identical to base) |
| `make_generic_model(parts=…)` from the IFC / Claude Design routes | only caller-supplied specs | **unchanged — still a gap** (no route derives specs yet) | — |

## Census (421-family private reference corpus — development instrument, counts only)

Scripts live in the session scratchpad (`drv-rest/c0.py`, `c3.py`, `c4.py`, `c5.py`) and
are never committed; no specimen or parameter name is recorded here.

- **Form inventory:** ExtrusionElem 2,161, RevolutionElem 104, SweepElem 104,
  BlendElem 65, SweptBlendElem 10.
- **How a horizontal round run is built.** A solid whose profile is one circle and
  whose axis is horizontal is an **ExtrusionElem sketched on a vertical plane** 151
  times (147 single circles + 4 concentric rings), a sweep 8 times, a revolve never
  (no revolution profile is a circle). So the dominant born way is a circle on a
  vertical work plane extruded along that plane's normal — not a sweep, not a revolve,
  and not a rotated B-rep.
  - Work plane: the origin centre plane square to the run 78 / 151, another
    reference plane 18, unresolved 55.
  - Start offset negative (the run centred on its work plane) 79 / 151, zero 52,
    positive 20.
  - The circle is one full `GArc` (endParams [0, 0]) 147 / 151.
  - In 79 files carrying such runs: the `VarSketch` `m_serFlags` is 2 on 145 / 160
    (plan sketches carry 1); each arc is in world coordinates on the plane
    (181 / 193), its centre marker along the normal (170 / 193), arc header
    `m_regenOnly` [extrusion, work plane] (102 / 193); `m_sideRefPlaneCurveBased`
    True on all.
- **How its length is driven.** End-face locks, 94 in those files:
  - every one an `Alignment` flags 14, no cell, owned by no view, one segment
    (flags 1, locked value 0), header `m_regenOnly` [UnitsElem], header flags 10;
  - `m_planeNormal` +Z (the plan) 87 / 94;
  - the other witness a **surface-only** vertical reference plane on 77 / 77
    non-origin planes (the 17 drawn ones are origin planes);
  - END face (geomTag 0) constrained along −normal 50 / 55, START (geomTag 1)
    +normal 26 / 28; the plane is the first witness exactly when that direction
    points down its world axis (+X runs: END plane-first 31 / 45, START face-first
    12 / 17; −Y runs: END face-first 9 / 10, START plane-first 10 / 11) — height_law's
    rule for −Z / +Z;
  - the planes are held by **plan-view** dimensions: labelled (flags 12, normal +Z,
    2 witnesses) 105, EQ about the origin plane (flags 140, segments flags 2) 35;
  - FamDimConstrMgr rows as on a Case B height: `m_paramExprs` 1.0 × the built-in
    end / start offset (msg 580); driven-dim entries (plane +s, SketchPlane −s,
    lock −s) with s the sign of the normal along its axis (47 / 61 on +X runs, the
    flipped form 19 / 21 on −Y runs); `m_dimSegDataMap` `m_dimDir` the run axis with
    coefficients (−s, +s); `m_fixedRefs` plane refFlip 2, SketchPlane refFlip 2 on a
    +normal and 1 on a −normal.
- **How its diameter is driven.** On the 151 runs' circles: a labelled type-9
  diameter 24, a labelled radius (type 2 / 0, mostly formula-driven) 29, an unlabelled
  radial dim 59, nothing 38. The labelled diameters' `m_planeNormal` runs along the
  sketch normal: + on 14 / 27, − on 13; 7 of the + ones carry no dimension sketch
  plane — the form written here.

## What was built

- **`src/rvt/famgen/run_law.py`** (new):
  - `add_run_cylinder(doc, axis, radius_ft, length_ft, center, base_z_ft, rep)`: the
    engine's verified upright cylinder cluster built in the work plane's local frame,
    then every element and the cached B-rep placed into world by that frame's rotation
    (`orient.rotate_record`, the #514 path), the SketchPlane re-hosted on the origin
    centre plane square to the run (Center (Left/Right) for X, Center (Front/Back) for
    Y), the sketch `m_serFlags` 2, regen parents on the work plane, bboxes in world.
    Sketch, frame, arcs and B-rep agree: the B-rep's cylinder axis is the run axis.
  - `wire_run_length(doc, caption, targets, symmetric=True)`: two surface-only end
    planes, a labelled plan dimension between them (+ EQ about the origin plane), each
    run's END / START face locked by the born lock, the manager rows. All-or-nothing:
    every check (parameter exists, drivable spec, value = run length, one axis, shared
    caps, faces not locked yet, centred when symmetric) runs before the first mutation.
  - `wire_run_specs`: declarative specs, a refusal is a note (hard rule 1).
- **`drive_law`**: `plane_at` / `_plane_ends` read a surface-only plane off its surface
  (`is_surface_only`), so `dim3d` / `eq3d` dimension the run's end planes. Drawn planes
  read exactly as before.
- **`diameter_law`**: `circle_of(..., vertical=True)` admits a circle in its own
  vertical sketch plane, and the dimension takes that sketch's frame and normal
  (cached arc, reference point, `m_planeNormal`). The plan path is unchanged (the
  trapeze is byte-identical), a plan circle is still required without the flag, and
  the rotated-B-rep refusal (#929) still stands for `cylinder_x` without a work plane.
- **`factory`**:
  - `add_generic_part`: a `cylinder_x` / `cylinder_y` part with `"work_plane":
    "vertical"` is authored by `run_law`; without it the rotated-B-rep form is
    unchanged.
  - `make_generic_model(runs=…, prism_drive="law")`: run-length specs on the multipart
    path; the single-prism law (Width / Depth through `_plan_drive_spec` +
    `_wire_equipment_drives`, Height through `_prism_height_specs`).
  - `make_archetype` passes the archetype's `runs`.
- **`archetypes`**: `Archetype.runs`; the conduit's part carries `"work_plane":
  "vertical"`, `family_params` Outside Diameter / Length, `runs` Length (symmetric),
  `diameters` Outside Diameter; `lod_note` and `limits` say what is authored and that
  the assembled family is unverified. Nominal Diameter (the category's conduit-size
  standard) keeps the trade size as a value.
- **`famfrom_ifc`**: `make_downlight(drive="law")`, `downlight_drive_specs`,
  `DownlightProduct.drives / heights / diameters`.
- **`spec/famspec.schema.json`**: `downlight.drive` (`law | null`, required by the
  schema-mirror test) and `generic_model.prism_drive` (`law | 372 | null`).
- **`tools/self_battery.py`**: rows `prism_rect_law`, `prism_polygon_law`,
  `shape_run_x`, `shape_run_y`, `archetype_conduit`.

## Evidence

- **Wired chains** (2026, in process):

  | Family | In-plane | Heights (wired, face locks, locked unlabelled) | Runs / diameters |
  |---|---|---|---|
  | conduit 3/4 in | — | — | Length: 2 end-face locks; Outside Diameter: 1 dim |
  | prism 2 × 1 × 3 ft | Width 2, Depth 2 (symmetric) | 1, 2, 0 | — |
  | prism raised 0.5 ft | Width 2, Depth 2 | 2, 2, 1 | — |
  | prism polygon | — | 1, 2, 0 | — |
  | IFC downlight | Frame Length 2 (two new planes: the plate is off the can axis), Frame Width 2 (symmetric), Bar Hanger Span 4 (symmetric) | 3, 4, 2 | Housing / Trim / Lens Diameter |
  | IFC downlight envelope | — | 2, 2, 1 | Housing / Trim Diameter |

- **Read-back from the written file, 2026 and 2025**
  (`test_every_written_lock_lies_on_its_plane`, 8 builds × 2 releases): every sketch
  lock's GLine ends on its plane (count = authored), every cap-face lock's face (the
  extrusion offset along its SketchPlane's normal) on its plane, `constraint_law
  .check_file == []`, no refusal note.
- **`tools/rvt_validate.py`:** VALID, 0 errors, 0 warnings on 14 files — conduit (3/4 in
  and 2 in), prism, raised prism, polygon prism, IFC downlight standard and envelope,
  each for 2026 and 2025.
- **`tools/self_battery.py`:** 26 / 26 PASS (21 before + the 5 new rows).
- **Byte identity, base `96f976f` vs this branch** (sha256 prefix, fixed output path,
  same inputs): untouched constructors identical — panelboard `702e6c6c697b7f96`,
  transformer `d241c255b97dca56`, troffer `e8c10d6322b3c074`, factory downlight
  `14c4f9668232124b`, device `a6b12a53339a134f`, cable tray `0121098d8eeb0398`,
  wireway `ce3e7c7a428799ac`, junction box `d27000d28dd35cd4`, strut channel
  `7d3584f40ede4ed9`, LCP `f3e5da5278203035`, trapeze (plan diameters)
  `19cb02558cb9e666`, multipart box `045a95ebf169d1f2`, rotated-B-rep `cylinder_x`
  `fce815e0c8e4cb8c`. The old modes reproduce the base defaults: prism
  `prism_drive="372"` = base prism `6fd3cce92d09fd06`; polygon `prism_drive=None` =
  base polygon `1c68236fc1ea4e00`; downlight `drive=None` = base `a81244869a6ccd37`;
  envelope `drive=None` = base `4339ced6318acb8d`.
- **Refusals are SHA-identical** (`tests/test_drives_rest_913.py`): six bad run specs
  (missing part, number spec, wrong value, missing parameter, empty, listed twice) and
  an off-centre symmetric run each equal the build without the spec; a run diameter with
  the wrong value equals the build without it; a corrupted prism Width or Height spec
  equals the build without it; every downlight spec refused equals `drive=None`; the
  rotated-B-rep `cylinder_x` refuses both a run length and a diameter, SHA-identical; the
  direct `wire_run_length` refusals leave the element count unchanged.
- **Latency** (build + write, warmed, min of 5, one process, idle machine; base
  `96f976f` → branch): conduit 0.158 → 0.179 s; prism 0.166 → 0.186 s (`"372"` 0.191 s);
  polygon prism 0.160 → 0.176 s; IFC downlight 0.284 → 0.348 s (`drive=None` 0.286 s);
  envelope 0.259 → 0.268 s. This is not a `surface_bench` measurement.

## Re-pinned on purpose

- `tests/test_drive_law_904.py::test_the_single_prism_path_never_drops_drives_silently`
  and `tests/test_height_law_787.py::test_the_single_prism_path_says_heights_were_not_wired`:
  the single prism now wires its OWN Width / Depth / Height by default, so its reports
  are no longer empty. The substance is kept: a caller's spec is never wired on this path
  and never dropped silently — the reports equal the build without the caller's spec,
  and the NOT-wired note is present. The old empty reports are pinned beside them under
  `prism_drive="372"`.
- `tests/test_panel_drives_914.py::test_a_centred_profile_keeps_its_planes_at_plus_minus_half`
  pins the #372 chain's planes; it now builds with `prism_drive="372"`, the chain that
  was the default until this change (byte-identical).
- `tests/test_diameter_916.py` replaces `wire_diameter_specs` with a probe of the old
  signature; the factory passes the new `runs=` keyword only when a run is present, so
  the call is unchanged otherwise (no test edit).

## Honest limits

- **No desktop verdict for any of this** (hard rule 4). Authored; the assembled families
  are unverified. Never probed on a desktop:
  - a form sketched on a vertical plane whose sketch, frame and B-rep agree (#591
    rounds 1–3 moved only the datum and kept a vertical B-rep; round 4 rotated the
    B-rep only);
  - an end-face lock to a vertical surface-only plane held by plan dimensions;
  - a diameter label on a vertical circle (the P5 verdict is a plan radius);
  - the single prism's and the downlight's Case B heights (no Case B element has a
    verdict), the downlight's diameters (no diameter has a verdict).
- **The run's circle** is this engine's two half arcs; born runs draw one full arc
  (147 / 151), so the diameter sits on the [0, π] half (`diameter_law`'s own gap). Its
  centre is not locked to the origin planes (born runs lock it on 10 / 151). The sketch
  solver records keep the circle in the sketch's own 2D frame — unverified on a
  vertical plane.
- **Conduit:** the bore, couplings and wall thickness are still not modelled; Nominal
  Diameter (conduit size) is a value and drives nothing; the old rotated-B-rep conduit is
  not kept behind a switch (nothing pins it; the rotated form itself is unchanged for the
  IFC route).
- **Single prism:** a polygon's Width / Depth are not driven (no axis-aligned edge pair);
  a caller's `drives` / `heights` / `diameters` / `runs` are still refused on this path
  with the note.
- **IFC downlight:** Aperture Diameter (no aperture solid) and Overall Height (the stated
  pset value is not the drawn envelope) are values only; the junction box and driver keep
  their plan positions when Frame Length flexes; trim, lens and frame thicknesses are not
  driven; the lens keeps its height inside the can.
- **Still unwired from the survey:** `make_generic_model(parts=…)` from the IFC / Claude
  Design routes — no route derives specs for an arbitrary assembly yet.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/run_law.py` (new): the born-way run and its length drive.
- `src/rvt/famgen/drive_law.py`: `is_surface_only`; `plane_at` / `_plane_ends` read a
  surface-only plane off its surface.
- `src/rvt/famgen/diameter_law.py`: `sketch_frame`; the vertical-sketch lane
  (`circle_of(vertical=)`, `wire_diameter(vertical=)`, `wire_diameter_specs(runs=)`).
- `src/rvt/famgen/factory.py`: the run part, `runs=`, `prism_drive=`,
  `_prism_height_specs`.
- `src/rvt/famgen/archetypes.py`: `Archetype.runs`; the conduit's params / runs /
  diameters / notes.
- `src/rvt/ifc/famfrom_ifc.py`: `make_downlight(drive=)`, `downlight_drive_specs`.
- `spec/famspec.schema.json` + plugin mirror; `plugin/lib/…` mirrors.
- `tools/self_battery.py`: five rows.
- `tests/test_drives_rest_913.py` (new, 21 test functions, 44 cases) +
  `tests/ci_shard.d/913-drives-rest.txt`; re-pins in `test_drive_law_904.py`,
  `test_height_law_787.py`, `test_panel_drives_914.py` (above).
- This fragment.

**Gates**
- `tools/sync_plugin.py` rebuilt; `--check` clean; `plugin/scripts/validate_plugin.py`
  PASS (25 assertions); `check_portable_paths` ok.
- `rvt_validate`: VALID 0 errors / 0 warnings on 14 files (2026 + 2025).
- `self_battery`: 26 / 26 PASS.
- pytest batch 1 (diameter_916, equipment_drives_913, archetype_drives_913,
  panel_drives_914, height_law_787, drive_law_904, famfrom_ifc_standards,
  lock_column_915, famgen_archetypes, orient_514, spec_lists_929, drive_follow_904):
  461 passed / 4 failed before the re-pins; the 4 were the three re-pinned tests and
  the diameter probe's signature (fixed in the factory) — rerun with the new file:
  137 passed.
- pytest batch 2 (router, conftest_scaffolding, surface_perf, bootstrap, coldstart,
  specsheet route / backend / sheet 688, size_bound_806, standards_apply_safe,
  photometric_641, ifc_family, fraction_parse_831, frontdoor_json_strict,
  famgen_standards, ifc_pset_params, nest_917, nest_locks_917, family_anatomy_837,
  constraint_law_910, cylinder_tessellation_530, edit_family_size_668,
  lcp_clearance_820, archetype_alias_order_812, ifc_intent, famspec_schema_keys_913,
  famgen_factory, mep_conduit, horizontal_cylinder_fit, coverage, famgen_catalog):
  1230 passed / 28 skipped / 5 xfailed / 0 failed.
- After the final sync: the new file + plugin_sync + diameter_916 +
  equipment_drives_913 + archetype_drives_913 + famfrom_ifc_standards +
  famspec_schema_keys_913: 179 passed.

**Shipped vs staged:** wired by default. No viewer or desktop batch was staged (steer
#913: no probe families to the owner). Authored; the assembled families are unverified.

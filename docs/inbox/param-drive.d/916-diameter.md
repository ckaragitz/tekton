# #916 — a circle's diameter labelled with a family parameter

Stream: param-drive. Branch `diameter-916`, based on local `stack-all` (e206edb).

## What was built

- `src/rvt/famgen/diameter_law.py` (new). `wire_diameter(doc, caption=, sketches=)` labels
  the one circle of each sketch with a length or size parameter as its **diameter**.
  It writes the Revit-born form: an in-sketch `RadialDim` whose style is a `DimensionStyle`
  with `m_dimensionStyleType` 9 and whose value is 2 × the arc radius. The call is
  all-or-nothing, with every check made before the first mutation:
  - the document is not finalized;
  - the parameter exists and has a drivable spec;
  - each sketch holds exactly one circle in the plan plane that no `RadialDim` labels yet;
  - no sketch is listed twice;
  - the parameter's current value equals 2 × each circle's radius.

  The style is authored on first use and reused after that.
- `author_diameter_style` builds the type-9 style from this engine's **own** default-style
  constellation (`skeleton.new_dimension_style_constellation`): the style, its text / tick /
  centreline categories, their line styles and its font. The leader style is dropped,
  because the born no-arrow style references none. The type-9 fields are then set:
  `ø` prefix, symbol location 1, arrowhead and interior tick -1, radial tick 8, and the
  symbol name "Diameter". No donor bytes.
- `factory.make_generic_model(..., diameters=[{caption, parts}])` wires the specs after
  the height drives. A refused spec becomes a note and never raises (hard rule 1). The
  single-prism path says its diameters are NOT wired. `prod.diameters` reports the result.
- `archetypes.Archetype.diameters` (new field) and `_trapeze_diameters`: **Rod Diameter**
  labels both threaded rods. The rods' centres already follow Rod Inset (#904 P4). The
  trapeze `lod_note` now says the diameter is authored with no desktop verdict, and
  `limits` gained one item:
  - Rod Diameter is authored to drive the rods but is unverified;
  - it sits on a half arc, which no born diameter does;
  - the washers and nuts do not change with it.

  Rod Diameter left the "carry values and do not drive" list.

## Census (421-family private reference corpus — development instrument, counts only)

Scripts `census13.py` / `census14.py` live in the session scratchpad and are never committed.

- **Class and marker.** Every labelled diameter is a `RadialDim` whose style has
  `m_dimensionStyleType` 9 (67 / 67). Every labelled radius uses type 2 or 0 (274). Each
  type-9 dimension's segment holds 2r in `m_lockedValue` and `m_values[0]` (67 / 67);
  `m_values[1..2]` are -1, the segment flags are 0, and the text fields are None.
- **Style.** Every born file has exactly 2 own type-9 styles (421 / 421). Labelled
  diameters use the one without an arrowhead (`m_arrowHeadStyleId` -1), 67 / 67.
  Compared with the file's own default type-0 style (421 / 421), the differences are:
  - the fields `m_dimensionStyleType` 9, prefix U+00F8 vs "R", symbol location 1 vs 0,
    radial tick 8 vs 0, arrowhead -1, interior tick -1 (419);
  - its own text / tick / centreline category ids and font;
  - the symbol name;
  - its `m_pParamValueSetDouble` (our default set already equals a born type-9 set).

  Header flags are 14. The deletion list is [family, self, 3 CategoryElems, FontElem].
- **Dimension.** Every labelled diameter carries:
  - flags 12, `m_dimLockedForLabeling` True, `m_dimVersion` 6, view -1, `SketchMembership`;
  - one witness: id -1, an `ArcRef` with geomTag 0, a cached GArc with GInfo flags
    17301508, `m_pWitnessRefs` [].

  The cached arc spans [0, π] on 66 / 67. The header deletion is [Family, DimensionStyle,
  ParamElemFamily, VarSketch, CurveElem, self], with regenOnly = the sketch's SketchPlane
  on 56 / 67. The other 11 carry that SketchPlane in deletion with an empty regenOnly.
  Header flags are 10.
- **Header m_nVisibleViewFlags.** It is -1 on **4,308 / 4,308** in-sketch RadialDims,
  every labelled diameter included. -4225 occurs only on the 5 view-owned ones. This
  module writes -1. The P5 radius that passed on desktop carried -4225, the linear-dim
  constant.
- **Circle.** The labelled arc is one full GArc (endParams [0, 0]) on 66 / 67 and a
  partial arc on 1 / 67. A **half arc carries a diameter 0 / 67 times**.
- **Formula alternative.** 31 labelled radii are driven by `Radius = <diameter-named
  param> / 2` (or × 0.5); 62 labelled radii are X / 2 overall. The direct type-9 label (67) is the
  majority and is what this lane authors. Of the 67 labelled diameters, 33 are themselves
  formula-driven. Their specs: length 58, conduit size 8, pipe size 1.
- **Field diff.** A field diff of our written trapeze `RadialDim` against a born diameter
  on the corpus trapeze specimen, with ids normalised, leaves only:
  - the coordinates;
  - the seg/last-seg `m_id1` (born 263, ours 0, as in the verified P5);
  - the cached-arc orientation vectors.

  The style diff leaves header `m_familyId` (born = Family, ours -1) and `m_regenOnly`
  (born [-2], ours []). These two are the same as on our default linear style, which
  passed on desktop.

## Evidence (numbers)

- Trapeze (2 tiers): `diameters` wired 1/1 with 2 dims, both on Rod Diameter; 0 refused.
  rvt_validate: VALID, 0 errors, 0 warnings. `constraint_law.check_file` == [] on 2026
  and 2025.
- `tests/test_diameter_916.py`, 16 tests:
  - the read-back born-law field pin, on a 3-part model and on the trapeze in 2026 and
    2025;
  - 8 refusals, each written SHA-identical to the build without the spec: wrong value,
    non-length spec, missing param, box part, missing part, empty, listed twice, and one
    bad of three;
  - the good spec changes the bytes;
  - a direct-call refusal leaves the element count unchanged;
  - a second label on the same circle is refused;
  - two specs share one type-9 style;
  - the default linear style stays the first `DimensionStyle`. The SymbolIdMgr key-10
    registration takes the first one (#333).

## Honest gaps / open questions

- **No desktop verdict for any diameter (hard rule 4).** What passed on desktop is the
  labelled radius (P5). This lane differs from P5 in four things:
  - the type-9 style, with its own categories and font;
  - the value 2r;
  - the header visible flags -1;
  - the segment origin at the centre.
- **Half arc.** This engine draws a circle as two half arcs. The dimension goes on the
  [0, π] half: the arc P5 labelled, and the cached arc born dims carry. Born diameters
  are never on a half arc (0 / 67). If the desktop shows the other half not following,
  the next single-variable probe is a full-GArc circle, which the corpus prefers (66 / 67).
  That changes the profile sketch and the #904 P4 centre locks.
- **Default-type map.** Whether born documents register the diameter style in
  `SymbolIdMgr.m_defElementTypeMap` was not censused; ours registers only key 10, the
  linear default. P5's radial style was unregistered and passed.
- **Conduit: out of scope.** Its run is a horizontal cylinder (`cylinder_x`). Such a part
  keeps a vertical *authoring* sketch and only rotates its B-rep, so the plan-plane
  check in `circle_of` alone does not catch it.
  - The factory refuses any part whose B-rep is rotated, as a reported note: a label
    there would sit on a sketch Revit does not draw from (#591 round 4).
  - This refusal was found in the #929 review and is pinned by a SHA-identical test
    for `cylinder_x` and `cylinder_y`.
  - The conduit's "Outside Diameter" is also an archetype dimension, not a family
    parameter today.
- **Washers and nuts** do not change with Rod Diameter. Nut Across Flats is a value
  (1.5 d) and drives nothing.

## Suggested probe (for the batch harness, not staged)

1. `Diameter_A`: the trapeze as shipped. Flex Rod Diameter 3/8 in → 3/4 in. Expect both
   rods to grow about centres that keep following Rod Inset.
2. `Diameter_C`: the control. The same build with the style type left at 2 and the value
   at r (the P5 shape on a "Rod Radius" parameter).

## Review of #929 (head `90cbfab`, 🛑)

- **Horizontal cylinders.** They passed the plan-plane check, as described in the
  conduit gap above, and are now refused in the factory.
- **Partial mutation (not reachable today).** In `wire_diameter`, the style and the
  dimensions are authored one after another. A raise inside `_radial_dim` on a later
  sketch would leave the earlier ones wired. Every precondition is checked before the
  first mutation, and no input was found that raises there.
- **Wording.** The PR title says "labels … (authored, unverified)", never "drives".

## BRANCH STATE

**Files written**
- `src/rvt/famgen/diameter_law.py` (new)
- `src/rvt/famgen/factory.py`: the `diameters=` kwarg, wiring, report and notes
- `src/rvt/famgen/archetypes.py`: the `Archetype.diameters` field, `_trapeze_diameters`,
  and the trapeze `lod_note` / `limits`
- `plugin/lib/src/rvt/famgen/{diameter_law,factory,archetypes}.py` (mirrors, synced)
- `tests/test_diameter_916.py` (new), `tests/ci_shard.d/916-diameter.txt` (new)
- this fragment

**Gates**
- `tools/sync_plugin.py` rebuilt the plugin; `--check` is clean (deny-audit and identity
  scan match the allowlist).
- `plugin/scripts/validate_plugin.py` PASS (25 assertions).
- `check_portable_paths` ok (3351 paths).
- pytest batch 1: 393 passed. Files: test_diameter_916, conftest_scaffolding,
  archetype_drives_913, height_law_787, constraint_law_910, panel_drives_914,
  drive_follow_904, drive_law_904, strut_trapeze_899, family_anatomy_837, plugin_sync.
- pytest batch 2: 377 passed. Files: famgen_archetypes, lcp_clearance_820,
  famgen_size_bound_806, cylinder_tessellation_530, famgen_standards,
  standards_apply_safe.

**Shipped vs staged:** shipped wired, no viewer batch staged. The diameter is authored, and
the assembled family is unverified.

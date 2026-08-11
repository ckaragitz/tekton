# eng #628 — the circle verdict reads the outline's own minimum width, so it is the same at every yaw (2026-08-11)

*Fragment of the `ifc-assembly-rfa` stream (index: `docs/inbox/ifc-assembly-rfa.md`, left untouched),
written by engineer session eng #628 on branch `cam/628-caliper-width` from `main` @ 9152c86.
One PR, one voice; nobody else appends here (docs/inbox/README.md, #636).*

Refs #628 (this task), #620 / #626 (the law being corrected and the review nit that filed this), PG1.

## The defect, reproduced on `main` @ 9152c86 first

`_fit_circle` (as merged by #626) accepts a hull as a circle by three laws: (a) ≥ 8 hull points whose
radii agree to ±`CYLINDER_TOLERANCE` (0.12); the plan-fill floor `hull_area ≥ CYLINDER_MIN_PLAN_FILL
(0.85) × πr²`; and (b) `r ≤ 1.12 × min(ext[0], ext[1]) / 2` — where `ext` is the **world axis-aligned
bounding box**. (a) and the floor read the outline alone; (b) reads a box that grows toward the
half-diagonal as the body turns. So a body in the narrow band *fill 0.85–0.90 with r more than 12 %
over its narrowest half-width* got a yaw-dependent verdict. In memory (`fit_solid` on the point rings /
meshes in feet; the issue's five yaws):

| body | 0° | 10° | 22.5° | 30° | 45° |
|---|---|---|---|---|---|
| chamfered 1×1 square, c = 0.2 (fill 0.861, r / half-width 1.166) — **main** | polygon | **cylinder** | **cylinder** | **cylinder** | **cylinder** |
| same — **this branch** | polygon | polygon | polygon | polygon | polygon |
| double-D shaft r = 0.5, flats at 0.4 (fill 0.90, r / half-width 1.25) — **main** | polygon | polygon | **cylinder** | **cylinder** | **cylinder** |
| same — **this branch** | polygon | polygon | polygon | polygon | polygon |

(`main` before #626 said cylinder at every yaw for both; #626 made 0° honest and left the rest to the
bounding box.) Through the IFC path the flip is visible in what ships: `chamfered_square_yaw22.5.ifc`
routes on `main` to a single prism read as a **cylinder, fill 0.8613**, which the slab lane then
"improves" into a 16-vertex slab polygon (`slab decomposition improved Plinth (1 solids, fill 0.86 ->
1.00)`); the same body at 0° is its 8-vertex octagon straight away, no decomposition. Same body, two
different families depending on site north.

## What was built (territory: `_fit_circle`'s law (b) + one helper; nothing else in the module)

* **`_min_caliper_width(hull) -> float`** — the minimum width of the CCW convex ring `fit_solid`
  already computes: the closest pair of parallel supporting lines (rotating calipers). One of the two
  lines is always flush with an edge, so it is `min over edges of (farthest vertex from that edge)`,
  walked with the standard two-pointer (the farthest vertex only moves forward as the edge does):
  O(n), stdlib only, ~20 lines with its docstring. Degenerate input (< 3 points, collinear) → 0.0,
  which law (b) then refuses — such a hull never reaches law (b) anyway (radii spread).
* **Law (b) is now `r > (1 + CYLINDER_TOLERANCE) × _min_caliper_width(hull) / 2 → not a circle`.**
  The tolerance is unchanged and still right: half the minimum width of a regular N-gon is its
  apothem (even N) or `R(1 + cos π/N)/2` (odd N), so an 8-gon's circumradius is 8.2 % over, a 9-gon's
  3.1 %, every finer tessellation less — all inside 12 %. `_fit_circle` loses its `ext` parameter (law
  (b) was its only reader); the one call site in `fit_solid` passes `(hull, hull_area)`. The ≥ 8-point
  guard, law (a), the plan-fill floor, the cylinder / box / N-gon branches of `fit_solid`, every
  constant, the lanes, ring nesting and the #652 budgets are byte-intact.
* What the new law means in one sentence: **at every yaw a body now gets the verdict `main` gave it at
  its *strictest* yaw** (the minimum width equals the bounding box's smaller side at the yaw where the
  narrowest flats face an axis, and is smaller at every other yaw). Nothing that was a polygon at any
  yaw on `main` becomes a cylinder; the chamfered square and the two-flat shaft become their polygon
  everywhere. Expected and intended per the issue ("polygon is expected since r/apothem > 1.12").

**Why the O(n) walk and not the O(n²) one-liner** — both were written; the walk is what ships, the
brute force is the tests' oracle. Measured on this VM (regular n-gon hulls; `_decimate` shown because
`fit_solid` already pays it on the same large hulls, so neither choice changes the function's cost
class):

| hull points | walk | brute force | `_decimate(hull, 48)` already costs |
|---|---|---|---|
| 48 | 0.08 ms | 0.27 ms | 0.01 ms |
| 200 | 0.38 ms | 3.7 ms | 4.2 ms |
| 400 | 0.93 ms | 13.1 ms | 18.7 ms |
| 1000 | 1.6 ms | 96 ms | 119 ms |

The walk's only assumption is that distance-from-an-edge is unimodal round a convex ring, which float
noise could in principle dent on near-collinear runs; so it was checked against the brute force on
**5 430 hulls** — the yawed 4×1 U and 900 mm strut (the #620 bodies whose rounding noise keeps
near-collinear hull points) every 0.5° from 0 to 90°, a 64-, 360- and 2 000-gon pipe, each at the
origin, at (12 345.678, 9 876.5) ft and at (1e6, −2e6) ft, each both raw and through the STEP `%.6f`
rounding — **worst relative difference 0.0**; plus 300 random hulls (3–200 points, aspect 0.2–1, the
same three offsets): 0.0. A reduced version of that cross-check is a permanent test.

## Evidence

**In memory** (`fit_solid`, feet, meshes with their real `mesh_volume`, point rings without; probe
script kept out of the tree) — kind at each of the issue's yaws, `main` @ 9152c86 → this branch:

| body | 0° | 10° | 22.5° | 30° | 45° | change |
|---|---|---|---|---|---|---|
| chamfered 1×1 square c = 0.2 | polygon | cyl → **polygon** | cyl → **polygon** | cyl → **polygon** | cyl → **polygon** | one verdict now |
| chamfered square c = 0.15 (fill 0.816, under the floor) | polygon ×5 | | | | | identical |
| chamfered square c = 0.25 (r 11.8 % over) / c = 0.29 (8.5 %) | cylinder ×5 / cylinder ×5 | | | | | identical |
| double-D shaft, flats at 0.8 R | polygon | polygon | cyl → **polygon** | cyl → **polygon** | cyl → **polygon** | one verdict now |
| #620 U-channel 4×1×1 m | box | polygon | polygon | polygon | polygon | identical (fill 0.28) |
| #620 strut 900×41×41 mm | box | polygon | polygon | polygon | polygon | identical (fill 0.1755) |
| CONTROL pipe r = 50 mm, 12-gon / 16-gon | cylinder ×5 / cylinder ×5 | | | | | identical (r 0.1640 ft, fill 0.9549 / 0.9745) |
| CONTROL hollow tube 32-gon, 6 mm wall (fill 0.2242) | cylinder at 0 / 7 / 22.5 / 45° | | | | | identical |
| CONTROL rod r = 0.5, 48 points | cylinder ×5 | | | | | identical |
| regular N-gon prisms N = 8/9/10/12/24/64 × the 5 yaws | cylinder **30/30** | | | | | identical (**30/30**) |

**The sweep** (0…90° × 1°, 91 yaws per body, 364 fits): `main` — U 91 prism, strut 91 prism,
chamfered square **10 prism / 81 cylinder**, double-D **22 prism / 69 cylinder** → 2 of 4 bodies
yaw-dependent; this branch — 91 prism each, **0 of 4 yaw-dependent**. (The test module sweeps 0…90° ×
2.5° over the same four plus the 16-gon pipe: one verdict per body.) Total fits run for this record
≈ 1 900, per the CPU-modesty ask.

**Through the router** (`RVT_STEPLITE_FORCE=1 .venv/bin/python tools/route.py run --ifc X --output rfa
--out D --json`, the same IFC bytes against a worktree of `main` @ 9152c86 and this branch):

| IFC | main @ 9152c86 | this branch |
|---|---|---|
| `chamfered_square_yaw22.5.ifc` (1×1×1 m, c = 0.2, yaw 22.5°) | OK 1-part; single prism **cylinder fill 0.8613** → `slab decomposition improved Plinth (1 solids, fill 0.86 -> 1.00)`; ships a **16-point** slab polygon, `slabs 1` | OK 1-part **polygon fill 1.0, 8 points, no decomposition** (`decomposed: []`), i.e. exactly what 0° ships |
| `chamfered_square_yaw0.ifc` | OK 1-part polygon, 8 points, fill 1.0 | identical |
| `pipe16_yaw7.ifc` (control) | OK 1-part cylinder r = 0.164042 ft, fill 0.9745 | identical |

Every one of the six `.rfa` (3 per tree): `tools/rvt_validate.py --family` **VALID (no errors);
warnings=0 info=2**; `tools/make_family.py provenance` **ok: true, findings []**. Transcript of the
22.5° run on this branch, trimmed to the assembly lines:
```
$ RVT_STEPLITE_FORCE=1 .venv/bin/python tools/route.py run --ifc chamfered_square_yaw22.5.ifc --output rfa --out D --json
ok= True | OK (1-part generic_model .rfa measured from chamfered_square_yaw22.5.ifc) by the ASSEMBLY lane, after the archetype lane failed at facts->rfa
  caveat: ASSEMBLY LANE: 1 IFC product(s) measured into prisms (polygon x1), overall 45.41 x 45.41 x 39.37 in; every dimension is GIVEN by your mesh …
  parts: Plinth polygon fill=1.0 polygon_points=8 slabs=0   decomposed: []   kept_prism: []   fit_counts: {'polygon': 1}
  validate: VALID (no errors); warnings=0 info=2      provenance: ok, findings []
```
(on `main` the same command adds `caveat: slab decomposition improved Plinth (1 solids, fill 0.86 -> 1.00)`
and reports `polygon_points=16 slabs=1`.)

`tools/route.py matrix`: sha256 `7dae5d40eb461e9a…` on both trees — **byte-identical** (no cell, caveat
or evidence line changes; this is a geometry fix inside a "works" cell).

**Tests** — a new module `tests/test_ifc_assembly_628.py` (29 tests) + drop-in
`tests/ci_shard.d/628-caliper-width.txt`; `tests/test_ifc_assembly.py` is imported from for its
fixture generators and **not edited** (#636; the issue text predates that convention and said "append",
the tech-lead brief said new module — the brief wins). What they pin: the helper's textbook widths for
regular 3…64-gons; a 2×1 rectangle is 1 wide at all 37 yaws while its bounding box's short side reaches
2.12; walk == brute force on the noisy yawed hulls above with a 120-gon pipe (260 hulls incl. site
coordinates and `%.6f`);
the chamfered square c = 0.2 is its 8-vertex polygon at all 37 yaws and at the issue's five by name;
chamfers 0.15 / 0.18 / 0.22 → polygon and 0.27 / 0.29 → cylinder, each ONE verdict over the sweep; the
double-D shaft is never round; site coordinates (1e6, −2e6 ft) do not change any verdict; the #620 U and
strut are box at 0°/90° and polygon between, fill 0.28 / 0.1755, at all 37 yaws; the 12/16-gon pipe is
a cylinder with exact r and fill at all 37; a hollow 32-gon tube is a cylinder holding 12–25 %; regular
8…64-gons are cylinders at 0/5/11.25/22.5/30°; and end-to-end through
`write_ifc` → `read_assembly` the chamfered square at 0° and 22.5° is the same single 8-vertex polygon
part of plan area 0.92 m². **Against `main`'s `assembly_parts.py` 14 of the 29 fail** (the 9 helper
tests by `AttributeError`, and 5 by behaviour: the c = 0.2 square, c = 0.22, the double-D, site
coordinates, the routed 22.5° square = 16-point slab); on this head **29 pass** in ~0.3 s. (`/simplify`
folded a sixth, whole-sweep no-flip test into the per-body ones it duplicated, and reuses
`test_ifc_assembly._fit_m` and `_prism_mesh`'s triangulation instead of copies.)

## BRANCH STATE (eng #628)

Branch `cam/628-caliper-width` from `main` @ 9152c86; one issue, one PR (`Closes #628`).
Files: `src/rvt/ifc/assembly_parts.py` (`_min_caliper_width` new, `_fit_circle` law (b) + docstring +
signature, its one call site, the `CYLINDER_TOLERANCE` comment) + its `plugin/lib` mirror via
`tools/sync_plugin.py`; `tests/test_ifc_assembly_628.py` (new); `tests/ci_shard.d/628-caliper-width.txt`
(new); this fragment (new; the index `docs/inbox/ifc-assembly-rfa.md` is not edited). Not touched: the
lanes, ring nesting, budgets, `router.py`, famgen, `tools/route.py`, SKILL.md, `tests/test_ifc_assembly.py`,
any hot file.

Gates on the final tree:
* `RVT_SKIP_LARGE=1 RVT_STEPLITE_FORCE=1 pytest tests/test_ifc_assembly_628.py tests/test_ifc_assembly.py
  tests/test_ifc_assembly_623.py tests/test_router.py tests/test_records_layout.py -q -rs`: main (worktree,
  without the new module) **241 passed / 14 skipped** (test_ifc_assembly 96, _623 8, router 132 + 14
  skipped, records_layout 5) → branch **270 passed / 14 skipped**, 0 failed (the same 14 skips: 13 ×
  `RVT_SKIP_LARGE` / ifcopenshell-absent in test_router, 1 × chmod-as-root);
* whole merged CI shard (`RVT_SKIP_LARGE=1 pytest -q -p no:cacheprovider $(python3 tools/dev/shard_list.py --print)`,
  111 files incl. the new drop-in): see the PR body for the count on the final head;
* `tools/route.py matrix` byte-identical to main (sha256 7dae5d40…); 6 routed `.rfa` VALID 0 errors 0
  warnings + provenance ok / findings [];
* `tools/sync_plugin.py` → rebuilt, then `--check`: in sync (deny-audit clean, identity scan ==
  allowlist); `plugin/scripts/validate_plugin.py` PASS (25 assertions); `tools/dev/check_portable_paths.py`
  ok; `shard_list.py --print` resolves the drop-in.

Nothing staged for the viewer, no ledger entry, no certification claimed (rule 4): "VALID" above is a
fact about the files, not about Revit. No follow-up issues needed: the band this closes was the last
yaw-dependent input to `_fit_circle` (law (a), the floor and now (b) all read the hull alone).

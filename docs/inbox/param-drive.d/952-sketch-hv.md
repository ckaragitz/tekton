# #952 — the sketch writer's HV constraint only on axis-parallel lines; CG11

Stream: param-drive. Issue: #952. Branch `fix-952`, based on `main` `7d2fcde`
plus the not-yet-merged #953 CG7 commit (cherry-picked as `b10f7c9`'s content,
so the two `constraint_law.py` changes do not conflict; #953 merges first).
Territory: `src/rvt/famgen/geometry.py`, `src/rvt/famgen/constraint_law.py`
(+ their `plugin/lib` mirrors), `tests/test_sketch_hv_952.py`,
`tests/ci_shard.d/952-sketch-hv.txt`, this fragment, and a dated correction in
`916-run-arc.md` (#955 review nit). Not touched: `nest.py`, `angular_law.py`,
`famload.py`.

## The problem

`geometry.new_var_sketch` (every straight-line profile sketch: `prism_form`)
put a `VarSketchHorVerConstrObj` on **every** line, with `m_hor` chosen by the
line's dominant axis. On a non-rectangular profile (the generic polygon prism,
the solid trapeze's eight hex nuts) that constrains a slanted line to be
horizontal or vertical: the solver state contradicts the geometry it holds.
#948's `angular_law` already re-shapes the nested nut's hexagon; nothing fixed
the other polygon sketches. It also wrote `m_angleCoef` = 1.0 on every line,
while born files often carry the line length.

## Census

Instrument: every `VarSketch` with solver records in every document unit of the
421-family born library (git-ignored development instrument; counts only, no
names) — 421 host documents + 4,425 nested units, 0 read errors; 398 files
carry solver records. Per solver line (`VarSketchLineSegObj`, 4 parameters
x1, y1, x2, y2): slope class (horizontal / vertical when the off-axis extent is
≤ 1e-9 × max(1 ft, length), else slanted), the HV constraints naming it, its
`m_angleCoef`, and sketch / line features. All 421 files declare release 2025
in `BasicFileInfo`, so release is not a variable this corpus can test.

### 1. When born sketches carry HV

| | all units | host |
|---|---:|---:|
| solver lines | 77,002 | 17,103 |
| horizontal lines with an HV, `m_hor` True | 32,046 | 7,614 |
| vertical lines with an HV, `m_hor` False | 29,987 | 6,595 |
| HV with `m_hor` disagreeing with the line's axis | **0** | **0** |
| **slanted lines with an HV** | **0 / 14,219** | **0 / 2,704** |
| axis-parallel lines without an HV | 750 / 62,783 | 190 / 14,399 |
| lines with more than one HV | 0 | 0 |

- The slanted line nearest an axis is 6.3e-8° off it (4 lines under 1e-6°,
  7 under 0.01°) — none carries an HV, so a 1e-9 relative tolerance separates
  the two classes with room either side.
- **Which axis-parallel lines lack it:** all 750 sit in sketches with
  `m_highResidualTol` True (750 / 750); in the 9,603 sketches with
  `m_highResidualTol` False, **21,753 / 21,753** axis-parallel lines carry one.
  The 750 are in 316 sketches; their other solver constraints are PP joins
  only (661), point-on-line (30), PP + point-on-line (27), PP + tangent (16),
  none (13), distance (3). 459 of them are in sketches with no HV at all.
- Polygon sketches are common: 4,206 of 18,144 line-bearing sketches have a
  slanted line (2,415 of them `m_highResidualTol` False); their axis-parallel
  lines carry an HV like any other (15,169 with, 76 without).

**Rule:** a sketch without `m_highResidualTol` (every sketch this writer emits)
carries one HV on each axis-parallel line, `m_hor` = horizontal, and none on a
slanted line.

### 2. When `m_angleCoef` is 1.0 vs the line length

| `m_angleCoef` | all units | host |
|---|---:|---:|
| = line length | 36,362 | 11,494 |
| = 1.0 | 36,799 | 4,216 |
| neither (ratio to length spread 0.04 – 48) | 3,841 | 1,393 |

(The issue quoted 28,197 length / 22,074 1.0 from a different scope; this
instrument's counts are the table above.)

| split by | length | 1.0 | neither |
|---|---:|---:|---:|
| sketch `m_highResidualTol` **False** | **0** | **26,561** | **0** |
| sketch `m_highResidualTol` True | 36,362 | 10,238 | 3,841 |
| — of those, sketch has dimensions (`m_dimIds`) | 33,654 | 363 | 2,857 |
| — of those, sketch has none | 2,708 | 9,875 | 984 |
| line witnessed by an `AngularDim` | 364 | 1 | 9 |
| line slope H / V / slanted | 14,232 / 14,854 / 7,276 | 16,444 / 13,738 / 6,617 | 1,728 / 1,787 / 326 |

Per sketch: 9,603 / 9,603 `m_highResidualTol`-False sketches are all-1.0; of
the 8,541 True ones 5,520 are all-length, 1,753 all-1.0, 534 all-"neither",
734 mixed. Line kind (slope), sketch kind (lines only / with arcs / with
ellipses) and witnessing do not separate the classes; `m_highResidualTol` does
completely on one side.

**Rule:** `m_highResidualTol` False ⇒ `m_angleCoef` 1.0 (26,561 / 26,561).
Inside `m_highResidualTol` sketches the value tracks the solver's history
(length mostly when the sketch is dimensioned; "neither" values look like a
stale length) — not something we can model, and not needed: our generic
sketches are `m_highResidualTol` False, so **1.0 is already the born value for
them and stays**. `angular_law` (the only writer of `m_highResidualTol` True)
already writes the length, as its census found. No change to `m_angleCoef`.

## Built

- **`geometry.new_var_sketch`**: emits `VarSketchHorVerConstrObj` only where
  `constraint_law.line_axis` says the line is horizontal (`m_hor` True) or
  vertical (`m_hor` False); a slanted line gets none. The interleave order
  (HV0, then per line its corner joins and its HV) is unchanged, minus the
  dropped records. `m_angleCoef` 1.0 kept, with the census in the comment.
- **`constraint_law.line_axis`** + `HV_AXIS_TOL` (1e-9 × max(1 ft, length)):
  the one predicate the writer emits by and CG11 judges by.
- **CG11** (next free id; CG1–CG10 exist, CG2 retired): every
  `VarSketchHorVerConstrObj` of a `VarSketch` names a solver line along its own
  axis — horizontal for `m_hor` True, vertical for False — read from the
  line's own four solver parameters. HVs naming a non-line or an unresolved
  pid are not judged. Runs in `check_graph` (so `check_doc` and `check_file`,
  host and nested units).
- **#955 nits**: `new_full_arc_curve_elem`'s docstring names
  `m_nextMidParamId` = 4 as engine convention alongside the curve `m_GInfo`
  flags and the guess cache's `m_nPar`; `916-run-arc.md` carries a dated
  correction (base `3e03fd3`, not `3f575d3`; 9 functions / 16 cases, not
  11 / 16).

## Evidence

**CG11 over the born library** (all 421 host documents + 4,425 nested units,
`check_file` per unit): **0 CG11 findings**. (The same sweep reports 236 CG5
findings in nested units and none in host documents — pre-existing, not CG11,
not touched here.) Fires on synthetic violations: an HV added to a slanted
line, an HV with `m_hor` flipped on a rectangle, and the pre-#952 writer's
triangle prism (2 findings, one per slanted edge).

**Bytes, base (`7d2fcde` + #953) vs this branch**, fixed output path, sha256,
built and written in process per release:

| product | 2026 | 2025 | HV before → after |
|---|---|---|---|
| conduit, prism (rectangle), IFC downlight, panelboard, transformer, cable tray, wireway, junction box, strut channel, LCP, nested trapeze | identical | identical | unchanged (0 / 4 / 20 / 36 / 164 / 64 / 16 / 24 / 20 / 28 / 160) |
| prism, triangle profile | changed | changed | 3 → 1 |
| prism, hexagon profile | changed | changed | 6 → 2 |
| solid trapeze (8 hex nuts) | changed | changed | 240 → 208 |

In every changed file the ONLY records that differ are seq-102 `VarSketch`
objects (1 / 1 / 8 records), each smaller by 43 bytes per dropped HV
(−86 / −172 / −1,376 payload bytes); file sizes are unchanged (CFB sectors).
The nested trapeze is identical because `angular_law` re-shapes its hexagon
to the census form either way (its `hv_dropped` report figure falls from 5 to
1 per nut — the generic writer now leaves only the two flats' HVs for it).
Every build: `rvt_validate` family mode 0 errors; `constraint_law.check_file`
== [] on the host and on every nested unit (2 in the nested trapeze), both
releases. The test file re-proves the byte split by re-running the old rule
(monkeypatched `line_axis`) and asserting rectangle products hash identical,
polygon products not.

**Build time** (build + write, 2026, solid trapeze — the largest polygon
product; base = the old rule): 6 interleaved runs each, old rule median 1.403 s (min 1.269 s), new
median 1.392 s (min 1.286 s): no measurable change (the dropped records are
43 bytes each; the predicate is a few float compares per line). Single-run
build+write of the triangle prism: 0.21 s → 0.17 s (2026), within noise.

**Tests**: `tests/test_sketch_hv_952.py` 11 functions / 24 cases: 22 passed, 2 corpus
cases skipped without `samples/` (CI shape); with the library present both corpus
cases pass (every-20th-file sample host + nested 19 s; full 421 host + nested
sweep 427 s, `@slow`, skipped under `RVT_SKIP_LARGE`).

## Gaps / open questions

- `angular_law`'s docstring still says "the generic sketch writer puts one on
  every line, slanted ones included"; now stale — `angular_law.py` was out of
  this PR's territory (another PR in flight). One-line follow-up.
- The 750 axis-parallel born lines without an HV (all in
  `m_highResidualTol` sketches) are not modelled; we never write such a
  sketch outside `angular_law`.
- `m_angleCoef` inside `m_highResidualTol` sketches: length on 36,362, 1.0 on
  10,238, other on 3,841 — no rule found that our writer could apply; left
  to `angular_law`'s own census (length on angular-witnessed lines).
- The corpus is release 2025 only; the HV rule is release-independent in our
  writer by construction, unverified on 2026/2024-born sketches.
- Nothing here is a Revit claim (hard rule 4): whether Revit's solver treats
  an HV on a slanted line as an error, or re-solves silently, is unknown; the
  change removes a contradiction our own law can see.

## BRANCH STATE

**Files written**
- `src/rvt/famgen/geometry.py` (HV only on axis-parallel lines; #955 docstring
  nit), `src/rvt/famgen/constraint_law.py` (`line_axis`, `HV_AXIS_TOL`, CG11)
  + `plugin/lib/src/rvt/famgen/` mirrors via `tools/sync_plugin.py`.
- `tests/test_sketch_hv_952.py` (new) + `tests/ci_shard.d/952-sketch-hv.txt`.
- `docs/inbox/param-drive.d/916-run-arc.md` (dated correction section only).
- This fragment.

**Gates**: `RVT_SKIP_LARGE=1` batch — `test_sketch_hv_952`,
  `test_constraint_law`, `test_constraint_law_910`, `test_cg7_953`,
  `test_angular_eq_948`, `test_trapeze_nested_917`, `test_run_arc_916`,
  `test_drives_rest_913`, `test_archetype_drives_913`, `test_famgen_archetypes`,
  `test_ifc_assembly`, `test_plugin_sync`: **499 passed / 3 skipped / 0 failed**
  (123 s). `tools/sync_plugin.py` rebuilt, `--check` clean;
  `plugin/scripts/validate_plugin.py` PASS (25 assertions);
  `tools/dev/check_portable_paths.py` ok (3,425 paths); `tools/self_battery.py`
  26 / 26 PASS (`prism_polygon_law`, `archetype_strut_trapeze` among them).

**Shipped vs staged**: the writer change is the default for every
straight-line profile sketch. Nothing staged for a viewer or desktop round; no
byte/sha test needed re-pinning (none pins a polygon product's hash).

# #948: the nested hex nut's Nut Across Flats drives a regular hexagon

Stream: param-drive. Issue #948, the follow-up to #940's census 2 ("Nut Across
Flats is value-only"). Branch `fix-948`, based on `main` a737087.

The census reads the owner's reference library (421 born families, git-ignored,
development instrument only). Only counts and field facts are cited; no
specimen name, parameter name or value reaches the output.

## Census 1: every `AngularDim` in the library

387 `AngularDim`s in 62 files (113 document units; 74 in host documents, 313 in
nested ones).

| Field | Count |
|---|---:|
| witnesses / segments: **2 / 1** | **387 / 387** (no angular dimension has 3+ witnesses) |
| `m_dimVersion` 6 | 387 |
| `m_flags` 12 / 13 | 377 / 10 |
| segment `m_flags` 1 (LOCKED) / 0 | 203 / 184 |
| locked values: 60° / 90° / 45° / 10° / 3° | 160 / 21 / 17 / 3 / 2 |
| labelled (segment `m_paramId` ≥ 0) | 163 |
| sketch member (`SketchMembership`) | 357; all 357 owned by no view (object and header -1), in the sketch's `m_dimIds` 357 / 357, in its `m_dimData` 0 / 357 |
| not a sketch member | 30, all owned by a view |
| header category -2000260, flags 10 | 387; visible-view flags -1 379, -4225 8 |
| witness class `GeomSegInPlaneRef` | 387 / 387 |
| witness targets: two curves / curve + plane / other pairs | 246 / 90 / 51 |
| `m_pDimArc` a `GArc`, pid 3, GInfo flags 524292, endParams [0, 0] | 387 / 387 |
| text fields on segment values | 0 / 387 |

> **Recount (review of #954), 2026-10-02. Counts only.** A reviewer recounted
> **502** `AngularDim`s in **71** files, **164** of them locked at 60°. The
> table above says 387 in 62 files (113 units), with 160 locked at 60°. A
> scratch script (not committed) recounted the same 421-file library under
> its own release, with 0 read errors, and reproduces the reviewer's figures
> under every enumeration that includes unit 0:
>
> | Units enumerated | Dims | Files | Units | Locked 60° | Host / nested |
> |---|---:|---:|---:|---:|---:|
> | every unit `FamilyIndex.units` holds (4,846 units, 421 with no GUID = unit 0) | 502 | 71 | 156 | 164 | 74 / 428 |
> | unit 0 + `unit_by_guid` (the reviewer's) | 502 | 71 | 156 | 164 | 74 / 428 |
> | the same, each nested GUID counted once across the library | 502 | 71 | 156 | 164 | 74 / 428 |
> | `unit_by_guid` only (nested, no unit 0) | 428 | 59 | 136 | 154 | 0 / 428 |
>
> No unit shares a GUID within a file or across files, so the enumerations
> that include unit 0 agree. The host count (74) matches the table. The
> nested count does not: 428 here against 313 in the table. No enumeration
> tried reproduces 387 / 62 / 113 / 160, so that row's unit selection is not
> known. The 156 units match this record's own law-run count ("units with an
> `AngularDim`, 156", below). **Read Census 1's totals as 502 / 71 / 156 /
> 164.** The per-field rows of the table were not recounted. Their
> denominators are those of the 387-dimension selection. Their conclusions
> (no angular EQ; every hexagon angle a locked π/3) were not re-checked on
> the 502. Census 2's 32 hexagons are a separate count.

**Correction to #940.** The #940 record called the hexagon's angular
dimensions "5 EQ `AngularDim`s". They are not EQ: each has one segment,
segment flags 1 (locked) and value π/3 (160 / 160). The "EQ" came from counting
a non-empty `m_ArrEqualityFormulaInfo` array, which every dimension carries as
a placeholder. The library has no angular EQ at all (0 / 387).

## Census 2: the hexagon recipe, role by role

All 32 labelled hexagons (23 files, 7 distinct families) carry the same 11
constraints. Every one is a sketch member of the hexagon's own sketch, owned by
no view, header regen = that sketch's plane (32 / 32 each). The flats are
square to y in all 32. The lines run CCW and are named H0..H5 from the
bottom-right slant: Q0, Q1, Ft (top flat), S', S, Fb (bottom flat).

| `m_dimIds` | Constraint | Witness constrFlags / endIdx / id | `m_dimData` |
|---|---|---|---:|
| 0-4 | locked 60° `AngularDim` (Fb,Q0) (Q0,Q1) (Q1,Ft) (Ft,S') (S',S) | (0,0,0) (0,1,1) | — |
| 5 | EQ Ft \| Ppar \| Fb, `m_flags` 140, segments 2 / 2 | (0,0,0) (16,1,1) (0,1,2) | 3 |
| 6 | EQ Fb.start \| Pperp \| Fb.end (subTags 0 / 1) | (0,0,0) (16,0,1) (0,0,2) | 0 |
| 7 | EQ S'.start \| Pperp \| Ft.start | (0,0,0) (16,1,1) (0,0,2) | 0 |
| 8 | **label**: S to the origin point (`CurveXCurveInPlaneRef`, Pperp × Ppar, idx 0, orientation 0), measured along S's inward normal (32 / 32) | (0,0,0) (0,0,1) | 3 |
| 9 | **label**: Fb to Ppar | (0,0,0) (0,0,1) | 3 |
| 10 | zero-length pin of the S/S' corner on Ppar: category -2000261, `m_flags` 28, drawn in a **secret internal dimension style** that brings its own category, font and leader elements | (0,0,1) (0,0,0) in 31, (0,0,0) (0,0,1) in 1 | 1 |

- **Angular geometry** (160 / 160 each): w0 = A with its ends in order, w1 =
  B reversed; A ends where B starts; the arc is centred on that vertex;
  `m_refPnts` lie on the two rays back from the vertex at the arc radius; the
  text sits on their bisector; `m_2ArcAngle` False. The radius is 13-38× the
  side, a cosmetic choice.
- **The labels**: one instance formula parameter (32 / 32, #940). Value =
  across flats / 2. Text fields absent on every hexagon dimension (192 / 192).
- **The sketch**:
  - `m_highResidualTol` True: 32 / 32. Every sketch with an angular dimension
    has it, 112 / 112.
  - Solver constraints: six point-point joins and **one** horizontal
    `VarSketchHorVerConstrObj`, on Ft, in one fixed order (32 / 32).
  - `m_angleCoef` = the line's length on 348 / 358 angular-witnessed lines.
  - Every curve carries GInfo bit 0x80000 (192 / 192).
  - `m_regenOnly` = [Level, Ppar, Pperp] (32 / 32).
- **Ownership**: in host documents, every sketch-member dimension is owned in
  the `ElemTable` by its sketch. That holds for 26,335 / 26,335 linear, 66 / 66
  angular and 2,666 / 2,666 alignments. Non-members are owned by the Family.
- **Schema**: `AngularDim` and `CurveXCurveInPlaneRef` exist, with the same
  fields, in the bundled 2026, 2025 and 2024 schemas.

## Built

**`src/rvt/famgen/angular_law.py`** (new)

- `new_angular_lock`: a locked `AngularDim` in the census shape.
- `new_sketch_dim`: a sketch-member labelled or EQ `LinearDimString` over
  curve, curve-end, plane or plane-crossing witnesses.
- `hexagon_roles`: refuses anything but a regular hexagon centred on the origin
  with its flats square to y, CCW and chained.
- `wire_hexagon_drive` writes the recipe. All checks run before the first
  mutation (all-or-nothing). It checks:
  - the parameters exist and are length parameters;
  - the half parameter's formula is `<caption> / 2`;
  - every type's values agree with the geometry;
  - the hexagon is unconstrained and the sketch registers no dimension;
  - the solver records are the six lines, with exactly six PP joins plus HV
    locks.

  It writes:
  - the 11 constraints and the sketch's `m_dimIds` / `m_dimData`;
  - deletion and regen = Level + both origin planes;
  - the census solver state: HV only on Ft, in census order (the generic
    writer put an HV on all six lines, including the slanted ones);
  - `m_angleCoef` = side, `m_highResidualTol`, and the curve bit;
  - every dimension owned by its sketch.
- **One substitution, stated in the module, the notes and here.** Position 10
  (the secret-style corner pin) becomes a second labelled dimension, S' to the
  origin point, in the exact shape of position 8. Both remove the last degree
  of freedom: with S and S' each at across-flats / 2 from the centre at fixed
  angles, their corner lies on Ppar. Authoring the secret style would mean
  authoring its category, font and leader elements, which the census only saw
  inside Autodesk-born files. So 10 of the 11 constraints are the born shape
  field for field.

**`src/rvt/famgen/trapeze_nested.py`**

- The nut child is drawn in the census orientation (`hex_ring`: flats square to
  y, ring from the 300° corner). That puts it 90° from the solid trapeze's nut,
  which is unchanged.
- `Nut Half Across Flats` (instance, formula `Nut Across Flats / 2`) labels the
  three labels.
- Width = corner and Depth = across flats, following the rotation.
- A refused wiring still builds the nut, with "VALUE ONLY" in its notes.
- The product notes say which case happened.

**`src/rvt/famgen/drive_law.py`**

`apply_born_inplane_law` item 7 skips sketch-member labelled dimensions. A
sketch-member label keeps regen = its sketch plane (64 / 64). Item 7's
[UnitsElem] is the census of plane-to-plane labels. No existing product has a
sketch-member label, so no existing bytes change.

**`src/rvt/famgen/constraint_law.py`**

- `AngularDim` is a constraining class.
- **CG5** shapes it: at least 2 witnesses, one segment per gap.
- **CG6** now covers every sketch-member constraint, not only sketch locks.
- **CG9**: each locked angle equals the angle between its two sketch lines
  (either supplement). An angular EQ's segments are equal; there are 0 born
  angular EQs, so that part is judged on synthetic graphs only. An arc-centre
  check was tried and dropped: 19 of 36 judged born host angular dimensions
  draw the arc away from where their lines cross.
- **CG10**: a `LinearDimString` whose witnesses all resolve stores, on every
  locked, labelled or EQ segment, the distance between its witnesses along the
  dimension line, and its EQ segments are equal. A witness resolves when it is
  one of:
  - a plane square to the line;
  - a sketch line square to it;
  - a line end;
  - the crossing of two planes.

  Anything else is unjudged.
- `CG1` reads both planes of a crossing witness.
- `check_file(path, unit=…)` and `nested_units(path)` judge a nested family's
  own document.
- **#949 review nits**:
  1. `_cg8_frame` now reports a missing `m_constrDir`, `m_refPnts` or
     `m_oldOrigin` as a CG8 **WARNING** naming the field. It was silently
     skipped before. `check_file == []` still holds on our outputs, because the
     nest writer emits all three.
  2. `cg8_pick` is the one selection rule, shared by `_cg8` and
     `judged_instance_locks`.

  `test_nest_locks_917`'s synthetic lock now carries a full frame.

## Evidence (numbers read back from written files)

**The law over the born library.**

- Host documents, all 421 files (`check_file`). Base (main) vs this branch:
  - Base: 139 CG7 errors, 368 clean files.
  - This branch: the same 139 CG7 errors and 368 clean files, so it adds 0
    findings. CG10 judged 5,836 born dimensions (2,902 of them sketch members)
    with 0 findings. CG9 judged 36 host angular dimensions (21 locked segments)
    with 0 findings. CG8 judged 2,393 frames with 0 frame-absent warnings:
    every born lock carries all three fields.
- Every document unit that holds an `AngularDim` (156 units, host and nested):
  - CG9 judged 214 dimensions (175 locked segments): 0 findings.
  - CG10 judged 2,055 dimensions: 0 findings. That includes all 32 hexagon
    slant labels through the plane crossing and 880 with a line-end witness.
  - CG6 on sketch-member dimensions: 0 findings.
  - The CG5 (54) and CG7 (51) findings in nested units come from existing
    rules and are unchanged by this pass.

**Our output, 2026 and 2025.** Checked on the standalone nut and on the
default nested trapeze:

- `tools/rvt_validate.py`: 0 errors, 0 warnings, all four files.
- `constraint_law.check_file` == [] on the host, and on every nested unit via
  `unit=`.
- The 11 hexagon dimensions match the census table role for role (positions
  0-9 exactly; 10 is the stated substitute). The test pins the full table.
- 5 `AngularDim`s, each locked at π/3 (exact to 1e-12), in the nested nut unit.
- `judged_instance_locks` still covers all 48 instance locks: 16 instances ×
  {1, 4, 7}.
- The sketch dimensions are owned by the sketch in the `ElemTable`.
- Nut Half Across Flats is written as `BinaryOperatorExpression /` of Nut Across
  Flats, instance, value AF / 2.
- CG9 and CG10 **judge** the hexagon, not merely pass it:
  - a tampered copy (angle 45°) is caught by CG9;
  - a doubled EQ gap, a wrong flat label and a wrong slant label are each
    caught by CG10.
- Refusals leave the document identical (snapshot equality) in five cases:
  - rotated hexagon;
  - wrong formula;
  - type value disagrees;
  - already wired;
  - finalized document.
- Any across-flats (7/16, 9/16, 1 1/8 in) writes a valid, law-clean nut.
- Determinism: two builds give identical streams.

**Cost** (2026, warm process, median of 3): solid trapeze write 1.52 s, nested
2.48 s (1.6×).

## The default: stays SOLID

Re-decided against DONE 4. The nut now has the advantage it lacked in #940:
Nut Across Flats drives the hexagon inside the file. That still does not make
the nested lane the safer deliverable:

1. **No desktop verdict for any of it** (hard rule 4).
   - `AngularDim` has never been authored by this engine before. A desktop
     verdict exists for no hexagon drive and for no nested lock, height locks
     included.
   - Validator green and an empty CG5-CG10 report are facts about the file.
     They do not show that Revit regenerates the hexagon when Nut Across Flats
     changes, or moves a locked nested instance.
2. **One born element is substituted** (the corner pin). It is
   degree-of-freedom equivalent on paper, but whether Revit's solver treats it
   the same is unverified.
3. **Cost**: the nested lane is 1.6× the solid write.

What would flip it: a desktop verdict, through the unattended harness (steer
#765, no click ladder to the owner), that

- a nested hex nut regenerates as a regular hexagon when Nut Across Flats
  changes, and
- a nested instance follows a host height change.

## Gaps, stated plainly

1. **No desktop verdict** (hard rule 4) for the hexagon drive or the
   substitution.
2. **The corner pin is substituted, not authored.** The secret internal
   dimension style constellation is not built.
3. **Finding outside this territory, `geometry.py`.** The generic sketch writer
   puts a `VarSketchHorVerConstrObj` on **every** line, classifying slanted
   lines as horizontal or vertical. Born writes one per axis-parallel line it
   needs, and the hexagon has exactly one. Any non-rectangular polygon sketch
   carries solver constraints that contradict its own geometry if Revit
   re-solves it. That includes the solid trapeze's nut and every `polygon`
   part. Fixed here only for the hexagon being wired. A generic fix changes
   the bytes of every polygon product, so it is its own issue.
4. **Same file, `m_angleCoef`.** The generic writer writes 1.0. Born writes the
   line length in 28,197 line objects and 1.0 in 22,074 (348 / 358 on
   angular-witnessed lines). It is set here only for the hexagon.
5. **CG7 is not born-clean**: 139 errors in host documents of the born library
   on `main` already, unchanged here. Worth its own look.
6. **Annotation placement is cosmetic and not census-derived**: the arc radius
   (4× the side) and the dimension-line offsets (3× the side).
7. The nested nut's hexagon is 90° from the solid nut's. The dimensions and
   the hexagon are the same; only the look differs.

## BRANCH STATE (`fix-948`)

**Files written**
- `src/rvt/famgen/angular_law.py` (new)
- `src/rvt/famgen/trapeze_nested.py`: `hex_ring`, `NUT_HALF_ACROSS_FLATS`, the
  nut wiring, `_nut_child`, notes, docstring
- `src/rvt/famgen/drive_law.py`: item 7 skips sketch members
- `src/rvt/famgen/constraint_law.py`: AngularDim, CG5/CG6 widened, CG9, CG10,
  `check_file(unit=)`, `nested_units`, the CG8 frame warning, `cg8_pick`,
  docstring
- `plugin/lib/src/rvt/famgen/{angular_law,trapeze_nested,drive_law,constraint_law}.py`:
  sync mirrors
- `tests/test_angular_eq_948.py` (new, 45 tests) and
  `tests/ci_shard.d/948-angular-eq.txt`
- `tests/test_trapeze_nested_917.py`: the nut's labels follow the new truth
- `tests/test_nest_locks_917.py`: the synthetic lock carries a full frame
- this fragment

**Gates**
- `sync_plugin.py`, then `--check`: in sync. `validate_plugin.py`: PASS (25).
  `check_portable_paths.py`: ok.
- `pytest`: **241 passed, 0 failed** over these files:
  - `test_angular_eq_948`, `test_nested_heights_940`, `test_trapeze_nested_917`;
  - `test_nest_917`, `test_nest_locks_917`, `test_drive_law_904`;
  - `test_constraint_law`, `test_constraint_law_910`, `test_height_law_787`;
  - `test_panel_drives_914`, `test_plugin_sync`.
- Born-library law runs (scratch instruments, counts above): host documents,
  421 files; units with an `AngularDim`, 156.

**Shipped vs staged:** the opt-in nested lane ships the hexagon drive. The
default is unchanged (solid), and no route uses the lane. Nothing is staged,
and no viewer or desktop batch has been run.

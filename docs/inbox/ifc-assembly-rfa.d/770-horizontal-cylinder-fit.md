# 770 — lying cylinders fit as TRUE cylinders, not box staircases

Refs #770. Stream: `ifc-assembly-rfa`.

Owner, on the Greenlee 855GX conversion: *"we really need to stop not making
circles out of smaller rectangle extrusion and make its true form"*.

## The gap

`fit_solid` detects a round outline only in **plan**, so only vertical
cylinders ever fit. A horizontal tube's plan projection is a rectangle → `box`
→ often the slab-decomposition staircase. Meanwhile the engine has authored
TRUE lying cylinders since #591 round 4 (`cylinder_x`/`cylinder_y`, the
rotated cached B-rep, desktop-verified as delivered) — **nothing ever fit
them**. The capability and the measurement never met.

## The fix

After the vertical fit fails, `fit_solid` projects the mesh onto XZ (axis Y)
and YZ (axis X) and runs the SAME `_fit_circle` on the side hull — so both
anti-false-positive laws (#620 equidistant-corners, #628 outline-not-bbox)
are inherited, not re-derived. Axis-aligned only: a yawed tube stays its
envelope, never a guessed cylinder. A wafer (length ≤ 10% of diameter) is
refused. `PartSolid` grew `length_ft` and emits the
`radius_ft`/`length_ft`/`center`/`base_z_ft` contract `add_generic_part`
already takes.

## Measured on the owner's file

```
BEFORE: 678 parts  {box 24, polygon 653, cylinder 1}     mean fill 1.001
AFTER : 224 parts  {box 24, polygon 164, cylinder_y 24,
                    cylinder_x 11, cylinder 1}           mean fill 1.000
```

The 35 new true cylinders are exactly the bender's round anatomy: wheel_axle,
tires, hubs, caps, both casters, roller_lead/mid/tail. The 454-part drop is
the slab staircases those bodies used to decompose into. VALID 0 errors,
constraint graph coherent.

## Still not "true form", said plainly

- The **shoe_casting** (a sculptural curve, not a cylinder) remains its
  prismatic envelope — that needs swept/blended forms.
- A true **sphere** remains a disc stack. `RevolutionElem` (+
  `RevolutionCurveData`, `SphereData`, `SweepElem`, `BlendElem`) exist in the
  schema, so true revolves are EXPRESSIBLE; the engine has no constructor.
  Follow-up filed; the owner holds `sphere_test_12in.rfa` as the
  before/after control.

## BRANCH STATE

Files: `src/rvt/ifc/assembly_parts.py` (side fits in `fit_solid`,
`PartSolid.length_ft` + emit), `tests/test_horizontal_cylinder_fit.py`
(11 tests) + shard drop-in, this record.
Gates: 11 tests pass; sync deny-audit clean; Greenlee re-run VALID 0 errors,
graph coherent; before/after counts above.

## Review round 1 (#772, head 49cb812) — the dead validate instrument

The independent reviewer measured the battery's central claim false: the
validate step imported `tools/rvt_validate.py` (a CLI shim with no `Validator`
class), hit `AttributeError`, and recorded `SKIP` — counted as pass. A family
with validator errors sailed through the steer-#765 instrument. Fixed:

* the battery now calls `rvt.validate.validate_file(path, family=True)` — the
  real layered validator in family mode — and an instrument crash records
  `FAIL instrument (…)`, never an invisible SKIP;
* `skeleton.finalize()`'s back-edge repair failure now appends to `doc.notes`
  instead of a bare `pass`, so the battery can see a skipped repair;
* `verdict_harness.py` no longer calls `run()` unconditionally at import — the
  `__main__` guard covers both plain python and pyRevit exec;
* this record's test count corrected 7 → 11 (the round-2 lathe tests).

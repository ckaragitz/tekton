# arcsolver — the arc's solver record, and which parameter vector Revit wants (#589)

**PROOF-ONLY.** `.rfa` binaries and `*.report.json` are git-ignored; `arcprobes.json` is
the tracked manifest.

## Settled already

`new_var_sketch_curves` wrote `m_elemRecs = []` while `m_curveObjIdxMap` named both arcs.
`VarSketch::getCurveObj` indexes the records **through** that map, so the read ran off the
end: Revit 2026 survives OPENING such a family and dies inside `Insert > Load Family` —
journal 0040, `VarSketch.cpp:634` + `0xc0000005`. Boxes and N-gons carry one
`VarSketchLineSegObj` per curve and load; arcs carried none.

The class comes from the file's own schema: `VarSketchArcObj` extends
`VarSketchCurveObj` → `VarSketchObj`, adding `m_flipped`. It was already in
`REGISTERED_CLASSES` — known to the encoder, never emitted.

## The one thing the schema does NOT give: the parameter layout

A line's four params are its endpoint coordinates (x1, y1, x2, y2). An arc's degrees of
freedom are centre, radius and two end angles — and the schema carries
`VarSketchArcEndAngleConstrObj(m_angle, m_end)`, which only makes sense if the end angles
are parameters. That is a strong hypothesis, not a law, so it gets a matched pair.

| rung | `m_params` per arc | what it tests |
|---|---|---|
| `A5_cylinder` | `[cx, cy, r, ang0, ang1]` | the 5-DOF reading (favoured) |
| `A3_cylinder` | `[cx, cy, r]` | angles held by the curve token alone |
| `A0_cylinder` | *(empty — the pre-fix state)* | **control**: must still crash |

Every rung is ONE cylinder and nothing else, all three validator-VALID with 0 errors.

## How to read it

`Insert > Load Family` into a **new** project, all three:

- **A0 crashes, A5 loads** → layout confirmed; set `ARC_SOLVER_PARAMS` and close #589.
- **A0 crashes, A3 loads, A5 does not** → the angles are not parameters; use `center_radius`.
- **A0 crashes and neither loads** → the record class or its constraint set is wrong, not
  just the vector; the next probe adds `VarSketchArcEndAngleConstrObj` / PP joins.
- **A0 LOADS** → the mechanism is not what the journal implies and everything above is
  suspect. That is the outcome most worth knowing, which is why the control is here.

A0 is the control precisely so a pass on A5 cannot be credited to some unrelated change
between builds.

## Rebuild

```bash
.venv/bin/python experiments/ifc-assembly/arcsolver/build_arc_probes.py
```

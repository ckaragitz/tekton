# rotate — true round bodies instead of stacked slabs (#591, round 1)

**PROOF-ONLY.** `.rfa` and `*.report.json` are git-ignored; `rotate.json` is the manifest.

## The complaint, and why it is correct

> "These circle entities need to be a actual sphere, not rectangluar break up"

A horizontal cylinder sliced in Z gives **rectangles**, however many slices you take —
the roundness lies in a plane the part contract cannot draw on. `rvt.famgen.revolve`
converges in *volume* (a sphere reaches 1.0001 at 64 slices) and that measurement is
honest, but volume convergence is not what an eye sees. Stacked slabs look like stacked
slabs. No amount of tuning fixes that; the contract has to gain the ability to draw on
another plane.

## The format supports the real thing — from the file's own schema

| class | fields | what it gives |
|---|---|---|
| `RevolutionElem` | `m_sketchId` (extends `GenSweep` ← `Element`) | a **true revolve** — the same shape as `ExtrusionElem`, which we already author |
| `CylSurf` | `m_center, m_xVec, m_yVec, m_zVec, m_radius` | a cylinder about **any axis** |
| `ConeSurf` | `m_center, m_xVec, m_yVec, m_zVec, m_halfAngle` | true cones |
| `SphereData` | `m_center, m_rad` | a **true sphere**, reachable via `GeometryVRepImpl.m_sphereDatas` |

Note what `RevolutionElem` does *not* carry: no axis, no start/end angle. Those live in
built-in parameters and in the profile sketch (Revit draws the axis as a line in the same
sketch) — exactly as `ExtrusionElem`'s start/end live in params -1001800 / -1001801. That
is the unknown a donor would normally settle, and we have none in a fresh clone.

## Round 1: the cheaper road first

Before authoring a new element class, ask whether the existing one can point somewhere
else. A `SketchPlane` binds to a **datum** (`OnDatumPlaneRef.m_datumPlaneId`), which has
always been the horizontal 'Ref. Level'. `RefPlane` datums are **vertical**. If a sketch
can sit on one, the form extrudes along *its* normal and a wheel is a true cylinder —
and the same mechanism gives a strut channel its own C-profile.

| rung | what it is |
|---|---|
| `R0_vertical_cylinder` | **control** — an ordinary cylinder on the level datum, known to load |
| `R1_wheel_on_refplane` | the experiment — the same circle drawn on a vertical `RefPlane` |

Both are validator-VALID with 0 errors, which says nothing about whether Revit accepts
R1; that is the whole point of the round.

## How to read it

`Insert > Load Family` into a new project, then look at the geometry:

- **R1 loads and shows a cylinder lying on its side** → the road is open. Wheels, axles
  and rotated profiles all follow, and `revolve.py`'s stacks retire.
- **R1 loads but the geometry is wrong** (wrong plane, wrong size, flat) → the datum
  binding works and the *frame* is wrong: the sketch's u/v mapping onto a vertical plane
  is the next variable, one round away.
- **R1 crashes or is rejected** → a SketchPlane may only sit on a level, and the answer is
  `RevolutionElem` proper — a bigger piece of format work, and the honest next step.
- **R0 fails** → something unrelated broke; ignore R1 entirely.

Two precedents for how long this takes: the value-edit law (#333) took 26 desktop rounds;
the arc solver (#589) took one. This is round 1.

## Rebuild

```bash
.venv/bin/python experiments/ifc-assembly/rotate/build_rotate_probes.py
```

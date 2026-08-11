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

## ROUND 1 VERDICT (owner, Revit 2026.5, 2026-08-10): NEGATIVE — the extrusion did not rotate

| rung | result |
|---|---|
| `R0_vertical_cylinder` | **loads, renders as a proper cylinder in 3D** — the control holds |
| `R1_wheel_on_refplane` | **loads, no crash — but the profile is still drawn in PLAN on Ref. Level** |

R1's screenshot is the Ref. Level plan with the Work Plane ribbon active and the circle
lying flat in it. So pointing `OnDatumPlaneRef.m_datumPlaneId` at a vertical `RefPlane`,
even with a rotated `Trf.m_3x3` on the SketchPlane, **does not move the form's work
plane**. The file is accepted; the geometry is unchanged.

That is the second of the four outcomes this README listed, and it costs one hypothesis:
the sketch plane's datum reference alone is not what orients an extrusion. Something else
carries the work plane — candidates, in the order worth testing:

1. **`ExtrusionElem.m_alwaysRefPlaneNorm`** — its own field, and the name says exactly
   this: extrude along the reference plane's normal. Round 2 is one boolean.
2. The extrusion's `m_geomSteps` / GStep, which may carry the sweep direction
   independently of the sketch.
3. The cached B-rep, which is authored in world coordinates and may simply be overriding
   what the sketch implies.

Only when all three are exhausted does `RevolutionElem` become the answer, and a sphere
needs it regardless — no stack of extrusions, rotated or not, is a sphere.

### A second observation from the same screenshots, not yet explained

Both files draw their circle **faceted** (roughly 12–16 segments) in plan, while R0's 3D
view shows a smooth cylinder. That is consistent with Revit's coarse-detail arc display
rather than with our geometry — the arcs are true `GArc` tokens and the 3D render is
smooth — but it is worth confirming at Fine detail before anyone reads it as a defect in
the arc path.

## ROUND 2 VERDICT: NEGATIVE — `m_alwaysRefPlaneNorm` does not orient it either

Owner, Revit 2026.5: `R2_wheel_refnorm` loads; the 3D view still shows a flat disc on a
vertical axis and the plan still shows the circle lying in Ref. Level. Setting
`ExtrusionElem.m_alwaysRefPlaneNorm = True` changes nothing about the sweep direction.

Two hypotheses dead. What round 2 rules out is worth stating plainly: the orientation is
**not** carried by the extrusion element's own flags, and **not** by the sketch plane's
choice of datum alone.

## Round 3: the vector we have been writing as zero

`OnDatumPlaneRef` inherits from `OneElementMovablePlaneRef`, whose fields are
`m_vecInPlane`, `m_rotation`, `m_datumPlaneId`, `m_mirror`. We have always written
**`m_vecInPlane = [0, 0, 0]`**.

On the horizontal level that is harmless — there is only one sensible frame, so Revit
supplies it. On a VERTICAL plane a zero vector says nothing about which way the sketch's
u axis points, and a reader with no orientation has every reason to fall back to the
level. That would explain rounds 1 and 2 exactly: the datum was accepted, the flag was
accepted, and the sketch still had no frame.

`R3_wheel_vecinplane` sets it to a real in-plane vector (and a consistent `Trf.m_3x3`).

- **R3 rotates** → the frame was the missing piece; wheels, axles and the strut channel's
  C-profile all follow.
- **R3 does not** → orientation is not in the sketch plane at all, and the remaining
  candidates are the extrusion's GStep sweep direction and the cached B-rep authored in
  world coordinates. After those, `RevolutionElem`.

## ROUND 3 VERDICT: NEGATIVE — and three negatives make one shape

Owner, Revit 2026.5: `R3_wheel_vecinplane` loads; 3D still shows a flat disc on a vertical
axis. So:

| round | what was changed | result |
|---|---|---|
| R1 | SketchPlane bound to a vertical `RefPlane` | flat disc |
| R2 | `ExtrusionElem.m_alwaysRefPlaneNorm = True` | flat disc |
| R3 | `OnDatumPlaneRef.m_vecInPlane` set to a real vector | flat disc |

Three different edits to the SKETCH, three identical pictures. That is not three
independent failures — it is one finding: **nothing in the sketch moves the geometry.**

## Round 4: the cached B-rep, which has been saying "vertical" all along

`cyl_surf` hard-writes `m_zVec = [0, 0, 1]`. Every cylinder this engine has ever authored
declares a **vertical axis in world coordinates** inside its cached B-rep. If that B-rep is
what Revit draws, it explains all three rounds at once — the sketch was never going to win
an argument with it.

`rotate_rep` rotates a cached B-rep's positions and directions together (5 field types,
14 vectors in a cylinder: `m_xVec`, `m_yVec`, `m_zVec`, `m_origin`, `m_center`).
`R4_wheel_rotated_brep` rotates ONLY the B-rep, 90° about X, and leaves the sketch alone.

- **R4 lies on its side** → the B-rep drives the display. Wheels are reachable today, and
  the parametric side must then be made to agree — or the form regenerates back to
  vertical on the first edit, which is a trade to *measure* next, not to assume.
- **R4 is still a flat disc** → the B-rep does not drive it either, and the honest
  conclusion is that direction is fixed by the element kind itself. `RevolutionElem` is
  then the only road — and a sphere needs it regardless.

## ROUND 4 VERDICT: THE B-REP DRIVES THE DISPLAY

Owner, Revit 2026.5, `R4_wheel_rotated_brep` — sketch untouched, cached B-rep rotated 90°
about X:

| view | rounds 1–3 (flat disc) | round 4 | a cylinder along Y should show |
|---|---|---|---|
| Plan (Ref. Level) | circle | **rectangle** | rectangle 3.44 (X) × 0.95 (Y) ✓ |
| Left elevation | wide flat rectangle | **narrow, tall rectangle** | 0.95 wide × 3.44 tall ✓ |

Both views moved, and moved the way a cylinder lying along Y moves. **The cached B-rep is
what Revit draws** — which is why three rounds of editing the sketch changed nothing, and
why `cyl_surf`'s hard-wired `m_zVec = [0, 0, 1]` was the whole story.

### Still to confirm: round or boxy

The decisive view is the **Front elevation** (or 3D), which must show a **CIRCLE** — the
wheel's round face. A rectangle there would mean the rotation moved the solid but mangled
its curved surfaces, and the `CylSurf` frame needs more than a rigid rotation.

### The consequence nobody should skip

The sketch and the B-rep now **disagree**: the sketch still describes a vertical extrusion,
the B-rep a horizontal cylinder. Revit is showing the B-rep, but a **regeneration** — any
parameter edit, a flex, possibly a reload — may rebuild from the sketch and snap the wheel
upright. That is the next thing to MEASURE (open the family, change a dimension, look),
not to assume in either direction. A wheel that is round until someone touches it is worth
knowing about before it ships.

Two roads from here, and the choice depends on that measurement:

* the B-rep alone is enough for *display-only* content → wheels ship now, with the
  regeneration caveat recorded honestly in the matrix;
* regeneration snaps it back → the parametric side has to agree, which means the
  extrusion's own sweep direction, and if that has no expression, `RevolutionElem`.

## Rebuild

```bash
.venv/bin/python experiments/ifc-assembly/rotate/build_rotate_probes.py
```

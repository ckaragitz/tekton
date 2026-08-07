# Family geometry — parametric FORM generators (`rvt.famgen.geometry`)

Stream: `family-geometry` (2026-08-03, cylinder pass added the same day).
Code: `src/rvt/famgen/geometry.py` (`box`, `plate`/`faceplate`, `cylinder`,
`solid_box_brep`, `solid_cylinder_brep`, `extrusion_gstep` /
`extrusion_gstep_circles`, `assign_pids` / `renumber_pids`, `emit_form_rfa`,
`reproduce_specimen_solid`, `reproduce_specimen_cylinders`); proofs in
`experiments/families/genesis/` (`G_box_solid.rfa`, `G_box_dummy.rfa`,
`G_cyl_solid.rfa`, `G_cyl_dummy.rfa`, `G_report.json`); tests
`tests/test_famgen_geometry.py` (19 pass).
Confidence tags: **[V]** verified on the corpus by code, **[H]** hypothesis
(needs Revit acceptance), **[D]** design decision. Companions:
`family-authoring.md` (the family document / .rfa container),
`docs/product/content-strategy.md` (the rule: geometry is OURS, dimensions
are facts — nothing here clones an Autodesk payload).

Product sentence served: "build me an Eaton panel with X and Y" needs the
platform to CREATE the family's geometry from catalog dimensions. This
stream turns `(width, depth, height)` into a complete, self-consistent
element cluster: sketch plane, profile sketch, its model lines, the
extrusion, and the extrusion's cached B-rep solid — expressed field by field.

## 0 · TL;DR

1. A family FORM = **7 elements** for a box: `SketchPlane` (on the
   'Ref. Level' datum) + `VarSketch` (the drawn profile) + 4 `CurveElem`
   (OST_Lines model lines) + `ExtrusionElem` (start/end offsets, the
   traced-loop copy, the geometry-history tag map) [V, three specimen
   clusters decoded: rme panelboard 786837 / 786867, sample .rfa 82].
2. The extrusion's seq-103 rep is a **six-face B-rep solid whose topology
   is a fixed template**: identical archive object numbering, weakref
   graph, edge-loop chains, history tags and flag words across two
   independent Autodesk boxes; only frames / uv coordinates / envelopes
   depend on the six dimensions [V]. `solid_box_brep` rebuilds BOTH
   specimen solids **from their dimensions alone**: 786867 exact in all
   533 leaves, 786837 exact modulo one volatile GInfo bit (0x200, which
   differs between the two Autodesk specimens themselves); both
   **byte-identical after snapping floats at 1e-9** (the specimens carry
   ~1e-15 transform noise) — `reproduce_specimen_solid`, the topology proof.
3. The archive object-index numbering (**pids**) is fully understood and
   reproduced: `assign_pids` renumbers **6,296/6,296** specimen records
   pointer-for-pointer (registered classes are a fixed set; numbering =
   encounter order, breadth-first deferred bodies) [V]. This is what lets
   us AUTHOR arbitrary object graphs, not just re-encode decoded ones.
4. **Both delivery paths built and self-verified** for BOTH shapes:
   `G_box_solid.rfa` / `G_box_dummy.rfa` (our 500×300×700 mm box) and
   `G_cyl_solid.rfa` / `G_cyl_dummy.rfa` (our 6 in × 190 mm recessed-can
   cylinder) = the sample `.rfa` + our form spliced in (records + ElemTable
   + partition header); CRC/ECC/walker clean, every element decodes,
   validator parity with the donor (0 warnings, no error beyond the 5
   baseline family-file gaps). Acceptance = Revit / the viewer opening
   them **[H — the gate]**; the solid/dummy pair per shape answers the
   F4 regeneration question.
5. **The cylinder is DONE (§4)**: `solid_cylinder_brep` rebuilds the sample
   .rfa's 4-leg solid (extrusion 614: 10 faces / 24 edges / 16 loops incl.
   multi-loop caps) from its four circles + offsets — **structurally exact
   over 1,421 leaves, all 678 geometric floats exact (max 1.5e-14), only the
   104 cap/loop envelope corners differ by ≤1.2e-4 ft (Revit's finer
   envelope tessellation — cache class)**. Curved edges, `CylSurf` frames,
   the 7/6-chord tessellation rule, chained cap loops and the arc CurveElem
   / sketch cluster are all constructed. The parametric hooks (labeled
   dimensions, §5) stay a documented recipe (fixed-dimension geometry
   delivered; the generator IS the parameter).

## 1 · What a form is on disk [V]

Specimen clusters: rme `Partitions/14` unit 243 ("MLO 208V panelboard"
family, extrusions 786837 & 786867) and the standalone
`racbasicsamplefamily-2026.rfa` (extrusions 82 rounded-rect top, 614 four
cylindrical legs). Every id below is real.

| element | seq-102 essentials | seq-103 rep |
|---|---|---|
| `SketchPlane` 786835 / rfa 80 | `m_oPlaneRef = OnDatumPlaneRef{m_datumPlaneId = LEVEL id}` (786449 'Ref. Level' / rfa 21), `m_oTrf` identity, `m_userId` = its VarSketch | `SerializedDummy` |
| `VarSketch` 786836 / rfa 81 | `m_absorbedCurves[]` = the DRAWN GLines (tags 0..n-1, "as drawn": origin = start point, interval [0,len]), `m_absorbedCurvesData[]` (CurveElemData per curve), `m_elemIdsPairSet` + `m_curveObjIdxMap` (curve elem id ↔ index), `RegenSketchCurvesGStep{curveHist [1,i,-1,-1,-1] per curve}`, `GeomTable` (n entries → generator 1), `m_pPlane` (identity frame, envelope = curve bbox), `m_sketchPlaneId`, `m_userId` = the ExtrusionElem it feeds, `m_dimIds` (its dimensions, if any), solver state `m_elemRecs/m_constrRecs/m_oGuessCache` | `GElement{n GLine sub-nodes}` (gElemType 2) |
| `CurveElem` 786838 / rfa 85 | category OST_Lines (-2000045); `m_pCurveDriver = CurveElemDriver{m_pCrv = GLine, m_controlJoinsSet = endpoint joins to the two neighbour lines (this end 0 ↔ prev end 1, end 1 ↔ next end 0)}`; `SketchMembership{m_groupId = sketch}`; `CurveElemGStep{curveHist [2,0,-1,-1,-1]}`; `m_sketchPlaneId`; int param `-1006205 = 1` | `GElement{1 GLine}` (gElemType 2, root flags 32) |
| `ExtrusionElem` 786837 / rfa 82 | `ParamValueSetDouble{-1001801 END, -1001800 START}` (feet along the sketch normal — **order end-then-start**), int `-1006205 = 1`; `GeomStepList{m_bRepFormGList = [ExtrusionGStep{faceHistTable, edgeHistTable}]}` (§3.2); `GeomTable` (2+4n entries → generator 1); `CellList{ExtrusionElemExtrusionHelper{m_sketchId, m_pCurveLoops = [CurveLoop{n GLines}]}, GenSweepPatternHelper}` — a **private copy of the traced closed profile loop** (§2); `m_categoryId` (sub-category, -1 = family's), `m_materialId`, `m_famElemVisibility{57398}` | **`GElement` solid (§3)** or `SerializedDummy` [H] |

Ownership (ElemTable `owner_id`, .rfa) [V]: SketchPlane → family (17);
ExtrusionElem → family; VarSketch → its ExtrusionElem; CurveElem → its
VarSketch. Header regen edges [V]: CurveElem `m_regenOnly = [level,
extrusion]`, VarSketch `m_regenOnly = [level (+ constraining ref planes)]`,
ExtrusionElem `m_regenOnly = [origin ref plane, its sketch plane]`,
`m_deletion` lists close over the cluster (sketch deletes with the
extrusion, curves with the sketch, everything with the self-Family).

Family-doc flavour constants [V] (`FamilyDocContext`; `context_from_rfa`
discovers them): header `(m_abFlags4Bytes, m_nVisibleViewFlags)` =
SketchPlane (26, -32768), VarSketch (16779322, -32768), CurveElem
(17340539, -4225), ExtrusionElem (3896, -4225); a family document embedded
in a PROJECT differs by bit 0x10 on the first three. Object
`m_designOptionId = -4` on every element (header -1). GLine
`m_GInfo.m_flags`: 0x1000004 in an .rfa, +0x80000 embedded, +0x8000 on the
sketch's rep copies, +0x8200 on the curve-elem rep copy. Solid graphics:
`Geometry.m_GInfo.m_categoryId` = the family sub-category `GStyleElem` id
(rfa 4087) — the small integers in an embedded doc (124, 179, 69) are the
HOST's GStyleElem ids.

## 2 · The three profile representations [V]

A rectangle profile exists three times, plus the solid:

| copy | parametrization | evidence |
|---|---|---|
| `VarSketch.m_absorbedCurves` + `CurveElem` drivers | AS DRAWN by the user (any direction; tags 0..3) | 786836 curve 0: origin (−4, 4) dir +x interval [0, 8] (drawn left→right) |
| `ExtrusionElem` helper `CurveLoop` | Revit's **traced closed loop**: COUNTER-CLOCKWISE w.r.t. the sketch normal; each curve anchored at its END vertex with interval [−len, 0], reversed relative to the drawing when needed | 786837 curve 0: origin (−4, 4) (= its end vertex V1) dir −x interval [−8, 0]; loop area > 0 |
| the seq-103 solid | frames derived from the traced loop (§3) | — |

Our generator draws the profile CCW head-to-tail (curve i from V<sub>i</sub> to
V<sub>i+1</sub>) so all three copies describe the same loop; the helper copy
uses the traced [−len, 0] form exactly like the specimens.

## 3 · The six-face solid — topology template [V]

`solid_box_brep(profile CCW V0..V3, start, end)` with `start > end`
(**every box specimen extrudes DOWN**: the START cap is the top; rme
786837 start 0 / end −1, 786867 start 0.4793 / end ≈ 0; the .rfa's
non-box forms extrude up — different frame convention, not needed here).

### 3.1 Object graph and archive numbering (identical in both specimens)

```
GElement (pid 2)  m_gElemType 3, m_flags 0, m_bBox/m_tightbBox = axis bbox
 └─ Geometry (3)  m_flags 7, m_geometryTag -1, tessEps {type 0, ver 1}
     m_pFaces = [ start cap (4, tag 1), end cap (5, tag 0),
                  side_0 (6, tag 2), side_1 (7, tag 5), side_2 (8, tag 9),
                  side_3 (9, tag 13) ]
     m_pEdges = 12 Edge, pids 10..21 in TAG order
                (3,4,6,7,8,10,11,12,14,15,16,17)
     Face k   -> EdgeLoop pid 22+2k, Plane surface pid 23+2k
                (faceRegions [], filling null, renderStyle -1,
                 cutType 0, faceFlags_v9 4)
```

Numbering rule (`assign_pids`, §6): registered classes get the next index
in encounter order, breadth-first: Geometry → its `m_pFaces` (6) → its
`m_pEdges` (12) → then each face's body assigns its loop + surface. Our
constructor lays out these pids by formula and asserts `assign_pids`
agrees (`_assert_pid_stable`).

### 3.2 History tags (`ExtrusionGStep`) [V, formula]

Tag allocation for an n-curve profile (n = 4 → 18 tags): `0 = end cap`,
`1 = start cap`; then walking the loop: for curve i → its **side face**,
its **start rail** `[1,i,0]`, its **end rail** `[1,i,1]`, and (from i = 1)
the **lateral** `[2,i−1,i]`; finally the closing lateral `[2,n−1,0]`.

| face | tag | faceHist key | | edge | tag | edgeHist key |
|---|---:|---|---|---|---:|---|
| end cap | 0 | `[2,-1,-1]` | | start rail c_i | 3,6,10,14 | `[1,i,0]` |
| start cap | 1 | `[1,-1,-1]` | | end rail c_i | 4,7,11,15 | `[1,i,1]` |
| side_i | 2,5,9,13 | `[3,i,-1]` | | lateral at V_{i+1} | 8,12,16 | `[2,i,i+1]` |
| | | | | closing lateral at V_0 | 17 | `[2,3,0]` |

The GeomTable maps every tag 0..17 → generator 1 (the ExtrusionGStep
`m_id`); `GeomStepList.m_idCounter = 2`, `m_latestGStepTypeInPrevRegenCycle
= [2,2,2,2,2]` (form step), list flags 9. The same formula reproduces the
4-circle leg extrusion's per-loop pattern (n = 2 arcs → 10 tags).

### 3.3 Face frames (Plane surfaces) [V]

`ext = (0,0,−1)` (start→end), `n_start = +z`, `n_end = −z`, `t_i` = curve i
tangent, vertices lifted to the start plane (`Vt`) / end plane (`Vb`).

| face | origin | xVec | yVec | envelope [[umin,vmin],[umax,vmax]] |
|---|---|---|---|---|
| start cap | Vt<sub>1</sub> (curve 0's END vertex) | t<sub>0</sub> | n_start × xVec | u ∈ [−len<sub>0</sub>, 0] |
| end cap | Vb<sub>1</sub> | −t<sub>0</sub> | n_end × xVec (= same yVec) | u ∈ [0, len<sub>0</sub>] |
| side_i | Vt<sub>i</sub> | ext (down) | t<sub>i</sub> | [[0,0],[start−end, len<sub>i</sub>]] |

Outward normals fall out: cap yVec = normal × xVec; side normal = ext ×
t<sub>i</sub> = t<sub>i</sub> rotated −90° (outward for a CCW loop with a
downward extrusion). Envelopes = the face's vertex extents in its own uv.

### 3.4 Edges: coedges, uv points, loop links, direction flags [V]

Each `Edge` sits between exactly two faces: `m_pFace = [A, B]` (weakrefs),
`m_next = [next in A's loop, next in B's loop]`, `m_prev` likewise; the
FIRST edge of a loop has `prev = the EdgeLoop's pid` and the LAST has
`next = the EdgeLoop's pid` (the loop's own `m_next` = first edge, `m_prev`
= last edge). **`m_firstAndLastEdgePnts = [ FIRST point {uv: [uv in A, uv
in B]}, LAST point {…} ]`** — per point, the uv in EACH adjacent face's
frame (proved by re-deriving the 3D endpoints from both frames: they
coincide to 1e-15). `m_interiorEdgePnts` = [] for straight edges (curved
edges carry tessellation points, §4).

| edge | 3D (first → last) | m_pFace [A, B] | loop membership | m_flags |
|---|---|---|---|:-:|
| start rail c_i | Vt<sub>i</sub> → Vt<sub>i+1</sub> | [start cap, side_i] | cap chain c0..c3; side_i's 1st edge | 6 |
| end rail c_i | Vb<sub>i+1</sub> → Vb<sub>i</sub> | [end cap, side_i] | cap chain c3..c0; side_i's 3rd edge | 6 |
| lateral at V<sub>i+1</sub> (i<3) | Vb<sub>i+1</sub> → Vt<sub>i+1</sub> (up) | [side_{i+1}, side_i] | side_{i+1}'s 2nd, side_i's 4th | **7** |
| closing lateral at V<sub>0</sub> | Vt<sub>0</sub> → Vb<sub>0</sub> (down) | [side_0, side_3] | side_0's 2nd, side_3's 4th | 6 |

Side-face loop order: [start rail i, lateral at V<sub>i</sub>, end rail i,
lateral at V<sub>i+1</sub>]. **`m_flags` bit 0 = "the stored direction is
REVERSED relative to face A's loop"**; equivalently, the stored parametric
direction is FORWARD in the adjacent face with the SMALLER tag (base flags
6). This single rule explains every rail (forward in its cap) and every
lateral (three stored upward with flag 7, the closing one downward with
flag 6) in both specimens.

GInfo flag words [V]: root 557060, Geometry 573444, EdgeLoop 524292, Face
558596, Edge 557572. **Bit 0x200 is volatile**: box 786837 clears it on 5
faces (558084) and all 12 edges (557060) while box 786867 (same family, same
file) sets it — a graphics-cache bit, not derivable from dimensions and
irrelevant to acceptance (both load); the topology proof compares modulo it.

### 3.5 The proof [V]

`reproduce_specimen_solid(project, unit, extrusion_id)` reads ONLY the
specimen's dimensions (4 traced-loop vertices + start/end + graphics ids),
runs `solid_box_brep`, and compares against the decoded specimen GElement:

| specimen | leaves | structural mismatches | max float dev | bytes @1e-9 |
|---|---:|---|---:|---|
| 786867 (arbitrary rectangle, sketch on Ref. Level) | 533 | **0** | 1.1e-13 | **identical** (3,058 B) |
| 786837 (8 × 10.75 × 1 box) | 533 | 17, all = GInfo bit 0x200 | 6.2e-15 | **identical** (3,058 B) |

The float deviations are Revit's own transform arithmetic (its solid does
not even sit exactly on its sketch plane: 786837's cap z = −6.217e-15 vs the
plane's −6.128e-15); a clean generator produces exact zeros where the
specimen carries 1e-15 noise. Test:
`test_specimen_box_topology_reproduced_from_dimensions`.

## 4 · Cylinder — arc profile + `CylSurf` B-rep (DONE) [V]

Specimen: sample .rfa **extrusion 614** = FOUR cylindrical legs in ONE
extrusion (4 closed loops, each 2 half arcs, r = 0.125 ft, start 0 →
end 1.2493 = **extrude-UP**), sketch 613 (8 absorbed `GArc`s), arc
`CurveElem`s 3736/3741/... Its solid = 10 faces, 24 edges, 16 loops.
Constructors: `circle_profile`, `cylsurf`, `_circle_loop_tags`,
`extrusion_gstep_circles`, `solid_cylinder_brep`, `new_arc_curve_elem`,
`new_var_sketch_curves`, `new_cylinder_extrusion`, `cylinder_form` /
`cylinder`. Proof: `reproduce_specimen_cylinders` (§4.6).

### 4.1 How Revit draws a circle [V]

Two half arcs about one centre, xVec/yVec = the sketch axes: **U** =
params [0, π] (drawn first, sketch curve index 0) and **L** = params
[−π, 0] (drawn second, index 1); the two arc `CurveElem`s join each
other at BOTH ends (end 0 ↔ partner end 1, non-tangent). The extrusion
helper's `CurveLoop` keeps the arcs' own parametrization (NOT
re-anchored like lines) but ORDERED as the tracer walked the loop:
**L first, then U** (614's four loops all list the [−π,0] arc first).
Frame vertices: V1 = the θ = 0 point (L's end / U's start), V0 = the
θ = π point.

Arc `CurveElem` extras vs a line CurveElem [V 3736]: `m_oArcCntr` = a
zero-length `GLine` centre marker (geometry tag 1, params [0,0], origin
= centre, dirVec = the sketch normal — a REGISTERED object, pid before the
driver's `GArc`); `ArcElemCell` in the cell list; TWO curve-history
entries ([2,0,…] the arc, [2,1,…] the marker) and a 2-entry GeomTable;
`m_referenceType` 1; header `m_miscId` = the sketch id and
`m_hasNonDetermRegenChildren` = true (both true of LINE curve elems too —
fixed in `new_curve_elem` this pass).

### 4.2 Tags — the box formula with n = 2 [V]

Per circle j the traversal is (L, U) and the history TAG block is the
box formula (§3.2) for a 2-curve loop at base B<sub>j</sub>: side(L)=B,
rail<sub>top</sub>(L)=B+1, rail<sub>bot</sub>(L)=B+2, side(U)=B+3,
rail<sub>top</sub>(U)=B+4, rail<sub>bot</sub>(U)=B+5, lateral at V1
`[2,L,U]`=B+6, closing lateral at V0 `[2,U,L]`=B+7; caps are global
(end cap 0, start cap 1). Clean history: B<sub>j</sub> = 2 + 8j.
Specimen 614 carries EDITING-HISTORY baggage: its hist tables cover 36
curves (four 2-loops, five 4-loops, four 2-loops — deleted attempts keep
their tag reservations), so its live faces sit at bases 114/122/130/138
and its GeomTable has 146 entries; only curves 28–35 (the current
circles) own faces. Our generator emits a clean history; the reproduction
feeds the specimen's bases as facts.

### 4.3 Solid structure [V — full-graph reproduction]

```
GElement (pid 2)   root flags 0, GInfo 557060, bbox = TESSELLATION-NODE extents
 └─ Geometry (3)   m_flags 6 (curved solids; 7 on all-planar boxes),
                    tessEps version = donor's (0 rfa / 1 rme)
     m_pFaces = [ TOP cap (4, END cap tag 0), BOTTOM cap (5, START tag 1),
                  then per circle j: side_L (tag B), side_U (tag B+3) ]
     m_pEdges = 6 per circle in tag order: rail_top_L, rail_bot_L,
                rail_top_U, rail_bot_U, lat_v1, lat_v0
     caps: ONE Face each; the k circles are k EdgeLoops CHAINED by
           m_nextLoop (circle 0's loop = m_pFirstLoop; the chain bodies
           are numbered after every face body -- BFS, §6)
     sides: CylSurf surfaces (unregistered, pid -1); one loop each
```

Serialization order rule generalising box + cylinder: **the TOP cap
(higher z) is always face 0** — box (extrude-down): top = START cap
(tag 1); cylinder (extrude-up): top = END cap (tag 0).

Frames [V]:

| face | origin | xVec | yVec | envelope (u,v) |
|---|---|---|---|---|
| top cap (Plane) | V1 of circle 0 at z<sub>top</sub> | +y (CCW tangent at V1) | (+z) × xVec = −x | union of the circles' extents |
| bottom cap (Plane) | V1 of circle 0 at z<sub>bot</sub> | −y | (−z) × xVec = −x | 〃 |
| side_L (CylSurf) | axis base = centre at the START plane | xVec +x, yVec +y, zVec +z, radius r | | θ ∈ [π, 2π], v ∈ [0, len] |
| side_U (CylSurf) | 〃 | 〃 | | θ ∈ [s, s+π], s = 0 (or 2π — 614's legs 2/3 use [2π,3π]; both valid, tracer's choice; `u_shifts` input) |

Unifying cap rule (box + cylinder): xVec<sub>top</sub> = +t<sub>0</sub>,
xVec<sub>bottom</sub> = −t<sub>0</sub>, yVec = outward × xVec, where
t<sub>0</sub> = the traced tangent at the frame vertex V1 — the cap's
`xVec × yVec` is then its OUTWARD normal in both extrusion directions.

### 4.4 Edges: curved rails, seams, coedge uv, the tessellation rule [V]

Per circle (all four legs of 614 identical):

| edge | stored direction | pFace [A, B] | m_flags | GInfo flags | interior pts |
|---|---|---|:-:|:-:|:-:|
| rail_top_L | θ π→2π on the top | [top cap, side_L] | 14 | 557572 | **6** (7 chords, Δθ = π/7) |
| rail_bot_L | θ 2π→π on the bottom | [bottom cap, side_L] | 14 | 557572 | **6** |
| rail_top_U | θ 0→π on the top | [top cap, side_U] | 14 | 557572 | **5** (6 chords, Δθ = π/6) |
| rail_bot_U | θ π→0 on the bottom | [bottom cap, side_U] | 14 | 557572 | **5** |
| lat_v1 (θ=0 seam) | top → bottom | [side_U, side_L] | 6 | **557796** | 0 |
| lat_v0 (θ=π seam) | top → bottom | [side_L, side_U] | 6 | **557796** | 0 |

Flags: 14 = curved bit 8 | 6; every curved rail is stored FORWARD in
face A (its cap) and traversed reversed in the side face; the seams are
forward in face A. Each point (first, last, interior) = `{uv: [uv in
face A, uv in face B]}` — cap uv by projection into the cap frame,
cylinder uv = (θ, z − z<sub>start</sub>) with θ expressed in that face's
own range. **Tessellation rule**: the first-traversed half (L, params
[−π,0]) is stored with 7 uniform chords, its partner half with 6 uniform
chords — deterministic on 8/8 specimen half-arcs (why 7 ≠ 6 for equal
spans is unknown [H mechanism]; the values are reproduced exactly).

Loops (traversal, exactly the specimen's `m_next/m_prev`):
top-cap loop = [rail_top_L, rail_top_U]; bottom-cap loop = [rail_bot_U,
rail_bot_L]; side_L loop = [rail_top_L, lat_v0, rail_bot_L, lat_v1];
side_U loop = [rail_top_U, lat_v1, rail_bot_U, lat_v0] — the box's
side-face pattern [start rail, lateral at the loop's start vertex, end
rail, lateral at its end vertex] with "start rail" = the TOP rail.
First edge's `m_prev` / last edge's `m_next` = the EdgeLoop's own pid.

The solid's `m_bBox/m_tightbBox` = the extents of the stored edge
NODES (614's ymin = −0.5 − 0.125·sin(3π/7) = −0.62187, the 7-chord node —
NOT the analytic −0.625) — reproduced exactly by taking our node bbox.

### 4.5 Two cache-noise classes we deliberately do NOT reproduce [V/H]

1. **Face/loop envelopes** (`Face`/`EdgeLoop`/cap `Plane` `m_Envelope`
   corners): computed by Revit from a FINER display tessellation than the
   stored 6/7-chord edge points — where a chord midpoint misses the
   circle's extreme the corner is off by the sagitta (≈1.2e-4 ft at
   r = 0.125). We emit ANALYTIC envelopes (true circle extents); the
   reproduction reports these corners separately (104 corners, max
   1.17e-4 ft). CylSurf/side-loop envelopes ([π,2π]×[0,len]) are analytic
   in the specimen too and match exactly. Bounding hints, recomputed by
   Revit — irrelevant to acceptance [H], like the box's volatile bit.
2. **Material surface fillings**: 614's faces (material 5264 with a
   surface pattern) each own a `GFilling` (registered object; `m_pGFace`
   weakref, `m_placer{scale, origin, dir, uvScale, mirrored, draft}`,
   `m_patternId` −1, `m_fillColor` 16777216, `m_flags` 18, GInfo category
   = the pattern) and `m_renderStyleId` = the extrusion's `m_materialId`.
   The CAP placers ARE derivable (origin/dir = the world origin / +X
   projected into the face uv), but the CylSurf-face placers hold
   uninterpretable cache floats (e.g. dir (7.36, 0)). Our forms carry NO
   material pattern (fillings null, render style −1) — exactly like both
   ACCEPTED box specimens — so the comparison strips the specimen's
   fillings (`_strip_fillings`) and renumbers its pids with weakref
   remapping (`renumber_pids`) before comparing.

### 4.6 The proof [V]

`reproduce_specimen_cylinders(rfa, 0, 614)` reads ONLY the specimen's
four circles (centre, radius from the helper loops), start/end, the four
tag bases, the four U-θ shifts, the graphics ids and the tess version,
runs `solid_cylinder_brep`, and compares with the specimen's own decoded
solid (fillings stripped):

| aspect | result |
|---|---|
| leaves compared | 1,421 (10 faces, 24 edges, 16 loops) |
| structural mismatches (class / pid / weakref / int / flag / count) | **0** |
| geometric floats (frames, CylSurf params, all coedge uv incl. every interior tessellation point) | 678 leaves, max dev **1.5e-14** |
| envelope corners (§4.5 class 1) | 104 leaves, max dev 1.17e-4 ft (< tol 5e-4) |

Test: `test_specimen_cylinders_reproduced_from_dimensions`. This is the
cylinder analogue of the box's §3.5 proof; multi-circle extrusions (4
legs in one form) come for free (`solid_cylinder_brep(circles=[...])`).

### 4.7 What a rounded rectangle would add (phase 2, sec. for the record)

rfa extrusion 82 (the table top: 4 lines + 4 fillet arcs, one loop) mixes
`GLine` and `GArc` curves in one loop — tangent-junction laterals between
a Plane side and a CylSurf side. The per-curve template (side + 2 rails +
lateral) is unchanged; only the surface/edge kind alternates. Not built
tonight (no product need before acceptance).

## 5 · Reference-plane / parameter hooks — decoded recipe [V structure]

The parametric machinery is TWO more element kinds on top of the fixed
geometry above:

1. **Labeled dimension** (rfa `LinearDimString` 472): its ONE segment has
   `m_ArrSegInfo[0].m_paramId = 4208` (the `ParamElemFamily` "Height") with
   `m_lockedValue = 1.4993 ft` (the current height) and
   `m_dimLockedForLabeling = True`, `m_flags` 8; its `m_witnessRefs` are
   `GeomSegInPlaneRef` geometry references — one to the **extrusion 82**
   (its top face/edge by geom tag) and one to **RefPlane 47** — and the
   dimension's `m_refPnts` sit on the two dimensioned lines. So "Height =
   the family parameter" is: a locked linear dimension between a solid's
   face and a ref plane, whose segment carries the parameter id. The
   circle case is a `RadialDim` (5814) whose segment `m_paramId = 5812`
   ("Radius") with an `ArcRef` witness to arc 5809.
2. **The datum**: the sketch already sits ON the 'Ref. Level' via
   `SketchPlane.m_oPlaneRef.m_datumPlaneId` (§1), and constrained sketch
   lines list their ref planes in the VarSketch header's `m_regenOnly`
   (rfa 81 → [level 21, ref planes 48/1083/1084/1085]) — the regen edges
   that make the profile follow the planes.

Constructing `LinearDimString` (≈1.3 KB: dim style symbol, witness refs
with `GeomSegInPlaneRef{m_elemId, m_geomTag}`, seg infos, dim line, ref
points, `ContinuousLinearDimState`) is the phase-2 deliverable; tonight's
forms are FIXED-dimension (the generator IS the parameter — regenerate the
cluster for a new size). Recipe evidence: this section + the specimen dumps
(rme 786891: an unlabeled locked EQ dimension between two sketch lines,
`m_ArrSegInfo[0].m_paramId = −1`, `m_lockedValue 8.0`, witnesses = the two
`CurveElem`s with `m_geomTag 0`).

## 6 · Archive numbering — `assign_pids` [V]

The u32 pointer index every owned object carries is the archive's object
table index: **1 = the document, 2 = the record's root object**, then
sequential in ENCOUNTER order over the root's fields in schema order —
inline value structs recurse in place; owned pointers queue their bodies
and are processed breadth-first — **but only instances of a fixed
REGISTERED set are indexed** (all other classes serialize −1): `Edge,
EdgeLoop, Face, GElement, Geometry, GLine, GArc, GPoint, GPolyMesh,
GBitmap, GFilling, GFilter, GGTag, GGroup, Plane, VarParam,
VarSketch{LineSeg,Arc}Obj, VarSketch{PP,HorVer,ArcEndAngle,
LSegPerpToLSeg}ConstrObj, FamilyDocument`. Discovered by collecting which
`ptr_class`es EVER carry a real pid across 6,296 clean records (the two
sets are disjoint) and validated by renumbering ALL of them: 3,984 (rfa) +
1,102 (unit 243) + 1,210 (unit 271) records, **0 mismatches**. Weak
references are then just those indices (e.g. `Face.m_pFirstLoop`'s loop
carries `m_pFace = {weakref: <face pid>}`; every G-step's `m_pElem` = 2 =
the element object itself; `m_docAccess.m_pDoc` = 1).

## 7 · Emission — `emit_form_rfa(donor, out, bundles)` [V mechanism]

Minimal-commit posture (exactly what Autodesk accepted for the first
created project element, KNOWLEDGE V20), applied to a family file:

1. Encode each new element's three records (`rvt.encode`, adler32
   stamps); append them to save-unit 0 of `Partitions/<N>` immediately
   before each per-seq sentinel (last block per seq), recompute the touched
   blocks' A/C counters, re-gzip every block (level 3, sync-flush), patch
   the stream header's element count, re-frame with real CRCIO ECC.
2. Append 40-byte `ElemRec` rows to `Global/ElemTable` (id-sorted; episode
   = the donor's max modified episode so the History invariant holds;
   owner = §1 ownership chain), **preserving a family file's graveyard
   tail** (u32 count + n × 32-byte deleted-record entries — 18 in the
   sample .rfa — which the project decoder does not model) and raising the
   footer watermark (`_elemtable_append`). Note for the ElemTable owner:
   the .rfa footer layout is `u32 graveyard_count | GraveyardRec[n] (32 B:
   i64 original_id, u32 0, i64 id, 3 × u32 episodes) | u32 0xFFFFFFFF |
   u16 0x096a | u16 0 | u64 last_id | u32 0` — the fix for
   `stream_encoders.decode_elemtable`'s "GraveyardRec wire layout not
   observed" error and the validator's matching consistency error.
3. Copy every other stream (identity, `PartAtom`, `Global/Latest`,
   `Contents`) and rebuild the container with our CFB writer.

Block-counter fidelity (fixed this pass): the touched blocks' C counter
uses the FULL record-header length (16 B seq101 / 20 B seq102-103 incl.
the psize repeat) — the corpus identity `ISIZE == hdr_len(seq)*A + C +
adj(flags)` — matching `rvt.commit`; the previous 12/16-byte convention
left C high by 4×A on the 3 rewritten blocks and the validator warned
(tolerated by Revit, but a defect). The emitted files now carry **0
warnings**.

Read-back (`verify_emitted`) on all four proof files: 8 gzip members / 0
CRC failures, 14 full pages / 0 ECC mismatch, walker clean, every seq-102
record decodes clean, all donor ids preserved, our new elements decode
clean in all three seqs (box: 7 elements → 1,999 total; cylinder: 5 →
1,997); ElemTable count = partition header count, watermark raised;
`validate_parity` = TRUE (the same 5 baseline family-file findings as the
untouched donor — validator gaps for family files owned by the `validate`
stream: PartAtom framing, missing ProjectInformation, family ElemTable
graveyard, DIT — 0 warnings, no new error; ~30 k refs checked, 0 decode
failures).

## 8 · Confidence / unknowns

| claim | status |
|---|---|
| form cluster contents, ownership, regen edges, family-doc flag constants (§1) | **V** (three specimen clusters) |
| the three profile parametrizations (§2); circle = 2 half arcs, traversal (L, U) (§4.1) | **V** |
| box B-rep topology: numbering, tags, frames, coedges, loop links, direction rule (§3) | **V** — both specimens rebuilt from dimensions, canonical byte-exact |
| cylinder B-rep: CylSurf frames, curved rails + 7/6-chord tessellation, seams, chained multi-loop caps, node bbox (§4) | **V** — the 4-leg specimen rebuilt from its circles: 1,421 leaves structurally exact, 678 geometric floats @1.5e-14 |
| cap/loop envelopes use a finer tessellation (~1e-4 corner deviation); GInfo bit 0x200 volatile | **V observed**, **H** irrelevance (cache classes) |
| Geometry.m_flags 7 = all-planar / 6 = curved faces; tessEps version 0 rfa / 1 rme | **V observed 4/4 & 2 donors**, **H** semantics |
| archive pid numbering / registered class set; renumbering with weakref remap (§6) | **V** (6,296/6,296 records) |
| ElemTable family-file graveyard tail layout (§7) | **V structure** (600-byte tail parsed; watermark round-trips) |
| emission preserves container/CRC/ECC/decode integrity + validator parity, block counters exact | **V** (0 warnings) |
| our authored solids / dummy reps OPEN in Revit; the added forms regenerate and display; the empty sketch-solver state (`m_elemRecs = []`) is tolerated | **H — the acceptance gate (`G_box_*.rfa`, `G_cyl_*.rfa`)** |
| BIP names −1001800 start / −1001801 end, −1006205 | **H names, V behaviour** (values consistent in 5 extrusions) |
| labeled-dimension constructor (§5); rounded-rect mixed loops (§4.7) | recipes only — **phase 2** |

Unknowns: (1) whether Revit REGENERATES a family form whose rep is
`SerializedDummy` (F4b) or requires our solid (F4a) — the four proof files
answer exactly this; (2) whether a form whose sketch has no dimensions /
constraints (ours) survives the family editor's regeneration (specimen
sketches all carry auto-dimensions); (3) the `Geometry.m_GInfo.
m_controlCommand` word (0 in the .rfa, 67145729 / 32768 in the rme copies)
— copied from context; (4) the box generator refuses extrude-UP (`end >
start`) and the cylinder generator refuses extrude-DOWN — each has
specimens in only one direction; the unified cap rule (§4.3) covers both
and can lift either restriction once accepted; (5) `FamilyGeomCombination`
(joining forms) not yet constructed — a form that must UNION with another
needs an `AddGeomToCombinationGStep`; (6) why the two equal half-arcs
tessellate to 7 vs 6 chords (§4.4) — reproduced, not explained; (7) the
614 `ExtrusionElem` also carries a `FamilyParametrizedElemParamsCell`
(family parameter 5447 driving its material property) — omitted from our
material-less forms.

## 9 · Reproduction

```
.venv/bin/python -m rvt.famgen.geometry            # both topology proofs (2 boxes + the 4-leg cylinder) + G_box_*/G_cyl_* .rfa + G_report.json
.venv/bin/python -m rvt.famgen.geometry --no-emit  # topology proofs only
.venv/bin/python -m pytest tests/test_famgen_geometry.py -q                      # 19 passed
# python:
#   from rvt.famgen import geometry as G
#   ctx = G.context_from_rfa()                       # family/level/graphics ids from a donor
#   ids = G._Ids(G._donor_watermark(G.SAMPLE_RFA) + 1)
#   fb  = G.box(G.mm(500), G.mm(300), G.mm(700), ctx, ids)          # or
#   fc  = G.cylinder(G.inches(3), G.mm(190), ctx, ids)              # 6 in recessed can
#   G.emit_form_rfa(G.SAMPLE_RFA, "out.rfa", [fb, fc])
#   G.reproduce_specimen_solid("rmebasicsampleproject", 243, 786867)   # box proof
#   G.reproduce_specimen_cylinders(G.SAMPLE_RFA, 0, 614)              # cylinder proof
```

# Wall hosting — panels mounted ON wall faces (the face-hosting model)

**Status: DECODED and IMPLEMENTED** (`src/rvt/hosting.py`, 15 tests in
`tests/test_hosting.py`, test files `experiments/hosting/H1..H3`).
Ground truth: the Revit MEP sample `rmebasicsampleproject` (Revit 2026).

The product goal is that panelboards created by our writer arrive
**mounted on walls**, not free-standing, so the QA engineer never re-hosts
40 panels. In Revit, MEP electrical equipment (panelboards, receptacles,
switches, disconnects) is *work-plane based*: an instance is never hosted
directly on a wall — it is hosted on a `SketchPlane` element that lies on
the wall's face. This document specifies that model completely.

## 1. The two hosting flavours in the wild

Survey of every `FamilyInstance` in the rme host document (5,629
instances): `m_hostId` classes = SWall 2,558 (doors/windows/curtain
panels, host-cut = phase 2), **SketchPlane 1,063**, Level 80, Floor 2.
The 1,063 SketchPlane-hosted instances share **240 distinct SketchPlanes**,
whose `m_oPlaneRef` polymorphic member falls into three classes:

| `m_oPlaneRef.ptr_class` | count (of 240) | what it is | who uses it |
|---|---|---|---|
| `DummyPlaneRef` | 218 | a free work plane with a stored `Plane`, **no reference to anything** | most panelboards (581482-85 on plane 581481), lighting on ceilings, duct/pipe accessories |
| `GeomOnPlaneRef` | 21 | a **face reference** into another element's geometry: `m_geomRef = {m_elemId, m_geomTag, m_subTag}` | 13 into `SWall` faces (panels 742670/622023/622026, receptacles, switches), 8 into other `FamilyInstance` faces |
| `OnDatumPlaneRef` | 1 | reference to a datum (level/ref plane) | — |

Both `DummyPlaneRef` and `GeomOnPlaneRef` planes render as a mounted
panel. The difference is **association**: a `GeomOnPlaneRef` plane makes
the wall the host (Revit reports the wall, moving the wall carries the
panel); a `DummyPlaneRef` plane is "<not associated>" — it merely happens
to be coincident with the wall face (plane 581481's `m_origin.x =
59.256374`, and wall 573608's +X face is at `x = 59.2564` exactly; the four
panels 581482-85 on it are physically flush on that wall but reference
nothing).

`src/rvt/hosting.py` writes either: `plane_ref="geom"` (default, true
association) or `plane_ref="dummy"` (the regeneration-independent
fallback).

## 2. The face reference is a SMALL STABLE TAG, not a GUID

All 13 `GeomOnPlaneRef -> SWall` planes:

| SketchPlane | wall | `m_geomTag` | `m_subTag` | face offset from location line |
|---|---|---|---|---|
| 573811 / 574263 / 574998 | 573596 / 574261 / 574646 | **1** | -1 | (the location-plane group; not used for hosting instances) |
| 595054, 623305, 623405, 625760, 626178 | 573703, 573590, 575086, 573738, 573768 | **5** | -1 | **-thickness/2** (right of the drawing direction) |
| 593910, 577820, 591345, 625865, 627076 | 573703, 573384, 573697, 573738, 573768 | **6** | -1 | **+thickness/2** (left of the drawing direction) |

Wall 573738 (and 573768, 573703) carries BOTH a tag-5 and a tag-6 plane
(receptacles on both faces of one interior partition), so the two side
tags are directly comparable on the same solid:

```
wall 573738  type 563416  dir (1,0)  thickness 0.3773 ft   (leftNormal = +Y)
  seq-103 GElement (the cached wall solid) face tags (Face.m_GInfo.m_tag):
     tag 5   side face   offset -0.1886   outward normal (0,-1,0)  <- SketchPlane 625760
     tag 6   side face   offset +0.1886   outward normal (0,+1,0)  <- SketchPlane 625865
     tag 7   bottom      normal (0,0,-1)
     tag 14  top         normal (0,0,+1)
     tag 10 / 18  end caps
  GGroup sub-nodes tag 1..4 = the four driven reference planes (m_pRefFaces)
```

So `m_geomTag` names a face of the wall's **geometry-generator solid**
(the same tag Revit's stable face references use), and for a basic
straight wall the two side faces are **always tag 5 and tag 6**:

* **tag 5** = the side face on the **-leftNormal** side (RIGHT of the
  wall's drawing direction) = **interior** for an unflipped wall
  (`m_isFlipped == false`, all corpus walls).
* **tag 6** = the side face on the **+leftNormal** side (LEFT of the
  drawing direction) = **exterior** (Revit places the exterior face on
  the left as you draw; draw clockwise to put exterior outside).
* `leftNormal = (-dy, dx)` where `(dx, dy)` = the location line's unit
  direction (`SWall.m_pCurveDriver.m_pCrv{GLine}.m_dirVec`).

`m_subTag = -1`, `m_offset = [0,0]` (the plane sits ON the face),
`m_angle = 0`, `m_flip = false`, `m_intermediateTags = []` (a direct
reference — no link chain), `m_foreignElemIdRef.m_id64 = -1` (host
document, not a linked model).

**Because interior/exterior are conventions of the drawing direction,
MEP intent ("the face that looks into the room") is best expressed as
`side_facing_point(doc, wall, point_inside_room)`** — the sample itself
mounts panels on the tag-6 ("exterior") face of wall 573608 because that
face happens to look into electrical room 573809.

Confidence: face tags 5/6 = the two side faces — **CERTAIN** (10 planes,
3 wall types, both orientations, plus the wall solids' own face tags).
Interior=5 / exterior=6 naming — **HIGH** (Revit's documented
draw-direction convention; unverified against a flipped wall — none in
corpus; `[hypothesis]` a flipped wall (`m_isFlipped`) swaps the sides).

## 3. The plane frame (`SketchPlane.m_oTrf`) — the vertical-face frame

`Trf.m_3x3` is stored **COLUMN-major** (the three columns are the local
X, Y, Z axes; the decoded JSON rows are `(X.i, Y.i, Z.i)`). For a wall-face
plane:

* **Z (3rd column) = the face's OUTWARD unit normal** (tag 5: -leftNormal;
  tag 6: +leftNormal),
* **Y (2nd column) = world +Z (up)**,
* **X (1st column) = up × Z** (lies along the wall; = +dir on the tag-5
  face, = -dir on the tag-6 face),
* `m_or` = a point ON the face plane, `z` = the wall base elevation
  (623405 `x=6.428` ft along, 623305 `3.937` ft (= 1.2 m), others `-0.049` —
  the origin's position along the wall is arbitrary; it is just where the
  plane was first anchored).

Verification (`tests/test_hosting.py::test_frame_formula_reproduces_every_real_plane`):
this formula reproduces the stored `m_3x3` **byte-for-byte on all 10
tag-5/6 planes**, including walls running along -Y where a naive
row-major reading would fail. Worked example, SketchPlane 595054 (tag 5
on wall 573703, dir (0,-1), leftNormal (+1,0)): Z = -leftNormal =
(-1,0,0), X = up×Z = (0,-1,0), so rows = `[[0,0,-1],[-1,0,0],[0,1,0]]` —
exactly the stored value (and exactly what H2 emits for its -Y wall).

There is no separate `Plane` object in a `GeomOnPlaneRef` plane (the
geometry comes from the referenced face); only `m_oTrf`. A `DummyPlaneRef`
additionally stores `m_pPlane -> Plane{m_origin, m_xVec, m_yVec}` — we
write it consistently (`xVec = X`, `yVec = Y = up`, so its implied normal
`xVec×yVec = Z`); the one catalogued dummy specimen (581481) uses an
author-arbitrary rotated frame, so this consistency is a choice, not a
constraint.

## 4. The hosted instance

A face-hosted `FamilyInstance` (verified on 742670 = a 480 V panel of
symbol 619617 on plane 623305, and on receptacles 460372 / 460229 on both
faces of wall 573738):

| field | value |
|---|---|
| `m_hostId` | the **SketchPlane** id (never the wall) |
| `m_workPlaneBased` | `true` |
| `m_assocLevelId` | `-1` (no level constraint) |
| `m_scheduleOnlyLevelId` | the level it schedules to (378117 = Level 1) |
| `m_hostParam`, `m_elevation` | `0.0`, `0.0` |
| `m_workPlaneFlipped`, `m_flippedX/Y` | `false` |
| `InstanceInfo.m_symbolId` | == `m_masterSymbolId` (no per-host geometry clone — unlike host-CUT doors) |
| **`InstanceInfo.m_Trf.m_3x3`** | **identical to the host SketchPlane's `m_oTrf.m_3x3`** (the instance sits un-rotated in the plane's frame) |
| `InstanceInfo.m_Trf.m_or` | the mounting point **ON the face plane** (742670: 7.8 ft along wall 573590, z = 7.53 = mounting height) |
| header `m_deletion` | includes the **SketchPlane**, the symbol, the level, the phase, self |
| header `m_regenOnly` | includes the **WALL** (573590) and the family |

Same-symbol proof: the three real 619617 panels (742670, 745912, 746575)
sit on three different tag-5 planes and each has `m_3x3` == its plane's.

## 5. Element parents (dependencies)

* Wall-face SketchPlane header (seq 101 `ElementHeader.m_parents`):
  **`m_deletion = [wall, self]`, `m_regenOnly = [wall_type]`**, all other
  lists empty (verified on all 10 tag-5/6 planes). Answering the task
  question directly: **yes — the SketchPlane's header lists the wall in
  `m_parents.m_deletion`** (deleting the wall deletes the plane; a type
  change re-solves the face).
* DummyPlaneRef SketchPlane header: `m_deletion = [self]` only.
* SketchPlane seq-103 rep = `SerializedDummy` (no cached geometry); it has
  an ordinary `ElemRec` in `Global/ElemTable` (owner INVALID, partition 0).

## 6. The writer (`src/rvt/hosting.py`)

```
wall_geometry(doc, wall) -> WallFaceGeom          # existing id OR NewElement
side_facing_point(doc, wall, point) -> 5|6          # face that looks at a room point
add_sketchplane_on_wall(doc, wall, side, at_point_ft=None,
                        plane_ref="geom"|"dummy") -> NewElement(SketchPlane)
host_instance_on_wall(doc, symbol_id, wall, distance_along_ft, elevation_ft,
                      side="interior"|"exterior"|5|6, sketchplane=None,
                      plane_ref="geom", level_id=None) -> [sketchplane, instance]
```

`add_sketchplane_on_wall` clones a real hosting SketchPlane
(auto-discovered `GeomOnPlaneRef->SWall` or `DummyPlaneRef` specimen),
rewrites `m_geomRef = {m_elemId: wall, m_geomTag: 5|6, m_subTag: -1}`,
builds the §3 frame from the wall's location line + thickness, and sets
the §5 parents. `host_instance_on_wall` reuses
`Document.add_family_instance(..., host_id=<new plane>)` (template = a REAL
face-hosted instance of the same symbol when one exists, so
`m_scheduleOnlyLevelId` and the parameter sets already have the hosted
shape), then imposes the §4 fields and the plane's frame. Both accept the
wall as an **existing element id or a wall planned in the same run**
(`Document.add_wall`'s NewElement) — `wall_geometry` reads the location
line / rebuilt `m_pRefFaces` from either.

## 7. Newly created walls (the electrical-room case)

For a wall created in the same commit, everything above is derivable
without regeneration: the face tags of a basic straight wall's solid are
**fixed by the geometry generator (5 / 6)**, the frame comes from the wall's
authored location line + type thickness, and all element ids (wall,
plane, instance) resolve inside the same commit. `H2` writes exactly this
(`GeomOnPlaneRef.m_elemId = 888014` = the new wall). What we **cannot
prove offline** is the *ordering* inside Autodesk's regenerator: our new
wall's seq-103 is a `SerializedDummy`, so its solid (and therefore face
tag 5) only exists after Revit regenerates the wall; if the SketchPlane's
face reference is resolved before that solid is built, the reference is
transiently dangling. The rme corpus never contains a plane referencing a
not-yet-regenerated wall (Autodesk always saves post-regeneration), so
this is an acceptance-test question, and `H3` (same room, plane =
`DummyPlaneRef` coincident with the new wall's face, **no reference into
the wall at all**) is delivered as the guaranteed-safe fallback. Verdict
matrix for the orchestrator's viewer run:

| H1 | H2 | H3 | conclusion |
|---|---|---|---|
| PASS | PASS | – | full face-hosting works, including on created walls |
| PASS | FAIL | PASS | face-refs into created walls need regeneration; ship `plane_ref="dummy"` for created walls, `geom` for existing |
| PASS | FAIL | FAIL | created-wall hosting needs the wall's cached solid (author its GElement) — separate stream |
| FAIL | * | * | face-hosting record shape wrong — re-open this doc |

## 8. Deliverables

| file | proves |
|---|---|
| `experiments/hosting/H1_panel_on_existing_wall.rvt` | new SketchPlane (`GeomOnPlaneRef` → EXISTING wall 573608, tag 6, the face looking into room 573809) + new 480 V panel (symbol 619617, id 888015) hosted on it (`m_hostId` = plane 888014). 6 ft along the wall, 4 ft above Level 1, clear of the sample's own panels 581482-85 further down the same face. |
| `experiments/hosting/H2_panel_on_created_wall.rvt` | NEW partition (id 888014, type 563416, inside room 573809: x=64.5, y 118→106, 8 ft) + SketchPlane 888015 (`GeomOnPlaneRef` → the NEW wall, tag 5) + hosted panel 888016 — the electrical-room-from-scratch case. |
| `experiments/hosting/H3_panel_on_created_wall_dummyplane.rvt` | identical to H2 but the plane is a `DummyPlaneRef` coincident with the new wall's face (no reference into the wall) — the fallback / control for H2. |
| `experiments/hosting/manifest.json` | per-file element ids, notes, `verify_written` report (CRC/ECC/walker/stamps all clean, all new records decode clean in seqs 101/102/103, counts match, sentinels last) and a decode-readback of the hosting fields. |
| `experiments/hosting/make_hosting.py` | reproduces the three files (`.venv/bin/python experiments/hosting/make_hosting.py`). |

## 9. Unknowns / open questions

1. **Regeneration ordering for face-refs into created walls** (§7) — H2 vs
   H3 in the Autodesk viewer decides it. `[the one honest blocker]`
2. **Flipped walls**: `[hypothesis]` `SWall.m_isFlipped = true` swaps which
   side tag 5/6 land on. No flipped wall in the corpus; `side_facing_point`
   is immune (it resolves the face by geometry, not by name).
3. **Non-basic walls**: curtain walls / walls with edited profiles have
   different geometry generators; tag 5/6 is proven only for basic
   straight (`SWall` + `GLine`) walls — exactly what `Document.add_wall`
   creates.
4. **Family Z convention**: the frame (§3) fixes the *plane*; a family
   authored with unusual internal axes lands rotated within the plane.
   Panels of symbol 619617 are proven correct against three real specimens;
   arbitrary families are `[expected]` (the rule "instance 3x3 == plane 3x3"
   held for every hosted family in the sample: 619617, 742645, 621990,
   620368 panels, 342654 receptacles, 370023/543268/542320/856972 devices,
   470440-family panels).
5. `OnDatumPlaneRef` (1 plane) and `GeomOnPlaneRef -> FamilyInstance` (8
   planes: gear mounted on other gear, geomTag 7/57) are catalogued but not
   implemented (not needed for wall mounting).

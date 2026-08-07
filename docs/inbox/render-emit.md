# inbox — render-emit (BAKED WALL GEOMETRY: the native rep grammar, an exact constructor, and the render probes)

Stream: **render-emit** (2026-08-04). Charter (ORCHESTRATOR VERDICTS #22,
open item A — LOAD IS NOT RENDER): reproduce the diff between a native
wall's full record set and our created wall's, name the geometry-bearing
record(s) ours lack, CONSTRUCT the wall's baked geometry in the same
grammar the natives use (prefer the B-rep grammar `rvt.famgen.geometry`
already authors byte-exact), provide `bake_wall_geometry(doc, wall_id)`,
and re-emit the room's walls-only stage baked + a single-wall minimal
probe on the certified genesis base ZA_deep, with a control and a
manifest.  Territory touched ONLY: `src/rvt/render/wallgeom.py` (new),
`tests/test_render_wallgeom.py` (new, 15 pass),
`experiments/ifc_room/render/**` (7 files + `probes.json` +
`render_build.json` + 2 fixtures), this file.  No existing
`src/rvt/*.py`, `tools/*`, test, sample or the sibling stream's
`src/rvt/render/{__init__,inspect,brep}.py` was edited (everything is
IMPORTED).  No browser / viewer used — the probes await the orchestrator's
gate.

## Result in one screen

* **THE DIFF (item A) IS EXACTLY ONE RECORD.** Native wall vs ours, all
  three seqs: the seq-101 headers and seq-102 objects are structurally
  peers (ours already carries the location line, the four rebuilt
  `m_pRefFaces` planes and the cloned `GeomStepList` whose `BaseWallGStep`
  DECLARES a 6-face/12-edge box with concrete tags); the seq-103 rep is a
  ~8.7 KB `GElement` B-rep on every native wall (413/413 in the sibling
  archaeology census) and a **2-byte `SerializedDummy`** on ours
  (`mutate.add_wall` sets `rep=None` — the T1 "Revit regenerates" bet,
  which desktop Revit honours and the cloud extractor does not).  LOAD is
  not RENDER because there is nothing to draw.  No cell / ElemTable /
  ADocument registration is missing — the `GeomTable` tag->generator map
  and the step tables live inside the wall's own seq-102 object, and the
  ElemRec has no rep field.  **The fix is a seq-103 record substitution
  (+ optional seq-102 bookkeeping normalization); nothing else moves.**
* **THE NATIVE WALL REP GRAMMAR IS DECODED TO THE LEAF, AND OUR
  CONSTRUCTOR REPRODUCES REAL NATIVE WALLS EXACTLY.**
  `src/rvt/render/wallgeom.py` builds, from a wall's own object + type,
  the same `GElement` a Revit save baked: root `GElement(cat = Walls
  GStyle, tag = id, flags 557060)` -> **4 x `GGroup`** (the
  `WallRefPlanesGStep` reference planes, category = the -2000896 GStyle
  24925, node order by history KEY 39/30/29/40, each `Geometry` -> 1 open
  planar quad + 4 single-face edges) + **1 solid `Geometry`** (the
  `BaseWallGStep` box: 6 planar `Face`s each with an `EdgeLoop`, a
  `Plane` and a `GFilling`, 12 `Edge`s) with the natives' archive pid
  numbering (root subnodes 3.., group geometries next, solid faces 12-17,
  edges 18-29, group quads, then loops/fillings/planes -- `assign_pids`
  reproduces it) and every weak reference resolved.  **PROOF:
  `reproduce_native_wall` rebuilds four native rme walls from their own
  objects and diffs the result against their real seq-103 records: ZERO
  differing leaves** on all four (single-layer 573386 / 573735 / 573763
  and the two-layer 575873) modulo the one field that is per-element
  garbage in the natives themselves (`Geometry.m_GInfo.m_controlCommand`,
  see G6).  The reproduction runs in the tests off two saved fixtures (no
  corpus) — `tests/test_render_wallgeom.py`, 15/15 pass.
* **THE GRAMMAR IS THE FAMGEN BOX -- with wall-specific numbering, frames
  and dressing** (the archaeology stream's calibration table is confirmed
  independently): the box is the elevation rectangle (length x height)
  extruded through the THICKNESS -- caps = the two long faces (history
  keys [2]/[1] = the MIN-/MAX-offset side planes along the left normal,
  NOT keyed to compound key 29/30), sides = start/finish/bottom/top (keys
  [3,0..3]), rails [1,curve,cap], laterals [2,i,j] between consecutive
  cycle curves -- famgen's `_box_tags` layout at a base tag B (= the tags
  the WallRefPlanesGStep consumed) with the two cap tags swapped and the
  face list in ascending-tag order.  Plus: cap-face GInfo 557572 vs
  thin-face 558596, per-key GGroup/face/edge flags, a `GFilling` per solid
  face whose placer origin = the location-line START base point projected
  onto the face and whose direction = Z x n_out (vertical faces) / the
  wall direction (horizontal faces), materials per face (single layer:
  the layer material everywhere; multi-layer: caps = their exterior
  layer, thin faces = the FIRST layer), `m_bBox == m_tightbBox` = the
  exact solid AABB.  For a multi-layer type the compound keys 29/30 are
  the STRUCTURAL layer's boundaries (interior planes); the solid's exterior
  faces come from the compound grid's outer segments, the cs->world map
  fixed by the two known key planes (this is how `m_isFlipped` acts --
  derived, not interpreted).  All [V], sections G1-G6.
* **TWO WRITE PATHS, BOTH WORKING, NO EXISTING MODULE EDITED.**
  (a) **create-time**: `bake_planned_wall(doc, new_element)` sets
  `NewElement.rep` = the constructed GElement (mutate already emits a
  GElement record when `.rep` is not None) and normalizes the object's
  geometry bookkeeping to the canonical unjoined state; the standard
  `commit_new_elements` path writes it.  (b) **existing file, in place**:
  `bake_wall_geometry(src, out, wall_ids)` swaps each wall's seq-103
  (+ seq-102) records through the certified `regadd.substitute_elements`
  (same ids / ElemTable rows / positions, Global/Latest byte-identical;
  the 2-byte dummy grows to the ~6.9 KB GElement and unit 0 is
  re-blocked; verdict VALID).
* **SEVEN VALIDATOR-CLEAN PROBE FILES + probes.json** (gate-`check`
  ADMISSIBLE, section P): the certified base's control; the room's four
  walls baked (`walls_baked.rvt`, canonical bookkeeping) and baked
  rep-only (`walls_baked_reponly.rvt`); the four walls UNbaked
  (`walls_only_dummy.rvt` = the LOAD-certified wall state, rebuilt as the
  wall-layer control); a single baked wall (`wall_baked_min.rvt`) and its
  root-category-(-1) twin (`wall_baked_min_catneg.rvt`); and a
  **diagnostic on the rst SAMPLE** (`diag_rst_wall_baked.rvt`) that
  separates "our baked geometry" from "the genesis base lacks the Walls
  category catalog rows" (section B4).  Every created wall in the baked
  files reads back as a decode-clean, audit-clean `GElement`, and the
  sibling stream's `rvt.render.inspect` independently reports `brep /
  baked=YES / drawable_3d` for all of them.  Build deterministic (md5s
  reproduce), ~21 s for the whole set.
* **THE HONEST CO-BLOCKER (not geometry): ZA_deep has NO Walls-category
  projection GStyleElem** (the rst lineage's row 30 -- the id every native
  wall rep names as its root `m_GInfo.m_categoryId` -- is one of the
  catalog rows the R9->ZA_deep reductions GC'd away; the base's catalog
  DOES have the rows for Levels 144 / Doors 44 / Electrical Equipment 124 /
  Lines 69 / the ref-plane category 24925 / fills 32, all of which render or
  are used).  If the extractor needs the category style to draw a wall,
  the ADD-cat rung (the 235 GC'd built-in category rows, Walls first) is a
  RENDER prerequisite independent of our geometry -- the rst-hosted
  diagnostic and the -1/30 root-category A/B are built to answer exactly
  that.

---

## A. The diff (item A of the charter): native record set vs ours

Reproduced this session, decoded field-by-field with `rvt.objects` (all
scripts under the session scratchpad, results here):

| record | native wall (rst 493879 / 1115258, rme 573386) | our created wall (walls-only files, ids 1472525-8) |
|---|---|---|
| seq-101 `ElementHeader` | class 0x5e5, `m_categroyId` -2000011, `m_pBBox` = the solid's box, parents incl. the Walls GStyle 30 | same shape; category -2000011; bbox from `add_wall`; parents filtered to existing ids (30 dropped -- absent from ZA_deep) |
| seq-102 `SWall` object | location GLine, 4 `m_pRefFaces` (tags 1-4), `m_geomSteps` (`WallRefPlanesGStep` id 3 + `BaseWallGStep` id 1 + `VerticalExtensionOfLayersGStep` id 2 + tweak/join steps), `m_pGeomTable` (tag -> generating step), `CoverSettingsCell`, cached `SnapshotData` (topology only, empty `m_snapshotGRep`) | the SAME (cloned from the R5 specimen 1115258 and repaired by `_clean_wall_clone`): 4 rebuilt ref planes at the new line, the identical B=5 tag layout (faces 6/5/18/10/7/14, edges 19,20,11,12,8,9,15,16,22,17,13,21), a 39-entry GeomTable still naming the specimen's join generators, join steps dropped in 'unjoin' mode, snapshots null |
| **seq-103 rep** | **`GElement`, 6,884 - 11,030 B: 4 GGroup ref planes + a 6+ face solid** | **`SerializedDummy`, psize 2 -- NOTHING to draw** |

So the geometry-bearing record ours lack is the seq-103 GElement, and
the "geometry cell registration" the brief suspected does not exist as a
separate structure: the tag map (`m_pGeomTable`) and the step tables are
inside seq-102 and were already cloned.  The single caveat: our clones'
bookkeeping still names the specimen's JOIN generators (tags 23-38 ->
steps 6/7/4 that the unjoin trim removed) and its `CoverSettingsCell`
still lists the specimen's join faces (27, 32).  Both are reader-
tolerated at LOAD (the walls-only files PASSED), and the render draws
seq-103, but `normalize_geometry_history` restores the exact native
standalone-wall state (section H) so the primary probes are internally
consistent.

## B. The base's catalog: what a wall rep references, and what ZA_deep has

Ids a native wall rep names, and their status on the certified base
(measured on `CTRL_ZA_deep_ifcroom.rvt`, md5 `56308637...` = ZA_deep):

| referenced element | role in the rep | in rst | in ZA_deep |
|---|---|---|---|
| GStyleElem 30 (cat -2000011 Walls, projection) | root `GElement.m_GInfo.m_categoryId` | present | **ABSENT** (a GC'd catalog row) |
| GStyleElem 24925 (cat -2000896, the ref-plane geometry category) | the 4 GGroups' `m_GInfo.m_categoryId` | present | present |
| GStyleElem 32 (cat -2000540) | every `GFilling.m_GInfo.m_categoryId` | present | present |
| MaterialElem 600660 (the type's layer material) | solid faces' `m_renderStyleId` | present | present ("GEN Concrete, Cast-in-Place", ours; `m_surfacePatternId = -1` -> the empty filling form) |
| MaterialElem 24 ("Default") | the ref-plane quads' `m_renderStyleId` | present | ABSENT -> we write -1 (INVALID = category default; the ref planes never draw in 3D anyway) |
| FillPatternElem 448 / 3 | surface / cut pattern data | present | present (ours) |

**B4 -- why this may block RENDER regardless of geometry.**  ZA_deep's
category catalog (GStyle rows keyed by built-in category) covers Levels
(144), Doors (44/45), Electrical Equipment (124), Lines (69), the
ref-plane category (24925), fills (32/33) -- and NOTHING for Walls
(-2000011) or Floors.  Levels render on this lineage; equipment instances
are the archaeology stream's next question; walls have no category row
at all.  If the extractor resolves an element's category style before
tessellating (a plausible visibility gate), a wall on ZA_deep draws
NOTHING no matter how perfect its rep -- and the cure is the genesis
ADD-cat rung, not this stream.  Hence:

* the primary probes name **root category 30** (the lineage's Walls
  GStyle id -- dangling on ZA_deep today, valid the moment the ADD-cat rung
  restores the rows at their lineage ids; dangling ids are LOAD-tolerated
  per R5/R9), with a **-1 twin** (`wall_baked_min_catneg.rvt`);
* the **rst-hosted diagnostic** builds one baked wall with the SAME
  constructor on the untouched rst SAMPLE, where row 30, material 24 and
  native walls all exist -- if it renders there and not on ZA_deep, the
  blocker is the catalog, not the geometry (section P reading matrix).

## G. The wall rep grammar (all [V] unless marked)

Sources: rst 493879 (type 600634, joined, B=8), rst 1115258 (type 600634 =
the R5 specimen our clones descend from, doubly joined, B=5), rme 573386 /
573735 / 573763 / 575873 (UNJOINED standalone walls, B=5) -- the four rme
walls are reproduced leaf-for-leaf by the constructor.

**G1 -- Root and node structure.**

| node | class | `m_GInfo{cat, tag, ctl, flags}` | body |
|---|---|---|---|
| root | GElement (0x89e) | `{Walls GStyle (30), elem id, 0, 557060}` | `m_subNodes` = [4 GGroups, 1 Geometry], `m_bBox` == `m_tightbBox` = the solid's exact world AABB, `m_elementId` = id, `m_gElemType 3`, `m_flags 0` |
| ref plane k (x4) | GGroup | `{-2000896 GStyle (24925), ref-face tag, 0, per-key}` | `m_subNodes` = [1 Geometry] |
| its geometry | Geometry | `{-1, -1, garbage, 573444}` | 1 `Face` (open quad) + 4 `Edge`s, `m_flags 7`, `m_geometryTag -1`, `m_tessEpsCntrl {0, version 1}`, `m_sharedSurfInfo []` |
| the solid | Geometry | `{-1, -1, garbage, 573444}` | 6 `Face`s + 12 `Edge`s (same tail fields) |

Node ORDER of the four GGroups = by history KEY **39, 30, 29, 40** (the
native node tags therefore run 4, 3, 2, 1 for a wall whose ref-face tags
are 1..4).  Per-key constants (3/3 walls, both files): GGroup flags
{39: 168329380, 30: 34111648, 29: 34111648, 40: 168329892}; quad-face
GInfo flags {39: 67665924, 30: 67665920, 29: 67665920, 40: 67666436};
quad-edge GInfo flags {39: 557060, 30: 557056, 29: 557056, 40: 557572}.
The quad = the ref face's own plane (origin/xVec/yVec/envelope straight
off `m_pRefFaces[k].m_pSurf`), `m_faceFlags_v9 36`, material = the
Default material, 4 open edges (`m_pFace = [face, 0]`, `m_flags 6`,
chained e0->e1->e2->e3 through the loop; uv corners (0,0)->(L,0)->(L,H)->
(0,H)).  The ref-plane category is in the standard 3D view's EXCLUDED
category list (`genesis.skeleton.DRAW_EXCLUDED_CATEGORIES['3d']` has
-2000896): the quads never draw -- they exist for the reference-plane
machinery.

**G2 -- The keys.**  `WallRefPlanesGStep.m_faceHistTable` maps ref-face
tag -> key: 29 / 30 = the compound-structure grid segments named by
`CompoundStructure.m_segRefFaceKeys` (single-layer type: the two exterior
side planes; multi-layer: the STRUCTURAL layer's boundaries), 39 = the
core centre plane, 40 = the location-line plane; a joined wall adds keys
31/32 (no rep node).  `BaseWallGStep.m_faceHistTable` maps solid-face
tag -> key: `[2,-1,-1]` and `[1,-1,-1]` = the two long faces (CAP2 /
CAP1), `[3,k,-1]` = the four thin faces (k: 0 start end, 1 finish end, 2
bottom, 3 top); its `m_edgeHistTable`: `[1,i,side,-1]` = the rail of thin
face i on cap `side` (0 = CAP2, 1 = CAP1), `[2,i,j,-1]` = the lateral
between consecutive cycle curves i -> j.  `m_pGeomTable.m_table[tag]
.m_geomGeneratorId` = the m_id of the step that generated `tag` (a
standalone wall: tags 0..B-1 -> the ref step (3), tags B..B+17 -> the
BaseWallGStep (1); B = 5 for a 4-plane wall, 8 for rst 493879's 7 planes).

**G3 -- The solid's frames (min = the CAP2 side offset along the left
normal L = (-D.y, D.x, 0), max = CAP1's; O/D/t0/t1 = the location GLine).**

| face (key) | tag | GInfo flags | plane origin | xVec | yVec | uv envelope |
|---|---|---|---|---|---|---|
| CAP2 [2] | B+0 | 557572 | O + min*L (base z) | D | Z | u [t0,t1] x v [0,H] |
| CAP1 [1] | B+1 | 557572 | O + max*L | -D | Z | u [-t1,-t0] x v [0,H] |
| BOTTOM [3,2] | B+2 | 558596 | P(start, min, base) | L | D | u [0,T] x v [0,len] |
| FINISH [3,1] | B+5 | 558596 | P(end, min, base) | L | Z | u [0,T] x v [0,H] |
| TOP [3,3] | B+9 | 558596 | P(end, min, top) | L | -D | u [0,T] x v [0,len] |
| START [3,0] | B+13 | 558596 | P(start, min, top) | L | -Z | u [0,T] x v [0,H] |

**CAP2 is ALWAYS the MIN-offset side**, independent of which compound key
sits there (rme 573386: key 29 = min; rme 573735 / 575873: key 29 = MAX,
CAP2 still = min) -- the box orientation is geometric, the key numbering
is the compound structure's.  Face list order (and pid order) = ascending
tag.  All faces: `m_faceRegions []`, `m_oBackgroundFilling` null,
`m_cutType 0`, `m_faceFlags_v9 4`, `m_renderStyleId` = the material.

**G3b -- The 12 edges** (list order = ascending tag: [1,2,0] B+3,
[1,2,1] B+4, [1,1,0] B+6, [1,1,1] B+7, [2,2,1] B+8, [1,3,0] B+10,
[1,3,1] B+11, [2,1,3] B+12, [1,0,0] B+14, [1,0,1] B+15, [2,3,0] B+16,
[2,0,2] B+17 -- exactly famgen's `_box_tags(4)` + B with the caps
swapped).  Each rail is stored FORWARD in its cap's loop (`m_flags` 6):
CAP2's loop runs the elevation rectangle CCW (bottom +D, finish +Z, top
-D, start -Z), CAP1's is the reverse cycle; the closing lateral [2,0,2]
(start^bottom vertex) runs min->max with flags 6, the other three
laterals run max->min with flags 7; `m_pFace = [rail's cap or lateral's
face(j), the side face]`; GInfo flags 557572, tag = the edge tag, ctl 0;
`m_next/m_prev[slot]` = the neighbours in that face's loop (the EdgeLoop
itself at the chain ends); `m_firstAndLastEdgePnts` = both end points'
uv in BOTH adjacent face frames; `m_interiorEdgePnts []`.  Per-face loop
orders (famgen's pattern): CAP2 = the cycle rails on side 0, CAP1 = the
reversed cycle on side 1, each thin face = [its cap-2 rail, the lateral
at its cycle-start vertex, its cap-1 rail, the lateral at its cycle-end
vertex].  Each `EdgeLoop`: GInfo flags 524292, `m_nextLoop` null,
`m_pFace` = its face, `m_next/m_prev` = first/last edge, `m_Envelope` =
the face envelope, `m_open false`.

**G4 -- The GFilling on every solid face.**  `GInfo{cat = the -2000540
GStyle (32), -1, 0, 524292}`, `m_pGFace` = the face, `m_placer{scale 1,
origin, dir, uvScale [1,1], mirrored false, draft false}`, `m_data`
null.  **Placer origin = the location line's START point at the base
elevation (A = O + D*t0) projected onto the face's uv; placer dir = the
uv projection of Z x n_out for vertical faces and of the wall direction D
for the two horizontal faces** -- reproduces all 6 placers of every rme
wall and both caps of the rst walls.  No surface pattern (our material
600660, every rme wall): `m_patternId -1`, `m_fillColor 16777216`
(0x1000000), `m_flags 18`.  With a surface pattern (rst concrete caps):
`m_patternId` = the material's `m_surfacePatternId`, `m_fillColor` = its
colour, `m_flags 8`, `m_data` = a `FillPatternData` cache of the pattern
-- the thin faces STILL carry the empty form.  (The pattern branch is
[hypothesis]-marked in code: our target material has no pattern, so the
probes ride the verified empty form.)

**G5 -- Materials.**  Single-layer type (ours; rme 573386/573735/573763):
every face's `m_renderStyleId` = the layer's material.  Multi-layer (rme
575873, layers 0.3937 + 0.8202 ft): CAP2 / CAP1 = the material of the
layer whose EXTERIOR boundary they are; all four thin faces = the FIRST
layer's material [1 specimen -- hypothesis-marked].  The layer widths and
the grid coordinates give the exterior side offsets (the keys' cs coords
+ their world offsets fix the affine cs->world map; its sign IS the
`m_isFlipped` effect -- derived, never interpreted).

**G6 -- Two things that are NOT what they look like.**
(i) `Geometry.m_GInfo.m_controlCommand` = a per-element garbage bit
field (differs between two walls of the SAME rst file: 84115474 vs
67272737; rme 151457864; FamilySymbol geometries mostly 0) -- not a
checksum; we write 0.  (ii) The seq-102 `SnapshotData` (`m_bRepForm-
Snapshot` / `m_bRepAdjustSnapshot`) is TOPOLOGY only: `m_geomTops` =
[GeometryTopology{ faces: [{m_id: face tag, m_edges: [4, +-(edge tag +
1), ...]}] ...}] (sign = orientation in that face; rails negative in the
side loops), an EMPTY `m_snapshotGRep` (bBox +-1e30), `m_valid true`.  Our
'unjoin' clones carry NULL snapshots and LOADED, so the primary probes
null them (the topology grammar is documented here for a future rung;
render draws seq-103).

## R. The reproduction proof (how "exact" was measured)

`reproduce_native_wall(doc, wall_id)` = spec from the wall's own object +
type (`wall_render_spec`) -> `build_wall_gelement` -> `diff_reps` against
the real seq-103 record (every leaf, pids included, floats to 1e-6),
ignoring only `m_controlCommand`; plus `audit_wall_rep` (weakref
targets, loop closure, uv<->3D agreement between each edge's two face
frames, tag sets, bbox).  Results (`python -m rvt.render.wallgeom
reproduce rmebasicsampleproject <id>`, RVT_SEG_CACHE set):

| wall | type | note | diff leaves | audit |
|---|---|---|---|---|
| rme 573386 | 563414 single layer 200 mm | key 29 = min side, isFlipped True | **0** | 0 |
| rme 573735 | 563416 single layer 115 mm | key 29 = MAX side, isFlipped False | **0** | 0 |
| rme 573763 | 563416 | same shaft group | **0** | 0 |
| rme 575873 | 563418 TWO layers, keys 29/30 interior | exterior offsets + per-side materials derived from the grid | **0** | 0 |

The derivation path (materials / offsets from the compound structure
rather than read off the native) reaches the same 0 (test
`test_multilayer_materials_derived_from_the_type_not_read`).  The two
fixtures `experiments/ifc_room/render/fixtures/native_wall_rme_*.json`
(the walls' decoded records + their type objects; derived data of the
Autodesk sample, labelled as such) let the tests run this in 1.7 s
without the corpus.  The rst walls are not reproduction targets (all
joined -> extra join faces/edges by design), but their shared parts
(GGroups, cap flags, filling grammar, per-key constants) were the
cross-check.

## H. The APIs (`src/rvt/render/wallgeom.py`)

* `wall_render_spec(doc, wall)` -> `WallRenderSpec` (location line,
  base z, height from BIP -1001101 / -1001105 / the header bbox, side
  offsets from the ref planes + the compound grid, tags from the wall's
  own step tables (canonical fallback), materials, the category GStyles by
  built-in id, pattern; warnings for every fallback).
* `build_wall_gelement(spec)` -> the GElement dict (pid-numbered via
  famgen's `_number_graph` over symbolic weakrefs; asserted pid-stable).
* `audit_wall_rep(rep, spec=...)` -> problems list (also runs on natives).
* `normalize_geometry_history(obj, spec)` -> the canonical UNJOINED
  bookkeeping (steps = [RefPlanes 3] / [BaseWall 1] / [VertExt 2], join /
  tweak / cutout lists emptied, snapshots nulled, `m_idCounter` = max step
  id + 1, the step-list 'joined' flag bit cleared (11 -> 9), `m_pGeomTable`
  rebuilt to exactly the rep's tags (39 stale entries -> 23), the
  `CoverSettingsCell` concealed (join) faces cleared).  On the room walls:
  `{'idCounter': [8, 4], 'gsl_flags': [11, 9], 'geom_table': [39, 23],
  'concealed_faces_cleared': [27, 32]}`.
* `bake_planned_wall(doc, el, ...)` (create-time) and
  `bake_wall_geometry(src, out, wall_ids, ...)` (existing file, via
  `regadd.substitute_elements`), `render_readback(path)` (decode + audit
  + the archaeology inspector when importable), `build_render_probes()`
  (the whole probe set + manifest), `dump_native_fixture` /
  `load_fixture_doc` (the test oracles).  CLI: `python -m rvt.render.wallgeom
  {reproduce,bake,audit,fixture,all}`.

## P. The probe set (`experiments/ifc_room/render/`, base = ZA_deep, control declared)

Built by `.venv/bin/python -m rvt.render.wallgeom all` (~21 s,
deterministic).  All: validator VALID / 0 errors (the 1 warning = the
base's own pre-existing DataStorage ES-blob decoder gap, byte-identical in
the parent), structural proof green, every created wall in the baked
files reads back as a decode-clean, audit-clean GElement (and
`rvt.render.inspect` says `brep / baked / drawable_3d`).  `probe_batch
check` on both batches -> ADMISSIBLE.

| file | md5 | what it is | reads |
|---|---|---|---|
| `CTRL_ZA_deep_render.rvt` | `56308637…` | byte-identical copy of the certified base | round validity (FIRST) |
| `walls_only_dummy.rvt` | `9e8d64f0…` | the room's 4 walls UNbaked (SerializedDummy reps) = the LOAD-certified wall-layer state, rebuilt this session | the wall-layer LOAD control (must PASS; renders nothing by design) |
| `wall_baked_min.rvt` | `58cf7111…` | ZA_deep + ONE baked wall (20 ft x 3.66 m, root cat 30) | the cleanest render test |
| `wall_baked_min_catneg.rvt` | `cbc83295…` | the same wall, root category -1 | the root-category A/B |
| `walls_baked.rvt` | `1802fe89…` | the room's 4 walls BAKED + canonical bookkeeping | the wall layer renders (the 9.2 x 6.2 m ring) |
| `walls_baked_reponly.rvt` | `b4b7e479…` | 4 walls baked, cloned bookkeeping UNTOUCHED | isolates the bookkeeping variable |
| `diag_rst_wall_baked.rvt` | `f473c901…` | DIAGNOSTIC: one baked wall by the same constructor on the untouched rst SAMPLE, typed with the sample's own 600634 (CL_W1; Walls GStyle 30, Default material 24 and native walls all present) | separates 'our geometry' from 'ZA_deep lacks the Walls category rows' |

**Reading matrix** (the RENDER gate = wall nodes under the level in the
model tree + visible walls in {3D}; LOAD as before):

* control FAIL -> the round is VOID.
* dummy control LOAD-PASS + `wall_baked_min` renders -> **created walls
  RENDER; LOAD is now also RENDER for the wall layer.**  Then read
  `walls_baked` (the room ring) and note whether `_reponly` also renders
  (does the bookkeeping matter to the extractor?).
* `wall_baked_min` LOAD-PASS but empty model tree -> the geometry did not
  draw.  Now the diagnostic decides: **if `diag_rst_wall_baked` RENDERS,
  the blocker is the missing Walls category rows on ZA_deep (the ADD-cat
  rung), not the geometry**; if it does NOT render either, the fault is in
  the constructed grammar (read the card + tree; the archaeology stream's
  independently-built solid-only probe `experiments/render/RSOLID_walls_A_
  solid.rvt` is the natural second opinion -- see section X).
* `wall_baked_min` PASS vs `_catneg` FAIL (or the reverse) -> the root
  category id form is the discriminator; keep the winner.
* any baked file LOAD-FAILS while `walls_only_dummy` PASSES -> the bake
  itself trips the audit: bisect `walls_baked_reponly` (rep only) vs
  `walls_baked` (rep + bookkeeping).

Stage into the gate:
`.venv/bin/python tools/probe_batch.py stage experiments/ifc_room/render/
{walls_baked,walls_baked_reponly,wall_baked_min,wall_baked_min_catneg,walls_only_dummy}.rvt
--manifest experiments/ifc_room/render/probes.json`
(and separately `diag_rst_wall_baked.rvt`, whose base is the rst sample).

## X. Coordination with the archaeology stream (`docs/inbox/render-archaeology.md`)

Their record landed while this stream was building; the two are
complementary and agree on every shared fact (storage location, the
famgen-identical constants, the SerializedDummy diagnosis, the Walls-
GStyle question).  Their `rvt.render.inspect` is now this stream's
independent read-back lens.  Their `rvt.render.brep` is a SECOND,
simpler constructor: the solid alone via `solid_box_brep` re-tagged
(footprint extruded vertically, root category -1, uniform face flags, no
GFillings, optional ref planes).  This stream's `wallgeom` is the
native-exact one (proof: section R).  The gate therefore has TWO
independent constructions of the same solid to A/B: **their
`RSOLID_walls_A_solid.rvt` (in-place, seq-103 only, on the walls-only
file) and our set** -- if either renders and the other does not, the
delta between them is small and named (frames / flags / fillings / ref
planes / root category), which is the fastest possible convergence.
Their KNOWLEDGE retraction request (V26 showed instances, not walls; no
native 3D element is ever dummy) is seconded by the reproduction proof.
One suggested one-line addition to their `src/rvt/render/__init__.py`
docstring (not applied -- their file): list `rvt.render.wallgeom` and
`rvt.render.brep` beside `inspect`.

## §5 What this stream did NOT establish (honest gaps)

* **The viewer verdict** -- the whole point of the probes; nothing here
  has been uploaded.  Every VALID / clean above is the machine gate.
* **Whether the extractor needs the Walls category catalog rows** (section
  B4) -- the diagnostic + the -1/30 A/B are built to answer it; if it does,
  the fix is genesis' ADD-cat rung, outside this territory.
* **Joined walls** (join faces from `JoinEndGStep`s), face-hosted inserts
  (door cut-outs = `WallCutoutGStep`s), arc walls (`GArc` drivers ->
  cylindrical faces; the constructor raises `WallRenderError`) -- the
  unjoined straight wall is the certified path; the room's door OPENINGS
  are still not cut (recorded in the intent).
* **The GFilling pattern branch** (materials WITH a surface pattern:
  `FillPatternData` derivation) -- our material has none; the branch is
  [hypothesis]-marked and warns.
* **The multi-layer thin-face material rule** is one specimen (rme
  575873); our type is single-layer, where the rule is certain.
* **`mutate.add_wall` still emits the dummy by default** -- deliberately not
  edited (not this territory); the create-time bake is opt-in via
  `bake_planned_wall`.  The archaeology stream's request #3 (route the
  emission change to the creation path) is served WITHOUT a mutate edit:
  `NewElement.rep_class_id` already switches to GElement when `.rep` is set.

## §6 Requests for the orchestrator

1. **VIEWER-GATE the render set** (section P reading matrix), reading the
   model tree of each baked file for wall nodes; read the archaeology
   stream's `RSOLID_walls_A_solid` in the same round for the A/B.
2. **KNOWLEDGE.md merges**: (i) the wall rep grammar summary (this record,
   sections G1-G6) with the reproduction proof line; (ii) the correction
   *"m_bBox == m_tightbBox = the exact solid AABB for unjoined walls; the
   Geometry-node m_controlCommand is per-element garbage (write 0)"*;
   (iii) *"a wall's compound keys 29/30 name the structural layer's grid
   segments; the box caps are the min/max-offset planes (multi-layer:
   from the grid's outer segments); the flip flag is encoded in the
   cs->world sign and can be derived from the two key planes"*; (iv)
   second the archaeology retractions.
3. **If the diagnostic renders and ZA_deep does not: prioritize the
   ADD-cat rung's Walls row** (GStyleElem 30 at its lineage id, so the
   already-emitted probes need no change).
4. **PLUGIN SYNC (not this territory)**: `src/rvt/render/wallgeom.py`
   joins the standing plugin-bundle drift; the fix is
   `.venv/bin/python tools/sync_plugin.py`.

## Verification (how to re-run)

```
.venv/bin/python -m pytest tests/test_render_wallgeom.py -q          # 15 passed
.venv/bin/python -m rvt.render.wallgeom all                           # rebuild the probe set (~21 s)
.venv/bin/python tools/probe_batch.py check experiments/ifc_room/render/{walls_baked,walls_baked_reponly,wall_baked_min,wall_baked_min_catneg,walls_only_dummy}.rvt --manifest experiments/ifc_room/render/probes.json   # ADMISSIBLE
.venv/bin/python tools/rvt_validate.py experiments/ifc_room/render/walls_baked.rvt   # VALID, 0 errors
.venv/bin/python -m rvt.render.wallgeom audit experiments/ifc_room/render/walls_baked.rvt   # all_baked true
.venv/bin/python -m rvt.render.inspect experiments/ifc_room/render/walls_baked.rvt --class SWall   # brep/baked (sibling lens)
RVT_SEG_CACHE=<segcache> .venv/bin/python -m rvt.render.wallgeom reproduce rmebasicsampleproject 573386   # 0 diff / 0 audit (corpus)
```

## BRANCH STATE

* **status**: DONE -- READY FOR THE VIEWER QUEUE (nothing uploaded).  Item
  A (the diff) is closed at the record level: the missing thing is the
  seq-103 GElement.  The constructor emits the native grammar (four native
  walls reproduced leaf-for-leaf); both bake paths work; the probe set +
  manifest are staged in-repo and gate-admissible.
* **files (repo-relative)**: code `src/rvt/render/wallgeom.py`; tests
  `tests/test_render_wallgeom.py` (15 pass); probes
  `experiments/ifc_room/render/{CTRL_ZA_deep_render, walls_only_dummy,
  wall_baked_min, wall_baked_min_catneg, walls_baked, walls_baked_reponly,
  diag_rst_wall_baked}.rvt` + `probes.json` + `render_build.json` (the
  full per-file build/validate/read-back record); fixtures
  `experiments/ifc_room/render/fixtures/native_wall_rmebasicsampleproject_
  {573386,575873}.json`; this record.
* **gates passed (machine)**: validator VALID / 0 errors on all seven
  files; structural proof green on every write; read-back all_baked on
  every baked file (own audit + `rvt.render.inspect`); `probe_batch check`
  ADMISSIBLE (both batches); reproduction 0 diff / 0 audit on four native
  walls; stream tests 15/15.
* **NOT viewer-tested** -- no acceptance claim.  The known co-blocker
  (ZA_deep's missing Walls category rows) is instrumented, not resolved.
* **full suite** (`.venv/bin/python -m pytest tests -q --ignore=tests/
  oracle`, 17:17): **1,222 passed / 3 failed** -- the SAME three
  pre-existing cross-stream failures every prior record lists
  (`test_plugin_sync::test_plugin_is_in_sync_with_source` = the standing
  plugin-bundle drift, now also naming `src/rvt/render/*`;
  `test_provenance::test_G0_resource_refs_are_counted` and
  `::test_G0_identity_dit_usernames_still_leak` = the parallel provenance/
  genesis streams' stale G0 fixtures), NONE in this territory, ZERO new
  failures.  This stream's 15 tests + the sibling render stream's 16 run
  green together (`tests/test_render_{wallgeom,inspect}.py`, 31 passed).

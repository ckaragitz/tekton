# inbox — render-archaeology (BAKED GEOMETRY: where the viewer's geometry lives, and why our walls have none)

Stream: **render-archaeology** (2026-08-04). Charter (ORCHESTRATOR VERDICTS
#22): confirm or refute the interpretation that our files carry valid
element DEFINITIONS but no BAKED geometry, locate where and how a
Revit-saved element stores the geometry the viewer draws, diff native
walls / instances against ours, decode the native rep enough to
characterise it (B-rep? tessellation? recipe? blob?), and deliver the
answer + a geometry-carriage inspector + the exact emission prescription.

Territory touched ONLY: `src/rvt/render/` (new package: `__init__.py`,
`inspect.py`, `brep.py`), `tests/test_render_inspect.py` (new),
`docs/writer/baked-geometry.md` (new), `experiments/render/` (new: two
probe files + control + `probes.json` + `build_probes.py` + build
record), this file. **No existing `src/rvt/*.py`, `tools/*`, test or
sample was edited** (`rvt.mutate`, `rvt.objects`, `rvt.encode`,
`rvt.regadd`, `rvt.famgen.geometry`, `tools/probe_batch.py`,
`tools/rvt_validate.py` are IMPORTED, never modified). No browser /
viewer use — the two probe files are staged for the orchestrator's gate.

## Verdict in one screen

* **THE INTERPRETATION IS CONFIRMED, with byte-level evidence, and the
  location + grammar are decoded.** A Revit-saved element's drawable
  geometry is its **seq-103 record** in `Partitions/<N>`: a decoded
  `GElement` (class 0x89e) scene graph whose `Geometry` (`GBRep`) nodes
  are B-rep solids — `Face` (`EdgeLoop` + analytic `Plane` +
  `m_renderStyleId` material) + `Edge` (adjacent-face weakrefs, uv end
  points). NOT a separate stream; NOT an ElemTable/ADocument registration
  (`ElemRec` has no rep field; `ElemsSetWithCellsTracking` tracks
  material/analytical cells — wall 493612 is in none of its sets); NOT an
  opaque blob (100 % schema-decodable). **Every wall we have ever created
  carries a `SerializedDummy` (2-byte, empty) rep** — V22 (racbasic),
  V26's four (rme), H2 (rme), the four genesis-room walls — while **413/413
  native walls carry a `GElement` B-rep**. Load is not render because
  there is nothing to draw; the cloud extractor never regenerates.
* **THE GRAMMAR IS THE FAMGEN GRAMMAR — WE CAN AUTHOR IT TODAY.** A wall's
  solid and `rvt.famgen.geometry.solid_box_brep`'s six-face family solid
  share the identical class shape AND the identical flag constants
  (`GElement.GInfo 557060`, `Geometry.GInfo 573444 / m_flags 7 /
  geometryTag -1 / tessEps{0,1}`, `EdgeLoop.GInfo 524292 / open False`,
  `Face/Edge.GInfo 557572`, `faceFlags_v9 4`, `Edge.m_flags 6/7`) —
  calibrated over 69 native walls / 1,287 faces / 5,467 edges (100 % of
  wall faces are `Plane`, `cutType 0`, `orientFlag True`).
* **DELIVERED AND WORKING:** `src/rvt/render/inspect.py` (the LOAD-vs-RENDER
  inspector — per element `{class, kind, has_baked_geometry, bytes,
  solids/faces/edges/curves, storage}`, CLI + JSON) and
  `src/rvt/render/brep.py` (the reference wall-solid constructor: reads the
  box + the six face / twelve edge TAGS the wall's OWN `BaseWallGStep`
  declares off its cloned object and builds the six-face `GElement` — the
  rep is consistent with the object's own `GeomStepList` + `GeomTable` by
  construction; encodes with `rvt.encode`, re-decodes 100 % clean).
  **15/15 tests pass.**
* **TWO VIEWER PROBES STAGED, VALIDATOR-CLEAN** (`experiments/render/`,
  `probe_batch check` = ADMISSIBLE): our four room walls with authored
  solids, byte-identical to the LOAD-certified base except the four
  seq-103 records (`regadd.substitute_elements`, verdict VALID, structural
  proof green). RENDER — wall nodes appearing under the level in the model
  tree — is the gate, and it is the ONE thing this stream could not run.
* **A RETRACTION FOR KNOWLEDGE.md:** "new walls may emit SerializedDummy
  relying on regeneration" was never true of any native 3D element; and
  the V26 "VISUAL PROOF that created elements are real rendered geometry"
  was the equipment INSTANCES (referencing native rme symbols with real
  solids) — the walls in that file were dummy and drew nothing.

## Findings (evidence)

**F1 — Storage location [V, corpus-wide].** The three parallel record
streams (seq 101 header / 102 object / **103 rep**) are the whole element
data; the rep record's class is `GElement` (0x89e) for a geometric element
or `SerializedDummy` (0x0f2c, psize 2) for a non-geometric one. Worked
byte example (rst wall 493612): record header
`2c 88 07 00 00 00 00 00 | 12 f3 45 5b | 28 2a 00 00 | 9e 08` = id 493612,
stamp 0x5b45f312 (= `adler32(u16 class ‖ body)`, VERIFIED), psize 10792,
class 0x089e; object opens `1e 00 00 00 00 00 00 00` (GInfo category 30 =
the Walls projection GStyle) `2c 88 07 00` (tag 493612) `04 80 08 00`
(flags 557060) `05 00 00 00` (5 sub-nodes). Ruled out: no separate
geometry stream exists; the 40-byte `ElemRec` (class 0x05c5) = history
episodes + id + owner + partition, no rep field; the ADocument
`ElemsSetWithCellsTracking` AppInfo slot = `cellKind -> {ids}` for
`m_cellList` owners (rst: kinds −100/1200/1201 hold materials e.g. 600660
and a few analytical ids; walls in none). => geometry lives in seq 103
and only there.

**F2 — The grammar [V].** `GElement = GRep(bBox, tightbBox, elementId,
gElemType 3) <- GGroup(subNodes) <- GNode(GInfo{category, tag,
controlCommand, flags})`; drawable descendants = `Geometry` (0x8fc,
`GBRep <- GNode`: `m_pFaces` -> `Face`{`m_pFirstLoop`->`EdgeLoop`,
`m_renderStyleId` = MaterialElem, `m_cutType`, `m_faceFlags_v9`,
`m_pSurf`->`Plane`{origin, xVec, yVec ft; normal = xVec×yVec}}; `m_pEdges`
-> `Edge`{`m_pFace[2]` weak, `m_next[2]/m_prev[2]` weak,
`m_firstAndLastEdgePnts[2]{uv[2][2]}`, `m_flags` 6/7}), `GLine`/`GArc`
symbolic curves (racbasic walls, symbol elevations, under `GFilter`
view-direction `GConditionDir` gates), `GPolyMesh` (imports/topo),
`GInstance` (a placed reference to a symbol's rep). Pointer serialization
= the codec's owned/weak tokens; archive pid numbering = the disjoint
`REGISTERED_CLASSES` set famgen already reproduces.

**F3 — A native wall, fully mapped [V]** (rst 493612): `GElement(cat 30
Walls GStyle) -> 4 × GGroup(cat 24925 ref-plane subcategory) each -> a
one-face Geometry (the driven reference planes)` + `1 main Geometry`
(the body, 8 planar faces / 30 edges): sides at line ± thickness/2
(0.4593 ft; type 600634 = 0.28 m precast), bottom/top at base/top
elevations, materials 600660 ("Precast aerated concrete", the finish) on
sides/top/bottom and 24 ("Default Wall", the core) on the two end caps,
plus join faces. The wall's OBJECT (seq 102) carries the recipe:
`m_geomSteps -> GeomStepList` (`WallRefPlanesGStep` m_id 3,
`BaseWallGStep` 26, two `JoinEndGStep` 27/28, `WallJoinTweakGStep` 4,
`VerticalExtensionOfLayersGStep` 2 — each with `m_faceHistTable` /
`m_edgeHistTable` of stable ids -> history keys) and topology-only
`SnapshotData` checkpoints (face ids <-> signed edge lists, EMPTY
`m_snapshotGRep`, `m_parseForGeometry false`); `m_pGeomTable ->
GeomTable{m_table[tag].m_geomGeneratorId}` = tag -> generating-step id.
Triple cross-check: body face tags {8,9,351,352,354,356} ->
`GeomTable[.] = 26` = `BaseWallGStep` whose faceHist lists exactly those
ids; 394/406 -> 27/28 = the JoinEndGSteps; ref-plane group tags 7/6/4/1 ->
3 = `WallRefPlanesGStep`. **The recipe (seq 102) has no coordinates for
the body; the drawing (seq 103) has no history — they meet through the
tag table.**

**F4 — The face-history KEY semantics [V, against real normals].** For
`BaseWallGStep.m_faceHistTable` (u = unit line dir, n_left = (−u.y, u.x,
0)): key (1,-1,-1) = LEFT side (outward normal +n_left, offset +t/2);
(2,-1,-1) = RIGHT (−n_left); (3,0,-1) = START cap at p0 (−u); (3,1,-1) = FAR
cap at p1 (+u); (3,2,-1) = BOTTOM (−Z); (3,3,-1) = TOP (+Z) — verified by
computing each face's plane normal on wall 493612 (line +Y, `m_isFlipped`
true — flip reorders LAYERS, the box is still line ± t/2). Edge keys
[1,f,e,-1] (8) + [2,i,j,-1] (4) = 12 for a box.

**F5 — The census [V]** (`census2.py`, 5 samples, ~81,500 host elements):
SWall 413/413 brep (rst 9, rme 166, rac 60, rst-adv 6, rac-adv 172 (+8
in-place `instance-ref+geom`)); Floor/Ceiling/Roof/Duct(724)/Pipe(491)/
Conduit(20)/FlexDuct(113)/RoomElem/AnalyticalPanel/WallSweep/ShaftOpening/
StairsSupport/FormElem/ExtrusionElem/FilledRegion all brep; SiteSurface
mesh; FamilySymbol brep (89/576/112/118/163; +curves-only annotation
symbols; +dummy = never-placed / annotation symbol subset); FamilyInstance
`instance-ref` (459/5595/404/905/5441) — its dummies (38–55/file) are
EXCLUSIVELY annotation categories −2000150 (generic annotation) /
−2000280 (OST_TitleBlocks) / −2006045 (elevation-mark bodies); Level /
Grid / RefPlane / RbsElectricalSystem(187) / GStyleElem / CategoryElem /
ParamElem* / FontElem / MaterialElem / TextNote / SketchPlane / Viewport /
IndependentTag = 100 % dummy. Byte size scales with FACE COUNT
(topological complexity), not linear dimensions (81 ft plain wall = 9.4
KB / 12 faces; 37 ft wall with openings = 48 KB / 51 faces).

**F6 — Our created content, every lineage [V]** (`rvt.render.inspect`):
V22 wall 1098948 (racbasic) dummy; V26 walls 888014‥888017 (rme, the
"visual proof" file) all dummy; H2 wall 888014 (rme) dummy; room walls
1472996‥1472999 dummy; genesis room (`electrical_room_2500a.rvt`) — walls
dummy, but the 8 SYMBOLS carry real 6-face solids sized to the equipment
(the switchboard's bBox = 14.01 × 2.04 × 7.5 ft = its 4.27 × 0.62 × 2.29 m
dims; LP-4 = a 1.67 × 4.0 × 0.48 ft panel box) under an unconditional
GFilter, and the 8 INSTANCES are 300-B `GElement{GInstance}` referencing
those symbols at the intent positions (1473000's bBox centred at T1's
location) — the instance/symbol layer is drawable-by-construction; the
wall layer was the empty one. The room's cloned unjoined wall 1472525 is
a textbook box awaiting its solid: its own `BaseWallGStep` declares
EXACTLY 6 faces (tags 6/5, 18/10, 7, 14) + 12 edges, its 39-entry
`GeomTable` maps all 18 of those tags to generator 1 (`BaseWallGStep`) and
the 4 ref-plane tags to generator 3, snapshots all null, and `add_wall`
already rebuilt its 4 `m_pRefFaces` planes (sides at ±0.4593 ft, envelope
30.18 × 12.01 ft) and location line — every constructor input is present.
`add_wall`'s own note (mutate.py:560) documents the bet: "seq103 =
SerializedDummy ... Revit must regenerate ... fallback = clone-and-
transform the template wall's GElement".

**F7 — The constructor + probes [V].** `rvt.render.brep.wall_solid_brep`
= `solid_box_brep(footprint CCW, top_z, base_z)` re-tagged (box faces
1/0/2/5/9/13 = top/bottom/RIGHT/FAR/LEFT/START -> the wall's keyed tags;
box edges -> the 12 edge tags) + wall face attributes (finish material on
sides/top/bottom, core/−1 on caps, GInfo 557572, faceFlags 4) + root
`GInfo(cat, tag = id)` [+ optional 4 ref-plane single-face GGroups]. On
wall 1472525: 3,058-byte rep, `rvt.encode` -> re-decode 100 % clean, kind
brep, 6 planar faces, 12 edges, material 600660, bBox = the wall box.
Probes A (solid only, 3,060 B/wall) and B (+ ref planes, 6,260 B/wall)
built by `substitute_elements(seqs=(103,))`: verdict VALID, validator 0
errors (the 1 warning = the base's own pre-existing DataStorage 1382860
ES-blob gap, byte-identical in the base), structural proof green (0 CRC /
0 ECC / counts / id sets / stamps / ISIZE), diff = only the 4 seq-103
records; the build is deterministic (md5s reproduce). Manifest
`experiments/render/probes.json`, gate ADMISSIBLE. **A composition bug
was caught and fixed while building B:** `famgen.assign_pids` renumbers
owned pointers but leaves WEAK references untouched, so prepending the
ref-plane sub-graphics stranded the main solid's Edge->Face / loop
weakrefs. `_renumber_with_weakrefs()` (same encounter order + an old->new
weakref rewrite over disjoint per-subtree provisional bases) fixes it;
`weakref_report()` now asserts zero dangling weakrefs before emission
(A: 31 pids/90 weakrefs, B: 67/198, both 0 dangling, re-verified after an
encode->decode round trip). A's bytes were unaffected (md5 unchanged); B
was rebuilt (`a9b51712…`). A guard test pins the invariant.

## What this stream did NOT establish (honest gaps)

* **The viewer verdict on an authored wall solid** — the whole point of
  the two probes; the grammar is native-calibrated and byte-compatible with
  family solids, but no authored WALL solid has been through the oracle.
* **Whether the extractor needs the Walls-category GStyle on the root.**
  The genesis base has NO Walls GStyle (native root category 30 is absent;
  its 1,458 GStyles include 24925 = ref-plane subcategory and 124 =
  Electrical Equipment but nothing for −2000011). Probe A uses root
  category −1. "Translates but draws no wall node" would point here (=>
  the ADD-cat rung becomes a RENDER prerequisite); a rerun on an rme/rst
  base (GStyle 30 present) separates it from "rep malformed".
* **Whether the extractor honours our `GInstance` -> symbol references**
  (our instances/symbols are structurally native, F6) — an existing
  verdict-#22 probe, orthogonal to walls.
* **The exact box-edge <-> edge-history-key correspondence** (face keys
  verified, edge keys best-effort) — zero render impact (tags only serve
  face/edge references a fresh wall has none of).
* **Joined-wall reps** (join faces from `JoinEndGStep`s) — phase 2; the
  unjoined six-face wall is the certified path.

## Requests for the orchestrator

1. **VIEWER-GATE the render batch** (`experiments/render/probes.json`,
   read CTRL_render -> RSOLID_A -> RSOLID_B). PASS = wall nodes under
   `L1 - Ground Floor [311]` in the model tree (the control shows the
   level alone) + four visible walls in {3D} — screenshot it. The reading
   matrix (translates-but-no-node / processing-failed) is in the manifest.
2. **KNOWLEDGE.md merges:** (i) the storage/grammar law: *"an element's
   drawable geometry is its seq-103 GElement B-rep (GBRep faces/edges/
   loops on analytic surfaces, materials on faces); SerializedDummy is
   legitimate only for non-geometric elements (settings/styles/annotation
   records/circuits) and datum + annotation-family instances (levels/grids
   drawn from parameters; title blocks/tags from 2D family graphics); no
   native 3D model element is ever dummy (413/413 walls, all floors/roofs/
   ducts/pipes brep)"*; (ii) **RETRACT** "new walls may emit
   SerializedDummy relying on regeneration" and reinterpret the V26
   "visual proof" (it showed instances, not walls; our walls have never
   rendered); (iii) *"the wall solid grammar = the famgen six-face box
   grammar (identical constants) — rvt.render.brep authors it, tagged from
   the wall's own BaseWallGStep so no registry/GeomTable edit is needed;
   only the seq-103 record changes."*
3. **Route the `add_wall` diff to the emission/creation stream**
   (`docs/writer/baked-geometry.md` sec. 6; `mutate.py` is outside this
   territory): pass the authored `GElement` (via `rvt.render.brep`) as
   the wall's rep instead of `None`, and set `NewElement.rep_class_id` =
   0x89e for it. The same six-face constructor generalises to floors/
   ceilings (a box footprint from the sketch) once walls certify.
4. **Add `has_baked_geometry` to the job gates** (`rvt_job` /
   `probe_batch`): a created 3D element with a dummy rep should be a LOUD
   pre-upload warning ("will load but not render") — `rvt.render.inspect`
   is the check.
5. **PLUGIN SYNC (not this territory):** `src/rvt/render/{__init__,
   inspect, brep}.py` adds to the standing plugin-bundle drift
   (`tests/test_plugin_sync.py`, red at baseline for every stream); the
   fix is `.venv/bin/python tools/sync_plugin.py`.

## Verification (how to re-run)

* Inspector: `.venv/bin/python -m rvt.render.inspect <file.rvt|project>
  [--class SWall] [--id N] [--all] [--faces] [--json out]`.
* Probes: `.venv/bin/python experiments/render/build_probes.py`
  (deterministic, ~2 s, verdict VALID, md5s per the manifest) then
  `.venv/bin/python tools/probe_batch.py check experiments/render/{CTRL_
  walls_only_unjoined_render,RSOLID_walls_A_solid,RSOLID_walls_B_solid_
  refplanes}.rvt --manifest experiments/render/probes.json` -> ADMISSIBLE.
* Tests: `.venv/bin/python -m pytest tests/test_render_inspect.py -q` ->
  15 passed (classifier corpus-free; corpus law on rstbasic; our-files
  checks; constructor normals/materials/encode-round-trip).
* Full suite: `.venv/bin/python -m pytest tests -q` -> reported below.

## BRANCH STATE

* **status**: DONE — the storage location + grammar answer is delivered
  with byte-level and corpus-scale evidence; the inspector reports
  `has_baked_geometry` for the corpus and for every file of ours; the
  emission prescription is written AND made executable (constructor +
  two validator-clean, gate-admissible probe files). STOPPED AT READY —
  RENDER awaits the orchestrator's viewer gate.
* **files (repo-relative)**:
  * code: `src/rvt/render/__init__.py`, `src/rvt/render/inspect.py`,
    `src/rvt/render/brep.py`; tests `tests/test_render_inspect.py` (15
    pass).
  * docs: `docs/writer/baked-geometry.md` (the spec: layout tables,
    worked hex example, calibration, prescription, unknowns), this record.
  * probes: `experiments/render/CTRL_walls_only_unjoined_render.rvt`
    (`691eed08…`, control), `RSOLID_walls_A_solid.rvt` (`df658d2a…`,
    THE probe), `RSOLID_walls_B_solid_refplanes.rvt` (`a9b51712…`),
    `probes.json` (ADMISSIBLE), `build_probes.py`, `build_record.json`.
* **gates passed**: validator VALID / 0 errors on both probes;
  structural proof green; `probe_batch check` ADMISSIBLE; stream tests
  15/15; the constructor's rep encodes + re-decodes clean.
* **NOT viewer-tested** — no acceptance claim is made; the two probe
  files are the standing request.
* **full suite** (`.venv/bin/python -m pytest tests -q`, 17:00):
  **1,216 passed / 3 failed** — the SAME three pre-existing cross-stream
  failures every prior record lists (`test_plugin_sync::test_plugin_is_in_
  sync_with_source` = the standing plugin-bundle drift now including this
  stream's `src/rvt/render/*`; `test_provenance::test_G0_resource_refs_are_
  counted` and `::test_G0_identity_dit_usernames_still_leak` = the parallel
  provenance/genesis streams), NONE in this territory, ZERO new failures.
  That run collected an earlier 12-test version of the stream's test file;
  the final file (16 tests: + brep constructor normals/materials/round-trip
  + the weakref-composition guard) passes 16/16 separately — effective
  total 1,220 passed / 3 failed.

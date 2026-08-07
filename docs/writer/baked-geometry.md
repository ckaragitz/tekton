# Baked geometry — why our walls don't render, and the exact fix

**Stream:** render-archaeology (2026-08-04). **Owns:** `src/rvt/render/`,
`docs/writer/baked-geometry.md`, `docs/inbox/render-archaeology.md`,
`experiments/render/`. **Question posed by ORCHESTRATOR VERDICTS #22:**
*"LOAD IS NOT RENDER — the translated walls file's model tree contains
ONLY the level node; our created walls emit NO viewable geometry. WHERE
and HOW does a Revit-saved element store the geometry the viewer draws, and
DO our created elements carry it?"*

## The answer in one screen

| question | answer | confidence |
|---|---|---|
| Where is baked (viewer-drawable) geometry stored? | The element's **seq-103 record** in `Partitions/<N>` — the per-element "rep" stream that runs parallel to seq 101 (`ElementHeader`) and seq 102 (the element object). **Not** a separate geometry stream (there is none), **not** an `ElemTable` / ADocument cell registration. | **CERTAIN** — decoded, corpus-wide |
| In what form? | A **`GElement`** (class `0x089e` = `GRep <- GGroup <- GNode`) whose sub-node tree is a **B-rep**: `Geometry` (`GBRep`, class `0x08fc`) solids with `Face` (`EdgeLoop` + analytic `Surface`, e.g. `Plane` + `m_renderStyleId` material) and `Edge` (two adjacent-face weakrefs, next/prev loop links, uv end points). Same schema-directed codec as every other record; decodes 100 %. | **CERTAIN** |
| Is it the grammar `rvt.famgen` already authors? | **YES — byte-compatible.** The wall solid and `rvt.famgen.geometry.solid_box_brep`'s family solid share the identical class shape and the identical flag constants (`GElement.GInfo 557060`, `Geometry.GInfo 573444` / `m_flags 7`, `EdgeLoop.GInfo 524292`, `Face`/`Edge.GInfo 557572`, `faceFlags_v9 4`, `Edge.m_flags 6/7`). **We can author it today.** | **CERTAIN** — 69 walls / 1,287 faces / 5,467 edges calibrated |
| Do OUR created walls carry it? | **NO.** Every wall we have ever created — V22 (racbasic), V26's four (rme), H2 (rme), the four genesis-base room walls — carries a **`SerializedDummy`** rep (psize 2, zero object bytes). That is the entire reason they never rendered. | **CERTAIN** — inspected every file |
| Did our earlier sample-base V-walls ever render? | **No.** They never carried geometry. V22's certification ("wall creation, SerializedDummy regen") proved LOAD tolerance, not visibility. V26's viewer "detached cluster" = the equipment INSTANCES (referencing native rme symbols that carry real solids), not the walls. | **CERTAIN** |
| The fix | Give the wall a `GElement` rep = one six-face box `Geometry` (2 sides, 2 end caps, top, bottom; 12 edges) aligned to its location line, tagged with the tags its own `BaseWallGStep` already declares. Implemented: `rvt.render.brep.wall_solid_brep`; two probe files staged (`experiments/render/`), validator VALID, awaiting the viewer. | **HIGH** on grammar; **the viewer verdict is the open gate** |

Two corpus laws fell out of the census (5 samples, ~81,500 host elements),
both usable as validator invariants:

1. **A 3D model element's rep is never `SerializedDummy`.** 413/413 native
   walls, every floor / ceiling / roof / duct (724) / pipe (491) / conduit
   / room / sweep / form / stairs support carries a `GElement` B-rep.
2. **`SerializedDummy` is legitimate for exactly two families:** the
   non-geometric records (settings, styles, params, fonts, materials,
   annotation records, circuits — `RbsElectricalSystem` 187/187, view
   records) and **datum + annotation-family instances** — levels, grids,
   ref planes (drawn from PARAMETERS) and title blocks / tags / elevation
   marks (drawn from 2D family graphics). This is why our created LEVEL
   appears in the viewer tree while our walls do not: a level is *supposed*
   to have a dummy rep; a wall is not.

---

## 1. Storage location — the three seq streams, and the third one is the drawing

Every element is (up to) three parallel records in `Partitions/<N>`
(`docs/streams/`, KNOWLEDGE.md §Partitions), keyed by the same ElementId:

| seq | class | role | our created wall |
|---:|---|---|---|
| 101 | `ElementHeader` (0x5e5) | dependency graph, category, bbox, flags | present (ours) |
| 102 | the polymorphic element object (`SWall` 0xf02, ...) | ALL parametric state: params, location line, ref faces, the geometry-step *recipe* | present (ours) |
| **103** | **`GElement` (0x89e) or `SerializedDummy` (0xf2c)** | **the baked, drawable representation** | **`SerializedDummy` — nothing to draw** |

Record framing (uniform, KNOWLEDGE.md, byte-verified): `i64 id, u32 stamp,
u32 psize, {u16 class_id, object[psize-2]}, u32 psize`, with
`stamp = adler32(u16 class ‖ object bytes)`.

**Worked example — native wall 493612 (rstbasic), its seq-103 record:**

```
header:  2c 88 07 00 00 00 00 00 | 12 f3 45 5b | 28 2a 00 00 | 9e 08
         i64 id = 493612          u32 stamp     u32 psize     u16 class
                                  0x5b45f312    = 10792      = 0x089e GElement
stamp:   adler32(u16 0x089e ‖ 10,790 object bytes) = 0x5b45f312   VERIFIED (MATCH)
object:  1e 00 00 00 00 00 00 00   GElement.m_GInfo.m_categoryId = 30 (the Walls
                                   projection GStyleElem, category -2000011)
         2c 88 07 00               m_tag = 493612 (== the element id)
         00 00 00 00               m_controlCommand = 0
         04 80 08 00               m_flags = 0x88004 = 557060 (GELEM_ROOT_FLAGS)
         05 00 00 00               m_subNodes count = 5
         03 00 00 00 a0 08 ...     pointer token: pid 3, class 0x08a0 GGroup
```

The same wall's seq-102 `SWall` object (8,915 B) and seq-101 header (295 B)
carry NO drawable coordinates for the body — see §3. And the same
element's seq-103 record in OUR files:

```
V22 wall 1098948 (racbasic):        seq-103 = SerializedDummy, psize 2
V26 walls 888014..888017 (rme):     seq-103 = SerializedDummy, psize 2
H2 wall 888014 (rme):               seq-103 = SerializedDummy, psize 2
room walls 1472996..1472999:        seq-103 = SerializedDummy, psize 2
```

**Ruled out — the other candidate locations:**

* *A separate geometry stream.* There is none. The three seqs are the whole
  element-data content of `Partitions/<N>`; `Global/*` are the ADocument
  (settings/registries), ElemTable, history and increment tables (§KNOWLEDGE
  Container). Wall size scales the seq-103 record and nothing else (§4).
* *An `ElemTable` registration.* The 40-byte `ElemRec` (class 0x05c5) =
  `{history: originalId, creation/lastMod/userMod episodes; m_id; m_owner;
  m_partitionId}` — **no rep-kind or geometry field** (`src/rvt/elemtable.py`).
* *An ADocument cell registry — `ElemsSetWithCellsTracking`.* That AppInfo
  slot is a `cellKind -> {element ids}` map (schema
  `m_elemIdSetMap: vector<pair<int, TrackingIdSet>>`) tracking elements that
  own `m_cellList` **cells** — in rstbasic its three kinds (−100 / 1200 /
  1201) hold materials/appearance ids (e.g. material 600660) and a few
  analytical ids; **wall 493612 is in NO cell-kind set.** It registers
  cell ownership, not geometry.

## 2. The grammar — a decoded scene graph, not a blob

`GElement` (0x89e) inherits `GRep <- GGroup <- GNode`. Class fields
(`rvt.schema`, per-release constant `Formats/Latest`):

| class (id) | fields | meaning |
|---|---|---|
| `GNode` 0x577 | `m_GInfo{ m_categoryId, m_tag, m_controlCommand, m_flags }` | every graphics node's header: **category** = a `GStyleElem` id; **tag** = the stable geometry TAG (root: the element id) |
| `GGroup` 0x8a0 | `m_subNodes vector<ptr>` | grouping node (also `GFilter` 0x8a6 = group + `m_oConditions` view-direction visibility gates) |
| `GRep` 0x89f | `m_bBox, m_tightbBox` (`array<double[3]>[2]`, feet), `m_elementId` (i64), `m_gElemType` (3 = geometry element), `m_flags` | the representation root |
| `GElement` 0x89e | (adds nothing) | the concrete rep class stored in seq 103 |
| `Geometry` 0x8fc (`GBRep 0x881 <- GNode`) | `GBRep.m_pFaces vector<ptr Face>`, `m_flags` (=7), `m_geometryTag` (−1), `m_tessEpsCntrl{type 0, version 1}`, `m_pEdges vector<ptr Edge>`, `m_sharedSurfInfo` | **THE B-REP SOLID** |
| `Face` 0x6ef (`GFace 0x6f0 <- GNode`) | `m_pFirstLoop -> EdgeLoop`, `m_faceRegions`, `m_pGFilling`, `m_oBackgroundFilling`, `m_renderStyleId` (= a **MaterialElem** id: the face's material), `m_cutType`, `m_faceFlags_v9`, `m_pSurf -> Surface` | one bounded face |
| `EdgeLoop` 0x57f (`GEdgeLoop <- GEdgeBase <- GNode`) | `m_nextLoop`, `m_pFace` (weak), `m_next` / `m_prev` (weak: first/last edge), `m_Envelope{ m_corners uv[2] }`, `m_open` | the face's boundary loop, uv envelope in the face's own parameter space |
| `Edge` 0x574 | `m_pFace[2]` (weak: the 2 adjacent faces), `m_next[2]` / `m_prev[2]` (weak: loop links per face), `m_interiorEdgePnts`, `m_firstAndLastEdgePnts[2]{ uv[2][2] }` (each end point's uv in BOTH adjacent faces), `m_flags` (6 forward / 7 reversed) | a shared edge |
| `Plane` 0x265 (`Surface 0x266`) | `m_Envelope`, `m_orientFlag`, `m_origin`, `m_xVec`, `m_yVec` (feet; normal = xVec × yVec) | the analytic surface (100 % of wall faces are planar) |
| `GLine` 0x78b / `GArc` 0x87d (`GCurve`) | origin/dirVec/endParams; centre/radius/xVec/yVec | symbolic 2D curves (plan/section reps of racbasic walls, symbol elevations) |
| `GInstance` 0x87f | `m_instanceInfo`, `m_oEmbeddedSymbolGRep`, `m_tagId`, ... | a placed **reference** to a symbol's rep (§5) |

Pointer serialization is the codec's owned-pointer token (`i32 pid` + `u16
class` + body deferred breadth-first; weakrefs = `u32 pid`); the archive
numbers `GElement`/`Geometry`/`Face`/`Edge`/`EdgeLoop`/`Plane` instances
(`rvt.famgen.geometry.REGISTERED_CLASSES`, `assign_pids` — the numbering
`solid_box_brep` reproduces and self-checks).

**A native wall's rep, decoded (rstbasic 493612, 8,917 B; and the corpus
shape over 69 walls):**

```
GElement    cat=30 (Walls GStyle) tag=493612 flags=557060 bBox=[..] gElemType=3
 ├─ GGroup  cat=24925 (ref-plane subcategory GStyle) tag=7   ─ Geometry: 1 Face (Plane) + 4 Edges
 ├─ GGroup  cat=24925 tag=6                                   ─ Geometry: 1 Face + 4 Edges
 ├─ GGroup  cat=24925 tag=4                                   ─ Geometry: 1 Face + 4 Edges
 ├─ GGroup  cat=24925 tag=1                                   ─ Geometry: 1 Face + 4 Edges
 └─ Geometry cat=-1 flags=573444  ── THE SOLID: 8 Faces (all Plane), 30 Edges
       face tag  8  x=-37.2312 normal +X  material 600660  (RIGHT side)
       face tag  9  x=-38.1498 normal -X  material 600660  (LEFT side)
       face tag 351 z=-8.858   normal -Z  material 600660  (bottom)
       face tag 354 z=+6.562   normal +Z  material 600660  (top)
       face tag 356 y=-10.963  normal -Y  material 24      (start cap)
       face tag 352 y=+20.625  normal +Y  material 24      (far cap)
       face tag 394, 406       join-end faces (from JoinEndGSteps)
```

The four single-face `GGroup`s are the wall's driven **reference planes**
(interior/exterior/centre — subcategory GStyle 24925), graphics-only. The
main `Geometry` is the drawable body: `600660` = MaterialElem "Precast
aerated concrete" (the type's finish; sides + top + bottom), `24` =
MaterialElem "Default Wall" (the core; the two end caps). A joined wall
has 7–8+ faces (the box + join faces); an **unjoined** wall's body is
**exactly six faces / twelve edges** (§6). racbasic walls additionally carry
`GLine` symbolic curves under `GFilter` nodes (plan/cut linework) — the
viewer draws the solid.

## 3. The recipe lives in seq 102; the drawing lives in seq 103

The element OBJECT (seq 102) carries the parametric machinery, not the
drawing. `Element` (0x25, the universal base) has:

* `m_geomSteps -> GeomStepList` — the **regeneration recipe**: six step
  lists (`m_nonBRepGList` … `m_bRepTweakGList`) of `GeomStep` objects
  (`WallRefPlanesGStep`, `BaseWallGStep`, `JoinEndGStep`,
  `WallJoinTweakGStep`, `VerticalExtensionOfLayersGStep`, …), each with
  `m_faceHistTable` / `m_edgeHistTable` / `m_curveHistTableSet` mapping
  **stable ids** (`m_id`) to history **keys** (`FaceHist.m_keys int[3]`,
  `EdgeHist.m_keys int[4]`); plus four `m_bRep*Snapshot -> SnapshotData`
  = **topology-only** checkpoints (`GeometryTopology`: face ids ↔ signed
  edge-id lists; an EMPTY `m_snapshotGRep`; `m_parseForGeometry false`) —
  **no coordinates**.
* `m_pGeomTable -> GeomTable{ m_table vector<GeomTabEntry{ m_geomGeneratorId }> }`
  — the **tag table**: `m_table[tag] = m_id` of the `GeomStep` that
  generated the geometry piece carrying that tag. This is the bridge from
  a rep node's `m_GInfo.m_tag` back to its generating step.

Cross-verified three ways on wall 493612: the body faces' tags
(8, 9, 351, 352, 354, 356) → `GeomTable[tag].m_geomGeneratorId = 26` =
`BaseWallGStep(m_id 26)`, whose `m_faceHistTable` lists exactly those
ids; tags 394/406 → generators 27/28 = the two `JoinEndGStep`s; the
ref-plane `GGroup` tags 7/6/4/1 → generator 3 = `WallRefPlanesGStep`.

`VWall` also carries `m_pRefFaces vector<Face>` — the driven reference
face **planes** live on the object too (and `rvt.mutate.add_wall` already
rebuilds them correctly for a new line/height). Everything a body needs —
location line (`m_pCurveDriver -> VWallDriver.m_pCrv = GLine`), per-layer
face offsets (from the type's compound structure), thickness, base
elevation, height — is computed by `add_wall` today. Only the seq-103
record was left dummy, by a documented bet:

```python
# src/rvt/mutate.py:560-565 (add_wall)
notes=["seq103 = SerializedDummy (no cached geometry): Revit must "
       "regenerate the wall solid from m_geomSteps [acceptance test T1]; "
       "fallback = clone-and-transform the template wall's GElement.", ...]
```

Desktop Revit regenerates on open; **Autodesk's cloud extractor
(RevitExtractor / the viewer) does not** — it draws baked geometry only.
The bet lost; the named fallback is the fix.

## 4. What grows with wall size (the census)

`SWall` in rstbasic (9) + racbasic (60), seq-103 byte size vs geometry:

| wall | bytes | faces | solids | curves | header dims (ft) |
|---|---:|---:|---:|---:|---|
| 493879 | 8,719 | 11 | 5 | 0 | 26.4 × 0.9 × 15.4 |
| 627064 | 9,364 | 12 | 5 | 0 | **81.0** × 0.9 × 3.9 |
| 628523 | 11,030 | 12 | 5 | 0 | 72.1 × 0.9 × 3.9 |
| 428745 (rac) | 66,959 | **50** | 12 | 0 | 64.6 × 0.7 × 12.5 |
| 430064 (rac) | 48,295 | **51** | 5 | 0 | 37.3 × 0.4 × 14.7 |
| 428797 (rac) | 25,073 | 34 | 6 | **52** | 3.3 × 20.4 × 19.4 |

**Size scales with topological complexity (face count = openings, joins,
sweeps, layers), not with linear dimensions** — an 81 ft plain wall is
9.4 KB / 12 faces while a 37 ft wall with hosted openings is 48 KB / 51
faces. Dimensions cost nothing extra: they are the `Plane` origins / uv
envelopes (a fixed number of doubles per face). A six-face body is ~3 KB.

Corpus-wide rep kinds (`rvt.render.inspect`, host-document elements):

| class | rst | rme | rac | rst-adv | rac-adv | kind |
|---|---:|---:|---:|---:|---:|---|
| SWall | 9 | 166 | 60 | 6 | 172 (+8 in-place) | **100 % brep** |
| Floor / Ceiling / Roof* | 5 | 21+43 | 9+2 | 5 | 16+65 | brep |
| RbsDuctCurve / RbsPipeCurve / RbsConduitCurve | – | 724 / 491 / 20 | – | – | – | brep |
| FamilySymbol | 89 | 576 | 112 | 118 | 163 | brep (+ curves-only annotation symbols) |
| FamilyInstance | 459 ref | 5,595 ref | 404 ref | 905 ref | 5,441 ref | **instance-ref** (dummy only for annotation categories −2000150 / −2000280 title blocks / −2006045 elevation marks) |
| Level / Grid / RefPlane | 9/16/21 | 4/22/12 | 7/14/56 | 5/27/4 | 6/22/13 | **100 % dummy** (datum from parameters) |
| RbsElectricalSystem | – | 187 | – | – | – | 100 % dummy (circuits: no geometry) |
| GStyleElem / CategoryElem / ParamElem* / FontElem / MaterialElem / TextNote / SketchPlane / Viewport … | thousands | | | | | 100 % dummy (settings / styles / annotation records) |

(*) plus WallSweep, ShaftOpening, StairsSupport, FormElem, ExtrusionElem,
SysMullionFamSym / SysPanelFamSym, RoomElem, AnalyticalPanel, FilledRegion,
SiteSurface (mesh) — every geometric class carries geometry.

## 5. The instance path — geometry by reference (our instances are correct)

A model `FamilyInstance`'s rep is a *reference*, not a copy:

```
native rme instance 742670 (a 400 A panel), 638 B:
GElement cat=124 tag=742670
 ├─ GGroup ─ GPoint ×5             (the connector points)
 └─ GInstance{ m_instanceInfo -> InstanceInfo, m_oEmbeddedSymbolGRep = null }
```

The `GInstance` draws the **symbol's** rep transformed by the instance
info; the geometry lives on the `FamilySymbol` (native 619617, 5,402 B: a
6-face `Geometry` solid + 12 `GLine` elevations under `GFilter`
`GConditionDir` view gates; the solid sits under an EMPTY-condition
filter = unconditionally visible). Host-cut doors/windows additionally
embed a per-host `m_oEmbeddedSymbolGRep` clone (`instance-ref+geom`).

**Our created content already conforms:** in `electrical_room_2500a.rvt`
our 8 instances (300 B each) are `GElement{ GInstance }` referencing our 8
loaded symbols, and **our symbols carry real, correctly-sized six-face
solids** (the switchboard symbol's bBox is 14.01 × 2.04 × 7.5 ft = its
4.27 × 0.62 × 2.29 m dims; LP-4's is a 1.67 × 4.0 × 0.48 ft panel box) under
an unconditional `GFilter`, structurally equivalent to native symbol reps.
=> **the instance/symbol layer is drawable by construction; the wall layer
is the one that was empty.** Whether the extractor honours our `GInstance`
references is an existing open probe (verdict #22 next-steps), separable
from the wall question and not caused by missing bytes on our side.

## 6. The prescription — what to write, in what grammar, registered how

**For a straight wall (`Document.add_wall`): emit a `GElement` seq-103 rep
instead of `None`.** Implemented as the reference constructor
`src/rvt/render/brep.py` (`wall_rep_from_object` / `wall_solid_brep`),
which reuses the proven six-face box `rvt.famgen.geometry.solid_box_brep`
and re-tags / re-materials it to the wall.

```
GElement  m_GInfo{ cat = walls_gstyle_id | -1, tag = element_id, flags 557060 }
          m_bBox / m_tightbBox = the box (feet); m_elementId = id; m_gElemType 3; m_flags 0
 └─ Geometry  m_GInfo{ cat -1, tag -1, flags 573444 }, m_flags 7, m_geometryTag -1,
              m_tessEpsCntrl{0,1}, m_sharedSurfInfo []
    m_pFaces = 6 × Face  (Plane surfaces; loop uv envelope = the face rectangle;
              m_faceFlags_v9 4; m_cutType 0; GInfo.flags 557572)
       LEFT   key(1,-1,-1)  plane at line + n_left*off_left , normal +n_left  material = finish | -1
       RIGHT  key(2,-1,-1)  plane at line + n_left*off_right, normal -n_left  material = finish | -1
       START  key(3,0,-1)   plane at p0, normal -u                               material = core   | -1
       FAR    key(3,1,-1)   plane at p1, normal +u                               material = core   | -1
       BOTTOM key(3,2,-1)   z = base_z, normal -Z                               material = finish | -1
       TOP    key(3,3,-1)   z = base_z + height, normal +Z                      material = finish | -1
    m_pEdges = 12 × Edge (GInfo.flags 557572; m_flags 6/7; two adjacent-face weakrefs;
              next/prev loop links per face; both end points' uv in both faces)
 [+ optional 4 × GGroup(cat = ref-plane GStyle) ─ Geometry(1 Face + 4 Edges)  — native shape]
```

The face-key ↔ face semantics above are **verified against a native
wall's actual face normals and positions** (§2 table; `u` = unit line
direction, `n_left = (-u.y, u.x, 0)`; `m_isFlipped` reorders compound
LAYERS, not the box). `add_wall` already computes p0/p1, `n_left`, the
side offsets `off_left/off_right` (= its `told["faces"]` offsets),
`base_z` and `height`.

**Registration = tag consistency, and it comes for free.** The rep's face
and edge TAGS must be tags the element's `m_pGeomTable` maps to a real
generating step. Our cloned walls already carry the specimen's
`GeomStepList` and `GeomTable`; `tags_from_wall_object()` reads the six
face tags and twelve edge tags the wall's OWN `BaseWallGStep` declares
(keys as above) and the constructor reuses them — verified on our unjoined
room wall 1472525: its `BaseWallGStep(m_id 1)` declares exactly 6 faces
(tags 6/5 sides, 18/10 caps, 7 bottom, 14 top) + 12 edges, its 39-entry
`GeomTable` maps every one of those 18 tags to generator 1 (`BaseWallGStep`)
and the 4 ref-plane tags to generator 3 (`WallRefPlanesGStep`). The
authored rep is therefore **consistent with the object's own history and
tag table by construction** — no new tag allocation, no `GeomTable` edit,
no ElemTable edit, no ADocument edit. **Only the seq-103 record changes.**

Materials: `Face.m_renderStyleId` = a **MaterialElem** id (native: finish
on sides/top/bottom, "Default Wall" core on the caps); use the wall type's
material if the base carries it, else `-1` (default appearance — the
convention on native symbol faces). Root category: a native root's
`m_categoryId` = the element's category **projection GStyleElem** (Walls =
element 30, `m_categoryId -2000011`, `m_gstyleType 1`); use it if present,
else `-1`.

**Emission-stream diff for `src/rvt/mutate.py::add_wall`** (NOT applied —
`mutate.py` is outside this territory; ~10 lines):

```diff
+from .render.brep import (WallGeometry, WallTags, tags_from_wall_object,
+                          wall_solid_brep, CLASS_GELEMENT)
@@ def add_wall(...):
-        el = NewElement(eid, "wall", "SWall", CLASS_SWALL, header, obj, None,
+        # baked rep (docs/writer/baked-geometry.md): the six-face box the
+        # wall's own BaseWallGStep declares, in the native seq-103 grammar.
+        offs = [m["offset"] for m in told["faces"] if m]
+        geom = WallGeometry(p0=[x0, y0, base_z], p1=[x1, y1, base_z],
+                            base_z=base_z, height=wall_h,
+                            off_left=max(offs), off_right=min(offs))
+        rep = wall_solid_brep(geom, tags_from_wall_object(obj), element_id=eid,
+                              root_category_id=self._walls_gstyle_or(-1),
+                              side_material_id=self._wall_finish_material(wall_type_id),
+                              end_material_id=-1)
+        el = NewElement(eid, "wall", "SWall", CLASS_SWALL, header, obj, rep,
                         self._new_elemrec(eid), tpl,
-                        notes=["seq103 = SerializedDummy (no cached geometry): Revit must "
-                               "regenerate the wall solid from m_geomSteps [acceptance test T1]; "
-                               "fallback = clone-and-transform the template wall's GElement.",
+                        notes=["seq103 = authored 6-face GElement B-rep "
+                               "(rvt.render.brep) -- the cloud extractor draws baked geometry only",
                                f"cloned from wall {tpl} ..."])
```

`NewElement.rep_class_id` for a `GElement` rep = 0x89e (the class the
commit layer must frame); `rvt.regadd.framed_records_from` accepts
`{103: (0x89e, rep_dict)}` and stamps it correctly (probe files below were
built exactly this way).

## 7. The probes staged for the viewer (RENDER gate, not LOAD)

`experiments/render/` — `probe_batch check`: **ADMISSIBLE**, base =
`experiments/ifc_room/electrical_room_2500a_walls_only_unjoined.rvt` (the
LOAD-certified file whose model tree showed ONLY the level). Both probes
are byte-identical to that base **except the four walls' seq-103 records**
(`regadd.substitute_elements(seqs=(103,))`: verdict VALID, validator 0
errors, structural proof green — 0 CRC / 0 ECC mismatches, counts / id
sets / stamps / ISIZE ok; diff = only ids 1472525‥1472528 seq 103;
`Global/Latest` + `ElemTable` byte-identical).

| probe | file | md5 | change per wall | reads |
|---|---|---|---|---|
| CTRL_render | `CTRL_walls_only_unjoined_render.rvt` | `691eed08…` | none (byte-identical control) | round validity; tree = level only |
| **RSOLID_A** | `RSOLID_walls_A_solid.rvt` | `df658d2a…` | dummy (2 B) → **one 6-face `Geometry`** (3,060 B; sides+top+bottom material 600660, caps −1, root cat −1, no ref planes) | **the primary question:** does an authored wall B-rep render? |
| RSOLID_B | `RSOLID_walls_B_solid_refplanes.rvt` | `a9b51712…` | as A **plus** the 4 ref-plane sub-graphics (GGroup cat 24925; 6,260 B, 5 solids) — the FULL native rep shape | discriminates "ref planes needed?" |

**PASS criterion is the model tree, not translation:** wall nodes must
appear under `L1 - Ground Floor [311]`; the base (control) shows the level
node alone. Reading matrix in `experiments/render/probes.json`.

**A composition rule learned while building B** (worth a KNOWLEDGE.md
line): `rvt.famgen.geometry.assign_pids` renumbers owned pointers but
**leaves weak references untouched** — correct for a lone `solid_box_brep`
box (its weakrefs were computed against its own base-3 numbering), WRONG
the moment G-node subtrees are composed (prepending the four ref-plane
`GGroup`s shifts the main solid's pids while its `Edge -> Face` and loop
weakrefs still name the old ones). `rvt.render.brep._renumber_with_weakrefs`
numbers in the same encounter order and rewrites every `weakref` through
the old→new map (each subtree is built on a disjoint provisional base —
box at 3, ref planes at 200/210/… — so the map is unambiguous; 0/1/2 =
null/document/root preserved). `weakref_report()` asserts zero dangling
weakrefs before emission (A: 31 pids / 90 weakrefs; B: 67 / 198; both 0
dangling, re-verified after an encode→decode round trip). Variant A's
bytes were unaffected (its numbering never moved); B was rebuilt.

## 8. Unknowns (explicit)

1. **The viewer verdict on RSOLID_A/B** — the grammar is calibrated to 69
   native walls and byte-compatible with certified family solids, but no
   authored *wall* solid has been through the oracle. This is the gate.
2. **Root category on the genesis base.** The base carries **no Walls
   category GStyle** (native root category = element 30, absent from the
   ZA_deep lineage; only 24925 = the ref-plane subcategory and 124 =
   Electrical Equipment exist among its 1,458 GStyles). RSOLID_A therefore
   uses root category −1. If A translates but no wall node is drawn, the
   missing Walls GStyle (the ADD-cat rung) becomes a RENDER prerequisite —
   rerun the probe on an rme/rst-based file (GStyle 30 present) to
   separate "needs the GStyle" from "rep malformed".
3. **Exact box-edge ↔ edge-history-key correspondence.** The 12 wall
   edge tags are reused from the `BaseWallGStep` edge history but their
   1:1 assignment to the box's 12 edges is best-effort (the face keys are
   VERIFIED, the edge keys inferred). Tags affect only face/edge
   references (dimensions, paint, joins), of which a fresh wall has none —
   **zero render impact**; a desktop-Revit re-save would re-tag anyway.
4. **`GInstance` honouring by the extractor** (do our correctly-formed
   instance→symbol reps draw?) — an existing verdict-#22 probe, orthogonal
   to walls; our symbol/instance bytes are structurally equivalent to
   native (§5).
5. **Face `GInfo.m_flags` variety.** Natives use several values (557572
   dominant; 33284, 67665920, 558596, …) whose bit semantics are undecoded;
   we use the dominant / famgen-proven constants. Low risk (family solids
   with these constants validate; unknown for the viewer).
6. **Joined walls.** A joined wall's body adds `JoinEndGStep` faces
   (7–8+ faces) with `SnapshotData` topology. The certified path is
   UNJOINED walls (six faces); joined-wall reps are phase 2 (author the
   join faces or keep walls unjoined — the room's `_unjoined` variant is the
   right base).

## 9. Reproduce

```
# inspect any file / corpus project (the LOAD-vs-RENDER lens)
.venv/bin/python -m rvt.render.inspect rstbasicsampleproject --class SWall --faces
.venv/bin/python -m rvt.render.inspect experiments/ifc_room/electrical_room_2500a.rvt \
    --id 1472996 --id 1473000 --id 1472586
# rebuild the two render probes (writes experiments/render/, verdict VALID)
.venv/bin/python <scratch>/build_probes.py          # driver reproduced in the inbox record
.venv/bin/python tools/probe_batch.py check experiments/render/*.rvt \
    --manifest experiments/render/probes.json         # ADMISSIBLE
.venv/bin/python -m pytest tests/test_render_inspect.py -q   # 15 passed
```

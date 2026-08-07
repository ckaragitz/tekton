# Claude Design ground truth — how the user's models & IFC are made today

Source: the user's Claude Design project **"Chicago plenum recessed light"**
(project id `f07f3020-fff9-4ed4-92a5-c2caf8907fe4`), read directly by the
orchestrator (subagents cannot reach Design). A real exported sample lives
at `samples/design-ifc/bs-area-e-electrical-room.ifc` (84 KB) — the project
"DDOT Coolidge – Area E bus storage electrical room". This document is the
authoritative brief for building the `revit-bridge` skill and its canonical
exporter. Do NOT contradict it without evidence.

## 1. Who / what

The end users are the user's brothers: **electrical / MEP contractors-
engineers on transit & institutional facilities** (DC bus garages etc.).
Deliverables in Design: 3D models, one-line diagrams, panel schedules,
BOMs, shop drawings, submittal packages, renderings — and **IFC exports**
they then bring into **Autodesk Revit**. They are non-developers. They
have a work Autodesk account (Revit; APS possible subject to IT policy).
`[open]` The exact Revit version they run is unconfirmed (target ceiling).

## 2. The existing authoring stack (comes from a Design "3D object" skill)

- Pages are HTML with a pinned three.js **import map** (three@0.184.0
  from unpkg, with SRI integrity hashes) — this exact map is mandated by
  Design's existing "3D object" skill. Keep it verbatim; do not change
  versions casually.
- `<three-d-stage>` (`three-d-stage.js`) is a starter web component: a
  three.js viewer (studio lights, orbit controls, ground shadow, auto-frame)
  with a download toolbar: **OBJ+MTL, GLB, and IFC**. Usage:
  `const {THREE} = await stage.ready;` build a model as a `THREE.Group`
  of named meshes/materials; `stage.setObject(model)`;
  `stage.ifcMeta = {...}` supplies whole-object IFC metadata. Convention:
  **real-world metres, y-up, origin at a meaningful anchor** (panelboard =
  bottom-center of enclosure back).
- IFC export: the stage's `_exportIfc()` does
  `const mod = await import('./ifc-export.js')` and calls
  **`mod.toIfc(THREE, object, meta)`** → text → download `<name>.ifc`.
  Therefore the canonical exporter MUST keep exactly this module path
  (`./ifc-export.js`) and export signature `toIfc(THREE, object, meta)` to
  be a zero-change drop-in. Any project already has the stage; only
  `ifc-export.js` needs upgrading.

## 3. The model-tagging contract (v1, in use — must remain 100% supported)

Any `THREE.Group`/`Object3D` carrying `userData.ifc` becomes ONE IFC
product; all its descendant meshes' geometry is merged into that product.
If no node is tagged, the whole object is one product described by `meta`.

`userData.ifc = { ifcClass, predefinedType, name, description, tag, psets,
typeName, typePsets }` where:
- `ifcClass` e.g. `IFCELECTRICDISTRIBUTIONBOARD` (default fallback:
  `IFCBUILDINGELEMENTPROXY`); `predefinedType` e.g. `DISTRIBUTIONBOARD`
  (default `NOTDEFINED`).
- `psets: [{ name, props: { PropName: {value, type} | scalar } }]` —
  typed measure `type` ∈ boolean | integer | count | real | voltage |
  current | power | length | identifier | text | label(default). Emitted as
  `IfcPropertySet`/`IfcPropertySingleValue` with `IfcElectricVoltageMeasure`,
  `IfcElectricCurrentMeasure`, `IfcPowerMeasure`, `IfcLengthMeasure`,
  `IfcCountMeasure`, `IfcInteger`, `IfcBoolean`, `IfcIdentifier`,
  `IfcText`, `IfcLabel`.
- `typeName` (+ `typePsets`) → an `IfcXxxType` linked via
  `IfcRelDefinesByType` (v1 BUG: one type object PER element even when
  typeName is identical).
- `meta` (whole-object / defaults): `{name, projectName, fileName,
  description, tag, ifcClass, predefinedType, psets, typeName, typePsets}`.

Reference implementation of a tagged assembly: `panel-meta.js` builds the
panelboard product meta: ifcClass `IFCELECTRICDISTRIBUTIONBOARD`,
predefinedType `DISTRIBUTIONBOARD`, typeName like
`"Eaton Pow-R-Line 4 (style) - 400A MB - 42 space"`, psets
`PanelSchedule` (PanelName, DoorPosition, DoorSwingRadius[length],
WorkingClearanceShown[boolean], WorkingClearanceDepth/Width/Height[length],
Voltage[voltage], Phases[integer], Wires[integer], BusRating[current],
MainsType[label], MainsRating[current], ShortCircuitRatingkA[real],
Mounting[label], NumberOfCircuits[count], NeutralRating[label]) and
`Pset_ElectricDistributionBoardTypeCommon` (Reference, IsMain,
NumberOfCircuits); typePsets `Pset_ManufacturerTypeInformation`
(Manufacturer, ModelLabel, ModelReference).

A **Revit shared-parameters file** already exists in the project
(`exports/panelboard-shared-parameters.txt`) defining group "Panelboard"
with PanelName(TEXT), Voltage(ELECTRICAL_POTENTIAL), Phases(INTEGER),
Wires(INTEGER), BusRating(ELECTRICAL_CURRENT), MainsType(TEXT),
MainsRating(ELECTRICAL_CURRENT), ShortCircuitRatingkA(NUMBER),
Mounting(TEXT), NumberOfCircuits(INTEGER), NeutralRating(TEXT) — i.e. the
psets are DESIGNED to land as Revit shared parameters. This is the bridge
from IFC psets → real Revit parameters and the skill must document how to
apply it (Revit's IFC import parameter-mapping / shared-parameter file).

## 4. How geometry is actually built (drives extrusion recovery)

Models are procedural three.js: `THREE.BoxGeometry(w,h,d)`,
`THREE.CylinderGeometry(rt,rb,h,seg)`, `THREE.TorusGeometry`,
`THREE.CircleGeometry`, `THREE.ExtrudeGeometry(shape,{depth,bevelEnabled:
false})` where `shape` is a real `THREE.Shape` **with `.holes`** (e.g. the
dead-front panel with rectangular breaker cutouts, the front trim with the
door opening). Meshes get `.position`/`.rotation` set on the Object3D
(good — recoverable transform), BUT two patterns BAKE transforms into
vertices and destroy parametric info: (a) geometry methods like
`.rotateX(Math.PI/2)` / `.translate(...)` applied to the geometry, and
(b) a `merge([...])` helper that clones + `applyMatrix4` several geometries
into one anonymous `BufferGeometry` (used for screws, hinges, knockouts,
breaker arrays). RULE for the exporter: emit parametric solids ONLY for
meshes whose `geometry.type` is a known primitive (`BoxGeometry`,
`CylinderGeometry`, `ExtrudeGeometry`) AND whose `geometry.parameters` are
intact; everything else (merged/baked/anonymous `BufferGeometry`) falls
back to tessellation. `geometry.parameters` exists on primitives:
Box{width,height,depth}, Cylinder{radiusTop,radiusBottom,height,...},
Extrude{shapes, options{depth,...}} — Extrude shapes retain their curves
and holes, mapping to `IfcArbitraryClosedProfileDef` /
`IfcArbitraryProfileDefWithVoids` + `IfcExtrudedAreaSolid`.

## 5. What the v1 exporter emits (verified on the real sample)

Excellent semantics; poor editability. On `bs-area-e-electrical-room.ifc`:
- Valid IFC4 STEP (`FILE_SCHEMA(('IFC4'))`), Project→Site→Building→one
  Storey "Level 1" with `IfcRelAggregates`; SI metres + electrical units
  (volt/ampere/watt); owner history; 22-char IFC GUIDs; materials as
  `IfcSurfaceStyle`/`IfcStyledItem` (colour + transparency).
- Correct classes: 6× `IfcElectricDistributionBoard` (panels B-HG4, B-LR1,
  B-HQ1, B-LQ1, B-SLQ1, B-SHQ1), 3× `IfcTransformer`,
  `IfcDiscreteAccessory` (trapeze hangers), 1 proxy; psets PanelSchedule /
  TransformerSchedule / SupportSchedule / RoomInformation; types via
  `IfcRelDefinesByType`; `IfcRelContainedInSpatialStructure` to the storey.
- **THE EDITABILITY DEFECTS (fix all in v2):**
  1. **100% tessellation:** 50× `IfcTriangulatedFaceSet`, 0 extrusions.
     Vertices baked to WORLD coords (matrixWorld applied into each point,
     y-up→z-up as (x, -z, y)). → Revit imports every element as a
     **DirectShape** (categorized/schedulable but a frozen, non-parametric
     blob).
  2. **Identity placements:** every product's `IfcLocalPlacement` is the
     same axis-at-origin, so element insertion points are all at the world
     origin; location is only in the vertices. Elements cannot be cleanly
     moved/rotated in Revit.
  3. **Duplicated types:** one `IfcXxxType` per element even for identical
     `typeName` (6 identical panels ⇒ 6 types). Should be ONE shared type.
  4. **No instancing:** repeated identical geometry (42 breakers, 6 panels)
     duplicated verbatim → huge files (277–700 KB). Should use
     `IfcRepresentationMap` + `IfcMappedItem`.
  5. **Annotation graphics exported as solids:** helper groups such as
     `working_clearance` (NEC 110.26 clearance volume, transparent) and
     `door_swing_clearance` (plan swing sector/arc) are exported as
     geometry → Revit gets phantom translucent solids in the model. They
     are already represented as psets (WorkingClearanceDepth/Width/Height,
     DoorSwingRadius). Must be excluded from geometry (or optionally
     emitted as `IfcSpace`/annotation), never as building-element solids.
  6. Single storey only; no `IfcSpace`; empty `IfcPerson`; org
     'three-d-stage'.

## 6. The v2 exporter specification (canonical skill asset)

File: `skills/revit-bridge/assets/ifc-export.js`, exporting
`toIfc(THREE, object, meta = {})` — **API- and tag-compatible drop-in**
for the existing `<three-d-stage>` (module path stays `./ifc-export.js`
inside a Design project). All v1 tags/meta keep working; new behaviour is
default-on where safe and controllable via `meta`. Requirements:

R1 REAL PLACEMENTS. For each product node compute its world matrix;
   decompose to position + rotation (quaternion → z-axis + x-axis
   directions) and emit `IfcLocalPlacement(IfcAxis2Placement3D)` for the
   node (relative to its storey placement). Geometry coordinates are then
   expressed in the node's LOCAL frame (mesh matrixWorld relative to node),
   converted y-up→z-up consistently. Result: correct insertion points and
   orientation; elements are movable/rotatable in Revit.
R2 PARAMETRIC SOLIDS. For a mesh whose `geometry.type` is a known
   primitive with intact `parameters`, emit `IfcExtrudedAreaSolid`:
   Box → `IfcRectangleProfileDef` (width=w, ylen=d, depth=h; three's box
   is centred — offset the profile/position by h/2 correctly and account
   for the mesh's own position/rotation via its placement or an
   `IfcAxis2Placement3D` position on the solid); Cylinder (rt==rb) →
   `IfcCircleProfileDef` extrusion (three cylinders extrude along +Y;
   map to IFC's extrusion direction); Extrude with `Shape` (+holes) →
   `IfcArbitraryClosedProfileDef` / `IfcArbitraryProfileDefWithVoids`
   from the shape's `extractPoints()` outer contour + holes, extruded by
   `options.depth`. Non-primitive / merged / baked `BufferGeometry` →
   tessellation fallback (v1 behaviour). Config `meta.geometry`:
   `"auto"` (default: solids where possible), `"tessellation"` (force v1),
   `"solids"` (force; error if impossible). Representation identifier
   `Body` with type `SweptSolid` for solids, `Tessellation` for fallback;
   mixed → `MappedRepresentation`/multiple items as appropriate.
R3 SHARED TYPES. Dedupe type objects by `(ifcClass, typeName)`: identical
   typeName ⇒ ONE `IfcXxxType`, one `IfcRelDefinesByType` listing all its
   occurrences. Type psets attach once to the shared type.
R4 INSTANCING. Dedupe repeated geometry: meshes sharing the same
   `geometry.uuid` + material set (or an explicit `userData.ifc.instanceOf`
   / repeated `typeName` with identical structure) share one
   `IfcRepresentationMap`; each occurrence is an `IfcMappedItem` with an
   `IfcCartesianTransformationOperator3D` for its local transform.
R5 EXCLUSIONS. Skip nodes where `userData.ifcExclude === true` or
   `userData.ifc === false`; also skip nodes whose name matches
   `meta.excludeNames` (default: `['working_clearance',
   'door_swing_clearance']`, matched as substring/prefix) and any node with
   `userData.helper === true`. Optional `meta.clearanceAs: 'skip' (default)
   | 'space' | 'proxy'` to emit clearance volumes as `IfcSpace` (predefined
   INTERNAL) instead of building elements.
R6 SPATIAL STRUCTURE. `meta.storeys: [{name, elevation}]` (default one
   `{name:'Level 1', elevation:0}`); a node picks its storey via
   `userData.ifc.storey` (name or index); products contained per storey via
   one `IfcRelContainedInSpatialStructure` per storey. Optional
   `userData.ifc.ifcClass === 'IFCSPACE'` handled as a space aggregated to
   its storey (`IfcRelAggregates`) rather than contained.
R7 DETAIL CONTROL. `meta.minFeatureSize` (metres, default 0) drops meshes
   whose bounding box is smaller in all dimensions (screws etc.);
   `userData.ifcLOD = 'skip'|'bbox'|'full'`; `'bbox'` replaces a mesh with
   its bounding box extrusion. Never drop a tagged product node itself.
R8 METADATA. `meta.author {name, org}`, `meta.description`, `meta.site
   {name, latitude, longitude, elevation}`, `meta.building{name}`;
   `IfcApplication` = 'revit-bridge exporter' with version.
R9 DETERMINISM & VALIDITY. Same input ⇒ byte-identical output except
   GUIDs and timestamp; `meta.guidSeed` (optional) makes GUIDs stable via
   a seeded PRNG so re-exports of an unchanged model keep GlobalIds (matters
   for re-import/update workflows). Every entity referenced is defined; no
   dangling `#` refs; strings escaped per ISO-10303-21 (`\X2\..\X0\`).
R10 SIZE. Instancing + shared types should shrink typical outputs by
   large factors versus v1; report entity counts.

Backward-compat guarantee: with `meta.geometry='tessellation'`, no
`excludeNames`, and a v1-tagged model, output must be semantically
equivalent to v1 (same products, classes, psets).

## 7. Why (the Revit reality this all serves)

- Getting IFC INTO Revit is trivial (Open IFC / Link IFC). Getting it in
  EDITABLE depends on the entity classes + geometry representations chosen
  at authoring time. Tessellated Breps/facesets ⇒ **DirectShape** blobs;
  extruded/swept solids with proper placements ⇒ cleaner, movable,
  dimensionally-honest geometry (still generally DirectShape for
  non-architectural MEP equipment in the right category, but usable).
- HARD MEP LIMIT: Revit's IFC importer never creates functioning electrical
  connectors/circuits from IFC. So "editable" has two tiers:
  Tier 1 (better IFC, achievable now via v2 + hardening) = clean,
  movable, correctly-placed, data-rich, correctly-categorized reference
  geometry; Tier 2 (true native MEP families with circuits/panel schedules
  inside Revit) = Revit API only (APS Design Automation add-in placing real
  families and setting parameters — the shared-params file maps 1:1) or a
  native `.rvt` writer. The skill must frame results in these two tiers so
  users are never surprised.
- Renderings need nothing from Revit (images). Shop drawings mostly follow
  from a good model (Revit generates views/sheets); the skill should say
  what stays in Design as docs vs what must become model.

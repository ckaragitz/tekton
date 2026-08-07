# Authoring rules — model three.js so the IFC imports into Revit as cleanly as possible

Every rule here exists because of something Revit's IFC importer does. The
"Why" column is the mechanism; when in doubt, obey the mechanism, not the
letter. Contract details for the tags mentioned live in
`references/tagging-contract.md`.

## 0. The two things Revit rewards

1. **A real placement transform per element** (an insertion point +
   orientation) — so the element is movable/rotatable and its location is
   not "wherever the vertices happen to be".
2. **Parametric solids instead of triangle soup** — an extruded profile
   is a clean, dimensionally exact solid; a bag of triangles is a frozen
   mesh. Both import as DirectShape, but the extrusion is smaller, exact, and
   sections/dimensions cleanly.

Everything below serves one of those two, plus data (psets) and file size.

## 1. Units, orientation, origins

| Rule | Do | Why |
|---|---|---|
| **1.1 Metres.** | All dimensions in real-world metres (`0.508` for a 20-in panel). Convert imperial in code: `const IN = 0.0254, FT = 0.3048;` | The exporter writes SI metres into IFC and Revit converts on link. A model in feet is 3.28× wrong; a model in mm is 1000× wrong. Nothing downstream can tell — the numbers are just wrong. |
| **1.2 Y-up.** | three.js default: +Y is up, floor is the XZ plane, `y = 0` is the finished floor of the node's storey. | The exporter maps three (x, y, z) → IFC (x, −z, y) (z-up). Modelling z-up in three double-rotates. |
| **1.3 Meaningful origins per component.** | Panelboard: origin at **bottom-centre of the enclosure back** (against the wall, on the floor line). Transformer: bottom-centre of the base. Fixture: centre of the mounting face. | The tagged node's origin becomes the Revit insertion point — the thing you snap, dimension and "move to" in Revit. |
| **1.4 Model near the world origin.** | Put the room corner or the equipment lineup near (0,0,0); no 6-digit site coordinates in the model. | Revit misplaces geometry with large Cartesian offsets; use Revit's shared coordinates for site position, not the model. |
| **1.5 One storey datum per level.** | `y=0` of a node = its storey's floor; declare storeys in `meta.storeys`, pick with `userData.ifc.storey`. | Storeys become Revit Levels; the element's reference level and offset come from this. |

## 2. Geometry — keep parameters intact (the extrusion rule)

The exporter emits an `IfcExtrudedAreaSolid` **only** for a mesh whose
`geometry.type` is a known primitive **with intact `.parameters`**:

| Geometry | Exported as | Notes |
|---|---|---|
| `THREE.BoxGeometry(w, h, d)` | `IfcRectangleProfileDef(XDim=w, YDim=d)` extruded `h` | The single most valuable primitive: enclosures, cans, boxes, pads. |
| `THREE.CylinderGeometry(rt, rb, h, seg)` with `rt === rb` | `IfcCircleProfileDef(Radius=rt)` extruded `h` | Conduit stubs, rods, poles. (Tapered `rt ≠ rb` falls back to tessellation.) |
| `THREE.ExtrudeGeometry(shape, { depth, bevelEnabled:false })` | `IfcArbitraryClosedProfileDef` (or `...WithVoids` when `shape.holes` is non-empty) extruded `depth` | The power tool: dead-fronts with breaker cutouts, trims with door openings, L/C strut profiles, any 2D outline. |
| Anything else — `BufferGeometry` from `merge()`, `.applyMatrix4()`, or with `.rotateX()/.rotateY()/.translate()` applied to the **geometry** | `IfcTriangulatedFaceSet` (tessellation) | Still imports; just frozen and heavier. |

**Do:**
```js
const enclosure = new THREE.Mesh(new THREE.BoxGeometry(0.508, 0.914, 0.150), steel);
enclosure.position.set(0, 0.914 / 2, 0.075);   // place with the Object3D, params stay intact
group.add(enclosure);
```

**Don't (these BAKE and destroy parameters):**
```js
geom.rotateX(Math.PI / 2);          // baking a rotation into the vertices → tessellation
geom.translate(0, 1, 0);            // same
const merged = mergeGeometries([a, b, c].map(g => g.clone().applyMatrix4(m)));  // anonymous BufferGeometry → tessellation
```

**Instead:** set `.position` / `.rotation` / `.scale` on the **Mesh/Group**
(the exporter recovers those transforms), and keep repeated parts as
separate meshes sharing one geometry object (§4) rather than merging them.
Merging is only acceptable for genuinely disposable detail you will drop
anyway (`minFeatureSize`), and even then instancing is better.

Non-uniform `.scale` on a primitive is honoured for boxes (dimensions
scale) but forces tessellation for cylinders/extrusions — prefer building
the primitive at final size.

## 3. One tagged product node per real-world component

- Tag the **assembly**, not its parts: `panel_B-LQ1` (a Group) carries
  `userData.ifc`; its enclosure, door, dead-front, trim, and breaker meshes
  are untagged children ⇒ one Revit element with all its geometry. Tagging
  each screw makes 200 Revit elements out of one panel.
- Tag a child separately ONLY if it is genuinely a separately scheduled,
  separately located thing (a wall-mounted disconnect next to a panel is
  its own product; the panel's own main breaker is not).
- Nest products for physical containment that Revit should see (a
  transformer inside an equipment pad group is still its own product node).
- Every tagged node gets a stable, descriptive `.name`
  (`panel_B-LQ1`, `xfmr_LQ1`, `hangers_row_16`). Names feed exclusion
  matching, GUID seeding (`guidSeed`), and your own debugging.

## 4. Shared types and instancing (identical parts)

- **Same physical product ⇒ same `typeName`.** Six identical 42-space
  panelboards share `typeName: 'PB-208Y120-225A-MLO-42SP'` ⇒ ONE
  `IfcElectricDistributionBoardType` in the file (one Revit type identity),
  not six. Put manufacturer/model data in `typePsets` once.
- **Reuse geometry objects for identical parts** so the exporter
  auto-instances them (`IfcRepresentationMap` + `IfcMappedItem`):
```js
const strutGeom = new THREE.BoxGeometry(1.7, 0.041, 0.041);   // ONE geometry object
for (const y of rackElevations) {
  const strut = new THREE.Mesh(strutGeom, galv);             // shared geometry.uuid
  strut.position.set(0, y, 0);
  hangers.add(strut);
}
```
  Constructing `new THREE.BoxGeometry(...)` inside the loop gives every
  strut a different `uuid` ⇒ no instancing. Either share the object as
  above or set `userData.ifc.instanceOf: 'strut-1.7m'` on each.
- Instancing is the difference between a 100 KB and a 5 MB file for a
  hardware-heavy model, and Revit links the small one in seconds.

## 5. Annotation is never physical geometry

These are DRAWING information, not building elements. Model them for the
Design rendering if you like, but they must not become solids in Revit:

| Thing | In the three.js model | In the IFC / Revit |
|---|---|---|
| NEC 110.26 working clearance (the 3–3.5 ft deep zone in front of a panel) | Optional transparent box named `working_clearance` (a child of the panel) for the render | **Excluded by name** (`meta.excludeNames` default). Its size is data: `WorkingClearanceDepth/Width/Height` (length psets on the panel). Optional `meta.clearanceAs:'space'` ⇒ `IfcSpace`. |
| Door swing arc / sector | Flat wedge named `door_swing_clearance` | Excluded by name; radius is the `DoorSwingRadius` length pset. |
| Dimension lines, callouts, tags, level marks, grid bubbles | HTML/SVG overlay or excluded helper nodes | Never in IFC. Revit generates its own annotation from the model. |
| Section boxes, ghosted "existing structure" context, north arrows | `userData.ifcExclude = true` or `userData.helper = true` | Skipped. |

If a clearance/annotation solid ever reaches Revit it appears as a phantom
translucent piece of equipment in every view and clash test — the single
most confusing defect for the Revit user. Name helpers so the default
`excludeNames` catches them, and/or set `ifcExclude`.

## 6. Multi-storey, spaces, and level of detail

- Declare every real level in `meta.storeys` (`[{name:'Level 1',
  elevation:0},{name:'Mezzanine', elevation:3.0}]`, absolute metres) and
  assign products with `userData.ifc.storey`. Racks and hangers at 5 m in a
  double-height room still belong to the **level they are referenced from**
  in the drawings (usually the floor below), with their true `y`.
- Model the room as an `IFCSPACE` product (a simple `BoxGeometry` shell or
  the floor-plate extrusion, `predefinedType:'INTERNAL'` or `'SPACE'`) so
  `RoomInformation` psets have a home and the Revit user gets a schedulable
  Space. A proxy shell (`IFCBUILDINGELEMENTPROXY`, tag `ROOM`) is the v1
  fallback and imports as a Generic Model — acceptable for a "cut-away
  viewing shell", worse for a real room.
- Kill invisible detail: `meta.minFeatureSize: 0.01` drops sub-10 mm
  untagged meshes (screws, rivets); `userData.ifcLOD:'bbox'` collapses a
  dense assembly to its bounding box; `'skip'` keeps a product's data but no
  body. Revit does not need thread pitch on a 3/8-in rod.

## 7. Naming conventions

- **Node names:** `snake_case`, `<kind>_<tag>` — `panel_B-LQ1`, `xfmr_LQ1`,
  `hangers_grid16`, `space_room101`, `working_clearance`. Helper/annotation
  names must contain `working_clearance`, `door_swing_clearance`, or your
  own token added to `meta.excludeNames`.
- **`name` (IFC/Revit element name):** the equipment tag humans read —
  `B-LQ1`, `XFMR-LR1`, `Trapeze hangers — rack at 16 ft 6 in AFF`.
- **`tag`:** the pure equipment mark — `B-LQ1`, `XFMR-LR1`, `BS-EP7-00`.
- **`typeName`:** manufacturer-catalogue style, identical for identical
  units — `Eaton Pow-R-Line 4 — 208Y/120V — 225A MLO — 42 space`.
- **Pset names:** `PanelSchedule`, `TransformerSchedule`, `SupportSchedule`,
  `RoomInformation`, plus standard `Pset_*Common` where they exist
  (`Pset_ElectricDistributionBoardTypeCommon`, `Pset_TransformerTypeCommon`,
  `Pset_ManufacturerTypeInformation`).
- **Property names:** exactly the firm's shared-parameter names
  (`PanelName, Voltage, Phases, Wires, BusRating, MainsType, MainsRating,
  ShortCircuitRatingkA, Mounting, NumberOfCircuits, NeutralRating`);
  CamelCase, no spaces, case-sensitive.
- **File/project names:** `meta.fileName` kebab-case
  (`bs-area-e-electrical-room`), `meta.projectName` human title.

## 8. Full worked example — Area E electrical room (2 storeys, shared type, transformer, excluded clearance)

The scenario the rules were extracted from. Two identical panelboards
sharing a type, one transformer feeding one of them, a working-clearance
helper that must NOT export, and a trapeze-hanger rack on the mezzanine
level. Copy this pattern; the runnable version is
`assets/example-model.js`.

```js
// model.js — imported by the Design page; buildModel(THREE) returns the root Group
const FT = 0.3048, IN = 0.0254;

export const ifcMeta = {
  projectName: 'DDOT Coolidge — Area E bus storage electrical room',
  fileName:    'bs-area-e-electrical-room',
  description: '34 ft x 16 ft clear, 20 ft to structure',
  author:      { org: 'Coolidge JV Electrical' },
  storeys:     [ { name: 'Level 1',   elevation: 0 },
                 { name: 'Mezzanine', elevation: 10 * FT } ],
  geometry:      'auto',
  excludeNames:  ['working_clearance', 'door_swing_clearance'],
  clearanceAs:   'skip',
  minFeatureSize: 0.01,
  guidSeed:      'coolidge-area-e-v1',
};

export function buildModel(THREE) {
  const root  = new THREE.Group(); root.name = 'area_e_electrical_room';
  const steel = new THREE.MeshStandardMaterial({ color: 0x9ca2a3 }); steel.name = 'ansi61_gray';
  const cu    = new THREE.MeshStandardMaterial({ color: 0xb87333 }); cu.name = 'transformer_gray';

  // ---- The room itself: a schedulable IfcSpace ------------------------------------------
  const space = new THREE.Mesh(new THREE.BoxGeometry(34 * FT, 20 * FT, 16 * FT),
                               new THREE.MeshStandardMaterial({ transparent: true, opacity: 0.06 }));
  space.name = 'space_room_E';
  space.position.set(0, 10 * FT, 0);                    // box is centred → lift by half height
  space.userData.ifc = { ifcClass: 'IFCSPACE', predefinedType: 'SPACE',
    name: 'Electrical Room E', tag: 'E', storey: 'Level 1',
    psets: [ { name: 'RoomInformation', props: {
      Facility: 'DDOT Coolidge — bus storage / coach services', Area: 'E' } } ] };
  root.add(space);

  // ---- Shared geometry for BOTH panels ⇒ instancing; shared typeName ⇒ one type ------
  const encGeom  = new THREE.BoxGeometry(20 * IN, 36 * IN, 5.75 * IN);   // W x H x D, params intact
  const trimGeom = (() => {                                              // ExtrudeGeometry w/ door opening (hole)
    const s = new THREE.Shape().moveTo(-10*IN, -18*IN).lineTo(10*IN, -18*IN).lineTo(10*IN, 18*IN).lineTo(-10*IN, 18*IN).closePath();
    const hole = new THREE.Path().moveTo(-8*IN, -16*IN).lineTo(8*IN, -16*IN).lineTo(8*IN, 16*IN).lineTo(-8*IN, 16*IN).closePath();
    s.holes.push(hole);
    return new THREE.ExtrudeGeometry(s, { depth: 0.002, bevelEnabled: false });
  })();

  const PANEL_TYPE = 'Eaton Pow-R-Line 4 — 208Y/120V — 225A MLO — 42 space';
  const panelTypePsets = [ { name: 'Pset_ManufacturerTypeInformation',
    props: { Manufacturer: 'Eaton', ModelLabel: 'Pow-R-Line 4', ModelReference: 'PRL4a' } } ];

  function panel(tag, x, feed) {
    const g = new THREE.Group(); g.name = `panel_${tag}`;
    g.position.set(x, 0.75 * FT, -7.85 * FT);          // origin = bottom-centre of enclosure back; 9 in below top-of-panel AFF calc
    const enc = new THREE.Mesh(encGeom, steel);          // SHARED geometry object ⇒ IfcMappedItem
    enc.position.set(0, 18 * IN, 2.875 * IN);            // centre the box on the origin (bottom-back-centre)
    const trim = new THREE.Mesh(trimGeom, steel);        // extrusion with a void ⇒ IfcArbitraryProfileDefWithVoids
    trim.position.set(0, 18 * IN, 5.75 * IN);            // on the front face (extrudes +z, i.e. toward the room)
    g.add(enc, trim);

    // Annotation, NOT geometry: rendered translucent, excluded from IFC by name.
    const wc = new THREE.Mesh(new THREE.BoxGeometry(30 * IN, 6.5 * FT, 42 * IN),
                              new THREE.MeshStandardMaterial({ transparent: true, opacity: 0.15 }));
    wc.name = 'working_clearance';                       // matches meta.excludeNames ⇒ skipped
    wc.position.set(0, (6.5 * FT) / 2 - 0.75 * FT, 5.75 * IN + 21 * IN);
    g.add(wc);

    g.userData.ifc = {
      ifcClass: 'IFCELECTRICDISTRIBUTIONBOARD', predefinedType: 'DISTRIBUTIONBOARD',
      name: tag, tag, description: `Panelboard, 208Y/120 V; fed from ${feed}`,
      storey: 'Level 1', typeName: PANEL_TYPE, typePsets: panelTypePsets,
      psets: [ { name: 'PanelSchedule', props: {
        PanelName: tag, DoorPosition: 'Hinged left',
        DoorSwingRadius:        { value: 20 * IN,   type: 'length' },
        WorkingClearanceShown:  { value: true,      type: 'boolean' },
        WorkingClearanceDepth:  { value: 42 * IN,   type: 'length' },
        WorkingClearanceWidth:  { value: 30 * IN,   type: 'length' },
        WorkingClearanceHeight: { value: 6.5 * FT,  type: 'length' },
        Voltage:   { value: 208, type: 'voltage' }, Phases: { value: 3, type: 'integer' },
        Wires:     { value: 4,   type: 'integer' }, BusRating: { value: 225, type: 'current' },
        MainsType: 'MLO', MainsRating: { value: 225, type: 'current' },
        ShortCircuitRatingkA: { value: 10, type: 'real' }, Mounting: 'Surface',
        NumberOfCircuits: { value: 42, type: 'count' }, NeutralRating: '100%' } },
        { name: 'Pset_ElectricDistributionBoardTypeCommon', props: {
          Reference: tag, IsMain: { value: false, type: 'boolean' },
          NumberOfCircuits: { value: 42, type: 'count' } } } ],
    };
    return g;
  }

  root.add(panel('B-LQ1',  -12.4 * FT, 'XFMR-LQ1 via BS-FD1013'));
  root.add(panel('B-SLQ1', -9.0 * FT,  'XFMR-B-SLQ1'));           // SAME typeName ⇒ ONE shared type

  // ---- Transformer: its own product, distinct class ---------------------------------------
  const xf = new THREE.Group(); xf.name = 'xfmr_LQ1';
  xf.position.set(-14.5 * FT, 0, -7.4 * FT);           // origin = bottom-centre of base
  const xfCase = new THREE.Mesh(new THREE.BoxGeometry(26 * IN, 30 * IN, 20 * IN), cu);
  xfCase.position.set(0, 15 * IN, 0);
  xf.add(xfCase);
  xf.userData.ifc = {
    ifcClass: 'IFCTRANSFORMER', predefinedType: 'VOLTAGE',
    name: 'XFMR-LQ1', tag: 'XFMR-LQ1', storey: 'Level 1',
    description: '45 kVA dry-type, 480 V delta – 208Y/120 V, feeds B-LQ1',
    typeName: 'Dry-type 45 kVA 480D-208Y/120 Cu',
    psets: [ { name: 'TransformerSchedule', props: {
      RatingkVA: { value: 45, type: 'real' }, Primary: '480 V delta',
      Secondary: '208Y/120 V', Feeds: 'B-LQ1' } } ],
  };
  root.add(xf);

  // ---- Trapeze hangers on the MEZZANINE level, instanced strut ------------------------
  const hangers = new THREE.Group(); hangers.name = 'hangers_rack16';
  hangers.userData.ifc = { ifcClass: 'IFCDISCRETEACCESSORY', predefinedType: 'BRACKET',
    name: 'Trapeze hangers — rack at 16 ft 6 in AFF', tag: 'HANGERS', storey: 'Mezzanine',
    psets: [ { name: 'SupportSchedule', props: {
      StrutSize: '1-5/8 in x 1-5/8 in, 12 ga',
      StrutLengthEach: { value: 1.7, type: 'length' },
      RodSize: '3/8 in-16 threaded rod',
      RodLengthEach: { value: 1.03536, type: 'length' },
      SpacingFt: { value: 8, type: 'real' } } } ] };
  const strutGeom = new THREE.BoxGeometry(1.7, 0.041, 0.041);   // one geometry object, reused ⇒ instancing
  for (let i = 0; i < 4; i++) {
    const s = new THREE.Mesh(strutGeom, steel);        // shared uuid ⇒ IfcMappedItem
    s.position.set(-12 * FT + i * 8 * FT, 6.5 * FT, -3 * FT); // y relative to Mezzanine (10 ft) ⇒ 16.5 ft AFF
    hangers.add(s);
  }
  root.add(hangers);

  return root;
}
```

What this produces, and why each choice is right:

- 2 `IfcElectricDistributionBoard` products sharing **one**
  `IfcElectricDistributionBoardType` (`typeName` identical) — Revit shows one
  type, not two.
- The enclosure `BoxGeometry` is one shared object across both panels ⇒ one
  `IfcRepresentationMap`, two `IfcMappedItem`s ⇒ half the geometry bytes.
- The trim is an `ExtrudeGeometry` with a hole ⇒
  `IfcArbitraryProfileDefWithVoids` extrusion — an exact opening, not
  triangles.
- Each `panel_*` Group's `.position` is the real insertion point ⇒ each
  panel is independently movable in Revit; nothing baked into vertices.
- `working_clearance` matches `meta.excludeNames` ⇒ no phantom solid; the
  clearance dimensions still travel as `WorkingClearance*` length psets.
- The transformer is its own `IfcTransformer .VOLTAGE.` product with its own
  `TransformerSchedule` pset ⇒ correct category and its own row in any
  Revit equipment schedule.
- The hangers live on the `Mezzanine` storey ⇒ a second Revit Level, with
  their true elevation; strut is instanced.
- `guidSeed` fixed ⇒ re-exports keep GlobalIds ⇒ re-linking updates in place.
- The `IFCSPACE` shell gives Revit a Space carrying `RoomInformation`.

## 9. Pre-export checklist (run down it every time)

1. All numbers metres; y-up; model near origin. (`8.10` in SKILL.md)
2. Every real component is exactly one tagged Group; helpers named/flagged
   for exclusion.
3. Every solid you care about is an intact `Box/Cylinder/ExtrudeGeometry`
   positioned via the `Object3D`, not baked.
4. Identical units share `typeName`; identical parts share a geometry
   object (or `instanceOf`).
5. Every product has `storey`; `meta.storeys` lists every level.
6. Psets use the firm's exact property names and correct `type`s
   (numbers unitless-in-value, metres/V/A).
7. `meta.guidSeed` set; `meta.fileName` kebab-case.
8. No clearance/annotation node can escape into geometry
   (`excludeNames` covers all helper names).

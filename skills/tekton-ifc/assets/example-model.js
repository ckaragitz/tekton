// =============================================================================
//  example-model.js — canonical tekton-ifc demo assembly
// =============================================================================
//
//  buildExampleModel(THREE) → THREE.Group
//
//  A two-storey electrical room that exercises EVERY exporter feature:
//
//  Level 1
//    ├─ IFCSPACE   "Electrical Room 101"   (room volume; aggregated to storey)
//    ├─ panel P1   IFCELECTRICDISTRIBUTIONBOARD, typeName T400
//    │    ├─ enclosure  un-baked BoxGeometry           → IfcExtrudedAreaSolid
//    │    ├─ dead_front ExtrudeGeometry(shape + holes)   → IfcArbitraryProfileDefWithVoids
//    │    ├─ latch      baked/merged BufferGeometry, ifcLOD 'bbox' → bbox extrusion
//    │    ├─ screw      ifcLOD 'skip'                    → dropped
//    │    └─ working_clearance (helper group)         → EXCLUDED (R5)
//    ├─ panel P2   same typeName + SAME geometry objects → shared type +
//    │             IfcMappedItem instancing; rotated 90° (placement test)
//    ├─ xfmr T1    IFCTRANSFORMER (VOLTAGE), box case
//    └─ conduit    IFCCABLECARRIERSEGMENT (CONDUITSEGMENT), cylinder rt==rb
//  Level 2 (elevation 4 m)
//    ├─ panel P3   different typeName → its own type
//    └─ proxy      merged/baked BufferGeometry → tessellation fallback
//
//  Conventions: metres, y-up, origin at a meaningful anchor (panelboard =
//  bottom-centre of enclosure back). Everything is tagged per the
//  ifc-export.js contract (psets with typed measures, typeName, typePsets).
// =============================================================================

export const EXAMPLE_STOREYS = [
  { name: 'Level 1', elevation: 0 },
  { name: 'Level 2', elevation: 4 },
];

/** Suggested `meta` / stage.ifcMeta for the example. */
export function exampleMeta(overrides = {}) {
  return {
    projectName: 'Example Electrical Room',
    fileName: 'example-electrical-room',
    description: 'tekton-ifc canonical example: two-storey electrical room',
    author: { name: 'tekton-ifc', org: 'tekton-ifc' },
    building: { name: 'Electrical Building E' },
    site: { name: 'Example Site' },
    storeys: EXAMPLE_STOREYS,
    ...overrides,
  };
}

/**
 * Build the demo assembly.
 * @param {object} THREE  the three.js namespace (0.184.x)
 * @returns {THREE.Group}
 */
export function buildExampleModel(THREE) {
  const root = new THREE.Group();
  root.name = 'electrical_room_101';

  // -------------------------------------------------------------- materials
  const mat = {
    enclosure: new THREE.MeshStandardMaterial({ color: 0x9ca2a3, metalness: 0.35, roughness: 0.55, name: 'ansi61_gray' }),
    deadfront: new THREE.MeshStandardMaterial({ color: 0xb8bdc0, metalness: 0.3, roughness: 0.5, name: 'deadfront_gray' }),
    hardware: new THREE.MeshStandardMaterial({ color: 0x2a2a28, metalness: 0.6, roughness: 0.4, name: 'black_hardware' }),
    breaker: new THREE.MeshStandardMaterial({ color: 0x1f2224, metalness: 0.2, roughness: 0.7, name: 'breaker_black' }),
    xfmr: new THREE.MeshStandardMaterial({ color: 0x8a8f92, metalness: 0.3, roughness: 0.6, name: 'ansi61_gray_xfmr' }),
    conduit: new THREE.MeshStandardMaterial({ color: 0xa7abae, metalness: 0.7, roughness: 0.35, name: 'emt_zinc' }),
    strut: new THREE.MeshStandardMaterial({ color: 0x6b6f72, metalness: 0.6, roughness: 0.4, name: 'strut_galv' }),
    clearance: new THREE.MeshStandardMaterial({ color: 0xffcc00, transparent: true, opacity: 0.18, name: 'clearance_amber' }),
    space: new THREE.MeshStandardMaterial({ color: 0x7fb0d8, transparent: true, opacity: 0.10, name: 'space_volume' }),
  };

  // ---------------------------------------------------------- shared parts
  // Panel type "T400": ONE set of geometry objects, reused by P1 and P2 so
  // the exporter emits IfcRepresentationMap + IfcMappedItem instancing.
  const T400 = {
    typeName: 'Eaton Pow-R-Line 4 (style) - 400A MB - 42 space',
    W: 0.508, H: 1.194, D: 0.144,          // 20" x 47" x 5.75"
    encl: null, deadfront: null,
  };
  T400.encl = new THREE.BoxGeometry(T400.W, T400.H, T400.D);
  // dead-front cut-outs: one twin-pole opening per row (21 rows)
  T400.slots = { slotW: 0.24, slotH: 0.028, rows: 21, cols: 1, pitch: 0.05, colOffset: 0 };
  T400.deadfront = makeDeadFrontGeometry(THREE, {
    width: 0.457, height: 1.09, depth: 0.002, ...T400.slots,
  });
  // breakers: 21 rows × 2 columns = 42, ALL sharing one geometry object
  T400.breakers = { rows: 21, cols: 2, pitch: 0.05, colOffset: 0.09 };
  T400.breaker = new THREE.BoxGeometry(0.076, 0.024, 0.05);

  // Panel type "T100" (Level 2): its own geometry (different size)
  const T100 = {
    typeName: 'Eaton Pow-R-Line 1a (style) - 100A MLO - 30 space',
    W: 0.406, H: 0.813, D: 0.108,          // 16" x 32" x 4.25"
    encl: null, deadfront: null,
  };
  T100.encl = new THREE.BoxGeometry(T100.W, T100.H, T100.D);
  T100.slots = { slotW: 0.21, slotH: 0.026, rows: 15, cols: 1, pitch: 0.045, colOffset: 0 };
  T100.deadfront = makeDeadFrontGeometry(THREE, {
    width: 0.36, height: 0.72, depth: 0.002, ...T100.slots,
  });
  T100.breakers = { rows: 15, cols: 2, pitch: 0.045, colOffset: 0.08 };
  T100.breaker = new THREE.BoxGeometry(0.068, 0.022, 0.045);

  // A deliberately BAKED / MERGED geometry (no `parameters`) → tessellation
  const bakedLatch = mergeBakedBoxes(THREE, [
    { size: [0.02, 0.07, 0.02], offset: [0, 0, 0] },
    { size: [0.05, 0.012, 0.03], offset: [0, 0, 0.02] },
  ]);

  // ================================================================ LEVEL 1
  const level1 = new THREE.Group();
  level1.name = 'level_1';
  root.add(level1);

  // ---- room volume as IFCSPACE (aggregated to Level 1, not "contained")
  const room = new THREE.Group();
  room.name = 'electrical_room_101_volume';
  const roomW = 7.0, roomH = 3.2, roomD = 5.0;
  const roomMesh = new THREE.Mesh(new THREE.BoxGeometry(roomW, roomH, roomD), mat.space);
  roomMesh.name = 'room_volume';
  roomMesh.position.set(0, roomH / 2, 0);
  room.add(roomMesh);
  room.userData.ifc = {
    ifcClass: 'IFCSPACE',
    predefinedType: 'INTERNAL',
    name: 'Electrical Room 101',
    longName: 'Level 1 Electrical Room',
    description: '400 A service electrical room, Level 1',
    storey: 'Level 1',
    psets: [{
      name: 'RoomInformation',
      props: {
        RoomNumber: { value: '101', type: 'identifier' },
        RoomName: 'Electrical Room',
        Occupancy: 'Electrical equipment room (NEC 110.26)',
        ClearFloorArea: { value: roomW * roomD, type: 'area' },
        CeilingHeight: { value: roomH, type: 'length' },
        RatedEnclosure: { value: false, type: 'boolean' },
      },
    }],
  };
  level1.add(room);

  // ---- panels P1 and P2 (identical type + shared geometry)
  const p1 = makePanel(THREE, T400, mat, {
    name: 'panel_B-HG4', panelName: 'B-HG4',
    description: "Panelboard, 480Y/277 V — 400 A main breaker; fed from MDB via BS-FD1020 (per O'Malley spec, Ø 3″)",
    voltage: 480, phases: 3, wires: 4, busRating: 400, mainsType: 'Main Breaker',
    mainsRating: 400, sccr: 35, circuits: 42, isMain: true,
    storey: 'Level 1', latch: bakedLatch,
  });
  p1.position.set(-1.8, 1.0, -2.32);      // bottom of enclosure at 1.0 m AFF, back to north wall
  level1.add(p1);

  const p2 = makePanel(THREE, T400, mat, {
    name: 'panel_B-HQ1', panelName: 'B-HQ1',
    description: 'Panelboard, 480Y/277 V, 400 A main breaker; fed from B-HD1 via BS-FD1009',
    voltage: 480, phases: 3, wires: 4, busRating: 400, mainsType: 'Main Breaker',
    mainsRating: 400, sccr: 35, circuits: 42, isMain: false,
    storey: 'Level 1', latch: bakedLatch,
  });
  p2.position.set(3.32, 1.0, 0.6);        // on the east wall …
  p2.rotation.y = -Math.PI / 2;           // … rotated to face west (placement rotation test)
  level1.add(p2);

  // ---- transformer T1 (box)
  const xfmr = new THREE.Group();
  xfmr.name = 'xfmr_LR1';
  const caseW = 0.66, caseH = 0.762, caseD = 0.508;
  const caseMesh = new THREE.Mesh(new THREE.BoxGeometry(caseW, caseH, caseD), mat.xfmr);
  caseMesh.name = 'xfmr_case';
  caseMesh.position.set(0, caseH / 2, 0);          // sits on the floor
  xfmr.add(caseMesh);
  // ventilation louvre bar (small box, still parametric)
  const louvre = new THREE.Mesh(new THREE.BoxGeometry(caseW * 0.8, 0.02, 0.012), mat.hardware);
  louvre.name = 'xfmr_louvre';
  louvre.position.set(0, caseH * 0.75, caseD / 2 + 0.006);
  xfmr.add(louvre);
  xfmr.position.set(2.4, 0, -2.2);
  xfmr.userData.ifc = {
    ifcClass: 'IFCTRANSFORMER',
    predefinedType: 'VOLTAGE',
    name: 'XFMR-LR1',
    tag: 'XFMR-LR1',
    description: '45 kVA dry-type, 480 V delta - 208Y/120 V, feeds B-LR1',
    typeName: 'Dry-type transformer 45 kVA 480D-208Y/120',
    storey: 'Level 1',
    psets: [{
      name: 'TransformerSchedule',
      props: {
        TransformerTag: 'XFMR-LR1',
        RatingkVA: { value: 45, type: 'real' },
        RatedPower: { value: 45000, type: 'power' },
        PrimaryVoltage: { value: 480, type: 'voltage' },
        SecondaryVoltage: { value: 208, type: 'voltage' },
        Phases: { value: 3, type: 'integer' },
        ImpedancePercent: { value: 5.75, type: 'real' },
        KFactor: { value: 4, type: 'count' },
        WeatherEnclosure: { value: false, type: 'boolean' },
        MountingHeightAFF: { value: 0, type: 'length' },
      },
    }],
    typePsets: [{
      name: 'Pset_ManufacturerTypeInformation',
      props: { Manufacturer: 'Eaton', ModelLabel: 'DT-3 dry type', ModelReference: 'V48M28T45' },
    }],
  };
  level1.add(xfmr);

  // ---- conduit stub (cylinder rt == rb) running horizontally into P1
  const conduit = new THREE.Group();
  conduit.name = 'conduit_CN-101';
  const cRadius = 0.0224, cLength = 1.6;  // 1-1/2" EMT
  const cMesh = new THREE.Mesh(new THREE.CylinderGeometry(cRadius, cRadius, cLength, 20), mat.conduit);
  cMesh.name = 'conduit_run';
  cMesh.rotation.z = Math.PI / 2;         // three cylinders extrude along +Y → lay it along X
  cMesh.position.set(0, 0, 0);
  conduit.add(cMesh);
  conduit.position.set(-3.1, 2.6, -2.25);
  conduit.userData.ifc = {
    ifcClass: 'IFCCABLECARRIERSEGMENT',
    predefinedType: 'CONDUITSEGMENT',
    name: 'CN-101 feeder stub',
    tag: 'CN-101',
    description: '1-1/2 in EMT feeder stub into B-HG4',
    typeName: 'EMT conduit 1-1/2 in',
    storey: 0,                              // storey by index
    psets: [{
      name: 'ConduitRun',
      props: {
        TradeSize: '1-1/2"',
        Material: 'EMT',
        Length: { value: cLength, type: 'length' },
        ConduitCount: { value: 1, type: 'count' },
        Voltage: { value: 480, type: 'voltage' },
        AmpacityBasis: { value: 400, type: 'current' },
        FieldRouted: { value: true, type: 'boolean' },
      },
    }],
  };
  level1.add(conduit);

  // ---- a door-swing clearance helper at storey level (excluded by name)
  const doorSwing = new THREE.Group();
  doorSwing.name = 'door_swing_clearance';
  const swingMesh = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 0.9, 0.02, 24, 1, false, 0, Math.PI / 2), mat.clearance);
  swingMesh.name = 'door_swing_sector';
  doorSwing.add(swingMesh);
  doorSwing.position.set(2.8, 0.01, 1.6);
  level1.add(doorSwing);

  // ================================================================ LEVEL 2
  const level2 = new THREE.Group();
  level2.name = 'level_2';
  level2.position.set(0, EXAMPLE_STOREYS[1].elevation, 0);   // +4 m
  root.add(level2);

  const p3 = makePanel(THREE, T100, mat, {
    name: 'panel_B-LQ2', panelName: 'B-LQ2',
    description: 'Panelboard, 208Y/120 V, 100 A MLO; fed from XFMR-LQ2',
    voltage: 208, phases: 3, wires: 4, busRating: 100, mainsType: 'MLO',
    mainsRating: 100, sccr: 10, circuits: 30, isMain: false,
    storey: 'Level 2', latch: null,
  });
  p3.position.set(1.1, 1.1, -2.32);
  level2.add(p3);

  // ---- a proxy with baked/merged geometry (no storey tag → inferred by elevation)
  const proxy = new THREE.Group();
  proxy.name = 'unistrut_kit_baked';
  const proxyMesh = new THREE.Mesh(mergeBakedBoxes(THREE, [
    { size: [1.2, 0.041, 0.041], offset: [0, 0, 0] },        // strut channel
    { size: [0.01, 0.6, 0.01], offset: [-0.5, 0.3, 0] },       // threaded rod L
    { size: [0.01, 0.6, 0.01], offset: [0.5, 0.3, 0] },        // threaded rod R
  ]), mat.strut);
  proxyMesh.name = 'trapeze_baked';
  proxy.add(proxyMesh);
  proxy.position.set(-1.4, 2.7, -1.4);
  proxy.userData.ifc = {
    ifcClass: 'IFCBUILDINGELEMENTPROXY',
    predefinedType: 'NOTDEFINED',
    name: 'Trapeze hanger kit (baked geometry demo)',
    description: 'Merged BufferGeometry - tessellation fallback demo; storey inferred by elevation',
    typeName: 'Trapeze hanger 1-5/8 strut on 3/8 rod',
    psets: [{
      name: 'SupportSchedule',
      props: {
        StrutSize: '1-5/8 in',
        RodDiameter: { value: 0.0095, type: 'length' },
        RackElevationAFF: { value: 2.7, type: 'length' },
        SeismicBracing: { value: false, type: 'boolean' },
        Quantity: { value: 1, type: 'count' },
      },
    }],
  };
  level2.add(proxy);

  return root;
}

export default buildExampleModel;

// =============================================================================
//  builders
// =============================================================================

/**
 * A panelboard: tagged Group (product) whose origin is the bottom-centre of
 * the enclosure back. Meshes are placed in the group's LOCAL frame; the
 * exporter turns the group's world transform into the IFC insertion point.
 */
function makePanel(THREE, T, mat, opt) {
  const g = new THREE.Group();
  g.name = opt.name;

  // enclosure (un-baked box → IfcExtrudedAreaSolid); shared geometry object
  const encl = new THREE.Mesh(T.encl, mat.enclosure);
  encl.name = `${opt.panelName}_enclosure`;
  encl.position.set(0, T.H / 2, T.D / 2);          // back face at z=0, bottom at y=0
  g.add(encl);

  // dead front WITH breaker slots (ExtrudeGeometry shape+holes) — shared
  const df = new THREE.Mesh(T.deadfront, mat.deadfront);
  df.name = `${opt.panelName}_dead_front`;
  df.position.set(0, T.H / 2, T.D - 0.012);        // recessed 12 mm behind the front, extrudes +z 2 mm
  g.add(df);

  // breakers: rows×cols identical boxes SHARING one geometry object →
  // mesh-level IfcRepresentationMap + one IfcMappedItem per breaker.
  const breakers = new THREE.Group();
  breakers.name = `${opt.panelName}_breakers`;
  const { rows, cols, pitch, colOffset } = T.breakers;
  const y0 = T.H / 2 - ((rows - 1) * pitch) / 2;
  for (let r = 0; r < rows; r += 1) {
    for (let c = 0; c < cols; c += 1) {
      const b = new THREE.Mesh(T.breaker, mat.breaker);
      b.name = `${opt.panelName}_bkr_${String(r * cols + c + 1).padStart(2, '0')}`;
      b.position.set((c === 0 ? -1 : 1) * colOffset, y0 + r * pitch, T.D + 0.006);
      breakers.add(b);
    }
  }
  g.add(breakers);

  // main-breaker handle (small parametric cylinder — still a solid)
  const handle = new THREE.Mesh(new THREE.CylinderGeometry(0.012, 0.012, 0.06, 12), mat.hardware);
  handle.name = `${opt.panelName}_main_handle`;
  handle.rotation.x = Math.PI / 2;                  // point out of the front (+z)
  handle.position.set(0.15, T.H * 0.86, T.D + 0.03);
  g.add(handle);

  // latch (baked/merged geometry) with ifcLOD 'bbox' → bounding-box extrusion
  if (opt.latch) {
    const latch = new THREE.Mesh(opt.latch, mat.hardware);
    latch.name = `${opt.panelName}_latch`;
    latch.position.set(-T.W / 2 + 0.03, T.H * 0.55, T.D + 0.01);
    latch.userData.ifcLOD = 'bbox';
    g.add(latch);
  }

  // a screw far below any useful feature size → ifcLOD 'skip'
  const screw = new THREE.Mesh(new THREE.CylinderGeometry(0.004, 0.004, 0.008, 8), mat.hardware);
  screw.name = `${opt.panelName}_screw`;
  screw.rotation.x = Math.PI / 2;
  screw.position.set(T.W / 2 - 0.03, T.H - 0.03, T.D + 0.004);
  screw.userData.ifcLOD = 'skip';
  g.add(screw);

  // NEC 110.26 working clearance — a HELPER group; never a building element
  const clearance = new THREE.Group();
  clearance.name = 'working_clearance';
  clearance.userData.helper = true;
  const wcW = 0.762, wcH = 1.98, wcD = 0.914;
  const wcMesh = new THREE.Mesh(new THREE.BoxGeometry(wcW, wcH, wcD), mat.clearance);
  wcMesh.name = 'working_clearance_volume';
  wcMesh.position.set(0, wcH / 2 - 0.9, T.D + wcD / 2);
  clearance.add(wcMesh);
  g.add(clearance);

  // ---- IFC tag (the product) --------------------------------------------
  const vLabel = opt.voltage === 480 ? '480Y/277 V' : opt.voltage === 208 ? '208Y/120 V' : `${opt.voltage} V`;
  g.userData.ifc = {
    ifcClass: 'IFCELECTRICDISTRIBUTIONBOARD',
    predefinedType: 'DISTRIBUTIONBOARD',
    name: opt.panelName,
    tag: opt.panelName,
    description: opt.description,
    typeName: T.typeName,
    storey: opt.storey,
    psets: [
      {
        name: 'PanelSchedule',
        props: {
          PanelName: opt.panelName,
          Voltage: { value: opt.voltage, type: 'voltage' },
          VoltageSystem: vLabel,
          Phases: { value: opt.phases, type: 'integer' },
          Wires: { value: opt.wires, type: 'integer' },
          BusRating: { value: opt.busRating, type: 'current' },
          MainsType: opt.mainsType,
          MainsRating: { value: opt.mainsRating, type: 'current' },
          ShortCircuitRatingkA: { value: opt.sccr, type: 'real' },
          Mounting: 'Surface',
          NumberOfCircuits: { value: opt.circuits, type: 'count' },
          NeutralRating: '100%',
          DoorPosition: 'Hinged Left',
          DoorSwingRadius: { value: 0.51, type: 'length' },
          WorkingClearanceShown: { value: true, type: 'boolean' },
          WorkingClearanceDepth: { value: wcD, type: 'length' },
          WorkingClearanceWidth: { value: wcW, type: 'length' },
          WorkingClearanceHeight: { value: wcH, type: 'length' },
        },
      },
      {
        name: 'Pset_ElectricDistributionBoardTypeCommon',
        props: {
          Reference: { value: T.typeName, type: 'identifier' },
          IsMain: { value: opt.isMain, type: 'boolean' },
          NumberOfCircuits: { value: opt.circuits, type: 'count' },
        },
      },
    ],
    typePsets: [{
      name: 'Pset_ManufacturerTypeInformation',
      props: {
        Manufacturer: 'Eaton',
        ModelLabel: opt.busRating >= 400 ? 'Pow-R-Line 4' : 'Pow-R-Line 1a',
        ModelReference: `PRL-${opt.busRating}-${opt.circuits}`,
        ArticleNumber: { value: `EAT-PRL-${opt.busRating}`, type: 'identifier' },
      },
    }],
  };
  return g;
}

/**
 * Dead-front panel: a rectangle Shape with a grid of rectangular breaker
 * cut-outs as `.holes`, extruded by `depth` (bevelEnabled:false). The
 * exporter converts this to IfcArbitraryProfileDefWithVoids +
 * IfcExtrudedAreaSolid — an editable profile, not triangles.
 */
export function makeDeadFrontGeometry(THREE, o) {
  const { width, height, depth, slotW, slotH, rows, cols, pitch, colOffset } = o;
  const shape = new THREE.Shape();
  shape.moveTo(-width / 2, -height / 2);
  shape.lineTo(width / 2, -height / 2);
  shape.lineTo(width / 2, height / 2);
  shape.lineTo(-width / 2, height / 2);
  shape.lineTo(-width / 2, -height / 2);
  const y0 = -((rows - 1) * pitch) / 2;
  for (let r = 0; r < rows; r += 1) {
    const cy = y0 + r * pitch;
    for (let c = 0; c < cols; c += 1) {
      const cx = (c === 0 ? -1 : 1) * colOffset;
      const hole = new THREE.Path();
      hole.moveTo(cx - slotW / 2, cy - slotH / 2);
      hole.lineTo(cx - slotW / 2, cy + slotH / 2);
      hole.lineTo(cx + slotW / 2, cy + slotH / 2);
      hole.lineTo(cx + slotW / 2, cy - slotH / 2);
      hole.lineTo(cx - slotW / 2, cy - slotH / 2);
      shape.holes.push(hole);
    }
  }
  return new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false });
}

/**
 * Emulates the v1 "merge()" helper: several boxes cloned, transformed and
 * merged into ONE anonymous BufferGeometry. This DESTROYS the parametric
 * definition (no `parameters`) — the exporter must tessellate it.
 */
export function mergeBakedBoxes(THREE, parts) {
  const positions = [];
  const normals = [];
  for (const p of parts) {
    const g = new THREE.BoxGeometry(p.size[0], p.size[1], p.size[2]);
    g.translate(p.offset[0], p.offset[1], p.offset[2]);          // bake!
    const ng = g.toNonIndexed();
    positions.push(...ng.attributes.position.array);
    normals.push(...ng.attributes.normal.array);
    g.dispose(); ng.dispose();
  }
  const merged = new THREE.BufferGeometry();
  merged.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  merged.setAttribute('normal', new THREE.Float32BufferAttribute(normals, 3));
  return merged;
}

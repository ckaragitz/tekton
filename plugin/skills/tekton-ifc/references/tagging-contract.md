# The model-tagging contract — `userData.ifc` and `meta`

This is the complete interface between a three.js model and the canonical
exporter `assets/ifc-export.js` (`toIfc(THREE, object, meta)`). Everything the
exporter knows about your building comes from (a) the scene graph, (b)
`userData.ifc` on nodes, and (c) the `meta` object (`stage.ifcMeta`). There is
no other input.

The contract is versioned: **v1** keys are the ones already in the field and
are supported forever; **v2** keys are additive. A model with only v1 keys
still exports; v2 features are on by default and controlled through `meta`.

Notation: `type` = the JavaScript type expected; `default` = what the
exporter uses if the key is absent; `effect` = what it changes in the IFC and
therefore in Revit.

---

## 1. How products are formed (read this first)

A **product** is one IFC element (one Revit element). The exporter walks the
scene graph from the root object:

1. Any node (`THREE.Group`, `Mesh`, or any `Object3D`) with `userData.ifc`
   set to an **object** starts a product. **All descendant meshes** are that
   product's body geometry — until a descendant itself has `userData.ifc`,
   which starts a nested product (its geometry belongs to the child, not the
   parent).
2. A node with `userData.ifc === false`, `userData.ifcExclude === true`,
   `userData.helper === true`, or a name matching `meta.excludeNames` is
   **skipped entirely** (it and its subtree contribute nothing).
3. Meshes with no tagged ancestor belong to an implicit **root product**
   described by the whole-file `meta` (v1 behaviour: if you tag nothing, the
   whole object is one product).
4. Meshes with `visible === false` are skipped (visibility is honoured so
   design-time toggles don't leak into the model).

Rule of thumb: **one tagged group per thing you would tag on a drawing.**

```js
const panel = new THREE.Group();
panel.name = 'panel_B-LQ1';
panel.userData.ifc = { ifcClass: 'IFCELECTRICDISTRIBUTIONBOARD', name: 'B-LQ1' };
panel.add(enclosureMesh, deadFrontMesh, doorMesh);   // all become B-LQ1's body
model.add(panel);
```

---

## 2. Node keys — `userData.ifc = { ... }` (v1)

### `ifcClass`
- **type** `string` — an IFC4 entity name, upper-case (`'IFCELECTRICDISTRIBUTIONBOARD'`).
- **default** `meta.ifcClass` if set, else `'IFCBUILDINGELEMENTPROXY'`.
- **effect** The IFC entity emitted for this product, which Revit maps to a
  **category** (Electrical Equipment, Lighting Fixtures…). A proxy imports as
  *Generic Models* — avoid for real equipment. Table:
  `references/mep-class-map.md`.
```js
userData.ifc = { ifcClass: 'IFCTRANSFORMER' };
```

### `predefinedType`
- **type** `string` — the entity's `PredefinedType` enum member without
  dots (`'DISTRIBUTIONBOARD'`, `'VOLTAGE'`, `'BRACKET'`, `'USERDEFINED'`).
- **default** `meta.predefinedType` if set, else `'NOTDEFINED'`.
- **effect** Emitted as `.<VALUE>.` on the entity; refines the subtype
  (`IFCTRANSFORMER … .VOLTAGE.`). Use `'USERDEFINED'` + `tag`/`name` when no
  member fits. Invalid members for the class are downgraded to `NOTDEFINED`
  with a console warning.
```js
userData.ifc = { ifcClass: 'IFCELECTRICDISTRIBUTIONBOARD', predefinedType: 'DISTRIBUTIONBOARD' };
```

### `name`
- **type** `string`.
- **default** the node's `.name`, else the `ifcClass` without the `IFC` prefix.
- **effect** IFC `Name` attribute → the element's name in Revit's IFC
  parameters (`IfcName`). Human-readable; keep it the equipment tag or a
  short title (`'B-HG4'`, `'XFMR-LR1'`).

### `description`
- **type** `string`. **default** none (`$`).
- **effect** IFC `Description` → Revit `IfcDescription` parameter. Free text
  (`'Panelboard, 480Y/277 V; fed from MDB via BS-FD1020'`). Non-ASCII is
  escaped automatically (`—` → `\X2\2014\X0\`).

### `tag`
- **type** `string`. **default** none.
- **effect** IFC `Tag` attribute → Revit `IfcTag`; the equipment mark /
  callout id (`'B-HG4'`). Distinct from `name`; keep both if you have them.

### `psets`
- **type** `Array<{ name: string, props: { [PropName]: TypedValue | scalar } }>`.
- **default** none.
- **effect** Each entry becomes an `IfcPropertySet` attached to the product
  via `IfcRelDefinesByProperties`. In Revit (Link IFC) every property becomes
  an **instance parameter** on the element, grouped by pset name — this is
  how panel/transformer/support schedule data reaches Revit. Property names
  are case-sensitive and should match the firm's shared parameters
  (`references/shared-parameters-mapping.md`).

`TypedValue` is `{ value, type }`; a bare scalar means `type: 'label'`
(strings) — see §3 for the type table.
```js
userData.ifc = { psets: [
  { name: 'PanelSchedule', props: {
      PanelName: 'B-HG4',                         // scalar ⇒ IfcLabel
      Voltage:   { value: 480, type: 'voltage' }, // IfcElectricVoltageMeasure
      BusRating: { value: 400, type: 'current' }, // IfcElectricCurrentMeasure
      NumberOfCircuits: { value: 42, type: 'count' },
      WorkingClearanceDepth: { value: 1.2192, type: 'length' } } },
  { name: 'Pset_ElectricDistributionBoardTypeCommon',
    props: { Reference: 'B-HG4', IsMain: { value: false, type: 'boolean' } } } ] };
```

### `typeName`
- **type** `string`. **default** none (no type object).
- **effect** Creates an `IfcXxxType` (the `Type` counterpart of `ifcClass`,
  e.g. `IfcElectricDistributionBoardType`) and links this product to it via
  `IfcRelDefinesByType`. **v2: identical `typeName` (with the same
  `ifcClass`) across nodes ⇒ ONE shared type object listing all its
  occurrences** — fixes v1, which emitted one type per element. In Revit the
  type name populates `IfcTypeName`/type identity. Make it manufacturer-style:
  `'Eaton Pow-R-Line 4 (style) — 400A MB — 42 space'`.

### `typePsets`
- **type** same shape as `psets`. **default** none.
- **effect** Property sets attached to the **type** object, once, shared by
  every occurrence. Use for manufacturer/model data
  (`Pset_ManufacturerTypeInformation { Manufacturer, ModelLabel,
  ModelReference }`) rather than per-instance data. If two nodes share a
  `typeName` but supply different `typePsets`, the first wins and the
  exporter warns.

---

## 3. Property value types — the `type` codebook

| `type` string | IFC measure emitted | JS `value` | Revit shared-param datatype it should map to |
|---|---|---|---|
| `'label'` (default for bare scalars) | `IfcLabel` | string | TEXT |
| `'text'` | `IfcText` | string (long/free text) | TEXT |
| `'identifier'` | `IfcIdentifier` | string (a code/id) | TEXT |
| `'boolean'` | `IfcBoolean` | boolean | YESNO |
| `'integer'` | `IfcInteger` | integer | INTEGER |
| `'count'` | `IfcCountMeasure` | non-negative integer | INTEGER |
| `'real'` | `IfcReal` | number (unitless) | NUMBER |
| `'length'` | `IfcLengthMeasure` (**metres**) | number | LENGTH |
| `'voltage'` | `IfcElectricVoltageMeasure` (volts) | number | ELECTRICAL_POTENTIAL |
| `'current'` | `IfcElectricCurrentMeasure` (amperes) | number | ELECTRICAL_CURRENT |
| `'power'` | `IfcPowerMeasure` (watts) | number | ELECTRICAL_POWER (or NUMBER) |
| `'area'` | `IfcAreaMeasure` (m²) | number | AREA |
| `'volume'` | `IfcVolumeMeasure` (m³) | number | VOLUME |

Rules: numbers are metres/volts/amps/watts — never feet or kVA-as-length; a
"kVA" rating is `'real'` (`RatingkVA: {value:45, type:'real'}`) unless you
convert to VA `'power'`. A bare string value is always `IfcLabel`. Do not put
units in the value (`'480Y/277 V'` as a label is fine; `Voltage` as a measure
should be the number `480`).

---

### Also accepted on `userData.ifc` (advanced overrides)

| Key | type | default | effect |
|---|---|---|---|
| `typeClass` | string | `<ifcClass>Type` when that entity exists | Override the emitted type-object entity (e.g. `'IFCELECTRICDISTRIBUTIONBOARDTYPE'`). |
| `typePredefinedType` | string | mirrors `predefinedType` | `PredefinedType` on the type object when it differs from the occurrence. |
| `objectType` | string | none | IFC `ObjectType` — the user-defined type string; set it whenever `predefinedType:'USERDEFINED'`. |
| `longName` | string | none | `LongName` on spatial products (`IFCSPACE` room name vs number). |
| `globalId` | 22-char IFC GUID string | derived (see `meta.guidSeed`) | Force a specific stable `GlobalId` for this product (advanced; must be a valid compressed GUID). |
| `instanceOf` | string | none | Explicit instancing key — see §4. |

---

## 4. Node keys — v2 additions

### `storey`
- **type** `string` (storey name) **or** `number` (index into `meta.storeys`).
- **default** `0` (the first storey; `'Level 1'` when `meta.storeys` is absent).
- **effect** The product is contained in that `IfcBuildingStorey` via
  `IfcRelContainedInSpatialStructure` (one relationship per storey). In
  Revit each storey maps to a **Level**; the element's reference level and
  its Z placement are relative to it. An unknown name warns and falls back to
  storey 0.
```js
userData.ifc = { ifcClass: 'IFCDISCRETEACCESSORY', storey: 'Mezzanine' };  // or storey: 1
```

### `userData.ifcExclude`  (sibling of `userData.ifc`, on any node)
- **type** `boolean`. **default** `false`.
- **effect** `true` ⇒ this node and its whole subtree are omitted from the
  IFC (no geometry, no product). Use for construction helpers, section
  boxes, ghost/reference geometry, and any clearance/annotation visual.
```js
clearanceGroup.userData.ifcExclude = true;
```

### `userData.ifc === false`
- **type** the literal `false` in place of the object. **effect** identical
  to `ifcExclude: true` — the node is skipped. Provided so a single key can
  both tag and un-tag.

### `userData.helper`
- **type** `boolean`. **default** `false`. **effect** `true` ⇒ skipped
  (three.js convention for grid/axes/light helpers; the exporter honours it).

### `instanceOf`
- **type** `string` (an author-chosen key). **default** none.
- **effect** Forces instancing: all products/meshes with the same
  `instanceOf` key share ONE geometry definition (`IfcRepresentationMap`)
  and each occurrence is an `IfcMappedItem` with its own transform. Use for
  repeated identical parts whose geometry objects are separately constructed
  (so their `geometry.uuid` differs). Without it the exporter still instances
  automatically when meshes share the *same* `geometry` object (`geometry.uuid`)
  and material set. Shrinks files dramatically (42 breakers, 6 panels).
```js
breaker.userData.ifc = { ifcClass: 'IFCPROTECTIVEDEVICE', instanceOf: 'breaker-1p-20a' };
```

### `ifcLOD`
- **type** `'full' | 'bbox' | 'skip'`. **default** `'full'`.
- **effect** Level of detail for THIS node's meshes: `'bbox'` replaces the
  geometry with a single box extrusion of its bounding box (great for dense
  hardware that only needs to reserve space); `'skip'` drops the geometry but
  KEEPS the product and its psets if the node is a tagged product (a tagged
  product node is never silently deleted); on an untagged mesh `'skip'` drops
  it. See also `meta.minFeatureSize`.
```js
screwCluster.userData.ifcLOD = 'skip';
denseBreakerRow.userData.ifcLOD = 'bbox';
```

---

## 5. Whole-file `meta` — v1 keys

`meta` is passed as `toIfc(THREE, object, meta)`; in a Design page it is
`stage.ifcMeta`. It supplies file/project identity and the **defaults for
the implicit root product** when no node is tagged.

| Key | type | default | effect |
|---|---|---|---|
| `name` | string | object `.name` or `'Model'` | Name of the implicit root product (only when nothing is tagged) and fallback element name. |
| `projectName` | string | `name` | `IfcProject` Name — the project title Revit shows. |
| `fileName` | string | `name` | `FILE_NAME` in the STEP header and the download filename (`<fileName>.ifc`). |
| `description` | string | none | `IfcProject`/root product Description. |
| `tag` | string | none | Root product Tag. |
| `ifcClass` | string | `'IFCBUILDINGELEMENTPROXY'` | Default `ifcClass` for the root product and any tagged node that omits it. |
| `predefinedType` | string | `'NOTDEFINED'` | Default `predefinedType`, likewise. |
| `psets` | array (as §2) | none | Psets on the root product. |
| `typeName`, `typePsets` | as §2 | none | Type object for the root product. |

---

## 6. Whole-file `meta` — v2 additions

### `geometry`
- **type** `'auto' | 'tessellation' | 'solids'`. **default** `'auto'`.
- **effect** `'auto'`: emit `IfcExtrudedAreaSolid` for meshes whose
  `geometry.type` is a known primitive (`BoxGeometry`, `CylinderGeometry`
  with equal radii, `ExtrudeGeometry`) with intact `.parameters`, and
  `IfcTriangulatedFaceSet` for everything else (merged/baked/anonymous
  `BufferGeometry`). `'tessellation'`: force the v1 all-triangles output
  (compat/regression). `'solids'`: require solids, **throw** listing the
  offending meshes — use as a lint gate. Representation identifier is
  `Body`; type `SweptSolid` (solids) / `Tessellation` (fallback).

### `storeys`
- **type** `Array<{ name: string, elevation: number /* metres */ }>`.
- **default** `[{ name: 'Level 1', elevation: 0 }]`.
- **effect** One `IfcBuildingStorey` each, aggregated under the building;
  nodes attach via `userData.ifc.storey`. Revit creates/matches a **Level**
  per storey at that elevation. Elevations are absolute metres above the
  project 0.
```js
meta.storeys = [ { name: 'Level 1', elevation: 0 }, { name: 'Mezzanine', elevation: 3.0 } ];
```

### `excludeNames`
- **type** `Array<string>` (matched as case-insensitive **prefix or
  substring** of `node.name`). **default**
  `['working_clearance', 'door_swing_clearance']`.
- **effect** Any node whose name matches is skipped (like `ifcExclude`).
  Set `[]` to disable name-based exclusion; extend it for your own helper
  naming (`['working_clearance','door_swing_clearance','_helper','ghost']`).

### `clearanceAs`
- **type** `'skip' | 'space' | 'proxy'`. **default** `'skip'`.
- **effect** What to do with clearance/keep-out groups (those matched by
  `excludeNames` **that carry `userData.clearance === true` or whose name
  contains `clearance`**): `'skip'` = omit (the volume already lives as
  `WorkingClearance*` psets on the equipment); `'space'` = emit as `IfcSpace`
  with `PredefinedType .INTERNAL.` (Revit imports it as a translucent Space
  you can toggle, useful for NEC 110.26 coordination); `'proxy'` = emit as a
  transparent `IfcBuildingElementProxy` (last resort, imports as Generic
  Model). Never `'proxy'` for panel working clearances headed to a shared
  model — it reads as phantom equipment.

### `minFeatureSize`
- **type** `number` (metres). **default** `0` (keep everything).
- **effect** Drop any **untagged** mesh whose bounding box is smaller than
  this in **all three** dimensions (screws, rivets, small hardware). Never
  drops a tagged product node. Typical: `0.01` (10 mm) for equipment models;
  `0.003` for shop-detail fidelity.

### `author`
- **type** `{ name?: string, org?: string }`. **default**
  `{ org: 'tekton-ifc' }`. **effect** `IfcPerson`/`IfcOrganization` in the
  owner history and `FILE_NAME` header (v1 left these empty).
```js
meta.author = { name: 'C. Karagitz', org: 'C. Karagitz Electric' };
```

### `guidSeed`
- **type** `string | number`. **default** none (random GUIDs per export).
- **effect** Seeds a deterministic PRNG so every `GlobalId` (the 22-char
  IFC GUID) is a stable function of the seed + the node's path in the scene
  graph. Re-exporting an unchanged model then yields identical GlobalIds, so
  Revit's re-link **updates elements in place instead of duplicating** them
  and its IFC-GUID → element tracking works. Set it once per model and never
  change it. Renaming/re-parenting a node changes that node's GlobalId (by
  design). Without a seed, GUIDs and the timestamp are the only nondeterministic
  parts of the output.
```js
meta.guidSeed = 'ddot-coolidge-area-e-v1';
```

### `site`, `building`
- **type** `site: { name?, latitude?, longitude?, elevation? }`,
  `building: { name? }`. **default** `Site` / `Building`, no georeference.
- **effect** `IfcSite` name and (if given) `RefLatitude/RefLongitude/
  RefElevation`; `IfcBuilding` name. Georeference is optional; leave it out
  rather than guessing — Revit positions the link by origin regardless.

### `instancing`, `placements`, `timestamp` (rarely needed)
- `instancing: true|false` — **default** `true` (`false` when
  `geometry:'tessellation'`). Turn off `IfcMappedItem` sharing if a
  downstream tool chokes on mapped representations (Revit does not).
- `placements: 'local'|'world'` — **default** `'local'` (real per-product
  placements). `'world'` reproduces v1's identity placements + world-baked
  coordinates; regression use only.
- `timestamp: <seconds since epoch>` — **default** now. Fixes the header /
  owner-history time; with `guidSeed` it makes the whole file byte-stable.
- `storeys[i].description` — optional per-storey description.

---

## 7. Resolution order (how defaults cascade)

For every product the exporter resolves each attribute as: **node
`userData.ifc` value → `meta` value → built-in default**. Concretely:
`ifcClass = node.ifcClass ?? meta.ifcClass ?? 'IFCBUILDINGELEMENTPROXY'`;
`predefinedType = node.predefinedType ?? meta.predefinedType ?? 'NOTDEFINED'`;
`name = node.name ?? object3d.name ?? className`; `storey = node.storey ?? 0`.
`meta.psets/typeName/typePsets` apply **only** to the implicit root product,
not to every tagged node (tagged nodes have their own).

## 8. Backward-compatibility guarantee

With `meta.geometry = 'tessellation'`, `meta.excludeNames = []`, and a
v1-only model, the output is **semantically equivalent to the v1 exporter**:
same products, classes, psets, and containment. This is the regression test
for the exporter. Every v1 tag continues to work with no edits.

## 9. Compact full example (both levels of the contract)

```js
export const ifcMeta = {
  projectName: 'DDOT Coolidge — Area E electrical room',
  fileName: 'bs-area-e-electrical-room',
  author: { org: 'Coolidge JV Electrical' },
  storeys: [ { name: 'Level 1', elevation: 0 }, { name: 'Mezzanine', elevation: 3.0 } ],
  geometry: 'auto', excludeNames: ['working_clearance', 'door_swing_clearance'],
  clearanceAs: 'skip', minFeatureSize: 0.01, guidSeed: 'coolidge-area-e-v1',
};

const panel = new THREE.Group();
panel.name = 'panel_B-LQ1';
panel.position.set(-3.78, 1.07, 2.32);              // real insertion point (metres, y-up)
panel.userData.ifc = {
  ifcClass: 'IFCELECTRICDISTRIBUTIONBOARD', predefinedType: 'DISTRIBUTIONBOARD',
  name: 'B-LQ1', tag: 'B-LQ1', storey: 'Level 1',
  typeName: 'PB-208Y120-225A-MLO-42SP',
  typePsets: [ { name: 'Pset_ManufacturerTypeInformation',
                 props: { Manufacturer: 'Eaton', ModelLabel: 'Pow-R-Line 4' } } ],
  psets: [ { name: 'PanelSchedule', props: {
    PanelName: 'B-LQ1', Voltage: { value: 208, type: 'voltage' },
    Phases: { value: 3, type: 'integer' }, Wires: { value: 4, type: 'integer' },
    BusRating: { value: 225, type: 'current' }, MainsType: 'MLO',
    NumberOfCircuits: { value: 42, type: 'count' }, Mounting: 'Surface',
    WorkingClearanceDepth: { value: 1.0668, type: 'length' } } } ],
};
```

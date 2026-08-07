// =============================================================================
//  ifc-export.js  —  tekton-ifc canonical IFC4 exporter  (v2)
// =============================================================================
//
//  A dependency-free ES module. The ONLY external is the `THREE` namespace
//  the caller passes in (three@0.184.0 in Claude Design projects). It is a
//  zero-change drop-in for Design's `<three-d-stage>` component, which does
//
//      const mod = await import('./ifc-export.js');
//      const text = mod.toIfc(THREE, object, stage.ifcMeta);   // → IFC text
//
//  and downloads `<name>.ifc`. Keep this file at `./ifc-export.js`.
//
//  ---------------------------------------------------------------------
//  TAGGING CONTRACT (v1 — 100 % supported, unchanged)
//  ---------------------------------------------------------------------
//  Any Object3D (usually a THREE.Group) carrying `userData.ifc = {...}` is
//  ONE IFC product. All descendant meshes are that product's Body geometry
//  (until another tagged node, which is its own product). If nothing in the
//  tree is tagged, the whole object is one product described by `meta`.
//
//      userData.ifc = {
//        ifcClass:       'IFCELECTRICDISTRIBUTIONBOARD',   // default IFCBUILDINGELEMENTPROXY
//        predefinedType: 'DISTRIBUTIONBOARD',            // default NOTDEFINED
//        name, description, tag,
//        psets:     [ { name, props: { PropName: {value,type} | scalar } } ],
//        typeName:  'Eaton Pow-R-Line 4 - 400A MB - 42 space',  // → shared IfcXxxType
//        typePsets: [ ...same shape... ],
//        // ---- v2 additions (all optional) ----
//        storey:   'Level 1' | 0,        // name or index into meta.storeys
//        typeClass:'IFCELECTRICDISTRIBUTIONBOARDTYPE', // override type class
//        typePredefinedType, typeDescription, objectType, longName,
//        globalId, instanceOf,
//      }
//      // property value types: boolean | integer | count | real | voltage |
//      // current | power | length | area | volume | identifier | text |
//      // label (default)
//
//  Other node flags: `userData.ifc = false` (skip node), `userData.ifcExclude
//  = true` (skip node), `userData.helper = true` (skip node), `userData.ifcLOD
//  = 'skip' | 'bbox' | 'full'` (per node/mesh level of detail).
//
//  `meta` (whole-file, also the fallback tag for an untagged object):
//      { name, projectName, fileName, description, tag, ifcClass,
//        predefinedType, psets, typeName, typePsets,                 // v1
//        // ---- v2 additions ----
//        storeys:      [ {name, elevation, description} ],  // default one 'Level 1' @ 0
//        geometry:     'auto' | 'tessellation' | 'solids',  // default 'auto'
//        instancing:   true | false,   // default true (false when geometry='tessellation')
//        placements:   'local' | 'world', // default 'local' (real placements); 'world' = v1
//        excludeNames: ['working_clearance','door_swing_clearance'], // substring match
//        clearanceAs:  'skip' | 'space' | 'proxy',      // default 'skip'
//        minFeatureSize: 0,     // metres; drop meshes smaller in EVERY dimension
//        author: {name, org}, site: {name, latitude, longitude, elevation},
//        building: {name}, description,
//        guidSeed: 'string',    // deterministic GlobalIds (stable across re-exports)
//        timestamp: 1785383780 // seconds; fixes header + owner history time
//      }
//
//  WHAT v2 EMITS
//    R1  real per-product IfcLocalPlacement from world matrices (y-up→z-up)
//    R2  IfcExtrudedAreaSolid for un-baked Box / Cylinder / ExtrudeGeometry
//        (rectangle / circle / arbitrary-profile-with-voids), tessellation
//        fallback (IfcTriangulatedFaceSet) for baked / merged geometry
//    R3  shared IfcXxxType objects deduped by (ifcClass, typeName)
//    R4  IfcRepresentationMap + IfcMappedItem for repeated geometry.uuid
//    R5  exclusions (ifc=false / ifcExclude / helper / excludeNames)
//    R6  multi-storey spatial structure, IFCSPACE aggregation
//    R7  minFeatureSize + ifcLOD detail control
//    R8  author / site / building metadata, IfcApplication 'tekton-ifc exporter'
//    R9  seeded deterministic GUIDs, valid ISO-10303-21 escaping
//    R10 entity-count report (returned by exportIfc(), appended as comment)
//
//  Coordinate convention: three.js metres, +Y up. IFC: metres, +Z up.
//  Conversion for any vector v: (x, y, z)_three → (x, -z, y)_ifc.
// =============================================================================

export const VERSION = '2.0.0';
export const APPLICATION_NAME = 'tekton-ifc exporter';
export const APPLICATION_ID = 'revit_bridge';

const DEFAULT_EXCLUDE_NAMES = ['working_clearance', 'door_swing_clearance'];

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * v1-compatible entry point: returns IFC4 STEP text.
 * @param {object} THREE   the three.js namespace (the exporter is dependency-free)
 * @param {THREE.Object3D} object  the model (Group of tagged product nodes)
 * @param {object} meta   whole-file metadata + options (see header)
 * @returns {string} IFC4 (ISO-10303-21) text
 */
export function toIfc(THREE, object, meta = {}) {
  const { text, report } = exportIfc(THREE, object, meta);
  toIfc.lastReport = report;
  if (typeof meta.onReport === 'function') meta.onReport(report);
  return text;
}
toIfc.lastReport = null;

/** v2 rich entry point: returns { text, report }. */
export function exportIfc(THREE, object, meta = {}) {
  return new Exporter(THREE, meta).run(object);
}

/** Last report from toIfc() (R10). */
export function getLastReport() {
  return toIfc.lastReport;
}

export default toIfc;

// ---------------------------------------------------------------------------
// STEP text encoding (ISO-10303-21)
// ---------------------------------------------------------------------------

/** Encode a JS string as an ISO-10303-21 string literal (with quotes). */
export function stepString(value) {
  if (value === undefined || value === null) return '$';
  const s = String(value);
  let out = "'";
  let i = 0;
  while (i < s.length) {
    const cp = s.codePointAt(i);
    if (cp === 0x27) {              // apostrophe → doubled
      out += "''"; i += 1;
    } else if (cp === 0x5c) {       // backslash → escaped
      out += '\\\\'; i += 1;
    } else if (cp >= 0x20 && cp <= 0x7e) {
      out += s[i]; i += 1;
    } else {
      // group a run of non-ASCII into one \X2\..\X0\ block (UTF-16 code units)
      let hex = '';
      while (i < s.length) {
        const c = s.charCodeAt(i);   // UTF-16 code unit (surrogates encoded as pairs)
        if (c >= 0x20 && c <= 0x7e) break;
        if (c === 0x27 || c === 0x5c) break;
        hex += c.toString(16).toUpperCase().padStart(4, '0');
        i += 1;
      }
      out += '\\X2\\' + hex + '\\X0\\';
    }
  }
  return out + "'";
}

/** STEP REAL literal (must contain a decimal point; exponent as 'E'). */
export function stepReal(n) {
  n = Number(n);
  if (!Number.isFinite(n)) n = 0;
  if (Math.abs(n) < 1e-12) return '0.';
  let s = Number(n.toPrecision(12)).toString();
  if (/[eE]/.test(s)) {
    const [m, ex] = s.split(/[eE]/);
    return (m.includes('.') ? m : m + '.') + 'E' + parseInt(ex, 10);
  }
  return s.includes('.') ? s : s + '.';
}

const stepEnum = (v) => '.' + String(v).toUpperCase().replace(/[^A-Z0-9_]/g, '') + '.';
const stepBool = (v) => (v ? '.T.' : '.F.');
const stepInt = (v) => String(Math.round(Number(v) || 0));
const ref = (id) => (id == null ? '$' : '#' + id);
const list = (items) => '(' + items.join(',') + ')';

// ---------------------------------------------------------------------------
// GUIDs — IFC base64 compression of a 128-bit value (22 chars)
// ---------------------------------------------------------------------------

const IFC_B64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_$';

export function compressGuid(bytes /* Uint8Array(16) */) {
  let n = 0n;
  for (let i = 0; i < 16; i += 1) n = (n << 8n) | BigInt(bytes[i] & 0xff);
  let s = IFC_B64[Number((n >> 126n) & 3n)];
  for (let i = 20; i >= 0; i -= 1) s += IFC_B64[Number((n >> BigInt(6 * i)) & 63n)];
  return s;
}

/** cyrb128 string hash → four 32-bit words (deterministic). */
function cyrb128(str) {
  let h1 = 1779033703, h2 = 3144134277, h3 = 1013904242, h4 = 2773480762;
  for (let i = 0; i < str.length; i += 1) {
    const k = str.charCodeAt(i);
    h1 = h2 ^ Math.imul(h1 ^ k, 597399067);
    h2 = h3 ^ Math.imul(h2 ^ k, 2869860233);
    h3 = h4 ^ Math.imul(h3 ^ k, 951274213);
    h4 = h1 ^ Math.imul(h4 ^ k, 2716044179);
  }
  h1 = Math.imul(h3 ^ (h1 >>> 18), 597399067);
  h2 = Math.imul(h4 ^ (h2 >>> 22), 2869860233);
  h3 = Math.imul(h1 ^ (h3 >>> 17), 951274213);
  h4 = Math.imul(h2 ^ (h4 >>> 19), 2716044179);
  return [(h1 ^ h2 ^ h3 ^ h4) >>> 0, (h2 ^ h1) >>> 0, (h3 ^ h1) >>> 0, (h4 ^ h1) >>> 0];
}

/**
 * GUID source. With a seed, GlobalIds are derived from a stable per-entity
 * key (so re-exporting an unchanged model reproduces the same GlobalIds —
 * essential for Revit re-link / update workflows). Without a seed they are
 * crypto-random.
 */
class GuidSource {
  constructor(seed) {
    this.seed = seed == null ? null : String(seed);
    this.used = new Set();
  }
  guid(key, explicit) {
    if (explicit && typeof explicit === 'string' && explicit.length === 22) return explicit;
    let g;
    if (this.seed !== null) {
      let salt = 0;
      do {
        const words = cyrb128(this.seed + ' ' + key + (salt ? '#' + salt : ''));
        const bytes = new Uint8Array(16);
        for (let i = 0; i < 4; i += 1) {
          bytes[i * 4] = words[i] >>> 24;
          bytes[i * 4 + 1] = (words[i] >>> 16) & 0xff;
          bytes[i * 4 + 2] = (words[i] >>> 8) & 0xff;
          bytes[i * 4 + 3] = words[i] & 0xff;
        }
        g = compressGuid(bytes);
        salt += 1;
      } while (this.used.has(g));
    } else {
      const bytes = new Uint8Array(16);
      const c = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined;
      if (c && typeof c.getRandomValues === 'function') c.getRandomValues(bytes);
      else for (let i = 0; i < 16; i += 1) bytes[i] = Math.floor(Math.random() * 256);
      g = compressGuid(bytes);
    }
    this.used.add(g);
    return g;
  }
}

// ---------------------------------------------------------------------------
// STEP writer
// ---------------------------------------------------------------------------

class StepWriter {
  constructor() {
    this.lines = [];
    this.next = 1;
    this.counts = Object.create(null);
    this.cache = new Map();
  }
  add(entity, args) {
    const id = this.next++;
    this.lines.push('#' + id + '=' + entity + '(' + args + ');');
    this.counts[entity] = (this.counts[entity] || 0) + 1;
    return id;
  }
  /** Add-or-reuse for immutable value entities (points, directions, styles…). */
  intern(key, entity, args) {
    const k = entity + '' + key;
    let id = this.cache.get(k);
    if (id === undefined) {
      id = this.add(entity, args);
      this.cache.set(k, id);
    }
    return id;
  }
  get total() { return this.next - 1; }
}

// ---------------------------------------------------------------------------
// Entity attribute signatures (occurrence / type classes that deviate
// from the standard IFC4 element signature). Everything not listed here is
// emitted with the standard signatures:
//   occurrence: (GlobalId,OwnerHistory,Name,Description,ObjectType,
//                ObjectPlacement,Representation,Tag,PredefinedType)
//   type:       (GlobalId,OwnerHistory,Name,Description,ApplicableOccurrence,
//                HasPropertySets,RepresentationMaps,Tag,ElementType,
//                PredefinedType)
// ---------------------------------------------------------------------------

// IFC4 element classes with NO PredefinedType attribute (8 attributes).
const OCC_NO_PREDEFINED = new Set([
  'IFCDISTRIBUTIONELEMENT', 'IFCDISTRIBUTIONFLOWELEMENT', 'IFCDISTRIBUTIONCONTROLELEMENT',
  'IFCFLOWCONTROLLER', 'IFCFLOWFITTING', 'IFCFLOWMOVINGDEVICE', 'IFCFLOWSEGMENT',
  'IFCFLOWSTORAGEDEVICE', 'IFCFLOWTERMINAL', 'IFCFLOWTREATMENTDEVICE',
  'IFCENERGYCONVERSIONDEVICE', 'IFCFURNISHINGELEMENT', 'IFCFEATUREELEMENT',
]);
// IFC4 type classes with NO PredefinedType attribute (9 attributes).
const TYPE_NO_PREDEFINED = new Set([
  'IFCDISTRIBUTIONELEMENTTYPE', 'IFCDISTRIBUTIONFLOWELEMENTTYPE',
  'IFCDISTRIBUTIONCONTROLELEMENTTYPE', 'IFCFLOWCONTROLLERTYPE', 'IFCFLOWFITTINGTYPE',
  'IFCFLOWMOVINGDEVICETYPE', 'IFCFLOWSEGMENTTYPE', 'IFCFLOWSTORAGEDEVICETYPE',
  'IFCFLOWTERMINALTYPE', 'IFCFLOWTREATMENTDEVICETYPE', 'IFCENERGYCONVERSIONDEVICETYPE',
  'IFCELEMENTTYPE', 'IFCBUILDINGELEMENTTYPE', 'IFCELEMENTCOMPONENTTYPE',
  'IFCFURNISHINGELEMENTTYPE', 'IFCSPATIALELEMENTTYPE', 'IFCSPATIALSTRUCTUREELEMENTTYPE',
]);

// ---------------------------------------------------------------------------
// The exporter
// ---------------------------------------------------------------------------

class Exporter {
  constructor(THREE, meta) {
    this.THREE = THREE;
    this.meta = meta || {};
    this.opt = this._normalizeMeta(this.meta);
    this.w = new StepWriter();
    this.guids = new GuidSource(this.opt.guidSeed);
    this.warnings = [];
    this.report = {
      version: VERSION,
      geometry: this.opt.geometry,
      instancing: this.opt.instancing,
      products: 0, spaces: 0, elements: 0,
      types: 0, mappedItems: 0, representationMaps: 0,
      extrudedSolids: 0, profilesWithVoids: 0, faceSets: 0,
      excluded: [], droppedByFeatureSize: 0, lodSkipped: 0,
      storeys: [], entityCounts: {}, totalEntities: 0, bytes: 0,
      warnings: this.warnings,
    };
    // caches
    this._styleCache = new Map();
    this._maps = new Map();          // instance key → { mapId }
    this._singleSeq = 0;             // deterministic ids for single-use maps
    this._excludedNodes = new Set(); // dedupe report.excluded
  }

  // ------------------------------------------------------------------------
  // meta normalisation
  // ------------------------------------------------------------------------
  _normalizeMeta(meta) {
    const geometry = ['auto', 'tessellation', 'solids'].includes(meta.geometry)
      ? meta.geometry : 'auto';
    let storeys = Array.isArray(meta.storeys) && meta.storeys.length
      ? meta.storeys.map((s, i) => ({
          name: (s && s.name != null) ? String(s.name) : `Level ${i + 1}`,
          elevation: Number((s && s.elevation) || 0),
          description: s && s.description,
        }))
      : [{ name: 'Level 1', elevation: 0 }];
    return {
      geometry,
      instancing: typeof meta.instancing === 'boolean'
        ? meta.instancing : geometry !== 'tessellation',
      placements: meta.placements === 'world' ? 'world' : 'local',
      storeys,
      excludeNames: Array.isArray(meta.excludeNames)
        ? meta.excludeNames.map(String) : DEFAULT_EXCLUDE_NAMES.slice(),
      clearanceAs: ['skip', 'space', 'proxy'].includes(meta.clearanceAs)
        ? meta.clearanceAs : 'skip',
      minFeatureSize: Number(meta.minFeatureSize) > 0 ? Number(meta.minFeatureSize) : 0,
      guidSeed: meta.guidSeed != null ? meta.guidSeed : null,
      timestamp: Number.isFinite(meta.timestamp)
        ? Math.floor(Number(meta.timestamp))
        : Math.floor(Date.now() / 1000),
      curveSegments: Number.isFinite(meta.curveSegments) ? Math.max(3, Math.floor(meta.curveSegments)) : 24,
      orphans: meta.orphans === 'skip' ? 'skip' : 'proxy',
      precision: 1e-5,
    };
  }

  // ------------------------------------------------------------------------
  // run
  // ------------------------------------------------------------------------
  run(object) {
    const THREE = this.THREE;
    if (!THREE || !THREE.Matrix4) throw new Error('toIfc: pass the THREE namespace as first argument');
    if (!object || !object.isObject3D) throw new Error('toIfc: object must be a THREE.Object3D');

    object.updateMatrixWorld(true);

    // 1. discover products (tagging contract + exclusions)
    const products = this._collectProducts(object);
    this._productNodes = new Set(products.filter((p) => !p.orphan).map((p) => p.node));

    // 2. gather geometry items per product (meshes → items in local frame)
    for (const p of products) this._gatherItems(p);

    // 3. instancing analysis (R4): count identical (geometry.uuid, style, kind)
    this._analyseInstancing(products);

    // 4. header / project structure entities
    this._emitHeader(object);

    // 5. products
    for (const p of products) this._emitProduct(p);

    // 6. relationships (containment, aggregation, types, psets)
    this._emitRelationships(products);

    // 7. assemble text
    return this._assemble(products);
  }

  // ------------------------------------------------------------------------
  // Traversal — the tagging contract
  // ------------------------------------------------------------------------
  _isExcludedNode(node) {
    const ud = node.userData || {};
    if (ud.ifc === false) return 'ifc=false';
    if (ud.ifcExclude === true) return 'ifcExclude';
    if (ud.helper === true) return 'helper';
    // ifcLOD='skip' drops UNTAGGED geometry nodes; a tagged product node is
    // never dropped (its geometry is skipped instead — see _gatherItems).
    if (ud.ifcLOD === 'skip' && !this._tagOf(node)) return 'ifcLOD=skip';
    const name = (node.name || '').toLowerCase();
    if (name) {
      for (const pat of this.opt.excludeNames) {
        if (pat && name.includes(String(pat).toLowerCase())) return `excludeName:${pat}`;
      }
    }
    return null;
  }

  _isClearanceNode(node) {
    const name = (node.name || '').toLowerCase();
    if (!name) return false;
    for (const pat of this.opt.excludeNames) {
      if (pat && name.includes(String(pat).toLowerCase())) return true;
    }
    return false;
  }

  _tagOf(node) {
    const ud = node.userData || {};
    const t = ud.ifc;
    if (!t || t === true) return t === true ? {} : null;
    if (typeof t === 'object') return t;
    return null;
  }

  _collectProducts(root) {
    const products = [];
    const meta = this.meta;
    let anyTagged = false;
    root.traverse((n) => { if (this._tagOf(n)) anyTagged = true; });

    const pathOf = (node) => {
      const parts = [];
      let cur = node;
      while (cur && cur !== root.parent) {
        parts.push((cur.name || cur.type || 'node') + (cur.parent ? ':' + cur.parent.children.indexOf(cur) : ''));
        if (cur === root) break;
        cur = cur.parent;
      }
      return parts.reverse().join('/');
    };

    const makeProduct = (node, tag, meshRoots, extra = {}) => ({
      node,
      tag: this._mergedTag(tag, node, extra),
      key: pathOf(node),
      meshRoots, // roots to gather meshes from
      items: [],
      ...extra,
    });

    if (!anyTagged) {
      // whole object is one product described by meta
      const tag = {
        ifcClass: meta.ifcClass, predefinedType: meta.predefinedType,
        name: meta.name || root.name, description: meta.description, tag: meta.tag,
        psets: meta.psets, typeName: meta.typeName, typePsets: meta.typePsets,
      };
      products.push(makeProduct(root, tag, [root]));
      this.report.products = 1;
      return products;
    }

    const orphanMeshes = [];
    const walk = (node) => {
      const excl = node === root ? null : this._isExcludedNode(node);
      if (excl) {
        // clearance volumes optionally exported as spaces / proxies
        if (this._isClearanceNode(node) && this.opt.clearanceAs !== 'skip') {
          const asSpace = this.opt.clearanceAs === 'space';
          products.push(makeProduct(node, {
            ifcClass: asSpace ? 'IFCSPACE' : 'IFCBUILDINGELEMENTPROXY',
            predefinedType: asSpace ? 'INTERNAL' : 'NOTDEFINED',
            name: node.name, description: 'Clearance / keep-out volume',
          }, [node], { clearance: true }));
        } else {
          this._noteExcluded(node, excl);
        }
        return; // do not descend
      }
      const tag = this._tagOf(node);
      if (tag) {
        products.push(makeProduct(node, tag, [node]));
        // descend to find NESTED products; the product itself gathers only
        // meshes that do not belong to a nested product (handled in _gatherItems)
        for (const c of node.children) walk(c);
        return;
      }
      // untagged node: geometry belongs to nearest tagged ancestor; if there
      // is none it is an orphan.
      if (node.isMesh || node.isInstancedMesh) {
        if (!this._nearestProduct(node, products)) orphanMeshes.push(node);
      }
      for (const c of node.children) walk(c);
    };
    walk(root);

    if (orphanMeshes.length && this.opt.orphans !== 'skip') {
      const tag = {
        ifcClass: meta.ifcClass || 'IFCBUILDINGELEMENTPROXY',
        predefinedType: meta.predefinedType,
        name: meta.name || root.name || 'Model geometry',
        description: meta.description, tag: meta.tag,
        psets: meta.psets, typeName: meta.typeName, typePsets: meta.typePsets,
      };
      const p = makeProduct(root, tag, orphanMeshes, { orphan: true });
      p.meshList = orphanMeshes;
      products.push(p);
    }
    this.report.products = products.length;
    return products;
  }

  _noteExcluded(node, reason) {
    if (this._excludedNodes.has(node)) return;
    this._excludedNodes.add(node);
    this.report.excluded.push({ name: node.name || node.type, reason });
  }

  _nearestProduct(node, products) {
    let cur = node.parent;
    const set = new Set(products.map((p) => p.node));
    while (cur) {
      if (set.has(cur)) return cur;
      cur = cur.parent;
    }
    return null;
  }

  _mergedTag(tag, node, extra) {
    const meta = this.meta;
    const t = tag || {};
    const isSpace = String(t.ifcClass || '').toUpperCase() === 'IFCSPACE';
    const ifcClass = String(t.ifcClass || 'IFCBUILDINGELEMENTPROXY').toUpperCase();
    return {
      ifcClass,
      isSpace,
      predefinedType: String(t.predefinedType || (isSpace ? 'INTERNAL' : 'NOTDEFINED')).toUpperCase(),
      name: t.name != null ? String(t.name) : (node.name || (extra.clearance ? 'clearance' : ifcClass)),
      description: t.description != null ? String(t.description) : null,
      tag: t.tag != null ? String(t.tag) : null,
      objectType: t.objectType != null ? String(t.objectType) : null,
      longName: t.longName != null ? String(t.longName) : null,
      psets: Array.isArray(t.psets) ? t.psets : [],
      typeName: t.typeName != null ? String(t.typeName) : null,
      typePsets: Array.isArray(t.typePsets) ? t.typePsets : [],
      typeClass: t.typeClass ? String(t.typeClass).toUpperCase() : null,
      typePredefinedType: t.typePredefinedType ? String(t.typePredefinedType).toUpperCase() : null,
      typeDescription: t.typeDescription != null ? String(t.typeDescription) : null,
      storey: t.storey != null ? t.storey : (meta.storey != null ? meta.storey : null),
      globalId: typeof t.globalId === 'string' ? t.globalId : null,
      lod: node.userData && node.userData.ifcLOD ? node.userData.ifcLOD : null,
    };
  }

  // ------------------------------------------------------------------------
  // Product frame + mesh gathering
  // ------------------------------------------------------------------------
  _productFrame(product) {
    const THREE = this.THREE;
    const world = product.node.matrixWorld.clone();
    if (this.opt.placements === 'world') {
      // v1 compatibility: identity placement, geometry in world coords
      product.frameWorld = new THREE.Matrix4();
      product.frameInv = new THREE.Matrix4();
      product.pos = new THREE.Vector3();
      product.axisX = new THREE.Vector3(1, 0, 0);
      product.axisY = new THREE.Vector3(0, 1, 0);
      product.axisZ = new THREE.Vector3(0, 0, 1);
      return;
    }
    const pos = new THREE.Vector3(), quat = new THREE.Quaternion(), scl = new THREE.Vector3();
    world.decompose(pos, quat, scl);
    // frame = translation + rotation only (scale folded into local geometry)
    const frame = new THREE.Matrix4().compose(pos, quat, new THREE.Vector3(1, 1, 1));
    product.frameWorld = frame;
    product.frameInv = frame.clone().invert();
    product.pos = pos;
    product.axisX = new THREE.Vector3(1, 0, 0).applyQuaternion(quat).normalize();
    product.axisY = new THREE.Vector3(0, 1, 0).applyQuaternion(quat).normalize();
    product.axisZ = new THREE.Vector3(0, 0, 1).applyQuaternion(quat).normalize();
  }

  _gatherItems(product) {
    const THREE = this.THREE;
    this._productFrame(product);
    const items = [];

    const addMesh = (mesh, matrixWorld) => {
      const geometry = mesh.geometry;
      if (!geometry || !geometry.isBufferGeometry) return;
      if (!geometry.attributes || !geometry.attributes.position) return;
      // per-mesh LOD
      const lod = (mesh.userData && mesh.userData.ifcLOD) || product.tag.lod || 'full';
      if (lod === 'skip') { this.report.lodSkipped += 1; return; }
      // minFeatureSize (R7): drop meshes smaller than threshold in EVERY dim
      if (this.opt.minFeatureSize > 0) {
        const size = this._worldBoxSize(mesh, matrixWorld);
        if (size.x < this.opt.minFeatureSize && size.y < this.opt.minFeatureSize && size.z < this.opt.minFeatureSize) {
          this.report.droppedByFeatureSize += 1;
          return;
        }
      }
      const matrixLocal = product.frameInv.clone().multiply(matrixWorld);
      const material = Array.isArray(mesh.material) ? mesh.material[0] : mesh.material;
      items.push({ mesh, geometry, matrixLocal, material, name: mesh.name || '', lod });
    };

    const visit = (node, isRoot) => {
      if (!isRoot) {
        // nested product (tagged node or a clearance emitted as space/proxy)?
        // then its meshes belong to it, not us
        if (this._tagOf(node) || (this._productNodes && this._productNodes.has(node))) return;
        const excl = this._isExcludedNode(node);
        if (excl) {
          this._noteExcluded(node, excl);
          return;
        }
      }
      if (node.isInstancedMesh && node.geometry) {
        const m = new THREE.Matrix4();
        for (let i = 0; i < node.count; i += 1) {
          node.getMatrixAt(i, m);
          addMesh(node, node.matrixWorld.clone().multiply(m));
        }
      } else if (node.isMesh && node.geometry) {
        addMesh(node, node.matrixWorld);
      }
      for (const c of node.children) visit(c, false);
    };

    if (product.orphan) {
      for (const mesh of product.meshList) addMesh(mesh, mesh.matrixWorld);
    } else {
      // a tagged Mesh node contributes its own geometry too
      visit(product.node, true);
    }
    product.items = items;
  }

  _worldBoxSize(mesh, matrixWorld) {
    const THREE = this.THREE;
    const g = mesh.geometry;
    if (!g.boundingBox) g.computeBoundingBox();
    const box = g.boundingBox.clone().applyMatrix4(matrixWorld);
    return box.getSize(new THREE.Vector3());
  }

  // ------------------------------------------------------------------------
  // Geometry classification (R2) and instancing analysis (R4)
  // ------------------------------------------------------------------------
  _classify(item) {
    const mode = this.opt.geometry;
    const g = item.geometry;
    if (mode === 'tessellation') return 'tess';   // force v1 geometry (bbox LOD ignored)
    if (item.lod === 'bbox') return 'bbox';
    const p = g.parameters;
    let kind = null;
    if (p && g.type === 'BoxGeometry' && this._boxIntact(g, p)) kind = 'box';
    else if (p && g.type === 'CylinderGeometry' && this._cylinderIntact(g, p)) kind = 'cylinder';
    else if (p && g.type === 'ExtrudeGeometry' && this._extrudeIntact(g, p)) kind = 'extrude';
    if (!kind) {
      if (mode === 'solids') {
        throw new Error(`toIfc: geometry mode 'solids' but mesh "${item.name || item.mesh.uuid}" ` +
          `(${g.type || 'BufferGeometry'}) has no intact parametric definition ` +
          `(baked / merged BufferGeometry cannot be expressed as an IfcExtrudedAreaSolid)`);
      }
      kind = 'tess';
    }
    return kind;
  }

  _bbox(g) {
    if (!g.boundingBox) g.computeBoundingBox();
    return g.boundingBox;
  }

  /** true if the box's vertices still match its parameters (not baked). */
  _boxIntact(g, p) {
    if (!(p.width > 0 && p.height > 0 && p.depth > 0)) return false;
    const b = this._bbox(g); const t = 1e-4;
    return Math.abs(b.min.x + p.width / 2) < t && Math.abs(b.max.x - p.width / 2) < t &&
           Math.abs(b.min.y + p.height / 2) < t && Math.abs(b.max.y - p.height / 2) < t &&
           Math.abs(b.min.z + p.depth / 2) < t && Math.abs(b.max.z - p.depth / 2) < t;
  }

  _cylinderIntact(g, p) {
    const rt = Number(p.radiusTop), rb = Number(p.radiusBottom), h = Number(p.height);
    if (!(rt > 0 && h > 0) || Math.abs(rt - rb) > 1e-9) return false;
    if (p.openEnded) return false;
    const theta = p.thetaLength == null ? Math.PI * 2 : Number(p.thetaLength);
    if (Math.abs(theta - Math.PI * 2) > 1e-6) return false;
    const b = this._bbox(g); const t = 1e-4;
    return Math.abs(b.min.y + h / 2) < t && Math.abs(b.max.y - h / 2) < t &&
           b.max.x <= rt + t && b.min.x >= -rt - t &&
           b.max.z <= rt + t && b.min.z >= -rt - t &&
           b.max.x > rt * 0.9; // vertices actually reach the radius
  }

  _extrudeIntact(g, p) {
    const shapes = p.shapes ? (Array.isArray(p.shapes) ? p.shapes : [p.shapes]) : null;
    if (!shapes || !shapes.length) return false;
    for (const s of shapes) if (!s || typeof s.extractPoints !== 'function') return false;
    const o = p.options || {};
    if (o.bevelEnabled) return false;               // bevels are not a plain extrusion
    if (o.extrudePath) return false;                 // path sweeps not supported → tess
    const depth = Number(o.depth != null ? o.depth : (o.amount != null ? o.amount : 1));
    if (!(depth > 0)) return false;
    const b = this._bbox(g); const t = 1e-4;
    return Math.abs(b.min.z) < t && Math.abs(b.max.z - depth) < t;
  }

  _styleKeyOf(material) {
    if (!material) return 'default';
    const c = material.color;
    const col = c ? `${c.r.toFixed(4)},${c.g.toFixed(4)},${c.b.toFixed(4)}` : 'nocolor';
    const op = material.transparent ? Number(material.opacity).toFixed(3) : '1';
    return `${material.name || ''}|${col}|${op}`;
  }

  /**
   * Content key of a geometry. Identical parametric primitives (even if they
   * are distinct objects) map to the same key, so repeated identical parts
   * are instanced; anonymous/baked BufferGeometry falls back to its uuid
   * (share the geometry OBJECT to instance those).
   */
  _geomKey(g) {
    if (!this._geomKeyCache) this._geomKeyCache = new WeakMap();
    let k = this._geomKeyCache.get(g);
    if (k !== undefined) return k;
    const p = g.parameters;
    if (p && g.type === 'BoxGeometry') {
      k = `box:${p.width},${p.height},${p.depth}`;
    } else if (p && g.type === 'CylinderGeometry') {
      k = `cyl:${p.radiusTop},${p.radiusBottom},${p.height},${p.radialSegments},${p.heightSegments},` +
          `${!!p.openEnded},${p.thetaStart || 0},${p.thetaLength == null ? 6.2832 : Number(p.thetaLength).toFixed(4)}`;
    } else if (p && g.type === 'ExtrudeGeometry' && p.shapes) {
      const shapes = Array.isArray(p.shapes) ? p.shapes : [p.shapes];
      const o = p.options || {};
      const r = (n) => Math.round(Number(n) * 1e6) / 1e6;
      let s = `ext:${r(o.depth != null ? o.depth : (o.amount != null ? o.amount : 1))},${!!o.bevelEnabled}:`;
      for (const sh of shapes) {
        if (typeof sh.extractPoints !== 'function') { s += g.uuid; break; }
        const pts = sh.extractPoints(this.opt.curveSegments);
        s += pts.shape.map((v) => `${r(v.x)},${r(v.y)}`).join(';');
        for (const h of pts.holes || []) s += '/h:' + h.map((v) => `${r(v.x)},${r(v.y)}`).join(';');
        s += '|';
      }
      k = s;
    } else {
      k = `geom:${g.uuid}`;
    }
    this._geomKeyCache.set(g, k);
    return k;
  }

  _itemKey(it) {
    return `${this._geomKey(it.geometry)}|${this._styleKeyOf(it.material)}|${it.kind}`;
  }

  /** Signature of a whole product body: geometry keys + local matrices. */
  _bodySignature(product) {
    const r = (n) => (Math.abs(n) < 1e-9 ? 0 : Math.round(n * 1e6) / 1e6);
    return product.items.map((it) =>
      this._itemKey(it) + '@' + it.matrixLocal.elements.map(r).join(',')).join('#');
  }

  _analyseInstancing(products) {
    // classify every item first
    for (const p of products) for (const it of p.items) it.kind = this._classify(it);
    if (!this.opt.instancing) {
      for (const p of products) for (const it of p.items) it.instanceKey = null;
      return;
    }
    // (a) ASSEMBLY-level instancing: products with an identical body share
    //     one IfcRepresentationMap (the canonical IFC type-geometry pattern:
    //     the map is also attached to the shared IfcXxxType.RepresentationMaps).
    const groups = new Map();
    for (const p of products) {
      if (!p.items.length) continue;
      const sig = this._bodySignature(p);
      let g = groups.get(sig);
      if (!g) { g = { members: [], mapId: null, signature: sig }; groups.set(sig, g); }
      g.members.push(p);
    }
    this._assemblyGroups = [];
    for (const g of groups.values()) {
      if (g.members.length >= 2) {
        for (const p of g.members) p.assemblyGroup = g;
        this._assemblyGroups.push(g);
      }
    }
    // (b) MESH-level instancing: count identical (geometry, style, kind)
    //     across the UNIQUE bodies (a shared assembly is emitted once).
    const counts = new Map();
    const seen = new Set();
    for (const p of products) {
      if (p.assemblyGroup) {
        if (seen.has(p.assemblyGroup)) continue;
        seen.add(p.assemblyGroup);
      }
      for (const it of p.items) {
        if (it.kind === 'bbox') continue;             // bbox LOD is per-mesh; not instanced
        const key = this._itemKey(it);
        counts.set(key, (counts.get(key) || 0) + 1);
      }
    }
    this._instanceCounts = counts;
    for (const p of products) {
      for (const it of p.items) {
        if (it.kind === 'bbox') { it.instanceKey = null; continue; }
        const key = this._itemKey(it);
        it.instanceKey = (counts.get(key) || 0) >= 2 ? key : null;
      }
    }
  }

  // ------------------------------------------------------------------------
  // Coordinate conversion helpers
  // ------------------------------------------------------------------------
  /** three (x,y,z) → IFC (x,-z,y) as array of 3 numbers. */
  _c(v) { return [v.x, -v.z, v.y]; }

  _pt3(a) {
    const s = a.map(stepReal).join(',');
    return this.w.intern(s, 'IFCCARTESIANPOINT', '(' + s + ')');
  }
  _pt2(x, y) {
    const s = stepReal(x) + ',' + stepReal(y);
    return this.w.intern(s, 'IFCCARTESIANPOINT', '(' + s + ')');
  }
  _dir3(a) {
    // normalise
    const len = Math.hypot(a[0], a[1], a[2]) || 1;
    const n = [a[0] / len, a[1] / len, a[2] / len];
    const s = n.map(stepReal).join(',');
    return this.w.intern(s, 'IFCDIRECTION', '(' + s + ')');
  }
  _axis3(loc, axisZ, refX) {
    const l = this._pt3(loc);
    const z = axisZ ? this._dir3(axisZ) : null;
    const x = refX ? this._dir3(refX) : null;
    const key = `${l}|${z}|${x}`;
    return this.w.intern(key, 'IFCAXIS2PLACEMENT3D', `${ref(l)},${ref(z)},${ref(x)}`);
  }
  _identityAxis3() {
    return this._axis3([0, 0, 0], null, null);
  }

  /** Decompose a THREE matrix into {pos, mx, my, mz (unit), sx, sy, sz}. */
  _decompose(m) {
    const THREE = this.THREE;
    const pos = new THREE.Vector3(), q = new THREE.Quaternion(), s = new THREE.Vector3();
    m.decompose(pos, q, s);
    const mx = new THREE.Vector3(1, 0, 0).applyQuaternion(q).normalize();
    const my = new THREE.Vector3(0, 1, 0).applyQuaternion(q).normalize();
    const mz = new THREE.Vector3(0, 0, 1).applyQuaternion(q).normalize();
    return { pos, mx, my, mz, sx: s.x, sy: s.y, sz: s.z, det: m.determinant() };
  }

  // ------------------------------------------------------------------------
  // Header entities
  // ------------------------------------------------------------------------
  _emitHeader(object) {
    const w = this.w, meta = this.meta, opt = this.opt;
    const author = meta.author || {};
    const authorName = author.name != null ? String(author.name) : '';
    const orgName = author.org != null ? String(author.org) : (author.organization ? String(author.organization) : 'tekton-ifc');

    this.projectName = String(meta.projectName || meta.name || object.name || 'Untitled project');
    this.fileName = String(meta.fileName || this.projectName).replace(/[^\w.-]+/g, '-').replace(/^-+|-+$/g, '') || 'model';

    const person = w.add('IFCPERSON', `$,$,${stepString(authorName)},$,$,$,$,$`);
    const org = w.add('IFCORGANIZATION', `$,${stepString(orgName)},$,$,$`);
    const pao = w.add('IFCPERSONANDORGANIZATION', `${ref(person)},${ref(org)},$`);
    const appOrg = w.add('IFCORGANIZATION', `$,'tekton-ifc',$,$,$`);
    const app = w.add('IFCAPPLICATION', `${ref(appOrg)},${stepString(VERSION)},${stepString(APPLICATION_NAME)},${stepString(APPLICATION_ID)}`);
    this.ownerHistory = w.add('IFCOWNERHISTORY', `${ref(pao)},${ref(app)},$,.NOCHANGE.,$,$,$,${stepInt(opt.timestamp)}`);

    // world coordinate system
    const origin = this._pt3([0, 0, 0]);
    const zdir = this._dir3([0, 0, 1]);
    const xdir = this._dir3([1, 0, 0]);
    this.wcs = w.add('IFCAXIS2PLACEMENT3D', `${ref(origin)},${ref(zdir)},${ref(xdir)}`);
    this.context = w.add('IFCGEOMETRICREPRESENTATIONCONTEXT', `$,'Model',3,${stepReal(opt.precision)},${ref(this.wcs)},$`);
    this.bodyContext = w.add('IFCGEOMETRICREPRESENTATIONSUBCONTEXT', `'Body','Model',*,*,*,*,${ref(this.context)},$,.MODEL_VIEW.,$`);

    // units — SI metres + electrical units
    const uLen = w.add('IFCSIUNIT', '*,.LENGTHUNIT.,$,.METRE.');
    const uArea = w.add('IFCSIUNIT', '*,.AREAUNIT.,$,.SQUARE_METRE.');
    const uVol = w.add('IFCSIUNIT', '*,.VOLUMEUNIT.,$,.CUBIC_METRE.');
    const uAng = w.add('IFCSIUNIT', '*,.PLANEANGLEUNIT.,$,.RADIAN.');
    const uV = w.add('IFCSIUNIT', '*,.ELECTRICVOLTAGEUNIT.,$,.VOLT.');
    const uA = w.add('IFCSIUNIT', '*,.ELECTRICCURRENTUNIT.,$,.AMPERE.');
    const uW = w.add('IFCSIUNIT', '*,.POWERUNIT.,$,.WATT.');
    const uHz = w.add('IFCSIUNIT', '*,.FREQUENCYUNIT.,$,.HERTZ.');
    const units = w.add('IFCUNITASSIGNMENT', list([uLen, uArea, uVol, uAng, uV, uA, uW, uHz].map(ref)));

    // project
    this.project = w.add('IFCPROJECT',
      `${stepString(this.guids.guid('project'))},${ref(this.ownerHistory)},${stepString(this.projectName)},` +
      `${stepString(meta.description)},$,$,$,(${ref(this.context)}),${ref(units)}`);

    // site
    const site = meta.site || {};
    const sitePlacement = w.add('IFCLOCALPLACEMENT', `$,${ref(this.wcs)}`);
    const lat = Number.isFinite(site.latitude) ? this._compoundAngle(site.latitude) : '$';
    const lon = Number.isFinite(site.longitude) ? this._compoundAngle(site.longitude) : '$';
    const elev = Number.isFinite(site.elevation) ? stepReal(site.elevation) : '$';
    this.site = w.add('IFCSITE',
      `${stepString(this.guids.guid('site'))},${ref(this.ownerHistory)},${stepString(site.name || 'Site')},` +
      `${stepString(site.description)},$,${ref(sitePlacement)},$,$,.ELEMENT.,${lat},${lon},${elev},$,$`);

    // building
    const bldg = meta.building || {};
    const bldgPlacement = w.add('IFCLOCALPLACEMENT', `${ref(sitePlacement)},${ref(this.wcs)}`);
    this.bldgPlacement = bldgPlacement;
    this.building = w.add('IFCBUILDING',
      `${stepString(this.guids.guid('building'))},${ref(this.ownerHistory)},${stepString(bldg.name || 'Building')},` +
      `${stepString(bldg.description)},$,${ref(bldgPlacement)},$,$,.ELEMENT.,$,$,$`);

    // storeys
    this.storeys = opt.storeys.map((s, i) => {
      const loc = this._axis3([0, 0, s.elevation], null, null);
      const lp = w.add('IFCLOCALPLACEMENT', `${ref(bldgPlacement)},${ref(loc)}`);
      const id = w.add('IFCBUILDINGSTOREY',
        `${stepString(this.guids.guid('storey:' + s.name))},${ref(this.ownerHistory)},${stepString(s.name)},` +
        `${stepString(s.description)},$,${ref(lp)},$,$,.ELEMENT.,${stepReal(s.elevation)}`);
      this.report.storeys.push({ name: s.name, elevation: s.elevation });
      return { ...s, id, placement: lp, contained: [], spaces: [] };
    });

    // aggregation project → site → building → storeys
    w.add('IFCRELAGGREGATES', `${stepString(this.guids.guid('rel:project-site'))},${ref(this.ownerHistory)},$,$,${ref(this.project)},(${ref(this.site)})`);
    w.add('IFCRELAGGREGATES', `${stepString(this.guids.guid('rel:site-building'))},${ref(this.ownerHistory)},$,$,${ref(this.site)},(${ref(this.building)})`);
    w.add('IFCRELAGGREGATES', `${stepString(this.guids.guid('rel:building-storeys'))},${ref(this.ownerHistory)},$,$,${ref(this.building)},` +
      list(this.storeys.map((s) => ref(s.id))));
  }

  _compoundAngle(deg) {
    const sign = deg < 0 ? -1 : 1;
    const a = Math.abs(Number(deg));
    const d = Math.floor(a);
    const mf = (a - d) * 60;
    const m = Math.floor(mf);
    const sf = (mf - m) * 60;
    const s = Math.floor(sf);
    const micro = Math.round((sf - s) * 1e6);
    return `(${sign * d},${sign * m},${sign * s},${sign * micro})`;
  }

  // ------------------------------------------------------------------------
  // Storey selection (R6)
  // ------------------------------------------------------------------------
  _pickStorey(product) {
    const sel = product.tag.storey;
    if (typeof sel === 'number' && this.storeys[sel]) return this.storeys[sel];
    if (typeof sel === 'string') {
      const byName = this.storeys.find((s) => s.name.toLowerCase() === sel.toLowerCase());
      if (byName) return byName;
      const idx = Number(sel);
      if (Number.isInteger(idx) && this.storeys[idx]) return this.storeys[idx];
      this.warnings.push(`product "${product.tag.name}": unknown storey "${sel}", inferring by elevation`);
    }
    // infer: highest storey whose elevation <= node world elevation (+eps)
    const worldY = product.node.matrixWorld.elements[13];
    let best = this.storeys[0];
    for (const s of this.storeys) {
      if (s.elevation <= worldY + 1e-3 && s.elevation >= best.elevation) best = s;
    }
    // if node is below every storey, choose the lowest
    let lowest = this.storeys[0];
    for (const s of this.storeys) if (s.elevation < lowest.elevation) lowest = s;
    if (worldY + 1e-3 < lowest.elevation) best = lowest;
    return best;
  }

  // ------------------------------------------------------------------------
  // Product emission
  // ------------------------------------------------------------------------
  _emitProduct(product) {
    const w = this.w;
    const tag = product.tag;
    const storey = this._pickStorey(product);
    product.storey = storey;

    // R1 — placement relative to the storey placement
    let placement;
    if (this.opt.placements === 'world') {
      // v1 compatibility: identity placement (relative to the building, whose
      // origin is the world origin); geometry stays in world coordinates.
      placement = w.add('IFCLOCALPLACEMENT', `${ref(this.bldgPlacement)},${ref(this._identityAxis3())}`);
    } else {
      const loc = this._c(product.pos); loc[2] -= storey.elevation;
      const axisZ = this._c(product.axisY);   // node local +Y (up) → IFC z axis
      const refX = this._c(product.axisX);    // node local +X → IFC x axis
      const isIdentityRot =
        Math.abs(axisZ[0]) < 1e-9 && Math.abs(axisZ[1]) < 1e-9 && Math.abs(axisZ[2] - 1) < 1e-9 &&
        Math.abs(refX[0] - 1) < 1e-9 && Math.abs(refX[1]) < 1e-9 && Math.abs(refX[2]) < 1e-9;
      const a2p = isIdentityRot ? this._axis3(loc, null, null) : this._axis3(loc, axisZ, refX);
      placement = w.add('IFCLOCALPLACEMENT', `${ref(storey.placement)},${ref(a2p)}`);
    }

    // Body representation. Assembly-instanced products (identical bodies)
    // share ONE IfcProductDefinitionShape (legal in IFC4: ShapeOfProduct is a
    // SET) whose Body is a single IfcMappedItem onto the shared map.
    let productShape = '$';
    const group = product.assemblyGroup;
    if (group && group.shapeId != null) {
      productShape = ref(group.shapeId);
    } else {
      const repItems = this._emitBodyItems(product);
      if (repItems.items.length) {
        const shapeRep = w.add('IFCSHAPEREPRESENTATION',
          `${ref(this.bodyContext)},'Body',${stepString(repItems.type)},${list(repItems.items.map(ref))}`);
        const pds = w.add('IFCPRODUCTDEFINITIONSHAPE', `$,$,(${ref(shapeRep)})`);
        productShape = ref(pds);
        if (group) group.shapeId = pds;
      }
    }

    // the product entity itself
    const guid = this.guids.guid('product:' + product.key, tag.globalId);
    let id;
    if (tag.isSpace) {
      // IfcSpace: (…, LongName, CompositionType, PredefinedType, ElevationWithFlooring)
      const pd = ['INTERNAL', 'EXTERNAL', 'GFA', 'PARKING', 'SPACE', 'USERDEFINED', 'NOTDEFINED']
        .includes(tag.predefinedType) ? tag.predefinedType : 'INTERNAL';
      id = w.add('IFCSPACE',
        `${stepString(guid)},${ref(this.ownerHistory)},${stepString(tag.name)},${stepString(tag.description)},` +
        `${stepString(tag.objectType)},${ref(placement)},${productShape},${stepString(tag.longName)},.ELEMENT.,` +
        `${stepEnum(pd)},$`);
      storey.spaces.push(id);
      this.report.spaces += 1;
    } else {
      id = w.add(tag.ifcClass, this._occurrenceArgs(tag, guid, placement, productShape));
      storey.contained.push(id);
      this.report.elements += 1;
    }
    product.entityId = id;

    // property sets (per product)
    for (const pset of tag.psets) this._emitPset(pset, id, `pset:${product.key}:`);

    // type (R3 — deduped later)
    if (tag.typeName) this._registerType(product);
  }

  _occurrenceArgs(tag, guid, placement, productShape) {
    const cls = tag.ifcClass;
    const objectType = tag.objectType != null
      ? tag.objectType : (tag.predefinedType === 'USERDEFINED' ? (tag.typeName || tag.name) : tag.typeName);
    const head = `${stepString(guid)},${ref(this.ownerHistory)},${stepString(tag.name)},` +
      `${stepString(tag.description)},${stepString(objectType)},${ref(placement)},${productShape},` +
      `${stepString(tag.tag)}`;
    if (OCC_NO_PREDEFINED.has(cls)) return head;                       // 8 attributes
    if (cls === 'IFCELEMENTASSEMBLY') return head + `,$,${stepEnum(tag.predefinedType)}`; // AssemblyPlace,PredefinedType
    if (cls === 'IFCDOOR' || cls === 'IFCWINDOW') {
      return head + `,$,$,${stepEnum(tag.predefinedType)},$,$`;         // OverallHeight,OverallWidth,PredefinedType,OperationType,UserDefinedOperationType
    }
    return head + `,${stepEnum(tag.predefinedType)}`;                    // standard 9 attributes
  }

  // ------------------------------------------------------------------------
  // Body geometry items (solids / facesets / mapped items)
  // ------------------------------------------------------------------------
  _emitBodyItems(product) {
    const items = product.items;
    if (!items.length) return { items: [], type: 'Tessellation' };

    // ASSEMBLY instancing (R4, product level): identical bodies share one
    // IfcRepresentationMap; each occurrence's Body is a single IfcMappedItem
    // with the identity operator (the map is in the product's own frame).
    const group = product.assemblyGroup;
    if (group) {
      const w = this.w;
      if (group.mapId == null) {
        const inner = this._emitBodyItemsInner(product);
        const rep = w.add('IFCSHAPEREPRESENTATION',
          `${ref(this.bodyContext)},'Body',${stepString(inner.type)},${list(inner.items.map(ref))}`);
        group.mapId = w.add('IFCREPRESENTATIONMAP', `${ref(this._identityAxis3())},${ref(rep)}`);
        this.report.representationMaps += 1;
      }
      const item = w.add('IFCMAPPEDITEM', `${ref(group.mapId)},${ref(this._identityOperator())}`);
      this.report.mappedItems += 1;
      return { items: [item], type: 'MappedRepresentation' };
    }
    return this._emitBodyItemsInner(product);
  }

  _identityOperator() {
    return this.w.intern('identity', 'IFCCARTESIANTRANSFORMATIONOPERATOR3D',
      `$,$,${ref(this._pt3([0, 0, 0]))},$,$`);
  }

  /** Body items for one product (mesh-level instancing / direct geometry). */
  _emitBodyItemsInner(product) {
    const items = product.items;
    // decide per item: direct or mapped
    const anyMapped = items.some((it) => it.instanceKey);
    const kinds = new Set(items.filter((it) => !it.instanceKey).map((it) => (it.kind === 'tess' ? 'tess' : 'solid')));
    // If the product mixes mapped + direct items, or mixes solids with
    // tessellation, wrap the direct items into single-use maps so the whole
    // body is one honest 'MappedRepresentation'.
    const heterogeneous = anyMapped || kinds.size > 1;

    const emitted = [];
    for (const it of items) {
      if (heterogeneous || it.instanceKey) {
        emitted.push(this._emitMappedItem(product, it));
      } else {
        emitted.push(...this._emitGeometryItems(it, it.matrixLocal, product));
      }
    }
    let type;
    if (heterogeneous) type = 'MappedRepresentation';
    else type = kinds.has('tess') ? 'Tessellation' : 'SweptSolid';
    return { items: emitted, type };
  }

  /** Emit (or reuse) an IfcRepresentationMap for the item, then an IfcMappedItem. */
  _emitMappedItem(product, item) {
    const w = this.w;
    const key = item.instanceKey || `single:${this._singleSeq++}`;
    let entry = this._maps.get(key);
    if (!entry) {
      // geometry expressed in its own local frame (identity matrix)
      const inner = this._emitGeometryItems(item, new this.THREE.Matrix4(), product);
      const innerType = inner.solid ? 'SweptSolid' : 'Tessellation';
      const rep = w.add('IFCSHAPEREPRESENTATION',
        `${ref(this.bodyContext)},'Body',${stepString(innerType)},${list(inner.map(ref))}`);
      const mapId = w.add('IFCREPRESENTATIONMAP', `${ref(this._identityAxis3())},${ref(rep)}`);
      entry = { mapId };
      this._maps.set(key, entry);
      this.report.representationMaps += 1;
    }
    // transformation operator from the item's local matrix (three, product frame)
    const d = this._decompose(item.matrixLocal);
    const axis1 = this._dir3(this._c(d.mx));                       // IFC-local x ← three x
    const axis2 = this._dir3(this._c(d.mz.clone().negate()));      // IFC-local y ← three −z
    const axis3 = this._dir3(this._c(d.my));                       // IFC-local z ← three y
    const origin = this._pt3(this._c(d.pos));
    const sx = Math.abs(d.sx), sy = Math.abs(d.sy), sz = Math.abs(d.sz);
    let op;
    if (Math.abs(sx - sy) < 1e-9 && Math.abs(sx - sz) < 1e-9) {
      const scale = Math.abs(sx - 1) < 1e-12 ? '$' : stepReal(sx);
      op = w.add('IFCCARTESIANTRANSFORMATIONOPERATOR3D',
        `${ref(axis1)},${ref(axis2)},${ref(origin)},${scale},${ref(axis3)}`);
    } else {
      // Axis2 corresponds to three z (scale sz), Axis3 to three y (scale sy)
      op = w.add('IFCCARTESIANTRANSFORMATIONOPERATOR3DNONUNIFORM',
        `${ref(axis1)},${ref(axis2)},${ref(origin)},${stepReal(sx)},${ref(axis3)},${stepReal(sz)},${stepReal(sy)}`);
    }
    this.report.mappedItems += 1;
    return w.add('IFCMAPPEDITEM', `${ref(entry.mapId)},${ref(op)}`);
  }

  /**
   * Emit the representation items for one mesh geometry under transform M
   * (a THREE.Matrix4 relative to the product frame). Returns an array of
   * item ids (styled). `.solid` on the array is true when all items are
   * swept solids.
   */
  _emitGeometryItems(item, M, product) {
    const kind = item.kind;
    let ids = [];
    try {
      if (kind === 'box') ids = [this._emitBoxSolid(item, M)];
      else if (kind === 'cylinder') ids = [this._emitCylinderSolid(item, M)];
      else if (kind === 'extrude') ids = this._emitExtrudeSolids(item, M);
      else if (kind === 'bbox') ids = [this._emitBBoxSolid(item, M)];
      else ids = [this._emitFaceSet(item, M)];
      ids.solid = kind !== 'tess';
    } catch (err) {
      if (this.opt.geometry === 'solids') throw err;
      this.warnings.push(`mesh "${item.name}": solid emission failed (${err.message}); tessellating`);
      ids = [this._emitFaceSet(item, M)];
      ids.solid = false;
    }
    // style every item
    const style = this._surfaceStyle(item.material);
    for (const id of ids) {
      this.w.add('IFCSTYLEDITEM', `${ref(id)},(${ref(style)}),${stepString(item.name)}`);
    }
    return ids;
  }

  // --- solids -------------------------------------------------------------

  /** BoxGeometry(w,h,d) → IfcExtrudedAreaSolid(IfcRectangleProfileDef) along mesh +Y. */
  _emitBoxSolid(item, M) {
    const p = item.geometry.parameters;
    const d = this._decompose(M);
    const W = p.width * Math.abs(d.sx), H = p.height * Math.abs(d.sy), D = p.depth * Math.abs(d.sz);
    // bottom-centre of the box in the product frame (three's box is centred)
    const bottom = d.pos.clone().addScaledVector(d.my, -H / 2);
    return this._extrusion(this._c(bottom), this._c(d.my), this._c(d.mx), this._rectProfile(W, D), H);
  }

  /** CylinderGeometry(r,r,h) → IfcExtrudedAreaSolid(IfcCircleProfileDef) along mesh +Y. */
  _emitCylinderSolid(item, M) {
    const p = item.geometry.parameters;
    const d = this._decompose(M);
    const R = p.radiusTop * (Math.abs(d.sx) + Math.abs(d.sz)) / 2;
    const H = p.height * Math.abs(d.sy);
    const bottom = d.pos.clone().addScaledVector(d.my, -H / 2);
    return this._extrusion(this._c(bottom), this._c(d.my), this._c(d.mx), this._circleProfile(R), H);
  }

  /** ifcLOD='bbox' → the mesh's bounding box as an extruded rectangle. */
  _emitBBoxSolid(item, M) {
    const THREE = this.THREE;
    const b = this._bbox(item.geometry);
    const size = b.getSize(new THREE.Vector3());
    const center = b.getCenter(new THREE.Vector3());
    const M2 = M.clone().multiply(new THREE.Matrix4().makeTranslation(center.x, center.y, center.z));
    const d = this._decompose(M2);
    const W = Math.max(size.x * Math.abs(d.sx), 1e-6), H = Math.max(size.y * Math.abs(d.sy), 1e-6);
    const D = Math.max(size.z * Math.abs(d.sz), 1e-6);
    const bottom = d.pos.clone().addScaledVector(d.my, -H / 2);
    return this._extrusion(this._c(bottom), this._c(d.my), this._c(d.mx), this._rectProfile(W, D), H);
  }

  /** ExtrudeGeometry(shape(+holes), {depth}) → IfcExtrudedAreaSolid along mesh +Z. */
  _emitExtrudeSolids(item, M) {
    const p = item.geometry.parameters;
    const shapes = Array.isArray(p.shapes) ? p.shapes : [p.shapes];
    const o = p.options || {};
    const depth = Number(o.depth != null ? o.depth : (o.amount != null ? o.amount : 1));
    const segs = Number.isFinite(o.curveSegments) ? o.curveSegments : this.opt.curveSegments;
    const d = this._decompose(M);
    const sx = Math.abs(d.sx), sy = Math.abs(d.sy), sz = Math.abs(d.sz);
    const ids = [];
    for (const shape of shapes) {
      const pts = shape.extractPoints(segs);
      let outer = cleanRing(pts.shape);
      if (outer.length < 3) throw new Error('degenerate extrude outer contour');
      if (signedArea(outer) < 0) outer.reverse();       // outer CCW
      const holes = [];
      for (const h of pts.holes || []) {
        let ring = cleanRing(h);
        if (ring.length < 3) continue;
        if (signedArea(ring) > 0) ring.reverse();       // holes CW
        holes.push(ring);
      }
      // one shared 2D point list for the outer ring + all hole rings; each
      // ring is an IfcIndexedPolyCurve with an IfcLineIndex segment (compact)
      const rings = [outer, ...holes];
      const coords = [];
      const idx = [];
      for (const ring of rings) {
        const start = coords.length;
        for (const p of ring) coords.push(`(${stepReal(p.x * sx)},${stepReal(p.y * sy)})`);
        const line = [];
        for (let i = 0; i < ring.length; i += 1) line.push(start + i + 1);
        line.push(start + 1); // close
        idx.push(line);
      }
      const plist = this.w.add('IFCCARTESIANPOINTLIST2D', '(' + coords.join(',') + ')');
      const curves = idx.map((line) =>
        this.w.add('IFCINDEXEDPOLYCURVE', `${ref(plist)},(IFCLINEINDEX((${line.join(',')}))),.F.`));
      let profile;
      if (holes.length) {
        profile = this.w.add('IFCARBITRARYPROFILEDEFWITHVOIDS',
          `.AREA.,${stepString(item.name || null)},${ref(curves[0])},${list(curves.slice(1).map(ref))}`);
        this.report.profilesWithVoids += 1;
      } else {
        profile = this.w.add('IFCARBITRARYCLOSEDPROFILEDEF',
          `.AREA.,${stepString(item.name || null)},${ref(curves[0])}`);
      }
      // extrusion along mesh local +Z starting at the mesh origin (z=0)
      ids.push(this._extrusion(this._c(d.pos), this._c(d.mz), this._c(d.mx), profile, depth * sz));
    }
    return ids;
  }

  /** Interned rectangle profile (identical dims reuse one entity). */
  _rectProfile(W, D) {
    const key = `${stepReal(W)},${stepReal(D)}`;
    return this.w.intern(key, 'IFCRECTANGLEPROFILEDEF', `.AREA.,$,$,${key}`);
  }

  /** Interned circle profile. */
  _circleProfile(R) {
    const key = stepReal(R);
    return this.w.intern(key, 'IFCCIRCLEPROFILEDEF', `.AREA.,$,$,${key}`);
  }

  /** Emit IfcExtrudedAreaSolid with a Position frame (location, z-axis, x-axis) in the product frame. */
  _extrusion(loc, axisZ, refX, profileId, depth) {
    const pos = this._axis3(loc, axisZ, refX);
    const dir = this._dir3([0, 0, 1]);
    this.report.extrudedSolids += 1;
    return this.w.add('IFCEXTRUDEDAREASOLID',
      `${ref(profileId)},${ref(pos)},${ref(dir)},${stepReal(depth)}`);
  }

  // --- tessellation -------------------------------------------------------

  /** Any BufferGeometry → IfcTriangulatedFaceSet in the product frame. */
  _emitFaceSet(item, M) {
    const THREE = this.THREE;
    const g = item.geometry;
    const posAttr = g.attributes.position;
    const v = new THREE.Vector3();
    const coords = [];
    for (let i = 0; i < posAttr.count; i += 1) {
      v.set(posAttr.getX(i), posAttr.getY(i), posAttr.getZ(i)).applyMatrix4(M);
      const c = this._c(v);
      coords.push(`(${stepReal(c[0])},${stepReal(c[1])},${stepReal(c[2])})`);
    }
    const flip = M.determinant() < 0;
    const tris = [];
    const idx = g.index;
    const push = (a, b, c) => {
      if (a === b || b === c || a === c) return; // skip degenerate
      tris.push(flip ? `(${a + 1},${c + 1},${b + 1})` : `(${a + 1},${b + 1},${c + 1})`);
    };
    if (idx) {
      for (let i = 0; i + 2 < idx.count; i += 3) push(idx.getX(i), idx.getX(i + 1), idx.getX(i + 2));
    } else {
      for (let i = 0; i + 2 < posAttr.count; i += 3) push(i, i + 1, i + 2);
    }
    if (!tris.length) throw new Error('no triangles');
    const plist = this.w.add('IFCCARTESIANPOINTLIST3D', '(' + coords.join(',') + ')');
    this.report.faceSets += 1;
    return this.w.add('IFCTRIANGULATEDFACESET', `${ref(plist)},$,$,(${tris.join(',')}),$`);
  }

  // --- materials → surface styles ------------------------------------------

  _surfaceStyle(material) {
    const key = this._styleKeyOf(material);
    let id = this._styleCache.get(key);
    if (id !== undefined) return id;
    const w = this.w;
    let r = 0.8, g = 0.8, b = 0.8;
    if (material && material.color) { r = material.color.r; g = material.color.g; b = material.color.b; }
    let transparency = 0;
    if (material && material.transparent && Number.isFinite(material.opacity)) {
      transparency = Math.min(1, Math.max(0, 1 - material.opacity));
    }
    const name = (material && material.name) || `material_${this._styleCache.size + 1}`;
    const colour = w.add('IFCCOLOURRGB', `$,${stepReal(r)},${stepReal(g)},${stepReal(b)}`);
    const rendering = w.add('IFCSURFACESTYLERENDERING',
      `${ref(colour)},${stepReal(transparency)},$,$,$,$,$,$,.NOTDEFINED.`);
    id = w.add('IFCSURFACESTYLE', `${stepString(name)},.BOTH.,(${ref(rendering)})`);
    this._styleCache.set(key, id);
    return id;
  }

  // ------------------------------------------------------------------------
  // Property sets
  // ------------------------------------------------------------------------
  _emitPset(pset, targetId, keyPrefix) {
    if (!pset || !pset.name) return null;
    const w = this.w;
    const props = [];
    const src = pset.props || pset.properties || {};
    for (const propName of Object.keys(src)) {
      const raw = src[propName];
      const value = this._measure(raw);
      if (value == null) continue;
      props.push(w.add('IFCPROPERTYSINGLEVALUE', `${stepString(propName)},$,${value},$`));
    }
    if (!props.length) return null;
    const psetId = w.add('IFCPROPERTYSET',
      `${stepString(this.guids.guid(keyPrefix + pset.name))},${ref(this.ownerHistory)},` +
      `${stepString(pset.name)},${stepString(pset.description)},${list(props.map(ref))}`);
    if (targetId != null) {
      w.add('IFCRELDEFINESBYPROPERTIES',
        `${stepString(this.guids.guid(keyPrefix + pset.name + ':rel'))},${ref(this.ownerHistory)},` +
        `$,$,(${ref(targetId)}),${ref(psetId)}`);
    }
    return psetId;
  }

  /** {value,type} | scalar → typed IFC measure text, or null. */
  _measure(raw) {
    if (raw === undefined || raw === null) return null;
    let value = raw, type = null;
    if (typeof raw === 'object' && !Array.isArray(raw)) {
      value = raw.value;
      type = raw.type != null ? String(raw.type).toLowerCase() : null;
      if (value === undefined || value === null) return null;
    }
    if (!type) {
      if (typeof value === 'boolean') type = 'boolean';
      else if (typeof value === 'number') type = Number.isInteger(value) ? 'real' : 'real';
      else type = 'label';
    }
    switch (type) {
      case 'boolean': return `IFCBOOLEAN(${stepBool(value === true || value === 'true' || value === 1)})`;
      case 'integer': return `IFCINTEGER(${stepInt(value)})`;
      case 'count': return `IFCCOUNTMEASURE(${stepInt(value)})`;
      case 'real': return `IFCREAL(${stepReal(value)})`;
      case 'voltage': return `IFCELECTRICVOLTAGEMEASURE(${stepReal(value)})`;
      case 'current': return `IFCELECTRICCURRENTMEASURE(${stepReal(value)})`;
      case 'power': return `IFCPOWERMEASURE(${stepReal(value)})`;
      case 'length': return `IFCLENGTHMEASURE(${stepReal(value)})`;
      case 'positivelength': return `IFCPOSITIVELENGTHMEASURE(${stepReal(value)})`;
      case 'area': return `IFCAREAMEASURE(${stepReal(value)})`;
      case 'volume': return `IFCVOLUMEMEASURE(${stepReal(value)})`;
      case 'mass': return `IFCMASSMEASURE(${stepReal(value)})`;
      case 'frequency': return `IFCFREQUENCYMEASURE(${stepReal(value)})`;
      case 'angle': return `IFCPLANEANGLEMEASURE(${stepReal(value)})`;
      case 'thermodynamictemperature': return `IFCTHERMODYNAMICTEMPERATUREMEASURE(${stepReal(value)})`;
      case 'ratio': return `IFCRATIOMEASURE(${stepReal(value)})`;
      case 'identifier': return `IFCIDENTIFIER(${stepString(String(value))})`;
      case 'text': return `IFCTEXT(${stepString(String(value))})`;
      case 'logical': return `IFCLOGICAL(${value === true ? '.T.' : value === false ? '.F.' : '.U.'})`;
      case 'label':
      default: return `IFCLABEL(${stepString(String(value))})`;
    }
  }

  // ------------------------------------------------------------------------
  // Types (R3) and relationships
  // ------------------------------------------------------------------------
  _registerType(product) {
    if (!this._types) this._types = new Map();
    const tag = product.tag;
    const typeClass = tag.typeClass || defaultTypeClass(tag.ifcClass, tag.isSpace);
    const key = `${typeClass}|${tag.typeName}`;
    let entry = this._types.get(key);
    if (!entry) {
      entry = { typeClass, typeName: tag.typeName, tag, occurrences: [] };
      this._types.set(key, entry);
    }
    entry.occurrences.push(product.entityId);
  }

  _emitRelationships(products) {
    const w = this.w;

    // R3 shared types + IfcRelDefinesByType
    if (this._types) {
      for (const [key, t] of this._types) {
        // type property sets attach ONCE to the shared type
        const psetIds = [];
        for (const pset of t.tag.typePsets) {
          const id = this._emitPset(pset, null, `typepset:${key}:`);
          if (id != null) psetIds.push(id);
        }
        // If every occurrence of this type shares one assembly map (product-
        // level instancing), attach that map to the type — the canonical IFC
        // "type geometry" pattern (occurrences reference it via IfcMappedItem).
        let repMaps = null;
        if (this._assemblyGroups) {
          const occ = t.occurrences.slice().sort();
          for (const g of this._assemblyGroups) {
            if (g.mapId == null) continue;
            const mem = g.members.map((p) => p.entityId).sort();
            if (mem.length === occ.length && mem.every((v, i) => v === occ[i])) { repMaps = [g.mapId]; break; }
          }
        }
        const typeId = w.add(t.typeClass, this._typeArgs(t, key, psetIds, repMaps));
        w.add('IFCRELDEFINESBYTYPE',
          `${stepString(this.guids.guid('rel:type:' + key))},${ref(this.ownerHistory)},$,$,` +
          `${list(t.occurrences.map(ref))},${ref(typeId)}`);
        this.report.types += 1;
      }
    }

    // R6 containment: one IfcRelContainedInSpatialStructure per storey
    for (const s of this.storeys) {
      if (s.contained.length) {
        w.add('IFCRELCONTAINEDINSPATIALSTRUCTURE',
          `${stepString(this.guids.guid('rel:contained:' + s.name))},${ref(this.ownerHistory)},` +
          `${stepString('Storey ' + s.name)},$,${list(s.contained.map(ref))},${ref(s.id)}`);
      }
      // spaces are AGGREGATED to their storey (IfcRelAggregates), not contained
      if (s.spaces.length) {
        w.add('IFCRELAGGREGATES',
          `${stepString(this.guids.guid('rel:spaces:' + s.name))},${ref(this.ownerHistory)},$,$,` +
          `${ref(s.id)},${list(s.spaces.map(ref))}`);
      }
    }
  }

  _typeArgs(t, key, psetIds, repMaps) {
    const tag = t.tag;
    const guid = this.guids.guid('type:' + key);
    const pd = tag.typePredefinedType || tag.predefinedType || 'NOTDEFINED';
    const psets = psetIds.length ? list(psetIds.map(ref)) : '$';
    const maps = repMaps && repMaps.length ? list(repMaps.map(ref)) : '$';
    const head = `${stepString(guid)},${ref(this.ownerHistory)},${stepString(t.typeName)},` +
      `${stepString(tag.typeDescription)},$,${psets},${maps},$,${stepString(t.typeName)}`;
    const cls = t.typeClass;
    if (TYPE_NO_PREDEFINED.has(cls)) return head;                    // 9 attributes
    if (cls === 'IFCSPACETYPE') return head + `,${stepEnum(pd)},${stepString(tag.longName)}`; // 11
    if (cls === 'IFCDOORTYPE' || cls === 'IFCWINDOWTYPE') return head + `,${stepEnum(pd)},.NOTDEFINED.,$,$`;
    return head + `,${stepEnum(pd)}`;                                // standard 10 attributes
  }

  // ------------------------------------------------------------------------
  // Assembly
  // ------------------------------------------------------------------------
  _assemble(products) {
    const w = this.w;
    const ts = new Date(this.opt.timestamp * 1000);
    const iso = ts.toISOString().replace(/\.\d+Z$/, '');
    const author = this.meta.author || {};
    const header =
      'ISO-10303-21;\n' +
      'HEADER;\n' +
      "FILE_DESCRIPTION(('ViewDefinition [CoordinationView]'),'2;1');\n" +
      `FILE_NAME(${stepString(this.fileName + '.ifc')},${stepString(iso)},(${stepString(author.name || '')}),` +
      `(${stepString(author.org || author.organization || '')}),${stepString('tekton-ifc IFC toolkit ' + VERSION)},` +
      `${stepString(APPLICATION_NAME + ' ' + VERSION)},'');\n` +
      "FILE_SCHEMA(('IFC4'));\n" +
      'ENDSEC;\n' +
      'DATA;\n';

    // finalise report (R10)
    this.report.entityCounts = { ...w.counts };
    this.report.totalEntities = w.total;
    const body = w.lines.join('\n');
    const reportForComment = { ...this.report };
    delete reportForComment.warnings;
    delete reportForComment.excluded;
    const reportComment = JSON.stringify({
      totalEntities: reportForComment.totalEntities,
      products: reportForComment.products,
      elements: reportForComment.elements,
      spaces: reportForComment.spaces,
      types: reportForComment.types,
      mappedItems: reportForComment.mappedItems,
      representationMaps: reportForComment.representationMaps,
      extrudedSolids: reportForComment.extrudedSolids,
      profilesWithVoids: reportForComment.profilesWithVoids,
      faceSets: reportForComment.faceSets,
      geometry: reportForComment.geometry,
    }).replace(/\*\//g, '*_/');
    const text = header + body + '\nENDSEC;\n' +
      `/* tekton-ifc exporter ${VERSION} report ${reportComment} */\n` +
      'END-ISO-10303-21;\n';
    this.report.bytes = text.length;
    return { text, report: this.report };
  }
}

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------

/** IfcXxx → IfcXxxType (type object class for an occurrence class). */
export function defaultTypeClass(ifcClass, isSpace) {
  const cls = String(ifcClass || 'IFCBUILDINGELEMENTPROXY').toUpperCase();
  if (isSpace || cls === 'IFCSPACE') return 'IFCSPACETYPE';
  return cls.endsWith('TYPE') ? cls : cls + 'TYPE';
}

/** Remove consecutive duplicate points and the closing duplicate of a ring. */
function cleanRing(points) {
  const out = [];
  for (const p of points) {
    const last = out[out.length - 1];
    if (last && Math.abs(last.x - p.x) < 1e-9 && Math.abs(last.y - p.y) < 1e-9) continue;
    out.push({ x: p.x, y: p.y });
  }
  while (out.length > 1) {
    const a = out[0], b = out[out.length - 1];
    if (Math.abs(a.x - b.x) < 1e-9 && Math.abs(a.y - b.y) < 1e-9) out.pop(); else break;
  }
  return out;
}

/** Shoelace signed area of a 2D ring (positive = counter-clockwise). */
function signedArea(ring) {
  let a = 0;
  for (let i = 0, n = ring.length; i < n; i += 1) {
    const p = ring[i], q = ring[(i + 1) % n];
    a += p.x * q.y - q.x * p.y;
  }
  return a / 2;
}

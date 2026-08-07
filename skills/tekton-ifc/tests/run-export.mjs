// Headless export harness for the tekton-ifc canonical exporter.
//
//   cd skills/tekton-ifc/tests && npm install && node run-export.mjs
//
// Builds the example model with real three.js (0.184.0) and writes:
//   out/example-auto.ifc   (geometry: 'auto'  → solids + instancing)
//   out/example-tess.ifc   (geometry: 'tessellation' → v1-style triangles)
// then runs a determinism check (guidSeed ⇒ byte-identical re-export).

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { exportIfc, toIfc, VERSION } from '../assets/ifc-export.js';
import { buildExampleModel } from '../assets/example-model.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(here, 'out');
fs.mkdirSync(outDir, { recursive: true });

const baseMeta = {
  projectName: 'Test Electrical Room',
  storeys: [{ name: 'Level 1', elevation: 0 }, { name: 'Level 2', elevation: 4 }],
  author: { name: 'test', org: 'tekton' },
  guidSeed: 'tekton-example',
  timestamp: 1785383780,
};

function run(mode, file) {
  const model = buildExampleModel(THREE);
  const { text, report } = exportIfc(THREE, model, { ...baseMeta, geometry: mode, fileName: path.basename(file, '.ifc') });
  fs.writeFileSync(path.join(outDir, file), text);
  console.log(`\n=== geometry=${mode} → tests/out/${file} (${text.length} bytes, ${report.totalEntities} entities) ===`);
  console.log(JSON.stringify({
    products: report.products, elements: report.elements, spaces: report.spaces,
    types: report.types, mappedItems: report.mappedItems, maps: report.representationMaps,
    extrudedSolids: report.extrudedSolids, profilesWithVoids: report.profilesWithVoids,
    faceSets: report.faceSets, droppedByFeatureSize: report.droppedByFeatureSize,
    lodSkipped: report.lodSkipped,
  }, null, 2));
  console.log('excluded nodes:', report.excluded.map((e) => `${e.name} (${e.reason})`).join('; ') || '(none)');
  if (report.warnings.length) console.log('warnings:', report.warnings);
  return { text, report };
}

console.log(`tekton-ifc ifc-export.js v${VERSION} — headless harness (three ${THREE.REVISION})`);
const auto = run('auto', 'example-auto.ifc');
const tess = run('tessellation', 'example-tess.ifc');

// --- determinism (R9): same model + guidSeed ⇒ byte-identical output ------
const model = buildExampleModel(THREE);
const a = toIfc(THREE, model, { ...baseMeta, geometry: 'auto', fileName: 'example-auto' });
const b = toIfc(THREE, model, { ...baseMeta, geometry: 'auto', fileName: 'example-auto' });
if (a !== b) throw new Error('DETERMINISM FAILURE: two exports of the same model differ');
if (a !== auto.text) throw new Error('DETERMINISM FAILURE: rebuilt model produced different bytes');
console.log('\ndeterminism: OK (byte-identical across re-export and model rebuild)');

// --- backward-compat smoke: v1-only tagging still works -------------------
{
  const g = new THREE.Group();
  const m = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0x999999 }));
  m.name = 'cube';
  g.add(m);
  // no userData.ifc anywhere → whole object is one product described by meta (v1 rule)
  const text = toIfc(THREE, g, { name: 'Generic proxy', ifcClass: 'IFCBUILDINGELEMENTPROXY', psets: [{ name: 'P', props: { A: 1 } }] });
  if (!/IFCBUILDINGELEMENTPROXY\(/.test(text)) throw new Error('v1 untagged-object fallback broken');
  console.log('v1 compat: OK (untagged object → single IfcBuildingElementProxy from meta)');
}

// --- size comparison (R10) --------------------------------------------------
console.log(`\nsize: auto ${auto.text.length} B / ${auto.report.totalEntities} entities  vs  ` +
  `tessellation ${tess.text.length} B / ${tess.report.totalEntities} entities`);
if (!(auto.report.totalEntities < tess.report.totalEntities)) {
  throw new Error('expected instancing/solids to yield fewer entities than tessellation');
}
console.log('\nrun-export: ALL OK');

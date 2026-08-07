// Extra option-path scenarios for ifc-export.js. Writes out/scenario-*.ifc
// (schema-checked afterwards by validate_export.py) and asserts inline.
//   node extra-scenarios.mjs

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import * as THREE from 'three';
import { exportIfc, toIfc, stepString, stepReal, compressGuid } from '../assets/ifc-export.js';
import { buildExampleModel } from '../assets/example-model.js';

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.join(here, 'out');
fs.mkdirSync(outDir, { recursive: true });
const meta = {
  projectName: 'Scenario', storeys: [{ name: 'Level 1', elevation: 0 }, { name: 'Level 2', elevation: 4 }],
  author: { name: 'test', org: 'tekton' }, guidSeed: 'scenarios', timestamp: 1785383780,
};
const write = (name, text) => fs.writeFileSync(path.join(outDir, name), text);
const assert = (cond, msg) => { if (!cond) throw new Error('ASSERT: ' + msg); console.log('  ok - ' + msg); };
const count = (text, ent) => (text.match(new RegExp(`=${ent}\\(`, 'g')) || []).length;

console.log('== scenario: clearanceAs = space (helper clearance volumes → IfcSpace)');
{
  const { text, report } = exportIfc(THREE, buildExampleModel(THREE), { ...meta, clearanceAs: 'space' });
  write('scenario-clearance-space.ifc', text);
  // 3 working_clearance helpers + 1 door_swing_clearance + the real room space
  assert(count(text, 'IFCSPACE') >= 4, `clearance volumes emitted as IfcSpace (${count(text, 'IFCSPACE')} spaces)`);
  assert(report.excluded.length < 7, 'clearance nodes no longer reported as excluded-only');
}

console.log('== scenario: minFeatureSize drops tiny meshes');
{
  const { text, report } = exportIfc(THREE, buildExampleModel(THREE), { ...meta, minFeatureSize: 0.06 });
  write('scenario-minfeature.ifc', text);
  assert(report.droppedByFeatureSize > 0, `droppedByFeatureSize = ${report.droppedByFeatureSize}`);
  const base = exportIfc(THREE, buildExampleModel(THREE), meta).report.totalEntities;
  assert(report.totalEntities < base, `fewer entities with minFeatureSize (${report.totalEntities} < ${base})`);
}

console.log('== scenario: placements = world (v1 identity placements, world-baked geometry)');
{
  const { text } = exportIfc(THREE, buildExampleModel(THREE), { ...meta, placements: 'world', geometry: 'tessellation' });
  write('scenario-world-placements.ifc', text);
  // every product placement uses the identity axis at the origin
  const identity = text.match(/IFCAXIS2PLACEMENT3D\(#(\d+),\$,\$\)/);
  assert(identity, 'identity axis placement present');
  assert(count(text, 'IFCEXTRUDEDAREASOLID') === 0, 'tessellation mode: no solids');
}

console.log("== scenario: geometry = 'solids' errors on baked geometry");
{
  let threw = false;
  try { exportIfc(THREE, buildExampleModel(THREE), { ...meta, geometry: 'solids' }); }
  catch (e) { threw = /solids/.test(e.message); console.log('    got:', e.message.slice(0, 90) + '…'); }
  assert(threw, "geometry:'solids' throws when a mesh cannot be a solid");
}

console.log('== scenario: nested tags (space group CONTAINING tagged panels) + non-uniform scale');
{
  const room = new THREE.Group();
  room.name = 'room';
  room.userData.ifc = { ifcClass: 'IFCSPACE', name: 'Nested Room', storey: 'Level 1' };
  const vol = new THREE.Mesh(new THREE.BoxGeometry(4, 3, 4), new THREE.MeshStandardMaterial());
  vol.name = 'vol'; vol.position.y = 1.5;
  room.add(vol);
  const panel = new THREE.Group();
  panel.name = 'panel'; panel.position.set(1, 1, -1);
  panel.userData.ifc = { ifcClass: 'IFCELECTRICDISTRIBUTIONBOARD', predefinedType: 'DISTRIBUTIONBOARD', name: 'P-N1', storey: 'Level 1' };
  const box = new THREE.Mesh(new THREE.BoxGeometry(1, 1, 1), new THREE.MeshStandardMaterial({ color: 0x336699 }));
  box.name = 'stretched_box';
  box.scale.set(0.5, 1.2, 0.15);           // non-uniform scale folded into the extrusion dims
  box.position.y = 0.6;
  panel.add(box);
  room.add(panel);                          // tagged product NESTED inside the tagged space
  const { text, report } = exportIfc(THREE, room, meta);
  write('scenario-nested.ifc', text);
  assert(report.products === 2, `nested tags → 2 products (${report.products})`);
  assert(count(text, 'IFCSPACE') === 1 && count(text, 'IFCELECTRICDISTRIBUTIONBOARD') === 1, 'space + board both emitted');
  // the space body must NOT swallow the panel's box: expect exactly one 4x4 rect and one 0.5x0.15 rect
  assert(/IFCRECTANGLEPROFILEDEF\(\.AREA\.,\$,\$,4\.,4\.\)/.test(text), 'space extrusion 4x4 present');
  assert(/IFCRECTANGLEPROFILEDEF\(\.AREA\.,\$,\$,0\.5,0\.15\)/.test(text), 'scaled box → 0.5 x 0.15 rectangle (scale folded)');
  assert(count(text, 'IFCEXTRUDEDAREASOLID') === 2, 'exactly two solids (no double-counting of nested geometry)');
}

console.log('== scenario: untagged model, whole-object product from meta (v1 rule)');
{
  const g = new THREE.Group();
  const m = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.3, 2, 24), new THREE.MeshStandardMaterial({ color: 0x999999 }));
  m.name = 'post'; m.position.y = 1;
  g.add(m);
  const text = toIfc(THREE, g, {
    ...meta, name: 'Bollard', ifcClass: 'IFCBUILDINGELEMENTPROXY', predefinedType: 'ELEMENT',
    psets: [{ name: 'Info', props: { Height: { value: 2, type: 'length' }, Note: 'v1-style meta psets' } }],
    typeName: 'Bollard type A',
  });
  write('scenario-untagged.ifc', text);
  assert(count(text, 'IFCBUILDINGELEMENTPROXY') === 1, 'single proxy product from meta');
  assert(count(text, 'IFCBUILDINGELEMENTPROXYTYPE') === 1, 'meta.typeName → type object');
  assert(/IFCCIRCLEPROFILEDEF\(\.AREA\.,\$,\$,0\.3\)/.test(text), 'cylinder → circle profile extrusion');
}

console.log('== scenario: STEP encoding helpers');
{
  assert(stepString("O'Neil — 400A") === "'O''Neil \\X2\\2014\\X0\\ 400A'", 'stepString escapes apostrophe + unicode');
  assert(stepString('a\\b') === "'a\\\\b'", 'stepString escapes backslash');
  assert(stepReal(1) === '1.' && stepReal(0.25) === '0.25' && stepReal(1e-7) === '1.E-7' && stepReal(0) === '0.',
    `stepReal formatting (${stepReal(1)}, ${stepReal(0.25)}, ${stepReal(1e-7)}, ${stepReal(0)})`);
  const g = compressGuid(new Uint8Array(16).fill(255));
  assert(g.length === 22 && g === '3$$$$$$$$$$$$$$$$$$$$$', `compressGuid(all-ones) = ${g}`);
}

console.log('\nextra-scenarios: ALL OK');

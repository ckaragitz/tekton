# exporter-engineer — out-of-scope notes for the orchestrator

Deliverables (all inside the slice):
`skills/revit-bridge/assets/ifc-export.js` (v2 canonical exporter),
`skills/revit-bridge/assets/example-model.js`, `skills/revit-bridge/tests/`
(`package.json`, `run-export.mjs`, `extra-scenarios.mjs`,
`validate_export.py`, `.gitignore`). Everything below is a note, not an
action taken.

## Facts learned (candidates for KNOWLEDGE.md)

1. **IFC4 schema defect — known false positive.** The official IFC4
   (ADD2 TC1) EXPRESS rule `IfcTransformer.CorrectTypeAssigned` misspells
   the type class as `IFC4.IFCTRANFORMERTYPE` (missing "s"). Consequence:
   ifcopenshell `validate(..., express_rules=True)` reports ONE spurious
   error whenever an `IfcTransformer` is typed by a (correct)
   `IfcTransformerType`. The json/attribute rules pass clean. Any
   `validate_ifc.py` in the skill should whitelist/annotate this exact
   rule so the report does not scare the user. All other WHERE rules pass.
2. **Entity count is NOT the right size metric; bytes are.** Mesh-level
   IFC instancing costs `IfcMappedItem + operator + origin point ≈ 3`
   entities per occurrence — the SAME as a tessellated mesh
   (`pointlist + faceset + styleditem = 3`). Instancing shrinks BYTES ~10x
   (44 KB vs 390 KB on the example) but shrinks entity COUNT only through
   ASSEMBLY-level sharing (identical whole products → one map, also
   attached to the shared type's `RepresentationMaps`) and shared point
   lists. Reports/SKILL text should quote byte reduction, not entities.
3. **IFC4 lets several products share one `IfcProductDefinitionShape`**
   (`ShapeOfProduct` is a SET in IFC4, was 1:1 in 2x3). The exporter uses
   this for identical products (each keeps its own `IfcLocalPlacement`).
   Valid per schema + ifcopenshell; worth confirming Revit's importer
   places both instances (expected: yes — placement is per product).
4. Compact profile encoding used: outer + hole rings of a holed dead front
   share ONE `IfcCartesianPointList2D`, each ring an
   `IfcIndexedPolyCurve(#list,(IFCLINEINDEX((...))),.F.)`. Revit ≥2016
   reads IfcIndexedPolyCurve; if an older Revit target is confirmed (open
   question in TRACKER), a fallback to `IfcPolyline` may be needed.
5. y-up→z-up conversion validated numerically: per-product world bboxes
   from the solid (auto) export and the tessellated export agree to
   0.2 mm across all 7 products, including a 90°-rotated panel — so the
   placement decomposition (Axis=C(nodeY), Ref=C(nodeX)) and the
   Box/Cylinder/Extrude solid frames are consistent.

## Suggested follow-ups (not in this slice)

- **SKILL.md alignment** (owned by another agent): the exporter also
  accepts `meta.instancing`, `meta.placements ('local'|'world')`,
  `meta.orphans`, `meta.timestamp`, `meta.curveSegments`, per-node
  `ifcLOD`, `userData.ifc.typeClass / typePredefinedType /
  typeDescription / globalId / longName / objectType`, and exposes
  `exportIfc(THREE, obj, meta) → {text, report}` + `getLastReport()` in
  addition to `toIfc`. `meta.geometry='tessellation'` also defaults
  `instancing` to false (pure v1 geometry); `placements:'world'`
  reproduces v1 identity placements. Worth reflecting in the SKILL.md
  option table if not already there.
- **F7 (deliver into the Chicago-plenum Design project):** the asset is
  ready to drop in as `./ifc-export.js`. The panel builder in that project
  bakes some transforms (`.rotateX()`, `merge()`); those meshes will
  tessellate (by design). To get MORE solids there, the model code should
  keep primitives un-baked and set `.position/.rotation` on the Object3D —
  the exporter's bbox sanity check deliberately refuses "primitives" whose
  vertices no longer match their `parameters`.
- A project `/verify` skill could run `npm --prefix
  skills/revit-bridge/tests test` (export → scenarios → python validator);
  the harness is already headless and takes ~10 s.

## Known limitations documented in the module header

- Occurrence/type attribute signatures: standard IFC4 element signature
  + a small exception table (flow supertypes, furnishing, door/window,
  element assembly, space/space type). Exotic classes with bespoke
  attribute lists (e.g. `IfcWindow` lining detail) are not modelled.
- `ExtrudeGeometry` with bevels or an `extrudePath` (sweeps) falls back to
  tessellation. `THREE.InstancedMesh` IS expanded into instances.
- GUIDs are stable only with `meta.guidSeed` (or per-node
  `userData.ifc.globalId`); without a seed they are crypto-random per
  export (v1 behaviour).

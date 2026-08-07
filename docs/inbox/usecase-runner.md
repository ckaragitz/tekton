# inbox — usecase-runner (2026-08-03)

Ran both real use cases through the existing engine; bundles under
`usecases/`. Notes for the orchestrator (do not edit source outside my
paths, so these are proposals):

1. **`spec/building.schema.json` is out of sync with `generate_ifc.py`.** The
   generator consumes an `equipment` array (documented in its docstring and
   used by `spec/examples/electrical-room.json`), but the schema has
   `additionalProperties: false` and NO `equipment` property. Any spec with
   equipment fails schema validation even though the generator accepts it.
   Add `equipment` (kind, name, level, position, rotationDeg, elevation,
   dims, ifcClass, predefinedType, typeName, description, tag, psets,
   typePsets) to the schema. Also the schema requires levels/footprint-style
   architecture; an equipment-only product model (the Eaton panelboard spec,
   no walls) generates fine and should be a documented, schema-valid case.
2. **`validate_ifc.py` typing-smell heuristic keys on substring "voltage"
   in a property name**, so the intentionally separate human-readable label
   `SystemVoltage` ('480Y/277 V') — which `references/shared-parameters-mapping.md`
   §2 explicitly recommends — is flagged as an untyped electrical value and
   docks the data score. Either whitelist a documented label name (e.g.
   `SystemDesignation`, which I used) or teach the linter to skip labels
   when a numeric `Voltage` measure is present in the same pset. Reconcile
   the doc and the linter so authors don't fight the tool.
3. **`spec/examples/electrical-room.json` equipment positions were
   approximate** (B-HG4 at x=1.6). The customer's real export decodes to
   B-HG4 centreline 1.399 m from the west wall (matches its own
   `CenterlineFromGrid16BS` pset). `usecases/chicago-plenum-electrical-room/room-spec.json`
   carries the corrected positions recovered by harden_ifc.py — consider
   promoting them into the canonical example.
4. **The firm's real shared-parameters GUIDs are still missing** from the
   repo (the literal `exports/panelboard-shared-parameters.txt` lives only
   in the Design project). I delivered `usecases/eaton-panelboard/panelboard-shared-parameters.txt`
   with stable seeded GUIDs + an explicit warning header. Get the real file
   from the Design project so Route B (pre-seeded sidecar adopting the
   firm's GUIDs) can be delivered for real; today it is documented but
   unconfirmed in a live Revit.
5. Hardening ceiling on the real room is 89.0 (not 100) purely because the
   trapeze hangers are a `merge()`-baked triangle assembly (not a provable
   box). Source-side fix only (author strut/rod as intact primitives, or use
   the regenerated spec). This is a good, concrete example for the SOP
   "author for editability" rules.

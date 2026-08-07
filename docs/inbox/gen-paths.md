# inbox: gen-paths (2026-08-02)

Out-of-slice notes for the orchestrator / other agents.

1. **Ground-truth pairs for Track D.** Once the APS Automation back-end
   (docs/generation-paths.md, path B) exists we can generate `.rvt` files
   whose *entire* content is known from the spec (e.g. exactly 4 walls, 1
   door). Diffing `Partitions/*` + `Global/ElemTable` between two such files
   that differ by one wall is the fastest way to localise element records in
   the binary. Same trick with an ODA BimRv trial write (path C). Suggest a
   TRACKER item: "produce spec-controlled .rvt corpus for differential
   decoding".
2. **Environment additions** made in this slice (venv `.venv`):
   `ifcopenshell==0.8.5` (+numpy, shapely), `pytest` (needed by
   `ifcopenshell.validate` express-rule executor), `jsonschema`. All installed
   from PyPI wheels via `uv pip install`; nothing built from source.
3. **KNOWLEDGE.md candidates:** IfcOpenShell 0.8.5 `geometry.create_2pt_wall`
   returns the representation but does not assign it (must call
   `assign_representation`); `validate(express_rules=True)` imports `_pytest`.
4. **Revit IFC open path is IFC2x3-scoped** per Autodesk help (link path
   supports IFC4). The IFC generator therefore needs a dual-schema emitter
   (IFC4 for Link, IFC2X3 + IfcWallStandardCase for Open). Recorded in the
   spec via `targets.ifc`.
5. `vendor/sketchit/` = shallow clone of Autodesk's SketchIt Design-Automation
   sample (JSON walls/floors -> .rvt) for reference; ~200 LOC add-in.

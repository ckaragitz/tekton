# cowork-engine — out-of-scope notes for the orchestrator

Slice: the Python engine in `skills/revit-bridge/scripts/`. Everything in
scope shipped; these are the things I found that live outside my paths.

## 1. The saved Design sample does NOT contain two defects the brief assumed

`samples/design-ifc/bs-area-e-electrical-room.ifc` is real and matches the
brief on: 11 products (6 boards, 3 transformers, 1 discrete accessory, 1
proxy), 50 `IfcTriangulatedFaceSet` (100% tessellated), every placement
identity, single storey, no `IfcSpace`, `Voltage` stored as `IfcLabel`.

BUT it has:
- **zero type objects** — no `IfcRelDefinesByType`, no `IfcXxxType` at all
  (so "types before: 11 duplicated" cannot be shown on this file; before = 0,
  all 11 elements untyped). The "one type per element" duplication is a
  property of the *newer* exporter code path described in
  `docs/design-ground-truth.md`, not of this saved export.
- **no clearance / swing / helper solids and no transparent materials** —
  the phantom-solid audit correctly finds 0 on this file.

Consequence: `harden_ifc.py` handles BOTH cases (merge duplicated types when
present; synthesise one shared type per identical-geometry group when
untyped -> 4 shared types on the sample), and the pytest suite covers
duplicate-type merging + phantom removal on a synthetic v1-defect fixture
(`tests/fixtures_ifc.py`) rather than on the sample. If you can save a newer
Design export that actually carries the duplicated types and the
`working_clearance` / `door_swing_clearance` solids, drop it in
`samples/design-ifc/` and the same tests will exercise the real thing.
KNOWLEDGE.md's ground-truth section should say the *saved* sample predates
types/clearances.

## 2. `spec/building.schema.json` needs two small additions (v0.2.0)

`spec/examples/electrical-room.json` (my deliverable) uses two keys the
wave-1 schema (`additionalProperties: false`) rejects:

1. top-level **`equipment`** array — the MEP profile `generate_ifc.py`
   consumes. Proposed `$defs.equipment`:
   `{kind: enum[panelboard,transformer,lightfixture,switchgear,proxy] |
   string, name, id, level, position: point2 (m), rotationDeg: number,
   elevation: number (mounting height above level), dims:{w,d,h}, ifcClass,
   predefinedType, typeName, tag, description, psets: object,
   typePsets: object}`; required: `kind`. `psets` values are scalar or
   `{value, type}` with `type` in the Design measure vocabulary
   (boolean|integer|count|real|voltage|current|power|length|identifier|
   text|label ...).
2. **`rooms[].psets`** (free-form object, same value contract) so room
   data (RoomInformation) rides on the `IfcSpace`.

The generator does not itself run jsonschema, so the example works today;
`gen_ifc_min.py`'s `check_specs()` would flag it if pointed at the file.

## 3. Generator scope limits worth a follow-up ticket

- Roof forms other than flat are emitted flat (a `note:` is printed).
- `defaults.autoOpenings` places one entrance door only (no auto windows).
- Doors/windows are simple prismatic representations from
  `ifcopenshell.api.geometry.add_door/window_representation`, no families.
- `columns`, `beams`, `grids` from the schema are not emitted yet.
- Curved (`kind: arc`) walls are treated as straight.

## 4. Cowork-sandbox unknowns (need one empirical run)

See the "Sandbox limits" section of `skills/revit-bridge/scripts/README.md`:
PyPI egress for `pip install ifcopenshell==0.8.5` (else pre-stage the two
manylinux wheels), and confirm the sandbox Python is 3.9–3.13. Runtime and
memory are non-issues at this scale (<1 s, tens of MB; no OCC kernel used).

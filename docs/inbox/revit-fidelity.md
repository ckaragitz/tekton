# inbox — revit-fidelity (references author) — out-of-slice notes

For the orchestrator to triage. Nothing here was acted on.

## 1. High-value follow-up: ship an import class-mapping file with the skill
Source-verified quirks in the Link IFC built-in map
(`vendor/revit-ifc/Source/Revit.IFC.Import/Utility/IFCCategoryUtil.cs`):
- `IfcCableCarrierSegment` (any predefined type, incl. `CONDUITSEGMENT`) →
  Cable Trays; the Conduits category is fed only by `IfcCableSegment`.
- `IfcElectricGenerator`, `IfcElectricFlowStorageDevice` (UPS/battery),
  `IfcElectricMotor`, untyped `IfcOutlet` → Generic Models (no map entry, no
  supertype fallback → warning "Setting IFC entity X to Generic Models").
Fix without lying about classes: ship a COMPLETE `importIFCClassMapping.txt`
(start from Revit's shipped file + our added rows; a partial file replaces the
whole built-in map). Proposed rows are in `references/mep-class-map.md` §3.
Task suggestion: F6 "class-mapping sidecar generator + SOP step (File ▸ Open
▸ IFC Options ▸ Load)".

## 2. Live-test needed: pre-seeded `<name>.ifc.sharedparameters.txt` (route B)
Derived from source (`ParametersToSet.AddParameterBase` reuses an existing
definition by exact name inside the existing sidecar file's group), NOT yet
run in Revit. If confirmed, the imported `PanelSchedule.*` parameters carry the
FIRM's GUIDs — schedules/tags key on them directly. Needs one Revit session
(trial or the brothers): (a) place seeded sidecar beside .ifc, (b) Link IFC,
(c) check the parameter GUID on an imported panel matches the firm's GUID.
If it fails, route A (schedule `PanelSchedule.*` directly) is the fallback and
the harden step should NOT emit the seeded file. Task: F7 "confirm shared-
parameter GUID adoption".

## 3. Design's shared-parameter file is not in this repo
`references/shared-parameters-mapping.md` quotes the documented GROUP/PARAM
structure but the literal file (GUIDs!) lives only in the Design project
(`exports/panelboard-shared-parameters.txt`). Someone with Design access should
copy it into the repo (suggest `skills/revit-bridge/assets/panelboard-shared-parameters.txt`)
so the harden step can emit the seeded sidecar deterministically. Its GUIDs
must never be regenerated.

## 4. SKILL.md wording to reconcile
- SKILL §6.2 says "let the auto-generated .ifc.sharedparameters.txt supply the
  parameters" — true, but the auto names are `PanelSchedule.PanelName` (Pset
  prefix) with importer GUIDs, not the firm's flat `PanelName`. §6.2 should
  point at route A/B in `references/shared-parameters-mapping.md`.
- SKILL says psets become "Project Parameters"; more exactly they arrive as
  bound instance *shared* parameters in the intermediate .ifc.RVT; the host
  binds the same GUIDs via Project Parameters to schedule linked values.
- The Autodesk IFC Manual claims the class-mapping file affects only Open, not
  Link; the open-source Link code demonstrably reads it. Treat manual as scope
  statement; our docs cite the code. Worth a footnote in the SOP.

## 5. APS pricing numbers unverified
Structure verified (rated API, 0.5 token/complex job, free monthly tier since
2025-12-08); exact free allowance + USD/token not retrievable from
aps.autodesk.com/pricing (dynamic page). Re-verify before quoting costs.
Design Automation lets us pick the Revit engine year → solves the "can't open
newer" rule for any generated .rvt.

## 6. Viewer-mode + Link IFC unverified
Whether Revit *viewer mode* can Link IFC (it must save the intermediate
.ifc.RVT while save is disabled) is unconfirmed; docs treat it as review-only.

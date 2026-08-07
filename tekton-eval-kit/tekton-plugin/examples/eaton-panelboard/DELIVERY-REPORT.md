# Delivery report — Eaton Pow-R-Line 4 panelboard (parametric equipment)

Prepared by tekton-ifc, 2026-08-03. This is the deliverable for the
panelboard you specified in Claude Design (`panel-meta.js`): a parametric
spec, the Revit-ready IFC generated from it, its validation, and the
shared-parameters bridge that makes the panel data land as your firm's real
Revit parameters.

## What we captured (from your `panel-meta.js` / `docs/design-ground-truth.md`)

`panel-spec.json` records the full parametric definition as one equipment
entry:

| Property | Value | IFC measure → Revit datatype |
|---|---|---|
| PanelName | `PANEL-A` | IfcLabel → TEXT |
| Voltage | 480 (numeric volts) | IfcElectricVoltageMeasure → ELECTRICAL_POTENTIAL |
| SystemDesignation | `480Y/277 V, 3PH, 4W` (human-readable) | IfcLabel → TEXT |
| Phases / Wires | 3 / 4 | IfcInteger → INTEGER |
| BusRating | 400 A | IfcElectricCurrentMeasure → ELECTRICAL_CURRENT |
| MainsType / MainsRating | Main Breaker / 400 A | IfcLabel / IfcElectricCurrentMeasure |
| ShortCircuitRatingkA | 65 (kA, plain number) | IfcReal → NUMBER |
| Mounting | Surface | IfcLabel → TEXT |
| NumberOfCircuits | 42 spaces | IfcCountMeasure → INTEGER |
| NeutralRating | 100% | IfcLabel → TEXT |
| DoorPosition / DoorSwingRadius | recorded as data (never geometry) | IfcLabel / IfcLengthMeasure |
| WorkingClearanceShown / Depth·Width·Height | false / 1.067 · 0.762 · 1.981 m | IfcBoolean / IfcLengthMeasure |
| Enclosure dimensions | W 0.508 m × H 1.372 m × D 0.190 m | (geometry + `revitbridge_Dimensions` type pset) |
| Manufacturer / Model / Reference | Eaton / Pow-R-Line 4 / PRL4-400MB-42 | type pset `Pset_ManufacturerTypeInformation` |
| Reference / IsMain / NumberOfCircuits | PRL4-400MB-42 / true / 42 | `Pset_ElectricDistributionBoardTypeCommon` |

Insertion point = bottom-centre of the enclosure back, mounting height
1.067 m (top of panel ≈ 2.44 m / 8 ft). The NEC 110.26 working clearance and
the door swing are **properties on the panel, not solid geometry** — so Revit
gets no phantom translucent clearance box.

## The generated file and its validation (real numbers)

Command run:

```
python skills/tekton-ifc/scripts/generate_ifc.py --spec panel-spec.json -o panelboard.ifc
python skills/tekton-ifc/scripts/validate_ifc.py panelboard.ifc --json panelboard-validation.json
```

Result: **`panelboard.ifc` — 98.8/100, Tier 1**, IFC4 with **0 schema
errors / 0 warnings**, 6,892 bytes, 92 entities.

| Check | Result |
|---|---|
| Geometry | 0/1 tessellated — clean `IfcExtrudedAreaSolid` box, shared via a representation map |
| Placement | Real insertion point at (0, 0, 1.067 m); movable & rotatable |
| Types | 1 shared `IfcElectricDistributionBoardType` (`Eaton Pow-R-Line 4 (style) - 400A MB - 42 space`), 0 untyped |
| Property sets | 2 occurrence psets (`PanelSchedule`, `Pset_ElectricDistributionBoardTypeCommon`) + type psets, 100% consistent, 0 electrical values stored as text |
| Units | METRE, OK |
| Only note | "single storey, no space" — expected: this is a standalone product model, not a room. It costs 1.2 points and does not affect the panel. |

Full report: `panelboard-validation.json`; the engine's raw report:
`report-generated.md`.

## What you get in Revit

Link `panelboard.ifc` (Insert ▸ **Link IFC**, origin-to-origin) and the panel
lands as an **Electrical Equipment** element: a true 0.508 × 1.372 × 0.190 m
box with a real insertion point, one shared type, and every value above as a
parameter — instance data (`PanelSchedule.*`, `Pset_ElectricDistributionBoardTypeCommon.*`)
on the element, catalogue data (`Pset_ManufacturerTypeInformation.*`) on the
type. You can move it, dimension to it, section it, tag it, put it on sheets,
and schedule it.

**Honest Tier statement.** This is **Tier 1**: a clean, movable, data-rich
DirectShape in the right category. It is **not** a native Eaton panelboard
family — Revit's IFC importer never creates electrical **connectors,
circuits, or the branded "Panel Schedule" view** from IFC. The circuit-by-
circuit panel schedule stays a Design deliverable (PDF/sheet) **or** becomes
real via **Tier 2**: placing a native panelboard family through the Revit API
(APS Design Automation add-in or a native `.rvt`). The good news for Tier 2:
your psets already map **1:1 onto your firm's shared parameters** (below), so
setting the family's parameters from this same spec is mechanical.

## How the psets map to your Revit shared parameters

Your firm's `panelboard-shared-parameters.txt` (group **Panelboard**)
defines exactly these eleven parameters, and our `PanelSchedule` property
names match them 1:1 on purpose. A copy in the correct Revit format is
delivered here as **`panelboard-shared-parameters.txt`** (see the GUID note
inside the file — if your firm already has this file with its own GUIDs, use
yours: in Revit the GUID *is* the parameter's identity).

| PanelSchedule property | Firm shared parameter | Revit DATATYPE |
|---|---|---|
| PanelName | PanelName | TEXT |
| Voltage | Voltage | ELECTRICAL_POTENTIAL |
| Phases | Phases | INTEGER |
| Wires | Wires | INTEGER |
| BusRating | BusRating | ELECTRICAL_CURRENT |
| MainsType | MainsType | TEXT |
| MainsRating | MainsRating | ELECTRICAL_CURRENT |
| ShortCircuitRatingkA | ShortCircuitRatingkA | NUMBER |
| Mounting | Mounting | TEXT |
| NumberOfCircuits | NumberOfCircuits | INTEGER |
| NeutralRating | NeutralRating | TEXT |

Two ways to close the gap between "IFC parameter" and "the firm's parameter"
(full detail: `skills/tekton-ifc/references/shared-parameters-mapping.md`):

**Route A — works today, zero setup.** After Link IFC, Revit auto-creates
each property as an instance parameter named `PanelSchedule.PanelName`,
`PanelSchedule.Voltage`, … in the sidecar `panelboard.ifc.sharedparameters.txt`
next to the IFC. To schedule them: Manage ▸ Shared Parameters ▸ Browse ▸ pick
that sidecar ▸ Manage ▸ Project Parameters ▸ add each as an instance parameter
bound to **Electrical Equipment** ▸ View ▸ Schedules ▸ Electrical Equipment ▸
add the fields, tick **Include elements in links**, filter
`IfcPredefinedType = DISTRIBUTIONBOARD`. That schedule *is* your panelboard
directory (name / voltage / phases / bus / mains / SCCR / spaces). The only
wart: field names carry the `PanelSchedule.` prefix (schedule column headings
are free text — rename them) and they are *new* parameters, not your firm's.

**Route B — make them BE your firm's parameters.** Because the psets are
correctly *typed* (Voltage as a real `IfcElectricVoltageMeasure`, not the
string "480Y/277 V"; BusRating as `IfcElectricCurrentMeasure`; SCCR as a plain
kA number), the importer will pick the same DATATYPE as your firm's file. If a
`panelboard.ifc.sharedparameters.txt` sidecar is placed next to the IFC
**before** the first link, containing definitions named
`PanelSchedule.PanelName`, … **with your firm's GUIDs**, the importer adopts
those definitions instead of inventing new GUIDs — the imported values land
directly on your firm's `PanelName`, `Voltage`, … parameters, so your existing
Electrical Equipment tags and schedule templates pick them up unchanged. (We
can generate that sidecar from `panelboard-shared-parameters.txt` on request;
one live Revit confirmation of this route is pending — Route A is the
guaranteed fallback.)

Type-level data (`Manufacturer`, `ModelLabel`, `ModelReference`) lands on the
DirectShape**Type** (Edit Type), so a catalogue change is one edit for every
panel of that type.

## Files in this bundle

| File | What it is |
|---|---|
| `panel-spec.json` | The full parametric spec (the single source of truth; edit this to change rating, dims, breaker count). |
| `panelboard.ifc` | **The file to link into Revit** — 98.8/100, Tier 1, 0 errors. |
| `panelboard-validation.json` | Full fidelity report. |
| `report-generated.md` | The engine's raw machine-generated report. |
| `panelboard-shared-parameters.txt` | Your firm's Panelboard shared-parameter file, in the correct Revit format, with the GUID note. |

## Next steps

1. Link `panelboard.ifc` and confirm the panel and its parameters (Route A).
2. If you want the values on your firm's *own* parameters, send us your real
   `panelboard-shared-parameters.txt` (with its GUIDs) and we deliver the
   pre-seeded sidecar (Route B).
3. When you need connectors, circuits and Revit's Panel Schedule view (Tier 2),
   this same `panel-spec.json` drives the native-family / `.rvt` path now
   being built — no re-entry of the panel data.


> **Update (2026-08-03):** `panelboard-shared-parameters.txt` in this bundle now carries the firm's **real** shared-parameter GUIDs (recovered from the Claude Design project), replacing the earlier seeded placeholders. Route B (adopting the firm's GUIDs so parameters bind to their existing schedules) is now viable as written.

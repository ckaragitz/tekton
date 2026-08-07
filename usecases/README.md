# Use-case bundles — what a customer receives today

Two real jobs from the family's Claude Design work, run end-to-end through
the existing, proven engine on 2026-08-03. Each folder is a complete customer
deliverable: source, delivered file(s), machine validation JSON, and a
customer-facing `DELIVERY-REPORT.md`. Every number below is pasted from the
actual validator output, not estimated.

## 1. `chicago-plenum-electrical-room/` — DDOT Coolidge, Area E bus-storage electrical room

Input: the real Design IFC export `samples/design-ifc/bs-area-e-electrical-room.ifc`
(6 panelboards B-HG4/B-LR1/B-HQ1/B-LQ1/B-SLQ1/B-SHQ1, 3 transformers
XFMR-LR1/XFMR-LQ1/XFMR-B-SLQ1, trapeze hangers, room shell).

| Stage | File | Score | Tier | Notes |
|---|---|---:|---|---|
| As exported (before) | `original.ifc` | **31.4/100** | Tier 0 | 11/11 frozen triangle blobs, 11/11 at world origin, 0 shared types, IFC4 0 errors |
| Hardened (delivered) | `hardened.ifc` | **89.0/100** | Tier 1 (partial) | 10/11 recovered as real extrusions with true insertion points, 4 shared types, GlobalIds preserved; only the merged strut/rod hanger stays a blob |
| Regenerated from spec | `generated.ifc` (from `room-spec.json`) | **100.0/100** | Tier 1 | 18 elements incl. walls/slab/door/`IfcSpace`, 4 instanced hanger racks, 7 shared types, 0 tessellated, 0 identity placements |

Proves both delivery paths on the real job: (a) *fix what you exported*
(harden) and (b) *regenerate from parameters* (spec → IFC).

## 2. `eaton-panelboard/` — Eaton Pow-R-Line 4 panelboard (parametric equipment)

Input: the parametric spec from `panel-meta.js` (`docs/design-ground-truth.md`
§3–4): 480Y/277 V 3-ph 4-wire, 400 A bus, main breaker, 42 spaces, 65 kA,
surface mount; W 0.508 × H 1.372 × D 0.190 m; `PanelSchedule` +
`Pset_ElectricDistributionBoardTypeCommon` + `Pset_ManufacturerTypeInformation`
psets with typed measures.

| File | Score | Tier | Notes |
|---|---:|---|---|
| `panelboard.ifc` (from `panel-spec.json`) | **98.8/100** | Tier 1 | IFC4 0 errors, clean box extrusion, real insertion point, 1 shared type, 100% pset consistency, 0 electrical values stored as text; the only note is "single storey / no space" (expected for a standalone product model) |

Also delivered: `panelboard-shared-parameters.txt` (the firm's Panelboard
shared-parameter file in correct Revit format) and the documented mapping
of every pset property onto the firm's shared parameters (Route A: zero-setup
`PanelSchedule.*` parameters; Route B: pre-seeded sidecar so values land on
the firm's own parameter GUIDs).

## What is native today vs. what is coming — the honest picture

**Native today — IFC Tier 1 (this whole `usecases/` tree).** For any job we
can, today, deliver an IFC that links into any Revit 2019+ as **correctly-
categorized, correctly-placed, true-dimension, movable elements carrying the
schedule data as parameters**, plus a delivery report and the shared-parameter
bridge. Both real use cases above are at Tier 1 (89.0 hardened / 98.8 and
100.0 generated). This is the ceiling for *any* IFC file, and we are at it.
What Tier 1 is NOT, and never will be from IFC: parametric families with
grips, **MEP connectors, circuits, or Revit's branded Panel Schedule view** —
Revit's IFC importer never creates those, from any IFC.

**Coming — native `.rvt` authoring (Tier 2, the real families and circuits).**
The native writer pipeline is **proven end-to-end** against Autodesk's own
reader (`docs/acceptance-log.md` Batch 3/4): V15 re-wrote a whole `.rvt` and
it rendered; V18/V19 were the first *authored content changes* — our own text
rendered on a Revit sheet through the full decode → edit → encode → ECC →
CFB chain, with record stamps confirmed non-validating (V18) and correctly
computed (V19). What is **not yet done** are the per-element authoring
recipes — placing a panelboard family instance, its SketchPlane face host,
symbols, and eventually circuits — which are in progress per
`docs/writer/mutation-plan.md` (element-creation recipe, save invariants, 19
decoded specimens incl. MEP panelboard/circuit/receptacle). So today a
customer gets Tier-1 IFC; the `.rvt` files delivering true native panelboard
families and circuits are the next milestone, and both use cases above are
staged for it — the same `room-spec.json` / `panel-spec.json` (tags, classes,
insertion points, full schedule data) is exactly the input the family-
placement path consumes, so nothing is re-entered.

## Reproduce

All commands run against `/Users/ck/dev/things/tekton/.venv/bin/python`
and the scripts in `skills/tekton-ifc/scripts/`
(`validate_ifc.py`, `harden_ifc.py`, `report.py`, `generate_ifc.py`); exact
invocations are printed in each `DELIVERY-REPORT.md`.

## Native `.rvt` deliverables (added 2026-08-03) — ACCEPTED BY AUTODESK

- `chicago-plenum-electrical-room/electrical-room.rvt` — the room generated
  as a NATIVE Revit file by `tools/spec_to_rvt.py` from `room-spec.json`
  (3 walls, 6 panelboards on 480V/400A families, 3 x 500 kVA transformers).
  Translates in the Autodesk Viewer (V23).
- `chicago-plenum-electrical-room/electrical-room-with-walls.rvt` — the same
  room produced by the FULLY AUTOMATED chain
  `hardened.ifc -> tools/ifc_to_spec.py -> tools/spec_to_rvt.py` with zero
  hand-authoring: equipment at the export's recovered positions plus four
  perimeter walls synthesized from the room-shell footprint (V26).
- Created geometry is VISUALLY CONFIRMED (the generated model's whole-model
  {3D} shows the added cluster and grown extents vs the untouched control).
Honest caveats: panels are placed unhosted (re-host to walls in Revit),
circuits / panel schedules are not authored yet, and everything targets
Revit 2026 — see plugin/docs/HONEST-STATUS.md.

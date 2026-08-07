# Delivery report — Area E bus-storage electrical room (Chicago-plenum job)

Prepared by tekton-ifc, 2026-08-03. This bundle is what you would receive
today for the electrical room you built in Claude Design and exported as
`bs-area-e-electrical-room.ifc`.

## The one-paragraph summary

Your original Design export was a perfectly valid IFC4 file but scored
**31.4/100 (Tier 0)** on our Revit-fidelity check: every panel, transformer
and hanger would have come into Revit as a **frozen blob with its insertion
point at the world origin** — visible, but not something you can move,
dimension to sensibly, or reuse. We ran it through the hardening engine and
delivered `hardened.ifc`, which scores **89.0/100 (Tier 1 partial)**: 10 of
your 11 elements are now clean box extrusions with **real insertion points**
(so you can move/rotate/dimension them in Revit), grouped into **4 shared
types**, with all of your panel and transformer schedule data preserved as
element parameters. We also proved we can *regenerate the same room from a
parameter file* (`room-spec.json` → `generated.ifc`), which scores
**100.0/100 (Tier 1)** — that is the path we use when you change a panel or
add a rack and want a fresh file in seconds instead of re-modelling.

## Before / after — the actual validation numbers

| Metric | `original.ifc` (as exported) | `hardened.ifc` (delivered) | `generated.ifc` (regenerated from spec) |
|---|---:|---:|---:|
| Score | **31.4 / 100** | **89.0 / 100** | **100.0 / 100** |
| Tier | Tier 0 (v1-like) | Tier 1 (partial) | Tier 1 |
| IFC schema | IFC4, 0 errors | IFC4, 0 errors | IFC4, 0 errors |
| Elements | 11 | 11 | 18 (adds walls/slab/door/space, 4 hanger racks) |
| Triangle-mesh (frozen) elements | 11 / 11 (100%) | 1 / 11 (9%) | 0 / 18 (0%) |
| Elements at world origin (no insertion point) | 11 / 11 | 1 / 11 | 0 / 18 |
| Shared type objects | 0 (11 untyped) | 4 (0 untyped) | 7 (0 untyped) |
| Extruded solids | 0 | 61 | all solids parametric |
| Rooms / spaces | 0 | 0 | 1 (`Electrical Room E101`) |
| Property sets | 4 (100% consistent) | 4 (100% consistent) | 4 (100% consistent) |
| File size | 83,780 B | 81,767 B | 43,919 B |

Full machine reports: `validation-before.json`, `validation-after.json`,
`generated-validation.json`; hardening action log: `harden-report.json`.

What the hardening engine did (from `harden-report.json`): 4 shared types
created; 10 products converted from triangle soup to true box extrusions
(61 boxes recovered), each with its insertion point moved to the box's real
base-centre; owner-history fields repaired; **all 11 element GlobalIds
preserved** (so re-linking updates in place instead of duplicating).

## What imports into Revit as clean, categorized elements

Link `hardened.ifc` (Insert ▸ Link IFC — see checklist below) and you get:

| Element | IFC class | Revit category | Result |
|---|---|---|---|
| B-HG4, B-LR1, B-HQ1, B-LQ1, B-SLQ1, B-SHQ1 (6 panelboards) | IfcElectricDistributionBoard | **Electrical Equipment** | Clean box solid, real insertion point at mounting height 1.067 m along the north wall, one shared type, `PanelSchedule` data (voltage, feeder, top-of-panel AFF, grid centreline) as instance parameters. |
| XFMR-LR1, XFMR-LQ1, XFMR-B-SLQ1 (3 transformers) | IfcTransformer | **Electrical Equipment** | Clean solid, real insertion point on the floor line, one shared type, `TransformerSchedule` data as parameters. |
| Room shell — Area E (proxy) | IfcBuildingElementProxy | Generic Models | Clean solid (the cut-away shell you modelled for viewing). In `generated.ifc` this becomes real walls (`IfcWall` → Walls), a slab, a door, and an `IfcSpace` room instead — see "regeneration" below. |

Because 6 panels share one type and 3 transformers share another, you can
edit the manufacturer / model data once per type instead of six times.

## What remains a DirectShape (frozen blob) and why

| Element | Why | What to do about it |
|---|---|---|
| **Trapeze hangers** (1-5/8 in strut on 3/8 in rods, rack at 16 ft 6 in AFF) | The Design model built the hangers with a `merge()` helper that baked the strut and rods into anonymous triangle geometry with world coordinates burned into the vertices. Hardening can only recover *exact upright boxes*; a merged strut/rod assembly is not a box, so it correctly stays tessellated (400 triangles) and keeps an identity placement. It still imports — right category, taggable, schedulable — but it cannot be moved/rotated about a real insertion point. | Two options: (1) accept it as-is (coordination geometry rarely needs to move), or (2) use the regenerated path — `room-spec.json` models each hanger rack as an `IfcDiscreteAccessory` bracket with a real insertion point at 16 ft 6 in AFF and one shared type instanced 4×; that file scores 100/100. This is the single fix left between 89 and 100 on the hardened file. |

One more data note carried over from your export: 6 electrical values were
written as plain text (e.g. `Voltage` = the string `"480Y/277 V"` rather than
the number 480). They still import — but as **Text** parameters, so they will
not bind to a unit-aware ELECTRICAL_POTENTIAL parameter. Hardening never
rewrites your data, so `hardened.ifc` keeps them as text; the regenerated
`generated.ifc` fixes this by writing `Voltage` as a real
`IfcElectricVoltageMeasure` (480) with the human-readable system string kept
separately (validator: "0 untyped electrical values" on that file).

Also honest: **every** element above — even the clean Tier-1 ones — arrives
in Revit as a **DirectShape**, not a parametric family. That is what any IFC
becomes in Revit. See the Tier statement below.

## The Tier-1 / Tier-2 honesty statement (read this before promising anything downstream)

**Tier 1 — clean reference geometry (this delivery, today).** Every
panelboard and transformer lands in the right Revit category, at the right
position with a real insertion point, at true dimensions, with your schedule
data as element parameters that tags and schedules can read. You can move it,
hide it, dimension to it, section it, and put it on sheets. It comes in as
**DirectShape** geometry: not a parametric family — no size grips, and **no
electrical connectors, so no circuits or Revit-native Panel Schedules.** This
is the ceiling for *any* IFC file, and this bundle is at that ceiling.

**Tier 2 — native MEP families with working connectors and circuits.**
Revit's IFC importer **never** creates functioning connectors, circuits or
Revit "Panel Schedule" views from IFC — no matter how good the IFC is. Tier 2
requires placing real families through the Revit API (an add-in run inside
Revit or in Autodesk's cloud, APS Design Automation) or a native `.rvt`. Both
routes are being built (see the top-level `usecases/README.md` for status).
Everything Tier 2 needs is already in this bundle: per-element tag, class →
target category, insertion point in metres, type name, and the full schedule
data — so the wiring step is minutes, not a re-model.

We are **not** claiming native families, connectors, or circuits from these
IFC files. Correct phrasing: *"correctly-categorized, correctly-placed Revit
elements carrying your schedule data."*

## The regeneration path (why `room-spec.json` matters to you)

`room-spec.json` is a plain, editable description of the *same* room — the
6 panelboards (B-HG4, B-LR1, B-HQ1, B-LQ1, B-SLQ1, B-SHQ1), the 3 transformers
(XFMR-LR1, XFMR-LQ1, XFMR-B-SLQ1), 4 hanger racks, the room space, walls, slab
and door — with the equipment positions taken from *your own export's*
recovered insertion points (B-HG4 centreline = 1.399 m from the west wall,
matching your `CenterlineFromGrid16BS` callout). Working clearances are
recorded as `PanelSchedule` properties (`WorkingClearanceDepth/Width/Height`),
**never as solid geometry**, so you get no phantom translucent boxes in the
model. Running:

```
python skills/tekton-ifc/scripts/generate_ifc.py --spec room-spec.json -o generated.ifc --validate
```

produced `generated.ifc` at **100.0/100, Tier 1** (0 tessellated, 0
identity placements, 7 shared types, 1 space, 100% pset consistency). So the
next time a panel changes rating or a rack moves, we edit the spec and hand
you a new file — no re-drawing.

## Revit-side handoff checklist (do these once per delivery)

1. **Link, don't Open.** Revit ▸ Insert ▸ **Link IFC** ▸ pick `hardened.ifc`
   (or `generated.ifc`) ▸ Positioning "Auto – Origin to Origin". Revit writes a
   sidecar `hardened.ifc.RVT` + `hardened.ifc.sharedparameters.txt` next to it
   — keep them together. Do **not** use File ▸ Open ▸ IFC (legacy path; drops
   most schedule data).
2. **Make the schedule data usable.** Manage ▸ Shared Parameters ▸ Browse ▸
   pick the sidecar `hardened.ifc.sharedparameters.txt` (parameters appear as
   `PanelSchedule.PanelName`, `PanelSchedule.Voltage`, …) ▸ Manage ▸ Project
   Parameters ▸ add each as an instance parameter bound to **Electrical
   Equipment** ▸ View ▸ Schedules ▸ Electrical Equipment ▸ add the fields,
   tick **Include elements in links**, filter `IfcPredefinedType =
   DISTRIBUTIONBOARD`. That schedule is your panelboard directory sheet.
3. **Verify categories.** Panels and transformers → Electrical Equipment;
   hangers → Specialty Equipment / Generic Models. If anything shows in
   Generic Models unexpectedly, tell us — we fix the class in the file, not in
   Revit (Revit-side re-categorising is lost on re-link).
4. **Version note.** IFC is version-agnostic: this links into any Revit 2019
   or newer, and the sidecar `.RVT` is created by *your* Revit so it is
   automatically your version. (A native `.rvt`, when we deliver those, must
   match your Revit version — we will ask first.)
5. **Units / origin.** Model is metres SI; Revit converts on link. Switch
   display to feet-inches under Manage ▸ Project Units if you prefer.

## Files in this bundle

| File | What it is |
|---|---|
| `original.ifc` | Your untouched Design export (kept for reference / diffing). |
| `hardened.ifc` | **The file to link into Revit.** Semantics-preserving rewrite, 89.0/100 Tier 1 (partial). |
| `validation-before.json` | Full fidelity report of the original (31.4, Tier 0). |
| `validation-after.json` | Full fidelity report of the hardened file (89.0, Tier 1 partial). |
| `harden-report.json` | Every action the hardening engine took, before/after metric table. |
| `room-spec.json` | Editable parametric spec of this same room (the regeneration source). |
| `generated.ifc` | The room regenerated from the spec — 100.0/100 Tier 1. |
| `generated-validation.json` | Full fidelity report of the regenerated file. |
| `report-generated.md` | The engine's raw machine-generated report (element table, checklist) that this document summarises. |

## Next steps

1. Link `hardened.ifc` into your Revit project and confirm the panels sit on
   the north wall at the right heights; send us any element that looks wrong
   (a screenshot + the element's IfcGUID from the Properties palette).
2. Tell us whether you want the hanger racks movable (we switch you to the
   regenerated `generated.ifc`, which fixes the one remaining blob).
3. Decide on Tier 2: when you need real panelboard families with circuits and
   a Revit Panel Schedule, we run the same spec through the family-placement
   path (in progress) — nothing you did here is thrown away.

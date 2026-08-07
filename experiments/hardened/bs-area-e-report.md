# Revit-readiness report: `bs-area-e-electrical-room.ifc`

**Score: 31.4/100** — **Tier 0 (v1-like) -- imports as frozen DirectShape blobs with baked coordinates**

- IFC schema `IFC4` — valid (0 schema errors)
- 11 model elements; 11 triangle-mesh (100% tessellated), 11 without a real insertion point
- 1 level(s), 0 room/space(s), 0 type object(s), 0 phantom annotation solid(s)
- File size 83,780 bytes

## What happens when you Link this IFC into Revit

Revit's IFC importer turns every IFC element into a **DirectShape** in the mapped category (see the table below): visible, taggable, schedulable, filterable, with your IFC property sets available as parameters. It never creates parametric families or MEP connectors from IFC — that is a Revit limitation, not something the file can fix. So the honest ceiling for any IFC is **Tier 1**; **Tier 2** needs the Revit API.

| Tier | What it means | How you get it |
|---|---|---|
| **Tier 1** | Clean solid geometry in the right category, at the right place, movable/rotatable, one shared type per catalogue item, schedule data on the element. Still a DirectShape (no grips, no circuits). | A good IFC — this file, once its score is high. |
| **Tier 2** | Real Revit families (hosted, connectable), circuits, panel schedules that live-update. | Only via the Revit API — an APS Design Automation add-in placing families from the same spec. The panelboard shared-parameters file maps the psets 1:1. |

## Before / after hardening

| metric | before | after |
|---|---:|---:|
| score | 31.4 | 89.0 |
| tier | Tier 0 (v1-like) -- imports as frozen DirectShape blobs with baked coordinates | Tier 1 (partial) -- imports usably but some elements come in as frozen blobs / at the origin |
| elements | 11 | 11 |
| type_objects | 0 | 4 |
| duplicate_type_objects | 0 | 0 |
| untyped_elements | 11 | 0 |
| tessellated_elements | 11 | 1 |
| extruded_solids | 0 | 61 |
| identity_placements | 11 | 1 |
| spaces | 0 | 0 |
| size_bytes | 83780 | 81767 |

Actions taken: owner history fields repaired: 2, shared types created: 4, products converted to extrusions: 10, boxes converted: 61, product globalids preserved: 11, products before: 11, products after: 11

## Element-by-element: what will and won't be editable in Revit

| Element | IFC class | Revit category | Geometry | In Revit you CAN | You CANNOT |
|---|---|---|---|---|---|
| Bus storage electrical room shell — Area E | IfcBuildingElementProxy | Generic Models | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| XFMR-LR1 | IfcTransformer | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| XFMR-LQ1 | IfcTransformer | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| XFMR-B-SLQ1 | IfcTransformer | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| B-HG4 | IfcElectricDistributionBoard | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| B-LR1 | IfcElectricDistributionBoard | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| B-HQ1 | IfcElectricDistributionBoard | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| B-LQ1 | IfcElectricDistributionBoard | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| B-SLQ1 | IfcElectricDistributionBoard | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| B-SHQ1 | IfcElectricDistributionBoard | Electrical Equipment | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |
| Trapeze hangers — 1-5/8 in strut on 3/8 in rods, rack at 16 ft 6 in AFF | IfcDiscreteAccessory | Specialty Equipment / Generic Models | triangle mesh | see, tag, schedule, filter by category, read parameters | move/rotate about a real insertion point, edit dimensions, connect circuits |

## Top fixes to raise the tier

1. **geometry_parametric** — 11/11 elements are triangle-mesh solids (100% tessellated). Emit IfcExtrudedAreaSolid (box/profile extrusions) instead -> clean, dimensionally-editable solids instead of frozen faceted blobs. harden_ifc.py converts exact boxes automatically.
2. **placements** — 11/11 elements have identity placements (coordinates baked into vertices; insertion points lost). Emit real IfcLocalPlacement positions per element so they can be moved/rotated in Revit.
3. **typing** — 11/11 elements have no type object. Add a shared IfcXxxType per model number so Revit gets one type per catalogue item (type parameters, tags, schedules).
4. **instancing** — 9 elements repeat identical geometry verbatim (528 duplicated triangles). Use IfcRepresentationMap + IfcMappedItem instancing.
5. **spatial** — Single storey and no IfcSpace: add one IfcBuildingStorey per real level and IfcSpace for rooms so Revit gets Levels and space data.

## Schedule data and parameters

Property sets found: `PanelSchedule`, `RoomInformation`, `SupportSchedule`, `TransformerSchedule`.

These arrive in Revit as IFC parameters on the DirectShapes. To make them proper **shared parameters** you can schedule and tag, bind the project's `panelboard-shared-parameters.txt` (Manage ▸ Shared Parameters) — property names match parameter names 1:1 (PanelName, Voltage, Phases, Wires, BusRating, MainsType, MainsRating, ShortCircuitRatingkA, Mounting, NumberOfCircuits, NeutralRating).

Note: 6 electrical value(s) are stored as text (e.g. `Voltage` as a label). They still import, but as text — export them as IfcElectricVoltage/Current/Power measures for unit-aware parameters.

## How to load it into Revit

1. Revit ▸ **Insert ▸ Link IFC** (not File ▸ Open) and pick the hardened file.
2. Levels come from the IFC storeys; elements land in the categories listed above.
3. For real electrical families and circuits (Tier 2), run the APS automation path from the same building spec — the IFC stays as the coordination reference.

_Generated by revit-bridge 0.1.0 from `bs-area-e-electrical-room.ifc`._

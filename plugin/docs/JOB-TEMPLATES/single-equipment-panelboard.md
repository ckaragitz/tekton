# JOB TEMPLATE — Single Equipment: Panelboard (Eaton Pow-R-Line spec → IFC + parameters)

**Hand this file to Claude.** For when the job is one piece of equipment,
not a whole room: model a panelboard once, get it into Revit as a
correctly-categorized element carrying the full panel-schedule data as
parameters, and reuse the type across every project. Grounded in your real
Eaton Pow-R-Line spec (`docs/design-ground-truth.md` §3–4).

**Honesty line:** the panelboard lands as *Electrical Equipment* with a real
insertion point, true dimensions, and every schedule value as a parameter —
schedulable, taggable, dimensionable. It is not a native family: no
breaker/connectors inside, no Revit-native panel schedule (Tier 2 — see
`plugin/docs/HONEST-STATUS.md`).

---

## 1. The spec — FILL IN / CONFIRM

```
Tag / PanelName ....... [B-HG4]
Manufacturer / model .. [Eaton Pow-R-Line 4]      (typeName below is the type key)
Enclosure (m) ......... W [0.508]  x  H [1.372]  x  D [0.190]     <- Pow-R-Line 4, 42-space
Voltage ............... [480Y/277 V]     Phases [3]   Wires [4]
Bus rating ............ [400 A]         Mains [Main breaker, 400 A]
Circuits (spaces) ..... [42]
Short-circuit rating .. [65 kA]         Neutral [100%]
Mounting .............. [Surface]       Mounting height (bottom of enclosure) [1.067 m]
Door .................. [Left hinge, swing radius 0.508 m]
Working clearance ..... [NEC 110.26: 0.914 D x 0.762 W x 1.981 H]  -- DATA, never a solid
Position (x, y) m ..... [0, 0]          Rotation [0 deg]
```

## 2. Path 1 — model it in Design (best result; PLAYBOOK 1)

Prompt to Design:

> Build ONE panelboard as a tagged `THREE.Group` per the tekton-ifc
> tagging contract, using the spec in this template. Origin = bottom-centre
> of the enclosure back; enclosure is an un-baked
> `BoxGeometry(0.508, 1.372, 0.190)` lifted by half its height; place the
> group at (x, y) with `position` and set mounting height via the group's
> y. Build ONE breaker geometry and reuse it 42 times (shared geometry ⇒
> instanced). `userData.ifc`: `ifcClass 'IFCELECTRICDISTRIBUTIONBOARD'`,
> `predefinedType 'DISTRIBUTIONBOARD'`, `name`/`tag` = the tag, `typeName
> 'Eaton Pow-R-Line 4 (style) - 400A MB - 42 space'`, storey 'Level 1'.
> `PanelSchedule` pset with EXACTLY these keys/types: PanelName,
> Voltage{voltage}, Phases{integer}, Wires{integer}, BusRating{current},
> MainsType, MainsRating{current}, ShortCircuitRatingkA{real}, Mounting,
> NumberOfCircuits{count}, NeutralRating, DoorPosition,
> DoorSwingRadius{length}, WorkingClearanceShown{boolean},
> WorkingClearanceDepth/Width/Height{length}. Type psets
> `Pset_ManufacturerTypeInformation` (Manufacturer 'Eaton', ModelLabel
> 'Pow-R-Line 4', ModelReference 'PRL4'). No clearance solid. Install
> `assets/ifc-export.js` as `./ifc-export.js`, export IFC.

Full worked code for this exact panel: `plugin/docs/PLAYBOOK-claude-design.md`
Step 2. Then run PLAYBOOK 2 (validate → deliver) on the export.

## 3. Path 2 — no model, straight from the spec (fastest)

Save this as `panel.json` (edit values from Section 1; positions in metres):

```json
{
  "specVersion": "0.1.0",
  "project": { "name": "Panelboard B-HG4", "author": "tekton-ifc" },
  "levels": [ { "id": "L1", "name": "Level 1", "elevation": 0.0 } ],
  "equipment": [ {
    "kind": "panelboard", "name": "B-HG4", "level": "L1",
    "position": [0, 0], "rotationDeg": 0, "elevation": 1.067,
    "dims": { "w": 0.508, "d": 0.190, "h": 1.372 },
    "typeName": "Eaton Pow-R-Line 4 (style) - 400A MB - 42 space",
    "description": "Panelboard, 480Y/277 V",
    "psets": {
      "PanelSchedule": {
        "PanelName": "B-HG4",
        "Voltage":   { "value": 480, "type": "voltage" },
        "Phases":    { "value": 3,   "type": "integer" },
        "Wires":     { "value": 4,   "type": "integer" },
        "BusRating": { "value": 400, "type": "current" },
        "MainsType": "Main breaker",
        "MainsRating": { "value": 400, "type": "current" },
        "ShortCircuitRatingkA": { "value": 65, "type": "real" },
        "Mounting": "Surface",
        "NumberOfCircuits": { "value": 42, "type": "count" },
        "NeutralRating": "100%",
        "WorkingClearanceDepth":  { "value": 0.914, "type": "length" },
        "WorkingClearanceWidth":  { "value": 0.762, "type": "length" },
        "WorkingClearanceHeight": { "value": 1.981, "type": "length" }
      }
    },
    "typePsets": {
      "Pset_ManufacturerTypeInformation": { "Manufacturer": "Eaton", "ModelLabel": "Pow-R-Line 4", "ModelReference": "PRL4" }
    }
  } ]
}
```

Then (Cowork prompt: *"generate a Tier-1 IFC from the attached panel.json,
validate it, and give me the delivery report"*), or locally:

```bash
python skills/tekton-ifc/scripts/generate_ifc.py --spec panel.json -o out/B-HG4.ifc --validate
python skills/tekton-ifc/scripts/validate_ifc.py out/B-HG4.ifc --json out/validate.json
python skills/tekton-ifc/scripts/report.py out/validate.json -o out/delivery-report.md
```

Verified run of exactly this spec (2026-08-03): the panel validates as
`IfcElectricDistributionBoard  B-HG4  Eaton Pow-R-Line 4  Level 1
mapped(swept)`, component scores `geometry_parametric=1.0, placements=1.0,
typing=1.0` (the only note is "single storey / no IfcSpace" — irrelevant
for one item), output `B-HG4.ifc` = 4.7 KB.

The minimal legal spec is just
`{"levels":[{"name":"Level 1","elevation":0}],"equipment":[{"kind":"panelboard","name":"B-HG4","position":[0,0]}]}`
— everything else defaults. Full schema: `spec/building.schema.json`.
Reference: the 6-panel version of this (`spec/examples/electrical-room.json`)
generates at **100/100 Tier 1**, each panel `mapped(swept)` = shared type +
real placement + extrusion (measured; PLAYBOOK 3 §3).

## 4. Make the parameters land in Revit

The `PanelSchedule` keys equal the firm's shared-parameter names on
purpose. After **Link IFC** in Revit: *Manage → Shared Parameters → Browse*
→ `panelboard-shared-parameters.txt`, then add each as a **Project
Parameter** bound to *Electrical Equipment*:

| Property | Shared-param datatype |
|---|---|
| PanelName | TEXT |
| Voltage | ELECTRICAL_POTENTIAL |
| Phases | INTEGER |
| Wires | INTEGER |
| BusRating | ELECTRICAL_CURRENT |
| MainsType | TEXT |
| MainsRating | ELECTRICAL_CURRENT |
| ShortCircuitRatingkA | NUMBER |
| Mounting | TEXT |
| NumberOfCircuits | INTEGER |
| NeutralRating | TEXT |

Now every panel of this typeName in the firm is one shared type carrying
`Manufacturer/ModelLabel`, and each instance carries its schedule. Reuse the
`typeName` string verbatim across jobs to keep it that way.

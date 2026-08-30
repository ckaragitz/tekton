# JOB TEMPLATE — Electrical Room Package (Chicago-plenum style)

**Hand this file to Claude** (Design → Cowork/chat → Revit). It is a complete
brief: fill in the blanks in Section 1, keep the rest. Modeled on the real
DDOT Coolidge "Area E bus storage electrical room" job.

**What you get:** a coordination-grade electrical room — the room, its
panelboards and transformers on real insertion points, hanger racks, panel
& transformer schedule data as parameters — as a **hardened Tier-1 IFC**
plus a delivery report and the Revit link checklist. Renderings, the
one-line, and the schedule tables stay in Design as documents.

**Honesty line (say it up front):** Tier 1 = correctly-categorized,
correctly-placed elements with schedule data as parameters. Wiring,
circuits, and Revit-native panel schedules are Tier 2 and are finished in
Revit (see `plugin/docs/HONEST-STATUS.md`).

---

## 1. Job inputs — FILL THESE IN

```
Project name .......... [DDOT Coolidge — Area E bus storage electrical room]
File name ............. [bs-area-e-electrical-room]
Firm / author ......... [C. Karagitz Electric]
Levels ................ [Level 1 @ 0 m; Mezzanine/T.O. structure @ 3.0 m]
Room .................. [Electrical Room E101; footprint 10.36 x 4.88 m; height 6.1 m]

Panelboards (one line each: tag | volts | phases/wires | bus A | mains | ckts | mounting | pos x,y m | mount ht m):
  [B-HG4  | 480Y/277 | 3ph 4W | 400 | MB 400  | 42 | Surface | 1.6, 4.73 | 1.07]
  [B-HQ1  | 480Y/277 | 3ph 4W | 400 | MB 400  | 42 | Surface | 3.4, 4.73 | 1.07]
  [B-SHQ1 | 480Y/277 | 3ph 4W | 400 | MB 400  | 42 | Surface | 5.2, 4.73 | 1.07]
  [B-LQ1  | 208Y/120 | 3ph 4W | 100 | MLO 100 | 42 | Surface | 1.6, 0.15 | 1.07]
  [B-LR1  | 208Y/120 | 3ph 4W | 100 | MLO 100 | 42 | Surface | 3.4, 0.15 | 1.07]
  [B-SLQ1 | 208Y/120 | 3ph 4W | 100 | MLO 100 | 42 | Surface | 5.2, 0.15 | 1.07]

Transformers (tag | kVA | primary→secondary | pos x,y m):
  [XFMR-LQ1   | 45 | 480→208Y/120 | 7.5, 4.5]
  [XFMR-LR1   | 45 | 480→208Y/120 | 8.8, 4.5]
  [XFMR-B-SLQ1| 45 | 480→208Y/120 | 7.5, 0.6]

Hangers ............... [trapeze racks along north wall @ Mezzanine, 1.2 m o.c.]
Clearances ............ [NEC 110.26: 0.914 D x 0.762 W x 1.981 H in front of each panel] (DATA ONLY)
guidSeed .............. [coolidge-area-e]   (keep the same for every re-export)
```

## 2. The three stages

### Stage A — Model + export in Claude Design (PLAYBOOK 1)

Prompt to Design:

> Build the electrical room from the inputs in this job template using the
> tekton-ifc tagging contract: metres/y-up, one tagged `THREE.Group` per
> panel, transformer and hanger rack, positioned via `group.position` (never
> baked vertices), un-baked `BoxGeometry` primitives. Give panels sharing a
> spec the SAME `typeName` (e.g. `Eaton Pow-R-Line 4 (style) - 400A MB - 42
> space`) so they share one Revit type. Put the panel schedule in a
> `PanelSchedule` pset using exactly the shared-parameter names (PanelName,
> Voltage[voltage], Phases[integer], Wires[integer], BusRating[current],
> MainsType, MainsRating[current], ShortCircuitRatingkA[real], Mounting,
> NumberOfCircuits[count], NeutralRating) plus WorkingClearanceDepth/Width/
> Height[length] and DoorSwingRadius[length]. Draw NO clearance solids — if
> you sketch one for the render, name it `working_clearance`. Install the
> plugin's `assets/ifc-export.js` as `./ifc-export.js`, set
> `stage.ifcMeta` (projectName, fileName, storeys, guidSeed
> 'coolidge-area-e', geometry 'auto'), then export IFC.

Also produce in Design (stay as documents): the one-line, the panel
schedule tables, the transformer schedule, renderings for the submittal.

### Stage B — Harden + deliverables (PLAYBOOK 2 in Cowork, or these commands)

Attach the exported `.ifc` and say: *"Run the electrical-room-package job
on this file."* Under the hood:

```bash
pip install -r skills/tekton-ifc/scripts/requirements.txt                    # once per sandbox
python skills/tekton-ifc/scripts/validate_ifc.py in.ifc --json out/validate.json
python skills/tekton-ifc/scripts/harden_ifc.py   in.ifc -o out/hardened.ifc --report out/harden.json
python skills/tekton-ifc/scripts/validate_ifc.py out/hardened.ifc --json out/validate-after.json   # errors=0
python skills/tekton-ifc/scripts/report.py       out/validate.json --compare out/harden.json -o out/delivery-report.md   # describes out/hardened.ifc (its validate-after.json sits beside harden.json)
```

**Acceptance for this stage:** `schema errors=0`, tier ≥ `Tier 1
(partial)`, every panel shows its `PanelSchedule` pset, each distinct
`typeName` appears once, no clearance solids in the inventory. Reference:
this exact room, exported v1 and hardened, went **31.4 → 89.0** (measured;
see PLAYBOOK 3). A v2 export starts near Tier 1 and needs little hardening.

If there's no Design model, skip Stage A: the same room ships as a
worked spec (`spec/examples/electrical-room.json`, 6 panels + 3 xfmrs) —
`python skills/tekton-ifc/scripts/generate_ifc.py --spec
spec/examples/electrical-room.json -o out/room.ifc --validate` → **100/100
Tier 1**. Copy that spec and edit the equipment list instead.

### Stage C — Deliver

Send, in one message:
1. `hardened.ifc` — link this into Revit.
2. `delivery-report.md` — the Tier 1/Tier 2 line, per-element Revit
   category preview, before/after table, pre-filled checklist.
3. `panelboard-shared-parameters.txt` guidance (bind to *Electrical
   Equipment* so `Voltage`/`BusRating`/`NumberOfCircuits` show as
   parameters — steps in `skills/tekton-ifc/references/shared-parameters-mapping.md`).
4. **Tier 2 handoff table** for the Revit user: per panel — tag, target
   family/category, insertion point (m), type, schedule values — so wiring
   the circuits takes minutes, not a remodel.
5. From Design: one-line, schedule tables, renderings.

Revit steps for the recipient: *Insert → Link IFC* (not Open) → Auto –
Origin to Origin → bind the shared parameters → check panels land in
*Electrical Equipment*.

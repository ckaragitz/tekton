---
name: tekton-ifc
description: "Author, export, validate, harden, and hand off 3D building/MEP models from Claude Design (three.js three-d-stage pages) so they land in Autodesk Revit as clean, correctly-categorized, as-editable-as-possible elements. Use whenever the user wants to build or export a model 'for Revit', download or generate IFC from Claude Design or three.js, make an IFC file open or link cleanly in Revit, model electrical/MEP equipment for Revit (panelboards, switchboards, transformers, lighting, trapeze hangers, conduit racks, cable tray, disconnects), validate/harden/repair an existing .ifc, map IFC property sets onto Revit shared parameters, or prepare a shop-drawing / coordination-model handoff for a Revit user. Covers the tagging contract for the canonical ifc-export.js, the sandbox scripts (validate_ifc.py, harden_ifc.py, report.py, generate_ifc.py), and the Revit-side checklist (Link vs Open IFC, shared parameters, version limits). Not for editing .rvt binaries or non-Revit CAD."
---

# tekton-ifc — Claude Design ⇄ Autodesk Revit for electrical / MEP work

This skill is the whole product. A fresh Claude session (Claude Design,
Cowork, claude.ai) can load it cold and execute the workflow end to end. Read
this file first, then only the reference files a step tells you to open.

> All paths below are relative to this skill's directory
> (`skills/tekton-ifc/`). Copy commands verbatim.

## 0. Glossary — terms used everywhere below

| Term | Meaning |
|---|---|
| **Claude Design** ("Design") | The Anthropic surface where the user builds 3D models as HTML pages using three.js and the `<three-d-stage>` viewer component. It authors the model; it usually does not run Python. |
| **Cowork / claude.ai sandbox** | The Linux code-execution sandbox where this skill's Python scripts run (same runtime as Anthropic's docx/xlsx/pdf skills). No Windows, no Revit. |
| **three.js** | The JavaScript 3D library the model is built in. Pinned to **version 0.184.0** (see 4.1). |
| **`<three-d-stage>`** | The starter web component (`three-d-stage.js`) already present in Design 3D projects: viewer + download toolbar (OBJ+MTL, GLB, **IFC**). Its IFC button calls `./ifc-export.js` → `toIfc(THREE, object, meta)`. |
| **IFC** | Industry Foundation Classes — the open building-model format (ISO 16739). We emit **IFC4** as a plain-text **STEP** file (`.ifc`, "STEP Physical File" ISO-10303-21). Version-agnostic: any modern Revit reads it. |
| **Pset (property set)** | A named group of typed key/value properties attached to an IFC element (e.g. `PanelSchedule` with `Voltage`, `Phases`). Revit turns these into element parameters. |
| **Revit family / category** | Revit's native element model. **Categories** (Electrical Equipment, Lighting Fixtures…) drive schedules and visibility; **families/types** are parametric templates; **connectors** are the MEP wiring points that make circuits work. |
| **DirectShape** | Revit's "frozen solid" element: correct category, name, parameters, schedulable, movable — but not parametric and with **no MEP connectors**. This is what IFC becomes in Revit. |
| **Link IFC / Open IFC** | The two ways Revit ingests an `.ifc`. **Link** (recommended, IFC4) = read-only linked model of DirectShapes with all psets as parameters. **Open** (legacy, IFC2x3-era) = converts into a new project, tries to nativise simple walls, drops most pset data. See section 6. |
| **Shared parameters** | Revit parameters defined in a shared-parameters `.txt` file (GUID-identified) so tags and schedules can use them across projects. Our psets are named to map 1:1 onto the firm's file. |
| **APS Design Automation** | Autodesk's cloud service that runs headless Revit against an add-in. The only route to Tier 2 (native families/circuits). Out of scope for the IFC path; referenced for escalation. |

## 1. Who this serves and what "editable" honestly means

The users are **electrical / MEP contractor-engineers** on transit and
institutional facilities (bus garages, electrical rooms). They are not
developers. They build models, one-lines, panel schedules, BOMs, shop drawings
and renderings in Design, export IFC, and bring it into **Revit** using a work
Autodesk account. `[open]` Their exact Revit version is unconfirmed — see 6.4.

**Say this to the user before doing anything else. Never let them be surprised
later:**

> There are two levels of "editable in Revit", and only the first comes from an
> IFC file:
>
> **Tier 1 — clean reference geometry (this skill, today).** Every panelboard,
> transformer, hanger rack, light fixture lands in the **right Revit category**,
> at the **right position with a real insertion point**, at true dimensions,
> with your **panel/transformer schedule data as element parameters** that
> tags and schedules can read. You can move it, hide it, dimension to it,
> section it, and put it on sheets. It comes in as **DirectShape** geometry:
> not a parametric family — no wall layers, no size grips, and **no
> electrical connectors, so no circuits or Revit-native panel schedules.**
> This is exactly what good IFC gets you, and our exporter + hardening scripts
> make it as good as IFC can be.
>
> **Tier 2 — native MEP families with working connectors and circuits.**
> Revit's IFC importer **never** creates functioning electrical connectors,
> circuits, or panel schedules from IFC, no matter how good the IFC is. Tier 2
> requires the Revit API: an add-in run inside Revit or in Autodesk's cloud
> (APS Design Automation) that places real families and sets their
> parameters (our psets map 1:1 to the firm's shared parameters), or a native
> `.rvt` file. This skill delivers Tier 1 plus a **Tier 2 handoff package**
> (schedule data, family/type callouts, insertion points) so someone with
> Revit can finish the wiring in minutes instead of remodelling.

Never claim Tier 2 from IFC. Never call the result "native Revit families".
Correct phrasing: "correctly-categorized, correctly-placed Revit elements
carrying your schedule data".

## 2. Which workflow?

| Situation | Go to |
|---|---|
| Starting or upgrading a Design 3D project whose model will go to Revit | **Workflow A** (section 4) |
| User attached an `.ifc` (from Design, or anywhere) and wants it Revit-ready | **Workflow B** (section 5) |
| User describes a building in words/JSON (levels, walls, rooms) and wants IFC | **Workflow C** (section 5.5) — `scripts/generate_ifc.py` from a building spec |
| User asks "how do I get this into Revit / why can't I edit it / where did my panel data go" | **Section 6** handoff checklist + **section 8** troubleshooting |
| User wants real families, connectors, circuits, or a `.rvt` file | Explain Tier 2 (section 1); produce the Tier 1 IFC + handoff package; do NOT promise `.rvt` |

If in Design: you author (A) and the browser exports the `.ifc`; the user
then attaches that `.ifc` in a Cowork/claude.ai chat where the skill runs (B).
Design itself is normally the author, not the script runner.

## 3. Non-negotiable rules

1. **Metres, y-up, meaningful origin** in the three.js model (a panelboard's
   origin is the bottom-centre of the enclosure back). The exporter converts
   y-up → z-up and metres → IFC SI. Never model in feet or millimetres.
2. **The pinned three@0.184.0 import map is verbatim** (4.1). Never bump
   versions, never mix CDNs.
3. **Exactly one tagged product node per real-world component**, tagged with
   `userData.ifc` (contract: `references/tagging-contract.md`).
4. **Prefer un-baked primitives** — `BoxGeometry`, `CylinderGeometry`,
   `ExtrudeGeometry` with `.parameters` intact — over `merge()` helpers and
   `geometry.rotateX()/translate()` baking, so solids export as extrusions
   (`references/authoring-rules.md`).
5. **Annotation is never physical geometry.** Clearance zones, door swings,
   working-space volumes are psets (`WorkingClearanceDepth`,
   `DoorSwingRadius`) or `IfcSpace`, never solids in the building.
6. **The exporter is only ever installed as `./ifc-export.js`** from
   `assets/ifc-export.js` — the drop-in path `<three-d-stage>` imports.
   Never fork it inline in the page.
7. **Validate before you deliver.** Every `.ifc` handed to the user has gone
   through `scripts/validate_ifc.py` (and, for anything not exported by our
   v2 asset, `scripts/harden_ifc.py`) with the report attached.
8. **IFC is version-agnostic; `.rvt` is not.** Revit cannot open a `.rvt`
   saved by a newer Revit. Deliver IFC. If a `.rvt` is ever requested, ask
   the user's Revit version first (6.4).

## 4. WORKFLOW A — Author a Revit-bound model in Claude Design

Full click-by-click runbook: `references/sop-design-authoring.md`. Modelling
rules: `references/authoring-rules.md`. Tag contract:
`references/tagging-contract.md`. Do these in order.

### 4.1 The page skeleton (mandated import map + stage)

Every Design 3D page starts from the "3D object" starter. If the project
already has an HTML page with an import map and `three-d-stage.js`, **keep
that map byte-for-byte** (it carries SRI `integrity` hashes). If you are
creating the page from scratch, use this map — module URLs only, and copy the
`integrity` attributes from the project's existing "3D object" page/skill if
present (do not invent hashes):

```html
<script type="importmap">
{
  "imports": {
    "three": "https://unpkg.com/three@0.184.0/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.184.0/examples/jsm/"
  }
}
</script>
<script type="module" src="./three-d-stage.js"></script>

<three-d-stage id="stage" name="area-e-electrical-room"></three-d-stage>

<script type="module">
  const stage = document.getElementById('stage');
  const { THREE } = await stage.ready;              // THREE 0.184.0, provided by the stage
  const { buildModel, ifcMeta } = await import('./model.js'); // your model module (4.3)
  stage.setObject(buildModel(THREE));                // a THREE.Group of tagged product nodes
  stage.ifcMeta = ifcMeta;                            // whole-file metadata (contract §meta)
</script>
```

The stage's toolbar has **OBJ+MTL / GLB / IFC** buttons. The IFC button runs
`(await import('./ifc-export.js')).toIfc(THREE, object, stage.ifcMeta)`,
turns the returned text into `<name>.ifc`, and downloads it. That module
path and signature are the whole integration contract.

### 4.2 Install the canonical exporter

Copy `assets/ifc-export.js` from this skill into the Design project as the
file **`./ifc-export.js`** (same folder as the page and `three-d-stage.js`),
overwriting any older version. It exports:

```js
export function toIfc(THREE, object, meta = {}) → string  // IFC4 STEP text
```

It is a zero-change drop-in: every v1 tag/meta still works; v2 behaviour
(real placements, extruded solids, shared types, instancing, exclusions,
multi-storey, level of detail) is on by default and controlled via `meta`.
`assets/example-model.js` is a complete worked model — exports
`buildExampleModel(THREE) → THREE.Group` and `exampleMeta(overrides)` (a
two-storey electrical room exercising every exporter feature: shared type,
instancing, extrusion with voids, `ifcLOD`, an excluded
`working_clearance`, tessellation fallback). Read it before writing a new
model module; the electrical room in 4.4 follows the same pattern.

### 4.3 The model-tagging contract (summary — full spec in references/tagging-contract.md)

Any `THREE.Group` (or `Object3D`) carrying `userData.ifc = {...}` becomes
**one IFC product**; all its descendant meshes' geometry are that product's
body. Untagged descendants are just geometry of the nearest tagged ancestor.
If nothing is tagged, the whole object is one product described by `meta`.

```js
group.userData.ifc = {
  ifcClass: 'IFCELECTRICDISTRIBUTIONBOARD',   // IFC entity → Revit category (references/mep-class-map.md)
  predefinedType: 'DISTRIBUTIONBOARD',        // enum of that class; default NOTDEFINED
  name: 'B-LQ1',                                // element name shown in Revit
  tag: 'B-LQ1',                                 // equipment tag / Revit "Mark"
  description: 'Panelboard, 208Y/120 V, fed from XFMR-LQ1',
  typeName: 'Panelboard 208Y/120V 225A MLO 42-space',   // identical typeName ⇒ ONE shared type
  storey: 'Level 1',                            // v2: name (or index) into meta.storeys
  psets: [ { name: 'PanelSchedule', props: {
      PanelName: 'B-LQ1',
      Voltage:   { value: 208, type: 'voltage' },   // → IfcElectricVoltageMeasure → shared param "Voltage"
      Phases:    { value: 3,   type: 'integer' },
      Wires:     { value: 4,   type: 'integer' },
      BusRating: { value: 225, type: 'current' },
      NumberOfCircuits: { value: 42, type: 'count' },
      Mounting:  'Surface',                          // bare scalar ⇒ type 'label' (IfcLabel)
  } } ],
  typePsets: [ { name: 'Pset_ManufacturerTypeInformation', props: {
      Manufacturer: 'Eaton', ModelLabel: 'Pow-R-Line 4' } } ],
};
```

Whole-file metadata lives on the stage: `stage.ifcMeta = {...}` (or passed
as `meta` to `toIfc`). The v2 keys you will use most:

```js
export const ifcMeta = {
  projectName: 'DDOT Coolidge — Area E bus storage electrical room',
  fileName: 'bs-area-e-electrical-room',
  author: { name: 'C. Karagitz Electric', org: 'C. Karagitz Electric' },
  storeys: [ { name: 'Level 1', elevation: 0 }, { name: 'Mezzanine', elevation: 3.0 } ],
  geometry: 'auto',            // solids where possible, tessellation fallback ('tessellation' | 'solids')
  excludeNames: ['working_clearance', 'door_swing_clearance'],  // default: skip these helper groups
  clearanceAs: 'skip',         // or 'space' to emit NEC 110.26 volumes as IfcSpace
  minFeatureSize: 0.01,        // drop meshes < 10 mm in every dimension (screws)
  guidSeed: 'coolidge-area-e', // stable GlobalIds across re-exports (Revit re-link tracking)
};
```

Pset property names for panelboards MUST match the firm's shared-parameters
file (`PanelName, Voltage, Phases, Wires, BusRating, MainsType, MainsRating,
ShortCircuitRatingkA, Mounting, NumberOfCircuits, NeutralRating`) so they
land as the firm's Revit parameters — see
`references/shared-parameters-mapping.md`.

### 4.4 Worked example — the electrical room, structure only

(Complete runnable module: `assets/example-model.js`; annotated version and
the reasoning behind every choice: `references/authoring-rules.md` §7.)

```
Group  "area_e_electrical_room"           userData.ifc = { ifcClass:'IFCSPACE', name:'Electrical Room 101', storey:'Level 1' }
├─ Group "panel_B-LQ1"                     userData.ifc = { IFCELECTRICDISTRIBUTIONBOARD, typeName:'PB-208-225-42', storey:'Level 1', psets:[PanelSchedule…] }
│   ├─ Mesh  enclosure   BoxGeometry(0.508, 0.914, 0.15)   ← intact parameters ⇒ IfcExtrudedAreaSolid
│   └─ Mesh  dead_front  ExtrudeGeometry(shape w/ breaker holes, {depth:0.002}) ⇒ profile with voids
├─ Group "panel_B-SLQ1"                    userData.ifc = { …, typeName:'PB-208-225-42', … }   ← SAME typeName ⇒ one shared IfcElectricDistributionBoardType
├─ Group "xfmr_LQ1"                        userData.ifc = { ifcClass:'IFCTRANSFORMER', predefinedType:'VOLTAGE', storey:'Level 1', psets:[TransformerSchedule…] }
│   └─ Mesh  case        BoxGeometry(0.66, 0.762, 0.51)
├─ Group "hangers"                         userData.ifc = { ifcClass:'IFCDISCRETEACCESSORY', predefinedType:'BRACKET', storey:'Mezzanine' }
│   └─ (repeated strut+rod meshes sharing geometry.uuid ⇒ IfcMappedItem instancing)
└─ Group "working_clearance"   ← matches meta.excludeNames ⇒ NOT exported as geometry
                                (its size is already in the PanelSchedule pset: WorkingClearanceDepth/Width/Height)
```

Node placement: set `group.position` / `group.rotation` on the tagged group
(e.g. `panel_B-LQ1.position.set(-3.78, 1.07, 2.32)`) and build meshes in the
group's LOCAL frame. The exporter turns each tagged node's world transform
into a real IFC insertion point + orientation, so the element is movable and
rotatable in Revit. Never bake position by editing vertices.

### 4.5 Export and sanity-check in Design

1. Load the page; visually confirm the model in the stage (studio lights,
   ground shadow, auto-frame). Wrong scale here (a 40 m panel) means feet were
   modelled as metres — fix the model, not the export.
2. Click **IFC** in the stage toolbar → `<fileName>.ifc` downloads.
3. Open the `.ifc` as text and eyeball: `FILE_SCHEMA(('IFC4'))`, an
   `IFCELECTRICDISTRIBUTIONBOARD` per panel, `IFCEXTRUDEDAREASOLID` /
   `IFCMAPPEDITEM` present (not 100% `IFCTRIANGULATEDFACESET`), one
   `IFCLOCALPLACEMENT` per product with non-identity coordinates, and each
   distinct `typeName` appearing ONCE in `IFCRELDEFINESBYTYPE`.
4. Hand the `.ifc` to Workflow B step 5.2 (validate) before delivery — even
   for our own exports.

## 5. WORKFLOW B — Validate, harden, and deliver an existing IFC

Runs in the Cowork / claude.ai sandbox. Full runbook with expected outputs:
`references/sop-harden-deliver.md`.

### 5.1 Set up the engine (once per sandbox)

```bash
cd skills/tekton-ifc                      # this skill's folder
pip install -r scripts/requirements.txt     # ifcopenshell + numpy (Linux manylinux wheels; no compiler)
                                            #   fallback if the file is absent: pip install ifcopenshell numpy pytest
python scripts/validate_ifc.py --help       # confirm the CLI is live; trust its --help over this doc if they differ
```

If `pip install ifcopenshell` fails in this sandbox (no egress / no wheel):
say so, run `validate_ifc.py` in its degraded pure-text mode if it offers
one, and record it as an environment blocker in the delivery report — do
not silently skip validation. See troubleshooting 8.6.

### 5.2 Validate

```bash
python scripts/validate_ifc.py path/to/input.ifc --json out/validate.json   # exit 0 = analysed; 2 = not IFC
```

The printed summary (full report in the JSON) has these parts. Interpret
each for the user in plain English:

| Line(s) in the summary | Meaning | What you do |
|---|---|---|
| `schema : IFC4 errors=N warnings=M` | STEP/EXPRESS validity. **N > 0 = the file is broken.** | Must reach 0 (harden or re-export) before delivery. Revit drops/mangles invalid entities. |
| `score : x/100` + `tier : …` | The editability verdict: `INVALID` (schema errors) / `Tier 0 (v1-like)` (frozen blobs, baked coordinates) / `Tier 1 (partial)` / `Tier 1` (clean, movable, dimensionally-honest reference geometry). | This is the sentence you report. It is never Tier 2 (section 1). |
| audits: `geometry` (n tessellated), `placements` (n identity/origin), `types`, `instancing`, `phantoms`, `spatial`, `psets`, `units` | Where the score is lost. Tessellation ⇒ frozen DirectShapes; identity placements ⇒ insertion points lost; phantoms ⇒ annotation exported as solids. | Component scores tell you which fixes matter. |
| `top fixes (highest impact first)` | Ranked to-do list; each item names its tool (`harden_ifc.py …` or "re-author at source"). | If we authored the model, re-export with the v2 asset (Workflow A); otherwise harden (5.3). |
| `element inventory` | Per element: class, name, type, storey, geometry kind → predicted Revit result (category per `references/mep-class-map.md`). | Paste into the delivery report. |

Reference point: the raw v1 sample `bs-area-e-electrical-room.ifc` scores
**31.4/100, Tier 0** (11/11 tessellated, 11/11 identity placements, 0
types, 9 unshared repeats), schema errors 0.

### 5.3 Harden

```bash
python scripts/harden_ifc.py path/to/input.ifc -o out/hardened.ifc --report out/harden.json
#   optional: --keep-clearance-as-space  --no-remove-phantoms  --no-create-types  --no-extrusions
python scripts/validate_ifc.py out/hardened.ifc --json out/validate-after.json   # must show errors=0
```

Hardening is an automatic, **geometry-semantics-preserving** rewrite; it
prints a before/after diff table, an actions log, and reopens the output to
confirm `schema errors after = 0` (exit 0 ok, 1 output invalid, 2 usage).
Product `GlobalId`s are preserved. Transforms: merge duplicate type objects
with identical `(class, Name)`; create ONE shared `IfcXxxType` per group of
untyped elements sharing (class, predefined type, geometry signature); move
psets that are identical across all occurrences onto the type; repair empty
owner-history fields; detect and remove phantom annotation solids
(clearance/swing/helper — or `--keep-clearance-as-space` ⇒ `IfcSpace
.INTERNAL.`); **convert tessellation that is provably an upright box into a
real `IfcExtrudedAreaSolid` and move the placement to the box's base-centre**
(recovering an insertion point and orientation) — only when exact, otherwise
tessellation is left alone; contain orphan elements in the first storey.
On the raw v1 sample this takes the score 31.4 → 89.0 (Tier 0 → Tier 1
partial): 10/11 elements gain extrusions and real placements, 4 shared
types created. What it can never do: recover a *non-box* solid from
triangle soup, or a rotation baked into vertices — those are source-only
fixes (Workflow A).

### 5.4 Delivery report and the deliverable set

```bash
python scripts/report.py out/hardened.ifc --before path/to/input.ifc -o out/delivery-report.md
```

(If `scripts/report.py` is not present in this checkout, assemble
`out/delivery-report.md` yourself from `validate_ifc.py`'s printed summary
of the final file plus `out/harden.json`'s before/after table and actions —
never invent numbers.) Deliver, together, in one message:

1. `hardened.ifc` — the file to link into Revit.
2. `delivery-report.md` — what is in it, what each element becomes in Revit
   (category from `references/mep-class-map.md`), errors fixed, warnings
   remaining, the Tier 1 / Tier 2 statement, and the section-6 checklist
   pre-filled for this file.
3. The firm's shared-parameters `.txt` (or the mapping guidance) so the
   psets show up under the right parameter names
   (`references/shared-parameters-mapping.md`).
4. If Tier 2 was asked for: the **Tier 2 handoff package** — per-element
   table of tag, class → target family/category, insertion point (metres),
   type, and the schedule data — for the person with Revit / the APS step.

### 5.5 Workflow C (pointer) — generate IFC from a building spec

When the input is a description or `spec.json` of a building (levels,
walls, doors, rooms) rather than a Design export:

```bash
python scripts/generate_ifc.py --spec path/to/spec.json -o out/model.ifc --validate   # then run 5.2 → 5.4 on it
```

The spec also carries an `equipment` array (panelboards/transformers/light
fixtures with `position`, `rotationDeg`, `elevation`, `dims`, `typeName`,
`psets`) emitted the Tier-1 way (extrusions, one shared type per typeName,
`IfcMappedItem` occurrences, real placements) — see the script's docstring.

The spec schema is `spec/building.schema.json` at the repo root (versioned,
`additionalProperties:false`, everything defaultable except intent — minimal
document: `{"storeys": 2, "footprint": [[0,0],[12,0],[12,8],[0,8]]}`).

## 6. Revit-side handoff checklist (paste, pre-filled, into every delivery)

Full detail and screenshots-in-words: `references/revit-import-fidelity.md`,
`references/shared-parameters-mapping.md`, `references/revit-versions.md`.

**6.1 Link IFC, don't Open it (default).**
Revit → *Insert* tab → **Link IFC** → choose the `.ifc` → Positioning
"Auto – Origin to Origin". Revit converts the file into a sidecar
`<name>.ifc.RVT` (+ `<name>.ifc.sharedparameters.txt`) next to the `.ifc` and
links it. Result: every element is a DirectShape in the mapped category
(section 1, Tier 1) with every pset property as an instance parameter. Keep
the `.ifc` and the sidecar files together; re-linking a re-exported `.ifc`
with the same `guidSeed` updates in place.
Use **File → Open → IFC** (which creates a *new* standalone project and is
Autodesk's legacy, IFC2x3-era path) ONLY when the user explicitly needs a
self-contained `.rvt` with no link and accepts that most pset data is lost
and MEP equipment becomes generic in-place elements. If you go this route,
tell the user to check *Manage → IFC options → Import IFC class mapping* first.

**6.2 Make the psets land as the firm's shared parameters.**
Our pset property names equal the firm's shared-parameter names on purpose.
After linking, either (a) let the auto-generated
`<name>.ifc.sharedparameters.txt` supply the parameters, or (b) point Revit
at the firm's file (*Manage → Shared Parameters → Browse* →
`panelboard-shared-parameters.txt`) and add each parameter as a **Project
Parameter** bound to the *Electrical Equipment* (and relevant) categories so
tags and schedules resolve them. Exact steps + the name/datatype mapping
table (PanelName TEXT, Voltage ELECTRICAL_POTENTIAL, Phases INTEGER, Wires
INTEGER, BusRating ELECTRICAL_CURRENT, MainsType TEXT, MainsRating
ELECTRICAL_CURRENT, ShortCircuitRatingkA NUMBER, Mounting TEXT,
NumberOfCircuits INTEGER, NeutralRating TEXT):
`references/shared-parameters-mapping.md`.

**6.3 Verify the categories.**
Panelboards/switchboards/transformers → *Electrical Equipment*; fixtures →
*Lighting Fixtures*; hangers/strut/racks → *Structural Framing / Specialty
Equipment* per `references/mep-class-map.md`. If something lands in
*Generic Models*, its `ifcClass` was a proxy or unmapped — fix the tag and
re-export (or let `harden_ifc.py` remap it) rather than re-categorising in
Revit, which is lost on the next re-link.

**6.4 Target-version warning (state it every time).**
> IFC is version-agnostic: this `.ifc` links into any Revit 2019 or newer, and
> the sidecar `.ifc.RVT` is created by *your* Revit, so it is automatically your
> version. **A `.rvt` file, by contrast, cannot be opened by any Revit older
> than the one that saved it.** So if you ever ask for a `.rvt` instead of an
> IFC, tell us your exact Revit version first (Help → About), and never save
> the coordination file forward past your team's oldest install.

**6.5 Units and origin.** Model is metres SI; Revit converts on link — switch
display to feet-inches with *Manage → Project Units* if wanted. The model
sits near the origin; use *Auto – Origin to Origin* positioning (or shared
coordinates if the host project has a survey point).

## 7. What stays in Design as documents vs. what must be model

| Deliverable | Where it lives | Why |
|---|---|---|
| Renderings, hero images, animations | **Design** | Revit adds nothing; render in the stage. |
| One-line diagrams, riser diagrams | **Design** (page graphics / SVG) | Circuiting inside Revit is Tier 2; the one-line is a drawing, not a model. |
| Panel schedules, transformer schedules, load calcs | **Design table** + the **numbers as psets on the element** | Revit-native panel schedules need circuits (Tier 2). Ship the table for the submittal and the psets so Revit tags/schedules can still read the values. |
| BOMs, submittal cover pages, spec sheets | **Design** | Documents. |
| Panelboards, switchboards, transformers, disconnects, ATS, lighting fixtures | **Model** (tagged product nodes) | Must be coordinated, dimensioned, sectioned, tagged, shown on sheets. |
| Hanger racks, strut, threaded rod, conduit racks, cable tray runs | **Model** | Clash/coordination geometry; hangers instance well (`IfcMappedItem`). |
| The room / space itself | **Model** as `IFCSPACE` (or a proxy shell) | Gives Revit a schedulable space and a home for `RoomInformation` psets. |
| NEC 110.26 working clearance, door-swing arcs, keep-outs | **Psets** on the equipment (+ optional `IfcSpace` via `clearanceAs`) — never solids | Solid clearance boxes import as phantom translucent equipment. |
| Views, sheets, dimensions, shop-drawing annotation | **Revit** generates these from the model | That is what the Revit user does after the link; don't attempt in Design. |

## 8. Troubleshooting

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 8.1 | In Revit every element's insertion point is at the world origin; can't move/rotate cleanly | v1 exporter (identity `IfcLocalPlacement`, world-baked vertices) | Install v2 `assets/ifc-export.js` as `./ifc-export.js`, set node `.position/.rotation`, re-export. |
| 8.2 | Phantom translucent boxes / swing wedges in Revit | Clearance helper groups exported as solids | Name them so `meta.excludeNames` catches them, or `userData.ifcExclude = true`, or `meta.clearanceAs:'space'`. `harden_ifc.py` strips known helper names from foreign files. |
| 8.3 | Everything is a frozen blob; validate says "0 extrusions / 100% tessellation" | `merge()`/`.rotateX()`/`applyMatrix4` baked geometry into anonymous `BufferGeometry` | Rebuild with intact `BoxGeometry`/`CylinderGeometry`/`ExtrudeGeometry` (`references/authoring-rules.md` §2); position via `Object3D`, not vertices. |
| 8.4 | Huge `.ifc`, slow link, N identical types in Revit | No instancing, one `IfcXxxType` per element (v1) | v2 dedupes by `(ifcClass,typeName)` and instances by `geometry.uuid`; give identical parts the same `typeName`/shared geometry; use `minFeatureSize` / `ifcLOD:'bbox'`. |
| 8.5 | Equipment lands in *Generic Models* | `ifcClass` missing / `IFCBUILDINGELEMENTPROXY` | Set the real class (`references/mep-class-map.md`); re-export or harden. Never fix categories inside Revit. |
| 8.6 | `pip install ifcopenshell` fails in the sandbox | Sandbox egress/wheel restriction | Report it as a blocker; use the script's degraded text-only checks if offered; escalation path is the project's MCP/local-runner route — do not fake a validation result. |
| 8.7 | Panel data not visible in Revit / wrong parameter names | Psets present but not bound to the category, or property names ≠ shared-parameter names | Follow 6.2 exactly; property names are case-sensitive; use the tagging contract's canonical names. |
| 8.8 | "This file was saved in a later version and cannot be opened" | A `.rvt` version mismatch — never an IFC problem | You delivered a `.rvt`; IFC has no such limit. Re-read 6.4; get the user's version. |
| 8.9 | STEP parse error / garbled non-ASCII (em-dashes, °) in Revit | Unescaped Unicode in the STEP text | Strings must use ISO-10303-21 `\X2\....\X0\` escapes; the v2 exporter and `harden_ifc.py` both re-escape — run harden. |
| 8.10 | Model is ~3.28× too large or small | Feet modelled as metres (or vice-versa) | Fix the three.js model (metres, y-up). Do not rescale in the exporter or in Revit. |
| 8.11 | Second link of a re-export duplicates elements instead of updating | GlobalIds changed between exports | Set `meta.guidSeed` (stable seeded GUIDs); re-export; relink over the old `.ifc` path. |
| 8.12 | User expects connectors / circuits / Revit panel schedules | Tier 2 expectation | Re-state section 1; deliver the Tier 2 handoff package (5.4 item 4). |

## 9. Reference files (open only what a step tells you to)

| Path | What it is | When to read |
|---|---|---|
| `references/tagging-contract.md` | Complete `userData.ifc` / `meta` contract, every key with type, default, effect, snippet (v1 + v2) | Before writing or reviewing any model module |
| `references/authoring-rules.md` | Modelling rules that maximise Revit editability + a full worked electrical-room example | Before building geometry |
| `references/sop-design-authoring.md` | Numbered runbook for Workflow A (Design side) | Executing Workflow A |
| `references/sop-harden-deliver.md` | Numbered runbook for Workflow B (sandbox side), exact commands and success criteria | Executing Workflow B |
| `references/revit-import-fidelity.md` | What each IFC construct becomes in Revit; Link vs Open evidence; the DirectShape reality | Explaining results / debugging import |
| `references/mep-class-map.md` | IFC class + predefinedType ↔ Revit category table for MEP/electrical gear | Choosing `ifcClass`; predicting categories |
| `references/shared-parameters-mapping.md` | Pset property names ↔ firm shared parameters; how to bind them in Revit | Section 6.2 |
| `references/revit-versions.md` | Revit version compatibility rules, the "can't open newer" constraint, IFC version support | Any `.rvt`/version question |
| `assets/ifc-export.js` | THE canonical v2 exporter (`toIfc(THREE, object, meta)`) — install as `./ifc-export.js` | Workflow A step 4.2 |
| `assets/example-model.js` | Worked electrical-room model module (panels sharing a type, transformer, hangers, excluded clearance, two storeys) | Template for new models |
| `scripts/validate_ifc.py` | IFC validator + Revit-fidelity linter: score/tier verdict, ranked fixes, element inventory (`--help` is authoritative) | 5.2 |
| `scripts/harden_ifc.py` | Semantics-preserving normaliser (types, phantoms, provable-box→extrusion + placement recovery, owner history, containment) | 5.3 |
| `scripts/bridge_lib.py` | Shared analysis engine both CLIs import (`analyze(path) → report dict`, `human_summary`) | Extending checks |
| `scripts/report.py` | Delivery-report generator (census, Revit category preview, checklist) | 5.4 |
| `scripts/generate_ifc.py` | Building-spec JSON → IFC (architectural shells) | 5.5 |
| `scripts/requirements.txt` | Python deps for the sandbox (`ifcopenshell` etc.) | 5.1 |

Ground truth for every claim in this skill: the analysed real export
`samples/design-ifc/bs-area-e-electrical-room.ifc` and
`docs/design-ground-truth.md` in the repo root.

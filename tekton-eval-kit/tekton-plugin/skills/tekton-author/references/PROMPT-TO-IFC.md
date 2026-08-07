# PROMPT-TO-IFC — turning a natural-language request into the IFC that tekton consumes

Input path (1) of the front door is a **prompt**. tekton never invents a
building from prose inside the writer: the prompt becomes a structured,
reviewable intermediate first, and that intermediate is exported as **IFC4**
— the same file input path (2) consumes. So "prompt → .rvt" is always
`prompt → (spec / model) → IFC → intent → .rvt`, and the user can inspect
and correct the IFC before anything native is authored.

There are two proven ways to get from the prompt to the IFC. Pick by
surface.

## A. On Claude Design (the user's established flow): prompt → three.js scene → IFC

Claude Design builds the model as a three.js `<three-d-stage>` page and
exports IFC4 with the canonical exporter. This is the flow that produced
`examples/electrical-room-2500a.ifc` (a full 2500 A electrical room) and
`examples/chicago-plenum-downlight.ifc` (a fixture) — both authored by our
own `ifc-export.js`, both consumed by this skill end to end.

The complete authoring SOP is the sibling skill's Workflow A — follow it,
do not re-derive it:

- `skills/tekton-ifc/references/sop-design-authoring.md` — the numbered
  SOP: page skeleton (pinned `three@0.184.0` import map), install the
  canonical exporter (`skills/tekton-ifc/assets/ifc-export.js` →
  `./ifc-export.js` in the Design project, unmodified), build `./model.js`
  (`buildModel(THREE)` + `ifcMeta`), one tagged Group per real component,
  visual sanity check, click **IFC**, self-inspect the export.
- `skills/tekton-ifc/references/tagging-contract.md` — the `userData.ifc`
  contract (`ifcClass`, `predefinedType`, `name`, `tag`, `psets`,
  `typeName` …) — with `references/TAGGING-CONTRACT.md` (this skill) for
  the exact pset property NAMES tekton reads back as the join key.
- `skills/tekton-ifc/references/authoring-rules.md` — metres, y-up,
  intact primitives (extrusions survive; baked triangle soup does not),
  insertion points at real positions, `IfcMappedItem` instancing, spaces,
  clearances-as-data.
- `skills/tekton-ifc/references/mep-class-map.md` — which IFC class per
  equipment type (panelboard → `IFCELECTRICDISTRIBUTIONBOARD`, transformer →
  `IFCTRANSFORMER`, supports → `IFCDISCRETEACCESSORY`, room → `IFCSPACE`).

What tekton needs from the export (the checklist before you hand the IFC
to input path (2)):

1. `FILE_SCHEMA(('IFC4'))`, metre units, a Project→Site→Building→Storey tree.
2. Each real component is its own product with the right entity class and
   a `PanelSchedule` / `TransformerSchedule` / `SwitchboardSchedule` pset
   carrying the tagging-contract keys (§1 of `TAGGING-CONTRACT.md`).
3. Real placements: distinct `IFCLOCALPLACEMENT`s — OR world-baked
   vertices (our three-d-stage writer's style; tekton's intent resolver
   recovers world positions from the composed placement chain either way,
   so both writer styles work; a legacy IFC with everything at the origin
   AND no world-baked geometry cannot be positioned).
4. Feeders as data: `FedFrom` on each fed board (and, ideally, the
   `conduit_<from>_<to>` conduit solids that corroborate them).
5. Clearances / door swings / helper ghosts EXCLUDED from the model
   (`meta.excludeNames`) with their dimensions carried as psets.

## B. In any code sandbox (Claude Chat, Cowork, ChatGPT, Gemini…): prompt → spec.json → IFC

No three.js needed. Write a small equipment spec from the prompt and let
the sibling skill's generator emit the IFC:

```bash
# 1. write the spec from the prompt (structure below), e.g. job-spec.json
# 2. generate + validate the IFC (spec `equipment[]`; see the worked example spec)
python skills/tekton-ifc/scripts/generate_ifc.py --spec job-spec.json \
    -o out/job.ifc --validate                    # prints score / tier / IFC4 schema errors
```

The proven worked instance is the Eaton panelboard:
`examples/eaton-panelboard/panel-spec.json` → an `IfcElectricDistributionBoard`
(480Y/277 V, 400 A bus, 42 spaces) with its full panel schedule as typed
psets; the validator scores it `98.8/100`, Tier 1, `IFC4 errors=0`. Copy
that spec's shape. The generator's own reference is
`skills/tekton-ifc/scripts/README.md`; the deep validate/harden loop is
`skills/tekton-ifc/references/sop-harden-deliver.md` (validate → harden
only if the validator finds fixable issues → delivery report).

The spec fields that matter for the join are the SAME tagging-contract
psets — put `PanelName`, `Voltage`, `BusRating`, `MainsType`,
`NumberOfCircuits`, `Mounting`, `FedFrom` on each board and the transformer
schedule keys on each transformer (`references/TAGGING-CONTRACT.md`).

## C. Then hand the IFC to input path (2)

Either route ends the same way: an IFC on disk. Continue in `SKILL.md` §5
("Input path 2 — IFC"): resolve the intent (`scripts/ifc_intent.py
intent <file>.ifc`) to confirm positions and mapping BEFORE authoring, then
run the front door on it. Correcting the IFC (or the spec / the Design
model) is always cheaper than correcting the native output.

## D. Honest limits of the prompt path (state them up front)

- The prompt path is only as good as the intermediate it produces. tekton
  authors what the IFC says; ambiguity in the prompt must be resolved in
  the spec / model, and shown back to the user, before generation.
- A prompt naming a product our catalog does not cover (e.g. a 2500 A
  switchboard) still works — but as a HOUSE family built from the modeled
  extents with the ratings as parameter values, and the report says so
  (`references/CATALOG-FACTS.md`).
- MEP connectivity limit of IFC itself: an IFC never carries functioning
  Revit connectors/circuits; tekton reconstructs circuits from the
  `FedFrom` feeder tree, not from IFC ports.

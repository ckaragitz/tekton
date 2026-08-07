# SOP — Author a Revit-bound model in Claude Design (Workflow A)

Follow the numbered steps in order. Do not skip steps. Each step states what
"done" looks like. All paths are relative to the skill folder
`skills/tekton-ifc/` unless they start with `./` (which means "inside the
user's Claude Design project"). Terms are defined in `SKILL.md` §0.

## Before you start (2 minutes)

1. **State the two-tier truth to the user, verbatim** (SKILL.md §1). Wait
   for acknowledgement. If the user needs connectors/circuits/native panel
   schedules, confirm you will deliver Tier 1 IFC **plus** the Tier 2
   handoff package — not a `.rvt`.
   *Done when:* the user has agreed the target is Tier 1 IFC (+ handoff).
2. **Ask three questions and record the answers in the page as a comment
   block at the top of `model.js`:**
   - What Revit version does the firm run? (Only matters if a `.rvt` is
     ever produced; IFC needs no answer — SKILL.md §6.4.)
   - What are the source units of the given dimensions (ft-in or metric)?
     You will model in metres regardless (rule 1.1).
   - Does the firm use its own shared-parameters `.txt`? If yes, get the
     parameter names; the pset property names must equal them
     (`references/shared-parameters-mapping.md`).
   *Done when:* the comment block records the answers or "unknown".

## Part 1 — Page skeleton

3. **Look for an existing page.** Open the project's HTML. If it already
   contains a `<script type="importmap">` with `three@0.184.0` and a
   `<script type="module" src="./three-d-stage.js">`, DO NOT touch the
   import map (it carries SRI `integrity` hashes mandated by Design's
   "3D object" skill). Go to step 5.
   *Done when:* you have confirmed the map is present and unmodified.
4. **Only if creating from scratch:** write the page skeleton from SKILL.md
   §4.1 (import map for `three@0.184.0` — `three` →
   `https://unpkg.com/three@0.184.0/build/three.module.js`, `three/addons/`
   → `https://unpkg.com/three@0.184.0/examples/jsm/`; add the `integrity`
   attributes from the "3D object" skill if you have them, never invent
   them), the `three-d-stage.js` module tag, and the `<three-d-stage>`
   element. If `three-d-stage.js` is missing from the project, obtain it
   from Design's "3D object" starter — this skill does not ship the stage.
   *Done when:* the page loads and the empty stage renders (dark studio
   background, no console errors).
5. **Confirm the stage contract in the console:**
   `const s = document.querySelector('three-d-stage'); const {THREE} = await s.ready; THREE.REVISION`
   → `'184'`. `typeof s.setObject` → `'function'`.
   *Done when:* both checks pass. If `REVISION` is not `184`, stop and fix
   the import map before writing any model code.

## Part 2 — Install the canonical exporter

6. **Copy the exporter into the project.** Read `assets/ifc-export.js` from
   this skill and write its **entire, unmodified** contents to
   `./ifc-export.js` in the Design project (same folder as the page and
   `three-d-stage.js`), overwriting any existing file. Never edit it inline;
   never rename it; never inline it into the page.
   *Done when:* `./ifc-export.js` exists and its first non-comment export is
   `export function toIfc(THREE, object, meta = {})`.
7. **Smoke-test the module resolves:** in the page's module script (or the
   console) run `const m = await import('./ifc-export.js'); typeof m.toIfc`
   → `'function'`.
   *Done when:* it returns `'function'` with no 404.

## Part 3 — Build the model module

8. **Read the worked example first:** `assets/example-model.js` and
   `references/authoring-rules.md` §8. Copy its structure. Do not invent a
   new pattern.
9. **Create `./model.js`** exporting `buildModel(THREE) → THREE.Group` and
   `ifcMeta` (the whole-file metadata object). Fill `ifcMeta` per
   `references/tagging-contract.md` §5–6: at minimum `projectName`,
   `fileName` (kebab-case), `author.org`, `storeys` (every real level, metres,
   absolute), `geometry:'auto'`, `excludeNames`, `minFeatureSize:0.01`, and a
   fixed `guidSeed`.
   *Done when:* `ifcMeta` has all of those keys and `storeys` matches the
   user's levels.
10. **Model each real component as ONE tagged Group** (rules §3). For each:
    - name the Group `<kind>_<tag>`;
    - set `group.position` (and `.rotation` if not axis-aligned) to the
      component's **insertion point in metres, y-up** (rules §1.3);
    - build meshes from **intact primitives** (`BoxGeometry`,
      `CylinderGeometry`, `ExtrudeGeometry` — rules §2) placed via mesh
      `.position/.rotation`, never `geometry.rotateX/translate` or
      `merge()`;
    - reuse the SAME geometry object for identical parts (rules §4);
    - set `group.userData.ifc` per the contract: `ifcClass` from
      `references/mep-class-map.md`, `predefinedType`, `name`, `tag`,
      `description`, `storey`, `typeName` (identical for identical units),
      `psets` (schedule data with the firm's exact property names and
      correct `type`s), `typePsets` (manufacturer/model, once per type).
    *Done when:* every scheduled component in the user's brief is a tagged
    Group and no real component is untagged.
11. **Model annotation as annotation.** Any working-clearance box, door
    swing, keep-out, or context ghost gets a name in `meta.excludeNames`
    (`working_clearance`, `door_swing_clearance`, …) or
    `userData.ifcExclude = true`. Put its dimensions into psets
    (`WorkingClearanceDepth/Width/Height`, `DoorSwingRadius` — type
    `'length'`, metres). Add the room as an `IFCSPACE` product (rules §6).
    *Done when:* a search for helper meshes shows each is either name-matched
    or flagged, and none is a physical product.
12. **Wire the page** (SKILL.md §4.1 script): import `buildModel`/`ifcMeta`
    from `./model.js`, `stage.setObject(buildModel(THREE))`,
    `stage.ifcMeta = ifcMeta`.
    *Done when:* the model appears in the stage, auto-framed, with ground
    shadow.

## Part 4 — Visual sanity check (catches unit and origin errors free)

13. Look at the stage. Check, and fix the MODEL (never the exporter) if any
    fails:
    - Scale is plausible (a panelboard is ~0.9 m tall, not 3 m and not 3 cm).
      3.28× off ⇒ feet-as-metres (SKILL.md §8.10); 1000× ⇒ mm.
    - Equipment stands on the floor (`y = 0` for Level 1), not floating or
      buried.
    - Fronts face the room; nothing is mirrored (a y/z sign error shows as
      equipment facing the wall).
    - Clearance/annotation visuals look like transparent overlays, not solid
      gear.
    *Done when:* all four are true.
14. Toggle helper visibility in the console
    (`obj.getObjectByName('working_clearance').visible=false`) to confirm you
    named helpers as you think — the exporter matches on the same names.

## Part 5 — Export and self-inspect

15. Click **IFC** in the stage toolbar. `<fileName>.ifc` downloads
    (`fileName` from `ifcMeta`). If nothing downloads, open the console:
    the usual causes are `ifc-export.js` not found (step 6) or an exception
    listing a mesh (with `meta.geometry:'solids'`) that could not be
    extruded — either fix that geometry to a primitive or use `'auto'`.
    *Done when:* the `.ifc` file exists and is non-empty.
16. **Open the `.ifc` as text and verify by eye** (grep-level checks):
    - `FILE_SCHEMA(('IFC4'))` present.
    - One entity line per tagged Group with the right class
      (`IFCELECTRICDISTRIBUTIONBOARD`, `IFCTRANSFORMER`,
      `IFCDISCRETEACCESSORY`, `IFCSPACE`) and its `.PREDEFINEDTYPE.`.
    - `IFCEXTRUDEDAREASOLID` and/or `IFCMAPPEDITEM` occur (proof that
      primitives and instancing survived). A file that is 100%
      `IFCTRIANGULATEDFACESET` means geometry was baked (rules §2) — go back
      to step 10.
    - `IFCLOCALPLACEMENT` per product references distinct
      `IFCCARTESIANPOINT`s (not every one at `(0.,0.,0.)`) ⇒ real insertion
      points.
    - Each distinct `typeName` appears exactly once as an `IFC…TYPE`, and
      each `IFCRELDEFINESBYTYPE` lists ALL its occurrences.
    - No product named `working_clearance` / `door_swing_clearance`.
    - `IFCPROPERTYSET('…','PanelSchedule',…)` present with the expected
      property names.
    *Done when:* every check passes.
17. **Do not deliver yet.** Hand the `.ifc` to Workflow B step 5.2 in
    `references/sop-harden-deliver.md` (validate; harden only if the
    validator finds fixable issues; produce the delivery report). Even our
    own exports go through validation.
    *Done when:* Workflow B has produced the deliverable set (SKILL.md §5.4).

## Definition of done for Workflow A

- `./ifc-export.js` is the unmodified canonical asset; `./model.js` builds
  a tagged model per the contract; the page renders it in the stage.
- The exported `.ifc` passes step 16's checks and `scripts/validate_ifc.py`
  with zero ERRORS.
- The user has received the deliverable set from SKILL.md §5.4, including
  the pre-filled Revit handoff checklist (§6) and the Tier 1/Tier 2 statement.
- The three answers from step 2 are recorded in `model.js`.

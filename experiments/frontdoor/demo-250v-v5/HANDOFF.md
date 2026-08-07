# Front-door HANDOFF -- prompt -> Three.js scene -> IFC4 -> tekton

This is the PRIMARY prompt path. Give this file (and `scene-brief.json`) to
ANY AI surface that can write Three.js -- Claude Design / Chat / Cowork,
ChatGPT Work, Gemini -- and follow `PROMPT_TO_IFC.md` (copied here).
The surface builds the scene, exports IFC4 with OUR tagging contract, and
the exported `.ifc` re-enters the front door:

```bash
python tools/frontdoor.py author --ifc <export>.ifc --out <dir>
```

## The prompt

> an electrical room rated for 250V with 6 panels

## What the front door resolved from it

* **Products** (6):
  * `PP-1` — panelboard — `IFCELECTRICDISTRIBUTIONBOARD.DISTRIBUTIONBOARD.` at (0.25, 0.00, 1.42) m, surface; typeName `PB-480Y/277-225A-MLO-42SP`
  * `PP-2` — panelboard — `IFCELECTRICDISTRIBUTIONBOARD.DISTRIBUTIONBOARD.` at (1.66, 0.00, 1.42) m, surface; typeName `PB-480Y/277-225A-MLO-42SP`
  * `PP-3` — panelboard — `IFCELECTRICDISTRIBUTIONBOARD.DISTRIBUTIONBOARD.` at (3.07, 0.00, 1.42) m, surface; typeName `PB-480Y/277-225A-MLO-42SP`
  * `PP-4` — panelboard — `IFCELECTRICDISTRIBUTIONBOARD.DISTRIBUTIONBOARD.` at (4.48, 0.00, 1.42) m, surface; typeName `PB-480Y/277-225A-MLO-42SP`
  * `PP-5` — panelboard — `IFCELECTRICDISTRIBUTIONBOARD.DISTRIBUTIONBOARD.` at (5.89, 0.00, 1.42) m, surface; typeName `PB-480Y/277-225A-MLO-42SP`
  * `PP-6` — panelboard — `IFCELECTRICDISTRIBUTIONBOARD.DISTRIBUTIONBOARD.` at (7.29, 0.00, 1.42) m, surface; typeName `PB-480Y/277-225A-MLO-42SP`
* **Ignored words**: 250V

## Build the scene (Three.js) -- the recipe in one screen

1. `const model = new THREE.Group();` — this is the object you pass to the exporter.
2. For the room: one group `room_shell` tagged with the `shell_tagging.userData_ifc`
   block from `scene-brief.json`; inside it one `THREE.Mesh(new THREE.BoxGeometry(
   length, height, thickness))` per wall named `wall_n` / `wall_s` / `wall_e` /
   `wall_w`, centred on the wall's centerline with its base at z = 0.
3. For every entry in `products`: create a `THREE.Group()`, `group.name =
   product.group_name`, position it at `product.position_m` (metres; the
   three-d-stage convention maps IFC (x, y, z) to THREE (x, z, -y)), model
   the enclosure box at `product.dims_m`, orient it so the equipment FRONT
   faces `product.front_normal`, and set `group.userData.ifc = product.userData_ifc`
   VERBATIM (class, predefinedType, tag, typeName, psets = OUR schedule Psets).
4. `stage.ifcMeta = <brief.ifcMeta>` (storeys, geometry:'auto', guidSeed, ...).
5. `const ifcText = toIfc(THREE, model, stage.ifcMeta)` with the CANONICAL
   exporter (tekton-ifc `assets/ifc-export.js` v2). Save as `<fileName>.ifc`.
6. Return the `.ifc`. Do NOT hand-write STEP text; the exporter emits real
   `IfcLocalPlacement`s + `IfcExtrudedAreaSolid`s + typed Psets from the scene.

Every detail (property value types, storeys, naming, what the front door
reads back) is in `PROMPT_TO_IFC.md`. The `scene-brief.json` beside this
file is the exact machine-readable version of the list above.

## Why the brief exists at all

The front door has a built-in fallback that turns the same prompt straight
into a `.rvt` with NO model call (it produced the intent this brief was
rendered from). The handoff is the PRIMARY path because a Three.js scene
authored by a design surface carries the real geometry, placements and
manufacturer detail a one-line prompt cannot — the IFC route then resolves
REAL insertion points from that geometry.

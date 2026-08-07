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

> create an electrical room 30 by 20 feet with a 2500A switchboard, a distribution panel, a lighting panel, and a transformer

## What the front door resolved from it

* **Room** `Electrical Room`: 9.144 m x 6.096 m, 3.66 m high, wall thickness 0.203 m
* **Walls**: 4 (closed counter-clockwise centerline ring, centred at the origin)
* **Products** (4):
  * `MSB` — switchboard — `IFCELECTRICDISTRIBUTIONBOARD.SWITCHBOARD.` at (-0.54, 2.39, 0.10) m, floor; typeName `SWBD-480Y/277-2500A-MB-4SEC`
  * `DP-1` — distribution_panelboard — `IFCELECTRICDISTRIBUTIONBOARD.DISTRIBUTIONBOARD.` at (-4.47, 2.09, 1.42) m, surface; typeName `PB-480Y/277-400A-MB-42SP`
  * `LP-1` — lighting_panelboard — `IFCELECTRICDISTRIBUTIONBOARD.DISTRIBUTIONBOARD.` at (4.47, 2.09, 1.42) m, surface; typeName `PB-480Y/277-100A-MLO-42SP`
  * `T1` — transformer — `IFCTRANSFORMER.VOLTAGE.` at (2.10, 2.54, 0.10) m, floor; typeName `XFMR-75kVA-480D-208Y/120`
* **Feeder tree** (4 edges): MSB -> DP-1, MSB -> T1, DP-1 -> LP-1, UTILITY -> MSB

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

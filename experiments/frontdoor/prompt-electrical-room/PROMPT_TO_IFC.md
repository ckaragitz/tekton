# PROMPT → Three.js scene → IFC4 → tekton (`--ifc`)

**Who this is for.** Any AI surface that can write JavaScript — Claude Design,
Claude Chat, Claude Cowork, ChatGPT Work, Gemini, or a plain code session.
You have been handed a `scene-brief.json` (produced by the tekton front door
from a natural-language prompt) or a plain prompt. Your job is to **build the
scene in Three.js, tag it, export IFC4, and hand the `.ifc` back**. This is
the front door's PRIMARY prompt path; it mirrors the user's own established
*three-d-stage* flow (a Three.js scene exported as IFC4 whose products carry
OUR schedule Psets).

You do **not** invent the equipment schedule data — it is in the brief. You
do **not** hand-write STEP/IFC text — the canonical exporter writes it. You
**do** build honest geometry (boxes at the given dimensions and positions),
tag every product exactly as specified, and export.

The one command that closes the loop, once you have the file:

```bash
python tools/frontdoor.py author --ifc <your-export>.ifc --out <dir>
```

The front door then **resolves real placements from your geometry** (the
insertion point, orientation, dimensions and mounting of every product are
recovered from the tessellated bodies you modeled — see §7), maps every
tagged board onto OUR generated Revit families through the Psets, and authors
the native `.rvt` on the certified genesis base. Your scene *is* the design;
the brief was only a starting layout.

---

## 1. Inputs you were given

`scene-brief.json` carries everything:

| field | what it is |
|---|---|
| `ifcMeta` | the object you assign to `stage.ifcMeta` (project name, storeys, `geometry:'auto'`, `guidSeed`, exclusions) — pass it straight to the exporter |
| `room` | width / depth / height / wall thickness (metres), the wall list (start/end of each centerline), and the `shell_tagging.userData_ifc` block for the room-shell group |
| `products[]` | one entry per equipment item: `group_name`, `position_m` (metres, world), `front_normal`, `dims_m` (the enclosure box `w`×`d`×`h`), `mounting`, `storey`, and the **`userData_ifc`** block you copy verbatim onto the group |
| `feederTree[]` | who feeds whom (`from` → `to`); already reflected in each product's `FedFrom` property |
| `coverage` | what the front door understood from the prompt and what it defaulted — read it; anything under `not_built` is yours to model as reference geometry only if you want it in the picture (it will not become Revit equipment) |

If you have only a **plain prompt** and no brief, run the front door once
(`python tools/frontdoor.py author --prompt "<text>" --out <dir>`) — it emits
the brief for you (and, as a fallback, a `.rvt` grown from its own
deterministic layout). Or read §6 and produce the equivalent tags yourself.

---

## 2. Coordinate conventions

* Everything is **metres**. The room is centred at the world origin;
  `+x` = east, `+y` = north, `+z` = up in the **brief's** frame.
* Three.js is **Y-up**. The three-d-stage stage maps IFC `(x, y, z)` →
  THREE `(x, z, -y)`. So a brief position `(x, y, z)` becomes
  `group.position.set(x, z, -y)`. The exporter converts back; you never
  see the difference in Revit.
* `front_normal` (2-D, in the brief's plan) is the direction the equipment
  **faces** — the door/dead-front side. Floor gear (switchboards,
  transformers) has a `yaw_deg` too; wall panels stand **upright** with
  their back on the mounting wall (`mounting: "surface"`), front into the
  room.
* `position_m` of **floor** equipment = the footprint centre at the base of
  the body (it sits on a 0.1 m housekeeping pad — model the pad as a
  separate `pad_<tag>` box if you like; the front door reads it as a pad).
  `position_m` of **wall** equipment = the centre of the enclosure's
  **back (mounting) plane** at the enclosure's mid-height.

---

## 3. Build the scene — the recipe

```js
const model = new THREE.Group();                       // what you pass to toIfc()

// 3a. the room shell -------------------------------------------------------
const shell = new THREE.Group();
shell.name = 'room_shell';
shell.userData.ifc = brief.room.shell_tagging.userData_ifc;   // VERBATIM
for (const w of brief.room.walls) {
  const dx = w.end_m[0] - w.start_m[0], dy = w.end_m[1] - w.start_m[1];
  const len = Math.hypot(dx, dy);
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(len, w.height_m, w.thickness_m), material);
  mesh.name = w.group_name;                                    // wall_n / wall_s / wall_e / wall_w
  const cx = (w.start_m[0] + w.end_m[0]) / 2, cy = (w.start_m[1] + w.end_m[1]) / 2;
  mesh.position.set(cx, w.height_m / 2, -cy);                  // Y-up: (x, z, -y)
  mesh.rotation.y = -Math.atan2(dy, dx);                       // align the box with the centerline
  shell.add(mesh);
}
model.add(shell);

// 3b. every product ----------------------------------------------------------
for (const p of brief.products) {
  const g = new THREE.Group();
  g.name = p.group_name;                                       // e.g. panel_DP-1
  g.userData.ifc = p.userData_ifc;                             // VERBATIM: class, tag, typeName, psets
  const box = new THREE.Mesh(new THREE.BoxGeometry(p.dims_m.w, p.dims_m.h, p.dims_m.d), mat);
  box.name = 'enclosure';
  if (p.mounting === 'floor') {
    // footprint centre at the base -> lift by h/2 ; front faces front_normal
    box.position.set(0, p.dims_m.h / 2, 0);
    g.position.set(p.position_m.x, p.position_m.z, -p.position_m.y);
    g.rotation.y = -THREE.MathUtils.degToRad(p.yaw_deg);
  } else {
    // back (mounting) plane at position_m -> push the box out by d/2 along the front
    box.position.set(0, 0, p.dims_m.d / 2);
    g.position.set(p.position_m.x, p.position_m.z, -p.position_m.y);
    g.lookAt(g.position.x + p.front_normal[0], g.position.y, g.position.z - p.front_normal[1]);
  }
  g.add(box);
  // optional detail meshes named for the front door's feature recognition (see 4)
  model.add(g);
}
```

Then export:

```js
stage.ifcMeta = brief.ifcMeta;                                 // storeys, geometry:'auto', guidSeed
const ifcText = toIfc(THREE, model, stage.ifcMeta);            // revit-bridge assets/ifc-export.js v2
// save ifcText as `${brief.ifcMeta.fileName}.ifc`
```

Rules:

1. **One tagged group per thing you would tag on a drawing.** A group with
   `userData.ifc` starts a product; all descendant meshes are its body.
2. **`userData.ifc` is copied verbatim from the brief.** The `ifcClass`
   picks the Revit category (`IFCELECTRICDISTRIBUTIONBOARD` → Electrical
   Equipment); the `tag`/`name` is the panel mark; `typeName` groups
   identical types; the `psets` carry the schedule data (§5).
3. Prefer real **`THREE.BoxGeometry`** for enclosures so the exporter can
   emit `IfcExtrudedAreaSolid` (`geometry:'auto'`) instead of triangle soup.
4. Keep clearance zones / construction helpers OUT of the export:
   `helper.userData.ifcExclude = true` (or name them with the
   `excludeNames` prefixes in `ifcMeta`).

---

## 4. Name your detail meshes (feature recognition)

The front door recovers each product's FRONT from named sub-meshes. Use
these mesh names inside a product group and its orientation is unambiguous:

| put on the FRONT face | put on the BACK / mounting side | the body |
|---|---|---|
| `door`, `latch`, `nameplate`, `handle`, `breaker`, `meter`, `display`, `hinge`, `escutcheon`, `louver` | `strut`, `backing`, `standoff`, `hub` | `enclosure`, `body`, `can`, `housing`, `skid`, `kick_plate`, `bus_bar` |

No named features → the front is inferred from the thin footprint axis
toward the room interior (fine for a symmetric room; ambiguous otherwise).

---

## 5. The tagging contract — the property NAMES are the join key

The Psets in `userData_ifc.psets` are how the front door maps a product onto
OUR generated content. **Keep the property names exactly as given**; the
values may change if the design changes.

| board type | pset name | key properties (names are the contract) |
|---|---|---|
| panelboard | `PanelSchedule` | `PanelName`, `Voltage` (`{value:480,type:'voltage'}`), `Phases`, `Wires`, `BusRating` (`{value:400,type:'current'}`), `MainsType` ("Main breaker"/"Main lugs only"), `MainsRating`, `NumberOfCircuits` (`{value:42,type:'count'}`), `Mounting`, `FeederEntry`, `FedFrom`, `ShortCircuitRatingkA` |
| switchboard | `SwitchboardSchedule` | `PanelName`, `Voltage`, `Phases`, `Wires`, `BusRating`, `MainsRating`, `MainDevice`, `ShortCircuitRatingkA`, `Sections`, `Mounting`, `FeederEntry`, `FedFrom` |
| transformer | `TransformerSchedule` | `PanelName`, `RatingkVA` (`{value:150,type:'real'}`), `Primary` ("480 V delta"), `Secondary` ("208Y/120 V"), `TemperatureRise`, `ImpedancePercent`, `FedFrom` |
| any (type level) | `Pset_ManufacturerTypeInformation` (`typePsets`) | `Manufacturer`, `ModelLabel` — declared identity strings, not catalog facts |

Property value types (the exporter's codebook): a bare string = `IfcLabel`;
`{value, type}` with `type` ∈ `voltage | current | count | integer | real |
length | boolean | text`. Numbers are **volts / amps / metres** — never feet;
a kVA rating is `real` (`RatingkVA: {value:150, type:'real'}`).

`FedFrom` is a directed feeder edge (`DP-1.FedFrom = 'MSB'`). Optional but
recommended: model the feeders as named solids `conduit_<from>_<to>` (e.g.
`conduit_msb_dp1`) inside an `IFCCABLECARRIERSEGMENT` product — the front
door corroborates the feeder tree against them.

---

## 6. From a plain prompt to the brief (if you have no brief)

Derive it deterministically, as the front door's own fallback does:

* **Room**: `W × D` (metres) centred at the origin; four walls, counter-
  clockwise centerline ring (interior on the left of each wall's
  direction); thickness 0.2032 m and height 3.6576 m (12 ft) unless stated.
* **Floor gear** (switchboards then transformers): a lineup along the
  NORTH wall interior, fronts facing SOUTH (into the room), on a 0.1 m pad,
  0.1 m off the wall behind and 0.3 m between items.
* **Wall gear** (panelboards): surface-mounted on the WEST then EAST
  interior faces alternately, distribution panels nearest the north,
  enclosure centre 1.42 m above the floor, front facing into the room.
* **Tags**: `MSB` (`MSB-2`…), `DP-1…`, `LP-1…`, `RP-1…`, `T1…`.
* **Feeders**: switchboard feeds every distribution panel + every
  transformer primary; a transformer's secondary feeds the ≤240 V panels;
  277/480 V lighting panels ride on the distribution panels round-robin;
  the switchboard's own supply is the UTILITY service (no in-model
  circuit).
* Then tag exactly as §5.

---

## 7. What the front door reads back from your IFC (so you know what matters)

The `--ifc` route runs `rvt.ifc.intent`:

* **Placement chain**: every product's `IfcLocalPlacement` chain (product →
  storey → building → site) is composed root→leaf. The three-d-stage
  writer bakes world coordinates into the tessellated vertices and gives
  every product the same identity placement — that is fine: the front door
  transforms your vertices by the composed chain and **recovers the
  insertion point, orientation, dims and elevation from the geometry**. So
  what you MODEL is what lands in Revit; the brief positions are advisory.
* **Front / orientation**: from the named feature meshes (§4) or the thin
  footprint axis toward the room interior. Wall gear gets an upright
  work-plane frame (family +Z = front normal, +Y = up); floor gear a yaw.
* **The join key**: the Pset property NAMES (§5) map each board onto our
  generated families — Eaton Pow-R-Line panelboard members by
  voltage/mains/spaces, dry-type transformers by kVA (catalog FACTS), and a
  house switchboard for ratings no panelboard member covers (composed from
  YOUR modeled lineup extents — so model the switchboard box honestly).
* **Room shell**: the `wall_*` solids in the `room shell` proxy become real
  walls (centerline, thickness, height, door openings from `door_*_leaf`
  + `*_header` solids); slab/pad boxes named `*slab*` / `pad_<tag>` are
  recorded.
* **Clearances**: solids named `clearance_<tag>` in a proxy whose
  description states the NEC 110.26 depths become checked clearance zones
  (annotation, not model elements).

Everything else (materials, colours, screws, labels smaller than
`minFeatureSize`) is presentation — put in as much as makes the design
right; it does not confuse the front door.

---

## 8. Checklist before you hand back the file

- [ ] every equipment group has `userData.ifc` with `ifcClass`, `tag`,
      `typeName`, and the schedule `psets` from the brief (names unchanged)
- [ ] enclosures are `BoxGeometry` (not baked triangle blobs) so solids export as extrusions
- [ ] `stage.ifcMeta` = the brief's `ifcMeta` (storeys + `guidSeed` set)
- [ ] clearance / helper geometry excluded (`ifcExclude` / `excludeNames`)
- [ ] the file was produced by the canonical exporter `toIfc(THREE, model, meta)`
- [ ] `python tools/frontdoor.py author --ifc <file>.ifc --out <dir>` — and read the manifest it writes

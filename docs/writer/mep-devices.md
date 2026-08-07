# MEP devices — electrical devices & fixture instances (full CRUD)

Stream: `mep-devices` (wave: MEP product bar). Module: `src/rvt/mep/devices.py`.
Tests: `tests/test_mep_devices.py` (18). Proofs: `experiments/mep/devices/*.rvt`
+ `manifest.json` (built by `make_devices.py`). Confidence tags: **[V]**
verified on the corpus / by structural + validator proof, **[H]** hypothesis
(needs Autodesk-viewer certification), **[D]** design decision.
Ground truth = `samples/rmebasicsampleproject.rvt` (Revit 2026, 5,629
family instances; 424 receptacles, 410 lights, 63 switches, 187 circuits).

## 0 · TL;DR

Every category an electrical contractor's DEVICES / FIXTURE-INSTANCES touch
— receptacles, switches / occupancy sensors, lighting-fixture instances
(recessed, pendant, wall sconce), data / telephone / fire-alarm devices,
junction boxes, disconnects, floor boxes — is a plain point-placed
`FamilyInstance` whose editability hinges on ONE thing: its HOSTING. This
stream decodes the three hosting flavours those categories use, implements
CREATE for each, wraps MODIFY / MOVE / RETYPE / DELETE over `rvt.manipulate`
with device semantics, and adds CIRCUITING OVER MULTIPLE LOADS
(`add_multi_load_circuit`), the missing verb between "4 receptacles" and
"one 20 A circuit".

```
CREATE  add_wall_device(doc, symbol, wall, along, height, side/facing_point,
                        plane_ref='dummy'|'geom', sketchplane=<share>, mark)
        add_device_on_plane(doc, symbol, plane_id|NewElement, uv= | xyz=, rotation)
        add_ceiling_plane(doc, origin_xyz, facing='down')   /  add_light_fixture(...)
        add_level_datum_plane(doc, level, at_xy)              /  add_floor_device(..., 'datum'|'free')
        add_multi_load_circuit(doc, panel, [loads], number, rating, poles, voltage_v, va)
EDIT    set_device_mark  |  set_mounting_height  |  move_device_along_host  |  rehost_device
        retype_device    |  delete_device  (all -> rvt.manipulate plans)
```

## 1 · How the corpus hosts each device category [V]

Census of every device instance in the MEP sample (`devices.device_census`):

| category (OST) | count | hosting flavour (host = `SketchPlane`) |
|---|---:|---|
| ElectricalFixtures −2001060 (receptacles) | 424 | **416 on a vertical `DummyPlaneRef` work plane coincident with the wall face**, 8 on a `GeomOnPlaneRef` bound to the wall |
| LightingDevices −2008087 (switches, occ. sensors) | 63 | **63 vertical `DummyPlaneRef`** |
| LightingFixtures −2001120 | 410 | **344 on a HORIZONTAL DOWN-FACING `DummyPlaneRef`** ("ceiling"), 66 wall sconces on vertical dummy planes |
| ElectricalEquipment −2001040 (panels/xfmrs) | 29 | 10 dummy, 10 `GeomOnPlaneRef->SWall` (face-bound), 7 gear-on-gear, 2 FREE |
| cat −2003400 (generic, face-based) | 6 | **4 on an `OnDatumPlaneRef` work plane -> LEVEL 1** (573289), 2 free |

Three facts fall out:

1. **Wall devices**: the *native* pattern (98 %) is a `DummyPlaneRef` work
   plane laid COINCIDENT with the wall face, exactly like the panelboards on
   plane 581481 (hosting.md §1); the true face reference (`GeomOnPlaneRef
   {m_elemId = wall, m_geomTag = 5|6}`) is the 2 % minority. Both are legal;
   `rvt.hosting` writes either, so `add_wall_device` defaults to
   `plane_ref='dummy'` and shares planes between devices on one face
   (172 planes carry the 424 receptacles).
2. **Ceiling lights are NOT hosted on ceilings.** Not one hosting plane in
   the file references a `Ceiling` element (`test_devices_never_reference_a_
   ceiling_element`). A ceiling light stands on a horizontal work plane whose
   frame is FLIPPED DOWN and whose elevation is the ceiling's underside; 48
   such planes carry the 410 fixtures (76 on the busiest). "Ceiling hosted" is
   the same *coincidence* trick as the wall panels.
3. **Level (floor) hosting** = an `OnDatumPlaneRef` work plane whose
   `m_datumPlaneId` IS the level id (91 such planes, incl. the 82 sketch
   planes of floors); face-based families placed "on Level 1" sit on one
   (573289, four instances 579920-23). Truly FREE (`m_hostId = -1`,
   `m_workPlaneBased = false`) is reserved for equipment-style families
   (transformer 624416, switchboard 630241) and 45 mechanical units.

## 2 · The three plane shapes (`SketchPlane` = class 0x0f5d) [V]

All three are ordinary `SketchPlane` elements (seq-102 object + seq-101
header + `SerializedDummy` seq-103 rep, an ordinary `ElemRec`); only
`m_oPlaneRef` (a polymorphic pointer) and `m_oTrf` differ. `m_oTrf.m_3x3` is
stored **column-major**: row *i* = (X.i, Y.i, Z.i); a hosted family's own +Z
axis points along the plane's **Z column** (the plane normal).

| flavour | `m_oPlaneRef.ptr_class` | payload | frame `m_oTrf` (columns X, Y, Z) | header `m_deletion` |
|---|---|---|---|---|
| wall (dummy) | `DummyPlaneRef` | `m_pPlane -> Plane{m_origin, m_xVec = X, m_yVec = up}` (normal = xVec×yVec) | Z = the face's OUTWARD normal, Y = up, X = up×Z (along the wall) — the `hosting.face_frame` frame, byte-identical to plane 456146 / 453884 | `[self]` |
| wall (geom) | `GeomOnPlaneRef` | `m_geomRef{m_elemId = wall, m_geomTag = 5 (right/interior) or 6, m_subTag = -1}` | same frame | `[wall, self]`, `m_regenOnly = [wall_type]` |
| ceiling | `DummyPlaneRef` | `Plane{m_origin = (x, y, z_ceiling), m_xVec = (1,0,0), m_yVec = (0,-1,0)}` -> normal (0,0,-1) | X = (1,0,0), Y = (0,-1,0), **Z = (0,0,-1)** (rows `[[1,0,0],[0,-1,0],[0,0,-1]]`, plane 442678 / 433695) | `[self]` |
| level datum | `OnDatumPlaneRef` | `{m_datumPlaneId = LEVEL id, m_vecInPlane = origin (x,y,0), m_rotation 0, m_mirror false}` | identity at (x, y, level_z) | `[level, self]` (573300) |

Worked example — ceiling plane 431707 (76 fixtures): `m_pPlane.m_origin
= (29.649, 118.309, 20.505)`, `m_xVec = (0,-1,0)`, `m_yVec = (-1,0,0)`,
normal = xVec×yVec = **(0,0,-1)**; `m_oTrf.m_3x3 = [[0,-1,0],[-1,0,0],
[0,0,-1]]` (columns X=(0,-1,0), Y=(-1,0,0), Z=(0,0,-1)); `m_or` = the same
origin. Its z (20.505 ft) is the underside of `Ceiling` 580538 (bbox z-min
20.51). Fixture 431705 on it: `m_Trf.m_3x3` columns X=(1,0,0), Y=(0,-1,0),
**Z=(0,0,-1)** — the plane frame rotated 90° about the normal (a fixture is
free to rotate IN its ceiling); `m_or = (9.872, 120.458, 20.505)` (ON the
plane), `m_assocLevelId = -1`, `m_scheduleOnlyLevelId = 378118` (Level 2),
`m_workPlaneBased = true`, `m_elevation = 0`.

## 3 · The hosted device object [V]

Common to every flavour (verified on receptacles 467291 / 456145, switch
452792, troffer 431705, occupancy sensor 452442, datum instance 579920):

| field | value |
|---|---|
| `m_hostId` | the **SketchPlane** id (never the wall / ceiling / level) |
| `m_workPlaneBased` | `true` |
| `m_assocLevelId` | `-1` (no level constraint) |
| `m_scheduleOnlyLevelId` | the LEVEL the device belongs to (wall/ceiling devices; `-1` on the generic datum specimen — we set the level so devices schedule) |
| `InstanceInfo.m_Trf.m_3x3` | the plane frame, optionally rotated about the plane normal (`rotation`) |
| `InstanceInfo.m_Trf.m_or` | the mounting point ON the plane (z = mounting height for wall devices, = ceiling z for lights, = level z for datum devices) |
| `InstanceInfo.m_symbolId == m_masterSymbolId` | the loaded type (no per-host geometry clone — unlike doors) |
| `m_hostParam / m_elevation` | `0.0` |
| `ElectricalFamInstDesignPropertyManager.{m_idSpace, m_idRoom}` | the containing MEP space / room (`devices.space_room_at` — rooms and MEP spaces are the SAME class `RoomElem`, told apart by category −2000160 / −2003600) |
| parameters | `Mark` = `BIP_ALL_MODEL_MARK` (−1001203) in `m_pParamValueSetAString` (families whose donor had none — switches — get the holder CREATED: `{ptr_class ParamValueSetAString, value {m_paramSet:[{m_paramId,m_value}]}}`, decode-verified) |

**Native header parents [V]** (467291 / 452792 / 431705 / 452442 —
`_nativeize_device` reproduces this shape, which `rvt.hosting` alone does
not):

```
m_deletion            = {phase, symbol, level, SPACE, ROOM, self, host plane, (circuit, wires once wired)}
m_regenOnly           = {UnitsElem, the FAMILY, ActiveGeoLocationTrackingElement}
m_appearanceParents   = {symbol, ActiveGeoLocationTrackingElement}
m_nonDetermRegenChildren = {SPACE}          m_hasNonDetermRegenChildren = true
m_deferredParents     = {MEPSystemTracker}   m_categroryId (seq-101) = the OST category
```

## 4 · CREATE — the API [D]

* **`add_wall_device`** wraps `hosting.host_instance_on_wall` (geom or dummy
  plane; the wall may be existing OR created in the same run) and then applies
  §3: space/room, Mark, native parents. `facing_point=` (a point inside the
  served room) picks the face by geometry (`hosting.side_facing_point`),
  robust against the interior/exterior drawing-direction convention. Pass
  `sketchplane=` to share one plane between many devices (the corpus norm).
* **`add_device_on_plane`** hosts on ANY plane — an EXISTING SketchPlane id
  (how the multi-load proof reuses the electrical-room plane 581481 for its
  panel) or a planned plane — positioned by plane `uv` or a projected world
  `xyz`, with an in-plane `rotation`.
* **`add_ceiling_plane` / `add_light_fixture`** — the ceiling flavour of §2;
  the light's Z is (0,0,−1); `ceiling_plane=` shares a plane across a whole
  ceiling; the scheduling level defaults to `level_at_or_below(z)` (the
  sample authored some pendants below Level 2's elevation to Level 2 — an
  authoring choice, so `level_id` is an explicit parameter).
* **`add_level_datum_plane` / `add_floor_device`** — `hosting_mode='datum'`
  (level datum plane, up-facing, device at the level elevation) or `'free'`
  (`Document.add_family_instance`, `m_hostId = -1`).
* **`add_multi_load_circuit(doc, panel, loads, ...)`** — §5.

Discovery helpers: `device_symbols` (every loaded device symbol, its
category, placed count and native hosting flavour — so authoring targets the
firm's OWN loaded content), `find_device_symbol`, `device_census`,
`space_room_at`, `plane_frame`, `level_at_or_below`.

## 5 · Circuits over MULTIPLE loads [V structure]

`Document.add_circuit` (mutate) makes single-load feeders (panel <-
transformer). Branch circuits need N loads on ONE circuit. Real specimens:
471829 ("Power Manager 66", 4 receptacles, 20 A / 1 P / 120 V) and 469428
(9 receptacles); connector-count histogram over 187 circuits: 1×16, 2×60,
5×6, 6×7, 7×24, 8×10, 9×29, 10×19, … 17×1. `add_multi_load_circuit` clones the
smallest real circuit with ≥ N+1 connectors (an EXACT match exists for
common branch sizes) and re-wires it:

| element | field | value |
|---|---|---|
| circuit | `m_connPtrArray[0..N-1].m_arrRefs` | `[{load_i, load's supply connector index (its lowest small index, ~1), connType 1}]` |
| circuit | `m_connPtrArray[LAST].m_arrRefs` | `[{panel, next free 50000-series SLOT, connType 4}]` — panel slots are per-circuit, never shared (tracked per session) |
| circuit | `m_baseConnectorIdArray` | `[{self, LAST connector index, connType 4}]` |
| circuit | `m_pathNodes[0].m_elemId` | **the PANEL** (base equipment), verified **171/171** circuits with path nodes — this CORRECTS `KNOWLEDGE.md`, which said "first load"; later nodes are virtual, re-anchored at the panel origin |
| circuit | `m_dVoltage`, `m_dApparentLoad`, `m_dTrueLoad` | SI ÷ 0.3048² (×10.7639): 120 V = 1291.669, 4×180 VA = 720 VA = 7750.0155 — byte-exact vs 471829 |
| circuit | `m_number`, `m_dRating`, `m_nPoles`, `m_strLoadClassifications` | `"1"`, 20.0, 1, `"Receptacles"` |
| circuit header | `m_deletion` / `m_appearanceParents` / `m_regenOnly` | `{loads, panel, self, cable type/size, LoadClassification}` / `{loads, panel}` / `{load symbol, ElectricalSetting, CircuitNamingTypeSetting}` (mirrors 471829: 690425 = ElectricalLoadClassification "Receptacles", 639116 ElectricalSetting, 885628 CircuitNamingTypeSetting) |
| each load | its supply `Connector.m_arrRefs` | `+ {circuit, index of the circuit connector holding it, connType 4}` |
| panel | its slot `Connector.m_arrRefs` | `[{circuit, LAST index, connType 4}]` |

Connector `nIndex` numbering follows the template (0- or 1-based; the base
is always the highest); truncating a larger template keeps the first N
connectors + the last, and each `Connector` object retains its own archive
pid, so no pid is ever duplicated. **Loads and panel must be NEW elements
created in the same commit** [D] — circuiting EXISTING elements needs the same
two-sided edit applied as in-place record edits (phase 2, listed below); the
proof therefore builds the panel too.

## 6 · EDIT existing devices (wrappers over `rvt.manipulate`) [V structure]

| verb | function | edit |
|---|---|---|
| MODIFY | `set_device_mark(doc, eid, mark)` | `BIP_ALL_MODEL_MARK` (AString) |
| MODIFY | `set_mounting_height(doc, eid, ft_above_level)` | pure +Z move to `level_z + h` |
| MOVE (on the face) | `move_device_along_host(doc, eid, along_ft, up_ft)` | translates `m_or` (+ the cached rep + header bbox, via `move_instance`) by `along·X + up·Y` of the host plane frame — the device never leaves its face (off-plane component ≡ 0) |
| MOVE (to another face) | `rehost_device(doc, eid, new_plane_id, uv= / xyz=)` | `m_hostId` -> new plane, `m_Trf` = new plane frame at the new mounting point, and the header's dependency lists swap old plane id -> new (three composed plans on one session) |
| RETYPE | `retype_device(doc, eid, new_symbol)` | `symbolId` + `masterSymbolId` + rep symbol + parents remap (e.g. Standard -> GFCI) |
| DELETE | `delete_device(doc, eid, cascade=True)` | the device's 3 records + ElemRec leave; its host plane stays (a peer); its CIRCUIT stays but its member connector's ref is dropped; every referrer (circuit, wires, panel bookkeeping, room/space, MEP system tracker) is neutralised; `cascade` removes its own annotation dependents (tags) |
| inspect | `device_placement(doc, eid)` | origin + host plane frame + (u, v) in-plane coordinates + height above its level |

## 7 · The proofs (`experiments/mep/devices/`) [V]

Built by `make_devices.py`; every entry in `manifest.json` records the
writer's structural verify (0 CRC failures, 0 ECC mismatches, 0 walker
errors, stamps ok, counts match, sentinels last), a semantic READBACK
(re-open with `Document.from_file`, check every device field / connector),
and `tools/rvt_validate.py` (structure + consistency + semantic: reference
integrity, connector-graph symmetry, circuit invariants) at **ZERO errors**.

| file | verbs | contents (all ids resolve; 0 dangling refs) |
|---|---|---|
| `receptacle_wall_hosted.rvt` | receptacle CREATE, switch CREATE | Standard duplex receptacle 1.5 ft AFF + single-pole switch 3.65 ft AFF SHARING one new `DummyPlaneRef` plane on the east wall's room-side face (x = 68.916); GFCI receptacle 3.5 ft AFF on the interior partition via a new `GeomOnPlaneRef` plane (`m_elemId` = wall 573609, tag 5); Marks R-101 / S-101 / R-102; space 379575 / room 573809 |
| `light_ceiling_hosted.rvt` | lighting CREATE | 2 recessed troffers on ONE new down-facing ceiling plane at z 20.51 (ceiling 580538's underside) + a pendant on the EXISTING ceiling plane 442678; all Z = (0,0,−1), schedule to Level 2; L-201..L-203 |
| `floor_device.rvt` | floor device CREATE | floor receptacle on a new `OnDatumPlaneRef` plane -> Level 1 + a FREE-standing 15 kVA transformer (hostId −1) |
| `multi_load_circuit.rvt` | circuit CREATE, panel CREATE | 208 V MLO panel (LP-DEV1) on the existing electrical-room plane 581481 + 4 receptacles (2 north wall, 2 east wall, two shared planes) + one 20 A / 120 V / 1 P circuit #1 "Receptacles" (4×180 VA); connector graph closes both ways, base = the panel's free 50000-series slot, `baseConnectorIdArray = {self, LAST}`, path node 0 = the panel |
| `device_modify_move.rvt` | MODIFY, MOVE, RETYPE, re-host | receptacle 467473 Mark -> R-EDITED; receptacle 467523 moved +2.0 ft along its wall and +0.5 ft up (0 off-plane, host kept); receptacle 467480 Standard -> GFCI; receptacle 467456 re-hosted onto east-wall plane 453884 (host id, frame, mounting point ON the new plane, header deletion swapped) |
| `device_delete.rvt` | receptacle DELETE, lighting DELETE | circuited receptacle 467291 removed (circuit 469428 + host plane 467294 survive; the circuit's member connector, 2 wires and the panel bookkeeping neutralised); pendant 444176 removed with its 2 IndependentTags cascaded (circuit + wires neutralised); no surviving reference to any deleted id |

The validator's `--strict` "circuit-ready" gate is also recorded per file:
the created files carry two pre-existing findings from OTHER streams'
code — the create-writer's block-counter identity defect
(`commit.commit_new_elements`, tolerated by Autodesk's reader per the
accepted V20-V29) and the known Extensible-Storage decode gap — and ZERO
connector / circuit / reference findings from this module. The edit and
delete files (via `manipulate.commit_plans`, which does not have the counter
defect) are strict-clean.

## 8 · Findings for other streams (filed in `docs/inbox/mep-devices.md`)

1. **`m_pathNodes[0].m_elemId` = the PANEL, not the first load** — 171/171
   circuits. `KNOWLEDGE.md` §"Electrical circuits" and
   `Document.add_circuit` (which writes the first load) should be corrected;
   this module writes the panel.
2. **Identity scrub vs validator L2.** `commit_new_elements` now runs the G2
   identity scrub (fresh Unique Document GUID) but its minimal commit adds no
   History episode, so every file it writes FAILS the validator's L2 check
   "BasicFileInfo Unique Document GUID == History entry[0]". The device proofs
   pass `identity={"document_guid": <template's GUID>}` to stay
   self-consistent; the real fix (a new History episode carrying the fresh
   GUID, i.e. `streams_edit.record_save()`) belongs to the identity /
   save-history stream, and the earlier H-/V-files may need re-validation.
3. The create path's block-counter defect (3 blocks' A/C headers) is the one
   remaining strict-gate finding on created files — writer-core territory.

## 9 · Confidence / unknowns

| claim | status |
|---|---|
| wall devices: dummy-plane-on-face is the native pattern; frame + fields as §2/§3 | **V** (172 planes / 424 receptacles / 63 switches; readback + validator) |
| ceiling fixtures: down-facing dummy plane at the ceiling underside, no ceiling reference; light Z = plane −Z | **V** (48 planes / 410 fixtures; `test_ceiling_lights_stand_on_downfacing_dummy_planes`) |
| floor / level devices: `OnDatumPlaneRef -> level` plane; free instances for equipment | **V** structure (specimen 573289 + 4 instances) |
| multi-load circuit reference closure; base = LAST = panel slot; back-links; internal units | **V** (187 circuits; graph checked by the validator + readback) |
| path node 0 = the panel | **V** (171/171) — corrects KNOWLEDGE |
| native header parents / space-room / Mark holder creation | **V** shape (5 specimens); regenerated by Revit anyway |
| edits (move within face / re-host / retype / mark) touch every cached field | **V** structural + re-read; **H** for Revit acceptance |
| deletes leave a referentially clean model | **V** (`referrers()` re-scan finds no surviving mention) |
| **all of the above render / regenerate correctly in Autodesk's reader** | **H** — awaiting the orchestrator's viewer certification of the six proof files |

Open items: **O1** circuiting EXISTING devices to an existing panel — needs
the same connector edits applied as in-place record edits (a
`manipulate.modify_element` on the load's / panel's connector `m_arrRefs`
plus a created circuit) in ONE commit; the two commit paths
(`commit_new_elements` / `commit_plans`) are separate today, so this is a
2-stage recipe or a combined commit (phase 2). **O2** the scheduling-level
default (`level_at_or_below`) vs the sample's authored level for pendants
hung below the next level — a caller choice, exposed as `level_id`. **O3**
`m_workPlaneFlipped` / face-flip and mirrored devices (`m_flippedX/Y`) are
written false; a receptacle on a flipped wall face is untested. **O4** an
emptied circuit after a device delete: Revit may drop or flag a circuit whose
member connector references nothing (manipulation.md O5) — deleting the LAST
load of a circuit should probably delete the circuit too (peer today).
**O5** panels grow 50000-series slot connectors as circuits are added; a new
panel's clone has a fixed slot count (4 for the 208 V MLO family) — more
circuits than slots needs new `Connector` objects appended (fresh pids),
not implemented. **O6** load values per receptacle live in the family's
connector calculation data (180 VA is the family default); overriding a
load's VA per instance is not exposed.

## 10 · Reproduction

```
.venv/bin/python experiments/mep/devices/make_devices.py       # 6 files + manifest.json
.venv/bin/python tools/rvt_validate.py experiments/mep/devices/*.rvt
.venv/bin/python -m pytest tests/test_mep_devices.py -q           # 18 passed
.venv/bin/python -m rvt.mep.devices samples/rmebasicsampleproject.rvt   # device inventory
```

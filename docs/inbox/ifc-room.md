# inbox — ifc-room (IFC INTENT -> OUR PROJECT FILE, END TO END)

Stream: **ifc-room** (2026-08-04). Charter: close the front door's two gaps
(positions all `[0.0, 0.0]`; no mapping to our content), emit the resolved
mapped INTENT, and drive it to a project file on the certified genesis base.
Territory touched ONLY: `src/rvt/ifc/intent.py` (new), `tools/ifc_intent.py`
(new), `tests/test_ifc_intent.py` (new, 25 pass), `inputs/ifc/electrical-
room-2500a.intent.json`, `experiments/ifc_room/**`, this file.  No existing
`src/rvt/*.py` / `tools/*` / tests edited (all IMPORTED).  Note: the sibling
fixture stream already owns `src/rvt/ifc/__init__.py` (its `product_facts` /
`famfrom_ifc` sub-modules) — left untouched; `rvt.ifc.intent` imports fine
beside it.  No browser used; the outputs sit on disk for the orchestrator's
viewer gate (probes.json below).

## Result in one screen

* **THE INTENT IS RESOLVED AND MAPPED.** `inputs/ifc/electrical-room-2500a.intent.json`
  (spec v2, 286 KB): all 12 products carry REAL world positions (none at the
  origin), orientation frames, dims, elevation and mounting; the room shell
  proxy is decomposed into 4 walls (a closed 9.2 × 6.2 m centerline ring, the
  cut-away front wall SYNTHESIZED and flagged), 2 out-swinging egress doors
  with their openings (1.0 m wide, 2.13 m head), the floor slab and the two
  housekeeping pads; 8 NEC 110.26 clearance zones each tied to its equipment
  (1.07 m at the switchboard, 0.914 m elsewhere — every check `ok`); the
  FEEDER TREE = 8 edges, all 7 FedFrom edges CORROBORATED by the conduit-run
  named solids (`conduit_msb_dp1` …) plus the UTILITY service edge, each with
  its circuit plan (panel → load, rating, poles, voltage); and the FAMILY
  MAPPING table (below).  `.venv/bin/python -m pytest tests/test_ifc_intent.py`
  → **25 passed**.
* **THE FAMILIES ARE BUILT.** `experiments/ifc_room/families/*.rfa` — 8
  generated families (MSB switchboard, DP-1, DP-2, LP-1, LP-2, LP-3, LP-4,
  T1), every one `verify OK · validate VALID (family mode, 0 errors) ·
  provenance scan ok`; the Pset ratings ride as parameter VALUES on each
  board's own family/type.
* **THE PROJECT FILE IS BUILT ON THE CERTIFIED GENESIS BASE.**
  `experiments/ifc_room/electrical_room_2500a.rvt` = **ZA_deep + our 8
  loaded families + the room's 4 walls + the 7 boards and T1 as OUR family
  instances** (free-standing, intent frames, our connector managers with a
  50000-series slot per outgoing feeder): **rvt_validate VALID, 0 errors**;
  **four-registry COHERENT** (9 save units / 8 ContentDocuments / 8
  ContentTable / GUID sets equal); **identity gate PASS** (author +
  client `rvt-writer`, path/username scrubbed, document GUID coherent with
  History[0]); **status gate: PROOF-ONLY, NOT-DELIVERABLE** (the base is
  the sample-derived genesis lineage — recorded honestly, exactly as the job
  runner records it).  Plus four staged bisection candidates (loaded-only /
  walls-only / walls-only-unjoined / loaded+walls), all VALID.
  `experiments/ifc_room/probes.json` declares every candidate on the
  certified base **ZA_deep** with the byte-identical control
  `CTRL_ZA_deep_ifcroom.rvt` (md5 `56308637...`, == ZA_deep); `probe_batch
  check` → **admissible, 0 violations**.
* **A GENESIS RESULT IN PASSING:** the endgame's open question "do OUR
  component families load onto a FAMILY-FREE base?" is exercised for real —
  `rvt.famgen.loader.load_family_into_project` (place=False) chained 8 loads
  onto ZA_deep, four registries coherent, validator-clean, in 11 s.  Viewer
  acceptance is the orchestrator's gate; the file is staged for it.

## Gap (a) — POSITIONS: what was actually wrong

The front door reads positions from `IfcLocalPlacement` and prints `[0.0,
0.0]` for everything.  Two facts, and this stream resolves BOTH:

1. The placement is a **CHAIN** (product → storey → building → site), each
   link's `RelativePlacement` expressed in its parent's frame; the absolute
   placement is the root-to-leaf composition.  `compose_placement()` walks
   and records the whole chain (a synthetic-IFC test proves it against a
   rotated + translated nested chain and cross-checks
   `ifcopenshell.util.placement`).
2. **Our own three-d-stage writer bakes world coordinates into the
   tessellated vertices** and gives EVERY product the SAME identity
   `IfcAxis2Placement3D` (#9 in this file) — the chain genuinely composes
   to the identity (chain depth 4, every link `relative_identity: true` in
   the intent JSON), so the position is NOT in the placement graph at all:
   it is in the `IfcCartesianPointList3D` vertices.  `analyze_product()`
   transforms every tessellated body by the composed chain into WORLD
   space (`world = composed_chain @ local vertices`, exact for both writer
   styles) and recovers the insertion point (footprint centre at the body
   base for floor gear; the enclosure BACK-FACE centre = the mounting plane
   for wall gear), the front normal (from named front features — door /
   nameplate / meter / breaker faces — or the thin footprint axis toward the
   room interior), the orientation frame (an UPRIGHT work-plane frame for
   wall equipment: family +Z = front normal, +Y = up; a yaw frame for floor
   equipment: family +X = width axis, front = family −Y), the dims (extents
   along the width / front axes, height) and the elevation.  Every number in
   the JSON carries `positionSource` ("geometry-recovered (placement chain
   composes to the identity; world-baked vertices)").

Resolved (metres, world; audit: `positions_all_zero=false`,
`equipment_inside_room_ring=12/12`):

| tag | kind | insertion (x, y, z) | frame | note |
|---|---|---|---|---|
| MSB | switchboard | (−2.067, 2.588, 0.100) | yaw 0, front −Y | 4.27 × 0.62 × 2.29 m lineup on the north pad |
| T1 | transformer | (2.700, 2.475, 0.100) | yaw 0, front −Y | on its pad |
| DP-1 / DP-2 | distribution panelboard | (∓4.455, 1.700, 1.314) | upright, front ±X | mirrored on the west / east walls, top 2.0 m |
| LP-1 / LP-2 | lighting panelboard | (−4.455, ±0.550, 1.543) | upright, front +X | west wall |
| LP-3 / LP-4 | lighting / receptacle | (4.455, ±0.550, 1.543) | upright, front −X | east wall |
| TMGB | ground bus | (0.900, 2.968, 1.475) | upright, front −Y | north wall, 1.5 m AFF (recorded) |

## Gap (b) — MAPPING: the tagging contract IS the join key

`normalize_contract()` folds whichever schedule Pset a board carries
(`PanelSchedule` / `SwitchboardSchedule` / `TransformerSchedule` /
`Pset_ManufacturerTypeInformation`) into the revit-bridge contract names,
filling gaps from the name text (`(\d+) A`, `NN space`, MLO/MB), each value
recording its provenance (`pset:PanelSchedule.BusRating`, `name-text`, …).
`plan_families()` maps each item onto ONE of our constructors and RUNS the
facts resolvers so the plan records fact / assumed / refusal per field, and
the modeled-vs-catalog dims side by side:

| tag | Pset (join key) | our constructor | catalog member (facts) | modeled → catalog dims |
|---|---|---|---|---|
| DP-1, DP-2 | PanelSchedule 400 A MB 42 sp 480Y/277 | `famgen.factory.make_panelboard(eaton pow-r-line, 400 A, 42, mcb, surface)` | **PRL2X** (W 20 in fact; H 60 in *assumed* — borrowed from the PRL1X box family, surfaced; sccr assumed) | w 0.508 → 0.508 (EXACT — our writer modeled the Eaton box), h 1.372 → 1.524, d 0.19 → 0.146 |
| LP-1..3 | 100 A MLO 30 sp 480Y/277 | same, `mcb=False`, 30 spaces | **PRL2X** (H 48 in assumed) | h 0.914 → 1.219 |
| LP-4 | 225 A MB 42 sp 208Y/120 | same, 208Y/120 | **PRL1X** (240 V class; H 48 in fact) | h 0.914 → 1.219 |
| T1 | TransformerSchedule 150 kVA 480 delta → 208Y/120 | `famgen.factory.make_transformer(150, eaton, 480, 208Y/120)` | **V48M28T4916** (all dims / weight facts, no assumed fields) | 0.9×0.75×1.14 → 0.876×0.80×1.295 |
| MSB | SwitchboardSchedule 2500 A 480Y/277 65 kA 4-section | **`rvt.ifc.intent.make_house_switchboard`** — the panelboard resolver is asked FIRST and REFUSES honestly: `FactoryError: no sizing rows for 2500.0 A mains; tabulated: [100, 225, 400, 600]` (recorded in the plan); no switchboard product / catalog line exists, so the house family is composed from OUR OWN IFC-modeled lineup extents (our provenance — the IFC is our authoring) with the Pset ratings as parameter values; Eaton / "Pow-R-Line C style switchboard" ride as *ifc-declared* identity strings, not catalog facts | 4.27 × 0.62 × 2.29 (= modeled) |
| TMGB, conduits, hangers, clearances | — | unmapped, each with a stated reason (ground-bus generic family follow-up; `rvt.mep.conduit` over the recorded runs; detailing; annotation) | — | — |

The house switchboard is a real generated family: Electrical Equipment,
part type 16 (switchboard), the tagging-contract parameters, one 3-pole
supply connector on the top face; validate VALID (family mode) + provenance
scan clean — same building blocks as `make_transformer`, so the loader /
placement path treats it like any factory product.

## The pipeline (tools/ifc_intent.py room), stage results

| stage | mechanism | output | verdict |
|---|---|---|---|
| F families | `plan.constructor(**kwargs).write()` (famgen) | `families/*.rfa` (8) | all `ok`: verify · validate VALID (family) · provenance ok |
| L load ×8 | `rvt.famgen.loader.load_family_into_project(place=False)` CHAINED, each product rebuilt at `start_id = host watermark + 1` | `stage_L1..L8_*.rvt` | 8/8; final `stage_L8_lp4.rvt` **VALID, four-registry coherent** (9 units / 8 CD / 8 CT / GUIDs equal) — component families onto a FAMILY-FREE base, first time |
| W walls | `rvt.mutate.Document.add_wall` × 4 on the base's own wall type **600634**, level 311 (L1 - Ground Floor), 3.66 m; specimen scaffolding from the base's certified ANCESTOR R5 (same wall type id in both files; ids continuous through the in-place lineage; the specimen is a clone TEMPLATE, never emitted) + the clone clean-up below | `electrical_room_2500a_walls_only.rvt` (+ `_unjoined` twin), `stage_W_loaded_walls.rvt` | **VALID, 0 errors** all three |
| E equipment | `Document.add_family_instance` × 8 pointed at OUR loaded symbols (symbol == masterSymbol, free-standing), the intent's full frame written into `m_Trf` (upright 3×3 for the six wall panels — the certified free-standing wall-family precedent = V23..V29), our connector manager per instance via the loader's slot builder (+ one 50000-series slot per outgoing feeder ⇒ circuit-ready), scaffolding specimen = the CLEANEST placed model instance in the ancestor (auto-scored: no instance geometry steps / rebar / cover cells / param rows; the door-category record 975217, already on level 311 / phase 86961), header category patched to Electrical Equipment (−2001040), specimen-symbol refs repointed, door FamInstSpec dropped — per-instance scrub log recorded; **0 dangling refs per instance** | `electrical_room_2500a.rvt` | **VALID, 0 errors; four-registry coherent; identity PASS** |
| C circuits | `Document.add_circuit` per feeder edge | — | **NAMED BLOCKER** (below) |
| V gates | `rvt.validate` + `famload.four_registry_census` + `rvt_job.identity_gate` + `rvt_job.provenance_gate` + `probe_batch.check_batch` | `build_record.json`, `probes.json`, `CTRL_ZA_deep_ifcroom.rvt` | all candidates VALID · coherent · identity PASS; status **PROOF-ONLY, NOT-DELIVERABLE**; batch admissible |

The written room file decodes as intended (`Document.from_file`): 8
FamilyInstances on level 311, category −2001040, symbols = our '2500A
4-section' / '400A MCB 42ckt' ×2 / '100A MLO 30ckt' ×3 / '225A MCB 42ckt'
/ '150 kVA 480-208Y/120', origins in feet at the intent positions, upright
`m_3x3` on the wall panels, connector slots MSB 7 / T1 3 / panels 1; 4
SWalls of type 600634 on level 311 forming the 30.18 × 20.34 ft ring; 8 of
our Families + 8 symbols; ElemTable 3,342 → 3,497 rows.

## The wall-clone finding (worth a KNOWLEDGE.md line)

EVERY same-type wall specimen in the lineage (R5's 9 walls, the rstbasic
sample's 9 walls — all type 600634) is a **JOINED, painted** wall: the
`rvt.mutate.add_wall` clone (which correctly resets the join *lists* and
rebuilds the ref-face planes) still carries (a) `m_cellList` stable-face-ref
overrides whose `m_geomRef.m_elemId` = the SPECIMEN and whose `m_setting` = a
paint `CoverType` element absent here, (b) `WallJoinTweakGStep.
m_affectedEdgesTags[k].first` = the specimen's partner walls, (c) join-end /
split-face geometry steps + cached snapshots of the joined solid, (d) header
`m_regenOnly` / `m_appearanceParents` = **element 30 = the Walls-category
GStyleElem — one of the 235 built-in catalog rows the R9 lineage GC'd away**
(ZA_deep does NOT carry the Walls category style; the ADD-cat rung is the
endgame's Phase II).  The tool's `_clean_wall_clone()` repairs (a)(b)(d) in
mode `min` (history + snapshots KEPT — the certified V22/V26 wall clones
kept their template's stale history) and additionally trims to the textbook
UNJOINED history in mode `unjoin`; the two `walls_only` probes are that
bisection.  A viewer FAIL on walls with a card message about missing
category machinery would point at the 235-row ADD-cat rung, not at our
walls — the probe manifest says so.

## Named blockers / missing pieces (exact)

1. **CIRCUITS (stage C).** `rvt.mutate.Document.add_circuit` CLONES an
   `RbsElectricalSystem` specimen (`_template_circuit()`) and wires elements
   created in the SAME commit.  The family-free structural-lineage base
   (and its R5 ancestor) carries **no circuit** ⇒ `LookupError`.  Missing
   piece: an **`RbsElectricalSystem` CONSTRUCTOR** (or a same-commit
   circuit template).  Everything upstream is READY: the intent's
   `feederTree.circuitPlan` (7 edges + ratings + poles + voltage,
   geometry-corroborated) and one unconnected 50000-series slot per
   outgoing feeder on every placed board (MSB 6, T1 → LP-4 on its
   secondary).  KNOWLEDGE.md's circuit model (owner connectors + panel slot
   back-links, connType 4) is the constructor's spec.
2. **FACE-HOSTING** (fidelity, not correctness): panels are FREE-STANDING
   at the intent frame (the V23..V29 free wall-family precedent).  Hosting
   on the CREATED walls = `rvt.hosting.add_sketchplane_on_wall` +
   `host_instance_on_wall` (certified H1/H2) — it too clones a face-
   SketchPlane template + a hosted-instance template, absent here; the walls
   and the intent's mounting planes (`insertion_m` = the enclosure back
   face; wall side by front normal) are the ready inputs.
3. **INSTANCE-LEVEL parameter rows** (per-instance PanelName / mounting
   height): our specimen-scaffolded clones carry NO instance param rows
   keyed by our families' ParamElemFamily TWINS (the famgen loader's
   `author_family_instance` writes those when IT places, but it needs a
   host specimen of the category).  Today the tag rides on each board's own
   family/type (one family per board), which is why 8 families rather than
   5 — the Pset values ARE on the placed content, at the type level.
4. **Doors / conduit runs / pads / TMGB / clearances**: recorded in the
   intent with dispositions (door family + wall hosting/cut = the fixture
   stream + hosting; `rvt.mep.conduit.add_conduit_path` over the recorded
   run geometry needs conduit TYPES in the base; pads/slab = floor stream;
   TMGB = a small generic family; clearances = plan-view annotation).
5. **`src/rvt/ifc/__init__.py`** (owned by the fixture stream) does not
   list `intent` — suggested one-line addition to its docstring/`__all__`
   (not applied; their file):
   `* :mod:`rvt.ifc.intent` -- resolve an authored IFC into the placement-true, mapped INTENT (spec v2).`

## The exact fix-diff for tools/ifc_to_spec.py (NOT applied — outside territory)

Surgical (positions / rotations / dims from the resolver; ~25 lines):

```diff
--- a/tools/ifc_to_spec.py
+++ b/tools/ifc_to_spec.py
@@
 import ifcopenshell.util.placement as upl
 import numpy as np
+
+# GAP (a): the placement CHAIN composes to the identity in the three-d-stage
+# writer's exports (world-baked vertices) -> resolve position / rotation /
+# dims from the chain-composed tessellated geometry (rvt.ifc.intent).
+import os as _os, sys as _sys
+_sys.path.insert(0, _os.path.join(_os.path.dirname(_os.path.dirname(
+    _os.path.abspath(__file__))), "src"))
+from rvt.ifc import intent as _I
@@ def extract(path: str) -> dict:
     for cls, kind in KIND_BY_CLASS.items():
         for eq in list(f.by_type(cls)):
-            m = _placement_matrix(eq)
-            pos = m[:3, 3] * scale
-            xdir = m[:3, 0]
-            rot = math.degrees(math.atan2(float(xdir[1]), float(xdir[0])))
-            bb = _bbox(f, eq, settings, scale)
-            dims = None
-            if bb is not None:
-                lo, hi = bb
-                ext = (hi - lo)
-                dims = {"w": round(float(ext[0]), 4), "d": round(float(ext[1]), 4),
-                        "h": round(float(ext[2]), 4)}
+            plc, geom = _I.analyze_product(f, eq, scale=scale)      # chain @ geometry
+            _ps = _I._psets(eq)
+            _con = _I.normalize_contract(_ps, name=eq.Name or "", object_type=eq.ObjectType,
+                                         description=eq.Description, tag=eq.Tag)
+            _e = _I.Equipment(step_id=eq.id(), guid=eq.GlobalId, ifc_class=cls,
+                              predefined_type=str(getattr(eq, "PredefinedType", "") or "") or None,
+                              name=eq.Name or "", tag=str(eq.Tag or eq.Name),
+                              description=eq.Description, object_type=eq.ObjectType,
+                              type_name=None, kind=_I._classify_equipment(eq, _ps, _con),
+                              psets=_ps, contract=_con, placement=plc, geometry=geom)
+            _I._resolve_equipment_placement(_e, room_center_xy=None)
+            pos = _e.insertion_m                    # metres, world
+            rot = _e.yaw_deg                       # + _e.frame3x3 / front for wall gear
+            dims = {"w": round(_e.dims_m.get("w", 0.0), 4),
+                    "d": round(_e.dims_m.get("d", 0.0), 4),
+                    "h": round(_e.dims_m.get("h", 0.0), 4)}
             psets = {}
@@
             rec = {
                 "kind": kind, "name": eq.Name or eq.GlobalId,
                 "level": "L1",
                 "position": [round(float(pos[0]), 4), round(float(pos[1]), 4)],
-                "rotationDeg": round(rot, 2),
-                "elevation": round(float(pos[2]), 4),
+                "rotationDeg": round(float(rot), 2),
+                "elevation": round(float(_e.elevation_m), 4),
+                "front": [round(float(x), 4) for x in _e.front_normal[:2]],
+                "frameKind": _e.frame_kind,
                 "typeName": (etype.Name if etype else None) or (eq.ObjectType or kind),
```

The wall side (the four-wall synthesis from the whole-product bbox counts
the swung-open door leaves and yields 11.06 × 6.2 m instead of the true 9.2
× 6.2 m ring) is better replaced wholesale: call
`rvt.ifc.intent.resolve_intent(path)` and adapt `model.room.walls` /
`model.room.doors` / `model.equipment` / `model.feeders` into the v1 spec
shape — i.e. keep `ifc_to_spec.py` as a thin v1-spec ADAPTER over the intent,
which is now the single extraction engine.

## Probes for the orchestrator (upload set)

`experiments/ifc_room/probes.json` (base = certified ZA_deep for every
candidate; control declared).  Suggested batch, control first:

1. `CTRL_ZA_deep_ifcroom.rvt` — byte-identical certified copy (round validity).
2. `stage_L8_lp4.rvt` (**IFCR_loaded**) — OUR 8-family component layer on the
   family-free base, no placement variable.  PASS = the endgame's family-
   load question answered YES.
3. `electrical_room_2500a_walls_only.rvt` (**IFCR_walls_only**, mode `min`)
   and `electrical_room_2500a_walls_only_unjoined.rvt` — the wall add path
   on this base (Walls-category GStyle row absent) + the history-trim
   bisection.
4. `stage_W_loaded_walls.rvt` (**IFCR_walls**) — families + walls together.
5. `electrical_room_2500a.rvt` (**IFCR_room**) — the FULL room; a FAIL with
   3–4 PASS convicts the instance layer (cross-category scaffolding /
   upright free frames / connector managers).

Stage them through the gate to get the manifest + a fresh CTRL:
`.venv/bin/python tools/probe_batch.py stage experiments/ifc_room/{stage_L8_lp4,electrical_room_2500a_walls_only,electrical_room_2500a_walls_only_unjoined,stage_W_loaded_walls,electrical_room_2500a}.rvt`
(`check` on that set → admissible, 0 violations).

## How to run

```
.venv/bin/python tools/ifc_intent.py intent   inputs/ifc/electrical-room-2500a.ifc \
    -o inputs/ifc/electrical-room-2500a.intent.json           # ~1 s
.venv/bin/python tools/ifc_intent.py families inputs/ifc/electrical-room-2500a.ifc \
    -d experiments/ifc_room                                    # 8 x .rfa, ~20 s
.venv/bin/python tools/ifc_intent.py room     inputs/ifc/electrical-room-2500a.ifc \
    -d experiments/ifc_room --stages FLWECV                  # the whole pipeline, ~90 s
.venv/bin/python -m pytest tests/test_ifc_intent.py            # 25 passed
```

## Requests for the orchestrator

1. **VIEWER-GATE the ifc-room batch above** (probes.json read order).  The
   `loaded` probe alone answers a standing endgame question (component-family
   load on the family-free base); the `walls_only` pair isolates the never-
   before-tested "placed walls with the Walls-category GStyle row absent".
2. **KNOWLEDGE.md lines to merge:** (i) *the three-d-stage IFC writer bakes
   world coordinates into the tessellated vertices; every product's placement
   chain is 4 links of the SAME identity Axis2Placement3D — positions must be
   recovered from the chain-composed geometry (rvt.ifc.intent), and the
   tagging-contract Pset is the join key to our generated families;* (ii)
   *every same-type wall specimen in the rst lineage is JOINED + painted; a
   wall clone needs the reference clean-up (self face-ref repoint, paint-map
   clear, partner-tag clear, header parents filtered to existing ids — the
   Walls-category GStyle row 30 is among the 235 GC'd catalog rows);* (iii)
   *the cleanest placement scaffolding in the family-free lineage's ancestor
   is a small placed model instance with null geometry steps (score in
   tools/ifc_intent.py SpecimenSet), not a column (rebar / joins / cover
   baggage).*
3. **Next constructors** (unblock stage C / raise fidelity): an
   `RbsElectricalSystem` circuit CONSTRUCTOR against the KNOWLEDGE.md circuit
   model; a face-SketchPlane + hosted-instance path that needs no template
   (or accepts a specimen file); the ADD-cat rung (235 catalog rows) so the
   Walls category has its projection GStyle.

## BRANCH STATE

* **DONE** (this session): `src/rvt/ifc/intent.py` (the resolver: placement
  chains + world geometry + tagging-contract mapping + room shell + feeder
  tree + clearances + family plan + house switchboard); `tools/ifc_intent.py`
  (intent / families / room CLI, the staged pipeline with checkpoints, wall
  clean-up, specimen scoring, the four gates, probes.json); `tests/
  test_ifc_intent.py` — **25 passed**; `inputs/ifc/electrical-room-
  2500a.intent.json` (spec v2, resolved + mapped); `experiments/ifc_room/`:
  the intent, 8 validated families, `electrical_room_2500a.rvt` (**VALID 0
  errors · four-registry coherent · identity PASS · PROOF-ONLY**) + 4
  bisection candidates + the certified control + `probes.json` (admissible)
  + `build_record.json` (every stage's evidence); this record.
* **BLOCKED, NAMED:** feeder CIRCUITS (no `RbsElectricalSystem` specimen /
  constructor — the circuit plan + panel slots are ready); face-hosting;
  per-instance parameter rows; doors / conduits / pads / TMGB.
* **NOT VIEWER-TESTED**: every `.rvt` above is validator/registry/identity-
  clean but AWAITS the orchestrator's viewer gate — no acceptance claim is
  made here.  The status is PROOF-ONLY: the base is the sample-derived
  genesis lineage (ZA_deep = the rst sample reduced + 54 % substituted in
  place by our constructors — NOT a clean-room file); our added layer
  (families, walls, instances) is ours.
* **Full suite**: running at record time; count reported by the session.

Files (all under the repo root): `src/rvt/ifc/intent.py`,
`tools/ifc_intent.py`, `tests/test_ifc_intent.py`, `inputs/ifc/electrical-
room-2500a.intent.json`, `experiments/ifc_room/{electrical_room_2500a.rvt,
electrical_room_2500a_walls_only.rvt, electrical_room_2500a_walls_only_
unjoined.rvt, stage_W_loaded_walls.rvt, stage_L1..L8_*.rvt, CTRL_ZA_deep_
ifcroom.rvt, probes.json, build_record.json, electrical-room-2500a.intent.
json, families/*.rfa}`, `docs/inbox/ifc-room.md`.

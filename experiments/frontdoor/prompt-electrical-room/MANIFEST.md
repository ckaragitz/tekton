# Deliverable manifest — route `prompt`

**Status:** PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)
**Tool:** tekton frontdoor (rvt.frontdoor) v1.0.0 · 2026-08-04T17:49:45Z

## Input
- **prompt**: `an electrical room 30x20 ft rated for 2500 A service with a main switchboard, two 400 A distribution panels and four lighting panels`
- **fallback_parser**: `rules-first deterministic (no external model call, no API key)`

## Base (certified genesis base — never an Autodesk sample)
- file: `/Users/ck/dev/things/rev-revit/experiments/genesis/subst_k4/compose/G_ABPD.rvt` (source: pinned-repo, sha256 `84173b8960b8cbba…`)
- pinned: True · certified genesis base: True · Autodesk sample: False
- certification: THE COMPOSED GENESIS PROJECT BASE LOADS: G_ABP + the 240-element lawful maxgc deletion set; validator VALID 0 errors, EDIT-FREE, four-registry coherent; the Autodesk viewer opens it as a browsable model (3D view + sheet 'GEN-101 - GEN OVERALL PLAN', not empty, not corrupt)
  - verdict: docs/inbox/genesis-audit.md '***** ORCHESTRATOR VERDICTS #24' (2026-08-04): GENESIS LOADS

## Intent
- project: Electrical Room - 2500 A service
- room `Electrical Room`: 4 walls (0 synthesized), 0 doors
- equipment (7): switchboard×1, distribution_panelboard×2, lighting_panelboard×4
- family plans: house 1, resolved 6
- feeder edges: 7
- intent JSON: `experiments/frontdoor/prompt-electrical-room/intent.json`

## Prompt coverage (what the fallback parser understood)
- understood: “30x20 ft” → room dimensions
- understood: “rated for 2500 A service” → service rating
- understood: “main switchboard” → equipment
- understood: “distribution panels” → equipment
- understood: “lighting panels” → equipment
- default: room height: 3.6576 m (12 ft)
- default: wall thickness: 0.2032 m location-line offset (the built wall uses the base wall type's compound structure)
- default: service voltage system: 480Y/277 V
- default: MSB: bus rating 2500 A (= the room's service rating)
- default: MSB: voltage 480Y/277 V (service system)
- default: MSB: main breaker (switchboard default)
- default: MSB: SCCR 65 kA (typical 480 V service default; an ordering value, not a catalog fact)
- default: MSB: 4 sections (lineup sizing rule round(A/625), clamped 2..6)
- default: DP-1: voltage 480Y/277 V (service system)
- default: DP-1: MCB (main breaker kind default)
- default: DP-1: 42 spaces (default)
- default: DP-2: voltage 480Y/277 V (service system)
- default: DP-2: MCB (main breaker kind default)
- default: DP-2: 42 spaces (default)
- default: LP-1: 100 A bus (kind default)
- default: LP-1: voltage 480Y/277 V (service system)
- default: LP-1: MLO (main lugs only kind default)
- default: LP-1: 42 spaces (default)
- default: LP-2: 100 A bus (kind default)
- default: LP-2: voltage 480Y/277 V (service system)
- default: LP-2: MLO (main lugs only kind default)
- default: LP-2: 42 spaces (default)
- default: LP-3: 100 A bus (kind default)
- default: LP-3: voltage 480Y/277 V (service system)

## Primary prompt path — the AI-surface handoff
- scene_brief: `experiments/frontdoor/prompt-electrical-room/scene-brief.json`
- handoff: `experiments/frontdoor/prompt-electrical-room/HANDOFF.md`
- instructions: `experiments/frontdoor/prompt-electrical-room/PROMPT_TO_IFC.md`
- primary_path_note: `an AI surface executes HANDOFF.md/scene-brief.json with Three.js, exports IFC4 (revit-bridge exporter, our tagging-contract Psets), and the .ifc re-enters via `frontdoor author --ifc` -- the recommended path`

## Build
- degrade mode: **stamp-proof-only** — default: ONE combined file (the room's walls + the loaded families + their instances) is emitted and the manifest is STAMPED 'PROOF-ONLY: walls+families combination unverified' -- this exact combination is the OPEN BUG (unverified/failing in the viewer). Pass --strict to get two coordinated proven-shaped files instead.
- **STAMP: PROOF-ONLY: walls+families combination unverified**
- open bug: created WALLS + LOADED FAMILY DOCUMENTS in the SAME file currently trip Autodesk's audit ('Processing failed'), while walls alone PASS (electrical_room_2500a_walls_only.rvt, certified) and loaded families alone PASS (stage_L8_lp4.rvt, certified) -- docs/inbox/genesis-audit.md ORCHESTRATOR VERDICTS #24 (verdict #22's 'one defective family' RETRACTED). The mechanism is under bisection in the render/creation stream; until it is fixed the front door DEGRADES: --strict emits two coordinated files (shell + equipment), the default emits one combined file STAMPED 'PROOF-ONLY: walls+families combination unverified'.
- file **combined**: `experiments/frontdoor/prompt-electrical-room/electrical_room_prompt.rvt` (655360 bytes, sha256 `cde47a7590825200…`)
- family: `Switchboard MSB 2500A 480Y/277` (MSB; house family (our own modeled extents; no catalog line covers the rating); ok=True)
- family: `Distribution Panelboard DP-1 480Y/277 400A MB 42sp` (DP-1; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Distribution Panelboard DP-2 480Y/277 400A MB 42sp` (DP-2; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Lighting Panelboard LP-1 480Y/277 100A MLO 42sp` (LP-1; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Lighting Panelboard LP-2 480Y/277 100A MLO 42sp` (LP-2; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Lighting Panelboard LP-3 480Y/277 100A MLO 42sp` (LP-3; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Lighting Panelboard LP-4 480Y/277 100A MLO 42sp` (LP-4; eaton/pow-r-line-panelboards PRL2X; ok=True)
- created: 4 walls, 7 equipment instances, 7 loaded families
- self-checks **combined**: validator VALID (0 errors, 1 warnings); registries coherent=True; identity PASS
- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — P0 genesis gate G1 fails (the base carries derived expression that G1 blocks): FAIL — 3,060 Autodesk-derived element(s) in expression-bearing categories. Nothing built on a sample base is a product; ship only from a certified genesis base.
- **degradation**: feeder CIRCUITS not authored: NO CIRCUIT SPECIMEN in the base or the loaded file (the family-free structural-lineage base carries no RbsElectricalSystem; rvt.mutate.add_circuit CLONES one) -- an RbsElectricalSystem CONSTRUCTOR is the exact missing piece.  The feeder tree is fully resolved (edges + ratings + poles + voltage, corroborated by the conduit geometry) and every placed board carries an unconnected 50000-series slot per outgoing feeder, so each edge is one add_circuit(panel, load) call once a constructor / same-commit circuit template exists.  (LookupError: electrical_room_prompt: no 2-connector circuit specimen to clone) -- the resolved circuit PLAN rides in the manifest (rvt.mep add_circuit / a Revit-side add-in build them from it)

## Honesty
- **PROOF-ONLY: walls+families combination unverified**
- **PROOF-ONLY, NOT-DELIVERABLE**
- self_checks: rvt.validate (0 errors), four-registry coherence, identity gate -- prove OUR OWN invariants; reported per file below
- autodesk_acceptance: NOT claimed by this run: only the Autodesk Viewer / Revit prove acceptance (upload -> 'translated' -> open the {3D} view). Report both tiers separately, never conflated.
- load_vs_render: every certification behind these shapes is a LOAD pass; created walls carry a SerializedDummy rep (desktop Revit regenerates; the cloud viewer does NOT) and our loaded symbols carry real solids -- RENDER (baked geometry) is the render stream's second gate
- release: Revit 2026 target (the base and the schema are 2026); Revit cannot open a newer file -- confirm the customer's Revit version before promising a .rvt

## CRUD — everything created is editable / deletable
- entrypoint: `python tools/frontdoor.py author --rvt experiments/frontdoor/prompt-electrical-room/electrical_room_prompt.rvt --edit "<sentence | ops.json | inline JSON>" --out <dir>`
- `W-S` (id 1472942, wall): delete: `delete 1472942`
- `W-E` (id 1472943, wall): delete: `delete 1472943`
- `W-N` (id 1472944, wall): delete: `delete 1472944`
- `W-W` (id 1472945, wall): delete: `delete 1472945`
- `MSB` (id 1472946, equipment-instance): move: `move MSB to X,Y,Z ft`; retype: `retype MSB to <symbol id>`; delete: `delete MSB with cascade`
- `DP-1` (id 1472947, equipment-instance): move: `move DP-1 to X,Y,Z ft`; retype: `retype DP-1 to <symbol id>`; delete: `delete DP-1 with cascade`
- `DP-2` (id 1472948, equipment-instance): move: `move DP-2 to X,Y,Z ft`; retype: `retype DP-2 to <symbol id>`; delete: `delete DP-2 with cascade`
- `LP-1` (id 1472949, equipment-instance): move: `move LP-1 to X,Y,Z ft`; retype: `retype LP-1 to <symbol id>`; delete: `delete LP-1 with cascade`
- `LP-2` (id 1472950, equipment-instance): move: `move LP-2 to X,Y,Z ft`; retype: `retype LP-2 to <symbol id>`; delete: `delete LP-2 with cascade`
- `LP-3` (id 1472951, equipment-instance): move: `move LP-3 to X,Y,Z ft`; retype: `retype LP-3 to <symbol id>`; delete: `delete LP-3 with cascade`
- `LP-4` (id 1472952, equipment-instance): move: `move LP-4 to X,Y,Z ft`; retype: `retype LP-4 to <symbol id>`; delete: `delete LP-4 with cascade`
- not available on created instances — **rename / set-mark**: front-door instances are specimen-scaffolded clones with NO instance parameter rows (the tag/PanelName rides on each board's own generated family + type) -- rename = regenerate with a new tag; `rename`/`set-mark` DO work on native instances in a user's file (--rvt route)
- recreate: re-run the same `frontdoor author` command (deterministic for the same inputs) -- outputs are regenerated from the intent
- start_over: the base is untouched; delete the output directory to discard the whole created layer
- circuits: feeder circuits are NOT authored on this base yet (named blocker in the manifest); the resolved circuit plan is in the intent's feederTree.circuitPlan -- rvt.mep add_circuit / a Revit-side add-in consume it
- coverage-matrix cells exercised: electrical_equipment:create, families:create, walls:create

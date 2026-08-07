# Deliverable manifest — route `ifc`

**Status:** PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)
**Tool:** tekton frontdoor (rvt.frontdoor) v1.0.0 · 2026-08-04T17:50:33Z

## Input
- **ifc**: `/Users/ck/dev/things/rev-revit/inputs/ifc/electrical-room-2500a.ifc`
- **intent_resolver**: `rvt.ifc.intent (placement chains + world geometry + tagging-contract Pset join key)`

## Base (certified genesis base — never an Autodesk sample)
- file: `/Users/ck/dev/things/rev-revit/experiments/genesis/subst_k4/compose/G_ABPD.rvt` (source: pinned-repo, sha256 `84173b8960b8cbba…`)
- pinned: True · certified genesis base: True · Autodesk sample: False
- certification: THE COMPOSED GENESIS PROJECT BASE LOADS: G_ABP + the 240-element lawful maxgc deletion set; validator VALID 0 errors, EDIT-FREE, four-registry coherent; the Autodesk viewer opens it as a browsable model (3D view + sheet 'GEN-101 - GEN OVERALL PLAN', not empty, not corrupt)
  - verdict: docs/inbox/genesis-audit.md '***** ORCHESTRATOR VERDICTS #24' (2026-08-04): GENESIS LOADS

## Intent
- project: Electrical room - 2500 A service
- room `Electrical room shell`: 4 walls (1 synthesized), 2 doors
- equipment (12): ground_bus×1, transformer×1, switchboard×1, distribution_panelboard×2, lighting_panelboard×3, receptacle_panelboard×1, conduit_run×1, service_entrance×1, support×1
- family plans: unmapped 4, resolved 7, house 1
- feeder edges: 8
- intent JSON: `experiments/frontdoor/ifc-electrical-room-2500a/intent.json`

## Build
- degrade mode: **stamp-proof-only** — default: ONE combined file (the room's walls + the loaded families + their instances) is emitted and the manifest is STAMPED 'PROOF-ONLY: walls+families combination unverified' -- this exact combination is the OPEN BUG (unverified/failing in the viewer). Pass --strict to get two coordinated proven-shaped files instead.
- **STAMP: PROOF-ONLY: walls+families combination unverified**
- open bug: created WALLS + LOADED FAMILY DOCUMENTS in the SAME file currently trip Autodesk's audit ('Processing failed'), while walls alone PASS (electrical_room_2500a_walls_only.rvt, certified) and loaded families alone PASS (stage_L8_lp4.rvt, certified) -- docs/inbox/genesis-audit.md ORCHESTRATOR VERDICTS #24 (verdict #22's 'one defective family' RETRACTED). The mechanism is under bisection in the render/creation stream; until it is fixed the front door DEGRADES: --strict emits two coordinated files (shell + equipment), the default emits one combined file STAMPED 'PROOF-ONLY: walls+families combination unverified'.
- file **combined**: `experiments/frontdoor/ifc-electrical-room-2500a/electrical-room-2500a.rvt` (663552 bytes, sha256 `f6392557c6b13b8e…`)
- family: `Dry Type Transformer T1 150kVA 480-208Y/120` (T1; eaton/dry-type-transformers V48M28T4916; ok=True)
- family: `Switchboard MSB 2500A 480Y/277` (MSB; house family (our own modeled extents; no catalog line covers the rating); ok=True)
- family: `Distribution Panelboard DP-1 480Y/277 400A MB 42sp` (DP-1; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Lighting Panelboard LP-1 480Y/277 100A MLO 30sp` (LP-1; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Lighting Panelboard LP-2 480Y/277 100A MLO 30sp` (LP-2; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Distribution Panelboard DP-2 480Y/277 400A MB 42sp` (DP-2; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Lighting Panelboard LP-3 480Y/277 100A MLO 30sp` (LP-3; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Receptacle Panelboard LP-4 208Y/120 225A MB 42sp` (LP-4; eaton/pow-r-line-panelboards PRL1X; ok=True)
- created: 4 walls, 8 equipment instances, 8 loaded families
- self-checks **combined**: validator VALID (0 errors, 1 warnings); registries coherent=True; identity PASS
- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — P0 genesis gate G1 fails (the base carries derived expression that G1 blocks): FAIL — 3,062 Autodesk-derived element(s) in expression-bearing categories. Nothing built on a sample base is a product; ship only from a certified genesis base.
- **degradation**: TMGB (ground_bus): NOT built -- family plan unmapped: no house generator for a ground bus bar (a small generic-model family is the follow-up; the TMGB is a detail component, not equipment) -- recorded only (the facts store never invents dimensions/ratings; supply the missing facts or choose a covered rating)
- **degradation**: CONDUIT (conduit_run): NOT built -- family plan unmapped: conduit RUNS are rvt.mep.conduit territory (add_conduit_path over the recorded polyline); needs conduit types in the base -- recorded as run geometry, omitted from v1 (the facts store never invents dimensions/ratings; supply the missing facts or choose a covered rating)
- **degradation**: SERVICE (service_entrance): NOT built -- family plan unmapped: utility service entrance: external source -- recorded as the SERVICE edge of the feeder tree (the facts store never invents dimensions/ratings; supply the missing facts or choose a covered rating)
- **degradation**: HANGERS (support): NOT built -- family plan unmapped: trapeze hangers / clevis supports = detailing (supports stream); recorded, omitted from the project file (the facts store never invents dimensions/ratings; supply the missing facts or choose a covered rating)
- **degradation**: feeder CIRCUITS not authored: NO CIRCUIT SPECIMEN in the base or the loaded file (the family-free structural-lineage base carries no RbsElectricalSystem; rvt.mutate.add_circuit CLONES one) -- an RbsElectricalSystem CONSTRUCTOR is the exact missing piece.  The feeder tree is fully resolved (edges + ratings + poles + voltage, corroborated by the conduit geometry) and every placed board carries an unconnected 50000-series slot per outgoing feeder, so each edge is one add_circuit(panel, load) call once a constructor / same-commit circuit template exists.  (LookupError: electrical-room-2500a: no 2-connector circuit specimen to clone) -- the resolved circuit PLAN rides in the manifest (rvt.mep add_circuit / a Revit-side add-in build them from it)

## Honesty
- **PROOF-ONLY: walls+families combination unverified**
- **PROOF-ONLY, NOT-DELIVERABLE**
- self_checks: rvt.validate (0 errors), four-registry coherence, identity gate -- prove OUR OWN invariants; reported per file below
- autodesk_acceptance: NOT claimed by this run: only the Autodesk Viewer / Revit prove acceptance (upload -> 'translated' -> open the {3D} view). Report both tiers separately, never conflated.
- load_vs_render: every certification behind these shapes is a LOAD pass; created walls carry a SerializedDummy rep (desktop Revit regenerates; the cloud viewer does NOT) and our loaded symbols carry real solids -- RENDER (baked geometry) is the render stream's second gate
- release: Revit 2026 target (the base and the schema are 2026); Revit cannot open a newer file -- confirm the customer's Revit version before promising a .rvt

## CRUD — everything created is editable / deletable
- entrypoint: `python tools/frontdoor.py author --rvt experiments/frontdoor/ifc-electrical-room-2500a/electrical-room-2500a.rvt --edit "<sentence | ops.json | inline JSON>" --out <dir>`
- `W-N` (id 1472996, wall): delete: `delete 1472996`
- `W-W` (id 1472997, wall): delete: `delete 1472997`
- `W-E` (id 1472998, wall): delete: `delete 1472998`
- `W-S` (id 1472999, wall): delete: `delete 1472999`
- `T1` (id 1473000, equipment-instance): move: `move T1 to X,Y,Z ft`; retype: `retype T1 to <symbol id>`; delete: `delete T1 with cascade`
- `MSB` (id 1473001, equipment-instance): move: `move MSB to X,Y,Z ft`; retype: `retype MSB to <symbol id>`; delete: `delete MSB with cascade`
- `DP-1` (id 1473002, equipment-instance): move: `move DP-1 to X,Y,Z ft`; retype: `retype DP-1 to <symbol id>`; delete: `delete DP-1 with cascade`
- `LP-1` (id 1473003, equipment-instance): move: `move LP-1 to X,Y,Z ft`; retype: `retype LP-1 to <symbol id>`; delete: `delete LP-1 with cascade`
- `LP-2` (id 1473004, equipment-instance): move: `move LP-2 to X,Y,Z ft`; retype: `retype LP-2 to <symbol id>`; delete: `delete LP-2 with cascade`
- `DP-2` (id 1473005, equipment-instance): move: `move DP-2 to X,Y,Z ft`; retype: `retype DP-2 to <symbol id>`; delete: `delete DP-2 with cascade`
- `LP-3` (id 1473006, equipment-instance): move: `move LP-3 to X,Y,Z ft`; retype: `retype LP-3 to <symbol id>`; delete: `delete LP-3 with cascade`
- `LP-4` (id 1473007, equipment-instance): move: `move LP-4 to X,Y,Z ft`; retype: `retype LP-4 to <symbol id>`; delete: `delete LP-4 with cascade`
- not available on created instances — **rename / set-mark**: front-door instances are specimen-scaffolded clones with NO instance parameter rows (the tag/PanelName rides on each board's own generated family + type) -- rename = regenerate with a new tag; `rename`/`set-mark` DO work on native instances in a user's file (--rvt route)
- recreate: re-run the same `frontdoor author` command (deterministic for the same inputs) -- outputs are regenerated from the intent
- start_over: the base is untouched; delete the output directory to discard the whole created layer
- circuits: feeder circuits are NOT authored on this base yet (named blocker in the manifest); the resolved circuit plan is in the intent's feederTree.circuitPlan -- rvt.mep add_circuit / a Revit-side add-in consume it
- coverage-matrix cells exercised: electrical_equipment:create, families:create, walls:create

# Deliverable manifest — route `prompt`

**Status:** PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)
**Tool:** tekton frontdoor (rvt.frontdoor) v1.0.0 · 2026-08-09T13:00:18Z

## Target Revit version
- requested: 2026 · output release: 2026 · status: **match**
- Revit 2026 target: certified Revit 2026 genesis base resolved

## Input
- **prompt**: `an electrical room 30 by 20 ft`
- **fallback_parser**: `rules-first deterministic (no external model call, no API key)`

## Base (certified genesis base — never an Autodesk sample)
- file: `/home/user/tekton/plugin/assets/genesis/G_ABPD.rvt` (source: pinned-bundled, sha256 `84173b8960b8cbba…`)
- pinned: True · certified genesis base: True · Autodesk sample: False
- certification: THE COMPOSED GENESIS PROJECT BASE LOADS: G_ABP + the 240-element lawful maxgc deletion set; validator VALID 0 errors, EDIT-FREE, four-registry coherent; the Autodesk viewer opens it as a browsable model (3D view + sheet 'GEN-101 - GEN OVERALL PLAN', not empty, not corrupt)
  - verdict: docs/inbox/genesis-audit.md '***** ORCHESTRATOR VERDICTS #24' (2026-08-04): GENESIS LOADS

## Intent
- project: Electrical Room
- room `Electrical Room`: 4 walls (0 synthesized), 0 doors
- equipment (0): 
- family plans: 
- feeder edges: 0
- intent JSON: `experiments/wall_solids_frontdoor/2026/intent.json`

## Prompt coverage (what the fallback parser understood)
- understood: “30 by 20 ft” → room dimensions
- default: room height: 3.6576 m (12 ft)
- default: wall thickness: 0.2032 m location-line offset (the built wall uses the base wall type's compound structure)
- default: service voltage system: 480Y/277 V

## Primary prompt path — the AI-surface handoff
- scene_brief: `experiments/wall_solids_frontdoor/2026/scene-brief.json`
- handoff: `experiments/wall_solids_frontdoor/2026/HANDOFF.md`
- instructions: `experiments/wall_solids_frontdoor/2026/PROMPT_TO_IFC.md`
- primary_path_note: `an AI surface executes HANDOFF.md/scene-brief.json with Three.js, exports IFC4 (tekton-ifc exporter, our tagging-contract Psets), and the .ifc re-enters via `frontdoor author --ifc` -- the recommended path`

## Build
- degrade mode: **single** — open cell not exercised by this job: walls only (viewer-certified shape: room shell on the genesis base)
- file **combined**: `experiments/wall_solids_frontdoor/2026/WSOLID2026_walls.rvt` (581632 bytes, sha256 `98addb3d76bfa001…`)
- created: 4 walls, 0 equipment instances, 0 loaded families
- self-checks **combined**: validator VALID (0 errors, 1 warnings); registries coherent=True; identity PASS
- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — P0 genesis gate G1 fails (the base carries derived expression that G1 blocks): FAIL — 3,046 Autodesk-derived element(s) in expression-bearing categories. Nothing built on a sample base is a product; ship only from a certified genesis base.

## Honesty
- **PROOF-ONLY, NOT-DELIVERABLE**
- self_checks: rvt.validate (0 errors), four-registry coherence, identity gate -- prove OUR OWN invariants; reported per file below
- autodesk_acceptance: NOT claimed by this run: only the Autodesk Viewer / Revit prove acceptance (upload -> 'translated' -> open the {3D} view). Report both tiers separately, never conflated.
- load_vs_render: created walls carry authored solids: each SWall's seq-103 rep is a six-face GElement B-rep (rvt.render.brep, the W1_gabpd_wall_solid / RSOLID_walls_A_solid recipe -- RENDER-certified as a SHAPE on the composed base); THIS exact output is uncertified until its own viewer batch passes, and every other certification behind these shapes is a LOAD pass; our loaded symbols carry real solids; RVT_WALL_REP=dummy restores the SerializedDummy rep
- release: Revit 2026 target (the base and the schema are 2026); Revit cannot open a newer file -- confirm the customer's Revit version before promising a .rvt (`--target-version N` makes the front door check, and degrade honestly, for you)

## CRUD — everything created is editable / deletable
- entrypoint: `python tools/frontdoor.py author --rvt experiments/wall_solids_frontdoor/2026/WSOLID2026_walls.rvt --edit "<sentence | ops.json | inline JSON>" --out <dir>`
- `W-S` (id 1472525, wall): delete: `delete 1472525`
- `W-E` (id 1472526, wall): delete: `delete 1472526`
- `W-N` (id 1472527, wall): delete: `delete 1472527`
- `W-W` (id 1472528, wall): delete: `delete 1472528`
- recreate: re-run the same `frontdoor author` command (deterministic for the same inputs) -- outputs are regenerated from the intent
- start_over: the base is untouched; delete the output directory to discard the whole created layer
- circuits: feeder circuits are NOT authored on this base yet (named blocker in the manifest); the resolved circuit plan is in the intent's feederTree.circuitPlan -- rvt.mep add_circuit / a Revit-side add-in consume it
- coverage-matrix cells exercised: walls:create

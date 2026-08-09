# Deliverable manifest — route `prompt`

**Status:** PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)
**Tool:** tekton frontdoor (rvt.frontdoor) v1.0.0 · 2026-08-09T13:00:22Z

## Target Revit version
- requested: 2024 · output release: 2024 · status: **match**
- Revit 2024 target: certified Revit 2024 genesis base resolved

## Input
- **prompt**: `an electrical room 30 by 20 ft`
- **fallback_parser**: `rules-first deterministic (no external model call, no API key)`

## Base (certified genesis base — never an Autodesk sample)
- file: `/home/user/tekton/plugin/assets/genesis/G_ABPD_2024.rvt` (source: pinned-bundled, sha256 `e4a40671d8b6c649…`)
- pinned: True · certified genesis base: True · Autodesk sample: False
- certification: 
  - verdict: 

## Intent
- project: Electrical Room
- room `Electrical Room`: 4 walls (0 synthesized), 0 doors
- equipment (0): 
- family plans: 
- feeder edges: 0
- intent JSON: `experiments/wall_solids_frontdoor/2024/intent.json`

## Prompt coverage (what the fallback parser understood)
- understood: “30 by 20 ft” → room dimensions
- default: room height: 3.6576 m (12 ft)
- default: wall thickness: 0.2032 m location-line offset (the built wall uses the base wall type's compound structure)
- default: service voltage system: 480Y/277 V

## Primary prompt path — the AI-surface handoff
- scene_brief: `experiments/wall_solids_frontdoor/2024/scene-brief.json`
- handoff: `experiments/wall_solids_frontdoor/2024/HANDOFF.md`
- instructions: `experiments/wall_solids_frontdoor/2024/PROMPT_TO_IFC.md`
- primary_path_note: `an AI surface executes HANDOFF.md/scene-brief.json with Three.js, exports IFC4 (tekton-ifc exporter, our tagging-contract Psets), and the .ifc re-enters via `frontdoor author --ifc` -- the recommended path`

## Build
- degrade mode: **single** — open cell not exercised by this job: walls only (viewer-certified shape: room shell on the genesis base)
- file **combined**: `experiments/wall_solids_frontdoor/2024/WSOLID2024_walls.rvt` (581632 bytes, sha256 `cdec67b3d79684be…`)
- created: 4 walls, 0 equipment instances, 0 loaded families
- self-checks **combined**: validator VALID (0 errors, 0 warnings); registries coherent=True; identity PASS
- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — P0 genesis gate G1 fails (the base carries derived expression that G1 blocks): FAIL — 3,223 Autodesk-derived element(s) in expression-bearing categories. Nothing built on a sample base is a product; ship only from a certified genesis base.

## Honesty
- **PROOF-ONLY, NOT-DELIVERABLE**
- self_checks: rvt.validate (0 errors), four-registry coherence, identity gate -- prove OUR OWN invariants; reported per file below
- autodesk_acceptance: NOT claimed by this run: only the Autodesk Viewer / Revit prove acceptance (upload -> 'translated' -> open the {3D} view). Report both tiers separately, never conflated.
- load_vs_render: created walls carry authored solids: each SWall's seq-103 rep is a six-face GElement B-rep (rvt.render.brep, the W1_gabpd_wall_solid / RSOLID_walls_A_solid recipe -- RENDER-certified as a SHAPE on the composed base); THIS exact output is uncertified until its own viewer batch passes, and every other certification behind these shapes is a LOAD pass; our loaded symbols carry real solids; RVT_WALL_REP=dummy restores the SerializedDummy rep
- release: Revit 2024 target (the base and the schema are 2024); Revit cannot open a newer file -- confirm the customer's Revit version before promising a .rvt (`--target-version N` makes the front door check, and degrade honestly, for you)

## CRUD — everything created is editable / deletable
- entrypoint: `python tools/frontdoor.py author --rvt experiments/wall_solids_frontdoor/2024/WSOLID2024_walls.rvt --edit "<sentence | ops.json | inline JSON>" --out <dir>`
- `W-S` (id 1472510, wall): delete: `delete 1472510`
- `W-E` (id 1472511, wall): delete: `delete 1472511`
- `W-N` (id 1472512, wall): delete: `delete 1472512`
- `W-W` (id 1472513, wall): delete: `delete 1472513`
- recreate: re-run the same `frontdoor author` command (deterministic for the same inputs) -- outputs are regenerated from the intent
- start_over: the base is untouched; delete the output directory to discard the whole created layer
- circuits: feeder circuits are NOT authored on this base yet (named blocker in the manifest); the resolved circuit plan is in the intent's feederTree.circuitPlan -- rvt.mep add_circuit / a Revit-side add-in consume it
- coverage-matrix cells exercised: walls:create

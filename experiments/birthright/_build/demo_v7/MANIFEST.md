# Deliverable manifest — route `prompt`

**Status:** PROOF-ONLY (self-checks PASS; see honesty.proof_only_stamps + status_gate)
**Tool:** tekton frontdoor (rvt.frontdoor) v1.0.0 · 2026-08-05T14:53:47Z

## Target Revit version
- requested: None · output release: 2026 · status: **unspecified**
- no --target-version given: the output targets the certified default release (Revit 2026). Revit cannot open a newer file -- ask the user's Revit version before promising a .rvt (the tekton-author skill asks first).

## Input
- **prompt**: `an electrical room rated for 250V with 6 panels`
- **fallback_parser**: `rules-first deterministic (no external model call, no API key)`

## Base (certified genesis base — never an Autodesk sample)
- file: `/Users/ck/dev/things/tekton/experiments/genesis/subst_k4/compose/G_ABPD.rvt` (source: pinned-repo, sha256 `84173b8960b8cbba…`)
- pinned: True · certified genesis base: True · Autodesk sample: False
- certification: THE COMPOSED GENESIS PROJECT BASE LOADS: G_ABP + the 240-element lawful maxgc deletion set; validator VALID 0 errors, EDIT-FREE, four-registry coherent; the Autodesk viewer opens it as a browsable model (3D view + sheet 'GEN-101 - GEN OVERALL PLAN', not empty, not corrupt)
  - verdict: docs/inbox/genesis-audit.md '***** ORCHESTRATOR VERDICTS #24' (2026-08-04): GENESIS LOADS

## Intent
- project: Electrical Room
- equipment (6): panelboard×6
- family plans: resolved 6
- feeder edges: 0
- intent JSON: `experiments/birthright/_build/demo_v7/intent.json`

## Prompt coverage (what the fallback parser understood)
- understood: “panels” → equipment
- **ignored words**: 250V
- default: room height: 3.6576 m (12 ft)
- default: wall thickness: 0.2032 m location-line offset (the built wall uses the base wall type's compound structure)
- default: service voltage system: 480Y/277 V
- default: PP-1: 225 A bus (kind default)
- default: PP-1: voltage 480Y/277 V (service system)
- default: PP-1: MLO (main lugs only kind default)
- default: PP-1: 42 spaces (default)
- default: PP-2: 225 A bus (kind default)
- default: PP-2: voltage 480Y/277 V (service system)
- default: PP-2: MLO (main lugs only kind default)
- default: PP-2: 42 spaces (default)
- default: PP-3: 225 A bus (kind default)
- default: PP-3: voltage 480Y/277 V (service system)
- default: PP-3: MLO (main lugs only kind default)
- default: PP-3: 42 spaces (default)
- default: PP-4: 225 A bus (kind default)
- default: PP-4: voltage 480Y/277 V (service system)
- default: PP-4: MLO (main lugs only kind default)
- default: PP-4: 42 spaces (default)
- default: PP-5: 225 A bus (kind default)
- default: PP-5: voltage 480Y/277 V (service system)
- default: PP-5: MLO (main lugs only kind default)
- default: PP-5: 42 spaces (default)
- default: PP-6: 225 A bus (kind default)
- **warning**: a room was named but no dimensions were given: no room shell will be built (equipment only)

## Build
- degrade mode: **single** — no walls+families combination in this intent: loaded families + instances only (viewer-certified shape: family load + placement on the genesis base)
- file **combined**: `experiments/birthright/_build/demo_v7/DEMO_250v_room_v7.rvt` (1216512 bytes, sha256 `63bf7795e74538d1…`)
- family: `Panelboard PP-1 480Y/277 225A MLO 42sp` (PP-1; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Panelboard PP-2 480Y/277 225A MLO 42sp` (PP-2; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Panelboard PP-3 480Y/277 225A MLO 42sp` (PP-3; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Panelboard PP-4 480Y/277 225A MLO 42sp` (PP-4; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Panelboard PP-5 480Y/277 225A MLO 42sp` (PP-5; eaton/pow-r-line-panelboards PRL2X; ok=True)
- family: `Panelboard PP-6 480Y/277 225A MLO 42sp` (PP-6; eaton/pow-r-line-panelboards PRL2X; ok=True)
- created: 0 walls, 6 equipment instances, 6 loaded families
- self-checks **combined**: validator VALID (0 errors, 1 warnings); registries coherent=True; identity PASS
- deliverability (P0 gate): PROOF-ONLY, NOT-DELIVERABLE — P0 genesis gate G1 fails (the base carries derived expression that G1 blocks): FAIL — 3,054 Autodesk-derived element(s) in expression-bearing categories. Nothing built on a sample base is a product; ship only from a certified genesis base.

## Honesty
- **PROOF-ONLY, NOT-DELIVERABLE**
- self_checks: rvt.validate (0 errors), four-registry coherence, identity gate -- prove OUR OWN invariants; reported per file below
- autodesk_acceptance: NOT claimed by this run: only the Autodesk Viewer / Revit prove acceptance (upload -> 'translated' -> open the {3D} view). Report both tiers separately, never conflated.
- load_vs_render: every certification behind these shapes is a LOAD pass; created walls carry a SerializedDummy rep (desktop Revit regenerates; the cloud viewer does NOT) and our loaded symbols carry real solids -- RENDER (baked geometry) is the render stream's second gate
- release: Revit 2026 target (the base and the schema are 2026); Revit cannot open a newer file -- confirm the customer's Revit version before promising a .rvt (`--target-version N` makes the front door check, and degrade honestly, for you)

## CRUD — everything created is editable / deletable
- entrypoint: `python tools/frontdoor.py author --rvt experiments/birthright/_build/demo_v7/DEMO_250v_room_v7.rvt --edit "<sentence | ops.json | inline JSON>" --out <dir>`
- `PP-1` (id 1482977, equipment-instance): move: `move PP-1 to X,Y,Z ft`; retype: `retype PP-1 to <symbol id>`; delete: `delete PP-1 with cascade`
- `PP-2` (id 1482978, equipment-instance): move: `move PP-2 to X,Y,Z ft`; retype: `retype PP-2 to <symbol id>`; delete: `delete PP-2 with cascade`
- `PP-3` (id 1482979, equipment-instance): move: `move PP-3 to X,Y,Z ft`; retype: `retype PP-3 to <symbol id>`; delete: `delete PP-3 with cascade`
- `PP-4` (id 1482980, equipment-instance): move: `move PP-4 to X,Y,Z ft`; retype: `retype PP-4 to <symbol id>`; delete: `delete PP-4 with cascade`
- `PP-5` (id 1482981, equipment-instance): move: `move PP-5 to X,Y,Z ft`; retype: `retype PP-5 to <symbol id>`; delete: `delete PP-5 with cascade`
- `PP-6` (id 1482982, equipment-instance): move: `move PP-6 to X,Y,Z ft`; retype: `retype PP-6 to <symbol id>`; delete: `delete PP-6 with cascade`
- not available on created instances — **rename / set-mark**: front-door instances are specimen-scaffolded clones with NO instance parameter rows (the tag/PanelName rides on each board's own generated family + type) -- rename = regenerate with a new tag; `rename`/`set-mark` DO work on native instances in a user's file (--rvt route)
- recreate: re-run the same `frontdoor author` command (deterministic for the same inputs) -- outputs are regenerated from the intent
- start_over: the base is untouched; delete the output directory to discard the whole created layer
- circuits: feeder circuits are NOT authored on this base yet (named blocker in the manifest); the resolved circuit plan is in the intent's feederTree.circuitPlan -- rvt.mep add_circuit / a Revit-side add-in consume it
- coverage-matrix cells exercised: electrical_equipment:create, families:create

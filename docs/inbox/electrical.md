# RECORD — electrical calc engine stream (2026-08-03)

Territory: `src/rvt/electrical/*`, `tools/panel_schedule.py`,
`tests/test_electrical.py`, `usecases/chicago-plenum-electrical-room/
electrical-job.json` + `schedules/`, `docs/electrical-calcs.md`, this file.
DONE = engine + tests + the room's schedules rendered — MET.

## What was built

- `src/rvt/electrical/` — stdlib-only design-aid engine:
  - `models.py` — `VoltageSystem` (parses '480Y/277', '208Y/120', '240/120',
    '480' into V_LL/V_LN/phases/wires), `Load` (VA|kVA|amps, phases 1|3,
    poles 1|2|3, class lighting|receptacle|motor|hvac|xfmr|misc, continuous,
    optional fixed slot `number`, optional `tag` = equipment element it feeds),
    `Panel` (system, MCB|MLO, mains/bus A, spaces, minBranchBreaker),
    `Circuit`, `Transformer`.
  - `calcs.py` — line current (1-pole VA/V_LN, 2-pole VA/V_LL, 3-ph
    VA/(V_LL·√3)); continuous ×125%; NEC 240.6(A) standard OCPD ladder;
    Cu 75 °C ampacity table (310.16 + 240.4(D)); transformer FLA/primary OCPD
    (FLA×125% → next std); demand factors (lighting 100%, receptacles first
    10 kVA @100% then 50% [220.44], motors +25% of largest [430.24], others
    100%); panel amps; slot/phase geometry.
  - `schedule.py` — `build_panel_schedule(Panel)`: fixed slots first, then
    greedy largest-first placement choosing the free start slot that
    minimises max−min per-phase VA (2-pole → AB/BC/CA pairs, 3-pole across
    ABC), per-circuit breaker/wire, class VA, connected/demand kVA & amps,
    largest motor, continuous VA, warnings (OVER CAPACITY vs bus, OVER MAINS
    vs MCB, poles>spaces, NO SPACE, imbalance>20% when ≥15 kVA);
    `calc_transformer` (primary/secondary FLA + OCPDs, loading% vs the fed
    panel's demand kVA, OVERLOADED >100%).
  - `render.py` — printable industry-format HTML panelboard schedule
    (header block, two-column odd|even table with a phase column and VA per
    row, footer with per-phase VA/amps, load-class summary, warnings, design-aid
    disclaimer, EXAMPLE banner), CSV, and `panel_summary`/`transformer_summary`
    dicts with `psets.PanelScheduleCalc` / `psets.TransformerCalc` in the
    room-spec `{value,type}` shape.
  - `job.py` — job JSON → objects → `render_job(job, out)` writes
    `<panel>.html/.csv`, `schedules.html`, `summary.json`.
- `tools/panel_schedule.py --spec job.json --out dir` (prints a per-panel /
  per-transformer summary; exits 0).
- Worked example `usecases/chicago-plenum-electrical-room/electrical-job.json`
  (`example: true`, clearly labelled EXAMPLE, NOT the DDOT schedule): B-HG4
  480Y/277 400 A MCB feeding 3× 45 kVA transformers (fixed ckts 1,2,7 →
  70 A/3P) + 277 V plenum lighting + 480 V EF/UH; B-LR1/B-LQ1/B-SLQ1 208Y/120
  225 A MLO branch panels; the three transformers linked to their panels.
  Rendered to `usecases/chicago-plenum-electrical-room/schedules/`
  (B-HG4/B-LR1/B-LQ1/B-SLQ1 .html+.csv, schedules.html, summary.json).
- `docs/electrical-calcs.md` — every formula, code reference, worked
  numbers, the output→.rvt/IFC mapping, and an explicit "NOT evaluated"
  engineer-review scope.

## Evidence (hand-checked, pinned by tests)

- Spec sanity example: 75 kVA @ 480 V 3-ph → 75000/(480·1.732) = 90.2 A →
  ×1.25 = 112.8 A → next OCPD **125 A** (`test_transformer_75kva...`).
- Chicago 45 kVA xfmrs: primary 54.1 A → 67.7 → **70 A/3P**; secondary
  124.9 A → 156.1 → **175 A**; B-HG4 breakers for the 3 primaries = 70 A/3P.
- B-HG4: connected 163.39 kVA (196.5 A); demand 164.39 kVA = **197.7 A** on a
  400 A bus/MCB → no warnings; phase imbalance 6.6%.
- B-LR1: receptacle connected 12,240 VA → 220.44 demand 10,000+0.5×2,240 =
  **11,120 VA**; panel demand 21.29 kVA = 59.1 A on 225 A; XFMR-LR1 loading
  47%; XFMR-LQ1 25%; XFMR-B-SLQ1 12%.
- 32 tests in `tests/test_electrical.py` (29 test functions, one
  parametrised x4) (formulas, OCPD boundaries, 125%
  rule, min-branch, wire table, all demand rules, phase-balance ≤ naive and
  =0 on equal loads, 2-pole pairs balance to 6000/6000/6000, 3-pole VA/3,
  fixed-slot conflict, panel-full, over-capacity/mains warnings, end-to-end
  job + CLI + committed schedules exist).
- Visual check: B-HG4 and B-LR1 HTML rendered in the preview browser — real
  two-column panelboard schedule with header/footer/warnings/disclaimer.
- Full suite `.venv/bin/python -m pytest tests/ -q --ignore=tests/oracle`:
  see BRANCH STATE for the count.

## How the numbers feed back into what we author

- `summary.json.circuits[]` is emitted in the `spec_to_rvt` circuits schema
  (`panel, load, number, description, rating, poles` + `wire, va, amps,
  slots, phases, equipmentLoad`). Panel→transformer feeders
  (`equipmentLoad: true`, `load` = the transformer element name) can be
  passed straight to `Document.add_circuit(..., rating=70, poles=3)` by
  `tools/spec_to_rvt.py`, so the .rvt's RbsElectricalSystem carries the
  computed protection. Schedule-only branch circuits (`equipmentLoad:
  false`) have no modeled load element — the generator's existing SKIP
  path handles them.
- `psets.PanelScheduleCalc` / `psets.TransformerCalc` mirror the
  `room-spec.json` pset shape so the IFC/hardening generators can merge
  ConnectedLoadKVA / DemandLoadKVA / DemandLoadAmps / PhaseA..C VA /
  imbalance / primary+secondary FLA/OCPD onto each
  IfcElectricDistributionBoard / IfcTransformer.

## Notes / gotchas for the orchestrator

- The plugin bundles `src/rvt/**` and `usecases/**` json; adding
  `src/rvt/electrical/` made `tests/test_plugin_sync.py` fail until
  `tools/sync_plugin.py` ran. I ran it (sanctioned mirror; validation
  passed, zip rebuilt). It also swept in-flight files from PARALLEL streams
  (`hosting.py`, `reduce.py`, `families.py`, `inventory.py`, then
  `validate.py`) — expected; those streams must re-run the sync when they
  finish, and the drift test can flap red at any instant while streams are
  actively writing source.
- 208 V 5 kW unit heater sizes at 24.04 A × 1.25 = 30.05 → 35 A/2P (a hair
  over 30 — honest rule application; an engineer would likely spec 30 A on
  the nameplate heater — exactly the kind of thing the review catches).
- Small panels are inherently phase-lumpy; the imbalance warning is
  suppressed under 15 kVA connected (imbalance % is still reported).

## Proposed next work (not in territory — for the tracker)

- `tools/spec_to_rvt.py`: accept `--electrical-summary summary.json` to
  auto-wire `circuits[]` (equipmentLoad true) and stamp panel/transformer
  psets, closing the loop with no hand-copying.
- `tools/ifc_to_spec.py` / hardening: merge `PanelScheduleCalc` and
  `TransformerCalc` psets into the exported IFC.
- Optional refinements once the engineers ask: voltage-drop check, feeder
  sizing (NEC 220 standard method), motor 430.52 inrush allowance, AIC
  calc, K-factor — each is a bounded addition to `calcs.py`.

## Verification pass (2026-08-03, second session)

Re-verified the delivered stream cold: `tests/test_electrical.py` 32/32
green; hand-check `transformer_primary_ocpd(75, 480, 3)` = 90.2 A ->
112.8 A -> 125 A; `tools/panel_schedule.py --spec electrical-job.json`
re-rendered to a scratch dir and `diff -r` against the committed
`schedules/` was byte-identical (reproducible). Full suite
(`--ignore=tests/oracle`): 259 passed + 1 = the plugin-drift test, whose
only failure was `lib/src/rvt/validate.py` (a PARALLEL stream's in-flight
file, not this stream) — re-ran `tools/sync_plugin.py` (validation
passed, zip rebuilt) and the drift test went green; it can re-flap while
other streams keep writing source. Corrected the test count above
(32 collected, not 34).

BRANCH STATE: electrical calc engine COMPLETE and committed-ready in-tree
(no git branch in this session — working tree at
/Users/ck/dev/things/rev-revit). New: src/rvt/electrical/{__init__,models,
calcs,schedule,render,job}.py, tools/panel_schedule.py,
tests/test_electrical.py (32 pass), usecases/chicago-plenum-electrical-room/
electrical-job.json + schedules/ (4 panels rendered + summary.json),
docs/electrical-calcs.md, docs/inbox/electrical.md; plugin bundle
re-synced via tools/sync_plugin.py. Full suite (--ignore=tests/oracle):
260 passed after sync (259 + plugin-drift; 32/32 for this stream).
DONE met; STOP.

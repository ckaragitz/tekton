# Electrical calc engine — formulas, rules and limits

`src/rvt/electrical/` is a **pure-Python (stdlib-only) design AID** for
electrical / MEP contractors. From a job spec (panels, circuits/loads,
transformers) it computes NEC-style branch-circuit sizing, phase
balancing, connected + demand kVA, transformer full-load currents and
overcurrent protection, and renders the deliverable **panelboard
schedule** (HTML + CSV) plus a `summary.json` the revit-bridge generators
consume.

**Product model — read this first.** Every number here is a *design aid*.
The AI computes; the contractor's two licensed engineers review and stamp.
No Autodesk seat is needed to produce or read any of it. The engine is
deliberately conservative and deliberately simplified — the items in
"What is NOT evaluated" below are exactly the engineer's review scope.

## Run it

```
tools/panel_schedule.py --spec usecases/chicago-plenum-electrical-room/electrical-job.json \
                        --out  usecases/chicago-plenum-electrical-room/schedules/
```

Outputs: `<panel>.html`, `<panel>.csv` per panel, `schedules.html`
(all panels, print-ready), `summary.json`. Library entry points:
`rvt.electrical.job.run(spec, out_dir)`, `build_panel_schedule(Panel)`,
`calc_transformer(Transformer, fed_schedule)`.

## 1. Line current (`calcs.line_current`)

| Load connection | Formula | Example |
|---|---|---|
| 1-pole, line-to-neutral | I = VA / V_LN | 1,440 VA / 120 V = 12.0 A |
| 2-pole, line-to-line (1-ph) | I = VA / V_LL | 5,000 VA / 208 V = 24.0 A |
| 3-pole, three-phase | I = VA / (V_LL × √3) | 10,000 VA / (480 × 1.732) = 12.03 A |

A load may be given as `va`, `kva`, or `amps`; `calcs.load_va` converts
`amps` back to VA at the voltage the load actually sees (1-pole → V_LN,
2-pole → V_LL, 3-ph → V_LL·√3). 277 V lighting on a 480Y/277 panel:
3,600 VA / 277 V = 13.0 A.

## 2. Continuous loads and breaker sizing (`select_breaker`)

- **Continuous** (3 h+) loads: OCPD ≥ 125% of the load (NEC 210.20(A) /
  215.3). `design_amps = I × 1.25`.
- **Transformer primaries** (`loadClass: xfmr`) and **motors**
  (`loadClass: motor`) are always sized at 125% too (NEC 450.3(B)-style
  primary protection; NEC 430.22 motor conductors). The code permits
  *larger* inverse-time breakers on motors for inrush (430.52) — the
  engine's 125% is the conservative floor, flagged for engineer review.
- Then take the **next standard OCPD** (NEC 240.6(A)):
  `15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150,
  175, 200, 225, 250, 300, 350, 400, 450, 500, 600, 700, 800, 1000, …`
- Optional per-panel **minimum branch breaker** (`minBranchBreakerA`,
  a project convention, e.g. 20 A in commercial work; not a code minimum).
- An explicit `breaker` in the job overrides the calc (spares).

Worked: 3,600 VA lighting @ 277 V, continuous → 13.0 A × 1.25 = 16.2 A
→ **20 A**. Exhaust fan FLA 4.8 A (NEC Table 430.250, 3 HP @ 460 V) →
4.8 × 1.25 = 6.0 A → 15 A → with a 20 A branch minimum → **20 A**.

## 3. Transformer primary/secondary (`transformer_primary_ocpd`)

- 3-ph FLA: I = kVA × 1000 / (V × √3); 1-ph: I = kVA × 1000 / V.
- Primary OCPD = FLA × 1.25 → next standard size.
- Secondary OCPD (reported) = secondary FLA × 1.25 → next standard.

**Sanity example from the product spec** (pinned by
`test_transformer_75kva_primary_ocpd_hand_worked`):
75 kVA @ 480 V, 3-ph → 75,000 / (480 × 1.732) = **90.2 A** → × 1.25 =
**112.8 A** → next OCPD **125 A**.

Chicago-room transformers (45 kVA, 480→208Y/120): primary 54.1 A →
67.7 A → **70 A/3P**; secondary 124.9 A → 156.1 → **175 A**.

## 4. Conductors (`select_wire`)

Smallest **copper, 75 °C** conductor (NEC Table 310.16) with ampacity ≥
the OCPD rating, with the 240.4(D) small-conductor caps applied
(14 AWG→15 A, 12 AWG→20 A, 10 AWG→30 A): 12 AWG=20, 10=30, 8=50, 6=65,
4=85, 3=100, 2=115, 1=130, 1/0=150, 2/0=175, 3/0=200, 4/0=230,
250 kcmil=255 … Simplified: no temperature/bundling derating, no voltage
drop, no 240.4(B) next-size-up allowance.

## 5. Phase balancing (`build_panel_schedule`)

Physical panel model: slots number down two columns (odd left, even
right); each **row** sits on one bus phase — row r = (slot−1)//2 →
phase `'ABC'[r mod 3]` (3-ph) or `'AB'[r mod 2]` (1-ph 3-wire). So
slots 1,2→A; 3,4→B; 5,6→C; 7,8→A … A 2-pole breaker on slot 5 occupies
(5, 7) = phases C,A; 3-pole on slot 1 = (1, 3, 5) = A,B,C.

- Circuits with a fixed `number` keep their slots.
- The rest are placed **largest VA first**; for each, every free start
  slot is trialled and the one giving the **minimum per-phase imbalance**
  (max − min of the running phase VA) is chosen (ties → lowest slot).
- VA convention on the schedule: a circuit's VA is split equally over
  the phases it lands on (3-pole = VA/3 per phase; 2-pole = VA/2 on two).
- 2-pole loads therefore land on pairs **AB / BC / CA**; three equal
  2-pole loads balance perfectly (`test_two_pole_lands_on_a_valid_pair_
  and_balances`); equal 1-pole loads balance to 0 imbalance.
- Reported: per-phase VA, `imbalance = max − min`, and
  `imbalance% = (max − min) / average phase`. A warning fires when
  imbalance > 20% **and** connected load ≥ 15 kVA (tiny panels are
  inherently lumpy).

## 6. Demand load (`demand_kva`)

The simple factor set requested for this product:

| Class | Rule | Reference |
|---|---|---|
| lighting | 100% | design-aid simplification |
| receptacle | first 10 kVA @ 100%, remainder @ 50% | NEC 220.44 |
| motor | all motors + 25% of the largest motor | NEC 430.24 |
| hvac / xfmr / misc | 100% | — |

Worked (B-LR1): receptacles connected 12,240 VA → 10,000 + 0.5 × 2,240
= **11,120 VA**. Motors: EF 3,991 VA is the largest → motor demand =
3,991 + 0.25 × 3,991 = 4,988 VA.

## 7. Panel totals and capacity warnings

- `connected_va = Σ circuit VA`; `demand_va` from §6.
- `panel amps = kVA × 1000 / (V_LL × √3)` (3-ph) or `/ V_LL` (1-ph).
- Warnings: demand amps > **bus rating** → *OVER CAPACITY*; > 80% of
  bus → informational; MCB panel and demand amps > mains rating →
  *OVER MAINS*; poles used > spaces; phase imbalance (§5); a panel full
  with unplaced loads → *NO SPACE*.
- Phase amps on the schedule footer = phase VA / V_LN (wye systems).

Chicago-room B-HG4: connected 163.39 kVA → 196.5 A; demand 164.39 kVA
→ **197.7 A** on a 400 A bus/MCB (49%). No warnings.

## 8. Transformer loading

`loading% = fed panel demand kVA / transformer kVA × 100`. > 100% →
*OVERLOADED*; > 80% → limited spare capacity. Chicago room: XFMR-LR1
carries B-LR1's 21.3 kVA demand → **47%**; XFMR-LQ1 25%; XFMR-B-SLQ1 12%.

## 9. Outputs and how they feed the .rvt / IFC

`summary.json` (`kind: rev-revit.electrical-summary`) carries:

- `panels[<name>].psets.PanelScheduleCalc` — ConnectedLoadKVA,
  DemandLoadKVA, DemandLoadAmps, PhaseA/B/CVA, PhaseImbalancePct,
  PolesUsed, in the same `{value, type}` shape as
  `room-spec.json`'s `PanelSchedule` pset, so `ifc_to_spec` / the
  hardening generator can merge them onto each
  `IfcElectricDistributionBoard`.
- `transformers[<name>].psets.TransformerCalc` — PrimaryFLA/OCPD,
  SecondaryFLA/OCPD, DemandLoadingPct → merge onto each `IfcTransformer`.
- `circuits[]` — in the **spec_to_rvt `circuits` schema**
  (`panel`, `load`, `number`, `description`, `rating`, `poles`) plus
  `wire`, `va`, `amps`, `slots`, `phases`, `equipmentLoad`. When both
  ends are authored elements (a panelboard feeding a transformer —
  `equipmentLoad: true`, `load` = the transformer's element name),
  `tools/spec_to_rvt.py` passes `rating`/`poles` straight into
  `Document.add_circuit(...)`, so the .rvt's real `RbsElectricalSystem`
  carries the computed 70 A / 3-pole. Branch circuits with no modeled
  load element (`equipmentLoad: false`, e.g. a lighting run) are the
  schedule-only rows the generator skips.

## What is NOT evaluated (engineer review scope)

Voltage drop; conductor derating (ambient/bundling), neutral sizing,
grounding conductors; short-circuit/interrupting adequacy and series
ratings (AIC is echoed from the spec, not calculated); selective
coordination; feeder sizing per NEC 215/220 optional methods; harmonic
K-factor; motor 430.52 inrush allowances beyond the 125% floor; multiple
services; any jurisdictional amendment. The engine states this on every
rendered page (`render.DISCLAIMER`).

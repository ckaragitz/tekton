"""Tests for the electrical calc engine (src/rvt/electrical).

Numbers are hand-checked (sanity tests double as the worked-formula
documentation in docs/electrical-calcs.md). This is a DESIGN AID: the
tests pin the arithmetic; a licensed engineer reviews the outputs.
"""
import json
import math
import os
import subprocess
import sys

import pytest

from rvt.electrical import (
    Load, Panel, Transformer, VoltageSystem, build_panel_schedule,
    calc_transformer, calcs,
)
from rvt.electrical import job as ejob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOB = os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room",
                   "electrical-job.json")
SCHED = os.path.join(ROOT, "usecases", "chicago-plenum-electrical-room",
                     "schedules")
SQRT3 = math.sqrt(3.0)


# ------------------------------------------------------------ transformer
def test_transformer_75kva_primary_ocpd_hand_worked():
    """The spec's sanity example: 75 kVA, 480 V, 3-ph.
    I = 75000 / (480 * sqrt3) = 90.2 A -> x125 = 112.8 A -> next OCPD 125 A.
    """
    fla, x125, ocpd = calcs.transformer_primary_ocpd(75, 480, 3)
    assert round(fla, 1) == 90.2
    assert round(x125, 1) == 112.8
    assert ocpd == 125


def test_transformer_45kva_primary_and_secondary():
    fla, x125, ocpd = calcs.transformer_primary_ocpd(45, 480, 3)
    assert round(fla, 1) == 54.1          # 45000/(480*1.732)
    assert round(x125, 1) == 67.7
    assert ocpd == 70
    sec = calcs.transformer_current(45, 208, 3)
    assert round(sec, 1) == 124.9          # 45000/(208*1.732)
    assert calcs.next_standard_ocpd(sec * 1.25) == 175   # 156.1 -> 175


def test_transformer_single_phase_current():
    assert calcs.transformer_current(25, 240, 1) == pytest.approx(104.17, rel=1e-3)


def test_calc_transformer_loading_and_warning():
    p = Panel(name="P", system=VoltageSystem.parse("208Y/120"),
              bus_rating=225, mains_rating=225,
              loads=[Load("big", kva=40, phases=3, load_class="misc")])
    sched = build_panel_schedule(p)
    t = Transformer(name="T", kva=30, primary_v=480, secondary_v=208,
                    feeds="P")
    tc = calc_transformer(t, sched)
    assert tc.fed_panel == "P"
    assert tc.loading_pct == pytest.approx(40 / 30 * 100)
    assert any("OVERLOADED" in w for w in tc.warnings)


# --------------------------------------------------------------- currents
def test_line_current_forms():
    s = VoltageSystem.parse("208Y/120")
    assert calcs.line_current(1440, s.v_ll, s.v_ln, poles=1, phases=1) == 12.0
    assert calcs.line_current(5000, s.v_ll, s.v_ln, poles=2, phases=1) == \
        pytest.approx(24.04, rel=1e-3)
    hi = VoltageSystem.parse("480Y/277")
    assert calcs.line_current(10000, hi.v_ll, hi.v_ln, poles=3, phases=3) == \
        pytest.approx(10000 / (480 * SQRT3))
    # 277 V lighting on a 1-pole
    assert calcs.line_current(3600, hi.v_ll, hi.v_ln, 1, 1) == \
        pytest.approx(13.0, rel=1e-3)


def test_load_va_from_amps_and_kva():
    s = VoltageSystem.parse("208Y/120")
    assert calcs.load_va(Load("a", amps=9.8), s) == pytest.approx(9.8 * 120)
    assert calcs.load_va(Load("k", kva=3, poles=2), s) == 3000.0
    hi = VoltageSystem.parse("480Y/277")
    assert calcs.load_va(Load("m", amps=4.8, phases=3), hi) == \
        pytest.approx(4.8 * 480 * SQRT3)


# ------------------------------------------------------------------ OCPD
def test_next_standard_ocpd_boundaries():
    assert calcs.next_standard_ocpd(12.4) == 15
    assert calcs.next_standard_ocpd(15) == 15
    assert calcs.next_standard_ocpd(15.1) == 20
    assert calcs.next_standard_ocpd(100.001) == 110
    assert calcs.next_standard_ocpd(112.8) == 125
    assert calcs.next_standard_ocpd(1201) == 1600


def test_continuous_125_percent_rule():
    b, note = calcs.select_breaker(13.0, continuous=True)   # 16.25 -> 20
    assert b == 20 and "125%" in note
    b2, _ = calcs.select_breaker(13.0, continuous=False)     # 13 -> 15
    assert b2 == 15
    # exactly 16 A continuous -> 20 A
    assert calcs.select_breaker(16.0, True)[0] == 20


def test_min_branch_breaker_convention():
    assert calcs.select_breaker(6.0, False)[0] == 15
    b, note = calcs.select_breaker(6.0, False, min_rating=20)
    assert b == 20 and "min branch" in note


def test_select_wire_table():
    assert calcs.select_wire(15) == "14 AWG"
    assert calcs.select_wire(20) == "12 AWG"
    assert calcs.select_wire(30) == "10 AWG"
    assert calcs.select_wire(70) == "4 AWG"
    assert calcs.select_wire(125) == "1 AWG"
    assert calcs.select_wire(175) == "2/0 AWG"
    assert calcs.select_wire(200) == "3/0 AWG"
    assert calcs.select_wire(10_000).startswith("(exceeds")


# ---------------------------------------------------------------- demand
def test_demand_receptacle_first_10kva_rule():
    total, per = calcs.demand_kva({"receptacle": 12240})
    assert per["receptacle"] == pytest.approx(10000 + 0.5 * 2240)   # 11120
    assert total == per["receptacle"]
    # under 10 kVA -> 100%
    assert calcs.demand_kva({"receptacle": 8000})[0] == 8000


def test_demand_motor_largest_plus_25pct():
    total, per = calcs.demand_kva({"motor": 5000}, largest_motor_va=3000)
    assert per["motor"] == pytest.approx(5000 + 0.25 * 3000)


def test_demand_lighting_and_others_100pct():
    total, per = calcs.demand_kva({"lighting": 14400, "hvac": 10000,
                                   "xfmr": 135000, "misc": 1234})
    assert per["lighting"] == 14400 and per["hvac"] == 10000
    assert per["xfmr"] == 135000 and per["misc"] == 1234
    assert total == 14400 + 10000 + 135000 + 1234


def test_panel_amps_three_and_single_phase():
    hi = VoltageSystem.parse("480Y/277")
    assert calcs.panel_amps(164.388, hi) == pytest.approx(
        164388 / (480 * SQRT3))
    one = VoltageSystem.parse("240/120")
    assert calcs.panel_amps(24, one) == pytest.approx(100.0)


# --------------------------------------------------------------- phasing
def test_slot_phase_pattern_two_columns_three_rows():
    ph = [calcs.slot_phase(s) for s in range(1, 13)]
    assert ph == ["A", "A", "B", "B", "C", "C", "A", "A", "B", "B", "C", "C"]
    assert calcs.circuit_slots(5, 2) == (5, 7)      # 2-pole same column
    assert calcs.circuit_slots(1, 3) == (1, 3, 5)


def test_phase_va_split_conventions():
    assert calcs.phase_va_split(15000, ("A", "B", "C")) == \
        {"A": 5000, "B": 5000, "C": 5000}
    assert calcs.phase_va_split(5000, ("A", "B")) == \
        {"A": 2500, "B": 2500, "C": 0.0}


def _naive_imbalance(vas, panel_va_split=True):
    """Assign 1-pole loads to slots 1,2,3,... in given order (no balancing)."""
    ph = {"A": 0.0, "B": 0.0, "C": 0.0}
    for i, va in enumerate(vas, 1):
        ph[calcs.slot_phase(i)] += va
    return calcs.imbalance(ph)


def test_phase_balancing_minimises_vs_naive():
    """Greedy balancing must never be worse than naive slot-order filling,
    and lands equal loads perfectly."""
    vas = [1440] * 6
    p = Panel(name="P", system=VoltageSystem.parse("208Y/120"), spaces=42,
              loads=[Load(f"r{i}", va=v, load_class="receptacle")
                     for i, v in enumerate(vas)])
    s = build_panel_schedule(p)
    assert s.imbalance_va == 0
    # a lumpy set: greedy <= naive
    lumpy = [3600, 3600, 3600, 1200, 800, 500, 5000]
    p2 = Panel(name="Q", system=VoltageSystem.parse("208Y/120"), spaces=42,
               loads=[Load(f"l{i}", va=v) for i, v in enumerate(lumpy)])
    s2 = build_panel_schedule(p2)
    assert s2.imbalance_va <= _naive_imbalance(lumpy) + 1e-9


def test_two_pole_lands_on_a_valid_pair_and_balances():
    """Three equal 2-pole loads should end up on distinct pairs AB/BC/CA
    => perfectly balanced per-phase."""
    p = Panel(name="P", system=VoltageSystem.parse("208Y/120"), spaces=42,
              loads=[Load(f"h{i}", va=6000, poles=2, load_class="hvac")
                     for i in range(3)])
    s = build_panel_schedule(p)
    pairs = {frozenset(c.phases_used) for c in s.circuits}
    valid = {frozenset(("A", "B")), frozenset(("B", "C")),
             frozenset(("C", "A"))}
    assert pairs <= valid
    assert s.phase_va == {"A": 6000, "B": 6000, "C": 6000}
    for c in s.circuits:
        assert c.poles == 2


def test_three_pole_load_across_abc():
    p = Panel(name="P", system=VoltageSystem.parse("480Y/277"), spaces=42,
              loads=[Load("x", kva=45, phases=3, load_class="xfmr")])
    s = build_panel_schedule(p)
    c = s.circuits[0]
    assert c.poles == 3 and set(c.phases_used) == {"A", "B", "C"}
    assert s.phase_va == {"A": 15000, "B": 15000, "C": 15000}
    # xfmr class always sized at 125%: 54.1 A -> 70 A
    assert c.breaker == 70


def test_fixed_circuit_number_kept_and_conflict_flagged():
    p = Panel(name="P", system=VoltageSystem.parse("208Y/120"), spaces=42,
              loads=[Load("a", va=1000, number=7),
                     Load("b", va=1000, number=7)])   # collides with 'a'
    s = build_panel_schedule(p)
    assert s.circuit(7) is not None
    assert any("cannot occupy" in w for w in s.warnings)


def test_panel_full_no_space_warning():
    p = Panel(name="P", system=VoltageSystem.parse("208Y/120"), spaces=4,
              loads=[Load(f"a{i}", va=500) for i in range(6)])
    s = build_panel_schedule(p)
    assert any("NO SPACE" in w for w in s.warnings)
    assert s.poles_used == 4


def test_over_capacity_warning():
    p = Panel(name="P", system=VoltageSystem.parse("208Y/120"),
              bus_rating=100, mains_rating=100, mains_type="MCB", spaces=42,
              loads=[Load("big", kva=50, phases=3, load_class="misc")])
    s = build_panel_schedule(p)
    assert s.demand_amps > 100
    assert any("OVER CAPACITY" in w for w in s.warnings)
    assert any("OVER MAINS" in w for w in s.warnings)


def test_receptacle_demand_flows_into_panel_totals():
    loads = [Load(f"r{i}", va=1440, load_class="receptacle")
             for i in range(8)] + [Load("elec rm", va=720,
                                        load_class="receptacle")]
    p = Panel(name="P", system=VoltageSystem.parse("208Y/120"), loads=loads)
    s = build_panel_schedule(p)
    assert s.class_va["receptacle"] == pytest.approx(12240)
    assert s.class_demand_va["receptacle"] == pytest.approx(11120)
    assert s.connected_va == pytest.approx(12240)
    assert s.demand_va == pytest.approx(11120)
    assert s.demand_amps == pytest.approx(11.12 * 1000 / (208 * SQRT3))


def test_motor_sizing_and_largest_tracking():
    hi = VoltageSystem.parse("480Y/277")
    p = Panel(name="P", system=hi,
              loads=[Load("ef", amps=4.8, phases=3, load_class="motor"),
                     Load("bigger", amps=10, phases=3, load_class="motor")])
    s = build_panel_schedule(p)
    ef = next(c for c in s.circuits if c.load.description == "ef")
    assert ef.breaker == 15          # 4.8 x 1.25 = 6.0 -> 15
    assert s.largest_motor_va == pytest.approx(10 * 480 * SQRT3)
    total, per = calcs.demand_kva(s.class_va, s.largest_motor_va)
    assert per["motor"] == pytest.approx(s.class_va["motor"]
                                          + 0.25 * s.largest_motor_va)


# --------------------------------------------------------- voltage systems
@pytest.mark.parametrize("txt,ll,ln,ph,w", [
    ("480Y/277", 480, 277, 3, 4),
    ("208Y/120", 208, 120, 3, 4),
    ("240/120", 240, 120, 1, 3),
    ("480", 480, 277.1, 3, 3),
])
def test_voltage_system_parse(txt, ll, ln, ph, w):
    s = VoltageSystem.parse(txt)
    assert (s.v_ll, s.phases, s.wires) == (ll, ph, w)
    assert s.v_ln == pytest.approx(ln, abs=0.1)


def test_load_validation():
    with pytest.raises(ValueError):
        Load("bad", va=1, load_class="nope")
    with pytest.raises(ValueError):
        Load("bad", va=1, phases=3, poles=2)


# ---------------------------------------------- the Chicago worked example
def test_chicago_job_end_to_end(tmp_path):
    summ = ejob.run(JOB, str(tmp_path))
    # files
    for n in ("B-HG4", "B-LR1", "B-LQ1", "B-SLQ1"):
        assert (tmp_path / f"{n}.html").exists()
        assert (tmp_path / f"{n}.csv").exists()
    assert (tmp_path / "schedules.html").exists()
    assert (tmp_path / "summary.json").exists()
    # B-HG4: three 45 kVA transformer primaries at 70 A / 3P
    hg4 = summ["panels"]["B-HG4"]
    prims = [c for c in hg4["circuits"] if c["equipmentLoad"]]
    assert sorted(c["load"] for c in prims) == \
        ["XFMR-B-SLQ1", "XFMR-LQ1", "XFMR-LR1"]
    assert all(c["rating"] == 70 and c["poles"] == 3 for c in prims)
    # transformer report matches the panel breakers
    for name in ("XFMR-LR1", "XFMR-LQ1", "XFMR-B-SLQ1"):
        t = summ["transformers"][name]
        assert t["primaryOCPD"] == 70
        assert round(t["primaryFLA"], 1) == 54.1
        assert t["secondaryOCPD"] == 175
        assert t["fedPanel"] is not None and t["loadingPct"] is not None
    # B-LR1 exercises the 220.44 receptacle rule (12,240 VA -> 11,120)
    lr1 = summ["panels"]["B-LR1"]
    assert lr1["classConnectedVA"]["receptacle"] == pytest.approx(12240)
    assert lr1["classDemandVA"]["receptacle"] == pytest.approx(11120)
    # nothing over capacity in the example; example flag carried through
    assert summ["example"] is True
    for p in summ["panels"].values():
        assert not any("OVER CAPACITY" in w for w in p["warnings"])
    html = (tmp_path / "B-HG4.html").read_text()
    assert "PANELBOARD SCHEDULE" in html and "EXAMPLE" in html
    assert "DESIGN AID" in html


def test_committed_room_schedules_exist():
    """DONE criterion: the room's schedules are rendered into the repo."""
    for f in ("summary.json", "schedules.html", "B-HG4.html", "B-HG4.csv",
              "B-LR1.html", "B-LQ1.html", "B-SLQ1.html"):
        assert os.path.exists(os.path.join(SCHED, f)), f
    summ = json.load(open(os.path.join(SCHED, "summary.json")))
    assert summ["kind"] == "tekton.electrical-summary"
    assert summ["transformers"]["XFMR-LR1"]["primaryOCPD"] == 70


def test_cli_tool_runs(tmp_path):
    tool = os.path.join(ROOT, "tools", "panel_schedule.py")
    r = subprocess.run([sys.executable, tool, "--spec", JOB, "--out",
                        str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert "B-HG4" in r.stdout and "XFMR-LR1" in r.stdout
    assert (tmp_path / "summary.json").exists()

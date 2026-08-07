"""Panel schedule construction: slot assignment, phase balancing, per-circuit
breaker/wire selection, per-phase totals, connected/demand kVA and
capacity warnings.

The output :class:`PanelSchedule` is the single source of truth for
every renderer (HTML / CSV / summary JSON) and for feeding computed
values back into the .rvt (add_circuit rating/poles) and IFC psets.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from . import calcs
from .models import Circuit, Load, Panel, Transformer


@dataclass
class PanelSchedule:
    panel: Panel
    circuits: list                 # list[Circuit], sorted by number
    slot_map: dict                 # {slot:int -> Circuit | None}
    phase_va: dict                 # {'A','B','C'} connected VA per phase
    class_va: dict                 # connected VA per load class
    connected_va: float
    demand_va: float
    class_demand_va: dict
    largest_motor_va: float
    continuous_va: float
    connected_amps: float
    demand_amps: float
    poles_used: int
    imbalance_va: float
    imbalance_pct: float
    warnings: list = field(default_factory=list)

    # ---- convenience -----------------------------------------------
    @property
    def connected_kva(self) -> float:
        return self.connected_va / 1000.0

    @property
    def demand_kva(self) -> float:
        return self.demand_va / 1000.0

    def circuit(self, number: int) -> Optional[Circuit]:
        for c in self.circuits:
            if c.number == number:
                return c
        return None


# ------------------------------------------------------------------ build
def _free_starts(occupied: set, spaces: int, poles: int) -> list:
    """Slot numbers where a ``poles``-pole breaker fits (same column)."""
    starts = []
    for s in range(1, spaces + 1):
        slots = calcs.circuit_slots(s, poles)
        if slots[-1] > spaces:
            continue
        if any(x in occupied for x in slots):
            continue
        starts.append(s)
    return starts


def _phases_for(slots: tuple, bus_phases: int) -> tuple:
    seen = []
    for s in slots:
        p = calcs.slot_phase(s, bus_phases)
        if p not in seen:
            seen.append(p)
    return tuple(seen)


def _size_circuit(load: Load, va: float, system,
                  min_breaker: float = 0.0) -> tuple:
    """Return (amps, breaker, wire, note) for one load on this panel."""
    amps = calcs.line_current(va, system.v_ll, system.v_ln, load.poles,
                              load.phases)
    # transformers and motors are sized at 125% like continuous loads
    continuous = bool(load.continuous or load.load_class in ("xfmr", "motor"))
    if load.breaker is not None:
        breaker = float(load.breaker)
        note = f"{amps:.1f} A; breaker assigned {breaker:g} A"
    else:
        breaker, note = calcs.select_breaker(amps, continuous, min_breaker)
    wire = load.wire or calcs.select_wire(breaker)
    return amps, breaker, wire, note


def build_panel_schedule(panel: Panel) -> PanelSchedule:
    """Assign every load to slots (phase-balanced), size breakers/wires and
    compute totals + warnings."""
    sys = panel.system
    bus_phases = 3 if sys.phases == 3 else 1
    occupied: set = set()
    phase_va = {"A": 0.0, "B": 0.0, "C": 0.0}
    circuits: list = []
    warnings: list = []

    loads = list(panel.loads)
    fixed = [ld for ld in loads if ld.number is not None]
    free = [ld for ld in loads if ld.number is None]
    # greedy phase balancing works best largest-first
    free.sort(key=lambda ld: -calcs.load_va(ld, sys))

    def place(ld: Load, start: int) -> None:
        va = calcs.load_va(ld, sys)
        slots = calcs.circuit_slots(start, ld.poles)
        ph = _phases_for(slots, bus_phases)
        occupied.update(slots)
        split = calcs.phase_va_split(va, ph)
        for p, v in split.items():
            phase_va[p] += v
        amps, breaker, wire, note = _size_circuit(ld, va, sys,
                                                   panel.min_branch_breaker)
        circuits.append(Circuit(number=start, slots=slots, phases_used=ph,
                                load=ld, va=va, amps=amps, breaker=breaker,
                                wire=wire, va_by_phase=split,
                                breaker_note=note))

    # 1) fixed-number circuits keep their slots
    for ld in sorted(fixed, key=lambda l: l.number):
        slots = calcs.circuit_slots(int(ld.number), ld.poles)
        if slots[-1] > panel.spaces or any(s in occupied for s in slots):
            warnings.append(f"circuit '{ld.description}' cannot occupy slots "
                            f"{slots} (out of range or occupied)")
            continue
        place(ld, int(ld.number))

    # 2) balance the rest: choose the free position minimising imbalance
    for ld in free:
        va = calcs.load_va(ld, sys)
        starts = _free_starts(occupied, panel.spaces, ld.poles)
        if not starts:
            warnings.append(f"NO SPACE for '{ld.description}' "
                            f"({ld.poles}P) — panel is full")
            continue
        best = None
        for s in starts:
            ph = _phases_for(calcs.circuit_slots(s, ld.poles), bus_phases)
            trial = dict(phase_va)
            for p, v in calcs.phase_va_split(va, ph).items():
                trial[p] += v
            score = calcs.imbalance(trial, bus_phases)
            if best is None or score < best[0] - 1e-9:
                best = (score, s)
        place(ld, best[1])

    circuits.sort(key=lambda c: c.number)
    slot_map = {s: None for s in range(1, panel.spaces + 1)}
    for c in circuits:
        for s in c.slots:
            slot_map[s] = c

    # ---- totals ----------------------------------------------------
    class_va: dict = {}
    largest_motor = 0.0
    continuous_va = 0.0
    for c in circuits:
        cls = c.load.load_class
        class_va[cls] = class_va.get(cls, 0.0) + c.va
        if cls == "motor":
            largest_motor = max(largest_motor, c.va)
        if c.load.continuous:
            continuous_va += c.va
    connected_va = sum(class_va.values())
    demand_va, class_demand = calcs.demand_kva(class_va, largest_motor)
    connected_amps = calcs.panel_amps(connected_va / 1000.0, sys)
    demand_amps = calcs.panel_amps(demand_va / 1000.0, sys)
    poles_used = len(occupied)
    imb = calcs.imbalance(phase_va, bus_phases)
    imb_pct = calcs.imbalance_pct(phase_va, bus_phases)

    # ---- warnings --------------------------------------------------
    if demand_amps > panel.bus_rating:
        warnings.append(f"OVER CAPACITY: demand {demand_amps:.1f} A exceeds "
                        f"bus rating {panel.bus_rating:g} A")
    elif demand_amps > 0.8 * panel.bus_rating:
        warnings.append(f"demand {demand_amps:.1f} A is above 80% of the "
                        f"{panel.bus_rating:g} A bus (little spare capacity)")
    if panel.mains_type.upper() in ("MCB", "MAIN BREAKER") and \
            demand_amps > panel.mains_rating:
        warnings.append(f"OVER MAINS: demand {demand_amps:.1f} A exceeds main "
                        f"breaker {panel.mains_rating:g} A")
    if poles_used > panel.spaces:
        warnings.append(f"{poles_used} poles used exceeds {panel.spaces} spaces")
    # imbalance only matters once there is real load to balance
    if bus_phases == 3 and imb_pct > 20.0 and connected_va >= 15000.0:
        warnings.append(f"phase imbalance {imb_pct:.0f}% (>20% at "
                        f"{connected_va/1000:.1f} kVA) — rebalance "
                        f"single-pole circuits")

    return PanelSchedule(panel=panel, circuits=circuits, slot_map=slot_map,
                         phase_va=phase_va, class_va=class_va,
                         connected_va=connected_va, demand_va=demand_va,
                         class_demand_va=class_demand,
                         largest_motor_va=largest_motor,
                         continuous_va=continuous_va,
                         connected_amps=connected_amps, demand_amps=demand_amps,
                         poles_used=poles_used, imbalance_va=imb,
                         imbalance_pct=imb_pct, warnings=warnings)


# ------------------------------------------------------------ transformer
@dataclass
class TransformerCalc:
    transformer: Transformer
    primary_fla: float
    primary_x125: float
    primary_ocpd: int
    secondary_fla: float
    secondary_ocpd: int
    fed_panel: Optional[str] = None
    fed_connected_kva: Optional[float] = None
    fed_demand_kva: Optional[float] = None
    loading_pct: Optional[float] = None
    warnings: list = field(default_factory=list)


def calc_transformer(t: Transformer,
                     fed_schedule: Optional[PanelSchedule] = None
                     ) -> TransformerCalc:
    """Primary/secondary currents and OCPDs; loading % vs the fed panel."""
    pfla, px125, pocpd = calcs.transformer_primary_ocpd(t.kva, t.primary_v,
                                                        t.phases)
    sfla = calcs.transformer_current(t.kva, t.secondary_v, t.phases)
    socpd = calcs.next_standard_ocpd(sfla * 1.25)
    tc = TransformerCalc(transformer=t, primary_fla=pfla, primary_x125=px125,
                         primary_ocpd=pocpd, secondary_fla=sfla,
                         secondary_ocpd=socpd)
    if fed_schedule is not None:
        tc.fed_panel = fed_schedule.panel.name
        tc.fed_connected_kva = fed_schedule.connected_kva
        tc.fed_demand_kva = fed_schedule.demand_kva
        tc.loading_pct = (fed_schedule.demand_kva / t.kva * 100.0
                          if t.kva else None)
        if tc.loading_pct is not None:
            if tc.loading_pct > 100.0:
                tc.warnings.append(f"OVERLOADED: demand load "
                                   f"{fed_schedule.demand_kva:.1f} kVA is "
                                   f"{tc.loading_pct:.0f}% of {t.kva:g} kVA")
            elif tc.loading_pct > 80.0:
                tc.warnings.append(f"loading {tc.loading_pct:.0f}% (>80%) — "
                                   f"limited spare capacity")
    return tc

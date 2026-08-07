"""NEC-style electrical calculations (design AID — engineer reviews).

Every formula is documented in ``docs/electrical-calcs.md``. Summary of
the rules coded here (simplified, US National Electrical Code flavour):

* Line current
    - 1-pole 1-phase load on line-to-neutral:      I = VA / V_LN
    - 2-pole 1-phase load on line-to-line:         I = VA / V_LL
    - 3-phase load:                                I = VA / (V_LL * sqrt(3))
* Continuous loads: OCPD sized at 125% (NEC 210.20(A) / 215.3).
* Motors: OCPD/conductor sized here at 125% of FLA (NEC 430.22/430.24 —
  conservative; the code permits larger inverse-time breakers for inrush).
* Transformer primary OCPD: 125% of primary FLA, next standard size
  (NEC 450.3(B) style primary-only protection).
* Standard OCPD ratings: NEC 240.6(A).
* Demand factors (simple set requested by the product spec):
    lighting 100%; receptacles 100% of the first 10 kVA then 50%
    (NEC 220.44); motors: all at 100% plus 25% of the largest (NEC 430.24);
    hvac / xfmr / misc 100%.
"""
from __future__ import annotations

import math
from typing import Iterable, Optional

SQRT3 = math.sqrt(3.0)

# NEC 240.6(A) standard ampere ratings for fuses / inverse-time breakers.
STANDARD_OCPD = (
    15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 110, 125, 150,
    175, 200, 225, 250, 300, 350, 400, 450, 500, 600, 700, 800, 1000,
    1200, 1600, 2000, 2500, 3000, 4000, 5000, 6000,
)

# Copper conductor ampacity, 75 degC column of NEC Table 310.16, with
# the small-conductor OCPD caps of 240.4(D) applied (14->15, 12->20,
# 10->30). Ordered smallest to largest.
CU_AMPACITY_75C = (
    ("14 AWG", 15), ("12 AWG", 20), ("10 AWG", 30), ("8 AWG", 50),
    ("6 AWG", 65), ("4 AWG", 85), ("3 AWG", 100), ("2 AWG", 115),
    ("1 AWG", 130), ("1/0 AWG", 150), ("2/0 AWG", 175), ("3/0 AWG", 200),
    ("4/0 AWG", 230), ("250 kcmil", 255), ("300 kcmil", 285),
    ("350 kcmil", 310), ("400 kcmil", 335), ("500 kcmil", 380),
    ("600 kcmil", 420), ("750 kcmil", 475), ("1000 kcmil", 545),
)

DEMAND_FACTORS_DOC = {
    "lighting": "100% (design-aid simplification)",
    "receptacle": "100% of first 10 kVA, 50% of remainder (NEC 220.44)",
    "motor": "sum of motors + 25% of the largest (NEC 430.24)",
    "hvac": "100%",
    "xfmr": "100% (downstream transformer treated as its nameplate kVA)",
    "misc": "100%",
}


# ------------------------------------------------------------------ core
def line_current(va: float, v_ll: float, v_ln: float, poles: int,
                 phases: int) -> float:
    """RMS line current (A) for a load of ``va`` volt-amperes.

    ``phases``=3 -> three-phase (uses V_LL and sqrt(3)); otherwise a
    single-phase load on ``poles`` poles: 1-pole = line-to-neutral (V_LN),
    2-pole = line-to-line (V_LL).
    """
    if va <= 0:
        return 0.0
    if phases == 3:
        return va / (v_ll * SQRT3)
    if poles == 1:
        v = v_ln if v_ln else v_ll
        return va / v
    return va / v_ll


def load_va(load, system) -> float:
    """Resolve a :class:`~rvt.electrical.models.Load` to VA on ``system``.

    Precedence: explicit ``va`` -> ``kva`` -> ``amps`` (converted at the
    voltage the load actually sees on this panel).
    """
    if load.va is not None:
        return float(load.va)
    if load.kva is not None:
        return float(load.kva) * 1000.0
    if load.amps is not None:
        a = float(load.amps)
        if load.phases == 3:
            return a * system.v_ll * SQRT3
        if load.poles == 1:
            return a * (system.v_ln or system.v_ll)
        return a * system.v_ll
    raise ValueError(f"load {load.description!r} has no va/kva/amps")


def transformer_current(kva: float, volts: float, phases: int = 3) -> float:
    """Full-load current: 3-ph  I = kVA*1000/(V*sqrt(3)); 1-ph I = kVA*1000/V."""
    if phases == 3:
        return kva * 1000.0 / (volts * SQRT3)
    return kva * 1000.0 / volts


def next_standard_ocpd(amps: float, table: Iterable[int] = STANDARD_OCPD) -> int:
    """Smallest standard rating >= ``amps`` (NEC 240.6(A))."""
    for r in table:
        if r >= amps - 1e-9:
            return r
    raise ValueError(f"no standard OCPD >= {amps:.1f} A")


def design_amps(amps: float, continuous: bool) -> float:
    """Amps to size the OCPD on: 125% for continuous loads, else 100%."""
    return amps * 1.25 if continuous else amps


def select_breaker(amps: float, continuous: bool,
                   min_rating: float = 0.0) -> tuple:
    """Return ``(breaker_A, note)`` — 125% for continuous, next standard,
    but never below ``min_rating`` (e.g. a 20 A branch-circuit minimum,
    a project convention rather than a code minimum)."""
    d = max(design_amps(amps, continuous), float(min_rating))
    b = next_standard_ocpd(d)
    note = (f"{amps:.1f} A x 125% = {design_amps(amps, True):.1f} A -> {b} A"
            if continuous else f"{amps:.1f} A -> {b} A")
    if min_rating and design_amps(amps, continuous) < min_rating:
        note += f" (min branch {min_rating:g} A)"
    return b, note


def select_wire(breaker_amps: float) -> str:
    """Smallest Cu 75 degC conductor whose ampacity >= the OCPD rating.

    Simplified: ignores derating (temperature / bundling) and voltage
    drop — flagged as a design aid; the engineer sizes conductors finally.
    """
    for name, amp in CU_AMPACITY_75C:
        if amp >= breaker_amps:
            return name
    return "(exceeds table - engineer to size)"


def transformer_primary_ocpd(kva: float, primary_v: float, phases: int = 3):
    """Primary breaker per the product rule: FLA x 125% -> next standard.

    Returns ``(fla, x125, ocpd)``. Example (from the spec): 75 kVA @ 480 V
    3-ph -> 90.2 A -> 112.8 A -> 125 A.
    """
    fla = transformer_current(kva, primary_v, phases)
    x125 = fla * 1.25
    return fla, x125, next_standard_ocpd(x125)


# ---------------------------------------------------------------- demand
def demand_kva(class_va: dict, largest_motor_va: float = 0.0) -> tuple:
    """Apply the simple demand factors to per-class connected VA.

    ``class_va`` maps load class -> connected VA. Returns
    ``(demand_va_total, {class: demand_va})``.
    """
    out = {}
    for cls, va in class_va.items():
        va = float(va)
        if cls == "receptacle":
            first = min(va, 10000.0)
            out[cls] = first + max(0.0, va - 10000.0) * 0.5
        elif cls == "motor":
            out[cls] = va + 0.25 * float(largest_motor_va)
        else:
            out[cls] = va
    return sum(out.values()), out


def panel_amps(kva: float, system) -> float:
    """Amps drawn at the panel for ``kva`` on the given voltage system."""
    if kva <= 0:
        return 0.0
    if system.phases == 3:
        return kva * 1000.0 / (system.v_ll * SQRT3)
    return kva * 1000.0 / system.v_ll


# --------------------------------------------------------- phase balancing
PHASES = ("A", "B", "C")
PAIRS = (("A", "B"), ("B", "C"), ("C", "A"))


def slot_phase(slot: int, phases_on_bus: int = 3) -> str:
    """Phase of a physical panel slot.

    Slots number down two columns (odd left, even right). Rows alternate
    phases: row r = (slot-1)//2 -> phase 'ABC'[r % 3] for a 3-phase bus,
    'AB'[r % 2] for a 1-phase 3-wire bus.
    """
    row = (slot - 1) // 2
    if phases_on_bus == 3:
        return PHASES[row % 3]
    return ("A", "B")[row % 2]


def circuit_slots(start: int, poles: int) -> tuple:
    """Slots occupied by a breaker of ``poles`` poles starting at ``start``
    (same column, consecutive rows): 2-pole on 5 -> (5, 7)."""
    return tuple(start + 2 * i for i in range(poles))


def phase_va_split(va: float, phases_used: tuple) -> dict:
    """Distribute a circuit's VA equally across the phases it lands on
    (the usual panel-schedule convention: 3-pole load = VA/3 per phase)."""
    share = va / len(phases_used) if phases_used else 0.0
    return {p: (share if p in phases_used else 0.0) for p in PHASES}


def imbalance(phase_va: dict, phases: int = 3) -> float:
    """max - min per-phase VA (0 = perfectly balanced). ``phases``=1 for a
    single-phase 3-wire bus compares legs A/B only."""
    keys = PHASES if phases == 3 else ("A", "B")
    vals = [phase_va[p] for p in keys]
    return max(vals) - min(vals)


def imbalance_pct(phase_va: dict, phases: int = 3) -> float:
    """(max - min) / average, as a percentage; 0 when nothing connected."""
    keys = PHASES if phases == 3 else ("A", "B")
    vals = [phase_va[p] for p in keys]
    avg = sum(vals) / len(keys)
    if avg <= 0:
        return 0.0
    return (max(vals) - min(vals)) / avg * 100.0

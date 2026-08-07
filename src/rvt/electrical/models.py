"""Data model for the electrical calc engine.

Pure-stdlib dataclasses describing an electrical distribution job:
panelboards, the loads/circuits they serve, and dry-type transformers.
All numbers are DESIGN AIDS — a licensed engineer reviews every output
(that is exactly the product model: the AI computes, the seats review).

Voltage systems are given as strings such as ``'480Y/277'``,
``'208Y/120'``, ``'240/120'``, ``'480'``, ``'208'``. :class:`VoltageSystem`
parses them into line-to-line / line-to-neutral volts, phase count and
wire count.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


# ----------------------------------------------------------------- voltage
@dataclass(frozen=True)
class VoltageSystem:
    """A supply system: line-to-line volts, line-to-neutral volts (0 if no
    neutral), number of phases (1 or 3) and wires."""

    text: str
    v_ll: float
    v_ln: float
    phases: int
    wires: int

    @staticmethod
    def parse(text: str, phases: Optional[int] = None,
              wires: Optional[int] = None) -> "VoltageSystem":
        t = str(text).strip().upper().replace(" ", "").replace("V", "")
        # forms: 480Y/277  208Y/120  120/240 (1ph)  240/120  480  208  600Y/347
        m = re.fullmatch(r"(\d+(?:\.\d+)?)Y?/(\d+(?:\.\d+)?)", t)
        if m:
            a, b = float(m.group(1)), float(m.group(2))
            hi, lo = max(a, b), min(a, b)
            # wye 3-phase if ratio ~ sqrt(3); else 1-phase 3-wire (240/120)
            ratio = hi / lo if lo else 0.0
            if 1.6 < ratio < 1.85:
                return VoltageSystem(text, hi, lo, phases or 3, wires or 4)
            return VoltageSystem(text, hi, lo, phases or 1, wires or 3)
        m = re.fullmatch(r"(\d+(?:\.\d+)?)", t)
        if m:
            v = float(m.group(1))
            ph = phases or 3
            if ph == 1:
                return VoltageSystem(text, v, v, 1, wires or 2)
            return VoltageSystem(text, v, round(v / 3 ** 0.5, 1), 3, wires or 3)
        raise ValueError(f"unrecognised voltage system: {text!r}")

    @property
    def label(self) -> str:
        if self.phases == 3 and self.wires == 4:
            return f"{self.v_ll:g}Y/{self.v_ln:g}V, 3PH, 4W"
        if self.phases == 3:
            return f"{self.v_ll:g}V, 3PH, {self.wires}W"
        return f"{self.v_ll:g}/{self.v_ln:g}V, 1PH, {self.wires}W"


# ------------------------------------------------------------------ loads
LOAD_CLASSES = ("lighting", "receptacle", "motor", "hvac", "xfmr", "misc")


@dataclass
class Load:
    """A connected load. Supply exactly one of ``va``, ``kva`` or
    ``amps`` (with the panel voltage) — :func:`rvt.electrical.calcs.load_va`
    resolves it against the panel it lands on."""

    description: str
    va: Optional[float] = None
    kva: Optional[float] = None
    amps: Optional[float] = None
    phases: int = 1              # 1 or 3
    poles: Optional[int] = None    # 1, 2 or 3 (default: 1 for 1-ph, 3 for 3-ph)
    load_class: str = "misc"       # one of LOAD_CLASSES
    continuous: bool = False       # NEC continuous load (3+ hours) -> 125% OCPD
    breaker: Optional[float] = None  # assigned OCPD, else computed
    wire: Optional[str] = None       # assigned conductor, else computed
    number: Optional[int] = None     # fixed circuit (slot) number, else assigned
    tag: Optional[str] = None        # equipment element name this feeds (e.g.
                                     # 'XFMR-LR1'); lets the tekton-ifc wire a
                                     # real circuit between two authored elements

    def __post_init__(self) -> None:
        if self.load_class not in LOAD_CLASSES:
            raise ValueError(f"load_class must be one of {LOAD_CLASSES}: "
                             f"{self.load_class!r}")
        if self.phases not in (1, 3):
            raise ValueError(f"phases must be 1 or 3: {self.phases}")
        if self.poles is None:
            self.poles = 3 if self.phases == 3 else 1
        if self.poles not in (1, 2, 3):
            raise ValueError(f"poles must be 1, 2 or 3: {self.poles}")
        if self.phases == 3 and self.poles != 3:
            raise ValueError("a 3-phase load needs a 3-pole breaker")


@dataclass
class Panel:
    name: str
    system: VoltageSystem
    mains_type: str = "MLO"        # 'MCB' (main circuit breaker) | 'MLO'
    mains_rating: float = 225.0    # A
    bus_rating: float = 225.0      # A
    spaces: int = 42               # pole spaces (poles) on the bus
    fed_from: str = ""
    feeder: str = ""
    mounting: str = "Surface"
    aic_ka: Optional[float] = None
    min_branch_breaker: float = 15.0   # A; commercial convention often 20
    loads: list = field(default_factory=list)   # list[Load]
    notes: str = ""


@dataclass
class Circuit:
    """A load assigned to a panel slot with its computed breaker/wire.

    ``slots`` are the physical pole positions occupied (odd = left column,
    even = right column). A 2-pole breaker on slot 5 occupies (5, 7); a
    3-pole on slot 1 occupies (1, 3, 5). ``phases_used`` are the phase
    letters those slots land on ('A', 'B', 'C')."""

    number: int
    slots: tuple
    phases_used: tuple
    load: Load
    va: float
    amps: float
    breaker: float
    wire: str
    va_by_phase: dict          # {'A': va, 'B': va, 'C': va}
    breaker_note: str = ""

    @property
    def poles(self) -> int:
        return len(self.slots)


@dataclass
class Transformer:
    name: str
    kva: float
    primary_v: float
    secondary_v: float
    phases: int = 3
    secondary_system: str = ""     # e.g. '208Y/120'
    fed_from: str = ""
    feeds: str = ""
    impedance_pct: Optional[float] = None

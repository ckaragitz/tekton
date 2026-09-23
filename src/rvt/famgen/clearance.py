"""rvt.famgen.clearance -- NEC working space about electrical equipment, as DATA.

THE GAP THIS CLOSES (owner steer #818: "for the future you need to know NEC code
in order to get the clearances on there", and "clearances need to be toggleable
within the family parameters").  A generated electrical family modelled the
equipment and nothing about the space the code requires in front of it -- the
first thing an electrical designer checks.  This module is the table a family
generator sizes that space from (#819); drawing it is #820.

WHAT THE TABLE IS.  NEC (NFPA 70) 110.26, working space for equipment likely to
be examined, adjusted, serviced or maintained while energized:

* DEPTH (110.26(A)(1), Table 110.26(A)(1)) -- by nominal voltage to ground and
  by CONDITION, i.e. what faces the equipment across the space:
    1  exposed live parts on one side; no live or grounded parts on the other
    2  exposed live parts on one side; grounded parts (concrete, brick, tile
       walls count as grounded) on the other
    3  exposed live parts on both sides
  Measured from the exposed live parts, or from the enclosure front when they
  are enclosed.
* WIDTH (110.26(A)(2)) -- the equipment width or 30 in, whichever is greater.
* HEIGHT (110.26(A)(3)) -- 6-1/2 ft or the equipment height, whichever greater.

No NFPA text is reproduced here -- NFPA 70 is copyrighted and this repository
is public (hard rule 6).  Numbers and article references only.

WHAT IS AND IS NOT VERIFIED -- read this before trusting or adding a row.

Every depth row carries ``checked_against`` and ``corroboration``.  As first
written (2026-09-23) NO row was checked against the NFPA 70 text: the session
environment's egress proxy blocked every source page it tried (#819).  The rows
are the commonly cited values, corroborated by model knowledge and one
web-search summary -- two model-derived sources, which is corroboration, not
verification.  The 601-1000 V row rests on the search summary alone and is
marked weaker.  :func:`working_space` reports this status with every answer, so
a family generated from an unchecked row says so in plain words.  To upgrade a
row, read the edition text and set ``checked_against`` -- never by editing the
status alone.

Editions: the depths above are, per the same search, unchanged 2017-2026 (the
601-1000 V band was added in 2017).  Rows are keyed by the editions they are
claimed for; the answer names the edition used.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

IN = 1.0 / 12.0                                   # feet per inch

#: Editions the table is claimed for, newest first.
EDITIONS: Tuple[int, ...] = (2026, 2023, 2020, 2017)
DEFAULT_EDITION = 2026

CONDITIONS = (1, 2, 3)

#: The status string a row carries when nobody has read the code text for it.
UNCHECKED = "not checked against the NFPA 70 text"


@dataclass(frozen=True)
class DepthRow:
    """One voltage band of Table 110.26(A)(1)."""
    v_min: float                                  # nominal volts to ground, inclusive
    v_max: float                                  # inclusive
    depth_ft: Tuple[float, float, float]          # Condition 1, 2, 3
    editions: Tuple[int, ...]
    checked_against: Optional[str]                # edition text read, or None
    corroboration: Tuple[str, ...]
    confidence: str                               # "corroborated" | "single-source"


_MODEL = "model knowledge (commonly cited value)"
_SEARCH = "web-search summary, 2026-09-23 (no source page reachable: egress blocked, #819)"

DEPTH_TABLE: Tuple[DepthRow, ...] = (
    DepthRow(0.0, 150.0, (3.0, 3.0, 3.0), EDITIONS, None, (_MODEL, _SEARCH), "corroborated"),
    DepthRow(151.0, 600.0, (3.0, 3.5, 4.0), EDITIONS, None, (_MODEL, _SEARCH), "corroborated"),
    DepthRow(601.0, 1000.0, (3.0, 4.0, 5.0), EDITIONS, None, (_SEARCH,), "single-source"),
)

MIN_WIDTH_FT = 30.0 * IN                          # 110.26(A)(2)
MIN_HEIGHT_FT = 6.5                               # 110.26(A)(3)


class ClearanceError(ValueError):
    """A request the table cannot answer -- said by name, never guessed."""


@dataclass
class WorkingSpace:
    """The working space for one piece of equipment, with its provenance."""
    depth_ft: float
    width_ft: float
    height_ft: float
    edition: int
    voltage_to_ground: float
    condition: int
    source: str                                   # "NEC 2026 110.26(A)(1)-(3)"
    verified: bool
    status: str                                   # the plain-words line a report carries
    assumed: Dict[str, str] = field(default_factory=dict)


def _row_for(volts: float, edition: int) -> DepthRow:
    for row in DEPTH_TABLE:
        if row.v_min <= volts <= row.v_max:
            if edition not in row.editions:
                raise ClearanceError(
                    f"NEC {edition}: the {row.v_min:g}-{row.v_max:g} V row is not held for "
                    f"that edition (held: {', '.join(map(str, row.editions))})")
            return row
    if 150.0 < volts < 151.0 or 600.0 < volts < 601.0:
        raise ClearanceError(f"{volts:g} V to ground falls between the table's bands; state "
                             "the nominal voltage (e.g. 120, 277, 480)")
    raise ClearanceError(f"{volts:g} V to ground is outside Table 110.26(A)(1) (0-1000 V); "
                         "over 1000 V is 110.34, which this table does not hold")


def working_space(*, equipment_width_ft: float, equipment_height_ft: float,
                  voltage_to_ground: Optional[float] = None,
                  condition: Optional[int] = None,
                  edition: Optional[int] = None,
                  default_voltage_to_ground: float = 277.0) -> WorkingSpace:
    """The 110.26 working space in front of equipment of the given size.

    Voltage to ground, Condition and edition are what a prompt usually does NOT
    say (S-2026-08-11-c: residue).  Each one left out is DEFAULTED, and the
    default is recorded in ``assumed`` so the caller can state it -- never
    silently.  Delivery is never gated on them (hard rule 1):

    * voltage -> ``default_voltage_to_ground`` (277 V, a 480Y/277 V system: the
      common commercial lighting voltage, which lands in the 151-600 V row);
    * Condition -> 1, the least demanding;
    * edition -> :data:`DEFAULT_EDITION`.

    Condition 1 is the least demanding depth, so a defaulted Condition can
    UNDER-state the space.  ``assumed`` says so, for the caller to surface.
    """
    assumed: Dict[str, str] = {}
    if edition is None:
        edition = DEFAULT_EDITION
        assumed["edition"] = f"NEC {edition} (newest held; the enforcing jurisdiction may differ)"
    elif edition not in EDITIONS:
        raise ClearanceError(f"NEC {edition} is not held (held: {', '.join(map(str, EDITIONS))})")
    if voltage_to_ground is None:
        voltage_to_ground = float(default_voltage_to_ground)
        assumed["voltage_to_ground"] = (f"{voltage_to_ground:g} V to ground -- not stated; "
                                        "state it if the system differs")
    if condition is None:
        condition = 1
        assumed["condition"] = ("Condition 1 (nothing live or grounded opposite) -- the least "
                                "demanding; a wall of concrete, brick or tile opposite is "
                                "Condition 2 and needs more depth above 150 V")
    elif condition not in CONDITIONS:
        raise ClearanceError(f"Condition {condition} does not exist; 110.26(A)(1) has 1, 2, 3")
    if equipment_width_ft <= 0 or equipment_height_ft <= 0:
        raise ClearanceError("equipment width and height must be positive")

    row = _row_for(float(voltage_to_ground), edition)
    verified = row.checked_against is not None
    status = (f"working space per NEC {edition} Table 110.26(A)(1)"
              + ("" if verified else
                 f" as commonly cited -- {UNCHECKED}"
                 + (" (single source)" if row.confidence == "single-source" else "")))
    return WorkingSpace(
        depth_ft=row.depth_ft[condition - 1],
        width_ft=max(float(equipment_width_ft), MIN_WIDTH_FT),
        height_ft=max(float(equipment_height_ft), MIN_HEIGHT_FT),
        edition=edition, voltage_to_ground=float(voltage_to_ground), condition=condition,
        source=f"NEC {edition} 110.26(A)(1)-(3)", verified=verified, status=status,
        assumed=assumed)

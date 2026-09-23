"""rvt.famgen.clearance -- NEC working space about electrical equipment, as DATA.

THE GAP THIS CLOSES (owner steer #818: "for the future you need to know NEC code
in order to get the clearances on there", and "clearances need to be toggleable
within the family parameters").  A generated electrical family modelled the
equipment and nothing about the space the code requires around it -- the first
thing an electrical designer checks.  This module is the table a family
generator sizes that space from (#819); drawing it is #820.

WHAT THE TABLE IS.  NEC (NFPA 70) 110.26, spaces about electrical equipment
likely to be examined, adjusted, serviced or maintained while energized:

* WORKING SPACE, in front of the equipment:
  - depth (110.26(A)(1), Table 110.26(A)(1)) by nominal AC voltage to ground and
    by CONDITION -- what faces the equipment across the space:
      1  live parts on one side, nothing live or grounded on the other
      2  live parts on one side, grounded parts on the other (concrete, brick
         and tile walls count as grounded)
      3  live parts on both sides
    measured from the live parts, or from the enclosure front when enclosed;
  - width (110.26(A)(2)): the equipment width or 30 in, whichever is greater;
  - height (110.26(A)(3)): 6-1/2 ft or the equipment height, whichever greater.
* DEDICATED EQUIPMENT SPACE (110.26(E)(1)), for the equipment kinds that rule
  names only: a zone the width and depth of the equipment, from the floor to
  6 ft above the equipment or to the structural ceiling, whichever is lower.
  :data:`DEDICATED_SPACE_KINDS` says, per kind, whether it applies and why.

No NFPA text is reproduced -- NFPA 70 is copyrighted and this repository is
public (hard rule 6).  Numbers, article references and short functional
descriptions only.

WHAT IS AND IS NOT VERIFIED -- read this before trusting or adding a row.

Every rule here -- each depth row, the width and height minimums, the
dedicated-space rule and its list of kinds -- carries ``checked`` (the
``(edition, what was read)`` pairs) and ``corroboration``.  As first written
(2026-09-23) NOTHING was checked against the NFPA 70 text: the session
environment's egress proxy blocked every source page tried (#819).  The values
are the commonly cited ones, corroborated by model knowledge and a web-search
summary -- two model-derived sources, which is corroboration, not
verification.  Two rules are single-source: the 601-1000 V depth row (the
search summary alone) and the dedicated-space rule (model knowledge alone).

An answer is ``verified`` only if EVERY rule it used was checked FOR THE
EDITION it answered in -- the AND over rules, and per edition -- and
``verified`` is derived from ``checked``, never declared, so it cannot be
upgraded without recording what was read.  To upgrade a rule, read that
edition's text and add ``(edition, what was read)`` to its ``checked``.

PROVENANCE TIER.  The ledger has no "standard" tier.  A code minimum's source is
a named standard -- not a manufacturer (``fact``) and not the user (``given``)
-- which is what ``nominal`` means here (S-2026-08-10-e: source = standard
practice, never a manufacturer claim).  So every answer is tier ``nominal``,
source ``NEC <edition> <article>``, and the inputs it had to default are listed
in ``assumed``.

Editions: per the same search, these depths are unchanged 2017-2026 (the
601-1000 V band arrived in 2017).  Rows are keyed by the editions they are
claimed for; the answer names the edition used.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple

IN = 1.0 / 12.0                                   # feet per inch

#: Editions the table is claimed for, newest first.
EDITIONS: Tuple[int, ...] = (2026, 2023, 2020, 2017)
DEFAULT_EDITION = 2026

CONDITIONS = (1, 2, 3)

#: The default Condition.  2, not 1: the clearance is drawn as a solid to CATCH
#: obstructions, and a false clash costs a click while a missed one costs a code
#: violation.  Equipment most often faces a concrete, block or tile wall, which
#: is Condition 2.  (Condition 3 -- equipment facing live equipment -- is deeper
#: still; the assumption text says so.)  Changed from 1 in #826's review.
DEFAULT_CONDITION = 2
DEFAULT_VOLTAGE_TO_GROUND = 277.0

TIER = "nominal"

#: The status wording every unverified answer carries.
UNCHECKED = "not checked against the NFPA 70 text"

_MODEL = "model knowledge (commonly cited value)"
_SEARCH = "web-search summary, 2026-09-23 (no source page reachable: egress blocked, #819)"


@dataclass(frozen=True)
class Rule:
    """A single cited requirement and what backs it."""
    article: str                                  # e.g. "110.26(A)(2)"
    editions: Tuple[int, ...]
    #: ((edition, what was read), ...) -- a check covers only the edition whose
    #: text was read; checking the 2026 text says nothing about 2017's
    checked: Tuple[Tuple[int, str], ...]
    corroboration: Tuple[str, ...]
    confidence: str                               # "corroborated" | "single-source"

    def checked_for(self, edition: int) -> bool:
        return any(ed == edition for ed, _ in self.checked)


@dataclass(frozen=True)
class DepthRow:
    """One voltage band of Table 110.26(A)(1)."""
    v_min: float                                  # nominal AC volts to ground, inclusive
    v_max: float                                  # inclusive
    depth_ft: Tuple[float, float, float]          # Condition 1, 2, 3
    rule: Rule


def _rule(article: str, sources: Tuple[str, ...]) -> Rule:
    return Rule(article, EDITIONS, (), sources,
                "corroborated" if len(sources) >= 2 else "single-source")


DEPTH_TABLE: Tuple[DepthRow, ...] = (
    DepthRow(0.0, 150.0, (3.0, 3.0, 3.0), _rule("Table 110.26(A)(1)", (_MODEL, _SEARCH))),
    DepthRow(151.0, 600.0, (3.0, 3.5, 4.0), _rule("Table 110.26(A)(1)", (_MODEL, _SEARCH))),
    DepthRow(601.0, 1000.0, (3.0, 4.0, 5.0), _rule("Table 110.26(A)(1)", (_SEARCH,))),
)

WIDTH_RULE = _rule("110.26(A)(2)", (_MODEL, _SEARCH))
MIN_WIDTH_FT = 30.0 * IN

HEIGHT_RULE = _rule("110.26(A)(3)", (_MODEL, _SEARCH))
MIN_HEIGHT_FT = 6.5

DEDICATED_RULE = _rule("110.26(E)(1)", (_MODEL,))
DEDICATED_ABOVE_FT = 6.0                          # above the equipment, or to the ceiling

#: kind -> (applies, why).  The rule names switchboards, switchgear, panelboards
#: and motor control centers; a kind it does not name is NOT given a dedicated
#: space, and says so -- never applied to every electrical kind by default.
DEDICATED_SPACE_KINDS: Dict[str, Tuple[bool, str]] = {
    "panelboard": (True, "panelboards are named by 110.26(E)(1)"),
    "switchboard": (True, "switchboards are named by 110.26(E)(1)"),
    "switchgear": (True, "switchgear is named by 110.26(E)(1)"),
    "motor_control_center": (True, "motor control centers are named by 110.26(E)(1)"),
    "lighting_control_panel": (False, "a lighting control (relay) panel is not among the "
                               "kinds 110.26(E)(1) names, so none is applied; working space "
                               "still applies. BUT a unit built and listed as a panelboard "
                               "(e.g. remote-operated breakers) IS a panelboard for this rule "
                               "-- ask for kind 'panelboard' then"),
}


class ClearanceError(ValueError):
    """A request the table cannot answer -- said by name, never guessed."""


@dataclass
class WorkingSpace:
    """The working space in front of one piece of equipment, with provenance."""
    depth_ft: float
    width_ft: float
    height_ft: float
    edition: int
    voltage_to_ground: float
    condition: int
    source: str                                   # "NEC 2026 Table 110.26(A)(1), 110.26(A)(2)-(3)"
    tier: str                                     # always TIER
    verified: bool                                # every rule used was checked
    status: str                                   # the plain-words line a report carries
    assumed: Dict[str, str] = field(default_factory=dict)


@dataclass
class DedicatedSpace:
    """Whether 110.26(E)(1) applies to a kind, and the zone if it does."""
    applies: bool
    why: str
    width_ft: Optional[float] = None
    depth_ft: Optional[float] = None
    height_above_ft: Optional[float] = None       # above the equipment (see height_limit)
    height_limit: str = ""                        # the ceiling cap, in words -- always carried
    source: str = ""
    tier: str = TIER
    verified: bool = False
    status: str = ""


def _edition(edition: Optional[int], assumed: Dict[str, str]) -> int:
    if edition is None:
        assumed["edition"] = (f"NEC {DEFAULT_EDITION} (newest held; the enforcing "
                              "jurisdiction may differ)")
        return DEFAULT_EDITION
    if isinstance(edition, bool) or not isinstance(edition, int) or edition not in EDITIONS:
        raise ClearanceError(f"NEC {edition} is not held (held: {', '.join(map(str, EDITIONS))})")
    return edition


def _status(edition: int, rules: Tuple[Rule, ...], what: str) -> Tuple[bool, str]:
    verified = all(r.checked_for(edition) for r in rules)
    if verified:
        return True, f"{what} per NEC {edition}"
    weak = any(r.confidence == "single-source" for r in rules)
    return False, (f"{what} per NEC {edition} as commonly cited -- {UNCHECKED}"
                   + (" (single source)" if weak else ""))


def _row_for(volts: float, edition: int) -> DepthRow:
    for row in DEPTH_TABLE:
        if row.v_min <= volts <= row.v_max:
            if edition not in row.rule.editions:
                raise ClearanceError(
                    f"NEC {edition}: the {row.v_min:g}-{row.v_max:g} V row is not held for "
                    f"that edition (held: {', '.join(map(str, row.rule.editions))})")
            return row
    if 150.0 < volts < 151.0 or 600.0 < volts < 601.0:
        raise ClearanceError(f"{volts:g} V to ground falls between the table's bands; state "
                             "the nominal voltage (e.g. 120, 277, 480)")
    raise ClearanceError(
        f"{volts:g} V AC to ground is outside the 0-1000 V this table holds. Over 1000 V is "
        "covered elsewhere in the NEC (110.34 in the 2017 and 2020 editions; not verified for "
        "later ones), and DC working space is not held here at all")


def working_space(*, equipment_width_ft: float, equipment_height_ft: float,
                  voltage_to_ground: Optional[float] = None,
                  condition: Optional[int] = None,
                  edition: Optional[int] = None) -> WorkingSpace:
    """The 110.26(A) working space in front of equipment of the given size.

    Voltage, Condition and edition are what a prompt usually does NOT say
    (S-2026-08-11-c: residue).  Each one left out is DEFAULTED and recorded in
    ``assumed`` so the caller can state it -- never silently, never gating
    delivery (hard rule 1).  Voltage is NOMINAL AC volts to ground.
    """
    assumed: Dict[str, str] = {}
    edition = _edition(edition, assumed)

    if voltage_to_ground is None:
        voltage_to_ground = DEFAULT_VOLTAGE_TO_GROUND
        assumed["voltage_to_ground"] = (f"{voltage_to_ground:g} V AC to ground (a 480Y/277 V "
                                        "system) -- not stated; state it if the system differs")
    else:
        try:
            voltage_to_ground = float(voltage_to_ground)
        except (TypeError, ValueError):
            raise ClearanceError(f"voltage to ground {voltage_to_ground!r} is not a number")
        if math.isnan(voltage_to_ground) or voltage_to_ground < 0:
            raise ClearanceError(f"voltage to ground {voltage_to_ground:g} is not a voltage "
                                 "(it must be a number, 0 or more)")

    if condition is None:
        condition = DEFAULT_CONDITION
        assumed["condition"] = (
            f"Condition {condition} (equipment facing a concrete, block or tile wall) -- the "
            "common case, chosen so a drawn clearance catches obstructions; Condition 1 "
            "(nothing grounded opposite) can be shallower, Condition 3 (equipment facing live "
            "equipment) can be deeper -- below 151 V to ground all three are the same")
    elif isinstance(condition, bool) or not isinstance(condition, int) or condition not in CONDITIONS:
        raise ClearanceError(f"Condition {condition!r} does not exist; 110.26(A)(1) has 1, 2, 3")

    if not (equipment_width_ft > 0 and equipment_height_ft > 0):
        raise ClearanceError("equipment width and height must be positive")

    row = _row_for(voltage_to_ground, edition)
    rules = (row.rule, WIDTH_RULE, HEIGHT_RULE)
    verified, status = _status(edition, rules, "working space")
    return WorkingSpace(
        depth_ft=row.depth_ft[condition - 1],
        width_ft=max(float(equipment_width_ft), MIN_WIDTH_FT),
        height_ft=max(float(equipment_height_ft), MIN_HEIGHT_FT),
        edition=edition, voltage_to_ground=voltage_to_ground, condition=condition,
        source=f"NEC {edition} {row.rule.article}, {WIDTH_RULE.article}, {HEIGHT_RULE.article}",
        tier=TIER, verified=verified, status=status, assumed=assumed)


def dedicated_space(kind: str, *, equipment_width_ft: float, equipment_depth_ft: float,
                    edition: Optional[int] = None,
                    ceiling_above_ft: Optional[float] = None) -> DedicatedSpace:
    """110.26(E)(1) dedicated equipment space for a taxonomy ``kind``.

    A kind the rule does not name gets ``applies=False`` and the reason; a kind
    this table has no entry for is refused by name rather than guessed either
    way.
    """
    if kind not in DEDICATED_SPACE_KINDS:
        raise ClearanceError(f"no 110.26(E)(1) decision is held for kind {kind!r}; add one to "
                             "DEDICATED_SPACE_KINDS rather than guessing")
    edition = _edition(edition, {})
    if not (equipment_width_ft > 0 and equipment_depth_ft > 0):
        raise ClearanceError("equipment width and depth must be positive")
    if ceiling_above_ft is not None:
        if isinstance(ceiling_above_ft, bool) or not isinstance(ceiling_above_ft, (int, float)):
            raise ClearanceError(f"the ceiling above the equipment must be a number, "
                                 f"not {ceiling_above_ft!r}")
        if not (ceiling_above_ft >= 0):
            raise ClearanceError("the ceiling above the equipment must be 0 or more")
    applies, why = DEDICATED_SPACE_KINDS[kind]
    verified, status = _status(edition, (DEDICATED_RULE,), "dedicated equipment space")
    if not applies:
        return DedicatedSpace(False, why, source=f"NEC {edition} {DEDICATED_RULE.article}",
                              verified=verified, status=status)
    above = DEDICATED_ABOVE_FT
    if ceiling_above_ft is not None:
        above = min(above, float(ceiling_above_ft))
        limit = (f"capped at the structural ceiling ({float(ceiling_above_ft):g} ft above the "
                 "equipment)" if above < DEDICATED_ABOVE_FT else
                 f"{DEDICATED_ABOVE_FT:g} ft above the equipment (the ceiling is not lower)")
    else:
        limit = (f"{DEDICATED_ABOVE_FT:g} ft above the equipment OR to the structural ceiling, "
                 "whichever is lower -- the ceiling is not known here, so the "
                 "6 ft may overshoot a low ceiling")
    return DedicatedSpace(True, why, width_ft=float(equipment_width_ft),
                          depth_ft=float(equipment_depth_ft),
                          height_above_ft=above, height_limit=limit,
                          source=f"NEC {edition} {DEDICATED_RULE.article}",
                          verified=verified, status=status)

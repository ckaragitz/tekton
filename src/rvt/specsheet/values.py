"""rvt.specsheet.values -- read a number out of a spec-sheet cell, or refuse.

This module is the narrow gate every extracted figure passes through, and
it is deliberately unhelpful: it returns a value ONLY when the sheet states
one unambiguously, and returns ``None`` -- with a reason -- for everything
else.  The failure this guards against is the quiet one: a parser that
turns ``"36 - 90"`` into ``36``, ``"Contact factory"`` into ``0``, or
``2-3/8"`` into ``2``.  Each of those writes a number the manufacturer
never published into a family that claims to carry their dimensions.

WHAT IS A VALUE
  * a plain decimal or integer, with or without a unit: ``38 W``, ``47.75``
  * a fraction or mixed fraction, which is EXACT at the denominators sheets
    use: ``3/4``, ``47-3/4 in``, ``2 3/8"``
  * a thousands-separated integer: ``1,250 lb``

WHAT IS REFUSED (:class:`Refusal`, never a number)
  * a RANGE -- ``36-90``, ``36 to 90``, ``36–90``: the sheet states two
    numbers and we do not get to pick one
  * a LIST -- ``15, 30, 45``: same reason
  * prose placeholders -- ``Contact factory``, ``N/A``, ``—``, ``TBD``, ``-``
  * a bare unit, an empty cell, or text with no digits at all
  * anything with a leading qualifier that changes its meaning: ``approx.``,
    ``up to``, ``max``, ``min``, ``<``, ``>``, ``±``, ``~``

ROUNDING.  Nothing here rounds.  Fractions convert exactly; a decimal is
kept at the precision printed.  Unit CONVERSION is not done here at all --
:func:`to_inches` is offered separately and its result is ``derived``, never
``fact`` (see :mod:`rvt.specsheet.sheet`), so the stated figure and our
arithmetic never get confused for each other.

TERRITORY (specsheet stream): see :mod:`rvt.specsheet.pdftext`.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from fractions import Fraction
from typing import Optional, Tuple, Union

__all__ = [
    "Measure", "Refusal", "parse_measure", "to_inches", "UNITS",
    "IN_PER_FT", "MM_PER_IN",
]

IN_PER_FT = 12.0
MM_PER_IN = 25.4

#: unit spellings a sheet uses -> the canonical token we record
UNITS = {
    "in": "in", "in.": "in", "inch": "in", "inches": "in", '"': "in", "”": "in",
    "ft": "ft", "ft.": "ft", "foot": "ft", "feet": "ft", "'": "ft",
    "mm": "mm", "cm": "cm", "m": "m",
    "w": "W", "kw": "kW", "va": "VA", "kva": "kVA",
    "v": "V", "vac": "Vac", "vdc": "Vdc", "a": "A", "ka": "kA",
    "k": "K", "lm": "lm", "lux": "lux", "hz": "Hz",
    "lb": "lb", "lbs": "lb", "kg": "kg",
    "%": "%", "cri": "CRI",
}

#: text that means "the sheet does not state a number here"
_PLACEHOLDERS = {
    "", "-", "--", "—", "–", "n/a", "na", "n.a.", "tbd", "tba", "none",
    "consult factory", "contact factory", "contact eaton", "consult",
    "varies", "variable", "see note", "see notes", "*", "x", "std",
}

#: qualifiers that change what a number means; we do not silently drop them
_QUALIFIERS = re.compile(
    r"^\s*(approx\.?|approximately|about|up\s+to|max\.?|maximum|min\.?|minimum"
    r"|nom\.?|nominal|typ\.?|typical|<|>|≤|≥|±|\+/-|~)\s*", re.I)

_FRACTION = r"\d+\s*/\s*\d+"
_MIXED = rf"\d+\s*[-\s]\s*{_FRACTION}"
_DECIMAL = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+\.\d+|\.\d+|\d+"

_RANGE = re.compile(
    rf"(?<![\d/])({_DECIMAL})\s*(?:-|–|—|to|\.\.\.|\.\.)\s*({_DECIMAL})(?![\d/])",
    re.I)


@dataclass(frozen=True)
class Measure:
    """One number the sheet states, with the unit and the exact source text."""
    value: float
    unit: str = ""
    raw: str = ""
    exact: bool = True            # False if the sheet printed a rounded form

    def as_json(self) -> dict:
        return {"value": self.value, "unit": self.unit, "raw": self.raw}

    def __str__(self) -> str:
        return f"{self.value}{(' ' + self.unit) if self.unit else ''}"


@dataclass(frozen=True)
class Refusal:
    """Why no number was taken from a cell.  Carried into the report so a
    blank field says *why* it is blank."""
    reason: str
    raw: str = ""

    def __bool__(self) -> bool:          # so `if parse_measure(...)` is False
        return False

    def as_json(self) -> dict:
        return {"refused": self.reason, "raw": self.raw}

    def __str__(self) -> str:
        return f"{self.reason} ({self.raw!r})" if self.raw else self.reason


def _unit_of(tail: str) -> str:
    t = tail.strip().strip(".,;:").lower()
    if not t:
        return ""
    return UNITS.get(t, "")


def _fraction_value(text: str) -> Optional[float]:
    """``3/4`` / ``47-3/4`` / ``2 3/8`` -> exact float, else None."""
    m = re.fullmatch(rf"\s*(\d+)\s*[-\s]\s*(\d+)\s*/\s*(\d+)\s*", text)
    if m:
        whole, num, den = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if den == 0:
            return None
        return float(whole + Fraction(num, den))
    m = re.fullmatch(r"\s*(\d+)\s*/\s*(\d+)\s*", text)
    if m:
        num, den = int(m.group(1)), int(m.group(2))
        if den == 0:
            return None
        return float(Fraction(num, den))
    return None


def parse_measure(text: str) -> Union[Measure, Refusal]:
    """Read ONE number out of a spec-sheet cell, or refuse with a reason.

    Never returns a number the cell does not literally state.  See the
    module docstring for the accepted and refused shapes.
    """
    if text is None:
        return Refusal("empty cell", "")
    raw = str(text).strip()
    if raw.lower() in _PLACEHOLDERS:
        return Refusal("the sheet states no value here", raw)
    if "�" in raw:
        return Refusal("text could not be decoded from the PDF", raw)
    if not re.search(r"\d", raw):
        return Refusal("no digits in the cell", raw)

    q = _QUALIFIERS.match(raw)
    if q:
        return Refusal(f"qualified value ({q.group(1).strip()}) -- not a "
                       f"stated figure", raw)

    body = raw
    # a trailing unit token, taken off before range/fraction analysis
    unit = ""
    um = re.search(r"([A-Za-z%°\"'”]+\.?|\")\s*$", body)
    if um:
        cand = _unit_of(um.group(1))
        if cand:
            unit = cand
            body = body[:um.start()].strip()
    body = body.replace("°", "").strip()

    # a mixed fraction contains a '-' that is NOT a range: test fractions first
    frac = _fraction_value(body)
    if frac is not None:
        return Measure(frac, unit, raw)

    if _RANGE.search(body):
        return Refusal("the sheet states a range, not one value", raw)
    if body.count(",") and re.search(r",\s*\d", body) and \
            not re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", body):
        return Refusal("the sheet lists several values", raw)

    nums = re.findall(_DECIMAL, body)
    if not nums:
        return Refusal("no number in the cell", raw)
    if len(nums) > 1:
        return Refusal(f"the cell holds {len(nums)} numbers", raw)

    token = nums[0]
    leftover = re.sub(re.escape(token), "", body, count=1).strip()
    leftover = leftover.strip(".,;:()")
    if leftover and not _unit_of(leftover):
        return Refusal(f"unparsed text beside the number ({leftover!r})", raw)
    if leftover and not unit:
        unit = _unit_of(leftover)

    try:
        value = float(token.replace(",", ""))
    except ValueError:
        return Refusal("number could not be read", raw)
    return Measure(value, unit, raw)


def to_inches(m: Measure) -> Optional[Measure]:
    """Convert a length to inches EXACTLY, or return None.

    The result is our arithmetic, not the sheet's statement -- callers
    record it as ``derived`` and keep the stated figure as the ``fact``.
    Returns None for a non-length unit or a unitless number (we do not
    assume what a bare number means).
    """
    if m.unit == "in":
        return m
    if m.unit == "ft":
        return Measure(m.value * IN_PER_FT, "in", m.raw)
    if m.unit == "mm":
        return Measure(m.value / MM_PER_IN, "in", m.raw)
    if m.unit == "cm":
        return Measure(m.value * 10.0 / MM_PER_IN, "in", m.raw)
    if m.unit == "m":
        return Measure(m.value * 1000.0 / MM_PER_IN, "in", m.raw)
    return None

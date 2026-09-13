"""rvt.specsheet.vocab -- what a spec sheet's row LABELS mean, as data.

#685 (S-2026-08-11-c) is explicit that breadth here is data, not code: adding
a synonym, a field or a unit must not need a new branch anywhere.  So the
label vocabulary, the unit table and the per-field kinds all live in this
module as plain tables, and :mod:`rvt.specsheet.sheet` only reads them.

WHAT THE SYNONYMS ARE, AND ARE NOT.  They are ordinary trade usage -- the
words English-language electrical and mechanical submittals use for the same
quantity ("Catalog Number", "Cat. No.", "Part Number").  They are NOT copied
from any manufacturer's document, and they carry no dimension, rating or
other manufacturer fact: matching "Height" to ``height_in`` says nothing
about how tall anything is.  The VALUE always comes from the user's sheet
and is cited to it (#688 DONE 3).

MATCHING IS A CLAIM, SO IT IS RECORDED AS ONE.  A row whose label matched a
synonym carries both the canonical key and the sheet's literal label into the
report, because "Depth" on a panelboard sheet and "Depth" on a light fixture
sheet are the same word for different axes and only a human reading the
report can catch that.  A row that matches nothing is listed too, never
dropped -- "the sheet said this and we did not use it" is information.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

__all__ = ["FIELDS", "SYNONYMS", "LENGTH_UNITS", "canonical_key", "field_kind"]

#: canonical key -> (kind, unit)   kind: "length" | "number" | "text"
#: A "length" is normalised to INCHES (the engine's famspec unit); a "number"
#: keeps whatever unit the sheet stated; "text" is never parsed numerically.
FIELDS: Dict[str, Tuple[str, str]] = {
    "height_in":      ("length", "in"),
    "width_in":       ("length", "in"),
    "depth_in":       ("length", "in"),
    "length_in":      ("length", "in"),
    "diameter_in":    ("length", "in"),
    "weight_lb":      ("number", "lb"),
    "amps":           ("number", "A"),
    "sccr_ka":        ("number", "kA"),
    "kva":            ("number", "kVA"),
    "watts":          ("number", "W"),
    "lumens":         ("number", "lm"),
    "cct_k":          ("number", "K"),
    "voltage":        ("text",   ""),
    "phases":         ("number", ""),
    "frequency_hz":   ("number", "Hz"),
    "enclosure":      ("text",   ""),
    "manufacturer":   ("text",   ""),
    "model":          ("text",   ""),
    "series":         ("text",   ""),
    "mounting":       ("text",   ""),
    "material":       ("text",   ""),
    "finish":         ("text",   ""),
    "ip_rating":      ("text",   ""),
    "temperature_c":  ("number", "C"),
}

#: canonical key -> the labels a sheet writes it as, lowercased.  Longest
#: match wins (see ``canonical_key``), so "overall height" beats "height".
SYNONYMS: Dict[str, List[str]] = {
    "height_in":     ["height", "overall height", "height (h)", "h",
                      "case height", "enclosure height"],
    "width_in":      ["width", "overall width", "width (w)", "w",
                      "case width", "enclosure width"],
    "depth_in":      ["depth", "overall depth", "depth (d)", "d",
                      "case depth", "enclosure depth", "projection"],
    "length_in":     ["length", "overall length", "length (l)", "l"],
    "diameter_in":   ["diameter", "dia", "dia.", "nominal diameter", "od",
                      "outside diameter"],
    "weight_lb":     ["weight", "net weight", "shipping weight",
                      "approximate weight", "approx. weight", "wt", "wt."],
    "amps":          ["amperes", "ampere rating", "amps", "current rating",
                      "main bus rating", "bus rating", "ampacity",
                      "rated current", "continuous current"],
    "sccr_ka":       ["short circuit rating", "short circuit current rating",
                      "sccr", "interrupting rating", "aic", "kaic",
                      "withstand rating"],
    "kva":           ["kva", "kva rating", "rated kva", "capacity"],
    "watts":         ["watts", "wattage", "input watts", "input power",
                      "power", "rated power"],
    "lumens":        ["lumens", "delivered lumens", "lumen output",
                      "light output"],
    "cct_k":         ["cct", "color temperature", "colour temperature",
                      "correlated color temperature"],
    "voltage":       ["voltage", "system voltage", "input voltage",
                      "rated voltage", "volts", "supply voltage"],
    "phases":        ["phase", "phases", "no. of phases"],
    "frequency_hz":  ["frequency", "hz", "line frequency"],
    "enclosure":     ["enclosure", "enclosure type", "nema type",
                      "nema rating", "enclosure rating", "housing"],
    "manufacturer":  ["manufacturer", "mfr", "mfr.", "brand", "made by",
                      "vendor"],
    "model":         ["catalog number", "catalog no", "catalog no.",
                      "cat no", "cat no.", "cat. no.", "part number",
                      "part no", "part no.", "model", "model number",
                      "model no.", "type number", "ordering number"],
    "series":        ["series", "product line", "line", "family"],
    "mounting":      ["mounting", "mounting type", "installation",
                      "mounting method"],
    "material":      ["material", "construction", "body material"],
    "finish":        ["finish", "color", "colour", "paint"],
    "ip_rating":     ["ip rating", "ingress protection", "ip"],
    "temperature_c": ["ambient temperature", "operating temperature",
                      "max ambient"],
}

#: unit token (lowercased, punctuation stripped) -> inches per unit.
#: Only LENGTH lives here; every other unit is carried through verbatim,
#: because converting a rating is how a 65 kA becomes a 65000 A nobody asked
#: for.
LENGTH_UNITS: Dict[str, float] = {
    "in": 1.0, "inch": 1.0, "inches": 1.0, '"': 1.0, "”": 1.0, "″": 1.0,
    "ft": 12.0, "foot": 12.0, "feet": 12.0, "'": 12.0, "’": 12.0, "′": 12.0,
    "mm": 1.0 / 25.4, "cm": 1.0 / 2.54, "m": 1000.0 / 25.4,
}

#: built once: every synonym -> key, longest first so the specific wins
_INDEX: List[Tuple[str, str]] = sorted(
    ((syn, key) for key, syns in SYNONYMS.items() for syn in syns),
    key=lambda p: (-len(p[0]), p[0]))


def _norm(label: str) -> str:
    """Lowercase, strip the trailing colon and the decorative punctuation
    sheets put around labels -- not the parentheses INSIDE one ("Width (W)"),
    which are part of how the label is written."""
    s = " ".join(str(label).lower().split())
    return s.strip(" \t:.-–—*†‡")


def canonical_key(label: str) -> str:
    """The canonical field this row label names, or ``""``.

    Exact match on the normalised label only.  Substring matching was tried
    and rejected: "Enclosure Height" contains "enclosure", so a substring
    rule reads a panel's height into the NEMA-type field and cites the sheet
    while doing it -- a wrong value wearing a citation is worse than none.
    """
    n = _norm(label)
    if not n:
        return ""
    for syn, key in _INDEX:
        if n == syn:
            return key
    return ""


def field_kind(key: str) -> str:
    """``"length"`` / ``"number"`` / ``"text"``, or ``""`` if unknown."""
    row = FIELDS.get(key)
    return row[0] if row else ""

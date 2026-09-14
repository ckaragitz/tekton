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

import re
from typing import Dict, List, Tuple

__all__ = ["FIELDS", "SYNONYMS", "LENGTH_UNITS", "UNIT_SPELLINGS",
           "canonical_key", "canonical_key_and_unit", "field_kind",
           "unit_matches"]

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

#: declared unit -> the spellings a sheet writes it as, lowercased and with
#: trailing periods dropped.  A value whose stated unit is NOT one of these
#: is refused for that field rather than recorded, because the key carries
#: the unit: ``weight_lb = 90`` read off a row that said "90 kg" is a fact
#: about the document and a lie about the product, and the consumer reading
#: ``weight_lb`` by name has no way to see the difference (#688 review).
#:
#: Converting instead was considered and rejected here: a rating is not a
#: length, and silently turning 65 kA into 65000 A is the same class of
#: error one step further on.  The refusal names the unit, so a sheet in
#: other units is a one-line "add the spelling or the conversion" rather
#: than a wrong number nobody notices.
UNIT_SPELLINGS: Dict[str, set] = {
    "lb":  {"lb", "lbs", "lb.", "pound", "pounds", "#"},
    "A":   {"a", "amp", "amps", "ampere", "amperes", "aic"},
    "kA":  {"ka", "kaic", "kair", "ka ic", "kasym", "karms"},
    "kVA": {"kva"},
    "W":   {"w", "watt", "watts"},
    "lm":  {"lm", "lumen", "lumens"},
    "K":   {"k", "kelvin"},
    "Hz":  {"hz", "hertz", "cycles"},
    "C":   {"c", "°c", "degc", "deg c", "celsius", "centigrade"},
}


def unit_matches(declared: str, stated: str) -> bool:
    """Is ``stated`` an accepted spelling of the field's ``declared`` unit?

    An EMPTY ``stated`` matches: a sheet that tables ratings under a column
    header states the unit once, and refusing every unitless rating would
    gut the reader on real documents.  That case is recorded with a note
    instead -- unlike a length, where a bare number is refused outright,
    because "62" can be inches or millimetres and the two differ by 25x.
    """
    if not declared or not stated:
        return True
    s = " ".join(stated.lower().split()).rstrip(".")
    return s == declared.lower() or s in UNIT_SPELLINGS.get(declared, set())


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


#: a trailing parenthetical that is a UNIT and nothing else -- "Height (in)",
#: "Weight (lb)".  Stripped before the second match attempt below.
_TRAILING_UNIT = re.compile(r"\s*\(([^()]{1,8})\)\s*$")


def _known_unit(text: str) -> bool:
    t = text.strip().lower().rstrip(".")
    if t in LENGTH_UNITS:
        return True
    return any(t == d.lower() or t in sp
               for d, sp in UNIT_SPELLINGS.items())


def canonical_key(label: str) -> str:
    """The canonical field this row label names, or ``""``.

    Exact match on the normalised label only.  Substring matching was tried
    and rejected: "Enclosure Height" contains "enclosure", so a substring
    rule reads a panel's height into the NEMA-type field and cites the sheet
    while doing it -- a wrong value wearing a citation is worse than none.

    One narrow second attempt: a trailing parenthetical that is a **unit**
    is dropped, so "Height (in)" -- a row shape real sheets use constantly,
    with the unit hoisted into the label -- reaches ``height_in``.  Only a
    unit, never an arbitrary word: "Enclosure (Height)" must NOT become
    ``enclosure``, which is the same substring trap one step along.  The
    explicit synonyms still win first, so "Width (W)" keeps matching its own
    entry rather than being read as watts.
    """
    n = _norm(label)
    if not n:
        return ""
    for syn, key in _INDEX:
        if n == syn:
            return key
    key, _unit = _key_with_label_unit(n)
    return key


def _key_with_label_unit(n: str) -> Tuple[str, str]:
    m = _TRAILING_UNIT.search(n)
    if m and _known_unit(m.group(1)):
        stripped = n[:m.start()].strip()
        for syn, key in _INDEX:
            if stripped == syn:
                return key, m.group(1).strip()
    return "", ""


def canonical_key_and_unit(label: str) -> Tuple[str, str]:
    """``(key, unit the LABEL states)`` -- the unit is ``""`` unless the row
    label itself carries one, as in "Height (in)".

    This is a READING, not an inference, and the distinction is the whole
    reason it is a separate function: a unit taken from a COLUMN HEADER
    belongs to a different row and assuming it applies here is a guess about
    layout, which this module does not make.  A unit in *this row's own
    label* is this row stating it, and refusing to use it would throw away
    something the document says in as many words.
    """
    n = _norm(label)
    if not n:
        return "", ""
    for syn, key in _INDEX:
        if n == syn:
            return key, ""
    return _key_with_label_unit(n)


def field_kind(key: str) -> str:
    """``"length"`` / ``"number"`` / ``"text"``, or ``""`` if unknown."""
    row = FIELDS.get(key)
    return row[0] if row else ""

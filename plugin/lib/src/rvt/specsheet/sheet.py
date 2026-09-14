"""rvt.specsheet.sheet -- a user's spec sheet read into CITED values.

This is the layer #688 is actually about.  ``pdftext`` says what was drawn,
``layout`` says which cell it is in, ``vocab`` says what the row label means;
here those three become values that a family can be built from, each one
carrying the document, page and row it came from.

THE RULE THAT SHAPES EVERY DECISION BELOW.  S-2026-08-11-c forbids the model
supplying a manufacturer's dimensions as a ``fact``; S-2026-08-11-d makes the
user's own sheet the honest route to exactly those numbers.  So a value is
``fact``-tier **only** when this module read it off the page, and it carries
the citation that makes the claim checkable.  Everything else -- a row we
could not parse, a field the sheet never mentions, a unit nobody stated --
stays absent.  Absent becomes ``nominal`` later, in the archetype lane, where
it is labelled as generated.  Nothing here ever interpolates, rounds a range
into a number, or converts a rating.

WHAT IS A FACT AND WHAT IS AN INFERENCE, kept separate on purpose:

* **Fact**: the characters on the page, their page and their row.  Recorded
  verbatim in ``SheetValue.raw``.
* **Inference**: that the row labelled "Depth" is the family's depth, and
  that "5.75 in" means 5.75 inches.  Recorded as ``key`` and ``value`` -- and
  the literal label and raw text ride along, so the report shows the
  inference next to the fact it was drawn from and a human can see a wrong
  column at a glance (#688 DONE 4).

REFUSALS ARE BY NAME AND NEVER BLOCK DELIVERY (hard rule 1).  An unreadable
sheet, a sheet with no recognisable rows, a row whose value is not a
quantity: each produces one line saying so, and the caller still builds --
from an archetype, with the assumed values stated.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from . import vocab as V
from ._backend import FORCE_ENV, extract_pages
from .layout import Table, build_table
from .pdftext import PdfError, UnreadablePdf, read_pdf

__all__ = ["Quantity", "SheetValue", "ParsedSheet", "parse_quantity",
           "read_sheet"]


# ---------------------------------------------------------------------------
# quantities
# ---------------------------------------------------------------------------

#: a unit token: letters, degree/percent and the prime and quote marks sheets
#: use for feet and inches -- and NO DIGITS.  The digit ban is what makes
#: "480Y/277 V" refuse to parse as "480 <unit Y/277 V>": a designation is not
#: a quantity, and reading one as a number is how a 480V system becomes a
#: 480-inch panel.
_UNIT = r"""[A-Za-z°%/·.²³"'″”′’]*"""

_FEET_INCH = re.compile(
    r"""^\s*(?P<ft>\d+(?:\.\d+)?)\s*['′’]\s*[-–]?\s*
        (?P<in>\d+(?:\.\d+)?(?:\s*[-–\s]\s*\d+/\d+)?|\d+/\d+)?\s*
        ["″”]?\s*$""", re.X)

_MIXED = re.compile(r"^\s*(?P<whole>\d+)\s*[-–\s]\s*(?P<n>\d+)/(?P<d>\d+)\s*$")
_FRAC = re.compile(r"^\s*(?P<n>\d+)/(?P<d>\d+)\s*$")
_PLAIN = re.compile(r"^\s*(?P<num>[-+]?\d+(?:\.\d+)?)\s*$")

#: "62.0 in (1575 mm)" -- the metric twin every international sheet carries.
#: Taken as a NOTE, never averaged with the first: two statements of one
#: measurement that disagree are a thing to show a human, not to reconcile.
_PAREN = re.compile(r"^(?P<head>[^()]*?)\s*\((?P<tail>[^()]*)\)\s*$")


class Quantity:
    """A number read off the page, with the unit the page stated."""

    __slots__ = ("value", "unit", "raw", "note")

    def __init__(self, value: float, unit: str, raw: str, note: str = ""):
        self.value, self.unit, self.raw, self.note = value, unit, raw, note

    def __repr__(self) -> str:                                    # pragma: no cover
        return "Quantity(%g, %r)" % (self.value, self.unit)

    def unit_key(self) -> str:
        """The unit, normalised for lookup: lowercased, trailing periods
        dropped.  "in." and "In" are how sheets abbreviate inches roughly as
        often as "in", and treating them as unknown units made a perfectly
        clear dimension come back as "states no length unit"."""
        return self.unit.lower().rstrip(".")

    def in_inches(self) -> Optional[float]:
        """Inches, or ``None`` when the unit is not a length we know.

        A BARE number returns ``None`` on purpose.  A spec table often heads
        a column "Dimensions (in)" and leaves the rows unitless; taking the
        unit from a header is an inference about layout, and this module
        makes no inference that turns into a dimension.  The reader reports
        "no unit stated" and the caller asks or defaults visibly.
        """
        f = V.LENGTH_UNITS.get(self.unit_key())
        return self.value * f if f is not None else None


def _num(text: str) -> Optional[float]:
    """A bare number, a fraction or a mixed fraction -> float."""
    m = _MIXED.match(text)
    if m:
        return int(m.group("whole")) + int(m.group("n")) / int(m.group("d"))
    m = _FRAC.match(text)
    if m:
        return int(m.group("n")) / int(m.group("d"))
    m = _PLAIN.match(text)
    return float(m.group("num")) if m else None


def parse_quantity(text: str) -> Optional[Quantity]:
    """``"20-1/2 in"`` -> 20.5 in.  ``"480Y/277 V"`` -> ``None``.

    Returns ``None`` -- never a guess -- for anything that is not one number
    with at most one unit.  The caller reports the cell verbatim instead.
    """
    s = " ".join(str(text).split())
    if not s:
        return None
    note = ""
    m = _PAREN.match(s)
    if m and m.group("head").strip():
        note = "the sheet also states (%s)" % m.group("tail").strip()
        s = m.group("head").strip()

    fi = _FEET_INCH.match(s)
    if fi and fi.group("ft"):
        inches = float(fi.group("ft")) * 12.0
        rest = fi.group("in")
        if rest:
            v = _num(rest)
            if v is None:
                return None
            inches += v
        return Quantity(inches, "in", str(text).strip(), note)

    m = re.match(r"^(?P<head>.*?)\s*(?P<unit>%s)$" % _UNIT, s)
    head = m.group("head") if m else s
    unit = (m.group("unit") if m else "").strip()
    v = _num(head)
    if v is None:
        return None
    return Quantity(v, unit, str(text).strip(), note)


# ---------------------------------------------------------------------------
# cited values
# ---------------------------------------------------------------------------

class SheetValue:
    """One value read from the sheet, with everything needed to check it."""

    __slots__ = ("key", "label", "raw", "value", "unit", "page", "row",
                 "column", "note")

    def __init__(self, key: str, label: str, raw: str, value: Any, unit: str,
                 page: int, row: int, column: int, note: str = ""):
        self.key, self.label, self.raw = key, label, raw
        self.value, self.unit = value, unit
        self.page, self.row, self.column = page, row, column
        self.note = note

    def citation(self, document: str) -> str:
        """``"panel.pdf p2 r14 'Overall Height' = '62.0 in'"`` -- the string
        that goes into the fact's ``source`` and into the delivered report."""
        return "%s p%d r%d %r = %r" % (os.path.basename(document), self.page,
                                       self.row, self.label, self.raw)

    def as_json(self, document: str = "") -> Dict[str, Any]:
        return {"key": self.key, "label": self.label, "raw": self.raw,
                "value": self.value, "unit": self.unit,
                "page": self.page, "row": self.row, "column": self.column,
                "citation": self.citation(document) if document else "",
                "note": self.note}

    def __repr__(self) -> str:                                    # pragma: no cover
        return "SheetValue(%s=%r %s p%d r%d)" % (self.key, self.value,
                                                 self.unit, self.page, self.row)


class ParsedSheet:
    """Everything one PDF yielded, including what it did not."""

    __slots__ = ("path", "tables", "values", "unmapped", "notes", "unreadable")

    def __init__(self, path: str, tables: List[Table],
                 values: List[SheetValue], unmapped: List[Tuple[int, int, str]],
                 notes: List[str], unreadable: str = ""):
        self.path, self.tables, self.values = path, tables, values
        #: (page, row, text) for every row that named no field we know --
        #: shown, never dropped: "the sheet says this and we did not use it"
        self.unmapped = unmapped
        self.notes, self.unreadable = notes, unreadable

    @property
    def ok(self) -> bool:
        return not self.unreadable and bool(self.values)

    def by_key(self) -> Dict[str, SheetValue]:
        """First occurrence wins: a spec sheet states the headline dimension
        before the accessory tables that reuse the same words."""
        out: Dict[str, SheetValue] = {}
        for v in self.values:
            out.setdefault(v.key, v)
        return out

    def duplicates(self) -> Dict[str, List[SheetValue]]:
        """Keys the sheet states more than once, with every reading.

        Not an error -- a sheet legitimately tables several catalog numbers --
        but the caller must SEE it, because ``by_key`` silently picked one.
        """
        seen: Dict[str, List[SheetValue]] = {}
        for v in self.values:
            seen.setdefault(v.key, []).append(v)
        return {k: vs for k, vs in seen.items() if len(vs) > 1}

    def questions(self) -> List[str]:
        """What the sheet left undetermined, as questions for #684's lane.

        Deliberately only the residue: a question about something the sheet
        answered would be the reader failing to read.
        """
        qs: List[str] = []
        have = set(self.by_key())
        dups = self.duplicates()
        for key, readings in sorted(dups.items()):
            qs.append("the sheet states %s %d times (%s) -- which one?"
                      % (key, len(readings),
                         ", ".join("p%d r%d %r" % (v.page, v.row, v.raw)
                                   for v in readings[:4])))
        for key in ("height_in", "width_in", "depth_in"):
            if key not in have:
                qs.append("the sheet states no %s" % key)
        return qs

    def report(self, max_rows: int = 60) -> str:
        """The parsed table AS READ, then what was taken from it (DONE 4)."""
        out = ["spec sheet: %s" % self.path]
        if self.unreadable:
            out.append("UNREADABLE: %s" % self.unreadable)
        for t in self.tables:
            out.append("")
            out.append("--- page %d as read (%d rows, %d columns) ---"
                       % (t.page, len(t.rows), t.n_columns))
            if t.note:
                out.append("note: %s" % t.note)
            out.append(t.as_text(max_rows=max_rows))
        out.append("")
        out.append("--- values taken (every one cited) ---")
        if not self.values:
            out.append("(none)")
        for v in self.values:
            out.append("  %-14s = %-18s   <- %s"
                       % (v.key, "%s %s" % (v.value, v.unit) if v.unit
                          else v.value, v.citation(self.path)))
            if v.note:
                out.append("  %-14s   note: %s" % ("", v.note))
        if self.unmapped:
            out.append("")
            out.append("--- rows read but NOT used (%d) ---" % len(self.unmapped))
            for page, row, text in self.unmapped[:max_rows]:
                out.append("  p%d r%d  %s" % (page, row, text[:100]))
        for n in self.notes:
            out.append("note: %s" % n)
        return "\n".join(out)

    def as_json(self) -> Dict[str, Any]:
        return {"path": self.path,
                "unreadable": self.unreadable,
                "values": [v.as_json(self.path) for v in self.values],
                "unmapped_rows": [{"page": p, "row": r, "text": t}
                                  for p, r, t in self.unmapped],
                "duplicates": {k: [v.as_json(self.path) for v in vs]
                               for k, vs in self.duplicates().items()},
                "questions": self.questions(),
                "tables": [t.as_json() for t in self.tables],
                "notes": list(self.notes)}


# ---------------------------------------------------------------------------
# the reader
# ---------------------------------------------------------------------------

def _value_cells(row) -> List:
    """The cells to the RIGHT of the label cell, in order.

    A spec row is ``label | value`` or ``label | value | value``; the first
    non-empty cell after the label is the reading, and the rest are noted.
    """
    return row.cells[1:]


class _Split:
    """A label/value pair recovered from ONE cell by its colon."""

    __slots__ = ("text", "column")

    def __init__(self, text: str, column: int):
        self.text, self.column = text, column


def _colon_split(row) -> Optional[Tuple[str, List[_Split]]]:
    """``"Catalog Number: PW-400-42"`` in one cell -> label + value.

    Identity lines are typeset as running text, not as a table row, so the
    layout layer correctly reports ONE cell -- there is no column gap to
    find.  Splitting on the first colon recovers the pair.

    This is an INFERENCE and is narrow on purpose: only a single-cell row,
    only the FIRST colon, and only when what precedes it already names a
    field we know.  Without that last condition "Note: see page 4" becomes a
    labelled value, and a sheet's prose starts arriving as facts.
    """
    if len(row.cells) != 1 or ":" not in row.cells[0].text:
        return None
    head, _, tail = row.cells[0].text.partition(":")
    head, tail = head.strip(), tail.strip()
    if not tail or not V.canonical_key(head):
        return None
    return head, [_Split(tail, row.cells[0].column)]


def _read_row(row) -> Tuple[Optional[SheetValue], str]:
    """One layout row -> a cited value, or ``(None, why not)``."""
    split = _colon_split(row)
    if split is not None:
        label, cells = split
    elif len(row.cells) < 2:
        return None, "no value cell"
    else:
        label, cells = row.cells[0].text, _value_cells(row)
    key, label_unit = V.canonical_key_and_unit(label)
    if not key:
        return None, "label %r names no field we know" % label
    kind = V.field_kind(key)
    raw = cells[0].text
    extra = [c.text for c in cells[1:] if c.text]
    note = ("the row also holds %s" % ", ".join(repr(e) for e in extra)) if extra else ""

    if kind == "text":
        return SheetValue(key, label, raw, raw, "", row.page, row.index,
                          cells[0].column, note), ""

    q = parse_quantity(raw)
    if q is None:
        return None, ("%r is not a single quantity, so %s is left unset"
                      % (raw, key))
    if q.note:
        note = "; ".join(x for x in (note, q.note) if x)

    if kind == "length":
        inches = q.in_inches()
        if inches is None and label_unit:
            # the ROW'S OWN LABEL states the unit ("Height (in)"), which is
            # this row saying it -- a reading, not the column-header guess
            # refused below
            probe = Quantity(q.value, label_unit, q.raw, q.note)
            inches = probe.in_inches()
            if inches is not None:
                note = "; ".join(x for x in (
                    note, "unit %r read from the row's own label" % label_unit)
                    if x)
                q = probe
        if inches is None:
            return None, ("%r states no length unit, so %s is left unset "
                          "(a unit taken from a column header would be an "
                          "inference, not a reading)" % (raw, key))
        if inches <= 0.0:
            # never a real dimension, and a zero or negative one builds a
            # degenerate solid that our validator still calls VALID
            return None, ("%r is not a positive length, so %s is left unset"
                          % (raw, key))
        if q.unit_key() not in ("in", "inch", "inches", '"', "”", "″"):
            note = "; ".join(x for x in (note, "converted from %s" % q.unit) if x)
        return SheetValue(key, label, raw, round(inches, 6), "in", row.page,
                          row.index, cells[0].column, note), ""

    declared = V.FIELDS[key][1]
    if not q.unit and label_unit:
        q = Quantity(q.value, label_unit, q.raw, q.note)
        note = "; ".join(x for x in (
            note, "unit %r read from the row's own label" % label_unit) if x)
    if not V.unit_matches(declared, q.unit):
        return None, ("%r states %s, but %s is declared in %s and nothing "
                      "here converts a rating; add the spelling to "
                      "vocab.UNIT_SPELLINGS or a conversion, but do not "
                      "assume" % (raw, q.unit, key, declared))
    if declared and not q.unit:
        note = "; ".join(x for x in (
            note, "the sheet states no unit for this row; %s is declared in "
                  "%s" % (key, declared)) if x)
    return SheetValue(key, label, raw, q.value, q.unit or declared, row.page,
                      row.index, cells[0].column, note), ""


def _second_opinion(path: str, backend: str, max_pages: int) -> str:
    """When the chosen backend read nothing, say whether the OTHER one would.

    The result is never SWAPPED for the second opinion -- that would make the
    same document read differently depending on what happens to be installed,
    which is the whole reason ``_backend`` picks one and stays with it.  This
    only turns "unreadable" into "unreadable HERE, and here is the switch",
    which is the difference between a dead end and one environment variable.
    """
    if backend == "stdlib":
        return ""
    try:
        other = read_pdf(path, max_pages=max_pages)
    except (UnreadablePdf, PdfError):
        return ""
    if not any(p.has_text for p in other):
        return ""
    return ("the built-in stdlib reader DOES find text on %d of its %d pages "
            "-- re-run with %s=1 to use it"
            % (sum(1 for p in other if p.has_text), len(other), FORCE_ENV))


def read_sheet(path: str, max_pages: int = 64, **layout_params) -> ParsedSheet:
    """Read ``path`` into cited values.  Never raises for a bad document.

    An unreadable sheet comes back as a :class:`ParsedSheet` whose
    ``unreadable`` says why, so the caller can report the reason AND still
    deliver an archetype family (hard rule 1).  Only a caller bug -- a
    missing file -- raises.
    """
    try:
        pages, backend = extract_pages(path, max_pages=max_pages)
    except UnreadablePdf as exc:
        return ParsedSheet(path, [], [], [], [], str(exc))
    except PdfError as exc:
        return ParsedSheet(path, [], [], [], [], str(exc))

    tables = [build_table(p, **layout_params) for p in pages]
    values: List[SheetValue] = []
    unmapped: List[Tuple[int, int, str]] = []
    notes: List[str] = []
    for t in tables:
        if t.note:
            notes.append("page %d: %s" % (t.page, t.note))
        for row in t.rows:
            sv, why = _read_row(row)
            if sv is not None:
                values.append(sv)
            else:
                unmapped.append((t.page, row.index, row.text))
                if why and not why.startswith("label ") and why != "no value cell":
                    notes.append("p%d r%d: %s" % (t.page, row.index, why))

    notes.append("read with the %s PDF backend" % backend)
    unreadable = ""
    if not pages:
        # NOT the same as "the pages are blank", and saying so matters: this
        # reason sends a user looking for OCR, and the cause is the backend.
        # Found A/B-ing the two backends on a stale-xref file (#688): the
        # optional extra trusts the xref, returns ZERO pages, and the
        # image-only message was the one that came out.
        unreadable = "the %s backend found no pages in this PDF" % backend
        second = _second_opinion(path, backend, max_pages)
        if second:
            unreadable += "; " + second
    elif not any(p.has_text for p in pages):
        unreadable = ("no page in this PDF draws any text -- it is a scanned "
                      "or image-only sheet and this reader does no OCR "
                      "(%s backend)" % backend)
        second = _second_opinion(path, backend, max_pages)
        if second:
            unreadable += "; " + second
    elif not values:
        notes.append("no row in this sheet named a field the engine knows; "
                     "the rows read are listed above")
    return ParsedSheet(path, tables, values, unmapped, notes, unreadable)

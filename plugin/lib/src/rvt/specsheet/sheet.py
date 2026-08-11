"""rvt.specsheet.sheet -- a user-supplied spec sheet -> a cited FactSheet.

THE POINT OF THIS LANE (steer #685's line).  Model knowledge may supply
taxonomy and standard practice, but never a manufacturer's dimensions as a
``fact``; recalled numbers written into ``famgen/facts/**`` would be
fabricated catalog data.  A document the USER supplies is a *source*, so
this is the honest route to real member data -- and the whole value of it
rests on the provenance being exact.  Therefore:

* every value taken from the sheet is a :class:`~rvt.famgen.factory.Fact`
  of kind ``fact`` whose ``source`` is a full :class:`~rvt.specsheet.table.Citation`
  -- document, page, and the row/cell text it was read from;
* a field the sheet does not state gets **no Fact at all** (blank), and the
  reason is recorded in :attr:`SheetReading.blanks` so the report can say
  *why* it is blank rather than leaving a silent hole;
* a unit conversion we perform is ``derived``, never ``fact``: the stated
  figure stays the fact and our arithmetic is labelled as ours;
* nothing is interpolated and nothing is rounded into a fact.

IDENTITY.  This is the one lane where a generated family may wear a real
manufacturer / model / part number on its identity parameters, because the
user supplied the document that says so.  :attr:`SheetReading.identity`
carries those three as ordinary cited facts, and
:meth:`SheetReading.backing_document` names the document that backs the
claim -- the report must print it wherever the claim appears.

TERRITORY (specsheet stream): see :mod:`rvt.specsheet.pdftext`.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Dict, List, Optional, Sequence, Tuple, Union

from .pdftext import Document, PdfTextError, read_pdf
from .table import Citation, Row, render_table, rows_from_page
from .values import Measure, Refusal, parse_measure, to_inches

__all__ = [
    "SheetError", "FIELD_LABELS", "IDENTITY_LABELS", "SheetReading",
    "read_sheet", "build_fact_sheet",
]


class SheetError(ValueError):
    """The sheet cannot be read at all.  The message is ONE clear line --
    hard rule 1: the caller still delivers a file where an archetype can
    stand in, and says this instead of raising."""


#: spec-sheet row labels -> the field name the factory uses.  Matching is
#: case-insensitive on the label cell, after punctuation is stripped.  Only
#: labels listed here become facts; every other row stays visible in the
#: parsed table but contributes nothing, so an unrecognised sheet under-
#: reports rather than mis-reports.
FIELD_LABELS: Dict[str, str] = {
    "length": "length_in", "overall length": "length_in", "nominal length": "length_in",
    "width": "width_in", "overall width": "width_in", "nominal width": "width_in",
    "height": "height_in", "overall height": "height_in",
    "depth": "depth_in", "overall depth": "depth_in",
    "diameter": "diameter_in",
    "weight": "weight_lb", "shipping weight": "weight_lb",
    "operating weight": "weight_lb",
    "input power": "input_power_w", "wattage": "input_power_w",
    "power": "input_power_w", "input watts": "input_power_w",
    "voltage": "voltage_v", "input voltage": "voltage_v",
    "current": "current_a", "input current": "current_a",
    "frequency": "frequency_hz",
    "lumens": "luminous_flux_lm", "luminous flux": "luminous_flux_lm",
    "delivered lumens": "luminous_flux_lm",
    "cct": "cct_k", "color temperature": "cct_k",
    "correlated color temperature": "cct_k",
    "cri": "cri", "color rendering index": "cri",
    "kva": "kva", "rating": "rating",
}

#: identity labels -- the manufacturer claim this lane is allowed to carry
IDENTITY_LABELS: Dict[str, str] = {
    "manufacturer": "manufacturer", "brand": "manufacturer",
    "model": "model", "model number": "model", "model no": "model",
    "series": "model",
    "catalog number": "part_number", "catalog no": "part_number",
    "cat no": "part_number", "part number": "part_number",
    "part no": "part_number", "ordering code": "part_number",
    "sku": "part_number",
}

_LABEL_CLEAN = re.compile(r"[\s:.\-_]+")


def _norm_label(text: str) -> str:
    return _LABEL_CLEAN.sub(" ", text.strip().lower()).strip()


@dataclass
class SheetReading:
    """Everything read from one spec sheet, and everything refused."""
    document: str                                   # basename, as cited
    path: str = ""
    backend: str = "pdftext"
    rows: List[Row] = dc_field(default_factory=list)
    #: field -> (Measure, Citation) taken as a fact
    measures: Dict[str, Tuple[Measure, Citation]] = dc_field(default_factory=dict)
    #: field -> (text, Citation) for the identity claim
    identity: Dict[str, Tuple[str, Citation]] = dc_field(default_factory=dict)
    #: field or label -> why no value was taken
    blanks: Dict[str, Refusal] = dc_field(default_factory=dict)
    #: pages with no text layer at all (scanned images)
    scanned_pages: List[int] = dc_field(default_factory=list)
    notes: List[str] = dc_field(default_factory=list)

    @property
    def any_facts(self) -> bool:
        return bool(self.measures or self.identity)

    def backing_document(self) -> str:
        """The document that backs any manufacturer claim from this sheet."""
        return self.document

    def parsed_table(self, max_rows: int = 0) -> str:
        """The table AS READ -- printed in the report before anything is
        trusted, so a wrong column is visible rather than silently built."""
        return render_table(self.rows, self.document, max_rows=max_rows)

    def as_json(self) -> dict:
        return {
            "document": self.document,
            "backend": self.backend,
            "rows_parsed": len(self.rows),
            "scanned_pages": list(self.scanned_pages),
            "measures": {k: {**m.as_json(), "citation": c.as_json()}
                         for k, (m, c) in sorted(self.measures.items())},
            "identity": {k: {"value": v, "citation": c.as_json()}
                         for k, (v, c) in sorted(self.identity.items())},
            "blanks": {k: r.as_json() for k, r in sorted(self.blanks.items())},
            "notes": list(self.notes),
        }


def _pairs(row: Row) -> List[Tuple[str, str]]:
    """(label, value) candidates from one row.

    A two-cell row is one pair.  A wider row is read as alternating
    label/value pairs, which is how spec sheets lay out two-column blocks.
    A single-cell row yields nothing -- we do not guess that a lone cell is
    a value for the label above it.
    """
    cells = [c.text for c in row.cells]
    if len(cells) < 2:
        return []
    if len(cells) == 2:
        return [(cells[0], cells[1])]
    out: List[Tuple[str, str]] = []
    for i in range(0, len(cells) - 1, 2):
        out.append((cells[i], cells[i + 1]))
    return out


def read_sheet(path: str, max_pages: int = 0) -> SheetReading:
    """Read a spec sheet into cited facts.

    Raises :class:`SheetError` -- one clear line -- when the document cannot
    be read at all.  A sheet that reads but yields nothing is NOT an error:
    it comes back with ``any_facts`` False and its reasons in ``blanks``.
    """
    from ._backend import read_document, backend_name

    doc_name = os.path.basename(path) or path
    try:
        doc: Document = read_document(path)
    except PdfTextError as exc:
        raise SheetError(str(exc)) from exc
    except OSError as exc:
        raise SheetError(f"cannot read {doc_name}: {exc}") from exc

    reading = SheetReading(document=doc_name, path=path,
                           backend=backend_name())
    pages = doc.pages if max_pages <= 0 else doc.pages[:max_pages]
    reading.scanned_pages = [p.number for p in pages if p.scanned]

    for page in pages:
        reading.rows.extend(rows_from_page(page))

    if not reading.rows:
        if reading.scanned_pages:
            reading.notes.append(
                f"{doc_name}: no text layer on "
                f"{len(reading.scanned_pages)} page(s) -- the sheet looks "
                f"scanned; this reader does not OCR")
        else:
            reading.notes.append(f"{doc_name}: no text rows could be parsed")
        return reading

    for row in reading.rows:
        for label, value in _pairs(row):
            key = _norm_label(label)
            cell = next((c for c in row.cells if c.text == value), None)
            cit = row.citation(doc_name, cell)

            if key in IDENTITY_LABELS:
                field = IDENTITY_LABELS[key]
                text = value.strip()
                if text and "�" not in text:
                    reading.identity.setdefault(field, (text, cit))
                else:
                    reading.blanks.setdefault(
                        field, Refusal("identity cell could not be decoded",
                                       value))
                continue

            if key not in FIELD_LABELS:
                continue
            field = FIELD_LABELS[key]
            if field in reading.measures:
                continue                      # first statement on the sheet wins
            parsed = parse_measure(value)
            if isinstance(parsed, Refusal):
                reading.blanks.setdefault(field, parsed)
            else:
                reading.measures[field] = (parsed, cit)
                reading.blanks.pop(field, None)

    if reading.scanned_pages:
        reading.notes.append(
            f"{doc_name}: page(s) {', '.join(str(p) for p in reading.scanned_pages)} "
            f"have no text layer and were not read")
    return reading


def build_fact_sheet(reading: SheetReading, subject: str = ""):
    """Turn a :class:`SheetReading` into a ``famgen`` ``FactSheet``.

    Every stated value lands as kind ``fact`` with its citation as the
    source.  A length is ALSO offered in inches as a separate ``derived``
    entry (``<field>_derived_in``) when the sheet stated another unit --
    the stated figure stays the fact, our conversion is labelled ours.
    Fields the sheet did not state are absent, with the reason in a note.
    """
    from rvt.famgen.factory import FactSheet

    fs = FactSheet(subject=subject or reading.document,
                   catalog="", variant="")

    for field, (measure, cit) in sorted(reading.measures.items()):
        fs.set(field, measure.value, kind="fact", source=str(cit),
               note=(f"stated as {measure.raw!r}"
                     + (f" [{measure.unit}]" if measure.unit else "")))
        if measure.unit and measure.unit not in ("in",):
            conv = to_inches(measure)
            if conv is not None:
                fs.set(f"{field}_derived_in", conv.value, kind="derived",
                       source=str(cit),
                       note=f"converted by us from {measure.raw!r} "
                            f"({measure.unit} -> in); the stated figure is "
                            f"the fact")

    for field, (text, cit) in sorted(reading.identity.items()):
        fs.set(field, text, kind="fact", source=str(cit),
               note=f"manufacturer claim backed by {reading.document}")

    for field, refusal in sorted(reading.blanks.items()):
        fs.notes.append(f"{field}: left blank -- {refusal}")
    fs.notes.extend(reading.notes)
    return fs

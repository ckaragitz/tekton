"""rvt.specsheet -- the spec-sheet INPUT lane: a user's document -> cited facts.

Steer #685 drew the line this package exists to respect: model knowledge may
supply taxonomy and standard practice, but NEVER a manufacturer's dimensions
as a ``fact``.  Recalled numbers written into ``famgen/facts/**`` would be
fabricated catalog data at scale.  A spec sheet the USER supplies is a
*source*, so this lane is the honest route to real member data -- and it is
the ONE lane where a generated family may wear a real manufacturer, model or
part number on its identity parameters, because the user supplied the
document that says so.

The four modules, in the order the data flows:

* :mod:`rvt.specsheet.pdftext` -- stdlib-only text-layer PDF reader
  (positioned fragments per page).  No OCR, no glyph guessing, no
  decryption; each of those is reported, never guessed around.
* :mod:`rvt.specsheet._backend` -- picks the optional ``pdfplumber`` wheel
  (``pip install -e ".[pdf]"``) when installed, the stdlib reader otherwise.
  No new REQUIRED runtime dependency; ``olefile`` stays the only one.
* :mod:`rvt.specsheet.table` -- fragments -> rows and cells, each carrying
  the :class:`~rvt.specsheet.table.Citation` (document, page, row/cell text)
  that every extracted value is stamped with.
* :mod:`rvt.specsheet.values` -- reads ONE number from a cell or refuses
  with a reason.  Ranges, lists, qualified figures and prose placeholders
  are refused, never silently resolved to a number.
* :mod:`rvt.specsheet.sheet` -- assembles the cited
  :class:`~rvt.famgen.factory.FactSheet`, and renders the parsed table AS
  READ so a wrong column is visible before anything is built from it.

Hard rule 1 holds throughout: an unreadable sheet is ONE clear line
(:class:`~rvt.specsheet.sheet.SheetError`), and where an archetype can stand
in the file is still delivered.
"""
from __future__ import annotations

from ._backend import (BACKEND_DIST, FORCE_ENV, backend_name,
                       pdf_backend_installed, read_document,
                       using_stdlib_reader)
from .pdftext import (PDFTEXT_VERSION, Document, Fragment, Page, PdfTextError,
                      read_pdf)
from .sheet import (FIELD_LABELS, IDENTITY_LABELS, SheetError, SheetReading,
                    build_fact_sheet, read_sheet)
from .table import Cell, Citation, Row, render_table, rows_from_page
from .values import Measure, Refusal, parse_measure, to_inches

__all__ = [
    # backend selection
    "BACKEND_DIST", "FORCE_ENV", "backend_name", "pdf_backend_installed",
    "read_document", "using_stdlib_reader",
    # pdf reading
    "PDFTEXT_VERSION", "Document", "Fragment", "Page", "PdfTextError", "read_pdf",
    # tables and citations
    "Cell", "Citation", "Row", "render_table", "rows_from_page",
    # values
    "Measure", "Refusal", "parse_measure", "to_inches",
    # the lane
    "FIELD_LABELS", "IDENTITY_LABELS", "SheetError", "SheetReading",
    "build_fact_sheet", "read_sheet",
]

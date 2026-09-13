"""rvt.specsheet -- read a user-supplied spec sheet (PDF) as a SOURCE.

#688 / steer #687 (S-2026-08-11-d): a spec sheet the user hands us is the
honest route to a manufacturer's real dimensions, because they supplied the
document that states them -- the one thing S-2026-08-11-c forbids the model
to recall from memory.  Values read here are ``fact``-tier and cite the file,
page and row; anything the sheet does not state stays absent and becomes a
labelled ``nominal`` in the archetype lane, never an interpolation.

Four layers, deliberately separate so each can be checked on its own:

``pdftext``  what was drawn and WHERE -- stdlib only (zlib), no new runtime
             dependency, exactly as ``rvt.ifc.steplite`` is for IFC.
``layout``   positions -> rows, cells and columns: the inference, rendered
             so a human can see a wrong column before anything is built.
``vocab``    what row labels mean, as data tables (#685: breadth is data).
``sheet``    the two joined into cited values, with honest named refusals.

No manufacturer document is stored in this repo and none is read from any
installed product (hard rules 2 and 3); the only input is the file the user
points at.
"""
from __future__ import annotations

from .pdftext import PdfError, UnreadablePdf, read_pdf
from .sheet import ParsedSheet, SheetValue, parse_quantity, read_sheet

__all__ = ["PdfError", "UnreadablePdf", "read_pdf",
           "ParsedSheet", "SheetValue", "parse_quantity", "read_sheet"]

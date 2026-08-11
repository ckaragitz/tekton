"""rvt.specsheet.table -- positioned text fragments -> rows, cells, citations.

The spec-sheet lane's contract is that **every extracted value can be shown
back to the user as the row it came from**.  This module is where that
citation is minted: :func:`rows_from_page` groups a page's fragments into
:class:`Row` objects by their baseline ``y`` and orders the cells by ``x``,
and every :class:`Cell` keeps the exact text the PDF drew.

LAYOUT IS A HEURISTIC; VALUES ARE NOT.  Grouping fragments into rows and
cells uses tolerances (baseline distance, an estimated text width, a gap
threshold).  Those tolerances decide *where a piece of text is placed in
the table* -- they never rewrite, round, merge or synthesise the text
itself.  A mis-grouped sheet therefore shows up as a visibly wrong table in
the report (:func:`render_table`), which is the point: the reader is asked
to check the parse, not to trust it.  This is why the report prints the
table as read before any fact is drawn from it.

TERRITORY (specsheet stream): see :mod:`rvt.specsheet.pdftext`.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .pdftext import Fragment, Page

__all__ = [
    "Citation", "Cell", "Row", "rows_from_page", "render_table",
    "DEFAULT_BASELINE_TOL", "DEFAULT_GAP_FACTOR", "AVG_CHAR_WIDTH",
]

#: fragments whose baselines differ by less than this many points are one row
DEFAULT_BASELINE_TOL = 2.5

#: a horizontal gap wider than ``factor * font size`` starts a new cell
DEFAULT_GAP_FACTOR = 0.6

#: mean glyph advance as a fraction of font size, used ONLY to estimate where
#: a run of text ends so the gap to the next run can be measured.  A pure
#: layout estimate: it never changes a character of the extracted text.
AVG_CHAR_WIDTH = 0.5


@dataclass(frozen=True)
class Citation:
    """Where one extracted value was read from -- file, page, and the text.

    This is the unit the ``FactSheet`` stores as a fact's source and the
    report prints.  ``row_text`` is the whole row as parsed; ``cell_text``
    is the single cell the value came from.  Both are the PDF's own
    characters, never normalised.
    """
    document: str                 # the file as the user named it (basename)
    page: int                     # 1-based
    row_text: str
    cell_text: str = ""
    row_index: int = -1           # 0-based position within the page

    def as_json(self) -> dict:
        return {"document": self.document, "page": self.page,
                "row": self.row_text, "cell": self.cell_text,
                "row_index": self.row_index}

    def __str__(self) -> str:
        where = f"{self.document} p.{self.page}"
        if self.cell_text and self.cell_text != self.row_text:
            return f'{where}: "{self.cell_text}" in row "{self.row_text}"'
        return f'{where}: "{self.row_text}"'


@dataclass(frozen=True)
class Cell:
    """One cell: the text drawn, and where on the page it started."""
    text: str
    x: float
    undecodable: bool = False


@dataclass
class Row:
    """One parsed row of a page, ordered left to right."""
    page: int
    index: int
    y: float
    cells: List[Cell] = dc_field(default_factory=list)

    @property
    def text(self) -> str:
        """The row as a human reads it, cells separated by two spaces."""
        return "  ".join(c.text for c in self.cells).strip()

    @property
    def undecodable(self) -> bool:
        return any(c.undecodable for c in self.cells)

    def citation(self, document: str, cell: Optional[Cell] = None) -> Citation:
        return Citation(document=document, page=self.page, row_text=self.text,
                        cell_text=(cell.text if cell is not None else ""),
                        row_index=self.index)


def _estimated_end(f: Fragment) -> float:
    size = f.size if f.size > 0 else 10.0
    return f.x + len(f.text) * size * AVG_CHAR_WIDTH


def rows_from_page(page: Page,
                   baseline_tol: float = DEFAULT_BASELINE_TOL,
                   gap_factor: float = DEFAULT_GAP_FACTOR) -> List[Row]:
    """Group one page's fragments into rows of cells, top of page first.

    Fragments sharing a baseline (within ``baseline_tol`` points) are one
    row; within a row, a horizontal gap wider than ``gap_factor`` times the
    font size starts a new cell.  Returns ``[]`` for a page with no text
    layer -- the caller distinguishes that from "the sheet said nothing"
    via :attr:`Page.scanned`.
    """
    if not page.fragments:
        return []

    # bucket by baseline, descending y (PDF origin is bottom-left, so the
    # top of the page is the LARGEST y)
    buckets: List[Tuple[float, List[Fragment]]] = []
    for f in sorted(page.fragments, key=lambda f: (-f.y, f.x)):
        for i, (y, group) in enumerate(buckets):
            if abs(f.y - y) <= baseline_tol:
                group.append(f)
                break
        else:
            buckets.append((f.y, [f]))

    rows: List[Row] = []
    for idx, (y, group) in enumerate(buckets):
        group.sort(key=lambda f: f.x)
        cells: List[Cell] = []
        cur_text: List[str] = []
        cur_x = group[0].x
        cur_bad = False
        prev: Optional[Fragment] = None
        for f in group:
            if prev is not None:
                size = f.size if f.size > 0 else 10.0
                gap = f.x - _estimated_end(prev)
                if gap > gap_factor * size:
                    cells.append(Cell("".join(cur_text).strip(), cur_x, cur_bad))
                    cur_text, cur_x, cur_bad = [], f.x, False
            cur_text.append(f.text)
            cur_bad = cur_bad or f.undecodable
            prev = f
        if cur_text:
            cells.append(Cell("".join(cur_text).strip(), cur_x, cur_bad))
        cells = [c for c in cells if c.text]
        if cells:
            rows.append(Row(page=page.number, index=idx, y=y, cells=cells))
    return rows


def render_table(rows: Sequence[Row], document: str = "",
                 max_rows: int = 0) -> str:
    """The parsed table AS READ, for the delivered report.

    Printed before any value is trusted, so a wrong column is visible rather
    than silently built into a family.  ``max_rows`` 0 means every row; when
    a limit truncates, the omission is stated in the output rather than left
    to look like the end of the sheet.
    """
    if not rows:
        return "(no rows parsed)"
    shown = list(rows) if max_rows <= 0 else list(rows[:max_rows])
    width = max(len(str(r.page)) for r in shown)
    out: List[str] = []
    if document:
        out.append(f"parsed from {document}")
    for r in shown:
        mark = " !" if r.undecodable else ""
        out.append(f"p{str(r.page).rjust(width)} r{r.index:<3d}{mark} | "
                   + " | ".join(c.text for c in r.cells))
    if max_rows > 0 and len(rows) > max_rows:
        out.append(f"... {len(rows) - max_rows} further row(s) not shown "
                   f"(of {len(rows)} parsed)")
    return "\n".join(out)

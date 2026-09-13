"""rvt.specsheet.layout -- positioned text -> rows, cells and columns.

WHY THIS IS A SEPARATE LAYER.  ``pdftext`` answers "what was drawn, where".
That is a fact about the file.  *Which cell a number belongs to* is an
INFERENCE from those coordinates, and inferences must be inspectable: #688
DONE 4 requires the parsed table to be shown before it is trusted, so the
structure this module builds is a first-class object with its own rendering,
not a transient step inside a parser.

THE THREE DECISIONS, each a number a reader can argue with (so each is a
named parameter with its default written down, never a literal buried in a
loop):

* **A line** is the set of runs sharing a baseline within ``y_tol`` (default
  0.45 em of the tallest run on it).  Subscripts and a slightly-off
  superscript join their line; a genuinely lower line does not.
* **Two runs are one cell** when the horizontal gap between them is under
  ``cell_em`` (default 1.6 em).  Under ``space_em`` (0.18 em) they are one
  WORD and are joined with no space -- the kerned-pair case, where a producer
  emits ``(V) (oltage)``.  In between, one space.
* **Two cells are one column** when their left edges agree within ``col_tol``
  (default 0.8 em).  Left edges, not centres: spec sheets are left-aligned
  and a centred number's centre says nothing about its column.

WHAT THIS DOES NOT DO, stated rather than discovered later:

* no spanning-cell detection -- a title drawn across a table is simply a row
  with one cell, which is what it looks like;
* no multi-line cell joining -- a value wrapped onto two lines is two rows,
  and the reader above decides whether to join them;
* no rotated text -- a run drawn sideways still gets an x/y, so it lands in
  some row; the em-based tolerances make it unlikely to capture a real cell,
  but nothing here detects it.  A sheet whose table is rotated is a case for
  the optional ``[pdf]`` extra, and the reader says so.
* nothing is dropped.  Every glyph reaches exactly one cell, so the rendered
  table can be compared against the page by eye and anything missing is a
  bug here, not a filter.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from .pdftext import Glyph, Page

__all__ = ["Cell", "Row", "Table", "build_table", "DEFAULTS"]

#: the tunables above, in one place so a caller can state what it changed
DEFAULTS: Dict[str, float] = {
    "y_tol_em": 0.45,
    "space_em": 0.18,
    "cell_em": 1.6,
    "col_tol_em": 0.8,
}


class Cell:
    """One table cell as read: its text and the x span it occupies."""

    __slots__ = ("text", "x0", "x1", "column")

    def __init__(self, text: str, x0: float, x1: float, column: int = -1):
        self.text, self.x0, self.x1, self.column = text, x0, x1, column

    def __repr__(self) -> str:                                    # pragma: no cover
        return "Cell(%r, x=%.1f..%.1f, col=%d)" % (
            self.text, self.x0, self.x1, self.column)


class Row:
    """One line of the page: its baseline, its cells, and where it came from.

    ``page`` and ``index`` are carried because a value read out of this row
    has to CITE it (#688 DONE 3) -- a citation assembled later from whatever
    is in scope is how a report ends up naming the wrong page.
    """

    __slots__ = ("page", "index", "y", "size", "cells")

    def __init__(self, page: int, index: int, y: float, size: float,
                 cells: List[Cell]):
        self.page, self.index, self.y, self.size, self.cells = \
            page, index, y, size, cells

    @property
    def text(self) -> str:
        return "  ".join(c.text for c in self.cells)

    def cell_texts(self) -> List[str]:
        return [c.text for c in self.cells]

    def __repr__(self) -> str:                                    # pragma: no cover
        return "Row(p%d #%d y=%.1f %r)" % (self.page, self.index, self.y,
                                           self.cell_texts())


class Table:
    """Every row of one page, with a column grid inferred across them."""

    __slots__ = ("page", "rows", "columns", "note", "params")

    def __init__(self, page: int, rows: List[Row], columns: List[float],
                 note: str = "", params: Optional[Dict[str, float]] = None):
        self.page, self.rows, self.columns = page, rows, columns
        self.note = note
        self.params = dict(params or DEFAULTS)

    @property
    def n_columns(self) -> int:
        return len(self.columns)

    def column_grid(self) -> List[List[str]]:
        """``rows x columns`` of text, blank where a row has no cell there.

        This is the shape a human checks: a value that landed one column too
        far right is obvious here and invisible in a flat string.
        """
        grid = []
        for row in self.rows:
            line = [""] * max(1, len(self.columns))
            for c in row.cells:
                if 0 <= c.column < len(line):
                    line[c.column] = (line[c.column] + " " + c.text).strip() \
                        if line[c.column] else c.text
            grid.append(line)
        return grid

    def as_text(self, max_rows: int = 200, width: int = 34) -> str:
        """The parsed table as read -- #688 DONE 4's "show it before you
        trust it".  Column-aligned, because that is the whole question."""
        out = []
        for row, line in zip(self.rows[:max_rows], self.column_grid()[:max_rows]):
            cells = [(c[:width - 1] + "…") if len(c) > width else c
                     for c in line]
            out.append("p%d r%-3d | %s" % (self.page, row.index,
                                           " | ".join(c.ljust(width) for c in cells).rstrip()))
        if len(self.rows) > max_rows:
            out.append("... %d more rows" % (len(self.rows) - max_rows))
        return "\n".join(out)

    def as_json(self) -> Dict[str, Any]:
        return {"page": self.page,
                "columns": [round(x, 2) for x in self.columns],
                "rows": [{"index": r.index, "y": round(r.y, 2),
                          "cells": r.cell_texts()} for r in self.rows],
                "note": self.note,
                "params": dict(self.params)}


def _lines(glyphs: Sequence[Glyph], y_tol_em: float) -> List[List[Glyph]]:
    """Group runs onto baselines, top of page first."""
    out: List[List[Glyph]] = []
    for g in sorted(glyphs, key=lambda g: (-g.y, g.x)):
        if out:
            cur = out[-1]
            tol = y_tol_em * max(max(x.size for x in cur), g.size, 1.0)
            if abs(cur[0].y - g.y) <= tol:
                cur.append(g)
                continue
        out.append([g])
    return out


def _cells(line: Sequence[Glyph], space_em: float, cell_em: float) -> List[Cell]:
    """Merge runs left to right into cells at the gap thresholds above."""
    runs = sorted(line, key=lambda g: g.x)
    cells: List[Cell] = []
    text, x0, x1, size = "", 0.0, 0.0, 1.0
    for g in runs:
        if not text:
            text, x0, x1, size = g.text, g.x, g.x1, g.size or 1.0
            continue
        em = max(size, g.size, 1.0)
        gap = g.x - x1
        if gap > cell_em * em:
            cells.append(Cell(text.strip(), x0, x1))
            text, x0, x1, size = g.text, g.x, g.x1, g.size or 1.0
        else:
            joiner = "" if gap <= space_em * em else " "
            # a run that already ends in a space needs no second one: some
            # producers draw the trailing space, others kern past it
            if joiner and (text.endswith(" ") or g.text.startswith(" ")):
                joiner = ""
            text = text + joiner + g.text
            x1 = max(x1, g.x1)
            size = max(size, g.size)
    if text:
        cells.append(Cell(text.strip(), x0, x1))
    return [c for c in cells if c.text]


def _assign_columns(rows: Sequence[Row], col_tol_em: float) -> List[float]:
    """Cluster cell LEFT EDGES into a column grid and stamp each cell."""
    edges: List[Tuple[float, float]] = sorted(
        (c.x0, r.size) for r in rows for c in r.cells)
    cols: List[List[float]] = []
    for x, size in edges:
        tol = col_tol_em * max(size, 1.0)
        # measured from the cluster's LEFTMOST member, not its running mean:
        # against a drifting mean a long run of edges each a hair right of
        # the last chains into one cluster many tolerances wide, and two real
        # columns silently become one.  This bounds every cluster at `tol`.
        if cols and x - cols[-1][0] <= tol:
            cols[-1].append(x)
        else:
            cols.append([x])
    centres = [sum(c) / len(c) for c in cols]
    for r in rows:
        for cell in r.cells:
            # nearest column, unconditionally: every left edge helped BUILD
            # a cluster, so one is always within tolerance and a fallback
            # branch here would be unreachable code pretending to be a guard
            cell.column = min(range(len(centres)),
                              key=lambda i: abs(cell.x0 - centres[i]))
    return centres


def build_table(page: Page, **params: float) -> Table:
    """Rows, cells and a column grid for one :class:`~.pdftext.Page`.

    Unknown keyword names raise rather than being ignored -- a silently
    misspelled tolerance would change the parse and say nothing.
    """
    bad = set(params) - set(DEFAULTS)
    if bad:
        raise TypeError("unknown layout parameter(s): %s" % ", ".join(sorted(bad)))
    p = dict(DEFAULTS)
    p.update(params)

    rows: List[Row] = []
    for i, line in enumerate(_lines(page.glyphs, p["y_tol_em"])):
        cells = _cells(line, p["space_em"], p["cell_em"])
        if not cells:
            continue
        size = max(g.size for g in line) or 1.0
        rows.append(Row(page.number, len(rows), line[0].y, size, cells))
    centres = _assign_columns(rows, p["col_tol_em"])
    return Table(page.number, rows, centres, page.note, p)

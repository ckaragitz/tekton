"""test_specsheet_pdftext_688.py -- the stdlib PDF reader reads what was
DRAWN, and where (#688 DONE 2).

WHY THIS FILE EXISTS.  ``rvt.specsheet.pdftext`` exists so a spec sheet can
be read with no new runtime dependency.  Its whole value is positional: a
reader that returns a flat string has thrown away the columns, and the
columns are where a spec sheet's meaning lives.  So every case here asserts a
COORDINATE, not just that some text came back.

THE INSTRUMENT.  ``tests/fixtures_pdf.py`` writes the PDFs, and declares
every glyph 600/1000 em wide -- so the x of the n-th character is arithmetic,
not a fuzzy range.  No real vendor sheet is or may be committed (hard rules 3
and 6); a writer is also the better instrument, because each fixture states
the coordinate it drew at and the test asserts the reader recovered THAT.

THE FOUR SHAPES, each a real producer habit and each able to break a
different part of the reader:

  ``Tm``      one absolute placement per cell -- the easy case.
  ``TJ``      a whole row as one kerned array.  Breaks unless the pen
              advances by the font's own widths: every run lands at the
              first x and the row becomes one cell.
  ``cm``      the table wrapped in ``q <translate> cm ... Q``.  Breaks unless
              the CTM is composed with the text matrix: the table is read
              perfectly, at the wrong place.
  ``type0``   2-byte CIDs with a ``/ToUnicode`` CMap and a ``/W`` array --
              what a subset-embedded font looks like.  Breaks unless both
              the CMap and the CID widths are read.

Each of those two matrix rules was confirmed by a single-variable mutant
(see the record); the tests that catch them are marked below.
"""
import os

import pytest

import fixtures_pdf as FP
from rvt.specsheet import pdftext as P

#: the shapes above; each parametrised case is one producer habit
SHAPES = {
    "Tm": {},
    "TJ": {"draw": "TJ"},
    "cm": {"draw": "cm"},
    "type0": {"font": "type0"},
    "stale_xref": {"stale_xref": True},
    "raw_stream": {"compress": False},
}


@pytest.fixture
def sheet(tmp_path):
    """``build(shape) -> [Page]`` for the standard fixture sheet."""
    def build(shape, draws=None, **extra):
        kw = dict(SHAPES[shape]) if shape in SHAPES else {}
        kw.update(extra)
        path = FP.build_pdf(str(tmp_path / ("%s.pdf" % shape)),
                            [draws if draws is not None
                             else FP.spec_sheet_draws()], **kw)
        return P.read_pdf(path)
    return build


def _at(pages, text):
    """The one glyph whose text starts with ``text`` -- and exactly one."""
    hits = [g for p in pages for g in p.glyphs if g.text.startswith(text)]
    assert len(hits) == 1, "%r appears %d times, not once" % (text, len(hits))
    return hits[0]


# ---------------------------------------------------------------------------
# (1) every shape recovers the SAME coordinates
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_producer_shape_recovers_the_drawn_position(shape, sheet):
    """The fixture drew "62.0 in" at (300, 700).  Every shape must say so.

    ``cm`` is the case that fails without CTM composition (mutant: glyphs
    land at 0,0); ``TJ`` is the case that fails without the pen advance
    (mutant: 36pt left, exactly the width of the un-advanced "Height").
    """
    pages = sheet(shape)
    assert len(pages) == 1
    g = _at(pages, "62.0 in")
    assert (round(g.x, 3), round(g.y, 3)) == (300.0, 700.0)
    assert g.size == pytest.approx(10.0)


@pytest.mark.parametrize("shape", sorted(SHAPES))
def test_every_row_of_the_sheet_survives(shape, sheet):
    """Nothing is dropped: all 8 labels and all 8 values come back."""
    pages = sheet(shape)
    text = " | ".join(g.text for g in pages[0].glyphs)
    for label, value in FP.SHEET_ROWS:
        assert label in text, "%s lost the label %r" % (shape, label)
        assert value in text, "%s lost the value %r" % (shape, value)


# ---------------------------------------------------------------------------
# (2) the advance is MEASURED, not estimated
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("shape", ["Tm", "type0"])
def test_run_width_is_the_fonts_own_advance(shape, sheet):
    """``Glyph.width`` must come from ``/Widths`` (or ``/W``), which is what
    lets the layout layer tell "two words" from "two columns".

    The fixture declares 600/1000 em for every code, so a 7-character run at
    10pt is exactly 42pt.  A reader estimating 0.5 em would say 35 -- close
    enough to look right in a screenshot and wrong enough to merge two
    columns on a tight sheet.
    """
    g = _at(sheet(shape), "62.0 in")
    assert g.width == pytest.approx(FP.advance(10.0, len("62.0 in")))
    assert g.x1 == pytest.approx(g.x + g.width)


def test_a_font_with_no_declared_widths_says_so(tmp_path):
    """An ESTIMATE must be visible.  A silently-estimated advance shifts
    every column on the page and looks exactly like a badly typeset sheet."""
    path = FP.build_pdf(str(tmp_path / "nowidths.pdf"), [FP.spec_sheet_draws()])
    raw = open(path, "rb").read()
    # strip the /Widths array, keeping the byte count identical so no offset
    # in the file moves (the reader ignores the xref, but the fixture's is
    # still written and a length change would be a second variable)
    m = __import__("re").search(rb"/FirstChar 32 /LastChar 126 /Widths \[[^\]]*\]", raw)
    assert m, "the fixture stopped declaring /Widths -- this probe is broken"
    raw = raw.replace(m.group(0), b" " * len(m.group(0)))
    open(path, "wb").write(raw)

    page = P.read_pdf(path)[0]
    assert page.has_text, "removing /Widths must not lose the text"
    assert "estimated" in page.note, page.note


# ---------------------------------------------------------------------------
# (3) what it will NOT do, said out loud
# ---------------------------------------------------------------------------

def test_an_image_only_page_is_reported_not_read_as_empty(tmp_path):
    """The failure this module was written to prevent: a scanned sheet read
    as an empty table becomes "the sheet states nothing", and a family is
    then built at nominal sizes while the user believes their document was
    used."""
    path = FP.build_pdf(str(tmp_path / "scan.pdf"), [FP.spec_sheet_draws()],
                        no_text=True)
    page = P.read_pdf(path)[0]
    assert not page.has_text
    assert "no OCR" in page.note and "scanned" in page.note


def test_an_unsupported_filter_is_named_not_half_decoded(tmp_path):
    path = FP.build_pdf(str(tmp_path / "lzw.pdf"), [FP.spec_sheet_draws()],
                        filter_name="LZWDecode")
    page = P.read_pdf(path)[0]
    assert "/LZWDecode" in page.note, page.note
    assert "FlateDecode" in page.note, "the note must say what IS supported"


def test_an_encrypted_pdf_refuses_by_name(tmp_path):
    path = FP.build_pdf(str(tmp_path / "enc.pdf"), [FP.spec_sheet_draws()],
                        encrypt=True)
    with pytest.raises(P.UnreadablePdf) as exc:
        P.read_pdf(path)
    assert "encrypted" in str(exc.value)


def test_a_non_pdf_raises_pdferror(tmp_path):
    path = tmp_path / "not.pdf"
    path.write_bytes(b"PK\x03\x04 this is a zip")
    with pytest.raises(P.PdfError):
        P.read_pdf(str(path))


# ---------------------------------------------------------------------------
# (4) multi-page, and the page cap
# ---------------------------------------------------------------------------

def test_pages_are_numbered_in_document_order(tmp_path):
    pages_in = [[(72.0, 700.0, "PAGE %d MARKER" % i)] for i in range(1, 4)]
    path = FP.build_pdf(str(tmp_path / "multi.pdf"), pages_in)
    pages = P.read_pdf(path)
    assert [p.number for p in pages] == [1, 2, 3]
    assert [p.glyphs[0].text for p in pages] == \
        ["PAGE 1 MARKER", "PAGE 2 MARKER", "PAGE 3 MARKER"]


def test_max_pages_caps_the_read(tmp_path):
    path = FP.build_pdf(str(tmp_path / "many.pdf"),
                        [[(72.0, 700.0, "p%d" % i)] for i in range(1, 9)])
    assert len(P.read_pdf(path, max_pages=3)) == 3


def test_the_media_box_is_read(tmp_path):
    page = P.read_pdf(FP.build_pdf(str(tmp_path / "mb.pdf"),
                                   [FP.spec_sheet_draws()]))[0]
    assert (page.width, page.height) == (FP.PAGE_W, FP.PAGE_H)

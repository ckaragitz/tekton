"""test_specsheet_read.py -- reading a user's spec sheet into CITED facts (#688).

Written against the three failure classes PR #674's six review rounds kept
turning up:

* **(a) user-facing text asserting behaviour the code did not implement** --
  the report prints the parsed table AS READ, names its backend, says when
  it truncated, and says when a page had no text layer.  Each of those
  claims is asserted here against what the code actually did.
* **(b) parsing that silently dropped or invented a number** -- a field the
  sheet does not state produces NO fact and a recorded reason
  (``tests/test_specsheet_values.py`` covers the cell-level gate).
* **(c) an exception escaping and withholding a file** -- every unreadable
  input below must come back as ONE clear ``SheetError`` line, never a
  traceback: hard rule 1 keeps the delivery promise.

Fresh-clone safe: every fixture is built in ``tmp_path`` by conftest's
``build_specsheet_pdf``; nothing reads ``samples/``.

Run: .venv/bin/python -m pytest tests/test_specsheet_read.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import build_specsheet_pdf                          # noqa: E402
from rvt.specsheet import (                                       # noqa: E402
    FORCE_ENV, PdfTextError, SheetError, backend_name, build_fact_sheet,
    read_pdf, read_sheet, using_stdlib_reader)

#: a small sheet with one of each: identity, plain values, a fraction, a
#: range, and a prose placeholder
SHEET_ROWS = [
    (72, 700, "ACME LIGHTING"),
    (72, 660, "Manufacturer"), (300, 660, "Acme Lighting"),
    (72, 645, "Catalog Number"), (300, 645, "TL-24-40K"),
    (72, 630, "Length"), (300, 630, "47.75 in"),
    (72, 615, "Width"), (300, 615, "23.75 in"),
    (72, 600, "Depth"), (300, 600, '2-3/8"'),
    (72, 585, "Input Power"), (300, 585, "38 W"),
    (72, 570, "Weight"), (300, 570, "Contact factory"),
    (72, 555, "Height"), (300, 555, "36-90"),
    (72, 540, "CCT"), (300, 540, "4000 K"),
]


@pytest.fixture
def sheet(tmp_path):
    return build_specsheet_pdf(tmp_path / "acme-tl24.pdf", SHEET_ROWS)


# --------------------------------------------------------------------------
# extraction
# --------------------------------------------------------------------------

def test_every_stated_value_becomes_a_fact_with_a_citation(sheet):
    r = read_sheet(sheet)
    assert r.measures, "the sheet states values; none were read"
    for field, (measure, cit) in r.measures.items():
        assert cit.document == "acme-tl24.pdf", field
        assert cit.page == 1, field
        assert cit.row_text, f"{field} has no row text to show the user"
        assert measure.raw in cit.row_text, (
            f"{field}: the citation must quote the row the value came from")


def test_values_are_the_sheets_own_numbers(sheet):
    r = read_sheet(sheet)
    assert r.measures["length_in"][0].value == 47.75
    assert r.measures["width_in"][0].value == 23.75
    assert r.measures["depth_in"][0].value == 2.375       # 2-3/8", exact
    assert r.measures["input_power_w"][0].value == 38.0
    assert r.measures["cct_k"][0].value == 4000.0


def test_a_field_the_sheet_does_not_state_is_blank_with_a_reason(sheet):
    """The two dangerous cells: a range and a prose placeholder.  Neither
    may become a number, and each must say WHY it is blank."""
    r = read_sheet(sheet)
    assert "height_in" not in r.measures
    assert "weight_lb" not in r.measures
    assert "range" in r.blanks["height_in"].reason
    assert r.blanks["weight_lb"].raw == "Contact factory"

    fs = build_fact_sheet(r)
    assert "height_in" not in fs.values
    assert "weight_lb" not in fs.values
    assert any("height_in" in n for n in fs.notes)


def test_identity_is_carried_with_its_backing_document(sheet):
    """This is the ONE lane a family may wear a manufacturer claim -- and
    the document that backs it must be nameable."""
    r = read_sheet(sheet)
    assert r.identity["manufacturer"][0] == "Acme Lighting"
    assert r.identity["part_number"][0] == "TL-24-40K"
    assert r.backing_document() == "acme-tl24.pdf"

    fs = build_fact_sheet(r)
    assert fs.values["manufacturer"].kind == "fact"
    assert "acme-tl24.pdf" in fs.values["manufacturer"].note
    assert "acme-tl24.pdf" in fs.values["manufacturer"].source


def test_facts_are_facts_and_our_arithmetic_is_derived(tmp_path):
    """A stated mm figure stays the fact; the inch value we compute is
    ``derived`` and says so, so the two can never be confused."""
    p = build_specsheet_pdf(tmp_path / "mm.pdf",
                            [(72, 700, "Length"), (300, 700, "1213 mm")])
    fs = build_fact_sheet(read_sheet(p))
    assert fs.values["length_in"].kind == "fact"
    assert fs.values["length_in"].value == 1213.0
    assert fs.values["length_in_derived_in"].kind == "derived"
    assert fs.values["length_in_derived_in"].value == pytest.approx(1213 / 25.4)
    assert "converted by us" in fs.values["length_in_derived_in"].note


def test_compressed_and_plain_streams_read_identically(tmp_path):
    """A FlateDecode content stream is what a real exporter emits; a reader
    that silently produced nothing for it would report a full sheet as
    blank."""
    a = read_sheet(build_specsheet_pdf(tmp_path / "z.pdf", SHEET_ROWS,
                                       compress=True))
    b = read_sheet(build_specsheet_pdf(tmp_path / "p.pdf", SHEET_ROWS,
                                       compress=False))
    assert [r.text for r in a.rows] == [r.text for r in b.rows]
    assert {k: v[0].value for k, v in a.measures.items()} == \
           {k: v[0].value for k, v in b.measures.items()}
    assert a.measures, "the compressed sheet read as empty"


def test_page_numbers_in_citations_are_the_pages_a_human_cites(tmp_path):
    p = build_specsheet_pdf(tmp_path / "two.pdf", None, pages=[
        [(72, 700, "Length"), (300, 700, "10 in")],
        [(72, 700, "Width"), (300, 700, "20 in")],
    ])
    r = read_sheet(p)
    assert r.measures["length_in"][1].page == 1
    assert r.measures["width_in"][1].page == 2


# --------------------------------------------------------------------------
# (a) the report says only what the code did
# --------------------------------------------------------------------------

def test_the_report_shows_the_table_as_read(sheet):
    r = read_sheet(sheet)
    table = r.parsed_table()
    assert "acme-tl24.pdf" in table
    assert len(table.splitlines()) == len(r.rows) + 1     # + the header line
    for row in r.rows:
        for cell in row.cells:
            assert cell.text in table, (
                f"row {row.index} cell {cell.text!r} is not visible in the "
                f"table the user is shown")
    # the refused cells are still SHOWN -- the user can see what we declined
    assert "Contact factory" in table
    assert "36-90" in table


def test_a_truncated_table_says_it_truncated(sheet):
    r = read_sheet(sheet)
    assert len(r.rows) > 3
    table = r.parsed_table(max_rows=3)
    assert "not shown" in table
    assert str(len(r.rows)) in table


def test_the_reading_names_the_backend_it_used(sheet):
    r = read_sheet(sheet)
    assert r.backend == backend_name()
    assert r.backend in ("pdftext", "pdfplumber")


def test_a_page_with_no_text_layer_is_reported_not_silently_empty(tmp_path):
    """A scanned page must never read as 'the sheet says nothing'."""
    p = build_specsheet_pdf(tmp_path / "mixed.pdf", None, pages=[
        [(72, 700, "Length"), (300, 700, "10 in")],
        [],                                     # image-only page
    ])
    r = read_sheet(p)
    assert r.scanned_pages == [2]
    assert any("no text layer" in n for n in r.notes)
    assert r.measures["length_in"][0].value == 10.0   # page 1 still delivered


def test_a_fully_scanned_sheet_says_so_and_does_not_raise(tmp_path):
    p = build_specsheet_pdf(tmp_path / "scan.pdf", None, pages=[[], []])
    r = read_sheet(p)                     # no exception: still a delivery
    assert not r.any_facts
    assert r.scanned_pages == [1, 2]
    assert any("scanned" in n for n in r.notes)


# --------------------------------------------------------------------------
# (c) an unreadable sheet is ONE clear line, never a traceback
# --------------------------------------------------------------------------

def test_a_missing_file_is_one_clear_line(tmp_path):
    with pytest.raises(SheetError) as e:
        read_sheet(str(tmp_path / "nope.pdf"))
    assert "\n" not in str(e.value), "the message must be one line"
    assert "nope.pdf" in str(e.value)


def test_a_file_that_is_not_a_pdf_is_one_clear_line(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("Length 47.75 in\n", encoding="utf-8")
    with pytest.raises(SheetError) as e:
        read_sheet(str(p))
    assert "not a PDF" in str(e.value)


def test_a_truncated_pdf_is_one_clear_line(tmp_path):
    good = build_specsheet_pdf(tmp_path / "good.pdf", SHEET_ROWS)
    raw = open(good, "rb").read()
    bad = tmp_path / "cut.pdf"
    bad.write_bytes(raw[:40])
    with pytest.raises(SheetError) as e:
        read_sheet(str(bad))
    assert str(e.value).strip()


def test_an_encrypted_pdf_says_it_is_encrypted(tmp_path):
    good = build_specsheet_pdf(tmp_path / "e.pdf", SHEET_ROWS)
    raw = open(good, "rb").read()
    enc = tmp_path / "enc.pdf"
    enc.write_bytes(raw.replace(b"trailer\n<< /Size",
                                b"trailer\n<< /Encrypt 99 0 R /Size"))
    with pytest.raises(SheetError) as e:
        read_sheet(str(enc))
    assert "encrypted" in str(e.value)


def test_an_unsupported_stream_filter_is_named_not_swallowed(tmp_path):
    good = build_specsheet_pdf(tmp_path / "f.pdf", SHEET_ROWS, compress=True)
    raw = open(good, "rb").read()
    odd = tmp_path / "odd.pdf"
    odd.write_bytes(raw.replace(b"/Filter /FlateDecode", b"/Filter /JPXDecode"))
    with pytest.raises(PdfTextError) as e:
        read_pdf(str(odd))
    assert "JPXDecode" in str(e.value)


def test_a_directory_path_does_not_escape_as_oserror(tmp_path):
    with pytest.raises(SheetError):
        read_sheet(str(tmp_path))


# --------------------------------------------------------------------------
# the optional dependency stays optional
# --------------------------------------------------------------------------

def test_the_stdlib_reader_serves_with_no_pdf_wheel_installed(sheet, monkeypatch):
    """The engine must read a text-layer sheet on a bare interpreter."""
    monkeypatch.setenv(FORCE_ENV, "1")
    assert using_stdlib_reader()
    r = read_sheet(sheet)
    assert r.backend == "pdftext"
    assert r.measures["length_in"][0].value == 47.75


def test_specsheet_imports_without_any_optional_backend():
    """Importing the lane must not require the optional wheel."""
    import importlib
    mod = importlib.import_module("rvt.specsheet")
    assert mod.BACKEND_DIST == "pdfplumber"
    assert isinstance(mod.pdf_backend_installed(), bool)

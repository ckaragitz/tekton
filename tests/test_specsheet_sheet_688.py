"""test_specsheet_sheet_688.py -- positions become CITED values (#688 DONE 3/4/6).

The reader below the layout layer is measured in
``test_specsheet_pdftext_688.py``.  This file is about the part that can be
dishonest: turning coordinates into "the panel is 62 inches tall".

THE LINE BEING GUARDED.  S-2026-08-11-c forbids the model supplying a
manufacturer's dimension as a ``fact``; S-2026-08-11-d makes the user's own
sheet the honest route to exactly that number.  So the contract is narrow and
every case here pins one edge of it:

* a value is taken ONLY when the sheet states it, and it carries the file,
  page and row it was read from (DONE 3);
* the parse is shown as a grid before it is trusted, so a value that landed
  one column right is visible (DONE 4);
* everything else -- an unparseable cell, a unitless length, an unknown
  label, an unreadable document -- is refused BY NAME and listed, never
  dropped and never guessed (DONE 6, hard rule 1).

What is deliberately NOT asserted: that any number here is true of any real
product.  ``fixtures_pdf.SHEET_ROWS`` is invented for this fixture and no
manufacturer's document was read to produce it (hard rule 3).
"""
import os

import pytest

import fixtures_pdf as FP
from rvt.specsheet import layout as L, pdftext as P, sheet as S, vocab as V

#: every case reads through the STDLIB backend, so the assertions below are
#: about this repo's code and not about whichever extra happens to be
#: installed.  The backends' agreement is its own file
#: (test_specsheet_backend_688.py), which is where that claim belongs.
pytestmark = pytest.mark.usefixtures("stdlib_pdf_backend")


@pytest.fixture
def stdlib_pdf_backend(monkeypatch):
    from rvt.specsheet import _backend as B
    monkeypatch.setenv(B.FORCE_ENV, "1")


@pytest.fixture
def parsed(tmp_path):
    """``read(draws=None, **build_kw) -> ParsedSheet``."""
    def read(draws=None, name="probe.pdf", **kw):
        path = FP.build_pdf(str(tmp_path / name),
                            [draws if draws is not None
                             else FP.spec_sheet_draws()], **kw)
        return S.read_sheet(path)
    return read


def test_this_module_really_runs_on_the_stdlib_backend():
    """The module-level ``usefixtures`` above is load-bearing: without it
    these assertions would silently be about whichever extra is installed on
    the machine running them, and would say nothing about this repo."""
    from rvt.specsheet import _backend as B
    assert B.backend_name() == "stdlib"


# ---------------------------------------------------------------------------
# (1) the layout inference
# ---------------------------------------------------------------------------

def test_the_two_column_sheet_is_read_as_two_columns(tmp_path):
    page = P.read_pdf(FP.build_pdf(str(tmp_path / "t.pdf"),
                                   [FP.spec_sheet_draws()]))[0]
    table = L.build_table(page)
    assert [round(c) for c in table.columns] == [72, 300], \
        "the fixture draws labels at x=72 and values at x=300"
    grid = table.column_grid()
    assert ["Height", "62.0 in"] in grid
    assert ["Short Circuit Rating", "65 kAIC"] in grid


def test_column_clusters_are_bounded_by_the_tolerance(tmp_path):
    """A drifting left edge must NOT chain into one wide column.

    12 rows, each 3pt right of the last, span 33pt at a 0.8 em (8pt)
    tolerance.  Clustering against a running MEAN chains all twelve into one
    cluster 33pt wide and two real columns silently become one; clustering
    from each cluster's leftmost member bounds every cluster at the
    tolerance.  Measured: 4 clusters, mean-anchored gives 1.
    """
    draws = [(72.0 + 3.0 * i, 700.0 - 18.0 * i, "v%d" % i) for i in range(12)]
    table = L.build_table(P.read_pdf(
        FP.build_pdf(str(tmp_path / "drift.pdf"), [draws]))[0])
    assert len(table.columns) == 4
    for centres in zip(table.columns, table.columns[1:]):
        assert centres[1] - centres[0] > 0


def test_runs_close_together_are_one_cell_and_far_apart_are_two(tmp_path):
    """The cell threshold is 1.6 em; at 10pt that is 16pt.

    Drawn: "AB" at x=72 (ends at 84), then a run 8pt later (one cell) and a
    run 40pt later (two cells).  A reader with no gap rule returns one cell
    for both, and every label/value pair on the sheet is lost.
    """
    near = [(72.0, 700.0, "AB"), (92.0, 700.0, "CD")]      # gap 8pt  -> one
    far = [(72.0, 600.0, "AB"), (124.0, 600.0, "CD")]      # gap 40pt -> two
    table = L.build_table(P.read_pdf(
        FP.build_pdf(str(tmp_path / "gap.pdf"), [near + far]))[0])
    texts = [r.cell_texts() for r in table.rows]
    assert ["AB CD"] in texts, texts
    assert ["AB", "CD"] in texts, texts


def test_an_unknown_layout_parameter_raises(tmp_path):
    page = P.read_pdf(FP.build_pdf(str(tmp_path / "p.pdf"),
                                   [FP.spec_sheet_draws()]))[0]
    with pytest.raises(TypeError) as exc:
        L.build_table(page, cell_emm=2.0)
    assert "cell_emm" in str(exc.value), \
        "a misspelled tolerance must not be silently ignored"


# ---------------------------------------------------------------------------
# (2) quantities -- where a wrong parse becomes a wrong dimension
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,value,unit", [
    ("62.0 in", 62.0, "in"),
    ("62in", 62.0, "in"),
    ('62"', 62.0, '"'),
    ("20-1/2 in", 20.5, "in"),
    ("1/2 in", 0.5, "in"),
    ("5.75 in", 5.75, "in"),
    ("145 lb", 145.0, "lb"),
    ("400 A", 400.0, "A"),
    ("65 kAIC", 65.0, "kAIC"),
    ("1575 mm", 1575.0, "mm"),
    ("3", 3.0, ""),
])
def test_quantities_that_parse(text, value, unit):
    q = S.parse_quantity(text)
    assert q is not None, "%r should parse" % text
    assert q.value == pytest.approx(value)
    assert q.unit == unit


@pytest.mark.parametrize("text", [
    "480Y/277 V",        # a system designation, not a number with a unit
    "NEMA 1",            # a type, and the digit is not a measurement
    "see page 4",
    "",
    "-",
    "TBD",
])
def test_things_that_are_not_quantities_return_none(text):
    """``None``, never a guess.  "480Y/277 V" parsing as 480 is how a
    voltage designation becomes a 480-inch panel."""
    assert S.parse_quantity(text) is None


@pytest.mark.parametrize("text,inches", [
    ("3'-6\"", 42.0),
    ("3' 6\"", 42.0),
    ("2'", 24.0),
    ("1 ft", 12.0),
    ("1575 mm", 1575.0 / 25.4),
    ("62 in", 62.0),
])
def test_lengths_convert_to_inches(text, inches):
    assert S.parse_quantity(text).in_inches() == pytest.approx(inches)


def test_a_bare_number_is_not_a_length():
    """A unit taken from a column header would be an inference about layout;
    this module makes no inference that turns into a dimension."""
    assert S.parse_quantity("62").in_inches() is None


def test_a_dual_dimension_keeps_the_first_and_NOTES_the_second():
    q = S.parse_quantity("62.0 in (1575 mm)")
    assert q.value == pytest.approx(62.0) and q.unit == "in"
    assert "1575 mm" in q.note, \
        "the metric twin must be shown, not averaged in and not dropped"


# ---------------------------------------------------------------------------
# (3) cited values -- DONE 3
# ---------------------------------------------------------------------------

def test_every_stated_field_is_read_with_its_citation(parsed):
    ps = parsed()
    got = ps.by_key()
    assert got["height_in"].value == pytest.approx(62.0)
    assert got["width_in"].value == pytest.approx(20.5)
    assert got["depth_in"].value == pytest.approx(5.75)
    assert got["weight_lb"].value == pytest.approx(145.0)
    assert got["amps"].value == pytest.approx(400.0)
    assert got["voltage"].value == "480Y/277 V"
    assert got["enclosure"].value == "NEMA 1"

    cite = got["height_in"].citation(ps.path)
    assert "probe.pdf" in cite and "p1" in cite
    assert "'Height'" in cite and "'62.0 in'" in cite, cite
    assert got["height_in"].row == 3, "the citation must name the real row"


def test_a_unit_conversion_is_recorded_on_the_value(tmp_path):
    draws = [(72.0, 700.0, "Height"), (300.0, 700.0, "1575 mm")]
    ps = S.read_sheet(FP.build_pdf(str(tmp_path / "mm.pdf"), [draws]))
    v = ps.by_key()["height_in"]
    assert v.value == pytest.approx(1575.0 / 25.4)
    assert v.raw == "1575 mm", "the page's own text is kept verbatim"
    assert "converted from mm" in v.note


def test_an_identity_line_is_split_on_its_colon(parsed):
    """"Catalog Number: PW-400-42-NEMA1" is typeset as running text, so the
    layout layer correctly sees ONE cell; the colon recovers the pair."""
    v = parsed().by_key()["model"]
    assert v.value == "PW-400-42-NEMA1"
    assert v.label == "Catalog Number"


def test_the_colon_split_does_not_turn_prose_into_facts(parsed):
    """"Note: see page 4" must stay unused: the split only fires when what
    precedes the colon already names a field we know."""
    ps = parsed(FP.spec_sheet_draws()
                + [(72.0, 520.0, "Note: see page 4 for accessories")])
    assert "see page 4 for accessories" not in repr(ps.by_key())
    assert any("see page 4" in t for _p, _r, t in ps.unmapped)


def test_a_row_whose_value_is_unitless_is_left_unset_and_said_so(tmp_path):
    draws = [(72.0, 700.0, "Height"), (300.0, 700.0, "62")]
    ps = S.read_sheet(FP.build_pdf(str(tmp_path / "u.pdf"), [draws]))
    assert "height_in" not in ps.by_key()
    assert any("states no length unit" in n for n in ps.notes), ps.notes


def test_rows_the_engine_does_not_understand_are_listed_not_dropped(parsed):
    ps = parsed()
    unused = [t for _p, _r, t in ps.unmapped]
    assert "PROBEWORKS INDUSTRIES" in unused, \
        "an unlabelled heading must be SHOWN, not guessed at as a manufacturer"
    assert "Specifications" in unused


def test_a_label_that_merely_contains_a_known_word_is_not_matched():
    """Substring matching reads "Enclosure Height" into the NEMA-type field
    and cites the sheet while doing it.  A wrong value wearing a citation is
    worse than no value."""
    assert V.canonical_key("Enclosure Height") == "height_in"
    assert V.canonical_key("Height of shipping crate") == ""


def test_a_field_stated_twice_is_reported_as_a_question(tmp_path):
    draws = [(72.0, 700.0, "Height"), (300.0, 700.0, "62.0 in"),
             (72.0, 600.0, "Height"), (300.0, 600.0, "48.0 in")]
    ps = S.read_sheet(FP.build_pdf(str(tmp_path / "dup.pdf"), [draws]))
    assert len(ps.duplicates()["height_in"]) == 2
    assert ps.by_key()["height_in"].value == pytest.approx(62.0), \
        "first occurrence wins -- but silently would be wrong"
    assert any("height_in" in q and "which one" in q for q in ps.questions())


# ---------------------------------------------------------------------------
# (4) the parse is SHOWN before it is trusted -- DONE 4
# ---------------------------------------------------------------------------

def test_the_report_shows_the_table_as_read_and_every_citation(parsed):
    ps = parsed()
    text = ps.report()
    assert "page 1 as read" in text
    for label, value in FP.SHEET_ROWS:
        assert label in text and value in text, \
            "the table as read must show every row, used or not"
    assert "values taken (every one cited)" in text
    assert "p1 r3 'Height' = '62.0 in'" in text
    assert "rows read but NOT used" in text


def test_the_json_carries_the_grid_the_values_and_the_residue(parsed):
    js = parsed().as_json()
    assert js["tables"][0]["rows"][3]["cells"] == ["Height", "62.0 in"]
    heights = [v for v in js["values"] if v["key"] == "height_in"]
    assert len(heights) == 1 and heights[0]["citation"]
    assert any("PROBEWORKS" in r["text"] for r in js["unmapped_rows"])


# ---------------------------------------------------------------------------
# (5) refusals -- named, and never blocking (DONE 6, hard rule 1)
# ---------------------------------------------------------------------------

def test_an_image_only_sheet_says_so_and_does_not_raise(parsed):
    ps = parsed(no_text=True)
    assert not ps.ok
    assert "no OCR" in ps.unreadable and "scanned" in ps.unreadable
    assert ps.values == [], "nothing may be invented for an unreadable sheet"


def test_an_unsupported_filter_says_which_one(parsed):
    ps = parsed(filter_name="LZWDecode")
    assert "/LZWDecode" in " ".join(ps.notes) + ps.unreadable


def test_an_encrypted_sheet_says_so_and_does_not_raise(parsed):
    ps = parsed(encrypt=True)
    assert "encrypted" in ps.unreadable
    assert ps.tables == []


def test_a_non_pdf_says_so_and_does_not_raise(tmp_path):
    p = tmp_path / "x.pdf"
    p.write_bytes(b"not a pdf at all")
    ps = S.read_sheet(str(p))
    assert "not a PDF" in ps.unreadable


def test_a_sheet_with_no_recognisable_rows_says_so_and_lists_them(tmp_path):
    draws = [(72.0, 700.0 - 18 * i, "Lorem ipsum line %d" % i) for i in range(5)]
    ps = S.read_sheet(FP.build_pdf(str(tmp_path / "prose.pdf"), [draws]))
    assert not ps.ok and not ps.unreadable, \
        "readable but uninformative is NOT the same as unreadable"
    assert any("named a field the engine knows" in n for n in ps.notes)
    assert len(ps.unmapped) == 5


def test_a_missing_file_is_a_caller_bug_and_raises(tmp_path):
    with pytest.raises(OSError):
        S.read_sheet(str(tmp_path / "nope.pdf"))

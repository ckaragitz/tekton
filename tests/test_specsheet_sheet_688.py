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


@pytest.mark.parametrize("text,inches", [
    ("62.0 in.", 62.0),          # the abbreviation half of all sheets use
    ("62.0 In", 62.0),
    ("62.0 INCHES", 62.0),
])
def test_an_abbreviated_unit_is_still_a_unit(text, inches):
    """A trailing period made a perfectly clear inch value come back as
    "states no length unit"."""
    assert S.parse_quantity(text).in_inches() == pytest.approx(inches)


@pytest.mark.parametrize("text", ["20-24 in", "20 - 24 in", "20 to 24 in"])
def test_a_RANGE_is_not_a_number(text):
    """Rounding a range into a fact is named in the module docstring as a
    thing that never happens here.  "20-1/2" is a mixed fraction and does
    parse; "20-24" is a range and must not."""
    assert S.parse_quantity(text) is None


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


@pytest.mark.parametrize("raw", ["0 in", "-4 in", "0.0 in"])
def test_a_non_positive_length_is_refused_by_name(raw, tmp_path):
    """Zero or negative is never a real dimension, and taking one builds a
    degenerate solid that our own validator still calls VALID."""
    draws = [(72.0, 700.0, "Height"), (300.0, 700.0, raw)]
    ps = S.read_sheet(FP.build_pdf(str(tmp_path / "neg.pdf"), [draws]))
    assert "height_in" not in ps.by_key()
    assert any("not a positive length" in n for n in ps.notes), ps.notes


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
# (3b) the #688 review's findings, each pinned
# ---------------------------------------------------------------------------

#: bare-numeric values, with the unit hoisted into the row label
NUMERIC_SHAPES = {"Tm": {}, "TJ": {"draw": "TJ"},
                  "TJ_kern_split": {"draw": "TJ", "kern_split": 1}}


@pytest.mark.parametrize("shape", sorted(NUMERIC_SHAPES))
def test_a_sheet_of_bare_numbers_reads_end_to_end(shape, tmp_path):
    """The whole pipeline on the shape the old fixture could not produce.

    Every value in ``SHEET_ROWS`` contains a space, so a reader deciding
    "string or kerning number?" by trying ``float()`` always fell through to
    the right answer by accident and the suite stayed green over a real bug
    (#688 review). Here the values are bare numbers and, in one case, split
    mid-number by a zero kern -- so both halves of that bug are exercised.
    """
    path = FP.build_pdf(str(tmp_path / ("n_%s.pdf" % shape)),
                        [FP.numeric_sheet_draws()], **NUMERIC_SHAPES[shape])
    got = S.read_sheet(path).by_key()
    assert got["height_in"].value == pytest.approx(62.0)
    assert got["width_in"].value == pytest.approx(20.5)
    assert got["depth_in"].value == pytest.approx(5.75)
    assert got["weight_lb"].value == pytest.approx(145.0)


def test_a_unit_in_the_rows_own_label_is_a_reading(tmp_path):
    """"Height (in)" with a bare "62.0" is the row STATING its unit.

    Distinct from a column header, which belongs to a different row and is
    still refused: the note records which it was, so the report never
    presents an assumption as a reading.
    """
    draws = [(72.0, 700.0, "Height (in)"), (300.0, 700.0, "62.0")]
    v = S.read_sheet(FP.build_pdf(str(tmp_path / "lbl.pdf"), [draws])).by_key()
    assert v["height_in"].value == pytest.approx(62.0)
    assert "read from the row's own label" in v["height_in"].note


@pytest.mark.parametrize("label", ["Enclosure (Height)", "Notes (see p4)"])
def test_only_a_UNIT_is_stripped_from_a_label(label):
    """The trailing-parenthetical rule must not become the substring trap
    one step along: "Enclosure (Height)" is not the enclosure field."""
    assert V.canonical_key(label) == ""


def test_width_W_still_means_width_not_watts():
    assert V.canonical_key("Width (W)") == "width_in"


def test_a_value_in_the_wrong_unit_is_refused_by_name(tmp_path):
    """``weight_lb = 90`` read off a row saying "90 kg" is a fact about the
    document and a lie about the product, and a consumer reading the key by
    name cannot see the difference (#688 review). Nothing here converts a
    rating, so the mismatch is named instead."""
    draws = [(72.0, 700.0, "Weight"), (300.0, 700.0, "90 kg")]
    ps = S.read_sheet(FP.build_pdf(str(tmp_path / "kg.pdf"), [draws]))
    assert "weight_lb" not in ps.by_key()
    assert any("states kg" in n and "weight_lb" in n for n in ps.notes), ps.notes


@pytest.mark.parametrize("raw,expect", [("145 lbs", 145.0), ("145 LB.", 145.0),
                                        ("145", 145.0)])
def test_accepted_unit_spellings_and_a_bare_rating_still_read(raw, expect, tmp_path):
    """A rating is not a length: a bare number under a rating key is
    recorded WITH a note, not refused, because refusing every unitless
    rating would gut the reader on real sheets. The 25x ambiguity that
    justifies refusing a bare LENGTH does not exist here."""
    draws = [(72.0, 700.0, "Weight"), (300.0, 700.0, raw)]
    v = S.read_sheet(FP.build_pdf(str(tmp_path / "sp.pdf"), [draws])).by_key()
    assert v["weight_lb"].value == pytest.approx(expect)


def test_a_malformed_media_box_does_not_raise(tmp_path):
    """``read_sheet`` documents that it never raises for a bad document.
    Fuzzing in the #688 review found exactly two escapes, both here."""
    path = FP.build_pdf(str(tmp_path / "mb.pdf"), [FP.spec_sheet_draws()])
    raw = open(path, "rb").read()
    assert b"/MediaBox [0 0 612 792]" in raw, "fixture changed; probe broken"
    raw = raw.replace(b"/MediaBox [0 0 612 792]", b"/MediaBox [. . .  . ]", 1)
    open(path, "wb").write(raw)
    ps = S.read_sheet(path)                              # must not raise
    assert ps.by_key()["height_in"].value == pytest.approx(62.0)
    assert ps.tables[0].page == 1


def test_the_page_cap_is_reported_not_silent(tmp_path):
    """Dropping pages 65+ of a 100-page submittal turns "we did not look"
    into "the sheet does not say so", and questions() then asks about a
    field the document answers on page 80."""
    pages = [[(72.0, 700.0, "PAGE %d" % i)] for i in range(1, 7)]
    ps = S.read_sheet(FP.build_pdf(str(tmp_path / "many.pdf"), pages),
                      max_pages=3)
    assert len(ps.tables) == 3
    assert any("only the first 3 were read" in n for n in ps.notes), ps.notes


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

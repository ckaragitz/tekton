"""test_specsheet_backend_688.py -- the two PDF backends must AGREE (#688 DONE 2).

The engine declares one runtime dependency, so a spec sheet has to be
readable with none added: ``rvt.specsheet.pdftext`` is that guarantee, and
the optional ``[pdf]`` extra is for the documents it names and refuses.  That
is only honest if both roads reach the same place -- otherwise the family a
user gets depends on what happens to be installed on their machine, with
nothing in the output to say so.

The architecture that makes the claim testable: both backends produce the
same ``Page``/``Glyph`` shape and everything above them (layout, vocab,
sheet) is shared.  So this file is a genuine CROSS-IMPLEMENTATION control,
not a self-consistency check: pdfminer (under pdfplumber) is an independent
implementation of the same format, written by other people, and where it
agrees with ``pdftext`` on a coordinate that coordinate is very unlikely to
be our bug.

Skipped wholesale without the extra -- including in CI, which installs only
``[test]``.  The measured result is recorded in the stream record; re-run it
with ``pip install -e ".[pdf]"``.
"""
import pytest

import fixtures_pdf as FP

pdfplumber = pytest.importorskip(
    "pdfplumber", reason='the optional [pdf] extra: pip install -e ".[pdf]"')

from rvt.specsheet import _backend as B, sheet as S       # noqa: E402

#: the producer habits from test_specsheet_pdftext_688, minus the one where
#: the two are KNOWN to differ (see test_the_backends_differ_on_a_stale_xref)
AGREEING_SHAPES = {
    "Tm": {},
    "TJ": {"draw": "TJ"},
    "cm": {"draw": "cm"},
    "type0": {"font": "type0"},
    "raw_stream": {"compress": False},
    "filter_array": {"filter_array": True},
}

#: The bare-numeric sheet, in its own dict because it uses different draws.
#: This is the shape the first round of this file could not produce, and so
#: the shape whose bug the pdfminer control never got to catch: every value
#: in ``SHEET_ROWS`` contains a space.  Listed here so the independent
#: implementation checks the fix rather than only our own tests doing it.
NUMERIC_SHAPES = {"Tm": {}, "TJ": {"draw": "TJ"},
                  "TJ_kern_split": {"draw": "TJ", "kern_split": 1}}


def _read(path, monkeypatch, stdlib: bool):
    if stdlib:
        monkeypatch.setenv(B.FORCE_ENV, "1")
    else:
        monkeypatch.delenv(B.FORCE_ENV, raising=False)
    return S.read_sheet(path)


def test_the_extra_is_actually_selected_when_installed(monkeypatch):
    monkeypatch.delenv(B.FORCE_ENV, raising=False)
    assert B.backend_name() == "pdfplumber"
    monkeypatch.setenv(B.FORCE_ENV, "1")
    assert B.backend_name() == "stdlib", \
        "RVT_PDF_STDLIB_FORCE must pin the stdlib reader over an install"


@pytest.mark.parametrize("shape", sorted(AGREEING_SHAPES))
def test_both_backends_read_the_same_values(shape, tmp_path, monkeypatch):
    """Every cited value, key for key, from an independent implementation."""
    path = FP.build_pdf(str(tmp_path / ("%s.pdf" % shape)),
                        [FP.spec_sheet_draws()], **AGREEING_SHAPES[shape])
    ours = {v.key: (v.value, v.unit) for v in _read(path, monkeypatch, True).values}
    theirs = {v.key: (v.value, v.unit) for v in _read(path, monkeypatch, False).values}
    assert ours == theirs
    assert len(ours) == 9, "the fixture states 9 fields we know; got %d" % len(ours)


@pytest.mark.parametrize("shape", sorted(AGREEING_SHAPES))
def test_both_backends_agree_on_the_row_grid(shape, tmp_path, monkeypatch):
    """Not just the values -- the whole parsed table, which is what a human
    checks (DONE 4).  A backend that recovered the right numbers from the
    wrong cells would pass the test above and fail this one."""
    path = FP.build_pdf(str(tmp_path / ("%s.pdf" % shape)),
                        [FP.spec_sheet_draws()], **AGREEING_SHAPES[shape])
    ours = _read(path, monkeypatch, True).tables[0].column_grid()
    theirs = _read(path, monkeypatch, False).tables[0].column_grid()
    assert ours == theirs


@pytest.mark.parametrize("shape", sorted(NUMERIC_SHAPES))
def test_both_backends_read_a_sheet_of_BARE_NUMBERS_the_same(
        shape, tmp_path, monkeypatch):
    """pdfminer as the control on the case that actually broke.

    A numeric string inside a ``TJ`` array was being taken for a kerning
    adjustment, so the value vanished -- or, kern-split, came back
    truncated: ``62.0`` read as ``2.0``, a wrong dimension carrying a
    citation. pdfminer never had that ambiguity, so it is the right oracle.
    """
    path = FP.build_pdf(str(tmp_path / ("n_%s.pdf" % shape)),
                        [FP.numeric_sheet_draws()], **NUMERIC_SHAPES[shape])
    ours = {v.key: v.value for v in _read(path, monkeypatch, True).values}
    theirs = {v.key: v.value for v in _read(path, monkeypatch, False).values}
    assert ours == theirs
    assert ours == {"height_in": 62.0, "width_in": 20.5,
                    "depth_in": 5.75, "weight_lb": 145.0}


def test_a_missing_file_raises_on_BOTH_backends(tmp_path, monkeypatch):
    """A missing FILE is a caller bug, not a bad document, and must not
    depend on what is installed. With the extra, a blanket ``except
    Exception`` was folding ``FileNotFoundError`` into ``UnreadablePdf``, so
    the same typo'd path raised on one machine and returned a ParsedSheet on
    another -- the one thing _backend claims cannot happen (#688 review)."""
    missing = str(tmp_path / "nope.pdf")
    for stdlib in (True, False):
        with pytest.raises(OSError):
            _read(missing, monkeypatch, stdlib)


def test_the_backends_differ_on_a_stale_xref_and_the_reason_says_so(
        tmp_path, monkeypatch):
    """A MEASURED difference, pinned rather than papered over.

    ``pdftext`` finds objects by scanning, so a stale cross-reference table
    costs it nothing; pdfminer trusts the table and returns zero pages.  The
    result is NOT silently swapped for the one that worked -- that would make
    one document read differently on two machines -- but the refusal names
    the switch that does work.
    """
    path = FP.build_pdf(str(tmp_path / "stale.pdf"), [FP.spec_sheet_draws()],
                        stale_xref=True)
    ours = _read(path, monkeypatch, True)
    assert len(ours.values) == 9 and not ours.unreadable

    theirs = _read(path, monkeypatch, False)
    assert not theirs.values
    assert "found no pages" in theirs.unreadable
    assert B.FORCE_ENV in theirs.unreadable, \
        "a dead end must come with the one switch that is not one"

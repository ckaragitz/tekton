"""A fraction is read as the number it is written as (issue #831).

``archetypes._to_number`` stripped every space before parsing, so "1 3/16"
and "13/16" became the same string -- and the mixed-number pattern, tried
first with an OPTIONAL separator, won:

    "strut channel 13/16 in tall"  ->  height_in = 1.1875  given   (13/16 = 0.8125)

13/16 in is a standard shallow-strut depth, and ``given`` means "you stated
it".  Found by the round-2 reviewer of #828.

The spec-sheet reader (``specsheet.sheet._num``) had the fraction patterns
right but divided by a zero denominator: "3/0" and "4/0" are everyday AWG
sizes, and a sheet row carrying one FAILED the whole pdf route with no file
(hard rule 1).  Same family of defect, same fix shape: a zero denominator is
not a quantity.
"""
from __future__ import annotations

import os
import sys
from fractions import Fraction

import pytest

from rvt.famgen import archetypes as AR
from rvt.specsheet import sheet as S

DENS = (2, 4, 8, 16, 32, 64)


def _fractions():
    for d in DENS:
        for n in range(1, 100):
            yield n, d


@pytest.mark.parametrize("parse", [AR._to_number, S._num], ids=["archetypes", "specsheet"])
def test_every_plain_fraction_is_its_own_value(parse):
    bad = [(f"{n}/{d}", parse(f"{n}/{d}")) for n, d in _fractions()
           if parse(f"{n}/{d}") != pytest.approx(float(Fraction(n, d)))]
    assert not bad, f"{len(bad)} plain fractions misread; first: {bad[:5]}"


@pytest.mark.parametrize("parse", [AR._to_number, S._num], ids=["archetypes", "specsheet"])
@pytest.mark.parametrize("sep", ["-", " ", " - "])
def test_a_mixed_number_needs_and_keeps_its_separator(parse, sep):
    bad = []
    for n, d in _fractions():
        for whole in (1, 2, 12):
            txt = f"{whole}{sep}{n}/{d}"
            if parse(txt) != pytest.approx(whole + float(Fraction(n, d))):
                bad.append((txt, parse(txt)))
    assert not bad, f"{len(bad)} mixed numbers misread; first: {bad[:5]}"


@pytest.mark.parametrize("txt", ["3/0", "4/0", "1-1/0", "2 0/0"])
@pytest.mark.parametrize("parse", [AR._to_number, S._num], ids=["archetypes", "specsheet"])
def test_a_zero_denominator_is_not_a_quantity(parse, txt):
    assert parse(txt) is None


@pytest.mark.parametrize("txt,want", [("1,200", 1200.0), ("1,200.5", 1200.5), ("24", 24.0),
                                      ("1.5", 1.5), ("12,00", None), ("1-5", None)])
def test_grouping_and_plain_numbers_are_unchanged(txt, want):
    assert AR._to_number(txt) == want


@pytest.mark.parametrize("prompt,key,want", [
    ("strut channel 13/16 in tall", "height_in", 0.8125),
    ("strut channel 15/16 in tall", "height_in", 0.9375),
    ("a 1 13/16 in tall strut channel", "height_in", 1.8125),
    ("a 1-3/16 in tall strut channel", "height_in", 1.1875),
    ("conduit 2 1/2 in diameter", "diameter_in", 2.5),
    ("a 1,200 mm cable tray", "width_in", 1200 / 25.4),
])
def test_the_prompt_route_reads_the_number_that_was_written(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key])
    assert r.provenance[key] == "given"


def _awg_sheet(tmp_path):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import fixtures_pdf as FP
    draws = [(72.0, 754.0, "PROBEWORKS INDUSTRIES"), (72.0, 736.0, "Catalog Number: PW-1"),
             (72.0, 718.0, "Specifications"),
             (72.0, 700.0, "Height"), (300.0, 700.0, "62.0 in"),
             (72.0, 682.0, "Width"), (300.0, 682.0, "3/0 in"),
             (72.0, 664.0, "Depth"), (300.0, 664.0, "13/16 in")]
    return FP.build_pdf(str(tmp_path / "awg.pdf"), [draws])


def test_a_sheet_row_with_a_zero_denominator_is_left_unset_not_a_crash(tmp_path):
    sheet = S.read_sheet(_awg_sheet(tmp_path))
    got = {v.key: v.value for v in sheet.values}
    assert got.get("height_in") == pytest.approx(62.0)
    assert got.get("depth_in") == pytest.approx(0.8125)
    assert "width_in" not in got, "3/0 in is not a width"


def test_the_pdf_route_still_delivers_when_a_row_says_3_0(tmp_path):
    from rvt.frontdoor import router as R
    res = R.route({"pdf": _awg_sheet(tmp_path), "prompt": "a lighting control panel"}, "rfa",
                  out=str(tmp_path / "out"), quiet=True)
    assert res.ok, res.status
    assert os.path.isfile(res.files["rfa"])

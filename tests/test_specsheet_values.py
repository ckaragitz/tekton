"""test_specsheet_values.py -- the value gate refuses what it cannot honestly
read (#688).

This module is written against failure class (b) from PR #674's review
rounds: *parsing that silently dropped or invented a number the user had
written*.  Every row below is a cell a real spec sheet prints; the assertion
is either "this exact number" or "no number, and a reason".  A parser that
resolves ``36-90`` to ``36``, ``Contact factory`` to ``0``, or ``2-3/8"`` to
``2`` fails here, which is the point -- each of those would write a figure
the manufacturer never published into a family claiming their dimensions.

Run: .venv/bin/python -m pytest tests/test_specsheet_values.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.specsheet.values import (                                # noqa: E402
    IN_PER_FT, MM_PER_IN, Measure, Refusal, parse_measure, to_inches)


# --------------------------------------------------------------------------
# values the sheet DOES state -- read exactly, never rounded
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cell,value,unit", [
    ("47.75 in", 47.75, "in"),
    ("47.75 inches", 47.75, "in"),
    ('47.75"', 47.75, "in"),
    ("38 W", 38.0, "W"),
    ("4000 K", 4000.0, "K"),
    ("1213 mm", 1213.0, "mm"),
    ("600 Vac", 600.0, "Vac"),
    ("5 ft", 5.0, "ft"),
    ("12.5", 12.5, ""),
    (".5", 0.5, ""),
    ("0.5", 0.5, ""),
    ("1,250 lb", 1250.0, "lb"),
])
def test_stated_values_are_read_exactly(cell, value, unit):
    m = parse_measure(cell)
    assert isinstance(m, Measure), f"{cell!r} should parse, got {m}"
    assert m.value == value
    assert m.unit == unit
    assert m.raw == cell


@pytest.mark.parametrize("cell,value", [
    ("3/4", 0.75),
    ("2-3/8\"", 2.375),          # a '-' inside a MIXED FRACTION is not a range
    ("2 3/8\"", 2.375),
    ("47-3/4 in", 47.75),
    ("1/2", 0.5),
    ("15/16", 0.9375),
])
def test_fractions_are_exact_not_truncated(cell, value):
    """The denominators sheets use are exact in binary floating point; a
    parser that took the leading integer would silently shrink the part."""
    m = parse_measure(cell)
    assert isinstance(m, Measure), f"{cell!r} should parse, got {m}"
    assert m.value == value


# --------------------------------------------------------------------------
# values the sheet does NOT state -- refused with a reason, never a number
# --------------------------------------------------------------------------

@pytest.mark.parametrize("cell", [
    "36-90", "36 - 90", "36–90", "36—90", "36 to 90", "15..30",
])
def test_a_range_is_never_resolved_to_one_end(cell):
    r = parse_measure(cell)
    assert isinstance(r, Refusal), f"{cell!r} must not yield a number, got {r}"
    assert "range" in r.reason


@pytest.mark.parametrize("cell", ["15, 30, 45", "100, 225, 400"])
def test_a_list_is_never_resolved_to_one_item(cell):
    r = parse_measure(cell)
    assert isinstance(r, Refusal)
    assert "several" in r.reason


@pytest.mark.parametrize("cell", [
    "Contact factory", "Consult factory", "N/A", "n.a.", "TBD", "—", "-",
    "", "   ", "None", "varies",
])
def test_placeholders_never_become_zero(cell):
    r = parse_measure(cell)
    assert isinstance(r, Refusal), f"{cell!r} must not yield a number, got {r}"


@pytest.mark.parametrize("cell", [
    "up to 90", "approx. 47", "approximately 47", "max 90", "min 12",
    "~47", "<10", ">100", "± 5", "nominal 24",
])
def test_qualified_figures_are_not_stated_figures(cell):
    """``up to 90`` is not the same claim as ``90``; dropping the qualifier
    would turn a bound into a dimension."""
    r = parse_measure(cell)
    assert isinstance(r, Refusal), f"{cell!r} must not yield a number, got {r}"


@pytest.mark.parametrize("cell", ["abc", "in", "W", "Length"])
def test_text_without_a_number_is_refused(cell):
    assert isinstance(parse_measure(cell), Refusal)


def test_a_cell_with_two_numbers_is_refused():
    """``100 A 3P`` states a current AND a pole count; picking one is a
    guess about which column the reader wanted."""
    r = parse_measure("100 A 3P")
    assert isinstance(r, Refusal)
    assert "2 numbers" in r.reason


def test_undecodable_text_is_refused_not_guessed():
    r = parse_measure("47.7� in")
    assert isinstance(r, Refusal)
    assert "decoded" in r.reason


def test_refusal_is_falsey_and_carries_the_raw_cell():
    r = parse_measure("Contact factory")
    assert not r
    assert r.raw == "Contact factory"
    assert "Contact factory" in str(r)


def test_none_and_non_string_do_not_raise():
    """Failure class (c): an exception escaping withholds the file."""
    assert isinstance(parse_measure(None), Refusal)


# --------------------------------------------------------------------------
# conversion is OURS, and exact
# --------------------------------------------------------------------------

def test_to_inches_is_exact_and_only_for_lengths():
    assert to_inches(Measure(1.0, "ft")).value == IN_PER_FT
    assert to_inches(Measure(25.4, "mm")).value == pytest.approx(1.0)
    assert to_inches(Measure(2.54, "cm")).value == pytest.approx(1.0)
    assert to_inches(Measure(47.75, "in")).value == 47.75
    # not a length, or no unit at all -> we do not assume what it means
    assert to_inches(Measure(38.0, "W")) is None
    assert to_inches(Measure(38.0, "")) is None

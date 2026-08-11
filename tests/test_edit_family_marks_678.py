"""test_edit_family_marks_678.py -- the family edit lane reads the trade's
inch / foot MARKS (#678; Refs #668 #659 #665).

``rvt.convert.modify_family._UNIT_TOKENS`` always listed ``"`` (inch) and
``'`` (foot) -- and the generic refusal's offer named them -- but
``_convert_value`` opened with ``str(raw).strip().strip("\\"'")``, which ate a
TRAILING mark before the number/unit regex ran.  So ``--set 'Width=4"'`` and
``--set "Depth=2'"`` reached the converter as a bare ``4`` / ``2`` and were
refused as unitless lengths ("units are never guessed"), and ``1'6"`` could
not be read at all.  Shell quoting was never the cause: the mark is lost at
Python level, inside the converter (proven below without any CLI).

Now ONE pair of quotes cleanly WRAPPING a value still comes off (``"600 mm"``,
``'4"'``, ``'DP-7'``), nothing else is stripped, and a mark converts through
the ONE length row (sizes included, #668): ``4"`` -> 1/3 ft, ``2'`` -> 2 ft,
``1'6"`` / ``1' 6"`` / ``1'-6"`` -> 1.5 ft; a mark on a non-length spec is
refused BY NAME like any wrong-kind unit; every ambiguous quote arrangement
(``4''`` -- two apostrophes typed for an inch --, ``4'"``, ``''4''``) is
refused by name or as unreadable, never read as feet; a bare number is refused
exactly as before.  ``4 in`` and ``4"`` write byte-identical families.

Tiers: (1) the pure converter on synthetic parameter rows (no file);
(2) ON A WRITTEN cable-tray fitting ``.rfa`` through the real CLI entry
(``rvt.convert.edit_family.main``) and the JSON-ops route: read-back via
``inventory_family``, family-mode VALID 0 errors, provenance clean after every
edit.  Validator-green is a fact about the file, never evidence that Revit
opens it (hard rule 4); no certification is claimed.

Run: .venv/bin/python -m pytest tests/test_edit_family_marks_678.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import needs_schema                              # noqa: E402
from rvt.convert import modify_family as MFAM                  # noqa: E402

import test_edit_family_mass_659 as T659                       # noqa: E402  (helpers + pinned strings only)
import test_edit_family_size_668 as T668                       # noqa: E402  (the fitting writer + pinned strings only)

LENGTH_SPEC = T668.LENGTH_SPEC
TRAY_SPEC = T668.TRAY_SPEC
CAVEAT = T668.CAVEAT

#: (raw --set value, stored feet, how the note quotes what was given)
MARK_ROWS = {
    "inch": ('4"', 4 / 12, '4"'),
    "foot": ("2'", 2.0, "2'"),
    "ft-in": ("1'6\"", 1.5, '18"'),                             # feet-and-inches read as inches
    "ft-in-spaced": ("1' 6\"", 1.5, '18"'),
    "ft-in-dashed": ("1'-6\"", 1.5, '18"'),
    "wrapped-inch": ("'4\"'", 4 / 12, '4"'),                     # quotes that WRAP the value still come off
    "wrapped-foot": ('"2\'"', 2.0, "2'"),
    "spaced-inch": ('4 "', 4 / 12, '4"'),                         # the JSON ops {"value": 4, "unit": "\""} spelling
}


_param = T659._param
_by_kind = pytest.mark.parametrize(
    "caption, spec, refusal",
    [("Width", LENGTH_SPEC, T659.LENGTH_REFUSAL), ("Tray Width", TRAY_SPEC, T668.TRAY_REFUSAL)],
    ids=["length", "size"])


def _mark_rows(*keys):
    keys = keys or tuple(MARK_ROWS)
    return pytest.mark.parametrize("raw, want_ft, given", [MARK_ROWS[k] for k in keys], ids=keys)


def _note(caption, given, feet):
    return f"{caption}: {given} -> {feet:g} ft" + CAVEAT


# ---------------------------------------------------------------------------
# 1. the pure converter (no file) -- where the mark was lost, and is not now
# ---------------------------------------------------------------------------

@_mark_rows()
@_by_kind
def test_a_mark_converts_on_a_length_and_on_a_size(caption, spec, refusal, raw, want_ft, given):
    val, notes = MFAM._convert_value(_param(caption, spec), raw)
    assert val == pytest.approx(want_ft, abs=1e-12)
    assert notes == [_note(caption, given, want_ft)]


def test_the_marks_are_the_tables_own_tokens_not_a_second_factor():
    assert MFAM._UNIT_TOKENS['"'] == MFAM._UNIT_TOKENS["in"] == ("length", 1 / 12)
    assert MFAM._UNIT_TOKENS["'"] == MFAM._UNIT_TOKENS["ft"] == ("length", 1.0)
    assert MFAM._convert_value(_param("Width", LENGTH_SPEC), '4"') [0] == \
        MFAM._convert_value(_param("Width", LENGTH_SPEC), "4 in")[0]


@pytest.mark.parametrize("raw, mark", [('600"', '"'), ("600'", "'"), ("1'6\"", '"')])
def test_a_mark_on_a_non_length_spec_is_refused_by_name_like_any_wrong_kind_unit(raw, mark):
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Operating Weight", T659.MASS_SPEC), raw)
    assert str(ei.value) == f"Operating Weight is a mass; got unit {mark!r}"
    with pytest.raises(MFAM.FamilyEditError, match="BusRating is a current"):
        MFAM._convert_value(_param("BusRating", "autodesk.spec.aec.electrical:current-1.0.0"), raw)


@pytest.mark.parametrize("raw", ["4", '"4"', "'2'"], ids=["bare", "wrapped-dq", "wrapped-sq"])
@_by_kind
def test_a_bare_or_merely_wrapped_number_is_still_refused_units_are_never_guessed(caption, spec, refusal, raw):
    """``"4"`` / ``'2'`` are a WRAPPED bare number, not 4 in / 2 ft."""
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param(caption, spec), raw)
    assert str(ei.value) == refusal


def test_control_wrapping_quotes_still_come_off_text_and_unit_words():
    """The issue's DONE 2 controls: a quoted text value on an ``m_str``
    parameter and a quoted ``"600 mm"`` behave exactly as on main."""
    assert MFAM._convert_value(_param("PanelName", "", "m_str"), "'DP-7'") == ("DP-7", [])
    assert MFAM._convert_value(_param("PanelName", "", "m_str"), '"DP-7"') == ("DP-7", [])
    val, notes = MFAM._convert_value(_param("Width", LENGTH_SPEC), '"600 mm"')
    assert val == pytest.approx(600 / 304.8) and notes == [T659.LENGTH_NOTE_600MM]
    assert MFAM._convert_value(_param("Width", LENGTH_SPEC), "'600 mm'") == (val, notes)
    # an integer carrier ignores a mark like any unit word (noted, never converted)
    assert MFAM._convert_value(_param("Poles", "", "m_int"), '3"') == (
        3, ["Poles: unit '\"' ignored (integer parameter)"])
    # the generic refusal's offer already named both marks and still tells the truth
    assert "length ft / feet / foot / ' / in / inch / inches / \" / mm / m; " in MFAM._converted_units()


def test_what_cannot_be_read_is_still_said_plainly():
    for raw in ("6\"1'", "1'6", "'\"", "1' x 6\"", '"600 mm', "'4\""):
        with pytest.raises(MFAM.FamilyEditError, match="Width: cannot read a number from"):
            MFAM._convert_value(_param("Width", LENGTH_SPEC), raw)


#: quote arrangements that are NOT a mark: two apostrophes typed for an inch,
#: mixed / doubled marks, a "wrap" whose inside starts or ends with the same
#: quote.  Each names what it got; none is ever 4 ft / 4 in (a 12x misread).
AMBIGUOUS_BY_NAME = {"4''": "''", "4'\"": "'\"", '4""': '""', "600 mm\"": 'mm"'}
AMBIGUOUS_UNREADABLE = ("''4''", "'4''", '"4""', '"1\'6""')


@_by_kind
def test_an_ambiguous_quote_arrangement_is_refused_by_name_never_read_as_feet(caption, spec, refusal):
    kind = refusal.split(" is a ")[0]                            # the caption, as the wrong-kind wording spells it
    for raw, unit in AMBIGUOUS_BY_NAME.items():
        with pytest.raises(MFAM.FamilyEditError) as ei:
            MFAM._convert_value(_param(caption, spec), raw)
        assert str(ei.value) == f"{kind} is a length; got unit {unit!r}", raw
    for raw in AMBIGUOUS_UNREADABLE:
        with pytest.raises(MFAM.FamilyEditError) as ei:
            MFAM._convert_value(_param(caption, spec), raw)
        assert str(ei.value) == f"{kind}: cannot read a number from {raw!r}", raw
    # on a measurable spec outside the table (angle) and on a mass: still by name, still no value
    with pytest.raises(MFAM.FamilyEditError, match="no conversion for unit \"''\" on spec autodesk.spec.aec:angle"):
        MFAM._convert_value(_param("Fitting Angle", T668.ST.SPECS["angle"]), "45''")
    with pytest.raises(MFAM.FamilyEditError, match="Operating Weight is a mass; got unit \"''\""):
        MFAM._convert_value(_param("Operating Weight", T659.MASS_SPEC), "600''")
    # the unwrap itself: one clean pair off, everything else verbatim
    assert [MFAM._unwrap_measure(t) for t in ("'4\"'", '"2\'"', '"600 mm"', "4''", "''4''", "'4''", '4"')] == [
        '4"', "2'", "600 mm", "4''", "''4''", "'4''", '4"']


@pytest.mark.parametrize("caption, spec, carrier", [
    ("Poles", "", "m_int"), ("Temperature Rise", T659.NUMBER_SPEC, "m_value"), ("X", "", "m_value")],
    ids=["integer", "number", "spec-less"])
def test_feet_and_inches_stay_unreadable_where_a_unit_would_be_ignored(caption, spec, carrier):
    """Where a unit is IGNORED (integer carrier, Revit's unitless ``number``, a
    spec-less double) there is no one number written in ``1'6"`` -- it stays
    "cannot read a number", exactly as on main; never 18, never 1.5."""
    with pytest.raises(MFAM.FamilyEditError, match="cannot read a number from"):
        MFAM._convert_value(_param(caption, spec, carrier), "1'6\"")
    assert MFAM._convert_value(_param(caption, spec, carrier), "18")[0] == 18


# ---------------------------------------------------------------------------
# 2. ON THE FILE: a cable-tray fitting, through the CLI and the JSON ops route
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tray_rfa(tmp_path_factory):
    """A 12 x 4 in cable-tray elbow: Tray Width 1 ft (a SIZE), Width 1 ft (a LENGTH)."""
    path = T668._write_fitting(
        tmp_path_factory, "tray678", "cable_tray_fitting", "Tray Elbow 12x4",
        [{"shape": "box", "width_ft": 1.0, "depth_ft": 1.0, "height_ft": 4 / 12}],
        {"Tray Width": 1.0, "Tray Height": 4 / 12})
    inv = MFAM.inventory_family(path)
    assert inv.param_by_caption("Tray Width")["spec"] == TRAY_SPEC
    assert inv.param_by_caption("Width")["spec"] == LENGTH_SPEC
    return path


@needs_schema
@_mark_rows("inch", "foot", "ft-in", "ft-in-spaced")
@pytest.mark.parametrize("caption", ["Width", "Tray Width"], ids=["length", "size"])
def test_set_with_a_mark_on_the_written_fitting_reads_back_in_feet(tray_rfa, tmp_path, caption,
                                                                   raw, want_ft, given):
    rc, man, out = T659._cli_edit(tray_rfa, tmp_path, f"{caption}={raw}")
    assert rc == 0 and out and os.path.isfile(out), man
    other = "Tray Width" if caption == "Width" else "Width"
    edited, neighbour = T659._currents(out, caption, other)
    assert edited == pytest.approx(want_ft, abs=1e-12)
    assert json.loads(man["edit"]) == {"ops": [{"op": "set-param", "param": caption, "value": raw}]}  # the mark reached the engine verbatim
    changes = man["apply"]["record_changes"]
    assert changes and all(v == pytest.approx(want_ft) for v in changes.values())
    assert man["degradations"] == [_note(caption, given, want_ft)]
    T659._assert_valid_and_ours(man, out)
    assert neighbour == 1.0                            # the neighbour of the other kind stays put


@needs_schema
@pytest.mark.parametrize("caption", ["Width", "Tray Width"], ids=["length", "size"])
def test_control_four_inches_by_word_and_by_mark_write_byte_identical_families(tray_rfa, tmp_path, caption):
    rc_w, man_w, by_word = T659._cli_edit(tray_rfa, tmp_path / "word", f"{caption}=4 in")
    rc_m, man_m, by_mark = T659._cli_edit(tray_rfa, tmp_path / "mark", f'{caption}=4"')
    assert rc_w == rc_m == 0 and by_word and by_mark
    assert T659._same_bytes(by_word, by_mark)
    assert man_w["apply"]["record_changes"] == man_m["apply"]["record_changes"]
    T659._assert_valid_and_ours(man_m, by_mark)


@needs_schema
def test_on_the_file_a_wrapped_bare_size_and_a_mark_on_a_non_length_are_refused_before_anything_is_written(
        tray_rfa, tmp_path, capsys):
    """``Tray Width="4"`` is a wrapped bare number -> the length refusal;
    ``Fitting Angle=45"`` (``aec:angle``, no conversion in this lane) is
    refused naming the unit and the spec -- main stripped the mark and stored
    45 silently.  Exit 2, nothing written, the refusal is the last thing said."""
    out_dir = tmp_path / "wrapped"
    T668._assert_refused_and_nothing_written(
        *T659._cli_edit(tray_rfa, out_dir, 'Tray Width="4"'), out_dir, capsys, T668.TRAY_REFUSAL)
    out_dir = tmp_path / "angle"
    rc, man, out = T659._cli_edit(tray_rfa, out_dir, 'Fitting Angle=45"')
    assert rc == 2 and man is None and out is None
    said = capsys.readouterr().out.strip().splitlines()[-1]
    assert said.startswith("ERROR: Fitting Angle: no conversion for unit '\"' on spec autodesk.spec.aec:angle")
    assert said.endswith(T659.WAY_FORWARD)
    assert not os.path.isdir(str(out_dir)) or not os.listdir(str(out_dir))


@needs_schema
@pytest.mark.parametrize("raw, message", [
    ("4''", "Width is a length; got unit \"''\""),                # two apostrophes: refused by name, never 4 ft
    ("4'\"", "Width is a length; got unit '\\'\"'"),
    ("''4''", "Width: cannot read a number from \"''4''\""),
], ids=["two-apostrophes", "foot-inch-marks", "doubly-wrapped"])
def test_on_the_file_an_ambiguous_quote_arrangement_is_refused_before_anything_is_written(
        tray_rfa, tmp_path, capsys, raw, message):
    out_dir = tmp_path / "amb"
    T668._assert_refused_and_nothing_written(
        *T659._cli_edit(tray_rfa, out_dir, f"Width={raw}"), out_dir, capsys, message)


@needs_schema
def test_control_a_quoted_text_value_on_the_file_lands_unquoted_as_on_main(tray_rfa, tmp_path):
    rc, man, out = T659._cli_edit(tray_rfa, tmp_path, "Tray Type='Ladder'")
    assert rc == 0 and T659._current(out, "Tray Type") == "Ladder" and man["degradations"] == []
    T659._assert_valid_and_ours(man, out)


@needs_schema
def test_the_json_ops_route_shares_the_tokenizer(tray_rfa, tmp_path):
    """``{"value": "4\\""}`` inline and ``{"value": 2, "unit": "'"}`` through the
    structured ``edit_family`` normaliser (which spells it ``2 '``) both land."""
    inv = MFAM.inventory_family(tray_rfa)
    ops = json.dumps([{"op": "set", "param": "Tray Width", "value": '4"'},
                      {"op": "set", "param": "Width", "value": "1'6\""}])
    got = MFAM.parse_family_edit(ops, inv)["ops"]
    assert [o["value"] for o in got] == [pytest.approx(4 / 12), pytest.approx(1.5)]
    from rvt.convert import edit_family as EF
    rec = EF.edit_family(tray_rfa, [{"op": "set-param", "param": "Tray Width", "value": 2, "unit": "'"}],
                         str(tmp_path))
    assert rec["structured_ops"] == [{"op": "set-param", "param": "Tray Width", "value": "2 '"}]
    assert T659._current(rec["files"]["rfa"], "Tray Width") == 2.0
    assert rec["degradations"] == [_note("Tray Width", "2'", 2.0)]
    with open(os.path.join(str(tmp_path), "manifest.json")) as fh:
        T659._assert_valid_and_ours(json.load(fh), rec["files"]["rfa"])


@needs_schema
def test_the_natural_language_route_reads_a_mark_too(tray_rfa, tmp_path):
    """prompt + rfa -> rfa (``modify_family``'s own text grammar, the route the
    router runs): 'set TrayWidth 4"' lands as 1/3 ft."""
    rec = MFAM.modify_family(tray_rfa, 'set TrayWidth 4"', str(tmp_path))
    assert T659._current(rec["files"]["rfa"], "Tray Width") == pytest.approx(4 / 12)
    assert [r["ok"] for r in rec["validation"]["rfa"]["reread"]] == [True]

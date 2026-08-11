"""test_edit_family_size_668.py -- the family edit lane treats Revit's SIZE
specs as the lengths they are (#668; Refs #659 #665 #601).

Since #601 the category tables author size parameters under Revit's
discipline SIZE specs, not ``aec:length``: ``Tray Width`` / ``Tray Height``
(``electrical:cableTraySize``), ``Nominal Diameter`` (``electrical:conduitSize``
/ ``piping:pipeSize``), ``Duct Width`` (``hvac:ductSize``), wire diameters
(``electrical:wireDiameter``).  Revit stores every one of them in FEET -- they
are lengths with a discipline-specific display -- but the edit lane's
converter matched only the ``:length`` marker, so after #665
``--set "Tray Width=4 in"`` fell into the generic *no conversion for unit
'in' on spec ...cableTraySize...* refusal while a bare ``=4`` was stored as
4 ft silently: the opposite of the length policy ("units are never guessed").

Now the LENGTH row of ``modify_family._SPEC_UNITS`` governs every spec the
format's OWN units table (``famgen/assets/family_units.json``) displays in a
plain length unit -- derived (``_feet_specs``), never a second hand-kept list
of spec ids: ``in`` / ``ft`` / ``mm`` / ``m`` convert to feet with the length
note and its geometry CAVEAT, a bare number is refused with the length
wording, a unit of another kind is refused by name.  Every #665 row stays as
it was (its module runs beside this one; the control rows here reuse its
pinned strings).

Tiers: (1) the pure converter on synthetic parameter rows (no file);
(2) ON A WRITTEN cable-tray fitting and conduit fitting ``.rfa`` (generic
model + the #601 category standards, written the product's way) through the
real CLI entry (``rvt.convert.edit_family.main``): read-back via
``inventory_family``, family-mode VALID 0 errors, provenance clean after every
successful edit; refusals exit 2 with nothing written.  Validator-green is a
fact about the file, never evidence that Revit opens it (hard rule 4); no
certification is claimed.

Run: .venv/bin/python -m pytest tests/test_edit_family_size_668.py -q
"""
from __future__ import annotations

import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import needs_schema                              # noqa: E402
from rvt.convert import modify_family as MFAM                  # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402
from rvt.famgen import standards as ST                         # noqa: E402

import test_edit_family_mass_659 as T659                       # noqa: E402  (helpers + pinned strings only)

#: the five size specs #601's tables author (``standards.SPECS`` keys) -- the issue's list
SIZE_KEYS = ("cable_tray_size", "conduit_size", "wire_diameter", "duct_size", "pipe_size")
SIZE_SPECS = {k: ST.SPECS[k] for k in SIZE_KEYS}
TRAY_SPEC = SIZE_SPECS["cable_tray_size"]
CONDUIT_SPEC = SIZE_SPECS["conduit_size"]
LENGTH_SPEC = ST.SPECS["length"]

CAVEAT = (" (CAVEAT: type-table value only; the authored solid is not re-derived -- "
          "regenerate from the facts sidecar for geometry-true resizing)")
#: the length wording, kind and offer exactly as ``Width`` gets them (#659 pinned it)
TRAY_REFUSAL = T659.LENGTH_REFUSAL.replace("Width", "Tray Width", 1)
TRAY_WRONG_KIND = "Tray Width is a length; got unit 'kg'"

#: (raw --set value, stored feet, the manifest note) -- shared by both tiers
TRAY_ROWS = {
    "4in": ("4 in", 4 / 12, "Tray Width: 4 in -> 0.333333 ft" + CAVEAT),
    "100mm": ("100 mm", 100 / 304.8, "Tray Width: 100 mm -> 0.328084 ft" + CAVEAT),
    "12in": ("12 in", 1.0, "Tray Width: 12 in -> 1 ft" + CAVEAT),                  # the issue's DONE 2 rows
    "300mm": ("300 mm", 300 / 304.8, "Tray Width: 300 mm -> 0.984252 ft" + CAVEAT),
    "inches": ("4 inches", 4 / 12, "Tray Width: 4 inches -> 0.333333 ft" + CAVEAT),
    "ft": ("0.5 ft", 0.5, "Tray Width: 0.5 ft -> 0.5 ft" + CAVEAT),
    "m": ("0.1 m", 0.1 / 0.3048, "Tray Width: 0.1 m -> 0.328084 ft" + CAVEAT),
}


def _tray_rows(*keys):
    keys = keys or tuple(TRAY_ROWS)
    return pytest.mark.parametrize("raw, want_ft, note", [TRAY_ROWS[k] for k in keys], ids=keys)


def _param(caption, spec, carrier="m_value"):
    return {"caption": caption, "spec": spec, "carrier": carrier}


# ---------------------------------------------------------------------------
# 1. the pure converter (no file)
# ---------------------------------------------------------------------------

def test_the_size_specs_are_derived_from_the_units_table_not_listed_twice():
    """DONE 1's law: the spec family comes from the format's own units table
    (every spec it DISPLAYS in a plain length unit is stored in feet)."""
    feet = MFAM._feet_specs()
    for key, spec in dict(SIZE_SPECS, length=LENGTH_SPEC).items():
        assert MFAM._unversioned(spec) in feet, key
    # other dimensions never become lengths: mass, mass/length, Revit's unitless
    # number, W, lm/W, and the compound-unit guard (hvac velocity = feetPerMinute,
    # area = squareFeet mention feet but are not lengths); nor a spec-less double
    for key in ("mass", "mass_per_length", "number", "wattage", "efficacy",
                "hvac_velocity", "area", "volume", "angle"):
        assert MFAM._unversioned(ST.SPECS[key]) not in feet, key
    assert "" not in feet


@_tray_rows()
def test_a_size_converts_every_length_unit_to_feet_with_the_length_note(raw, want_ft, note):
    val, notes = MFAM._convert_value(_param("Tray Width", TRAY_SPEC), raw)
    assert val == pytest.approx(want_ft, abs=1e-12)
    assert notes == [note]


@pytest.mark.parametrize("key", SIZE_KEYS)
def test_every_size_spec_refuses_a_bare_number_exactly_like_a_length(key):
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Tray Width", SIZE_SPECS[key]), "4")
    assert str(ei.value) == TRAY_REFUSAL
    assert MFAM._convert_value(_param("X", SIZE_SPECS[key]), "100 mm")[0] == pytest.approx(100 / 304.8)


@pytest.mark.parametrize("unit", ["kg", "lb", "V", "Hz", "W"])
def test_a_size_refuses_a_unit_of_another_kind_by_name(unit):
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Tray Width", TRAY_SPEC), f"4 {unit}")
    assert str(ei.value) == f"Tray Width is a length; got unit '{unit.lower()}'"


def test_an_unknown_unit_on_a_size_is_refused_as_on_a_length_never_ignored():
    """``4 cm``: no ``cm`` token in this lane -- refused as the wrong kind (the
    length row's pre-existing behaviour for an unknown token), never stored."""
    for spec in (TRAY_SPEC, LENGTH_SPEC):
        with pytest.raises(MFAM.FamilyEditError, match="is a length; got unit 'cm'"):
            MFAM._convert_value(_param("Tray Width", spec), "4 cm")


def test_control_the_665_rows_and_the_generic_refusals_offer_are_untouched():
    """The length / mass / identity rows and the "this lane converts: ..." offer
    are byte-for-byte #665's (its module pins them; re-asserted here so a size
    change that moved them fails in THIS module too)."""
    val, notes = MFAM._convert_value(_param("Width", LENGTH_SPEC), "600 mm")
    assert val == pytest.approx(600 / 304.8) and notes == [T659.LENGTH_NOTE_600MM]
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Width", LENGTH_SPEC), "600")
    assert str(ei.value) == T659.LENGTH_REFUSAL
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Operating Weight", T659.MASS_SPEC), "600")
    assert str(ei.value) == T659.MASS_REFUSAL
    for caption, spec, raw, stored, note in T659.IDENTITY_ROWS:
        assert MFAM._convert_value(_param(caption, spec), raw) == (stored, [note])
    # the offer lists UNITS, and a size takes exactly the length units -- still truthful, unchanged
    assert "length ft / feet / foot / ' / in / inch / inches / \" / mm / m; " in MFAM._converted_units()
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Efficacy", T659.EFFICACY_SPEC), "100 lpw")
    assert str(ei.value).startswith("Efficacy: " + T659.NO_CONVERSION)
    assert str(ei.value).endswith(T659.WAY_FORWARD)


# ---------------------------------------------------------------------------
# 2. ON THE FILE: a cable-tray fitting and a conduit fitting, through the CLI
# ---------------------------------------------------------------------------

def _write_fitting(tmp_path_factory, tag, category, name, parts, values):
    """A generic-model-route family in a containment category, carrying its
    #601 standards with the size values FILLED (internal feet), written the
    product's way (bundled base, family-mode validated, provenance-scanned)."""
    from rvt.frontdoor.standalone import standalone_family_write
    path = str(tmp_path_factory.mktemp(tag) / f"{tag}.rfa")
    prod = F.make_generic_model(parts=parts, name=name, category=category,
                                standard_values=values)
    assert set(values) <= set(prod.standards["filled"]), prod.standards
    rep = standalone_family_write(prod, path)
    fam = (rep.get("validate") or {}).get("family_mode") or {}
    assert fam.get("verdict") == "VALID" and fam.get("n_errors") == 0, fam.get("errors")
    assert (rep.get("provenance") or {}).get("ok") is True, rep["provenance"].get("suspects")
    return path


@pytest.fixture(scope="module")
def tray_rfa(tmp_path_factory):
    """A 12 x 4 in cable-tray elbow: Tray Width 1 ft, Tray Height 4 in."""
    path = _write_fitting(
        tmp_path_factory, "tray668", "cable_tray_fitting", "Tray Elbow 12x4",
        [{"shape": "box", "width_ft": 1.0, "depth_ft": 1.0, "height_ft": 4 / 12}],
        {"Tray Width": 1.0, "Tray Height": 4 / 12})
    tw = MFAM.inventory_family(path).param_by_caption("Tray Width")
    assert (tw["spec"], tw["carrier"], tw["current"]) == (TRAY_SPEC, "m_value", 1.0)
    return path


@pytest.fixture(scope="module")
def conduit_rfa(tmp_path_factory):
    """A 1 in EMT coupling: Nominal Diameter 1/12 ft."""
    path = _write_fitting(
        tmp_path_factory, "conduit668", "conduit_fitting", "EMT Coupling 1in",
        [{"shape": "cylinder", "radius_ft": 0.5 / 12, "height_ft": 0.5}],
        {"Nominal Diameter": 1 / 12})
    nd = MFAM.inventory_family(path).param_by_caption("Nominal Diameter")
    assert (nd["spec"], nd["carrier"]) == (CONDUIT_SPEC, "m_value")
    assert nd["current"] == pytest.approx(1 / 12)
    return path


def _assert_refused_and_nothing_written(rc, man, out, out_dir, capsys, message):
    assert rc == 2 and man is None and out is None
    assert capsys.readouterr().out.strip().splitlines()[-1] == "ERROR: " + message   # the refusal is the last thing said
    assert not os.path.isdir(str(out_dir)) or not os.listdir(str(out_dir))


@needs_schema
@_tray_rows("4in", "100mm", "12in", "300mm")                    # token aliasing (inches / ft / m) is tier 1's
def test_set_tray_width_on_the_written_fitting_reads_back_in_feet(tray_rfa, tmp_path, raw, want_ft, note):
    rc, man, out = T659._cli_edit(tray_rfa, tmp_path, f"Tray Width={raw}")
    assert rc == 0 and out and os.path.isfile(out), man
    width, height, geom_w = T659._currents(out, "Tray Width", "Tray Height", "Width")
    assert width == pytest.approx(want_ft, abs=1e-12)
    changes = man["apply"]["record_changes"]
    assert changes and all(v == pytest.approx(want_ft) for v in changes.values())
    assert any(k.startswith("m_familyParams.") for k in changes)          # the current-defaults mirror
    assert sum(k.startswith("m_pFamilyTypes.") for k in changes) == 1     # the one type row
    assert man["degradations"] == [note]                                  # the length note + CAVEAT
    T659._assert_valid_and_ours(man, out)
    # untouched neighbours stay put: the other size and the geometry length
    assert height == pytest.approx(4 / 12) and geom_w == 1.0


@needs_schema
def test_a_bare_tray_width_is_refused_before_anything_is_written(tray_rfa, tmp_path, capsys):
    out_dir = tmp_path / "bare"
    _assert_refused_and_nothing_written(*T659._cli_edit(tray_rfa, out_dir, "Tray Width=4"),
                                        out_dir, capsys, TRAY_REFUSAL)


@needs_schema
def test_a_tray_width_in_kilograms_is_refused_by_name_before_anything_is_written(tray_rfa, tmp_path, capsys):
    out_dir = tmp_path / "kg"
    _assert_refused_and_nothing_written(*T659._cli_edit(tray_rfa, out_dir, "Tray Width=4 kg"),
                                        out_dir, capsys, TRAY_WRONG_KIND)


@needs_schema
def test_the_conduit_fittings_nominal_diameter_converts_and_refuses_the_same_way(conduit_rfa, tmp_path, capsys):
    rc, man, out = T659._cli_edit(conduit_rfa, tmp_path / "mm", "Nominal Diameter=27 mm")
    assert rc == 0 and T659._current(out, "Nominal Diameter") == pytest.approx(27 / 304.8)
    assert man["degradations"] == ["Nominal Diameter: 27 mm -> 0.0885827 ft" + CAVEAT]
    T659._assert_valid_and_ours(man, out)
    rc, man, out = T659._cli_edit(conduit_rfa, tmp_path / "in", "Nominal Diameter=1.25 in")
    assert rc == 0 and T659._current(out, "Nominal Diameter") == pytest.approx(1.25 / 12)
    T659._assert_valid_and_ours(man, out)
    out_dir = tmp_path / "bare"
    _assert_refused_and_nothing_written(
        *T659._cli_edit(conduit_rfa, out_dir, "Nominal Diameter=1.25"), out_dir, capsys,
        "Nominal Diameter is a LENGTH: give an explicit unit (in / ft / mm / m) -- units are never guessed")


@needs_schema
def test_control_the_plain_lengths_on_the_same_fitting_behave_exactly_as_on_main(tray_rfa, tmp_path):
    """``Bend Radius`` (``aec:length``, blank) and the geometry ``Width``: the
    same branch, the same strings ``main`` produced -- a size joining the row
    moved nothing for the lengths already on it."""
    rc, man, out = T659._cli_edit(tray_rfa, tmp_path / "br", "Bend Radius=6 in")
    assert rc == 0 and T659._current(out, "Bend Radius") == pytest.approx(0.5)
    assert man["degradations"] == ["Bend Radius: 6 in -> 0.5 ft" + CAVEAT]
    T659._assert_valid_and_ours(man, out)
    rc, man, out = T659._cli_edit(tray_rfa, tmp_path / "w", "Width=600 mm")
    assert rc == 0 and T659._current(out, "Width") == pytest.approx(600 / 304.8)
    assert man["degradations"] == [T659.LENGTH_NOTE_600MM]
    rc, man, out = T659._cli_edit(tray_rfa, tmp_path / "nolen", "Width=600")
    assert rc == 2 and out is None


@needs_schema
def test_the_natural_language_and_json_routes_share_the_size_conversion(tray_rfa, tmp_path):
    """prompt + rfa -> rfa (``modify_family``, the route the router runs):
    'set TrayWidth 4 in' lands as 1/3 ft; the JSON ops form refuses a bare
    size.  (One-word caption on the text route: #663, pre-existing.)"""
    rec = MFAM.modify_family(tray_rfa, "set TrayWidth 4 in", str(tmp_path))
    assert T659._current(rec["files"]["rfa"], "Tray Width") == pytest.approx(4 / 12)
    assert [r["ok"] for r in rec["validation"]["rfa"]["reread"]] == [True]
    inv = MFAM.inventory_family(tray_rfa)
    with pytest.raises(MFAM.FamilyEditError, match=re.escape(TRAY_REFUSAL)):
        MFAM.parse_family_edit("set TrayWidth 4", inv)
    ops = json.dumps([{"op": "set", "param": "Tray Height", "value": "150 mm"}])
    assert MFAM.parse_family_edit(ops, inv)["ops"][0]["value"] == pytest.approx(150 / 304.8)

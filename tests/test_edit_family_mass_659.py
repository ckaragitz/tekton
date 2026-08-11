"""test_edit_family_mass_659.py -- the family edit lane converts a MASS
(#659; Refs #630).

#630 made generated transformers carry a filled ``Operating Weight``
(``autodesk.spec.aec.structural:mass-1.0.0``, stored in kilograms -- Revit's
internal mass unit).  The edit lane's spec-driven converter
(``rvt.convert.modify_family._convert_value``) had no mass branch, so
``--set "Operating Weight=600 lb"`` stored 600.0 (read by Revit as 600 kg =
1323 lb) under the false note *unit 'lb' ignored (dimensionless spec
...mass...)*, and a unitless ``=600`` was stored silently although a unitless
LENGTH is refused ("units are never guessed").

Now: ``lb`` / ``lbs`` / ``lbm`` -> x ``rvt.famgen.factory.KG_PER_LB`` (the ONE
constant, imported -- no second literal), ``kg`` -> as is, no unit -> refused
exactly like a length, and a unit on a measurable spec the lane merely lacks a
conversion for (``Frequency=60 Hz``) is refused BY NAME instead of being
stored under the false "dimensionless" note; only Revit's unitless ``number``
(and a spec-less double) still ignores a unit suffix.  Lengths and
dimensionless numbers behave byte-for-byte as before (control rows pin the
exact strings ``main`` produced).

Tiers: (1) the pure converter on synthetic parameter rows (no file);
(2) ON A WRITTEN #630 transformer ``.rfa`` through the real CLI entry
(``rvt.convert.edit_family.main``): read-back via ``inventory_family``,
family-mode VALID 0 errors, provenance clean after every successful edit.
Validator-green is a fact about the file, never evidence that Revit opens it
(hard rule 4); no certification is claimed.

Run: .venv/bin/python -m pytest tests/test_edit_family_mass_659.py -q
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import needs_schema                              # noqa: E402
from rvt.convert import edit_family as EF                      # noqa: E402
from rvt.convert import modify_family as MFAM                  # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402
from rvt.famgen import standards as ST                         # noqa: E402

MASS_SPEC = "autodesk.spec.aec.structural:mass-1.0.0"          # pinned literally: the id #630 writes
LENGTH_SPEC = ST.SPECS["length"]
NUMBER_SPEC = ST.SPECS["number"]
FREQ_SPEC = ST.SPECS["frequency"]
MASS_PER_LENGTH_SPEC = ST.SPECS["mass_per_length"]

#: the exact strings ``main`` produced before #659 -- control rows must not move
LENGTH_NOTE_600MM = ("Width: 600 mm -> 1.9685 ft (CAVEAT: type-table value only; the "
                     "authored solid is not re-derived -- regenerate from the facts "
                     "sidecar for geometry-true resizing)")
LENGTH_REFUSAL = ("Width is a LENGTH: give an explicit unit (in / ft / mm / m) -- "
                  "units are never guessed")
DIMLESS_NOTE_115C = f"Temperature Rise: unit 'c' ignored (dimensionless spec {NUMBER_SPEC})"
#: the wording #659 picked (pinned): a MASS refuses like a length ...
MASS_REFUSAL = ("Operating Weight is a MASS: give an explicit unit (lb / kg) -- "
                "units are never guessed")
#: ... and a measurable spec without a conversion is refused BY NAME
NO_CONVERSION = "no conversion for unit 'hz' on spec " + FREQ_SPEC

#: (raw --set value, stored kg, the manifest note) -- shared by the pure and the on-file tiers
MASS_ROWS = {
    "lb": ("600 lb", 600 * F.KG_PER_LB, "Operating Weight: 600 lb -> 272.155 kg"),
    "lbs": ("600 lbs", 600 * F.KG_PER_LB, "Operating Weight: 600 lbs -> 272.155 kg"),
    "lbm": ("600lbm", 600 * F.KG_PER_LB, "Operating Weight: 600 lbm -> 272.155 kg"),
    "LB": ("600 LB", 600 * F.KG_PER_LB, "Operating Weight: 600 lb -> 272.155 kg"),
    "kg": ("272.155 kg", 272.155, "Operating Weight: 272.155 kg -> 272.155 kg"),
    "zero": ("0 kg", 0.0, "Operating Weight: 0 kg -> 0 kg"),
}


def _mass_rows(*keys):
    keys = keys or tuple(MASS_ROWS)
    return pytest.mark.parametrize("raw, want_kg, note", [MASS_ROWS[k] for k in keys], ids=keys)


def _param(caption, spec, carrier="m_value"):
    return {"caption": caption, "spec": spec, "carrier": carrier}


# ---------------------------------------------------------------------------
# 1. the pure converter (no file)
# ---------------------------------------------------------------------------

def test_one_constant_the_factorys_pound_is_the_edit_lanes_pound():
    assert MFAM.KG_PER_LB is F.KG_PER_LB
    assert MFAM._UNIT_TOKENS["kg"] == ("mass", 1.0)           # Revit's internal mass unit is the kilogram
    for tok in ("lb", "lbs", "lbm"):
        assert MFAM._UNIT_TOKENS[tok] == ("mass", F.KG_PER_LB), tok


def test_no_second_pound_literal_anywhere_in_the_engine():
    """DONE 2: ``git grep -n 0.4535 -- src/`` finds exactly one definition."""
    hits = [(str(p.relative_to(ROOT)), n, line.strip())
            for p in sorted(Path(ROOT, "src", "rvt").rglob("*.py"))
            for n, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1)
            if "0.4535" in line]
    assert [(p, line.split("=")[0].strip()) for p, _n, line in hits] == [
        (os.path.join("src", "rvt", "famgen", "factory.py"), "KG_PER_LB")], hits


@_mass_rows()
def test_a_mass_converts_pounds_to_kilograms_and_takes_kilograms_as_is(raw, want_kg, note):
    val, notes = MFAM._convert_value(_param("Operating Weight", MASS_SPEC), raw)
    assert val == pytest.approx(want_kg, abs=1e-9)
    assert notes == [note]
    assert not any("dimensionless" in n for n in notes)


def test_a_unitless_mass_is_refused_exactly_like_a_unitless_length():
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Operating Weight", MASS_SPEC), "600")
    assert str(ei.value) == MASS_REFUSAL
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Width", LENGTH_SPEC), "600")
    assert str(ei.value) == LENGTH_REFUSAL                       # control: unchanged from main


def test_a_mass_refuses_a_unit_of_another_kind():
    with pytest.raises(MFAM.FamilyEditError, match="Operating Weight is a mass; got unit 'mm'"):
        MFAM._convert_value(_param("Operating Weight", MASS_SPEC), "600 mm")
    with pytest.raises(MFAM.FamilyEditError, match="Width is a length; got unit 'kg'"):
        MFAM._convert_value(_param("Width", LENGTH_SPEC), "600 kg")


def test_control_a_length_converts_with_the_same_note_as_on_main():
    val, notes = MFAM._convert_value(_param("Width", LENGTH_SPEC), "600 mm")
    assert val == pytest.approx(600 / 304.8)
    assert notes == [LENGTH_NOTE_600MM]


@pytest.mark.parametrize("spec", [NUMBER_SPEC, ""], ids=["number", "spec-less"])
def test_control_a_dimensionless_number_still_ignores_a_unit_suffix(spec):
    val, notes = MFAM._convert_value(_param("Temperature Rise", spec), "115 C")
    assert val == 115.0
    assert notes == [f"Temperature Rise: unit 'c' ignored (dimensionless spec {spec})"]
    assert MFAM._convert_value(_param("Temperature Rise", spec), "115") == (115.0, [])
    # the kA decoration on a number-spec short-circuit rating: unchanged
    assert MFAM._convert_value(_param("ShortCircuitRatingkA", spec), "65 kA")[0] == 65.0


def test_a_measurable_spec_without_a_conversion_is_refused_by_name_not_called_dimensionless():
    """``Frequency=60 Hz``: main stored 60.0 under *unit 'hz' ignored
    (dimensionless spec ...frequency...)* -- false, a frequency is measurable.
    The lane now says it has no conversion and how to proceed; a bare number
    is still stored as Revit internal units, as before."""
    with pytest.raises(MFAM.FamilyEditError) as ei:
        MFAM._convert_value(_param("Frequency", FREQ_SPEC), "60 Hz")
    msg = str(ei.value)
    assert msg.startswith("Frequency: " + NO_CONVERSION)
    assert "dimensionless" not in msg and "units are never guessed" in msg
    assert "no unit suffix" in msg                              # the way forward is named
    assert MFAM._convert_value(_param("Frequency", FREQ_SPEC), "60") == (60.0, [])


def test_mass_per_unit_length_is_not_mistaken_for_a_mass():
    """``structural:massPerUnitLength`` shares the ``:mass`` prefix; it has no
    conversion here and must be refused by name, never scaled by KG_PER_LB."""
    with pytest.raises(MFAM.FamilyEditError, match="no conversion for unit 'lb'"):
        MFAM._convert_value(_param("Linear Weight", MASS_PER_LENGTH_SPEC), "5 lb")


def test_the_electrical_branches_are_untouched():
    amps = _param("BusRating", "autodesk.spec.aec.electrical:current-1.0.0")
    assert MFAM._convert_value(amps, "225 A") == (225.0, [])
    assert MFAM._convert_value(amps, "225") == (225.0, [])
    volts = _param("Voltage", "autodesk.spec.aec.electrical:potential-1.0.0")
    assert MFAM._convert_value(volts, "208 V")[0] == pytest.approx(208 / 0.3048 ** 2)
    kva = _param("kVA Rating", "autodesk.spec.aec.electrical:apparentPower-1.0.0")
    assert MFAM._convert_value(kva, "30 kVA")[0] == pytest.approx(30000 / 0.3048 ** 2)
    with pytest.raises(MFAM.FamilyEditError, match="is a current"):
        MFAM._convert_value(amps, "225 lb")


# ---------------------------------------------------------------------------
# 2. ON THE FILE: a #630 transformer, edited through the CLI entry point
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def xfmr_rfa(tmp_path_factory):
    """A multi-type Eaton transformer written the product's way (bundled base,
    family-mode validated, provenance-scanned) -- Operating Weight filled."""
    from rvt.frontdoor.standalone import standalone_family_write
    path = str(tmp_path_factory.mktemp("xfmr659") / "xfmr.rfa")
    rep = standalone_family_write(F.make_transformer(kva=30, types=[30, 45, 75]), path)
    fam = (rep.get("validate") or {}).get("family_mode") or {}
    assert fam.get("verdict") == "VALID" and fam.get("n_errors") == 0, fam.get("errors")
    assert (rep.get("provenance") or {}).get("ok") is True, rep["provenance"].get("suspects")
    ow = MFAM.inventory_family(path).param_by_caption("Operating Weight")
    assert ow["spec"] == MASS_SPEC and ow["carrier"] == "m_value"
    assert ow["current"] == pytest.approx(409 * F.KG_PER_LB)   # the catalog's 409 lb, in kg
    return path


def _cli_edit(rfa, out_dir, *sets):
    """``python -m rvt.convert.edit_family <rfa> -o <out> --set ...`` in-process.
    Returns (exit code, manifest or None, edited path or None)."""
    argv = [rfa, "-o", str(out_dir)]
    for s in sets:
        argv += ["--set", s]
    rc = EF.main(argv)
    man_path = os.path.join(str(out_dir), "manifest.json")
    if not os.path.isfile(man_path):
        return rc, None, None
    with open(man_path) as fh:
        man = json.load(fh)
    files = man.get("files") or {}
    return rc, man, files.get("rfa")


def _currents(path, *captions):
    inv = MFAM.inventory_family(path)
    return [inv.param_by_caption(c)["current"] for c in captions]


def _current(path, caption):
    return _currents(path, caption)[0]


def _assert_valid_and_ours(man, path):
    """Family-mode VALID 0 errors / 0 warnings (the route's own gate = the
    family-mode arbiter run on the delivered file) + release preserved + re-read
    proven + structurally clean, and provenance clean (a fresh scan -- the
    route does not run one)."""
    g = man["validation"]["rfa"]
    assert g["family_mode"] == {"verdict": "VALID", "n_errors": 0, "n_warnings": 0}, g
    assert g["release"]["preserved"] is True and all(r["ok"] for r in g["reread"])
    assert man["apply"]["structural_ok"] is True
    prov = F.provenance_scan(path)
    assert prov["ok"] is True, prov.get("suspects")


@needs_schema
@_mass_rows("lb", "kg")                                        # token aliasing (lbs / lbm / LB) is tier 1's
def test_set_operating_weight_on_the_written_transformer_reads_back_in_kilograms(
        xfmr_rfa, tmp_path, raw, want_kg, note):
    rc, man, out = _cli_edit(xfmr_rfa, tmp_path, f"Operating Weight={raw}")
    assert rc == 0 and out and os.path.isfile(out), man
    weight, width, rise = _currents(out, "Operating Weight", "Width", "Temperature Rise")
    assert weight == pytest.approx(want_kg, abs=1e-9)
    # every type row AND the current-defaults mirror carry the converted value
    changes = man["apply"]["record_changes"]
    assert changes and all(v == pytest.approx(want_kg) for v in changes.values())
    assert any(k.startswith("m_familyParams.") for k in changes)
    assert sum(k.startswith("m_pFamilyTypes.") for k in changes) == 3     # 30 / 45 / 75 kVA rows
    assert man["degradations"] == [note]                       # the honest note, never "dimensionless"
    _assert_valid_and_ours(man, out)
    # untouched neighbours stay put (Width 24.88 in, Temperature Rise 150)
    assert width == pytest.approx(_current(xfmr_rfa, "Width")) and rise == 150.0


@needs_schema
def test_a_unitless_operating_weight_is_refused_and_nothing_half_written(xfmr_rfa, tmp_path, capsys):
    rc, man, out = _cli_edit(xfmr_rfa, tmp_path, "Operating Weight=600")
    assert rc == 2 and man is None and out is None
    assert capsys.readouterr().out.strip() == "ERROR: " + MASS_REFUSAL
    assert not any(f.endswith(".rfa") for f in os.listdir(str(tmp_path)))


@needs_schema
def test_hz_on_the_transformers_frequency_is_refused_by_name(xfmr_rfa, tmp_path, capsys):
    rc, _man, out = _cli_edit(xfmr_rfa, tmp_path, "Frequency=60 Hz")
    assert rc == 2 and out is None
    printed = capsys.readouterr().out.strip()
    assert printed.startswith("ERROR: Frequency: " + NO_CONVERSION) and "dimensionless" not in printed
    # the bare number is stored as internal units, exactly as on main
    rc, man, out = _cli_edit(xfmr_rfa, tmp_path / "bare", "Frequency=60")
    assert rc == 0 and _current(out, "Frequency") == 60.0 and man["degradations"] == []


@needs_schema
def test_control_rows_on_the_file_a_length_and_a_dimensionless_number_behave_as_on_main(
        xfmr_rfa, tmp_path):
    rc, man, out = _cli_edit(xfmr_rfa, tmp_path / "len", "Width=600 mm")
    assert rc == 0 and _current(out, "Width") == pytest.approx(600 / 304.8)
    assert man["degradations"] == [LENGTH_NOTE_600MM]
    _assert_valid_and_ours(man, out)
    rc, man, out = _cli_edit(xfmr_rfa, tmp_path / "num", "Temperature Rise=115 C")
    assert rc == 0 and _current(out, "Temperature Rise") == 115.0
    assert man["degradations"] == [DIMLESS_NOTE_115C]
    _assert_valid_and_ours(man, out)
    rc, man, out = _cli_edit(xfmr_rfa, tmp_path / "nolen", "Width=600")
    assert rc == 2 and out is None


@needs_schema
def test_the_natural_language_route_converts_the_same_mass(xfmr_rfa, tmp_path):
    """prompt + rfa -> rfa (``modify_family``, the route the router runs) shares
    the converter: 'set OperatingWeight 600 lb' lands as 272.155 kg.  (The
    caption is spelled as one word: the built-in text grammar splits a clause
    at its first word and matches captions space-insensitively -- pre-existing,
    unchanged here; the structured ``--set "Operating Weight=..."`` form above
    takes the spaced caption.)"""
    rec = MFAM.modify_family(xfmr_rfa, "set OperatingWeight 600 lb", str(tmp_path))
    out = rec["files"]["rfa"]
    assert _current(out, "Operating Weight") == pytest.approx(600 * F.KG_PER_LB)
    assert [r["ok"] for r in rec["validation"]["rfa"]["reread"]] == [True]
    inv = MFAM.inventory_family(xfmr_rfa)
    with pytest.raises(MFAM.FamilyEditError, match=re.escape(MASS_REFUSAL)):
        MFAM.parse_family_edit("set OperatingWeight 600", inv)
    ops = json.dumps([{"op": "set", "param": "Operating Weight", "value": "600 lbs"}])
    assert MFAM.parse_family_edit(ops, inv)["ops"][0]["value"] == pytest.approx(600 * F.KG_PER_LB)

"""test_modify_family_carrier.py -- rvt.convert.modify_family resolves the
value carrier from the parameter definition's STORAGE CLASS (#354).

Under the storage-class law (#333 round 24, landed in #336) our generated
families author a Text parameter as ``ParamDefString`` and an Integer
parameter as ``ParamDefInt`` -- both WITHOUT ``m_specTypeId``.  The
family-edit inventory must therefore key the carrier on the pointer class
NAME the file's own schema resolves (``ParamDefString`` -> ``m_str``,
``ParamDefInt`` -> ``m_int``) and only fall back to the spec of a
``ParamDefValue``; otherwise ``set PanelName DP-9`` lands in the numeric
branch and is refused.

Self-contained: the family is generated fresh from the bundled catalog +
genesis base (no ``samples/``, no pre-built experiment output), so this file
runs green in a fresh clone and rides in the CI shard
(``tests/ci_shard.d/354-modify-family-carrier.txt``).
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


# ---------------------------------------------------------------------------
# the pure rule (no file needed)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("def_class, spec, want", [
    ("ParamDefString", "", "m_str"),                          # the law: no spec at all
    ("ParamDefInt", "", "m_int"),                             # the law: no spec at all
    ("ParamDefValue", "autodesk.spec.aec.electrical:current-1.0.0", "m_value"),
    ("ParamDefValue", "autodesk.spec.aec:length-1.0.0", "m_value"),
    # pre-law files (spec-typed string / int64 on a ParamDefValue) still resolve
    ("ParamDefValue", "autodesk.spec:spec.string-2.0.0", "m_str"),
    ("ParamDefValue", "autodesk.spec:spec.int64-2.0.0", "m_int"),
    ("", "", "m_value"),
])
def test_carrier_follows_storage_class_then_spec(def_class, spec, want):
    assert MFAM._carrier_for_param(def_class, spec) == want


# ---------------------------------------------------------------------------
# a family built under the new law: inventory + edit a Text AND an Integer
# ---------------------------------------------------------------------------

def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=225, spaces=42,
                                   voltage="208Y/120", mcb=True,
                                   mounting="surface", panel_name="X")
        return True
    except Exception:                                          # noqa: BLE001
        return False


needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")


@pytest.fixture(scope="module")
def law_rfa(tmp_path_factory):
    """A panelboard .rfa generated NOW (so it carries ParamDefString /
    ParamDefInt definitions per the storage-class law)."""
    from rvt.famgen import factory as F
    prod = F.make_panelboard(mains_a=225, spaces=42, voltage="208Y/120", mcb=True,
                             mounting="surface", panel_name="DP-1")
    path = str(tmp_path_factory.mktemp("law") / "panel_225a.rfa")
    rep = prod.write(path, validate=False, provenance=False)
    assert rep["verify"]["ok"], rep
    return path


@needs_schema
@needs_catalog
def test_inventory_lists_text_and_integer_params_by_storage_class(law_rfa):
    inv = MFAM.inventory_family(law_rfa)
    by_cap = {p["caption"]: p for p in inv.params}
    # the law really is in force on this file: no spec on the two classes
    assert by_cap["PanelName"]["def_class"] == "ParamDefString"
    assert by_cap["PanelName"]["spec"] == ""
    assert by_cap["NumberOfCircuits"]["def_class"] == "ParamDefInt"
    assert by_cap["NumberOfCircuits"]["spec"] == ""
    # ... and the carrier follows the class
    assert by_cap["PanelName"]["carrier"] == "m_str"
    assert by_cap["PanelName"]["current"] == "DP-1"
    assert by_cap["NumberOfCircuits"]["carrier"] == "m_int"
    assert by_cap["NumberOfCircuits"]["current"] == 42
    # measurable specs are untouched: still spec-driven doubles
    assert by_cap["BusRating"]["def_class"] == "ParamDefValue"
    assert by_cap["BusRating"]["carrier"] == "m_value"
    assert "electrical:current" in by_cap["BusRating"]["spec"]
    # --inventory's JSON names the kind in so many words: PanelName is text
    js = json.loads(json.dumps(inv.as_json(), default=str))
    kinds = {p["caption"]: p["kind"] for p in js["params"]}
    assert (kinds["PanelName"], kinds["NumberOfCircuits"], kinds["BusRating"]) == (
        "text", "integer", "number")


@needs_schema
@needs_catalog
def test_edit_text_and_integer_params_end_to_end(law_rfa, tmp_path):
    """`set PanelName DP-9; set NumberOfCircuits 30` on a law-built family:
    delivered, family-mode VALID 0 errors, release preserved, both values
    echoed by the semantic re-read on their class-decided carriers."""
    rec = MFAM.modify_family(law_rfa, "set PanelName DP-9; set NumberOfCircuits 30",
                             str(tmp_path))
    assert rec["deliverables"], rec.get("errors")
    g = rec["validation"]["rfa"]
    assert g["family_mode"]["verdict"] == "VALID" and g["family_mode"]["n_errors"] == 0
    assert g["release"]["preserved"] is True
    assert [(r["caption"], r["got"], r["ok"]) for r in g["reread"]] == [
        ("PanelName", "DP-9", True), ("NumberOfCircuits", 30, True)]
    assert rec["apply"]["structural_ok"] is True
    # the edited file inventories the new values on the same carriers
    inv = MFAM.inventory_family(next(iter(rec["files"].values())))
    cur = {p["caption"]: p["current"] for p in inv.params}
    assert cur["PanelName"] == "DP-9" and cur["NumberOfCircuits"] == 30


@needs_schema
@needs_catalog
def test_text_param_no_longer_refused_as_a_number(law_rfa):
    """The exact #354 symptom: parsing 'set PanelName DP-9' must not raise
    'cannot read a number'."""
    inv = MFAM.inventory_family(law_rfa)
    parsed = MFAM.parse_family_edit("set PanelName DP-9", inv)
    assert parsed["ops"][0]["carrier"] == "m_str" and parsed["ops"][0]["value"] == "DP-9"
    # an integer param still refuses non-numeric text, honestly
    with pytest.raises(MFAM.FamilyEditError, match="cannot read a number"):
        MFAM.parse_family_edit("set NumberOfCircuits lots", inv)

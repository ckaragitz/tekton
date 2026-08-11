"""test_famgen_standards.py -- the CATEGORY -> STANDARD PARAMETERS table (#601).

Owner steer: "every family type has a set of parameters associated with them
... if i ask for a data device all parameters that are typically associated
within revit need to be in it, that goes for all of them."

Evidence tiers:

1. PROVENANCE.  Every measurable spec id the table uses is one the FORMAT
   itself declares -- it is in the ``m_formatOptionsMap`` of the units table
   (``src/rvt/famgen/assets/family_units.json``) that every family document we
   author ships.  A spec id nobody can source is a failure here, not a comment.
   Group ids come from Autodesk's published ``autodesk.parameter.group:*``
   enum, the same constants ``genesis.residue_b`` uses.
2. COVERAGE.  Every category ``skeleton._resolve_category`` accepts resolves to
   a table, and the categories the product actually claims are covered; an
   unknown category says so plainly instead of silently emitting a bare family.
3. AUTHORING.  Applying the table to a family document authors one
   ``ParamElemFamily`` per standard parameter with the right spec/group, at its
   storage class's BLANK unless the caller supplied a value, never redefining a
   parameter the constructor already authored, and never blocking delivery.
4. ON THE FILE.  A generated data-device family carries its standard parameters
   through the writer and reads back from the .rfa, family-mode VALID 0 errors.

Validator-green is necessary, NOT certification (hard rule 4): nothing here
says the enlarged parameter sets have been through desktop Revit.

Run: .venv/bin/python -m pytest tests/test_famgen_standards.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import needs_schema                              # noqa: E402
from rvt.famgen import standards as ST                         # noqa: E402
from rvt.famgen import skeleton as SK                          # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402


# ---------------------------------------------------------------------------
# 1. provenance -- the table cannot invent a spec id
# ---------------------------------------------------------------------------

def test_the_table_passes_its_own_provenance_gate():
    assert ST.check_specs() == []


def test_every_measurable_spec_id_is_one_the_format_declares_units_for():
    """The gate, spelled out independently of check_specs: the units table our
    own family documents ship enumerates the spec ids the format formats, and
    every measurable parameter in the table uses one of them."""
    declared = set(ST.units_spec_ids())
    assert len(declared) > 100                       # the real corpus, not a stub
    used = {p.spec for rows in ST.CATEGORY_STANDARDS.values() for p in rows if p.authored}
    measurable = used - set(ST.NON_MEASURABLE)
    assert measurable                                # the table does measure things
    assert {ST.SPECS[k] for k in measurable} <= declared
    # ... and the two non-measurable storage classes are NOT in it (a string /
    # an int has no unit), which is why they are exempt rather than forgotten
    assert not {ST.SPECS[k] for k in ST.NON_MEASURABLE} & declared


def test_group_ids_are_the_published_enum_form():
    for key, gid in ST.GROUPS.items():
        assert gid.startswith("autodesk.parameter.group:") and gid.endswith("-1.0.0"), key


def test_every_origin_is_one_of_the_three_and_builtins_are_never_authored():
    for key, rows in ST.CATEGORY_STANDARDS.items():
        for p in rows:
            assert p.origin in (ST.ORIGIN_BUILTIN, ST.ORIGIN_CONTRACT,
                                ST.ORIGIN_CONVENTION), (key, p.name)
            assert p.authored is (p.origin != ST.ORIGIN_BUILTIN)


def test_the_contract_origin_is_only_used_for_names_the_repo_really_carries():
    """origin='contract' claims the name comes from an in-repo tagging
    contract -- so every one of them must actually be in it."""
    contract_names = {n for n, _s, _g in F.PANEL_CONTRACT_PARAMS}
    used = {p.name for rows in ST.CATEGORY_STANDARDS.values() for p in rows
            if p.origin == ST.ORIGIN_CONTRACT}
    assert used <= contract_names, used - contract_names


# ---------------------------------------------------------------------------
# 2. coverage
# ---------------------------------------------------------------------------

#: every category name the writer accepts (the table must not disagree with it)
_WRITER_CATEGORIES = (
    "furniture", "generic_model", "generic", "lighting_fixture", "lighting_fixtures",
    "electrical_equipment", "panelboard", "transformer", "switchboard",
    "electrical_fixture", "electrical_fixtures", "mechanical_equipment",
    "plumbing_fixture", "plumbing_fixtures", "specialty_equipment", "casework",
    "pipe_accessory", "pipe_accessories", "duct_accessory", "duct_accessories",
    "cable_tray", "cable_trays", "conduit", "conduits", "cable_tray_fitting",
    "conduit_fitting", "lighting_device", "lighting_devices", "fire_alarm_device",
    "fire_alarm_devices", "data_device", "data_devices", "communication_device",
    "security_device", "nurse_call_device", "telephone_device",
    "structural_framing", "structural_column", "door", "doors", "window", "windows",
)


@pytest.mark.parametrize("cat", _WRITER_CATEGORIES)
def test_every_category_the_writer_accepts_has_a_standard_set(cat):
    SK._resolve_category(cat)                        # the writer knows it...
    d = ST.describe(cat)                             # ... and so does the table
    assert d["covered"], d
    assert d["authored"] or d["builtin"]


def test_an_unknown_category_says_so_plainly_instead_of_pretending():
    d = ST.describe("submarine_docking_collar")
    assert d["covered"] is False
    assert d["authored"] == [] and ST.NO_TABLE_NOTE in d["note"]


def test_aliases_and_ost_ids_resolve_to_the_same_table():
    assert ST.canonical_category("data_devices") == "data_device"
    assert ST.canonical_category("Data Devices") == "data_device"
    assert ST.canonical_category(-2008083) == "data_device"
    assert ST.canonical_category(SK.OST_LIGHTING_FIXTURES) == "lighting_fixture"
    # a PRODUCT set wins over the category it lives in ...
    assert ST.canonical_category("panelboard") == "panelboard"
    assert ST.canonical_category("transformer") == "transformer"
    # ... and a bare OST id, which cannot tell the products apart, gets the
    # category's own common set
    assert ST.canonical_category(SK.OST_ELECTRICAL_EQUIPMENT) == "electrical_equipment"


def test_the_panel_only_parameters_are_not_on_every_electrical_equipment():
    """The bug this table shape exists to prevent: a transformer carrying
    PanelName / BusRating / NumberOfCircuits because it shares a category."""
    panel = {p.name for p in ST.standard_params("panelboard")}
    xfmr = {p.name for p in ST.standard_params("transformer")}
    common = {p.name for p in ST.standard_params("electrical_equipment")}
    assert {"PanelName", "BusRating", "NumberOfCircuits", "NeutralRating"} <= panel
    assert not {"PanelName", "BusRating", "NumberOfCircuits"} & xfmr
    assert not {"PanelName", "BusRating", "NumberOfCircuits"} & common
    assert common <= panel and common <= xfmr        # both extend the category set
    assert {"kVA Rating", "Primary Voltage", "Secondary Voltage", "Impedance"} <= xfmr


def test_the_data_device_set_is_what_an_engineer_would_schedule_it_by():
    """The owner's worked example (#601)."""
    names = {p.name for p in ST.authored_params("data_devices")}
    assert {"Device Type", "Mounting", "Mounting Height", "Number of Ports",
            "Cable Category", "Backbox Size", "Voltage", "Apparent Load",
            "Load Classification"} <= names
    by_name = {p.name: p for p in ST.standard_params("data_devices")}
    assert by_name["Mounting Height"].spec == "length" and by_name["Mounting Height"].instance
    assert by_name["Number of Ports"].spec == "integer"
    assert by_name["Apparent Load"].spec == "apparent_power"
    # Panel / Circuit Number are Revit's own once the device is circuited
    assert by_name["Panel"].origin == ST.ORIGIN_BUILTIN and not by_name["Panel"].authored


# ---------------------------------------------------------------------------
# 3. authoring
# ---------------------------------------------------------------------------

@needs_schema
def test_apply_authors_one_family_parameter_per_standard_at_the_right_spec():
    doc = SK.new_family_document("data_devices", "Probe")
    rep = ST.apply(doc, "data_devices")
    assert rep["covered"] and rep["skipped"] == []
    expect = {p.name for p in ST.authored_params("data_devices")}
    assert set(doc.params) == expect
    for p in ST.authored_params("data_devices"):
        pe = doc.params[p.name]
        assert pe.class_name == "ParamElemFamily"
        pd = pe.obj["m_pParamDef"]["value"]
        assert pd["m_caption"] == p.name
        assert pd["m_groupTypeId"]["m_typeId"] == p.group_id


@needs_schema
def test_values_are_filled_only_when_given_and_blanks_keep_their_storage_class():
    doc = SK.new_family_document("data_devices", "Probe")
    doc.add_type("Probe", {})
    rep = ST.apply(doc, "data_devices",
                   values={"Number of Ports": 2, "Cable Category": "Cat6A",
                           "Mounting Height": 1.5, "Chassis Colour": "beige"})
    assert rep["filled"] == ["Cable Category", "Mounting Height", "Number of Ports"]
    assert rep["values_not_placed"] == ["Chassis Colour"]     # named nothing; said so
    (_name, vals), = doc.types
    assert vals[doc.params["Number of Ports"].elem_id] == 2
    assert vals[doc.params["Cable Category"].elem_id] == "Cat6A"
    assert vals[doc.params["Mounting Height"].elem_id] == pytest.approx(1.5)
    # every parameter nobody supplied is BLANK at its own storage class -- an
    # honest empty slot, never a guessed value
    assert vals[doc.params["Jack Color"].elem_id] == ""
    assert vals[doc.params["Termination Type"].elem_id] == ""
    assert vals[doc.params["Voltage"].elem_id] == 0.0


@needs_schema
def test_a_parameter_the_constructor_already_authored_is_never_redefined():
    doc = SK.new_family_document("data_devices", "Probe")
    mine = doc.add_family_parameter("Mounting Height", SK.SPEC_LENGTH,
                                    SK.PGROUP_DIMENSIONS)
    rep = ST.apply(doc, "data_devices")
    assert doc.params["Mounting Height"] is mine
    assert [s["name"] for s in rep["skipped"]] == ["Mounting Height"]
    assert "already authored" in rep["skipped"][0]["why"]


@needs_schema
def test_skip_and_instance_switches_are_reported_not_silent():
    doc = SK.new_family_document("data_devices", "Probe")
    rep = ST.apply(doc, "data_devices", skip=("Jack Color",), instance_params=False)
    why = {s["name"]: s["why"] for s in rep["skipped"]}
    assert "Jack Color" in why and "skip" in why["Jack Color"]
    assert "Mounting Height" in why and "instance" in why["Mounting Height"]
    assert "Mounting Height" not in doc.params


@needs_schema
def test_an_unknown_category_still_builds_the_family_and_records_the_gap():
    """Hard rule 1: a gap is a label, never refusal logic."""
    doc = SK.new_family_document("generic_model", "Probe")
    rep = ST.apply(doc, "submarine_docking_collar")
    assert rep["covered"] is False and rep["applied"] == []
    assert any(ST.NO_TABLE_NOTE in n for n in doc.notes)


@needs_schema
def test_applying_after_finalize_is_refused_rather_than_silently_lost():
    doc = SK.new_family_document("data_devices", "Probe")
    doc.add_type("Probe", {})
    doc.finalize()
    with pytest.raises(ValueError, match="finalized"):
        ST.apply(doc, "data_devices")


# ---------------------------------------------------------------------------
# 4. through the constructors, and on the file
# ---------------------------------------------------------------------------

@needs_schema
def test_a_generated_data_device_carries_its_category_standards():
    prod = F.make_generic_model(
        parts=[{"shape": "box", "width_ft": 0.375, "depth_ft": 0.05, "height_ft": 0.458}],
        name="Data Outlet 2-Port", category="data_devices",
        standard_values={"Number of Ports": 2, "Cable Category": "Cat6A"})
    assert prod.standards["category"] == "data_device"
    assert set(prod.standards["filled"]) == {"Number of Ports", "Cable Category"}
    names = set(prod.doc.params)
    assert {"Width", "Depth", "Height"} <= names          # the geometry report
    assert {p.name for p in ST.authored_params("data_devices")} <= names
    assert any("category standards" in n for n in prod.notes)


@needs_schema
def test_standards_false_is_the_regression_control():
    prod = F.make_generic_model(
        parts=[{"shape": "box", "width_ft": 1.0, "depth_ft": 1.0, "height_ft": 1.0}],
        name="Bare", category="data_devices", standards=False)
    assert prod.standards is None
    assert sorted(prod.doc.params) == ["Depth", "Height", "Width"]


@needs_schema
@pytest.mark.parametrize("maker,expect", [
    ("make_panelboard", {"PanelName", "BusRating", "Enclosure Rating", "Service Clearance"}),
    ("make_transformer", {"kVA Rating", "Impedance", "Enclosure Rating"}),
    ("make_luminaire", {"Luminous Flux", "Color Rendering Index", "Driver Type"}),
    ("make_device", {"Device Type", "NEMA Configuration", "Number of Gangs"}),
])
def test_every_catalog_constructor_applies_its_product_standards(maker, expect):
    prod = getattr(F, maker)()
    assert prod.standards is not None and prod.standards["covered"]
    assert expect <= set(prod.doc.params), expect - set(prod.doc.params)
    # the constructor's own parameters are left exactly as it made them
    for s in prod.standards["skipped"]:
        assert "already authored" in s["why"]


@needs_schema
def test_the_standard_parameters_survive_the_writer_and_the_validator(tmp_path):
    """ON THE FILE: the .rfa reads back with every standard parameter as a
    ParamElemFamily at its caption, family-mode VALID with 0 errors."""
    from rvt.families import FamilyIndex
    prod = F.make_generic_model(
        parts=[{"shape": "box", "width_ft": 0.375, "depth_ft": 0.05, "height_ft": 0.458},
               {"shape": "box", "width_ft": 0.333, "depth_ft": 0.187, "height_ft": 0.333,
                "base_z_ft": -0.187}],
        name="Data Outlet 2-Port", category="data_devices",
        standard_values={"Number of Ports": 2, "Cable Category": "Cat6A"})
    out = str(tmp_path / "data_outlet.rfa")
    rep = prod.write(out, validate=True)
    assert rep["ok"], rep.get("caveats")
    fam = rep["validate"]["family_mode"]
    assert fam["verdict"] == "VALID" and fam["n_errors"] == 0, fam.get("errors")
    idx = FamilyIndex(out)
    captions = {idx.value(0, eid)["m_pParamDef"]["value"]["m_caption"]
                for eid in idx.ids_of_class(0, "ParamElemFamily")}
    assert {p.name for p in ST.authored_params("data_devices")} <= captions

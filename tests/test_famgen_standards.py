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
    contract -- so every one of them must actually be in it: the factory's
    panelboard set, or the pset keys the IFC intent joins on (#642: the
    switchboard's ``Sections`` is ``SwitchboardSchedule.Sections``)."""
    from rvt.ifc.intent import CONTRACT_KEYS
    contract_names = {n for n, _s, _g in F.PANEL_CONTRACT_PARAMS} | set(CONTRACT_KEYS)
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
    # both extend the category set, QUANTITY for quantity (#622: the
    # transformer carries the common Operating Weight as its legacy 'Weight',
    # one entry per meaning -- so the law is stated over meaning keys)
    mk = ST.meaning_key
    assert common <= panel
    assert {mk(n) for n in common} <= {mk(n) for n in xfmr}
    assert common - xfmr == {"Operating Weight"} and "Weight" in xfmr
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
# 2b. one entry per meaning (#622) -- no two standard parameters of one
#     category are two spellings of the same quantity
# ---------------------------------------------------------------------------

def test_meaning_key_folds_spelling_and_the_trade_synonyms_but_keeps_distinct_quantities_apart():
    mk = ST.meaning_key
    # the three pairs the review of #601 found, plus the folding itself
    assert mk("Lumens") == mk("Luminous Flux") == mk("luminous_flux")
    assert mk("MountingHeight") == mk("Mounting Height") == mk("mounting height")
    assert mk("Weight") == mk("Operating Weight")
    assert mk("Color Temperature") == mk("Initial Color Temperature") == mk("CCT")
    assert mk("Load") == mk("Apparent Load") and mk("Enclosure") == mk("Enclosure Rating")
    # ... and what is NOT the same quantity stays apart (a synonym list that
    # swallowed these would delete real parameters)
    assert mk("Wattage") != mk("Apparent Load")               # W is not VA
    assert mk("Load Classification") != mk("Apparent Load")
    assert mk("Voltage") != mk("Primary Voltage") != mk("Secondary Voltage")
    assert mk("Full Load Amps") != mk("Apparent Load")
    assert mk("Lamp") != mk("Number of Lamps") != mk("Luminous Flux")
    assert mk("K-Factor") == "kfactor"                          # punctuation folds, nothing else


def test_the_synonym_vocabulary_is_itself_consistent():
    assert ST._SYNONYM_CLASHES == []                 # no spelling claimed by two groups
    canon = [ST.meaning_key(g[0]) for g in ST.SYNONYM_GROUPS]
    assert len(canon) == len(set(canon))             # one group per quantity
    for g in ST.SYNONYM_GROUPS:
        assert len(g) >= 2 and len({ST.meaning_key(s) for s in g}) == 1, g


def test_no_category_lists_two_spellings_of_one_quantity():
    """The self-check, restated independently of check_specs: within every
    category (built-ins included -- a user sees those side by side with ours
    too) no two names share a meaning key."""
    for key, rows in ST.CATEGORY_STANDARDS.items():
        seen = {}
        for p in rows:
            m = ST.meaning_key(p.name)
            assert m not in seen or seen[m] == p.name, (key, seen.get(m), p.name)
            seen[m] = p.name


@pytest.mark.parametrize("a,b", [
    (ST._P("Lumens", "luminous_flux", "photometrics"),
     ST._P("Luminous Flux", "luminous_flux", "photometrics")),
    (ST._P("MountingHeight", "length", "constraints", instance=True),
     ST._P("Mounting Height", "length", "constraints", instance=True)),
    (ST._P("Weight", "mass", "identity"), ST._P("Operating Weight", "mass", "identity")),
])
def test_a_planted_duplicate_meaning_fails_the_table_check(monkeypatch, a, b):
    """The shipped table passes (section 1); a planted pair does not."""
    monkeypatch.setitem(ST.CATEGORY_STANDARDS, "zz_planted_probe",
                        (ST._P("Device Type"), a, b))
    probs = ST.check_specs()
    assert len(probs) == 1, probs
    assert probs[0].startswith(f"zz_planted_probe/{a.name} + {b.name}: 2 spellings of one quantity")


def test_the_transformer_keeps_weight_as_its_single_weight_entry_with_a_stated_reason():
    """Per-pair decision (#622): the transformer's catalog weight is a plain
    number in lb that make_transformer fills; converting it to the category's
    Operating Weight (mass) is a unit change, so the legacy name is KEPT as
    the one entry and its row says why.  Every other electrical equipment set
    keeps Operating Weight (mass)."""
    xf = {p.name: p for p in ST.standard_params("transformer")}
    assert "Weight" in xf and "Operating Weight" not in xf
    assert xf["Weight"].spec == "number" and "Operating Weight" in xf["Weight"].note
    for other in ("electrical_equipment", "panelboard", "switchboard",
                  "mechanical_equipment", "lighting_fixture"):
        by = {p.name: p for p in ST.standard_params(other)}
        assert by["Operating Weight"].spec == "mass" and "Weight" not in by, other


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
def test_apply_never_authors_a_blank_twin_of_a_quantity_already_on_the_document():
    """#622 through apply(): a constructor's (or a caller's) 'Lumens' /
    'MountingHeight' means the table's 'Luminous Flux' / 'Mounting Height' is
    NOT added blank next to it; the skip names the spelling carrying the
    quantity, and a value offered for the skipped spelling is reported as not
    placed rather than silently dropped."""
    doc = SK.new_family_document("lighting_fixtures", "Probe")
    doc.add_type("Probe", {})
    mine = doc.add_family_parameter("Lumens", SK.SPEC_LUMINOUS_FLUX, SK.PGROUP_ELECTRICAL)
    rep = ST.apply(doc, "lighting_fixtures", values={"Luminous Flux": 3200.0})
    assert "Luminous Flux" not in doc.params and doc.params["Lumens"] is mine
    why = {s["name"]: s["why"] for s in rep["skipped"]}
    assert list(why) == ["Luminous Flux"]
    # by MEANING the carrier may be a constructor's or a caller's parameter, so
    # the skip says what is on the document rather than who put it there
    assert why["Luminous Flux"] == "already on the document as 'Lumens' (the same quantity)"
    assert rep["values_not_placed"] == ["Luminous Flux"]     # its slot is the constructor's
    keys = [ST.meaning_key(n) for n in doc.params]
    assert len(keys) == len(set(keys))
    # the folded-spelling case needs no synonym row at all
    dev = SK.new_family_document("electrical_fixtures", "Probe")
    dev.add_family_parameter("MountingHeight", SK.SPEC_LENGTH, SK.PGROUP_CONSTRAINTS)
    rep = ST.apply(dev, "electrical_fixtures")
    assert "Mounting Height" not in dev.params
    assert [s["name"] for s in rep["skipped"]] == ["Mounting Height"]


@needs_schema
def test_a_value_offered_under_any_spelling_of_the_quantity_fills_the_tables_spelling():
    """The same key on the way IN: standard_values={'Lumens': ...} (a famspec
    written before the rename, an IFC pset's 'CCT') fills 'Luminous Flux' /
    'Initial Color Temperature' rather than being reported as not placed."""
    doc = SK.new_family_document("lighting_fixtures", "Probe")
    doc.add_type("Probe", {})
    rep = ST.apply(doc, "lighting_fixtures", values={"Lumens": 3200.0, "CCT": 3500.0,
                                                     "Beam Angle": 40})
    assert rep["filled"] == ["Initial Color Temperature", "Luminous Flux"]
    assert rep["values_not_placed"] == ["Beam Angle"]
    (_n, vals), = doc.types
    assert vals[doc.params["Luminous Flux"].elem_id] == pytest.approx(3200.0)
    assert vals[doc.params["Initial Color Temperature"].elem_id] == pytest.approx(3500.0)


@needs_schema
def test_two_spellings_of_one_quantity_in_values_fill_it_once_and_report_the_loser():
    """{'Lumens': .., 'Luminous Flux': ..} cannot both land on one parameter:
    the table's own spelling wins whatever the order, else the first given;
    the other is named in values_not_placed instead of vanishing last-wins."""
    for given in ({"Lumens": 3200.0, "Luminous Flux": 4600.0},
                  {"Luminous Flux": 4600.0, "Lumens": 3200.0}):
        doc = SK.new_family_document("lighting_fixtures", "Probe")
        doc.add_type("Probe", {})
        rep = ST.apply(doc, "lighting_fixtures", values=given)
        (_n, vals), = doc.types
        assert vals[doc.params["Luminous Flux"].elem_id] == pytest.approx(4600.0)
        assert "Luminous Flux" in rep["filled"] and rep["values_not_placed"] == ["Lumens"]
    # neither spelling is the table's: the first given wins, the second is reported
    doc = SK.new_family_document("lighting_fixtures", "Probe")
    doc.add_type("Probe", {})
    rep = ST.apply(doc, "lighting_fixtures", values={"CCT": 3500.0, "Colour Temperature": 3000.0})
    (_n, vals), = doc.types
    assert vals[doc.params["Initial Color Temperature"].elem_id] == pytest.approx(3500.0)
    assert rep["values_not_placed"] == ["Colour Temperature"]
    assert "Lumens" not in doc.params and "CCT" not in doc.params


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
@pytest.mark.parametrize("maker,kwargs,filled,gone", [
    # lighting fixture: the photometric facts land under the table's spelling
    ("make_luminaire", {}, {"Luminous Flux", "Initial Color Temperature", "Wattage"},
     {"Lumens", "Color Temperature"}),
    # electrical fixture: the connector-bound load and the placement height
    ("make_device", {}, {"Apparent Load", "Mounting Height", "Voltage"},
     {"Load", "MountingHeight"}),
    # electrical equipment: the NEMA class renamed, the weight KEPT as 'Weight'
    ("make_transformer", {}, {"Weight", "Enclosure Rating", "kVA Rating"},
     {"Enclosure", "Operating Weight"}),
    ("make_panelboard", {}, {"PanelName", "BusRating"}, set()),
    # mechanical equipment goes down the anything route
    ("make_generic_model", {"parts": [{"shape": "box", "width_ft": 3.0, "depth_ft": 2.5,
                                        "height_ft": 4.0}],
                            "name": "RTU-1", "category": "mechanical_equipment"},
     {"Width", "Depth", "Height"}, set()),
])
def test_every_generated_family_lists_each_quantity_once_and_the_values_still_land(
        maker, kwargs, filled, gone):
    """#622 DONE 3: one entry per meaning on the generated family, and the
    value the constructor used to put under the legacy name is under the
    surviving one (blank standard parameters stay blank -- never invented)."""
    prod = getattr(F, maker)(**kwargs)
    doc = prod.doc
    names = list(doc.params)
    by_key = {}
    for n in names:
        by_key.setdefault(ST.meaning_key(n), []).append(n)
    twins = {k: v for k, v in by_key.items() if len(v) > 1}
    assert twins == {}, twins
    assert not gone & set(names), gone & set(names)
    _tname, vals = doc.types[0]
    for n in filled:
        assert n in doc.params, n
        assert vals[doc.params[n].elem_id] not in (None, "", 0, 0.0), n
    # nothing the standards layer skipped was skipped for any reason but
    # "the document already carries it" (by name or by meaning)
    for s in (prod.standards or {}).get("skipped", []):
        assert s["why"].startswith(("already authored", "already on the document")), s


@needs_schema
def test_the_transformer_connector_and_catalog_follow_the_renamed_enclosure_but_keep_weight():
    xf = F.make_transformer(kva=75)
    _t, vals = xf.doc.types[0]
    assert vals[xf.doc.params["Enclosure Rating"].elem_id] == "NEMA 2 (indoor)"
    assert vals[xf.doc.params["Weight"].elem_id] == pytest.approx(570.0)
    header = F.type_catalog_text(xf).splitlines()[0]
    assert "Enclosure Rating##OTHER##" in header and "Weight##OTHER##" in header
    # a vendor with no catalog weight still gets ONE weight entry, blank
    hps = F.make_transformer(kva=75, vendor="hps")
    assert "Weight" in hps.doc.params and "Operating Weight" not in hps.doc.params
    _t, hv = hps.doc.types[0]
    assert hv[hps.doc.params["Weight"].elem_id] == 0.0
    # the device's connector is bound to the renamed load parameter
    dev = F.make_device("duplex-receptacle")
    dom = dev.doc.connectors[0].obj["m_pDomain"]["value"]
    assert dom["m_dApparentLoadPhase1"] == pytest.approx(SK.voltamps(180.0))
    _t, dv = dev.doc.types[0]
    assert dv[dev.doc.params["Apparent Load"].elem_id] == pytest.approx(SK.voltamps(180.0))
    assert dv[dev.doc.params["Mounting Height"].elem_id] == pytest.approx(1.5)


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

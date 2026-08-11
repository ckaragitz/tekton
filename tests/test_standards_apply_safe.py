"""test_standards_apply_safe.py -- ONE standards step for every model-family
constructor, and given values land in their parameter's storage class (#642).

Issue #642 (Refs #631 #622 #601, steer S-2026-08-11-a): the guarded standards
step used to be a factory-private helper (``factory._std``) that constructors
outside ``factory.py`` reached into or skipped; ``make_generic_model`` called
the table unguarded and ``rvt.ifc.intent.make_house_switchboard`` (Electrical
Equipment) applied no table at all.  Now ``rvt.famgen.standards.apply_safe``
is the one call all of them make.  Two defects ride along:

* an ``int`` offered for a DOUBLE-spec standard parameter
  (``{"Color Rendering Index": 90}``, JSON ``{"CCT": 3000}``) was filed by
  ``skeleton.family_param_value`` in ``m_int`` beside an ``m_value`` of 0.0 --
  Revit reads the 0.0.  ``standards.coerce_value`` writes every given value in
  its entry's storage class; the read-back below pins it ON THE FILE.
* ``standards=False`` dropped a caller's ``standard_values`` silently; the
  document now names them, exactly as the IFC route already did for its job
  values.

Evidence tiers: (1) the step -- every constructor the router reaches returns a
report for ITS category, off = None + a note naming what was offered, a fault =
a note, never a failed build; (2) coercion -- by spec, in the document and on
the written ``.rfa`` (family-mode VALID 0 errors, provenance clean); (3) the
switchboard carries the Electrical Equipment ``switchboard`` set with each
quantity once and its own pset ratings left as made.

Validator-green is necessary, NOT certification (hard rule 4): nothing here
says the switchboard's enlarged parameter set has been through desktop Revit.

Run: .venv/bin/python -m pytest tests/test_standards_apply_safe.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import HAVE_SCHEMA, needs_schema                 # noqa: E402
from rvt.famgen import standards as ST                         # noqa: E402
from rvt.famgen import skeleton as SK                          # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402
from rvt.ifc import famfrom_ifc as FI                          # noqa: E402
from rvt.ifc import intent as I                                # noqa: E402
from rvt.ifc import product_facts as PF                        # noqa: E402

needs_ifc = pytest.mark.skipif(not (HAVE_SCHEMA and os.path.exists(PF.DEFAULT_IFC)),
                               reason="class schema / tracked IFC input absent")

SWBD = dict(tag="MSB", name="Switchboard MSB", mains_a=2500, voltage="480Y/277",
            sections=4, width_m=3.6, depth_m=0.9, height_m=2.3)


def _switchboard(**kw):
    return I.make_house_switchboard(**{**SWBD, **kw})


def _type_values(doc):
    """{caption: value} of the first type row."""
    _tname, vals = doc.types[0]
    return {n: vals[pe.elem_id] for n, pe in doc.params.items()}


def _write_valid(prod, path):
    """Write ``prod`` on the bundled base; family-mode VALID 0 errors and
    provenance clean, or the test fails here.  Returns the write report."""
    from rvt.frontdoor.standalone import standalone_family_write
    rep = standalone_family_write(prod, path)
    fam = (rep.get("validate") or {}).get("family_mode") or {}
    assert fam.get("verdict") == "VALID" and fam.get("n_errors") == 0, fam.get("errors")
    assert (rep.get("provenance") or {}).get("ok") is True, rep["provenance"].get("suspects")
    return rep


#: every MODEL-family constructor the router can reach -> the table it names.
#: (annotation heads in famgen.heads are exempt by design: no table applies.)
CONSTRUCTORS = [
    ("factory.make_panelboard", F.make_panelboard, "panelboard"),
    ("factory.make_transformer", F.make_transformer, "transformer"),
    ("factory.make_luminaire", F.make_luminaire, "lighting_fixture"),
    ("factory.make_device", F.make_device, "electrical_fixture"),
    ("factory.make_generic_model",
     lambda **kw: F.make_generic_model(width_ft=2.0, depth_ft=1.0, height_ft=3.0, **kw),
     "generic_model"),
    ("factory.make_generic_model(parts)",
     lambda **kw: F.make_generic_model(
         parts=[{"shape": "box", "width_ft": 1.0, "depth_ft": 1.0, "height_ft": 1.0}],
         category="mechanical_equipment", name="RTU-1", **kw),
     "mechanical_equipment"),
    ("intent.make_house_switchboard", _switchboard, "switchboard"),
]


# ---------------------------------------------------------------------------
# 1. one step, everywhere
# ---------------------------------------------------------------------------

def test_the_factory_private_helper_is_gone():
    """One code path: nothing to reach into or re-implement beside apply_safe."""
    assert not hasattr(F, "_std")


@needs_schema
@pytest.mark.parametrize("label,make,category", CONSTRUCTORS,
                         ids=[c[0] for c in CONSTRUCTORS])
def test_every_model_family_constructor_returns_a_report_for_its_category(label, make, category):
    prod = make()
    rep = prod.standards
    assert rep is not None and rep["covered"], label
    assert rep["category"] == category
    assert prod.summary()["standards"]["category"] == category
    # what the step skipped, it skipped only because the document already had it
    for s in rep["skipped"]:
        assert s["why"].startswith(("already authored", "already on the document")), (label, s)


@needs_ifc
def test_the_ifc_born_downlight_goes_through_the_same_step():
    prod = FI.make_downlight(start_id=1000)
    assert prod.standards is not None and prod.standards["category"] == FI.STD_CATEGORY


@needs_schema
@pytest.mark.parametrize("label,make,category", CONSTRUCTORS,
                         ids=[c[0] for c in CONSTRUCTORS])
def test_standards_off_names_the_values_it_drops(label, make, category):
    """#642 (b): ``standards=False`` + ``standard_values`` -> no report, and the
    document SAYS which offered values are now not authored -- never silent."""
    prod = make(standards=False, standard_values={"Warranty Duration": "5 yr",
                                                  "Not A Standard Thing": 1})
    assert prod.standards is None and "standards" not in prod.summary()
    notes = [n for n in prod.doc.notes if n.startswith("standards off")]
    assert len(notes) == 1, prod.doc.notes
    assert f"({category})" in notes[0]
    assert "'Not A Standard Thing'" in notes[0] and "'Warranty Duration'" in notes[0]
    # names them; does not claim an arbitrary key is a standard parameter
    assert "NOT authored" in notes[0] and "standard parameters of the category" not in notes[0]


@needs_ifc
def test_the_downlight_names_job_values_and_caller_values_in_one_note():
    prod = FI.make_downlight(standards=False, lumens=900, standard_values={"CRI": 80},
                             start_id=1000)
    notes = [n for n in prod.doc.notes if n.startswith("standards off")]
    assert len(notes) == 1, prod.doc.notes
    assert "'CRI'" in notes[0] and "'Luminous Flux'" in notes[0]


@needs_schema
def test_off_with_nothing_offered_says_nothing():
    doc = SK.new_family_document("data_devices", "Probe")
    assert ST.apply_safe(doc, "data_devices", False) is None
    assert ST.apply_safe(doc, "data_devices", False, {"Jack Color": None}) is None
    assert not any("standards off" in n for n in doc.notes)
    assert doc.params == {}


@needs_schema
def test_a_fault_in_the_step_is_a_note_never_a_failed_build():
    """Hard rule 1: apply() refuses a finalized document (a programming error);
    through apply_safe that becomes a note and the constructor carries on."""
    doc = SK.new_family_document("data_devices", "Probe")
    doc.add_type("Probe", {})
    doc.finalize()
    with pytest.raises(ValueError):
        ST.apply(doc, "data_devices")
    assert ST.apply_safe(doc, "data_devices") is None
    assert any(n.startswith("category standards NOT applied (ValueError") for n in doc.notes)


@needs_schema
def test_apply_safe_on_is_apply():
    a = SK.new_family_document("lighting_fixtures", "Probe"); a.add_type("Probe", {})
    b = SK.new_family_document("lighting_fixtures", "Probe"); b.add_type("Probe", {})
    ra = ST.apply(a, "lighting_fixtures", values={"CCT": 3000}, skip=("Lamp",))
    rb = ST.apply_safe(b, "lighting_fixtures", True, {"CCT": 3000}, skip=("Lamp",))
    assert ra == rb
    assert list(a.params) == list(b.params) and a.types == b.types


# ---------------------------------------------------------------------------
# 2. a given value lands in its parameter's storage class
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec,given,expect", [
    ("number", 90, 90.0), ("number", 90.5, 90.5), ("number", "0.85", 0.85),
    ("cct", 3000, 3000.0), ("length", 2, 2.0),
    ("integer", 2, 2), ("integer", 2.0, 2), ("integer", " 4 ", 4),
    ("integer", False, 0), ("integer", True, 1),          # a 0/1 flag (Emergency, GFCI ...)
    ("text", 7, "7"), ("text", "Cat6A", "Cat6A"), ("text", 2.5, "2.5"),
])
def test_coerce_value_by_spec(spec, given, expect):
    got = ST.coerce_value(spec, given)
    assert got == expect and type(got) is type(expect)


INF, NAN = float("inf"), float("nan")


@pytest.mark.parametrize("spec,given", [
    ("integer", 2.5), ("integer", "2.5"), ("number", "warm"), ("cct", "3000K"),
    ("number", [90]), ("length", None),
    # a bool is a flag, never a quantity: {"Wattage": True} is not 1 W (S-2026-08-11-a)
    ("wattage", True), ("number", False), ("length", True),
    # non-finite is never a value, on either storage class
    ("integer", INF), ("integer", -INF), ("integer", NAN), ("integer", "inf"),
    ("number", INF), ("number", -INF), ("number", NAN), ("cct", "nan"), ("length", "-inf"),
])
def test_coerce_value_refuses_what_it_cannot_write_rather_than_guessing(spec, given):
    with pytest.raises((TypeError, ValueError)):
        ST.coerce_value(spec, given)


@needs_schema
def test_flags_and_non_finite_numbers_leave_blanks_and_the_full_set_is_still_authored():
    """A bool for a measurable, and inf / nan anywhere, are unusable: the slot
    stays blank, the value is named, and apply() finishes the WHOLE set (an
    ``int(inf)`` OverflowError used to escape mid-loop and leave a partial
    family behind an 'NOT applied' note)."""
    doc = SK.new_family_document("lighting_fixtures", "Probe")
    doc.add_type("Probe", {})
    rep = ST.apply(doc, "lighting_fixtures",
                   values={"Wattage": True, "Luminous Flux": INF, "Number of Lamps": NAN,
                           "Light Loss Factor": -INF, "Emergency": True})
    assert {p.name for p in ST.authored_params("lighting_fixtures")} <= set(doc.params)
    v = _type_values(doc)
    assert v["Wattage"] == 0.0 and v["Luminous Flux"] == 0.0 and v["Light Loss Factor"] == 0.0
    assert v["Number of Lamps"] == 0 and v["Emergency"] == 1
    assert rep["filled"] == ["Emergency"]
    assert sorted(u["name"] for u in rep["values_unusable"]) == [
        "Light Loss Factor", "Luminous Flux", "Number of Lamps", "Wattage"]
    assert not any("NOT applied" in n for n in doc.notes)


@needs_schema
def test_an_int_for_a_double_spec_lands_as_the_value_not_beside_a_zero():
    """#642 (a), in the document: 90 -> 90.0 (float) on the type row, so
    ``skeleton.family_param_value`` files it in ``m_value``."""
    doc = SK.new_family_document("lighting_fixtures", "Probe")
    doc.add_type("Probe", {})
    rep = ST.apply(doc, "lighting_fixtures",
                   values={"Color Rendering Index": 90, "CCT": 3000, "Lumens": "3200",
                           "Number of Lamps": 2.0, "Driver Type": 10, "Efficacy": "high"})
    v = _type_values(doc)
    assert v["Color Rendering Index"] == 90.0 and type(v["Color Rendering Index"]) is float
    assert v["Initial Color Temperature"] == 3000.0 and type(v["Initial Color Temperature"]) is float
    assert v["Luminous Flux"] == 3200.0
    assert v["Number of Lamps"] == 2 and type(v["Number of Lamps"]) is int
    assert v["Driver Type"] == "10"
    # a value that cannot be written leaves the slot BLANK and is named
    assert v["Efficacy"] == 0.0
    assert [u["name"] for u in rep["values_unusable"]] == ["Efficacy"]
    assert "'high'" in rep["values_unusable"][0]["why"]
    assert "Efficacy" not in rep["filled"] and "values_not_placed" not in rep
    assert set(rep["filled"]) == {"Color Rendering Index", "Initial Color Temperature",
                                  "Luminous Flux", "Number of Lamps", "Driver Type"}
    entry = SK.family_param_value(doc.params["Color Rendering Index"].elem_id,
                                  v["Color Rendering Index"])
    assert entry["m_value"] == 90.0 and entry["m_int"] == 0


@needs_schema
def test_a_none_value_is_no_value():
    doc = SK.new_family_document("lighting_fixtures", "Probe")
    doc.add_type("Probe", {})
    rep = ST.apply(doc, "lighting_fixtures", values={"Color Rendering Index": None})
    assert _type_values(doc)["Color Rendering Index"] == 0.0
    assert rep["filled"] == [] and "values_not_placed" not in rep and "values_unusable" not in rep


def _readback(path, caption):
    """{type name: FamilyParamValue entry} of ``caption`` off the WRITTEN .rfa."""
    from rvt.families import FamilyIndex
    idx = FamilyIndex(path)
    pids = [eid for eid in idx.ids_of_class(0, "ParamElemFamily")
            if idx.value(0, eid)["m_pParamDef"]["value"]["m_caption"] == caption]
    assert len(pids) == 1, pids
    out = {}
    for fid in idx.ids_of_class(0, "Family"):
        v = idx.value(0, fid) or {}
        for pr in ((v.get("m_pFamilyTypes") or {}).get("value") or {}).get("m_pairs") or []:
            for p in (pr.get("params") or {}).get("m_params") or []:
                if p.get("m_paramId") == pids[0]:
                    out[pr.get("name")] = p
        for p in ((v.get("m_familyParams") or {}).get("value") or {}).get("m_params") or []:
            if p.get("m_paramId") == pids[0]:
                out["<current type>"] = p
    return out


@needs_schema
def test_the_written_luminaire_reads_back_cri_90_as_the_value(tmp_path):
    """#642 (a), ON THE FILE: before this change the same call read back
    ``m_value 0.0 / m_int 90`` on every row."""
    from rvt.convert.modify_family import inventory_family
    prod = F.make_luminaire(standard_values={"Color Rendering Index": 90})
    path = str(tmp_path / "troffer_cri90.rfa")
    _write_valid(prod, path)
    rows = _readback(path, "Color Rendering Index")
    assert set(rows) == {t.name for t in prod.types} | {"<current type>"}
    for name, entry in rows.items():
        assert entry["m_value"] == 90.0 and entry["m_int"] == 0, (name, entry)
    # the same fact in the edit lane's vocabulary: a number-spec parameter is
    # carried in m_value, and that is where the 90 now is
    cri = inventory_family(path).param_by_caption("Color Rendering Index")
    assert cri["carrier"] == "m_value" and cri["current"] == 90.0


# ---------------------------------------------------------------------------
# 3. the house switchboard carries the Electrical Equipment switchboard set
# ---------------------------------------------------------------------------

@needs_schema
def test_the_switchboard_carries_its_set_once_and_keeps_its_own_ratings():
    prod = _switchboard()
    doc, rep = prod.doc, prod.standards
    names = set(doc.params)
    assert {p.name for p in ST.authored_params("switchboard")} <= names
    keys = [ST.meaning_key(n) for n in doc.params]
    assert len(keys) == len(set(keys)), sorted(doc.params)
    # the pset ratings the constructor authors are left exactly as it made them
    own = {"BusRating", "MainsType", "MainsRating", "ShortCircuitRatingkA", "Sections",
           "Voltage", "Phases", "Wires", "Mounting"}
    assert {s["name"] for s in rep["skipped"]} == own
    assert all(s["why"] == "already authored by the constructor" for s in rep["skipped"])
    v = _type_values(doc)
    assert v["Sections"] == 4 and v["BusRating"] == 2500.0 and v["PanelName"] == "MSB"
    # the rest are honest blanks at their storage class -- nothing invented
    assert rep["filled"] == []
    assert v["Frequency"] == 0.0 and v["Bus Material"] == "" and v["Enclosure Rating"] == ""
    assert v["Operating Weight"] == 0.0 and v["Service Clearance"] == 0.0


@needs_schema
def test_the_switchboard_fills_a_standard_value_only_when_the_caller_holds_it():
    prod = _switchboard(standard_values={"Frequency": 60, "Enclosure Rating": "NEMA 1",
                                         "Number of Sections": 6})
    doc, rep = prod.doc, prod.standards
    v = _type_values(doc)
    assert v["Frequency"] == 60.0 and v["Enclosure Rating"] == "NEMA 1"
    # 'Number of Sections' IS the constructor's Sections (one quantity): the
    # constructor's value stands, the offered one is reported, no twin grows
    assert "Number of Sections" not in doc.params and v["Sections"] == 4
    assert rep["values_not_placed"] == ["Number of Sections"]
    assert set(rep["filled"]) == {"Frequency", "Enclosure Rating"}


def test_the_switchboard_row_is_the_contract_spelling():
    by = {p.name: p for p in ST.standard_params("switchboard")}
    assert "Sections" in by and "Number of Sections" not in by
    assert by["Sections"].origin == ST.ORIGIN_CONTRACT and by["Sections"].spec == "integer"
    assert "Sections" in I.CONTRACT_KEYS
    assert ST.meaning_key("Number of Sections") == ST.meaning_key("Sections")
    assert ST.check_specs() == []


@needs_schema
def test_the_written_switchboard_is_family_mode_valid_and_provenance_clean(tmp_path):
    from rvt.families import FamilyIndex
    prod = _switchboard()
    path = str(tmp_path / "switchboard.rfa")
    _write_valid(prod, path)
    idx = FamilyIndex(path)
    caps = {idx.value(0, eid)["m_pParamDef"]["value"]["m_caption"]
            for eid in idx.ids_of_class(0, "ParamElemFamily")}
    assert caps == set(prod.doc.params)
    assert {p.name for p in ST.authored_params("switchboard")} <= caps

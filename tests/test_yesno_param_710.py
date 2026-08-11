"""test_yesno_param_710.py -- SPEC_YESNO authors a Yes/No family parameter
(``ParamDefYesNo``), extending the #333 storage-class law to the boolean case.

Before: `add_family_parameter` covered text, integer and every measurable spec,
but not Yes/No -- the parameter Revit uses for every visibility toggle.  A
caller wanting a checkbox had to fake it with an integer.

The law this follows is already verified, not invented.  #333 round 24 (a
Revit-2026-born specimen, desktop-confirmed) established that a NON-MEASURABLE
parameter takes its own ``ParamDef`` class and writes no ``m_specTypeId`` /
``m_restriction`` / ``m_boundless``; only measurable double-valued specs use
``ParamDefValue``.  ``ParamDefYesNo`` is in the 2026 schema with NO own fields
-- the same shape as ``ParamDefString``, which this factory already authors --
so the boolean case falls straight out of it.  ``SPEC_YESNO`` is a SELECTOR
and never reaches the bytes, exactly like ``SPEC_TEXT`` / ``SPEC_INTEGER``.

Evidence tiers: (1) the schema shape this rests on; (2) the storage class
chosen; (3) no spec id is written (the #333 law's actual content); (4) the
sibling specs are unchanged; (5) the WRITTEN .rfa -- family-mode VALID 0
errors, provenance clean, the parameter present in the report.
"""
import pytest

from rvt import schema as S
from rvt.famgen import factory as F, skeleton as SK


def _doc(name="YesNo Probe"):
    return SK.new_family_document("generic_model", name,
                                  part_type=SK.PART_TYPE["normal"],
                                  work_plane_based=False, start_id=1000,
                                  plane_length_ft=6.0)


# ---------------------------------------------------------------------------
# (1) the schema shape the law is applied to
# ---------------------------------------------------------------------------

def test_paramdefyesno_has_the_same_shape_as_paramdefstring():
    sch = S.load_schema()
    yes = sch.by_name["ParamDefYesNo"]
    txt = sch.by_name["ParamDefString"]
    integer = sch.by_name["ParamDefInt"]
    assert [f.name for f in yes.fields] == [], "ParamDefYesNo carries no own fields"
    assert [f.name for f in txt.fields] == [], "…the same as ParamDefString"
    assert [f.name for f in integer.fields] == ["m_lowBound", "m_upBound"], \
        "ParamDefInt is the one that adds bounds — the contrast this rests on"


# ---------------------------------------------------------------------------
# (2)+(3) the storage class, and the law: no spec id is written
# ---------------------------------------------------------------------------

def test_yesno_selects_paramdefyesno_and_writes_no_spec_id():
    pe = _doc().add_family_parameter("Door Open", SK.SPEC_YESNO, SK.PGROUP_DIMENSIONS)
    pdef = pe.obj["m_pParamDef"]
    assert pdef["ptr_class"] == "ParamDefYesNo"
    body = pdef["value"]
    assert "m_specTypeId" not in body, "#333: a non-measurable param writes no spec"
    assert "m_restriction" not in body
    assert "m_boundless" not in body
    assert body["m_caption"] == "Door Open"


# ---------------------------------------------------------------------------
# (4) the sibling specs are untouched
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec,cls", [
    (SK.SPEC_TEXT, "ParamDefString"),
    (SK.SPEC_INTEGER, "ParamDefInt"),
    (SK.SPEC_LENGTH, "ParamDefValue"),
])
def test_other_specs_still_choose_their_own_storage_class(spec, cls):
    pe = _doc().add_family_parameter("P", spec, SK.PGROUP_DIMENSIONS)
    assert pe.obj["m_pParamDef"]["ptr_class"] == cls


def test_a_measurable_spec_still_writes_its_spec_id():
    pe = _doc().add_family_parameter("L", SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS)
    body = pe.obj["m_pParamDef"]["value"]
    assert body["m_specTypeId"]["m_typeId"] == SK.SPEC_LENGTH


# ---------------------------------------------------------------------------
# (5) the written family
# ---------------------------------------------------------------------------

def test_a_family_with_yesno_params_writes_and_validates(tmp_path):
    doc = _doc("YesNo Written")
    for cap in ("Door Open", "Door Closed", "Show Working Clearance"):
        doc.add_family_parameter(cap, SK.SPEC_YESNO, SK.PGROUP_DIMENSIONS)
    F.add_box_form(doc, 1.0, 1.0, 1.0)
    doc.add_type("Standard", {"Door Open": 1, "Door Closed": 0,
                              "Show Working Clearance": 1})
    doc.finalize()
    prod = F.FamilyProduct("generic_model", doc, F.FactSheet(subject="yesno probe"),
                           file_stem="yesno")
    rep = prod.write(str(tmp_path / "yesno.rfa"), validate=True)
    assert rep["validate"]["family_mode"]["n_errors"] == 0, \
        rep["validate"]["family_mode"]["errors"]
    assert rep["provenance"]["ok"], rep["provenance"]["suspects"]
    for cap in ("Door Open", "Door Closed", "Show Working Clearance"):
        assert cap in rep["family"]["parameters"]

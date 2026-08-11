"""test_transformer_mass_630.py -- the transformer's catalog weight is the
category's ``Operating Weight``: a MASS, lb -> internal kilograms, with a
``MASS##POUNDS_MASS`` type-catalog column (#630; Refs #622 #601,
steer S-2026-08-11-a: one parameter per meaning, values only when known).

Before: ``make_transformer`` authored a legacy ``Weight`` -- a plain
``number`` in lb -- and ``rvt.famgen.standards`` carved the category's
``Operating Weight`` out of the transformer set so the two spellings never met
on one family.  The transformer was the one piece of electrical equipment whose
weight was a unitless number under another name.  Now the factory has the mass
path (``SPEC["mass"]``, ``_TO_INTERNAL["mass"] = pounds``,
``TYPE_CATALOG_COLUMNS["mass"]``) and the exception is gone.

Evidence tiers: (1) the unit path itself -- the spec id is the one OUR units
table declares, the conversion is the pound's definition, the internal unit is
kilograms; (2) the document -- Eaton (catalog weight) and HPS (none) name the
quantity identically, one entry per meaning, value converted / blank; (3) the
type catalog header and its lb cells; (4) the WRITTEN ``.rfa`` -- family-mode
VALID 0 errors, provenance clean, ``Weight`` gone, ``Operating Weight`` reads
back with the mass spec id and the kg value on every type row.

Validator-green is necessary, NOT certification (hard rule 4): the mass
parameter is one more measurable ``ParamDefValue`` of the kind the panelboard /
switchboard sets already carry blank; no desktop round is claimed here.

Run: .venv/bin/python -m pytest tests/test_transformer_mass_630.py -q
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import needs_schema                              # noqa: E402
from rvt.famgen import standards as ST                         # noqa: E402
from rvt.famgen import skeleton as SK                          # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402

MASS_SPEC = "autodesk.spec.aec.structural:mass-1.0.0"
MASS_COLUMN = "Operating Weight##MASS##POUNDS_MASS"
EATON = {"kva": 30, "types": [30, 45, 75]}
EATON_LB = {"30 kVA 480-208Y/120": 409.0, "45 kVA 480-208Y/120": 416.0,
            "75 kVA 480-208Y/120": 570.0}
HPS = {"kva": 75, "vendor": "hps"}
HPS_LB = {"75 kVA 480-208Y/120": 0.0}                          # nothing published -> blank


@pytest.fixture(scope="module")
def eaton():
    return F.make_transformer(**EATON)


@pytest.fixture(scope="module")
def hps():
    return F.make_transformer(**HPS)


def _weight_names(doc):
    """Every parameter on ``doc`` a Revit user reads as THE weight."""
    return [n for n in doc.params if ST.meaning_key(n) == ST.meaning_key("Operating Weight")]


def _type_values(doc, caption):
    """{type name: value} of ``caption`` in the document's type table."""
    pid = doc.params[caption].elem_id
    return {name: vals[pid] for name, vals in doc.types}


# ---------------------------------------------------------------------------
# 1. the unit path: spec id sourced, conversion defined, catalog token
# ---------------------------------------------------------------------------

def test_the_mass_spec_is_the_one_our_units_table_declares_and_formats_in_pounds():
    assert F.SPEC["mass"] == ST.SPECS["mass"] == MASS_SPEC
    # factory's spec table is the subset of the standards vocabulary it has
    # converters / catalog columns for -- same ids, so check_specs' units-table
    # provenance gate covers every spec a constructor authors
    assert {k: v for k, v in ST.SPECS.items() if k in F.SPEC} == F.SPEC
    with open(ST._UNITS_ASSET, encoding="utf-8") as fh:
        fmt = {e["first"]["m_typeId"]: e["second"] for e in json.load(fh)["m_formatOptionsMap"]}
    # authorable (the format formats it), displayed in the unit the catalog column names
    assert fmt[MASS_SPEC]["m_unitTypeId"]["m_typeId"] == "autodesk.unit.unit:poundsMass-1.0.1"


def test_pounds_convert_to_kilograms_by_the_definition_of_the_pound():
    assert F.KG_PER_LB == 0.45359237                           # exact by definition, not measured
    assert F.pounds(570) == pytest.approx(258.5476509)
    assert F._TO_INTERNAL["mass"] is F.pounds


def test_the_type_catalog_declares_mass_in_pounds_mass():
    assert F.TYPE_CATALOG_COLUMNS["mass"] == ("MASS", "POUNDS_MASS")
    assert F._catalog_header([("Operating Weight", "mass")]) == [MASS_COLUMN]


# ---------------------------------------------------------------------------
# 2. the table: no exception carved, one entry per meaning, check clean
# ---------------------------------------------------------------------------

def test_the_transformer_set_carries_operating_weight_and_no_exception():
    xf = {p.name: p for p in ST.standard_params("transformer")}
    assert "Weight" not in xf
    assert xf["Operating Weight"].spec == "mass" and xf["Operating Weight"].group == "identity"
    assert ST.check_specs() == []


# ---------------------------------------------------------------------------
# 3. the document: Eaton (weight published) and HPS (none) name it identically
# ---------------------------------------------------------------------------

@needs_schema
def test_eaton_transformer_stores_the_catalog_pounds_as_kilograms_under_operating_weight(eaton):
    doc = eaton.doc
    assert _weight_names(doc) == ["Operating Weight"]         # one entry per meaning, the table's spelling
    pe = doc.params["Operating Weight"]
    assert pe.refs["spec"] == MASS_SPEC and pe.refs["group"] == SK.PGROUP_IDENTITY
    kg = _type_values(doc, "Operating Weight")
    assert set(kg) == set(EATON_LB)
    for name, lb in EATON_LB.items():
        assert kg[name] == pytest.approx(lb * F.KG_PER_LB), name
    # the standards step left the constructor's parameter exactly as made
    skipped = {s["name"]: s["why"] for s in eaton.standards["skipped"]}
    assert skipped["Operating Weight"] == "already authored by the constructor"


@needs_schema
def test_hps_transformer_carries_the_same_entry_blank_and_no_catalog_column(eaton, hps):
    doc = hps.doc
    assert _weight_names(doc) == ["Operating Weight"]
    assert doc.params["Operating Weight"].refs["spec"] == MASS_SPEC
    assert _type_values(doc, "Operating Weight") == HPS_LB     # blank, never invented
    assert "Weight" not in F.type_catalog_text(hps).splitlines()[0]   # unpublished -> no column at all
    assert sorted(doc.params) == sorted(eaton.doc.params)      # Eaton and HPS name every parameter identically


@needs_schema
def test_the_eaton_type_catalog_cells_stay_in_pounds_and_the_report_names_the_inferred_column(
        eaton, hps, tmp_path):
    lines = F.type_catalog_text(eaton).split("\r\n")
    head = lines[0].split(",")
    assert not any(h.startswith("Weight##") for h in head)
    col = head.index(MASS_COLUMN)
    assert [row.split(",")[col] for row in lines[1:4]] == ["409", "416", "570"]
    # the MASS##POUNDS_MASS declaration is inferred from the vocabulary's law:
    # the sidecar report says so where a user reads it -- and only when present
    rep = F.write_type_catalog(eaton, str(tmp_path / "eaton.txt"))
    assert rep["inferred_columns"] == [MASS_COLUMN] and "inferred" in rep["note"]
    assert "inferred_columns" not in F.write_type_catalog(hps, str(tmp_path / "hps.txt"))


# ---------------------------------------------------------------------------
# 4. ON THE FILE: valid, provenance clean, reads back as a mass in kg
# ---------------------------------------------------------------------------

def _write_valid(prod, path):
    from rvt.frontdoor.standalone import standalone_family_write
    rep = standalone_family_write(prod, path)
    fam = (rep.get("validate") or {}).get("family_mode") or {}
    assert fam.get("verdict") == "VALID" and fam.get("n_errors") == 0, fam.get("errors")
    assert (rep.get("provenance") or {}).get("ok") is True, rep["provenance"].get("suspects")
    return rep


def _file_param(path, caption):
    """(ParamDef, {type name: m_value}, every caption) of ``caption`` off the WRITTEN .rfa."""
    from rvt.families import FamilyIndex
    idx = FamilyIndex(path)
    defs = {eid: idx.value(0, eid)["m_pParamDef"]["value"]
            for eid in idx.ids_of_class(0, "ParamElemFamily")}
    pids = [eid for eid, d in defs.items() if d["m_caption"] == caption]
    assert len(pids) == 1, (caption, sorted(d["m_caption"] for d in defs.values()))
    per_type = {}
    for fid in idx.ids_of_class(0, "Family"):
        v = idx.value(0, fid) or {}
        for pr in ((v.get("m_pFamilyTypes") or {}).get("value") or {}).get("m_pairs") or []:
            for p in (pr.get("params") or {}).get("m_params") or []:
                if p.get("m_paramId") == pids[0]:
                    per_type[pr.get("name")] = p.get("m_value")
    return defs[pids[0]], per_type, sorted(d["m_caption"] for d in defs.values())


@needs_schema
@pytest.mark.parametrize("kwargs,expect_lb,primary_lb", [
    (EATON, EATON_LB, 409.0),
    (HPS, HPS_LB, 0.0),
], ids=["eaton", "hps"])
def test_the_written_transformer_reads_back_operating_weight_as_a_mass_in_kilograms(
        tmp_path, kwargs, expect_lb, primary_lb):
    from rvt.convert.modify_family import inventory_family
    path = str(tmp_path / "xfmr.rfa")
    _write_valid(F.make_transformer(**kwargs), path)
    pdef, per_type, captions = _file_param(path, "Operating Weight")
    assert "Weight" not in captions
    assert pdef["m_specTypeId"]["m_typeId"] == MASS_SPEC                  # a measurable ParamDefValue, mass
    assert pdef["m_groupTypeId"]["m_typeId"] == SK.PGROUP_IDENTITY
    assert set(per_type) == set(expect_lb)
    for name, lb in expect_lb.items():
        assert per_type[name] == pytest.approx(lb * F.KG_PER_LB), name
    # the edit lane's inventory says the same: a mass, carried in m_value (the primary type's)
    ow = inventory_family(path).param_by_caption("Operating Weight")
    assert ow["spec"] == MASS_SPEC and ow["carrier"] == "m_value"
    assert ow["current"] == pytest.approx(primary_lb * F.KG_PER_LB)

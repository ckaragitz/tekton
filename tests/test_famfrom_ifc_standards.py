"""test_famfrom_ifc_standards.py -- the IFC -> family route carries the
Lighting Fixtures STANDARD parameter set exactly like the factory (#631).

Issue #631 (Refs #622 #601 #498): ``rvt.ifc.famfrom_ifc.make_downlight`` used
to author its own ``Lumens`` / ``Color Temperature`` and applied NO category
standards, so an IFC-born luminaire and a prompt-born one
(``rvt.famgen.factory.make_luminaire``) named the same quantity differently and
carried different parameter sets.  Now the downlight hands its photometric job
values to the factory's own standards step (``factory._std`` ->
``rvt.famgen.standards.apply``) -- the table owns the spelling, spec and group
of every standard parameter -- and carries the category set the same way the
factory constructors do.

Evidence tiers:

1. COMPOSITION.  The downlight document carries the Lighting Fixtures authored
   set; every quantity is listed ONCE (``standards.meaning_key`` pairwise
   distinct); the legacy spellings are gone; the constructor's own parameters
   are never redefined; job values land under the table's spelling and an
   unsourced value stays BLANK (never invented); a synonym offered by a caller
   (an IFC-pset style key) fills the table's entry instead of growing a twin.
2. PARITY.  For every quantity BOTH luminaire routes carry, the caption is the
   same string -- in the documents and read back off the two written ``.rfa``.
3. ON THE FILE.  Both families emit on the bundled base family-mode VALID with
   0 errors and provenance clean, and the standard captions read back as
   ``ParamElemFamily`` records.

Fresh-clone safe: the IFC input is tracked (``inputs/ifc/``), the reader is the
bundled steplite shim, the container is the bundled genesis base.  Validator-
green is necessary, NOT certification (hard rule 4).

Run: .venv/bin/python -m pytest tests/test_famfrom_ifc_standards.py -q
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import HAVE_SCHEMA                               # noqa: E402
from rvt.famgen import standards as ST                         # noqa: E402
from rvt.famgen import factory as F                            # noqa: E402
from rvt.ifc import famfrom_ifc as FI                          # noqa: E402
from rvt.ifc import product_facts as PF                        # noqa: E402

IFC = os.path.join(ROOT, "inputs", "ifc", "chicago-plenum-downlight.ifc")
needs_build = pytest.mark.skipif(not (os.path.exists(IFC) and HAVE_SCHEMA),
                                 reason="IFC input / class schema absent")

LEGACY = {"Lumens", "Color Temperature"}
STANDARD = {p.name for p in ST.authored_params(FI.STD_CATEGORY)}
OWN_FOUR = {"Wattage", "Voltage", "Lamp", "Mounting"}      # authored by the constructor itself


@pytest.fixture(scope="module")
def facts():
    return PF.extract_product_facts(IFC)


@pytest.fixture(scope="module")
def ifc_born(facts):
    return FI.make_downlight(facts=facts, start_id=1000)


@pytest.fixture(scope="module")
def prompt_born():
    return F.make_luminaire()


def _twins(names):
    """{meaning key: [captions]} for every quantity spelled more than once."""
    by_key = {}
    for n in names:
        by_key.setdefault(ST.meaning_key(n), []).append(n)
    return {k: v for k, v in by_key.items() if len(v) > 1}


def _differing(a_names, b_names):
    """{meaning key: (caption in a, caption in b)} for shared quantities the
    two caption sets spell differently."""
    a = {ST.meaning_key(n): n for n in a_names}
    b = {ST.meaning_key(n): n for n in b_names}
    return {k: (a[k], b[k]) for k in set(a) & set(b) if a[k] != b[k]}


def _type_values(prod):
    _tname, vals = prod.doc.types[0]
    return {n: vals[pe.elem_id] for n, pe in prod.doc.params.items()}


# ---------------------------------------------------------------------------
# 1. composition
# ---------------------------------------------------------------------------

@needs_build
def test_the_ifc_born_luminaire_carries_the_lighting_fixture_standard_set(ifc_born):
    rep = ifc_born.standards
    assert rep is not None and rep["covered"] and rep["category"] == FI.STD_CATEGORY
    names = set(ifc_born.doc.params)
    assert STANDARD <= names, STANDARD - names
    assert not LEGACY & names
    # the IFC contract + dimension parameters are still all there
    for caption, *_rest in FI.CCEA_CONTRACT_PARAMS + FI.DIM_PARAMS:
        assert caption in names, caption
    assert {"Wattage", "Voltage", "Photometric Web File"} <= names
    assert ifc_born.summary()["standards"]["category"] == FI.STD_CATEGORY


@needs_build
def test_every_quantity_is_listed_once_and_the_constructors_own_are_never_redefined(ifc_born):
    assert _twins(ifc_born.doc.params) == {}
    for s in ifc_born.standards["skipped"]:
        assert s["why"].startswith(("already authored", "already on the document")), s
    assert {s["name"] for s in ifc_born.standards["skipped"]} == OWN_FOUR


@needs_build
def test_unsourced_photometrics_stay_blank_and_nothing_is_invented(ifc_born):
    """The Chicago-plenum IFC states no lumens / CCT: the standard parameters
    exist (an engineer can fill them) but hold their storage class's blank."""
    vals = _type_values(ifc_born)
    assert ifc_born.standards["filled"] == []
    assert "values_not_placed" not in ifc_born.standards
    for _key, caption in FI.PHOTOMETRIC_JOB_VALUES:
        assert vals[caption] == 0.0, caption
    assert vals["Color Rendering Index"] == 0.0 and vals["Driver Type"] == ""


@needs_build
@pytest.mark.parametrize("kwargs,expected", [
    # job parameters + a standard value under the table's own spelling
    ({"lumens": 900, "cct": 3000, "wattage": 11.5,
      "standard_values": {"Color Rendering Index": 90.0}},
     {"Luminous Flux": 900.0, "Initial Color Temperature": 3000.0,
      "Color Rendering Index": 90.0}),
    # IFC-pset habits: 'CCT' / 'Lamp Lumens' fold onto the table's entries
    # (standards.meaning_key) -- one entry each, filled, no twin grown
    ({"standard_values": {"CCT": 2700.0, "Lamp Lumens": 650.0}},
     {"Initial Color Temperature": 2700.0, "Luminous Flux": 650.0}),
])
def test_values_land_under_the_tables_spelling_whatever_spelling_offered_them(
        facts, kwargs, expected):
    prod = FI.make_downlight(facts=facts, start_id=1000, **kwargs)
    names = set(prod.doc.params)
    assert not (LEGACY | {"CCT", "Lamp Lumens"}) & names
    assert _twins(names) == {}
    vals = _type_values(prod)
    for caption, value in expected.items():
        assert vals[caption] == pytest.approx(value), caption
    assert set(prod.standards["filled"]) == set(expected)
    assert "values_not_placed" not in prod.standards


@needs_build
def test_standards_false_is_the_regression_control(facts):
    prod = FI.make_downlight(facts=facts, standards=False, lumens=900, start_id=1000)
    assert prod.standards is None and "standards" not in prod.summary()
    names = set(prod.doc.params)
    own = {c for c, *_r in FI.CCEA_CONTRACT_PARAMS + FI.DIM_PARAMS}
    assert names == own | {"Wattage", "Voltage", "Photometric Web File"}
    assert not (STANDARD - OWN_FOUR) & names and not LEGACY & names
    # a given photometric value is then said out loud, not silently dropped
    assert any("standards off" in n and "Luminous Flux" in n for n in prod.doc.notes)


def test_the_famspec_downlight_kind_exposes_the_same_switches_as_the_constructor():
    """The famspec surface (spec/famspec.schema.json, kind = downlight) mirrors
    make_downlight's keyword arguments -- ``standards`` / ``standard_values``
    included, as every catalog kind already does -- so the product route can
    reach what the constructor accepts (``facts`` is a Python object, not a
    famspec field; ``target_version`` is the route's own field)."""
    import inspect
    from rvt.frontdoor import famspec as FS
    fields = set(FS.schema()["definitions"]["downlight"]["properties"]) - {"kind", "target_version"}
    params = set(inspect.signature(FI.make_downlight).parameters) - {"start_id", "facts"}
    assert fields == params, fields ^ params
    assert FS.validate({"kind": "downlight", "standards": False}) == []
    assert FS.validate({"kind": "downlight", "standard_values": {"CCT": 3000}}) == []


# ---------------------------------------------------------------------------
# 2. parity with the prompt-born luminaire (the factory archetype)
# ---------------------------------------------------------------------------

@needs_build
def test_ifc_born_and_prompt_born_spell_every_shared_quantity_the_same_way(ifc_born,
                                                                          prompt_born):
    assert STANDARD <= set(prompt_born.doc.params)
    assert _differing(ifc_born.doc.params, prompt_born.doc.params) == {}


# ---------------------------------------------------------------------------
# 3. on the file
# ---------------------------------------------------------------------------

def _write_and_read_captions(prod, path):
    from rvt.frontdoor.standalone import standalone_family_write
    from rvt.families import FamilyIndex
    rep = standalone_family_write(prod, path)
    fam = (rep.get("validate") or {}).get("family_mode") or {}
    assert fam.get("verdict") == "VALID" and fam.get("n_errors") == 0, fam.get("errors")
    assert (rep.get("provenance") or {}).get("ok") is True, rep["provenance"].get("suspects")
    assert rep["ok"] is True
    idx = FamilyIndex(path)
    return {idx.value(0, eid)["m_pParamDef"]["value"]["m_caption"]
            for eid in idx.ids_of_class(0, "ParamElemFamily")}


@needs_build
def test_both_written_families_read_back_the_same_captions_for_shared_quantities(
        ifc_born, prompt_born, tmp_path):
    ifc_caps = _write_and_read_captions(ifc_born, str(tmp_path / "ifc_downlight.rfa"))
    prompt_caps = _write_and_read_captions(prompt_born, str(tmp_path / "prompt_troffer.rfa"))
    assert ifc_caps == set(ifc_born.doc.params)          # the file carries what the doc does
    assert STANDARD <= ifc_caps and STANDARD <= prompt_caps
    assert not LEGACY & (ifc_caps | prompt_caps)
    assert _twins(ifc_caps) == {} and _twins(prompt_caps) == {}
    assert _differing(ifc_caps, prompt_caps) == {}

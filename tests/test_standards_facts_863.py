"""#863: a constructor's own KNOWN facts reach its standard parameters.

A 45 kVA transformer's catalog record says 60 Hz (tier ``fact``), so its standard
**Frequency** is 60 Hz on every type -- while ``Voltage`` and ``Wires`` stay blank
(a transformer has two sides: one value would be a guess).  Only a known tier
(``fact`` / ``given`` / ``derived``) fills a standard parameter (S-2026-08-11-a);
a value the types disagree on stays blank, said; the caller's values win.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import standards as ST  # noqa: E402


def _rows(prod, name):
    pid = prod.doc.params[name].elem_id
    fam = prod.doc.self_family.obj
    return [{e["m_paramId"]: e for e in r["params"]["m_params"]}[pid]
            for r in fam["m_pFamilyTypes"]["value"]["m_pairs"]]


def test_a_transformer_carries_its_catalog_frequency_on_every_type():
    prod = F.make_transformer(kva=45)
    rows = _rows(prod, "Frequency")
    assert rows and all(r["m_value"] == pytest.approx(60.0) for r in rows)
    assert prod.standards["filled_from_facts"] == [
        {"name": "Frequency", "fact": "frequency_hz", "tier": "fact",
         "source": prod.facts.values["frequency_hz"].source}]
    for honest_blank in ("Voltage", "Wires"):
        assert all(r["m_value"] == 0.0 and r["m_int"] == 0 and r["m_str"] == ""
                   for r in _rows(prod, honest_blank))


def test_the_callers_value_wins_over_the_fact():
    prod = F.make_transformer(kva=45, standard_values={"Frequency": 50.0})
    assert all(r["m_value"] == pytest.approx(50.0) for r in _rows(prod, "Frequency"))
    assert "filled_from_facts" not in prod.standards


def test_a_luminaire_carries_its_catalog_cri():
    prod = F.make_luminaire()
    assert prod.facts.values["cri"].kind == "fact"
    rows = _rows(prod, "Color Rendering Index")
    assert all(r["m_value"] == pytest.approx(float(prod.facts.values["cri"].value)) for r in rows)


@pytest.mark.parametrize("tier", ["assumed", "nominal", "ours"])
def test_an_unknown_tier_never_fills_a_standard(tier):
    sh = F.FactSheet(subject="probe")
    sh.set("frequency_hz", 60, kind=tier, source="probe")
    assert ST.values_from_facts(sh) == ({}, [], [])


def test_types_that_disagree_leave_it_blank_and_say_so():
    a, b = F.FactSheet(subject="a"), F.FactSheet(subject="b")
    a.set("cri", 80, kind="fact", source="sheet a")
    b.set("cri", 90, kind="fact", source="sheet b")
    assert ST.values_from_facts([a, b]) == ({}, [], ["Color Rendering Index"])
    b.set("cri", 80, kind="fact", source="sheet b")
    vals, prov, split = ST.values_from_facts([a, b])
    assert vals == {"Color Rendering Index": 80} and not split


def test_a_disagreement_is_noted_on_the_document():
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("lighting_fixture", "Zz Split", work_plane_based=False)
    doc.add_type("T", {})
    a, b = F.FactSheet(subject="a"), F.FactSheet(subject="b")
    a.set("cri", 80, kind="fact", source="a")
    b.set("cri", 90, kind="fact", source="b")
    rep = ST.apply_safe(doc, "lighting_fixture", True, None, facts=[a, b])
    assert "Color Rendering Index" not in rep["filled"]
    assert any("'Color Rendering Index' left blank: the family's types do not all hold one "
               "known value" in n for n in doc.notes)


def test_standards_off_authors_nothing_from_facts():
    prod = F.make_transformer(kva=45, standards=False)
    assert "Frequency" not in prod.doc.params
    assert not any("Frequency" in n for n in prod.doc.notes)



# --- #1031 review nits -------------------------------------------------------------------

def test_a_multi_type_transformer_carries_the_frequency_on_every_type_and_cites_each():
    prod = F.make_transformer(types=[30, 45, 75])
    rows = _rows(prod, "Frequency")
    assert len(rows) == 3 and all(r["m_value"] == pytest.approx(60.0) for r in rows)
    (p,) = prod.standards["filled_from_facts"]
    srcs = {f.source for f in (s.values["frequency_hz"] for s in prod._sheets())}
    assert all(s in p["source"] for s in srcs if s)


def test_a_fact_for_a_parameter_the_category_lacks_is_not_reported_as_the_callers():
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("generic_model", "Zz Leak", work_plane_based=False)
    doc.add_type("T", {})
    sh = F.FactSheet(subject="probe")
    sh.set("frequency_hz", 60, kind="fact", source="probe")
    rep = ST.apply_safe(doc, "generic_model", True, None, facts=sh)
    assert "values_not_placed" not in rep and "values_unusable" not in rep
    assert not rep.get("filled_from_facts")


def test_an_unusable_fact_is_reported_apart_from_the_callers_values():
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("transformer", "Zz Unusable", work_plane_based=False)
    doc.add_type("T", {})
    sh = F.FactSheet(subject="probe")
    sh.set("frequency_hz", "60 Hz", kind="fact", source="probe")
    rep = ST.apply_safe(doc, "transformer", True, None, facts=sh)
    assert "values_unusable" not in rep and rep.get("facts_not_written") == ["Frequency"]


def test_a_type_without_the_fact_leaves_it_blank_and_says_so():
    a, b = F.FactSheet(subject="a"), F.FactSheet(subject="b")
    a.set("cri", 82, kind="fact", source="a")
    assert ST.values_from_facts([a, b]) == ({}, [], ["Color Rendering Index"])
    b.set("cri", 82, kind="nominal", source="b")
    assert ST.values_from_facts([a, b])[2] == ["Color Rendering Index"]
    prod = F.make_luminaire(types=[38, {"wattage": 99, "size": "2x2"}])
    assert any("'Color Rendering Index' left blank" in n for n in prod.doc.notes)


def test_equal_values_in_different_number_types_agree():
    a, b, c = (F.FactSheet(subject=x) for x in "abc")
    a.set("frequency_hz", 60, kind="fact", source="a")
    b.set("frequency_hz", 60.0, kind="fact", source="b")
    c.set("frequency_hz", "60", kind="given", source="c")
    vals, prov, split = ST.values_from_facts([a, b, c])
    assert vals == {"Frequency": 60} and not split
    assert prov[0]["source"] == "a; b; c"


def test_a_filled_fact_is_named_as_the_familys_own_not_the_callers():
    prod = F.make_transformer(kva=45)
    assert any("'Frequency' (fact) came from the family's own facts" in n
               for n in prod.doc.notes)



def test_a_multi_type_provenance_names_every_tier():
    a, b = F.FactSheet(subject="a"), F.FactSheet(subject="b")
    a.set("frequency_hz", 60, kind="fact", source="cat")
    b.set("frequency_hz", 60, kind="derived", source="calc")
    prov = ST.values_from_facts([a, b])[1]
    assert prov[0]["tier"] == "fact; derived" and prov[0]["source"] == "cat; calc"


def test_a_pathological_fact_never_blocks_the_family():
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("electrical_equipment", "Zz Huge", work_plane_based=False)
    doc.add_type("T", {})
    a = F.FactSheet(subject="a")
    a.set("frequency_hz", 10 ** 400, kind="fact", source="a")
    rep = ST.apply_safe(doc, "electrical_equipment", True, None, facts=a)   # no raise
    assert rep is not None and len(rep["applied"]) > 1      # only Frequency goes blank
    assert "Frequency" not in rep["filled"]


def test_a_skipped_split_parameter_is_not_noted_as_left_blank():
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("lighting_fixture", "Zz Skip", work_plane_based=False)
    doc.add_type("T", {})
    a, b = F.FactSheet(subject="a"), F.FactSheet(subject="b")
    a.set("cri", 80, kind="fact", source="a")
    b.set("cri", 90, kind="fact", source="b")
    ST.apply_safe(doc, "lighting_fixture", True, None, facts=[a, b],
                  skip=["Color Rendering Index"])
    assert not any("left blank" in n for n in doc.notes)

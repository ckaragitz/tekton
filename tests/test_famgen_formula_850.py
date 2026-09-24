"""test_famgen_formula_850.py -- family parameter FORMULAS as Revit's expression tree.

Revit stores a formula as a parsed tree in each FamilyParamValue's ``m_oExpression``
(the family's value set and every type row), with the evaluated result as the value.
The operator / function codes were pinned numerically against the owner's reference
pack (#850); these tests pin the encoder, the unit rule, the refusals and the
writer integration -- on OUR documents only (no reference file is read here).
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import needs_schema                         # noqa: E402

from rvt.famgen import formula as F                        # noqa: E402

L, N = F.SPEC_LENGTH, F.SPEC_NUMBER
PARAMS = {"Width": F.ParamRef(11, L), "Height": F.ParamRef(12, L),
          "Box Depth": F.ParamRef(13, L), "Count": F.ParamRef(14, N),
          "Is Tall": F.ParamRef(15, F.SPEC_YESNO)}


def _tree(text):
    return F.parse_formula(text, PARAMS)


def test_division_by_a_number_keeps_length():
    tree, spec = _tree("Width / 2")
    assert spec == L
    v = tree["value"]
    assert tree["ptr_class"] == "BinaryOperatorExpression" and v["m_binaryOperator"] == 4
    assert v["m_pLeftSubexpression"] == {"ptr_class": "ParameterExpression", "pid": -1,
                                         "value": {"m_paramId": 11}}
    assert v["m_pRightSubexpression"]["value"] == {"m_value": 2.0,
                                                   "m_specTypeId": {"m_typeId": N}}


@pytest.mark.parametrize("text,feet", [("1'", 1.0), ('6"', 0.5), ("304.8 mm", 1.0),
                                       ("30.48 cm", 1.0), ("0.3048 m", 1.0), ("12 in", 1.0)])
def test_a_literal_with_a_unit_is_a_length_constant_in_feet(text, feet):
    tree, spec = _tree(f"Width + {text}")
    right = tree["value"]["m_pRightSubexpression"]["value"]
    assert spec == L and right["m_specTypeId"]["m_typeId"] == L
    assert right["m_value"] == pytest.approx(feet)


@pytest.mark.parametrize("text", ["Width + 1", "Width > 2", "Width - Count",
                                  "if(Is Tall, Width, 3)"])
def test_inconsistent_units_are_refused_like_revit(text):
    with pytest.raises(F.FormulaError, match="inconsistent units"):
        _tree(text)


@pytest.mark.parametrize("text", ["Width ^ 2", "sqrt(Count)", "abs(Count)",
                                  "Width >= 1'", "size_lookup(T, \"A\", 1', Width)"])
def test_unpinned_codes_are_refused_never_approximated(text):
    with pytest.raises(F.FormulaError, match="no pinned code"):
        _tree(text)


def test_names_with_spaces_resolve_longest_first():
    tree, _ = _tree("Box Depth * 2")
    assert tree["value"]["m_pLeftSubexpression"]["value"]["m_paramId"] == 13


@pytest.mark.parametrize("text,code", [("Width = 1'", 6), ("Width > 1'", 7), ("Width < 1'", 8),
                                       ("Width + 1'", 1), ("Width - 1'", 2), ("Count * 2", 3),
                                       ("Count / 2", 4)])
def test_operator_codes(text, code):
    assert _tree(text)[0]["value"]["m_binaryOperator"] == code


@pytest.mark.parametrize("text,code,nargs", [
    ("if(Is Tall, Width, Height)", 10, 3), ("and(Is Tall, Width > 1')", 12, 2),
    ("or(Is Tall, Width > 1', Height < 2')", 11, 3), ("not(Is Tall)", 13, 1),
    ("round(Count)", 18, 1), ("tan(Count)", 3, 1)])
def test_function_codes(text, code, nargs):
    v = _tree(text)[0]["value"]
    assert v["m_function"] == code and len(v["m_subexpressions"]) == nargs


def test_evaluate_matches_revit_semantics():
    vals = {11: 2.0, 12: 5.0, 13: 0.5, 14: 7.0, 15: 1}
    ev = lambda t: F.evaluate(_tree(t)[0], vals)          # noqa: E731
    assert ev("Width / 2") == pytest.approx(1.0)
    assert ev("if(Height > 4', Height - 6\", Height)") == pytest.approx(4.5)
    assert ev("round(Count / 2)") == 4.0                   # 3.5 rounds half up
    assert ev("and(Is Tall, not(Width < 1'))") is True
    assert ev("-(Width) + 3'") == pytest.approx(1.0)


def test_referenced_params_for_dependency_order():
    tree, _ = _tree("if(Is Tall, Width, Height + Box Depth)")
    assert sorted(set(F.referenced_params(tree))) == [11, 12, 13, 15]


# --- writer integration (our own FamilyDoc) ------------------------------------------

def _probe_doc():
    from rvt.famgen import skeleton as fs
    doc = fs.new_family_document("electrical_equipment", "Formula Probe",
                                 part_type=fs.PART_TYPE["panelboard"], work_plane_based=True)
    p = {"w": doc.add_family_parameter("Width", fs.SPEC_LENGTH, fs.PGROUP_DIMENSIONS),
         "h": doc.add_family_parameter("Height", fs.SPEC_LENGTH, fs.PGROUP_DIMENSIONS),
         "cover": doc.add_family_parameter("Cover Height", fs.SPEC_LENGTH, fs.PGROUP_DIMENSIONS,
                                           formula="if(Is Tall, Height - 6\", Height + Half Width)"),
         "hw": doc.add_family_parameter("Half Width", fs.SPEC_LENGTH, fs.PGROUP_DIMENSIONS,
                                        formula="Width / 2"),
         "tall": doc.add_family_parameter("Is Tall", fs.SPEC_YESNO, fs.PGROUP_DIMENSIONS,
                                          formula="Height > 4'"),
         "bad": doc.add_family_parameter("Bad", fs.SPEC_LENGTH, fs.PGROUP_DIMENSIONS,
                                         formula="Width + 1")}
    doc.add_type("Small", {"Width": fs.mm(500), "Height": fs.mm(900)})
    doc.add_type("Large", {"Width": fs.mm(600), "Height": fs.mm(1800)})
    return fs, doc, p


def _rows(fam):
    return {r["name"]: {e["m_paramId"]: e for e in r["params"]["m_params"]}
            for r in fam["m_pFamilyTypes"]["value"]["m_pairs"]}


@needs_schema
def test_formulas_are_written_on_every_type_row_with_evaluated_values():
    fs, doc, p = _probe_doc()
    doc.finalize()
    rows = _rows(doc.self_family.obj)
    small, large = rows["Small"], rows["Large"]
    mm = lambda e: e["m_value"] * 304.8                     # noqa: E731
    assert mm(small[p["hw"].elem_id]) == pytest.approx(250.0)
    assert small[p["tall"].elem_id]["m_int"] == 0 and large[p["tall"].elem_id]["m_int"] == 1
    # dependency order: Cover reads Is Tall and Half Width, both formulas themselves
    assert mm(small[p["cover"].elem_id]) == pytest.approx(900 + 250)
    assert mm(large[p["cover"].elem_id]) == pytest.approx(1800 - 152.4)
    # the SAME tree on every row (the reference law, 2,052 / 2,052)
    for key in ("hw", "tall", "cover"):
        assert small[p[key].elem_id]["m_oExpression"] == large[p[key].elem_id]["m_oExpression"]
        assert small[p[key].elem_id]["m_oExpression"] is not None
    # the current-type value set carries it too
    cur = {e["m_paramId"]: e for e in doc.self_family.obj["m_familyParams"]["value"]["m_params"]}
    assert cur[p["hw"].elem_id]["m_oExpression"]["ptr_class"] == "BinaryOperatorExpression"


@needs_schema
def test_a_formula_that_cannot_be_stored_is_left_out_and_said():
    fs, doc, p = _probe_doc()
    doc.finalize()
    rows = _rows(doc.self_family.obj)
    assert rows["Small"][p["bad"].elem_id]["m_oExpression"] is None
    assert any("'Bad' NOT written: inconsistent units" in n for n in doc.notes)


@needs_schema
def test_a_circular_formula_is_refused_and_said():
    from rvt.famgen import skeleton as fs
    doc = fs.new_family_document("electrical_equipment", "Cycle Probe",
                                 part_type=fs.PART_TYPE["panelboard"], work_plane_based=True)
    a = doc.add_family_parameter("A", fs.SPEC_LENGTH, formula="B + 1'")
    doc.add_family_parameter("B", fs.SPEC_LENGTH, formula="A + 1'")
    doc.add_type("T", {})
    doc.finalize()
    assert any("circular reference" in n for n in doc.notes)
    assert _rows(doc.self_family.obj)["T"][a.elem_id]["m_oExpression"] is None


@needs_schema
def test_the_document_with_formulas_round_trips_through_the_schema():
    _fs, doc, _p = _probe_doc()
    doc.finalize()
    assert doc.roundtrip()["failed"] == 0


@needs_schema
def test_an_emitted_rfa_carries_the_trees_and_validates(tmp_path):
    from rvt.famgen.famdoc_adoc import emit_family_rfa_v2
    from rvt.frontdoor.standalone import bundled_base_path
    from rvt.families import FamilyIndex
    from rvt.validate import Validator
    fs, doc, p = _probe_doc()
    doc.finalize()
    out = str(tmp_path / "formula_probe.rfa")
    emit_family_rfa_v2(doc, out, donor=bundled_base_path(), write_reports=False)
    fi = FamilyIndex(out)
    fam = None
    for e, rec in fi.unit_records(0).get(102, {}).items():
        if fi.class_name(rec.class_id) == "Family":
            v = fi.decode(0, e, 102).value
            if v.get("m_surrogateId") == -1:
                fam = v
    rows = _rows(fam)
    assert rows["Large"][p["cover"].elem_id]["m_oExpression"]["ptr_class"] == "FunctionExpression"
    assert rows["Large"][p["cover"].elem_id]["m_value"] * 304.8 == pytest.approx(1647.6)
    report = Validator(out, family=True).run()
    errors = report.errors() if callable(report.errors) else report.errors
    assert not errors, [e.message for e in errors][:5]

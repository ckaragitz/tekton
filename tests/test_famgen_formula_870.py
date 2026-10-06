"""test_famgen_formula_870.py -- TEXT formulas (#870), as the reference library uses them.

A private census of the owner's library (counts only, nothing committed) found 4,002
formulas carrying text: 3,278 bare string constants, the rest ``if()`` chains choosing
between texts over Yes/No conditions; every text result is stored in the row's
``m_str`` with ``m_value`` 0.0, ``m_int`` 0, ``m_elemId`` -1, and a
``StringConstantExpression`` holds only ``m_value``.  These tests pin the encoder, the
refusals (no operator takes text) and the writer -- on OUR documents only.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import needs_schema                         # noqa: E402

from rvt.famgen import formula as F                        # noqa: E402

PARAMS = {"Flag": F.ParamRef(1, F.SPEC_YESNO), "Name": F.ParamRef(2, F.SPEC_TEXT),
          "Width": F.ParamRef(3, F.SPEC_LENGTH), "Count": F.ParamRef(4, F.SPEC_NUMBER),
          "Other": F.ParamRef(5, F.SPEC_YESNO)}


def test_a_string_constant_holds_only_its_value():
    tree, spec = F.parse_formula('"Pull Box"', PARAMS)
    assert spec == F.SPEC_TEXT
    assert tree == {"ptr_class": "StringConstantExpression", "pid": -1,
                    "value": {"m_value": "Pull Box"}}
    assert F.evaluate(tree, {}) == "Pull Box"


def test_an_if_chain_chooses_between_texts():
    text = 'if(Flag, "A", if(and(Other, Width > 2\'), "B", if(Count = 3, Name, "D")))'
    tree, spec = F.parse_formula(text, PARAMS)
    assert spec == F.SPEC_TEXT
    assert tree["ptr_class"] == "FunctionExpression" and tree["value"]["m_function"] == F.FUNCTION["if"]
    base = {1: 0, 2: "nm", 3: 1.0, 4: 3.0, 5: 0}
    assert F.evaluate(tree, {**base, 1: 1}) == "A"
    assert F.evaluate(tree, {**base, 5: 1, 3: 3.0}) == "B"
    assert F.evaluate(tree, base) == "nm"
    assert F.evaluate(tree, {**base, 4: 2.0}) == "D"


def test_a_text_parameter_may_be_named():
    tree, spec = F.parse_formula("Name", PARAMS)
    assert spec == F.SPEC_TEXT and tree["value"] == {"m_paramId": 2}


def test_an_empty_branch_is_a_value_but_an_empty_formula_is_no_formula():
    tree, _ = F.parse_formula('if(Flag, "", "x")', PARAMS)
    assert F.evaluate(tree, {1: 1}) == ""
    for text in ('""', '("")', '((""))'):
        with pytest.raises(F.FormulaError, match="NO formula"):
            F.parse_formula(text, PARAMS)


@pytest.mark.parametrize("text,match", [
    ('"a" + "b"', "cannot take '\\+'"),
    ('Name = "b"', "cannot take '='"),
    ('Name > "b"', "cannot take '>'"),
    ('Name * 2', "cannot take '\\*'"),
    ("-Name", "cannot take '-'"),
    ('if(Flag, "A", 1)', "mixes text and number"),
    ('if(Flag, 2\', "A")', "mixes text and length"),
    ("round(Name)", "takes a measurable value, not spec.string"),
    ('not("x")', "takes Yes/No arguments"),
    ('if(Name, "A", "B")', "condition must be Yes/No"),
    ('"open', "no closing quote"),
    ('Width + "1"', "cannot take '\\+'"),
])
def test_no_operator_takes_text(text, match):
    with pytest.raises(F.FormulaError, match=match):
        F.parse_formula(text, PARAMS)


def test_integer_and_material_storage_stay_refused():
    params = dict(PARAMS, Poles=F.ParamRef(9, "autodesk.spec:spec.int64-1.0.0"),
                  Finish=F.ParamRef(10, "tekton.storage:material-browse"))
    for name in ("Poles", "Finish"):
        with pytest.raises(F.FormulaError, match="only measurable, Yes/No and text"):
            F.parse_formula(name, params)


@pytest.mark.parametrize("text", ['"Box"', 'if(Flag, "A", if(Other, "B", Name))', "Name",
                                  'if(Flag, "", "x y-z")'])
def test_a_text_formula_spells_back_to_the_same_tree(text):
    tree, _ = F.parse_formula(text, PARAMS)
    names = {r.param_id: n for n, r in PARAMS.items()}
    spelled = F.unparse_checked(tree, names, F.NameTable(PARAMS))
    assert spelled is not None
    assert F._shape(F.parse_formula(spelled, PARAMS)[0]) == F._shape(tree)


# --- the writer -------------------------------------------------------------------------

def _doc():
    from rvt.famgen import skeleton as fs
    doc = fs.new_family_document("electrical_equipment", "Text Formula Probe",
                                 part_type=fs.PART_TYPE["panelboard"], work_plane_based=True)
    p = {"flag": doc.add_family_parameter("Has Door", fs.SPEC_YESNO),
         "name": doc.add_family_parameter("Series", fs.SPEC_TEXT),
         "pick": doc.add_family_parameter("Enclosure", fs.SPEC_TEXT,
                                          formula='if(Has Door, "Door in door", Series)'),
         "const": doc.add_family_parameter("Kind", fs.SPEC_TEXT, formula='"Panel"')}
    doc.add_type("With Door", {"Has Door": True, "Series": "S1"})
    doc.add_type("Bare", {"Has Door": False, "Series": "S2"})
    doc.finalize()
    return doc, p


def _rows(fam):
    return {r["name"]: {e["m_paramId"]: e for e in r["params"]["m_params"]}
            for r in fam["m_pFamilyTypes"]["value"]["m_pairs"]}


@needs_schema
def test_a_text_formula_is_written_on_every_row_into_m_str():
    doc, p = _doc()
    rows = _rows(doc.self_family.obj)
    pick, const = p["pick"].elem_id, p["const"].elem_id
    assert rows["With Door"][pick]["m_str"] == "Door in door"
    assert rows["Bare"][pick]["m_str"] == "S2"
    assert rows["With Door"][const]["m_str"] == rows["Bare"][const]["m_str"] == "Panel"
    for row in rows.values():
        for pid in (pick, const):
            e = row[pid]
            assert (e["m_value"], e["m_int"], e["m_elemId"]) == (0.0, 0, -1)
            assert e["m_oExpression"] == rows["Bare"][pid]["m_oExpression"] is not None
    assert not any("NOT written" in n for n in doc.notes)


@needs_schema
def test_a_text_formula_on_a_number_or_a_material_is_refused_and_said():
    from rvt.famgen import skeleton as fs
    doc = fs.new_family_document("electrical_equipment", "Text Misfit Probe",
                                 part_type=fs.PART_TYPE["panelboard"], work_plane_based=True)
    n = doc.add_family_parameter("Gap", fs.SPEC_LENGTH, formula='"wide"')
    m = doc.add_family_parameter("Finish", fs.SPEC_MATERIAL, formula='"Steel"')
    doc.add_type("T", {})
    doc.finalize()
    rows = _rows(doc.self_family.obj)
    assert rows["T"][n.elem_id]["m_oExpression"] is None
    assert rows["T"][m.elem_id]["m_oExpression"] is None
    notes = "\n".join(doc.notes)
    assert "'Gap' NOT written" in notes and "'Finish' NOT written" in notes


@needs_schema
def test_an_emitted_rfa_reads_back_identically_and_validates(tmp_path):
    from rvt.famgen.famdoc_adoc import emit_family_rfa_v2
    from rvt.frontdoor.standalone import bundled_base_path
    from rvt.families import FamilyIndex
    from rvt.validate import Validator
    doc, p = _doc()
    out = str(tmp_path / "text_formula_probe.rfa")
    emit_family_rfa_v2(doc, out, donor=bundled_base_path(), write_reports=False)
    fi = FamilyIndex(out)
    fam = None
    for e, rec in fi.unit_records(0).get(102, {}).items():
        if fi.class_name(rec.class_id) == "Family":
            v = fi.decode(0, e, 102).value
            if v.get("m_surrogateId") == -1:
                fam = v
    back, built = _rows(fam), _rows(doc.self_family.obj)
    for tname in ("With Door", "Bare"):
        for key in ("pick", "const"):
            pid = p[key].elem_id
            for f in ("m_str", "m_value", "m_int", "m_elemId"):
                assert back[tname][pid][f] == built[tname][pid][f]
            assert F._shape(back[tname][pid]["m_oExpression"]) == \
                F._shape(built[tname][pid]["m_oExpression"])
            assert back[tname][pid]["m_oExpression"]["value"] == \
                built[tname][pid]["m_oExpression"]["value"]
    report = Validator(out, family=True).run()
    errors = report.errors() if callable(report.errors) else report.errors
    assert not errors, [e.message for e in errors][:5]


def test_a_name_that_starts_with_a_quote_is_read_as_text_and_refused():
    """A quote opens a text constant, so a caption beginning with one cannot be named
    in a formula (spelled-back formulas over such a name are reported unread) --
    refused with the reason, never misread as the parameter."""
    params = dict(PARAMS, **{'"Q" Name': F.ParamRef(7, F.SPEC_LENGTH)})
    with pytest.raises(F.FormulaError):
        F.parse_formula('"Q" Name + Width', params)
    assert not F.is_spellable('"Q" Name')

"""#875: a parameter profile carries each parameter's VALUE CONVENTION, and a generated
family is filled the way the library fills it -- structure, never one product's data.

* the extractor records, per family row, the current type's ``value`` (text / Yes-No /
  integer / measurable, internal units) and ``formula`` (Revit text over parameter
  NAMES, via ``rvt.famgen.formula.unparse``; ``formula_unread`` when it cannot spell it);
* ``param_profile`` takes a FORMULA when every carrying family uses it, a CONSTANT only
  when two or more families hold it and all agree; a text formula is written as the
  formula it is (#870: a string constant, a text parameter, an if() over texts);
  materials / family types never carry;
* the caller's own values win over a convention.

Synthetic only: made-up names / GUIDs / values (rule 6).
"""
from __future__ import annotations

import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import shared_params_from_rfa as SP  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import formula as FX  # noqa: E402
from rvt.famgen import param_profile as PP  # noqa: E402
from rvt.famgen import skeleton as SK  # noqa: E402

EQ = SK.OST_ELECTRICAL_EQUIPMENT
GRP = "autodesk.parameter.group:identityData-1.0.0"


def _g(n: int) -> str:
    return f"0000bbbb-cccc-4ddd-8eee-{n:012d}"


def _defn(name, def_class="ParamDefString", spec=None):
    return dict(name=name, def_class=def_class, spec=spec, datatype="TEXT", datatype_basis="class",
                data_category=None, description="", visible=True, user_modifiable=True,
                hide_when_no_value=False, used_by=1)


PARAMS = {
    _g(1): _defn("Zz Unit"),
    _g(2): _defn("Zz Half", "ParamDefValue", "autodesk.spec.aec:length-2.0.0"),
    _g(3): _defn("Zz Kind"),
    _g(4): _defn("Zz Rating"),
    _g(5): _defn("Zz Label"),
    _g(6): _defn("Zz Mixed", "ParamDefValue", "autodesk.spec.aec:length-1.0.0"),
    _g(7): _defn("Zz Finish", "ParamDefMaterialBrowse"),
    _g(8): _defn("Zz Flag", "ParamDefYesNo"),
}


def _row(n, value=None, formula=None, instance=False, unread=False):
    return {"guid": _g(n), "name": PARAMS[_g(n)]["name"], "instance": instance,
            "palette_group": GRP, "value": value, "formula": formula, "formula_unread": unread}


def _profile():
    a = [_row(1, "EA"), _row(2, 1.0, "Width / 2"), _row(3, "Box", '"Box"'), _row(4, "500 kVa"),
         _row(5, "x", "Zz Unit"), _row(6, 2.0), _row(7, 842), _row(8, 1)]
    b = [_row(1, "EA"), _row(2, 3.0, "Width / 2"), _row(3, "Box", '"Box"'), _row(4, "75 kVa"),
         _row(5, "y", "Zz Unit"), _row(6, 1.0, "Width"), _row(7, 842), _row(8, 1)]
    return {"schema": PP.PROFILE_SCHEMA, "conflicts": [], "variants": [], "warnings": [],
            "parameters": PARAMS,
            "families": {"Unit A": {"category": EQ, "params": a},
                         "Unit B": {"category": EQ, "params": b}}}


def _written(prod):
    fam = prod.doc.self_family.obj
    rows = {q["m_paramId"]: q for q in fam["m_familyParams"]["value"]["m_params"]}
    return {n: rows[pe.elem_id] for n, pe in prod.doc.params.items() if pe.elem_id in rows}


@pytest.fixture
def path(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(_profile()), encoding="utf-8")
    return str(p)


def test_conventions_are_selected_structure_not_product_data():
    sel, _ = PP.select(_profile(), category=EQ)
    conv = {p.name: p.convention for p in sel}
    assert conv["Zz Unit"] == {"value": "EA"}                 # two families agree
    assert conv["Zz Half"] == {"formula": "Width / 2"}        # every family's formula
    assert conv["Zz Kind"] == {"formula": '"Box"'}
    assert conv["Zz Rating"] is None                          # product data differs
    assert conv["Zz Mixed"] is None                           # one by formula, one not
    assert conv["Zz Finish"] is None                          # a material id never carries
    assert conv["Zz Flag"] == {"value": 1}
    # mirroring ONE family: its formulas are structure, its constants are its own data
    one, _ = PP.select(_profile(), family="Unit A")
    conv1 = {p.name: p.convention for p in one}
    assert conv1["Zz Half"] == {"formula": "Width / 2"} and conv1["Zz Unit"] is None
    assert conv1["Zz Rating"] is None


def test_an_unreadable_formula_is_never_a_convention():
    prof = _profile()
    prof["families"]["Unit B"]["params"][1]["formula_unread"] = True
    sel, _ = PP.select(prof, category=EQ)
    assert {p.name: p.convention for p in sel}["Zz Half"] is None


def test_a_generated_family_is_filled_by_the_conventions(path):
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path))
    rows = _written(prod)
    assert rows["Zz Unit"]["m_str"] == "EA"
    assert rows["Zz Kind"]["m_str"] == "Box"                  # '"Box"' written as the formula
    assert rows["Zz Kind"]["m_oExpression"]["ptr_class"] == "StringConstantExpression"
    assert rows["Zz Label"]["m_str"] == "EA"                  # 'Zz Unit': a text parameter
    assert rows["Zz Flag"]["m_int"] == 1
    half = rows["Zz Half"]
    assert half["m_oExpression"] is not None
    assert half["m_value"] == pytest.approx(rows["Width"]["m_value"] / 2)
    assert rows["Zz Rating"]["m_str"] == "" and rows["Zz Finish"]["m_elemId"] == -1
    notes = "\n".join(prod.doc.notes)
    assert "5 from the library's own conventions" in notes


def test_a_text_formula_over_parameters_is_written(path):
    prof = _profile()
    for f in prof["families"].values():
        f["params"][4]["formula"] = "Zz Unit"                 # the same in both: a convention
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(prof, fh)
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path))
    label = _written(prod)["Zz Label"]
    assert label["m_str"] == "EA" and label["m_oExpression"]["ptr_class"] == "ParameterExpression"
    assert (label["m_value"], label["m_int"], label["m_elemId"]) == (0.0, 0, -1)
    assert "'Zz Label' by formula" in "\n".join(prod.doc.notes)


def test_the_callers_values_win_over_a_convention(path):
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(
        path, values={"Zz Unit": "LOT", "Zz Half": {"formula": "Width"}}))
    rows = _written(prod)
    assert rows["Zz Unit"]["m_str"] == "LOT"
    assert rows["Zz Half"]["m_value"] == pytest.approx(rows["Width"]["m_value"])


def test_the_extractor_reads_values_and_formulas_back(path, tmp_path):
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path))
    out = str(tmp_path / "tx.rfa")
    prod.write(out, validate=False, provenance=False)
    got = {q["name"]: q for q in SP.read_family(out)["params"]}
    assert (got["Zz Unit"]["value"], got["Zz Unit"]["formula"]) == ("EA", None)
    assert got["Zz Half"]["formula"] == "Width / 2" and not got["Zz Half"]["formula_unread"]
    assert got["Zz Half"]["value"] == pytest.approx(prod.facts.get("width_in") / 12 / 2)
    assert got["Zz Flag"]["value"] == 1 and got["Zz Rating"]["value"] is None


@pytest.mark.parametrize("text", ["Width / 2", "if(Show A, Width + 1', Depth - 6\")",
                                  "and(Show A, not(Width > 3'))", "round(N * 2.5)",
                                  "-(Width) + (Depth)", "Width * 0.001"])
def test_unparse_is_the_inverse_of_parse(text):
    refs = FX.NameTable({"Width": FX.ParamRef(11, FX.SPEC_LENGTH), "Depth": FX.ParamRef(12, FX.SPEC_LENGTH),
                         "Show A": FX.ParamRef(13, FX.SPEC_YESNO), "N": FX.ParamRef(14, FX.SPEC_NUMBER)})
    names = {11: "Width", 12: "Depth", 13: "Show A", 14: "N"}
    tree, spec = FX.parse_formula(text, refs)
    back = FX.unparse(tree, names)
    tree2, spec2 = FX.parse_formula(back, refs)
    vals = {11: 2.0, 12: 1.5, 13: 1, 14: 3.0}
    assert spec2 == spec and FX.evaluate(tree2, vals) == FX.evaluate(tree, vals)


def test_unparse_refuses_what_it_cannot_spell():
    angle = {"ptr_class": "NumberConstantExpression",
             "value": {"m_value": 0.5, "m_specTypeId": {"m_typeId": "autodesk.spec.aec:angle-1.0.0"}}}
    assert FX.unparse(angle, {}) is None
    assert FX.unparse({"ptr_class": "ParameterExpression", "value": {"m_paramId": 99}}, {}) is None
    assert FX.unparse({"ptr_class": "FunctionExpression",
                       "value": {"m_function": 777, "m_subexpressions": []}}, {}) is None


# --- review round 1 (#889) ------------------------------------------------------------

def _p(pid):
    return {"ptr_class": "ParameterExpression", "value": {"m_paramId": pid}}


def _b(op, left, right):
    return {"ptr_class": "BinaryOperatorExpression",
            "value": {"m_binaryOperator": FX.BINARY_OP[op],
                      "m_pLeftSubexpression": left, "m_pRightSubexpression": right}}


def _neg(inner):
    return {"ptr_class": "UnaryOperatorExpression",
            "value": {"m_unaryOperator": FX.UNARY_NEG, "m_pSubexpression": inner}}


A, B, C = _p(11), _p(12), _p(14)


@pytest.mark.parametrize("tree,text", [
    (_b("*", _b("+", A, B), C), "(Width + Depth) * N"),
    (_b("-", A, _b("-", B, C)), "Width - (Depth - N)"),
    (_b("/", A, _b("*", B, C)), "Width / (Depth * N)"),
    (_b("-", _b("-", A, B), C), "Width - Depth - N"),
    (_neg(_b("+", A, B)), "-(Width + Depth)"),
    (_b(">", _b("+", A, B), C), "Width + Depth > N"),
])
def test_unparse_brackets_a_paren_free_tree_by_precedence(tree, text):
    """A Revit-born tree need not store ParenExpression nodes: precedence is spelled
    from the tree, and the text parses back to a tree of the same value."""
    names = {11: "Width", 12: "Depth", 14: "N"}
    refs = FX.NameTable({"Width": FX.ParamRef(11, FX.SPEC_NUMBER), "Depth": FX.ParamRef(12, FX.SPEC_NUMBER),
                         "N": FX.ParamRef(14, FX.SPEC_NUMBER)})
    got = FX.unparse(tree, names)
    assert got == text
    vals = {11: 2.0, 12: 1.5, 14: 3.0}
    assert FX.evaluate(FX.parse_formula(got, refs)[0], vals) == FX.evaluate(tree, vals)


def test_an_empty_string_constant_is_no_formula():
    empty = {"ptr_class": "StringConstantExpression", "value": {"m_value": ""}}
    assert FX.is_no_formula(empty) and FX.is_no_formula(None)
    got = SP._value_of({"m_value": 2.0, "m_oExpression": empty}, "ParamDefValue", {})
    assert got == {"value": 2.0, "formula": None, "formula_unread": False}
    # a profile written before this fix spells it '""': still read as no formula
    prof = _profile()
    for f in prof["families"].values():
        f["params"][5].update(value=2.0, formula='""')
    sel, _ = PP.select(prof, category=EQ)
    assert {p.name: p.convention for p in sel}["Zz Mixed"] == {"value": 2.0}


def test_a_malformed_row_costs_only_its_own_parameter(tmp_path):
    prof = _profile()
    prof["families"]["Unit A"]["params"][1]["formula"] = ["not", "text"]
    sel, _ = PP.select(prof, category=EQ)
    conv = {p.name: p.convention for p in sel}
    assert conv["Zz Half"] is None and conv["Zz Unit"] == {"value": "EA"}
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(prof), encoding="utf-8")
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(str(p)))
    assert _written(prod)["Zz Unit"]["m_str"] == "EA"
    assert not any("NOT applied" in n for n in prod.doc.notes)


def test_a_convention_formula_over_a_missing_parameter_is_said_and_left_blank(tmp_path):
    prof = _profile()
    for f in prof["families"].values():
        f["params"][1]["formula"] = "Zz Absent * 2"
    p = tmp_path / "absent.json"
    p.write_text(json.dumps(prof), encoding="utf-8")
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(str(p)))
    notes = "\n".join(prod.doc.notes)
    assert "formula of 'Zz Half' NOT written" in notes
    row = _written(prod)["Zz Half"]
    assert row["m_oExpression"] is None and row["m_value"] == 0.0


def test_every_convention_value_is_provenance_tagged_and_the_family_validates(path, tmp_path):
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(path, values={"Zz Rating": "45 kVa"}))
    prov = {n: pe.refs.get("provenance") for n, pe in prod.doc.params.items() if pe.refs.get("provenance")}
    assert prov["Zz Unit"] == {"tier": "library", "source": "the profile 'profile.json'", "by": "value"}
    assert prov["Zz Half"]["by"] == "formula" and prov["Zz Half"]["tier"] == "library"
    assert prov["Zz Rating"]["tier"] == "given"
    (line,) = [n for n in prod.doc.notes if n.startswith("provenance library (the profile 'profile.json'): ")]
    assert "'Zz Unit' by value" in line and "'Zz Half' by formula" in line and "Zz Rating" not in line
    rep = prod.write(str(tmp_path / "tx.rfa"))
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True

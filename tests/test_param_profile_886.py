"""#886 (the #889 review nits): a parameter profile's provenance stays truthful
when the build refuses something, and the formula reader never spells a formula
into a different tree.

* a library formula the finalize step refuses loses its ``library`` provenance tag,
  leaves the provenance line, and a note names it;
* a Yes/No convention of 0 (No) is reported as a convention, though it equals the
  blank row;
* ``formula.unparse_checked`` refuses a spelling that parses back to a different
  tree (a caption that holds two others and an operator);
* a tree deeper than the recursion limit gives None, never an exception.

Synthetic only: made-up names / GUIDs / values (rule 6).
"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import test_param_profile_875 as T  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import formula as FX  # noqa: E402
from rvt.famgen import param_profile as PP  # noqa: E402


def _build(tmp_path, prof):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(prof), encoding="utf-8")
    return F.make_transformer(kva=45, shared_params=PP.ProfileRequest(str(p)))


def test_a_refused_library_formula_carries_no_library_provenance(tmp_path):
    prof = T._profile()
    for f in prof["families"].values():
        f["params"][1]["formula"] = "Zz Absent * 2"
    prod = _build(tmp_path, prof)
    assert "provenance" not in prod.doc.params["Zz Half"].refs
    (line,) = [n for n in prod.doc.notes if n.startswith("provenance library (")]
    assert "Zz Half" not in line and "'Zz Unit' by value" in line
    assert any(n.startswith("library formulas not written") and "'Zz Half'" in n
               for n in prod.doc.notes)
    # a written formula keeps its tag
    ok = _build(tmp_path, T._profile())
    assert ok.doc.params["Zz Half"].refs["provenance"]["by"] == "formula"


def test_a_yes_no_convention_of_no_is_reported(tmp_path):
    prof = T._profile()
    for f in prof["families"].values():
        f["params"][7]["value"] = 0
    prod = _build(tmp_path, prof)
    assert prod.doc.params["Zz Flag"].refs["provenance"] == {
        "tier": "library", "source": "the profile 'profile.json'", "by": "value"}
    assert "4 from the library's own conventions" in "\n".join(prod.doc.notes)


def test_a_spelling_that_reads_back_as_another_parameter_is_refused():
    table = FX.NameTable({"A": FX.ParamRef(1, FX.SPEC_NUMBER), "B": FX.ParamRef(2, FX.SPEC_NUMBER),
                          "A - B": FX.ParamRef(3, FX.SPEC_NUMBER)})
    names = {1: "A", 2: "B", 3: "A - B"}
    tree, _ = FX.parse_formula("(A) - B", FX.NameTable({"A": FX.ParamRef(1, FX.SPEC_NUMBER),
                                                        "B": FX.ParamRef(2, FX.SPEC_NUMBER)}))
    assert FX.unparse(tree, names) == "(A) - B"              # the stored paren keeps it apart
    bare = {"ptr_class": "BinaryOperatorExpression",
            "value": {"m_binaryOperator": FX.BINARY_OP["-"],
                      "m_pLeftSubexpression": {"ptr_class": "ParameterExpression", "value": {"m_paramId": 1}},
                      "m_pRightSubexpression": {"ptr_class": "ParameterExpression", "value": {"m_paramId": 2}}}}
    assert FX.unparse(bare, names) == "A - B"                 # the plain spelling ...
    assert FX.unparse_checked(bare, names, table) is None     # ... reads back as 'A - B': refused
    assert FX.unparse_checked(tree, names, table) == "(A) - B"


def test_a_very_deep_tree_is_unread_not_a_crash():
    node = {"ptr_class": "ParameterExpression", "value": {"m_paramId": 1}}
    for _ in range(5000):
        node = {"ptr_class": "UnaryOperatorExpression",
                "value": {"m_unaryOperator": FX.UNARY_NEG, "m_pSubexpression": node}}
    assert FX.unparse(node, {1: "A"}) is None

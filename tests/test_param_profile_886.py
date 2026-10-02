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

import pytest  # noqa: E402

import test_param_profile_875 as T  # noqa: E402
from rvt.famgen import skeleton as SK  # noqa: E402
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
    assert "5 from the library's own conventions" in "\n".join(prod.doc.notes)


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


# --- the #896 review nits (#886 comment): provenance settled afresh on every finalize ---

def _absent(prof):
    for f in prof["families"].values():
        f["params"][1]["formula"] = "Zz Absent * 2"
    return prof


def test_a_formula_refused_once_and_written_later_is_tagged_again(tmp_path):
    # a finalize whose formula step fails writes no formula (skeleton.finalize's
    # fallback); a later one that writes it must tag it again -- settle each in turn
    prod = _build(tmp_path, T._profile())
    doc = prod.doc
    doc.finalize()
    half = doc.params["Zz Half"]
    PP.settle_formula_provenance(doc, set())                  # nothing written
    assert "provenance" not in half.refs
    assert any(n.startswith("library formulas not written") for n in doc.notes)
    every = {pe.elem_id for pe in doc.params.values() if pe.refs.get("formula_provenance")}
    PP.settle_formula_provenance(doc, every)                 # written this time
    assert half.refs["provenance"] == {
        "tier": "library", "source": "the profile 'profile.json'", "by": "formula"}
    (line,) = [n for n in doc.notes if n.startswith("provenance library (")]
    assert "'Zz Half' by formula" in line and "'Zz Unit' by value" in line
    assert not any(n.startswith("library formulas not written") for n in doc.notes)


def test_settling_twice_says_each_thing_once(tmp_path):
    prod = _build(tmp_path, _absent(T._profile()))
    prod.doc.finalize()
    prod.doc.finalize()
    assert sum(n.startswith("library formulas not written") for n in prod.doc.notes) == 1
    assert sum(n.startswith("provenance library (") for n in prod.doc.notes) == 1


def test_a_refused_given_formula_carries_no_given_provenance(tmp_path):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps(T._profile()), encoding="utf-8")
    prod = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(
        str(p), values={"Zz Half": {"formula": "Zz Absent * 3"}}))
    prod.doc.finalize()
    assert "provenance" not in prod.doc.params["Zz Half"].refs
    assert any(n.startswith("given formulas not written") and "'Zz Half'" in n
               for n in prod.doc.notes)
    ok = F.make_transformer(kva=45, shared_params=PP.ProfileRequest(
        str(p), values={"Zz Half": {"formula": "Width * 3"}}))
    ok.doc.finalize()
    assert ok.doc.params["Zz Half"].refs["provenance"] == {
        "tier": "given", "source": ok.doc.params["Zz Half"].refs["provenance"]["source"], "by": "formula"}


def test_a_formula_replaced_after_the_profile_loses_the_profile_claim(tmp_path):
    prod = _build(tmp_path, T._profile())
    doc = prod.doc
    doc.finalize()
    assert doc.params["Zz Half"].refs["provenance"]["tier"] == "library"
    doc.params["Zz Half"].refs["formula"] = "Width / 4"         # someone else's formula now
    doc.finalize()
    assert "provenance" not in doc.params["Zz Half"].refs
    (line,) = [n for n in doc.notes if n.startswith("provenance library (")]
    assert "Zz Half" not in line


def _num(v):
    return {"ptr_class": "NumberConstantExpression", "value": {"m_value": v}}


def _par(pid):
    return {"ptr_class": "ParameterExpression", "value": {"m_paramId": pid}}


def _bin(op, a, b):
    return {"ptr_class": "BinaryOperatorExpression",
            "value": {"m_binaryOperator": FX.BINARY_OP[op], "m_pLeftSubexpression": a,
                      "m_pRightSubexpression": b}}


@pytest.mark.parametrize("tree", [
    _bin("*", _par(1), _num(-2.0)),          # reads back as -(2.0)
    _bin("*", _par(1), _num(2)),             # an int constant
    _bin("+", _par(1), _num(-0.0)),          # -0.0
    _bin("*", _par("1"), _num(2.0)),         # a string parameter id
])
def test_trees_that_compute_alike_are_not_reported_unread(tree):
    table = FX.NameTable({"A": FX.ParamRef(1, FX.SPEC_NUMBER)})
    assert FX.unparse_checked(tree, {1: "A"}, table) is not None


def test_a_different_constant_is_still_a_different_tree():
    a, b = _bin("*", _par(1), _num(2.0)), _bin("*", _par(1), _num(-2.0))
    assert FX._shape(a) != FX._shape(b)


# --- the #961 review nits ---------------------------------------------------------------

def test_a_failed_formula_step_then_a_good_one_settles_through_finalize(tmp_path, monkeypatch):
    """The real path: finalize's formula step raises once (every formula left out, the
    fallback note), then a later finalize writes them -- the tags come back."""
    from rvt.famgen import skeleton as SKm
    prod = _build(tmp_path, T._profile())
    doc = prod.doc
    real = SKm.FamilyDoc._apply_formulas
    calls = {"n": 0}

    def flaky(self):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("probe")
        return real(self)
    monkeypatch.setattr(SKm.FamilyDoc, "_apply_formulas", flaky)
    doc.finalize()
    assert "provenance" not in doc.params["Zz Half"].refs
    assert any(n.startswith("library formulas not written") for n in doc.notes)
    doc.finalize()
    assert doc.params["Zz Half"].refs["provenance"]["by"] == "formula"
    assert not any(n.startswith("library formulas not written") for n in doc.notes)


def test_each_profile_line_lists_only_its_own_source(tmp_path):
    prod = _build(tmp_path, T._profile())
    doc = prod.doc
    doc.finalize()
    doc.params["Zz Unit"].refs["provenance"] = {"tier": "library", "source": "another", "by": "value"}
    doc.notes.append("provenance library (another): 'Zz Unit' by value")
    every = {pe.elem_id for pe in doc.params.values() if pe.refs.get("formula_provenance")}
    PP.settle_formula_provenance(doc, every)
    lines = [n for n in doc.notes if n.startswith("provenance library (")]
    mine = next(n for n in lines if "profile.json" in n)
    assert "Zz Unit" not in mine and "'Zz Half' by formula" in mine
    assert "provenance library (another): 'Zz Unit' by value" in lines

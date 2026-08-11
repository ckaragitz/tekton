"""The corpus oracle (#689): what born family documents always do."""
import os
import pytest
from rvt.famgen import conformance as CF

RFT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "samples", "rft")


class _El:
    def __init__(self, eid, cls, obj):
        self.elem_id, self.class_name, self.obj = eid, cls, obj


class _Doc:
    def __init__(self, els):
        self.elements = els


def _oracle(rows):
    o = CF.Oracle()
    for cls, obj in rows:
        o.observe(cls, obj)
    return o


def test_always_empty_is_derived():
    o = _oracle([("X", {"f": []}) for _ in range(6)])
    assert o.invariants()["X"]["f"]["invariant"] == "ALWAYS_EMPTY"


def test_always_present_is_derived():
    o = _oracle([("X", {"f": [1]}) for _ in range(6)])
    assert o.invariants()["X"]["f"]["invariant"] == "ALWAYS_PRESENT"


def test_constant_is_derived_for_scalars():
    o = _oracle([("X", {"f": 7}) for _ in range(6)])
    r = o.invariants()["X"]["f"]
    assert r["invariant"] == "CONSTANT" and r["value"] == "int:7"


def test_a_field_missing_on_some_specimens_yields_no_invariant():
    o = _oracle([("X", {"f": [1]}) for _ in range(5)] + [("X", {})])
    assert "f" not in o.invariants().get("X", {})


def test_too_few_specimens_yields_no_invariant():
    o = _oracle([("X", {"f": [1]}) for _ in range(3)])
    assert o.invariants(min_specimens=5) == {}


def test_missing_where_born_files_always_fill_is_flagged():
    inv = _oracle([("X", {"f": [1]}) for _ in range(9)]).invariants()
    f = CF.check_doc(_Doc([_El(1, "X", {"f": []})]), inv)
    assert len(f) == 1 and f[0]["severity"] == "question"
    assert f[0]["specimens"] == 9


def test_filled_where_born_files_are_always_empty_is_noted():
    inv = _oracle([("X", {"f": []}) for _ in range(9)]).invariants()
    f = CF.check_doc(_Doc([_El(1, "X", {"f": [1]})]), inv)
    assert len(f) == 1 and f[0]["severity"] == "note"


def test_a_conforming_document_is_silent():
    inv = _oracle([("X", {"f": [1]}) for _ in range(9)]).invariants()
    assert CF.check_doc(_Doc([_El(1, "X", {"f": [2]})]), inv) == []


def test_findings_rank_by_specimen_count():
    o = _oracle([("X", {"a": [1], "b": [1]}) for _ in range(9)])
    inv = o.invariants()
    inv["X"]["a"]["specimens"] = 400
    f = CF.check_doc(_Doc([_El(1, "X", {"a": [], "b": []})]), inv)
    assert [x["field"] for x in f] == ["a", "b"]


def test_only_scalar_laws_are_quoted_never_content():
    # a string value must never become a CONSTANT the report quotes
    o = _oracle([("X", {"f": "some authored text"}) for _ in range(9)])
    r = o.invariants()["X"]["f"]
    assert r["invariant"] == "ALWAYS_PRESENT"
    assert "value" not in r


def test_summarise_collapses_per_field():
    inv = _oracle([("X", {"f": [1]}) for _ in range(9)]).invariants()
    doc = _Doc([_El(i, "X", {"f": []}) for i in range(4)])
    s = CF.summarise(CF.check_doc(doc, inv))
    assert "1 divergent field(s) over 4 element(s)" in s


@pytest.mark.skipif(not os.path.isdir(RFT), reason="templates not present")
def test_the_oracle_is_not_inert_on_the_real_corpus():
    o = CF.mine(RFT, limit=8)
    inv = o.invariants()
    assert inv, "no invariants mined from the corpus"
    # it must check real fields on a real document, not silently cover nothing
    covered = sum(len(r) for r in inv.values())
    assert covered > 50, covered

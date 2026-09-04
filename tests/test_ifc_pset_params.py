"""#769 -- an IFC's own property sets reach the family as real parameters."""
import os
import pytest
from rvt.ifc import pset_params as PP

IFC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "out", "xfmr", "padmountedtransformer.ifc")


def test_clean_name_is_palette_safe():
    assert PP._clean("Top_Clearance") == "Top Clearance"
    assert PP._clean("  a   b  ") == "a b"
    assert PP._clean("") == "Property"
    assert len(PP._clean("x" * 200)) <= 60


def test_eid_handles_a_method_not_an_attribute():
    class _E:
        def id(self):
            return 7
    assert PP._eid(_E()) == 7

    class _F:
        id = 9
    assert PP._eid(_F()) == 9
    assert PP._eid(object()) == -1


def test_type_name_handles_both_reader_shapes():
    class _Callable:
        def is_a(self):
            return "IfcLengthMeasure"

    class _Attr:
        is_a = "IfcReal"
    assert PP._type_name(_Callable()) == "IfcLengthMeasure"
    assert PP._type_name(_Attr()) == "IfcReal"
    assert PP._type_name(object()) == ""


def test_an_unreadable_file_yields_no_params_and_says_so():
    # hard rule 1: never block delivery on this
    c = PP.collect("/definitely/not/a/file.ifc")
    assert c["params"] == {}
    assert c["notes"] and "not read" in c["notes"][0]


def test_reserved_names_are_never_substituted_for_geometry_dims():
    assert "Width" in PP.RESERVED_NAMES
    assert "Height" in PP.RESERVED_NAMES
    assert "Depth" in PP.RESERVED_NAMES


def test_summarise_is_quotable_and_names_skips():
    c = {"params": {"TopClearance": ("length", 3.0)},
         "skipped": [{"name": "Width", "pset": "P", "why": "reserved"}],
         "notes": []}
    lines = PP.summarise(c)
    assert any("carried through as 1 family parameter" in t for t in lines)
    assert any("was NOT carried" in t for t in lines)


def test_summarise_of_nothing_is_silent():
    assert PP.summarise({"params": {}, "skipped": [], "notes": []}) == []


@pytest.mark.skipif(not os.path.exists(IFC), reason="sample IFC not present")
def test_the_transformer_psets_are_carried_with_unit_conversion():
    c = PP.collect(IFC)
    p = c["params"]
    assert len(p) == 10, sorted(p)
    # metres -> feet, checked against the file's own _in companions
    assert p["TopClearance"][0] == "length"
    assert abs(p["TopClearance"][1] * 12.0 - 36.0) < 1e-6
    assert abs(p["FrontClearance"][1] * 12.0 - 120.0) < 1e-6
    assert abs(p["BodyWidth"][1] * 12.0 - 62.0) < 1e-6
    assert abs(p["PadDepth"][1] * 12.0 - 72.0) < 1e-6
    # a plain IfcReal stays a number, NOT scaled as a length
    assert p["TopClearance in"] == ("number", 36.0)
    assert c["sources"]["TopClearance"]["tier"] == "given"

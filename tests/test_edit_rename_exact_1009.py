"""#1009 -- a rename names its type EXACTLY, and a caption that itself
contains "of type" is a parameter, not a qualifier.

PR #1007's fifth review: ``_op_rename_type`` still fell back to a substring,
so with types T10 / T2 ``rename type T1 to Z`` renamed T10 -- the B1
mis-target #1007 retired for sets.  And #1007's qualifier resolution read the
"of type" in a caption such as ``Size of Type`` as a type qualifier, refusing
``set Size of Type to 5`` that main parsed.

No desktop verdict is claimed (hard rule 4).

Run: .venv/bin/python -m pytest tests/test_edit_rename_exact_1009.py -q
"""
from __future__ import annotations

import pytest

from rvt.convert import modify_family as MF


class _Inv:
    params = [{"caption": c} for c in ("Finish", "Size of Type")]
    type_names = ["T10", "T2"]
    notes: list = []


@pytest.mark.parametrize("old", ["T1", "T", "1", "0"])
def test_a_partial_old_name_is_refused(old):
    with pytest.raises(MF.FamilyEditError, match="not exactly one of this family's types"):
        MF._op_rename_type(_Inv, old, "Z")


@pytest.mark.parametrize("old, idx", [("T10", 0), ("t10", 0), ('"T2"', 1), (" T2 ", 1)])
def test_an_exact_old_name_renames_that_type(old, idx):
    op = MF._op_rename_type(_Inv, old, "Z")
    assert (op["type_index"], op["old"], op["name"]) == (idx, _Inv.type_names[idx], "Z")


def test_a_one_type_family_may_omit_the_old_name():
    class _One(_Inv):
        type_names = ["Only"]
    assert MF._op_rename_type(_One, None, "Z")["old"] == "Only"


def test_parse_refuses_a_partial_rename():
    with pytest.raises(MF.FamilyEditError, match="not exactly one"):
        MF.parse_family_edit("rename type T1 to Z", _Inv)


@pytest.mark.parametrize("clause, want", [
    ("set Size of Type to 5", ("Size of Type", "5", None)),
    ("set Size of Type = 5", ("Size of Type", "5", None)),
    ("set Size of Type 5", ("Size of Type", "5", None)),
    ("set Size of Type of type T2 = 5", ("Size of Type", "5", "T2")),
])
def test_a_caption_containing_of_type_is_a_parameter(clause, want):
    m = MF._match_set(_Inv, clause)
    assert (m.group("cap"), m.group("val"),
            m.group("typeq") or m.group("typeq2") or m.group("type")) == want


def test_a_wrong_type_after_such_a_caption_is_still_refused():
    with pytest.raises(MF.FamilyEditError, match="'of type T1' is not a type"):
        MF._match_set(_Inv, "set Size of Type of type T1 = 5")

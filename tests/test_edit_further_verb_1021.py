"""#1021 -- a quoted edit value whose second part merely STARTS with a verb
is a value, not a further edit.

#1018/#1020 refused any quoted span that ran across a separator followed by
one of the lane's verbs: ``rename LP-1 to "Main; Mark B"`` and ``set Note =
"Hex bolt, set screw included"`` were refused.  The refusal now fires only
where the fragment the old quote-blind split produced after that separator
is one that lane would actually have APPLIED (its grammar reads it; in the
family lane, naming a real parameter): ``'heavy; set Mark = workers'`` stays
refused.  And the family lane's "cannot read" refusal is narrowed to match
the .rvt lane: a kept-whole clause no part of which ever read stays
unparsed, the other edits apply.

Run: .venv/bin/python -m pytest tests/test_edit_further_verb_1021.py -q
"""
from __future__ import annotations

import pytest

from rvt.convert import modify_family as MF
from rvt.frontdoor import edit as E


def _inv():
    ps = [{"caption": c, "param_id": 1000 + i, "def_class": "ParamDefString",
           "spec": "autodesk.spec:string-2.0.0", "carrier": "m_str", "current": "", "formula": False}
          for i, c in enumerate(("Width", "Note", "Mark", "Finish", "Length"))]
    return MF.FamilyInventory(path="x.rfa", family_id=1, family_name="F", type_names=["T1"], params=ps)


def _family(text):
    r = MF.parse_family_edit(text, _inv())
    return [(o["caption"], o["value"]) for o in r["ops"]], r.get("unparsed")


@pytest.mark.parametrize("text, want", [
    ('set Note = "Hex bolt, set screw included"', [("Note", "Hex bolt, set screw included")]),
    ('set Note = "ready; set up later"', [("Note", "ready; set up later")]),
    ('set Note = "a; rename it"', [("Note", "a; rename it")]),
    ('set Note = "a then set aside"; set Mark = 2', [("Note", "a then set aside"), ("Mark", "2")]),
])
def test_family_a_verb_word_in_a_quoted_value_is_stored(text, want):
    assert _family(text)[0] == want


@pytest.mark.parametrize("text", [
    "set Note = 'heavy; set Mark = workers'",
    'set Note = "x; set Mark"',
    "set Note = 'a, rename family to B'",
])
def test_family_a_fragment_that_would_have_applied_is_still_refused(text):
    with pytest.raises(MF.FamilyEditError, match="runs across a further edit"):
        MF.parse_family_edit(text, _inv())


def test_family_a_kept_whole_clause_no_part_of_which_read_stays_unparsed():
    ops, unparsed = _family('also set Note = "a; b"; set Mark = 2')
    assert ops == [("Mark", "2")] and unparsed == ['also set Note = "a; b"']


def test_family_a_kept_whole_clause_whose_part_read_is_still_refused():
    with pytest.raises(MF.FamilyEditError, match="cannot read"):
        MF.parse_family_edit('set Note = "p\nq"\nset Width = 2', _inv())


@pytest.mark.parametrize("text, want", [
    ('rename 742670 to "Main; Mark B"', [{"op": "rename", "id": 742670, "name": "Main; Mark B"}]),
    ('mark 742670 as "Existing; move to upper level"',
     [{"op": "set-mark", "id": 742670, "mark": "Existing; move to upper level"}]),
    ('rename 742670 to "Spare; to be set"', [{"op": "rename", "id": 742670, "name": "Spare; to be set"}]),
])
def test_rvt_a_verb_word_in_a_quoted_value_is_stored(text, want):
    assert E.parse_edit_spec(text).ops == want


@pytest.mark.parametrize("text", [
    "mark 742670 as 'heavy; delete 1466502 workers'",
    'rename 742670 to "x; move 1466502 by 1,0,0 ft; spare"',
    # has a delete command's shape; the old split refused the whole edit on it too
    'rename 742670 to "Spare then delete later"',
])
def test_rvt_a_fragment_that_would_have_applied_is_still_refused(text):
    with pytest.raises(E.EditParseError, match="runs across a further edit"):
        E.parse_edit_spec(text)

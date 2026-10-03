"""#1019 -- an .rvt edit's quoted mark / name / value with a ';', newline or
'then' inside is one clause, not two (the family lane's #1017 fix, shared
through rvt._quoted).  Before, ``mark 742670 as "A; B"`` wrote the mark
``A`` and left ``B"`` unparsed.

Run: .venv/bin/python -m pytest tests/test_rvt_edit_quoted_split_1019.py -q
"""
from __future__ import annotations

import pytest

from rvt.frontdoor import edit as E


def _ops(text):
    return E.parse_edit_spec(text).ops


@pytest.mark.parametrize("text, want", [
    ('mark 742670 as "A; B"', [{"op": "set-mark", "id": 742670, "mark": "A; B"}]),
    ('set mark of 742670 to "A then B"', [{"op": "set-mark", "id": 742670, "mark": "A then B"}]),
    ('rename 742670 to "Panel; spare"; delete 1466502',
     [{"op": "rename", "id": 742670, "name": "Panel; spare"},
      {"op": "delete", "id": 1466502, "cascade": False}]),
    ("rename 742670 to 'LP and then spare' then delete 1466502",
     [{"op": "rename", "id": 742670, "name": "LP and then spare"},
      {"op": "delete", "id": 1466502, "cascade": False}]),
    ('set parameter 5 of 742670 to "a; b"', [{"op": "set-param", "id": 742670, "param_id": 5,
                                              "value": "a; b"}]),
    # unchanged: apostrophes, unbalanced quotes, unit marks split as before
    ("set parameter 5 of 742670 to Bob's; set parameter 6 of 742670 to Ann's",
     [{"op": "set-param", "id": 742670, "param_id": 5, "value": "Bob's"},
      {"op": "set-param", "id": 742670, "param_id": 6, "value": "Ann's"}]),
    ('rename 742670 to "x then move 1466502 by 1,0,0"',          # 0" is an inch mark: as before
     [{"op": "rename", "id": 742670, "name": "x"}]),
    ('mark 742670 as "A\nB"; delete 1466502',                   # this grammar reads the newline
     [{"op": "set-mark", "id": 742670, "mark": "A\nB"}, {"op": "delete", "id": 1466502, "cascade": False}]),
    ("rename 742670 to '90s; delete 1466502",
     [{"op": "rename", "id": 742670, "name": "90s"}, {"op": "delete", "id": 1466502, "cascade": False}]),
])
def test_quoted_separators(text, want):
    assert _ops(text) == want


@pytest.mark.parametrize("text", [
    "mark 742670 as 'heavy; delete 1466502 workers'",
    'rename 742670 to "x then move 1466502 by 1,0,0 ft then spare"',
])
def test_a_quote_running_across_a_further_edit_is_refused(text):
    with pytest.raises(E.EditParseError, match="runs across a further edit"):
        E.parse_edit_spec(text)


@pytest.mark.parametrize("text", [
    # the old split applied a cut part ("A", "p"): refused, never dropped silently
    "mark 742670 as 'A; \"B\"x'; delete 1466502",
    "set parameter 5 of 742670 to 'p\nq' it's",
])
def test_a_kept_whole_clause_the_grammar_cannot_read_is_refused(text):
    with pytest.raises(E.EditParseError, match="cannot read"):
        E.parse_edit_spec(text)


def test_a_kept_whole_clause_no_part_of_which_ever_read_stays_unparsed():
    # the old split read no part of it either: the other edits apply, as before
    spec = E.parse_edit_spec("rename 742670 to 'it\"s; odd'; delete 1466502")
    assert spec.ops == [{"op": "delete", "id": 1466502, "cascade": False}]
    assert spec.unparsed == ["rename 742670 to 'it\"s; odd'"]


def test_plain_multi_clause_edits_are_unchanged():
    ops = _ops("delete 1466502 with cascade; move 742670 to 3, 4, 0 ft then rotate 742670 to 90 deg")
    assert [o["op"] for o in ops] == ["delete", "move", "move"]

"""#1003 -- the family-edit refusal hint keeps an ``of type T`` qualifier as
the TYPE, in its parsed position, never folded into the value.

PR #1001's review: for ``set Finish color of type T1 to black`` the hint
suggested ``set Finish = color of type T1 to black``, which re-parses with no
type, so following it would write the whole string to the default type.  The
hint is message text only; these cases pin that the recovery it names
re-parses to the intended caption, value and type.

Run: .venv/bin/python -m pytest tests/test_edit_hint_1003.py -q
"""
from __future__ import annotations

import pytest

from rvt.convert import modify_family as MF


class _Inv:
    params = [{"caption": c} for c in ("Material", "Finish")]
    type_names = ["T1", "T 1"]          # the types the cases name (exact match since #1007)


def _type(m):
    return m.group("typeq") or m.group("typeq2") or m.group("type")


@pytest.mark.parametrize("caption, clause, example, val, typ", [
    ("Finish color", "set Finish color of type T1 to black",
     'set Finish of type "T1" = color to black', "color to black", "T1"),   # a known type, quoted in (#1007)
    ("Finish color", 'set Finish color of type "T 1" to black',
     'set Finish of type "T 1" = color to black', "color to black", "T 1"),
    ("Finish color", "set Finish color of type 'T 1' = black",
     "set Finish of type 'T 1' = color = black", "color = black", "T 1"),
    ("Finish color", "set Finish color to black",
     "set Finish = color to black", "color to black", None),
])
def test_the_hinted_recovery_reparses_to_caption_value_and_type(caption, clause, example,
                                                                val, typ):
    hint = MF._value_hint(_Inv, caption, clause)
    assert hint.endswith(example)
    m = MF._match_set(_Inv, example)
    assert (m.group("cap"), m.group("val"), _type(m)) == ("Finish", val, typ)

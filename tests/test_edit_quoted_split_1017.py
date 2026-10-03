"""#1017 -- a family-edit value quoted with a ';' / ',' / 'then' / newline
inside is one clause, not two.  #1008 made a quoted value the way to store
text exactly as typed; a separator inside the quotes cut it ('"a').

A quote pairs only when it opens at a word start onto a non-space, the next
copy of it closes at a word end, and that close is not a unit mark (3' / 5").
Anything else is literal, so an apostrophe ('90s, Bob's), a feet/inch mark,
a glued quote or an unbalanced quote never pairs with a quote in a LATER
clause and swallows it (PR #1018 review) -- those split exactly as on main.
A quoted value that still runs across what reads as a further set/rename
clause is refused: that shape cannot be told from a stray quote pairing with
the next edit's, and a refusal is recoverable where a swallowed edit is not.

Run: .venv/bin/python -m pytest tests/test_edit_quoted_split_1017.py -q
"""
from __future__ import annotations

import pytest

from conftest import HAVE_SCHEMA, context_constants, ladder_constants
from rvt.convert import modify_family as MF

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


@pytest.mark.parametrize("text, want", [
    ('set Note = "a; b"', ['set Note = "a; b"']),
    ("set Note = 'x, set Width = 2'", ["set Note = 'x", "set Width = 2'"]),   # 2' = feet: as main
    ('set Note = "x then y" then set Width = 2', ['set Note = "x then y"', "set Width = 2"]),
    ('set Note = "p\nq"\nset Width = 2', ['set Note = "p\nq"', "set Width = 2"]),
    ('set Note: "a; b"', ['set Note: "a; b"']),
    ('set Note to "a; b"; set Width = 2', ['set Note to "a; b"', "set Width = 2"]),
    ('set Note = "a"; set Width = "b; c"', ['set Note = "a"', 'set Width = "b; c"']),
    # unchanged: apostrophes, unbalanced quotes, quotes glued inside a word
    ("set Mark = Bob's; set Note = Ann's", ["set Mark = Bob's", "set Note = Ann's"]),
    ('set Note = "a; b', ['set Note = "a', "b"]),
    ('set Note = 5"; set Width = 2', ['set Note = 5"', "set Width = 2"]),
    ("set Note = a; set Width = 2, set Mark = 3", ["set Note = a", "set Width = 2", "set Mark = 3"]),
    ("set Note = a then set Width = 2", ["set Note = a", "set Width = 2"]),
    # PR #1018 review: a literal quote never pairs with a later clause's quote
    ("set Finish = '90s style; set Length = 3'", ["set Finish = '90s style", "set Length = 3'"]),
    ('set Finish = "a; b; set Length = 5"', ['set Finish = "a', "b", 'set Length = 5"']),
    ('set Finish = 3 "; set Length = 5"', ['set Finish = 3 "', 'set Length = 5"']),
    ('set Finish = "hot dip; set Length = "X"', ['set Finish = "hot dip', 'set Length = "X"']),
    ("set Note = 'tis; set Mark = 'x'", ["set Note = 'tis", "set Mark = 'x'"]),
    ('set Note = "A"B; set Mark = "x"', ['set Note = "A"B', 'set Mark = "x"']),
    ("set Note = 10 '; set Mark = 'x'", ["set Note = 10 '", "set Mark = 'x'"]),
    ("set Note = 'rock 'n' roll; set Mark = 2'", ["set Note = 'rock 'n' roll", "set Mark = 2'"]),
])
def test_split(text, want):
    assert MF._split_clauses(text) == want


@pytest.mark.parametrize("text", [
    "set Note = 'heavy; set Mark = workers'",
    'set Note = "x, set Mark = A"',
    'set Note = "a then rename type T1 to Big"',
    "set Note = 'a\nset Mark = b'",
])
def test_a_quoted_value_running_across_a_further_edit_is_refused(text):
    with pytest.raises(MF.FamilyEditError, match="runs across a further edit"):
        MF._split_clauses(text)


def _inv():
    ps = [{"caption": c, "param_id": 1000 + i, "def_class": "ParamDefString",
           "spec": "autodesk.spec:string-2.0.0", "carrier": "m_str", "current": "", "formula": False}
          for i, c in enumerate(("Width", "Note", "Mark"))]
    return MF.FamilyInventory(path="x.rfa", family_id=1, family_name="F", type_names=["T1"], params=ps)


@pytest.mark.parametrize("text", [
    # PR #1018 second review: kept whole, then unreadable -> refused, never dropped
    'set Note = "p\nq"\nset Width = 2',
    'set Note = "p\nq" then set Mark = 2',
    'set Mark = 2; set Note = "line one\r\nline two"',
    "rename the type to 'Run 2\"; long'; set Mark = 2",
])
def test_a_kept_whole_clause_the_grammar_cannot_read_is_refused(text):
    with pytest.raises(MF.FamilyEditError, match="cannot read"):
        MF.parse_family_edit(text, _inv())


def test_a_kept_whole_clause_that_reads_gives_every_op():
    ops = MF.parse_family_edit('set Note = "a; b then c"; set Mark = 2', _inv())["ops"]
    assert [(o["caption"], o["value"]) for o in ops] == [("Note", "a; b then c"), ("Mark", "2")]


@pytest.fixture(scope="module")
def conduit():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    import os
    import shutil
    import tempfile
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t1017_")
    try:
        p = os.path.join(d, "c.rfa")
        F.make_archetype(product="conduit").write(p, validate=False, provenance=False)
        yield p
    finally:
        shutil.rmtree(d, True)


def test_a_quoted_separator_reads_back_whole_on_a_generated_family(conduit, tmp_path):
    rec = MF.modify_family(conduit, 'set Finish = "hot dip; galv then coat"', str(tmp_path))
    assert MF.inventory_family(rec["files"]["rfa"]).param_by_caption("Finish")["current"] \
        == "hot dip; galv then coat"


def test_a_leading_apostrophe_never_swallows_the_next_edit(conduit, tmp_path):
    # PR #1018 review row 1: main applied both edits; the first head dropped Length
    ops = MF.parse_family_edit("set Finish = '90s style; set Length = 3'",
                               MF.inventory_family(conduit))["ops"]
    assert len(ops) == 2

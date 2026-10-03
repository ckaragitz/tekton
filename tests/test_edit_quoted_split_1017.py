"""#1017 -- a family-edit value quoted with a ';' / ',' / 'then' / newline
inside is one clause, not two.  #1008 made a quoted value the way to store
text exactly as typed; a separator inside the quotes cut it ('"a').

A quote counts only when it opens at a word start and closes at a word end,
so an apostrophe ("Bob's") or an unbalanced quote never hides a separator --
those split exactly as before.

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
    ("set Note = 'x, set Width = 2'", ["set Note = 'x, set Width = 2'"]),
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
])
def test_split(text, want):
    assert MF._split_clauses(text) == want


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
    rec = MF.modify_family(conduit, 'set Finish = "hot dip; galv, set Mark"', str(tmp_path))
    assert MF.inventory_family(rec["files"]["rfa"]).param_by_caption("Finish")["current"] \
        == "hot dip; galv, set Mark"

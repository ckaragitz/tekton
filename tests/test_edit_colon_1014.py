"""#1014 -- a colon after a caption is a delimiter; punctuation glued to a
caption is refused; "<caption> to <longer caption, mistyped> = v" is refused.

All three wrote text the user did not mean as a value (": 1", "^ 1", "-1",
"Walls = 5") or wrote it into a shorter parameter.  Principle (#994): a
refusal is recoverable, a mis-targeted write or a rewritten value is not.

Run: .venv/bin/python -m pytest tests/test_edit_colon_1014.py -q
"""
from __future__ import annotations

import re

import pytest

from conftest import HAVE_SCHEMA, context_constants, ladder_constants
from rvt.convert import modify_family as MF

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


class _I:
    params = [{"caption": c} for c in ("Tray Type", "Finish", "Width", "Mark", "Mark Note", "Note",
                                       "Ratio", "Height", "Height tolerance",
                                       "Size of Type", "Size of Type A", "Size",
                                       "Distance", "Distance to Wall")]
    type_names = ["T1", "Big One"]


def _read(clause):
    m = MF._match_set(_I, clause)
    return m.group("cap"), m.group("val"), m.group("typeq") or m.group("typeq2") or m.group("type")


@pytest.mark.parametrize("clause, want", [
    ("set Tray Type: 1", ("Tray Type", "1", None)),
    ("set Tray  Type: 1", ("Tray Type", "1", None)),
    ("set Tray Type:1", ("Tray Type", "1", None)),
    ("set Tray Type of type T1: 1", ("Tray Type", "1", "T1")),
    ("set Finish = 10:30", ("Finish", "10:30", None)),          # a colon INSIDE a value stays
    ("set Finish to a:b", ("Finish", "a:b", None)),
    ("set Finish to a=b", ("Finish", "a=b", None)),             # no longer 'Finish to ...' caption
    ("set Mark to-do", ("Mark", "to-do", None)),
    ("set Distance to Wall-mounted box", ("Distance", "Wall-mounted box", None)),
    ("set Distance to Wall: 3", ("Distance to Wall", "3", None)),
    ("set Width=3", ("Width", "3", None)),
    # PR #1016 review: only a colon GLUED to the caption is a delimiter -- after
    # a space it is the value's own
    ("set Note :)", ("Note", ":)", None)),
    ("set Note :-)", ("Note", ":-)", None)),
    ("set Ratio :1", ("Ratio", ":1", None)),
    ("set Width of type T1 :)", ("Width", ":)", "T1")),
    ("set Width of type T1: 3", ("Width", "3", "T1")),
    # 'Height tolerance' is not a 'Height to ...' caption: whole words only
    ("set Height to a=b", ("Height", "a=b", None)),
])
def test_read(clause, want):
    assert _read(clause) == want


@pytest.mark.parametrize("clause, match", [
    ("set Mark^ 1", "runs straight into '^'"),
    ("set Mark Note-1", "runs straight into '-'"),
    ("set Mark-1", "runs straight into '-'"),
    ("set Size of Type A- 1", "runs straight into '-'"),
    ("set Distance to Walls = 5", "no parameter 'Distance to Walls'"),
    ("set Distance to W\u00e1ll = 5", "no parameter 'Distance to W\u00e1ll'"),
])
def test_refused(clause, match):
    with pytest.raises(MF.FamilyEditError, match=re.escape(match)):
        MF._match_set(_I, clause)


@pytest.fixture(scope="module")
def conduit():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    import os
    import shutil
    import tempfile
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t1014_")
    try:
        p = os.path.join(d, "c.rfa")
        F.make_archetype(product="conduit").write(p, validate=False, provenance=False)
        yield p
    finally:
        shutil.rmtree(d, True)


def test_a_colon_value_reads_back_on_a_generated_family(conduit, tmp_path):
    rec = MF.modify_family(conduit, "set Finish: hot dip", str(tmp_path))
    assert MF.inventory_family(rec["files"]["rfa"]).param_by_caption("Finish")["current"] \
        == "hot dip"

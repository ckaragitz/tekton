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


class _TC:
    """Type names that contain colons (PR #1016 second review)."""
    params = [{"caption": c} for c in ("Width", "Note", "Note: Install", "Note:")]
    type_names = ["A", "A:B", "A: Heavy", "T1", "T1:B"]


@pytest.mark.parametrize("clause, want", [
    ("set Width of type A:B = 3", ("Width", "3", "A:B")),
    ("set Width of type A:B to 3", ("Width", "3", "A:B")),
    ("set Width of type A:B 3", ("Width", "3", "A:B")),
    ("set Width of type A: Heavy = 3", ("Width", "3", "A: Heavy")),
    ("set Width of type T1:B = 3", ("Width", "3", "T1:B")),
    ("set Note: Install = x", ("Note: Install", "x", None)),
    ("set Note: x", ("Note:", "x", None)),
    ("set Note x", ("Note", "x", None)),
])
def test_type_names_with_colons_read_whole(clause, want):
    m = MF._match_set(_TC, clause)
    assert (m.group("cap"), m.group("val"),
            m.group("typeq") or m.group("typeq2") or m.group("type")) == want


@pytest.mark.parametrize("clause", [
    "set Width of type T1:C = 3",        # never T1 = "C = 3"
    "set Width of type T1::B = 3",
    "set Width of type A::B = 3",
    "set Width of type A::B 3",
    "set Width of type T1: 3",           # a colon after a TYPE is not a delimiter
    "set Note:",                         # never a blank write
    "set Note: ",
])
def test_type_and_caption_colon_misreads_are_refused(clause):
    with pytest.raises(MF.FamilyEditError):
        MF._match_set(_TC, clause)


@pytest.mark.parametrize("caps, clause, want", [
    # PR #1016 third review: a LONGER caption the user typed exactly, with the
    # value glued on, is never rewritten into the shorter caption's '=' reading
    (("Mark", "Mark: Ref"), 'set Mark: Ref"x"', ("Mark: Ref", '"x"')),
    (("Note", "Note: A"), 'set Note: A"x"', ("Note: A", '"x"')),
    (("Note", "Note:"), 'set Note:"x"', ("Note:", '"x"')),
    (("Note", "Note:"), "set Note: :", ("Note:", ":")),
    (("Mark", "Mark: Ref"), "set Mark: Ref := 5", ("Mark: Ref", ":= 5")),
    (("Mark", "Mark: Ref"), "set Mark: 5", ("Mark", "5")),
])
def test_a_longer_colon_caption_typed_exactly_wins(caps, clause, want):
    inv = type("I", (), {"params": [{"caption": c} for c in caps], "type_names": ["T1"]})
    m = MF._match_set(inv, clause)
    assert (m.group("cap"), m.group("val")) == want


@pytest.mark.parametrize("caps", [("Note", "Note:"), ("Note", "Note: A"), ("Note",)])
def test_a_glued_colon_with_no_value_is_always_refused(caps):
    inv = type("I", (), {"params": [{"caption": c} for c in caps], "type_names": ["T1"]})
    with pytest.raises(MF.FamilyEditError, match="no value given"):
        MF._match_set(inv, "set Note:")


def test_a_mistyped_longer_colon_caption_is_refused():
    # with captions Note / Note: Install (and no 'Note:' caption -- where one
    # exists, 'set Note: Installs = x' names it exactly, as on main)
    inv = type("I", (), {"params": [{"caption": c} for c in ("Note", "Note: Install")],
                         "type_names": ["T1"]})
    with pytest.raises(MF.FamilyEditError, match="no parameter 'Note: Installs'"):
        MF._match_set(inv, "set Note: Installs = x")


@pytest.mark.parametrize("clause", ["set Note to A: to x", "set Note to A:= x", "set Note: = x"])
def test_a_colon_followed_by_another_delimiter_is_refused(clause):
    inv = type("I", (), {"params": [{"caption": c} for c in ("Note", "Note to A")],
                         "type_names": ["T1"]})
    with pytest.raises(MF.FamilyEditError):
        MF._match_set(inv, clause)

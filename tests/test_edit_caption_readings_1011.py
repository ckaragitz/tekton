"""#1011 -- "of type" inside or after a caption never lands as a value of a
shorter caption; two caption readings are refused; a typed value ending in a
type is refused; a unit-bearing bare value after a long caption parses.

From the second review of PR #1010 (all also on main).  Principle (#994):
a refusal is recoverable, a mis-targeted write is not.

Run: .venv/bin/python -m pytest tests/test_edit_caption_readings_1011.py -q
"""
from __future__ import annotations

import os
import re
import shutil
import tempfile

import pytest

from conftest import HAVE_SCHEMA, context_constants, ladder_constants
from rvt.convert import modify_family as MF

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


class _S:
    params = [{"caption": c} for c in ("Size of Type", "Size", "Finish")]
    type_names = ["Big", "Big One", "T2"]


class _D:
    params = [{"caption": c} for c in ("Distance", "Distance to Wall", "Finish")]
    type_names = ["T1"]


class _DT:
    params = [{"caption": c} for c in ("Distance", "Distance to Wall")]
    type_names = ["T", "T 1"]


class _SA:
    params = [{"caption": c} for c in ("Size of Type", "Size of Type A", "Size")]
    type_names = ["T1"]


class _MN:
    params = [{"caption": c} for c in ("Mark", "Mark Note")]
    type_names = ["T1"]


class _G:
    params = [{"caption": c} for c in ("Mounting", "Mounting Height", "Enclosure Rating",
                                       "Mark", "Mark Note")]
    type_names = ["T1"]


class _A:
    params = [{"caption": c} for c in ("Size of Type A", "Size", "Finish")]
    type_names = ["A", "B"]


def _read(inv, clause):
    m = MF._match_set(inv, clause)
    return m.group("cap"), m.group("val"), m.group("typeq") or m.group("typeq2") or m.group("type")


@pytest.mark.parametrize("inv, clause, match", [
    (_S, "set Size of Type", "no value given"),                                   # (1)
    (_S, "set Size of Type Big Mac", "reads two ways"),                          # (2)
    (_A, "set Size of Type A = 5", "reads two ways"),
    (_A, "set Size of Type A to 5", "reads two ways"),
    (_A, "set Size of Type A 5", "reads two ways"),
    (_S, "set Size of type Big One to of type Big", "the value ends in 'of type Big'"),  # (3)
    (_S, "set Finish of type T2 to x of type 'Big One'", "the value ends in 'of type Big One'"),
    # the clause IS a multi-word caption with no value: never the shorter
    # caption = the rest (PR #1012 review: Distance = "Wall to")
    (_D, "set Distance to Wall to", "no value given for 'Distance to Wall'"),
    (_D, "set Distance to Wall", "no value given for 'Distance to Wall'"),
    (_D, "set Distance to Wall.", "no value given for 'Distance to Wall'"),
    # PR #1013 review: whitespace and more punctuation never bypass it
    (_D, "set Distance to  Wall to", "no value given for 'Distance to Wall'"),
    (_D, "set Distance  to  Wall", "no value given for 'Distance to Wall'"),
    (_D, "set Distance to Wall?", "no value given for 'Distance to Wall'"),
    (_D, "set Distance to Wall:", "no value given for 'Distance to Wall'"),
    # the longest caption's bare value holds a delimiter: two readings
    (_D, "set Distance to Wall height to 3", "reads two ways"),
])
def test_refused(inv, clause, match):
    with pytest.raises(MF.FamilyEditError, match=re.escape(match)):
        MF._match_set(inv, clause)


@pytest.mark.parametrize("inv, clause, want", [
    (_S, "set Size of Type 5 mm", ("Size of Type", "5 mm", None)),               # (4)
    (_S, "set Size of Type 5", ("Size of Type", "5", None)),
    (_S, "set Size of Type to 5", ("Size of Type", "5", None)),
    (_S, "set Size of type Big One = 5", ("Size", "5", "Big One")),              # #1010 kept
    (_S, "set Size of Type of type Big One = 5", ("Size of Type", "5", "Big One")),
    (_S, "set Size 5", ("Size", "5", None)),
    (_S, "set Finish of type T2 to x of type steel", ("Finish", "x of type steel", "T2")),
    (_A, "set Size of type B = 5", ("Size", "5", "B")),
    (_D, "set Distance to Wall to 3 ft", ("Distance to Wall", "3 ft", None)),
    (_D, "set Distance to 3 ft", ("Distance", "3 ft", None)),
    # the LONGEST caption followed by a bare value is the parameter (#1013 review)
    (_D, "set Distance to Wall 3 ft", ("Distance to Wall", "3 ft", None)),
    (_D, "set Distance to Wall: 3", ("Distance to Wall", "3", None)),
    (_D, "set Distance  to  Wall = 2 ft", ("Distance to Wall", "2 ft", None)),
    (_D, "set Finish = two  spaces", ("Finish", "two  spaces", None)),   # value spacing kept
    # B1 (#1013 second review): a QUOTED type is the qualifier -- the form the
    # two-readings refusal tells the user to write
    (_S, 'set Size of type "Big One" 5', ("Size", "5", "Big One")),
    (_S, 'set Size of type "Big One" = 5', ("Size", "5", "Big One")),
    (_S, "set Size of type 'Big One' to 5", ("Size", "5", "Big One")),
    (_S, 'set Size of type "T2" = 5', ("Size", "5", "T2")),
    # B2: a caption typed with extra spaces resolves its type whole
    (_DT, "set Distance to  Wall of type T 1 = 4", ("Distance to Wall", "4", "T 1")),
    (_DT, "set Distance  to  Wall of type T 1 4", ("Distance to Wall", "4", "T 1")),
    # third review: a caption ending INSIDE a word is not named -- the shorter
    # caption + 'to' reads it, value as typed (main's result)
    (_D, "set Distance to Wall-mounted box", ("Distance", "Wall-mounted box", None)),
    (_D, "set Distance to Wall's face", ("Distance", "Wall's face", None)),
    (_D, 'set Distance to Wall"3"', ("Distance", 'Wall"3"', None)),
    (_D, "set Distance to Wall.5", ("Distance", "Wall.5", None)),
    (_D, "set Distance to Wall/Floor", ("Distance", "Wall/Floor", None)),
    (_D, "set Distance to Wall(s)", ("Distance", "Wall(s)", None)),
    (_D, "set Distance to Wall,5", ("Distance", "Wall,5", None)),
    (_D, "set Distance\tto\tWall-mounted", ("Distance", "Wall-mounted", None)),
    (_D, "set Distance to Wall=3", ("Distance to Wall", "3", None)),
    # fourth review: a caption ending inside a NON-ASCII word is not named either
    (_SA, "set Size of Type Aé", ("Size of Type", "Aé", None)),
    (_SA, "set Size of Type Aé red", ("Size of Type", "Aé red", None)),
    (_SA, "set Size of Type A 5", ("Size of Type A", "5", None)),
    (_MN, "set Mark Noteé", ("Mark", "Noteé", None)),
    (_MN, "set Mark Note x", ("Mark Note", "x", None)),
    (_D, "set Distance to Wallé x", ("Distance", "Wallé x", None)),
])
def test_read(inv, clause, want):
    assert _read(inv, clause) == want


@pytest.fixture(scope="module")
def conduit_two_captions():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t1011_")
    try:
        p = os.path.join(d, "conduit.rfa")
        F.make_archetype(product="conduit",
                         text_params={"Size": "s0", "Size of Type": "t0"}).write(
            p, validate=False, provenance=False)
        yield p
    finally:
        shutil.rmtree(d, True)


def test_no_value_after_the_long_caption_writes_nothing(conduit_two_captions, tmp_path):
    inv = MF.inventory_family(conduit_two_captions)
    before = {c: inv.param_by_caption(c)["current"] for c in ("Size", "Size of Type")}
    with pytest.raises(MF.FamilyEditError, match="no value given"):
        MF.modify_family(conduit_two_captions, "set Size of Type", str(tmp_path))
    after = MF.inventory_family(conduit_two_captions)
    assert {c: after.param_by_caption(c)["current"] for c in before} == before
    rec = MF.modify_family(conduit_two_captions, "set Size of Type 5 mm", str(tmp_path))
    assert MF.inventory_family(rec["files"]["rfa"]).param_by_caption("Size of Type")["current"] \
        == "5 mm"


def test_the_longest_caption_with_a_value_on_a_generated_family(tmp_path):
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    from rvt.famgen import factory as F
    p = str(tmp_path / "c.rfa")
    F.make_archetype(product="conduit",
                     text_params={"Distance": "d0", "Distance to Wall": "w0"}).write(
        p, validate=False, provenance=False)
    rec = MF.modify_family(p, "set Distance to Wall 3 ft", str(tmp_path / "o"))
    inv = MF.inventory_family(rec["files"]["rfa"])
    assert (inv.param_by_caption("Distance")["current"],
            inv.param_by_caption("Distance to Wall")["current"]) == ("d0", "3 ft")


def test_a_caption_ending_inside_a_word_on_a_generated_family(tmp_path):
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    from rvt.famgen import factory as F
    p = str(tmp_path / "c.rfa")
    F.make_archetype(product="conduit",
                     text_params={"Distance": "d0", "Distance to Wall": "w0"}).write(
        p, validate=False, provenance=False)
    rec = MF.modify_family(p, "set Distance to Wall-mounted box", str(tmp_path / "o"))
    inv = MF.inventory_family(rec["files"]["rfa"])
    assert (inv.param_by_caption("Distance")["current"],
            inv.param_by_caption("Distance to Wall")["current"]) == ("Wall-mounted box", "w0")


@pytest.mark.parametrize("clause", [
    # fifth review: a caption running straight into a combining mark, a
    # zero-width joiner or an emoji cannot be read safely -- refused
    "set Mounting Height\u200d 1",
    "set Mounting Height\u0301 to red",
    "set Enclosure Rating\u0308 1",
    "set Mark Note\U0001F600 1",
])
def test_a_caption_glued_to_a_mark_or_symbol_is_refused(clause):
    with pytest.raises(MF.FamilyEditError, match="runs straight into the character"):
        MF._match_set(_G, clause)


@pytest.mark.parametrize("inv, clause, want", [
    (_SA, "set Size of Type A\u0301 5", None),             # NFD 'Á': refused, never "\u0301 5"
    (_G, "set Mark Note x to red", ("Mark Note", "x to red", None)),   # no shorter reading
    (_G, "set Mark Note\xa0x to red", ("Mark Note", "x to red", None)),
    (_G, "set Mark to red", ("Mark", "red", None)),
])
def test_unicode_and_single_reading_forms(inv, clause, want):
    if want is None:
        with pytest.raises(MF.FamilyEditError):
            MF._match_set(inv, clause)
    else:
        assert _read(inv, clause) == want


class _TM:
    params = [{"caption": c} for c in ("Size", "Size\u2122 Code", "Temp", "Temp\u00b0 Rating")]
    type_names = ["T1"]


@pytest.mark.parametrize("clause, want", [
    # sixth review B1: a LONGER caption the user typed whole is never refused
    # as "glued" because a shorter prefix caption sits inside it
    ("set Size\u2122 Code = 5", ("Size\u2122 Code", "5", None)),
    ("set Size\u2122 Code to 5", ("Size\u2122 Code", "5", None)),
    ("set Size\u2122 Code 5", ("Size\u2122 Code", "5", None)),
    ("set Size\u2122 Code of type T1 = 5", ("Size\u2122 Code", "5", "T1")),
    ("set Temp\u00b0 Rating = 90", ("Temp\u00b0 Rating", "90", None)),
])
def test_a_longer_caption_containing_a_symbol_reads_whole(clause, want):
    assert _read(_TM, clause) == want


def test_a_glued_refusal_names_no_guessed_caption():
    with pytest.raises(MF.FamilyEditError) as e:
        MF._match_set(_TM, "set Size\u2122 5")
    assert "set <Parameter> = <value>" in str(e.value) and "set Size =" not in str(e.value)


@pytest.mark.parametrize("stored, typed", [("NFD", "NFC"), ("NFC", "NFD")])
def test_a_caption_matches_in_either_normalisation_form(stored, typed):
    import unicodedata as U
    long_cap = "Size of Type " + U.normalize(stored, "\u00c1")

    class _N:
        params = [{"caption": c} for c in ("Size of Type", long_cap, "Size")]
        type_names = ["T1"]
    clause = "set Size of Type " + U.normalize(typed, "\u00c1") + " 5"
    assert _read(_N, clause) == (long_cap, "5", None)

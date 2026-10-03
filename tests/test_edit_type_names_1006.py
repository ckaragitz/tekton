"""#1006 -- an unquoted multi-word type name after ``of type`` is ONE name.

Generated families' type names carry spaces ("Conduit - Straight Run 0.75
in 10 ft").  The grammar took an unquoted name's first word as the type --
and, because a type is matched by substring, wrote the rest of the name into
the value of that type -- or folded the whole clause into the value of the
DEFAULT type.  Now the family's own type names are resolved first (longest,
case-insensitive, word boundary); an unquoted multi-word name that is not a
type of the family is refused by name.  A refusal is recoverable, a
mis-targeted write is not (#994).

All fixtures are ours.  No desktop verdict is claimed (hard rule 4).

Run: .venv/bin/python -m pytest tests/test_edit_type_names_1006.py -q
"""
from __future__ import annotations

import os
import re
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import HAVE_SCHEMA, context_constants, ladder_constants   # noqa: E402
from rvt.convert import modify_family as MF                             # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")

LONG = "Conduit - Straight Run 0.75 in 10 ft"


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


class _Inv:
    params = [{"caption": c} for c in ("Material", "Finish", "Width")]
    type_names = [LONG, LONG + " Long", "Big One", "Run to Ground", "T1"]


def _parse(clause):
    m = MF._match_set(_Inv, clause)
    return m.group("cap"), m.group("val"), (m.group("typeq") or m.group("typeq2")
                                            or m.group("type"))


@pytest.mark.parametrize("clause, want", [
    # the four rows of #1006 -- the first is refused later by name ("Finish color")
    (f"set Finish color of type {LONG} to black", ("Finish color", "black", LONG)),
    (f"set Finish of type {LONG} to black", ("Finish", "black", LONG)),
    ("set Width of type Big One to 3 ft", ("Width", "3 ft", "Big One")),
    ("set Finish of type T1 to black", ("Finish", "black", "T1")),
    # case-insensitive; the longest name wins over its prefix
    (f"set Finish of type {LONG.lower()} long = red", ("Finish", "red", LONG + " Long")),
    # a type name containing 'to'
    ("set Finish of type Run to Ground to black", ("Finish", "black", "Run to Ground")),
    # the bare-value form with an exact name (any case) still works
    ("set Finish of type Big One black", ("Finish", "black", "Big One")),
    ("set Width of type t1 3 ft", ("Width", "3 ft", "T1")),
    # quoted and single-token forms are unchanged
    (f'set Finish of type "{LONG}" to black', ("Finish", "black", LONG)),
    ("set Finish to black", ("Finish", "black", None)),
])
def test_a_family_type_name_is_one_name(clause, want):
    assert _parse(clause) == want


@pytest.mark.parametrize("clause, named", [
    ("set Finish of type Conduit - Straight Run to black", "Conduit - Straight Run"),
    ("set Width of type Big Two to 3 ft", "Big Two"),
    # no to / '=': a first word that is not EXACTLY a type cannot be told from
    # the value ("Big" would substring-match 'Big One' and get "Two black")
    ("set Finish of type Big Two black", "Big ..."),
    ("set Finish of type Conduit - Straight black", "Conduit ..."),
])
def test_an_unknown_multi_word_type_is_refused_by_name(clause, named):
    with pytest.raises(MF.FamilyEditError, match=re.escape(f"'of type {named}' is not a type")):
        MF._match_set(_Inv, clause)


def test_the_value_hint_keeps_a_full_type_name_whole():
    hint = MF._value_hint(_Inv, "Finish color", f"set Finish color of type {LONG} to black")
    assert hint.endswith(f'set Finish of type "{LONG}" = color to black')


@pytest.fixture(scope="module")
def conduit():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t1006_")
    try:
        p = os.path.join(d, "conduit.rfa")
        F.make_archetype(product="conduit").write(p, validate=False, provenance=False)
        yield p
    finally:
        shutil.rmtree(d, True)


def test_an_unquoted_generated_type_name_targets_that_type(conduit, tmp_path):
    inv = MF.inventory_family(conduit)
    (name,) = inv.type_names
    assert " " in name                                   # the premise: spaces in the name
    rec = MF.modify_family(conduit, f"set Finish of type {name} to black", str(tmp_path))
    out = rec["files"]["rfa"]
    assert MF.inventory_family(out).param_by_caption("Finish")["current"] == "black"
    assert rec["validation"]["rfa"]["self_checks_ok"]
    with pytest.raises(MF.FamilyEditError, match="is not a type"):
        MF.parse_family_edit(f"set Finish of type {name.split()[0]} Wrong Words to black", inv)

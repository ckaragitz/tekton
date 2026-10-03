"""#1008 -- a text value keeps the user's quotes unless it is wholly wrapped
in one matching pair, and ``set P to`` / ``set P =`` with no value is refused
instead of storing the delimiter.

No desktop verdict is claimed (hard rule 4).

Run: .venv/bin/python -m pytest tests/test_edit_values_1008.py -q
"""
from __future__ import annotations

import os
import shutil
import tempfile

import pytest

from conftest import HAVE_SCHEMA, context_constants, ladder_constants
from rvt.convert import modify_family as MF

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


_TEXT = {"caption": "Finish", "param_id": 1, "carrier": "m_str", "spec": "", "def_class": ""}


@pytest.mark.parametrize("raw, want", [
    ("'quoted' value", "'quoted' value"),
    ('"x"', "x"),
    ("'x'", "x"),
    ('3/4" EMT', '3/4" EMT'),
    ("it's fine", "it's fine"),
    ('"to"', "to"),
    ('"mixed\'', '"mixed\''),
    ("plain", "plain"),
])
def test_a_text_value_is_unquoted_only_when_wholly_wrapped(raw, want):
    assert MF._convert_value(_TEXT, raw)[0] == want


class _Inv:
    params = [_TEXT]
    type_names = ["T1"]

    def param_by_caption(self, caption):
        return _TEXT if caption.lower() == "finish" else None


@pytest.mark.parametrize("clause", ["set Finish to", "set Finish =", "set Finish of type T1 ="])
def test_a_missing_value_is_refused(clause):
    with pytest.raises(MF.FamilyEditError, match="no value given"):
        MF.parse_family_edit(clause, _Inv())


@pytest.fixture(scope="module")
def conduit():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t1008_")
    try:
        p = os.path.join(d, "conduit.rfa")
        F.make_archetype(product="conduit").write(p, validate=False, provenance=False)
        yield p
    finally:
        shutil.rmtree(d, True)


def test_a_quoted_word_reads_back_as_typed(conduit, tmp_path):
    rec = MF.modify_family(conduit, "set Finish = 'hot dip' galvanized", str(tmp_path))
    assert MF.inventory_family(rec["files"]["rfa"]).param_by_caption("Finish")["current"] \
        == "'hot dip' galvanized"

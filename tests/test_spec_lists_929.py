"""A malformed drives / heights / diameters argument is a reported refusal,
never an exception that withholds the file (hard rule 1; #929 review)."""
from __future__ import annotations

import pytest

from rvt.famgen import factory as F

BOX = {"shape": "box", "name": "a", "width_ft": 1.0, "depth_ft": 1.0,
       "height_ft": 1.0, "center": [0.0, 0.0]}


@pytest.mark.parametrize("kw", ["drives", "heights", "diameters"])
@pytest.mark.parametrize("bad", [5, True, "x", 1.5], ids=["int", "bool", "str", "float"])
@pytest.mark.parametrize("multipart", [True, False], ids=["multipart", "single"])
def test_a_malformed_spec_argument_still_delivers(kw, bad, multipart):
    parts = [dict(BOX)] + ([dict(BOX, name="b", center=[3.0, 0.0])] if multipart else [])
    prod = F.make_generic_model(parts=parts, name="f", **{kw: bad})
    assert prod.doc.finalized
    assert any("not wired" in n for n in prod.doc.notes)


def test_spec_list_shapes():
    assert F._spec_list(None) is None and F._spec_list([]) == []
    assert F._spec_list(({"a": 1},)) == [{"a": 1}]
    assert F._spec_list({"a": 1}) == [{"a": 1}]
    assert F._spec_list("ab") == ["ab"] and F._spec_list(5) == [5]
    assert F._spec_list(x for x in (1, 2)) == [1, 2]

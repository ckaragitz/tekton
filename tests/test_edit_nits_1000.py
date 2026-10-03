"""#1000 -- the optional nits of PR #997's final review.

N1: our own PartAtom built with ZERO types carries no ``<A:type>``; a
    rename-family still renames its ``<A:feature><A:title>`` (only Revit's
    ``<A:family><A:part>`` form keeps a feature title -- a parameter group).
N2: the refusal's recovery hint quotes the user's own clause with ``=``
    after the caption, whichever delimiter they wrote.

All fixtures are hand-written stubs or ours.  No desktop verdict is claimed
(hard rule 4).

Run: .venv/bin/python -m pytest tests/test_edit_nits_1000.py -q
"""
from __future__ import annotations

import pytest

from rvt.convert import modify_family as MF
from rvt.famgen import skeleton as SK


def _patch(monkeypatch, xml):
    written = {}

    class _F:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def raw(self, _name):
            return xml.encode()
    import rvt.container as C
    import rvt.roundtrip as R
    monkeypatch.setattr(C, "open_rvt", lambda _p: _F())
    monkeypatch.setattr(R, "rewrite_entries", lambda _a, _b, d: written.update(d))
    MF._patch_partatom_scoped("x.rfa", "New", {})
    return written["PartAtom"].decode()


@pytest.mark.parametrize("types", [(), ("Old",), ("T1", "T2")])
def test_our_form_renames_its_feature_title_with_any_type_count(monkeypatch, types):
    xml = SK.build_part_atom("Old", "Electrical Equipment", type_names=types).decode()
    assert ("<A:type>" in xml) == bool(types)
    got = _patch(monkeypatch, xml)
    assert "<A:feature><A:title>New</A:title>" in got
    assert "<A:feature><A:title>Old</A:title>" not in got
    assert "<A:title>New.rfa</A:title>" in got


def test_revit_form_keeps_its_parameter_group_title(monkeypatch):
    xml = ('<entry><title>Constraints</title><id>Constraints</id><A:family type="user">'
           '<A:part type="user"><title>T1</title></A:part></A:family>'
           '<A:features><A:feature><A:title>Constraints</A:title></A:feature></A:features>'
           '</entry>')
    got = _patch(monkeypatch, xml)
    assert got.startswith("<entry><title>New</title><id>New</id>")
    assert "<A:feature><A:title>Constraints</A:title></A:feature>" in got


class _Inv:
    params = [{"caption": c} for c in ("Material", "Finish")]


@pytest.mark.parametrize("caption, clause, example", [
    ("Finish color", "set Finish color = black", "set Finish = color = black"),
    ("Finish galvanized", "set Finish galvanized to spec", "set Finish = galvanized to spec"),
    ("finish color", "set the finish color to black", "set Finish = color to black"),
])
def test_the_hint_quotes_the_users_own_clause(caption, clause, example):
    assert MF._value_hint(_Inv, caption, clause).endswith(example)


def test_the_hinted_form_parses_to_the_known_caption():
    m = MF._match_set(_Inv, "set Finish = color = black")
    assert (m.group("cap"), m.group("val")) == ("Finish", "color = black")


def test_the_refusal_carries_the_hint_from_the_clause():
    class _Full(_Inv):
        def param_by_caption(self, _c):
            return None
    with pytest.raises(MF.FamilyEditError, match=r"set Finish = color = black$"):
        MF.parse_family_edit("set Finish color = black", _Full())

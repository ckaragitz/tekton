"""#994 -- the leftovers of PR #993's re-review of the family-edit lane.

1. A rename-type touches only the type: in a generated family the type name
   equals the family title, and the PartAtom follow used to be a plain text
   replace, so "rename the type to Y" also retitled the family, and "rename
   the type ...; rename the family to X" ended up titled "Y" with a failed
   re-read.  Now each rename rewrites only its own PartAtom elements, in any
   order.
2. The rebuilt edit's name note is true for every combination: Revit names a
   LOADED family by its FILE name, so the note says which file name loads over
   the placed family; it names exactly the names that are still dimension-
   derived and stale (the family title unless renamed, the type unless renamed).
3. A clause with ``to`` names its parameter as everything before it, so
   ``set Material Finish to galvanized`` / ``set finish color to black`` /
   ``set Model number to X`` are refused by name, never written to Material /
   Finish / Model (the review of PR #997: no case or vocabulary rule tells a
   value's words from a mistyped parameter).  ``set Finish galvanized to
   spec`` is refused the same way, and the refusal names the recovery:
   ``set Finish = galvanized to spec`` (or ``set Finish to galvanized to
   spec``), which writes Finish = "galvanized to spec".
4. An op a later op of the same edit overrides gets ONE "overridden" note and
   no note about a value the file does not carry.

All fixtures are OURS, generated here.  No desktop verdict is claimed (hard
rule 4).

Run: .venv/bin/python -m pytest tests/test_edit_leftovers_994.py -q
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import HAVE_SCHEMA, context_constants, ladder_constants   # noqa: E402
from rvt.convert import modify_family as MF                             # noqa: E402

needs_schema = pytest.mark.skipif(not HAVE_SCHEMA, reason="class schema cache absent")

# the rebuild nests through famgen.nest (host_release_context): conftest's
# guard watches it (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


def _build(product: str, d: str) -> str:
    from rvt.famgen import factory as F
    p = os.path.join(d, product + ".rfa")
    F.make_archetype(product=product).write(p, validate=False, provenance=False)
    return p


@pytest.fixture(scope="module")
def conduit():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    d = tempfile.mkdtemp(prefix="t994c_")
    try:
        yield _build("conduit", d)
    finally:
        shutil.rmtree(d, True)


@pytest.fixture(scope="module")
def trapeze():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    d = tempfile.mkdtemp(prefix="t994t_")
    try:
        yield _build("strut_trapeze", d)
    finally:
        shutil.rmtree(d, True)


def _partatom(path) -> str:
    from rvt.container import open_rvt
    with open_rvt(path) as f:
        return f.raw("PartAtom").decode("utf-8")


def _edit(src, edit, d, **kw):
    rec = MF.modify_family(str(src), edit, str(d), **kw)
    return rec, rec["files"]["rfa"]


# --------------------------------------------------------------------------- 1. rename-type

@needs_schema
def test_a_type_rename_alone_keeps_the_family_title(conduit, tmp_path):
    title = MF.inventory_family(conduit).family_name
    assert MF.inventory_family(conduit).type_names == [title]       # the premise
    rec, out = _edit(conduit, "rename the type to Y", tmp_path)
    inv = MF.inventory_family(out)
    assert inv.type_names == ["Y"] and inv.family_name == title
    xml = _partatom(out)
    assert f"<title>{title}</title>" in xml and f"<id>{title}</id>" in xml
    assert "<A:type><A:title>Y</A:title></A:type>" in xml
    assert f"<A:feature><A:title>{title}</A:title>" in xml
    assert rec["validation"]["rfa"]["self_checks_ok"]


@needs_schema
@pytest.mark.parametrize("edit", [
    "rename the type to Y; rename the family to X",
    "rename the family to X; rename the type to Y",
    "set Length to 20 ft; rename the type to Y; rename the family to X",
    "rename the type to Y; rename the family to X; set Length to 20 ft",
])
def test_type_and_family_renames_are_order_independent(conduit, tmp_path, edit):
    rec, out = _edit(conduit, edit, tmp_path)
    inv = MF.inventory_family(out)
    assert (inv.family_name, inv.type_names, os.path.basename(out)) == ("X", ["Y"], "X.rfa")
    xml = _partatom(out)
    assert "<title>X</title>" in xml and "<A:design-file><A:title>X.rfa</A:title>" in xml
    assert "<A:type><A:title>Y</A:title></A:type>" in xml
    g = rec["validation"]["rfa"]
    assert g["self_checks_ok"] and all(r["ok"] for r in g["reread"])


@needs_schema
def test_the_reread_fails_when_the_family_title_is_not_the_renamed_one(conduit, tmp_path):
    """The rename-family re-read is exact now (it was a substring test)."""
    _rec, out = _edit(conduit, "rename the family to Xy", tmp_path)
    assert MF._reread_proof(out, [{"op": "rename-family", "name": "X"}])[0]["ok"] is False
    assert MF._reread_proof(out, [{"op": "rename-family", "name": "Xy"}])[0]["ok"] is True


@needs_schema
def test_renames_are_xml_escaped(conduit, tmp_path):
    rec, out = _edit(conduit, "rename the type to A&B <1>; rename the family to C&D", tmp_path)
    inv = MF.inventory_family(out)
    assert inv.type_names == ["A&B <1>"]
    xml = _partatom(out)
    assert "<title>C&amp;D</title>" in xml and "<A:title>A&amp;B &lt;1&gt;</A:title>" in xml
    assert rec["validation"]["rfa"]["self_checks_ok"]
    assert MF._partatom_title(out) == "C&D"            # read back unescaped


def test_the_scoped_patch_reads_a_revit_born_part_list(tmp_path, monkeypatch):
    """Revit's own PartAtom names types as ``<A:part ...><title>`` -- a type
    rename finds them; the family's ``<title>`` is the entry's FIRST one."""
    xml = ('<entry><title>Fam</title><id>Fam</id><A:family type="user">'
           '<A:part type="user"><title>Fam</title></A:part>'
           '<A:part type="user"><title>T2</title></A:part></A:family></entry>')
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
    rep = MF._patch_partatom_scoped("x.rfa", None, {0: ("Fam", "Big")})
    got = written["PartAtom"].decode()
    assert rep["changed"] and got == xml.replace('<A:part type="user"><title>Fam',
                                                 '<A:part type="user"><title>Big')
    written.clear()
    MF._patch_partatom_scoped("x.rfa", "NewFam", {})
    got = written["PartAtom"].decode()
    assert got.startswith("<entry><title>NewFam</title><id>NewFam</id>")
    assert '<A:part type="user"><title>Fam</title>' in got                # the type kept


def test_a_revit_born_feature_group_title_is_never_renamed(tmp_path, monkeypatch):
    """In Revit's PartAtom ``<A:feature><A:title>`` is a parameter GROUP; a
    family that happens to be titled like a group keeps the group's title."""
    xml = ('<entry><title>Constraints</title><id>Constraints</id><A:family type="user">'
           '<A:part type="user"><title>T1</title></A:part></A:family>'
           '<A:features><A:feature><A:title>Constraints</A:title></A:feature></A:features>'
           '</entry>')
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
    got = written["PartAtom"].decode()
    assert got.startswith("<entry><title>New</title><id>New</id>")
    assert "<A:feature><A:title>Constraints</A:title></A:feature>" in got


# --------------------------------------------------------------------------- 2. name notes

def _name_note(rec):
    notes = [d for d in rec["degradations"] if "generated from the old dimensions" in d]
    assert len(notes) <= 1
    assert notes == ([rec["regeneration"]["name_note"]]
                     if rec["regeneration"].get("name_note") else [])
    return notes[0] if notes else ""


@needs_schema
def test_a_default_edit_says_it_loads_as_a_second_family(conduit, tmp_path):
    rec, out = _edit(conduit, "set Length to 20 ft", tmp_path)
    note = _name_note(rec)
    assert "reloads over the original" not in note
    assert "the family title" in note and "the type name" in note
    assert "'Conduit - Straight Run 0.75 in 20 ft'" in note
    assert "'conduit.edited.rfa'" in note and "SECOND family 'conduit.edited'" in note
    assert "save or load it as 'conduit.rfa' to replace the placed family" in note


@needs_schema
def test_an_edit_written_under_the_input_file_name_says_it_replaces(conduit, tmp_path):
    rec, out = _edit(conduit, "set Length to 20 ft", tmp_path, stem="conduit")
    note = _name_note(rec)
    assert os.path.basename(out) == "conduit.rfa"
    assert "keeps the input's file name 'conduit.rfa', so loading it replaces" in note
    assert "SECOND" not in note


@needs_schema
@pytest.mark.parametrize("edit, fam_stale, type_stale", [
    ("set Length to 20 ft; rename the type to Y", True, False),
    ("rename the type to Y; set Length to 20 ft", True, False),
    ("set Length to 20 ft; rename the family to X", False, True),
    ("rename the family to X; set Length to 20 ft", False, True),
    ("set Length to 20 ft; rename the family to X; rename the type to Y", False, False),
])
def test_the_name_note_names_exactly_the_stale_names(conduit, tmp_path, edit, fam_stale,
                                                    type_stale):
    rec, out = _edit(conduit, edit, tmp_path)
    note = _name_note(rec)
    assert rec["regeneration"]["route"] == "regenerated"
    assert bool(note) == (fam_stale or type_stale)
    assert ("the family title" in note) == fam_stale
    assert ("the type name" in note) == type_stale
    # reload advice only when the family keeps its identity (no rename-family)
    assert ("Revit names a loaded family by its file name" in note) == fam_stale
    inv = MF.inventory_family(out)
    assert (inv.family_name == "X") != fam_stale
    assert (inv.type_names == ["Y"]) != type_stale


@needs_schema
def test_no_name_note_when_the_name_was_not_the_generators(tmp_path):
    from rvt.famgen import factory as F
    src = str(tmp_path / "custom.rfa")
    F.make_archetype(product="conduit", name="My Conduit").write(src, validate=False,
                                                                 provenance=False)
    rec, _out = _edit(src, "set Length to 20 ft", tmp_path / "o")
    assert rec["regeneration"]["route"] == "regenerated"
    assert _name_note(rec) == ""


# --------------------------------------------------------------------------- 3. grammar

class _Inv:
    params = [{"caption": c} for c in ("Material", "Finish", "Width", "Strut Length", "Model")]


@pytest.mark.parametrize("clause, cap, val", [
    # everything before the first 'to' is the parameter -> refused by name later
    ("set Finish galvanized to spec", "Finish galvanized", "spec"),
    ("set Material Finish to galvanized", "Material Finish", "galvanized"),
    ("set Material Color to red", "Material Color", "red"),
    ("set material color to red", "material color", "red"),
    ("set finish color to black", "finish color", "black"),
    ("set Model number to ABC-1", "Model number", "ABC-1"),
    # the value after an explicit delimiter may contain 'to'
    ("set Finish = galvanized to spec", "Finish", "galvanized to spec"),
    ("set Finish to galvanized to spec", "Finish", "galvanized to spec"),
    ("set Strut Length to 36 in", "Strut Length", "36 in"),
    ("set Width 600 mm", "Width", "600 mm"),
])
def test_a_known_caption_with_a_value_containing_to(clause, cap, val):
    m = MF._match_set(_Inv, clause)
    assert (m.group("cap"), m.group("val")) == (cap, val)


def test_the_refusal_names_the_recovery_only_after_a_known_caption():
    hint = MF._value_hint(_Inv, "Finish galvanized")
    assert hint.endswith("set Finish = <value>")         # no clause: a placeholder (#1000)
    assert MF._value_hint(_Inv, "Colour") == ""
    assert MF._value_hint(_Inv, "Finishes") == ""          # not a word boundary


@needs_schema
@pytest.mark.parametrize("clause, cap", [
    ("set Finish galvanized to spec", "Finish galvanized"),
    ("set finish color to black", "finish color"),
    ("set material color to red", "material color"),
    ("set Material Finish to galvanized", "Material Finish"),
    ("set Material Color to red", "Material Color"),
])
def test_a_parameter_the_family_lacks_is_refused_never_written(conduit, clause, cap):
    inv = MF.inventory_family(conduit)
    with pytest.raises(MF.FamilyEditError, match=f"no parameter '{cap}'") as e:
        MF.parse_family_edit(clause, inv)
    if cap.lower().startswith(("finish ", "material ")):
        assert "write the value after '='" in str(e.value)


@needs_schema
def test_finish_equals_galvanized_to_spec_is_written(conduit, tmp_path):
    inv = MF.inventory_family(conduit)
    for clause in ("set Finish = galvanized to spec", "set Finish to galvanized to spec"):
        ops = MF.parse_family_edit(clause, inv)["ops"]
        assert [(o["caption"], o["value"]) for o in ops] == [("Finish", "galvanized to spec")]
    rec, out = _edit(conduit, "set Finish = galvanized to spec", tmp_path)
    assert MF.inventory_family(out).param_by_caption("Finish")["current"] == "galvanized to spec"
    assert rec["validation"]["rfa"]["self_checks_ok"]


# --------------------------------------------------------------------------- 4. overridden ops

@needs_schema
def test_an_overridden_op_gets_one_overridden_note_and_nothing_else(trapeze, tmp_path):
    rec, out = _edit(trapeze, "set Strut Length to 1 in; set Strut Length to 36 in", tmp_path)
    assert rec["regeneration"]["route"] == "regenerated"
    sl = [d for d in rec["degradations"] if d.startswith("Strut Length:")]
    assert len(sl) == 2
    assert "'1 in' (op 1) is overridden by a later op in the same edit (op 2: '36 in')" in sl[0]
    assert sl[1] == "Strut Length: 36 in -> 3 ft" + MF.REBUILT_NOTE
    assert not any(d.startswith("Strut Length: 1 in") for d in rec["degradations"])
    ops = rec["parsed"]["ops"]
    assert ops[0]["overridden_by"] == 2 and "overridden_by" not in ops[1]
    reread = rec["validation"]["rfa"]["reread"]
    assert len(reread) == 1 and reread[0]["ok"]
    assert MF.inventory_family(out).param_by_caption("Strut Length")["current"] == \
        pytest.approx(3.0)


@needs_schema
def test_overridden_renames_and_scoped_sets(conduit, tmp_path):
    inv = MF.inventory_family(conduit)
    t = inv.type_names[0]
    parsed = MF.parse_family_edit(
        f'rename the type to A; rename the type to B; rename the family to F1; '
        f'rename the family to F2; set Finish of type "{t}" to x; set Finish to y', inv)
    over = [o.get("overridden_by") for o in parsed["ops"]]
    assert over == [2, None, 4, None, 6, None]
    assert sum("overridden by a later op" in n for n in parsed["notes"]) == 3
    # a later SCOPED set does not override an earlier unscoped one
    p2 = MF.parse_family_edit(f'set Finish to y; set Finish of type "{t}" to x', inv)
    assert [o.get("overridden_by") for o in p2["ops"]] == [None, None]
    rec, out = _edit(conduit, "rename the type to A; rename the type to B; "
                              "rename the family to F1; rename the family to F2", tmp_path)
    inv2 = MF.inventory_family(out)
    assert (inv2.family_name, inv2.type_names, os.path.basename(out)) == ("F2", ["B"], "F2.rfa")
    assert rec["validation"]["rfa"]["self_checks_ok"]


def test_settle_overrides_keeps_notes_of_the_winning_ops():
    ops = [{"op": "set-param", "param_id": 1, "caption": "W", "raw": "1 in"},
           {"op": "set-param", "param_id": 2, "caption": "H", "raw": "2 in"},
           {"op": "set-param", "param_id": 1, "caption": "W", "raw": "3 in"}]
    notes = MF._settle_overrides(ops, [["W: 1"], ["H: 2"], ["W: 3"]])
    assert notes[1:] == ["H: 2", "W: 3"] and "overridden" in notes[0]
    assert [o.get("overridden_by") for o in ops] == [3, None, None]
    assert MF._effective_ops(ops) == ops[1:]

"""#1023 -- a family edit with a clause the grammar cannot read says so.

``parse_family_edit`` put such clauses into ``parsed["unparsed"]``, which
nothing showed the user: ``set Length; set Material = PVC`` applied Material
and dropped the bare ``set Length`` without a word.  Each such clause is now
a "not applied" note, which ``modify_family`` reports as a degradation; the
family is still delivered with what was read (hard rule 1).

Also the optional nits of the PR #1022 review: a near-miss / ambiguous
caption inside a quoted value is a further edit (refused, as the old split
refused it), and a fragment is read with and without the span's closing
quote.

Run: .venv/bin/python -m pytest tests/test_edit_unparsed_note_1023.py -q
"""
from __future__ import annotations

import pytest

from conftest import HAVE_SCHEMA, context_constants, ladder_constants
from rvt.convert import modify_family as MF
from rvt.frontdoor import edit as E

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


def _inv():
    ps = [{"caption": c, "param_id": 1000 + i, "def_class": "ParamDefString",
           "spec": "autodesk.spec:string-2.0.0", "carrier": "m_str", "current": "", "formula": False}
          for i, c in enumerate(("Width", "Note", "Mark", "Outside Diameter", "Nominal Diameter",
                                 "Material"))]
    return MF.FamilyInventory(path="x.rfa", family_id=1, family_name="F", type_names=["T1"], params=ps)


@pytest.mark.parametrize("text, clause", [
    ("set Width; set Material = PVC", "set Width"),
    ("set Bend: EMT; set Width = 2", "set Bend: EMT"),
    ('also set Note = x\nset Mark = 2', "also set Note = x"),
])
def test_an_unread_clause_is_a_not_applied_note(text, clause):
    r = MF.parse_family_edit(text, _inv())
    assert r["ops"] and r["unparsed"] == [clause]
    assert [n for n in r["notes"] if n.startswith("not applied:")] == [
        n for n in r["notes"] if repr(clause) in n]
    assert any(repr(clause) in n for n in r["notes"])


def test_an_edit_that_reads_whole_has_no_not_applied_note():
    r = MF.parse_family_edit("set Width = 2; set Mark = A", _inv())
    assert not r["unparsed"] and not [n for n in r["notes"] if n.startswith("not applied:")]


@pytest.mark.parametrize("text", [
    'set Note = "x; set Widht 600 mm"',          # near-miss of Width
    'set Note = "x; set Notes x"',                # near-miss of Note
    'set Note = "x; set Diameter 3 in"',          # several parameters contain it
])
def test_a_near_miss_caption_inside_quotes_is_a_further_edit(text):
    with pytest.raises(MF.FamilyEditError, match="runs across a further edit"):
        MF.parse_family_edit(text, _inv())


@pytest.mark.parametrize("text, want", [
    ('set Note = "Hex bolt, set screw included"', "Hex bolt, set screw included"),
    ('set Note = "ready; set up later"', "ready; set up later"),
])
def test_text_inside_quotes_is_still_stored(text, want):
    assert MF.parse_family_edit(text, _inv())["ops"][0]["value"] == want


def test_a_fragment_hidden_by_the_closing_quote_is_a_further_edit():
    with pytest.raises(E.EditParseError, match="runs across a further edit"):
        E.parse_edit_spec('rename 742670 to "x then move 1466502 by 1,0,0 ft"')


@pytest.fixture(scope="module")
def conduit():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    import os
    import shutil
    import tempfile
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t1023_")
    try:
        p = os.path.join(d, "c.rfa")
        F.make_archetype(product="conduit").write(p, validate=False, provenance=False)
        yield p
    finally:
        shutil.rmtree(d, True)


@pytest.fixture(scope="module")
def real_invs(conduit):
    import os
    import shutil
    import tempfile
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t1023b_")
    try:
        p = os.path.join(d, "jb.rfa")
        F.make_archetype(product="junction box").write(p, validate=False, provenance=False)
        yield [MF.inventory_family(conduit), MF.inventory_family(p)]
    finally:
        shutil.rmtree(d, True)


@pytest.mark.parametrize("value", [
    # PR #1024 review: short words were read as near-miss / shared captions on
    # every real family ("in" is inside Nominal Diameter, "with" ~ "width")
    "galvanized; set in place by others", "PVC; set in concrete", "epoxy coated; set with epoxy",
    "x; set it plumb", "surface; set at 48 in AFF", "duplex, set of four", "pad; set on pad",
    "LP-1; set as shown", "ready; set up later", "Hex bolt, set screw included",
])
def test_value_text_is_stored_on_real_generated_families(real_invs, value):
    for inv in real_invs:
        cap = next(p["caption"] for p in inv.params if not p.get("spec") or "string" in p["spec"])
        ops = MF.parse_family_edit(f'set {cap} = "{value}"', inv)["ops"]
        assert [o["value"] for o in ops] == [value], inv.family_name


@pytest.mark.parametrize("value", [
    # PR #1024 review 2: an abbreviation the grammar applies outside quotes
    # (Len -> Length, Out -> Outside Diameter, Mat -> Material) is a further edit
    "PVC; set Len 10 ft", "EMT; set Out 2 in", "HDG; set Mat steel", "x; set Dep 3 in",
    # review 3: inner abbreviations and one-letter keys the grammar applies too
    "see detail; set Ht 18 in", "PVC then set W 2 in",
])
def test_an_abbreviated_caption_inside_quotes_is_a_further_edit(real_invs, value):
    inv = real_invs[0]                                              # the conduit
    with pytest.raises(MF.FamilyEditError, match="runs across a further edit"):
        MF.parse_family_edit(f'set Finish = "{value}"', inv)


@pytest.mark.parametrize("caps, text", [
    # PR #1024 review 3: unit tokens inside a caption ("Rated kVA", "...Rating kA")
    (("Mark", "Rated kVA"), "set Mark = 'T-1; set kVA 75 nominal'"),
    (("Mark", "Interrupting kA"), "set Mark = 'P-1; set kA 22 sym'"),
    (("Mark", "ShortCircuitRatingkA"), "set Mark = 'MCB; set kA 65 kA'"),
    (("Mark", "Height", "Width"), "set Mark = 'B-1; set Ht 4 ft'"),
    (("Mark", "Width", "Depth"), "set Mark = 'B-1; set W 4 ft'"),
    # review 4: a caption that IS a function word, or starts with one
    (("Mark", "A", "B"), "set Mark = 'see note; set A 600 mm'"),
    (("Mark", "A", "B"), "set Mark = 'see note then set a 2 ft'"),
    (("Mark", "On"), "set Mark = 'x; set On 3 ft'"),
    (("Mark", "No. of Poles"), "set Mark = 'x; set no 3 poles'"),
    (("Mark", "Up Light"), "set Mark = 'x; set Up 3 ft'"),
])
def test_a_short_key_naming_a_parameter_inside_quotes_is_a_further_edit(caps, text):
    ps = [{"caption": c, "param_id": 1000 + i, "def_class": "ParamDefString",
           "spec": "autodesk.spec:string-2.0.0", "carrier": "m_str", "current": "", "formula": False}
          for i, c in enumerate(caps)]
    inv = MF.FamilyInventory(path="x.rfa", family_id=1, family_name="F", type_names=["T1"], params=ps)
    with pytest.raises(MF.FamilyEditError, match="runs across a further edit"):
        MF.parse_family_edit(text, inv)


def test_a_function_word_caption_outside_quotes_still_applies():
    ps = [{"caption": c, "param_id": 1000 + i, "def_class": "ParamDefString",
           "spec": "autodesk.spec:string-2.0.0", "carrier": "m_str", "current": "", "formula": False}
          for i, c in enumerate(("Mark", "A", "On"))]
    inv = MF.FamilyInventory(path="x.rfa", family_id=1, family_name="F", type_names=["T1"], params=ps)
    ops = MF.parse_family_edit("set Mark = 'see note'; set A 600 mm; set On 3 ft", inv)["ops"]
    assert [o["caption"] for o in ops] == ["Mark", "A", "On"]


def test_the_note_reaches_the_delivered_records_degradations(conduit, tmp_path):
    rec = MF.modify_family(conduit, "set Length; set Material = PVC", str(tmp_path))
    assert rec["files"]["rfa"]                                     # still delivered
    assert any(d.startswith("not applied: 'set Length'") for d in rec["degradations"])

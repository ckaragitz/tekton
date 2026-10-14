"""#1025 -- a caption word glued to digits ("AT1", "IN1") names its parameter
inside a quoted value, and the family-edit route's "N clause(s) NOT applied"
status and the "(+N more ...)" caveat line are pinned.

PR #1024 left ``_split_camel`` splitting digit -> Upper ("1AT" -> "1 AT") but
never letter -> digit, so with a caption "AT1" an edit ``set AT 5 A`` inside a
quoted value was stored as text although the grammar applies it unquoted.
The boundary that stays (record ``1025-edit-digit-glued.md``): an all-caps
caption glued to a word ("ONDELAY") cannot be told from a word that merely
starts with a function word ("NOMINAL" holds "NO") without a dictionary, so
``set ON ...`` inside quotes stays text there.

Run: .venv/bin/python -m pytest tests/test_edit_digit_glued_1025.py -q
"""
from __future__ import annotations

import importlib.util
import os

import pytest

from conftest import HAVE_SCHEMA, context_constants, ladder_constants
from rvt.convert import modify_family as MF

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    return lambda: dict(ladder_constants(), **context_constants())


def _inv(*caps):
    ps = [{"caption": c, "param_id": 1000 + i, "def_class": "ParamDefString",
           "spec": "autodesk.spec:string-2.0.0", "carrier": "m_str", "current": "", "formula": False}
          for i, c in enumerate(caps)]
    return MF.FamilyInventory(path="x.rfa", family_id=1, family_name="F", type_names=["T1"], params=ps)


@pytest.mark.parametrize("text, words", [
    ("AT1", "AT 1"), ("IN1", "IN 1"), ("Rating IN1", "Rating IN 1"), ("AN2 Rating", "AN 2 Rating"),
    ("1AT", "1 AT"), ("ONDelay", "ON Delay"), ("PanelName", "Panel Name"),
])
def test_split_camel(text, words):
    assert MF._split_camel(text) == words


@pytest.mark.parametrize("caps, key", [
    (("Mark", "AT1"), "AT"), (("Mark", "IN1"), "IN"), (("Mark", "Rating IN1"), "IN"),
    (("Mark", "AN2 Rating"), "AN"),
])
def test_a_digit_glued_caption_word_inside_quotes_is_a_further_edit(caps, key):
    with pytest.raises(MF.FamilyEditError, match="runs across a further edit"):
        MF.parse_family_edit(f"set Mark = 'see note; set {key} 5 A'", _inv(*caps))
    # unquoted, the same clause applies to that parameter (unchanged)
    ops = MF.parse_family_edit(f"set Mark = 'see note'; set {key} 5 A", _inv(*caps))["ops"]
    assert [o["caption"] for o in ops] == ["Mark", caps[1]]


@pytest.mark.parametrize("caps, text", [
    # PR #1074 review: a digit-bearing key several captions share, which old and main
    # refused, must not be stored as text -- the caption is also read as written
    (("Mark", "L1 Current", "L1 Voltage"), 'set Mark = "see E-101; set L1 30 A"'),
    (("Mark", "A1 Width", "A1 Depth"), "set Mark = 'see note; set A1 5 mm'"),
    (("Mark", "CB1 Rating", "CB1 Frame"), 'set Mark = "spare then set CB1 225 A"'),
    (("Mark", "Lamp1 Type", "Lamp1 Watts"), "set Mark = 'x; set Lamp1 LED'"),
    (("Mark", "Upstream Pipe2 Diameter", "Downstream Pipe2 Diameter"), "set Mark = 'x; set Pipe2 4 in'"),
])
def test_a_shared_digit_bearing_key_inside_quotes_is_a_further_edit(caps, text):
    with pytest.raises(MF.FamilyEditError, match="runs across a further edit"):
        MF.parse_family_edit(text, _inv(*caps))


def test_the_trade_off_prose_that_starts_a_digit_caption_is_refused():
    # "in" IS the word that starts "IN1": refused (recoverable -- close the quote or
    # use a JSON op), as main refuses it with a spaced "IN 1" caption
    with pytest.raises(MF.FamilyEditError, match="runs across a further edit"):
        MF.parse_family_edit("set Mark = 'PVC; set in concrete'", _inv("Mark", "IN1"))


def test_the_all_caps_glued_boundary_stays_text():
    # 'ON' inside "ONDELAY" cannot be told from 'NO' inside "NOMINAL" without a
    # dictionary: known residue (the old split wrote ONDELAY here, the meant
    # parameter; it wrote NOMINAL for 'no', a mis-target) -- tracked in the record
    ops = MF.parse_family_edit("set Mark = 'see note; set ON 5 s'", _inv("Mark", "ONDELAY"))["ops"]
    assert [o["value"] for o in ops] == ["see note; set ON 5 s"]


def test_prose_stays_text():
    for v in ("PVC; set in concrete", "x; set it plumb", "LP-1; set as shown"):
        ops = MF.parse_family_edit(f'set Mark = "{v}"', _inv("Mark", "AT1", "Material"))["ops"]
        assert [o["value"] for o in ops] == [v]


def _route_cli():
    spec = importlib.util.spec_from_file_location("_route_cli_1025", os.path.join(ROOT, "tools", "route.py"))
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    return cli


def test_the_text_output_says_how_many_caveats_it_cut(capsys):
    from rvt.frontdoor.router import RouteResult
    res = RouteResult(ok=True, status="OK", caveats=[f"c{i}" for i in range(11)])
    _route_cli()._print_result(res)
    out = capsys.readouterr().out
    assert out.count("  caveat    : c") == 8
    assert "(+3 more in route.json / ROUTE.md)" in out
    res = RouteResult(ok=True, status="OK", caveats=[f"c{i}" for i in range(8)])
    _route_cli()._print_result(res)
    assert "more in route.json" not in capsys.readouterr().out


@pytest.fixture(scope="module")
def conduit():
    if not HAVE_SCHEMA:
        pytest.skip("class schema cache absent")
    import shutil
    import tempfile
    from rvt.famgen import factory as F
    d = tempfile.mkdtemp(prefix="t1025_")
    try:
        p = os.path.join(d, "c.rfa")
        F.make_archetype(product="conduit").write(p, validate=False, provenance=False)
        yield p
    finally:
        shutil.rmtree(d, True)


def test_the_route_status_counts_clauses_not_applied(conduit, tmp_path):
    from rvt.frontdoor import router as R
    prompt = "set Length; set Bend: EMT; also set Finish x; set Width; set Material = PVC"
    res = R.route({"rfa": conduit, "prompt": prompt}, "rfa", out=str(tmp_path / "o"))
    assert res.ok and os.path.isfile(res.files["rfa"])                     # still delivered
    assert "4 clause(s) NOT applied (see caveats)" in res.status, res.status
    assert sum(c.startswith("not applied:") for c in res.caveats) == 4
    res = R.route({"rfa": conduit, "prompt": "set Material = PVC"}, "rfa", out=str(tmp_path / "p"))
    assert res.ok and "NOT applied" not in res.status

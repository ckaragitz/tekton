"""test_release_ctx_refusal.py -- ``rvt.frontdoor.release_ctx`` keeps its two
promises for a file it cannot even PROBE (issue #535, Refs #518 / #70 / #116):

* ``host_release_context(p)`` raises ONE type, ``UnreadableHost`` (a
  ``ReleaseContextError`` carrying ``.path``, ``.why`` and the layer's own
  error as ``__cause__``) for a text file named ``.rvt``, a copy truncated
  mid-sector, and a 2025/2024 host whose ``Formats/Latest`` does not parse --
  never the raw ``OleFileError`` / ``ParseError`` / ``OSError``;
* ``enter_host_release(stack, p)`` therefore returns its refusal NOTE for
  every one of them and never raises;
* a setup failure after the first ``swap()`` restores every module constant
  (nothing leaks into the next job of the process);
* the three readable pinned bases behave exactly as before (controls), and a
  host with no ``BasicFileInfo`` is still readable (the schema signature
  detects its release);
* the callers rely on it: the front door's ``--rvt --edit`` route answers a
  damaged-schema host with its normal FAILED envelope (exit 3, ONE JSON,
  empty stderr), ``rvt_edit_text.py`` refuses in one line (exit 2: the
  container is opened before the release is entered, as ``rvt_selfcheck``
  does, so a text file is ONE line; a damaged schema is the warning + the
  walker's line), and
  ``rvt_selfcheck.py`` -- its interim guard deleted -- still reaches FAIL.

Damaged copies are built in-test from the tracked pins; nothing is checked in.
Run: .venv/bin/python -m pytest tests/test_release_ctx_refusal.py -q
"""
from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import (CERTIFIED_YEARS, FOREIGN, FOREIGN_FIRST, load_tool, native_constants,   # noqa: E402
                      pinned_base, rewrite_stream, truncated_copy, zero_schema_bytes)
from rvt import mutate as MU                                   # noqa: E402
from rvt import versions as V                                  # noqa: E402
from rvt.frontdoor import release_ctx as RC                    # noqa: E402
from rvt.frontdoor import standalone as SA                     # noqa: E402
from rvt.genesis import skeleton as GSK                        # noqa: E402

LEVEL_EDIT = "set level 1351691 elevation to -9 ft"                 # GEN B1 - Basement, on every pin
OLD_NAME, NEW_NAME = "GEN B1 - Basement", "OUR B1 - Basement"      # same length
pytestmark = pytest.mark.usefixtures("no_release_leak")             # foreign pins run first: a leak breaks the native run


def _constants() -> dict:
    """Everything a leaked release context would leave behind: conftest's ``native_constants()`` plus the
    refusal registry and the mutate / skeleton / standalone names ``host_release_context`` swaps."""
    return dict(native_constants(), refused=dict(RC._REFUSED),
                mu=(MU.CLASS_ELEMENT_HEADER, MU.CLASS_SWALL, MU.CLASS_FAMILY_INSTANCE),
                gsk=(GSK.minimal_history, GSK.minimal_elemtable, sorted(GSK._SCHEMA_CACHE)),
                sa=(SA.bundled_base_path, SA.family_instance_template, dict(SA._SCHEMA_STATE)))


@pytest.fixture
def release_leak_extra():
    """``no_release_leak`` watches the swapped engine names too, not the framing table alone."""
    return _constants


@pytest.fixture(scope="module")
def bad(tmp_path_factory):
    """name -> (path, expected __cause__ type name) of every unreadable host."""
    d = tmp_path_factory.mktemp("bad")
    any_pin = pinned_base(CERTIFIED_YEARS[0])
    out = {}
    text = d / "text.rvt"
    text.write_text("this is not a Revit file\n" * 8, encoding="utf-8")
    out["text"] = (str(text), "NotOleFileError")
    out["trunc4k"] = (truncated_copy(any_pin, d / "trunc4k.rvt", 4096), "OleFileError")
    if FOREIGN:                      # a NATIVE host never parses its schema to enter (nothing to swap)
        pin = pinned_base(FOREIGN[0])
        out["schema_dmg"] = (rewrite_stream(pin, d / "schema_dmg.rvt", "Formats/Latest", zero_schema_bytes), "ParseError")
        out["schema_gone"] = (rewrite_stream(pin, d / "schema_gone.rvt", "Formats/Latest", None), "OSError")
    return out


@pytest.fixture(scope="module")
def schema_dmg(bad):
    if "schema_dmg" not in bad:
        pytest.skip("no certified foreign-release pin")
    return bad["schema_dmg"][0]


# ---------------------------------------------------------------------------
# the helper itself
# ---------------------------------------------------------------------------

def test_unreadable_hosts_raise_one_typed_exception(bad):
    for name, (path, cause) in bad.items():
        with pytest.raises(RC.UnreadableHost) as ei:
            with RC.host_release_context(path):
                pytest.fail(f"{name}: entered a context on an unreadable host")
        e = ei.value
        assert isinstance(e, RC.ReleaseContextError), name          # `except ReleaseContextError` callers keep working
        assert e.path == path and "\n" not in e.why, name            # .path: the path as handed in, for callers
        assert type(e.__cause__).__name__ == cause and cause in e.why, (name, e.why)
        assert str(e) == f"{path}: {e.why}"
        # what could not be read, then the layer's error as a CLAUSE (#574/#587)
        assert e.why == f"{e.what} ({RC.cause_clause(e.__cause__)})" and "(" not in e.what, (name, e.why)


def test_cause_clause_is_type_plus_words_the_error_itself_untouched():
    """``.why`` / the note carry ``Type: <words>``: the schema parser's byte
    dump is dropped by shape, long words are cut on a boundary, and the
    exception object is never edited (``rvt._clause``, #574/#587)."""
    from rvt import schema
    from rvt._clause import CAUSE_MAX
    short = ValueError("Partitions/20: walker errors ['no trailer']")
    assert RC.cause_clause(short) == f"ValueError: {short}"            # fits: verbatim
    assert RC.cause_clause(OSError()) == "OSError"                     # no message: the type alone
    # a real parser error on damaged bytes: `parse error at 0x..: <words> @0x..: <24 hex> | <40 hex>`
    with pytest.raises(schema.ParseError) as ei:
        schema.parse(bytes(range(1, 200)))
    dumped = str(ei.value)
    assert " | " in dumped and len(dumped) > CAUSE_MAX                 # the dump IS there on the exception ...
    clause = RC.cause_clause(ei.value)
    assert clause == "ParseError: " + dumped[:dumped.index(" @0x")]    # ... and only its words ride
    assert str(ei.value) == dumped                                     # the error itself untouched
    # the engine's longest WORDED one-sentence error rides whole (#569's)
    with pytest.raises(schema.ParseError) as ei:
        schema.parse(b"")
    assert RC.cause_clause(ei.value) == f"ParseError: {ei.value}" \
        and str(ei.value).endswith("(an empty or truncated schema stream)")
    # longer words: one line, cut on a word boundary within the budget, `...` marks it
    wordy = RuntimeError("walker errors " + " ".join(f"['no trailer for block at {n}']" for n in range(40))
                         + "\nsecond line")
    clause = RC.cause_clause(wordy)
    assert clause.endswith("...") and "\n" not in clause and len(clause) <= len("RuntimeError: ") + CAUSE_MAX
    kept = clause[len("RuntimeError: "):-3]
    assert str(wordy).startswith(kept) and str(wordy)[len(kept)] == " "


def test_the_read_side_rung_names_its_cause_by_the_same_clause(schema_dmg):
    """``global_framing.enter_own_release``'s lenient rung relays the schema
    error through ``cause_clause`` too: no byte dump in the note the
    instruments print / the front door's ``read side:`` (#587)."""
    from rvt import global_framing as GF
    with pytest.raises(Exception) as ei:              # the very error the rung swallows
        GF.schema_of(schema_dmg)
    with contextlib.ExitStack() as stack:
        rung = GF.enter_own_release(stack, schema_dmg)
    assert rung == (f"own schema unreadable ({RC.cause_clause(ei.value)}); checked against the pinned "
                    f"Revit {FOREIGN[0]} framing table (the release BasicFileInfo declares)")
    assert "@0x" not in rung and "..." not in rung and " @0x" in str(ei.value)


def test_enter_host_release_returns_its_note_never_raises(bad):
    for name, (path, cause) in bad.items():
        lead = f"no release context for {os.path.basename(path)}: "
        with contextlib.ExitStack() as stack:
            note = RC.enter_host_release(stack, path)
            assert RC.active_release() is None, name
            # a caller composing its own sentence reads the typed error back
            # while its stack is open: these hosts could not even be probed
            e = RC.refused(path)
            assert isinstance(e, RC.UnreadableHost) and note == lead + e.why, name
        assert RC.refused(path) is None, name                          # gone with the caller's stack
        # the host by NAME, once: the caller reports the path it handed in (#574)
        assert note.startswith(lead) and cause in note and os.path.dirname(path) not in note, (name, note)


def test_a_release_we_cannot_author_into_is_refused_but_not_unreadable(monkeypatch):
    """An uncertified release: the note says so and ``refused`` hands back a
    plain ``ReleaseContextError`` -- context behind a caller's own finding,
    not the reason it leads with."""
    if not FOREIGN:
        pytest.skip("no certified foreign-release pin")
    year, path = FOREIGN[0], pinned_base(FOREIGN[0])
    monkeypatch.setitem(V.KNOWN_RELEASES, year,
                        dataclasses.replace(V.KNOWN_RELEASES[year], creation_certified=False))
    with contextlib.ExitStack() as stack:
        note = RC.enter_host_release(stack, path)
        e = RC.refused(path)
        assert type(e) is RC.ReleaseContextError and note == f"no release context for {os.path.basename(path)}: {e}"
        assert f"Revit {year} is not a certified creation release" in note and RC.active_release() is None
    assert RC.refused(path) is None


@pytest.mark.parametrize("year", FOREIGN_FIRST)
def test_readable_pins_are_unchanged_controls(year):
    with contextlib.ExitStack() as stack:
        assert RC.enter_host_release(stack, pinned_base(year)) is None
        assert RC.active_release() == (None if year == V.LATEST_RELEASE else year)


@pytest.mark.parametrize("year", FOREIGN_FIRST)
def test_a_host_without_basicfileinfo_is_still_readable(year, tmp_path):
    """``detect_release`` falls back to the schema signature; the context's
    identity strings come from OUR bundled base, never the host (rule 6)."""
    host = rewrite_stream(pinned_base(year), tmp_path / "no_bfi.rvt", "BasicFileInfo", None)
    with RC.host_release_context(host) as info:
        if year == V.LATEST_RELEASE:
            assert info is None
        else:
            assert info["release"] == year and info["base"] != os.path.abspath(host)


def test_setup_failure_after_the_first_swap_restores_everything(monkeypatch):
    if not FOREIGN:
        pytest.skip("no certified foreign-release pin")
    calls = {"n": 0}
    orig = RC._by_name

    def by_name_failing_once(schema, name):
        calls["n"] += 1
        if calls["n"] == 3:                       # two mutate constants already swapped
            raise RC.ReleaseContextError("class 'X' is missing (injected once)")
        return orig(schema, name)

    monkeypatch.setattr(RC, "_by_name", by_name_failing_once)
    before = _constants()
    with pytest.raises(RC.ReleaseContextError, match="injected once"):
        with RC.host_release_context(pinned_base(FOREIGN[0])):
            pytest.fail("entered despite the setup failure")
    assert _constants() == before                 # main leaked MU.CLASS_ELEMENT_HEADER here
    with RC.host_release_context(pinned_base(FOREIGN[0])) as info:      # and the next job still works
        assert info["release"] == FOREIGN[0] and MU.CLASS_ELEMENT_HEADER != before["mu"][0]


# ---------------------------------------------------------------------------
# the callers that rely on it
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def frontdoor_cli():
    return load_tool("frontdoor")


@pytest.fixture(scope="module")
def edit_text():
    return load_tool("rvt_edit_text")


@pytest.fixture(scope="module")
def selfcheck():
    return load_tool("rvt_selfcheck")


def test_frontdoor_edit_route_answers_a_damaged_schema_host_with_its_failed_envelope(
        schema_dmg, frontdoor_cli, tmp_path, capsys):
    import rvt.frontdoor as FD
    res = FD.author(rvt=schema_dmg, edit=LEVEL_EDIT, out=str(tmp_path / "api"))
    assert res.route == "rvt" and res.ok is False and res.status.startswith("FAILED"), res.status
    # the host could not even be probed: that IS the reason (the sentence's
    # shape is test_edit_status's); the whole note rides in errors[1] (#574)
    assert res.errors and "Formats/Latest" in res.errors[0] \
        and "(no release context for schema_dmg.rvt: " in res.errors[1]
    assert not res.files and os.path.isfile(res.manifest_paths["json"])
    capsys.readouterr()
    rc = frontdoor_cli.main(["author", "--rvt", schema_dmg, "--edit", LEVEL_EDIT,
                            "--out", str(tmp_path / "cli"), "--json"])
    cap = capsys.readouterr()
    assert rc == frontdoor_cli.EX_INCOMPLETE == 3
    assert cap.err == ""                                   # no traceback, no chatter
    doc = json.loads(cap.out)                              # ONE json document, nothing else
    assert doc["ok"] is False and (doc["status"], doc["errors"]) == (res.status, res.errors)


def test_rvt_edit_text_refuses_in_one_line(bad, schema_dmg, edit_text, tmp_path, capsys):
    rc = edit_text.main([schema_dmg, "--old", OLD_NAME, "--new", NEW_NAME, "--utf16",
                         "-o", str(tmp_path / "never.rvt")])
    cap = capsys.readouterr()
    assert rc == 2 and not os.path.exists(tmp_path / "never.rvt")
    warning, error = cap.err.splitlines()                  # exactly two lines, no traceback
    assert warning.startswith("warning: no release context for ") and "Formats/Latest" in warning
    assert error.startswith("ERROR: input partition does not walk cleanly: ValueError: ")
    for name in ("text", "trunc4k"):                    # not even a container: ONE line, before any release entry
        rc = edit_text.main([bad[name][0], "--old", OLD_NAME, "--new", NEW_NAME, "--utf16",
                             "-o", str(tmp_path / "never.rvt")])
        (only_line,) = capsys.readouterr().err.splitlines()
        assert rc == 2 and only_line.startswith("ERROR: cannot open as an .rvt container: "), name


def test_rvt_selfcheck_reaches_its_verdict_without_a_local_guard(schema_dmg, selfcheck, tmp_path, capsys):
    rc = selfcheck.main([schema_dmg, "--json", str(tmp_path / "sc.json")])
    cap = capsys.readouterr()
    assert rc == 1 and "Traceback" not in cap.err + cap.out
    assert cap.err.startswith("warning: no release context for ") and "Formats/Latest" in cap.err
    with open(tmp_path / "sc.json", encoding="utf-8") as fh:
        rep = json.load(fh)
    assert rep["verdict"] == "FAIL" and rep["release_note"].startswith("no release context for ")
    assert rep["walker"]["walker_errors"] == 1

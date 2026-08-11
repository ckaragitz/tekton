"""test_rvt_edit_refusal.py -- ``tools/rvt_edit.py`` (shipped as the tekton-edit
and tekton-native ``rvt_edit.py`` scripts; ``--json`` is what ``go edit`` runs)
refuses a file it cannot open or plan at its ONE open boundary, on both of
its paths, instead of the raising layer's traceback (issue #560, Refs #535 /
#70 / #111):

* plain (human) mode: the release warning when there is one, then ONE
  ``[rvt_edit] FAILED (...)`` line on stderr -- ``cannot open as an .rvt
  container: ...`` and exit 2 for a text file named ``.rvt`` / a copy cut
  mid-sector (``rvt_edit_text`` / ``rvt_selfcheck``'s words and code),
  ``cannot open/plan <basename>: <Exc>: <msg>`` and exit 1 for a container
  that does not walk or parse (a 64 KiB truncation, a 2025/2024 host whose
  ``Formats/Latest`` is damaged, a host without ``Global/ElemTable`` -- the
  container is probed only after the open failed, so "which sentence" is
  decided as the sibling CLIs decide it, not by exception type; the input
  by NAME like every other door, #573/#587: its path is ``input.path`` /
  argv); an impossible edit is ONE line too;
* ``--json``: exactly ONE ``{"ok": false, "error": "<one sentence>", ...}``
  object on stdout with the keys the success shape uses (``command``,
  ``input``, ``release``, ``release_note`` when there is one, ``seconds``),
  the same exit codes, and an EMPTY stderr;
* controls: ``info`` and ``set-level`` on the three tracked, certified pins
  answer / write exactly as before (exit 0, empty stderr, own release kept).

Damaged copies are built in-test from the tracked pins; nothing is checked in.
Run: .venv/bin/python -m pytest tests/test_rvt_edit_refusal.py -q
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from conftest import CERTIFIED_YEARS, load_tool, pinned_base    # noqa: E402
from rvt import partitions as P                                # noqa: E402
from rvt import versions as V                                  # noqa: E402
from rvt.frontdoor import release_ctx as RC                    # noqa: E402

NATIVE_LAST = sorted(CERTIFIED_YEARS, key=lambda y: y == V.LATEST_RELEASE)   # a leaked context would break the native run
FOREIGN = [y for y in CERTIFIED_YEARS if y != V.LATEST_RELEASE]
LEVEL_ID = 1351691                                     # "GEN B1 - Basement", on every pin
SET_LEVEL = ["set-level", "--id", str(LEVEL_ID), "--elevation-ft", "5"]
NO_RELEASE = {"input": None, "output": None, "opens_in": None, "line": None}
NOT_A_CONTAINER = "cannot open as an .rvt container: "


@pytest.fixture(autouse=True)
def _no_leak():
    before = ({k: getattr(P, k) for k in V.framing_table(V.LATEST_RELEASE)}, RC.active_release())
    assert before[1] is None
    yield
    assert ({k: getattr(P, k) for k in V.framing_table(V.LATEST_RELEASE)}, RC.active_release()) == before


@pytest.fixture(scope="module")
def edit():
    return load_tool("rvt_edit")


def _rewrite_stream(src: str, dst: str, name: str, damage) -> str:
    """``src`` re-emitted as ``dst`` with stream ``name``'s RAW bytes replaced
    by ``damage(raw)`` (dropped when ``damage`` is None) -- every other entry
    byte-identical.  (A copy of test_release_ctx_refusal's helper; #579 folds
    these into conftest.)"""
    from rvt.cfb_writer import write_cfb
    from rvt.roundtrip import read_entries
    entries = []
    for e in read_entries(src):
        if e.entry_type == "stream" and e.path == name:
            if damage is None:
                continue
            e = dataclasses.replace(e, data=damage(e.data))
        entries.append(e)
    write_cfb(dst, entries)
    return dst


@pytest.fixture(scope="module")
def bad(tmp_path_factory):
    """name -> (path, exit code, error prefix, source year, warned?) of every
    input the tool must refuse; ``warned`` = the release entry has a note for
    it (plain mode prints it first; ``--json`` carries it as release_note)."""
    d = tmp_path_factory.mktemp("bad560")
    out = {}
    text = d / "text.rvt"
    text.write_text("this is not a Revit file\n" * 8, encoding="utf-8")
    out["text"] = (str(text), 2, NOT_A_CONTAINER, None, True)
    with open(pinned_base(CERTIFIED_YEARS[0]), "rb") as fh:
        (d / "trunc4k.rvt").write_bytes(fh.read(4096))
    out["trunc4k"] = (str(d / "trunc4k.rvt"), 2, NOT_A_CONTAINER, None, True)
    for year in CERTIFIED_YEARS:                 # still a container; its partitions / schema are cut
        p = d / f"trunc64k_{year}.rvt"
        with open(pinned_base(year), "rb") as fh:
            p.write_bytes(fh.read(65536))
        out[f"trunc64k_{year}"] = (str(p), 1, f"cannot open/plan {p.name}: ", year, year != V.LATEST_RELEASE)
    # a container that opens, enters its release fine, but lacks the element table:
    # "cannot open/plan" (1), NOT "not a container" (2) -- although olefile says OSError for it
    year = CERTIFIED_YEARS[-1]
    p = _rewrite_stream(pinned_base(year), str(d / "no_elemtable.rvt"), "Global/ElemTable", None)
    out["no_elemtable"] = (p, 1, "cannot open/plan no_elemtable.rvt: OSError: ", year, False)
    if FOREIGN:                                  # a NATIVE host never parses its schema to enter (nothing to swap)
        p = _rewrite_stream(pinned_base(FOREIGN[0]), str(d / "schema_dmg.rvt"), "Formats/Latest",
                            lambda raw: raw[:2000] + bytes(64) + raw[2064:])       # #518's repro
        out["schema_dmg"] = (p, 1, "cannot open/plan schema_dmg.rvt: ValueError: unexpected Partitions header",
                             FOREIGN[0], True)
    return out


# ---------------------------------------------------------------------------
# the refusals
# ---------------------------------------------------------------------------

def test_plain_mode_refuses_in_one_or_two_lines_never_a_traceback(bad, edit, capsys):
    for name, (path, rc, prefix, _year, warned) in bad.items():
        assert edit.main([path, "info"]) == rc, name
        cap = capsys.readouterr()
        assert cap.out == "" and "Traceback" not in cap.err, name
        lines = cap.err.splitlines()
        assert len(lines) == 1 + warned, (name, lines)
        if warned:
            assert lines[0].startswith(f"[rvt_edit] warning: no release context for {os.path.basename(path)}: "), (name, lines[0])
        assert lines[-1].startswith(f"[rvt_edit] FAILED ({prefix}") and lines[-1].endswith(")"), (name, lines[-1])
        assert os.path.dirname(path) not in cap.err, name       # the input by NAME on every line (argv has the path)
    assert (edit.EX_OK, edit.EX_FAIL, edit.EX_NOT_RVT) == (0, 1, 2) and "Exit codes:" in edit.__doc__


def test_json_mode_refuses_with_one_object_and_an_empty_stderr(bad, edit, capsys):
    for name, (path, rc, prefix, year, warned) in bad.items():
        assert edit.main([path, "info", "--json"]) == rc, name
        cap = capsys.readouterr()
        assert cap.err == "", (name, cap.err)                    # no warning line, no traceback
        doc = json.loads(cap.out)                                # exactly ONE json document
        assert doc["ok"] is False and doc["command"] == "info", name
        assert doc["error"].startswith(prefix) and "\n" not in doc["error"], (name, doc["error"])
        assert os.path.dirname(path) not in doc["error"], name          # by NAME; the path is input.path:
        assert doc["input"] == {"path": os.path.abspath(path)} and isinstance(doc["seconds"], float), name
        assert ("release_note" in doc) is warned, name
        if warned:
            assert doc["release_note"].startswith(f"no release context for {os.path.basename(path)}: "), name
        assert doc["release"] == (NO_RELEASE if rc == 2 else {**NO_RELEASE, "input": year,
                                                              "opens_in": doc["release"]["opens_in"]}), name
        if rc == 1:
            assert doc["release"]["opens_in"].startswith(f"Revit {year} "), name


@pytest.mark.parametrize("name", ["text", "schema_dmg"])
def test_a_write_verb_on_an_unusable_input_refuses_the_same_way_and_writes_nothing(name, bad, edit, tmp_path, capsys):
    if name not in bad:
        pytest.skip("no certified foreign-release pin")
    path, rc, prefix, _year, _warned = bad[name]
    out = tmp_path / "never.rvt"
    assert edit.main([path, *SET_LEVEL, "-o", str(out), "--json"]) == rc
    cap = capsys.readouterr()
    doc = json.loads(cap.out)
    assert cap.err == "" and doc["ok"] is False and doc["error"].startswith(prefix)
    assert doc["command"] == "set-level" and "output" not in doc
    assert edit.main([path, *SET_LEVEL, "-o", str(out)]) == rc
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err.splitlines()[-1].startswith(f"[rvt_edit] FAILED ({prefix}")
    assert "written" not in cap.err and not out.exists()


def test_an_impossible_edit_is_one_line_in_plain_mode_too(edit, tmp_path, capsys):
    pin = pinned_base(CERTIFIED_YEARS[0])
    out = tmp_path / "never.rvt"
    assert edit.main([pin, "set-level", "--id", "999999999", "--elevation-ft", "5", "-o", str(out)]) == 1
    cap = capsys.readouterr()
    (line,) = cap.err.splitlines()                               # ONE line, no traceback
    assert line.startswith("[rvt_edit] FAILED (set-level impossible: ") and "999999999" in line
    assert cap.out == "" and not out.exists()
    assert edit.main([pin, "deps", "--id", "999999999"]) == 1
    (line,) = capsys.readouterr().err.splitlines()
    assert line.startswith("[rvt_edit] FAILED (deps impossible: ") and "999999999" in line


# ---------------------------------------------------------------------------
# controls: the three readable pins behave exactly as before
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", NATIVE_LAST)
def test_info_on_a_readable_pin_is_unchanged(year, edit, capsys):
    pin = pinned_base(year)
    assert edit.main([pin, "info"]) == 0
    cap = capsys.readouterr()
    assert cap.err == "" and any(lv["id"] == LEVEL_ID for lv in json.loads(cap.out)["levels"])
    assert edit.main([pin, "info", "--json"]) == 0
    cap = capsys.readouterr()
    doc = json.loads(cap.out)
    assert cap.err == "" and doc["ok"] is True and "error" not in doc and "release_note" not in doc
    assert doc["release"]["input"] == year and any(lv["id"] == LEVEL_ID for lv in doc["levels"])


@pytest.mark.parametrize("year", NATIVE_LAST)
def test_set_level_on_a_readable_pin_is_unchanged(year, edit, tmp_path, capsys):
    pin = pinned_base(year)
    out = tmp_path / f"j{year}.rvt"
    assert edit.main([pin, *SET_LEVEL, "-o", str(out), "--json"]) == 0
    cap = capsys.readouterr()
    doc = json.loads(cap.out)
    assert cap.err == "" and doc["ok"] is True and doc["gates"]["hard_gates_passed"] is True
    assert doc["output"]["path"] == str(out) and doc["release"]["input"] == doc["release"]["output"] == year
    assert doc["report"]["replaced"] == [[102, LEVEL_ID]] and V.detect_release(str(out)) == year
    out = tmp_path / f"p{year}.rvt"
    assert edit.main([pin, *SET_LEVEL, "-o", str(out)]) == 0
    cap = capsys.readouterr()
    assert cap.err == "" and f"written: {out} (" in cap.out and '"walker_errors": 0' in cap.out
    assert V.detect_release(str(out)) == year

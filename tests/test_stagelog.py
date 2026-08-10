"""test_stagelog.py -- the ONE quiet-stage log helper every front-door route
shares (src/rvt/frontdoor/stagelog.py, issue #373).

The contract, checked on the helper itself (the three routes' wrappers are
covered where they live: tests/test_frontdoor.py section 8b for build.log /
edit.log, tests/test_router.py for route.log):

* not quiet -> a null context: live stdout, no file;
* quiet -> ``<out_dir>/<name>`` opened at CALL time, ``on_open(path)`` told,
  the block's prints land in the file (utf-8, odd code points escaped, never
  raised), nothing on the caller's stdout;
* an unopenable log -- a read-only dir (OSError) or a path the standalone
  tripwire's audit hook refuses from inside ``open()`` (StandaloneError, not
  an OSError: the #374 review's edge) -- still runs the block, tells
  ``on_degrade`` ONE note, writes no file and leaks nothing to stdout.

Fresh-clone safe (stdlib + the package; no samples, no bases).
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor.stagelog import stage_stdout      # noqa: E402


def _sinks():
    opened, notes = [], []
    return opened, notes, {"on_open": opened.append, "on_degrade": notes.append}


def test_verbose_is_a_null_context(tmp_path, capsys):
    opened, notes, cb = _sinks()
    with stage_stdout(str(tmp_path), "x.log", quiet=False, **cb):
        print("[fake] live progress")
    assert "[fake] live progress" in capsys.readouterr().out
    assert opened == [] and notes == [] and not (tmp_path / "x.log").exists()


def test_quiet_streams_the_block_into_the_named_file(tmp_path, capsys):
    opened, notes, cb = _sinks()
    log_p = str(tmp_path / "x.log")
    with stage_stdout(str(tmp_path), "x.log", quiet=True, **cb):
        print("[fake] stage 1")
        assert os.path.isfile(log_p)                     # opened at call time, not at exit
        with open(log_p, encoding="utf-8") as fh:        # line-buffered: tail-able mid-run
            assert "[fake] stage 1" in fh.read()
        print("[fake] lone surrogate \udcff survives")   # backslashreplace, never UnicodeEncodeError
    assert opened == [log_p] and notes == []
    assert capsys.readouterr().out == ""
    with open(log_p, encoding="utf-8") as fh:
        text = fh.read()
    assert "[fake] stage 1\n" in text and "\\udcff survives" in text


def test_readonly_dir_degrades_to_an_unlogged_run(tmp_path, capsys):
    ro = tmp_path / "ro"
    ro.mkdir()
    ro.chmod(0o555)
    opened, notes, cb = _sinks()
    ran = []
    try:
        if os.access(str(ro), os.W_OK):
            pytest.skip("chmod 0555 did not make the dir read-only (running as root?)")
        with stage_stdout(str(ro), "x.log", quiet=True, **cb):
            print("[fake] progress")
            ran.append(1)
    finally:
        ro.chmod(0o755)
    assert ran == [1] and opened == []
    assert len(notes) == 1 and notes[0].startswith("x.log not writable (PermissionError")
    assert "[fake]" not in capsys.readouterr().out and not (ro / "x.log").exists()


def test_tripwire_refusal_degrades_exactly_like_an_oserror(tmp_path, capsys):
    """An ``--out`` under a quarantined name (…/samples/x): the armed
    research-input tripwire raises StandaloneError from inside ``open()`` --
    the helper treats it as "log not writable", so the route keeps its ONE
    JSON / no-traceback envelope (root or not: no chmod involved)."""
    from rvt.frontdoor import standalone as SA
    qdir = tmp_path / "samples" / "x"
    qdir.mkdir(parents=True)
    opened, notes, cb = _sinks()
    ran = []
    SA.forbid_research_inputs()
    try:
        with stage_stdout(str(qdir), "build.log", quiet=True, **cb):
            print("[fake] progress")
            ran.append(1)
    finally:
        SA.allow_research_inputs()
    assert ran == [1] and opened == []
    assert len(notes) == 1 and "build.log not writable (StandaloneError" in notes[0]
    assert "[fake]" not in capsys.readouterr().out and not (qdir / "build.log").exists()


def test_callbacks_are_optional(tmp_path):
    with stage_stdout(str(tmp_path), "x.log", quiet=True):
        print("[fake]")
    with stage_stdout(str(tmp_path / "missing" / "dir"), "x.log", quiet=True):
        print("[fake]")                                  # FileNotFoundError -> silent in-memory sink
    assert (tmp_path / "x.log").is_file() and not (tmp_path / "missing").exists()

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

Issue #424: the body lives in the stdlib-only leaf ``src/rvt/_logsink.py``
(``rvt.frontdoor.stagelog`` re-exports it) so the two remaining call sites --
the router's spec+rvt ``job-create.log`` and ``tools/rvt_job.py --json``'s
``<out>.log`` -- share it without the ``rvt.frontdoor`` package import; both
call sites are checked here (a fake seed job for the router; the real ops
door on the bundled 2025 base for ``rvt_job.py``, skipped if it is absent).

Fresh-clone safe (stdlib + the package; no samples).
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

from rvt.frontdoor.stagelog import stage_stdout      # noqa: E402

BASE_2025 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2025.rvt")
LEVEL_ID = 1351691                                   # "GEN B1 - Basement" on the pinned bases


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
    squat = tmp_path / "a file"
    squat.write_text("not a dir")
    with stage_stdout(str(squat), "x.log", quiet=True):
        print("[fake]")                                  # unmakeable dir -> silent in-memory sink
    assert (tmp_path / "x.log").is_file() and squat.read_text() == "not a dir"


# ---------------------------------------------------------------------------
# issue #424: one stdlib leaf; the two call sites that joined it last
# ---------------------------------------------------------------------------

def test_the_front_door_name_is_the_stdlib_leaf():
    """ONE implementation, and importing it runs nothing under rvt.frontdoor
    (``tools/rvt_job.py`` pays no package import for its --json log)."""
    from rvt import _logsink
    assert stage_stdout is _logsink.stage_stdout
    r = subprocess.run([sys.executable, "-I", "-S", "-c",
                        f"import sys; sys.path.insert(0, {SRC!r}); import rvt._logsink; "
                        "print(sorted(m for m in sys.modules if m == 'rvt' or m.startswith('rvt.')))"],
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    assert ast.literal_eval(r.stdout.strip()) == ["rvt", "rvt._logsink"]


def test_a_missing_out_dir_is_made_and_an_unmakeable_one_degrades_like_open(tmp_path, capsys):
    """The log may open before its job has made a fresh ``--out`` dir
    (``rvt_job.py --json``): quiet makes the dir; a dir that cannot be made is
    the same ONE note as an unopenable log (any uid: no chmod); verbose makes
    nothing."""
    opened, notes, cb = _sinks()
    fresh = tmp_path / "fresh" / "dir"
    with stage_stdout(str(fresh), "x.log", quiet=False, **cb):
        pass
    assert not (tmp_path / "fresh").exists()
    with stage_stdout(str(fresh), "x.log", quiet=True, **cb):
        print("[fake] first")
    assert opened == [str(fresh / "x.log")] and notes == [] and (fresh / "x.log").is_file()
    squat = tmp_path / "a file"
    squat.write_text("not a dir")
    ran = []
    with stage_stdout(str(squat / "sub"), "x.log", quiet=True, **cb):
        print("[fake] second")
        ran.append(1)
    assert ran == [1] and len(opened) == 1 and len(notes) == 1
    assert notes[0].startswith("x.log not writable (") and notes[0].endswith("; stage output not logged")
    assert not (squat / "sub").exists() and capsys.readouterr().out == ""


def _seed_route(tmp_path, monkeypatch, job_main):
    """spec+rvt through the router with ``job_main(argv) -> rc`` standing in
    for ``tools/rvt_job.py``; returns ``run(out, quiet) -> RouteResult``."""
    from rvt.frontdoor import edit as E
    from rvt.frontdoor import router as R
    monkeypatch.setattr(E, "load_job_module",
                        lambda: type("FakeJob", (), {"main": staticmethod(job_main)}))
    spec, seed = tmp_path / "tiny.json", tmp_path / "seed.rvt"
    spec.write_text("{}")
    seed.write_bytes(b"")
    return lambda out, quiet: R.route({"spec": str(spec), "rvt": str(seed)}, "rvt",
                                      out=str(out), quiet=quiet)


def test_router_seed_job_log_streams_through_the_helper(tmp_path, monkeypatch, capsys):
    """spec+rvt: the seed job's progress streams into ``<out>/job-create.log``
    (named in ``files['job_log']``); a squatted log costs the log -- ONE
    caveat, no error, the job still runs and delivers -- never the step."""
    def fake_job(argv):
        out = argv[argv.index("-o") + 1]
        print(f"[fake_job] create -> {out}")
        with open(out, "wb") as fh:
            fh.write(b"not really a project")
        return 0

    run = _seed_route(tmp_path, monkeypatch, fake_job)
    out = tmp_path / "logged"
    res = run(out, True)
    log_p = str(out / "job-create.log")
    assert res.ok, (res.status, res.errors)
    assert res.files.get("job_log") == log_p and res.files.get("rvt") == str(out / "tiny.rvt")
    with open(log_p, encoding="utf-8") as fh:
        assert "[fake_job] create -> " in fh.read()
    assert not [cv for cv in res.caveats if "not writable" in cv]

    squatted = tmp_path / "squatted"
    (squatted / "job-create.log").mkdir(parents=True)
    res = run(squatted, True)
    assert res.ok and res.files.get("rvt") == str(squatted / "tiny.rvt"), (res.status, res.errors)
    assert "job_log" not in res.files
    notes = [cv for cv in res.caveats if "not writable" in cv]
    assert len(notes) == 1 and notes[0].startswith("job-create.log not writable (IsADirectoryError")
    assert not [e for e in res.errors if "job-create" in e or "route crashed" in e], res.errors
    assert "[fake_job]" not in capsys.readouterr().out


def test_router_seed_job_stderr_verdict_joins_its_log_when_quiet(tmp_path, monkeypatch, capsys):
    """#448: a FAILING seed job's ONE stderr verdict line lands in
    ``job-create.log`` after its progress when the route is quiet (``--json``:
    stderr 0 B); a verbose route keeps that line live on stderr."""
    def failing_job(argv):
        print("[fake_job] seed audit ...")
        print("[fake_job] SEED NOT READY -> aborting", file=sys.stderr)
        return 2

    run = _seed_route(tmp_path, monkeypatch, failing_job)
    res = run(tmp_path / "q", True)
    cap = capsys.readouterr()
    assert cap.out == "" and cap.err == ""
    assert not res.ok and res.status == "FAILED (rvt_job.py create exited 2)"
    with open(res.files["job_log"], encoding="utf-8") as fh:
        assert fh.read().splitlines() == ["[fake_job] seed audit ...",
                                        "[fake_job] SEED NOT READY -> aborting"]

    res = run(tmp_path / "v", False)
    cap = capsys.readouterr()
    assert cap.err.splitlines() == ["[fake_job] SEED NOT READY -> aborting"]
    with open(res.files["job_log"], encoding="utf-8") as fh:
        assert fh.read().splitlines() == ["[fake_job] seed audit ..."]   # progress still logged, as before


@pytest.mark.skipif(not os.path.isfile(BASE_2025), reason="bundled 2025 genesis base missing")
def test_rvt_job_json_with_a_squatted_log_still_delivers_one_json(tmp_path):
    """``rvt_job.py edit … --json`` whose ``<out>.log`` cannot open: the edit is
    delivered, stdout is still exactly ONE JSON == the on-disk manifest (both
    carry the ONE ``degradations`` note, no ``output.log`` named) + ``exit_code``,
    stderr stays empty -- no traceback (#424, #440; the logged happy path is
    tests/test_go_edit.py's ops-door case)."""
    ops = tmp_path / "ops.json"
    ops.write_text(json.dumps([{"op": "set-level", "id": LEVEL_ID, "elevation_ft": 5}]))
    out = tmp_path / "ops door" / "edited.rvt"
    (tmp_path / "ops door" / "edited.rvt.log").mkdir(parents=True)
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "rvt_job.py"), "edit", BASE_2025,
                        "--ops", str(ops), "-o", str(out), "--json"],
                       capture_output=True, text=True, timeout=600, cwd=str(tmp_path),
                       env={k: v for k, v in os.environ.items() if not k.startswith("RVT_")})
    assert r.returncode == 0, r.stderr[-2000:]
    assert r.stderr == ""
    doc = json.loads(r.stdout)                           # exactly one document
    assert doc["exit_code"] == 0 and doc["hard_gates_passed"] is True
    assert doc["output"]["path"] == str(out) and os.path.isfile(out) and doc["output"]["bytes"] > 0
    assert "log" not in doc["output"]
    with open(str(out) + ".manifest.json") as fh:
        on_disk = json.load(fh)
    assert len(on_disk["degradations"]) == 1             # the file itself says why output.log is absent
    assert on_disk["degradations"][0].startswith("edited.rvt.log not writable (IsADirectoryError")
    assert {k: v for k, v in doc.items() if k != "exit_code"} == on_disk   # the printed object IS the manifest (+ exit_code)

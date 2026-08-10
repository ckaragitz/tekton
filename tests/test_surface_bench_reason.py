"""surface_bench: a non-PASS job's `reason` names the job's OWN verdict (issue #287).

A job that fails cleanly -- exit != 0 but a well-formed ``--json`` result on
stdout, e.g. the IFC route on a numpy-less bare VM (#127) -- pretty-prints
its JSON, so "the last output line" is ``}`` and the bench used to report
``author --ifc failed: }``.  ``_why()`` must quote the parsed result's own
``errors[0]`` / ``status`` (front door) or ``result.error`` / ``gates.line``
(`go` envelope) first, then stderr, then a non-punctuation stdout line, then
``exit N`` -- capped at 200 chars.  Pure unit test: no plugin build, no bare
interpreter, fresh-clone safe (listed in tests/ci_shard.d/).

Issue #553 adds the classification rows: a prerequisite the surface stated
UP FRONT (`go` envelope ``go.prerequisite`` since #550, or preflight's
``routes.ifc`` for the `run frontdoor.py author --ifc` job) is ``BLOCKED``
with the {route, needs, fix} carried into the JSON row -- distinct from a
FAILED job (still ``FAIL``) and a READY one (still ``PASS``).
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def bench():
    spec = importlib.util.spec_from_file_location(
        "surface_bench", os.path.join(ROOT, "tools", "surface_bench.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _inv(bench, stdout="", stderr="", exit_code=3):
    return bench.Invocation("fake", ["python3", "x.py"], 0.1, exit_code, stdout, stderr)


FRONTDOOR_FAILED = {"route": "ifc", "ok": False, "status": "FAILED (X)",
                    "errors": ["X: detail"], "seconds": 0.3}


def test_clean_failure_quotes_errors0_not_a_brace(bench):
    """DONE 2 verbatim: pretty-printed front-door JSON, exit 3, empty stderr."""
    inv = _inv(bench, stdout=json.dumps(FRONTDOOR_FAILED, indent=1))
    assert inv.stdout.strip().splitlines()[-1] == "}"       # the trap the old _tail fell into
    reason = bench._why(inv)
    assert "X: detail" in reason and reason != "}"


@pytest.mark.parametrize("payload, expected", [
    # front door without an errors list: the status line
    ({"ok": False, "status": "FAILED (no base for 2023)"}, "FAILED (no base for 2023)"),
    # `go` envelope, edit door: ONE error line beats the gates line
    ({"go": {"ready": True, "verb": "edit"},
      "result": {"ok": False, "error": "set-level failed: KeyError: 42",
                 "gates": {"line": "structural PASS | validation FAIL (2 errors)"}}},
     "set-level failed: KeyError: 42"),
    # `go` envelope, edit door, written but gated: the gates line
    ({"go": {"ready": True, "verb": "edit"},
      "result": {"ok": False, "gates": {"line": "structural PASS | validation FAIL (2 errors)"}}},
     "structural PASS | validation FAIL (2 errors)"),
    # `go` envelope, front door inside: result.errors[0]
    ({"go": {"ready": True, "verb": "author"}, "result": FRONTDOOR_FAILED}, "X: detail"),
    # `go` envelope, preflight NOT READY: the job never ran, result is null
    ({"go": {"ready": False, "preflight_line": "tekton: NOT READY | engine: ImportError"},
      "result": None}, "tekton: NOT READY | engine: ImportError"),
    # plain preflight --json that is not READY: its own line
    ({"ok": False, "line": "tekton: NOT READY | genesis-base: missing"},
     "tekton: NOT READY | genesis-base: missing"),
])
def test_parsed_result_shapes(bench, payload, expected):
    assert bench._why(_inv(bench, stdout=json.dumps(payload, indent=1))) == expected


def test_fallbacks_stderr_then_stdout_then_exit(bench):
    # non-JSON stdout + a traceback on stderr: the last stderr line
    inv = _inv(bench, stdout="working...\n", stderr="Traceback (most recent call last):\n"
                                                   "  File \"x.py\"\nValueError: boom\n")
    assert bench._why(inv) == "ValueError: boom"
    # JSON with none of the known keys and empty stderr: last stdout line that
    # is not bare punctuation (never `}` / `]` / `},`)
    inv = _inv(bench, stdout=json.dumps({"levels": [], "n": 1}, indent=1))
    assert bench._why(inv) == '"n": 1'
    # nothing at all: the exit code
    assert bench._why(_inv(bench, exit_code=-9)) == "exit -9"
    assert bench._why(_inv(bench, stdout="}\n", stderr=" \n")) == "exit 3"


def test_reason_is_one_line_capped_at_200(bench):
    long = {"ok": False, "errors": ["IFC intent failed:\n" + "numpy " * 80]}
    reason = bench._why(_inv(bench, stdout=json.dumps(long, indent=1)))
    assert len(reason) == 200 and "\n" not in reason and reason.startswith("IFC intent failed: numpy")


# ---------------------------------------------------------------------------
# issue #553: a prerequisite the surface stated UP FRONT is BLOCKED, not FAIL
# ---------------------------------------------------------------------------

PREREQ = {"route": "ifc", "needs": ["numpy"], "fix": "python -m pip install numpy"}
NOT_READY_IFC = ("tekton: NOT READY for --ifc | ifc-route needs numpy (python -m pip "
                 "install numpy) -- one-time; the other routes are READY without it")
#: the ONE JSON `go author --ifc ...` prints on a numpy-less interpreter since #550
GO_PREREQ_ENVELOPE = {"go": {"one_call": True, "ready": False, "verb": "author",
                             "prerequisite": PREREQ, "preflight_line": NOT_READY_IFC,
                             "preflight_seconds": 0.07, "exit_code": 3, "preflight": {}},
                      "result": None}
GO_READY_OK = {"go": {"one_call": True, "ready": True, "verb": "author", "exit_code": 0,
                      "preflight_line": "tekton: READY | ...", "job_seconds": 2.0},
               "result": {"ok": True, "route": "prompt", "status": "PROOF-ONLY (self-checks PASS)",
                          "errors": [], "files": {}}}


class _FakeSurface:
    """Just enough Surface for a job classifier: ``run`` hands back a canned
    Invocation instead of spawning a shell call."""

    def __init__(self, bench, stdout: str, exit_code: int, workdir: str):
        self._bench, self._stdout, self._exit = bench, stdout, exit_code
        self.call_no, self.workdir, self.plugin_dir = 0, workdir, workdir

    def bootstrap(self, skill: str) -> str:
        return os.path.join(self.plugin_dir, "skills", skill, "scripts", "_bootstrap.py")

    def run(self, label, argv_builder):
        self.call_no += 1
        argv_builder(self)                                # the job builds its argv as for real
        return _inv(self._bench, stdout=self._stdout, exit_code=self._exit)


def _surface(bench, tmp_path, payload, exit_code):
    return _FakeSurface(bench, json.dumps(payload, indent=1), exit_code, str(tmp_path))


def test_go_envelope_with_prerequisite_is_blocked_and_carries_needs_fix(bench, tmp_path):
    job = bench.job_go_author_prompt(_surface(bench, tmp_path, GO_PREREQ_ENVELOPE, 3), {})
    assert job.status == "BLOCKED"
    assert job.reason == NOT_READY_IFC                    # the preflight line, verbatim
    assert job.prerequisite == PREREQ
    jd = job.as_dict()
    assert jd["status"] == "BLOCKED" and jd["prerequisite"] == PREREQ
    # every timing column is still there
    assert {"shell_calls", "seconds", "extract_seconds", "invocations"} <= set(jd)


def test_go_envelope_failed_is_still_fail(bench, tmp_path):
    failed = {"go": {"ready": True, "verb": "author", "exit_code": 3}, "result": FRONTDOOR_FAILED}
    job = bench.job_go_author_prompt(_surface(bench, tmp_path, failed, 3), {})
    assert job.status == "FAIL" and "X: detail" in job.reason
    assert "prerequisite" not in job.as_dict()


def test_go_envelope_ready_ok_is_still_pass(bench, tmp_path):
    job = bench.job_go_author_prompt(_surface(bench, tmp_path, GO_READY_OK, 0), {})
    assert job.status == "PASS" and job.reason == ""
    assert "prerequisite" not in job.as_dict()


def test_environment_not_ready_without_prerequisite_is_still_fail(bench, tmp_path):
    """go.ready:false WITHOUT go.prerequisite = the environment itself is broken
    (engine / genesis base / out-dir): a real failure on that surface, not BLOCKED."""
    env_broken = {"go": {"ready": False, "exit_code": 3,
                         "preflight_line": "tekton: NOT READY | engine: ImportError: x"},
                  "result": None}
    job = bench.job_go_author_prompt(_surface(bench, tmp_path, env_broken, 3), {})
    assert job.status == "FAIL" and "NOT READY | engine" in job.reason


IFC_FAILED_NUMPY = {"route": "ifc", "ok": False, "errors": [
    "IFC intent failed: the --ifc route needs numpy, not installed on this interpreter -- "
    "one-time fix: python -m pip install numpy (--prompt / --rvt run without it)"],
    "status": "FAILED (IFC intent failed: ...)", "files": {}}


@pytest.mark.parametrize("routes, expected_status", [
    ({"ifc": {"ok": False, "needs": ["numpy"], "fix": "python -m pip install numpy"}}, "BLOCKED"),
    ({"ifc": {"ok": True, "needs": []}}, "FAIL"),         # route buildable + failed job = a real FAIL
    (None, "FAIL"),                                       # pre-#127 plugin build: no routes table
])
def test_author_ifc_prerequisite_stated_by_preflight(bench, tmp_path, routes, expected_status):
    state = {"preflight": {} if routes is None else {"routes": routes}}
    job = bench.job_author_ifc(_surface(bench, tmp_path, IFC_FAILED_NUMPY, 3), state)
    assert job.status == expected_status
    if expected_status == "BLOCKED":
        assert job.reason == ("ifc route prerequisite stated by preflight: "
                              "needs numpy (python -m pip install numpy)")
        assert job.as_dict()["prerequisite"] == PREREQ
    else:
        assert job.reason.startswith("author --ifc failed: IFC intent failed: the --ifc route needs numpy")
        assert "prerequisite" not in job.as_dict()


def test_author_ifc_that_built_is_pass_whatever_the_table_says(bench, tmp_path):
    state = {"preflight": {"routes": {"ifc": {"ok": False, "needs": ["numpy"], "fix": "x"}}}}
    ok = {"route": "ifc", "ok": True, "status": "PROOF-ONLY", "errors": [], "files": {}}
    assert bench.job_author_ifc(_surface(bench, tmp_path, ok, 0), state).status == "PASS"


def test_table_and_summary_say_blocked_needs_numpy(bench, tmp_path):
    blocked = bench.job_go_author_prompt(_surface(bench, tmp_path, GO_PREREQ_ENVELOPE, 3), {}).as_dict()
    passed = bench.job_go_author_prompt(_surface(bench, tmp_path, GO_READY_OK, 0), {}).as_dict()
    assert bench._cell(blocked, "cowork") == "0.1s BLOCKED (needs numpy)"
    assert bench._cell(passed, "cowork") == "0.1s"          # untouched
    plain_blocked = dict(blocked, prerequisite={})            # e.g. the ifcopenshell special-case
    assert bench._cell(plain_blocked, "cowork") == "0.1s BLOCKED"

    def surface(name, jobs):
        return {"surface": name, "model": bench.SURFACE_BLURB[name], "python_version": "3.11.9",
                "extras": {"numpy": name == "local"}, "session_setup_seconds": 0.0, "jobs": jobs,
                "session_totals": {"shell_calls": 1, "seconds": 0.1, "extract_seconds": 0.0}}
    report = {"surfaces": [surface("cowork", [blocked]), surface("local", [passed])]}
    md = bench.markdown_table(report)
    assert "| go-author-prompt | 1 | 0.1s BLOCKED (needs numpy) | 0.1s |" in md
    assert f"- cowork / go-author-prompt: BLOCKED -- {NOT_READY_IFC}" in md
    assert "FAIL" not in md

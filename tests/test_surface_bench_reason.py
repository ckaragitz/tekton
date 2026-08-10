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

Issue #562 adds the ``go-author-ifc`` job (ONE `go author --ifc FILE
--target-version N` call, classified from the envelope itself) and makes the
``author-ifc`` row's BLOCKED independent of job order: run without the
preflight job it asks the surface for its route table itself (one counted call).
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
    """Just enough Surface for a job classifier: ``run`` hands back canned
    Invocations -- one (stdout, exit) per call, in order -- instead of
    spawning shell calls, and remembers each call's label + argv."""

    def __init__(self, bench, calls: list, workdir: str):
        self._bench, self._calls, self.labels, self.argvs = bench, list(calls), [], []
        self.call_no, self.workdir, self.plugin_dir = 0, workdir, workdir

    def bootstrap(self, skill: str) -> str:
        return os.path.join(self.plugin_dir, "skills", skill, "scripts", "_bootstrap.py")

    def run(self, label, argv_builder):
        self.call_no += 1
        self.labels.append(label)
        self.argvs.append(argv_builder(self))             # the job builds its argv as for real
        stdout, exit_code = self._calls[self.call_no - 1]  # an unplanned call is an IndexError
        return _inv(self._bench, stdout=stdout, exit_code=exit_code)


def _surface(bench, tmp_path, payload, exit_code, *then):
    """``then``: further ``(payload, exit)`` pairs answering the 2nd, 3rd... call."""
    calls = [(json.dumps(p, indent=1), c) for p, c in ((payload, exit_code), *then)]
    return _FakeSurface(bench, calls, str(tmp_path))


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
IFC_BUILT_OK = {"route": "ifc", "ok": True, "status": "PROOF-ONLY", "errors": [], "files": {}}
AUTHOR_IFC_BLOCKED = ("ifc route prerequisite stated by preflight: "
                      "needs numpy (python -m pip install numpy)")


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
        assert job.reason == AUTHOR_IFC_BLOCKED
        assert job.as_dict()["prerequisite"] == PREREQ
    else:
        assert job.reason.startswith("author --ifc failed: IFC intent failed: the --ifc route needs numpy")
        assert "prerequisite" not in job.as_dict()


def test_author_ifc_that_built_is_pass_whatever_the_table_says(bench, tmp_path):
    state = {"preflight": {"routes": {"ifc": {"ok": False, "needs": ["numpy"], "fix": "x"}}}}
    assert bench.job_author_ifc(_surface(bench, tmp_path, IFC_BUILT_OK, 0), state).status == "PASS"


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


# ---------------------------------------------------------------------------
# issue #562: the `go author --ifc` row, and author-ifc BLOCKED whatever ran before it
# ---------------------------------------------------------------------------

#: the ONE JSON `go author --ifc ...` prints when numpy IS present and the job built
GO_IFC_READY_OK = {"go": {"one_call": True, "ready": True, "verb": "author", "exit_code": 0,
                          "preflight_line": "tekton: READY | ... | ifc-route OK | ...",
                          "job_seconds": 7.1},
                   "result": {"ok": True, "route": "ifc", "status": "PROOF-ONLY (self-checks PASS)",
                              "errors": [], "files": {},
                              "release": {"requested": 2025, "output": 2025}}}
#: ... and when the job ran but the IFC itself was unusable (a real failure, numpy or not)
GO_IFC_FAILED = {"go": {"one_call": True, "ready": True, "verb": "author", "exit_code": 3},
                 "result": {"ok": False, "route": "ifc", "files": {},
                            "errors": ["IFC intent failed: Error: Unable to parse IFC SPF header"],
                            "status": "FAILED (IFC intent failed: Error: Unable to parse IFC SPF header)"}}
#: `_bootstrap.py --json` on a numpy-less interpreter (the keys the bench reads)
PREFLIGHT_BARE = {"ok": True, "python": {"version": "3.11.15"}, "seconds": 0.06,
                  "line": "tekton: READY | ... | ifc-route needs numpy (python -m pip install numpy) | ...",
                  "extras": {"numpy": False, "ifcopenshell": True},
                  "routes": {"prompt": {"ok": True, "needs": []}, "ifc": dict(PREREQ, ok=False),
                             "rvt": {"ok": True, "needs": []}}}


def test_go_author_ifc_is_a_canonical_job_after_author_ifc(bench):
    order = list(bench.JOB_ORDER)
    assert order.index("go-author-ifc") == order.index("author-ifc") + 1
    assert bench.JOBS["go-author-ifc"] is bench.job_go_author_ifc


def test_go_author_ifc_is_one_go_call_naming_the_bundled_ifc_and_a_release(bench, tmp_path):
    s = _surface(bench, tmp_path, GO_PREREQ_ENVELOPE, 3)
    job = bench.job_go_author_ifc(s, {})
    assert job.calls == 1 and s.labels == ["go author --ifc (electrical room)"]
    argv = s.argvs[0]
    assert argv[:3] == [s.bootstrap("tekton-author"), "go", "author"]
    assert argv[argv.index("--ifc") + 1] == os.path.join(s.plugin_dir, bench.IFC_EXAMPLE_REL)
    assert argv[argv.index("--target-version") + 1] == bench.GO_IFC_TARGET_VERSION == "2025"
    assert "--json" in argv and argv[argv.index("--out") + 1].startswith(s.workdir)


@pytest.mark.parametrize("payload, exit_code, status, reason", [
    (GO_PREREQ_ENVELOPE, 3, "BLOCKED", NOT_READY_IFC),        # bare interpreter: stated up front
    (GO_IFC_READY_OK, 0, "PASS", ""),                          # numpy present: built
    (GO_IFC_FAILED, 3, "FAIL",                                 # ran and failed: a real FAIL, own verdict
     "go author failed: IFC intent failed: Error: Unable to parse IFC SPF header"),
])
def test_go_author_ifc_classified_from_the_envelope_itself(bench, tmp_path, payload, exit_code,
                                                            status, reason):
    """No preflight job, no routes table in state: the envelope alone decides."""
    job = bench.job_go_author_ifc(_surface(bench, tmp_path, payload, exit_code), {})
    assert (job.status, job.reason) == (status, reason)
    jd = job.as_dict()
    assert jd["job"] == "go-author-ifc" and jd["shell_calls"] == 1
    assert {"shell_calls", "seconds", "extract_seconds", "invocations"} <= set(jd)
    if status == "BLOCKED":
        assert jd["prerequisite"] == PREREQ
        assert bench._cell(jd, "cowork") == "0.1s BLOCKED (needs numpy)"
    else:
        assert "prerequisite" not in jd
    if status == "PASS":
        assert jd["breakdown"]["job_seconds"] == 7.1


def test_go_author_ifc_on_a_pre_go_build_is_skipped(bench, tmp_path):
    """A plugin build that predates `go` answers unknown argv with the plain
    readiness line -- an absent feature (skipped), not a failure."""
    s = _FakeSurface(bench, [("tekton: READY | engine OK | 0.05s\n", 0)], str(tmp_path))
    assert bench.job_go_author_ifc(s, {}).status == "SKIPPED"


def test_author_ifc_alone_asks_the_surface_for_its_route_table(bench, tmp_path):
    """`--jobs author-ifc` with no preflight job before it (#562): the failed job
    is followed by ONE counted `_bootstrap.py --json` probe on the same row, and
    the stated `routes.ifc` prerequisite makes it BLOCKED exactly as in a full
    session -- never FAIL just because of job order."""
    s = _surface(bench, tmp_path, IFC_FAILED_NUMPY, 3, (PREFLIGHT_BARE, 0))
    state: dict = {}
    job = bench.job_author_ifc(s, state)
    assert (job.status, job.reason) == ("BLOCKED", AUTHOR_IFC_BLOCKED)
    assert job.as_dict()["prerequisite"] == PREREQ
    assert job.calls == 2 and s.labels == ["author --ifc (electrical room)",
                                           "preflight --json (route table)"]
    assert s.argvs[1] == [s.bootstrap("tekton-author"), "--json"]
    assert state["preflight"]["routes"]["ifc"]["ok"] is False   # kept for later jobs
    # in a full session (preflight already asked) the row stays ONE call
    s2 = _surface(bench, tmp_path, IFC_FAILED_NUMPY, 3)
    job2 = bench.job_author_ifc(s2, {"preflight": {"routes": PREFLIGHT_BARE["routes"]}})
    assert (job2.status, job2.reason, job2.calls) == ("BLOCKED", job.reason, 1)


@pytest.mark.parametrize("probe, probe_exit", [
    ({k: v for k, v in PREFLIGHT_BARE.items() if k != "routes"}, 0),   # pre-#127 build: READY, no table
    ({"ok": False, "line": "tekton: NOT READY | engine: ImportError: x"}, 3),   # broken surface
])
def test_author_ifc_alone_without_a_stated_prerequisite_is_still_fail(bench, tmp_path,
                                                                        probe, probe_exit):
    s = _surface(bench, tmp_path, IFC_FAILED_NUMPY, 3, (probe, probe_exit))
    state: dict = {}
    job = bench.job_author_ifc(s, state)
    assert job.status == "FAIL" and job.calls == 2
    assert job.reason.startswith("author --ifc failed: IFC intent failed: the --ifc route needs numpy")
    assert "prerequisite" not in job.as_dict()
    assert "preflight" in state                                 # asked once; later jobs reuse it


def test_author_ifc_alone_that_built_never_probes(bench, tmp_path):
    job = bench.job_author_ifc(_surface(bench, tmp_path, IFC_BUILT_OK, 0), {})
    assert (job.status, job.calls) == ("PASS", 1)


def test_preflight_job_ready_records_the_route_table(bench, tmp_path):
    state: dict = {}
    job = bench.job_preflight(_surface(bench, tmp_path, PREFLIGHT_BARE, 0), state)
    assert (job.status, job.reason, job.calls) == ("PASS", "", 1)
    assert state["preflight"] == {"python": "3.11.15", "extras": PREFLIGHT_BARE["extras"],
                                  "routes": PREFLIGHT_BARE["routes"], "internal_seconds": 0.06}


def test_preflight_job_not_ready_fails_and_leaves_an_asked_marker(bench, tmp_path):
    not_ready = {"ok": False, "line": "tekton: NOT READY | genesis-base: missing"}
    state: dict = {}
    job = bench.job_preflight(_surface(bench, tmp_path, not_ready, 3), state)
    assert (job.status, job.calls) == ("FAIL", 1)
    assert job.reason == "preflight not READY: tekton: NOT READY | genesis-base: missing"
    assert state["preflight"] == {}          # asked, not READY: author-ifc will not re-probe

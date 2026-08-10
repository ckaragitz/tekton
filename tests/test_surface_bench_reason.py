"""surface_bench: a non-PASS job's `reason` names the job's OWN verdict (issue #287).

A job that fails cleanly -- exit != 0 but a well-formed ``--json`` result on
stdout, e.g. the IFC route on a numpy-less bare VM (#127) -- pretty-prints
its JSON, so "the last output line" is ``}`` and the bench used to report
``author --ifc failed: }``.  ``_why()`` must quote the parsed result's own
``errors[0]`` / ``status`` (front door) or ``result.error`` / ``gates.line``
(`go` envelope) first, then stderr, then a non-punctuation stdout line, then
``exit N`` -- capped at 200 chars.  Pure unit test: no plugin build, no bare
interpreter, fresh-clone safe (listed in tests/ci_shard.d/).
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

"""CI perf-regression gate for the sandboxed AI surfaces.

Every tekton skill runs on a surface where a shell invocation is a full
model round-trip and a fresh VM has never seen the plugin, so the hot path
has a BUDGET: preflight must stay a sub-2-second one-liner and the flagship
author job must stay under 20 seconds on a BARE environment (no venv, no
pip, no repo -- only the plugin).  These ceilings are deliberately generous
(the 2026-08-04 baseline measured preflight ~0.1 s and author ~7 s on a
bare python 3.9); the point is catching regressions -- a reintroduced pip
install, an eager heavy import, a schema re-parse on the readiness path, or
a new mandatory shell call sneaking into the flow.

The bench itself is tools/surface_bench.py (the simulated-surface harness);
this test drives its "cowork" surface -- a fresh copy of plugin/ at a
mount-like path, cleared env, dead proxies -- against the plugin WORKING
TREE (the shipped zip is separately guarded by test_plugin_sync's drift
check).
"""
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ceilings (seconds) -- generous on purpose; the baseline is ~20x under them
PREFLIGHT_CEILING = 2.0
AUTHOR_CEILING = 20.0
EDIT_CEILING = 20.0

# the canonical flow's call budget: preflight 1 + author 1 + edit 1 (`go edit`,
# issue #111; the pre-#111 edit flow alone was 3: info -> edit -> gate)
SESSION_CALL_BUDGET = 3


def _load_bench():
    spec = importlib.util.spec_from_file_location(
        "surface_bench", os.path.join(ROOT, "tools", "surface_bench.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bare_python() -> str:
    """The bare interpreter approximating a sandbox VM.  The author job's
    intent model needs numpy (both real sandboxes ship it); skip -- loudly --
    when no such interpreter exists on this CI host."""
    for cand in ("/usr/bin/python3", shutil_which("python3")):
        if cand and os.path.isfile(cand):
            r = subprocess.run([cand, "-c", "import numpy"], capture_output=True)
            if r.returncode == 0:
                return cand
    pytest.skip("no bare python3 with numpy on this host -- the bare-surface "
                "perf gate needs one (both real sandboxes ship numpy)")


def shutil_which(name: str):
    import shutil
    return shutil.which(name)


@pytest.fixture(scope="module")
def bench_report():
    bench = _load_bench()
    report = bench.run_bench(
        surfaces=["cowork"],
        jobs=["preflight", "author-prompt", "go-edit"],
        source=os.path.join(ROOT, "plugin"),      # the working tree, always current
        python_bare=_bare_python(),
        timeout=120.0,
    )
    return report["surfaces"][0]


def _job(report: dict, name: str) -> dict:
    jd = next((j for j in report["jobs"] if j["job"] == name), None)
    assert jd is not None, f"job {name} missing from the bench report"
    return jd


def test_bare_preflight_under_2s(bench_report):
    jd = _job(bench_report, "preflight")
    assert jd["status"] == "PASS", f"preflight not READY on a bare surface: {jd['reason']}"
    assert jd["shell_calls"] == 1, "preflight must stay ONE shell call"
    assert jd["seconds"] < PREFLIGHT_CEILING, (
        f"bare-env preflight took {jd['seconds']}s (ceiling {PREFLIGHT_CEILING}s) -- "
        "something heavy crept onto the readiness path")


def test_bare_author_prompt_under_20s(bench_report):
    jd = _job(bench_report, "author-prompt")
    assert jd["status"] == "PASS", f"author --prompt failed on a bare surface: {jd['reason']}"
    assert jd["shell_calls"] == 1, "the prompt job must stay ONE shell call"
    assert jd["seconds"] < AUTHOR_CEILING, (
        f"bare-env author --prompt took {jd['seconds']}s (ceiling {AUTHOR_CEILING}s) -- "
        "cold-start compute regressed (pip? eager imports? schema re-parse?)")


def test_bare_go_edit_is_one_call_and_bounded(bench_report):
    """The tekton-edit flow is ONE `go edit` call (readiness + edit + self-check
    + the mandatory validation gate; issue #111) -- fewer than the pre-#111
    info -> edit -> gate choreography -- and it keeps working from the plugin
    alone (guards the 2026-08-04 bare-machine ObjectDecoder fix too: the edit
    opens, re-emits and validates a real project with only the bundled engine)."""
    jd = _job(bench_report, "go-edit")
    assert jd["status"] == "PASS", f"`go edit` broken on a bare surface: {jd['reason']}"
    assert jd["shell_calls"] == 1, "the edit flow is ONE `go edit` call (was 3 before #111)"
    assert "validation PASS" in (jd.get("breakdown") or {}).get("gates", ""), (
        "the mandatory gate must run INSIDE the one call and pass on the bundled base")
    assert jd["seconds"] < EDIT_CEILING


def test_session_shell_call_budget(bench_report):
    """The choreography budget: a new mandatory call in any canonical flow is
    a regression on every surface (each call is a model round-trip)."""
    total = sum(j["shell_calls"] for j in bench_report["jobs"])
    assert total <= SESSION_CALL_BUDGET, (
        f"the canonical preflight+author+edit session now takes {total} shell "
        f"calls (budget {SESSION_CALL_BUDGET}) -- a flow grew an extra round-trip")

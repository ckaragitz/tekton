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

The README/CLAUDE.md FLAGSHIP job -- `go author --prompt "an electrical room
with 6 panels"`: six generated families, loaded and placed, walls, circuits,
the gates, ONE shell call -- has its own ceiling (issue #184).  It is the job
the latency epic (#110) tracks, and it moved 27-28.6 s -> ~10 s (#237 ECC)
-> ~8.5 s (#256 one host pass) -> 3.1-3.7 s (#292 schema memo) on the same
class of cloud VM; gating only the 1-panel prompt would leave a 4x flagship
regression (or the loss of any of those wins) invisible.

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
# The flagship 6-panel `go author` job (issue #184).  Measured 2026-08-09 on
# a claude.ai/code cloud VM (4 vCPU Intel Xeon @ 2.10 GHz, Linux 6.18, bare
# system python 3.11.15, numpy absent) at main@dc0980f: by-hand bare unzip
# go.job_seconds 3.479 / 3.081 / 3.084 (median 3.08 s, wall 3.19 s); the
# bench's cowork surface from the shipped zip 3.1 s (codeexec 3.7 s, local
# 3.2 s); this fixture (cowork, plugin/ tree, numpy present via the user
# site) 3.48 / 3.44 / 3.31 s wall, job_seconds 3.37 / 3.32 / 3.20.  The
# GitHub ubuntu-latest runner timed the shard's other bare-build tests
# within a few percent of this VM the same day, so 8 s is ~2.3-2.5x the
# medians and ~2.2x the slowest observed run: room for runner variance,
# none for a lost win (the pre-#292 8.1-8.9 s job and the pre-#237 27 s job
# both fail it).  Widen only with a newly measured number stated here;
# never delete the assertion.
ROOM6_CEILING = 8.0
ROOM6_FAMILIES = 6

# the canonical flow's call budget: preflight 1 + author 1 + edit 1 (`go edit`,
# issue #111; the pre-#111 edit flow alone was 3: info -> edit -> gate)
CANONICAL_SESSION = ("preflight", "author-prompt", "go-edit")
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
        jobs=[*CANONICAL_SESSION, "go-author-6panels"],
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


def test_bare_go_author_6panels_under_ceiling(bench_report):
    """The flagship demo job in ONE `go author` call on a bare surface: READY,
    ok, all six families actually loaded (a job that got fast by silently
    loading nothing is not a pass), and under ROOM6_CEILING (issue #184)."""
    jd = _job(bench_report, "go-author-6panels")
    assert jd["status"] == "PASS", f"flagship `go author` (6 panels) failed on a bare surface: {jd['reason']}"
    assert jd["shell_calls"] == 1, "the flagship prompt job must stay ONE `go author` call"
    bd = jd.get("breakdown") or {}
    assert bd.get("job_seconds") is not None, "the `go` envelope must report job_seconds"
    load = next((st for st in bd.get("stages") or [] if st.get("stage") == "L"), {})
    assert load.get("n_loaded") == load.get("n_planned") == ROOM6_FAMILIES, (
        f"the flagship job must load all {ROOM6_FAMILIES} generated families "
        f"(manifest L stage: {load})")
    assert jd["seconds"] < ROOM6_CEILING, (
        f"bare-env flagship `go author` (6 panels) took {jd['seconds']}s, job_seconds "
        f"{bd['job_seconds']}s (ceiling {ROOM6_CEILING}s) -- per-family cost regressed "
        f"(schema re-materialised per decoder? a second host pass? ECC back on the slow path?)")


def test_session_shell_call_budget(bench_report):
    """The choreography budget: a new mandatory call in any canonical flow is
    a regression on every surface (each call is a model round-trip)."""
    total = sum(_job(bench_report, name)["shell_calls"] for name in CANONICAL_SESSION)
    assert total <= SESSION_CALL_BUDGET, (
        f"the canonical preflight+author+edit session now takes {total} shell "
        f"calls (budget {SESSION_CALL_BUDGET}) -- a flow grew an extra round-trip")

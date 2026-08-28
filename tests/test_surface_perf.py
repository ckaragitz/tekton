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
with 6 panels"`, six generated families loaded and placed in ONE call -- has
its own, tighter ceiling (issue #184): it is the job the latency epic (#110)
tracks, and gating only the 1-panel prompt would leave a 4x flagship
regression (or the loss of the #237 / #256 / #292 wins) invisible.

The bench itself is tools/surface_bench.py (the simulated-surface harness);
this test drives its "cowork" surface -- a fresh copy of plugin/ at a
mount-like path, cleared env, dead proxies -- against the plugin WORKING
TREE (the shipped zip is separately guarded by test_plugin_sync's drift
check).

The tekton-ifc skill (Claude Design / Cowork: plain CLIs, no `rvt` engine,
no `go`) is a DIFFERENT session and is benched on its own (`ifc-harden`,
issue #113, and its ONE-call form `go-ifc-harden` = scripts/ifc_flow.py,
issue #754): its calls have their own ceiling and do not count against the
`go` session's call budget.
"""
from __future__ import annotations

import functools
import importlib.util
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# the plugin's own floor (plugin/skills/_shared/tekton_env.py MIN_PY)
MIN_BARE_PY = (3, 9)

# ceilings (seconds) -- generous on purpose; the baseline is ~20x under them
PREFLIGHT_CEILING = 2.0
AUTHOR_CEILING = 20.0
EDIT_CEILING = 20.0
# The flagship 6-panel `go author` job (issue #184): measured 2026-08-09 at
# main@dc0980f on a claude.ai/code cloud VM (bare system python 3.11), median
# 3.1-3.4 s wall, slowest observed 3.7 s; GitHub's ubuntu-latest runner timed
# the shard's other bare builds on par with that VM the same day.  8 s is
# ~2.3x headroom for runner variance and still fails both earlier states of
# main (pre-#292 8.1-8.9 s, pre-#237 27 s).  Per-run / per-surface tables:
# docs/inbox/perf-surfaces.md "FLAGSHIP-PERF-GATE".  Widen only with a newly
# measured number stated here; never delete the assertion.
ROOM6_CEILING = 8.0
# The documented IFC flow -- ONE `go author --ifc FILE --target-version N`
# call (issue #562) -- has exactly two honest outcomes on a bare surface: on a
# python WITHOUT numpy the surface states the route's prerequisite up front and
# attempts no job (BLOCKED, a preflight-cost answer: measured 0.1 s), and WITH
# numpy the real ifc build runs (measured 2026-08-10 on a claude.ai/code cloud
# VM, venv python 3.11 + numpy as the bare interpreter, plugin tree, cowork
# surface: 8.6-9.2 s wall, job ~8.5 s, 8/8 families in one host pass) and is
# held to the same generous AUTHOR_CEILING as the 1-panel prompt job.

# The tekton-ifc skill's four-call flow (`ifc-harden`, issue #113) on a bare
# surface: without ifcopenshell + numpy it is BLOCKED at the first import
# (measured 0.05 s); with them, measured 2026-08-27 on a claude.ai/code cloud
# VM (venv python 3.11 + ifcopenshell 0.8.5 + numpy 2.4 as the bare
# interpreter, plugin tree, cowork surface): 5.4-5.7 s wall over the 4 calls --
# validate 1.4-1.5 s, harden 2.6-2.7 s, re-validate 1.3-1.6 s, report 0.04 s
# (~0.5-0.7 s of every tool call is the ifcopenshell import; codeexec 5.9 s
# + 0.5 s extract) -- and the sample goes 35.7 -> 77.0 (Tier 0 -> Tier 1
# partial), 13/13 GlobalIds kept, 0 schema errors after.  20 s is ~3.5x
# headroom (the same generous figure as AUTHOR_CEILING); widen only with a
# newly measured number stated here, never delete the assertion.
# The ONE-call form (`go-ifc-harden` = scripts/ifc_flow.py, issue #754: one
# process, one import, the file analysed twice instead of four times) is held
# to the same ceiling and must beat its four-call twin from the same run:
# measured 2026-08-28 on the same VM, same run, cowork surface: four calls
# 3.35-3.75 s -> one call 1.5-1.7 s (in-process ~1.2 s: validate ~0.55 s,
# harden + reopen/re-validate ~0.65 s, report 0.00 s); codeexec 3.5 s + 0.7 s
# extract -> 1.8 s + 0.1 s extract.
IFC_SKILL_CEILING = 20.0

# the session's call budget: preflight 1 + author 1 + edit 1 (`go edit`, issue
# #111; the pre-#111 edit flow alone was 3: info -> edit -> gate) + the
# flagship author job 1 (`go author`, readiness inline) + the documented IFC
# flow 1 (`go author --ifc`, issue #562: ONE call whether it builds or states
# its prerequisite -- was 4 before that row joined the session)
SESSION_CALL_BUDGET = 5


def _load_bench():
    spec = importlib.util.spec_from_file_location(
        "surface_bench", os.path.join(ROOT, "tools", "surface_bench.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@functools.lru_cache(maxsize=None)
def _bare_python() -> str:
    """The bare interpreter approximating a sandbox VM: the system
    ``/usr/bin/python3``, else the first ``python3`` on PATH, else the BASE
    interpreter under this (venv) one -- whichever first meets the plugin's
    own floor -- and only as a last resort the test interpreter itself (a venv
    python would put its site-packages on the "bare" surface).  numpy is NOT
    required: every canonical job builds numpy-free (#44 / #127), so the gate
    EXECUTES on any host instead of skipping where the system python lacks it
    (issue #136)."""
    floor = "import sys; sys.exit(sys.version_info < %r)" % (MIN_BARE_PY,)
    for cand in ("/usr/bin/python3", shutil.which("python3"),
                 getattr(sys, "_base_executable", None)):
        if cand and os.path.isfile(cand) and subprocess.run([cand, "-c", floor]).returncode == 0:
            return cand
    return sys.executable


@pytest.fixture(scope="module")
def bench():
    return _load_bench()


def _cowork_report(bench, jobs: list) -> dict:
    """One session of ``jobs`` on the cowork surface: the plugin WORKING TREE
    (always current), the bare interpreter."""
    report = bench.run_bench(surfaces=["cowork"], jobs=jobs,
                             source=os.path.join(ROOT, "plugin"),
                             python_bare=_bare_python(), timeout=120.0)
    return report["surfaces"][0]


@pytest.fixture(scope="module")
def bench_report(bench):
    return _cowork_report(bench, ["preflight", "author-prompt", "go-edit",
                                  "go-author-6panels", "go-author-ifc"])


@pytest.fixture(scope="module")
def ifc_skill_report(bench):
    """The tekton-ifc skill's own session (#113): not part of the `go` session
    above, so its calls never count against SESSION_CALL_BUDGET.  Both the
    four-call flow and its one-call form (#754) from ONE run, so the
    before/after pair is measured under the same conditions."""
    return _cowork_report(bench, ["ifc-harden", "go-ifc-harden"])


def _bare_has(bench, python: str, modules, tmp_path) -> bool:
    """Whether the bare interpreter can import ``modules`` UNDER THE BENCH ENV
    (cleared PATH/HOME/proxies), asked of that interpreter in a subprocess so
    nothing heavy is imported here.  Not the preflight's ``extras``: those read
    ifcopenshell as present through the engine's steplite shim, which the
    tekton-ifc tools (separate processes) never see."""
    probe = ("import importlib.util as u, sys; "
             "sys.exit(0 if all(u.find_spec(m) for m in %r) else 1)" % (list(modules),))
    return subprocess.run([python, "-c", probe], env=bench.bare_env(str(tmp_path)),
                          capture_output=True).returncode == 0


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


def test_bare_go_author_6panels_under_ceiling(bench, bench_report):
    """The flagship demo job in ONE `go author` call on a bare surface: PASS
    (the bench itself refuses a degraded load as a pass), the full family
    count planned (a prompt-parse collapse to fewer families would be fast
    for the wrong reason), job_seconds reported, and under ROOM6_CEILING
    (issue #184)."""
    jd = _job(bench_report, "go-author-6panels")
    assert jd["status"] == "PASS", f"flagship `go author` (6 panels) failed on a bare surface: {jd['reason']}"
    assert jd["shell_calls"] == 1, "the flagship prompt job must stay ONE `go author` call"
    bd = jd.get("breakdown") or {}
    assert bd.get("job_seconds") is not None, "the `go` envelope must report job_seconds"
    load = bench.load_stage(bd)
    assert load.get("n_planned") == bench.ROOM6_FAMILIES, (
        f"the flagship prompt must plan {bench.ROOM6_FAMILIES} generated families "
        f"(manifest L stage: {load})")
    assert jd["seconds"] < ROOM6_CEILING, (
        f"bare-env flagship `go author` (6 panels) took {jd['seconds']}s, job_seconds "
        f"{bd['job_seconds']}s (ceiling {ROOM6_CEILING}s) -- per-family cost regressed "
        f"(schema re-materialised per decoder? a second host pass? ECC back on the slow path?)")


def test_bare_go_author_ifc_builds_or_states_its_prerequisite(bench_report):
    """The documented IFC flow is ONE `go author --ifc` call on a bare surface
    (issue #562) and reads exactly one of two honest outcomes -- PASS (numpy on
    the bare python: the ifc job built, under AUTHOR_CEILING) or BLOCKED (no
    numpy: the surface named the route's prerequisite up front, `go.prerequisite`,
    and attempted no job) -- never FAIL, never a silent SKIPPED.  Which of the
    two applies is read from the surface's OWN preflight (`extras.numpy` = that
    interpreter's `find_spec("numpy")` under the bench env), so the test runs on
    any host and numpy is never imported into this process."""
    jd = _job(bench_report, "go-author-ifc")
    assert jd["status"] in ("PASS", "BLOCKED"), (
        f"`go author --ifc` on a bare surface is {jd['status']}: {jd['reason']}")
    assert jd["shell_calls"] == 1, "the IFC flow must stay ONE `go author --ifc` call"
    if (bench_report.get("extras") or {}).get("numpy"):
        assert jd["status"] == "PASS", (
            f"numpy is on the bare python but the ifc job did not build: {jd['reason']}")
        assert (jd.get("breakdown") or {}).get("job_seconds") is not None, (
            "the `go` envelope must report job_seconds")
        assert jd["seconds"] < AUTHOR_CEILING, (
            f"bare-env `go author --ifc` took {jd['seconds']}s (ceiling {AUTHOR_CEILING}s) -- "
            "the ifc route's cold-start compute regressed")
    else:
        assert jd["status"] == "BLOCKED", (
            f"numpy is absent but the ifc route was not gated up front: {jd['status']} -- {jd['reason']}")
        assert (jd.get("prerequisite") or {}).get("needs") == ["numpy"], (
            f"a numpy-less surface must state the ifc route's ONE prerequisite (go.prerequisite): {jd}")
        assert jd["seconds"] < PREFLIGHT_CEILING, (
            f"stating the prerequisite took {jd['seconds']}s (ceiling {PREFLIGHT_CEILING}s) -- "
            "it must stay a preflight-cost answer, not a job that starts and stops")


@pytest.mark.parametrize("name, calls", [("ifc-harden", 4), ("go-ifc-harden", 1)],
                         ids=["four-calls", "one-call"])
def test_ifc_skill_flow_hardens_or_states_its_prerequisite(bench, ifc_skill_report, tmp_path, name, calls):
    """The tekton-ifc flow on a bare surface -- the documented four calls
    (`ifc-harden`, #113) and its ONE-call form (`go-ifc-harden` =
    scripts/ifc_flow.py, #754) -- is PASS (the wheels present: the hardened
    file reopens clean, the sample's score rises, under IFC_SKILL_CEILING;
    the one call also faster than the four measured in the same run) or
    BLOCKED (absent: one call, the missing prerequisite named, at preflight
    cost) -- never FAIL, never a silent SKIPPED."""
    jd = _job(ifc_skill_report, name)
    assert jd["status"] in ("PASS", "BLOCKED"), (
        f"the tekton-ifc flow ({name}) on a bare surface is {jd['status']}: {jd['reason']}")
    if _bare_has(bench, _bare_python(), bench.IFC_SKILL_NEEDS, tmp_path):
        assert jd["status"] == "PASS", (
            f"ifcopenshell + numpy are on the bare python but {name} did not run: {jd['reason']}")
        assert jd["shell_calls"] == calls, f"{name} must stay {calls} shell call(s)"
        bd = jd.get("breakdown") or {}
        assert bd.get("schema_errors_after") == 0, f"the hardened file must reopen clean: {bd}"
        assert bd.get("score_after", 0) > bd.get("score_before", 0), (
            f"hardening the sample must raise its fidelity score: {bd}")
        assert jd["seconds"] < IFC_SKILL_CEILING, (
            f"bare-env {name} took {jd['seconds']}s (ceiling {IFC_SKILL_CEILING}s) -- "
            "the tools' cold start regressed (a heavier import? an extra parse or analysis?)")
        if name == "go-ifc-harden":
            four = _job(ifc_skill_report, "ifc-harden")
            assert jd["seconds"] < four["seconds"], (
                f"the one-call flow ({jd['seconds']}s) is not faster than the four calls "
                f"({four['seconds']}s) in the same run -- it must import once and analyse twice, not four times")
    else:
        assert jd["status"] == "BLOCKED", (
            f"ifcopenshell/numpy are absent but {name} was not gated at its first import: "
            f"{jd['status']} -- {jd['reason']}")
        assert jd["shell_calls"] == 1, "a blocked flow must stop at the first failed import"
        needs = (jd.get("prerequisite") or {}).get("needs") or []
        assert needs and set(needs) <= set(bench.IFC_SKILL_NEEDS), (
            f"the BLOCKED row must state which of {bench.IFC_SKILL_NEEDS} is missing: {jd}")
        assert jd["seconds"] < PREFLIGHT_CEILING, (
            f"stating the prerequisite took {jd['seconds']}s (ceiling {PREFLIGHT_CEILING}s) -- "
            "it must fail at import, not start a job")


def test_session_shell_call_budget(bench_report):
    """The choreography budget: a new mandatory call in any canonical flow is
    a regression on every surface (each call is a model round-trip)."""
    total = sum(j["shell_calls"] for j in bench_report["jobs"])
    assert total <= SESSION_CALL_BUDGET, (
        f"the canonical preflight+author+edit+flagship session now takes {total} shell "
        f"calls (budget {SESSION_CALL_BUDGET}) -- a flow grew an extra round-trip")

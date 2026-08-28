"""tekton-ifc's ONE-call flow: ``scripts/ifc_flow.py`` and the `go-ifc-harden` bench row (issue #754).

The tekton-ifc (Claude Design / Cowork) skill's documented flow on a foreign
IFC is validate -> harden -> re-validate -> report; #113 measured it as FOUR
shell calls (each a model round-trip, each importing ifcopenshell, the file
analysed four times).  ``ifc_flow.py`` runs the same four steps in ONE process
(one import, the input parsed + analysed once and the hardened output once:
``harden_ifc.harden_analysed`` takes the input's report and hands back the
output's) and prints ONE JSON; ``job_go_ifc_harden`` benches that one call
next to the four-call row.  Pinned here without ifcopenshell (fresh-clone
safe, in the CI shard through tests/ci_shard.d/):

* the bench row: canonical job, BLOCKED at the first import when the wheels
  are missing, FAIL in the tool's own words (its envelope `line`) for a
  hardened file with schema errors -- the files still kept -- or any other
  failure, PASS with the same breakdown/notes shape as `ifc-harden`;
* the tool's contract, with the three engine modules stubbed: the five files
  are written whatever the verdict (exit 1 keeps them: hard rule 1), exit 2 for
  a missing/unreadable input with nothing written, the JSON envelope's shape,
  the input's report handed to harden_analysed (analysed ONCE), the harden
  flags passed through, --quiet;
* and, when the real ifcopenshell wheel is importable (conftest's ONE gate --
  the engine's steplite shim never counts), the real tool on the plugin's
  sample: exit 0, five files, a higher score after, 0 schema errors, exactly
  two analyses, and report.md byte-identical to report.py's rendering.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import types

import pytest
from conftest import ROOT, load_tool, needs_ifc_authoring
from test_ifc_skill_bench_113 import NO_IFCOS, NO_NUMPY
from test_surface_bench_reason import _inv

SCRIPTS = os.path.join(ROOT, "skills", "tekton-ifc", "scripts")
FLOW = os.path.join(SCRIPTS, "ifc_flow.py")
SAMPLE = os.path.join(ROOT, "plugin", "skills", "tekton-author", "examples", "electrical-room-2500a.ifc")
FILES = {"validate": "validate.json", "hardened": "hardened.ifc", "harden": "harden.json",
         "validate_after": "validate-after.json", "report": "report.md"}


@pytest.fixture(scope="module")
def bench():
    return load_tool("surface_bench")


# --------------------------------------------------------------------------- #
# the bench row on a fake surface
# --------------------------------------------------------------------------- #

def _envelope(out_dir: str, errors: int = 0) -> dict:
    ok = errors == 0
    return {
        "engine": "tekton-ifc flow", "engine_version": "0.1.0",
        "input": SAMPLE, "out_dir": out_dir, "ok": ok,
        "line": (f"hardened: score 35.7 -> 77.0, 0 schema errors after, 5 files under {out_dir}" if ok else
                 f"the hardened file has {errors} schema error(s) -- delivered under {out_dir}, fix before linking"),
        "before": {"score": 35.7, "tier": "Tier 0 (v1-like) -- imports as frozen DirectShape blobs",
                   "schema_errors": 0},
        "after": {"score": 77.0, "tier": "Tier 1 (partial) -- imports usably but some come in frozen",
                  "schema_errors": errors},
        "actions": {"boxes_converted": 124, "product_globalids_preserved": 13,
                    "products_before": 14, "products_after": 13},
        "files": {role: os.path.join(out_dir, name) for role, name in FILES.items()},
        "stages": [{"stage": "validate", "seconds": 0.6}, {"stage": "harden+re-validate", "seconds": 0.7},
                   {"stage": "report", "seconds": 0.0}],
        "seconds": 1.3,
    }


class _FakeFlowSurface:
    """Just enough Surface for ``job_go_ifc_harden``: ONE canned answer
    (exit, stdout, stderr) and, when ``deliver`` is set, the five files the
    tool would have written under the ``--out`` dir the job asked for."""

    def __init__(self, bench, workdir: str, exit_code: int, stdout: str = "", stderr: str = "",
                 deliver: bool = False):
        self._bench, self._answer, self._deliver = bench, (exit_code, stdout, stderr), deliver
        self.call_no, self.workdir, self.plugin_dir = 0, workdir, workdir
        self.argvs, self.kept = [], []

    def stage_input(self, path: str) -> str:
        return path

    def keep_artifact(self, path: str, name: str) -> str:
        self.kept.append(name)
        return path

    def run(self, label, argv_builder):
        self.call_no += 1
        argv = argv_builder(self)
        self.argvs.append(argv)
        if self._deliver:
            out_dir = argv[argv.index("--out") + 1]
            os.makedirs(out_dir, exist_ok=True)
            for name in FILES.values():
                with open(os.path.join(out_dir, name), "w") as fh:
                    fh.write("x")
        exit_code, stdout, stderr = self._answer
        return _inv(self._bench, stdout=stdout, stderr=stderr, exit_code=exit_code)


def _out_dir(tmp_path) -> str:
    return os.path.join(str(tmp_path), "go-ifc-1")


KEPT = sorted("go-ifc-" + name for name in FILES.values())


def test_go_ifc_harden_is_a_canonical_job_next_to_the_four_call_row(bench):
    assert "go-ifc-harden" in bench.JOBS
    assert bench.JOB_ORDER.index("go-ifc-harden") == bench.JOB_ORDER.index("ifc-harden") + 1


def test_the_one_call_asks_for_the_flow_tool_with_json_and_keeps_its_files(bench, tmp_path):
    s = _FakeFlowSurface(bench, str(tmp_path), 0, json.dumps(_envelope(_out_dir(tmp_path))), deliver=True)
    job = bench.job_go_ifc_harden(s, {})
    assert job.status == "PASS", job.reason
    assert job.calls == 1
    (argv,) = s.argvs
    assert argv[0] == os.path.join(str(tmp_path), bench.IFC_SKILL_SCRIPTS_REL, "ifc_flow.py")
    assert argv[1] == os.path.join(str(tmp_path), bench.IFC_EXAMPLE_REL)
    assert argv[2:] == ["--out", _out_dir(tmp_path), "--json"]
    assert sorted(s.kept) == KEPT


def test_pass_reports_the_same_breakdown_shape_as_the_four_call_row(bench, tmp_path):
    s = _FakeFlowSurface(bench, str(tmp_path), 0, json.dumps(_envelope(_out_dir(tmp_path))))
    bd = bench.job_go_ifc_harden(s, {}).breakdown
    assert bd["score_before"] == 35.7 and bd["score_after"] == 77.0
    assert bd["tier_before"] == "Tier 0 (v1-like)" and bd["tier_after"] == "Tier 1 (partial)"
    assert bd["schema_errors_after"] == 0 and bd["boxes_converted"] == 124
    assert (bd["products_before"], bd["products_after"], bd["globalids_preserved"]) == (14, 13, 13)
    assert [st["stage"] for st in bd["stages"]] == ["validate", "harden+re-validate", "report"]
    assert bd["job_seconds"] == 1.3
    assert bd["summary"] == ("score 35.7 -> 77.0 (Tier 0 (v1-like) -> Tier 1 (partial)); 124 boxes -> "
                             "extrusions; products 14 -> 13; GlobalIds 13/13 kept; schema errors after 0")
    assert bench._fmt_breakdown(bd).startswith("job 1.3s = validate 0.6s · harden+re-validate 0.7s · report 0.0s; score")


@pytest.mark.parametrize("stderr, needs", [(NO_NUMPY, ["numpy"]), (NO_IFCOS, ["ifcopenshell"])])
def test_missing_wheels_block_at_the_first_import(bench, tmp_path, stderr, needs):
    s = _FakeFlowSurface(bench, str(tmp_path), 1, "", stderr)
    job = bench.job_go_ifc_harden(s, {})
    assert job.status == "BLOCKED"
    assert job.prerequisite == {"route": "ifc-skill", "needs": needs, "fix": bench.IFC_SKILL_FIX}
    assert job.reason.endswith(f"needs {' + '.join(needs)} ({bench.IFC_SKILL_FIX})")
    assert job.calls == 1


def test_a_hardened_file_with_schema_errors_is_fail_in_the_tools_words_but_delivered(bench, tmp_path):
    env = _envelope(_out_dir(tmp_path), errors=3)
    s = _FakeFlowSurface(bench, str(tmp_path), 1, json.dumps(env, indent=2), deliver=True)
    job = bench.job_go_ifc_harden(s, {})
    assert job.status == "FAIL"
    assert job.reason == "ifc_flow failed: " + env["line"]      # the tool's verdict, not the bench's
    assert sorted(s.kept) == KEPT


def test_a_usage_or_io_failure_is_fail_in_the_tools_own_words(bench, tmp_path):
    s = _FakeFlowSurface(bench, str(tmp_path), 2, "", "error: no such file: /x/y.ifc\n")
    job = bench.job_go_ifc_harden(s, {})
    assert job.status == "FAIL"
    assert job.reason == "ifc_flow failed: error: no such file: /x/y.ifc"


def test_an_envelope_without_scores_is_fail(bench, tmp_path):
    s = _FakeFlowSurface(bench, str(tmp_path), 0, json.dumps({"ok": True, "files": {}}))
    job = bench.job_go_ifc_harden(s, {})
    assert job.status == "FAIL"
    assert job.reason == "ifc_flow printed no before/after score"


# --------------------------------------------------------------------------- #
# the tool's own contract (engine modules stubbed: no ifcopenshell, no numpy)
# --------------------------------------------------------------------------- #

BEFORE_REP = {"score": {"score": 35.7, "tier": "Tier 0 (v1-like) -- frozen"}, "schema": {"n_errors": 0}}
AFTER_REP = {"score": {"score": 77.0, "tier": "Tier 1 (partial) -- usable"}, "schema": {"n_errors": 0}}


def _stub_engine(errors_after: int = 0):
    """Stand-ins for ifcopenshell / bridge_lib / harden_ifc / report with the
    flow's contract: open() answers a model token (raises on a 'junk' path),
    analyze() a canned report, harden_analysed() writes its output and
    returns ``(result, after_report)`` like the real one, render() a marker.
    ``calls`` records what the flow handed each of them."""
    calls = {"open": [], "analyze": [], "harden": []}
    ios = types.ModuleType("ifcopenshell")

    def open_(path):
        if "junk" in os.path.basename(path):
            raise ValueError("Unable to parse IFC SPF header")
        calls["open"].append(path)
        return ("model", path)

    ios.open = open_
    bl = types.ModuleType("bridge_lib")
    bl.ENGINE_VERSION = "stub"

    def analyze(path, model=None):
        calls["analyze"].append((path, model))
        return dict(BEFORE_REP, file=path)

    def dump_json(rep, path):
        with open(path, "w") as fh:
            json.dump(rep, fh, default=str)

    bl.analyze, bl.dump_json = analyze, dump_json
    hz = types.ModuleType("harden_ifc")

    def harden_analysed(in_path, out_path, before_report, *, model=None, **opts):
        calls["harden"].append({"before": before_report, "model": model, "opts": opts})
        with open(out_path, "w") as fh:
            fh.write("ISO-10303-21;\n")
        result = {"before": {"score": 35.7}, "after": {"score": 77.0},
                  "actions": {"boxes_converted": 124, "product_globalids_preserved": 13,
                              "products_before": 14, "products_after": 13},
                  "schema_after": {"errors": errors_after, "warnings": 0, "reopened": True}, "log": []}
        return result, dict(AFTER_REP, schema={"n_errors": errors_after}, file=out_path)

    def add_harden_args(ap):
        for flag in ("--keep-clearance-as-space", "--no-remove-phantoms", "--no-create-types", "--no-extrusions"):
            ap.add_argument(flag, action="store_true")

    hz.harden_analysed, hz.add_harden_args = harden_analysed, add_harden_args
    hz.harden_kwargs = lambda a: {"remove_phantoms": not a.no_remove_phantoms,
                                  "clearance_as_space": a.keep_clearance_as_space,
                                  "create_types": not a.no_create_types, "extrusions": not a.no_extrusions}
    rp = types.ModuleType("report")
    rp.render = lambda rep, cmp=None: "# stub report" + (" with before/after" if cmp else "")
    return {"ifcopenshell": ios, "bridge_lib": bl, "harden_ifc": hz, "report": rp}, calls


@pytest.fixture
def flow(monkeypatch):
    """``ifc_flow`` imported fresh against stubbed engine modules; returns
    ``(module, calls)`` -- call ``flow.main(argv)`` like the CLI."""
    def _load(errors_after: int = 0):
        stubs, calls = _stub_engine(errors_after)
        for name, mod in stubs.items():
            monkeypatch.setitem(sys.modules, name, mod)
        spec = importlib.util.spec_from_file_location("ifc_flow_under_test", FLOW)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        return m, calls
    return _load


def _files_in(out_dir: str) -> list:
    return sorted(os.listdir(out_dir)) if os.path.isdir(out_dir) else []


def test_one_call_writes_the_five_files_and_prints_one_json(flow, tmp_path, capsys):
    m, calls = flow()
    src = tmp_path / "in.ifc"
    src.write_text("ISO-10303-21;\n")
    out = str(tmp_path / "out")
    assert m.main([str(src), "--out", out, "--json"]) == 0
    assert _files_in(out) == sorted(FILES.values())
    env = json.loads(capsys.readouterr().out)
    assert env["ok"] is True
    assert env["line"] == f"hardened: score 35.7 -> 77.0, 0 schema errors after, 5 files under {out}"
    assert env["before"] == {"score": 35.7, "tier": "Tier 0 (v1-like) -- frozen", "schema_errors": 0}
    assert env["after"] == {"score": 77.0, "tier": "Tier 1 (partial) -- usable", "schema_errors": 0}
    assert env["actions"]["boxes_converted"] == 124
    assert env["files"] == {role: os.path.join(out, name) for role, name in FILES.items()}
    assert [st["stage"] for st in env["stages"]] == ["validate", "harden+re-validate", "report"]
    assert env["seconds"] == round(sum(st["seconds"] for st in env["stages"]), 3)
    # parsed once, analysed once, and THAT report + model handed to harden_analysed (#754's saving)
    assert calls["open"] == [str(src)]
    assert calls["analyze"] == [(str(src), ("model", str(src)))]
    (h,) = calls["harden"]
    assert h["before"]["file"] == str(src) and h["model"] == ("model", str(src))
    assert (tmp_path / "out" / "report.md").read_text() == "# stub report with before/after\n"
    assert json.load(open(os.path.join(out, "validate-after.json")))["score"]["score"] == 77.0


def test_schema_errors_after_exit_1_with_every_file_still_delivered(flow, tmp_path, capsys):
    m, _ = flow(errors_after=2)
    src = tmp_path / "in.ifc"
    src.write_text("ISO-10303-21;\n")
    out = str(tmp_path / "out")
    assert m.main([str(src), "--out", out]) == 1
    assert _files_in(out) == sorted(FILES.values()), "exit 1 delivers the files -- never withheld (hard rule 1)"
    text = capsys.readouterr().out
    assert "schema errors : 0 -> 2 after hardening" in text
    assert f"verdict       : the hardened file has 2 schema error(s) -- delivered under {out}, fix before linking" in text


def test_missing_or_unreadable_input_is_exit_2_with_nothing_written(flow, tmp_path, capsys):
    m, calls = flow()
    out = str(tmp_path / "out")
    assert m.main([str(tmp_path / "nope.ifc"), "--out", out]) == 2
    assert calls["analyze"] == [] and _files_in(out) == []
    junk = tmp_path / "junk.ifc"
    junk.write_text("not an ifc\n")
    assert m.main([str(junk), "--out", out]) == 2
    assert _files_in(out) == []
    err = capsys.readouterr().err
    assert "no such file" in err and "could not run the flow" in err and "IFC SPF header" in err


def test_harden_flags_pass_through_and_quiet_prints_nothing(flow, tmp_path, capsys):
    m, calls = flow()
    src = tmp_path / "in.ifc"
    src.write_text("ISO-10303-21;\n")
    assert m.main([str(src), "--out", str(tmp_path / "o1"), "--quiet"]) == 0
    assert capsys.readouterr().out == ""
    assert calls["harden"][-1]["opts"] == {"remove_phantoms": True, "clearance_as_space": False,
                                           "create_types": True, "extrusions": True}
    assert m.main([str(src), "--out", str(tmp_path / "o2"), "--quiet", "--no-extrusions",
                   "--no-create-types", "--no-remove-phantoms", "--keep-clearance-as-space"]) == 0
    assert calls["harden"][-1]["opts"] == {"remove_phantoms": False, "clearance_as_space": True,
                                           "create_types": False, "extrusions": False}


# --------------------------------------------------------------------------- #
# the real tool, when the real wheel is importable
# --------------------------------------------------------------------------- #

@needs_ifc_authoring
def test_real_flow_on_the_sample_matches_the_four_tools(tmp_path):
    out = str(tmp_path / "flow")
    p = subprocess.run([sys.executable, FLOW, SAMPLE, "--out", out, "--json"],
                       capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr[-800:]
    env = json.loads(p.stdout)
    assert _files_in(out) == sorted(FILES.values())
    assert env["ok"] and env["after"]["schema_errors"] == 0
    assert env["after"]["score"] > env["before"]["score"]
    assert env["actions"]["product_globalids_preserved"] == env["actions"]["products_after"]
    # the delivery report is exactly what report.py renders from the same JSON
    q = subprocess.run([sys.executable, os.path.join(SCRIPTS, "report.py"),
                        env["files"]["validate"], "--compare", env["files"]["harden"],
                        "-o", str(tmp_path / "report-by-hand.md")], capture_output=True, text=True, timeout=120)
    assert q.returncode == 0, q.stderr[-400:]
    assert (tmp_path / "report-by-hand.md").read_text() == open(env["files"]["report"]).read()


@needs_ifc_authoring
def test_real_flow_analyses_the_file_exactly_twice(tmp_path):
    """The saving #754 claims: bridge_lib.analyze runs once on the input and
    once on the reopened output -- counted in a child process (nothing heavy
    imported here) by wrapping the function the flow and harden both call."""
    probe = ("import sys; sys.path.insert(0, %r); import bridge_lib as bl, ifc_flow\n"
             "n = [0]; real = bl.analyze\n"
             "def counted(path, model=None):\n"
             "    n[0] += 1\n"
             "    return real(path, model=model)\n"
             "bl.analyze = counted\n"
             "rc = ifc_flow.main([%r, '--out', %r, '--quiet'])\n"
             "print(n[0], rc)" % (SCRIPTS, SAMPLE, str(tmp_path / "flow")))
    p = subprocess.run([sys.executable, "-c", probe], capture_output=True, text=True, timeout=300)
    assert p.returncode == 0, p.stderr[-800:]
    assert p.stdout.split() == ["2", "0"], p.stdout

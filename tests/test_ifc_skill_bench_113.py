"""surface_bench `ifc-harden`: the tekton-ifc skill's flow is benched with an honest verdict (issue #113).

The tekton-ifc (Claude Design / Cowork) skill runs plain CLIs under
``skills/tekton-ifc/scripts/`` -- no `rvt`, no `_bootstrap.py`, importing
ifcopenshell + numpy -- and its documented flow on a foreign IFC is
validate_ifc.py -> harden_ifc.py -> validate_ifc.py again -> report.py.
``job_ifc_harden`` runs exactly those four calls; pinned here with a fake
surface (no plugin build, no bare interpreter, no ifcopenshell -- fresh-clone
safe, in the CI shard through tests/ci_shard.d/): BLOCKED at the first call
when the wheels are missing, FAIL for any other failure (in the call's own
words), the four argv shapes and their chaining, the breakdown + notes line,
and that the declared prerequisites are the skill's own requirements.txt.
"""
from __future__ import annotations

import json
import os
import re

import pytest
from conftest import ROOT, load_tool
from test_surface_bench_reason import _inv


@pytest.fixture(scope="module")
def bench():
    return load_tool("surface_bench")


def _validate_json(score: float, tier: str) -> dict:
    return {"schema": {"ran": True, "schema": "IFC4", "n_errors": 0, "n_warnings": 0},
            "score": {"score": score, "tier": tier, "stats": {}}}


HARDEN_JSON = {"actions": {"boxes_converted": 124, "product_globalids_preserved": 13,
                           "products_before": 14, "products_after": 13},
               "schema_after": {"errors": 0, "warnings": 0, "reopened": True}}
BEFORE = _validate_json(35.7, "Tier 0 (v1-like) -- imports as frozen DirectShape blobs")
AFTER = _validate_json(77.0, "Tier 1 (partial) -- imports usably but some elements come in frozen")


class _FakeIfcSurface:
    """Just enough Surface for ``job_ifc_harden``: ``run`` answers each call
    with a canned (exit, stderr) and PLANTS the files that call would have
    written (from ``--json`` / ``-o`` / ``--report`` in the argv the job built),
    so the job reads real JSON back like it does for real.  Persistent
    semantics: inputs are used in place, artifacts are kept where they are."""

    def __init__(self, bench, workdir: str, answers: list):
        self._bench, self._answers = bench, list(answers)
        self.call_no, self.workdir, self.plugin_dir = 0, workdir, workdir
        self.labels, self.argvs = [], []

    def stage_input(self, path: str) -> str:
        return path

    def keep_artifact(self, path: str, name: str) -> str:
        return path

    def run(self, label, argv_builder):
        self.call_no += 1
        argv = argv_builder(self)
        self.labels.append(label)
        self.argvs.append(argv)
        exit_code, stderr, outputs = self._answers.pop(0)      # an unplanned call is an IndexError
        for flag, payload in outputs.items():
            with open(argv[argv.index(flag) + 1], "w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload) if isinstance(payload, dict) else payload)
        return _inv(self._bench, stderr=stderr, exit_code=exit_code)


NO_NUMPY = ('Traceback (most recent call last):\n  File "validate_ifc.py", line 23, in <module>\n'
            '    import bridge_lib\n  File "bridge_lib.py", line 20, in <module>\n'
            '    import numpy as np\nModuleNotFoundError: No module named \'numpy\'\n')
NO_IFCOS = "ModuleNotFoundError: No module named 'ifcopenshell.util'\n"


def _happy_path():
    """Answers for the four documented calls, in order."""
    return [(0, "", {"--json": BEFORE}),
            (0, "", {"-o": "ISO-10303-21;\n", "--report": HARDEN_JSON}),
            (0, "", {"--json": AFTER}),
            (0, "", {"-o": "# delivery report\n"})]


def test_ifc_harden_is_a_canonical_job_of_its_own(bench):
    # its own session, after every `go` job (its one-call form, #754, follows it)
    assert bench.JOB_ORDER.index("ifc-harden") > bench.JOB_ORDER.index("go-edit")
    assert bench.JOB_ORDER[-2:] == ("ifc-harden", "go-ifc-harden")
    assert bench.JOBS["ifc-harden"] is bench.job_ifc_harden


def test_declared_prerequisites_are_the_skills_own_requirements(bench):
    """IFC_SKILL_NEEDS mirrors scripts/requirements.txt (package names, its
    order) so a wheel added there cannot silently turn BLOCKED into FAIL."""
    req = os.path.join(ROOT, "skills", "tekton-ifc", "scripts", "requirements.txt")
    with open(req, encoding="utf-8") as fh:
        names = [re.split(r"[<>=!~ ]", ln.strip(), 1)[0] for ln in fh
                 if ln.strip() and not ln.lstrip().startswith("#")]
    assert tuple(names) == bench.IFC_SKILL_NEEDS
    assert bench.IFC_SKILL_FIX.endswith("scripts/requirements.txt")


@pytest.mark.parametrize("stderr, needs", [(NO_NUMPY, ["numpy"]), (NO_IFCOS, ["ifcopenshell"]),
                                           (NO_IFCOS + NO_NUMPY, ["ifcopenshell", "numpy"])])
def test_missing_wheels_block_at_the_first_call(bench, tmp_path, stderr, needs):
    s = _FakeIfcSurface(bench, str(tmp_path), [(1, stderr, {})])
    job = bench.job_ifc_harden(s, {})
    assert job.status == "BLOCKED" and job.calls == 1
    assert job.prerequisite == {"route": "ifc-skill", "needs": needs, "fix": bench.IFC_SKILL_FIX}
    assert job.reason == ("tekton-ifc tools cannot import on this interpreter: needs "
                          + " + ".join(needs) + f" ({bench.IFC_SKILL_FIX})")
    assert "breakdown" not in job.as_dict()


def test_a_non_import_failure_is_still_fail(bench, tmp_path):
    s = _FakeIfcSurface(bench, str(tmp_path), [(2, "validate_ifc.py: error: not an IFC (STEP) file\n", {})])
    job = bench.job_ifc_harden(s, {})
    assert job.status == "FAIL" and job.calls == 1
    assert job.reason == "validate_ifc failed: validate_ifc.py: error: not an IFC (STEP) file"
    assert "prerequisite" not in job.as_dict()


def test_the_four_documented_calls_chain_their_outputs(bench, tmp_path):
    s = _FakeIfcSurface(bench, str(tmp_path), _happy_path())
    job = bench.job_ifc_harden(s, {})
    assert job.status == "PASS" and job.reason == "" and job.calls == 4
    assert s.labels == ["validate_ifc (sample)", "harden_ifc", "validate_ifc (hardened)",
                        "report (before/after)"]
    scripts = os.path.join(s.plugin_dir, "skills", "tekton-ifc", "scripts")
    sample = os.path.join(s.plugin_dir, bench.IFC_EXAMPLE_REL)
    v1, h, v2, r = s.argvs
    assert v1[:2] == [os.path.join(scripts, "validate_ifc.py"), sample] and "--json" in v1
    assert h[:2] == [os.path.join(scripts, "harden_ifc.py"), sample]
    hardened, harden_json = h[h.index("-o") + 1], h[h.index("--report") + 1]
    assert v2[:2] == [os.path.join(scripts, "validate_ifc.py"), hardened]   # the HARDENED file, re-validated
    assert r[:2] == [os.path.join(scripts, "report.py"), v1[v1.index("--json") + 1]]
    assert r[r.index("--compare") + 1] == harden_json                       # before/after from harden's report
    assert all(p.startswith(s.workdir) for p in (v1[-1], hardened, harden_json, v2[-1], r[-1]))
    assert job.breakdown == {
        "stages": [{"stage": st, "seconds": 0.1} for st in ("validate", "harden", "re-validate", "report")],
        "score_before": 35.7, "tier_before": "Tier 0 (v1-like)",
        "score_after": 77.0, "tier_after": "Tier 1 (partial)",
        "schema_errors_after": 0, "boxes_converted": 124, "globalids_preserved": 13,
        "products_before": 14, "products_after": 13,
        "summary": ("score 35.7 -> 77.0 (Tier 0 (v1-like) -> Tier 1 (partial)); 124 boxes -> extrusions; "
                    "products 14 -> 13; GlobalIds 13/13 kept; schema errors after 0")}


def test_a_hardened_file_that_does_not_reopen_clean_is_fail(bench, tmp_path):
    answers = _happy_path()
    answers[1] = (1, "reopened OK, schema errors after = 3\n", {"-o": "ISO-10303-21;\n", "--report": HARDEN_JSON})
    s = _FakeIfcSurface(bench, str(tmp_path), answers)
    job = bench.job_ifc_harden(s, {})
    assert job.status == "FAIL" and job.calls == 2
    assert job.reason == "harden_ifc failed: reopened OK, schema errors after = 3"


def test_a_validate_report_without_a_score_is_fail(bench, tmp_path):
    s = _FakeIfcSurface(bench, str(tmp_path), [(0, "", {"--json": {"engine": "x"}})])
    job = bench.job_ifc_harden(s, {})
    assert job.status == "FAIL" and job.calls == 1 and job.reason == "validate_ifc wrote no score"


def test_markdown_notes_render_the_stage_times_and_what_hardening_did(bench, tmp_path):
    s = _FakeIfcSurface(bench, str(tmp_path), _happy_path())
    job = bench.job_ifc_harden(s, {})
    report = {"surfaces": [{"surface": "cowork", "model": "m", "python_version": "3.11.15",
                            "extras": {}, "session_setup_seconds": 0.0,
                            "jobs": [job.as_dict()],
                            "session_totals": {"shell_calls": 4, "seconds": 0.4, "extract_seconds": 0.0}}]}
    md = bench.markdown_table(report)
    assert "| ifc-harden | 4 | 0.4s |" in md
    assert ("- cowork / ifc-harden stages: validate 0.1s · harden 0.1s · re-validate 0.1s · report 0.1s; "
            "score 35.7 -> 77.0 (Tier 0 (v1-like) -> Tier 1 (partial)); 124 boxes -> extrusions; "
            "products 14 -> 13; GlobalIds 13/13 kept; schema errors after 0") in md


def test_missing_prerequisite_reads_dotted_modules_in_needs_order(bench):
    needs = bench.IFC_SKILL_NEEDS
    assert bench._missing_prerequisite(_inv(bench, stderr=NO_NUMPY + NO_IFCOS, exit_code=1), needs) == ["ifcopenshell", "numpy"]
    assert bench._missing_prerequisite(_inv(bench, stderr=NO_NUMPY, exit_code=0), needs) == []
    other = _inv(bench, stderr="ModuleNotFoundError: No module named 'pytest'\n", exit_code=1)
    assert bench._missing_prerequisite(other, needs) == []                # not a declared prerequisite

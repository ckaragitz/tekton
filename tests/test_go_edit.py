"""`_bootstrap.py go edit IN.rvt VERB ... -o OUT.rvt` is the WHOLE tekton-edit
skill flow in ONE shell call (issue #111, steer #108: every call is a model
round-trip on an AI surface): inline readiness + the id-based edit + the
structural self-check + THE MANDATORY VALIDATION GATE, one combined JSON on
stdout carrying everything the skill reports -- the written file, Revit N in
/ N out, both gate verdicts, the change report.

Bare-surface style like tests/test_coldstart.py / test_go_target_version.py:
the plugin tree copied to a mount-like temp path, ``python -I -S`` (no
site-packages, so no numpy), every ``RVT_*`` scrubbed; sample-free (the
inputs are the bundled certified genesis bases), so it runs in a fresh clone
and in the CI shard.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")
BARE_PY = [sys.executable, "-I", "-S"]
LEVEL_ID = 1351691                     # "GEN B1 - Basement", present in all three bases
BASE = {2026: "G_ABPD.rvt", 2025: "G_ABPD_2025.rvt", 2024: "G_ABPD_2024.rvt"}

pytestmark = pytest.mark.skipif(
    not all(os.path.isfile(os.path.join(PLUGIN, "assets", "genesis", b)) for b in BASE.values()),
    reason="bundled genesis bases missing")


def _copy_plugin(dst_root: str) -> str:
    dst = os.path.join(dst_root, "plugin copy (go edit)")
    ign = shutil.ignore_patterns("__pycache__", "node_modules", ".pytest_cache", ".DS_Store")
    for part in (".claude-plugin", "skills", "lib", "assets"):
        src = os.path.join(PLUGIN, part)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, part), ignore=ign)
    return dst


@pytest.fixture(scope="module")
def plugin_copy(tmp_path_factory):
    return _copy_plugin(str(tmp_path_factory.mktemp("goedit")))


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("goeditwork"))


def _bootstrap(copy_root: str, skill: str = "tekton-edit") -> str:
    return os.path.join(copy_root, "skills", skill, "scripts", "_bootstrap.py")


def _base(copy_root: str, release: int) -> str:
    return os.path.join(copy_root, "assets", "genesis", BASE[release])


def _go(plugin_copy, workdir, *args, skill="tekton-edit", timeout=600):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    r = subprocess.run(BARE_PY + [_bootstrap(plugin_copy, skill), "go", *args],
                       cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout)
    doc = json.loads(r.stdout)               # stdout is exactly ONE JSON object
    assert doc["go"]["ready"] is True, doc["go"]["preflight_line"]
    assert doc["go"]["exit_code"] == r.returncode
    return r, doc


@pytest.mark.parametrize("release", [2025, 2026])
def test_go_edit_one_call_carries_the_whole_report(plugin_copy, workdir, release):
    out = os.path.join(workdir, f"fresh dir {release}", "edited.rvt")   # parent does not exist yet
    r, doc = _go(plugin_copy, workdir, "edit", _base(plugin_copy, release),
                 "set-level", "--id", str(LEVEL_ID), "--elevation-ft", "5", "-o", out)
    assert r.returncode == 0, r.stderr[-2000:]
    assert doc["go"]["verb"] == "edit"
    assert "stdout" not in doc["go"], "the job printed non-JSON noise"
    # the detected input release rides in the SAME json (no follow-up call, #24)
    assert [i["revit_release"] for i in doc["go"]["inputs"]] == [release]
    res = doc["result"]
    assert res["ok"] is True and res["command"] == "set-level" and res["id"] == LEVEL_ID
    # the written file
    assert res["output"]["path"] == os.path.abspath(out) and os.path.isfile(out)
    assert res["output"]["bytes"] == os.path.getsize(out) > 0
    # Revit N in -> Revit N out, from each file's own BasicFileInfo
    assert res["release"]["input"] == release and res["release"]["output"] == release
    assert f"Revit {release} in, Revit {release} out" in res["release"]["line"]
    # both gates ran INSIDE the call: structural self-check + the mandatory validator
    g = res["gates"]
    assert g["hard_gates_passed"] is True
    assert g["structural"]["status"] == "PASS"
    rep = g["structural"]["report"]
    assert (rep["crc_failures"], rep["ecc_mismatches"], rep["walker_errors"], rep["stamps_ok"]) == (0, 0, 0, True)
    v = g["validation"]
    assert v["status"] == "PASS" and v["errors"] == 0
    assert set(v["layers"]) == {"structure", "consistency", "semantic"}
    assert os.path.isfile(v["report_json"]) and v["report_json"] == res["output"]["validation_json"]
    assert "structural PASS" in g["line"] and "validation PASS (0 errors" in g["line"]
    # the change report: exactly the one Level record replaced, nothing removed
    assert res["report"]["replaced"] == [[102, LEVEL_ID]] and res["report"]["removed_ids"] == []


def test_go_edit_impossible_edit_is_one_clear_line_not_a_traceback(plugin_copy, workdir):
    out = os.path.join(workdir, "never.rvt")
    r, doc = _go(plugin_copy, workdir, "edit", _base(plugin_copy, 2025),
                 "set-level", "--id", "999999999", "--elevation-ft", "5", "-o", out)
    assert r.returncode == 1
    res = doc["result"]
    assert res["ok"] is False and "999999999" in res["error"] and "\n" not in res["error"]
    assert "output" not in res and not os.path.exists(out)
    assert "exception" not in doc["go"] and "Traceback" not in r.stderr
    assert res["release"]["input"] == 2025


def test_go_edit_info_is_the_same_one_call(plugin_copy, workdir):
    """`go edit IN info` (ids + names) rides the same dispatch: result IS the
    inventory (+ ok/command/input/release), not text in go.stdout."""
    r, doc = _go(plugin_copy, workdir, "edit", _base(plugin_copy, 2024), "info")
    assert r.returncode == 0, r.stderr[-2000:]
    res = doc["result"]
    assert res["ok"] is True and res["command"] == "info"
    assert any(l["id"] == LEVEL_ID for l in res["levels"])
    assert res["release"]["input"] == 2024


def test_go_edit_works_from_a_skill_without_rvt_edit(plugin_copy, workdir):
    """`go edit` from tekton-author (no rvt_edit.py beside it) resolves the
    canonical copy beside tekton-edit from the plugin root -- never a search."""
    assert not os.path.isfile(os.path.join(plugin_copy, "skills", "tekton-author",
                                           "scripts", "rvt_edit.py"))
    r, doc = _go(plugin_copy, workdir, "edit", _base(plugin_copy, 2025), "info",
                 skill="tekton-author")
    assert r.returncode == 0, r.stderr[-2000:]
    assert doc["result"]["ok"] is True and doc["result"]["levels"]

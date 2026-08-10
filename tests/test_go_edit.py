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


def test_go_ops_door_result_is_the_manifest(plugin_copy, workdir):
    """`go rvt_job.py edit IN --ops ops.json -o OUT` (the batch/ops door) is
    ONE call whose ``result`` IS the manifest the door writes -- status, all
    four gates, the written file, the op log -- not prose in ``go.stdout`` and
    no second call to read ``OUT.manifest.json`` (issue #267); the progress
    lines went to ``result.output.log``, stderr stays clean."""
    ops = os.path.join(workdir, "ops.json")
    with open(ops, "w") as fh:
        json.dump({"ops": [{"op": "set-level", "id": LEVEL_ID, "elevation_ft": 5}]}, fh)
    out = os.path.join(workdir, "ops door", "edited.rvt")
    r, doc = _go(plugin_copy, workdir, "rvt_job.py", "edit", _base(plugin_copy, 2025),
                 "--ops", ops, "-o", out)
    assert r.returncode == 0, r.stderr[-2000:]
    assert doc["go"]["verb"] == "rvt_job.py"
    assert "stdout" not in doc["go"], "the ops door printed non-JSON on stdout"
    assert r.stderr == ""
    res = doc["result"]
    assert res["mode"] == "edit" and res["exit_code"] == 0
    assert res["status"].startswith("PROOF-ONLY") and res["hard_gates_passed"] is True
    assert res["output"]["path"] == os.path.abspath(out) and os.path.isfile(out)
    assert res["output"]["bytes"] == os.path.getsize(out) > 0
    g = res["gates"]
    assert g["structural"]["status"] == "PASS" and g["identity"]["status"] == "PASS"
    assert g["validation"]["status"] == "PASS" and g["validation"]["errors"] == 0
    assert g["base_provenance"]["base_kind"] == "pinned-composed-genesis"
    assert res["edit"]["edited_ids"] == [LEVEL_ID] and res["edit"]["deleted_ids"] == []
    assert len(res["edit"]["log"]) == 1 and "set-level" in res["edit"]["log"][0]
    # the same object is the manifest on disk (+ exit_code); progress rode the log
    with open(out + ".manifest.json") as fh:
        on_disk = json.load(fh)
    assert {k: v for k, v in res.items() if k != "exit_code"} == on_disk
    assert res["output"]["log"] == out + ".log"
    with open(res["output"]["log"]) as fh:
        assert "[rvt_job] validating" in fh.read()


def _aborted(r, doc, out, code, status_prefix):
    """The ops door's abort shape: exit ``code``, the ONE JSON is a stub whose
    ``status`` names why, nothing written, stderr is that status as exactly ONE
    ``[rvt_job] FAILED (…)`` line -- never a traceback (that rides in
    ``output.log``).  Returns ``result``."""
    assert r.returncode == code, r.stderr[-2000:]
    assert "stdout" not in doc["go"] and "exception" not in doc["go"]
    res = doc["result"]
    assert res["exit_code"] == code and res["status"].startswith(status_prefix), res["status"]
    assert res["output"]["written"] is False and not os.path.exists(out)
    assert r.stderr.splitlines() == [f"[rvt_job] {res['status']}"] and "Traceback" not in r.stderr
    with open(res["output"]["log"]) as fh:               # the diagnostic detail is kept, off stderr
        assert "Traceback (most recent call last)" in fh.read()
    return res


def test_go_ops_door_unplannable_op_is_one_json_stub(plugin_copy, workdir):
    """An unplannable op aborts the whole run (a partial edit is worse than
    none): exit 2, ONE stub, ONE stderr line."""
    ops = os.path.join(workdir, "bad-ops.json")
    with open(ops, "w") as fh:
        json.dump([{"op": "set-level", "id": 999999999, "elevation_ft": 5}], fh)
    out = os.path.join(workdir, "ops door", "never.rvt")
    r, doc = _go(plugin_copy, workdir, "rvt_job.py", "edit", _base(plugin_copy, 2025),
                 "--ops", ops, "-o", out)
    res = _aborted(r, doc, out, 2, "FAILED (planning: ")
    assert res["mode"] == "edit" and "999999999" in res["status"]


def test_go_create_door_unplannable_spec_is_one_json_stub(plugin_copy, workdir):
    """The create door's planning abort is the same shape (a spec the builder
    cannot plan: a level with no ``id``)."""
    spec = os.path.join(workdir, "bad-spec.json")
    with open(spec, "w") as fh:
        json.dump({"project": {"name": "x"}, "levels": [{"name": "Level 1"}],
                   "walls": [], "equipment": []}, fh)
    out = os.path.join(workdir, "create door", "never.rvt")
    r, doc = _go(plugin_copy, workdir, "rvt_job.py", "create", "--spec", spec,
                 "--base", _base(plugin_copy, 2026), "--allow-not-ready", "-o", out,
                 skill="tekton-author")               # the copy with spec_to_rvt.py beside it
    assert _aborted(r, doc, out, 2, "FAILED (planning: ")["mode"] == "create"


def test_go_ops_door_unusable_input_is_one_line_too(plugin_copy, workdir):
    """An abort before any manifest of its own (an ``--ops`` that is not JSON:
    the dispatcher's last resort, exit 1) holds the same law, and the stub's
    ``status`` IS the reason -- nothing to fish out of stderr."""
    bad = os.path.join(workdir, "not-json.txt")
    with open(bad, "w") as fh:
        fh.write("{oops")
    out = os.path.join(workdir, "unusable ops", "never.rvt")
    r, doc = _go(plugin_copy, workdir, "rvt_job.py", "edit", _base(plugin_copy, 2025),
                 "--ops", bad, "-o", out)
    assert _aborted(r, doc, out, 1, "FAILED (edit: JSONDecodeError: ")["mode"] == "edit"


def test_go_edit_works_from_a_skill_without_rvt_edit(plugin_copy, workdir):
    """`go edit` from tekton-author (no rvt_edit.py beside it) resolves the
    canonical copy beside tekton-edit from the plugin root -- never a search."""
    assert not os.path.isfile(os.path.join(plugin_copy, "skills", "tekton-author",
                                           "scripts", "rvt_edit.py"))
    r, doc = _go(plugin_copy, workdir, "edit", _base(plugin_copy, 2025), "info",
                 skill="tekton-author")
    assert r.returncode == 0, r.stderr[-2000:]
    assert doc["result"]["ok"] is True and doc["result"]["levels"]

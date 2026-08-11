"""The fast deterministic bootstrap (plugin/skills/_shared/tekton_env.py +
every skill's scripts/_bootstrap.py shim).

What is proven here (the problem-B kill list):

* the plugin root is resolved STRICTLY from the bootstrap's own file --
  the whole plugin is copied to a temp dir with an unusual, mount-like
  path (spaces, parentheses) and preflight still resolves and reports
  READY from an unrelated working directory;
* the engine imports with NO pip install and NO site-packages at all
  (subprocesses run with ``-I -S``: isolated, no site) -- the bundled
  ``lib/src`` engine plus the vendored olefile are sufficient;
* preflight is ONE call, one readiness line, < 2 s;
* the ``run`` launcher executes a sibling skill script (the front door's
  prompt route) from the copied location with zero setup commands;
* the retired family-donor variable changes nothing: families are
  self-generated from the bundled assets, so preflight/doctor neither read
  nor report ``RVT_FAMILY_DONOR`` (#653);
* no tekton plugin file carries a probeable Autodesk-installation path
  (the HARD RULE: every input comes from bundled assets or a user-supplied
  file -- never from ProgramData/Program Files/Applications Autodesk
  directories).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")

# every readiness line looks like this
LINE_RE = re.compile(r"^tekton: (READY|NOT READY) \| ")

# python -I -S: isolated mode + no site module -> no PYTHONPATH, no user
# site, no site-packages.  If the bootstrap works here, it works without
# pip anywhere.
NO_PIP_PY = [sys.executable, "-I", "-S"]


def _copy_plugin(dst_root: str) -> str:
    """Copy the plugin's load-bearing trees (not the 60 MB examples) to an
    unusual mount-like destination, mimicking a sandbox upload."""
    dst = os.path.join(dst_root, "mnt volume 1 (user files)", "skill uploads",
                       "tekton plugin copy")
    ign = shutil.ignore_patterns("__pycache__", "node_modules", ".pytest_cache",
                                 ".DS_Store")
    for part in (".claude-plugin", "skills", "lib", "assets", "commands"):
        src = os.path.join(PLUGIN, part)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, part), ignore=ign)
    return dst


@pytest.fixture(scope="module")
def plugin_copy(tmp_path_factory):
    return _copy_plugin(str(tmp_path_factory.mktemp("mountlike")))


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    """An unrelated working directory (job outputs land here, proving the
    bootstrap never depends on being run from the plugin folder)."""
    return str(tmp_path_factory.mktemp("elsewhere"))


def _bootstrap(copy_root: str, skill: str = "tekton-author") -> str:
    return os.path.join(copy_root, "skills", skill, "scripts", "_bootstrap.py")


def _run(args, cwd, env_extra=None, timeout=120):
    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


# ---------------------------------------------------------------------------
# preflight from an arbitrary copied location
# ---------------------------------------------------------------------------

def test_preflight_json_from_copied_mountlike_path(plugin_copy, workdir):
    t0 = time.time()
    r = _run(NO_PIP_PY + [_bootstrap(plugin_copy), "--json"], cwd=workdir)
    wall = time.time() - t0
    assert r.returncode == 0, r.stderr
    pf = json.loads(r.stdout)
    # root resolved from the bootstrap's own file, not the cwd
    assert os.path.realpath(pf["plugin_root"]["path"]) == os.path.realpath(plugin_copy)
    assert pf["ok"] is True
    assert pf["python"]["ok"] is True
    # engine importable WITHOUT pip (isolated interpreter, bundled source)
    assert pf["engine"]["ok"] is True, pf["engine"]
    assert pf["engine"]["source"].startswith("bundled source:")
    assert pf["engine"]["facts_store"] is True
    # genesis base present AND sha256-verified against the shipped pin
    g = pf["genesis_base"]
    assert g["present"] and g["sha256_verified"] and g["ok"]
    assert g["revit_release"], "pin's revit_release feeds the version-first question"
    # no family input is reported at all: families are self-generated (#653)
    assert "family_donor" not in pf
    assert "family-donor" not in pf["line"]
    assert pf["specimen"]["status"] in ("bundled", "user-supplied", "missing")
    assert pf["out_dir"]["ok"] is True
    # optional extras are REPORTED (so skills point at `doctor --install`
    # instead of pip-installing on the hot path); under -S they read absent
    assert set(pf["extras"]) == {"numpy", "ifcopenshell"}
    # the <2 s hot-path budget (internal measure; wall clock gets slack)
    assert pf["seconds"] < 2.0, f"preflight took {pf['seconds']}s"
    assert wall < 10.0
    assert LINE_RE.match(pf["line"]), pf["line"]


def test_readiness_line_is_the_only_output(plugin_copy, workdir):
    for skill in ("tekton-author", "tekton-edit", "tekton-inspect", "tekton-native"):
        r = _run(NO_PIP_PY + [_bootstrap(plugin_copy, skill)], cwd=workdir)
        assert r.returncode == 0, (skill, r.stderr)
        lines = [ln for ln in r.stdout.splitlines() if ln.strip()]
        assert len(lines) == 1, (skill, r.stdout)
        assert LINE_RE.match(lines[0]), (skill, lines[0])
        assert "READY" in lines[0]


# ---------------------------------------------------------------------------
# the one-command launcher: run a sibling skill script, engine ready
# ---------------------------------------------------------------------------

def test_run_launcher_frontdoor_prompt_handoff(plugin_copy, workdir):
    # The front door's intent model imports numpy (the one heavy extra a
    # sandbox normally ships; `doctor --install` covers the rest).  Run with
    # -I (isolated env, still no pip step) rather than -S so the
    # interpreter's own site-packages provide it.
    pytest.importorskip("numpy")
    out = os.path.join(workdir, "job-handoff")
    r = _run([sys.executable, "-I"] + [_bootstrap(plugin_copy), "run", "frontdoor.py",
                          "author", "--handoff-only",
                          "--prompt", "an electrical room 20x15 ft rated for 800 A "
                                      "service with one switchboard and two lighting panels",
                          "--out", out, "--json"],
             cwd=workdir)
    assert r.returncode == 0, r.stderr[-2000:]
    res = json.loads(r.stdout)
    assert res["route"] == "prompt"
    assert res["ok"] is True
    assert os.path.isfile(res["intent_json"])
    assert os.path.isfile(res["handoff"]["scene_brief"])
    assert os.path.isfile(res["handoff"]["instructions"])


def test_run_launcher_missing_script_is_one_clear_line(plugin_copy, workdir):
    r = _run(NO_PIP_PY + [_bootstrap(plugin_copy), "run", "no_such_script.py"],
             cwd=workdir)
    assert r.returncode == 2
    assert "not found" in r.stderr


# ---------------------------------------------------------------------------
# the retired family-donor variable changes nothing (#653)
# ---------------------------------------------------------------------------

def test_retired_family_donor_env_changes_nothing(plugin_copy, workdir, tmp_path):
    donor = tmp_path / "their-panel.rfa"
    donor.write_bytes(b"a file the retired variable points at; nothing may read it")
    env = {"RVT_FAMILY_DONOR": str(donor)}
    plain = _run(NO_PIP_PY + [_bootstrap(plugin_copy), "--json"], cwd=workdir)
    withenv = _run(NO_PIP_PY + [_bootstrap(plugin_copy), "--json"], cwd=workdir, env_extra=env)
    assert plain.returncode == withenv.returncode == 0, withenv.stderr
    a, b = json.loads(plain.stdout), json.loads(withenv.stdout)
    for volatile in ("seconds", "line"):          # the line differs only by its timing tail
        a.pop(volatile), b.pop(volatile)
    assert a == b
    assert "family_donor" not in b

    doc = _run(NO_PIP_PY + [_bootstrap(plugin_copy), "doctor"], cwd=workdir, env_extra=env)
    assert doc.returncode == 0, doc.stderr
    assert "family container: bundled (genesis base)" in doc.stdout
    assert "Autodesk" in doc.stdout          # the never-read-an-install assurance stays printed
    for gone in ("FAMILY_DONOR", "family-donor", "user-supplied donor", "override, e.g."):
        assert gone not in doc.stdout, gone


# ---------------------------------------------------------------------------
# legacy --env compatibility (older docs eval these lines)
# ---------------------------------------------------------------------------

def test_legacy_env_exports_still_printed(plugin_copy, workdir):
    r = _run(NO_PIP_PY + [_bootstrap(plugin_copy), "--env"], cwd=workdir)
    assert r.returncode == 0
    assert 'export PYTHONPATH="' in r.stdout
    assert 'export RVT_PLUGIN_ROOT="' in r.stdout
    # RVT_GENESIS_BASE is the USER's override; exporting the bundled default
    # would pin --target-version jobs to 2026 (#92, tests/test_go_target_version.py)
    assert "RVT_GENESIS_BASE" not in r.stdout


# ---------------------------------------------------------------------------
# HARD RULE: no probeable Autodesk-installation path anywhere in the plugin
# ---------------------------------------------------------------------------

# Path-LITERAL forms only (prose that *names* the prohibition is allowed;
# a path you could actually open is not):
_FORBIDDEN = [
    re.compile(r"[A-Za-z]:[\\/]+(?:ProgramData|Program Files(?: \(x86\))?)[\\/]+Autodesk"),
    re.compile(r"/Applications/Autodesk/"),
    re.compile(r"RVT (?:20\d\d|<year>)[\\/]"),
    re.compile(r"Family Templates[\\/]"),
]
_SCAN_EXT = (".py", ".md", ".js", ".json", ".txt", ".html", ".sh")


def test_no_autodesk_install_paths_in_plugin():
    hits = []
    for base, dirs, files in os.walk(PLUGIN):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", "node_modules",
                                                ".pytest_cache")]
        for f in files:
            if not f.lower().endswith(_SCAN_EXT):
                continue
            p = os.path.join(base, f)
            try:
                if os.path.getsize(p) > 4_000_000:
                    continue
                text = open(p, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            for pat in _FORBIDDEN:
                m = pat.search(text)
                if m:
                    hits.append(f"{os.path.relpath(p, ROOT)}: {m.group(0)!r}")
    assert not hits, ("Autodesk installation paths must never appear in the "
                      "plugin (every input comes from bundled assets or a "
                      "user-supplied file only):\n" + "\n".join(hits))

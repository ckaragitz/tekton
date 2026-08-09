"""`_bootstrap.py go author --target-version N` from a bare plugin copy
authors NATIVELY on the bundled Revit-N base (issue #92: the bootstrap used
to export ``RVT_GENESIS_BASE=<plugin>/assets/genesis/G_ABPD.rvt``, which the
engine honours as the user's override ahead of the per-release slot, so
2025/2024 jobs silently fell back to a 2026 file).

Bare-surface style like tests/test_coldstart.py (plugin trees copied to a
temp dir, ``python -I -S``, every ``RVT_*`` scrubbed unless set on purpose),
sample-free.  Resolution is checked cheaply with ``--handoff-only``; one full
build per non-default release proves the bytes.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys

import pytest

from rvt import versions

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN = os.path.join(ROOT, "plugin")

PROMPT = "an electrical room 12x10 ft with one lighting panel"
BARE_PY = [sys.executable, "-I", "-S"]
DEFAULT_RELEASE = 2026
BASE_NAME = {2026: "G_ABPD.rvt", 2025: "G_ABPD_2025.rvt", 2024: "G_ABPD_2024.rvt"}


def _copy_plugin(dst_root: str) -> str:
    dst = os.path.join(dst_root, "plugin copy (target version)")
    ign = shutil.ignore_patterns("__pycache__", "node_modules", ".pytest_cache",
                                 ".DS_Store")
    for part in (".claude-plugin", "skills", "lib", "assets"):
        src = os.path.join(PLUGIN, part)
        if os.path.isdir(src):
            shutil.copytree(src, os.path.join(dst, part), ignore=ign)
    return dst


@pytest.fixture(scope="module")
def plugin_copy(tmp_path_factory):
    return _copy_plugin(str(tmp_path_factory.mktemp("tv")))


@pytest.fixture(scope="module")
def workdir(tmp_path_factory):
    return str(tmp_path_factory.mktemp("tvwork"))


def _bootstrap(copy_root: str, skill: str = "tekton-author") -> str:
    return os.path.join(copy_root, "skills", skill, "scripts", "_bootstrap.py")


def _run(args, cwd, env_extra=None, timeout=600):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("RVT_") and k != "PYTHONPATH"}
    if env_extra:
        env.update(env_extra)
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True,
                          text=True, timeout=timeout)


def _go_author(plugin_copy, workdir, name, *extra, env_extra=None, timeout=600):
    """One `go author` call; returns (combined go JSON, manifest.json dict)."""
    out = os.path.join(workdir, name)
    r = _run(BARE_PY + [_bootstrap(plugin_copy), "go", "author",
                        "--prompt", PROMPT, "--out", out, "--json", *extra],
             cwd=workdir, env_extra=env_extra, timeout=timeout)
    assert r.returncode in (0, 4), r.stderr[-2000:]
    doc = json.loads(r.stdout)
    assert doc["go"]["ready"] is True, doc["go"]["preflight_line"]
    assert doc["result"]["route"] == "prompt"
    with open(os.path.join(out, "manifest.json")) as fh:
        return doc, json.load(fh)


def _assert_native(manifest, year, plugin_copy):
    tv, base = manifest["target_version"], manifest["base"]
    assert tv["status"] == "match", tv
    assert tv["output_release"] == year, tv
    assert base["source"].startswith("pinned"), base      # never "env"
    assert base["certified_genesis_base"] is True, base
    assert os.path.basename(base["path"]) == BASE_NAME[year], base
    assert os.path.realpath(base["path"]).startswith(os.path.realpath(plugin_copy))


# ---------------------------------------------------------------------------
# resolution per release (cheap: --handoff-only resolves base + version block)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2025, 2024, 2026])
def test_go_target_version_resolves_the_bundled_release_base(plugin_copy, workdir, year):
    _, m = _go_author(plugin_copy, workdir, f"handoff-{year}", "--handoff-only",
                      "--target-version", str(year))
    _assert_native(m, year, plugin_copy)


def test_go_without_target_version_is_the_default_release(plugin_copy, workdir):
    _, m = _go_author(plugin_copy, workdir, "handoff-default", "--handoff-only")
    tv, base = m["target_version"], m["base"]
    assert tv["status"] == "unspecified" and tv["requested"] is None, tv
    assert tv["output_release"] == DEFAULT_RELEASE, tv
    assert base["source"].startswith("pinned"), base
    assert os.path.basename(base["path"]) == BASE_NAME[DEFAULT_RELEASE], base


@pytest.mark.parametrize("where", ["bundled", "old-install-copy"])
def test_stale_default_base_env_does_not_override_target_version(plugin_copy, workdir,
                                                                  tmp_path, where):
    """An inherited ``RVT_GENESIS_BASE`` that IS our default base -- the
    bundled file (what older bootstraps / the legacy ``--env`` lines
    exported) or a byte-identical copy left in a previous install dir --
    carries no user intent: it must not pin a 2025 job to the 2026 base."""
    stale = os.path.join(plugin_copy, "assets", "genesis", BASE_NAME[DEFAULT_RELEASE])
    if where == "old-install-copy":
        stale = shutil.copyfile(stale, tmp_path / BASE_NAME[DEFAULT_RELEASE])
    _, m = _go_author(plugin_copy, workdir, f"handoff-stale-{where}", "--handoff-only",
                      "--target-version", "2025",
                      env_extra={"RVT_GENESIS_BASE": str(stale)})
    _assert_native(m, 2025, plugin_copy)


def test_user_supplied_env_base_is_still_honoured(plugin_copy, workdir, tmp_path):
    """A REAL override -- the user's own base living outside the plugin --
    keeps winning (source ``env``), release-checked against the target."""
    theirs = tmp_path / "firm-template-2025.rvt"
    shutil.copyfile(os.path.join(plugin_copy, "assets", "genesis", BASE_NAME[2025]),
                    theirs)
    _, m = _go_author(plugin_copy, workdir, "handoff-user-env", "--handoff-only",
                      "--target-version", "2025",
                      env_extra={"RVT_GENESIS_BASE": str(theirs)})
    tv, base = m["target_version"], m["base"]
    assert tv["status"] == "match" and tv["output_release"] == 2025, tv
    assert base["source"] == "env", base
    assert os.path.realpath(base["path"]) == os.path.realpath(str(theirs))


# ---------------------------------------------------------------------------
# the bytes: a full bare build per non-default release IS that release
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", [2025, 2024])
def test_go_full_build_is_native_to_the_target_release(plugin_copy, workdir, year):
    doc, m = _go_author(plugin_copy, workdir, f"build-{year}",
                        "--target-version", str(year), timeout=900)
    _assert_native(m, year, plugin_copy)
    combined = (doc["result"].get("files") or {}).get("combined")
    assert combined and os.path.isfile(combined), doc["result"].get("files")
    # in-job (release-aware) validation of the combined file: under -I -S the
    # numpy-backed ECC tier states its absence as an in-report ERROR (honest
    # degrade, exit 4 -- tests/test_coldstart.py); every OTHER error is real
    v = m["build"]["validation"]["combined"]["validate"]
    real = [e for e in v.get("errors") or [] if "numpy" not in json.dumps(e)]
    assert not real, real
    # the release the FILE itself says it is (BasicFileInfo), read back independently
    assert versions.detect_release(combined) == year

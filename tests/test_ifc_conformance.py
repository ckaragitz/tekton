"""IFC conformance fixtures (issue #154): our OWN hand-authored IFCs, resolved
by ``rvt.ifc.intent.resolve_intent`` under the stdlib steplite backend, must
match the pinned ``tests/ifc_conformance/<name>.expected.json`` -- and, when
a REAL ifcopenshell is importable, the real library must yield the very same
summary (known divergences are strict xfails citing their issue, never hidden).

Runs in the CI shard WITHOUT ifcopenshell: the resolver is driven in one
child interpreter with ``RVT_STEPLITE_FORCE=1`` (the engine then serves the
bundled shim first even on a laptop that has the wheel), so "green here"
means "green on steplite".  Changing an expectation is a deliberate act:
``python3 tools/dev/make_ifc_fixtures.py --update-expected`` and commit the
diff in the PR that owns the behaviour change (#152 / #155 / #157 / ...).
"""
from __future__ import annotations

import difflib
import importlib.util
import json
import os
import re
import subprocess
import sys

import pytest

from conftest import HAVE_IFC_AUTHORING   # real-library parity needs the real wheel, #367

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "dev", "make_ifc_fixtures.py")

_spec = importlib.util.spec_from_file_location("make_ifc_fixtures", TOOL)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

FX = {fx["name"]: fx for fx in M.FIXTURES}
NAMES = list(FX)
PATHS = {n: os.path.join(M.FIXTURE_DIR, n + ".ifc") for n in NAMES}

needs_numpy = pytest.mark.skipif(importlib.util.find_spec("numpy") is None,
                                 reason="intent placement / geometry maths needs numpy (#127)")


def _diff(want: dict, got: dict) -> str:
    a = json.dumps(want, indent=1, sort_keys=True).splitlines()
    b = json.dumps(got, indent=1, sort_keys=True).splitlines()
    return "\n".join(difflib.unified_diff(a, b, "pinned (.expected.json)", "resolver today", n=2, lineterm=""))


# ---------------------------------------------------------------------------
# the fixtures themselves: owned, small, portable, reproducible
# ---------------------------------------------------------------------------

def test_generator_check_reports_no_drift():
    """``make_ifc_fixtures.py --check`` is the drift gate: the committed .ifc
    bytes ARE what the generator writes, every fixture has its .expected.json
    with a registry-fresh header, and nothing stray sits in the directory."""
    proc = subprocess.run([sys.executable, TOOL, "--check"], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr[-2000:]
    assert proc.stdout.strip().startswith("ok: "), proc.stdout


def test_generator_is_deterministic():
    assert M.render_all() == M.render_all()


@pytest.mark.parametrize("name", NAMES)
def test_fixture_hygiene(name):
    assert re.fullmatch(r"[a-z][a-z0-9_]*", name), "portable, lowercase fixture names only"
    with open(PATHS[name], "rb") as fh:
        raw = fh.read()
    assert len(raw) < M.MAX_BYTES, f"{name}.ifc is {len(raw)} bytes (limit {M.MAX_BYTES})"
    assert b"\r" not in raw, "LF line endings only"
    head = raw[:raw.index(b"DATA;")].decode("ascii")          # comment + HEADER section, pure ASCII
    assert head.startswith("ISO-10303-21;\n")
    assert M.HEADER_MARK in head and M.GENERATOR in head
    assert f"FILE_SCHEMA(('{FX[name]['build']().schema}'));" in head
    if FX[name]["parity_xfail"]:
        assert re.match(r"#\d+", FX[name]["parity_xfail"]), "a parity divergence must cite its issue"


# ---------------------------------------------------------------------------
# resolver behaviour: steplite == pinned; real ifcopenshell == steplite
# ---------------------------------------------------------------------------

def _summaries(force_steplite: bool, backend: str) -> dict:
    """resolve_intent on every fixture in ONE child interpreter; asserts the
    child really ran ``backend`` and strips that key."""
    got = M.resolve_summaries([PATHS[n] for n in NAMES], force_steplite=force_steplite)
    out = {n: got[PATHS[n]] for n in NAMES}
    for n, summary in out.items():
        assert summary.pop("backend") == backend, f"{n}: expected the {backend} backend"
    return out


@pytest.fixture(scope="module")
def lite_summaries():
    return _summaries(True, "steplite")


@pytest.fixture(scope="module")
def real_summaries():
    if not HAVE_IFC_AUTHORING:
        pytest.skip("real ifcopenshell not installed (optional extra .[ifc]); parity runs where it is")
    return _summaries(False, "ifcopenshell")


@needs_numpy
@pytest.mark.parametrize("name", NAMES)
def test_steplite_resolves_to_pinned_expectation(name, lite_summaries):
    want = M.load_expected(name)["expected"]
    got = lite_summaries[name]
    assert got == want, (
        f"{name}: resolver output moved off the pinned expectation.\n{_diff(want, got)}\n"
        f"If this change is INTENDED, re-pin with `python3 tools/dev/make_ifc_fixtures.py "
        f"--update-expected` in the PR that owns it and say so in its record.")


@needs_numpy
@pytest.mark.parametrize("name", [
    pytest.param(n, marks=pytest.mark.xfail(strict=True, reason=FX[n]["parity_xfail"]))
    if FX[n]["parity_xfail"] else n for n in NAMES])
def test_real_ifcopenshell_parity_with_steplite(name, real_summaries, lite_summaries):
    lite, real = lite_summaries[name], real_summaries[name]
    assert real == lite, f"{name}: ifcopenshell and steplite disagree.\n{_diff(lite, real)}"

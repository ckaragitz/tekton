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
import importlib.machinery
import importlib.util
import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "dev", "make_ifc_fixtures.py")
FIX_DIR = os.path.join(ROOT, "tests", "ifc_conformance")
SHIM_DIR = os.path.join(ROOT, "src", "rvt", "ifc", "_ifcos_shim")

_spec = importlib.util.spec_from_file_location("make_ifc_fixtures", TOOL)
M = importlib.util.module_from_spec(_spec)
sys.modules["make_ifc_fixtures"] = M
_spec.loader.exec_module(M)

NAMES = [fx["name"] for fx in M.FIXTURES]
PATHS = {n: os.path.join(FIX_DIR, n + ".ifc") for n in NAMES}


def _load_expected(name: str) -> dict:
    with open(os.path.join(FIX_DIR, name + ".expected.json"), encoding="ascii") as fh:
        return json.load(fh)


EXPECTED = {n: _load_expected(n) for n in NAMES}


def _real_ifcopenshell_importable() -> bool:
    """A REAL ifcopenshell (not the bundled shim) is on sys.path."""
    paths = [p for p in sys.path if os.path.abspath(p or ".") != SHIM_DIR]
    try:
        spec = importlib.machinery.PathFinder.find_spec("ifcopenshell", paths)
    except (ImportError, AttributeError, ValueError):
        return False
    return spec is not None and bool(spec.origin) and SHIM_DIR not in os.path.abspath(spec.origin)


HAVE_REAL_IFCOS = _real_ifcopenshell_importable()
needs_numpy = pytest.mark.skipif(importlib.util.find_spec("numpy") is None,
                                 reason="intent placement / geometry maths needs numpy (#127)")


def _diff(want: dict, got: dict) -> str:
    a = json.dumps(want, indent=1, sort_keys=True).splitlines()
    b = json.dumps(got, indent=1, sort_keys=True).splitlines()
    return "\n".join(difflib.unified_diff(a, b, "pinned (.expected.json)", "resolver today", n=2, lineterm=""))


# ---------------------------------------------------------------------------
# the fixtures themselves: owned, small, portable, reproducible
# ---------------------------------------------------------------------------

def test_registry_and_committed_files_agree():
    ifcs = sorted(f[:-4] for f in os.listdir(FIX_DIR) if f.endswith(".ifc"))
    exps = sorted(f[:-len(".expected.json")] for f in os.listdir(FIX_DIR) if f.endswith(".expected.json"))
    assert ifcs == sorted(NAMES) == exps
    assert len(NAMES) >= 9                                  # (a)..(i) of #154's DONE


def test_generator_check_reports_no_drift():
    """``make_ifc_fixtures.py --check`` is the drift gate: the committed .ifc
    bytes ARE what the generator writes (nobody hand-edited a fixture, and a
    generator change re-committed its output)."""
    proc = subprocess.run([sys.executable, TOOL, "--check"], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr[-2000:]
    assert proc.stdout.strip().startswith("ok: "), proc.stdout


def test_generator_is_deterministic():
    assert M.render_all() == M.render_all()


@pytest.mark.parametrize("name", NAMES)
def test_fixture_hygiene(name):
    path = PATHS[name]
    assert re.fullmatch(r"[a-z][a-z0-9_]*", name), "portable, lowercase fixture names only"
    raw = open(path, "rb").read()
    assert len(raw) < M.MAX_BYTES, f"{name}.ifc is {len(raw)} bytes (limit {M.MAX_BYTES})"
    raw.decode("ascii")                                       # pure ASCII STEP text
    assert b"\r" not in raw, "LF line endings only"
    head = raw[:raw.index(b"DATA;")].decode("ascii")          # comment + HEADER section
    assert head.startswith("ISO-10303-21;\n")
    assert M.HEADER_MARK in head and M.GENERATOR in head
    schema = "IFC2X3" if name == "i_schema_ifc2x3" else "IFC4"
    assert f"FILE_SCHEMA(('{schema}'));" in head
    doc = EXPECTED[name]
    assert doc["fixture"] == name and doc["pinned_backend"] == "steplite"
    assert doc["pins"] and isinstance(doc["notes"], list)
    if doc["parity_xfail"]:
        assert re.match(r"#\d+", doc["parity_xfail"]), "a parity divergence must cite its issue"


# ---------------------------------------------------------------------------
# resolver behaviour: steplite == pinned; real ifcopenshell == steplite
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def lite_summaries():
    """resolve_intent on every fixture in ONE child interpreter, shim forced."""
    got = M.resolve_summaries([PATHS[n] for n in NAMES], force_steplite=True)
    return {n: got[PATHS[n]] for n in NAMES}


@pytest.fixture(scope="module")
def real_summaries():
    if not HAVE_REAL_IFCOS:
        pytest.skip("real ifcopenshell not installed (optional extra .[ifc]); parity runs where it is")
    got = M.resolve_summaries([PATHS[n] for n in NAMES], force_steplite=False)
    return {n: got[PATHS[n]] for n in NAMES}


@needs_numpy
@pytest.mark.parametrize("name", NAMES)
def test_steplite_resolves_to_pinned_expectation(name, lite_summaries):
    got = dict(lite_summaries[name])
    assert got.pop("backend") == "steplite", "RVT_STEPLITE_FORCE did not select the bundled shim"
    want = EXPECTED[name]["expected"]
    assert got == want, (
        f"{name}: resolver output moved off the pinned expectation.\n{_diff(want, got)}\n"
        f"If this change is INTENDED, re-pin with `python3 tools/dev/make_ifc_fixtures.py "
        f"--update-expected` in the PR that owns it and say so in its record.")


def _parity_params():
    out = []
    for fx in M.FIXTURES:
        marks = []
        if fx["parity_xfail"]:
            marks.append(pytest.mark.xfail(strict=True, reason=fx["parity_xfail"]))
        out.append(pytest.param(fx["name"], id=fx["name"], marks=marks))
    return out


@needs_numpy
@pytest.mark.parametrize("name", _parity_params())
def test_real_ifcopenshell_parity_with_steplite(name, lite_summaries, real_summaries):
    lite = dict(lite_summaries[name])
    real = dict(real_summaries[name])
    assert lite.pop("backend") == "steplite" and real.pop("backend") == "ifcopenshell"
    assert real == lite, f"{name}: ifcopenshell and steplite disagree.\n{_diff(lite, real)}"

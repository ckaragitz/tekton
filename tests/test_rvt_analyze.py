"""Stream-local tests for tools/rvt_analyze.py (the one-shot analyzer)
and the landed ``rvt_validate --family`` mode.

Everything here runs from a FRESH CLONE: the inputs are the tracked
bundled genesis base and a family generated on the spot by the factory
(standalone resolvers) -- no samples, no experiments artifacts.

Run: .venv/bin/python -m pytest tests/test_rvt_analyze.py -q
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
BASE_2025 = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2025.rvt")
PY = sys.executable

pytestmark = pytest.mark.skipif(
    not os.path.isfile(BASE), reason="bundled genesis base missing")

import rvt_analyze as RA  # noqa: E402


@pytest.fixture(scope="module")
def rfa(tmp_path_factory):
    """A factory-generated family (standalone resolvers when the research
    corpus is absent -- the fresh-clone path)."""
    from rvt import schema as _RS
    if not os.path.isfile(_RS.DEFAULT_PATH):
        from rvt.frontdoor.standalone import activate
        activate()
    from rvt.famgen import factory as F
    prod = F.make_panelboard(mains_a=225, spaces=30, voltage="480Y/277")
    out = str(tmp_path_factory.mktemp("rfa") / "pb.rfa")
    rep = prod.write(out, validate=False)
    assert rep["path"] == out and os.path.isfile(out)
    return out


def test_analyze_bundled_base():
    rep = RA.analyze(BASE, top=5)
    ident = rep["identity"]
    assert ident["kind"] == "project"
    assert ident["release"] == 2026
    assert ident["identity_ours"] is False          # the base keeps sample identity
    from rvt.frontdoor.standalone import SCHEMA_2026_SHA256
    assert rep["schema"]["sha256"] == SCHEMA_2026_SHA256
    assert rep["schema"]["release"] == 2026
    assert rep["container"]["n_streams"] >= 10
    assert rep["census"]["coherence"]["coherent"] is True
    assert rep["validation"]["mode"] == "project"
    assert rep["validation"]["n_errors"] == 0


@pytest.mark.skipif(not os.path.isfile(BASE_2025),
                    reason="bundled 2025 genesis base missing")
def test_analyze_older_release_base_is_coherent():
    """census + validation of a 2025 file run under ITS release (issue #50):
    no silent census error, no spurious validation errors, no fallback."""
    rep = RA.analyze(BASE_2025, top=5)
    assert rep["identity"]["release"] == 2025
    assert "framing" not in rep                          # own release resolved
    assert "error" not in rep["census"], rep["census"]
    assert rep["census"]["host_records"] > 0
    assert rep["validation"]["verdict"] == "VALID", rep["validation"]["errors"]


def test_analyze_states_the_framing_fallback(monkeypatch):
    """If the file's own schema cannot settle its framing the report says
    which rung was used under ``framing`` (here: the pinned table of the
    release BasicFileInfo declares) and the sections still run."""
    import rvt.versions.records32 as R32

    def _unreadable(path):
        raise RuntimeError("schema unreadable (simulated)")
    monkeypatch.setattr(R32, "reading32", _unreadable)
    rep = RA.analyze(BASE, top=5, with_validate=False)
    fb = rep["framing"]["fallback"]
    assert "simulated" in fb and "Revit 2026 framing table" in fb, fb
    assert rep["census"]["coherence"]["coherent"] is True


def test_analyze_generated_family(rfa):
    rep = RA.analyze(rfa, with_provenance=True)
    ident = rep["identity"]
    assert ident["kind"] == "family"
    assert ident["identity_ours"] is True
    assert ident["basic_file_info"]["author"] == "rvt-writer"
    assert rep["validation"]["mode"] == "family"
    assert rep["validation"]["n_errors"] == 0, rep["validation"]["errors"]
    assert rep["provenance"]["ok"] is True
    # the census sees the single family save unit and its class census
    assert rep["census"]["units"]["total"] == 1
    assert "ParamElemFamily" in rep["census"]["top_classes"]


def test_validate_family_mode_flag(rfa):
    """family=True is the landed two-adjustment mode: 0 errors on our
    generated .rfa; project mode reports exactly the family-shape
    calibration findings (ProjectInformation + PartAtom framing)."""
    from rvt.validate import validate_file
    fam = validate_file(rfa, family=True)
    assert not fam.errors, [f"{f.where}: {f.message}" for f in fam.errors]
    raw = validate_file(rfa)
    wheres = {f.where for f in raw.errors}
    assert wheres and wheres <= {"ProjectInformation", "PartAtom"}, wheres


def test_cli_family_autodetect(rfa, tmp_path):
    out = tmp_path / "v.json"
    p = subprocess.run(
        [PY, os.path.join(ROOT, "tools", "rvt_validate.py"), rfa,
         "--json", str(out), "--quiet"],
        capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stdout + p.stderr
    assert json.loads(out.read_text())["ok"] is True
    # forced project mode still fails (the calibration gap, unchanged)
    p2 = subprocess.run(
        [PY, os.path.join(ROOT, "tools", "rvt_validate.py"), rfa,
         "--project", "--quiet"],
        capture_output=True, text=True, cwd=ROOT)
    assert p2.returncode == 1


def test_cli_analyze_json(tmp_path):
    out = tmp_path / "a.json"
    p = subprocess.run(
        [PY, os.path.join(ROOT, "tools", "rvt_analyze.py"), BASE,
         "--json", str(out), "--quiet", "--top", "5"],
        capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0, p.stdout + p.stderr
    rep = json.loads(out.read_text())
    assert rep["identity"]["release"] == 2026
    assert rep["validation"]["n_errors"] == 0
    assert len(rep["census"]["top_classes"]) == 5

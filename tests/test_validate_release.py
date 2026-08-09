"""The validator judges every file under its OWN release (issue #50).

Before, ``rvt_validate`` / ``validate_file`` read every input with the
built-in latest-release framing ordinals, so the certified pinned
G_ABPD_2025 / G_ABPD_2024 bases each reported 4 spurious framing errors.

Fresh-clone runnable: the inputs are the tracked bundled genesis bases.

Run: .venv/bin/python -m pytest tests/test_validate_release.py -q
"""
from __future__ import annotations

import os

import pytest

from rvt import partitions as P
from rvt import versions as V
from rvt.validate import main, validate_file

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}

pytestmark = pytest.mark.skipif(
    not all(os.path.isfile(p) for p in BASES.values()),
    reason="bundled genesis bases missing")


def _msgs(findings):
    return [f"[{f.layer}] {f.where}: {f.message}" for f in findings]


@pytest.fixture(autouse=True)
def _constants_restored():
    """After every test the built-in (latest-release) framing is back."""
    yield
    latest = V.framing_table(V.LATEST_RELEASE)
    assert {k: getattr(P, k) for k in latest} == latest


@pytest.mark.parametrize("year", sorted(BASES))
def test_pinned_base_validates_clean_under_its_own_release(year):
    rep = validate_file(BASES[year])
    assert rep.ok, _msgs(rep.errors)
    infos = _msgs(rep.infos)
    assert any(f"canonical Revit {year} archive schema" in m for m in infos), infos
    assert not any(f.where == "release" for f in rep.findings)   # no fallback taken


def test_cli_exit_zero_on_older_release_bases(capsys):
    assert main([BASES[2025], BASES[2024], "--quiet"]) == 0
    out = capsys.readouterr().out
    assert out.count("OK  ") == 2, out


def test_nested_inside_an_outer_reading_context():
    """validate_file inside a caller's own ``reading`` (the front door does
    this) is nest-safe: the outer ordinals are back when it returns."""
    with V.reading(year=2025) as ords:
        rep = validate_file(BASES[2024])
        assert rep.ok, _msgs(rep.errors)
        assert P.PT_CLASS == ords["PT_CLASS"]


def test_damaged_schema_falls_back_to_the_declared_release_table(tmp_path):
    """A truncated 2025 file (schema stream unreadable) is still judged as a
    2025 file: the pinned table of the release BasicFileInfo declares is
    used and said so at ``release``; the truncation shows as real errors,
    not as latest-release framing mismatches (``cls=0x391`` / ``0xc40``)."""
    trunc = tmp_path / "trunc_2025.rvt"
    with open(BASES[2025], "rb") as fh:
        trunc.write_bytes(fh.read(64 * 1024))
    rep = validate_file(str(trunc))
    assert not rep.ok
    assert any(f.where == "release" and "Revit 2025 framing table" in f.message
               for f in rep.infos), _msgs(rep.infos)
    msgs = " ".join(_msgs(rep.errors))
    assert "cls=0x" not in msgs and "class ordinal" not in msgs, msgs


def test_unresolvable_release_degrades_to_a_report(tmp_path):
    """A non-CFB input cannot have its release resolved: no exception, the
    real cause is an ERROR and the fallback is stated as INFO."""
    bogus = tmp_path / "not_a_revit_file.rvt"
    bogus.write_bytes(b"this is not a compound file" * 10)
    rep = validate_file(str(bogus))
    assert not rep.ok
    assert any(f.where == "container" for f in rep.errors), _msgs(rep.errors)
    assert any(f.where == "release" and "not resolved" in f.message
               for f in rep.infos), _msgs(rep.infos)

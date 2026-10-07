"""#864: the standalone provenance instruments read a 2024 / 2025 family in its OWN
release and judge its Formats/Latest against its OWN release's schema constant.

Before: ``make_family.py provenance`` refused a 2025 / 2024 family ("unexpected
Partitions header: v=9 ..."), and ``provenance_scan_v2`` -- even under the file's
own release -- returned ok=False on ``formats_latest_is_format_constant`` because
it compared against the 2026 pin.  Now one family built for 2024, 2025 and 2026
gets the same verdict from every instrument.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from conftest import context_constants  # noqa: E402
from rvt.famgen import famdoc_adoc as FA  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")   # the 2024 / 2025 builds enter release_build_context


@pytest.fixture
def release_leak_extra():
    """``no_release_leak`` watches the names the authoring context swaps too (#707)."""
    return context_constants


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    from rvt.frontdoor import release_ctx as RC
    out = tmp_path_factory.mktemp("rel")
    files = {}
    for year in (2026, 2025, 2024):
        path = str(out / f"tx{year}.rfa")
        if year == 2026:
            F.make_transformer(kva=45).write(path, validate=False, provenance=False)
        else:
            base = os.path.join(ROOT, "plugin", "assets", "genesis", f"G_ABPD_{year}.rvt")
            if not os.path.exists(base):
                continue
            with RC.release_build_context(base):
                F.make_transformer(kva=45).write(path, validate=False, provenance=False)
        files[year] = path
    return files


@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_the_cli_reads_every_release(built, year):
    if year not in built:
        pytest.skip(f"the pinned {year} base is not in this checkout")
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "provenance",
                        built[year]], cwd=ROOT, capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
    rep = json.loads(r.stdout)
    assert rep["ok"] is True
    assert rep["carried_format_constants"]["Formats/Latest"]["is_corpus_schema_constant"] is True


@pytest.mark.parametrize("year", [2026, 2025, 2024])
def test_the_v2_ledger_judges_each_release_by_its_own_constant(built, year):
    if year not in built:
        pytest.skip(f"the pinned {year} base is not in this checkout")
    rep = FA.provenance_scan_v2(built[year])
    assert rep["checks"]["formats_latest_is_format_constant"] is True
    assert rep["ok"] is True, {k: v for k, v in rep["checks"].items() if not v}


def test_the_constant_is_the_declared_releases_not_any_releases(built):
    from rvt import versions as V
    from rvt.container import open_rvt
    if 2025 not in built:
        pytest.skip("the pinned 2025 base is not in this checkout")
    with open_rvt(built[2025]) as f:
        bfi25 = f.raw("BasicFileInfo")
    with open_rvt(built[2026]) as f:
        bfi26 = f.raw("BasicFileInfo")
    sha25 = V.KNOWN_RELEASES[2025].schema_sha256
    sha26 = V.KNOWN_RELEASES[2026].schema_sha256
    assert FA.is_release_schema_constant(sha25, bfi25)
    assert not FA.is_release_schema_constant(sha26, bfi25)     # a 2026 schema in a 2025 file
    assert FA.is_release_schema_constant(sha26, bfi26)
    assert not FA.is_release_schema_constant("", bfi25)

"""The five read-only entry points open a Revit 2025 / 2024 file under its
OWN release (issue #121).

Before, ``python -m rvt.census``, ``python -m rvt.render.inspect``,
``tools/seed_audit.py``, ``python -m rvt.inventory`` and
``python -m rvt.convert.rvt_to_ifc`` read every input with the built-in
latest-release framing and died on the certified pinned 2025 / 2024 bases
with ``ValueError: unexpected Partitions header: v=9 cls=0x391|0x37b``
(census swallowed it into an ``ERROR`` line and mis-counted a 2025 file's
ContentDocuments / ContentTable as 0 / None).  Each now enters
``rvt.global_framing.enter_own_release`` once at the top.

Fresh-clone runnable: the inputs are the tracked bundled genesis bases and
a 2025 project built from them in a tmp dir.

Run: .venv/bin/python -m pytest tests/test_readers_own_release.py -q
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt import adocument as ADOC                          # noqa: E402
from rvt import partitions as P                            # noqa: E402
from rvt import versions as V                              # noqa: E402
from rvt.famgen import factory as FF                       # noqa: E402

GEN = os.path.join(ROOT, "plugin", "assets", "genesis")
BASES = {2026: os.path.join(GEN, "G_ABPD.rvt"),
         2025: os.path.join(GEN, "G_ABPD_2025.rvt"),
         2024: os.path.join(GEN, "G_ABPD_2024.rvt")}
YEARS = sorted(BASES)
ROOM_PROMPT = "an electrical room with 6 panels"

pytestmark = pytest.mark.skipif(
    not all(os.path.isfile(p) for p in BASES.values()),
    reason="bundled genesis bases missing")


def _native_state():
    """What the ladder swaps: framing table, Global-stream tokens, decoder."""
    return ({k: getattr(P, k) for k in V.framing_table(V.LATEST_RELEASE)},
            FF.CD_SEPARATOR, FF.CD_END_RECORD, ADOC._DECODER)


@pytest.fixture(autouse=True)
def _constants_restored():
    """Every entry point restores the built-in (latest-release) state."""
    before = _native_state()
    yield
    assert _native_state() == before
    assert before[0] == V.framing_table(V.LATEST_RELEASE)


def _seed_audit():
    p = os.path.join(ROOT, "tools", "seed_audit.py")
    spec = importlib.util.spec_from_file_location("seed_audit", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def room2025(tmp_path_factory):
    """prompt -> a Revit 2025 project with 6 generated panels loaded and
    placed (the front door, --target-version 2025), built once per module."""
    import rvt.frontdoor as FD
    out = tmp_path_factory.mktemp("room25")
    r = FD.author(prompt=ROOM_PROMPT, target_version=2025, out=str(out))
    path = r.files.get("combined")
    assert path and os.path.isfile(path), r.manifest.get("errors")
    assert V.detect_release(path) == 2025
    return path


# ---------------------------------------------------------------------------
# 1. census
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", YEARS)
def test_census_reads_each_base_under_its_own_release(year, capsys):
    from rvt.census import census, main
    c = census(BASES[year])
    assert c["release"] == year
    assert "release_note" not in c                      # own schema settled it
    assert c["host_records"] > 3000 and c["n_classes"] > 100, c
    assert c["units"]["total"] == 1 and c["coherence"]["coherent"] is True
    assert c["content_documents"]["entries"] == 0
    assert c["adocument"]["decoded"] and c["adocument"]["content_table_records"] == 0
    assert main([BASES[year]]) == 0
    out = capsys.readouterr().out
    assert "ERROR" not in out and "host_records=" in out, out


def test_census_counts_a_2025_projects_registries(room2025):
    """The DONE's coherence point: 6 loaded documents read 6 / 6 / 6, not
    0 / None (the tokens + ADocument decoder follow the file)."""
    from rvt.census import census
    c = census(room2025)
    assert c["release"] == 2025
    assert c["content_documents"]["entries"] == 6, c["content_documents"]
    assert c["adocument"]["content_table_records"] == 6, c["adocument"]
    assert c["units"]["family_documents"] == 6
    assert c["coherence"]["coherent"] is True, c["coherence"]
    assert c["families"]["with_document"] == 6


def test_run_certified_keeps_releases_apart(monkeypatch):
    """``--certified`` must not silently change meaning now that older
    releases read: top-level tables = the reference (latest) release only,
    every release under ``by_release``."""
    from rvt import census as C
    rel = {y: os.path.relpath(p, ROOT) for y, p in BASES.items()}
    monkeypatch.setattr(C, "load_certified",
                        lambda *a, **k: {"certified": [rel[2026], rel[2025]],
                                         "failed": [rel[2024]]})
    rep = C.run_certified(include_samples=False, with_dbviewtype=False)
    assert rep["reference_release"] == V.LATEST_RELEASE == 2026
    assert rep["passing_files"] == [rel[2026]] and rep["failing_files"] == []
    assert set(rep["by_release"]) == {2026, 2025, 2024}
    assert rep["by_release"][2025]["passing_files"] == [rel[2025]]
    assert rep["by_release"][2024]["failing_files"] == [rel[2024]]
    assert rep["mandatory_set"] == rep["by_release"][2026]["mandatory_set"]
    assert set(rep["censuses"]) == set(rel.values())
    assert {c["release"] for c in rep["censuses"].values()} == {2026, 2025, 2024}


def test_census_nests_inside_an_outer_release_context():
    from rvt.census import census
    with V.reading(year=2025) as ords:
        c = census(BASES[2024], with_dbviewtype=False, with_adocument=False)
        assert c["release"] == 2024 and c["host_records"] > 3000
        assert P.PT_CLASS == ords["PT_CLASS"]


# ---------------------------------------------------------------------------
# 2. render.inspect
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", YEARS)
def test_render_inspect_on_each_base(year, capsys):
    from rvt.render import inspect as RI
    rows = RI.inspect(BASES[year], classes=["Level", "Grid"])
    assert len(rows) >= 9 and all(r.kind == "dummy" for r in rows), [r.line() for r in rows]
    assert {r.klass for r in rows} <= {"Level", "Grid"}
    assert RI.main([BASES[year]]) == 0
    out = capsys.readouterr().out
    assert "elements:" in out and "release:" not in out, out


def test_render_inspect_sees_the_baked_symbols_of_a_2025_project(room2025):
    from rvt.render import inspect as RI
    rows = RI.inspect(room2025, classes=["FamilySymbol", "FamilyInstance"])
    s = RI.summary(rows)
    assert s["kinds"].get("brep") == 6, s                # six generated symbols
    assert s["per_class"]["FamilyInstance"], s


# ---------------------------------------------------------------------------
# 3. seed_audit (tools/, mirrored into the tekton-inspect skill)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", YEARS)
def test_seed_audit_on_each_base(year, tmp_path, capsys):
    SA = _seed_audit()
    js = tmp_path / "audit.json"
    assert SA.main([BASES[year], "--json", str(js)]) == 0
    rep = json.loads(js.read_text())
    assert "release_note" not in rep
    assert rep["inventory"]["stats"]["levels"] == 9
    wts = rep["inventory"]["wall_types"]
    assert len(wts) == 1 and wts[0]["name"] and wts[0]["thickness_ft"], wts
    out = capsys.readouterr().out
    assert out.startswith("=== SEED AUDIT:") and "release:" not in out, out


# ---------------------------------------------------------------------------
# 4. inventory
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", YEARS)
def test_inventory_cli_on_each_base(year, capsys):
    from rvt import inventory as INV
    assert INV.main([BASES[year], "--json"]) == 0
    inv = json.loads(capsys.readouterr().out)
    assert "release_note" not in inv
    assert inv["stats"]["levels"] == 9 and inv["stats"]["wall_types"] == 1
    assert [p["name"] for p in inv["phases"]] == ["Existing Conditions", "New Work"]
    assert INV.main([BASES[year]]) == 0
    assert capsys.readouterr().out.startswith("== inventory of ")


def test_inventory_names_a_2025_projects_symbols(room2025, capsys):
    from rvt import inventory as INV
    assert INV.main([room2025, "--json"]) == 0
    inv = json.loads(capsys.readouterr().out)
    assert inv["stats"]["symbols"] == 6 and inv["stats"]["symbols_named"] == 6


# ---------------------------------------------------------------------------
# 5. convert.rvt_to_ifc
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("year", YEARS)
def test_rvt_to_ifc_delivers_from_each_base(year, tmp_path, capsys):
    from rvt.convert import rvt_to_ifc as R2I
    assert R2I.main([BASES[year], "--out-dir", str(tmp_path)]) == 0
    stem = os.path.splitext(os.path.basename(BASES[year]))[0]
    ifc = tmp_path / f"{stem}.ifc"
    assert ifc.is_file() and ifc.read_bytes().startswith(b"ISO-10303-21")
    man = json.loads((tmp_path / f"{stem}.manifest.json").read_text())
    assert not man["errors"], man["errors"]
    assert man["input"]["provenance"]["format"] == str(year)      # names the release
    assert man["extraction"]["cells"]["levels"] == {"status": "works", "count": 9}
    assert not any(d.startswith("source release:") for d in man["degradations"])
    assert "delivered:" in capsys.readouterr().out


def test_rvt_to_ifc_round_trips_a_2025_project(room2025, tmp_path):
    from rvt.convert.rvt_to_ifc import convert_rvt_to_ifc
    rec = convert_rvt_to_ifc(room2025, out_dir=str(tmp_path))
    assert not rec["errors"], rec["errors"]
    assert rec["input"]["provenance"]["format"] == "2025"
    assert rec["extraction"]["cells"]["equipment"]["count"] == 6
    rt = rec["roundtrip"]
    if rt.get("ran"):                                    # steplite or ifcopenshell
        assert rt["equipment_survived"] == "6/6" and rt["all_survived"], rt


def test_rvt_to_ifc_degraded_source_states_the_fallback_and_still_writes_a_manifest(tmp_path):
    """A truncated 2025 file: the own schema is unreadable, so the pinned
    2025 table is used AND SAID SO; the failure reported is the real one
    (truncation), never a fictitious latest-release framing mismatch."""
    from rvt.convert import rvt_to_ifc as R2I
    trunc = tmp_path / "trunc_2025.rvt"
    with open(BASES[2025], "rb") as fh:
        trunc.write_bytes(fh.read(64 * 1024))
    assert R2I.main([str(trunc), "--out-dir", str(tmp_path / "o")]) == 2
    man = json.loads((tmp_path / "o" / "trunc_2025.manifest.json").read_text())
    assert any(d.startswith("source release: own schema unreadable")
               and "Revit 2025 framing table" in d for d in man["degradations"]), man
    errs = " ".join(man["errors"])
    assert "cls=0x" not in errs and "unexpected Partitions header" not in errs, errs

"""End-to-end tests for the tekton-ifc engine (skills/tekton-ifc/scripts).

Run:  .venv/bin/python -m pytest tests/test_engine.py -q

Covers:
  * validate_ifc on the REAL Design export flags what is really there:
    100% tessellation, all-identity placements, untyped elements (the saved
    sample has no type objects), and repeated unshared geometry;
  * validate_ifc on the synthetic v1-defect fixture flags duplicated types
    and the transparent 'working_clearance' phantom solid (defects the saved
    sample lacks);
  * harden_ifc merges the fixture's duplicate types, removes the phantom,
    recovers extrusions/insertion points, reopens with 0 schema errors, and on
    the real sample yields fewer tessellated elements + shared types;
  * generate_ifc builds the electrical-room example: schema-clean, Tier 1,
    0% tessellated equipment, shared types via mapped items, deterministic.
"""
from __future__ import annotations

import filecmp
import json
import os
import shutil
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "skills", "tekton-ifc", "scripts")
SAMPLE = os.path.join(ROOT, "samples", "design-ifc", "bs-area-e-electrical-room.ifc")
ESPEC = os.path.join(ROOT, "spec", "examples", "electrical-room.json")
PY = sys.executable

sys.path.insert(0, SCRIPTS)
sys.path.insert(0, os.path.join(ROOT, "tests"))
import bridge_lib  # noqa: E402
import harden_ifc  # noqa: E402
from fixtures_ifc import build_v1_defect_fixture  # noqa: E402


def run(*args, cwd=ROOT):
    p = subprocess.run([PY, *args], cwd=cwd, capture_output=True, text=True)
    return p.returncode, p.stdout + p.stderr


@pytest.fixture(scope="module")
def sample_report():
    assert os.path.isfile(SAMPLE), "real Design sample missing"
    return bridge_lib.analyze(SAMPLE)


@pytest.fixture(scope="module")
def fixture_path(tmp_path_factory):
    d = tmp_path_factory.mktemp("fix")
    return build_v1_defect_fixture(str(d / "v1_defect.ifc"))


# --------------------------------------------------------------- validate ---

def test_validate_real_sample_flags_defects(sample_report):
    rep = sample_report
    st = rep["score"]["stats"]
    assert rep["schema"]["n_errors"] == 0
    # 100% tessellation
    assert st["tessellated"] == st["with_body"] == 11
    assert st["tessellated_fraction"] == 1.0
    # identity placements everywhere -> insertion points lost
    assert st["identity_placements"] == st["products"] == 11
    # the saved sample carries NO type objects at all (all 11 elements untyped)
    assert rep["types"]["type_objects"] == 0
    assert rep["types"]["products_untyped"] == 11
    # 6 identical panels + 3 identical transformers, not instanced
    ia = rep["instancing"]
    assert ia["unshared_repeated_products"] == 9
    assert ia["duplicated_triangles"] > 0
    # single storey, no spaces, Voltage-as-label smell
    assert rep["spatial"]["single_storey"] and rep["spatial"]["space_count"] == 0
    assert any(s["property"] == "Voltage" for s in rep["psets"]["typing_smells"])
    assert rep["score"]["tier"].startswith("Tier 0")
    # box recovery: 10 of 11 products decompose entirely into exact boxes
    boxable = [p for p in rep["products"] if p["geometry"]["all_boxes"]]
    assert len(boxable) == 10


def test_validate_fixture_flags_duplicate_types_and_phantom(fixture_path):
    rep = bridge_lib.analyze(fixture_path)
    ta = rep["types"]
    assert ta["duplicate_type_objects"] == 2
    assert len(ta["duplicate_groups"]) == 1
    assert ta["duplicate_groups"][0]["name"].startswith("Eaton Pow-R-Line 4")
    ph = rep["phantoms"]
    assert ph["count"] >= 1
    names = [x["name"] for x in ph["findings"]]
    assert any("clearance" in (n or "").lower() for n in names)
    hi = [x for x in ph["findings"] if x["confidence"] == "high"]
    assert hi, "the transparent clearance solid must be a high-confidence phantom"
    assert rep["spatial"]["orphan_count"] == 1


def test_validate_cli_writes_json(tmp_path):
    out = tmp_path / "v.json"
    rc, txt = run(os.path.join(SCRIPTS, "validate_ifc.py"), SAMPLE, "--json", str(out))
    assert rc == 0, txt
    assert "tessellated" in txt and "Tier" in txt
    data = json.loads(out.read_text())
    assert data["score"]["stats"]["products"] == 11


def test_validate_cli_missing_file():
    rc, txt = run(os.path.join(SCRIPTS, "validate_ifc.py"), "/no/such/file.ifc")
    assert rc == 2


# ----------------------------------------------------------------- harden ---

def test_harden_fixture_merges_types_and_removes_phantom(fixture_path, tmp_path):
    out = tmp_path / "hardened.ifc"
    res = harden_ifc.harden(fixture_path, str(out))
    b, a = res["before"], res["after"]
    assert res["schema_after"]["errors"] == 0                       # reopens cleanly
    assert res["actions"]["duplicate_types_merged"] == 2
    assert a["duplicate_type_objects"] == 0
    assert a["type_objects"] < b["type_objects"]                     # fewer type objects
    assert res["actions"]["phantom_products_removed"] == 1
    assert res["actions"]["orphans_contained"] == 1
    assert res["actions"]["products_converted_to_extrusions"] >= 4
    assert a["tessellated_elements"] == 0
    assert a["identity_placements"] == 0
    assert a["score"] > b["score"]
    # identical psets migrated to the shared type
    assert res["actions"]["psets_moved_to_types"] >= 1


def test_harden_real_sample_recovers_geometry(tmp_path):
    out = tmp_path / "sample_hardened.ifc"
    res = harden_ifc.harden(SAMPLE, str(out))
    a, b = res["after"], res["before"]
    assert res["schema_after"]["errors"] == 0
    # 10 of 11 products are exact boxes -> converted; trapeze stays tessellated
    assert res["actions"]["products_converted_to_extrusions"] == 10
    assert res["actions"]["boxes_converted"] >= 40
    assert a["tessellated_elements"] < b["tessellated_elements"]
    assert a["identity_placements"] < b["identity_placements"]
    # shared types synthesised for the untyped-but-identical panels/transformers
    assert res["actions"]["shared_types_created"] >= 3
    assert a["untyped_elements"] == 0
    # element identity preserved
    assert res["actions"]["product_globalids_preserved"] == 11
    assert a["score"] > b["score"]


def test_harden_geometry_is_unchanged(tmp_path):
    """World-space bounding boxes of every element are identical after hardening."""
    ifcopenshell = pytest.importorskip("ifcopenshell")
    import ifcopenshell.geom
    import numpy as np
    out = tmp_path / "sample_hardened.ifc"
    harden_ifc.harden(SAMPLE, str(out))

    def boxes(path):
        f = ifcopenshell.open(path)
        s = ifcopenshell.geom.settings()
        s.set("use-world-coords", True)
        d = {}
        for p in f.by_type("IfcElement"):
            if not p.Representation:
                continue
            sh = ifcopenshell.geom.create_shape(s, p)
            v = np.array(sh.geometry.verts).reshape(-1, 3)
            d[p.GlobalId] = (v.min(0), v.max(0))
        return d

    a, b = boxes(SAMPLE), boxes(str(out))
    assert set(a) == set(b)
    for gid, (mn, mx) in a.items():
        mn2, mx2 = b[gid]
        assert np.allclose(mn, mn2, atol=2e-3), gid
        assert np.allclose(mx, mx2, atol=2e-3), gid


def test_harden_cli(tmp_path):
    out = tmp_path / "h.ifc"
    rep = tmp_path / "h.json"
    rc, txt = run(os.path.join(SCRIPTS, "harden_ifc.py"), SAMPLE, "-o", str(out), "--report", str(rep))
    assert rc == 0, txt
    assert "schema errors after = 0" in txt
    data = json.loads(rep.read_text())
    assert data["actions"]["product_globalids_preserved"] == 11


# --------------------------------------------------------------- generate ---

def test_generate_electrical_room_is_tier1(tmp_path):
    out = tmp_path / "eroom.ifc"
    rc, txt = run(os.path.join(SCRIPTS, "generate_ifc.py"), "--spec", ESPEC, "-o", str(out))
    assert rc == 0, txt
    rep = bridge_lib.analyze(str(out))
    assert rep["schema"]["n_errors"] == 0
    st = rep["score"]["stats"]
    # equipment (and everything else) is parametric geometry, not tessellation
    assert st["tessellated"] == 0
    assert st["tessellated_fraction"] == 0.0
    # 6 panels + 3 transformers present with real placements
    classes = [p["class"] for p in rep["products"]]
    assert classes.count("IfcElectricDistributionBoard") == 6
    assert classes.count("IfcTransformer") == 3
    assert st["identity_placements"] == 0
    # shared types + instancing: no duplicate types, no unshared repeats
    assert rep["types"]["duplicate_type_objects"] == 0
    assert rep["types"]["products_untyped"] == 0
    assert rep["instancing"]["unshared_repeated_products"] == 0
    # the room space and no phantom solids (clearances live in psets)
    assert rep["spatial"]["space_count"] == 1
    assert rep["phantoms"]["count"] == 0
    assert rep["score"]["tier"].startswith("Tier 1")


def test_generate_is_deterministic(tmp_path):
    a, b = tmp_path / "a.ifc", tmp_path / "b.ifc"
    assert run(os.path.join(SCRIPTS, "generate_ifc.py"), "--spec", ESPEC, "-o", str(a))[0] == 0
    assert run(os.path.join(SCRIPTS, "generate_ifc.py"), "--spec", ESPEC, "-o", str(b))[0] == 0
    assert filecmp.cmp(str(a), str(b), shallow=False)


def test_generate_minimal_spec(tmp_path):
    spec = {"levels": [{"name": "Level 1", "elevation": 0}],
            "equipment": [{"kind": "panelboard", "name": "B-HG4", "position": [0, 0]}]}
    sp = tmp_path / "min.json"
    sp.write_text(json.dumps(spec))
    out = tmp_path / "min.ifc"
    rc, txt = run(os.path.join(SCRIPTS, "generate_ifc.py"), "--spec", str(sp), "-o", str(out))
    assert rc == 0, txt
    rep = bridge_lib.analyze(str(out))
    assert rep["schema"]["n_errors"] == 0
    assert [p["class"] for p in rep["products"]] == ["IfcElectricDistributionBoard"]
    assert rep["products"][0]["type_name"] is not None


# ----------------------------------------------------------------- report ---

def test_report_cli(tmp_path):
    v = tmp_path / "v.json"
    assert run(os.path.join(SCRIPTS, "validate_ifc.py"), SAMPLE, "--json", str(v), "--quiet")[0] == 0
    md = tmp_path / "r.md"
    rc, txt = run(os.path.join(SCRIPTS, "report.py"), str(v), "-o", str(md))
    assert rc == 0, txt
    body = md.read_text()
    assert "Tier 1" in body and "Tier 2" in body
    assert "DirectShape" in body
    assert "B-HG4" in body

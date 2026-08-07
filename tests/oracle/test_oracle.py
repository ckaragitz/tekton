"""Regression gate: the ground-truth oracle must keep agreeing.

Run:  .venv/bin/python -m pytest tests/oracle -q
These assertions pin the wave-2 agreement so any decoder regression (or a
genuine improvement) shows up as a MEASURED delta against Revit's own IFC
export of the same model.
"""
from __future__ import annotations

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)

VENDOR = os.path.join(ROOT, "vendor", "magnetar-revit-test-datasets")
RVT_2024 = os.path.join(VENDOR, "Revit", "2024_Core_Interior.rvt")
IFC_2024 = os.path.join(VENDOR, "IFC Exports", "2024_Core_Interior_slim.ifc")
RVT_2023 = os.path.join(VENDOR, "Revit", "Revit_IFC5_Einhoven.rvt")
FME_DIR = os.path.join(VENDOR, "FME Demos")

pytestmark = pytest.mark.skipif(not os.path.exists(RVT_2024), reason="magnetar corpus not present")


@pytest.fixture(scope="module")
def rep_2024():
    import compare_oracle as C
    return C.compare(RVT_2024, IFC_2024)


@pytest.fixture(scope="module")
def rep_einhoven():
    import compare_oracle as C
    return C.compare_fme(RVT_2023, FME_DIR)


def test_document_identity(rep_2024):
    assert rep_2024["identity"]["guid_match"] is True


def test_element_id_join_coverage(rep_2024):
    ej = rep_2024["element_join"]
    assert ej["ifc_elements_with_tag"] >= 1000
    assert ej["coverage_records"] == 1.0
    assert ej["coverage_elemtable"] == 1.0


@pytest.mark.parametrize("ifc_cls,rvt_cls", [
    ("IfcWall", "SWall"), ("IfcDoor", "FamilyInstance"), ("IfcWindow", "FamilyInstance"),
    ("IfcColumn", "FamilyInstance"), ("IfcSlab", "Floor"),
])
def test_class_correspondences(rep_2024, ifc_cls, rvt_cls):
    rows = {r["ifc_class"]: r for r in rep_2024["element_join"]["rows"]}
    assert rows[ifc_cls]["rvt_class"] == rvt_cls
    assert rows[ifc_cls]["purity"] >= 0.95


def test_name_agreement(rep_2024):
    na = rep_2024["name_agreement"]
    for key in ("storeys", "wall_types", "spaces", "materials"):
        sc = na[key]["score"]
        assert sc["n"] > 0 and sc["found"] == sc["n"], f"{key}: {sc}"


def test_einhoven_fme_ids_resolve(rep_einhoven):
    assert rep_einhoven["n_ids"] >= 20
    assert rep_einhoven["n_in_records"] == rep_einhoven["n_ids"]
    assert rep_einhoven["n_in_elemtable"] == rep_einhoven["n_ids"]
    cls = {c["fme_class"]: c["rvt_class"] for c in rep_einhoven["class_correspondence"]}
    assert cls.get("hok.wall.Properties") == "SWall"


def test_release_independent_walker():
    import rvt_release as R
    from rvt.container import open_rvt
    for path in (RVT_2023, RVT_2024):
        with open_rvt(path) as doc:
            cm = R.class_map(doc)
            tags = R.framing_tags(cm)
            assert all(v == "schema" for v in tags.source.values())
            for s in doc.partition_streams():
                pp = R.walk_partition(R.depage(doc.raw(s)), tags)
                assert pp.blocks and all(b.crc_ok for b in pp.blocks)
                assert not pp.errors

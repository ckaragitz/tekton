"""The REQUIRED-SETTINGS law (issue #52, desktop rounds 4-5).

Desktop Revit 2026 demands four singleton settings elements of every
family document, and names them when absent:

* ``DefaultDivideSettings`` + ``DrawOrder3dElem`` -- the
  ``TaskDialog_Repair_Missing_Unique_Elements`` pair;
* ``AutoCamSettingsElem`` -- the ``Cannot get AutoCamSettingsElem from the
  ADoccument!`` DBG_WARN;
* ``PenWidthTableElem`` -- the ``PenWidthTableGetter.cpp:62`` draw assert.

Plus two donor-measured laws from the same rounds (a Revit-2026-born
family supplied by the owner): ``RefPlane.m_cutVec`` == the plane NORMAL
(not an in-plane vector), and element headers carry NO ``m_pBBox`` (Revit
computes boxes at runtime; our zero-thickness line Outlines were the
``BoundedSpace`` warning's shape).

Everything here runs from a fresh clone (bundled base + standalone
resolvers).  Run: .venv/bin/python -m pytest tests/test_required_settings.py -q
"""
from __future__ import annotations

import os
import sys
from collections import Counter

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (os.path.join(ROOT, "src"), os.path.join(ROOT, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

BASE = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD.rvt")
pytestmark = pytest.mark.skipif(
    not os.path.isfile(BASE), reason="bundled genesis base missing")

REQUIRED = ("AutoCamSettingsElem", "DefaultDivideSettings",
            "DrawOrder3dElem", "PenWidthTableElem")


@pytest.fixture(scope="module")
def rfa(tmp_path_factory):
    from rvt import schema as _RS
    if not os.path.isfile(_RS.DEFAULT_PATH):
        from rvt.frontdoor.standalone import activate
        activate()
    from rvt.famgen import factory as F
    prod = F.make_panelboard(mains_a=225, spaces=30, voltage="480Y/277")
    out = str(tmp_path_factory.mktemp("rfa") / "pb.rfa")
    prod.write(out, validate=False)
    return out


@pytest.fixture(scope="module")
def fi(rfa):
    from rvt.families import FamilyIndex
    return FamilyIndex(rfa)


def test_every_required_settings_element_present(fi):
    recs = fi.unit_records(0).get(102, {})
    cls = Counter(fi.class_name(r.class_id) for r in recs.values())
    for c in REQUIRED:
        assert cls.get(c) == 1, f"{c}: expected exactly one, got {cls.get(c, 0)}"


def test_settings_elements_owned_and_doc_bound(fi):
    recs = fi.unit_records(0).get(102, {})
    fam_ids = [eid for eid, r in recs.items()
               if fi.class_name(r.class_id) == "Family"]
    for eid, r in sorted(recs.items()):
        if fi.class_name(r.class_id) in REQUIRED:
            v = fi.value(0, eid, 102)
            assert v.get("m_famId") in fam_ids, (eid, v.get("m_famId"))
            assert (v.get("m_docAccess") or {}).get("m_pDoc") == {"weakref": 1}


def test_pen_width_table_carries_the_iso_series(fi):
    recs = fi.unit_records(0).get(102, {})
    for eid, r in sorted(recs.items()):
        if fi.class_name(r.class_id) == "PenWidthTableElem":
            v = fi.value(0, eid, 102)
            tab = ((v.get("m_pPenWidthTable") or {}).get("value") or {})
            rows = tab.get("m_modelPenInfo") or []
            assert rows, "pen table has no model pen rows"
            assert all(len(row.get("m_pens") or []) == 16 for row in rows)
            return
    raise AssertionError("no PenWidthTableElem in the document")


def test_refplane_cutvec_is_the_plane_normal(fi):
    recs = fi.unit_records(0).get(102, {})
    seen = 0
    for eid, r in sorted(recs.items()):
        if fi.class_name(r.class_id) == "RefPlane":
            assert fi.value(0, eid, 102).get("m_cutVec") == [0.0, 0.0, 1.0], eid
            seen += 1
    assert seen == 2


def test_headers_carry_no_bbox(fi):
    """Donor law: Revit-born headers carry m_pBBox null everywhere; a
    zero-thickness Outline on a line curve is the degenerate box the
    BoundedSpace warning names."""
    h101 = fi.unit_records(0).get(101, {})
    r102 = fi.unit_records(0).get(102, {})
    for eid in h101:
        cn = fi.class_name(r102[eid].class_id) if eid in r102 else "?"
        if cn in ("CurveElem", "VarSketch"):
            assert fi.value(0, eid, 101).get("m_pBBox") is None, (cn, eid)


def test_family_viewer_bound_law(fi):
    """Donor law (#333): every family Viewer's z bound interval is
    (100.0, 0.0) -- on the reference level, never degenerate -- and the plan
    viewer matches the project viewer's shape (bounds inactive, crop on,
    ortho projMethod 1, viewerFlags 0, not intentionally placed).  The basis
    frames stay per-view-type (plan frame vs elevation frame) -- the donor
    exonerated them."""
    recs = fi.unit_records(0).get(102, {})
    proj_view = [eid for eid, r in sorted(recs.items())
                 if fi.class_name(r.class_id) == "DBViewProject"]
    assert len(proj_view) == 1
    seen = 0
    for eid, r in sorted(recs.items()):
        if fi.class_name(r.class_id) != "Viewer":
            continue
        seen += 1
        v = fi.value(0, eid, 102)
        bs = v.get("m_boundedSpace") or {}
        assert (bs.get("m_boundOffset") or [])[2] == [100.0, 0.0], eid
        assert bs.get("m_boundActive") == [[False, False]] * 3, eid
        assert bs.get("m_isOn") is True, eid
        assert v.get("m_projMethodType") == 1, eid
        assert v.get("m_viewerFlags") == 0, eid
        assert v.get("m_intentionallyPlaced") is False, eid
    assert seen == 2, seen


def test_units_table_covers_every_param_spec(fi):
    """The family-units law (#333, round 16-17): the Family Types dialog
    formats every parameter value through UnitsElem.m_units, so every
    unit-bearing spec a ParamElemFamily declares MUST have a format entry
    (a miss threw at ADialog::doModal).  Unitless base specs (string,
    int64, bool) are exempt -- they carry no format."""
    recs = fi.unit_records(0).get(102, {})
    specs = None
    for eid, r in recs.items():
        if fi.class_name(r.class_id) == "UnitsElem":
            fmt = ((fi.value(0, eid, 102).get("m_units") or {})
                   .get("m_formatOptionsMap") or [])
            specs = {p["first"]["m_typeId"] for p in fmt}
            break
    assert specs, "no UnitsElem format table"
    assert len(specs) >= 130, f"units table too small: {len(specs)}"
    unitless = ("autodesk.spec:spec.string", "autodesk.spec:spec.int64",
                "autodesk.spec:spec.bool")
    missing = []
    for eid, r in sorted(recs.items()):
        if fi.class_name(r.class_id) != "ParamElemFamily":
            continue
        pd = (fi.value(0, eid, 102).get("m_pParamDef") or {}).get("value") or {}
        sp = (pd.get("m_specTypeId") or {}).get("m_typeId")
        if sp and not sp.startswith(unitless) and sp not in specs:
            missing.append((pd.get("m_caption"), sp))
    assert not missing, f"param specs missing from units table: {missing}"


def test_order_cell_has_one_group_per_group_type(fi):
    """The order-cell law (#333, round 18): the Family Types dialog builds a
    tree keyed by parameter group, so each group-type id may appear only once
    in the self-Family FamilyParamsOrderCell.m_sortedParams (a duplicate
    identityData group -- user identity params + built-in identity BIPs --
    threw at ADialog::doModal)."""
    recs = fi.unit_records(0).get(102, {})
    fam = [eid for eid, r in recs.items() if fi.class_name(r.class_id) == "Family"]
    assert len(fam) == 1
    sf = fi.value(0, fam[0], 102)
    cells = ((sf.get("m_cellList") or {}).get("value") or {}).get("m_cells") or []
    assert cells, "self-Family carries no order cell"
    for c in cells:
        sp = ((c.get("value") or {}) if isinstance(c, dict) else {}).get("m_sortedParams")
        if not isinstance(sp, list):
            continue
        keys = [(g.get("m_groupTypeId") or {}).get("m_typeId") for g in sp]
        assert len(keys) == len(set(keys)), f"duplicate group keys: {keys}"


def test_walked_binds_stay_self_contained(rfa):
    """The viewer-certified self-contained-binds law (T2a): curve/solid rep
    style binds are member GStyleElem ids or -1, never foreign ids -- the
    settings elements this file adds must not disturb it.  (A Revit-born
    famdoc resolves styles through IN-DOCUMENT GStyleElem rows -- ours has
    none yet; authoring them is the open #52 lead.)"""
    from rvt.famgen import factory as F
    from rvt.famgen.birthright import walked_bind_census
    prod = F.make_panelboard(mains_a=225, spaces=30, voltage="480Y/277")
    census = walked_bind_census(prod.doc)
    assert census["foreign"] == 0, census

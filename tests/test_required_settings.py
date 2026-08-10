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
    # 2 center planes + the 4 parametric-drive side planes (issue #372)
    assert seen == 6


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
    # project + floor plan + ceiling plan + the four elevations (the 3D
    # view's Viewer3d is a different class with its own donor shape -- not
    # under this law)
    assert seen == 7, seen


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


def test_donorless_host_document_wires_every_registry(tmp_path):
    """THE DONOR-LESS LAW (the ckaragitz12 bug): a family built with NO
    ``family_donor`` -- what every install without the owner's escape-hatch
    file produces -- must ship a REAL host ADocument, not a skeleton.

    Its constructive tree populates the AppInfoManager's manager slots (a
    Revit-born famdoc fills 133 of 239); with them empty every registry the
    famgen laws wire silently no-opped and ``Global/Latest`` shipped as a
    252-byte stub that Revit rejects at ``Failed to load elemStream#0``.
    Every other test reads the ELEMENT records, so nothing caught it.
    """
    from rvt import schema as _RS
    if not os.path.isfile(_RS.DEFAULT_PATH):
        from rvt.frontdoor.standalone import activate
        activate()
    from rvt.famgen import factory as F
    from rvt.frontdoor.standalone import standalone_family_write
    from rvt import adocument as A
    from rvt.container import open_rvt

    out = str(tmp_path / "donorless.rfa")
    prod = F.make_panelboard(mains_a=225, spaces=30, voltage="480Y/277")
    standalone_family_write(prod, out, validate=False, provenance=False,
                            timestamp=0)                      # NO family_donor
    with open_rvt(out) as f:
        host = b"".join(f.inflate_all("Global/Latest"))
    assert len(host) > 1000, f"host ADocument is a stub ({len(host)} bytes)"
    arr = (((A.decode_latest(host).value.get("m_pAppInfoManager") or {})
            .get("value") or {}).get("m_appInfoArr") or [])
    populated = {s.get("ptr_class"): (s.get("value") or {})
                 for s in arr if isinstance(s, dict)}
    assert len(populated) >= 130, f"only {len(populated)} manager slots populated"
    uet = populated.get("UniqueElementsTracking")
    assert uet is not None, "no UniqueElementsTracking manager"
    ids = uet.get("m_elemIds") or []
    assert len(ids) == 93, f"UET id array is {len(ids)} long, expected 93"
    for slot in (10, 60, 64, 65, 85):        # autocam/divide/assembly/keynote/draworder
        assert ids[slot] > 0, f"UniqueElementsTracking[{slot}] unset ({ids[slot]})"
    assert (populated.get("PenWidthTableInfo") or {}).get("m_penWidthTableElemId", -1) > 0
    assert (populated.get("SymbolIdMgr") or {}).get("m_defElementTypeMap")
    assert (populated.get("BrowserOrganizationTracking") or {}).get("m_elemIdSet")


def test_family_carries_the_four_elevations(fi):
    """Owner steer S-2026-08-10-a: a generated family carries a Revit-born
    family's view set -- Ref. Level plan, ceiling plan, four elevations and
    the "View 1" 3D view.  Shape measured on the donor's DBViewSection
    31/35/39/43: one shared "Elevation 1" DBViewType, a section view type of
    1, cut plane through the family origin, and the family view scale."""
    recs = fi.unit_records(0).get(102, {})
    sections = {}
    for eid, r in sorted(recs.items()):
        if fi.class_name(r.class_id) == "DBViewSection":
            sections[fi.value(0, eid, 102)["m_viewName"]] = eid
    assert sorted(sections) == ["Back", "Front", "Left", "Right"], sorted(sections)
    types = set()
    for name, eid in sections.items():
        v = fi.value(0, eid, 102)
        assert v["m_sectionViewType"] == 1, name
        assert v["m_scale"] == 0.041666666666666664, name
        assert v["m_origin"] == [0.0, 0.0, 0.0], name
        assert v["m_lightSchemeId"] == -1, name
        assert v["m_pDetailDrawOrderMgr"]["ptr_class"] == "DrawOrderMgr3dFamily", name
        assert v["m_pViewDisplayMgr"]["value"]["m_lights"][
            "m_sunAndShadowSettingsId"] == -1, name
        # the four view directions are the four faces, and each viewer's
        # basis is the matching camera frame
        vw = fi.value(0, v["m_viewerId"], 102)
        vd = v["m_viewDir"]
        assert vw["m_boundedSpace"]["m_basis"][2] == [-vd[0], -vd[1], -vd[2]], name
        types.add(v["m_dbViewTypeId"])
    assert len(types) == 1, types            # ONE shared elevation view type
    dirs = {tuple(fi.value(0, e, 102)["m_viewDir"]) for e in sections.values()}
    assert dirs == {(0.0, 1.0, -0.0), (0.0, -1.0, 0.0),
                    (-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)}, dirs


def test_solids_name_the_family_object_style(fi):
    """THE OBJECT-STYLE LAW (owner: "when graphics display is on i can not
    see the outlining of the geometry").  A solid's ``Geometry`` node names
    the graphics style Revit draws its EDGES with; ours named -1, so a
    generated family rendered as a shaded body with no outline and vanished
    in Wireframe.  Measured on the Autodesk library panelboard's extrusions:
    the style is a GStyleElem whose m_categoryId is the family's BUILT-IN
    category, and the node carries control command 67108864."""
    recs = fi.unit_records(0).get(102, {})
    styles = {}
    for eid, r in recs.items():
        if fi.class_name(r.class_id) == "GStyleElem":
            v = fi.value(0, eid, 102)
            if int(v.get("m_categoryId", 0)) < 0:      # a BUILT-IN category
                styles[eid] = int(v["m_categoryId"])
    assert len(styles) == 1, styles
    (style_id, cat), = styles.items()
    assert cat == -2001040, cat                        # Electrical Equipment
    seen = 0
    for eid, r in recs.items():
        if fi.class_name(r.class_id) != "ExtrusionElem":
            continue
        rep = fi.decode(0, eid, 103)
        if rep is None:                                 # dummy rep variant
            continue
        gi = rep.value["m_subNodes"][0]["value"]["m_GInfo"]
        assert gi["m_categoryId"] == style_id, (eid, gi["m_categoryId"])
        assert gi["m_controlCommand"] == 67108864, eid
        seen += 1
    assert seen >= 1

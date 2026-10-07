"""#879 / #878: a generated transformer is built from its real parts and opens in
its 3D view at Fine detail.

* ``rvt.famgen.equipment_detail.transformer_parts`` lays out a ventilated dry-type
  transformer inside the catalog envelope: base skids, enclosure with a louvered
  ventilation slot under the lid, overhanging top cover, side louver banks, bolted
  front access panel, nameplate (nominal proportions, never a manufacturer drawing);
* ``make_transformer`` authors them (the dummy variant stays one envelope box) with
  the connectors on the cover's top face at the catalog height;
* every generated family records ONE open window -- its 3D "View 1" -- in
  ``DBDrawingInfo.m_openWindowStates`` (Revit restores that window on open) and the
  3D view carries VIEW_DETAIL_LEVEL 3 (Fine); plans stay Coarse.

"Opens in 3D" and "looks right in Revit" are claimed only with a desktop / viewer
verdict (hard rule 4); these tests pin what the file carries.
"""
from __future__ import annotations

import os
import sys
from contextlib import ExitStack

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import equipment_detail as ED  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402

IN = 1 / 12.0

# the open-in-3D check reads the written file inside its OWN release (the read-side
# instrument ladder): conftest's leak guard, module-wide (#707)
pytestmark = pytest.mark.usefixtures("no_release_leak")


@pytest.fixture
def release_leak_extra():
    from conftest import ladder_constants
    return ladder_constants


def _extent(parts):
    xs = [c for p in parts for c in (p.cx - p.w / 2, p.cx + p.w / 2)]
    ys = [c for p in parts for c in (p.cy - p.d / 2, p.cy + p.d / 2)]
    zs = [z for p in parts for z in (p.z0, p.z0 + p.h)]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


@pytest.mark.parametrize("W,D,H", [(24.88 * IN, 21.13 * IN, 36.88 * IN),     # 45 kVA
                                   (30.5 * IN, 24.0 * IN, 43.0 * IN),        # 75 kVA
                                   (14 * IN, 10 * IN, 16 * IN)])              # a small one
def test_parts_stand_inside_the_catalog_envelope(W, D, H):
    parts = ED.transformer_parts(W, D, H)
    x0, x1, y0, y1, z0, z1 = _extent(parts)
    assert z0 == pytest.approx(0.0) and z1 == pytest.approx(H)          # floor to catalog height
    slack = 1.0 * IN                                                     # overhang / proud plates
    assert -W / 2 - slack <= x0 and x1 <= W / 2 + slack
    assert -D / 2 - slack <= y0 and y1 <= D / 2 + slack
    assert all(p.w > 0 and p.d > 0 and p.h > 0 for p in parts)
    roles = [p.role for p in parts]
    assert roles[0] == "enclosure body"
    for role, n in (("base skid", 2), ("top cover", 1), ("vent slot louver", 2), ("side louver", 8),
                    ("front access panel", 1), ("nameplate", 1), ("access panel bolt", 4)):
        assert roles.count(role) >= n, role
    cover = next(p for p in parts if p.role == "top cover")
    assert cover.z0 + cover.h == pytest.approx(H) and cover.w > W and cover.d > D
    body = parts[0]
    assert (body.w, body.d) == pytest.approx((W, D))
    band = next(p for p in parts if p.role.startswith("enclosure upper band"))
    assert band.d < D and band.cy > 0                                   # the slot is recessed at the front


def test_a_non_positive_envelope_is_refused():
    with pytest.raises(ValueError):
        ED.transformer_parts(1.0, 0.0, 1.0)


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    d = tmp_path_factory.mktemp("xf879")
    prod = F.make_transformer(kva=45)
    out = str(d / "xf.rfa")
    rep = prod.write(out)
    return prod, out, rep


def test_transformer_is_authored_from_its_parts_and_validates(built):
    prod, _out, rep = built
    f = prod.facts
    parts = ED.transformer_parts(f.get("width_in") / 12, f.get("depth_in") / 12,
                                 f.get("height_in") / 12)
    body = [x for x in prod.forms if not x.params["role"].startswith("clearance")]
    assert len(body) == len(parts) > 20 and len(prod.forms) == len(parts) + 2   # + the 2 zones
    assert [x.params["role"] for x in body[1:]] == [p.role for p in parts[1:]]
    assert prod.forms[0].params["role"] == "transformer enclosure"
    assert any(ED.DETAIL_NOTE == x for x in prod.doc.notes)
    H = max(f.params["base_z_ft"] + f.params["height_ft"] for f in body)
    for c in prod.doc.connectors:                     # on the cover, at the top: END cap, #1030
        assert c.obj["m_oPlaneRef"]["value"]["m_geomRef"]["m_geomTag"] == 0
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0)
    assert rep["provenance"]["ok"] is True
    assert H == pytest.approx(prod.facts.get("height_in") / 12)


def test_the_dummy_variant_stays_one_envelope_box():
    prod = F.make_transformer(kva=45, solid=False)
    assert len(prod.forms) == 1
    assert prod.forms[0].params["height_ft"] == pytest.approx(prod.facts.get("height_in") / 12)


def _views_and_window(path):
    from rvt import adocument as AD
    from rvt import global_framing as GF
    from rvt.families import FamilyIndex
    with ExitStack() as st:
        GF.enter_own_release(st, path)
        fi = FamilyIndex(path)
        views = {}
        for e, r in fi.unit_records(0).get(102, {}).items():
            c = fi.class_name(r.class_id)
            if c in ("DBView3d", "DBViewPlan"):
                v = fi.value(0, e) or {}
                detail = {q["m_paramId"]: q["m_value"] for q in
                          (((v.get("m_pParamValueSetInt") or {}).get("value") or {})
                           .get("m_paramSet") or [])}.get(-1011002)
                views.setdefault(c, []).append((v.get("m_viewName"), v.get("m_dbDrawingId"), detail))
        doc = AD.open_document_object(path, AD.get_decoder(fi.schema))
        dd = AD._appinfo_body(doc.value if hasattr(doc, "value") else doc, "DBDrawingInfo")
        return views, dd["m_openWindowStates"]


def test_the_family_opens_in_its_3d_view_at_fine_detail(built):
    _prod, out, _rep = built
    views, windows = _views_and_window(out)
    ((name, drawing, detail),) = views["DBView3d"]
    assert name == "View 1" and detail == 3                              # Fine
    assert all(d == 1 for _n, _dr, d in views["DBViewPlan"])             # plans stay Coarse
    assert len(windows) == 1
    w = windows[0]
    assert w["ptr_class"] == "WindowState" and w["value"]["m_dbDrawingId"] == drawing
    assert w["value"]["m_projLeftBottom"] == [0.0, 0.0, 0.0]            # no saved zoom: fit


def test_every_family_route_opens_in_3d(tmp_path):
    """Not only the transformer: the window is recorded by the family writer itself."""
    out = str(tmp_path / "device.rfa")
    F.make_device("duplex-receptacle", standards=False).write(out, validate=False, provenance=False)
    views, windows = _views_and_window(out)
    assert [w["value"]["m_dbDrawingId"] for w in windows] == [views["DBView3d"][0][1]]

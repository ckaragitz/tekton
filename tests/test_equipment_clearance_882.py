"""#882 / #884: every generated equipment family carries its clearance zones, shown by
Yes/No parameters bound to their visibility, painted a see-through magenta.

* the transformer: a FRONT NEC 110.26(A) working space from its -y working face, from
  the floor (table: 3.5 ft x max(W, 30 in) x 6.5 ft at the stated 277 V / Condition 2
  defaults) and a NOMINAL top ventilation zone (said to be nominal);
* the panelboard: the working space from its door face (+y), reaching the floor below
  a NOMINALLY mounted cabinet, and the 110.26(E)(1) dedicated space above (6 ft);
* each zone's extrusion carries the ``FamilyParametrizedElemParamsCell``
  ``{param, -1006205}`` association (the "Visible" property) between its extrusion and
  pattern helpers, the driving parameter in its header's deletion parents, the param
  = ``and(Show Clearances, Show Front/Top Clearance)``;
* one graphics-only ``MaterialElem`` (magenta, 50 % transparent, no appearance asset)
  on both zones, registered in ``MaterialTracking``;
* the dummy variant carries no zones.

"The toggle hides the zone" / "renders see-through" are desktop claims (hard rule 4):
the owner's first check reported the toggles not reliably working (#884) -- these
tests pin what the FILE carries, nothing more.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import clearance as CL  # noqa: E402
from rvt.famgen import equipment_clearance as EC  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402

IN = 1 / 12.0


def _zones(prod):
    return {f.params["role"]: f for f in prod.forms if str(f.params.get("role", "")).startswith("clearance")}


def _ext(form):
    return next(e for e in form.elements if e.class_name == "ExtrusionElem")


@pytest.fixture(scope="module")
def transformer():
    return F.make_transformer(kva=45)


@pytest.fixture(scope="module")
def panelboard():
    return F.make_panelboard()


def test_transformer_front_zone_is_the_nec_working_space_from_its_face(transformer):
    f = transformer.facts
    W, D, H = f.get("width_in") / 12, f.get("depth_in") / 12, f.get("height_in") / 12
    z = _zones(transformer)
    front, top = z["clearance: front working space"], z["clearance: top"]
    ws = CL.working_space(equipment_width_ft=W, equipment_height_ft=H)
    fp = front.params
    assert (fp["width_ft"], fp["depth_ft"], fp["height_ft"]) == pytest.approx(
        (ws.width_ft, ws.depth_ft, ws.height_ft))
    assert (ws.depth_ft, ws.width_ft, ws.height_ft) == pytest.approx((3.5, 2.5, 6.5))
    assert fp["base_z_ft"] == pytest.approx(0.0)                       # from the floor
    from rvt.famgen import equipment_detail as ED
    # starts at the front's proud plates (access panel + bolts), not inside them
    assert fp["center"][1] + fp["depth_ft"] / 2 == pytest.approx(-D / 2 - ED.FRONT_PROUD_FT)
    front_min_y = min(p.cy - p.d / 2 for p in ED.transformer_parts(W, D, H))
    assert front_min_y >= -D / 2 - ED.FRONT_PROUD_FT - 1e-9
    tp = top.params
    assert tp["base_z_ft"] == pytest.approx(H) and tp["height_ft"] == pytest.approx(EC.NOMINAL_TOP_FT)
    assert "NOMINAL" in tp["source"] and "NEC 450.9" in tp["source"]
    notes = "\n".join(transformer.doc.notes)
    assert "clearance assumption -- voltage_to_ground" in notes
    assert "NOT yet verified in Revit" in notes


def test_panelboard_zone_leaves_the_door_face_and_reaches_the_floor(panelboard):
    from rvt.famgen.archetypes import MOUNT_TOP_IN
    f = panelboard.facts
    W, D, H = f.get("width_in") / 12, f.get("depth_in") / 12, f.get("height_in") / 12
    z = _zones(panelboard)
    fp = z["clearance: front working space"].params
    floor = -max(0.0, MOUNT_TOP_IN / 12 - H)
    assert fp["base_z_ft"] == pytest.approx(floor)
    # surface: the box face at +D, the zone in front of the door hardware standing on it
    from rvt.famgen import equipment_detail as ED
    proud = ED.front_proud_ft(ED.panelboard_parts(W, D, H), D)
    assert 0 < proud < 1.0 / 12
    assert fp["center"][1] - fp["depth_ft"] / 2 == pytest.approx(D + proud)
    assert fp["height_ft"] >= 6.5
    tp = z["clearance: top"].params
    assert tp["height_ft"] == pytest.approx(6.0) and tp["base_z_ft"] == pytest.approx(H)
    assert "110.26(E)(1)" in tp["source"]
    assert "NOMINAL" in "\n".join(panelboard.doc.notes)                     # the mounting is said


@pytest.mark.parametrize("which", ["transformer", "panelboard"])
def test_each_zone_is_bound_to_its_visibility_parameter(request, which):
    prod = request.getfixturevalue(which)
    doc = prod.doc
    p = doc.params
    for name in (EC.P_SHOW, EC.P_FRONT, EC.P_TOP, EC.P_FRONT_ON, EC.P_TOP_ON):
        assert name in p and p[name].obj["m_pParamDef"]["ptr_class"] == "ParamDefYesNo"
    assert p[EC.P_SHOW].obj.get("m_instanceParam") is True                  # master: per instance
    assert not p[EC.P_FRONT].obj.get("m_instanceParam")                     # per type
    assert p[EC.P_FRONT_ON].refs["formula"] == f"and({EC.P_SHOW}, {EC.P_FRONT})"
    z = _zones(prod)
    for role, pname in (("clearance: front working space", EC.P_FRONT_ON),
                        ("clearance: top", EC.P_TOP_ON)):
        ext = _ext(z[role])
        cells = ext.obj["m_cellList"]["value"]["m_cells"]
        assert [c["ptr_class"] for c in cells] == [
            "ExtrusionElemExtrusionHelper", "FamilyParametrizedElemParamsCell", "GenSweepPatternHelper"]
        (d,) = cells[1]["value"]["m_paramDrivenData"]
        assert (d["m_famParamId"], d["m_elemPropId"]) == (p[pname].elem_id, EC.ELEM_PROP_VISIBLE)
        dele = ext.header["m_parents"]["value"]["m_deletion"]
        assert p[pname].elem_id in dele and dele == sorted(dele)
    # the equipment's own solids are never bound
    for f in prod.forms:
        if not str(f.params.get("role", "")).startswith("clearance"):
            cells = _ext(f).obj["m_cellList"]["value"]["m_cells"]
            assert all(c["ptr_class"] != "FamilyParametrizedElemParamsCell" for c in cells)


@pytest.mark.parametrize("which", ["transformer", "panelboard"])
def test_the_zones_are_painted_see_through_magenta(request, which):
    prod = request.getfixturevalue(which)
    mats = [e for e in prod.doc.elements if e.class_name == "MaterialElem"]
    assert len(mats) == 1
    m = mats[0].obj["m_pMaterial"]["value"]
    assert (m["m_name"], m["m_color"] & 0xFFFFFF, m["m_transparency"], m["m_appearanceAssetId"]) == \
        (EC.CLEARANCE_MATERIAL, 0xFF00FF, EC.CLEARANCE_TRANSPARENCY, -1)
    assert mats[0].header["m_categroryId"] == EC.OST_MATERIALS
    for f in _zones(prod).values():
        ext = _ext(f)
        assert ext.obj["m_materialId"] == mats[0].elem_id
        assert mats[0].elem_id in ext.header["m_parents"]["value"]["m_deletion"]
    for f in prod.forms:
        if not str(f.params.get("role", "")).startswith("clearance"):
            assert _ext(f).obj.get("m_materialId", -1) == -1               # equipment unpainted


def test_the_written_family_validates_and_tracks_its_material(tmp_path, transformer):
    from rvt import adocument as AD
    from rvt.families import FamilyIndex
    out = str(tmp_path / "xf.rfa")
    rep = transformer.write(out)
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True
    fi = FamilyIndex(out)
    mat_ids = fi.ids_of_class(0, "MaterialElem")
    assert len(mat_ids) == 1
    doc = AD.open_document_object(out, AD.get_decoder(fi.schema))
    mt = AD._appinfo_body(doc.value if hasattr(doc, "value") else doc, "MaterialTracking")
    assert mt["m_elemIdSet"] == mat_ids


def test_the_dummy_variant_carries_no_zones():
    for prod in (F.make_transformer(kva=45, solid=False), F.make_panelboard(solid=False)):
        assert not _zones(prod)
        assert EC.P_SHOW not in prod.doc.params

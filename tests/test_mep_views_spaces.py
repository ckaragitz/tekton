"""Tests for rvt.mep.views_spaces: panel schedule views, MEP spaces, zones
and space tags (create + rename + delete planning).

Ground truth = the Revit MEP sample (rmebasicsampleproject):
 * 24 PanelScheduleViews, each the root of an 8-9 element OWNED cluster
   (Viewer, DBDrawing -> Viewport, FontElems, CategoryElem -> GStyleElem),
   naming their panel through TableView.m_targetId (742926 -> 742670) and
   their layout through m_idTemplate (638860 'Branch Panel'); the panel's
   ElementHeader back-links the view in m_regenOnly.
 * The stored table (m_oTableData, ~150 KB) is LAYOUT + parameter bindings
   only: every TableCellData.m_oCalculatedValue is null and body data
   cells carry m_text == "" -> the values are computed by Revit on open.
 * 87 spaces (RoomElem, OST_MEPSpaces -2003600) + 87 space tags (RoomTag,
   OST_MEPSpaceTags -2000485); spaces are zoned (ZoneElement.m_spaceIds is
   the two-sided member list) and located by m_point.

The plan-level tests run against the corpus (Document.from_file, ~1 s).
The single write-and-verify test is marked ``slow`` (RVT_SKIP_LARGE=1).
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
SAMPLE = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

LEVEL1 = 378117
WALL_TYPE = 563416
PANEL_480V = 619617
XFMR = 621242
VIEW_MDP1 = 742926           # smallest schedule-view cluster (target panel 742670)
VIEW_LP1 = 709455
SPACE = 379575                # 'Technology' 28, tag 379576, zone 379574
SPACE_TAG = 379576
ZONE_DEFAULT = 293242


@pytest.fixture(scope="module")
def rme():
    if not os.path.exists(SAMPLE):
        pytest.skip("rme sample not present")
    from rvt.mutate import Document
    return Document.from_file(SAMPLE)


def _fresh():
    from rvt.mutate import Document
    return Document.from_file(SAMPLE)


# ---------------------------------------------------------------------------
# ground truth (READ)
# ---------------------------------------------------------------------------
def test_schedule_view_names_panel_via_targetid_and_template(rme):
    from rvt.mep import views_spaces as vs
    d = vs.describe_panel_schedule_view(rme, VIEW_MDP1)
    assert d["class"] == "PanelScheduleView"
    assert d["target_panel"] == 742670 and rme.class_of(742670) == "FamilyInstance"
    assert d["template"] == 638860 and rme.class_of(638860) == "PanelScheduleTemplate"
    assert d["name"] == "MDP-1" and d["out_of_date"] is False
    kinds = {rme.class_of(e) for e, _ in d["cluster"]}
    assert {"Viewer", "DBDrawing", "Viewport", "FontElem",
            "CategoryElem", "GStyleElem"} <= kinds
    # the panel back-links its schedule view (header regenOnly)
    ph = rme.value(742670, 101)
    assert VIEW_MDP1 in ph["m_parents"]["value"]["m_regenOnly"]


def test_schedule_table_cells_store_no_computed_values(rme):
    v = rme.value(VIEW_MDP1)
    tv = v["PanelScheduleView::m_oTableData"]["value"]
    sections = tv["m_SectionData"]
    assert len(sections) == 4                        # header / body / summary / footer
    n_calc, n_text_data = 0, 0
    for s in sections:
        for row in s["value"]["m_tableCells"]:
            for c in row["value"]["m_arrCells"]:
                cv = c["value"]
                if cv.get("m_oCalculatedValue") is not None:
                    n_calc += 1
                if cv.get("m_cellType") == 3 and cv.get("m_text"):
                    n_text_data += 1
    assert n_calc == 0, "cell VALUES are computed by Revit, never stored"
    assert n_text_data == 0, "body data cells carry no stored text"


def test_panel_schedule_templates_catalog(rme):
    from rvt.mep import views_spaces as vs
    names = {t["name"] for t in vs.panel_schedule_templates(rme)}
    assert {"Branch Panel", "Switchboard", "Data Panel"} <= names


def test_space_is_roomelem_with_point_zone_and_tag(rme):
    from rvt.mep import views_spaces as vs
    d = vs.describe_space(rme, SPACE)
    assert d["class"] == "RoomElem" and d["category"] == vs.OST_MEPSpaces
    assert d["name"] == "Technology" and d["number"] == "28"
    assert d["zone"] == 379574 and d["tags"] == [SPACE_TAG]
    assert d["point"] and abs(d["point"][0] - 63.6266) < 1e-3
    # placement offset semantics: signed distance from the wall location
    # line, positive to the RIGHT of the drawing direction
    plc = d["placement"]
    assert plc["m_ref0"] == 573608 and abs(plc["m_offset0"] + 4.5589) < 1e-3
    assert plc["m_ref1"] == 573607 and abs(plc["m_offset1"] - 7.3944) < 1e-3
    got = vs.placement_from_walls(rme, d["point"], [573608, 573607])
    assert got["m_ref0"] in (573608, 573607) and got["m_ref1"] in (573608, 573607)
    offs = {got["m_ref0"]: got["m_offset0"], got["m_ref1"]: got["m_offset1"]}
    assert abs(offs[573608] + 4.5589) < 1e-3 and abs(offs[573607] - 7.3944) < 1e-3


def test_zone_membership_is_two_sided(rme):
    z = rme.value(379574)
    assert SPACE in z["m_spaceIds"]
    dz = rme.value(ZONE_DEFAULT)
    assert dz["m_bDefault"] is True and dz["m_spaceIds"] == []


# ---------------------------------------------------------------------------
# CREATE — panel schedule view for a NEW panel
# ---------------------------------------------------------------------------
def test_add_panel_schedule_view_clones_cluster_and_rewires():
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    panel = doc.add_family_instance(PANEL_480V, LEVEL1, position=(50.0, -90.0, 3.5))
    load = doc.add_family_instance(XFMR, LEVEL1, position=(50.0, -100.0, 0.3))
    circ = doc.add_circuit(panel, load, number="1")
    cluster = vs.add_panel_schedule_view(doc, panel, name="EP-T")
    view = cluster[0]
    assert view.class_name == "PanelScheduleView" and len(cluster) >= 7
    # rewired to OUR panel, template + name set, freshness flagged
    assert view.obj["m_targetId"] == panel.elem_id
    assert view.obj["m_viewName"] == "EP-T"
    assert view.obj["m_idTemplate"] == 638860
    assert view.obj["m_outOfDate"] is True and view.obj["m_cachedSlotNumbers"] == []
    # internal cluster references close over the NEW ids
    new_ids = {e.elem_id for e in cluster}
    assert view.obj["m_dbDrawingId"] in new_ids and view.obj["m_viewerId"] in new_ids
    assert set(view.obj["m_fontIds"]) <= new_ids
    assert all(p["second"] in new_ids for p in view.obj["m_colorToCategoryIdMap"])
    # ownership preserved (fonts/viewer/drawing owned by the view, viewport
    # by the drawing, gstyle by the category)
    by_class = {e.class_name: e for e in cluster}
    assert by_class["Viewer"].elemrec.owner_id == view.elem_id
    assert by_class["DBDrawing"].elemrec.owner_id == view.elem_id
    assert by_class["Viewport"].elemrec.owner_id == by_class["DBDrawing"].elem_id
    assert by_class["GStyleElem"].elemrec.owner_id == by_class["CategoryElem"].elem_id
    assert view.elemrec.owner_id == -1
    # the new panel back-links its view; the donor panel id is gone
    assert view.elem_id in panel.header["m_parents"]["value"]["m_regenOnly"]
    dumped = json.dumps([e.obj for e in cluster] + [e.header for e in cluster], default=str)
    assert "742670" not in dumped and "742926" not in dumped
    # referential integrity + serialisation for the whole plan
    for el in [panel, load, circ] + cluster:
        assert doc.check_references(el) == [], el.elem_id
        assert doc.serialize(el) is not None


def test_schedule_view_control_variant_keeps_slot_cache():
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    panel = doc.add_family_instance(PANEL_480V, LEVEL1, position=(0, 0, 3.5))
    view = vs.add_panel_schedule_view(doc, panel, out_of_date=False)[0]
    assert view.obj["m_outOfDate"] is False
    assert view.obj["m_cachedSlotNumbers"]              # donor cache kept


def test_schedule_view_for_existing_panel_needs_edit_pass(rme):
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    view = vs.add_panel_schedule_view(doc, 630241)[0]     # existing switchboard 'SWB'
    assert view.obj["m_targetId"] == 630241
    assert any("EXISTS in the template" in n for n in view.notes)
    plan = vs.link_schedule_view_into_existing_panel(doc, 630241, view.elem_id)
    assert plan.edited_ids == [630241]
    changes = {c.path: c for c in plan.changes}
    assert view.elem_id in changes["m_parents.value.m_regenOnly"].after


# ---------------------------------------------------------------------------
# CREATE — space + zone + tag inside walls made in the same run
# ---------------------------------------------------------------------------
def test_add_space_in_new_walls_with_zone_and_tag():
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    walls = [
        doc.add_wall(LEVEL1, WALL_TYPE, (100.0, -120.0), (120.0, -120.0), height=10),
        doc.add_wall(LEVEL1, WALL_TYPE, (120.0, -120.0), (120.0, -104.0), height=10),
        doc.add_wall(LEVEL1, WALL_TYPE, (120.0, -104.0), (100.0, -104.0), height=10),
        doc.add_wall(LEVEL1, WALL_TYPE, (100.0, -104.0), (100.0, -120.0), height=10),
    ]
    zone = vs.add_zone(doc, name="ELEC")
    space = vs.add_space(doc, LEVEL1, (110.0, -112.0), name="ELECTRICAL ROOM",
                         number="E101", upper_offset=10.0, bounding_walls=walls,
                         zone=zone)
    tag = vs.add_space_tag(doc, space)
    o = space.obj
    assert space.class_name == "RoomElem" and space.header["m_categroryId"] == vs.OST_MEPSpaces
    assert o["m_point"] == [110.0, -112.0]
    assert o["m_levelId"] == LEVEL1 and o["m_upperLevelId"] == LEVEL1
    assert o["m_upperOffset"] == 10.0 and o["m_height"] == 10.0
    assert vs._astring_param(o, vs.BIP_ROOM_NAME) == "ELECTRICAL ROOM"
    assert vs._astring_param(o, vs.BIP_ROOM_NUMBER) == "E101"
    assert o["m_zoneElementId"] == zone.elem_id and zone.obj["m_spaceIds"] == [space.elem_id]
    wall_ids = {w.elem_id for w in walls}
    assert {b["m_linkInstOrHostId"] for b in o["m_volumeBoundingElems"]} == wall_ids
    plc = o["m_pPlacement"]["value"]
    assert plc["m_ref0"] in wall_ids and plc["m_ref1"] in wall_ids
    assert plc["m_ref0"] != plc["m_ref1"]
    assert abs(abs(plc["m_offset0"]) - 8.0) < 1e-6 or abs(abs(plc["m_offset0"]) - 10.0) < 1e-6
    # computed caches invalidated
    assert o["m_loadPerLoadClass"] == [] and o["m_dActualPowerLoad"] == 0.0
    assert o["m_cachedCircuitId"] == {"m_id": 0}
    # reference planes moved to the new point (base + top of the volume)
    zs = sorted(f["value"]["m_pSurf"]["value"]["m_origin"][2] for f in o["m_referenceFaces"])
    org = o["m_referenceFaces"][0]["value"]["m_pSurf"]["value"]["m_origin"]
    assert abs(org[0] - 110.0) < 1e-9 and abs(org[1] + 112.0) < 1e-9
    assert abs((zs[1] - zs[0]) - 10.0) < 1e-6
    # rep = SerializedDummy (regenerate); tag points at the space in a plan view
    assert space.rep is None
    assert tag.class_name == "RoomTag" and tag.header["m_categroryId"] == vs.OST_MEPSpaceTags
    assert tag.obj["m_taggedRoomElemId"]["m_linkInstOrHostId"] == space.elem_id
    assert tag.obj["m_ownerDBViewId"] == 379500 == tag.header["m_ownerViewId"]
    assert tag.obj["m_oTagOrientationCell"]["value"]["m_headLocation"][:2] == [110.0, -112.0]
    assert tag.obj["m_pPlacement"]["value"] == plc
    for el in walls + [zone, space, tag]:
        assert doc.check_references(el) == [], el.elem_id
        assert doc.serialize(el) is not None


def test_add_room_is_unzoned_arch_room():
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    room = vs.add_room(doc, LEVEL1, (10.0, 10.0), name="OFFICE", number="7")
    assert room.header["m_categroryId"] == vs.OST_Rooms
    assert room.obj["m_zoneElementId"] == -1
    assert not any(e.class_name == "ZoneElement" for e in doc.new_elements)


# ---------------------------------------------------------------------------
# MODIFY / DELETE plans on EXISTING elements
# ---------------------------------------------------------------------------
def test_rename_space_edits_name_and_number_params(rme):
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    plans = vs.rename_space(doc, SPACE, name="STORAGE", number="199")
    paths = {c.path: c for p in plans for c in p.changes}
    news = {c.after for c in paths.values()}
    assert news == {"STORAGE", "199"}
    assert all(pl.elem_id == SPACE for pl in plans)


def test_rename_panel_schedule_view_plan(rme):
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    plan = vs.rename_panel_schedule_view(doc, VIEW_LP1, "LP-1 REV")
    assert plan.elem_id == VIEW_LP1
    assert [c.path for c in plan.changes] == ["m_viewName"]
    assert plan.changes[0].before == "LP-1" and plan.changes[0].after == "LP-1 REV"


def test_delete_schedule_view_takes_its_owned_cluster(rme):
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    cluster = set(vs.owned_cluster(doc, VIEW_LP1))
    assert len(cluster) >= 7
    plan = vs.delete_panel_schedule_view(doc, VIEW_LP1, cascade=True)
    assert cluster <= set(plan.ids_to_remove)
    # the panel that owned the view (581482) is a REFERRER (its regenOnly
    # mention is neutralised) - never deleted with its schedule
    assert 581482 not in set(plan.ids_to_remove)


def test_delete_space_cascades_to_its_tag_not_the_zone(rme):
    from rvt.mep import views_spaces as vs
    doc = _fresh()
    plan = vs.delete_space(doc, SPACE, cascade=True)
    removed = set(plan.ids_to_remove)
    assert SPACE in removed and SPACE_TAG in removed        # tag = annotation dependent
    assert 379574 not in removed                              # its zone survives...
    referrer_ids = {e["id"] for e in plan.referrer_edits}
    assert 379574 in referrer_ids                             # ...with the member removed


# ---------------------------------------------------------------------------
# WRITE + VERIFY (slow: ~1 min, full commit + structural verification)
# ---------------------------------------------------------------------------
@pytest.mark.slow
def test_schedule_view_and_space_write_and_verify(tmp_path):
    if os.environ.get("RVT_SKIP_LARGE"):
        pytest.skip("RVT_SKIP_LARGE set")
    from rvt.commit import verify_written
    from rvt.mep import views_spaces as vs
    from rvt.mutate import Document
    doc = _fresh()
    panel = doc.add_family_instance(PANEL_480V, LEVEL1, position=(50.0, -90.0, 3.5))
    load = doc.add_family_instance(XFMR, LEVEL1, position=(50.0, -100.0, 0.3))
    circ = doc.add_circuit(panel, load, number="1")
    cluster = vs.add_panel_schedule_view(doc, panel, name="EP-W")
    walls = [
        doc.add_wall(LEVEL1, WALL_TYPE, (100.0, -120.0), (120.0, -120.0), height=10),
        doc.add_wall(LEVEL1, WALL_TYPE, (120.0, -120.0), (120.0, -104.0), height=10),
        doc.add_wall(LEVEL1, WALL_TYPE, (120.0, -104.0), (100.0, -104.0), height=10),
        doc.add_wall(LEVEL1, WALL_TYPE, (100.0, -104.0), (100.0, -120.0), height=10),
    ]
    space = vs.add_space(doc, LEVEL1, (110.0, -112.0), name="ELECTRICAL ROOM",
                         number="E101", upper_offset=10.0, bounding_walls=walls)
    tag = vs.add_space_tag(doc, space)
    zone = doc._vs_default_zone
    els = [panel, load, circ] + cluster + walls + [zone, space, tag]
    out = str(tmp_path / "vs.rvt")
    vs.commit_elements(SAMPLE, out, doc, els)
    ids = [e.elem_id for e in els]
    v = verify_written(out, ids)
    assert v["crc_failures"] == 0 and v["walker_errors"] == 0 and v["stamps_ok"]
    assert v["elemtable_count"] == v["header_count"]
    # ECC is judged by the validator (verify_written's page-by-page trailer
    # comparison mis-flags a FINAL block that happens to fill a whole page —
    # see docs/inbox/mep-schedules.md "verify_written false positive")
    from rvt.validate import validate_file
    rep = validate_file(out, layers=("structure",))
    assert rep.ok, [f.message for f in rep.errors]
    for s in (101, 102, 103):
        assert all(x["clean"] for x in v["new_ids_found"][s].values())
        assert len(v["new_ids_found"][s]) == len(ids)
    d = Document.from_file(out)
    assert d.value(cluster[0].elem_id)["m_targetId"] == panel.elem_id
    assert d.et_by_id[cluster[1].elem_id].owner_id == cluster[0].elem_id   # owner links written
    ds = vs.describe_space(d, space.elem_id)
    assert ds["name"] == "ELECTRICAL ROOM" and ds["zone"] == zone.elem_id
    assert d.value(zone.elem_id)["m_spaceIds"] == [space.elem_id]
    assert vs.space_tags_of(d, space.elem_id) == [tag.elem_id]

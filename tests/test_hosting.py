"""Tests for rvt.hosting: mounting FamilyInstances on wall faces.

Ground truth is the Revit MEP sample (rmebasicsampleproject): 13 SketchPlanes
whose ``m_oPlaneRef`` is a ``GeomOnPlaneRef`` into an ``SWall`` face
(geomTag 5 = the -leftNormal / right-of-direction side, 6 = the
+leftNormal / left side), 218 ``DummyPlaneRef`` work planes, and the
face-hosted panelboards / receptacles standing on them.

The template Document takes ~1-3 min to build on first load (concatenates
the element segments); set ``RVT_SEG_CACHE`` to reuse them.
"""
import math
import os

import pytest

from rvt import hosting
from rvt.hosting import (FACE_TAG_EXTERIOR, FACE_TAG_INTERIOR, face_frame,
                         wall_geometry)
from rvt.mutate import Document

CACHE = os.environ.get("RVT_SEG_CACHE")

# rme facts (element ids in the template)
LEVEL1 = 378117
WALL_TYPE = 563416
PANEL_480V = 619617            # 480V MCB Surface :: 400 A
EXISTING_WALL = 573608          # electrical-room wall (dummy plane 581481 sits on its face)
WALL_573738 = 573738            # carries BOTH a tag-5 and a tag-6 hosting plane
SP_TAG5_573738 = 625760
SP_TAG6_573738 = 625865
DUMMY_PLANE = 581481            # DummyPlaneRef hosting panels 581482-85


@pytest.fixture(scope="module")
def rme():
    return Document.load("rmebasicsampleproject", CACHE)


# ---------------------------------------------------------------------------
# (a) the reverse-engineered hosting model
# ---------------------------------------------------------------------------

def _wall_face_planes(doc):
    """(sketchplane_id, wall_id, tag) for every GeomOnPlaneRef->SWall plane."""
    out = []
    for spid in doc.ids_of_class("SketchPlane"):
        pref = ((doc.value(spid) or {}).get("m_oPlaneRef") or {})
        if pref.get("ptr_class") != "GeomOnPlaneRef":
            continue
        gr = ((pref.get("value") or {}).get("m_geomRef") or {})
        wid = gr.get("m_elemId")
        if isinstance(wid, int) and wid > 0 and doc.class_of(wid) == "SWall":
            out.append((spid, wid, gr.get("m_geomTag"), gr.get("m_subTag")))
    return out


def test_face_reference_is_small_stable_tag_not_guid(rme):
    planes = _wall_face_planes(rme)
    assert len(planes) >= 10, planes
    tags = {t for _, _, t, _ in planes}
    # side faces are tag 5 / 6 (tag 1 = the location-plane group, unused here)
    assert {FACE_TAG_INTERIOR, FACE_TAG_EXTERIOR} <= tags <= {1, FACE_TAG_INTERIOR, FACE_TAG_EXTERIOR}
    assert all(sub == -1 for _, _, _, sub in planes)      # no sub-tag


def test_side_faces_offset_half_thickness(rme):
    # tag 5 plane origin sits at -halfThickness from the location line
    # (right of direction); tag 6 at +halfThickness (left) -> the two SIDE faces
    checked = 0
    for spid, wid, tag, _ in _wall_face_planes(rme):
        if tag not in (FACE_TAG_INTERIOR, FACE_TAG_EXTERIOR):
            continue
        g = wall_geometry(rme, wid)
        org = ((rme.value(spid).get("m_oTrf") or {}).get("value") or {}).get("m_or")
        nx, ny = g.left_normal
        off = (org[0] - g.start[0]) * nx + (org[1] - g.start[1]) * ny
        want = g.thickness / 2 * (1 if tag == FACE_TAG_EXTERIOR else -1)
        assert abs(off - want) < 1e-6, (spid, wid, tag, off, want)
        assert abs(org[2] - g.base_z) < 1e-6                # plane origin at wall base z
        checked += 1
    assert checked >= 10


def test_frame_formula_reproduces_every_real_plane(rme):
    # Z = outward face normal, Y = up, X = up x Z, m_3x3 stored COLUMN-major:
    # the reconstruction must match Autodesk's stored matrix on all specimens
    match = 0
    for spid, wid, tag, _ in _wall_face_planes(rme):
        if tag not in (FACE_TAG_INTERIOR, FACE_TAG_EXTERIOR):
            continue
        r = hosting.reconstruct_plane_trf(rme, spid)
        assert r is not None
        for prow, srow in zip(r["predicted"], r["stored"]):
            for a, b in zip(prow, srow):
                assert abs(a - b) < 1e-9, (spid, r)
        match += 1
    assert match >= 10


def test_hosted_instance_shares_the_plane_frame(rme):
    # a face-hosted instance's InstanceInfo.m_Trf 3x3 == its SketchPlane's
    # m_oTrf 3x3 (742670 panel on 623305; receptacles on both faces of 573738)
    for iid, spid in ((742670, 623305), (460372, SP_TAG5_573738), (460229, SP_TAG6_573738)):
        iv = rme.value(iid)
        assert iv["m_hostId"] == spid and iv["m_workPlaneBased"] is True
        assert iv["m_assocLevelId"] == -1
        itrf = iv["m_pInstanceInfo"]["value"]["m_Trf"]["m_3x3"]
        ptrf = rme.value(spid)["m_oTrf"]["value"]["m_3x3"]
        for prow, irow in zip(ptrf, itrf):
            for a, b in zip(prow, irow):
                assert abs(a - b) < 1e-9


def test_sketchplane_header_lists_wall_dependency(rme):
    # a wall-face SketchPlane's ElementHeader deletion parents = [wall, self]
    # and regenOnly = [the wall's TYPE]  (the dependency question)
    for spid, wid, tag, _ in _wall_face_planes(rme):
        if tag not in (FACE_TAG_INTERIOR, FACE_TAG_EXTERIOR):
            continue
        par = ((rme.value(spid, 101) or {}).get("m_parents") or {}).get("value") or {}
        assert sorted(par.get("m_deletion")) == sorted({wid, spid})
        wtype = (rme.value(wid) or {}).get("m_WallAttributesId")
        assert par.get("m_regenOnly") == [wtype]


def test_dummy_planeref_carries_no_wall_reference(rme):
    # the OTHER real pattern: 218/240 hosting planes reference nothing
    v = rme.value(DUMMY_PLANE)
    pref = v["m_oPlaneRef"]
    assert pref["ptr_class"] == "DummyPlaneRef"
    gr = pref["value"]["m_geomRef"]
    assert gr["m_elemId"] == -1 and gr["m_geomTag"] == -1
    # ... yet it is COINCIDENT with wall 573608's face plane (x = 59.2564)
    g = wall_geometry(rme, EXISTING_WALL)
    fx = g.point_on_face(FACE_TAG_EXTERIOR, 0.0)[0]
    px = pref["value"]["m_pPlane"]["value"]["m_origin"][0]
    assert abs(fx - px) < 1e-3


def test_side_facing_point(rme):
    # room 573809 is at x > 59.256 (the +leftNormal side of wall 573608)
    assert hosting.side_facing_point(rme, EXISTING_WALL, (60.5, 115.0)) == FACE_TAG_EXTERIOR
    assert hosting.side_facing_point(rme, EXISTING_WALL, (58.0, 115.0)) == FACE_TAG_INTERIOR


def test_side_aliases():
    assert hosting._resolve_side("interior") == FACE_TAG_INTERIOR == hosting._resolve_side("right")
    assert hosting._resolve_side("exterior") == FACE_TAG_EXTERIOR == hosting._resolve_side("left")
    assert hosting._resolve_side(5) == 5 and hosting._resolve_side(6) == 6
    with pytest.raises(ValueError):
        hosting._resolve_side("top")
    with pytest.raises(ValueError):
        hosting._resolve_side(7)


# ---------------------------------------------------------------------------
# (b) authoring API
# ---------------------------------------------------------------------------

def test_add_sketchplane_geom_on_existing_wall(rme):
    sp = hosting.add_sketchplane_on_wall(rme, EXISTING_WALL, side="exterior",
                                         at_point_ft=(60.0, 118.0, 4.0))
    assert sp.class_name == "SketchPlane" and sp.rep is None      # seq103 = SerializedDummy
    pv = sp.obj["m_oPlaneRef"]
    assert pv["ptr_class"] == "GeomOnPlaneRef"
    gr = pv["value"]["m_geomRef"]
    assert gr["m_elemId"] == EXISTING_WALL and gr["m_geomTag"] == FACE_TAG_EXTERIOR
    assert gr["m_subTag"] == -1 and pv["value"]["m_offset"] == [0.0, 0.0]
    # origin projected ON the exterior face (x = 59.2564), z kept
    org = sp.obj["m_oTrf"]["value"]["m_or"]
    g = wall_geometry(rme, EXISTING_WALL)
    assert abs(org[0] - g.point_on_face(FACE_TAG_EXTERIOR, 0.0)[0]) < 1e-6
    assert abs(org[1] - 118.0) < 1e-6 and abs(org[2] - 4.0) < 1e-6
    # frame Z (3rd column) = outward normal = +leftNormal for tag 6
    m3 = sp.obj["m_oTrf"]["value"]["m_3x3"]
    n = (m3[0][2], m3[1][2], m3[2][2])
    assert n == pytest.approx((g.left_normal[0], g.left_normal[1], 0.0), abs=1e-9)
    # header parents: wall in deletion, wall type in regenOnly
    par = sp.header["m_parents"]["value"]
    assert set(par["m_deletion"]) == {EXISTING_WALL, sp.elem_id}
    assert par["m_regenOnly"] == [g.wall_type_id]
    assert rme.check_references(sp) == []


def test_add_sketchplane_dummy_has_no_wall_ref(rme):
    sp = hosting.add_sketchplane_on_wall(rme, EXISTING_WALL, side="interior",
                                         plane_ref="dummy")
    pv = sp.obj["m_oPlaneRef"]
    assert pv["ptr_class"] == "DummyPlaneRef"
    plane = pv["value"]["m_pPlane"]["value"]
    g = wall_geometry(rme, EXISTING_WALL)
    # coincident with the interior face plane, canonical up frame
    assert abs(plane["m_origin"][0] - g.point_on_face(FACE_TAG_INTERIOR, 0.0)[0]) < 1e-6
    assert plane["m_yVec"] == [0.0, 0.0, 1.0]
    xv = plane["m_xVec"]
    # xVec x yVec == outward normal of the interior face (-leftNormal)
    n = (xv[1] * 1.0 - xv[2] * 0.0, xv[2] * 0.0 - xv[0] * 1.0, 0.0)
    assert n == pytest.approx((-g.left_normal[0], -g.left_normal[1], 0.0), abs=1e-9)
    par = sp.header["m_parents"]["value"]
    assert EXISTING_WALL not in par["m_deletion"]            # no wall dependency
    assert rme.check_references(sp) == []


def test_host_instance_on_existing_wall(rme):
    sp, inst = hosting.host_instance_on_wall(
        rme, symbol_id=PANEL_480V, wall=EXISTING_WALL,
        distance_along_ft=6.0, elevation_ft=4.0, side="exterior", level_id=LEVEL1)
    assert inst.template_id == 742670          # cloned from a REAL face-hosted 619617
    o = inst.obj
    assert o["m_hostId"] == sp.elem_id and o["m_workPlaneBased"] is True
    assert o["m_assocLevelId"] == -1 and o["m_scheduleOnlyLevelId"] == LEVEL1
    assert o["m_workPlaneFlipped"] is False and o["m_hostParam"] == 0.0
    ii = o["m_pInstanceInfo"]["value"]
    assert ii["m_symbolId"] == PANEL_480V
    # instance frame == the sketch plane frame, origin on the face
    assert ii["m_Trf"]["m_3x3"] == sp.obj["m_oTrf"]["value"]["m_3x3"]
    g = wall_geometry(rme, EXISTING_WALL)
    want = g.point_on_face(FACE_TAG_EXTERIOR, 6.0, g.base_z + 4.0)
    assert ii["m_Trf"]["m_or"] == pytest.approx(list(want), abs=1e-6)
    # rep (GElement) carries the same frame
    if inst.rep is not None:
        for node in inst.rep.get("m_subNodes") or []:
            info = (((node.get("value") or {}).get("m_instanceInfo") or {}).get("value")) or {}
            if info:
                assert info["m_Trf"]["m_3x3"] == ii["m_Trf"]["m_3x3"]
    # header: sketch plane in deletion, WALL in regenOnly, symbol appearance
    par = inst.header["m_parents"]["value"]
    assert {sp.elem_id, inst.elem_id, PANEL_480V, LEVEL1} <= set(par["m_deletion"])
    assert EXISTING_WALL in par["m_regenOnly"]
    assert PANEL_480V in par["m_appearanceParents"]
    assert rme.check_references(sp) == [] and rme.check_references(inst) == []
    # serializes to real records in all three seqs
    for el in (sp, inst):
        recs = rme.serialize(el)
        assert recs and {s for s, _ in recs} == {101, 102, 103}
        assert all(len(b) > 20 for _, b in recs)


def test_host_instance_on_wall_created_in_same_run(rme):
    # electrical-room case: wall + plane + panel all planned in one run
    wall = rme.add_wall(level_id=LEVEL1, wall_type_id=WALL_TYPE,
                        p0=(64.5, 118.0), p1=(64.5, 106.0), height=8.0)
    tag = hosting.side_facing_point(rme, wall, (60.5, 115.0))
    assert tag == FACE_TAG_INTERIOR          # room point is on the -leftNormal side
    sp, inst = hosting.host_instance_on_wall(
        rme, symbol_id=PANEL_480V, wall=wall, distance_along_ft=6.0,
        elevation_ft=4.0, side=tag, level_id=LEVEL1)
    gr = sp.obj["m_oPlaneRef"]["value"]["m_geomRef"]
    assert gr["m_elemId"] == wall.elem_id and gr["m_geomTag"] == FACE_TAG_INTERIOR
    assert wall.elem_id in sp.header["m_parents"]["value"]["m_deletion"]
    assert wall.elem_id in inst.header["m_parents"]["value"]["m_regenOnly"]
    # frame: tag-5 of a wall running -Y => Z = -X outward, X = -Y (== real 595054)
    m3 = sp.obj["m_oTrf"]["value"]["m_3x3"]
    flat = [c for row in m3 for c in row]
    assert flat == pytest.approx([0.0, 0.0, -1.0, -1.0, 0.0, 0.0, 0.0, 1.0, 0.0], abs=1e-9)
    # panel origin: on the -X face, 6 ft along, 4 ft above Level 1 (0.309)
    org = inst.obj["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"]
    assert org == pytest.approx([64.5 - 0.37729658792650866 / 2, 112.0, 0.30896239133315895 + 4.0],
                                abs=1e-6)
    # every reference (incl. the not-yet-existing wall) resolves within the plan
    for el in (wall, sp, inst):
        assert rme.check_references(el) == []


def test_dummy_plane_fallback_on_created_wall(rme):
    wall = rme.add_wall(level_id=LEVEL1, wall_type_id=WALL_TYPE,
                        p0=(80.0, 118.0), p1=(80.0, 106.0), height=8.0)
    sp, inst = hosting.host_instance_on_wall(
        rme, symbol_id=PANEL_480V, wall=wall, distance_along_ft=6.0,
        elevation_ft=4.0, side="interior", level_id=LEVEL1, plane_ref="dummy")
    assert sp.obj["m_oPlaneRef"]["ptr_class"] == "DummyPlaneRef"
    # no reference into the new wall anywhere, but instance still hosted
    assert wall.elem_id not in sp.header["m_parents"]["value"]["m_deletion"]
    assert wall.elem_id not in inst.header["m_parents"]["value"]["m_regenOnly"]
    assert inst.obj["m_hostId"] == sp.elem_id and inst.obj["m_workPlaneBased"] is True
    for el in (wall, sp, inst):
        assert rme.check_references(el) == []


def test_reuse_one_plane_for_several_panels(rme):
    # real files share one SketchPlane among several instances
    sp = hosting.add_sketchplane_on_wall(rme, EXISTING_WALL, side="exterior")
    a = hosting.host_instance_on_wall(rme, PANEL_480V, EXISTING_WALL, 3.0, 4.0,
                                      sketchplane=sp, level_id=LEVEL1)[1]
    b = hosting.host_instance_on_wall(rme, PANEL_480V, EXISTING_WALL, 9.0, 4.0,
                                      sketchplane=sp, level_id=LEVEL1)[1]
    assert a.obj["m_hostId"] == b.obj["m_hostId"] == sp.elem_id
    assert a.elem_id != b.elem_id
    oa = a.obj["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"]
    ob = b.obj["m_pInstanceInfo"]["value"]["m_Trf"]["m_or"]
    assert abs(math.hypot(oa[0] - ob[0], oa[1] - ob[1]) - 6.0) < 1e-6   # 6 ft apart on the face


# ---------------------------------------------------------------------------
# (c) end-to-end: commit + verify a hosted panel on an existing wall
# ---------------------------------------------------------------------------

@pytest.mark.slow
def test_commit_hosted_panel_roundtrip(rme, tmp_path):
    from rvt.commit import commit_new_elements, verify_written
    src = os.path.join(os.path.dirname(__file__), "..", "samples", "rmebasicsampleproject.rvt")
    if not os.path.exists(src):
        pytest.skip("rme sample not present")
    if os.environ.get("RVT_SKIP_LARGE"):
        pytest.skip("large round trip skipped")
    doc = Document.load("rmebasicsampleproject", CACHE)   # fresh id allocator state
    sp, inst = hosting.host_instance_on_wall(doc, PANEL_480V, EXISTING_WALL, 6.0, 4.0,
                                             side="exterior", level_id=LEVEL1)
    recs = [dict(doc.serialize(sp)), dict(doc.serialize(inst))]
    out = str(tmp_path / "hosted.rvt")
    rep = commit_new_elements(src, out, recs, [sp.elemrec, inst.elemrec])
    v = verify_written(out, [sp.elem_id, inst.elem_id])
    assert v["crc_failures"] == 0 and v["ecc_mismatches"] == 0
    assert v["walker_errors"] == 0 and v["stamps_ok"]
    assert v["elemtable_count"] == v["header_count"] == rep.elemtable_count_after
    for seq in (101, 102, 103):
        assert v["new_ids_found"][seq][sp.elem_id]["clean"] is not False
        assert v["new_ids_found"][seq][inst.elem_id]["clean"]
    # decode back: hosting fields survived the write
    d = Document.from_file(out)
    iv = d.value(inst.elem_id)
    assert iv["m_hostId"] == sp.elem_id and iv["m_workPlaneBased"] is True
    gr = d.value(sp.elem_id)["m_oPlaneRef"]["value"]["m_geomRef"]
    assert gr["m_elemId"] == EXISTING_WALL and gr["m_geomTag"] == FACE_TAG_EXTERIOR

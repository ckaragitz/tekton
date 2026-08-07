"""Tests for rvt.mutate: the element-creation planner (mutation layer).

These build a new wall and new family instances against the two template
documents (racbasic = architectural, rme = MEP) and assert referential
integrity: every ElementId the new records reference must already exist in
the template (or be one of the new elements).  Serialization is stubbed
until the parallel ``rvt.encode`` lands.

Loading a template concatenates the whole element segment (all save
units), which takes ~1-3 minutes per template on first run; set
``RVT_SEG_CACHE`` to a directory to cache the segments between runs.
"""
import math
import os
import zlib
import struct

import pytest

from rvt import mutate
from rvt.mutate import (Document, record_stamp, DUMMY_STAMP,
                        CLASS_SERIALIZED_DUMMY, CLASS_ELEMENT_HEADER,
                        CLASS_GELEMENT, CLASS_SWALL, CLASS_FAMILY_INSTANCE)

CACHE = os.environ.get("RVT_SEG_CACHE")


@pytest.fixture(scope="module")
def rac():
    return Document.load("racbasicsampleproject", CACHE)


@pytest.fixture(scope="module")
def rme():
    return Document.load("rmebasicsampleproject", CACHE)


# ---------------------------------------------------------------------------
# constants / codebook facts established by the planner
# ---------------------------------------------------------------------------

def test_record_stamp_is_adler32():
    # seq-102/103 stamp == adler32(u16 class_id + object bytes); dummy const
    assert DUMMY_STAMP == 0x0069003C == record_stamp(CLASS_SERIALIZED_DUMMY)
    assert zlib.adler32(b"") == 1                     # id -1 sentinel stamp
    payload = struct.pack("<H", 0x08CC) + b"\x00" * 16
    assert record_stamp(0x08CC, b"\x00" * 16) == zlib.adler32(payload)


def test_stamp_matches_real_records(rac):
    # spot-check the corpus: stamp of stored records == adler32(payload)
    seen = 0
    for eid in list(rac.idx[102])[:2000]:
        r = rac.idx[102][eid]
        assert record_stamp(r.class_id, r.payload) == r.stamp
        r3 = rac.idx[103][eid]
        assert record_stamp(r3.class_id, r3.payload) == r3.stamp
        seen += 1
    assert seen == 2000


def test_unit0_is_the_host_element_table(rac):
    # the ids in the host document's records == Global/ElemTable ids
    assert set(rac.et_by_id) <= set(rac.idx[102])
    assert rac.et.count == len(rac.et_by_id)
    # the id watermark (IdentifierSource.m_last) >= every issued id
    assert rac.last_issued_id >= max(rac.et_by_id)


# ---------------------------------------------------------------------------
# racbasic: architectural template - a new wall + a free family instance
# ---------------------------------------------------------------------------

def test_catalog_racbasic(rac):
    ids = {l["id"] for l in rac.levels()}
    named = {l["id"] for l in rac.levels() if l["name"] == "Level 1"}
    # 311 = the project 'Level 1'; 800333 is a second element also named
    # 'Level 1' (an in-place family's owned level living in the host table)
    assert 311 in named and 245423 in ids and 694 in ids
    assert abs(rac._level_elevation(245423) - 9.84252) < 1e-4       # 3.0 m
    types = rac.wall_types_with_instances()
    assert 232827 in types and 198367 in types                    # Interior/Timber types


def test_add_wall_racbasic(rac):
    wm_before = rac.last_issued_id
    w = rac.add_wall(level_id=311, wall_type_id=232827,
                     p0=(0.0, 0.0), p1=(20.0, 0.0), top_level_id=245423)
    assert w.elem_id == wm_before + 1 and w.class_id == CLASS_SWALL
    obj = w.obj
    assert obj["m_id"] == w.elem_id
    assert obj["m_assocLevelId"] == 311 and obj["m_upToLevelId"] == 245423
    assert obj["m_WallAttributesId"] == 232827
    crv = obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
    assert crv["m_origin"] == [0.0, 0.0, 0.0]
    assert crv["m_dirVec"] == [1.0, 0.0, 0.0]
    assert crv["m_endParams"] == [0.0, pytest.approx(20.0)]
    assert obj["m_pCurveDriver"]["value"]["m_sideJoins"] == []   # unjoined
    # header: category walls, class SWall, parents rewritten to the new deps
    hdr = w.header
    assert hdr["m_categroryId"] == -2000011                        # OST_Walls
    assert hdr["m_classDef"]["m_ref"]["classref"] == "SWall"
    dele = hdr["m_parents"]["value"]["m_deletion"]
    assert {311, 245423, 232827, w.elem_id} <= set(dele)
    # geometry rep: no cached solid -> SerializedDummy in seq 103
    assert w.rep is None and w.rep_class_id == CLASS_SERIALIZED_DUMMY
    # ElemTable row
    er = w.elemrec
    assert er.elem_id == w.elem_id == er.original_id
    assert er.creation_ep == rac.new_episode == er.modified_ep
    assert len(er.pack()) == 40
    # referential integrity
    assert rac.check_references(w) == []


def test_add_wall_needs_clonable_type(rac):
    with pytest.raises(LookupError):
        rac.add_wall(level_id=311, wall_type_id=397,       # no straight instance
                     p0=(0, 0), p1=(1, 0), height=8)


def test_add_family_instance_racbasic(rac):
    # a free-standing (symbol == master) instance: PV panel symbol 776839
    syms = {s["symbol_id"] for s in rac.symbols(category=-2001040)}
    assert 776839 in syms
    fi = rac.add_family_instance(symbol_id=776839, level_id=311,
                                 position=(5.0, 5.0, 0.0), rotation=math.pi / 2)
    assert fi.class_id == CLASS_FAMILY_INSTANCE
    ii = fi.obj["m_pInstanceInfo"]["value"]
    assert ii["m_symbolId"] == 776839 == fi.obj["m_masterSymbolId"]
    assert ii["m_Trf"]["m_or"] == [5.0, 5.0, 0.0]
    assert ii["m_Trf"]["m_3x3"][0] == pytest.approx([0.0, 1.0, 0.0], abs=1e-9)
    assert fi.obj["m_assocLevelId"] == 311 and fi.obj["m_hostId"] == -1
    assert rac.check_references(fi) == []


def test_plan_and_diff(rac):
    plan = rac.plan()
    streams = {c["stream"] for c in plan["streams"]}
    assert {"Global/ElemTable", "Partitions/<N>", "Global/DocumentIncrementTable",
            "Global/History", "BasicFileInfo", "Global/Latest"} <= streams
    assert plan["new_episode"] == rac.current_episode + 1
    # every planned element is referentially clean
    assert all(v == [] for v in plan["referential_integrity"].values())


# ---------------------------------------------------------------------------
# rme: MEP template - a panelboard instance + a receptacle
# ---------------------------------------------------------------------------

def test_catalog_rme(rme):
    lv = {l["name"] for l in rme.levels()}
    assert {"Level 1", "Level 2", "Level 3", "Roof Level"} <= lv
    equip = {s["symbol_id"]: s for s in rme.symbols(category=-2001040)}
    # the 208V MLO panelboard type and its family
    assert 455409 in equip
    assert equip[455409]["family_name"].startswith("M_Lighting and Appliance Panelboard")


def test_add_panelboard_rme(rme):
    # duplicate the panel pattern of specimen 581483: face-hosted on the
    # existing SketchPlane 581481 (wall face), symbol 455409 '400 A'
    p = rme.add_family_instance(symbol_id=455409, level_id=378117,
                                position=(59.26, 104.5, 2.562), rotation=0.0,
                                host_id=581481, template_instance_id=581483)
    ii = p.obj["m_pInstanceInfo"]["value"]
    assert ii["m_symbolId"] == 455409 == p.obj["m_masterSymbolId"]
    assert p.obj["m_hostId"] == 581481
    assert p.obj["m_id"] == p.elem_id
    # the cloned connector manager / design-property manager carry over but
    # must not reference the template instance's id any more
    refs = [i for _, i in rme.referenced_ids(p)]
    assert 581483 not in refs
    # seq 103: instances have a formulaic GElement rep (cloned + rewritten)
    assert p.rep is not None and p.rep_class_id == CLASS_GELEMENT
    assert p.rep["m_elementId"] == p.elem_id and p.rep["m_GInfo"]["m_tag"] == p.elem_id
    ginst = [n for n in p.rep["m_subNodes"] if n.get("ptr_class") == "GInstance"]
    assert ginst and ginst[0]["value"]["m_instanceInfo"]["value"]["m_symbolId"] == 455409
    assert rme.check_references(p) == []


def test_add_receptacle_rme(rme):
    f = rme.add_family_instance(symbol_id=342654, level_id=378117,
                                position=(20.0, 15.0, 1.0),
                                template_instance_id=467291, host_id=467294)
    assert f.obj["m_pInstanceInfo"]["value"]["m_symbolId"] == 342654
    assert rme.check_references(f) == []


def test_add_wall_rme(rme):
    w = rme.add_wall(level_id=378117, wall_type_id=563414,
                     p0=(0.0, 0.0), p1=(0.0, 12.0), top_level_id=378118)
    assert w.obj["m_WallAttributesId"] == 563414
    crv = w.obj["m_pCurveDriver"]["value"]["m_pCrv"]["value"]
    assert crv["m_dirVec"] == pytest.approx([0.0, 1.0, 0.0])
    assert crv["m_endParams"][1] == pytest.approx(12.0)
    assert rme.check_references(w) == []
    # the wall lands in the host document (unit 0) with a new ElemTable row
    assert w.elem_id not in rme.et_by_id and w.elem_id > max(rme.et_by_id)


def test_serialize_stub(rac):
    # rvt.encode is the parallel serializer; until it exists serialize()
    # must degrade gracefully (None), never crash the planner.
    el = rac.new_elements[0]
    out = rac.serialize(el)
    if out is None:
        recs = el.records()
        assert [s for s, _, _ in recs] == [101, 102, 103]
        assert recs[0][1] == CLASS_ELEMENT_HEADER
    else:                                   # encoder landed: bytes back
        assert all(isinstance(b, (bytes, bytearray)) for _, b in out)

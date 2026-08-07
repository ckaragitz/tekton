"""Tests for rvt.render.inspect -- the geometry-carriage (LOAD-vs-RENDER) inspector.

Evidence tiers:

1. THE CLASSIFIER, corpus-free: synthetic decoded G-node trees exercise
   every reported kind (brep / instance-ref / instance-ref+geom /
   curves-only / mesh / empty-grep / dummy) and the carriage counts.
2. THE CORPUS LAW (rstbasic sample): every native wall (SWall) carries a
   baked B-rep (never a dummy); every Level / Grid (datum) is a dummy;
   family symbols carry solids; model instances reference their symbol.
3. OUR CREATED FILES (the ifc-room walls-only / room builds): our created
   walls carry SerializedDummy reps (the LOAD-not-RENDER finding), while
   our created symbols carry real 6-face solids and our instances resolve
   to them by reference.

Corpus / experiment files skip when absent.
"""
from __future__ import annotations

import json
import os

import pytest

from rvt.render import inspect as RI

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCHEMA_JSON = os.path.join(ROOT, "extracted", "_schema", "schema.json")
RST_DIR = os.path.join(ROOT, "extracted", "rstbasicsampleproject")
HAVE_CORPUS = os.path.exists(SCHEMA_JSON) and os.path.isdir(RST_DIR)

ROOM_UNJOINED = os.path.join(
    ROOT, "experiments", "ifc_room", "electrical_room_2500a_walls_only_unjoined.rvt")
ROOM_FULL = os.path.join(ROOT, "experiments", "ifc_room", "electrical_room_2500a.rvt")

corpus = pytest.mark.skipif(not HAVE_CORPUS, reason="extracted corpus / schema not present")
skip_large = pytest.mark.skipif(
    os.environ.get("RVT_SKIP_LARGE") == "1", reason="RVT_SKIP_LARGE=1")


# ---------------------------------------------------------------------------
# synthetic decoded structures (mimic rvt.objects decode output)
# ---------------------------------------------------------------------------

def _ptr(cls, value):
    return {"ptr_class": cls, "pid": -1, "value": value}


def _ginfo(tag=-1, cat=-1, flags=557060):
    return {"m_categoryId": cat, "m_tag": tag, "m_controlCommand": 0, "m_flags": flags}


def _plane():
    return _ptr("Plane", {"m_Envelope": {"m_corners": [[0, 0], [10, 12]]},
                          "m_orientFlag": True,
                          "m_origin": [0.0, 0.0, 0.0],
                          "m_xVec": [1.0, 0.0, 0.0],
                          "m_yVec": [0.0, 1.0, 0.0]})


def _face(tag=1, mat=-1):
    return _ptr("Face", {"m_GInfo": _ginfo(tag=tag),
                         "m_pFirstLoop": _ptr("EdgeLoop", {"m_GInfo": _ginfo()}),
                         "m_faceRegions": [], "m_pGFilling": None,
                         "m_oBackgroundFilling": None,
                         "m_renderStyleId": mat, "m_cutType": 0,
                         "m_faceFlags_v9": 4, "m_pSurf": _plane()})


def _edge(tag=3):
    return _ptr("Edge", {"m_GInfo": _ginfo(tag=tag),
                         "m_pFace": [{"weakref": 4}, {"weakref": 5}],
                         "m_next": [{"weakref": 6}, {"weakref": 0}],
                         "m_prev": [{"weakref": 7}, {"weakref": 0}],
                         "m_interiorEdgePnts": [],
                         "m_firstAndLastEdgePnts": [{"uv": [[0, 0], [0, 0]]},
                                                    {"uv": [[10, 0], [0, 0]]}],
                         "m_flags": 6})


def _geometry(nfaces=6, nedges=12, mat=-1):
    return _ptr("Geometry", {"m_GInfo": _ginfo(flags=573444),
                             "m_pFaces": [_face(i, mat) for i in range(nfaces)],
                             "m_flags": 7, "m_geometryTag": -1,
                             "m_tessEpsCntrl": {"m_type": 0, "m_TessEpsCntrlVersion": 1},
                             "m_pEdges": [_edge(i) for i in range(nedges)],
                             "m_sharedSurfInfo": []})


def _gline():
    return _ptr("GLine", {"m_GInfo": _ginfo(flags=17334276),
                          "m_endParams": [0.0, 5.0],
                          "m_origin": [0.0, 0.0, 0.0], "m_dirVec": [1.0, 0.0, 0.0]})


def _gelement(subnodes):
    return {"m_GInfo": _ginfo(tag=99),
            "m_subNodes": subnodes,
            "m_bBox": [[0.0, 0.0, 0.0], [10.0, 1.0, 12.0]],
            "m_tightbBox": [[0.0, 0.0, 0.0], [10.0, 1.0, 12.0]],
            "m_elementId": 99, "m_gElemType": 3, "m_flags": 0}


def _carriage(subnodes):
    c = RI._Carriage()
    RI._walk_gnode("GElement", _gelement(subnodes), c)
    return c


def test_classify_brep_wall_shape():
    """A native-wall-shaped tree: ref-plane GGroups + a main Geometry solid."""
    tree = [
        _ptr("GGroup", {"m_GInfo": _ginfo(tag=7, cat=24925),
                         "m_subNodes": [_geometry(nfaces=1, nedges=4)]}),
        _geometry(nfaces=8, nedges=30, mat=600660),
    ]
    c = _carriage(tree)
    assert c.solids == 2 and c.faces == 9 and c.edges == 34
    assert RI._classify("GElement", c) == "brep"
    assert c.surfaces["Plane"] == 9
    assert 600660 in c.styles


def test_classify_instance_ref_and_embedded_geom():
    inst = _ptr("GInstance", {"m_GInfo": _ginfo(),
                               "m_instanceInfo": _ptr("InstanceInfo", {}),
                               "m_oEmbeddedSymbolGRep": None,
                               "m_subNodes": []})
    c = _carriage([inst])
    assert RI._classify("GElement", c) == "instance-ref"
    # host-cut door/window: the GInstance embeds a per-host symbol-GRep clone
    inst2 = _ptr("GInstance", {"m_GInfo": _ginfo(),
                                "m_oEmbeddedSymbolGRep": _ptr(
                                    "GElement", _gelement([_geometry(4, 8)])),
                                "m_subNodes": []})
    c2 = _carriage([inst2])
    assert c2.instances == 1 and c2.faces == 4
    assert RI._classify("GElement", c2) == "instance-ref+geom"


def test_classify_curves_only_mesh_and_empty():
    c = _carriage([_gline(), _gline()])
    assert RI._classify("GElement", c) == "curves-only" and c.curves == 2
    mesh = _ptr("GPolyMesh", {"m_GInfo": _ginfo(), "m_subNodes": []})
    assert RI._classify("GElement", _carriage([mesh])) == "mesh"
    assert RI._classify("GElement", _carriage([])) == "empty-grep"
    # a bare Geometry node with NO faces is still "no drawable content"
    assert RI._classify("GElement", _carriage([_geometry(0, 0)])) == "empty-grep"


def test_classify_dummy_and_other_and_missing():
    c = RI._Carriage()
    assert RI._classify("SerializedDummy", c) == "dummy"
    assert RI._classify(None, c) == "no-record"
    assert RI._classify("GStyleElem", c) == "other:GStyleElem"


def test_gfilter_and_ggroup_descend():
    """Solids nested under GFilter (unconditional visibility) still count."""
    tree = [_ptr("GFilter", {"m_GInfo": _ginfo(), "m_oConditions": [],
                              "m_bIsNestedDetailFamily": False,
                              "m_subNodes": [_geometry(6, 12)]})]
    c = _carriage(tree)
    assert RI._classify("GElement", c) == "brep" and c.faces == 6


# ---------------------------------------------------------------------------
# corpus law (rstbasic)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def rst_doc():
    from rvt.mutate import Document
    return Document.load("rstbasicsampleproject")


@corpus
@skip_large
def test_every_native_wall_carries_a_baked_brep(rst_doc):
    rows = RI.inspect(rst_doc, classes=["SWall"])
    assert rows, "rstbasic has 9 walls"
    for r in rows:
        assert r.kind == "brep", f"wall {r.element_id} is {r.kind} (native walls are never dummy)"
        assert r.has_baked_geometry and r.drawable_3d
        assert r.n_solids >= 2 and r.n_faces >= 7
        assert r.geometry_bytes > 5000
        assert r.storage == RI.STORAGE_BREP
        assert r.gelem_type == 3
    # size grows with topological complexity (face count), monotone-ish here
    assert max(r.n_faces for r in rows) >= 11


@corpus
@skip_large
def test_datum_is_dummy_drawn_from_parameters(rst_doc):
    """Levels / Grids carry NO baked geometry -- they render from parameters."""
    rows = RI.inspect(rst_doc, classes=["Level", "Grid"])
    assert rows
    for r in rows:
        assert r.kind == "dummy", f"{r.klass} {r.element_id} should be dummy, got {r.kind}"
        assert not r.has_baked_geometry
        assert r.geometry_bytes == 2                 # bare class id
        assert r.storage == RI.STORAGE_DUMMY


@corpus
@skip_large
def test_family_symbol_carries_solid_and_instance_references_it(rst_doc):
    syms = RI.inspect(rst_doc, classes=["FamilySymbol"])
    breps = [s for s in syms if s.kind == "brep"]
    assert breps, "structural symbols carry baked family solids"
    insts = RI.inspect(rst_doc, classes=["FamilyInstance"])
    refs = [i for i in insts if i.by_reference]
    assert refs, "model instances reference their symbol"
    # a referencing instance resolves to a symbol row
    r0 = refs[0]
    assert r0.symbol_id and r0.has_baked_geometry
    sym = RI.resolve_instance_reference(rst_doc, r0)
    assert sym is not None and sym.element_id == r0.symbol_id


@corpus
@skip_large
def test_face_report_lists_the_wall_solid_planes(rst_doc):
    txt = RI.face_report(rst_doc, 493612)
    assert "solid #" in txt and "Plane" in txt and "material=" in txt
    # the main body solid: 8 faces incl. the finish material 600660
    assert "material=600660" in txt


@corpus
@skip_large
def test_summary_and_json_shape(rst_doc):
    rows = RI.inspect(rst_doc, classes=["SWall", "Level"])
    s = RI.summary(rows)
    assert s["elements"] == len(rows)
    assert s["kinds"]["brep"] == 9 and s["with_baked_geometry"] == 9
    j = RI.to_json_rows(rows)
    json.dumps(j)                                     # serialisable
    assert set(j) == {"summary", "rows"}
    txt = RI.render_report(rows)
    assert "baked=YES" in txt and "baked=no" in txt


# ---------------------------------------------------------------------------
# our created files: the LOAD-is-not-RENDER finding, byte-checked
# ---------------------------------------------------------------------------

@pytest.mark.slow
@skip_large
@pytest.mark.skipif(not os.path.exists(ROOM_UNJOINED), reason="ifc-room build absent")
def test_our_created_walls_are_dummy_no_baked_geometry():
    """The four walls we CREATED carry SerializedDummy reps -> invisible in
    the cloud viewer (the model tree showed only the level).  This is the
    root cause named in docs/writer/baked-geometry.md."""
    from rvt.mutate import Document
    doc = Document.from_file(ROOM_UNJOINED)
    walls = sorted(doc.ids_of_class("SWall", host_only=True))
    ours = [w for w in walls if w > 1470000]
    assert len(ours) == 4
    rows = [RI.inspect_element(doc, w) for w in ours]
    for r in rows:
        assert r.kind == "dummy" and not r.has_baked_geometry
        assert r.geometry_bytes == 2
    # yet their OBJECT machinery is a textbook six-face box awaiting a solid
    v = doc.value(ours[0], 102)
    steps = (v.get("m_geomSteps") or {}).get("value") or {}
    base = [s for s in (steps.get("m_bRepFormGList") or [])
            if s.get("ptr_class") == "BaseWallGStep"]
    assert base, "clone keeps its BaseWallGStep"
    fh = base[0]["value"].get("m_faceHistTable") or []
    eh = base[0]["value"].get("m_edgeHistTable") or []
    assert len(fh) == 6 and len(eh) == 12       # a box: 6 faces, 12 edges declared


@pytest.mark.slow
@skip_large
@pytest.mark.skipif(not os.path.exists(ROOM_FULL), reason="ifc-room build absent")
def test_our_symbols_carry_solids_and_instances_reference_them():
    """Our loaded families' SYMBOLS carry real 6-face solids and our placed
    INSTANCES reference them -- the instance layer is drawable BY REFERENCE."""
    from rvt.mutate import Document
    doc = Document.from_file(ROOM_FULL)
    syms = sorted(doc.ids_of_class("FamilySymbol", host_only=True))
    our_syms = [s for s in syms if s > 1470000]
    insts = sorted(doc.ids_of_class("FamilyInstance", host_only=True))
    our_insts = [i for i in insts if i > 1470000]
    assert len(our_syms) == 8 and len(our_insts) == 8
    for s in our_syms:
        r = RI.inspect_element(doc, s)
        assert r.kind == "brep" and r.n_faces == 6 and r.n_edges == 12
    ref_ids = set()
    for i in our_insts:
        r = RI.inspect_element(doc, i)
        assert r.kind == "instance-ref" and r.by_reference and r.symbol_id
        sym = RI.resolve_instance_reference(doc, r)
        assert sym is not None and sym.kind == "brep"
        ref_ids.add(sym.element_id)
    assert ref_ids <= set(our_syms)


# ---------------------------------------------------------------------------
# rvt.render.brep -- the wall solid CONSTRUCTOR (the render prescription)
# ---------------------------------------------------------------------------

def _face_planes(gelement):
    """{face_tag: (origin, outward_normal, material)} from a built GElement."""
    from rvt.render.brep import _unwrap
    out = {}
    geo = _unwrap(gelement["m_subNodes"][-1])
    for f in geo["m_pFaces"]:
        fv = _unwrap(f)
        sv = _unwrap(fv["m_pSurf"])
        x, y = sv["m_xVec"], sv["m_yVec"]
        nrm = [x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2],
               x[0] * y[1] - x[1] * y[0]]
        out[fv["m_GInfo"]["m_tag"]] = (sv["m_origin"], nrm, fv["m_renderStyleId"])
    return out, geo


def test_wall_solid_brep_shape_normals_and_materials():
    """A synthetic wall along +X: the box has 6 faces / 12 edges, each
    BaseWallGStep key lands on the geometrically CORRECT face (verified
    against a native wall's normals), and materials go to the right faces."""
    from rvt.render.brep import (WallGeometry, WallTags, wall_solid_brep,
                                 KEY_LEFT, KEY_RIGHT, KEY_START, KEY_FAR,
                                 KEY_BOTTOM, KEY_TOP)
    geom = WallGeometry(p0=[0.0, 0.0, 0.0], p1=[20.0, 0.0, 0.0], base_z=0.0,
                        height=10.0, off_left=0.5, off_right=-0.5)
    tags = WallTags.fresh(base=100)
    rep = wall_solid_brep(geom, tags, element_id=555, side_material_id=777,
                          end_material_id=888, root_category_id=30)
    assert rep["m_elementId"] == 555 and rep["m_gElemType"] == 3
    assert rep["m_GInfo"]["m_categoryId"] == 30 and rep["m_GInfo"]["m_tag"] == 555
    faces, geo = _face_planes(rep)
    assert len(geo["m_pFaces"]) == 6 and len(geo["m_pEdges"]) == 12
    # u = +X, n_left = +Y : LEFT normal +Y at y=+0.5; RIGHT normal -Y at y=-0.5
    o, n, mat = faces[tags.faces[KEY_LEFT]]
    assert [round(t, 6) for t in n] == [0.0, 1.0, 0.0] and abs(o[1] - 0.5) < 1e-9 and mat == 777
    o, n, mat = faces[tags.faces[KEY_RIGHT]]
    assert [round(t, 6) for t in n] == [0.0, -1.0, 0.0] and abs(o[1] + 0.5) < 1e-9 and mat == 777
    o, n, mat = faces[tags.faces[KEY_START]]
    assert [round(t, 6) for t in n] == [-1.0, 0.0, 0.0] and abs(o[0]) < 1e-9 and mat == 888
    o, n, mat = faces[tags.faces[KEY_FAR]]
    assert [round(t, 6) for t in n] == [1.0, 0.0, 0.0] and abs(o[0] - 20.0) < 1e-9 and mat == 888
    o, n, mat = faces[tags.faces[KEY_BOTTOM]]
    assert [round(t, 6) for t in n] == [0.0, 0.0, -1.0] and abs(o[2]) < 1e-9 and mat == 777
    o, n, mat = faces[tags.faces[KEY_TOP]]
    assert [round(t, 6) for t in n] == [0.0, 0.0, 1.0] and abs(o[2] - 10.0) < 1e-9 and mat == 777
    # bbox = the box
    assert rep["m_bBox"] == [[0.0, -0.5, 0.0], [20.0, 0.5, 10.0]]


@corpus
def test_wall_solid_encodes_and_redecodes_clean():
    """The authored rep serialises with rvt.encode and decodes back 100%
    (the same schema-directed codec that reads native walls)."""
    from rvt.render.brep import WallGeometry, WallTags, wall_solid_brep, CLASS_GELEMENT
    from rvt.encode import encode_record
    from rvt.objects import ObjectDecoder
    import struct
    geom = WallGeometry(p0=[5.0, 5.0, 0.0], p1=[5.0, 35.0, 0.0], base_z=-2.0,
                        height=12.0, off_left=0.45, off_right=-0.45)
    rep = wall_solid_brep(geom, WallTags.fresh(), element_id=12345,
                          side_material_id=600660, end_material_id=-1)
    framed = encode_record(103, 12345, None, CLASS_GELEMENT, rep)
    size = struct.unpack_from("<I", framed, 12)[0]
    pay = framed[16:16 + size]
    cls = struct.unpack_from("<H", pay, 0)[0]
    assert cls == CLASS_GELEMENT
    o = ObjectDecoder().decode_record(cls, pay[2:])
    assert o.clean and o.consumed == o.total and not o.errors
    c = RI._Carriage()
    RI._walk_gnode("GElement", o.value, c)
    assert RI._classify("GElement", c) == "brep"
    assert c.faces == 6 and c.edges == 12 and c.surfaces["Plane"] == 6
    assert 600660 in c.styles


@pytest.mark.slow
@skip_large
@pytest.mark.skipif(not os.path.exists(ROOM_UNJOINED), reason="ifc-room build absent")
def test_wall_rep_from_our_created_wall_object():
    """Read geometry + history tags off OUR created (dummy-rep) wall and
    build its solid: the box matches the wall's own line / thickness /
    height and reuses the six face tags + twelve edge tags its own
    BaseWallGStep declares (rep consistent with its history by construction)."""
    from rvt.mutate import Document
    from rvt.render.brep import (wall_rep_from_object, tags_from_wall_object,
                                 wall_geometry_from_object)
    doc = Document.from_file(ROOM_UNJOINED)
    ours = [w for w in sorted(doc.ids_of_class("SWall", host_only=True)) if w > 1470000]
    obj = doc.value(ours[0], 102)
    tags = tags_from_wall_object(obj)
    assert tags.source == "history" and tags.complete
    assert len(set(tags.faces.values())) == 6 and len(tags.edges) == 12
    geom = wall_geometry_from_object(obj)
    assert abs(geom.length - 30.1837) < 1e-3          # the 9.2 m room wall
    assert abs(geom.thickness - 0.9186) < 1e-3
    assert abs(geom.height - 12.0079) < 1e-3
    rep, g2, t2 = wall_rep_from_object(obj, element_id=ours[0],
                                       side_material_id=600660)
    c = RI._Carriage()
    RI._walk_gnode("GElement", rep, c)
    assert RI._classify("GElement", c) == "brep" and c.faces == 6 and c.edges == 12
    used = {(rep["m_subNodes"][-1]["value"]["m_pFaces"][i]["value"]["m_GInfo"]["m_tag"])
            for i in range(6)}
    assert used == set(tags.faces.values())        # our tags, no fresh allocation


def test_wall_rep_weakrefs_are_consistent_in_composed_tree():
    """GUARD (a bug the ref-plane variant once had): composing the four
    ref-plane sub-graphics with the main solid renumbers the archive pids,
    and every weak reference (Edge->Face, loop links, Face->EdgeLoop back
    links) MUST follow.  A dangling weakref = a malformed rep."""
    from rvt.render.brep import (WallGeometry, WallTags, wall_solid_brep,
                                 weakref_report)
    geom = WallGeometry(p0=[0.0, 0.0, 0.0], p1=[30.0, 0.0, 0.0], base_z=0.0,
                        height=12.0, off_left=0.46, off_right=-0.46)
    tags = WallTags.fresh()
    ref_planes = [
        {"origin": [0.0, off, 0.0], "xvec": [1.0, 0.0, 0.0],
         "yvec": [0.0, 0.0, 1.0], "u_len": 30.0, "v_len": 12.0}
        for off in (0.0, 0.46, -0.46, 0.0)
    ]
    solo = wall_solid_brep(geom, tags, element_id=9)
    both = wall_solid_brep(geom, tags, element_id=9, with_ref_planes=True,
                           refplane_gstyle_id=24925, ref_planes=ref_planes)
    r_solo, r_both = weakref_report(solo), weakref_report(both)
    assert r_solo["dangling"] == [] and r_solo["pids"] == 31 and r_solo["weakrefs"] == 90
    assert r_both["dangling"] == []
    assert r_both["pids"] > r_solo["pids"] and r_both["weakrefs"] > r_solo["weakrefs"]
    # the composed tree really did renumber: the main solid moved off pid 3
    assert both["m_subNodes"][-1]["pid"] > solo["m_subNodes"][-1]["pid"]

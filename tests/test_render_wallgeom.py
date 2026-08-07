"""Tests for rvt.render.wallgeom -- BAKED wall geometry (the RENDER track).

Evidence tiers:

1. GRAMMAR CONSTANTS: the BaseWallGStep box tag layout / face + edge
   serialization order / cycle wiring match the corpus (rst 493879 B=8,
   rst 1115258 + rme B=5, and famgen's family box).
2. NATIVE REPRODUCTION (the crown jewel): a native, Revit-saved wall's
   seq-103 GElement is rebuilt from that wall's OWN seq-102 object + type
   and matches the real record LEAF-FOR-LEAF (pids, weakrefs, frames, uv
   end points, per-key flags, GFilling placers, materials) modulo the
   garbage field Geometry.m_GInfo.m_controlCommand.  Two fixtures: a
   single-layer wall (rme 573386) and a two-layer wall whose compound keys
   29/30 are INTERIOR layer boundaries with per-side materials (rme
   575873).  Fixtures = decoded records of Autodesk 2026 sample walls saved
   by ``python -m rvt.render.wallgeom fixture`` (no corpus needed).
3. CONSTRUCTION AUDIT: a synthetic wall spec builds a rep that is
   pid-stable, weakref-consistent, closed-loop, uv/3D-consistent, and
   round-trips through rvt.encode -> rvt.objects byte-exact.
4. THE BAKE PATHS: the existing-file in-place bake on the LOAD-certified
   walls-only file yields a validator-VALID file whose four walls read
   back as clean baked GElements (and rvt.render.inspect agrees).
"""
from __future__ import annotations

import json
import os

import pytest

from rvt.render import wallgeom as W

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIX_DIR = os.path.join(ROOT, "experiments", "ifc_room", "render", "fixtures")
FIX_SINGLE = os.path.join(FIX_DIR, "native_wall_rmebasicsampleproject_573386.json")
FIX_MULTI = os.path.join(FIX_DIR, "native_wall_rmebasicsampleproject_575873.json")
WALLS_UNJOINED = os.path.join(ROOT, "experiments", "ifc_room",
                              "electrical_room_2500a_walls_only_unjoined.rvt")
RENDER_DIR = os.path.join(ROOT, "experiments", "ifc_room", "render")

HAVE_SINGLE = os.path.exists(FIX_SINGLE)
HAVE_MULTI = os.path.exists(FIX_MULTI)


# ---------------------------------------------------------------------------
# 1. grammar constants
# ---------------------------------------------------------------------------

def test_box_face_key_order_is_ascending_tag_order():
    # native face list order = ascending tag: cap2, cap1, bottom, finish, top, start
    assert W.BOX_FACE_KEY_ORDER == [(2, -1), (1, -1), (3, 2), (3, 1), (3, 3), (3, 0)]
    offs = [W.BOX_FACE_TAG_OFFSET[k] for k in W.BOX_FACE_KEY_ORDER]
    assert offs == sorted(offs) == [0, 1, 2, 5, 9, 13]


def test_box_edge_key_order_matches_the_corpus():
    # rme 573386 (B=5) edge list, ascending tag: rails/laterals interleaved
    keys = W.BOX_EDGE_KEY_ORDER
    assert keys == [(1, 2, 0), (1, 2, 1), (1, 1, 0), (1, 1, 1), (2, 2, 1),
                    (1, 3, 0), (1, 3, 1), (2, 1, 3), (1, 0, 0), (1, 0, 1),
                    (2, 3, 0), (2, 0, 2)]
    offs = [W.BOX_EDGE_TAG_OFFSET[k] for k in keys]
    assert offs == [3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16, 17]


def test_canonical_tags_reproduce_the_native_layouts():
    # B=5 (rst 1115258 / every rme wall) and B=8 (rst 493879)
    f5, e5 = W.canonical_box_tags(5)
    assert sorted(f5.values()) == [5, 6, 7, 10, 14, 18]
    assert sorted(e5.values()) == [8, 9, 11, 12, 13, 15, 16, 17, 19, 20, 21, 22]
    f8, e8 = W.canonical_box_tags(8)
    assert sorted(f8.values()) == [8, 9, 10, 13, 17, 21]
    assert sorted(e8.values()) == [11, 12, 14, 15, 16, 18, 19, 20, 22, 23, 24, 25]


def test_cycle_wiring_matches_famgen_box_template():
    loops = W._loop_orders()
    # cap2 = the cycle rails on side 0; cap1 = the reversed cycle on side 1
    assert loops[W.FACEKEY_CAP2] == [(1, k, 0) for k in W.CYCLE]
    assert loops[W.FACEKEY_CAP1] == [(1, k, 1) for k in reversed(W.CYCLE)]
    # side loop = [rail on cap2, lateral(start vertex), rail on cap1, lateral(end vertex)]
    assert loops[W.FACEKEY_BOTTOM] == [(1, 2, 0), (2, 0, 2), (1, 2, 1), (2, 2, 1)]
    assert loops[W.FACEKEY_FINISH] == [(1, 1, 0), (2, 2, 1), (1, 1, 1), (2, 1, 3)]
    assert loops[W.FACEKEY_TOP] == [(1, 3, 0), (2, 1, 3), (1, 3, 1), (2, 3, 0)]
    assert loops[W.FACEKEY_START] == [(1, 0, 0), (2, 3, 0), (1, 0, 1), (2, 0, 2)]


# ---------------------------------------------------------------------------
# 2. native reproduction (fixtures)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not HAVE_SINGLE, reason="single-layer fixture absent")
def test_reproduce_native_single_layer_wall_exactly():
    doc, wid, native = W.load_fixture_doc(FIX_SINGLE)
    r = W.reproduce_native_wall(doc, wid, native_rep=native)
    assert r["diff"] == [], f"leaf diffs vs the native rep: {r['diff'][:8]}"
    assert r["audit"] == [], f"self-audit: {r['audit'][:5]}"
    s = r["summary"]
    assert (s["ggroups"], s["solids"], s["solid_faces"], s["solid_edges"]) == (4, 1, 6, 12)
    assert s["root_category"] == 30 and s["element_id"] == wid


@pytest.mark.skipif(not HAVE_MULTI, reason="multi-layer fixture absent")
def test_reproduce_native_multilayer_wall_exactly():
    """The two-layer wall: compound keys 29/30 are INTERIOR layer
    boundaries; the exterior faces come from the grid's outer segments and
    the two caps carry different layer materials."""
    doc, wid, native = W.load_fixture_doc(FIX_MULTI)
    r = W.reproduce_native_wall(doc, wid, native_rep=native)
    assert r["diff"] == [], f"leaf diffs vs the native rep: {r['diff'][:8]}"
    assert r["audit"] == []
    spec = r["spec"]
    # thickness = the FULL two-layer width (1.2139 ft), not |off29-off30| (0.82)
    assert abs(spec.thickness - 1.2139) < 1e-3
    # per-side materials differ from the thin-face material
    assert spec.material_cap2 not in (None, spec.material_id) or \
           spec.material_cap1 not in (None, spec.material_id)


@pytest.mark.skipif(not HAVE_MULTI, reason="multi-layer fixture absent")
def test_multilayer_materials_derived_from_the_type_not_read():
    """The DERIVATION path (compound structure grid + segRefFaceKeys)
    reaches the same rep: run wall_render_spec through the doc facade with
    only the root category / ref-plane material overridden (facts a
    fixture cannot supply), then patch the native's fill category and
    compare -- the geometry, tags and MATERIALS must all be derived."""
    doc, wid, native = W.load_fixture_doc(FIX_MULTI)
    spec = W.wall_render_spec(doc, wid, root_category_id=30, refplane_material_id=24)
    # derivation notes name the interior-boundary case
    assert any("interior layer boundaries" in n for n in spec.notes), spec.notes
    assert spec.material_cap2 is not None and spec.material_cap1 is not None
    assert spec.material_cap2 != spec.material_cap1
    # the fixture facade has no GStyle catalogue: take those two ids off
    # the native (they are catalogue facts, not construction)
    nodes = native["m_subNodes"]
    for n in nodes:
        if n.get("ptr_class") == "GGroup":
            spec.refplane_category_id = n["value"]["m_GInfo"]["m_categoryId"]
            break
    for n in nodes:
        if n.get("ptr_class") == "Geometry":
            f0 = n["value"]["m_pFaces"][0]["value"]
            spec.fill_category_id = f0["m_pGFilling"]["value"]["m_GInfo"]["m_categoryId"]
            break
    ours = W.build_wall_gelement(spec)
    d = W.diff_reps(ours, native)
    assert d == [], f"derived rep differs from the native: {d[:8]}"


# ---------------------------------------------------------------------------
# 3. synthetic construction + encode/decode round trip
# ---------------------------------------------------------------------------

def _synthetic_spec(**over) -> W.WallRenderSpec:
    faces, edges = W.canonical_box_tags(5)
    ref_planes = []
    length, height = 20.0, 12.007874015748031
    off = {29: -0.4593, 30: 0.4593, 39: 0.0, 40: 0.0}
    for i, (key, tag) in enumerate(((40, 1), (29, 2), (30, 3), (39, 4))):
        ref_planes.append(W.RefPlane(key=key, tag=tag,
                                     origin=[0.0, off[key], 0.0],
                                     xvec=[1.0, 0.0, 0.0], yvec=[0.0, 0.0, 1.0],
                                     envelope=[[0.0, 0.0], [length, height]]))
    kw = dict(elem_id=1_500_001, origin=[0.0, 0.0, 0.0], direction=[1.0, 0.0, 0.0],
              t0=0.0, t1=length, base_z=0.0, height=height,
              off_min=-0.4593, off_max=0.4593, ref_planes=ref_planes,
              face_tags=faces, edge_tags=edges, material_id=600660,
              root_category_id=30, refplane_category_id=24925,
              refplane_material_id=-1, fill_category_id=32)
    kw.update(over)
    return W.WallRenderSpec(**kw)


def test_constructed_rep_passes_the_audit_and_is_pid_stable():
    spec = _synthetic_spec()
    rep = W.build_wall_gelement(spec)
    assert W.audit_wall_rep(rep, spec=spec) == []
    s = W.rep_summary(rep)
    assert (s["ggroups"], s["solids"], s["solid_faces"], s["solid_edges"]) == (4, 1, 6, 12)
    assert s["materials"] == [600660]
    # bbox = the exact solid AABB
    bb = rep["m_bBox"]
    assert bb[0][:2] == [0.0, -0.4593] and bb[1][:2] == [20.0, 0.4593]
    assert abs(bb[1][2] - 12.007874015748031) < 1e-9
    # native pid layout: root subnodes 3..7, group geometries 8..11
    pids = [n["pid"] for n in rep["m_subNodes"]]
    assert pids == [3, 4, 5, 6, 7]
    inner = [n["value"]["m_subNodes"][0]["pid"] for n in rep["m_subNodes"]
             if n["ptr_class"] == "GGroup"]
    assert inner == [8, 9, 10, 11]
    solid = next(n for n in rep["m_subNodes"] if n["ptr_class"] == "Geometry")
    fpids = [f["pid"] for f in solid["value"]["m_pFaces"]]
    epids = [e["pid"] for e in solid["value"]["m_pEdges"]]
    assert fpids == list(range(12, 18)) and epids == list(range(18, 30))


def test_constructed_rep_encodes_and_decodes_byte_exact():
    """The rep survives rvt.encode -> rvt.objects: the seq-103 record we
    write is exactly what the decoder reads back (and re-encodes)."""
    from rvt.encode import encode_record
    from rvt.objects import ObjectDecoder
    import struct
    spec = _synthetic_spec()
    rep = W.build_wall_gelement(spec)
    framed = encode_record(103, spec.elem_id, None, W.CLASS_GELEMENT, rep)
    # header: i64 id, u32 stamp, u32 psize; payload = u16 class + object
    eid, stamp, psize = struct.unpack_from("<qII", framed, 0)
    assert eid == spec.elem_id
    payload = framed[16:16 + psize]
    cls = struct.unpack_from("<H", payload, 0)[0]
    assert cls == W.CLASS_GELEMENT
    dec = ObjectDecoder().decode_record(cls, payload[2:])
    assert dec.clean, dec.errors
    assert dec.value == rep, W.diff_reps(dec.value, rep)[:5]
    # and re-encoding the decoded value reproduces the bytes
    assert encode_record(103, spec.elem_id, None, cls, dec.value) == framed


def test_off_centre_orientation_is_min_max_not_key_29_30():
    """CAP2 (key [2]) is the MIN-offset side even when the key-29 plane is
    on the max side (rme 573735 / 575873): swapping the key planes' sides
    must not change the box."""
    a = _synthetic_spec()
    ref_swapped = []
    for rp in a.ref_planes:
        o = list(rp.origin)
        if rp.key in (29, 30):
            o[1] = -o[1]                       # swap sides
        ref_swapped.append(W.RefPlane(key=rp.key, tag=rp.tag, origin=o,
                                       xvec=rp.xvec, yvec=rp.yvec, envelope=rp.envelope))
    b = _synthetic_spec(ref_planes=ref_swapped)
    ra, rb = W.build_wall_gelement(a), W.build_wall_gelement(b)
    sa = next(n for n in ra["m_subNodes"] if n["ptr_class"] == "Geometry")
    sb = next(n for n in rb["m_subNodes"] if n["ptr_class"] == "Geometry")
    # identical solids (only the ref-plane sub-graphics moved)
    assert W.diff_reps(sa["value"], sb["value"]) == []


def test_fill_placer_rule_projects_the_start_anchor():
    """GFilling placer origin = the location line START base point in each
    face's uv; direction = Z x n_out for vertical faces, the wall direction
    for horizontal faces [V native]."""
    spec = _synthetic_spec(t0=-0.5, t1=20.0)      # anchor at t0 = -0.5
    rep = W.build_wall_gelement(spec)
    solid = next(n for n in rep["m_subNodes"] if n["ptr_class"] == "Geometry")
    faces = {f["value"]["m_GInfo"]["m_tag"]: f["value"] for f in solid["value"]["m_pFaces"]}
    cap2 = faces[spec.face_tags[W.FACEKEY_CAP2]]
    pl = cap2["m_pGFilling"]["value"]["m_placer"]
    assert abs(pl["m_origin"][0] - (-0.5)) < 1e-9 and abs(pl["m_origin"][1]) < 1e-9
    assert pl["m_dir"] == [1.0, 0.0]              # +u = wall direction on cap2
    bottom = faces[spec.face_tags[W.FACEKEY_BOTTOM]]
    plb = bottom["m_pGFilling"]["value"]["m_placer"]
    # bottom frame: u across thickness (anchor at the line = +0.4593 from the min side),
    # v along the wall from the start point; dir = the wall direction = +v
    assert abs(plb["m_origin"][0] - 0.4593) < 1e-9 and abs(plb["m_origin"][1]) < 1e-9
    assert plb["m_dir"] == [0.0, 1.0]
    # every solid face carries a GFilling of the fill category, no pattern
    for fv in faces.values():
        fl = fv["m_pGFilling"]["value"]
        assert fl["m_GInfo"]["m_categoryId"] == 32
        assert fl["m_patternId"] == -1 and fl["m_flags"] == W.GFILLING_FLAGS_NOPATTERN
        assert fl["m_fillColor"] == W.GFILLING_COLOR_NONE


def test_wall_render_error_for_arc_walls():
    obj = {"m_pCurveDriver": {"ptr_class": "VWallDriver", "value": {
        "m_pCrv": {"ptr_class": "GArc", "value": {}}}}}
    with pytest.raises(W.WallRenderError):
        W.location_line(obj)


# ---------------------------------------------------------------------------
# 4. the bake paths
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not os.path.exists(WALLS_UNJOINED), reason="walls-only file absent")
def test_created_walls_spec_out_on_the_genesis_base():
    """Our clones on ZA_deep: single-layer CL_W1 (280 mm), material
    600660, ref-plane GStyle 24925, fill GStyle 32, no surface pattern,
    history tags B=5 -- and the missing-Walls-GStyle warning surfaces."""
    from rvt.mutate import Document
    doc = Document.from_file(WALLS_UNJOINED)
    walls = doc.ids_of_class("SWall", host_only=True)
    assert len(walls) == 4
    spec = W.wall_render_spec(doc, walls[0])
    assert spec.material_id == 600660
    assert spec.material_cap2 is None and spec.material_cap1 is None
    assert spec.refplane_category_id == 24925 and spec.fill_category_id == 32
    assert spec.pattern_id == -1
    assert spec.tag_source == "history" and spec.base_tag == 5
    assert abs(spec.thickness - 0.9186351706036745) < 1e-9
    assert spec.root_category_id == -1
    assert any("Walls-category" in w for w in spec.warnings), spec.warnings
    rep = W.build_wall_gelement(spec)
    assert W.audit_wall_rep(rep, spec=spec) == []


@pytest.mark.skipif(not os.path.exists(WALLS_UNJOINED), reason="walls-only file absent")
@pytest.mark.skipif(os.environ.get("RVT_SKIP_LARGE") == "1", reason="RVT_SKIP_LARGE=1")
def test_bake_wall_geometry_inplace_yields_valid_baked_file(tmp_path):
    """Existing-file bake (rvt.regadd.substitute_elements in place): the
    LOAD-certified walls-only file's four SerializedDummy reps become
    audit-clean GElements; the file stays validator-VALID."""
    from rvt.validate import validate_file
    out = str(tmp_path / "baked.rvt")
    rep = W.bake_wall_geometry(WALLS_UNJOINED, out, None, root_category_id=30)
    assert len(rep["walls"]) == 4
    sub = rep["substitute"]
    assert isinstance(sub, dict) and sub.get("verdict") == "VALID", str(sub)[:400]
    v = validate_file(out)
    assert v.ok, [f.to_json() for f in v.errors[:3]]
    rb = W.render_readback(out)
    assert rb["all_baked"] is True, json.dumps(rb, default=str)[:600]
    for w in rb["walls"]:
        assert w["rep_class"] == "GElement" and w["audit"] == []
        insp = w.get("inspect") or {}
        if insp and "error" not in insp:            # the archaeology stream's lens agrees
            assert insp.get("has_baked_geometry") is True and insp.get("kind") == "brep"


@pytest.mark.skipif(not os.path.isdir(RENDER_DIR), reason="render probes not built")
def test_render_probes_manifest_is_consistent():
    """probes.json (when built) names existing files with matching md5s and
    every ZA_deep probe declares the certified base."""
    manifest = os.path.join(RENDER_DIR, "probes.json")
    if not os.path.exists(manifest):
        pytest.skip("probes.json not built")
    with open(manifest) as fh:
        m = json.load(fh)
    assert m["base"]["file"].endswith("ZA_deep.rvt")
    import hashlib
    for p in m["probes"]:
        path = os.path.join(ROOT, p["file"])
        assert os.path.exists(path), p["file"]
        h = hashlib.md5(open(path, "rb").read()).hexdigest()
        assert h == p["md5"], f"{p['file']} md5 drift (rebuilt after the manifest?)"
        assert p.get("validator") in ("VALID", None)

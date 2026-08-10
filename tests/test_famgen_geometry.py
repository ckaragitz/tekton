"""Tests for rvt.famgen.geometry -- parametric family FORM generators.

Facts under test (docs/writer/family-geometry.md):

  * a rectangular extrusion's cached B-rep is a FIXED topology template
    (2 caps + n side faces, 3n edges, EdgeLoop/Plane per face, a fixed
    archive pid layout Geometry=3 / faces 4.. / edges .. / loop+surface
    pairs), fully reproducible from the profile's 4 vertices + 2 offsets;
  * both Autodesk box specimens (rme panelboard family, save unit 243,
    extrusions 786837 / 786867) are rebuilt from their dimensions:
    structurally exact (modulo the volatile GInfo bit 0x200 that differs
    between the two specimens themselves) and canonically byte-exact
    (floats snapped at 1e-9: the specimens carry ~1e-15 transform noise);
  * the archive object-index numbering (pids) is reproduced by
    ``assign_pids`` over every clean record of the sample .rfa;
  * every generated record round-trips through rvt.encode/rvt.objects;
  * a generated box splices into the sample .rfa (records + ElemTable +
    partition header) and reads back CRC/ECC/decode clean with the
    donor's ids preserved.

Run: .venv/bin/python -m pytest tests/test_famgen_geometry.py -q
"""
import copy
import os

import pytest

# element bundles round-trip against the schema alone; ``ctx`` falls back to
# the from-scratch FamilyDocContext defaults when the sample .rfa is absent
from conftest import needs_schema
from rvt.famgen import geometry as G

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RFA_2026 = G.SAMPLE_RFA
RME = os.path.join(ROOT, "samples", "rmebasicsampleproject.rvt")

needs_rfa = pytest.mark.skipif(not os.path.exists(RFA_2026), reason="rfa sample missing")
needs_rme = pytest.mark.skipif(not os.path.exists(RME), reason="rme sample missing")


class _Ids:
    def __init__(self, start=500_000):
        self.n = start

    def next(self):
        v = self.n
        self.n += 1
        return v


@pytest.fixture(scope="module")
def ctx():
    if os.path.exists(RFA_2026):
        return G.context_from_rfa(RFA_2026)
    return G.FamilyDocContext()


# ---------------------------------------------------------------------------
# profiles / tags / pids
# ---------------------------------------------------------------------------

def test_rect_profile_is_ccw_and_ordered():
    p = G.rect_profile(2.0, 1.0)
    assert G.polygon_area_xy(p.vertices) > 0                 # counter-clockwise
    assert p.vertices[0] == [1.0, 0.5, 0.0]                  # +x/+y corner first
    assert p.vertices[1] == [-1.0, 0.5, 0.0]                 # curve 0 runs -x (top edge)
    assert abs(p.width - 2.0) < 1e-12 and abs(p.depth - 1.0) < 1e-12
    with pytest.raises(ValueError):
        G.profile_from_vertices(list(reversed(p.vertices)))  # CW rejected


def test_box_tag_allocation_matches_specimen():
    t = G._box_tags(4)
    assert t["count"] == 18                       # 6 faces + 12 edges
    assert t["end_face"] == 0 and t["start_face"] == 1
    assert t["face"] == [2, 5, 9, 13]              # side-face tags
    assert t["rail_start"] == [3, 6, 10, 14]
    assert t["rail_end"] == [4, 7, 11, 15]
    assert t["lateral"] == [8, 12, 16, 17]         # V1, V2, V3 laterals + closing (V0)
    # the two-arc circle template (614's per-loop pattern) has 10 tags
    assert G._box_tags(2)["count"] == 10


@needs_rfa
def test_assign_pids_reproduces_every_donor_record():
    from rvt.families import FamilyIndex
    idx = FamilyIndex(RFA_2026)

    def pids(v, out):
        if isinstance(v, dict):
            if "ptr_class" in v:
                out.append((v["ptr_class"], v.get("pid", -1)))
                pids(v.get("value"), out)
            else:
                for x in v.values():
                    pids(x, out)
        elif isinstance(v, list):
            for x in v:
                pids(x, out)

    checked = mismatched = 0
    for seq in (102, 103):
        for eid in list(idx.unit_records(0)[seq])[:1200]:
            o = idx.decode(0, eid, seq)
            if not (o and o.clean):
                continue
            orig, new = [], []
            pids(o.value, orig)
            v2 = copy.deepcopy(o.value)
            G.assign_pids(v2)
            pids(v2, new)
            checked += 1
            mismatched += (orig != new)
    assert checked > 1000
    assert mismatched == 0


# ---------------------------------------------------------------------------
# the B-rep
# ---------------------------------------------------------------------------

def test_solid_box_brep_structure():
    prof = G.rect_profile(8.0, 10.75, center=(0.0, -1.375))
    s = G.solid_box_brep(prof, 0.0, -1.0, element_id=42, geometry_style_id=124)
    assert s["m_gElemType"] == 3 and s["m_elementId"] == 42
    geo = s["m_subNodes"][0]
    assert geo["ptr_class"] == "Geometry" and geo["pid"] == 3
    faces = geo["value"]["m_pFaces"]
    edges = geo["value"]["m_pEdges"]
    assert [f["pid"] for f in faces] == list(range(4, 10))
    assert [e["pid"] for e in edges] == list(range(10, 22))
    assert [f["value"]["m_GInfo"]["m_tag"] for f in faces] == [1, 0, 2, 5, 9, 13]
    assert [e["value"]["m_GInfo"]["m_tag"] for e in edges] == \
        [3, 4, 6, 7, 8, 10, 11, 12, 14, 15, 16, 17]
    # loop + surface pids interleave after the edges
    assert [f["value"]["m_pFirstLoop"]["pid"] for f in faces] == [22, 24, 26, 28, 30, 32]
    assert [f["value"]["m_pSurf"]["pid"] for f in faces] == [23, 25, 27, 29, 31, 33]
    # every edge sits between two DIFFERENT existing faces (weakref closure)
    fpids = {f["pid"] for f in faces}
    for e in edges:
        a, b = (w["weakref"] for w in e["value"]["m_pFace"])
        assert a in fpids and b in fpids and a != b
    # loop chains close: each face's loop references its first/last edge
    epids = {e["pid"] for e in edges}
    for f in faces:
        lp = f["value"]["m_pFirstLoop"]["value"]
        assert lp["m_next"]["weakref"] in epids and lp["m_prev"]["weakref"] in epids
    # lateral flags per the min-tag rule
    flags = {e["value"]["m_GInfo"]["m_tag"]: e["value"]["m_flags"] for e in edges}
    assert flags[8] == flags[12] == flags[16] == 7 and flags[17] == 6
    # the archive numbering agrees with the constructor's layout
    G._assert_pid_stable(s)


def test_solid_requires_ccw_and_downward():
    prof = G.rect_profile(1.0, 1.0)
    with pytest.raises(ValueError):
        G.solid_box_brep(prof, 0.0, 1.0, element_id=1)      # end > start
    # a pre-built profile must already be CCW -- the caller asserted an order
    with pytest.raises(ValueError):
        G.solid_box_brep(G.RectProfile([[1, 1, 0], [1, -1, 0], [-1, -1, 0],
                                        [-1, 1, 0]]), 1.0, 0.0, element_id=1)
    # a RAW vertex ring is normalised instead (an IFC profile's winding
    # follows its own axis convention), so clockwise input builds fine...
    cw = G.solid_box_brep([[1, 1], [1, -1], [-1, -1], [-1, 1]], 1.0, 0.0,
                          element_id=1)
    assert cw["m_subNodes"][0]["value"]["m_pFaces"]
    # ...but a degenerate ring still cannot be a prism
    with pytest.raises(ValueError):
        G.solid_box_brep([[0, 0], [1, 0]], 1.0, 0.0, element_id=1)
    with pytest.raises(ValueError):                       # collinear
        G.solid_box_brep([[0, 0], [1, 0], [2, 0]], 1.0, 0.0, element_id=1)


@pytest.mark.parametrize("n", [3, 5, 6, 12])
def test_ngon_prism_solid_is_cached(n):
    """THE N-GON PRISM (owner probe: a form shipped with the SerializedDummy
    'regeneration' rep draws NOTHING in Revit, so every form needs a real
    cached solid).  An N-gon prism is the box topology with N sides."""
    import math
    ring = [[math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)]
            for k in range(n)]
    g = G.solid_box_brep(ring, 1.0, 0.0, element_id=1)
    geom = g["m_subNodes"][0]["value"]
    assert len(geom["m_pFaces"]) == n + 2, n        # 2 caps + N sides
    assert len(geom["m_pEdges"]) == 3 * n, n        # N rails x2 + N laterals
    # a concave ring is a prism too -- the topology does not care
    L = [[0, 0], [1.5, 0], [1.5, .4], [.4, .4], [.4, 1.2], [0, 1.2]]
    gl = G.solid_box_brep(L, 1.0, 0.0, element_id=1)["m_subNodes"][0]["value"]
    assert len(gl["m_pFaces"]) == 8 and len(gl["m_pEdges"]) == 18


@needs_rme
@pytest.mark.parametrize("eid,strict", [(786867, True), (786837, False)])
def test_specimen_box_topology_reproduced_from_dimensions(eid, strict):
    """THE topology proof: rebuild a real Autodesk box solid from JUST its
    6 dimensions and compare against the specimen's decoded GElement."""
    r = G.reproduce_specimen_solid("rmebasicsampleproject", 243, eid)
    assert r["n_leaves"] > 500
    assert r["structurally_exact_modulo_volatile_bit"], r["structural_mismatches"][:8]
    if strict:
        assert r["structurally_exact"]
    else:
        # 786837's only mismatches are the volatile GInfo bit 0x200
        assert G._volatile_only(r["structural_mismatches"])
    assert r["max_float_dev"] < 1e-12                       # transform noise only
    assert r["canonical_byte_exact"]                        # identical bytes @1e-9
    assert r["canonical_bytes_ours"] == r["canonical_bytes_specimen"] == r["raw_len_specimen"]


# ---------------------------------------------------------------------------
# element bundles
# ---------------------------------------------------------------------------

@needs_schema
@pytest.mark.parametrize("rep", [G.REP_SOLID, G.REP_DUMMY])
def test_box_bundle_schema_roundtrip(ctx, rep):
    fb = G.box(G.mm(500), G.mm(300), G.mm(700), ctx, _Ids(), rep=rep)
    assert [e.class_name for e in fb.elements] == \
        ["SketchPlane", "VarSketch", "CurveElem", "CurveElem", "CurveElem",
         "CurveElem", "ExtrusionElem"]
    rt = fb.roundtrip()
    assert rt["ok"], [(k, v) for k, v in rt["elements"].items() if not v["ok"]]
    ex = fb.by_class("ExtrusionElem")[0]
    assert (ex.rep is not None) == (rep == G.REP_SOLID)
    # extrusion offsets are ordered by ELEVATION, not by the tracer's
    # direction: Revit reads -1001800 as "Extrusion Start" and shows
    # Depth = End - Start, so the box path's traced start (its TOP) belongs
    # in END or every box reports a negative depth in the properties palette
    ps = {p["m_paramId"]: p["m_value"]
          for p in ex.obj["m_pParamValueSetDouble"]["value"]["m_paramSet"]}
    assert ps[G.BIP_EXTRUSION_START] == 0.0
    assert abs(ps[G.BIP_EXTRUSION_END] - G.mm(700)) < 1e-12
    # the sketch feeds the extrusion; the extrusion's helper points at the sketch
    sk = fb.by_class("VarSketch")[0]
    assert sk.obj["m_userId"] == ex.elem_id
    assert ex.obj["m_cellList"]["value"]["m_cells"][0]["value"]["m_sketchId"] == sk.elem_id
    # 4 curve elems joined head-to-tail in a cycle
    curves = fb.by_class("CurveElem")
    ids = [c.elem_id for c in curves]
    for i, c in enumerate(curves):
        joins = c.obj["m_pCurveDriver"]["value"]["m_controlJoinsSet"]
        others = {j["m_JoinInfo"]["m_info"][1]["m_elemId"] for j in joins}
        assert others == {ids[i - 1], ids[(i + 1) % 4]}
    # sketch plane sits on the family's reference level
    sp = fb.by_class("SketchPlane")[0]
    assert sp.obj["m_oPlaneRef"]["value"]["m_datumPlaneId"] == ctx.level_id


@needs_schema
def test_plate_and_polygonal_cylinder_roundtrip(ctx):
    for fb in (G.plate(G.mm(400), G.mm(600), G.mm(3), ctx, _Ids()),
               G.polygon_cylinder(G.mm(75), G.mm(150), ctx, _Ids())):
        rt = fb.roundtrip()
        assert rt["ok"], fb.kind


# ---------------------------------------------------------------------------
# cylinders (arc profile + CylSurf B-rep) -- docs sec. 4
# ---------------------------------------------------------------------------

def test_circle_loop_tags_and_gstep():
    t = G._circle_loop_tags(2)                     # clean single-circle history
    assert t == {"side_L": 2, "rail_top_L": 3, "rail_bot_L": 4, "side_U": 5,
                 "rail_top_U": 6, "rail_bot_U": 7, "lat_v1": 8, "lat_v0": 9}
    assert G._circle_loop_tags(114)["lat_v0"] == 121      # specimen leg 1 block
    st = G.extrusion_gstep_circles(1)
    fh = {tuple(x["m_faceHist"]["m_keys"]): x["m_id"] for x in st["m_faceHistTable"]}
    eh = {tuple(x["m_edgeHist"]["m_keys"]): x["m_id"] for x in st["m_edgeHistTable"]}
    assert fh[(1, -1, -1)] == 1 and fh[(2, -1, -1)] == 0     # start cap 1, end cap 0
    assert fh[(3, 1, -1)] == 2 and fh[(3, 0, -1)] == 5     # side of L (curve 1) / U (curve 0)
    assert eh[(1, 1, 0, -1)] == 3 and eh[(1, 0, 1, -1)] == 7
    assert eh[(2, 1, 0, -1)] == 8 and eh[(2, 0, 1, -1)] == 9  # V1 lateral / closing


@needs_schema
def test_solid_cylinder_brep_structure(ctx):
    c = G.circle_profile((1.0, 2.0), 0.25)
    s = G.solid_cylinder_brep([c], 0.0, 1.5, element_id=99, geometry_style_id=4087)
    geo = s["m_subNodes"][0]
    assert geo["ptr_class"] == "Geometry" and geo["pid"] == 3
    faces = geo["value"]["m_pFaces"]
    edges = geo["value"]["m_pEdges"]
    assert [f["pid"] for f in faces] == [4, 5, 6, 7]
    assert [e["pid"] for e in edges] == [8, 9, 10, 11, 12, 13]
    # top (end) cap tag 0 first, bottom (start) cap tag 1, then L (2) and U (5)
    assert [f["value"]["m_GInfo"]["m_tag"] for f in faces] == [0, 1, 2, 5]
    assert [e["value"]["m_GInfo"]["m_tag"] for e in edges] == [3, 4, 6, 7, 8, 9]
    surfs = [f["value"]["m_pSurf"] for f in faces]
    assert [x["ptr_class"] for x in surfs] == ["Plane", "Plane", "CylSurf", "CylSurf"]
    assert [x["pid"] for x in surfs] == [15, 17, -1, -1]          # CylSurf unregistered
    assert [f["value"]["m_pFirstLoop"]["pid"] for f in faces] == [14, 16, 18, 19]
    import math
    envL = surfs[2]["value"]["m_Envelope"]["m_corners"]
    envU = surfs[3]["value"]["m_Envelope"]["m_corners"]
    assert abs(envL[0][0] - math.pi) < 1e-12 and abs(envL[1][0] - 2 * math.pi) < 1e-12
    assert envU[0][0] == 0.0 and abs(envU[1][0] - math.pi) < 1e-12
    assert abs(envL[1][1] - 1.5) < 1e-12                          # v range = extrusion length
    assert surfs[2]["value"]["m_radius"] == 0.25
    assert surfs[2]["value"]["m_center"] == [1.0, 2.0, 0.0]     # axis base at the start plane
    # curved rails: 6 interior points on the L half, 5 on the U half; seams straight
    n_int = [len(e["value"]["m_interiorEdgePnts"]) for e in edges]
    assert n_int == [6, 6, 5, 5, 0, 0]
    flags = [e["value"]["m_flags"] for e in edges]
    assert flags == [14, 14, 14, 14, 6, 6]
    ginfl = [e["value"]["m_GInfo"]["m_flags"] for e in edges]
    assert ginfl == [G.EDGE_INFO_FLAGS] * 4 + [G.EDGE_SEAM_INFO_FLAGS] * 2
    # every edge sits between two DIFFERENT faces; loops reference edges
    fpids = {f["pid"] for f in faces}
    epids = {e["pid"] for e in edges}
    for e in edges:
        a, b = (w["weakref"] for w in e["value"]["m_pFace"])
        assert a in fpids and b in fpids and a != b
    for f in faces:
        lp = f["value"]["m_pFirstLoop"]["value"]
        assert lp["m_next"]["weakref"] in epids and lp["m_prev"]["weakref"] in epids
        assert lp["m_pFace"]["weakref"] == f["pid"]
    # curved geometry / bbox from the tessellation nodes / geometry flags
    assert geo["value"]["m_flags"] == G.GEOMETRY_FLAGS_CURVED
    bb = s["m_bBox"]
    assert abs(bb[0][2] - 0.0) < 1e-12 and abs(bb[1][2] - 1.5) < 1e-12
    assert bb[0][1] > 2.0 - 0.25 + 1e-4          # bottom of the circle is NOT a chord node
    G._assert_pid_stable(s)
    # extrude-DOWN cylinders are refused (no specimen frame)
    with pytest.raises(ValueError):
        G.solid_cylinder_brep([c], 1.0, 0.0, element_id=1)


def test_curved_edge_tessellation_rule():
    """L half (theta pi..2pi, traversed first) = 7 uniform chords, U half
    = 6 uniform chords [V on all 8 half-arcs of specimen 614]."""
    import math
    c = G.circle_profile((0.0, 0.0), 1.0)
    s = G.solid_cylinder_brep([c], 0.0, 1.0, element_id=1)
    edges = s["m_subNodes"][0]["value"]["m_pEdges"]
    top_L = edges[0]                                # tag 3: theta pi -> 2pi at the top
    ths = [top_L["value"]["m_firstAndLastEdgePnts"][0]["uv"][1][0]]
    ths += [p["uv"][1][0] for p in top_L["value"]["m_interiorEdgePnts"]]
    ths += [top_L["value"]["m_firstAndLastEdgePnts"][1]["uv"][1][0]]
    steps = [b - a for a, b in zip(ths, ths[1:])]
    assert all(abs(d - math.pi / 7) < 1e-12 for d in steps)
    assert abs(ths[0] - math.pi) < 1e-12 and abs(ths[-1] - 2 * math.pi) < 1e-12
    top_U = edges[2]                                # tag 6: theta 0 -> pi at the top
    thu = [top_U["value"]["m_firstAndLastEdgePnts"][0]["uv"][1][0]]
    thu += [p["uv"][1][0] for p in top_U["value"]["m_interiorEdgePnts"]]
    thu += [top_U["value"]["m_firstAndLastEdgePnts"][1]["uv"][1][0]]
    assert all(abs((b - a) - math.pi / 6) < 1e-12 for a, b in zip(thu, thu[1:]))
    # both uv frames of a coedge point locate the SAME 3D point: at the
    # top the cap v (= -x offset) matches the cylinder theta via cos
    for p in top_L["value"]["m_interiorEdgePnts"]:
        (cu, cv), (th, z) = p["uv"]
        assert abs(z - 1.0) < 1e-12
        # cap frame: origin V1=(1,0,1), xVec=+y, yVec=-x  =>  u = sin(th), v = 1 - cos(th)
        assert abs(cu - math.sin(th)) < 1e-9 and abs(cv - (1 - math.cos(th))) < 1e-9


@needs_rfa
def test_specimen_cylinders_reproduced_from_dimensions():
    """THE CYLINDER TOPOLOGY PROOF: the sample .rfa's 4-leg extrusion 614
    (10 faces, 24 edges, 16 loops incl. multi-loop caps) rebuilt from its
    four circles + offsets: structure exact, geometry exact, only the
    cap/loop envelope corners differ (Revit's finer envelope
    tessellation, ~1e-4 ft)."""
    r = G.reproduce_specimen_cylinders(RFA_2026, 0, 614)
    assert r["n_faces"] == 10 and r["n_edges"] == 24
    assert r["n_leaves"] > 1400
    assert r["structurally_exact"], r["structural_mismatches"][:8]
    assert r["geometry_exact"], r["geometry_devs_over_1e9"][:8]
    assert r["geometry_max_float_dev"] < 1e-12          # 678 leaves: transform noise only
    assert r["envelope_max_dev"] < 2e-4                 # cache-envelope tessellation class
    assert r["ok"]


@needs_schema
@pytest.mark.parametrize("rep", [G.REP_SOLID, G.REP_DUMMY])
def test_cylinder_bundle_schema_roundtrip(ctx, rep):
    fb = G.cylinder(G.inches(3), G.mm(190), ctx, _Ids(), center=(1.0, 1.0), rep=rep)
    assert [e.class_name for e in fb.elements] == \
        ["SketchPlane", "VarSketch", "CurveElem", "CurveElem", "ExtrusionElem"]
    rt = fb.roundtrip()
    assert rt["ok"], [(k, v) for k, v in rt["elements"].items() if not v["ok"]]
    ex = fb.by_class("ExtrusionElem")[0]
    assert (ex.rep is not None) == (rep == G.REP_SOLID)
    ps = {p["m_paramId"]: p["m_value"]
          for p in ex.obj["m_pParamValueSetDouble"]["value"]["m_paramSet"]}
    # extrude-UP: start = 0 (base), end = height
    assert ps[G.BIP_EXTRUSION_START] == 0.0
    assert abs(ps[G.BIP_EXTRUSION_END] - G.mm(190)) < 1e-12
    # helper loop = 2 arcs: L [-pi,0] then U [0,pi], same centre/radius
    loops = ex.obj["m_cellList"]["value"]["m_cells"][0]["value"]["m_pCurveLoops"]
    arcs = loops[0]["value"]["m_curves"]
    assert [a["ptr_class"] for a in arcs] == ["GArc", "GArc"]
    import math
    assert arcs[0]["value"]["m_endParams"] == [-math.pi, 0.0]
    assert arcs[1]["value"]["m_endParams"] == [0.0, math.pi]
    assert arcs[0]["value"]["m_center"] == [1.0, 1.0, 0.0]
    assert abs(arcs[0]["value"]["m_radius"] - G.inches(3)) < 1e-12
    # the two arc CurveElems join each other at both ends and carry the
    # arc-specific machinery (centre marker, ArcElemCell, 2 curve hists)
    cus = fb.by_class("CurveElem")
    ids = [c.elem_id for c in cus]
    for k, c in enumerate(cus):
        joins = c.obj["m_pCurveDriver"]["value"]["m_controlJoinsSet"]
        assert {j["m_JoinInfo"]["m_info"][1]["m_elemId"] for j in joins} == {ids[1 - k]}
        assert c.obj["m_oArcCntr"] is not None
        assert c.obj["m_oArcCntr"]["value"]["m_endParams"] == [0.0, 0.0]
        cells = [x["ptr_class"] for x in c.obj["m_cellList"]["value"]["m_cells"]]
        assert cells == ["SketchMembership", "ArcElemCell", "PatternHelper"]
        assert len(c.obj["m_pGeomTable"]["value"]["m_table"]) == 2
        assert c.header["m_miscId"] == fb.by_class("VarSketch")[0].elem_id
        assert c.header["m_parents"]["value"]["m_hasNonDetermRegenChildren"] is True
    sk = fb.by_class("VarSketch")[0]
    assert sk.obj["m_userId"] == ex.elem_id
    assert [x["ptr_class"] for x in sk.obj["m_absorbedCurves"]] == ["GArc", "GArc"]


@needs_rfa
def test_emit_cylinder_rfa_reads_back_clean(tmp_path, ctx):
    donor = RFA_2026
    wm = G._donor_watermark(donor)
    fb = G.cylinder(G.inches(3), G.mm(190), ctx, G._Ids(wm + 1),
                    center=(G.mm(3000), G.mm(1000)), rep=G.REP_SOLID)
    out = tmp_path / "G_cyl_test.rfa"
    rep = G.emit_form_rfa(donor, str(out), [fb])
    v = rep["verify"]
    assert v["gzip_crc_failures"] == 0 and v["ecc_mismatch"] == 0
    assert v["walker_errors"] == []
    assert v["new_all_clean"] and v["donor_ids_preserved"] and v["ok"]
    assert v["record_counts_out"] == {s: v["record_counts_donor"][s] + 5
                                      for s in ("101", "102", "103")}
    from rvt.families import FamilyIndex
    idx = FamilyIndex(str(out))
    g = idx.value(0, fb.ids[-1], 103)
    assert idx.class_name(idx.unit_records(0)[103][fb.ids[-1]].class_id) == "GElement"
    geo = g["m_subNodes"][0]["value"]
    assert len(geo["m_pFaces"]) == 4 and len(geo["m_pEdges"]) == 6
    assert [f["value"]["m_pSurf"]["ptr_class"] for f in geo["m_pFaces"]] == \
        ["Plane", "Plane", "CylSurf", "CylSurf"]
    vp = G.validate_parity(str(out), donor)
    assert vp["parity"], vp["errors_beyond_baseline"]


@needs_rfa
def test_emit_form_rfa_reads_back_clean(tmp_path, ctx):
    donor = RFA_2026
    wm = G._donor_watermark(donor)
    fb = G.box(G.mm(500), G.mm(300), G.mm(700), ctx, G._Ids(wm + 1),
               center=(G.mm(3000), 0.0), rep=G.REP_SOLID)
    out = tmp_path / "G_box_test.rfa"
    rep = G.emit_form_rfa(donor, str(out), [fb])
    v = rep["verify"]
    assert v["gzip_crc_failures"] == 0 and v["ecc_mismatch"] == 0
    assert v["walker_errors"] == []
    assert v["new_all_clean"] and v["donor_ids_preserved"] and v["ok"]
    # record counts grew by exactly the 7 new elements in every seq
    assert v["record_counts_out"] == {s: v["record_counts_donor"][s] + 7
                                      for s in ("101", "102", "103")}
    # ElemTable count + watermark advanced; graveyard tail preserved
    et = rep["elemtable"]
    assert et["count_after"] == et["count_before"] + 7
    assert et["watermark_after"] == fb.ids[-1]
    assert et["graveyard_bytes"] > 0
    # the new extrusion decodes back with our authored solid
    from rvt.families import FamilyIndex
    idx = FamilyIndex(str(out))
    g = idx.value(0, fb.ids[-1], 103)
    assert idx.class_name(idx.unit_records(0)[103][fb.ids[-1]].class_id) == "GElement"
    geo = g["m_subNodes"][0]["value"]
    assert len(geo["m_pFaces"]) == 6 and len(geo["m_pEdges"]) == 12


@needs_rfa
def test_emitted_family_validates_at_parity(tmp_path, ctx):
    """The emitted .rfa raises NO validator error beyond the donor's own
    baseline (an untouched Autodesk .rfa already reports family-file
    validator gaps -- docs/inbox/families.md)."""
    donor = RFA_2026
    wm = G._donor_watermark(donor)
    fb = G.box(G.mm(500), G.mm(300), G.mm(700), ctx, G._Ids(wm + 1),
               center=(G.mm(3000), 0.0), rep=G.REP_DUMMY)
    out = tmp_path / "G_box_parity.rfa"
    G.emit_form_rfa(donor, str(out), [fb])
    vp = G.validate_parity(str(out), donor)
    assert vp["parity"], vp["errors_beyond_baseline"]
    assert vp["out_stats"]["decode_failures"] == 0
    assert vp["out_stats"]["elements_decoded"] == vp["donor_stats"]["elements_decoded"] + 7


@pytest.mark.parametrize("n", [3, 4, 5, 6, 8, 12])
def test_prism_solid_is_a_closed_manifold(n):
    """Every generated prism must be a CLOSED, self-consistent solid.  The
    validator cannot see this (it checks records, not B-rep topology), so a
    broken solid used to reach Revit with 0 errors reported."""
    import math
    ring = [[math.cos(2 * math.pi * k / n), math.sin(2 * math.pi * k / n)]
            for k in range(n)]
    assert G.check_solid(G.solid_box_brep(ring, 1.0, 0.0, element_id=1),
                         expect_n=n) == []


def test_check_solid_catches_an_open_shell():
    """The check must FAIL on a solid that is missing a face -- otherwise it
    is not evidence of anything."""
    g = G.solid_box_brep(G.rect_profile(1.0, 1.0), 1.0, 0.0, element_id=1)
    assert G.check_solid(g, expect_n=4) == []
    g["m_subNodes"][0]["value"]["m_pFaces"].pop()          # drop a side face
    assert G.check_solid(g, expect_n=4) != []


def test_concave_prism_solid_is_closed():
    L = [[0, 0], [1.5, 0], [1.5, .4], [.4, .4], [.4, 1.2], [0, 1.2]]
    assert G.check_solid(G.solid_box_brep(L, 1.0, 0.0, element_id=1),
                         expect_n=6) == []

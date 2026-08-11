# DO NOT APPEND NEW TESTS HERE (#636). Every assembly-lane PR used to add its tests to the end of this file, so any
# two of them in flight conflicted at the EOF and one paid a rebase + a full CI re-run (#583/#626/#627/#632/#635).
# A PR that adds tests for this lane creates its OWN module, tests/test_ifc_assembly_<issue>.py, plus a drop-in
# tests/ci_shard.d/<issue>-<slug>.txt (see tests/ci_shard.d/README), reusing fixtures via tests/conftest.py or an
# import from this module. Touch this file only to genuinely edit the tests already in it.
"""The ASSEMBLY lane: an arbitrary-geometry IFC -> one multi-part .rfa.

Covers :mod:`rvt.ifc.assembly_parts` (hull, prism fit, mesh volume, the
reader) and the ``ifc -> rfa`` router fallback that uses it.  Every fixture
is SYNTHESISED here as IFC4 STEP text -- no ``samples/``, no built ladder, no
ifcopenshell: the file runs on a fresh clone.

Territory: ifc-assembly stream.
"""
from __future__ import annotations

import json
import math
import os

import pytest

from rvt.ifc import assembly_parts as AP


# ---------------------------------------------------------------------------
# fixtures: a minimal IFC4 with N triangulated boxes / prisms
# ---------------------------------------------------------------------------

_HEADER = """ISO-10303-21;
HEADER;
FILE_DESCRIPTION((''),'2;1');
FILE_NAME('{name}','2026-01-01T00:00:00',('t'),('t'),'tekton-test','tekton-test','');
FILE_SCHEMA(('IFC4'));
ENDSEC;
DATA;
#1=IFCPERSON($,$,'t',$,$,$,$,$);
#2=IFCORGANIZATION($,'t',$,$,$);
#3=IFCPERSONANDORGANIZATION(#1,#2,$);
#4=IFCAPPLICATION(#2,'1.0','tekton-test','TT');
#5=IFCOWNERHISTORY(#3,#4,$,.ADDED.,$,$,$,0);
#6=IFCSIUNIT(*,.LENGTHUNIT.,{prefix},.METRE.);
#10=IFCUNITASSIGNMENT((#6));
#11=IFCDIRECTION((0.,0.,1.));
#12=IFCDIRECTION((1.,0.,0.));
#13=IFCCARTESIANPOINT((0.,0.,0.));
#14=IFCAXIS2PLACEMENT3D(#13,#11,#12);
#15=IFCGEOMETRICREPRESENTATIONCONTEXT($,'Model',3,1.E-05,#14,$);
#16=IFCPROJECT('0project0000000000000t',#5,'T',$,$,$,$,(#15),#10);
#17=IFCLOCALPLACEMENT($,#14);
#18=IFCSITE('0site000000000000000t',#5,'Site',$,$,#17,$,$,.ELEMENT.,$,$,$,$,$);
"""


def _box_mesh(w, d, h, ox=0.0, oy=0.0, oz=0.0):
    """8 corners + 12 triangles of an axis-aligned box (model units)."""
    x0, x1 = ox - w / 2.0, ox + w / 2.0
    y0, y1 = oy - d / 2.0, oy + d / 2.0
    z0, z1 = oz, oz + h
    pts = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
           (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    tris = [(1, 3, 2), (1, 4, 3), (5, 6, 7), (5, 7, 8), (1, 2, 6), (1, 6, 5),
            (2, 3, 7), (2, 7, 6), (3, 4, 8), (3, 8, 7), (4, 1, 5), (4, 5, 8)]
    return pts, tris


def _prism_mesh(radius, h, sides, ox=0.0, oy=0.0, oz=0.0):
    """A regular N-gon prism -- the shape a tessellated cylinder arrives as."""
    ring = [(ox + radius * math.cos(2 * math.pi * i / sides),
             oy + radius * math.sin(2 * math.pi * i / sides)) for i in range(sides)]
    pts = [(x, y, oz) for x, y in ring] + [(x, y, oz + h) for x, y in ring]
    tris = []
    for i in range(sides):
        j = (i + 1) % sides
        a, b, c, d = i + 1, j + 1, j + 1 + sides, i + 1 + sides
        tris += [(a, b, c), (a, c, d)]
    for i in range(1, sides - 1):                      # caps (fans)
        tris.append((1, i + 2, i + 1))
        tris.append((1 + sides, 1 + sides + i, 2 + sides + i))
    return pts, tris


def write_ifc(path, bodies, *, prefix="$", placements=None):
    """``bodies`` = [(name, ifc_class, (pts, tris))]; one product each."""
    out = [_HEADER.format(name=os.path.basename(path), prefix=prefix)]
    nid = 100
    for i, (name, klass, (pts, tris)) in enumerate(bodies):
        cp = ",".join("(%.6f,%.6f,%.6f)" % p for p in pts)
        ci = ",".join("(%d,%d,%d)" % t for t in tris)
        shift = (placements or {}).get(name)
        if shift:
            out.append(f"#{nid}=IFCCARTESIANPOINT(({shift[0]:.6f},{shift[1]:.6f},{shift[2]:.6f}));")
            out.append(f"#{nid + 1}=IFCAXIS2PLACEMENT3D(#{nid},#11,#12);")
            out.append(f"#{nid + 2}=IFCLOCALPLACEMENT(#17,#{nid + 1});")
            place = nid + 2
            nid += 3
        else:
            place = 17
        out.append(f"#{nid}=IFCCARTESIANPOINTLIST3D(({cp}));")
        out.append(f"#{nid + 1}=IFCTRIANGULATEDFACESET(#{nid},$,.T.,({ci}),$);")
        out.append(f"#{nid + 2}=IFCSHAPEREPRESENTATION(#15,'Body','Tessellation',(#{nid + 1}));")
        out.append(f"#{nid + 3}=IFCPRODUCTDEFINITIONSHAPE($,$,(#{nid + 2}));")
        out.append(f"#{nid + 4}={klass}('{i:022d}',#5,'{name}',$,$,#{place},#{nid + 3},$"
                   + (",.NOTDEFINED.);" if klass != "IFCBUILDINGELEMENTPROXY" else ",.NOTDEFINED.);"))
        nid += 10
    out.append("ENDSEC;\nEND-ISO-10303-21;\n")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    return path


FT = AP.FT_PER_M


# ---------------------------------------------------------------------------
# plan geometry
# ---------------------------------------------------------------------------

def test_convex_hull_of_a_square_is_its_four_corners():
    pts = [(0, 0), (1, 0), (1, 1), (0, 1), (0.5, 0.5), (0.25, 0.75)]
    hull = AP.convex_hull_2d(pts)
    assert len(hull) == 4
    assert sorted(tuple(v) for v in hull) == [(0.0, 0.0), (0.0, 1.0), (1.0, 0.0), (1.0, 1.0)]


def test_convex_hull_drops_collinear_points():
    hull = AP.convex_hull_2d([(0, 0), (1, 0), (2, 0), (2, 2), (0, 2), (0, 1)])
    assert len(hull) == 4


def test_convex_hull_of_two_points_is_not_a_ring():
    assert len(AP.convex_hull_2d([(0, 0), (1, 1), (1, 1)])) == 2


def test_mesh_volume_of_a_unit_cube_is_one():
    pts, tris = _box_mesh(1.0, 1.0, 1.0)
    zero = [(p[0], p[1], p[2]) for p in pts]
    tri0 = [(a - 1, b - 1, c - 1) for a, b, c in tris]
    assert AP.mesh_volume(zero, tri0) == pytest.approx(1.0, rel=1e-9)


def test_mesh_volume_is_translation_invariant():
    """The divergence-theorem sum is about the origin -- a body far from it
    must still measure its own volume, or `fill` would be nonsense for any
    real (site-placed) IFC."""
    pts, tris = _box_mesh(2.0, 3.0, 4.0, ox=100.0, oy=-250.0, oz=17.0)
    tri0 = [(a - 1, b - 1, c - 1) for a, b, c in tris]
    assert AP.mesh_volume(pts, tri0) == pytest.approx(24.0, rel=1e-9)


# ---------------------------------------------------------------------------
# the prism fit
# ---------------------------------------------------------------------------

def test_fit_box_reports_its_extents_and_centre():
    pts, _ = _box_mesh(2.0, 4.0, 6.0, ox=1.0, oy=-1.0, oz=3.0)
    fit = AP.fit_solid(pts)
    assert fit["fit"] == "box"
    assert fit["width_ft"] == pytest.approx(2.0)
    assert fit["depth_ft"] == pytest.approx(4.0)
    assert fit["height_ft"] == pytest.approx(6.0)
    assert fit["base_z_ft"] == pytest.approx(3.0)
    assert fit["center"] == pytest.approx((1.0, -1.0))


def test_fit_cylinder_from_a_tessellated_prism():
    pts, _ = _prism_mesh(0.5, 3.0, 24, ox=2.0, oy=2.0)
    fit = AP.fit_solid(pts)
    assert fit["fit"] == "cylinder"
    assert fit["radius_ft"] == pytest.approx(0.5, rel=0.02)
    assert fit["center"] == pytest.approx((2.0, 2.0), abs=1e-6)


def test_a_coarse_prism_is_a_polygon_not_a_cylinder():
    """6 sides is a hexagon the caller drew, not a circle to smooth away."""
    pts, _ = _prism_mesh(1.0, 1.0, 6)
    assert AP.fit_solid(pts)["fit"] == "polygon"


def test_rotated_rectangle_becomes_a_polygon_that_keeps_its_area():
    a = math.radians(30.0)
    corners = [(-1, -0.25), (1, -0.25), (1, 0.25), (-1, 0.25)]
    rot = [(x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a))
           for x, y in corners]
    pts = [(x, y, 0.0) for x, y in rot] + [(x, y, 2.0) for x, y in rot]
    fit = AP.fit_solid(pts)
    assert fit["fit"] == "polygon"
    assert len(fit["vertices"]) == 4
    assert AP._polygon_area(fit["vertices"]) == pytest.approx(1.0, rel=1e-6)


def test_a_degenerate_mesh_is_refused_by_name_never_given_a_thickness():
    flat = [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)]
    with pytest.raises(AP.AssemblyError) as e:
        AP.fit_solid(flat)
    assert "degenerate in z" in str(e.value)


def test_fill_is_none_without_a_mesh_volume_never_assumed_full():
    pts, _ = _box_mesh(1.0, 1.0, 1.0)
    assert AP.fit_solid(pts)["fill"] is None


def test_fill_measures_the_prism_the_mesh_actually_occupies():
    pts, _ = _prism_mesh(1.0, 2.0, 64)                 # a circle in a circle
    assert AP.fit_solid(pts, math.pi * 2.0)["fill"] == pytest.approx(1.0, rel=0.01)
    # the same footprint holding half the material reads as a half-full envelope
    assert AP.fit_solid(pts, math.pi)["fill"] == pytest.approx(0.5, rel=0.01)


def test_hull_is_decimated_to_the_authored_cap():
    ring = [(math.cos(t / 200.0 * 2 * math.pi) * (1.0 + 0.35 * (t % 2)),
             math.sin(t / 200.0 * 2 * math.pi) * (1.0 + 0.35 * (t % 2)))
            for t in range(200)]
    pts = [(x, y, 0.0) for x, y in ring] + [(x, y, 1.0) for x, y in ring]
    fit = AP.fit_solid(pts)
    if fit["fit"] == "polygon":
        assert len(fit["vertices"]) <= AP.MAX_HULL_POINTS


# ---------------------------------------------------------------------------
# the reader
# ---------------------------------------------------------------------------

def test_reads_every_product_and_keeps_their_relative_positions(tmp_path):
    p = write_ifc(str(tmp_path / "two.ifc"), [
        ("Base", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 1.0, 0.2)),
        ("Post", "IFCMEMBER", _prism_mesh(0.1, 2.0, 24, oz=0.2)),
    ])
    m = AP.read_assembly(p, recentre=False)
    assert len(m.parts) == 2
    assert m.fit_counts() == {"box": 1, "cylinder": 1}
    post = [x for x in m.parts if x.name == "Post"][0]
    assert post.base_z_ft == pytest.approx(0.2 * FT, rel=1e-6)   # stacked, not piled
    assert post.height_ft == pytest.approx(2.0 * FT, rel=1e-6)


def test_units_are_honoured_millimetres_are_not_read_as_metres(tmp_path):
    p = write_ifc(str(tmp_path / "mm.ifc"),
                  [("B", "IFCBUILDINGELEMENTPROXY", _box_mesh(1000.0, 1000.0, 1000.0))],
                  prefix=".MILLI.")
    m = AP.read_assembly(p, recentre=False)
    assert m.unit_scale_m == pytest.approx(0.001)
    assert m.parts[0].height_ft == pytest.approx(FT, rel=1e-6)   # 1000 mm = 1 m


def test_the_placement_chain_moves_a_part_into_the_assembly(tmp_path):
    p = write_ifc(str(tmp_path / "placed.ifc"),
                  [("Far", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 1.0, 1.0))],
                  placements={"Far": (10.0, 20.0, 30.0)})
    m = AP.read_assembly(p, recentre=False)
    assert m.parts[0].center_ft[0] == pytest.approx(10.0 * FT, rel=1e-6)
    assert m.parts[0].base_z_ft == pytest.approx(30.0 * FT, rel=1e-6)


def test_recentre_puts_the_family_origin_at_the_plan_centre_and_base(tmp_path):
    p = write_ifc(str(tmp_path / "off.ifc"),
                  [("A", "IFCBUILDINGELEMENTPROXY", _box_mesh(2.0, 2.0, 1.0))],
                  placements={"A": (50.0, 60.0, 70.0)})
    m = AP.read_assembly(p, recentre=True)
    assert m.parts[0].center_ft == pytest.approx((0.0, 0.0), abs=1e-9)
    assert m.parts[0].base_z_ft == pytest.approx(0.0, abs=1e-9)
    assert m.origin_shift_ft[2] == pytest.approx(-70.0 * FT, rel=1e-6)


def test_a_degenerate_product_is_skipped_by_name_and_the_rest_survive(tmp_path):
    flat = ([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [(1, 2, 3), (1, 3, 4)])
    p = write_ifc(str(tmp_path / "mixed.ifc"), [
        ("Sheet", "IFCBUILDINGELEMENTPROXY", flat),
        ("Solid", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 1.0, 1.0)),
    ])
    m = AP.read_assembly(p)
    assert [x.name for x in m.parts] == ["Solid"]
    assert m.skipped and m.skipped[0]["name"] == "Sheet"
    assert "degenerate" in m.skipped[0]["reason"]
    assert any("skipped by name" in n for n in m.notes)


def test_an_ifc_with_nothing_measurable_raises_not_invents(tmp_path):
    flat = ([(0, 0, 0), (1, 0, 0), (1, 1, 0)], [(1, 2, 3)])
    p = write_ifc(str(tmp_path / "flat.ifc"), [("S", "IFCBUILDINGELEMENTPROXY", flat)])
    with pytest.raises(AP.AssemblyError) as e:
        AP.read_assembly(p)
    assert "no measurable solid" in str(e.value)


def test_spatial_structure_is_not_measured_as_a_part(tmp_path):
    p = write_ifc(str(tmp_path / "one.ifc"),
                  [("Only", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 1.0, 1.0))])
    m = AP.read_assembly(p)
    assert [x.ifc_class for x in m.parts] == ["IfcBuildingElementProxy"]


def test_to_parts_is_the_factory_contract(tmp_path):
    p = write_ifc(str(tmp_path / "c.ifc"), [
        ("Box", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 2.0, 3.0)),
        ("Rod", "IFCMEMBER", _prism_mesh(0.2, 1.0, 24, ox=3.0)),
    ])
    m = AP.read_assembly(p)
    assert {x.fit for x in m.parts} == {"box", "cylinder"}
    parts = m.to_parts()
    assert {q["shape"] for q in parts} == {"box", "cylinder"}
    for q in parts:
        assert q["height_ft"] > 0
        assert "base_z_ft" in q and "name" in q
        if q["shape"] == "box":
            assert q["width_ft"] > 0 and q["depth_ft"] > 0 and len(q["center"]) == 2
        else:
            assert q["radius_ft"] > 0 and len(q["center"]) == 2


def test_json_record_carries_the_numbers_a_reader_needs(tmp_path):
    p = write_ifc(str(tmp_path / "j.ifc"),
                  [("Box", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 2.0, 3.0))])
    d = AP.read_assembly(p).to_json()
    assert d["part_count"] == 1
    assert d["overall_dims_in"]["z"] == pytest.approx(3.0 * FT * 12.0, rel=1e-6)
    assert d["parts"][0]["fill"] == pytest.approx(1.0, rel=1e-6)
    json.dumps(d)                                     # the record must serialise


# ---------------------------------------------------------------------------
# the router lane
# ---------------------------------------------------------------------------

def test_ifc_to_rfa_falls_through_to_the_assembly_lane(tmp_path):
    """The whole point: an IFC with several untagged meshes used to END at
    'name one'.  It must now DELIVER one multi-part family."""
    from rvt.frontdoor import router as R
    p = write_ifc(str(tmp_path / "asm.ifc"), [
        ("Plate", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 1.0, 0.1)),
        ("Post A", "IFCMEMBER", _prism_mesh(0.05, 1.0, 24, ox=-0.4, oz=0.1)),
        ("Post B", "IFCMEMBER", _prism_mesh(0.05, 1.0, 24, ox=0.4, oz=0.1)),
    ])
    out = str(tmp_path / "out")
    res = R.route({"ifc": p}, "rfa", out=out, quiet=True)
    d = res.to_json() if hasattr(res, "to_json") else {}
    assert res.ok, d.get("status")
    rfa = res.files.get("rfa")
    assert rfa and os.path.isfile(rfa)
    assert os.path.isfile(res.files["assembly_parts"])
    with open(res.files["assembly_parts"], encoding="utf-8") as fh:
        rec = json.load(fh)
    assert rec["part_count"] == 3
    assert not res.errors                       # the refusal became a caveat
    assert any("ASSEMBLY LANE" in c for c in res.caveats)
    assert any("PRISMATIC MASSING" in c for c in res.caveats)


def test_the_assembly_lane_says_what_it_could_not_measure(tmp_path):
    from rvt.frontdoor import router as R
    flat = ([(0, 0, 0), (1, 0, 0), (1, 1, 0)], [(1, 2, 3)])
    p = write_ifc(str(tmp_path / "none.ifc"), [("S", "IFCBUILDINGELEMENTPROXY", flat)])
    res = R.route({"ifc": p}, "rfa", out=str(tmp_path / "o2"), quiet=True)
    assert not res.ok
    assert "tessellated" in (res.line or "").lower()


# ---------------------------------------------------------------------------
# slab decomposition
# ---------------------------------------------------------------------------

def _tri0(tris):
    return [(a - 1, b - 1, c - 1) for a, b, c in tris]


def test_slice_of_a_box_is_its_rectangle():
    pts, tris = _box_mesh(2.0, 4.0, 6.0)
    rings = AP.slice_loops(pts, _tri0(tris), 3.0)
    assert len(rings) == 1
    assert AP._polygon_area(rings[0]) == pytest.approx(8.0, rel=1e-9)


def test_two_regions_touching_at_a_point_resolve_into_two_rings():
    """Two boxes meeting at exactly one corner. The segments alone do not say
    which continues into which; the MATERIAL does -- the wedge between two
    spokes is either inside the section or not. This used to be refused as
    ambiguous, which cost the beam clamp (and every C-shape) its geometry."""
    p1, t1 = _box_mesh(1.0, 1.0, 2.0, ox=-0.5, oy=-0.5)
    p2, t2 = _box_mesh(1.0, 1.0, 2.0, ox=0.5, oy=0.5)
    pts = list(p1) + list(p2)
    tris = _tri0(t1) + [(a - 1 + len(p1), b - 1 + len(p1), c - 1 + len(p1))
                        for a, b, c in t2]
    rings = AP.slice_loops(pts, tris, 1.0)
    assert rings is not None and len(rings) == 2
    assert [round(AP._polygon_area(r), 6) for r in rings] == [1.0, 1.0]
    assert AP.ring_nesting(rings) == [0, 0]        # two solids, neither a hole


def test_an_open_chain_is_still_refused():
    """A vertex of ODD degree cannot close: that is a broken slice, not a
    junction, and must still be refused rather than guessed."""
    segs = [((0.0, 0.0), (1.0, 0.0)), ((1.0, 0.0), (1.0, 1.0))]
    assert AP._stitch(segs) is None


def test_ring_nesting_marks_a_hole_odd_and_its_island_even():
    outer = [[0, 0], [10, 0], [10, 10], [0, 10]]
    hole = [[2, 2], [8, 2], [8, 8], [2, 8]]
    island = [[4, 4], [6, 4], [6, 6], [4, 6]]
    assert AP.ring_nesting([outer, hole, island]) == [0, 1, 2]


def test_two_stacked_boxes_decompose_into_two_slabs():
    pts, tris = _box_mesh(4.0, 4.0, 1.0)
    p2, t2 = _box_mesh(1.0, 1.0, 1.0, oz=1.0)
    n = len(pts)
    allp = list(pts) + list(p2)
    allt = _tri0(tris) + [(a - 1 + n, b - 1 + n, c - 1 + n) for a, b, c in t2]
    dec = AP.decompose_slabs(allp, allt)
    assert dec is not None
    assert len(dec["parts"]) == 2
    assert dec["volume_ft3"] == pytest.approx(16.0 + 1.0, rel=1e-6)


def test_a_constant_section_merges_into_one_part_not_many():
    """A plain rod must not come back as a stack of pancakes."""
    pts, tris = _prism_mesh(0.5, 4.0, 24)
    dec = AP.decompose_slabs(pts, _tri0(tris))
    if dec is not None:
        assert len(dec["parts"]) == 1


def test_decomposition_conserves_material_or_is_refused():
    assert AP._conserves(1.0, 1.0)
    assert AP._conserves(1.5, 1.0)          # a filled hole ADDS material: fine
    assert not AP._conserves(0.5, 1.0)      # lost material: never acceptable


def test_the_budget_is_a_refusal_not_a_truncation():
    pts, tris = _box_mesh(1.0, 1.0, 1.0)
    assert AP.decompose_slabs(pts, _tri0(tris), max_parts=0) is None
    assert AP.decompose_slabs(pts, _tri0(tris), max_slabs=0) is None


def test_a_body_whose_section_runs_sideways_is_now_exact_not_an_envelope(tmp_path):
    """Was the known gap: a C-section constant along X cannot be sliced into
    Z slabs, so it used to keep a 0.20-fill envelope. It is a union of
    axis-aligned boxes, so the box lane reproduces it exactly -- no rotation
    in the part contract, none needed."""
    pts, tris = _u_channel()
    p = write_ifc(str(tmp_path / "u.ifc"),
                  [("U Channel", "IFCMEMBER",
                    (pts, [(a + 1, b + 1, c + 1) for a, b, c in tris]))])
    m = AP.read_assembly(p)
    assert not m.kept_prism
    assert m.decomposed and m.decomposed[0]["exact"] is True
    assert m.decomposed[0]["fill_before"] < 0.6      # the envelope it replaced
    assert m.decomposed[0]["fill_after"] == 1.0


def test_decomposition_is_reported_per_product(tmp_path):
    pts, tris = _box_mesh(4.0, 4.0, 1.0)
    p2, t2 = _box_mesh(1.0, 1.0, 1.0, oz=1.0)
    n = len(pts)
    allp = list(pts) + list(p2)
    allt = list(tris) + [(a + n, b + n, c + n) for a, b, c in t2]
    p = write_ifc(str(tmp_path / "d.ifc"), [("Stepped", "IFCBUILDINGELEMENTPROXY", (allp, allt))])
    m = AP.read_assembly(p)
    assert len(m.parts) == 2
    assert m.decomposed and m.decomposed[0]["name"] == "Stepped"
    assert m.decomposed[0]["fill_after"] > m.decomposed[0]["fill_before"]
    assert all(x.of_product == "Stepped" for x in m.parts)
    assert [x.name for x in m.parts] == ["Stepped [1/2]", "Stepped [2/2]"]


def test_decompose_can_be_switched_off(tmp_path):
    pts, tris = _box_mesh(4.0, 4.0, 1.0)
    p2, t2 = _box_mesh(1.0, 1.0, 1.0, oz=1.0)
    n = len(pts)
    allp = list(pts) + list(p2)
    allt = list(tris) + [(a + n, b + n, c + n) for a, b, c in t2]
    p = write_ifc(str(tmp_path / "d2.ifc"), [("Stepped", "IFCBUILDINGELEMENTPROXY", (allp, allt))])
    assert len(AP.read_assembly(p, decompose=False).parts) == 1


# ---------------------------------------------------------------------------
# exact box decomposition (the C-channel answer -- no rotation needed)
# ---------------------------------------------------------------------------

def _u_channel(length=4.0, width=1.0, height=1.0, t=0.1):
    """A C-section running along X: web on the -Z face, two flanges up +Z.

    Its cross-section is constant along X, so no Z-slab decomposition can
    express it -- but it IS a union of axis-aligned boxes.
    """
    boxes = [_box_mesh(length, width, t),                                   # web
             _box_mesh(length, t, height - t, oy=-(width - t) / 2.0, oz=t),  # flange
             _box_mesh(length, t, height - t, oy=(width - t) / 2.0, oz=t)]
    pts, tris = [], []
    for p, tr in boxes:
        n = len(pts)
        pts += list(p)
        tris += [(a - 1 + n, b - 1 + n, c - 1 + n) for a, b, c in tr]
    return pts, tris


def test_a_cube_is_axis_aligned_a_prism_is_not():
    assert AP.is_axis_aligned(*(lambda p, t: (p, _tri0(t)))(*_box_mesh(1, 1, 1)))
    pts, tris = _prism_mesh(1.0, 1.0, 12)
    assert not AP.is_axis_aligned(pts, _tri0(tris))


def test_winding_number_is_one_inside_and_zero_outside():
    pts, tris = _box_mesh(2.0, 2.0, 2.0)
    t0 = _tri0(tris)
    assert abs(AP.winding_number(pts, t0, (0.0, 0.0, 1.0))) == pytest.approx(1.0, abs=1e-6)
    assert abs(AP.winding_number(pts, t0, (9.0, 9.0, 9.0))) == pytest.approx(0.0, abs=1e-6)


def test_inside_does_not_depend_on_face_orientation():
    """This IFC winds its triangles so that inside reads -1; the test must
    read the magnitude, or every real body would classify as empty."""
    pts, tris = _box_mesh(2.0, 2.0, 2.0)
    fwd = _tri0(tris)
    rev = [(c, b, a) for a, b, c in fwd]
    assert AP._inside(pts, fwd, (0.0, 0.0, 1.0))
    assert AP._inside(pts, rev, (0.0, 0.0, 1.0))


def test_a_box_decomposes_to_exactly_one_box():
    pts, tris = _box_mesh(2.0, 3.0, 4.0)
    dec = AP.decompose_boxes(pts, _tri0(tris))
    assert dec["n_boxes"] == 1
    assert dec["exact"] is True
    assert dec["volume_ft3"] == pytest.approx(24.0, rel=1e-9)


def test_the_c_channel_decomposes_exactly_without_any_rotation():
    """The headline case. A section running along X cannot be sliced into Z
    slabs, but it IS a union of axis-aligned boxes -- each Z-extrudable."""
    pts, tris = _u_channel()
    dec = AP.decompose_boxes(pts, tris)
    assert dec is not None and dec["exact"]
    assert dec["volume_ft3"] == pytest.approx(AP.mesh_volume(pts, tris), rel=1e-9)
    # and the single prism it replaces really was a poor envelope
    assert AP.fit_solid(pts, AP.mesh_volume(pts, tris))["fill"] < 0.6


def test_overlapping_shells_are_measured_as_a_union_not_counted_twice():
    """Two boxes sharing half their volume: the mesh's divergence volume
    counts the overlap twice, the decomposition must not."""
    p1, t1 = _box_mesh(2.0, 2.0, 2.0)
    p2, t2 = _box_mesh(2.0, 2.0, 2.0, ox=1.0)
    pts = list(p1) + list(p2)
    tris = _tri0(t1) + [(a - 1 + len(p1), b - 1 + len(p1), c - 1 + len(p1))
                        for a, b, c in t2]
    dec = AP.decompose_boxes(pts, tris)
    assert dec is not None
    assert dec["volume_ft3"] == pytest.approx(12.0, rel=1e-6)      # union
    assert AP.mesh_volume(pts, tris) == pytest.approx(16.0, rel=1e-6)  # 8 + 8
    assert dec["overlap_ft3"] == pytest.approx(4.0, rel=1e-6)
    assert dec["volume_ft3"] + dec["overlap_ft3"] == pytest.approx(
        AP.mesh_volume(pts, tris), rel=1e-6)


def test_a_curved_body_is_not_box_decomposed_into_a_staircase():
    pts, tris = _prism_mesh(1.0, 2.0, 24)
    assert AP.decompose_boxes(pts, _tri0(tris)) is None


def test_the_box_budget_is_a_refusal_not_a_truncation():
    pts, tris = _u_channel()
    assert AP.decompose_boxes(pts, tris, max_boxes=1) is None
    assert AP.decompose_boxes(pts, tris, max_cells=1) is None


def test_the_reader_prefers_the_exact_box_lane(tmp_path):
    pts, tris = _u_channel()
    p = write_ifc(str(tmp_path / "chan.ifc"),
                  [("Channel", "IFCMEMBER", (pts, [(a + 1, b + 1, c + 1) for a, b, c in tris]))])
    m = AP.read_assembly(p)
    assert m.decomposed and m.decomposed[0]["method"] == "boxes"
    assert m.decomposed[0]["exact"] is True
    assert m.decomposed[0]["fill_after"] == 1.0
    assert all(x.fit == "box" for x in m.parts)
    assert not m.kept_prism


# ---------------------------------------------------------------------------
# the Load Family crash law (#333 / VarSketch.cpp:634)
# ---------------------------------------------------------------------------

def _inconsistent_sketches(parts, name="probe"):
    """Sketches whose curve index map promises more curves than the solver
    records hold.  ``VarSketch::getCurveObj`` indexes ``m_elemRecs`` through
    that map, so a map longer than the records is an out-of-range read inside
    Revit -- it survives OPEN and kills ``Insert > Load Family``."""
    from rvt.frontdoor import famspec as FS
    doc = FS.build("generic_model", {"parts": parts, "name": name}).doc
    return [e.elem_id for e in doc.elements
            if e.class_name == "VarSketch"
            and len(e.obj.get("m_curveObjIdxMap") or []) > len(e.obj.get("m_elemRecs") or [])]


def test_an_arc_sketch_now_carries_the_solver_records_it_promises():
    """The engine fix (#589). add_cylinder_form used to author a VarSketch
    naming 2 arcs in m_curveObjIdxMap with m_elemRecs EMPTY -- an out-of-range
    read inside VarSketch::getCurveObj that survives OPEN and kills
    Insert > Load Family (owner journal 0040: VarSketch.cpp:634 + 0xc0000005).

    STRUCTURE is fixed and asserted here; whether Revit accepts the arc
    parameter vector is a DESKTOP question and #589 stays open until a verdict.
    """
    from rvt.frontdoor import famspec as FS
    doc = FS.build("generic_model", {"parts": [
        {"shape": "cylinder", "radius_ft": 0.5, "height_ft": 2.0}], "name": "arc"}).doc
    sketches = [e for e in doc.elements if e.class_name == "VarSketch"
                and e.obj.get("m_absorbedCurves")]
    assert sketches, "the cylinder must author a curve sketch"
    for e in sketches:
        o = e.obj
        recs = o.get("m_elemRecs") or []
        assert len(recs) == len(o.get("m_curveObjIdxMap") or []) == len(o["m_absorbedCurves"])
        assert all(r["ptr_class"] == "VarSketchArcObj" for r in recs)
        # the guess cache must declare the same parameter vector the records do
        guess = ((o.get("m_oGuessCache") or {}).get("value") or {}).get("m_guessArr") or []
        n_params = sum(len(r["value"]["m_params"]) for r in recs)
        assert guess and len(guess[0]["value"]["m_values"]) == n_params


def test_line_based_shapes_carry_the_solver_records_they_promise():
    for shape in ({"shape": "box", "width_ft": 1.0, "depth_ft": 1.0, "height_ft": 1.0},
                  {"shape": "polygon", "height_ft": 1.0,
                   "vertices": [[0, 0], [1, 0], [1, 1], [0.5, 1.4], [0, 1]]}):
        assert _inconsistent_sketches([shape], "line") == []


def test_the_assembly_lane_never_emits_a_sketch_revit_cannot_load(tmp_path):
    """THE INVARIANT. Whatever this lane measures -- round, boxy or N-gon --
    the family it hands the factory must not contain a sketch that promises
    curves its solver cannot resolve. This is the check that would have caught
    the crash before a human opened Revit."""
    pts, tris = _prism_mesh(0.5, 3.0, 40)          # measured as a CYLINDER
    box_p, box_t = _box_mesh(1.0, 1.0, 1.0, ox=4.0)
    n = len(pts)
    allp = list(pts) + list(box_p)
    allt = [(a + 1, b + 1, c + 1) for a, b, c in _tri0(tris)] + \
           [(a + n, b + n, c + n) for a, b, c in box_t]
    p = write_ifc(str(tmp_path / "mix.ifc"),
                  [("Rod", "IFCMEMBER", (allp[:n], [(a + 1, b + 1, c + 1) for a, b, c in _tri0(tris)])),
                   ("Block", "IFCBUILDINGELEMENTPROXY", (list(box_p), list(box_t)))])
    m = AP.read_assembly(p)
    assert any(x.fit == "cylinder" for x in m.parts)        # it IS measured round
    assert _inconsistent_sketches(m.to_parts(), "mix") == []  # and still loadable


def test_a_round_profile_is_measured_round_and_authored_round():
    """With #589's arc solver records desktop-verified (A5/A3 load, the empty
    A0 control crashes), a measured cylinder is authored as a real cylinder
    again -- not as the N-gon stand-in the crash forced."""
    pts, _ = _prism_mesh(0.5, 3.0, 40)
    fit = AP.fit_solid(pts)
    assert fit["fit"] == "cylinder"
    assert fit["radius_ft"] == pytest.approx(0.5, rel=0.02)
    part = AP.PartSolid(name="r", ifc_class="IfcMember", tag="", guid="",
                        fit="cylinder", center_ft=tuple(fit["center"]),
                        height_ft=fit["height_ft"], base_z_ft=fit["base_z_ft"],
                        radius_ft=fit["radius_ft"], vertices_ft=fit["vertices"]).to_part()
    assert part["shape"] == "cylinder"
    assert part["radius_ft"] == pytest.approx(0.5, rel=0.02)


# ---------------------------------------------------------------------------
# round and rotated bodies (rvt.famgen.revolve, #591)
# ---------------------------------------------------------------------------

def test_a_sphere_becomes_a_stack_whose_volume_converges():
    """The part contract extrudes along Z only, so a sphere is sliced. More
    slices must get CLOSER to the real volume -- if they do not, the stack is
    not approximating anything."""
    from rvt.famgen import revolve as RV
    errs = []
    for seg in (8, 16, 32, 64):
        _, rep = RV.expand_parts([{"shape": "sphere", "radius_ft": 1.0, "segments": seg}])
        errs.append(abs(rep[0]["ratio"] - 1.0))
    assert errs == sorted(errs, reverse=True), f"error must fall with slices: {errs}"
    assert errs[-1] < 0.005


def test_a_wheel_is_a_TRUE_cylinder_not_a_stack():
    """Desktop round 4 (#591) settled it: the cached B-rep is what Revit draws,
    so a wheel is authored as a real cylinder whose B-rep is rotated onto a
    horizontal axis -- verified round in the Front elevation. The old stack of
    boxes is retired, and the expander must leave these shapes alone."""
    from rvt.famgen import revolve as RV
    from rvt.frontdoor import famspec as FS
    part = {"shape": "cylinder_y", "radius_ft": 1.72, "length_ft": 0.95,
            "center": [2.0, 3.0], "name": "wheel"}
    made, rep = RV.expand_parts([part])
    assert [p["shape"] for p in made] == ["cylinder_y"] and rep == []

    doc = FS.build("generic_model", {"parts": [part], "name": "W"}).doc
    axes = []

    def walk(v):
        if isinstance(v, dict):
            for k, x in v.items():
                if k == "m_zVec" and isinstance(x, list):
                    axes.append([round(n, 6) for n in x])
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)
    for e in doc.elements:
        if e.class_name == "ExtrusionElem" and e.rep is not None:
            walk(e.rep)
    assert axes, "the wheel must author a cylinder surface"
    assert all(a == [0.0, 1.0, 0.0] for a in axes), f"axis must be +Y, got {axes}"


def test_a_horizontal_cylinder_is_refused_without_its_length():
    from rvt.famgen import factory as F
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("generic_model", "x", work_plane_based=False,
                                 start_id=1000)
    with pytest.raises(F.FactoryError) as e:
        F.add_generic_part(doc, {"shape": "cylinder_y", "radius_ft": 1.0})
    assert "length_ft" in str(e.value)


def test_a_round_body_rests_on_its_base_z_not_centred_on_it():
    from rvt.famgen import revolve as RV
    made, _ = RV.expand_parts([{"shape": "sphere", "radius_ft": 2.0, "base_z_ft": 10.0}])
    assert min(p["base_z_ft"] for p in made) == pytest.approx(10.0, abs=1e-9)
    tops = [p["base_z_ft"] + p["height_ft"] for p in made]
    assert max(tops) == pytest.approx(14.0, abs=1e-9)                 # 10 + 2r


def test_composites_expand_only_where_asked():
    from rvt.famgen import revolve as RV
    plain = {"shape": "box", "width_ft": 1, "depth_ft": 1, "height_ft": 1}
    made, rep = RV.expand_parts([plain, {"shape": "dome", "radius_ft": 1.0}])
    assert made[0] == plain                       # untouched, same object
    assert rep and rep[0]["shape"] == "dome"


def test_a_round_body_without_its_dimension_is_refused_by_name():
    from rvt.famgen import revolve as RV
    for part, want in (({"shape": "sphere", "radius_ft": 0}, "positive radius"),
                       ({"shape": "dome", "radius_ft": 0}, "positive radius"),
                       ({"shape": "sphere", "radius_ft": 1.0, "segments": 2}, "too few")):
        with pytest.raises(RV.RevolveError) as e:
            RV.expand_parts([part])
        assert want in str(e.value)


def test_the_detailed_bus_builds_and_never_ships_an_unloadable_sketch():
    """End to end for 'make a bus': round wheels, a dome, and the sketch
    invariant that Load Family depends on."""
    parts = [{"shape": "box", "width_ft": 40, "depth_ft": 8.5, "height_ft": 7.2,
              "base_z_ft": 1.9, "name": "body"},
             {"shape": "dome", "radius_ft": 1.5, "base_z_ft": 9.4, "segments": 8,
              "name": "roof pod"}]
    for x, y in ((-14.5, -3.55), (-14.5, 3.55), (11.0, -3.55), (11.0, 3.55)):
        parts.append({"shape": "cylinder_y", "radius_ft": 1.72, "length_ft": 0.95,
                      "center": [x, y], "segments": 12, "name": f"wheel {x},{y}"})
    from rvt.frontdoor import famspec as FS
    spec = {"kind": "generic_model", "name": "Bus", "parts": parts}
    assert FS.validate(spec) == []
    assert _inconsistent_sketches(parts, "bus") == []


# ---------------------------------------------------------------------------
# tech-lead pre-merge fix (#609): "exact" is checked, never assumed, and a
# solid ring is never dropped as a hole
# ---------------------------------------------------------------------------

def _yaw(pts, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return [(x * c - y * s, x * s + y * c, z) for x, y, z in pts]


def _strut(deg):
    """A 900 mm strut, 41 x 41 mm section, 2.5 mm wall, yawed about Z --
    1-based triangles, ready for write_ifc."""
    pts, tris = _u_channel(length=0.9, width=0.041, height=0.041, t=0.0025)
    return _yaw(pts, deg), [(a + 1, b + 1, c + 1) for a, b, c in tris]


def _strut_mismatch(deg, dz=50e-6):
    """The same strut with its two flanges dz metres different in height --
    the hairline disagreement two CAD shells routinely have along a seam."""
    length, width, height, t = 0.9, 0.041, 0.041, 0.0025
    pts, tris = [], []
    for p, tr in (_box_mesh(length, width, t),
                  _box_mesh(length, t, height - t, oy=-(width - t) / 2.0, oz=t),
                  _box_mesh(length, t, height - t - dz, oy=(width - t) / 2.0, oz=t)):
        n = len(pts)
        pts += list(p)
        tris += [(a + n, b + n, c + n) for a, b, c in tr]
    return _yaw(pts, deg), tris


def _frustum(r0=0.10, r1=0.05, h=0.20, bands=8, sides=32):
    """A tessellated reducer: `bands` latitude rings on a linear taper."""
    pts, tris = [], []
    for b in range(bands + 1):
        z, r = h * b / bands, r0 + (r1 - r0) * b / bands
        pts += [(r * math.cos(2 * math.pi * i / sides), r * math.sin(2 * math.pi * i / sides), z)
                for i in range(sides)]
    for b in range(bands):
        for i in range(sides):
            j = (i + 1) % sides
            a, b2, c, d = b * sides + i, b * sides + j, (b + 1) * sides + j, (b + 1) * sides + i
            tris += [(a, b2, c), (a, c, d)]
    top = bands * sides
    for i in range(1, sides - 1):
        tris += [(0, i + 1, i), (top, top + i, top + i + 1)]
    return pts, [(a + 1, b + 1, c + 1) for a, b, c in tris]


def _authored_ft3(model):
    v = 0.0
    for p in model.parts:
        if p.fit == "box":
            v += p.width_ft * p.depth_ft * p.height_ft
        elif p.fit == "polygon":
            v += AP._polygon_area(p.vertices_ft) * p.height_ft
        else:
            v += math.pi * p.radius_ft ** 2 * p.height_ft
    return v


def _mesh_ft3(pts_m, tris1):
    return AP.mesh_volume([(x * FT, y * FT, z * FT) for x, y, z in pts_m], _tri0(tris1))


def test_axis_alignment_is_float_noise_not_an_angle_budget():
    """1 - cos(0.1 deg) = 1.5e-6 sailed under the old 1e-4 and turned a strut
    into a dozen sliver boxes.  Aligned means ALIGNED."""
    pts, tris = _strut(0.0)
    assert AP.is_axis_aligned(pts, _tri0(tris))
    for deg in (0.05, 0.1, 0.2, 0.8):
        pts, tris = _strut(deg)
        assert not AP.is_axis_aligned(pts, _tri0(tris)), deg


def test_a_sliver_box_refuses_the_box_lane_a_hairline_step_does_not():
    """A MERGED box thinner than MIN_EXTENT_FT is a sliver Revit cannot keep
    (and the signature of a nearly-aligned body): no box lane.  A hairline
    grid step that merges away -- two flanges 50 um different in height, the
    multi-shell CAD noise real exports carry -- must NOT cost the lane."""
    p1, t1 = _box_mesh(1.0, 1.0, 1.0)
    shim, _ = _box_mesh(0.5, 0.5, AP.MIN_EXTENT_FT / 2.0, oz=1.0)      # a real 0.2 mm film
    tris = _tri0(t1) + [(a + len(p1), b + len(p1), c + len(p1)) for a, b, c in _tri0(t1)]
    assert AP.is_axis_aligned(list(p1) + list(shim), tris)          # aligned, and still refused:
    assert AP.decompose_boxes(list(p1) + list(shim), tris) is None
    pts, tris1 = _strut_mismatch(0.0)                               # 50 um step between flanges
    dec = AP.decompose_boxes([(x * FT, y * FT, z * FT) for x, y, z in pts], _tri0(tris1))
    assert dec is not None and dec["n_boxes"] == 3
    assert min(min(q["width_ft"], q["depth_ft"], q["height_ft"]) for q in dec["parts"]) > AP.MIN_EXTENT_FT


@pytest.mark.parametrize("deg", [0.1, 0.2, 0.5, 0.8])
def test_a_yawed_channel_is_exact_slabs_never_sliver_boxes(tmp_path, deg):
    """THE REGRESSION.  A strut yawed a fraction of a degree is not an
    axis-aligned polyhedron; head authored it as ~10 'exact' boxes, most
    thinner than MIN_EXTENT_FT, at 50-300 % of the mesh's volume.  It must
    fall through to the slab lane, which authors its three rotated rectangles
    exactly -- as main always did."""
    pts, tris = _strut(deg)
    p = write_ifc(str(tmp_path / f"strut_{deg}.ifc"), [("Strut", "IFCMEMBER", (pts, tris))])
    m = AP.read_assembly(p)
    assert not m.kept_prism
    assert m.decomposed and m.decomposed[0]["method"] == "slabs"
    assert m.decomposed[0]["exact"] is False
    assert len(m.parts) == 3 and all(x.fit == "polygon" for x in m.parts)
    assert min(x.height_ft for x in m.parts) > AP.MIN_EXTENT_FT
    mesh, authored = _mesh_ft3(pts, tris), _authored_ft3(m)
    assert AP._conserves(authored, mesh, AP.EXACT_REL_TOL)   # nothing lost
    assert authored == pytest.approx(mesh, rel=1e-3)         # nothing invented


def test_the_box_lane_is_held_to_the_mesh_volume(tmp_path, monkeypatch):
    """'Exact' is a claim about volume and is checked as one.  Unyawed, the
    strut takes the box lane and gives the mesh's volume back to 1e-6; a box
    set that does not is not accepted, whatever is_axis_aligned thought of
    the faces."""
    pts, tris = _strut(0.0)
    p = write_ifc(str(tmp_path / "s.ifc"), [("Strut", "IFCMEMBER", (pts, tris))])
    mesh = _mesh_ft3(pts, tris)
    m = AP.read_assembly(p)
    assert m.decomposed and m.decomposed[0]["method"] == "boxes"
    assert m.decomposed[0]["exact"] is True and len(m.parts) == 3
    assert _authored_ft3(m) == pytest.approx(mesh, rel=AP.EXACT_REL_TOL)

    real = AP.decompose_boxes

    def short(points, triangles, **kw):
        d = real(points, triangles, **kw)
        d["volume_ft3"] *= 0.999                          # a tenth of a percent off
        return d
    monkeypatch.setattr(AP, "decompose_boxes", short)
    m = AP.read_assembly(p)
    assert not (m.decomposed and m.decomposed[0]["method"] == "boxes")
    assert AP._conserves(_authored_ft3(m), mesh, AP.EXACT_REL_TOL)


def test_ring_nesting_survives_a_shared_vertex():
    """Two solids meeting at a corner SHARE that vertex.  Testing containment
    with rings[i][0] read ring A as a hole in B whenever the stitch happened to
    start A at the shared corner -- and the slab silently lost a member."""
    a = [[1, 1], [-1, 1], [-1, -1], [1, -1]]           # starts AT the shared corner
    b = [[1, 1], [3, 1], [3, 3], [1, 3]]
    assert AP.ring_nesting([a, b]) == [0, 0]
    assert AP.ring_nesting([b, a]) == [0, 0]
    # and a real hole whose first vertex touches nothing is still a hole
    outer = [[0, 0], [10, 0], [10, 10], [0, 10]]
    hole = [[2, 2], [8, 2], [8, 8], [2, 8]]
    assert AP.ring_nesting([hole, outer]) == [1, 0]


def test_the_interior_probe_is_inside_its_ring_and_is_not_a_vertex():
    for ring in ([[0, 0], [4, 0], [4, 1], [0, 1]],
                 [[0, 0], [2, 0], [2, 2], [1, 3], [0, 2]],
                 [[0, 0], [3, 0], [3, 3], [2, 3], [2, 1], [1, 1], [1, 3], [0, 3]]):   # a U
        pt = AP._interior_probe(ring)
        assert AP._point_in_ring(pt, ring)
        assert all(math.hypot(pt[0] - v[0], pt[1] - v[1]) > 1e-9 for v in ring)


def _corner_pair(ox, oy, yaw_deg):
    """A 6 m cube and a 1 x 1 x 2 m member touching it along ONE corner
    edge at (ox, oy), yawed -- 1-based triangles."""
    big_p, big_t = _box_mesh(6.0, 6.0, 6.0)
    small_p, small_t = _box_mesh(1.0, 1.0, 2.0, ox=ox, oy=oy)
    n = len(big_p)
    return (_yaw(list(big_p) + list(small_p), yaw_deg),
            list(big_t) + [(a + n, b + n, c + n) for a, b, c in small_t])


def _triangle_orders(tris, seeds=40):
    """Seeded permutations of the triangle ORDER plus each triangle's start
    vertex.  Which segment the stitch starts from -- and so which vertex was
    the old rings[i][0] -- depends on exactly this; on a3506ad 21 of the 160
    runs below start a ring at the shared corner and lose the member."""
    import random
    yield list(tris)
    for seed in range(seeds):
        rng = random.Random(seed)
        out = [t[s:] + t[:s] for t, s in ((t, rng.randrange(3)) for t in tris)]
        rng.shuffle(out)
        yield out


def test_a_corner_touching_pair_never_loses_its_member(tmp_path):
    """THE OTHER REGRESSION, over triangle orders that DO move the stitch
    start onto the shared corner: the small member -- 0.9 % of the body, so
    inside the 2 % conservation slack -- must never vanish without a word.
    The law: material is conserved or the body is kept as one honest prism
    that says so.  The outcome, now: both solids, always."""
    for ox, oy, yaw_deg in ((-3.5, 3.5, 5.0), (-3.5, 3.5, 12.0), (-3.5, 3.5, 33.0),
                            (-3.5, -3.5, -5.0)):
        pts, base = _corner_pair(ox, oy, yaw_deg)
        mesh = _mesh_ft3(pts, base)                      # order-invariant
        for tris in _triangle_orders(base):
            p = write_ifc(str(tmp_path / "pair.ifc"),
                          [("Pair", "IFCBUILDINGELEMENTPROXY", (pts, tris))])
            m = AP.read_assembly(p)
            authored = _authored_ft3(m)
            assert authored >= mesh * (1.0 - 1e-6) or m.kept_prism, (ox, oy, yaw_deg, len(m.parts))
            assert m.decomposed and len(m.parts) >= 2, (ox, oy, yaw_deg)
            assert authored == pytest.approx(mesh, rel=1e-4)


def test_the_slab_lane_keeps_its_declared_approximations(tmp_path):
    """The slab lane makes no exactness claim: midpoint sections under-integrate
    a taper by a hair, hairline Z levels are skipped, slivers dropped -- all
    inside the 2 % envelope, all better than one fat prism.  A reducer must
    stay a stack and a strut with 50 um of flange mismatch must stay a
    channel (exact boxes unyawed, three slabs yawed), exactly as on main."""
    cases = [("Reducer", _frustum(), None, 8),
             ("Strut0", _strut_mismatch(0.0), "boxes", 3),
             ("Strut12", _strut_mismatch(12.0), "slabs", 3)]
    for name, (pts, tris), method, n_parts in cases:
        p = write_ifc(str(tmp_path / f"{name}.ifc"), [(name, "IFCBUILDINGELEMENTPROXY", (pts, tris))])
        m = AP.read_assembly(p)
        assert not m.kept_prism, (name, m.kept_prism)
        assert m.decomposed and len(m.parts) == n_parts, (name, len(m.parts))
        if method:
            assert m.decomposed[0]["method"] == method, name
            assert m.decomposed[0]["exact"] is (method == "boxes")
        assert _authored_ft3(m) == pytest.approx(_mesh_ft3(pts, tris), rel=2e-3), name


def test_volume_and_area_do_not_lose_precision_at_site_coordinates(tmp_path):
    """The exactness checks compare to 1e-6, so the measurements must be good
    to far better than that wherever the body sits: tetrahedra and shoelaces
    are summed about a LOCAL vertex, not the world origin (at 5 km out the
    origin-based sum was 0.6 % off and every aligned body missed its lane)."""
    # (rel 1e-7, not 1e-9: the INPUT is already quantised -- float spacing at
    # 4.8e6 is ~1e-9, so '+ 0.03' itself carries 3e-8; the sums add nothing)
    pts, tris = _box_mesh(0.02, 0.03, 0.05, ox=5.0e5, oy=4.8e6, oz=300.0)   # UTM-ish
    assert AP.mesh_volume(pts, _tri0(tris)) == pytest.approx(3e-5, rel=1e-7)
    ring = [[5.0e5 + x, 4.8e6 + y] for x, y in ((0, 0), (0.02, 0), (0.02, 0.03), (0, 0.03))]
    assert AP._polygon_area(ring) == pytest.approx(6e-4, rel=1e-7)
    for deg, method in ((0.0, "boxes"), (0.5, "slabs")):
        s_pts, s_tris = _strut(deg)
        p = write_ifc(str(tmp_path / f"far_{deg}.ifc"), [("Strut", "IFCMEMBER", (s_pts, s_tris))],
                      placements={"Strut": (50000.0, 80000.0, 100.0)})
        m = AP.read_assembly(p)
        assert m.decomposed and m.decomposed[0]["method"] == method, deg
        assert len(m.parts) == 3 and not m.kept_prism


def test_the_route_caveat_names_the_lane_that_ran(tmp_path):
    """A box decomposition must not be reported as a slab decomposition: one
    assembly holding an aligned strut and a yawed one names each lane."""
    from rvt.frontdoor import router as R
    p = write_ifc(str(tmp_path / "two.ifc"),
                  [("Aligned", "IFCMEMBER", _strut(0.0)), ("Yawed", "IFCMEMBER", _strut(0.5))],
                  placements={"Yawed": (0.0, 0.5, 0.0)})
    res = R.route({"ifc": p}, "rfa", out=str(tmp_path / "o"), quiet=True)
    assert res.ok and os.path.isfile(res.files["rfa"])
    caveat = next(c for c in res.caveats if "decomposition improved" in c)
    assert "box decomposition improved Aligned" in caveat
    assert "slab decomposition improved Yawed" in caveat


# ---------------------------------------------------------------------------
# eng #620: a yawed thin bar is never a giant cylinder
# ---------------------------------------------------------------------------

def _fit_m(pts_m, tris0):
    """fit_solid on a model-unit mesh, in feet, with its real mesh volume."""
    p = [(x * FT, y * FT, z * FT) for x, y, z in pts_m]
    return AP.fit_solid(p, AP.mesh_volume(p, tris0))


def _strut0(deg):
    """`_strut` with 0-based triangles, for the in-memory fits."""
    pts, tris = _strut(deg)
    return pts, _tri0(tris)


@pytest.mark.parametrize("deg", [5.0, 30.0])
def test_a_yawed_u_channel_is_its_rotated_rectangle_not_a_2m_cylinder(deg):
    """THE REPRO.  Yaw keeps a few near-collinear points on the hull, all of
    them half a diagonal from the centre, and the 4 x 1 m U 'fitted' an
    r = 2.05 m (6.73 ft) cylinder holding 8 % of it.  Its honest single prism
    is the rotated 4 x 1 rectangle: 28 % full, whatever the yaw."""
    pts, tris = _u_channel()
    fit = _fit_m(_yaw(pts, deg), tris)
    assert fit["fit"] == "polygon" and "radius_ft" not in fit
    assert fit["fill"] == pytest.approx(0.28, rel=1e-6)          # 1.12 m3 in 4 m3
    assert fit["fill"] == pytest.approx(_fit_m(pts, tris)["fill"], rel=1e-6)   # = unyawed


@pytest.mark.parametrize("deg", [0.1, 12.0])
def test_a_yawed_strut_is_its_rotated_rectangle_not_an_18in_cylinder(deg):
    """The other repro: 900 x 41 x 41 mm, yawed a tenth of a degree, was an
    r = 1.48 ft cylinder holding 1 % of it."""
    fit = _fit_m(*_strut0(deg))
    assert fit["fit"] == "polygon" and "radius_ft" not in fit
    assert fit["fill"] == pytest.approx(_fit_m(*_strut0(0.0))["fill"], rel=1e-6)
    assert fit["fill"] > 0.17                                     # was 0.0102


def test_no_yaw_of_a_thin_bar_ever_fits_a_cylinder():
    """The law, not the two angles that happened to be reported: at no yaw is
    a fitted circle allowed to reach past the body or to hold an outline that
    does not fill it."""
    u_pts, u_tris = _u_channel()
    for k in range(0, 361):
        deg = k / 4.0                                             # 0 .. 90 by 0.25
        for pts, tris in ((_yaw(u_pts, deg), u_tris), _strut0(deg)):
            fit = _fit_m(pts, tris)
            assert fit["fit"] != "cylinder", (deg, fit.get("radius_ft"))
            assert fit["fill"] > 0.17, (deg, fit["fill"])
            if fit["fit"] == "polygon":                           # the envelope stays inside the body's box
                ext = [fit["bbox"][1][i] - fit["bbox"][0][i] for i in range(2)]
                assert AP._polygon_area(fit["vertices"]) <= ext[0] * ext[1] * (1 + 1e-9)


@pytest.mark.parametrize("sides", [12, 16])
@pytest.mark.parametrize("deg", [0.0, 7.0, 22.5])
def test_a_real_pipe_still_fits_a_cylinder_upright_and_yawed(sides, deg):
    """THE CONTROL.  A 12/16-band tessellated pipe is a cylinder at any yaw,
    with the radius of its bands and a fill of ~1 (the N-gon in its circle)."""
    pts, tris = _prism_mesh(0.05, 1.0, sides)
    fit = _fit_m(_yaw(pts, deg), _tri0(tris))
    assert fit["fit"] == "cylinder"
    assert fit["radius_ft"] == pytest.approx(0.05 * FT, rel=1e-6)
    assert fit["fill"] == pytest.approx(1.0, abs=0.05)
    assert fit["fill"] == pytest.approx(sides / (2 * math.pi) * math.sin(2 * math.pi / sides), rel=1e-6)


def test_a_circle_must_be_the_outline_not_just_equidistant_corners():
    """The two refusals in isolation: a chamfered 2 x 1 bar (8 hull points, all
    one radius out) reaches past its own half-width; a chamfered square does
    not, but fills only 64 % of its circle.  A regular octagon fills 90 % and
    is the coarsest outline that still reads as round."""
    def chamfered(l, w, c=0.02):
        ring = [(-l / 2 + c, -w / 2), (l / 2 - c, -w / 2), (l / 2, -w / 2 + c), (l / 2, w / 2 - c),
                (l / 2 - c, w / 2), (-l / 2 + c, w / 2), (-l / 2, w / 2 - c), (-l / 2, -w / 2 + c)]
        return [(x, y, 0.0) for x, y in ring] + [(x, y, 1.0) for x, y in ring]
    bar, square = chamfered(2.0, 1.0), chamfered(1.0, 1.0)
    octagon, _ = _prism_mesh(1.0, 1.0, 8)
    for deg in (0.0, 20.0, 45.0):
        assert AP.fit_solid(_yaw(bar, deg))["fit"] != "cylinder", deg
        assert AP.fit_solid(_yaw(square, deg))["fit"] != "cylinder", deg
        assert AP.fit_solid(_yaw(octagon, deg))["fit"] == "cylinder", deg


def test_with_the_lanes_off_the_delivered_envelope_is_the_prism_not_the_cylinder(tmp_path):
    """When no decomposition runs (or both lanes refuse), the single prism IS
    what ships.  For the U at 4 deg -- a yaw that mis-fits through the IFC
    path on e621ab6 (r = 6.73 ft) -- that is now its rotated rectangle."""
    pts, tris = _u_channel()
    yawed, one = _yaw(pts, 4.0), [(a + 1, b + 1, c + 1) for a, b, c in tris]
    p = write_ifc(str(tmp_path / "u4.ifc"), [("U", "IFCMEMBER", (yawed, one))])
    m = AP.read_assembly(p, decompose=False)
    assert len(m.parts) == 1 and m.parts[0].fit == "polygon"
    assert m.parts[0].radius_ft is None
    assert m.parts[0].fill == pytest.approx(0.28, rel=1e-4)          # %.6f STEP text
    assert m.fit_counts() == {"polygon": 1}
    # and with the lanes on, the slab lane still authors it exactly, as before
    m = AP.read_assembly(p)
    assert m.decomposed and m.decomposed[0]["method"] == "slabs" and not m.kept_prism
    assert _authored_ft3(m) == pytest.approx(_mesh_ft3(yawed, one), rel=1e-4)


def _plate_tower(deg, n=70, length=2.0, width=0.10, step=0.01):
    """A 2 m x 100 mm rail built of `n` stacked 10 mm plates whose width
    alternates by 2 mm, yawed: more Z levels than MAX_SLABS (the slab lane
    refuses on budget) and not axis-aligned (no box lane) -- so the single
    prism is what ships.  1-based triangles."""
    pts, tris = [], []
    for k in range(n):
        p, t = _box_mesh(length, width if k % 2 == 0 else width - 0.002, step, oz=k * step)
        b = len(pts)
        pts += list(p)
        tris += [(a + b, b2 + b, c + b) for a, b2, c in t]
    return _yaw(pts, deg), tris


def test_when_both_lanes_refuse_the_shipped_solid_is_the_rail_not_a_1m_drum(tmp_path):
    """End to end, the case the lanes do NOT rescue.  On e621ab6 this rail,
    yawed 10 deg, shipped as ONE cylinder of r = 3.28 ft (a 2 m drum for a
    100 mm rail, 6 % full, wider than the body's own bounding box) because the
    slab lane was over budget and the kept prism was that cylinder.  Now the
    kept prism is the rail's rotated rectangle, 99 % full -- so full that no
    decomposition is even attempted."""
    assert 70 > AP.MAX_SLABS                                     # the premise
    pts, tris = _plate_tower(10.0)
    p = write_ifc(str(tmp_path / "rail.ifc"), [("Rail", "IFCMEMBER", (pts, tris))])
    m = AP.read_assembly(p)
    assert len(m.parts) == 1
    rail = m.parts[0]
    assert rail.fit == "polygon" and rail.radius_ft is None
    assert rail.fill == pytest.approx(0.99, abs=0.002)           # half the plates are 98 mm
    assert not m.kept_prism and not m.decomposed                 # nothing to rescue any more
    ext = [rail.bbox_ft[1][i] - rail.bbox_ft[0][i] for i in range(2)]
    assert AP._polygon_area(rail.vertices_ft) <= ext[0] * ext[1]  # inside its own box, unlike r = 3.28 ft
    assert m.fit_counts() == {"polygon": 1}


# ---------------------------------------------------------------------------
# --target-version across the archetype -> assembly hand-off (#564)
# ---------------------------------------------------------------------------

def _one_box(tmp_path):
    return write_ifc(str(tmp_path / "one.ifc"),
                     [("Plate", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 1.0, 0.1))])


@pytest.mark.parametrize("year", [2025, 2024])
def test_a_single_product_ifc_is_emitted_at_the_target_release(tmp_path, year):
    """ONE box fails the archetype lane INSIDE its Revit-N release context (a
    box carries no downlight housing) and again natively; that dead lane's
    'fallback' story must not leak into the assembly lane, which makes its
    own attempt at Revit N -- and a box emits there.  Red on 152d009: the
    .rfa detected as 2026 under a caveat blaming a lane that produced nothing."""
    from rvt import versions as V
    from rvt.frontdoor import router as R
    res = R.route({"ifc": _one_box(tmp_path)}, "rfa", out=str(tmp_path / "o"),
                  quiet=True, target_version=year)
    assert res.ok, res.errors + [res.status]
    assert res.releases["rfa"] == year == V.detect_release(res.files["rfa"])
    assert res.target_version["status"] == "match"
    assert res.target_version["output_release"] == year
    assert not any("cannot run at Revit" in c for c in res.caveats)   # the dead lane's line is gone
    assert "ifc" not in res.files                 # no version-agnostic IFC beside a MATCH
    assert "ASSEMBLY lane" in res.status and "facts->rfa" in res.status   # who built it, who failed
    assert any("measured-archetype lane did not apply" in c for c in res.caveats)


def test_a_single_product_ifc_without_a_target_stays_native(tmp_path):
    from rvt.frontdoor import release_ctx as RC
    from rvt.frontdoor import router as R
    res = R.route({"ifc": _one_box(tmp_path)}, "rfa", out=str(tmp_path / "o"), quiet=True)
    assert res.ok, res.errors + [res.status]
    assert res.releases["rfa"] == RC.native_release()
    assert res.target_version["status"] == "unspecified"


def test_a_two_product_ifc_at_2025_stays_2025(tmp_path):
    """The case that was already right (the archetype lane fails at ifc->facts,
    BEFORE any release context) must stay right."""
    from rvt import versions as V
    from rvt.frontdoor import router as R
    p = write_ifc(str(tmp_path / "two.ifc"), [
        ("Plate", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 1.0, 0.1)),
        ("Post A", "IFCMEMBER", _prism_mesh(0.05, 1.0, 24, ox=-0.4, oz=0.1)),
    ])
    res = R.route({"ifc": p}, "rfa", out=str(tmp_path / "o"), quiet=True, target_version=2025)
    assert res.ok, res.errors + [res.status]
    assert res.releases["rfa"] == 2025 == V.detect_release(res.files["rfa"])
    assert res.target_version["status"] == "match"
    assert "ifc->facts" in res.status


# ---------------------------------------------------------------------------
# eng #625: on the assembly lane's GENUINE fallback the source IFC rides beside
# the delivered .rfa (the archetype lane already did this; the famspec-only
# lane has no IFC and keeps saying so)
# ---------------------------------------------------------------------------

def _two_products(tmp_path):
    return write_ifc(str(tmp_path / "two.ifc"), [
        ("Plate", "IFCBUILDINGELEMENTPROXY", _box_mesh(1.0, 1.0, 0.1)),
        ("Post A", "IFCMEMBER", _prism_mesh(0.05, 1.0, 24, ox=-0.4, oz=0.1)),
    ])


def _cannot_run_below_native(monkeypatch):
    """Guarantee the degrade this test observes: the famspec constructor
    refuses inside any non-native release context (today the 24-gon post's
    arc sketch already does at 2024 -- no ArcElemCell port, #241; the guard
    keeps the test about the IFC-beside-the-fallback plumbing once that closes)."""
    from rvt.frontdoor import release_ctx as RC
    from rvt.frontdoor import router as R
    real = R.FS.build

    def build(kind, kw, **k):
        if RC.active_release() is not None:
            raise KeyError(f"simulated: no port for this family at Revit {RC.active_release()}")
        return real(kind, kw, **k)
    monkeypatch.setattr(R.FS, "build", build)


@pytest.mark.parametrize("year", [2024, 2023])
def test_an_assembly_fallback_carries_the_source_ifc_beside_the_rfa(tmp_path, monkeypatch, year):
    """two.ifc at a year the emit cannot serve (2024: the lane degrades inside
    the release context; 2023: no certified base, the resolver's fallback):
    the .rfa is DELIVERED native (rule 1), the block says `fallback`, and --
    red on 55cc977 -- the IFC the user supplied is copied beside it, named in
    `files['ifc']` / `ifc_addition`, and the line keeps its 'IFC alongside'
    clause instead of claiming 'no IFC rides beside a FAMILY request'."""
    from rvt import versions as V
    from rvt.frontdoor import release_ctx as RC
    from rvt.frontdoor import router as R
    if year == 2024:
        _cannot_run_below_native(monkeypatch)
    src = _two_products(tmp_path)
    out = tmp_path / "o"
    res = R.route({"ifc": src}, "rfa", out=str(out), quiet=True, target_version=year)
    assert res.ok, res.errors + [res.status]
    native = RC.native_release()
    assert res.releases["rfa"] == native == V.detect_release(res.files["rfa"])
    tv = res.target_version
    assert tv["requested"] == year and tv["status"] == "fallback"
    assert tv["output_release"] == native
    ifc = res.files["ifc"]                                   # the addition rides beside the .rfa
    assert os.path.dirname(os.path.abspath(ifc)) == os.path.abspath(str(out))
    assert os.path.basename(ifc) == "two.ifc"
    with open(ifc, "rb") as a, open(src, "rb") as b:
        assert a.read() == b.read()                          # the input verbatim, nothing authored
    assert str(tv["ifc_addition"]).endswith("two.ifc")
    assert "input IFC" in tv["ifc_addition_source"]
    line = tv["line"]
    assert f"target {year} requested" in line and "cannot open it" in line
    assert "IFC alongside is version-agnostic" in line and "no IFC rides" not in line
    assert res.caveats.count(line) == 1                      # stated once, after delivery
    assert "ASSEMBLY lane" in res.status


def test_an_assembly_match_copies_no_ifc_and_says_nothing_extra(tmp_path):
    """The forwarded source IFC only matters on a fallback: two.ifc at 2025
    matches, so no IFC role, no addition, no version line."""
    from rvt import versions as V
    from rvt.frontdoor import router as R
    out = tmp_path / "o"
    res = R.route({"ifc": _two_products(tmp_path)}, "rfa", out=str(out), quiet=True,
                  target_version=2025)
    assert res.ok, res.errors + [res.status]
    assert res.releases["rfa"] == 2025 == V.detect_release(res.files["rfa"])
    tv = res.target_version
    assert tv["status"] == "match" and not tv.get("line") and not tv.get("ifc_addition")
    assert "ifc" not in res.files
    assert "two.ifc" not in os.listdir(str(out))
    assert not any("IFC alongside" in c or "no IFC rides" in c for c in res.caveats)


def test_a_famspec_only_fallback_still_says_no_ifc_rides(tmp_path):
    """rfa -> rfa from a famspec has no IFC to forward: at an uncertified year
    the family is delivered native and the line keeps today's honest clause.
    (test_router pins the same on a catalog kind; this is the catalog-free
    generic_model pin, beside the lane it contrasts with.)"""
    from rvt.frontdoor import release_ctx as RC
    from rvt.frontdoor import router as R
    spec = {"kind": "generic_model", "name": "Crate",
            "parts": [{"shape": "box", "width_ft": 2.0, "depth_ft": 1.5, "height_ft": 1.0,
                       "name": "body"}]}
    out = tmp_path / "o"
    res = R.route({"rfa": spec}, "rfa", out=str(out), quiet=True, target_version=2023)
    assert res.ok and os.path.isfile(res.files["rfa"]), res.errors + [res.status]
    assert res.releases["rfa"] == RC.native_release()
    tv = res.target_version
    assert tv["status"] == "fallback" and not tv.get("ifc_addition")
    assert "ifc" not in res.files
    assert not any(n.endswith(".ifc") for n in os.listdir(str(out)))
    line = tv["line"]
    assert "cannot open it" in line and "IFC alongside" not in line and "no IFC rides" in line


# ---------------------------------------------------------------------------
# eng #621: two members sharing a FACE never lose the smaller one -- nesting
# is never judged from ON the other ring's boundary
# ---------------------------------------------------------------------------

def _face_pair(big, lug, off, yaw_deg):
    """A ``big`` = (w, d, h) m block on the origin and a ``lug`` = (w, d, h)
    block at ``off`` = (ox, oy, oz) with one lug face lying IN a block face
    (coplanar and overlapping -- not merely a corner line), yawed about Z.
    Two shells, 1-based triangles, coordinates rounded to the micron exactly
    as ``write_ifc``'s ``%.6f`` keeps them (so a mesh volume computed here IS
    the volume of the file's mesh)."""
    big_p, big_t = _box_mesh(*big)
    lug_p, lug_t = _box_mesh(*lug, ox=off[0], oy=off[1], oz=off[2])
    n = len(big_p)
    pts = _yaw(list(big_p) + list(lug_p), yaw_deg)
    return ([tuple(round(c, 6) for c in p) for p in pts],
            list(big_t) + [(a + n, b + n, c + n) for a, b, c in lug_t])


#: (block, lug, lug offset, yaw): a 1 x 4 x 4 m upright slab carrying a 0.5 m
#: cube stud, and a 2 x 6 x 3 m block carrying a 0.5 x 1 x 0.5 m lug -- studs
#: and lugs of 0.7-0.8 % of the body, so the 2 % conservation slack could not
#: see them go.  Every row loses the small member on dcda26e (main before this
#: fix) in 17 to 41 of its 41 triangle orders: 140 silent losses in 205 runs,
#: each authoring 0.9922-0.9931 of the mesh with no kept_prism and no caveat.
_FACE_PAIRS = [
    ((1.0, 4.0, 4.0), (0.5, 0.5, 0.5), (0.75, 0.0, 0.0), 5.0),        # stud at the base, mid-face
    ((1.0, 4.0, 4.0), (0.5, 0.5, 0.5), (-0.75, 0.0, 1.024), -5.0),    # stud up the other face
    ((1.0, 4.0, 4.0), (0.5, 0.5, 0.5), (0.75, -0.75, 1.75), 20.0),    # off-centre, mid-height
    ((2.0, 6.0, 3.0), (0.5, 1.0, 0.5), (-1.25, 0.969, 1.25), 12.0),   # lug half-way up the -x face
    ((2.0, 6.0, 3.0), (0.5, 1.0, 0.5), (1.25, -1.668, 1.024), 12.0),  # lug on the +x face
]


def test_ring_nesting_survives_a_shared_edge():
    """Two shells sharing a face slice into two rings sharing an EDGE, each
    written with its own rounding.  When the small ring's copy of that edge
    lands a micron INSIDE the big ring and the probe hugs it, the small SOLID
    ring read as a hole.  Containment is now judged from a probe standing
    clear of the other ring -- and either way round the answer is: two
    solids, side by side."""
    big = [[0, 0], [10, 0], [10, 10], [0, 10]]
    for dx in (-2e-6, 0.0, 2e-6):                       # inside big / exactly on it / outside
        x = 10.0 + dx
        lug = [[x, 5], [x, 4], [10.5, 4], [10.5, 5]]      # starts with the shared edge, its longest
        assert AP.ring_nesting([lug, big]) == [0, 0], dx
        assert AP.ring_nesting([big, lug]) == [0, 0], dx
        assert AP.ring_nesting([lug[2:] + lug[:2], big]) == [0, 0], dx
    # a hole is still a hole -- also one hugging the outer ring closer than
    # MIN_EXTENT_FT along its longest side (the probe moves to another edge)
    hole = [[0.0005, 8], [0.0005, 2], [5, 2], [5, 8]]
    assert AP.ring_nesting([hole, big]) == [1, 0]
    assert AP.ring_nesting([big, hole]) == [0, 1]
    island = [[1, 4], [1, 3], [2, 3], [2, 4]]             # solid inside that hole
    assert sorted(AP.ring_nesting([island, hole, big])) == [0, 1, 2]


def test_interior_probes_are_one_per_edge_longest_first_and_never_a_vertex():
    ring = [[0, 0], [4, 0], [4, 1], [3, 1], [3, 3], [0, 3]]          # an L
    probes = list(AP._interior_probes(ring))
    assert len(probes) == len(ring)
    assert probes[0] == AP._interior_probe(ring)                    # the primary is unchanged
    assert 0 < probes[0][1] < 1e-5                                  # just inside the 4-long base
    for pt in probes:
        assert AP._point_in_ring(pt, ring)
        assert all(math.hypot(pt[0] - v[0], pt[1] - v[1]) > 1e-9 for v in ring)
    # a zero-area sliver has no inside: its first vertex, as before
    assert list(AP._interior_probes([[0, 0], [1, 0], [2, 0]])) == [(0.0, 0.0)]


def test_a_probe_on_the_other_boundary_is_never_the_one_asked():
    big = [[0, 0], [10, 0], [10, 10], [0, 10]]
    lug = [[10 - 2e-6, 5], [10 - 2e-6, 4], [10.5, 4], [10.5, 5]]
    gen = AP._interior_probes(lug)
    found = [next(gen)]
    assert AP._clearance(found[0], big) < AP.MIN_EXTENT_FT             # the primary hugs big's edge
    probe = AP._probe_clear_of(big, gen, found)
    assert AP._clearance(probe, big) >= AP.MIN_EXTENT_FT and AP._point_in_ring(probe, lug)
    assert not AP._point_in_ring(probe, big)
    assert len(found) >= 2 and found[0] != probe                       # drawn lazily, cached
    # no edge clear of the other ring (a duplicated shell): the first probe answers
    gen = AP._interior_probes(big)
    found = [next(gen)]
    assert AP._probe_clear_of(big, gen, found) == found[0]


def test_a_face_sharing_pair_never_loses_its_member(tmp_path):
    """THE REGRESSION (present on main since the slab lane existed): a stud or
    lug whose face lies IN a bigger member's face vanished without a word --
    authored volume 0.7 % under the mesh, no kept_prism, no caveat -- in the
    triangle orders that start the small ring on the shared edge with the
    rounding falling inward.  Over 205 seeded orders of five such pairs: the
    material is conserved (or the body is honestly kept as one prism), and in
    fact every run decomposes into the block's slabs plus the member."""
    runs = 0
    for big, lug, off, yaw in _FACE_PAIRS:
        pts, base = _face_pair(big, lug, off, yaw)
        mesh = _mesh_ft3(pts, base)                          # order-invariant
        lug_share = (lug[0] * lug[1] * lug[2]) / (big[0] * big[1] * big[2] + lug[0] * lug[1] * lug[2])
        assert lug_share < 0.02                              # the premise: inside _conserves' slack
        for tris in _triangle_orders(base):
            p = write_ifc(str(tmp_path / "pair.ifc"), [("Pair", "IFCBUILDINGELEMENTPROXY", (pts, tris))])
            m = AP.read_assembly(p)
            authored = _authored_ft3(m)
            runs += 1
            assert authored >= mesh * (1.0 - 1e-6) or m.kept_prism, (big, off, yaw, len(m.parts), authored / mesh)
            assert m.decomposed and m.decomposed[0]["method"] == "slabs", (big, off, yaw)
            assert m.decomposed[0]["holes_filled"] == 0, (big, off, yaw)
            assert len(m.parts) >= 3, (big, off, yaw, len(m.parts))   # block below/above + block & member
            assert authored == pytest.approx(mesh, rel=1e-5), (big, off, yaw)
    assert runs == 41 * len(_FACE_PAIRS)


def test_face_sharing_at_zero_yaw_is_still_the_exact_box_lane(tmp_path):
    """Control: unyawed, the same pairs are axis-aligned polyhedra and take
    the box lane exactly (block + member = 2 boxes) -- untouched by this fix."""
    for big, lug, off, _yaw_unused in (_FACE_PAIRS[0], _FACE_PAIRS[3]):
        pts, base = _face_pair(big, lug, off, 0.0)
        p = write_ifc(str(tmp_path / "pair0.ifc"), [("Pair", "IFCBUILDINGELEMENTPROXY", (pts, base))])
        m = AP.read_assembly(p)
        assert m.decomposed and m.decomposed[0]["method"] == "boxes" and m.decomposed[0]["exact"]
        assert len(m.parts) == 2 and not m.kept_prism
        assert _authored_ft3(m) == pytest.approx(_mesh_ft3(pts, base), rel=AP.EXACT_REL_TOL)


def test_a_flush_face_pair_is_kept_as_one_honest_prism_not_lost(tmp_path):
    """The neighbouring case this fix does NOT change, pinned so nobody
    mistakes it for a regression: a lug FLUSH with the block's edge shares a
    corner line as well as a face, its ring meets the block's at a junction
    with two COINCIDENT spokes, `_junction_pairs` cannot pair those from the
    material alone and refuses the slice -- so the body is delivered as one
    prism that says so (rule 1), on main and here alike, at every triangle
    order.  Never a silent loss; #634 owns resolving it."""
    big, lug = (2.0, 6.0, 3.0), (0.5, 1.0, 0.5)
    for off, yaw in (((-1.25, 2.5, 1.25), 12.0), ((1.25, 2.5, 0.0), 33.0)):   # lug's +y face flush with the block's
        pts, base = _face_pair(big, lug, off, yaw)
        mesh = _mesh_ft3(pts, base)
        for tris in _triangle_orders(base, seeds=10):
            p = write_ifc(str(tmp_path / "flush.ifc"), [("Flush", "IFCBUILDINGELEMENTPROXY", (pts, tris))])
            m = AP.read_assembly(p)
            assert m.kept_prism and "ambiguous slice" in m.kept_prism[0]["reason"], (off, yaw)
            assert len(m.parts) == 1 and _authored_ft3(m) > mesh

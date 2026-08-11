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

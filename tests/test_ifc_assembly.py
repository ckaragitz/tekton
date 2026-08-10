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
    parts = AP.assembly_parts(p)
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


def test_slice_returns_none_when_the_section_is_ambiguous():
    """Two boxes touching at exactly one point: the segments alone do not
    determine the rings, so the slice must refuse rather than guess."""
    p1, t1 = _box_mesh(1.0, 1.0, 2.0, ox=-0.5, oy=-0.5)
    p2, t2 = _box_mesh(1.0, 1.0, 2.0, ox=0.5, oy=0.5)
    pts = list(p1) + list(p2)
    tris = _tri0(t1) + [(a - 1 + len(p1), b - 1 + len(p1), c - 1 + len(p1))
                        for a, b, c in t2]
    assert AP.slice_loops(pts, tris, 1.0) is None


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

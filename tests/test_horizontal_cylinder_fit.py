"""#766 -- the assembly lane fits TRUE lying cylinders, not box staircases.

The engine has authored true horizontal cylinders since #591 round 4
(cylinder_x / cylinder_y, the rotated cached B-rep) but nothing ever FIT
them: the plan projection of a horizontal tube is a rectangle, so every
wheel, roller and tube shipped as boxes.
"""
import math

import pytest

from rvt.ifc.assembly_parts import PartSolid, fit_solid


def _tube(axis, r=0.25, L=3.0, cz=1.0, n=24):
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        for t in (0.0, L):
            if axis == "y":
                pts.append((r * math.cos(a), t, cz + r * math.sin(a)))
            elif axis == "x":
                pts.append((t, r * math.cos(a), cz + r * math.sin(a)))
            else:
                pts.append((r * math.cos(a), r * math.sin(a), t))
    return pts


@pytest.mark.parametrize("axis,fit", [("y", "cylinder_y"), ("x", "cylinder_x")])
def test_a_lying_tube_fits_a_true_cylinder(axis, fit):
    r, L = 0.25, 3.0
    f = fit_solid(_tube(axis, r, L), math.pi * r * r * L)
    assert f["fit"] == fit
    assert abs(f["radius_ft"] - r) < 0.01
    assert abs(f["length_ft"] - L) < 1e-6
    # underside and vertical extent follow the circle, not the bbox
    assert abs(f["base_z_ft"] - (1.0 - r)) < 0.01
    assert abs(f["height_ft"] - 2 * r) < 0.02
    assert abs((f["fill"] or 0) - 1.0) < 0.05


def test_a_vertical_cylinder_still_fits_vertically():
    r, L = 0.25, 3.0
    f = fit_solid(_tube("z", r, L), math.pi * r * r * L)
    assert f["fit"] == "cylinder"


def test_the_620_law_survives_sideways():
    # a long thin bar's side hull has equidistant CORNERS; it must stay a
    # box, exactly as the plan fit already guarantees (#620)
    bar = [(x, y, z) for x in (0, 4.0) for y in (0, 0.15) for z in (0, 0.15)]
    assert fit_solid(bar, 4.0 * 0.15 * 0.15)["fit"] == "box"


def test_a_yawed_tube_is_not_guessed():
    # axis-aligned only (#628): a tube at 45 degrees in plan must never come
    # back as an axis cylinder
    r, L, c, s = 0.25, 3.0, math.cos(math.pi / 4), math.sin(math.pi / 4)
    pts = []
    for k in range(24):
        a = 2 * math.pi * k / 24
        u, z = r * math.cos(a), 1.0 + r * math.sin(a)
        for t in (0.0, L):
            pts.append((t * c - u * s, t * s + u * c, z))
    f = fit_solid(pts, math.pi * r * r * L)
    assert not f["fit"].startswith("cylinder_")


def test_a_wafer_is_not_a_lying_cylinder():
    # a disc standing on edge but only paper-long along the axis
    f = fit_solid(_tube("y", r=0.5, L=0.002), math.pi * 0.25 * 0.002)
    assert not f["fit"].startswith("cylinder_")


def test_part_solid_emits_the_rotated_cylinder_contract():
    p = PartSolid(name="axle", ifc_class="IfcBuildingElementProxy", tag="",
                  guid="", fit="cylinder_y", center_ft=(1.0, 2.0),
                  height_ft=0.5, base_z_ft=0.75, radius_ft=0.25, length_ft=3.0)
    d = p.to_part()
    assert d["shape"] == "cylinder_y"
    assert d["radius_ft"] == 0.25 and d["length_ft"] == 3.0
    assert d["center"] == [1.0, 2.0] and d["base_z_ft"] == 0.75
    assert "length_ft" in p.to_json() or p.to_json().get("length_ft") == 3.0


# ---------------------------------------------------------------------------
# the lathe lane (#766 round 2): stepped true cylinders, not slab staircases
# ---------------------------------------------------------------------------

from rvt.ifc.assembly_parts import decompose_lathe


def _closed_cyl_y(r, y0, y1, cx=0.0, cz=1.0, n=24, pts=None, tris=None):
    pts = [] if pts is None else pts
    tris = [] if tris is None else tris
    b = len(pts)
    for y in (y0, y1):
        for k in range(n):
            a = 2 * math.pi * k / n
            pts.append((cx + r * math.cos(a), y, cz + r * math.sin(a)))
    pts.append((cx, y0, cz))
    pts.append((cx, y1, cz))
    c0, c1 = b + 2 * n, b + 2 * n + 1
    for k in range(n):
        k2 = (k + 1) % n
        tris.append((b + k, b + k2, b + n + k))
        tris.append((b + k2, b + n + k2, b + n + k))
        tris.append((c0, b + k2, b + k))
        tris.append((c1, b + n + k, b + n + k2))
    return pts, tris


def test_a_stepped_shaft_becomes_coaxial_true_cylinders():
    pts, tris = _closed_cyl_y(0.5, 0.0, 0.3)
    pts, tris = _closed_cyl_y(0.15, 0.3, 2.7, pts=pts, tris=tris)
    d = decompose_lathe(pts, tris, "y")
    assert d is not None
    shapes = [(p["shape"], round(p["radius_ft"], 2), round(p["length_ft"], 2))
              for p in d["parts"]]
    assert shapes == [("cylinder_y", 0.5, 0.3), ("cylinder_y", 0.15, 2.4)]
    # every segment sits on the shared axis: base_z = axis_z - r
    for p in d["parts"]:
        assert abs((p["base_z_ft"] + p["radius_ft"]) - 1.0) < 0.01
        assert abs(p["center"][0]) < 0.01
    assert d["authored_volume_ft3"] > 0


def test_an_offset_boss_refuses_the_lane():
    pts, tris = _closed_cyl_y(0.5, 0.0, 0.3)
    pts, tris = _closed_cyl_y(0.15, 0.3, 2.7, cz=1.6, pts=pts, tris=tris)
    why = []
    assert decompose_lathe(pts, tris, "y", refusal=why) is None
    assert any("not coaxial" in w for w in why)


def test_a_square_section_refuses_the_lane():
    bx = [(x, y, z) for x in (0, 1) for y in (0, 2) for z in (0, 1)]
    bt = [(0, 1, 3), (0, 3, 2), (4, 7, 5), (4, 6, 7), (0, 5, 1), (0, 4, 5),
          (2, 3, 7), (2, 7, 6), (0, 2, 6), (0, 6, 4), (1, 5, 7), (1, 7, 3)]
    why = []
    assert decompose_lathe(bx, bt, "y", refusal=why) is None
    assert any("not a circle" in w or "not a body of revolution" in w
               for w in why)


def test_unknown_axis_refuses():
    why = []
    assert decompose_lathe([(0, 0, 0)], [], "z", refusal=why) is None
    assert why

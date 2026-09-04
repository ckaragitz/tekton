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

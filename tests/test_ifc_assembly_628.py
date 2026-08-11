"""`fit_solid`'s circle / no-circle verdict is the SAME at every yaw (#628).

Law (b) of ``_fit_circle`` used to bound the fitted radius by the smaller
half-extent of the WORLD bounding box, which grows toward the half-diagonal
as a body turns: a 1 x 1 square with 0.2 chamfers (plan fill 0.861,
r / apothem 1.166) was its octagon facing north and a cylinder at 10 / 22.5 /
30 / 45 degrees; a two-flat shaft flipped the same way.  The bound is now half
the hull's own minimum caliper width, a property of the outline alone.

Own module per the #636 convention (fixture generators come from
``tests/test_ifc_assembly.py``, which is not appended to); in-memory meshes and
synthesised IFC4 text only -- no ``samples/``, no ifcopenshell.

Territory: ifc-assembly stream, issue #628.
"""
from __future__ import annotations

import math

import pytest

from rvt.ifc import assembly_parts as AP
from test_ifc_assembly import _fit_m, _prism_mesh, _tri0, _u_channel, _yaw, write_ifc, FT

SWEEP = [k * 2.5 for k in range(37)]                       # 0 .. 90 deg by 2.5


def _chamfered(l, w, c):
    """An l x w bar with 45-degree chamfers of leg c: 8 hull points (model
    units) -- the ring #620's refusal test builds inline, at module level."""
    ring = [(-l / 2 + c, -w / 2), (l / 2 - c, -w / 2), (l / 2, -w / 2 + c), (l / 2, w / 2 - c),
            (l / 2 - c, w / 2), (-l / 2 + c, w / 2), (-l / 2, w / 2 - c), (-l / 2, -w / 2 + c)]
    return [(x, y, 0.0) for x, y in ring] + [(x, y, 1.0) for x, y in ring]


def _double_d(r=0.5, flat=0.4, sides=64):
    """A round shaft with two parallel flats `flat` from its axis: fills 90 %
    of its circle, yet the circle is 25 % wider than the flats."""
    h = math.sqrt(r * r - flat * flat)
    ring = [(r * math.cos(a), r * math.sin(a))
            for a in (2 * math.pi * i / sides for i in range(sides))
            if abs(r * math.cos(a)) <= flat]
    ring += [(flat, -h), (flat, h), (-flat, h), (-flat, -h)]
    return [(x, y, 0.0) for x, y in ring] + [(x, y, 1.0) for x, y in ring]


def _tube(r_out=0.05, r_in=0.044, h=1.0, sides=32):
    """A hollow pipe wall as a closed mesh (0-based triangles): outer skin,
    bore, and the two annular ends."""
    def ring(r, z):
        return [(r * math.cos(2 * math.pi * i / sides), r * math.sin(2 * math.pi * i / sides), z)
                for i in range(sides)]
    pts = ring(r_out, 0.0) + ring(r_out, h) + ring(r_in, 0.0) + ring(r_in, h)
    ob, ot, ib, it = 0, sides, 2 * sides, 3 * sides
    tris = []
    for i in range(sides):
        j = (i + 1) % sides
        tris += [(ob + i, ob + j, ot + j), (ob + i, ot + j, ot + i)]          # outer skin
        tris += [(ib + i, it + j, ib + j), (ib + i, it + i, it + j)]          # bore (inward)
        tris += [(ob + i, ib + j, ob + j), (ob + i, ib + i, ib + j)]          # bottom annulus
        tris += [(ot + i, ot + j, it + j), (ot + i, it + j, it + i)]          # top annulus
    return pts, tris


def _fit_pts(pts_m, deg, off=(0.0, 0.0)):
    """fit_solid on bare points (no mesh volume), yawed, in feet."""
    return AP.fit_solid([(x * FT + off[0], y * FT + off[1], z * FT) for x, y, z in _yaw(pts_m, deg)])


def _fit_mesh(pts_m, tris0, deg):
    """fit_solid on a closed mesh with its real volume, yawed, in feet."""
    return _fit_m(_yaw(pts_m, deg), tris0)


def _brute_width(hull):
    """The oracle: for every edge, its farthest vertex; the least of those."""
    n = len(hull)
    best = float("inf")
    for i in range(n):
        (ax, ay), (bx, by) = hull[i], hull[(i + 1) % n]
        e = math.hypot(bx - ax, by - ay)
        if e > 0:
            best = min(best, max(abs((bx - ax) * (py - ay) - (by - ay) * (px - ax))
                                 for px, py in hull) / e)
    return best


# ---------------------------------------------------------------------------
# the helper: minimum caliper width is a property of the outline
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("n", [3, 4, 5, 8, 9, 12, 64])
def test_a_regular_polygons_width_is_its_textbook_value(n):
    """Even N: flat to flat, 2 R cos(pi/N).  Odd N: vertex to flat, R (1 + cos(pi/N)).
    (The hull welds vertices to 1e-9, hence the tolerance.)"""
    hull = AP.convex_hull_2d([(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n))
                              for i in range(n)])
    expected = 2 * math.cos(math.pi / n) if n % 2 == 0 else 1 + math.cos(math.pi / n)
    assert AP._min_caliper_width(hull) == pytest.approx(expected, rel=1e-8)


def test_width_does_not_turn_with_the_body_the_bounding_box_does():
    """The whole point: a 2 x 1 rectangle is 1 wide at every yaw, while its
    world bounding box's smaller side runs from 1 up to 2.12 at 45 degrees."""
    rect = [(-1.0, -0.5), (1.0, -0.5), (1.0, 0.5), (-1.0, 0.5)]
    for deg in SWEEP:
        turned = [(x, y) for x, y, _ in _yaw([(x, y, 0.0) for x, y in rect], deg)]
        hull = AP.convex_hull_2d(turned)
        assert AP._min_caliper_width(hull) == pytest.approx(1.0, rel=1e-9), deg
    box45 = [(x, y) for x, y, _ in _yaw([(x, y, 0.0) for x, y in rect], 45.0)]
    assert min(max(v[i] for v in box45) - min(v[i] for v in box45) for i in (0, 1)) > 2.1


def test_the_two_pointer_walk_agrees_with_brute_force_on_noisy_yawed_hulls():
    """The walk relies on the farthest vertex only moving forward; check it
    against the O(n^2) oracle on the hulls this lane really sees -- yawed thin
    bars whose rounding noise keeps near-collinear points, a fine tessellation,
    and the same outlines a million feet from the origin."""
    bodies = [_u_channel()[0], _u_channel(0.9, 0.041, 0.041, 0.0025)[0],
              _prism_mesh(0.05, 1.0, 120)[0], _chamfered(1.0, 1.0, 0.2), _double_d()]
    checked = 0
    for pts in bodies:
        for off in ((0.0, 0.0), (1.0e6, -2.0e6)):
            for deg in SWEEP[::3]:
                plan = [(x * FT + off[0], y * FT + off[1]) for x, y, _ in _yaw(pts, deg)]
                for q in (plan, [(round(x, 6), round(y, 6)) for x, y in plan]):   # + the STEP %.6f path
                    hull = AP.convex_hull_2d(q)
                    assert AP._min_caliper_width(hull) == pytest.approx(_brute_width(hull), rel=1e-9), (deg, off)
                    checked += 1
    assert checked == 5 * 2 * len(SWEEP[::3]) * 2
    assert AP._min_caliper_width([[0.0, 0.0], [1.0, 1.0]]) == 0.0                # not a ring
    assert AP._min_caliper_width([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0]]) == 0.0    # collinear


# ---------------------------------------------------------------------------
# the verdict: one answer per body, whatever the yaw
# ---------------------------------------------------------------------------

def test_the_chamfered_square_in_the_band_is_its_octagon_at_every_yaw():
    """THE REPRO.  c = 0.2 on a 1 x 1 square: fill 0.861 passes the floor, and
    r = 0.583 is 16.6 % over the half-width across the square's own flats --
    over the 12 % a real tessellation needs -- so it is the polygon.  On
    dcda26e it was that polygon at 0 degrees only and a cylinder from ~5 on."""
    square = _chamfered(1.0, 1.0, 0.2)
    fits = {deg: _fit_pts(square, deg) for deg in SWEEP}
    assert {f["fit"] for f in fits.values()} == {"polygon"}, {d: f["fit"] for d, f in fits.items()}
    for deg in (0.0, 10.0, 22.5, 30.0, 45.0):                  # the issue's five yaws, by name
        assert "radius_ft" not in fits[deg] and len(fits[deg]["vertices"]) == 8, deg


@pytest.mark.parametrize("c, expected", [
    (0.15, "polygon"),      # fill 0.816: refused by the plan-fill floor at any yaw (as before)
    (0.18, "polygon"),      # fill 0.845: still the floor's refusal, just under it
    (0.22, "polygon"),      # fill 0.876 passes; r 14.6 % over the flats: law (b) alone decides
    (0.27, "cylinder"),     # r 10.1 % over the flats -- inside what an 8-gon needs
    (0.29, "cylinder"),     # all but the regular octagon (c = 0.2929)
])
def test_chamfers_straddling_the_band_each_get_one_verdict_for_all_yaws(c, expected):
    body = _chamfered(1.0, 1.0, c)
    kinds = {deg: _fit_pts(body, deg)["fit"] for deg in SWEEP}
    assert set(kinds.values()) == {expected}, (c, kinds)


def test_a_two_flat_shaft_is_never_round_whichever_way_its_flats_face():
    """The body law (b) exists for: 90 % plan fill, every hull point on the
    circle, yet the circle is 25 % wider than the flats.  dcda26e: polygon
    with the flats facing X or Y, cylinder from ~15 degrees on."""
    shaft = _double_d()
    kinds = {deg: _fit_pts(shaft, deg)["fit"] for deg in SWEEP}
    assert set(kinds.values()) == {"polygon"}, kinds


def test_site_coordinates_do_not_change_the_verdict():
    square, shaft, rod = _chamfered(1.0, 1.0, 0.2), _double_d(), _double_d(0.5, 0.5, 48)
    for deg in (0.0, 22.5, 45.0):
        for off in ((0.0, 0.0), (1.0e6, -2.0e6)):
            assert _fit_pts(square, deg, off)["fit"] == "polygon", (deg, off)
            assert _fit_pts(shaft, deg, off)["fit"] == "polygon", (deg, off)
            assert _fit_pts(rod, deg, off)["fit"] == "cylinder", (deg, off)


# ---------------------------------------------------------------------------
# #620's repros and controls, unchanged
# ---------------------------------------------------------------------------

def test_the_620_bars_are_still_prisms_at_every_yaw():
    u_pts, u_tris = _u_channel()
    s_pts, s_tris = _u_channel(0.9, 0.041, 0.041, 0.0025)      # the 900 mm strut
    for deg in SWEEP:
        for pts, tris, fill in ((u_pts, u_tris, 0.28), (s_pts, s_tris, 0.1755)):
            fit = _fit_mesh(pts, tris, deg)
            assert fit["fit"] != "cylinder", (deg, fit.get("radius_ft"))
            assert fit["fit"] == ("box" if deg in (0.0, 90.0) else "polygon"), deg
            assert fit["fill"] == pytest.approx(fill, rel=2e-3), (deg, fit["fill"])


@pytest.mark.parametrize("sides", [12, 16])
def test_the_control_pipe_is_a_cylinder_at_every_yaw(sides):
    pts, tris = _prism_mesh(0.05, 1.0, sides)
    for deg in SWEEP:
        fit = _fit_mesh(pts, _tri0(tris), deg)
        assert fit["fit"] == "cylinder", deg
        assert fit["radius_ft"] == pytest.approx(0.05 * FT, rel=1e-6), deg
        assert fit["fill"] == pytest.approx(sides / (2 * math.pi) * math.sin(2 * math.pi / sides), rel=1e-6)


def test_a_hollow_tube_is_a_true_cylinder_holding_a_fifth_of_its_envelope():
    """Why no law reads the mesh volume: a thin-wall tube IS a cylinder at
    12-25 % occupancy, and stays one at any yaw."""
    pts, tris = _tube()
    for deg in (0.0, 7.0, 22.5, 45.0):
        fit = _fit_mesh(pts, tris, deg)
        assert fit["fit"] == "cylinder", deg
        assert fit["radius_ft"] == pytest.approx(0.05 * FT, rel=1e-6)
        assert 0.12 < fit["fill"] < 0.25, fit["fill"]


@pytest.mark.parametrize("n", [8, 9, 10, 12, 24, 64])
def test_regular_polygons_from_the_octagon_up_are_cylinders_at_every_yaw(n):
    """A regular 8-gon's circumradius is 8.2 % over its apothem (= half its
    minimum width), a 9-gon's 3.1 %: every real tessellation clears 12 %."""
    pts, tris = _prism_mesh(1.0, 1.0, n)
    for deg in (0.0, 5.0, 11.25, 22.5, 30.0):
        assert _fit_mesh(pts, _tri0(tris), deg)["fit"] == "cylinder", (n, deg)


# ---------------------------------------------------------------------------
# through the IFC path: the delivered part does not depend on site north
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("deg", [0.0, 22.5])
def test_the_routed_chamfered_square_is_the_same_octagon_facing_any_way(tmp_path, deg):
    square = _chamfered(1.0, 1.0, 0.2)
    tris = _prism_mesh(1.0, 1.0, 8)[1]          # an 8-ring prism's triangulation is index-only
    p = write_ifc(str(tmp_path / f"square_yaw{round(deg)}.ifc"),
                  [("Plinth", "IFCMEMBER", (_yaw(square, deg), tris))])
    m = AP.read_assembly(p)
    assert len(m.parts) == 1, [q.fit for q in m.parts]
    part = m.parts[0]
    assert part.fit == "polygon" and part.radius_ft is None
    assert len(part.vertices_ft) == 8
    assert AP._polygon_area(part.vertices_ft) == pytest.approx(0.92 * FT * FT, rel=1e-4)   # 1 - 4 chamfers
    assert m.fit_counts() == {"polygon": 1}

"""A member SUNK into a block never vanishes: slice rings that CROSS are one
outline before anything is nested (#637).

Two shells that interpenetrate -- a lug pushed a centimetre or five into a
block, an embedded plate, a bar run through a post -- slice into two rings
that cross.  Neither nests in the other, so ``ring_nesting``'s probe answered
"a hole" or "a solid" by which edge of the lug it happened to stand beside,
and in the hole case the member disappeared inside ``_conserves``' 2 % slack:
on ``main`` @ 6f33fb7, 338 of 1476 seeded runs of the sunk pairs below
authored 0.9922-0.9931 of the mesh with no ``kept_prism`` and no caveat (and
204 more kept the whole body as a prism because the BLOCK's ring read as the
hole).  Now the crossing pair is cut at its crossings, the boundary pieces
inside the other ring are dropped -- only where the body itself reads two
overlapping shells -- and the rest is welded into the union's outline; the
material the mesh counts twice there is credited to the conservation law the
way the box lane credits its overlap.  Contact (a shared corner, #609; a
shared face, #621) is not a crossing and is untouched, which the reference
rows re-measure.

Own module per the #636 convention (fixture generators are imported from
``tests/test_ifc_assembly.py`` / ``_623`` / ``_628``, never copied; nothing is
appended to those files); synthesised IFC4 text and in-memory rings only --
no ``samples/``, no ifcopenshell: runs on a fresh clone.

Territory: ifc-assembly stream, issue #637.
"""
from __future__ import annotations

import math
import os

import pytest

from rvt.ifc import assembly_parts as AP
from test_ifc_assembly import (_authored_ft3, _box_mesh, _corner_pair, _face_pair, _FACE_PAIRS,
                               _frustum, _mesh_ft3, _prism_mesh, _strut, _strut_mismatch,
                               _tri0, _triangle_orders, _u_channel, _yaw, write_ifc, FT)
from test_ifc_assembly_623 import _lattice
from test_ifc_assembly_628 import _chamfered, _tube

FT3 = FT ** 3
BOTH = lambda x, y: True                      # noqa: E731 -- "the body holds two shells here"
NEITHER = lambda x, y: False                  # noqa: E731

BIG = [[0, 0], [10, 0], [10, 10], [0, 10]]


def _shells(bodies, yaw_deg, flip_last=False):
    """Several ``_box_mesh``-style (pts, 1-based tris) shells as ONE product,
    yawed about Z and rounded to the micron exactly as ``write_ifc`` keeps
    them (so a volume computed here IS the file's).  ``flip_last`` winds the
    last shell the other way -- an exporter defect the merge must refuse."""
    pts, tris = [], []
    for k, (p, t) in enumerate(bodies):
        n = len(pts)
        pts += list(p)
        tt = [(a + n, b + n, c + n) for a, b, c in t]
        if flip_last and k == len(bodies) - 1:
            tt = [(a, c, b) for a, b, c in tt]
        tris += tt
    return [tuple(round(c, 6) for c in q) for q in _yaw(pts, yaw_deg)], tris


def _read(tmp_path, pts, tris, name="Pair"):
    p = write_ifc(str(tmp_path / "b.ifc"), [(name, "IFCBUILDINGELEMENTPROXY", (pts, tris))])
    return AP.read_assembly(p)


# ---------------------------------------------------------------------------
# the plan-geometry law: crossings are proper, contact is not a crossing, the
# union is checked against the body and must close
# ---------------------------------------------------------------------------

def test_ring_cuts_are_proper_crossings_and_nothing_else():
    lug = [[9, 4], [12, 4], [12, 5], [9, 5]]                        # 1 unit into BIG
    cuts = AP._ring_cuts(BIG, lug)
    assert sorted(pt for *_, pt in cuts) == [(10.0, 4.0), (10.0, 5.0)]
    assert all(0.0 < t < 1.0 and 0.0 < u < 1.0 for _, t, _, u, _ in cuts)
    corner = [[10, 10], [12, 10], [12, 12], [10, 12]]                # #609: a shared corner
    face = [[10, 4], [12, 4], [12, 5], [10, 5]]                      # #621: a shared edge, exactly
    hole = [[2, 2], [8, 2], [8, 8], [2, 8]]                          # nested
    apart = [[20, 0], [21, 0], [21, 1], [20, 1]]
    for other in (corner, face, hole, apart):
        assert AP._ring_cuts(BIG, other) == [] and AP._ring_cuts(other, BIG) == [], other


def test_the_union_of_two_crossing_rings_is_their_outline_and_their_shared_area():
    lug = [[9, 4], [12, 4], [12, 5], [9, 5]]
    for a, b in ((BIG, lug), (lug, BIG)):
        rings, shared = AP._union_of_crossing(a, b, AP._ring_cuts(a, b), BOTH)
        assert len(rings) == 1 and len(rings[0]) == 8
        assert AP._polygon_area(rings[0]) == pytest.approx(102.0)     # 100 + 3 - 1
        assert shared == pytest.approx(1.0)                            # counted twice by the mesh
    # a plus: no vertex of either bar lies inside the other, yet they cross
    h = [[-3, -1], [3, -1], [3, 1], [-3, 1]]
    v = [[-1, -3], [1, -3], [1, 3], [-1, 3]]
    rings, shared = AP._union_of_crossing(h, v, AP._ring_cuts(h, v), BOTH)
    assert len(rings) == 1 and len(rings[0]) == 12
    assert AP._polygon_area(rings[0]) == pytest.approx(20.0) and shared == pytest.approx(4.0)
    # a bar closing a C: the union has a POCKET, which comes back as its own
    # ring (nested later as the hole it is) and is not part of the shared area
    C = [[0, 0], [10, 0], [10, 2], [2, 2], [2, 8], [10, 8], [10, 10], [0, 10]]
    bar = [[8, 1], [12, 1], [12, 9], [8, 9]]
    rings, shared = AP._union_of_crossing(C, bar, AP._ring_cuts(C, bar), BOTH)
    assert sorted(AP._polygon_area(r) for r in rings) == pytest.approx([36.0, 116.0])
    assert shared == pytest.approx(4.0)                                 # 52 + 32 - (116 - 36)
    assert sorted(AP.ring_nesting(rings)) == [0, 1]


def test_contact_is_not_a_crossing_and_is_left_to_ring_nesting():
    """#621's shared edge, written with each shell's own rounding: the lug's
    edge lands microns inside the block at a hair of an angle, so its edges DO
    cut the block's -- but neither boundary reaches MIN_EXTENT_FT into the
    other.  That is contact: no merge, both rings exactly as they were."""
    lug = [[10 - 2e-6, 4], [12, 4], [12, 5], [10 + 1e-6, 5]]
    assert AP._ring_cuts(BIG, lug)                                       # the premise: cuts exist
    assert AP._union_of_crossing(BIG, lug, AP._ring_cuts(BIG, lug), BOTH) == ([], 0.0)
    rings, merged, shared = AP._merge_crossing_rings([lug, BIG], BOTH)
    assert merged == 0 and shared == 0.0 and rings == [lug, [list(map(float, v)) for v in BIG]]
    assert AP.ring_nesting(rings) == [0, 0]                              # and #621's law still answers
    # just past the feature floor it IS a crossing (the depth _probe_clear_of
    # starts trusting a probe beside the buried edge is where this takes over)
    sunk = [[10 - 2 * AP.MIN_EXTENT_FT, 4], [12, 4], [12, 5], [10 - 2 * AP.MIN_EXTENT_FT, 5]]
    rings, merged, shared = AP._merge_crossing_rings([sunk, BIG], BOTH)
    assert merged == 1 and len(rings) == 1 and shared == pytest.approx(2 * AP.MIN_EXTENT_FT)


def test_a_merge_the_body_does_not_back_is_refused_not_guessed():
    lug = [[9, 4], [12, 4], [12, 5], [9, 5]]
    cuts = AP._ring_cuts(BIG, lug)
    # the dropped boundary must lie where TWO shells overlap -- a ring bounding
    # a hole, or a shell wound the other way, does not, and is never merged away
    assert AP._union_of_crossing(BIG, lug, cuts, NEITHER) is None
    assert AP._merge_crossing_rings([BIG, lug], NEITHER) is None
    # kept pieces that do not close (an edge of one ring lying ON the other's,
    # exactly) are not an outline: refused
    flush = [[9, 5], [12, 5], [12, 10], [9, 10]]
    assert AP._ring_cuts(BIG, flush)
    assert AP._union_of_crossing(BIG, flush, AP._ring_cuts(BIG, flush), BOTH) is None
    # nothing crossing: nothing to do, whatever the body would have said
    hole = [[2, 2], [8, 2], [8, 8], [2, 8]]
    assert AP._merge_crossing_rings([BIG, hole], NEITHER) == (
        [[list(map(float, v)) for v in BIG], [list(map(float, v)) for v in hole]], 0, 0.0)


def test_several_rings_crossing_one_are_all_merged():
    left = [[-2, 4], [1, 4], [1, 5], [-2, 5]]
    right = [[9, 4], [12, 4], [12, 5], [9, 5]]
    rings, merged, shared = AP._merge_crossing_rings([left, BIG, right], BOTH)
    assert merged == 2 and len(rings) == 1 and len(rings[0]) == 12
    assert AP._polygon_area(rings[0]) == pytest.approx(104.0) and shared == pytest.approx(2.0)


def test_the_shared_area_is_net_of_rings_swallowed_whole_on_the_bodys_word():
    """A plate slotted through a pipe crosses the SKIN and swallows the BORE
    whole: the bore is one shell deep (the plate), so it is not shared
    material -- ``area(a) + area(b) - area(union)`` alone credited it (the
    #713 review's probe: 8 % of the mesh).  Every ring enclosed in the common
    region is asked at its own probe; a bore subtracts itself, an island of
    two shells inside that bore adds itself back, a third shell changes
    nothing -- and nothing enclosed means nothing to correct."""
    plate = [[-2, 3], [12, 3], [12, 7], [-2, 7]]                 # through BIG, 10 x 4 = 40 shared as discs
    bore = [[4, 4], [6, 4], [6, 6], [4, 6]]                       # BIG's own hole, under the plate: area 4
    rod = [[4.5, 4.5], [5.5, 4.5], [5.5, 5.5], [4.5, 5.5]]       # a second shell down that bore: area 1
    beside = [[20, 20], [21, 20], [21, 21], [20, 21]]             # not enclosed: never asked

    def body(x, y):                                               # doubled everywhere but in the empty bore
        in_bore = 4 < x < 6 and 4 < y < 6
        in_rod = 4.5 < x < 5.5 and 4.5 < y < 5.5
        return (not in_bore) or in_rod

    assert AP._enclosed_correction(BIG, plate, [], body) == 0.0
    assert AP._enclosed_correction(BIG, plate, [beside], NEITHER) == 0.0
    assert AP._enclosed_correction(BIG, plate, [bore], body) == pytest.approx(-4.0)
    assert AP._enclosed_correction(BIG, plate, [rod, bore, beside], body) == pytest.approx(-3.0)
    assert AP._enclosed_correction(BIG, plate, [bore], BOTH) == 0.0     # a third shell's ring: no change
    rings, merged, shared = AP._merge_crossing_rings([bore, BIG, plate, rod], body)
    assert merged == 1 and shared == pytest.approx(40.0 - 4.0 + 1.0)
    assert len(rings) == 3                                             # bore and rod ride along, un-merged


# ---------------------------------------------------------------------------
# the slab lane: a sunk member is conserved at every triangle order
# ---------------------------------------------------------------------------

#: (block, lug, sink into the +x face (m), lug y / z offset, yaw): the #621
#: face pairs pushed INTO the block.  On main @ 6f33fb7 each row's outcome is
#: triangle-order roulette between two wrongs -- the member silently LOST
#: (lug ring read as a hole) or its buried part authored TWICE (both rings
#: solid) -- plus, for the base stud, the whole body kept as a prism when the
#: SLAB read as the hole.  Per row over its 41 orders: 0 lost / 41 doubled
#: (the issue's named placement, 2 cm at -17 deg, on this generator);
#: 41 lost; 41 lost; 24 lost + 17 prisms; 24 doubled + 17 prisms.
_SUNK = [
    ((2.0, 6.0, 3.0), (0.5, 1.0, 0.5), 0.02, (-1.668, 1.024), -17.0),   # the issue's named placement
    ((2.0, 6.0, 3.0), (0.5, 1.0, 0.5), 0.01, (-1.668, 1.024), 12.0),    # 41/41 silent losses on main
    ((2.0, 6.0, 3.0), (0.5, 1.0, 0.5), 0.05, (-1.668, 1.024), 5.0),     # 41/41 silent losses on main
    ((1.0, 4.0, 4.0), (0.5, 0.5, 0.5), 0.01, (0.0, 0.0), 12.0),          # stud at the base
    ((1.0, 4.0, 4.0), (0.5, 0.5, 0.5), 0.05, (0.0, 0.0), 33.0),
]


def _sunk(big, lug, sink, off, yaw):
    pts, tris = _face_pair(big, lug, (big[0] / 2.0 + lug[0] / 2.0 - sink, off[0], off[1]), yaw)
    union_ft3 = (big[0] * big[1] * big[2] + lug[0] * lug[1] * lug[2] - sink * lug[1] * lug[2]) * FT3
    return pts, tris, union_ft3


def test_decompose_slabs_merges_the_crossing_and_reports_what_the_mesh_counts_twice():
    big, lug, sink, off, yaw = _SUNK[0]
    pts, tris, union = _sunk(big, lug, sink, off, yaw)
    why = []
    dec = AP.decompose_slabs([(x * FT, y * FT, z * FT) for x, y, z in pts], _tri0(tris), refusal=why)
    assert dec is not None and why == []
    assert dec["crossings_merged"] == 1 and dec["holes_filled"] == 0
    assert dec["overlap_ft3"] == pytest.approx(sink * lug[1] * lug[2] * FT3, rel=1e-4)
    assert dec["volume_ft3"] == pytest.approx(union, rel=1e-5)              # the union, not the sum
    below, band, above = (AP._polygon_area(p["vertices"]) for p in dec["parts"])   # block / outline / block
    assert below == pytest.approx(big[0] * big[1] * FT * FT, rel=1e-6) == above     # the block's own ring, twice
    assert band - below == pytest.approx((lug[0] - sink) * lug[1] * FT * FT, rel=1e-5)  # + exactly the part standing proud


def test_a_sunk_member_is_conserved_at_every_triangle_order(tmp_path):
    """THE REGRESSION.  Judged against the exact UNION volume (the mesh's own
    volume counts the buried part of the lug twice): every run decomposes,
    merges the crossing, fills no hole, and authors the union to 1e-5 --
    never less, and never the double-counted sum either."""
    runs = 0
    for row, seeds in zip(_SUNK, (100, 40, 40, 40, 40)):
        pts, base, union = _sunk(*row)
        mesh = _mesh_ft3(pts, base)
        assert 0.0 < (mesh - union) / mesh < 0.02                            # the premise: inside the slack
        for tris in _triangle_orders(base, seeds=seeds):
            m = _read(tmp_path, pts, tris)
            authored = _authored_ft3(m)
            runs += 1
            assert authored >= union * (1.0 - 1e-6) or m.kept_prism, (row, len(m.parts), authored / union)
            assert m.decomposed and not m.kept_prism, (row, m.kept_prism)
            d = m.decomposed[0]
            assert d["method"] == "slabs" and d["crossings_merged"] >= 1 and d["holes_filled"] == 0, (row, d)
            assert d["fill_after"] <= 1.0 and d["mesh_overlap_in3"] > 0.0, (row, d)
            assert authored == pytest.approx(union, rel=1e-5), row
            assert len(m.parts) == (3 if row[3][1] else 2), (row, len(m.parts))
    assert runs == 101 + 4 * 41
    assert any("crossing section(s) merged" in n for n in m.notes)             # said, for the router to relay


def test_interpenetration_beyond_the_slack_is_credited_on_the_bodys_evidence_not_refused(tmp_path):
    """A bar run clean THROUGH a post, two equal bars crossing, two lugs in
    one band: the shells share far more than 2 % of the mesh.  The union is
    still the body; what the mesh counts twice is credited (it was checked
    against the body when merged), so these decompose instead of falling to
    one prism -- and never author the shared material twice."""
    cases = [
        ("bar through post", [_box_mesh(2, 2, 2), _box_mesh(3.0, 0.4, 0.4, oz=0.8)], 12.0,
         8 + 0.48 - 0.32, 3, 1),
        ("equal bars crossing", [_box_mesh(3.0, 0.4, 0.4), _box_mesh(0.4, 3.0, 0.4)], 20.0,
         0.96 - 0.064, 1, 1),
        ("two lugs, one band", [_box_mesh(2, 6, 3), _box_mesh(0.5, 1.0, 0.5, ox=1.23, oy=-1.668, oz=1.024),
                                _box_mesh(0.5, 1.0, 0.5, ox=-1.23, oy=0.969, oz=1.024)], 12.0,
         36.5 - 0.02, 3, 2),
        ("lugs crossing each other too", [_box_mesh(2, 6, 3), _box_mesh(0.6, 1.0, 0.5, ox=1.2, oz=1.0),
                                          _box_mesh(1.0, 0.3, 0.3, ox=1.3, oy=0.3, oz=1.1)], 12.0,
         None, 5, 4),
    ]
    for name, bodies, yaw, union_m3, n_parts, n_merged in cases:
        pts, base = _shells(bodies, yaw)
        for tris in _triangle_orders(base, seeds=6):
            m = _read(tmp_path, pts, tris, name)
            assert m.decomposed and not m.kept_prism, (name, m.kept_prism)
            d = m.decomposed[0]
            assert d["crossings_merged"] == n_merged and len(m.parts) == n_parts, (name, d)
            assert d["fill_after"] == pytest.approx(1.0, abs=1e-3), (name, d)
            if union_m3 is not None:
                assert _authored_ft3(m) == pytest.approx(union_m3 * FT3, rel=1e-5), name
    # the plus really is a plus: ONE outline holding both bars less their shared square
    pts, base = _shells(cases[1][1], cases[1][2])
    m = _read(tmp_path, pts, base)
    assert len(m.parts) == 1 and m.parts[0].fit == "polygon"
    assert AP._polygon_area(m.parts[0].vertices_ft) == pytest.approx((2 * 3.0 * 0.4 - 0.16) * FT * FT, rel=1e-5)


def test_a_curved_member_and_a_hollow_one_merge_too(tmp_path):
    # a 16-gon boss straddling a plate's edge: the crossing ring is not a box
    pts, base = _shells([_box_mesh(2.0, 2.0, 0.2), _prism_mesh(0.05, 1.0, 16, ox=0.98, oz=0.05)], 12.0)
    m = _read(tmp_path, pts, base)
    assert m.decomposed and m.decomposed[0]["crossings_merged"] == 1 and len(m.parts) == 3
    # a radial pin sunk into a tube's WALL: merged; the bore is a hole and is
    # filled, as every hole is (holes_filled counts it below / in / above the pin)
    tp, tt = _tube(r_out=0.5, r_in=0.3, h=1.0, sides=32)
    pts, base = _shells([(tp, [(a + 1, b + 1, c + 1) for a, b, c in tt]),
                         _box_mesh(0.3, 0.1, 0.1, ox=0.55, oz=0.45)], 12.0)
    m = _read(tmp_path, pts, base)
    d = m.decomposed[0]
    assert d["crossings_merged"] == 1 and d["holes_filled"] == 3 and len(m.parts) == 3


def test_a_plate_slotted_through_a_pipe_credits_the_wall_it_crosses_never_the_bore_it_swallows(tmp_path):
    """The #713 review's body: a 1.4 x 0.7 x 0.2 m plate through a 32-gon pipe
    (r 0.5, bore 0.3) -- wider than the bore, narrower than the skin, so it
    crosses the OUTER ring only and the bore ring lies whole inside it.  The
    credit is (|skin & plate| - |bore|) x plate height, read from the body;
    with a 16-gon rod down the bore the rod's section is two shells deep
    again and comes back: (|skin & plate| - |bore| + |rod|) x height."""
    tp, tt = _tube(r_out=0.5, r_in=0.3, h=1.0, sides=32)
    tube = (tp, [(a + 1, b + 1, c + 1) for a, b, c in tt])
    skin = [[0.5 * math.cos(2 * math.pi * i / 32), 0.5 * math.sin(2 * math.pi * i / 32)] for i in range(32)]
    rect = [[-0.7, -0.35], [0.7, -0.35], [0.7, 0.35], [-0.7, 0.35]]
    _rings, cap = AP._union_of_crossing(skin, rect, AP._ring_cuts(skin, rect), BOTH)   # |skin & plate|, m2
    bore = 0.5 * 32 * 0.3 ** 2 * math.sin(2 * math.pi / 32)
    rod = 0.5 * 16 * 0.1 ** 2 * math.sin(2 * math.pi / 16)
    for bodies, doubled_m3, n_parts in (
            ([tube, _box_mesh(1.4, 0.7, 0.2, oz=0.4)], (cap - bore) * 0.2, 3),
            ([tube, _box_mesh(1.4, 0.7, 0.2, oz=0.4), _prism_mesh(0.1, 1.0, 16)], (cap - bore + rod) * 0.2, 6)):
        pts, base = _shells(bodies, 12.0)
        mesh = _mesh_ft3(pts, base)
        for tris in _triangle_orders(base, seeds=6):
            m = _read(tmp_path, pts, tris, "PlatePipe")
            assert m.decomposed and not m.kept_prism
            d = m.decomposed[0]
            assert d["crossings_merged"] == 1 and d["holes_filled"] == 3 and len(m.parts) == n_parts
            assert d["mesh_overlap_in3"] / 1728.0 == pytest.approx(doubled_m3 * FT3, rel=1e-5)
            assert d["fill_after"] == pytest.approx((mesh - doubled_m3 * FT3) / _authored_ft3(m), rel=1e-4)


def test_a_crossing_the_body_does_not_back_keeps_the_honest_prism_and_says_where(tmp_path):
    """Two things the merge refuses rather than guess, each ATTRIBUTED and
    delivered as the single prism (rule 1): a shell wound the other way (the
    dropped boundary does not read as two overlapping shells), and a pin
    driven through a tube wall into its BORE (the deepest dropped boundary
    lies in the void)."""
    blk, lug = _box_mesh(2, 6, 3), _box_mesh(0.5, 1.0, 0.5, ox=1.23, oy=-1.668, oz=1.024)
    pts, base = _shells([blk, lug], 12.0, flip_last=True)
    why = []
    assert AP.decompose_slabs([(x * FT, y * FT, z * FT) for x, y, z in pts], _tri0(base), refusal=why) is None
    assert len(why) == 1 and why[0].startswith("crossing rings at z = ")
    m = _read(tmp_path, pts, base)
    assert len(m.parts) == 1 and len(m.kept_prism) == 1
    reason = m.kept_prism[0]["reason"]
    assert reason.startswith("box lane: not axis-aligned (") and ", then slab lane: crossing rings at z = " in reason
    tp, tt = _tube(r_out=0.5, r_in=0.3, h=1.0, sides=32)
    pts, base = _shells([(tp, [(a + 1, b + 1, c + 1) for a, b, c in tt]),
                         _box_mesh(0.5, 0.1, 0.1, ox=0.45, oz=0.45)], 12.0)      # 0.1 into the bore
    m = _read(tmp_path, pts, base)
    assert len(m.parts) == 1 and "slab lane: crossing rings at z = " in m.kept_prism[0]["reason"]


def test_the_merge_holds_at_site_coordinates(tmp_path):
    """Decomposition runs before recentre, i.e. wherever the body sits; the
    probe that asks the body 'two shells here?' is 1e-7 ft off a boundary."""
    big, lug, sink, off, yaw = _SUNK[0]
    pts, base, union = _sunk(big, lug, sink, off, yaw)
    for place in ((500.0, 300.0, 10.0), (50000.0, 80000.0, 100.0), (5.0e5, 4.8e6, 300.0)):
        p = write_ifc(str(tmp_path / "far.ifc"), [("Far", "IFCBUILDINGELEMENTPROXY", (pts, base))],
                      placements={"Far": place})
        m = AP.read_assembly(p)
        assert m.decomposed and m.decomposed[0]["crossings_merged"] == 1 and len(m.parts) == 3, place
        assert _authored_ft3(m) == pytest.approx(union, rel=1e-5), place


def test_the_router_delivers_the_sunk_pair_and_says_what_it_merged(tmp_path):
    from rvt.frontdoor import router as R
    big, lug, sink, off, yaw = _SUNK[0]
    pts, base, _ = _sunk(big, lug, sink, off, yaw)
    p = write_ifc(str(tmp_path / "sunk.ifc"), [("Pair", "IFCBUILDINGELEMENTPROXY", (pts, base))])
    res = R.route({"ifc": p}, "rfa", out=str(tmp_path / "o"), quiet=True)
    assert res.ok and os.path.isfile(res.files["rfa"])
    assert res.status.startswith("OK (3-part generic_model .rfa")
    assert any("slab decomposition improved Pair (3 solids, fill 0.88 -> 1.00)" in c for c in res.caveats)
    assert any("1 crossing section(s) merged (Pair: 1," in c and "INTERPENETRATE" in c for c in res.caveats)
    assert not any("kept as a single prism" in c for c in res.caveats)


# ---------------------------------------------------------------------------
# reference rows: everything contact / taper / hairline / budget / fit related
# reads EXACTLY as on main @ 6f33fb7 (parts, lane, authored / mesh)
# ---------------------------------------------------------------------------

def _row(tmp_path, pts, tris, klass="IFCBUILDINGELEMENTPROXY"):
    p = write_ifc(str(tmp_path / "ref.ifc"), [("Ref", klass, (pts, tris))])
    m = AP.read_assembly(p)
    lane = m.decomposed[0]["method"] if m.decomposed else ("kept" if m.kept_prism else "prism")
    return len(m.parts), lane, round(_authored_ft3(m) / _mesh_ft3(pts, tris), 6)


def test_reference_rows_read_exactly_as_on_main(tmp_path):
    up, ut = _u_channel()
    ut1 = [(a + 1, b + 1, c + 1) for a, b, c in ut]
    ch = _chamfered(1.0, 1.0, 0.2)
    n = len(ch) // 2
    ch_t = [t for i in range(n) for t in ((i + 1, (i + 1) % n + 1, (i + 1) % n + 1 + n),
                                          (i + 1, (i + 1) % n + 1 + n, i + 1 + n))]
    ch_t += [t for i in range(1, n - 1) for t in ((1, i + 2, i + 1), (1 + n, 1 + n + i, 2 + n + i))]
    rows = [
        ("900 mm strut 0.0", _strut(0.0), (3, "boxes", 1.0)),
        ("900 mm strut 0.1", _strut(0.1), (3, "slabs", 1.000002)),
        ("900 mm strut 0.2", _strut(0.2), (3, "slabs", 1.000006)),
        ("900 mm strut 0.5", _strut(0.5), (3, "slabs", 1.000022)),
        ("900 mm strut 0.8", _strut(0.8), (3, "slabs", 1.000064)),
        ("50 um mismatch strut 0", _strut_mismatch(0.0), (3, "boxes", 1.0)),
        ("50 um mismatch strut 12", _strut_mismatch(12.0), (3, "slabs", 0.999622)),
        ("8-band reducer frustum", _frustum(), (8, "slabs", 0.999442)),
        ("12-band cone", _frustum(r0=0.10, r1=0.005, bands=12), (12, "slabs", 0.998513)),
        ("U-channel 4", (_yaw(up, 4.0), ut1), (3, "slabs", 0.999997)),
        ("U-channel 30", (_yaw(up, 30.0), ut1), (3, "slabs", 1.000003)),
        ("chamfered square 22.5 (#628)", (_yaw(ch, 22.5), ch_t), (1, "prism", 1.000001)),
        ("lattice 3x3x3 (#623)", _lattice(3), (27, "boxes", 1.0)),
        ("flush lug 12 (#634)", _face_pair((2.0, 6.0, 3.0), (0.5, 1.0, 0.5), (-1.25, 2.5, 1.25), 12.0),
         (1, "kept", 1.137931)),
    ]
    for name, (pts, tris), expect in rows:
        got = _row(tmp_path, pts, tris)
        assert got[:2] == expect[:2] and got[2] == pytest.approx(expect[2], abs=1.5e-6), (name, got, expect)
    # the plate with a 6 mm2 pin: the pin's ring is a sliver and is DROPPED, as before
    p1, t1 = _box_mesh(0.30, 0.20, 0.035)
    side = math.sqrt(6e-6)
    pts, tris = _shells([(p1, t1), _box_mesh(side, side, 0.02, ox=0.05, oy=0.03, oz=0.035)], 7.0)
    m = _read(tmp_path, pts, tris)
    assert len(m.parts) == 1 and m.decomposed[0]["slivers_dropped"] == 1
    assert m.decomposed[0].get("crossings_merged", 0) == 0


def test_corner_and_face_contact_pairs_read_exactly_as_on_main(tmp_path):
    """#609's corner pairs (4 positions x 6 yaws x 41 orders) and #621's five
    face pairs (x 41 orders): contact, never a crossing -- slabs every run,
    no merge, no hole, authored = mesh as before (max off 1.5e-7 / 7.6e-11)."""
    runs = 0
    corner = [(_corner_pair(ox, oy, y), 2e-7) for ox, oy in ((-3.5, 3.5), (-3.5, -3.5), (3.5, 3.5), (3.5, -3.5))
              for y in (5.0, 12.0, 33.0, -5.0, 45.0, 0.05)]
    face = [(_face_pair(*row), 1e-9) for row in _FACE_PAIRS]
    for (pts, base), tol in corner + face:
        mesh = _mesh_ft3(pts, base)
        for tris in _triangle_orders(base):
            m = _read(tmp_path, pts, tris)
            runs += 1
            d = m.decomposed[0]
            assert d["method"] == "slabs" and d["holes_filled"] == 0 and not m.kept_prism
            assert d.get("crossings_merged", 0) == 0 and "mesh_overlap_in3" not in d
            assert len(m.parts) in (3, 4) and abs(_authored_ft3(m) - mesh) / mesh <= tol
    assert runs == (24 + 5) * 41

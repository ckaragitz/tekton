"""eng #634 -- a member FLUSH with another member's edge decomposes into its
slabs; the two coincident spokes at the shared slice vertex no longer cost
the whole body its decomposition.

Two shells in contact whose rings meet at ONE welded slice vertex with two
COINCIDENT spokes -- a lug whose side face lies in the block's end face, or
two touching faces whose triangulation diagonals cross at the slab's height
-- made :func:`_junction_pairs` probe a zero-width wedge ON the doubled face,
refuse the junction, and ship the body as one honest prism (pinned that way
by #621, filed as #634).  :func:`_stitch_bands` now stitches such a slice one
shell band at a time (segments grouped by the mesh edges they were cut from),
only where the welded stitch refused; touching bands' rings then share an
edge or a corner, which #609 / #621 already nest safely.

Every fixture is SYNTHESISED IFC4 text (generators imported from
``tests/test_ifc_assembly.py`` and ``tests/test_ifc_assembly_637.py``, not
edited); the volume / area / containment ORACLE below is this module's own
arithmetic, never an engine function.  ``python tests/test_ifc_assembly_634.py
<named|random|contact|reference|timing> ...`` re-runs the record's sweeps
(docs/inbox/ifc-assembly-rfa.d/634-flush-junction.md) against whichever
engine is first on ``sys.path``.

Territory: ifc-assembly stream (#634).
"""
from __future__ import annotations

import math
import os
import sys
from collections import Counter, defaultdict

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rvt.ifc import assembly_parts as AP                              # noqa: E402
from test_ifc_assembly import (_box_mesh, _corner_pair, _face_pair, _FACE_PAIRS, _frustum,   # noqa: E402
                               _strut, _strut_mismatch, _triangle_orders, _u_channel, _yaw,
                               write_ifc, FT)
from test_ifc_assembly_623 import _dup_lug, _lattice                  # noqa: E402
from test_ifc_assembly_637 import _shells                             # noqa: E402

FT3 = FT ** 3


# ---------------------------------------------------------------------------
# the independent oracle: shoelace, tetrahedra, even-odd -- this module's own
# ---------------------------------------------------------------------------

def _area(ring):
    n = len(ring)
    ox, oy = ring[0][0], ring[0][1]
    return abs(sum((ring[i][0] - ox) * (ring[(i + 1) % n][1] - oy)
                   - (ring[(i + 1) % n][0] - ox) * (ring[i][1] - oy) for i in range(n))) / 2.0


def _pip(x, y, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        (x1, y1), (x2, y2) = ring[i][:2], ring[(i + 1) % n][:2]
        if (y1 > y) != (y2 > y) and x1 + (y - y1) * (x2 - x1) / (y2 - y1) > x:
            inside = not inside
    return inside


def _tet_volume(pts_m, tris1):
    """|divergence volume| of a closed mesh in ft3, model metres in, 1-based
    triangles -- summed about the first vertex (site coordinates safe)."""
    ox, oy, oz = pts_m[0]
    v = 0.0
    for a, b, c in tris1:
        p, q, r = pts_m[a - 1], pts_m[b - 1], pts_m[c - 1]
        px, py, pz = p[0] - ox, p[1] - oy, p[2] - oz
        qx, qy, qz = q[0] - ox, q[1] - oy, q[2] - oz
        rx, ry, rz = r[0] - ox, r[1] - oy, r[2] - oz
        v += px * (qy * rz - qz * ry) - py * (qx * rz - qz * rx) + pz * (qx * ry - qy * rx)
    return abs(v) / 6.0 * FT3


def _authored(model):
    """Authored volume (ft3) of a model's parts, by this module's shoelace."""
    v = 0.0
    for p in model.parts:
        if p.fit == "box":
            v += p.width_ft * p.depth_ft * p.height_ft
        elif p.fit == "polygon":
            v += _area(p.vertices_ft) * p.height_ft
        else:
            v += math.pi * p.radius_ft ** 2 * p.height_ft
    return v


def _covering(model, x_m, y_m, z_m):
    """Indices of the parts holding the model-metre point (x, y, z) -- read
    with ``recentre=False`` so parts sit where the mesh does."""
    x, y, z = x_m * FT, y_m * FT, z_m * FT
    out = []
    for k, p in enumerate(model.parts):
        if not (p.base_z_ft - 1e-9 <= z <= p.base_z_ft + p.height_ft + 1e-9):
            continue
        if p.fit == "polygon":
            hit = _pip(x, y, p.vertices_ft)
        elif p.fit == "box":
            hit = (abs(x - p.center_ft[0]) <= p.width_ft / 2.0 + 1e-9
                   and abs(y - p.center_ft[1]) <= p.depth_ft / 2.0 + 1e-9)
        else:
            hit = math.hypot(x - p.center_ft[0], y - p.center_ft[1]) <= p.radius_ft + 1e-9
        if hit:
            out.append(k)
    return out


def _classify(model):
    """One word for the outcome: boxes / slabs / prism (fill >= DECOMPOSE_FILL,
    nothing attempted) / kept:<the refusing clause>."""
    if model.decomposed:
        return model.decomposed[0]["method"]
    if not model.kept_prism:
        return "prism"
    reason = model.kept_prism[0]["reason"]
    for key in ("ambiguous slice", "crossing rings", "dropped material", "no closer",
                "part budget", "slab budget", "work budget", "one Z level", "no slab held"):
        if key in reason:
            return "kept:" + key
    return "kept:other"


def _run(path, pts, tris, name="Flush"):
    p = write_ifc(path, [(name, "IFCBUILDINGELEMENTPROXY", (pts, tris))])
    return AP.read_assembly(p, recentre=False)


# ---------------------------------------------------------------------------
# fixtures: flush placements (each shell's copy of ONE boundary direction at a
# shared slice vertex) and coincident diagonals (two bundles of two)
# ---------------------------------------------------------------------------

#: (label, block (w, d, h) m, member (w, d, h) m, member offset (ox, oy, oz) m).
#: Every member face lies IN a block face AND one member side face lies in the
#: block's end face (flush), so at every yawed slab through the member the two
#: rings meet at a vertex with two coincident spokes.  On main @ 7cb0cc7 each
#: row is the honest single prism ("ambiguous slice") at EVERY triangle order
#: and every yaw but 0 (where the box lane takes it exactly).
_FLUSH = [
    ("issue: lug on -x, +y edge flush, mid-height", (2.0, 6.0, 3.0), (0.5, 1.0, 0.5), (-1.25, 2.5, 1.25)),
    ("issue: lug on +x, +y edge flush, at the base", (2.0, 6.0, 3.0), (0.5, 1.0, 0.5), (1.25, 2.5, 0.0)),
    ("lug on +x, -y edge flush, mid-height", (2.0, 6.0, 3.0), (0.5, 1.0, 0.5), (1.25, -2.5, 1.25)),
    ("lug on +y face, +x edge flush", (2.0, 6.0, 3.0), (1.0, 1.5, 0.5), (0.5, 3.75, 1.0)),
    ("lug on -x, +y edge flush AND top flush (shared 3-D corner)", (2.0, 6.0, 3.0), (0.5, 1.0, 0.5),
     (-1.25, 2.5, 2.5)),
    ("stud on a 1x4x4 slab, +y edge flush, at the base", (1.0, 4.0, 4.0), (0.5, 0.5, 0.5), (0.75, 1.75, 0.0)),
    ("tall member against a plinth, edge flush", (2.0, 2.0, 0.5), (0.5, 0.5, 3.0), (1.25, 0.75, 0.0)),
    ("member wider than the face it is flush with (overhangs the other edge)", (2.0, 1.0, 3.0),
     (0.5, 1.5, 0.5), (1.25, -0.25, 1.0)),
]

_YAWS = (12.0, 33.0, -5.0, 5.0, -17.0, 45.0, 0.05)


def _two_flush_lugs(yaw):
    """A block with a flush lug at EACH end of its -x face: two junctions of
    the same kind in one slice (three shells)."""
    return _shells([_box_mesh(2.0, 6.0, 3.0),
                    _box_mesh(0.5, 1.0, 0.5, ox=-1.25, oy=2.5, oz=1.25),
                    _box_mesh(0.5, 1.0, 0.5, ox=-1.25, oy=-2.5, oz=1.25)], yaw)


def _diag_pair(yaw, coincident_lines=False):
    """The issue's coincident-diagonal case: a 1x1x2 m member centred half-way
    up a 3x3x6 m column's +x face (same aspect, centred), so the two touching
    faces' triangulation diagonals cross at the face centre -- exactly the
    mid slab's height: one slice vertex, two bundles of two coincident spokes.
    ``coincident_lines`` re-triangulates the member's touching face with the
    other diagonal, so the two diagonals are one LINE over the member's whole
    height rather than crossing at a point."""
    col_p, col_t = _box_mesh(3.0, 3.0, 6.0)
    mem_p, mem_t = _box_mesh(1.0, 1.0, 2.0, ox=2.0, oy=0.0, oz=2.0)
    if coincident_lines:                                # the x0 face: diagonal 1-8 instead of 4-5
        mem_t = [t for t in mem_t if set(t) not in ({4, 1, 5}, {4, 5, 8})] + [(1, 5, 8), (1, 8, 4)]
    return _shells([(col_p, col_t), (mem_p, mem_t)], yaw)


# ---------------------------------------------------------------------------
# the mechanism, on hand-made segments
# ---------------------------------------------------------------------------

def _square_band(x0, y0, x1, y1, z0, z1):
    """The four slice segments of an upright box and, per segment, the two
    vertical mesh edges it was cut from (as 3-D end point pairs)."""
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    post = {c: ((c[0], c[1], z0), (c[0], c[1], z1)) for c in corners}
    segs, cut_from = [], []
    for i in range(4):
        a, b = corners[i], corners[(i + 1) % 4]
        segs.append((a, b))
        cut_from.append([post[a], post[b]])
    return segs, cut_from


def test_bands_tell_the_two_copies_of_a_flush_boundary_apart():
    """Block [0,4]x[0,4] and lug [4,5]x[3,4]: the lug's top edge continues the
    block's, its left edge lies IN the block's right edge, and the two rings
    meet at (4, 4) with two coincident downward spokes.  The welded stitch
    refuses (main's answer, kept); band by band it is two rings."""
    bs, bc = _square_band(0, 0, 4, 4, 0.0, 10.0)
    ls, lc = _square_band(4, 3, 5, 4, 2.0, 6.0)
    segs, cut_from = bs + ls, bc + lc
    inside = lambda pt: (0 <= pt[0] <= 4 and 0 <= pt[1] <= 4) or (4 <= pt[0] <= 5 and 3 <= pt[1] <= 4)  # noqa: E731
    assert AP._stitch(segs, inside) is None                      # the coincident spokes, unresolved
    rings = AP._stitch_bands(segs, cut_from, inside)
    assert rings is not None and sorted(_area(r) for r in rings) == [1.0, 16.0]
    assert AP.ring_nesting(rings) == [0, 0]                      # side by side, both solid (#621)
    # an STL-style soup (every segment naming its OWN copies of the edge end
    # points) welds by coordinate all the same
    soup = [[tuple(tuple(float(c) for c in p) for p in e) for e in edges] for edges in cut_from]
    assert sorted(_area(r) for r in AP._stitch_bands(segs, soup, inside)) == [1.0, 16.0]


def test_bands_refuse_what_they_cannot_tell_apart():
    """One band (a shell touching ITSELF that way, or bands fused through a
    shared mesh edge) is nothing to separate: None, today's honest prism.  A
    band that does not close on its own: None.  Never a guess."""
    bs, bc = _square_band(0, 0, 4, 4, 0.0, 10.0)
    ls, lc = _square_band(4, 3, 5, 4, 2.0, 6.0)
    inside = lambda pt: (0 <= pt[0] <= 4 and 0 <= pt[1] <= 4) or (4 <= pt[0] <= 5 and 3 <= pt[1] <= 4)  # noqa: E731
    # fuse the two bands: the lug's post at (4, 4) IS the block's mesh edge
    fused = [list(e) for e in lc]
    fused[2][1] = bc[1][1]                                       # lug top edge's (4,4) end -> block's post
    fused[3][0] = bc[1][1]                                       # lug left edge's (4,4) end -> block's post
    assert AP._stitch_bands(bs + ls, bc + fused, inside) is None
    assert AP._stitch_bands(bs, bc, inside) is None              # a single band
    # a band missing a segment is an open chain on its own
    assert AP._stitch_bands(bs + ls[:3], bc + lc[:3], inside) is None


def test_the_flush_slice_is_two_rings_and_the_diagonal_slice_pairs_straight_through():
    for (pts, tris), z_m, areas_m2 in ((_face_pair(*_FLUSH[0][1:], 12.0), 1.5, [0.5, 12.0]),
                                       (_diag_pair(33.0), 3.0, [1.0, 9.0]),
                                       (_diag_pair(-5.0, coincident_lines=True), 3.0, [1.0, 9.0])):
        p = [(x * FT, y * FT, z * FT) for x, y, z in pts]
        t0 = [(a - 1, b - 1, c - 1) for a, b, c in tris]
        rings = AP.slice_loops(p, t0, z_m * FT)
        assert rings is not None and len(rings) == 2
        assert sorted(_area(r) / FT ** 2 for r in rings) == pytest.approx(areas_m2, rel=1e-5)   # the file keeps microns
        assert AP.ring_nesting(rings) == [0, 0]


# ---------------------------------------------------------------------------
# end to end: every flush placement decomposes with its member, at every order
# ---------------------------------------------------------------------------

def _check_pair(model, big, mem, off, yaw, oracle_ft3):
    """The law and the outcome.  Law: never authored < mesh without kept_prism.
    Outcome: slabs, no hole filled, authored == the two shells' volume to
    1e-5, and the MEMBER IS THERE -- its centre is held by an authored part at
    its own mid-height, and so is the block's (by a different part unless the
    member stands taller than the block there)."""
    authored = _authored(model)
    assert authored >= oracle_ft3 * (1.0 - 1e-6) or model.kept_prism, (off, yaw, authored / oracle_ft3)
    assert _classify(model) == "slabs", (off, yaw, _classify(model), model.kept_prism)
    assert model.decomposed[0]["holes_filled"] == 0 and not model.kept_prism, (off, yaw)
    assert authored == pytest.approx(oracle_ft3, rel=1e-5), (off, yaw, authored / oracle_ft3)
    held_m = _covering(model, *_yaw([(off[0], off[1], off[2] + mem[2] / 2.0)], yaw)[0])
    held_b = _covering(model, 0.0, 0.0, min(big[2], mem[2]) / 2.0)
    assert len(held_m) == 1 and len(held_b) == 1, (off, yaw, held_m, held_b)
    assert held_m != held_b, (off, yaw)                          # two regions, not one envelope


def test_the_issues_flush_pairs_decompose_with_their_member_at_every_order(tmp_path):
    """DONE 1, the named fixtures: `_face_pair((2,6,3),(0.5,1,0.5),(-1.25,2.5,1.25),12)`
    and `(1.25,2.5,0) @ 33` over 101 seeded triangle orders each (identity +
    100 shuffles) => slabs with the member present, authored == block + lug to
    1e-5, at every order.  Main @ 7cb0cc7: 202/202 kept prisms at 1.1379x."""
    runs = 0
    for row, yaw in ((_FLUSH[0], 12.0), (_FLUSH[1], 33.0)):
        _label, big, mem, off = row
        pts, base = _face_pair(big, mem, off, yaw)
        oracle = _tet_volume(pts, base)
        assert oracle == pytest.approx((big[0] * big[1] * big[2] + mem[0] * mem[1] * mem[2]) * FT3, rel=2e-6)
        for tris in _triangle_orders(base, seeds=100):
            _check_pair(_run(str(tmp_path / "f.ifc"), pts, tris), big, mem, off, yaw, oracle)
            runs += 1
    assert runs == 202


def test_every_flush_placement_decomposes_at_every_yaw_and_order(tmp_path):
    """The eight flush placements x seven yaws x 13 orders (728 runs): slabs,
    member present, exact -- including the lug flush with the block's edge AND
    its top (a shared 3-D corner: the two copies are still different mesh
    edges), the tall member past a plinth, and a member overhanging the face."""
    runs = 0
    for row in _FLUSH:
        _label, big, mem, off = row
        for yaw in _YAWS:
            pts, base = _face_pair(big, mem, off, yaw)
            oracle = _tet_volume(pts, base)
            for tris in _triangle_orders(base, seeds=12):
                _check_pair(_run(str(tmp_path / "f.ifc"), pts, tris), big, mem, off, yaw, oracle)
                runs += 1
    assert runs == len(_FLUSH) * len(_YAWS) * 13


def test_two_flush_lugs_in_one_slice_both_come_back(tmp_path):
    for yaw in (12.0, 33.0, -17.0):
        pts, base = _two_flush_lugs(yaw)
        oracle = _tet_volume(pts, base)
        for tris in _triangle_orders(base, seeds=12):
            m = _run(str(tmp_path / "two.ifc"), pts, tris)
            assert _classify(m) == "slabs" and not m.kept_prism, (yaw, m.kept_prism)
            assert _authored(m) == pytest.approx(oracle, rel=1e-5), yaw
            assert len(m.parts) == 5, (yaw, len(m.parts))            # block / block + 2 lugs / block
            for oy in (2.5, -2.5):
                assert len(_covering(m, *_yaw([(-1.25, oy, 1.5)], yaw)[0])) == 1, (yaw, oy)


def test_coincident_diagonals_pair_straight_through(tmp_path):
    """DONE 1's third fixture: the member centred half-way up the column's
    face.  Diagonals crossing at the mid slab's height (the standard mesh) and
    diagonals lying on one line (re-triangulated) both decompose: column below
    / column + member / column above, exact, every yaw and order.  Main: kept
    prism at every yawed order of both."""
    runs = 0
    for lines in (False, True):
        for yaw in _YAWS:
            pts, base = _diag_pair(yaw, coincident_lines=lines)
            oracle = _tet_volume(pts, base)
            assert oracle == pytest.approx((54.0 + 2.0) * FT3, rel=2e-6)
            for tris in _triangle_orders(base, seeds=100 if yaw == 12.0 else 6):
                m = _run(str(tmp_path / "d.ifc"), pts, tris, name="Diag")
                _check_pair(m, (3.0, 3.0, 6.0), (1.0, 1.0, 2.0), (2.0, 0.0, 2.0), yaw, oracle)
                assert len(m.parts) == 4, (lines, yaw, len(m.parts))
                runs += 1
    assert runs == 2 * (101 + 6 * 7)


def test_what_no_band_can_tell_apart_is_still_the_honest_prism(tmp_path):
    """The residue, delivered and attributed (rule 1): the flush lug exported
    TWICE.  Its two copies weld into ONE band whose every vertex carries two
    coincident spoke pairs -- nothing says which copy continues which -- so
    the slice stays ambiguous and the body ships as one prism that says so,
    at every order; never a guessed ring set, never authored under the mesh."""
    pts, base = _dup_lug(off=_FLUSH[0][3], yaw=12.0)
    oracle = _tet_volume(pts, base)
    for tris in _triangle_orders(base, seeds=12):
        m = _run(str(tmp_path / "dup.ifc"), pts, tris)
        assert _classify(m) == "kept:ambiguous slice" and len(m.parts) == 1, m.kept_prism
        assert _authored(m) >= oracle


def test_at_zero_yaw_the_box_lane_still_takes_the_flush_pair_exactly(tmp_path):
    """Control: unyawed, a flush pair is an axis-aligned polyhedron -- two
    exact boxes, before and after alike; the band stitch is never asked."""
    for row in (_FLUSH[0], _FLUSH[5]):
        _label, big, mem, off = row
        pts, base = _face_pair(big, mem, off, 0.0)
        m = _run(str(tmp_path / "f0.ifc"), pts, base)
        assert _classify(m) == "boxes" and m.decomposed[0]["exact"] and len(m.parts) == 2
        assert _authored(m) == pytest.approx(_tet_volume(pts, base), rel=AP.EXACT_REL_TOL)


# ---------------------------------------------------------------------------
# #621's randomised face-sharing search, re-run: no silent loss, and the flush
# class decomposes instead of costing the body its decomposition
# ---------------------------------------------------------------------------

def _random_face_pairs(seed, n=300):
    """The shape of #621's randomised search: block in {1..6}^3 m, member
    0.5-2 m a side on a random face (+-x, +-y, top), lateral placement centred
    / FLUSH with an edge / random, vertical placement base / mid / top-flush /
    taller than the block.  Yields (big, mem, off, kind) in model metres,
    kind naming the lateral and vertical draw."""
    import random
    rng = random.Random(seed)
    for _ in range(n):
        big = (rng.randint(1, 6), rng.randint(1, 6), rng.randint(1, 6))
        mem = [round(rng.uniform(0.5, 2.0), 3) for _ in range(3)]
        face = rng.choice(("+x", "-x", "+y", "-y", "top"))
        lateral = rng.choice(("centred", "flush", "random"))
        vertical = rng.choice(("base", "mid", "topflush", "taller"))

        def along(extent_big, extent_mem):                    # the member's centre along one face axis
            if lateral == "centred":
                return 0.0
            if lateral == "flush":
                return rng.choice((-1, 1)) * (extent_big - extent_mem) / 2.0
            return round(rng.uniform(-1, 1) * (extent_big + extent_mem) / 2.0 * 0.9, 3)

        if face == "top":
            off = (along(big[0], mem[0]), along(big[1], mem[1]), float(big[2]))
        else:
            axis = 0 if face[1] == "x" else 1
            sign = 1.0 if face[0] == "+" else -1.0
            if vertical == "taller":
                mem[2] = round(big[2] * rng.uniform(1.1, 1.5), 3)
            oz = {"base": 0.0, "mid": (big[2] - mem[2]) / 2.0, "topflush": big[2] - mem[2],
                  "taller": 0.0}[vertical]
            lat = along(big[1 - axis], mem[1 - axis])
            normal = sign * (big[axis] + mem[axis]) / 2.0
            off = (normal, lat, oz) if axis == 0 else (lat, normal, oz)
        yield big, tuple(mem), off, f"{face}/{lateral}/{vertical}"


def _random_search(path, seeds, n, yaws, orders):
    """Run the search; return (runs, silent losses, {class: count},
    {kind: {class: count}}, worst authored / oracle among decompositions)."""
    runs, losses, worst = 0, [], 0.0
    classes, by_kind = Counter(), defaultdict(Counter)
    for seed in seeds:
        for big, mem, off, kind in _random_face_pairs(seed, n):
            for yaw in yaws:
                pts, base = _face_pair(big, mem, off, yaw)
                oracle = _tet_volume(pts, base)
                for tris in _triangle_orders(base, seeds=orders - 1):
                    m = _run(path, pts, tris, name="Pair")
                    runs += 1
                    cls = _classify(m)
                    authored = _authored(m)
                    classes[cls] += 1
                    by_kind[kind][cls] += 1
                    if authored < oracle * (1.0 - 1e-6) and not m.kept_prism:
                        losses.append((seed, big, mem, off, yaw, cls, authored / oracle))
                    if cls in ("slabs", "boxes"):
                        worst = max(worst, abs(authored - oracle) / oracle)
    return runs, losses, classes, by_kind, worst


def test_the_randomised_face_sharing_search_never_loses_and_its_flush_draws_decompose(tmp_path):
    """A CI-sized slice of the record's search (seed 634, 40 configurations x
    yaws {12, 33} x 3 orders = 240 runs; the record runs 3 x 300 x 5 x 41):
    zero silent losses, zero "dropped material", every decomposition exact to
    1e-5 -- and not one flush draw left as an "ambiguous slice" prism (main @
    7cb0cc7 keeps every yawed flush draw whose fill is under 0.90 that way)."""
    runs, losses, classes, by_kind, worst = _random_search(
        str(tmp_path / "r.ifc"), seeds=(634,), n=40, yaws=(12.0, 33.0), orders=3)
    assert runs == 240 and not losses, losses[:3]
    assert classes.get("kept:dropped material", 0) == 0, classes
    assert worst <= 1e-5, worst
    flush_kept = sum(c.get("kept:ambiguous slice", 0) for k, c in by_kind.items() if "/flush/" in k)
    assert flush_kept == 0, {k: c for k, c in by_kind.items() if "/flush/" in k}
    assert sum(c.get("slabs", 0) for k, c in by_kind.items() if "/flush/" in k) > 0


# ---------------------------------------------------------------------------
# the router delivers the flush pair in parts, and says so
# ---------------------------------------------------------------------------

def test_the_router_delivers_the_flush_pair_as_block_and_lug(tmp_path):
    from rvt.frontdoor import router as R
    pts, base = _face_pair(*_FLUSH[0][1:], 12.0)
    p = write_ifc(str(tmp_path / "flush.ifc"), [("Flush", "IFCBUILDINGELEMENTPROXY", (pts, base))])
    res = R.route({"ifc": p}, "rfa", out=str(tmp_path / "o"), quiet=True)
    assert res.ok and os.path.isfile(res.files["rfa"])
    assert res.status.startswith("OK (4-part generic_model .rfa"), res.status
    assert any("slab decomposition improved Flush (4 solids, fill 0.88 -> 1.00)" in c for c in res.caveats), res.caveats
    assert not any("kept as a single prism" in c for c in res.caveats)
    assert not any("crossing section(s) merged" in c for c in res.caveats)     # contact, not a crossing


# ---------------------------------------------------------------------------
# the record's sweeps: python tests/test_ifc_assembly_634.py <what> [args]
# ---------------------------------------------------------------------------

def _reference_rows():
    """Contact / taper / hairline / budget / fit rows that must read as on
    main (name, (pts, 1-based tris))."""
    from test_ifc_assembly_628 import _chamfered
    up, ut = _u_channel()
    ut1 = [(a + 1, b + 1, c + 1) for a, b, c in ut]
    ch = _chamfered(1.0, 1.0, 0.2)
    n = len(ch) // 2
    ch_t = [t for i in range(n) for t in ((i + 1, (i + 1) % n + 1, (i + 1) % n + 1 + n),
                                          (i + 1, (i + 1) % n + 1 + n, i + 1 + n))]
    ch_t += [t for i in range(1, n - 1) for t in ((1, i + 2, i + 1), (1 + n, 1 + n + i, 2 + n + i))]
    p1, t1 = _box_mesh(0.30, 0.20, 0.035)
    side = math.sqrt(6e-6)
    return [
        ("900 mm strut 0.0", _strut(0.0)), ("900 mm strut 0.1", _strut(0.1)),
        ("900 mm strut 0.2", _strut(0.2)), ("900 mm strut 0.5", _strut(0.5)),
        ("900 mm strut 0.8", _strut(0.8)),
        ("50 um mismatch strut 0", _strut_mismatch(0.0)), ("50 um mismatch strut 12", _strut_mismatch(12.0)),
        ("8-band reducer frustum", _frustum()), ("12-band cone", _frustum(r0=0.10, r1=0.005, bands=12)),
        ("24-band 64-side frustum", _frustum(bands=24, sides=64)),
        ("plate + 6 mm2 pin 7", _shells([(p1, t1), _box_mesh(side, side, 0.02, ox=0.05, oy=0.03, oz=0.035)], 7.0)),
        ("U-channel 4", (_yaw(up, 4.0), ut1)), ("U-channel 30", (_yaw(up, 30.0), ut1)),
        ("chamfered square 22.5 (#628)", (_yaw(ch, 22.5), ch_t)),
        ("lattice 3x3x3 (#623)", _lattice(3)), ("lattice 9x9x9 (#623)", _lattice(9)),
        ("sunk lug 1 cm @ 12 (#637)", _face_pair((2.0, 6.0, 3.0), (0.5, 1.0, 0.5), (1.24, 0.969, 1.25), 12.0)),
        ("#621 face pair 12", _face_pair(*_FACE_PAIRS[3])),
        ("#609 corner pair 12", _corner_pair(-3.5, 3.5, 12.0)),
        ("flush lug 12 (#634)", _face_pair(*_FLUSH[0][1:], 12.0)),
    ]


def _describe(m, pts, tris):
    d = m.decomposed[0] if m.decomposed else {}
    return (f"{_classify(m):<22} parts {len(m.parts):>3}  authored/mesh {_authored(m) / _tet_volume(pts, tris):.6f}"
            f"  holes {d.get('holes_filled', '-')}  merged {d.get('crossings_merged', '-')}"
            + (f"  [{m.kept_prism[0]['reason'][:90]}]" if m.kept_prism else ""))


def _main(argv):                                        # pragma: no cover -- the record's driver
    import tempfile
    import time
    what = argv[1] if len(argv) > 1 else "named"
    tmp = tempfile.mkdtemp(prefix="flush634_")
    path = os.path.join(tmp, "b.ifc")
    print(f"# engine: {AP.__file__}  ({'with' if hasattr(AP, '_stitch_bands') else 'WITHOUT'} _stitch_bands)")
    if what == "named":                                 # flush placements + diagonals x yaws x orders
        orders = int(argv[2]) if len(argv) > 2 else 101
        rows = [(f"F{k} {r[0]}", (lambda y, r=r: _face_pair(*r[1:], y))) for k, r in enumerate(_FLUSH)]
        rows += [("two flush lugs, one slice", _two_flush_lugs),
                 ("D1 diagonals crossing at the mid slab (issue's column + member)", _diag_pair),
                 ("D2 diagonals on one line (member face re-triangulated)", lambda y: _diag_pair(y, True))]
        total = Counter()
        for label, gen in rows:
            for yaw in _YAWS + (0.0,):
                pts, base = gen(yaw)
                oracle = _tet_volume(pts, base)
                ratios, parts = defaultdict(list), defaultdict(set)     # per outcome class
                for tris in _triangle_orders(base, seeds=orders - 1):
                    m = _run(path, pts, tris)
                    cls = _classify(m)
                    ratios[cls].append(_authored(m) / oracle)
                    parts[cls].add(len(m.parts))
                    total[cls] += 1
                    if ratios[cls][-1] < 1.0 - 1e-6 and not m.kept_prism:
                        print("  SILENT LOSS", label, yaw, cls, ratios[cls][-1])
                cells = "; ".join(f"{c} x{len(r)} parts {sorted(parts[c])} {min(r):.6f}..{max(r):.6f}"
                                  for c, r in ratios.items())
                print(f"{label:<72} yaw {yaw:>6}: {cells}")
        print("TOTAL", sum(total.values()), dict(sorted(total.items())))
    elif what == "random":                              # #621's search shape: seeds x n x yaws x orders
        seeds = tuple(int(s) for s in (argv[2] if len(argv) > 2 else "1,2,3").split(","))
        n = int(argv[3]) if len(argv) > 3 else 300
        orders = int(argv[4]) if len(argv) > 4 else 41
        t0 = time.time()
        runs, losses, classes, by_kind, worst = _random_search(path, seeds, n, (0.0, 5.0, 12.0, 33.0, -5.0), orders)
        print(f"runs {runs} in {time.time() - t0:.0f} s; silent losses {len(losses)}; "
              f"worst |authored-oracle|/oracle among decompositions {worst:.2e}")
        print("classes", dict(sorted(classes.items())))
        for kind in sorted(by_kind):
            print(f"  {kind:<26} {dict(sorted(by_kind[kind].items()))}")
        for loss in losses[:20]:
            print("  LOSS", loss)
    elif what == "contact":                             # #609 corner pairs (984) + #621 face pairs (205), per run
        for tag, (pts, base) in ([(f"corner {ox},{oy} @ {y}", _corner_pair(ox, oy, y))
                                  for ox, oy in ((-3.5, 3.5), (-3.5, -3.5), (3.5, 3.5), (3.5, -3.5))
                                  for y in (5.0, 12.0, 33.0, -5.0, 45.0, 0.05)]
                                 + [(f"face {row}", _face_pair(*row)) for row in _FACE_PAIRS]):
            for k, tris in enumerate(_triangle_orders(base)):
                m = _run(path, pts, tris)
                print(f"{tag} #{k}: {_describe(m, pts, tris)}")
    elif what == "reference":
        for name, (pts, tris) in _reference_rows():
            print(f"{name:<34} {_describe(_run(path, pts, tris), pts, tris)}")
    elif what == "timing":                              # best of 5 read_assembly, ms
        for name, (pts, tris) in _reference_rows():
            p = write_ifc(path, [("T", "IFCBUILDINGELEMENTPROXY", (pts, tris))])
            best = float("inf")
            for _ in range(5):
                t0 = time.perf_counter()
                AP.read_assembly(p)
                best = min(best, time.perf_counter() - t0)
            print(f"{name:<34} {best * 1000:8.2f} ms")
    else:
        raise SystemExit("usage: test_ifc_assembly_634.py named [orders] | random [seeds] [n] [orders] "
                         "| contact | reference | timing")


if __name__ == "__main__":                              # pragma: no cover
    _main(sys.argv)

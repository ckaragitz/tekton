"""The ASSEMBLY lane's refusals are ATTRIBUTED, and a dense lattice is refused
on a work budget BEFORE the grid pass instead of after 44 s of it (#623).

Own module per the #636 convention (fixtures come from
``tests/test_ifc_assembly.py``, which is not appended to); synthesised IFC4
text only -- no ``samples/``, no ifcopenshell: runs on a fresh clone.

Territory: ifc-assembly stream, issue #623.
"""
from __future__ import annotations

import time

import pytest

from rvt.ifc import assembly_parts as AP
from test_ifc_assembly import (_box_mesh, _face_pair, _prism_mesh, _strut, _tri0,
                               _u_channel, write_ifc, FT)

#: The wording every refusal used to get, whichever lane and budget refused.
OLD_CATCH_ALL = "most likely runs along X or Y"

#: Generous on purpose (slow CI VMs): the 9^3 lattice read 44 s before the
#: work budget and 0.3 s after it on the VM that measured #623.
WALL_CEILING_S = 10.0


def _lattice(n, size=0.1, gap=0.1):
    """n x n x n separate cubes as ONE product (1-based triangles): the #583
    review's dense body -- (2n-1)^3 grid cells, 12 n^3 triangles."""
    pts, tris = [], []
    for i in range(n):
        for j in range(n):
            for k in range(n):
                p, t = _box_mesh(size, size, size, ox=i * (size + gap),
                                 oy=j * (size + gap), oz=k * (size + gap))
                b = len(pts)
                pts += list(p)
                tris += [(a + b, b2 + b, c + b) for a, b2, c in t]
    return pts, tris


@pytest.fixture(scope="module")
def lattice9(tmp_path_factory):
    pts, tris = _lattice(9)
    assert len(tris) == 8748                                        # the review's numbers
    p = write_ifc(str(tmp_path_factory.mktemp("lat") / "lattice9.ifc"),
                  [("Lattice9", "IFCBUILDINGELEMENTPROXY", (pts, tris))])
    t0 = time.perf_counter()
    model = AP.read_assembly(p)
    return p, model, time.perf_counter() - t0


# ---------------------------------------------------------------------------
# the lattice: fast, delivered, and honest about why it is one prism
# ---------------------------------------------------------------------------

def test_a_dense_lattice_is_refused_on_the_work_budget_before_the_grid_pass(lattice9):
    _, m, seconds = lattice9
    assert seconds < WALL_CEILING_S, seconds
    assert len(m.parts) == 1 and m.parts[0].fit == "box"           # rule 1: the prism ships
    assert not m.decomposed and len(m.kept_prism) == 1
    reason = m.kept_prism[0]["reason"]
    assert reason.startswith("box lane: work budget (4913 grid cells x 8748 triangles")
    assert "slab lane: part budget (81 solids by the slab at" in reason   # each lane, its own reason
    assert OLD_CATCH_ALL not in reason


def test_the_work_budget_is_the_product_it_says_it_is():
    pts, tris = _lattice(9)
    axes = [sorted({round(p[i], AP._WELD) for p in pts}) for i in range(3)]
    cells = (len(axes[0]) - 1) * (len(axes[1]) - 1) * (len(axes[2]) - 1)
    assert cells == 4913 and cells <= AP.MAX_GRID_CELLS               # the cell budget let it in
    assert cells * len(tris) > AP.MAX_GRID_WORK                       # the work budget does not
    why = []
    t0 = time.perf_counter()
    assert AP.decompose_boxes(pts, _tri0(tris), refusal=why) is None
    assert time.perf_counter() - t0 < WALL_CEILING_S
    assert len(why) == 1 and why[0].startswith("work budget (4913 grid cells x 8748 triangles = 4.3e+07")
    # under a big enough budget the very same body is only over the BOX budget
    # -- proven on a 5^3 corner of it (125 cubes > MAX_BOXES, 1.1e6 tests) so
    # the test does not spend the 44 s
    pts5, tris5 = _lattice(5)
    assert 5 ** 3 > AP.MAX_BOXES
    why = []
    assert AP.decompose_boxes(pts5, _tri0(tris5), refusal=why, max_work=10 ** 9) is None
    assert why == [f"box budget (more than {AP.MAX_BOXES} merged boxes)"]


def test_the_route_caveat_carries_the_lanes_own_reasons(lattice9, tmp_path):
    from rvt.frontdoor import router as R
    p, _, _ = lattice9
    res = R.route({"ifc": p}, "rfa", out=str(tmp_path / "o"), quiet=True)
    assert res.ok and res.files.get("rfa")                              # delivered (rule 1)
    caveat = next(c for c in res.caveats if c.startswith("kept as a single prism"))
    assert "Lattice9 -- box lane: work budget (" in caveat
    assert "then slab lane: part budget (" in caveat
    assert not any(OLD_CATCH_ALL in c for c in res.caveats)


# ---------------------------------------------------------------------------
# every refusal of either lane names itself; success says nothing
# ---------------------------------------------------------------------------

def test_box_lane_refusals_are_attributed_and_the_contract_is_still_None():
    chan = _u_channel()                                          # 0-based triangles already
    prism_p, prism_t = _prism_mesh(1.0, 2.0, 24)
    cube_p, cube_t = _box_mesh(1.0, 1.0, 1.0)                    # + a real 0.2 mm film on top:
    shim_p, _ = _box_mesh(0.5, 0.5, AP.MIN_EXTENT_FT / 2.0, oz=1.0)
    slivered = (list(cube_p) + list(shim_p),
                _tri0(cube_t) + [(a + 8, b + 8, c + 8) for a, b, c in _tri0(cube_t)])
    cases = [
        ((prism_p, _tri0(prism_t)), {}, "not axis-aligned"),
        (chan, {"max_cells": 1}, "cell budget (1 x 3 x 2 = 6 grid cells, over the 1 allowed)"),
        (chan, {"max_work": 1}, "work budget (6 grid cells x 36 triangles"),
        (chan, {"max_boxes": 1}, "box budget (more than 1 merged boxes)"),
        (slivered, {}, "sliver box ("),
    ]
    for (pts, tris), kw, expect in cases:
        why = []
        assert AP.decompose_boxes(pts, tris, refusal=why, **kw) is None, expect
        assert len(why) == 1 and why[0].startswith(expect), why
        assert AP.decompose_boxes(pts, tris, **kw) is None            # nobody asked: bare None, as ever
    # and a body that decomposes appends nothing
    why = []
    dec = AP.decompose_boxes(*chan, refusal=why)
    assert dec is not None and dec["exact"] and why == []


def test_slab_lane_refusals_are_attributed_and_the_contract_is_still_None():
    pts, tris = _box_mesh(1.0, 1.0, 1.0)
    for kw, expect in (({"max_parts": 0}, "part budget (1 solids by the slab at z = 0.5000 ft, over the 0 allowed)"),
                       ({"max_slabs": 0}, "slab budget (1 Z slabs, over the 0 allowed)")):
        why = []
        assert AP.decompose_slabs(pts, _tri0(tris), refusal=why, **kw) is None
        assert why == [expect]
        assert AP.decompose_slabs(pts, _tri0(tris), **kw) is None
    why = []
    flat = [(x, y, 0.0) for x, y, _ in pts]
    assert AP.decompose_slabs(flat, _tri0(tris), refusal=why) is None
    assert why[0].startswith("one Z level")
    assert AP.decompose_slabs(pts, [], refusal=why) is None and why[-1] == "no readable triangles"
    # a lug exported TWICE against a block (a duplicated shell): an ambiguous slice, and it says WHERE
    # (was #634's flush lug, which decomposes since #634 -- fixture swapped BY DESIGN, assertion unchanged)
    fp, ft = _dup_lug()
    why = []
    assert AP.decompose_slabs([(x * FT, y * FT, z * FT) for x, y, z in fp], _tri0(ft), refusal=why) is None
    assert why[0].startswith("ambiguous slice at z = ")
    # success appends nothing
    p2, t2 = _box_mesh(0.5, 0.5, 1.0, oz=1.0)
    why = []
    dec = AP.decompose_slabs(list(pts) + list(p2),
                             _tri0(tris) + [(a - 1 + 8, b - 1 + 8, c - 1 + 8) for a, b, c in t2], refusal=why)
    assert dec is not None and len(dec["parts"]) == 2 and why == []


def test_a_volume_mismatch_is_named_when_both_lanes_refuse(tmp_path, monkeypatch):
    """The box lane's exactness law is the CALLER's check (it holds the mesh
    volume), so its refusal is worded there; it only reaches kept_prism when
    the slab lane refuses too -- forced here through the part budget."""
    pts, tris = _strut(0.0)
    p = write_ifc(str(tmp_path / "s.ifc"), [("Strut", "IFCMEMBER", (pts, tris))])
    real_boxes, real_slabs = AP.decompose_boxes, AP.decompose_slabs

    def short(points, triangles, **kw):
        d = real_boxes(points, triangles, **kw)
        d["volume_ft3"] *= 0.999
        return d
    monkeypatch.setattr(AP, "decompose_boxes", short)
    m = AP.read_assembly(p)                                   # slabs rescue it: no prism, no word
    assert m.decomposed and m.decomposed[0]["method"] == "slabs" and not m.kept_prism
    monkeypatch.setattr(AP, "decompose_slabs",
                        lambda points, triangles, **kw: real_slabs(points, triangles, max_parts=0, **kw))
    m = AP.read_assembly(p)
    assert len(m.parts) == 1 and len(m.kept_prism) == 1
    reason = m.kept_prism[0]["reason"]
    assert reason.startswith("box lane: volume mismatch (3 boxes ")
    assert ", then slab lane: part budget (" in reason


def test_a_yawed_body_the_slab_lane_rescues_reports_no_refusal(tmp_path):
    """A box-lane refusal followed by a slab-lane SUCCESS is not a kept prism:
    the yawed strut is 'not axis-aligned' and then three exact slabs -- and
    kept_prism stays empty, exactly as before this change."""
    p = write_ifc(str(tmp_path / "y.ifc"), [("Strut", "IFCMEMBER", _strut(0.5))])
    m = AP.read_assembly(p)
    assert m.decomposed and m.decomposed[0]["method"] == "slabs" and len(m.parts) == 3
    assert not m.kept_prism


def _dup_lug(off=(-1.25, 0.969, 1.25), yaw=12.0):
    """#621's block + lug (`_face_pair`, lug at ``off``) with the lug shell
    exported TWICE: every vertex of the doubled ring is a junction of two
    coincident spoke pairs of ONE welded band, which no stitch can tell apart
    -- genuinely ambiguous, the honest prism before and after #634 (whose
    flush lug, the fixture these two tests used to borrow, now decomposes)."""
    fp, ft = _face_pair((2.0, 6.0, 3.0), (0.5, 1.0, 0.5), off, yaw)
    n = len(fp) // 2                                     # _face_pair: block's 8 points, then the lug's 8
    lug_t = ft[len(ft) // 2:]                            # ... and its 12 triangles, then the lug's 12
    return list(fp) + list(fp[n:]), list(ft) + [(a + n, b + n, c + n) for a, b, c in lug_t]


def test_an_undecomposable_yawed_body_names_both_lanes(tmp_path):
    """The doubled lug both lanes refuse: the box lane because it is yawed, the
    slab lane on its ambiguous slice -- and the reason says both, in order."""
    fp, ft = _dup_lug()
    p = write_ifc(str(tmp_path / "dup.ifc"), [("Dup", "IFCBUILDINGELEMENTPROXY", (fp, ft))])
    m = AP.read_assembly(p)
    assert len(m.parts) == 1 and len(m.kept_prism) == 1
    reason = m.kept_prism[0]["reason"]
    assert reason.startswith("box lane: not axis-aligned (")
    assert ", then slab lane: ambiguous slice at z = " in reason

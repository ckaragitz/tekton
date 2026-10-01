"""Parts that FOLLOW a moving plane (#904, steer #908).

The owner's "Follow" probe ladder came back with all 9 rungs working on desktop
Revit (#904, 2026-10-01):
- symmetric ends;
- a labelled offset plane;
- EQ about a plane;
- a locked width;
- a circle's centre locked to a plane.

These tests pin the production port of those mechanisms (``drive_law.wire_follow``
and ``wire_symmetric``) and the trapeze that uses them: every lock lies on its plane,
a refused follow leaves the written file byte-identical to the build without it, and
the linear drive it builds on is never undone.  Nothing here claims the assembled
trapeze flexes; that is its own desktop verdict (hard rule 4).
"""
from __future__ import annotations

import hashlib
import os
import shutil
import tempfile

import pytest

from rvt.famgen import archetypes as AR
from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F

IN = 1.0 / 12.0


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t904f_")
    try:
        path = os.path.join(d, "f.rfa")
        prod.write(path)
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    finally:
        shutil.rmtree(d, True)


def _locks_on_planes(doc):
    """(line locks, arc-centre locks, off-plane count) over every sketch lock."""
    planes = {p.elem_id: p for p in doc.refplanes}
    by_id = {e.elem_id: e for e in doc.elements}
    lines = arcs = bad = 0
    for al in DL._sketch_locks(doc):
        g = [w["m_pWitnessRef"]["value"]["m_geomRef"] for w in al.obj["m_witnessRefs"]]
        pl = [x for x in g if x["m_elemId"] in planes]
        cu = [x for x in g if x["m_elemId"] not in planes]
        x = DL.plane_at(planes[pl[0]["m_elemId"]], "x")
        crv = by_id[cu[0]["m_elemId"]].obj["m_pCurveDriver"]["value"]["m_pCrv"]
        v = crv["value"]
        if crv["ptr_class"] == "GArc":
            arcs += 1
            bad += abs(v["m_center"][0] - x) > 1e-6 or cu[0]["m_geomTag"] != 1
        else:
            lines += 1
            ends = [v["m_origin"][0] + v["m_dirVec"][0] * t for t in v["m_endParams"]]
            bad += any(abs(e - x) > 1e-6 for e in ends)
    return lines, arcs, bad


@pytest.mark.parametrize("prompt, tiers", [
    ("a 2 tier slotted trapeze with threaded rod", 2),
    ("a 3 tier trapeze 36 in long with 1/2 in threaded rod", 3),
    ("a 1 tier trapeze", 1),
])
def test_the_trapeze_rods_washers_and_nuts_follow_the_strut_ends(prompt, tiers):
    prod = F.make_archetype(product="strut_trapeze", prompt=prompt)
    (d,) = prod.drives
    assert d["symmetric"] is True
    fol = d["follow"]
    # 2 rods + per tier, per side: a washer and a nut below and above
    assert fol["followers"] == 2 + 8 * tiers
    assert fol["rigid_pairs"] == 4                      # washer + nut planes per side
    assert fol["locks"] == 4 + 2 * 8 * tiers            # 2 arcs per rod, 2 flats per part
    lines, arcs, bad = _locks_on_planes(prod.doc)
    assert arcs == 4 and bad == 0
    assert lines == len(d["locks"]) + 2 * 8 * tiers
    eq = [x for x in prod.doc.by_class("LinearDimString") if x.obj["m_flags"] == 140]
    assert len(eq) == 1 + 1 + 4                         # ends, rod planes, 4 rigid pairs
    labelled = {s["m_paramId"] for x in prod.doc.by_class("LinearDimString")
                for s in x.obj["m_ArrSegInfo"] if s["m_paramId"] >= 0}
    assert labelled == {prod.doc.params["Strut Length"].elem_id,
                        prod.doc.params["Rod Inset"].elem_id}
    assert any("follow it at Rod Inset" in n for n in prod.doc.notes)
    assert not any(e.obj.get("m_constrInfo") for e in prod.doc.elements)


def test_the_hex_nut_has_two_flats_square_to_the_strut():
    v = AR.archetype("strut_trapeze").defaults()
    nut = next(p for p in AR._strut_trapeze(v) if " nut " in p["name"])
    xs = [round(q[0], 9) for q in nut["vertices"][:-1]]
    af = 1.5 * 0.375 * IN
    assert sorted(set(xs)) == pytest.approx([-af / 2.0, 0.0, af / 2.0])
    assert xs.count(round(af / 2.0, 9)) == 2 and xs.count(round(-af / 2.0, 9)) == 2


STRUT = {"shape": "box", "name": "strut", "width_ft": 2.5, "depth_ft": 0.2,
         "height_ft": 0.2, "center": [0.0, 0.0]}
POST = {"shape": "box", "name": "post", "width_ft": 1 * IN, "depth_ft": 1 * IN,
        "height_ft": 1.0, "center": [-1.25 + 3 * IN, 0.0], "base_z_ft": 0.2}
ROD = {"shape": "cylinder", "name": "rod", "radius_ft": 0.25 * IN, "height_ft": 1.0,
       "center": [1.25 - 3 * IN, 0.0], "base_z_ft": 0.2}
PARAMS = {"Run": ("length", 2.5), "Inset": ("length", 3 * IN)}


def _spec(follow=None, symmetric=True):
    s = {"caption": "Run", "axis": "x", "lo": -1.25, "hi": 1.25, "symmetric": symmetric,
         "parts": {"strut": ("lo", "hi")}}
    if follow is not None:
        s["follow"] = follow
    return s


GOOD = {"caption": "Inset", "offset": 3 * IN,
        "followers": [{"part": "post", "side": "lo", "kind": "rigid", "half": 0.5 * IN},
                      {"part": "rod", "side": "hi", "kind": "circle"}]}


def _build(spec):
    return F.make_generic_model(parts=[dict(STRUT), dict(POST), dict(ROD)], name="f",
                                numeric_params=dict(PARAMS), drives=[spec])


def test_a_generic_follow_wires_a_box_and_a_circle():
    prod = _build(_spec(GOOD))
    (d,) = prod.drives
    assert d["follow"]["followers"] == 2 and d["follow"]["locks"] == 4
    lines, arcs, bad = _locks_on_planes(prod.doc)
    assert (arcs, bad) == (2, 0)


@pytest.mark.parametrize("follow", [
    dict(GOOD, offset=4 * IN),                                     # disagrees with Inset
    dict(GOOD, caption="Nope"),                                    # no such parameter
    dict(GOOD, followers=[{"part": "post", "side": "lo", "kind": "rigid",
                           "half": 0.75 * IN}]),                   # edges not at R +- h
    dict(GOOD, followers=[{"part": "rod", "side": "lo", "kind": "circle"}]),  # off-plane circle
    dict(GOOD, followers=[{"part": "ghost", "side": "lo", "kind": "circle"}]),
    dict(GOOD, followers=[{"part": "post", "side": "mid", "kind": "rigid", "half": 0.5 * IN}]),
    dict(GOOD, followers=[{"part": "post", "side": "lo", "kind": "spin"}]),
    dict(GOOD, followers=[{"part": "strut", "side": "lo", "kind": "rigid",
                           "half": 0.5 * IN}]),                    # already locked by Run
])
def test_a_refused_follow_leaves_the_drive_and_nothing_else(follow):
    prod = _build(_spec(follow))
    control = _build(_spec(None))
    (d,) = prod.drives
    assert "follow" not in d and d.get("symmetric")
    assert any("followers of 'Run' not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(control)


def test_a_follow_needs_symmetric_ends():
    prod = _build(_spec(GOOD, symmetric=False))
    assert "follow" not in prod.drives[0]
    assert any("mirrors through the symmetric ends" in n for n in prod.doc.notes)


def test_symmetric_ends_add_exactly_one_equality():
    prod = _build(_spec(None))
    control = F.make_generic_model(parts=[dict(STRUT), dict(POST), dict(ROD)], name="f",
                                   numeric_params=dict(PARAMS),
                                   drives=[_spec(None, symmetric=False)])
    eq = lambda p: [x for x in p.doc.by_class("LinearDimString")  # noqa: E731
                    if x.obj["m_flags"] == 140]
    assert len(eq(prod)) == 1 and len(eq(control)) == 0

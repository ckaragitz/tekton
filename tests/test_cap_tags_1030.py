"""#1030: an extrusion's cap tags follow its own Start / End (tag 0 = the End cap).

Our forms order Start / End by elevation (End = the top), so the cached solid
carries tag 0 on the top cap, as every born extrusion whose End is above its
Start does; the solid is still traced from the top (its [1,i,0] rails and side
frames there).  Every height lock (``height_law``: "end" = tag 0 -> the higher
plane) then witnesses the cap that lies on its plane.  Facts about the file
only: nothing here says Revit flexes it (hard rule 4).
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import archetypes as A  # noqa: E402
from rvt.famgen import cap_law as CL  # noqa: E402
from rvt.famgen import factory as F  # noqa: E402
from rvt.famgen import geometry as G  # noqa: E402

SQUARE = [[0.5, 0.5], [-0.5, 0.5], [-0.5, -0.5], [0.5, -0.5]]


def _caps(rep):
    faces = rep["m_subNodes"][0]["value"]["m_pFaces"]
    return [(f["value"]["m_GInfo"]["m_tag"], f["pid"]) for f in faces[:2]]


def _edge_caps(rep, edge_tag):
    geo = rep["m_subNodes"][0]["value"]
    pid2tag = {f["pid"]: f["value"]["m_GInfo"]["m_tag"] for f in geo["m_pFaces"]}
    (e,) = [e for e in geo["m_pEdges"] if e["value"]["m_GInfo"]["m_tag"] == edge_tag]
    return [pid2tag[w["weakref"]] for w in e["value"]["m_pFace"] if pid2tag[w["weakref"]] in (0, 1)]


def test_end_on_top_puts_tag_0_on_the_top_cap_and_keeps_the_rails():
    up = G.solid_box_brep(SQUARE, 2.0, 0.0, element_id=99, end_on_top=True)
    caps = CL.horizontal_cap_z(up)
    assert caps == {0: 2.0, 1: 0.0}
    assert _edge_caps(up, 3) == [0]                   # the [1,0,0] rail bounds the top = tag 0
    assert _edge_caps(up, 4) == [1]
    assert _caps(up)[0][0] == 0                       # the top cap is serialized first


def test_without_it_the_extrude_down_specimen_form_is_unchanged():
    down = G.solid_box_brep(SQUARE, 2.0, 0.0, element_id=99)
    assert CL.horizontal_cap_z(down) == {1: 2.0, 0: 0.0}
    assert _edge_caps(down, 3) == [1]


def test_box_face_names_the_top_as_the_end_cap():
    top, bottom = F.box_face("top"), F.box_face("bottom")
    assert (top["tag"], top["edges"]) == (0, [3, 6, 10, 14])
    assert (bottom["tag"], bottom["edges"]) == (1, [4, 7, 11, 15])
    with pytest.raises(KeyError):
        F.box_face("start")                           # ambiguous now: ask for top / bottom


def test_a_form_extrusion_tags_its_top_cap_0():
    prod = F.make_panelboard()
    ext = prod.forms[0].by_class("ExtrusionElem")[0]
    caps = CL.horizontal_cap_z(ext.rep)
    assert caps[0] > caps[1]


def _builds():
    yield "panelboard", F.make_panelboard
    yield "transformer", lambda: F.make_transformer(kva=45)
    for k in sorted(A.ARCHETYPES):
        yield k, (lambda k=k: F.make_archetype(product=k))


def test_every_height_lock_witnesses_the_cap_on_its_plane():
    rows, built = [], set()
    for name, build in _builds():
        try:
            doc = build().doc
        except Exception:                             # an archetype that does not build is not this law's
            if name in ("panelboard", "transformer"):
                raise
            continue
        built.add(name)
        got = CL.lock_face_findings(doc)
        if name in ("panelboard", "transformer"):
            assert got, f"{name} has no cap locks to judge"
        rows += [dict(r, family=name) for r in got]
    assert len(rows) >= 50                            # 179 locks at the time of writing
    off = [r for r in rows if not r["on_plane"]]
    assert not off, off[:5]

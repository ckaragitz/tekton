"""The in-plane parametric drive, authored the way Revit-born families store it
(#787 DONE 1, #904).

The owner's desktop verdict on the one-box probe pair (#787, 2026-10-01): both
the full law (P) and the control without the sketch regen edge (C) WIDENED when
Width went 2' 0" -> 3' 0" -- the first generated family whose parameter drove
its geometry.  These tests pin the law's fields (so a refactor cannot quietly
fall back to the chain that moved nothing, #372 / #901), the probe pair's
single variable, and the multi-part wiring the trapeze uses.  Nothing here
claims a family flexes: each lane needs its own desktop verdict (hard rule 4).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOX = {"shape": "box", "name": "body", "width_ft": 2.0, "depth_ft": 1.0, "height_ft": 1.5}


def _probe(regen_edge=True):
    prod = F.make_generic_model(parts=[dict(BOX)], name="DriveProbe", drive=True)
    rep = DL.apply_born_inplane_law(prod.doc, regen_edge=regen_edge)
    return prod.doc, rep


def test_the_born_law_fields_on_the_one_box_probe():
    doc, rep = _probe()
    locks = DL._sketch_locks(doc)
    assert len(locks) == 4 and len(rep["labelled"]) == 2
    for al in locks:                                   # view-less sketch locks
        assert al.obj["m_ownerDBViewId"] == -1 and al.header["m_ownerViewId"] == -1
        assert al.obj["m_dimVersion"] == DL.BORN_DIM_VERSION
    for dim in doc.by_class("LinearDimString"):
        assert dim.obj["m_dimVersion"] == DL.BORN_DIM_VERSION
        assert all(s["m_flags"] == 0 for s in dim.obj["m_ArrSegInfo"])
    assert not any(e.obj.get("m_constrInfo") for e in doc.elements)   # no back-edges
    assert all(e.obj["m_sideRefPlaneCurveBased"] for e in doc.by_class("ExtrusionElem"))
    assert len(rep["curves"]) == 4                     # every locked curve has the bit
    sk = doc.by_class("VarSketch")[0]
    regen = sk.header["m_parents"]["value"]["m_regenOnly"]
    assert set(rep["sketches"][sk.elem_id]["planes"]) <= set(regen)


def test_the_control_differs_only_in_the_regen_edge():
    p_doc, p = _probe(True)
    c_doc, c = _probe(False)
    (pk, pv), = p["sketches"].items()
    (ck, cv), = c["sketches"].items()
    assert pv["planes"] == cv["planes"] and cv["regen_after"] == cv["regen_before"]
    assert set(pv["regen_after"]) - set(cv["regen_after"]) == set(pv["planes"])
    size = lambda v: len(v) if isinstance(v, list) else v      # noqa: E731
    for k in ("locks", "labelled", "extrusions", "curves", "constr_info_cleared"):
        assert size(p[k]) == size(c[k]), k


def test_wire_linear_drive_on_both_axes():
    prod = F.make_generic_model(
        parts=[dict(BOX, name="a"), dict(BOX, name="b", center=[0.0, 2.0])],
        name="Two", numeric_params={"Run": ("length", 2.0), "Deep": ("length", 1.0)},
        drives=[{"caption": "Run", "axis": "x", "lo": -1.0, "hi": 1.0,
                 "parts": {"a": ("lo", "hi"), "b": ("lo", "hi")}},
                {"caption": "Deep", "axis": "y", "lo": -0.5, "hi": 0.5,
                 "parts": {"a": ("lo", "hi")}}])
    assert [d["caption"] for d in prod.drives] == ["Run", "Deep"]
    assert len(prod.drives[0]["locks"]) == 4 and len(prod.drives[1]["locks"]) == 2
    params = {e.elem_id for e in prod.doc.params.values()}
    labelled = [d for d in prod.doc.by_class("LinearDimString")
                if any(s["m_paramId"] in params for s in d.obj["m_ArrSegInfo"])]
    assert len(labelled) == 2
    for sk in prod.doc.by_class("VarSketch"):          # each lock registered on its sketch
        ids = set(sk.obj.get("m_dimIds") or [])
        assert ids <= set(sk.header["m_parents"]["value"]["m_deletion"])


def test_a_drive_naming_no_part_is_noted_never_raised():
    prod = F.make_generic_model(parts=[dict(BOX)], name="x",
                                numeric_params={"Run": ("length", 2.0)},
                                drives=[{"caption": "Run", "axis": "x", "lo": -1, "hi": 1,
                                         "parts": {"nope": ("lo",)}}])
    assert prod.drives == []
    assert any("not wired" in n for n in prod.doc.notes)


def test_the_trapeze_strut_length_moves_both_ends_of_every_tier():
    prod = F.make_archetype(product="strut_trapeze",
                            prompt="a 2 tier slotted trapeze with threaded rod")
    (d,) = prod.drives
    assert d["caption"] == "Strut Length" and d["axis"] == "x"
    # per tier: 2 webs + 2 lips both ends (8 locks) + the outer end of the
    # first and last back segments (2) = 10; two tiers = 20 locks on 12 parts
    assert d["targets"] == 12 and len(d["locks"]) == 20
    planes = {e.elem_id: e for e in prod.doc.by_class("RefPlane")}
    xs = sorted(planes[i].obj["m_freeEnd"][0] for i in d["planes"])
    assert xs == pytest.approx([-1.25, 1.25])          # the 30 in strut's ends
    assert not any(e.obj.get("m_constrInfo") for e in prod.doc.elements)


def test_a_solid_back_trapeze_drives_the_whole_back():
    prod = F.make_archetype(product="strut_trapeze",
                            dimensions={"slot_length_in": 0, "slot_spacing_in": 0, "tiers": 1})
    (d,) = prod.drives
    assert d["targets"] == 5 and len(d["locks"]) == 10  # back + 2 webs + 2 lips, both ends


def test_the_probe_tool_stages_a_pair_differing_in_one_field():
    out = tempfile.mkdtemp(prefix="t904_")
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "drive_probe.py"), out],
                          capture_output=True, text=True, timeout=600, cwd=ROOT)
    assert proc.returncode == 0, proc.stderr
    rep = json.load(open(os.path.join(out, "PROBE.json"), encoding="utf-8"))
    files = {f["file"]: f for f in rep["files"]}
    assert len(files) == 2 and all(f["errors"] == 0 for f in files.values())
    p = next(f for n, f in files.items() if "_P_" in n)
    c = next(f for n, f in files.items() if "_C_" in n)
    (ps,), (cs,) = p["sketches"].values(), c["sketches"].values()
    assert len(ps["regen_after"]) > len(cs["regen_after"]) == len(cs["regen_before"])


def test_a_document_carrying_the_law_gets_no_back_edges_at_all():
    """#907 review: finalize wrote 22 back-edges and the law then cleared them,
    leaving two contradicting notes; a law-carrying document skips the step."""
    prod = F.make_archetype(product="strut_trapeze",
                            prompt="a 2 tier slotted trapeze with threaded rod")
    assert not any("back-edges:" in n for n in prod.doc.notes)
    assert any("0 back-edges cleared" in n for n in prod.doc.notes)


def test_planes_that_disagree_with_their_parameter_are_refused_by_name():
    prod = F.make_generic_model(parts=[dict(BOX)], name="x",
                                numeric_params={"Run": ("length", 2.0)},
                                drives=[{"caption": "Run", "axis": "x", "lo": -1.5,
                                         "hi": 1.5, "parts": {"body": ("lo", "hi")}}])
    assert prod.drives == []
    assert any("Run" in n and "not wired" in n for n in prod.doc.notes)

"""The panelboard's Width / Depth / Height through drive_law (#914 DONE 3).

The catalog panelboard used to carry the #372 first-solid chain
(``param_drive.wire_panelboard_drive``): Width and Depth labelled on the
enclosure alone, its front parts (#892) and clearance zones (#882) left where
they were drawn.  Now (``make_panelboard(drive="law")``, the default):

* **Width** is a symmetric in-plane drive (``drive_law.wire_linear_drive`` +
  ``wire_symmetric``; the box is centred in x) on the enclosure, every
  full-width part and the top clearance zone; the door (and a flush trim) span
  it at fixed insets, the hinges ride +x and the latch -x (``wire_attach``).
* **Depth** is ONE-SIDED: the fixed face is held on the origin centre plane --
  a surface box's back, a flush box's front (``wire_linear_drive(lo_plane= /
  hi_plane=)``) -- and a surface box's front parts and working space ride the
  face plane.
* **Height** is the #787 Case B cap-face chain (``height_law``): origin ->
  cabinet top, with the faces that belong to the top riding it by locked
  heights.
* The Revit-born in-plane law runs after ``finalize`` and no back-edges are
  written.

Every refusal leaves the written file byte-identical to the build without the
refused spec.  ``drive="372"`` keeps the old chain; ``drive=None`` wires none.
Nothing here claims the family flexes in Revit: the assembled panelboard, the
anchored one-sided drive and every Case B height have no desktop verdict (hard
rule 4).  The written-file read-back on 2026 and 2025 (every sketch lock on
its plane, ``constraint_law.check_file == []``) is in
``tests/test_panel_drives_914.py``.
"""
from __future__ import annotations

import copy
import hashlib
import os
import shutil
import tempfile

import pytest

from rvt.famgen import constraint_law as CL
from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F


def _sha(prod) -> str:
    d = tempfile.mkdtemp(prefix="t914law_")
    try:
        path = os.path.join(d, "f.rfa")
        res = prod.write(path)
        assert (res.get("validate") or {}).get("family_mode", {}).get("n_errors") == 0, res
        return hashlib.sha256(open(path, "rb").read()).hexdigest()
    finally:
        shutil.rmtree(d, True)


def _counts(doc):
    return {c: len(doc.by_class(c)) for c in ("RefPlane", "Alignment", "LinearDimString")}


# --------------------------------------------------------------------------- the wired chain

EXPECT = {
    # (Width locks, Width attach (parts, planes, locks), Depth locks, Depth anchored end,
    #  Depth attach (parts, planes, locks) or None, heights (wired, face locks, locked))
    "surface": (6, (4, 6, 8), 4, ["lo"], (7, 7, 14), (7, 11, 6)),
    "flush": (4, (5, 8, 10), 4, ["hi"], None, (8, 10, 7)),
}


@pytest.mark.parametrize("mounting", ["surface", "flush"])
def test_width_depth_and_height_are_wired_with_the_front_riding(mounting):
    prod = F.make_panelboard(name="L914", mounting=mounting)
    w_locks, w_att, d_locks, anchored, d_att, (hw, hf, hl) = EXPECT[mounting]
    width, depth = prod.drives
    assert (width["caption"], width["axis"], width["symmetric"]) == ("Width", "x", True)
    assert len(width["locks"]) == w_locks
    att = width["attach"]
    assert (att["parts"], att["planes"], att["locks"]) == w_att
    assert (depth["caption"], depth["axis"], depth.get("symmetric")) == ("Depth", "y", None)
    assert len(depth["locks"]) == d_locks and depth["anchored"] == anchored
    if d_att is None:
        assert "attach" not in depth          # a flush box's face is the wall: nothing rides
    else:
        att = depth["attach"]
        assert (att["parts"], att["planes"], att["locks"]) == d_att
    h = prod.heights
    assert (h["wired"], h["refused"], h["face_locks"], h["locked_unlabelled"]) == (hw, [], hf, hl)
    assert h["captions"] == ["Height"]
    doc = prod.doc
    assert doc.born_drive_law is True
    assert not any(e.obj.get("m_constrInfo") for e in doc.elements)   # the born law: none
    assert all(int(a.obj["m_ownerDBViewId"]) == -1 for a in DL._sketch_locks(doc))
    assert CL.check_doc(doc) == []
    assert not any("not wired" in n or "not made" in n or "NOT wired" in n
                   for n in doc.notes), doc.notes


def test_the_depth_drive_holds_its_fixed_face_on_the_origin_plane():
    """The one-sided Depth: the labelled dimension witnesses the origin centre
    plane (y = 0, the wall plane) and the box's back edge is locked to it."""
    prod = F.make_panelboard(name="L914O")
    doc = prod.doc
    origin = DL.origin_centre_plane(doc, "y")
    _width, depth = prod.drives
    assert depth["planes"][0] == origin.elem_id
    dim = next(e for e in doc.elements if e.elem_id == depth["dim"])
    assert origin.elem_id in DL._witness_ids(dim)
    on_origin = [a for a in DL._sketch_locks(doc) if origin.elem_id in DL._witness_ids(a)]
    assert len(on_origin) == 2               # the enclosure's back, the top zone's back
    assert any("anchored on the origin plane (one-sided; no desktop verdict)" in n
               for n in doc.notes), doc.notes


def test_the_specs_name_who_rides_what():
    """Read off the geometry: the hinges (+x) ride the high Width end, the
    latch (-x) the low one, the door spans; the nameplate (centred, narrow)
    and the working space (its width is the code minimum) stay in x; on a
    surface box every front part and the working space ride the face."""
    prod = F.make_panelboard(name="L914R")
    from rvt.famgen import equipment_detail as ED
    W, D, H = (prod.doc.types[prod.doc.current_type][1][prod.doc.params[c].elem_id]
               for c in ("Width", "Depth", "Height"))
    parts = ED.panelboard_parts(W, D, H)
    detail = prod.forms[1:1 + len(parts)]
    named = F._panelboard_named_forms(prod.forms[0], parts, detail, prod.forms[1 + len(parts):])
    width, depth = F._panelboard_drive_specs(W, D, H, flush=False, named=named,
                                             top_zone_h=1.0)[0]
    assert width["attach"] == {"lo": ["door latch handle"],
                               "hi": ["door hinge low", "door hinge high"], "span": ["door"]}
    assert set(width["parts"]) == {"enclosure", "front trim", "clearance: top"}
    assert depth["lo_plane"] == "origin" and set(depth["parts"]) == {"enclosure",
                                                                     "clearance: top"}
    assert depth["attach"]["hi"] == ["front trim", "door", "door hinge low", "door hinge high",
                                     "door latch handle", "nameplate",
                                     "clearance: front working space"]


def test_a_panel_without_its_front_drives_the_enclosure_alone():
    """solid=False draws no front and no clearance zones: the drives carry the
    enclosure only, and nothing rides."""
    prod = F.make_panelboard(name="L914D", solid=False)
    width, depth = prod.drives
    assert len(width["locks"]) == 2 and "attach" not in width and width["symmetric"]
    assert len(depth["locks"]) == 2 and "attach" not in depth
    assert prod.heights["wired"] == 1 and prod.heights["face_locks"] == 2
    assert CL.check_doc(prod.doc) == []


def test_multi_type_notes_say_what_the_rows_label():
    prod = F.make_panelboard(name="L914T", types=["225A", "400A"])
    assert len(prod.drives) == 2
    assert not any("geometry is not label-driven yet" in n for n in prod.notes)
    assert any("labelled by the rows' Width / Depth / Height" in n
               and "UNVERIFIED" in n for n in prod.notes)


# --------------------------------------------------------------------------- the old chain, kept

def test_the_old_372_chain_is_kept_behind_the_flag():
    prod = F.make_panelboard(name="L914C", drive="372")
    doc = prod.doc
    assert prod.drives == [] and prod.heights == {}
    assert not getattr(doc, "born_drive_law", False)
    c = _counts(doc)
    assert (c["Alignment"], c["LinearDimString"]) == (4, 2)
    assert CL.check_doc(doc) == []


def test_no_drive_wires_nothing():
    prod = F.make_panelboard(name="L914N", drive=None)
    c = _counts(prod.doc)
    assert (c["Alignment"], c["LinearDimString"]) == (0, 0)
    with pytest.raises(F.FactoryError):
        F.make_panelboard(name="L914X", drive="flex")


# --------------------------------------------------------------------------- refusals

REAL = F._panelboard_drive_specs


def _build(monkeypatch, edit, name="L914S", **kw):
    def specs(*a, **k):
        d, h = REAL(*a, **k)
        d, h = copy.deepcopy(d), copy.deepcopy(h)
        edit(d, h)
        return d, h
    monkeypatch.setattr(F, "_panelboard_drive_specs", specs)
    try:
        return F.make_panelboard(name=name, **kw)
    finally:
        monkeypatch.setattr(F, "_panelboard_drive_specs", REAL)


def _drop(i):
    def edit(d, _h):
        del d[i]
    return edit


@pytest.mark.parametrize("bad, control", [
    # Width: a part name that matches nothing
    (lambda d, h: d[0]["parts"].update({"no such part": ("lo", "hi")}), _drop(0)),
    # Width: planes that disagree with the Width row
    (lambda d, h: d[0].update(lo=d[0]["lo"] - 0.1), _drop(0)),
    # Depth: the anchor plane is not at the drive's fixed end
    (lambda d, h: d[1].update(lo=0.1, hi=d[1]["hi"] + 0.1), _drop(1)),
    # Depth: an anchor that is not the origin plane
    (lambda d, h: d[1].update(lo_plane="somewhere"), _drop(1)),
])
def test_a_refused_drive_leaves_the_file_byte_identical(monkeypatch, bad, control):
    prod = _build(monkeypatch, bad)
    ref = _build(monkeypatch, control)
    assert len(prod.drives) == 1
    assert any("not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(ref)


def test_a_refused_attach_keeps_its_drive_and_touches_nothing_else(monkeypatch):
    def bad(d, _h):
        d[0]["attach"]["hi"] = d[0]["attach"]["hi"] + ["no such part"]

    def control(d, _h):
        del d[0]["attach"]
    prod = _build(monkeypatch, bad)
    ref = _build(monkeypatch, control)
    assert len(prod.drives) == 2 and "attach" not in prod.drives[0]
    assert any("parts attached to 'Width' not wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(ref)


def test_a_refused_height_leaves_the_file_byte_identical(monkeypatch):
    def bad(_d, h):
        h[-1]["lo" if h[-1]["hi"] == "cabinet top" else "hi"] = 99.0   # off every face

    def control(_d, h):
        del h[-1]
    prod = _build(monkeypatch, bad)
    ref = _build(monkeypatch, control)
    assert prod.heights["refused"] and prod.heights["wired"] == ref.heights["wired"]
    assert _sha(prod) == _sha(ref)


def test_every_spec_refused_is_the_undriven_panelboard(monkeypatch):
    def bad(d, h):
        for s in d:
            s["caption"] = "PanelName"                # not a length: every drive refused
        h[:] = [dict(h[0], hi=h[0]["hi"] + 1.0)]      # off the cap faces
    prod = _build(monkeypatch, bad)
    assert prod.drives == [] and prod.heights["wired"] == 0
    assert any("panelboard drives NOT wired" in n for n in prod.doc.notes)
    assert _sha(prod) == _sha(F.make_panelboard(name="L914S", drive=None))


# --------------------------------------------------------------------------- the anchored end

def _doc_with_box():
    from rvt.famgen import skeleton as SK
    doc = SK.new_family_document("generic_model", "A914", work_plane_based=False)
    F._num(doc, "Depth", "length", "dimensions")
    doc.add_type("A914", {doc.params["Depth"].elem_id: 1.0})
    fb = F.add_box_form(doc, 2.0, 1.0, 1.0, center=(0.0, 0.5))
    sk = next(e for e in fb.elements if e.class_name == "VarSketch")
    return doc, sk


@pytest.mark.parametrize("kw, match", [
    ({"lo": 0.0, "hi": 1.0, "hi_plane": "origin"}, "not the y = 1 ft plane"),
    ({"lo": 0.0, "hi": 1.0, "lo_plane": "foreign"}, "not in this document"),
    ({"lo": 0.0, "hi": 1.0, "lo_plane": "origin", "hi_plane": "origin"}, "both ends"),
])
def test_an_anchor_off_its_end_is_refused_before_any_mutation(kw, match):
    doc, sk = _doc_with_box()
    origin = DL.origin_centre_plane(doc, "y")
    foreign = copy.copy(origin)
    foreign.elem_id = 987654
    pick = {"origin": origin, "foreign": foreign}
    for end in ("lo_plane", "hi_plane"):
        if end in kw:
            kw[end] = pick[kw[end]]
    before = ([e.elem_id for e in doc.elements], len(doc.refplanes),
              list(sk.obj.get("m_dimIds") or []))
    with pytest.raises(ValueError, match=match):
        DL.wire_linear_drive(doc, caption="Depth", axis="y",
                             targets=[(sk, ("lo", "hi"))], **kw)
    assert ([e.elem_id for e in doc.elements], len(doc.refplanes),
            list(sk.obj.get("m_dimIds") or [])) == before


def test_a_horizontal_plane_is_never_an_anchor_or_an_origin_centre():
    """#931 review: a plane whose ends sit at y = 0 but whose normal is +-z
    (the origin elevation plane's shape) passed the ends-only check."""
    doc, sk = _doc_with_box()
    origin = DL.origin_centre_plane(doc, "y")
    origin.obj["m_freeEnd"] = [-5.0, 0.0, 0.0]
    origin.obj["m_bubbleEnd"] = [5.0, 0.0, 0.0]
    origin.obj["m_cutVec"] = [0.0, 1.0, 0.0]          # normal = (10,0,0) x (0,1,0) = +z
    before = ([e.elem_id for e in doc.elements], len(doc.refplanes))
    with pytest.raises(ValueError, match="not square to y"):
        DL.wire_linear_drive(doc, caption="Depth", axis="y", lo=0.0, hi=1.0,
                             targets=[(sk, ("lo", "hi"))], lo_plane=origin)
    assert ([e.elem_id for e in doc.elements], len(doc.refplanes)) == before
    with pytest.raises(ValueError, match="no origin centre plane"):
        DL.origin_centre_plane(doc, "y")


def test_an_anchored_end_adds_one_plane_not_two():
    doc, sk = _doc_with_box()
    origin = DL.origin_centre_plane(doc, "y")
    n = len(doc.refplanes)
    rep = DL.wire_linear_drive(doc, caption="Depth", axis="y", lo=0.0, hi=1.0,
                               targets=[(sk, ("lo", "hi"))], lo_plane=origin)
    assert len(doc.refplanes) == n + 1 and rep["planes"][0] == origin.elem_id
    assert rep["anchored"] == ["lo"]
    assert CL.check_doc(doc) == []

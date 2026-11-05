"""#1085: every extrusion we author is side-ref-plane curve based, driven or not.

The born corpus carries ``ExtrusionElem.m_sideRefPlaneCurveBased`` True on
2,161 of 2,161 extrusions (counted by the #796 self-battery's conformance
instrument; the specimens themselves are quarantined and never named). Until
#1085 only the drive law (#904 item 4) set it, so every UNDRIVEN extrusion --
part shapes, prisms, the fan-powered box -- kept False and failed conformance.

Fresh-clone safe: every family is built from the tracked genesis bases.
"""
import os

import pytest

from rvt.famgen import drive_law as DL
from rvt.famgen import factory as F
from rvt.famgen import fan_powered as FPB
from rvt.famgen import revolve as RV


def _part(shape, **kw):
    part = {"name": f"p {shape}", "shape": shape, "height_ft": 1.2, "base_z_ft": 0.0,
            "center": [0.0, 0.0], "width_ft": 1.0, "depth_ft": 0.8, "diameter_ft": 0.8,
            "radius_ft": 0.4, "length_ft": 2.0, "top_radius_ft": 0.2, "segments": 3,
            "vertices": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.5, 0.4], [0.0, 1.0]]}
    part.update(kw)
    return part


def _extrusions(prod):
    exs = list(prod.doc.by_class("ExtrusionElem"))
    assert exs, "the family authored no extrusion, so this test would prove nothing"
    return exs


SHAPES = tuple(F.GENERIC_PART_SHAPES) + tuple(RV.COMPOSITE_SHAPES)


@pytest.mark.parametrize("shape", SHAPES)
def test_every_undriven_part_shape_extrusion_is_side_ref_plane_curve_based(shape):
    prod = F.make_generic_model(parts=[_part(shape)], name=f"Side {shape}", source="1085")
    assert not getattr(prod, "drives", None), "the part-shape lane must stay undriven here"
    bad = [e.elem_id for e in _extrusions(prod)
           if e.obj.get("m_sideRefPlaneCurveBased") is not True]
    assert bad == [], f"{shape}: extrusions still False: {bad}"


@pytest.mark.parametrize("footprint", [{"width_ft": 1.0, "depth_ft": 0.8},
                                       {"vertices": [[0.0, 0.0], [1.0, 0.0], [1.0, 1.0],
                                                     [0.5, 0.4], [0.0, 1.0]]}],
                         ids=["rect", "ring"])
def test_the_single_prism_without_its_drive_is_side_ref_plane_curve_based(footprint):
    """``prism_drive=None`` is the undriven prism (the drive law never runs)."""
    prod = F.make_generic_model(height_ft=1.2, name="Prism", source="1085",
                                prism_drive=None, **footprint)
    assert all(e.obj["m_sideRefPlaneCurveBased"] is True for e in _extrusions(prod))


@pytest.mark.parametrize("kind", ["series", "parallel"])
def test_the_fan_powered_box_extrusions_are_side_ref_plane_curve_based(kind):
    prod = FPB.make_fan_powered_box(kind=kind)
    exs = _extrusions(prod)
    assert len(exs) > 3
    assert [e.elem_id for e in exs if e.obj["m_sideRefPlaneCurveBased"] is not True] == []


def test_the_drive_law_flip_is_now_a_no_op_on_our_own_extrusions():
    """The drive law's item 4 stays (a document authored before #1085 still
    gets the field), but on an extrusion we author it no longer changes
    anything -- before #1085 it reported the undriven box's extrusion here."""
    prod = F.make_generic_model(parts=[_part("box")], name="Undriven", source="1085")
    rep = DL.apply_born_inplane_law(prod.doc)
    assert rep["extrusions"] == []
    assert all(e.obj["m_sideRefPlaneCurveBased"] is True for e in _extrusions(prod))


def test_the_drive_law_still_flips_a_false_extrusion():
    """The law is still the safety net: an extrusion left False (e.g. by an
    older document) is set True and reported, so the flip cannot rot silently."""
    prod = F.make_generic_model(parts=[_part("box")], name="Old", source="1085")
    ex = _extrusions(prod)[0]
    ex.obj["m_sideRefPlaneCurveBased"] = False
    rep = DL.apply_born_inplane_law(prod.doc)
    assert rep["extrusions"] == [ex.elem_id]
    assert ex.obj["m_sideRefPlaneCurveBased"] is True


def test_the_field_survives_the_write_and_read_back(tmp_path):
    """Authored True must still read True from the written file, under its own
    release -- the property is about the file, not the in-memory object."""
    from rvt.famgen import conformance as CO
    path = str(tmp_path / "box.rfa")
    F.make_generic_model(parts=[_part("box")], name="Read", source="1085").write(
        path, validate=False, provenance=False)
    assert os.path.getsize(path) > 0
    _note, objs, counters = CO.iter_objects(path, ("ExtrusionElem",))
    assert counters == {"undecoded_records": 0, "partial_records": 0}
    assert objs and all(o.get("m_sideRefPlaneCurveBased") is True for _id, _cls, o in objs)

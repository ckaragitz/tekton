"""The parametric spine (#689): declare what a family is parametric in, get
the drive chain derived from that declaration.

These tests are all plan-level -- no document is built -- which is the point
of the module: a caller can see exactly what a parameter would add before
authoring anything.
"""
import pytest

from rvt.famgen import famdim
from rvt.famgen.parametric import (
    GROUP_DIMENSIONS, OUT_OF_PLANE_GAP, SPEC_LENGTH, SPEC_NUMBER,
    DrivenAxis, FreeParam, ParametricModel, box_model, check_model, explain,
    plan, template_binding,
)


def _box():
    return box_model("electrical_equipment", width=2.0, height=1.5)


# ---------------------------------------------------------------------------
# the declaration
# ---------------------------------------------------------------------------

def test_a_plain_box_model_is_authorable():
    m = _box()
    assert check_model(m) == []
    p = plan(m)
    assert p["authorable"] is True
    assert p["counts"] == {"axes": 2, "free_params": 0,
                           "reference_planes": 4, "labelled_dimensions": 2,
                           "parameters": 2, "alignments": 4}


def test_planes_are_placed_symmetrically_about_the_centre():
    p = plan(_box())
    width = [pl for pl in p["reference_planes"] if pl["axis"] == "width"]
    assert sorted(pl["offset"] for pl in width) == [-1.0, 1.0]
    height = [pl for pl in p["reference_planes"] if pl["axis"] == "height"]
    assert sorted(pl["offset"] for pl in height) == [-0.75, 0.75]


def test_the_dimension_is_authored_at_the_declared_size():
    p = plan(_box())
    by_param = {d["parameter"]: d for d in p["labelled_dimensions"]}
    assert by_param["Width"]["value"] == 2.0
    assert by_param["Height"]["value"] == 1.5
    assert all(d["labelled"] for d in p["labelled_dimensions"])


# ---------------------------------------------------------------------------
# "associate any parameter at any time"
# ---------------------------------------------------------------------------

def test_adding_a_free_parameter_changes_only_the_parameter_list():
    before = plan(_box())
    after = plan(_box().with_param(FreeParam("Load Rating", spec=SPEC_NUMBER)))
    assert after["counts"]["free_params"] == 1
    assert after["counts"]["parameters"] == before["counts"]["parameters"] + 1
    # no geometry is disturbed by a non-driving parameter
    assert after["reference_planes"] == before["reference_planes"]
    assert after["labelled_dimensions"] == before["labelled_dimensions"]


def test_adding_a_driven_axis_adds_planes_a_dimension_and_alignments():
    m = ParametricModel(
        category="generic_model",
        axes=(DrivenAxis("width", "Width", (1, 0, 0), 2.0),))
    before = plan(m)
    after = plan(m.with_axis(DrivenAxis("height", "Height", (0, 1, 0), 1.0)))
    assert after["counts"]["reference_planes"] == before["counts"]["reference_planes"] + 2
    assert after["counts"]["labelled_dimensions"] == before["counts"]["labelled_dimensions"] + 1
    assert after["counts"]["alignments"] == before["counts"]["alignments"] + 2


def test_models_are_immutable():
    m = _box()
    m.with_param(FreeParam("X"))
    assert m.parameter_names == ("Width", "Height")   # unchanged


def test_without_removes_by_name():
    m = _box().with_param(FreeParam("Scratch"))
    assert "Scratch" in m.parameter_names
    assert "Scratch" not in m.without("Scratch").parameter_names
    assert "Width" not in m.without("Width").parameter_names


def test_a_free_parameter_with_no_known_value_stays_empty():
    # steer S-2026-08-11-a: an empty standard parameter is correct, an
    # invented value is not.
    p = plan(_box().with_param(FreeParam("Voltage", spec=SPEC_NUMBER)))
    volt = next(q for q in p["parameters"] if q["name"] == "Voltage")
    assert volt["value"] is None
    assert volt["drives"] is None


# ---------------------------------------------------------------------------
# the gate
# ---------------------------------------------------------------------------

def test_out_of_plane_axis_is_named_not_authored():
    m = _box().without("Height").with_axis(
        DrivenAxis("depth", "Depth", (0, 0, 1), 0.5))
    problems = check_model(m)
    assert len(problems) == 1
    assert "out of the sketch plane" in problems[0]
    assert OUT_OF_PLANE_GAP in problems[0]
    assert plan(m)["authorable"] is False


def test_parallel_axes_are_rejected():
    m = _box().with_axis(DrivenAxis("w2", "Width2", (2, 0, 0), 1.0))
    assert any("are parallel: they would drive" in t for t in check_model(m))


def test_a_z_axis_is_not_reported_as_parallel_to_x_and_y():
    # the full 3-D cross product matters: using only its z component reads
    # any z axis as parallel to both in-plane axes and buries the real
    # complaint under two false ones.
    m = _box().with_axis(DrivenAxis("depth", "Depth", (0, 0, 1), 0.5))
    # NB match the parallel complaint exactly: OUT_OF_PLANE_GAP itself
    # contains the word "parallel", so a loose substring match passes
    # for the wrong reason.
    assert not any("are parallel: they would drive" in t
                   for t in check_model(m))


def test_a_diagonal_in_plane_axis_is_fine():
    m = _box().with_axis(DrivenAxis("diag", "Diagonal", (1, 1, 0), 1.0))
    assert check_model(m) == []


@pytest.mark.parametrize("value", [0.0, -1.0])
def test_non_positive_size_is_rejected(value):
    m = ParametricModel(category="generic_model",
                        axes=(DrivenAxis("w", "Width", (1, 0, 0), value),))
    assert any("not positive" in t for t in check_model(m))


def test_duplicate_parameter_names_are_rejected():
    m = _box().with_param(FreeParam("Width"))
    assert any("declared twice" in t or "already used" in t
               for t in check_model(m))
    m2 = ParametricModel(
        category="generic_model",
        axes=(DrivenAxis("a", "Size", (1, 0, 0), 1.0),
              DrivenAxis("b", "Size", (0, 1, 0), 1.0)))
    assert any("already used" in t for t in check_model(m2))


def test_zero_direction_is_rejected():
    m = ParametricModel(category="generic_model",
                        axes=(DrivenAxis("w", "W", (0, 0, 0), 1.0),))
    assert any("zero vector" in t for t in check_model(m))


def test_asymmetric_axis_is_refused_with_its_reason():
    m = ParametricModel(
        category="generic_model",
        axes=(DrivenAxis("w", "W", (1, 0, 0), 1.0, symmetric=False),))
    assert any("m_fixedRefs" in t and "P3" in t for t in check_model(m))


def test_below_minimum_is_rejected():
    m = ParametricModel(
        category="generic_model",
        axes=(DrivenAxis("w", "W", (1, 0, 0), 0.5, minimum=1.0),))
    assert any("below its minimum" in t for t in check_model(m))


# ---------------------------------------------------------------------------
# the template binding
# ---------------------------------------------------------------------------

def test_template_binding_resolves_a_known_category():
    b = template_binding("electrical_equipment")
    assert b["category_id"] == -2001040
    assert b["evidence"] in ("rft", "resolver")


def test_template_binding_never_raises_on_an_unknown_category():
    # hard rule 1: a caller must still be able to deliver.
    b = template_binding("not_a_real_category_at_all")
    assert b["category_id"] is None
    assert b["notes"]


def test_plan_carries_the_binding():
    p = plan(_box())
    assert p["binding"]["category_id"] == -2001040


# ---------------------------------------------------------------------------
# honesty about the driver
# ---------------------------------------------------------------------------

def test_the_driver_status_never_claims_the_family_flexes():
    p = plan(_box())
    assert p["driver"]["rung"] == famdim.DEFAULT_RUNG
    assert "HYPOTHESIS" in p["driver"]["status"]
    assert "no desktop verdict" in p["driver"]["status"]


def test_explain_mentions_the_rung_and_the_parameters():
    text = explain(_box().with_param(FreeParam("Voltage", spec=SPEC_NUMBER)))
    assert "Width drives width" in text
    assert "Voltage: empty" in text
    assert famdim.DEFAULT_RUNG in text


def test_explain_lists_problems_when_not_authorable():
    m = _box().with_axis(DrivenAxis("depth", "Depth", (0, 0, 1), 0.5))
    text = explain(m)
    assert "NOT AUTHORABLE AS DECLARED" in text


def test_specs_and_groups_are_format_vocabulary():
    assert SPEC_LENGTH.startswith("autodesk.spec")
    assert GROUP_DIMENSIONS.startswith("autodesk.parameter.group:")
    p = plan(_box())
    assert all(q["spec"].startswith("autodesk.") for q in p["parameters"])


# ---------------------------------------------------------------------------
# the driver tables themselves (#689): WHICH table, and HOW it is keyed
# ---------------------------------------------------------------------------

def test_the_ladder_is_the_p_series_with_a_control():
    assert set(famdim.RUNGS) == {"P0", "P1", "P2", "P3", "P4"}
    assert famdim.DEFAULT_RUNG == "P2"
    assert famdim.LADDER[0] == "P2"          # most-likely first
    assert famdim.LADDER[-1] == "P0"         # the control
    assert "CONTROL" in famdim.RUNGS["P0"][1]


def test_p0_is_empty_and_p1_is_the_parameter_binding():
    # P0 must add nothing: it is the control that must NOT flex.
    assert "nothing" in famdim.RUNGS["P0"][0]
    assert "m_paramExprs" in famdim.RUNGS["P1"][0]


def test_the_drive_lives_in_param_exprs_not_driven_dim_segs():
    # read off the schema: m_drivenDimSegs is an expression in OTHER DIMENSION
    # SEGMENTS (dim-to-dim equality), m_paramExprs is the expression in
    # PARAMETERS.  A ladder that opens on m_drivenDimSegs is aimed at the
    # wrong table -- that was the first cut's mistake and must not come back.
    assert "m_drivenDimSegs" not in famdim.RUNGS["P1"][0]
    assert "m_drivenDimSegs" not in famdim.RUNGS["P2"][0]
    assert "m_drivenDimSegs" in famdim.RUNGS["P4"][0]


def test_param_expr_is_keyed_by_the_element_not_the_parameter():
    # ParamExpr is an expression IN parameters, owned by the element whose
    # value it computes.  Keying it by the parameter had the relation
    # backwards; m_elemId must be the dimension.
    expr = famdim._param_expr(param_id=77, elem_id=42)
    assert expr["m_elemId"] == 42
    assert expr["m_elemId"] != 77
    assert expr["m_entries"] == [{"m_coef": 1.0, "m_paramId": 77}]


def test_unknown_rung_is_rejected():
    class _Doc:
        elements = []
    with pytest.raises(ValueError):
        famdim.driver_tables(_Doc(), rung="D1")   # the retired name


def test_the_constr_info_unknown_is_still_recorded():
    # the templates did NOT settle it, and the note must say so rather than
    # implying the question is closed.
    assert famdim.UNKNOWN_NEEDS_SPECIMEN
    assert any("m_constrInfo" in t for t in famdim.UNKNOWN_NEEDS_SPECIMEN)

"""test_famgen_size_bound_806.py -- a generated body has an upper size bound.

#806, found by the standing test/debug loop (#805) hunting adversarial spec
sheets. The constructors refused `<= 0` and nothing else, so a sheet row
reading `999999999999 in` built a family 15.8 million miles tall, wrote
229 KB, validated **VALID with 0 errors**, and carried `provenance: fact`
cited to the user's own document. Every gate we had passed it.

WHAT THE BOUND IS AND IS NOT. `MAX_BODY_FT` is a **sanity bound, not a mined
format law**: `rvt.validate` has no magnitude rule, `docs/writer/` records no
extent limit, and nothing here has been checked against Autodesk's reader
(hard rule 4). It is a floor on absurdity -- a body bigger than this is a
misparsed row, a metre/millimetre mix-up or a typo far more often than a
product anyone makes. These tests pin that behaviour, never that Revit
accepts everything below it.

WHY BOTH ENTRY POINTS ARE TESTED. The defect surfaced through the spec sheet
but lives in `famgen.factory`, so it reaches the IFC assembly lane and any
`generic_model` famspec too. A test that only drove the sheet would leave the
constructor unguarded for every other caller.
"""
import os

import pytest

from rvt.famgen import factory as F

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: the repro from #806, in feet
ABSURD_FT = 83_333_333_333.25


def _ok(**kw):
    return dict(dict(height_ft=5.0, width_ft=1.7, depth_ft=0.5, name="T"), **kw)


# ===========================================================================
# 1. the constructor
# ===========================================================================

def test_a_normal_body_still_builds():
    """The control: the bound must not cost the ordinary case."""
    prod = F.make_generic_model(**_ok())
    assert len(prod.doc.elements) > 0


@pytest.mark.parametrize("field", ["height_ft", "width_ft", "depth_ft"])
def test_an_absurd_dimension_is_REFUSED_BY_NAME(field):
    """All three, not just height.

    A sheet that misparses one row usually misparses one, not all three, so
    bounding only the height would still ship the body.
    """
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(**_ok(**{field: ABSURD_FT}))
    msg = str(e.value)
    assert field in msg
    assert "sanity bound" in msg
    # the VALUE and the BOUND both appear -- "too large" without the numbers
    # leaves the caller guessing which input was wrong
    assert "83,333,333,333" in msg and "105,600" in msg
    assert "#806" in msg


def test_a_body_just_under_the_bound_is_allowed():
    """The bound is a floor on absurdity, not a taste test: something huge
    but conceivable must still build, or the refusal starts costing real work.
    """
    prod = F.make_generic_model(**_ok(height_ft=F.MAX_BODY_FT - 1.0))
    assert len(prod.doc.elements) > 0


def test_the_multipart_path_is_bounded_too():
    """`parts=[...]` is a different code path with its own `<= 0` check."""
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="T", parts=[
            {"shape": "box", "width_ft": 1, "depth_ft": 1,
             "height_ft": ABSURD_FT}])
    assert "sanity bound" in str(e.value)


def test_zero_and_negative_are_still_refused():
    """The pre-existing low bound must survive the new high one."""
    for bad in (0, -5):
        with pytest.raises(F.FactoryError):
            F.make_generic_model(**_ok(height_ft=bad))


# ===========================================================================
# 1b. the gaps the first version of this fix left -- found by #808's review
#     AFTER four mutants and a green CI already said it was complete
# ===========================================================================

#: Each pair puts the assembly's EXTENT past the bound while keeping every
#: coordinate well inside it (+/-53,000 ft, bound 105,600), so these cases
#: can only be caught by the bounding-box check and never by the
#: distance-from-origin check. Without that separation the two guards mask
#: each other and deleting either leaves the tests green (#808 round 2).
@pytest.mark.parametrize("first,second", [
    ({"center": (-53_000, 0)}, {"center": (53_000, 0)}),    # X
    ({"center": (0, -53_000)}, {"center": (0, 53_000)}),    # Y
    ({"base_z_ft": -53_000},   {"base_z_ft": 53_000}),      # Z
], ids=["x", "y", "z"])
def test_the_ASSEMBLY_bounding_box_is_bounded_on_EVERY_axis(first, second):
    """All three axes, because only X was pinned.

    #808's round-2 reviewer deleted the `overall depth` and `overall height`
    lines and all 19 tests still passed -- the code was right, the test was
    one-axis.
    """
    box = {"shape": "box", "width_ft": 1, "depth_ft": 1, "height_ft": 1}
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="T", parts=[dict(box, **first),
                                              dict(box, **second)])
    assert "overall" in str(e.value), "caught by the wrong guard: " + str(e.value)


def test_a_NON_FINITE_center_cannot_slip_the_bbox():
    """`min`/`max` SKIP NaN rather than propagating it.

    So one part at `center=(nan, 0)` left `x0=+inf, x1=-inf` and `W=-inf`,
    which is not `> MAX_BODY_FT` and slipped the guard: the family BUILT,
    wrote a VALID 225,280-byte file, and its type row read `Width = -inf ft`.
    That is #806's exact symptom, one field over from where it was fixed.
    """
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="T", parts=[
            {"shape": "box", "width_ft": 1, "depth_ft": 1, "height_ft": 1,
             "center": (float("nan"), 0)}])
    assert "center[0]" in str(e.value)


@pytest.mark.parametrize("bad", [float("nan"), float("inf")])
def test_base_z_ft_is_checked_like_every_other_field(bad):
    """Unchecked, `base_z_ft` died as the bare `ValueError: extrusions here
    are extrude-DOWN` -- no field name, not a FactoryError -- i.e. precisely
    the symptom the NaN guard was added to remove, one field over."""
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="T", parts=[
            {"shape": "box", "width_ft": 1, "depth_ft": 1, "height_ft": 1,
             "base_z_ft": bad}])
    assert "base_z_ft" in str(e.value)


def test_an_OFFSET_RING_is_caught_only_by_the_assembly_origin_check():
    """The case that pins the assembly-level distance guard specifically.

    A 2 ft polygon ring whose vertices sit 1,000,000 ft from the origin
    passes every PER-PART check -- profile width is 2 ft, `center` is absent
    so it defaults to (0, 0) -- and the bounding box measures only 2 ft
    across. Its absolute position is what is absurd, and nothing but the
    assembly's distance-from-origin check sees it.

    Without a case like this the guard is masked: deleting it left all 25
    tests green, because the per-part `center` check happened to catch every
    other probe (#808 round 2).

    (1e6 rather than 1e9 on purpose: at 1e9 the `+2` is lost to float
    precision and the ring degenerates into `ValueError: profile vertices
    are collinear or zero-area` before the guard is ever reached.)
    """
    off = 1e6
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="T", parts=[{
            "shape": "polygon", "height_ft": 1,
            "vertices": [[off, off], [off + 2, off],
                         [off + 2, off + 2], [off, off + 2]]}])
    assert "distance from the family origin" in str(e.value)


def test_DISTANCE_from_the_origin_is_bounded_not_only_extent():
    """A 1 ft box can measure 1 ft and sit 189,394 miles away.

    Before this, such a part built and wrote a VALID 225,280-byte file whose
    type row honestly read `Width = 1.000 ft` while the solid sat far past
    the same working extent `MAX_BODY_FT`'s docstring cites. Extent was
    bounded; placement was not.
    """
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="T", parts=[
            {"shape": "box", "width_ft": 1, "depth_ft": 1, "height_ft": 1,
             "center": (1e9, 0)}])
    assert "center[0]" in str(e.value)


def test_length_ft_is_bounded_the_axial_dimension_of_a_conduit():
    """`length_ft` was missing from the enumerated fields, and it is the
    DOMINANT dimension of the cylinder shapes `rvt.ifc.assembly_parts`
    emits for a conduit or pipe run -- i.e. exactly the lane #806 cited as
    motivation while leaving it unbounded."""
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="T", parts=[
            {"shape": "cylinder_x", "radius_ft": 0.5, "length_ft": 1e12}])
    assert "length_ft" in str(e.value)


def test_a_polygon_profile_is_bounded_by_its_RING():
    """A polygon's size lives in its vertices, not in a named scalar."""
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="T", parts=[
            {"shape": "polygon", "height_ft": 5,
             "vertices": [[0, 0], [1e12, 0], [1e12, 1e12], [0, 1e12]]}])
    assert "profile width" in str(e.value)


def test_a_MIS_SCALED_ifc_conduit_is_refused_end_to_end():
    """The motivating case, with the real measured fit.

    A 1 in conduit 40 m long, read with a metre/millimetre mix-up (x1000),
    fits `cylinder_x length_ft=131200 radius_ft=41.7` -- a 24.8-mile
    conduit. Before #808's review it built 93 elements with `width_in`
    1,574,400 stamped `given source='ifc body'`.
    """
    mis = {"shape": "cylinder_x", "length_ft": 131_200.0,
           "radius_ft": 41.7, "height_ft": 83.4}
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(name="Conduit", parts=[mis], source="ifc body")
    assert "24.8 miles" in str(e.value)

    # the control that keeps this from being a bound on real work: the SAME
    # conduit read correctly (40 m = 131.2 ft) still builds
    ok = {"shape": "cylinder_x", "length_ft": 131.2,
          "radius_ft": 0.0417, "height_ft": 0.0834}
    prod = F.make_generic_model(name="Conduit", parts=[ok], source="ifc body")
    assert len(prod.doc.elements) > 0


def test_NaN_is_refused_as_a_FactoryError_naming_the_field():
    """NaN passes `<= 0` AND `> MAX_BODY_FT` -- every comparison with it is
    False -- so it slipped both ends and died deeper as `ValueError:
    extrusions here are extrude-DOWN`, with no field name and not even a
    FactoryError."""
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(height_ft=float("nan"), width_ft=1, depth_ft=1,
                             name="T")
    # keyed on the CLAUSE, not on how Python spells the float: the message
    # prints the value, so asserting "NaN" broke when inf joined the guard
    assert "not a finite size" in str(e.value)
    assert "height_ft" in str(e.value)


def test_infinity_is_refused_too():
    with pytest.raises(F.FactoryError) as e:
        F.make_generic_model(height_ft=float("inf"), width_ft=1, depth_ft=1,
                             name="T")
    assert "not a finite size" in str(e.value)


def test_the_bound_is_INCLUSIVE_at_exactly_MAX_BODY_FT():
    """Pins the comparison itself. A `>` -> `>=` mutant survived all eleven
    of the first tests, because none of them sat on the boundary."""
    import math
    prod = F.make_generic_model(**_ok(height_ft=F.MAX_BODY_FT))
    assert len(prod.doc.elements) > 0                      # exactly at: allowed
    with pytest.raises(F.FactoryError):                     # one ULP over: not
        F.make_generic_model(**_ok(height_ft=math.nextafter(F.MAX_BODY_FT,
                                                            math.inf)))


def test_the_bounds_VALUE_is_pinned_to_its_order_of_magnitude():
    """Nothing stopped a later edit loosening the constant 1000x silently --
    mutating it to 105_600_000.0 left every test green.

    Asserted as a RANGE, not a literal, so re-tuning it stays possible while
    quietly turning it off does not. The reasoning lives in the constant's
    own docstring: it is a floor on absurdity, not a certified limit.
    """
    assert 1_000 < F.MAX_BODY_FT < 1_000_000


# ===========================================================================
# 2. the spec-sheet lane -- and hard rule 1
# ===========================================================================

FIXTURES = os.path.join(ROOT, "tests")


def _sheet(tmp_path, height_text):
    import sys
    if FIXTURES not in sys.path:
        sys.path.insert(0, FIXTURES)
    import fixtures_pdf as FP
    rows = [("Height", height_text), ("Width", "20 in"), ("Depth", "5 in")]
    draws = []
    for i, (k, v) in enumerate(rows):
        y = 700.0 - i * 18.0
        draws += [(72.0, y, k), (300.0, y, v)]
    return FP.build_pdf(str(tmp_path / "adv.pdf"), [draws])


def test_the_sheet_lane_refuses_the_ROW_and_cites_it(tmp_path, monkeypatch):
    """The caveat must name the row, not only the converted number.

    This lane exists to cite sources; "height_ft is 83,333,333,333.25 ft" is
    a number the user has to map back to their own document.
    """
    monkeypatch.setenv("RVT_PDF_STDLIB_FORCE", "1")
    from rvt.specsheet.sheet import read_sheet
    from rvt.specsheet.famspec_from_sheet import plan_from_sheet
    plan = plan_from_sheet(read_sheet(_sheet(tmp_path, "999999999999 in")))
    assert not plan.buildable
    hits = [r for r in plan.refused if "sanity bound" in r]
    assert hits, plan.refused
    assert "999999999999 in" in hits[0]      # the raw cell, as written
    assert " p1 r" in hits[0]                # page and row


def test_the_sheet_lane_STILL_DELIVERS_through_the_archetype(tmp_path, monkeypatch):
    """Hard rule 1: the refusal is a label on a delivered file."""
    monkeypatch.setenv("RVT_PDF_STDLIB_FORCE", "1")
    from rvt.frontdoor import router as R
    res = R.route({"pdf": _sheet(tmp_path, "999999999999 in"),
                   "prompt": "create a cable tray family"}, "rfa",
                  out=str(tmp_path / "out"), quiet=True)
    assert res.ok, res.status
    assert os.path.isfile(res.files["rfa"])
    assert any("sanity bound" in c for c in res.caveats)


def test_a_plausible_sheet_is_untouched_by_the_bound(tmp_path, monkeypatch):
    """The control for the lane: the bound must not refuse real sheets."""
    monkeypatch.setenv("RVT_PDF_STDLIB_FORCE", "1")
    from rvt.specsheet.sheet import read_sheet
    from rvt.specsheet.famspec_from_sheet import plan_from_sheet
    plan = plan_from_sheet(read_sheet(_sheet(tmp_path, "62 in")))
    assert plan.buildable
    assert not [r for r in plan.refused if "sanity bound" in r]


def test_the_lane_and_the_factory_share_ONE_bound():
    """Two copies of this number would drift silently -- the lane would
    refuse at one size and the constructor at another, with the caveat
    quoting whichever fired."""
    from rvt.specsheet import famspec_from_sheet as FFS
    assert FFS._max_body_ft() == F.MAX_BODY_FT

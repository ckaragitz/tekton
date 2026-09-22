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

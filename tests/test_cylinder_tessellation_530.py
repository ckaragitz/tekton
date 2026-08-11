"""test_cylinder_tessellation_530.py -- a cylinder MEASURES the fixed-chord
extrapolation it carries instead of applying it silently (#530).

`G.cylinder`'s curved rails are tessellated with hard constants:

    ARC_CHORDS_FIRST_HALF = 7
    ARC_CHORDS_SECOND_HALF = 6

mined from ONE specimen -- 614's legs, radius 0.125 ft -- and applied at every
radius with no radius term.  That matters because the stored edge nodes are not
cosmetic: `docs/writer/family-geometry.md` sec. 4.4 records that the solid's
`m_bBox`/`m_tightbBox` ARE the extents of those nodes ("614's ymin = -0.5 -
0.125*sin(3pi/7) = -0.62187, the 7-chord node -- NOT the analytic -0.625").
A 16 in shade is therefore drawn, and bounded, as a 13-gon whose nodes sit
0.273 in inside the true circle.

WHY Revit chose 7 and 6 for two equal spans is flagged `[H]` in tree -- if it
sized them from a chord tolerance they do not transfer to another radius.  No
second-radius specimen exists in this clone (`samples/` is absent on a fresh
clone), so this change does NOT invent a radius law.  It measures the
extrapolation and labels it, the way every unsourced figure in this engine is
labelled: `arc_tessellation_facts()` on the bundle, surfaced in the family
report, `verified` True only at the one radius on record.

Evidence tiers: (1) the measurement itself; (2) it is attached to every
cylinder bundle; (3) it reaches the written report; (4) it changes NO written
byte -- report metadata only; (5) the constants are untouched, so specimen
reproduction is unaffected.
"""
import json
import math

import pytest

from rvt.famgen import factory as F, geometry as G, skeleton as SK


def _doc():
    return SK.new_family_document("lighting_fixture", "Cyl Probe",
                                  part_type=SK.PART_TYPE["normal"],
                                  work_plane_based=True, start_id=1000,
                                  plane_length_ft=6.0)


# ---------------------------------------------------------------------------
# (1) the measurement
# ---------------------------------------------------------------------------

def test_facts_at_the_one_verified_radius():
    f = G.arc_tessellation_facts(G.ARC_CHORDS_VERIFIED_RADIUS_FT)
    assert f["verified"] is True
    assert f["chords"] == G.ARC_CHORDS_FIRST_HALF + G.ARC_CHORDS_SECOND_HALF == 13
    assert f["specimen_ratio"] == pytest.approx(1.0)


@pytest.mark.parametrize("radius_ft,ratio,sagitta_in", [
    (0.03125, 0.25, 0.013),     # a 0.75 in stem
    (0.208333, 1.67, 0.085),    # a 5 in canopy
    (0.666667, 5.33, 0.273),    # a 16 in shade
])
def test_facts_away_from_the_specimen_radius(radius_ft, ratio, sagitta_in):
    f = G.arc_tessellation_facts(radius_ft)
    assert f["verified"] is False, "only 0.125 ft is on record"
    assert f["chords"] == 13, "the count does NOT change with radius (that is the point)"
    assert f["specimen_ratio"] == pytest.approx(ratio, abs=0.01)
    assert f["sagitta_ft"] * 12 == pytest.approx(sagitta_in, abs=0.001)


def test_sagitta_is_the_chord_to_arc_deviation_of_the_widest_half():
    """Independent derivation: the coarser half spans pi/6 per chord."""
    r = 0.5
    expected = r * (1.0 - math.cos((math.pi / G.ARC_CHORDS_SECOND_HALF) / 2.0))
    assert G.arc_tessellation_facts(r)["sagitta_ft"] == pytest.approx(expected)


# ---------------------------------------------------------------------------
# (2) every cylinder bundle carries it, and says so when extrapolating
# ---------------------------------------------------------------------------

def test_bundle_carries_the_facts_and_notes_the_extrapolation():
    fb = F.add_cylinder_form(_doc(), 0.666667, 0.8333)
    assert fb.params["tessellation"]["verified"] is False
    assert any("#530" in n for n in fb.notes), "an extrapolation must say so"


def test_no_note_at_the_verified_radius():
    fb = F.add_cylinder_form(_doc(), G.ARC_CHORDS_VERIFIED_RADIUS_FT, 1.0)
    assert fb.params["tessellation"]["verified"] is True
    assert not any("#530" in n for n in fb.notes)


# ---------------------------------------------------------------------------
# (3) it reaches the written report
# ---------------------------------------------------------------------------

def test_report_surfaces_radius_and_tessellation(tmp_path):
    prod = F.make_generic_model(parts=[{"shape": "cylinder", "radius_ft": 0.666667,
                                        "height_ft": 1.0}], name="Cyl Report")
    rep = prod.write(str(tmp_path / "cyl.rfa"), validate=True)
    assert rep["validate"]["family_mode"]["n_errors"] == 0
    cyls = [f for f in rep["family"]["forms"] if f["kind"] == "cylinder"]
    assert cyls, "a cylinder part must appear in the report"
    assert "tessellation" in cyls[0] and "radius_ft" in cyls[0]


# ---------------------------------------------------------------------------
# (4) NO written byte changes -- this is report metadata only
# ---------------------------------------------------------------------------

def test_facts_are_never_written_into_an_element():
    fb = F.add_cylinder_form(_doc(), 0.666667, 0.8333)
    blob = json.dumps([e.obj for e in fb.elements], default=str)
    assert "tessellation" not in blob
    assert "specimen_ratio" not in blob
    assert len(fb.elements) == 5, "SketchPlane + VarSketch + 2 arcs + ExtrusionElem"


# ---------------------------------------------------------------------------
# (5) the constants themselves are untouched (specimen reproduction unaffected)
# ---------------------------------------------------------------------------

def test_constants_are_unchanged():
    assert G.ARC_CHORDS_FIRST_HALF == 7
    assert G.ARC_CHORDS_SECOND_HALF == 6
    assert G.ARC_CHORDS_VERIFIED_RADIUS_FT == 0.125

"""NEC 110.26 working space and dedicated equipment space as data (#819, steer #818).

The table is what a family generator sizes its clearance solid from, so these
tests pin two things: that the answers are the table's, and that the table
never claims more certainty than it has.  As written, NOTHING was checked
against the NFPA 70 text (egress blocked, #819); the second half makes sure
that stays visible in every answer until someone actually checks a rule.
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from rvt.famgen import clearance as C

IN = 1.0 / 12.0
ALL_RULES = [r.rule for r in C.DEPTH_TABLE] + [C.WIDTH_RULE, C.HEIGHT_RULE, C.DEDICATED_RULE]


# ---------------------------------------------------------------------------
# the numbers
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("volts,cond,depth", [
    (120, 1, 3.0), (120, 2, 3.0), (120, 3, 3.0),
    (277, 1, 3.0), (277, 2, 3.5), (277, 3, 4.0),
    (480, 2, 3.5),
    (600, 3, 4.0),
    (601, 1, 3.0), (601, 2, 4.0), (1000, 3, 5.0),     # every cell of the 601-1000 V row
    (0, 1, 3.0), (150, 3, 3.0), (151, 3, 4.0),
])
def test_depth_by_voltage_band_and_condition(volts, cond, depth):
    w = C.working_space(equipment_width_ft=1.0, equipment_height_ft=1.0,
                        voltage_to_ground=volts, condition=cond, edition=2023)
    assert w.depth_ft == depth


def test_width_is_the_greater_of_the_equipment_or_30_in():
    narrow = C.working_space(equipment_width_ft=20 * IN, equipment_height_ft=2.5)
    wide = C.working_space(equipment_width_ft=40 * IN, equipment_height_ft=2.5)
    assert narrow.width_ft == pytest.approx(30 * IN)
    assert wide.width_ft == pytest.approx(40 * IN)


def test_height_is_the_greater_of_the_equipment_or_6_and_a_half_ft():
    assert C.working_space(equipment_width_ft=1, equipment_height_ft=2.5).height_ft == 6.5
    assert C.working_space(equipment_width_ft=1, equipment_height_ft=7.5).height_ft == 7.5


def test_the_source_names_the_edition_and_every_article_used():
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1, edition=2020)
    assert w.source.startswith("NEC 2020 ")
    for art in ("Table 110.26(A)(1)", "110.26(A)(2)", "110.26(A)(3)"):
        assert art in w.source, (art, w.source)


# ---------------------------------------------------------------------------
# defaults are stated, and the Condition default is the conservative one
# ---------------------------------------------------------------------------

def test_every_default_is_stated_never_silent():
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1)
    assert set(w.assumed) == {"edition", "voltage_to_ground", "condition"}
    assert (w.edition, w.voltage_to_ground, w.condition) == (C.DEFAULT_EDITION, 277.0, 2)


def test_the_condition_text_does_not_claim_a_difference_where_there_is_none():
    """Below 151 V every Condition is 3 ft, so the text must not say Condition 3
    IS deeper -- only that it can be (#826 round 2)."""
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1, voltage_to_ground=120)
    assert w.depth_ft == 3.0
    assert "can be deeper" in w.assumed["condition"]
    assert "all three are the same" in w.assumed["condition"]


def test_the_default_condition_is_2_and_says_what_is_shallower_and_deeper():
    """A drawn clearance exists to CATCH obstructions: a false clash costs a
    click, a missed one a code violation.  Condition 2 (facing a concrete,
    block or tile wall) is the common case; the text names both neighbours."""
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1)
    assert w.condition == 2 and w.depth_ft == 3.5          # 277 V, Condition 2
    text = w.assumed["condition"]
    assert "Condition 1" in text and "shallower" in text
    assert "Condition 3" in text and "deeper" in text


def test_nothing_is_assumed_when_everything_is_stated():
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1,
                        voltage_to_ground=120, condition=1, edition=2020)
    assert w.assumed == {}


# ---------------------------------------------------------------------------
# the table never claims more than it has
# ---------------------------------------------------------------------------

def test_every_rule_has_an_article_editions_and_corroboration():
    for r in ALL_RULES:
        assert r.article and ("110.26" in r.article), r
        assert r.editions and set(r.editions) <= set(C.EDITIONS), r
        assert r.corroboration, r


def test_a_rule_is_only_as_confident_as_its_sources():
    """'corroborated' needs at least two named sources.  Bumping the label
    without adding a source fails here."""
    for r in ALL_RULES:
        assert r.confidence == ("corroborated" if len(r.corroboration) >= 2 else "single-source"), r


def test_every_answer_says_it_is_unchecked_while_any_rule_it_used_is():
    for row in C.DEPTH_TABLE:
        for cond in C.CONDITIONS:
            w = C.working_space(equipment_width_ft=1, equipment_height_ft=1,
                                voltage_to_ground=row.v_max, condition=cond, edition=2023)
            assert w.verified is False and C.UNCHECKED in w.status
            assert ("single source" in w.status) == (row.rule.confidence == "single-source")
    d = C.dedicated_space("panelboard", equipment_width_ft=1, equipment_depth_ft=1)
    assert d.verified is False and C.UNCHECKED in d.status


def test_checking_the_depth_row_alone_does_not_make_an_answer_verified(monkeypatch):
    """``verified`` is the AND of every rule an answer used.  Recording a check
    on the depth row alone must not drop the 'not checked' wording while the
    width and height minimums are still unchecked (#826 review)."""
    read = ((2026, "NEC 2026 text"),)
    row = C.DEPTH_TABLE[1]
    checked = dataclasses.replace(row, rule=dataclasses.replace(row.rule, checked=read))
    monkeypatch.setattr(C, "DEPTH_TABLE", (C.DEPTH_TABLE[0], checked, C.DEPTH_TABLE[2]))
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1, voltage_to_ground=277)
    assert w.verified is False and C.UNCHECKED in w.status
    # ... and with every rule it used checked, it IS verified -- the flag is live
    for name in ("WIDTH_RULE", "HEIGHT_RULE"):
        monkeypatch.setattr(C, name, dataclasses.replace(getattr(C, name), checked=read))
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1, voltage_to_ground=277)
    assert w.verified is True and C.UNCHECKED not in w.status
    # ... but only FOR THE EDITION that was read: the 2026 text says nothing about 2017
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1, voltage_to_ground=277,
                        edition=2017)
    assert w.verified is False and C.UNCHECKED in w.status


def test_every_answer_carries_the_nominal_tier():
    assert C.working_space(equipment_width_ft=1, equipment_height_ft=1).tier == "nominal"
    assert C.dedicated_space("panelboard", equipment_width_ft=1, equipment_depth_ft=1).tier == "nominal"


# ---------------------------------------------------------------------------
# dedicated equipment space: per kind, never applied to everything
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kind", ["panelboard", "switchboard", "switchgear", "motor_control_center"])
def test_dedicated_space_applies_to_the_kinds_the_rule_names(kind):
    d = C.dedicated_space(kind, equipment_width_ft=20 * IN, equipment_depth_ft=6 * IN)
    assert d.applies and d.width_ft == pytest.approx(20 * IN) and d.depth_ft == pytest.approx(6 * IN)
    assert d.height_above_ft == 6.0
    assert d.source.startswith("NEC 2026 ") and "110.26(E)(1)" in d.source


def test_the_ceiling_cap_is_always_carried_and_applied_when_known():
    """"6 ft above the equipment OR to the structural ceiling, whichever is
    lower" -- a caller drawing the zone must never overshoot silently."""
    unknown = C.dedicated_space("panelboard", equipment_width_ft=1, equipment_depth_ft=1)
    assert unknown.height_above_ft == 6.0
    assert "whichever is lower" in unknown.height_limit and "not known" in unknown.height_limit
    low = C.dedicated_space("panelboard", equipment_width_ft=1, equipment_depth_ft=1,
                            ceiling_above_ft=3.0)
    assert low.height_above_ft == 3.0 and "capped at the structural ceiling" in low.height_limit
    high = C.dedicated_space("panelboard", equipment_width_ft=1, equipment_depth_ft=1,
                             ceiling_above_ft=9.0)
    assert high.height_above_ft == 6.0 and "ceiling is not lower" in high.height_limit


@pytest.mark.parametrize("edition", [2014, True, "x"])
def test_dedicated_space_refuses_an_edition_it_does_not_hold(edition):
    """The same over-claim fixed in working_space: 'NEC 2014 110.26(E)(1)' is a
    citation of an edition this module does not hold (#826 round 2)."""
    with pytest.raises(C.ClearanceError, match="is not held"):
        C.dedicated_space("panelboard", equipment_width_ft=1, equipment_depth_ft=1,
                          edition=edition)


def test_a_lighting_control_panel_gets_no_dedicated_space_and_is_told_why():
    d = C.dedicated_space("lighting_control_panel", equipment_width_ft=1, equipment_depth_ft=1)
    assert d.applies is False and d.width_ft is None
    assert "not among" in d.why and "working space still applies" in d.why
    # ... and it says when that answer is wrong: a unit listed as a panelboard IS one
    assert "listed as a panelboard" in d.why and "'panelboard'" in d.why
    # the non-applying branch validates its inputs too
    with pytest.raises(C.ClearanceError, match="must be positive"):
        C.dedicated_space("lighting_control_panel", equipment_width_ft=-1, equipment_depth_ft=1)
    # ... names its edition (a correct but unpinned source survived #826 round 3)
    assert d.source.startswith("NEC 2026 ")
    # ... and validates a ceiling it will never use
    with pytest.raises(C.ClearanceError, match="0 or more"):
        C.dedicated_space("lighting_control_panel", equipment_width_ft=1, equipment_depth_ft=1,
                          ceiling_above_ft=-1)


@pytest.mark.parametrize("ceiling", [True, "5"])
def test_a_ceiling_that_is_not_a_number_is_refused(ceiling):
    with pytest.raises(C.ClearanceError, match="must be a number"):
        C.dedicated_space("panelboard", equipment_width_ft=1, equipment_depth_ft=1,
                          ceiling_above_ft=ceiling)


def test_an_equal_ceiling_is_described_as_not_lower():
    d = C.dedicated_space("panelboard", equipment_width_ft=1, equipment_depth_ft=1,
                          ceiling_above_ft=6.0)
    assert d.height_above_ft == 6.0 and "not lower" in d.height_limit


def test_a_kind_with_no_decision_is_refused_not_guessed():
    with pytest.raises(C.ClearanceError, match="no 110.26\\(E\\)\\(1\\) decision"):
        C.dedicated_space("transformer", equipment_width_ft=1, equipment_depth_ft=1)


# ---------------------------------------------------------------------------
# refusals are named, never guessed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs,match", [
    (dict(voltage_to_ground=1200), "outside the 0-1000 V"),
    (dict(voltage_to_ground=150.5), "between the table's bands"),
    (dict(voltage_to_ground=-1), "not a voltage"),
    (dict(voltage_to_ground=float("nan")), "not a voltage"),
    (dict(voltage_to_ground="lots"), "not a number"),
    (dict(condition=4), "does not exist"),
    (dict(condition=2.0), "does not exist"),
    (dict(condition=True), "does not exist"),
    (dict(edition=2014), "NEC 2014 is not held"),
])
def test_a_request_the_table_cannot_answer_is_refused_by_name(kwargs, match):
    with pytest.raises(C.ClearanceError, match=match):
        C.working_space(equipment_width_ft=1, equipment_height_ft=1, **kwargs)


def test_the_over_1000_v_pointer_is_hedged_by_edition():
    """110.34 is the over-1000 V article in 2017/2020; later editions are not
    verified, so the refusal must not assert it for them."""
    with pytest.raises(C.ClearanceError) as e:
        C.working_space(equipment_width_ft=1, equipment_height_ft=1, voltage_to_ground=4160)
    assert "not verified for later ones" in str(e.value) and "DC" in str(e.value)


def test_no_copyright_or_trademark_marker_from_the_code_is_carried():
    """Hard rule 6.  This is a TOKEN guard only -- it catches the obvious
    markers of pasted code text, not a paraphrase; the review is what judges
    whether a description reproduces the code."""
    import inspect
    src = inspect.getsource(C)
    assert "Copyright" not in src and "NFPA 70®" not in src and "All rights reserved" not in src

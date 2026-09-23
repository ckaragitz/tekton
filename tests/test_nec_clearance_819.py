"""NEC 110.26 working space as data (issue #819, steer #818).

The table is the source a family generator sizes its clearance solid from, so
these tests pin two things: that the answers are the table's, and that the
table never claims more certainty than it has.  As written, no row was checked
against the NFPA 70 text (egress blocked, #819) -- the second half makes sure
that stays visible in every answer until someone actually checks a row.
"""
from __future__ import annotations

import pytest

from rvt.famgen import clearance as C

IN = 1.0 / 12.0


@pytest.mark.parametrize("volts,cond,depth", [
    (120, 1, 3.0), (120, 2, 3.0), (120, 3, 3.0),
    (277, 1, 3.0), (277, 2, 3.5), (277, 3, 4.0),
    (480, 2, 3.5),
    (600, 3, 4.0), (601, 2, 4.0), (1000, 3, 5.0),
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


def test_every_default_is_stated_never_silent():
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1)
    assert set(w.assumed) == {"edition", "voltage_to_ground", "condition"}
    assert w.edition == C.DEFAULT_EDITION and w.voltage_to_ground == 277.0 and w.condition == 1
    assert "least demanding" in w.assumed["condition"]


def test_nothing_is_assumed_when_everything_is_stated():
    w = C.working_space(equipment_width_ft=1, equipment_height_ft=1,
                        voltage_to_ground=120, condition=2, edition=2020)
    assert w.assumed == {}


# ---------------------------------------------------------------------------
# the table never claims more than it has
# ---------------------------------------------------------------------------

def test_every_row_names_its_corroboration_and_editions():
    for row in C.DEPTH_TABLE:
        assert row.corroboration, row
        assert row.editions and set(row.editions) <= set(C.EDITIONS), row
        assert row.confidence in ("corroborated", "single-source"), row


def test_a_row_is_only_as_confident_as_its_sources():
    """'corroborated' needs at least two named sources; one source is
    'single-source'.  A future edit that bumps the label without adding a
    source fails here."""
    for row in C.DEPTH_TABLE:
        if row.confidence == "corroborated":
            assert len(row.corroboration) >= 2, row
        else:
            assert len(row.corroboration) == 1, row


def test_an_unchecked_row_says_so_in_every_answer():
    for row in C.DEPTH_TABLE:
        w = C.working_space(equipment_width_ft=1, equipment_height_ft=1,
                            voltage_to_ground=row.v_max, condition=1, edition=2023)
        if row.checked_against is None:
            assert w.verified is False
            assert C.UNCHECKED in w.status
            if row.confidence == "single-source":
                assert "single source" in w.status
        else:
            assert w.verified is True and C.UNCHECKED not in w.status


def test_verified_follows_checked_against_not_a_separate_flag():
    """There is no way to mark a row verified except by recording what it was
    checked against -- the status is derived, so it cannot drift from the
    evidence."""
    assert not hasattr(C.DepthRow, "verified")


# ---------------------------------------------------------------------------
# refusals are named, never guessed
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kwargs,match", [
    (dict(voltage_to_ground=1200), "110.34"),
    (dict(voltage_to_ground=150.5), "between the table's bands"),
    (dict(condition=4), "Condition 4 does not exist"),
    (dict(edition=2014), "NEC 2014 is not held"),
])
def test_a_request_the_table_cannot_answer_is_refused_by_name(kwargs, match):
    with pytest.raises(C.ClearanceError, match=match):
        C.working_space(equipment_width_ft=1, equipment_height_ft=1, **kwargs)


def test_no_nfpa_text_is_carried():
    """Hard rule 6: numbers and article references only.  A crude guard -- no
    long runs of prose from the code -- but it catches a pasted paragraph."""
    import inspect
    src = inspect.getsource(C)
    assert "Copyright" not in src and "NFPA 70®" not in src

"""test_prompt_intent.py -- prompt-grammar contract (issue #1).

Pins the two behaviours the owner's demo prompt regressed on:

* WALL DERIVATION: a NAMED room always yields a 4-wall shell -- explicit
  dimensions when given, the stated 30 x 20 ft DEFAULT shell when not.
  'equipment only' / 'no walls' still suppresses the shell, and a prompt
  with no room noun still builds equipment-only.
* RATING-CLASS VOLTAGE: 'rated for 250V' is understood as the 240 V-class
  system (UL rating class -> system mapping), the mapping is STATED in
  coverage.defaults_applied, and '250V' never lands in ignored_words.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.frontdoor import prompt_intent as PP  # noqa: E402


def _catalog_ok() -> bool:
    try:
        from rvt.famgen import factory as F
        F.resolve_panelboard_facts("eaton", "pow-r-line", mains_a=400, spaces=42,
                                    voltage="480Y/277", mcb=True, mounting="surface",
                                    panel_name="X")
        return True
    except Exception:
        return False


needs_catalog = pytest.mark.skipif(not _catalog_ok(), reason="famgen catalog absent")

DEMO = "an electrical room rated for 250V with 6 panels"


# ===========================================================================
# rating-class voltage vocabulary
# ===========================================================================

def test_rating_class_voltage_mapped_and_stated():
    parsed = PP.parse_prompt("a 30 by 20 ft electrical room rated for 250V with 6 panels")
    assert parsed.room is not None
    assert parsed.room.service_voltage == "240"
    assert "250V" not in parsed.coverage.ignored_words
    assert any("rating class" in d for d in parsed.coverage.defaults_applied), \
        "the 250 V -> 240 V-class mapping must be STATED, never silent"
    assert any(u.get("as") == "service voltage" and u.get("voltage") == "240"
               for u in parsed.coverage.understood)


def test_rated_600v_reads_as_the_600y347_system():
    # 600 V is a real system (600Y/347): the existing vocabulary wins and
    # the rating-class mapping stays out of its way
    parsed = PP.parse_prompt("an electrical room rated for 600V with 2 panels")
    assert parsed.room.service_voltage == "600Y/347"
    assert not any("rating class" in d for d in parsed.coverage.defaults_applied)
    assert "600V" not in parsed.coverage.ignored_words


def test_rated_system_voltage_passes_through_unmapped():
    # 480 is a SYSTEM (-> 480Y/277 canonical), not a rating class: no
    # rating-class note, and nothing about it in ignored_words
    parsed = PP.parse_prompt("an electrical room rated for 480V with 2 panels")
    assert parsed.room.service_voltage == "480Y/277"
    assert not any("rating class" in d for d in parsed.coverage.defaults_applied)
    assert "480V" not in parsed.coverage.ignored_words


def test_amp_service_clause_still_wins():
    # the existing amp-service grammar is untouched by the voltage-rating one
    parsed = PP.parse_prompt("an electrical room rated for 2500 A service with 2 panels")
    assert parsed.room.service_rating_a == 2500.0
    assert parsed.room.service_voltage == PP.DEFAULT_SERVICE_VOLTAGE


# ===========================================================================
# wall derivation
# ===========================================================================

def test_named_room_without_dims_gets_default_shell():
    parsed = PP.parse_prompt("an electrical room with 6 panels")
    r = parsed.room
    assert r is not None and r.walls
    assert abs(r.width_m - PP.DEFAULT_ROOM_W_M) < 1e-9
    assert abs(r.depth_m - PP.DEFAULT_ROOM_D_M) < 1e-9
    assert any("DEFAULT room shell" in d for d in parsed.coverage.defaults_applied), \
        "the default shell must be STATED in coverage"


def test_explicit_dims_still_win_over_default():
    parsed = PP.parse_prompt("a 30 by 20 ft electrical room rated for 250V with 6 panels")
    assert abs(parsed.room.width_m - 9.144) < 1e-6
    assert abs(parsed.room.depth_m - 6.096) < 1e-6
    assert not any("DEFAULT room shell" in d for d in parsed.coverage.defaults_applied)


def test_equipment_only_still_suppresses_shell():
    parsed = PP.parse_prompt("an electrical room with 6 panels, equipment only")
    assert parsed.room is not None and parsed.room.walls is False


def test_no_room_noun_still_builds_equipment_only():
    parsed = PP.parse_prompt("a 150 kVA transformer and two 225 A panels")
    assert parsed.room is None


@needs_catalog
def test_demo_prompt_end_to_end():
    # the owner's demo prompt: 4 walls + the mapped voltage + zero ignored
    model, parsed = PP.prompt_to_intent(DEMO)
    assert model.room is not None and len(model.room.walls) == 4
    assert parsed.room.service_voltage == "240"
    assert parsed.coverage.ignored_words == []
    tags = [e.tag for e in model.equipment]
    assert tags == [f"PP-{i}" for i in range(1, 7)]
    # every panel inside the default ring
    assert model.audit["equipment_inside_room_ring"] == "6/6"


@needs_catalog
def test_dimensioned_demo_prompt_end_to_end():
    model, parsed = PP.prompt_to_intent(
        "a 30 by 20 ft electrical room rated for 250V with 6 panels")
    assert model.room is not None and len(model.room.walls) == 4
    assert parsed.room.service_voltage == "240"
    assert parsed.coverage.ignored_words == []

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


# ===========================================================================
# levels (issue #147): storey counts, per-item level references, the
# floor-to-floor height, and the honest 'storeys beyond 2' record
# ===========================================================================

TWO_STOREY = ("a two storey electrical building 40 by 30 ft, floor to floor 14 ft, with a "
              "main switchboard and four lighting panels on level 2")


def _levels(parsed):
    return [(lv["id"], lv["name"], lv["elevation"]) for lv in parsed.levels]


def test_two_storey_prompt_levels_and_per_item_levels():
    parsed = PP.parse_prompt(TWO_STOREY)
    # 'two storey' AND 'on level 2' are both consumed (every level clause, not the first)
    kinds = [(u["as"], u["clause"]) for u in parsed.coverage.understood]
    assert ("storeys", "two storey") in kinds and ("equipment level", "on level 2") in kinds
    assert ("floor-to-floor height", "floor to floor 14 ft") in kinds
    # datums a floor-to-floor height apart: 14 ft = 4.2672 m
    assert _levels(parsed) == [("L1", "Level 1", 0.0), ("L2", "Level 2", 4.2672)]
    assert parsed.room is not None and parsed.room.level == 1
    assert parsed.room.floor_to_floor_m == 4.2672
    assert [(it.tag, it.level) for it in parsed.items] == [
        ("MSB", 1), ("LP-1", 2), ("LP-2", 2), ("LP-3", 2), ("LP-4", 2)]
    # the old blanket warning is gone; the room-level default for the MSB is STATED
    assert not any("all equipment is placed on Level 1" in w for w in parsed.coverage.warnings)
    assert any(d.startswith("MSB: placed on Level 1") for d in parsed.coverage.defaults_applied)
    assert parsed.coverage.not_built == [] and parsed.coverage.ignored_words == []


def test_three_storeys_are_recorded_not_built_never_collapsed():
    parsed = PP.parse_prompt("a three storey electrical building 40 by 30 ft with a main "
                             "switchboard, two distribution panels on level 2 and four "
                             "lighting panels on level 3")
    # the intent keeps all three storeys (default spacing = room height + 2 ft, stated) ...
    assert [lv["id"] for lv in parsed.levels] == ["L1", "L2", "L3"]
    assert parsed.levels[2]["elevation"] == round(2 * (PP.DEFAULT_ROOM_HEIGHT_M
                                                       + PP.DEFAULT_FLOOR_ALLOWANCE_M), 4)
    assert any(d.startswith("floor-to-floor height:") for d in parsed.coverage.defaults_applied)
    assert [(it.tag, it.level) for it in parsed.items] == [
        ("MSB", 1), ("DP-1", 2), ("DP-2", 2), ("LP-1", 3), ("LP-2", 3), ("LP-3", 3), ("LP-4", 3)]
    # ... and the storey the base cannot carry is recorded, with the reason
    nb = [n for n in parsed.coverage.not_built if n["kind"] == "storey"]
    assert len(nb) == 1 and PP.BUILT_STOREYS == 2
    assert "storeys beyond 2 (base carries two story levels)" in nb[0]["reason"]
    assert "Level 3" in nb[0]["reason"]


def test_room_level_reference_scopes_the_room_and_its_gear():
    parsed = PP.parse_prompt("an electrical room on level 2 with 4 panels")
    assert parsed.room.level == 2
    assert [lv["id"] for lv in parsed.levels] == ["L1", "L2"]
    assert {it.level for it in parsed.items} == {2}
    assert any(u["as"] == "room level" and u["level"] == "L2" for u in parsed.coverage.understood)


@pytest.mark.parametrize("prompt,scope", [
    ("6 panels in an electrical room on the second floor", "room level"),      # ref right after the room
    ("a second floor electrical room with 6 panels", "room level"),            # ref right before it
    ("four lighting panels on level 2 in a 30 by 20 ft electrical room", "equipment level"),
])
def test_level_reference_adjacent_to_the_room_scopes_the_room(prompt, scope):
    """A reference glued to the room phrase moves the ROOM (walls + gear),
    even when no ',' / 'and' / 'with' separates it from the equipment
    clause; one inside the equipment clause alone stays item-scope."""
    parsed = PP.parse_prompt(prompt)
    assert any(u["as"] == scope and u["level"] == "L2" for u in parsed.coverage.understood)
    assert {it.level for it in parsed.items} == {2}
    assert parsed.room.level == (2 if scope == "room level" else 1)


def test_ordinal_floors_and_tag_lists_across_and():
    parsed = PP.parse_prompt("a 2-story equipment room 20 by 20 ft, 4.2 m floor to floor, two "
                             "lighting panels LP-1 and LP-2 on the second floor and a "
                             "transformer on the ground floor")
    assert _levels(parsed) == [("L1", "Level 1", 0.0), ("L2", "Level 2", 4.2)]
    # the level reference after a tag list that ran across 'and' still binds to the panels
    assert [(it.tag, it.level) for it in parsed.items] == [("LP-1", 2), ("LP-2", 2), ("T1", 1)]
    # 'floor 4' inside '4.2 m floor to floor' is NOT a level reference; '2' is not a count
    assert len(parsed.levels) == 2 and len(parsed.items) == 3
    # a stated floor-to-floor height sizes the unstated clear height (stated default)
    assert parsed.room.height_m == round(4.2 - PP.DEFAULT_FLOOR_ALLOWANCE_M, 4)
    assert parsed.coverage.ignored_words == []


def test_single_storey_prompts_are_unchanged():
    parsed = PP.parse_prompt("an electrical room with 6 panels")
    # nothing said about levels: ONE defaulted storey that asserts nothing about the datum
    assert parsed.levels == [{"id": "L1", "name": "Level 1", "elevation": 0.0, "default": True}]
    assert parsed.room.level == 1 and {it.level for it in parsed.items} == {1}
    assert not any("floor-to-floor" in d or "placed on Level" in d
                   for d in parsed.coverage.defaults_applied)
    # a level digit is never an equipment count: 'level 2 lighting panels' != 2 panels by count
    p2 = PP.parse_prompt("an electrical room with level 2 lighting panels LP-7")
    assert [(it.tag, it.level) for it in p2.items] == [("LP-7", 2)]


@needs_catalog
def test_two_storey_intent_model_carries_levels():
    model, parsed = PP.prompt_to_intent(TWO_STOREY)
    assert [(lv["id"], lv["elevation"]) for lv in model.levels] == [("L1", 0.0), ("L2", 4.2672)]
    assert model.room is not None and model.room.level == "L1" and len(model.room.walls) == 4
    assert {e.tag: e.level for e in model.equipment} == {
        "MSB": "L1", "LP-1": "L2", "LP-2": "L2", "LP-3": "L2", "LP-4": "L2"}
    # z stays level-relative (the panel mount centre AFF), each storey laid out afresh
    lp = model.by_tag("LP-1")
    assert abs(lp.insertion_m[2] - PP.DEFAULT_PANEL_MOUNT_CENTER_M) < 1e-9
    assert lp.as_json()["level"] == "L2"

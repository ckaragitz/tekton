"""test_prompt_intent_775.py -- a room NOUN inside a product NAME is
not a room.

Found by `tools/prompt_battery.py --rows` (1 of 100 rows failed):

    create a Water closet family
      -> room {'name': 'Electrical Room', 'width_m': 9.144, 'depth_m': 6.096,
               'source_text': 'closet'}, items []
      -> router: "FAILED (no family plan in this prompt could be built)"

`_ROOM_NOUNS` (prompt_intent.py) holds `closet` because "electrical closet"
is a room this route builds -- but `_RE_ROOM.search` ran before the taxonomy
scan and ate the `closet` of `water closet`, a `water_closet` taxonomy row
(Plumbing Fixtures).  The prompt for a fixture became a DEFAULT 30 x 20 ft
electrical room with no equipment, and the honest taxonomy refusal every
other plumbing row gives ("recognised, NOT built by this route ... NOT
buildable here") was replaced by a generic failure.

The fix tests the room NOUN's span against the taxonomy mentions, never the
whole match -- so `a transformer vault` (a room whose PREFIX is a taxonomy
mention) is still a room.
"""
import pytest

from rvt.frontdoor import prompt_intent as PI


@pytest.mark.parametrize("prompt", ["create a Water closet family",
                                    "a water closet"])
def test_water_closet_is_a_fixture_not_a_room(prompt):
    """Both of these DO fail against pre-change code -- this test earns its name."""
    with pytest.raises(PI.PromptError) as e:
        PI.parse_prompt(prompt)
    msg = str(e.value)
    assert "NOT built by this route" in msg
    assert "Plumbing Fixtures" in msg
    assert "Electrical Room" not in msg


def test_wc_alias_is_a_fixture():
    """A guard on the alias, NOT evidence for #775.

    'wc' refused correctly before this change too -- its alias carries no
    room noun for ``_RE_ROOM`` to eat, so it never took the room path. Split
    out of the parametrisation above so that test's name keeps meaning "this
    fix", rather than averaging a real pin with a vacuous one (#674 round 5).
    """
    with pytest.raises(PI.PromptError) as e:
        PI.parse_prompt("a wc")
    assert "Plumbing Fixtures" in str(e.value)


@pytest.mark.parametrize("prompt,room_name", [
    ("an electrical closet with 2 panels", "Electrical Closet"),
    ("a transformer vault", "Transformer Vault"),
    ("an electrical room with 6 panels", "Electrical Room"),
    ("a mechanical space", "Mechanical Space"),
])
def test_real_rooms_still_parse(prompt, room_name):
    parsed = PI.parse_prompt(prompt)
    assert parsed.room is not None, f"{prompt!r} lost its room"
    assert parsed.room.name == room_name


def test_the_room_prefix_may_itself_be_a_taxonomy_mention():
    """'transformer vault': the TX mention covers the PREFIX, not the noun."""
    parsed = PI.parse_prompt("a transformer vault")
    assert parsed.room is not None
    assert parsed.room.source_text.strip() == "transformer vault"


def test_a_room_prompt_with_equipment_is_unchanged():
    parsed = PI.parse_prompt("an electrical room with 6 panels")
    assert [i.kind for i in parsed.items] == ["panelboard"] * 6
    assert parsed.room.width_m == pytest.approx(9.144)

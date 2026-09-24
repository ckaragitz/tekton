"""test_prompt_phase_count_845.py -- a phase / wire / pole designator is a
system description, never an equipment count.

Found producing the owner's test panelboard (#845):

    a 208/120V 3-phase 4-wire panelboard  -> 4 panelboards (PP-1..PP-4)
    a 208/120V 3-phase panelboard         -> 3
    a 75 kVA 3-phase transformer          -> 3 transformers

The equipment clause scrubs ratings from the words before the noun before it
looks for a count, but phase / wire / pole designators were not scrubbed, so
the '3' of '3-phase' and the '4' of '4-wire' won as the count.
"""
import pytest

from rvt.frontdoor import prompt_intent as PI


def _kinds(prompt):
    return [it.kind for it in PI.parse_prompt(prompt).items]


@pytest.mark.parametrize("prompt", [
    "a 208/120V 3-phase panelboard",
    "a 208/120V 4-wire panelboard",
    "a 208/120V 3-phase 4-wire panelboard",
    "a three phase four wire 480Y/277V panelboard",
    "a 3 phase panel",
])
def test_designator_is_not_a_count(prompt):
    """Each of these built 3 or 4 panelboards before the fix."""
    assert _kinds(prompt) == ["panelboard"]


def test_transformer_designator_is_not_a_count():
    assert _kinds("a 75 kVA 3-phase transformer") == ["transformer"]


@pytest.mark.parametrize("prompt", [
    "a 208/120V panelboard",
    "a single-phase 120/240V panelboard",
    "a 3PH 4W 208Y/120 panel",
    "a 3Ø panelboard",
    "a 3P panelboard",
    "a 3-pole 225A panelboard",
])
def test_other_forms_stay_one(prompt):
    """Guards on the wider forms the scrub now covers (these already read as one)."""
    assert _kinds(prompt) == ["panelboard"]


@pytest.mark.parametrize("prompt,n", [
    ("two 3-phase panels", 2),                      # was 3 before the fix
    ("2 208Y/120V 3-phase 4-wire panels", 2),       # was 4 before the fix
    ("three three-phase panelboards", 3),
    ("4 panels", 4),
    ("an electrical room with 6 panels", 6),
])
def test_explicit_count_still_wins(prompt, n):
    kinds = _kinds(prompt)
    assert len(kinds) == n and set(kinds) == {"panelboard"}

"""test_prompt_rating_commas_855.py -- a comma between ONE item's ratings does not
cut the item's count off.

Spec-sheet phrasing puts commas between ratings ("four 225A, 3-phase, 4-wire
panels"). The equipment clause closed its window at every comma, so the count
before the first comma was never seen and the plural took its default of 2 (#855).
A comma is now crossed only when no count follows it and the text before it, back
to the previous boundary, is a count and ratings alone.
"""
import pytest

from rvt.frontdoor import prompt_intent as PI


def _items(prompt):
    return PI.parse_prompt(prompt).items


@pytest.mark.parametrize("prompt,n", [
    ("four 225A, MCB panels", 4),                          # main: 2
    ("three 75 kVA, dry-type transformers", 3),            # main: 2
    ("six 225A, 3-phase, 4-wire panels", 6),               # main: 4
    ("four 3-phase, 4-wire panels", 4),                    # main after #848: 2
    ("three 480V, 3-phase transformers", 3),
    ("four 75 kVA, 3-phase, 4-wire transformers", 4),
    ("three 4-wire, 3-phase panels", 3),
])
def test_count_before_a_rating_list_is_read(prompt, n):
    assert len(_items(prompt)) == n


def test_ratings_before_the_comma_reach_the_items():
    its = _items("four 225A, MCB panels")
    assert all(it.rating_a == 225.0 and it.mains == "MCB" for it in its)


@pytest.mark.parametrize("prompt,n", [
    ("a 225A panel, two transformers", 3),
    ("two transformers, three panels", 5),
    ("an electrical room with 6 panels, 2 transformers", 8),
    ("two 225A panels, a 75 kVA transformer", 3),
    ("panels LP-1, LP-2 and LP-3", 3),
    ("an electrical room, 30 x 20 ft, with 4 panels", 4),
    ("four panels, 225A", 4),
    ("a 3-phase, 4-wire panelboard", 1),
])
def test_a_comma_that_starts_a_new_item_still_splits(prompt, n):
    assert len(_items(prompt)) == n


def test_two_items_keep_their_own_ratings():
    its = _items("two 225A panels, a 75 kVA transformer")
    panels = [i for i in its if i.kind == "panelboard"]
    xfmrs = [i for i in its if i.kind == "transformer"]
    assert len(panels) == 2 and all(p.rating_a == 225.0 and p.kva is None for p in panels)
    assert len(xfmrs) == 1 and xfmrs[0].kva == 75.0 and xfmrs[0].rating_a is None


def _by_tag(prompt):
    return {it.tag: it for it in _items(prompt)}


@pytest.mark.parametrize("prompt", [
    "panel LP-1, 225A, MCB, panel LP-2, 100A, MLO",       # review of #856: LP-2 got 225 A MCB
    "LP-1, 225A, MCB, LP-2, 100A, MLO",
])
def test_trailing_ratings_never_reach_the_next_tagged_item(prompt):
    lp2 = _by_tag(prompt)["LP-2"]
    assert lp2.rating_a != 225.0 and lp2.mains != "MCB"


def test_semicolon_does_not_carry_ratings_forward():
    assert _by_tag("panel LP-1, 225A; panel LP-2")["LP-2"].rating_a != 225.0


def test_spaces_and_mounting_do_not_carry_forward():
    lp2 = _by_tag("LP-1 225A, 42-space, flush, LP-2")["LP-2"]
    assert lp2.spaces != 42 and lp2.mounting != "flush"


@pytest.mark.parametrize("prompt,kind,attr,leaked", [
    ("a transformer, 75 kVA, panels", "panelboard", "kva", 75.0),
    ("a transformer, 75 kVA, 480V, 3-phase, 4-wire panels", "panelboard", "kva", 75.0),
    ("a panelboard, 225A, 42-space, transformers", "transformer", "rating_a", 225.0),
    ("four panels, 225A, 3-phase transformers", "transformer", "rating_a", 225.0),
    ("four receptacles at 18 in AFF, 20A, panels", "panelboard", "rating_a", 20.0),
    ("two panels 225A, 42-space, flush, transformers", "transformer", "spaces", 42),
])
def test_ratings_never_cross_between_kinds(prompt, kind, attr, leaked):
    its = [i for i in _items(prompt) if i.kind == kind]
    assert its and all(getattr(i, attr) != leaked for i in its)


def test_voltage_does_not_cross_between_kinds():
    its = [i for i in _items("a transformer, 480V, 3-phase, panels") if i.kind == "panelboard"]
    assert its and all(i.voltage != "480Y/277" for i in its)

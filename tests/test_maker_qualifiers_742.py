"""#742 -- the residual maker nits of #741's final review: model / configuration tokens in a
place-word qualifier gap, 'replace | remove | demo | salvage ... the X equipment' as context,
'all equipment: X <noun>' lists, 'both by X' after two nouns, and brand-vs-parent cells.

Fresh-clone safe: pure prompt parsing, no samples, no built files."""
import time

import pytest

from rvt.famgen import vendors as V
from rvt.frontdoor import prompt_intent as PP

HPS = "Hammond Power Solutions"


def _makers(prompt):
    p = PP.parse_prompt(prompt)
    return p, {it.tag: it.manufacturer for it in p.items}


# --------------------------------------------------------------------------- (1) model tokens

@pytest.mark.parametrize("prompt,prefix,maker", [
    ("an Eaton house PRL1a panel and six tenant panels", "PP-1", "Eaton"),
    ("two Eaton lab 3P4W 225A panels", "PP", "Eaton"),
    ("an Eaton house 1P3W 200A panel", "PP", "Eaton"),
    ("two Eaton lab 3Ø 4W panels", "PP", "Eaton"),
    ("two Eaton site 3R lighting panels", "LP", "Eaton"),
    ("two Eaton site N3R lighting panels", "LP", "Eaton"),
    ("two Eaton site 4X lighting panels", "LP", "Eaton"),
    ("two Eaton site NEMA-3R lighting panels", "LP", "Eaton"),
    ("an Eaton house Cat# PRL1A panel", "PP", "Eaton"),
    ("The Eaton House PRL1a Panel", "PP", "Eaton"),
    ("two Siemens data center P1 panels 400 A", "PP", "Siemens"),
    ("an Eaton station K-13 45 kVA transformer", "T", "Eaton"),      # (the item COUNT is #740's)
    ("two Eaton lab 200% neutral panels", "PP", "Eaton"),
])
def test_a_model_token_between_a_place_qualifier_and_its_noun_keeps_the_maker(prompt, prefix, maker):
    p, mk = _makers(prompt)
    got = {m for t, m in mk.items() if t.startswith(prefix)}
    assert got == {maker}, (prompt, mk)
    assert p.coverage.warnings == [] or all("known by name" in w or "makes nothing" in w
                                            for w in p.coverage.warnings), p.coverage.warnings


@pytest.mark.parametrize("prompt", ["two Kohler 3P4W panels", "two Kohler N3R panels", "two Kohler K-13 panels"])
def test_the_same_tokens_count_as_adjacent_for_a_maker_of_other_kinds(prompt):
    p, mk = _makers(prompt)                          # one vocabulary for both tests: declared, said
    assert set(mk.values()) == {"Kohler"}, mk
    assert any(V.NOT_THAT_MAKER in w for w in p.coverage.warnings), p.coverage.warnings


def test_the_gap_helpers_agree_and_stay_linear():
    for gap in (" N3R ", " 3P4W 225A ", " K-13 45 kVA ", " PRL1a ", " 200% neutral ", ", 225 A"):
        assert PP._only_ratings(gap) and PP._qualifier_gap(gap), gap
    assert not PP._only_ratings(" 12 ") and not PP._qualifier_gap(" 12 ")       # a bare count
    assert not PP._only_ratings(" hospital grade ") and PP._qualifier_gap(" hospital grade ")
    assert not PP._qualifier_gap(" needs 4 ") and not PP._qualifier_gap(" for the ")
    for hostile in ("two Trane " + "1" * 40 + " custom panels", "two Trane " + "A1" * 30 + " custom panels",
                    "an Eaton house " + "A1-/" * 20 + "x panels"):
        t = time.perf_counter()
        PP.parse_prompt(hostile)
        assert time.perf_counter() - t < 0.5, hostile


# --------------------------------------------------------------------------- (2) context verbs

@pytest.mark.parametrize("prompt,name", [
    ("salvage the Square D equipment; provide 4 new panels", "Square D"),
    ("demo the Siemens gear; provide 4 panels and a transformer", "Siemens"),
    ("remove Siemens equipment. Provide 4 panels.", "Siemens"),
    ("coordinate with Siemens equipment supplier; 4 panels", "Siemens"),
    ("replace the Siemens equipment with 4 panels", "Siemens"),
    ("relocate the existing Eaton equipment and add two panels", "Eaton"),
])
def test_work_on_existing_gear_names_no_maker_for_the_new_work(prompt, name):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None}, (prompt, mk)
    assert any(w.startswith(f"maker {name} names existing or neighbouring equipment") for w in
               p.coverage.warnings), p.coverage.warnings


def test_the_replaced_noun_keeps_its_maker_and_the_new_ones_theirs():
    p, mk = _makers("replace the existing Eaton panel with two new Kohler panels")
    assert mk == {"PP-1": "Eaton", "PP-2": "Kohler", "PP-3": "Kohler"}, mk
    assert any(V.NOT_THAT_MAKER in w for w in p.coverage.warnings)      # Kohler makes no panelboard


# --------------------------------------------------------------------------- (3) 'all equipment: X <noun>'

@pytest.mark.parametrize("prompt,expect", [
    ("all equipment: Eaton panels and a 45 kVA transformer", {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("everything: Eaton panels and a Hammond 45 kVA transformer", {"T1": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("all equipment is Eaton panels and Hammond transformers",
     {"T1": HPS, "T2": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}),
    # not adjacent to a noun: still the whole job
    ("all equipment: Eaton. two panels and a transformer", {"T1": "Eaton", "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("all equipment by Eaton: two panels and a transformer", {"T1": "Eaton", "PP-1": "Eaton", "PP-2": "Eaton"}),
])
def test_all_equipment_colon_introducing_a_list_names_each_noun_its_maker(prompt, expect):
    _p, mk = _makers(prompt)
    assert mk == expect, (prompt, mk)


# --------------------------------------------------------------------------- (4) 'both by X'

@pytest.mark.parametrize("prompt,expect", [
    # two groups before it: both
    ("two panels and a transformer, both by Eaton, and 6 receptacles at 18 in AFF",
     {"T1": "Eaton", "PP-1": "Eaton", "PP-2": "Eaton"}),
    # the last group holds the two: that group
    ("a 2000 A switchboard feeding two panels, both by Eaton, and a 45 kVA transformer",
     {"MSB": None, "T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("panels LP-1 and LP-2, both by Eaton, and a transformer", {"T1": None, "LP-1": "Eaton", "LP-2": "Eaton"}),
    ("two panels, both by Eaton, and a 45 kVA transformer", {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
])
def test_both_by_x_binds_the_two_it_names(prompt, expect):
    p, mk = _makers(prompt)
    assert {t: m for t, m in mk.items() if not t.startswith("R-")} == expect, (prompt, mk)
    assert not p.coverage.warnings, p.coverage.warnings


def test_both_after_more_than_two_nouns_says_so_instead_of_guessing():
    p, mk = _makers("4 panels, a transformer and a switchboard, both by Eaton, plus 6 receptacles at 18 in AFF")
    assert set(mk.values()) == {None}
    assert any(w.startswith("maker Eaton: 'both' follows more than two pieces of equipment -- applied to nothing")
               for w in p.coverage.warnings), p.coverage.warnings


# --------------------------------------------------------------------------- (5) brand vs parent cells

@pytest.mark.parametrize("cell,kind", [("Eaton by Siemens", "transformer_dry"), ("Eaton by Siemens", "panelboard"),
                                       ("Siemens by Eaton", "switchboard")])
def test_two_makers_of_the_same_equipment_stay_two(cell, kind):
    d = V.declared(cell, kind)
    assert (d["known"], d["vendor"], d["record"]) == (False, None, None), (cell, kind, d)
    assert "names 2 makers" in d["line"]


@pytest.mark.parametrize("cell,kind,vendor", [
    ("Cooper Lighting Solutions by Eaton", "downlight", "cooper-lighting"),
    ("Cooper Lighting Solutions by Eaton", "panelboard", "cooper-lighting"),   # a brand on any kind
    ("Halo, an Eaton brand", "downlight", "cooper-lighting"),
    ("Metalux, a division of Cooper Lighting", "troffer", "cooper-lighting"),
    ("Square D by Schneider Electric", "panelboard", "square-d"),             # the recorded parent
])
def test_a_brand_and_its_parent_collapse_to_the_brand(cell, kind, vendor):
    d = V.declared(cell, kind)
    assert (d["known"], d["vendor"]) == (True, vendor), (cell, kind, d)


# --------------------------------------------------------------------------- nothing regressed nearby

@pytest.mark.parametrize("prompt,expect_none,ignored", [
    ("the Kohler campus needs 4 panels", True, "Kohler"),
    ("Sloan wing: 4 panels", True, "Sloan"),
    ("4 panels for the Edwards building", True, "Edwards"),
])
def test_places_are_still_places(prompt, expect_none, ignored):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and ignored in p.coverage.ignored_words and not p.coverage.warnings


def test_context_and_cues_from_741_hold():
    _p, mk = _makers("two panels next to an Eaton 75 kVA transformer")
    assert mk == {"T1": "Eaton", "PP-1": None, "PP-2": None}
    _p, mk = _makers("4 new panels to match the existing Eaton gear")
    assert set(mk.values()) == {"Eaton"}
    _p, mk = _makers("Eaton equipment: 4 panels and a transformer")
    assert set(mk.values()) == {"Eaton"}
    p, mk = _makers("two panels beside existing Siemens equipment and a new transformer")
    assert set(mk.values()) == {None} and any("names existing or neighbouring" in w for w in p.coverage.warnings)


# --------------------------------------------------------------------------- review of #743, round 1

@pytest.mark.parametrize("prompt", [
    "All equipment: Eaton -- panels LP-1 and LP-2, transformer T-1 45 kVA",
    "All equipment: Eaton - panels LP-1 and LP-2, transformer T-1 45 kVA",
    "All equipment: Eaton (panels LP-1 and LP-2, transformer T-1 45 kVA)",
    "All equipment: Eaton\npanels LP-1 and LP-2, transformer T-1 45 kVA",
    "All equipment: Eaton\n- panels LP-1 and LP-2\n- transformer T-1 45 kVA",
    "All equipment: Eaton / panels LP-1 and LP-2, transformer T-1 45 kVA",
    "All equipment is Eaton -- panels LP-1 and LP-2, one 45 kVA transformer",
])
def test_punctuation_or_a_line_break_after_all_equipment_x_keeps_the_whole_job(prompt):
    _p, mk = _makers(prompt)                          # only 'all equipment: X <noun>' with nothing
    assert set(mk.values()) == {"Eaton"}, (prompt, mk)   # but spaces / ratings between is a list


def test_the_list_reading_is_said_not_silent():
    p, mk = _makers("all equipment: Eaton panels and a 45 kVA transformer")
    assert mk["T1"] is None
    assert any(w.startswith("maker Eaton after 'all equipment:' stands against the next noun") for w in
               p.coverage.warnings), p.coverage.warnings


@pytest.mark.parametrize("prompt", [
    "4 panels\n225 A each\nand a transformer", "provide:\n2 panels\n225A\nEaton",
])
def test_a_line_break_is_still_only_layout_elsewhere(prompt):
    p, mk = _makers(prompt)                           # ratings / makers on their own line still
    pans = [it for it in p.items if it.tag.startswith("PP")]   # reach the noun, exactly as on main
    assert pans and all(it.rating_a == 225.0 for it in pans), [(it.tag, it.rating_a) for it in p.items]


@pytest.mark.parametrize("prompt,name", [
    ("the Eaton building 3rd floor panels", "Eaton"), ("the Eaton building #3 panels", "Eaton"),
    ("Eaton hall room 214B panels", "Eaton"), ("Eaton campus phase 2B panels", "Eaton"),
    ("the Westinghouse building 4th floor panels", "Westinghouse"), ("Siemens campus bldg 4B panels: 4 x 225A", "Siemens"),
    ("Leviton hall rm 12B receptacles (6)", "Leviton"),
])
def test_an_ordinal_or_room_designator_after_a_place_keeps_it_a_place(prompt, name):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and name in p.coverage.ignored_words, (prompt, mk, p.coverage.ignored_words)


def test_vendor_kinds_is_computed_once():
    assert V.get("eaton").kinds is V.get("eaton").kinds and "panelboard" in V.get("eaton").kinds

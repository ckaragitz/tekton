"""#739 -- follow-up of the third review of #736: a maker the vendor directory says does not
make the noun's kind rides that noun only when the two are ADJACENT; a maker's name used as a
place or a client ('for the Edwards building') names no maker; whole-job cues are wider
('manufacturer: Eaton', 'use Eaton', a leading 'Eaton:', 'Eaton only') and the after-cue needs
its quantifier ('existing Siemens equipment' is no cue); the two-word 'Square D' and acronyms
('GE') are real names, not plain words; Price / Titus grilles; a cell naming two makers.
Every prompt the reviewer listed is here in both word orders."""
from __future__ import annotations

import pytest

from rvt.famgen import taxonomy as TX
from rvt.famgen import vendors as V
from rvt.frontdoor import prompt_intent as PP

HPS = "Hammond Power Solutions"


def _makers(prompt):
    p = PP.parse_prompt(prompt)
    return p, {it.tag: it.manufacturer for it in p.items}


def _no_maker_anywhere(prompt, word):
    """Nothing declared: no item maker, the word left over as ignored, no warning, and no
    Manufacturer value or maker kwarg anywhere downstream (the delivered IFC carries none)."""
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None}, (prompt, mk)
    assert word in p.coverage.ignored_words, (prompt, p.coverage.ignored_words)
    assert p.coverage.warnings == [], (prompt, p.coverage.warnings)
    assert not [u for u in p.coverage.understood if u.get("as") == "manufacturer"], prompt
    model, _parsed = PP.prompt_to_intent(prompt if "room" in prompt else "an electrical room with " + prompt)
    assert not any(e.contract.get("Manufacturer") for e in model.equipment), prompt
    assert not any((e.psets.get("Pset_ManufacturerTypeInformation") or {}).get("Manufacturer")
                   for e in model.equipment), prompt
    assert not any(fp.kwargs.get("manufacturer") for fp in model.family_plans), prompt
    return p


# --------------------------------------------------------------------------- DONE 1: locatives

@pytest.mark.parametrize("prompt,word", [
    # the reviewer's eight, as written ...
    ("4 panels for the Edwards building", "Edwards"),
    ("two panels in Cooper Hall", "Cooper"),
    ("Sloan wing: 4 panels", "Sloan"),
    ("the Kohler campus needs 4 panels", "Kohler"),
    ("4 panels for Armstrong High School", "Armstrong"),
    ("two lighting panels 42 spaces 208Y/120 V for the Schneider residence", "Schneider"),
    ("a 75 kVA transformer for the Hammond plant", "Hammond"),
    ("a 75 kVA transformer in the Hammond Street vault", "Hammond"),
    # ... and the other way round
    ("for the Edwards building: 4 panels", "Edwards"),
    ("in Cooper Hall, two panels", "Cooper"),
    ("4 panels in the Sloan wing", "Sloan"),
    ("4 panels for the Kohler campus", "Kohler"),
    ("Armstrong High School: 4 panels", "Armstrong"),
    ("the Schneider residence gets two lighting panels 42 spaces 208Y/120 V", "Schneider"),
    ("the Hammond plant needs a 75 kVA transformer", "Hammond"),
    ("Hammond Street vault: a 75 kVA transformer", "Hammond"),
    # a longer proper-noun phrase before the place noun; a client with no place noun at all
    ("for the Edwards Lifesciences campus: 4 panels and a 45 kVA transformer", "Edwards"),
    ("4 panels for Edwards", "Edwards"),
    ("Kohler wants 4 panels", "Kohler"),
])
def test_a_makers_name_used_as_a_place_or_client_names_no_maker(prompt, word):
    _no_maker_anywhere(prompt, word)


@pytest.mark.parametrize("prompt,expect", [
    ("six Eaton panels in building B", {"Eaton"}),                       # the noun sits between
    ("an Eaton transformer in vault 2", {"Eaton"}),
    ("a transformer by Hammond for the plant", {HPS}),                   # 'for the plant' alone
    ("Eaton panels for the office and a Hammond transformer", {"Eaton", HPS}),
    ("two panels fed from the Eaton switchboard", {"Eaton", None}),      # the switchboard's maker
])
def test_a_place_after_the_equipment_does_not_swallow_a_real_declaration(prompt, expect):
    _p, mk = _makers(prompt)
    assert set(mk.values()) == expect, (prompt, mk)


def test_a_place_named_after_a_maker_of_the_kind_is_still_a_place():
    _no_maker_anywhere("two panels for the new Eaton building", "Eaton")


@pytest.mark.parametrize("prompt,name", [
    ("two panels beside existing Siemens equipment and a new transformer", "Siemens"),
    ("a new transformer and two panels beside the existing Siemens equipment", "Siemens"),
    ("two panels next to the Eaton gear and a transformer", "Eaton"),
    ("two panels; existing Siemens gear to remain", "Siemens"),
])
def test_existing_gear_nearby_is_context_not_a_declaration_and_says_so(prompt, name):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None}, (prompt, mk)
    (w,) = p.coverage.warnings
    assert w.startswith(f"maker {name} names existing or neighbouring equipment, not the new "
                        "work -- applied to nothing")


@pytest.mark.parametrize("prompt,expect", [
    # the noun the context phrase qualifies keeps its maker (the noun is built today: #740)
    ("two panels next to an Eaton 75 kVA transformer", {"T1": "Eaton", "PP-1": None, "PP-2": None}),
    ("replace the existing Eaton panel with two new Kohler panels",
     {"PP-1": "Eaton", "PP-2": "Kohler", "PP-3": "Kohler"}),
    # 'to match the existing X gear' is a (soft) whole-job cue, not context
    ("4 new panels to match the existing Eaton gear", {"PP-1": "Eaton", "PP-2": "Eaton", "PP-3": "Eaton", "PP-4": "Eaton"}),
])
def test_context_names_the_maker_of_the_noun_it_qualifies(prompt, expect):
    _p, mk = _makers(prompt)
    assert mk == expect, (prompt, mk)


# --------------------------------------------------------------------------- review of #741, round 1

@pytest.mark.parametrize("prompt,expect", [
    # a place noun that QUALIFIES the equipment noun is not a place ('house panel', 'site lighting')
    ("an Eaton house panel and six tenant panels", {"Eaton", None}),
    ("two Eaton site lighting panels 100 A", {"Eaton"}),
    ("two Eaton lab panels and a 75 kVA transformer", {"Eaton", None}),
    ("six Eaton suite panels 100 A MLO", {"Eaton"}),
    # '-wide' is a whole-job quantifier, 'factory-assembled' an adjective, 'base bid' no place
    ("use Eaton site-wide: 4 panels and a 45 kVA transformer", {"Eaton"}),
    ("standardize on Eaton plant-wide: 4 panels and a 45 kVA transformer", {"Eaton"}),
    ("a 2000 A Eaton factory-assembled switchboard", {"Eaton"}),
    ("Eaton base bid: 4 panels", {"Eaton"}),
])
def test_place_words_that_qualify_the_noun_do_not_swallow_the_maker(prompt, expect):
    _p, mk = _makers(prompt)
    assert set(mk.values()) == expect, (prompt, mk)


@pytest.mark.parametrize("prompt,expect", [
    ("two panels, both by Eaton, and a 45 kVA transformer", {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("a 45 kVA transformer and two panels, all by Eaton, plus 4 receptacles at 18 in AFF",
     {"T1": "Eaton", "PP-1": "Eaton", "PP-2": "Eaton", "R-1": None, "R-2": None, "R-3": None, "R-4": None}),
    ("4 panels and a 45 kVA transformer, all by Eaton",                       # trailing: the job
     {"T1": "Eaton", "PP-1": "Eaton", "PP-2": "Eaton", "PP-3": "Eaton", "PP-4": "Eaton"}),
    ("all by Eaton: 4 panels and a 45 kVA transformer",                       # leading: the job
     {"T1": "Eaton", "PP-1": "Eaton", "PP-2": "Eaton", "PP-3": "Eaton", "PP-4": "Eaton"}),
])
def test_all_by_x_inside_a_list_names_the_list_before_it_not_the_job(prompt, expect):
    p, mk = _makers(prompt)
    assert mk == expect, (prompt, mk)
    assert p.coverage.warnings == [], (prompt, p.coverage.warnings)


@pytest.mark.parametrize("prompt", [
    "Eaton or Siemens: 4 panels and a 75 kVA transformer", "Eaton / Siemens: 4 panels",
    "all gear by Eaton or Siemens: 4 panels", "4 panels; manufacturer: Eaton, Siemens",
])
def test_two_names_ahead_of_a_cue_are_one_cued_set_and_apply_to_nothing(prompt):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None}, (prompt, mk)
    assert any(w.startswith("makers Eaton, Siemens are all named for the whole job -- applied to nothing")
               for w in p.coverage.warnings), p.coverage.warnings


def test_a_cue_when_every_item_already_names_its_maker_says_that():
    p, mk = _makers("six Eaton panels; manufacturer: Siemens")
    assert set(mk.values()) == {"Eaton"}
    assert p.coverage.warnings[-1] == ("maker Siemens is named for the job but every item already "
                                       "names its own maker -- applied to nothing")


@pytest.mark.parametrize("prompt,word", [
    ("ROOM 20 FT SQUARED WITH 4 PANELS", "SQUARED"),
    ("PROVIDE 4 PANELS. PRICE SEPARATELY.", "PRICE"),
    ("4 PANELS AND A 75 KVA TRANSFORMER. YORK TO REVIEW.", "YORK"),
])
def test_an_all_caps_prompt_keeps_plain_words_plain(prompt, word):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and word in p.coverage.ignored_words and not p.coverage.warnings


@pytest.mark.parametrize("prompt,expect", [
    ("a GE 480-208Y/120V 75 kVA transformer", {"T1": "ABB"}),
    ("a GE step-down 75 kVA transformer", {"T1": "ABB"}),
    ("a Trane type NQ 225 A panel", {"PP-1": "Trane"}),
    ("two Kohler NEMA 3R panels", {"PP-1": "Kohler", "PP-2": "Kohler"}),
    ("two Kohler 400A 65kAIC MLO 480/277V panels", {"PP-1": "Kohler", "PP-2": "Kohler"}),
])
def test_more_rating_spellings_between_maker_and_noun_are_adjacent(prompt, expect):
    p, mk = _makers(prompt)
    assert mk == expect, (prompt, mk)
    assert [w for w in p.coverage.warnings if V.NOT_THAT_MAKER in w], p.coverage.warnings


def test_adjacency_stays_linear_on_hostile_gaps():
    import time
    for gap in ("1" * 40, "/" * 40, " " * 300 + "x", "480/277V " * 60):
        t = time.perf_counter()
        PP.parse_prompt(f"two Trane {gap} custom panels")
        assert time.perf_counter() - t < 0.5, gap[:12]


# --------------------------------------------------------------------------- DONE 1: adjacency

@pytest.mark.parametrize("prompt,tags", [
    ("a Trane panel", ["PP-1"]),                                  # <maker> <noun>
    ("two new Kohler 225 A panels", ["PP-1", "PP-2"]),            # <maker> [ratings] <noun>
    ("two Kohler main circuit breaker 225 amperes 480Y/277 V 42-circuit panels", ["PP-1", "PP-2"]),
    ("two panels (Kohler, 480 V 3 ph 4 wire) and a 75 kVA transformer", ["PP-1", "PP-2"]),
    ("panels LP-1 and LP-2 by Kohler", ["LP-1", "LP-2"]),         # <noun> [tags] by <maker>
    ("two panels (Kohler) and a 75 kVA transformer", ["PP-1", "PP-2"]),
    ("two panels, manufacturer: Kohler, and a 75 kVA transformer", ["PP-1", "PP-2"]),
])
def test_a_maker_of_other_kinds_rides_the_noun_only_when_adjacent_and_is_said(prompt, tags):
    p, mk = _makers(prompt)
    named = sorted(t for t, m in mk.items() if m)
    assert named == tags, (prompt, mk)
    said = [w for w in p.coverage.warnings if V.NOT_THAT_MAKER in w]
    assert len(said) == 1 and said[0].startswith(", ".join(tags) + ": "), p.coverage.warnings


@pytest.mark.parametrize("prompt,word", [
    ("provide 4 panels (Generac backup) and a 2000 A switchboard", "Generac"),   # not '(Generac)'
    ("Kohler wants 4 panels and a 30 kVA transformer", "Kohler"),
    ("4 panels feeding Kohler kitchen loads", "Kohler"),
])
def test_a_maker_of_other_kinds_that_is_not_adjacent_is_an_ignored_word(prompt, word):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and word in p.coverage.ignored_words, (prompt, mk)


def test_the_nearest_noun_still_wins_for_a_maker_of_the_kind():
    _p, mk = _makers("an electrical room 20 ft by 15 ft with two 225 A panels by Eaton and a 75 kVA "
                     "Hammond transformer")
    assert mk == {"T1": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}
    p, mk = _makers("a 500 kW Cummins generator and two panels")
    assert set(mk.values()) == {None}
    assert [(r["text"], r.get("manufacturer")) for r in p.coverage.not_built] == [
        ("generator", "Cummins Power Generation")]


# --------------------------------------------------------------------------- DONE 2: 'Square D'

@pytest.mark.parametrize("prompt", [
    "6 Square D receptacles at 18 in AFF and two panels",
    "two panels and 6 Square D receptacles at 18 in AFF",
])
def test_the_two_word_square_d_is_a_real_name_not_a_plain_word(prompt):
    p, mk = _makers(prompt)
    assert {t: m for t, m in mk.items() if t.startswith("R-")} == {f"R-{i}": "Square D" for i in range(1, 7)}
    assert mk["PP-1"] is None and mk["PP-2"] is None
    assert "Square" not in p.coverage.ignored_words and "D" not in p.coverage.ignored_words
    (said,) = [w for w in p.coverage.warnings if V.NOT_THAT_MAKER in w]
    assert said.startswith("R-1, R-2, R-3, R-4, R-5, R-6: Square D makes nothing the directory "
                           "lists for receptacle")


def test_a_repeated_by_square_d_keeps_both_mentions():
    for prompt in ("6 receptacles by Square D and two panels by Square D",
                   "two panels by Square D and 6 receptacles by Square D"):
        _p, mk = _makers(prompt)
        assert set(mk.values()) == {"Square D"}, (prompt, mk)


def _strength(m):
    return "weak" if m.weak else "acronym" if m.acronym else "real"


def test_the_scanner_grades_names_once_for_every_reader():
    got = {m.text: _strength(m) for m in V.scan("GE, Square-D, Square D, York, 1200 Watts, Eaton, Squared ft")}
    assert got == {"GE": "acronym", "Square-D": "real", "Square D": "real", "York": "weak",
                   "Watts": "weak", "Eaton": "real", "Squared": "weak"}
    assert V.scan("1200 watts and twenty feet squared, the carrier's demarc, york's team") == []
    assert {m.text: _strength(m) for m in V.scan("ROOM 20 FT SQUARED WITH 4 GE PANELS")} == {
        "SQUARED": "weak", "GE": "weak"}                       # a shouted sentence: no acronyms
    assert [_strength(m) for m in V.scan("manufacturer: GE")] == ["acronym"]   # one token: no shout
    for prompt in ("6 Square-D receptacles at 18 in AFF", "6 square-d receptacles at 18 in AFF"):
        _p, mk = _makers(prompt)                                # the hyphenated spelling too
        assert set(mk.values()) == {"Square D"}, prompt


def test_squared_stays_a_plain_word_for_the_scanner():
    assert "squared" in V.AMBIGUOUS_ALONE
    p, mk = _makers("4 panels 208Y/120 V for a room twenty feet squared")
    assert set(mk.values()) == {None} and "squared" in p.coverage.ignored_words


# --------------------------------------------------------------------------- DONE 3: cues

@pytest.mark.parametrize("prompt", [
    "Eaton: two panels and a 75 kVA transformer",                        # a leading '<maker>:'
    "use Eaton for everything: two panels and a 45 kVA transformer",
    "we use Eaton: two panels and a 75 kVA transformer",
    "please use Eaton. Two panels and one 75 kVA transformer.",
    "Manufacturer: Eaton. Two panels and a 75 kVA transformer.",
    "two panels and a 75 kVA transformer; manufacturer: Eaton",
    "two panels and a 75 kVA transformer, mfr Eaton",
    "basis of design Eaton, two panels and a 75 kVA transformer",
    "all the gear is Eaton: two panels and a 75 kVA transformer",
    "Eaton only: two panels and a 30 kVA transformer",
    "two panels and a 30 kVA transformer, Eaton only",
    "two panels and a 30 kVA transformer, Eaton throughout",
    "everything by Eaton -- two panels and a 30 kVA transformer",
])
def test_whole_job_cues(prompt):
    p, mk = _makers(prompt)
    assert set(mk) == {"T1", "PP-1", "PP-2"} and set(mk.values()) == {"Eaton"}, (prompt, mk)
    assert p.coverage.warnings == [] and p.coverage.ignored_words == [], (prompt, p.coverage)
    scoped = [u for u in p.coverage.understood if u.get("as") == "manufacturer" and u.get("scope")]
    assert {u["kind"] for u in scoped} == {"panelboard", "transformer"}


def test_everything_else_by_fills_only_the_items_that_name_no_maker():
    for prompt in ("everything else by Eaton: a Hammond 75 kVA transformer and two panels",
                   "two panels and a Hammond 75 kVA transformer, everything else by Eaton"):
        _p, mk = _makers(prompt)
        assert mk == {"T1": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}, (prompt, mk)


@pytest.mark.parametrize("prompt", [
    "two panels and a 30 kVA transformer, manufacturer Hammond",
    "manufacturer Hammond: two panels and a 30 kVA transformer",
])
def test_a_soft_cue_names_the_maker_only_for_the_kinds_it_makes_and_says_what_it_skipped(prompt):
    p, mk = _makers(prompt)
    assert mk == {"T1": HPS, "PP-1": None, "PP-2": None}, (prompt, mk)
    (w,) = p.coverage.warnings
    assert w.startswith(f"maker {HPS} is named for the job but the vendor directory lists no "
                        "Panelboard by it -- applied to the Dry-type distribution transformer "
                        "only (T1)")


@pytest.mark.parametrize("prompt", ["Kohler: 4 panels", "4 panels; manufacturer: Kohler"])
def test_a_soft_cue_by_a_maker_of_none_of_the_kinds_applies_to_nothing_and_says_so(prompt):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None}
    (w,) = p.coverage.warnings
    assert w.startswith("maker Kohler is named for the job but the vendor directory lists none of "
                        "its equipment (Panelboard) by it -- applied to nothing")


def test_a_hard_cue_is_taken_at_its_word_and_a_soft_one_is_not():
    p, mk = _makers("all gear by Eaton: 4 panels and 6 receptacles at 18 in AFF")
    assert set(mk.values()) == {"Eaton"}
    (said,) = [w for w in p.coverage.warnings if V.NOT_THAT_MAKER in w]
    assert said.startswith("R-1, R-2, R-3, R-4, R-5, R-6: Eaton makes nothing the directory")
    p, mk = _makers("4 panels and 6 receptacles at 18 in AFF; manufacturer: Eaton")
    assert {m for t, m in mk.items() if t.startswith("PP")} == {"Eaton"}
    assert {m for t, m in mk.items() if t.startswith("R-")} == {None}
    (w,) = p.coverage.warnings
    assert "applied to the Panelboard only (PP-1, PP-2, PP-3, PP-4)" in w


def test_a_mid_list_manufacturer_aside_binds_to_the_noun_before_it():
    for prompt in ("two panels, manufacturer Eaton, and a 75 kVA transformer, manufacturer Hammond",
                   "a 7.5 kVA transformer, mfr. Hammond, and two panels, mfr. Eaton"):
        p, mk = _makers(prompt)
        assert mk == {"T1": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}, (prompt, mk)
        assert p.coverage.warnings == [], (prompt, p.coverage.warnings)


@pytest.mark.parametrize("prompt,expect", [
    ("Eaton only for panels; transformer by Hammond", {"T1": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("Eaton for all the panels, plus a 75 kVA transformer", {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("Use Eaton panels and a Hammond 75 kVA transformer", {"T1": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("two Eaton panels only and a 30 kVA transformer", {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
])
def test_a_quantifier_that_names_a_clause_is_not_a_whole_job_cue(prompt, expect):
    _p, mk = _makers(prompt)
    assert mk == expect, (prompt, mk)


def test_two_whole_job_makers_apply_to_nothing_and_say_so():
    p, mk = _makers("all gear by Eaton and everything from Siemens: two panels")
    assert set(mk.values()) == {None}
    assert any(w.startswith("makers Eaton, Siemens are all named for the whole job") for w in p.coverage.warnings)


def test_a_maker_with_no_noun_and_no_cue_still_applies_to_nothing_and_says_so():
    for prompt in ("two panels and a 75 kVA transformer. Eaton.", "Hammond preferred; two panels"):
        p, mk = _makers(prompt)
        assert set(mk.values()) == {None}
        assert any("is named outside any equipment clause -- applied to nothing" in w
                   for w in p.coverage.warnings), (prompt, p.coverage.warnings)


# --------------------------------------------------------------------------- DONE 4: consistency

@pytest.mark.parametrize("prompt", ["a GE 75 kVA transformer", "a 75 kVA transformer by GE"])
def test_an_acronym_adjacent_to_a_noun_it_does_not_make_is_declared_and_said_like_trane(prompt):
    p, mk = _makers(prompt)
    assert mk == {"T1": "ABB"}                        # the directory files GE under ABB
    (said,) = p.coverage.warnings
    assert said.startswith("T1: ABB makes nothing the directory lists for transformer_dry") and V.NOT_THAT_MAKER in said
    model, _parsed = PP.prompt_to_intent("an electrical room with " + prompt)
    (t1,) = [fp for fp in model.family_plans if fp.tag == "T1"]
    assert t1.catalog == "eaton/dry-type-transformers"           # built from the default record ...
    assert any(V.NOT_THAT_MAKER in n for n in t1.degradations)   # ... and says so


@pytest.mark.parametrize("prompt", ["4 panels; manufacturer: GE", "all gear by GE: 4 panels"])
def test_an_acronym_takes_a_cue_like_any_real_name(prompt):
    _p, mk = _makers(prompt)
    assert set(mk.values()) == {"ABB"}, (prompt, mk)


@pytest.mark.parametrize("prompt,word", [
    ("designed by GE Consulting with 4 panels", "GE"),        # an acronym with no noun, no cue:
    ("4 panels, delivery EST 6 weeks", "EST"),                 # also an abbreviation -- a word
    ("4 panels and a 75 kVA transformer. NOTE: PRICE ALTERNATES SEPARATELY.", "PRICE"),
])
def test_an_acronym_with_neither_noun_nor_cue_is_an_ignored_word(prompt, word):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and word in p.coverage.ignored_words and not p.coverage.warnings


def test_a_maker_written_as_an_alias_is_named_as_written_in_warnings():
    p, mk = _makers("two panels and a 75 kVA transformer. Cutler-Hammer.")
    assert set(mk.values()) == {None}
    assert any(w.startswith("maker Eaton (written Cutler-Hammer) is named outside any equipment clause")
               for w in p.coverage.warnings), p.coverage.warnings


@pytest.mark.parametrize("prompt,word", [
    ("Supply 4 panels for our New York office", "York"), ("Price out 4 panels", "Price"),
    ("two panels rated 1200 Watts", "Watts"), ("4 Simplex receptacles at 18 in AFF", "Simplex"),
])
def test_one_word_plain_english_names_are_still_makers_only_where_they_make_the_kind(prompt, word):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and word in p.coverage.ignored_words and not p.coverage.warnings


@pytest.mark.parametrize("prompt,pairs", [
    ("Price grilles and two panels", [("grilles", "Price Industries")]),
    ("two panels and Price grilles", [("grilles", "Price Industries")]),
    ("Titus diffusers, Price grilles and 2 panels", [("diffusers", "Titus"), ("grilles", "Price Industries")]),
])
def test_price_and_titus_make_air_terminals_by_name(prompt, pairs):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None}
    assert [(r["text"], r.get("manufacturer")) for r in p.coverage.not_built] == pairs
    assert "Price" not in p.coverage.ignored_words
    d = V.describe("Price", kind="air_terminal")
    assert d["known"] and d["records"] == [] and "known by name only" in d["line"]
    assert "not buildable here yet" in d["line"]                 # the pending row's own caveat


def test_a_cell_naming_two_makers_declares_neither():
    d = V.declared("Eaton or Siemens", "panelboard")
    assert (d["known"], d["vendor"], d["record"]) == (False, None, None)
    assert d["line"].startswith("'Eaton or Siemens' names 2 makers (Eaton, Siemens), so no single "
                                "maker is read from it -- built here from what tekton holds")
    assert d["line"].endswith(V.NOT_THAT_MAKER)      # the marker every surface filters on
    # one maker written the long way is still one maker
    assert V.declared("Square D by Schneider Electric", "panelboard")["record"] == (
        "square-d", "nq-nf-iline-panelboards")
    assert V.declared("Eaton Corporation", "panelboard")["record"] == ("eaton", "pow-r-line-panelboards")
    from rvt.ifc import intent as I
    rec, note = I.declared_maker({"Manufacturer": "Eaton / Siemens"}, "panelboard")
    assert rec is None and "names 2 makers" in note


def test_the_directory_and_the_taxonomy_still_gate_clean():
    assert V.check() == []
    assert [pr for pr in TX.check() if not pr.startswith("warning")] == []


# --------------------------------------------------------------------------- review of #741, round 2

@pytest.mark.parametrize("prompt,maker", [
    ("6 Hubbell hospital grade receptacles at 18 in AFF", "Hubbell Wiring Device-Kellems"),
    ("4 Eaton hospital grade panels", "Eaton"),
    ("two Eaton lab area panels 100 A", "Eaton"),
    ("an Eaton garage sub panel", "Eaton"),
    ("two Eaton mall tenant panels 100 A", "Eaton"),
    ("four Eaton dorm floor panels 100 A MLO", "Eaton"),
    ("two Siemens data center row panels", "Siemens"),
    ("an Eaton campus loop switchboard 2000 A", "Eaton"),
])
def test_a_place_word_among_the_nouns_qualifiers_is_not_a_place(prompt, maker):
    _p, mk = _makers(prompt)
    assert set(mk.values()) == {maker}, (prompt, mk)


def test_a_place_needs_saying_as_one_when_equipment_follows():
    # said as a place: a locative word before the name, or a proper place name after it
    for prompt in ("for the Edwards building: 4 panels", "the Kohler campus needs 4 panels",
                   "in the Sloan wing, 4 panels", "Hammond Street vault: a 75 kVA transformer",
                   "in Cooper Hall, two panels"):
        _p, mk = _makers(prompt)
        assert set(mk.values()) == {None}, (prompt, mk)
    # not said as one: the maker rules decide ('Sloan' makes no panelboard: an ignored word)
    p, mk = _makers("Sloan wing: 4 panels")
    assert set(mk.values()) == {None} and "Sloan" in p.coverage.ignored_words and not p.coverage.warnings
    p, mk = _makers("6 Hubbell hospital grade receptacles at 18 in AFF and two panels (Eaton only) and "
                    "a 45 kVA transformer")
    assert {t: m for t, m in mk.items() if not t.startswith("R-")} == {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}
    assert {m for t, m in mk.items() if t.startswith("R-")} == {"Hubbell Wiring Device-Kellems"}


@pytest.mark.parametrize("prompt,expect", [
    ("two panels (Eaton only) and a 45 kVA transformer", {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("4 panels (Eaton only) and a 45 kVA transformer (any make)",
     {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton", "PP-3": "Eaton", "PP-4": "Eaton"}),
    ("two panels - Eaton for all - and a 30 kVA transformer", {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("two panels, Eaton only, and a 30 kVA transformer", {"T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("a 30 kVA transformer (Hammond only) and two panels", {"T1": HPS, "PP-1": None, "PP-2": None}),
    # leading / trailing: still the whole job
    ("Eaton only: two panels and a 30 kVA transformer", {"T1": "Eaton", "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("two panels and a 30 kVA transformer, Eaton only", {"T1": "Eaton", "PP-1": "Eaton", "PP-2": "Eaton"}),
    # 'both' names the group before it, not the whole sentence
    ("a 2000 A switchboard feeding two panels, both by Eaton, and a 45 kVA transformer",
     {"MSB": None, "T1": None, "PP-1": "Eaton", "PP-2": "Eaton"}),
])
def test_x_only_and_for_all_inside_a_list_name_what_stands_before_them(prompt, expect):
    p, mk = _makers(prompt)
    assert mk == expect, (prompt, mk)
    assert p.coverage.warnings == [], (prompt, p.coverage.warnings)


@pytest.mark.parametrize("prompt,expect", [
    ("two panels by Eaton, Hammond 75 kVA transformer", {"T1": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}),
    ("a 75 kVA transformer by Hammond, Eaton panels LP-1 and LP-2", {"T1": HPS, "LP-1": "Eaton", "LP-2": "Eaton"}),
    ("panels LP-1 and LP-2 from Eaton, Siemens 2000 A switchboard", {"MSB": "Siemens", "LP-1": "Eaton", "LP-2": "Eaton"}),
    ("two panels by Eaton, and a transformer by Hammond, Cummins genset", {"T1": HPS, "PP-1": "Eaton", "PP-2": "Eaton"}),
])
def test_a_comma_between_two_items_makers_separates_them(prompt, expect):
    p, mk = _makers(prompt)
    assert mk == expect, (prompt, mk)
    assert not any("both named" in w for w in p.coverage.warnings), p.coverage.warnings


@pytest.mark.parametrize("prompt", ["Eaton, Siemens: 4 panels", "Eaton, Siemens or ABB: 4 panels",
                                    "4 panels; manufacturer: Eaton, Siemens"])
def test_a_comma_inside_an_or_list_or_next_to_a_cue_still_joins(prompt):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None}
    assert any("are all named for the whole job -- applied to nothing" in w for w in p.coverage.warnings)


def test_a_dropped_weak_name_in_a_context_phrase_stays_visible():
    p, mk = _makers("4 panels beside the York units and a 45 kVA transformer")
    assert set(mk.values()) == {None} and "York" in p.coverage.ignored_words and not p.coverage.warnings


def test_a_brand_and_its_parent_in_one_cell_declare_the_brand():
    # said in words ('by', 'an ... brand', 'a division of'); the parent lists nothing for the kind
    for cell in ("Cooper Lighting Solutions by Eaton", "Halo, an Eaton brand",
                 "Metalux, a division of Cooper Lighting", "Metalux - Cooper Lighting"):   # (one key)
        d = V.declared(cell, "downlight")
        assert (d["known"], d["vendor"]) == (True, "cooper-lighting"), (cell, d)
    # anything else names two makers and declares neither -- said, never picked
    for cell, kind in (("Eaton, Siemens", "panelboard"), ("Eaton - Siemens", "panelboard"),
                       ("Eaton by Siemens", "panelboard"), ("Eaton (Siemens)", "panelboard"),
                       ("Eaton / Siemens", "panelboard"), ("Cooper Lighting (Eaton)", "downlight"),
                       ("Eaton (Siemens)", "transformer_dry"), ("Eaton - Siemens", "transformer_dry")):
        d = V.declared(cell, kind)
        assert (d["known"], d["vendor"], d["record"]) == (False, None, None), (cell, kind, d)


# --------------------------------------------------------------------------- review of #741, round 3

@pytest.mark.parametrize("prompt,maker", [
    # an article / possessive before the maker and Title Case change nothing: the place word
    # still qualifies the equipment noun it stands against
    ("the Eaton house panel and six tenant panels", "Eaton"),
    ("our Eaton house panel and six tenant panels", "Eaton"),
    ("an Eaton house panel and six tenant panels", "Eaton"),
    ("for two Eaton house panels 100 A and six tenant panels", "Eaton"),
    ("feed the Eaton house panel from the switchboard", "Eaton"),
    ("replace one of the Eaton lab panels with a 225 A panel", "Eaton"),
    ("the Eaton branch panels are 100 A MLO, plus a 45 kVA transformer", "Eaton"),   # noun starts inside
    ("6 Leviton Hospital Grade receptacles at 18 in AFF", "Leviton"),
    ("6 Hubbell Hospital Grade duplex receptacles at 18 in AFF and two panels", "Hubbell Wiring Device-Kellems"),
    ("Two Eaton Lab Panels 100 A", "Eaton"), ("4 Eaton Hospital Grade Panels", "Eaton"),
    ("Six Eaton Suite Panels 100 A MLO", "Eaton"), ("An Eaton Campus Loop Switchboard 2000 A", "Eaton"),
    ("6 Hubbell Hospital Grade Receptacles At 18 In AFF", "Hubbell Wiring Device-Kellems"),
])
def test_articles_and_title_case_do_not_turn_a_qualifier_into_a_place(prompt, maker):
    _p, mk = _makers(prompt)
    assert maker in set(mk.values()), (prompt, mk)
    named = {t for t, m in mk.items() if m == maker}
    assert all(mk[t] in (None, maker) for t in mk), (prompt, mk)
    assert named, prompt


@pytest.mark.parametrize("prompt", [
    "Cooper Hall panels: replace two panels", "the Kohler campus panels: 4 panels", "the Sloan house panel and 4 panels",
])
def test_a_place_name_qualifying_a_noun_it_does_not_make_is_still_an_ignored_word(prompt):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and not p.coverage.warnings, (prompt, mk, p.coverage.warnings)


def test_context_reaches_the_qualified_noun_across_qualifier_words():
    p, mk = _makers("two panels next to the existing Siemens site lighting panel")
    # (how many LP items 'the ... lighting panel' yields is #740's count question, not this one)
    assert {m for t, m in mk.items() if t.startswith("LP")} == {"Siemens"}, mk
    assert {m for t, m in mk.items() if t.startswith("PP")} == {None}, mk
    assert not any("names existing or neighbouring equipment" in w for w in p.coverage.warnings)


def test_a_client_before_a_leading_colon_is_not_the_jobs_maker():
    _p, mk = _makers("electrical room for Eaton: 4 panels and a 75 kVA transformer")
    assert mk["T1"] is None and {m for t, m in mk.items() if t.startswith("PP")} == {"Eaton"}


def test_three_makers_on_one_noun_are_all_named_and_none_applied():
    p, mk = _makers("two Eaton or Siemens or ABB panels")
    assert set(mk.values()) == {None}
    assert p.coverage.warnings == ["PP-1, PP-2: makers ABB, Eaton, Siemens are all named for it -- "
                                   "applied none; name one"]


def test_long_prompts_stay_linear():
    import time
    clause = "two 225 A panels 42 spaces 480Y/277 V by Eaton for the Edwards building, "
    t = time.perf_counter()
    p = PP.parse_prompt("an electrical room 40 ft by 30 ft with " + clause * 25 + "and a 75 kVA transformer")
    assert time.perf_counter() - t < 2.0 and len(p.items) == 51


# --------------------------------------------------------------------------- review of #741, round 4

@pytest.mark.parametrize("prompt,untouched", [
    # an item-level 'X only' trailing the job names its own noun's items, never the others
    ("Provide 4 panels and a 75 kVA transformer. Panelboards shall be by Eaton only.", ["T1"]),
    ("4 panels and a 45 kVA transformer; panels Eaton only", ["T1"]),
    ("Provide 4 panels and a 75 kVA transformer. Transformers: Hammond only.", ["PP-1", "PP-2", "PP-3", "PP-4"]),
    ("4 panels and a 45 kVA transformer; receptacles Hubbell only", ["T1", "PP-1", "PP-2", "PP-3", "PP-4"]),
])
def test_a_trailing_noun_x_only_names_that_noun_not_the_job(prompt, untouched):
    _p, mk = _makers(prompt)
    assert all(mk[t] is None for t in untouched), (prompt, mk)
    assert any(m for m in mk.values()), (prompt, mk)


@pytest.mark.parametrize("prompt,name", [
    ("4 panels and a 45 kVA transformer; breakers Eaton only", "Eaton"),        # no equipment noun:
    ("4 panels and a 45 kVA transformer; breakers: Square D only", "Square D"),  # not a cue at all
    ("4 panels and a 75 kVA transformer; use Eaton breakers", "Eaton"),          # a part, not the job
    ("two panels and a 45 kVA transformer, using Eaton lugs", "Eaton"),
    ("4 panels; specify Siemens breakers", "Siemens"),
])
def test_a_maker_named_for_a_part_applies_to_nothing_and_says_so(prompt, name):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None}, (prompt, mk)
    assert any(w.startswith(f"maker {name} is named outside any equipment clause") for w in p.coverage.warnings), \
        p.coverage.warnings


@pytest.mark.parametrize("prompt,maker", [
    ("6 Hubbell hospital grade 20 A duplex receptacles at 18 in AFF", "Hubbell Wiring Device-Kellems"),
    ("6 Leviton hospital grade 20A tamper resistant receptacles at 18 in AFF", "Leviton"),
    ("6 Hubbell hospital grade 5-20R receptacles at 18 in AFF", "Hubbell Wiring Device-Kellems"),
    ("Hubbell hospital grade 20 A receptacles: 6 at 18 in AFF", "Hubbell Wiring Device-Kellems"),
    ("6 Hubbell Hospital Grade 20A Receptacles", "Hubbell Wiring Device-Kellems"),
    ("6 Hubbell hospital grade (green dot) receptacles at 18 in AFF", "Hubbell Wiring Device-Kellems"),
    ("two Siemens data center 400 A panels", "Siemens"),
    ("four Eaton branch circuit 42-circuit panels", "Eaton"),
    ("two Eaton lab 225 A panels", "Eaton"), ("the Eaton lab 225 A panels", "Eaton"),
    ("an Eaton station service 45 kVA transformer", "Eaton"),
    ("an Eaton house 100 A panel", "Eaton"), ("An Eaton House 100 A Panel", "Eaton"),
])
def test_ratings_between_a_qualifier_and_its_noun_do_not_make_a_place(prompt, maker):
    _p, mk = _makers(prompt)
    assert set(mk.values()) == {maker}, (prompt, mk)


@pytest.mark.parametrize("prompt,name", [
    ("6 Hubbell hospital grade, tamper resistant receptacles at 18 in AFF", "Hubbell Wiring Device-Kellems"),
    ("two Eaton house and tenant panels 100 A", "Eaton"),
])
def test_a_counted_maker_cut_from_its_noun_by_a_boundary_is_said_not_dropped(prompt, name):
    p, mk = _makers(prompt)                          # (main's behaviour: disclosed, not silent)
    assert set(mk.values()) == {None}
    assert any(w.startswith(f"maker {name} is named outside any equipment clause") for w in p.coverage.warnings)


@pytest.mark.parametrize("prompt", ["For the Kohler campus, provide 4 panels", "Kohler headquarters; 4 panels and a transformer"])
def test_a_place_cut_from_the_nouns_by_a_boundary_is_still_a_place(prompt):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and "Kohler" in p.coverage.ignored_words and not p.coverage.warnings


def test_for_everything_except_is_said_not_modelled():
    p, mk = _makers("Eaton for everything except the transformer: two panels and a 45 kVA transformer")
    assert {m for t, m in mk.items() if t.startswith("PP")} == {"Eaton"}
    assert any("'except ...' -- the exception is not modelled" in w for w in p.coverage.warnings)


def test_per_x_is_a_source_not_the_jobs_maker():
    _p, mk = _makers("Per Eaton: 4 panels and a 75 kVA transformer")
    assert mk["T1"] is None and {m for t, m in mk.items() if t.startswith("PP")} == {"Eaton"}


# --------------------------------------------------------------------------- review of #741, round 5

@pytest.mark.parametrize("prompt", [
    "electrical room 20 ft by 15 ft. Eaton equipment: 4 panels and a 75 kVA transformer",
    "electrical room 20 ft by 15 ft. All Eaton equipment: 4 panels and a 75 kVA transformer",
    "electrical room 20 ft by 15 ft with 4 panels and a 75 kVA transformer using Eaton equipment",
    "provide 4 panels and a 75 kVA transformer using Eaton gear",
    "furnish Eaton equipment: 4 panels and a 75 kVA transformer",
    "Eaton equipment - 4 panels and a 75 kVA transformer",
    "use Eaton equipment for 4 panels and a 75 kVA transformer",
    "4 panels and a 75 kVA transformer, Eaton equipment",
    "4 panels and a 75 kVA transformer with Eaton equipment",
    "Eaton gear. 4 panels and a 75 kVA transformer.",
    "4 panels and a 75 kVA transformer, all Eaton equipment",
])
def test_maker_equipment_closing_a_phrase_or_led_by_a_job_verb_names_the_whole_job(prompt):
    p, mk = _makers(prompt)
    assert set(mk) == {"T1", "PP-1", "PP-2", "PP-3", "PP-4"} and set(mk.values()) == {"Eaton"}, (prompt, mk)
    assert p.coverage.warnings == [], (prompt, p.coverage.warnings)


def test_existing_maker_equipment_is_still_context_not_a_cue():
    p, mk = _makers("two panels beside existing Siemens equipment and a new transformer")
    assert set(mk.values()) == {None}
    assert any("names existing or neighbouring equipment" in w for w in p.coverage.warnings)


@pytest.mark.parametrize("prompt,prefix", [
    ("two Eaton lab 3-phase panels", "PP"), ("an Eaton house 1ph panel", "PP"),
    ("two Eaton site 3ph 480V lighting panels", "LP"), ("an Eaton house 120/240V 1-phase 100 A panel", "PP"),
    ("two Eaton lab 208Y/120V 3-phase 4-wire 225 A panels", "PP"), ("an Eaton house 100A 3P panel", "PP"),
    ("two Eaton lab 3PH 4W 225A panels", "PP"), ("an Eaton house type PRL1a panel", "PP"),
    ("an Eaton campus 15 kV switchgear lineup", "MSB"),
])
def test_phase_pole_model_tokens_in_a_qualifier_gap_do_not_make_a_place(prompt, prefix):
    _p, mk = _makers(prompt)                          # (item COUNTS here are #740's, not judged)
    assert {m for t, m in mk.items() if t.startswith(prefix)} == {"Eaton"}, (prompt, mk)


def test_one_vocabulary_for_adjacency_and_qualifier_gaps():
    from rvt.frontdoor.prompt_intent import _only_ratings, _strip_ratings
    for gap in (" 3-phase ", " 208Y/120V 3-phase 4-wire 225 A ", " type PRL1a ", " NEMA 3R ", " 15 kV ",
                " 480-208Y/120V 75 kVA ", " main circuit breaker 225 amperes ", " 5-20R "):
        assert _only_ratings(gap), gap
        assert not _strip_ratings(gap).strip(" -/()'\","), gap
    assert not _only_ratings(" hospital grade ") and not _only_ratings(" backup ")


def test_an_exception_after_any_whole_job_cue_is_said():
    p, mk = _makers("Eaton only, except the transformer by Hammond: 4 panels and a 75 kVA transformer")
    assert {m for t, m in mk.items() if t.startswith("PP")} == {"Eaton"}
    assert any("'except ...' -- the exception is not modelled" in w for w in p.coverage.warnings)

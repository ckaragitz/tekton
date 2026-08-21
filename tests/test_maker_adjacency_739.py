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


@pytest.mark.parametrize("prompt,word", [
    ("two panels beside existing Siemens equipment and a new transformer", "Siemens"),
    ("a new transformer and two panels beside the existing Siemens equipment", "Siemens"),
    ("two panels next to the Eaton gear and a transformer", "Eaton"),
])
def test_existing_gear_nearby_is_context_not_a_declaration(prompt, word):
    p, mk = _makers(prompt)
    assert set(mk.values()) == {None} and word in p.coverage.ignored_words, (prompt, mk)
    assert p.coverage.warnings == []


# --------------------------------------------------------------------------- DONE 1: adjacency

@pytest.mark.parametrize("prompt,tags", [
    ("a Trane panel", ["PP-1"]),                                  # <maker> <noun>
    ("two new Kohler 225 A panels", ["PP-1", "PP-2"]),            # <maker> [ratings] <noun>
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


def test_an_acronym_outside_any_clause_is_named_as_written():
    p, mk = _makers("designed by GE Consulting with 4 panels")
    assert set(mk.values()) == {None}
    assert any(w.startswith("maker ABB (written GE) is named outside any equipment clause")
               for w in p.coverage.warnings)


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
    assert d["line"].startswith("'Eaton or Siemens' names 2 makers (Eaton, Siemens) -- no single "
                                "maker is read from it")
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

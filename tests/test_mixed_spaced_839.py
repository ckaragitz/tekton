"""A mixed number whose slash is spaced like its hyphen is read whole (#839).

``_NUM_CORE`` accepted spaces around a mixed number's hyphen ("2 - 1/2") but
not around its slash, so the prompt route split "24 - 1 / 2 in wide" at the
slash and read the trailing fraction alone:

    "cable tray 24 - 1 / 2 in wide"   -> width_in    = 0.5    given   (24 1/2)
    "a 2 1 / 2 in conduit"            -> diameter_in = 2.0    given   (2 1/2)

A wrong number under ``given``, the tier that means "you stated it".  Found by
the reviewer of #835, whose unit rows showed ``_to_number`` already reads these
strings -- the regex never handed them over.
"""
from __future__ import annotations

import itertools

import pytest

from rvt.famgen import archetypes as AR

GIVEN = "given"


@pytest.mark.parametrize("prompt,key,want", [
    ("cable tray 24 - 1 / 2 in wide", "width_in", 24.5),
    ("a 2 - 1 / 2 in conduit", "diameter_in", 2.5),
    ("a 2 1 / 2 in conduit", "diameter_in", 2.5),
    ("strut channel 1 - 5 / 8 in tall", "height_in", 1.625),
    ("cable tray width 12 - 3 / 16 in", "width_in", 12.1875),
    # the forms that always worked keep working
    ("a 2-1/2 in conduit", "diameter_in", 2.5),
    ("a 2 - 1/2 in conduit", "diameter_in", 2.5),
    ("a 2 1/2 in conduit", "diameter_in", 2.5),
    ("a 1 / 2 in conduit", "diameter_in", 0.5),
])
def test_a_spaced_mixed_number_is_one_number(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


# A whole number followed by a slash token that is NOT a fraction of a unit
# keeps the whole number (#841 review): the round-1 head joined them into a
# "mixed number" -- "width 12 480 / 277 V" was 13.73 in, stamped given.
@pytest.mark.parametrize("prompt,key,want", [
    ("wireway width 12 480 / 277 V", "width_in", 12.0),
    ("lighting control panel width 20 277 / 480 V", "width_in", 20.0),
    ("lighting control panel width 20 277/480 V", "width_in", 20.0),   # 20.58 on main
    ("lighting control panel height 36 120 / 277 V", "height_in", 36.0),
    ("cable tray, width 24 120 / 208 V feed", "width_in", 24.0),
    ("lighting control panel width 24 24 / 7 operation", "width_in", 24.0),
    ("conduit trade size 2 4 / 0 conductors", "diameter_in", 2.0),
    ("junction box depth 6 3 / 0 feeders", "depth_in", 6.0),
    ("cable tray wide 12 12/2 cable", "width_in", 12.0),
    ("cable tray wide 6 3 / 4w", "width_in", 6.0),
    ("cable tray wide 6 3/4w", "width_in", 6.0),                    # 6.75 on main
    # ... while real unit fractions, thirds and a unit glued on still join
    ("a 2 1/3 ft long conduit", "length_ft", 7 / 3),
    ("conduit length 7 1/3", "length_ft", 22 / 3),               # no unit: thirds still join
    ("a 2 1/2in conduit", "diameter_in", 2.5),
    ("a 1-5/8\" strut channel", "height_in", 1.625),
])
def test_a_slash_token_after_a_number_is_not_its_fraction(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


def _spaced():
    """Every spacing of a mixed number's hyphen and slash, on every inch
    parameter of every archetype, in both phrasings, noun first and last.
    Measured: main gets 13,500 of 18,000 wrong; this fix 0; none worse.
    Round 9: the 2,700 with a TIGHT hyphen and a spaced slash ("2-1 / 2")
    are lists now and left out -- 15,300 remain."""
    for key, a in AR.ARCHETYPES.items():
        noun = a.title.split(" - ")[0].lower()
        for p in [p for p in a.params if p.aliases and p.unit == "in"]:
            al = p.aliases[0]
            for w, (n, d) in itertools.product((1, 2, 12), ((1, 2), (5, 8), (3, 16))):
                for hy, sl in itertools.product(["-", " - ", "- ", " -", " "], ["/", " / ", " /", "/ "]):
                    if hy == "-" and sl != "/":
                        continue      # a TIGHT hyphen before a spaced slash is a list (#841 round 9)
                    num = f"{w}{hy}{n}{sl}{d}"
                    for ph in (f"{num} in {al}", f"{al} {num} in"):
                        for pr in (f"{noun} {ph}", f"a {ph} {noun}"):
                            yield key, pr, p.key, w + n / d


def test_every_spacing_of_a_mixed_number_binds_whole_and_alone():
    fails, total = [], 0
    for key, pr, pk, v in _spaced():
        total += 1
        a = AR.archetype(key)
        r = AR.resolve_prompt(pr, product=key)
        stray = [k for k, pv in r.provenance.items() if pv == GIVEN and k != pk
                 and not (a.param(k).follows == pk and abs(r.values[k] - v) < 1e-6)]
        if r.provenance[pk] != GIVEN or abs(r.values[pk] - v) > 1e-6 or stray:
            fails.append((pr, r.values[pk], stray))
    assert total >= 15300, total      # 18,000 less the 2,700 tight-hyphen/spaced-slash lists (round 9)
    assert not fails, f"{len(fails)}/{total} misread; first: {fails[:3]}"


@pytest.mark.parametrize("prompt", ["cable tray width 24 - 120/208 V",     # 24.577 given on main
                                    "cable tray width 24 - 120 / 208 V",
                                    "wireway width 12 - 480 / 277 V"])
def test_a_hyphen_before_a_slash_token_never_joins_them(prompt):
    """"24 - 120/208" is not 24 120/208 in.  Honest nominal is acceptable
    here (the hyphen makes it a range-like token); a joined value stamped
    ``given`` is not."""
    r = AR.resolve_prompt(prompt)
    w = r.values["width_in"]
    assert not (r.provenance["width_in"] == GIVEN and abs(w - round(w)) > 1e-9), (prompt, w)


# Round 2 (#841): a fraction FOLLOWED BY A UNIT -- or by the 'x' of a cross --
# is always a fraction of that unit, whatever its denominator.  Round 1 kept
# only 2/3/4/8/16/32/64 everywhere and "wide 2 1/5 in" became 2.0, given.
@pytest.mark.parametrize("prompt,key,want", [
    ("cable tray wide 2 1/5 in", "width_in", 2.2),
    ("a 2 1/5 in wide cable tray", "width_in", 2.2),
    ("cable tray wide 2-3/10 in", "width_in", 2.3),
    ("a nema 12 cable tray wide 2 1/5 in", "width_in", 2.2),
    ("conduit 10 5/12 ft long", "length_ft", 10 + 5 / 12),
    ("cable tray wide 12 7 / 20 inches", "width_in", 12.35),
    ("a cable tray wide 1 1/2ins", "width_in", 1.5),          # glued plural unit
    ("a cable tray wide 1-1/2ins", "width_in", 1.5),
    # round 3: the unit may be joined by a hyphen (the grammar's _SEP), and
    # the typographic marks are units -- all fell back to the whole number
    ("conduit length 10 5/12-ft", "length_ft", 10 + 5 / 12),
    ("cable tray width 24 1/5-inch", "width_in", 24.2),
    ("cable tray width 24 3/10-in.", "width_in", 24.3),
    ("conduit 10 5/12-ft long", "length_ft", 10 + 5 / 12),
    ("a 12 1/5-in wide cable tray", "width_in", 12.2),
    ("cable tray width 24 - 1 / 5-in", "width_in", 24.2),
    ("cable tray wide 2 1/5\u2033", "width_in", 2.2),        # ″
    ("cable tray wide 2 1/5\u201d", "width_in", 2.2),        # ”
])
def test_a_fraction_followed_by_a_unit_joins_whatever_its_denominator(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


@pytest.mark.parametrize("prompt,dims", [
    ("a 2 1/5 x 4 in wireway", (2.2, 4.0)),                    # round 1: W4 H4 given
    ("a 2 1/5×4 in wireway", (2.2, 4.0)),
    ("a 2 1/2x4 in wireway", (2.5, 4.0)),                      # round 1: nominal
    ("a 4x2 1/2x4 in junction box", (4.0, 2.5, 4.0)),
])
def test_a_mixed_number_inside_a_cross_keeps_the_cross(prompt, dims):
    r = AR.resolve_prompt(prompt)
    keys = ("width_in", "height_in", "depth_in")[:len(dims)]
    assert tuple(round(r.values[k], 6) for k in keys) == pytest.approx(dims), (prompt, r.values)
    assert all(r.provenance[k] == GIVEN for k in keys)


def _denominators():
    """Every inch alias x whole numbers x denominators in and out of the
    unit-less set, three separators, four units, both phrasings, noun first
    and last.  Number-first phrases with a glued "ins" or a typographic
    inch mark are left out: the unit list has neither for number-first
    phrases on main either (#844).  Measured on the full set: main and this head both 3,150
    wrong of 31,590, 0 worse; round 1 of #841 was 17,681 worse on the
    reviewer's generator."""
    for key, a in AR.ARCHETYPES.items():
        noun = a.title.split(" - ")[0].lower()
        for p in [p for p in a.params if p.aliases and p.unit == "in"]:
            al = p.aliases[0]
            for w, (n, d) in itertools.product((1, 12), ((1, 5), (3, 10), (5, 12), (7, 20), (1, 6), (1, 2))):
                for sep, u in itertools.product((" ", "-", " - "),
                                                ("in", "inch", '"', "ins", "-in", "-inch", "\u2033")):
                    glue = "" if u in ('"', "ins", "-in", "-inch", "\u2033") else " "
                    num = f"{w}{sep}{n}/{d}"
                    # number-first needs the unit in _UNITS, which has no "ins"
                    # and no typographic mark -- pre-existing on main (#844)
                    forms = [f"{al} {num}{glue}{u}"] + ([] if u in ("ins", "\u2033") else [f"{num}{glue}{u} {al}"])
                    for ph in forms:
                        for pr in (f"{noun} {ph}", f"a {ph} {noun}"):
                            yield key, pr, p.key, w + n / d


def test_every_denominator_joins_when_a_unit_follows():
    fails, total = [], 0
    for key, pr, pk, v in _denominators():
        total += 1
        r = AR.resolve_prompt(pr, product=key)
        if r.provenance[pk] != GIVEN or abs(r.values[pk] - v) > 1e-6:
            fails.append((pr, r.values[pk]))
    assert total > 5000, total
    assert not fails, f"{len(fails)}/{total} misread; first: {fails[:3]}"


# Round 4 (#841): only an UNSPACED slash ahead of a unit takes any denominator.
# A spaced one must be a proper fraction of at most two digits -- "480 / 277 in
# the electrical room" is a voltage followed by a preposition, and a quote
# after "120 / 208" read as feet delivered a 294.9 in panel, stamped given.
@pytest.mark.parametrize("prompt,key,want", [
    ("wireway width 12 480 / 277 in the electrical room", "width_in", 12.0),
    ("lighting control panel width 24 120 / 208 'LP-1'", "width_in", 24.0),
    ("junction box depth 6 12 / 2 in each run", "depth_in", 6.0),
    ("lighting control panel width 24 24 / 7 x 365 operation", "width_in", 24.0),
    ("lighting control panel height 36 277 / 480 in a nema 1 enclosure", "height_in", 36.0),
    ("cable tray width 24 480 / 277 footprint", "width_in", 24.0),
    ("cable tray width 24 480 / 277 feet away", "width_in", 24.0),
    ("cable tray wide 12 20 / 19 in", "width_in", 12.0),           # improper, 2 digits
    ("cable tray wide 12 5 / 5 in", "width_in", 12.0),             # not proper
    ("cable tray wide 12 4 / 0 in", "width_in", 12.0),
])
def test_a_spaced_improper_slash_is_never_a_fraction_even_before_a_unit(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))


@pytest.mark.parametrize("prompt,key,want", [
    ("conduit length 10 11 / 12 ft", "length_ft", 10 + 11 / 12),   # 2-digit over 2-digit
    ("conduit length 10 5 / 12 ft", "length_ft", 10 + 5 / 12),     # 1-digit over 2-digit
    ("cable tray wide 12 12 / 20 in", "width_in", 12.6),           # first digit 1 < 2
    ("cable tray wide 12 19 / 20 in", "width_in", 12.95),
    ("cable tray wide 12 11 / 16 in", "width_in", 12 + 11 / 16),   # same first digit
    ("cable tray wide 2 3 / 5 in", "width_in", 2.6),               # 1-digit over 1-digit
    ("cable tray wide 12 480/277 in", "width_in", 12 + 480 / 277), # UNSPACED: main's reading, kept
])
def test_a_spaced_proper_fraction_before_a_unit_still_joins(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


def test_a_spaced_fraction_joins_only_when_proper_over_a_measuring_denominator():
    """Exhaustive over n in 1..99, d in 1..130: '12 n / d in' joins iff n < d
    and d is one digit or one of 10, 12, 16, 20, 32, 64 (round 5: 12 / 24 is
    a low-voltage pair, 9 / 23 a date; three digits never join)."""
    wrong = []
    for d in range(1, 131):
        for n in range(1, 100):
            r = AR.resolve_prompt(f"cable tray wide 12 {n} / {d} in")
            want = 12 + n / d if n < d and (d < 10 or d in (10, 12, 16, 20, 32, 64)) else 12.0
            if abs(r.values["width_in"] - want) > 1e-9:
                wrong.append((n, d, r.values["width_in"]))
    assert not wrong, wrong[:10]



# Round 5 (#841): a REJECTED fraction must not be re-read from its own middle.
# The lookbehind blocked only one space: "24 - 5/12 wide" re-matched at
# "5/12 wide" and stamped a 0.42 in tray ``given``; and "24 - 5 / 12 wide", once
# the numerator was blocked, at "12 wide".  Rejected, the phrase stays nominal.
# Round 6: those are MEASURING fractions, which now join with or without a
# unit -- main's values, and what the user wrote ...
@pytest.mark.parametrize("prompt,key,want", [
    ("cable tray 24 - 5/12 wide", "width_in", 24 + 5 / 12),
    ("a 2 - 1/5 wide cable tray", "width_in", 2.2),
    ("conduit 10 - 5/12 long", "length_ft", 10 + 5 / 12),
    ("cable tray 12  5/12 wide", "width_in", 12 + 5 / 12),     # double space
    ("cable tray 12\t5/12 wide", "width_in", 12 + 5 / 12),    # tab
    ("cable tray 24     5/12 wide", "width_in", 24 + 5 / 12),  # five spaces
    ("lighting control panel 20 - 3/10 wide", "width_in", 20.3),
    ("wireway 8 - 5/6 tall", "height_in", 8 + 5 / 6),
    ("strut channel 1 - 7/20 tall", "height_in", 1.35),
    ("cable tray 24 - 5 / 12 wide", "width_in", 24 + 5 / 12),
    ("cable tray 24 5 / 12 wide", "width_in", 24 + 5 / 12),
    ("junction box sheet thickness 1  -  5 / 12 each", "thickness_in", 1 + 5 / 12),
])
def test_a_measuring_fraction_joins_its_whole_number_without_a_unit(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


# ... and a REJECTED fraction (not a measuring one) is never re-read from its
# own middle, whatever the separator's width (round 6: a fixed lookbehind
# list let five spaces through, and also barred "LP-1 - 3/4 in conduit").
@pytest.mark.parametrize("prompt,key", [
    ("cable tray 24 - 5/11 wide", "width_in"),
    ("cable tray 24     5/11 wide", "width_in"),                # five spaces
    ("cable tray 12  -  7/23 wide", "width_in"),
    ("lighting control panel 20  -  3/13 deep", "depth_in"),
    ("junction box 4   -   5/11 deep", "depth_in"),
    ("cable tray 24\u00a0\u00a0\u00a0\u00a0\u00a05/11 wide", "width_in"),   # non-breaking
    ("cable tray 24 \t \t 5/11 wide", "width_in"),
    ("cable tray 24 - 5 / 11 wide", "width_in"),
])
def test_a_rejected_fraction_is_never_read_from_its_middle(prompt, key):
    r = AR.resolve_prompt(prompt)
    assert r.provenance[key] != GIVEN, (prompt, r.values[key], r.quoted.get(key))


# ... while a fraction after something that is NOT a whole number reads as
# main reads it: a tag, a voltage's tail, a cross, a separator the mixed
# grammar never accepts ("--", " / ")
@pytest.mark.parametrize("prompt,key,want", [
    ("EMT for LP-1 - 3/4 in conduit", "diameter_in", 0.75),
    ("conduit for EF-2 - 1/2 in dia", "diameter_in", 0.5),
    ("panel LP-1 -- 3/4 in conduit", "diameter_in", 0.75),
    ('conduit rev 3 -- 3/4" trade size', "diameter_in", 0.75),
    ("junction box 4x4 / 6 in deep", "depth_in", 6.0),
    ("wireway 480/277 / 12 in wide", "width_in", 12.0),
    ("strut channel 1-5/8 x 1-5/8 - 1/2 in slot length", "slot_length_in", 0.5),
    ("junction box width 10 -- 5/8 in sheet thickness", "thickness_in", 0.625),
    ("conduit for LP-1 - 5 / 11 in dia", "diameter_in", 5 / 11),   # a tag's digit is no whole number
])
def test_a_fraction_after_a_tag_or_a_foreign_separator_reads_as_main(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


# ... and "N / M/D" stays one token no number reads (main's tail), never
# N / M: "24 / 3/4" was 8 in, "8 / 4/0 AWG" a 2 in wireway (round 6)
@pytest.mark.parametrize("prompt,key", [
    ("cable tray width 24 / 3/4 in rail flange", "width_in"),
    ("junction box width 4 / 3/4 in knockouts", "width_in"),
    ("conduit length 10 / 3/4 in trade size", "length_ft"),
    ("conduit length 10/3/4", "length_ft"),
    ("lighting control panel depth 6 / 5/8 in", "depth_in"),
    ("strut channel height 1 / 5/8 in", "height_in"),
    ("wireway width 8 / 4/0 AWG", "width_in"),
])
def test_a_number_over_a_fraction_is_never_the_number_over_its_numerator(prompt, key):
    r = AR.resolve_prompt(prompt)
    assert r.provenance[key] != GIVEN, (prompt, r.values[key], r.quoted.get(key))


def test_a_cross_before_a_slash_tail_keeps_its_cross():
    r = AR.resolve_prompt("a 12 x 12 x 6 / 3/4 in junction box")
    assert (r.values["width_in"], r.values["height_in"]) == (12.0, 12.0)
    assert r.provenance["width_in"] == r.provenance["height_in"] == GIVEN


@pytest.mark.parametrize("prompt,key,want", [
    ("lighting control panel width 20 'LCP-1'", "width_in", 20.0),   # main: 240 in
    ('junction box width 12 "JB-4"', "width_in", 12.0),
    ('conduit length 10 "L-2"', "length_ft", 10.0),                  # not 10 INCHES
    ("wireway width 12' long", "width_in", 144.0),                   # a closing mark is still a unit
    ('junction box width 12" deep 4"', "width_in", 12.0),
])
def test_a_quote_is_a_unit_only_when_it_closes_the_number(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN



@pytest.mark.parametrize("prompt,key,want", [
    ("lighting control panel width 20 12 / 24 'LCP-1'", "width_in", 20.0),  # a quote OPENING a tag
    # ... after a real fraction the fraction joins -- but the opening quote
    # is still never feet (it was 245 in)
    ("lighting control panel width 20 5 / 12 'LCP-1'", "width_in", 20 + 5 / 12),
    ("lighting control panel width 20 5/12 \u2018LCP-1\u2019", "width_in", 20 + 5 / 12),
    ("cable tray long 20 12 / 24 in the room", "length_ft", 20.0),         # low-voltage pair
    ("wireway width 12 12 / 24 in the room", "width_in", 12.0),
    ("wireway width 12 24 / 48 in the room", "width_in", 12.0),
    ("cable tray wide 12 9 / 23 in", "width_in", 12.0),                    # a date
    ("cable tray wide 12 1 / 100 in", "width_in", 12.0),                   # three digits
    ("wireway width 12 1 / 2", "width_in", 12.5),                          # unit-less, spaced, listed
    ("cable tray wide 2 1/5\"", "width_in", 2.2),                          # a quote CLOSING the number
    # a proper measuring fraction that ENDS the prompt joins (it fell back to
    # the whole number); an improper or non-measuring one still does not
    ("cable tray wide 2 1/5", "width_in", 2.2),
    ("cable tray wide 2 1 / 5", "width_in", 2.2),
    ("cable tray wide 12 5/12.", "width_in", 12 + 5 / 12),
    ("cable tray wide 12 480/277", "width_in", 12.0),
    ("cable tray wide 12 12/24", "width_in", 12.0),
    # " - " also separates PHRASES: only a fraction is barred after it
    ('wireway width 25 in. - tall of 1/2 - 46 1/8" long', "length_ft", 46.125 / 12),
    ("wireway width 25 in. - tall of 1/2 - 46 1/8\" long", "height_in", 0.5),
])
def test_round_5_rows(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN



# Round 7 (#841): a quote TOUCHING the number is a unit -- feet-inch notation
# and "24\"W" forms (requiring "nothing after it" alone turned 7'0" into
# 7 in and 60"L into 60 ft) -- while a spaced quote before a word is a tag.
@pytest.mark.parametrize("prompt,key,want", [
    ("a lighting control panel height 7'0\"", "height_in", 84.0),
    ("a lighting control panel width 2'6\"", "width_in", 24.0),
    ("a lighting control panel 30\" wide, height 6'0\"", "height_in", 72.0),
    ('a wireway length 60"L', "length_ft", 5.0),
    ('a conduit length 120"L', "length_ft", 10.0),
    ("a cable tray 24\"wide, 4\"deep, 12'long", "length_ft", 12.0),
    ("a cable tray 24\"wide, 4\"deep, 12'long", "width_in", 24.0),
    ('a 6"tall junction box', "height_in", 6.0),
    ("a conduit 3/4\" EMT 10'long", "length_ft", 10.0),
    ("lighting control panel width 20 'LCP-1'", "width_in", 20.0),     # still a tag
    ("conduit length 10 5/11'L", "length_ft", 10 + 5 / 11),            # a touching quote after a fraction
])
def test_a_quote_touching_the_number_is_its_unit(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


# ... and a conductor count before a wire size ("3-4/0 AWG", "3 4/0 AWG") is
# no number at all, as on main -- with only "4/0" blanked, the 3 stood alone
# and took the slot of the value the user gave (round 7)
@pytest.mark.parametrize("prompt,key,want", [
    ("a 24 in cable tray 20 ft long 3-4/0 AWG", "length_ft", 20.0),
    ("a 12 in wide wireway 10 ft long 4-1/0 AWG feeders", "length_ft", 10.0),
    ("a 2 in conduit 10 ft long 3-3/0 AWG", "length_ft", 10.0),
    ("a cable tray 24 in wide 3-4/0 AWG", "width_in", 24.0),
    ("a lighting control panel 20 in wide 4-2/0 AWG", "width_in", 20.0),
    ("a cable tray 24 in wide 3 4/0 AWG", "width_in", 24.0),
    ("conduit trade size 2 4 / 0 conductors", "diameter_in", 2.0),      # spaced: the 2 stands
    ("a cable tray 20 ft long 3-5/11 each", "length_ft", 20.0),        # any rejected hyphen token
])
def test_a_conductor_count_is_never_a_dimension(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


# Round 8 (#841): the spacing of a mixed number must AGREE.  A tight hyphen
# before a SPACED slash is a list separator -- "levels 2-3 / 12\" wide" read
# as 2 3/12 took the next phrase's 12 (and blanking it on rejection dropped
# that phrase), while "24 - 1 / 2" and "24-1/2" stay mixed numbers.
@pytest.mark.parametrize("prompt,key,want", [
    ('pull box / levels 2-3 / 12" wide', "width_in", 12.0),
    ("junction box / 3-4 / 12 wide", "width_in", 12.0),
    ("emt / rev 2-3 / 12 feet long", "length_ft", 12.0),
    ("cable tray width 24 in / 2-3 / 4 in deep", "depth_in", 4.0),
    ("junction box / grid 4-7 / 12 in wide", "width_in", 12.0),
    ("strut channel / rooms 101-104 / 1 5/8 in tall", "height_in", 1.625),   # not 5/8 alone
    ('lighting control panel / rooms 101-104 / 24" wide / 6" deep', "width_in", 24.0),
    ("wireway / 480-277 / 6 in wide", "width_in", 6.0),
    ("cable tray 12-18 / 24 in wide", "width_in", 24.0),
    ("junction box grid 4-7 / 4 in wide", "width_in", 4.0),    # 7/4 improper: a list, no other slash
    ("cable tray 24 - 1 / 2 in wide", "width_in", 24.5),       # agreeing spacings join
    ("cable tray 24-1/2 in wide", "width_in", 24.5),
    ("cable tray 24 -1 / 2 in wide", "width_in", 24.5),
    ("cable tray 24- 1 / 2 in wide", "width_in", 24.5),
])
def test_a_tight_hyphen_before_a_spaced_slash_is_a_list(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN



# Round 9 (#841): a tight hyphen before a spaced slash is ALWAYS a list --
# round 8 kept "a 2-1 / 2 in conduit" as 2 1/2 when it was a lone inch
# fraction, and lists after any of , ; | - // still read "levels 2-3 / 8 in
# wide" as 2 3/8.  The one spacing given up is pinned as a known limit.
@pytest.mark.xfail(strict=True, reason="tight hyphen + spaced slash is read as a list (#841 round 9)")
@pytest.mark.parametrize("prompt", ["a 2-1 /2 in conduit", "a 2-1 / 2 in conduit"])
def test_a_tight_hyphen_spaced_slash_mixed_number_is_not_read(prompt):
    r = AR.resolve_prompt(prompt)
    assert r.values["diameter_in"] == pytest.approx(2.5) and r.provenance["diameter_in"] == GIVEN


@pytest.mark.parametrize("prompt,key,want", [
    ("pull box/levels 2-3 / 8 in wide", "width_in", 8.0),
    ("pull box // levels 2-3 / 8 in wide", "width_in", 8.0),
    ("pull box | levels 2-3 / 8 in wide", "width_in", 8.0),
    ("pull box - levels 2-3 / 8 in wide", "width_in", 8.0),
    ("pull box; levels 2-3 / 4 in deep", "depth_in", 4.0),
    ("cable tray, levels 2-3 / 4 in deep", "depth_in", 4.0),
    ('wireway, rev 2-3 / 16" wide', "width_in", 16.0),
    ("strut channel rev 2-3 / 16 in. wide", "width_in", 16.0),
    # the whole number of a "W - a/b" token is never a fraction's denominator
    ("strut channel, tall = 3 / 4 - 277/480 v", "height_in", 0.75),
    ("junction box, depth 3 / 8 - 4/0 awg", "depth_in", 0.375),
    ("emt trade size 3 / 4 - 12/2 mc", "diameter_in", 0.75),
])
def test_round_9_lists_and_denominators(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


# ... and a blank left by the mask counts as a digit: the orphaned " 5/8" of
# "rooms 101-104/1 5/8 in" is never read alone (main: nominal)
@pytest.mark.parametrize("prompt,key", [
    ("pull box / rooms 101-104/1 5/8 in tall", "height_in"),
    ("rooms 101-104/1 5/8 in tall junction box", "height_in"),
    ("emt/floors 2-4/18 3/4 ft long", "length_ft"),
])
def test_a_fraction_beside_a_blank_is_not_read_alone(prompt, key):
    r = AR.resolve_prompt(prompt)
    assert r.provenance[key] != GIVEN, (prompt, r.values[key], r.quoted.get(key))



# Round 10 (#841): the whole-token mask must not eat the whole number of the
# NEXT mixed number -- "floors 2 - 3 / 24 - 1/2 in wide" blanked the 24 and
# read "1/2" alone; the denominator that opens a number stays readable.
@pytest.mark.parametrize("prompt,key,want", [
    ("cable tray, floors 2 - 3 / 24 - 1/2 in wide", "width_in", 24.5),
    ("a conduit, floors 2 - 3 / 2 - 1/2 in diameter", "diameter_in", 2.5),
    ('cable tray, rooms 101 - 104 / 24 - 1/2" wide', "width_in", 24.5),
    ("cable tray, phases 1 - 2 / 18 - 1/2 in wide", "width_in", 18.5),
    ("strut channel, 12 - 2 / 1 - 1/4 inches slot length", "slot_length_in", 1.25),
    ("emt conduit 2 - 3 / 11 - 5/16 feet long", "length_ft", 11.3125),
    ("need a wireway -- item 7 - 2 / 22 - 5/12 inches wide", "width_in", 22 + 5 / 12),
    ("a conduit, floors 2 - 3 / 2 1/2 in diameter", "diameter_in", 2.5),
    ("pull box // 2 - 3 / 29 1/2 in. sheet thickness", "thickness_in", 29.5),
    ("emt conduit floors 2 - 3 / 23-1/2 feet length", "length_ft", 23.5),
    ("lighting control panel . 12 - 2 / 15-5/12 in width", "width_in", 15 + 5 / 12),
    ('make cable tray - floors 2 - 3 / 1 / 4" rung centres', "rung_spacing_in", 0.25),
    ("strut channel & floors 2 - 3 / 1 / 3 lip", "lip_in", 1 / 3),
])
def test_a_denominator_that_opens_the_next_number_stays_readable(prompt, key, want):
    r = AR.resolve_prompt(prompt)
    assert r.values[key] == pytest.approx(want), (prompt, r.values[key], r.quoted.get(key))
    assert r.provenance[key] == GIVEN


# Round 11 (#841): the round-10 branch blanked from the whole number even with
# no hyphen ("trade size 1 120 / 208 3/4 in conduit" became a 208.75 in
# conduit) and broke a range its denominator opened ("6 - 12 / 18 - 24 in
# wide" read 24 alone).  Every row reads exactly as main: the given set.
@pytest.mark.parametrize("prompt,given", [
    ("conduit trade size 1 120 / 208 3/4 in conduit", {"diameter_in": 1.0}),
    ("conduit diameter 1 277 / 480 1/2 in conduit", {"diameter_in": 1.0}),
    ("lighting control panel width 20 277 / 480 3/4 in conduit", {"width_in": 20.0}),
    ("lighting control panel height 36 120 / 277 3/4 in conduit", {"height_in": 36.0}),
    ("junction box depth 6 12 / 24 3/4 in knockouts", {"depth_in": 6.0}),
    ("cable tray 6 - 12 / 18 - 24 in wide", {}),
    ("cable tray sizes 12 - 18 / 24 - 30 in wide", {}),
    ("cable tray 12 18 / 24 - 30 in wide", {}),
    ("conduit sizes 6 - 12 / 18 - 24 length 5-3 / 16", {}),
    ("wireway width 12 480 / 277 - 6 in tall", {"width_in": 12.0, "height_in": 12.0}),
    # an UNSPACED slash before the range keeps main's reading of the range's end
    ("levels strut channel depth 6  277 /12 - 36 long", {"length_ft": 36.0}),
    ("conduit 0 24 /3 - 10 long deep", {"length_ft": 10.0}),
])
def test_a_denominator_never_frees_a_whole_or_a_range_end(prompt, given):
    r = AR.resolve_prompt(prompt)
    got = {k: v for k, v in r.values.items() if r.provenance.get(k) == GIVEN}
    assert got == pytest.approx(given), (prompt, got, r.quoted)


# Round 12 (#841): round 9's denominator skip ran before the list rule, so a
# tight-hyphen list after a slash read as a mixed number again; the list rule
# freed a number glued to the next slash; and round 10's denominator branch
# freed a slash-glued denominator ("2 120 /208 3/4 in" was 208.75).  Every row
# reads exactly as main: the given set.
@pytest.mark.parametrize("prompt,given", [
    ('cable tray levels 1 / 2-3 / 12" wide', {"width_in": 12.0}),
    ("cable tray floors 2 / 3-4 / 12 in wide", {"width_in": 12.0}),
    ("cable tray 3 / 2-3 / 6 in deep", {"depth_in": 6.0}),
    ("cable tray levels 2-3 /4 / 6 in deep", {"depth_in": 6.0}),
    ("a 1-120 /16 / 8 in junction box", {"width_in": 8.0, "height_in": 8.0}),
    ("wireway #12-120 /208 / 10 ft long", {"length_ft": 10.0}),
    ("a 2-3 /4 in conduit", {}),
    ("a 2 120 /208 3/4 in conduit", {}),
    ("cable tray 24 120 /208 1/2 in deep", {}),
    ("cable tray width 24 120 /208 1/2 in deep", {"width_in": 24.0}),
])
def test_a_list_or_a_glued_slash_never_frees_a_number(prompt, given):
    r = AR.resolve_prompt(prompt)
    got = {k: v for k, v in r.values.items() if r.provenance.get(k) == GIVEN}
    assert got == pytest.approx(given), (prompt, got, r.quoted)

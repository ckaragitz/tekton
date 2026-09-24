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
    ("a 2-1 /2 in conduit", "diameter_in", 2.5),
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
    Measured: main gets 13,500 of 18,000 wrong; this fix 0; none worse."""
    for key, a in AR.ARCHETYPES.items():
        noun = a.title.split(" - ")[0].lower()
        for p in [p for p in a.params if p.aliases and p.unit == "in"]:
            al = p.aliases[0]
            for w, (n, d) in itertools.product((1, 2, 12), ((1, 2), (5, 8), (3, 16))):
                for hy, sl in itertools.product(["-", " - ", "- ", " -", " "], ["/", " / ", " /", "/ "]):
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
    assert total >= 18000, total
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

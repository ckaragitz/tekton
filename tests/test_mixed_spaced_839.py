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

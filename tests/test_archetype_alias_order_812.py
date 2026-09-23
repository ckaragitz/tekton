"""An alias must not steal the NEXT phrase's number (issue #812).

``_alias_patterns`` emits two phrasings per alias: number-first ("24 in wide")
and alias-first ("wide 24 in").  Both carry the same alias length, and the
alias-first one used to sort first.  Its connector is optional and ``_SEP``
allows no comma, so it degenerated to *alias + whatever number comes next*:

    "cable tray 24 in wide 4 in deep 20 ft long"
      width_in  =   4.0  given    <- the user said 24
      depth_in  = 240.0  given    <- the "20 ft long" value, read as depth
      length_ft =  10.0  nominal  <- the user said 20 ft

and the built family had 20-foot-tall side rails.  ``given`` means "you stated
it", so this was a wrong number wearing a trustworthy label.  A comma or "and"
between the phrases hid it, which is why it survived.

These tests drive the whole TABLE rather than one example, and assert the
provenance as well as the value: the defect was never only a wrong number, it
was a wrong number certified as the user's own.
"""
from __future__ import annotations

import os
import tempfile
import json

import pytest

from rvt.famgen import archetypes as AR

GIVEN, NOMINAL = "given", "nominal"

# (prompt, {key: expected value}) -- every listed key must also be GIVEN
TABLE = [
    # the defect: juxtaposed phrases, no separator
    ("cable tray 24 in wide 4 in deep",            {"width_in": 24.0, "depth_in": 4.0}),
    ("cable tray 24 in wide 6 in deep",            {"width_in": 24.0, "depth_in": 6.0}),
    ("cable tray 24 in wide 4 in deep 20 ft long", {"width_in": 24.0, "depth_in": 4.0,
                                                    "length_ft": 20.0}),
    ("cable tray 12 in rung spacing 24 in wide",   {"rung_spacing_in": 12.0, "width_in": 24.0}),
    # separators and order: these always worked and must keep working
    ("cable tray 24 in wide, 4 in deep",           {"width_in": 24.0, "depth_in": 4.0}),
    ("cable tray 24 in wide and 4 in deep",        {"width_in": 24.0, "depth_in": 4.0}),
    ("cable tray 4 in deep 24 in wide",            {"width_in": 24.0, "depth_in": 4.0}),
    # alias-first phrasings: the reason pattern A exists -- the regression risk
    ("cable tray width 24 inches",                 {"width_in": 24.0}),
    ("cable tray depth = 6 in",                    {"depth_in": 6.0}),
    ("cable tray rung spacing of 18 in",           {"rung_spacing_in": 18.0}),
    ("cable tray width 24 in depth 6 in",          {"width_in": 24.0, "depth_in": 6.0}),
    # the same chains with the parameters in the OTHER declaration order --
    # width_in is declared before depth_in, and a fixed order's failures
    # depend on that, so both orders of both styles have to be here
    ("cable tray depth 6 in width 24 in",          {"width_in": 24.0, "depth_in": 6.0}),
    ("cable tray 4 in deep 24 in wide 20 ft long", {"width_in": 24.0, "depth_in": 4.0,
                                                    "length_ft": 20.0}),
    # hyphenated, units, and in front of the noun
    ("a 24-inch-wide cable tray",                  {"width_in": 24.0}),
    ("a cable tray 10 ft long",                    {"length_ft": 10.0}),
    ("a 600 mm cable tray",                        {"width_in": 600 / 25.4}),
    ("a 24x4 cable tray",                          {"width_in": 24.0, "depth_in": 4.0}),
]


@pytest.mark.parametrize("prompt,want", TABLE, ids=[t[0] for t in TABLE])
def test_each_stated_dimension_binds_to_its_own_phrase(prompt, want):
    r = AR.resolve_prompt(prompt)
    assert r is not None, prompt
    got = {k: r.values[k] for k in want}
    assert got == pytest.approx(want, abs=1e-6), f"{prompt!r}: {got} != {want}"
    assert {k: r.provenance[k] for k in want} == {k: GIVEN for k in want}, prompt


@pytest.mark.parametrize("prompt,want", TABLE, ids=[t[0] for t in TABLE])
def test_nothing_is_stamped_given_that_the_prompt_did_not_state(prompt, want):
    """The honesty half: every key NOT in the prompt stays nominal.  The
    defect left keys the user never stated wearing ``given`` values that were
    really some other phrase's number."""
    r = AR.resolve_prompt(prompt)
    stray = {k: r.values[k] for k, v in r.provenance.items()
             if v == GIVEN and k not in want}
    assert not stray, f"{prompt!r}: stamped given but not stated: {stray}"


def test_the_quoted_words_are_the_phrase_that_set_each_value():
    """``quoted`` is what the report shows the user as the source of a given
    value.  Under the defect it quoted 'wide 4 in' as the width's source --
    words the user did write, cited for a meaning they did not have."""
    r = AR.resolve_prompt("cable tray 24 in wide 4 in deep 20 ft long")
    assert r.quoted["width_in"] == "24 in wide"
    assert r.quoted["depth_in"] == "4 in deep"
    assert r.quoted["length_ft"] == "20 ft long"


def test_the_emit_order_is_the_only_difference_between_the_two_readings():
    """The mechanism, pinned directly so a refactor cannot pass the table by
    accident.  For every alias, ``alias_first`` flips which phrasing of the
    pair comes first -- and nothing else: the same patterns, the same ranks."""
    arch = AR.archetype("cable_tray")
    for p in arch.params:
        led = AR._alias_patterns(p, alias_first=True)
        trailed = AR._alias_patterns(p, alias_first=False)
        assert sorted(led) == sorted(trailed), p.key
        for i in range(0, len(led), 2):
            assert [r for _, r, _ in led[i:i + 2]] == [1, 0], (p.key, led[i:i + 2])
            assert [r for _, r, _ in trailed[i:i + 2]] == [0, 1], (p.key, trailed[i:i + 2])


def test_both_chains_need_a_different_order_so_no_fixed_order_passes():
    """Why the resolver binds twice.  In each prompt one number stands
    between two aliases: in the first it belongs to the phrase on its RIGHT,
    in the second to the phrase on its LEFT.  Alias-first-only reads the
    first as a 4 in tray; number-first-only reads the second as a 6 in tray,
    because width_in is declared before depth_in and its number-first
    pattern takes "6 in width".  The witness has to be the param-order-
    REVERSED chain: "width 24 in depth 6 in" resolves correctly under both
    fixed orders and proves nothing -- citing it was a mistake during #812."""
    number_led = AR.resolve_prompt("cable tray 24 in wide 4 in deep")
    alias_led = AR.resolve_prompt("cable tray depth 6 in width 24 in")
    assert (number_led.values["width_in"], number_led.values["depth_in"]) == (24.0, 4.0)
    assert (alias_led.values["width_in"], alias_led.values["depth_in"]) == (24.0, 6.0)
    assert number_led.quoted["width_in"] == "24 in wide"
    assert alias_led.quoted["width_in"] == "width 24 in"
    assert alias_led.quoted["depth_in"] == "depth 6 in"


def test_the_built_family_has_the_stated_geometry():
    """End to end through the product route, not just the resolver: the
    delivered .rfa's solids carry 24 in rungs and 4 in rails, not the 4 in
    rungs and 20-foot rails the defect built."""
    import subprocess, sys
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = tempfile.mkdtemp(prefix="t812_")
    proc = subprocess.run(
        [sys.executable, os.path.join(root, "tools", "route.py"), "run",
         "--prompt", "cable tray 24 in wide 4 in deep 20 ft long",
         "--output", "rfa", "--out", out, "--json"],
        capture_output=True, text=True, timeout=300, cwd=root)
    res = json.loads(proc.stdout)
    assert res["ok"], res.get("status")
    report = json.load(open(res["files"]["rfa_report"], encoding="utf-8"))
    forms = report["family"]["forms"]
    tallest = max(f.get("height_ft") or 0 for f in forms)
    assert tallest < 1.0, f"a form is {tallest} ft tall -- the 20-foot rail is back"
    rung_spans = {round(f["depth_ft"], 4) for f in forms
                  if round(f.get("width_ft") or 0, 4) < 0.5 and (f.get("depth_ft") or 0) > 0.5}
    assert rung_spans == {2.0}, f"rung spans {rung_spans} ft; a 24 in tray has 2.0 ft rungs"
    assert "Cable_Tray_-_Ladder_24_in_20_ft" in os.path.basename(res["files"]["rfa"])


@pytest.mark.xfail(strict=True, reason="known gap, split out of #812: W x D after the "
                                       "product noun is not read -- see the follow-up issue")
@pytest.mark.parametrize("prompt", ["cable tray 24 x 4 in", "cable tray 600x100 mm",
                                    "cable tray 24in by 4in"])
def test_known_gap_cross_dimension_after_the_noun(prompt):
    """Recorded, not hidden.  These resolve to an HONEST nominal 12 in tray
    (provenance nominal, "0 dimension(s) from the prompt" in the status), so
    the severity is lower than #812's false ``given`` -- but the user still
    gets a size they did not ask for.  strict=True: when someone fixes it,
    this starts passing and the xfail must be removed."""
    r = AR.resolve_prompt(prompt)
    assert r.provenance["width_in"] == GIVEN

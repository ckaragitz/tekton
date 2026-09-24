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
    # a dimension stated TWICE, where its alias contains a shorter alias of
    # another parameter ('width' in 'rung width', 'length' in 'slot length').
    # Round 1 of #828 stamped the restated value on the short one too: a
    # 1 in tray width, a 2 in long strut -- both 'given'.
    ("cable tray 1 in rung width, rung width 1 in", {"rung_width_in": 1.0}),
    ("cable tray 1 in rung width rung width 1 in",  {"rung_width_in": 1.0}),
    ("strut channel 2 in slot length, slot length 2 in", {"slot_length_in": 2.0}),
    ("cable tray 2 in rail flange, rail flange 2 in", {"rail_flange_in": 2.0}),
    # a restatement around another phrase: 2-2 on bindings under both
    # orders, and only the number-first reading agrees with the repeat
    ("cable tray 7 in wide 13 in loading depth 7 in wide", {"width_in": 7.0, "depth_in": 13.0}),
    ("cable tray wide 7 in 13 in loading depth 7 in wide", {"width_in": 7.0, "depth_in": 13.0}),
    # a label-first chain then a bare adjective: a full tie, which keeps
    # main's alias-first reading.  Round 2 broke the tie number-first and read
    # these as height 8 / depth 6 -- the #812 defect from the other side
    ("junction box width 8 in height 6 in deep",   {"width_in": 8.0, "height_in": 6.0}),
    ("lighting control panel width 20 in height 30 in deep",
                                                   {"width_in": 20.0, "height_in": 30.0}),
    ("wireway width 8 in height 6 in long",        {"width_in": 8.0, "height_in": 6.0}),
    # a restatement just before the noun: the winner's intact phrases are
    # claimed, or the noun rules re-read "4 in junction box" as the width
    ("a 4 in depth, depth 4 in junction box",      {"depth_in": 4.0}),
    ("a 9 in rung spacing, rung spacing 9 in cable tray", {"rung_spacing_in": 9.0}),
    ("a 2 in lip, lip 2 in strut channel",         {"lip_in": 2.0}),
    ("a 0.06 in thickness, thickness 0.06 in wireway", {"thickness_in": 0.06}),
    # a cross-dimension in front of the noun, with a restated phrase before
    # it.  Round 3 claimed "thickness 12" out of "thickness 12 x 6 in" as an
    # intact restatement, which locked the cross out: the noun rule then read
    # the LAST number as the width
    ("a 1/8 in sheet thickness, 1/8 in thickness 12 x 6 in wireway",
                                                   {"thickness_in": 0.125, "width_in": 12.0,
                                                    "height_in": 6.0}),
    ("a 0.06 in sheet thickness 0.06 in thickness 8 x 8 x 4 in junction box",
                                                   {"thickness_in": 0.06, "width_in": 8.0,
                                                    "height_in": 8.0, "depth_in": 4.0}),
    ("a 13-in-long 13-in-long 11 x 19in wireway",  {"length_ft": 13 / 12, "width_in": 11.0,
                                                    "height_in": 19.0}),
    ("a 22 thickness 14 x 19 x 9 in lighting control panel 22 sheet thickness",
                                                   {"thickness_in": 22.0, "width_in": 14.0,
                                                    "height_in": 19.0, "depth_in": 9.0}),
    # ... and the 'x' shapes that are NOT a cross: a count, a separator
    # between complete phrases, W x D spelled out
    ("a 3 x 10 ft long cable tray",                {"length_ft": 10.0}),
    ("cable tray 24 in wide, 2 x 10 ft long",      {"width_in": 24.0, "length_ft": 10.0}),
    ("strut channel thickness = 0.25 inches x 9 feet long",
                                                   {"thickness_in": 0.25, "length_ft": 9.0}),
    ("cable tray 12 in wide x 4 in deep x 10 ft long",
                                                   {"width_in": 12.0, "depth_in": 4.0,
                                                    "length_ft": 10.0}),
    # round 4: a cross labelled by a cross-dimension alias keeps main's
    # reading -- the alias labels the first number ("width 20 x 30 in" is
    # width 20), and a number before the alias belongs to whatever phrase it
    # is in ("depth 6 in width 20 x 30 in": 6 is the depth, not the width)
    ("lighting control panel depth 6 in width 20 x 30 in", {"width_in": 20.0, "depth_in": 6.0}),
    ("Create A Lighting Relay Panel Depth 18 Inches Width 13 X 16 In",
                                                   {"width_in": 13.0, "depth_in": 18.0}),
    ("junction box depth 4 in width 8 x 6",        {"width_in": 8.0, "height_in": 8.0,
                                                    "depth_in": 4.0}),
    ("a wire way long 12' width 12 x 5",           {"width_in": 12.0, "height_in": 12.0,
                                                    "length_ft": 12.0}),
    ("strut channel section width 13 x 27 in tall", {"width_in": 13.0, "height_in": 27.0}),
    ("junction box width 8 x 6 in tall",           {"width_in": 8.0, "height_in": 6.0}),
    ("deep 89mm width 22 x 24 lighting relay panel", {"width_in": 22.0, "depth_in": 89 / 25.4}),
    ("5-in-thickness 23x24 in junction box",       {"thickness_in": 5.0, "width_in": 23.0,
                                                    "height_in": 24.0}),      # main: thickness 23
    # opens_cross's three limits, each pinned: an 'x' that does not open a
    # cross into the noun ("1-1/8 x 9/16" is a slot size), a phrase whose
    # unit completes it, and a number-first phrase before an 'x'
    ("strut channel slot length 1-1/8 x 9/16 in",  {"slot_length_in": 1.125}),
    ("cable tray rung spacing 9 x 2 in, 10 ft long", {"rung_spacing_in": 9.0, "length_ft": 10.0}),
    ("thickness 1/8 in x 12 x 6 in wireway",       {"thickness_in": 0.125, "width_in": 12.0,
                                                    "height_in": 6.0}),
    ("a 2 lip x 12 x 6 in strut channel",          {"lip_in": 2.0, "width_in": 12.0,
                                                    "height_in": 6.0}),
    # round 5: a cross in FEET is a run length, never a section; and an
    # archetype with no cross rule (conduit) never drops the alias
    ("ladder tray rung spacing 9 x 12 ft ladder tray", {"rung_spacing_in": 9.0, "length_ft": 12.0}),
    ("cable tray rail thickness 0.105 x 20 ft cable tray",
                                                   {"rail_thickness_in": 0.105, "length_ft": 20.0}),
    ("strut channel, lip 1/2 x 10 ft strut",       {"lip_in": 0.5, "length_ft": 10.0}),
    ("sheet thickness 0.06 x 5 ft wireway",        {"thickness_in": 0.06, "length_ft": 5.0}),
    ("EMT, trade size 3/4 x 10' EMT",              {"diameter_in": 0.75, "length_ft": 10.0}),
    ("create a raceway diameter 1 x 10 raceway",   {"diameter_in": 1.0}),
    ("the trade size 4 x 11' emt long is 3 foot",  {"diameter_in": 4.0, "length_ft": 3.0}),
    # ... and only while the cross rule is still open: once a cross
    # dimension is given it will not read the cross, so dropping the alias
    # would only lose the stated lip
    ("strut channel section height 2 in, lip 0.5 x 3 in strut channel",
                                                   {"height_in": 2.0, "width_in": 2.0, "lip_in": 0.5}),
    ("junction box sheet thickness 1/8, 12 x 12 in junction box",
                                                   {"thickness_in": 0.125, "width_in": 12.0,
                                                    "height_in": 12.0}),
    ("a 1/8 in sheet thickness, 1/8 in thickness 12 × 6 in wireway",
                                                   {"thickness_in": 0.125, "width_in": 12.0,
                                                    "height_in": 6.0}),       # the '×' sign
    # a unitless NUMBER-FIRST phrase before an 'x' is a phrase, not a cross
    ("a 24 wide x 4 deep cable tray",              {"width_in": 24.0, "depth_in": 4.0}),
    ("cable tray 12 long x 4 in rung spacing",     {"length_ft": 12.0, "rung_spacing_in": 4.0}),
    # intact phrases may not overlap each other: counted twice, a reading
    # that cut the restatements apart outscored the right one
    ('wireway 1 inch wide 2 inch sheet thickness 1 inch width 3" height height is 3"',
                                                   {"width_in": 1.0, "thickness_in": 2.0,
                                                    "height_in": 3.0}),
    ('strut channel 1.75" tall 1.75 " section height 190 mm lip 10 in gauge material '
     'gauge material is 10 in',                    {"height_in": 1.75, "width_in": 1.75,
                                                    "lip_in": 190 / 25.4, "thickness_in": 10.0}),
    # hyphenated, units, and in front of the noun
    ("a 24-inch-wide cable tray",                  {"width_in": 24.0}),
    ("a cable tray 10 ft long",                    {"length_ft": 10.0}),
    ("a 600 mm cable tray",                        {"width_in": 600 / 25.4}),
    ("a 24x4 cable tray",                          {"width_in": 24.0, "depth_in": 4.0}),
    # round 6: a cross dimension's own alias restated elsewhere, right before
    # an "N x N" cross, is not a phrase left whole -- "deep 20" claimed the
    # cross's first number and the noun rule read its last as the width
    ("6 in deep 20 x 30 in lighting control panel, depth: 6 in",
                                                   {"width_in": 20.0, "height_in": 30.0, "depth_in": 6.0}),
    ("150 mm deep 600 x 900 mm lighting control panel, depth 150 mm",
                                                   {"width_in": 600 / 25.4, "height_in": 900 / 25.4,
                                                    "depth_in": 150 / 25.4}),
    ("depth 4 in, 4 in deep 12 x 24 in junction box",
                                                   {"width_in": 12.0, "height_in": 24.0, "depth_in": 4.0}),
    ("6 in deep 20x30 lighting control panel, depth 6 in",
                                                   {"width_in": 20.0, "height_in": 30.0, "depth_in": 6.0}),
    # ... only while the cross is still open: with depth GIVEN, a junction
    # box's width and height are what the cross fills (cross_dims[:2])
    ("junction box, depth 4 in, sheet thickness 12 x 12 in junction box",
                                                   {"width_in": 12.0, "height_in": 12.0, "depth_in": 4.0}),
    # ... and the tail holds one number fewer than the cross dimensions: a
    # wireway's "length 24 X 42 x 42in" already has its whole cross
    ("length 24 X 42 × 42in wireway",              {"length_ft": 24.0, "width_in": 42.0, "height_in": 42.0}),
    # a unit-less number after a rating or count word is not a dimension,
    # even in front of a (doubled) label -- "nema 1 width" is NEMA 1
    ("junction box, nema 1 width 6 in wide",       {"width_in": 6.0, "height_in": 6.0}),
    ("nema 12 height 6 in tall junction box",      {"height_in": 6.0}),
    ("junction box type 1 width 6 in wide",        {"width_in": 6.0, "height_in": 6.0}),
    ("junction box qty 2 width 6 in wide",         {"width_in": 6.0, "height_in": 6.0}),
    ("junction box class 20 width 6 in wide",      {"width_in": 6.0, "height_in": 6.0}),
    ("junction box (2) width 6 in wide",           {"width_in": 6.0, "height_in": 6.0}),
    ("nema 12 tall junction box",                  {}),        # a rating, not a height (main: 12)
    # a designator only when the parameter is stated again with a unit ...
    ("size 1 wide 6 in wide junction box",         {"width_in": 6.0, "height_in": 6.0}),
    ("junction box #2 width 6 in wide",            {"width_in": 6.0, "height_in": 6.0}),
    # ... alone, "size 12 wide" is still read as main reads it
    ("a size 12 wide junction box",                {"width_in": 12.0, "height_in": 12.0}),
    ("size 1 wide 6 wide junction box",            {"width_in": 6.0, "height_in": 6.0}),
    # WITH a unit the number is a dimension, whatever word precedes it
    ("pole 6 in wide junction box",                {"width_in": 6.0, "height_in": 6.0}),
    ("cable tray, group 24 in wide",               {"width_in": 24.0}),       # a listed rating word
    ("wireway, phase 12 thickness 6 in thickness", {"thickness_in": 6.0}),   # phase as a designator
    ("junction box, pole 2 width 6 in wide",       {"width_in": 6.0, "height_in": 6.0}),
    # round 7: "phase" and "pole" come AFTER their count -- the number that
    # follows them is a size
    ("a 3 phase 12 tall 8 in wide junction box",   {"width_in": 8.0, "height_in": 12.0}),
    ("wireway, three phase 8 tall wide 33 in",     {"width_in": 33.0, "height_in": 8.0}),
    ("a 2 pole 30 tall 20 wide lighting control panel", {"width_in": 20.0, "height_in": 30.0}),
    ("a 3 phase 24 wide lighting control panel",   {"width_in": 24.0}),
    ("a single-phase 24 wide lighting control panel", {"width_in": 24.0}),
    ("a 3 phase 22 dia conduit",                   {"diameter_in": 22.0}),
    ("a single phase 20 wide 30 tall 6 deep lighting control panel",
                                                   {"width_in": 20.0, "height_in": 30.0, "depth_in": 6.0}),
    # ... and a restatement is this parameter's own phrase, not a longer alias
    ("size 24 wide cable tray, rung width 1 in",   {"width_in": 24.0, "rung_width_in": 1.0}),
    ("tag 20 long strut channel, slot length 2 in", {"length_ft": 20.0, "slot_length_in": 2.0}),
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


@pytest.mark.xfail(strict=True, reason="known ambiguity, #832: '6 in wide' and 'wide 4 x 4' "
                                       "share one alias; main's label reading is kept")
def test_known_ambiguity_a_number_first_phrase_sharing_its_alias_with_a_cross():
    """Recorded, not hidden.  Round 3 read "junction box 6 in wide 4 x 4 in"
    as 6 in wide; round 4 returns to main's reading, width 4 ("wide" labels
    the cross), because the same shape with an alias in front -- "depth 6 in
    width 20 x 30 in" -- must read the label way, and nothing local tells the
    two apart.  strict=True: a rule that separates them makes this pass."""
    r = AR.resolve_prompt("junction box 6 in wide 4 x 4 in")
    assert r.values["width_in"] == 6.0


@pytest.mark.xfail(strict=True, reason="known gap, split out of #812 as #832: a full tie "
                                       "between the two readings keeps alias-first")
def test_known_gap_bare_adjective_before_a_number_first_chain():
    """Recorded, not hidden: "long" is an adjective here, and alias-first
    reads "long 24 in" as a 2 ft length and "wide 4 in" as the width -- both
    ``given``, as on main.  Breaking the tie the other way broke the mirror
    shape ("width 8 in height 6 in deep"), so the fix is #832's, measured
    against main on both.  strict=True: a fix makes this pass."""
    r = AR.resolve_prompt("a long 24 in wide 4 in deep cable tray")
    assert (r.values["width_in"], r.values["depth_in"]) == (24.0, 4.0)
    assert r.provenance["length_ft"] == NOMINAL


@pytest.mark.xfail(strict=True, reason="known gap, split out of #812 as #827: W x D after "
                                       "the product noun is not read")
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


# ---------------------------------------------------------------------------
# the property, over every archetype -- not a hand-picked table
# ---------------------------------------------------------------------------

def _stray(arch, r, want):
    """Keys stamped ``given`` that the prompt did not state -- except a
    follower (``Param.follows``) carrying its stated leader's value, which is
    ``given`` by design (a square wireway asked for at 12 in is 12 in tall)."""
    return {k: r.values[k] for k, v in r.provenance.items()
            if v == GIVEN and k not in want
            and not (arch.param(k).follows in want
                     and abs(r.values[k] - want[arch.param(k).follows]) < 1e-6)}


def _place(noun, parts, sep, where):
    """The prompt with the product noun FIRST ("cable tray 7 in wide ..."),
    LAST ("a 7 in wide ... cable tray") or in the MIDDLE.  Round 2's review
    found every regression it had in the last two: the noun rules read a
    number standing next to the noun, so a sweep that always puts the noun
    first cannot see them."""
    if where == "first":
        return noun + " " + sep.join(parts)
    if where == "last":
        return "a " + sep.join(parts) + " " + noun
    k = max(1, len(parts) // 2)
    return "a " + sep.join(parts[:k]) + " " + noun + " " + sep.join(parts[k:])


_WHERE = ("first", "last", "middle")


def _chains():
    """Every two- and three-phrase chain over every archetype's dimensional
    aliases, in both phrasings ("7 in wide" / "wide 7 in"), in every order,
    with NO separator between phrases, and with every alias of every
    parameter used (rotated, so a chain's phrases do not all take their
    first alias together).  Each prompt carries its own oracle: number i
    belongs to the phrase it is written in."""
    import itertools
    for key, a in AR.ARCHETYPES.items():
        noun = a.title.split(" - ")[0].lower()
        ps = [p for p in a.params if p.aliases and p.unit in ("in", "ft")]
        for k in (2, 3):
            for combo in itertools.permutations(ps, k):
                for j in range(max(len(p.aliases) for p in combo)):
                    for styles in itertools.product((0, 1), repeat=k):
                        parts, want = [], {}
                        for i, (p, st) in enumerate(zip(combo, styles)):
                            n = (7, 13, 19)[i]
                            al = p.aliases[(j + i) % len(p.aliases)]
                            parts.append(f"{n} {p.unit} {al}" if st == 0 else f"{al} {n} {p.unit}")
                            want[p.key] = float(n)
                        yield key, noun + " " + " ".join(parts), want


def _restatements(where="first"):
    """One dimension stated twice with another phrase before, between or
    after (PPQ / PQP / PQQ / QPP), every alias of the restated parameter,
    both phrasings, with and without a comma: 18,496 prompts.  The class the
    round-1 review of #828 found.  Measured on this generator: main gets
    2,152 wrong, #828's round-1 head 2,401 (it fixed some and broke others),
    this head 0.  With ``where="cycle"`` (noun first, last or middle in
    turn): main 2,466, round 1 2,773, round 2 2,010, this head 0."""
    import itertools
    i = 0
    for key, a in AR.ARCHETYPES.items():
        noun = a.title.split(" - ")[0].lower()
        ps = [p for p in a.params if p.aliases and p.unit in ("in", "ft")]
        ph = lambda p, al, n, st: f"{n} {p.unit} {al}" if st == 0 else f"{al} {n} {p.unit}"
        for p, q in itertools.permutations(ps, 2):
            for ap in p.aliases:
                aq = q.aliases[len(ap) % len(q.aliases)]
                for order in ("PPQ", "PQP", "PQQ", "QPP"):
                    for sts in itertools.product((0, 1), repeat=3):
                        for sep in (" ", ", "):
                            parts = [ph(p, ap, 7, st) if c == "P" else ph(q, aq, 13, st)
                                     for c, st in zip(order, sts)]
                            w, i = (where if where != "cycle" else _WHERE[i % 3]), i + 1
                            yield key, _place(noun, parts, sep, w), {p.key: 7.0, q.key: 13.0}


def _sweep(gen):
    import collections
    per, fails = collections.Counter(), []
    for key, prompt, want in gen:
        per[key] += 1
        arch = AR.archetype(key)
        r = AR.resolve_prompt(prompt, product=key)
        bad = {k: (r.values[k], r.provenance[k]) for k, v in want.items()
               if abs(r.values[k] - v) > 1e-6 or r.provenance[k] != GIVEN}
        stray = _stray(arch, r, want)
        if bad or stray:
            fails.append((prompt, bad, stray))
    return per, fails


def _assert_coverage(per, floor):
    """A per-archetype floor, not one total: losing a whole archetype (its
    aliases filtered out by a refactor) must fail, not hide in a big sum."""
    missing = {k for k in AR.ARCHETYPES if per[k] < floor.get(k, 1)}
    assert not missing, f"sweep lost coverage: {dict(per)} (floors {floor})"


def test_every_stated_number_binds_to_its_own_phrase_across_every_archetype():
    """On main this fails 3,564 of these 16,344 prompts, in every archetype
    (1,201 of 5,488 when only each parameter's first alias was used) -- e.g.
    "cable tray 7 in rung spacing 13 ft long" gave a 13-FOOT rung spacing
    stamped given.  Measured, not assumed.  Checks the stray half too:
    nothing the chain did not state may come back ``given``."""
    per, fails = _sweep(_chains())
    _assert_coverage(per, {"cable_tray": 2000, "strut_channel": 1000, "wireway": 100,
                           "junction_box": 100, "lighting_control_panel": 100,
                           "conduit": 20})
    assert not fails, f"{len(fails)}/{sum(per.values())} chains mis-bound; first: {fails[:3]}"


@pytest.mark.parametrize("where", ["first", "cycle"])
def test_a_restated_dimension_binds_once_and_nothing_else_follows_it(where):
    """``cycle`` moves the noun last or into the middle as well -- the shape
    round 2's regressions all had (see _place)."""
    per, fails = _sweep(_restatements(where))
    _assert_coverage(per, {"cable_tray": 5000, "strut_channel": 3000, "wireway": 500,
                           "junction_box": 500, "lighting_control_panel": 500,
                           "conduit": 50})
    assert not fails, f"{len(fails)}/{sum(per.values())} restatements mis-bound; first: {fails[:3]}"


def _contradictions(where="first"):
    """One dimension stated twice with DIFFERENT values (7 then 9) around
    another phrase (PPQ / PQP / QPP), every alias, both phrasings, with and
    without a comma: 13,872 prompts.  Which of 7 or 9 wins is not this
    test's business -- the user contradicted themselves -- but the OTHER
    dimension must still be the 13 they stated for it.  Measured: main gets
    1,478 wrong; a tie-break that only counted restatements carrying the
    SAME value got 1,156 wrong ("wide 7 in loading depth 13 in wide 9 in"
    became a 13 in wide, 7 in deep tray); this head 0.  With the noun
    cycled first / last / middle: main 1,543, round 1 1,611, round 2 1,692,
    this head 0."""
    import itertools
    i = 0
    for key, a in AR.ARCHETYPES.items():
        noun = a.title.split(" - ")[0].lower()
        ps = [p for p in a.params if p.aliases and p.unit in ("in", "ft")]
        ph = lambda p, al, n, st: f"{n} {p.unit} {al}" if st == 0 else f"{al} {n} {p.unit}"
        for p, q in itertools.permutations(ps, 2):
            for ap in p.aliases:
                for order in ("PPQ", "PQP", "QPP"):
                    for sts in itertools.product((0, 1), repeat=3):
                        for sep in (" ", ", "):
                            pv, parts = iter((7, 9)), []
                            for c, st in zip(order, sts):
                                parts.append(ph(p, ap, next(pv), st) if c == "P"
                                             else ph(q, q.aliases[0], 13, st))
                            w, i = (where if where != "cycle" else _WHERE[i % 3]), i + 1
                            yield key, _place(noun, parts, sep, w), p.key, q.key


@pytest.mark.parametrize("where", ["first", "cycle"])
def test_a_contradicted_dimension_never_takes_the_other_phrases_number(where):
    import collections
    per, fails = collections.Counter(), []
    for key, prompt, pk, qk in _contradictions(where):
        per[key] += 1
        arch = AR.archetype(key)
        r = AR.resolve_prompt(prompt, product=key)
        p_ok = r.provenance[pk] == GIVEN and min(abs(r.values[pk] - v) for v in (7, 9)) < 1e-6
        q_ok = r.provenance[qk] == GIVEN and abs(r.values[qk] - 13) < 1e-6
        stray = {k for k in _stray(arch, r, {pk: r.values[pk], qk: 13.0})}
        if not (p_ok and q_ok) or stray:
            fails.append((prompt, {pk: r.values[pk], qk: r.values[qk]}, stray))
    _assert_coverage(per, {"cable_tray": 5000, "strut_channel": 3000, "wireway": 500,
                           "junction_box": 500, "lighting_control_panel": 500,
                           "conduit": 50})
    assert not fails, f"{len(fails)}/{sum(per.values())} contradictions mis-bound; first: {fails[:3]}"


def test_a_contradiction_leaves_the_other_dimension_alone():
    r = AR.resolve_prompt("cable tray wide 7 in loading depth 13 in wide 9 in")
    assert (r.values["depth_in"], r.provenance["depth_in"]) == (13.0, GIVEN)
    assert r.quoted["depth_in"] == "loading depth 13 in"
    assert min(abs(r.values["width_in"] - v) for v in (7.0, 9.0)) < 1e-6
    assert r.provenance["width_in"] == GIVEN


def _crossed():
    """A chain of non-cross parameters, one of them restated, then a
    "W x H [x D] in" cross right before the noun -- the shape round 3's review
    found: a cross never met a restatement in any earlier sweep.  Phrases are
    number-first ("7 in lip") or alias-first ("lip 7 in") with their unit,
    because "1/8 in thickness 12 x 6 in" is how the defect reads in a real
    prompt ("thickness 12" is the alias of the restated phrase running into
    the cross).  Measured: main gets 1,170 of 2,684 wrong, round 3's head
    (403988b) 1,342, this head 0."""
    import itertools
    for key, a in AR.ARCHETYPES.items():
        cross = [k for k in ("width_in", "height_in", "depth_in")
                 if any(p.key == k for p in a.params)]
        if len(cross) < 2:
            continue
        noun = a.title.split(" - ")[0].lower()
        ps = [p for p in a.params if p.aliases and p.unit in ("in", "ft") and p.key not in cross]
        dims = (12, 6, 4)[:len(cross)]
        cx = " x ".join(str(d) for d in dims) + " in"
        pairs = list(itertools.permutations(ps, 2)) or [(p, None) for p in ps]
        for p, q in pairs:
            orders = ("PPQ", "PQP", "QPP", "PQ") if q else ("PP", "P")
            for al_p in p.aliases:
                for order in orders:
                    for sts in itertools.product((0, 1), repeat=len(order)):
                        parts = []
                        for c, st in zip(order, sts):
                            r, n, al = (p, 7, al_p) if c == "P" else (q, 9, q.aliases[-1])
                            parts.append((f"{n} {r.unit} {al}", f"{al} {n} {r.unit}")[st])
                        want = {p.key: 7.0}
                        if q:
                            want[q.key] = 9.0
                        want.update({k: float(d) for k, d in zip(cross, dims)})
                        yield key, "a " + " ".join(parts) + f" {cx} {noun}", want


def test_a_cross_dimension_keeps_its_numbers_next_to_a_restatement():
    per, fails = _sweep(_crossed())
    _assert_coverage(per, {"cable_tray": 1000, "strut_channel": 1000, "conduit": 0,
                           "wireway": 100, "junction_box": 8,
                           "lighting_control_panel": 8})
    assert not fails, f"{len(fails)}/{sum(per.values())} cross prompts mis-bound; first: {fails[:3]}"

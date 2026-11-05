"""#825: "a pump / generator / elevator / BMS control panel" must never build a panelboard.

Before this, each of those prompts returned a clean ``OK`` and an
``Eaton PRL2X 225 A, 42-space, 480Y/277 V`` panelboard -- a different product carrying a
real manufacturer's model, with nothing in the status line saying so.  That is the silent
substitution S-2026-08-11-c forbids, and worse than a refusal: a refusal leaves the
designer without a file, this handed them a file that looks right and is the wrong
equipment.

MECHANISM (measured, not assumed).  The #692 taxonomy shield marks only the span the
taxonomy MATCHED as taken, so for "a pump control panel" the word ``pump`` was shielded
while the trailing ``control panel`` still fell to the ``panelboard`` clause
(``panel\\s*boards?|(?:electrical\\s+|branch\\s+)?panels?``); ``elevator`` and ``BMS`` are
not taxonomy rows at all, so nothing was shielded.  "a fire alarm control panel" and
"a protective relay panel" refused only because a taxonomy row happened to claim the whole
phrase -- the same shield by accident, which is why #821 kept the ``relay panel`` alias
until this landed.

The fix is two coordinated halves, and both are tested below: the panelboard clause no
longer reads a bare ``panel`` preceded by ``control`` (so no wrong file), and a
``_CONTEXT_PATTERNS`` row reports the phrase (so the refusal SAYS what it saw instead of
dropping the words silently).

The control matters as much as the fix: a blanket "panel never builds" would also be
wrong, so the legitimate panelboard prompts are pinned here too.
"""
from __future__ import annotations

import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import taxonomy as T            # noqa: E402
from rvt.frontdoor import prompt_intent as PI   # noqa: E402


def _outcome(prompt: str):
    """``(built_kinds, refusal_text)`` -- exactly one of them is truthy."""
    try:
        return [i.kind for i in PI.parse_prompt(prompt).buildable_items], None
    except PI.PromptError as e:
        return [], str(e)


#: the issue's own table, plus the two cases found after filing (a protective relay panel,
#: #825 comment) and three more this module measured (motor / irrigation / VFD)
NEVER_A_PANELBOARD = [
    "a fire alarm control panel", "a pump control panel", "a generator control panel",
    "an elevator control panel", "a BMS control panel", "a protective relay panel",
    "a generator relay panel", "a relay panel", "an LCP",
    "a motor control panel", "an irrigation control panel", "a VFD control panel",
]


@pytest.mark.parametrize("prompt", NEVER_A_PANELBOARD)
def test_no_control_panel_phrase_builds_a_panelboard(prompt):
    """DONE 1 + 3: not one of these yields a panelboard -- the whole point of the issue."""
    built, _ = _outcome(prompt)
    assert not any("panelboard" in k for k in built), (
        f"{prompt!r} built {built}: a panelboard is a DIFFERENT product from what was asked, "
        "and substituting it silently is what #825 was filed for")


@pytest.mark.parametrize("prompt", NEVER_A_PANELBOARD)
def test_each_one_is_refused_by_name_and_says_what_it_recognised(prompt):
    """DONE 1: refused *by name*, stating what was recognised -- never a silent drop.

    An empty build with an empty reason would satisfy the test above while leaving the
    designer no wiser than the wrong file did.
    """
    built, why = _outcome(prompt)
    assert built == [] and why, f"{prompt!r} built {built} instead of refusing"
    assert "recognised" in why.lower(), f"{prompt!r} refusal does not say what it recognised: {why}"


@pytest.mark.parametrize("prompt,expect", [
    ("a pump control panel", "pump"),              # a taxonomy row: named by the taxonomy
    ("a generator control panel", "generator"),
    ("a VFD control panel", "VFD"),
    ("a fire alarm control panel", "fire alarm control panel"),
    ("an elevator control panel", "control panel"),  # NOT a taxonomy row: the new row names it
    ("a BMS control panel", "control panel"),
    ("a motor control panel", "control panel"),
])
def test_the_refusal_names_the_phrase_it_actually_read(prompt, expect):
    """The reason quotes the recognised words, so a designer can see WHY it refused.

    The split is the point: where the taxonomy carries the qualifier it is named; where it
    does not ('elevator', 'BMS'), #825's ``control_panel`` row is the whole report.
    """
    _, why = _outcome(prompt)
    assert expect.lower() in why.lower(), f"{prompt!r}: {expect!r} not in refusal: {why}"


#: THE CONTROL -- a real panelboard ask must still build one.  Without these the fix could
#: pass by refusing every 'panel' prompt, which would break the route's main lane.
@pytest.mark.parametrize("prompt,expect", [
    ("two 225 A panels", ["panelboard", "panelboard"]),
    ("a lighting panel", ["lighting_panelboard"]),
    ("a distribution panel", ["distribution_panelboard"]),
    ("an electrical panel", ["panelboard"]),
    ("a panelboard", ["panelboard"]),
])
def test_a_genuine_panelboard_ask_still_builds_one(prompt, expect):
    built, why = _outcome(prompt)
    assert built == expect, f"{prompt!r} built {built} (refusal: {why}) -- the fix over-reached"


def test_control_is_only_blocked_as_a_qualifier_of_panel():
    """'control' next to 'panel' is blocked; the word alone never suppresses a panelboard."""
    built, _ = _outcome("a 225 A panel for the controls room")
    assert built == ["panelboard"], f"built {built}: 'controls' in other words must not block"


# ---------------------------------------------------------------------------
# DONE 4: does any OTHER generic word fall to a product the same way?
# ---------------------------------------------------------------------------

def test_only_panel_and_outlet_are_claimed_by_a_grammar_clause():
    """DONE 4, as a law rather than a one-off sweep.

    ``taxonomy.AMBIGUOUS_ALONE`` governs the TAXONOMY SCAN only -- a grammar clause in
    ``_KIND_PATTERNS`` runs regardless, which is the whole reason #825 existed.  Of the 13
    ambiguous words, exactly two are claimed by a clause on their own: ``panel`` (#825,
    fixed here) and ``outlet`` (#1065, recorded not fixed).  The other 11 have no builder
    clause to fall to, which is why they all refuse -- so this pair is the COMPLETE
    exposure, not a sample.

    A red here means a new ambiguous word became claimable by a grammar clause: give it a
    guard like ``control\\s`` or add it below with its issue.
    """
    claimed = {w: sorted(k for k, _tag, pat in PI._KIND_PATTERNS if re.search(pat, w, re.I))
               for w in sorted(T.AMBIGUOUS_ALONE)}
    assert {w: ks for w, ks in claimed.items() if ks} == {
        "outlet": ["receptacle_device"], "panel": ["panelboard"]}


@pytest.mark.parametrize("prompt", [
    "a pull box", "a junction box", "an elevator box", "a BMS box",
    "a safety switch", "a transfer switch", "an elevator switch", "a BMS switch",
    "a water meter", "a utility meter", "an elevator meter", "a BMS meter",
])
def test_the_other_generic_words_build_nothing(prompt):
    """DONE 4 measured: box / switch / meter have no builder clause, so they refuse."""
    built, _ = _outcome(prompt)
    assert built == [], f"{prompt!r} built {built}: a third generic word now substitutes"


@pytest.mark.parametrize("prompt", [
    "a medical gas outlet", "a gas outlet", "a compressed air outlet",
    "a TV outlet", "a cable outlet", "an AV outlet", "a fibre outlet",
    "a BMS outlet", "an elevator outlet",
])
def test_the_outlet_gap_is_pinned_until_1065_lands(prompt):
    """A PINNED KNOWN GAP (#1065), not an endorsement.

    These build a generic ``receptacle_device`` -- the #825 shape on the other claimed
    word.  #825 deliberately does not fix it: the receptacle clause is a different product
    surface and needs its own decision about which ``X outlet`` phrases genuinely ARE
    receptacles (#1065 DONE 2).  It is pinned so the behaviour cannot drift unnoticed in
    either direction: when #1065 lands this test goes red and is replaced by that issue's
    own, rather than #825 quietly having covered it.

    Measured distinction from #825: the item carries NO manufacturer model
    (``{'kind': 'receptacle_device', 'tag': 'R-1'}``), where #825 handed over a branded
    Eaton PRL2X -- which is why #1065 is P1 and this was P0.
    """
    built, _ = _outcome(prompt)
    assert built == ["receptacle_device"], (
        f"{prompt!r} built {built}: if #1065 fixed this, delete this test and point at its "
        "module; if something else changed it, that is a regression to explain")

"""#766 -- a taxonomy-recognised kind with a famspec hint builds through its
constructor from a bare prompt."""
import tempfile

import pytest

from rvt.frontdoor import taxonomy_build as TB


def test_the_troffer_prompt_plans_its_constructor():
    ps = TB.plans("a 2x4 recessed troffer light fixture")
    assert len(ps) == 1, ps                    # troffer+luminaire dedupe to one
    p = ps[0]
    assert p["kind"] == "luminaire"
    assert p["kw"]["kind"] == "recessed-troffer"   # famspec rename applied
    assert p["kw"]["size"] == "2x4"
    assert p["mention"] == "troffer"


def test_wattage_and_cct_ride_along():
    p = TB.plans("a 2x2 38W 3500K troffer")[0]
    assert p["kw"]["size"] == "2x2"
    assert p["kw"]["wattage"] == 38.0
    assert p["kw"]["cct"] == 3500.0


def test_an_uncatalogued_size_is_heard_but_not_passed():
    # the catalog resolver is binary and "4x4" would silently deliver the
    # 2x2 member wearing the caller's size -- the steer #591 substitution.
    p = TB.plans("create a 4x4 troffer")[0]
    assert "size" not in p["kw"]
    assert p["notes"] and "NOT a 4x4" in p["notes"][0]


def test_unbuildable_kinds_yield_no_plan():
    # the refusal relay (#692) must keep the floor for these
    assert TB.plans("create a VAV box family") == []


def test_gibberish_yields_no_plan_and_no_crash():
    assert TB.plans("purple monkey dishwasher") == []
    assert TB.plans("") == []
    assert TB.plans(None) == []


def test_describe_is_quotable():
    p = TB.plans("a downlight")[0]
    line = TB.describe(p)
    assert "downlight" in line and "constructor" in line


# ---------------------------------------------------------------------------
# through the route (the user-visible contract)
# ---------------------------------------------------------------------------

def _route(prompt):
    from rvt.frontdoor import router as R
    return R.route({"prompt": prompt}, "rfa", out=tempfile.mkdtemp(), quiet=True)


def test_the_original_failing_prompt_now_delivers():
    r = _route("a 2x4 recessed troffer light fixture")
    assert r.ok is True
    assert "recessed-troffer" in r.status
    assert r.files.get("rfa") or r.files.get("families_dir") or r.files


def test_unsupported_size_delivers_loudly():
    r = _route("create a 4x4 troffer")
    assert r.ok is True
    assert "NOT at the size you named" in r.status
    assert any("NOT a 4x4" in str(c) for c in r.caveats)


def test_the_taxonomy_refusal_relay_is_untouched():
    r = _route("create a VAV box family")
    assert r.ok is False
    assert "VAV terminal unit: Mechanical Equipment; NOT buildable here" in r.status


def test_the_archetype_lane_is_untouched():
    r = _route("create a cable tray family")
    assert r.ok is True
    assert "Cable Tray" in r.status


def test_the_scene_grammar_keeps_priority():
    # a panelboard prompt must still go through the room/scene lane, not
    # become a bare taxonomy build
    r = _route("an electrical room with 2 panels")
    assert r.ok is True

"""A prompt for a strut trapeze builds the whole trapeze (issue #899).

Before this, "a 2 tier slotted trapeze with threaded rod" built ONE 10 ft
strut channel and listed tier / slotted / trapeze / threaded / rod as ignored
words.  These tests pin the lane, the assembly by POSITION (two tiers stacked
at the tier spacing, rods through both, washers and nuts touching the channel
they clamp), and the family parameters a user adjusts -- with their values.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

from rvt.famgen import archetypes as AR
from rvt.famgen import factory as F
from rvt.famgen import taxonomy as TX

IN = 1.0 / 12.0
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_taxonomy_routes_trapeze_to_the_archetype_lane():
    kind = TX.get("strut_trapeze")
    assert "archetype:strut_trapeze" in kind.via
    assert kind.lane == "archetype"
    ok, why = TX.builder_available(kind, strict=True)
    assert ok, why


@pytest.mark.parametrize("prompt, given", [
    ("a 2 tier slotted trapeze with threaded rod", {"tiers": 2.0}),
    ("create a trapeze family", {}),
    ("a 2 tier slotted strut trapeze hanger with 3/8 in threaded rod",
     {"tiers": 2.0, "rod_diameter_in": 0.375}),
    ("3 tier unistrut trapeze 36 in long with 1/2 in threaded rod, 18 in tier spacing",
     {"tiers": 3.0, "strut_length_in": 36.0, "rod_diameter_in": 0.5,
      "tier_spacing_in": 18.0, "rod_spacing_in": 30.0}),
    ("a 4-tier trapeze", {"tiers": 4.0}),
    ("a trapeze with 3 tiers", {"tiers": 3.0}),
    # the #900 review's prompts: a bare rod size, the 1-5/8 trade name, rod spacing
    ("a 2 tier trapeze with 1/2 rod", {"tiers": 2.0, "rod_diameter_in": 0.5}),
    ("a trapeze with 5/8 in rod", {"rod_diameter_in": 0.625}),
    ('a trapeze with 5/8" rod', {"rod_diameter_in": 0.625}),
    ("a 2 tier 1-5/8 strut trapeze", {"tiers": 2.0}),
    ("a 2 tier 1-5/8 in strut trapeze with 3/8 in threaded rod",
     {"tiers": 2.0, "height_in": 1.625, "rod_diameter_in": 0.375}),
    ("a 1-5/8 in wide strut trapeze", {}),
    ("a 13/16 in strut trapeze", {"height_in": 0.8125}),
    ("a 2 tier trapeze with 18 in rod spacing",
     {"tiers": 2.0, "rod_spacing_in": 18.0, "strut_length_in": 24.0}),
    ("a 36 in trapeze with 30 in rod spacing",
     {"strut_length_in": 36.0, "rod_spacing_in": 30.0, "rod_inset_in": 3.0}),
    # round 2 of the #900 review: "slotted" leading the noun, a rod size
    # followed by another number
    ("a 2 tier 1-5/8 in slotted trapeze", {"tiers": 2.0}),
    ("a 1-5/8 in slotted strut trapeze", {"height_in": 1.625}),
    ("a 1-5/8 in slotted trapeze", {}),
    # bare "apart" is not a rod-spacing alias ("tiers 12 in apart" is the tier
    # spacing, review round 3); the stated 1/2 in rod survives
    ("a trapeze with 1/2 in rod 24 in apart", {"rod_diameter_in": 0.5}),
    # bare "centers" is not a spacing alias ("rod centers" would be ambiguous);
    # what matters is the stated 1/2 in rod survives the following number
    ("a trapeze with 1/2 in rod at 18 in centers", {"rod_diameter_in": 0.5}),
    ("a trapeze with 1/2 in rod 18 in on center", {"rod_diameter_in": 0.5}),
    # review round 3: a trapeze LENGTH before "strut" / "channel" / "unistrut"
    # is the strut length; only a channel-sized number names the channel
    ("a 36 in strut trapeze", {"strut_length_in": 36.0, "rod_spacing_in": 30.0}),
    ("a 3 ft strut trapeze", {"strut_length_in": 36.0, "rod_spacing_in": 30.0}),
    ("a 24 in unistrut trapeze", {"strut_length_in": 24.0, "rod_spacing_in": 18.0}),
    ("a 36 in slotted strut trapeze", {"strut_length_in": 36.0, "rod_spacing_in": 30.0}),
    ("a 2 tier 36 in slotted channel trapeze hanger",
     {"tiers": 2.0, "strut_length_in": 36.0, "rod_spacing_in": 30.0}),
    ("a 2 tier trapeze with tiers 12 in apart", {"tiers": 2.0}),
    ("a 2 tier trapeze with tiers 12 in apart and rods 24 in apart", {"tiers": 2.0}),
    ("a 2 tier trapeze with 1/2 in rod 2 ft above", {"tiers": 2.0, "rod_diameter_in": 0.5}),
    ("a 1 tier trapeze", {"tiers": 1.0}),
    ("a 24 in rod spacing 1/2 in rod trapeze, 3 in rod inset",
     {"rod_spacing_in": 24.0, "rod_diameter_in": 0.5, "rod_inset_in": 3.0,
      "strut_length_in": 30.0}),
])
def test_every_way_of_asking_resolves_to_the_trapeze(prompt, given):
    r = AR.resolve_prompt(prompt)
    assert r is not None and r.arch.key == "strut_trapeze", prompt
    stated = {k: r.values[k] for k in r.given() if k not in r.derived}
    derived = {k: r.values[k] for k in r.derived}
    assert {**stated, **derived} == pytest.approx(given), (prompt, stated, derived)
    # strut length = rod spacing + 2 x inset, always -- stated or derived
    v = r.values
    assert v["strut_length_in"] == pytest.approx(v["rod_spacing_in"] + 2 * v["rod_inset_in"])


def test_a_plain_strut_channel_is_still_a_strut_channel():
    r = AR.resolve_prompt("a 10 ft strut channel")
    assert r is not None and r.arch.key == "strut_channel"


def test_a_count_takes_a_bare_whole_number_only():
    p = AR.archetype("strut_trapeze").param("tiers")
    assert AR._convert(2.0, "count", p) == 2.0
    assert AR._convert(2.0, "in", p) is None       # "2 in tiers" is not a count
    assert AR._convert(1.625, "count", p) is None  # "tier 1-5/8 strut" is not 1.6 tiers


@pytest.mark.parametrize("prompt", [
    "a 2 tier 1-5/8 in slotted trapeze", "a 1-5/8 in slotted strut trapeze",
    "a trapeze with 1/2 in rod 24 in apart", "a trapeze with 1/2 in rod at 18 in centers",
    "a 36 in strut trapeze", "a 36 in slotted strut trapeze", "a 7 tier trapeze",
    "a 2 tier trapeze with 1/2 in rod 2 ft above",
    "a 2 tier trapeze with 1/2 rod", "a 2 tier 1-5/8 strut trapeze",
    "a 1-5/8 in wide strut trapeze", "a 13/16 in strut trapeze",
    "a 2 tier trapeze with 18 in rod spacing", "a 6 tier 48 in trapeze",
])
def test_every_phrasing_builds(prompt):
    """The review found "a 1-5/8 in wide strut trapeze" delivered NO file."""
    assert AR.resolve_prompt(prompt).parts()


def test_an_override_re_derives_rather_than_keeping_a_stale_derivation():
    r = AR.resolve("strut_trapeze", {"rod_inset_in": 4},
                   prompt="a 2 tier trapeze with 18 in rod spacing")
    assert r.values["strut_length_in"] == pytest.approx(26.0)   # 18 + 2 x 4, not 24
    assert "strut_length_in" in r.derived and r.parts()


@pytest.mark.parametrize("prompt, said", [
    ("a 7 tier trapeze", "7 tier"),
    ("a 2 tier 25 ft trapeze", "25 ft trapeze"),
    ("a trapeze with 2 in threaded rod", "2 in threaded rod"),
])
def test_an_out_of_range_number_is_reported_not_silently_dropped(prompt, said):
    r = AR.resolve_prompt(prompt)
    assert [o["said"] for o in r.out_of_range] == [said]
    assert r.parts()                                     # still delivered


def test_the_route_names_a_number_it_did_not_use():
    out = tempfile.mkdtemp(prefix="t900_")
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "route.py"), "run",
         "--prompt", "a 7 tier trapeze", "--output", "rfa", "--out", out, "--json"],
        capture_output=True, text=True, timeout=300, cwd=ROOT)
    res = json.loads(proc.stdout)
    assert res["ok"] and os.path.getsize(res["files"]["rfa"]) > 0
    assert any(c.startswith('NOT USED: "7 tier"') for c in res["caveats"]), res["caveats"]


def test_strut_length_rod_spacing_and_inset_must_agree():
    with pytest.raises(AR.ArchetypeError, match="state two of the three"):
        AR.resolve("strut_trapeze", {"strut_length_in": 36, "rod_spacing_in": 24,
                                     "rod_inset_in": 3}).parts()


@pytest.fixture(scope="module")
def parts():
    return AR.resolve("strut_trapeze", {}).parts()


def _named(parts, word):
    return [p for p in parts if word in p["name"]]


def test_two_tiers_each_a_real_slotted_channel(parts):
    for t in (1, 2):
        tier = _named(parts, f"tier {t} ")
        assert len(_named(tier, "back segment")) > 1, "slotted back is segments"
        assert len(_named(tier, "web")) == 2 and len(_named(tier, "inturned lip")) == 2
    t2_back = _named(parts, "tier 2 back segment")[0]
    assert t2_back["base_z_ft"] == pytest.approx(12 * IN)   # 12 in tier spacing


def test_two_rods_full_length_through_both_tiers(parts):
    rods = _named(parts, "threaded rod")
    assert len(rods) == 2
    xs = sorted(r["center"][0] for r in rods)
    assert xs[1] - xs[0] == pytest.approx(24 * IN)          # 30 in strut, 3 in insets
    for r in rods:
        assert r["radius_ft"] == pytest.approx(0.375 * IN / 2)
        bottom, top = r["base_z_ft"], r["base_z_ft"] + r["height_ft"]
        lowest_nut = min(p["base_z_ft"] for p in _named(parts, "nut below"))
        assert bottom == pytest.approx(lowest_nut - 1 * IN)  # 1 in tail below the nut
        assert top == pytest.approx((12 + 1.625 + 24) * IN)  # 24 in above the top tier


def test_washers_and_nuts_clamp_each_tier_at_each_rod(parts):
    for t, z0 in ((1, 0.0), (2, 12 * IN)):
        for side in ("left", "right"):
            wb = _named(parts, f"tier {t} washer below {side}")[0]
            nb = _named(parts, f"tier {t} nut below {side}")[0]
            wa = _named(parts, f"tier {t} washer above {side}")[0]
            na = _named(parts, f"tier {t} nut above {side}")[0]
            assert wb["base_z_ft"] + wb["height_ft"] == pytest.approx(z0)   # under the back
            assert nb["base_z_ft"] + nb["height_ft"] == pytest.approx(wb["base_z_ft"])
            assert wa["base_z_ft"] == pytest.approx(z0 + 1.625 * IN)         # on the lips
            assert na["base_z_ft"] == pytest.approx(wa["base_z_ft"] + wa["height_ft"])
            assert nb["shape"] == "polygon" and len(nb["vertices"]) == 7    # hexagon, closed


@pytest.mark.parametrize("over, word", [
    ({"tiers": 0.0}, "1 to 6"),
    ({"tiers": 7.0}, "1 to 6"),
    ({"tiers": 2.5}, "1 to 6"),
    ({"tier_spacing_in": 2.0}, "between tiers"),
    ({"rod_inset_in": 0.5, "rod_spacing_in": 29.0}, "past the end"),
    ({"strut_length_in": 6.0, "rod_inset_in": 3.0, "rod_spacing_in": 0.0}, "no room"),
    ({"strut_length_in": 7.0, "rod_inset_in": 3.0, "rod_spacing_in": 1.0}, "washers"),
])
def test_impossible_trapezes_are_refused_by_name(over, word):
    arch = AR.archetype("strut_trapeze")
    with pytest.raises(AR.ArchetypeError, match=word):
        arch.build(dict(arch.defaults(), **over))


def test_every_adjustable_dimension_is_a_family_parameter_with_its_value():
    prod = F.make_archetype(product="strut_trapeze",
                            prompt="a 3 tier slotted trapeze 36 in long with 1/2 in threaded rod")
    doc = prod.doc
    row = doc.types[0][1]
    val = {cap: row[p.elem_id] for cap, p in doc.params.items() if p.elem_id in row}
    assert val["Number of Tiers"] == 3 and isinstance(val["Number of Tiers"], int)
    assert val["Strut Length"] == pytest.approx(36 * IN)
    assert val["Rod Spacing"] == pytest.approx(30 * IN)     # 36 - 2 x 3 in inset
    assert val["Rod Diameter"] == pytest.approx(0.5 * IN)
    assert val["Tier Spacing"] == pytest.approx(12 * IN)
    assert "Overall Height" not in val                     # was a copy of Rod Length
    for cap in ("Rod Inset", "Rod Above Top Tier", "Rod Below Bottom Nut", "Strut Height",
                "Strut Width", "Strut Thickness", "Slot Length", "Slot Spacing",
                "Washer Size", "Washer Thickness", "Nut Across Flats"):
        assert val[cap] > 0, cap
    assert prod.name.startswith("Strut Trapeze 36 in 3 Tier")


def test_the_route_delivers_the_trapeze_where_main_built_one_channel():
    out = tempfile.mkdtemp(prefix="t899_")
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "route.py"), "run",
         "--prompt", "a 2 tier slotted trapeze with threaded rod",
         "--output", "rfa", "--out", out, "--json"],
        capture_output=True, text=True, timeout=300, cwd=ROOT)
    res = json.loads(proc.stdout)
    assert res["ok"], res.get("status")
    assert os.path.getsize(res["files"]["rfa"]) > 0
    report = json.load(open(res["files"]["rfa_report"], encoding="utf-8"))
    fam = report["family"]
    assert fam["family_name"].startswith("Strut Trapeze")
    assert len(fam["forms"]) > 40                            # was 5: one channel
    assert {"Number of Tiers", "Rod Spacing", "Tier Spacing", "Rod Diameter"} <= set(fam["parameters"])
    assert report["validate"]["family_mode"]["n_errors"] == 0

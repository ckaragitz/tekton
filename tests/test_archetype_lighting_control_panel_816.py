"""A prompt for a lighting control panel builds one (issue #816).

The taxonomy recognised the kind and its Revit category but declared no
mechanism, so the route REFUSED -- ``files: {}`` -- which is hard rule 1 and
S-2026-08-10-e's "not a refusal".  The owner found it on the first try.

These tests pin the lane, the parts and where they are, and the provenance.
"It builds" alone would pass a cabinet whose seven parts were stacked at the
origin, so the geometry is asserted by position, not just by count.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile

import pytest

from rvt.famgen import archetypes as AR
from rvt.famgen import taxonomy as TX

IN = 1.0 / 12.0
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_the_taxonomy_routes_the_kind_to_the_archetype_lane():
    kind = TX.get("lighting_control_panel")
    assert "archetype:lighting_control_panel" in kind.via
    assert kind.lane == "archetype"            # was "none" -- the refusal
    ok, why = TX.builder_available(kind, strict=True)
    assert ok, why                              # strict: imports and proves the builder


@pytest.mark.parametrize("prompt", [
    "create a lighting control panel family",
    "a lighting control panel",
    "a lighting relay panel",
])
def test_every_way_of_naming_it_resolves_to_the_archetype_all_nominal(prompt):
    r = AR.resolve_prompt(prompt)
    assert r is not None and r.arch.key == "lighting_control_panel", prompt
    assert r.arch.category == "electrical_equipment"
    assert set(r.provenance.values()) == {"nominal"}, (prompt, r.provenance)


@pytest.mark.parametrize("prompt", [
    "a generator relay panel",
    "a protective relay panel",
    "a fire alarm relay panel",
    "an AHU with an LCP",           # in HVAC, LCP is a LOCAL control panel
    "a relay panel",
    "an LCP",
])
def test_names_that_mean_another_product_do_not_build_this_one(prompt):
    """Matching bare "relay panel" / "LCP" once built a lighting control panel
    for a generator relay panel and for an AHU's local control panel (#821
    review) -- a different product under the name asked for.  Only the names
    that mean THIS product resolve to it."""
    r = AR.resolve_prompt(prompt)
    assert r is None or r.arch.key != "lighting_control_panel", prompt


def test_a_stated_size_is_given_and_the_rest_stay_nominal():
    r = AR.resolve_prompt("a 24 in wide, 36 in tall lighting control panel")
    assert (r.values["width_in"], r.values["height_in"]) == (24.0, 36.0)
    assert r.provenance["width_in"] == "given" and r.provenance["height_in"] == "given"
    assert r.provenance["depth_in"] == "nominal"


@pytest.fixture(scope="module")
def parts():
    arch = AR.archetype("lighting_control_panel")
    return {p["name"]: p for p in arch.build(arch.defaults())}


def _y_span(p):
    cy, hd = p["center"][1], p["depth_ft"] / 2.0
    return cy - hd, cy + hd


def test_the_parts_are_the_cabinet_not_a_labelled_box(parts):
    assert set(parts) == {"back", "wall top", "wall bottom", "wall left", "wall right",
                          "door", "door latch"}


def test_the_cabinet_stands_on_the_mounting_plane_and_projects_forward(parts):
    """Back on y = 0, everything else in front of it (-Y), nothing behind."""
    back0, back1 = _y_span(parts["back"])
    assert back1 == pytest.approx(0.0)
    for name, p in parts.items():
        assert _y_span(p)[1] <= 1e-9, f"{name} pokes behind the mounting plane"


def test_the_door_is_the_front_face_and_the_latch_is_on_it(parts):
    """The door's front face is the cabinet's depth; the latch sits proud of
    it.  Stacked at the origin, the door would coincide with the back."""
    D = 6.0 * IN
    door0, door1 = _y_span(parts["door"])
    assert door0 == pytest.approx(-D)
    latch0, latch1 = _y_span(parts["door latch"])
    assert latch1 == pytest.approx(door0) and latch0 < door0
    assert parts["door latch"]["center"][0] > 0, "the latch is on the door's right edge"
    lz0 = parts["door latch"]["base_z_ft"]
    lz1 = lz0 + parts["door latch"]["height_ft"]
    assert (lz0 + lz1) / 2 == pytest.approx(30.0 * IN / 2), "the latch is at mid-height"


def test_the_walls_close_the_box_between_back_and_door(parts):
    back1_front = _y_span(parts["back"])[0]
    door_back = _y_span(parts["door"])[1]
    for w in ("wall top", "wall bottom", "wall left", "wall right"):
        w0, w1 = _y_span(parts[w])
        assert w1 == pytest.approx(back1_front) and w0 == pytest.approx(door_back), w
    W = 20.0 * IN
    assert parts["wall left"]["center"][0] == pytest.approx(-parts["wall right"]["center"][0])
    # ... and in Z: top and bottom walls cap the box, the side walls fill the
    # height between them -- no gap, no overlap (the #821 review found three Z
    # mutations that no test caught)
    H, g = 30.0 * IN, 0.075 * IN

    def z_span(p):
        return p["base_z_ft"], p["base_z_ft"] + p["height_ft"]

    assert z_span(parts["wall bottom"]) == pytest.approx((0.0, g))
    assert z_span(parts["wall top"]) == pytest.approx((H - g, H))
    for side in ("wall left", "wall right"):
        assert z_span(parts[side]) == pytest.approx((g, H - g)), side
    for full in ("back", "door"):
        assert z_span(parts[full]) == pytest.approx((0.0, H)), full
    assert abs(parts["wall right"]["center"][0]) + parts["wall right"]["width_ft"] / 2 \
        == pytest.approx(W / 2)


def test_a_sheet_thicker_than_half_the_box_is_refused_by_name():
    arch = AR.archetype("lighting_control_panel")
    v = dict(arch.defaults(), thickness_in=4.0)
    with pytest.raises(AR.ArchetypeError, match="lighting control panel"):
        arch.build(v)


def test_the_route_delivers_a_file_where_main_refused():
    """The repro from #816, end to end: main answered ok=False, files={}."""
    out = tempfile.mkdtemp(prefix="t816_")
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "route.py"), "run",
         "--prompt", "create a lighting control panel family",
         "--output", "rfa", "--out", out, "--json"],
        capture_output=True, text=True, timeout=300, cwd=ROOT)
    res = json.loads(proc.stdout)
    assert res["ok"], res.get("status")
    assert os.path.getsize(res["files"]["rfa"]) > 0
    report = json.load(open(res["files"]["rfa_report"], encoding="utf-8"))
    assert report["family"]["category"] == "Electrical Equipment"
    depth = report["facts"]["values"]["overall_depth_in"]["value"]
    assert depth == pytest.approx(6.75), "6 in cabinet + 0.75 in latch; 5.85 means stacked"

"""The lighting control panel WITH its NEC working space (issue #820, steer #818).

Owner, on the panel built for their test: "for the future you need to know NEC
code in order to get the clearances on there", and "clearances need to be
toggleable within the family parameters".

What this pins, and what it deliberately does not claim:

* a prompt asking for the clearance gets the NEC 110.26(A) working space
  (sized by rvt.famgen.clearance, #819) as a real solid, in front of the door,
  from the floor up;
* the zone is kept OUT of the panel's own Width / Depth / Height -- a 3.5 ft
  zone is not a 6 in cabinet's depth;
* a real "Show Clearance" Yes/No parameter exists -- and the output says
  plainly that it is NOT yet linked to the zone's visibility (#690) and that
  there is no subcategory, so the zone is always drawn;
* the plain panel is unchanged: no zone, no toggle.
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
from rvt.famgen import clearance as CL

IN = 1.0 / 12.0
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ---------------------------------------------------------------------------
# the request
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("prompt,want", [
    ("a lighting control panel with NEC clearance", True),
    ("a lighting control panel with clearances", True),
    ("a lighting control panel showing the working space", True),
    ("a lighting control panel with working clearance", True),
    ("a lighting control panel", False),
    ("a lighting control panel without clearance", False),
    ("a lighting control panel, no NEC clearance", False),
    ("a lighting control panel w/o working space", False),
])
def test_the_clearance_is_drawn_only_when_asked_for(prompt, want):
    r = AR.resolve_prompt(prompt)
    assert r.arch.key == "lighting_control_panel"
    assert r.clearance is want
    assert len(r.parts()) == (8 if want else 7)
    assert r.name.endswith("with NEC Clearance") is want


# ---------------------------------------------------------------------------
# the zone: where it is and how big
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def zone():
    r = AR.resolve_prompt("a lighting control panel with NEC clearance")
    return r, AR.working_space_part(r)


def test_the_zone_is_the_nec_working_space_at_the_stated_defaults(zone):
    r, z = zone
    ws = CL.working_space(equipment_width_ft=20 * IN, equipment_height_ft=30 * IN)
    assert z["role"] == "clearance"
    assert (z["width_ft"], z["depth_ft"], z["height_ft"]) == (ws.width_ft, ws.depth_ft, ws.height_ft)
    assert (z["width_ft"], z["depth_ft"], z["height_ft"]) == pytest.approx((30 * IN, 3.5, 6.5))


def test_the_zone_starts_at_the_door_face_and_extends_forward(zone):
    """The cabinet projects toward -Y and the door face is at y = -depth, so
    the working space runs from -depth to -(depth + zone depth)."""
    r, z = zone
    D = r.values["depth_in"] * IN
    y_back = z["center"][1] + z["depth_ft"] / 2.0
    y_front = z["center"][1] - z["depth_ft"] / 2.0
    assert y_back == pytest.approx(-D)
    assert y_front == pytest.approx(-(D + z["depth_ft"]))
    assert z["center"][0] == 0.0, "centred on the equipment"


def test_the_zone_runs_from_the_floor_for_the_stated_mounting(zone):
    """110.26(A)(3) measures from the floor.  The family origin is the cabinet
    bottom, so the floor is MOUNT_TOP_IN minus the cabinet height below it."""
    r, z = zone
    H = r.values["height_in"] * IN
    floor = -(AR.MOUNT_TOP_IN * IN - H)
    assert z["base_z_ft"] == pytest.approx(floor) == pytest.approx(-4.0)
    assert z["base_z_ft"] + z["height_ft"] == pytest.approx(6.5 + floor)


def test_a_wider_panel_widens_the_zone_to_its_own_width():
    r = AR.resolve_prompt("a 24 in wide lighting control panel with clearance")
    assert AR.working_space_part(r)["width_ft"] == pytest.approx(30 * IN)   # 24 < 30
    r = AR.resolve("lighting_control_panel", {"width_in": 36},
                   prompt="a lighting control panel with clearance")
    assert AR.working_space_part(r)["width_ft"] == pytest.approx(36 * IN)


# ---------------------------------------------------------------------------
# the family: the zone does not become the panel's dimensions; the toggle exists
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def products():
    from rvt.frontdoor import standalone as SA
    SA.install_schema(SA.bundled_base_path())
    plain = F.make_archetype(product="lighting_control_panel",
                             prompt="a lighting control panel")
    clear = F.make_archetype(product="lighting_control_panel",
                             prompt="a lighting control panel with NEC clearance")
    return plain, clear


def test_the_zone_is_kept_out_of_the_panels_own_dimensions(products):
    plain, clear = products
    for k in ("overall_width_in", "overall_depth_in", "overall_height_in"):
        assert clear.facts.get(k) == pytest.approx(plain.facts.get(k)), k
    assert clear.facts.get("overall_depth_in") == pytest.approx(6.75)
    assert clear.facts.get("clearance_part_count") == 1
    assert plain.facts.get("clearance_part_count") is None


def test_show_clearance_is_a_real_yes_no_defaulting_to_yes(products):
    _plain, clear = products
    pe = clear.doc.params["Show Clearance"]
    assert pe.obj["m_pParamDef"]["ptr_class"] == "ParamDefYesNo"
    (_type_name, row), = clear.doc.types          # exactly one type, unconditionally
    assert row[pe.elem_id] == 1, "Show Clearance defaults to Yes"


def test_the_plain_panel_has_no_toggle(products):
    plain, _clear = products
    assert "Show Clearance" not in plain.doc.params


def test_the_notes_say_it_is_not_toggleable_and_not_verified(products):
    _plain, clear = products
    notes = " ".join(clear.notes)
    assert "NOT yet linked" in notes and "#690" in notes
    assert CL.UNCHECKED in notes
    assert "subcategory" in notes and "mounting" in notes


# ---------------------------------------------------------------------------
# the factory rule underneath
# ---------------------------------------------------------------------------

def test_a_model_of_only_clearances_is_refused():
    with pytest.raises(F.FactoryError, match="nothing to be the clearance of"):
        F.make_generic_model(parts=[{"shape": "box", "name": "z", "role": "clearance",
                                     "width_ft": 1, "depth_ft": 1, "height_ft": 1}])


def test_the_sanity_bounds_still_see_a_clearance_part():
    """Excluding the zone from the equipment's size must not exclude it from
    the #808 bounds: an absurd clearance is still refused."""
    with pytest.raises(F.FactoryError, match="sanity bound"):
        F.make_generic_model(parts=[
            {"shape": "box", "name": "box", "width_ft": 1, "depth_ft": 1, "height_ft": 1},
            {"shape": "box", "name": "z", "role": "clearance", "width_ft": 1,
             "depth_ft": 1, "height_ft": 1, "center": [0.0, 1e6]}])


def test_a_non_boolean_toggle_value_is_refused():
    with pytest.raises(F.FactoryError, match="True or False"):
        F.make_generic_model(parts=[{"shape": "box", "name": "b", "width_ft": 1,
                                     "depth_ft": 1, "height_ft": 1}],
                             numeric_params={"Show Clearance": ("yesno", 1)})


# ---------------------------------------------------------------------------
# end to end, through the route
# ---------------------------------------------------------------------------

def _route(prompt):
    out = tempfile.mkdtemp(prefix="t820_")
    proc = subprocess.run(
        [sys.executable, os.path.join(ROOT, "tools", "route.py"), "run", "--prompt", prompt,
         "--output", "rfa", "--out", out, "--json"],
        capture_output=True, text=True, timeout=300, cwd=ROOT)
    return json.loads(proc.stdout)


def test_the_route_delivers_the_variant_and_says_what_it_is_not():
    res = _route("create a lighting control panel family with NEC clearance")
    assert res["ok"], res.get("status")
    assert "with_NEC_Clearance" in os.path.basename(res["files"]["rfa"])
    assert "NOT toggleable yet" in res["status"]
    cav = " ".join(res["cell"]["caveats"] if "cell" in res else []) + " " + \
        " ".join(res.get("caveats", []))
    assert "NEC WORKING SPACE" in cav and "not checked against the NFPA 70 text" in cav


def test_a_clearance_on_a_product_with_no_working_space_rule_is_said_not_drawn():
    res = _route("create a cable tray family with clearance")
    assert res["ok"]
    cav = " ".join(res.get("caveats", []))
    assert "none was drawn" in cav

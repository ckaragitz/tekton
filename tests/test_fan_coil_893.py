"""#893 (steer #891): a horizontal concealed fan coil unit with a unit-mounted fused
disconnect, built from its researched parts.

* the anatomy: cabinet, supply duct collar (+x), return filter rack (-x), bottom
  access panel, four hanger brackets, coil supply / return and condensate stubs on
  the PIPING end (-y), the control box and the fused disconnect -- handle, rating
  label, conduit hub -- on the ELECTRICAL end (+y), opposite the coil connections;
* every dimension ``nominal`` unless given, the disconnect's 30 A frame / 15 A fuses
  ``given``, the voltage an assumption unless given;
* ONE electrical connector, on the disconnect's top, bound to Voltage;
* the NEC working space in front of the disconnect, magenta, bound to
  ``and(Show Clearances, Show Front Clearance)``;
* VALID, 0 errors, on 2026 and inside the 2025 build context.

"Behaves in Revit" is a desktop claim (hard rule 4); these pin what the file carries.
"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import equipment_clearance as EC  # noqa: E402
from rvt.famgen import fan_coil as FC  # noqa: E402

IN = 1 / 12.0


def test_the_anatomy_puts_pipes_and_power_on_opposite_ends():
    L, D, H = 42 * IN, 23 * IN, 10.5 * IN
    parts = FC.fan_coil_parts(L, D, H)
    by = {}
    for p in parts:
        by.setdefault(p["role"], []).append(p)
    for role, n in (("fan coil cabinet", 1), ("supply duct collar", 1), ("return filter rack", 1),
                    ("bottom access panel", 1), ("hanger bracket", 4), ("coil supply connection", 1),
                    ("coil return connection", 1), ("condensate drain connection", 1),
                    ("unit control box", 1), ("fused disconnect switch", 1),
                    ("disconnect operating handle", 1), ("disconnect rating label", 1),
                    ("disconnect conduit hub", 1)):
        assert len(by.get(role, [])) == n, role
    assert by["supply duct collar"][0]["cx"] > D / 2 and by["return filter rack"][0]["cx"] < -D / 2
    for role in ("coil supply connection", "coil return connection", "condensate drain connection"):
        assert by[role][0]["cy"] < -L / 2                       # the piping end
    for role in ("unit control box", "fused disconnect switch"):
        assert by[role][0]["cy"] > L / 2                        # the electrical end
    drain = by["condensate drain connection"][0]
    assert drain["zc"] - drain["r"] < 0.2 * H                   # at the drain pan, low
    disc = by["fused disconnect switch"][0]
    assert disc["z0"] >= 0 and disc["z0"] + disc["h"] <= H      # within the cabinet height
    hub = by["disconnect conduit hub"][0]
    assert hub["z0"] == pytest.approx(disc["z0"] + disc["h"]) and hub["z0"] + hub["h"] <= H + 1e-9
    assert FC.front_of_disconnect(parts) > disc["cy"] + disc["d"] / 2 - 1e-9


def test_a_cabinet_too_small_for_its_end_hardware_is_refused():
    with pytest.raises(ValueError):
        FC.fan_coil_parts(20 * IN, 23 * IN, 10.5 * IN)


@pytest.fixture(scope="module")
def fcu():
    return FC.make_fan_coil_unit()


def test_values_carry_their_provenance(fcu):
    v = fcu.facts.values
    assert {k: v[k].kind for k in ("length_in", "depth_in", "height_in")} == dict.fromkeys(
        ("length_in", "depth_in", "height_in"), "nominal")
    assert (v["disconnect_frame_a"].kind, v["disconnect_frame_a"].value) == ("given", 30.0)
    assert (v["disconnect_fuse_a"].kind, v["disconnect_fuse_a"].value) == ("given", 15.0)
    assert v["voltage_v"].kind == "assumed"
    assert fcu.facts.get("manufacturer") == "" and fcu.facts.get("model") == ""
    given = FC.make_fan_coil_unit(length_in=60, voltage=277)
    assert given.facts.values["length_in"].kind == "given"
    assert given.facts.values["voltage_v"].kind == "given"


def test_the_family_is_mechanical_equipment_with_one_power_connector_on_the_disconnect(fcu):
    assert fcu.doc.category_id == -2001140                       # Mechanical Equipment
    (con,) = fcu.doc.connectors
    disc = next(f for f in fcu.forms if f.params["role"] == "fused disconnect switch")
    gr = con.obj["m_oPlaneRef"]["value"]["m_geomRef"]
    assert gr["m_elemId"] == disc.by_class("ExtrusionElem")[0].elem_id and gr["m_geomTag"] == 1
    assert con.obj["m_pDomain"]["value"]["m_nNumberOfPoles"] == 2      # 208 V single-phase
    notes = "\n".join(fcu.doc.notes)
    assert "pipe / duct connectors are NOT authored" in notes


def test_the_disconnect_working_space_is_toggleable_and_magenta(fcu):
    zone = next(f for f in fcu.forms if f.params["role"] == "clearance: front working space")
    p = zone.params
    disc = next(f for f in fcu.forms if f.params["role"] == "fused disconnect switch").params
    assert (p["depth_ft"], p["width_ft"]) == pytest.approx((3.0, 2.5))       # 120 V to ground
    assert p["center"][0] == pytest.approx(disc["center"][0])
    ext = zone.by_class("ExtrusionElem")[0]
    cells = ext.obj["m_cellList"]["value"]["m_cells"]
    (d,) = cells[1]["value"]["m_paramDrivenData"]
    assert (d["m_famParamId"], d["m_elemPropId"]) == (fcu.doc.params[EC.P_FRONT_ON].elem_id,
                                                      EC.ELEM_PROP_VISIBLE)
    mats = [e for e in fcu.doc.elements if e.class_name == "MaterialElem"]
    assert len(mats) == 1 and ext.obj["m_materialId"] == mats[0].elem_id
    assert "110.26(A)(4)" in "\n".join(fcu.doc.notes)


@pytest.mark.parametrize("year", [2026, 2025])
def test_the_written_family_validates(fcu, tmp_path, year):
    out = str(tmp_path / f"fcu{year}.rfa")
    if year == 2026:
        rep = fcu.write(out)
    else:
        from rvt.frontdoor import release_ctx as RC
        base = os.path.join(ROOT, "plugin", "assets", "genesis", "G_ABPD_2025.rvt")
        if not os.path.exists(base):
            pytest.skip("the pinned 2025 base is not in this checkout")
        with RC.release_build_context(base):
            rep = FC.make_fan_coil_unit().write(out)
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True


def test_the_cli_builds_it(tmp_path):
    import subprocess
    out = tmp_path / "cli.rfa"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"), "fan-coil",
                        "--frame", "30", "--fuse", "15", "-o", str(out)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert out.exists() and "VALID (0 errors" in r.stdout


# --- review round 1 (#902) ------------------------------------------------------------

@pytest.mark.parametrize("v,ph,poles,vtg", [(120, 1, 1, 120), (208, 1, 2, 120), (240, 1, 2, 120),
                                            (277, 1, 1, 277), (480, 1, 2, 277), (208, 3, 3, 120),
                                            (480, 3, 3, 277), (600, 3, 3, 347)])
def test_poles_and_voltage_to_ground_follow_the_supply(v, ph, poles, vtg):
    assert FC.poles_for(v, ph) == poles
    assert FC.voltage_to_ground_for(v, ph) == vtg


def test_a_277v_unit_gets_a_one_pole_connector_and_given_provenance():
    prod = FC.make_fan_coil_unit(voltage=277)
    (con,) = prod.doc.connectors
    assert con.obj["m_pDomain"]["value"]["m_nNumberOfPoles"] == 1
    v = prod.facts.values
    assert (v["voltage_v"].kind, v["voltage_v"].source) == ("given", "the request")
    assert v["phases"].kind == "assumed"
    stated = FC.make_fan_coil_unit(voltage=208, phases=1).facts.values
    assert stated["voltage_v"].kind == "given" and stated["phases"].kind == "given"


def test_a_non_fused_disconnect_carries_no_fuse():
    prod = FC.make_fan_coil_unit(fused=False, disconnect_frame_a=60)
    assert "disconnect_fuse_a" not in prod.facts.values
    assert prod.facts.values["disconnect_frame_a"].source == "the request (60AF)"
    roles = [f.params["role"] for f in prod.forms]
    assert FC.ROLE_DISCONNECT_NF in roles and FC.ROLE_DISCONNECT not in roles
    assert len(prod.doc.connectors) == 1


@pytest.mark.parametrize("dims", [(20, 23, 10.5), (42, 12, 10.5), (42, 23, 6), (42, 15, 10.5)])
def test_odd_dimensions_still_deliver_the_cabinet_and_say_so(dims, tmp_path):
    L, D, H = dims
    prod = FC.make_fan_coil_unit(length_in=L, depth_in=D, height_in=H)
    roles = [f.params["role"] for f in prod.forms]
    assert roles[0] == FC.ROLE_CABINET and "clearance: front working space" in roles
    assert len(prod.doc.connectors) == 1
    assert any(n.startswith("fan coil end hardware NOT drawn") for n in prod.doc.notes)
    rep = prod.write(str(tmp_path / "odd.rfa"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0


def test_the_control_box_and_disconnect_never_overlap_at_the_smallest_depth():
    parts = FC.fan_coil_parts(42 * IN, FC.MIN_DEPTH_IN * IN, 10.5 * IN)
    cb = next(p for p in parts if p["role"] == "unit control box")
    ds = next(p for p in parts if p["role"] == FC.ROLE_DISCONNECT)
    assert cb["cx"] + cb["w"] / 2 <= ds["cx"] - ds["w"] / 2

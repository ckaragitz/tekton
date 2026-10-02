"""#895 (steer #891): a fan-powered terminal unit, series or parallel, built from its
researched parts.

* the anatomy: casing, round primary inlet at the -x end with its damper actuator,
  the induction opening (beside the inlet for series; in the side fan module's wall
  for parallel), the discharge collar at +x (after a hot-water reheat coil with two
  stubs, when asked), controls and the electrical enclosure (toggle disconnect,
  conduit hub) on the +y service side each in its own slot, four hanger brackets --
  and NO part overlapping another (the inlet meets the casing face);
* every dimension ``nominal`` unless given, the voltage an assumption unless given;
* one power and one conduit connector on the electrical enclosure (#894);
* the NEC working space in front of it, toggleable and magenta;
* VALID, 0 errors, at 2026, 2025 and 2024 (round parts square at 2024, #786); a casing
  too small for its hardware still delivers the casing, said.

"Behaves in Revit" is a desktop claim (hard rule 4); these pin what the file carries.
"""
from __future__ import annotations

import itertools
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from rvt.famgen import equipment_clearance as EC  # noqa: E402
from rvt.famgen import fan_powered as FP  # noqa: E402
from rvt.famgen.equipment_common import square_round_part as _square  # noqa: E402
from conftest import context_constants  # noqa: E402

pytestmark = pytest.mark.usefixtures("no_release_leak")   # rows build inside release_build_context


@pytest.fixture
def release_leak_extra():
    """``no_release_leak`` watches the names the authoring context swaps too (#707)."""
    return context_constants


IN = 1 / 12.0


def _bb(p):
    p = _square(p) if p["shape"] != "box" else p
    return (p["cx"] - p["w"] / 2, p["cx"] + p["w"] / 2, p["cy"] - p["d"] / 2,
            p["cy"] + p["d"] / 2, p["z0"], p["z0"] + p["h"])


@pytest.mark.parametrize("kind,reheat", [("series", "none"), ("parallel", "none"),
                                         ("series", "hot_water"), ("parallel", "electric")])
@pytest.mark.parametrize("dims", [(44, 30, 18, 10), (41, 18, 10, 6), (96, 48, 30, 16)])
def test_the_parts_do_not_overlap(kind, reheat, dims):
    L, W, H, d = (x * IN for x in dims)
    parts = FP.fan_powered_parts(L, W, H, kind=kind, inlet_d=d, reheat=reheat)
    for a, b in itertools.combinations(parts, 2):
        A, B = _bb(a), _bb(b)
        ov = [min(A[i + 1], B[i + 1]) - max(A[i], B[i]) for i in (0, 2, 4)]
        assert not all(o > 1e-6 for o in ov), (a["role"], b["role"])
    inlet = _square(next(p for p in parts if p["role"] == "primary air inlet"))
    assert inlet["cx"] + inlet["w"] / 2 == pytest.approx(-L / 2)        # meets the casing face
    assert inlet["w"] == pytest.approx(6 * IN) and inlet["d"] == pytest.approx(d)   # along x


def test_series_and_parallel_put_the_induction_opening_where_each_draws_air():
    s = {p["role"]: p for p in FP.fan_powered_parts(40 * IN, 30 * IN, 18 * IN, inlet_d=10 * IN)}
    assert s["induction opening filter"]["cx"] < -20 * IN and "parallel fan module" not in s
    p = {q["role"]: q for q in FP.fan_powered_parts(40 * IN, 30 * IN, 18 * IN, kind="parallel",
                                                    inlet_d=10 * IN)}
    assert p["parallel fan module"]["cy"] < -15 * IN
    assert p["induction opening filter"]["cy"] < p["parallel fan module"]["cy"]


@pytest.fixture(scope="module")
def box():
    return FP.make_fan_powered_box()


def test_provenance_connectors_and_zone(box):
    v = box.facts.values
    assert {k: v[k].kind for k in ("length_in", "width_in", "height_in", "inlet_in")} == dict.fromkeys(
        ("length_in", "width_in", "height_in", "inlet_in"), "nominal")
    assert (v["voltage_v"].kind, v["voltage_v"].value) == ("assumed", 277.0)
    assert box.doc.category_id == -2001140
    (power,) = box.doc.connectors
    (conduit,) = box.doc.mep_connectors
    assert power.obj["m_pDomain"]["value"]["m_nNumberOfPoles"] == 1          # 277 V: line-to-neutral
    assert conduit.obj["m_pDomain"]["ptr_class"] == "ConnectorElemDomainCableTrayConduit"
    zone = next(f for f in box.forms if f.params["role"] == "clearance: front working space")
    assert zone.params["depth_ft"] == pytest.approx(3.5)                     # 277 V to ground
    assert EC.P_FRONT_ON in box.doc.params
    notes = "\n".join(box.doc.notes)
    assert "pipe / duct connectors are NOT authored" in notes and "110.26(A)(4)" in notes


def test_electric_reheat_defaults_to_a_longer_casing():
    e = FP.make_fan_powered_box(reheat="electric")
    assert e.facts.values["length_in"].value == FP.NOMINAL_LENGTH_ELECTRIC_IN
    assert any(f.params["role"] == "electric heater control panel" for f in e.forms)


@pytest.mark.parametrize("kw", [dict(kind="mixed"), dict(reheat="steam"), dict(voltage=0),
                                dict(voltage=True), dict(phases=2)])
def test_invalid_input_is_refused(kw):
    with pytest.raises(ValueError):
        FP.make_fan_powered_box(**kw)


def test_a_small_casing_still_delivers_it(tmp_path):
    prod = FP.make_fan_powered_box(length_in=20)
    assert [f.params["role"] for f in prod.forms][0] == FP.ROLE_CASING
    assert any(n.startswith("terminal unit hardware NOT drawn") for n in prod.doc.notes)
    rep = prod.write(str(tmp_path / "small.rfa"))
    assert rep["validate"]["family_mode"]["n_errors"] == 0


@pytest.mark.parametrize("year", [2026, 2025, 2024])
@pytest.mark.parametrize("kw", [dict(), dict(kind="parallel", reheat="hot_water")])
def test_the_written_family_validates(tmp_path, year, kw):
    out = str(tmp_path / f"fp{year}.rfa")
    if year == 2026:
        prod = FP.make_fan_powered_box(**kw)
        rep = prod.write(out)
    else:
        from rvt.frontdoor import release_ctx as RC
        base = os.path.join(ROOT, "plugin", "assets", "genesis", f"G_ABPD_{year}.rvt")
        if not os.path.exists(base):
            pytest.skip(f"the pinned {year} base is not in this checkout")
        with RC.release_build_context(base):
            prod = FP.make_fan_powered_box(**kw)
            rep = prod.write(out)
    fm = rep["validate"]["family_mode"]
    assert (fm["verdict"], fm["n_errors"]) == ("VALID", 0) and rep["provenance"]["ok"] is True
    assert any("drawn SQUARE" in n for n in prod.doc.notes) == (year == 2024)


def test_the_cli_builds_it(tmp_path):
    import subprocess
    out = tmp_path / "cli.rfa"
    r = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make_family.py"),
                        "fan-powered-box", "--kind", "parallel", "--reheat", "hot_water",
                        "-o", str(out)], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    assert out.exists() and "VALID (0 errors" in r.stdout



# --- #926 ---------------------------------------------------------------------------------

@pytest.mark.parametrize("kw", [dict(inlet_in=0), dict(inlet_in=-4), dict(length_in=float("nan")),
                                dict(width_in=0), dict(height_in=True)])
def test_a_non_positive_or_nan_dimension_is_refused_in_inches(kw):
    with pytest.raises(ValueError, match="inches"):
        FP.make_fan_powered_box(**kw)


@pytest.mark.parametrize("kw", [dict(length_in=20), dict(reheat="electric", length_in=30)])
def test_the_casing_only_notes_say_only_what_is_drawn(kw):
    notes = "\n".join(FP.make_fan_powered_box(**kw).doc.notes)
    assert "draw duct and pipe to them by eye" not in notes
    assert "no inlet, discharge or induction openings to draw to" in notes
    assert "working space in front of the service side" in notes


def _touch(a, b, axis):
    """The two boxes share a face along ``axis`` (0 x, 1 y, 2 z) and overlap on the others."""
    A, B = _bb(a), _bb(b)
    lo, hi = 2 * axis, 2 * axis + 1
    meet = abs(A[hi] - B[lo]) < 1e-9 or abs(B[hi] - A[lo]) < 1e-9
    others = all(min(A[2 * k + 1], B[2 * k + 1]) - max(A[2 * k], B[2 * k]) > 0 for k in range(3) if k != axis)
    return meet and others


@pytest.mark.parametrize("kind,reheat", [("series", "hot_water"), ("parallel", "electric")])
def test_attached_hardware_touches_what_it_hangs_on(kind, reheat):
    """Not only no interpenetration: the attached parts are ON their hosts, never floating."""
    parts = {p["role"]: p for p in FP.fan_powered_parts(44 * IN, 30 * IN, 18 * IN, kind=kind,
                                                         inlet_d=10 * IN, reheat=reheat)}
    case = parts[FP.ROLE_CASING]
    assert _touch(parts["primary air inlet"], case, 0)
    assert _touch(parts["controls enclosure"], case, 1)
    assert _touch(parts[FP.ROLE_ELECTRICAL], case, 1)
    assert _touch(parts["disconnect toggle"], parts[FP.ROLE_ELECTRICAL], 1)
    assert _touch(parts["discharge collar"], parts.get("hot water reheat coil", case), 0)
    if kind == "parallel":
        assert _touch(parts["parallel fan module"], case, 1)
        assert _touch(parts["induction opening filter"], parts["parallel fan module"], 1)
        assert _touch(parts["electric heater control panel"], case, 1)
    else:
        assert _touch(parts["induction opening filter"], case, 0)
        for s in ("reheat supply connection", "reheat return connection"):
            assert _touch(parts[s], parts["hot water reheat coil"], 1)
    actuator, inlet = _bb(parts["primary damper actuator"]), _bb(parts["primary air inlet"])
    assert abs(actuator[3] - inlet[2]) < 1e-9                          # on the collar's side


def test_the_shared_helpers_live_in_equipment_common():
    from rvt.famgen import equipment_common as E
    from rvt.famgen import fan_coil as FC
    assert FC.poles_for is E.poles_for and FC._square is E.square_round_part
    assert E.poles_for(277, 1) == 1 and E.voltage_to_ground_for(480, 3) == 277


# --- #959 review nits -------------------------------------------------------------------

@pytest.mark.parametrize("kw,unit", [(dict(length_in="abc"), "inches"), (dict(inlet_in="4x"), "inches"),
                                     (dict(voltage="high"), "volts"), (dict(voltage=float("-inf")), "volts")])
def test_a_non_numeric_value_gets_the_same_refusal(kw, unit):
    with pytest.raises(ValueError, match=f"positive, finite number of {unit}"):
        FP.make_fan_powered_box(**kw)


@pytest.mark.parametrize("length_in", [41, 44, 60, 120])
def test_the_electric_heater_panel_is_centred_on_the_service_side(length_in):
    parts = {p["role"]: p for p in FP.fan_powered_parts(length_in * IN, 30 * IN, 18 * IN,
                                                         inlet_d=10 * IN, reheat="electric")}
    assert parts["electric heater control panel"]["cx"] == pytest.approx(0.0)

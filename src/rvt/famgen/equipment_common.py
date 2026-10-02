"""equipment_common -- what the generated ceiling-hung equipment families share (#926).

The fan coil unit (#893) and the fan-powered terminal unit (#895) share their
electrical reading of a supply and their clearance zone: the connector poles a
supply implies, its nominal voltage to ground and the stated assumption behind it,
the toggleable magenta NEC 110.26(A) working space drawn the unit's height (a
ceiling-hung family does not know the floor; 110.26(A)(4)), and the 2024 fallback
that draws round parts square (that release's class map has no ``ArcElemCell``,
#786).  Moved here from ``fan_coil`` unchanged in behaviour, so a third family does
not import private helpers across modules.
"""
from __future__ import annotations

import math
from typing import Any, Dict

def positive_finite(val: Any, what: str, unit: str) -> float:
    """``val`` as a positive, finite float, or a ``ValueError`` naming ``what`` and
    ``unit`` -- the one refusal for a bool, a non-numeric string, NaN, an infinity,
    zero or a negative (invalid input is refused with a message, never drawn)."""
    try:
        if type(val).__name__ in ("bool", "bool_"):    # Python's, and numpy's (1.x / 2.x)
            raise TypeError
        v = float(val)
    except (TypeError, ValueError, OverflowError):
        v = float("nan")
    if not (math.isfinite(v) and v > 0):
        raise ValueError(f"{what} must be a positive, finite number of {unit}, got {val!r}")
    return v


#: single-phase supplies that are LINE-TO-NEUTRAL (one pole + neutral); every other
#: single-phase supply (208, 240, 480, 600 V) is line-to-line: two poles
LINE_TO_NEUTRAL_V = (120.0, 127.0, 277.0, 347.0)


def poles_for(voltage: float, phases: int) -> int:
    """Connector poles for a supply: 3 for three-phase; single-phase is 1 pole when
    the voltage is line-to-neutral (120 / 127 / 277 / 347 V), else 2."""
    if int(phases) >= 3:
        return 3
    return 1 if any(abs(float(voltage) - v) <= 5.0 for v in LINE_TO_NEUTRAL_V) else 2


def voltage_to_ground_for(voltage: float, phases: int) -> float:
    """The nominal voltage to ground of a supply (for the 110.26(A) table), stated
    as an assumption by the caller:

    * single-phase line-to-neutral (120 / 277 / 347 V): its own voltage;
    * single-phase 240 V: the 120/240 V system, 120 V;
    * three-phase 240 V: a DELTA system -- no conductor is 120 V to ground (a
      high leg is 208 V, a corner-grounded phase 240 V, and an ungrounded system
      counts its phase-to-phase voltage), so 240 V, the conservative reading;
    * 208 -> 120, 480 -> 277, 600 -> 347 (the wye systems);
    * anything else: V / sqrt(3) (a wye system)."""
    v = float(voltage)
    if int(phases) < 3 and poles_for(v, phases) == 1:
        return v
    if abs(v - 240.0) <= 10.0:
        return 240.0 if int(phases) >= 3 else 120.0
    for ll, ln in ((208.0, 120.0), (480.0, 277.0), (600.0, 347.0)):
        if abs(v - ll) <= 10.0:
            return ln
    return round(v / 3 ** 0.5)


def arcs_available() -> bool:
    """True when the class map in force can author an arc (a round sketch): the
    2024 map has no ``ArcElemCell`` (#786)."""
    from ..genesis import types as GT
    try:
        GT.class_id("ArcElemCell")
    except KeyError:
        return False
    return True


def square_round_part(p: Dict[str, Any]) -> Dict[str, Any]:
    """A round part as the square box of the same envelope (for a map with no arcs)."""
    if p["shape"] == "cylinder":
        return {"shape": "box", "role": p["role"], "w": 2 * p["r"], "d": 2 * p["r"], "h": p["h"],
                "z0": p["z0"], "cx": p["cx"], "cy": p["cy"]}
    along_x = p["shape"] == "cylinder_x"                 # its length runs along x, not y
    return {"shape": "box", "role": p["role"],
            "w": p["length"] if along_x else 2 * p["r"],
            "d": 2 * p["r"] if along_x else p["length"], "h": 2 * p["r"],
            "z0": p["zc"] - p["r"], "cx": p["cx"], "cy": p["cy"]}


def add_working_zone(doc, forms, ws, H: float, y0: float, zx: float, where: str, vtg: float) -> None:
    """The toggleable, magenta NEC working-space form of a ceiling-hung unit, in front
    of ``where`` (e.g. "disconnect"): ``ws`` = the 110.26(A) :class:`WorkingSpace`,
    drawn the unit's height ``H`` from its bottom, starting at y = ``y0`` and extending
    +y, centred at x = ``zx``; ``forms`` receives it."""
    from . import equipment_clearance as EC
    from . import factory as F
    from . import skeleton as SK
    zone = F.add_box_form(doc, ws.width_ft, ws.depth_ft, H, base_z_ft=0.0,
                          center=(zx, y0 + ws.depth_ft / 2.0))
    zone.params.update({"role": "clearance: front working space", "source": ws.source,
                        "width_ft": ws.width_ft, "depth_ft": ws.depth_ft, "height_ft": H,
                        "base_z_ft": 0.0, "center": (zx, y0 + ws.depth_ft / 2.0)})
    mat = EC.new_family_material(doc, EC.CLEARANCE_MATERIAL, EC.CLEARANCE_RGB,
                                 EC.CLEARANCE_TRANSPARENCY)
    EC.apply_material(zone, mat)
    yes = SK.SPEC_YESNO
    doc.add_family_parameter(EC.P_SHOW, yes, EC.GROUP_VISIBILITY, is_instance=True, default=1)
    doc.add_family_parameter(EC.P_FRONT, yes, EC.GROUP_VISIBILITY, is_instance=False, default=1)
    on = doc.add_family_parameter(EC.P_FRONT_ON, yes, EC.GROUP_VISIBILITY, is_instance=True,
                                  formula=f"and({EC.P_SHOW}, {EC.P_FRONT})", default=1)
    EC.bind_visibility(zone, on)
    forms.append(zone)
    doc.notes.append(
        f"clearance zone (steer #882): working space in front of the "
        f"{where}, "
        f"{ws.depth_ft:g} ft deep x {ws.width_ft * 12:g} in wide ({ws.source}; {ws.status}; "
        f"{vtg:g} V to ground) -- drawn the UNIT's height, not 6 1/2 ft from the floor: a "
        f"ceiling-hung family does not know the floor, and above a suspended ceiling NEC "
        f"110.26(A)(4) (limited access) governs; shown by '{EC.P_SHOW}' and '{EC.P_FRONT}', "
        f"bound to its visibility -- NOT yet verified in Revit (hard rule 4)")
    for k, v in ws.assumed.items():
        doc.notes.append(f"clearance assumption -- {k}: {v}")


def note_voltage_to_ground(doc, vtg, voltage, phases) -> None:
    """The stated assumption behind a derived voltage to ground."""
    if phases >= 3 and abs(voltage - 240.0) <= 10.0:
        why = (" -- read as a delta (240Y/139 V systems exist): no conductor of a delta is "
               "120 V to ground (high leg 208 V, corner-grounded 240 V), so the conservative 240 V")
    elif phases < 3 and abs(voltage - 240.0) <= 10.0:
        why = (" -- read as the 120/240 V single-phase system; a load on a corner-grounded "
               "240 V delta is 240 V to ground and needs the deeper space")
    else:
        why = ""
    doc.notes.append(f"clearance assumption -- voltage_to_ground: {vtg:g} V (from the "
                     f"{voltage:g} V {phases}-phase supply{why}) -- state it if the system "
                     f"differs (--voltage-to-ground)")

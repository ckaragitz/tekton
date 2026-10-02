"""fan_powered -- a FAN-POWERED TERMINAL UNIT (series or parallel) built from its
researched parts (owner steer #891: "do your research about fan coil units or fan power
boxes"; #895).

THE ANATOMY (standard practice for the class, from public product literature read
for this module -- anatomy and class proportions only; no manufacturer's dimension
is carried):

* a lined sheet-metal CASING hung above the ceiling: standard height about 17-20 in
  (low-profile units about 10.5-12.5 in), offered in a handful of casing sizes;
* the PRIMARY-AIR INLET: a round collar (classes of about 4-16 in) with its damper and
  the damper actuator on its side, at one end (here -x; airflow +x);
* a SERIES unit puts its fan in the airstream and draws plenum air through an
  INDUCTION opening (often filtered) beside the primary inlet; a PARALLEL unit mounts
  its fan beside the primary airstream, with its own induction opening in the casing
  wall and a backdraft damper (internal, not drawn);
* a rectangular DISCHARGE collar at the other end, optionally after a hot-water
  REHEAT coil (two pipe stubs) or with an electric heater's control panel;
* the CONTROLS enclosure and the high-voltage ELECTRICAL enclosure (with a toggle
  disconnect, its feeder entering through a conduit hub) on the service side (+y);
* four HANGER BRACKETS.

Every dimension is ``nominal`` unless given; the voltage an assumption unless given
(277 V single-phase, the common ECM-motor supply, stated).  One power connector and
the feeder's conduit connector (#894) sit on the electrical enclosure.  Pipe and duct
connectors are NOT authored: no corpus specimen pins their system (#894); the inlet,
discharge, induction and reheat stubs are geometry, said in the notes.

Clearance: the NEC 110.26(A) working space in front of the electrical enclosure, drawn
the unit's height (a ceiling-hung family does not know the floor; 110.26(A)(4)),
magenta and toggleable like every equipment family (#882 / #884).  "Behaves in Revit"
needs a desktop verdict (hard rule 4).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from .equipment_common import (add_working_zone, arcs_available, note_voltage_to_ground, poles_for,
                               positive_finite, square_round_part, voltage_to_ground_for)
from .fan_coil import IN, CONDUIT_NOMINAL_IN

KINDS = ("series", "parallel")
REHEATS = ("none", "hot_water", "electric")
#: nominal casing (a mid-size unit): length (x, airflow) x width (y) x height
NOMINAL_LENGTH_IN, NOMINAL_WIDTH_IN, NOMINAL_HEIGHT_IN = 40.0, 30.0, 18.0
NOMINAL_INLET_IN = 10.0
#: a unit with an electric heater is longer: its heater section and control panel
NOMINAL_LENGTH_ELECTRIC_IN = 44.0
#: smallest casing with room for the end and side hardware: the service side holds the
#: controls and the electrical enclosure (10 in each, 3.5 in from the ends), and an
#: electric heater's panel between them needs a longer casing
MIN_LENGTH_IN, MIN_WIDTH_IN, MIN_HEIGHT_IN = 28.0, 18.0, 10.0
MIN_LENGTH_ELECTRIC_IN = 41.0

ROLE_CASING = "terminal unit casing"
ROLE_ELECTRICAL = "electrical enclosure"


def fan_powered_parts(L: float, W: float, H: float, *, kind: str = "series", inlet_d: float,
                      reheat: str = "none") -> List[Dict[str, Any]]:
    """The parts (feet): casing centred on the origin in plan, bottom at z = 0; airflow
    +x (primary inlet at -x, discharge at +x); service side +y.  Shapes as
    :func:`rvt.famgen.fan_coil.fan_coil_parts`."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    if reheat not in REHEATS:
        raise ValueError(f"reheat must be one of {REHEATS}, got {reheat!r}")
    if not all(math.isfinite(v) and v > 0 for v in (L, W, H, inlet_d)):
        raise ValueError(f"casing and inlet must be positive, got {L * 12:g} x {W * 12:g} x "
                         f"{H * 12:g} in, inlet {inlet_d * 12:g} in")
    min_l = MIN_LENGTH_ELECTRIC_IN if reheat == "electric" else MIN_LENGTH_IN
    if L < min_l * IN or W < MIN_WIDTH_IN * IN or H < MIN_HEIGHT_IN * IN:
        raise ValueError(f"a casing under {min_l:g} in long, {MIN_WIDTH_IN:g} in wide or "
                         f"{MIN_HEIGHT_IN:g} in high has no room for its end and side hardware")
    if inlet_d > H - 2 * IN or inlet_d > W / 2 - 1 * IN:
        raise ValueError(f"a {inlet_d * 12:g} in inlet does not fit a {W * 12:g} x {H * 12:g} in end")

    def box(role, w, d, h, z0, cx=0.0, cy=0.0):
        return {"shape": "box", "role": role, "w": w, "d": d, "h": h, "z0": z0, "cx": cx, "cy": cy}

    ri = inlet_d / 2
    xin, xout = -L / 2, L / 2
    parts = [box(ROLE_CASING, L, W, H, 0.0)]
    # primary inlet (-x end, toward -y) with its damper actuator on the collar's side
    yin = -W / 4
    parts.append({"shape": "cylinder_x", "role": "primary air inlet", "r": ri, "length": 6 * IN,
                  "zc": H / 2, "cx": xin - 3 * IN, "cy": yin})
    parts.append(box("primary damper actuator", 3 * IN, 3 * IN, 2.5 * IN, H / 2 - 1.25 * IN,
                     xin - 3 * IN, yin - ri - 1.5 * IN))
    # induction opening: series = on the inlet end beside the primary inlet; parallel =
    # in the fan module's wall
    if kind == "series":
        parts.append(box("induction opening filter", 1.0 * IN, W * 0.4, H - 4 * IN, 2 * IN,
                         xin - 0.5 * IN, W / 4))
    else:
        fw, fd = 0.4 * L, 0.35 * W
        fx = xout - fw / 2 - 3 * IN                     # clear of the corner hanger bracket
        parts.append(box("parallel fan module", fw, fd, H - 2 * IN, 1 * IN, fx, -W / 2 - fd / 2))
        parts.append(box("induction opening filter", fw - 4 * IN, 1.0 * IN, H - 6 * IN, 3 * IN,
                         fx, -W / 2 - fd - 0.5 * IN))
    # discharge (+x end), after the reheat coil section when there is one
    xd = xout
    if reheat == "hot_water":
        parts.append(box("hot water reheat coil", 6 * IN, W - 6 * IN, H - 4 * IN, 2 * IN,
                         xout + 3 * IN, 0.0))
        for role, zc in (("reheat supply connection", 0.35 * H), ("reheat return connection", 0.65 * H)):
            parts.append({"shape": "cylinder_y", "role": role, "r": 0.3125 * IN,
                          "length": 2 * IN, "zc": zc, "cx": xout + 3 * IN, "cy": W / 2 - 3 * IN + 1 * IN})
        xd = xout + 6 * IN
    parts.append(box("discharge collar", 1.5 * IN, W - 8 * IN, H - 6 * IN, 3 * IN, xd + 0.75 * IN, 0.0))
    # service side (+y): the controls at the inlet end, the electrical enclosure at the
    # discharge end, an electric heater's control panel centred between them -- each in
    # its own slot along the side, clear of the corner hanger brackets
    ch = min(8 * IN, H - 3 * IN)
    parts.append(box("controls enclosure", 10 * IN, 3.5 * IN, ch, (H - ch) / 2, xin + 8.5 * IN,
                     W / 2 + 1.75 * IN))
    eh = min(10 * IN, H - 2 * IN)
    ex, ez0, ed = xout - 8.5 * IN, (H - eh) / 2, 4 * IN
    parts.append(box(ROLE_ELECTRICAL, 10 * IN, ed, eh, ez0, ex, W / 2 + ed / 2))
    face = W / 2 + ed
    parts.append(box("disconnect toggle", 0.75 * IN, 1.0 * IN, 1.5 * IN, ez0 + eh / 2 - 0.75 * IN,
                     ex + 3 * IN, face + 0.5 * IN))
    parts.append({"shape": "cylinder", "role": "electrical conduit hub", "r": 0.55 * IN,
                  "h": min(0.75 * IN, H - (ez0 + eh)), "z0": ez0 + eh, "cx": ex,
                  "cy": W / 2 + ed / 2})
    if reheat == "electric":
        hh = min(12 * IN, H - 2 * IN)
        parts.append(box("electric heater control panel", 10 * IN, 4 * IN, hh, (H - hh) / 2,
                         0.0, W / 2 + 2 * IN))
    # hanger brackets at the top corners, on the long sides
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(box("hanger bracket", 2.0 * IN, 1.5 * IN, 1.5 * IN, H - 1.5 * IN,
                             sx * (L / 2 - 1.5 * IN), sy * (W / 2 + 0.75 * IN)))
    return parts


def make_fan_powered_box(*, kind: str = "series", length_in: Optional[float] = None,
                         width_in: Optional[float] = None, height_in: Optional[float] = None,
                         inlet_in: Optional[float] = None, reheat: str = "none",
                         voltage: Optional[float] = None, phases: Optional[int] = None,
                         voltage_to_ground: Optional[float] = None,
                         name: Optional[str] = None, start_id: int = 1000,
                         shared_params: Any = None, standards: bool = True):
    """Compose the fan-powered terminal unit family (see the module docstring).
    Dimensions left ``None`` are the class nominals; the voltage and phases
    assumptions unless given (277 V single-phase, stated).  A casing too small for its
    hardware still delivers the casing, said (hard rule 1); invalid input (an unknown
    kind or reheat, a voltage that is not positive and finite, phases other than 1 or
    3) is refused."""
    from . import factory as F
    from . import geometry as G
    from . import skeleton as SK
    from . import standards as ST
    from . import equipment_clearance as EC
    from . import clearance as CL
    from . import mep_connectors as MC

    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    if reheat not in REHEATS:
        raise ValueError(f"reheat must be one of {REHEATS}, got {reheat!r}")
    if voltage is not None:
        positive_finite(voltage, "supply voltage", "volts")
    if phases is not None and (isinstance(phases, bool) or phases not in (1, 3)):
        raise ValueError(f"phases must be 1 or 3, got {phases!r}")
    given = {}
    for key, val in (("length_in", length_in), ("width_in", width_in), ("height_in", height_in),
                     ("inlet_in", inlet_in)):
        if val is not None:
            given[key] = positive_finite(val, key[:-3], "inches")
    sheet = F.FactSheet(subject=f"fan-powered terminal unit, {kind} (archetype)")
    dims = {}
    nominal_l = NOMINAL_LENGTH_ELECTRIC_IN if reheat == "electric" else NOMINAL_LENGTH_IN
    for key, val, nom in (("length_in", length_in, nominal_l),
                          ("width_in", width_in, NOMINAL_WIDTH_IN),
                          ("height_in", height_in, NOMINAL_HEIGHT_IN),
                          ("inlet_in", inlet_in, NOMINAL_INLET_IN)):
        if val is None:
            sheet.set(key, nom, kind="nominal", source="class proportions (fan_powered.py)")
            dims[key] = nom
        else:
            dims[key] = given[key]
            sheet.set(key, dims[key], kind="given", source="the request")
    if voltage is None:
        voltage = 277.0
        sheet.set("voltage_v", voltage, kind="assumed",
                  source="277 V assumed (not stated; the common ECM-motor supply) -- state the "
                         "unit's nameplate voltage")
    else:
        voltage = float(voltage)
        sheet.set("voltage_v", voltage, kind="given", source="the request")
    if phases is None:
        phases = 1
        sheet.set("phases", phases, kind="assumed", source="single-phase assumed (not stated)")
    else:
        phases = int(phases)
        sheet.set("phases", phases, kind="given", source="the request")
    sheet.set("conduit_diameter_in", CONDUIT_NOMINAL_IN, kind="nominal",
              source="3/4 in, the common branch-circuit conduit trade size")
    sheet.set("manufacturer", "", kind="ours")
    sheet.set("model", "", kind="ours")
    L, W, H = dims["length_in"] * IN, dims["width_in"] * IN, dims["height_in"] * IN
    try:
        parts = fan_powered_parts(L, W, H, kind=kind, inlet_d=dims["inlet_in"] * IN, reheat=reheat)
        casing_only = None
    except ValueError as exc:
        if min(L, W, H) <= 0:
            raise
        parts = [{"shape": "box", "role": ROLE_CASING, "w": L, "d": W, "h": H, "z0": 0.0,
                  "cx": 0.0, "cy": 0.0}]
        casing_only = str(exc)

    v_txt = f"{voltage:g}V-{phases}Ph"
    heat = {"none": "", "hot_water": " - HW Reheat", "electric": " - Electric Reheat"}[reheat]
    fam_name = name or f"Fan Powered Terminal Unit - {kind.title()}{heat} - {v_txt}"
    doc = SK.new_family_document("mechanical_equipment", fam_name,
                                 part_type=SK.PART_TYPE["normal"], work_plane_based=False,
                                 start_id=start_id, plane_length_ft=max(6.0, L * 1.5),
                                 shared_params=shared_params)
    doc.notes.append(
        f"fan-powered terminal unit ({kind}): ceiling-hung; family origin = the casing bottom "
        f"centre (set the mounting height with the instance's offset); airflow +x (primary "
        f"inlet -x, discharge +x), service side +y (controls, electrical enclosure)")
    for dim in ("Length", "Width", "Height", "Inlet Diameter", "Conduit Diameter"):
        F._num(doc, dim, "length", "dimensions" if dim != "Conduit Diameter" else "electrical")
    F._num(doc, "Voltage", "voltage", "electrical")
    F._num(doc, "Number of Phases", "integer", "electrical")
    F._text(doc, "Fan Configuration")
    F._text(doc, "Reheat")
    rows: List[Any] = []
    F._add_type_row(doc, rows, f"{kind.title()} - {dims['inlet_in']:g} in Inlet{heat} - {v_txt}", sheet, [
        ("Length", "length", dims["length_in"]), ("Width", "length", dims["width_in"]),
        ("Height", "length", dims["height_in"]), ("Inlet Diameter", "length", dims["inlet_in"]),
        ("Conduit Diameter", "length", CONDUIT_NOMINAL_IN),
        ("Voltage", "voltage", float(voltage)), ("Number of Phases", "integer", int(phases)),
        ("Fan Configuration", "text", kind.title()),
        ("Reheat", "text", {"none": "None", "hot_water": "Hot Water", "electric": "Electric"}[reheat]),
    ], description=(f"fan-powered terminal unit, {kind}, {dims['length_in']:g} L x "
                    f"{dims['width_in']:g} W x {dims['height_in']:g} H in casing, "
                    f"{dims['inlet_in']:g} in primary inlet (nominal class proportions, no "
                    f"manufacturer), {v_txt}{heat.replace(' - ', ', ')}"))
    forms: List[Any] = []
    host_el = host_case = None
    arcs = arcs_available()
    if not arcs and any(p["shape"] != "box" for p in parts):
        doc.notes.append("round parts (inlet, reheat stubs, conduit hub) drawn SQUARE: this "
                         "release's class map has no ArcElemCell (#786) -- same size and place")
    for p in parts:
        if p["shape"] != "box" and not arcs:
            p = square_round_part(p)
        if p["shape"] == "box":
            f = F.add_box_form(doc, p["w"], p["d"], p["h"], base_z_ft=p["z0"],
                               center=(p["cx"], p["cy"]), rep=G.REP_SOLID)
            f.params.update({"width_ft": p["w"], "depth_ft": p["d"], "height_ft": p["h"],
                             "base_z_ft": p["z0"], "center": (p["cx"], p["cy"])})
        elif p["shape"] == "cylinder":
            f = F.add_cylinder_form(doc, p["r"], p["h"], base_z_ft=p["z0"], center=(p["cx"], p["cy"]))
        else:
            f = F.add_generic_part(doc, {"shape": p["shape"], "radius_ft": p["r"],
                                         "length_ft": p["length"], "base_z_ft": p["zc"] - p["r"],
                                         "center": (p["cx"], p["cy"])})
        f.params.update({"role": p["role"]})
        if p["role"] == ROLE_ELECTRICAL:
            host_el = (f, p)
        if p["role"] == ROLE_CASING:
            host_case = (f, p)
        forms.append(f)
    if casing_only:
        doc.notes.append(f"terminal unit hardware NOT drawn ({casing_only}): the casing is "
                         f"delivered alone, its power and conduit connectors on its service (+y) side")
    else:
        doc.notes.append(
            f"terminal unit detail at NOMINAL class proportions (no manufacturer drawing): "
            f"{kind} casing {dims['length_in']:g} x {dims['width_in']:g} x {dims['height_in']:g} in, "
            f"{dims['inlet_in']:g} in primary inlet with damper actuator, induction opening "
            f"filter, discharge collar"
            + {"none": "", "hot_water": ", hot-water reheat coil with supply / return stubs",
               "electric": ", electric heater control panel"}[reheat]
            + ", controls and electrical enclosures (toggle disconnect, conduit hub), 4 hanger "
              "brackets")
    if casing_only:
        doc.notes.append("pipe / duct connectors are NOT authored (#894), and with the hardware "
                         "left out there are no inlet, discharge or induction openings to draw to")
    else:
        doc.notes.append("pipe / duct connectors are NOT authored (no corpus specimen pins their "
                         "system, #894): the inlet, discharge"
                         + (", induction and reheat" if reheat == "hot_water" else " and induction")
                         + " openings are geometry -- draw duct and pipe to them by eye")
    if host_el is not None:
        fel, pe = host_el
        loc = (pe["cx"], pe["cy"], pe["z0"] + pe["h"])
    else:
        fel, pe = host_case
        loc = (0.0, pe["cy"] + pe["d"] / 2 - min(2.0 * IN, pe["d"] / 4), pe["z0"] + pe["h"])
    poles = poles_for(voltage, phases)
    F.add_connector(doc, host=fel, face="top", location=loc, direction=(0.0, 0.0, 1.0),
                    u_axis=(1.0, 0.0, 0.0), voltage_v=float(voltage), poles=poles,
                    apparent_load_va=0.0, power_factor=1.0, bind_voltage_param="Voltage",
                    load_class="Power", description="Unit Power (electrical enclosure)")
    MC.add_conduit_connector(doc, host=fel, face="top", location=loc, direction=(0.0, 0.0, 1.0),
                             u_axis=(1.0, 0.0, 0.0), diameter_ft=CONDUIT_NOMINAL_IN * IN,
                             bind_diameter_param="Conduit Diameter", description="Feeder Conduit")
    doc.notes.append(f"power connector ({poles} pole(s), {voltage:g} V {phases}-phase, apparent "
                     f"load 0 VA: the fan motor's nameplate load is not known -- enter it) and the "
                     f"feeder's conduit connector ({CONDUIT_NOMINAL_IN:g} in NOMINAL, driven by "
                     f"'Conduit Diameter') on the {'electrical enclosure' if host_el else 'casing'}'s top")
    vtg = voltage_to_ground if voltage_to_ground is not None else voltage_to_ground_for(voltage, phases)
    try:
        ws = CL.working_space(equipment_width_ft=pe["w"] if host_el else L, equipment_height_ft=H,
                              voltage_to_ground=vtg)
    except CL.ClearanceError as exc:
        doc.notes.append(f"clearance zone NOT drawn: {exc}")
        ws = None
    if ws is not None:
        y0 = max(p["cy"] + p["d"] / 2 for p in parts if p["shape"] == "box"
                 and p["role"] in (ROLE_ELECTRICAL, "disconnect toggle")) if host_el else W / 2
        add_working_zone(doc, forms, ws, H, y0, pe["cx"] if host_el else 0.0,
                         "electrical enclosure" if host_el else "service side", vtg)
        if voltage_to_ground is None:
            note_voltage_to_ground(doc, vtg, voltage, phases)
    std = ST.apply_safe(doc, "mechanical_equipment", standards, None)
    doc.finalize()
    return F.FamilyProduct("fan_powered_box", doc, sheet, forms=forms, types=rows, standards=std,
                           file_stem=F._slug(f"fan_powered_{kind}_{dims['inlet_in']:g}in_{reheat}_{v_txt}"))

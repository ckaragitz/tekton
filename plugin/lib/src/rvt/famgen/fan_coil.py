"""fan_coil -- a HORIZONTAL CONCEALED FAN COIL UNIT with a unit-mounted disconnect,
built from its real parts (owner steer #891: "learn how to build anything ... do your
research about fan coil units").

THE ANATOMY (standard practice for the class, from public installation / product
literature read for this module -- anatomy and class proportions only; no
manufacturer's dimension is carried):

* a sheet-metal CABINET hung above the ceiling, about 10-11 in high and about 2 ft
  deep in the airflow direction; its LENGTH grows with the unit's airflow
  (roughly 200 - 1200 cfm classes);
* air enters a RETURN opening at the back, through a FILTER rack, and leaves a
  rectangular SUPPLY duct collar at the front (airflow +x here);
* a removable BOTTOM ACCESS PANEL for the fan, motor and filter;
* the COIL CONNECTIONS (3/4 in supply and return) and the sloped DRAIN PAN's
  condensate outlet on one end (here -y, "the piping end");
* the ELECTRICAL end opposite the coil connections: the unit CONTROL BOX, and here
  the unit-mounted fused DISCONNECT SWITCH the schedule names (30 A frame / 15 A
  fuses), its feeder entering through a conduit hub on top (7/8 in knockouts);
* four HANGER BRACKETS for the threaded rods.

Every dimension is ``nominal`` (S-2026-08-10-e) unless the caller gives it: the
class proportions above, never a manufacturer's drawing, model or part number.

WHAT THE FILE DOES NOT CARRY YET: hydronic (pipe) and duct CONNECTORS -- the writer
authors electrical connectors only, so the coil, drain and duct connections are
geometry, said in the notes.  The unit's one electrical connector sits on the
disconnect.  "Behaves in Revit" is claimed only with a desktop verdict (hard rule 4).

Clearance: the NEC 110.26(A) working space in front of the DISCONNECT's face, 
toggleable and magenta like every equipment family (steer #882 / #884).  A
ceiling-hung unit does not know where the floor is, so the zone is drawn the unit's
height tall and the note says so (above a suspended ceiling, 110.26(A)(4) limited
access governs).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

IN = 1.0 / 12.0

#: nominal cabinet for the class (a ~400 cfm unit): length (y) x depth (x, airflow) x height
NOMINAL_LENGTH_IN = 42.0
NOMINAL_DEPTH_IN = 23.0
NOMINAL_HEIGHT_IN = 10.5

ROLE_CABINET = "fan coil cabinet"


def fan_coil_parts(L: float, D: float, H: float) -> List[Dict[str, Any]]:
    """The parts (feet).  Cabinet centred on the origin in plan, bottom at z = 0;
    airflow +x (return at -x, supply at +x); piping end -y, electrical end +y.
    Boxes: ``{"shape": "box", role, w (x), d (y), h, z0, cx, cy}``; cylinders along y:
    ``{"shape": "cylinder_y", role, r, length, zc, cx, cy}``; vertical cylinders:
    ``{"shape": "cylinder", role, r, h, z0, cx, cy}``."""
    if min(L, D, H) <= 0:
        raise ValueError(f"fan coil cabinet must be positive, got {L} x {D} x {H}")
    if H < 7 * IN or D < 14 * IN or L < 24 * IN:
        raise ValueError("a fan coil cabinet under 24 in long, 14 in deep or 7 in high has "
                         "no room for its end hardware")

    def box(role, w, d, h, z0, cx=0.0, cy=0.0):
        return {"shape": "box", "role": role, "w": w, "d": d, "h": h, "z0": z0, "cx": cx, "cy": cy}

    y_pipe, y_elec = -L / 2, L / 2
    parts = [box(ROLE_CABINET, D, L, H, 0.0)]
    # supply duct collar (front, +x) and return filter rack (back, -x)
    parts.append(box("supply duct collar", 1.5 * IN, L - 8 * IN, H - 3 * IN, 1.5 * IN,
                     D / 2 + 0.75 * IN, 0.0))
    parts.append(box("return filter rack", 2.0 * IN, L - 8 * IN, H - 1.5 * IN, 0.75 * IN,
                     -D / 2 - 1.0 * IN, 0.0))
    # bottom access panel (fan / motor / filter service), proud of the bottom by 1/8 in
    parts.append(box("bottom access panel", D - 2 * IN, L - 8 * IN, 0.125 * IN, -0.125 * IN))
    # hanger brackets: on the front and back faces, near the ends, at the top
    for sx in (-1, 1):
        for sy in (-1, 1):
            parts.append(box("hanger bracket", 1.5 * IN, 2.0 * IN, 1.5 * IN, H - 1.5 * IN,
                             sx * (D / 2 + 0.75 * IN), sy * (L / 2 - 1.25 * IN)))
    # piping end (-y): coil supply / return stubs toward the back, the drain low
    r_pipe = 0.4375 * IN                                   # 3/4 in copper, 7/8 in OD
    for role, x, zc in (("coil supply connection", -D / 2 + 4.0 * IN, 0.35 * H),
                        ("coil return connection", -D / 2 + 7.0 * IN, 0.70 * H)):
        parts.append({"shape": "cylinder_y", "role": role, "r": r_pipe, "length": 3.0 * IN,
                      "zc": zc, "cx": x, "cy": y_pipe - 1.5 * IN})
    parts.append({"shape": "cylinder_y", "role": "condensate drain connection", "r": 0.525 * IN,
                  "length": 2.0 * IN, "zc": 1.25 * IN, "cx": D / 2 - 4.0 * IN,
                  "cy": y_pipe - 1.0 * IN})
    # electrical end (+y): control box toward the back, the fused disconnect toward the front
    cb_w, cb_d, cb_h = 7.0 * IN, 3.5 * IN, H - 3.0 * IN
    parts.append(box("unit control box", cb_w, cb_d, cb_h, 1.5 * IN, -D / 2 + 1.0 * IN + cb_w / 2,
                     y_elec + cb_d / 2))
    ds_w, ds_d, ds_h = 6.5 * IN, 4.25 * IN, min(9.5 * IN, H - 1.0 * IN)
    ds_x = D / 2 - 1.0 * IN - ds_w / 2
    ds_z0 = (H - ds_h) / 2
    parts.append(box("fused disconnect switch", ds_w, ds_d, ds_h, ds_z0, ds_x, y_elec + ds_d / 2))
    face = y_elec + ds_d                                    # the disconnect's working face
    hz = ds_z0 + ds_h / 2 - 1.25 * IN
    parts.append(box("disconnect operating handle", 0.75 * IN, 1.25 * IN, 2.5 * IN, hz,
                     ds_x + ds_w / 2 - 1.0 * IN, face + 0.625 * IN))
    parts.append(box("disconnect rating label", 2.5 * IN, 0.06 * IN, 1.0 * IN,
                     ds_z0 + ds_h - 2.0 * IN, ds_x - 0.75 * IN, face + 0.03 * IN))
    parts.append({"shape": "cylinder", "role": "disconnect conduit hub", "r": 0.55 * IN,
                  "h": min(0.75 * IN, H - (ds_z0 + ds_h)) or 0.25 * IN, "z0": ds_z0 + ds_h,
                  "cx": ds_x, "cy": y_elec + ds_d / 2})
    return parts


def front_of_disconnect(parts: List[Dict[str, Any]]) -> float:
    """The y of the frontmost disconnect hardware (where its working space starts)."""
    ys = [p["cy"] + p["d"] / 2 for p in parts
          if p["shape"] == "box" and p["role"].startswith(("fused disconnect", "disconnect"))]
    return max(ys)


def make_fan_coil_unit(*, length_in: Optional[float] = None, depth_in: Optional[float] = None,
                       height_in: Optional[float] = None, voltage: float = 208.0,
                       phases: int = 1, disconnect_frame_a: float = 30.0,
                       disconnect_fuse_a: float = 15.0, fused: bool = True,
                       voltage_to_ground: Optional[float] = None,
                       name: Optional[str] = None, start_id: int = 1000,
                       shared_params: Any = None, standards: bool = True):
    """Compose the fan coil family (see the module docstring).  Dimensions left
    ``None`` are the class nominals; the disconnect's ratings are the schedule's
    (30 A frame / 15 A fuses by default, the owner's request), the voltage an
    assumption unless given (208 V single-phase, stated)."""
    from . import factory as F
    from . import geometry as G
    from . import skeleton as SK
    from . import standards as ST
    from . import equipment_clearance as EC
    from . import clearance as CL

    sheet = F.FactSheet(subject="fan coil unit, horizontal concealed (archetype)")
    dims = {}
    for key, val, nom in (("length_in", length_in, NOMINAL_LENGTH_IN),
                          ("depth_in", depth_in, NOMINAL_DEPTH_IN),
                          ("height_in", height_in, NOMINAL_HEIGHT_IN)):
        if val is None:
            sheet.set(key, nom, kind="nominal", source="class proportions (fan_coil.py)")
            dims[key] = nom
        else:
            sheet.set(key, float(val), kind="given", source="the request")
            dims[key] = float(val)
    sheet.set("voltage_v", float(voltage), kind="assumed" if voltage == 208.0 else "given",
              source="208 V single-phase assumed -- state the unit's nameplate voltage")
    sheet.set("phases", int(phases), kind="assumed" if phases == 1 else "given")
    sheet.set("disconnect_frame_a", float(disconnect_frame_a), kind="given", source="the request (30AF)")
    sheet.set("disconnect_fuse_a", float(disconnect_fuse_a), kind="given", source="the request (15AS)")
    sheet.set("manufacturer", "", kind="ours")
    sheet.set("model", "", kind="ours")
    L, D, H = dims["length_in"] * IN, dims["depth_in"] * IN, dims["height_in"] * IN
    parts = fan_coil_parts(L, D, H)

    v_txt = f"{voltage:g}V-{phases}Ph"
    sw = f"{disconnect_frame_a:g}AF-{disconnect_fuse_a:g}AS" if fused else f"{disconnect_frame_a:g}A NF"
    fam_name = name or f"Fan Coil Unit - Horizontal Concealed - {v_txt} - {sw} Disconnect"
    doc = SK.new_family_document("mechanical_equipment", fam_name,
                                 part_type=SK.PART_TYPE["normal"], work_plane_based=False,
                                 start_id=start_id, plane_length_ft=max(6.0, L * 1.5),
                                 shared_params=shared_params)
    doc.notes.append(
        "fan coil unit: horizontal concealed, ceiling-hung; family origin = the cabinet "
        "bottom centre (set the mounting height with the instance's offset); airflow +x "
        "(return -x, supply +x), coil connections and drain on the -y end, control box "
        "and disconnect on the +y end (opposite the coil connections, standard practice)")
    for dim in ("Length", "Width", "Height"):
        F._num(doc, dim, "length", "dimensions")
    F._num(doc, "Voltage", "voltage", "electrical")
    F._num(doc, "Number of Phases", "integer", "electrical")
    F._num(doc, "Disconnect Frame Rating", "current", "electrical")
    F._num(doc, "Disconnect Fuse Rating", "current", "electrical")
    F._text(doc, "Disconnect Type", "electrical")
    F._text(doc, "Disconnect Enclosure", "electrical")
    F._text(doc, "Coil Configuration")
    F._text(doc, "Connection Hand")
    rows: List[Any] = []
    type_name = f"Nominal {dims['length_in']:g} in - {v_txt} - {sw}"
    F._add_type_row(doc, rows, type_name, sheet, [
        ("Length", "length", dims["length_in"]), ("Width", "length", dims["depth_in"]),
        ("Height", "length", dims["height_in"]),
        ("Voltage", "voltage", float(voltage)), ("Number of Phases", "integer", int(phases)),
        ("Disconnect Frame Rating", "current", float(disconnect_frame_a)),
        ("Disconnect Fuse Rating", "current", float(disconnect_fuse_a) if fused else 0.0),
        ("Disconnect Type", "text", "Fused Disconnect Switch" if fused else "Non-Fused Disconnect Switch"),
        ("Disconnect Enclosure", "text", "NEMA 1 (nominal)"),
        ("Coil Configuration", "text", "2-pipe (nominal)"),
        ("Connection Hand", "text", "coil connections -y end, electrical +y end (nominal)"),
    ], description=(f"horizontal concealed fan coil unit, {dims['length_in']:g} L x "
                    f"{dims['depth_in']:g} D x {dims['height_in']:g} H in cabinet (nominal class "
                    f"proportions, no manufacturer), {v_txt}, unit-mounted "
                    f"{'fused' if fused else 'non-fused'} disconnect {sw}"))
    forms: List[Any] = []
    host_disc = None
    for p in parts:
        if p["shape"] == "box":
            f = F.add_box_form(doc, p["w"], p["d"], p["h"], base_z_ft=p["z0"],
                               center=(p["cx"], p["cy"]), rep=G.REP_SOLID)
        elif p["shape"] == "cylinder":
            f = F.add_cylinder_form(doc, p["r"], p["h"], base_z_ft=p["z0"],
                                    center=(p["cx"], p["cy"]))
        else:
            f = F.add_generic_part(doc, {"shape": "cylinder_y", "radius_ft": p["r"],
                                         "length_ft": p["length"], "base_z_ft": p["zc"] - p["r"],
                                         "center": (p["cx"], p["cy"])})
        f.params.update({"role": p["role"]})
        if p["shape"] == "box":
            f.params.update({"width_ft": p["w"], "depth_ft": p["d"], "height_ft": p["h"],
                             "base_z_ft": p["z0"], "center": (p["cx"], p["cy"])})
        if p["role"] == "fused disconnect switch":
            host_disc = (f, p)
        forms.append(f)
    doc.notes.append(
        f"fan coil detail at NOMINAL class proportions (no manufacturer drawing): cabinet "
        f"{dims['length_in']:g} x {dims['depth_in']:g} x {dims['height_in']:g} in, supply duct "
        f"collar, return filter rack, bottom access panel, 4 hanger brackets, 3/4 in coil "
        f"supply / return and condensate drain stubs, unit control box, unit-mounted "
        f"{'fused' if fused else 'non-fused'} disconnect ({sw}) with handle, rating label and "
        f"conduit hub")
    doc.notes.append("pipe / duct connectors are NOT authored (the writer authors electrical "
                     "connectors only): the coil, drain and duct connections are geometry -- "
                     "draw pipe and duct to them by eye")
    # the one electrical connector: on the disconnect's top, where the feeder enters
    fdisc, pd = host_disc
    poles = 2 if phases == 1 and voltage > 150 else (1 if phases == 1 else 3)
    F.add_connector(doc, host=fdisc, face="top",
                    location=(pd["cx"], pd["cy"], pd["z0"] + pd["h"]),
                    direction=(0.0, 0.0, 1.0), u_axis=(1.0, 0.0, 0.0),
                    voltage_v=float(voltage), poles=poles, apparent_load_va=0.0,
                    power_factor=1.0, bind_voltage_param="Voltage", load_class="Power",
                    description="Unit Power (at the disconnect)")
    doc.notes.append("power connector on the disconnect's top (the conduit hub), apparent "
                     "load 0 VA: the motor's nameplate load is not known -- enter it")
    # clearance: the 110.26(A) working space in front of the disconnect, toggleable
    vtg = voltage_to_ground if voltage_to_ground is not None else (120.0 if voltage <= 240 else 277.0)
    ws = CL.working_space(equipment_width_ft=pd["w"], equipment_height_ft=H,
                          voltage_to_ground=vtg)
    y0 = front_of_disconnect(parts)
    zone = F.add_box_form(doc, ws.width_ft, ws.depth_ft, H, base_z_ft=0.0,
                          center=(pd["cx"], y0 + ws.depth_ft / 2.0))
    zone.params.update({"role": "clearance: front working space", "source": ws.source,
                        "width_ft": ws.width_ft, "depth_ft": ws.depth_ft, "height_ft": H,
                        "base_z_ft": 0.0, "center": (pd["cx"], y0 + ws.depth_ft / 2.0)})
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
        f"clearance zone (steer #882): working space in front of the disconnect, "
        f"{ws.depth_ft:g} ft deep x {ws.width_ft * 12:g} in wide ({ws.source}; {ws.status}; "
        f"{vtg:g} V to ground) -- drawn the UNIT's height, not 6 1/2 ft from the floor: a "
        f"ceiling-hung family does not know the floor, and above a suspended ceiling NEC "
        f"110.26(A)(4) (limited access) governs; shown by '{EC.P_SHOW}' and '{EC.P_FRONT}', "
        f"bound to its visibility -- NOT yet verified in Revit (hard rule 4)")
    for k, v in ws.assumed.items():
        doc.notes.append(f"clearance assumption -- {k}: {v}")
    if voltage_to_ground is None:
        doc.notes.append(f"clearance assumption -- voltage_to_ground: {vtg:g} V (from the "
                         f"{voltage:g} V supply) -- state it if the system differs")
    std = ST.apply_safe(doc, "mechanical_equipment", standards, None)
    doc.finalize()
    prod = F.FamilyProduct("fan_coil_unit", doc, sheet, forms=forms, types=rows, standards=std,
                           file_stem=F._slug(f"fan_coil_horizontal_{dims['length_in']:g}in_"
                                             f"{v_txt}_{sw}"))
    return prod

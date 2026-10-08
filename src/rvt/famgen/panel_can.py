"""panel_can -- a panelboard modelled as its BACK BOX and COVER (#1047, steer #1046).

WHY A SECOND PANELBOARD.  ``factory.make_panelboard`` draws the cabinet a user
sees once the job is done: a solid enclosure with trim, a hinged door, hinges,
a latch and a nameplate (#892).  A prefabrication / rough-in library models the
same product the way it is installed: an open-front **back box** ("can") set at
a mounting height, and a **cover** that is surface-mounted (the size of the box)
or flush (lapping the wall opening), with the NEC working space in front and the
dedicated space above, each switchable.  The owner's reference panelboard is
built that way (measured privately, counts only -- the reference stays in the
git-ignored ``samples/``; S-2026-09-23-b: built the same way, never copied).

WHAT IS BUILT (every name below is OURS; a user's library names arrive only
through their own parameter profile at build time, #1048):

* the back box from five plates -- back, two sides, bottom, top -- of wall
  thickness ``Box Thickness``, open at the front.  (The reference cuts one box
  solid with a void; void extrusions are #1049.  The plates look the same from
  every side and resize the same way.)
* the cover, ``Box Thickness`` thick on the box front: the box's size when
  ``Surface Cover`` is on, :data:`FLUSH_LAP_IN` larger on every side when it is
  off (``Flush Cover`` = ``not(Surface Cover)``), shown by ``Show Cover``.
  ``Cover Width`` / ``Cover Height`` / ``Cover Offset`` are formulas of the
  switch and label the cover's own dimensions.
* the clearance zones of :mod:`rvt.famgen.equipment_clearance` (#882): the
  110.26(A) working space in front of the cover, measured from the floor, and the
  110.26(E)(1) dedicated space above the box, with their Yes/No switches.
* the electrical circuiting parameters a connector reads -- ``Voltage``,
  ``Number of Poles`` (Revit's number-of-poles storage), ``Power Factor``,
  ``Apparent Load``, ``Load Classification`` (a load-classification parameter,
  not text) and ``Motor`` -- each ASSOCIATED to the power connector on the box
  top; and two round conduit connectors, on the box top and bottom.
* section-header rows (text parameters whose formula is their own label), so the
  properties palette reads in sections.
* ``Width`` / ``Height`` / ``Depth`` / ``Mounting Height`` (per instance) drive
  the box, the cover rides its front, the zones ride the box (drive / height
  laws, #914 / #787) -- every drive all-or-nothing, a refusal a note.

Nothing here claims behaviour in Revit -- the cover switch, the zone switches and
the resizing are claims only a desktop verdict makes (hard rule 4).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import factory as F
from . import geometry as G
from . import param_binding as PB
from . import skeleton as SK
from . import standards as ST

#: the back box's wall (and the cover's) thickness: 10 gauge-class sheet steel,
#: 1/8 in nominal -- ours, overridable
BOX_THICKNESS_IN = 0.125
#: how far a FLUSH cover laps the wall opening on every side (in)
FLUSH_LAP_IN = 0.5
#: the box top's height above the floor when nothing says otherwise: the top
#: breaker handle at the 6 ft 7 in of NEC 240.24(A) less trim -- 78 in, the
#: archetype lane's mounting rule (``archetypes.MOUNT_TOP_IN``)
MOUNT_TOP_IN = 78.0
#: the conduit connectors' nominal size (a 2 in trade-size entry), ours
CONDUIT_IN = 2.0

#: connector properties a family parameter drives (the power connector's), as the
#: owner's reference library binds them (private census, counts only: poles 21 /
#: 21 to a number-of-poles parameter, voltage 24, power factor 21, load class 21 to
#: a load-classification parameter, apparent load 21 of 23 to -1140004 -- not the
#: -1140005 ``skeleton.ELEM_PROP_APPARENT_LOAD`` holds, which 2 bind)
ELEM_PROP_POLES = -1140001
ELEM_PROP_VOLTAGE = -1140002
ELEM_PROP_APPARENT_LOAD = -1140004
ELEM_PROP_POWER_FACTOR = -1140008
ELEM_PROP_LOAD_CLASS = -1140014

GROUP_CIRCUITING = "autodesk.parameter.group:electricalCircuiting-1.0.0"
GROUP_VISIBILITY = "autodesk.parameter.group:visibility-1.0.0"

#: our parameter names
P_WIDTH, P_HEIGHT, P_DEPTH = "Width", "Height", "Depth"
P_MOUNT = "Mounting Height"
P_THICK = "Box Thickness"
P_SURFACE, P_FLUSH, P_SHOW_COVER = "Surface Cover", "Flush Cover", "Show Cover"
P_COVER_W, P_COVER_H, P_COVER_Z = "Cover Width", "Cover Height", "Cover Offset"
P_VOLTAGE, P_POLES, P_PF = "Voltage", "Number of Poles", "Power Factor"
P_LOAD, P_LOAD_CLASS, P_MOTOR = "Apparent Load", "Load Classification", "Motor"
P_MIN_CLW, P_CLW = "Minimum Clearance Width", "Clearance Width"
P_FRONT_DEPTH, P_TOP_H = "Front Clearance Depth", "Top Clearance Height"
P_TO_FLOOR, P_FRONT_H = "Front Clearance To Floor", "Front Clearance Height"
#: the working space's minimum width, NEC 110.26(A)(2): the equipment's width or
#: 30 in, whichever is greater (a code minimum, cited by article -- never NFPA text)
MIN_CLEARANCE_WIDTH_IN = 30.0
#: section headers: (parameter, palette group) -- a text parameter whose formula
#: is its own label
HEADERS = (("--- Identity ---", SK.PGROUP_CONSTRAINTS),
           ("--- Dimensions ---", SK.PGROUP_CONSTRAINTS),
           ("--- Cover ---", SK.PGROUP_CONSTRAINTS),
           ("--- Clearance Zones ---", SK.PGROUP_CONSTRAINTS))


class PanelCanError(ValueError):
    """The request cannot be built (a size that leaves no box inside its walls)."""


def _in(v: float) -> float:
    return float(v) / 12.0


def _lit(inches: float) -> str:
    """A length literal in a formula, in feet (``0.0416666666666667'``)."""
    return f"{float(inches) / 12.0:.15g}'"


def cover_formulas() -> Dict[str, str]:
    """The cover's size and placement as formulas of the surface switch: a surface
    cover is the box; a flush one laps the opening by :data:`FLUSH_LAP_IN` on every
    side, so it is ``2 x lap`` wider and taller and starts ``lap`` lower."""
    lap2, lap = _lit(2 * FLUSH_LAP_IN), _lit(FLUSH_LAP_IN)
    return {P_COVER_W: f"if({P_SURFACE}, {P_WIDTH}, {P_WIDTH} + {lap2})",
            P_COVER_H: f"if({P_SURFACE}, {P_HEIGHT}, {P_HEIGHT} + {lap2})",
            P_COVER_Z: f"if({P_SURFACE}, {P_MOUNT}, {P_MOUNT} - {lap})"}


def _plates(W: float, D: float, H: float, t: float, z0: float
            ) -> List[Tuple[str, float, float, float, float, Tuple[float, float]]]:
    """``(name, w, d, h, base_z, (cx, cy))`` of the five back-box plates: the box
    spans x -W/2..W/2, y 0..D (back on the wall plane y = 0), z z0..z0+H."""
    return [
        ("back", W, t, H, z0, (0.0, t / 2.0)),
        ("left side", t, D, H, z0, (-W / 2.0 + t / 2.0, D / 2.0)),
        ("right side", t, D, H, z0, (W / 2.0 - t / 2.0, D / 2.0)),
        ("bottom", W, D, t, z0, (0.0, D / 2.0)),
        ("top", W, D, t, z0 + H - t, (0.0, D / 2.0)),
    ]


def make_panel_can(*, vendor: str = "eaton", line: str = "pow-r-line",
                   mains_a: float = 225, spaces: int = 42, voltage: Any = "208Y/120",
                   mcb: bool = False, panel_name: str = "PANEL",
                   width_in: Optional[float] = None, height_in: Optional[float] = None,
                   depth_in: Optional[float] = None,
                   mounting_height_in: Optional[float] = None,
                   surface: bool = True, name: Optional[str] = None,
                   start_id: int = 1000, shared_params: SK.SharedParamsArg = None,
                   standards: bool = True, drive: bool = True) -> "F.FamilyProduct":
    """A panelboard as its back box and cover (see the module doc).

    The box size is the catalog's (``vendor`` / ``line`` / ``mains_a`` / ``spaces``,
    as :func:`rvt.famgen.factory.make_panelboard`) unless ``width_in`` /
    ``height_in`` / ``depth_in`` say otherwise (then ``given``).
    ``mounting_height_in`` = the box bottom above the floor; default: the box top at
    :data:`MOUNT_TOP_IN` (``nominal``).  ``surface`` = the cover switch's value.
    """
    facts = F.resolve_panelboard_facts(vendor, line, mains_a=float(mains_a),
                                       spaces=int(spaces), voltage=voltage, mcb=bool(mcb),
                                       mounting="surface" if surface else "flush",
                                       panel_name=panel_name)
    given: List[str] = []
    dims = {}
    for key, val, fact in (("width_in", width_in, facts.get("width_in")),
                           ("height_in", height_in, facts.get("height_in")),
                           ("depth_in", depth_in, facts.get("depth_in"))):
        if val is not None:
            given.append(key)
        dims[key] = float(val if val is not None else fact)
    W, H, D = _in(dims["width_in"]), _in(dims["height_in"]), _in(dims["depth_in"])
    t = _in(BOX_THICKNESS_IN)
    if min(W, H, D) <= 4 * t:
        raise PanelCanError(f"a {dims['width_in']:g} x {dims['height_in']:g} x "
                            f"{dims['depth_in']:g} in box leaves nothing inside "
                            f"{BOX_THICKNESS_IN:g} in walls")
    mh_in = (float(mounting_height_in) if mounting_height_in is not None
             else max(0.0, MOUNT_TOP_IN - dims["height_in"]))
    MH = _in(mh_in)
    vll = float(facts.get("voltage_ll_v"))
    poles = 3 if int(facts.get("phases")) >= 3 else 1
    fam_name = name or F._clean_name("Panelboard Box and Cover", facts.get("voltage_system"),
                                     f"{int(mains_a)}A", f"{int(spaces)}ckt")
    doc = SK.new_family_document("electrical_equipment", fam_name,
                                 part_type=SK.PART_TYPE["panelboard"],
                                 work_plane_based=False, start_id=start_id,
                                 plane_length_ft=max(8.0, (MH + H) * 1.5),
                                 shared_params=shared_params)
    # the ONE type, first: every parameter added below registers its value on it
    # (a parameter added before any type row exists keeps no value at all)
    doc.add_type(F._clean_name(f"{int(mains_a)}A", facts.get("mains_type"), f"{int(spaces)}ckt"),
                 {"manufacturer": str(facts.get("manufacturer")),
                  "model": str(facts.get("model")),
                  "description": (f"{facts.get('voltage_system')} V panelboard back box and "
                                  f"cover, {int(mains_a)} A, {int(spaces)} circuits (box "
                                  f"{dims['width_in']:g} W x {dims['height_in']:g} H x "
                                  f"{dims['depth_in']:g} D in)")})

    # -- parameters ----------------------------------------------------------
    for hdr, grp in HEADERS:
        doc.add_family_parameter(hdr, SK.SPEC_TEXT, grp, is_instance=True,
                                 formula=f'"{hdr}"', default=hdr)
    for cap, val in ((P_WIDTH, W), (P_HEIGHT, H), (P_DEPTH, D), (P_MOUNT, MH)):
        doc.add_family_parameter(cap, SK.SPEC_LENGTH, SK.PGROUP_CONSTRAINTS,
                                 is_instance=True, default=val)
    doc.add_family_parameter(P_THICK, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                             formula=_lit(BOX_THICKNESS_IN), default=t)
    doc.add_family_parameter(P_SURFACE, SK.SPEC_YESNO, SK.PGROUP_CONSTRAINTS,
                             is_instance=True, default=1 if surface else 0)
    doc.add_family_parameter(P_FLUSH, SK.SPEC_YESNO, SK.PGROUP_CONSTRAINTS,
                             is_instance=True, formula=f"not({P_SURFACE})",
                             default=0 if surface else 1)
    show_cover = doc.add_family_parameter(P_SHOW_COVER, SK.SPEC_YESNO, SK.PGROUP_CONSTRAINTS,
                                          is_instance=True, default=1)
    lap = _in(FLUSH_LAP_IN)
    CW, CH, CZ = (W, H, MH) if surface else (W + 2 * lap, H + 2 * lap, MH - lap)
    for cap, val in ((P_COVER_W, CW), (P_COVER_H, CH), (P_COVER_Z, CZ)):
        doc.add_family_parameter(cap, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                 is_instance=True, formula=cover_formulas()[cap], default=val)
    # electrical circuiting: the values the power connector reads
    doc.add_family_parameter(P_VOLTAGE, SK.SPEC_VOLTAGE, GROUP_CIRCUITING,
                             default=SK.volts(vll))
    poles_p = doc.add_family_parameter(P_POLES, SK.SPEC_INTEGER, GROUP_CIRCUITING,
                                       default=int(poles))
    _as_number_of_poles(poles_p)
    doc.add_family_parameter(P_PF, SK.SPEC_NUMBER, GROUP_CIRCUITING, default=1.0)
    doc.add_family_parameter(P_LOAD, SK.SPEC_APPARENT_POWER, GROUP_CIRCUITING,
                             is_instance=True, default=0.0)
    doc.add_family_parameter(P_MOTOR, SK.SPEC_YESNO, GROUP_CIRCUITING, is_instance=True,
                             default=0)

    # -- geometry --------------------------------------------------------------
    named: List[Tuple[str, Any]] = []
    for nm, w, d, h, z, c in _plates(W, D, H, t, MH):
        fb = F.add_box_form(doc, w, d, h, base_z_ft=z, center=c)
        fb.params.update({"role": f"back box: {nm}"})
        named.append((nm, fb))
    cover = F.add_box_form(doc, CW, t, CH, base_z_ft=CZ, center=(0.0, D + t / 2.0))
    cover.params.update({"role": "cover"})
    PB.bind_visibility(cover, show_cover)
    named.append(("cover", cover))
    plates = dict(named)

    # -- connectors: power on the box top, conduit on the top and bottom -------
    con = F.add_connector(doc, host=plates["top"], face="top", location=(0.0, D / 2.0, MH + H),
                          direction=(0.0, 0.0, 1.0), u_axis=(1.0, 0.0, 0.0),
                          voltage_v=vll, poles=poles, apparent_load_va=0.0,
                          power_factor=1.0, bind_voltage_param=P_VOLTAGE,
                          load_class="Power", description="Panel Feed")
    lc_param = _load_class_parameter(doc, con)
    PB.bind(con, doc.params[P_LOAD], ELEM_PROP_APPARENT_LOAD)
    PB.bind(con, doc.params[P_POLES], ELEM_PROP_POLES)
    PB.bind(con, doc.params[P_PF], ELEM_PROP_POWER_FACTOR)
    if lc_param is not None:
        PB.bind(con, lc_param, ELEM_PROP_LOAD_CLASS)
    from . import mep_connectors as MC
    for face, z, dirz in (("top", MH + H, 1.0), ("bottom", MH, -1.0)):
        MC.add_conduit_connector(doc, host=plates[face], face=face,
                                 location=(0.0, D / 2.0, z), direction=(0.0, 0.0, dirz),
                                 u_axis=(1.0, 0.0, 0.0), diameter_ft=_in(CONDUIT_IN),
                                 description=f"Conduit {face}")

    # -- clearance zones (#882), measured from the floor (the family origin) ----
    from . import equipment_clearance as EC
    rep_c = EC.add_clearance_zones(
        doc, F.add_box_form, kind="panelboard", width_ft=W, depth_ft=D, height_ft=H,
        body_center=(0.0, D / 2.0), base_z_ft=MH, front_dir=+1, front_y_ft=D,
        floor_z_ft=0.0, voltage_to_ground=F._panel_volts_to_ground(facts),
        mounting_note=(f"box bottom {mh_in:g} in above the floor "
                       + ("(given)" if mounting_height_in is not None else
                          f"(NOMINAL: the box top at {MOUNT_TOP_IN:g} in)")))
    zones = rep_c.pop("forms")
    for fb in zones:
        named.append((fb.params["role"], fb))
    zone_ctl = _clearance_controls(doc, W, MH, H, rep_c, dict(named))

    # -- drives -----------------------------------------------------------------
    drive_report: List[Dict[str, Any]] = []
    height_report: Dict[str, Any] = {}
    if drive:
        d_specs, h_specs = drive_specs(W, D, H, t, MH, CW, CH, CZ,
                                       zone_names=[n for n, _f in named
                                                   if n.startswith("clearance")],
                                       top_zone_h=(rep_c.get("top") or {}).get("height_ft"),
                                       zone_ctl=zone_ctl)
        drive_report, height_report = F._wire_equipment_drives(
            doc, named, d_specs, h_specs, what="panel box and cover")
        _wire_front_depth(doc, named, drive_report, D, zone_ctl)

    std_report = ST.apply_safe(doc, "panelboard", standards, None, facts=[facts])
    _contract_values(doc, facts, int(spaces))
    doc.finalize()
    F._born_law_after_finalize(doc)
    prod = F.FamilyProduct("panelboard", doc, facts, forms=[f for _n, f in named],
                           standards=std_report,
                           file_stem=F._slug(f"panel_box_cover_{facts.get('voltage_system')}_"
                                             f"{int(mains_a)}A_{int(spaces)}sp"))
    prod.drives = drive_report
    prod.heights = height_report
    prod.notes.append(
        "panelboard as BACK BOX + COVER (#1047): the box is five plates "
        f"{BOX_THICKNESS_IN:g} in thick, open at the front (a void-cut box is #1049); "
        f"the cover is {'surface' if surface else 'flush'} -- '{P_SURFACE}' off makes it "
        f"lap the opening {FLUSH_LAP_IN:g} in per side; shown by '{P_SHOW_COVER}' (bound "
        "to its visibility). No switch or resize has a desktop verdict (hard rule 4).")
    if given:
        prod.notes.append("box size GIVEN, not the catalog's: " + ", ".join(
            f"{k[:-3]} {dims[k]:g} in" for k in given))
    return prod


def drive_specs(W: float, D: float, H: float, t: float, MH: float,
                CW: float, CH: float, CZ: float, *, zone_names: Sequence[str],
                top_zone_h: Optional[float], zone_ctl: Optional[Dict[str, Any]] = None
                ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """In-plane and height drive specs of the box, the cover and the zones.

    * Width (x, symmetric): back, bottom, top and the top zone span it; the two
      sides ride their ends rigidly (their thickness holds).
    * Cover Width (x, symmetric): the cover alone.
    * Depth (y, one-sided, the back on the wall plane y = 0): the sides, bottom,
      top and the top zone span it; the cover and the working space ride the front.
    * Mounting Height: floor -> box bottom (the plates' bottom faces); Height:
      box bottom -> box top; the bottom plate's top and the top plate's bottom ride
      their faces at the wall thickness (locked); Cover Offset / Cover Height label
      the cover's faces; the top zone stands on the box top, Top Clearance Height
      tall.
    * Clearance Width (x, symmetric): the working space.  Its depth (Front
      Clearance Depth, from the box front) is wired after these, anchored on the
      Depth drive's front plane (:func:`_wire_front_depth`); its height (Front
      Clearance Height, down from the box top) when ``zone_ctl`` carries the plane
      it starts from.
    """
    zone_ctl = zone_ctl or {}
    zones = set(zone_names)
    top_zone = "clearance: top" if "clearance: top" in zones else None
    front_zone = ("clearance: front working space"
                  if "clearance: front working space" in zones else None)
    w_parts: Dict[str, Tuple[str, ...]] = {"back": ("lo", "hi"), "bottom": ("lo", "hi"),
                                           "top": ("lo", "hi")}
    if top_zone:
        w_parts[top_zone] = ("lo", "hi")
    width = {"caption": P_WIDTH, "axis": "x", "symmetric": True, "lo": -W / 2.0,
             "hi": W / 2.0, "parts": w_parts,
             "attach": {"lo": ["left side"], "hi": ["right side"]}}
    cover_w = {"caption": P_COVER_W, "axis": "x", "symmetric": True, "lo": -CW / 2.0,
               "hi": CW / 2.0, "parts": {"cover": ("lo", "hi")}}
    d_parts: Dict[str, Tuple[str, ...]] = {n: ("lo", "hi") for n in
                                           ("left side", "right side", "bottom", "top")}
    if top_zone:
        d_parts[top_zone] = ("lo", "hi")
    depth = {"caption": P_DEPTH, "axis": "y", "lo": 0.0, "hi": D, "lo_plane": "origin",
             "parts": d_parts, "attach": {"hi": ["cover"]}}
    plan = [width, cover_w, depth]
    if front_zone and zone_ctl.get("width_ft"):
        cw = float(zone_ctl["width_ft"])
        plan.append({"caption": P_CLW, "axis": "x", "symmetric": True, "lo": -cw / 2.0,
                     "hi": cw / 2.0, "parts": {front_zone: ("lo", "hi")}})
    both = {"start": "hi"}
    heights: List[Dict[str, Any]] = [
        {"caption": P_MOUNT, "lo": 0.0, "hi": MH, "name_hi": "box bottom",
         "parts": {n: dict(both) for n in ("back", "left side", "right side", "bottom")}},
        {"caption": P_HEIGHT, "lo": "box bottom", "hi": MH + H, "name_hi": "box top",
         "parts": {n: {"end": "hi"} for n in ("back", "left side", "right side", "top")}},
        {"caption": None, "locked": True, "lo": "box bottom", "hi": MH + t,
         "parts": {"bottom": {"end": "hi"}}},
        {"caption": None, "locked": True, "lo": MH + H - t, "hi": "box top",
         "parts": {"top": {"start": "lo"}}},
        {"caption": P_COVER_Z, "lo": 0.0, "hi": CZ, "name_hi": "cover bottom",
         "parts": {"cover": {"start": "hi"}}},
        {"caption": P_COVER_H, "lo": "cover bottom", "hi": CZ + CH,
         "parts": {"cover": {"end": "hi"}}},
    ]
    if top_zone and top_zone_h:
        heights[1]["parts"][top_zone] = {"start": "hi"}
        heights.append({"caption": P_TOP_H if zone_ctl.get("top") else None,
                        "locked": not zone_ctl.get("top"), "lo": "box top",
                        "hi": MH + H + float(top_zone_h), "parts": {top_zone: {"end": "hi"}}})
    if front_zone and zone_ctl.get("floor_plane") is not None:
        heights.append({"caption": P_FRONT_H, "lo": zone_ctl["floor_plane"], "hi": "box top",
                        "parts": {front_zone: {"start": "lo", "end": "hi"}}})
    return plan, heights


def _as_number_of_poles(pe) -> None:
    """Store an integer parameter as Revit's NUMBER-OF-POLES definition
    (``ParamDefNoOfPoles``: an int definition bounded 1..3), the storage a power
    connector's poles property is associated to."""
    pdef = pe.obj["m_pParamDef"]
    body = dict(pdef["value"])
    body.pop("m_lowBound", None)
    body.pop("m_upBound", None)
    body.update({"m_lowBound": 1, "m_upBound": 3})
    pdef["ptr_class"] = "ParamDefNoOfPoles"
    pdef["value"] = body
    pe.refs["kind"] = "ParamDefNoOfPoles"


def _load_class_parameter(doc, con) -> Optional[Any]:
    """A LOAD CLASSIFICATION family parameter (``ElectricalLoadClassificationParamDef``,
    per instance), valued with the connector's own load class -- the parameter a
    power connector's load-classification property is associated to."""
    lc_id = int(con.obj["m_pDomain"]["value"].get("m_idLoadClassification", -1))
    if lc_id < 0:
        return None
    pe = doc.add_family_parameter(P_LOAD_CLASS, SK.SPEC_TEXT, GROUP_CIRCUITING,
                                  is_instance=True, default={"m_elemId": lc_id})
    pdef = pe.obj["m_pParamDef"]
    pdef["ptr_class"] = "ElectricalLoadClassificationParamDef"
    pe.refs["kind"] = "ElectricalLoadClassificationParamDef"
    pe.refs["spec"] = None
    return pe


def _clearance_controls(doc, W: float, MH: float, H: float, rep_c: Dict[str, Any],
                        forms: Dict[str, Any]) -> Dict[str, Any]:
    """The working space's and the dedicated space's size parameters, per instance:
    ``Minimum Clearance Width`` (30 in, 110.26(A)(2)) and ``Clearance Width`` = the
    greater of it and the box width; ``Front Clearance Depth`` (the 110.26(A)(1)
    table value the zone was drawn at); ``Top Clearance Height`` (the dedicated
    space drawn); and -- when the working space was drawn from the floor to exactly
    the box top -- ``Front Clearance To Floor`` with ``Front Clearance Height`` =
    ``if(to floor, Mounting Height + Height, Height)`` measured down from the box
    top.  Returns what was authored, for the drive specs."""
    out: Dict[str, Any] = {}
    front, top = rep_c.get("front"), rep_c.get("top")
    hdr = SK.PGROUP_CONSTRAINTS
    if front:
        mn = _in(MIN_CLEARANCE_WIDTH_IN)
        doc.add_family_parameter(P_MIN_CLW, SK.SPEC_LENGTH, hdr, is_instance=True, default=mn)
        cw = max(W, mn)
        if abs(cw - float(front["width_ft"])) < 1e-9:
            doc.add_family_parameter(
                P_CLW, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS, is_instance=True,
                formula=f"if({P_WIDTH} < {P_MIN_CLW}, {P_MIN_CLW}, {P_WIDTH})", default=cw)
            out["width_ft"] = cw
        doc.add_family_parameter(P_FRONT_DEPTH, SK.SPEC_LENGTH, hdr, is_instance=True,
                                 default=float(front["depth_ft"]))
        out["depth_ft"] = float(front["depth_ft"])
        if abs(float(front["height_ft"]) - (MH + H)) < 1e-9 and MH > 1e-6:
            from . import height_law as HL
            doc.add_family_parameter(P_TO_FLOOR, SK.SPEC_YESNO, hdr, is_instance=True,
                                     default=1)
            doc.add_family_parameter(
                P_FRONT_H, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS, is_instance=True,
                formula=f"if({P_TO_FLOOR}, {P_MOUNT} + {P_HEIGHT}, {P_HEIGHT})",
                default=MH + H)
            # the zone's floor is its OWN plane, coincident with the origin plane
            # at the floor: the switch moves it up to the box bottom
            out["floor_plane"] = HL._new_zplane(doc, 0.0)
        else:
            doc.notes.append(
                f"the working space reaches {float(front['height_ft']):g} ft above the "
                f"floor (110.26(A)(3)), above the box top at {MH + H:g} ft: its height "
                f"is the code minimum, not switchable to the box")
    if top and top.get("height_ft"):
        doc.add_family_parameter(P_TOP_H, SK.SPEC_LENGTH, hdr, is_instance=True,
                                 default=float(top["height_ft"]))
        out["top"] = True
    return out


def _wire_front_depth(doc, named, drive_report, D: float, zone_ctl: Dict[str, Any]) -> None:
    """``Front Clearance Depth`` drives the working space's depth from the box front:
    a one-sided drive anchored on the Depth drive's front plane, so the zone follows
    the box when Depth changes.  A refusal is a note (hard rule 1)."""
    from . import drive_law as DL
    depth = next((d for d in drive_report if d.get("caption") == P_DEPTH), None)
    if depth is None or not zone_ctl.get("depth_ft"):
        doc.notes.append(f"'{P_FRONT_DEPTH}' drives nothing: the box depth drive was not "
                         f"wired, so the working space has no front plane to start from")
        return
    try:
        sketch_of, dup = F._named_sketches(named)
        zone = "clearance: front working space"
        if zone not in sketch_of or zone in dup:
            raise ValueError("no unique working-space part")
        planes = {p.elem_id: p for p in doc.refplanes}
        front_plane = planes[depth["planes"][1]]
        DL.wire_linear_drive(doc, caption=P_FRONT_DEPTH, axis="y", lo=D,
                             hi=D + float(zone_ctl["depth_ft"]),
                             targets=[(sketch_of[zone], ("lo", "hi"))], lo_plane=front_plane)
    except Exception as e:                                   # noqa: BLE001
        doc.notes.append(f"drive for {P_FRONT_DEPTH!r} not wired "
                         f"({type(e).__name__}: {str(e)[:90]})")


def _contract_values(doc, facts, spaces: int) -> None:
    """The panelboard's catalog facts as the values of the tagging-contract parameters
    the standards step added (``PanelName``, ``Phases``, ``MainsRating`` ...), as
    :func:`rvt.famgen.factory.make_panelboard` writes them -- a parameter the step did
    not add (``standards=False``) is skipped."""
    sccr = facts.get("sccr_ka")
    entries = (("PanelName", "text", str(facts.get("panel_name"))),
               ("Phases", "integer", int(facts.get("phases"))),
               ("Wires", "integer", int(facts.get("wires"))),
               ("BusRating", "current", float(facts.get("bus_rating_a"))),
               ("MainsType", "text", str(facts.get("mains_type"))),
               ("MainsRating", "current", float(facts.get("mains_rating_a"))),
               ("ShortCircuitRatingkA", "number", float(sccr) if sccr is not None else 0.0),
               ("Mounting", "text", str(facts.get("mounting"))),
               ("NumberOfCircuits", "integer", int(spaces)),
               ("NeutralRating", "text", str(facts.get("neutral_rating"))))
    name = doc.types[0][0]
    for cap, spec, val in entries:
        if cap in doc.params:
            doc.set_type_param(name, cap, F._TO_INTERNAL.get(spec, lambda v: v)(val))

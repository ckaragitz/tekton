"""panel_can -- a panelboard modelled as its BACK BOX and TRIM (#1047, steer #1046).

WHY A SECOND PANELBOARD.  ``factory.make_panelboard`` draws the cabinet a user
sees once the job is done: a solid enclosure with trim, a hinged door, hinges,
a latch and a nameplate (#892).  A prefabrication / rough-in library models the
same product the way it is installed: an open-front **back box** ("can") set at
a mounting height, and a **trim** (the front cover) that is surface-mounted (the
size of the box) or flush (lapping the wall opening), with the NEC working space
in front and the dedicated space above, each switchable.  The owner's reference
panelboard is built that way (measured privately, counts only -- the reference
stays in the git-ignored ``samples/``; S-2026-09-23-b: built the same way, never
copied).

WHAT IS BUILT.  Names are ours: the trade's words for the parts (back box, trim,
surface / flush) and NEC 110.26's for the spaces (working space, dedicated
equipment space); Revit's own terms for the circuiting values.  Every size that
is not a catalog fact or a code minimum is a NOMINAL of ours, overridable by the
caller.  A user's library names arrive only through their own parameter profile at
build time (#1048).

* the back box from five plates -- back, two sides, bottom, top -- open at the
  front, :data:`BOX_THICKNESS_IN` thick (``Box Thickness`` reports it; the walls
  hold it by locked dimensions -- it is not a drive).  (A box cut from one solid by
  a void, and its mounting holes, are #1049.  The plates look the same from every
  side and resize the same way.)
* the trim, one wall thick on the box front: the box's size when ``Surface Trim``
  is on, :data:`FLUSH_LAP_IN` larger on every side when it is off (``Flush Trim`` =
  ``not(Surface Trim)``), shown by ``Show Trim``.  ``Trim Width`` / ``Trim Height`` /
  ``Trim Bottom`` are formulas of the switch and label the trim's own dimensions.
* the clearance zones of :mod:`rvt.famgen.equipment_clearance` (#882): the
  110.26(A) working space starting at the trim's face, measured from the floor, and
  the 110.26(E)(1) dedicated space above the box, with their Yes/No switches -- and
  their sizes as parameters labelling the zones' own dimensions: width (the greater
  of the box and ``Working Space Minimum Width``) with a checked left / right shift
  (right = +x, left = -x: as seen in the floor plan with the panel's front, +y, toward
  the top of the screen), depth, the dedicated space's height, and a from-the-floor
  switch.
* the electrical circuiting parameters a connector reads -- ``Voltage``,
  ``Number of Poles`` (Revit's number-of-poles storage), ``Power Factor``,
  ``Apparent Load``, ``Load Classification`` (a load-classification parameter,
  not text) and ``Motor`` -- the first five ASSOCIATED to the power connector on
  the box top; and two round conduit connectors, on the box top and bottom.
* section-header rows (text parameters whose formula is their own label), each
  authored immediately before the members it heads in its palette group, so the
  stored parameter order reads in sections.
* ``Width`` / ``Height`` / ``Depth`` / ``Mounting Height`` (per instance) drive
  the box, the trim rides its front, the zones ride the box (drive / height laws,
  #914 / #787) -- every drive all-or-nothing, a refusal a note.

Nothing here claims behaviour in Revit -- the trim switch, the zone switches and
the resizing are claims only a desktop verdict makes (hard rule 4).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import factory as F
from . import param_binding as PB
from . import skeleton as SK
from . import standards as ST

#: the back box's wall (and the trim's) thickness -- NOMINAL, ours: 1/16 in sheet
#: steel; ``box_thickness_in=`` overrides it
BOX_THICKNESS_IN = 0.0625
#: how far a FLUSH trim laps the wall opening on every side -- NOMINAL, ours: 3/4 in;
#: ``flush_lap_in=`` overrides it
FLUSH_LAP_IN = 0.75
#: the box top's height above the floor when nothing says otherwise: the top
#: breaker handle at the 6 ft 7 in of NEC 240.24(A) less trim -- 78 in, the
#: archetype lane's mounting rule (``archetypes.MOUNT_TOP_IN``); a box this tall or
#: taller stands on the floor
MOUNT_TOP_IN = 78.0
#: the conduit connectors' nominal size (a 2 in trade-size entry), ours
CONDUIT_IN = 2.0
#: a length below this is zero (ft)
EPS = 1e-6
#: a mounting height (or a flush trim's bottom) closer to the floor than this is ON it:
#: Revit draws nothing shorter than about 1/32 in, so a labelled length that small
#: would be a dimension it cannot hold (in)
FLOOR_SNAP_IN = 1.0 / 32.0

#: connector properties a family parameter drives (the power connector's), as the
#: owner's reference library binds them (private census, counts only: poles 21 /
#: 21 to a number-of-poles parameter, voltage 24, power factor 21, load class 21 to
#: a load-classification parameter, apparent load 21 of 23 to -1140004 -- not the
#: -1140005 ``skeleton.ELEM_PROP_APPARENT_LOAD`` holds, which 2 bind; #1051)
ELEM_PROP_POLES = -1140001
ELEM_PROP_VOLTAGE = -1140002
ELEM_PROP_APPARENT_LOAD = -1140004
ELEM_PROP_POWER_FACTOR = -1140008
ELEM_PROP_LOAD_CLASS = -1140014

GROUP_CIRCUITING = "autodesk.parameter.group:electricalCircuiting-1.0.0"

#: our parameter names
P_WIDTH, P_HEIGHT, P_DEPTH = "Width", "Height", "Depth"
P_MOUNT = "Mounting Height"
P_THICK = "Box Thickness"
P_SURFACE, P_FLUSH, P_SHOW_TRIM = "Surface Trim", "Flush Trim", "Show Trim"
P_TRIM_W, P_TRIM_H, P_TRIM_Z = "Trim Width", "Trim Height", "Trim Bottom"
P_VOLTAGE, P_POLES, P_PF = "Voltage", "Number of Poles", "Power Factor"
P_LOAD, P_LOAD_CLASS, P_MOTOR = "Apparent Load", "Load Classification", "Motor"
P_MIN_WS_W, P_WS_W = "Working Space Minimum Width", "Working Space Width"
P_WS_DEPTH, P_DED_H = "Working Space Depth", "Dedicated Space Height"
P_FROM_FLOOR, P_WS_H = "Working Space From Floor", "Working Space Height"
P_CENTERED, P_WS_LEFT = "Working Space Centered", "Working Space Left Edge"
P_SHIFT_L, P_SHIFT_R = "Working Space Shift Left", "Working Space Shift Right"
P_SHIFT_L_ON, P_SHIFT_R_ON = "Working Space Shift Left Applied", "Working Space Shift Right Applied"
#: the working space's minimum width, NEC 110.26(A)(2): the equipment's width or
#: 30 in, whichever is greater (a code minimum, cited by article -- never NFPA text)
MIN_WORKING_WIDTH_IN = 30.0
#: section headers: (parameter, palette group) -- a text parameter whose formula
#: is its own label, authored IMMEDIATELY before the members it heads in its group
#: (the palette's stored order is the authoring order within a group)
H_IDENTITY, H_DIMS, H_TRIM, H_CLEAR = ("--- Identity ---", "--- Dimensions ---",
                                       "--- Trim ---", "--- Clearances ---")
HEADERS = ((H_IDENTITY, SK.PGROUP_IDENTITY), (H_DIMS, SK.PGROUP_CONSTRAINTS),
           (H_TRIM, SK.PGROUP_CONSTRAINTS), (H_CLEAR, SK.PGROUP_CONSTRAINTS))

ZONE_FRONT = "clearance: front working space"
ZONE_TOP = "clearance: top"


class PanelCanError(ValueError):
    """The request cannot be built (a size that leaves no box inside its walls)."""


def _in(v: float) -> float:
    return float(v) / 12.0


def _lit(inches: float) -> str:
    """A length literal in a formula, in feet (``0.0416666666666667'``)."""
    return f"{float(inches) / 12.0:.15g}'"


def trim_formulas(lap_in: float = FLUSH_LAP_IN) -> Dict[str, str]:
    """The trim's size and placement as formulas of the surface switch: a surface
    trim is the box; a flush one laps the opening by ``lap_in`` on every side, so it
    is ``2 x lap`` wider and taller and starts ``lap`` lower."""
    lap2, lap = _lit(2 * lap_in), _lit(lap_in)
    return {P_TRIM_W: f"if({P_SURFACE}, {P_WIDTH}, {P_WIDTH} + {lap2})",
            P_TRIM_H: f"if({P_SURFACE}, {P_HEIGHT}, {P_HEIGHT} + {lap2})",
            P_TRIM_Z: f"if({P_SURFACE}, {P_MOUNT}, {P_MOUNT} - {lap})"}


def shift_formula(shift: str) -> str:
    """A shift as APPLIED: zero when the working space is centred or the shift is
    negative, else no more than the room the minimum width leaves beside the box --
    so the working space always spans the box (110.26(A)(2))."""
    room = f"({P_WS_W} - {P_WIDTH}) / 2"
    return (f"if({P_CENTERED}, 0', if({shift} < 0', 0', "
            f"if({shift} < {room}, {shift}, {room})))")


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
                   surface: bool = True, box_thickness_in: Optional[float] = None,
                   flush_lap_in: Optional[float] = None, name: Optional[str] = None,
                   start_id: int = 1000, shared_params: SK.SharedParamsArg = None,
                   standards: bool = True, drive: bool = True) -> "F.FamilyProduct":
    """A panelboard as its back box and trim (see the module doc).

    The box size is the catalog's (``vendor`` / ``line`` / ``mains_a`` / ``spaces``,
    as :func:`rvt.famgen.factory.make_panelboard`) unless ``width_in`` /
    ``height_in`` / ``depth_in`` say otherwise (then ``given``).
    ``mounting_height_in`` = the box bottom above the floor; default: the box top at
    :data:`MOUNT_TOP_IN` (``nominal``), on the floor for a box that tall.
    ``surface`` = the trim switch's value; ``box_thickness_in`` / ``flush_lap_in``
    override the nominal wall thickness and flush lap.
    """
    facts = F.resolve_panelboard_facts(vendor, line, mains_a=float(mains_a),
                                       spaces=int(spaces), voltage=voltage, mcb=bool(mcb),
                                       mounting="surface" if surface else "flush",
                                       panel_name=panel_name)
    given: List[str] = []
    dims = {}
    for key, val, fact in (("width_in", width_in, facts.get("width_in")),
                           ("height_in", height_in, facts.get("height_in")),
                           ("depth_in", depth_in, facts.get("depth_in")),
                           ("box_thickness_in", box_thickness_in, BOX_THICKNESS_IN),
                           ("flush_lap_in", flush_lap_in, FLUSH_LAP_IN)):
        if val is not None:
            given.append(key)
        dims[key] = float(val if val is not None else fact)
    W, H, D = _in(dims["width_in"]), _in(dims["height_in"]), _in(dims["depth_in"])
    t, lap_in = _in(dims["box_thickness_in"]), dims["flush_lap_in"]
    if not t > 0 or lap_in < 0:
        raise PanelCanError(f"a {dims['box_thickness_in']:g} in wall and a {lap_in:g} in "
                            f"flush lap cannot be built")
    if min(W, H, D) <= 4 * t:
        raise PanelCanError(f"a {dims['width_in']:g} x {dims['height_in']:g} x "
                            f"{dims['depth_in']:g} in box leaves nothing inside "
                            f"{dims['box_thickness_in']:g} in walls")
    if mounting_height_in is not None and float(mounting_height_in) < 0:
        raise PanelCanError(f"a box cannot be mounted {mounting_height_in:g} in below "
                            f"the floor")
    mh_in = (float(mounting_height_in) if mounting_height_in is not None
             else max(0.0, MOUNT_TOP_IN - dims["height_in"]))
    snapped = []
    if 0 < mh_in < FLOOR_SNAP_IN:
        snapped.append(f"the box bottom {mh_in:g} in above the floor is ON it")
        mh_in = 0.0
    if not surface and 0 < abs(mh_in - lap_in) < FLOOR_SNAP_IN:
        snapped.append(f"a box bottom {mh_in:g} in up puts the flush trim's bottom on the floor")
        mh_in = lap_in
    MH = _in(mh_in)
    vll = float(facts.get("voltage_ll_v"))
    poles = 3 if int(facts.get("phases")) >= 3 else 1
    fam_name = name or F._clean_name("Panelboard Back Box and Trim", facts.get("voltage_system"),
                                     f"{int(mains_a)}A", f"{int(spaces)}ckt")
    doc = SK.new_family_document("electrical_equipment", fam_name,
                                 part_type=SK.PART_TYPE["panelboard"],
                                 work_plane_based=False, start_id=start_id,
                                 plane_length_ft=max(8.0, (MH + H) * 1.5),
                                 shared_params=shared_params)
    for note in snapped:
        doc.notes.append(f"{note} (closer than {FLOOR_SNAP_IN:g} in, which Revit cannot "
                         f"dimension): built as on the floor")
    # the ONE type, first: every parameter added below registers its value on it
    # (a parameter added before any type row exists keeps no value at all)
    doc.add_type(F._clean_name(f"{int(mains_a)}A", facts.get("mains_type"), f"{int(spaces)}ckt"),
                 {"manufacturer": str(facts.get("manufacturer")),
                  "model": str(facts.get("model")),
                  "description": (f"{facts.get('voltage_system')} V panelboard back box and "
                                  f"trim, {int(mains_a)} A, {int(spaces)} circuits (box "
                                  f"{dims['width_in']:g} W x {dims['height_in']:g} H x "
                                  f"{dims['depth_in']:g} D in)")})

    # -- parameters ----------------------------------------------------------
    # authored per instance or by formula here, so never a row of a shared-parameter
    # file (the writer builds no instance / formula-driven shared parameter): such a
    # row is set aside -- the family is built, the parameter local, and said
    _keep_local(doc)
    _header(doc, H_DIMS)
    for cap, val in ((P_WIDTH, W), (P_HEIGHT, H), (P_DEPTH, D), (P_MOUNT, MH)):
        doc.add_family_parameter(cap, SK.SPEC_LENGTH, SK.PGROUP_CONSTRAINTS,
                                 is_instance=True, default=val)
    doc.add_family_parameter(P_THICK, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                             formula=_lit(dims["box_thickness_in"]), default=t)
    _header(doc, H_TRIM)
    doc.add_family_parameter(P_SURFACE, SK.SPEC_YESNO, SK.PGROUP_CONSTRAINTS,
                             is_instance=True, default=1 if surface else 0)
    doc.add_family_parameter(P_FLUSH, SK.SPEC_YESNO, SK.PGROUP_CONSTRAINTS,
                             is_instance=True, formula=f"not({P_SURFACE})",
                             default=0 if surface else 1)
    show_trim = doc.add_family_parameter(P_SHOW_TRIM, SK.SPEC_YESNO, SK.PGROUP_CONSTRAINTS,
                                         is_instance=True, default=1)
    lap = _in(lap_in)
    TW, TH, TZ = (W, H, MH) if surface else (W + 2 * lap, H + 2 * lap, MH - lap)
    formulas = trim_formulas(lap_in)
    for cap, val in ((P_TRIM_W, TW), (P_TRIM_H, TH), (P_TRIM_Z, TZ)):
        doc.add_family_parameter(cap, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                 is_instance=True, formula=formulas[cap], default=val)
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
    trim = F.add_box_form(doc, TW, t, TH, base_z_ft=TZ, center=(0.0, D + t / 2.0))
    trim.params.update({"role": "trim"})
    PB.bind_visibility(trim, show_trim)
    named.append(("trim", trim))
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
    # the conduit entries a quarter width off centre: never on the feeder's point
    for face, z, dirz in (("top", MH + H, 1.0), ("bottom", MH, -1.0)):
        MC.add_conduit_connector(doc, host=plates[face], face=face,
                                 location=(W / 4.0, D / 2.0, z), direction=(0.0, 0.0, dirz),
                                 u_axis=(1.0, 0.0, 0.0), diameter_ft=_in(CONDUIT_IN),
                                 description=f"Conduit {face}")

    # -- clearance zones (#882), measured from the floor (the family origin) ----
    from . import equipment_clearance as EC
    rep_c = EC.add_clearance_zones(
        doc, F.add_box_form, kind="panelboard", width_ft=W, depth_ft=D, height_ft=H,
        body_center=(0.0, D / 2.0), base_z_ft=MH, front_dir=+1, front_y_ft=D + t,
        floor_z_ft=0.0, voltage_to_ground=F._panel_volts_to_ground(facts),
        mounting_note=(f"box bottom {mh_in:g} in above the floor "
                       + ("(given)" if mounting_height_in is not None else
                          f"(NOMINAL: the box top at {MOUNT_TOP_IN:g} in, or the box on the "
                          f"floor when it is that tall)")))
    for fb in rep_c.pop("forms"):
        named.append((fb.params["role"], fb))
    zone_ctl = _clearance_controls(doc, W, MH, H, rep_c, standards=standards)

    for note in (zone_ctl.get("notes") or []):
        doc.notes.append(note)

    # -- drives -----------------------------------------------------------------
    drive_report: List[Dict[str, Any]] = []
    height_report: Dict[str, Any] = {}
    if drive:
        from . import height_law as HL
        floor_plane = None
        if zone_ctl.get("height"):
            # the working space's floor is its OWN plane, coincident with the origin
            # plane: the from-the-floor switch moves it up to the box bottom
            floor_plane = HL._new_zplane(doc, 0.0)
        d_specs, h_specs = drive_specs(W, D, H, t, MH, TW, TH, TZ,
                                       zone_names=[n for n, _f in named
                                                   if n.startswith("clearance")],
                                       top_zone_h=(rep_c.get("top") or {}).get("height_ft"),
                                       zone_ctl=dict(zone_ctl, floor_plane=floor_plane))
        drive_report, height_report = F._wire_equipment_drives(
            doc, named, d_specs, h_specs, what="panel box and trim")
        if floor_plane is not None and P_WS_H not in (height_report.get("captions") or []):
            # its spec was refused: the plane holds nothing -- take it out again
            doc.refplanes.remove(floor_plane)
            doc.elements.remove(floor_plane)
            st = HL._state(doc)
            st["planes"] = [p for p in st["planes"] if p != floor_plane.elem_id]
            st["positioned"].discard(floor_plane.elem_id)
            if height_report.get("planes"):
                height_report["planes"] = len(st["planes"])
        _wire_working_depth(doc, named, drive_report, D, t, zone_ctl)
        _wire_working_width(doc, named, drive_report, zone_ctl)
        if MH <= EPS:
            doc.notes.append(f"the box stands on the floor: '{P_MOUNT}' is 0 and labels no "
                             f"dimension (the box bottom is the origin plane)")
        elif -EPS <= TZ <= EPS:
            doc.notes.append(f"the flush trim's bottom is on the floor: '{P_TRIM_Z}' labels no "
                             f"dimension, so the trim's bottom stays on the floor if "
                             f"'{P_MOUNT}' is changed")
        if TZ < -EPS:
            doc.notes.append(f"the flush trim laps {-TZ * 12:g} in below the floor: '{P_TRIM_Z}' "
                             f"and '{P_TRIM_H}' label no dimension (a length below the origin "
                             f"is not drawn as a drive)")

    if standards:
        _header(doc, H_IDENTITY)        # heads the identity rows the standards step adds
    std_report = ST.apply_safe(doc, "panelboard", standards, None, facts=[facts])
    _contract_values(doc, facts, int(spaces))
    doc.finalize()
    F._born_law_after_finalize(doc)
    prod = F.FamilyProduct("panelboard", doc, facts, forms=[f for _n, f in named],
                           standards=std_report,
                           file_stem=F._slug(f"panel_box_trim_{facts.get('voltage_system')}_"
                                             f"{int(mains_a)}A_{int(spaces)}sp"))
    prod.drives = drive_report
    prod.heights = height_report
    prod.notes.append(
        "panelboard as BACK BOX + TRIM (#1047): the box is five plates "
        f"{dims['box_thickness_in']:g} in thick, open at the front (a void-cut box is "
        f"#1049); the trim is {'surface' if surface else 'flush'} -- '{P_SURFACE}' off makes "
        f"it lap the opening {lap_in:g} in per side; shown by '{P_SHOW_TRIM}' (bound to its "
        "visibility). No switch or resize has a desktop verdict (hard rule 4).")
    if given:
        prod.notes.append("GIVEN, not the catalog's or our nominal: " + ", ".join(
            f"{k[:-3].replace('_', ' ')} {dims[k]:g} in" for k in given))
    return prod


def drive_specs(W: float, D: float, H: float, t: float, MH: float,
                TW: float, TH: float, TZ: float, *, zone_names: Sequence[str],
                top_zone_h: Optional[float], zone_ctl: Optional[Dict[str, Any]] = None
                ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """In-plane and height drive specs of the box, the trim and the zones.

    * Width (x, symmetric): back, bottom, top and the top zone span it; the two
      sides ride their ends rigidly (their thickness holds).
    * Trim Width (x, symmetric): the trim alone.
    * Depth (y, one-sided, the back on the wall plane y = 0): the sides, bottom,
      top and the top zone span it; the trim rides the front.
    * Mounting Height: floor -> box bottom (the plates' bottom faces) -- none when
      the box stands on the floor, whose bottom is then the origin plane; Height:
      box bottom -> box top; the bottom plate's top and the top plate's bottom ride
      their faces at the wall thickness (locked); Trim Bottom / Trim Height label the
      trim's faces (a trim bottom on the floor starts on the origin plane; one below
      it is not driven, said); the top zone stands on the box top, Dedicated Space
      Height tall.
    * The working space's width and shift (:func:`_wire_working_width`) and its
      depth (:func:`_wire_working_depth`) are wired after these; its height (Working
      Space Height, down from the box top) is a spec here when ``zone_ctl`` carries
      the floor plane it starts from.
    """
    zone_ctl = zone_ctl if zone_ctl is not None else {}
    zones = set(zone_names)
    top_zone = ZONE_TOP if ZONE_TOP in zones else None
    front_zone = ZONE_FRONT if ZONE_FRONT in zones else None
    w_parts: Dict[str, Tuple[str, ...]] = {"back": ("lo", "hi"), "bottom": ("lo", "hi"),
                                           "top": ("lo", "hi")}
    if top_zone:
        w_parts[top_zone] = ("lo", "hi")
    width = {"caption": P_WIDTH, "axis": "x", "symmetric": True, "lo": -W / 2.0,
             "hi": W / 2.0, "parts": w_parts,
             "attach": {"lo": ["left side"], "hi": ["right side"]}}
    trim_w = {"caption": P_TRIM_W, "axis": "x", "symmetric": True, "lo": -TW / 2.0,
              "hi": TW / 2.0, "parts": {"trim": ("lo", "hi")}}
    d_parts: Dict[str, Tuple[str, ...]] = {n: ("lo", "hi") for n in
                                           ("left side", "right side", "bottom", "top")}
    if top_zone:
        d_parts[top_zone] = ("lo", "hi")
    depth = {"caption": P_DEPTH, "axis": "y", "lo": 0.0, "hi": D, "lo_plane": "origin",
             "parts": d_parts, "attach": {"hi": ["trim"]}}
    sides = ("back", "left side", "right side")
    heights: List[Dict[str, Any]] = []
    if MH > EPS:
        heights.append({"caption": P_MOUNT, "lo": 0.0, "hi": MH, "name_hi": "box bottom",
                        "parts": {n: {"start": "hi"} for n in sides + ("bottom",)}})
        box_h = {n: {"end": "hi"} for n in sides + ("top",)}
        bottom: Any = "box bottom"
    else:                                   # on the floor: the box bottom IS the origin
        box_h = {n: {"start": "lo", "end": "hi"} for n in sides}
        box_h.update({"bottom": {"start": "lo"}, "top": {"end": "hi"}})
        bottom = 0.0
    heights.append({"caption": P_HEIGHT, "lo": bottom, "hi": MH + H, "name_hi": "box top",
                    "name_lo": "box bottom", "parts": box_h})
    heights += [
        {"caption": None, "locked": True, "lo": "box bottom", "hi": MH + t,
         "parts": {"bottom": {"end": "hi"}}},
        {"caption": None, "locked": True, "lo": MH + H - t, "hi": "box top",
         "parts": {"top": {"start": "lo"}}},
    ]
    if TZ > EPS:
        heights += [{"caption": P_TRIM_Z, "lo": 0.0, "hi": TZ, "name_hi": "trim bottom",
                     "parts": {"trim": {"start": "hi"}}},
                    {"caption": P_TRIM_H, "lo": "trim bottom", "hi": TZ + TH,
                     "parts": {"trim": {"end": "hi"}}}]
    elif TZ > -EPS:
        heights.append({"caption": P_TRIM_H, "lo": 0.0, "hi": TH,
                        "parts": {"trim": {"start": "lo", "end": "hi"}}})
    if top_zone and top_zone_h:
        heights[1 if MH > EPS else 0]["parts"][top_zone] = {"start": "hi"}
        heights.append({"caption": P_DED_H if zone_ctl.get("top") else None,
                        "locked": not zone_ctl.get("top"), "lo": "box top",
                        "hi": MH + H + float(top_zone_h), "parts": {top_zone: {"end": "hi"}}})
    if front_zone and zone_ctl.get("floor_plane") is not None:
        heights.append({"caption": P_WS_H, "lo": zone_ctl["floor_plane"], "hi": "box top",
                        "parts": {front_zone: {"start": "lo", "end": "hi"}}})
    return [width, trim_w, depth], heights


def _clearance_controls(doc, W: float, MH: float, H: float, rep_c: Dict[str, Any], *,
                        standards: bool = True) -> Dict[str, Any]:
    """The working space's and the dedicated space's size parameters, per instance:

    * ``Working Space Minimum Width`` (30 in, 110.26(A)(2)) and ``Working Space
      Width`` = the greater of it and the box width; ``Working Space Centered``, a
      shift each way and each shift as APPLIED (:func:`shift_formula`), and
      ``Working Space Left Edge`` = the zone's left edge from the centre plane;
    * ``Working Space Depth`` (the 110.26(A)(1) table value the zone was drawn at);
    * ``Dedicated Space Height`` (the dedicated space drawn);
    * when the working space was drawn from the floor to exactly the box top, a box
      off the floor: ``Working Space From Floor`` and ``Working Space Height`` =
      ``if(from floor, Mounting Height + Height, Height)`` measured down from the box
      top (a box lowered in Revit then draws its working space below the 6 1/2 ft of
      110.26(A)(3) -- the code height holds only at the height it was built at).

    Returns what was authored, for the drive specs, with ``notes`` for what was not."""
    out: Dict[str, Any] = {"notes": []}
    front, top = rep_c.get("front"), rep_c.get("top")
    grp = SK.PGROUP_CONSTRAINTS
    if front or (top and top.get("height_ft")) or standards:
        _header(doc, H_CLEAR)       # (with no zones it heads the standards' Service Clearance)
    if front:
        mn = _in(MIN_WORKING_WIDTH_IN)
        doc.add_family_parameter(P_MIN_WS_W, SK.SPEC_LENGTH, grp, is_instance=True, default=mn)
        cw = max(W, mn)
        if abs(cw - float(front["width_ft"])) < 1e-9:
            doc.add_family_parameter(
                P_WS_W, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS, is_instance=True,
                formula=f"if({P_WIDTH} < {P_MIN_WS_W}, {P_MIN_WS_W}, {P_WIDTH})", default=cw)
            out["width_ft"] = cw
            doc.add_family_parameter(P_CENTERED, SK.SPEC_YESNO, grp, is_instance=True,
                                     default=1)
            for cap in (P_SHIFT_L, P_SHIFT_R):
                doc.add_family_parameter(cap, SK.SPEC_LENGTH, grp, is_instance=True,
                                         default=0.0)
            for on, cap in ((P_SHIFT_L_ON, P_SHIFT_L), (P_SHIFT_R_ON, P_SHIFT_R)):
                doc.add_family_parameter(on, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS,
                                         is_instance=True, formula=shift_formula(cap),
                                         default=0.0)
            # the zone's LEFT edge from the centre plane: never below half the box
            # width, so the labelled dimension never reaches zero
            doc.add_family_parameter(
                P_WS_LEFT, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS, is_instance=True,
                formula=f"{P_WS_W} / 2 - {P_SHIFT_R_ON} + {P_SHIFT_L_ON}", default=cw / 2.0)
        else:
            out["notes"].append(
                f"the working space was drawn {float(front['width_ft']) * 12:g} in wide, not "
                f"the greater of the box and {MIN_WORKING_WIDTH_IN:g} in: its width and shift "
                f"are not parameters")
        doc.add_family_parameter(P_WS_DEPTH, SK.SPEC_LENGTH, grp, is_instance=True,
                                 default=float(front["depth_ft"]))
        out["depth_ft"] = float(front["depth_ft"])
        on_floor = MH <= EPS
        if abs(float(front["height_ft"]) - (MH + H)) < 1e-9 and not on_floor:
            doc.add_family_parameter(P_FROM_FLOOR, SK.SPEC_YESNO, grp, is_instance=True,
                                     default=1)
            doc.add_family_parameter(
                P_WS_H, SK.SPEC_LENGTH, SK.PGROUP_DIMENSIONS, is_instance=True,
                formula=f"if({P_FROM_FLOOR}, {P_MOUNT} + {P_HEIGHT}, {P_HEIGHT})",
                default=MH + H)
            out["height"] = True
        elif on_floor:
            out["notes"].append(
                "the box stands on the floor, so its working space always starts there: no "
                "from-the-floor switch, and the working space's height is not a drive")
        else:
            out["notes"].append(
                f"the working space reaches {float(front['height_ft']):g} ft above the floor "
                f"(the 6 1/2 ft of 110.26(A)(3)), above the box top at {MH + H:g} ft: its "
                f"height is the code minimum, not switchable to the box")
    if top and top.get("height_ft"):
        doc.add_family_parameter(P_DED_H, SK.SPEC_LENGTH, grp, is_instance=True,
                                 default=float(top["height_ft"]))
        out["top"] = True
    return out


def _local_only() -> Tuple[str, ...]:
    """Everything authored per instance, by formula, or as a storage the writer builds
    only locally (the number-of-poles definition) -- never from a shared-parameter row."""
    from . import equipment_clearance as EC
    return tuple(h for h, _g in HEADERS) + (
        P_WIDTH, P_HEIGHT, P_DEPTH, P_MOUNT, P_THICK, P_SURFACE, P_FLUSH, P_SHOW_TRIM, P_TRIM_W,
        P_TRIM_H, P_TRIM_Z, P_LOAD, P_MOTOR, P_LOAD_CLASS, P_POLES, P_MIN_WS_W, P_WS_W,
        P_WS_DEPTH, P_DED_H, P_FROM_FLOOR, P_WS_H, P_CENTERED, P_WS_LEFT, P_SHIFT_L, P_SHIFT_R,
        P_SHIFT_L_ON, P_SHIFT_R_ON, EC.P_SHOW, EC.P_FRONT_ON, EC.P_TOP_ON)


def _authored_specs() -> Dict[str, str]:
    """The spec this constructor authors each remaining caption it creates itself
    under; a shared row of another datatype cannot be that parameter."""
    from . import equipment_clearance as EC
    return {P_VOLTAGE: SK.SPEC_VOLTAGE, P_PF: SK.SPEC_NUMBER,
            EC.P_FRONT: SK.SPEC_YESNO, EC.P_TOP: SK.SPEC_YESNO}


def _keep_local(doc) -> None:
    """Set aside the shared-parameter file's rows this constructor cannot author shared:
    a caption it authors per instance, by formula or as a local-only storage
    (:func:`_local_only`), and one whose DATATYPE is not the spec it authors that
    caption under (:func:`_authored_specs` -- e.g. a YESNO row, which the writer
    reads no spec for).  The parameter is local, the family built, and a note names
    each -- never a refused job (hard rule 1).  The table is the document's own copy."""
    table = getattr(doc, "shared_params", None)
    if not table:
        return
    local = [n for n in _local_only() if n in table]
    other = [n for n, spec in _authored_specs().items()
             if n in table and not SK.shared_datatype_matches(table[n].datatype, spec)]
    for n in local + other:
        table.pop(n)
    if local:
        doc.notes.append(f"kept LOCAL, not shared: {', '.join(local)} -- authored per instance, "
                         f"by formula or as a local-only storage here, which a row of the "
                         f"shared-parameter file is not")
    if other:
        doc.notes.append(f"kept LOCAL, not shared: {', '.join(other)} -- the shared-parameter "
                         f"file's datatype is not the one this family authors it as")


def _header(doc, name: str) -> None:
    grp = dict(HEADERS)[name]
    doc.add_family_parameter(name, SK.SPEC_TEXT, grp, is_instance=True,
                             formula=f'"{name}"', default=name)


def _zone_sketch(named):
    sketch_of, dup = F._named_sketches(named)
    if ZONE_FRONT not in sketch_of or ZONE_FRONT in dup:
        raise ValueError("no unique working-space part")
    return sketch_of[ZONE_FRONT]


def _wire_working_depth(doc, named, drive_report, D: float, t: float,
                        zone_ctl: Dict[str, Any]) -> None:
    """``Working Space Depth`` drives the working space from the trim's FACE: a
    one-sided drive anchored on the plane the trim's front edge rides (the Depth
    drive's front plane plus one wall, made by the trim's attach), so the zone
    follows the box when Depth changes.  A refusal is a note (hard rule 1)."""
    from . import drive_law as DL
    depth = next((d for d in drive_report if d.get("caption") == P_DEPTH), None)
    if not zone_ctl.get("depth_ft"):
        return
    try:
        if depth is None or not depth.get("attach"):
            raise ValueError("the box depth drive (and the trim riding it) was not wired")
        face = [p for p in doc.refplanes
                if _square_to_y(p) and abs(DL.plane_at(p, "y") - (D + t)) < 1e-9]
        if len(face) != 1:
            raise ValueError(f"{len(face)} planes at the trim face, not one")
        drive_report.append(DL.wire_linear_drive(
            doc, caption=P_WS_DEPTH, axis="y", lo=D + t, hi=D + t + float(zone_ctl["depth_ft"]),
            targets=[(_zone_sketch(named), ("lo", "hi"))], lo_plane=face[0]))
    except Exception as e:                                   # noqa: BLE001
        doc.notes.append(f"drive for {P_WS_DEPTH!r} not wired "
                         f"({type(e).__name__}: {str(e)[:90]})")


def _square_to_y(rp) -> bool:
    """A vertical plan reference plane square to y (its two ends share one y)."""
    from . import drive_law as DL
    if DL.is_surface_only(rp):
        return False
    a, b = rp.obj["m_freeEnd"], rp.obj["m_bubbleEnd"]
    return abs(float(a[1]) - float(b[1])) < 1e-9 and abs(float(a[0]) - float(b[0])) > 1e-9


def _wire_working_width(doc, named, drive_report, zone_ctl: Dict[str, Any]) -> None:
    """The working space's width and shift as a CHAIN from the origin centre plane:
    ``Working Space Left Edge`` (centre plane -> the zone's left edge, at least half
    the box width) then ``Working Space Width`` (left edge -> right edge, anchored on
    the plane the first drive made).  Every length stays positive at any shift,
    which a symmetric drive about the centre could not do.  A refusal is a note."""
    from . import drive_law as DL
    if not zone_ctl.get("width_ft"):
        return
    cw = float(zone_ctl["width_ft"])
    try:
        zone = _zone_sketch(named)
        left = DL.wire_linear_drive(doc, caption=P_WS_LEFT, axis="x", lo=-cw / 2.0, hi=0.0,
                                    targets=[(zone, ("lo",))],
                                    hi_plane=DL.origin_centre_plane(doc, "x"))
        planes = {p.elem_id: p for p in doc.refplanes}
        width = DL.wire_linear_drive(doc, caption=P_WS_W, axis="x", lo=-cw / 2.0, hi=cw / 2.0,
                                     targets=[(zone, ("hi",))],
                                     lo_plane=planes[left["planes"][0]])
        drive_report += [left, width]
    except Exception as e:                                   # noqa: BLE001
        doc.notes.append(f"drive for {P_WS_W!r} / {P_WS_LEFT!r} not wired "
                         f"({type(e).__name__}: {str(e)[:90]})")


def _as_number_of_poles(pe) -> None:
    """Store an integer parameter as Revit's NUMBER-OF-POLES definition
    (``ParamDefNoOfPoles``: an int definition bounded 1..3), the storage a power
    connector's poles property is associated to."""
    pdef = pe.obj["m_pParamDef"]
    body = dict(pdef["value"])
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

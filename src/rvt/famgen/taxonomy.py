"""rvt.famgen.taxonomy -- the MEP EQUIPMENT TAXONOMY and the VENDOR DIRECTORY.

THE GAP THIS CLOSES.  ``standards`` answers "given a category, what parameters
does a family carry".  ``catalog`` answers "given a vendor and a product line,
what are the published figures".  Nothing answered the two questions in
between, which are the ones a request actually arrives as:

* "make me a *motor control centre*" -- **what is that, and which Revit
  category does it belong in?**  (the TAXONOMY)
* "make me an *Eaton panelboard*" -- **do we hold real facts for that line, or
  are we about to invent them?**  (the VENDOR DIRECTORY)

Both tables are TRADE KNOWLEDGE, and this module is built around being honest
about exactly how far that goes.

THE LINE THIS MODULE IS DRAWN AROUND -- read before adding a row.

There are two very different claims in play, and only one of them is allowed
to live in this file:

* **What exists, and where it belongs.**  That a motor control centre is a
  piece of electrical equipment; that a receptacle is an Electrical Fixture
  and a panel is Electrical Equipment; that an engineer schedules a
  transformer by its kVA rating and a notification appliance by its candela
  rating; that Eaton makes the Pow-R-Line panelboards, Square D the NQ/NF/
  I-Line, Hoffman the enclosures.  This is the trade's own vocabulary.  It is
  checkable against things already in this repo (the category vocabulary in
  ``skeleton._resolve_category``, the parameter table in ``standards``), and
  those checks are :func:`check` below.  **This is what the tables hold.**

* **What a specific member measures or is rated for.**  That *this* panelboard
  is 20 in wide, that *this* transformer's impedance is 4.6 %.  A figure like
  that is a FACT about a real product, and in this repo a fact has exactly one
  home: ``facts/<vendor>/<line>.json``, each figure carrying its source
  document, date accessed and per-field provenance, resolved through
  ``catalog``.  ``facts/LICENSE_NOTES.md``'s basis line -- *facts are not
  copyrightable; we store no manufacturer files* -- is about published tables
  that were read, not figures that were recalled.  **Recalled numbers are not
  facts, and this module has NOWHERE TO PUT ONE.**

That last sentence is structural, not a promise.  :class:`Taxon` and
:class:`VendorLine` have no field a dimension or a rating could be written
into -- no ``dims``, no ``ratings``, no value of any kind -- and
:func:`check` additionally scans every string in both tables for a
number-followed-by-a-unit and fails on it (rule T7).  A dimension cannot be
smuggled in as prose either.

THE THIRD TIER, WHICH IS NOT HERE.  Standard practice for a product CLASS -- a
12 in ladder tray, a 1-5/8 in strut -- is real and needed, and is neither a
recalled member fact nor taxonomy.  It is the ``nominal`` tier of steer #591
(S-2026-08-10-e) and it belongs to the ARCHETYPE REGISTRY, not to this file.
:func:`archetype_status` reports whether that registry is present; it is
imported softly and nothing here requires it.

WHAT ``facts_held`` MEANS, AND WHY THE GATE IS THE POINT.  Every vendor line
says whether this repo holds sourced facts for it:

* ``facts_held=True``  -- ``facts_ref`` names a record ``catalog`` really
  resolves.  :func:`check` LOADS it (rule T5).  A line that claims facts we
  cannot resolve fails the gate; the table can never drift ahead of the store.
* ``facts_held=False`` -- we know the line exists and nothing more.  This is
  the honest majority of the directory, and it is the answer that stops a
  named part number from silently becoming a generic object wearing that
  number (steer #591).  Such a line may not carry a ``facts_ref`` at all
  (rule T6).

The gate also runs BACKWARDS (rule T8): every record in the facts store must
be claimed by some directory line, so the directory can never quietly
understate what we hold.

Public API::

    from rvt.famgen import taxonomy as T
    T.taxon("motor_control_center")        -> Taxon (or None)
    T.resolve("mcc")                       -> Taxon via alias
    T.taxa_for_category("panelboard")      -> (Taxon, ...)
    T.vendor("eaton")                      -> Vendor
    T.lines_for_taxon("panelboard")        -> ((Vendor, VendorLine), ...)
    T.sourced_lines()                      -> only the facts_held ones
    T.describe("panelboard")               -> the honest picture, incl. facts
    T.check()                              -> [problems]; empty == sound
    T.table()                              -> the whole thing, for a CLI / doc

CLI::

    python -m rvt.famgen.taxonomy --check      # the gate; exit 1 on any problem
    python -m rvt.famgen.taxonomy              # the whole table as JSON
    python -m rvt.famgen.taxonomy <taxon>      # one entry

TERRITORY: famgen (new module).  Reads ``standards``, ``skeleton`` and
``catalog``; writes nothing and edits no writer path.
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import catalog as C
from . import skeleton as SK
from . import standards as ST

__all__ = [
    "Taxon", "Vendor", "VendorLine",
    "CLAIM_TAXONOMY", "CLAIM_DIRECTORY", "CLAIM_TIERS",
    "DISCIPLINES", "MEP_TAXONOMY", "TAXON_ALIASES", "VENDORS",
    "taxon", "resolve", "taxa_for_category", "vendor", "lines_for_taxon",
    "sourced_lines", "describe", "table", "check", "archetype_status",
    "NOT_A_FACT_NOTE", "NOMINAL_TIER_NOTE",
]


# ---------------------------------------------------------------------------
# claim tiers -- what kind of statement a row in this file is
# ---------------------------------------------------------------------------

#: "this equipment exists and belongs in this Revit category, and these are the
#: parameters it is scheduled by".  Trade knowledge.  INFERRED as to naming,
#: but every part of it is cross-checked against an in-repo table by check().
CLAIM_TAXONOMY = "taxonomy"

#: "this manufacturer makes this product line".  Trade knowledge.  Carries NO
#: figure about any member of the line -- that is what facts_held is for.
CLAIM_DIRECTORY = "directory"

#: The tiers this module may assert.  ``fact`` is deliberately NOT one of
#: them: a fact lives in the facts store and is reached through ``catalog``.
CLAIM_TIERS: Tuple[str, ...] = (CLAIM_TAXONOMY, CLAIM_DIRECTORY)

NOT_A_FACT_NOTE = (
    "taxonomy and vendor rows are trade knowledge, not manufacturer facts: "
    "they say what a thing is, which Revit category it belongs in, and who "
    "makes a line of them. No dimension or rating of any member is asserted "
    "here -- those live in facts/<vendor>/<line>.json with their source, and "
    "are reached only through catalog.py")

NOMINAL_TIER_NOTE = (
    "standard practice for a product CLASS (a 12 in ladder tray, a 1-5/8 in "
    "strut) is the 'nominal' tier of steer #591 and belongs to the archetype "
    "registry, not to this table")


# ---------------------------------------------------------------------------
# the rows
# ---------------------------------------------------------------------------

#: The MEP disciplines this taxonomy spans (the grouping an engineer reads it
#: by; it carries no format meaning).
DISCIPLINES: Tuple[str, ...] = (
    "electrical", "lighting", "low_voltage", "fire_alarm",
    "raceway", "mechanical", "plumbing",
)


@dataclass(frozen=True)
class Taxon:
    """One kind of MEP equipment.

    NOTE THE ABSENT FIELDS.  There is no place here for a size, a rating, a
    voltage or a weight -- by construction, so that a recalled figure has
    nowhere to go.  ``schedule_by`` names PARAMETERS, never values, and every
    name in it must really exist in that category's ``standards`` table
    (check() rule T3), so "an engineer schedules this by X" is bound to a
    table in this repo rather than floating free.
    """

    key: str
    #: what a person calls it
    label: str
    #: one of DISCIPLINES
    discipline: str
    #: the Revit category key -- must be one skeleton._resolve_category knows
    #: AND one standards has a table for
    category: str
    #: parameter names an engineer schedules/selects this by; each must be in
    #: standards.standard_params(category) or a common built-in
    schedule_by: Tuple[str, ...]
    #: what it is, in words. No figures (check() rule T7 enforces this).
    role: str = ""
    #: other names the trade uses, for resolve()
    aliases: Tuple[str, ...] = ()
    #: anything worth saying about the category choice
    note: str = ""

    claim: str = CLAIM_TAXONOMY


@dataclass(frozen=True)
class VendorLine:
    """One product line of one manufacturer.

    ``facts_held`` is the whole point of the row: True means ``facts_ref``
    names a record ``catalog`` resolves and check() has loaded; False means we
    know the line exists and hold no figure for any member of it.
    """

    #: the line as the manufacturer names it
    line: str
    #: taxonomy keys this line covers (a line can span several -- the generic
    #: devices record covers receptacles, a switch and a box)
    taxa: Tuple[str, ...]
    facts_held: bool = False
    #: (vendor_dir, line_id) in the facts store -- ONLY when facts_held
    facts_ref: Optional[Tuple[str, str]] = None
    note: str = ""

    claim: str = CLAIM_DIRECTORY


@dataclass(frozen=True)
class Vendor:
    key: str
    name: str
    lines: Tuple[VendorLine, ...]
    note: str = ""


def _T(key: str, label: str, discipline: str, category: str,
       schedule_by: Sequence[str], role: str = "", aliases: Sequence[str] = (),
       note: str = "") -> Taxon:
    return Taxon(key=key, label=label, discipline=discipline,
                 category=category, schedule_by=tuple(schedule_by),
                 role=role, aliases=tuple(aliases), note=note)


# ---------------------------------------------------------------------------
# THE TAXONOMY
#
# Every row's ``category`` is checked against skeleton's vocabulary and
# standards' table, and every ``schedule_by`` name against that category's
# parameters -- so a wrong category or an invented parameter name is a gate
# failure, not a comment.
# ---------------------------------------------------------------------------

_TAXA: Tuple[Taxon, ...] = (

    # -- electrical: power distribution ------------------------------------
    _T("panelboard", "Panelboard", "electrical", "panelboard",
       ("PanelName", "BusRating", "MainsType", "MainsRating",
        "ShortCircuitRatingkA", "NumberOfCircuits", "Voltage", "Phases",
        "Mounting", "Enclosure Rating"),
       role="branch-circuit distribution: a bus fed by mains, with branch "
            "breakers serving lighting, appliance or power circuits",
       aliases=("panel", "distribution panel", "load centre", "load center")),

    _T("switchboard", "Switchboard", "electrical", "switchboard",
       ("BusRating", "MainsType", "MainsRating", "ShortCircuitRatingkA",
        "Sections", "Bus Material", "Voltage", "Phases", "Enclosure Rating"),
       role="floor-standing service or distribution lineup of sections, "
            "feeding panelboards and large loads",
       aliases=("switch board", "distribution switchboard")),

    _T("dry_type_transformer", "Dry-type transformer", "electrical",
       "transformer",
       ("kVA Rating", "Primary Voltage", "Secondary Voltage", "Impedance",
        "Temperature Rise", "Insulation Class", "K-Factor", "Sound Level",
        "Taps", "Mounting"),
       role="steps distribution voltage down to utilisation voltage; "
            "air-cooled, no liquid",
       aliases=("transformer", "dry type transformer", "xfmr", "general "
                "purpose transformer")),

    _T("motor_control_center", "Motor control centre", "electrical",
       "electrical_equipment",
       ("Voltage", "Phases", "Wires", "Enclosure Rating", "Apparent Load",
        "Load Classification", "Service Clearance", "Mounting"),
       role="lineup of plug-in buckets, each a starter or drive for one motor",
       aliases=("mcc", "motor control center")),

    _T("automatic_transfer_switch", "Automatic transfer switch", "electrical",
       "electrical_equipment",
       ("Voltage", "Phases", "Wires", "Enclosure Rating", "Apparent Load",
        "Load Classification", "Mounting"),
       role="transfers a load between a normal and an alternate source on "
            "loss of the normal source",
       aliases=("ats", "transfer switch")),

    _T("safety_disconnect_switch", "Safety disconnect switch", "electrical",
       "electrical_equipment",
       ("Voltage", "Phases", "Enclosure Rating", "Mounting",
        "Load Classification"),
       role="local lockable means of disconnect within sight of the equipment "
            "it serves",
       aliases=("disconnect", "safety switch", "isolator")),

    _T("enclosure", "Electrical enclosure", "electrical",
       "electrical_equipment",
       ("Enclosure Rating", "Mounting", "Service Clearance"),
       role="empty rated box or cabinet housing terminations, controls or a "
            "purchased assembly",
       aliases=("junction box", "terminal cabinet", "wireway box", "pull box"),
       note="the enclosure itself; whatever it houses is its own taxon"),

    _T("generator", "Engine generator", "electrical", "electrical_equipment",
       ("Voltage", "Phases", "Wires", "Frequency", "Apparent Load",
        "Enclosure Rating", "Service Clearance", "Operating Weight"),
       role="on-site alternate source, engine-driven",
       aliases=("genset", "emergency generator", "standby generator")),

    _T("ups", "Uninterruptible power supply", "electrical",
       "electrical_equipment",
       ("Voltage", "Phases", "Wires", "Apparent Load", "Load Classification",
        "Enclosure Rating", "Service Clearance", "Operating Weight"),
       role="rides through a source interruption from stored energy and "
            "conditions the load's supply",
       aliases=("uninterruptible power supply", "static ups")),

    _T("capacitor_bank", "Capacitor bank", "electrical",
       "electrical_equipment",
       ("Voltage", "Phases", "Wires", "Enclosure Rating", "Mounting",
        "Load Classification"),
       role="supplies reactive power locally to correct the power factor of a "
            "distribution bus",
       aliases=("power factor correction", "pfc bank")),

    # -- electrical: wiring devices ----------------------------------------
    _T("receptacle", "Receptacle", "electrical", "electrical_fixture",
       ("Device Type", "NEMA Configuration", "Number of Poles",
        "Mounting Height", "Number of Gangs", "GFCI Protected", "Voltage",
        "Backbox Size"),
       role="the room outlet a cord-connected load plugs into",
       aliases=("outlet", "socket", "convenience outlet", "duplex receptacle")),

    _T("motor_connection", "Motor connection", "electrical",
       "electrical_fixture",
       ("Device Type", "Number of Poles", "Voltage", "Apparent Load",
        "Load Classification", "Mounting"),
       role="the point a motor's branch circuit terminates at, carrying the "
            "motor's electrical load into the circuit",
       aliases=("equipment connection", "motor tap", "junction connection")),

    # -- lighting -----------------------------------------------------------
    _T("recessed_troffer", "Recessed troffer", "lighting", "lighting_fixture",
       ("Luminous Flux", "Initial Color Temperature", "Color Rendering Index",
        "Wattage", "Efficacy", "Driver Type", "Dimming Protocol", "Mounting",
        "Voltage"),
       role="rectangular luminaire recessed into a modular ceiling grid",
       aliases=("troffer", "grid luminaire", "recessed fluorescent")),

    _T("downlight", "Downlight", "lighting", "lighting_fixture",
       ("Luminous Flux", "Initial Color Temperature", "Color Rendering Index",
        "Wattage", "Efficacy", "Driver Type", "Dimming Protocol", "Mounting",
        "IP Rating"),
       role="round or square recessed luminaire delivering light downward "
            "from a ceiling aperture",
       aliases=("can light", "recessed downlight", "pot light")),

    _T("linear_pendant", "Linear pendant", "lighting", "lighting_fixture",
       ("Luminous Flux", "Initial Color Temperature", "Color Rendering Index",
        "Wattage", "Driver Type", "Dimming Protocol", "Mounting", "Lamp"),
       role="suspended linear luminaire, direct or direct/indirect",
       aliases=("pendant", "suspended linear", "linear suspended")),

    _T("high_bay", "High bay", "lighting", "lighting_fixture",
       ("Luminous Flux", "Initial Color Temperature", "Wattage", "Efficacy",
        "Driver Type", "Mounting", "IP Rating", "Voltage"),
       role="luminaire for tall spaces, mounted well above the working plane",
       aliases=("highbay", "high-bay", "industrial luminaire")),

    _T("exit_sign", "Exit sign", "lighting", "lighting_fixture",
       ("Wattage", "Mounting", "Emergency", "Voltage", "Lamp"),
       role="illuminated means-of-egress marker, with an integral or central "
            "emergency supply",
       aliases=("exit light", "egress sign", "running man sign")),

    _T("emergency_luminaire", "Emergency luminaire", "lighting",
       "lighting_fixture",
       ("Luminous Flux", "Wattage", "Mounting", "Emergency", "Voltage",
        "Driver Type"),
       role="luminaire that lights an egress path when normal power is lost",
       aliases=("emergency light", "bug eye", "egress luminaire")),

    _T("wall_switch", "Wall switch", "lighting", "lighting_device",
       ("Device Type", "Mounting Height", "Switch ID", "Control Type",
        "Number of Gangs", "Backbox Size", "Voltage"),
       role="the manual local control a room's lighting is switched from",
       aliases=("light switch", "toggle switch", "switch")),

    _T("occupancy_sensor", "Occupancy sensor", "lighting", "lighting_device",
       ("Device Type", "Mounting", "Control Type", "Switch ID", "Voltage"),
       role="switches or dims lighting from detected presence in the space",
       aliases=("vacancy sensor", "presence detector", "occ sensor")),

    _T("lighting_control_panel", "Lighting control panel", "lighting",
       "electrical_equipment",
       ("Voltage", "Phases", "Wires", "Enclosure Rating", "Mounting",
        "Load Classification"),
       role="relay or dimming panel switching lighting branch circuits under "
            "a schedule or a control system",
       aliases=("relay panel", "lighting relay panel", "dimming panel")),

    # -- low voltage / communications ---------------------------------------
    _T("data_outlet", "Data outlet", "low_voltage", "data_device",
       ("Device Type", "Mounting Height", "Number of Ports", "Cable Category",
        "Jack Color", "Termination Type", "Backbox Size"),
       role="the structured-cabling faceplate a work area is served from",
       aliases=("data jack", "network outlet", "rj45 outlet", "work area "
                "outlet")),

    _T("wireless_access_point", "Wireless access point", "low_voltage",
       "data_device",
       ("Device Type", "Mounting", "Number of Ports", "PoE Class",
        "Cable Category"),
       role="ceiling or wall radio serving wireless clients, fed over the "
            "structured cabling",
       aliases=("wap", "access point", "wifi ap")),

    _T("telephone_outlet", "Telephone outlet", "low_voltage",
       "telephone_device",
       ("Device Type", "Mounting Height", "Number of Ports", "Jack Type",
        "Backbox Size"),
       role="voice outlet, whether served by a PBX or by voice over the data "
            "cabling",
       aliases=("phone jack", "voice outlet", "telephone jack")),

    _T("security_camera", "Security camera", "low_voltage", "security_device",
       ("Device Type", "Mounting", "Field of View", "Resolution", "PoE Class",
        "Mounting Height"),
       role="fixed or steerable camera on the security network",
       aliases=("cctv camera", "surveillance camera", "ip camera")),

    _T("card_reader", "Card reader", "low_voltage", "security_device",
       ("Device Type", "Mounting", "Mounting Height", "Detection Range",
        "Voltage"),
       role="credential reader at a controlled door",
       aliases=("access control reader", "badge reader", "prox reader")),

    _T("motion_detector", "Security motion detector", "low_voltage",
       "security_device",
       ("Device Type", "Mounting", "Mounting Height", "Detection Range",
        "Field of View"),
       role="intrusion-detection sensor reporting to the security panel",
       aliases=("intrusion sensor", "pir detector", "security sensor"),
       note="the security-system sensor; the lighting-control one is "
            "occupancy_sensor"),

    _T("nurse_call_station", "Nurse call station", "low_voltage",
       "nurse_call_device",
       ("Device Type", "Mounting Height", "Station Type", "Number of Ports",
        "Backbox Size"),
       role="patient, staff or duty station on the nurse call system",
       aliases=("call station", "patient station", "nurse call")),

    _T("intercom", "Intercom station", "low_voltage", "communication_device",
       ("Device Type", "Mounting", "Mounting Height", "Number of Ports",
        "Signal Type"),
       role="two-way voice station, at an entry or within a paging system",
       aliases=("door station", "entry intercom", "talkback")),

    _T("paging_speaker", "Paging speaker", "low_voltage",
       "communication_device",
       ("Device Type", "Mounting", "Signal Type", "Voltage",
        "Apparent Load"),
       role="distributed-audio loudspeaker on a paging or mass-notification "
            "circuit",
       aliases=("ceiling speaker", "pa speaker", "overhead speaker")),

    _T("clock", "Synchronised clock", "low_voltage", "communication_device",
       ("Device Type", "Mounting", "Mounting Height", "Signal Type",
        "Voltage"),
       role="wall or double-faced clock driven from a master time source",
       aliases=("wall clock", "master clock", "time clock")),

    # -- fire alarm ---------------------------------------------------------
    _T("smoke_detector", "Smoke detector", "fire_alarm", "fire_alarm_device",
       ("Device Type", "Mounting", "Addressable", "Listing",
        "Standby Current", "Alarm Current", "Voltage"),
       role="initiating device sensing products of combustion",
       aliases=("smoke detector head", "photoelectric detector",
                "area smoke detector")),

    _T("heat_detector", "Heat detector", "fire_alarm", "fire_alarm_device",
       ("Device Type", "Mounting", "Addressable", "Listing",
        "Standby Current", "Alarm Current"),
       role="initiating device sensing a fixed temperature or a rate of rise",
       aliases=("thermal detector", "rate of rise detector")),

    _T("notification_appliance", "Notification appliance", "fire_alarm",
       "fire_alarm_device",
       ("Device Type", "Mounting Height", "Candela Rating", "Sound Output",
        "Alarm Current", "Listing", "Voltage"),
       role="occupant-notification appliance: audible, visible, or both",
       aliases=("horn strobe", "strobe", "horn", "speaker strobe",
                "audible visible")),

    _T("manual_pull_station", "Manual pull station", "fire_alarm",
       "fire_alarm_device",
       ("Device Type", "Mounting Height", "Addressable", "Listing",
        "Standby Current"),
       role="manual initiating device at an exit",
       aliases=("pull station", "manual call point", "break glass")),

    _T("duct_smoke_detector", "Duct smoke detector", "fire_alarm",
       "fire_alarm_device",
       ("Device Type", "Mounting", "Addressable", "Listing", "Alarm Current"),
       role="sampling detector in an air-handling duct, shutting the unit down "
            "on detection",
       aliases=("duct detector", "duct mounted smoke detector")),

    _T("fire_alarm_control_panel", "Fire alarm control panel", "fire_alarm",
       "electrical_equipment",
       ("Voltage", "Phases", "Enclosure Rating", "Mounting",
        "Load Classification", "Service Clearance"),
       role="the head end supervising the initiating and notification "
            "circuits",
       aliases=("facp", "fire panel", "fire alarm panel")),

    # -- raceway ------------------------------------------------------------
    _T("cable_tray_fitting", "Cable tray fitting", "raceway",
       "cable_tray_fitting",
       ("Tray Width", "Tray Height", "Bend Radius", "Fitting Angle",
        "Tray Type", "Material", "Finish", "Load Class"),
       role="a change of direction, elevation or size in a cable tray run",
       aliases=("tray fitting", "tray elbow", "tray tee", "cable tray elbow"),
       note="the fitting; a straight tray run is modelled by the run itself, "
            "and its class dimensions are archetype/nominal territory"),

    _T("conduit_fitting", "Conduit fitting", "raceway", "conduit_fitting",
       ("Nominal Diameter", "Bend Radius", "Fitting Angle",
        "Conduit Standard", "Material", "Finish"),
       role="an elbow, coupling or body in a conduit run",
       aliases=("conduit body", "conduit elbow", "condulet", "conduit "
                "coupling")),

    # -- mechanical ---------------------------------------------------------
    _T("air_handling_unit", "Air handling unit", "mechanical",
       "mechanical_equipment",
       ("Air Flow", "External Static Pressure", "Total Cooling Capacity",
        "Total Heating Capacity", "Entering Air Temperature",
        "Leaving Air Temperature", "Full Load Amps",
        "Minimum Circuit Ampacity", "Maximum Overcurrent Protection",
        "Sound Level"),
       role="central unit conditioning and moving supply air through coils, "
            "filters and a fan",
       aliases=("ahu", "air handler")),

    _T("rooftop_unit", "Rooftop unit", "mechanical", "mechanical_equipment",
       ("Air Flow", "External Static Pressure", "Total Cooling Capacity",
        "Total Heating Capacity", "Full Load Amps",
        "Minimum Circuit Ampacity", "Maximum Overcurrent Protection",
        "Operating Weight", "Voltage", "Phases"),
       role="packaged unit on the roof, conditioning and delivering air to "
            "the space below",
       aliases=("rtu", "packaged rooftop", "packaged unit")),

    _T("fan_coil_unit", "Fan coil unit", "mechanical", "mechanical_equipment",
       ("Air Flow", "External Static Pressure", "Total Cooling Capacity",
        "Total Heating Capacity", "Full Load Amps", "Sound Level", "Voltage"),
       role="terminal unit with a fan and a coil, conditioning one zone",
       aliases=("fcu", "fan coil")),

    _T("vav_terminal", "VAV terminal unit", "mechanical",
       "mechanical_equipment",
       ("Air Flow", "External Static Pressure", "Total Heating Capacity",
        "Sound Level", "Voltage", "Full Load Amps"),
       role="throttles zone supply air, with optional reheat",
       aliases=("vav box", "vav", "terminal box", "variable air volume box")),

    _T("exhaust_fan", "Exhaust fan", "mechanical", "mechanical_equipment",
       ("Air Flow", "External Static Pressure", "Full Load Amps",
        "Sound Level", "Voltage", "Phases", "Operating Weight"),
       role="moves air out of a space or a system to atmosphere",
       aliases=("fan", "inline fan", "roof exhaust fan", "ef")),

    _T("pump", "Pump", "mechanical", "mechanical_equipment",
       ("Full Load Amps", "Minimum Circuit Ampacity", "Voltage", "Phases",
        "Sound Level", "Operating Weight", "Service Clearance"),
       role="moves fluid through a hydronic, domestic or fire circuit",
       aliases=("circulator", "base mounted pump", "inline pump")),

    _T("chiller", "Chiller", "mechanical", "mechanical_equipment",
       ("Total Cooling Capacity", "Full Load Amps", "Minimum Circuit Ampacity",
        "Maximum Overcurrent Protection", "Voltage", "Phases", "Sound Level",
        "Operating Weight", "Service Clearance"),
       role="produces chilled water by a vapour-compression or absorption "
            "cycle",
       aliases=("water chiller", "air cooled chiller", "packaged chiller")),

    _T("boiler", "Boiler", "mechanical", "mechanical_equipment",
       ("Total Heating Capacity", "Full Load Amps", "Voltage", "Phases",
        "Operating Weight", "Service Clearance", "Sound Level"),
       role="produces hot water or steam for heating",
       aliases=("hot water boiler", "steam boiler", "condensing boiler")),

    _T("cooling_tower", "Cooling tower", "mechanical", "mechanical_equipment",
       ("Total Cooling Capacity", "Full Load Amps", "Voltage", "Phases",
        "Sound Level", "Operating Weight", "Service Clearance"),
       role="rejects condenser heat to atmosphere by evaporation",
       aliases=("tower", "evaporative cooler", "condenser water tower")),

    _T("unit_heater", "Unit heater", "mechanical", "mechanical_equipment",
       ("Total Heating Capacity", "Air Flow", "Full Load Amps", "Voltage",
        "Phases", "Sound Level"),
       role="fan-driven heater serving a space directly",
       aliases=("cabinet unit heater", "propeller unit heater", "cuh")),

    _T("volume_damper", "Volume damper", "mechanical", "duct_accessory",
       ("Duct Width", "Duct Height", "Pressure Class", "Leakage Class",
        "Face Velocity", "Material"),
       role="balances or shuts off air flow in a duct",
       aliases=("damper", "balancing damper", "manual volume damper", "vd")),

    _T("fire_smoke_damper", "Fire/smoke damper", "mechanical",
       "duct_accessory",
       ("Duct Width", "Duct Height", "Pressure Class", "Leakage Class",
        "Face Velocity", "Material"),
       role="closes a duct penetration of a rated assembly on fire or smoke "
            "detection",
       aliases=("fire damper", "smoke damper", "fsd", "combination damper")),

    # -- plumbing -----------------------------------------------------------
    _T("water_closet", "Water closet", "plumbing", "plumbing_fixture",
       ("Flow Rate", "Cold Water Fixture Units", "Drainage Fixture Units",
        "Supply Connection Size", "Drain Connection Size", "Mounting Height",
        "Accessible", "Operating Pressure"),
       role="soil fixture; floor- or wall-mounted, flush valve or tank",
       aliases=("toilet", "wc", "closet")),

    _T("urinal", "Urinal", "plumbing", "plumbing_fixture",
       ("Flow Rate", "Cold Water Fixture Units", "Drainage Fixture Units",
        "Supply Connection Size", "Drain Connection Size", "Mounting Height",
        "Accessible")),

    _T("lavatory", "Lavatory", "plumbing", "plumbing_fixture",
       ("Flow Rate", "Cold Water Fixture Units", "Hot Water Fixture Units",
        "Drainage Fixture Units", "Supply Connection Size",
        "Drain Connection Size", "Mounting Height", "Accessible", "Finish"),
       role="hand-washing basin",
       aliases=("wash basin", "hand basin", "lav")),

    _T("sink", "Sink", "plumbing", "plumbing_fixture",
       ("Flow Rate", "Cold Water Fixture Units", "Hot Water Fixture Units",
        "Drainage Fixture Units", "Supply Connection Size",
        "Drain Connection Size", "Mounting Height", "Finish"),
       role="service, kitchen or laboratory sink",
       aliases=("service sink", "mop sink", "kitchen sink")),

    _T("drinking_fountain", "Drinking fountain", "plumbing",
       "plumbing_fixture",
       ("Flow Rate", "Cold Water Fixture Units", "Drainage Fixture Units",
        "Supply Connection Size", "Drain Connection Size", "Mounting Height",
        "Accessible"),
       role="potable dispensing fixture, often with a bottle filler",
       aliases=("water cooler", "bottle filler", "efwc")),

    _T("shower", "Shower", "plumbing", "plumbing_fixture",
       ("Flow Rate", "Cold Water Fixture Units", "Hot Water Fixture Units",
        "Drainage Fixture Units", "Supply Connection Size",
        "Drain Connection Size", "Operating Pressure", "Accessible")),

    _T("floor_drain", "Floor drain", "plumbing", "plumbing_fixture",
       ("Drainage Fixture Units", "Drain Connection Size",
        "Vent Connection Size", "Finish"),
       role="drains a floor to the sanitary or storm system through a trap",
       aliases=("fd", "area drain", "trench drain")),

    _T("water_heater", "Water heater", "plumbing", "mechanical_equipment",
       ("Total Heating Capacity", "Full Load Amps", "Voltage", "Phases",
        "Operating Weight", "Service Clearance"),
       role="heats domestic water, stored or instantaneous",
       aliases=("dhw heater", "hot water heater", "water heater tank"),
       note="Revit content places water heaters under Mechanical Equipment "
            "(electrical load and connections) rather than Plumbing Fixtures; "
            "the taxon stays in the plumbing discipline"),

    _T("valve", "Valve", "plumbing", "pipe_accessory",
       ("Nominal Diameter", "End Connection", "Pressure Rating",
        "Temperature Rating", "Flow Coefficient", "Material"),
       role="isolates, throttles or checks flow in a pipe run",
       aliases=("gate valve", "ball valve", "butterfly valve", "check valve",
                "isolation valve")),

    _T("backflow_preventer", "Backflow preventer", "plumbing",
       "pipe_accessory",
       ("Nominal Diameter", "End Connection", "Pressure Rating",
        "Temperature Rating", "Flow Coefficient", "Material"),
       role="protects the potable supply from reverse flow at a cross "
            "connection",
       aliases=("rpz", "double check assembly", "bfp")),

    _T("strainer", "Strainer", "plumbing", "pipe_accessory",
       ("Nominal Diameter", "End Connection", "Pressure Rating",
        "Temperature Rating", "Flow Coefficient", "Material"),
       role="removes debris from a pipe run upstream of equipment",
       aliases=("y strainer", "basket strainer")),
)

MEP_TAXONOMY: Dict[str, Taxon] = {t.key: t for t in _TAXA}

#: trade name -> taxonomy key, for resolve()
TAXON_ALIASES: Dict[str, str] = {}
for _t in _TAXA:
    for _a in _t.aliases:
        TAXON_ALIASES.setdefault(_a.lower().replace(" ", "_"), _t.key)


# ---------------------------------------------------------------------------
# THE VENDOR DIRECTORY
#
# Who makes what.  facts_held=True is a CHECKED claim: check() resolves the
# named record through catalog and fails if it cannot.  Everything else is
# facts_held=False -- we know the line exists and hold no figure for it, which
# is the honest answer and the one that keeps a part number from becoming a
# generic object wearing that number (steer #591).
# ---------------------------------------------------------------------------

def _L(line: str, taxa: Sequence[str], *, facts: Optional[Tuple[str, str]] = None,
       note: str = "") -> VendorLine:
    return VendorLine(line=line, taxa=tuple(taxa), facts_held=facts is not None,
                      facts_ref=facts, note=note)


_VENDORS: Tuple[Vendor, ...] = (

    Vendor("eaton", "Eaton", (
        _L("Pow-R-Line panelboards", ("panelboard",),
           facts=("eaton", "pow-r-line-panelboards")),
        _L("Dry-type distribution transformers", ("dry_type_transformer",),
           facts=("eaton", "dry-type-transformers")),
        _L("Pow-R-Line switchboards", ("switchboard",)),
        _L("Freedom motor control centres", ("motor_control_center",)),
        _L("Heavy duty safety switches", ("safety_disconnect_switch",)),
        _L("ATC transfer switches", ("automatic_transfer_switch",)),
        _L("9395 UPS", ("ups",)),
        _L("B-Line cable tray and fittings", ("cable_tray_fitting",)),
    )),

    Vendor("square-d", "Square D by Schneider Electric", (
        _L("NQ / NF / I-Line panelboards", ("panelboard",),
           facts=("square-d", "nq-nf-iline-panelboards")),
        _L("QED switchboards", ("switchboard",)),
        _L("Model 6 motor control centres", ("motor_control_center",)),
        _L("EX dry-type transformers", ("dry_type_transformer",)),
        _L("Heavy duty safety switches", ("safety_disconnect_switch",)),
        _L("ASCO transfer switches", ("automatic_transfer_switch",),
           note="ASCO Power Technologies; sold alongside the Schneider line"),
    )),

    Vendor("hps", "Hammond Power Solutions", (
        _L("Sentinel G dry-type transformers", ("dry_type_transformer",),
           facts=("hps", "sentinel-g-transformers")),
        _L("Imperter / Titan control transformers",
           ("dry_type_transformer",)),
    )),

    Vendor("lithonia", "Lithonia Lighting (Acuity Brands)", (
        _L("BLT LED troffers", ("recessed_troffer",),
           facts=("lithonia", "blt-led-troffer")),
        _L("LDN LED downlights", ("downlight",),
           facts=("lithonia", "ldn6-led-downlight")),
        _L("IBG / IBH LED high bays", ("high_bay",)),
        _L("LHQM / EXR exit signs", ("exit_sign",)),
        _L("ELM emergency units", ("emergency_luminaire",)),
    )),

    Vendor("generic", "Generic (no manufacturer)", (
        _L("Wiring devices and mounting boxes",
           ("receptacle", "wall_switch", "enclosure"),
           facts=("generic", "devices-and-mounting"),
           note="deliberately unbranded: the default room outlet, the default "
                "switch and the box behind them"),
    ), note="not a manufacturer -- the unbranded defaults a room needs when "
            "no product has been chosen yet"),

    # -- vendors we hold no facts for --------------------------------------
    Vendor("hoffman", "Hoffman (nVent)", (
        _L("Enclosures and wireway", ("enclosure",)),
    )),

    Vendor("siemens", "Siemens", (
        _L("P1 / P2 panelboards", ("panelboard",)),
        _L("Sentron switchboards", ("switchboard",)),
        _L("tiastar motor control centres", ("motor_control_center",)),
        _L("Dry-type transformers", ("dry_type_transformer",)),
    )),

    Vendor("abb", "ABB", (
        _L("ReliaGear panelboards", ("panelboard",)),
        _L("Low voltage switchboards", ("switchboard",)),
        _L("Dry-type transformers", ("dry_type_transformer",)),
    )),

    Vendor("ge", "GE / ABB Electrification", (
        _L("A-Series panelboards", ("panelboard",)),
        _L("Spectra switchboards", ("switchboard",)),
    )),

    Vendor("generac", "Generac", (
        _L("Industrial engine generators", ("generator",)),
        _L("Transfer switches", ("automatic_transfer_switch",)),
    )),

    Vendor("caterpillar", "Caterpillar", (
        _L("Diesel and gas engine generator sets", ("generator",)),
    )),

    Vendor("vertiv", "Vertiv", (
        _L("Liebert UPS systems", ("ups",)),
    )),

    Vendor("hubbell", "Hubbell", (
        _L("Wiring devices", ("receptacle", "wall_switch")),
        _L("Premise wiring outlets", ("data_outlet", "telephone_outlet")),
    )),

    Vendor("leviton", "Leviton", (
        _L("Wiring devices", ("receptacle", "wall_switch")),
        _L("Atlas-X1 structured cabling outlets", ("data_outlet",)),
    )),

    Vendor("wattstopper", "Wattstopper (Legrand)", (
        _L("Occupancy and vacancy sensors", ("occupancy_sensor",)),
        _L("Lighting control panels", ("lighting_control_panel",)),
    )),

    Vendor("cooper-lighting", "Cooper Lighting Solutions (Signify)", (
        _L("Metalux troffers", ("recessed_troffer",)),
        _L("Halo and Portfolio downlights", ("downlight",)),
        _L("Sure-Lites exit and emergency", ("exit_sign",
                                             "emergency_luminaire")),
    )),

    Vendor("panduit", "Panduit", (
        _L("Mini-Com outlets and faceplates",
           ("data_outlet", "telephone_outlet")),
    )),

    Vendor("commscope", "CommScope", (
        _L("SYSTIMAX / NETCONNECT outlets", ("data_outlet",)),
    )),

    Vendor("cisco", "Cisco", (
        _L("Catalyst and Meraki access points", ("wireless_access_point",)),
    )),

    Vendor("axis", "Axis Communications", (
        _L("Network cameras", ("security_camera",)),
    )),

    Vendor("hid", "HID Global", (
        _L("Signo and iCLASS readers", ("card_reader",)),
    )),

    Vendor("rauland", "Rauland-Borg (Ametek)", (
        _L("Responder nurse call", ("nurse_call_station",)),
    )),

    Vendor("atlas-ied", "AtlasIED", (
        _L("Ceiling and paging loudspeakers", ("paging_speaker",)),
        _L("Intercom and talkback stations", ("intercom",)),
    )),

    Vendor("notifier", "Notifier (Honeywell)", (
        _L("Addressable initiating devices",
           ("smoke_detector", "heat_detector", "duct_smoke_detector",
            "manual_pull_station")),
        _L("Notification appliances", ("notification_appliance",)),
        _L("Fire alarm control panels", ("fire_alarm_control_panel",)),
    )),

    Vendor("simplex", "Simplex (Johnson Controls)", (
        _L("Initiating devices",
           ("smoke_detector", "heat_detector", "manual_pull_station")),
        _L("TrueAlert notification appliances",
           ("notification_appliance",)),
        _L("Fire alarm control panels", ("fire_alarm_control_panel",)),
    )),

    Vendor("edwards", "Edwards (Carrier)", (
        _L("Signature series initiating devices",
           ("smoke_detector", "heat_detector")),
        _L("Genesis notification appliances", ("notification_appliance",)),
    )),

    Vendor("chatsworth", "Chatsworth Products", (
        _L("Cable runway and tray", ("cable_tray_fitting",)),
    )),

    Vendor("allied-tube", "Atkore / Allied Tube & Conduit", (
        _L("Conduit and fittings", ("conduit_fitting",)),
    )),

    Vendor("trane", "Trane", (
        _L("Performance Climate Changer air handlers",
           ("air_handling_unit",)),
        _L("Voyager and Precedent rooftop units", ("rooftop_unit",)),
        _L("Series R and CenTraVac chillers", ("chiller",)),
        _L("VariTrane VAV terminals", ("vav_terminal",)),
    )),

    Vendor("carrier", "Carrier", (
        _L("39 series air handlers", ("air_handling_unit",)),
        _L("WeatherMaker rooftop units", ("rooftop_unit",)),
        _L("AquaEdge and AquaForce chillers", ("chiller",)),
        _L("Fan coil units", ("fan_coil_unit",)),
    )),

    Vendor("daikin", "Daikin Applied", (
        _L("Vision and Skyline air handlers", ("air_handling_unit",)),
        _L("Rebel rooftop units", ("rooftop_unit",)),
        _L("Magnitude and Pathfinder chillers", ("chiller",)),
    )),

    Vendor("greenheck", "Greenheck", (
        _L("Centrifugal and axial exhaust fans", ("exhaust_fan",)),
        _L("Volume and control dampers", ("volume_damper",)),
        _L("Fire and smoke dampers", ("fire_smoke_damper",)),
    )),

    Vendor("ruskin", "Ruskin (Johnson Controls)", (
        _L("Control and balancing dampers", ("volume_damper",)),
        _L("Fire, smoke and combination dampers", ("fire_smoke_damper",)),
    )),

    Vendor("titus", "Titus", (
        _L("VAV terminal units", ("vav_terminal",)),
    )),

    Vendor("bell-gossett", "Bell & Gossett (Xylem)", (
        _L("Series e and base-mounted pumps", ("pump",)),
    )),

    Vendor("grundfos", "Grundfos", (
        _L("Circulator and end-suction pumps", ("pump",)),
    )),

    Vendor("bac", "Baltimore Aircoil Company", (
        _L("Cooling towers", ("cooling_tower",)),
    )),

    Vendor("aerco", "AERCO (Watts)", (
        _L("Benchmark condensing boilers", ("boiler",)),
        _L("Water heaters", ("water_heater",)),
    )),

    Vendor("ao-smith", "A. O. Smith", (
        _L("Commercial water heaters", ("water_heater",)),
    )),

    Vendor("kohler", "Kohler", (
        _L("Commercial water closets and urinals",
           ("water_closet", "urinal")),
        _L("Lavatories and sinks", ("lavatory", "sink")),
    )),

    Vendor("american-standard", "American Standard", (
        _L("Commercial water closets and urinals",
           ("water_closet", "urinal")),
        _L("Lavatories", ("lavatory",)),
    )),

    Vendor("elkay", "Elkay", (
        _L("Sinks", ("sink",)),
        _L("Drinking fountains and bottle fillers",
           ("drinking_fountain",)),
    )),

    Vendor("zurn", "Zurn", (
        _L("Floor and area drains", ("floor_drain",)),
        _L("Backflow preventers", ("backflow_preventer",)),
        _L("Commercial fixtures", ("water_closet", "urinal", "lavatory")),
    )),

    Vendor("watts", "Watts Water Technologies", (
        _L("Backflow preventers", ("backflow_preventer",)),
        _L("Valves and strainers", ("valve", "strainer")),
    )),

    Vendor("nibco", "NIBCO", (
        _L("Valves and strainers", ("valve", "strainer")),
    )),

    Vendor("victaulic", "Victaulic", (
        _L("Grooved valves and fittings", ("valve",)),
    )),
)

VENDORS: Dict[str, Vendor] = {v.key: v for v in _VENDORS}


# ---------------------------------------------------------------------------
# reading the tables
# ---------------------------------------------------------------------------

def taxon(key: Any) -> Optional[Taxon]:
    """The taxon with this exact key, or ``None``."""
    return MEP_TAXONOMY.get(str(key).lower().replace(" ", "_"))


def resolve(name: Any) -> Optional[Taxon]:
    """The taxon for a key OR any trade alias -- ``None`` when unknown.
    Never guesses: an unrecognised name is ``None``, not a near match."""
    key = str(name).lower().replace(" ", "_").replace("-", "_")
    hit = MEP_TAXONOMY.get(key)
    if hit is not None:
        return hit
    aliased = TAXON_ALIASES.get(key)
    return MEP_TAXONOMY.get(aliased) if aliased else None


def taxa_for_category(category: Any) -> Tuple[Taxon, ...]:
    """Every taxon that lands in ``category`` (as ``standards`` canonicalises
    it), sorted by key."""
    want = ST.canonical_category(category)
    return tuple(sorted(
        (t for t in _TAXA if ST.canonical_category(t.category) == want),
        key=lambda t: t.key))


def vendor(key: Any) -> Optional[Vendor]:
    return VENDORS.get(str(key).lower())


def lines_for_taxon(key: Any) -> Tuple[Tuple[Vendor, VendorLine], ...]:
    """Every ``(vendor, line)`` the directory lists for a taxon, facts-held
    first then alphabetically."""
    k = str(key).lower().replace(" ", "_")
    out = [(v, l) for v in _VENDORS for l in v.lines if k in l.taxa]
    out.sort(key=lambda vl: (not vl[1].facts_held, vl[0].key, vl[1].line))
    return tuple(out)


def sourced_lines() -> Tuple[Tuple[Vendor, VendorLine], ...]:
    """Only the directory lines this repo really holds facts for."""
    return tuple((v, l) for v in _VENDORS for l in v.lines if l.facts_held)


def archetype_status() -> Dict[str, Any]:
    """Whether the ``nominal`` archetype registry (PR #674) is importable.

    The registry is NOT a dependency of this module: class-standard dimensions
    are a different tier and deliberately live there.  This reports the
    boundary rather than crossing it, and degrades to ``present=False`` when
    the module is absent (which it is on ``main`` today).
    """
    try:
        from . import archetypes as _A            # noqa: F401  (soft)
    except Exception as exc:                      # ImportError and anything else
        return {"present": False, "reason": f"{type(exc).__name__}: {exc}",
                "note": NOMINAL_TIER_NOTE}
    return {"present": True, "module": "rvt.famgen.archetypes",
            "note": NOMINAL_TIER_NOTE}


def describe(key: Any) -> Dict[str, Any]:
    """The honest picture for one taxon: its category, the parameters it is
    scheduled by, who makes one, and whether we hold facts for any of them."""
    t = resolve(key)
    if t is None:
        return {"taxon": str(key), "known": False,
                "note": ("no taxonomy entry for this name: the request is not "
                         "refused, but nothing here says which Revit category "
                         "it belongs in"),
                "nominal_tier": NOMINAL_TIER_NOTE}
    lines = lines_for_taxon(t.key)
    held = [(v, l) for v, l in lines if l.facts_held]
    return {
        "taxon": t.key, "known": True, "label": t.label,
        "discipline": t.discipline, "category": t.category,
        "category_ost": _ost(t.category),
        "schedule_by": list(t.schedule_by),
        "role": t.role, "aliases": list(t.aliases),
        "note": t.note, "claim": t.claim,
        "vendors": [
            {"vendor": v.key, "name": v.name, "line": l.line,
             "facts_held": l.facts_held,
             "facts_ref": list(l.facts_ref) if l.facts_ref else None,
             "note": l.note}
            for v, l in lines],
        "facts_held_lines": len(held),
        "basis": NOT_A_FACT_NOTE,
        "nominal_tier": NOMINAL_TIER_NOTE,
    }


def _ost(category: str) -> Optional[int]:
    try:
        return int(SK._resolve_category(category))
    except Exception:
        return None


def table() -> Dict[str, Any]:
    """The whole thing, for a CLI or a doc build."""
    return {
        "claim_tiers": list(CLAIM_TIERS),
        "basis": NOT_A_FACT_NOTE,
        "nominal_tier": NOMINAL_TIER_NOTE,
        "archetypes": archetype_status(),
        "disciplines": list(DISCIPLINES),
        "taxa": {t.key: describe(t.key) for t in
                 sorted(_TAXA, key=lambda x: (x.discipline, x.key))},
        "vendors": {
            v.key: {
                "name": v.name, "note": v.note,
                "lines": [
                    {"line": l.line, "taxa": list(l.taxa),
                     "facts_held": l.facts_held,
                     "facts_ref": list(l.facts_ref) if l.facts_ref else None,
                     "note": l.note}
                    for l in v.lines],
            } for v in _VENDORS},
        "counts": {
            "taxa": len(_TAXA),
            "categories": len({t.category for t in _TAXA}),
            "vendors": len(_VENDORS),
            "lines": sum(len(v.lines) for v in _VENDORS),
            "lines_facts_held": len(sourced_lines()),
            "facts_store_lines": len(C.list_lines()),
        },
    }


# ---------------------------------------------------------------------------
# THE GATE
# ---------------------------------------------------------------------------

#: Units a figure would be written in.  check() rule T7 refuses a number
#: followed by any of these ANYWHERE in either table's prose -- the mechanical
#: half of "this module holds no dimensions or ratings" (the structural half
#: is that the dataclasses have no field for one).
_UNIT_TOKENS: Tuple[str, ...] = (
    # length / area / volume
    "in", "inch", "inches", "ft", "feet", "foot", "mm", "cm", "m", "yd",
    # electrical
    "v", "kv", "va", "kva", "mva", "a", "ma", "ka", "w", "kw", "mw", "kwh",
    "hz", "ohm", "ohms", "hp", "ampere", "amperes", "amp", "amps", "volt",
    "volts", "watt", "watts",
    # light
    "lm", "lux", "fc", "k", "cd", "lpw",
    # thermal / flow / pressure
    "btu", "btuh", "mbh", "ton", "tons", "cfm", "gpm", "lps", "psi", "kpa",
    "pa", "bar", "inwg", "wg", "c", "f", "degc", "degf",
    # mass / sound / other
    "lb", "lbs", "kg", "g", "db", "dba", "nc", "pct", "percent",
)

_NUM_UNIT_RE = re.compile(
    r"(?<![A-Za-z0-9])\d+(?:[.,]\d+)?\s*[-/]?\s*(" +
    "|".join(sorted(_UNIT_TOKENS, key=len, reverse=True)) +
    r")(?![A-Za-z0-9])", re.IGNORECASE)

#: A facts record's own ``category`` -> the Revit categories a taxon on that
#: record may sit in.  Keeps the two tables and the store agreeing (rule T9).
_FACTS_CATEGORY_TO_REVIT: Dict[str, Tuple[str, ...]] = {
    "panelboard": ("panelboard",),
    "transformer": ("transformer",),
    "switchboard": ("switchboard",),
    "luminaire": ("lighting_fixture",),
    # the store's mixed "device" record spans wiring devices, their control
    # and the box behind them
    "device": ("electrical_fixture", "lighting_device", "data_device",
               "fire_alarm_device", "communication_device", "security_device",
               "nurse_call_device", "telephone_device", "electrical_equipment"),
}

#: Fields a row is allowed to have.  A future edit that adds e.g. ``dims`` or
#: ``ratings`` to either dataclass fails rule T1 -- the structural guarantee
#: that a recalled figure has nowhere to live.
_ALLOWED_TAXON_FIELDS = {"key", "label", "discipline", "category",
                         "schedule_by", "role", "aliases", "note", "claim"}
_ALLOWED_LINE_FIELDS = {"line", "taxa", "facts_held", "facts_ref", "note",
                        "claim"}


def _text_of(obj: Any) -> List[Tuple[str, str]]:
    """Every ``(where, string)`` in a row that a reader would see."""
    out: List[Tuple[str, str]] = []
    for f in fields(obj):
        val = getattr(obj, f.name)
        if isinstance(val, str):
            out.append((f.name, val))
        elif isinstance(val, tuple):
            for i, v in enumerate(val):
                if isinstance(v, str):
                    out.append((f"{f.name}[{i}]", v))
    return out


def check() -> List[str]:
    """Every problem in both tables, one line each -- empty when sound.

    T1  neither dataclass has a field a dimension or rating could live in
    T2  every taxon's category is in skeleton's vocabulary AND has a
        standards table
    T3  every ``schedule_by`` name really exists in that category's standards
        table (compared by ``standards.meaning_key``, so it respects the
        one-entry-per-meaning law) or is a common built-in
    T4  keys, aliases and disciplines are well-formed and unambiguous
    T5  **every ``facts_held=True`` line RESOLVES THROUGH ``catalog``** -- the
        record loads and has at least one variant.  This is the gate the
        module exists for: a table that claims facts we cannot resolve fails
    T6  a ``facts_held=False`` line carries no ``facts_ref``
    T7  no number-followed-by-a-unit anywhere in either table's prose
    T8  backwards: every record in the facts store is claimed by some line
    T9  a facts-held line's taxa agree with the record's own category
    """
    probs: List[str] = []

    # -- T1 structural: nowhere to put a figure ----------------------------
    got_t = {f.name for f in fields(Taxon)}
    if got_t != _ALLOWED_TAXON_FIELDS:
        probs.append(
            f"T1 Taxon fields changed: {sorted(got_t ^ _ALLOWED_TAXON_FIELDS)} "
            f"-- this table may not gain a field that holds a dimension or a "
            f"rating (those belong in facts/, reached through catalog)")
    got_l = {f.name for f in fields(VendorLine)}
    if got_l != _ALLOWED_LINE_FIELDS:
        probs.append(
            f"T1 VendorLine fields changed: "
            f"{sorted(got_l ^ _ALLOWED_LINE_FIELDS)} -- same rule")

    # -- T2/T3/T4 the taxonomy ---------------------------------------------
    seen_alias: Dict[str, str] = {}
    for t in _TAXA:
        # T4
        if t.key != t.key.lower().replace(" ", "_") or not t.key:
            probs.append(f"T4 {t.key!r}: key must be lower_snake_case")
        if t.discipline not in DISCIPLINES:
            probs.append(f"T4 {t.key}: discipline {t.discipline!r} not in "
                         f"{DISCIPLINES}")
        if t.claim != CLAIM_TAXONOMY:
            probs.append(f"T4 {t.key}: claim {t.claim!r} != {CLAIM_TAXONOMY!r}")
        if not t.schedule_by:
            probs.append(f"T4 {t.key}: schedule_by is empty -- say what an "
                         f"engineer selects it by, or drop the row")
        for a in t.aliases:
            ak = a.lower().replace(" ", "_")
            if ak in MEP_TAXONOMY and MEP_TAXONOMY[ak].key != t.key:
                probs.append(f"T4 {t.key}: alias {a!r} is another taxon's key")
            if ak in seen_alias and seen_alias[ak] != t.key:
                probs.append(f"T4 alias {a!r} claimed by both "
                             f"{seen_alias[ak]} and {t.key}")
            seen_alias[ak] = t.key

        # T2 -- the category vocabulary must agree with skeleton's
        try:
            SK._resolve_category(t.category)
        except KeyError:
            probs.append(f"T2 {t.key}: category {t.category!r} is unknown to "
                         f"skeleton._resolve_category")
            continue
        canon = ST.canonical_category(t.category)
        rows = ST.CATEGORY_STANDARDS.get(canon)
        if not rows:
            probs.append(f"T2 {t.key}: category {t.category!r} has no "
                         f"standards table ({ST.NO_TABLE_NOTE})")
            continue

        # T3 -- every scheduling parameter is really in that table
        known = {ST.meaning_key(p.name): p.name for p in rows}
        for p in ST.COMMON_BUILTINS:
            known.setdefault(ST.meaning_key(p.name), p.name)
        for name in t.schedule_by:
            mk = ST.meaning_key(name)
            if mk not in known:
                probs.append(
                    f"T3 {t.key}: schedule_by {name!r} is not a parameter of "
                    f"category {canon!r} in standards -- add it there or stop "
                    f"claiming it here")
            elif known[mk] != name:
                probs.append(
                    f"T3 {t.key}: schedule_by {name!r} is standards' "
                    f"{known[mk]!r} under another spelling -- use that one "
                    f"(#622: one entry per meaning)")

    # -- the directory ------------------------------------------------------
    claimed: Dict[Tuple[str, str], List[str]] = {}
    seen_vendor_line: set = set()
    for v in _VENDORS:
        if v.key != v.key.lower() or not v.key:
            probs.append(f"T4 vendor {v.key!r}: key must be lower-case")
        for l in v.lines:
            where = f"{v.key}/{l.line}"
            if (v.key, l.line) in seen_vendor_line:
                probs.append(f"T4 {where}: duplicate line")
            seen_vendor_line.add((v.key, l.line))
            if l.claim != CLAIM_DIRECTORY:
                probs.append(f"T4 {where}: claim {l.claim!r} != "
                             f"{CLAIM_DIRECTORY!r}")
            if not l.taxa:
                probs.append(f"T4 {where}: names no taxon")
            for k in l.taxa:
                if k not in MEP_TAXONOMY:
                    probs.append(f"T4 {where}: unknown taxon {k!r}")

            # -- T6 --------------------------------------------------------
            if not l.facts_held:
                if l.facts_ref is not None:
                    probs.append(
                        f"T6 {where}: facts_held is False but facts_ref is "
                        f"{l.facts_ref!r} -- a line may not point at a record "
                        f"it does not claim")
                continue

            # -- T5: the gate ----------------------------------------------
            if not (isinstance(l.facts_ref, tuple) and len(l.facts_ref) == 2):
                probs.append(f"T5 {where}: facts_held is True but facts_ref is "
                             f"{l.facts_ref!r} -- name (vendor, line)")
                continue
            fv, fl = l.facts_ref
            try:
                doc = C.load_line(fv, fl)
            except C.CatalogError as exc:
                probs.append(
                    f"T5 {where}: claims facts_held but catalog cannot resolve "
                    f"{fv}/{fl}: {exc}")
                continue
            variants = doc.get("variants") or []
            if not variants:
                probs.append(f"T5 {where}: facts record {fv}/{fl} has no "
                             f"variants -- nothing to resolve")
                continue
            claimed.setdefault((fv, fl), []).append(where)

            # -- T9: the record's own category agrees ----------------------
            fcat = doc.get("category")
            allowed = _FACTS_CATEGORY_TO_REVIT.get(str(fcat))
            if allowed is None:
                probs.append(
                    f"T9 {where}: facts record {fv}/{fl} has category {fcat!r},"
                    f" which this module has no Revit mapping for -- add it to "
                    f"_FACTS_CATEGORY_TO_REVIT")
            else:
                for k in l.taxa:
                    t2 = MEP_TAXONOMY.get(k)
                    if t2 is not None and t2.category not in allowed:
                        probs.append(
                            f"T9 {where}: taxon {k!r} is category "
                            f"{t2.category!r} but the facts record says "
                            f"{fcat!r} (expects one of {allowed})")

    # -- T8 backwards: the directory may not understate the store ----------
    try:
        store = set(C.list_lines())
    except C.CatalogError as exc:
        probs.append(f"T8 cannot list the facts store: {exc}")
        store = set()
    for ref in sorted(store - set(claimed)):
        probs.append(
            f"T8 facts store has {ref[0]}/{ref[1]} but no vendor line claims "
            f"it -- the directory would understate what we hold")
    for ref, wheres in sorted(claimed.items()):
        if len(wheres) > 1:
            probs.append(f"T8 {ref[0]}/{ref[1]} is claimed by {len(wheres)} "
                         f"lines: {', '.join(wheres)}")

    # -- T7 no figure anywhere in the prose --------------------------------
    for t in _TAXA:
        for wh, s in _text_of(t):
            m = _NUM_UNIT_RE.search(s)
            if m:
                probs.append(
                    f"T7 {t.key}.{wh}: {m.group(0)!r} reads as a dimension or "
                    f"a rating -- this table holds none (facts live in "
                    f"facts/, class-standard sizes in the archetype registry)")
    for v in _VENDORS:
        for s in (v.name, v.note):
            m = _NUM_UNIT_RE.search(s or "")
            if m:
                probs.append(f"T7 vendor {v.key}: {m.group(0)!r} reads as a "
                             f"dimension or a rating")
        for l in v.lines:
            for wh, s in _text_of(l):
                m = _NUM_UNIT_RE.search(s)
                if m:
                    probs.append(
                        f"T7 {v.key}/{l.line}.{wh}: {m.group(0)!r} reads as a "
                        f"dimension or a rating")

    return probs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "--check":
        probs = check()
        for p in probs:
            print(p)
        arch = archetype_status()
        print(f"{len(_TAXA)} taxa across {len({t.category for t in _TAXA})} "
              f"categories, {len(_VENDORS)} vendors / "
              f"{sum(len(v.lines) for v in _VENDORS)} lines, "
              f"{len(sourced_lines())} facts-held (store has "
              f"{len(C.list_lines())}), archetypes "
              f"{'present' if arch['present'] else 'ABSENT'}, "
              f"{len(probs)} problems")
        return 1 if probs else 0
    if args:
        print(json.dumps(describe(args[0]), indent=1))
        return 0
    print(json.dumps(table(), indent=1))
    return 0


if __name__ == "__main__":                            # pragma: no cover
    raise SystemExit(main())

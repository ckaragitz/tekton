"""rvt.famgen.standards -- the CATEGORY -> STANDARD PARAMETERS table.

THE GAP THIS CLOSES (owner steer #601: "every family type has a set of
parameters associated with them ... if i ask for a data device all parameters
that are typically associated within revit need to be in it, that goes for all
of them").  Until now a generated family carried whatever the constructor
happened to author -- ``Width`` / ``Depth`` / ``Height`` on a generic model,
the panelboard's tagging-contract set on a panelboard -- so a *data device*
came out of the "anything" route with three dimension parameters and nothing an
engineer would schedule it by.  This module is the table that fixes that: for
every category the engine can author, the parameters a family in that category
is expected to carry, each one saying WHERE IT CAME FROM.

WHAT IS AND IS NOT VERIFIED -- read this before adding a row.

* The **spec type id** (what the parameter measures) and the **group id**
  (where it sits in the properties palette) are format facts.  Every
  measurable spec id used here is checked, by :func:`check_specs`, against
  ``assets/family_units.json`` -- the units table OUR OWN family documents
  ship, which enumerates the 136 spec ids the format declares formatting for.
  A spec id that is not in that table is not authorable by us and is a test
  failure, not a comment.
* The **parameter name** is a different kind of claim, and carries an
  ``origin``:
  - ``builtin``    Revit itself gives every family of the category this
                   parameter.  We must NOT author it -- a local family
                   parameter of the same name would collide with (or shadow)
                   Revit's own.  It is listed so the report is complete and so
                   the authored set never duplicates one.
  - ``contract``   the name comes from an in-repo tagging contract
                   (``skills/tekton-ifc/references/shared-parameters-mapping.md``,
                   ``factory.PANEL_CONTRACT_PARAMS``, the pset keys
                   ``rvt.ifc.intent.CONTRACT_KEYS`` joins on) -- a name a
                   tekton schedule/tag already binds to.
  - ``convention`` the name is the industry content convention for that
                   category.  **INFERRED**: no in-repo verified source says
                   Revit spells it exactly this way.  The parameter is real,
                   authorable and schedulable either way -- it is a family
                   parameter of ours, with a correct spec and group -- but a
                   project expecting a different spelling will not bind to it.

WHAT THIS IS NOT.  It is not a claim to reproduce Revit's built-in parameter
table: the format's own schema does NOT carry the built-in id -> name ->
category mapping (that is application knowledge, not file knowledge), so the
only true BUILT-IN parameters we bind are the handful whose ids are verified in
``skeleton`` (Description, Manufacturer, Model, Type Comments, URL, Cost).
Everything this module authors is an ordinary FAMILY parameter with the right
spec and the right group.  Values are filled ONLY when the caller knows them
(hard rule 1's honesty: a blank standard parameter is an honest slot, an
invented value is a lie).

ONE ENTRY PER MEANING (#622).  A Revit user reads ``Lumens`` next to a blank
``Luminous Flux`` as two spellings of one quantity, one of them always empty --
which is worse than either alone.  So names are compared by :func:`meaning_key`
(case / spaces / underscores / hyphens folded, plus the hand-authored trade
synonyms in :data:`SYNONYM_GROUPS`), and that one key is used three times:
:func:`check_specs` fails a category that lists two spellings of one quantity,
:func:`apply` never authors a blank standard parameter next to a constructor's
(or a caller's) parameter of the same meaning, and the constructors fill the
table's spelling rather than a legacy one.  Where a legacy spelling is KEPT it
is the category's single entry and its row says why (the transformer's
``Weight``).

ONE STEP FOR EVERY CONSTRUCTOR (#642).  :func:`apply_safe` is the guarded
call every model-family constructor makes (the factory's five, the IFC-born
downlight, the intent's house switchboard): standards off -> no report, and any
values the caller offered are NAMED as not authored; standards on -> :func:`apply`,
and a fault in this module becomes a note on the document, never a failed
delivery (hard rule 1).  A given value is written in its parameter's own storage
class (:func:`coerce_value`): ``90`` for a number-spec ``Color Rendering Index``
lands as the double 90.0 Revit reads, not in the integer slot beside a 0.0.

STRUCTURAL STATUS.  Authoring N family parameters is the same machinery,
repeated, that the desktop-verified panelboard (11 contract parameters) and the
generated generic models already ship; nothing new is written to the file.  The
enlarged per-category sets have NOT themselves been through a desktop round --
they validate 0 errors and load-test like any other family, and that is stated,
not assumed away (hard rule 4).

Territory: famgen (new module; authors through ``FamilyDoc.add_family_parameter``
and edits no writer path).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from . import skeleton as SK

__all__ = [
    "StdParam", "ORIGIN_BUILTIN", "ORIGIN_CONTRACT", "ORIGIN_CONVENTION",
    "SPECS", "GROUPS", "NON_MEASURABLE", "COMMON_BUILTINS",
    "CATEGORY_STANDARDS", "CATEGORY_ALIASES", "canonical_category",
    "standard_params", "authored_params", "describe", "apply", "apply_safe",
    "coerce_value", "table", "check_specs", "units_spec_ids", "NO_TABLE_NOTE",
    "SYNONYM_GROUPS", "meaning_key",
]


ORIGIN_BUILTIN = "builtin"
ORIGIN_CONTRACT = "contract"
ORIGIN_CONVENTION = "convention"

#: what a category with no table gets told -- plainly, never silently
NO_TABLE_NOTE = ("no standard parameter table for this category yet: the family "
                 "carries its geometry parameters and the common identity "
                 "built-ins only, and that is a gap, not a claim of completeness")


# ---------------------------------------------------------------------------
# the vocabulary: spec type ids (WHAT a parameter measures) and group ids
# (WHERE it appears in the properties palette)
# ---------------------------------------------------------------------------

#: Forge spec type ids.  Every measurable one is verified present in the
#: format's own units table (:func:`units_spec_ids`); ``text`` / ``integer``
#: are the non-measurable storage classes, which that table never lists.
SPECS: Dict[str, str] = {
    # non-measurable storage classes
    "text": SK.SPEC_TEXT,
    "integer": SK.SPEC_INTEGER,
    # generic measurables
    "number": SK.SPEC_NUMBER,
    "length": SK.SPEC_LENGTH,
    "area": "autodesk.spec.aec:area-1.0.0",
    "volume": "autodesk.spec.aec:volume-1.0.0",
    "angle": "autodesk.spec.aec:angle-1.0.0",
    "speed": "autodesk.spec.aec:speed-1.0.0",
    "currency": "autodesk.spec.measurable:currency-1.0.0",
    # electrical
    "voltage": SK.SPEC_VOLTAGE,
    "current": "autodesk.spec.aec.electrical:current-1.0.0",
    "apparent_power": SK.SPEC_APPARENT_POWER,
    "wattage": SK.SPEC_WATTAGE,
    "power": "autodesk.spec.aec.electrical:power-1.0.0",
    "frequency": "autodesk.spec.aec.electrical:frequency-1.0.0",
    "demand_factor": "autodesk.spec.aec.electrical:demandFactor-1.0.0",
    "cable_tray_size": "autodesk.spec.aec.electrical:cableTraySize-1.0.0",
    "conduit_size": "autodesk.spec.aec.electrical:conduitSize-1.0.0",
    "wire_diameter": "autodesk.spec.aec.electrical:wireDiameter-1.0.0",
    # photometric
    "luminous_flux": SK.SPEC_LUMINOUS_FLUX,
    "luminous_intensity": "autodesk.spec.aec.electrical:luminousIntensity-1.0.0",
    "illuminance": "autodesk.spec.aec.electrical:illuminance-1.0.0",
    "cct": SK.SPEC_COLOR_TEMPERATURE,
    "efficacy": "autodesk.spec.aec.electrical:efficacy-1.0.0",
    # mechanical / hvac
    "air_flow": "autodesk.spec.aec.hvac:airFlow-1.0.0",
    "cooling_load": "autodesk.spec.aec.hvac:coolingLoad-1.0.0",
    "heating_load": "autodesk.spec.aec.hvac:heatingLoad-1.0.0",
    "hvac_pressure": "autodesk.spec.aec.hvac:pressure-1.0.0",
    "hvac_temperature": "autodesk.spec.aec.hvac:temperature-1.0.0",
    "duct_size": "autodesk.spec.aec.hvac:ductSize-1.0.0",
    "hvac_velocity": "autodesk.spec.aec.hvac:velocity-1.0.0",
    # piping / plumbing
    "flow": "autodesk.spec.aec.piping:flow-1.0.0",
    "piping_pressure": "autodesk.spec.aec.piping:pressure-1.0.0",
    "pipe_size": "autodesk.spec.aec.piping:pipeSize-1.0.0",
    "piping_temperature": "autodesk.spec.aec.piping:temperature-1.0.0",
    # structural / mass
    "mass": "autodesk.spec.aec.structural:mass-1.0.0",
    "mass_per_length": "autodesk.spec.aec.structural:massPerUnitLength-1.0.0",
    "force": "autodesk.spec.aec.structural:force-1.0.0",
    "moment": "autodesk.spec.aec.structural:moment-1.0.0",
    # energy
    "u_factor": "autodesk.spec.aec.energy:heatTransferCoefficient-1.0.0",
    "thermal_resistance": "autodesk.spec.aec.energy:thermalResistance-1.0.0",
}

#: spec keys the units table cannot vouch for because they are not measurable
#: (a string / an int has no unit to format) -- exempt from :func:`check_specs`.
NON_MEASURABLE = ("text", "integer")

#: Autodesk's published ``autodesk.parameter.group:*`` identifiers (the same
#: openly published enum ``genesis.residue_b`` uses).
GROUPS: Dict[str, str] = {
    "identity": SK.PGROUP_IDENTITY,
    "dimensions": SK.PGROUP_DIMENSIONS,
    "constraints": SK.PGROUP_CONSTRAINTS,
    "materials": SK.PGROUP_MATERIALS,
    "text": SK.PGROUP_TEXT,
    "construction": "autodesk.parameter.group:construction-1.0.0",
    "data": "autodesk.parameter.group:data-1.0.0",
    "general": "autodesk.parameter.group:general-1.0.0",
    "graphics": "autodesk.parameter.group:graphics-1.0.0",
    "green_building": "autodesk.parameter.group:greenBuilding-1.0.0",
    "electrical": SK.PGROUP_ELECTRICAL,
    "electrical_loads": SK.PGROUP_ELECTRICAL_LOADS,
    "electrical_circuiting": "autodesk.parameter.group:electricalCircuiting-1.0.0",
    "electrical_lighting": "autodesk.parameter.group:electricalLighting-1.0.0",
    "photometrics": "autodesk.parameter.group:lightPhotometrics-1.0.0",
    "mechanical": "autodesk.parameter.group:mechanical-1.0.0",
    "mechanical_airflow": "autodesk.parameter.group:mechanicalAirflow-1.0.0",
    "mechanical_loads": "autodesk.parameter.group:mechanicalLoads-1.0.0",
    "plumbing": "autodesk.parameter.group:plumbing-1.0.0",
    "structural": "autodesk.parameter.group:structural-1.0.0",
}


# ---------------------------------------------------------------------------
# one row of the table
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StdParam:
    """One standard parameter of a category.

    ``spec`` / ``group`` are keys into :data:`SPECS` / :data:`GROUPS`;
    ``instance`` = an instance parameter (per placed element) rather than a
    type parameter; ``origin`` = where the NAME comes from (see the module
    docstring); ``note`` = anything a reader needs to not be misled.
    """
    name: str
    spec: str = "text"
    group: str = "identity"
    instance: bool = False
    origin: str = ORIGIN_CONVENTION
    note: str = ""

    @property
    def authored(self) -> bool:
        """True when tekton writes this parameter into the family (a
        ``builtin`` row is Revit's own and is only reported)."""
        return self.origin != ORIGIN_BUILTIN

    @property
    def spec_id(self) -> str:
        return SPECS[self.spec]

    @property
    def group_id(self) -> str:
        return GROUPS[self.group]

    def to_json(self) -> Dict[str, Any]:
        d = {"name": self.name, "spec": self.spec, "group": self.group,
             "instance": self.instance, "origin": self.origin,
             "authored_by_tekton": self.authored}
        if self.authored:
            d["spec_id"] = self.spec_id
            d["group_id"] = self.group_id
        if self.note:
            d["note"] = self.note
        return d


def _P(name, spec="text", group="identity", *, instance=False,
       origin=ORIGIN_CONVENTION, note="") -> StdParam:
    return StdParam(name, spec, group, instance, origin, note)


def _B(name, note="") -> StdParam:
    """A parameter Revit itself provides -- reported, never authored."""
    return StdParam(name, "text", "identity", False, ORIGIN_BUILTIN, note)


def _without(block: Sequence[StdParam], *names: str) -> Tuple[StdParam, ...]:
    """``block`` minus the named rows -- for a product set that deliberately
    keeps its OWN spelling of one of the block's quantities (see the
    transformer's ``Weight``); greppable, unlike a silent merge rule."""
    return tuple(p for p in block if p.name not in names)


# ---------------------------------------------------------------------------
# one quantity, one entry (#622): names compare by MEANING, not spelling
# ---------------------------------------------------------------------------

#: Spellings a Revit user reads as ONE quantity.  Hand-authored trade
#: synonyms and abbreviations -- no vendor table, no Autodesk-authored list.
#: The FIRST spelling of each group is the one this table standardises on; the
#: rest are legacy constructor names, manufacturer-content habits and IFC-pset
#: style keys.  Spellings that differ only by case / spaces / underscores /
#: hyphens need no row: :func:`meaning_key` folds those by itself
#: (``MountingHeight`` == ``Mounting Height``, ``Airflow`` == ``Air Flow``).
SYNONYM_GROUPS: Tuple[Tuple[str, ...], ...] = (
    # photometric
    ("Luminous Flux", "Lumens", "Lamp Lumens", "Luminaire Lumens",
     "Initial Luminous Flux", "Light Output", "Lumen Output"),
    ("Initial Color Temperature", "Color Temperature", "Colour Temperature",
     "CCT", "Correlated Color Temperature"),
    ("Color Rendering Index", "CRI"),
    ("Efficacy", "Luminous Efficacy", "Lumens per Watt"),
    ("Light Loss Factor", "LLF"),
    # electrical
    ("Apparent Load", "Load", "Apparent Power", "Load VA"),
    ("Wattage", "Watts", "Input Watts", "Rated Wattage"),
    ("Voltage", "Volts", "Nominal Voltage", "Rated Voltage"),
    ("Phases", "Number of Phases"),
    ("Wires", "Number of Wires"),
    ("Number of Poles", "Poles"),
    ("Frequency", "Rated Frequency", "Hz"),
    ("kVA Rating", "kVA", "Rated kVA"),
    ("ShortCircuitRatingkA", "Short Circuit Rating", "SCCR",
     "Short Circuit Current Rating", "AIC Rating"),
    ("NumberOfCircuits", "Number of Circuits", "Circuit Count"),
    ("Sections", "Number of Sections", "Section Count"),
    ("Enclosure Rating", "Enclosure", "Enclosure Type", "NEMA Rating", "NEMA Type"),
    ("Full Load Amps", "FLA", "Full Load Current"),
    ("Minimum Circuit Ampacity", "MCA"),
    ("Maximum Overcurrent Protection", "MOCP", "MOP"),
    ("Temperature Rise", "Temp Rise"),
    # placement / identity
    ("Mounting Height", "Mounting Height AFF", "Height AFF"),
    ("Operating Weight", "Weight", "Unit Weight"),
    ("Warranty Duration", "Warranty", "Warranty Period"),
    ("Sound Level", "Noise Level", "Sound Pressure Level"),
    ("Fire Rating", "Fire Resistance Rating"),
    # mechanical / plumbing / envelope
    ("Air Flow", "CFM"),
    ("External Static Pressure", "ESP"),
    ("Total Cooling Capacity", "Cooling Capacity"),
    ("Total Heating Capacity", "Heating Capacity"),
    ("Flow Rate", "Flow", "GPM"),
    ("Nominal Diameter", "Nominal Size", "Trade Size"),
    ("U-Factor", "U Value", "Thermal Transmittance"),
    ("Solar Heat Gain Coefficient", "SHGC"),
    ("Visible Transmittance", "VT", "VLT"),
)


def _fold(name: Any) -> str:
    """Case / space / underscore / hyphen / punctuation-insensitive form."""
    return "".join(ch for ch in str(name).lower() if ch.isalnum())


def _build_synonym_key(groups: Sequence[Sequence[str]]) -> Tuple[Dict[str, str], List[str]]:
    """folded spelling -> folded canonical spelling for every group member,
    plus any spelling claimed by two groups (a table bug :func:`check_specs`
    reports)."""
    key: Dict[str, str] = {}
    clashes: List[str] = []
    for group in groups:
        canon = _fold(group[0])
        for spelling in group:
            f = _fold(spelling)
            if key.get(f, canon) != canon:
                clashes.append(f"synonym {spelling!r} is claimed by two groups "
                               f"({key[f]!r} and {canon!r})")
            key[f] = canon
    return key, clashes


_SYNONYM_KEY, _SYNONYM_CLASHES = _build_synonym_key(SYNONYM_GROUPS)


def meaning_key(name: Any) -> str:
    """The key two parameter names share iff a Revit user would read them as
    the same quantity: the folded spelling, mapped through
    :data:`SYNONYM_GROUPS` (``'Lumens'`` -> ``'luminousflux'``,
    ``'MountingHeight'`` -> ``'mountingheight'`` == ``'Mounting Height'``)."""
    f = _fold(name)
    return _SYNONYM_KEY.get(f, f)


# ---------------------------------------------------------------------------
# what EVERY model family already has, from Revit, whatever its category
# ---------------------------------------------------------------------------

#: Revit gives every loadable family these; the six with a note are the ones
#: whose built-in ids ``skeleton`` has verified, so tekton can FILL them (see
#: ``factory``'s ``identity=`` argument).  The rest are listed for completeness.
COMMON_BUILTINS: Tuple[StdParam, ...] = (
    _B("Description", "verified built-in id (BIP_TYPE_DESCRIPTION); tekton fills it"),
    _B("Manufacturer", "verified built-in id (BIP_TYPE_MANUFACTURER); tekton fills it"),
    _B("Model", "verified built-in id (BIP_TYPE_MODEL); tekton fills it"),
    _B("Type Comments", "verified built-in id (BIP_TYPE_TYPE_COMMENTS); tekton fills it"),
    _B("URL", "verified built-in id (BIP_TYPE_URL); tekton fills it"),
    _B("Cost", "verified built-in id (BIP_TYPE_COST); tekton fills it"),
    _B("Assembly Code"), _B("Assembly Description"), _B("Keynote"),
    _B("Type Mark"), _B("Type Image"),
    _B("Comments", "instance"), _B("Mark", "instance"), _B("Image", "instance"),
    _B("Phase Created", "instance"), _B("Phase Demolished", "instance"),
)

#: the electrical instance parameters Revit's circuiting fills once a family
#: with a power connector is placed and circuited -- never authored by us.
_CIRCUIT_BUILTINS: Tuple[StdParam, ...] = (
    _B("Panel", "instance; filled by Revit's circuiting when the element is circuited"),
    _B("Circuit Number", "instance; filled by Revit's circuiting"),
)


# ---------------------------------------------------------------------------
# reusable blocks
# ---------------------------------------------------------------------------

#: what any powered element carries so it schedules on a panel schedule
_POWER: Tuple[StdParam, ...] = (
    _P("Voltage", "voltage", "electrical"),
    _P("Apparent Load", "apparent_power", "electrical_loads", instance=True),
    _P("Load Classification", "text", "electrical_loads"),
)

#: what any wall/ceiling-mounted low-voltage DEVICE carries (data, fire alarm,
#: security, nurse call, telephone, communication, lighting devices).  This is
#: the block the owner's "data devices" example lands on.
_DEVICE_BASE: Tuple[StdParam, ...] = (
    _P("Device Type", "text", "identity"),
    _P("Mounting", "text", "identity"),
    _P("Mounting Height", "length", "constraints", instance=True,
       note="height above the host level the placement law uses"),
    _P("Backbox Size", "text", "identity"),
    _P("Faceplate Color", "text", "identity"),
) + _POWER

#: identity every physical product carries in a facility register (COBie-shaped)
_PRODUCT_IDENTITY: Tuple[StdParam, ...] = (
    _P("Operating Weight", "mass", "identity"),
    _P("Warranty Duration", "text", "identity"),
)

#: what ANY piece of electrical equipment carries, whatever it is.  The
#: product-specific sets below extend it -- a panelboard's circuit schedule
#: parameters have no business on a transformer, which is what a single
#: category-wide list got wrong the first time.
_EE_COMMON: Tuple[StdParam, ...] = (
    _P("Voltage", "voltage", "electrical", origin=ORIGIN_CONTRACT),
    _P("Phases", "integer", "electrical", origin=ORIGIN_CONTRACT),
    _P("Wires", "integer", "electrical", origin=ORIGIN_CONTRACT),
    _P("Frequency", "frequency", "electrical"),
    _P("Mounting", "text", "identity", origin=ORIGIN_CONTRACT),
    _P("Enclosure Rating", "text", "identity", note="NEMA / IP enclosure class"),
    _P("Apparent Load", "apparent_power", "electrical_loads", instance=True),
    _P("Load Classification", "text", "electrical_loads"),
    _P("Service Clearance", "length", "constraints",
       note="working clearance in front of the equipment (NFPA 70 110.26)"),
) + _PRODUCT_IDENTITY + _CIRCUIT_BUILTINS


def _merge(*groups: Sequence[StdParam]) -> Tuple[StdParam, ...]:
    """Concatenate parameter blocks, FIRST spelling of a name winning.

    Blocks overlap on purpose (a panelboard's contract ``Voltage`` and the
    electrical-equipment common ``Voltage`` are the same parameter), and a
    category that listed one twice would author it twice -- :func:`check_specs`
    fails on that, so the merge is the single place it is resolved."""
    out: List[StdParam] = []
    seen: set = set()
    for g in groups:
        for p in g:
            if p.name in seen:
                continue
            seen.add(p.name)
            out.append(p)
    return tuple(out)


# ---------------------------------------------------------------------------
# THE TABLE.  Keys are the canonical category names rvt.famgen.skeleton's
# _resolve_category accepts; CATEGORY_ALIASES folds the rest onto them.
# ---------------------------------------------------------------------------

CATEGORY_STANDARDS: Dict[str, Tuple[StdParam, ...]] = {

    # -- electrical ---------------------------------------------------------
    # The CATEGORY set is what any electrical equipment carries; the three
    # product sets under it extend it with what only that product has.  A
    # caller naming the category gets the common set; a constructor that knows
    # it is building a panelboard names 'panelboard' and gets the schedule
    # parameters too.
    "electrical_equipment": _EE_COMMON,

    "panelboard": _merge((
        _P("PanelName", "text", "identity", origin=ORIGIN_CONTRACT),
        _P("BusRating", "current", "electrical", origin=ORIGIN_CONTRACT),
        _P("MainsType", "text", "electrical", origin=ORIGIN_CONTRACT),
        _P("MainsRating", "current", "electrical", origin=ORIGIN_CONTRACT),
        _P("ShortCircuitRatingkA", "number", "electrical", origin=ORIGIN_CONTRACT),
        _P("NumberOfCircuits", "integer", "electrical", origin=ORIGIN_CONTRACT),
        _P("NeutralRating", "text", "electrical", origin=ORIGIN_CONTRACT),
    ), _EE_COMMON),

    "switchboard": _merge((
        _P("BusRating", "current", "electrical", origin=ORIGIN_CONTRACT),
        _P("MainsType", "text", "electrical", origin=ORIGIN_CONTRACT),
        _P("MainsRating", "current", "electrical", origin=ORIGIN_CONTRACT),
        _P("ShortCircuitRatingkA", "number", "electrical", origin=ORIGIN_CONTRACT),
        _P("Bus Material", "text", "materials", note="copper / aluminium bus"),
        # the lineup's section count under the tagging contract's spelling
        # (SwitchboardSchedule.Sections, rvt.ifc.intent.CONTRACT_KEYS) -- the
        # one make_house_switchboard authors and fills; #642
        _P("Sections", "integer", "electrical", origin=ORIGIN_CONTRACT),
    ), _EE_COMMON),

    "transformer": _merge((
        _P("kVA Rating", "apparent_power", "electrical"),
        _P("Primary Voltage", "voltage", "electrical"),
        _P("Secondary Voltage", "voltage", "electrical"),
        _P("Impedance", "number", "electrical", note="%Z"),
        _P("Temperature Rise", "hvac_temperature", "electrical"),
        _P("Insulation Class", "text", "identity"),
        _P("Taps", "text", "electrical", note="e.g. 2 x 2.5% FCAN, 4 x 2.5% FCBN"),
        _P("Sound Level", "number", "identity", note="dBA"),
        _P("K-Factor", "number", "electrical"),
        # #622: the transformer's ONE weight entry, kept under its legacy name so
        # every transformer (catalog weight or none) names it the same way;
        # _EE_COMMON's ``Operating Weight`` is dropped for this product only.
        _P("Weight", "number", "identity",
           note="lb as a plain number: the catalog weight make_transformer fills; "
                "stands in for the category's Operating Weight (mass) -- one name on "
                "every transformer -- until the factory has a verified lb -> mass "
                "unit path (#630)"),
    ), _without(_EE_COMMON, "Operating Weight")),

    "electrical_fixture": (
        _P("Device Type", "text", "identity"),
        _P("NEMA Configuration", "text", "identity"),
        _P("Number of Poles", "integer", "electrical"),
        _P("Wattage", "wattage", "electrical"),
        _P("Mounting", "text", "identity"),
        _P("Mounting Height", "length", "constraints", instance=True),
        _P("Number of Gangs", "integer", "identity"),
        _P("Backbox Size", "text", "identity"),
        _P("Faceplate Color", "text", "identity"),
        _P("GFCI Protected", "integer", "electrical", note="0/1: no Yes/No spec id "
           "is in our verified set, so this is an integer"),
    ) + _POWER + _CIRCUIT_BUILTINS,

    "lighting_fixture": (
        _P("Luminous Flux", "luminous_flux", "photometrics"),
        _P("Initial Color Temperature", "cct", "photometrics"),
        _P("Color Rendering Index", "number", "photometrics"),
        _P("Light Loss Factor", "number", "photometrics"),
        _P("Efficacy", "efficacy", "photometrics"),
        _P("Wattage", "wattage", "electrical"),
        _P("Lamp", "text", "identity"),
        _P("Number of Lamps", "integer", "identity"),
        _P("Driver Type", "text", "identity", note="ballast / LED driver"),
        _P("Dimming Protocol", "text", "identity", note="0-10V, DALI, phase, none"),
        _P("Mounting", "text", "identity"),
        _P("IP Rating", "text", "identity"),
        _P("Switch ID", "text", "electrical_lighting", instance=True),
        _P("Emergency", "integer", "electrical_lighting",
           note="0/1: no Yes/No spec id is in our verified set"),
    ) + _POWER + _PRODUCT_IDENTITY + _CIRCUIT_BUILTINS,

    "lighting_device": _DEVICE_BASE + (
        _P("Switch ID", "text", "electrical_lighting", instance=True),
        _P("Control Type", "text", "identity", note="toggle, dimmer, occupancy, daylight"),
        _P("Number of Gangs", "integer", "identity"),
    ) + _CIRCUIT_BUILTINS,

    "data_device": _DEVICE_BASE + (
        _P("Number of Ports", "integer", "identity"),
        _P("Cable Category", "text", "identity", note="Cat6, Cat6A, OM4 ..."),
        _P("Jack Color", "text", "identity"),
        _P("Termination Type", "text", "identity"),
        _P("PoE Class", "text", "electrical", note="802.3af/at/bt class"),
    ) + _CIRCUIT_BUILTINS,

    "fire_alarm_device": _DEVICE_BASE + (
        _P("Candela Rating", "number", "electrical"),
        _P("Sound Output", "number", "electrical", note="dBA at 10 ft"),
        _P("Alarm Current", "current", "electrical"),
        _P("Standby Current", "current", "electrical"),
        _P("Addressable", "integer", "identity",
           note="0/1: no Yes/No spec id is in our verified set"),
        _P("Listing", "text", "identity", note="UL 464 / UL 1971 / FM listing"),
    ) + _CIRCUIT_BUILTINS,

    "communication_device": _DEVICE_BASE + (
        _P("Number of Ports", "integer", "identity"),
        _P("Signal Type", "text", "identity"),
    ) + _CIRCUIT_BUILTINS,

    "security_device": _DEVICE_BASE + (
        _P("Field of View", "angle", "identity"),
        _P("Resolution", "text", "identity"),
        _P("PoE Class", "text", "electrical"),
        _P("Detection Range", "length", "identity"),
    ) + _CIRCUIT_BUILTINS,

    "nurse_call_device": _DEVICE_BASE + (
        _P("Station Type", "text", "identity"),
        _P("Number of Ports", "integer", "identity"),
    ) + _CIRCUIT_BUILTINS,

    "telephone_device": _DEVICE_BASE + (
        _P("Number of Ports", "integer", "identity"),
        _P("Jack Type", "text", "identity"),
    ) + _CIRCUIT_BUILTINS,

    # -- electrical containment ---------------------------------------------
    "cable_tray_fitting": (
        _P("Tray Width", "cable_tray_size", "dimensions"),
        _P("Tray Height", "cable_tray_size", "dimensions"),
        _P("Bend Radius", "length", "dimensions"),
        _P("Fitting Angle", "angle", "dimensions"),
        _P("Tray Type", "text", "identity", note="ladder, trough, wire basket, solid"),
        _P("Material", "text", "materials"),
        _P("Finish", "text", "materials"),
        _P("Load Class", "text", "identity", note="NEMA VE 1 load/span class"),
    ),

    "conduit_fitting": (
        _P("Nominal Diameter", "conduit_size", "dimensions"),
        _P("Bend Radius", "length", "dimensions"),
        _P("Fitting Angle", "angle", "dimensions"),
        _P("Conduit Standard", "text", "identity", note="EMT, IMC, RMC, PVC ..."),
        _P("Material", "text", "materials"),
        _P("Finish", "text", "materials"),
    ),

    # -- mechanical / plumbing ---------------------------------------------
    "mechanical_equipment": (
        _P("Air Flow", "air_flow", "mechanical_airflow", instance=True),
        _P("External Static Pressure", "hvac_pressure", "mechanical"),
        _P("Total Cooling Capacity", "cooling_load", "mechanical"),
        _P("Total Heating Capacity", "heating_load", "mechanical"),
        _P("Entering Air Temperature", "hvac_temperature", "mechanical"),
        _P("Leaving Air Temperature", "hvac_temperature", "mechanical"),
        _P("Phases", "integer", "electrical"),
        _P("Frequency", "frequency", "electrical"),
        _P("Full Load Amps", "current", "electrical"),
        _P("Minimum Circuit Ampacity", "current", "electrical"),
        _P("Maximum Overcurrent Protection", "current", "electrical"),
        _P("Sound Level", "number", "identity", note="dBA"),
        _P("Service Clearance", "length", "constraints"),
    ) + _POWER + _PRODUCT_IDENTITY + _CIRCUIT_BUILTINS,

    "plumbing_fixture": (
        _P("Flow Rate", "flow", "plumbing"),
        _P("Cold Water Fixture Units", "number", "plumbing", note="WSFU, cold"),
        _P("Hot Water Fixture Units", "number", "plumbing", note="WSFU, hot"),
        _P("Drainage Fixture Units", "number", "plumbing", note="DFU"),
        _P("Supply Connection Size", "pipe_size", "plumbing"),
        _P("Drain Connection Size", "pipe_size", "plumbing"),
        _P("Vent Connection Size", "pipe_size", "plumbing"),
        _P("Operating Pressure", "piping_pressure", "plumbing"),
        _P("Mounting Height", "length", "constraints", instance=True),
        _P("Accessible", "integer", "identity",
           note="0/1 (ADA/ANSI A117.1); no Yes/No spec id is in our verified set"),
        _P("Finish", "text", "materials"),
    ) + _PRODUCT_IDENTITY,

    "pipe_accessory": (
        _P("Nominal Diameter", "pipe_size", "dimensions"),
        _P("End Connection", "text", "identity", note="flanged, threaded, grooved, solder"),
        _P("Pressure Rating", "piping_pressure", "identity"),
        _P("Temperature Rating", "piping_temperature", "identity"),
        _P("Flow Coefficient", "number", "identity", note="Cv"),
        _P("Material", "text", "materials"),
    ),

    "duct_accessory": (
        _P("Duct Width", "duct_size", "dimensions"),
        _P("Duct Height", "duct_size", "dimensions"),
        _P("Pressure Class", "text", "identity", note="SMACNA pressure class"),
        _P("Leakage Class", "number", "identity"),
        _P("Face Velocity", "hvac_velocity", "mechanical"),
        _P("Material", "text", "materials"),
    ),

    # -- architectural ------------------------------------------------------
    "furniture": (
        _P("Material", "text", "materials"),
        _P("Finish", "text", "materials"),
        _P("Weight", "mass", "identity"),
        _P("Fire Rating", "text", "identity"),
    ),

    "casework": (
        _P("Material", "text", "materials"),
        _P("Finish", "text", "materials"),
        _P("Counter Material", "text", "materials"),
        _P("Counter Height", "length", "dimensions"),
        _P("Hardware Set", "text", "identity"),
    ),

    "specialty_equipment": (
        _P("Utility Requirements", "text", "identity"),
        _P("Service Clearance", "length", "constraints"),
    ) + _POWER + _PRODUCT_IDENTITY,

    "door": (
        _B("Width", "Revit's own Doors built-in"),
        _B("Height", "Revit's own Doors built-in"),
        _B("Thickness", "Revit's own Doors built-in"),
        _B("Rough Width", "Revit's own Doors built-in"),
        _B("Rough Height", "Revit's own Doors built-in"),
        _B("Fire Rating", "Revit's own Doors built-in"),
        _B("Frame Type", "Revit's own Doors built-in"),
        _B("Frame Material", "Revit's own Doors built-in"),
        _B("Finish", "Revit's own Doors built-in"),
        _B("Function", "Revit's own Doors built-in"),
        _B("Head Height", "Revit's own Doors built-in, instance"),
        _P("Door Operation", "text", "identity", note="single swing, double, sliding"),
        _P("Hardware Set", "text", "identity"),
        _P("Acoustic Rating", "text", "identity", note="STC"),
        _P("Glazing", "text", "materials"),
        _P("Undercut", "length", "dimensions"),
        _P("Louver Size", "text", "identity"),
    ),

    "window": (
        _B("Width", "Revit's own Windows built-in"),
        _B("Height", "Revit's own Windows built-in"),
        _B("Rough Width", "Revit's own Windows built-in"),
        _B("Rough Height", "Revit's own Windows built-in"),
        _B("Window Inset", "Revit's own Windows built-in"),
        _B("Finish", "Revit's own Windows built-in"),
        _B("Sill Height", "Revit's own Windows built-in, instance"),
        _P("Operation", "text", "identity", note="fixed, casement, awning, hung"),
        _P("Glazing", "text", "materials"),
        _P("U-Factor", "u_factor", "green_building"),
        _P("Solar Heat Gain Coefficient", "number", "green_building"),
        _P("Visible Transmittance", "number", "green_building"),
        _P("Frame Material", "text", "materials"),
    ),

    # -- structural ---------------------------------------------------------
    "structural_framing": (
        _P("Section Shape", "text", "identity", note="W, HSS, C, L, PL ..."),
        _P("Nominal Depth", "length", "dimensions"),
        _P("Nominal Width", "length", "dimensions"),
        _P("Web Thickness", "length", "dimensions"),
        _P("Flange Thickness", "length", "dimensions"),
        _P("Mass per Unit Length", "mass_per_length", "structural"),
        _P("Material Grade", "text", "materials"),
        _P("Cross-Sectional Area", "area", "structural"),
    ),

    "structural_column": (
        _P("Section Shape", "text", "identity"),
        _P("Nominal Depth", "length", "dimensions"),
        _P("Nominal Width", "length", "dimensions"),
        _P("Web Thickness", "length", "dimensions"),
        _P("Flange Thickness", "length", "dimensions"),
        _P("Mass per Unit Length", "mass_per_length", "structural"),
        _P("Material Grade", "text", "materials"),
        _P("Axial Capacity", "force", "structural"),
    ),

    # -- the catch-all ------------------------------------------------------
    "generic_model": (
        _P("Material", "text", "materials"),
        _P("Finish", "text", "materials"),
        _P("Weight", "mass", "identity"),
    ),
}

#: every spelling ``skeleton._resolve_category`` accepts, folded onto the key
#: the table uses (so ``standards`` and the writer never disagree on what a
#: category IS).
CATEGORY_ALIASES: Dict[str, str] = {
    "generic": "generic_model",
    "panelboard": "electrical_equipment",
    "transformer": "electrical_equipment",
    "switchboard": "electrical_equipment",
    "electrical_fixtures": "electrical_fixture",
    "lighting_fixtures": "lighting_fixture",
    "lighting_devices": "lighting_device",
    "data_devices": "data_device",
    "fire_alarm_devices": "fire_alarm_device",
    "plumbing_fixtures": "plumbing_fixture",
    "pipe_accessories": "pipe_accessory",
    "duct_accessories": "duct_accessory",
    "cable_tray": "cable_tray_fitting",
    "cable_trays": "cable_tray_fitting",
    "conduit": "conduit_fitting",
    "conduits": "conduit_fitting",
    "doors": "door",
    "windows": "window",
}

#: OST id -> canonical key, so an integer category (which ``_resolve_category``
#: passes straight through) still finds its table.
_OST_TO_KEY: Dict[int, str] = {}
for _key in list(CATEGORY_STANDARDS) + list(CATEGORY_ALIASES):
    try:
        _OST_TO_KEY.setdefault(SK._resolve_category(_key),
                               CATEGORY_ALIASES.get(_key, _key))
    except KeyError:                                  # pragma: no cover
        pass


def canonical_category(category: Any) -> str:
    """The table key for a category as any caller may spell it: a canonical
    name, one of ``skeleton``'s aliases, or an integer OST id."""
    if isinstance(category, int):
        return _OST_TO_KEY.get(int(category), f"category {int(category)}")
    key = str(category).lower().replace(" ", "_")
    if key in CATEGORY_STANDARDS:        # a PRODUCT set beats its category's
        return key
    return CATEGORY_ALIASES.get(key, key)


# ---------------------------------------------------------------------------
# reading the table
# ---------------------------------------------------------------------------

def standard_params(category: Any) -> Tuple[StdParam, ...]:
    """Every standard parameter of ``category`` -- authored AND built-in.
    An unknown category returns ``()``; :func:`describe` says so out loud."""
    return CATEGORY_STANDARDS.get(canonical_category(category), ())


def authored_params(category: Any) -> Tuple[StdParam, ...]:
    """Only the ones tekton writes into the family."""
    return tuple(p for p in standard_params(category) if p.authored)


def describe(category: Any) -> Dict[str, Any]:
    """The honest picture of what a family in ``category`` will carry."""
    key = canonical_category(category)
    rows = CATEGORY_STANDARDS.get(key, ())
    d: Dict[str, Any] = {
        "category": key,
        "covered": bool(rows),
        "authored": [p.to_json() for p in rows if p.authored],
        "builtin": [p.to_json() for p in rows if not p.authored],
        "common_builtins": [p.name for p in COMMON_BUILTINS],
    }
    if not rows:
        d["note"] = NO_TABLE_NOTE
    else:
        by_origin: Dict[str, int] = {}
        for p in rows:
            by_origin[p.origin] = by_origin.get(p.origin, 0) + 1
        d["origins"] = by_origin
        d["note"] = (
            f"{len(d['authored'])} parameters authored by tekton as family "
            f"parameters with format-verified spec and group ids; "
            f"{len(d['builtin'])} listed as Revit's own (never authored). "
            f"Names marked '{ORIGIN_CONVENTION}' are the content convention "
            f"for the category and are INFERRED -- a project expecting another "
            f"spelling will not bind to them.")
    return d


def table() -> Dict[str, Any]:
    """The whole table, for a CLI / a doc build."""
    return {
        "categories": {k: describe(k) for k in sorted(CATEGORY_STANDARDS)},
        "aliases": dict(CATEGORY_ALIASES),
        "common_builtins": [p.to_json() for p in COMMON_BUILTINS],
        "origins": {
            ORIGIN_BUILTIN: "Revit provides it; tekton reports it and never authors it",
            ORIGIN_CONTRACT: "the name comes from an in-repo tagging contract",
            ORIGIN_CONVENTION: "the name is the category's content convention (INFERRED)",
        },
    }


# ---------------------------------------------------------------------------
# authoring
# ---------------------------------------------------------------------------

#: the blank value a standard parameter starts at, per storage class.  A
#: standard parameter with no known value is BLANK, never guessed.
def _blank(spec_key: str) -> Any:
    if spec_key == "text":
        return ""
    if spec_key == "integer":
        return 0
    return 0.0


def _offered(values: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """The values a caller actually offered: a ``None`` value is no value."""
    return {str(k): v for k, v in (values or {}).items() if v is not None}


def coerce_value(spec_key: str, value: Any) -> Any:
    """A given value in the storage class its parameter is WRITTEN in.

    ``skeleton.family_param_value`` files a value by its Python type -- str
    -> ``m_str``, int -> ``m_int``, float -> ``m_value`` -- so an int handed
    to a double-spec parameter (JSON ``{"CCT": 3000}``, ``{"Color Rendering
    Index": 90}``) used to sit in the integer slot next to an ``m_value`` of
    0.0, which is what Revit shows (#642).  Here the ENTRY decides: ``text``
    -> str, ``integer`` -> int (a whole number only), every measurable spec
    -> float.  A numeric string is read as the number it spells; anything
    else raises ``ValueError`` / ``TypeError`` and :func:`apply` leaves that
    parameter BLANK and names the value as unusable -- a value is coerced,
    never guessed at."""
    if spec_key == "text":
        return str(value)
    if isinstance(value, bool):
        value = int(value)
    elif isinstance(value, str):
        value = float(value.strip())
    elif not isinstance(value, (int, float)):
        raise TypeError(f"a {type(value).__name__} is not a {spec_key} value")
    if spec_key == "integer":
        if float(value) != int(value):
            raise ValueError(f"{value!r} is not a whole number")
        return int(value)
    return float(value)


def apply(doc: "SK.FamilyDoc", category: Any, *,
          values: Optional[Dict[str, Any]] = None,
          skip: Sequence[str] = (),
          instance_params: bool = True) -> Dict[str, Any]:
    """Author ``category``'s standard parameters into ``doc``.

    ``values`` fills the ones the caller actually knows (by parameter name --
    or any spelling of the same meaning, ``Lumens`` filling ``Luminous Flux``
    -- in INTERNAL units: feet for lengths, the same convention
    ``FamilyDoc.add_family_parameter``'s ``default`` takes); every other
    parameter is authored BLANK, which is the honest state of a fact nobody
    supplied.  A quantity already on the document -- by name (``Width`` on a
    generic model, a constructor's own ``Voltage``) or by MEANING
    (:func:`meaning_key`, #622: a constructor's or a caller's ``Lumens``) -- is
    left exactly as it was made and reported as skipped, naming the spelling
    that carries it; this never redefines a parameter and never adds a blank
    twin.  Two spellings of one quantity in ``values`` fill it once (the
    table's spelling wins, else the first given) and the other is listed in
    ``values_not_placed``.  Each value is written in its entry's storage
    class (:func:`coerce_value`); one that cannot be (``"warm"`` for a colour
    temperature) leaves the parameter BLANK and is named in
    ``values_unusable``.  A ``None`` value is no value: the slot stays blank.

    Returns the report: what was authored, what was skipped and why, and the
    category's note.  Never raises for a merely unknown category (hard rule 1:
    a family still gets built and delivered).
    """
    rep = describe(category)
    rows = standard_params(category)
    table_names = {p.name for p in rows}
    # meaning -> (the caller's spelling, value).  Two spellings of ONE quantity
    # in ``values`` ({"Lumens": .., "Luminous Flux": ..}) cannot both land: the
    # table's own spelling wins, else the first given; the loser is reported in
    # ``values_not_placed`` -- nothing vanishes unannounced.
    vals: Dict[str, Tuple[str, Any]] = {}
    shadowed: List[str] = []
    for name, v in _offered(values).items():
        mk = meaning_key(name)
        if mk not in vals:
            vals[mk] = (name, v)
        elif name in table_names and vals[mk][0] not in table_names:
            shadowed.append(vals[mk][0])
            vals[mk] = (name, v)
        else:
            shadowed.append(name)
    skipped: List[Dict[str, str]] = []
    authored: List[Dict[str, Any]] = []
    unusable: List[Dict[str, str]] = []
    placed: set = set()                                  # meanings whose given value is accounted for
    if doc.finalized:
        raise ValueError("document is finalized; apply standards before finalize")
    present = {meaning_key(n): n for n in doc.params}    # meaning -> the spelling carrying it
    for p in rows:
        if not p.authored:
            continue
        if p.name in skip:
            skipped.append({"name": p.name, "why": "caller asked to skip it"})
            continue
        if not instance_params and p.instance:
            skipped.append({"name": p.name, "why": "instance parameters were not requested"})
            continue
        mk = meaning_key(p.name)
        twin = present.get(mk)
        if twin is not None:
            # by name it is the constructor's own parameter; by meaning it may be
            # a constructor's OR a caller's text parameter -- say what is there
            skipped.append({"name": p.name, "why": "already authored by the constructor"
                            if twin == p.name else
                            f"already on the document as {twin!r} (the same quantity)"})
            continue
        val = _blank(p.spec)
        given = vals.get(mk)                       # (the caller's spelling, value) or None
        if given:
            gname, gv = given
            try:
                val = coerce_value(p.spec, gv)
            except (TypeError, ValueError) as e:   # the slot stays BLANK, the value is named
                unusable.append({"name": gname, "why": f"{gv!r} cannot be written as {p.spec} ({e})"})
                placed.add(mk)
                given = None
        try:
            doc.add_family_parameter(p.name, p.spec_id, p.group_id,
                                     is_instance=p.instance, default=val)
        except Exception as e:                     # never block delivery
            skipped.append({"name": p.name,
                            "why": f"{type(e).__name__}: {str(e)[:120]}"})
            continue
        present[mk] = p.name
        if given:
            placed.add(mk)
        authored.append({"name": p.name, "spec": p.spec, "group": p.group,
                         "instance": p.instance, "origin": p.origin,
                         "value": "given" if given else "blank"})
    rep["applied"] = authored
    rep["skipped"] = skipped
    rep["filled"] = sorted(a["name"] for a in authored if a["value"] == "given")
    unknown = sorted([name for mk, (name, _v) in vals.items() if mk not in placed]
                     + shadowed)
    if unknown:
        rep["values_not_placed"] = unknown
    if unusable:
        rep["values_unusable"] = unusable
    doc.notes.append(
        f"category standards ({rep['category']}): {len(authored)} standard "
        f"parameters authored, {len(rep['filled'])} filled from given facts, "
        f"{len(skipped)} skipped"
        + (f", {len(unusable)} given values unusable ({[u['name'] for u in unusable]})"
           if unusable else "")
        if rep["covered"] else
        f"category standards ({rep['category']}): {NO_TABLE_NOTE}")
    return rep


def apply_safe(doc: "SK.FamilyDoc", category: Any, on: bool = True,
               values: Optional[Dict[str, Any]] = None,
               **kw: Any) -> Optional[Dict[str, Any]]:
    """The standards step EVERY model-family constructor calls (#642) --
    :func:`apply` under the two guarantees a constructor needs.

    ``on`` False (the caller's ``standards=False``, the regression control):
    nothing is authored and ``None`` comes back -- but ``values`` the caller
    offered are standard parameters that will now NOT exist, and that is said
    on the document, naming them, never dropped silently.  ``on`` True: the
    report of :func:`apply`; if this module itself faults, the family is still
    built and delivered with a note saying the standards were not applied and
    why (hard rule 1: a status is a label, never refusal logic).  ``kw`` passes
    ``skip`` / ``instance_params`` through."""
    if not on:
        offered = sorted(_offered(values))
        if offered:
            doc.notes.append(f"standards off ({canonical_category(category)}): the "
                             f"given {offered} are NOT authored (they are standard "
                             f"parameters of the category)")
        return None
    try:
        return apply(doc, category, values=values, **kw)
    except Exception as e:                            # pragma: no cover - never block delivery
        doc.notes.append(f"category standards NOT applied "
                         f"({type(e).__name__}: {str(e)[:120]})")
        return None


# ---------------------------------------------------------------------------
# the provenance gate -- a spec id we cannot source is a test failure
# ---------------------------------------------------------------------------

_UNITS_ASSET = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "assets", "family_units.json")


def units_spec_ids() -> Tuple[str, ...]:
    """Every spec type id the format's OWN units table declares -- the
    ``m_formatOptionsMap`` of ``assets/family_units.json``, which every family
    document we author ships.  This is the source a measurable standard
    parameter's spec id must come from."""
    with open(_UNITS_ASSET, encoding="utf-8") as fh:
        d = json.load(fh)
    return tuple(e["first"]["m_typeId"] for e in d.get("m_formatOptionsMap") or [])


def check_specs() -> List[str]:
    """Every problem in the table, one line each -- empty when it is sound.

    (1) every spec/group key a row uses exists; (2) every MEASURABLE spec id
    is in the format's own units table; (3) no category authors two parameters
    of the same name; (4) no authored name collides with a common built-in;
    (5) no category lists two SPELLINGS of one quantity (#622: ``Lumens`` next
    to ``Luminous Flux`` -- compared by :func:`meaning_key`), and no spelling
    is claimed by two synonym groups.
    """
    problems: List[str] = list(_SYNONYM_CLASHES)
    known = set(units_spec_ids())
    common = {p.name for p in COMMON_BUILTINS}
    for key, rows in CATEGORY_STANDARDS.items():
        by_meaning: Dict[str, List[str]] = {}         # meaning key -> names, repeats kept
        for p in rows:
            by_meaning.setdefault(meaning_key(p.name), []).append(p.name)
            if p.spec not in SPECS:
                problems.append(f"{key}/{p.name}: unknown spec key {p.spec!r}")
                continue
            if p.group not in GROUPS:
                problems.append(f"{key}/{p.name}: unknown group key {p.group!r}")
            if p.authored and p.spec not in NON_MEASURABLE and SPECS[p.spec] not in known:
                problems.append(
                    f"{key}/{p.name}: spec id {SPECS[p.spec]} is not in the format's "
                    f"own units table -- unsourced, remove it or find its id")
            if p.authored and p.name in common:
                problems.append(f"{key}/{p.name}: collides with the common built-in "
                                f"of the same name -- mark it origin={ORIGIN_BUILTIN}")
            if p.origin not in (ORIGIN_BUILTIN, ORIGIN_CONTRACT, ORIGIN_CONVENTION):
                problems.append(f"{key}/{p.name}: unknown origin {p.origin!r}")
        for mk, names in by_meaning.items():
            distinct = list(dict.fromkeys(names))
            if len(distinct) > 1:
                problems.append(f"{key}/{' + '.join(distinct)}: {len(distinct)} spellings "
                                f"of one quantity ({mk!r}) -- keep ONE")
            elif len(names) > 1:
                problems.append(f"{key}/{names[0]}: listed {len(names)} times")
    for alias, key in CATEGORY_ALIASES.items():
        if key not in CATEGORY_STANDARDS:
            problems.append(f"alias {alias!r} points at {key!r}, which has no table")
    return problems


if __name__ == "__main__":                            # pragma: no cover
    import sys
    args = sys.argv[1:]
    if args and args[0] == "--check":
        probs = check_specs()
        for p in probs:
            print(p)
        print(f"{len(CATEGORY_STANDARDS)} categories, {len(SYNONYM_GROUPS)} "
              f"synonym groups, {len(probs)} problems")
        sys.exit(1 if probs else 0)
    if args:
        print(json.dumps(describe(args[0]), indent=1))
    else:
        print(json.dumps(table(), indent=1))

"""MEP TAXONOMY -- every equipment kind the product speaks about, as ONE TABLE (#692).

Each row (a :class:`Kind`) declares, for one kind of MEP equipment:

* the **Revit category** it belongs to, as a key ``rvt.famgen.skeleton._resolve_category``
  resolves (never a numeric id typed here).  The label the row *intends* (``INTENDED_LABEL``)
  is cross-checked against the ids Revit-written files show (``rvt.inventory``'s VERIFIED
  table): :func:`category_status` says ``confirmed`` / ``inferred`` / ``conflict``, and a row in
  conflict never claims to be placeable -- it says which issue tracks the resolver (#516).
  A kind whose category the resolver does not carry at all is a **pending** row (label of the
  category it waits for, no key), so it is known, aliased and honest instead of absent;
* the **standard-parameter table** it carries is the category's own (:mod:`rvt.famgen.standards`);
* the **mechanisms** that can build it here, in priority order (``via``):

  ``famspec:<kind>[/<sub>]``  the famspec lane's constructor for a catalog kind -- available when
                             ``rvt.famgen.vendors`` holds a catalog record for the kind; the tier
                             (``fact`` or ``assumed``) is COMPUTED from that record's provenance,
                             never declared here;
  ``archetype:<key>``        the archetype registry (``rvt.famgen.archetypes``, #674) -- probed,
                             never imported blindly, so such rows say "not on this build" today;
  ``house:<module>:<fn>``    an honest house model at prompt-default or given dimensions
                             (today: the switchboard).

  ``lane`` is derived: ``catalog`` if a famspec mechanism is declared, ``archetype`` if only
  archetype/house mechanisms are, ``none`` otherwise -- and :func:`describe` says in one line
  what builds the kind here or which lane is missing (#692 DONE 3).

This module is TAXONOMY: **no dimensions, ratings or part numbers live here** (steers #685 /
#591 -- model knowledge may supply the taxonomy and standard practice, never a manufacturer's
dimensions).  Manufacturers and lines are the sibling table :mod:`rvt.famgen.vendors`.
Adding a kind is adding a row to ``_ROWS``.  ``python tools/make_family.py taxonomy [KIND]
[--discipline D] [--check] [--json]`` prints it.

Two readers sit on top of the table (#692 DONE 3 / 5): :func:`resolve` maps ONE phrase (an
interview answer, a famspec word) to a row, and :func:`scan` finds every kind a free-text prompt
names -- whole words, plural-tolerant, longest phrase first -- so the prompt grammar
(:mod:`rvt.frontdoor.prompt_intent`) reports each recognised-but-not-built kind with this
table's honest line instead of keeping a product list of its own.  ``Kind.intent`` names the
intent schema's equipment kinds (``rvt.ifc.intent`` ``Equipment.kind``) a row stands for, so the
plan resolver, the prompt grammar and the vendor directory speak about the same kind
(:func:`for_intent_kind`; gated against that schema's vocabulary by :func:`check`).
"""
from __future__ import annotations

import importlib
import importlib.util
import re
from dataclasses import dataclass, asdict
from typing import (Any, Callable, Dict, FrozenSet, Iterable, List, NamedTuple, Optional,
                    Sequence, Tuple)

__all__ = ["Kind", "Mention", "LANES", "DISCIPLINES", "MECHANISMS", "INTENDED_LABEL",
           "AMBIGUOUS_ALONE", "kinds", "keys", "get", "resolve", "scan",
           "for_intent_kind", "by_discipline", "archetype_registry", "category_status",
           "member_model", "facts_tier", "builder_available", "caveat", "describe", "table",
           "check_row", "check"]

LANES = ("catalog", "archetype", "none")
MECHANISMS = ("famspec", "archetype", "house")
DISCIPLINES = ("electrical", "lighting", "fire_alarm", "technology", "mechanical", "plumbing",
               "fire_protection")
#: the issue that owns the resolver's [INFERRED] category ids -- named in every conflict line
RESOLVER_ISSUE = "#516"

#: resolver key -> the Revit category label the row INTENDS.  This is the claim under test,
#: not a copy of a label table: :func:`category_status` checks it against the ids Revit files
#: show.  (``skeleton.category_label`` is writer state feeding the PartAtom and knows only the
#: five desktop-verified ids, so it cannot serve as the presentation label here.)
INTENDED_LABEL = {
    "panelboard": "Electrical Equipment", "switchboard": "Electrical Equipment",
    "transformer": "Electrical Equipment", "electrical_equipment": "Electrical Equipment",
    "electrical_fixture": "Electrical Fixtures", "lighting_fixture": "Lighting Fixtures",
    "lighting_device": "Lighting Devices", "fire_alarm_device": "Fire Alarm Devices",
    "data_device": "Data Devices", "telephone_device": "Telephone Devices",
    "communication_device": "Communication Devices", "security_device": "Security Devices",
    "nurse_call_device": "Nurse Call Devices", "mechanical_equipment": "Mechanical Equipment",
    "duct_accessory": "Duct Accessories", "pipe_accessory": "Pipe Accessories",
    "plumbing_fixture": "Plumbing Fixtures", "cable_tray_fitting": "Cable Tray Fittings",
    "conduit_fitting": "Conduit Fittings", "generic_model": "Generic Models",
}


@dataclass(frozen=True)
class Kind:
    key: str                          # stable snake_case id: "transformer_dry"
    label: str                        # what an engineer calls it
    discipline: str                   # one of DISCIPLINES
    category: Optional[str]           # skeleton._resolve_category key; None on a pending row
    via: Tuple[str, ...] = ()         # build mechanisms, priority order (module docstring)
    aliases: Tuple[str, ...] = ()
    pending: str = ""                 # the Revit category a pending row waits for
    note: str = ""
    refine: Tuple[str, ...] = ()      # a GENERIC word ("light fixture"): the specific rows it
                                      # must be narrowed to before anything is built
    intent: Tuple[str, ...] = ()      # the intent schema's equipment kinds this row stands for
                                      # (rvt.ifc.intent Equipment.kind); first row listed wins


    @property
    def lane(self) -> str:
        mechs = [_mech(m)[0] for m in self.via]
        return "catalog" if "famspec" in mechs else ("archetype" if mechs else "none")

    @property
    def revit_category(self) -> str:
        return INTENDED_LABEL[self.category] if self.category else self.pending


def _mech(m: str) -> Tuple[str, str]:
    kind, _, arg = m.partition(":")
    return kind, arg


def _k(key, label, discipline, category, via=(), *, aliases=(), pending="", note="",
       refine=(), intent=()) -> Kind:
    return Kind(key, label, discipline, category, tuple(via), tuple(aliases), pending, note,
                tuple(refine), tuple(intent))


_HOUSE_SWBD = "house:rvt.ifc.intent:make_house_switchboard"

_ROWS: Tuple[Kind, ...] = (
    # ---------------------------------------------------------------- electrical distribution
    _k("panelboard", "Panelboard", "electrical", "panelboard", ["famspec:panelboard"],
       intent=("panelboard", "distribution_panelboard", "lighting_panelboard",
               "receptacle_panelboard"),
       aliases=("panel", "branch panel", "lighting panel", "power panel", "distribution panel",
                "load center", "distribution panelboard", "lighting panelboard",
                "receptacle panelboard", "appliance panelboard")),
    _k("switchboard", "Switchboard", "electrical", "switchboard", [_HOUSE_SWBD],
       intent=("switchboard",),
       aliases=("main switchboard", "msb", "service switchboard", "distribution switchboard"),
       note="no manufacturer member is held for switchboards: the house model is built at the "
            "prompt lane's default dimensions or the ones the prompt gives"),
    # a switchgear LINEUP is carried as the intent schema's 'switchboard' kind and built as the
    # same house lineup model -- a sectioned enclosure at prompt/default dimensions, no draw-out
    # or metal-clad construction modelled -- and says so; the IFC route's own 'switchgear' kind
    # is IfcSwitchingDevice (a switching DEVICE), which this row does not claim
    _k("switchgear", "Low-voltage switchgear", "electrical", "electrical_equipment",
       [_HOUSE_SWBD], intent=("switchboard",),
       aliases=("lv switchgear", "metal-enclosed switchgear", "metal-clad switchgear"),
       note="built as the house service-board lineup (sections x section width), the same "
            "generic model a switchboard gets: draw-out / metal-clad construction is not "
            "modelled and no manufacturer member is held"),
    _k("transformer_dry", "Dry-type distribution transformer", "electrical", "transformer",
       ["famspec:transformer"], intent=("transformer",),
       aliases=("transformer", "dry type transformer", "step-down transformer", "xfmr",
                "distribution transformer")),
    _k("motor_control_center", "Motor control center", "electrical", "electrical_equipment",
       aliases=("mcc",)),
    _k("disconnect_switch", "Safety / disconnect switch", "electrical", "electrical_equipment",
       aliases=("safety switch", "disconnect", "fused disconnect", "non-fused disconnect")),
    _k("variable_frequency_drive", "Variable frequency drive", "electrical",
       "electrical_equipment", aliases=("vfd", "variable speed drive", "asd", "drive")),
    _k("automatic_transfer_switch", "Automatic transfer switch", "electrical",
       "electrical_equipment", aliases=("ats", "transfer switch")),
    _k("ups", "Uninterruptible power supply", "electrical", "electrical_equipment",
       aliases=("ups system",)),
    _k("generator", "Engine generator set", "electrical", "electrical_equipment",
       aliases=("genset", "standby generator", "emergency generator", "diesel generator")),
    _k("meter_center", "Meter center / metering cabinet", "electrical", "electrical_equipment",
       aliases=("meter", "meter stack", "metering", "ct cabinet", "meter socket")),
    _k("enclosed_circuit_breaker", "Enclosed circuit breaker", "electrical",
       "electrical_equipment", aliases=("ecb", "enclosed breaker")),
    _k("lighting_control_panel", "Lighting control / relay panel", "electrical",
       "electrical_equipment", aliases=("relay panel", "lighting relay panel", "lcp")),
    _k("busway", "Busway / bus duct", "electrical", "electrical_equipment",
       aliases=("bus duct",),
       note="a busway RUN is drawn, not loaded; plug-in units and end fittings are the "
            "loadable parts and are not built yet"),
    _k("cable_tray", "Cable tray (ladder) section", "electrical", "cable_tray_fitting",
       ["archetype:cable_tray"],
       aliases=("ladder tray", "cable ladder", "ladder cable tray", "tray section"),
       note="a loadable ladder-tray SECTION at NEMA VE 1 nominal sizes from the archetype "
            "registry (#591/#674); a routed tray RUN in a project is Revit's system family"),
    _k("cable_tray_fitting", "Cable tray fitting", "electrical", "cable_tray_fitting",
       aliases=("tray elbow", "tray tee", "tray fitting", "tray cross")),
    _k("conduit", "Conduit straight section", "electrical", "conduit_fitting",
       ["archetype:conduit"], aliases=("emt", "rigid conduit", "imc", "conduit run", "raceway"),
       note="a loadable straight SECTION at trade sizes from the archetype registry (#674); a "
            "routed conduit RUN in a project is Revit's system family"),
    _k("conduit_fitting", "Conduit fitting", "electrical", "conduit_fitting",
       aliases=("conduit elbow", "conduit body", "condulet")),
    _k("wireway", "Wireway (lay-in)", "electrical", "electrical_equipment", ["archetype:wireway"],
       aliases=("lay-in wireway", "wire trough", "gutter", "auxiliary gutter")),
    _k("strut_channel", "Strut channel", "electrical", "generic_model",
       ["archetype:strut_channel"],
       aliases=("strut", "unistrut", "channel strut", "trapeze strut")),
    # ---------------------------------------------------------------- wiring devices
    _k("receptacle", "Duplex receptacle", "electrical", "electrical_fixture",
       ["famspec:device/duplex-receptacle"], intent=("receptacle_device",),
       aliases=("outlet", "duplex", "convenience receptacle", "5-15r", "wall outlet",
                "power outlet", "receptacle device")),
    _k("receptacle_20a", "Duplex receptacle, 20 A", "electrical", "electrical_fixture",
       ["famspec:device/duplex-receptacle-20a"], intent=("receptacle_device",),
       aliases=("5-20r", "20a receptacle")),
    _k("light_switch", "Wall switch", "electrical", "electrical_fixture",
       ["famspec:device/switch"],
       aliases=("switch", "toggle switch", "single pole switch", "wall switch")),
    _k("junction_box", "Junction box", "electrical", "electrical_fixture",
       ["famspec:device/junction-box", "archetype:junction_box"],
       aliases=("j-box", "pull box", "4in square box", "box"),
       note="the 4-in device box is a catalog record; larger screw-cover boxes come from the "
            "archetype registry when it is on the build (#674)"),
    _k("floor_box", "Floor box", "electrical", "electrical_fixture",
       aliases=("poke-through", "floor outlet")),
    # ---------------------------------------------------------------- lighting
    # the GENERIC word first: "light fixtures" names a category, not a buildable type -- the
    # row says which types it narrows to (the interview's first question, #684) instead of
    # pretending a generic fixture can be generated
    _k("luminaire", "Luminaire (type not named)", "lighting", "lighting_fixture",
       intent=("light_fixture",),
       refine=("troffer", "downlight", "high_bay", "linear_luminaire", "wall_pack",
               "wall_sconce", "exit_sign", "emergency_light", "pole_light"),
       aliases=("light fixture", "lighting fixture", "light fitting", "led fixture",
                "led luminaire")),
    _k("troffer", "Recessed LED troffer", "lighting", "lighting_fixture",
       ["famspec:luminaire/recessed-troffer"],
       aliases=("recessed troffer", "led troffer", "lay-in fixture", "lay-in", "recessed fixture")),
    _k("downlight", "Recessed LED downlight", "lighting", "lighting_fixture",
       ["famspec:luminaire/downlight"],
       aliases=("can light", "recessed downlight", "recessed can", "pot light")),
    _k("high_bay", "High-bay luminaire", "lighting", "lighting_fixture",
       aliases=("highbay", "low bay", "bay light")),
    _k("linear_luminaire", "Linear / strip luminaire", "lighting", "lighting_fixture",
       aliases=("strip light", "linear pendant", "linear fixture", "wraparound", "wrap")),
    _k("wall_pack", "Exterior wall pack", "lighting", "lighting_fixture",
       aliases=("wallpack", "wall mount area light")),
    _k("wall_sconce", "Wall sconce", "lighting", "lighting_fixture", aliases=("sconce",)),
    _k("exit_sign", "Exit sign", "lighting", "lighting_fixture",
       aliases=("exit light", "egress sign")),
    _k("emergency_light", "Emergency lighting unit", "lighting", "lighting_fixture",
       aliases=("bug eye", "egress light", "frog eyes")),
    _k("pole_light", "Site / area pole luminaire", "lighting", "lighting_fixture",
       aliases=("area light", "parking lot light", "site light", "pole fixture")),
    _k("occupancy_sensor", "Occupancy / vacancy sensor", "lighting", "lighting_device",
       aliases=("motion sensor", "vacancy sensor", "occ sensor", "ceiling sensor")),
    _k("dimmer_switch", "Dimmer", "lighting", "lighting_device",
       aliases=("wall dimmer", "dimming switch")),
    _k("daylight_sensor", "Daylight / photo sensor", "lighting", "lighting_device",
       aliases=("photocell", "photosensor", "daylight harvesting sensor")),
    # ---------------------------------------------------------------- fire alarm
    _k("smoke_detector", "Smoke detector", "fire_alarm", "fire_alarm_device",
       aliases=("smoke", "photoelectric detector", "smoke alarm")),
    _k("heat_detector", "Heat detector", "fire_alarm", "fire_alarm_device",
       aliases=("rate of rise detector", "thermal detector")),
    _k("pull_station", "Manual pull station", "fire_alarm", "fire_alarm_device",
       aliases=("manual station", "fire alarm pull")),
    _k("horn_strobe", "Notification appliance (horn / strobe)", "fire_alarm",
       "fire_alarm_device",
       aliases=("strobe", "horn", "speaker strobe", "notification appliance")),
    _k("duct_smoke_detector", "Duct smoke detector", "fire_alarm", "fire_alarm_device",
       aliases=("duct detector",)),
    _k("fire_alarm_control_panel", "Fire alarm control panel", "fire_alarm",
       "fire_alarm_device", aliases=("facp", "fire alarm panel", "facu")),
    # ---------------------------------------------------------------- technology / low voltage
    _k("data_outlet", "Data / telecom outlet", "technology", "data_device",
       aliases=("data jack", "network outlet", "telecom outlet", "data drop", "rj45 outlet",
                "data device")),
    _k("telephone_outlet", "Telephone outlet", "technology", "telephone_device",
       aliases=("phone jack", "voice outlet")),
    _k("speaker", "Speaker / intercom station", "technology", "communication_device",
       aliases=("intercom", "paging speaker", "ceiling speaker", "pa speaker")),
    _k("card_reader", "Access-control card reader", "technology", "security_device",
       aliases=("badge reader", "access reader", "prox reader")),
    _k("security_camera", "Security camera", "technology", "security_device",
       aliases=("cctv", "camera", "ip camera", "dome camera")),
    _k("intrusion_detector", "Intrusion motion detector", "technology", "security_device",
       aliases=("pir", "glass break", "door contact")),
    _k("nurse_call_station", "Nurse call station", "technology", "nurse_call_device",
       aliases=("nurse call", "patient station", "code blue station", "pull cord station")),
    # ---------------------------------------------------------------- mechanical
    _k("air_handling_unit", "Air handling unit", "mechanical", "mechanical_equipment",
       aliases=("ahu", "air handler", "make-up air unit", "mau", "doas")),
    _k("rooftop_unit", "Packaged rooftop unit", "mechanical", "mechanical_equipment",
       aliases=("rtu", "packaged unit", "rooftop")),
    _k("fan_coil_unit", "Fan coil unit", "mechanical", "mechanical_equipment",
       aliases=("fcu", "fan coil")),
    _k("vav_box", "VAV terminal unit", "mechanical", "mechanical_equipment",
       aliases=("vav", "terminal unit", "fan powered box", "vav terminal")),
    _k("exhaust_fan", "Fan (exhaust / supply / inline)", "mechanical", "mechanical_equipment",
       aliases=("fan", "inline fan", "roof exhauster", "utility set", "supply fan")),
    _k("pump", "Pump", "mechanical", "mechanical_equipment",
       aliases=("hydronic pump", "circulator", "end suction pump", "inline pump",
                "booster pump", "base mounted pump")),
    _k("boiler", "Boiler", "mechanical", "mechanical_equipment",
       aliases=("hot water boiler", "condensing boiler", "steam boiler")),
    _k("chiller", "Chiller", "mechanical", "mechanical_equipment",
       aliases=("air cooled chiller", "water cooled chiller", "centrifugal chiller")),
    _k("cooling_tower", "Cooling tower", "mechanical", "mechanical_equipment",
       aliases=("fluid cooler", "evaporative cooler")),
    _k("unit_heater", "Unit heater", "mechanical", "mechanical_equipment",
       aliases=("cabinet unit heater", "cuh", "gas unit heater")),
    _k("split_system", "Split system (condensing unit + indoor unit)", "mechanical",
       "mechanical_equipment",
       aliases=("condensing unit", "mini split", "heat pump", "dx split", "vrf")),
    _k("energy_recovery_unit", "Energy recovery ventilator", "mechanical",
       "mechanical_equipment", aliases=("erv", "hrv", "energy recovery")),
    _k("expansion_tank", "Expansion tank", "mechanical", "mechanical_equipment",
       aliases=("compression tank",)),
    _k("fire_damper", "Fire / smoke damper", "mechanical", "duct_accessory",
       aliases=("smoke damper", "fire smoke damper", "fsd")),
    _k("volume_damper", "Balancing / volume damper", "mechanical", "duct_accessory",
       aliases=("balancing damper", "manual damper", "mvd")),
    _k("air_terminal", "Diffuser / grille / register", "mechanical", None,
       pending="Air Terminals",
       aliases=("diffuser", "grille", "register", "supply diffuser", "return grille")),
    _k("duct_run", "Duct run", "mechanical", None, pending="Ducts (a system family drawn in "
       "the project, never a loadable .rfa)", aliases=("duct", "ductwork")),
    # ---------------------------------------------------------------- plumbing
    _k("water_heater", "Water heater", "plumbing", "mechanical_equipment",
       aliases=("domestic water heater", "dwh", "tank water heater", "tankless water heater"),
       note="placed under Mechanical Equipment (long-standing practice); Revit 2022+ also "
            "offers Plumbing Equipment, which the resolver does not carry yet"),
    _k("water_closet", "Water closet", "plumbing", "plumbing_fixture",
       aliases=("toilet", "wc", "flush valve water closet")),
    _k("urinal", "Urinal", "plumbing", "plumbing_fixture"),
    _k("lavatory", "Lavatory", "plumbing", "plumbing_fixture",
       aliases=("lav", "bathroom sink", "hand sink", "wall hung lavatory")),
    _k("sink", "Sink (kitchen / service / mop)", "plumbing", "plumbing_fixture",
       aliases=("kitchen sink", "service sink", "mop sink", "utility sink")),
    _k("drinking_fountain", "Drinking fountain / bottle filler", "plumbing",
       "plumbing_fixture", aliases=("water cooler", "bottle filler", "ewc")),
    _k("shower", "Shower", "plumbing", "plumbing_fixture", aliases=("shower stall",)),
    _k("floor_drain", "Floor drain", "plumbing", "plumbing_fixture",
       aliases=("fd", "area drain", "floor sink", "trench drain")),
    _k("backflow_preventer", "Backflow preventer", "plumbing", "pipe_accessory",
       aliases=("rpz", "double check valve", "dcva", "reduced pressure zone")),
    _k("pressure_reducing_valve", "Pressure reducing valve", "plumbing", "pipe_accessory",
       aliases=("prv", "pressure regulator")),
    _k("valve", "Valve (ball / gate / butterfly / check)", "plumbing", "pipe_accessory",
       aliases=("ball valve", "gate valve", "butterfly valve", "check valve",
                "isolation valve")),
    _k("grease_interceptor", "Grease interceptor", "plumbing", None,
       pending="Plumbing Equipment (Revit 2022+)", aliases=("grease trap",)),
    _k("pipe_run", "Pipe run", "plumbing", None, pending="Pipes (a system family drawn in "
       "the project, never a loadable .rfa)", aliases=("pipe", "piping")),
    # ---------------------------------------------------------------- fire protection
    _k("fire_pump", "Fire pump", "fire_protection", "mechanical_equipment",
       aliases=("jockey pump", "fire pump skid")),
    _k("sprinkler", "Sprinkler head", "fire_protection", None, pending="Sprinklers",
       aliases=("sprinkler head", "fire sprinkler", "pendent sprinkler", "upright sprinkler")),
)

_BY_KEY: Dict[str, Kind] = {k.key: k for k in _ROWS}


def _fold(text: Any) -> str:
    """Case / space / hyphen / punctuation-insensitive form (same folding as
    ``standards._fold``; kept local so importing the taxonomy stays a 2 ms affair)."""
    return "".join(ch for ch in str(text).lower() if ch.isalnum())


def _alias_index(rows: Sequence[Any], names: Callable[[Any], Iterable[str]]
                 ) -> Tuple[Dict[str, str], List[str]]:
    """Folded name -> row key over every name ``names(row)`` yields, plus the clashes (two
    rows claiming one folded name).  Shared with :mod:`rvt.famgen.vendors`."""
    index: Dict[str, str] = {}
    clashes: List[str] = []
    for row in rows:
        for name in names(row):
            f = _fold(name)
            if not f:
                continue
            owner = index.setdefault(f, row.key)
            if owner != row.key:
                clashes.append(f"alias {name!r} claimed by both {owner!r} and {row.key!r}")
    return index, clashes


def _names(row: Kind) -> Tuple[str, ...]:
    return (row.key, row.label) + row.aliases


_ALIAS, _ALIAS_CLASHES = _alias_index(_ROWS, _names)


def kinds() -> Tuple[Kind, ...]:
    """Every row, in table order (pending rows included -- see ``Kind.pending``)."""
    return _ROWS


def keys() -> Tuple[str, ...]:
    return tuple(_BY_KEY)


def get(key: str) -> Kind:
    """The row for an exact key (KeyError otherwise) -- :func:`resolve` takes free text."""
    return _BY_KEY[key]


def resolve(text: Any) -> Optional[Kind]:
    """Free text -> row by key, label or alias (case/space/hyphen/plural-insensitive); None
    when the taxonomy does not know the words.  Whole-phrase on purpose: the prompt grammar
    decides what a phrase is (:func:`scan` finds phrases), this table decides what a KIND is."""
    key = next((_ALIAS[c] for c in _singulars(_fold(text)) if c in _ALIAS), "")
    return _BY_KEY.get(key)


#: intent equipment kind -> the row that stands for it (``Kind.intent``; the first row in table
#: order wins, so 'receptacle_device' is the plain receptacle although the 20 A member also
#: rides that kind).  The prompt grammar derives from it which rows the room build models; the
#: plan resolver reads the vendor directory through it.
_BY_INTENT: Dict[str, Kind] = {}
for _row in _ROWS:
    for _ik in _row.intent:
        _BY_INTENT.setdefault(_ik, _row)


def for_intent_kind(kind: Any) -> Optional[Kind]:
    """The row an intent equipment kind ('lighting_panelboard', 'transformer', 'light_fixture')
    stands for; None for kinds that are not equipment rows (walls, room shells, supports)."""
    return _BY_INTENT.get(str(kind))


#: single words that ARE a kind when they are the whole answer (:func:`resolve`) but are not
#: evidence of one inside a sentence (:func:`scan`): 'box', 'switch', 'drive', 'meter' ... read
#: as English far more often than as equipment, and 'panel' / 'outlet' belong to the prompt
#: grammar's own clauses.  A longer phrase containing them ('pull box', 'transfer switch',
#: 'meter socket') is matched as always.
AMBIGUOUS_ALONE: FrozenSet[str] = frozenset({
    "box", "switch", "drive", "smoke", "register", "wrap", "gutter", "meter", "panel", "outlet",
    "duct", "pipe", "horn"})


class Mention(NamedTuple):
    """One kind (or vendor) a text names: ``text[start:end]`` is the phrase as written."""
    start: int
    end: int
    key: str
    text: str


_WORD = re.compile(r"[a-z0-9]+(?:[-'./&][a-z0-9]+)*")
_MAX_WORDS = 5


def _singulars(word: str) -> Iterable[str]:
    """The word and its plausible singulars ('trays' -> 'tray', 'boxes' -> 'box', 'assemblies'
    -> 'assembly'); every candidate is tried against the index, so a wrong guess costs nothing."""
    yield word
    if len(word) > 3:
        if word.endswith("ies"):
            yield word[:-3] + "y"
        if word.endswith("es"):
            yield word[:-2]
        if word.endswith("s") and not word.endswith("ss"):
            yield word[:-1]


def _match_at(text: str, toks: Sequence[Tuple[int, int, str]], i: int, index: Dict[str, str],
              ambiguous: FrozenSet[str], proper: bool) -> Optional[Tuple[Mention, int]]:
    """The longest name in ``index`` starting at token ``i`` -> (mention, tokens used)."""
    for n in range(min(_MAX_WORDS, len(toks) - i), 0, -1):
        words = [t[2] for t in toks[i:i + n]]
        head = "".join(words[:-1])
        for last in _singulars(words[-1]):
            folded = _fold(head + last)
            key = index.get(folded)
            if key is None:
                continue
            if n == 1 and folded in ambiguous and not (proper and text[toks[i][0]].isupper()):
                continue
            start, end = toks[i][0], toks[i + n - 1][1]
            return Mention(start, end, key, text[start:end]), n
    return None


def _scan(text: Any, index: Dict[str, str], *, ambiguous: FrozenSet[str] = frozenset(),
          proper: bool = False) -> List[Mention]:
    """Every phrase of ``text`` (up to five words) whose folded form is a name in ``index``:
    whole words only, plural-tolerant, longest phrase first, left to right, non-overlapping.
    A one-word hit whose folded form is in ``ambiguous`` is skipped -- unless ``proper`` and
    the word is Capitalised as written (a maker's name is a proper noun: 'Carrier', 'Watts').
    Shared with :mod:`rvt.famgen.vendors`."""
    text = str(text or "")
    toks = [(m.start(), m.end(), m.group()) for m in _WORD.finditer(text.lower())]
    out: List[Mention] = []
    i = 0
    while i < len(toks):
        hit = _match_at(text, toks, i, index, ambiguous, proper)
        if hit is None:
            i += 1
        else:
            out.append(hit[0])
            i += hit[1]
    return out


def scan(text: Any) -> List[Mention]:
    """Every kind ``text`` names, as :class:`Mention` s in text order (see :func:`_scan`).  The
    prompt grammar decides what to DO with a mention (build it, shield it from the panel
    grammar, record it as not built); this table only says what kind the words are."""
    return _scan(text, _ALIAS, ambiguous=AMBIGUOUS_ALONE)


def by_discipline(discipline: Optional[str] = None) -> Dict[str, Tuple[Kind, ...]]:
    out: Dict[str, List[Kind]] = {}
    for row in _ROWS:
        if discipline in (None, row.discipline):
            out.setdefault(row.discipline, []).append(row)
    return {d: tuple(v) for d, v in out.items()}


# --------------------------------------------------------------------------- authorities

def archetype_registry() -> Optional[Dict[str, Any]]:
    """``rvt.famgen.archetypes.ARCHETYPES`` (key -> archetype, each with a ``category``) when
    that module is on this build, else None -- probed on every call, never imported at module
    load (#674 is not merged at the time of writing)."""
    try:
        mod = importlib.import_module("rvt.famgen.archetypes")
    except ImportError:
        return None
    reg = getattr(mod, "ARCHETYPES", None)
    return reg if isinstance(reg, dict) else None


def category_status(row: Kind) -> Tuple[str, str]:
    """(status, detail): ``pending`` (no resolver key yet), ``conflict`` (Revit-written files
    put this id or this label elsewhere -- the row must not claim placeability), ``confirmed``
    (a Revit-written file corroborates id AND label) or ``inferred`` (only the published
    constants speak for it).  Evidence: ``rvt.inventory.BUILTIN_CATEGORIES_VERIFIED`` (ids
    corroborated by sample elements) outranks ``..._ASSUMED`` (recalled constants, hints)."""
    if row.category is None:
        return "pending", (f"{row.pending} is not a category the engine's resolver carries yet; "
                           f"the kind is known to the taxonomy but neither placeable nor "
                           f"buildable here")
    from . import skeleton as _SK
    from .. import inventory as _INV
    cid = _SK._resolve_category(row.category)
    want = row.revit_category
    verified = {i: lab for i, (_ost, lab) in _INV.BUILTIN_CATEGORIES_VERIFIED.items()}
    if verified.get(cid) == want:
        return "confirmed", f"{want} = {cid}, corroborated by Revit-written sample elements"
    if cid in verified:
        return "conflict", (f"the resolver maps {row.category!r} to {cid}, an id Revit-written "
                            f"files show as {verified[cid]!r}, not {want!r} ({RESOLVER_ISSUE})")
    other = [i for i, lab in verified.items() if lab == want]
    if other:
        return "conflict", (f"the resolver maps {row.category!r} to {cid} but Revit-written "
                            f"files put {want!r} at {other[0]} ({RESOLVER_ISSUE})")
    assumed = {i: lab for i, (_ost, lab) in _INV.BUILTIN_CATEGORIES_ASSUMED.items()}
    if assumed.get(cid) == want:
        hint = "; the published-constant table agrees"
    else:
        parts = ([f"names {cid} {assumed[cid]!r}"] if cid in assumed else []) + \
                [f"puts {want!r} at {i}" for i, lab in assumed.items() if lab == want]
        hint = f"; the published-constant table {' and '.join(parts)}" if parts else ""
    return "inferred", (f"{want} = {cid} is the resolver's [INFERRED] id, not yet corroborated "
                        f"by a Revit-written file ({RESOLVER_ISSUE}){hint}")


def _famspec_parts(row: Kind) -> Tuple[Optional[str], Optional[str]]:
    """(famspec kind, sub-kind) of the row's first famspec mechanism, or (None, None)."""
    for m in row.via:
        kind, arg = _mech(m)
        if kind == "famspec":
            fam, _, sub = arg.partition("/")
            return fam, (sub or None)
    return None, None


def member_model(kind: Any) -> Optional[str]:
    """The catalog variant ``model`` the kind's sub-kind selects, or None (= every variant of
    the kind's records is the member, e.g. a luminaire line holds only that fixture; also None
    for a key the table does not know).  Device sub-kinds share ONE record, so the member is
    the factory's own ``DEVICE_KINDS`` mapping -- imported lazily, only for those rows, so the
    selection is never a second copy.  ``kind`` is a key or a :class:`Kind` row."""
    row = kind if isinstance(kind, Kind) else _BY_KEY.get(str(kind))
    if row is None:
        return None
    fam, sub = _famspec_parts(row)
    if fam == "device" and sub:
        from . import factory as _F
        return _F.DEVICE_KINDS[_F.device_kind(sub)]["model"]
    return None


def facts_tier(kind: Any) -> Tuple[Optional[str], List[Tuple[str, str]], int, Optional[str]]:
    """(tier, records, fact_fields, model) for THE MEMBER a kind builds: ``fact`` when the variant(s)
    the kind selects carry at least one fact-tier field, ``assumed`` when a record is held but
    every one of the member's values is search-summary / assumed, None when no record is held.
    Counted from the records' own ``field_provenance`` (``vendors.record_tier``).  ``kind``
    is a key or a :class:`Kind` row."""
    from . import vendors as _V
    row = kind if isinstance(kind, Kind) else _BY_KEY[kind]
    records = _V.records_for_kind(row.key)
    if not records:
        return None, [], 0, None
    model = member_model(row)
    facts = sum(_V.record_tier(v, ln, model=model)["fields_fact"] for v, ln in records)
    return ("fact" if facts else "assumed"), records, facts, model


def _mechanism_available(row: Kind, mech: str, strict: bool) -> Tuple[bool, str]:
    kind, arg = _mech(mech)
    if kind == "famspec":
        try:
            tier, records, n_fact, model = facts_tier(row)
        except Exception as e:                # noqa: BLE001 -- a record that fails to load is
            from .._clause import cause_clause                     # a finding, never a traceback
            return False, f"a catalog record held for {row.key!r} does not load ({cause_clause(e)})"
        if not records:
            return False, f"no catalog record is held for {row.key!r} (rvt.famgen.vendors)"
        if strict:
            from ..frontdoor import famspec as _FS
            if _import_attr(_FS.constructor_name(arg.partition("/")[0])) is None:
                return False, f"constructor for famspec kind {arg!r} is not importable"
        recs = ", ".join(f"{v}/{ln}" for v, ln in records)
        member = f"variant {model} carries" if model else (
            "the record carries" if len(records) == 1 else "the records carry")
        if tier == "fact":
            return True, f"catalog lane from {recs} ({member} {n_fact} fact-tier fields)"
        return True, (f"catalog lane from {recs} -- {member} NO fact-tier field: the values "
                      f"are search-summary `assumed`, and the family says so")
    if kind == "archetype":
        reg = archetype_registry()
        if reg is None:
            return False, ("archetype registry (rvt.famgen.archetypes, #674) is not on this "
                           "build -- the kind is known but cannot be generated here yet")
        if arg not in reg:
            return False, f"archetype {arg!r} is not in the registry on this build"
        cat = getattr(reg[arg], "category", None)      # a shape without .category is drift too
        if cat != row.category:
            return False, (f"archetype {arg!r} builds category {cat!r}, the row says "
                           f"{row.category!r}")
        return True, f"archetype lane ({arg}) at the registry's nominal sizes, overridable"
    if kind == "house":
        mod, _, fn = arg.rpartition(":")
        if not (mod == "rvt" or mod.startswith("rvt.")):
            return False, f"house builder {arg} is not one of ours (an rvt. module is required)"
        if strict:
            ok = callable(_import_attr(arg))
        else:
            try:
                ok = importlib.util.find_spec(mod) is not None
            except (ImportError, ValueError):
                ok = False
        if not ok:
            return False, f"house builder {arg} is not on this build (no such callable)"
        return True, (f"house model ({fn}) at the prompt lane's default dimensions or the "
                      f"ones the prompt gives (nominal / given) -- no manufacturer member")
    return False, f"unknown mechanism {mech!r}"


def _import_attr(dotted: str) -> Optional[Any]:
    mod, _, attr = dotted.rpartition(":")
    try:
        return getattr(importlib.import_module(mod), attr, None)
    except ImportError:
        return None


def builder_available(row: Kind, *, strict: bool = False) -> Tuple[bool, str]:
    """(available, why) on THIS build: the category must be usable (not pending, not in
    conflict), then the first mechanism in ``via`` that is available wins.  ``strict``
    imports constructors to prove them (what :func:`check` does); the default probes cheaply
    so a surface can describe a kind without loading the factory."""
    status, detail = category_status(row)
    if status in ("pending", "conflict"):
        return False, detail
    if row.refine:
        fine = [(_BY_KEY[k].label, builder_available(_BY_KEY[k], strict=strict)[0])
                for k in row.refine]
        groups = (([lb for lb, ok in fine if ok], "buildable here"),
                  ([lb for lb, ok in fine if not ok], "known, not buildable here yet"))
        return False, "a generic word -- name the type: " + "; ".join(
            f"{', '.join(labels)} ({what})" for labels, what in groups if labels)
    if not row.via:
        return False, (f"{row.label} is placed under {row.revit_category}, but no lane builds "
                       f"it yet: no catalog record is held and no archetype generates it")
    whys = []
    for mech in row.via:
        ok, why = _mechanism_available(row, mech, strict)
        if ok:
            return True, why
        whys.append(why)
    return False, "; ".join(whys)


def caveat(row: Kind) -> str:
    """The bracketed category caveat every surface appends for an [INFERRED] id (pending and
    conflicting rows lead with their finding instead, confirmed ones need none)."""
    status, detail = category_status(row)
    return f" [category id {status}: {detail}]" if status == "inferred" else ""


def describe(text: Any) -> Dict[str, Any]:
    """One kind as a JSON-able dict with availability computed live and the ONE honest line
    a surface relays (``line``).  Unknown text -> ``{"known": False, "line": ...}``."""
    row = resolve(text)
    if row is None:
        return {"known": False, "query": str(text),
                "line": (f"'{text}' is not a kind the MEP taxonomy knows "
                         f"({len(_ROWS)} kinds across {', '.join(DISCIPLINES)})")}
    from . import standards as _S
    status, detail = category_status(row)
    ok, why = builder_available(row)
    n_std = len(_S.standard_params(row.category)) if row.category else 0
    d = asdict(row)
    d.update({"known": True, "lane": row.lane, "revit_category": row.revit_category,
              "category_status": status, "category_detail": detail, "available": ok,
              "availability": why, "standards_count": n_std})
    head = f"{row.label}: {row.revit_category}"
    if ok:
        d["line"] = f"{head}; {why}; {n_std} standard parameters{caveat(row)}"
    else:
        d["line"] = f"{head}; NOT buildable here -- {why}{caveat(row)}"
    return d


def table() -> Dict[str, Any]:
    """The whole taxonomy, JSON-able (what ``make_family.py taxonomy --json`` prints)."""
    rows = [describe(r.key) for r in _ROWS]
    reg = archetype_registry()
    return {"kinds": rows, "count": len(rows),
            "by_discipline": {d: [r.key for r in rs] for d, rs in by_discipline().items()},
            "by_lane": {ln: [r["key"] for r in rows if r["lane"] == ln] for ln in LANES},
            "by_category_status": {s: [r["key"] for r in rows if r["category_status"] == s]
                                   for s in ("confirmed", "inferred", "conflict", "pending")},
            "available": [r["key"] for r in rows if r["available"]],
            "archetype_registry": None if reg is None else sorted(reg)}


# --------------------------------------------------------------------------- the gate

def check_row(row: Kind) -> List[str]:
    """Problems this ONE row has (empty = honest).  :func:`check` runs it over the table; the
    tests feed it deliberately broken rows."""
    from . import skeleton as _SK, standards as _S
    tag = f"taxonomy[{row.key}]"
    problems: List[str] = []
    if row.discipline not in DISCIPLINES:
        problems.append(f"{tag}: discipline {row.discipline!r} not in {DISCIPLINES}")
    if row.category is None:
        if not row.pending:
            problems.append(f"{tag}: neither a category key nor a pending category label")
        elif row.pending in INTENDED_LABEL.values():
            keys = sorted(k for k, v in INTENDED_LABEL.items() if v == row.pending)
            problems.append(f"{tag}: pending label {row.pending!r} is a category the resolver "
                            f"already carries ({', '.join(keys)}) -- give the row that key")
        else:
            try:
                _SK._resolve_category(row.pending)
                problems.append(f"{tag}: pending label {row.pending!r} resolves through "
                                f"skeleton._resolve_category -- the row is not pending, key it")
            except Exception:                            # noqa: BLE001 -- unresolvable = pending
                pass
        if row.via or row.refine:
            problems.append(f"{tag}: a pending row cannot declare build mechanisms {row.via} "
                            f"or refinements {row.refine}")
        return problems
    if row.pending:
        problems.append(f"{tag}: has a category key AND a pending label -- pick one")
    if row.refine:
        if row.via:
            problems.append(f"{tag}: a generic (refine) row cannot declare build mechanisms")
        for k in row.refine:
            fine = _BY_KEY.get(k)
            if fine is None:
                problems.append(f"{tag}: refines to unknown kind {k!r}")
            elif fine.refine or fine.key == row.key:
                problems.append(f"{tag}: refines to {k!r}, which is itself generic")
            elif fine.category != row.category:
                problems.append(f"{tag}: refines to {k!r} of category {fine.category!r}, not "
                                f"{row.category!r} -- a generic word never changes category")
    if row.category not in INTENDED_LABEL:
        problems.append(f"{tag}: category {row.category!r} has no INTENDED_LABEL entry")
    try:
        cid = _SK._resolve_category(row.category)
        if not isinstance(cid, int) or cid >= 0:
            problems.append(f"{tag}: category {row.category!r} resolved to {cid!r}")
    except Exception as e:                               # noqa: BLE001 -- report, don't raise
        problems.append(f"{tag}: category {row.category!r} does not resolve ({e})")
    if _S.canonical_category(row.category) not in _S.CATEGORY_STANDARDS:
        problems.append(f"{tag}: no standard-parameter table for {row.category!r}")
    from ..frontdoor import famspec as _FS
    for mech in row.via:
        kind, arg = _mech(mech)
        if kind not in MECHANISMS or not arg:
            problems.append(f"{tag}: malformed mechanism {mech!r}")
            continue
        if kind == "famspec":
            fam, _, sub = arg.partition("/")
            bad = None
            if fam not in _FS.CATALOG_KINDS:
                bad = f"famspec kind {fam!r} not in {_FS.CATALOG_KINDS}"
            elif bool(sub) != (fam in _FS.OWN_KIND_FIELD):
                bad = f"famspec kind {fam!r} {'needs' if fam in _FS.OWN_KIND_FIELD else 'takes no'} sub-kind"
            elif sub and sub not in _sub_kinds(fam):
                bad = f"famspec sub-kind {sub!r} is not one make_{fam} knows {sorted(_sub_kinds(fam))}"
            if bad:
                problems.append(f"{tag}: {bad}")
                continue
            problems.extend(f"{tag}: {p}" for p in _record_problems(row, fam, sub or None))
        ok, why = _mechanism_available(row, mech, strict=True)
        if not ok and not (kind == "archetype" and archetype_registry() is None):
            problems.append(f"{tag}: {why}")          # an ABSENT registry is #674, not a lie
    return problems


def _sub_kinds(fam: str) -> Tuple[str, ...]:
    """The sub-kinds a famspec constructor accepts -- read from the factory's own tables."""
    from . import factory as _F
    return tuple({"device": _F.DEVICE_KINDS, "luminaire": _F._LUM_KINDS}.get(fam, {}))


def _constructor_records(fam: str, sub: Optional[str]) -> set:
    """The (vendor, line) records the famspec constructor for ``fam``/``sub`` actually reads,
    from the factory's own registries (strict path only: the factory is already imported)."""
    from . import factory as _F
    if fam == "panelboard":
        return set(_F._PANEL_LINES.values())
    if fam == "transformer":
        return set(_F._XFMR_LINES.values())
    if fam == "luminaire":
        return {_F._LUM_KINDS[sub]} if sub in _F._LUM_KINDS else set()
    if fam == "device":
        return {_F._DEVICE_LINE}
    return set()


def _record_problems(row: Kind, fam: str, sub: Optional[str]) -> List[str]:
    """The directory's records for the kind must be exactly the ones the constructor reads,
    its DEFAULT record the one the constructor's own signature defaults name, and each record
    must agree with the row (``vendors.record_row_problems`` -- the one gate both tables'
    checks share) -- else describe() would report the tier of a record the build never
    touches (review of #735)."""
    from . import vendors as _V
    held = set(_V.records_for_kind(row.key))
    reads = _constructor_records(fam, sub)
    out = []
    if held != reads:
        out.append(f"directory records {sorted(held)} != the records make_{fam}"
                   f"{'/' + sub if sub else ''} reads {sorted(reads)}")
    built_in = _constructor_default(fam)
    if built_in is not None and built_in != _V.default_record(row.key):
        out.append(f"directory default {_V.default_record(row.key)} != the record make_{fam}'s "
                   f"own defaults name {built_in}")
    model = member_model(row)
    for v, ln in sorted(held):
        out.extend(_V.record_row_problems(v, ln, row, model=model))
    return out


def _constructor_default(fam: str) -> Optional[Tuple[str, str]]:
    """The (vendor, line) record a famspec constructor builds from when called with its own
    default arguments -- read from the factory's signature, not restated."""
    import inspect
    from . import factory as _F
    if fam == "panelboard":
        ps = inspect.signature(_F.make_panelboard).parameters
        return _F._PANEL_LINES.get((ps["vendor"].default, ps["line"].default))
    if fam == "transformer":
        return _F._XFMR_LINES.get(inspect.signature(_F.make_transformer).parameters["vendor"].default)
    if fam == "device":
        return _F._DEVICE_LINE
    return None


def check() -> List[str]:
    """Problems that make the table dishonest (empty list = clean).  Per #692: every row's
    category resolves through ``skeleton._resolve_category`` and has a standard-parameter
    table; every famspec mechanism names a real famspec kind, an importable constructor and a
    held catalog record; every house builder imports; keys and aliases are unambiguous.
    Category *conflicts* are the resolver's (#516) and are reported by ``taxonomy --check``
    as warnings, not counted here -- the rows already refuse to claim placeability."""
    problems = list(_ALIAS_CLASHES)
    if len(_BY_KEY) != len(_ROWS):
        problems.append("taxonomy: duplicate row keys")
    from ..ifc import intent as _I                       # check-only import: the schema's kinds
    vocabulary = set(_I.GENERATED_KINDS) | set(_I.KIND_BY_CLASS.values())
    problems.extend(f"taxonomy[{r.key}]: intent kind {ik!r} is not one rvt.ifc.intent emits "
                    f"({sorted(vocabulary)})"
                    for r in _ROWS for ik in r.intent if ik not in vocabulary)
    for row in _ROWS:                                     # a generic word names EVERY type of it
        if not row.refine:
            continue
        named = {k for g in _ROWS if g.refine and g.category == row.category for k in g.refine}
        missing = [r.key for r in _ROWS if r.category == row.category and not r.refine
                   and not r.pending and r.key not in named]
        if missing:
            problems.append(f"taxonomy[{row.key}]: generic for {row.category!r} but these rows "
                            f"of that category are in no refine list: {missing}")
    problems.extend(f"taxonomy: AMBIGUOUS_ALONE word {w!r} is not a name any row carries"
                    for w in sorted(AMBIGUOUS_ALONE) if w not in _ALIAS)
    for row in _ROWS:
        problems.extend(check_row(row))
    return problems

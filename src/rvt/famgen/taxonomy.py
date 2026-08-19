"""MEP TAXONOMY -- every equipment kind the product speaks about, as ONE TABLE (#692).

Each row (a :class:`Kind`) says, for one kind of MEP equipment:

* which **Revit category** it belongs to -- a key ``rvt.famgen.skeleton._resolve_category``
  resolves (never a guessed numeric id; a kind whose category the engine cannot resolve yet
  is simply not a row until it can be, see ``NOT_YET`` at the bottom);
* which **standard-parameter table** (:mod:`rvt.famgen.standards`, #601) a family of that
  kind carries;
* which **lane** can build it today:

  ``catalog``    sourced manufacturer/standards FACTS are held (``famgen/facts/**``) and a
                 constructor exists -> the family is built at true member dimensions (``fact``);
  ``archetype``  a constructor generates it at standard NOMINAL dimensions with no facts
                 (``nominal``) -- today the honest house switchboard; rows keyed to the
                 archetype registry (``rvt.famgen.archetypes``: cable_tray, conduit, wireway,
                 strut_channel, junction_box -- #674) become available the day that module is
                 on the build: it is *probed*, never imported blindly;
  ``none``       the kind is known and placed under the right category, but nothing builds
                 it yet -- :func:`describe` says so in one line naming the missing lane.

This module is TAXONOMY, not data about any member: **no dimensions, ratings or part
numbers live here** (steers #685/#591: model knowledge may supply the taxonomy and standard
practice, never a manufacturer's dimensions).  Manufacturers and product lines are the
sibling table :mod:`rvt.famgen.vendors`; the two are cross-checked by :func:`check` there.

Adding a kind is adding a row to ``_ROWS`` -- no dispatch code changes.  ``python
tools/make_family.py taxonomy [KIND] [--discipline D] [--check] [--json]`` prints it.
"""
from __future__ import annotations

import importlib
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, Iterable, List, Optional, Tuple

__all__ = ["Kind", "LANES", "DISCIPLINES", "kinds", "keys", "get", "resolve", "by_discipline",
           "builder_available", "describe", "table", "check", "NOT_YET"]

LANES = ("catalog", "archetype", "none")
DISCIPLINES = ("electrical", "lighting", "fire_alarm", "technology", "mechanical", "plumbing",
               "fire_protection")

#: resolver key -> the label Revit shows (only the categories this table uses)
CATEGORY_LABEL = {
    "panelboard": "Electrical Equipment", "switchboard": "Electrical Equipment",
    "transformer": "Electrical Equipment", "electrical_equipment": "Electrical Equipment",
    "electrical_fixture": "Electrical Fixtures", "lighting_fixture": "Lighting Fixtures",
    "lighting_device": "Lighting Devices", "fire_alarm_device": "Fire Alarm Devices",
    "data_device": "Data Devices", "telephone_device": "Telephone Devices",
    "communication_device": "Communication Devices", "security_device": "Security Devices",
    "nurse_call_device": "Nurse Call Devices", "mechanical_equipment": "Mechanical Equipment",
    "duct_accessory": "Duct Accessories", "pipe_accessory": "Pipe Accessories",
    "plumbing_fixture": "Plumbing Fixtures",
    "cable_tray_fitting": "Cable Tray Fittings", "conduit_fitting": "Conduit Fittings",
    "generic_model": "Generic Models",
}


@dataclass(frozen=True)
class Kind:
    key: str                     # stable snake_case id: "transformer_dry"
    label: str                   # what an engineer calls it
    discipline: str              # one of DISCIPLINES
    category: str                # rvt.famgen.skeleton._resolve_category key
    standards: str               # rvt.famgen.standards category key (its parameter table)
    lane: str                    # one of LANES -- the lane DECLARED for this kind
    aliases: Tuple[str, ...] = ()
    #: dotted "module:function" of the constructor for catalog/archetype rows
    builder: Optional[str] = None
    #: (famspec kind, that constructor's own sub-kind) for rows the famspec lane builds
    famspec: Optional[Tuple[str, Optional[str]]] = None
    #: key in the #674 archetype registry, for archetype rows that depend on it
    archetype: Optional[str] = None
    note: str = ""

    @property
    def revit_category(self) -> str:
        return CATEGORY_LABEL.get(self.category, self.category.replace("_", " ").title())


def _k(key, label, discipline, category, lane="none", *, standards=None, aliases=(),
       builder=None, famspec=None, archetype=None, note="") -> Kind:
    return Kind(key=key, label=label, discipline=discipline, category=category,
                standards=standards or category, lane=lane, aliases=tuple(aliases),
                builder=builder, famspec=famspec, archetype=archetype, note=note)


_FACTORY = "rvt.famgen.factory"

_ROWS: Tuple[Kind, ...] = (
    # ---------------------------------------------------------------- electrical distribution
    _k("panelboard", "Panelboard", "electrical", "panelboard", "catalog",
       aliases=("panel", "branch panel", "lighting panel", "power panel", "distribution panel",
                "load center", "panel board"),
       builder=f"{_FACTORY}:make_panelboard", famspec=("panelboard", None)),
    _k("switchboard", "Switchboard", "electrical", "switchboard", "archetype",
       aliases=("main switchboard", "msb", "service switchboard", "distribution switchboard"),
       builder="rvt.ifc.intent:make_house_switchboard",
       note="built as the honest HOUSE switchboard at nominal dimensions -- no manufacturer "
            "member is held for switchboards"),
    _k("switchgear", "Low-voltage switchgear", "electrical", "electrical_equipment",
       aliases=("lv switchgear", "metal-enclosed switchgear", "metal-clad switchgear")),
    _k("transformer_dry", "Dry-type distribution transformer", "electrical", "transformer",
       "catalog",
       aliases=("transformer", "dry type transformer", "dry-type transformer",
                "step-down transformer", "xfmr", "distribution transformer"),
       builder=f"{_FACTORY}:make_transformer", famspec=("transformer", None)),
    _k("motor_control_center", "Motor control center", "electrical", "electrical_equipment",
       aliases=("mcc",)),
    _k("disconnect_switch", "Safety / disconnect switch", "electrical", "electrical_equipment",
       aliases=("safety switch", "disconnect", "fused disconnect", "non-fused disconnect")),
    _k("variable_frequency_drive", "Variable frequency drive", "electrical",
       "electrical_equipment", aliases=("vfd", "variable speed drive", "asd", "drive")),
    _k("automatic_transfer_switch", "Automatic transfer switch", "electrical",
       "electrical_equipment", aliases=("ats", "transfer switch")),
    _k("ups", "Uninterruptible power supply", "electrical", "electrical_equipment",
       aliases=("uninterruptible power supply", "ups system")),
    _k("generator", "Engine generator set", "electrical", "electrical_equipment",
       aliases=("genset", "standby generator", "emergency generator", "diesel generator")),
    _k("meter_center", "Meter center / metering cabinet", "electrical", "electrical_equipment",
       aliases=("meter stack", "metering", "ct cabinet", "meter socket")),
    _k("enclosed_circuit_breaker", "Enclosed circuit breaker", "electrical",
       "electrical_equipment", aliases=("ecb", "enclosed breaker")),
    _k("lighting_control_panel", "Lighting control / relay panel", "electrical",
       "electrical_equipment", aliases=("relay panel", "lighting relay panel", "lcp")),
    _k("busway", "Busway / bus duct", "electrical", "electrical_equipment",
       aliases=("bus duct", "busduct"),
       note="a busway RUN is drawn, not loaded; plug-in units and end fittings are the "
            "loadable parts and are not built yet"),
    _k("cable_tray", "Cable tray (ladder) section", "electrical", "cable_tray_fitting",
       "archetype", archetype="cable_tray",
       aliases=("ladder tray", "cable ladder", "ladder cable tray", "tray section", "cable tray"),
       note="a loadable ladder-tray SECTION at NEMA VE 1 nominal sizes from the archetype "
            "registry (#591/#674); a routed tray RUN in a project is Revit's system family"),
    _k("cable_tray_fitting", "Cable tray fitting", "electrical", "cable_tray_fitting",
       aliases=("tray elbow", "tray tee", "tray fitting", "tray cross")),
    _k("conduit", "Conduit straight section", "electrical", "conduit_fitting", "archetype",
       archetype="conduit", aliases=("emt", "rigid conduit", "imc", "conduit run", "raceway"),
       note="a loadable straight SECTION at trade sizes from the archetype registry (#674); a "
            "routed conduit RUN in a project is Revit's system family"),
    _k("conduit_fitting", "Conduit fitting", "electrical", "conduit_fitting",
       aliases=("conduit elbow", "conduit body", "condulet")),
    _k("wireway", "Wireway (lay-in)", "electrical", "electrical_equipment", "archetype",
       archetype="wireway", aliases=("lay-in wireway", "wire trough", "gutter", "auxiliary gutter")),
    _k("strut_channel", "Strut channel", "electrical", "generic_model", "archetype",
       archetype="strut_channel", aliases=("strut", "unistrut", "channel strut", "trapeze strut")),
    # ---------------------------------------------------------------- wiring devices
    _k("receptacle", "Duplex receptacle", "electrical", "electrical_fixture", "catalog",
       aliases=("outlet", "duplex", "duplex receptacle", "convenience receptacle", "5-15r",
                "5-20r", "wall outlet", "power outlet"),
       builder=f"{_FACTORY}:make_device", famspec=("device", "duplex-receptacle")),
    _k("light_switch", "Wall switch", "electrical", "electrical_fixture", "catalog",
       aliases=("switch", "toggle switch", "single pole switch", "light switch", "wall switch"),
       builder=f"{_FACTORY}:make_device", famspec=("device", "switch")),
    _k("junction_box", "Junction box", "electrical", "electrical_fixture", "catalog",
       aliases=("j-box", "jbox", "pull box", "4in square box"),
       builder=f"{_FACTORY}:make_device", famspec=("device", "junction-box"),
       archetype="junction_box",
       note="the 4-in device box is catalog-backed (standards facts); larger screw-cover "
            "boxes come from the archetype registry when it is on the build (#674)"),
    _k("floor_box", "Floor box", "electrical", "electrical_fixture",
       aliases=("poke-through", "poke through", "floor outlet")),
    # ---------------------------------------------------------------- lighting
    _k("troffer", "Recessed LED troffer", "lighting", "lighting_fixture", "catalog",
       aliases=("2x4 troffer", "2x2 troffer", "recessed troffer", "lay-in fixture", "lay-in",
                "recessed fixture"),
       builder=f"{_FACTORY}:make_luminaire", famspec=("luminaire", "recessed-troffer")),
    _k("downlight", "Recessed LED downlight", "lighting", "lighting_fixture", "catalog",
       aliases=("can light", "recessed downlight", "recessed can", "pot light"),
       builder=f"{_FACTORY}:make_luminaire", famspec=("luminaire", "downlight")),
    _k("high_bay", "High-bay luminaire", "lighting", "lighting_fixture",
       aliases=("highbay", "high bay", "low bay", "bay light")),
    _k("linear_luminaire", "Linear / strip luminaire", "lighting", "lighting_fixture",
       aliases=("strip light", "linear pendant", "linear fixture", "wraparound", "wrap")),
    _k("wall_pack", "Exterior wall pack", "lighting", "lighting_fixture",
       aliases=("wallpack", "wall mount area light")),
    _k("wall_sconce", "Wall sconce", "lighting", "lighting_fixture", aliases=("sconce",)),
    _k("exit_sign", "Exit sign", "lighting", "lighting_fixture",
       aliases=("exit light", "egress sign")),
    _k("emergency_light", "Emergency lighting unit", "lighting", "lighting_fixture",
       aliases=("bug eye", "bug-eye", "emergency light", "egress light", "frog eyes")),
    _k("pole_light", "Site / area pole luminaire", "lighting", "lighting_fixture",
       aliases=("area light", "parking lot light", "site light", "pole fixture")),
    _k("occupancy_sensor", "Occupancy / vacancy sensor", "lighting", "lighting_device",
       aliases=("motion sensor", "vacancy sensor", "occ sensor", "ceiling sensor")),
    _k("dimmer_switch", "Dimmer", "lighting", "lighting_device",
       aliases=("dimmer", "wall dimmer", "dimming switch")),
    _k("daylight_sensor", "Daylight / photo sensor", "lighting", "lighting_device",
       aliases=("photocell", "photosensor", "daylight harvesting sensor")),
    # ---------------------------------------------------------------- fire alarm
    _k("smoke_detector", "Smoke detector", "fire_alarm", "fire_alarm_device",
       aliases=("smoke", "photoelectric detector", "smoke alarm")),
    _k("heat_detector", "Heat detector", "fire_alarm", "fire_alarm_device",
       aliases=("rate of rise detector", "thermal detector")),
    _k("pull_station", "Manual pull station", "fire_alarm", "fire_alarm_device",
       aliases=("manual station", "pull", "fire alarm pull")),
    _k("horn_strobe", "Notification appliance (horn / strobe)", "fire_alarm",
       "fire_alarm_device",
       aliases=("horn strobe", "strobe", "horn", "speaker strobe", "notification appliance")),
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
    _k("water_heater", "Water heater", "plumbing", "mechanical_equipment",
       aliases=("domestic water heater", "dwh", "tank water heater", "tankless water heater"),
       note="placed under Mechanical Equipment (long-standing practice); Revit 2022+ also "
            "offers Plumbing Equipment, which the engine's category resolver does not carry yet"),
    _k("fire_damper", "Fire / smoke damper", "mechanical", "duct_accessory",
       aliases=("smoke damper", "fire smoke damper", "fsd")),
    _k("volume_damper", "Balancing / volume damper", "mechanical", "duct_accessory",
       aliases=("balancing damper", "manual damper", "mvd")),
    # ---------------------------------------------------------------- plumbing
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
    # ---------------------------------------------------------------- fire protection
    _k("fire_pump", "Fire pump", "fire_protection", "mechanical_equipment",
       aliases=("jockey pump", "fire pump skid")),
)

#: kinds engineers ask for whose Revit category the engine's resolver does not carry yet --
#: kept OUT of the table on purpose (a wrong category is worse than an absent row, #692);
#: each becomes a row the day ``skeleton._resolve_category`` learns the category.
#: (label, Revit category, phrases an engineer uses)
NOT_YET: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("Diffuser / grille / register", "Air Terminals",
     ("diffuser", "grille", "register", "air terminal", "supply diffuser", "return grille")),
    ("Sprinkler head", "Sprinklers", ("sprinkler", "sprinkler head", "fire sprinkler")),
    ("Duct run", "Ducts (system family, drawn in the project)", ("duct", "ductwork")),
    ("Pipe run", "Pipes (system family, drawn in the project)", ("pipe", "piping")),
    ("Grease interceptor", "Plumbing Equipment (Revit 2022+)",
     ("grease interceptor", "grease trap")),
)

_BY_KEY: Dict[str, Kind] = {k.key: k for k in _ROWS}


def _norm(text: Any) -> str:
    return " ".join(str(text).lower().replace("_", " ").replace("-", " ").split())


_ALIAS: Dict[str, str] = {}
for _row in _ROWS:
    for _a in (_row.key, _row.label) + _row.aliases:
        _ALIAS.setdefault(_norm(_a), _row.key)
_NOT_YET_ALIAS: Dict[str, Tuple[str, str]] = {
    _norm(p): (label, cat) for label, cat, phrases in NOT_YET for p in phrases + (label,)}


def kinds() -> Tuple[Kind, ...]:
    """Every row, in table order."""
    return _ROWS


def keys() -> Tuple[str, ...]:
    return tuple(_BY_KEY)


def get(key: str) -> Kind:
    """The row for an exact key (KeyError otherwise) -- see :func:`resolve` for free text."""
    return _BY_KEY[key]


def resolve(text: Any) -> Optional[Kind]:
    """Free text -> row, by key, label or alias (case/space/hyphen-insensitive); None if the
    taxonomy does not know the words.  Deliberately exact-phrase: the prompt grammar decides
    what a phrase is, this table decides what a KIND is."""
    return _BY_KEY.get(_ALIAS.get(_norm(text), ""))


def by_discipline(discipline: Optional[str] = None) -> Dict[str, Tuple[Kind, ...]]:
    out: Dict[str, List[Kind]] = {}
    for row in _ROWS:
        if discipline and row.discipline != discipline:
            continue
        out.setdefault(row.discipline, []).append(row)
    return {d: tuple(v) for d, v in out.items()}


# --------------------------------------------------------------------------- availability

def _import_attr(dotted: str) -> Optional[Any]:
    mod, _, attr = dotted.partition(":")
    try:
        return getattr(importlib.import_module(mod), attr, None)
    except Exception:            # noqa: BLE001 -- an optional builder that is not importable
        return None              # on this build is "unavailable", never a crash of the table


def archetype_registry() -> Optional[Iterable[str]]:
    """The #674 archetype registry's keys if that module is on this build, else None.  Probed,
    never imported unconditionally (the registry is not merged at the time of writing)."""
    try:
        mod = importlib.import_module("rvt.famgen.archetypes")
    except Exception:            # noqa: BLE001
        return None
    reg = getattr(mod, "ARCHETYPES", None)
    if isinstance(reg, dict):
        return tuple(reg)
    fn = getattr(mod, "kinds", None) or getattr(mod, "keys", None)
    try:
        return tuple(fn()) if callable(fn) else None
    except Exception:            # noqa: BLE001
        return None


def builder_available(row: Kind) -> Tuple[bool, str]:
    """(available, why) for the row's declared lane on THIS build."""
    if row.lane == "none":
        return False, (f"{row.label} is placed under {row.revit_category}, but no lane builds "
                       f"it yet: no sourced facts are held and no archetype generates it")
    if row.builder:
        if _import_attr(row.builder) is None:
            return False, f"builder {row.builder} is not importable on this build"
        if row.lane == "catalog":
            from . import vendors as _V          # the directory owns kind <-> facts lines
            if not _V.facts_lines(row.key):
                return False, (f"lane is catalog but no held facts line lists {row.key!r} "
                               f"(rvt.famgen.vendors)")
        return True, f"{row.lane}: {row.builder}"
    if row.archetype:
        reg = archetype_registry()
        if reg is None:
            return False, ("archetype registry (rvt.famgen.archetypes, #674) is not on this "
                           "build -- the kind is known but cannot be generated here yet")
        if row.archetype not in reg:
            return False, f"archetype {row.archetype!r} is not in the registry on this build"
        return True, f"archetype: {row.archetype}"
    return False, f"lane {row.lane!r} declared without a builder or archetype key"


def describe(key_or_text: Any) -> Dict[str, Any]:
    """One kind as a JSON-able dict, availability computed live, plus the ONE honest line a
    surface relays (``line``).  Unknown text -> ``{"known": False, "line": ...}``."""
    row = _BY_KEY.get(str(key_or_text)) or resolve(key_or_text)
    if row is None:
        pending = _NOT_YET_ALIAS.get(_norm(key_or_text))
        if pending:
            label, cat = pending
            return {"known": False, "not_yet": True, "query": str(key_or_text), "label": label,
                    "revit_category": cat,
                    "line": (f"{label}: belongs under {cat}, a category the engine's resolver "
                             f"does not carry yet -- known to the taxonomy as pending, not "
                             f"buildable or placeable here")}
        return {"known": False, "query": str(key_or_text),
                "line": (f"'{key_or_text}' is not a kind the MEP taxonomy knows "
                         f"({len(_ROWS)} kinds across {', '.join(DISCIPLINES)})")}
    ok, why = builder_available(row)
    from . import standards as _S
    std = _S.describe(row.standards)
    d = asdict(row)
    d.update({"known": True, "revit_category": row.revit_category, "available": ok,
              "availability": why, "standards_covered": bool(std.get("covered")),
              "standards_count": len(std.get("authored") or []) + len(std.get("builtin") or [])})
    if ok:
        tier = "fact" if row.lane == "catalog" else "nominal"
        d["line"] = (f"{row.label}: {row.revit_category}; built by the {row.lane} lane "
                     f"({tier}-tier dimensions); {d['standards_count']} standard parameters")
    else:
        d["line"] = f"{row.label}: {row.revit_category}; NOT buildable here -- {why}"
    return d


def table() -> Dict[str, Any]:
    """The whole taxonomy, JSON-able (what ``make_family.py taxonomy --json`` prints)."""
    rows = [describe(r.key) for r in _ROWS]
    lanes = {ln: [r["key"] for r in rows if r["lane"] == ln] for ln in LANES}
    return {"kinds": rows, "count": len(rows),
            "by_discipline": {d: [r.key for r in rs] for d, rs in by_discipline().items()},
            "by_lane": lanes,
            "available": [r["key"] for r in rows if r["available"]],
            "archetype_registry": (None if archetype_registry() is None
                                   else sorted(archetype_registry())),
            "not_yet": [{"label": l, "revit_category": c, "phrases": list(p)}
                        for l, c, p in NOT_YET]}


# --------------------------------------------------------------------------- the gate

def check() -> List[str]:
    """Problems that make the table dishonest (empty list = clean).  Gates, per #692:
    every row's category resolves through ``skeleton._resolve_category``; every
    row's standard-parameter set exists in ``standards.py``; every catalog row has an
    importable builder AND a held facts line; keys/aliases are unambiguous; the enums hold."""
    from . import skeleton as _SK, standards as _S
    problems: List[str] = []
    std_cats = set(_S.table()["categories"])
    seen_alias: Dict[str, str] = {}
    for row in _ROWS:
        tag = f"taxonomy[{row.key}]"
        if row.lane not in LANES:
            problems.append(f"{tag}: lane {row.lane!r} not in {LANES}")
        if row.discipline not in DISCIPLINES:
            problems.append(f"{tag}: discipline {row.discipline!r} not in {DISCIPLINES}")
        try:
            cid = _SK._resolve_category(row.category)
            if not isinstance(cid, int) or cid >= 0:
                problems.append(f"{tag}: category {row.category!r} resolved to {cid!r}")
        except Exception as e:                           # noqa: BLE001
            problems.append(f"{tag}: category {row.category!r} does not resolve ({e})")
        if row.category not in CATEGORY_LABEL:
            problems.append(f"{tag}: category {row.category!r} has no CATEGORY_LABEL entry")
        if _S.canonical_category(row.standards) not in std_cats:
            problems.append(f"{tag}: standards table {row.standards!r} does not exist")
        if row.lane != "none" and not (row.builder or row.archetype):
            problems.append(f"{tag}: lane {row.lane} needs a builder or an archetype key")
        if row.lane == "none" and row.builder:
            problems.append(f"{tag}: lane none but a builder is declared")
        if row.lane == "catalog":
            ok, why = builder_available(row)
            if not ok:
                problems.append(f"{tag}: {why}")
        if row.famspec and not row.builder:
            problems.append(f"{tag}: famspec declared without a builder")
        for a in (row.key, row.label) + row.aliases:
            n = _norm(a)
            if n in seen_alias and seen_alias[n] != row.key:
                problems.append(f"{tag}: alias {a!r} also claimed by {seen_alias[n]!r}")
            seen_alias.setdefault(n, row.key)
    return problems

"""VENDOR DIRECTORY -- who makes which MEP product lines, and which of them we hold sourced
FACTS for (#692).  The sibling of :mod:`rvt.famgen.taxonomy`.

The line this table walks (steer #685, restated on #692 because this is where it is tested):
**a manufacturer's name and a product line's name are things the engine may know; a
member's dimensions are not.**  So a :class:`Line` carries a label, the taxonomy kinds it
covers, and -- only when ``rvt.famgen.catalog`` really holds a facts file for it -- the key
of that file (``facts``).  ``facts_held`` is therefore never an opinion: :func:`check`
loads every claimed file, confirms it is the vendor's and that its ``category`` is the
famspec kind the taxonomy row builds through, and confirms that EVERY line the catalog
holds appears here exactly once.  A vendor we can name but hold nothing for says exactly
that (:func:`describe`), which is the honest answer #685 asks for -- never a silent
substitution, never a recalled number.

No dimensions, ratings, prices or part numbers live here.  Adding a manufacturer or a line
is adding a row.  ``python tools/make_family.py vendors [VENDOR] [--kind K] [--check]
[--json]`` prints it.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from . import taxonomy as TX

__all__ = ["Vendor", "Line", "vendors", "get", "resolve", "lines_for_kind", "facts_lines",
           "describe", "table", "check"]


@dataclass(frozen=True)
class Line:
    key: str                       # slug, unique within the vendor
    label: str                     # the product line as the maker names it (or a plain
                                   # description where no single trade name applies)
    kinds: Tuple[str, ...]         # taxonomy keys this line covers
    facts: Optional[str] = None    # rvt.famgen.catalog line key when facts ARE held

    @property
    def facts_held(self) -> bool:
        return self.facts is not None


@dataclass(frozen=True)
class Vendor:
    key: str                       # slug == the catalog's vendor directory name when held
    name: str
    lines: Tuple[Line, ...]
    aliases: Tuple[str, ...] = ()
    parent: str = ""               # owning group, informational ("Schneider Electric")


def _L(key, label, kinds, facts=None) -> Line:
    return Line(key, label, tuple(kinds), facts)


def _V(key, name, lines, aliases=(), parent="") -> Vendor:
    return Vendor(key, name, tuple(lines), tuple(aliases), parent)


_ROWS: Tuple[Vendor, ...] = (
    # ------------------------------------------------------------ electrical distribution
    _V("eaton", "Eaton", [
        _L("pow-r-line-panelboards", "Pow-R-Line panelboards (PRL1a/1X/2X/3X/4X)",
           ["panelboard"], facts="pow-r-line-panelboards"),
        _L("dry-type-transformers", "Dry-type distribution transformers (ventilated, 480-208Y)",
           ["transformer_dry"], facts="dry-type-transformers"),
        _L("pow-r-line-switchboards", "Pow-R-Line switchboards", ["switchboard"]),
        _L("magnum-switchgear", "Magnum low-voltage switchgear", ["switchgear"]),
        _L("freedom-mcc", "Freedom motor control centers", ["motor_control_center"]),
        _L("safety-switches", "Heavy-duty / general-duty safety switches",
           ["disconnect_switch"]),
        _L("powerxl-drives", "PowerXL variable frequency drives", ["variable_frequency_drive"]),
        _L("ats", "Automatic transfer switches", ["automatic_transfer_switch"]),
        _L("ups", "Three-phase UPS (93PM / 9395 families)", ["ups"]),
    ], aliases=("cutler-hammer", "cutler hammer", "westinghouse")),
    _V("square-d", "Square D", [
        _L("nq-nf-iline-panelboards", "NQ / NF / I-Line panelboards", ["panelboard"],
           facts="nq-nf-iline-panelboards"),
        _L("qed-switchboards", "QED-2 switchboards", ["switchboard"]),
        _L("model-6-mcc", "Model 6 motor control centers", ["motor_control_center"]),
        _L("safety-switches", "General-duty / heavy-duty safety switches",
           ["disconnect_switch"]),
        _L("dry-type-transformers", "Low-voltage dry-type transformers", ["transformer_dry"]),
        _L("altivar-drives", "Altivar variable frequency drives", ["variable_frequency_drive"]),
    ], aliases=("schneider", "schneider electric", "sqd", "square d"), parent="Schneider Electric"),
    _V("siemens", "Siemens", [
        _L("p-series-panelboards", "P1 - P5 panelboards", ["panelboard"]),
        _L("sb-switchboards", "SB1 / SB2 / SB3 switchboards", ["switchboard"]),
        _L("tiastar-mcc", "tiastar motor control centers", ["motor_control_center"]),
        _L("sinamics-drives", "SINAMICS variable frequency drives",
           ["variable_frequency_drive"]),
        _L("safety-switches", "General-duty / heavy-duty safety switches",
           ["disconnect_switch"]),
    ]),
    _V("abb", "ABB (incl. former GE Industrial Solutions)", [
        _L("reliagear-panelboards", "ReliaGear lighting / power panelboards", ["panelboard"]),
        _L("reliagear-switchboards", "ReliaGear switchboards", ["switchboard"]),
        _L("acs-drives", "ACS-family variable frequency drives", ["variable_frequency_drive"]),
    ], aliases=("ge", "general electric", "ge industrial")),
    _V("hps", "Hammond Power Solutions", [
        _L("sentinel-g-transformers", "Sentinel G energy-efficient dry-type transformers",
           ["transformer_dry"], facts="sentinel-g-transformers"),
    ], aliases=("hammond", "hammond power")),
    _V("generac", "Generac Industrial Power", [
        _L("gensets", "Diesel / gaseous standby generator sets", ["generator"]),
        _L("transfer-switches", "Automatic transfer switches", ["automatic_transfer_switch"]),
    ]),
    _V("cummins", "Cummins Power Generation", [
        _L("gensets", "Standby / prime generator sets", ["generator"]),
        _L("transfer-switches", "OTEC / OTPC transfer switches", ["automatic_transfer_switch"]),
    ], aliases=("onan",)),
    _V("kohler-power", "Kohler Power Systems", [
        _L("gensets", "Standby generator sets", ["generator"]),
        _L("transfer-switches", "Automatic transfer switches", ["automatic_transfer_switch"]),
    ], aliases=("kohler generators", "rehlko")),
    # ------------------------------------------------------------ wiring devices
    _V("generic", "Generic (standards-derived, no manufacturer)", [
        _L("devices-and-mounting", "NEMA wiring devices and code mounting heights",
           ["receptacle", "light_switch", "junction_box"], facts="devices-and-mounting"),
    ], aliases=("standards", "nema")),
    _V("hubbell", "Hubbell Wiring Device-Kellems", [
        _L("spec-grade-devices", "Commercial / spec-grade receptacles and switches",
           ["receptacle", "light_switch"]),
        _L("floor-boxes", "Floor boxes and poke-throughs", ["floor_box"]),
    ]),
    _V("leviton", "Leviton", [
        _L("decora-commercial", "Decora and commercial spec-grade devices",
           ["receptacle", "light_switch", "dimmer_switch"]),
        _L("occupancy-sensors", "Occupancy / vacancy sensors", ["occupancy_sensor"]),
    ]),
    _V("legrand", "Legrand (Pass & Seymour / Wattstopper / Wiremold)", [
        _L("pass-seymour-devices", "Pass & Seymour spec-grade devices",
           ["receptacle", "light_switch"]),
        _L("wattstopper-controls", "Wattstopper occupancy sensors and lighting controls",
           ["occupancy_sensor", "daylight_sensor", "lighting_control_panel"]),
        _L("wiremold-floor-boxes", "Wiremold floor boxes and poke-throughs", ["floor_box"]),
    ], aliases=("pass & seymour", "pass and seymour", "wattstopper", "wiremold")),
    # ------------------------------------------------------------ lighting
    _V("lithonia", "Lithonia Lighting", [
        _L("blt-led-troffer", "BLT LED troffer", ["troffer"], facts="blt-led-troffer"),
        _L("ldn6-led-downlight", "LDN6 LED downlight", ["downlight"],
           facts="ldn6-led-downlight"),
        _L("ibg-high-bay", "IBG LED high bay", ["high_bay"]),
        _L("wall-packs", "LED wall packs", ["wall_pack"]),
        _L("exit-emergency", "Exit signs and emergency units (LQM / ELM families)",
           ["exit_sign", "emergency_light"]),
        _L("area-luminaires", "LED area / site luminaires", ["pole_light"]),
    ], aliases=("acuity", "acuity brands", "lithonia lighting"), parent="Acuity Brands"),
    _V("cooper-lighting", "Cooper Lighting Solutions", [
        _L("metalux-troffers", "Metalux LED troffers and panels", ["troffer"]),
        _L("halo-downlights", "Halo commercial LED downlights", ["downlight"]),
        _L("sure-lites", "Sure-Lites exit and emergency lighting",
           ["exit_sign", "emergency_light"]),
        _L("lumark-mcgraw", "Lumark / McGraw-Edison exterior luminaires",
           ["wall_pack", "pole_light"]),
    ], aliases=("cooper", "metalux", "halo", "sure-lites"), parent="Signify"),
    _V("cree-lighting", "Cree Lighting", [
        _L("troffers", "LED troffers", ["troffer"]),
        _L("high-bay", "LED high-bay luminaires", ["high_bay"]),
    ], aliases=("cree",)),
    # ------------------------------------------------------------ fire alarm / technology
    _V("notifier", "NOTIFIER", [
        _L("panels", "Addressable fire alarm control panels", ["fire_alarm_control_panel"]),
        _L("detectors", "Addressable smoke / heat / duct detectors",
           ["smoke_detector", "heat_detector", "duct_smoke_detector"]),
        _L("notification", "Notification appliances and pull stations",
           ["horn_strobe", "pull_station"]),
    ], parent="Honeywell"),
    _V("simplex", "Simplex", [
        _L("panels", "4100ES / 4010ES fire alarm control panels", ["fire_alarm_control_panel"]),
        _L("truealarm", "TrueAlarm detectors", ["smoke_detector", "heat_detector"]),
        _L("truealert", "TrueAlert notification appliances", ["horn_strobe", "pull_station"]),
    ], aliases=("simplexgrinnell", "jci fire"), parent="Johnson Controls"),
    _V("edwards", "Edwards (EST)", [
        _L("panels", "EST addressable fire alarm control panels", ["fire_alarm_control_panel"]),
        _L("signature-detectors", "Signature Series detectors",
           ["smoke_detector", "heat_detector"]),
        _L("genesis-notification", "Genesis notification appliances", ["horn_strobe"]),
    ], aliases=("est",), parent="Carrier"),
    _V("panduit", "Panduit", [
        _L("workstation-outlets", "Mini-Com workstation outlets and faceplates", ["data_outlet"]),
    ]),
    _V("commscope", "CommScope", [
        _L("workstation-outlets", "SYSTIMAX / Uniprise workstation outlets", ["data_outlet"]),
    ], aliases=("systimax",)),
    # ------------------------------------------------------------ mechanical
    _V("trane", "Trane", [
        _L("air-handlers", "Performance Climate Changer air handlers", ["air_handling_unit"]),
        _L("rooftops", "Precedent / Voyager / IntelliPak rooftop units", ["rooftop_unit"]),
        _L("chillers", "Air- and water-cooled chillers (incl. CenTraVac)", ["chiller"]),
        _L("terminal-units", "VariTrane VAV terminal units", ["vav_box"]),
        _L("fan-coils", "Fan coil units", ["fan_coil_unit"]),
        _L("unit-heaters", "Unit heaters", ["unit_heater"]),
    ], parent="Trane Technologies"),
    _V("carrier", "Carrier", [
        _L("air-handlers", "39-series air handlers", ["air_handling_unit"]),
        _L("rooftops", "WeatherMaker / WeatherExpert rooftop units", ["rooftop_unit"]),
        _L("chillers", "AquaEdge / AquaSnap chillers", ["chiller"]),
        _L("fan-coils", "Fan coil units", ["fan_coil_unit"]),
        _L("splits", "Ductless and ducted split systems", ["split_system"]),
    ]),
    _V("daikin", "Daikin Applied", [
        _L("rooftops", "Rebel / Maverick rooftop units", ["rooftop_unit"]),
        _L("air-handlers", "Vision / Skyline air handlers", ["air_handling_unit"]),
        _L("chillers", "Magnitude / Pathfinder / Trailblazer chillers", ["chiller"]),
        _L("vrv", "VRV variable refrigerant systems", ["split_system"]),
        _L("fan-coils", "Fan coil units", ["fan_coil_unit"]),
    ], aliases=("daikin applied", "mcquay")),
    _V("york", "YORK", [
        _L("chillers", "YK / YZ centrifugal and air-cooled chillers", ["chiller"]),
        _L("air-handlers", "Solution air handlers", ["air_handling_unit"]),
        _L("rooftops", "Packaged rooftop units", ["rooftop_unit"]),
    ], aliases=("jci", "johnson controls"), parent="Johnson Controls"),
    _V("greenheck", "Greenheck", [
        _L("fans", "Centrifugal, inline and roof-mounted fans", ["exhaust_fan"]),
        _L("dampers", "Fire / smoke and control dampers", ["fire_damper", "volume_damper"]),
        _L("energy-recovery", "Energy recovery ventilators", ["energy_recovery_unit"]),
        _L("doas", "Dedicated outdoor air units", ["air_handling_unit"]),
    ]),
    _V("loren-cook", "Loren Cook", [
        _L("fans", "Exhaust and supply fans", ["exhaust_fan"]),
    ], aliases=("cook",)),
    _V("ruskin", "Ruskin", [
        _L("dampers", "Fire / smoke and control dampers", ["fire_damper", "volume_damper"]),
    ]),
    _V("bell-gossett", "Bell & Gossett", [
        _L("pumps", "e-1510 end-suction and e-90 inline pumps", ["pump"]),
        _L("hydronic-specialties", "Expansion tanks and hydronic specialties",
           ["expansion_tank"]),
    ], aliases=("b&g", "bell and gossett"), parent="Xylem"),
    _V("grundfos", "Grundfos", [
        _L("pumps", "Circulators, inline and end-suction pumps, booster sets", ["pump"]),
    ]),
    _V("taco", "Taco Comfort Solutions", [
        _L("pumps", "Circulators and base-mounted pumps", ["pump"]),
        _L("tanks", "Expansion tanks", ["expansion_tank"]),
    ], aliases=("taco",)),
    _V("armstrong", "Armstrong Fluid Technology", [
        _L("pumps", "Design Envelope pumps", ["pump"]),
        _L("fire-pumps", "Fire pump packages", ["fire_pump"]),
    ]),
    _V("lochinvar", "Lochinvar", [
        _L("boilers", "CREST / KNIGHT condensing boilers", ["boiler"]),
        _L("water-heaters", "Commercial water heaters (ARMOR / SHIELD)", ["water_heater"]),
    ]),
    _V("cleaver-brooks", "Cleaver-Brooks", [
        _L("boilers", "Firetube and condensing boilers", ["boiler"]),
    ]),
    _V("bac", "Baltimore Aircoil Company", [
        _L("cooling-towers", "Cooling towers and closed-circuit fluid coolers", ["cooling_tower"]),
    ], aliases=("baltimore aircoil",)),
    _V("evapco", "EVAPCO", [
        _L("cooling-towers", "Cooling towers and fluid coolers", ["cooling_tower"]),
    ]),
    _V("mitsubishi-electric", "Mitsubishi Electric Trane HVAC", [
        _L("city-multi", "CITY MULTI VRF and M/P-series splits", ["split_system"]),
    ], aliases=("mitsubishi", "metus")),
    _V("modine", "Modine", [
        _L("unit-heaters", "Gas-fired and hydronic unit heaters", ["unit_heater"]),
    ]),
    _V("price", "Price Industries", [
        _L("terminal-units", "Single-duct and fan-powered VAV terminal units", ["vav_box"]),
    ], aliases=("price industries",)),
    _V("titus", "Titus", [
        _L("terminal-units", "VAV terminal units", ["vav_box"]),
    ]),
    _V("peerless", "Peerless Pump", [
        _L("fire-pumps", "Fire pump systems", ["fire_pump"]),
    ]),
    # ------------------------------------------------------------ plumbing
    _V("ao-smith", "A. O. Smith", [
        _L("water-heaters", "Commercial gas and electric water heaters (Cyclone family)",
           ["water_heater"]),
    ], aliases=("a.o. smith", "aosmith")),
    _V("rheem", "Rheem", [
        _L("water-heaters", "Commercial water heaters", ["water_heater"]),
    ], aliases=("ruud",)),
    _V("kohler", "Kohler", [
        _L("fixtures", "Commercial water closets, urinals, lavatories and sinks",
           ["water_closet", "urinal", "lavatory", "sink"]),
    ]),
    _V("american-standard", "American Standard", [
        _L("fixtures", "Commercial water closets, urinals and lavatories",
           ["water_closet", "urinal", "lavatory"]),
    ], parent="LIXIL"),
    _V("sloan", "Sloan", [
        _L("fixtures", "Vitreous china fixtures for flushometer applications",
           ["water_closet", "urinal", "lavatory"]),
    ]),
    _V("zurn", "Zurn Elkay", [
        _L("drains", "Floor and area drains (Z415 family)", ["floor_drain"]),
        _L("wilkins-backflow", "Wilkins backflow preventers and PRVs",
           ["backflow_preventer", "pressure_reducing_valve"]),
        _L("elkay-coolers", "Elkay drinking fountains and bottle fillers", ["drinking_fountain"]),
        _L("fixtures", "Commercial fixtures", ["water_closet", "urinal", "lavatory", "sink"]),
    ], aliases=("elkay", "wilkins", "zurn wilkins")),
    _V("watts", "Watts", [
        _L("backflow", "909 / 007 backflow preventers", ["backflow_preventer"]),
        _L("regulators", "Water pressure reducing valves", ["pressure_reducing_valve"]),
        _L("drains", "Floor drains", ["floor_drain"]),
    ], aliases=("watts water",)),
    _V("nibco", "NIBCO", [
        _L("valves", "Ball, gate, butterfly and check valves", ["valve"]),
    ]),
    _V("victaulic", "Victaulic", [
        _L("valves", "Grooved butterfly, check and ball valves", ["valve"]),
    ]),
    _V("jr-smith", "Jay R. Smith", [
        _L("drains", "Floor, area and roof drains", ["floor_drain"]),
    ], aliases=("jay r smith", "j.r. smith")),
)

_BY_KEY: Dict[str, Vendor] = {v.key: v for v in _ROWS}

_ALIAS: Dict[str, str] = {}
for _v in _ROWS:
    for _a in (_v.key, _v.name) + _v.aliases:
        _ALIAS.setdefault(TX._norm(_a), _v.key)


def vendors() -> Tuple[Vendor, ...]:
    return _ROWS


def get(key: str) -> Vendor:
    return _BY_KEY[key]


def resolve(text: Any) -> Optional[Vendor]:
    """Free text -> vendor by key, name or alias; None when the directory does not know it."""
    return _BY_KEY.get(_ALIAS.get(TX._norm(text), ""))


def lines_for_kind(kind: str) -> List[Tuple[Vendor, Line]]:
    """Every (vendor, line) that makes the taxonomy kind, facts-held lines first."""
    out = [(v, ln) for v in _ROWS for ln in v.lines if kind in ln.kinds]
    return sorted(out, key=lambda p: (not p[1].facts_held, p[0].key, p[1].key))


def facts_lines(kind: str) -> List[Tuple[str, str]]:
    """(catalog vendor, catalog line) pairs whose FACTS are held for the kind."""
    return [(v.key, ln.facts) for v, ln in lines_for_kind(kind) if ln.facts_held]


def _line_dict(v: Vendor, ln: Line) -> Dict[str, Any]:
    d = asdict(ln)
    d["facts_held"] = ln.facts_held
    d["vendor"] = v.key
    return d


def describe(key_or_text: Any, kind: Optional[str] = None) -> Dict[str, Any]:
    """One vendor, JSON-able, with the honest ``line`` a surface relays: which of its lines
    we hold facts for and which we can only name.  ``kind`` narrows to one taxonomy kind."""
    v = _BY_KEY.get(str(key_or_text)) or resolve(key_or_text)
    if v is None:
        return {"known": False, "query": str(key_or_text),
                "line": f"'{key_or_text}' is not a manufacturer the vendor directory knows "
                        f"({len(_ROWS)} vendors)"}
    lines = [ln for ln in v.lines if kind is None or kind in ln.kinds]
    held = [ln for ln in lines if ln.facts_held]
    named = [ln for ln in lines if not ln.facts_held]
    what = f" for {kind}" if kind else ""
    if held:
        line = (f"{v.name}{what}: sourced facts held for " +
                ", ".join(ln.label for ln in held) +
                (f"; known by name only (no member data): {', '.join(ln.label for ln in named)}"
                 if named else ""))
    elif lines:
        line = (f"{v.name}{what}: known lines {', '.join(ln.label for ln in lines)} -- no "
                f"sourced member data is held, so a family is generated at nominal/standard "
                f"dimensions and says so; supply a spec sheet for true dimensions")
    else:
        line = f"{v.name} makes nothing the directory lists{what}"
    return {"known": True, "key": v.key, "name": v.name, "parent": v.parent,
            "aliases": list(v.aliases), "lines": [_line_dict(v, ln) for ln in lines],
            "facts_held": [ln.facts for ln in held], "line": line}


def table() -> Dict[str, Any]:
    rows = [describe(v.key) for v in _ROWS]
    n_lines = sum(len(v.lines) for v in _ROWS)
    held = [(v.key, ln.facts) for v in _ROWS for ln in v.lines if ln.facts_held]
    return {"vendors": rows, "count": len(rows), "lines": n_lines,
            "facts_held": held, "facts_held_count": len(held),
            "kinds_covered": sorted({k for v in _ROWS for ln in v.lines for k in ln.kinds})}


def check() -> List[str]:
    """Problems that make the directory dishonest (empty = clean).  Gates, per #692: every
    ``facts`` claim loads through ``rvt.famgen.catalog`` from THIS vendor's directory and its
    ``category`` is the famspec kind the taxonomy row builds through; every line the catalog
    holds is claimed here exactly once; every kind named is a taxonomy row; keys and aliases
    are unambiguous."""
    from . import catalog as _C
    problems: List[str] = []
    seen_v: Dict[str, str] = {}
    claimed: Dict[Tuple[str, str], str] = {}
    tx_keys = set(TX.keys())
    for v in _ROWS:
        tag = f"vendors[{v.key}]"
        for a in (v.key, v.name) + v.aliases:
            n = TX._norm(a)
            if n in seen_v and seen_v[n] != v.key:
                problems.append(f"{tag}: alias {a!r} also claimed by {seen_v[n]!r}")
            seen_v.setdefault(n, v.key)
        line_keys = [ln.key for ln in v.lines]
        if len(set(line_keys)) != len(line_keys):
            problems.append(f"{tag}: duplicate line keys {line_keys}")
        for ln in v.lines:
            ltag = f"{tag}/{ln.key}"
            if not ln.kinds:
                problems.append(f"{ltag}: covers no kind")
            for k in ln.kinds:
                if k not in tx_keys:
                    problems.append(f"{ltag}: kind {k!r} is not a taxonomy row")
            if ln.facts is None:
                continue
            pair = (v.key, ln.facts)
            if pair in claimed:
                problems.append(f"{ltag}: facts {pair} also claimed by {claimed[pair]}")
            claimed[pair] = ltag
            try:
                data = _C.load_line(v.key, ln.facts)
            except Exception as e:                       # noqa: BLE001
                problems.append(f"{ltag}: facts {pair} do not load ({type(e).__name__}: {e})")
                continue
            if data.get("vendor") != v.key or data.get("line") != ln.facts:
                problems.append(f"{ltag}: facts file names {data.get('vendor')}/"
                                f"{data.get('line')}, not {v.key}/{ln.facts}")
            cat = data.get("category")
            for k in ln.kinds:
                row = TX.get(k) if k in tx_keys else None
                fam = row.famspec[0] if row and row.famspec else None
                if fam != cat:
                    problems.append(f"{ltag}: facts category {cat!r} but kind {k!r} builds "
                                    f"through famspec {fam!r}")
                if row and row.lane != "catalog":
                    problems.append(f"{ltag}: facts held for {k!r} whose lane is {row.lane!r}, "
                                    f"not 'catalog'")
    for pair in _C.list_lines():
        if pair not in claimed:
            problems.append(f"vendors: catalog holds {pair[0]}/{pair[1]} but no directory line "
                            f"claims it")
    return problems

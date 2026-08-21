"""VENDOR DIRECTORY -- who makes which MEP product lines, and for which of them the catalog
holds a record (#692).  The sibling of :mod:`rvt.famgen.taxonomy`.

The line this table walks (steer #685, restated on #692 because this is where it is tested):
**a manufacturer's name and a product line's name are things the engine may know; a
member's dimensions are not.**  So a :class:`Line` carries a label, the taxonomy kinds it
covers, and ``record=True`` only when ``rvt.famgen.catalog`` really holds
``facts/<vendor>/<line>.json``.  What that record is worth is COMPUTED, never declared:
:func:`record_tier` reads the catalog's own provenance report, so a record whose every value
is search-summary ``assumed`` (the LDN6 downlight today) is reported as exactly that, not as
"sourced facts".  :func:`check` loads every claimed record, confirms it is the vendor's own
and that its ``category`` is the famspec kind the taxonomy builds through, and confirms EVERY
line the catalog holds appears here exactly once.  A vendor we can name but hold nothing for
says so (:func:`describe`) -- never a silent substitution, never a recalled number.

No dimensions, ratings, prices or part numbers live here.  Adding a manufacturer or a line
is adding a row.  ``python tools/make_family.py vendors [VENDOR] [--kind K] [--check]
[--json]`` prints it.  :func:`scan` finds the makers a prompt names (the taxonomy's scanner
over this table's names) and :func:`record_for` says which held record a NAMED maker selects
for a kind -- what the plan resolver (``rvt.ifc.intent``) reads instead of a hard-coded
"eaton" (#692 DONE 5).
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass, asdict
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

from . import taxonomy as TX

__all__ = ["Vendor", "Line", "AMBIGUOUS_ALONE", "NOT_THAT_MAKER", "UNNAMED_MAKERS", "vendors", "makes",
           "get", "resolve", "scan", "lines_for_kind", "records_for_kind", "default_record",
           "record_for", "declared", "record_tier", "describe", "table", "record_row_problems",
           "check_line", "check"]


@dataclass(frozen=True)
class Line:
    key: str                       # slug, unique within the vendor; == the catalog line key
                                   # when ``record`` is True
    label: str                     # the product line as the maker names it (or a plain
                                   # description where no single trade name applies)
    kinds: Tuple[str, ...]         # taxonomy keys this line covers
    record: bool = False           # rvt.famgen.catalog holds facts/<vendor>/<key>.json
    default: bool = False          # the record its kinds are built from when no maker is read
                                   # (one per kind that has records; == the factory's own default)


@dataclass(frozen=True)
class Vendor:
    key: str                       # slug == the catalog's vendor directory name when held
    name: str
    lines: Tuple[Line, ...]
    aliases: Tuple[str, ...] = ()
    parent: str = ""               # owning group, informational ("Schneider Electric")


def _L(key, label, kinds, record=False, default=False) -> Line:
    return Line(key, label, tuple(kinds), record, default)


def _V(key, name, lines, aliases=(), parent="") -> Vendor:
    return Vendor(key, name, tuple(lines), tuple(aliases), parent)


_ROWS: Tuple[Vendor, ...] = (
    # ------------------------------------------------------------ electrical distribution
    _V("eaton", "Eaton", [
        _L("pow-r-line-panelboards", "Pow-R-Line panelboards (PRL1a/1X/2X/3X/4X)",
           ["panelboard"], record=True, default=True),
        _L("dry-type-transformers", "Dry-type distribution transformers (ventilated, 480-208Y)",
           ["transformer_dry"], record=True, default=True),
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
        _L("nq-nf-iline-panelboards", "NQ / NF / I-Line panelboards", ["panelboard"], record=True),
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
    _V("abb", "ABB", [                     # incl. the former GE Industrial Solutions lines
        _L("reliagear-panelboards", "ReliaGear lighting / power panelboards", ["panelboard"]),
        _L("reliagear-switchboards", "ReliaGear switchboards", ["switchboard"]),
        _L("acs-drives", "ACS-family variable frequency drives", ["variable_frequency_drive"]),
    ], aliases=("ge", "general electric", "ge industrial")),
    _V("hps", "Hammond Power Solutions", [
        _L("sentinel-g-transformers", "Sentinel G energy-efficient dry-type transformers",
           ["transformer_dry"], record=True),
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
           ["receptacle", "receptacle_20a", "light_switch", "junction_box"], record=True,
           default=True),
    ], aliases=("standards", "nema")),
    _V("hubbell", "Hubbell Wiring Device-Kellems", [
        _L("spec-grade-devices", "Commercial / spec-grade receptacles and switches",
           ["receptacle", "receptacle_20a", "light_switch"]),
        _L("floor-boxes", "Floor boxes and poke-throughs", ["floor_box"]),
    ]),
    _V("leviton", "Leviton", [
        _L("decora-commercial", "Decora and commercial spec-grade devices",
           ["receptacle", "light_switch", "dimmer_switch"]),
        _L("occupancy-sensors", "Occupancy / vacancy sensors", ["occupancy_sensor"]),
    ]),
    _V("legrand", "Legrand", [              # Pass & Seymour / Wattstopper / Wiremold brands
        _L("pass-seymour-devices", "Pass & Seymour spec-grade devices",
           ["receptacle", "light_switch"]),
        _L("wattstopper-controls", "Wattstopper occupancy sensors and lighting controls",
           ["occupancy_sensor", "daylight_sensor", "lighting_control_panel"]),
        _L("wiremold-floor-boxes", "Wiremold floor boxes and poke-throughs", ["floor_box"]),
    ], aliases=("pass & seymour", "pass and seymour", "wattstopper", "wiremold")),
    # ------------------------------------------------------------ lighting
    _V("lithonia", "Lithonia Lighting", [
        _L("blt-led-troffer", "BLT LED troffer", ["troffer"], record=True, default=True),
        _L("ldn6-led-downlight", "LDN6 LED downlight", ["downlight"], record=True, default=True),
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
    _V("edwards", "Edwards", [              # EST
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
        _L("grds", "Grilles, registers and diffusers", ["air_terminal"]),
    ], aliases=("price industries",)),
    _V("titus", "Titus", [
        _L("terminal-units", "VAV terminal units", ["vav_box"]),
        _L("grds", "Grilles, registers and diffusers", ["air_terminal"]),
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
_ALIAS, _ALIAS_CLASHES = TX._alias_index(_ROWS, lambda v: (v.key, v.name) + v.aliases)


def vendors() -> Tuple[Vendor, ...]:
    return _ROWS


def get(key: str) -> Vendor:
    return _BY_KEY[key]


def resolve(text: Any) -> Optional[Vendor]:
    """Free text -> vendor by key, name or alias; None when the directory does not know it."""
    return _BY_KEY.get(_ALIAS.get(TX._fold(text), ""))


#: maker names that are also plain English ('1200 watts', 'a cable carrier', 'unit price'):
#: :func:`scan` accepts them alone only when Capitalised as written.  The ``generic``
#: pseudo-vendor (standards-derived records) is never a maker a prompt can name.
AMBIGUOUS_ALONE: FrozenSet[str] = frozenset({
    "price", "cook", "taco", "york", "watts", "carrier", "halo", "est", "ge", "jci",
    "peerless", "simplex",
    "squared"})           # 'twenty feet squared' folds to the same letters as 'Square D'
_NEVER_NAMED = ("generic",)
_SCAN_INDEX: Dict[str, str] = {f: k for f, k in _ALIAS.items() if k not in _NEVER_NAMED}


def scan(text: Any) -> List[TX.Mention]:
    """Every maker ``text`` names (key / name / alias; whole words, longest first) as
    :class:`rvt.famgen.taxonomy.Mention` s -- ``Mention.key`` is the vendor key."""
    return TX._scan(text, _SCAN_INDEX, ambiguous=AMBIGUOUS_ALONE, proper=True)


def makes(vendor: Any, kind: str) -> bool:
    """Does the directory list a line of this maker (key, name, alias or :class:`Vendor`) for
    the taxonomy kind -- held record or named only?  False for a maker it does not know."""
    v = vendor if isinstance(vendor, Vendor) else (_BY_KEY.get(vendor) or resolve(vendor))
    return v is not None and any(kind in ln.kinds for ln in v.lines)


def lines_for_kind(kind: str) -> List[Tuple[Vendor, Line]]:
    """Every (vendor, line) that makes the taxonomy kind, catalog records first."""
    out = [(v, ln) for v in _ROWS for ln in v.lines if kind in ln.kinds]
    return sorted(out, key=lambda p: (not p[1].record, p[0].key, p[1].key))


def records_for_kind(kind: str) -> List[Tuple[str, str]]:
    """(catalog vendor, catalog line) pairs held for the kind."""
    return [(v.key, ln.key) for v, ln in lines_for_kind(kind) if ln.record]


#: how a maker-SUBSTITUTION sentence ends when the directory has no line of its own to say it
#: with (an unknown maker, a maker of other kinds, a maker's record that refused the member);
#: a maker named for the kind is answered by :func:`describe` in its own words ("never
#: presented as a product of <maker>") -- either way said once per sentence
NOT_THAT_MAKER = "never presented as that maker's product"
#: ... and the whole clause a substitution sentence closes with
_SUBSTITUTED = (" -- built here from what tekton holds for the kind instead and reported as "
                f"such; {NOT_THAT_MAKER}")

#: manufacturer cells that DECLARE nothing (blank, placeholder): no maker is read from them
UNNAMED_MAKERS: FrozenSet[str] = frozenset({
    "", "unspecified", "generic", "n/a", "n.a.", "na", "none", "null", "-", "$", "tbd",
    "by others", "varies", "unknown", "notdefined", "not defined", "undefined"})


def default_record(kind: str) -> Optional[Tuple[str, str]]:
    """The record a kind is built from when the input names no maker, or one nothing is held
    for: the held line flagged ``default=True`` for it -- ONE per kind that has records
    (:func:`check`), and the same one the factory's constructor defaults name (gated in
    ``taxonomy.check`` where the factory is already imported)."""
    return next(((v.key, ln.key) for v in _ROWS for ln in v.lines
                 if ln.record and ln.default and kind in ln.kinds), None)


def record_for(vendor: str, kind: str) -> Optional[Tuple[str, str]]:
    """The (catalog vendor, catalog line) this maker's HELD record for the taxonomy kind is,
    or None -- the maker is unknown, or known by name only for that kind (say so, never
    substitute silently: :func:`describe` has the line)."""
    v = _BY_KEY.get(vendor) or resolve(vendor)
    if v is None:
        return None
    return next(((v.key, ln.key) for ln in v.lines if ln.record and kind in ln.kinds), None)


def declared(text: Any, kind: str) -> Optional[Dict[str, Any]]:
    """What a DECLARED maker ('six Eaton panels', an IFC's Pset_ManufacturerTypeInformation)
    means for one taxonomy kind -- None when the cell declares nothing (``UNNAMED_MAKERS``).
    ``record`` is the held (vendor, line) the build should read instead of
    :func:`default_record`, or None; ``line`` is the ONE sentence every surface relays -- what
    :func:`describe` says of the maker for that kind, plus, whenever no record of the maker is
    read, the substitution said out loud (``NOT_THAT_MAKER``).  The prompt coverage and the
    plan resolver (``rvt.ifc.intent.declared_maker``) both use it (steer #685)."""
    named = str(text or "").strip()
    if named.lower() in UNNAMED_MAKERS:
        return None
    from . import catalog as _C
    known, vendor, name, rec, line = _declared(named, kind, _C.generation())
    return {"known": known, "vendor": vendor, "name": name, "record": rec, "line": line}


#: between a brand and its parent in one manufacturer cell: 'X by Y', 'X (Y)', 'X, a Y brand'
_RE_PARENT_JOIN = re.compile(
    r"\s*(?:\(|-|by\b|,?\s*(?:an?\s+)?(?:brand|company|division|business|part)\s+of\b|,?\s*an?\s+)\s*",
    re.I)


@functools.lru_cache(maxsize=256)
def _declared(text: str, kind: str, _generation: int = 0
              ) -> Tuple[bool, Optional[str], str, Optional[Tuple[str, str]], str]:
    """:func:`declared` memoised on its two words: the plan resolver asks once per equipment
    ITEM, and every answer costs a record parse (review of #736).  Keyed on the catalog's
    reload generation too, so ``catalog.reload()`` after an in-process record edit is seen."""
    # the cell as written on an IFC ('Eaton Corporation', 'Square D by Schneider Electric')
    # names its maker by the longest maker mention in it when it is not a name outright; a
    # cell naming TWO makers ('Eaton or Siemens') declares neither -- say so, pick none (#739)
    v = _BY_KEY.get(text) or resolve(text)
    if v is None:
        mentions = scan(text)
        # 'Cooper Lighting by Eaton', 'Cooper Lighting (Eaton)': the brand, then its parent
        if len(mentions) > 1 and _RE_PARENT_JOIN.fullmatch(text, mentions[0].end, mentions[1].start):
            mentions = mentions[:1]
        keys = sorted({m.key for m in mentions})
        if len(keys) > 1:
            names = ", ".join(_BY_KEY[k].name for k in keys)
            return (False, None, text, None, f"'{text}' names {len(keys)} makers ({names}), so "
                                             f"no single maker is read from it{_SUBSTITUTED}")
        v = _BY_KEY[keys[0]] if keys else None
    d = describe(v.key if v else text, kind=kind)
    rec = record_for(d["key"], kind) if d["known"] else None
    line = d["line"]
    # a maker the directory names for this kind already had its say (describe -> _buildability);
    # an unknown maker, or one that does not make the kind, gets the substitution said here
    if rec is None and not (d["known"] and makes(d["key"], kind)):
        line += _SUBSTITUTED
    return d["known"], d.get("key"), d.get("name", text), rec, line


def record_tier(vendor: str, line: str, *, model: Optional[str] = None) -> Dict[str, Any]:
    """What a held record is worth, counted from its own ``field_provenance`` flags: ``tier``
    is ``fact`` when at least one field is fact-tier, else ``assumed`` (search-summary values).
    ``model`` narrows the count to that one variant (the member a device sub-kind selects);
    None counts every variant of the line."""
    from . import catalog as _C
    variants = [x for x in _C.load_line(vendor, line).get("variants") or []
                if model is None or x.get("model") == model]
    flags = [f for x in variants for f in (x.get("field_provenance") or {}).values()]
    n_fact, n_assumed = flags.count("fact"), flags.count("assumed")
    return {"vendor": vendor, "line": line, "model": model, "variants": len(variants),
            "fields_fact": n_fact, "fields_assumed": n_assumed,
            "tier": "fact" if n_fact else "assumed"}


def _line_dict(v: Vendor, ln: Line, model: Optional[str] = None) -> Dict[str, Any]:
    d = asdict(ln)
    d["vendor"] = v.key
    if ln.record:
        d.update(record_tier(v.key, ln.key, model=model))
    return d


def _held_phrase(v: Vendor, ln: Line, model: Optional[str] = None) -> str:
    """What one held record is worth -- counted on the MEMBER (``model``) when a kind selects
    one variant of a shared record, else over the whole line."""
    t = record_tier(v.key, ln.key, model=model)
    member = f"variant {model}: " if model else ""
    if t["tier"] == "fact":
        return f"{ln.label} ({member}sourced facts: {t['fields_fact']} fact-tier fields)"
    return (f"{ln.label} ({member}a catalog record with NO fact-tier field: {t['fields_assumed']} "
            f"search-summary `assumed` values -- the family says so)")


def _buildability(v: Vendor, lines: List[Line], kind: Optional[str]) -> str:
    """What the engine can do here for the kinds these NAMED-ONLY lines cover -- computed from
    the taxonomy row's availability, never asserted; never phrased as building this maker's
    product from someone else's record (the silent substitution steer #685 forbids); and
    carrying the taxonomy's own category caveat."""
    keys = [kind] if kind else sorted({k for ln in lines for k in ln.kinds})
    parts = []
    for k in keys:
        row = TX.get(k)
        ok, why = TX.builder_available(row)
        if not ok:
            parts.append(f"{row.label}: not buildable here yet -- {why}{TX.caveat(row)}")
        elif row.lane == "catalog":
            parts.append(f"{row.label}: buildable here only from the records held ({why}) -- "
                         f"never presented as a product of {v.name}{TX.caveat(row)}")
        else:
            parts.append(f"{row.label}: generated without member data and says so ({why}) -- "
                         f"not a model of {v.name}; the name rides only as the declared "
                         f"Manufacturer value{TX.caveat(row)}")
    return "; ".join(parts)


def describe(text: Any, kind: Optional[str] = None) -> Dict[str, Any]:
    """One vendor, JSON-able, with the honest ``line`` a surface relays: which of its lines
    the catalog holds a record for (and what that record is worth) and which we can only
    name.  ``kind`` narrows to one taxonomy kind."""
    v = resolve(text)
    if v is None:
        return {"known": False, "query": str(text),
                "line": f"'{text}' is not a manufacturer the vendor directory knows "
                        f"({len(_ROWS)} vendors)"}
    lines = [ln for ln in v.lines if kind is None or kind in ln.kinds]
    held = [ln for ln in lines if ln.record]
    named = [ln for ln in lines if not ln.record]
    what = f" for {kind}" if kind else ""
    model = TX.member_model(kind)
    if held:
        line = (f"{v.name}{what}: catalog records held for " +
                "; ".join(_held_phrase(v, ln, model) for ln in held) +
                (f"; known by name only (no member data): {', '.join(ln.label for ln in named)}"
                 if named else ""))
    elif lines:
        line = (f"{v.name}{what}: known by name only -- {', '.join(ln.label for ln in lines)}; "
                f"no member data is held for any of them. " + _buildability(v, lines, kind))
    else:
        line = f"{v.name} makes nothing the directory lists{what}"
    return {"known": True, "key": v.key, "name": v.name, "parent": v.parent,
            "aliases": list(v.aliases), "lines": [_line_dict(v, ln, model) for ln in lines],
            "records": [ln.key for ln in held], "line": line}


def table() -> Dict[str, Any]:
    rows = [describe(v.key) for v in _ROWS]
    records = [record_tier(v.key, ln.key) for v in _ROWS for ln in v.lines if ln.record]
    return {"vendors": rows, "count": len(rows), "lines": sum(len(v.lines) for v in _ROWS),
            "records": records, "record_count": len(records),
            "kinds_covered": sorted({k for v in _ROWS for ln in v.lines for k in ln.kinds})}


# --------------------------------------------------------------------------- the gate

def record_row_problems(vendor: str, line: str, row: TX.Kind, *,
                        model: Optional[str] = None) -> List[str]:
    """Problems between ONE held record and ONE taxonomy row it serves (empty = they agree):
    the record loads, names its own vendor/line, is a record OF the famspec kind the row builds
    through, files under the row's Revit category, and holds the member (``model``) the row
    selects.  The one gate both ``vendors --check`` and ``taxonomy --check`` call."""
    from . import catalog as _C
    from .._clause import cause_clause
    try:
        data = _C.load_line(vendor, line)
        n_variants = record_tier(vendor, line, model=model)["variants"]
    except Exception as e:                               # noqa: BLE001 -- report, don't raise
        return [f"record {vendor}/{line} does not load ({cause_clause(e)})"]
    out: List[str] = []
    if (data.get("vendor"), data.get("line")) != (vendor, line):
        out.append(f"record {vendor}/{line} names itself {data.get('vendor')}/{data.get('line')}")
    cat = data.get("category")
    fams = [TX._mech(m)[1].partition("/")[0] for m in row.via if m.startswith("famspec:")]
    if cat not in fams:
        out.append(f"record {vendor}/{line}: record category {cat!r} but kind {row.key!r} "
                   f"builds through famspec {fams or 'nothing'} (lane {row.lane})")
    ost = _ost_label(data.get("revit_category"))
    if ost and row.category and ost != row.revit_category:
        out.append(f"record {vendor}/{line} files under {ost!r} ({data.get('revit_category')}) "
                   f"but kind {row.key!r} is filed under {row.revit_category!r}")
    if n_variants < 1:
        out.append(f"record {vendor}/{line} holds no variant" + (f" {model!r}" if model else "")
                   + f" -- the member kind {row.key!r} builds does not exist in it")
    return out


def check_line(v: Vendor, ln: Line) -> List[str]:
    """Problems ONE line has (empty = honest); :func:`check` runs it over the directory and
    the tests feed it deliberately broken lines."""
    tag = f"vendors[{v.key}/{ln.key}]"
    problems: List[str] = []
    rows = []
    if not ln.kinds:
        problems.append(f"{tag}: covers no kind")
    for k in ln.kinds:
        try:
            rows.append(TX.get(k))
        except KeyError:
            problems.append(f"{tag}: kind {k!r} is not a taxonomy row")
    if not ln.record:
        if ln.default:
            problems.append(f"{tag}: default=True on a line with no record")
        return problems
    for row in rows:
        problems.extend(f"{tag}: {msg}" for msg in
                        record_row_problems(v.key, ln.key, row, model=TX.member_model(row)))
    return problems


def _ost_label(ost_name: Any) -> Optional[str]:
    """'OST_ElectricalFixtures' -> 'Electrical Fixtures' via rvt.inventory's tables."""
    from .. import inventory as _INV
    for tab in (_INV.BUILTIN_CATEGORIES_VERIFIED, _INV.BUILTIN_CATEGORIES_ASSUMED):
        for _cid, (ost, label) in tab.items():
            if ost == ost_name:
                return label
    return None


def check() -> List[str]:
    """Problems that make the directory dishonest (empty = clean).  Per #692: every record
    claim loads through ``rvt.famgen.catalog`` from THIS vendor's directory and its
    ``category`` is the famspec kind the taxonomy row builds through; every line the catalog
    holds is claimed here exactly once; every kind named is a taxonomy row; keys and aliases
    are unambiguous."""
    from . import catalog as _C
    problems = list(_ALIAS_CLASHES)
    if len(_BY_KEY) != len(_ROWS):
        problems.append("vendors: duplicate vendor keys")
    problems.extend(f"vendors: AMBIGUOUS_ALONE word {w!r} is not a name any vendor carries"
                    for w in sorted(AMBIGUOUS_ALONE) if w not in _ALIAS)
    problems.extend(f"vendors: _NEVER_NAMED {k!r} is not a vendor key"
                    for k in _NEVER_NAMED if k not in _BY_KEY)
    claimed: Dict[Tuple[str, str], str] = {}
    for v in _ROWS:
        line_keys = [ln.key for ln in v.lines]
        if len(set(line_keys)) != len(line_keys):
            problems.append(f"vendors[{v.key}]: duplicate line keys {line_keys}")
        for ln in v.lines:
            problems.extend(check_line(v, ln))
            if ln.record:
                claimed[(v.key, ln.key)] = v.key
    for kind in sorted({k for v in _ROWS for ln in v.lines if ln.record for k in ln.kinds}):
        defaults = [(v.key, ln.key) for v in _ROWS for ln in v.lines
                    if ln.record and ln.default and kind in ln.kinds]
        if len(defaults) != 1:
            problems.append(f"vendors: kind {kind!r} has records but {len(defaults)} default "
                            f"lines {defaults} -- exactly one must carry default=True")
    for pair in _C.list_lines():
        if pair not in claimed:
            problems.append(f"vendors: catalog holds {pair[0]}/{pair[1]} but no directory line "
                            f"claims it (record=True)")
    for pair in claimed:
        if pair not in _C.list_lines():
            problems.append(f"vendors: {pair[0]}/{pair[1]} claims a record the catalog lacks")
    return problems

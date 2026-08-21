"""rvt.frontdoor.prompt_intent -- turn a natural-language PROMPT into the
front door's intent model, TWO ways.

(a) THE PRIMARY PATH IS A DOCUMENTED HANDOFF.  Every AI surface the product
    must be drivable from (Claude Design / Chat / Cowork, ChatGPT Work,
    Gemini, ...) already knows how to build a Three.js scene.  So the primary
    prompt route emits a compact **scene brief** (:func:`scene_brief`) + the
    exact IFC-authoring instructions (:func:`write_handoff`, backed by
    ``PROMPT_TO_IFC.md`` beside this module) that any surface can execute:
    build the Three.js scene, tag every product per OUR tagging contract
    (``userData.ifc`` + the schedule Psets), export IFC4 with the canonical
    three-d-stage exporter, and hand the ``.ifc`` back to the front door's
    ``--ifc`` route.  This mirrors the user's own established
    prompt -> Three.js scene -> IFC4 flow exactly.

(b) A BUILT-IN FALLBACK that WORKS WITH NO EXTERNAL MODEL CALL AND NO API
    KEY: :func:`parse_prompt` is a deterministic RULES-FIRST parser over our
    catalog vocabulary (rooms with dimensions + service rating; switchboards
    / distribution / lighting / receptacle panelboards / transformers /
    receptacles by count, rating, voltage, mains style, spaces; makers by
    name, read from :mod:`rvt.famgen.vendors`; walls; levels; feeders --
    and every OTHER equipment kind the MEP taxonomy knows,
    :mod:`rvt.famgen.taxonomy`, recognised and reported with that table's
    honest line instead of a product list kept here, #692),
    :func:`layout_room` places everything by a deterministic
    room-layout rule, and :func:`prompt_to_intent` builds the SAME
    :class:`rvt.ifc.intent.IntentModel` (spec v2) the IFC route resolves --
    same tagging-contract dict per equipment, same family mapping
    (:func:`rvt.ifc.intent.plan_families` over OUR generated content), same
    room-shell / feeder-tree shapes.  Its COVERAGE is stated honestly
    (:class:`PromptCoverage`: what it understood, what it ignored, what it
    recognised but cannot build, which defaults it applied) and rides into
    the deliverable manifest.

Example the fallback resolves end to end::

    "an electrical room 30x20 ft rated for 2500 A service with a main
     switchboard, two 400 A distribution panels and four lighting panels"
    -> room 9.144 x 6.096 m (4 walls, 3.66 m) ; MSB 2500 A switchboard (house
       family) ; DP-1/DP-2 400 A 480Y/277 MCB panelboards (Eaton PRL2X facts)
       ; LP-1..LP-4 lighting panelboards ; feeder tree MSB -> DP-1/DP-2/LP-*.

Territory: ``src/rvt/frontdoor/`` (front-door stream).  Imports (never edits)
``rvt.ifc.intent`` and ``rvt.famgen.factory`` (facts store).
"""
from __future__ import annotations

import functools
import json
import math
import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# LAZY (perf-coldstart): the prompt route is pure-python end to end; numpy
# stays un-imported unless a numeric path is actually exercised.
from .._lazyimp import lazy_import

np = lazy_import("numpy", globals(), "np", hint="prompt-intent numeric math")

from .. import _jsonsafe
from ..famgen import taxonomy as TX
from ..famgen import vendors as VD
from ..ifc import intent as I

__all__ = [
    "PromptError", "PromptItem", "PromptRoom", "ParsedPrompt", "PromptCoverage",
    "parse_prompt", "layout_room", "prompt_to_intent", "scene_brief",
    "write_handoff", "handoff_instructions_path", "FT_PER_M",
]

FT_PER_M = 3.280839895013123
M_PER_FT = 0.3048
IN_PER_M = 39.37007874015748

#: the shipped handoff instructions (any AI surface follows these)
_HERE = os.path.dirname(os.path.abspath(__file__))
PROMPT_TO_IFC_MD = os.path.join(_HERE, "PROMPT_TO_IFC.md")


class PromptError(ValueError):
    """The prompt could not be resolved into a buildable intent."""


# ============================================================================
# vocabulary (our catalog + electrical vocabulary)
# ============================================================================

#: number words
_NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "single": 1, "two": 2, "pair": 2, "double": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "dozen": 12, "no": 0, "zero": 0,
}

#: equipment kinds: (kind, tag prefix, regex over the noun phrase).  ORDER
#: MATTERS -- most specific first; a matched span is consumed so a bare
#: "panels" cannot re-match text a "distribution panels" clause already took.
#: A kind's ABBREVIATIONS sit in the named group ``abbr``: an abbreviation is
#: a noun ('two LPs') unless it is spelled as a tag reference ('LP-1').
_KIND_PATTERNS: List[Tuple[str, str, str]] = [
    ("switchboard", "MSB",
     r"(?:main\s+(?:service\s+)?)?(?:service\s+(?:entrance\s+)?)?switch\s*boards?"
     r"|switch\s*gear|(?P<abbr>\bmsb\b)|service\s+entrance\s+(?:board|equipment)"),
    ("distribution_panelboard", "DP",
     r"(?:power\s+)?distribution\s+(?:panel\s*boards?|panels?|boards?|sections?)"
     r"|power\s+panels?|(?P<abbr>\bmdp\b|\bdps?\b)|distribution\s+panelboards?"),
    ("lighting_panelboard", "LP",
     r"lighting\s+(?:and\s+appliance\s+)?(?:panel\s*boards?|panels?)|(?P<abbr>\blps?\b)"),
    ("receptacle_panelboard", "RP",
     r"(?:receptacle|appliance|branch(?:\s*-?\s*circuit)?|utility)\s+(?:panel\s*boards?|panels?)"
     r"|(?P<abbr>\brps?\b)"),
    ("transformer", "T",
     r"(?:dry[\s-]*type\s+)?(?:step[\s-]*(?:down|up)\s+)?transformers?|(?P<abbr>\bxfmrs?\b)"),
    ("panelboard", "PP",
     r"panel\s*boards?|(?:electrical\s+|branch\s+)?panels?"),
    # WIRING DEVICES (Electrical Fixtures, issue #166): our make_device family,
    # laid out at the ADA/NEC height on the west/east interior faces; the room
    # build loads ONE shared family per (kind, V, VA, height) and places every
    # device on it (issue #359)
    ("receptacle_device", "R",
     r"(?:duplex\s+|convenience\s+|quad\s+|gfci\s+|general[\s-]*purpose\s+)?"
     r"(?:receptacles?|(?:power\s+|wall\s+)?outlets?)(?!\s+panel)"),
]

#: kinds that carry a MOUNTING HEIGHT attribute ('at 18 in AFF') in their clause
_AFF_KINDS = ("receptacle_device",)

#: taxonomy row -> the grammar kind above that MODELS it in the room build: every row whose
#: intent kinds (``Kind.intent``) include one of this grammar's kinds -- derived, so the table
#: alone says that a switchgear lineup rides the switchboard clause and the 20 A receptacle the
#: receptacle clause.  Every other row the taxonomy recognises in a prompt is recorded NOT
#: built, with the table's own line (#692).
_GRAMMAR_KINDS = frozenset(k for k, _p, _r in _KIND_PATTERNS)
_SCENE_KIND: Dict[str, str] = {
    row.key: next(ik for ik in row.intent if ik in _GRAMMAR_KINDS)
    for row in TX.kinds() if any(ik in _GRAMMAR_KINDS for ik in row.intent)}
#: how a not-built line names what this route DOES model (the modelled rows' labels)
_MODELLED_PROSE = "switchboards, panelboards, transformers and receptacles"
#: an example clause per grammar kind, quoted when a prompt names a modelled kind in words
#: the grammar does not parse ('a load center')
_SCENE_EXAMPLE = {"panelboard": "two 225 A panels", "switchboard": "a 2000 A switchboard",
                  "transformer": "a 75 kVA transformer",
                  "receptacle_device": "6 duplex receptacles at 18 in AFF"}

#: architectural CONTEXT words -- not equipment, so not taxonomy rows -- recognised only to
#: say they are outside the model build (the room shell is walls; doors / pads are other streams)
_CONTEXT_PATTERNS: List[Tuple[str, str, str]] = [
    ("door", r"\bdoors?\b|egress",
     "doors belong to the hosting stream; the room shell this route builds is walls only"),
    ("housekeeping_pad", r"house\s*keeping\s+pads?|equipment\s+pads?",
     "housekeeping pads are recorded in the intent, not modelled (floor gear stands on the slab)"),
]

#: rating / attribute extractors (applied inside an equipment clause)
_RE_AMP = re.compile(r"(\d{2,5}(?:[.,]\d+)?)\s*(?:-?\s*)(?:a\b|amps?\b|ampere?s?\b)", re.I)
_RE_KVA = re.compile(r"(\d{1,4}(?:[.,]\d+)?)\s*(?:-?\s*)k\s*va\b", re.I)
_RE_KA = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:-?\s*)k\s*a(?:ic)?\b", re.I)
_RE_VOLT_SYS = re.compile(r"(\d{3}\s*Y\s*/\s*\d{2,3})\s*(?:v(?:olts?)?)?\b", re.I)
_RE_VOLT_PLAIN = re.compile(r"(\d{3})\s*(?:v\b|volts?\b|vac\b)", re.I)
_RE_VOLT_SLASH = re.compile(r"(\d{3})\s*/\s*(\d{2,3})\s*(?:v(?:olts?)?)?\b", re.I)
_RE_SPACES = re.compile(r"(\d{1,3})\s*[- ]?\s*(?:space|spaces|circuit|circuits|ckt|ckts|pole|poles|way|ways)\b", re.I)
_RE_MCB = re.compile(r"main\s+(?:circuit\s+)?breakers?|\bmcb\b|\bmb\b", re.I)
_RE_MLO = re.compile(r"main\s+lugs?(?:\s+only)?|\bmlo\b", re.I)
_RE_FLUSH = re.compile(r"flush(?:[\s-]*mount(?:ed)?)?|recessed", re.I)
_RE_SURFACE = re.compile(r"surface(?:[\s-]*mount(?:ed)?)?", re.I)
_RE_SECTIONS = re.compile(r"(\d{1,2})\s*[- ]?\s*sections?\b", re.I)
#: a device MOUNTING HEIGHT above the floor: 'at 18 in AFF', '44 inches above
#: the finished floor', '1100 mm mounting height' (unit AND an AFF phrase
#: required, so neither a bare count nor the room's 'N ft high' is read as one)
_RE_AFF = re.compile(
    r"(?:mounted\s+)?(?:at\s+)?(?P<h>\d{1,4}(?:\.\d+)?)\s*(?P<u>in\b|inch(?:es)?|\"|mm\b|m\b)\s*"
    r"(?:a\.?f\.?f\.?\b|above\s+(?:the\s+)?(?:finish(?:ed)?\s+)?floor|mounting\s+height)", re.I)
_NAMING_VERBS = r"(?:named|called|tagged|labell?ed|mark(?:ed)?|designated)"
_RE_NAMED = re.compile(_NAMING_VERBS + r"\s+[\"']?([A-Za-z][A-Za-z0-9\-]{0,11})[\"']?", re.I)
#: an equipment TAG token ('LP-1', 'DP2', 'T1', 'PP-3A'): a short letter
#: prefix + number -- or a lineup abbreviation that is conventionally the
#: tag itself ('main switchboard MSB')
_TAG_TOKEN = r"(?:[a-z]{1,4}-?\d{1,3}[a-z]?|msb|mdp)\b"
#: the tag LIST that may directly follow an equipment noun -- 'lighting
#: panel LP-1', 'panels LP-1, LP-2 and LP-3', 'panel named "LP-1"'.  It
#: deliberately reads across 'and' / ',' (a clause boundary everywhere
#: else) because there they join tags, not clauses.
_RE_TAG_LIST = re.compile(
    r"\s*(?:" + _NAMING_VERBS + r"\s+)?[\"']?" + _TAG_TOKEN + r"[\"']?"
    r"(?:\s*(?:,\s*(?:and\s+)?|\band\s+|&\s*)[\"']?" + _TAG_TOKEN + r"[\"']?)*", re.I)
_RE_TAG_TOKEN = re.compile(_TAG_TOKEN, re.I)
#: '-1' right after a kind abbreviation ('lp', 'dp', 'msb') makes the whole
#: token a tag REFERENCE ('LP-1'), not another equipment noun
_RE_TAG_SUFFIX = re.compile(r"-\d{1,3}[a-z]?\b", re.I)
#: count words before an equipment noun: numerals / number words, and the
#: wider token set that also counts articles ('a panel') and 'pair'
_COUNT_WORDS = r"\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
_RE_COUNT_WORD = re.compile(r"\b(" + _COUNT_WORDS + r")\b")
_RE_COUNT_TOK = re.compile(r"\b(" + _COUNT_WORDS + r"|a|an|pair|single)\b")

#: room / dimension extractors
_ROOM_NOUNS = r"room|closet|vault|space"        # the room this route builds (and a place, below)
_RE_ROOM = re.compile(
    r"(?P<pre>(?:main\s+|new\s+|the\s+)*(?:electrical|electric|elec\.?|equipment|switch\s*gear|"
    r"transformer|mechanical|electrical\s+equipment|mdf|idf|utility|service|panel)\s+)?"
    r"(?P<noun>" + _ROOM_NOUNS + r")\b", re.I)
_DIM_UNIT = r"(?:ft|feet|foot|'|m\b|meters?|metres?|mm\b|in\b|inch(?:es)?|\")"
_RE_DIMS = re.compile(
    r"(?P<w>\d{1,4}(?:\.\d+)?)\s*(?P<u1>" + _DIM_UNIT + r")?\s*(?:x|×|by)\s*"
    r"(?P<d>\d{1,4}(?:\.\d+)?)\s*(?P<u2>" + _DIM_UNIT + r")?", re.I)
_RE_HEIGHT = re.compile(
    r"(?P<h>\d{1,2}(?:\.\d+)?)\s*(?P<u>" + _DIM_UNIT + r")\s*(?:high|tall|ceiling|clear\s+height|head\s*room)"
    r"|(?:ceiling|clear\s+height|height)\s+(?:of\s+)?(?P<h2>\d{1,2}(?:\.\d+)?)\s*(?P<u2>" + _DIM_UNIT + r")",
    re.I)
_RE_SERVICE = re.compile(
    r"(?:rated\s+(?:for|at)\s+|with\s+|providing\s+|serving\s+)?(?:an?\s+)?"
    r"(?P<a>\d{3,5})\s*[- ]?\s*(?:a|amps?|ampere?s?)\s+(?:electrical\s+)?service\b"
    r"|service\s+(?:rated\s+(?:for|at)\s+|of\s+)?(?P<a2>\d{3,5})\s*[- ]?\s*(?:a|amps?|ampere?s?)\b", re.I)
#: 'rated for 250V' / '600V class' -- an amp-less service VOLTAGE rating.
#: Kept separate from :data:`_RE_SERVICE` (which is the AMP service clause)
#: so a voltage-only rating is never mistaken for a bus ampacity.
_RE_RATED_VOLT = re.compile(
    r"rated\s+(?:for|at)\s+(?:an?\s+)?(?P<v>\d{2,3})(?!\d)\s*[- ]?\s*(?:v\b|volts?\b|vac\b)"
    r"|(?P<v2>\d{2,3})(?!\d)\s*[- ]?\s*(?:v\b|volts?\b|vac\b)[\s-]*(?:rated\b|class\b)", re.I)
_RE_NO_WALLS = re.compile(r"no\s+walls|without\s+walls|equipment\s+only|no\s+room", re.I)
_RE_NO_FEEDERS = re.compile(r"no\s+(?:feeders|circuits)|without\s+(?:feeders|circuits)|uncircuited", re.I)
_RE_WALL_THICK = re.compile(r"walls?\s+(?:that\s+are\s+|of\s+)?(?P<t>\d{1,3}(?:\.\d+)?)\s*(?P<u>" +
                            _DIM_UNIT + r")\s*thick", re.I)
#: levels, three clause kinds (each may appear any number of times):
#: a STOREY COUNT ('two storey', '3-story', 'two floors', 'single storey'),
#: -- never the singular '<n> level <digit>' ('4 level 2 lighting panels' =
#: 4 panels on L2), while '2 storeys 14 ft floor to floor' still counts
_RE_STOREYS = re.compile(
    r"\b(?P<n>\d{1,2}|one|two|three|four|five|six|single|double)[\s-]*"
    r"(?:stor(?:e)?ys?\b|stories\b|levels\b|level\b(?![\s-]*\d)|floors\b)", re.I)
#: a LEVEL REFERENCE ('on level 2', 'the second floor', 'ground floor',
#: 'at L2') -- scoped to the equipment clause it sits in, else to the room,
_LEVEL_NOUN = r"(?:level|floor|stor(?:e)?y)"
_RE_LEVEL_REF = re.compile(
    r"\b(?:(?:on|at|to|serving)\s+)?(?:the\s+)?(?:"
    + _LEVEL_NOUN + r"\s+(?P<n>\d{1,2}|one|two|three|four|five|six|ground)\b"
    r"|(?P<o>ground|first|second|third|fourth|fifth|sixth|top|upper|\d{1,2}(?:st|nd|rd|th))[\s-]+"
    + _LEVEL_NOUN + r"\b(?![\s-]*to[\s-]*floor)"
    r"|(?<=\bon |\bat )l(?P<l>\d{1,2})\b)", re.I)
#: ordinal floor words -> storey number (US convention: first floor = ground
#: = Level 1); 'top' / 'upper' resolve to the highest storey
_ORDINAL_LEVEL = {"ground": 1, "first": 1, "second": 2, "third": 3, "fourth": 4,
                  "fifth": 5, "sixth": 6}
#: and the FLOOR-TO-FLOOR height ('floor to floor 14 ft', '4.2 m storey
#: height', '14 ft per storey') that spaces the level datums.
_RE_F2F = re.compile(
    r"(?:floor[\s-]*to[\s-]*floor|stor(?:e)?y[\s-]*height|level[\s-]*to[\s-]*level)(?:\s+height)?"
    r"\s*(?:of\s+|is\s+|=\s*|:\s*)?(?P<f>\d{1,2}(?:\.\d+)?)\s*(?P<u>" + _DIM_UNIT + r")"
    r"|(?P<f2>\d{1,2}(?:\.\d+)?)\s*(?P<u2>" + _DIM_UNIT + r")\s*"
    r"(?:floor[\s-]*to[\s-]*floor|per\s+(?:stor(?:e)?y|floor|level)|stor(?:e)?y\s+height)", re.I)
_RE_FED_FROM = re.compile(r"(?P<load>[A-Za-z][A-Za-z0-9\-]{0,10})\s+(?:is\s+)?fed\s+(?:from|by)\s+"
                          r"(?:the\s+)?(?P<src>[A-Za-z][A-Za-z0-9\-]{0,10})", re.I)

#: UL RATING CLASSES -> the service system they imply.  A '250 V'
#: panelboard rating names the equipment's MAXIMUM voltage class (UL 67),
#: not a system voltage; the system a 250 V-class rating implies is the
#: 240 V-class one.  Applying this mapping is ALWAYS stated in
#: ``coverage.defaults_applied`` -- never silent (the deliverable rule).
#: (600 V is NOT here: :func:`_voltage_system_from` already reads it as the
#: real 600Y/347 system.)
RATING_CLASS_TO_SYSTEM = {250: "240", 240: "240"}

#: default voltages / dims (prompt defaults -- always flagged as defaults)
DEFAULT_SERVICE_VOLTAGE = "480Y/277"
DEFAULT_ROOM_HEIGHT_M = 3.6576          # 12 ft
DEFAULT_WALL_THICKNESS_M = 0.2032       # 8 in
DEFAULT_PANEL_SPACES = 42
DEFAULT_LP_SPACES = 42
DEFAULT_PANEL_MOUNT_CENTER_M = 1.42     # enclosure centre AFF (top ~2.0 m for a 60 in box)
DEFAULT_PAD_M = 0.1                     # housekeeping pad height (floor gear elevation)
DEFAULT_XFMR_KVA = 75.0
DEFAULT_ROOM_W_M = 9.144                # 30 ft \ the DEFAULT room shell when a room is
DEFAULT_ROOM_D_M = 6.096                # 20 ft / named without dimensions (always stated)
DEFAULT_FLOOR_ALLOWANCE_M = 0.6096      # 2 ft of structure between a storey's clear height and the next floor
#: storeys the create path BUILDS today: the genesis base carries exactly two
#: building-story datums (Level 1 / Level 2) and the front door renames +
#: re-elevates them (the certified modify shape); it does not add levels or
#: plan views yet.  Storeys beyond this are recorded, never silently dropped.
BUILT_STOREYS = 2

#: prompt-default panelboard box (metres) used ONLY when the catalog resolver
#: refuses; a resolved plan REPLACES these with catalog facts
_DEF_PANEL_DIMS = {"w": 0.508, "d": 0.190, "h": 1.219}
_DEF_LP_DIMS = {"w": 0.508, "d": 0.146, "h": 1.219}
#: the prompted receptacle (kind ``receptacle_device``): OUR
#: make_device('duplex-receptacle') at 120 V with the NEC 220.14(I) 180 VA unit
#: load booked on its connector, at the facts' 18 in AFF convention -- ONE row
#: every device branch below reads, and the SAME row the resolver's
#: ``plan_family_for`` maps a device to (one source: rvt.ifc.intent)
DEFAULT_DEVICE_KIND = I.DEFAULT_DEVICE_KIND
DEFAULT_DEVICE_VOLTAGE = I.DEFAULT_DEVICE_VOLTAGE
DEFAULT_DEVICE_VA = I.DEFAULT_DEVICE_VA
DEFAULT_DEVICE_HEIGHT_IN = 18.0         # used only when the facts store is unavailable
DEVICE_PSET = I.DEVICE_PSET             # the device's schedule pset (scene brief / contract)
DEVICE_IFC = ("IfcOutlet", "POWEROUTLET")
_DEF_DEVICE_DIMS = {"w": 0.070, "d": 0.070, "h": 0.114}     # facts-store fallback only


@functools.lru_cache(maxsize=1)
def _device_facts():
    """OUR device fact sheet (rvt.famgen.factory.resolve_device_facts) for
    the prompted receptacle's default row, or None when the facts store
    refuses -- the LAYOUT's reader (height convention, envelope dims); the
    per-device plan + facts are the resolver's (``I.plan_family_for``).
    Memoised: every receptacle of a job reads the same record (read-only)."""
    try:
        from ..famgen import factory as F
        return F.resolve_device_facts(DEFAULT_DEVICE_KIND, voltage=DEFAULT_DEVICE_VOLTAGE,
                                      va=DEFAULT_DEVICE_VA)
    except Exception:                                    # noqa: BLE001 - stated fallback
        return None


def _device_label() -> str:
    """'NEMA 5-15R Duplex Receptacle' from OUR device table (one source)."""
    try:
        from ..famgen import factory as F
        d = F.DEVICE_KINDS[DEFAULT_DEVICE_KIND]
        return f"{d['type']} {d['label']}"
    except Exception:                                    # noqa: BLE001
        return "duplex receptacle"


def _device_height_default() -> Tuple[float, str]:
    """The receptacle mounting height the layout uses when the prompt names
    none: the facts record's typical convention (18 in to the box centre,
    'assumed') inside the ADA 308.2.1 reach envelope (15..48 in, the FACT)."""
    sheet = _device_facts()
    if sheet is None:
        return DEFAULT_DEVICE_HEIGHT_IN, "convention; device facts store unavailable"
    rng = sheet.get("ada_reach_range_in") or [15, 48]
    return (float(sheet.get("mounting_height_in")),
            f"design convention from generic/devices-and-mounting, flagged "
            f"'{sheet.values['mounting_height_in'].kind}'; ADA 308.2.1 reach envelope "
            f"{rng[0]:g}..{rng[1]:g} in to the operable part is the sourced fact")


def _device_voltage(item: "PromptItem") -> str:
    """A prompted (1-pole duplex) device's connector voltage from the clause's
    voltage -- the resolver's ONE rule (:func:`rvt.ifc.intent.device_voltage`:
    the line-to-neutral of a wye system, '208Y/120' -> 120; a plain number
    as is; else the 120 V default), so the contract and the plan agree."""
    return I.device_voltage(item.voltage)


# ============================================================================
# data model
# ============================================================================

@dataclass
class PromptItem:
    """One equipment (or recognised-but-unbuilt) item from the prompt."""
    kind: str
    tag: str
    count_index: int = 1
    rating_a: Optional[float] = None
    kva: Optional[float] = None
    voltage: Optional[str] = None
    mains: Optional[str] = None            # 'MCB' | 'MLO'
    spaces: Optional[int] = None
    sccr_ka: Optional[float] = None
    sections: Optional[int] = None
    mounting: Optional[str] = None
    height_in: Optional[float] = None      # device mounting height AFF (receptacle_device)
    fed_from: Optional[str] = None
    name: Optional[str] = None
    manufacturer: Optional[str] = None     # a maker the prompt NAMED for this item (its directory
                                           # name, rvt.famgen.vendors) -- carried as DECLARED
                                           # identity; the plan resolver says what is held
    level: Optional[int] = None            # storey number (1 = Level 1); None -> the room's
    source_text: str = ""
    buildable: bool = True
    unbuilt_reason: Optional[str] = None
    # layout results (metres, world)
    insertion_m: List[float] = dc_field(default_factory=lambda: [0.0, 0.0, 0.0])
    yaw_deg: float = 0.0
    front: List[float] = dc_field(default_factory=lambda: [0.0, -1.0, 0.0])
    frame_kind: str = "yaw"
    mount_kind: str = "floor"
    wall_id: Optional[str] = None
    dims_m: Dict[str, float] = dc_field(default_factory=dict)
    dims_source: str = "prompt-default"

    def as_json(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v not in (None, "", [])}


@dataclass
class PromptRoom:
    """The room shell from the prompt (metres)."""
    name: str = "Electrical Room"
    width_m: float = 0.0
    depth_m: float = 0.0
    height_m: float = DEFAULT_ROOM_HEIGHT_M
    wall_thickness_m: float = DEFAULT_WALL_THICKNESS_M
    service_rating_a: Optional[float] = None
    service_voltage: Optional[str] = None
    walls: bool = True
    level: int = 1                         # the storey the room (its walls + unplaced gear) sits on
    floor_to_floor_m: Optional[float] = None
    source_text: str = ""
    height_default: bool = True
    thickness_default: bool = True

    def as_json(self) -> Dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class PromptCoverage:
    """The honest coverage report: what the parser understood vs ignored."""
    understood: List[Dict[str, Any]] = dc_field(default_factory=list)
    ignored_words: List[str] = dc_field(default_factory=list)
    not_built: List[Dict[str, Any]] = dc_field(default_factory=list)
    defaults_applied: List[str] = dc_field(default_factory=list)
    warnings: List[str] = dc_field(default_factory=list)
    consumed_ratio: float = 0.0

    def as_json(self) -> Dict[str, Any]:
        return {
            "understood": list(self.understood),
            "ignored_words": list(self.ignored_words),
            "not_built": list(self.not_built),
            "defaults_applied": list(self.defaults_applied),
            "warnings": list(self.warnings),
            "consumed_ratio": round(self.consumed_ratio, 3),
            "statement": (
                "rules-first deterministic parser (no external model call, no API key): "
                "everything under 'understood' was normalised into the intent; "
                "'ignored_words' are prompt words the parser did not use; 'not_built' "
                "items were recognised -- as MEP taxonomy kinds (rvt.famgen.taxonomy), with "
                "that table's Revit category, lane and buildability -- but are outside this "
                "route's model build; 'defaults_applied' names every value the parser had to "
                "assume; a maker the prompt names is understood as DECLARED identity and the "
                "warnings say when no record of that maker is held."),
        }


@dataclass
class ParsedPrompt:
    """The full parse: room + items + feeders + coverage."""
    prompt: str
    room: Optional[PromptRoom]
    items: List[PromptItem]
    unbuilt: List[Dict[str, Any]]
    feeders: List[Tuple[str, str]]                 # (source_tag, target_tag) explicit
    auto_feeders: bool = True
    levels: List[dict] = dc_field(default_factory=list)
    coverage: PromptCoverage = dc_field(default_factory=PromptCoverage)
    project_name: str = "Front-door prompt job"

    @property
    def buildable_items(self) -> List[PromptItem]:
        return [it for it in self.items if it.buildable]

    def as_json(self) -> Dict[str, Any]:
        return {
            "prompt": self.prompt,
            "project_name": self.project_name,
            "room": self.room.as_json() if self.room else None,
            "levels": list(self.levels),
            "items": [it.as_json() for it in self.items],
            "not_built": list(self.unbuilt),
            "feeders_explicit": [{"from": a, "to": b} for a, b in self.feeders],
            "auto_feeders": self.auto_feeders,
            "coverage": self.coverage.as_json(),
        }


# ============================================================================
# helpers
# ============================================================================

def _to_metres(value: float, unit: Optional[str]) -> float:
    u = (unit or "ft").lower().strip()
    if u.startswith(("m", "metre", "meter")) and not u.startswith(("mm", "mi")):
        return float(value)
    if u.startswith("mm"):
        return float(value) / 1000.0
    if u.startswith(("in", "inch", "\"")):
        return float(value) * 0.0254
    return float(value) * M_PER_FT                   # ft / feet / '  (default)


def _num_word(tok: Optional[str]) -> Optional[int]:
    if tok is None:
        return None
    t = tok.strip().lower()
    if t.isdigit():
        return int(t)
    return _NUM_WORDS.get(t)


def _clean_num(s: str) -> float:
    return float(s.replace(",", ""))


def _in_any(a: int, b: int, spans: Sequence[Tuple[int, int]]) -> bool:
    """Does the half-open span ``[a, b)`` overlap any of ``spans``?"""
    return any(a < y and x < b for x, y in spans)


def _voltage_system_from(text: str) -> Optional[str]:
    """First voltage system in ``text`` -> canonical '480Y/277' / '208Y/120'
    / '480' / '277' (the tagging-contract label, no unit)."""
    m = _RE_VOLT_SYS.search(text)
    if m:
        return re.sub(r"\s+", "", m.group(1)).upper().replace("V", "")
    m = _RE_VOLT_SLASH.search(text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        hi, lo = max(a, b), min(a, b)
        ratio = hi / lo if lo else 0.0
        return f"{hi}Y/{lo}" if 1.6 < ratio < 1.85 else f"{hi}/{lo}"
    m = _RE_VOLT_PLAIN.search(text)
    if m:
        v = int(m.group(1))
        return {480: "480Y/277", 208: "208Y/120", 277: "480Y/277", 120: "208Y/120",
                600: "600Y/347", 240: "240"}.get(v, str(v))
    return None


def _pick_room_dims(text: str, m_room) -> Optional[re.Match]:
    """Choose the ROOM dimension expression among all 'W x D' matches:
    prefer one carrying a length unit, then one close to the room noun; skip
    fixture / trade sizes ('2x4 troffer', '4x4 box') that carry no unit and
    are followed by an equipment word."""
    cands = list(_RE_DIMS.finditer(text))
    if not cands:
        return None
    fixture_after = re.compile(r"^\s*(?:led\b|troffers?\b|fixtures?\b|luminaires?\b|"
                               r"downlights?\b|panels?\b|box(?:es)?\b|junction\b)", re.I)

    def is_fixture_size(m) -> bool:
        no_unit = not (m.group("u1") or m.group("u2"))
        small = _clean_num(m.group("w")) <= 8 and _clean_num(m.group("d")) <= 8
        return bool(no_unit and small and fixture_after.match(text[m.end():m.end() + 24]))

    good = [m for m in cands if not is_fixture_size(m)]
    if not good:
        return None
    with_unit = [m for m in good if (m.group("u1") or m.group("u2"))]
    if with_unit:
        return with_unit[0]
    if m_room is not None:
        near = [m for m in good if abs(m.start() - m_room.end()) <= 48 or abs(m_room.start() - m.end()) <= 48]
        if near:
            return near[0]
    return good[0]


def _wall_ring(width_m: float, depth_m: float) -> List[Tuple[str, List[float], List[float]]]:
    """Counter-clockwise centerline ring (S: west->east, E: south->north,
    N: east->west, W: north->south) so the interior is on the LEFT of every
    wall's drawing direction (the ifc-room stream's convention)."""
    hw, hd = width_m / 2.0, depth_m / 2.0
    return [
        ("W-S", [-hw, -hd], [hw, -hd]),
        ("W-E", [hw, -hd], [hw, hd]),
        ("W-N", [hw, hd], [-hw, hd]),
        ("W-W", [-hw, hd], [-hw, -hd]),
    ]


# ============================================================================
# THE PARSER (rules first, deterministic)
# ============================================================================

_STOPWORDS = frozenset("""
a an the and or with of for to in on at by from into onto per each all its it is are be
this that these those which as also plus rated new main service room space closet vault
electrical electric elec equipment building project provide provides providing include includes
including containing contains complete typical standard please build make create generate
model design me my our we i want need would like along wall walls level floor ground first
mounted mount inside side both ends end near next opposite across serving served serve
feeders feeder feeding fed feed circuit circuits circuited off out
""".split())


def _resolve_levels(room: Optional[PromptRoom], items: List[PromptItem], n_levels: int,
                    level_refs: List[Dict[str, Any]], f2f_m: Optional[float],
                    cov: PromptCoverage, *, defaulted: bool) -> List[dict]:
    """The level datums the prompt implies; sets the room's and every item's
    storey number on the way.

    A level reference bound to no equipment clause scopes the ROOM (its walls
    and every unreferenced item); items default to the room's storey.  Datums
    sit a floor-to-floor height apart (stated clause, else the room height +
    :data:`DEFAULT_FLOOR_ALLOWANCE_M`, recorded as a default).  Storeys past
    :data:`BUILT_STOREYS` stay in the intent and are recorded ``not_built``.
    ``defaulted`` (the prompt said nothing about levels) yields ONE storey
    flagged ``default`` -- it asserts nothing about the base's datum.
    """
    room_refs = [r for r in level_refs if not r["tags"]]
    room_level = room_refs[0]["n"] if room_refs else 1
    if len({r["n"] for r in room_refs}) > 1:
        cov.warnings.append("several room-level references (" + ", ".join(
            repr(r["text"]) for r in room_refs) + f"): the room is placed on Level {room_level}")
    if room is not None:
        room.level = room_level
    on_room_level = [it.tag for it in items if it.level is None]
    for it in items:
        if it.level is None:
            it.level = room_level
    for r in level_refs:
        cov.understood.append({"clause": r["text"], "level": f"L{r['n']}",
                               **({"as": "equipment level", "tags": r["tags"]} if r["tags"]
                                  else {"as": "room level"})})
    if defaulted:
        return [{"id": "L1", "name": "Level 1", "elevation": 0.0, "default": True}]
    h = room.height_m if room and room.height_m else DEFAULT_ROOM_HEIGHT_M
    step = f2f_m if f2f_m is not None else round(h + DEFAULT_FLOOR_ALLOWANCE_M, 4)
    if n_levels > 1:
        if f2f_m is None:
            cov.defaults_applied.append(
                f"floor-to-floor height: {step} m = room height {h} m + {DEFAULT_FLOOR_ALLOWANCE_M} m "
                "(2 ft) of structure -- say 'floor to floor N ft' to set it")
        if on_room_level:
            cov.defaults_applied.append(
                f"{', '.join(on_room_level)}: placed on Level {room_level} (the room's level; say "
                "'<equipment> on level N' to place an item elsewhere)")
    if n_levels > BUILT_STOREYS:
        beyond = ", ".join(f"Level {i}" for i in range(BUILT_STOREYS + 1, n_levels + 1))
        cov.not_built.append({
            "text": f"{n_levels} storeys", "kind": "storey",
            "reason": (f"storeys beyond {BUILT_STOREYS} (base carries two story levels): {beyond} "
                       "recorded in the intent, NOT created -- the front door renames and "
                       "re-elevates the base's two building-story datums (the certified modify "
                       "shape) and does not add levels / plan views yet; equipment on those "
                       "storeys is placed at their elevation, associated to the top built level")})
    return [{"id": f"L{i + 1}", "name": f"Level {i + 1}", "elevation": round(i * step, 4)}
            for i in range(n_levels)]


#: the taxonomy.describe() fields a not-built record carries verbatim
_NOT_BUILT_FIELDS = ("label", "revit_category", "discipline", "lane", "category_status")


def _kind_record(m: TX.Mention, *, maker: Optional[str] = None) -> Dict[str, Any]:
    """The NOT-BUILT record of one kind the taxonomy recognised: that table's honest line
    (Revit category, the lane that builds it or the lane that is missing, the category-id
    caveat) plus what THIS route does with the kind (#692 DONE 3), and the maker the prompt
    named for it, if any (a stated request: nothing of that maker is held or built).  Never
    silence, never a category of this module's own invention."""
    d = TX.describe(m.key)
    scene = _SCENE_KIND.get(m.key)
    if scene:
        tail = (f"this room build DOES model it, as '{scene}', but not in this phrasing -- say "
                f"e.g. '{_SCENE_EXAMPLE[scene]}' and it is built")
    elif d["available"]:
        hint = TX.famspec_hint(m.key)
        tail = ("a family this engine generates through the famspec lane"
                + (f" (route run --rfa '{hint}' --output rfa)" if hint else "")
                + f", not from a room prompt, whose build places {_MODELLED_PROSE} only: "
                  "recorded in the intent, NOT modelled")
    else:
        tail = "recorded in the intent, NOT modelled"
    rec = {"text": m.text, "kind": m.key, **{k: d[k] for k in _NOT_BUILT_FIELDS},
           "family_buildable_here": d["available"], "generic": bool(d["refine"]),
           "reason": f"{d['line']} -- {tail}"}
    if maker:
        rec["manufacturer"] = maker
        rec["reason"] += f"; maker named for it: {maker} (a stated request -- nothing built)"
    return rec


#: a HARD cue that a maker applies to the WHOLE job wherever it stands: 'all gear by Eaton',
#: 'everything from Square D', 'all by Eaton' just before the name; 'Eaton equipment
#: throughout', 'Eaton only', 'Eaton site-wide', 'Eaton for everything' just after it -- the
#: quantifier is required ('existing Siemens equipment' is no cue, #739).  A bare 'by X' /
#: 'from X' is item-level ('a fire alarm panel by Notifier'), and 'all|both by X' set off
#: INSIDE a list ('two panels, both by Eaton, and a transformer') names the noun before it.
_RE_CUE_BEFORE = re.compile(
    r"\b(?:(?:all|both)\s+(?:(?:of\s+)?the\s+)?(?:gear|equipment|products?|hardware|items)\s*"
    r"(?:(?:by|from|is|are|to\s+be|shall\s+be|[:=])\s*)?"
    r"|(?P<listable>(?:all|both)\s+(?:made\s+)?(?:by|from)\s*)"
    r"|everything(?:\s+else)?\s+(?:made\s+)?(?:by|from)\s*"
    r"|everything(?:\s+else)?\s*[:=]\s*)$", re.I)
_RE_CUE_AFTER = re.compile(
    r"^(?:\s+(?:gear|equipment|products?|hardware|brand))?,?\s+(?:"
    r"(?:throughout|everywhere|exclusively|across\s+the\s+board|[a-z]+-wide)\b"
    r"|for\s+(?:everything|the\s+whole\s+(?:job|project|room))\b"
    # 'Eaton only:' / 'Eaton for all.' close the phrase; 'Eaton only for panels' names a clause
    r"|(?:only|for\s+all(?:\s+of\s+(?:it|them))?(?:\s+(?:the\s+)?(?:gear|equipment|items))?)"
    r"(?=\s*(?:$|[,.;:)]|-\s)))", re.I)
#: a SOFT cue: 'manufacturer: Eaton', 'mfr Eaton', 'use Eaton', 'basis of design Eaton', 'to
#: match the existing Eaton gear', or a LEADING 'Eaton: ...'.  Inside a clause that names
#: equipment it ties the maker to that noun ('two panels, manufacturer Eaton'); leading or
#: trailing the job -- no equipment noun in its clause -- it names the job's maker for the
#: kinds that maker makes.
_RE_SOFT_CUE_BEFORE = re.compile(
    r"\b(?:(?:manufacturers?|mfr|mfg|brand|vendor|oem)\b\.?\s*(?:[:=-]|is|are|to\s+be|shall\s+be|"
    r"of\s+choice(?:\s+is)?)?|make\s*[:=]|(?:use|using|specify|standardi[sz]e\s+on|"
    r"basis\s+of\s+design(?:\s+is)?|bod)\b\s*[:=]?|match(?:ing)?\s+(?:the\s+)?(?:existing\s+)?)"
    r"\s*$", re.I)
#: ADJACENT: between a maker and the equipment noun it precedes ('a GE 75 kVA transformer',
#: 'two Eaton 225 A MLO panels'), or inside the parenthetical it fills ('(Eaton, 225 A)'),
#: stands nothing but what the equipment clause itself extracts as ratings -- the same
#: extractors, not a second vocabulary -- and these few words
_RATING_EXTRACTORS = (_RE_VOLT_SYS, _RE_VOLT_SLASH, _RE_VOLT_PLAIN, _RE_KVA, _RE_KA, _RE_AMP,
                      _RE_SPACES, _RE_SECTIONS, _RE_MCB, _RE_MLO, _RE_FLUSH, _RE_SURFACE)
_RE_PRIMARY_VOLT = re.compile(r"\b\d{3,5}\s*v?\s*-\s*(?=\d{3})", re.I)   # '480-208Y/120 V'
_RE_ADJ_RESIDUE = re.compile(          # single-character alternatives: no nested quantifier
    r"(?:\s|[-/()'\",]|\b(?:new|series|style|step[\s-]?(?:down|up)|nema\s*[0-9a-z]{1,3}|"
    r"(?:type|model|cat(?:alog)?\.?)(?:\s+[a-z0-9][\w/-]{0,11})?|"
    r"(?:single|three|[1-4])[\s-]?(?:ph(?:ase)?|p(?:ole)?s?|w(?:ire)?))\b)*$", re.I)
#: what ties a maker to the equipment noun (and tag list) it FOLLOWS: 'panels LP-1 and LP-2 by
#: Eaton', 'a transformer (Hammond)', 'a cable tray family by Eaton' ('two panels,
#: manufacturer: Eaton' is the soft cue's tie, above)
_RE_ADJ_TRAIL = re.compile(
    r"^(?:\s+(?:famil(?:y|ies)|units?|assembl(?:y|ies)|line-?ups?))?\s*,?\s*"
    r"(?:(?P<paren>\(\s*)|(?:(?:made|manufactured|built|supplied)\s+by|by|from)\s+)$", re.I)
#: two maker names that are ONE mention for attachment: 'Eaton or Siemens', 'Eaton / Siemens',
#: 'Eaton, Siemens or ABB' ('and' stays the clause boundary it is everywhere else)
_RE_RUN_JOINER = re.compile(r"\s*(?:,\s*(?:or\b)?|\bor\b|/|&)\s*", re.I)
#: a maker's name used as a PLACE or a client ('for the Edwards building', 'in Cooper Hall',
#: 'Sloan wing', 'the Kohler campus', 'Armstrong High School', 'the Hammond Street vault')
#: names no maker: the name is followed -- directly, or across a Capitalised proper-noun
#: phrase of up to two more words -- by a place noun that is a word of its own ('site-wide'
#: is not) with no equipment noun in between or right behind ('an Eaton house panel' is a
#: panel) (#739)
_RE_LOCATIVE_AFTER = re.compile(
    r"(?:\s+(?!(?i:for|the|an?|our|in|at|on|of|by|from|and|with|to|is|are)\b)[A-Z][\w.&'-]*){0,2}"
    r"\s+(?i:" + _ROOM_NOUNS + r"|building|bldg|plant|offices?|campus|hall|wing|annex|quad|"
    r"residences?|home|house|school|university|college|academy|institute|hospital|clinic|site|"
    r"jobsite|street|st|avenue|ave|road|rd|boulevard|blvd|highway|hwy|towers?|cent(?:er|re)|"
    r"facilit(?:y|ies)|warehouse|factory|mill|store|mall|plaza|park|hotel|motel|"
    r"church|chapel|library|museum|theat(?:er|re)|arena|stadium|gym|garage|station|depot|complex|"
    r"county|city|town|village|district|headquarters|hq|branch|property|estate|farm|ranch|"
    r"labs?|laboratory|pavilion|dock|pier|airport|campus(?:es)?|lodge|manor|villa|studios?|"
    r"suite|apartments?|condos?|dorm(?:itory)?|data\s+cent(?:er|re))(?![\w-])")
#: a sentence stop -- not a decimal point ('7.5 kVA'), not an abbreviation's ('mfr. Eaton')
_RE_STOP = re.compile(r";|(?<!\b(?:mfr|mfg|inc))(?<!\bcorp)(?<!\b[cn]o)\.(?!\d)", re.I)
#: EXISTING or NEIGHBOURING gear is context: it names the maker of the noun it qualifies
#: ('next to an Eaton 75 kVA transformer') and of nothing else ('two panels beside the
#: existing Siemens equipment')
_RE_CONTEXT_BEFORE = re.compile(
    r"\b(?:existing|(?:beside|next\s+to|adjacent\s+to|alongside|near)\s+(?:the|an?|our)?)\s*$",
    re.I)


def _only_ratings(gap: str) -> bool:
    """Is ``gap`` nothing but equipment ratings and joining punctuation?  Measured with the
    clause's own extractors, so 'adjacent' means exactly what the clause reads as attributes."""
    gap = _RE_PRIMARY_VOLT.sub(" ", gap)
    for rx in _RATING_EXTRACTORS:
        gap = rx.sub(" ", gap)
    return bool(_RE_ADJ_RESIDUE.match(gap))


def _attach_makers(text: str, maker_mentions: Sequence[TX.Mention],
                   noun_groups: Sequence[Tuple[Tuple[int, int], List["PromptItem"]]],
                   unbuilt_anchors: Sequence[TX.Mention], items: List["PromptItem"],
                   clause_window, mark, cov: "PromptCoverage",
                   ) -> Tuple[Dict[TX.Mention, str], Optional[str], str]:
    """Attach every maker the prompt names (reviews of #736, #739).  Names joined by 'or',
    '/', 'and' ('Eaton or Siemens') are ONE mention here -- wherever it lands, two makers on
    one thing apply neither and a warning says so.

    * a name used as a PLACE or client ('for the Edwards building', 'the Kohler campus') names
      no maker -- it is an ignored word; EXISTING or neighbouring gear ('next to an Eaton
      transformer', 'beside the existing Siemens equipment') names the maker of the noun it
      qualifies and of nothing else, and says so when that is nothing;
    * a maker with a whole-job CUE applies to the items that name no maker of their own: a
      HARD cue ('all gear by Eaton', 'everything from Square D', 'Eaton equipment throughout')
      to every one of them, a SOFT cue ('manufacturer: Eaton' leading or trailing the job,
      'use Eaton', 'to match the existing Eaton gear', a leading 'Eaton: ...') to those of the
      kinds the directory says the maker makes, saying what it skipped; exactly one such
      maker may; a bare 'by X' is item-level, and a cue set off INSIDE a list ('two panels,
      both by Eaton, and ...', '..., manufacturer Eaton, ...') names the noun before it;
    * every other maker goes to the NEAREST equipment noun inside its clause window -- a built
      item group or a not-built kind ('a 500 kW Cummins generator' names the generator's
      maker; the panels in the same sentence keep none) -- when the directory says the maker
      makes that kind; a maker that does NOT make it rides the noun only when the two are
      ADJACENT ('a Trane panel', 'six Square D receptacles', 'panels LP-1 and LP-2 by
      Kohler'), and is then declared and said, never silently;
    * a WEAK name -- one plain-English word read as a maker only because it is Capitalised
      ('York', 'Price', 'Watts', 'Simplex'; ``Mention.weak``) -- counts only where that maker
      makes the noun's kind (the job's kinds, for a cue); anywhere else it stays an ignored
      word.  'Square D' and an acronym ('a GE transformer') are real names, not weak ones;
    * a real maker's name with no equipment noun in its clause and no cue applies to nothing,
      and a warning says so.

    Returns ({not-built mention: maker name}, the whole-job maker's vendor key or None, and
    -- for the nothing-buildable message -- the names that then applied to nothing)."""
    anchors: List[Tuple[Tuple[int, int], Optional[List["PromptItem"]], Optional[TX.Mention]]] = (
        [(span, its, None) for span, its in noun_groups]
        + [((m.start, m.end), None, m) for m in unbuilt_anchors])
    first_anchor = min((a[0][0] for a in anchors), default=len(text))
    item_kind = {it.tag: TX.for_intent_kind(it.kind).key for it in items}   # taxonomy rows
    built_kinds = set(item_kind.values())

    runs: List[List[TX.Mention]] = []                  # 'Eaton or Siemens' is one mention
    for mm in maker_mentions:
        if runs and _RE_RUN_JOINER.fullmatch(text, runs[-1][-1].end, mm.start):
            runs[-1].append(mm)
        else:
            runs.append([mm])

    def anchor_kind(i: int) -> str:                    # the taxonomy row an anchor stands for
        _span, its, unbuilt = anchors[i]
        return item_kind[its[0].tag] if its else unbuilt.key

    def makes(run: Sequence[TX.Mention], kind: str) -> bool:
        return any(VD.makes(mm.key, kind) for mm in run)

    def adjacent(s: int, e: int, i: int) -> bool:      # run text[s:e] and anchor i
        (a_start, a_end), _its, _unbuilt = anchors[i]
        if a_start >= e:                               # 'a GE 75 kVA transformer'
            return _only_ratings(text[e:a_start])
        tie = _RE_ADJ_TRAIL.match(text[a_end:s])      # 'panels LP-1, LP-2 by Eaton'
        if tie and tie.group("paren"):                 # '(Eaton, 225 A)' -- not '(Generac backup)'
            close = text.find(")", e)
            return close >= 0 and _only_ratings(text[e:close])
        return bool(tie)

    def next_anchor(e: int) -> Optional[int]:         # the first noun after position e
        later = [i for i, a in enumerate(anchors) if a[0][0] >= e]
        return min(later, key=lambda i: anchors[i][0][0]) if later else None

    def preceding(s: int, e: int) -> List[int]:      # the nouns a mid-list aside follows in
        stop = max((b.end() for b in _RE_STOP.finditer(text, 0, s)), default=0)   # its sentence,
        before = [i for i, a in enumerate(anchors) if stop <= a[0][1] <= s]   # nearest LAST; []
        later = next_anchor(e) is not None                                   # when trailing
        return sorted(before, key=lambda i: anchors[i][0][1]) if later else []

    def locative(e: int) -> bool:                      # '... the Edwards building'
        m = _RE_LOCATIVE_AFTER.match(text, e)
        if not m:
            return False
        nxt = next_anchor(e)                           # 'Eaton site lighting panels': a qualifier
        return nxt is None or text[m.end():anchors[nxt][0][0]].strip() != "" and anchors[nxt][0][0] >= m.end()

    cued: Dict[TX.Mention, bool] = {}                  # whole-job makers: is the cue HARD?
    on_anchor: Dict[int, List[TX.Mention]] = {}
    unplaced: List[TX.Mention] = []                    # a real maker's name, nothing to hang it on
    contextual: List[TX.Mention] = []                  # names existing / neighbouring gear only
    for run in runs:
        s, e = run[0].start, run[-1].end
        head, tail = text[:s], text[e:]
        weak = all(mm.weak for mm in run)
        soft = _RE_SOFT_CUE_BEFORE.search(head)
        lo = soft.start() if soft else s               # what to consume along with the name
        if locative(e):
            continue                                   # a place, a client: an ignored word
        if not soft and _RE_CONTEXT_BEFORE.search(head):
            nxt = next_anchor(e)                       # existing / neighbouring gear: the maker
            if nxt is not None and adjacent(s, e, nxt):   # of the noun it qualifies, no other
                on_anchor.setdefault(nxt, []).extend(run)
            elif not weak:
                contextual.extend(run)
            mark((s, e))
            continue
        before, after = _RE_CUE_BEFORE.search(head), _RE_CUE_AFTER.match(tail)
        listed = preceding(s, e) if before and before.group("listable") else []   # 'both by X'
        if (before or after) and not listed:           # the whole-job cue wins wherever it stands
            if weak and not any(makes(run, k) for k in built_kinds):
                continue                               # 'designed by York Engineering': a word
            cued.update((mm, True) for mm in run)
            mark(((before or soft).start() if (before or soft) else s,
                  e + (after.end() if after else 0)))
            continue
        ws, we = clause_window(s, e)                   # a tag list reads across 'and': overlap
        cands = [i for i, a in enumerate(anchors) if a[0][0] < we and a[0][1] > ws]
        tie: List[int] = []                            # a cue set off mid-list names the noun(s)
        if listed:                                     # before it: '..., both by Eaton, ...' the
            tie, lo = listed, before.start()           # list, '..., manufacturer Eaton, ...' the
        elif soft and not cands:                       # last one
            tie = preceding(s, e)[-1:]
        if tie:
            cands = tie
        elif (soft and not cands or tail.lstrip().startswith(":") and s < first_anchor) \
                and not weak:
            cued.update((mm, False) for mm in run)     # 'manufacturer: Eaton' / 'Eaton: ...'
            mark((lo, e))
            continue
        fits = [i for i in cands if makes(run, anchor_kind(i))]
        if weak:                                       # 'our New York office', '1200 Watts',
            cands = fits                               # '4 Simplex receptacles'
        if not cands:
            if not weak:
                unplaced.extend(run)
                mark((lo, e))
            continue

        def gap(i: int) -> float:                     # distance to the anchor; the FOLLOWING
            a_start, a_end = anchors[i][0]             # noun wins a tie ('Cummins generator')
            return (a_start - e) if a_start >= e else (s - a_end) + 0.5
        nearest = min(cands, key=gap)
        if not (nearest in fits or tie or soft or adjacent(s, e, nearest)):
            # a maker of OTHER kinds, not adjacent to this noun: the nearest noun it does make,
            # else a client's / person's name -- an ignored word ('Kohler wants 4 panels')
            if not fits:
                continue
            nearest = min(fits, key=gap)
        for i in (tie if listed else [nearest]):       # 'all by X' mid-list: the whole list
            on_anchor.setdefault(i, []).extend(run)
        mark((lo, e))
    unbuilt_makers: Dict[TX.Mention, str] = {}
    for i, mms in on_anchor.items():
        names = sorted({VD.get(mm.key).name for mm in mms})
        _span, its, unbuilt = anchors[i]
        if len(names) > 1:
            what = ", ".join(it.tag for it in its) if its else f"'{unbuilt.text}'"
            cov.warnings.append(f"{what}: makers {', '.join(names)} are both named for it -- "
                                "applied neither; name one")
        elif its is not None:
            for it in its:
                it.manufacturer = names[0]
        else:
            unbuilt_makers[unbuilt] = names[0]
            cov.understood.append({"clause": names[0], "as": "manufacturer",
                                   "vendor": mms[0].key, "kind": unbuilt.key,
                                   "applies_to": unbuilt.text, "record": None})

    def called(mms: Iterable[TX.Mention]) -> str:      # 'ABB (written GE), Eaton'
        return ", ".join(sorted({VD.get(mm.key).name + ("" if TX._fold(mm.text) in
                                 TX._fold(VD.get(mm.key).name) else f" (written {mm.text})")
                                 for mm in mms}))

    # the WHOLE-JOB maker: exactly one may be cued.  A HARD cue ('all gear by Eaton', 'Eaton
    # throughout') is taken at its word for every item that names no maker of its own; a SOFT
    # one ('manufacturer: Hammond', 'use Eaton', 'Eaton: ...') names the maker for the job's
    # equipment the directory says it makes -- a transformer maker named that way is not
    # stamped onto the panelboards -- and what it skipped is said
    cued_keys = sorted({mm.key for mm in cued})
    global_maker: Optional[str] = None
    if len(cued_keys) == 1 and items:
        key, hard = cued_keys[0], any(cued.values())
        name = VD.get(key).name
        open_kinds = {item_kind[it.tag] for it in items if not it.manufacturer}
        made = {k for k in open_kinds if VD.makes(key, k)}
        targets = [it for it in items if not it.manufacturer and (hard or item_kind[it.tag] in made)]
        for it in targets:
            it.manufacturer = name
        labels = lambda ks: ", ".join(sorted(TX.get(k).label for k in ks))   # noqa: E731
        force = f"write 'all gear by {name}' or name it inside a clause to declare it regardless"
        if targets:
            global_maker = key
            if not hard and made != open_kinds:
                cov.warnings.append(
                    f"maker {called(cued)} is named for the job but the vendor directory lists no "
                    f"{labels(open_kinds - made)} by it -- applied to the {labels(made)} only ("
                    + ", ".join(it.tag for it in targets) + f"); {force}")
        elif not open_kinds:                           # 'six Eaton panels; manufacturer: Siemens'
            cov.warnings.append(f"maker {called(cued)} is named for the job but every item "
                                "already names its own maker -- applied to nothing")
        elif not hard:                                 # 'Kohler: 4 panels'
            cov.warnings.append(f"maker {called(cued)} is named for the job but the vendor "
                                f"directory lists none of its equipment ({labels(open_kinds)}) "
                                f"by it -- applied to nothing; {force} ('two {name} panels')")
    elif cued_keys:
        cov.warnings.append(f"makers {called(cued)} are all named for the whole job -- applied "
                            "to nothing; name one, or name each inside its clause ('six Eaton "
                            "panels')")
    if contextual:
        cov.warnings.append(f"maker {called(contextual)} names existing or neighbouring "
                            "equipment, not the new work -- applied to nothing; write 'to match "
                            "the existing <maker> gear' to carry it over")
    if unplaced:
        cov.warnings.append(f"maker {called(unplaced)} is named outside any equipment clause -- "
                            "applied to nothing; write 'all gear by <maker>' for the whole job "
                            "or name it inside the clause ('six Eaton panels')")
    # when nothing was built no cue applied: every cued or unplaced name went nowhere
    return unbuilt_makers, global_maker, called([*unplaced, *cued])


def _maker_coverage(items: List["PromptItem"], global_key: Optional[str],
                    cov: "PromptCoverage") -> None:
    """One 'understood' entry per (maker, kind) the prompt named, and ONE warning wherever no
    record of that maker is held for the kind -- the vendor directory's own sentence
    (``vendors.declared``), the same one the plan resolver puts on the family plan: those
    items are built from the records that ARE held (or as our house model) and say so;
    nothing is presented as that maker's product (steer #685).  ``global_key`` is the maker
    that was named for the whole job ('all gear by Eaton'), if one was."""
    groups: Dict[Tuple[str, str], List["PromptItem"]] = {}
    for it in items:
        if it.manufacturer:
            groups.setdefault((it.manufacturer, it.kind), []).append(it)
    for (name, kind), its in groups.items():
        d = VD.declared(name, TX.for_intent_kind(kind).key)
        tags = [it.tag for it in its]
        entry: Dict[str, Any] = {"clause": name, "as": "manufacturer", "vendor": d["vendor"],
                                 "kind": kind, "tags": tags,
                                 "record": "/".join(d["record"]) if d["record"] else None}
        if d["vendor"] == global_key:
            entry["scope"] = "named for the job, not inside one clause: applied to these items"
        cov.understood.append(entry)
        if d["record"] is None:
            cov.warnings.append(f"{', '.join(tags)}: {d['line']}")


def parse_prompt(prompt: str) -> ParsedPrompt:
    """Deterministically parse ``prompt`` into a :class:`ParsedPrompt`.

    Rules-first over our vocabulary; NO external model call.  The coverage
    report says exactly what was understood, ignored, defaulted, and what
    was recognised but is not buildable today.
    """
    text = " ".join(str(prompt or "").split())
    if not text:
        raise PromptError("empty prompt")
    low = text.lower()
    # numpy-free consumed mask (perf-coldstart): the rules parser must run
    # on a bare sandbox with zero extras
    consumed = bytearray(len(text))
    cov = PromptCoverage()

    def mark(span: Tuple[int, int]) -> None:
        a, b = max(0, span[0]), min(len(text), span[1])
        if b > a:
            consumed[a:b] = b"\x01" * (b - a)

    # ------------------------------------------------------------------
    # 1. the ROOM (dimensions, height, service rating, wall options)
    # ------------------------------------------------------------------
    room: Optional[PromptRoom] = None
    m_room = _RE_ROOM.search(text)
    m_dims = _pick_room_dims(text, m_room)
    no_walls = bool(_RE_NO_WALLS.search(text))
    # the floor-to-floor height is a LEVEL spacing, never the room's clear
    # height: found first so 'floor to floor height of 14 ft' cannot be
    # read by the height grammar below
    m_f2f = _RE_F2F.search(text)
    f2f_m: Optional[float] = None
    if m_f2f:
        mark(m_f2f.span())
        f2f_m = round(_to_metres(_clean_num(m_f2f.group("f") or m_f2f.group("f2")),
                                 m_f2f.group("u") or m_f2f.group("u2")), 4)
        cov.understood.append({"clause": m_f2f.group(0), "as": "floor-to-floor height",
                               "height_m": f2f_m})
    if m_room or m_dims:
        room = PromptRoom()
        if m_room:
            mark(m_room.span())
            pre = (m_room.group("pre") or "").strip()
            room.name = (f"{pre} {m_room.group('noun')}".strip().title()
                         if pre else "Electrical Room")
            room.source_text += m_room.group(0)
        if m_dims:
            mark(m_dims.span())
            u1 = m_dims.group("u1") or m_dims.group("u2") or "ft"
            u2 = m_dims.group("u2") or m_dims.group("u1") or "ft"
            room.width_m = round(_to_metres(_clean_num(m_dims.group("w")), u1), 4)
            room.depth_m = round(_to_metres(_clean_num(m_dims.group("d")), u2), 4)
            room.source_text += " " + m_dims.group(0)
            cov.understood.append({"clause": m_dims.group(0), "as": "room dimensions",
                                   "width_m": room.width_m, "depth_m": room.depth_m,
                                   "unit_assumed": (u1 if (m_dims.group("u1") or m_dims.group("u2"))
                                                    else "ft (default)")})
            if not (m_dims.group("u1") or m_dims.group("u2")):
                cov.defaults_applied.append("room dimension unit: feet (no unit given)")
        else:
            # a room was NAMED: build the default shell (stated, never silent)
            # rather than silently dropping to an equipment-only layout --
            # 'an electrical room with 6 panels' must yield a room.
            room.width_m = DEFAULT_ROOM_W_M
            room.depth_m = DEFAULT_ROOM_D_M
            cov.defaults_applied.append(
                f"room dimensions: {DEFAULT_ROOM_W_M:g} x {DEFAULT_ROOM_D_M:g} m "
                "(30 x 20 ft) DEFAULT room shell -- the room was named with no "
                "dimensions; say 'W by D ft' to size it")
        m_h = next((m for m in _RE_HEIGHT.finditer(text)
                    if not (m_f2f and _in_any(m.start(), m.end(), [m_f2f.span()]))), None)
        room.floor_to_floor_m = f2f_m
        if m_h:
            mark(m_h.span())
            hv, hu = (m_h.group("h"), m_h.group("u")) if m_h.group("h") else (m_h.group("h2"), m_h.group("u2"))
            room.height_m = round(_to_metres(_clean_num(hv), hu), 4)
            room.height_default = False
            cov.understood.append({"clause": m_h.group(0), "as": "room height",
                                   "height_m": room.height_m})
            if f2f_m is not None and room.height_m > f2f_m:
                cov.warnings.append(f"room height {room.height_m} m exceeds the floor-to-floor "
                                    f"height {f2f_m} m: the walls run past the level above")
        elif f2f_m is not None:
            # a stated floor-to-floor height sizes the (unstated) clear height
            room.height_m = round(max(f2f_m - DEFAULT_FLOOR_ALLOWANCE_M, f2f_m / 2.0), 4)
            cov.defaults_applied.append(
                f"room height: {room.height_m} m = the floor-to-floor height {f2f_m} m less "
                f"{DEFAULT_FLOOR_ALLOWANCE_M} m (2 ft) of structure -- say 'N ft high' to set it")
        else:
            cov.defaults_applied.append(f"room height: {DEFAULT_ROOM_HEIGHT_M} m (12 ft)")
        m_wt = _RE_WALL_THICK.search(text)
        if m_wt:
            mark(m_wt.span())
            room.wall_thickness_m = round(_to_metres(_clean_num(m_wt.group("t")), m_wt.group("u")), 4)
            room.thickness_default = False
            cov.understood.append({"clause": m_wt.group(0), "as": "wall thickness",
                                   "thickness_m": room.wall_thickness_m})
        else:
            cov.defaults_applied.append(
                f"wall thickness: {DEFAULT_WALL_THICKNESS_M} m location-line offset "
                "(the built wall uses the base wall type's compound structure)")
        if no_walls:
            mno = _RE_NO_WALLS.search(text)
            mark(mno.span())
            room.walls = False
            cov.understood.append({"clause": mno.group(0), "as": "no wall shell (equipment only)"})
    m_srv = _RE_SERVICE.search(text)
    srv_voltage: Optional[str] = None
    if m_srv:
        mark(m_srv.span())
        amps = _clean_num(m_srv.group("a") or m_srv.group("a2"))
        if room is None:
            room = PromptRoom(walls=False)
            cov.warnings.append("service rating given without a room: equipment-only build")
        room.service_rating_a = amps
        cov.understood.append({"clause": m_srv.group(0), "as": "service rating", "amps": amps})
        # the service system voltage = a voltage mentioned IN the service clause
        s0, s1 = max(0, m_srv.start() - 24), min(len(text), m_srv.end() + 24)
        srv_voltage = _voltage_system_from(text[s0:s1])
        if srv_voltage:
            for vre in (_RE_VOLT_SYS, _RE_VOLT_SLASH, _RE_VOLT_PLAIN):
                vm = vre.search(text[s0:s1])
                if vm is not None:
                    mark((s0 + vm.start(), s0 + vm.end()))
                    break
            cov.understood.append({"clause": text[s0:s1].strip(), "as": "service voltage",
                                   "voltage": srv_voltage})
    # amp-less voltage rating ('rated for 250V'): the service system, with
    # RATING CLASSES (250 V / 600 V equipment classes) mapped to the system
    # they imply -- the mapping is STATED in defaults_applied, never silent.
    if srv_voltage is None:
        m_rv = _RE_RATED_VOLT.search(text)
        if m_rv:
            raw_v = int(m_rv.group("v") or m_rv.group("v2"))
            s0 = max(0, m_rv.start() - 12)
            sys_v = _voltage_system_from(text[s0:m_rv.end()])
            mapped = None
            if raw_v in RATING_CLASS_TO_SYSTEM and sys_v in (None, str(raw_v)):
                mapped = RATING_CLASS_TO_SYSTEM[raw_v]
                sys_v = mapped
            if sys_v is not None:
                mark(m_rv.span())
                srv_voltage = sys_v
                if room is None:
                    room = PromptRoom(walls=False)
                    cov.warnings.append("a voltage rating was given without a room: "
                                        "equipment-only build")
                cov.understood.append({"clause": m_rv.group(0), "as": "service voltage",
                                       "voltage": sys_v, "rated": f"{raw_v} V"})
                if mapped is not None:
                    cov.defaults_applied.append(
                        f"service voltage: {mapped} V-class system mapped from the "
                        f"prompt's '{raw_v} V' rating class (a {raw_v} V rating names "
                        "the equipment's maximum voltage class, not a system voltage)")
    #: the room noun (and its pre-word: 'switchgear room', 'transformer
    #: vault') is a place, never a piece of equipment
    room_taken: List[Tuple[int, int]] = [m_room.span()] if m_room else []

    # ------------------------------------------------------------------
    # 1b. LEVEL clauses: storey counts ('two storey') and level references
    #     ('on level 2', 'second floor') -- every occurrence, not the first.
    #     A reference is bound to the equipment clause it sits in (section
    #     2); one that sits in no equipment clause scopes the ROOM.
    # ------------------------------------------------------------------
    storey_count: Optional[int] = None
    storey_spans: List[Tuple[int, int]] = []
    for sm in _RE_STOREYS.finditer(text):
        n = _num_word(sm.group("n")) or 0
        if n <= 0:
            continue
        mark(sm.span())
        storey_spans.append(sm.span())
        storey_count = max(storey_count or 0, n)
        cov.understood.append({"clause": sm.group(0), "as": "storeys", "count": n})
    #: {"span", "text", "n" (storey number), "tags" (the equipment bound to
    #: it in section 2; empty = a ROOM-scope reference)}
    level_refs: List[Dict[str, Any]] = []
    not_a_ref = storey_spans + ([m_f2f.span()] if m_f2f else [])   # 'floor 14' in 'floor to floor 14 ft'
    for lm in _RE_LEVEL_REF.finditer(text):
        if _in_any(lm.start(), lm.end(), not_a_ref):
            continue
        raw = (lm.group("n") or lm.group("o") or lm.group("l")).lower()
        n = (0 if raw in ("top", "upper")                 # the highest storey, resolved below
             else _ORDINAL_LEVEL.get(raw) or _num_word(raw[:-2] if raw[:-2].isdigit() else raw) or 0)
        if n <= 0 and raw not in ("top", "upper"):
            continue
        mark(lm.span())
        # a reference ADJACENT to the room phrase ('electrical room on the
        # second floor', 'second floor electrical room') scopes the ROOM,
        # whatever equipment clause it also falls in
        adjacent = bool(m_room and (not text[m_room.end():lm.start()].strip(" ,")
                                    if lm.start() >= m_room.end()
                                    else not text[lm.end():m_room.start()].strip(" ,")))
        level_refs.append({"span": lm.span(), "text": lm.group(0).strip(), "n": n, "tags": [],
                           "room": adjacent})
    # storeys = max(the count, every referenced level); 'top floor' = that
    n_levels = max([storey_count or 1] + [r["n"] for r in level_refs])
    for r in level_refs:
        r["n"] = r["n"] or n_levels
    room_taken += storey_spans + [r["span"] for r in level_refs]

    # ------------------------------------------------------------------
    # 2. EQUIPMENT clauses (count + kind + attributes)
    # ------------------------------------------------------------------
    items: List[PromptItem] = []
    #: attribute window around a kind match: text between the previous
    #: comma/'and'/period and the next comma/'and'/period
    # (a decimal point inside a number -- '1.1 m', '7.5 kVA' -- is not a sentence stop)
    boundaries = [m.start() for m in re.finditer(r",|;|\band\b|\bplus\b|\bwith\b|\.(?!\d)", low)]

    def clause_window(start: int, end: int) -> Tuple[int, int]:
        lo_b = 0
        for b in boundaries:
            if b < start:
                lo_b = b
            else:
                break
        hi_b = len(text)
        for b in boundaries:
            if b >= end:
                hi_b = b
                break
        return lo_b, hi_b

    taken: List[Tuple[int, int]] = list(room_taken)

    def overlaps(a: int, b: int) -> bool:
        return any(not (b <= x or a >= y) for x, y in taken)

    # Every equipment kind the MEP taxonomy recognises in the prompt (#692).  A kind the
    # room build does NOT model is SHIELDED from the clauses below before they run, so
    # 'a fire alarm control panel' or 'a lighting relay panel' can no longer be read as a
    # panelboard by its last word; it is recorded NOT built in section 3, with the
    # taxonomy's own line.  Kinds the build models are left to their clauses.
    kind_mentions = [m for m in TX.scan(text) if not overlaps(m.start, m.end)]
    taken += [(m.start, m.end) for m in kind_mentions if m.key not in _SCENE_KIND]
    # every MAKER named (rvt.famgen.vendors); attached after the clauses are read, to the
    # nearest equipment noun in its clause -- built or not (_attach_makers below)
    maker_mentions = [m for m in VD.scan(text) if not overlaps(m.start, m.end)]
    noun_groups: List[Tuple[Tuple[int, int], List[PromptItem]]] = []   # (noun span, its items)

    counters: Dict[str, int] = {}                     # items issued per tag prefix
    used_tags: set = set()

    def issue_tag(prefix: str, explicit: Optional[str] = None) -> Tuple[str, int]:
        """(tag, ordinal) for the next ``prefix`` item: the tag the prompt
        named, else the next FREE auto-numbered one -- an explicitly named
        tag is never re-issued ('LP-2 and one more lighting panel')."""
        while True:
            counters[prefix] = counters.get(prefix, 0) + 1
            idx = counters[prefix]
            if explicit:
                tag = explicit
            elif prefix == "MSB":
                tag = "MSB" if idx == 1 else f"MSB-{idx}"
            elif prefix == "T":
                tag = f"T{idx}"
            else:
                tag = f"{prefix}-{idx}"
            if explicit or tag not in used_tags:
                used_tags.add(tag)
                return tag, idx

    #: 'X fed from Y': X and Y are tag REFERENCES by grammar, even digit-less
    fed_spans = [sp for fm in _RE_FED_FROM.finditer(text)
                 for sp in (fm.span("load"), fm.span("src"))]

    def ref_end(km: "re.Match") -> Optional[int]:
        """End offset of the tag REFERENCE a kind ABBREVIATION match is part
        of -- 'lp' + '-1' = 'LP-1', or a bare 'MSB' inside a fed-from clause
        -- or None when the match is an equipment NOUN ('two LPs')."""
        if not km.groupdict().get("abbr"):
            return None
        msuf = _RE_TAG_SUFFIX.match(low, km.end())
        if msuf is not None:
            return msuf.end()
        if any(a <= km.start() and km.end() <= b for a, b in fed_spans):
            return km.end()
        return None

    # Equipment NOUN clauses first ('two lighting panels LP-1 and LP-2',
    # 'an MDP'; they also consume the tag list that follows them), bare tag
    # REFERENCES last ('LP-1 fed from DP-1', 'LP-1 on the west wall') --
    # regardless of prompt order.  A reference to a tag a noun clause
    # already produced is just consumed; an unseen one stands for ONE item
    # carrying that tag.  So naming a tag never double-counts equipment.
    kind_matches = [(kind, prefix, km, ref_end(km)) for kind, prefix, pat in _KIND_PATTERNS
                    for km in re.finditer(pat, low)]
    kind_matches.sort(key=lambda m: m[3] is not None)      # stable: nouns, then refs
    for kind, prefix, km, rend in kind_matches:
        if overlaps(km.start(), km.end()):
            continue
        ref_tag = text[km.start():rend].upper() if rend is not None else None
        if ref_tag in used_tags:
            # a REFERENCE to equipment a noun clause already produced: consume
            taken.append((km.start(), rend))
            mark((km.start(), rend))
            continue
        ws, we = clause_window(km.start(), km.end())
        window = text[ws:we]
        # explicit TAGS: a bare reference IS its tag; a noun may be followed
        # by its tag list ('lighting panel LP-1', 'panels LP-1 and LP-2',
        # 'panel named LP-1'); else a 'named X' anywhere in the clause.
        tag_start = km.start()
        tag_toks: List[Tuple[str, int]] = []             # (TAG, end offset in text)
        if ref_tag is not None:
            tag_toks = [(ref_tag, rend)]
        else:
            mtl = _RE_TAG_LIST.match(low, km.end())
            named = _RE_NAMED.search(window) if mtl is None else None
            if mtl is not None:
                tag_start = km.end()
                tag_toks = [(tm.group(0).upper(), tm.end())
                            for tm in _RE_TAG_TOKEN.finditer(low, km.end(), mtl.end())]
            elif named is not None:
                tag_start = ws + named.start()
                tag_toks = [(named.group(1).upper(), ws + named.end())]
        fresh: List[Tuple[str, int]] = []                 # drop repeats / already-issued tags
        for t, e in tag_toks:
            if t not in used_tags and all(t != f for f, _e in fresh):
                fresh.append((t, e))
        tag_toks = fresh
        # count: the nearest number-word / digit BEFORE the noun in the
        # window, after RATING expressions ('400 A', '75 kVA', '65 kA',
        # '42-space', '480Y/277 V') are scrubbed so a unit letter ('A')
        # or a rating digit is never mistaken for a count.  An explicit
        # count WINS over the number of tags named; tags alone set the
        # count of an uncounted plural; a bare reference is ONE item.
        head = low[ws:km.start()]
        head_count = head
        for scrub in (_RE_AMP, _RE_KVA, _RE_KA, _RE_SPACES, _RE_SECTIONS,
                      _RE_VOLT_SYS, _RE_VOLT_SLASH, _RE_VOLT_PLAIN,
                      _RE_F2F, _RE_STOREYS, _RE_LEVEL_REF):
            head_count = scrub.sub(" ", head_count)
        plural = km.group(0).rstrip().endswith("s") or "pair" in head
        explicit_count = None
        for tok in ([] if ref_tag else reversed(_RE_COUNT_TOK.findall(head_count))):
            nv = _num_word(tok)
            if nv is None:
                continue
            explicit_count = nv
            break
        cnt = 1
        if explicit_count is not None:
            cnt = explicit_count
        elif tag_toks:
            cnt = len(tag_toks)
        elif plural:
            cnt = 2 if kind != "switchboard" else 1
            cov.defaults_applied.append(f"'{km.group(0)}' plural with no count: assumed {cnt}")
        if cnt <= 0:
            continue
        tag_toks = tag_toks[:cnt]
        tags = [t for t, _e in tag_toks]
        tag_span = None
        if tag_toks:
            tend = tag_toks[-1][1]
            tag_span = (tag_start, tend + (text[tend:tend + 1] in ("'", '"')))   # + closing quote
        # the item's LEVEL: a level reference inside its clause (the window,
        # extended past a tag list that ran across 'and': 'panels LP-1 and
        # LP-2 on level 2'); unreferenced items follow the room (section 4)
        region_end = clause_window(tag_span[1], tag_span[1])[1] if tag_span and tag_span[1] > we else we
        item_ref = next((ref for ref in level_refs if not ref["room"]
                         and ws <= ref["span"][0] and ref["span"][1] <= region_end), None)
        item_level = item_ref["n"] if item_ref else None
        # attributes from the clause window
        amp = _RE_AMP.search(window)
        kva = _RE_KVA.search(window)
        ka = _RE_KA.search(window)
        volt = _voltage_system_from(window)
        spaces = _RE_SPACES.search(window)
        mains = "MCB" if _RE_MCB.search(window) else ("MLO" if _RE_MLO.search(window) else None)
        mounting = ("flush" if _RE_FLUSH.search(window)
                    else ("surface" if _RE_SURFACE.search(window) else None))
        sections = _RE_SECTIONS.search(window)
        aff = _RE_AFF.search(window) if kind in _AFF_KINDS else None
        for j in range(cnt):
            tag, idx = issue_tag(prefix, tags[j] if j < len(tags) else None)
            it = PromptItem(kind=kind, tag=tag, count_index=idx, source_text=window.strip())
            if amp:
                it.rating_a = _clean_num(amp.group(1))
            if kva:
                it.kva = _clean_num(kva.group(1))
            if ka:
                it.sccr_ka = _clean_num(ka.group(1))
            if aff:
                it.height_in = round(_to_metres(_clean_num(aff.group("h")), aff.group("u"))
                                     * IN_PER_M, 2)
            it.voltage = volt
            it.mains = mains
            it.spaces = int(spaces.group(1)) if spaces else None
            it.mounting = mounting
            it.sections = int(sections.group(1)) if sections else None
            it.level = item_level            # None -> the room's level (section 4)
            items.append(it)
        if item_ref is not None:
            item_ref["tags"] += [x.tag for x in items[-cnt:]]
        # the noun AND its tag list ('panels LP-1 and LP-2 by Eaton': the maker follows the tags)
        noun_groups.append(((km.start(), max(km.end(), tag_span[1] if tag_span else 0)), items[-cnt:]))
        taken.append((km.start(), km.end()))
        mark((km.start(), km.end()))
        if tag_span is not None:
            taken.append(tag_span)
            mark(tag_span)
        for sub in (amp, kva, ka, spaces, sections, aff):
            if sub is not None:
                mark((ws + sub.start(), ws + sub.end()))
        if mains:
            mm = (_RE_MCB.search(window) or _RE_MLO.search(window))
            mark((ws + mm.start(), ws + mm.end()))
        for vm in (_RE_VOLT_SYS.search(window), _RE_VOLT_SLASH.search(window),
                   _RE_VOLT_PLAIN.search(window)):
            if vm is not None:
                mark((ws + vm.start(), ws + vm.end()))
        for nm in _RE_COUNT_WORD.finditer(head):
            if _num_word(nm.group(1)) == cnt:
                mark((ws + nm.start(), ws + nm.end()))
        cov.understood.append({
            "clause": text[km.start():km.end()], "as": "equipment", "kind": kind,
            "count": cnt, "rating_a": (items[-1].rating_a if items else None),
            "kva": (items[-1].kva if items else None), "voltage": volt,
            "mains": mains, "spaces": (items[-1].spaces if items else None),
            "tags": [it.tag for it in items[-cnt:]],
        })
        if tag_span is not None:
            cov.understood.append({
                "clause": text[tag_span[0]:tag_span[1]].strip(), "as": "equipment tag",
                "kind": kind, "tags": tags})

    # MAKERS: each one named goes to the nearest equipment noun in its clause -- a built
    # item's noun or a not-built kind ('a 500 kW Cummins generator' names the generator's
    # maker, never the panels') -- and applies to the whole job only on an explicit cue
    # ('all gear by Eaton'); a maker's name is never guessed onto equipment (steer #685)
    unbuilt_anchors = [m for m in kind_mentions if m.key not in _SCENE_KIND]
    unbuilt_makers, global_maker, loose_names = _attach_makers(
        text, maker_mentions, noun_groups, unbuilt_anchors, items, clause_window, mark, cov)
    _maker_coverage(items, global_maker, cov)

    # room service voltage: the service clause's own voltage, else a
    # switchboard's, else the default -- NEVER a branch panel's own system
    if room is not None:
        sb_v = next((it.voltage for it in items if it.kind == "switchboard" and it.voltage), None)
        room.service_voltage = srv_voltage or sb_v or DEFAULT_SERVICE_VOLTAGE
        if not (srv_voltage or sb_v):
            cov.defaults_applied.append(f"service voltage system: {DEFAULT_SERVICE_VOLTAGE} V")

    # ------------------------------------------------------------------
    # 3. recognised-but-unbuilt kinds (coverage honesty)
    # ------------------------------------------------------------------
    def built_nearby(m: TX.Mention) -> bool:
        """A scene-kind word standing in the clause that DID build that kind ('four 5-20R
        receptacles': the receptacle clause read it) is an attribute of it, not a miss."""
        lo, hi = clause_window(m.start, m.end)
        return any(lo <= span[0] and span[1] <= hi
                   and _SCENE_KIND.get(TX.for_intent_kind(its[0].kind).key) == _SCENE_KIND[m.key]
                   for span, its in noun_groups)

    found: List[Tuple[int, Dict[str, Any]]] = []
    for m in kind_mentions:
        # a shielded mention is reported; a scene-kind mention only when no clause built it
        # ('a load center': a panelboard by the taxonomy, not a phrasing the panel clause
        # reads) -- never twice for one span, never for a word of the clause that built it
        if m.key in _SCENE_KIND:
            if overlaps(m.start, m.end):
                continue
            taken.append((m.start, m.end))
            if built_nearby(m):
                mark((m.start, m.end))
                continue
        mark((m.start, m.end))
        found.append((m.start, _kind_record(m, maker=unbuilt_makers.get(m))))
    for kind, pat, why in _CONTEXT_PATTERNS:
        for um in re.finditer(pat, low):
            if overlaps(um.start(), um.end()):
                continue
            taken.append(um.span())
            mark(um.span())
            found.append((um.start(), {"text": text[um.start():um.end()], "kind": kind,
                                       "reason": f"recognised, NOT modelled: {why}"}))
    unbuilt: List[Dict[str, Any]] = [rec for _start, rec in sorted(found, key=lambda f: f[0])]
    cov.not_built.extend(unbuilt)

    # ------------------------------------------------------------------
    # 4. levels
    # ------------------------------------------------------------------
    levels = _resolve_levels(room, items, n_levels, level_refs, f2f_m, cov,
                             defaulted=storey_count is None and not level_refs)

    # ------------------------------------------------------------------
    # 5. feeders / circuits
    # ------------------------------------------------------------------
    feeders: List[Tuple[str, str]] = []
    auto_feeders = True
    m_nf = _RE_NO_FEEDERS.search(text)
    if m_nf:
        mark(m_nf.span())
        auto_feeders = False
        cov.understood.append({"clause": m_nf.group(0), "as": "no feeder tree"})
    for fm in _RE_FED_FROM.finditer(text):
        load_t, src_t = fm.group("load").upper(), fm.group("src").upper()
        known = {it.tag for it in items}
        if load_t in known and (src_t in known or src_t in ("SERVICE", "UTILITY")):
            feeders.append((src_t, load_t))
            mark(fm.span())
            cov.understood.append({"clause": fm.group(0), "as": "explicit feeder",
                                   "from": src_t, "to": load_t})

    # ------------------------------------------------------------------
    # 6. project name + ignored words
    # ------------------------------------------------------------------
    project_name = (room.name if room and room.name else "Prompt-authored model")
    if room and room.service_rating_a:
        project_name = f"{project_name} - {room.service_rating_a:g} A service"

    # residual significant words = ignored
    residual = "".join(ch if not consumed[i] else " " for i, ch in enumerate(text))
    words = [w for w in re.split(r"[^A-Za-z0-9/'.\-]+", residual) if w]
    ignored: List[str] = []
    for w in words:
        wl = w.lower().strip(".-'/")
        if not wl or wl in _STOPWORDS or wl in _NUM_WORDS:
            continue
        if re.fullmatch(r"\d+([.,]\d+)?", wl):
            continue
        if wl in ("x", "by", "ft", "feet", "foot", "m", "meters", "metres", "amps", "amp",
                  "a", "kva", "ka", "v", "volts", "volt"):
            continue
        ignored.append(w)
    cov.ignored_words = ignored
    cov.consumed_ratio = float(sum(consumed)) / max(1, len(text))

    if not items and not (room and room.width_m):
        # the recognised kind LEADS: a status line keeps its first ~160 characters (the
        # manifest's cut), and what the prompt named but this route cannot build is the news
        nothing = (f"nothing to author here: this route models {_MODELLED_PROSE}, or a room "
                   "with dimensions")
        raise PromptError(
            ("recognised, NOT built by this route: "
             + "; ".join(f"'{u['text']}' -> {u['reason']}" for u in unbuilt) + f" -- {nothing}."
             if unbuilt else
             f"the prompt names no equipment kind and no room -- {nothing}.")
            + (f" Makers named: {loose_names}." if loose_names else "")
            + " Ignored words: " + (", ".join(ignored[:12]) or "none"))

    return ParsedPrompt(prompt=text, room=room, items=items, unbuilt=unbuilt,
                        feeders=feeders, auto_feeders=auto_feeders,
                        levels=levels, coverage=cov, project_name=project_name)


# ============================================================================
# equipment attributes: normalise the tagging contract from the prompt facts
# ============================================================================

def _apply_defaults(item: PromptItem, room: Optional[PromptRoom],
                    cov: PromptCoverage) -> None:
    """Fill ratings / voltage / mains / spaces the prompt left unsaid, with
    every assumption recorded."""
    service_v = (room.service_voltage if room and room.service_voltage else DEFAULT_SERVICE_VOLTAGE)
    service_a = room.service_rating_a if room else None
    if item.kind == "switchboard":
        if item.rating_a is None:
            item.rating_a = float(service_a) if service_a else 2500.0
            cov.defaults_applied.append(f"{item.tag}: bus rating {item.rating_a:g} A "
                                        + ("(= the room's service rating)" if service_a
                                           else "(default 2500 A switchboard)"))
        if item.voltage is None:
            item.voltage = service_v
            cov.defaults_applied.append(f"{item.tag}: voltage {service_v} V (service system)")
        if item.mains is None:
            item.mains = "MCB"
            cov.defaults_applied.append(f"{item.tag}: main breaker (switchboard default)")
        if item.sccr_ka is None:
            item.sccr_ka = 65.0
            cov.defaults_applied.append(f"{item.tag}: SCCR 65 kA (typical 480 V service default; "
                                        "an ordering value, not a catalog fact)")
        if item.sections is None:
            item.sections = max(2, min(6, int(round(item.rating_a / 625.0))))
            cov.defaults_applied.append(f"{item.tag}: {item.sections} sections (lineup sizing rule "
                                        "round(A/625), clamped 2..6)")
        if item.mounting is None:
            item.mounting = "floor"
    elif item.kind == "transformer":
        if item.kva is None:
            item.kva = DEFAULT_XFMR_KVA
            cov.defaults_applied.append(f"{item.tag}: {DEFAULT_XFMR_KVA:g} kVA (no rating given)")
        if item.voltage is None:
            item.voltage = "480-208Y/120"
            cov.defaults_applied.append(f"{item.tag}: 480 V delta primary -> 208Y/120 V secondary "
                                        "(the standard step-down)")
        item.mounting = item.mounting or "floor"
    elif item.kind == "receptacle_device":
        # a 120 V 1-pole duplex receptacle; the placement height comes from
        # OUR device facts (18 in AFF convention inside the ADA 15..48 in
        # reach envelope) unless the prompt said 'at N in AFF'
        first = item.count_index == 1          # one coverage line per clause, not per device
        if item.voltage is None:
            item.voltage = DEFAULT_DEVICE_VOLTAGE
            if first:
                cov.defaults_applied.append(f"{item.tag} (and its siblings): {DEFAULT_DEVICE_VOLTAGE} V "
                                            f"1-pole receptacle ({DEFAULT_DEVICE_VA:g} VA booked, "
                                            "NEC 220.14(I) unit load)")
        else:
            item.voltage = _device_voltage(item)     # a system voltage -> the 1-pole L-N value
        if item.height_in is None:
            item.height_in, why = _device_height_default()
            if first:
                cov.defaults_applied.append(f"{item.tag} (and its siblings): mounted "
                                            f"{item.height_in:g} in AFF ({why})")
        item.mounting = item.mounting or "wall"
    else:  # panelboards
        if item.rating_a is None:
            item.rating_a = {"distribution_panelboard": 400.0, "lighting_panelboard": 100.0,
                             "receptacle_panelboard": 225.0}.get(item.kind, 225.0)
            cov.defaults_applied.append(f"{item.tag}: {item.rating_a:g} A bus (kind default)")
        if item.voltage is None:
            item.voltage = ("208Y/120" if item.kind == "receptacle_panelboard" else service_v)
            cov.defaults_applied.append(f"{item.tag}: voltage {item.voltage} V "
                                        + ("(receptacle/appliance default)"
                                           if item.kind == "receptacle_panelboard"
                                           else "(service system)"))
        if item.mains is None:
            item.mains = "MCB" if item.kind == "distribution_panelboard" else "MLO"
            cov.defaults_applied.append(f"{item.tag}: {item.mains} "
                                        f"({'main breaker' if item.mains == 'MCB' else 'main lugs only'}"
                                        " kind default)")
        if item.spaces is None:
            item.spaces = DEFAULT_PANEL_SPACES
            cov.defaults_applied.append(f"{item.tag}: {DEFAULT_PANEL_SPACES} spaces (default)")
        if item.mounting is None:
            item.mounting = "surface"


def _contract_for(item: PromptItem) -> Dict[str, Any]:
    """The tagging-contract dict (the SAME join key the IFC route yields),
    built through :func:`rvt.ifc.intent.normalize_contract` over synthetic
    schedule Psets so both routes normalise identically."""
    psets: Dict[str, Dict[str, Any]] = {}
    v = item.voltage or DEFAULT_SERVICE_VOLTAGE
    if item.kind == "transformer":
        pri, sec = _split_xfmr_voltage(item.voltage)
        psets["TransformerSchedule"] = {
            "PanelName": item.tag, "RatingkVA": float(item.kva or DEFAULT_XFMR_KVA),
            "Primary": pri, "Secondary": sec, "TemperatureRise": "150 C",
        }
        if item.fed_from:
            psets["TransformerSchedule"]["FedFrom"] = item.fed_from
    elif item.kind == "switchboard":
        psets["SwitchboardSchedule"] = {
            "PanelName": item.tag, "Voltage": f"{v} V", "Phases": 3, "Wires": 4,
            "BusRating": float(item.rating_a or 2500.0),
            "MainsRating": float(item.rating_a or 2500.0),
            "MainDevice": (f"{(item.rating_a or 2500):g} A main breaker"
                           if (item.mains or "MCB") == "MCB" else "Main lugs only"),
            "ShortCircuitRatingkA": float(item.sccr_ka or 65.0),
            "Sections": int(item.sections or 4),
            "Mounting": ("Floor, on housekeeping pad" if (item.mounting or "floor") == "floor"
                         else str(item.mounting)),
            "FeederEntry": "Top",
        }
        if item.fed_from:
            psets["SwitchboardSchedule"]["FedFrom"] = item.fed_from
    elif item.kind == "receptacle_device":
        psets[DEVICE_PSET] = {
            "PanelName": item.tag, "Voltage": f"{v} V", "Phases": 1, "Wires": 2,
            "Load": float(DEFAULT_DEVICE_VA), "MountingHeight": float(item.height_in),
            "Mounting": f"Wall, {item.height_in:g} in AFF to the box centre",
            "DeviceType": _device_label(),
        }
        if item.fed_from:
            psets[DEVICE_PSET]["FedFrom"] = item.fed_from
    else:  # panelboards
        psets["PanelSchedule"] = {
            "PanelName": item.tag, "Voltage": f"{v} V", "Phases": 3, "Wires": 4,
            "BusRating": float(item.rating_a or 225.0),
            "MainsRating": float(item.rating_a or 225.0),
            "MainsType": ("Main breaker" if (item.mains or "MLO") == "MCB" else "Main lugs only"),
            "NumberOfCircuits": int(item.spaces or DEFAULT_PANEL_SPACES),
            "Mounting": ("Flush" if item.mounting == "flush" else "Surface, wall"),
            "FeederEntry": "Top",
        }
        if item.sccr_ka is not None:
            psets["PanelSchedule"]["ShortCircuitRatingkA"] = float(item.sccr_ka)
        if item.fed_from:
            psets["PanelSchedule"]["FedFrom"] = item.fed_from
    if item.manufacturer:                # DECLARED identity, exactly as the IFC route reads it
        psets["Pset_ManufacturerTypeInformation"] = {"Manufacturer": item.manufacturer}
    con = I.normalize_contract(psets, name=item.name or item.tag, object_type=None,
                               description=item.source_text or None, tag=item.tag)
    con["_prompt_psets"] = psets
    return con


def _split_xfmr_voltage(v: Optional[str]) -> Tuple[str, str]:
    """'480-208Y/120' / '480Y/277' -> (primary, secondary) strings."""
    s = str(v or "480-208Y/120")
    if "-" in s and "Y/" in s.split("-", 1)[-1]:
        pri, sec = s.split("-", 1)
        return f"{pri.strip()} V delta", f"{sec.strip()} V"
    if s.startswith("208"):
        return "480 V delta", f"{s} V"
    return "480 V delta", "208Y/120 V"


# ============================================================================
# THE DETERMINISTIC ROOM LAYOUT
# ============================================================================

def layout_room(parsed: ParsedPrompt) -> None:
    """Assign world positions / orientation / mounting to every buildable
    item by the room-layout rule:

    * ROOM: width (E-W, x) x depth (N-S, y) centred at the origin; a
      counter-clockwise centerline wall ring.
    * FLOOR GEAR (switchboards, then transformers): a lineup along the NORTH
      wall interior, fronts facing SOUTH (into the room), standing on a
      100 mm housekeeping pad.
    * WALL GEAR (panelboards): surface-mounted on the WEST and EAST wall
      interior faces, distribution panels nearest the north, then lighting /
      receptacle panels southward, alternating W/E; enclosure centre at
      1.42 m AFF; the upright work-plane frame faces INTO the room.
    * NO ROOM: everything free-standing in a row along +X at y = 0.
    All numbers land in metres in the intent; the manifest records the rule.
    """
    room = parsed.room
    items = parsed.buildable_items
    cov = parsed.coverage
    for it in items:
        _apply_defaults(it, room, cov)
    # dims (metres): prompt defaults now; catalog facts overwrite after planning
    for it in items:
        it.dims_m, it.dims_source = _default_dims(it)

    floor_items = [it for it in items if it.kind in ("switchboard", "transformer")]
    wall_items = [it for it in items if it.kind not in ("switchboard", "transformer")]
    have_room = bool(room and room.walls and room.width_m > 0 and room.depth_m > 0)

    if not have_room:
        # equipment-only: a free-standing lineup along +X
        cov.defaults_applied.append("no room shell: equipment laid out in a row along +X "
                                    "(free-standing; wall panels stand upright facing -Y)")
        x = 0.0
        for it in floor_items + wall_items:
            w = float(it.dims_m.get("w", 1.0))
            it.insertion_m = [round(x + w / 2.0, 4), 0.0,
                              DEFAULT_PAD_M if it.kind in ("switchboard", "transformer")
                              else _wall_mount_z(it)]
            it.front = [0.0, -1.0, 0.0]
            if it.kind in ("switchboard", "transformer"):
                it.frame_kind, it.mount_kind, it.yaw_deg = "yaw", "floor", 0.0
            else:
                it.frame_kind, it.mount_kind, it.yaw_deg = "upright", "surface", 0.0
            x += w + 0.9
        return

    W, D, T = room.width_m, room.depth_m, room.wall_thickness_m
    hw_in = W / 2.0 - T / 2.0          # interior face x extent
    hd_in = D / 2.0 - T / 2.0          # interior face y extent
    # the same rule runs once PER STOREY (each level's lineup / panel rows
    # start afresh; z stays relative to the item's own level)
    for lvl in sorted({it.level for it in items}):
        _layout_storey([it for it in floor_items if it.level == lvl],
                       [it for it in wall_items if it.level == lvl], hw_in, hd_in, lvl, cov)


def _layout_storey(floor_items: List[PromptItem], wall_items: List[PromptItem],
                   hw_in: float, hd_in: float, lvl: int, cov: PromptCoverage) -> None:
    """One storey of :func:`layout_room`: the floor lineup along the north
    wall interior + the wall panels on the west / east interior faces."""
    # ---- floor lineup along the north wall interior ----------------------
    if floor_items:
        back_gap = 0.10
        gap = 0.30
        total = sum(float(it.dims_m.get("w", 1.0)) for it in floor_items) \
            + gap * (len(floor_items) - 1)
        avail = 2 * hw_in - 0.6
        if total > avail:
            cov.warnings.append(f"floor lineup ({total:.2f} m, Level {lvl}) is wider than the "
                                f"north wall interior ({avail:.2f} m): items overrun -- widen "
                                "the room")
        x = -total / 2.0
        for it in floor_items:
            w = float(it.dims_m.get("w", 1.0))
            d = float(it.dims_m.get("d", 0.6))
            it.insertion_m = [round(x + w / 2.0, 4),
                              round(hd_in - back_gap - d / 2.0, 4),
                              DEFAULT_PAD_M]
            it.front = [0.0, -1.0, 0.0]                 # facing south, into the room
            it.frame_kind, it.mount_kind, it.yaw_deg = "yaw", "floor", 0.0
            x += w + gap
    # ---- wall panels on the west / east interior faces ---------------------
    if wall_items:
        pitch = 0.30
        west: List[PromptItem] = []
        east: List[PromptItem] = []
        # distribution panels first, then lighting, receptacle, generic
        # panels, and the wiring devices last (same faces, their own height)
        order = {"distribution_panelboard": 0, "panelboard": 1,
                 "lighting_panelboard": 2, "receptacle_panelboard": 3, "receptacle_device": 5}
        wall_sorted = sorted(wall_items, key=lambda it: (order.get(it.kind, 9), it.count_index))
        for k, it in enumerate(wall_sorted):
            (west if k % 2 == 0 else east).append(it)
        for side, group, x_face, front in (("W-W", west, -hw_in, [1.0, 0.0, 0.0]),
                                          ("W-E", east, +hw_in, [-1.0, 0.0, 0.0])):
            y = hd_in - 0.60                              # start near the north end
            for it in group:
                w = float(it.dims_m.get("w", 0.508))
                y -= w / 2.0
                it.insertion_m = [round(x_face, 4), round(y, 4), _wall_mount_z(it)]
                it.front = list(front)
                it.frame_kind, it.mount_kind, it.yaw_deg = "upright", "surface", 0.0
                it.wall_id = side
                y -= w / 2.0 + pitch
                if y < -hd_in + 0.3:
                    cov.warnings.append(f"the {side} wall is full on Level {lvl}: {it.tag} "
                                        "overruns the south corner -- widen/deepen the room "
                                        "or reduce the panel count")


def _wall_mount_z(item: PromptItem) -> float:
    """Height above ITS floor of a wall item's insertion (the centre of its
    mounting plane): the panel enclosure centre, or a device's AFF height."""
    if item.kind == "receptacle_device":
        return round(float(item.height_in) / IN_PER_M, 4)
    return DEFAULT_PANEL_MOUNT_CENTER_M


def _default_dims(item: PromptItem) -> Tuple[Dict[str, float], str]:
    """Prompt-default dims (metres) -- REPLACED by catalog facts for every
    plan the facts resolver accepts (see :func:`prompt_to_intent`)."""
    if item.kind == "switchboard":
        sections = int(item.sections or 4)
        w = round(0.9 * sections + 0.3, 3)              # ~0.9 m per section + end trim
        return ({"w": w, "d": 0.9144, "h": 2.286}, "prompt-default (typical front-accessible "
                "lineup extents from the section count; NOT manufacturer data)")
    if item.kind == "transformer":
        try:  # OUR facts store first (a catalog fact when the kVA has a record)
            from ..famgen import factory as F
            sheet = F.resolve_transformer_facts(float(item.kva or DEFAULT_XFMR_KVA), vendor="eaton")
            return ({"w": float(sheet.get("width_in")) / IN_PER_M,
                     "d": float(sheet.get("depth_in")) / IN_PER_M,
                     "h": float(sheet.get("height_in")) / IN_PER_M},
                    f"catalog fact ({sheet.catalog} {sheet.variant})")
        except Exception:
            return ({"w": 0.9, "d": 0.75, "h": 1.14}, "prompt-default (generic dry-type footprint)")
    if item.kind == "receptacle_device":
        sheet = _device_facts()                        # no dimension depends on the height
        if sheet is None:
            return dict(_DEF_DEVICE_DIMS), "prompt-default (device facts store unavailable)"
        return ({"w": float(sheet.get("plate_width_in")) / IN_PER_M,
                 "d": float(sheet.get("box_depth_in") + sheet.get("plate_thickness_in")) / IN_PER_M,
                 "h": float(sheet.get("plate_height_in")) / IN_PER_M},
                f"OUR device envelope ({sheet.catalog} {sheet.variant}: faceplate w x h, box "
                "depth + plate; every figure 'assumed' on the record)")
    if item.kind in ("lighting_panelboard", "receptacle_panelboard"):
        return dict(_DEF_LP_DIMS), "prompt-default (replaced by catalog facts once planned)"
    return dict(_DEF_PANEL_DIMS), "prompt-default (replaced by catalog facts once planned)"


# ============================================================================
# INTENT MODEL construction (the SAME model the IFC route resolves)
# ============================================================================

def _upright_frame(front: Sequence[float]) -> List[List[float]]:
    # numpy-free (perf-coldstart): 3-vector normalise + cross of fy=[0,0,1]
    # with an in-plane fz -- identical arithmetic to the old np version
    fx0, fy0 = float(front[0]), float(front[1])
    n = math.hypot(fx0, fy0) or 1.0
    fz = [fx0 / n, fy0 / n, 0.0]
    fy = [0.0, 0.0, 1.0]
    fx = [fy[1] * fz[2] - fy[2] * fz[1],
          fy[2] * fz[0] - fy[0] * fz[2],
          fy[0] * fz[1] - fy[1] * fz[0]]
    return [list(map(float, fx)), list(map(float, fy)), list(map(float, fz))]


def _yaw_frame(front: Sequence[float]) -> Tuple[List[List[float]], float]:
    nx, ny = float(front[0]), float(front[1])
    nn = math.hypot(nx, ny) or 1.0
    nx, ny = nx / nn, ny / nn
    fx = [-ny, nx, 0.0]
    fy = [-nx, -ny, 0.0]
    fz = [0.0, 0.0, 1.0]
    yaw = math.degrees(math.atan2(fx[1], fx[0]))
    return [fx, fy, fz], yaw


def _default_feeders(parsed: ParsedPrompt, equipment: List[I.Equipment]) -> List[I.FeederEdge]:
    """The prompt feeder tree: explicit 'fed from' edges + the automatic
    tree (switchboard -> distribution panels + transformer primaries;
    transformer secondary -> the <=240 V panels; no switchboard -> the first
    distribution panel is the root, fed by the SERVICE)."""
    by_tag = {e.tag: e for e in equipment}
    edges: Dict[Tuple[str, str], I.FeederEdge] = {}
    for src, tgt in parsed.feeders:
        edges[(src, tgt)] = I.FeederEdge(source=src, target=tgt, from_pset=False,
                                          notes=["explicit 'fed from' in the prompt"])
    if not parsed.auto_feeders:
        return list(edges.values())
    fed = {t for (_s, t) in edges}
    boards = [e for e in equipment if e.kind == "switchboard"]
    dps = [e for e in equipment if e.kind == "distribution_panelboard"]
    xfmrs = [e for e in equipment if e.kind == "transformer"]
    lows = [e for e in equipment if e.kind in ("lighting_panelboard", "receptacle_panelboard",
                                                "panelboard")]
    low_v = [e for e in lows if (e.contract.get("_voltage") or {}).get("ll", 480) <= 240]
    high_v = [e for e in lows if e not in low_v]
    root = boards[0] if boards else (dps[0] if dps else None)

    def add(src: I.Equipment, tgt: I.Equipment, kind: str = "feeder") -> None:
        if tgt.tag in fed or tgt.tag == src.tag:
            return
        con = tgt.contract
        ed = I.FeederEdge(source=src.tag, target=tgt.tag, kind=kind, from_pset=False)
        ed.rating_a = con.get("MainsRating") or con.get("BusRating")
        ed.voltage = con.get("Voltage") or (con.get("_voltage") or {}).get("system")
        ed.poles = int(con.get("Phases") or 3)
        ed.notes.append("prompt feeder tree (automatic): switchboard feeds distribution "
                        "panels + transformer primaries; a transformer's secondary feeds the "
                        "<=240 V panels; higher-voltage lighting panels ride on the "
                        "switchboard / first distribution panel")
        edges[(src.tag, tgt.tag)] = ed
        fed.add(tgt.tag)

    if root is not None:
        for dp in dps:
            add(root, dp)
        for x in xfmrs:
            add(root, x, kind="primary")
        # higher-voltage branch panels ride round-robin on the distribution
        # panels (or on the root when there are none / the root IS the DP)
        carriers = [d for d in dps if d is not root] or [root]
        for i, lp in enumerate(high_v):
            add(carriers[i % len(carriers)], lp)
    # transformer secondaries feed the low-voltage panels (round-robin)
    if xfmrs:
        for i, lp in enumerate(low_v):
            add(xfmrs[i % len(xfmrs)], lp, kind="secondary")
    # low-voltage panels with no transformer: hang them off the root anyway
    if root is not None:
        for lp in low_v:
            add(root, lp)
    # the service edge (external source; no in-model circuit)
    if root is not None and not any(t == root.tag for (_s, t) in edges):
        edges[("SERVICE", root.tag)] = I.FeederEdge(
            source="UTILITY", target=root.tag, kind="service", from_pset=False,
            notes=["utility service entrance (external source; no in-model circuit -- "
                   "the switchboard's own supply connector stays unconnected)"])
    return list(edges.values())


def prompt_to_intent(prompt: str) -> Tuple[I.IntentModel, ParsedPrompt]:
    """THE BUILT-IN FALLBACK: prompt -> the SAME :class:`IntentModel` the
    ``--ifc`` route resolves (equipment with tagging-contract dicts, a room
    shell with a closed CCW wall ring, a feeder tree, and the family mapping
    over OUR generated content via :func:`rvt.ifc.intent.plan_families`).

    Deterministic; no external model call; no API key.  Returns
    ``(model, parsed)`` -- ``parsed.coverage`` states what was understood /
    ignored / defaulted / recognised-but-unbuilt.
    """
    parsed = parse_prompt(prompt)
    layout_room(parsed)
    room_pr = parsed.room
    #: storey number -> its datum's world elevation (m)
    level_z = {i + 1: float(lv.get("elevation") or 0.0) for i, lv in enumerate(parsed.levels)}
    room_z = level_z.get(room_pr.level, 0.0) if room_pr is not None else 0.0

    # ---- equipment -> rvt.ifc.intent.Equipment ---------------------------
    equipment: List[I.Equipment] = []
    for k, it in enumerate(parsed.buildable_items):
        con = _contract_for(it)
        plc = I.Placement(I.identity_matrix(), [],
                          ["prompt-authored: no IFC placement chain"])
        geom = I.ProductGeometry(items=[])
        cls = {"switchboard": "IfcElectricDistributionBoard", "transformer": "IfcTransformer",
               "receptacle_device": DEVICE_IFC[0]}.get(it.kind, "IfcElectricDistributionBoard")
        pdt = {"switchboard": "SWITCHBOARD", "transformer": "VOLTAGE",
               "receptacle_device": DEVICE_IFC[1]}.get(it.kind, "DISTRIBUTIONBOARD")
        if it.kind in ("switchboard", "transformer"):
            desc = "floor-mounted lineup on a housekeeping pad"
        elif it.kind == "receptacle_device":
            desc = f"wall-mounted wiring device at {it.height_in:g} in AFF"
        else:
            desc = "surface wall-mounted panelboard"
        eq = I.Equipment(
            step_id=-(k + 1), guid=f"prompt:{it.tag}", ifc_class=cls, predefined_type=pdt,
            name=(f"{it.tag} - " + _describe_item(it)), tag=it.tag,
            description=f"{_describe_item(it)}; {desc} (front-door prompt layout)",
            object_type=None, type_name=None, kind=it.kind, psets=con.pop("_prompt_psets"),
            contract=con, placement=plc, geometry=geom)
        # the layout's z is above ITS floor; the intent model carries WORLD z
        # (rvt.ifc.intent.level_elevation contract) + the level annotation
        eq.level = f"L{it.level or 1}"
        z_world = float(it.insertion_m[2]) + level_z.get(it.level or 1, 0.0)
        eq.insertion_m = [float(it.insertion_m[0]), float(it.insertion_m[1]), z_world]
        eq.front_normal = [float(it.front[0]), float(it.front[1]), 0.0]
        eq.dims_m = dict(it.dims_m)
        eq.elevation_m = z_world if it.frame_kind == "yaw" else (
            z_world - float(it.dims_m.get("h", 1.2)) / 2.0)
        if it.frame_kind == "upright":
            eq.frame3x3 = _upright_frame(eq.front_normal)
            fx = eq.frame3x3[0]
            eq.yaw_deg = math.degrees(math.atan2(fx[1], fx[0]))
            eq.mounting = "surface"
            eq.mounting_height_m = z_world
            eq.notes.append("insertion = centre of the enclosure's mounting (back) plane on the "
                            f"{it.wall_id or 'nearest'} wall; upright work-plane frame "
                            "(family +Z = front normal, +Y = up)")
        else:
            eq.frame3x3, eq.yaw_deg = _yaw_frame(eq.front_normal)
            eq.mounting = "floor"
            eq.notes.append("insertion = footprint centre at the base of the body (on a "
                            f"{DEFAULT_PAD_M} m housekeeping pad); yaw frame, front = family -Y")
        eq.frame_kind = it.frame_kind
        eq.position_source = ("prompt-layout (deterministic room-layout rule; positions are "
                              "authored from the prompt, not surveyed)")
        eq.notes.append(f"dims {it.dims_source}")
        eq.fed_from = con.get("FedFrom") or it.fed_from
        eq.disposition = "generated-family"
        equipment.append(eq)

    # ---- room shell ---------------------------------------------------------
    room: Optional[I.RoomShell] = None
    if room_pr is not None and room_pr.walls and room_pr.width_m > 0 and room_pr.depth_m > 0:
        walls = []
        for wid, p0, p1 in _wall_ring(room_pr.width_m, room_pr.depth_m):
            walls.append(I.WallRun(
                wall_id=wid, p0_m=[float(p0[0]), float(p0[1])],
                p1_m=[float(p1[0]), float(p1[1])],
                thickness_m=float(room_pr.wall_thickness_m),
                height_m=float(room_pr.height_m), base_m=room_z, synthesized=False,
                reason=("authored from the prompt's room dimensions (deterministic layout: "
                        "closed counter-clockwise centerline ring centred at the origin, "
                        "interior on the left of every wall's drawing direction)"),
                derived_from=[f"prompt: {room_pr.source_text.strip()}"] if room_pr.source_text.strip()
                else ["prompt room dimensions"]))
        room = I.RoomShell(name=room_pr.name or "Electrical Room", step_id=None, walls=walls,
                           level=f"L{room_pr.level}")
        hw, hd = room_pr.width_m / 2.0, room_pr.depth_m / 2.0
        room.clear = {"clearWidth_m": room_pr.width_m - room_pr.wall_thickness_m,
                      "clearDepth_m": room_pr.depth_m - room_pr.wall_thickness_m,
                      "clearHeight_m": room_pr.height_m, "wall_height_m": room_pr.height_m,
                      "base_m": room_z, "ring_ccw": True,
                      "centerline_extents_m": {"x": [-hw, hw], "y": [-hd, hd]}}
        room.info = {"RoomName": room_pr.name, "ClearWidth": room_pr.width_m,
                     "ClearDepth": room_pr.depth_m, "ClearHeight": room_pr.height_m,
                     "ServiceRatingA": room_pr.service_rating_a,
                     "ServiceVoltage": room_pr.service_voltage}
        room.notes.append("prompt-authored room shell: door openings, floor slab and "
                          "housekeeping pads are NOT authored from a prompt (hosting / floor "
                          f"streams); the walls sit on Level {room_pr.level} (one shell on the "
                          "room's level; per-storey shells are a follow-up)")
    elif parsed.coverage:
        parsed.coverage.defaults_applied.append("no wall shell built (no room dimensions or "
                                                "'equipment only')")

    # ---- family mapping (the SAME resolver the IFC route uses) --------------
    plans = I.plan_families(equipment)
    # catalog facts REPLACE the prompt-default dims wherever a plan resolved
    for eq, pl in zip(equipment, plans):
        if pl.status == "resolved" and pl.dims_catalog_m:
            for ax in ("w", "d", "h"):
                if pl.dims_catalog_m.get(ax) is not None:
                    eq.dims_m[ax] = float(pl.dims_catalog_m[ax])
            eq.notes.append(f"dims replaced by catalog facts ({pl.catalog} {pl.variant})")

    # ---- feeder tree ---------------------------------------------------------
    feeders = _default_feeders(parsed, equipment)
    for ed in feeders:
        if ed.kind == "primary":
            tgt = next((e for e in equipment if e.tag == ed.target), None)
            if tgt is not None and tgt.contract.get("RatingkVA"):
                kva = float(tgt.contract["RatingkVA"])
                vp = float((I.parse_voltage(tgt.contract.get("Primary")) or {}).get("ll") or 480.0)
                ed.rating_a = round(kva * 1000.0 / (math.sqrt(3) * vp), 1)
                ed.voltage = str(tgt.contract.get("Primary") or ed.voltage)
                ed.notes.append(f"feeder ampacity from kVA: {kva:g} kVA / (sqrt3 x {vp:g} V) "
                                f"= {ed.rating_a} A (FLA; the OCPD is 125% NEC 450 -- calc follow-up)")

    # ---- audit -----------------------------------------------------------------
    audit: Dict[str, Any] = {
        "source": "prompt (built-in rules-first fallback; no external model call)",
        "equipment_with_positions": len(equipment),
        "positions_all_zero": (all(abs(e.insertion_m[0]) < 1e-9 and abs(e.insertion_m[1]) < 1e-9
                                   for e in equipment) if equipment else None),
        "feeder_edges": len(feeders),
        "family_plans": {p.tag: p.status for p in plans},
        "prompt_consumed_ratio": round(parsed.coverage.consumed_ratio, 3),
        "prompt_ignored_words": list(parsed.coverage.ignored_words),
    }
    if room is not None and room.clear.get("centerline_extents_m"):
        ext = room.clear["centerline_extents_m"]
        inside = sum(1 for e in equipment
                     if ext["x"][0] - 0.05 <= e.insertion_m[0] <= ext["x"][1] + 0.05
                     and ext["y"][0] - 0.05 <= e.insertion_m[1] <= ext["y"][1] + 0.05)
        audit["equipment_inside_room_ring"] = f"{inside}/{len(equipment)}"

    model = I.IntentModel(
        source_path=f"prompt:{parsed.prompt}", schema="prompt/spec-v2",
        project_name=parsed.project_name, length_scale_m=1.0,
        levels=[dict(l, elevation_from_placement=l.get("elevation", 0.0), step_id=None, guid=None)
                for l in parsed.levels],
        equipment=equipment,
        other_products=[{"kind": u["kind"], "name": u["text"], "disposition": u["reason"],
                         **({"revit_category": u["revit_category"]}
                            if u.get("revit_category") else {})}
                        for u in parsed.unbuilt],
        room=room, clearances=[], feeders=feeders, conduit_runs=[],
        family_plans=plans, audit=audit)
    model.notes += [
        "positions are AUTHORED BY THE PROMPT LAYOUT RULE (not surveyed from geometry): "
        "room centred at the origin; floor gear in a lineup along the north wall facing "
        "into the room; wall panels surface-mounted on the west/east interior faces",
        "the tagging-contract dict per board is synthesised from the prompt through the "
        "SAME normalize_contract() the IFC route uses, so the family mapping "
        "(plan_families) is identical for both routes",
        "PRIMARY prompt path = the documented three-d-stage handoff (PROMPT_TO_IFC.md): "
        "an AI surface builds the Three.js scene, exports IFC4 with our tagging-contract "
        "Psets, and the file re-enters through --ifc; this fallback exists so the front "
        "door WORKS with no external model call and no API key",
    ]
    return model, parsed


def _describe_item(it: PromptItem) -> str:
    if it.kind == "switchboard":
        return (f"{(it.rating_a or 2500):g} A {it.voltage or DEFAULT_SERVICE_VOLTAGE} V "
                f"{'main breaker' if (it.mains or 'MCB') == 'MCB' else 'main lugs'} switchboard, "
                f"{it.sections or 4}-section")
    if it.kind == "transformer":
        pri, sec = _split_xfmr_voltage(it.voltage)
        return f"{(it.kva or DEFAULT_XFMR_KVA):g} kVA dry-type transformer, {pri} -> {sec}"
    if it.kind == "receptacle_device":
        return (f"{it.voltage} V {_device_label()}, {DEFAULT_DEVICE_VA:g} VA, "
                f"{it.height_in:g} in AFF")
    role = {"distribution_panelboard": "distribution panelboard",
            "lighting_panelboard": "lighting panelboard",
            "receptacle_panelboard": "receptacle/appliance panelboard",
            "panelboard": "panelboard"}.get(it.kind, it.kind)
    return (f"{(it.rating_a or 225):g} A {it.voltage or DEFAULT_SERVICE_VOLTAGE} V "
            f"{'MB' if (it.mains or 'MLO') == 'MCB' else 'MLO'} {role}, "
            f"{it.spaces or DEFAULT_PANEL_SPACES} spaces")


# ============================================================================
# (a) THE PRIMARY PATH: the scene brief + handoff instructions
# ============================================================================

def handoff_instructions_path() -> str:
    """Path of the shipped PROMPT_TO_IFC.md (the IFC-authoring instructions
    any AI surface follows)."""
    return PROMPT_TO_IFC_MD


def scene_brief(prompt: str, *, parsed: Optional[ParsedPrompt] = None,
                model: Optional[I.IntentModel] = None,
                project_slug: Optional[str] = None) -> Dict[str, Any]:
    """The compact SCENE BRIEF an AI surface executes with Three.js.

    It is the resolved intent expressed in the exporter's own terms: the
    ``stage.ifcMeta`` object, one tagged product per equipment item (its
    ``userData.ifc`` block with class / predefinedType / tag / typeName /
    the schedule Psets = OUR TAGGING CONTRACT), the room shell (walls to
    model as tall thin boxes named ``wall_<id>``), and the feeder tree
    (``FedFrom``).  Feed the exported ``.ifc`` back through
    ``frontdoor author --ifc``.
    """
    if parsed is None or model is None:
        model, parsed = prompt_to_intent(prompt)
    slug = project_slug or re.sub(r"[^a-z0-9]+", "-", parsed.project_name.lower()).strip("-") or "prompt-job"
    room = parsed.room
    storey_of = {str(lv.get("id") or f"L{i + 1}"): {"name": lv.get("name") or f"Level {i + 1}",
                                                    "elevation": float(lv.get("elevation") or 0.0)}
                 for i, lv in enumerate(model.levels or [])}
    storeys = list(storey_of.values()) or [{"name": "Level 1", "elevation": 0.0}]
    fed_by = {ed.target: ed.source for ed in model.feeders if ed.kind != "service"}

    products = []
    for eq in model.equipment:
        con = {k: v for k, v in eq.contract.items()
               if not k.startswith("_") and v not in (None, "")}
        pset_name = ("TransformerSchedule" if eq.kind == "transformer"
                     else "SwitchboardSchedule" if eq.kind == "switchboard"
                     else DEVICE_PSET if eq.kind == "receptacle_device"
                     else "PanelSchedule")
        typed = {}
        for k, v in con.items():
            if k in ("Voltage",) and isinstance(v, str):
                mv = re.search(r"(\d{3})", v)
                typed[k] = {"value": int(mv.group(1)) if mv else v, "type": "voltage"}
            elif k in ("BusRating", "MainsRating"):
                typed[k] = {"value": float(v), "type": "current"}
            elif k in ("NumberOfCircuits", "Sections"):
                typed[k] = {"value": int(v), "type": "count"}
            elif k in ("Phases", "Wires"):
                typed[k] = {"value": int(v), "type": "integer"}
            elif k in ("ShortCircuitRatingkA", "RatingkVA", "ImpedancePercent"):
                typed[k] = {"value": float(v), "type": "real"}
            else:
                typed[k] = str(v)
        if eq.kind == "transformer":
            for k in ("RatingkVA", "Primary", "Secondary"):
                if k in eq.contract and k not in typed:
                    v = eq.contract[k]
                    typed[k] = {"value": float(v), "type": "real"} if k == "RatingkVA" else str(v)
        elif eq.kind == "receptacle_device":
            dev = (eq.psets or {}).get(DEVICE_PSET) or {}
            for k, ty in (("Load", "real"), ("MountingHeight", "real"), ("DeviceType", None)):
                if k in dev and k not in typed:
                    typed[k] = {"value": float(dev[k]), "type": ty} if ty else str(dev[k])
        if eq.tag in fed_by:
            typed["FedFrom"] = fed_by[eq.tag]
        pos = [round(float(x), 4) for x in eq.insertion_m]
        storey = storey_of.get(eq.level or "", storeys[0])
        products.append({
            "group_name": f"{_group_prefix(eq.kind)}_{eq.tag}",
            "tag": eq.tag, "kind": eq.kind,
            "position_m": {"x": pos[0], "y": pos[1], "z": pos[2],
                           "note": ("world coordinates (z includes the storey's elevation); "
                                    "Three.js is Y-up: place the group at (x, z, -y) if your "
                                    "stage maps IFC(x,y,z) -> THREE(x,z,-y) [the three-d-stage "
                                    "convention]; the exporter writes real IfcLocalPlacements "
                                    "from group positions")},
            "front_normal": [round(float(x), 3) for x in eq.front_normal[:2]],
            "yaw_deg": round(float(eq.yaw_deg), 2),
            "mounting": eq.mounting,
            "dims_m": {k: round(float(v), 4) for k, v in eq.dims_m.items() if k in ("w", "d", "h")},
            "storey": storey["name"],
            "userData_ifc": {
                "ifcClass": eq.ifc_class.upper(),
                "predefinedType": eq.predefined_type or "NOTDEFINED",
                "name": eq.tag, "tag": eq.tag, "storey": storey["name"],
                "typeName": _type_name_for(eq),
                "psets": [{"name": pset_name, "props": typed}],
                "typePsets": [{"name": "Pset_ManufacturerTypeInformation",
                               "props": {"Manufacturer": str(eq.contract.get("Manufacturer") or "unspecified"),
                                         "ModelLabel": _type_name_for(eq)}}],
            },
        })
    walls_brief = []
    if model.room:
        for w in model.room.walls:
            walls_brief.append({
                "group_name": f"wall_{w.wall_id.lower().replace('w-', '')}",
                "id": w.wall_id, "start_m": [round(x, 4) for x in w.p0_m],
                "end_m": [round(x, 4) for x in w.p1_m],
                "thickness_m": round(w.thickness_m, 4), "height_m": round(w.height_m, 4),
                "base_m": round(float(w.base_m or 0.0), 4),
                "how": "a THREE.BoxGeometry(length, height, thickness) centred on the "
                       "centerline, base at z=base_m (the room storey's elevation), named "
                       "'wall_<n>' inside ONE room-shell group "
                       "tagged ifcClass IFCBUILDINGELEMENTPROXY predefinedType USERDEFINED "
                       "objectType 'room shell' (or model each wall as its own IFCWALL "
                       "product -- both resolve through the front door)",
            })
    brief = {
        "briefVersion": "1.0",
        "generator": "rvt.frontdoor.prompt_intent.scene_brief",
        "prompt": parsed.prompt,
        "purpose": ("Build this scene in Three.js exactly, tag every product with the "
                    "userData.ifc block given (OUR tagging contract), export IFC4 with the "
                    "canonical three-d-stage exporter (tekton-ifc assets/ifc-export.js v2), "
                    "then run: frontdoor author --ifc <export>.ifc"),
        "instructions": os.path.basename(PROMPT_TO_IFC_MD),
        "ifcMeta": {
            "projectName": parsed.project_name,
            "fileName": slug,
            "author": {"org": "tekton front door"},
            "storeys": storeys,
            "geometry": "auto",
            "excludeNames": ["working_clearance", "door_swing_clearance"],
            "clearanceAs": "skip",
            "minFeatureSize": 0.01,
            "guidSeed": f"{slug}-v1",
        },
        "room": None if not (room and room.width_m and room.depth_m) else {
            "name": room.name, "width_m": room.width_m, "depth_m": room.depth_m,
            "height_m": room.height_m, "wall_thickness_m": room.wall_thickness_m,
            "service_rating_a": room.service_rating_a, "service_voltage": room.service_voltage,
            "origin": "room centred at (0,0); +x east, +y north, +z up (metres)",
            "walls": walls_brief,
            "shell_tagging": {
                "group_name": "room_shell",
                "userData_ifc": {"ifcClass": "IFCBUILDINGELEMENTPROXY",
                                 "predefinedType": "USERDEFINED",
                                 "objectType": "room shell",
                                 "name": room.name,
                                 "psets": [{"name": "RoomInformation", "props": {
                                     "RoomName": room.name,
                                     "ClearWidth": {"value": round(room.width_m - room.wall_thickness_m, 4),
                                                    "type": "length"},
                                     "ClearDepth": {"value": round(room.depth_m - room.wall_thickness_m, 4),
                                                    "type": "length"},
                                     "ClearHeight": {"value": room.height_m, "type": "length"}}}]},
            },
        },
        "products": products,
        "feederTree": [{"from": ed.source, "to": ed.target, "kind": ed.kind,
                        "rating_a": ed.rating_a, "voltage": ed.voltage}
                       for ed in model.feeders],
        "coverage": parsed.coverage.as_json(),
        "next_step": ("Export the scene (toIfc(THREE, model, stage.ifcMeta)) and hand the .ifc "
                      "to the front door: `python tools/frontdoor.py author --ifc <file>.ifc "
                      "--out <dir>` -- the IFC route resolves REAL placements from your "
                      "geometry, so the built .rvt follows your scene, not this brief."),
    }
    return brief


def _group_prefix(kind: str) -> str:
    """Scene-brief group name prefix: 'panel_LP-1', 'receptacle_R-1', 'switchboard_MSB'."""
    if "panelboard" in kind:
        return "panel"
    return "receptacle" if kind == "receptacle_device" else kind


def _type_name_for(eq: I.Equipment) -> str:
    con = eq.contract
    v = (con.get("_voltage") or {}).get("system") or str(con.get("Voltage") or "").replace(" V", "")
    if eq.kind == "receptacle_device":
        dev = (eq.psets or {}).get(DEVICE_PSET) or {}
        return f"RCPT-{v}V-{float(dev.get('Load') or DEFAULT_DEVICE_VA):g}VA-{float(dev.get('MountingHeight') or 0):g}IN"
    if eq.kind == "transformer":
        return (f"XFMR-{float(con.get('RatingkVA') or 75):g}kVA-"
                f"{str(con.get('Primary') or '480 V delta').replace(' V delta', 'D').replace(' ', '')}-"
                f"{str(con.get('Secondary') or '208Y/120 V').replace(' V', '').replace(' ', '')}")
    if eq.kind == "switchboard":
        return (f"SWBD-{v}-{float(con.get('BusRating') or 2500):g}A-"
                f"{'MB' if 'breaker' in str(con.get('MainsType') or 'breaker').lower() else 'MLO'}-"
                f"{int(con.get('Sections') or 4)}SEC")
    mains = str(con.get("MainsType") or "")
    return (f"PB-{v}-{float(con.get('BusRating') or 225):g}A-"
            f"{'MB' if 'breaker' in mains.lower() else 'MLO'}-{int(con.get('NumberOfCircuits') or 42)}SP")


def write_handoff(prompt: str, out_dir: str, *, parsed: Optional[ParsedPrompt] = None,
                  model: Optional[I.IntentModel] = None) -> Dict[str, str]:
    """Write the PRIMARY-PATH handoff package into ``out_dir``:

    * ``scene-brief.json`` -- :func:`scene_brief` (machine-readable);
    * ``HANDOFF.md`` -- what to hand any AI surface (the brief inline + the
      step list + a pointer to the full instructions);
    * ``PROMPT_TO_IFC.md`` -- a copy of the shipped IFC-authoring instructions.

    Returns the written paths.
    """
    if parsed is None or model is None:
        model, parsed = prompt_to_intent(prompt)
    os.makedirs(out_dir, exist_ok=True)
    brief = scene_brief(prompt, parsed=parsed, model=model)
    bp = _jsonsafe.write(os.path.join(out_dir, "scene-brief.json"), brief, indent=2)
    # copy the shipped instructions beside the brief so the package is portable
    ip = os.path.join(out_dir, "PROMPT_TO_IFC.md")
    try:
        with open(PROMPT_TO_IFC_MD) as fh:
            instructions = fh.read()
    except OSError:
        instructions = "(PROMPT_TO_IFC.md not found beside rvt.frontdoor.prompt_intent)\n"
    with open(ip, "w") as fh:
        fh.write(instructions)
    hp = os.path.join(out_dir, "HANDOFF.md")
    with open(hp, "w") as fh:
        fh.write(_render_handoff_md(brief, parsed))
    return {"scene_brief": bp, "handoff": hp, "instructions": ip}


def _render_handoff_md(brief: Dict[str, Any], parsed: ParsedPrompt) -> str:
    room = brief.get("room")
    lines: List[str] = [
        "# Front-door HANDOFF -- prompt -> Three.js scene -> IFC4 -> tekton",
        "",
        "This is the PRIMARY prompt path. Give this file (and `scene-brief.json`) to",
        "ANY AI surface that can write Three.js -- Claude Design / Chat / Cowork,",
        "ChatGPT Work, Gemini -- and follow `PROMPT_TO_IFC.md` (copied here).",
        "The surface builds the scene, exports IFC4 with OUR tagging contract, and",
        "the exported `.ifc` re-enters the front door:",
        "",
        "```bash",
        "python tools/frontdoor.py author --ifc <export>.ifc --out <dir>",
        "```",
        "",
        "## The prompt",
        "",
        f"> {parsed.prompt}",
        "",
        "## What the front door resolved from it",
        "",
    ]
    if room:
        lines += [
            f"* **Room** `{room['name']}`: {room['width_m']:.3f} m x {room['depth_m']:.3f} m, "
            f"{room['height_m']:.2f} m high, wall thickness {room['wall_thickness_m']:.3f} m"
            + (f", **{room['service_rating_a']:g} A service** at {room['service_voltage']} V"
               if room.get('service_rating_a') else ""),
            f"* **Walls**: {len(room['walls'])} (closed counter-clockwise centerline ring, centred at the origin)",
        ]
    lines.append(f"* **Products** ({len(brief['products'])}):")
    for p in brief["products"]:
        u = p["userData_ifc"]
        lines.append(f"  * `{p['tag']}` — {p['kind']} — `{u['ifcClass']}."
                     f"{u['predefinedType']}.` at ({p['position_m']['x']:.2f}, "
                     f"{p['position_m']['y']:.2f}, {p['position_m']['z']:.2f}) m, "
                     f"{p['mounting']}; typeName `{u['typeName']}`")
    ft = brief.get("feederTree") or []
    if ft:
        lines.append(f"* **Feeder tree** ({len(ft)} edges): "
                     + ", ".join(f"{e['from']} -> {e['to']}" for e in ft))
    cov = brief.get("coverage") or {}
    if cov.get("not_built"):
        lines.append("* **Recognised but NOT modelled**: "
                     + ", ".join(sorted({n['kind'] for n in cov['not_built']})))
    if cov.get("ignored_words"):
        lines.append("* **Ignored words**: " + ", ".join(cov["ignored_words"][:20]))
    lines += [
        "",
        "## Build the scene (Three.js) -- the recipe in one screen",
        "",
        "1. `const model = new THREE.Group();` — this is the object you pass to the exporter.",
        "2. For the room: one group `room_shell` tagged with the `shell_tagging.userData_ifc`",
        "   block from `scene-brief.json`; inside it one `THREE.Mesh(new THREE.BoxGeometry(",
        "   length, height, thickness))` per wall named `wall_n` / `wall_s` / `wall_e` /",
        "   `wall_w`, centred on the wall's centerline with its base at z = 0.",
        "3. For every entry in `products`: create a `THREE.Group()`, `group.name =",
        "   product.group_name`, position it at `product.position_m` (metres; the",
        "   three-d-stage convention maps IFC (x, y, z) to THREE (x, z, -y)), model",
        "   the enclosure box at `product.dims_m`, orient it so the equipment FRONT",
        "   faces `product.front_normal`, and set `group.userData.ifc = product.userData_ifc`",
        "   VERBATIM (class, predefinedType, tag, typeName, psets = OUR schedule Psets).",
        "4. `stage.ifcMeta = <brief.ifcMeta>` (storeys, geometry:'auto', guidSeed, ...).",
        "5. `const ifcText = toIfc(THREE, model, stage.ifcMeta)` with the CANONICAL",
        "   exporter (tekton-ifc `assets/ifc-export.js` v2). Save as `<fileName>.ifc`.",
        "6. Return the `.ifc`. Do NOT hand-write STEP text; the exporter emits real",
        "   `IfcLocalPlacement`s + `IfcExtrudedAreaSolid`s + typed Psets from the scene.",
        "",
        "Every detail (property value types, storeys, naming, what the front door",
        "reads back) is in `PROMPT_TO_IFC.md`. The `scene-brief.json` beside this",
        "file is the exact machine-readable version of the list above.",
        "",
        "## Why the brief exists at all",
        "",
        "The front door has a built-in fallback that turns the same prompt straight",
        "into a `.rvt` with NO model call (it produced the intent this brief was",
        "rendered from). The handoff is the PRIMARY path because a Three.js scene",
        "authored by a design surface carries the real geometry, placements and",
        "manufacturer detail a one-line prompt cannot — the IFC route then resolves",
        "REAL insertion points from that geometry.",
        "",
    ]
    return "\n".join(lines)


# ============================================================================
# demo
# ============================================================================

def _main(argv: Optional[Sequence[str]] = None) -> int:  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser(description="prompt -> intent (front-door fallback) / scene brief")
    ap.add_argument("prompt", nargs="?", default=("an electrical room 30x20 ft rated for 2500 A service "
                                                   "with a main switchboard, two 400 A distribution "
                                                   "panels and four lighting panels"))
    ap.add_argument("--brief", action="store_true", help="print the scene brief instead")
    ap.add_argument("-o", "--out", default=None, help="write the intent JSON here")
    a = ap.parse_args(argv)
    model, parsed = prompt_to_intent(a.prompt)
    if a.brief:
        print(json.dumps(scene_brief(a.prompt, parsed=parsed, model=model), indent=1, default=str))
        return 0
    print(f"prompt: {parsed.prompt!r}")
    if parsed.room:
        print(f"room  : {parsed.room.name} {parsed.room.width_m} x {parsed.room.depth_m} m "
              f"h={parsed.room.height_m} service={parsed.room.service_rating_a} A "
              f"{parsed.room.service_voltage} V walls={parsed.room.walls}")
    for e in model.equipment:
        print(f"  {e.tag:6s} {e.kind:24s} at {[round(x, 2) for x in e.insertion_m]} "
              f"front={e.front_normal[:2]} {e.frame_kind:7s} {e.mounting}")
    for p in model.family_plans:
        print(f"  map {p.tag:6s} -> {p.status:8s} "
              f"{p.constructor.split('.')[-1] if p.constructor else '-':24s} {p.variant or ''} "
              f"{(p.refusal or '')[:60]}")
    for ed in model.feeders:
        print(f"  feed {ed.source} -> {ed.target} ({ed.kind}) {ed.rating_a} A {ed.voltage or ''}")
    print("coverage:", json.dumps(parsed.coverage.as_json(), indent=1))
    if a.out:
        I.write_intent(model, a.out)
        print(f"intent -> {a.out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())

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
    luminaires by count, rating, voltage, mains style, spaces; walls; levels;
    feeders), :func:`layout_room` places everything by a deterministic
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

import json
import math
import os
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

# LAZY (perf-coldstart): the prompt route is pure-python end to end; numpy
# stays un-imported unless a numeric path is actually exercised.
from .._lazyimp import lazy_import

np = lazy_import("numpy", globals(), "np", hint="prompt-intent numeric math")

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
    "a": 1, "an": 1, "one": 1, "single": 1, "two": 2, "pair": 2, "three": 3,
    "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "eleven": 11, "twelve": 12, "dozen": 12, "no": 0, "zero": 0,
}

#: equipment kinds: (kind, tag prefix, regex over the noun phrase).  ORDER
#: MATTERS -- most specific first; a matched span is consumed so a bare
#: "panels" cannot re-match text a "distribution panels" clause already took.
_KIND_PATTERNS: List[Tuple[str, str, str]] = [
    ("switchboard", "MSB",
     r"(?:main\s+(?:service\s+)?)?(?:service\s+(?:entrance\s+)?)?switch\s*boards?"
     r"|switch\s*gear|\bmsb\b|service\s+entrance\s+(?:board|equipment)"),
    ("distribution_panelboard", "DP",
     r"(?:power\s+)?distribution\s+(?:panel\s*boards?|panels?|boards?|sections?)"
     r"|power\s+panels?|\bmdp\b|\bdps?\b|distribution\s+panelboards?"),
    ("lighting_panelboard", "LP",
     r"lighting\s+(?:and\s+appliance\s+)?(?:panel\s*boards?|panels?)|\blps?\b"),
    ("receptacle_panelboard", "RP",
     r"(?:receptacle|appliance|branch(?:\s*-?\s*circuit)?|utility)\s+(?:panel\s*boards?|panels?)"
     r"|\brps?\b"),
    ("transformer", "T",
     r"(?:dry[\s-]*type\s+)?(?:step[\s-]*(?:down|up)\s+)?transformers?|\bxfmrs?\b"),
    ("panelboard", "PP",
     r"panel\s*boards?|(?:electrical\s+|branch\s+)?panels?"),
]

#: recognised but NOT in the model build path today (coverage honesty)
_UNBUILT_PATTERNS: List[Tuple[str, str]] = [
    ("luminaire", r"(?:led\s+)?(?:luminaires?|light\s+fixtures?|lighting\s+fixtures?|troffers?"
                  r"|down\s*lights?|high[\s-]*bays?|wall\s*packs?|exit\s+signs?)"),
    ("generator", r"(?:standby\s+|emergency\s+)?generators?|genset"),
    ("ups", r"\bups\b|uninterruptible\s+power\s+suppl(?:y|ies)"),
    ("transfer_switch", r"(?:automatic\s+)?transfer\s+switch(?:es)?|\bats\b"),
    ("motor_control_center", r"motor\s+control\s+cent(?:er|re)s?|\bmcc\b"),
    ("busway", r"bus\s*(?:way|duct|bar\s+trunking)"),
    ("disconnect", r"(?:fused\s+|non[\s-]*fused\s+)?disconnect(?:\s+switch(?:es)?)?s?|safety\s+switch(?:es)?"),
    ("receptacle_device", r"(?:duplex\s+|quad\s+|gfci\s+)?receptacles?(?!\s+panel)|outlets?"),
    ("meter", r"\bmeters?\b|metering(?:\s+cabinet)?|ct\s+cabinet"),
    ("cable_tray", r"cable\s+trays?"),
    ("conduit", r"conduits?|racew?ays?"),
    ("door", r"\bdoors?\b|egress"),
    ("housekeeping_pad", r"house\s*keeping\s+pads?|equipment\s+pads?"),
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
_RE_NAMED = re.compile(r"(?:named|called|tagged|labell?ed|mark(?:ed)?)\s+[\"']?([A-Za-z][A-Za-z0-9\-]{0,11})[\"']?", re.I)

#: room / dimension extractors
_RE_ROOM = re.compile(
    r"(?P<pre>(?:main\s+|new\s+|the\s+)*(?:electrical|electric|elec\.?|equipment|switch\s*gear|"
    r"transformer|mechanical|electrical\s+equipment|mdf|idf|utility|service|panel)\s+)?"
    r"(?P<noun>room|closet|vault|space)\b", re.I)
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
_RE_NO_WALLS = re.compile(r"no\s+walls|without\s+walls|equipment\s+only|no\s+room", re.I)
_RE_NO_FEEDERS = re.compile(r"no\s+(?:feeders|circuits)|without\s+(?:feeders|circuits)|uncircuited", re.I)
_RE_WALL_THICK = re.compile(r"walls?\s+(?:that\s+are\s+|of\s+)?(?P<t>\d{1,3}(?:\.\d+)?)\s*(?P<u>" +
                            _DIM_UNIT + r")\s*thick", re.I)
_RE_LEVEL = re.compile(r"(?:on|at)\s+(?:level|floor|storey|story)\s+(?P<n>\d{1,2}|one|two|three|ground)"
                       r"|(?P<n2>two|three|2|3)[\s-]*(?:stor(?:e)?y|level|floor)\b", re.I)
_RE_FED_FROM = re.compile(r"(?P<load>[A-Za-z][A-Za-z0-9\-]{0,10})\s+(?:is\s+)?fed\s+(?:from|by)\s+"
                          r"(?:the\s+)?(?P<src>[A-Za-z][A-Za-z0-9\-]{0,10})", re.I)

#: default voltages / dims (prompt defaults -- always flagged as defaults)
DEFAULT_SERVICE_VOLTAGE = "480Y/277"
DEFAULT_ROOM_HEIGHT_M = 3.6576          # 12 ft
DEFAULT_WALL_THICKNESS_M = 0.2032       # 8 in
DEFAULT_PANEL_SPACES = 42
DEFAULT_LP_SPACES = 42
DEFAULT_PANEL_MOUNT_CENTER_M = 1.42     # enclosure centre AFF (top ~2.0 m for a 60 in box)
DEFAULT_PAD_M = 0.1                     # housekeeping pad height (floor gear elevation)
DEFAULT_XFMR_KVA = 75.0

#: prompt-default panelboard box (metres) used ONLY when the catalog resolver
#: refuses; a resolved plan REPLACES these with catalog facts
_DEF_PANEL_DIMS = {"w": 0.508, "d": 0.190, "h": 1.219}
_DEF_LP_DIMS = {"w": 0.508, "d": 0.146, "h": 1.219}


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
    fed_from: Optional[str] = None
    name: Optional[str] = None
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
                "items were recognised but are outside today's model build path; "
                "'defaults_applied' names every value the parser had to assume."),
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
            cov.warnings.append("a room was named but no dimensions were given: no room shell "
                                "will be built (equipment only)")
            room.walls = False
        m_h = _RE_HEIGHT.search(text)
        if m_h:
            mark(m_h.span())
            hv, hu = (m_h.group("h"), m_h.group("u")) if m_h.group("h") else (m_h.group("h2"), m_h.group("u2"))
            room.height_m = round(_to_metres(_clean_num(hv), hu), 4)
            room.height_default = False
            cov.understood.append({"clause": m_h.group(0), "as": "room height",
                                   "height_m": room.height_m})
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
    #: the room noun (and its pre-word: 'switchgear room', 'transformer
    #: vault') is a place, never a piece of equipment
    room_taken: List[Tuple[int, int]] = [m_room.span()] if m_room else []

    # ------------------------------------------------------------------
    # 2. EQUIPMENT clauses (count + kind + attributes)
    # ------------------------------------------------------------------
    items: List[PromptItem] = []
    counters: Dict[str, int] = {}
    #: attribute window around a kind match: text between the previous
    #: comma/'and'/period and the next comma/'and'/period
    boundaries = [m.start() for m in re.finditer(r",|;|\band\b|\bplus\b|\bwith\b|\.", low)]

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

    for kind, prefix, pat in _KIND_PATTERNS:
        for km in re.finditer(pat, low):
            if overlaps(km.start(), km.end()):
                continue
            ws, we = clause_window(km.start(), km.end())
            window = text[ws:we]
            wlow = window.lower()
            # count: the nearest number-word / digit BEFORE the noun in the
            # window, after RATING expressions ('400 A', '75 kVA', '65 kA',
            # '42-space', '480Y/277 V') are scrubbed so a unit letter ('A')
            # or a rating digit is never mistaken for a count.
            head = wlow[: km.start() - ws]
            head_count = head
            for scrub in (_RE_AMP, _RE_KVA, _RE_KA, _RE_SPACES, _RE_SECTIONS,
                          _RE_VOLT_SYS, _RE_VOLT_SLASH, _RE_VOLT_PLAIN):
                head_count = scrub.sub(" ", head_count)
            cnt = 1
            mnum = re.findall(r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|"
                              r"eleven|twelve|a|an|pair|single)\b", head_count)
            plural = km.group(0).rstrip().endswith("s") or "pair" in head
            explicit_count = None
            for tok in reversed(mnum):
                nv = _num_word(tok)
                if nv is None:
                    continue
                explicit_count = nv
                break
            if explicit_count is not None:
                cnt = explicit_count
            elif plural:
                cnt = 2 if kind != "switchboard" else 1
                cov.defaults_applied.append(f"'{km.group(0)}' plural with no count: assumed {cnt}")
            if cnt <= 0:
                continue
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
            named = _RE_NAMED.search(window)
            for j in range(cnt):
                counters[prefix] = counters.get(prefix, 0) + 1
                idx = counters[prefix]
                if named and cnt == 1:
                    tag = named.group(1).upper()
                elif prefix == "MSB":
                    tag = "MSB" if idx == 1 else f"MSB-{idx}"
                elif prefix == "T":
                    tag = f"T{idx}"
                else:
                    tag = f"{prefix}-{idx}"
                it = PromptItem(kind=kind, tag=tag, count_index=idx, source_text=window.strip())
                if amp:
                    it.rating_a = _clean_num(amp.group(1))
                if kva:
                    it.kva = _clean_num(kva.group(1))
                if ka:
                    it.sccr_ka = _clean_num(ka.group(1))
                it.voltage = volt
                it.mains = mains
                it.spaces = int(spaces.group(1)) if spaces else None
                it.mounting = mounting
                it.sections = int(sections.group(1)) if sections else None
                items.append(it)
            taken.append((km.start(), km.end()))
            mark((km.start(), km.end()))
            for sub in (amp, kva, ka, spaces, sections, named):
                if sub is not None:
                    mark((ws + sub.start(), ws + sub.end()))
            if mains:
                mm = (_RE_MCB.search(window) or _RE_MLO.search(window))
                mark((ws + mm.start(), ws + mm.end()))
            for vm in (_RE_VOLT_SYS.search(window), _RE_VOLT_SLASH.search(window),
                       _RE_VOLT_PLAIN.search(window)):
                if vm is not None:
                    mark((ws + vm.start(), ws + vm.end()))
            for nm in re.finditer(r"\b(\d{1,2}|one|two|three|four|five|six|seven|eight|nine|ten|"
                                  r"eleven|twelve)\b", head):
                if _num_word(nm.group(1)) == cnt:
                    mark((ws + nm.start(), ws + nm.end()))
            cov.understood.append({
                "clause": text[km.start():km.end()], "as": "equipment", "kind": kind,
                "count": cnt, "rating_a": (items[-1].rating_a if items else None),
                "kva": (items[-1].kva if items else None), "voltage": volt,
                "mains": mains, "spaces": (items[-1].spaces if items else None),
            })

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
    unbuilt: List[Dict[str, Any]] = []
    for kind, pat in _UNBUILT_PATTERNS:
        for um in re.finditer(pat, low):
            if overlaps(um.start(), um.end()):
                continue
            taken.append((um.start(), um.end()))
            mark(um.span())
            rec = {"text": text[um.start():um.end()], "kind": kind,
                   "reason": ("recognised, but this kind is outside today's model build "
                              "path (recorded in the intent, NOT modelled). Luminaires: "
                              "our make_luminaire family exists but the room build "
                              "places electrical EQUIPMENT only; devices/conduit/doors "
                              "belong to the fixture / conduit / hosting streams.")}
            unbuilt.append(rec)
            cov.not_built.append(rec)

    # ------------------------------------------------------------------
    # 4. levels
    # ------------------------------------------------------------------
    levels: List[dict] = [{"id": "L1", "name": "Level 1", "elevation": 0.0}]
    m_lv = _RE_LEVEL.search(text)
    if m_lv:
        mark(m_lv.span())
        raw = (m_lv.group("n") or m_lv.group("n2") or "").lower()
        n = {"one": 1, "ground": 1, "two": 2, "three": 3}.get(raw) or (int(raw) if raw.isdigit() else 1)
        n = max(1, min(3, n))
        h = (room.height_m if room and room.height_m else DEFAULT_ROOM_HEIGHT_M)
        levels = [{"id": f"L{i + 1}", "name": f"Level {i + 1}", "elevation": round(i * (h + 0.3), 4)}
                  for i in range(n)]
        cov.understood.append({"clause": m_lv.group(0), "as": "levels", "count": n})
        if n > 1:
            cov.warnings.append(f"{n} levels created; all equipment is placed on Level 1 "
                                "(per-level placement is not parsed from a prompt yet)")

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
        raise PromptError(
            "the prompt names neither buildable equipment (switchboard / panels / "
            "transformers) nor a room with dimensions -- nothing to author. "
            "Recognised-but-unbuilt kinds: "
            + (", ".join(sorted({u['kind'] for u in unbuilt})) or "none")
            + ". Ignored words: " + (", ".join(ignored[:12]) or "none"))

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
                              else DEFAULT_PANEL_MOUNT_CENTER_M]
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
    room_service = float(room.service_rating_a or 0.0)

    # ---- floor lineup along the north wall interior ----------------------
    if floor_items:
        back_gap = 0.10
        gap = 0.30
        total = sum(float(it.dims_m.get("w", 1.0)) for it in floor_items) \
            + gap * (len(floor_items) - 1)
        avail = 2 * hw_in - 0.6
        if total > avail:
            cov.warnings.append(f"floor lineup ({total:.2f} m) is wider than the north wall "
                                f"interior ({avail:.2f} m): items overrun -- widen the room")
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
        order = {"distribution_panelboard": 0, "panelboard": 1,
                 "lighting_panelboard": 2, "receptacle_panelboard": 3}
        wall_sorted = sorted(wall_items, key=lambda it: (order.get(it.kind, 9), it.count_index))
        for k, it in enumerate(wall_sorted):
            (west if k % 2 == 0 else east).append(it)
        for side, group, x_face, front in (("W-W", west, -hw_in, [1.0, 0.0, 0.0]),
                                          ("W-E", east, +hw_in, [-1.0, 0.0, 0.0])):
            y = hd_in - 0.60                              # start near the north end
            for it in group:
                w = float(it.dims_m.get("w", 0.508))
                y -= w / 2.0
                it.insertion_m = [round(x_face, 4), round(y, 4), DEFAULT_PANEL_MOUNT_CENTER_M]
                it.front = list(front)
                it.frame_kind, it.mount_kind = "upright", "surface"
                it.yaw_deg = math.degrees(math.atan2(front[1], front[0])) if False else 0.0
                it.wall_id = side
                y -= w / 2.0 + pitch
                if y < -hd_in + 0.3:
                    cov.warnings.append(f"the {side} wall is full: {it.tag} overruns the south "
                                        "corner -- widen/deepen the room or reduce the panel count")


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

    # ---- equipment -> rvt.ifc.intent.Equipment ---------------------------
    equipment: List[I.Equipment] = []
    for k, it in enumerate(parsed.buildable_items):
        con = _contract_for(it)
        plc = I.Placement(I.identity_matrix(), [],
                          ["prompt-authored: no IFC placement chain"])
        geom = I.ProductGeometry(items=[])
        cls = {"switchboard": "IfcElectricDistributionBoard",
               "transformer": "IfcTransformer"}.get(it.kind, "IfcElectricDistributionBoard")
        pdt = {"switchboard": "SWITCHBOARD", "transformer": "VOLTAGE"}.get(it.kind, "DISTRIBUTIONBOARD")
        desc = ("floor-mounted lineup on a housekeeping pad" if it.kind in ("switchboard", "transformer")
                else "surface wall-mounted panelboard")
        eq = I.Equipment(
            step_id=-(k + 1), guid=f"prompt:{it.tag}", ifc_class=cls, predefined_type=pdt,
            name=(f"{it.tag} - " + _describe_item(it)), tag=it.tag,
            description=f"{_describe_item(it)}; {desc} (front-door prompt layout)",
            object_type=None, type_name=None, kind=it.kind, psets=con.pop("_prompt_psets"),
            contract=con, placement=plc, geometry=geom)
        eq.insertion_m = list(map(float, it.insertion_m))
        eq.front_normal = [float(it.front[0]), float(it.front[1]), 0.0]
        eq.dims_m = dict(it.dims_m)
        eq.elevation_m = float(it.insertion_m[2]) if it.frame_kind == "yaw" else float(
            it.insertion_m[2] - float(it.dims_m.get("h", 1.2)) / 2.0)
        if it.frame_kind == "upright":
            eq.frame3x3 = _upright_frame(eq.front_normal)
            fx = eq.frame3x3[0]
            eq.yaw_deg = math.degrees(math.atan2(fx[1], fx[0]))
            eq.mounting = "surface"
            eq.mounting_height_m = float(it.insertion_m[2])
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
                height_m=float(room_pr.height_m), base_m=0.0, synthesized=False,
                reason=("authored from the prompt's room dimensions (deterministic layout: "
                        "closed counter-clockwise centerline ring centred at the origin, "
                        "interior on the left of every wall's drawing direction)"),
                derived_from=[f"prompt: {room_pr.source_text.strip()}"] if room_pr.source_text.strip()
                else ["prompt room dimensions"]))
        room = I.RoomShell(name=room_pr.name or "Electrical Room", step_id=None, walls=walls)
        hw, hd = room_pr.width_m / 2.0, room_pr.depth_m / 2.0
        room.clear = {"clearWidth_m": room_pr.width_m - room_pr.wall_thickness_m,
                      "clearDepth_m": room_pr.depth_m - room_pr.wall_thickness_m,
                      "clearHeight_m": room_pr.height_m, "wall_height_m": room_pr.height_m,
                      "base_m": 0.0, "ring_ccw": True,
                      "centerline_extents_m": {"x": [-hw, hw], "y": [-hd, hd]}}
        room.info = {"RoomName": room_pr.name, "ClearWidth": room_pr.width_m,
                     "ClearDepth": room_pr.depth_m, "ClearHeight": room_pr.height_m,
                     "ServiceRatingA": room_pr.service_rating_a,
                     "ServiceVoltage": room_pr.service_voltage}
        room.notes.append("prompt-authored room shell: door openings, floor slab and "
                          "housekeeping pads are NOT authored from a prompt (hosting / floor "
                          "streams); the walls sit on Level 1")
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
        other_products=[{"kind": u["kind"], "name": u["text"], "disposition": u["reason"]}
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
    storeys = [{"name": lv.get("name") or f"Level {i + 1}",
                "elevation": float(lv.get("elevation") or 0.0)}
               for i, lv in enumerate(model.levels or [])] or [{"name": "Level 1", "elevation": 0.0}]
    fed_by = {ed.target: ed.source for ed in model.feeders if ed.kind != "service"}

    products = []
    for eq in model.equipment:
        con = {k: v for k, v in eq.contract.items()
               if not k.startswith("_") and v not in (None, "")}
        pset_name = ("TransformerSchedule" if eq.kind == "transformer"
                     else "SwitchboardSchedule" if eq.kind == "switchboard"
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
        if eq.tag in fed_by:
            typed["FedFrom"] = fed_by[eq.tag]
        pos = [round(float(x), 4) for x in eq.insertion_m]
        products.append({
            "group_name": f"{'panel' if 'panelboard' in eq.kind else eq.kind}_{eq.tag}",
            "tag": eq.tag, "kind": eq.kind,
            "position_m": {"x": pos[0], "y": pos[1], "z": pos[2],
                           "note": ("Three.js is Y-up: place the group at (x, elevation, -y) "
                                    "if your stage maps IFC(x,y,z) -> THREE(x,z,-y) [the "
                                    "three-d-stage convention]; the exporter writes real "
                                    "IfcLocalPlacements from group positions")},
            "front_normal": [round(float(x), 3) for x in eq.front_normal[:2]],
            "yaw_deg": round(float(eq.yaw_deg), 2),
            "mounting": eq.mounting,
            "dims_m": {k: round(float(v), 4) for k, v in eq.dims_m.items() if k in ("w", "d", "h")},
            "storey": storeys[0]["name"],
            "userData_ifc": {
                "ifcClass": eq.ifc_class.upper(),
                "predefinedType": eq.predefined_type or "NOTDEFINED",
                "name": eq.tag, "tag": eq.tag, "storey": storeys[0]["name"],
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
                "how": "a THREE.BoxGeometry(length, height, thickness) centred on the "
                       "centerline, base at z=0, named 'wall_<n>' inside ONE room-shell group "
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


def _type_name_for(eq: I.Equipment) -> str:
    con = eq.contract
    v = (con.get("_voltage") or {}).get("system") or str(con.get("Voltage") or "").replace(" V", "")
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
    bp = os.path.join(out_dir, "scene-brief.json")
    with open(bp, "w") as fh:
        json.dump(brief, fh, indent=2, default=str)
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

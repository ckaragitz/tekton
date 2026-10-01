"""rvt.famgen.archetypes -- NAMED PRODUCTS generated at STANDARD NOMINAL sizes.

THE ASK (owner steer #591, verbatim): *"pause , for example if i say crate a
cable tray family you should be able to create it in lod 400, you should be
able to create anything"*.

Before this module, "create a cable tray family" was REFUSED: the prompt names
no dimensions, the catalog holds no cable tray, and the `generic_model` lane
needs the caller to supply geometry.  Three honest lanes, and a request that
fell between all of them.

WHY GENERATING IT IS NOT A CONTRACT VIOLATION.  The rule the honesty contract
actually protects is *never present an invented dimension as a manufacturer
fact*.  It has never been *never generate geometry*.  So this module adds a
fourth provenance tier beside the three the factory already has:

===========  ====================================================  =============
provenance   where the number came from                            example
===========  ====================================================  =============
``fact``     a published catalog record we hold                    Eaton PRL2X, 20.00 in wide
``given``    the caller said so (a prompt, an IFC mesh, a famspec) "a 24 inch cable tray"
``assumed``  a catalog-flagged assumption / a rule off a fact      the PRL1X height row
``nominal``  **standard practice for this product class**          a 12 in ladder tray
===========  ====================================================  =============

A ``nominal`` value is NOT a manufacturer claim and never becomes one: no
manufacturer, no model, no part number is attached to an archetype family, and
`Fact.unverified()` reports every nominal field so the report says out loud
which dimensions were generated rather than sourced.  **The nominals here are
standard industry practice for the product class -- they are not read from a
standards document held in this repo**, and each parameter says which practice
it follows in its ``basis``.  Ask for "an Eaton B-Line 24 in tray, part number
X" and :func:`manufacturer_claim` catches it: the generic family is still
delivered (hard rule 1 -- output is never withheld), carrying no manufacturer,
model or part number, and the delivery says in its status line and its report
that THE NAMED ITEM IS NOT WHAT YOU RECEIVED.  That is what steer #591's "must
not SILENTLY become a generic nominal tray wearing that part number" asks for:
not a refusal to build, a refusal to pretend.

__all__ ordering note: :func:`manufacturer_claim` is part of the public surface
for exactly that reason -- any caller building an archetype family from user
text must be able to ask the question before it hands the file over.

LOD 400 MEANS THE PARTS ARE THE REAL PARTS.  A ladder tray is two side rails
and rungs at the standard spacing, not a box labelled "cable tray"; a strut
channel is a back, two webs and two inturned lips.  Every archetype emits the
ordinary ``parts`` list `factory.make_generic_model` already authors, so the
whole set travels the box / N-gon / arc paths desktop Revit 2026 has verified.

ADDING A PRODUCT IS ONE ENTRY AND ONE FUNCTION (steer #591 DONE 5): an
:class:`Archetype` in :data:`ARCHETYPES` with its :class:`Param` list, its
recognition patterns and a builder that turns resolved parameters into parts.
Nothing else in the engine changes.

Territory: famgen (new module; emits part dicts + a FactSheet, edits no writer
path).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field as dc_field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "ArchetypeError", "Param", "Archetype", "Resolved", "ARCHETYPES",
    "NOMINAL", "GIVEN", "archetype", "keys", "resolve_prompt", "resolve",
    "build_parts", "describe", "table", "check_registry", "manufacturer_claim",
    "MAX_PARTS",
]

#: the provenance tiers this module writes (``factory.Fact.kind`` values)
NOMINAL = "nominal"
GIVEN = "given"


class ArchetypeError(ValueError):
    """An archetype request that cannot be honestly built (unknown product, a
    parameter outside the range the geometry is defined for)."""


#: one family is one .rfa: a part list past this is a runaway parameter (a
#: 20 ft tray at 0.1 in rung spacing), refused by name rather than built.
MAX_PARTS = 400

IN = 1.0 / 12.0                      # inches -> feet
MM = 1.0 / 304.8                     # millimetres -> feet


# ---------------------------------------------------------------------------
# one generated dimension
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Param:
    """One dimension of an archetype.

    ``default`` is the NOMINAL value in ``unit``; ``basis`` says which standard
    practice that nominal follows (it is the sentence the report prints, so
    write it for an engineer reading the manifest).  ``choices`` are the
    standard sizes of the product class -- informational: a caller may pass
    anything, and a value off the list is still ``given``, never corrected.

    ``aliases`` are the words a prompt uses for this dimension; the resolver
    builds its patterns from them, so a new parameter needs no regex.
    """
    key: str
    label: str
    default: float
    unit: str = "in"                            # 'in' | 'ft' | 'count'
    basis: str = ""
    aliases: Tuple[str, ...] = ()
    choices: Tuple[float, ...] = ()
    minimum: float = 0.0
    #: 0 is a MEANING for this parameter (a solid strut back), not a degenerate
    #: size.  Everywhere else 0 is refused: a zero thickness authored boxes of
    #: zero volume that passed every other guard.
    allow_zero: bool = False
    primary: bool = False                       # "a 24 inch cable tray" -> this one
    #: this dimension FOLLOWS another when the caller states that one and not
    #: this one -- a square wireway asked for at 12 in is 12 in tall.  The
    #: followed value is the caller's, so the follower is ``given`` too, with
    #: the reason quoted rather than presented as a nominal.
    follows: str = ""
    #: the largest value a PROMPT may bind (in ``unit``): a number past it
    #: belongs to another phrase -- "1/2 in rod 24 in apart" is not a 24 in
    #: rod (#900 review).  A famspec override is not limited by it.
    maximum: float = math.inf

    def feet(self, value: Optional[float] = None) -> float:
        v = self.default if value is None else float(value)
        if self.unit == "in":
            return v * IN
        if self.unit == "ft":
            return v
        return v                                # count / unitless

    def display(self, value: Optional[float] = None) -> str:
        v = self.default if value is None else float(value)
        return f"{v:g} {self.unit}" if self.unit != "count" else f"{v:g}"


# ---------------------------------------------------------------------------
# one product
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Archetype:
    """A named product generated at standard nominal sizes.

    ``build(vals)`` receives every parameter resolved to its NATURAL unit (the
    ``Param.unit``, not feet -- the builders convert, so the numbers read like
    the standard they come from) and returns the part list.
    """
    key: str
    title: str                                  # "Cable Tray - Ladder"
    category: str                               # the family category
    basis: str                                  # the practice the nominals follow
    params: Tuple[Param, ...]
    build: Callable[[Dict[str, float]], List[Dict[str, Any]]]
    patterns: Tuple[str, ...] = ()              # how a prompt names it
    lod_note: str = ""                          # what the parts ARE
    limits: Tuple[str, ...] = ()                # what this model does NOT carry
    standard_values: Callable[[Dict[str, float]], Dict[str, Any]] = lambda v: {}
    #: True for equipment NEC 110.26 gives a working space in front of --
    #: a prompt asking for "clearance" / "working space" then gets the zone
    #: drawn from rvt.famgen.clearance (#818 / #820)
    working_space: bool = False
    aliases: Tuple[str, ...] = ()               # display names, for the report
    #: the Revit FAMILY PARAMETERS this product carries, with their values:
    #: ``vals -> {caption: (spec_key, value_in_internal_units)}``.  Empty for
    #: the products whose dimensions live in the fact sheet only; an assembly a
    #: user adjusts (a trapeze: tiers, rod spacing, rod size) lists every one.
    family_params: Callable[[Dict[str, float]], Dict[str, Any]] = lambda v: {}
    #: extra words for the family NAME after the primary dimension ("2 Tier")
    name_bits: Callable[[Dict[str, float]], List[str]] = lambda v: []
    #: dimensions DERIVED from others once the caller's are known -- run after
    #: ``follows``, with the provenance, so a derived value is ``given`` when
    #: the caller's numbers decided it: ``(vals, prov, quoted) -> None``
    settle: Optional[Callable[[Dict[str, float], Dict[str, str], Dict[str, str]], None]] = None
    #: a measurement right before one of these words in the product name
    #: binds THIS parameter instead of the primary: "a 1-5/8 in strut
    #: trapeze" names the channel, not a 1.6 in trapeze (#900 review)
    noun_leads: Tuple[Tuple[str, str], ...] = ()

    def param(self, key: str) -> Param:
        for p in self.params:
            if p.key == key:
                return p
        raise ArchetypeError(f"{self.key}: no parameter {key!r}")

    def defaults(self) -> Dict[str, float]:
        return {p.key: p.default for p in self.params}


@dataclass
class Resolved:
    """An archetype request with every dimension resolved AND attributed."""
    arch: Archetype
    values: Dict[str, float]
    #: parameter key -> 'nominal' | 'given'
    provenance: Dict[str, str] = dc_field(default_factory=dict)
    #: what the prompt said for each given key, verbatim
    quoted: Dict[str, str] = dc_field(default_factory=dict)
    name: str = ""
    #: set when the prompt named a SPECIFIC manufacturer's item that this
    #: generic family is not (:func:`manufacturer_claim`)
    claim: Optional[Dict[str, Any]] = None
    #: the prompt asked for the NEC working-space clearance (#820)
    clearance: bool = False
    #: keys ``Archetype.settle`` DERIVED from the caller's numbers -> the
    #: reason; ``given`` (the caller's numbers decided them) but not stated
    derived: Dict[str, str] = dc_field(default_factory=dict)
    #: numbers the prompt stated for a dimension that stayed NOMINAL because
    #: they are outside its range: ``[{key, label, said, range}]`` -- reported,
    #: never silently dropped (#900 review round 3)
    out_of_range: List[Dict[str, Any]] = dc_field(default_factory=list)

    def given(self) -> List[str]:
        return sorted(k for k, v in self.provenance.items() if v == GIVEN)

    def nominal(self) -> List[str]:
        return sorted(k for k, v in self.provenance.items() if v == NOMINAL)

    def parts(self) -> List[Dict[str, Any]]:
        parts = self.arch.build(dict(self.values))
        if self.clearance and self.arch.working_space:
            parts.append(working_space_part(self))
        return parts

    def to_json(self) -> Dict[str, Any]:
        return {
            "product": self.arch.key,
            "title": self.arch.title,
            "category": self.arch.category,
            "basis": self.arch.basis,
            "lod": self.arch.lod_note,
            "limits": list(self.arch.limits),
            "dimensions": [
                {"key": p.key, "label": p.label,
                 "value": self.values[p.key], "unit": p.unit,
                 "display": p.display(self.values[p.key]),
                 "provenance": self.provenance.get(p.key, NOMINAL),
                 "basis": p.basis,
                 "standard_sizes": list(p.choices),
                 **({"from_prompt": self.quoted[p.key]} if p.key in self.quoted else {})}
                for p in self.arch.params],
            "given": self.given(),
            "nominal": self.nominal(),
            **({"derived": dict(self.derived)} if self.derived else {}),
            **({"out_of_range": list(self.out_of_range)} if self.out_of_range else {}),
            "manufacturer_claim": self.claim,
            **({"working_space": working_space_report(self)}
               if self.clearance and self.arch.working_space else {}),
        }


# ---------------------------------------------------------------------------
# the builders -- each turns resolved dimensions into ordinary part dicts
# ---------------------------------------------------------------------------

def _box(name, w, d, h, cx=0.0, cy=0.0, base=0.0) -> Dict[str, Any]:
    return {"shape": "box", "name": name, "width_ft": w, "depth_ft": d,
            "height_ft": h, "center": [cx, cy], "base_z_ft": base}


def _ladder_tray(v: Dict[str, float]) -> List[Dict[str, Any]]:
    """A LADDER cable tray straight section: two side rails (each a channel --
    web plus top and bottom flange turned inward) and rungs at the standard
    spacing.  The run lies along X, the usable width along Y, the loading
    depth up Z, and the section is centred on its own origin."""
    W = float(v["width_in"]) * IN                       # inside (usable) width
    D = float(v["depth_in"]) * IN                       # loading depth = rail height
    L = float(v["length_ft"])
    S = float(v["rung_spacing_in"]) * IN
    t = float(v["rail_thickness_in"]) * IN
    fl = float(v["rail_flange_in"]) * IN
    rw = float(v["rung_width_in"]) * IN
    rt = float(v["rung_thickness_in"]) * IN
    if W <= 0 or D <= 0 or L <= 0 or S <= 0:
        raise ArchetypeError("a ladder tray needs a positive width, depth, length "
                             "and rung spacing")
    if rw >= L:
        raise ArchetypeError(f"a {rw / IN:g} in rung does not fit in a {L:g} ft section")
    if rw >= S:
        raise ArchetypeError(f"a {rw / IN:g} in rung does not fit in a {S / IN:g} in "
                             f"rung spacing -- the rungs would run through each other")
    if fl * 2.0 >= W:
        raise ArchetypeError(f"rail flanges ({fl / IN:g} in each) do not fit inside a "
                             f"{W / IN:g} in tray")
    # the two flanges + the rung between them have to fit in the rail height, or
    # the "solid" is two slabs intersecting each other
    if D <= 2.0 * t:
        raise ArchetypeError(f"a {D / IN:g} in loading depth is not deeper than the "
                             f"two {t / IN:g} in rail flanges it has to hold")
    if rt > D - 2.0 * t:
        raise ArchetypeError(f"a {rt / IN:g} in rung does not fit between the flanges "
                             f"of a {D / IN:g} in deep rail")
    parts: List[Dict[str, Any]] = []
    for sign, side in ((1.0, "left"), (-1.0, "right")):
        y_web = sign * (W / 2.0 + t / 2.0)
        parts.append(_box(f"side rail {side} - web", L, t, D, 0.0, y_web))
        y_fl = sign * (W / 2.0 - fl / 2.0)              # flanges turn INWARD
        parts.append(_box(f"side rail {side} - bottom flange", L, fl, t, 0.0, y_fl, 0.0))
        parts.append(_box(f"side rail {side} - top flange", L, fl, t, 0.0, y_fl, D - t))
    # RUNGS SIT AT THE STATED PITCH.  Spreading them evenly over the length
    # (L/(n-1)) made the achieved spacing differ from the spacing the family
    # reports -- 9 in asked for, 9.23 in built -- which is a parameter lying
    # about its own geometry.  They are laid from the first rung at the stated
    # S, and whatever length does not divide by S is left as a shorter END BAY,
    # which is what a real section does at a splice.
    # a spacing wider than the section gives ONE centred rung -- max(2, ...)
    # put two rungs a foot past both ends of the rails, attached to nothing
    n = max(1, int(math.floor((L - rw) / S + 1e-9)) + 1)
    if n + len(parts) > MAX_PARTS:                # parts, not rungs (the rails count)
        raise ArchetypeError(
            f"{n} rungs plus {len(parts)} rail parts at {S / IN:g} in over {L:g} ft is "
            f"past the {MAX_PARTS}-part budget for one family; ask for a longer "
            f"spacing or a shorter section")
    # the run of rungs is CENTRED on the section, so the two end bays are equal
    # and short -- the pitch between rungs is exactly S everywhere
    x0 = -(n - 1) * S / 2.0
    for i in range(n):
        parts.append(_box(f"rung {i + 1}/{n}", rw, W, rt, x0 + i * S, 0.0, t))
    return parts


def _strut_channel(v: Dict[str, float]) -> List[Dict[str, Any]]:
    """A strut channel straight length: the back, two webs and the two inturned
    lips of the standard C section -- and, when a slot spacing is given, the
    back is authored as the segments BETWEEN the slots, so the slots are
    really absent rather than drawn on."""
    H = float(v["height_in"]) * IN
    Wd = float(v["width_in"]) * IN
    L = float(v["length_ft"])
    g = float(v["thickness_in"]) * IN
    lip = float(v["lip_in"]) * IN
    slot_l = float(v["slot_length_in"]) * IN
    slot_s = float(v["slot_spacing_in"]) * IN
    if H <= 2 * g or Wd <= 2 * g or L <= 0:
        raise ArchetypeError("a strut channel needs a section larger than twice its "
                             "material thickness and a positive length")
    # each lip starts INSIDE its web, so the web material counts twice as well:
    # 2*(lip + g) is what actually has to fit across the section
    if 2.0 * (lip + g) >= Wd:
        raise ArchetypeError(f"inturned lips ({lip / IN:g} in each, behind {g / IN:g} in "
                             f"webs) do not fit across a {Wd / IN:g} in channel")
    parts: List[Dict[str, Any]] = []
    if (slot_l > 0) != (slot_s > 0):
        raise ArchetypeError(
            "a slotted back needs BOTH a slot length and a slot spacing; one "
            f"without the other would report a slot the geometry does not have "
            f"(got length={slot_l / IN:g} in, spacing={slot_s / IN:g} in)")
    if slot_l > 0 and slot_s > 0 and slot_l >= slot_s:
        raise ArchetypeError(
            f"a {slot_l / IN:g} in slot cannot repeat every {slot_s / IN:g} in -- the "
            f"slots would run into each other, leaving no back material between them")
    if slot_s > 0 and slot_l > 0 and slot_l < slot_s:
        n = max(1, int(math.floor(L / slot_s + 1e-9)))
        if n + 5 > MAX_PARTS:                    # + the webs and lips still to come
            raise ArchetypeError(
                f"{n} back segments at {slot_s / IN:g} in slot spacing over {L:g} ft is "
                f"past the {MAX_PARTS}-part budget for one family")
        pitch = L / n
        solid = pitch - slot_l
        if solid <= 0:
            raise ArchetypeError("the slot length leaves no material between slots")
        for i in range(n + 1):
            centre = -L / 2.0 + i * pitch
            lo = -L / 2.0 if i == 0 else centre - pitch / 2.0 + slot_l / 2.0
            hi = L / 2.0 if i == n else centre + pitch / 2.0 - slot_l / 2.0
            seg = hi - lo
            if seg <= 0:
                continue
            parts.append(_box(f"back segment {i + 1}/{n + 1}", seg, Wd, g,
                              (lo + hi) / 2.0, 0.0, 0.0))
    else:
        parts.append(_box("back", L, Wd, g, 0.0, 0.0, 0.0))
    for sign, side in ((1.0, "left"), (-1.0, "right")):
        y = sign * (Wd / 2.0 - g / 2.0)
        parts.append(_box(f"web {side}", L, g, H - g, 0.0, y, g))
        y_lip = sign * (Wd / 2.0 - g - lip / 2.0)
        parts.append(_box(f"inturned lip {side}", L, lip, g, 0.0, y_lip, H - g))
    return parts


def _wireway(v: Dict[str, float]) -> List[Dict[str, Any]]:
    """A lay-in wireway (square duct) straight section: bottom, two sides and
    the removable cover, at the sheet thickness -- an open-ended trough, which
    is what a straight section is."""
    W = float(v["width_in"]) * IN
    H = float(v["height_in"]) * IN
    L = float(v["length_ft"])
    g = float(v["thickness_in"]) * IN
    if W <= 2 * g or H <= 2 * g or L <= 0:
        raise ArchetypeError("a wireway needs a section larger than twice its sheet "
                             "thickness and a positive length")
    return [
        _box("bottom", L, W, g, 0.0, 0.0, 0.0),
        _box("side left", L, g, H - 2 * g, 0.0, (W - g) / 2.0, g),
        _box("side right", L, g, H - 2 * g, 0.0, -(W - g) / 2.0, g),
        _box("cover", L, W, g, 0.0, 0.0, H - g),
    ]


def _junction_box(v: Dict[str, float]) -> List[Dict[str, Any]]:
    """A screw-cover junction box: back, four walls and the cover."""
    W = float(v["width_in"]) * IN
    H = float(v["height_in"]) * IN
    D = float(v["depth_in"]) * IN
    g = float(v["thickness_in"]) * IN
    if W <= 2 * g or H <= 2 * g or D <= 2 * g:
        raise ArchetypeError("a junction box needs every dimension larger than twice "
                             "its sheet thickness")
    inner = D - 2 * g
    return [
        _box("back", W, H, g, 0.0, 0.0, 0.0),
        _box("wall top", W, g, inner, 0.0, (H - g) / 2.0, g),
        _box("wall bottom", W, g, inner, 0.0, -(H - g) / 2.0, g),
        _box("wall left", g, H - 2 * g, inner, (W - g) / 2.0, 0.0, g),
        _box("wall right", g, H - 2 * g, inner, -(W - g) / 2.0, 0.0, g),
        _box("cover", W, H, g, 0.0, 0.0, D - g),
    ]


def _lighting_control_panel(v: Dict[str, float]) -> List[Dict[str, Any]]:
    """A surface-mounted lighting control (relay) cabinet, UPRIGHT: the back
    sits on the mounting plane (y = 0), the cabinet projects toward -Y, and the
    height runs along Z from the bottom of the box -- so the family's Front
    elevation shows the door.  Parts: the back, four walls, the door, and a
    latch on the door's right edge."""
    W = float(v["width_in"]) * IN
    H = float(v["height_in"]) * IN
    D = float(v["depth_in"]) * IN
    g = float(v["thickness_in"]) * IN
    if W <= 2 * g or H <= 2 * g or D <= 2 * g:
        raise ArchetypeError("a lighting control panel needs every dimension larger than "
                             "twice its sheet thickness")
    inner = D - 2 * g
    y_mid = -(g + inner / 2.0)                   # centre of the walls' depth
    latch_w, latch_d, latch_h = 1.0 * IN, 0.75 * IN, 3.0 * IN
    return [
        _box("back", W, g, H, 0.0, -g / 2.0, 0.0),
        _box("wall top", W, inner, g, 0.0, y_mid, H - g),
        _box("wall bottom", W, inner, g, 0.0, y_mid, 0.0),
        _box("wall left", g, inner, H - 2 * g, -(W - g) / 2.0, y_mid, g),
        _box("wall right", g, inner, H - 2 * g, (W - g) / 2.0, y_mid, g),
        _box("door", W, g, H, 0.0, -(D - g / 2.0), 0.0),
        _box("door latch", latch_w, latch_d, latch_h,
             W / 2.0 - 2.0 * IN, -(D + latch_d / 2.0), H / 2.0 - latch_h / 2.0),
    ]


def _conduit(v: Dict[str, float]) -> List[Dict[str, Any]]:
    """A conduit straight run: one cylinder about the X axis at the conduit's
    outside diameter.  The BORE IS NOT MODELLED -- see ``limits``."""
    d = float(v["diameter_in"]) * IN
    L = float(v["length_ft"])
    if d <= 0 or L <= 0:
        raise ArchetypeError("a conduit run needs a positive diameter and length")
    return [{"shape": "cylinder_x", "name": "conduit run", "radius_ft": d / 2.0,
             "length_ft": L, "center": [0.0, 0.0], "base_z_ft": -d / 2.0}]


def _hex_nut(name: str, across_flats: float, height: float, cx: float, cy: float,
             base: float) -> Dict[str, Any]:
    """A hex nut as a hexagonal prism (the thread and the chamfers are not
    modelled), flats parallel to the strut so it reads square-on in plan."""
    r = across_flats / math.sqrt(3.0)              # centre to corner
    ring = [[r * math.cos(math.radians(a)), r * math.sin(math.radians(a))]
            for a in (0, 60, 120, 180, 240, 300)]
    ring.append(list(ring[0]))
    return {"shape": "polygon", "name": name, "vertices": ring,
            "height_ft": height, "center": [cx, cy], "base_z_ft": base}


def _trapeze_geometry(v: Dict[str, float]) -> Dict[str, float]:
    """The derived numbers of a trapeze, in FEET -- shared by the builder and
    the family parameters so the two can never disagree."""
    L = float(v["strut_length_in"]) * IN
    inset = float(v["rod_inset_in"]) * IN
    n = int(round(float(v["tiers"])))
    t = float(v["tier_spacing_in"]) * IN
    H = float(v["height_in"]) * IN
    d = float(v["rod_diameter_in"]) * IN
    wt = float(v["washer_thickness_in"]) * IN
    nut_h = 0.875 * d
    spacing = float(v["rod_spacing_in"]) * IN
    top = (n - 1) * t + H                            # top of the top tier's lips
    rod_top = top + float(v["rod_above_in"]) * IN
    rod_bottom = -(wt + nut_h + float(v["rod_below_in"]) * IN)
    return {"L": L, "inset": inset, "n": n, "t": t, "H": H, "d": d, "wt": wt,
            "nut_h": nut_h, "nut_af": 1.5 * d, "spacing": spacing, "top": top,
            "rod_top": rod_top, "rod_bottom": rod_bottom,
            "rod_length": rod_top - rod_bottom}


def _strut_trapeze(v: Dict[str, float]) -> List[Dict[str, Any]]:
    """A strut TRAPEZE hanger: ``tiers`` lengths of channel, open side up, hung
    on two vertical threaded rods, each tier clamped at each rod by a square
    washer and a hex nut BELOW the channel back and a washer and nut ON the
    lips.  The insertion point is the underside of the bottom tier's channel,
    midway between the rods."""
    g = _trapeze_geometry(v)
    if not (1 <= g["n"] <= 6) or abs(float(v["tiers"]) - g["n"]) > 1e-9:
        raise ArchetypeError(f"a trapeze takes 1 to 6 whole tiers, not {float(v['tiers']):g}")
    if g["d"] <= 0:
        raise ArchetypeError("a trapeze needs a positive rod diameter")
    if abs(g["L"] - 2.0 * g["inset"] - g["spacing"]) > 1e-6:
        raise ArchetypeError(
            f"a {g['L'] / IN:g} in strut with rods {g['spacing'] / IN:g} in apart cannot "
            f"also have them {g['inset'] / IN:g} in in from each end -- state two of the three")
    if g["spacing"] <= max(g["nut_af"], float(v["washer_size_in"]) * IN):
        raise ArchetypeError(
            f"rods {g['inset'] / IN:g} in in from each end of a {g['L'] / IN:g} in "
            f"strut leave no room between them for their washers")
    if g["inset"] < float(v["washer_size_in"]) * IN / 2.0:
        raise ArchetypeError(
            f"a {g['inset'] / IN:g} in rod inset puts the "
            f"{float(v['washer_size_in']):g} in washer past the end of the strut")
    if g["n"] > 1 and g["t"] <= g["H"] + 2.0 * (g["wt"] + g["nut_h"]):
        raise ArchetypeError(
            f"{float(v['tier_spacing_in']):g} in between tiers does not clear one "
            f"channel and its nuts and washers")
    if g["d"] >= float(v["width_in"]) * IN:
        raise ArchetypeError("the rod is wider than the channel it passes through")
    chan = {k: v[k] for k in ("height_in", "width_in", "thickness_in", "lip_in",
                              "slot_length_in", "slot_spacing_in")}
    chan["length_ft"] = g["L"]
    one_tier = _strut_channel(chan)
    ws = float(v["washer_size_in"]) * IN
    parts: List[Dict[str, Any]] = []
    for i in range(g["n"]):
        z0 = i * g["t"]
        tier = f"tier {i + 1}"
        for p in one_tier:
            q = dict(p)
            q["name"] = f"{tier} {p['name']}"
            q["base_z_ft"] = float(p.get("base_z_ft") or 0.0) + z0
            parts.append(q)
        for side, x in (("left", -g["spacing"] / 2.0), ("right", g["spacing"] / 2.0)):
            below_w = z0 - g["wt"]
            parts.append(_box(f"{tier} washer below {side}", ws, ws, g["wt"], x, 0.0, below_w))
            parts.append(_hex_nut(f"{tier} nut below {side}", g["nut_af"], g["nut_h"],
                                  x, 0.0, below_w - g["nut_h"]))
            above = z0 + g["H"]
            parts.append(_box(f"{tier} washer above {side}", ws, ws, g["wt"], x, 0.0, above))
            parts.append(_hex_nut(f"{tier} nut above {side}", g["nut_af"], g["nut_h"],
                                  x, 0.0, above + g["wt"]))
    for side, x in (("left", -g["spacing"] / 2.0), ("right", g["spacing"] / 2.0)):
        parts.append({"shape": "cylinder", "name": f"threaded rod {side}",
                      "radius_ft": g["d"] / 2.0, "height_ft": g["rod_length"],
                      "center": [x, 0.0], "base_z_ft": g["rod_bottom"]})
    if len(parts) > MAX_PARTS:
        raise ArchetypeError(f"{len(parts)} parts is past the {MAX_PARTS}-part budget "
                             f"for one family")
    return parts


def _trapeze_params(v: Dict[str, float]) -> Dict[str, Any]:
    """Every dimension a user adjusts on a trapeze, as a family parameter (feet
    internally for lengths), plus the derived ones a schedule wants."""
    g = _trapeze_geometry(v)
    ft = lambda key: float(v[key]) * IN            # noqa: E731
    return {
        "Number of Tiers": ("integer", g["n"]),
        "Strut Length": ("length", g["L"]),
        "Rod Spacing": ("length", g["spacing"]),
        "Rod Inset": ("length", g["inset"]),
        "Tier Spacing": ("length", g["t"]),
        "Rod Diameter": ("length", g["d"]),
        "Rod Length": ("length", g["rod_length"]),
        "Rod Above Top Tier": ("length", ft("rod_above_in")),
        "Rod Below Bottom Nut": ("length", ft("rod_below_in")),
        "Strut Height": ("length", g["H"]),
        "Strut Width": ("length", ft("width_in")),
        "Strut Thickness": ("length", ft("thickness_in")),
        "Slot Length": ("length", ft("slot_length_in")),
        "Slot Spacing": ("length", ft("slot_spacing_in")),
        "Washer Size": ("length", ft("washer_size_in")),
        "Washer Thickness": ("length", g["wt"]),
        "Nut Across Flats": ("length", g["nut_af"]),
    }


def _trapeze_settle(vals: Dict[str, float], prov: Dict[str, str],
                    quoted: Dict[str, str]) -> None:
    """Strut length = rod spacing + 2 x rod inset, whichever two the caller
    stated.  A value the caller's numbers decided is ``given``, with the reason
    quoted; with none of the three stated all stay nominal."""
    L, S, I = "strut_length_in", "rod_spacing_in", "rod_inset_in"
    g = {k: prov.get(k) == GIVEN for k in (L, S, I)}
    if g[S] and not g[L]:
        vals[L] = vals[S] + 2.0 * vals[I]
        prov[L] = GIVEN
        quoted[L] = f"rod spacing {vals[S]:g} in + 2 x {vals[I]:g} in inset"
    elif g[S] and g[L] and not g[I]:
        vals[I] = (vals[L] - vals[S]) / 2.0
        prov[I] = GIVEN
        quoted[I] = f"({vals[L]:g} in strut - {vals[S]:g} in rod spacing) / 2"
    elif not g[S]:
        vals[S] = vals[L] - 2.0 * vals[I]
        if g[L] or g[I]:
            prov[S] = GIVEN
            quoted[S] = f"{vals[L]:g} in strut - 2 x {vals[I]:g} in inset"


# ---------------------------------------------------------------------------
# THE REGISTRY.  One entry + one builder = one more product.
# ---------------------------------------------------------------------------

_TRAY_WIDTHS = (6.0, 9.0, 12.0, 18.0, 24.0, 30.0, 36.0)
_TRAY_DEPTHS = (3.0, 4.0, 5.0, 6.0)
_TRAY_RUNGS = (6.0, 9.0, 12.0, 18.0)
_TRAY_LENGTHS = (10.0, 12.0, 20.0, 24.0)

ARCHETYPES: Dict[str, Archetype] = {}


def _register(a: Archetype) -> Archetype:
    ARCHETYPES[a.key] = a
    return a


_register(Archetype(
    key="cable_tray",
    title="Cable Tray - Ladder",
    category="cable_tray_fitting",
    basis=("standard ladder cable tray practice (the NEMA VE 1 family of widths, "
           "loading depths and rung spacings). Nominal sizes for the product "
           "CLASS -- no manufacturer's catalog record is claimed or implied"),
    lod_note=("two side rails, each a channel with its flanges turned inward, plus "
              "a rung at every standard spacing -- the real parts, not a box"),
    limits=("a loadable family in Cable Tray Fittings: Revit's drawable Cable Trays "
            "element is a SYSTEM family and generates its own straight-run geometry "
            "(issue #608), so this section is placed, not routed",
            "splice plates, hold-down clamps and grounding lugs are not modelled"),
    aliases=("ladder tray", "cable ladder"),
    patterns=(r"cable\s+trays?", r"cable\s+ladders?", r"ladder\s+trays?",
              r"\btrays?\b(?!\s*(?:ceil|table))"),
    params=(
        Param("width_in", "Width", 12.0, "in",
              "standard ladder tray usable widths 6 / 9 / 12 / 18 / 24 / 30 / 36 in; "
              "12 in is the common branch-run size",
              aliases=("wide", "width"), choices=_TRAY_WIDTHS, primary=True),
        Param("depth_in", "Loading Depth", 4.0, "in",
              "standard loading depths 3 / 4 / 5 / 6 in",
              aliases=("loading depth", "deep", "depth", "rail height"),
              choices=_TRAY_DEPTHS),
        Param("length_ft", "Length", 10.0, "ft",
              "standard straight-section lengths 10 / 12 / 20 / 24 ft",
              aliases=("long", "length"), choices=_TRAY_LENGTHS),
        Param("rung_spacing_in", "Rung Spacing", 12.0, "in",
              "standard rung spacings 6 / 9 / 12 / 18 in",
              aliases=("rung spacing", "rung pitch", "rung centers", "rung centres"),
              choices=_TRAY_RUNGS),
        Param("rail_thickness_in", "Rail Thickness", 0.1, "in",
              "sheet-steel side rail in the 12-gauge range (0.105 in)",
              aliases=("rail thickness",)),
        Param("rail_flange_in", "Rail Flange", 0.875, "in",
              "inward flange of the side-rail channel",
              aliases=("rail flange", "flange")),
        Param("rung_width_in", "Rung Width", 1.0, "in",
              "rung width along the run",
              aliases=("rung width",)),
        Param("rung_thickness_in", "Rung Thickness", 0.1, "in",
              "rung material in the 12-gauge range",
              aliases=("rung thickness",)),
    ),
    build=_ladder_tray,
    standard_values=lambda v: {
        "Tray Width": float(v["width_in"]) * IN,
        "Tray Height": float(v["depth_in"]) * IN,
        "Tray Type": "ladder",
    },
))


_register(Archetype(
    key="strut_channel",
    title="Strut Channel",
    category="generic_model",
    basis=("standard 1-5/8 in metal framing channel practice (the 1-5/8 x 1-5/8 in "
           "section in the 12-gauge range with inturned lips). Nominal sizes for "
           "the product CLASS -- no manufacturer's part is claimed"),
    lod_note=("the back, two webs and the two inturned lips of the real C section; "
              "with a slot spacing the back is authored as the material BETWEEN the "
              "slots, so the slots are genuinely absent"),
    limits=("hole patterns other than the back slots are not modelled",
            "the section is authored square-cornered; the forming radii are not"),
    aliases=("unistrut", "metal framing channel", "strut"),
    patterns=(r"strut\s+channels?", r"\bstruts?\b", r"metal\s+framing\s+channels?",
              r"channel\s+framing", r"\bunistruts?\b"),
    params=(
        Param("height_in", "Section Height", 1.625, "in",
              "the 1-5/8 in standard channel height",
              aliases=("tall", "height", "section height"), primary=True),
        Param("width_in", "Section Width", 1.625, "in",
              "the 1-5/8 in standard channel width",
              aliases=("wide", "width", "section width"), follows="height_in"),
        Param("length_ft", "Length", 10.0, "ft",
              "standard stock lengths 10 / 20 ft",
              aliases=("long", "length"), choices=(10.0, 20.0)),
        Param("thickness_in", "Material Thickness", 0.105, "in",
              "12 gauge (0.105 in), the common structural weight",
              aliases=("thickness", "gauge material")),
        Param("lip_in", "Lip", 0.5, "in",
              "the inturned lip that the channel nut turns against",
              aliases=("lip",)),
        Param("slot_length_in", "Slot Length", 0.0, "in",
              "0 = a solid back; a slotted back uses the standard 1-1/8 in slot",
              aliases=("slot length",), allow_zero=True),
        Param("slot_spacing_in", "Slot Spacing", 0.0, "in",
              "0 = a solid back; the standard slotted pattern is on 2 in centres",
              aliases=("slot spacing", "slot centers", "slot centres"), allow_zero=True),
    ),
    build=_strut_channel,
    standard_values=lambda v: {"Material": "steel"},
))


_register(Archetype(
    key="wireway",
    title="Wireway - Lay-In",
    category="electrical_equipment",
    basis=("standard lay-in wireway (square duct) practice: square sections at "
           "4 / 6 / 8 / 12 in in the 16-gauge range. Nominal sizes for the product "
           "CLASS -- no manufacturer's catalog record is claimed"),
    lod_note="bottom, two sides and the removable cover -- an open-ended trough",
    limits=("knockouts, the hinge and the cover screws are not modelled",
            "an NEMA enclosure rating is a parameter slot, not a claim"),
    aliases=("square duct", "auxiliary gutter", "lay-in wireway"),
    patterns=(r"wire\s*ways?", r"square\s+ducts?", r"auxiliary\s+gutters?"),
    params=(
        Param("width_in", "Width", 6.0, "in",
              "standard square wireway sections 4 / 6 / 8 / 12 in",
              aliases=("wide", "width"), choices=(4.0, 6.0, 8.0, 12.0), primary=True),
        Param("height_in", "Height", 6.0, "in",
              "square section: the height matches the width",
              aliases=("tall", "height"), choices=(4.0, 6.0, 8.0, 12.0),
              follows="width_in"),
        Param("length_ft", "Length", 5.0, "ft",
              "standard section lengths 1 / 2 / 3 / 4 / 5 ft",
              aliases=("long", "length"), choices=(1.0, 2.0, 3.0, 4.0, 5.0)),
        Param("thickness_in", "Sheet Thickness", 0.06, "in",
              "16 gauge (0.0598 in), the common wireway sheet",
              aliases=("thickness", "sheet thickness")),
    ),
    build=_wireway,
    standard_values=lambda v: {"Mounting": "surface", "Material": "steel"},
))


_register(Archetype(
    key="lighting_control_panel",
    title="Lighting Control Panel - Surface",
    category="electrical_equipment",
    basis=("a surface-mounted lighting control (relay) cabinet sized like a standard "
           "20 in panelboard cabinet box, its height set by the relay count. Nominal "
           "sizes for the product CLASS -- no manufacturer's catalog record is claimed"),
    lod_note="the back, four walls, the door and its latch -- the cabinet, upright",
    limits=("the relays, the low-voltage section, the barrier and the knockouts are "
            "not modelled -- the interior is empty",
            "the door is a solid panel, not a hinged, openable one",
            "an NEMA enclosure rating is a parameter slot, not a claim"),
    aliases=("lighting relay panel",),
    # Only names that mean THIS product.  A bare "relay panel" is as often a
    # generator or protective relay panel, and "LCP" in HVAC is a LOCAL control
    # panel -- matching them built a lighting control panel for "a generator
    # relay panel" and "an AHU with an LCP" (#821 review).  Those stay with
    # whatever main does, rather than being answered with a guessed product.
    patterns=(r"lighting\s+control\s+panels?", r"lighting\s+relay\s+panels?"),
    params=(
        Param("width_in", "Width", 20.0, "in",
              "the standard 20 in panelboard-width cabinet; 24 in for wider panels",
              aliases=("wide", "width"), choices=(20.0, 24.0), primary=True),
        Param("height_in", "Height", 30.0, "in",
              "cabinet heights in 6 in steps with the relay count",
              aliases=("tall", "high", "height"), choices=(24.0, 30.0, 36.0, 42.0, 48.0)),
        Param("depth_in", "Depth", 6.0, "in",
              "surface cabinet depths 4 / 6 in",
              aliases=("deep", "depth"), choices=(4.0, 6.0)),
        Param("thickness_in", "Sheet Thickness", 0.075, "in",
              "14 gauge (0.0747 in), a common cabinet sheet",
              aliases=("thickness", "sheet thickness")),
    ),
    build=_lighting_control_panel,
    standard_values=lambda v: {"Mounting": "surface", "Material": "steel"},
    working_space=True,
))


_register(Archetype(
    key="junction_box",
    title="Junction Box - Screw Cover",
    category="electrical_fixture",
    basis=("standard screw-cover junction box practice: square sizes 4 / 6 / 8 / 12 in "
           "in the 16-gauge range. Nominal sizes for the product CLASS"),
    lod_note="the back, four walls and the screw cover",
    limits=("knockouts and the cover screws are not modelled",
            "an NEMA enclosure rating is a parameter slot, not a claim"),
    aliases=("pull box", "j-box"),
    patterns=(r"junction\s+box(?:es)?", r"pull\s+box(?:es)?", r"\bj-?\s*box(?:es)?\b"),
    params=(
        Param("width_in", "Width", 6.0, "in",
              "standard square box sizes 4 / 6 / 8 / 12 in",
              aliases=("wide", "width"), choices=(4.0, 6.0, 8.0, 12.0), primary=True),
        Param("height_in", "Height", 6.0, "in",
              "square box: the height matches the width",
              aliases=("tall", "height"), choices=(4.0, 6.0, 8.0, 12.0),
              follows="width_in"),
        Param("depth_in", "Depth", 4.0, "in",
              "standard box depths 4 / 6 in",
              aliases=("deep", "depth"), choices=(4.0, 6.0)),
        Param("thickness_in", "Sheet Thickness", 0.06, "in",
              "16 gauge (0.0598 in)",
              aliases=("thickness", "sheet thickness")),
    ),
    build=_junction_box,
    standard_values=lambda v: {"Device Type": "junction box", "Mounting": "surface"},
))


_register(Archetype(
    key="conduit",
    title="Conduit - Straight Run",
    category="conduit_fitting",
    basis=("standard conduit trade sizes 1/2 to 4 in. The run is modelled at the "
           "TRADE SIZE as its outside diameter: the true outside diameter per the "
           "conduit standard differs slightly by type and is not held in this repo, "
           "so pass diameter_in to set it exactly"),
    lod_note="one cylinder about the run axis at the conduit's outside diameter",
    limits=("THE BORE IS NOT MODELLED: the writer has no void or boolean, so the run "
            "is a solid rod at the outside diameter, not a tube",
            "couplings, straps and the wall thickness are not modelled"),
    aliases=("EMT", "raceway", "rigid conduit"),
    patterns=(r"conduits?", r"\bemt\b", r"racew?ays?", r"rigid\s+metal\s+conduits?"),
    params=(
        Param("diameter_in", "Outside Diameter", 0.75, "in",
              "trade sizes 1/2 / 3/4 / 1 / 1-1/4 / 1-1/2 / 2 / 2-1/2 / 3 / 4 in",
              aliases=("diameter", "trade size", "dia"),
              choices=(0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 2.5, 3.0, 4.0), primary=True),
        Param("length_ft", "Length", 10.0, "ft",
              "standard stock length 10 ft",
              aliases=("long", "length"), choices=(10.0,)),
    ),
    build=_conduit,
    standard_values=lambda v: {"Nominal Diameter": float(v["diameter_in"]) * IN,
                               "Material": "steel"},
))


_register(Archetype(
    key="strut_trapeze",
    title="Strut Trapeze",
    category="generic_model",
    basis=("standard trapeze hanger practice: 1-5/8 in metal framing channel, open "
           "side up, hung on two all-thread rods with a square washer and hex nut "
           "above and below each tier. Nominal sizes for the product CLASS -- no "
           "manufacturer's part is claimed"),
    lod_note=("every tier's real C section (back, webs, inturned lips, the back "
              "slots genuinely absent), both threaded rods full length, and a "
              "square washer + hex nut above and below each tier at each rod"),
    limits=("the rod threads and the nut chamfers are not modelled; a rod is a "
            "plain cylinder at its nominal diameter",
            "the rod holes are not cut: the rod passes through the channel back",
            "the beam clamp / anchor at the rod top is not modelled",
            "the section is authored square-cornered; the forming radii are not",
            "PARAMETERS CARRY VALUES, THEY DO NOT YET DRIVE THE GEOMETRY: editing "
            "Strut Length or Tier Spacing in Revit does not move the solids (the "
            "parametric drive has no desktop verdict, #372 / #787) -- a different "
            "size is a re-generation with the new numbers"),
    aliases=("trapeze", "trapeze hanger", "strut trapeze", "unistrut trapeze"),
    patterns=(r"(?:(?:strut|unistrut|channel|slotted)\s+)*trapezes?"
              r"(?:\s+(?:hangers?|supports?|racks?))?",
              r"trapeze\s+hangers?"),
    params=(
        Param("strut_length_in", "Strut Length", 30.0, "in",
              "a 30 in strut: 24 in between rods with the rods 3 in in from each end",
              aliases=("long", "length", "strut length", "trapeze length",
                       "trapeze width"),
              choices=(18.0, 24.0, 30.0, 36.0, 42.0, 48.0), primary=True,
              minimum=6.0, maximum=240.0),
        Param("tiers", "Number of Tiers", 2.0, "count",
              "two tiers, as asked for most often; 1 to 6",
              aliases=("tier", "tiers", "level", "levels", "tier trapeze"),
              choices=(1.0, 2.0, 3.0, 4.0), maximum=6.0),
        Param("tier_spacing_in", "Tier Spacing", 12.0, "in",
              "12 in between tiers, centre to centre",
              aliases=("tier spacing", "tier to tier"),
              choices=(8.0, 10.0, 12.0, 18.0, 24.0), maximum=120.0),
        Param("rod_spacing_in", "Rod Spacing", 24.0, "in",
              "rod centres 24 in apart: the strut length less the two insets",
              # NOT bare "apart" / "on center": "tiers 12 in apart" is the
              # TIER spacing (#900 review round 3)
              aliases=("rod spacing", "rod centers", "rod centres", "between rods",
                       "rods apart"),
              minimum=1.0, maximum=228.0),
        Param("rod_inset_in", "Rod Inset", 3.0, "in",
              "the rod 3 in in from each end of the strut",
              aliases=("rod inset", "overhang", "rod from end"), maximum=24.0),
        Param("rod_diameter_in", "Rod Diameter", 0.375, "in",
              "3/8 in all-thread, the common trapeze rod; 1/2, 5/8 and 3/4 in for "
              "heavier loads",
              aliases=("rod", "rod diameter", "threaded rod", "all thread",
                       "all-thread", "rod size"),
              # "24 in rod spacing" / "rod inset" are LONGER aliases of other
              # dimensions and claim their text first; the range keeps a
              # following number ("1/2 in rod 24 in apart") off the diameter
              choices=(0.375, 0.5, 0.625, 0.75), maximum=1.5),
        Param("rod_above_in", "Rod Above Top Tier", 24.0, "in",
              "24 in of rod above the top tier, up to the structure",
              aliases=("rod above", "rod drop", "to structure"), maximum=480.0),
        Param("rod_below_in", "Rod Below Bottom Nut", 1.0, "in",
              "1 in of rod left below the bottom nut",
              aliases=("rod below", "rod tail"), maximum=12.0),
        Param("height_in", "Strut Height", 1.625, "in",
              "the 1-5/8 in standard channel height",
              aliases=("strut height", "channel height", "section height"),
              maximum=4.0),
        Param("width_in", "Strut Width", 1.625, "in",
              "the 1-5/8 in standard channel width",
              aliases=("strut width", "channel width", "section width"),
              maximum=4.0),
        Param("thickness_in", "Strut Thickness", 0.105, "in",
              "12 gauge (0.105 in), the common structural weight",
              aliases=("thickness", "strut thickness")),
        Param("lip_in", "Lip", 0.5, "in",
              "the inturned lip that the channel nut turns against",
              aliases=("lip",)),
        Param("slot_length_in", "Slot Length", 1.125, "in",
              "the standard 1-1/8 in slot; 0 = a solid back",
              aliases=("slot length",), allow_zero=True),
        Param("slot_spacing_in", "Slot Spacing", 2.0, "in",
              "slots on 2 in centres; 0 = a solid back",
              aliases=("slot spacing", "slot centers", "slot centres"), allow_zero=True),
        Param("washer_size_in", "Washer Size", 1.625, "in",
              "the 1-5/8 in square strut washer",
              aliases=("washer size",)),
        Param("washer_thickness_in", "Washer Thickness", 0.25, "in",
              "a 1/4 in thick square washer",
              aliases=("washer thickness",)),
    ),
    build=_strut_trapeze,
    family_params=_trapeze_params,
    settle=_trapeze_settle,
    noun_leads=(("strut", "height_in"), ("channel", "height_in"),
                ("unistrut", "height_in")),
    name_bits=lambda v: [f"{int(round(float(v['tiers'])))} Tier"],
    standard_values=lambda v: {"Material": "steel"},
))


def keys() -> Tuple[str, ...]:
    return tuple(sorted(ARCHETYPES))


def archetype(product: str) -> Archetype:
    key = str(product).lower().strip().replace(" ", "_").replace("-", "_")
    a = ARCHETYPES.get(key)
    if a is None:
        raise ArchetypeError(
            f"no archetype for {product!r}. Generated products today: "
            + ", ".join(keys())
            + ". Anything else needs its geometry supplied (a famspec's 'parts', "
              "an IFC body) or catalog facts -- nothing is invented from a name alone.")
    return a


# ---------------------------------------------------------------------------
# reading a request out of a prompt
# ---------------------------------------------------------------------------

#: A NUMBER THE CALLER WROTE AS A NUMBER.  The left lookbehind is load-bearing:
#: without it the digits INSIDE a token became a dimension, so "an IP65 junction
#: box" was read as a 65-inch box, "a Unistrut P1000 strut" as an 83-foot
#: section and "a 480Y/277 wireway" as 277 in -- each reported `given` and
#: quoted back with words the caller never used as a measurement, which is the
#: provenance contract lying about itself.
_NUM_CORE = (r"(\d+\s+\d+/\d+"                            # 2 1/2 -- mixed, spaced
             r"|\d{1,3}(?:,\d{3})+(?:\.\d+)?"              # 1,200 -- grouped
             r"|\d+(?:\.\d+)?(?:\s*[-/]\s*\d+(?:/\d+)?)?"
             r"|\d+\s*/\s*\d+)")
#: the comma in the class matters: without it "a 1,200 mm cable tray" matched
#: the "200" and delivered a 7.9 in tray, quoted back as '200 mm cable tray'.
#: ... and the lookbehind excludes a preceding DIGIT+SPACE too, or "2 1/2 in"
#: matched its trailing "1/2" alone and delivered a conduit 5x too small.
_NUM = r"(?<![A-Za-z0-9.,/-])(?<!\d )" + _NUM_CORE

#: what may sit between a number, its unit and the word it qualifies.  English
#: hyphenates these -- "a 24-inch-wide tray", "a 6-in-deep tray", "a 10-ft-long
#: run" -- and a bare \s* dropped every one of those dimensions on the floor
#: while reporting the value as NOMINAL, i.e. "we generated it".
_SEP = r"[\s-]*"
_UNITS = {
    "in": r"(?:in\b|in\.|inch(?:es)?\b|\")",
    "ft": r"(?:ft\b|ft\.|foot\b|feet\b|')",
    "mm": r"(?:mm\b|millimet(?:er|re)s?\b)",
}
_ANY_UNIT = "|".join(_UNITS.values())


def _to_number(raw: str) -> Optional[float]:
    """'24' / '1.5' / '1-5/8' / '1 5/8' / '3/4' / '13/16' / '1,200' -> a float;
    None when it is not one."""
    s = re.sub(r"\s+", " ", str(raw).strip())
    # A mixed number needs a SEPARATOR -- a hyphen or a space -- between the
    # whole part and the fraction.  This used to strip every space first, which
    # made "1 3/16" and "13/16" the same string; the mixed reading ran first, so
    # a 13/16 in strut was read as 1 3/16 in and stamped ``given`` (#831).
    m = re.fullmatch(r"(\d+)(?: ?- ?| )(\d+) ?/ ?(\d+)", s)
    if m:
        den = float(m.group(3))
        return float(m.group(1)) + float(m.group(2)) / den if den else None
    m = re.fullmatch(r"(\d+) ?/ ?(\d+)", s)
    if m:
        den = float(m.group(2))
        # "3/0" and "4/0" are everyday AWG sizes for this product class, and a
        # ZeroDivisionError here escaped ArchetypeError, crashed the route and
        # WITHHELD THE FILE -- a hard rule 1 violation caused by a parser.
        return float(m.group(1)) / den if den else None
    # '1,200' is one thousand two hundred -- only as digit grouping
    m = re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?", s)
    return float(m.group(0).replace(",", "")) if m else None


def _convert(value: float, unit_found: str, p: Param) -> Optional[float]:
    """A number the prompt gave in ``unit_found`` expressed in the parameter's
    own unit.  A unit the parameter cannot mean (feet for a sheet thickness is
    fine; there is no rule against it) simply converts.  A COUNT takes a bare
    number only ("2 tier"); "2 in tiers" is not a count."""
    if p.unit == "count":
        # a whole number only: "2 tier 1-5/8 strut" must not read 1.625 tiers
        if unit_found != "count" or abs(value - round(value)) > 1e-9:
            return None
        return value
    ft = {"in": value * IN, "ft": value, "mm": value * MM}.get(unit_found)
    if ft is None:
        return None
    if p.unit == "in":
        return ft / IN
    if p.unit == "ft":
        return ft
    return value


def _unit_of(text: str) -> Optional[str]:
    low = text.lower()
    for key, pat in _UNITS.items():
        if re.search(pat, low):
            return key
    return None


# ---------------------------------------------------------------------------
# THE MANUFACTURER GUARD -- steer #591's "Still refused"
# ---------------------------------------------------------------------------

#: phrasings that name a specific catalog item.  TWO guards, both learned the
#: hard way: the keyword needs a WORD BOUNDARY (without it "partition" gave
#: 'ition', "catwalk" gave 'walk' and every honest delivery got the loudest
#: line in the product), and the token must contain a DIGIT (without it "generic
#: model family" read 'family' as a part number).  A designator without a digit
#: is a word, not a catalogue number.
_PART_PHRASE = re.compile(
    r"\b(?:part|catalog|catalogue|cat|model|item|sku|p/?n)\b\.?\s*"
    r"(?:numbers?|nos?\.?|#)?\s*[:#]?\s*"
    r"(?P<tok>(?=[A-Za-z0-9./-]*\d)[A-Za-z0-9][A-Za-z0-9./-]{2,})", re.I)

#: a bare token SHAPED like a part number: letters AND digits, with a separator,
#: e.g. 24A-09-120, B22SH-12-120.  Deliberately narrow -- '1-5/8', '12x12',
#: '480Y/277' and '2x4' must NOT trip it, so a separator plus both a letter and
#: a digit outside any fraction is required.
_PART_TOKEN = re.compile(r"\b(?=[A-Za-z0-9./-]*[A-Za-z])(?=[A-Za-z0-9./-]*\d)"
                         r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+){2,}\b")

#: words that make a hyphenated token a MEASUREMENT, not a catalogue number.
#: "6-in-deep", "12-inch-wide", "10-ft-long", "24-inch-wide" all fit the
#: separator-bearing part-number shape exactly -- and hyphenated measurement
#: adjectives are the commonest phrasing in this product's own domain, so
#: firing on them put the loudest line in the product on the most ordinary
#: request there is.
_UNIT_WORDS = frozenset("""
in inch inches ft foot feet mm cm m yd
wide width long length deep depth tall high height thick thickness
gang gangs pole poles way ways phase ph circuit circuits
awg mcm kcmil gauge ga
degree degrees deg
nema ul iec ip class div division type rated rating listed zone group
""".split())

#: a bare catalogue designator with NO separator -- 'F66L120', '2BLT4'.  Needs
#: at least two letters AND two digits and five characters, which is what keeps
#: 'Cat6A', '480Y', '12x12', '120V' and '2x4' out of it.  A one-letter
#: designator like Unistrut's 'P1000' is BELOW this bar and is not caught: a
#: stated gap, not a silent one.
_PART_BARE = re.compile(r"\b(?=(?:[A-Za-z]*\d){2})(?=(?:\d*[A-Za-z]){2})"
                        r"[A-Za-z0-9]{5,}\b")

#: the brand names OUR catalog actually resolves, plus the containment brands
#: this repo's own records name.  Sourced, never a guessed brand list -- and
#: therefore INCOMPLETE by construction: a brand that is not here is caught only
#: if the prompt also carries part-number phrasing or a catalogue-shaped token.
#: "a Hoffman F66L120 wireway" fires on both the brand and F66L120.  A brand
#: absent from the list and carrying no designator -- and a one-letter
#: designator like Unistrut's P1000 on its own -- is NOT caught.  The guard reduces silent mis-identification; it does not
#: eliminate it, and no text in this repo should say otherwise.
_BRAND_HINTS = (
    # resolved by OUR catalog (rvt.famgen.catalog) -- these are sourced
    "eaton", "schneider electric", "schneider", "square d", "square-d",
    "lithonia", "acuity", "hammond", "hps",
    # common manufacturers of the products this registry generates.  A HINT
    # LIST, not a claim of coverage: it is hand-written, certainly incomplete,
    # and its only job is to raise a bare designator from "ambiguous" to "the
    # caller means a specific product".  A brand absent here is caught only by
    # part-number phrasing or a separator-bearing token.
    "b-line", "b line", "cooper", "unistrut", "cablofil", "hoffman", "panduit",
    "nvent", "thomas & betts", "superstrut", "chalfant", "mono-systems",
    "wiremold", "legrand", "atkore", "allied tube")


def manufacturer_claim(prompt: str) -> Optional[Dict[str, Any]]:
    """Does this prompt name a SPECIFIC manufacturer's item?

    Steer #591 draws the line here: generating a generic product at standard
    nominal sizes is honest, and "an Eaton B-Line 24 in tray, part number
    24A-09-120" *"must not silently become a generic nominal tray wearing that
    part number"*.  We hold no such record, so we cannot build it -- but hard
    rule 1 says never withhold output.  So the family is still delivered, and
    this is what makes the delivery not silent: the caller is told, in the
    status line and the report, that the named item is NOT what they received.

    Returns ``None`` when the prompt names no specific item, else
    ``{"tokens": [...], "brands": [...], "reasons": [...]}``.
    """
    text = str(prompt or "")
    low = text.lower()
    tokens: List[str] = []
    brands: List[str] = []
    reasons: List[str] = []
    for m in _PART_PHRASE.finditer(text):
        tok = m.group("tok")
        if tok.lower() in ("of", "is", "the", "a", "an"):
            continue
        tokens.append(tok)
        reasons.append(f"names a specific item: {m.group(0).strip()!r}")
    for m in _PART_TOKEN.finditer(text):
        tok = m.group(0)
        if any(g.lower() in _UNIT_WORDS for g in tok.split("-")):
            continue                              # a measurement, not a part number
        if tok not in tokens:
            tokens.append(tok)
            reasons.append(f"{tok!r} is shaped like a catalogue number")
    for b in _BRAND_HINTS:
        if re.search(rf"\b{re.escape(b)}\b", low):
            brands.append(b)
            reasons.append(f"names a manufacturer: {b!r}")
    # A BARE designator (no separators) is only a catalogue number when the
    # prompt ALSO names a manufacturer or uses part-number phrasing.  On its own
    # it is far more often ordinary electrical shorthand -- 12AWG, 500MCM,
    # 200A3P, THHN12, NFPA70, 480V3PH all fit "two letters and two digits", and
    # accusing the caller of naming a product because they specified a wire
    # gauge puts the loudest line in the product on an honest delivery.
    if brands or tokens:
        for m in _PART_BARE.finditer(text):
            if m.group(0) not in tokens:
                tokens.append(m.group(0))
                reasons.append(f"{m.group(0)!r} is shaped like a catalogue number "
                               f"and the prompt names a manufacturer")
    if not tokens and not brands:
        return None
    return {"tokens": tokens, "brands": sorted(set(brands)), "reasons": reasons,
            "line": (
                "YOU NAMED A SPECIFIC PRODUCT ("
                + ", ".join(sorted(set(brands)) + tokens)
                + ") AND THIS FILE IS NOT IT. tekton holds no catalog record for "
                  "it, and a generated family must never wear a manufacturer's "
                  "identity it cannot back: what you have is a GENERIC family at "
                  "standard nominal sizes for the product class, carrying no "
                  "manufacturer, model or part number. Give the real dimensions "
                  "and they are recorded as yours, or send the manufacturer's IFC "
                  "and they are measured from it.")}


def _alias_re(al: str) -> str:
    """The regex for one alias as written in a prompt (any run of whitespace
    between its words)."""
    return re.escape(al).replace(r"\ ", r"\s+")


#: a rating / classification word right before a number: the number belongs
#: to that scheme, not to the product's size ("a NEMA 12 wireway")
_RATING_LEAD = re.compile(r"\b(?:nema|ul|iec|ip|type|class|div|division|level|"
                          r"grid|zone|group|phase|pole)\s*$")
#: ... and for a UNIT-LESS number read number-first ("1 wide"), also a count:
#: "nema 1 width 6 in wide" and "qty 2 width 6 in wide" bound the 1 / 2 as the
#: width, because the redundant "6 in wide" then scored as a phrase left whole
#: (#828 round 6).  NOT "phase" or "pole" here: their count comes BEFORE them
#: ("3 phase 12 tall", "2 pole 30 tall"), so the number after one is a size --
#: listed here, they threw it away and let "follows" stamp another (round 7).
_NOT_A_SIZE_LEAD = re.compile(r"\b(?:nema|ul|iec|ip|type|class|div|division|level|grid|"
                              r"zone|group|qty|quantity|count)\s*[#:=]?\s*$")
#: ... and a designator, but only when the same parameter is stated again
#: later ("size 1 wide 6 in wide", "#2 width 6 wide"): alone, "a size 12
#: wide tray" is as likely a 12 in width, as main reads it.  "phase" and
#: "pole" belong HERE: "phase 12 thickness 6 in thickness" is a doubled label
#: (main: 6), while "3 phase 12 tall" states the height once.
_DESIGNATOR_LEAD = re.compile(r"(?:\b(?:size|model|no\.?|number|item|mark|tag|phase|pole)|#)"
                              r"\s*[#:=.]?\s*$")


def _alias_patterns(p: Param, *, alias_first: bool = True) -> List[Tuple[int, int, str]]:
    """``(alias length, rank, pattern)`` for every way a prompt states this
    parameter, built from its aliases.

    The LENGTH matters and is why this returns pairs: aliases nest -- ``length``
    sits inside ``slot length``, ``width`` inside ``section width``. Scanned in
    declaration order, the short one wins the region and the long one is then
    locked out, so "slot spacing 2 in and slot length 1.125 in" bound the
    channel's LENGTH to 1.125 in and left the slots off (a 1.1-inch channel
    reporting a slot spacing it does not have). :func:`resolve_prompt` sorts
    every candidate across ALL parameters longest-alias-first, so the most
    specific reading always claims its text first.

    Each alias has two phrasings: NUMBER-FIRST (``"24 in wide"``, rank 0) and
    ALIAS-FIRST (``"wide 24 in"``, rank 1).  ``alias_first`` chooses which of
    the pair is emitted first; the caller's stable sort by length keeps that
    order within one alias.  Neither order is right on its own (#812): a number
    standing between two aliases belongs to one phrase or the other, and each
    fixed order steals it in one of the two chains --

    * alias-first first reads "24 in wide 4 in deep" as ``wide 4 in`` (a 4 in
      tray stamped ``given``) and "... 20 ft long" as ``deep 20 ft`` (a 20-foot
      side rail);
    * number-first first reads "depth 6 in width 24 in" as ``6 in width``
      (``width_in`` is declared before ``depth_in``, so its pattern runs
      first) -- a 6 in tray, with depth left nominal.

    :func:`resolve_prompt` therefore binds under BOTH orders and keeps the
    reading that gives more stated dimensions a home.  A comma or "and" hid the
    first chain for a long time, because either one stops alias-first from
    matching across the phrase boundary (``_SEP`` allows no comma).
    """
    out: List[Tuple[int, int, str]] = []
    for al in p.aliases:
        a = _alias_re(al)
        n = len(al)
        # rank 0: "12 in rung spacing", "24-inch-wide", "10-ft-long"
        number_first = (n, 0, rf"{_NUM}{_SEP}(?P<u>{_ANY_UNIT})?{_SEP}{a}")
        # rank 1: "rung spacing of 12 in", "width 24 inches", "depth = 6 in"
        alias_led = (n, 1, rf"{a}{_SEP}(?:of|is|at|=|:)?{_SEP}{_NUM}{_SEP}(?P<u>{_ANY_UNIT})?")
        out.extend((alias_led, number_first) if alias_first else (number_first, alias_led))
    return out


def _product_patterns(a: Archetype) -> List[str]:
    return list(a.patterns) or [re.escape(a.key.replace("_", r"\s+"))]


def resolve_prompt(prompt: str, *, product: Optional[str] = None) -> Optional[Resolved]:
    """Read a prompt as an archetype request -- or return None when it names no
    product this registry generates.

    Every dimension the prompt states becomes ``given`` (with the words it came
    from quoted back); every dimension it does not state stays ``nominal``.
    """
    text = str(prompt or "")
    low = text.lower()
    arch: Optional[Archetype] = None
    if product:
        arch = archetype(product)
    else:
        best: Optional[Tuple[int, Archetype]] = None
        for a in ARCHETYPES.values():
            for pat in _product_patterns(a):
                m = re.search(pat, low)
                if m and (best is None or len(m.group(0)) > best[0]):
                    best = (len(m.group(0)), a)
        if best is None:
            return None
        arch = best[1]
    vals = arch.defaults()
    prov = {p.key: NOMINAL for p in arch.params}
    quoted: Dict[str, str] = {}
    used: List[Tuple[int, int]] = []

    def free(s: int, e: int) -> bool:
        return not any(s < ue and e > us for us, ue in used)

    # LONGEST ALIAS FIRST, across every parameter -- not parameter by parameter.
    # Aliases nest ('length' inside 'slot length'), and whoever matches first
    # locks the region, so the specific reading has to go first or the generic
    # one silently steals it (see _alias_patterns).
    #
    # Longest-first only protects a long alias's text while the long alias is
    # still BINDING.  Once its parameter is given, its later occurrences are
    # unclaimed, and a shorter alias nested inside one ('width' in 'rung
    # width', 'length' in 'slot length') would read a restated value as its
    # own: "1 in rung width, rung width 1 in" stamped a 1 in tray WIDTH given
    # (#828 review).  So every occurrence of every alias is recorded up front,
    # bound or not, and a shorter alias may never match inside a longer one.
    spans = [(m.start(), m.end(), len(al))
             for al in {al for p in arch.params for al in p.aliases}
             for m in re.finditer(_alias_re(al), low)]

    cross_dims = [k for k in ("width_in", "height_in", "depth_in")
                  if any(q.key == k for q in arch.params)]

    def opens_cross(m: "re.Match", rank: int, p: "Param", now: Dict[str, str],
                    any_alias: bool = False) -> bool:
        # "thickness 12 x 6 in wireway": an alias-first match whose UNITLESS
        # number is the first element of an "N x N" cross-dimension that the
        # cross rule below will read reads the cross's number as its own
        # (#828 round 3).  Each limit was a measured regression (rounds 4, 5):
        #  * the cross must RUN INTO THE NOUN -- the only cross that rule
        #    reads; "depth 6 in width 20 x 30 in" has none;
        #  * the alias must NOT itself be a cross dimension -- "width 20 x 30"
        #    labels 20, as main reads it;
        #  * the archetype must HAVE a cross rule and it must still be open
        #    (two cross dimensions, both nominal in this reading) -- conduit
        #    has none, so "trade size 3/4 x 10' EMT" lost its diameter;
        #  * the cross must not be in FEET -- a foot measurement after 'x' is
        #    a run length, never a section: "rung spacing 9 x 12 ft ladder
        #    tray" became a 108 x 144 in tray.
        # With a unit the phrase is complete and the 'x' is a separator
        # ("thickness 12.5 in x 9 ft long"); number-first phrases next to an
        # 'x' are left alone ("12 in wide x 4 in deep", "3 x 10 ft long").
        if rank != 1 or m.group("u") or (p.key in cross_dims and not any_alias):
            return False
        if len(cross_dims) < 2 or any(now.get(k) == GIVEN for k in cross_dims[:2]):
            return False
        tail = low[m.end():]
        # the tail holds the REST of the cross: one number fewer than the
        # archetype has cross dimensions -- a wireway's "length 24 X 42 x 42in"
        # already has its whole cross after the alias (#828 round 6)
        more = rf"(?:\s*[x×]\s*{_NUM_CORE})?" if len(cross_dims) > 2 else ""
        for pat in _product_patterns(arch):
            mt = re.match(rf"\s*[x×]\s*{_NUM_CORE}{more}{_SEP}"
                          rf"(?P<u>{_ANY_UNIT})?{_SEP}(?:{pat})", tail)
            if mt:
                return not (mt.group("u") and re.fullmatch(_UNITS["ft"], mt.group("u")))
        return False

    def inside_longer(s: int, e: int, n: int) -> bool:
        # the whole match, not just its alias: the number and unit around
        # an alias are never part of another alias's text
        return any(s < oe and e > os_ and on > n for os_, oe, on in spans)

    def bind_aliases(alias_first: bool):
        b_vals, b_prov = dict(vals), dict(prov)
        b_quoted: Dict[str, str] = {}
        b_used: List[Tuple[int, int]] = []

        def b_free(s: int, e: int) -> bool:
            return not any(s < ue and e > us for us, ue in b_used)

        candidates = sorted(((n, rank, pat, p) for p in arch.params
                             for n, rank, pat in _alias_patterns(p, alias_first=alias_first)),
                            key=lambda c: -c[0])
        for n, rank, pat, p in candidates:
            if b_prov[p.key] == GIVEN:
                continue
            for m in re.finditer(pat, low):
                if not b_free(m.start(), m.end()):
                    continue
                if inside_longer(m.start(), m.end(), n) or opens_cross(m, rank, p, b_prov):
                    continue
                # a unit-less number after a rating or count word belongs to
                # that scheme: "nema 1 width 6 in wide" is NEMA 1, not a 1 in
                # width (#828 round 6) -- the noun rule's guard, same words
                if rank == 0 and not m.group("u"):
                    lead = low[max(0, m.start() - 24):m.start()]
                    # (a restatement is THIS parameter's phrase, not a longer
                    # alias holding it: "rung width 1 in" restates no width)
                    tail0 = m.end()
                    if _NOT_A_SIZE_LEAD.search(lead) or (_DESIGNATOR_LEAD.search(lead) and any(
                            not inside_longer(tail0 + mr.start(), tail0 + mr.end(), n_)
                            for n_, _r, pu in _alias_patterns(p)
                            for mr in re.finditer(pu, low[tail0:]))):
                        continue
                num = _to_number(m.group(1))
                if num is None:
                    continue
                unit = _unit_of(m.group(0)) or p.unit
                conv = _convert(num, unit, p)
                if conv is None or conv <= p.minimum or conv > p.maximum:
                    continue
                b_vals[p.key] = conv
                b_prov[p.key] = GIVEN
                b_quoted[p.key] = text[m.start():m.end()].strip()
                b_used.append((m.start(), m.end()))
                break
        # the prompt's OTHER phrases for a parameter this reading has bound
        # that it left whole ("... 7 in wide" said again, or "... wide 9 in"
        # contradicting it): a reading that cut such a phrase in half to bind
        # something else read a number across a phrase boundary
        intact: List[Tuple[int, int]] = []
        for n, rank, pat, p in candidates:
            if b_prov[p.key] != GIVEN:
                continue
            for m in re.finditer(pat, low):
                s_, e_ = m.start(), m.end()
                if not b_free(s_, e_) or any(s_ < ie and e_ > is_ for is_, ie in intact):
                    continue
                # ... and a cross dimension's own alias is no exception HERE:
                # the reading has already bound it elsewhere, so "deep 20" in
                # "6 in deep 20 x 30 in panel, depth: 6 in" is not a phrase
                # left whole but the cross's first number (#828 round 6)
                if inside_longer(s_, e_, n) or opens_cross(m, rank, p, b_prov, any_alias=True):
                    continue
                num = _to_number(m.group(1))
                conv = None if num is None else _convert(num, _unit_of(m.group(0)) or p.unit, p)
                if conv is not None and p.minimum < conv <= p.maximum:
                    intact.append((s_, e_))
        return b_vals, b_prov, b_quoted, b_used, intact

    # A number standing between two aliases belongs to one phrase or the
    # other, and either fixed order steals it in one of the two chains (#812):
    # bind under both and keep, in order,
    #   1. the reading that gives MORE stated dimensions a home;
    #   2. the one that leaves more of the prompt's other phrases for its
    #      bound parameters WHOLE -- "wide 7 in loading depth 13 in wide 9 in"
    #      binds two either way, but number-first does it by reading
    #      "7 in loading depth" and "13 in wide", breaking every phrase the
    #      user wrote; alias-first leaves "wide 9 in" intact;
    #   3. on a full tie, main's alias-first reading.  Number-first here
    #      read "junction box width 8 in height 6 in deep" as height 8, depth
    #      6 (#828 round 2) -- a trailing bare adjective is as common as a
    #      leading one, so neither side of a full tie is safe.  "a long 24 in
    #      wide 4 in deep cable tray" stays wrong, as on main (#832).
    # The winner's intact phrases are claimed too: a restatement left outside
    # ``used`` would be read again by the noun rules below ("a 4 in depth,
    # depth 4 in junction box" -> "4 in junction box", a 4 in wide box).
    led = bind_aliases(alias_first=True)
    trailed = bind_aliases(alias_first=False)
    score = lambda r: (sum(1 for v in r[1].values() if v == GIVEN), len(r[4]))
    vals, prov, quoted, used, intact = trailed if score(trailed) > score(led) else led
    used = used + intact

    # "a 12x12 wireway", "a 4 x 4 x 6 in box": a cross-dimension immediately
    # before the product noun sets width x height (x depth) in one go
    cross = [k for k in ("width_in", "height_in", "depth_in")
             if any(p.key == k for p in arch.params)]
    if len(cross) >= 2 and all(prov[k] == NOMINAL for k in cross[:2]):
        for pat in _product_patterns(arch):
            m = re.search(
                # only the FIRST number needs the left boundary; the 2nd/3rd
                # are preceded by the 'x' of "12x12", which the lookbehind
                # would otherwise reject
                rf"{_NUM}\s*[x×]\s*{_NUM_CORE}(?:\s*[x×]\s*{_NUM_CORE})?{_SEP}"
                rf"(?P<u>{_ANY_UNIT})?{_SEP}(?:{pat})", low)
            if not m or not free(m.start(), m.end()):
                continue
            unit = _unit_of(m.group(0))
            nums = [_to_number(g) for g in m.groups()[:3] if g]
            hit = False
            for k, num in zip(cross, nums):
                if num is None:
                    continue
                p = arch.param(k)
                conv = _convert(num, unit or p.unit, p)
                if conv is None or conv <= p.minimum or conv > p.maximum:
                    continue
                vals[k], prov[k] = conv, GIVEN
                quoted[k] = text[m.start():m.end()].strip()
                hit = True
            if hit:
                used.append((m.start(), m.end()))
                break

    # "a 24 inch cable tray" / "a 1-5/8 in strut": a bare measurement immediately
    # before the product noun sets the PRIMARY dimension when nothing else
    # claimed it -- but ONLY when the UNIT agrees with what that dimension is
    # measured in.  "a 10 ft cable tray" means a ten-foot-LONG tray, not a
    # ten-foot-WIDE one: a section dimension is quoted in inches and a run in
    # feet, so a foot measurement in front of the noun binds the length.
    prim = next((p for p in arch.params if p.primary), None)
    if prim is not None:
        for pat in _product_patterns(arch):
            # THE UNIT IS REQUIRED HERE.  A bare integer in front of the noun is
            # far more often a COUNT or a RATING than a size: "3 cable trays"
            # built one 3-INCH tray, "a NEMA 12 wireway" a 12 in one, "a Type 1
            # junction box" a 1 in one -- each quoting the user's own words back
            # as if they had given a width.  Every example in #591's DONE 4
            # carries a unit ("a 24 inch cable tray 20 ft long").
            m = re.search(rf"{_NUM}{_SEP}(?P<u>{_ANY_UNIT}){_SEP}(?:{pat})", low)
            if not m or not free(m.start(), m.end()):
                continue
            # ... and a rating/classification word in front of the number means
            # the number belongs to that scheme, not to the product's size
            if _RATING_LEAD.search(low[max(0, m.start() - 24):m.start()]):
                continue
            num = _to_number(m.group(1))
            if num is None:
                continue
            unit = _unit_of(m.group(0))
            target = prim
            # any modifier of the noun may lead: "1-5/8 in slotted strut trapeze"
            leads = dict(arch.noun_leads)
            lead_key = next((leads[w] for w in re.findall(r"[a-z]+", low[m.end("u"):m.end()])
                             if w in leads), None)
            if lead_key:
                # ... but only a value the channel section can take: "a 36 in
                # strut trapeze" is a 36 in TRAPEZE, "a 1-5/8 in strut trapeze"
                # a 1-5/8 in channel (#900 review round 3)
                lt = arch.param(lead_key)
                lc = _convert(num, unit or lt.unit, lt)
                if lc is not None and lt.minimum < lc <= lt.maximum:
                    target = lt
            if target is not prim:
                pass
            elif unit == "ft" and prim.unit == "in":
                # FEET in front of the noun names the RUN, not the section: "a
                # 10 ft cable tray" is ten feet long, not ten feet wide.  Only
                # this pair redirects -- every other unit (mm, in) is a section
                # measurement and is CONVERTED into the primary's own unit
                # rather than dropped ("a 600 mm cable tray" is a 23.6 in tray).
                target = next((q for q in arch.params
                               if q.unit == "ft" and prov[q.key] == NOMINAL), prim)
            if prov[target.key] == GIVEN:
                continue
            conv = _convert(num, unit or target.unit, target)
            if conv is None or conv <= target.minimum or conv > target.maximum:
                continue
            vals[target.key] = conv
            prov[target.key] = GIVEN
            quoted[target.key] = text[m.start():m.end()].strip()
            used.append((m.start(), m.end()))
            break
    _apply_follows(arch, vals, prov, quoted)
    derived = _settle(arch, vals, prov, quoted)
    clear = wants_clearance(text)
    return Resolved(arch=arch, values=vals, provenance=prov, quoted=quoted,
                    name=_name(arch, vals, prov, clearance=clear),
                    claim=manufacturer_claim(text), clearance=clear,
                    derived=derived, out_of_range=_out_of_range(arch, low, text, prov))


def _out_of_range(arch: Archetype, low: str, text: str,
                  prov: Dict[str, str]) -> List[Dict[str, Any]]:
    """Phrases that state a BOUNDED dimension (``Param.maximum``) left nominal
    at a value outside its range -- "a 7 tier trapeze" -- so the report can
    say what it did not use.  Only parameters that declare a range."""
    out: List[Dict[str, Any]] = []
    prim = next((p for p in arch.params if p.primary), None)
    for p in arch.params:
        if prov.get(p.key) != NOMINAL or not math.isfinite(p.maximum):
            continue
        pats = [pat for _n, _r, pat in _alias_patterns(p)]
        if p is prim:
            pats += [rf"{_NUM}{_SEP}(?P<u>{_ANY_UNIT}){_SEP}(?:{q})"
                     for q in _product_patterns(arch)]
        for pat in pats:
            for m in re.finditer(pat, low):
                num = _to_number(m.group(1))
                if num is None:
                    continue
                conv = _convert(num, _unit_of(m.group(0)) or p.unit, p)
                if conv is not None and conv > p.maximum:
                    if any(o["key"] == p.key and m.start() < o["_e"] and m.end() > o["_s"]
                           for o in out):
                        continue                 # one phrase, read by two patterns
                    out.append({"key": p.key, "label": p.label,
                                "said": text[m.start():m.end()].strip(),
                                "range": f"up to {p.display(p.maximum)}",
                                "_s": m.start(), "_e": m.end()})
    return [{k: v for k, v in o.items() if not k.startswith("_")} for o in out]


def _settle(arch: Archetype, vals: Dict[str, float], prov: Dict[str, str],
            quoted: Dict[str, str], undo: Dict[str, str] = None,
            keep: Sequence[str] = ()) -> Dict[str, str]:
    """Run ``arch.settle`` and return what it derived (key -> reason).  A value
    an EARLIER settle derived (``undo``) goes back to nominal first unless the
    caller has since stated it (``keep``), so it is re-derived from the
    caller's current numbers instead of being taken for one of them."""
    if arch.settle is None:
        return {}
    for k in (undo or {}):
        if k not in keep:
            vals[k] = arch.param(k).default
            prov[k] = NOMINAL
            quoted.pop(k, None)
    before = dict(prov)
    arch.settle(vals, prov, quoted)
    return {k: quoted.get(k, "") for k, v in prov.items()
            if v == GIVEN and before.get(k) != GIVEN}


def _apply_follows(arch: Archetype, vals: Dict[str, float], prov: Dict[str, str],
                   quoted: Dict[str, str]) -> None:
    """A dimension that FOLLOWS another takes it when the caller set that one
    and left this one alone -- a square wireway asked for at 12 in is 12 in
    tall.  It becomes ``given``, because the caller's number decided it."""
    for p in arch.params:
        if not p.follows or prov.get(p.key) != NOMINAL:
            continue
        if prov.get(p.follows) != GIVEN:
            continue
        src = arch.param(p.follows)
        if src.unit != p.unit:                   # only same-unit pairs follow
            continue
        vals[p.key] = vals[p.follows]
        prov[p.key] = GIVEN
        quoted[p.key] = f"follows the given {src.label} ({src.display(vals[p.follows])})"


def resolve(product: str, overrides: Optional[Dict[str, Any]] = None,
            *, prompt: str = "") -> Resolved:
    """An archetype request stated STRUCTURALLY (a famspec): every override is
    ``given`` by definition, everything else nominal.  ``prompt`` (optional) is
    read for anything the overrides did not set."""
    arch = archetype(product)
    base = resolve_prompt(prompt, product=product) if prompt else None
    vals = dict(base.values) if base else arch.defaults()
    prov = dict(base.provenance) if base else {p.key: NOMINAL for p in arch.params}
    quoted = dict(base.quoted) if base else {}
    for k, v in (overrides or {}).items():
        p = arch.param(k)                        # unknown key -> refused BY NAME
        try:
            fv = float(v)
        except (TypeError, ValueError):
            raise ArchetypeError(f"{arch.key}.{k}: {v!r} is not a number "
                                 f"({p.label}, in {p.unit})")
        if not math.isfinite(fv) or fv < p.minimum or (fv <= 0.0 and not p.allow_zero):
            raise ArchetypeError(f"{arch.key}.{k}: {v!r} is not a usable "
                                 f"{p.label} (in {p.unit})"
                                 + ("" if p.allow_zero else
                                    " -- a dimension of zero authors a solid of zero "
                                    "volume, which is not a smaller product"))
        vals[k] = fv
        prov[k] = GIVEN
        quoted.pop(k, None)
    _apply_follows(arch, vals, prov, quoted)
    derived = _settle(arch, vals, prov, quoted,
                      undo=(base.derived if base else None), keep=tuple(overrides or ()))
    clear = bool(base.clearance) if base else wants_clearance(prompt)
    return Resolved(arch=arch, values=vals, provenance=prov, quoted=quoted,
                    name=_name(arch, vals, prov, clearance=clear),
                    claim=(base.claim if base else manufacturer_claim(prompt)),
                    clearance=clear, derived=derived)


# ---------------------------------------------------------------------------
# NEC working space (#818 / #820) -- sized from rvt.famgen.clearance
# ---------------------------------------------------------------------------

_CLEARANCE_ASK = re.compile(
    r"\b(?:nec\s+)?(?:working\s+)?(?:clearances?|working\s+space)\b", re.I)
_CLEARANCE_NOT = re.compile(
    r"\b(?:no|without|w/o|minus|excluding|exclude)\s+(?:any\s+|the\s+|nec\s+|working\s+)*"
    r"(?:clearances?|working\s+space)\b", re.I)

#: the cabinet's TOP above the floor, used to reach the working space down to
#: the floor (110.26(A)(3) measures from the floor, the family's origin is the
#: cabinet bottom).  NOMINAL: a common surface-panel mounting, stated in the
#: report, and the reason the variant's zone is right only when the panel is
#: mounted that way.
MOUNT_TOP_IN = 78.0


def wants_clearance(text: str) -> bool:
    """The prompt asks for the NEC working-space clearance: "with clearance",
    "NEC clearances", "working space" -- and does not say "without" it."""
    t = str(text or "")
    return bool(_CLEARANCE_ASK.search(t)) and not _CLEARANCE_NOT.search(t)


def _working_space(res: "Resolved"):
    from . import clearance as CL
    v = res.values
    return CL.working_space(equipment_width_ft=v["width_in"] * IN,
                            equipment_height_ft=v["height_in"] * IN)


def working_space_part(res: "Resolved") -> Dict[str, Any]:
    """The NEC 110.26(A) working space as one ``role: clearance`` box: in front
    of the working face (the cabinet projects toward -Y, so the zone starts at
    the door face), centred on the equipment, from the FLOOR up -- the floor
    being :data:`MOUNT_TOP_IN` below the cabinet top.  ``role: clearance``
    keeps it out of the equipment's own Width / Depth / Height (#820)."""
    v = res.values
    ws = _working_space(res)
    H, D = v["height_in"] * IN, v["depth_in"] * IN
    floor = -max(0.0, MOUNT_TOP_IN * IN - H)          # the floor, below the cabinet bottom
    return {"shape": "box", "name": "nec working space", "role": "clearance",
            "width_ft": ws.width_ft, "depth_ft": ws.depth_ft, "height_ft": ws.height_ft,
            "center": [0.0, -(D + ws.depth_ft / 2.0)], "base_z_ft": floor}


def working_space_report(res: "Resolved") -> Dict[str, Any]:
    ws = _working_space(res)
    H = res.values["height_in"] * IN
    return {
        "depth_ft": ws.depth_ft, "width_ft": ws.width_ft, "height_ft": ws.height_ft,
        "source": ws.source, "tier": ws.tier, "verified": ws.verified,
        "status": ws.status, "assumed": dict(ws.assumed),
        "mounting": (f"cabinet top {MOUNT_TOP_IN:g} in above the floor "
                     f"(bottom {max(0.0, MOUNT_TOP_IN - H * 12.0):g} in) -- NOMINAL; the "
                     "zone reaches the floor only when the panel is mounted this way"),
        "toggle": ("'Show Clearance' is a real Yes/No parameter but is NOT yet linked to "
                   "the zone's visibility (#690): the zone is always drawn"),
        "subcategory": "none -- the engine cannot author a subcategory yet (#820)",
    }


def _name(arch: Archetype, vals: Dict[str, float], prov: Dict[str, str], *,
          clearance: bool = False) -> str:
    """A family name off the dimensions that identify the product."""
    prim = next((p for p in arch.params if p.primary), None)
    bits = [arch.title]
    if prim is not None:
        bits.append(prim.display(vals[prim.key]))
    length = next((p for p in arch.params if p.key == "length_ft"), None)
    if length is not None:
        bits.append(length.display(vals[length.key]))
    bits.extend(arch.name_bits(vals))
    if clearance and arch.working_space:
        bits.append("with NEC Clearance")
    return " ".join(bits)


# ---------------------------------------------------------------------------
# the parts + the honest fact sheet
# ---------------------------------------------------------------------------

def build_parts(res: Resolved) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """``(parts, report)`` -- the part list `make_generic_model` authors, and
    the provenance report naming every nominal and every given dimension."""
    parts = res.parts()
    rep = res.to_json()
    rep["parts"] = len(parts)
    rep["note"] = (
        f"generated at standard nominal dimensions for a {res.arch.title}: "
        f"{len(res.nominal())} dimension(s) NOMINAL "
        f"({res.arch.basis.split('.')[0]}), {len(res.given())} given by the caller. "
        "A nominal dimension is standard practice for this product class, NOT a "
        "manufacturer's catalog record -- no manufacturer, model or part number is "
        "claimed. Pass any dimension to override it.")
    if res.claim:
        rep["note"] = res.claim["line"] + " " + rep["note"]
    return parts, rep


def describe(product: str) -> Dict[str, Any]:
    a = archetype(product)
    return {
        "product": a.key, "title": a.title, "category": a.category,
        "basis": a.basis, "lod": a.lod_note, "limits": list(a.limits),
        "also_called": list(a.aliases),
        "parameters": [{"key": p.key, "label": p.label, "nominal": p.default,
                        "unit": p.unit, "basis": p.basis,
                        "standard_sizes": list(p.choices),
                        "primary": p.primary,
                        "prompt_words": list(p.aliases)} for p in a.params],
    }


def table() -> Dict[str, Any]:
    return {"products": {k: describe(k) for k in keys()},
            "provenance": {
                NOMINAL: ("standard practice for the product class, generated by the "
                          "archetype -- never a manufacturer claim"),
                GIVEN: "the caller stated it (a prompt, a famspec field)"}}


def check_registry() -> List[str]:
    """Every problem in the registry, one line each -- empty when it is sound.

    (1) every archetype builds from its own nominals; (2) every part it emits
    is a shape the famspec contract accepts; (3) parameter keys are unique and
    every alias is lower-case (the resolver matches against a lower-cased
    prompt); (4) each archetype's own patterns recognise it, and no archetype's
    pattern claims another's title.
    """
    from ..frontdoor import famspec as _FS          # noqa: F401  (shape vocabulary)
    problems: List[str] = []
    shapes = {"box", "cylinder", "cylinder_x", "cylinder_y", "polygon",
              "sphere", "dome", "cone"}
    for key, a in ARCHETYPES.items():
        if a.key != key:
            problems.append(f"{key}: registered under a different key than its own {a.key!r}")
        seen = set()
        for p in a.params:
            if p.key in seen:
                problems.append(f"{key}/{p.key}: listed twice")
            seen.add(p.key)
            for al in p.aliases:
                if al != al.lower():
                    problems.append(f"{key}/{p.key}: alias {al!r} is not lower-case")
        if not any(p.primary for p in a.params):
            problems.append(f"{key}: no primary parameter (a bare '24 in <product>' "
                            f"cannot be read)")
        try:
            parts = a.build(a.defaults())
        except Exception as e:                       # noqa: BLE001
            problems.append(f"{key}: does not build from its own nominals "
                            f"({type(e).__name__}: {e})")
            continue
        if not parts:
            problems.append(f"{key}: builds no parts")
        for p in parts:
            if str(p.get("shape")) not in shapes:
                problems.append(f"{key}: part {p.get('name')!r} has shape "
                                f"{p.get('shape')!r}, which the famspec does not accept")
        r = resolve_prompt(f"create a {a.title.split(' - ')[0].lower()} family")
        if r is None or r.arch.key != key:
            problems.append(f"{key}: its own title is not recognised by its patterns "
                            f"(got {None if r is None else r.arch.key})")
    return problems


if __name__ == "__main__":                          # pragma: no cover
    import json
    import sys
    args = sys.argv[1:]
    if args and args[0] == "--check":
        probs = check_registry()
        for p in probs:
            print(p)
        print(f"{len(ARCHETYPES)} archetypes, {len(probs)} problems")
        sys.exit(1 if probs else 0)
    if args:
        r = resolve_prompt(" ".join(args))
        print(json.dumps(r.to_json() if r else
                         {"recognised": False, "products": list(keys())}, indent=1))
    else:
        print(json.dumps(table(), indent=1))

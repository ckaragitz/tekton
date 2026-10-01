"""equipment_detail -- the real parts of an equipment family, not a labelled box (#879).

A generated dry-type transformer was one shaded box with two connectors on top
("this looks absolutely nothing like a transformer", steer #879).  A ventilated
dry-type transformer (NEMA 1 / 3R, the common 15-150 kVA floor-standing kind) is
recognisable by its parts, and this module lays them out inside the catalog
envelope ``W`` (x) x ``D`` (y) x ``H`` (z, from the floor), front = -y:

* two base SKIDS (the feet it stands on, open between them);
* the ENCLOSURE body, with a recessed VENTILATION SLOT across the top of the
  front under the lid, LOUVER slats set in the slot, and side cheeks framing it;
* the TOP COVER, overhanging the body all round (the drip lid);
* low and high LOUVER banks on both sides;
* the bolted FRONT ACCESS PANEL with its bolt heads, and a NAMEPLATE.

(No lifting lugs: on these units the lifting points are holes in the top flange,
and a lug would stand above the catalog height.)

Every detail dimension is a NOMINAL proportion of the envelope (the archetype,
S-2026-08-10-e): never a manufacturer's drawing -- a spec sheet (#871) is the
only source of those.  The envelope itself (W / D / H) stays the catalog fact the
caller passes: the parts are laid out inside it, the overhanging cover and
proud plates excepted (a fraction of an inch, said in ``DETAIL_NOTE``).

Pure geometry: :func:`transformer_parts` returns boxes; the factory authors them.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

IN = 1.0 / 12.0                     # one inch in feet

#: how far the frontmost part stands proud of the enclosure face -- the top cover's
#: overhang (0.5 in; the access panel + bolt heads reach 0.25 in): the working space
#: starts in front of it, never inside a part
FRONT_PROUD_FT = 0.5 * (1.0 / 12.0)

DETAIL_NOTE = ("transformer detail at NOMINAL proportions (archetype, not a manufacturer "
               "drawing): base skids, enclosure with a louvered ventilation slot under the "
               "lid, overhanging top cover, side louver banks, bolted front access panel, "
               "nameplate; W x D x H = the catalog envelope (the cover "
               "overhang and proud plates add under 1 in)")


@dataclass(frozen=True)
class BoxPart:
    """One axis-aligned solid: ``w`` (x) x ``d`` (y) x ``h`` (z) from ``z0``, centred
    on (``cx``, ``cy``) in plan.  Feet."""
    role: str
    w: float
    d: float
    h: float
    z0: float
    cx: float = 0.0
    cy: float = 0.0


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def transformer_parts(W: float, D: float, H: float) -> List[BoxPart]:
    """The parts of a ventilated dry-type transformer inside the W x D x H envelope
    (feet).  The first part is the enclosure body (the form a report calls "the
    solid"); the top cover's top face is at ``H`` (where the connectors go)."""
    if min(W, D, H) <= 0:
        raise ValueError("transformer envelope must be positive")
    parts: List[BoxPart] = []
    leg_h = _clamp(0.05 * H, 3 * IN, 5 * IN)
    skid_w = _clamp(0.12 * W, 2 * IN, 4 * IN)
    cover_t = _clamp(0.03 * H, 1.0 * IN, 2.0 * IN)
    overhang = 0.5 * IN
    slot_h = _clamp(0.07 * H, 2.5 * IN, 5 * IN)
    recess = _clamp(0.08 * D, 0.75 * IN, 1.5 * IN)
    cheek_w = _clamp(0.06 * W, 1.0 * IN, 2.0 * IN)
    body_top = H - cover_t
    slot_z0 = body_top - slot_h
    front = -D / 2.0

    # the enclosure: below the slot at full depth; the slot's band set back by the recess
    parts.append(BoxPart("enclosure body", W, D, slot_z0 - leg_h, leg_h))
    parts.append(BoxPart("enclosure upper band (behind the vent slot)", W, D - recess, slot_h,
                         slot_z0, 0.0, recess / 2.0))
    for sx in (-1, 1):
        parts.append(BoxPart("vent slot cheek", cheek_w, recess, slot_h, slot_z0,
                             sx * (W / 2.0 - cheek_w / 2.0), front + recess / 2.0))
    # louver slats in the slot: set against its back face, not quite flush
    n = max(2, int(slot_h / (0.75 * IN)))
    slat_h, slat_d = 0.18 * IN, recess * 0.85
    pitch = slot_h / (n + 1)
    for k in range(1, n + 1):
        parts.append(BoxPart("vent slot louver", W - 2 * cheek_w, slat_d, slat_h,
                             slot_z0 + k * pitch - slat_h / 2.0, 0.0, front + recess - slat_d / 2.0))
    # the top cover (drip lid), overhanging all round
    parts.append(BoxPart("top cover", W + 2 * overhang, D + 2 * overhang, cover_t, body_top))
    # base skids: the feet, open between them
    for sx in (-1, 1):
        parts.append(BoxPart("base skid", skid_w, D, leg_h, 0.0, sx * (W / 2.0 - skid_w / 2.0)))
    # side louver banks, low and high, both sides
    louver_d, louver_t, louver_h = 0.55 * D, 0.3 * IN, 0.2 * IN
    low = [leg_h + 3 * IN + i * 0.6 * IN for i in range(6)]
    high = [slot_z0 - 1.5 * IN - i * 0.6 * IN for i in range(4)]
    for sx in (-1, 1):
        for z in low + high:
            parts.append(BoxPart("side louver", louver_t, louver_d, louver_h, z,
                                 sx * (W / 2.0 + louver_t / 2.0), 0.0))
    # the bolted front access panel, its bolt heads, and the nameplate
    plate_t = 0.1 * IN
    p_x = W - 2 * 1.25 * IN
    p_z0, p_z1 = leg_h + 1 * IN, slot_z0 - 1 * IN
    parts.append(BoxPart("front access panel", p_x, plate_t, p_z1 - p_z0, p_z0,
                         0.0, front - plate_t / 2.0))
    bolt, bolt_t = 0.5 * IN, 0.15 * IN
    by = front - plate_t - bolt_t / 2.0
    for bx in (-(p_x / 2.0 - 1 * IN), p_x / 2.0 - 1 * IN):
        for bz in (p_z0 + 1 * IN, (p_z0 + p_z1) / 2.0, p_z1 - 1 * IN):
            parts.append(BoxPart("access panel bolt", bolt, bolt_t, bolt, bz - bolt / 2.0, bx, by))
    np_w = min(6 * IN, 0.3 * W)
    np_h = min(4 * IN, 0.2 * (p_z1 - p_z0))
    parts.append(BoxPart("nameplate", np_w, 0.06 * IN, np_h, p_z0 + 0.62 * (p_z1 - p_z0),
                         0.1 * W, front - plate_t - 0.03 * IN))
    return parts


#: panelboard front: trim plate and door thicknesses, proud of the box face
PANEL_TRIM_T = 0.1875 * IN
PANEL_DOOR_T = 0.125 * IN

PANEL_DETAIL_NOTE = ("panelboard detail at NOMINAL proportions (archetype, not a manufacturer "
                     "drawing): the catalog box, a front trim with corner screws, a hinged door "
                     "with two hinges, a latch handle with a key lock, and a nameplate; the box "
                     "W x D x H is the catalog fact, the trim and door stand under 1 in proud "
                     "of its face (a flush trim also laps the wall opening by 0.75 in)")


def panelboard_parts(W: float, D: float, H: float, *, flush: bool = False) -> List[BoxPart]:
    """The FRONT of a panelboard cabinet (the box itself is the caller's catalog-driven
    enclosure form and is NOT returned): its face is the plane ``y = face`` with the
    door facing +y -- ``face = D`` for a SURFACE box standing on ``0..D``, ``0`` for a
    FLUSH box recessed on ``-D..0`` (its trim laps the wall opening).  Feet, nominal
    proportions (:data:`PANEL_DETAIL_NOTE`)."""
    if min(W, D, H) <= 0:
        raise ValueError(f"panelboard box must be positive, got {W} x {D} x {H}")
    face = 0.0 if flush else D
    lap = 0.75 * IN if flush else 0.0
    tw, th, tz0 = W + 2 * lap, H + 2 * lap, -lap
    parts: List[BoxPart] = [
        BoxPart("front trim", tw, PANEL_TRIM_T, th, tz0, 0.0, face + PANEL_TRIM_T / 2)]
    # the door: inset from the trim edge, standing on the trim
    side_in = _clamp(0.065 * W, 0.75 * IN, 1.5 * IN)
    end_in = _clamp(0.045 * H, 1.0 * IN, 2.5 * IN)
    dw, dh, dz0 = W - 2 * side_in, H - 2 * end_in, end_in
    y_door = face + PANEL_TRIM_T
    parts.append(BoxPart("door", dw, PANEL_DOOR_T, dh, dz0, 0.0, y_door + PANEL_DOOR_T / 2))
    y_on = y_door + PANEL_DOOR_T                       # the door's outer face
    # hinges on the door's LEFT edge as you face it -- facing the door from +y,
    # your left is +x -- at a fifth and four fifths of its height
    hw, hd, hh = 0.3 * IN, 0.3 * IN, min(2.5 * IN, dh / 6)
    hx = dw / 2 + hw / 2 - 0.05 * IN
    for frac in (0.2, 0.8):
        parts.append(BoxPart("door hinge", hw, hd, hh, dz0 + frac * dh - hh / 2, hx, y_on - hd / 2 + 0.1 * IN))
    # latch handle and key lock on the RIGHT edge as you face it (-x), at mid height
    lx = -(dw / 2 - min(1.25 * IN, dw / 8))
    lh = min(3.0 * IN, dh / 5)
    lz = dz0 + dh / 2 - lh / 2
    parts.append(BoxPart("door latch handle", 0.9 * IN, 0.35 * IN, lh, lz, lx, y_on + 0.175 * IN))
    parts.append(BoxPart("door lock", 0.6 * IN, 0.2 * IN, 0.6 * IN, lz + lh + 0.4 * IN, lx, y_on + 0.1 * IN))
    # trim screws: the four corners outside the door, and mid-height on both sides
    sx = tw / 2 - side_in / 2
    for z in (tz0 + end_in / 2, tz0 + th - end_in / 2, tz0 + th / 2):
        for x in (-sx, sx):
            parts.append(BoxPart("trim screw", 0.4 * IN, 0.1 * IN, 0.4 * IN, z - 0.2 * IN, x,
                                 face + PANEL_TRIM_T + 0.05 * IN))
    # nameplate across the top of the door
    nw, nh = min(4.0 * IN, dw * 0.4), 1.25 * IN
    parts.append(BoxPart("nameplate", nw, 0.06 * IN, nh, dz0 + dh - 2.5 * IN - nh, 0.0, y_on + 0.03 * IN))
    return parts


def front_proud_ft(parts: List[BoxPart], face: float) -> float:
    """How far the frontmost part stands proud of ``face`` (the +y door side)."""
    return max([p.cy + p.d / 2 for p in parts] + [face]) - face

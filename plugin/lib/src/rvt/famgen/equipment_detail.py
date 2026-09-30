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

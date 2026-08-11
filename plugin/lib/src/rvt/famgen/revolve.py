"""rvt.famgen.revolve -- ROUND AND ROTATED BODIES out of Z-extruded prisms.

THE WALL THIS GETS OVER.  ``add_generic_part`` extrudes a plan profile along
Z and nothing else: no rotation, no revolve.  So a sphere was not expressible
at all, and a wheel -- a cylinder about a HORIZONTAL axis -- came out as a
disc lying flat.  The bus built for issue #591 had six boxes where its wheels
should be, and a strut channel's C-profile is massed by its envelope for the
same reason.

Rotating the extrusion itself would mean a non-identity 3x3 on a sketch plane
bound to the level datum -- the class of internal inconsistency the open cell
(``docs/inbox/genesis-audit.md`` #31-#48) is about, and uncertifiable without
a desktop round.  This module takes the other road, and needs no new law at
all: **a solid of revolution is a STACK of the prisms we already author and
Revit already loads.**

* a SPHERE is a stack of discs whose radius follows sqrt(r^2 - z^2);
* a HORIZONTAL cylinder (a wheel, a pipe run, an axle) is a stack of boxes
  whose width follows the same chord rule, the box's length being the
  cylinder's own length;
* a CONE / frustum is a stack of discs interpolating two radii;
* a DOME is the top half of the sphere.

Every generated part is an ordinary ``box`` / ``cylinder`` dict, so the whole
set travels the line-segment and arc paths that the owner's desktop Revit 2026
verified (boxes and N-gons load; arcs load since #589).  Nothing here touches
the writer.

THE APPROXIMATION IS MEASURED, NOT DESCRIBED.  ``segments`` controls the stack
and every generator reports the volume it authored against the true volume of
the body it approximates, so the error is a number in the report rather than
an adjective.  A stack always UNDER-fills a convex body (each slab is sized at
its mid-height), which is why the ratio is reported rather than assumed away.

Territory: famgen (new module; emits part dicts only, edits no writer path).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "RevolveError", "sphere_parts", "dome_parts", "cone_parts",
    "horizontal_cylinder_parts", "expand_parts", "COMPOSITE_SHAPES",
    "DEFAULT_SEGMENTS", "MAX_SEGMENTS",
]


class RevolveError(ValueError):
    """A composite shape was asked for with a dimension it cannot be built from."""


#: Slices per body by default.  16 keeps a sphere's authored volume within a
#: couple of percent of the true one while staying cheap; DETAIL raises it.
DEFAULT_SEGMENTS = 16

#: A stack this tall is already past the point where more slices buy anything
#: a viewer can see, and every slice is another solid in the family.
MAX_SEGMENTS = 64

#: The shapes this module expands into ordinary prisms.
COMPOSITE_SHAPES = ("sphere", "dome", "cone")
#: cylinder_x / cylinder_y are NO LONGER expanded here.  Desktop round 4 (#591)
#: showed the cached B-rep is what Revit draws, so the factory authors a TRUE
#: rotated cylinder for them -- a real wheel, verified round in the Front
#: elevation, instead of the stack of boxes this module used to emit.


def _segments(n: Optional[int]) -> int:
    s = int(n or DEFAULT_SEGMENTS)
    if s < 3:
        raise RevolveError(f"segments={s} is too few to make a round body (minimum 3)")
    return min(s, MAX_SEGMENTS)


def _named(base: str, i: int, n: int) -> str:
    return f"{base} [{i + 1}/{n}]" if n > 1 else base


# ---------------------------------------------------------------------------
# solids of revolution about the VERTICAL axis -- stacks of discs
# ---------------------------------------------------------------------------

def sphere_parts(radius_ft: float, *, center: Sequence[float] = (0.0, 0.0),
                 base_z_ft: float = 0.0, segments: Optional[int] = None,
                 name: str = "sphere") -> List[Dict[str, Any]]:
    """A sphere as a stack of discs, resting with its SOUTH POLE at
    ``base_z_ft`` (so it sits on the plane you place it on, like every other
    part in the contract).

    Each slab's radius is taken at its MID height -- the honest choice: a
    top-sampled stack would swell the body, a bottom-sampled one would shrink
    it, and mid-sampling keeps the error symmetric and small.
    """
    r = float(radius_ft)
    if r <= 0:
        raise RevolveError("a sphere needs a positive radius_ft")
    n = _segments(segments)
    h = 2.0 * r / n
    out: List[Dict[str, Any]] = []
    for i in range(n):
        zc = -r + (i + 0.5) * h                     # mid-height, sphere frame
        rr = math.sqrt(max(r * r - zc * zc, 0.0))
        if rr <= 0:
            continue
        out.append({"shape": "cylinder", "radius_ft": rr, "height_ft": h,
                    "base_z_ft": base_z_ft + r + zc - h / 2.0,
                    "center": [float(center[0]), float(center[1])],
                    "name": _named(name, i, n)})
    return out


def dome_parts(radius_ft: float, *, center: Sequence[float] = (0.0, 0.0),
               base_z_ft: float = 0.0, segments: Optional[int] = None,
               name: str = "dome") -> List[Dict[str, Any]]:
    """The upper half of a sphere, flat face down on ``base_z_ft``."""
    r = float(radius_ft)
    if r <= 0:
        raise RevolveError("a dome needs a positive radius_ft")
    n = _segments(segments)
    h = r / n
    out: List[Dict[str, Any]] = []
    for i in range(n):
        zc = (i + 0.5) * h
        rr = math.sqrt(max(r * r - zc * zc, 0.0))
        if rr <= 0:
            continue
        out.append({"shape": "cylinder", "radius_ft": rr, "height_ft": h,
                    "base_z_ft": base_z_ft + i * h,
                    "center": [float(center[0]), float(center[1])],
                    "name": _named(name, i, n)})
    return out


def cone_parts(radius_ft: float, height_ft: float, *,
               top_radius_ft: float = 0.0, center: Sequence[float] = (0.0, 0.0),
               base_z_ft: float = 0.0, segments: Optional[int] = None,
               name: str = "cone") -> List[Dict[str, Any]]:
    """A cone (or a frustum, with ``top_radius_ft``) as stacked discs."""
    r0, r1, hh = float(radius_ft), float(top_radius_ft), float(height_ft)
    if r0 <= 0 or hh <= 0:
        raise RevolveError("a cone needs a positive radius_ft and height_ft")
    if r1 < 0:
        raise RevolveError("top_radius_ft cannot be negative")
    n = _segments(segments)
    h = hh / n
    out: List[Dict[str, Any]] = []
    for i in range(n):
        t = (i + 0.5) / n
        rr = r0 + (r1 - r0) * t
        if rr <= 0:
            continue
        out.append({"shape": "cylinder", "radius_ft": rr, "height_ft": h,
                    "base_z_ft": base_z_ft + i * h,
                    "center": [float(center[0]), float(center[1])],
                    "name": _named(name, i, n)})
    return out


# ---------------------------------------------------------------------------
# a cylinder about a HORIZONTAL axis -- the wheel case
# ---------------------------------------------------------------------------

def horizontal_cylinder_parts(radius_ft: float, length_ft: float, *,
                              axis: str = "y",
                              center: Sequence[float] = (0.0, 0.0),
                              base_z_ft: float = 0.0,
                              segments: Optional[int] = None,
                              name: str = "roll") -> List[Dict[str, Any]]:
    """A cylinder lying along X or Y -- a wheel, an axle, a pipe run -- as a
    stack of boxes.

    Sliced horizontally, such a cylinder gives a rectangle at every height:
    the cylinder's own length along its axis, and a CHORD across it.  The
    chord follows 2*sqrt(r^2 - z^2), so the stack reproduces the round
    silhouette when seen from the end -- which is the view that makes a wheel
    read as a wheel.  ``base_z_ft`` is where the body RESTS (its lowest
    point), so a wheel sits on the ground rather than being centred on it.
    """
    r, L = float(radius_ft), float(length_ft)
    if r <= 0 or L <= 0:
        raise RevolveError("a horizontal cylinder needs a positive radius_ft and length_ft")
    ax = str(axis).lower()
    if ax not in ("x", "y"):
        raise RevolveError(f"axis must be 'x' or 'y', got {axis!r}")
    n = _segments(segments)
    h = 2.0 * r / n
    out: List[Dict[str, Any]] = []
    for i in range(n):
        zc = -r + (i + 0.5) * h
        chord = 2.0 * math.sqrt(max(r * r - zc * zc, 0.0))
        if chord <= 0:
            continue
        w, d = (L, chord) if ax == "x" else (chord, L)
        out.append({"shape": "box", "width_ft": w, "depth_ft": d, "height_ft": h,
                    "base_z_ft": base_z_ft + r + zc - h / 2.0,
                    "center": [float(center[0]), float(center[1])],
                    "name": _named(name, i, n)})
    return out


# ---------------------------------------------------------------------------
# the expander the contract calls
# ---------------------------------------------------------------------------

_TRUE_VOLUME = {
    "sphere": lambda p: 4.0 / 3.0 * math.pi * float(p["radius_ft"]) ** 3,
    "dome": lambda p: 2.0 / 3.0 * math.pi * float(p["radius_ft"]) ** 3,
    "cone": lambda p: (math.pi * float(p["height_ft"]) / 3.0
                       * (float(p["radius_ft"]) ** 2
                          + float(p["radius_ft"]) * float(p.get("top_radius_ft") or 0.0)
                          + float(p.get("top_radius_ft") or 0.0) ** 2)),
    "cylinder_x": lambda p: math.pi * float(p["radius_ft"]) ** 2 * float(p["length_ft"]),
    "cylinder_y": lambda p: math.pi * float(p["radius_ft"]) ** 2 * float(p["length_ft"]),
}


def _authored_volume(parts: Sequence[Dict[str, Any]]) -> float:
    v = 0.0
    for p in parts:
        if p["shape"] == "cylinder":
            v += math.pi * float(p["radius_ft"]) ** 2 * float(p["height_ft"])
        else:
            v += float(p["width_ft"]) * float(p["depth_ft"]) * float(p["height_ft"])
    return v


def expand_parts(parts: Sequence[Dict[str, Any]]
                 ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Expand every composite shape in ``parts`` into prisms the factory
    authors directly.

    Returns ``(expanded, report)`` -- one report row per composite, carrying
    the slice count and the AUTHORED / TRUE volume ratio, so the stack's error
    is a measured number.  Plain prisms pass through untouched.
    """
    out: List[Dict[str, Any]] = []
    report: List[Dict[str, Any]] = []
    for p in parts:
        shape = str(p.get("shape") or "box").lower()
        if shape not in COMPOSITE_SHAPES:
            out.append(p)
            continue
        seg = p.get("segments")
        name = str(p.get("name") or shape)
        centre = p.get("center") or (0.0, 0.0)
        base = float(p.get("base_z_ft") or 0.0)
        if shape == "sphere":
            made = sphere_parts(p["radius_ft"], center=centre, base_z_ft=base,
                                segments=seg, name=name)
        elif shape == "dome":
            made = dome_parts(p["radius_ft"], center=centre, base_z_ft=base,
                              segments=seg, name=name)
        elif shape == "cone":
            made = cone_parts(p["radius_ft"], p["height_ft"],
                              top_radius_ft=float(p.get("top_radius_ft") or 0.0),
                              center=centre, base_z_ft=base, segments=seg, name=name)
        else:                                            # cylinder_x / cylinder_y
            made = horizontal_cylinder_parts(
                p["radius_ft"], p["length_ft"], axis=shape[-1],
                center=centre, base_z_ft=base, segments=seg, name=name)
        true_v = _TRUE_VOLUME[shape](p)
        got_v = _authored_volume(made)
        report.append({
            "name": name, "shape": shape, "slices": len(made),
            "authored_ft3": round(got_v, 8), "true_ft3": round(true_v, 8),
            "ratio": (round(got_v / true_v, 4) if true_v > 0 else None),
            "note": ("a stack of prisms, not a true revolve: the part contract "
                     "extrudes along Z only, so the round body is sliced. The "
                     "ratio is authored volume over the real body's volume."),
        })
        out.extend(made)
    return out, report

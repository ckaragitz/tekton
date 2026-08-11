"""rvt.famgen.orient -- rigid re-orientation of an authored solid (issue #514).

WHY: every form ``rvt.famgen.geometry`` authors is extruded along -Z.  The
profile is lifted to two horizontal planes, ``ext``/``up``/``dn`` are the Z
unit vectors, and every face frame is derived from them.  A body whose axis is
NOT vertical -- a rod, a wire, a conduit, a sloped member -- cannot be
expressed.  Measured on a 71-wire cable-tray IFC4 export, only **14.9 % of
wire length** runs vertically: 53.2 % Y, 25.6 % X, 6.3 % diagonal.  Z-only
extrusion cannot express a cable tray at all.

WHAT THIS DOES: rather than re-deriving the six-face topology template (the
frame / loop / direction rules of ``docs/writer/family-geometry.md`` sec. 3,
every one stamped [V] against specimens), it builds the prism exactly as
today -- upright, verified -- and then applies ONE rigid rotation to the
finished record.  Topology, tags, loop links, coedge direction flags and uv
coordinates are untouched: uv pairs live in their own face frame, so a global
rotation leaves them correct by construction.

WHAT IS DELIBERATELY NOT ROTATED: ``m_keys`` (history tags such as
``[3, i, -1]`` -- integers that merely LOOK like a vector; rotating them
corrupts the element history), ``m_endParams`` (frame-local uv), and every
other numeric list.  The field list is an ALLOW-LIST for exactly that reason.

STATUS: the record is geometrically consistent and the validator accepts it,
but whether desktop Revit accepts a form whose baked B-rep is rotated while
its sketch stays on the Ref. Level datum is UNPROVEN -- hard rule 4, and the
single question the first desktop probe exists to answer.  Do not present a
rotated body as working until a Revit verdict says so.

Territory: issue #514 (new module; geometry.py untouched).
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Sequence, Tuple

__all__ = ["rotation_from_z", "rotate_record", "VECTOR_FIELDS"]

#: 3-vector fields that carry a POINT (rotate AND translate).
POINT_FIELDS = (
    "m_center",                         # circle + cylinder-surface centres
    "m_origin",                         # surface frame origins
    "m_or",                             # Trf translation
)
#: 3-vector fields that carry a DIRECTION (rotate ONLY -- never translate, or
#: every frame axis would drift with the body's position).
DIRECTION_FIELDS = (
    "m_xVec", "m_yVec", "m_zVec",      # face / plane frame axes
    "m_dirVec",                         # line direction
    "m_vecInPlane",                     # plane-ref in-plane vector
)
#: every field this module touches; everything else numeric is left as authored.
VECTOR_FIELDS = POINT_FIELDS + DIRECTION_FIELDS

Vec = Sequence[float]
Mat = List[List[float]]


def _unit(v: Vec) -> List[float]:
    n = math.sqrt(sum(float(c) * float(c) for c in v))
    if n <= 1e-12:
        raise ValueError(f"cannot orient along a zero-length direction {list(v)!r}")
    return [float(c) / n for c in v]


def rotation_from_z(direction: Vec) -> Mat:
    """The rotation taking **+Z** to ``direction`` (Rodrigues, shortest arc).

    Shortest-arc keeps the profile's own roll as close to the authored frame
    as possible, so an upright body rotated by ~0 is bit-for-bit the body the
    verified path produces.
    """
    d = _unit(direction)
    z = (0.0, 0.0, 1.0)
    c = sum(a * b for a, b in zip(z, d))
    if c > 1.0 - 1e-12:                                    # already +Z
        return [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    if c < -1.0 + 1e-12:                                   # antiparallel: 180 deg about X
        return [[1.0, 0.0, 0.0], [0.0, -1.0, 0.0], [0.0, 0.0, -1.0]]
    # v = z x d ; R = I + [v] + [v]^2 * 1/(1+c)
    vx, vy, vz = (z[1] * d[2] - z[2] * d[1],
                  z[2] * d[0] - z[0] * d[2],
                  z[0] * d[1] - z[1] * d[0])
    k = 1.0 / (1.0 + c)
    return [
        [1.0 + (-vz * vz - vy * vy) * k, -vz + vx * vy * k, vy + vx * vz * k],
        [vz + vx * vy * k, 1.0 + (-vz * vz - vx * vx) * k, -vx + vy * vz * k],
        [-vy + vx * vz * k, vx + vy * vz * k, 1.0 + (-vy * vy - vx * vx) * k],
    ]


def _apply(R: Mat, v: Vec) -> List[float]:
    x, y, z = (float(v[0]), float(v[1]), float(v[2]))
    return [R[0][0] * x + R[0][1] * y + R[0][2] * z,
            R[1][0] * x + R[1][1] * y + R[1][2] * z,
            R[2][0] * x + R[2][1] * y + R[2][2] * z]


def _matmul(A: Mat, B: Mat) -> Mat:
    return [[sum(A[i][k] * B[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _is_vec3(v: Any) -> bool:
    return (isinstance(v, list) and len(v) == 3
            and all(isinstance(c, (int, float)) and not isinstance(c, bool) for c in v))


def rotate_record(obj: Any, R: Mat, offset: Vec = (0.0, 0.0, 0.0)) -> int:
    """Place ``obj`` IN PLACE: rotate by ``R``, then move POINTS by ``offset``.

    Points and directions are kept apart deliberately.  A frame axis is a
    direction: translating it would make every face frame drift with the
    body's position and the solid would decode as nonsense.  ``m_3x3``
    (a Trf's basis) is composed as ``R . M`` rather than treated as three
    loose vectors, so a sketch plane's transform stays a transform.
    """
    n = 0
    ox, oy, oz = (float(offset[0]), float(offset[1]), float(offset[2]))
    if isinstance(obj, dict):
        for key, val in obj.items():
            if key == "m_3x3" and isinstance(val, list) and len(val) == 3 \
                    and all(_is_vec3(row) for row in val):
                obj[key] = _matmul(R, val)
                n += 1
            elif key in POINT_FIELDS and _is_vec3(val):
                p = _apply(R, val)
                obj[key] = [p[0] + ox, p[1] + oy, p[2] + oz]
                n += 1
            elif key in DIRECTION_FIELDS and _is_vec3(val):
                obj[key] = _apply(R, val)
                n += 1
            else:
                n += rotate_record(val, R, offset)
    elif isinstance(obj, list):
        for item in obj:
            n += rotate_record(item, R, offset)
    return n


def place_along(elements, start: Vec, end: Vec) -> int:
    """Place already-authored form elements as a rod from ``start`` to ``end``.

    The caller authors the body UPRIGHT at the origin with height =
    ``|end - start|``; this rotates +Z onto the segment and moves it to
    ``start``.  Returns the number of vectors touched.
    """
    d = [float(end[i]) - float(start[i]) for i in range(3)]
    R = rotation_from_z(d)
    n = 0
    for el in elements:
        if getattr(el, "rep", None) is not None:
            n += rotate_record(el.rep, R, start)
        n += rotate_record(el.obj, R, start)
    return n

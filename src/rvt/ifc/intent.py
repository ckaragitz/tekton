"""rvt.ifc.intent -- resolve an authored IFC into a placement-true, mapped
INTENT (spec v2): the two gaps of the front door ``tools/ifc_to_spec.py``
closed.

GAP (a) -- POSITIONS.  ``ifc_to_spec.py`` reads every position from
``IfcLocalPlacement`` and emits ``[0.0, 0.0]`` for everything.  Two facts
compose here, and this module resolves BOTH:

  1. the placement is a CHAIN (product -> storey -> building -> site), each
     link an ``IfcLocalPlacement`` whose ``RelativePlacement`` is an
     ``IfcAxis2Placement3D`` expressed in its parent's frame; the absolute
     placement is the composition root..leaf.  :func:`compose_placement`
     resolves the whole chain (and records every link) instead of trusting a
     single relative placement.
  2. our own three-d-stage IFC writer BAKES coordinates into the tessellated
     vertices and gives EVERY product the SAME identity ``IfcAxis2Placement3D``
     -- the chain genuinely composes to the identity, so the true position is
     NOT in the placement graph at all: it is in the ``IfcCartesianPointList3D``
     vertices.  :func:`analyze_product` therefore transforms each product's
     tessellated bodies by the composed placement into WORLD space and
     recovers the insertion point, footprint orientation, dims and elevation
     from the geometry (upright-box decomposition + a minimum-area oriented
     footprint).  When a file DOES carry real relative placements the same
     formula (world = composed_chain @ local geometry) stays exact, so both
     writer styles resolve.

GAP (b) -- MAPPING.  Every board carries a Pset whose property NAMES are the
tekton-ifc TAGGING CONTRACT (PanelName / Voltage / Phases / Wires /
BusRating / MainsType / FedFrom / FeederEntry / Mounting ...).  The contract
IS the join key: :func:`plan_families` maps each equipment item onto ONE of
OUR generated-content constructors (``rvt.famgen.factory.make_panelboard``
for the distribution / lighting / receptacle panelboards -- catalog FACTS
where the Eaton Pow-R-Line member covers the rating; ``make_transformer``
for the dry-type transformer; :func:`make_house_switchboard` for the
2500 A switchboard, which no panelboard member covers -- the factory
REFUSES it honestly and the house family is built from OUR OWN IFC-modeled
dimensions), with the Pset values riding as parameter VALUES.

Also resolved (the rest of the room):
  * the ROOM SHELL proxy's own solids -> real wall runs (centerline,
    thickness, height, door openings from the leaf/header solids), the
    floor slab footprint, the housekeeping pads, and the cut-away front wall
    inferred (flagged ``synthesized``);
  * the NEC 110.26 CLEARANCE proxy -> one clearance zone per equipment tag
    (depth / width / height, Condition-2 check), disposition = annotation
    (omitted from the model with a stated reason);
  * the FEEDER TREE: every ``FedFrom`` becomes a directed feeder edge,
    CORROBORATED by the conduit-run geometry (the ``conduit_<from>_<to>``
    named solids of the ``IfcCableCarrierSegment``) -> a circuit plan ready
    for ``rvt.mep`` (panel -> load, rating, poles, voltage).

Output: :func:`resolve_intent` -> :class:`IntentModel`;
:func:`intent_to_json` / :func:`write_intent` emit the versioned
``*.intent.json`` (spec v2).  Every resolved number carries a provenance
string ("placement-chain", "geometry-recovered", "pset", "inferred").

Provenance: the IFC consumed is OUR OWN authoring (three-d-stage writer);
this module only READS it.  Pure ifcopenshell + numpy (no OpenCascade
kernel: we analyse the exact vertices the writer wrote).

TERRITORY: new module of the ifc-room stream (``src/rvt/ifc/intent.py``);
imports, never edits, ``rvt.famgen`` and the sibling ``rvt.ifc`` modules.
"""
from __future__ import annotations

import json
import math
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# LAZY (perf-coldstart): numpy loads on first numeric use, so importing this
# module -- which the whole front door does -- is instant and survives a
# sandbox without numpy; the geometry paths are unchanged once touched.
from .._lazyimp import lazy_import

np = lazy_import("numpy", globals(), "np",
                 hint="IFC placement / geometry resolution")

# LAZY (issue #6): ifcopenshell (the real library OR the bundled steplite
# shim) loads on first IFC read, never at front-door import -- the real
# package's eager import taxed every prompt-only process and dragged numpy +
# shapely in with it.  resolve_intent() gates on _load_ifcos().
ifcopenshell = lazy_import("ifcopenshell", globals(), "ifcopenshell",
                           hint="reading an .ifc")
_ue = lazy_import("ifcopenshell.util.element", globals(), "_ue",
                  hint="reading an .ifc")


def _load_ifcos() -> bool:
    """Perform the deferred import now (the first touch of each proxy imports
    it and rebinds this module's global to the real module); False when no
    ifcopenshell -- real or shim -- is importable, the one condition
    resolve_intent refuses on."""
    try:
        return callable(ifcopenshell.open) and callable(_ue.get_psets)
    except Exception:  # pragma: no cover - the shim is always bundled
        return False

__all__ = [
    "INTENT_VERSION", "IntentError", "Placement", "GeomItem", "ProductGeometry",
    "Equipment", "WallRun", "DoorOpening", "RoomShell", "ClearanceZone",
    "FeederEdge", "FamilyPlan", "IntentModel",
    "compose_placement", "axis2placement3d_matrix", "identity_matrix",
    "is_identity", "analyze_product",
    "resolve_intent", "intent_to_json", "write_intent", "plan_families",
    "make_house_switchboard", "resolve_products",
]

INTENT_VERSION = "2.0"
FT_PER_M = 3.280839895013123
IN_PER_M = 39.37007874015748

#: horizontal / vertical rounding for grouping vertices (metres)
_ROUND = 5

#: OST built-in categories the placement layer needs
OST_ELECTRICAL_EQUIPMENT = -2001040
OST_WALLS = -2000011


class IntentError(RuntimeError):
    """The IFC cannot be resolved (missing units / no products / bad file)."""


# ============================================================================
# small vector helpers
# ============================================================================

def _f(x: Any, nd: int = 4) -> float:
    v = round(float(x), nd)
    return v + 0.0 if v != 0 else 0.0        # normalise -0.0


def _vf(v: Iterable[Any], nd: int = 4) -> List[float]:
    return [_f(x, nd) for x in v]


def _norm(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _unit2(x: float, y: float) -> Tuple[float, float]:
    n = math.hypot(x, y)
    return (x / n, y / n) if n > 1e-12 else (0.0, 0.0)


# ============================================================================
# GAP (a) part 1 -- PLACEMENT CHAIN RESOLUTION
# ============================================================================

def axis2placement3d_matrix(a2p) -> np.ndarray:
    """4x4 of an ``IfcAxis2Placement3D`` (or 2D) per ISO 16739:
    Z = Axis (default 0,0,1), X = RefDirection projected onto the plane
    normal to Z (default 1,0,0), Y = Z x X, origin = Location."""
    m = np.eye(4)
    if a2p is None:
        return m
    loc = list(a2p.Location.Coordinates) if getattr(a2p, "Location", None) else [0.0, 0.0, 0.0]
    while len(loc) < 3:
        loc.append(0.0)
    if a2p.is_a("IfcAxis2Placement3D"):
        z = np.array(list(a2p.Axis.DirectionRatios), float) if a2p.Axis else np.array([0.0, 0.0, 1.0])
        x = (np.array(list(a2p.RefDirection.DirectionRatios), float)
             if a2p.RefDirection else np.array([1.0, 0.0, 0.0]))
    else:  # IfcAxis2Placement2D: RefDirection in XY, Z up
        z = np.array([0.0, 0.0, 1.0])
        x = np.array([1.0, 0.0, 0.0])
        if getattr(a2p, "RefDirection", None):
            d = list(a2p.RefDirection.DirectionRatios)
            x = np.array([d[0], d[1] if len(d) > 1 else 0.0, 0.0])
    while len(z) < 3:
        z = np.append(z, 0.0)
    while len(x) < 3:
        x = np.append(x, 0.0)
    z = _norm(z)
    # RefDirection need not be exactly perpendicular: project onto plane _|_ Z
    x = x - np.dot(x, z) * z
    if np.linalg.norm(x) < 1e-12:
        # degenerate ref direction: pick any perpendicular
        x = np.cross(z, np.array([0.0, 0.0, 1.0]))
        if np.linalg.norm(x) < 1e-12:
            x = np.array([1.0, 0.0, 0.0])
    x = _norm(x)
    y = np.cross(z, x)
    m[:3, 0], m[:3, 1], m[:3, 2] = x, y, z
    m[:3, 3] = np.array(loc[:3], float)
    return m


def transformation_operator_matrix(op) -> np.ndarray:
    """4x4 of an ``IfcCartesianTransformationOperator3D`` (mapped items)."""
    m = np.eye(4)
    if op is None:
        return m
    x = np.array(list(op.Axis1.DirectionRatios), float) if getattr(op, "Axis1", None) else np.array([1.0, 0.0, 0.0])
    y = np.array(list(op.Axis2.DirectionRatios), float) if getattr(op, "Axis2", None) else np.array([0.0, 1.0, 0.0])
    z = np.array(list(op.Axis3.DirectionRatios), float) if getattr(op, "Axis3", None) else np.array([0.0, 0.0, 1.0])
    for v in (x, y, z):
        while len(v) < 3:
            v = np.append(v, 0.0)
    x = _norm(x)
    z = _norm(np.cross(x, y)) if np.linalg.norm(np.cross(x, y)) > 1e-12 else np.array([0.0, 0.0, 1.0])
    y = np.cross(z, x)
    s = float(getattr(op, "Scale", None) or 1.0)
    s2 = float(getattr(op, "Scale2", None) or s)
    s3 = float(getattr(op, "Scale3", None) or s)
    org = np.zeros(3)
    if getattr(op, "LocalOrigin", None):
        c = list(op.LocalOrigin.Coordinates)
        while len(c) < 3:
            c.append(0.0)
        org = np.array(c[:3], float)
    m[:3, 0], m[:3, 1], m[:3, 2], m[:3, 3] = x * s, y * s2, z * s3, org
    return m


_EYE4 = ((1.0, 0.0, 0.0, 0.0), (0.0, 1.0, 0.0, 0.0),
         (0.0, 0.0, 1.0, 0.0), (0.0, 0.0, 0.0, 1.0))


def identity_matrix() -> List[List[float]]:
    """A plain-list 4x4 identity: the numpy-free ``Placement`` matrix for
    routes (prompt authoring) that carry no IFC placement chain."""
    return [list(r) for r in _EYE4]


def is_identity(m, tol: float = 1e-9) -> bool:
    """Identity test for a 4x4 given as an ndarray OR nested lists; mirrors
    the previous ``np.allclose(m, np.eye(4), atol=tol)`` exactly (same atol
    + numpy's default rtol=1e-5 against the eye entries), numpy-free."""
    for i in range(4):
        row = m[i]
        for j in range(4):
            e = _EYE4[i][j]
            if abs(float(row[j]) - e) > tol + 1e-5 * e:
                return False
    return True


@dataclass
class Placement:
    """A product's RESOLVED absolute placement + the chain it came from.
    ``matrix`` is a 4x4: an ``np.ndarray`` on the IFC route, plain nested
    lists on the prompt route (``identity_matrix()``) -- every accessor
    here handles both, so carrying a Placement never requires numpy."""
    matrix: Any                            # 4x4 absolute (project length units)
    chain: List[dict] = dc_field(default_factory=list)   # leaf-first links
    warnings: List[str] = dc_field(default_factory=list)

    def _col(self, j: int) -> List[float]:
        m = self.matrix
        if hasattr(m, "shape"):            # ndarray (no numpy import needed)
            return [float(m[i, j]) for i in range(3)]
        return [float(m[i][j]) for i in range(3)]

    @property
    def origin(self):
        m = self.matrix
        if hasattr(m, "shape"):
            return m[:3, 3]                # ndarray: unchanged (vector math ok)
        return self._col(3)

    @property
    def identity(self) -> bool:
        return is_identity(self.matrix)

    @property
    def chain_depth(self) -> int:
        return len(self.chain)

    def as_json(self, scale_m: float = 1.0) -> dict:
        return {
            "absolute_origin_m": _vf([v * scale_m for v in self._col(3)]),
            "absolute_xdir": _vf(self._col(0)),
            "absolute_zdir": _vf(self._col(2)),
            "is_identity": self.identity,
            "chain_depth": self.chain_depth,
            "chain": [{k: v for k, v in link.items()} for link in self.chain],
            "warnings": list(self.warnings),
        }


def compose_placement(obj_placement) -> Placement:
    """RESOLVE an ``IfcObjectPlacement`` (an ``IfcLocalPlacement`` chain up
    to the site) into the absolute 4x4.

    absolute(product) = M_rel(site) @ M_rel(building) @ ... @ M_rel(product):
    each link's ``RelativePlacement`` is expressed in its parent's frame, so
    the composition runs root -> leaf.  Every link is recorded (id, class,
    relative origin, identity flag) so the intent can PROVE how the position
    was derived.  ``IfcGridPlacement`` (unused by our writer) resolves to
    the identity with a warning.
    """
    if obj_placement is None:
        return Placement(np.eye(4), [], ["product has no ObjectPlacement"])
    chain: List[dict] = []
    mats: List[np.ndarray] = []
    warnings: List[str] = []
    node = obj_placement
    guard = 0
    while node is not None and guard < 64:
        guard += 1
        if node.is_a("IfcLocalPlacement"):
            rel = node.RelativePlacement
            mrel = axis2placement3d_matrix(rel) if rel is not None else np.eye(4)
            chain.append({
                "id": node.id(), "class": node.is_a(),
                "relative_placement": (rel.is_a() + f" #{rel.id()}") if rel is not None else None,
                "relative_origin": _vf(mrel[:3, 3]),
                "relative_identity": is_identity(mrel),
            })
            mats.append(mrel)
            node = node.PlacementRelTo
        else:
            warnings.append(f"unsupported placement {node.is_a()} #{node.id()} "
                            "in chain: treated as identity")
            chain.append({"id": node.id(), "class": node.is_a(),
                          "relative_placement": None, "relative_origin": [0.0, 0.0, 0.0],
                          "relative_identity": True, "unsupported": True})
            mats.append(np.eye(4))
            break
    m = np.eye(4)
    for mrel in reversed(mats):            # root -> leaf
        m = m @ mrel
    return Placement(m, chain, warnings)


# ============================================================================
# GAP (a) part 2 -- TESSELLATED GEOMETRY -> world points, boxes, footprint
# ============================================================================

def _faceset_points_tris(item) -> Tuple[Optional[np.ndarray], Optional[np.ndarray]]:
    """(points Nx3 LOCAL, tris Mx3 zero-based) of a tessellated item."""
    if item.is_a("IfcTriangulatedFaceSet") or item.is_a("IfcTriangulatedIrregularNetwork"):
        pts = np.array(item.Coordinates.CoordList, float)
        idx = np.array(item.CoordIndex, int) if item.CoordIndex else np.zeros((0, 3), int)
        if getattr(item, "PnIndex", None):
            pn = np.array(item.PnIndex, int)
            idx = pn[idx - 1]
        return pts.reshape(-1, 3), (idx - 1).reshape(-1, 3)
    if item.is_a("IfcPolygonalFaceSet"):
        pts = np.array(item.Coordinates.CoordList, float)
        tris = []
        for face in item.Faces:
            ci = list(face.CoordIndex)
            for k in range(1, len(ci) - 1):
                tris.append((ci[0], ci[k], ci[k + 1]))
        return pts.reshape(-1, 3), np.array(tris, int).reshape(-1, 3) - 1
    if item.is_a("IfcFacetedBrep"):
        pts_list, tris, index = [], [], {}
        for face in item.Outer.CfsFaces:
            for bound in face.Bounds:
                loop = bound.Bound
                if not loop.is_a("IfcPolyLoop"):
                    continue
                ids = []
                for p in loop.Polygon:
                    c = tuple(float(x) for x in p.Coordinates)
                    if c not in index:
                        index[c] = len(pts_list)
                        pts_list.append(c)
                    ids.append(index[c])
                for k in range(1, len(ids) - 1):
                    tris.append((ids[0] + 1, ids[k] + 1, ids[k + 1] + 1))
        if not pts_list:
            return None, None
        return np.array(pts_list, float), np.array(tris, int) - 1
    return None, None


def _apply(m: np.ndarray, pts: np.ndarray) -> np.ndarray:
    if pts.size == 0:
        return pts
    homo = np.c_[pts, np.ones(len(pts))]
    return (homo @ m.T)[:, :3]


def _style_name(f, item) -> Tuple[Optional[str], float]:
    """(styled-item name, max surface transparency) of a representation item."""
    name, transp = None, 0.0
    for si in f.get_inverse(item):
        if not si.is_a("IfcStyledItem"):
            continue
        name = si.Name or name
        for pa in si.Styles or []:
            targets = pa.Styles if pa.is_a("IfcPresentationStyleAssignment") else [pa]
            for st in targets:
                if st is not None and st.is_a("IfcSurfaceStyle"):
                    for rend in st.Styles:
                        if rend.is_a("IfcSurfaceStyleRendering") and rend.Transparency:
                            transp = max(transp, float(rend.Transparency))
    return name, transp


@dataclass
class GeomItem:
    """One tessellated body of a product, transformed into WORLD (metres)."""
    item_id: int
    name: Optional[str]
    rep_identifier: str
    transparency: float
    points: np.ndarray                      # Nx3 world, metres
    tris: np.ndarray                        # Mx3 zero-based
    boxes: List[dict] = dc_field(default_factory=list)
    n_components: int = 0

    @property
    def n_tris(self) -> int:
        return int(len(self.tris))

    @property
    def lo(self) -> np.ndarray:
        return self.points.min(0)

    @property
    def hi(self) -> np.ndarray:
        return self.points.max(0)

    @property
    def extent(self) -> np.ndarray:
        return self.hi - self.lo

    @property
    def center(self) -> np.ndarray:
        return (self.lo + self.hi) / 2.0

    @property
    def is_all_boxes(self) -> bool:
        return bool(self.boxes) and len(self.boxes) == self.n_components

    def as_json(self) -> dict:
        return {
            "item_id": self.item_id, "name": self.name,
            "rep": self.rep_identifier, "triangles": self.n_tris,
            "transparency": _f(self.transparency, 3),
            "lo_m": _vf(self.lo), "hi_m": _vf(self.hi), "extent_m": _vf(self.extent),
            "components": self.n_components,
            "boxes": [{k: (_vf(v) if isinstance(v, (list, tuple, np.ndarray)) else _f(v))
                       for k, v in b.items()} for b in self.boxes],
            "is_box": self.is_all_boxes,
        }


# ---- box decomposition (connected components + upright-box test) -----------

def _components(points: np.ndarray, tris: np.ndarray) -> List[np.ndarray]:
    """Connected components of a triangle soup, joined on ROUNDED vertex
    coordinates (the three.js writer duplicates vertices per face).
    Returns a list of triangle-index arrays."""
    if len(tris) == 0:
        return []
    keys = [tuple(np.round(p, _ROUND)) for p in points]
    parent: Dict[tuple, tuple] = {k: k for k in keys}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for a, b, c in tris:
        union(keys[a], keys[b])
        union(keys[b], keys[c])
    comps: Dict[tuple, List[int]] = defaultdict(list)
    for ti, t in enumerate(tris):
        comps[find(keys[t[0]])].append(ti)
    return [np.array(v, int) for v in comps.values()]


def _rect_from_ring(bot: np.ndarray, tol: float = 1e-6):
    """4 coplanar 2-D points -> (centre, xdir, xdim, ydim) if a rectangle
    (tolerances are relative to the ring's scale so 3-decimal export
    coordinates and rounding noise both pass)."""
    c = bot.mean(0)
    ang = np.arctan2(bot[:, 1] - c[1], bot[:, 0] - c[0])
    ring = bot[np.argsort(ang)]
    e = [ring[(i + 1) % 4] - ring[i] for i in range(4)]
    n = [float(np.linalg.norm(x)) for x in e]
    scale = max(max(n), 1e-9)
    rel = 5e-3
    if not (abs(n[0] - n[2]) < rel * scale and abs(n[1] - n[3]) < rel * scale):
        return None
    if abs(np.dot(e[0], e[1])) > rel * (n[0] * n[1] + 1e-12):
        return None
    xd, yd = n[0], n[1]
    if xd < tol or yd < tol:
        return None
    return c, e[0] / xd, xd, yd


def box_from_points(pts: np.ndarray, tol: float = 1e-5) -> Optional[dict]:
    """If ``pts`` are exactly the 8 corners of an UPRIGHT rectangular prism
    (rotation about Z allowed), return its base-centre insertion point,
    xdir, xdim / ydim / height and world lo/hi; else None."""
    if pts is None or len(pts) == 0:
        return None
    u = np.unique(np.round(pts, _ROUND), axis=0)
    if len(u) != 8:
        return None
    zs = np.unique(np.round(u[:, 2], _ROUND))
    if len(zs) != 2:
        return None
    z0, z1 = float(zs[0]), float(zs[1])
    h = z1 - z0
    if h < tol:
        return None
    bot = u[np.isclose(u[:, 2], z0, atol=1e-5)]
    top = u[np.isclose(u[:, 2], z1, atol=1e-5)]
    if len(bot) != 4 or len(top) != 4:
        return None
    r = _rect_from_ring(bot[:, :2])
    if r is None:
        return None
    c, xdir, xd, yd = r
    tb = np.round(np.sort(np.round(top[:, :2], _ROUND), axis=0), _ROUND)
    bb = np.round(np.sort(np.round(bot[:, :2], _ROUND), axis=0), _ROUND)
    if not np.allclose(tb, bb, atol=max(2e-3, 1e-3 * max(xd, yd))):
        return None
    lo = pts.min(0)
    hi = pts.max(0)
    return {
        "origin": [float(c[0]), float(c[1]), z0],       # base-centre
        "center": [float(c[0]), float(c[1]), z0 + h / 2.0],
        "xdir": [float(xdir[0]), float(xdir[1]), 0.0],
        "xdim": float(xd), "ydim": float(yd), "height": float(h),
        "lo": [float(x) for x in lo], "hi": [float(x) for x in hi],
        "triangles": 12,
    }


def decompose_boxes(points: np.ndarray, tris: np.ndarray) -> Tuple[List[dict], int]:
    """Split a triangle soup into connected components; test each 12-tri
    component as an upright box.  Returns (boxes, n_components)."""
    comps = _components(points, tris)
    boxes: List[dict] = []
    for ts in comps:
        if len(ts) != 12:                       # a box = 6 quads = 12 tris
            continue
        vidx = sorted({int(i) for t in tris[ts] for i in t})
        b = box_from_points(points[vidx])
        if b:
            boxes.append(b)
    return boxes, len(comps)


# ---- oriented footprint (minimum-area enclosing rectangle) ------------------

def _convex_hull(pts2: np.ndarray) -> np.ndarray:
    """Andrew's monotone chain; returns hull vertices CCW (no repeat)."""
    p = np.unique(np.round(pts2, 9), axis=0)
    if len(p) < 3:
        return p
    p = p[np.lexsort((p[:, 1], p[:, 0]))]

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[np.ndarray] = []
    for pt in p:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], pt) <= 0:
            lower.pop()
        lower.append(pt)
    upper: List[np.ndarray] = []
    for pt in reversed(p):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], pt) <= 0:
            upper.pop()
        upper.append(pt)
    hull = np.array(lower[:-1] + upper[:-1])
    return hull if len(hull) else p


def oriented_footprint(pts_xy: np.ndarray) -> dict:
    """Minimum-area enclosing rectangle of a 2-D point set (rotating calipers
    over the convex hull's edges).  Returns centre, unit xdir (long axis),
    xdim >= ydim, area and the yaw of the long axis in degrees."""
    p = np.asarray(pts_xy, float)
    if len(p) == 0:
        raise ValueError("empty point set")
    hull = _convex_hull(p)
    best = None
    if len(hull) < 3:                      # degenerate (line/point)
        lo, hi = p.min(0), p.max(0)
        d = hi - lo
        ang = math.atan2(d[1], d[0]) if np.linalg.norm(d) > 1e-9 else 0.0
        return {"center": [float((lo[0] + hi[0]) / 2), float((lo[1] + hi[1]) / 2)],
                "xdir": [math.cos(ang), math.sin(ang)],
                "xdim": float(np.linalg.norm(d)), "ydim": 0.0, "area": 0.0,
                "yaw_deg": math.degrees(ang)}
    for i in range(len(hull)):
        e = hull[(i + 1) % len(hull)] - hull[i]
        n = float(np.linalg.norm(e))
        if n < 1e-12:
            continue
        ux = e / n
        uy = np.array([-ux[1], ux[0]])
        px = hull @ ux
        py = hull @ uy
        w = float(px.max() - px.min())
        h = float(py.max() - py.min())
        area = w * h
        if best is None or area < best[0] - 1e-12:
            cx = (px.max() + px.min()) / 2
            cy = (py.max() + py.min()) / 2
            centre = ux * cx + uy * cy
            best = (area, w, h, ux, uy, centre)
    assert best is not None
    area, w, h, ux, uy, centre = best
    if h > w:                                # long axis = xdir
        w, h, ux = h, w, uy
    ang = math.atan2(ux[1], ux[0])
    # canonicalise the direction into (-90, 90]
    if ang <= -math.pi / 2 - 1e-9:
        ang += math.pi
        ux = -ux
    elif ang > math.pi / 2 + 1e-9:
        ang -= math.pi
        ux = -ux
    return {"center": [float(centre[0]), float(centre[1])],
            "xdir": [float(ux[0]), float(ux[1])],
            "xdim": float(w), "ydim": float(h), "area": float(area),
            "yaw_deg": math.degrees(ang)}


# ---- product analysis -------------------------------------------------------

@dataclass
class ProductGeometry:
    """All tessellated bodies of a product in WORLD space + derived shape."""
    items: List[GeomItem]
    scale: float = 1.0

    @property
    def has_body(self) -> bool:
        return bool(self.items)

    def points(self, names: Optional[Iterable[str]] = None) -> np.ndarray:
        sel = [it.points for it in self.items
               if names is None or (it.name in set(names))]
        return np.vstack(sel) if sel else np.zeros((0, 3))

    def item(self, name: str) -> Optional[GeomItem]:
        for it in self.items:
            if it.name == name:
                return it
        return None

    def items_matching(self, *needles: str) -> List[GeomItem]:
        out = []
        for it in self.items:
            nm = (it.name or "").lower()
            if any(n in nm for n in needles):
                out.append(it)
        return out

    @property
    def lo(self) -> np.ndarray:
        return self.points().min(0)

    @property
    def hi(self) -> np.ndarray:
        return self.points().max(0)

    @property
    def extent(self) -> np.ndarray:
        return self.hi - self.lo

    @property
    def center(self) -> np.ndarray:
        return (self.lo + self.hi) / 2.0

    @property
    def all_boxes(self) -> bool:
        return all(it.is_all_boxes for it in self.items)

    def footprint(self, names: Optional[Iterable[str]] = None) -> dict:
        return oriented_footprint(self.points(names)[:, :2])

    def as_json(self) -> dict:
        if not self.items:
            return {"has_body": False, "items": []}
        return {
            "has_body": True,
            "lo_m": _vf(self.lo), "hi_m": _vf(self.hi), "extent_m": _vf(self.extent),
            "center_m": _vf(self.center),
            "footprint": {k: (_vf(v) if isinstance(v, list) else _f(v))
                          for k, v in self.footprint().items()},
            "all_boxes": self.all_boxes,
            "triangles": sum(it.n_tris for it in self.items),
            "items": [it.as_json() for it in self.items],
        }


def _collect_items(f, rep_items, base_m: np.ndarray, scale: float,
                   rep_identifier: str, out: List[GeomItem]) -> None:
    for item in rep_items:
        if item.is_a("IfcMappedItem"):
            src = item.MappingSource
            m_origin = axis2placement3d_matrix(src.MappingOrigin)
            m_target = transformation_operator_matrix(item.MappingTarget)
            # mapped-representation coords are relative to the mapping origin,
            # then moved by the target operator
            m_item = base_m @ m_target @ np.linalg.inv(m_origin)
            _collect_items(f, src.MappedRepresentation.Items, m_item, scale,
                           rep_identifier + "/mapped", out)
            continue
        pts, tris = _faceset_points_tris(item)
        if pts is None or len(pts) == 0:
            continue
        world = _apply(base_m, pts) * scale
        name, transp = _style_name(f, item)
        boxes, ncomp = decompose_boxes(world, tris)
        out.append(GeomItem(item_id=item.id(), name=name, rep_identifier=rep_identifier,
                            transparency=transp, points=world, tris=tris,
                            boxes=boxes, n_components=ncomp))


def analyze_product(f, prod, *, scale: float = 1.0,
                    placement: Optional[Placement] = None) -> Tuple[Placement, ProductGeometry]:
    """Resolve ``prod``'s placement chain and transform every tessellated
    body into WORLD metres (world = composed_chain @ local_vertices * scale).
    """
    plc = placement or compose_placement(getattr(prod, "ObjectPlacement", None))
    items: List[GeomItem] = []
    reps = prod.Representation.Representations if getattr(prod, "Representation", None) else []
    for rep in reps:
        _collect_items(f, rep.Items, plc.matrix, scale,
                       str(rep.RepresentationIdentifier or ""), items)
    return plc, ProductGeometry(items=items, scale=scale)


# ============================================================================
# semantic vocabulary
# ============================================================================

#: styled-item name prefixes the three-d-stage writer uses (our own
#: authoring vocabulary): part-role tags for equipment sub-solids.
FRONT_FEATURES = ("door", "latch", "nameplate", "window", "handle", "escutcheon",
                  "display", "meter", "breaker", "hasp", "hinge", "cover_seam", "louver")
BACK_FEATURES = ("strut", "backing", "standoff", "hub")
BODY_FEATURES = ("enclosure", "body", "skid", "kick_plate", "housing", "can", "bus_bar")

WALL_ITEM_RX = re.compile(r"^wall_", re.I)
HEADER_RX = re.compile(r"header", re.I)
DOOR_LEAF_RX = re.compile(r"^door_.*leaf", re.I)
DOOR_ANY_RX = re.compile(r"^door_", re.I)
SLAB_RX = re.compile(r"slab|floor", re.I)
PAD_RX = re.compile(r"^pad_(.*)", re.I)
CLEARANCE_RX = re.compile(r"^clearance_(.*)", re.I)
CONDUIT_RX = re.compile(r"^conduit_([a-z0-9]+)_([a-z0-9]+)", re.I)

#: pset property NAMES of the tekton-ifc tagging contract (the join key)
CONTRACT_KEYS = ("PanelName", "Voltage", "Phases", "Wires", "BusRating",
                 "MainsType", "MainsRating", "ShortCircuitRatingkA", "Mounting",
                 "NumberOfCircuits", "NeutralRating", "FedFrom", "FeederEntry",
                 "MainDevice", "Sections")

#: IFC class -> coarse kind (refined by predefined type + psets below)
KIND_BY_CLASS = {
    "IfcElectricDistributionBoard": "board",
    "IfcTransformer": "transformer",
    "IfcSwitchingDevice": "switchgear",
    "IfcCableCarrierSegment": "conduit_run",
    "IfcCableSegment": "conduit_run",
    "IfcDiscreteAccessory": "support",
    "IfcBuildingElementProxy": "proxy",
    "IfcSpace": "space",
    "IfcWall": "wall", "IfcWallStandardCase": "wall",
    "IfcLightFixture": "light_fixture",
}

#: equipment kinds that map to OUR generated content
GENERATED_KINDS = ("switchboard", "distribution_panelboard", "lighting_panelboard",
                   "receptacle_panelboard", "panelboard", "transformer")

FLOOR_KINDS = ("switchboard", "transformer", "switchgear")
WALL_KINDS = ("distribution_panelboard", "lighting_panelboard", "receptacle_panelboard",
              "panelboard", "ground_bus")


# ============================================================================
# psets: normalise the tagging contract
# ============================================================================

def _psets(prod) -> Dict[str, Dict[str, Any]]:
    """{pset name: {prop: value}} for a product (occurrence + its type)."""
    out: Dict[str, Dict[str, Any]] = {}
    try:
        raw = _ue.get_psets(prod) or {}
    except Exception:
        raw = {}
    for pname, props in raw.items():
        clean = {k: v for k, v in (props or {}).items() if k != "id"}
        if clean:
            out[pname] = clean
    return out


def _first(psets: Dict[str, Dict[str, Any]], *keys: str) -> Any:
    for props in psets.values():
        for k in keys:
            if k in props and props[k] not in (None, ""):
                return props[k]
    return None


def parse_voltage(v: Any) -> Dict[str, Any]:
    """'480Y/277 V' -> {ll: 480, ln: 277, phases 3, wires 4, system '480Y/277'}."""
    if v is None:
        return {}
    s = str(v).strip()
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*Y\s*/\s*(\d+(?:\.\d+)?)", s, re.I)
    if m:
        ll, ln = float(m.group(1)), float(m.group(2))
        return {"ll": ll, "ln": ln, "phases": 3, "wires": 4,
                "system": f"{int(ll) if ll == int(ll) else ll}Y/{int(ln) if ln == int(ln) else ln}",
                "raw": s}
    nums = [float(x) for x in re.findall(r"\d+(?:\.\d+)?", s)]
    if nums:
        return {"ll": max(nums), "ln": None, "system": f"{max(nums):g}", "raw": s}
    return {"raw": s}


def normalize_contract(psets: Dict[str, Dict[str, Any]], *, name: str,
                       object_type: Optional[str], description: Optional[str],
                       tag: Optional[str]) -> Dict[str, Any]:
    """Fold whichever schedule pset a board carries (PanelSchedule /
    SwitchboardSchedule / TransformerSchedule) into the tagging-contract
    field names, filling gaps from the name / object type text.  Every value
    records where it came from."""
    src: Dict[str, str] = {}
    con: Dict[str, Any] = {}

    def put(key: str, value: Any, provenance: str):
        if value in (None, "") or key in con:
            return
        con[key] = value
        src[key] = provenance

    # direct contract keys, from any pset
    for pname, props in psets.items():
        for k, v in props.items():
            if k in CONTRACT_KEYS:
                put(k, v, f"pset:{pname}.{k}")
    # aliases
    for pname, props in psets.items():
        if "MainDevice" in props:
            put("MainsType", "Main breaker" if "breaker" in str(props["MainDevice"]).lower()
                else str(props["MainDevice"]), f"pset:{pname}.MainDevice")
        if "RatingkVA" in props:
            put("RatingkVA", props["RatingkVA"], f"pset:{pname}.RatingkVA")
        for k in ("Primary", "Secondary", "ImpedancePercent", "TemperatureRise",
                  "Manufacturer", "ModelLabel", "Sections", "RoomName", "ClearWidth",
                  "ClearDepth", "ClearHeight", "Egress", "StrutSize", "RodSize",
                  "MaxSpacingM", "AttachTo"):
            if k in props:
                put(k, props[k], f"pset:{pname}.{k}")
    # PanelName defaults to the tag / leading name token
    if "PanelName" not in con:
        put("PanelName", tag or (name.split()[0] if name else None), "tag" if tag else "name")
    # ratings hidden in the name / object type text
    hay = " ".join(x for x in (name, object_type, description) if x)
    if "BusRating" not in con:
        m = re.search(r"(\d{2,5})\s*A\b", hay)
        if m:
            put("BusRating", float(m.group(1)), "name-text (NNN A)")
    if "NumberOfCircuits" not in con:
        m = re.search(r"(\d{1,3})[- ]?(?:space|circuit|ckt)", hay, re.I)
        if m:
            put("NumberOfCircuits", int(m.group(1)), "name-text (NN space)")
    if "MainsType" not in con:
        if re.search(r"\bMLO\b|main lugs", hay, re.I):
            put("MainsType", "Main lugs only", "name-text")
        elif re.search(r"\bMB\b|\bMCB\b|main breaker", hay, re.I):
            put("MainsType", "Main breaker", "name-text")
    if "Voltage" not in con:
        m = re.search(r"(\d{3}Y/\d{2,3})\s*V?", hay)
        if m:
            put("Voltage", m.group(1) + " V", "name-text")
    if "MainsRating" not in con and con.get("BusRating") is not None:
        put("MainsRating", con.get("BusRating"), "= BusRating (single-rating device)")
    # voltage decomposition
    vs = parse_voltage(con.get("Voltage"))
    con["_voltage"] = vs
    if "Phases" not in con and vs.get("phases"):
        put("Phases", vs["phases"], "derived from voltage system")
    if "Wires" not in con and vs.get("wires"):
        put("Wires", vs["wires"], "derived from voltage system")
    con["_provenance"] = src
    return con


# ============================================================================
# EQUIPMENT INTENT
# ============================================================================

@dataclass
class Equipment:
    """One equipment product, fully resolved."""
    step_id: int
    guid: str
    ifc_class: str
    predefined_type: Optional[str]
    name: str
    tag: str
    description: Optional[str]
    object_type: Optional[str]
    type_name: Optional[str]
    kind: str
    psets: Dict[str, Dict[str, Any]]
    contract: Dict[str, Any]
    placement: Placement
    geometry: ProductGeometry
    # resolved placement intent (metres / degrees, world)
    insertion_m: List[float] = dc_field(default_factory=lambda: [0.0, 0.0, 0.0])
    front_normal: List[float] = dc_field(default_factory=lambda: [0.0, -1.0, 0.0])
    frame3x3: List[List[float]] = dc_field(default_factory=list)
    frame_kind: str = "yaw"                 # 'yaw' (floor gear) | 'upright' (wall gear)
    yaw_deg: float = 0.0
    dims_m: Dict[str, float] = dc_field(default_factory=dict)
    elevation_m: float = 0.0
    mounting: str = "floor"
    mounting_height_m: Optional[float] = None
    position_source: str = "geometry-recovered"
    notes: List[str] = dc_field(default_factory=list)
    fed_from: Optional[str] = None
    disposition: str = "generated-family"   # or 'recorded' / 'omitted'

    def as_json(self, *, include_items: bool = True) -> dict:
        g = self.geometry.as_json()
        if not include_items and isinstance(g, dict):
            g = {k: v for k, v in g.items() if k != "items"}
        return {
            "tag": self.tag, "name": self.name, "kind": self.kind,
            "ifcClass": self.ifc_class, "predefinedType": self.predefined_type,
            "guid": self.guid, "step_id": self.step_id,
            "typeName": self.type_name, "objectType": self.object_type,
            "description": self.description,
            "disposition": self.disposition,
            "position_m": _vf(self.insertion_m[:2]),
            "elevation_m": _f(self.elevation_m),
            "insertion_m": _vf(self.insertion_m),
            "positionSource": self.position_source,
            "orientation": {
                "front_normal": _vf(self.front_normal),
                "yaw_deg": _f(self.yaw_deg, 2),
                "frame_kind": self.frame_kind,
                "frame3x3_rows_are_family_axes_in_world": [_vf(r) for r in self.frame3x3],
                "convention": ("family +X = width axis; front = family -Y (yaw frame) "
                               "for floor equipment, or family +Z = front normal / "
                               "family +Y = up (upright work-plane frame) for wall equipment"),
            },
            "dims_m": {k: _f(v) for k, v in self.dims_m.items()},
            "mounting": self.mounting,
            "mounting_height_m": None if self.mounting_height_m is None else _f(self.mounting_height_m),
            "fedFrom": self.fed_from,
            "contract": {k: v for k, v in self.contract.items()},
            "psets": self.psets,
            "placementChain": self.placement.as_json(self.geometry.scale),
            "geometry": g,
            "notes": list(self.notes),
        }


def _classify_equipment(prod, psets: Dict[str, Dict[str, Any]], contract: Dict[str, Any]) -> str:
    """Refine the IFC class into an actionable equipment kind by predefined
    type + the tagging-contract pset (the pset IS the join key)."""
    cls = prod.is_a()
    pdt = str(getattr(prod, "PredefinedType", "") or "").upper()
    hay = " ".join(str(x) for x in (prod.Name, prod.Description, getattr(prod, "ObjectType", None),
                                    getattr(prod, "Tag", None)) if x).lower()
    pset_names = {p.lower() for p in psets}
    if cls == "IfcElectricDistributionBoard":
        if pdt == "SWITCHBOARD" or "switchboardschedule" in pset_names or "switchboard" in hay:
            return "switchboard"
        # panelboard flavours by voltage / mains / role words
        v = contract.get("_voltage") or {}
        bus = contract.get("BusRating")
        if re.search(r"receptacle|appliance", hay) or (v.get("ll") and v["ll"] <= 240):
            return "receptacle_panelboard"
        if re.search(r"lighting|lp-", hay) or (bus is not None and float(bus) <= 225
                                                 and "lugs" in str(contract.get("MainsType", "")).lower()):
            return "lighting_panelboard"
        if re.search(r"distribution|dp-", hay) or (bus is not None and float(bus) >= 250):
            return "distribution_panelboard"
        return "panelboard"
    if cls == "IfcTransformer":
        return "transformer"
    if cls == "IfcSwitchingDevice":
        return "switchgear"
    if cls in ("IfcCableCarrierSegment", "IfcCableSegment"):
        return "service_entrance" if re.search(r"service", hay) else "conduit_run"
    if cls == "IfcDiscreteAccessory":
        return "support"
    if cls == "IfcSpace":
        return "space"
    if cls == "IfcBuildingElementProxy":
        if "roominformation" in pset_names or re.search(r"room shell|electrical room", hay):
            return "room_shell"
        if re.search(r"clearance|110\.26|working space", hay):
            return "clearance"
        if re.search(r"ground bus|tmgb|bus bar", hay):
            return "ground_bus"
        return "proxy"
    return KIND_BY_CLASS.get(cls, "proxy")


def _front_from_features(geom: ProductGeometry, body_center_xy: np.ndarray,
                         axes: Sequence[np.ndarray]) -> Optional[np.ndarray]:
    """Front direction = from the body centre toward the FRONT-feature items
    (door / nameplate / meter / breaker faces), snapped to the nearest
    footprint axis.  Back features (strut / standoff) vote the other way."""
    front = geom.items_matching(*FRONT_FEATURES)
    back = geom.items_matching(*BACK_FEATURES)
    votes = []
    for it in front:
        d = it.center[:2] - body_center_xy
        if np.linalg.norm(d) > 1e-6:
            votes.append(_norm(d))
    for it in back:
        d = body_center_xy - it.center[:2]
        if np.linalg.norm(d) > 1e-6:
            votes.append(_norm(d))
    if not votes:
        return None
    v = _norm(np.sum(votes, axis=0))
    if np.linalg.norm(v) < 1e-9:
        return None
    # snap to the closest of the four axis directions
    cands = []
    for a in axes:
        a2 = _norm(np.asarray(a[:2], float))
        cands += [a2, -a2]
    best = max(cands, key=lambda c: float(np.dot(c, v)))
    return best


def _upright_frame(front: Sequence[float]) -> List[List[float]]:
    """Rows = images of family X / Y / Z in world for WALL equipment:
    family +Z = front normal (out of the wall), family +Y = up,
    family +X = famY x famZ."""
    fz = np.array([front[0], front[1], 0.0])
    fz = _norm(fz)
    fy = np.array([0.0, 0.0, 1.0])
    fx = np.cross(fy, fz)
    return [list(map(float, fx)), list(map(float, fy)), list(map(float, fz))]


def _yaw_frame(front: Sequence[float]) -> Tuple[List[List[float]], float]:
    """Floor equipment: family -Y faces the front, so family +Y = -front;
    family +X = famY x famZ = (-ny, nx) ... yaw = angle of family +X."""
    nx, ny = _unit2(float(front[0]), float(front[1]))
    fx = np.array([-ny, nx, 0.0]) * -1.0          # X = Y x Z with Y=-n, Z=up
    # Y=(-nx,-ny,0), Z=(0,0,1): X = Y x Z = ((-ny)*1 - 0, 0 - (-nx)*1, 0) = (-ny, nx, 0)
    fx = np.array([-ny, nx, 0.0])
    fy = np.array([-nx, -ny, 0.0])
    fz = np.array([0.0, 0.0, 1.0])
    yaw = math.degrees(math.atan2(fx[1], fx[0]))
    return [list(map(float, fx)), list(map(float, fy)), list(map(float, fz))], yaw


def _resolve_equipment_placement(eq: Equipment, room_center_xy: Optional[np.ndarray]) -> None:
    """Fill insertion / front / frame / dims / elevation / mounting from the
    resolved geometry (and the placement chain when it is not the identity)."""
    geom = eq.geometry
    plc = eq.placement
    if not geom.has_body:
        # nothing to recover: fall back to the composed placement origin
        eq.insertion_m = list(map(float, plc.origin * geom.scale))
        eq.position_source = "placement-chain" if not plc.identity else "unresolved (no body, identity chain)"
        eq.frame3x3, eq.yaw_deg = _yaw_frame([0.0, -1.0])
        eq.notes.append("no tessellated body: position = composed placement origin")
        return
    # the BODY = everything except back features; prefer named body items
    body_items = geom.items_matching(*BODY_FEATURES) or geom.items
    body_pts = np.vstack([it.points for it in body_items])
    lo, hi = body_pts.min(0), body_pts.max(0)
    fp = oriented_footprint(body_pts[:, :2])
    center_xy = np.array(fp["center"])
    xdir = np.array(fp["xdir"] + [0.0]) if len(fp["xdir"]) == 2 else np.array(fp["xdir"])
    xdir = np.array([fp["xdir"][0], fp["xdir"][1], 0.0])
    ydir = np.array([-xdir[1], xdir[0], 0.0])
    # front normal
    front = _front_from_features(geom, center_xy, (xdir, ydir))
    if front is None:
        # thinner axis, pointing toward the room interior
        cand = ydir[:2] if fp["xdim"] >= fp["ydim"] else xdir[:2]
        if room_center_xy is not None:
            to_room = room_center_xy - center_xy
            if np.dot(cand, to_room) < 0:
                cand = -cand
        front = _norm(np.asarray(cand, float))
        eq.notes.append("front normal inferred from the footprint's thin axis "
                        "(no door/nameplate features named)")
    front = _norm(np.asarray(front[:2], float))
    eq.front_normal = [float(front[0]), float(front[1]), 0.0]
    # dims: width along the axis perpendicular to the front, depth along it
    fdir = np.array([front[0], front[1], 0.0])
    wdir = np.array([-front[1], front[0], 0.0])
    pw = body_pts[:, :2] @ wdir[:2]
    pd = body_pts[:, :2] @ fdir[:2]
    width = float(pw.max() - pw.min())
    depth = float(pd.max() - pd.min())
    height = float(hi[2] - lo[2])
    eq.dims_m = {"w": width, "d": depth, "h": height,
                 "footprint_area": float(width * depth)}
    eq.elevation_m = float(lo[2])
    wall_gear = eq.kind in WALL_KINDS
    if wall_gear:
        # insertion = centre of the BACK face of the enclosure (against the
        # wall / strut backing): body centre pushed back along the front
        # normal by depth/2; z = enclosure centre height
        enclosure = geom.items_matching("enclosure")
        enc_pts = np.vstack([it.points for it in enclosure]) if enclosure else body_pts
        elo, ehi = enc_pts.min(0), enc_pts.max(0)
        ecenter = (elo + ehi) / 2.0
        eproj = enc_pts[:, :2] @ fdir[:2]
        back = float(eproj.min())
        w_c = float((enc_pts[:, :2] @ wdir[:2]).mean())
        ins_xy = wdir[:2] * w_c + fdir[:2] * back
        eq.insertion_m = [float(ins_xy[0]), float(ins_xy[1]), float(ecenter[2])]
        eq.frame3x3 = _upright_frame(eq.front_normal)
        eq.frame_kind = "upright"
        fx = eq.frame3x3[0]
        eq.yaw_deg = math.degrees(math.atan2(fx[1], fx[0]))
        eq.mounting = "surface" if geom.items_matching("strut", "backing") else "wall"
        eq.mounting_height_m = float(ecenter[2])
        eq.dims_m.update({"enclosure_w": float(ehi[0] - elo[0]) if abs(front[0]) < abs(front[1])
                          else float(ehi[1] - elo[1]),
                          "enclosure_h": float(ehi[2] - elo[2]),
                          "top_of_panel": float(ehi[2]), "bottom_of_panel": float(elo[2])})
        eq.notes.append("insertion = centre of the enclosure's back face "
                        "(the mounting plane); dims w/d/h include strut backing")
    else:
        # floor gear: insertion = footprint centre at the body base
        eq.insertion_m = [float(center_xy[0]), float(center_xy[1]), float(lo[2])]
        eq.frame3x3, eq.yaw_deg = _yaw_frame(eq.front_normal)
        eq.frame_kind = "yaw"
        eq.mounting = "floor"
        eq.notes.append("insertion = footprint centre at the base of the body "
                        "(z = base of enclosure; sits on a housekeeping pad when one exists)")
    eq.position_source = ("placement-chain + local geometry" if not plc.identity
                          else "geometry-recovered (placement chain composes to the identity; "
                               "world-baked vertices)")


# ============================================================================
# ROOM SHELL
# ============================================================================

@dataclass
class DoorOpening:
    wall_id: str
    center_along_m: float
    width_m: float
    head_height_m: float
    sill_m: float = 0.0
    leaf_width_m: Optional[float] = None
    swing: str = "out"
    source: str = "leaf+header solids"
    world_center_m: Optional[List[float]] = None      # anchor for offset re-derivation

    def as_json(self) -> dict:
        return {"wall": self.wall_id, "center_along_m": _f(self.center_along_m),
                "width_m": _f(self.width_m), "head_height_m": _f(self.head_height_m),
                "sill_m": _f(self.sill_m),
                "world_center_m": None if self.world_center_m is None else _vf(self.world_center_m),
                "leaf_width_m": None if self.leaf_width_m is None else _f(self.leaf_width_m),
                "swing": self.swing, "source": self.source,
                "disposition": "recorded (no door family / wall hosting in v1)"}


@dataclass
class WallRun:
    wall_id: str
    p0_m: List[float]                       # centerline start (world, m)
    p1_m: List[float]
    thickness_m: float
    height_m: float
    base_m: float = 0.0
    synthesized: bool = False
    reason: str = ""
    derived_from: List[str] = dc_field(default_factory=list)
    openings: List[DoorOpening] = dc_field(default_factory=list)

    @property
    def length_m(self) -> float:
        return math.hypot(self.p1_m[0] - self.p0_m[0], self.p1_m[1] - self.p0_m[1])

    def as_json(self) -> dict:
        return {"id": self.wall_id, "start": _vf(self.p0_m), "end": _vf(self.p1_m),
                "length_m": _f(self.length_m), "thickness": _f(self.thickness_m),
                "height": _f(self.height_m), "base_m": _f(self.base_m),
                "synthesized": self.synthesized, "reason": self.reason,
                "derivedFrom": list(self.derived_from),
                "openings": [o.as_json() for o in self.openings],
                "type": "Room shell wall (from the shell proxy's wall solids)"}


@dataclass
class RoomShell:
    name: str
    step_id: Optional[int]
    walls: List[WallRun] = dc_field(default_factory=list)
    doors: List[DoorOpening] = dc_field(default_factory=list)
    floor: Optional[dict] = None
    pads: List[dict] = dc_field(default_factory=list)
    clear: Dict[str, Any] = dc_field(default_factory=dict)
    info: Dict[str, Any] = dc_field(default_factory=dict)
    notes: List[str] = dc_field(default_factory=list)

    def as_json(self) -> dict:
        return {"name": self.name, "step_id": self.step_id,
                "walls": [w.as_json() for w in self.walls],
                "doors": [d.as_json() for d in self.doors],
                "floor": self.floor, "housekeepingPads": self.pads,
                "clear": self.clear, "roomInformation": self.info,
                "notes": list(self.notes)}


def _box_axes(b: dict) -> Tuple[np.ndarray, float, float, np.ndarray]:
    """(unit long-axis 2-D, long dim, short dim, centre 2-D) of a box dict."""
    xd, yd = float(b["xdim"]), float(b["ydim"])
    xdir = np.asarray(b["xdir"][:2], float)
    ydir = np.array([-xdir[1], xdir[0]])
    c = np.asarray(b["center"][:2], float)
    if xd >= yd:
        return _norm(xdir), xd, yd, c
    return _norm(ydir), yd, xd, c


def _extract_room_shell(f, prod, geom: ProductGeometry, psets: Dict[str, Dict[str, Any]]) -> RoomShell:
    """Walls / doors / floor / pads from the room-shell proxy's named solids."""
    shell = RoomShell(name=prod.Name or "Room shell", step_id=prod.id())
    shell.info = dict(psets.get("RoomInformation") or {})
    items = geom.items
    wall_items = [it for it in items if it.name and WALL_ITEM_RX.match(it.name)]
    door_items = [it for it in items if it.name and DOOR_ANY_RX.match(it.name)]
    slab_items = [it for it in items if it.name and SLAB_RX.search(it.name)]
    pad_items = [it for it in items if it.name and PAD_RX.match(it.name)]

    # ---- floor slab
    if slab_items:
        s = slab_items[0]
        fp = oriented_footprint(s.points[:, :2])
        shell.floor = {"item": s.name, "footprint": {k: (_vf(v) if isinstance(v, list) else _f(v))
                                                       for k, v in fp.items()},
                       "top_m": _f(s.hi[2]), "thickness_m": _f(s.extent[2]),
                       "disposition": "recorded (host floor is a follow-up; walls sit on the level)"}
    # ---- pads
    for p in pad_items:
        fp = oriented_footprint(p.points[:, :2])
        m = PAD_RX.match(p.name or "")
        shell.pads.append({"item": p.name, "for": (m.group(1) if m else None),
                           "center_m": _vf(fp["center"]), "size_m": [_f(fp["xdim"]), _f(fp["ydim"])],
                           "height_m": _f(p.extent[2]), "top_m": _f(p.hi[2]),
                           "disposition": "recorded (housekeeping pad = floor/pad follow-up)"})
    if not wall_items:
        shell.notes.append("no wall_* solids: shell footprint only")
        return shell

    # ---- wall segments: each wall solid is an upright box
    segs = []                                   # {name, axis(2), long, thick, center(2), zlo, zhi, is_header}
    for it in wall_items:
        boxes = it.boxes or []
        b = boxes[0] if boxes else None
        if b is None:
            # fall back to the item's oriented footprint
            fp = oriented_footprint(it.points[:, :2])
            b = {"xdir": fp["xdir"], "xdim": fp["xdim"], "ydim": fp["ydim"],
                 "center": [fp["center"][0], fp["center"][1], float(it.center[2])],
                 "height": float(it.extent[2]), "origin": [fp["center"][0], fp["center"][1], float(it.lo[2])]}
        axis, long_d, short_d, c = _box_axes(b)
        segs.append({"name": it.name, "axis": axis, "long": long_d, "thick": short_d,
                     "center": c, "zlo": float(it.lo[2]), "zhi": float(it.hi[2]),
                     "is_header": bool(HEADER_RX.search(it.name or ""))})
    top_z = max(s["zhi"] for s in segs)
    base_z = min(s["zlo"] for s in segs if not s["is_header"]) if any(not s["is_header"] for s in segs) else 0.0

    # ---- group collinear segments (same axis direction & same offset line)
    groups: List[List[dict]] = []
    for s in segs:
        placed = False
        for g in groups:
            g0 = g[0]
            if abs(abs(float(np.dot(g0["axis"], s["axis"]))) - 1.0) > 1e-3:
                continue
            # perpendicular offset of s's centre from g0's line
            nrm = np.array([-g0["axis"][1], g0["axis"][0]])
            off = abs(float(np.dot(s["center"] - g0["center"], nrm)))
            if off <= max(g0["thick"], s["thick"]) * 0.75 + 1e-3:
                g.append(s)
                placed = True
                break
        if not placed:
            groups.append([s])

    # reference centre for compass naming: the slab centre, else the mean of
    # the wall segment centres
    if slab_items:
        ref_c = np.asarray(oriented_footprint(slab_items[0].points[:, :2])["center"], float)
    else:
        ref_c = np.mean([s["center"] for s in segs], axis=0)

    # ---- one WallRun per group: centerline = the merged extent along the axis
    walls: List[WallRun] = []
    for gi, g in enumerate(groups):
        axis = g[0]["axis"]
        nrm = np.array([-axis[1], axis[0]])
        # coordinates along the axis / across it, of every segment's ends
        along_vals = []
        across_vals = []
        full = [s for s in g if not s["is_header"]]
        for s in g:
            t0 = float(np.dot(s["center"], axis)) - s["long"] / 2
            t1 = float(np.dot(s["center"], axis)) + s["long"] / 2
            along_vals += [t0, t1]
            across_vals.append(float(np.dot(s["center"], nrm)))
        t_min, t_max = min(along_vals), max(along_vals)
        across = float(np.mean(across_vals))
        thick = float(np.mean([s["thick"] for s in g]))
        height = max(s["zhi"] for s in g) - base_z
        p0 = axis * t_min + nrm * across
        p1 = axis * t_max + nrm * across
        gc = np.mean([s["center"] for s in g], axis=0)
        wid = _wall_id_for(axis, gc, ref_c)
        wr = WallRun(wall_id=wid, p0_m=[float(p0[0]), float(p0[1])],
                     p1_m=[float(p1[0]), float(p1[1])], thickness_m=thick,
                     height_m=float(height), base_m=float(base_z),
                     derived_from=[s["name"] for s in g])
        # ---- openings: gaps between the full-height pieces below the header
        headers = [s for s in g if s["is_header"]]
        if len(full) >= 2 or headers:
            intervals = sorted((float(np.dot(s["center"], axis)) - s["long"] / 2,
                                float(np.dot(s["center"], axis)) + s["long"] / 2)
                               for s in full)
            for (a0, a1), (b0, b1) in zip(intervals, intervals[1:]):
                gap = b0 - a1
                if gap > 0.1:                                   # a real opening
                    head = base_z + height
                    for h in headers:
                        hc = float(np.dot(h["center"], axis))
                        if a1 - 1e-3 <= hc <= b0 + 1e-3:
                            head = h["zlo"]
                            break
                    wc = axis * ((a1 + b0) / 2) + nrm * across
                    wr.openings.append(DoorOpening(
                        wall_id=wid, center_along_m=(a1 + b0) / 2 - t_min,
                        width_m=gap, head_height_m=head - base_z, sill_m=0.0,
                        world_center_m=[float(wc[0]), float(wc[1])]))
        walls.append(wr)

    # ---- match door leaves to openings (leaf width / swing side)
    for it in door_items:
        if not DOOR_LEAF_RX.match(it.name or ""):
            continue
        c = it.center[:2]
        # nearest wall run by perpendicular distance
        best, bestd = None, 1e9
        for wr in walls:
            axis = np.array(_unit2(wr.p1_m[0] - wr.p0_m[0], wr.p1_m[1] - wr.p0_m[1]))
            nrm = np.array([-axis[1], axis[0]])
            d = abs(float(np.dot(c - np.array(wr.p0_m), nrm)))
            if d < bestd:
                best, bestd = wr, d
        fpl = oriented_footprint(it.points[:, :2])
        leaf_w = float(fpl["xdim"])
        opening = None
        if best is not None and best.openings:
            axis = np.array(_unit2(best.p1_m[0] - best.p0_m[0], best.p1_m[1] - best.p0_m[1]))
            along = float(np.dot(c - np.array(best.p0_m), axis))
            opening = min(best.openings, key=lambda o: abs(o.center_along_m - along))
            if opening.leaf_width_m is None:
                opening.leaf_width_m = leaf_w
        shell.doors.append(DoorOpening(
            wall_id=best.wall_id if best else "?",
            center_along_m=(opening.center_along_m if opening else 0.0),
            width_m=(opening.width_m if opening else leaf_w),
            head_height_m=(opening.head_height_m if opening else float(it.hi[2])),
            leaf_width_m=leaf_w,
            swing="out" if bestd > 0.2 else "in",       # leaf clear of the wall = swung out
            source=f"door solid '{it.name}' ({_f(leaf_w)} m leaf)",
            world_center_m=(list(opening.world_center_m) if opening and opening.world_center_m
                            else [float(c[0]), float(c[1])])))
    shell.walls = walls
    # ---- clear interior box (from the full-height wall inner faces / info)
    shell.clear = {"clearWidth_m": shell.info.get("ClearWidth"),
                   "clearDepth_m": shell.info.get("ClearDepth"),
                   "clearHeight_m": shell.info.get("ClearHeight"),
                   "wall_height_m": _f(top_z - base_z), "base_m": _f(base_z)}
    return shell


def _wall_id_for(axis: np.ndarray, center: np.ndarray, ref: np.ndarray) -> str:
    """Compass id of a wall from its centre relative to the room reference
    centre (axis-aligned rooms; the id does NOT depend on the sign of the
    fitted axis direction)."""
    ax = np.abs(axis)
    d = np.asarray(center, float) - np.asarray(ref, float)
    if ax[0] >= ax[1]:            # runs along X -> a north or south wall
        return "W-N" if d[1] > 0 else "W-S"
    return "W-E" if d[0] > 0 else "W-W"


def _rederive_along_offsets(shell: RoomShell) -> None:
    """After the ring closes, every opening / door offset is measured
    afresh from its wall's FINAL start point along the FINAL drawing
    direction, using the world anchor recorded at extraction time."""
    by_id = {w.wall_id: w for w in shell.walls}

    def along(wr: WallRun, anchor: Sequence[float]) -> float:
        p0 = np.array(wr.p0_m, float)
        p1 = np.array(wr.p1_m, float)
        u = _norm(p1 - p0)
        return float(np.dot(np.asarray(anchor, float) - p0, u))

    for wr in shell.walls:
        for o in wr.openings:
            if o.world_center_m:
                o.center_along_m = along(wr, o.world_center_m)
    for d in shell.doors:
        wr = by_id.get(d.wall_id)
        if wr is not None and d.world_center_m:
            d.center_along_m = along(wr, d.world_center_m)


def _close_room(shell: RoomShell) -> None:
    """If the shell has exactly three sides of an axis-aligned rectangle
    (the source's front wall is cut away for viewing), infer the fourth
    (flagged synthesized) from the floor slab footprint + the opposite wall,
    and extend every wall to the centerline intersections so the ring
    closes at clean corners."""
    walls = shell.walls
    if len(walls) < 2:
        return
    have = {w.wall_id: w for w in walls}
    thick = float(np.mean([w.thickness_m for w in walls]))
    height = max(w.height_m for w in walls)
    # axis-aligned bounding lines from the existing walls' centerlines
    ns = [w for w in walls if w.wall_id in ("W-N", "W-S")]
    ew = [w for w in walls if w.wall_id in ("W-E", "W-W")]
    ys = {w.wall_id: (w.p0_m[1] + w.p1_m[1]) / 2 for w in ns}
    xs = {w.wall_id: (w.p0_m[0] + w.p1_m[0]) / 2 for w in ew}
    slab = shell.floor
    # infer the missing side
    for missing, opp, key in (("W-S", "W-N", "y"), ("W-N", "W-S", "y"),
                              ("W-W", "W-E", "x"), ("W-E", "W-W", "x")):
        if missing in have or opp not in have:
            continue
        if len(walls) != 3:
            continue
        # place the missing wall symmetric about the slab centre (or mirror)
        if key == "y":
            other = ys[opp]
            span = None
            if slab and slab.get("footprint"):
                fp = slab["footprint"]
                cy = fp["center"][1]
                # slab edge on the missing side, offset inward by half thickness
                half = (fp["ydim"] if abs(fp["xdir"][0]) > 0.5 else fp["xdim"]) / 2
                edge = cy - half if other > cy else cy + half
                yline = edge - math.copysign(thick / 2, other - cy) * -1
                # simpler: the wall centerline sits half a thickness OUTSIDE the slab edge
                yline = edge - math.copysign(thick / 2, cy - edge)
                span = (min(w.p0_m[0] for w in ns) if ns else -1.0,
                        max(w.p1_m[0] for w in ns) if ns else 1.0)
            else:
                yline = -other
                span = (min(w.p0_m[0] for w in ns), max(w.p1_m[0] for w in ns))
            wr = WallRun(wall_id=missing, p0_m=[span[0], yline], p1_m=[span[1], yline],
                         thickness_m=thick, height_m=height, base_m=walls[0].base_m,
                         synthesized=True,
                         reason=("front wall cut away in the source model for viewing "
                                 "('front wall cut away' per the shell description); inferred to "
                                 f"close the room from the floor slab edge + the opposite wall {opp}"),
                         derived_from=["floor slab footprint", opp])
        else:
            other = xs[opp]
            if slab and slab.get("footprint"):
                fp = slab["footprint"]
                cx = fp["center"][0]
                half = (fp["xdim"] if abs(fp["xdir"][0]) > 0.5 else fp["ydim"]) / 2
                edge = cx - half if other > cx else cx + half
                xline = edge - math.copysign(thick / 2, cx - edge)
                span = (min(w.p0_m[1] for w in ew), max(w.p1_m[1] for w in ew))
            else:
                xline = -other
                span = (min(w.p0_m[1] for w in ew), max(w.p1_m[1] for w in ew))
            wr = WallRun(wall_id=missing, p0_m=[xline, span[0]], p1_m=[xline, span[1]],
                         thickness_m=thick, height_m=height, base_m=walls[0].base_m,
                         synthesized=True,
                         reason=("side wall not modeled in the source; inferred to close the room "
                                 f"from the floor slab edge + the opposite wall {opp}"),
                         derived_from=["floor slab footprint", opp])
        walls.append(wr)
        have[missing] = wr
        shell.notes.append(f"{missing} SYNTHESIZED: {wr.reason}")
        break
    # ---- close corners: intersect adjacent centerlines (axis-aligned)
    ns = {w.wall_id: w for w in walls if w.wall_id in ("W-N", "W-S")}
    ew = {w.wall_id: w for w in walls if w.wall_id in ("W-E", "W-W")}
    if len(ns) == 2 and len(ew) == 2:
        y_n = (ns["W-N"].p0_m[1] + ns["W-N"].p1_m[1]) / 2
        y_s = (ns["W-S"].p0_m[1] + ns["W-S"].p1_m[1]) / 2
        x_e = (ew["W-E"].p0_m[0] + ew["W-E"].p1_m[0]) / 2
        x_w = (ew["W-W"].p0_m[0] + ew["W-W"].p1_m[0]) / 2
        # a counter-clockwise ring so every wall's "interior" is on one side
        ns["W-S"].p0_m, ns["W-S"].p1_m = [x_w, y_s], [x_e, y_s]     # S: west -> east
        ew["W-E"].p0_m, ew["W-E"].p1_m = [x_e, y_s], [x_e, y_n]     # E: south -> north
        ns["W-N"].p0_m, ns["W-N"].p1_m = [x_e, y_n], [x_w, y_n]     # N: east -> west
        ew["W-W"].p0_m, ew["W-W"].p1_m = [x_w, y_n], [x_w, y_s]     # W: north -> south
        shell.notes.append("wall centerlines closed into a counter-clockwise ring "
                           "(S: west->east, E: south->north, N: east->west, W: north->south); "
                           "interior on the left of every wall's drawing direction")
        shell.clear.setdefault("ring_ccw", True)
        shell.clear["centerline_extents_m"] = {"x": [_f(min(x_w, x_e)), _f(max(x_w, x_e))],
                                                "y": [_f(min(y_s, y_n)), _f(max(y_s, y_n))]}
    _rederive_along_offsets(shell)


# ============================================================================
# CLEARANCE ZONES
# ============================================================================

@dataclass
class ClearanceZone:
    equipment_tag: Optional[str]
    depth_m: float
    width_m: float
    height_m: float
    center_m: List[float]
    condition: int = 2
    source_item: str = ""
    required_depth_m: Optional[float] = None
    ok: Optional[bool] = None

    def as_json(self) -> dict:
        return {"equipment": self.equipment_tag, "depth_m": _f(self.depth_m),
                "width_m": _f(self.width_m), "height_m": _f(self.height_m),
                "center_m": _vf(self.center_m), "condition": self.condition,
                "required_depth_m": None if self.required_depth_m is None else _f(self.required_depth_m),
                "nec_110_26_ok": self.ok, "source_item": self.source_item,
                "disposition": ("annotation-only: omitted from the model geometry (a "
                                "working-clearance zone is documentation, not a building "
                                "element -- a plan-view clearance region is the follow-up); "
                                "the NEC 110.26 depth check is recorded here")}


def _extract_clearances(prod, geom: ProductGeometry, description: str,
                        equipment: List["Equipment"]) -> List[ClearanceZone]:
    """One zone per ``clearance_<tag>`` solid; depth measured along the
    matched equipment's front normal."""
    zones: List[ClearanceZone] = []
    by_tag = {re.sub(r"[^a-z0-9]", "", (e.tag or "").lower()): e for e in equipment}
    req = _required_clearances(description)
    for it in geom.items:
        m = CLEARANCE_RX.match(it.name or "")
        tag_key = re.sub(r"[^a-z0-9]", "", (m.group(1) if m else "").lower())
        eq = by_tag.get(tag_key)
        ext = it.extent
        c = it.center
        if eq is not None and eq.front_normal:
            n = np.array(eq.front_normal[:2])
            wdir = np.array([-n[1], n[0]])
            depth = float(np.ptp(it.points[:, :2] @ n))
            width = float(np.ptp(it.points[:, :2] @ wdir))
        else:
            depth, width = float(min(ext[0], ext[1])), float(max(ext[0], ext[1]))
        height = float(ext[2])
        rq = None
        if req:
            rq = req.get("switchboard") if eq is not None and eq.kind == "switchboard" else req.get("panel")
        ok = None if rq is None else (depth + 0.005 >= rq)
        zones.append(ClearanceZone(
            equipment_tag=eq.tag if eq else (m.group(1).upper() if m else None),
            depth_m=depth, width_m=width, height_m=height,
            center_m=[float(c[0]), float(c[1]), float(c[2])],
            condition=int(req.get("condition") or 2),
            source_item=it.name or "", required_depth_m=rq, ok=ok))
    return zones


def _required_clearances(description: str) -> Dict[str, float]:
    """Parse 'Condition 2: 1.07 m (3.5 ft) at the 2500 A switchboard; 0.914 m
    (3 ft) x 0.762 m x 1.98 m at panelboards and transformer' into required
    depths (the FIRST metre value of each ';' clause = its working depth)."""
    out: Dict[str, float] = {}
    if not description:
        return out
    m = re.search(r"condition\s*(\d)", description, re.I)
    if m:
        out["condition"] = float(m.group(1))
    for clause in re.split(r";", description):
        cl = clause.lower()
        nums = re.findall(r"(\d+(?:\.\d+)?)\s*m\b", cl)
        if not nums:
            continue
        depth = float(nums[0])
        if "switchboard" in cl:
            out.setdefault("switchboard", depth)
        if re.search(r"panelboard|panel|transformer", cl):
            out.setdefault("panel", depth)
    return out


# ============================================================================
# FEEDER TREE
# ============================================================================

@dataclass
class FeederEdge:
    source: str                             # feeding equipment tag (or SERVICE)
    target: str                             # fed equipment tag
    kind: str = "feeder"                    # feeder | primary | secondary | service
    from_pset: bool = False
    conduit_items: List[str] = dc_field(default_factory=list)
    conduit_geometry: Optional[dict] = None
    rating_a: Optional[float] = None
    voltage: Optional[str] = None
    poles: Optional[int] = None
    notes: List[str] = dc_field(default_factory=list)

    def as_json(self) -> dict:
        return {"from": self.source, "to": self.target, "kind": self.kind,
                "sources": (["pset:FedFrom"] if self.from_pset else [])
                           + [f"geometry:{c}" for c in self.conduit_items],
                "corroborated": bool(self.from_pset and self.conduit_items),
                "conduitGeometry": self.conduit_geometry,
                "circuitPlan": {"panel": self.source, "load": self.target,
                                "rating_a": self.rating_a, "voltage": self.voltage,
                                "poles": self.poles,
                                "description": f"{self.target} feeder from {self.source}"},
                "notes": list(self.notes)}


_TAG_ALIASES = {"msb": "MSB", "t1": "T1", "utility": "UTILITY", "service": "SERVICE"}


def _norm_tag(token: str, known: Iterable[str]) -> Optional[str]:
    """'dp1' -> 'DP-1', 'lp4' -> 'LP-4', 'msb' -> 'MSB', 't1' -> 'T1'."""
    t = token.lower().strip()
    if t in _TAG_ALIASES:
        return _TAG_ALIASES[t]
    known_map = {re.sub(r"[^a-z0-9]", "", k.lower()): k for k in known}
    if t in known_map:
        return known_map[t]
    m = re.match(r"^([a-z]+)(\d+)$", t)
    if m:
        return f"{m.group(1).upper()}-{m.group(2)}"
    return token.upper()


def _build_feeder_tree(equipment: List[Equipment], conduit_products: List[Tuple[Any, ProductGeometry]]
                       ) -> Tuple[List[FeederEdge], List[dict]]:
    """Feeder edges from ``FedFrom`` psets, corroborated by the conduit-run
    geometry (``conduit_<from>_<to>`` named solids)."""
    tags = [e.tag for e in equipment]
    by_tag = {e.tag: e for e in equipment}
    edges: Dict[Tuple[str, str], FeederEdge] = {}
    for e in equipment:
        ff = e.fed_from
        if not ff:
            continue
        src = _norm_tag(str(ff), tags)
        ed = FeederEdge(source=src, target=e.tag, from_pset=True)
        con = e.contract
        ed.rating_a = con.get("MainsRating") or con.get("BusRating")
        ed.voltage = con.get("Voltage") or (con.get("_voltage") or {}).get("system")
        ed.poles = int(con.get("Phases") or 3)
        # transformer: fed on the PRIMARY, its own kVA sets the feeder
        if e.kind == "transformer":
            ed.kind = "primary"
            kva = con.get("RatingkVA")
            prim = str(con.get("Primary") or "")
            vp = parse_voltage(prim).get("ll") or 480.0
            if kva:
                ed.rating_a = round(float(kva) * 1000.0 / (math.sqrt(3) * vp), 1)
                ed.notes.append(f"feeder ampacity from kVA: {kva} kVA / (sqrt3 x {vp:g} V) "
                                f"= {ed.rating_a} A (FLA; the OCPD is 125% NEC 450 -- calc follow-up)")
            ed.voltage = prim or ed.voltage
        # a load fed by a transformer is on its SECONDARY
        if by_tag.get(src) is not None and by_tag[src].kind == "transformer":
            ed.kind = "secondary"
            ed.voltage = str(by_tag[src].contract.get("Secondary") or ed.voltage)
        edges[(src, e.tag)] = ed
    # ---- conduit corroboration
    runs: List[dict] = []
    for prod, geom in conduit_products:
        for it in geom.items:
            nm = (it.name or "").lower()
            run = {"item": it.name, "product": prod.Name, "step_id": prod.id(),
                   "triangles": it.n_tris, "lo_m": _vf(it.lo), "hi_m": _vf(it.hi),
                   "components": it.n_components,
                   "rack_elevation_m": _f(it.hi[2])}
            m = CONDUIT_RX.match(it.name or "")
            if m and not nm.endswith("_hubs"):
                a, b = m.group(1), m.group(2)
                src, tgt = _norm_tag(a, tags), _norm_tag(b, tags)
                run["from"], run["to"] = src, tgt
                key = (src, tgt)
                if key in edges:
                    edges[key].conduit_items.append(it.name)
                    edges[key].conduit_geometry = {"lo_m": run["lo_m"], "hi_m": run["hi_m"],
                                                   "components": run["components"],
                                                   "rack_elevation_m": run["rack_elevation_m"]}
                elif src in by_tag or src in ("SERVICE", "UTILITY"):
                    edges[key] = FeederEdge(source=src, target=tgt, from_pset=False,
                                            conduit_items=[it.name],
                                            notes=["edge seen ONLY in conduit geometry"])
            elif "service" in nm:
                run["from"], run["to"] = "UTILITY", "MSB" if "MSB" in by_tag else None
                key = ("UTILITY", run["to"] or "MSB")
                edges[key] = FeederEdge(source="UTILITY", target=run["to"] or "MSB",
                                        kind="service", from_pset=False,
                                        conduit_items=[it.name],
                                        notes=["utility service entrance (external source; "
                                               "no in-model circuit -- the switchboard's supply "
                                               "connector stays unconnected)"])
            runs.append(run)
    return list(edges.values()), runs


# ============================================================================
# FAMILY MAPPING (gap b)
# ============================================================================

@dataclass
class FamilyPlan:
    """The mapping of one equipment item onto OUR generated content."""
    tag: str
    kind: str
    constructor: str                        # dotted path of the constructor
    kwargs: Dict[str, Any]
    status: str = "planned"                 # 'resolved' | 'refused' | 'house' | 'unmapped'
    catalog: Optional[str] = None
    variant: Optional[str] = None
    facts_summary: Dict[str, Any] = dc_field(default_factory=dict)
    dims_catalog_m: Dict[str, float] = dc_field(default_factory=dict)
    dims_modeled_m: Dict[str, float] = dc_field(default_factory=dict)
    refusal: Optional[str] = None
    notes: List[str] = dc_field(default_factory=list)

    def as_json(self) -> dict:
        d = {"tag": self.tag, "kind": self.kind, "constructor": self.constructor,
             "kwargs": self.kwargs, "status": self.status,
             "catalog": self.catalog, "variant": self.variant,
             "facts": self.facts_summary,
             "dims": {"modeled_m": {k: _f(v) for k, v in self.dims_modeled_m.items()},
                      "catalog_m": {k: _f(v) for k, v in self.dims_catalog_m.items()},
                      "delta_m": {k: _f(self.dims_catalog_m[k] - self.dims_modeled_m[k])
                                  for k in self.dims_catalog_m
                                  if k in self.dims_modeled_m}},
             "notes": list(self.notes)}
        if self.refusal:
            d["refusal"] = self.refusal
        return d


def _mounting_word(eq: Equipment) -> str:
    mt = str(eq.contract.get("Mounting") or "").lower()
    if "flush" in mt:
        return "flush"
    return "surface"


def plan_family_for(eq: Equipment) -> FamilyPlan:
    """Map ONE equipment item to its generated-content constructor + facts.

    Panelboards -> ``rvt.famgen.factory.make_panelboard`` (Eaton Pow-R-Line
    catalog facts); the transformer -> ``make_transformer`` (catalog facts);
    the switchboard -> :func:`make_house_switchboard` (no panelboard member
    covers 2500 A -- the factory REFUSES it, honestly recorded, and the house
    family is composed from OUR OWN IFC-modeled dimensions + the Pset
    ratings).  Every other kind is 'unmapped' with a stated reason.
    """
    con = eq.contract
    v = con.get("_voltage") or {}
    dims_mod = {k: eq.dims_m.get(k) for k in ("w", "d", "h") if eq.dims_m.get(k) is not None}
    if eq.kind in ("distribution_panelboard", "lighting_panelboard",
                   "receptacle_panelboard", "panelboard"):
        mains_type = str(con.get("MainsType") or "")
        mcb = "lug" not in mains_type.lower()
        mains_a = float(con.get("MainsRating") or con.get("BusRating") or 0.0)
        spaces = int(con.get("NumberOfCircuits") or 42)
        voltage = str(v.get("system") or con.get("Voltage") or "480Y/277").replace(" V", "")
        kwargs = dict(vendor="eaton", line="pow-r-line", mains_a=mains_a, spaces=spaces,
                      voltage=voltage, mcb=mcb, mounting=_mounting_word(eq),
                      panel_name=str(con.get("PanelName") or eq.tag),
                      sccr_ka=con.get("ShortCircuitRatingkA"))
        fp = FamilyPlan(tag=eq.tag, kind=eq.kind,
                        constructor="rvt.famgen.factory.make_panelboard",
                        kwargs=kwargs, dims_modeled_m=dims_mod)
        _resolve_panel_facts(fp)
        return fp
    if eq.kind == "transformer":
        kva = float(con.get("RatingkVA") or 0.0)
        prim = parse_voltage(con.get("Primary")).get("ll") or 480.0
        sec = str(con.get("Secondary") or "208Y/120").replace(" V", "")
        kwargs = dict(kva=kva, vendor="eaton", primary_v=int(prim), secondary_v=sec)
        fp = FamilyPlan(tag=eq.tag, kind=eq.kind,
                        constructor="rvt.famgen.factory.make_transformer",
                        kwargs=kwargs, dims_modeled_m=dims_mod)
        _resolve_xfmr_facts(fp)
        return fp
    if eq.kind == "switchboard":
        # the panelboard factory covers Eaton Pow-R-Line PANELBOARDS (<= 600 A
        # / 1200 A members).  A 2500 A device is a SWITCHBOARD: no catalog
        # line on record -> ask the factory (records the honest refusal), then
        # plan the HOUSE switchboard from our own IFC-modeled dimensions.
        mains_a = float(con.get("MainsRating") or con.get("BusRating") or 2500.0)
        voltage = str(v.get("system") or con.get("Voltage") or "480Y/277").replace(" V", "")
        probe = dict(vendor="eaton", line="pow-r-line", mains_a=mains_a,
                     spaces=int(con.get("NumberOfCircuits") or 42),
                     voltage=voltage, mcb=True, mounting="surface",
                     panel_name=str(con.get("PanelName") or eq.tag))
        refusal = _probe_panel_refusal(probe)
        kwargs = dict(
            tag=eq.tag, name="Switchboard " + eq.tag, mains_a=mains_a, voltage=voltage,
            phases=int(con.get("Phases") or v.get("phases") or 3),
            wires=int(con.get("Wires") or v.get("wires") or 4),
            sccr_ka=float(con.get("ShortCircuitRatingkA") or 0.0),
            sections=int(con.get("Sections") or 1),
            mains_device=str(con.get("MainDevice") or con.get("MainsType") or "Main breaker"),
            mounting=str(con.get("Mounting") or "floor"),
            feeder_entry=str(con.get("FeederEntry") or ""),
            manufacturer=str(con.get("Manufacturer") or ""),
            model_label=str(con.get("ModelLabel") or ""),
            width_m=float(eq.dims_m.get("w") or 0.0),
            depth_m=float(eq.dims_m.get("d") or 0.0),
            height_m=float(eq.dims_m.get("h") or 0.0),
        )
        fp = FamilyPlan(tag=eq.tag, kind=eq.kind,
                        constructor="rvt.ifc.intent.make_house_switchboard",
                        kwargs=kwargs, status="house", refusal=refusal,
                        dims_modeled_m=dims_mod, dims_catalog_m=dict(dims_mod))
        fp.notes.append(
            "NO catalog record covers a 2500 A switchboard (the Pow-R-Line "
            "panelboard members top out at 600 / 800 / 1200 A) and no switchboard "
            "product exists in the factory -> the panelboard resolver REFUSES it "
            f"({refusal}); the HOUSE switchboard family is composed from OUR OWN "
            "IFC-modeled dimensions (this IFC is our provenance) with the "
            "SwitchboardSchedule Pset ratings riding as parameter VALUES "
            "(manufacturer / model strings from Pset_ManufacturerTypeInformation "
            "are carried as declared IDENTITY values, flagged 'ifc-declared', "
            "not catalog facts)")
        return fp
    reason = {
        "ground_bus": "no house generator for a ground bus bar (a small "
                      "generic-model family is the follow-up; the TMGB is a "
                      "detail component, not equipment) -- recorded only",
        "conduit_run": "conduit RUNS are rvt.mep.conduit territory (add_conduit_"
                       "path over the recorded polyline); needs conduit types in "
                       "the base -- recorded as run geometry, omitted from v1",
        "service_entrance": "utility service entrance: external source -- "
                            "recorded as the SERVICE edge of the feeder tree",
        "support": "trapeze hangers / clevis supports = detailing (supports "
                   "stream); recorded, omitted from the project file",
        "room_shell": "handled as the room shell (walls / doors / pads), not equipment",
        "clearance": "NEC 110.26 working clearances = annotation zones; recorded",
        "switchgear": "no house switchgear generator; recorded",
        "space": "spaces are the rooms/spaces stream; recorded",
        "proxy": "generic proxy with no equipment semantics; recorded",
    }.get(eq.kind, "no generated-content constructor for this kind; recorded")
    return FamilyPlan(tag=eq.tag, kind=eq.kind, constructor="", kwargs={},
                      status="unmapped", refusal=reason, dims_modeled_m=dims_mod)


def _probe_panel_refusal(kwargs: dict) -> str:
    """Run the panelboard fact resolver and return its refusal message."""
    try:
        from ..famgen import factory as F
        F.resolve_panelboard_facts(kwargs["vendor"], kwargs["line"],
                                  mains_a=kwargs["mains_a"], spaces=kwargs["spaces"],
                                  voltage=kwargs["voltage"], mcb=kwargs["mcb"],
                                  mounting=kwargs["mounting"], panel_name=kwargs["panel_name"])
        return "resolver unexpectedly accepted the switchboard rating"
    except Exception as e:                              # FactoryError expected
        return f"{type(e).__name__}: {e}"


def _resolve_panel_facts(fp: FamilyPlan) -> None:
    try:
        from ..famgen import factory as F
        sheet = F.resolve_panelboard_facts(fp.kwargs["vendor"], fp.kwargs["line"],
                                          mains_a=fp.kwargs["mains_a"],
                                          spaces=fp.kwargs["spaces"],
                                          voltage=fp.kwargs["voltage"],
                                          mcb=fp.kwargs["mcb"],
                                          mounting=fp.kwargs["mounting"],
                                          sccr_ka=fp.kwargs.get("sccr_ka"),
                                          panel_name=fp.kwargs["panel_name"])
    except Exception as e:
        fp.status = "refused"
        fp.refusal = f"{type(e).__name__}: {e}"
        return
    fp.status = "resolved"
    fp.catalog = sheet.catalog
    fp.variant = sheet.variant
    fp.facts_summary = {
        "subject": sheet.subject, "model": sheet.get("model"),
        "manufacturer": sheet.get("manufacturer"),
        "dims_in": {"w": sheet.get("width_in"), "h": sheet.get("height_in"),
                    "d": sheet.get("depth_in")},
        "assumed_fields": sheet.assumed(), "unverified_fields": sheet.unverified(),
        "sccr_ka": sheet.get("sccr_ka"), "notes": list(sheet.notes),
    }
    fp.dims_catalog_m = {"w": float(sheet.get("width_in")) / IN_PER_M,
                         "h": float(sheet.get("height_in")) / IN_PER_M,
                         "d": float(sheet.get("depth_in")) / IN_PER_M}


def _resolve_xfmr_facts(fp: FamilyPlan) -> None:
    try:
        from ..famgen import factory as F
        sheet = F.resolve_transformer_facts(fp.kwargs["kva"], vendor=fp.kwargs["vendor"],
                                            primary_v=fp.kwargs["primary_v"],
                                            secondary_v=fp.kwargs["secondary_v"])
    except Exception as e:
        fp.status = "refused"
        fp.refusal = f"{type(e).__name__}: {e}"
        return
    fp.status = "resolved"
    fp.catalog = sheet.catalog
    fp.variant = sheet.variant
    fp.facts_summary = {
        "subject": sheet.subject, "model": sheet.get("model"),
        "manufacturer": sheet.get("manufacturer"),
        "dims_in": {"w": sheet.get("width_in"), "h": sheet.get("height_in"),
                    "d": sheet.get("depth_in")},
        "weight_lb": sheet.get("weight_lb"),
        "assumed_fields": sheet.assumed(), "unverified_fields": sheet.unverified(),
        "notes": list(sheet.notes),
    }
    fp.dims_catalog_m = {"w": float(sheet.get("width_in")) / IN_PER_M,
                         "h": float(sheet.get("height_in")) / IN_PER_M,
                         "d": float(sheet.get("depth_in")) / IN_PER_M}


def plan_families(equipment: List[Equipment]) -> List[FamilyPlan]:
    """The mapping table: one :class:`FamilyPlan` per equipment item."""
    return [plan_family_for(e) for e in equipment]


# ---------------------------------------------------------------------------
# the HOUSE switchboard family (our own dimensions; the factory has no
# switchboard product / catalog line -- see plan_family_for)
# ---------------------------------------------------------------------------

def make_house_switchboard(*, tag: str = "MSB", name: str = "Switchboard",
                          mains_a: float = 2500.0, voltage: Any = "480Y/277",
                          phases: int = 3, wires: int = 4, sccr_ka: float = 65.0,
                          sections: int = 4, mains_device: str = "Main breaker",
                          mounting: str = "floor", feeder_entry: str = "top",
                          manufacturer: str = "", model_label: str = "",
                          width_m: float, depth_m: float, height_m: float,
                          solid: bool = True, start_id: int = 1000):
    """Compose OUR floor-standing SWITCHBOARD family (Electrical Equipment,
    part type 16 = switchboard) from OUR OWN IFC-modeled dimensions -- the
    honest fallback when no catalog line covers the rating.  Same building
    blocks as ``rvt.famgen.factory.make_transformer`` (free-standing box on
    the Reference Level, tagging-contract parameters, one 3-pole supply
    connector on the top face), so the loader / placement paths treat it
    like any generated equipment family.  Returns a
    :class:`rvt.famgen.factory.FamilyProduct`.

    Every dimension is flagged 'given' (source = our IFC), never a catalog
    fact; ``manufacturer`` / ``model_label`` are the IFC-DECLARED identity
    strings carried as parameter values, flagged 'ifc-declared'.
    """
    from ..famgen import factory as F
    from ..famgen import skeleton as SK
    from ..famgen import geometry as G

    W = float(width_m) * FT_PER_M
    D = float(depth_m) * FT_PER_M
    H = float(height_m) * FT_PER_M
    vs = parse_voltage(voltage)
    vll = float(vs.get("ll") or 480.0)
    sheet = F.FactSheet(subject=f"house switchboard {tag} {mains_a:g} A {voltage}",
                        catalog="none (our IFC-modeled dimensions)", variant="house-switchboard")
    sheet.set("width_in", width_m * IN_PER_M, kind="given", source="ifc:tessellated body",
              note="OUR IFC-modeled width (front-lineup extent)")
    sheet.set("depth_in", depth_m * IN_PER_M, kind="given", source="ifc:tessellated body")
    sheet.set("height_in", height_m * IN_PER_M, kind="given", source="ifc:tessellated body")
    sheet.set("voltage_ll_v", vll, kind="given", note=str(voltage))
    sheet.set("voltage_system", str(vs.get("system") or voltage), kind="given")
    sheet.set("phases", int(phases), kind="given")
    sheet.set("wires", int(wires), kind="given")
    sheet.set("mains_rating_a", float(mains_a), kind="given")
    sheet.set("bus_rating_a", float(mains_a), kind="given")
    sheet.set("mains_type", "MCB" if "breaker" in str(mains_device).lower() else "MLO",
              kind="given", note=str(mains_device))
    sheet.set("sccr_ka", float(sccr_ka), kind="given", note="SwitchboardSchedule.ShortCircuitRatingkA")
    sheet.set("sections", int(sections), kind="given")
    sheet.set("mounting", str(mounting), kind="given")
    sheet.set("panel_name", str(tag), kind="given")
    sheet.set("manufacturer", str(manufacturer or "unspecified"), kind="ifc-declared",
              note="Pset_ManufacturerTypeInformation.Manufacturer (declared identity, not a "
                   "catalog fact; no manufacturer geometry / data is carried)")
    sheet.set("model", str(model_label or "house switchboard"), kind="ifc-declared",
              note="Pset_ManufacturerTypeInformation.ModelLabel as the Model VALUE")
    sheet.notes.append("HOUSE SWITCHBOARD: no catalog line on record covers 2500 A "
                       "(the Pow-R-Line PANELBOARD members top out below it and no "
                       "switchboard product exists in the factory) -- dimensions are "
                       "OUR OWN IFC-modeled lineup extents (our authoring), never a "
                       "manufacturer's; the ratings ride as tagging-contract "
                       "parameter values from the SwitchboardSchedule Pset.")

    fam_name = f"{name} {mains_a:g}A {vs.get('system') or voltage}"
    doc = SK.new_family_document("electrical_equipment", fam_name,
                                 part_type=SK.PART_TYPE.get("switchboard", 16),
                                 work_plane_based=False, start_id=start_id,
                                 plane_length_ft=max(6.0, W * 1.5))
    doc.notes.append("house switchboard: floor-standing lineup box at OUR IFC-modeled "
                     "extents; one 3-pole supply connector on the top face (top-entry "
                     "service / feeders per the FeederEntry pset)")
    pW = doc.add_family_parameter("Width", F.SPEC["length"], F.GROUP["dimensions"])
    pH = doc.add_family_parameter("Height", F.SPEC["length"], F.GROUP["dimensions"])
    pD = doc.add_family_parameter("Depth", F.SPEC["length"], F.GROUP["dimensions"])
    contract: Dict[str, Any] = {}
    for pname, spec_k, group_k in F.PANEL_CONTRACT_PARAMS:
        contract[pname] = doc.add_family_parameter(pname, F.SPEC[spec_k], F.GROUP[group_k])
    pSections = doc.add_family_parameter("Sections", F.SPEC["integer"], F.GROUP["electrical"])
    pFeeder = doc.add_family_parameter("FeederEntry", F.SPEC["text"], F.GROUP["electrical"])
    type_name = f"{mains_a:g}A {sections}-section"
    values: Dict[Any, Any] = {
        pW.elem_id: W, pH.elem_id: H, pD.elem_id: D,
        contract["PanelName"].elem_id: str(tag),
        contract["Voltage"].elem_id: SK.volts(vll),
        contract["Phases"].elem_id: int(phases),
        contract["Wires"].elem_id: int(wires),
        contract["BusRating"].elem_id: float(mains_a),
        contract["MainsType"].elem_id: str(sheet.get("mains_type")),
        contract["MainsRating"].elem_id: float(mains_a),
        contract["ShortCircuitRatingkA"].elem_id: float(sccr_ka),
        contract["Mounting"].elem_id: str(mounting),
        contract["NumberOfCircuits"].elem_id: 0,
        contract["NeutralRating"].elem_id: "100%",
        pSections.elem_id: int(sections),
        pFeeder.elem_id: str(feeder_entry),
        "manufacturer": str(sheet.get("manufacturer")),
        "model": str(sheet.get("model")),
        "description": (f"{voltage} V, {phases}-phase {wires}-wire, {mains_a:g} A "
                        f"{mains_device}, {sccr_ka:g} kA SCCR, {sections}-section "
                        f"switchboard lineup ({width_m:g} W x {height_m:g} H x "
                        f"{depth_m:g} D m -- OUR IFC-modeled extents; house family, "
                        f"no catalog record)"),
    }
    doc.add_type(type_name, values)
    fb = F.add_box_form(doc, W, D, H, base_z_ft=0.0, center=(0.0, 0.0),
                        rep=G.REP_SOLID if solid else G.REP_DUMMY)
    fb.params.update({"role": "switchboard lineup enclosure (our IFC-modeled extents)",
                      "dims_m": [width_m, depth_m, height_m]})
    poles = 3 if int(phases) >= 3 else 1
    F.add_connector(doc, host=fb, face="top",
                    location=(0.0, 0.0, H), direction=(0.0, 0.0, 1.0),
                    u_axis=(1.0, 0.0, 0.0), voltage_v=vll, poles=poles,
                    apparent_load_va=0.0, power_factor=1.0,
                    bind_voltage_param="Voltage", load_class="Power",
                    description="Service / feeder bus (top entry)")
    doc.finalize()
    prod = F.FamilyProduct("switchboard", doc, sheet, forms=[fb],
                           file_stem=re.sub(r"[^a-z0-9_]+", "_",
                                             f"switchboard_{tag}_{mains_a:g}A_{vs.get('system') or 'v'}".lower()))
    prod.notes.append("house switchboard from OUR IFC-modeled dimensions (no catalog "
                      "record); ratings are Pset values, identity strings are ifc-declared")
    return prod


# ============================================================================
# THE INTENT MODEL
# ============================================================================

@dataclass
class IntentModel:
    """Everything resolved from one IFC file."""
    source_path: str
    schema: str
    project_name: str
    length_scale_m: float
    levels: List[dict]
    equipment: List[Equipment]
    other_products: List[dict]                      # recorded, unmapped products
    room: Optional[RoomShell]
    clearances: List[ClearanceZone]
    feeders: List[FeederEdge]
    conduit_runs: List[dict]
    family_plans: List[FamilyPlan]
    audit: Dict[str, Any] = dc_field(default_factory=dict)
    notes: List[str] = dc_field(default_factory=list)

    # -- lookups -----------------------------------------------------------
    def by_tag(self, tag: str) -> Optional[Equipment]:
        for e in self.equipment:
            if e.tag == tag:
                return e
        return None

    def plan_for(self, tag: str) -> Optional[FamilyPlan]:
        for p in self.family_plans:
            if p.tag == tag:
                return p
        return None


def _levels(f) -> List[dict]:
    out = []
    scale = _length_scale(f)
    storeys = sorted(f.by_type("IfcBuildingStorey"), key=lambda s: (s.Elevation or 0.0))
    for i, st in enumerate(storeys):
        plc = compose_placement(getattr(st, "ObjectPlacement", None))
        elev_p = float(plc.origin[2]) * scale
        elev_a = float(st.Elevation or 0.0) * scale
        out.append({"id": f"L{i + 1}", "name": st.Name or f"Level {i + 1}",
                    "elevation": _f(elev_a),
                    "elevation_from_placement": _f(elev_p),
                    "step_id": st.id(), "guid": st.GlobalId})
    if not out:
        out.append({"id": "L1", "name": "Level 1", "elevation": 0.0,
                    "elevation_from_placement": 0.0, "step_id": None, "guid": None,
                    "note": "no IfcBuildingStorey: default Level 1 at 0"})
    return out


def _length_scale(f) -> float:
    """Metres per model length unit."""
    try:
        import ifcopenshell.util.unit as uu  # type: ignore
        return float(uu.calculate_unit_scale(f))
    except Exception:
        return 1.0


def resolve_products(f) -> List[Tuple[Any, Placement, ProductGeometry]]:
    """(product, resolved placement, world geometry) for every element
    product -- the reusable core the old front door should import
    (see the ifc_to_spec.py fix-diff in docs/inbox/ifc-room.md)."""
    scale = _length_scale(f)
    out = []
    for p in f.by_type("IfcProduct"):
        if not p.is_a("IfcElement"):
            continue
        if p.is_a("IfcOpeningElement") or p.is_a("IfcFeatureElement"):
            continue
        plc, geom = analyze_product(f, p, scale=scale)
        out.append((p, plc, geom))
    return out


def resolve_intent(ifc_path: str, *, plan_families_flag: bool = True) -> IntentModel:
    """RESOLVE ``ifc_path`` into the placement-true, mapped INTENT."""
    if not _load_ifcos():
        raise IntentError("ifcopenshell is required to read IFC")
    if not os.path.isfile(ifc_path):
        raise IntentError(f"no such file: {ifc_path}")
    f = ifcopenshell.open(ifc_path)
    scale = _length_scale(f)
    proj = (f.by_type("IfcProject") or [None])[0]
    products = resolve_products(f)
    if not products:
        raise IntentError(f"{ifc_path}: no IfcElement products")

    equipment: List[Equipment] = []
    others: List[dict] = []
    room_prod = None
    room_geom = None
    room_psets: Dict[str, Dict[str, Any]] = {}
    clearance_prods: List[Tuple[Any, ProductGeometry, str]] = []
    conduit_prods: List[Tuple[Any, ProductGeometry]] = []

    # ---- pass 1: classify every product; equipment gets a full record
    for prod, plc, geom in products:
        psets = _psets(prod)
        contract = normalize_contract(psets, name=prod.Name or "", object_type=getattr(prod, "ObjectType", None),
                                      description=prod.Description, tag=getattr(prod, "Tag", None))
        kind = _classify_equipment(prod, psets, contract)
        etype = None
        try:
            t = _ue.get_type(prod)
            etype = t.Name if t is not None else None
        except Exception:
            etype = None
        base_rec = {"step_id": prod.id(), "guid": prod.GlobalId, "ifcClass": prod.is_a(),
                    "name": prod.Name, "tag": getattr(prod, "Tag", None), "kind": kind,
                    "description": prod.Description, "typeName": etype,
                    "placementChain": plc.as_json(scale)}
        if kind == "room_shell":
            room_prod, room_geom, room_psets = prod, geom, psets
            others.append({**base_rec, "disposition": "room shell -> walls / doors / pads (see 'room')"})
            continue
        if kind == "clearance":
            clearance_prods.append((prod, geom, str(prod.Description or "")))
            others.append({**base_rec, "disposition": "clearance zones -> annotation (see 'clearances')"})
            continue
        if kind in ("conduit_run", "service_entrance"):
            conduit_prods.append((prod, geom))
        eq = Equipment(step_id=prod.id(), guid=prod.GlobalId, ifc_class=prod.is_a(),
                       predefined_type=(str(getattr(prod, "PredefinedType", "") or "") or None),
                       name=prod.Name or "", tag=str(getattr(prod, "Tag", None) or prod.Name or prod.GlobalId),
                       description=prod.Description, object_type=getattr(prod, "ObjectType", None),
                       type_name=etype, kind=kind, psets=psets, contract=contract,
                       placement=plc, geometry=geom)
        eq.fed_from = contract.get("FedFrom")
        equipment.append(eq)

    # room centre (interior reference) for orientation inference
    room_center = None
    if room_geom is not None and room_geom.has_body:
        slabs = room_geom.items_matching("slab", "floor")
        if slabs:
            room_center = slabs[0].center[:2]
        else:
            room_center = room_geom.center[:2]
    elif equipment:
        pts = np.array([e.geometry.center[:2] for e in equipment if e.geometry.has_body])
        room_center = pts.mean(0) if len(pts) else None

    # ---- pass 2: resolve every equipment placement
    for eq in equipment:
        _resolve_equipment_placement(eq, room_center)
        # disposition: generated content vs recorded-only
        eq.disposition = ("generated-family" if eq.kind in GENERATED_KINDS
                          else ("recorded" if eq.kind in ("ground_bus", "conduit_run",
                                                          "service_entrance", "support",
                                                          "switchgear")
                                else "recorded"))

    # ---- room shell
    room: Optional[RoomShell] = None
    if room_prod is not None:
        room = _extract_room_shell(f, room_prod, room_geom, room_psets)
        _close_room(room)

    # ---- clearances (need the equipment fronts)
    clearances: List[ClearanceZone] = []
    for prod, geom, desc in clearance_prods:
        clearances.extend(_extract_clearances(prod, geom, desc, equipment))

    # ---- feeder tree (+ conduit corroboration)
    feeders, runs = _build_feeder_tree(equipment, conduit_prods)

    # ---- family mapping
    plans = plan_families(equipment) if plan_families_flag else []

    # ---- audit / self-checks
    audit = _audit(equipment, room, feeders)

    model = IntentModel(
        source_path=os.path.abspath(ifc_path), schema=f.schema,
        project_name=(proj.Name if proj else None) or "Imported model",
        length_scale_m=scale, levels=_levels(f), equipment=equipment,
        other_products=others, room=room, clearances=clearances,
        feeders=feeders, conduit_runs=runs, family_plans=plans, audit=audit)
    model.notes += [
        "positions are RECOVERED FROM THE TESSELLATED GEOMETRY: every product's "
        "IfcLocalPlacement chain (product -> storey -> building -> site) composes to "
        "the IDENTITY (the three-d-stage writer bakes world coordinates into the "
        "IfcCartesianPointList3D vertices and gives every product the same identity "
        "IfcAxis2Placement3D); world = composed_chain @ local vertices, so a file WITH "
        "real relative placements resolves through the same formula",
        "orientation = the front normal inferred from named front features "
        "(door / nameplate / meter / breaker faces) or the thin footprint axis "
        "toward the room interior; wall gear gets an upright work-plane frame, "
        "floor gear a yaw",
        "the tagging-contract Pset IS the join key: MSB / DP / LP / T1 map to OUR "
        "generated families with the Pset values as parameter VALUES; the 2500 A "
        "switchboard has NO catalog line -> house family from OUR IFC-modeled extents",
    ]
    return model


def _audit(equipment: List[Equipment], room: Optional[RoomShell],
           feeders: List[FeederEdge]) -> Dict[str, Any]:
    """Self-checks worth surfacing: mirrored panel pairs, positions inside
    the room, feeder-tree closure."""
    a: Dict[str, Any] = {}
    with_pos = [e for e in equipment if e.geometry.has_body]
    a["equipment_with_geometry"] = len(with_pos)
    a["positions_all_zero"] = all(abs(e.insertion_m[0]) < 1e-9 and abs(e.insertion_m[1]) < 1e-9
                                  for e in with_pos) if with_pos else None
    if room and room.clear.get("centerline_extents_m"):
        ext = room.clear["centerline_extents_m"]
        inside = 0
        for e in with_pos:
            x, y = e.insertion_m[0], e.insertion_m[1]
            if ext["x"][0] - 0.05 <= x <= ext["x"][1] + 0.05 and ext["y"][0] - 0.05 <= y <= ext["y"][1] + 0.05:
                inside += 1
        a["equipment_inside_room_ring"] = f"{inside}/{len(with_pos)}"
    tags = {e.tag for e in equipment}
    load_tags = {e.tag for e in equipment if e.kind in GENERATED_KINDS}
    roots = {ed.source for ed in feeders if ed.source not in tags}
    a["feeder_edges"] = len(feeders)
    a["feeder_edges_corroborated"] = sum(1 for ed in feeders if ed.from_pset and ed.conduit_items)
    a["feeder_roots_external"] = sorted(roots)
    fed = {ed.target for ed in feeders}
    a["load_equipment_unfed"] = sorted(t for t in load_tags if t not in fed and t not in roots)
    a["non_load_products"] = sorted(t for t in tags if t not in load_tags)
    return a


# ============================================================================
# JSON (the spec v2)
# ============================================================================

def intent_to_json(model: IntentModel, *, include_geometry_items: bool = True) -> dict:
    """The versioned intent JSON (spec v2)."""
    room_json = model.room.as_json() if model.room else None
    walls_v1 = []
    if model.room:
        for w in model.room.walls:
            walls_v1.append({"id": w.wall_id, "start": _vf(w.p0_m), "end": _vf(w.p1_m),
                             "thickness": _f(w.thickness_m), "height": _f(w.height_m),
                             "type": ("Room shell (from the shell proxy's wall solids)"
                                      if not w.synthesized else
                                      "Room shell (SYNTHESIZED closing wall)"),
                             "derivedFrom": w.derived_from, "synthesized": w.synthesized,
                             "openings": [o.as_json() for o in w.openings]})
    equipment_json = [e.as_json(include_items=include_geometry_items) for e in model.equipment]
    return {
        "specVersion": INTENT_VERSION,
        "intentVersion": INTENT_VERSION,
        "generator": "rvt.ifc.intent",
        "source": {"path": model.source_path, "schema": model.schema,
                   "length_scale_m_per_unit": model.length_scale_m},
        "project": {"name": model.project_name,
                    "description": f"Resolved intent (spec v{INTENT_VERSION}) from "
                                   f"{os.path.basename(model.source_path)} by rvt.ifc.intent"},
        "units": {"length": "m", "angle": "deg"},
        "levels": model.levels,
        "walls": walls_v1,
        "equipment": equipment_json,
        "room": room_json,
        "clearances": [z.as_json() for z in model.clearances],
        "feederTree": {
            "edges": [ed.as_json() for ed in model.feeders],
            "conduitRuns": model.conduit_runs,
            "circuitPlan": [ed.as_json()["circuitPlan"] for ed in model.feeders
                            if ed.kind in ("feeder", "primary", "secondary")],
            "notes": ["each FedFrom edge = one feeder circuit (panel -> load) for "
                      "rvt.mep add_circuit; the UTILITY service edge has no in-model "
                      "circuit (the switchboard's own supply connector stays unconnected)"],
        },
        "familyMapping": [p.as_json() for p in model.family_plans],
        "otherProducts": model.other_products,
        "audit": model.audit,
        "notes": model.notes,
    }


def write_intent(model: IntentModel, out_path: str, *, indent: int = 2) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
    with open(out_path, "w") as fh:
        json.dump(intent_to_json(model), fh, indent=indent, default=str)
    return out_path


def _main(argv: Optional[Sequence[str]] = None) -> int:  # pragma: no cover
    import argparse
    ap = argparse.ArgumentParser(description="IFC -> resolved intent (spec v2)")
    ap.add_argument("ifc")
    ap.add_argument("-o", "--out", default=None)
    a = ap.parse_args(argv)
    model = resolve_intent(a.ifc)
    out = a.out or (os.path.splitext(a.ifc)[0] + ".intent.json")
    write_intent(model, out)
    print(f"intent: {len(model.equipment)} equipment, "
          f"{len(model.room.walls) if model.room else 0} wall(s), "
          f"{len(model.feeders)} feeder edge(s) -> {out}")
    for e in model.equipment:
        print(f"  {e.tag:10s} {e.kind:24s} at {_vf(e.insertion_m[:2])} el={_f(e.elevation_m)} "
              f"front={_vf(e.front_normal[:2])} yaw={_f(e.yaw_deg, 1)}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())

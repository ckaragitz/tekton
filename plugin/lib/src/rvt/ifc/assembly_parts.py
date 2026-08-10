"""rvt.ifc.assembly_parts -- an ARBITRARY-GEOMETRY IFC -> multi-part solids.

THE GAP THIS CLOSES.  The ``ifc -> rfa`` route had exactly two lanes:

* a ROOM IFC whose equipment carries our tagging contract -> catalog
  families (``rvt.ifc.intent`` -> ``rvt.famgen.factory``), and
* a single-PRODUCT IFC -> measured facts -> the one wired archetype
  (``rvt.ifc.product_facts`` -> ``famfrom_ifc.make_downlight``).

An IFC that is neither -- a fabrication assembly, a Claude Design body, any
vendor's LOD-400 export: several sibling products, real meshes, no catalog
identity -- fell between them and was REFUSED (``13 products with geometry
-- name one``).  That refusal was honest but it was also the end of the
road, and steer S-2026-08-10-c (#498) says a self-generated ``.rfa`` is the
only supported family path: "when i go to claude design and ask it to build
me a 3d object you should be able to fully convert that to a rfa file".

THE BRIDGE.  ``rvt.famgen.factory.make_generic_model(parts=[...])`` (#515)
already authors a multi-solid family from box / cylinder / polygon
extrusions.  What was missing was the *measurement*: turning each IFC
product's triangle soup into one of those three prisms.  That is this
module, and only this module -- it reads, it measures, it decides a shape;
it never writes a family.  :func:`assembly_parts` hands the factory its
``parts`` list; the router lane composes and emits.

WHAT IS AND IS NOT CLAIMED (the honesty contract, rule 1 / the FactSheet
``given`` discipline).  Every dimension here is MEASURED FROM THE CALLER'S
MESH and is reported ``given`` with its source -- never a catalog fact, never
a manufacturer claim.  Each part becomes the *prismatic massing* of its mesh:

* the plan footprint is the mesh's convex hull projected on XY, fitted to a
  cylinder / an axis-aligned box / an N-gon (:func:`fit_solid`), and
* it is extruded over the mesh's full Z extent.

:attr:`PartSolid.fill` records exactly how much of that prism the mesh
actually occupies -- the mesh's own closed-surface volume (divergence theorem
over its triangles) over the authored prism's volume -- so the report says
which parts are faithful and which are envelopes, per part, in numbers
instead of adjectives.  Nothing is invented: a product with no tessellated
body is SKIPPED BY NAME, never given a guessed size.

WHEN ONE PRISM IS NOT ENOUGH (:func:`decompose_slabs`).  A body whose section
changes with height -- a stack of nuts and washers, a stepped base -- is cut
at its vertex Z levels and each slab's REAL section is authored
(:func:`slice_loops`), concavity and disjoint regions included; unchanged
slabs merge, so a plain rod stays one part.  Two things make this safe to
trust rather than merely impressive:

* an AMBIGUOUS slice (any welded vertex of degree != 2, i.e. regions touching
  at a point) is refused outright -- guessing there yields a plausible solid
  that is not the body; and
* the result must CONSERVE MATERIAL (:func:`_conserves`).  Filling a hole the
  part contract cannot express only ever ADDS volume; authoring *less* volume
  than the mesh holds means a ring was mis-nested or a region was lost, so
  the decomposition is discarded however good its fill ratio looks.

Either way the caller keeps the single prism and is told which body it was
and why (``AssemblyModel.kept_prism``).  The unfixable case is a section that
runs along X or Y -- a strut channel's C-profile -- because
``add_generic_part`` extrudes along Z only: no rotation is expressible in the
part contract, so that body is honestly an envelope until the contract grows
one.

IDENTITY.  ``Pset_ManufacturerTypeInformation`` (part numbers, references,
manufacturer) is read per product into a bill of materials and authored onto
the family type VERBATIM.  An absent property stays absent: an empty identity
field is honest, an invented one is not.

Pure stdlib (:mod:`rvt.ifc.steplite` through the engine's reader selection,
so no ifcopenshell is needed), no donor bytes, no Autodesk anything.

Territory: ifc-assembly stream (new module; imports steplite + product_facts
helpers, edits neither).
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field as dc_field
from typing import Any, Dict, List, Optional, Sequence, Tuple

__all__ = [
    "AssemblyError", "PartSolid", "AssemblyModel", "FT_PER_M",
    "convex_hull_2d", "fit_solid", "read_assembly", "assembly_parts",
    "slice_loops", "ring_nesting", "mesh_volume", "decompose_slabs",
    "is_axis_aligned", "decompose_boxes",
    "MIN_EXTENT_FT", "CYLINDER_TOLERANCE", "RECT_TOLERANCE", "MAX_HULL_POINTS",
]

FT_PER_M = 1.0 / 0.3048

#: Below this extent (feet) a mesh axis is degenerate -- a part thinner than
#: ~1/64 in in any direction cannot be extruded into a solid Revit will keep.
MIN_EXTENT_FT = 0.0013

#: Hull radii within +/- this fraction of their mean read as a circle.
CYLINDER_TOLERANCE = 0.12

#: Hull area within this fraction of its bounding box reads as a rectangle.
RECT_TOLERANCE = 0.98

#: Cap on the authored N-gon footprint (a tessellated arc can hull to
#: hundreds of points; the family only needs the shape, not the tessellation).
MAX_HULL_POINTS = 48

#: Decimal places vertices are welded to when stitching a slice (~1e-9 ft).
_WELD = 9

#: A single prism at or above this fill is already the body -- do not decompose.
DECOMPOSE_FILL = 0.90

#: Budgets for :func:`decompose_slabs`.  A body needing more than these is
#: kept as its single prism and the cap is REPORTED, never silently applied.
MAX_SLABS = 64
MAX_DECOMPOSED_PARTS = 40

#: A slice ring below this area (ft^2 ~ 0.0144 in^2) is a tessellation sliver.
MIN_SLAB_AREA_FT2 = 1e-4

#: Budget for the axis-aligned box grid (one inside-test per cell).
MAX_GRID_CELLS = 20000

#: An exact box decomposition may use more parts than a lossy slab one: a
#: slotted channel is genuinely many boxes, and each is EXACT.
MAX_BOXES = 120


class AssemblyError(ValueError):
    """The IFC has no product with a tessellated body to measure."""


# ---------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------

@dataclass
class PartSolid:
    """ONE IFC product measured into ONE prismatic solid.

    Lengths are FEET in the assembly frame (the family's frame after
    :meth:`AssemblyModel.recentre`).  ``fit`` names the footprint decision
    (``cylinder`` / ``box`` / ``polygon``) and ``fill`` is the mesh's bbox
    volume over the authored prism's volume -- 1.0 = the prism IS the mesh's
    envelope exactly, lower = an over-approximated massing.
    """
    name: str
    ifc_class: str
    tag: str
    guid: str
    fit: str                                  # cylinder | box | polygon
    center_ft: Tuple[float, float]
    height_ft: float
    base_z_ft: float
    width_ft: Optional[float] = None          # box
    depth_ft: Optional[float] = None          # box
    radius_ft: Optional[float] = None         # cylinder
    vertices_ft: Optional[List[List[float]]] = None   # polygon (absolute plan)
    n_points: int = 0
    n_faces: int = 0
    fill: Optional[float] = None
    bbox_ft: List[List[float]] = dc_field(default_factory=list)
    of_product: str = ""          # the IFC product this solid came from
    slabs: int = 0                # >0 when it is one slab of a decomposition
    part_number: str = ""         # Pset_ManufacturerTypeInformation, verbatim
    reference: str = ""

    def to_part(self) -> Dict[str, Any]:
        """The ``parts=[...]`` dict :func:`rvt.famgen.factory.add_generic_part`
        consumes."""
        part: Dict[str, Any] = {
            "shape": self.fit, "name": self.name,
            "height_ft": self.height_ft, "base_z_ft": self.base_z_ft,
        }
        if self.fit == "cylinder":
            part["radius_ft"] = self.radius_ft
            part["center"] = list(self.center_ft)
        elif self.fit == "polygon":
            # absolute plan ring: add_generic_part offsets by `center`, so the
            # ring already carries the placement and center stays at origin.
            part["vertices"] = self.vertices_ft
        else:
            part["width_ft"] = self.width_ft
            part["depth_ft"] = self.depth_ft
            part["center"] = list(self.center_ft)
        return part

    def to_json(self) -> Dict[str, Any]:
        d = {
            "name": self.name, "ifc_class": self.ifc_class, "tag": self.tag,
            "guid": self.guid, "fit": self.fit,
            "center_ft": [round(c, 6) for c in self.center_ft],
            "height_ft": round(self.height_ft, 6),
            "base_z_ft": round(self.base_z_ft, 6),
            "height_in": round(self.height_ft * 12.0, 4),
            "n_points": self.n_points, "n_faces": self.n_faces,
            "fill": (round(self.fill, 4) if self.fill is not None else None),
            "of_product": self.of_product or self.name,
            "slabs": self.slabs,
            "part_number": self.part_number, "reference": self.reference,
            "bbox_ft": [[round(v, 6) for v in row] for row in self.bbox_ft],
        }
        if self.width_ft is not None:
            d["width_ft"] = round(self.width_ft, 6)
            d["width_in"] = round(self.width_ft * 12.0, 4)
        if self.depth_ft is not None:
            d["depth_ft"] = round(self.depth_ft, 6)
            d["depth_in"] = round(self.depth_ft * 12.0, 4)
        if self.radius_ft is not None:
            d["radius_ft"] = round(self.radius_ft, 6)
            d["diameter_in"] = round(self.radius_ft * 24.0, 4)
        if self.vertices_ft is not None:
            d["polygon_points"] = len(self.vertices_ft)
        return d


@dataclass
class AssemblyModel:
    """Every measurable product of one IFC, as prismatic solids."""
    source_path: str
    schema: str
    project_name: str
    application: str
    assembly_name: str
    unit_scale_m: float
    parts: List[PartSolid]
    skipped: List[Dict[str, str]] = dc_field(default_factory=list)
    decomposed: List[Dict[str, Any]] = dc_field(default_factory=list)
    kept_prism: List[Dict[str, str]] = dc_field(default_factory=list)
    identity: Dict[str, str] = dc_field(default_factory=dict)
    assembly_tag: str = ""
    assembly_description: str = ""
    origin_shift_ft: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    notes: List[str] = dc_field(default_factory=list)

    # -- overall extents ---------------------------------------------------
    def bbox_ft(self) -> List[List[float]]:
        if not self.parts:
            return [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        mn = [min(p.bbox_ft[0][i] for p in self.parts) for i in range(3)]
        mx = [max(p.bbox_ft[1][i] for p in self.parts) for i in range(3)]
        return [mn, mx]

    def dims_ft(self) -> Dict[str, float]:
        mn, mx = self.bbox_ft()
        return {"x": mx[0] - mn[0], "y": mx[1] - mn[1], "z": mx[2] - mn[2]}

    def to_parts(self) -> List[Dict[str, Any]]:
        return [p.to_part() for p in self.parts]

    def to_json(self) -> Dict[str, Any]:
        d = self.dims_ft()
        return {
            "source_path": self.source_path, "schema": self.schema,
            "project_name": self.project_name, "application": self.application,
            "assembly_name": self.assembly_name,
            "unit_scale_m": self.unit_scale_m,
            "part_count": len(self.parts),
            "origin_shift_ft": [round(v, 6) for v in self.origin_shift_ft],
            "overall_bbox_ft": [[round(v, 6) for v in row] for row in self.bbox_ft()],
            "overall_dims_ft": {k: round(v, 6) for k, v in d.items()},
            "overall_dims_in": {k: round(v * 12.0, 4) for k, v in d.items()},
            "fit_counts": self.fit_counts(),
            "product_count": len({p.of_product or p.name for p in self.parts}),
            "parts": [p.to_json() for p in self.parts],
            "decomposed": list(self.decomposed),
            "kept_prism": list(self.kept_prism),
            "identity": dict(self.identity),
            "assembly_tag": self.assembly_tag,
            "assembly_description": self.assembly_description,
            "bill_of_materials": self.bill_of_materials(),
            "skipped": list(self.skipped),
            "notes": list(self.notes),
        }

    def bill_of_materials(self) -> List[Dict[str, Any]]:
        """One row per distinct source product: its part number, reference and
        how many solids were authored for it.  Read straight off the IFC's
        ``Pset_ManufacturerTypeInformation`` -- carried VERBATIM, never
        normalised into a catalog claim we cannot back."""
        rows: Dict[str, Dict[str, Any]] = {}
        for p in self.parts:
            key = p.of_product or p.name
            row = rows.setdefault(key, {"product": key, "ifc_class": p.ifc_class,
                                        "part_number": p.part_number,
                                        "reference": p.reference, "solids": 0})
            row["solids"] += 1
        return list(rows.values())

    def fit_counts(self) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for p in self.parts:
            out[p.fit] = out.get(p.fit, 0) + 1
        return out

    def recentre(self) -> "AssemblyModel":
        """Move the family origin to the assembly's PLAN CENTRE at its BASE.

        Revit families are placed by their origin; a body sitting at the IFC's
        site coordinates would land hundreds of feet from the insertion point.
        The shift is recorded (``origin_shift_ft``) so the mapping back to the
        source IFC's coordinates stays exact.
        """
        if not self.parts:
            return self
        mn, mx = self.bbox_ft()
        dx = -(mn[0] + mx[0]) / 2.0
        dy = -(mn[1] + mx[1]) / 2.0
        dz = -mn[2]
        if abs(dx) < 1e-12 and abs(dy) < 1e-12 and abs(dz) < 1e-12:
            return self
        for p in self.parts:
            p.center_ft = (p.center_ft[0] + dx, p.center_ft[1] + dy)
            p.base_z_ft += dz
            if p.vertices_ft is not None:
                p.vertices_ft = [[v[0] + dx, v[1] + dy] for v in p.vertices_ft]
            p.bbox_ft = [[p.bbox_ft[0][0] + dx, p.bbox_ft[0][1] + dy, p.bbox_ft[0][2] + dz],
                         [p.bbox_ft[1][0] + dx, p.bbox_ft[1][1] + dy, p.bbox_ft[1][2] + dz]]
        self.origin_shift_ft = (dx, dy, dz)
        self.notes.append(
            f"family origin = the assembly's plan centre at its base; the source "
            f"IFC body was shifted ({dx:+.4f}, {dy:+.4f}, {dz:+.4f}) ft to get there")
        return self


# ---------------------------------------------------------------------------
# plan geometry
# ---------------------------------------------------------------------------

def convex_hull_2d(points: Sequence[Sequence[float]]) -> List[List[float]]:
    """Counter-clockwise convex hull (monotone chain), collinear points
    dropped.  Fewer than 3 distinct points -> the distinct points as given."""
    pts = sorted({(round(float(p[0]), 9), round(float(p[1]), 9)) for p in points})
    if len(pts) < 3:
        return [list(p) for p in pts]

    def cross(o, a, b) -> float:
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    upper: List[Tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    hull = lower[:-1] + upper[:-1]
    return [list(p) for p in hull] if len(hull) >= 3 else [list(p) for p in pts]


def _polygon_area(ring: Sequence[Sequence[float]]) -> float:
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _decimate(ring: List[List[float]], limit: int) -> List[List[float]]:
    """Keep a ring's shape while capping its vertex count: drop the vertex
    whose removal changes the area least, repeatedly."""
    ring = [list(v) for v in ring]
    while len(ring) > limit:
        best_i, best_loss = 1, float("inf")
        for i in range(len(ring)):
            a, b, c = ring[i - 1], ring[i], ring[(i + 1) % len(ring)]
            loss = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2.0
            if loss < best_loss:
                best_i, best_loss = i, loss
        ring.pop(best_i)
    return ring


def fit_solid(points_ft: Sequence[Sequence[float]],
              mesh_volume_ft3: Optional[float] = None) -> Dict[str, Any]:
    """Fit ONE prism to a mesh's world points (feet).

    Returns ``{fit, center, height_ft, base_z_ft, bbox, fill, ...}`` -- the
    footprint decision plus the numbers that justify it.  ``mesh_volume_ft3``
    (from :func:`mesh_volume`) turns ``fill`` into the real occupancy of the
    authored prism; without it ``fill`` is ``None`` (unknown, never assumed
    to be 1.0).  Raises :class:`AssemblyError` when the mesh is degenerate in
    any axis (no solid can be authored from it, and inventing a thickness is
    forbidden).
    """
    if not points_ft:
        raise AssemblyError("no points")
    xs = [float(p[0]) for p in points_ft]
    ys = [float(p[1]) for p in points_ft]
    zs = [float(p[2]) for p in points_ft]
    mn = [min(xs), min(ys), min(zs)]
    mx = [max(xs), max(ys), max(zs)]
    ext = [mx[i] - mn[i] for i in range(3)]
    thin = [n for n, e in zip("xyz", ext) if e < MIN_EXTENT_FT]
    if thin:
        raise AssemblyError(
            f"degenerate in {'/'.join(thin)} ({', '.join(f'{n}={e * 12.0:.4f} in' for n, e in zip('xyz', ext))})"
            f": a solid needs three real extents")

    height = ext[2]
    hull = convex_hull_2d([(x, y) for x, y in zip(xs, ys)])
    bbox_area = ext[0] * ext[1]
    common = {"height_ft": height, "base_z_ft": mn[2], "bbox": [mn, mx]}

    def _fill(prism_vol: float) -> Optional[float]:
        if mesh_volume_ft3 is None or prism_vol <= 0:
            return None
        return float(mesh_volume_ft3) / prism_vol

    # -- circle? radii about the hull centroid all within tolerance ---------
    if len(hull) >= 8:
        cx = sum(v[0] for v in hull) / len(hull)
        cy = sum(v[1] for v in hull) / len(hull)
        radii = [math.hypot(v[0] - cx, v[1] - cy) for v in hull]
        mean_r = sum(radii) / len(radii)
        if mean_r > 0 and (max(radii) - min(radii)) / mean_r <= CYLINDER_TOLERANCE:
            return dict(common, fit="cylinder", center=(cx, cy), radius_ft=mean_r,
                        fill=_fill(math.pi * mean_r * mean_r * height))

    hull_area = _polygon_area(hull) if len(hull) >= 3 else 0.0

    # -- axis-aligned rectangle, or a hull too thin to author as an N-gon --
    if bbox_area <= 0 or hull_area <= 0 or len(hull) < 3 \
            or hull_area / bbox_area >= RECT_TOLERANCE:
        return dict(common, fit="box",
                    center=((mn[0] + mx[0]) / 2.0, (mn[1] + mx[1]) / 2.0),
                    width_ft=ext[0], depth_ft=ext[1], fill=_fill(bbox_area * height))

    # -- anything else: the hull itself (a rotated rectangle is exact here) -
    ring = _decimate(hull, MAX_HULL_POINTS) if len(hull) > MAX_HULL_POINTS else hull
    return dict(common, fit="polygon", center=(0.0, 0.0), vertices=ring,
                fill=_fill(_polygon_area(ring) * height))


def slice_loops(points: Sequence[Sequence[float]],
                triangles: Sequence[Sequence[int]],
                z: float) -> Optional[List[List[List[float]]]]:
    """The closed cross-section rings of a mesh at the horizontal plane ``z``.

    Each triangle straddling the plane contributes one segment; segments are
    welded end-to-end into closed rings.  ``z`` is expected to be a SLAB
    MIDPOINT (strictly between two vertex levels), so no vertex lies on the
    plane and the strictly-signed test below is exact -- that is what keeps
    this free of the usual coplanar-vertex special cases.

    Rings come back unordered and un-nested; :func:`ring_nesting` says which
    are solid and which are holes.  None means the slice is AMBIGUOUS (see
    :func:`_stitch`) -- not "no rings", which is an empty list.
    """
    segs: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    for tri in triangles:
        if len(tri) < 3:
            continue
        try:
            P = [points[tri[0]], points[tri[1]], points[tri[2]]]
        except IndexError:
            continue
        hit: List[Tuple[float, float]] = []
        for i in range(3):
            p, q = P[i], P[(i + 1) % 3]
            if (p[2] - z) * (q[2] - z) < 0.0:
                t = (z - p[2]) / (q[2] - p[2])
                hit.append((round(p[0] + t * (q[0] - p[0]), _WELD),
                            round(p[1] + t * (q[1] - p[1]), _WELD)))
        if len(hit) == 2 and hit[0] != hit[1]:
            segs.append((hit[0], hit[1]))
    def inside(pt):                # robust at a junction: the 3D body itself
        return abs(winding_number(points, triangles, (pt[0], pt[1], z))) >= 0.5

    rings = _stitch(segs, inside)
    if rings is None:
        return None
    return rings


def _stitch(segs: Sequence[Tuple[Tuple[float, float], Tuple[float, float]]],
            inside: Optional[Any] = None
            ) -> Optional[List[List[List[float]]]]:
    """Weld segments into closed rings, each segment used exactly once.

    Returns None when the slice is AMBIGUOUS -- any welded vertex with a
    degree other than 2, which is where two regions touch at a point or the
    plane grazes an edge.  There the ring set is not determined by the
    segments alone, and guessing produces a plausible-looking solid that is
    not the body.  The caller falls back to the single prism and says so.
    """
    from collections import defaultdict
    adj: Dict[Tuple[float, float], List[int]] = defaultdict(list)
    for i, (a, b) in enumerate(segs):
        adj[a].append(i)
        adj[b].append(i)
    if any(len(v) % 2 for v in adj.values()):
        return None                                     # an open chain: refuse
    pair_at = _junction_pairs(segs, adj, inside)
    if pair_at is None:
        return None
    used = [False] * len(segs)
    rings: List[List[List[float]]] = []
    for start_i in range(len(segs)):
        if used[start_i]:
            continue
        used[start_i] = True
        a, b = segs[start_i]
        ring = [a, b]
        cur = b
        prev = start_i
        while cur != a:
            nxt = pair_at.get((cur, prev), -1)          # the junction's own pairing
            if nxt < 0 or used[nxt]:
                nxt = -1
                for j in adj.get(cur, ()):              # degree 2: the other one
                    if not used[j]:
                        nxt = j
                        break
            if nxt < 0:
                break                                   # open chain: not a ring
            prev = nxt
            used[nxt] = True
            p, q = segs[nxt]
            cur = q if p == cur else p
            ring.append(cur)
        if cur == a and len(ring) >= 4:                 # closed (last == first)
            rings.append([list(v) for v in ring[:-1]])
    return [_drop_collinear(r) for r in rings if len(r) >= 3]



def _seg_inside(segs: Sequence[Tuple[Tuple[float, float], Tuple[float, float]]],
                pt: Sequence[float]) -> bool:
    """Even-odd test of a point against a slice's segment set (the section's
    own boundary), used to tell a MATERIAL wedge from an empty one."""
    x, y = float(pt[0]), float(pt[1])
    inside = False
    for (x1, y1), (x2, y2) in segs:
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def _junction_pairs(segs, adj, inside=None):
    """Resolve vertices where more than two segments meet.

    Two regions of a section can touch at a single point -- a C-clamp's throat
    closing on itself, two slots meeting at a corner.  The segments alone do
    not say which continues into which, and the older code refused the whole
    slice for it.  They ARE determined by the material: sort the incident
    directions by angle, and the two segments bounding a wedge that is INSIDE
    the section belong to the same ring.  Returns ``{(vertex, from_seg):
    to_seg}``, or None when a junction cannot be resolved consistently (every
    segment must be paired exactly once).
    """
    pair_at: Dict[Tuple[Tuple[float, float], int], int] = {}
    for v, inc in adj.items():
        if len(inc) <= 2:
            continue
        spokes = []
        for i in inc:
            a, b = segs[i]
            other = b if a == v else a
            d = (other[0] - v[0], other[1] - v[1])
            n = math.hypot(*d)
            if n <= 0:
                return None
            spokes.append((math.atan2(d[1], d[0]), i, n))
        spokes.sort()
        eps = min(s[2] for s in spokes) * 0.05
        taken: Dict[int, int] = {}
        for k in range(len(spokes)):
            a1, i1, _ = spokes[k]
            a2, i2, _ = spokes[(k + 1) % len(spokes)]
            mid = a1 + ((a2 - a1) % (2.0 * math.pi)) / 2.0
            probe = (v[0] + eps * math.cos(mid), v[1] + eps * math.sin(mid))
            hit = inside(probe) if inside is not None else _seg_inside(segs, probe)
            if not hit:
                continue                                # empty wedge
            if i1 in taken or i2 in taken:
                return None                             # inconsistent pairing
            taken[i1] = i2
            taken[i2] = i1
        if len(taken) != len(inc):
            return None                                 # not every spoke paired
        for i1, i2 in taken.items():
            pair_at[(v, i1)] = i2
    return pair_at


def _drop_collinear(ring: Sequence[Sequence[float]], eps: float = 1e-12
                    ) -> List[List[float]]:
    out: List[List[float]] = []
    n = len(ring)
    for i in range(n):
        a, b, c = ring[i - 1], ring[i], ring[(i + 1) % n]
        if abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) > eps:
            out.append([float(b[0]), float(b[1])])
    return out if len(out) >= 3 else [[float(v[0]), float(v[1])] for v in ring]


def _point_in_ring(pt: Sequence[float], ring: Sequence[Sequence[float]]) -> bool:
    x, y = float(pt[0]), float(pt[1])
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if (y1 > y) != (y2 > y):
            xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if xi > x:
                inside = not inside
    return inside


def ring_nesting(rings: Sequence[Sequence[Sequence[float]]]) -> List[int]:
    """Even-odd nesting depth per ring: 0 = solid outer, 1 = a hole in it,
    2 = an island inside that hole, ...

    Containment is tested with a ring's own VERTEX, not its interior point: a
    slice's rings are disjoint (the ambiguous case is refused upstream), so a
    boundary point of A lies in B exactly when A lies in B -- whereas an
    interior point of a ring that CONTAINS others is inside those others and
    would count them as its own parents.
    """
    return [sum(1 for j, other in enumerate(rings)
                if j != i and _point_in_ring(rings[i][0], other))
            for i in range(len(rings))]


def mesh_volume(points: Sequence[Sequence[float]],
                triangles: Sequence[Sequence[int]]) -> float:
    """The enclosed volume of a CLOSED triangle mesh (divergence theorem:
    the signed tetrahedra a face makes with the origin).

    A mesh that is not watertight gives a meaningless number, so callers use
    this only for the ``fill`` ratio -- a reported measurement, never a
    dimension anything is authored from.
    """
    total = 0.0
    n = len(points)
    for tri in triangles:
        if len(tri) < 3:
            continue
        a, b, c = tri[0], tri[1], tri[2]
        if not (0 <= a < n and 0 <= b < n and 0 <= c < n):
            continue
        p, q, r = points[a], points[b], points[c]
        total += (p[0] * (q[1] * r[2] - q[2] * r[1])
                  - p[1] * (q[0] * r[2] - q[2] * r[0])
                  + p[2] * (q[0] * r[1] - q[1] * r[0])) / 6.0
    return abs(total)


# ---------------------------------------------------------------------------
# slab decomposition -- the honest answer to "one prism is an envelope"
# ---------------------------------------------------------------------------

def decompose_slabs(points: Sequence[Sequence[float]],
                    triangles: Sequence[Sequence[int]], *,
                    max_slabs: int = MAX_SLABS,
                    max_parts: int = MAX_DECOMPOSED_PARTS,
                    min_area_ft2: float = MIN_SLAB_AREA_FT2
                    ) -> Optional[Dict[str, Any]]:
    """Cut a mesh into horizontal slabs and author each slab's REAL
    cross-section, so a body whose section changes with height stops being
    one fat envelope.

    Between two consecutive vertex Z levels a closed mesh's cross-section is
    constant, so the midpoint slice (:func:`slice_loops`) IS that slab's exact
    section -- concavity, disjoint regions and all.  Adjacent slabs whose
    section did not change are merged, so a plain rod stays ONE part while a
    C-channel becomes its back plate plus its two walls.

    Returns ``{parts, volume_ft3, n_slabs, holes_filled, dropped}``, or None
    when the body does not decompose usefully (one level, or the result would
    blow the budgets -- a cap the caller REPORTS rather than hides).  Holes
    are not expressible in the part contract: a ring at odd nesting depth is
    dropped from the solid set and counted in ``holes_filled``.
    """
    if not triangles:
        return None
    levels = sorted({round(float(p[2]), _WELD) for p in points})
    slabs_z = [(levels[i], levels[i + 1]) for i in range(len(levels) - 1)
               if levels[i + 1] - levels[i] > MIN_EXTENT_FT]
    if not slabs_z or len(slabs_z) > max_slabs:
        return None

    raw: List[Tuple[float, float, List[List[List[float]]]]] = []
    holes = dropped = 0
    for z0, z1 in slabs_z:
        rings = slice_loops(points, triangles, (z0 + z1) / 2.0)
        if rings is None:
            return None                                 # ambiguous slice
        if not rings:
            continue
        solid: List[List[List[float]]] = []
        for r, d in zip(rings, ring_nesting(rings)):
            if d % 2:                                   # a hole, not a solid
                holes += 1
                continue
            if _polygon_area(r) < min_area_ft2:         # slice sliver
                dropped += 1
                continue
            solid.append(r)
        if solid:
            raw.append((z0, z1, solid))
    if not raw:
        return None

    merged: List[List[Any]] = []
    for z0, z1, rings in raw:
        if merged and abs(merged[-1][1] - z0) <= 10.0 ** -_WELD \
                and _same_section(merged[-1][2], rings):
            merged[-1][1] = z1                          # the section continues
        else:
            merged.append([z0, z1, rings])

    if sum(len(r) for _, _, r in merged) > max_parts:
        return None

    parts: List[Dict[str, Any]] = []
    volume = 0.0
    for z0, z1, rings in merged:
        h = z1 - z0
        for ring in rings:
            out = _decimate(ring, MAX_HULL_POINTS) if len(ring) > MAX_HULL_POINTS else ring
            parts.append({"shape": "polygon", "vertices": out,
                          "height_ft": h, "base_z_ft": z0})
            volume += _polygon_area(out) * h
    return {"parts": parts, "volume_ft3": volume, "n_slabs": len(merged),
            "holes_filled": holes, "dropped": dropped}


def _conserves(authored_ft3: float, mesh_ft3: float, tol: float = 0.02) -> bool:
    """A decomposition may only ADD material (a hole it cannot express gets
    filled), never LOSE it.  Authored < mesh means a ring was mis-nested or a
    region went missing -- the decomposition is wrong and must be discarded,
    however good its fill ratio looks."""
    return authored_ft3 >= mesh_ft3 * (1.0 - tol)


def is_axis_aligned(points: Sequence[Sequence[float]],
                    triangles: Sequence[Sequence[int]],
                    eps: float = 1e-4) -> bool:
    """True when every face normal is parallel to X, Y or Z.

    Such a body is an axis-aligned polyhedron, and :func:`decompose_boxes`
    reproduces it EXACTLY out of boxes -- no envelope, no rotation.  A body
    with one slanted or curved face is not, and box decomposition would
    return a staircase, so it is not attempted.
    """
    for tri in triangles:
        if len(tri) < 3:
            continue
        try:
            p, q, r = points[tri[0]], points[tri[1]], points[tri[2]]
        except IndexError:
            continue
        u = [q[i] - p[i] for i in range(3)]
        v = [r[i] - p[i] for i in range(3)]
        n = [u[1] * v[2] - u[2] * v[1],
             u[2] * v[0] - u[0] * v[2],
             u[0] * v[1] - u[1] * v[0]]
        mag = math.sqrt(sum(x * x for x in n))
        if mag <= 0:
            continue                                    # degenerate triangle
        if max(abs(x) / mag for x in n) < 1.0 - eps:
            return False
    return True


def winding_number(points: Sequence[Sequence[float]],
                   triangles: Sequence[Sequence[int]],
                   pt: Sequence[float]) -> float:
    """The generalised winding number of a triangle mesh about ``pt``.

    The sum of the triangles' SIGNED solid angles / 4*pi (Van Oosterom &
    Strackee): ~1 inside a correctly-oriented closed shell, ~0 outside.

    This is used instead of parity ray-casting because real fabrication
    meshes are not always clean closed manifolds -- the trapeze hanger's
    "back-to-back" strut pair is two shells welded along a seam, with
    INTERNAL faces and non-manifold edges.  A ray crossing an internal face
    flips parity and reports solid material as empty; the winding number is
    unaffected by internal faces and by which shell the point sits in.
    """
    total = 0.0
    ox, oy, oz = float(pt[0]), float(pt[1]), float(pt[2])
    for tri in triangles:
        if len(tri) < 3:
            continue
        try:
            p, q, r = points[tri[0]], points[tri[1]], points[tri[2]]
        except IndexError:
            continue
        ax, ay, az = p[0] - ox, p[1] - oy, p[2] - oz
        bx, by, bz = q[0] - ox, q[1] - oy, q[2] - oz
        cx, cy, cz = r[0] - ox, r[1] - oy, r[2] - oz
        la = math.sqrt(ax * ax + ay * ay + az * az)
        lb = math.sqrt(bx * bx + by * by + bz * bz)
        lc = math.sqrt(cx * cx + cy * cy + cz * cz)
        if la <= 0.0 or lb <= 0.0 or lc <= 0.0:
            continue                                    # point ON a vertex
        num = (ax * (by * cz - bz * cy)
               - ay * (bx * cz - bz * cx)
               + az * (bx * cy - by * cx))
        den = (la * lb * lc
               + (ax * bx + ay * by + az * bz) * lc
               + (ax * cx + ay * cy + az * cz) * lb
               + (bx * cx + by * cy + bz * cz) * la)
        total += 2.0 * math.atan2(num, den)
    return total / (4.0 * math.pi)


def _inside(points: Sequence[Sequence[float]], triangles: Sequence[Sequence[int]],
            pt: Sequence[float]) -> bool:
    """Is ``pt`` inside the body?  |winding number| at or above 1/2.

    The MAGNITUDE, because face orientation is the exporter's choice, not a
    fact about the solid: this IFC winds its triangles so that inside reads
    -1, and :func:`mesh_volume` already takes the same absolute value.
    """
    return abs(winding_number(points, triangles, pt)) >= 0.5


def decompose_boxes(points: Sequence[Sequence[float]],
                    triangles: Sequence[Sequence[int]], *,
                    max_cells: int = MAX_GRID_CELLS,
                    max_boxes: int = MAX_BOXES
                    ) -> Optional[Dict[str, Any]]:
    """Reproduce an AXIS-ALIGNED body exactly as a set of axis-aligned boxes.

    The body's own vertex coordinates cut space into a grid whose every cell
    is wholly inside or wholly outside it (that is what axis-aligned means),
    so testing one point per cell classifies the cell exactly.  Occupied cells
    are then merged greedily into maximal boxes -- and every box is a plain
    Z-extruded rectangle, which the part contract already expresses.

    THIS IS WHY NO ROTATION IS NEEDED for the C-channel case: a channel is a
    union of axis-aligned boxes (back plate + two walls), each of which is
    Z-extrudable whatever direction the channel runs.  Returns
    ``{parts, volume_ft3, n_boxes, cells}`` or None (not axis-aligned, or over
    a budget -- reported by the caller, never silently truncated).
    """
    if not triangles or not is_axis_aligned(points, triangles):
        return None
    axes = [sorted({round(float(p[i]), _WELD) for p in points}) for i in range(3)]
    dims = [len(a) - 1 for a in axes]
    if min(dims) < 1 or dims[0] * dims[1] * dims[2] > max_cells:
        return None

    occ: Dict[Tuple[int, int, int], bool] = {}
    overlap = 0.0            # volume the mesh counts twice (shells that overlap)
    for i in range(dims[0]):
        cx = (axes[0][i] + axes[0][i + 1]) / 2.0
        for j in range(dims[1]):
            cy = (axes[1][j] + axes[1][j + 1]) / 2.0
            for k in range(dims[2]):
                cz = (axes[2][k] + axes[2][k + 1]) / 2.0
                w = abs(winding_number(points, triangles, (cx, cy, cz)))
                if w >= 0.5:
                    occ[(i, j, k)] = True
                    if w >= 1.5:      # inside two shells at once
                        overlap += ((axes[0][i + 1] - axes[0][i])
                                    * (axes[1][j + 1] - axes[1][j])
                                    * (axes[2][k + 1] - axes[2][k])) * (round(w) - 1)
    if not occ:
        return None

    # greedy maximal boxes: grow in x, then y, then z
    used: set = set()
    boxes: List[Tuple[int, int, int, int, int, int]] = []
    for k in range(dims[2]):
        for j in range(dims[1]):
            for i in range(dims[0]):
                if (i, j, k) in used or (i, j, k) not in occ:
                    continue
                i1 = i
                while (i1 + 1 < dims[0] and (i1 + 1, j, k) in occ
                       and (i1 + 1, j, k) not in used):
                    i1 += 1
                j1 = j
                while j1 + 1 < dims[1] and all(
                        (x, j1 + 1, k) in occ and (x, j1 + 1, k) not in used
                        for x in range(i, i1 + 1)):
                    j1 += 1
                k1 = k
                while k1 + 1 < dims[2] and all(
                        (x, y, k1 + 1) in occ and (x, y, k1 + 1) not in used
                        for x in range(i, i1 + 1) for y in range(j, j1 + 1)):
                    k1 += 1
                for x in range(i, i1 + 1):
                    for y in range(j, j1 + 1):
                        for z in range(k, k1 + 1):
                            used.add((x, y, z))
                boxes.append((i, i1, j, j1, k, k1))
                if len(boxes) > max_boxes:
                    return None

    parts: List[Dict[str, Any]] = []
    volume = 0.0
    for i, i1, j, j1, k, k1 in boxes:
        x0, x1 = axes[0][i], axes[0][i1 + 1]
        y0, y1 = axes[1][j], axes[1][j1 + 1]
        z0, z1 = axes[2][k], axes[2][k1 + 1]
        w, d, h = x1 - x0, y1 - y0, z1 - z0
        parts.append({"shape": "box", "width_ft": w, "depth_ft": d,
                      "height_ft": h, "base_z_ft": z0,
                      "center": [(x0 + x1) / 2.0, (y0 + y1) / 2.0]})
        volume += w * d * h
    return {"parts": parts, "volume_ft3": volume, "n_boxes": len(parts),
            "cells": len(occ), "overlap_ft3": overlap, "exact": True}


def _same_section(a: Sequence[Sequence[Sequence[float]]],
                  b: Sequence[Sequence[Sequence[float]]]) -> bool:
    """Two slabs carry the same section (so they merge into one taller part)."""
    if len(a) != len(b):
        return False
    return (sorted(tuple(tuple(v) for v in r) for r in a)
            == sorted(tuple(tuple(v) for v in r) for r in b))


# ---------------------------------------------------------------------------
# reading
# ---------------------------------------------------------------------------

def _apply(m: Sequence[Sequence[float]], p: Sequence[float]) -> Tuple[float, float, float]:
    x, y, z = float(p[0]), float(p[1]), float(p[2] if len(p) > 2 else 0.0)
    return (m[0][0] * x + m[0][1] * y + m[0][2] * z + m[0][3],
            m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3],
            m[2][0] * x + m[2][1] * y + m[2][2] * z + m[2][3])


def _tessellations(product, representation_identifier: str = "Body") -> List[Any]:
    """Every tessellated body item of a product (mapped items unwrapped)."""
    pdef = getattr(product, "Representation", None)
    if pdef is None:
        return []
    reps = [r for r in (pdef.Representations or ())
            if str(getattr(r, "RepresentationIdentifier", "") or "") == representation_identifier]
    if not reps:
        reps = list(pdef.Representations or ())
    items: List[Any] = []
    for r in reps:
        for it in (r.Items or ()):
            if it.is_a("IfcMappedItem"):
                src = it.MappingSource.MappedRepresentation
                items.extend(list(src.Items or ()))
            else:
                items.append(it)
    return [it for it in items
            if it.is_a("IfcTessellatedFaceSet") or it.is_a("IfcTriangulatedFaceSet")
            or it.is_a("IfcPolygonalFaceSet")]


def _mesh_triangles(item) -> List[Tuple[int, int, int]]:
    """Zero-based triangles of a tessellated item (IFC indices are 1-based).

    ``IfcTriangulatedFaceSet`` carries ``CoordIndex`` directly;
    ``IfcPolygonalFaceSet`` faces are fanned into triangles.  An item whose
    faces cannot be read yields ``[]`` -- the part is still measured, only
    its ``fill`` goes unreported.
    """
    ci = getattr(item, "CoordIndex", None)
    if ci:
        return [(int(t[0]) - 1, int(t[1]) - 1, int(t[2]) - 1)
                for t in ci if t is not None and len(t) >= 3]
    tris: List[Tuple[int, int, int]] = []
    for face in (getattr(item, "Faces", None) or ()):
        idx = getattr(face, "CoordIndex", None)
        if not idx or len(idx) < 3:
            continue
        ring = [int(i) - 1 for i in idx]
        for k in range(1, len(ring) - 1):       # triangle fan
            tris.append((ring[0], ring[k], ring[k + 1]))
    return tris


#: IFC property names we read identity from, most specific first.  Everything
#: is carried VERBATIM: these are the caller's strings, not catalog facts.
_PART_NUMBER_PROPS = ("PartNumber", "ArticleNumber", "ModelReference",
                      "ModelLabel", "GlobalTradeItemNumber")
_REFERENCE_PROPS = ("Reference", "Description", "Tag")


def _props(product) -> Dict[str, Any]:
    """Every single-value property of a product, flattened across its psets."""
    from . import product_facts as PF
    out: Dict[str, Any] = {}
    try:
        for props in (PF._collect_psets(product) or {}).values():
            for k, v in props.items():
                out.setdefault(str(k), v.get("value"))
    except Exception:
        return {}
    return out


def _identity_of(product) -> Tuple[str, str]:
    """``(part_number, reference)`` for one product, verbatim or ''."""
    p = _props(product)
    pn = next((str(p[k]) for k in _PART_NUMBER_PROPS if p.get(k) not in (None, "")), "")
    if not pn:
        pn = str(getattr(product, "Tag", "") or "")
    ref = next((str(p[k]) for k in _REFERENCE_PROPS if p.get(k) not in (None, "")), "")
    return pn, ref


def _pset_identity(product) -> Dict[str, str]:
    """The assembly's identity data mapped onto the family-type fields Revit
    schedules (``manufacturer`` / ``model`` / ``url``).  Absent stays ABSENT --
    an empty identity field is honest, an invented one is not."""
    p = _props(product)
    out: Dict[str, str] = {}
    for key, names in (("manufacturer", ("Manufacturer",)),
                       ("model", _PART_NUMBER_PROPS),
                       ("url", ("URL", "ProductURL"))):
        v = next((str(p[n]) for n in names if p.get(n) not in (None, "")), "")
        if v:
            out[key] = v
    return out


def _name_of(prod, index: int) -> str:
    for attr in ("Name", "Description", "Tag"):
        v = getattr(prod, attr, None)
        if v:
            return str(v)
    return f"{prod.is_a()} {index + 1}"


def read_assembly(ifc_path: str, *, recentre: bool = True,
                  decompose: bool = True) -> AssemblyModel:
    """Measure EVERY product with a tessellated body into a :class:`PartSolid`.

    World coordinates: each mesh's points are carried through its product's
    full ``IfcLocalPlacement`` chain, so parts keep their real relative
    positions (the assembly, not a pile at the origin).  Model units are
    converted to feet from the project's ``IfcUnitAssignment``.
    """
    path = os.path.abspath(ifc_path)
    if not os.path.isfile(path):
        raise AssemblyError(f"IFC not found: {path}")
    from . import product_facts as PF          # engine reader selection
    f = PF._open_ifc(path)

    try:
        import ifcopenshell.util.unit as uu
        scale = float(uu.calculate_unit_scale(f))
    except Exception:
        scale = 1.0
    to_ft = scale * FT_PER_M

    proj = (f.by_type("IfcProject") or [None])[0]
    project_name = str(proj.Name) if (proj is not None and proj.Name) else ""
    application = ""
    try:
        apps = f.by_type("IfcApplication")
        application = str(apps[0].ApplicationFullName) if apps else ""
    except Exception:
        application = ""
    asm = ""
    asm_tag = asm_desc = ""
    identity: Dict[str, str] = {}
    for a in (f.by_type("IfcElementAssembly") or []):
        if getattr(a, "Name", None):
            asm = str(a.Name)
            asm_tag = str(getattr(a, "Tag", "") or "")
            asm_desc = str(getattr(a, "Description", "") or "")
            identity = _pset_identity(a)
            break

    parts: List[PartSolid] = []
    skipped: List[Dict[str, str]] = []
    decomposed: List[Dict[str, Any]] = []
    kept_prism: List[Dict[str, str]] = []
    for i, prod in enumerate(f.by_type("IfcProduct") or []):
        if prod.is_a("IfcSpatialStructureElement") or prod.is_a("IfcSpatialElement"):
            continue
        tess = _tessellations(prod)
        name = _name_of(prod, i)
        if not tess:
            if getattr(prod, "Representation", None) is not None:
                skipped.append({"name": name, "ifc_class": prod.is_a(),
                                "reason": "body is not tessellated (only meshes are measured)"})
            continue
        try:
            m = PF._placement_matrix(prod)
        except Exception:
            m = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                 [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]
        pts_ft: List[Tuple[float, float, float]] = []
        tris: List[Tuple[int, int, int]] = []
        n_faces = 0
        closed = True
        for it in tess:
            n_faces += PF._mesh_face_count(it)
            base = len(pts_ft)                  # items concatenate: re-base indices
            for p in PF._mesh_points(it):
                w = _apply(m, p)
                pts_ft.append((w[0] * to_ft, w[1] * to_ft, w[2] * to_ft))
            item_tris = _mesh_triangles(it)
            if not item_tris:
                closed = False
            tris.extend((a + base, b + base, c + base) for a, b, c in item_tris)
        vol = mesh_volume(pts_ft, tris) if (closed and tris) else None
        try:
            fit = fit_solid(pts_ft, vol)
        except AssemblyError as e:
            skipped.append({"name": name, "ifc_class": prod.is_a(), "reason": str(e)})
            continue
        pn, ref = _identity_of(prod)
        common = dict(ifc_class=prod.is_a(),
                      tag=str(getattr(prod, "Tag", "") or ""),
                      guid=str(getattr(prod, "GlobalId", "") or ""),
                      n_points=len(pts_ft), n_faces=n_faces,
                      part_number=pn, reference=ref,
                      bbox_ft=[list(fit["bbox"][0]), list(fit["bbox"][1])])

        # One prism is an ENVELOPE for a body whose section varies with height.
        # Cut it into slabs when that would actually buy fidelity, and only
        # keep the result if it really is closer to the mesh.
        dec = None
        method = ""
        # An AXIS-ALIGNED body reproduces EXACTLY as boxes -- try that first.
        # This is the C-channel answer: a channel is a union of axis-aligned
        # boxes, each Z-extrudable, whichever direction the channel runs.
        if decompose and (fit.get("fill") or 0.0) < DECOMPOSE_FILL:
            box = decompose_boxes(pts_ft, tris)
            if box is not None:
                dec, method = box, "boxes"
                dec["fill_after"] = 1.0             # exact by construction
                dec["n_slabs"] = 0
                dec["holes_filled"] = 0
                dec["dropped"] = 0
        if dec is None and decompose and vol is not None \
                and (fit.get("fill") or 0.0) < DECOMPOSE_FILL:
            method = "slabs"
            dec = decompose_slabs(pts_ft, tris)
            if dec is not None:
                dv = dec["volume_ft3"]
                before = fit.get("fill") or 0.0
                if dv <= 0 or not _conserves(dv, vol):
                    # authored less material than the mesh holds: a ring was
                    # mis-nested or a region was lost. A better-looking fill
                    # ratio does not make that solid right.
                    kept_prism.append({"name": name, "reason": (
                        f"slab decomposition dropped material "
                        f"({dv * 1728:.3f} in3 authored vs {vol * 1728:.3f} in3 in the mesh)")})
                    dec = None
                elif vol / dv < before + 0.02:
                    kept_prism.append({"name": name, "reason": (
                        f"slab decomposition was no closer than the single prism "
                        f"(fill {vol / dv:.2f} vs {before:.2f})")})
                    dec = None
            else:
                kept_prism.append({"name": name, "reason": (
                    "not decomposable into horizontal slabs (an ambiguous slice, "
                    "one Z level, or over the part budget) -- its section most "
                    "likely runs along X or Y, which the Z-extruded part contract "
                    "cannot express")})
        if dec is not None:
            n = len(dec["parts"])
            after = (1.0 if dec.get("exact")
                     else (vol / dec["volume_ft3"] if dec["volume_ft3"] else None))
            for k, part in enumerate(dec["parts"], 1):
                nm = f"{name} [{k}/{n}]" if n > 1 else name
                if part["shape"] == "box":
                    parts.append(PartSolid(
                        name=nm, fit="box", center_ft=tuple(part["center"]),
                        height_ft=part["height_ft"], base_z_ft=part["base_z_ft"],
                        width_ft=part["width_ft"], depth_ft=part["depth_ft"],
                        fill=after, of_product=name, slabs=dec["n_slabs"], **common))
                else:
                    parts.append(PartSolid(
                        name=nm, fit="polygon", center_ft=(0.0, 0.0),
                        height_ft=part["height_ft"], base_z_ft=part["base_z_ft"],
                        vertices_ft=part["vertices"],
                        fill=after, of_product=name, slabs=dec["n_slabs"], **common))
            rec = {
                "name": name, "method": method, "parts": n,
                "slabs": dec["n_slabs"], "exact": bool(dec.get("exact")),
                "fill_before": round(float(fit.get("fill") or 0.0), 4),
                "fill_after": (round(after, 4) if after is not None else None),
                "holes_filled": dec["holes_filled"], "slivers_dropped": dec["dropped"]}
            if dec.get("overlap_ft3"):
                rec["mesh_overlap_in3"] = round(dec["overlap_ft3"] * 1728.0, 4)
                rec["note"] = ("the source mesh is SEVERAL SHELLS that overlap; its "
                               "divergence volume counts that overlap twice, so the "
                               "pre-decomposition fill was understated")
            decomposed.append(rec)
            continue

        parts.append(PartSolid(
            name=name,
            fit=fit["fit"], center_ft=tuple(fit["center"]),
            height_ft=fit["height_ft"], base_z_ft=fit["base_z_ft"],
            width_ft=fit.get("width_ft"), depth_ft=fit.get("depth_ft"),
            radius_ft=fit.get("radius_ft"), vertices_ft=fit.get("vertices"),
            fill=(None if fit.get("fill") is None else float(fit["fill"])),
            of_product=name, **common))

    if not parts:
        detail = ("; ".join(f"{s['name']}: {s['reason']}" for s in skipped[:4])
                  or "no IfcProduct carries a tessellated body")
        raise AssemblyError(
            f"no measurable solid in {os.path.basename(path)} -- {detail}")

    model = AssemblyModel(
        source_path=path, schema=str(getattr(f, "schema", "") or ""),
        project_name=project_name, application=application,
        assembly_name=asm, unit_scale_m=scale, parts=parts, skipped=skipped,
        decomposed=decomposed, kept_prism=kept_prism, identity=identity,
        assembly_tag=asm_tag, assembly_description=asm_desc,
    )
    model.notes.append(
        f"{len(parts)} product(s) measured into prismatic solids "
        f"({', '.join(f'{k}x{v}' for k, v in sorted(model.fit_counts().items()))}); "
        f"every dimension is GIVEN by the caller's mesh, never a catalog fact")
    envelopes = sorted((p for p in parts if p.fill is not None and p.fill < 0.95),
                       key=lambda p: p.fill)
    if envelopes:
        model.notes.append(
            f"{len(envelopes)} of {len(parts)} part(s) are ENVELOPES, not exact "
            f"bodies -- the authored prism is larger than the mesh it came from "
            f"(fill = mesh volume / prism volume): "
            + ", ".join(f"{p.name} {p.fill * 100:.0f}%" for p in envelopes[:6]))
    if skipped:
        model.notes.append(
            f"{len(skipped)} product(s) skipped by name (never guessed): "
            + "; ".join(f"{s['name']} ({s['reason']})" for s in skipped[:4]))
    return model.recentre() if recentre else model


def assembly_parts(ifc_path: str, *, recentre: bool = True,
                   decompose: bool = True) -> List[Dict[str, Any]]:
    """The ``parts=[...]`` list for
    :func:`rvt.famgen.factory.make_generic_model` -- the one call the router
    lane needs."""
    return read_assembly(ifc_path, recentre=recentre,
                         decompose=decompose).to_parts()

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

So a solid whose cross-section VARIES with height is over-approximated to
its shadow prism: a strut channel's C-profile becomes its rectangular
envelope, a hex nut's chamfer disappears, a bolt's thread is a smooth
cylinder.  :attr:`PartSolid.fill` records exactly how much of the prism the
mesh actually occupies -- the mesh's own closed-surface volume (divergence
theorem over its triangles) over the authored prism's volume -- so the report
can say which parts are faithful and which are envelopes, per part, in
numbers instead of adjectives.  Nothing is invented: a product with no
tessellated body is SKIPPED BY NAME, never given a guessed size.

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
            "parts": [p.to_json() for p in self.parts],
            "skipped": list(self.skipped),
            "notes": list(self.notes),
        }

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


def _name_of(prod, index: int) -> str:
    for attr in ("Name", "Description", "Tag"):
        v = getattr(prod, attr, None)
        if v:
            return str(v)
    return f"{prod.is_a()} {index + 1}"


def read_assembly(ifc_path: str, *, recentre: bool = True) -> AssemblyModel:
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
    for a in (f.by_type("IfcElementAssembly") or []):
        if getattr(a, "Name", None):
            asm = str(a.Name)
            break

    parts: List[PartSolid] = []
    skipped: List[Dict[str, str]] = []
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
        parts.append(PartSolid(
            name=name, ifc_class=prod.is_a(),
            tag=str(getattr(prod, "Tag", "") or ""),
            guid=str(getattr(prod, "GlobalId", "") or ""),
            fit=fit["fit"], center_ft=tuple(fit["center"]),
            height_ft=fit["height_ft"], base_z_ft=fit["base_z_ft"],
            width_ft=fit.get("width_ft"), depth_ft=fit.get("depth_ft"),
            radius_ft=fit.get("radius_ft"), vertices_ft=fit.get("vertices"),
            n_points=len(pts_ft), n_faces=n_faces,
            fill=(None if fit.get("fill") is None else float(fit["fill"])),
            bbox_ft=[list(fit["bbox"][0]), list(fit["bbox"][1])],
        ))

    if not parts:
        detail = ("; ".join(f"{s['name']}: {s['reason']}" for s in skipped[:4])
                  or "no IfcProduct carries a tessellated body")
        raise AssemblyError(
            f"no measurable solid in {os.path.basename(path)} -- {detail}")

    model = AssemblyModel(
        source_path=path, schema=str(getattr(f, "schema", "") or ""),
        project_name=project_name, application=application,
        assembly_name=asm, unit_scale_m=scale, parts=parts, skipped=skipped,
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


def assembly_parts(ifc_path: str, *, recentre: bool = True) -> List[Dict[str, Any]]:
    """The ``parts=[...]`` list for
    :func:`rvt.famgen.factory.make_generic_model` -- the one call the router
    lane needs."""
    return read_assembly(ifc_path, recentre=recentre).to_parts()
